from __future__ import annotations

import unittest

from bbt_bizdev.canada_scoring import normalize_employee_band, score_company


def evidence(evidence_id: str, **values):
    return {
        "status": "accepted",
        "evidence_id": evidence_id,
        "evidence_url": f"https://example.test/{evidence_id}",
        **values,
    }


def complete_tracks():
    return {
        name: {"status": "complete_matches"}
        for name in (
            "identity_canada", "firmographics", "hiring", "funding",
            "regulatory", "product_news",
        )
    }


class CanadaScoringV2Tests(unittest.TestCase):
    def test_unknown_data_receives_no_positive_stage_or_canada_points(self):
        result = score_company({
            "company_id": "unknown",
            "regulated_deliverable": {"status": "unknown", "evidence_ids": []},
            "employee_band": {"value": "unknown", "evidence_ids": []},
            "canada_relationship": {"value": "unknown", "evidence_ids": []},
            "completeness": {},
        }, as_of="2026-08-04")
        self.assertEqual(result["fit"], 0)
        self.assertEqual(result["ability_to_buy"], 0)
        self.assertEqual(result["canada_relevance"], 0)
        self.assertEqual(result["priority_score"], 0)
        self.assertIn("employee_band", result["missing_data_flags"])
        self.assertFalse(result["comparable_coverage"])

    def test_category_only_cannot_receive_maximum_fit(self):
        result = score_company({
            "company_id": "category-only",
            "regulated_deliverable": {"status": "category_only", "evidence_ids": ["cat-1"]},
            "employee_band": {"value": "unknown", "evidence_ids": []},
            "canada_relationship": {"value": "unknown", "evidence_ids": []},
            "completeness": complete_tracks(),
        }, as_of="2026-08-04")
        self.assertEqual(result["fit"], 5)
        self.assertLess(result["fit"], 35)

    def test_full_fit_requires_confirmed_service_need_evidence(self):
        needs = [
            {"need": value, "status": "confirmed", "evidence_ids": [f"need-{index}"]}
            for index, value in enumerate((
                "product_development", "design_controls", "verification_validation",
                "quality_systems", "regulatory",
            ))
        ]
        result = score_company({
            "company_id": "full-fit",
            "regulated_deliverable": {"status": "confirmed", "evidence_ids": ["product-1"]},
            "service_needs": needs,
            "employee_band": {"value": "20-50", "evidence_ids": ["size-1"]},
            "canada_relationship": {"value": "hq", "evidence_ids": ["hq-1"]},
            "completeness": complete_tracks(),
        }, as_of="2026-08-04")
        self.assertEqual(result["fit"], 35)
        self.assertEqual(result["canada_relevance"], 10)
        self.assertEqual(result["evidence_confidence"], 100)
        self.assertTrue(result["comparable_coverage"])

    def test_unverified_or_undated_events_do_not_score(self):
        result = score_company({
            "company_id": "bad-evidence",
            "regulated_deliverable": {"status": "unknown", "evidence_ids": []},
            "employee_band": {"value": "unknown", "evidence_ids": []},
            "canada_relationship": {"value": "unknown", "evidence_ids": []},
            "open_roles": [{
                "status": "open_verified", "evidence_id": "", "evidence_url": "https://example.test/job"
            }],
            "milestones": [evidence("milestone-1", status="accepted", event_type="product_launch")],
            "funding_events": [evidence("fund-1", status="manual_review", event_date="2026-07-01", amount_cad=5000000)],
            "completeness": complete_tracks(),
        }, as_of="2026-08-04")
        self.assertEqual(result["timing"], 0)
        self.assertEqual(result["ability_to_buy"], 0)

    def test_recent_verified_signals_score_deterministically(self):
        company = {
            "company_id": "scored",
            "regulated_deliverable": {"status": "confirmed", "evidence_ids": ["product-1"]},
            "service_needs": [{"need": "regulatory", "status": "confirmed", "evidence_ids": ["need-1"]}],
            "employee_band": {"value": "51-200", "evidence_ids": ["size-1"]},
            "canada_relationship": {"value": "substantial_product_development", "evidence_ids": ["ca-1"]},
            "open_roles": [evidence("job-1", status="open_verified", seniority="director")],
            "milestones": [evidence("milestone-1", event_type="regulatory_submission", event_date="2026-05-01")],
            "triggers": [evidence("trigger-1", event_type="expansion", event_date="2026-06-01")],
            "funding_events": [evidence("fund-1", funding_type="equity", event_date="2026-01-01", amount_cad=5000000)],
            "institutional_backing": [evidence("backing-1")],
            "completeness": complete_tracks(),
        }
        first = score_company(company, as_of="2026-08-04")
        second = score_company(company, as_of="2026-08-04")
        self.assertEqual(first, second)
        self.assertEqual(first["timing"], 24)
        self.assertEqual(first["ability_to_buy"], 25)
        self.assertEqual(first["priority_score"], 79)

    def test_explicit_exclusion_sets_priority_to_zero(self):
        result = score_company({
            "company_id": "inactive",
            "eligibility": "excluded",
            "exclusion_reasons": ["inactive"],
            "regulated_deliverable": {"status": "confirmed", "evidence_ids": ["product-1"]},
            "employee_band": {"value": "20-50", "evidence_ids": ["size-1"]},
            "canada_relationship": {"value": "hq", "evidence_ids": ["hq-1"]},
            "completeness": complete_tracks(),
        }, as_of="2026-08-04")
        self.assertFalse(result["eligible"])
        self.assertEqual(result["priority_score"], 0)

    def test_employee_band_normalization_is_bounded(self):
        self.assertEqual(normalize_employee_band("11–50"), "20-50")
        self.assertEqual(normalize_employee_band("201-500"), "201-500")
        self.assertEqual(normalize_employee_band("1,001–5,000"), "501+")
        self.assertEqual(normalize_employee_band("not stated"), "unknown")


if __name__ == "__main__":
    unittest.main()
