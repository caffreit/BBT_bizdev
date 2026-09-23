from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bbt_bizdev.canada_product_news import (
    classify_event,
    google_news_urls,
    infer_product_category,
    parse_google_news,
    parse_page,
    rank_company_links,
    run_product_news_enrichment,
)


COMPANY = {
    "company_id": "ca-company-test",
    "company_name": "Acme Medical",
    "legal_name": "Acme Medical Inc.",
    "aliases": [],
    "website": "https://acme.example",
    "product_category": "medical device",
    "product_summary": "",
}


class CanadaProductNewsTests(unittest.TestCase):
    def test_page_discovery_prefers_product_clinical_and_news(self) -> None:
        page = parse_page(
            """
            <a href="/privacy">Privacy</a><a href="/products/device">Our Device</a>
            <a href="/clinical-evidence">Clinical Evidence</a><a href="/news">Newsroom</a>
            """,
            "https://acme.example",
        )
        selected = rank_company_links(page["links"], COMPANY["website"])
        self.assertEqual([row["page_type"] for row in selected], ["product", "clinical", "newsroom"])

    def test_product_and_event_classification(self) -> None:
        self.assertEqual(infer_product_category("AI diagnostic assay for cancer screening"), "diagnostics")
        self.assertEqual(classify_event("Acme launches its new clinical device"), "product launch")

    def test_rss_results_are_review_candidates_not_accepted_evidence(self) -> None:
        raw = """
        <rss><channel><item>
          <title>Acme Medical launches diagnostic platform</title>
          <description>Acme Medical introduced a new clinical screening product.</description>
          <link>https://news.google.com/articles/abc</link>
          <source>Example News</source><pubDate>Tue, 28 Jul 2026 12:00:00 GMT</pubDate>
        </item><item><title>Other company launches</title><link>https://example.test/other</link></item>
        </channel></rss>
        """
        rows = parse_google_news(COMPANY, raw, "2026-07-30")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["review_status"], "manual_review")
        self.assertIn("primary evidence", rows[0]["notes"])

    def test_news_queries_cover_aliases_and_distinct_event_families(self) -> None:
        urls = google_news_urls({
            **COMPANY,
            "aliases": ["Acme Diagnostics"],
        })
        self.assertEqual(len(urls), 8)
        decoded = " ".join(urls)
        self.assertIn("funding", decoded)
        self.assertIn("manufacturing", decoded)
        self.assertIn("Acme%20Diagnostics", decoded)

    def test_runner_writes_auditable_outputs(self) -> None:
        homepage = """
        <html><head><meta name="description" content="Acme makes a connected medical device."></head>
        <body><a href="/product">Product</a><a href="/news">News</a></body></html>
        """
        product = "<html><head><title>Acme Device</title></head><body>Connected medical device for monitoring patients.</body></html>"
        news = "<html><head><title>Acme launches Device - July 28, 2026</title></head><body>Acme launched its clinical device.</body></html>"

        def fetcher(url: str, timeout: int):
            if url.endswith("/product"):
                return product, url, ""
            if url.endswith("/news"):
                return news, url + "/acme-launches-device", ""
            return homepage, url, ""

        def news_fetcher(company, timeout):
            return [], "https://news.example/rss", ""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies = root / "companies.json"
            companies.write_text(json.dumps({"companies": [COMPANY]}), encoding="utf-8")
            summary = run_product_news_enrichment(
                companies,
                root / "out",
                "2026-07-30",
                limit=1,
                fetcher=fetcher,
                news_fetcher=news_fetcher,
                delay=0,
            )
            self.assertEqual(summary["product_profiles"], 1)
            self.assertEqual(summary["accepted_official_events"], 1)
            events = json.loads((root / "out" / "product_news_events.json").read_text())["events"]
            self.assertEqual(events[0]["event_date"], "2026-07-28")
            completeness_path = root / "out" / "product_news_completeness.json"
            self.assertTrue(completeness_path.exists())
            completeness = json.loads(completeness_path.read_text())["companies"][0]
            self.assertEqual(completeness["news"]["status"], "partial")

    def test_homepage_only_empty_product_check_is_partial(self) -> None:
        def fetcher(url: str, timeout: int):
            return "<html><body>Welcome to Acme Medical</body></html>", url, ""

        def news_fetcher(company, timeout):
            return [], "https://news.example/rss", ""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies = root / "companies.json"
            companies.write_text(json.dumps({"companies": [COMPANY]}), encoding="utf-8")
            run_product_news_enrichment(
                companies, root / "out", "2026-07-30", limit=1,
                fetcher=fetcher, news_fetcher=news_fetcher, delay=0,
            )
            row = json.loads(
                (root / "out" / "product_news_completeness.json").read_text()
            )["companies"][0]
            self.assertEqual(row["product_development"]["status"], "partial")
            self.assertEqual(row["news"]["status"], "partial")

    def test_company_without_website_still_gets_news_attempt(self) -> None:
        company = {**COMPANY, "website": ""}
        calls = []

        def news_fetcher(row, timeout):
            calls.append(row["company_id"])
            return [], "https://news.example/rss", ""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companies = root / "companies.json"
            companies.write_text(json.dumps({"companies": [company]}), encoding="utf-8")
            summary = run_product_news_enrichment(
                companies, root / "out", "2026-07-30",
                fetcher=lambda *_: self.fail("website fetch should not run"),
                news_fetcher=news_fetcher, delay=0,
            )
            row = json.loads(
                (root / "out" / "product_news_completeness.json").read_text()
            )["companies"][0]
            self.assertEqual(calls, [company["company_id"]])
            self.assertEqual(row["product_development"]["status"], "no_source")
            self.assertEqual(row["news"]["status"], "partial")
            self.assertTrue(summary["comparable_coverage_run"])


if __name__ == "__main__":
    unittest.main()
