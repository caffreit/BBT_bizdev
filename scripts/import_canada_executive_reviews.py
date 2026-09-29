"""Import evidence-reviewed public contacts into the WP6 research ledger."""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research_canada_executives import OUT, FIELDS, candidate_id, pilot, read_csv, write_csv
from bbt_bizdev.adapters.linkedin import canonicalize_linkedin_url


def main() -> None:
    companies_path = OUT / "companies.json"
    companies = json.loads(companies_path.read_text(encoding="utf-8"))
    pilot_by_id = {row["row_id"]: row for row in pilot(companies)}
    existing = read_csv(OUT / "decisions.csv")
    by_id = {row["candidate_id"]: row for row in existing}
    additions = read_csv(OUT / "reviewed_additions.csv")
    for row in additions:
        row_id = row["row_id"]
        if row_id not in pilot_by_id:
            raise ValueError(f"Not in pilot: {row_id}")
        linkedin = canonicalize_linkedin_url(row["linkedin_url"], "person")
        if not linkedin or not row["role_url"] or not row["linkedin_evidence_url"]:
            raise ValueError(f"Incomplete evidence: {row_id} {row['name']}")
        if row["email"] and not row["email_evidence_url"]:
            raise ValueError(f"Email lacks source: {row_id} {row['name']}")
        cid = candidate_id(row_id, linkedin, row["name"])
        prior = by_id.get(cid, {})
        by_id[cid] = {**prior, "candidate_id": cid, "row_id": row_id,
                      "company": pilot_by_id[row_id]["company"], "name": row["name"],
                      "title": row["title"], "linkedin_url": linkedin,
                      "email": row["email"], "phone": "", "role_url": row["role_url"],
                      "linkedin_evidence_url": row["linkedin_evidence_url"],
                      "email_evidence_url": row["email_evidence_url"], "phone_evidence_url": "",
                      "identity_verified": "yes", "employment_verified": "yes",
                      "linkedin_verified": "yes", "decision": "accept",
                      "reason": "reviewed_public_evidence: " + row["evidence_note"],
                      "checked_at": date.today().isoformat()}
        pilot_by_id[row_id]["status"] = "reviewed_verified"
    write_csv(OUT / "decisions.csv", list(by_id.values()), FIELDS)
    companies_path.write_text(json.dumps(companies, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"reviewed_additions": len(additions), "companies": len({r['row_id'] for r in additions})}))


if __name__ == "__main__":
    main()
