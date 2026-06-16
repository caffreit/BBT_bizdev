import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

import build_bbt_bizdev_workbook as pipeline


RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>NovaScan Health raises $24M Series A for AI imaging platform - MedTech Dive</title>
      <link>https://news.google.com/rss/articles/novascan</link>
      <description>NovaScan Health raised new funding for FDA-focused medical imaging AI.</description>
      <source>MedTech Dive</source>
      <pubDate>Thu, 11 Jun 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>NovaScan Health raises $24M Series A for AI imaging platform - MedTech Dive</title>
      <link>https://news.google.com/rss/articles/novascan</link>
      <description>Duplicate result from another query.</description>
      <source>MedTech Dive</source>
      <pubDate>Thu, 11 Jun 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>PulseDx receives FDA clearance for AI cardiac device - Fierce Biotech</title>
      <link>https://news.google.com/rss/articles/pulsedx</link>
      <description>PulseDx received FDA clearance for a clinical AI medical device.</description>
      <source>Fierce Biotech</source>
      <pubDate>Thu, 11 Jun 2026 13:00:00 GMT</pubDate>
    </item>
    <item>
      <title>ClearPath Medical wins innovation award - Local Health News</title>
      <link>https://news.google.com/rss/articles/clearpath</link>
      <description>ClearPath Medical was highlighted for a medical device prototype.</description>
      <source>Local Health News</source>
      <pubDate>Thu, 11 Jun 2026 14:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


