import unittest

from bbt_bizdev.canada_fda import (
    applicant_query_url,
    fetch_all,
    fda_record_to_evidence,
    lucene_phrase,
    result_records,
    safe_discovery_name,
)


class CanadaFdaTests(unittest.TestCase):
    def test_query_and_response(self):
        url = applicant_query_url("https://api.example/data.json", "Acme Medical")
        self.assertIn("applicant%3A%22Acme+Medical%22", url)
        self.assertEqual([{"k_number": "K1"}], result_records({"results": [{"k_number": "K1"}]}))

    def test_fetch_all_paginates(self):
        def getter(url):
            if "skip=0" in url:
                return {
                    "meta": {"results": {"total": 3}},
                    "results": [{"id": 1}, {"id": 2}],
                }
            return {
                "meta": {"results": {"total": 3}},
                "results": [{"id": 3}],
            }

        rows, audit = fetch_all("https://api.example/data", "country:CA", getter, limit=2)
        self.assertEqual([1, 2, 3], [row["id"] for row in rows])
        self.assertEqual(2, len(audit))

    def test_lucene_phrase_escapes_reserved_characters(self):
        self.assertEqual(r"20\/20 \(Canada\)", lucene_phrase("20/20 (Canada)"))
        self.assertEqual("Telemedic Inc.", safe_discovery_name("Télémédic Inc."))
        self.assertEqual("Chapeau", safe_discovery_name("Chapeau!"))

    def test_510k_conversion(self):
        company = {
            "company_id": "c1",
            "company_name": "Acme Medical",
            "legal_name": "Acme Medical Inc.",
            "aliases": [],
        }
        record = {
            "k_number": "K250001",
            "applicant": "ACME MEDICAL INC.",
            "device_name": "Acme Scanner",
            "decision_date": "20250102",
            "decision_code": "SESE",
        }
        row = fda_record_to_evidence(
            company, record, "510(k)", "2026-07-28", "Acme Medical Inc."
        )
        self.assertEqual("510(k)", row["record_type"])
        self.assertEqual("cleared", row["status"])
        self.assertEqual("exact legal name", row["match_basis"])

    def test_pma_conversion(self):
        company = {
            "company_id": "c1",
            "company_name": "Acme Medical",
            "legal_name": "",
            "aliases": [],
        }
        record = {
            "pma_number": "P250001",
            "applicant": "ACME MEDICAL",
            "trade_name": "Acme Implant",
            "decision_date": "20250203",
        }
        row = fda_record_to_evidence(
            company, record, "PMA", "2026-07-28", "Acme Medical"
        )
        self.assertEqual("approved", row["status"])
        self.assertEqual("Acme Implant", row["product_name"])


if __name__ == "__main__":
    unittest.main()
