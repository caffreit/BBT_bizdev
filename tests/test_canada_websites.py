import json
import tempfile
import unittest
from pathlib import Path

from bbt_bizdev.adapters.linkedin import PublicSearchHit
from bbt_bizdev.canada_hiring import FetchResult
from bbt_bizdev.canada_websites import (
    candidate_allowed, candidate_score, canonical_root,
    probable_domains, resolve_by_domain_probe, resolve_company_website,
    run_website_resolution,
)


def company(name="Acme Medical"):
    return {
        "company_id": "ca-acme", "company_name": name, "website": "", "domain": "",
        "province": "Ontario", "product_category": "Medical device",
        "identity_keys": [], "completeness": {},
    }


class CanadaWebsiteTests(unittest.TestCase):
    def test_canonical_root_and_directory_exclusion(self):
        self.assertEqual(canonical_root("http://www.Acme.ca/about?q=1"), "https://acme.ca")
        self.assertFalse(candidate_allowed("https://app.marsdd.com/companies/acme"))
        self.assertTrue(candidate_allowed("https://acmemedical.ca"))

    def test_identity_score_prefers_matching_official_domain(self):
        hit = PublicSearchHit("Acme Medical | Official Site", "https://acmemedical.ca/about", "Canadian medical device company")
        self.assertGreaterEqual(candidate_score(company(), hit, "Welcome to Acme Medical"), 8)

    def test_probable_domains_and_verified_probe(self):
        self.assertIn("https://acmemedical.com", probable_domains("Acme Medical Inc."))
        fetch = lambda url: (
            FetchResult(url, "Acme Medical makes medical devices in Ontario Canada", 200)
            if url == "https://acmemedical.com" else FetchResult(url, "", 404)
        )
        result = resolve_by_domain_probe(company(), "2026-07-28", fetch)
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["domain"], "acmemedical.com")

    def test_single_token_brand_requires_context(self):
        branded = company("Blueberry")
        branded["province"] = ""
        branded["product_category"] = "unknown"
        fetch = lambda url: (
            FetchResult(url, "Welcome to Blueberry, a global trading platform", 200)
            if url == "https://blueberry.com" else FetchResult(url, "", 404)
        )
        result = resolve_by_domain_probe(branded, "2026-07-28", fetch)
        self.assertEqual(result["status"], "manual_review")

    def test_resolves_strong_candidate_and_rejects_ambiguous_candidates(self):
        search = lambda _: ([PublicSearchHit("Acme Medical", "https://acmemedical.ca", "Canada medical device")], None)
        fetch = lambda url: FetchResult(url, "Acme Medical develops devices in Canada", 200)
        result = resolve_company_website(company(), "2026-07-28", search, fetch)
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["domain"], "acmemedical.ca")

    def test_search_error_is_not_no_result(self):
        result = resolve_company_website(company(), "2026-07-28", lambda _: ([], "blocked"), lambda _: None)
        self.assertEqual(result["status"], "search_error")

    def test_run_updates_only_verified_resolutions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "companies.json"
            input_path.write_text(json.dumps({"companies": [company()]}), encoding="utf-8")
            search = lambda _: ([PublicSearchHit("Acme Medical", "https://acmemedical.ca", "Canada")], None)
            fetch = lambda url: FetchResult(url, "Acme Medical Canada", 200)
            summary, files = run_website_resolution(input_path, root / "out", "2026-07-28", search_fn=search, fetcher=fetch)
            self.assertEqual(summary["websites_resolved"], 1)
            payload = json.loads(files["companies"].read_text(encoding="utf-8"))
            self.assertEqual(payload["companies"][0]["domain"], "acmemedical.ca")


if __name__ == "__main__":
    unittest.main()
