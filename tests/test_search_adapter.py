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
    def test_add_hyperlinks_trims_excel_relationship_targets(self):
        wb = pipeline.Workbook()
        ws = wb.active
        ws.append(["Website"])
        ws.append(["http://www.delee.co    "])

        pipeline.add_hyperlinks(ws, [1])

        self.assertEqual(ws["A2"].value, "http://www.delee.co")
        self.assertEqual(ws["A2"].hyperlink.target, "http://www.delee.co")

    def test_sources_include_52_vc_portfolio_pages(self):
        vc_sources = [source for source in pipeline.SOURCES if source.source_type == "VC portfolio"]

        self.assertEqual(len(vc_sources), 52)
        self.assertTrue(all(source.adapter for source in vc_sources))
        adapters = {source.name: source.adapter for source in vc_sources}
        self.assertEqual(adapters["Fountain Healthcare Partners portfolio"], "fountain_healthcare")
        self.assertEqual(adapters["Seroba Life Sciences portfolio"], "seroba_life_sciences")
        self.assertEqual(adapters["Atlantic Bridge portfolio"], "atlantic_bridge")

    def test_priority_ireland_sources_use_dedicated_adapters(self):
        adapters = {source.name: source.adapter for source in pipeline.SOURCES}

        self.assertEqual(adapters["BioInnovate Ireland"], "bioinnovate_ireland")
        self.assertEqual(adapters["ARC Hub for HealthTech"], "arc_hub_healthtech")
        self.assertEqual(adapters["Health Innovation Hub Ireland"], "health_innovation_hub_ireland")
        self.assertEqual(adapters["Dogpatch Labs / NDRC"], "dogpatch_ndrc")
        self.assertEqual(adapters["Fountain Healthcare Partners portfolio"], "fountain_healthcare")
        self.assertEqual(adapters["Seroba Life Sciences portfolio"], "seroba_life_sciences")
        self.assertEqual(adapters["Atlantic Bridge portfolio"], "atlantic_bridge")

    def test_sources_include_20_jobs_sources_with_dedicated_ats_adapters(self):
        job_sources = [source for source in pipeline.SOURCES if source.source_type == "Jobs"]
        adapters = {source.name: source.adapter for source in job_sources}

        self.assertEqual(len(job_sources), 20)
        self.assertIsNone(adapters["Greenhouse job boards"])
        self.assertIsNone(adapters["Wellfound jobs"])
        self.assertEqual(adapters["Lever job boards"], "lever_jobs")
        self.assertEqual(adapters["Ashby job boards"], "ashby_jobs")
        self.assertEqual(adapters["Workable job boards"], "workable_jobs")
        self.assertEqual(adapters["SmartRecruiters job boards"], "smartrecruiters_jobs")
        self.assertEqual(adapters["Recruitee job boards"], "recruitee_jobs")
        self.assertEqual(adapters["Built In jobs"], "builtin_jobs")
        self.assertEqual(adapters["BioSpace jobs"], "biospace_jobs")
        self.assertEqual(adapters["NHS Jobs"], "nhs_jobs")
        self.assertEqual(sum(1 for source in job_sources if source.adapter == "jobs_page"), 10)

    def test_sources_include_university_spinout_sources_by_geo(self):
        spinout_sources = [source for source in pipeline.SOURCES if source.source_type == "University/spinout"]
        names = {source.name for source in spinout_sources}
        adapters = {source.name: source.adapter for source in spinout_sources}

        self.assertEqual(len(spinout_sources), 32)
        self.assertEqual(
            {name for name, adapter in adapters.items() if adapter},
            {
                "Trinity College Dublin spinouts",
                "UCD spinouts",
                "University of Oxford spinouts",
                "University of Cambridge spinouts",
                "Imperial College London spinouts",
            },
        )
        self.assertIn("University/spinout", pipeline.DISCOVERY_TERMS)
        self.assertEqual(pipeline.SOURCE_TRIGGER_TYPES["University/spinout"], "University/spinout origin")
        for name in [
            "Trinity College Dublin spinouts",
            "RCSI spinouts",
            "UCD spinouts",
            "University of Galway spinouts",
            "University of Limerick spinouts",
            "University College Cork spinouts",
            "University of Oxford spinouts",
            "University of Cambridge spinouts",
            "Imperial College London spinouts",
            "King's College London spinouts",
            "UCL spinouts",
            "University of Edinburgh spinouts",
            "University of Manchester spinouts",
            "University of Leeds spinouts",
            "University of Sheffield spinouts",
            "ETH Zurich spinouts",
            "KU Leuven spinouts",
            "EPFL spinouts",
            "Technical University of Denmark spinouts",
            "TU Delft spinouts",
            "Karolinska Institutet spinouts",
            "Stanford spinouts",
            "MIT spinouts",
            "Harvard spinouts",
            "Johns Hopkins spinouts",
            "Mayo Clinic spinouts",
            "UC Berkeley spinouts",
            "UCSF spinouts",
            "University of Toronto spinouts",
        ]:
            self.assertIn(name, names)

    def test_google_news_queries_include_university_spinout_terms(self):
        expected_count = len(pipeline.CORE_SEARCH_QUERIES) + len(pipeline.UNIVERSITY_SPINOUT_SEARCH_UNIVERSITIES) * len(pipeline.UNIVERSITY_SPINOUT_SEARCH_PATTERNS)

        self.assertEqual(len(pipeline.SEARCH_QUERIES), expected_count)
        self.assertIn('"Trinity College Dublin" spinout medical device', pipeline.SEARCH_QUERIES)
        self.assertIn('"University of Oxford" spinout digital health', pipeline.SEARCH_QUERIES)
        self.assertIn('"UCL" startup healthcare', pipeline.SEARCH_QUERIES)
        self.assertIn('"ETH Zurich" spinout medtech', pipeline.SEARCH_QUERIES)
        self.assertIn('"TU Delft" commercialisation health startup', pipeline.SEARCH_QUERIES)
        self.assertIn('"University of Toronto" startup "medical device"', pipeline.SEARCH_QUERIES)

    def test_university_spinout_adapter_extracts_candidate_company_links(self):
        source = pipeline.Source("Trinity College Dublin spinouts", "University/spinout", "https://www.tcd.ie/innovation/", "Ireland", "High", "Quarterly", "Spinout extraction", "AI health and medtech spinouts.", "tcd_spinouts")
        html = """
        <html><body>
          <a href="/innovation/spinout-companies/retina-ai/">RetinaAI Health</a>
          <a href="/innovation/news/2026/new-healthtech-start-up-launches/">New Healthtech Start-up Launches</a>
          <a href="/innovation/contact/">Contact</a>
        </body></html>
        """

        discovery_hits, trigger_events = pipeline.build_university_spinout_evidence(source, html)

        self.assertEqual([hit.company for hit in discovery_hits], ["RetinaAI Health"])
        self.assertEqual(discovery_hits[0].source_type, "University/spinout")
        self.assertEqual(trigger_events[0].trigger_type, "University/spinout origin")

    def test_priority_university_spinout_adapter_scans_configured_pages(self):
        source = pipeline.Source("UCD spinouts", "University/spinout", "https://www.ucd.ie/innovation/", "Ireland", "High", "Quarterly", "Spinout extraction", "Medtech and digital health spinouts.", "ucd_spinouts")
        pages = [
            ('<a href="/innovation/startups/ourstart-upcommunity/clinicflow/">ClinicFlow Health</a>', None),
            ('<a href="/innovation/news/2026/pulsedx-spinout/">PulseDx</a>', None),
            ("", "HTTP Error 404: Not Found"),
        ]

        with patch.object(pipeline, "fetch_raw_text", side_effect=pages):
            discovery_hits, trigger_events, result = pipeline.run_university_spinout_pages(source)

        self.assertEqual([hit.company for hit in discovery_hits], ["ClinicFlow Health", "PulseDx"])
        self.assertEqual(len(trigger_events), 2)
        self.assertIn("3 university spinout pages", result)
        self.assertIn("HTTP Error 404", result)

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

    def test_greenhouse_search_parser_extracts_job_urls_and_tokens(self):
        html = """
        <html><body>
          <a href="https://boards.greenhouse.io/novascan/jobs/123">Regulatory Affairs Manager</a>
          <a href="/url?q=https%3A%2F%2Fboards.greenhouse.io%2Fpulsedx%2Fjobs%2F456">Quality Engineer</a>
          https://job-boards.greenhouse.io/clearpath/jobs/789
        </body></html>
        """

        urls = pipeline.extract_greenhouse_job_urls(html)

        self.assertEqual(
            [pipeline.greenhouse_board_token_from_url(url) for url in urls],
            ["novascan", "pulsedx", "clearpath"],
        )

    def test_greenhouse_discovery_creates_company_level_hiring_signal(self):
        source = pipeline.Source("Greenhouse job boards", "Jobs", "https://www.greenhouse.com/", "Global", "Medium", "Weekly", "Company careers page search", "Fixture", "greenhouse_jobs")
        search_html = """
        <html><body>
          <a href="https://boards.greenhouse.io/novascan/jobs/123">Regulatory Affairs Manager</a>
          <a href="https://boards.greenhouse.io/novascan/jobs/456">Quality Engineer</a>
        </body></html>
        """
        board_fixture = {"name": "NovaScan Health", "content": "<p>AI imaging company</p>"}
        jobs_fixture = {
            "jobs": [
                {"title": "Regulatory Affairs Manager", "absolute_url": "https://job/reg", "content": "<p>FDA medical device submissions</p>"},
                {"title": "Quality Engineer", "absolute_url": "https://job/qa", "content": "<p>Design controls and V&V</p>"},
            ]
        }

        with patch.object(pipeline, "fetch_raw_text", return_value=(search_html, None)), patch.object(pipeline, "fetch_json_url", side_effect=[(board_fixture, None), (jobs_fixture, None)]):
            discovery_hits, trigger_events, result = pipeline.run_greenhouse_discovery(source, ["fixture query"])

        self.assertEqual([hit.company for hit in discovery_hits], ["NovaScan Health"])
        self.assertEqual([event.trigger_type for event in trigger_events], ["Hiring signal"])
        self.assertIn("Regulatory Affairs Manager", discovery_hits[0].discovery_rationale)
        self.assertIn("Quality Engineer", trigger_events[0].trigger_event)
        self.assertIn("1 search queries", result)
        self.assertIn("1 board tokens fetched", result)

    def test_greenhouse_discovery_ignores_irrelevant_jobs(self):
        source = pipeline.Source("Greenhouse job boards", "Jobs", "https://www.greenhouse.com/", "Global", "Medium", "Weekly", "Company careers page search", "Fixture", "greenhouse_jobs")
        search_html = '<a href="https://boards.greenhouse.io/genericco/jobs/123">Software Engineer</a>'
        board_fixture = {"name": "GenericCo"}
        jobs_fixture = {"jobs": [{"title": "Software Engineer", "absolute_url": "https://job/software", "content": "<p>Build internal tools.</p>"}]}

        with patch.object(pipeline, "fetch_raw_text", return_value=(search_html, None)), patch.object(pipeline, "fetch_json_url", side_effect=[(board_fixture, None), (jobs_fixture, None)]):
            discovery_hits, trigger_events, result = pipeline.run_greenhouse_discovery(source, ["fixture query"])

        self.assertEqual(discovery_hits, [])
        self.assertEqual(trigger_events, [])
        self.assertIn("1 boards with no matching jobs", result)

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

    def test_parse_biospace_jobs_extracts_company_role_and_url(self):
        html = """
        <ul id="listing" class="lister cf block">
          <li class="lister__item cf" id="item-3052525">
            <div class="lister__details cf js-clickable">
              <h3 class="lister__header"><a href="/job/3052525/manager-regulatory-affairs/"><span>Manager, Regulatory Affairs</span></a></h3>
              <ul class="lister__meta">
                <li class="lister__meta-item lister__meta-item--location">Boca Raton, FL</li>
                <li class="lister__meta-item lister__meta-item--recruiter">ADMA Biologics</li>
              </ul>
              <p class="lister__description js-clamp-2">FDA medical device regulatory submissions.</p>
            </div>
          </li>
        </ul>
        """

        leads = pipeline.parse_biospace_jobs(html, "https://jobs.biospace.com/jobs/?keywords=regulatory+affairs", "regulatory affairs")

        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].company, "ADMA Biologics")
        self.assertEqual(leads[0].posting.title, "Manager, Regulatory Affairs")
        self.assertEqual(leads[0].posting.url, "https://jobs.biospace.com/job/3052525/manager-regulatory-affairs/")

    def test_biospace_adapter_discovers_companies_from_role_search(self):
        source = pipeline.Source("BioSpace jobs", "Jobs", "https://www.biospace.com/jobs/", "US/global", "High", "Weekly", "BioSpace role search", "Fixture", "biospace_jobs")
        html = """
        <ul id="listing" class="lister cf block">
          <li class="lister__item cf" id="item-1">
            <div class="lister__details cf js-clickable">
              <h3 class="lister__header"><a href="/job/1/regulatory-affairs-manager/"><span>Regulatory Affairs Manager</span></a></h3>
              <ul class="lister__meta">
                <li class="lister__meta-item lister__meta-item--location">Boston, MA</li>
                <li class="lister__meta-item lister__meta-item--recruiter">NovaScan Health</li>
              </ul>
              <p class="lister__description js-clamp-2">FDA medical device and diagnostic submissions.</p>
            </div>
          </li>
          <li class="lister__item cf" id="item-2">
            <div class="lister__details cf js-clickable">
              <h3 class="lister__header"><a href="/job/2/software-engineer/"><span>Software Engineer</span></a></h3>
              <ul class="lister__meta">
                <li class="lister__meta-item lister__meta-item--location">Remote</li>
                <li class="lister__meta-item lister__meta-item--recruiter">GenericCo</li>
              </ul>
              <p class="lister__description js-clamp-2">Build internal tools.</p>
            </div>
          </li>
        </ul>
        """

        with patch.object(pipeline, "fetch_raw_text", return_value=(html, None)):
            discovery_hits, trigger_events, result = pipeline.run_biospace_jobs(source, ["regulatory affairs"])

        self.assertEqual([hit.company for hit in discovery_hits], ["NovaScan Health"])
        self.assertEqual([event.trigger_type for event in trigger_events], ["Hiring signal"])
        self.assertIn("Regulatory Affairs Manager", discovery_hits[0].discovery_rationale)
        self.assertIn("1 search queries", result)

    def test_parse_builtin_jobs_extracts_company_role_and_url(self):
        html = """
        <div id="job-card-9668948" data-id="job-card">
          <a href="/company/optum" data-id="company-title"><span>Optum</span></a>
          <h2><a href="/job/senior-director-actuarial-regulatory-affairs-pricing-underwriting/9668948" data-id="job-card-title">Senior Director, Actuarial &amp; Regulatory Affairs</a></h2>
          <i class="fa-regular fa-location-dot"></i></div><div><span class="font-barlow text-gray-04">Dublin, IRL</span></div>
        </div>
        """

        leads = pipeline.parse_builtin_jobs(html, "https://builtin.com/jobs?search=regulatory+affairs", "regulatory affairs")

        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].company, "Optum")
        self.assertEqual(leads[0].posting.title, "Senior Director, Actuarial & Regulatory Affairs")
        self.assertEqual(leads[0].posting.url, "https://builtin.com/job/senior-director-actuarial-regulatory-affairs-pricing-underwriting/9668948")

    def test_builtin_adapter_discovers_companies_from_role_search(self):
        source = pipeline.Source("Built In jobs", "Jobs", "https://builtin.com/jobs", "US", "Medium", "Weekly", "Built In role search", "Technology startup hiring signals, including healthtech and AI companies.", "builtin_jobs")
        html = """
        <div id="job-card-1" data-id="job-card">
          <a href="/company/pulsedx" data-id="company-title"><span>PulseDx</span></a>
          <h2><a href="/job/quality-engineer-healthcare/1" data-id="job-card-title">Quality Engineer, Healthcare AI</a></h2>
          <i class="fa-regular fa-location-dot"></i></div><div><span class="font-barlow text-gray-04">Remote</span></div>
        </div>
        <div id="job-card-2" data-id="job-card">
          <a href="/company/genericco" data-id="company-title"><span>GenericCo</span></a>
          <h2><a href="/job/account-executive/2" data-id="job-card-title">Account Executive</a></h2>
        </div>
        """

        with patch.object(pipeline, "fetch_raw_text", return_value=(html, None)):
            discovery_hits, trigger_events, result = pipeline.run_builtin_jobs(source, ["quality engineer"])

        self.assertEqual([hit.company for hit in discovery_hits], ["PulseDx"])
        self.assertEqual([event.trigger_type for event in trigger_events], ["Hiring signal"])
        self.assertIn("Quality Engineer", discovery_hits[0].discovery_rationale)
        self.assertIn("1 search queries", result)

    def test_parse_nhs_jobs_extracts_employer_role_and_url(self):
        html = """
        <ul class="nhsuk-list search-results">
          <li class="nhsuk-list-panel search-result" data-test="search-result">
            <h2><a href="/candidate/jobadvert/C9444-26-0330?keyword=clinical%20safety&amp;language=en" data-test="search-result-job-title">Clinical Safety Officer</a></h2>
            <div class="nhsuk-u-margin-bottom-4" data-test="search-result-location">
              <h3>Coventry and Warwickshire Partnership Trust
                <div class="location-font-size">Coventry CV6 6NY</div>
              </h3>
            </div>
            <li data-test="search-result-jobType">Contract type: <strong>Fixed-Term</strong></li>
          </li>
        </ul>
        """

        leads = pipeline.parse_nhs_jobs(html, "https://www.jobs.nhs.uk/candidate/search/results?keyword=clinical+safety", "clinical safety")

        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].company, "Coventry and Warwickshire Partnership Trust")
        self.assertEqual(leads[0].posting.title, "Clinical Safety Officer")
        self.assertEqual(leads[0].posting.url, "https://www.jobs.nhs.uk/candidate/jobadvert/C9444-26-0330?keyword=clinical%20safety&language=en")

    def test_nhs_adapter_discovers_provider_organisations_from_role_search(self):
        source = pipeline.Source("NHS Jobs", "Jobs", "https://www.jobs.nhs.uk/", "UK", "Medium", "Weekly", "NHS role search", "Fixture", "nhs_jobs")
        html = """
        <ul class="nhsuk-list search-results">
          <li class="nhsuk-list-panel search-result" data-test="search-result">
            <h2><a href="/candidate/jobadvert/C1" data-test="search-result-job-title">Clinical Safety Officer</a></h2>
            <div data-test="search-result-location"><h3>North Example NHS Trust<div class="location-font-size">London</div></h3></div>
          </li>
          <li class="nhsuk-list-panel search-result" data-test="search-result">
            <h2><a href="/candidate/jobadvert/C2" data-test="search-result-job-title">Catering Assistant</a></h2>
            <div data-test="search-result-location"><h3>Generic Hospital<div class="location-font-size">Leeds</div></h3></div>
          </li>
        </ul>
        """

        with patch.object(pipeline, "fetch_raw_text", return_value=(html, None)):
            discovery_hits, trigger_events, result = pipeline.run_nhs_jobs(source, ["clinical safety"])

        self.assertEqual([hit.company for hit in discovery_hits], ["North Example NHS Trust"])
        self.assertEqual([event.trigger_type for event in trigger_events], ["Hiring signal"])
        self.assertIn("Clinical Safety Officer", discovery_hits[0].discovery_rationale)
        self.assertIn("1 search queries", result)

    def test_parse_google_news_rss(self):
        results = pipeline.parse_google_news_rss(RSS_FIXTURE, "MedTech AI Funding")

        self.assertEqual(len(results), 4)
        self.assertEqual(results[0].query, "MedTech AI Funding")
        self.assertEqual(results[0].publisher, "MedTech Dive")
        self.assertEqual(results[0].link, "https://news.google.com/rss/articles/novascan")
        self.assertEqual(pipeline.article_year_from_pubdate(results[0].published_at), "2026")

    def test_search_evidence_extraction_classification_and_dedupe(self):
        source = pipeline.Source("Google News / web funding search", "News/search", "https://news.google.com/search", "US/EU/global", "High", "Weekly", "Google News RSS query", "Search fixture", "google_news_search")
        results = pipeline.parse_google_news_rss(RSS_FIXTURE, "MedTech AI Funding")
        discovery_hits, trigger_events = pipeline.build_google_news_evidence(source, results)

        self.assertEqual([hit.company for hit in discovery_hits], ["NovaScan Health", "PulseDx", "ClearPath Medical"])
        self.assertEqual([event.company for event in trigger_events], ["NovaScan Health", "PulseDx"])
        self.assertEqual(trigger_events[0].trigger_type, "Funding")
        self.assertEqual(trigger_events[1].trigger_type, "Regulatory clearance")
        self.assertIn("query: MedTech AI Funding", discovery_hits[0].matched_terms)
        self.assertEqual(discovery_hits[0].article_year, "2026")

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
        self.assertEqual(discovery_row[4], "2026")
        self.assertEqual(trigger_row[4], "https://news.google.com/rss/articles/novascan")
        self.assertEqual(novascan_lead[12], "2026")
        self.assertEqual(novascan_lead[17], "Verified trigger")

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
        self.assertIn("Article year", discovery_headers)
        self.assertIn("Company description", lead_headers)
        self.assertEqual(discovery_row[10], "Fixture Accelerator")
        self.assertEqual(discovery_row[12], "2026")

    def test_primary_discovery_prefers_richer_cohort_metadata(self):
        generic_hit = pipeline.DiscoveryHit(
            company="Rosalind Dx",
            source_name="MedTech Innovator",
            source_type="Accelerator",
            discovery_url="https://example.com/generic",
            discovery_rationale="Generic portfolio row.",
            cohort_label="MedTech Innovator portfolio",
        )
        cohort_hit = pipeline.DiscoveryHit(
            company="Rosalind Dx",
            source_name="MedTech Innovator",
            source_type="Accelerator",
            discovery_url="https://example.com/apac",
            discovery_rationale="Specific APAC cohort row.",
            website="https://www.rosalinddx.com",
            cohort_label="MedTech Innovator APAC 2025",
            cohort_year="2025",
            category_or_track="Diagnostics",
            company_description="Accessible prenatal testing.",
        )
        record = pipeline.CompanyRecord(company="Rosalind Dx", discovery_hits=[generic_hit, cohort_hit])

        self.assertEqual(pipeline.primary_discovery(record).discovery_url, "https://example.com/apac")

    def test_rule_classification_covers_core_personas(self):
        cases = [
            (
                "AcceleratorCo",
                pipeline.DiscoveryHit("AcceleratorCo", "Fixture Accelerator", "Accelerator", "https://example.com/a", "Current accelerator cohort.", product_type="AI medical device"),
                [],
                "Early startup",
                "Accelerator/cohort",
            ),
            (
                "FundedCo",
                pipeline.DiscoveryHit("FundedCo", "Funding News", "News/search", "https://example.com/f", "Raised a Series A for diagnostic AI.", product_type="Diagnostics"),
                [pipeline.TriggerEvent("FundedCo", "Funding", "Raised a Series A.", "Funding News", "https://example.com/f")],
                "Funded startup",
                "Funding trigger",
            ),
            (
                "JobsCo",
                pipeline.DiscoveryHit("JobsCo", "Jobs", "Jobs", "https://example.com/j", "Hiring a regulatory affairs lead.", product_type="SaMD"),
                [pipeline.TriggerEvent("JobsCo", "Hiring signal", "Hiring regulatory affairs and QA.", "Jobs", "https://example.com/j")],
                "Jobs-led capability gap",
                "Hiring gap",
            ),
            (
                "RegCo",
                pipeline.DiscoveryHit("RegCo", "FDA", "Regulatory database", "https://example.com/r", "FDA clearance listing.", product_type="Medical device"),
                [pipeline.TriggerEvent("RegCo", "Regulatory clearance", "Received FDA clearance.", "FDA", "https://example.com/r")],
                "Regulatory-led opportunity",
                "Regulatory pathway",
            ),
            (
                "SpinoutCo",
                pipeline.DiscoveryHit("SpinoutCo", "University", "University/spinout", "https://example.com/u", "University spinout.", product_type="Medical device"),
                [],
                "University/spinout",
                "Medical device",
            ),
        ]

        for company, hit, triggers, persona, secondary_tag in cases:
            record = pipeline.CompanyRecord(company=company, product_type=hit.product_type, discovery_hits=[hit], triggers=triggers)
            enrichment = pipeline.classify_company_rules(record)

            self.assertEqual(enrichment.persona, persona)
            self.assertEqual(enrichment.secondary_tag, secondary_tag)
            self.assertFalse(enrichment.llm_used)
            self.assertEqual(enrichment.method, "rules")

    def test_classification_marks_missing_llm_fallback(self):
        hit = pipeline.DiscoveryHit("NovaScan Health", "Fixture", "Accelerator", "https://example.com", "AI imaging accelerator company.")
        record = pipeline.CompanyRecord(company="NovaScan Health", discovery_hits=[hit])

        with patch.dict("os.environ", {}, clear=True):
            enrichment = pipeline.classify_company(record)

        self.assertFalse(enrichment.llm_used)
        self.assertEqual(enrichment.fallback_reason, "llm_not_configured")

    def test_classification_falls_back_for_llm_errors_and_invalid_outputs(self):
        hit = pipeline.DiscoveryHit("NovaScan Health", "Fixture", "Accelerator", "https://example.com", "AI imaging accelerator company.")
        record = pipeline.CompanyRecord(company="NovaScan Health", discovery_hits=[hit])

        with patch.dict("os.environ", {"BBT_LEAD_ENRICHMENT_API_KEY": "fixture"}, clear=True), patch.object(pipeline, "load_cached_llm_enrichment", return_value=None), patch("bbt_bizdev.pipeline._call_lead_enrichment_llm", side_effect=RuntimeError("boom")):
            error_fallback = pipeline.classify_company(record)

        with patch.dict("os.environ", {"BBT_LEAD_ENRICHMENT_API_KEY": "fixture"}, clear=True), patch.object(pipeline, "load_cached_llm_enrichment", return_value=None), patch("bbt_bizdev.pipeline._call_lead_enrichment_llm", side_effect=ValueError("invalid_json")):
            json_fallback = pipeline.classify_company(record)

        with patch.dict("os.environ", {"BBT_LEAD_ENRICHMENT_API_KEY": "fixture"}, clear=True), patch.object(pipeline, "load_cached_llm_enrichment", return_value={"persona": "Bad", "primary_quadrant": "Advisory", "secondary_tag": "SaMD/AI", "pain_hypothesis": "x", "value_prop": "x", "outreach_angle": "x", "confidence": 0.5, "rationale": "x"}):
            taxonomy_fallback = pipeline.classify_company(record)

        self.assertEqual(error_fallback.fallback_reason, "llm_error")
        self.assertEqual(json_fallback.fallback_reason, "invalid_json")
        self.assertEqual(taxonomy_fallback.fallback_reason, "invalid_taxonomy")
        self.assertFalse(error_fallback.llm_used)

    def test_workbook_includes_enrichment_columns_and_varied_personas(self):
        accelerator_hit = pipeline.DiscoveryHit("NovaScan Health", "Fixture Accelerator", "Accelerator", "https://example.com/novascan", "Current accelerator cohort.", product_type="AI medical device", website="https://novascan.example")
        jobs_hit = pipeline.DiscoveryHit("PulseDx", "Jobs", "Jobs", "https://example.com/pulsedx", "Hiring regulatory affairs and QA.", product_type="SaMD", website="https://pulsedx.example")
        companies = pipeline.normalize_companies([accelerator_hit, jobs_hit])
        trigger_events = pipeline.attach_trigger_events(
            companies,
            [pipeline.TriggerEvent("PulseDx", "Hiring signal", "Hiring regulatory affairs and QA.", "Jobs", "https://example.com/pulsedx")],
        )
        pipeline.mark_primary_triggers(companies)

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict("os.environ", {}, clear=True):
            original_out = pipeline.OUT
            try:
                pipeline.OUT = Path(temp_dir) / "enrichment.xlsx"
                workbook_path = pipeline.write_workbook(companies, [accelerator_hit, jobs_hit], trigger_events, [["Fixture", "Jobs", jobs_hit.discovery_url, "Fetched", "fixture"]])
                wb = load_workbook(workbook_path)
            finally:
                pipeline.OUT = original_out

        headers = [cell.value for cell in wb["Lead Filtering"][1]]
        rows = list(wb["Lead Filtering"].iter_rows(min_row=2, values_only=True))
        personas = {row[11] for row in rows}

        self.assertIn("Value prop", headers)
        self.assertIn("Outreach angle", headers)
        self.assertIn("LLM used", headers)
        self.assertIn("Fallback reason", headers)
        self.assertIn("Website", headers)
        self.assertIn("Evidence year", headers)
        self.assertIn("Evidence recency", headers)
        self.assertIn("Trigger type", headers)
        self.assertIn("Geography", headers)
        self.assertIn("Company stage", headers)
        self.assertIn("Product area", headers)
        self.assertIn("Hiring signal", headers)
        self.assertIn("Funding stage", headers)
        self.assertIn("Early startup", personas)
        self.assertIn("Jobs-led capability gap", personas)
        self.assertNotIn("AI/SaMD or healthtech company from approved source", personas)
        self.assertTrue(all(row[19] == "No" for row in rows))
        self.assertTrue(all(row[20] == "llm_not_configured" for row in rows))
        self.assertEqual(headers[36], "Primary evidence URL")
        self.assertEqual(headers[37], "Website")
        self.assertEqual({row[0]: row[37] for row in rows}, {"NovaScan Health": "https://novascan.example", "PulseDx": "https://pulsedx.example"})

    def test_lead_filter_fields_use_latest_evidence_and_explicit_signals(self):
        older = pipeline.DiscoveryHit("NovaScan", "Accelerator", "Accelerator", "https://example.com/2023", "Accelerator cohort.", cohort_year="2023", geography="Ireland")
        latest = pipeline.DiscoveryHit("NovaScan", "Funding News", "News/search", "https://example.com/2025", "Raised a Series A for diagnostic imaging AI.", article_year="2025", geography="Ireland")
        trigger = pipeline.TriggerEvent("NovaScan", "Funding", "Raised a Series A.", "Funding News", latest.discovery_url)
        record = pipeline.CompanyRecord(company="NovaScan", geography="Ireland", discovery_hits=[older, latest], triggers=[trigger])
        trigger.trigger_role = "Primary"

        fields = pipeline.lead_filter_fields(record, pipeline.classify_company_rules(record))

        self.assertEqual(fields["Evidence year"], "2025")
        self.assertEqual(fields["Evidence basis"], "Article year")
        self.assertEqual(fields["Trigger type"], "Funding")
        self.assertEqual(fields["Funding stage"], "Series A")
        self.assertEqual(fields["Product area"], "AI / SaMD")
        self.assertEqual(fields["Hiring signal"], "No")

    def test_geography_is_normalized_to_filter_regions(self):
        cases = {
            "San Francisco, CA, USA": "US",
            "Toronto, ON, Canada": "Canada",
            "London, England, United Kingdom": "UK",
            "Galway, County Galway, Ireland": "Ireland",
            "Paris, Ile-de-France, France": "Europe",
            "Singapore, Singapore": "Asia-Pacific",
            "Sydney, NSW, Australia": "Australia/New Zealand",
            "Israel/US": "Middle East",
            "EU/US": "Europe",
            "US/EU/global": "US",
            "Remote": "Unknown",
        }
        for raw, expected in cases.items():
            self.assertEqual(pipeline.normalize_geography_region(raw), expected)

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
        alpha_profile = "<html><body>Cohort: 2025 Sector: Digital health</body></html>"
        beta_profile = "<html><body>2024 Accelerator Technology: Diagnostics</body></html>"
        gamma_profile = "<html><body>Launchpad - 2023</body></html>"

        with patch.object(pipeline, "fetch_raw_text", side_effect=[(page_1, None), (alpha_profile, None), (beta_profile, None), (page_2, None), (gamma_profile, None)]):
            discovery_hits, trigger_events, result = pipeline.run_digitalhealth_london(source)

        self.assertEqual([hit.company for hit in discovery_hits], ["Alpha Care", "BetaDx", "Gamma EHR"])
        self.assertEqual([hit.cohort_year for hit in discovery_hits], ["2025", "2024", "2023"])
        self.assertIn("Remote monitoring", discovery_hits[0].company_description)
        self.assertEqual(len(trigger_events), 3)
        self.assertIn("2 directory pages", result)
        self.assertIn("3 profiles fetched", result)

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
        self.assertEqual(hits[0].discovery_url, "https://app.pory.dev/data/66eb41bc87c0d05ea2b410b8/records/rec1")
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

    def test_priority_ireland_accelerator_parsers_extract_company_links(self):
        fixtures = [
            (
                pipeline.Source("BioInnovate Ireland", "Accelerator", "https://www.bioinnovate.ie/", "Ireland", "High", "Annual", "Fellowship/company extraction", "Medtech programme.", "bioinnovate_ireland"),
                '<a href="/our-companies/proverum/">ProVerum</a><p>Medical device company for urology.</p>',
                "ProVerum",
            ),
            (
                pipeline.Source("ARC Hub for HealthTech", "Accelerator", "https://www.universityofgalway.ie/arc-healthtech/", "Ireland", "High", "Quarterly", "Commercialisation extraction", "Healthtech commercialisation.", "arc_hub_healthtech"),
                '<a href="/arc-healthtech/projects/feeltect/">FeelTect</a><p>Connected health compression monitoring device.</p>',
                "FeelTect",
            ),
            (
                pipeline.Source("Health Innovation Hub Ireland", "Accelerator", "https://www.hih.ie/", "Ireland", "High", "Quarterly", "Innovation extraction", "Clinical validation hub.", "health_innovation_hub_ireland"),
                '<a href="/case-studies/patientmpower/">patientMpower</a><p>Digital health respiratory monitoring platform.</p>',
                "PatientMpower",
            ),
            (
                pipeline.Source("Dogpatch Labs / NDRC", "Accelerator", "https://www.ndrc.ie/", "Ireland", "Medium", "Quarterly", "Portfolio extraction", "National accelerator.", "dogpatch_ndrc"),
                '<a href="/portfolio/silvercloud-health/">SilverCloud Health</a><p>Mental health digital therapeutics platform.</p>',
                "SilverCloud Health",
            ),
        ]

        for source, html, expected_company in fixtures:
            with self.subTest(source=source.name):
                hits = pipeline.parse_priority_accelerator_page(source, html, source.url)

                self.assertEqual([hit.company for hit in hits], [expected_company])
                self.assertEqual(hits[0].source_type, "Accelerator")
                self.assertIn(source.adapter, hits[0].matched_terms)

    def test_priority_ireland_accelerator_runners_emit_triggers(self):
        source = pipeline.Source("BioInnovate Ireland", "Accelerator", "https://www.bioinnovate.ie/", "Ireland", "High", "Annual", "Fellowship/company extraction", "Medtech programme.", "bioinnovate_ireland")
        html = '<script src="https://stories.universityofgalway.ie/bioinnovate/start-ups/embed.js"></script><script>fetch("https://data.shorthand.com/erKSumnd3Q/collections/Xta6wmZajc/items.json")</script>'
        payload = {
            "title": "BioInnovate Alumni Companies",
            "items": [
                {
                    "title": "Luma Vision",
                    "description": "Cardiac imaging medical device company.",
                    "url": "https://lumavision.com/",
                }
            ],
        }

        with patch.object(pipeline, "ACCELERATOR_SOURCE_PAGES", {"BioInnovate Ireland": ["https://www.bioinnovate.ie/bioinnovate/alumni/"]}), patch.object(pipeline, "fetch_raw_text", return_value=(html, None)), patch.object(pipeline, "fetch_json_url", return_value=(payload, None)):
            discovery_hits, trigger_events, result = pipeline.run_bioinnovate_ireland(source)

        self.assertEqual([hit.company for hit in discovery_hits], ["Luma Vision"])
        self.assertEqual(discovery_hits[0].website, "https://lumavision.com/")
        self.assertIn("shorthand alumni collection", discovery_hits[0].matched_terms)
        self.assertEqual([event.trigger_type for event in trigger_events], ["Accelerator/cohort"])
        self.assertIn("alumni collections scanned", result)

    def test_bioinnovate_extracts_all_plausible_alumni_without_health_keyword_filter(self):
        source = pipeline.Source("BioInnovate Ireland", "Accelerator", "https://www.bioinnovate.ie/", "Ireland", "High", "Annual", "Fellowship/company extraction", "Medtech programme.", "bioinnovate_ireland")
        html = """
        <a href="/our-companies/luma-vision/">Luma Vision</a><p>Alumni company.</p>
        <a href="/our-companies/galenband/">Galenband</a>
        <a href="/our-companies/proverum/">ProVerum</a><p>Venture profile.</p>
        """

        hits = pipeline.parse_priority_accelerator_page(source, html, source.url)

        self.assertEqual([hit.company for hit in hits], ["Luma Vision", "Galenband", "ProVerum"])

    def test_bioinnovate_skips_alumni_navigation_links(self):
        source = pipeline.Source("BioInnovate Ireland", "Accelerator", "https://www.bioinnovate.ie/bioinnovate/alumni/", "Ireland", "High", "Annual", "Fellowship/company extraction", "Medtech programme.", "bioinnovate_ireland")
        html = """
        <a href="/bioinnovate/alumni/">Alumni</a>
        <a href="/bioinnovate/alumni/directory/">BioInnovate Alumni</a>
        <a href="/bioinnovate/alumni/directory/">Alumni Directory</a>
        """

        hits = pipeline.parse_priority_accelerator_page(source, html, source.url)

        self.assertEqual(hits, [])

    def test_ndrc_filters_portfolio_links_to_healthcare_keyword_matches(self):
        source = pipeline.Source("Dogpatch Labs / NDRC", "Accelerator", "https://www.ndrc.ie/", "Ireland", "Medium", "Quarterly", "Portfolio extraction", "National accelerator.", "dogpatch_ndrc")
        html = """
        <a href="/portfolio/silvercloud-health/">SilverCloud Health</a>
        <p>Mental health digital therapeutics platform for patient care.</p>
        <a href="/portfolio/payrollflow/">PayrollFlow</a>
        <p>Payroll automation for small businesses.</p>
        """

        hits = pipeline.parse_priority_accelerator_page(source, html, source.url)

        self.assertEqual([hit.company for hit in hits], ["SilverCloud Health"])
        self.assertIn("healthcare keywords:", hits[0].matched_terms)
        self.assertIn("mental health", hits[0].matched_terms)

    def test_ndrc_extracts_healthcare_matches_from_current_cohort_domain_links(self):
        source = pipeline.Source("Dogpatch Labs / NDRC", "Accelerator", "https://www.ndrc.ie/accelerator-cohort-2024-h1", "Ireland", "Medium", "Quarterly", "Portfolio extraction", "National accelerator.", "dogpatch_ndrc")
        html = """
        <p>Blynksolve enables pharmaceutical drug substance manufacturers to build a digital knowledge twin.</p>
        <a href="https://www.blynksolve.com">blynksolve.com</a>
        <p>Vesta Insights serves the mortgage industry.</p>
        <a href="https://vesta-insights.example">vesta's website</a>
        """

        hits = pipeline.parse_priority_accelerator_page(source, html, source.url)

        self.assertEqual([hit.company for hit in hits], ["Blynksolve"])
        self.assertIn("pharma", hits[0].matched_terms)

    def test_priority_vc_parsers_extract_portfolio_company_links(self):
        fixtures = [
            (
                pipeline.Source("Fountain Healthcare Partners portfolio", "VC portfolio", "https://www.fountainhealthcare.com/portfolio/", "Ireland/EU/US", "High", "Monthly", "Portfolio extraction", "Life sciences investor.", "fountain_healthcare"),
                '<a href="/portfolio/neurovalve/">NeuroValve</a><p>Medical device company for structural heart disease.</p>',
                "NeuroValve",
            ),
            (
                pipeline.Source("Seroba Life Sciences portfolio", "VC portfolio", "https://seroba-lifesciences.com/portfolio/", "EU/Ireland", "High", "Monthly", "Portfolio extraction", "Life sciences investor.", "seroba_life_sciences"),
                '<a href="/portfolio/atlanti-dx/">AtlantiDx</a><p>Diagnostics platform for clinical labs.</p>',
                "AtlantiDx",
            ),
            (
                pipeline.Source("Atlantic Bridge portfolio", "VC portfolio", "https://www.abven.com/portfolio/", "Ireland/EU/US", "High", "Monthly", "Portfolio extraction", "Deeptech investor.", "atlantic_bridge"),
                '<a href="/portfolio/clinic-ai/">ClinicAI</a><p>AI health workflow spinout.</p>',
                "ClinicAI",
            ),
        ]

        for source, html, expected_company in fixtures:
            with self.subTest(source=source.name):
                hits = pipeline.parse_vc_portfolio_page(source, html, source.url)

                self.assertEqual([hit.company for hit in hits], [expected_company])
                self.assertEqual(hits[0].source_type, "VC portfolio")
                self.assertIn(source.adapter, hits[0].matched_terms)

    def test_priority_vc_runners_emit_investor_triggers(self):
        source = pipeline.Source("Seroba Life Sciences portfolio", "VC portfolio", "https://seroba-lifesciences.com/portfolio/", "EU/Ireland", "High", "Monthly", "Portfolio extraction", "Life sciences investor.", "seroba_life_sciences")
        html = '<a href="/portfolio/medbridge/">MedBridge</a><p>Digital health platform for regulated care pathways.</p>'

        with patch.object(pipeline, "fetch_raw_text", return_value=(html, None)):
            discovery_hits, trigger_events, result = pipeline.run_seroba_life_sciences(source)

        self.assertEqual([hit.company for hit in discovery_hits], ["MedBridge"])
        self.assertEqual([event.trigger_type for event in trigger_events], ["Investor backing"])
        self.assertIn("1 VC portfolio page", result)

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
        self.assertEqual([hit.cohort_year for hit in discovery_hits], ["2026", "2025", "2024"])
        self.assertEqual(discovery_hits[0].cohort_label, "Y Combinator Summer 2026")
        self.assertEqual(len(trigger_events), 3)
        self.assertIn("3 matches", result)

    def test_yc_batch_year_handles_short_batch_codes(self):
        self.assertEqual(pipeline.infer_yc_batch_year("W24"), "2024")
        self.assertEqual(pipeline.infer_yc_batch_year("S25"), "2025")


if __name__ == "__main__":
    unittest.main()
