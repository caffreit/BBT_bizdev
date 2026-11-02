import json
import unittest
from unittest.mock import patch

from bbt_bizdev.adapters import canada_ai_institutes as ai
from bbt_bizdev.config import ADAPTER_STATUS_NAMES, SOURCES


def source(adapter):
    return next(item for item in SOURCES if item.adapter == adapter)


def ai20_html(rows):
    """rows: (name, sector, hq, website); sector None renders the empty modal Vector publishes."""
    grid = "".join(
        f'<article class="institutions__institution institutions__institution--4">'
        f'<button class="institutions__logo" aria-label="{name}"></button>'
        f'<div><p class="institutions__name">{name}</p></div></article>'
        for name, *_ in rows
    )
    slides = ""
    for name, sector, hq, website in rows:
        body = ""
        if sector is not None:
            body = (
                f'<div class="modal__program"><h2>{name}</h2>'
                f"<p><strong>Sector</strong> {sector}</p>"
                f"<p><strong>Headquarters </strong>{hq}</p>"
                f"<p>{name} builds AI products.</p>"
                f'<div class="modal__link"><a class="button-link" href="{website}">Visit</a></div></div>'
            )
        slides += f'<div class="modal__slide"><div class="modal__institution-content">{body}</div></div>'
    return grid + slides


def ai20_fetcher(rows):
    payload = json.dumps([{"link": "https://vectorinstitute.ai/vectors-ai20-for-2023/", "content": {"rendered": ai20_html(rows)}}])
    return lambda url: (payload, None)


AI20_ROWS = (
    [("BenchSci", "Medical Research", "Toronto", "https://www.benchsci.com/"),
     ("BlueDot", "Health", "Toronto", "https://bluedot.global/"),
     ("Signal 1", "Health", "Toronto", "https://signal1.ai/"),
     ("Deep Genomics", None, "", ""),
     ("BrainBox AI", None, "", ""),
     ("Waabi", "Transportation", "Toronto", "https://waabi.ai/"),
     ("xpertSea", "Aquaculture", "Quebec City", "https://www.xpertsea.com/")]
    + [(f"Tech {index}", "Technology", "Ottawa", f"https://tech{index}.example/") for index in range(13)]
)


HEALTHSPARK_HTML = """
<h2 class="wp-block-heading">Current HealthSpark members</h2>
<div class="partners__container">
  {logos}
</div>
<div class="modal partners__modal"><section class="modal__body">{modals}</section></div>
<h2>Program details</h2>
<h2>Our partners</h2>
<button class="partners__logo" aria-label="Ontario Health" data-index="1"></button>
"""


def healthspark_html(names):
    logos = "".join(f'<button class="partners__logo" aria-label="{name} " data-index="{i}"></button>' for i, name in enumerate(names))
    modals = "".join(f'<div class="modal__description"><p><b>{name}</b> builds clinical AI.</p></div>' for name in names)
    return HEALTHSPARK_HTML.format(logos=logos, modals=modals)


AMII_HTML = """
<p><b>Meet the Cohort</b></p><p>We are thrilled to introduce the cohort:</p><ul>
<li><p><a href="https://www.resolvehd.ai/" target="_blank">ResolveHD</a>  (Halifax, NS)</p></li>
<li><p><a href="https://nuramedical.com/" target="_blank">NURA Medical</a> (Montreal, PQ)</p></li>
<li><p><a href="https://emergconnect.ca/" target="_blank">EmergConnect Inc.</a> (Toronto, ON)</p></li>
<li><p>Unlinked Health (Calgary, AB)</p></li>
</ul><p>Visit the <a href="https://www.amii.ca/courses/level-up">Level Up program</a> page.</p>
"""


class InstituteConfigTests(unittest.TestCase):
    def test_sources_use_dedicated_adapters_with_status_names(self):
        expected = {
            "Vector Institute AI20": "vector_ai20",
            "Vector Institute HealthSpark": "vector_healthspark",
            "Amii Level Up health-tech cohort": "amii_level_up_health",
            "Mila Startups": "mila_startups",
            "Mila health-AI industry partners": "mila_health_partners",
        }
        actual = {item.name: item.adapter for item in SOURCES if item.name in expected}
        self.assertEqual(actual, expected)
        for adapter in expected.values():
            self.assertIn(adapter, ADAPTER_STATUS_NAMES)

    def test_geography_uses_city_and_province_code(self):
        self.assertEqual(ai.institute_geography("Montreal, PQ"), "Montreal, QC")
        self.assertEqual(ai.institute_geography("Toronto"), "Toronto, ON")
        self.assertEqual(ai.institute_geography("Atlantis"), "Atlantis")
        self.assertEqual(ai.institute_geography(""), "Canada")


