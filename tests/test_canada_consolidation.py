import json
import tempfile
import unittest
from pathlib import Path

from bbt_bizdev.canada_consolidation import (
    consolidate,
    load_source_records,
    normalize_domain,
    normalize_name,
    run_consolidation,
)


def snapshot(path: Path, source: str, rows: list[dict]) -> None:
    path.write_text(json.dumps({
        "snapshot_date": "2026-07-27",
        "source": {"name": source, "source_type": "Accelerator", "url": f"https://{source}.example/list"},
        "records": rows,
    }), encoding="utf-8")


class CanadaConsolidationTests(unittest.TestCase):
    def test_normalization_removes_legal_suffix_and_tracking(self):
        self.assertEqual(normalize_name("Société Acme, Inc."), "societe acme")
        self.assertEqual(normalize_domain("https://www.Acme.ca/path?utm_source=x"), "acme.ca")

    def test_exact_name_variants_merge_and_preserve_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshot(root / "one_2026-07-27.json", "one", [{
                "company": "Acme Medical Inc.", "website": "https://www.acme.ca",
                "geography": "Toronto, ON", "description": "Medical device company",
                "discovery_url": "https://one.example/acme",
            }])
            snapshot(root / "two_2026-07-27.json", "two", [{
                "company": "Acme Medical", "website": "https://acme.ca/about",
                "discovery_url": "https://two.example/acme",
            }])
            records, rejected = load_source_records(root.glob("*.json"))
            payload = consolidate(records, "2026-07-27")
        self.assertFalse(rejected)
        self.assertEqual(len(payload["companies"]), 1)
        company = payload["companies"][0]
        self.assertEqual(company["domain"], "acme.ca")
        self.assertEqual(company["province"], "Ontario")
        self.assertEqual(len(payload["source_provenance"]), 2)
        self.assertEqual(company["completeness"]["hiring"]["status"], "not_run")

    def test_conflicting_domains_are_not_automatically_merged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshot(root / "one_2026-07-27.json", "one", [
                {"company": "Nova", "website": "https://nova-health.ca"}
            ])
            snapshot(root / "two_2026-07-27.json", "two", [
                {"company": "Nova Inc.", "website": "https://nova-labs.ca"},
                {"company": "Nova", "website": "https://nova-labs.ca"},
            ])
            records, _ = load_source_records(root.glob("*.json"))
            payload = consolidate(records, "2026-07-27")
        self.assertEqual(len(payload["companies"]), 2)
        self.assertEqual(len({row["company_id"] for row in payload["companies"]}), 2)
        self.assertEqual(payload["ambiguous_name_review"][0]["issue_type"], "same_name_conflicting_domains")

    def test_shared_domain_different_names_get_distinct_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshot(root / "one_2026-07-27.json", "one", [
                {"company": "Old Subsidiary", "website": "https://parent.ca"},
                {"company": "Parent Company", "website": "https://parent.ca"},
            ])
            records, _ = load_source_records(root.glob("*.json"))
            payload = consolidate(records, "2026-07-27")
        self.assertEqual(len(payload["companies"]), 2)
        self.assertEqual(len({row["company_id"] for row in payload["companies"]}), 2)
        self.assertEqual(payload["ambiguous_name_review"][0]["issue_type"], "shared_domain_different_names")

    def test_portfolio_page_is_not_treated_as_official_website(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshot(root / "uceed_2026-07-27.json", "uceed", [{
                "company": "Example Health",
                "website": "https://uceed.example/portfolio/example",
                "discovery_url": "https://uceed.example/portfolio/example",
            }])
            records, _ = load_source_records(root.glob("*.json"))
        self.assertEqual(records[0].domain, "")
        self.assertEqual(records[0].website, "")

    def test_nested_wordpress_shape_and_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root, output = Path(temp) / "data", Path(temp) / "out"
            root.mkdir()
            (root / "centech_2026-07-27.json").write_text(json.dumps({
                "collected_at": "2026-07-27",
                "source_name": "Centech",
                "source_url": "https://centech.example/api",
                "records": [{
                    "title": {"rendered": "Infirnaa"},
                    "link": "https://centech.example/startups/infirnaa",
                    "acf": {
                        "startups_website": {"url": "https://infirnaa.ca"},
                        "startups_description_en": "Immersive nursing simulation.",
                    },
                }],
            }), encoding="utf-8")
            payload, files = run_consolidation(root, output, "2026-07-27")
            summary = json.loads(files["summary"].read_text(encoding="utf-8"))
            self.assertEqual(payload["companies"][0]["domain"], "infirnaa.ca")
            self.assertEqual(summary["canonical_companies"], 1)
            self.assertTrue(all(path.exists() for path in files.values()))

    def test_previous_identity_keys_keep_company_id_stable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshot(root / "one_2026-07-27.json", "one", [
                {"company": "Old Name", "website": "https://stable.ca"}
            ])
            records, _ = load_source_records(root.glob("*.json"))
            first = consolidate(records, "2026-07-27")
            snapshot(root / "one_2026-07-27.json", "one", [
                {"company": "New Name", "website": "https://stable.ca"}
            ])
            records, _ = load_source_records(root.glob("*.json"))
            second = consolidate(records, "2026-08-01", previous_payload=first)
        self.assertEqual(first["companies"][0]["company_id"], second["companies"][0]["company_id"])


if __name__ == "__main__":
    unittest.main()
