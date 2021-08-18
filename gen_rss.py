#!/usr/bin/env python3

import argparse
import base64
import csv
import datetime
import hashlib
import logging
import os.path
import re
import urllib.request
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from bs4 import SoupStrainer
import dateparser
from feedgen.feed import FeedGenerator

EXPOSURE_URL = 'https://www.covid19.act.gov.au/act-status-and-response/act-covid-19-exposure-locations'
CSV_REGEX = 'https://www[.]covid19[.]act[.]gov[.]au/.*?[.]csv'
FIELDS = ['Event Id', 'Status', 'Exposure Site', 'Street', 'Suburb', 'State', 'Date', 'Arrival Time', 'Departure Time', 'Contact']

# Attempt to normalise data
def normalise(locations):
    for location in locations:
        for k, v in location.items():
            # Could be a dict but reasonably complex and the less tying to field names the better
            if k == 'Date':
                value = dateparser.parse(v)
                location[k] = v.strip().title() if value is None else value.isoformat()
            elif 'Time' in k:
                value = dateparser.parse(v)
                location[k] = v.strip().lower() if value is None else value.time().isoformat()
            elif k == 'Exposure Site':
                location[k] = v.strip()
            else:
                location[k] = v.strip().title()

# Find CSV location, returns None if can't find it
def find_csv_location():
    # Still use soup to limit our searching
    only_script = SoupStrainer("script")
    csv_regex = re.compile(CSV_REGEX)
    # TODO: Retry then fail
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
    # TODO: Retry then fail
    with urllib.request.urlopen(csv_location) as response:
        csv_data = response.read()
    return csv_data


# Generates locations based of CSV data
def parse_csv(csv_data):
    # Use reader rather than DictReader so can normalise fields
    # TODO: Parsing error
    rows = csv.reader(csv_data.splitlines())
    fields = [x.strip().title() for x in next(rows)]
    # If fields don't match what we support return None so don't spam when change
    # Can make a map to fix later
    if set(fields) != set(FIELDS):
        return None
    locations = []
    for i,row in enumerate(rows):
        l = {fields[i]: row[i].strip() for i in range(len(fields))}
        locations.append(l)
    return locations


# Add an id to each exposure location
def gen_id(locations):
    # Assume there is always a 'Event Id' and 'Status' out the front and just join everything else.
    # If time is updated will get a new entry, we are ignoring status field.
    # Given we have no id to go by, if a new time slot added for the same location at the same day there is no way to differentiate.
    # NOTE: Need to ensure python 3.7+ for insertion order remembering
    # Use base64(MD5) to reduce size, could also remove base64 padding
    for location in locations:
        digest = hashlib.md5('-'.join(list(location.values())[2:]).encode("utf-8")).digest()
        location['id'] = base64.b64encode(digest).decode("utf-8")


# Parse args, optinally pass in manually
def parse_args(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('file', metavar='FILE', nargs=1, help='Output file')
    return parser.parse_args(args)


# Gen RSS descrption tag
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
            if 'Time' in k:
                d = dateparser.parse(v)
                if d is not None:
                    v = d.strftime('%H%M')
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
        # NOTE: This header could easily change in data
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
    logging.info("Loaded CSV")
    # Excel likes to add BOM hence -sig
    locations = parse_csv(csv_data.decode("utf-8-sig"))
    logging.info("Found %d locations", len(locations))
    normalise(locations)
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
