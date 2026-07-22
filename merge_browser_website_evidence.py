from __future__ import annotations

import argparse
import json
from pathlib import Path

from bbt_bizdev.subscriber_enrichment import _review_row, classify_website_status


CHALLENGE_TITLES = (
    "403 forbidden",
    "403 - forbidden",
    "access is denied",
    "attention required",
    "just a moment",
    "dns points to prohibited ip",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-json", type=Path, required=True)
    parser.add_argument("--browser-evidence", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    evidence = json.loads(args.browser_evidence.read_text(encoding="utf-8"))
    by_id = {row["company_id"]: row for row in payload["companies"]}
    recovered = 0

    for item in evidence:
        row = by_id.get(item["company_id"])
        if not row or item.get("browser_status") != "Available in browser":
            continue
        title = str(item.get("title", "")).strip()
        headline = " | ".join(item.get("h1") or [])
        description = str(item.get("description", "")).strip()
        content = " ".join((title, headline, description)).strip()
        if not content or any(marker in content.lower() for marker in CHALLENGE_TITLES):
            continue

        final_url = str(item.get("final_url", "")).strip()
        status, redirect = classify_website_status(row["domain"], content, final_url)
        row["website_status"] = status
        row["redirect_target"] = redirect
        row["homepage_url"] = final_url
        row["source_urls"] = list(dict.fromkeys([final_url, *(row.get("source_urls") or [])]))
        row["evidence_urls"] = list(dict.fromkeys([final_url, *(row.get("evidence_urls") or [])]))
        row["errors"] = "; ".join(
            part.strip()
            for part in str(row.get("errors", "")).split(";")
            if part.strip() and not part.strip().startswith("Website unverified or blocked (")
        )
        row["method"] = f'{row.get("method", "")}; browser-verified first-party homepage'.strip("; ")
        recovered += 1

    prior_review = {row["Company ID"]: row for row in payload.get("review_queue", [])}
    payload["review_queue"] = [
        _review_row(row, prior_review.get(row["company_id"])) for row in payload["companies"]
    ]
    payload["stats"].update(
        {
            "website_failures": sum(row["website_status"] == "Unavailable" for row in payload["companies"]),
            "website_unverified_or_blocked": sum(
                row["website_status"] == "Unverified/Blocked" for row in payload["companies"]
            ),
            "browser_verified_recovered": recovered,
        }
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload["stats"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
