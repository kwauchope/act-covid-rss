#!/usr/bin/env python3
# NOTE: Ensure utf-8 support in rss xml

import argparse
import base64
import datetime
import hashlib
import os.path
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from bs4 import SoupStrainer
import dateparser
from feedgen.feed import FeedGenerator

EXPOSURE_URL = 'https://www.covid19.act.gov.au/act-status-and-response/act-covid-19-exposure-locations'
# TODO: Are these ids static or do they change?
CLOSE_TABLE_ID = 'table14458'
CASUAL_TABLE_ID = 'table66547'
MONITOR_TABLE_ID = 'table04293'


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
                    value = dateparser.parse(column.get_text().strip()).isoformat()
                    #If fail to pull out date just use the column
                    if value is None:
                        value = column.get_text().strip()
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


# pull the exposure tables from the site
def get_tables():
    html = ''
    # Also all in div id=suburbfiltertable
    # If add more tables to the page life is not great
    # Could test preceeding h3 matches expected name...
    only_tables = SoupStrainer("table")
    # TODO: Have n retries, then fail
    with urllib.request.urlopen(EXPOSURE_URL) as response:
        html = response.read()
    soup = BeautifulSoup(html, 'html.parser', parse_only=only_tables)
    return soup


# add an id to each exposure location
def gen_id(locations):
    # Assume there is always a 'Status' out the front and just join everything else. If time is updated will get a new
    # entry, we are ignoring status field. Given we have no id to go by, if a new time slot added for the same
    # location at the same day there is no way to differentiate. Would also need to keep past state to know if
    # NOTE: Need to ensure python 3.7+ for insertion order remembering
    # Use base64(MD5) to reduce size, could also remove base64 padding
    for location in locations:
        digest = hashlib.md5('-'.join(list(location.values())[1:]).encode("utf-8")).digest()
        location['id'] = base64.b64encode(digest).decode("utf-8")


def parse_args(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('file', metavar='FILE', nargs=1, help='Output file')
    return parser.parse_args(args)


def gen_desc(loc):
    desc = []
    for k, v in loc.items():
        # NOTE: Locks into RSS
        if k not in ['id', 'pubDate']:
            #Format here so if we decide to change output wont spam rss
            if k == 'Date':
                d = dateparser.parse(v)
                if d is not None:
                    v = d.strftime('%A, %d %B %Y')
            desc.append('<b>' + k + '</b>:' + v + '<br/>')
    return ''.join(desc)


def check_existing(rss_file, categories):
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
    for cat in categories:
        for loc in cat:
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


def gen_feed(rss_file, categories):
    fg = FeedGenerator()
    pd = datetime.datetime.now(datetime.timezone.utc)
    for cat in categories:
        for loc in cat:
            fe = fg.add_entry()
            fe.title(loc['Place'])
            fe.description(gen_desc(loc))
            fe.guid(loc['id'])
            # NOTE: Locks into RSS
            fe.pubDate(loc['pubDate']) if 'pubDate' in loc else fe.pubDate(pd)
    fg.title("ACT Exposure locations")
    fg.link(href=EXPOSURE_URL, rel='alternate')
    fg.description("Feed scraped from ACT exposure website")
    fg.lastBuildDate(pd)
    # doesn't actually return string
    with open(rss_file, 'w', encoding="utf-8") as f:
        f.write(fg.rss_str().decode("utf-8"))


def main():
    args = parse_args()

    soup = get_tables()

    # TODO: We keep categories separate, probably unnecessary and should flatten now they are tagged
    close = parse_table(soup, CLOSE_TABLE_ID, 'Close')
    casual = parse_table(soup, CASUAL_TABLE_ID, 'Casual')
    monitor = parse_table(soup, MONITOR_TABLE_ID, 'Monitor')
    categories = [close, casual, monitor]

    [gen_id(x) for x in categories]

    rss_file = args.file[0]
    changed = check_existing(rss_file, categories)

    # [print(x) for x in categories]

    # Convert time, nice to standardise display as well as use later for geo
    # Time format could change at any time
    # Date, Arrival Time, Departure Time

    # Do geo lookup

    # TODO: If there is an error create a random guid with message so user knows to not trust the source anymore
    # If last in previous list is an error then don't send it again
    if changed:
        gen_feed(rss_file, categories)


if __name__ == '__main__':
    main()