class VectorAI20Tests(unittest.TestCase):
    def test_runner_filters_to_health_and_curates_empty_profiles(self):
        hits, triggers, result = ai.run_vector_ai20(source("vector_ai20"), fetcher=ai20_fetcher(AI20_ROWS))
        self.assertEqual({hit.company for hit in hits}, {"BenchSci", "BlueDot", "Signal 1", "Deep Genomics"})
        self.assertNotIn("INCOMPLETE", result)
        self.assertIn("4 health included, 16 non-health excluded", result)
        # A public ranking is a discovery signal, not a trigger event.
        self.assertEqual(triggers, [])
        bluedot = next(hit for hit in hits if hit.company == "BlueDot")
        self.assertEqual((bluedot.geography, bluedot.website), ("Toronto, ON", "https://bluedot.global/"))
        self.assertEqual(bluedot.company_description, "BlueDot builds AI products.")
        deep = next(hit for hit in hits if hit.company == "Deep Genomics")
        self.assertEqual((deep.geography, deep.website), ("Toronto, ON", ""))
        self.assertIn("curated", deep.matched_terms)

    def test_count_change_is_incomplete(self):
        _, _, result = ai.run_vector_ai20(source("vector_ai20"), fetcher=ai20_fetcher(AI20_ROWS[:-1]))
        self.assertTrue(result.startswith("INCOMPLETE Vector Institute AI20"))

    def test_fetch_error_and_bad_payload_are_incomplete(self):
        hits, _, result = ai.run_vector_ai20(source("vector_ai20"), fetcher=lambda url: ("", "HTTP Error 403"))
        self.assertEqual(hits, [])
        self.assertIn("INCOMPLETE", result)
        self.assertIn("403", result)
        _, _, result = ai.run_vector_ai20(source("vector_ai20"), fetcher=lambda url: ("[]", None))
        self.assertIn("unexpected API payload", result)


class VectorHealthSparkTests(unittest.TestCase):
    NAMES = ["Revolve Surgical", "Banting AI", "MedEssist", "IDENTOS", "Verto Health", "MedMe Health", "Tenomix Inc"]

    def test_runner_reads_only_current_members(self):
        html = healthspark_html(self.NAMES)
        hits, triggers, result = ai.run_vector_healthspark(source("vector_healthspark"), fetcher=lambda url: (html, None))
        # Legal suffixes are stripped by the shared name cleaner.
        self.assertEqual([hit.company for hit in hits], self.NAMES[:6] + ["Tenomix"])
        self.assertEqual(len(triggers), 7)
        self.assertNotIn("INCOMPLETE", result)
        self.assertNotIn("Ontario Health", {hit.company for hit in hits})
        self.assertEqual(hits[0].company_description, "Revolve Surgical builds clinical AI.")
        self.assertEqual(hits[0].geography, "Southern Ontario, Canada")

    def test_duplicates_and_missing_section_are_incomplete(self):
        html = healthspark_html(self.NAMES[:6] + ["Banting AI"])
        hits, _, result = ai.run_vector_healthspark(source("vector_healthspark"), fetcher=lambda url: (html, None))
        self.assertEqual(len(hits), 6)
        self.assertIn("INCOMPLETE", result)
        hits, _, result = ai.run_vector_healthspark(source("vector_healthspark"), fetcher=lambda url: ("<h2>Redesigned</h2>", None))
        self.assertEqual(hits, [])
        self.assertIn("INCOMPLETE", result)


