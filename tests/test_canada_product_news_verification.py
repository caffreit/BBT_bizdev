from __future__ import annotations

import unittest

from bbt_bizdev.canada_product_news_verification import verify_recent_candidates


class CanadaProductNewsVerificationTests(unittest.TestCase):
    def test_deduplicates_verified_event_and_rejects_name_collision(self) -> None:
        candidates = [
            {
                "company_id": "fluid-id", "company_name": "Fluid Biomed",
                "title": "Fluid Biomed raises $27M for bioabsorbable stent",
                "freshness": "recent_24_months",
            },
            {
                "company_id": "fluid-id", "company_name": "Fluid Biomed",
                "title": "Fluid Biomed closes $27-million Series A",
                "freshness": "recent_24_months",
            },
            {
                "company_id": "swift-id", "company_name": "Swift Medical",
                "title": "Ambulance service promises swift medical response",
                "freshness": "recent_24_months",
            },
        ]
        result = verify_recent_candidates(candidates, "2026-07-30")
        events = [row for row in result["events"] if row["company_id"] == "fluid-id"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["product_or_program"], "ReSolv")
        self.assertEqual(
            [row["verification_status"] for row in result["decisions"]],
            ["verified_supporting_candidate", "verified_supporting_candidate", "rejected_identity_mismatch"],
        )

    def test_historical_candidates_are_out_of_scope(self) -> None:
        result = verify_recent_candidates([
            {
                "company_id": "x", "company_name": "Fluid Biomed",
                "title": "Fluid Biomed raises $27M", "freshness": "historical",
            }
        ], "2026-07-30")
        self.assertEqual(result["decisions"], [])


if __name__ == "__main__":
    unittest.main()
