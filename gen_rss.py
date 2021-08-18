#!/usr/bin/env python3
# NOTE: Ensure utf-8 support in rss xml

import argparse
import base64
import csv
import datetime
import hashlib
import logging
import os.path
import re
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from bs4 import SoupStrainer
import dateparser
from feedgen.feed import FeedGenerator

from helper_fns import suburb_to_region

EXPOSURE_URL = 'https://www.covid19.act.gov.au/act-status-and-response/act-covid-19-exposure-locations'
CSV_REGEX = 'https://www[.]covid19[.]act[.]gov[.]au/.*?[.]csv'


# extract locations
def parse_table(s, tableid, category):
    # TODO: check one and only one else error
    table = s.find_all(id=tableid)[0].find_all('tr')
    locations = []
    # unfortunately have different headers for different tables
    # lookup via header name isn't foolproof, could normalise to lowercase but thats about it
    fields = list(table[0].stripped_strings)
    # Normalise field names
    fields = [x.title() for x in fields]
    for location in table[1:]:
        columns = location.find_all('td')
        l = {}
        # Normalise to NFKD to remove hard breaks
        for num, column in enumerate(columns):
            # If there are multiple p elements in the Place field handle separately
            p = column.find_all('p')
            if p is not None and fields[num] == 'Place' and len(p) == 2:
                l[fields[num]] = unicodedata.normalize('NFKD', p[0].get_text().strip())
                # Add extra info if there is a <a> element in the place name
                a = p[1].find('a')
                if a is not None:
                    l['Info'] = a.encode().decode("utf-8")
            # Try to normalise as best we can to avoid rss spam
            else:
                value = None
                if fields[num] == 'Date':
                    # NOTE: Should return a naive datetime
                    value = dateparser.parse(column.get_text().strip())
                    # If fail to pull out date just use the column
                    value = column.get_text().strip() if value is None else value.isoformat()
                elif 'Time' in fields[num]:
                    value = column.get_text().strip().lower()
                elif fields[num] == 'Suburb':
                    value = column.get_text().strip().title()
                else:
                    value = column.get_text().strip()
                l[fields[num]] = unicodedata.normalize('NFKD', value)
        l['Exposure Type'] = category
        locations.append(l)
    return locations


# Find CSV location, returns None if can't find it
def find_csv_location():
    # Still use soup to limit our searching
    only_script = SoupStrainer("script")
    csv_regex = re.compile(CSV_REGEX)
    with urllib.request.urlopen(EXPOSURE_URL) as response:
        html = response.read()
        soup = BeautifulSoup(html, 'html.parser', parse_only=only_script)
        for script in soup.find_all():
            # TODO: Should only be one match
            csv_location = csv_regex.search(''.join(list(script.contents)))
            if csv_location is not None:
                return csv_location[0]
    return None


# Grab and return the CSV, returns None if fails
def get_csv(csv_location):
    csv_data = None
    with urllib.request.urlopen(csv_location) as response:
        csv_data = response.read()
    return csv_data


# Generates locations based of CSV data
def parse_csv(csv_data):
    # Use reader rather than DictReader so can do normalisation
    rows = csv.reader(csv_data.splitlines())
    fields = [x.strip().title() for x in next(rows)]
    locations = []
    for i, row in enumerate(rows):
        # TODO: Currently no normalisation
        l = {fields[i]: row[i].strip() for i in range(len(fields))}
        if l.get("Suburb"):
            l = {**l, "Region": suburb_to_region(l.get("Suburb"))}
        locations.append(l)
    return locations


# add an id to each exposure location
def gen_id(locations):
    # Assume there is always a 'Event Id' and 'Status' out the front and just join everything else.
    # If time is updated will get a new entry, we are ignoring status field.
    # Given we have no id to go by, if a new time slot added for the same location at the same day there is no way to
    # differentiate.
    # NOTE: Need to ensure python 3.7+ for insertion order remembering
    # Use base64(MD5) to reduce size, could also remove base64 padding
    for location in locations:
        digest = hashlib.md5('-'.join(list(location.values())[2:]).encode("utf-8")).digest()
        location['id'] = base64.b64encode(digest).decode("utf-8")


