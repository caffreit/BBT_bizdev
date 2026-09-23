from __future__ import annotations

import unittest

from bbt_bizdev.canada_scoring_integration import combine_product_news_status, score_universe


class CanadaScoringIntegrationTests(unittest.TestCase):
    def test_product_news_completeness_requires_both_tracks(self):
        self.assertEqual(
            combine_product_news_status(
                {"status": "complete_matches"}, {"status": "not_run"}
            ),
            "not_run",
        )
        self.assertEqual(
            combine_product_news_status(
                {"status": "complete_zero"}, {"status": "complete_zero"}
            ),
            "complete_zero",
        )

    def test_review_queue_includes_all_cutoff_ties(self):
        base = {
            "regulated_deliverable": {"status": "unknown", "evidence_ids": []},
            "employee_band": {"value": "unknown", "evidence_ids": []},
            "canada_relationship": {"value": "unknown", "evidence_ids": []},
            "completeness": {},
        }
        inputs = [
            {**base, "company_id": str(index), "company_name": f"Company {index:02d}"}
            for index in range(55)
        ]
        result = score_universe(inputs, "2026-08-04")
        self.assertEqual(result["summary"]["top_50_cutoff_score"], 0)
        self.assertEqual(result["summary"]["review_queue_including_ties"], 55)
        self.assertIn("fit", result["leave_one_component_out"])
        self.assertFalse(result["summary"]["release_ready"])

    def test_funding_event_id_is_normalized_as_scoring_evidence_id(self):
        from bbt_bizdev.canada_scoring_integration import build_scoring_inputs

        company = {"company_id": "c1", "company_name": "Acme", "completeness": {}}
        inputs = build_scoring_inputs(
            [company], provenance=[], hiring=[], hiring_companies=[],
            funding_events=[{
                "company_id": "c1", "funding_event_id": "fund-1",
                "event_date": "2026-01-01", "funding_type": "equity",
                "evidence_url": "https://example.com/funding",
            }],
            backing=[], funding_companies=[], regulatory=[], regulatory_companies=[],
            product_profiles=[], product_events=[], product_completeness=[],
        )
        self.assertEqual(inputs[0]["funding_events"][0]["evidence_id"], "fund-1")

    def test_canadian_geography_upgrades_program_only_to_other_operation_not_hq(self):
        from bbt_bizdev.canada_scoring_integration import build_scoring_inputs

        company = {
            "company_id": "c1", "company_name": "Acme",
            "canada_relationship": "program location only", "completeness": {},
        }
        inputs = build_scoring_inputs(
            [company], provenance=[{"company_id": "c1", "provenance_id": "p1", "geography": "Ontario"}],
            hiring=[], hiring_companies=[], funding_events=[], backing=[], funding_companies=[],
            regulatory=[], regulatory_companies=[], product_profiles=[], product_events=[], product_completeness=[],
        )
        self.assertEqual(inputs[0]["canada_relationship"]["value"], "other_operation")


if __name__ == "__main__":
    unittest.main()
