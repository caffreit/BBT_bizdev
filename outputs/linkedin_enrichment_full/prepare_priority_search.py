from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bbt_bizdev.adapters import linkedin as li
from bbt_bizdev.models import LinkedInContact


HERE = Path(__file__).resolve().parent
INPUT = HERE / "official_pilot_enrichment.json"
OUTPUT = HERE / "priority_search_enrichment.json"


def as_contact(payload: dict | None, bucket: str) -> LinkedInContact | None:
    if not payload:
        return None
    return LinkedInContact(
        payload["name"], payload["title"], payload["url"], bucket, "Official company site", 0.95
    )


def contact_dict(contact: LinkedInContact | None) -> dict | None:
    if contact is None:
        return None
    return {"name": contact.name, "title": contact.title, "url": contact.url}


def main() -> None:
    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    if len(rows) != 23:
        raise RuntimeError(f"Expected exactly 23 approved priority leads, got {len(rows)}")

    output = []
    for number, row in enumerate(rows, start=1):
        company_url = row["company_url"]
        company_status = row["company_status"]
        if not company_url:
            company_url, error = li._company_search_url(row["company"], row["website"], li.duckduckgo_search)
            company_status = "Found - public search" if company_url else "Search error" if error else "Not found"

        candidates = [
            contact
            for contact in (
                as_contact(row.get("executive"), "executive"),
                as_contact(row.get("technical"), "technical"),
                as_contact(row.get("quality"), "quality"),
            )
            if contact is not None
        ]
        executive, technical, quality = li.select_contacts(candidates)
        errors: list[str] = []
        if not all((executive, technical, quality)):
            searched, errors = li._contact_search_candidates(
                row["company"], row["website"], li.duckduckgo_search
            )
            candidates.extend(searched)
            executive, technical, quality = li.select_contacts(candidates)

        count = sum(contact is not None for contact in (executive, technical, quality))
        contact_status = (
            "Complete - 3 verified"
            if count == 3
            else f"Partial - {count}/3 verified"
            if count
            else "Search error"
            if errors
            else "No verified matches"
        )
        output.append(
            {
                "row": row["row"],
                "company": row["company"],
                "company_url": company_url,
                "company_status": company_status,
                "executive": contact_dict(executive),
                "technical": contact_dict(technical),
                "quality": contact_dict(quality),
                "contact_status": contact_status,
            }
        )
        print(f"{number}/23 {row['company']}: {company_status}; {contact_status}", flush=True)

    OUTPUT.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"wrote {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
