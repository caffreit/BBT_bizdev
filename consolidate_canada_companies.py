from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from bbt_bizdev.canada_consolidation import run_consolidation


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the canonical Canadian company identity table.")
    parser.add_argument("--input-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--previous", type=Path)
    parser.add_argument(
        "--overrides", type=Path, default=Path("data/canada_company_identity_overrides.json")
    )
    args = parser.parse_args()
    output_dir = args.output_dir or Path("outputs") / f"canada_company_identity_{args.run_date}"
    _, files = run_consolidation(
        args.input_dir, output_dir, args.run_date, args.previous, args.overrides
    )
    summary = json.loads(files["summary"].read_text(encoding="utf-8"))
    print(json.dumps({"output_dir": str(output_dir), **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
