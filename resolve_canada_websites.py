from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from bbt_bizdev.canada_websites import run_website_resolution


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve official websites for canonical Canadian companies.")
    parser.add_argument(
        "--input", type=Path,
        default=Path("outputs/canada_company_identity_2026-07-27/canonical_companies.json"),
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--limit", type=int)
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    output = args.output_dir or Path("outputs") / f"canada_website_resolution_{args.run_date}"
    summary, _ = run_website_resolution(
        args.input, output, args.run_date, args.limit,
        probe_only=args.probe_only, workers=args.workers,
    )
    print(json.dumps({"output_dir": str(output), **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
