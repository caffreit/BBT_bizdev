from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from bbt_bizdev.canada_product_news_verification import run_recent_verification


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify and deduplicate recent Canadian product/news candidates.")
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("outputs/canada_product_news_2026-07-30/news_candidates.json"),
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--run-date", default=date.today().isoformat())
    args = parser.parse_args()
    output_dir = args.output_dir or args.candidates.parent / "recent_verification"
    summary = run_recent_verification(args.candidates, output_dir, args.run_date)
    print(json.dumps({"output_dir": str(output_dir), **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
