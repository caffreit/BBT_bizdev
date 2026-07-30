import unittest

from bbt_bizdev.canada_fda_registration import record_key, to_evidence


class CanadaFdaRegistrationTests(unittest.TestCase):
    def test_listing_is_not_approval(self):
        company = {
            "company_id": "c1",
            "company_name": "Synaptive Medical",
            "legal_name": "",
            "aliases": [],
        }
        record = {
            "proprietary_name": ["ImageDrive Clinical"],
            "establishment_type": ["Manufacture Medical Device"],
            "registration": {
                "registration_number": "3012075008",
                "fei_number": "3012075008",
                "name": "Synaptive Medical Inc",
                "reg_expiry_date_year": "2026",
            },
            "k_number": "K153284",
            "pma_number": "",
            "products": [{
                "product_code": "LLZ",
                "openfda": {"device_class": "2"},
            }],
        }
        self.assertIn("3012075008", record_key(record))
        row = to_evidence(company, record, "2026-07-28", "Synaptive Medical")
        self.assertEqual("listing", row["record_type"])
        self.assertEqual("registered", row["status"])
        self.assertIn("not itself", row["interpretation_note"])
        self.assertEqual("Class 2", row["device_class"])


if __name__ == "__main__":
    unittest.main()
