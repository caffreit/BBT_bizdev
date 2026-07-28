from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from bbt_bizdev.canada_website_llm import MODEL, run_luna_resolution


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve Canadian company websites with Luna and grounded web search.")
    parser.add_argument(
        "--input", type=Path,
        default=Path("outputs/canada_website_probe_2026-07-28/canonical_companies_websites_enriched.json"),
    )
    parser.add_argument(
        "--provenance", type=Path,
        default=Path("outputs/canada_company_identity_2026-07-27/source_provenance.json"),
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--source-filter", default="")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--model", default=MODEL)
    args = parser.parse_args()
    output = args.output_dir or Path("outputs") / f"canada_website_luna_{args.run_date}_pilot"
    summary, _ = run_luna_resolution(
        args.input, args.provenance, output, args.run_date,
        args.source_filter, args.limit, args.max_workers, args.model,
    )
    print(json.dumps({"output_dir": str(output), **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
