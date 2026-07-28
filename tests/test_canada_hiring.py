import json
import tempfile
import unittest
from pathlib import Path

from bbt_bizdev.canada_hiring import (
    FetchResult, board_matches_company, classify_role, detect_ats, discover_careers,
    enrich_company_hiring, run_hiring_enrichment,
)
from bbt_bizdev.models import JobPosting


def company(website="https://acme.ca"):
    return {
        "company_id": "ca-company-acme", "company_name": "Acme Medical",
        "website": website, "completeness": {"hiring": {}}, "last_enriched_at": "2026-07-27",
    }


class CanadaHiringTests(unittest.TestCase):
    def test_detects_supported_ats_accounts(self):
        fixtures = {
            "https://boards.greenhouse.io/acme/jobs/1": ("greenhouse", "acme"),
            "https://jobs.lever.co/acme": ("lever", "acme"),
            "https://jobs.ashbyhq.com/acme": ("ashby", "acme"),
            "https://apply.workable.com/acme/": ("workable", "acme"),
            "https://jobs.smartrecruiters.com/Acme": ("smartrecruiters", "acme"),
            "https://acme.recruitee.com/": ("recruitee", "acme"),
        }
        for url, expected in fixtures.items():
            self.assertEqual(detect_ats(url), expected)

    def test_discovers_official_careers_link(self):
        links = discover_careers("https://acme.ca", '<a href="/about">About</a><a href="/careers">Join our team</a>')
        self.assertEqual(links, ["https://acme.ca/careers"])

    def test_board_identity_rejects_parent_company_redirect(self):
        self.assertTrue(board_matches_company("acmemedicalinc", company()))
        acquired = {**company("https://parentcorp.com"), "company_name": "Acme Medical"}
        self.assertFalse(board_matches_company("parentcorp", acquired))

    def test_classifies_role_family_and_seniority(self):
        posting = JobPosting("Director, Regulatory Affairs", "https://jobs.example/1")
        self.assertEqual(classify_role(posting)[:2], ("regulatory", "director"))
        boilerplate = JobPosting("Data Analyst", "https://jobs.example/2", "Maintain data quality for manufacturing teams")
        self.assertEqual(classify_role(boilerplate)[0], "other")

    def test_greenhouse_runner_emits_evidence_and_counts(self):
        responses = {
            "https://acme.ca": FetchResult("https://acme.ca", '<a href="https://boards.greenhouse.io/acme">Careers</a>', 200),
            "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true": FetchResult(
                "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true",
                json.dumps({"jobs": [
                    {"id": 1, "title": "Quality Engineer", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1", "location": {"name": "Toronto"}},
                    {"id": 2, "title": "Office Administrator", "absolute_url": "https://boards.greenhouse.io/acme/jobs/2"},
                ]}), 200, content_type="application/json",
            ),
        }
        result = enrich_company_hiring(company(), "2026-07-28", responses.__getitem__)
        self.assertEqual(result["status"], "complete_matches")
        self.assertEqual((result["raw_count"], result["accepted_count"]), (2, 1))
        self.assertEqual(result["evidence"][0]["role_family"], "QA")
        self.assertEqual(result["evidence"][0]["evidence_url"], "https://boards.greenhouse.io/acme/jobs/1")

    def test_successful_zero_and_blocked_are_distinct(self):
        zero = {
            "https://acme.ca": FetchResult("https://acme.ca", '<a href="https://jobs.lever.co/acme">Jobs</a>', 200),
            "https://api.lever.co/v0/postings/acme?mode=json": FetchResult("x", "[]", 200),
        }
        self.assertEqual(enrich_company_hiring(company(), "2026-07-28", zero.__getitem__)["status"], "complete_zero")
        blocked = lambda url: FetchResult(url, "Access denied", 403)
        self.assertEqual(enrich_company_hiring(company(), "2026-07-28", blocked)["status"], "blocked")

    def test_no_website_is_no_source_without_fetch(self):
        result = enrich_company_hiring(company(""), "2026-07-28", lambda _: self.fail("fetch called"))
        self.assertEqual(result["status"], "no_source")

    def test_run_writes_audit_files_and_updates_only_attempted_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "companies.json"
            input_path.write_text(json.dumps({"companies": [company("")]}), encoding="utf-8")
            summary, files = run_hiring_enrichment(input_path, root / "out", "2026-07-28", workers=1)
            self.assertEqual(summary["companies_attempted"], 1)
            self.assertEqual(summary["status_counts"]["no_source"], 1)
            self.assertTrue(all(path.exists() for path in files.values()))

    def test_shared_ats_board_is_routed_to_manual_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = [company(), {**company("https://alias.ca"), "company_id": "ca-company-alias", "company_name": "Acme Alias"}]
            input_path = root / "companies.json"
            input_path.write_text(json.dumps({"companies": rows}), encoding="utf-8")
            def fetch(url):
                if url in {"https://acme.ca", "https://alias.ca"}:
                    return FetchResult(url, '<a href="https://jobs.lever.co/acme">Jobs</a>', 200)
                return FetchResult(url, "[]", 200)
            summary, files = run_hiring_enrichment(input_path, root / "out", "2026-07-28", workers=1, fetcher=fetch)
            self.assertEqual(summary["status_counts"]["manual_review"], 2)
            evidence = json.loads(files["evidence"].read_text(encoding="utf-8"))
            self.assertEqual(evidence["records"], [])


if __name__ == "__main__":
    unittest.main()
