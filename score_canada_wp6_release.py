from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from bbt_bizdev.canada_scoring_integration import build_scoring_inputs, score_universe


def load(root: Path, filename: str, key: str) -> list[dict]:
    return json.loads((root / filename).read_text(encoding="utf-8-sig")).get(key, [])


def main() -> None:
    parser = argparse.ArgumentParser(description="Score a consolidated Canada WP6 release using deterministic Scoring V2.")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()
    inputs = build_scoring_inputs(
        load(args.data_dir, "canonical_companies.json", "companies"),
        provenance=load(args.data_dir, "source_provenance.json", "records"),
        hiring=load(args.data_dir, "hiring_evidence.json", "records"),
        hiring_companies=load(args.data_dir, "canonical_companies_hiring.json", "companies"),
        funding_events=load(args.data_dir, "funding_events.json", "events"),
        backing=load(args.data_dir, "funding_backing_evidence.json", "records"),
        funding_companies=load(args.data_dir, "canonical_companies_funding.json", "companies"),
        regulatory=load(args.data_dir, "regulatory_evidence.json", "records"),
        regulatory_companies=load(args.data_dir, "canonical_companies_regulatory.json", "companies"),
        product_profiles=load(args.data_dir, "product_profiles.json", "profiles"),
        product_events=load(args.data_dir, "product_news_events.json", "events"),
        product_completeness=load(args.data_dir, "product_news_completeness.json", "companies"),
    )
    result = score_universe(inputs, args.as_of)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "scoring_inputs.json").write_text(json.dumps({"schema_version": "2.0", "generated_at": args.as_of, "companies": inputs}, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.output_dir / "scoring_results.json").write_text(json.dumps({"schema_version": "2.0", "generated_at": args.as_of, **result}, indent=2, ensure_ascii=False), encoding="utf-8")
    columns = ["rank", "company_id", "company_name", "priority_score", "fit", "timing", "ability_to_buy", "canada_relevance", "evidence_confidence", "comparable_coverage", "missing_data_flags"]
    with (args.output_dir / "scoring_results.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in result["records"]:
            writer.writerow({**{column: row.get(column) for column in columns}, "missing_data_flags": "; ".join(row.get("missing_data_flags", []))})
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
