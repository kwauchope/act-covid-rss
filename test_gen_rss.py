import copy
import io
import unittest



import gen_rss

CSV_LINES = """Event Id,Status,Exposure Site,Street,Suburb,State,Date,Arrival Time,Departure Time,Contact
,,Harvey Norman,Barrier Street,Fyshwick,ACT,10/08/2021 - Tuesday,10:00am,11:00am,Close
,,Canberra Outlet Centre,377 Canberra Avenue,Fyshwick,ACT,08/08/2021 - Sunday,2:00pm,3:30pm,Monitor
,,Gold Creek School (including Early Childhood Learning Centre),Kelleway Avenue,Nicholls,ACT,12/08/2021 - Thursday,8:00am,3:10pm,Close
"""
CSV_PARSED = [
        {
            'Arrival Time': '10:00am',
            'Contact': 'Close',
            'Date': '10/08/2021 - Tuesday',
            'Departure Time': '11:00am',
            'Event Id': '',
            'Exposure Site': 'Harvey Norman',
            'Region': 'Inner South',
            'State': 'ACT',
            'Status': '',
            'Street': 'Barrier Street',
            'Suburb': 'Fyshwick'
        },
        {
            'Arrival Time': '2:00pm',
            'Contact': 'Monitor',
            'Date': '08/08/2021 - Sunday',
            'Departure Time': '3:30pm',
            'Event Id': '',
            'Exposure Site': 'Canberra Outlet Centre',
            'Region': 'Inner South',
            'State': 'ACT',
            'Status': '',
            'Street': '377 Canberra Avenue',
            'Suburb': 'Fyshwick'
        },
        {
            'Arrival Time': '8:00am',
            'Contact': 'Close',
            'Date': '12/08/2021 - Thursday',
            'Departure Time': '3:10pm',
            'Event Id': '',
            'Exposure Site': 'Gold Creek School (including Early Childhood Learning Centre)',
            'Region': 'Gungahlin',
            'State': 'ACT',
            'Status': '',
            'Street': 'Kelleway Avenue',
            'Suburb': 'Nicholls'
        }
]


def filter_rss(rss_str):
    dynamic_fields = ["lastBuildDate", "pubDate"]
    return '\n'.join(x for x in rss_str.splitlines() if all(y not in x for y in dynamic_fields))

def preprocess_locs(locs):
    dup = copy.deepcopy(locs)
    dup = gen_rss.normalise(dup)
    gen_rss.gen_id(dup)
    return dup

class TestParsingCSV(unittest.TestCase):

    def test_parse_csv(self):
        res = gen_rss.parse_csv(CSV_LINES)
        gen_rss.gen_region(res)
        for a,b in zip(res, CSV_PARSED):
            self.assertDictEqual(a, b)

    def test_rss_full(self):
        dup = preprocess_locs(CSV_PARSED)
        state = {}
        gen_rss.update_state(state, dup)
        out = gen_rss.gen_feed(state)

        expected = """<?xml version='1.0' encoding='UTF-8'?>
<rss xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0">
  <channel>
    <title>ACT Exposure Locations</title>
    <link>https://www.covid19.act.gov.au/act-status-and-response/act-covid-19-exposure-locations</link>
    <description>Feed scraped from ACT exposure website</description>
    <docs>http://www.rssboard.org/rss-specification</docs>
    <generator>python-feedgen</generator>
    <lastBuildDate>Fri, 20 Aug 2021 14:53:44 +0000</lastBuildDate>
    <item>
      <title>Nicholls:Gold Creek School (including Early Childhood Learning Centre)</title>
      <description><![CDATA[<b>Arrival Time</b>:0800<br/><b>Contact</b>:Close<br/><b>Date</b>:Thursday, 12 August 2021<br/><b>Departure Time</b>:1510<br/><b>Event Id</b>:<br/><b>Exposure Site</b>:Gold Creek School (including Early Childhood Learning Centre)<br/><b>Region</b>:Gungahlin<br/><b>State</b>:ACT<br/><b>Status</b>:<br/><b>Street</b>:Kelleway Avenue<br/><b>Suburb</b>:Nicholls<br/>]]></description>
      <guid isPermaLink="false">Bpk43ora2GlShwB6nKUZpg==</guid>
      <pubDate>Fri, 20 Aug 2021 14:53:44 +0000</pubDate>
    </item>
    <item>
      <title>Fyshwick:Harvey Norman</title>
      <description><![CDATA[<b>Arrival Time</b>:1000<br/><b>Contact</b>:Close<br/><b>Date</b>:Tuesday, 10 August 2021<br/><b>Departure Time</b>:1100<br/><b>Event Id</b>:<br/><b>Exposure Site</b>:Harvey Norman<br/><b>Region</b>:Inner South<br/><b>State</b>:ACT<br/><b>Status</b>:<br/><b>Street</b>:Barrier Street<br/><b>Suburb</b>:Fyshwick<br/>]]></description>
      <guid isPermaLink="false">iLODwJEKeYg5/3oi0CizTQ==</guid>
      <pubDate>Fri, 20 Aug 2021 14:53:44 +0000</pubDate>
    </item>
    <item>
      <title>Fyshwick:Canberra Outlet Centre</title>
      <description><![CDATA[<b>Arrival Time</b>:1400<br/><b>Contact</b>:Monitor<br/><b>Date</b>:Sunday, 08 August 2021<br/><b>Departure Time</b>:1530<br/><b>Event Id</b>:<br/><b>Exposure Site</b>:Canberra Outlet Centre<br/><b>Region</b>:Inner South<br/><b>State</b>:ACT<br/><b>Status</b>:<br/><b>Street</b>:377 Canberra Avenue<br/><b>Suburb</b>:Fyshwick<br/>]]></description>
      <guid isPermaLink="false">oxT1t6ljYzDG0NBj4Hr6sw==</guid>
      <pubDate>Fri, 20 Aug 2021 14:53:44 +0000</pubDate>
    </item>
  </channel>
</rss>
"""
        out = filter_rss(out)
        expected = filter_rss(expected)
        self.assertEqual(out, expected)


    def test_summarise(self):
        dup = preprocess_locs(CSV_PARSED)
        state = {}
        new = gen_rss.update_state(state, dup, cur_time=1)
        res = gen_rss.summarise_feed(new)

        expected = """<?xml version='1.0' encoding='UTF-8'?>
<rss xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0">
  <channel>
    <title>ACT Exposure Summaries</title>
    <link>https://www.covid19.act.gov.au/act-status-and-response/act-covid-19-exposure-locations</link>
    <description>Feed scraped from ACT exposure website</description>
    <docs>http://www.rssboard.org/rss-specification</docs>
    <generator>python-feedgen</generator>
    <lastBuildDate>Fri, 20 Aug 2021 15:05:47 +0000</lastBuildDate>
    <item>
      <title>3 additional exposure sites</title>
      <link>https://www.covid19.act.gov.au/act-status-and-response/act-covid-19-exposure-locations</link>
      <description><![CDATA[<b>Fyshwick:</b>2<br/><b>Nicholls:</b>1<br/>]]></description>
      <guid isPermaLink="false">QKtEQJFTu3kjlQbfIAXTcA==</guid>
      <pubDate>Thu, 01 Jan 1970 10:00:01 +0000</pubDate>
    </item>
  </channel>
</rss>
"""
        res = filter_rss(res)
        expected = filter_rss(expected)
        self.assertEqual(res, expected)


if __name__ == "__main__":
    unittest.main()
