from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from pathlib import Path

from bbt_bizdev.canada_executive_luna import check_openrouter_key, listed_site_matches_official, load_api_key, record_discovered_website, run_luna_pass, verify_cited_person, verify_person
from research_canada_executives import PageParser, collect_one, homepage_matches_company, pilot, read_rows, role_rank, validate, verified_site_candidates, website_pages


class CanadaExecutiveResearchTests(unittest.TestCase):
    def test_discovered_site_requires_live_company_heading(self):
        company = {"company": "KA Imaging", "website": "", "identity_issue": False, "status": "website_missing"}
        page = PageParser()
        page.raw = "<title>KA Imaging</title><h1>KA Imaging</h1>"
        page.final_url = "https://www.kaimaging.com/"
        self.assertTrue(record_discovered_website(company, "https://kaimaging.com", lambda url: (page, "")))
        self.assertEqual(company["website"], "https://www.kaimaging.com/")
        self.assertEqual(company["status"], "website_discovered")
        other = {"company": "KA Imaging", "website": "", "identity_issue": False}
        page.raw = "<title>Other Imaging</title><p>KA Imaging is a competitor</p>"
        self.assertFalse(record_discovered_website(other, "https://kaimaging.com", lambda url: (page, "")))
        self.assertEqual(other["website"], "")
        footer_company = {"company": "Swiftsure Innovations", "website": "", "identity_issue": False}
        page.raw = "<title>Swiftsure</title><footer>© 2026 Swiftsure Innovations</footer>"
        page.final_url = "https://swiftsure.com/"
        self.assertTrue(record_discovered_website(footer_company, "https://swiftsure.com", lambda url: (page, "")))

    def test_missing_website_has_distinct_status(self):
        company = {"row_id": "wp6-row-8", "company": "KA Imaging", "website": "", "identity_issue": False}
        self.assertEqual(collect_one(company, use_search=False), [])
        self.assertEqual(company["status"], "website_missing")

    def test_listed_domain_change_requires_real_redirect_and_identity_match(self):
        company = {"company": "AmacaThera", "website": "https://amacathera.ca", "identity_issue": False}
        page = PageParser()
        page.raw = "<title>AmacaThera</title>"
        page.final_url = "https://amacathera.com/"
        fetch = lambda url: (page, "")
        self.assertTrue(listed_site_matches_official(company, "https://amacathera.com", fetch))
        page.final_url = "https://unrelated.example/"
        self.assertFalse(listed_site_matches_official(company, "https://amacathera.com", fetch))

    def test_private_key_file_is_available_to_separate_processes(self):
        with TemporaryDirectory() as directory, patch.dict("os.environ", {"OPENROUTER_API_KEY": "", "BBT_OPENROUTER_API_KEY": ""}):
            path = Path(directory) / "openrouter.key"
            path.write_text("test-secret\n", encoding="utf-8")
            path.chmod(0o600)
            self.assertEqual(load_api_key(path), "test-secret")
            path.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError, "readable only by you"):
                load_api_key(path)

    def test_key_check_does_not_return_the_secret(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{"data":{"limit_remaining":4.5}}'
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-secret"}), patch("bbt_bizdev.canada_executive_luna.urlopen", return_value=Response()) as send:
            result = check_openrouter_key()
        self.assertEqual(result, {"authenticated": True, "limit_remaining_usd": 4.5, "expires_at": None})
        self.assertNotIn("test-secret", str(result))
        self.assertEqual(send.call_args.args[0].full_url, "https://openrouter.ai/api/v1/key")

    def test_redirected_homepage_prioritizes_team_page(self):
        home = PageParser()
        home.final_url = "https://www.example.com/"
        home.links = [(f"/page-{number}", "About company") for number in range(8)]
        home.links.append(("/meet-the-team", "Our team"))
        with patch("research_canada_executives.fetch_page", return_value=(home, "")):
            pages, error = website_pages("https://example.com")
        self.assertFalse(error)
        self.assertEqual(pages[0][0], "https://www.example.com/")
        self.assertEqual(pages[1][0], "https://www.example.com/meet-the-team")

    def test_about_page_can_lead_to_nested_leadership_page(self):
        home = PageParser(); home.raw = "<title>Example Medical</title>"; home.final_url = "https://example.com/"
        about = PageParser(); about.raw = "<h1>About</h1>"; about.final_url = "https://example.com/about/"
        about.links = [("leadership-team/", "Leadership Team")]
        team = PageParser(); team.raw = '<div><h2>Ada Smith</h2><p>CEO</p><a href="https://www.linkedin.com/in/ada-smith">LinkedIn</a></div>'
        team.final_url = "https://example.com/about/leadership-team/"
        company = {"row_id": "wp6-row-10", "company": "Example Medical", "website": "https://example.com", "identity_issue": False}
        with patch("research_canada_executives.website_pages", return_value=([("https://example.com/", home), ("https://example.com/about/", about)], "")), patch("research_canada_executives.fetch_page", return_value=(team, "")):
            found = collect_one(company, use_search=False)
        self.assertIn(team.final_url, company["pages_visited"])
        self.assertEqual([item["name"] for item in found if item["decision"] == "accept"], ["Ada Smith"])

    def test_credentials_are_removed_from_name_but_exact_title_is_kept(self):
        page = PageParser()
        page.raw = '''<div><h3>Karen Cross, MD, PhD, FRCSC</h3><div>CEO and Co-Founder</div>
          <a href="https://www.linkedin.com/in/drkarencross">LinkedIn</a></div>
          <div><h3>Dr. Derek Exner. FACC, FHRS</h3><h5>Co-Founder / Chief Medical Officer</h5>
          <a href="https://www.linkedin.com/in/dvexner">LinkedIn</a></div>'''
        company = {"company": "Example Medical", "identity_issue": False}
        found = verified_site_candidates(company, "https://example.com/team", page, True)
        self.assertEqual([(item["name"], item["title"]) for item in found],
                         [("Karen Cross", "CEO and Co-Founder"), ("Derek Exner", "Co-Founder / Chief Medical Officer")])

    def test_bio_card_with_short_name_and_title_paragraphs(self):
        page = PageParser()
        page.raw = '''<div><p>Sabina built medical devices and now leads market access. Her work spans several disciplines.</p>
          <p>Dr. Sabina Bruehlmann</p><p>Chief Executive Officer</p>
          <a href="https://www.linkedin.com/in/sabinabruehlmann/">LinkedIn</a></div>'''
        found = verified_site_candidates({"company": "Nimble Science", "identity_issue": False},
                                         "https://www.nimblesci.com/team", page, True)
        self.assertEqual([(item["name"], item["title"]) for item in found],
                         [("Sabina Bruehlmann", "Chief Executive Officer")])

    def test_luna_verification_requires_live_official_page_and_exact_link(self):
        company = {"row_id": "wp6-row-10", "company": "Example Medical", "website": "https://example.com", "identity_issue": False}
        home = PageParser()
        home.raw = "<title>Example Medical</title><h1>Example Medical</h1>"
        home.final_url = "https://example.com/"
        team = PageParser()
        team.raw = '<div><h2>Ada Smith</h2><p>CEO</p><a href="https://www.linkedin.com/in/ada-smith">LinkedIn</a></div>'
        team.final_url = "https://example.com/team"
        person = {"name": "Ada Smith", "title": "CEO", "linkedin_url": "https://www.linkedin.com/in/ada-smith", "role_url": "https://example.com/team", "conflict": ""}
        def fetch(url):
            return (home if url == "https://example.com" else team), ""
        self.assertEqual(verify_person(company, person, "https://example.com", fetch)["decision"], "accept")
        self.assertIsNone(verify_person(company, {**person, "linkedin_url": "https://www.linkedin.com/in/wrong-person"}, "https://example.com", fetch))
        self.assertIsNone(verify_person(company, {**person, "conflict": "Possible former CEO"}, "https://example.com", fetch))
        self.assertIsNone(verify_person(company, {**person, "role_url": "https://other.com/team"}, "https://example.com", fetch))

    def test_luna_can_verify_matching_official_role_and_public_linkedin_company(self):
        company = {"row_id": "wp6-row-8", "company": "KA Imaging", "website": "https://kaimaging.com", "identity_issue": False}
        home = PageParser(); home.raw = "<title>KA Imaging</title>"; home.final_url = "https://kaimaging.com/"
        team = PageParser(); team.raw = '<div><h3>Amol Karnick (M.Eng, BASc)</h3><p>President and Chief Executive Officer (CEO)</p></div>'; team.final_url = "https://kaimaging.com/our-team/"
        profile = PageParser(); profile.raw = "<title>Amol Karnick - KA Imaging Inc. | LinkedIn</title>"; profile.final_url = "https://ca.linkedin.com/in/akarnick"
        person = {"name": "Amol Karnick", "title": "CEO", "linkedin_url": "https://ca.linkedin.com/in/akarnick", "role_url": "https://kaimaging.com/our-team/", "conflict": ""}
        def fetch(url):
            return (profile if "linkedin.com" in url else team if "our-team" in url else home), ""
        accepted = verify_person(company, person, "https://kaimaging.com", fetch)
        self.assertEqual(accepted["reason"], "luna_official_role_and_linkedin_company")
        profile.raw = "<title>Amol Karnick - Another Company | LinkedIn</title>"
        self.assertIsNone(verify_person(company, person, "https://kaimaging.com", fetch))

    def test_cited_verification_requires_official_role_and_exact_current_profile(self):
        company = {"row_id": "wp6-row-5", "company": "Swift Medical", "website": "https://swiftmedical.com", "identity_issue": False}
        person = {"name": "Dwayne Sansone", "title": "Chief Executive Officer",
                  "linkedin_url": "https://www.linkedin.com/in/dwayne-sansone-2425a287",
                  "role_url": "https://swiftmedical.com/about/leadership-team/", "conflict": ""}
        role = {"url": person["role_url"], "title": "Leadership Team - Swift Medical",
                "content": "Swift Medical leadership team\nDwayne Sansone\nChief Executive Officer\nStratos Davlos\nChief Technology Officer"}
        profile = {"url": person["linkedin_url"], "title": "Dwayne Sansone - Swift Medical | LinkedIn",
                   "content": "Dwayne Sansone\nChief Executive Officer at Swift Medical\nExperience"}
        accepted = verify_cited_person(company, person, company["website"], [role, profile])
        self.assertEqual(accepted["reason"], "luna_cited_official_role_and_exact_profile")
        self.assertIsNone(verify_cited_person(company, person, company["website"],
                                               [role, {**profile, "url": "https://www.linkedin.com/in/other"}]))
        self.assertIsNone(verify_cited_person(company, person, company["website"],
                                               [role, {**profile, "title": "Dwayne Sansone - Another Company | LinkedIn",
                                                       "content": "Dwayne Sansone\nCEO at Another Company"}]))
        self.assertIsNone(verify_cited_person(company, person, company["website"],
                                               [{**role, "content": "Swift Medical leadership team\nDwayne Sansone\nDirector"}, profile]))
        self.assertIsNone(verify_cited_person({**company, "website": ""}, person,
                                               company["website"], [role, profile]))
        old_news = {**person, "role_url": "https://swiftmedical.com/2023-ceo-announcement/"}
        self.assertIsNone(verify_cited_person(company, old_news, company["website"],
                                               [{**role, "url": old_news["role_url"]}, profile]))

    def test_luna_pass_caps_calls_caches_and_queues_unverified(self):
        companies = [{"row_id": f"wp6-row-{i}", "company": f"Example {i}", "website": "", "identity_issue": False} for i in range(2, 5)]
        calls = []
        def requester(company, prior, key):
            calls.append(company["row_id"])
            return {"official_website": "https://example.com", "company_status": "active", "people": [{"name": "Ada Smith", "title": "CEO", "linkedin_url": f"https://www.linkedin.com/in/ada-{company['row_id']}", "role_url": "https://example.com/team", "email": "", "email_url": "", "conflict": ""}]}, {"cost": 0.2}, ""
        with TemporaryDirectory() as directory, patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            decisions, summary = run_luna_pass(companies, [], Path(directory), limit=1, max_cost_usd=1, requester=requester, verifier=lambda *args: None)
            self.assertEqual(len(calls), 1)
            self.assertEqual(summary["reported_cost_usd"], 0.2)
            self.assertEqual(decisions[0]["decision"], "pending")
            self.assertEqual(decisions[0]["email"], "")
            decisions, summary = run_luna_pass(companies[:1], decisions, Path(directory), limit=1, max_cost_usd=1, requester=requester, verifier=lambda *args: None)
            self.assertEqual(len(calls), 1)
            self.assertEqual(summary["cache_hits"], 1)
            self.assertEqual(len(decisions), 1)
            def verified(company, person, official):
                return {**decisions[0], "decision": "accept", "reason": "luna_found_official_team_card"}
            decisions, summary = run_luna_pass(companies[:1], decisions, Path(directory), limit=1, max_cost_usd=1, requester=requester, verifier=verified)
            self.assertEqual(len(decisions), 1)
            self.assertEqual(decisions[0]["decision"], "accept")
            self.assertEqual(summary["accepted"], 1)

    def test_luna_second_pass_can_resolve_missing_profile_from_cited_search(self):
        company = {"row_id": "wp6-row-5", "source_row": 5, "company": "Swift Medical",
                   "website": "https://swiftmedical.com", "identity_issue": False}
        person = {"name": "Dwayne Sansone", "title": "Chief Executive Officer",
                  "linkedin_url": "", "role_url": "https://swiftmedical.com/about/leadership-team/",
                  "email": "", "email_url": "", "conflict": ""}
        role = {"url": person["role_url"], "title": "Leadership Team - Swift Medical",
                "content": "Swift Medical leadership\nDwayne Sansone\nChief Executive Officer"}
        profile = {"url": "https://www.linkedin.com/in/dwayne-sansone-2425a287",
                   "title": "Dwayne Sansone - Swift Medical | LinkedIn",
                   "content": "Dwayne Sansone\nCEO at Swift Medical"}
        calls = []
        def discover(*args):
            calls.append("discover")
            return {"official_website": company["website"], "company_status": "active",
                    "people": [person]}, {"cost": 0.01, "citations": [role]}, ""
        def find_profile(*args):
            calls.append("profile")
            return {"people": [{"name": person["name"], "linkedin_url": profile["url"],
                                "match_status": "confirmed", "conflict": ""}]}, {"cost": 0.01, "citations": [profile]}, ""
        with TemporaryDirectory() as directory, patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            decisions, summary = run_luna_pass([company], [], Path(directory), limit=2,
                                               max_cost_usd=0.03, requester=discover,
                                               profile_requester=find_profile,
                                               verifier=lambda *args: None)
            self.assertEqual(calls, ["discover", "profile"])
            self.assertEqual(summary["accepted"], 1)
            self.assertEqual(summary["reported_cost_usd"], 0.02)
            self.assertEqual(decisions[0]["linkedin_url"], profile["url"])
            evidence = __import__("json").loads((Path(directory) / "luna_cited_evidence.json").read_text())
            self.assertEqual(evidence[decisions[0]["candidate_id"]]["profile"]["url"], profile["url"])
            again, replay = run_luna_pass([company], [], Path(directory), limit=1,
                                          max_cost_usd=0.03, requester=discover,
                                          profile_requester=find_profile,
                                          verifier=lambda *args: None)
            self.assertEqual(calls, ["discover", "profile"])
            self.assertEqual(replay["cache_hits"], 2)
            self.assertEqual(len(again), 1)

    def test_official_team_card_can_be_verified_without_a_model(self):
        home = PageParser()
        home.raw = '<html><title>Example Medical</title><body><h1>Example Medical</h1></body></html>'
        team = PageParser()
        team.raw = '''<h1>Leadership</h1>
          <div class="person"><h2>Ada Smith</h2><p>Chief Executive Officer</p>
          <a href="https://www.linkedin.com/in/ada-smith">LinkedIn</a>
          <a href="mailto:ada.smith@example.com">Email</a></div>
          <div class="person"><h2>Ben Jones</h2><p>Chief Technology Officer</p>
          <a href="https://www.linkedin.com/in/ben-jones">LinkedIn</a></div>'''
        company = {"row_id": "wp6-row-10", "company": "Example Medical", "website": "https://example.com", "identity_issue": False}
        self.assertTrue(homepage_matches_company(company, home))
        with patch("research_canada_executives.website_pages", return_value=([("https://example.com", home), ("https://example.com/team", team)], "")), patch("research_canada_executives.fetch_page", return_value=(team, "")), patch("research_canada_executives.search_candidates", return_value=([], [])):
            found = collect_one(company)
        accepted = [item for item in found if item["decision"] == "accept"]
        self.assertEqual({item["name"] for item in accepted}, {"Ada Smith", "Ben Jones"})
        self.assertEqual(next(item for item in accepted if item["name"] == "Ada Smith")["email"], "ada.smith@example.com")
        selected, issues = validate([company], accepted)
        self.assertEqual(len(selected), 2)
        self.assertFalse(issues)

    def test_ambiguous_or_unverified_site_never_auto_accepts(self):
        page = PageParser()
        page.raw = '''<div><h2>Ada Smith</h2><p>CEO</p>
          <a href="https://www.linkedin.com/in/ada-smith">LinkedIn</a>
          <a href="https://www.linkedin.com/in/another-person">LinkedIn</a></div>'''
        company = {"company": "Example Medical", "identity_issue": False}
        self.assertEqual(verified_site_candidates(company, "https://example.com/team", page, True), [])
        self.assertFalse(homepage_matches_company(company, page))
        company["identity_issue"] = True
        page.raw = "<title>Example Medical</title>"
        self.assertFalse(homepage_matches_company(company, page))

    def test_source_rows_and_pilot_are_stable(self):
        rows = read_rows(__import__("research_canada_executives").SOURCE)
        selected = pilot(rows)
        self.assertEqual(len(rows), 1503)
        self.assertEqual(len(selected), 25)
        self.assertEqual(len({row["row_id"] for row in selected}), 25)
        self.assertEqual(selected[0]["row_id"], "wp6-row-2")
        self.assertFalse(rows[1]["identity_issue"])  # Resolved duplicate, not an ambiguous identity.
        self.assertTrue(rows[1]["alias_review"])
        original_ids = [row["row_id"] for row in selected]
        for row in rows:
            if not row["website"]:
                row["website"] = "https://discovered.example"
        self.assertEqual([row["row_id"] for row in pilot(rows)], original_ids)

    def test_acceptance_requires_review_and_field_evidence(self):
        company = {"row_id": "wp6-row-2"}
        good = {"candidate_id": "one", "row_id": "wp6-row-2", "name": "Test Person", "title": "CEO", "linkedin_url": "https://www.linkedin.com/in/test-person", "role_url": "https://example.org/team", "linkedin_evidence_url": "https://example.org/team", "email": "", "phone": "", "identity_verified": "yes", "employment_verified": "yes", "linkedin_verified": "yes", "decision": "accept"}
        selected, issues = validate([company], [good])
        self.assertEqual(len(selected), 1)
        self.assertFalse(issues)
        bad = {**good, "candidate_id": "two", "identity_verified": "", "email": "test@example.org"}
        selected, issues = validate([company], [bad])
        self.assertFalse(selected)
        self.assertTrue(any("identity_verified" in issue and "email evidence URL" in issue for issue in issues))

    def test_role_order_and_three_person_limit(self):
        self.assertLess(role_rank("Chief Executive Officer"), role_rank("COO"))
        self.assertLess(role_rank("Chief Technology Officer"), role_rank("CFO"))
        people = []
        for number, title in enumerate(["CFO", "CEO", "CTO", "COO"], 1):
            people.append({"candidate_id": str(number), "row_id": "wp6-row-2", "name": f"Person {number}", "title": title, "linkedin_url": f"https://www.linkedin.com/in/person-{number}", "role_url": "https://example.org/team", "linkedin_evidence_url": "https://example.org/team", "email": "", "phone": "", "identity_verified": "yes", "employment_verified": "yes", "linkedin_verified": "yes", "decision": "accept"})
        selected, issues = validate([{"row_id": "wp6-row-2"}], people)
        self.assertEqual([item["title"] for item in selected], ["CEO", "COO", "CTO"])
        self.assertFalse(issues)


if __name__ == "__main__":
    unittest.main()
