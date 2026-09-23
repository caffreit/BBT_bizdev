import unittest

from merge_canada_hiring_runs import choose_records


class MergeCanadaHiringRunsTests(unittest.TestCase):
    def test_selects_strongest_status_and_latest_on_tie(self):
        old = [{"company_id": "a", "company_name": "A", "status": "partial", "notes": "old"}]
        new = [{"company_id": "a", "company_name": "A", "status": "complete_zero", "notes": "new"}]
        self.assertEqual(choose_records([old, new])[0]["status"], "complete_zero")
        tied = [{"company_id": "a", "company_name": "A", "status": "partial", "notes": "latest"}]
        self.assertEqual(choose_records([old, tied])[0]["notes"], "latest")


if __name__ == "__main__":
    unittest.main()
