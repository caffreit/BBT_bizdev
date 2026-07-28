import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bbt_bizdev.canada_hiring import FetchResult
from bbt_bizdev.canada_website_llm import (
    build_prompt, run_luna_resolution, validate_luna_decision,
)


def company():
    return {
        "company_id": "ca-acme", "company_name": "Acme Medical",
        "aliases": [], "website": "", "domain": "", "province": "Ontario",
        "product_category": "Medical device", "product_summary": "Acme makes cardiac devices.",
        "canada_relationship": "HQ", "identity_keys": [], "completeness": {},
    }


def verified():
    return {
        "decision": "verified", "official_website": "https://acmemedical.ca/about",
        "confidence": "high", "candidate_urls": ["https://acmemedical.ca"],
        "identity_signals": ["Exact name and Ontario device company"],
        "conflicting_signals": [], "rationale": "Strong identity match",
    }


class CanadaWebsiteLunaTests(unittest.TestCase):
    def test_prompt_includes_source_context_and_strict_identity_rules(self):
        prompt = build_prompt(company(), [{"source_name": "MaRS", "description": "Canadian cardiac startup"}])
        self.assertIn("MaRS", prompt)
        self.assertIn("similarly named foreign company", prompt)
        self.assertIn("Foreign headquarters alone does not disqualify", prompt)

    def test_high_confidence_decision_requires_live_homepage_match(self):
        fetch = lambda url: FetchResult(url, "Acme Medical makes cardiac devices in Ontario Canada", 200)
        result = validate_luna_decision(company(), verified(), {"citations": []}, "", "2026-07-28", fetch)
        self.assertEqual(result["status"], "resolved")
        bad_fetch = lambda url: FetchResult(url, "Unrelated company", 200)
        result = validate_luna_decision(company(), verified(), {"citations": []}, "", "2026-07-28", bad_fetch)
        self.assertEqual(result["status"], "manual_review")

    def test_ambiguous_decision_is_never_auto_accepted(self):
        decision = {**verified(), "decision": "ambiguous", "confidence": "medium"}
        result = validate_luna_decision(company(), decision, {}, "", "2026-07-28")
        self.assertEqual(result["status"], "manual_review")

    def test_blocked_homepage_can_use_official_domain_search_evidence(self):
        usage = {"citations": [{
            "url": "https://www.acmemedical.ca/about",
            "title": "Acme Medical",
            "content": "Acme Medical makes cardiac devices in Ontario.",
        }]}
        blocked = lambda url: FetchResult(url, "", 403, "HTTP 403")
        result = validate_luna_decision(company(), verified(), usage, "", "2026-07-28", blocked)
        self.assertEqual(result["status"], "resolved")
        self.assertIn("search evidence", result["notes"])

    def test_inactive_company_is_retained_as_status_not_website(self):
        decision = {**verified(), "decision": "inactive", "official_website": ""}
        result = validate_luna_decision(company(), decision, {}, "", "2026-07-28")
        self.assertEqual(result["status"], "inactive")
        self.assertEqual(result["website"], "")

    def test_pilot_updates_verified_company(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "companies.json"
            provenance_path = root / "provenance.json"
            input_path.write_text(json.dumps({"companies": [company()]}), encoding="utf-8")
            provenance_path.write_text(json.dumps({"records": [{
                "company_id": "ca-acme", "source_name": "MaRS VentureConnect",
                "description": "Canadian cardiac startup",
            }]}), encoding="utf-8")
            luna = lambda company, provenance, key, model: (verified(), {"cost": 0.01, "citations": []}, "")
            fetch = lambda url: FetchResult(url, "Acme Medical cardiac devices Ontario Canada", 200)
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "fixture"}, clear=True):
                summary, files = run_luna_resolution(
                    input_path, provenance_path, root / "out", "2026-07-28",
                    "MaRS", 1, 1, luna_fn=luna, fetcher=fetch,
                )
            self.assertEqual(summary["websites_resolved"], 1)
            payload = json.loads(files["companies"].read_text(encoding="utf-8"))
            self.assertEqual(payload["companies"][0]["domain"], "acmemedical.ca")


if __name__ == "__main__":
    unittest.main()
