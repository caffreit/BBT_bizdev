from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from bbt_bizdev.canada_fda_denovo import run_denovo_enrichment


def main() -> None:
    parser = argparse.ArgumentParser(description="Match Canadian medtech companies to FDA De Novo records.")
    parser.add_argument(
        "--companies",
        type=Path,
        default=Path("outputs/canada_company_identity_2026-07-27/canonical_companies.json"),
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--company-id", action="append", default=[])
    args = parser.parse_args()
    output_dir = args.output_dir or Path("outputs") / f"canada_regulatory_denovo_{args.run_date}"
    summary = run_denovo_enrichment(
        args.companies,
        output_dir,
        args.run_date,
        workers=args.workers,
        company_ids=set(args.company_id) or None,
    )
    print(json.dumps({"output_dir": str(output_dir), **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
