from __future__ import annotations

import argparse
import json
from pathlib import Path

from bbt_bizdev.phone_extractor import run_extraction


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract public Irish business phone numbers from the TOFU pipeline.")
    parser.add_argument("--input", type=Path, default=Path("BlueBridge_TOFU_BizDev_V1_pipeline.xlsx"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/irish_phone_extractor_20260915"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-pages", type=int, default=6)
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary, files = run_extraction(
        args.input,
        args.output_dir,
        workers=args.workers,
        max_pages=args.max_pages,
        limit=args.limit,
        progress_fn=lambda done, total, result: print(
            f"[{done}/{total}] {result.company_name}: website={result.website_status}, phone={result.phone_status}",
            flush=True,
        ),
    )
    print(json.dumps({"summary": summary, "files": {key: str(value) for key, value in files.items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