class SearchAdapterTests(unittest.TestCase):
    def test_sources_include_50_vc_portfolio_pages(self):
        vc_sources = [source for source in pipeline.SOURCES if source.source_type == "VC portfolio"]

        self.assertEqual(len(vc_sources), 50)
        self.assertTrue(all(source.adapter == "vc_portfolio_page" for source in vc_sources))

    def test_sources_include_20_jobs_sources_with_dedicated_ats_adapters(self):
        job_sources = [source for source in pipeline.SOURCES if source.source_type == "Jobs"]
        adapters = {source.name: source.adapter for source in job_sources}

        self.assertEqual(len(job_sources), 20)
        self.assertEqual(adapters["Greenhouse job boards"], "greenhouse_jobs")
        self.assertEqual(adapters["Lever job boards"], "lever_jobs")
        self.assertEqual(adapters["Ashby job boards"], "ashby_jobs")
        self.assertEqual(adapters["Workable job boards"], "workable_jobs")
        self.assertEqual(adapters["SmartRecruiters job boards"], "smartrecruiters_jobs")
        self.assertEqual(adapters["Recruitee job boards"], "recruitee_jobs")
        self.assertEqual(sum(1 for source in job_sources if source.adapter == "jobs_page"), 14)

    def test_job_board_parsers_cover_supported_ats_shapes(self):
        greenhouse = pipeline.parse_greenhouse_jobs({"jobs": [{"title": "Quality Engineer", "absolute_url": "https://job/gh", "content": "<p>Medical device QA</p>"}]})
        lever = pipeline.parse_lever_jobs([{"text": "Regulatory Affairs Lead", "hostedUrl": "https://job/lever", "description": "FDA submissions"}])
        ashby = pipeline.parse_ashby_jobs({"jobs": [{"title": "Clinical AI Product Manager", "jobUrl": "https://job/ashby", "descriptionHtml": "<p>Digital health</p>"}]})
        workable = pipeline.parse_workable_jobs({"jobs": [{"title": "Design Assurance Engineer", "url": "https://job/workable", "description": "V&V"}]})
        smartrecruiters = pipeline.parse_smartrecruiters_jobs({"content": [{"name": "Medical Device QA Manager", "url": "https://job/sr", "description": "Quality systems"}]})
        recruitee = pipeline.parse_recruitee_jobs({"offers": [{"title": "Clinical Validation Lead", "careers_url": "https://job/recruitee", "description": "Diagnostics"}]})

        self.assertEqual([jobs[0].title for jobs in [greenhouse, lever, ashby, workable, smartrecruiters, recruitee]], [
            "Quality Engineer",
            "Regulatory Affairs Lead",
            "Clinical AI Product Manager",
            "Design Assurance Engineer",
            "Medical Device QA Manager",
            "Clinical Validation Lead",
        ])

    def test_job_board_adapter_creates_company_level_hiring_signal(self):
        source = pipeline.Source("Greenhouse job boards", "Jobs", "https://www.greenhouse.com/", "Global", "Medium", "Weekly", "Company careers page search", "Fixture", "greenhouse_jobs")
        registry = {
            "NovaScan Health": {
                "aliases": ["NovaScan Health"],
                "website": "https://novascan.example",
                "geography": "US",
                "product_type": "AI medical device",
                "job_boards": [{"platform": "greenhouse", "account": "novascan"}],
            }
        }
        fixture = {
            "jobs": [
                {"title": "Regulatory Affairs Manager", "absolute_url": "https://job/reg", "content": "<p>FDA medical device submissions</p>"},
                {"title": "Quality Engineer", "absolute_url": "https://job/qa", "content": "<p>Design controls and V&V</p>"},
            ]
        }

        with patch.object(pipeline, "COMPANY_REGISTRY", registry), patch.object(pipeline, "fetch_json_url", return_value=(fixture, None)):
            discovery_hits, trigger_events, result = pipeline.run_job_board_adapter(source, "greenhouse")

        self.assertEqual([hit.company for hit in discovery_hits], ["NovaScan Health"])
        self.assertEqual([event.trigger_type for event in trigger_events], ["Hiring signal"])
        self.assertIn("Regulatory Affairs Manager", discovery_hits[0].discovery_rationale)
        self.assertIn("Quality Engineer", trigger_events[0].trigger_event)
        self.assertIn("1/1 configured boards fetched", result)

    def test_job_board_adapter_ignores_irrelevant_engineering_without_health_context(self):
        source = pipeline.Source("Lever job boards", "Jobs", "https://www.lever.co/", "Global", "Medium", "Weekly", "Company careers page search", "Fixture", "lever_jobs")
        registry = {
            "GenericCo": {
                "aliases": ["GenericCo"],
                "website": "https://generic.example",
                "geography": "US",
                "product_type": "Workflow software",
                "job_boards": [{"platform": "lever", "account": "genericco"}],
            }
        }
        fixture = [{"text": "Software Engineer", "hostedUrl": "https://job/software", "description": "Build internal tools."}]

        with patch.object(pipeline, "COMPANY_REGISTRY", registry), patch.object(pipeline, "fetch_json_url", return_value=(fixture, None)):
            discovery_hits, trigger_events, result = pipeline.run_job_board_adapter(source, "lever")

        self.assertEqual(discovery_hits, [])
        self.assertEqual(trigger_events, [])
        self.assertIn("1 boards with no matching jobs", result)

    def test_job_board_adapter_reports_no_config(self):
        source = pipeline.Source("Ashby job boards", "Jobs", "https://www.ashbyhq.com/", "Global", "Medium", "Weekly", "Company careers page search", "Fixture", "ashby_jobs")

        with patch.object(pipeline, "COMPANY_REGISTRY", {}):
            discovery_hits, trigger_events, result = pipeline.run_job_board_adapter(source, "ashby")

        self.assertEqual(discovery_hits, [])
        self.assertEqual(trigger_events, [])
        self.assertIn("No registry companies configured", result)

    def test_parse_google_news_rss(self):
        results = pipeline.parse_google_news_rss(RSS_FIXTURE, "MedTech AI Funding")

        self.assertEqual(len(results), 4)
        self.assertEqual(results[0].query, "MedTech AI Funding")
        self.assertEqual(results[0].publisher, "MedTech Dive")
        self.assertEqual(results[0].link, "https://news.google.com/rss/articles/novascan")

    def test_search_evidence_extraction_classification_and_dedupe(self):
        source = pipeline.Source("Google News / web funding search", "News/search", "https://news.google.com/search", "US/EU/global", "High", "Weekly", "Google News RSS query", "Search fixture", "google_news_search")
        results = pipeline.parse_google_news_rss(RSS_FIXTURE, "MedTech AI Funding")
        discovery_hits, trigger_events = pipeline.build_google_news_evidence(source, results)

        self.assertEqual([hit.company for hit in discovery_hits], ["NovaScan Health", "PulseDx", "ClearPath Medical"])
        self.assertEqual([event.company for event in trigger_events], ["NovaScan Health", "PulseDx"])
        self.assertEqual(trigger_events[0].trigger_type, "Funding")
        self.assertEqual(trigger_events[1].trigger_type, "Regulatory clearance")
        self.assertIn("query: MedTech AI Funding", discovery_hits[0].matched_terms)

    def test_workbook_preserves_search_traceability(self):
        source = pipeline.Source("Google News / web funding search", "News/search", "https://news.google.com/search", "US/EU/global", "High", "Weekly", "Google News RSS query", "Search fixture", "google_news_search")
        results = pipeline.parse_google_news_rss(RSS_FIXTURE, "MedTech AI Funding")
        discovery_hits, search_triggers = pipeline.build_google_news_evidence(source, results)
        companies = pipeline.normalize_companies(discovery_hits)
        trigger_events = pipeline.attach_trigger_events(companies, search_triggers)
        pipeline.mark_primary_triggers(companies)

        with tempfile.TemporaryDirectory() as temp_dir:
            original_out = pipeline.OUT
            try:
                pipeline.OUT = Path(temp_dir) / "traceability.xlsx"
                workbook_path = pipeline.write_workbook(companies, discovery_hits, trigger_events, [["Google News / web funding search", "News/search", source.url, "Fetched", "fixture"]])
                wb = load_workbook(workbook_path)
            finally:
                pipeline.OUT = original_out

        discovery_row = list(wb["Discovery Hits"].iter_rows(min_row=2, values_only=True))[0]
        trigger_row = list(wb["Trigger Log"].iter_rows(min_row=2, values_only=True))[0]
        lead_rows = list(wb["Lead Intake"].iter_rows(min_row=2, values_only=True))
        novascan_lead = [row for row in lead_rows if row[0] == "NovaScan Health"][0]

        self.assertEqual(discovery_row[1], "Google News / web funding search: MedTech AI Funding")
        self.assertEqual(discovery_row[3], "https://news.google.com/rss/articles/novascan")
        self.assertEqual(trigger_row[4], "https://news.google.com/rss/articles/novascan")
        self.assertEqual(novascan_lead[16], "Verified trigger")

    def test_workbook_includes_accelerator_metadata_columns(self):
        hit = pipeline.DiscoveryHit(
            company="NovaScan Health",
            source_name="Fixture Accelerator",
            source_type="Accelerator",
            discovery_url="https://example.com/novascan",
            discovery_rationale="Fixture accelerator extraction.",
            product_type="Diagnostics / imaging",
            accelerator_program="Fixture Accelerator",
            cohort_label="Fixture 2026 cohort",
            cohort_year="2026",
            category_or_track="Diagnostics",
            company_description="AI imaging triage for hospitals.",
        )
        companies = pipeline.normalize_companies([hit])

        with tempfile.TemporaryDirectory() as temp_dir:
            original_out = pipeline.OUT
            try:
                pipeline.OUT = Path(temp_dir) / "metadata.xlsx"
                workbook_path = pipeline.write_workbook(companies, [hit], [], [["Fixture Accelerator", "Accelerator", hit.discovery_url, "Fetched", "fixture"]])
                wb = load_workbook(workbook_path)
            finally:
                pipeline.OUT = original_out

        discovery_headers = [cell.value for cell in wb["Discovery Hits"][1]]
        lead_headers = [cell.value for cell in wb["Lead Intake"][1]]
        discovery_row = list(wb["Discovery Hits"].iter_rows(min_row=2, values_only=True))[0]

        self.assertIn("Accelerator program", discovery_headers)
        self.assertIn("Company description", lead_headers)
        self.assertEqual(discovery_row[9], "Fixture Accelerator")
        self.assertEqual(discovery_row[11], "2026")

    def test_digitalhealth_london_adapter_paginates_directory_cards(self):
        source = pipeline.Source("DigitalHealth.London Accelerator", "Accelerator", "https://digitalhealth.london/programmes/accelerator/", "UK", "High", "Annual", "Cohort extraction", "NHS-facing digital health.", "digitalhealth_london")
        page_1 = """
        <html><body>
          <a href="/innovation-directory/profile/alpha-care">Alpha Care Company Remote monitoring platform for NHS pathways.</a>
          <a href="/innovation-directory/profile/beta-dx">BetaDx Company Diagnostic decision support for urgent care.</a>
          <a href="https://digitalhealth.london/innovation-directory/companies/page/2">Older posts</a>
        </body></html>
        """
        page_2 = '<html><body><a href="/innovation-directory/profile/gamma-ehr">Gamma EHR Company EHR workflow automation for hospital teams.</a></body></html>'

        with patch.object(pipeline, "fetch_raw_text", side_effect=[(page_1, None), (page_2, None)]):
            discovery_hits, trigger_events, result = pipeline.run_digitalhealth_london(source)

        self.assertEqual([hit.company for hit in discovery_hits], ["Alpha Care", "BetaDx", "Gamma EHR"])
        self.assertIn("Remote monitoring", discovery_hits[0].company_description)
        self.assertEqual(len(trigger_events), 3)
        self.assertIn("2 directory pages", result)

    def test_digitalhealth_london_parser_can_enrich_from_profile_html(self):
        source = pipeline.Source("DigitalHealth.London Accelerator", "Accelerator", "https://digitalhealth.london/programmes/accelerator/", "UK", "High", "Annual", "Cohort extraction", "NHS-facing digital health.", "digitalhealth_london")
        page = '<html><body><a href="/innovation-directory/profile/alpha-care">Alpha Care Company Remote monitoring.</a></body></html>'
        profile_url = "https://digitalhealth.london/innovation-directory/profile/alpha-care"
        profile_html = '<html><head><meta property="og:description" content="Remote monitoring platform for NHS pathways."></head><body>Sector: Digital health Technology: AI Cohort 2026</body></html>'

        hits = pipeline.parse_digitalhealth_london_page(source, page, "https://digitalhealth.london/innovation-directory/companies", {profile_url: profile_html})

        self.assertEqual(hits[0].cohort_year, "2026")
        self.assertIn("Digital health", hits[0].category_or_track)

    def test_medtech_innovator_adapter_flags_incomplete_current_cohort(self):
        source = pipeline.Source("MedTech Innovator", "Accelerator", "https://medtechinnovator.org/2026cohort/", "US/EU/global", "High", "Quarterly", "Cohort extraction", "Medtech source.", "medtech_innovator")
        cohort_html = """
        <html><body>
          <p>65 companies selected for the 2026 cohort.</p>
          <a href="https://pro.innovator.org/showcase/2026cohort">Showcase</a>
        </body></html>
        """
        showcase_html = """
        <html><body>
          <h2>Diagnostics</h2>
          <a href="https://example.com/heartscan">HeartScan</a>
          <a href="https://example.com/neuroflow">NeuroFlowx</a>
        </body></html>
        """

        with patch.object(pipeline, "fetch_raw_text", side_effect=[(cohort_html, None), (showcase_html, None)]), patch.object(pipeline, "fetch_medtech_innovator_pory_records", return_value=([], [])):
            discovery_hits, _, result = pipeline.run_medtech_innovator(source)

        self.assertEqual([hit.company for hit in discovery_hits], ["HeartScan", "NeuroFlowx"])
        self.assertEqual(discovery_hits[0].cohort_year, "2026")
        self.assertIn("Diagnostics", discovery_hits[0].category_or_track)
        self.assertIn("INCOMPLETE current-cohort extraction", result)

    def test_medtech_innovator_adapter_extracts_pory_portfolio_records(self):
        source = pipeline.Source("MedTech Innovator", "Accelerator", "https://medtechinnovator.org/2026cohort/", "US/EU/global", "High", "Quarterly", "Cohort extraction", "Medtech source.", "medtech_innovator")
        records = [
            {
                "id": "rec1",
                "fields": {
                    "Company": "2morrow",
                    "Website": "https://www.2morrowinc.com/",
                    "Year.": "2017",
                    "Program.": "Accelerator-US",
                    "Product Short Description": "Clinically-tested mobile behavior change platform.",
                    "Thematic Categories": ["Digital Therapeutics", "Chronic Disease Management"],
                    "Company Country/Territory (Old Field)": "United States",
                },
            }
        ]

        hits = pipeline.parse_medtech_innovator_pory_records(source, records)

        self.assertEqual(hits[0].company, "2morrow")
        self.assertEqual(hits[0].cohort_year, "2017")
        self.assertEqual(hits[0].website, "https://www.2morrowinc.com/")
        self.assertIn("Digital Therapeutics", hits[0].category_or_track)

    def test_mayo_accelerate_adapter_extracts_descriptions_from_headings(self):
        source = pipeline.Source("Mayo Clinic Platform Accelerate", "Accelerator", "https://www.mayoclinicplatform.org/accelerate/", "US/global", "High", "Quarterly", "Cohort extraction", "AI digital health.", "mayo_accelerate")
        html = """
        <html><body>
          <h2>ClinicAI</h2><p>AI platform for clinical workflow automation and patient risk triage.</p>
          <h2>VitalsCloud</h2><p>Remote monitoring software for chronic care teams.</p>
        </body></html>
        """

        hits = pipeline.parse_mayo_accelerate_page(source, html, "https://example.com/accelerate-2026")

        self.assertEqual([hit.company for hit in hits], ["ClinicAI", "VitalsCloud"])
        self.assertEqual(hits[0].cohort_year, "2026")
        self.assertIn("clinical workflow", hits[0].company_description)

    def test_mayo_accelerate_adapter_uses_live_reader_when_direct_fetch_is_blocked(self):
        source = pipeline.Source("Mayo Clinic Platform Accelerate", "Accelerator", "https://www.mayoclinicplatform.org/accelerate/", "US/global", "High", "Quarterly", "Cohort extraction", "AI digital health.", "mayo_accelerate")
        reader_markdown = """
        Title: Accelerate Cohort Landing Page - Mayo Clinic Platform
        URL Source: https://www.mayoclinicplatform.org/focus-areas/digital-health/accelerate/accelerate-cohort-landing-page/
        Markdown Content:
        February 2026
        ## Meet the Newest Cohort of Innovative Health Tech Startups

        [![Image 1](https://cdn.example.com/100ms.jpg)](https://100ms.ai/)
        **100ms** builds AI agents for patient access, helping patients automate intake and scheduling for specialty practices.

        ![Image 2](https://cdn.example.com/wfh.jpg)
        "WFH: Wellness from Home" is a continuous health monitoring platform for elderly remote patient monitoring.
        """

        with patch.object(pipeline, "fetch_raw_text", side_effect=[("", "HTTP Error 403: Forbidden"), (reader_markdown, None)]):
            discovery_hits, trigger_events, result = pipeline.run_mayo_accelerate(source)

        self.assertEqual([hit.company for hit in discovery_hits], ["100ms", "WFH: Wellness from Home"])
        self.assertEqual(discovery_hits[0].website, "https://100ms.ai/")
        self.assertIn("live reader page", discovery_hits[0].matched_terms)
        self.assertEqual(len(trigger_events), len(discovery_hits))
        self.assertIn("HTTP Error 403", result)

    def test_mayo_accelerate_adapter_reports_incomplete_when_all_live_fetches_fail(self):
        source = pipeline.Source("Mayo Clinic Platform Accelerate", "Accelerator", "https://www.mayoclinicplatform.org/accelerate/", "US/global", "High", "Quarterly", "Cohort extraction", "AI digital health.", "mayo_accelerate")

        with patch.object(pipeline, "fetch_raw_text", return_value=("", "HTTP Error 403: Forbidden")):
            discovery_hits, trigger_events, result = pipeline.run_mayo_accelerate(source)

        self.assertEqual(discovery_hits, [])
        self.assertEqual(trigger_events, [])
        self.assertIn("INCOMPLETE Mayo extraction", result)

    def test_eit_health_catapult_adapter_extracts_winners_and_tracks(self):
        source = pipeline.Source("EIT Health Catapult", "Accelerator", "https://eithealth.eu/programmes/catapult/", "EU", "High", "Annual", "Finalist extraction", "European health startups.", "eit_health_catapult")
        html = """
        <html><body>
          <h2>Digital Health winners</h2>
          <img alt="DeepEye" src="/deepeye.jpg">
          <h2>MedTech winners</h2>
          <a href="https://example.com/acorai">Acorai</a>
        </body></html>
        """

        hits = pipeline.parse_eit_health_catapult_page(source, html, "https://eithealth.eu/programmes/catapult/")

        self.assertEqual([hit.company for hit in hits], ["DeepEye", "Acorai"])
        self.assertIn("Digital Health", hits[0].category_or_track)
        self.assertIn("MedTech", hits[1].category_or_track)

    def test_generic_accelerator_adapter_is_skipped(self):
        source = pipeline.Source("Illumina Accelerator", "Accelerator", "https://www.illumina.com/science/accelerator.html", "US/UK", "High", "Annual", "Portfolio extraction", "Genomics startups.", "accelerator_page")

        with patch.object(pipeline, "fetch_raw_text") as fetch_raw_text:
            discovery_hits, trigger_events, run_log = pipeline.run_discovery([source])

        fetch_raw_text.assert_not_called()
        self.assertEqual(discovery_hits, [])
        self.assertEqual(trigger_events, [])
        self.assertEqual(run_log[0][3], "Skipped")
        self.assertIn("No source-specific accelerator adapter", run_log[0][4])
        self.assertEqual(pipeline.adapter_inventory_label(source), "Manual/not implemented")

    def test_source_page_adapter_extracts_candidates_and_triggers(self):
        source = pipeline.Source("Fixture Accelerator", "Accelerator", "https://example.com/cohort", "US/global", "High", "Annual", "Cohort extraction", "AI medical device startups.", "accelerator_page")
        html = """
        <html><body>
          <a href="/companies/nova-scan">NovaScan Health</a>
          <a href="/about">About</a>
          <a href="/companies/pulse-dx">PulseDx</a>
        </body></html>
        """

        discovery_hits, trigger_events = pipeline.build_source_page_evidence(source, html)

        self.assertEqual([hit.company for hit in discovery_hits], ["NovaScan Health", "PulseDx"])
        self.assertEqual([event.trigger_type for event in trigger_events], ["Accelerator/cohort", "Accelerator/cohort"])
        self.assertEqual(discovery_hits[0].discovery_url, "https://example.com/companies/nova-scan")

    def test_source_page_adapter_uses_known_registry_metadata(self):
        source = pipeline.Source("Fixture VC", "VC portfolio", "https://example.com/portfolio", "US", "High", "Monthly", "Portfolio extraction", "Medtech portfolio.", "vc_portfolio_page")
        html = "<html><body><p>Portfolio includes Aidoc and other clinical AI companies.</p></body></html>"

        discovery_hits, trigger_events = pipeline.build_source_page_evidence(source, html)

        self.assertEqual(discovery_hits[0].company, "Aidoc")
        self.assertEqual(discovery_hits[0].website, "https://www.aidoc.com/")
        self.assertEqual(trigger_events[0].trigger_type, "Investor backing")

    def test_regulatory_adapter_does_not_extract_navigation_links(self):
        source = pipeline.Source("Fixture FDA", "Regulatory database", "https://example.com/fda", "US", "High", "Monthly", "Regulatory extraction", "FDA device database.", "regulatory_page")
        html = """
        <html><body>
          <a href="#search_form">Skip to Search</a>
          <a href="/medical-devices">Medical Devices</a>
          <p>Aidoc appears in this regulatory listing.</p>
        </body></html>
        """

        discovery_hits, trigger_events = pipeline.build_source_page_evidence(source, html)

        self.assertEqual([hit.company for hit in discovery_hits], ["Aidoc"])
        self.assertEqual(trigger_events[0].trigger_type, "Regulatory listing")

    def test_source_page_adapter_rejects_directory_action_links(self):
        source = pipeline.Source("Fixture Conference", "Conference", "https://example.com", "Global", "High", "Annual", "Exhibitor extraction", "Medtech conference.", "conference_page")
        html = """
        <html><body>
          <a href="/company-list">Company List</a>
          <a href="/become-an-exhibitor">Become an Exhibitor</a>
          <a href="/exhibitors/nova-scan">NovaScan Health</a>
        </body></html>
        """

        discovery_hits, _ = pipeline.build_source_page_evidence(source, html)

        self.assertEqual([hit.company for hit in discovery_hits], ["NovaScan Health"])

    def test_source_page_adapter_rejects_team_links(self):
        source = pipeline.Source("Fixture VC", "VC portfolio", "https://example.com", "US", "High", "Monthly", "Portfolio extraction", "Medtech portfolio.", "vc_portfolio_page")
        html = """
        <html><body>
          <a href="/team/jane-founder">Core Jane Founder</a>
          <a href="/portfolio/nova-scan">NovaScan Health</a>
        </body></html>
        """

        discovery_hits, _ = pipeline.build_source_page_evidence(source, html)

        self.assertEqual([hit.company for hit in discovery_hits], ["NovaScan Health"])

    def test_source_page_adapter_rejects_person_names_on_portfolio_paths(self):
        source = pipeline.Source("Fixture VC", "VC portfolio", "https://example.com", "US", "High", "Monthly", "Portfolio extraction", "Medtech portfolio.", "vc_portfolio_page")
        html = """
        <html><body>
          <a href="/portfolio/andrew-kress">Andrew Kress</a>
          <a href="/portfolio/brightheart">BrightHeart</a>
        </body></html>
        """

        discovery_hits, _ = pipeline.build_source_page_evidence(source, html)

        self.assertEqual([hit.company for hit in discovery_hits], ["BrightHeart"])

    def test_yc_healthcare_adapter_paginates_and_sorts_by_launch_date(self):
        source = pipeline.Source("Y Combinator Healthcare", "Accelerator", "https://www.ycombinator.com/companies", "US/global", "Medium", "Quarterly", "YC Algolia company directory query", "Healthcare startups.", "yc_healthcare")
        pages = [
            {
                "nbHits": 3,
                "nbPages": 2,
                "hits": [
                    {"name": "Older Health", "slug": "older-health", "website": "https://older.example", "one_liner": "Healthcare workflow", "all_locations": "US", "batch": "Winter 2024", "tags": ["Healthcare"], "launched_at": 100},
                    {"name": "Newest Health", "slug": "newest-health", "website": "https://newest.example", "one_liner": "AI clinic ops", "all_locations": "UK", "batch": "Summer 2026", "tags": ["Healthcare", "AI"], "launched_at": 300},
                ],
            },
            {
                "nbHits": 3,
                "nbPages": 2,
                "hits": [
                    {"name": "Middle Health", "slug": "middle-health", "website": "https://middle.example", "one_liner": "Digital health", "all_locations": "EU", "batch": "Summer 2025", "tags": ["Healthcare"], "launched_at": 200},
                ],
            },
        ]

        with patch.object(pipeline, "fetch_json", side_effect=[(pages[0], None), (pages[1], None)]):
            discovery_hits, trigger_events, result = pipeline.run_yc_healthcare(source)

        self.assertEqual([hit.company for hit in discovery_hits], ["Newest Health", "Middle Health", "Older Health"])
        self.assertEqual(discovery_hits[0].discovery_url, "https://www.ycombinator.com/companies/newest-health")
        self.assertEqual(len(trigger_events), 3)
        self.assertIn("3 matches", result)


if __name__ == "__main__":
    unittest.main()
