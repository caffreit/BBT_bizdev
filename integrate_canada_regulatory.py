from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from bbt_bizdev.canada_regulatory_integration import integrate_regulatory_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Combine Canada regulatory enrichment sources.")
    parser.add_argument(
        "--companies",
        type=Path,
        default=Path("outputs/canada_company_identity_2026-07-27/canonical_companies.json"),
    )
    parser.add_argument("--mdall-dir", type=Path, action="append", required=True)
    parser.add_argument("--mdel-dir", type=Path, action="append", required=True)
    parser.add_argument("--trials-dir", type=Path, action="append", required=True)
    parser.add_argument("--fda-dir", type=Path, action="append", required=True)
    parser.add_argument("--denovo-dir", type=Path, action="append", required=True)
    parser.add_argument("--registration-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--run-date", default=date.today().isoformat())
    args = parser.parse_args()
    output_dir = args.output_dir or Path("outputs") / f"canada_regulatory_{args.run_date}"
    summary = integrate_regulatory_outputs(
        args.companies,
        {
            "mdall": args.mdall_dir,
            "mdel": args.mdel_dir,
            "health_canada_trials": args.trials_dir,
            "fda": args.fda_dir,
            "fda_denovo": args.denovo_dir,
            "fda_registration": args.registration_dir,
        },
        output_dir,
        args.run_date,
    )
    print(json.dumps({"output_dir": str(output_dir), **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
