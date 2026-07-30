from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from bbt_bizdev.canada_fda import run_fda_enrichment, run_fda_enrichment_bulk


def main() -> None:
    parser = argparse.ArgumentParser(description="Match Canadian medtech companies to FDA 510(k) and PMA records.")
    parser.add_argument(
        "--companies",
        type=Path,
        default=Path("outputs/canada_company_identity_2026-07-27/canonical_companies.json"),
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--company-id", action="append", default=[])
    parser.add_argument(
        "--per-company",
        action="store_true",
        help="Use targeted per-company queries, primarily for retrying failed bulk batches.",
    )
    args = parser.parse_args()
    output_dir = args.output_dir or Path("outputs") / f"canada_regulatory_fda_{args.run_date}"
    if args.per_company:
        summary = run_fda_enrichment(
            args.companies,
            output_dir,
            args.run_date,
            workers=args.workers,
            company_ids=set(args.company_id) or None,
        )
    else:
        summary = run_fda_enrichment_bulk(
            args.companies,
            output_dir,
            args.run_date,
            company_ids=set(args.company_id) or None,
        )
    print(json.dumps({"output_dir": str(output_dir), **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
