import unittest

from build_canada_scoring_audit_sample import select_sample


class CanadaScoringAuditSampleTests(unittest.TestCase):
    def test_sample_is_stratified_unique_and_deterministic(self):
        records = [
            {
                "rank": rank,
                "company_id": f"c{rank}",
                "company_name": f"Company {rank}",
                "eligible": True,
                "priority_score": 100 - rank,
            }
            for rank in range(1, 151)
        ]
        first = select_sample(records, seed=7)
        second = select_sample(records, seed=7)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 100)
        self.assertEqual(len({row["company_id"] for row in first}), 100)
        self.assertEqual(sum(row["audit_stratum"] == "top_50" for row in first), 50)
        self.assertEqual(sum(row["audit_stratum"] == "cutoff_band" for row in first), 25)
        self.assertEqual(sum(row["audit_stratum"] == "random_remainder" for row in first), 25)


if __name__ == "__main__":
    unittest.main()
