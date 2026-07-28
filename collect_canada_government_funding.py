from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from bbt_bizdev.canada_government_funding import run_government_funding


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect exact-match Canadian federal grants.")
    parser.add_argument(
        "--companies",
        type=Path,
        default=Path("outputs/canada_funding_2026-07-28/canonical_companies_with_funding.json"),
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--all-companies", action="store_true")
    args = parser.parse_args()
    output_dir = args.output_dir or Path("outputs") / f"canada_government_funding_{args.run_date}"
    summary = run_government_funding(
        args.companies,
        output_dir,
        args.run_date,
        workers=args.workers,
        backed_only=not args.all_companies,
    )
    print(json.dumps({"output_dir": str(output_dir), **summary}))


if __name__ == "__main__":
    main()