# Parse args, optionally pass in manually
def parse_args(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('file', metavar='FILE', nargs=1, help='Output file')
    return parser.parse_args(args)


# Gen RSS description tag
def gen_desc(loc):
    desc = []
    for k, v in loc.items():
        # NOTE: Locks into RSS
        if k not in ['id', 'pubDate']:
            # Format here so if we decide to change output wont spam rss
            if k == 'Date':
                d = dateparser.parse(v)
                if d is not None:
                    v = d.strftime('%A, %d %B %Y')
            desc.append('<b>' + k + '</b>:' + v + '<br/>')
    return ''.join(desc)


# Check old RSS file if exists, if so keep original pubDate for any items
# Return if True if something changed from the old RSS file
def check_existing(rss_file, exposures):
    # see if file already exists, if so load it
    # Could try to avoid 2x file opens
    existing = []
    if os.path.exists(rss_file):
        # get existing ids, if bad XML will fail/die
        tree = ET.parse(rss_file)
        existing = tree.findall('./channel/item')

    # Compare ids to last ones, anything that exists in old one we keep the old pubDate
    # If could reliably detect updates could set lastBuildDate
    # TODO: This entire thing is still ugly/inefficient
    found = []
    locations = {}
    # Generate hash of locations for quick lookup
    for loc in exposures:
        found.append(loc['id'])
        locations[loc['id']] = loc
    guids = []
    # Go through existing items and look for a match
    for exists in existing:
        guid = exists.find('guid').text
        guids.append(guid)
        if guid in locations:
            # NOTE: Locks into RSS
            locations[guid]['pubDate'] = exists.find('pubDate').text

    # We have made changes if the ids don't match
    return set(found) != set(guids)


# Build the RSS feed and write it to rss_file
def gen_feed(rss_file, locations):
    fg = FeedGenerator()
    pd = datetime.datetime.now(datetime.timezone.utc)
    for loc in locations:
        fe = fg.add_entry()
        # NOTE: This could easily change in data, possibly normalise in parsing?
        fe.title(loc['Exposure Site'])
        fe.description(gen_desc(loc))
        fe.guid(loc['id'])
        # NOTE: Locks into RSS
        fe.pubDate(loc['pubDate']) if 'pubDate' in loc else fe.pubDate(pd)
    fg.title("ACT Exposure Locations")
    fg.link(href=EXPOSURE_URL, rel='alternate')
    fg.description("Feed scraped from ACT exposure website")
    fg.lastBuildDate(pd)
    # doesn't actually return string
    with open(rss_file, 'w', encoding="utf-8") as f:
        f.write(fg.rss_str().decode("utf-8"))


def main():
    logging.basicConfig(level=logging.INFO)
    args = parse_args()

    csv_location = find_csv_location()
    logging.info("Found CSV location at: %s", csv_location)
    csv_data = get_csv(csv_location)
    locations = parse_csv(csv_data.decode("utf-8"))
    logging.info("Found %d locations", len(locations))
    gen_id(locations)

    rss_file = args.file[0]
    changed = check_existing(rss_file, locations)

    # Convert time, nice to standardise display as well as use later for geo
    # Time format could change at any time
    # Date, Arrival Time, Departure Time

    # Do geo lookup, could be very error prone
    # Could support georss, kml and show source in leaflet etc

    # TODO: If there is an error consider creating a random guid with message
    # This is so user knows to not trust the source anymore
    # Often readers are pretty unobtrusive in showing broken feeds
    # If error is in previous is feed then don't send it again
    # Consider what happens if error state toggles if send a 'everything is ok again' msg
    if changed:
        logging.info("Contents changed, regenerating feed")
        gen_feed(rss_file, locations)
    else:
        logging.info("Contents unchanged, doing nothing")


if __name__ == '__main__':
    main()
