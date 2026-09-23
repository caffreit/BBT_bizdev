import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from bbt_bizdev.phone_extractor import (
    BoundedSearch, CompanyInput, FetchResult,
    crawl_company,
    extract_phone_candidates,
    load_irish_companies,
    normalize_irish_phone,
    prioritized_internal_links,
    recover_website,
    run_extraction,
)


def company(website="https://acme.ie", evidence=""):
    return CompanyInput(
        "ie-acme", "Acme Diagnostics", website, "Ireland", "Diagnostics", "",
        "Test", evidence, (2,),
    )


class PhoneExtractorTests(unittest.TestCase):
    def test_normalizes_landlines_and_excludes_mobile(self):
        self.assertEqual(normalize_irish_phone("01 234 5678"), ("012345678", "+35312345678", "business_landline"))
        self.assertEqual(normalize_irish_phone("+353 (21) 555 1234"), ("0215551234", "+353215551234", "business_landline"))
        self.assertEqual(normalize_irish_phone("087 123 4567")[2], "mobile")

    def test_extracts_tel_and_context_numbers_but_not_mobile_or_fax(self):
        html = """
        <a href="tel:+35315551234">Call Dublin</a>
        <p>Sales phone: 021 555 6789</p>
        <p>Mobile: 087 111 2222</p>
        <p>Fax: 091 333 4444</p>
        """
        candidates, mobile_candidates, mobiles = extract_phone_candidates(html, "https://acme.ie/contact")
        self.assertEqual([row.phone_e164 for row in candidates], ["+35315551234", "+353215556789"])
        self.assertGreaterEqual(mobiles, 1)
        self.assertEqual([row.phone_e164 for row in mobile_candidates], ["+353871112222"])

    def test_rejects_foreign_and_third_party_regulator_numbers(self):
        html = """
        <p>Italy Tel: (+39) 02 9952517</p>
        <p>South Africa Phone: +27(0)11 807 4887</p>
        <p>Contact the Data Protection Commissioner at www.dataprotection.ie, phone +353 57 868 4800.</p>
        """
        candidates, mobile_candidates, _ = extract_phone_candidates(html, "https://acme.ie/privacy")
        self.assertEqual(candidates, [])
        self.assertEqual(mobile_candidates, [])

    def test_prioritizes_contact_links_and_stays_on_domain(self):
        html = '<a href="/news">News</a><a href="/contact">Contact us</a><a href="https://other.ie/about">About</a>'
        self.assertEqual(prioritized_internal_links(html, "https://acme.ie"), ["https://acme.ie/contact"])

    def test_recovers_verified_website_from_discovery_evidence(self):
        pages = {
            "https://directory.ie/acme": '<a href="https://acme.ie">Acme Diagnostics</a>',
            "https://acme.ie": "<h1>Acme Diagnostics</h1>",
        }
        fetch = lambda url: FetchResult(url, pages.get(url, ""), 200 if url in pages else 404)
        resolved = recover_website(company("", "https://directory.ie/acme"), fetch, lambda _: ([], None))
        self.assertEqual(resolved, ("https://acme.ie", "discovery_evidence_link", "resolved"))

    def test_crawls_contact_page_and_selects_non_mobile_phone(self):
        pages = {
            "https://acme.ie": '<h1>Acme Diagnostics</h1><a href="/contact">Contact</a>',
            "https://acme.ie/contact": '<a href="tel:01 555 1234">Phone</a><a href="tel:087 123 4567">Mobile</a>',
        }
        fetch = lambda url: FetchResult(url, pages.get(url, ""), 200 if url in pages else 404)
        result = crawl_company(company(), fetch, lambda _: ([], None))
        self.assertEqual(result.phone_status, "found")
        self.assertEqual(result.phone_e164, "+35315551234")
        self.assertEqual(result.source_url, "https://acme.ie/contact")
        self.assertGreaterEqual(result.excluded_mobile_count, 1)
        self.assertEqual(result.mobile_candidates[0]["phone_e164"], "+353871234567")

    def test_loads_all_irish_rows_and_deduplicates_company_names(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Lead Intake"
            sheet.append(["Company", "Website", "Geography", "Product type", "Company description", "Discovery source", "Discovery evidence URL"])
            sheet.append(["Acme", "acme.ie", "Ireland", "Device", "", "A", ""])
            sheet.append([" ACME ", "", "EU/Ireland", "", "", "B", ""])
            sheet.append(["Other", "other.com", "Canada", "", "", "", ""])
            workbook.save(path)
            rows = load_irish_companies(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].source_rows, (2, 3))

    def test_end_to_end_run_writes_auditable_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "input.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Lead Intake"
            sheet.append(["Company", "Website", "Geography", "Product type", "Company description", "Discovery source", "Discovery evidence URL"])
            sheet.append(["Acme Diagnostics", "https://acme.ie", "Ireland", "Diagnostics", "", "A", ""])
            workbook.save(path)
            pages = {
                "https://acme.ie": '<h1>Acme Diagnostics</h1><a href="tel:+353 1 555 1234">Call</a>',
            }
            fetch = lambda url: FetchResult(url, pages.get(url, ""), 200 if url in pages else 404)
            summary, files = run_extraction(path, root / "out", workers=1, fetcher=fetch, search_fn=lambda _: ([], None), run_date="2026-09-15")
            self.assertEqual(summary["phones_found"], 1)
            self.assertTrue(files["results_csv"].exists())
            self.assertTrue(files["results_json"].exists())
            self.assertTrue(files["mobiles_csv"].exists())

    def test_search_circuit_breaker_stops_repeated_network_errors(self):
        calls = []
        search = BoundedSearch(lambda query: (calls.append(query), ([], "blocked"))[1], error_limit=2)
        self.assertEqual(search("one"), ([], "blocked"))
        self.assertIn("Search disabled", search("two")[1])
        self.assertIn("Search disabled", search("three")[1])
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
