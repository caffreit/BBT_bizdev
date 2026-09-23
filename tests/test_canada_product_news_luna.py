from __future__ import annotations

import unittest

from bbt_bizdev.canada_hiring import FetchResult
from bbt_bizdev.canada_product_news_luna import (
    _usage_cost, build_batches, deduplicate_events, prepare_candidates, validate_decision,
)


def candidate(identifier="1"):
    return {
        "company_id": "c1", "company_name": "Acme Medical", "event_date": "2026-01-02",
        "event_type": "product launch", "title": f"Acme Medical launches Device {identifier}",
        "discovery_url": f"https://news.google/a{identifier}", "freshness": "recent_24_months",
    }


class CanadaProductNewsLunaTests(unittest.TestCase):
    def test_preparation_rejects_historical_and_exact_duplicates(self):
        recent = candidate()
        historical = {**candidate("2"), "freshness": "historical"}
        prepared, rejected = prepare_candidates([recent, recent, historical])
        self.assertEqual(len(prepared), 1)
        self.assertEqual(len(rejected), 2)

    def test_batches_stay_with_company_and_respect_size(self):
        rows, _ = prepare_candidates([candidate(str(index)) for index in range(21)])
        batches = build_batches(rows, batch_size=20)
        self.assertEqual([len(batch) for batch in batches], [20, 1])
        self.assertTrue(all(len({row["company_id"] for row in batch}) == 1 for batch in batches))

    def test_local_gate_accepts_only_fetched_identity_supported_primary_source(self):
        row, _ = prepare_candidates([candidate()])
        company = {"company_id": "c1", "company_name": "Acme Medical", "website": "https://acme.example"}
        decision = {
            "decision": "verified", "confidence": "high", "identity_confidence": "high",
            "event_type": "product launch", "event_date": "2026-01-02",
            "canonical_title": "Acme Medical launches Device", "summary": "Launch",
            "product_or_program": "Device", "primary_url": "https://acme.example/news/launch",
            "primary_source_type": "company", "materiality": "high", "rejection_reason": "none", "rationale": "",
        }
        result = validate_decision(
            company, {}, row[0], decision, "2026-08-05",
            lambda url: FetchResult(url, "Acme Medical launches Device", 200),
        )
        self.assertEqual(result["verification_status"], "accepted")

    def test_local_gate_rejects_company_homepage_as_event_evidence(self):
        row, _ = prepare_candidates([candidate()])
        company = {"company_id": "c1", "company_name": "Acme Medical", "website": "https://acme.example"}
        decision = {
            "decision": "verified", "confidence": "high", "identity_confidence": "high",
            "event_type": "product launch", "event_date": "2026-01-02",
            "canonical_title": "Launch", "summary": "Launch", "product_or_program": "Device",
            "primary_url": "https://acme.example/", "primary_source_type": "company",
            "materiality": "high", "rejection_reason": "none", "rationale": "",
        }
        result = validate_decision(
            company, {}, row[0], decision, "2026-08-05",
            lambda url: FetchResult(url, "Acme Medical launches Device", 200),
        )
        self.assertEqual(result["verification_status"], "needs_review")

    def test_deduplication_merges_supporting_candidate_ids(self):
        base = {"evidence_id": "e1", "company_id": "c1", "event_type": "funding", "event_date": "2026-01-01", "product_or_program": "Series A", "title": "Round", "candidate_ids": ["a"]}
        rows = deduplicate_events([base, {**base, "evidence_id": "e2", "candidate_ids": ["b"]}])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["candidate_ids"], ["a", "b"])

    def test_usage_cost_prefers_reported_cost_and_has_token_fallback(self):
        self.assertEqual(_usage_cost({"cost": 0.25, "prompt_tokens": 1}), 0.25)
        self.assertAlmostEqual(_usage_cost({"prompt_tokens": 1_000_000, "completion_tokens": 100_000}), 1.6)


if __name__ == "__main__":
    unittest.main()
