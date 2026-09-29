from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from bbt_bizdev.adapters.linkedin import PublicSearchHit
from bbt_bizdev.canada_executive_investigation import (
    Budget, _resolve_exact_profile, _source, assess_claim, run_investigation,
    valid_response,
)
from research_canada_executives import PageParser, defer_new_automatic_acceptances


TODAY = date(2026, 9, 25)


def company(name="Swift Medical", website="https://swiftmedical.com", row=5):
    return {"row_id": f"wp6-row-{row}", "source_row": row, "company": name,
            "website": website, "source_website": website, "identity_issue": False}


def homepage(name="Swift Medical", website="https://swiftmedical.com"):
    raw = f"<title>{name}</title><h1>{name}</h1>"
    return {**_source("fetch", website, name, name, fetched=True, final_url=website),
            "raw_html": raw}


def claim(name="Dwayne Sansone", title="Chief Executive Officer",
          profile="https://www.linkedin.com/in/dwayne-sansone-2425a287",
          role="https://swiftmedical.com/about/leadership-team/"):
    return {"name": name, "title": title, "linkedin_url": profile,
            "role_url": role, "linkedin_evidence_url": profile,
            "verdict": "supported", "role_date": "", "profile_date": "",
            "conflicts": [], "source_urls": [role, profile]}


def role_source(name="Dwayne Sansone", title="Chief Executive Officer",
                url="https://swiftmedical.com/about/leadership-team/", raw=""):
    text = f"Swift Medical leadership team {name} {title}"
    return {**_source("fetch" if raw else "indexed", url, "Leadership Team - Swift Medical",
                      text, fetched=bool(raw), final_url=url if raw else ""),
            "raw_html": raw} if raw else _source("indexed", url, "Leadership Team - Swift Medical", text)


def profile_source(name="Dwayne Sansone", company_name="Swift Medical",
                   url="https://www.linkedin.com/in/dwayne-sansone-2425a287"):
    return _source("indexed", url, f"{name} - {company_name} | LinkedIn",
                   f"{name} Chief Executive Officer at {company_name}")


