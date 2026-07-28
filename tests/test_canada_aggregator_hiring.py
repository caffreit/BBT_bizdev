import unittest

from bbt_bizdev.canada_aggregator_hiring import (
    allowed_job_url, build_prompt, job_url_verification_level, validate_decision,
)


def company():
    return {
        "company_id": "ca-acme",
        "company_name": "Acme Medical",
        "legal_name": "",
        "aliases": [],
        "website": "https://acmemedical.ca",
        "province": "Ontario",
        "product_category": "Medical device",
        "product_summary": "Cardiac devices",
    }


class CanadaAggregatorHiringTests(unittest.TestCase):
    def test_prompt_names_aggregators_and_current_role_requirement(self):
        prompt = build_prompt(company())
        self.assertIn("LinkedIn Jobs", prompt)
        self.assertIn("currently open", prompt)
        self.assertIn("expired", prompt)

    def test_allowed_job_hosts(self):
        self.assertTrue(allowed_job_url("https://ca.indeed.com/viewjob?jk=123"))
        self.assertTrue(allowed_job_url("https://jobs.lever.co/acme/123"))
        self.assertTrue(allowed_job_url("https://acmemedical.ca/jobs/123", "https://acmemedical.ca"))
        self.assertTrue(allowed_job_url("https://acme.wd3.myworkdayjobs.com/job/123"))
        self.assertFalse(allowed_job_url("https://example.com/jobs/123"))

    def test_job_url_verification_level_distinguishes_specific_and_generic_pages(self):
        self.assertEqual(
            job_url_verification_level("https://www.linkedin.com/jobs/view/12345"),
            "specific_listing",
        )
        self.assertEqual(
            job_url_verification_level("https://company.example/careers"),
            "indexed_careers_or_results_page",
        )

    def test_accepts_exact_open_relevant_role(self):
        decision = {
            "decision": "found",
            "roles": [{
                "job_title": "Quality Assurance Manager",
                "job_url": "https://ca.indeed.com/viewjob?jk=123",
                "source": "Indeed",
                "location": "Toronto, Ontario",
                "department": "Quality",
                "posted_at": "2026-07-20",
                "company_match": "exact",
                "posting_status": "open",
                "evidence": "Current employer listing",
            }],
            "rationale": "Exact current listing",
        }
        result = validate_decision(company(), decision, {}, "", "2026-07-28")
        self.assertEqual(result["status"], "matches")
        self.assertEqual(result["evidence"][0]["role_family"], "QA")

    def test_rejects_closed_or_irrelevant_role(self):
        decision = {
            "decision": "found",
            "roles": [{
                "job_title": "Office Administrator",
                "job_url": "https://www.glassdoor.ca/job-listing/123",
                "source": "Glassdoor",
                "location": "Toronto",
                "department": "Administration",
                "posted_at": "",
                "company_match": "exact",
                "posting_status": "closed",
                "evidence": "Expired",
            }],
            "rationale": "No qualifying role",
        }
        result = validate_decision(company(), decision, {}, "", "2026-07-28")
        self.assertEqual(result["status"], "no_relevant_open_roles")
        self.assertEqual(result["evidence"], [])


if __name__ == "__main__":
    unittest.main()
