from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from bbt_bizdev.canada_aggregator_hiring import MODEL, run_aggregator_hiring


def main() -> None:
    parser = argparse.ArgumentParser(description="Find Canadian company roles through indexed aggregators.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--website-evidence", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--company-name", action="append", default=[])
    args = parser.parse_args()
    summary, _ = run_aggregator_hiring(
        args.input, args.website_evidence, args.output_dir, args.run_date,
        args.limit, args.workers, args.model, args.company_name or None,
    )
    print(json.dumps({"output_dir": str(args.output_dir), **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
