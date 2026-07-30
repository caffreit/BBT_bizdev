import unittest

from bbt_bizdev.canada_mdel import mdel_to_evidence, parse_mdel_detail


DETAIL = """
<main>
Licence number (maximum of 6 numbers): 6714 New search
Company Id (maximum of 6 numbers): 141128
Company name : Swift Medical Inc.
Address: 1 King Street West, Toronto, Ontario, Canada, M5H 1A1
Senior official name : JASPREET NIJJAR
Activities for device classes:
Device classes Distribute Import Manufacture Devices for Distribution
Class I No No Yes Class II No No Class III No No Class IV No No
New search
</main>
"""


class CanadaMdelTests(unittest.TestCase):
    def test_parse_detail(self):
        row = parse_mdel_detail(DETAIL)
        self.assertEqual("6714", row["licence_number"])
        self.assertEqual("Swift Medical Inc.", row["company_name"])
        self.assertIn("Class I", row["authorized_activities"])

    def test_mdel_is_not_product_approval(self):
        company = {
            "company_id": "c1",
            "company_name": "Swift Medical",
            "legal_name": "",
            "aliases": ["Swift Medical Inc."],
        }
        row = mdel_to_evidence(
            company, parse_mdel_detail(DETAIL), "2026-07-28", "Swift Medical Inc."
        )
        self.assertEqual("MDEL", row["record_type"])
        self.assertEqual("", row["product_name"])
        self.assertIn("not approval", row["interpretation_note"])
        self.assertEqual("exact canonical name", row["match_basis"])


if __name__ == "__main__":
    unittest.main()
