import unittest

from bbt_bizdev.canada_hiring_official_validation import (
    build_prompt, is_official_or_ats, validate_result,
)


class CanadaHiringOfficialValidationTests(unittest.TestCase):
    def test_official_and_ats_hosts(self):
        self.assertEqual(
            is_official_or_ats("https://acme.ca/careers/qa", "https://acme.ca"),
            (True, "employer"),
        )
        self.assertEqual(
            is_official_or_ats("https://jobs.lever.co/acme/123", "https://acme.ca"),
            (True, "ats"),
        )
        self.assertEqual(
            is_official_or_ats("https://ca.indeed.com/viewjob?jk=123", "https://acme.ca"),
            (False, "none"),
        )

    def test_prompt_rejects_aggregators_as_official(self):
        prompt = build_prompt(
            {"company_name": "Acme", "website": "https://acme.ca"},
            {"job_title": "QA Manager", "job_url": "https://indeed.com/123"},
        )
        self.assertIn("Do not treat LinkedIn", prompt)
        self.assertIn("official_open", prompt)

    def test_validation_accepts_only_official_url(self):
        company = {"company_name": "Acme", "website": "https://acme.ca"}
        role = {"company_id": "ca-acme", "company_name": "Acme", "job_title": "QA Manager"}
        decision = {
            "decision": "official_open",
            "official_job_url": "https://acme.ca/careers/qa-manager",
            "official_source_type": "employer",
            "identity_signals": ["Exact company"],
            "current_signals": ["Apply button"],
            "rationale": "Current official page",
        }
        result = validate_result(company, role, decision, {}, "", "2026-07-28")
        self.assertEqual(result["validation_status"], "official_open")
        bad = {**decision, "official_job_url": "https://indeed.com/viewjob?jk=1"}
        result = validate_result(company, role, bad, {}, "", "2026-07-28")
        self.assertEqual(result["validation_status"], "ambiguous")


if __name__ == "__main__":
    unittest.main()
