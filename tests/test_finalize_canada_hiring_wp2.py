import unittest

from finalize_canada_hiring_wp2 import merge_official_roles


class FinalizeCanadaHiringWp2Tests(unittest.TestCase):
    def test_merge_accepts_only_official_open_and_prefers_direct(self):
        companies = [{"company_id": "c1", "company_name": "Acme", "domain": "acme.ca"}]
        direct = [{
            "company_id": "c1", "job_title": "Research Scientist",
            "job_url": "https://jobs.acme.ca/1", "captured_at": "2026-07-28",
        }]
        validations = [
            {
                "company_id": "c1", "company_name": "Acme",
                "job_title": "Research Scientist", "validation_status": "official_open",
                "official_job_url": "https://acme.ca/careers/1",
            },
            {
                "company_id": "c1", "company_name": "Acme",
                "job_title": "QA Lead", "validation_status": "official_not_found",
                "official_job_url": "",
            },
        ]
        merged = merge_official_roles(direct, validations, companies)
        self.assertEqual(1, len(merged))
        self.assertEqual("https://jobs.acme.ca/1", merged[0]["job_url"])
        self.assertEqual("official_careers_run", merged[0]["discovery_source"])


if __name__ == "__main__":
    unittest.main()
