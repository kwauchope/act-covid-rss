#!/usr/bin/env python3

import argparse
import base64
import csv
import hashlib
import itertools
import json
import logging
import re
import urllib.request

from collections import Counter
from datetime import datetime, time, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from bs4 import SoupStrainer
import dateparser
from feedgen.feed import FeedGenerator

from helper_fns import suburb_to_region

EXPOSURE_URL = 'https://www.covid19.act.gov.au/act-status-and-response/act-covid-19-exposure-locations'
CSV_REGEX = 'https://www[.]covid19[.]act[.]gov[.]au/.*?[.]csv'
FIELDS = ['Event Id', 'Status', 'Exposure Site', 'Street', 'Suburb', 'State', 'Date', 'Arrival Time', 'Departure Time', 'Contact']
MIN_DATETIME = datetime(2020, 3, 11)


# Attempt to normalise data
def normalise(locations):
    invalid = set()
    now = datetime.now()
    for i, location in enumerate(locations):
        for k, v in location.items():
            # Could be a dict but reasonably complex and the less tying to field names the better
            if k == 'Date':
                value = dateparser.parse(v, languages=['en'], settings={'DATE_ORDER': 'DMY'})
                # If None or out of range add to set to delete and log warn
                if value is None or value < MIN_DATETIME or value > now:
                    invalid.add(i)
                    logging.warning("Invalid Date '%s' found in '%s'", v, location)
                    break
                # Could change to date for less characters, if so change gen_desc to use date
                location[k] = value.isoformat()
            elif 'Time' in k:
                value = dateparser.parse(v, languages=['en'], settings={'DATE_ORDER': 'DMY'})
                # If None add to set to delete and log warn
                if value is None:
                    invalid.add(i)
                    logging.warning("Invalid Time '%s' found in '%s'", v, location)
                    break
                location[k] = value.time().isoformat()
            elif k == 'Exposure Site':
                location[k] = v.strip()
            elif k == 'State':
                location[k] = v.strip().upper()
            else:
                location[k] = v.strip().title()
    if len(invalid):
        logging.warning("%d invalid record found", len(invalid))
    return [x for i, x in enumerate(locations) if i not in invalid]


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
    # In case extra empty columns/fields added again remove them
    while not fields[-1]:
        fields.pop()
    # If fields don't match what we support return None so don't spam when change
    # Can make a map to fix later
    locations = []
    if set(fields) != set(FIELDS):
        # Now we no longer have a header, at least make sure new headings haven't been added
        if len(fields) == len(FIELDS):
            # Pretty average hack to put the first row back in if headers aren't present
            l = {FIELDS[i]: fields[i].strip() for i in range(len(FIELDS))}
            locations.append(l)
            fields = FIELDS
        else:
            logging.error("Field mismatch")
            return None
    for row in rows:
        l = {fields[i]: row[i].strip() for i in range(len(fields))}
        locations.append(l)
    return locations


# Add an id to each exposure location
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

# Add region to locations
def gen_region(locations):
    for location in locations:
        if location.get("Suburb"):
            location["Region"] = suburb_to_region(location["Suburb"])


# Parse args, optionally pass in manually
def parse_args(args=None):
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('prefix', metavar='PREFIX', nargs=1, help='prefix for output files')
    parser.add_argument('--csv', type=argparse.FileType('r', encoding='utf-8-sig'),
            help='Use local CSV rather than getting from website')

    return parser.parse_args(args)


# Gen RSS description tag
def gen_desc(loc):
    desc = []
    for k, v in loc.items():
        # NOTE: Locks into RSS
        if k not in ['id', 'pubDate']:
            # Format here so if we decide to change output wont spam rss
            # NOTE: much less overhead with datetime as in a format we know (hopefully)
            if k == 'Date':
                d = datetime.fromisoformat(v)
                v = d.strftime('%A, %d %B %Y')
            if 'Time' in k:
                d = time.fromisoformat(v)
                v = d.strftime('%H%M')
            desc.append('<b>' + k + '</b>:' + v + '<br/>')
    return ''.join(desc)


# Check old RSS file if exists, if so keep original pubDate for any items
# Return if True if something changed from the old RSS file
def update_state(existing, exposures, cur_time=None):
    """Update the state with new entries."""
    # Compare ids to last ones, anything that exists in old one we keep the old pubDate
    # If could reliably detect updates could set lastBuildDate
    # TODO: This entire thing is still ugly/inefficient
    # Generate hash of locations for quick lookup
    exposure_guids = {x['id']: x for x in exposures}
    # Delete old entries from state.
    for guid in existing.keys() - exposure_guids:
        del existing[guid]

    cur_time = cur_time or datetime.utcnow().timestamp()
    new_entries = exposure_guids.keys() - existing
    for new_entry in new_entries:
        loc = exposure_guids[new_entry]
        loc['pubDate'] = cur_time
        existing[new_entry] = loc

    # Return the updated ids
    return {x: exposure_guids[x] for x in new_entries}


