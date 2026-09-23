import tempfile
import unittest
from pathlib import Path

from bbt_bizdev.canada_funding import (
    extract_structured_event, normalize_external_funding_event,
    provenance_to_backing,
)


class CanadaFundingTests(unittest.TestCase):
    def test_portfolio_provenance_becomes_backing_not_event(self):
        rows = [{
            "provenance_id": "p1",
            "company_id": "c1",
            "source_name": "Lumira Ventures portfolio",
            "source_type": "VC portfolio",
            "evidence_url": "https://example.com/portfolio",
            "snapshot_date": "2026-07-23",
            "captured_at": "2026-07-27",
            "source_company_name": "Acme",
        }]
        result = provenance_to_backing(rows)
        self.assertEqual(1, len(result))
        self.assertEqual("institutional_backing", result[0]["claim_type"])
        self.assertEqual("investor_portfolio", result[0]["backing_type"])

    def test_prose_and_portfolio_date_do_not_create_event(self):
        self.assertIsNone(extract_structured_event({
            "date": "2026-01-01",
            "description": "Raised $5 million",
        }))
        self.assertIsNone(extract_structured_event({
            "amount": "$5 million",
            "description": "Portfolio company",
        }))

    def test_explicit_structured_event_is_extracted(self):
        result = extract_structured_event({
            "event_date": "2026-01-02",
            "funding_type": "grant",
            "amount_original": "$2 million",
            "currency": "CAD",
            "evidence_url": "https://example.com/award",
        })
        self.assertEqual("grant", result["funding_type"])
        self.assertEqual("$2 million", result["amount_original"])

    def test_verified_funding_news_is_converted_but_other_news_is_rejected(self):
        result = normalize_external_funding_event({
            "evidence_id": "news-1",
            "company_id": "c1",
            "event_type": "funding",
            "event_date": "2026-02-10",
            "title": "Acme raises C$10 million Series A financing",
            "summary": "The financing supports clinical validation.",
            "evidence_url": "https://example.com/acme-series-a",
            "source_type": "company",
            "confidence": "high",
        })
        self.assertIsNotNone(result)
        self.assertEqual(result["funding_type"], "equity")
        self.assertEqual(result["stage"], "Series A")
        self.assertEqual(result["amount_cad"], 10_000_000)
        self.assertEqual(result["source_evidence_id"], "news-1")
        self.assertIsNone(normalize_external_funding_event({
            "company_id": "c1", "event_type": "partnership",
            "event_date": "2026-02-10", "evidence_url": "https://example.com/partner",
        }))


if __name__ == "__main__":
    unittest.main()
