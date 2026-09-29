"""Summarize the current 25-company executive pilot without conflating workflow status and coverage."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research_canada_executives import OUT, pilot


def category(company: dict, selected_count: int, pending_count: int) -> str:
    if selected_count >= 3:
        return "complete_three"
    if selected_count:
        return "partial_contacts"
    if not company.get("website"):
        return "website_unverified"
    if company.get("status") == "inactive_needs_review":
        return "activity_needs_review"
    if any("HTTP Error 403" in error for error in company.get("errors", [])):
        return "official_site_blocked"
    if pending_count:
        return "candidate_evidence_review"
    return "no_verified_candidate"


def main() -> None:
    companies = pilot(json.loads((OUT / "companies.json").read_text(encoding="utf-8")))
    selected = json.loads((OUT / "selected.json").read_text(encoding="utf-8"))
    with (OUT / "decisions.csv").open(newline="", encoding="utf-8") as handle:
        decisions = list(csv.DictReader(handle))
    output = OUT / "Pilot_25_Coverage.csv"
    fields = ["source_row", "company", "verified_contacts", "pending_candidates", "coverage_category",
              "working_website", "source_website", "research_status", "fetch_errors"]
    counts: dict[str, int] = {}
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        for company in companies:
            row_id = company["row_id"]
            verified = sum(row["row_id"] == row_id for row in selected)
            pending = sum(row["row_id"] == row_id and row["decision"] == "pending" for row in decisions)
            group = category(company, verified, pending)
            counts[group] = counts.get(group, 0) + 1
            writer.writerow({"source_row": company["source_row"], "company": company["company"],
                             "verified_contacts": verified, "pending_candidates": pending,
                             "coverage_category": group, "working_website": company.get("website", ""),
                             "source_website": company.get("source_website", company.get("website", "")),
                             "research_status": company.get("status", ""),
                             "fetch_errors": "; ".join(company.get("errors", []))})
    assert len(companies) == 25 and sum(counts.values()) == 25
    print(json.dumps({"output": str(output), "companies": 25, "verified_contacts": len(selected),
                      "coverage_categories": counts}))


if __name__ == "__main__":
    main()
