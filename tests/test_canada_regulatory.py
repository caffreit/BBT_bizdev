import json
import tempfile
import unittest
from pathlib import Path

from bbt_bizdev.canada_regulatory import (
    api_records,
    company_query_url,
    licence_to_evidence,
    run_mdall_enrichment,
)


class CanadaRegulatoryTests(unittest.TestCase):
    def test_api_records_normalizes_shapes(self):
        self.assertEqual([{"company_id": 1}], api_records({"company_id": 1}))
        self.assertEqual([{"company_id": 1}], api_records({"result": [{"company_id": 1}]}))
        self.assertEqual([], api_records(None))

    def test_licence_to_evidence(self):
        company = {
            "company_id": "c1", "company_name": "Acme Medical",
            "legal_name": "Acme Medical Inc.", "aliases": [],
        }
        manufacturer = {"company_id": 42, "company_name": "ACME MEDICAL INC.", "company_status": "A"}
        licence = {
            "original_licence_no": 123,
            "licence_status": "I",
            "appl_risk_class": 2,
            "licence_name": "ACME SCANNER",
            "first_licence_status_dt": "2025-01-02",
            "last_refresh_dt": "2026-07-27",
            "end_date": None,
            "licence_type_desc": "Device Family",
        }
        row = licence_to_evidence(
            company, manufacturer, licence, "active", "2026-07-28", "Acme Medical Inc."
        )
        self.assertEqual("123", row["record_id"])
        self.assertEqual("Class 2", row["device_class"])
        self.assertEqual("active", row["status"])
        self.assertEqual("exact legal name", row["match_basis"])

    def test_run_accepts_exact_and_quarantines_substring_match(self):
        companies = {
            "companies": [{
                "company_id": "c1",
                "company_name": "Acme Medical",
                "legal_name": "",
                "aliases": [],
                "product_category": "medical device",
            }]
        }

        def fake_getter(url):
            if "/company/" in url:
                self.assertIn("company_name=Acme+Medical", company_query_url("Acme Medical"))
                return [
                    {"company_id": 10, "company_name": "ACME MEDICAL", "company_status": "A"},
                    {"company_id": 11, "company_name": "ACME MEDICAL DEVICES", "company_status": "A"},
                ]
            if "company_id=10" in url and "state=active" in url:
                return [{
                    "original_licence_no": 99,
                    "licence_status": "I",
                    "appl_risk_class": 3,
                    "licence_name": "ACME DEVICE",
                    "first_licence_status_dt": "2024-03-01",
                    "end_date": None,
                }]
            return []

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "companies.json"
            source.write_text(json.dumps(companies), encoding="utf-8")
            summary = run_mdall_enrichment(
                source, root / "out", "2026-07-28", workers=1, getter=fake_getter
            )
            self.assertEqual(1, summary["licence_records"])
            self.assertEqual(1, summary["manual_review_candidates"])
            review = json.loads(
                (root / "out" / "mdall_manual_review.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                "substring_or_non_exact_manufacturer_name",
                review["records"][0]["review_reason"],
            )


if __name__ == "__main__":
    unittest.main()