# Build the RSS feed and write it to rss_file
def gen_feed(locations):
    fg = FeedGenerator()
    pd = datetime.now(timezone.utc)

    for loc in sorted(locations.values(), key=lambda x: (x['pubDate'], x['id']), reverse=True):
        fe = fg.add_entry()
        # NOTE: These headers could easily change in data
        fe.title(loc['Suburb'] + ':' + loc['Exposure Site'])
        fe.description(gen_desc(loc))
        fe.guid(loc['id'])
        # NOTE: Locks into RSS
        fe.pubDate(datetime.fromtimestamp(loc['pubDate']).replace(tzinfo=timezone.utc))
    fg.title("ACT Exposure Locations")
    fg.link(href=EXPOSURE_URL, rel='alternate')
    fg.description("Feed scraped from ACT exposure website")
    fg.lastBuildDate(pd)

    return fg.rss_str(pretty=True).decode('utf-8')

def summarise_feed(locations):
    """Return a summary of new locations since the last update."""

    def summarise_group(grp):
        counts = Counter(x['Suburb'] for x in grp)
        desc = [f"<b>{suburb}:</b>{count}<br/>" for (suburb,count) in counts.most_common()]
        return ''.join(desc)

    fg = FeedGenerator()
    pd = datetime.now(timezone.utc)

    locations = sorted(locations.values(), key=lambda x: (x['pubDate'], x['id']), reverse=True)
    for pubDate, locs in itertools.groupby(locations, key=lambda x: x['pubDate']):
        locs = list(locs)
        fe = fg.add_entry()
        # NOTE: This could easily change in data, possibly normalise in parsing?
        fe.title(f"{len(locs)} additional exposure sites")
        desc = summarise_group(locs)
        fe.description(desc)
        digest = hashlib.md5(f"{pubDate}-{desc}".encode("utf-8")).digest()
        guid = base64.b64encode(digest).decode("utf-8")
        fe.guid(guid)
        fe.link(href=EXPOSURE_URL)
        # NOTE: Locks into RSS
        fe.pubDate(datetime.fromtimestamp(pubDate).replace(tzinfo=timezone.utc))
    fg.title("ACT Exposure Summaries")
    fg.link(href=EXPOSURE_URL, rel='alternate')
    fg.description("Feed scraped from ACT exposure website")
    fg.lastBuildDate(pd)

    return fg.rss_str(pretty=True).decode('utf-8')


def main():
    logging.basicConfig(level=logging.INFO)
    args = parse_args()

    rss_file = Path(args.prefix[0] + '.rss')
    rss_summary_file = Path(args.prefix[0] + '_summary.rss')
    state_file = Path(args.prefix[0] + '_state.json')
    csv_file = Path(args.prefix[0] + '.csv')

    locations = []
    # Excel likes to add BOM hence -sig
    if args.csv is not None:
        locations = parse_csv(args.csv.read())
    else:
        csv_location = find_csv_location()
        logging.info("Found CSV location at: %s", csv_location)
        csv_data = get_csv(csv_location)
        logging.info("Loaded CSV")
        # Dump out CSV for debugging
        csv_file.write_bytes(csv_data)
        logging.info("Dumped CSV")
        locations = parse_csv(csv_data.decode("utf-8-sig"))
    logging.info("Found %d locations", len(locations))
    locations = normalise(locations)
    gen_id(locations)
    gen_region(locations)

    state = {}
    if state_file.is_file():
        try:
            with state_file.open(encoding='utf-8') as f:
                state = json.load(f)
        except Exception as ex:
            logging.error("Failed loading state: %s", ex)

    changes = update_state(state, locations)

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
    if changes:
        logging.info("Contents changed, %d new entries, regenerating feed", len(changes))
        feed = gen_feed(state)
        rss_file.write_text(feed, encoding="utf-8")

        summary = summarise_feed(state)
        rss_summary_file.write_text(summary, encoding="utf-8")

        # update state
        with state_file.open('w', encoding='utf-8') as f:
            json.dump(state, f)
    else:
        logging.info("Contents unchanged, doing nothing")


if __name__ == '__main__':
    main()
