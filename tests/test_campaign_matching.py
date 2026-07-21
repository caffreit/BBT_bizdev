import csv
import json
import tempfile
import unittest
from pathlib import Path

from bbt_bizdev.campaign_matching import (
    export_approved,
    match_campaign,
    profile_request_payload,
    validate_profile,
)


def profile():
    empty = {"required": [], "preferred": [], "excluded": []}
    return {
        "campaign_name": "AI validation",
        "subject": "Your AUC isn't the hard part",
        "theme": "Defensible clinical validation evidence",
        "primary_service": "V&V",
        "company_targets": {
            "company_types": {"required": [], "preferred": ["Startup", "University spinout"], "excluded": []},
            "employee_bands": {"required": [], "preferred": ["1–10", "11–50"], "excluded": []},
            "maturity_stages": {"required": [], "preferred": ["Clinical/validation", "Regulatory"], "excluded": []},
            "product_profiles": {"required": ["AI-enabled health"], "preferred": ["SaMD/digital health"], "excluded": ["Non-regulated/wellness"]},
            "services": {"required": [], "preferred": ["V&V", "Regulatory support"], "excluded": []},
            "regulatory_signals": {"required": [], "preferred": ["Clinical study/validation"], "excluded": []},
        },
        "contact_targets": {
            "primary_functions": ["Founder/executive", "QA/regulatory"],
            "secondary_functions": ["R&D/engineering/product"],
            "excluded_functions": ["HR"],
            "preferred_seniorities": ["Executive", "Director/VP"],
            "preferred_buying_roles": ["Economic buyer / sponsor", "Technical buyer / influencer"],
            "title_keywords": ["founder", "quality", "regulatory", "validation"],
            "excluded_title_keywords": ["recruitment"],
            "business_unit_keywords": ["medical", "digital health"],
            "require_business_unit_match": False,
        },
        "company_score_threshold": 60,
        "contact_score_threshold": 65,
        "minimum_classification_confidence": 0.55,
        "rationale": "Targets regulated AI teams planning validation.",
        "confidence": 0.9,
    }


def company(company_id="company-1", company_type="Startup", product="AI-enabled health"):
    return {
        "company_id": company_id,
        "canonical_company": "Acme Medical",
        "domain": "acme.example",
        "company_type": company_type,
        "employee_band": "1–10",
        "maturity_stage": "Clinical/validation",
        "product_profile": product,
        "services": "V&V; Regulatory support",
        "regulatory_signals": "Clinical study/validation",
        "confidence": 0.8,
        "resolution_confidence": 0.95,
        "research_date": "2026-07-01",
        "evidence_summary": "AI medical device in clinical validation.",
        "evidence_urls": "https://acme.example/product",
        "source_urls": "https://acme.example/product",
    }


def contact(record_id="contact-1", email="alice@acme.example", title="Founder and CEO", function="Founder/executive", seniority="Executive", role="Economic buyer / sponsor"):
    return {
        "Record ID": record_id,
        "Company ID": "company-1",
        "Resolved Company": "Acme Medical",
        "First Name": "Alice",
        "Last Name": "Jones",
        "Email": email,
        "Job Title": title,
        "Contact Function": function,
        "Seniority": seniority,
        "Buying Role": role,
        "Duplicate Email": "No",
        "Outreach Angle": "Discuss validation evidence.",
    }


class CampaignMatchingTests(unittest.TestCase):
    def test_profile_validation_rejects_overlap(self):
        value = profile()
        value["company_targets"]["company_types"]["excluded"] = ["Startup"]
        with self.assertRaisesRegex(ValueError, "cannot also be"):
            validate_profile(value)

    def test_profile_request_contains_only_draft_and_taxonomy_not_lead_data(self):
        payload = profile_request_payload("Subject: Validation plan\nHello team", "openai/gpt-5.6-luna", "medium")
        serialized = json.dumps(payload)
        self.assertIn("Validation plan", serialized)
        self.assertNotIn("alice@acme.example", serialized)
        self.assertNotIn("Acme Medical", serialized)

    def test_matching_selects_one_primary_and_one_backup(self):
        enrichment = {"companies": [company()], "contacts": [contact(), contact("contact-2", "bob@acme.example", "Quality Director", "QA/regulatory", "Director/VP", "Technical buyer / influencer"), contact("contact-3", "cara@acme.example")]}
        result = match_campaign(enrichment, profile(), waive_suppression=True)
        selected = {row["Record ID"]: row for row in result["contact_decisions"]}
        self.assertEqual(selected["contact-1"]["Selection"], "Primary")
        self.assertEqual(selected["contact-3"]["Selection"], "Backup")
        self.assertEqual(selected["contact-2"]["Selection"], "Not retained")
        self.assertEqual(result["summary"]["primary_contacts"], 1)

    def test_explicit_company_exclusion_and_unknown_required_value_fail_closed(self):
        excluded = match_campaign({"companies": [company(product="Non-regulated/wellness")], "contacts": [contact()]}, profile(), waive_suppression=True)
        self.assertEqual(excluded["company_decisions"][0]["Decision"], "Excluded")
        unknown = match_campaign({"companies": [company(product="Unknown")], "contacts": [contact()]}, profile(), waive_suppression=True)
        self.assertEqual(unknown["company_decisions"][0]["Decision"], "Review")

    def test_enterprise_without_business_unit_can_qualify_but_is_warned(self):
        result = match_campaign({"companies": [company(company_type="Enterprise")], "contacts": [contact()]}, profile(), waive_suppression=True)
        row = result["contact_decisions"][0]
        self.assertEqual(row["Decision"], "Eligible")
        self.assertIn("business unit", row["Warnings"])

    def test_missing_title_and_generic_mailbox_are_review_only(self):
        result = match_campaign({"companies": [company()], "contacts": [contact(email="info@acme.example", title="", function="Other", seniority="Unknown", role="Role requires review")]}, profile(), waive_suppression=True)
        row = result["contact_decisions"][0]
        self.assertEqual(row["Decision"], "Review")
        self.assertIn("generic", row["Review Reasons"])

    def test_suppression_excludes_email_and_domain(self):
        with tempfile.TemporaryDirectory() as temp:
            suppression = Path(temp) / "suppress.csv"
            suppression.write_text("email,domain\nalice@acme.example,\n,blocked.example\n", encoding="utf-8")
            result = match_campaign({"companies": [company()], "contacts": [contact()]}, profile(), suppression_path=suppression)
        row = result["contact_decisions"][0]
        self.assertEqual(row["Decision"], "Excluded")
        self.assertEqual(row["Suppression Status"], "Suppressed email")

    def test_export_requires_suppression_or_waiver_and_deduplicates(self):
        rows = [{"Campaign": "AI validation", "Record ID": "1", "Company ID": "c", "Company": "Acme", "First Name": "A", "Last Name": "B", "Email": "a@acme.example", "Job Title": "CEO", "Selection": "Primary", "Approval Status": "Approved", "Personalisation Angle": "Validation", "Personalisation Evidence URL": "https://acme.example"}]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "recipients.csv"
            with self.assertRaisesRegex(ValueError, "suppression CSV"):
                export_approved(rows, output, None, False)
            count = export_approved(rows + rows, output, None, True)
            self.assertEqual(count, 1)
            with output.open(encoding="utf-8-sig") as handle:
                exported = list(csv.DictReader(handle))
            self.assertEqual(len(exported), 1)


if __name__ == "__main__":
    unittest.main()