class AmiiLevelUpTests(unittest.TestCase):
    def test_parser_reads_names_websites_and_locations(self):
        hits = ai.parse_amii_level_up_health(source("amii_level_up_health"), AMII_HTML)
        self.assertEqual([hit.company for hit in hits], ["ResolveHD", "NURA Medical", "EmergConnect", "Unlinked Health"])
        self.assertEqual(hits[1].geography, "Montreal, QC")
        self.assertEqual(hits[0].website, "https://www.resolvehd.ai/")
        # Missing link: name still parsed, website left blank.
        self.assertEqual((hits[3].website, hits[3].geography), ("", "Calgary, AB"))

    def test_runner_flags_count_change_and_fetch_error(self):
        _, triggers, result = ai.run_amii_level_up_health(source("amii_level_up_health"), fetcher=lambda url: (AMII_HTML, None))
        self.assertEqual(len(triggers), 4)
        self.assertIn("INCOMPLETE", result)
        _, _, result = ai.run_amii_level_up_health(source("amii_level_up_health"), fetcher=lambda url: ("", "timed out"))
        self.assertIn("INCOMPLETE", result)


class MilaCuratedTests(unittest.TestCase):
    STARTUPS = [
        ("Chapa", "https://mila.example/status", "Financial services", "Ethiopia"),
        ("Raiv Computers", "https://mila.example/status", "Neurotechnology", "Canada"),
        ("Wise Algorithms", "https://mila.example/status", "Antibody drug discovery", "Canada"),
        ("SilicoLabs", "https://mila.example/silico", "Cognitive health research", "Montreal, QC"),
    ]
    PAGES = {
        "https://mila.example/status": (
            "<h1>Four new companies</h1><p>Mila names Apex, Chapa, Raiv Computers and Wise Algorithms as Mila Startups.</p>"
            "<p>Raiv Computers : a neurotechnology startup improving neural therapies.</p>"
            "<p>Wise Algorithms: designs antibodies for diabetes and cancer.</p>"
        ),
        "https://mila.example/silico": "<p>Researchers created the Mila startup SilicoLabs for cognitive research.</p>",
    }

    def run_startups(self, pages):
        calls = []

        def fetcher(url):
            calls.append(url)
            return (pages[url], None) if url in pages else ("", "HTTP Error 404")

        with patch.object(ai, "MILA_STARTUPS", self.STARTUPS):
            hits, triggers, result = ai.run_mila_startups(source("mila_startups"), fetcher=fetcher)
        return hits, triggers, result, calls

    def test_verifies_each_curated_company_and_excludes_non_health(self):
        hits, triggers, result, calls = self.run_startups(self.PAGES)
        self.assertEqual([hit.company for hit in hits], ["Raiv Computers", "Wise Algorithms", "SilicoLabs"])
        self.assertEqual(len(triggers), 3)
        self.assertNotIn("INCOMPLETE", result)
        self.assertIn("3 health included, 1 non-health excluded", result)
        self.assertEqual(sorted(calls), sorted(self.PAGES))  # each page fetched once
        self.assertTrue(hits[0].company_description.startswith("Raiv Computers : a neurotechnology"))
        self.assertEqual(hits[2].geography, "Montreal, QC")

    def test_missing_company_or_dead_page_is_incomplete(self):
        pages = dict(self.PAGES)
        pages["https://mila.example/status"] = "<p>Raiv Computers : neurotechnology startup.</p>"
        hits, _, result, _ = self.run_startups(pages)
        self.assertIn("missing Wise Algorithms", result)
        self.assertTrue(result.startswith("INCOMPLETE"))
        hits, _, result, _ = self.run_startups({"https://mila.example/status": self.PAGES["https://mila.example/status"]})
        self.assertEqual(len(hits), 2)
        self.assertIn("404", result)

    def test_partners_produce_no_accelerator_triggers(self):
        partners = [("Secai", "https://mila.example/secai", "Clinical workflow AI", "Montreal, QC")]
        with patch.object(ai, "MILA_HEALTH_PARTNERS", partners), patch.object(ai, "MILA_HEALTH_PARTNERS_EXPECTED", 1):
            hits, triggers, result = ai.run_mila_health_partners(
                source("mila_health_partners"),
                fetcher=lambda url: ("<p>Mila announces a partnership with Secai, a Montreal healthcare AI company.</p>", None),
            )
        self.assertEqual([hit.company for hit in hits], ["Secai"])
        self.assertEqual(triggers, [])
        self.assertNotIn("INCOMPLETE", result)


if __name__ == "__main__":
    unittest.main()
