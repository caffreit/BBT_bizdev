import unittest

from bbt_bizdev.canada_fda_denovo import parse_results, to_evidence


ROW = """
<table><tr bgcolor="#ffffff">
<td><a href="../cfpmn/denovo.cfm?id=DEN180008">MolecuLight i:X</a></td>
<td>MolecuLight, Inc.</td>
<td><a href="../cfpmn/denovo.cfm?id=DEN180008">DEN180008</a></td>
<td></td><td>07/31/2018</td>
</tr></table>
"""


class CanadaFdaDenovoTests(unittest.TestCase):
    def test_parse_and_convert(self):
        record = parse_results(ROW)[0]
        self.assertEqual("DEN180008", record["de_novo_number"])
        company = {
            "company_id": "c1",
            "company_name": "MolecuLight",
            "legal_name": "",
            "aliases": [],
        }
        row = to_evidence(company, record, "2026-07-28", "MolecuLight")
        self.assertEqual("De Novo", row["record_type"])
        self.assertEqual("2018-07-31", row["evidence_date"])
        self.assertEqual("cleared", row["status"])


if __name__ == "__main__":
    unittest.main()
