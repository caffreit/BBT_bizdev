from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path


def select_sample(records: list[dict], *, seed: int = 20260804) -> list[dict]:
    eligible = [row for row in records if row.get("eligible")]
    eligible.sort(key=lambda row: int(row.get("rank") or 10**9))
    selected: list[dict] = []
    used: set[str] = set()

    def add(rows: list[dict], stratum: str) -> None:
        for row in rows:
            company_id = str(row.get("company_id") or "")
            if not company_id or company_id in used:
                continue
            used.add(company_id)
            selected.append({"audit_stratum": stratum, **row})

    add(eligible[:50], "top_50")
    add(eligible[50:75], "cutoff_band")
    remainder = [row for row in eligible[75:] if row.get("company_id") not in used]
    rng = random.Random(seed)
    add(rng.sample(remainder, min(25, len(remainder))), "random_remainder")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a deterministic stratified audit sample for Canada Scoring V2.")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260804)
    args = parser.parse_args()

    payload = json.loads(args.results.read_text(encoding="utf-8-sig"))
    sample = select_sample(payload.get("records", []), seed=args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "audit_sample.json").write_text(
        json.dumps({"schema_version": "1.0", "seed": args.seed, "records": sample}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    columns = [
        "audit_stratum", "rank", "company_id", "company_name", "priority_score",
        "evidence_confidence", "comparable_coverage", "missing_data_flags",
        "auditor_score_correct", "auditor_evidence_correct", "auditor_notes",
    ]
    with (args.output_dir / "audit_sample.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in sample:
            writer.writerow({
                **{column: row.get(column, "") for column in columns},
                "missing_data_flags": "; ".join(row.get("missing_data_flags", [])),
            })
    print(json.dumps({
        "sample_size": len(sample),
        "strata": {
            name: sum(row["audit_stratum"] == name for row in sample)
            for name in ("top_50", "cutoff_band", "random_remainder")
        },
    }))


if __name__ == "__main__":
    main()