class InvestigationTests(unittest.TestCase):
    def test_unknown_billing_in_journal_blocks_paid_resume(self):
        with TemporaryDirectory() as directory, patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            root = Path(directory)
            (root / "request_journal.json").write_text(json.dumps({"base_cost": .02,
                "base_requests": 2, "requests": [{"state": "in_flight", "usage": {}}]}))
            def forbidden(*args):
                self.fail("Must not make a request when previous billing is unknown")
            _, summary = run_investigation([company()], [], root, source_rows={5}, requester=forbidden)
        self.assertEqual(summary["stopped_reason"], "missing_cost_data")
        self.assertEqual(summary["openrouter_requests"], 3)
        self.assertEqual(summary["reported_cost_usd"], .02)

    def test_redirect_and_stale_team_page_cannot_support_role(self):
        p = claim()
        source = role_source(raw='<p>Dwayne Sansone Chief Executive Officer</p>')
        source["final_url"] = "https://unrelated.example/team"
        for change in ({}, {"final_url": p["role_url"], "published_at": "2020-01-01"}):
            source.update(change)
            ok, _, _ = assess_claim(company(), p, [homepage(), source, profile_source()],
                company_verdict="supported", company_status="active", conflict_checked=True, today=TODAY)
            self.assertFalse(ok)

    def test_missing_role_gets_feedback_and_model_selects_new_source(self):
        c, p = company(), claim()
        bad = {**p, "role_url": "https://directory.example/swift"}
        responses = iter([bad, p])
        requests = []
        def requester(payload, key):
            requests.append(payload)
            response = {"official_website": c["website"], "company_verdict": "supported",
                        "company_status": "active", "actions": [], "claims": [next(responses)]}
            return {"choices": [{"message": {"content": json.dumps(response)}}], "usage": {"cost": .01}}
        def searcher(query):
            return [PublicSearchHit("Swift Medical Leadership", p["role_url"],
                        "Dwayne Sansone Chief Executive Officer at Swift Medical"),
                    PublicSearchHit("Dwayne Sansone - Swift Medical", p["linkedin_url"],
                        "Dwayne Sansone Chief Executive Officer at Swift Medical")], None
        def fetcher(url):
            page = PageParser()
            page.raw = "<title>Swift Medical</title><h1>Swift Medical</h1>"
            page.final_url = url
            return page, ""
        with TemporaryDirectory() as directory, patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            decisions, summary = run_investigation([c], [], Path(directory), source_rows={5},
                searcher=searcher, fetcher=fetcher, requester=requester)
        self.assertEqual(summary["newly_accepted"], 1)
        self.assertEqual(len(requests), 2)
        self.assertIn('gate_feedback', requests[1]["messages"][0]["content"])
        self.assertEqual(decisions[0]["role_url"], p["role_url"])

    def test_legacy_auto_accepts_are_deferred_without_changing_baseline(self):
        rows = [{"candidate_id": "old", "decision": "accept", "email": "sourced@example.com"},
                {"candidate_id": "new", "decision": "accept", "email": "unsourced@example.com",
                 "identity_verified": "yes", "employment_verified": "yes", "linkedin_verified": "yes"}]
        self.assertEqual(defer_new_automatic_acceptances(rows, {"old"},
                         "requires_investigation"), 1)
        self.assertEqual(rows[0]["decision"], "accept")
        self.assertEqual(rows[1]["decision"], "pending")
        self.assertEqual(rows[1]["email"], "")

    def test_swift_official_card_direct_exact_link(self):
        person = claim()
        raw = '<div><h2>Dwayne Sansone</h2><p>Chief Executive Officer</p><a href="https://www.linkedin.com/in/dwayne-sansone-2425a287">LinkedIn</a></div>'
        role = role_source(raw=raw)
        ok, reason, refs = assess_claim(company(), person,
            [homepage(), role], company_verdict="supported", company_status="active",
            conflict_checked=True, today=TODAY)
        self.assertTrue(ok, reason)
        self.assertEqual(reason, "official_card+official_direct_profile")
        self.assertEqual(refs["role"], role["evidence_id"])

    def test_trexo_official_role_and_indexed_exact_profile(self):
        c = company("Trexo Robotics", "https://trexorobotics.com", 17)
        p = claim("Manmeet Maggu", "Founder & CEO", "https://www.linkedin.com/in/manmeetmaggu",
                  "https://trexorobotics.com/who-we-are/")
        role = _source("indexed", p["role_url"], "Who we are - Trexo Robotics",
                       "Trexo Robotics Manmeet Maggu Founder and CEO")
        profile = profile_source("Manmeet Maggu", "Trexo Robotics", p["linkedin_url"])
        ok, reason, _ = assess_claim(c, p, [homepage(c["company"], c["website"]), role, profile],
            company_verdict="supported", company_status="active", conflict_checked=True, today=TODAY)
        self.assertTrue(ok, reason)

    def test_optina_former_ceo_and_stale_post_stay_pending(self):
        c = company("Optina Diagnostics", "https://optina.example", 35)
        p = claim("David Lapointe", "CEO", "https://www.linkedin.com/in/david-lapointe",
                  "https://www.linkedin.com/posts/optina-diagnostics_old")
        old = _source("indexed", p["role_url"], "Optina Diagnostics CEO",
                      "2023-08-01 Optina Diagnostics David Lapointe CEO", published_at="2023-08-01")
        former = _source("indexed", "https://news.example/former", "Former CEO David Lapointe",
                         "2026-01-01 Former CEO David Lapointe left Optina Diagnostics")
        ok, reason, _ = assess_claim(c, p, [homepage(c["company"], c["website"]), old,
            profile_source(p["name"], c["company"], p["linkedin_url"]), former],
            company_verdict="supported", company_status="active", conflict_checked=True, today=TODAY)
        self.assertFalse(ok)
        self.assertEqual(reason, "unresolved_conflicting_evidence")

    def test_closed_financing_is_not_a_company_closure(self):
        from bbt_bizdev.canada_executive_investigation import _unresolved_conflict
        for excerpt in ("Exact Imaging reported it has closed on $10 million in financing.",
                        "Swift Medical secured financing. The financing closed in 2023. Dwayne Sansone joined its board."):
            source = _source("indexed", "https://news.example/funding", "Funding", excerpt)
            self.assertFalse(_unresolved_conflict(source, "Exact Imaging", "Randy AuCoin"))
            self.assertFalse(_unresolved_conflict(source, "Swift Medical", "Dwayne Sansone"))
        for excerpt in ("Swiftsure Innovations has shut down.", "Swiftsure Innovations closed its doors.",
                        "Janpix was acquired by another company."):
            source = _source("indexed", "https://news.example/closure", "Closure", excerpt)
            self.assertTrue(_unresolved_conflict(source, "Janpix" if "Janpix" in excerpt else "Swiftsure Innovations", "Someone"))

    def test_unrelated_former_executive_does_not_conflict_with_current_ceo(self):
        p = claim()
        unrelated = _source("indexed", "https://news.example/transition", "Swift Medical leadership",
                            "Swift Medical Dwayne Sansone Chief Executive Officer. Former COO Rob Fraser now advises the board.")
        ok, reason, _ = assess_claim(company(), p,
            [homepage(), role_source(), profile_source(), unrelated],
            company_verdict="supported", company_status="active",
            conflict_checked=True, today=TODAY)
        self.assertTrue(ok, reason)

    def test_python_resolves_one_exact_profile_without_guessing_slug(self):
        p = claim(profile="")
        c = company()
        def searcher(query):
            self.assertIn('"Dwayne Sansone"', query)
            return [PublicSearchHit("Dwayne Sansone - Swift Medical | LinkedIn",
                "https://www.linkedin.com/in/dwayne-sansone-2425a287",
                "Dwayne Sansone Chief Executive Officer at Swift Medical")], None
        budget = Budget(max_cost_usd=1, max_requests=5, max_searches=5, max_fetches=5)
        with TemporaryDirectory() as directory:
            resolved, result = _resolve_exact_profile(c, p, [], Path(directory), "test-key",
                                                     budget, searcher=searcher)
        self.assertEqual(resolved["linkedin_url"],
                         "https://www.linkedin.com/in/dwayne-sansone-2425a287")
        self.assertEqual(result["resolved_profile"], resolved["linkedin_url"])

    def test_radialis_same_name_profile_other_company_is_pending(self):
        c = company("Radialis", "https://radialis.com", 15)
        p = claim("Eric Tribe", "CEO", "https://www.linkedin.com/in/eric-tribe",
                  "https://radialis.com/team/")
        sources = [homepage(c["company"], c["website"]),
                   _source("indexed", p["role_url"], "Radialis team", "Radialis Eric Tribe CEO"),
                   profile_source("Eric Tribe", "Other Company", p["linkedin_url"])]
        ok, reason, _ = assess_claim(c, p, sources, company_verdict="supported",
            company_status="active", conflict_checked=True, today=TODAY)
        self.assertFalse(ok)
        self.assertEqual(reason, "profile_identity_insufficient")
        # A second person cannot inherit Eric Tribe's exact profile URL.
        other = {**p, "name": "Another Executive"}
        ok, reason, _ = assess_claim(c, other, sources, company_verdict="supported",
            company_status="active", conflict_checked=True, today=TODAY)
        self.assertFalse(ok)
        self.assertEqual(reason, "role_evidence_insufficient")

    def test_inactive_acquired_and_wrong_entity_fail(self):
        p = claim()
        sources = [homepage(), role_source(), profile_source()]
        for status in ("inactive", "acquired", "uncertain"):
            ok, _, _ = assess_claim(company(), p, sources, company_verdict="supported",
                company_status=status, conflict_checked=True, today=TODAY)
            self.assertFalse(ok, status)
        c = company("Kyva", "https://kyva.example", 602)
        ok, reason, _ = assess_claim(c, p, sources, company_verdict="wrong-company",
            company_status="active", conflict_checked=True, today=TODAY)
        self.assertFalse(ok)
        self.assertEqual(reason, "company_identity_or_activity_unverified")

    def test_blocked_linkedin_and_incomplete_conflict_search_are_pending(self):
        p = claim()
        sources = [homepage(), role_source(),
                   _source("fetch", p["linkedin_url"], "", "", error="HTTP 999")]
        ok, reason, _ = assess_claim(company(), p, sources, company_verdict="supported",
            company_status="active", conflict_checked=True, today=TODAY)
        self.assertFalse(ok)
        self.assertEqual(reason, "profile_identity_insufficient")
        ok, reason, _ = assess_claim(company(), p, sources + [profile_source()],
            company_verdict="supported", company_status="active", conflict_checked=False, today=TODAY)
        self.assertFalse(ok)
        self.assertEqual(reason, "conflict_search_incomplete")

    def test_old_announcement_and_model_only_date_do_not_pass(self):
        c = company("Spring Loaded Technology", "https://springloadedtech.com", 28)
        p = claim("Joe Ellsmere", "CEO", "https://www.linkedin.com/in/joe-ellsmere-272b2675",
                  "https://www.newsfilecorp.com/release/old")
        p["role_date"] = "2026-09-01"
        role = _source("indexed", p["role_url"], "Spring Loaded Technology CEO",
                       "Spring Loaded Technology Joe Ellsmere CEO", published_at="2023-09-01")
        ok, reason, _ = assess_claim(c, p, [homepage(c["company"], c["website"]), role,
            profile_source(p["name"], c["company"], p["linkedin_url"])],
            company_verdict="supported", company_status="active", conflict_checked=True, today=TODAY)
        self.assertFalse(ok)
        self.assertEqual(reason, "role_evidence_insufficient")

    def test_recent_issued_announcement_with_exact_profile(self):
        c = company("Spring Loaded Technology", "https://springloadedtech.com", 28)
        p = claim("Joe Ellsmere", "CEO", "https://www.linkedin.com/in/joe-ellsmere-272b2675",
                  "https://www.newsfilecorp.com/release/301785")
        role = _source("indexed", p["role_url"], "Spring Loaded Technology CEO",
                       "2026-07-01 Spring Loaded Technology Joe Ellsmere CEO", published_at="2026-07-01")
        ok, reason, _ = assess_claim(c, p, [homepage(c["company"], c["website"]), role,
            profile_source(p["name"], c["company"], p["linkedin_url"])],
            company_verdict="supported", company_status="active", conflict_checked=True, today=TODAY)
        self.assertTrue(ok, reason)
        self.assertEqual(reason, "recent_issued_announcement+indexed_exact_profile")

    def test_personal_post_must_match_profile_author_slug(self):
        c = company("Trexo Robotics", "https://trexorobotics.com", 17)
        p = claim("Manmeet Maggu", "CEO", "https://www.linkedin.com/in/manmeetmaggu",
                  "https://trexorobotics.com/who-we-are/")
        p["linkedin_evidence_url"] = "https://www.linkedin.com/posts/manmeetmaggu_trexo-activity-1"
        role = _source("indexed", p["role_url"], "Trexo Robotics team",
                       "Trexo Robotics Manmeet Maggu CEO")
        post = _source("indexed", p["linkedin_evidence_url"], "Manmeet Maggu on LinkedIn",
                       "2026-05-01 Manmeet Maggu leads Trexo Robotics", published_at="2026-05-01")
        ok, reason, _ = assess_claim(c, p, [homepage(c["company"], c["website"]), role, post],
            company_verdict="supported", company_status="active", conflict_checked=True, today=TODAY)
        self.assertTrue(ok, reason)
        self.assertEqual(reason, "official_team+recent_attributable_personal_post")
        wrong = {**post, "url": "https://www.linkedin.com/posts/other-person_trexo-activity-1"}
        p["linkedin_evidence_url"] = wrong["url"]
        ok, _, _ = assess_claim(c, p, [homepage(c["company"], c["website"]), role, wrong],
            company_verdict="supported", company_status="active", conflict_checked=True, today=TODAY)
        self.assertFalse(ok)

    def test_company_post_requires_official_company_link(self):
        c = company("Flutter Care", "https://fluttercare.com", 1202)
        p = claim("Dolma Tsundu", "CEO", "https://www.linkedin.com/in/dolmatsundu",
                  "https://www.linkedin.com/posts/fluttercareinc_futurefocus-activity-1")
        home = homepage(c["company"], c["website"])
        home["raw_html"] = '<title>Flutter Care</title><h1>Flutter Care</h1><a href="https://www.linkedin.com/company/fluttercareinc/">LinkedIn</a>'
        role = _source("indexed", p["role_url"], "Flutter Care CEO",
                       "2026-06-01 Flutter Care Dolma Tsundu CEO", published_at="2026-06-01")
        sources = [home, role, profile_source(p["name"], c["company"], p["linkedin_url"])]
        ok, reason, _ = assess_claim(c, p, sources, company_verdict="supported",
            company_status="active", conflict_checked=True, today=TODAY)
        self.assertTrue(ok, reason)
        self.assertEqual(reason, "recent_company_post+indexed_exact_profile")
        home["raw_html"] = home["raw_html"].replace("/fluttercareinc/", "/fluttercare/")
        ok, _, _ = assess_claim(c, p, sources, company_verdict="supported",
            company_status="active", conflict_checked=True, today=TODAY)
        self.assertFalse(ok, "A company handle prefix must not establish authorship")
        home["raw_html"] = "<title>Flutter Care</title><h1>Flutter Care</h1>"
        ok, _, _ = assess_claim(c, p, sources, company_verdict="supported",
            company_status="active", conflict_checked=True, today=TODAY)
        self.assertFalse(ok)

    def test_schema_rejects_prose_and_extra_fields(self):
        self.assertFalse(valid_response("CEO is Ada"))
        response = {"official_website": "https://example.com", "company_verdict": "supported",
                    "company_status": "active", "actions": [], "claims": [claim()]}
        self.assertTrue(valid_response(response))
        self.assertFalse(valid_response({**response, "made_up": "yes"}))
        self.assertFalse(valid_response({**response, "claims": [{**claim(), "verdict": "certain"}]}))

    def test_budget_stops_before_request_and_on_missing_cost(self):
        low = Budget(max_cost_usd=.04, max_requests=24, max_searches=48, max_fetches=32)
        self.assertFalse(low.can_request())
        self.assertEqual(low.stopped_reason, "cost_reserve")
        budget = Budget(max_cost_usd=1, max_requests=24, max_searches=48, max_fetches=32)
        budget.record_request({})
        self.assertFalse(budget.can_request())
        self.assertEqual(budget.stopped_reason, "missing_cost_data")

    def test_live_loop_caches_and_deduplicates_on_replay(self):
        c = company()
        p = claim()
        responses = [
            {"official_website": c["website"], "company_verdict": "supported",
             "company_status": "active", "actions": [
                 {"kind": "search_person_role", "query": "role", "url": "", "person": p["name"]},
                 {"kind": "search_person_role", "query": "profile", "url": "", "person": p["name"]}],
             "claims": []},
            {"official_website": c["website"], "company_verdict": "supported",
             "company_status": "active", "actions": [], "claims": [p]},
        ]
        requests = []
        def requester(payload, key):
            requests.append(payload)
            return {"choices": [{"message": {"content": json.dumps(responses[len(requests)-1])}}],
                    "usage": {"cost": .01}}
        def searcher(query):
            if query == "profile":
                return [PublicSearchHit("Dwayne Sansone - Swift Medical | LinkedIn",
                    p["linkedin_url"], "Dwayne Sansone CEO at Swift Medical")], None
            return [PublicSearchHit("Leadership Team - Swift Medical", p["role_url"],
                "Swift Medical Dwayne Sansone Chief Executive Officer"),
                PublicSearchHit("Dwayne Sansone - Swift Medical | LinkedIn", p["linkedin_url"],
                "Dwayne Sansone CEO at Swift Medical")], None
        def fetcher(url):
            page = PageParser()
            page.raw = "<title>Swift Medical</title><h1>Swift Medical</h1>"
            page.final_url = url
            return page, ""
        with TemporaryDirectory() as directory, patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            path = Path(directory)
            decisions, summary = run_investigation([c], [], path, source_rows={5},
                searcher=searcher, fetcher=fetcher, requester=requester)
            self.assertEqual(summary["newly_accepted"], 1)
            self.assertEqual(summary["reported_cost_usd"], .02)
            self.assertEqual(len([x for x in decisions if x["decision"] == "accept"]), 1)
            self.assertTrue(json.loads((path / "investigation_records.json").read_text())[c["row_id"]]["completed"])
            decisions, replay = run_investigation([c], decisions, path, source_rows={5},
                searcher=searcher, fetcher=fetcher, requester=requester)
            self.assertEqual(len(requests), 2)
            self.assertEqual(replay["cache_hits"], 1)
            self.assertEqual(len(decisions), 1)

    def test_loop_recovers_blank_profile_from_targeted_search(self):
        c = company()
        p = claim(profile="")
        response = {"official_website": c["website"], "company_verdict": "supported",
                    "company_status": "active", "actions": [], "claims": [p]}
        def requester(payload, key):
            return {"choices": [{"message": {"content": json.dumps(response)}}],
                    "usage": {"cost": .01}}
        def searcher(query):
            if "site:linkedin.com/in/" in query:
                return [PublicSearchHit("Dwayne Sansone - Swift Medical | LinkedIn",
                    "https://www.linkedin.com/in/dwayne-sansone-2425a287",
                    "Dwayne Sansone Chief Executive Officer at Swift Medical")], None
            return [PublicSearchHit("Leadership Team - Swift Medical", p["role_url"],
                "Swift Medical Dwayne Sansone Chief Executive Officer")], None
        def fetcher(url):
            page = PageParser()
            page.raw = "<title>Swift Medical</title><h1>Swift Medical</h1>"
            page.final_url = url
            return page, ""
        with TemporaryDirectory() as directory, patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            root = Path(directory)
            (root / "luna_cache").mkdir()
            (root / "luna_cache" / "old.json").write_text(json.dumps({
                "row_id": c["row_id"], "requested_at": "2026-09-01",
                "usage": {"citations": [{"url": p["role_url"],
                    "title": "Leadership Team - Swift Medical",
                    "content": "Swift Medical Dwayne Sansone Chief Executive Officer"}]}}))
            decisions, summary = run_investigation([c], [], root / "pilot", source_rows={5},
                searcher=searcher, fetcher=fetcher, requester=requester)
        self.assertEqual(summary["newly_accepted"], 1)
        self.assertEqual(decisions[0]["linkedin_url"],
                         "https://www.linkedin.com/in/dwayne-sansone-2425a287")


if __name__ == "__main__":
    unittest.main()
