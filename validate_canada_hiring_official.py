from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from bbt_bizdev.canada_hiring_official_validation import MODEL, run_official_validation


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate aggregator roles against employer or ATS sources.")
    parser.add_argument("--aggregator-evidence", type=Path, required=True)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--model", default=MODEL)
    args = parser.parse_args()
    summary, _ = run_official_validation(
        args.aggregator_evidence, args.canonical, args.output_dir,
        args.run_date, args.workers, args.model,
    )
    print(json.dumps({"output_dir": str(args.output_dir), **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
