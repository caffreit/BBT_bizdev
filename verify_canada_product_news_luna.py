from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from bbt_bizdev.canada_product_news_luna import MODEL, run_verification


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-verify Canadian product/news candidates with Luna and deterministic primary-source gates.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--companies", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--progress-every", type=int, default=10)
    parser.add_argument("--max-companies", type=int)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = run_verification(
        args.candidates, args.companies, args.profiles, args.output_dir, args.as_of,
        workers=args.workers, max_companies=args.max_companies, dry_run=args.dry_run,
        progress_every=args.progress_every, model=args.model,
    )
    print(json.dumps({"output_dir": str(args.output_dir), **summary}))


if __name__ == "__main__":
    main()
