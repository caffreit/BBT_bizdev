import unittest

from bbt_bizdev.company_research import company_research, discover_company_pages, research_news


RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Acme Health opens new office - Local Health</title>
      <link>https://news.google.com/rss/articles/office</link>
      <description>Acme Health expands operations.</description>
      <source>Local Health</source>
      <pubDate>Thu, 01 Jan 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Acme Health raises $20M Series A - MedTech Dive</title>
      <link>https://news.google.com/rss/articles/funding</link>
      <description>Acme Health raised new investment.</description>
      <source>MedTech Dive</source>
      <pubDate>Thu, 02 Jan 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Acme Health partners with hospital group - Fierce Healthcare</title>
      <link>https://news.google.com/rss/articles/partner</link>
      <description>Partnership announced.</description>
      <source>Fierce Healthcare</source>
      <pubDate>Thu, 03 Jan 2026 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


class CompanyResearchTests(unittest.TestCase):
    def test_research_news_groups_money_signals_and_preserves_recent_order(self):
        def fetch(url):
            return RSS_FIXTURE, None

        result = research_news("Acme Health", fetch=fetch)

        self.assertEqual([item.title for item in result["funding"]], [
            "Acme Health partners with hospital group",
            "Acme Health raises $20M Series A",
        ])
        self.assertEqual(result["news"][0].title, "Acme Health opens new office")

    def test_discover_company_pages_from_homepage_links_and_common_paths(self):
        pages = {
            "https://acme.health": (
                '<html><head><title>Acme</title></head><body>'
                '<a href="/about-us">About us</a>'
                '<a href="/team">Team</a>'
                '<a href="/blog">Blog</a>'
                '<a href="https://other.example/team">Other team</a>'
                "</body></html>"
            ),
            "https://acme.health/news": "<html><head><title>Newsroom</title></head></html>",
            "https://acme.health/press": "<html><head><title>Press</title></head></html>",
        }

        def fetch(url):
            if url in pages:
                return pages[url], None
            return "", "not found"

        result = discover_company_pages("acme.health", fetch=fetch)

        company_urls = [item.url for item in result["companyPages"]]
        people_urls = [item.url for item in result["peopleTeam"]]
        self.assertIn("https://acme.health/blog", company_urls)
        self.assertIn("https://acme.health/news", company_urls)
        self.assertIn("https://acme.health/about-us", people_urls)
        self.assertIn("https://acme.health/team", people_urls)
        self.assertNotIn("https://other.example/team", people_urls)

    def test_company_research_returns_frontend_payload_shape(self):
        def fetch(url):
            if "news.google.com" in url:
                return RSS_FIXTURE, None
            if url == "https://acme.health":
                return '<a href="/team">Team</a><a href="/news">News</a>', None
            return "", "not found"

        result = company_research("Acme Health", "https://acme.health", fetch=fetch)

        self.assertEqual(set(result), {"news", "funding", "companyPages", "peopleTeam"})
        self.assertEqual(result["funding"][0]["source"], "Fierce Healthcare")
        self.assertEqual(result["peopleTeam"][0]["url"], "https://acme.health/team")


if __name__ == "__main__":
    unittest.main()
