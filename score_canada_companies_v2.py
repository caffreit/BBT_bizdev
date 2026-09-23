from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path

from bbt_bizdev.canada_scoring_integration import build_scoring_inputs, score_universe


def load(path: Path, key: str) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8-sig")).get(key, [])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic Canada Scoring V2 diagnostic outputs.")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/canada_scoring_v2_diagnostic"))
    args = parser.parse_args()
    inputs = build_scoring_inputs(
        load(Path("outputs/canada_company_identity_2026-07-27/canonical_companies.json"), "companies"),
        provenance=load(Path("outputs/canada_company_identity_2026-07-27/source_provenance.json"), "records"),
        hiring=load(Path("outputs/canada_hiring_wp2_final_2026-07-28/canonical_hiring_evidence.json"), "records"),
        hiring_companies=load(Path("outputs/canada_hiring_wp2_final_2026-07-28/canonical_companies_hiring_wp2_complete.json"), "companies"),
        funding_events=load(Path("outputs/canada_funding_2026-07-28/funding_events.json"), "events"),
        backing=load(Path("outputs/canada_funding_2026-07-28/funding_backing_evidence.json"), "records"),
        funding_companies=load(Path("outputs/canada_funding_2026-07-28/canonical_companies_with_funding.json"), "companies"),
        regulatory=load(Path("outputs/canada_regulatory_2026-07-28/regulatory_evidence.json"), "records"),
        regulatory_companies=load(Path("outputs/canada_regulatory_2026-07-28/canonical_companies_regulatory.json"), "companies"),
        product_profiles=load(Path("outputs/canada_product_news_2026-07-30/product_profiles.json"), "profiles"),
        product_events=load(Path("outputs/canada_product_news_2026-07-30/recent_verification/verified_recent_events.json"), "events"),
        product_completeness=load(Path("outputs/canada_product_news_2026-07-30/product_news_completeness.json"), "companies"),
    )
    result = score_universe(inputs, args.as_of)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "scoring_inputs.json").write_text(
        json.dumps({"schema_version": "2.0", "generated_at": args.as_of, "companies": inputs}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (args.output_dir / "scoring_results.json").write_text(
        json.dumps({"schema_version": "2.0", "generated_at": args.as_of, **result}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    with (args.output_dir / "scoring_results.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        columns = [
            "rank", "company_id", "company_name", "eligible", "priority_score",
            "fit", "timing", "ability_to_buy", "canada_relevance",
            "evidence_confidence", "comparable_coverage", "missing_data_flags",
        ]
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in result["records"]:
            writer.writerow({
                **{column: row.get(column) for column in columns},
                "missing_data_flags": "; ".join(row.get("missing_data_flags", [])),
            })
    print(json.dumps({"output_dir": str(args.output_dir), **result["summary"]}))


if __name__ == "__main__":
    main()
