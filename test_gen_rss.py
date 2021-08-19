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
    gen_rss.normalise(dup)
    gen_rss.gen_id(dup)
    return dup

class TestParsingCSV(unittest.TestCase):

    def test_parse_csv(self):
        res = gen_rss.parse_csv(CSV_LINES)
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
    <lastBuildDate>Thu, 19 Aug 2021 13:41:38 +0000</lastBuildDate>
    <item>
      <title>Nicholls:Gold Creek School (including Early Childhood Learning Centre)</title>
      <description>&lt;b&gt;Arrival Time&lt;/b&gt;:0800&lt;br/&gt;&lt;b&gt;Contact&lt;/b&gt;:Close&lt;br/&gt;&lt;b&gt;Date&lt;/b&gt;:Thursday, 12 August 2021&lt;br/&gt;&lt;b&gt;Departure Time&lt;/b&gt;:1510&lt;br/&gt;&lt;b&gt;Event Id&lt;/b&gt;:&lt;br/&gt;&lt;b&gt;Exposure Site&lt;/b&gt;:Gold Creek School (including Early Childhood Learning Centre)&lt;br/&gt;&lt;b&gt;Region&lt;/b&gt;:Gungahlin&lt;br/&gt;&lt;b&gt;State&lt;/b&gt;:ACT&lt;br/&gt;&lt;b&gt;Status&lt;/b&gt;:&lt;br/&gt;&lt;b&gt;Street&lt;/b&gt;:Kelleway Avenue&lt;br/&gt;&lt;b&gt;Suburb&lt;/b&gt;:Nicholls&lt;br/&gt;</description>
      <guid isPermaLink="false">Bpk43ora2GlShwB6nKUZpg==</guid>
      <pubDate>Thu, 19 Aug 2021 13:41:38 +0000</pubDate>
    </item>
    <item>
      <title>Fyshwick:Harvey Norman</title>
      <description>&lt;b&gt;Arrival Time&lt;/b&gt;:1000&lt;br/&gt;&lt;b&gt;Contact&lt;/b&gt;:Close&lt;br/&gt;&lt;b&gt;Date&lt;/b&gt;:Tuesday, 10 August 2021&lt;br/&gt;&lt;b&gt;Departure Time&lt;/b&gt;:1100&lt;br/&gt;&lt;b&gt;Event Id&lt;/b&gt;:&lt;br/&gt;&lt;b&gt;Exposure Site&lt;/b&gt;:Harvey Norman&lt;br/&gt;&lt;b&gt;Region&lt;/b&gt;:Inner South&lt;br/&gt;&lt;b&gt;State&lt;/b&gt;:ACT&lt;br/&gt;&lt;b&gt;Status&lt;/b&gt;:&lt;br/&gt;&lt;b&gt;Street&lt;/b&gt;:Barrier Street&lt;br/&gt;&lt;b&gt;Suburb&lt;/b&gt;:Fyshwick&lt;br/&gt;</description>
      <guid isPermaLink="false">iLODwJEKeYg5/3oi0CizTQ==</guid>
      <pubDate>Thu, 19 Aug 2021 13:41:38 +0000</pubDate>
    </item>
    <item>
      <title>Fyshwick:Canberra Outlet Centre</title>
      <description>&lt;b&gt;Arrival Time&lt;/b&gt;:1400&lt;br/&gt;&lt;b&gt;Contact&lt;/b&gt;:Monitor&lt;br/&gt;&lt;b&gt;Date&lt;/b&gt;:Sunday, 08 August 2021&lt;br/&gt;&lt;b&gt;Departure Time&lt;/b&gt;:1530&lt;br/&gt;&lt;b&gt;Event Id&lt;/b&gt;:&lt;br/&gt;&lt;b&gt;Exposure Site&lt;/b&gt;:Canberra Outlet Centre&lt;br/&gt;&lt;b&gt;Region&lt;/b&gt;:Inner South&lt;br/&gt;&lt;b&gt;State&lt;/b&gt;:ACT&lt;br/&gt;&lt;b&gt;Status&lt;/b&gt;:&lt;br/&gt;&lt;b&gt;Street&lt;/b&gt;:377 Canberra Avenue&lt;br/&gt;&lt;b&gt;Suburb&lt;/b&gt;:Fyshwick&lt;br/&gt;</description>
      <guid isPermaLink="false">oxT1t6ljYzDG0NBj4Hr6sw==</guid>
      <pubDate>Thu, 19 Aug 2021 13:41:38 +0000</pubDate>
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
    <lastBuildDate>Wed, 18 Aug 2021 15:44:41 +0000</lastBuildDate>
    <item>
      <title>3 additional exposure sites</title>
      <link>https://www.covid19.act.gov.au/act-status-and-response/act-covid-19-exposure-locations</link>
      <description>&lt;b&gt;Fyshwick:&lt;/b&gt;2&lt;br/&gt;&lt;b&gt;Nicholls:&lt;/b&gt;1&lt;br/&gt;</description>
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
