import unittest

from bbt_bizdev.canada_clinical_trials import protocol_to_evidence


class CanadaClinicalTrialTests(unittest.TestCase):
    def test_protocol_conversion(self):
        company = {
            "company_id": "c1",
            "company_name": "Acme Bio",
            "legal_name": "Acme Bio Inc.",
            "aliases": [],
        }
        sponsor = {"manufacturer_id": 4, "manufacturer_name": "ACME BIO INC."}
        products = [{"brand_name": "AB-101", "protocol_id": 8}]
        protocol = {
            "protocol_id": 8,
            "protocol_no": "AB1",
            "submission_no": "123",
            "status_id": 1,
            "start_date": "2025-01-01",
            "end_date": None,
            "nol_date": "2024-12-01",
            "protocol_title": "A study",
            "medConditionList": [{"med_condition": "MELANOMA"}],
            "studyPopulationList": [{"study_population": "ADULT"}],
        }
        row = protocol_to_evidence(
            company, sponsor, products, protocol, {1: "ONGOING"}, "2026-07-28"
        )
        self.assertEqual("trial", row["record_type"])
        self.assertEqual("active", row["status"])
        self.assertEqual("AB-101", row["product_name"])
        self.assertEqual("2024-12-01", row["evidence_date"])
        self.assertEqual("exact legal name", row["match_basis"])


if __name__ == "__main__":
    unittest.main()
