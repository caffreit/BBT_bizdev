from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from bbt_bizdev.canada_funding import run_funding_enrichment


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Canada institutional-backing and funding-event evidence.")
    parser.add_argument("--identity-dir", type=Path, default=Path("outputs/canada_company_identity_2026-07-27"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument(
        "--event-file",
        type=Path,
        action="append",
        default=[],
        help="Additional validated funding-event JSON payload; may be repeated.",
    )
    args = parser.parse_args()
    output_dir = args.output_dir or Path("outputs") / f"canada_funding_{args.run_date}"
    summary = run_funding_enrichment(
        args.identity_dir / "canonical_companies.json",
        args.identity_dir / "source_provenance.json",
        output_dir,
        args.run_date,
        event_paths=args.event_file,
    )
    print(json.dumps({"output_dir": str(output_dir), **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
