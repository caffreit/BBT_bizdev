from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from bbt_bizdev.canada_hiring import run_hiring_enrichment


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich canonical Canadian companies with official hiring evidence.")
    parser.add_argument(
        "--input", type=Path,
        default=Path("outputs/canada_company_identity_2026-07-27/canonical_companies.json"),
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    output = args.output_dir or Path("outputs") / f"canada_hiring_{args.run_date}"
    summary, _ = run_hiring_enrichment(
        args.input, output, args.run_date, args.workers, args.limit
    )
    print(json.dumps({"output_dir": str(output), **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
