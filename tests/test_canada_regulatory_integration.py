import json
import tempfile
import unittest
from pathlib import Path

from bbt_bizdev.canada_regulatory_integration import (
    aggregate_status,
    denovo_from_registration,
    integrate_regulatory_outputs,
)


class CanadaRegulatoryIntegrationTests(unittest.TestCase):
    def test_aggregate_status(self):
        self.assertEqual("complete_matches", aggregate_status(
            [{"status": "complete_zero"}, {"status": "complete_matches"}], 2, 0
        ))
        self.assertEqual("partial", aggregate_status(
            [{"status": "complete_matches"}, {"status": "failed"}], 2, 0
        ))
        self.assertEqual("manual_review", aggregate_status(
            [{"status": "manual_review"}], 0, 1
        ))

    def test_denovo_identifier_from_active_listing(self):
        row = {
            "evidence_id": "listing-1",
            "company_id": "c1",
            "k_number": "DEN240001",
            "legal_manufacturer": "Acme",
            "product_name": "Device",
            "device_class": "Class 2",
            "match_basis": "exact canonical name",
            "captured_at": "2026-07-28",
        }
        derived = denovo_from_registration(row)
        self.assertEqual("De Novo", derived["record_type"])
        self.assertIn("DEN240001", derived["evidence_url"])

    def test_integration_updates_canonical_company(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            companies = root / "companies.json"
            companies.write_text(json.dumps({
                "schema_version": "1.0",
                "companies": [{
                    "company_id": "c1",
                    "company_name": "Acme",
                    "completeness": {"regulatory": {"status": "not_run"}},
                }],
            }), encoding="utf-8")
            source_dirs = {}
            filenames = {
                "mdall": ("mdall_regulatory_evidence.json", "mdall_completeness.json", "mdall_manual_review.json"),
                "mdel": ("mdel_regulatory_evidence.json", "mdel_completeness.json", "mdel_manual_review.json"),
                "health_canada_trials": ("clinical_trial_regulatory_evidence.json", "clinical_trial_completeness.json", "clinical_trial_manual_review.json"),
                "fda": ("fda_regulatory_evidence.json", "fda_completeness.json", "fda_manual_review.json"),
                "fda_denovo": ("denovo_regulatory_evidence.json", "denovo_completeness.json", "denovo_manual_review.json"),
                "fda_registration": ("registration_regulatory_evidence.json", "registration_completeness.json", "registration_manual_review.json"),
            }
            for source, names in filenames.items():
                directory = root / source
                directory.mkdir()
                source_dirs[source] = directory
                evidence = [{
                    "evidence_id": "e1",
                    "company_id": "c1",
                    "authority": "Health Canada",
                    "record_type": "MDALL",
                    "record_id": "1",
                }] if source == "mdall" else []
                completeness = [{
                    "company_id": "c1", "company_name": "Acme",
                    "status": "complete_matches" if evidence else "complete_zero",
                    "raw_count": len(evidence), "accepted_count": len(evidence),
                }]
                for filename, records in zip(names, (evidence, completeness, [])):
                    (directory / filename).write_text(
                        json.dumps({"records": records}), encoding="utf-8"
                    )
            summary = integrate_regulatory_outputs(
                companies, source_dirs, root / "out", "2026-07-28"
            )
            self.assertEqual(1, summary["regulatory_evidence_records"])
            result = json.loads(
                (root / "out" / "canonical_companies_regulatory.json").read_text()
            )
            self.assertEqual(
                "complete_matches",
                result["companies"][0]["completeness"]["regulatory"]["status"],
            )
            self.assertIn("Health Canada MDALL: 1", result["companies"][0]["regulatory_summary"])


if __name__ == "__main__":
    unittest.main()
