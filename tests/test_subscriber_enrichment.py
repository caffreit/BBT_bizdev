import unittest
from unittest.mock import patch

from bbt_bizdev.subscriber_enrichment import (
    CompanySeed,
    build_company_seeds,
    classify_website_status,
    email_domain,
    fetch_page,
    parse_google_news,
    rules_classify,
    select_internal_pages,
    select_pilot,
    title_bucket,
)


class SubscriberEnrichmentTests(unittest.TestCase):
    def test_email_domain_rejects_malformed_addresses(self):
        self.assertEqual(email_domain("person@example.com"), "example.com")
        self.assertEqual(email_domain("broken"), "")
        self.assertEqual(email_domain("a@@example.com"), "")

    def test_same_domain_majority_resolves_missing_company(self):
        contacts = [
            {"Email Domain": "acme.com", "Company": "Acme Ltd", "Original Company Missing": "No"},
            {"Email Domain": "acme.com", "Company": "Acme", "Original Company Missing": "No"},
            {"Email Domain": "acme.com", "Company": "", "Original Company Missing": "Yes"},
        ]
        seeds, mapping = build_company_seeds(contacts)
        self.assertEqual(len(seeds), 1)
        self.assertIn(mapping["acme.com"].canonical_company, {"Acme", "Acme Ltd"})
        self.assertEqual(mapping["acme.com"].missing_company_count, 1)

    def test_personal_domain_is_not_inferred(self):
        contacts = [{"Email Domain": "gmail.com", "Company": "", "Original Company Missing": "Yes"}]
        _, mapping = build_company_seeds(contacts)
        self.assertEqual(mapping["gmail.com"].canonical_company, "Unknown")

    def test_title_bucket_prefers_quality_over_engineering(self):
        function, seniority, role = title_bucket("Director of Quality Engineering")
        self.assertEqual(function, "QA/regulatory")
        self.assertEqual(seniority, "Director/VP")
        self.assertIn("Technical", role)

    def test_rules_are_conservative_and_evidence_based(self):
        result = rules_classify("We build an AI-enabled software as a medical device and are ISO 13485 certified.", "acme.com")
        self.assertEqual(result["product_profile"], "AI-enabled health")
        self.assertIn("IEC 62304", result["services"])
        self.assertIn("ISO 13485", result["regulatory_signals"])
        self.assertEqual(result["employee_band"], "Unknown")

    def test_sample_is_stable_and_unique(self):
        seeds = [CompanySeed(f"c-{i}", f"d{i}.com", f"Company {i}", "Existing", .95, i % 5 + 1, i % 3, "") for i in range(30)]
        sample = select_pilot(seeds, 20)
        self.assertEqual(len(sample), 20)
        self.assertEqual(len({item.domain for item in sample}), 20)

    def test_internal_page_selection_prefers_distinct_high_value_categories(self):
        links = [
            ("https://acme.example/privacy", "Privacy"),
            ("https://acme.example/about", "About us"),
            ("https://acme.example/products/device", "Our products"),
            ("https://acme.example/quality", "Quality and regulatory"),
            ("https://acme.example/products/software", "Software products"),
        ]
        selected = select_internal_pages(links)
        self.assertEqual([item["category"] for item in selected], ["Regulatory/quality", "Product/technology", "About/company"])
        self.assertNotIn("https://acme.example/privacy", [item["url"] for item in selected])

    def test_fetch_page_encodes_spaces_in_internal_links(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return None
            def geturl(self): return "https://example.org/"
            def read(self, *_): return b'<a href="/About Sussex Partnership NHS Trust">About</a>'

        with patch("bbt_bizdev.subscriber_enrichment.urlopen", return_value=Response()):
            _, links, _ = fetch_page("https://example.org")
        self.assertEqual(links[0][0], "https://example.org/About%20Sussex%20Partnership%20NHS%20Trust")

    def test_fetch_page_rejects_relative_url_without_raising(self):
        self.assertEqual(fetch_page("/About Sussex Partnership NHS Trust"), ("", [], ""))

    def test_fetch_page_preserves_existing_percent_encoding(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return None
            def geturl(self): return "https://example.org/"
            def read(self, *_): return b'<a href="/already%20encoded">About</a>'

        with patch("bbt_bizdev.subscriber_enrichment.urlopen", return_value=Response()):
            _, links, _ = fetch_page("https://example.org")
        self.assertEqual(links[0][0], "https://example.org/already%20encoded")

    def test_news_selection_requires_exact_company_and_ranks_relevant_article(self):
        rss = """<rss><channel>
          <item><title>Acme Medical receives FDA clearance</title><link>https://news.example/fda</link><description>Acme Medical launches its device.</description><source>Med News</source><pubDate>Mon, 20 Jul 2026 00:00:00 GMT</pubDate></item>
          <item><title>Acme Medical appoints office manager</title><link>https://news.example/people</link><description>Acme Medical update.</description><source>Local News</source></item>
          <item><title>Other Medical receives FDA clearance</title><link>https://news.example/other</link><description>Unrelated company.</description><source>Other News</source></item>
        </channel></rss>"""
        selected = parse_google_news("Acme Medical", rss)
        self.assertEqual(selected[0]["url"], "https://news.example/fda")
        self.assertNotIn("https://news.example/other", [item["url"] for item in selected])

    def test_website_status_separates_unavailable_and_external_redirects(self):
        self.assertEqual(classify_website_status("acme.com", "", ""), ("Unavailable", ""))
        self.assertEqual(classify_website_status("acme.com", "content", "https://www.acme.com/about"), ("Available", ""))
        self.assertEqual(classify_website_status("acme.com", "content", "https://parent.example/acme"), ("External redirect", "https://parent.example/acme"))


if __name__ == "__main__":
    unittest.main()
