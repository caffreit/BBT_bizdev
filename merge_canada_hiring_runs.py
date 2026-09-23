from __future__ import annotations

import argparse
import json
from pathlib import Path


STATUS_RANK = {
    "complete_matches": 6,
    "complete_zero": 5,
    "manual_review": 4,
    "partial": 3,
    "blocked": 2,
    "no_source": 1,
    "failed": 0,
    "not_run": 0,
}


def choose_records(runs: list[list[dict]]) -> list[dict]:
    chosen: dict[str, dict] = {}
    for records in runs:
        for row in records:
            company_id = row["company_id"]
            current = chosen.get(company_id)
            if current is None or STATUS_RANK.get(row.get("status", ""), 0) >= STATUS_RANK.get(current.get("status", ""), 0):
                chosen[company_id] = row
    return sorted(chosen.values(), key=lambda row: (row.get("company_name", "").casefold(), row["company_id"]))


def load_records(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8-sig")).get("records", [])


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge Canada hiring runs using the strongest auditable result per company.")
    parser.add_argument("--run-dir", type=Path, action="append", required=True)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-date", required=True)
    args = parser.parse_args()

    completeness_runs = [load_records(path / "hiring_completeness.json") for path in args.run_dir]
    selected = choose_records(completeness_runs)
    selected_by_id = {row["company_id"]: row for row in selected}
    evidence_by_id: dict[str, dict] = {}
    for path in args.run_dir:
        for row in load_records(path / "hiring_evidence.json"):
            evidence_by_id[row["evidence_id"]] = row
    evidence = sorted(evidence_by_id.values(), key=lambda row: (row["company_id"], row["evidence_id"]))

    canonical_payload = json.loads(args.canonical.read_text(encoding="utf-8-sig"))
    companies = []
    for company in canonical_payload.get("companies", []):
        copied = json.loads(json.dumps(company))
        row = selected_by_id.get(company["company_id"])
        if row:
            copied.setdefault("completeness", {})["hiring"] = {
                "status": row["status"], "attempted_at": row.get("attempted_at"),
                "source_url": row.get("careers_url", ""), "raw_count": row.get("raw_count"),
                "accepted_count": row.get("accepted_count"), "notes": row.get("notes", ""),
            }
            copied["last_enriched_at"] = args.run_date
        companies.append(copied)

    counts: dict[str, int] = {}
    for row in selected:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    complete = counts.get("complete_matches", 0) + counts.get("complete_zero", 0)
    summary = {
        "schema_version": "1.0", "generated_at": args.run_date,
        "source_runs": [str(path) for path in args.run_dir],
        "canonical_companies": len(companies), "companies_merged": len(selected),
        "status_counts": counts, "complete_or_complete_zero": complete,
        "completion_rate": round(complete / len(selected), 4) if selected else 0,
        "evidence_records": len(evidence),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "hiring_completeness.json").write_text(json.dumps({"schema_version": "1.0", "generated_at": args.run_date, "records": selected}, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.output_dir / "hiring_evidence.json").write_text(json.dumps({"schema_version": "1.0", "generated_at": args.run_date, "records": evidence}, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.output_dir / "canonical_companies_hiring_enriched.json").write_text(json.dumps({"schema_version": "1.0", "generated_at": args.run_date, "companies": companies}, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
