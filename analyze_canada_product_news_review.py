from __future__ import annotations

import argparse
import json
from pathlib import Path

from bbt_bizdev.canada_product_news_luna import deduplicate_events, validate_decision


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate narrow product/news verification-gate relaxations without changing production rules.")
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--companies", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()

    decisions = json.loads(args.decisions.read_text(encoding="utf-8-sig")).get("decisions", [])
    companies = json.loads(args.companies.read_text(encoding="utf-8-sig")).get("companies", [])
    profiles = json.loads(args.profiles.read_text(encoding="utf-8-sig")).get("profiles", [])
    company_by_id = {row["company_id"]: row for row in companies}
    profile_by_id = {row["company_id"]: row for row in profiles}

    eligible = [
        row for row in decisions
        if row.get("verification_status") == "needs_review"
        and (row.get("luna_decision") or {}).get("decision") == "verified"
        and (row.get("luna_decision") or {}).get("identity_confidence") == "high"
        and (row.get("luna_decision") or {}).get("confidence") == "medium"
        and (row.get("luna_decision") or {}).get("primary_url")
    ]
    trials, accepted = [], []
    for row in eligible:
        decision = {**row["luna_decision"], "confidence": "high"}
        company = company_by_id[row["company_id"]]
        validated = validate_decision(
            company, profile_by_id.get(row["company_id"], {}), row, decision, args.as_of,
        )
        trials.append({
            "candidate_id": row["candidate_id"], "company_id": row["company_id"],
            "company_name": row.get("company_name", ""),
            "event_type": decision.get("event_type", ""),
            "primary_url": decision.get("primary_url", ""),
            "trial_status": validated["verification_status"],
            "trial_notes": validated["verification_notes"],
        })
        if validated.get("accepted_event"):
            accepted.append(validated["accepted_event"])
    accepted = deduplicate_events(accepted)
    counts: dict[str, int] = {}
    for row in trials:
        counts[row["trial_status"]] = counts.get(row["trial_status"], 0) + 1
    payload = {
        "schema_version": "1.0", "as_of": args.as_of,
        "relaxation": "allow medium event confidence only when Luna marked verified, identity confidence is high, a qualifying primary URL exists, and all deterministic gates pass",
        "candidates_tested": len(trials), "trial_status_counts": counts,
        "deduplicated_events_that_would_be_accepted": len(accepted),
        "trials": trials, "events": accepted,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: payload[key] for key in (
        "candidates_tested", "trial_status_counts", "deduplicated_events_that_would_be_accepted",
    )}))


if __name__ == "__main__":
    main()
