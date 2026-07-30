from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from bbt_bizdev.canada_product_news import run_product_news_enrichment


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich priority Canadian companies with first-party product pages and news candidates.")
    parser.add_argument(
        "--companies",
        type=Path,
        default=Path("outputs/canada_company_identity_2026-07-27/canonical_companies.json"),
    )
    parser.add_argument(
        "--regulatory",
        type=Path,
        default=Path("outputs/canada_regulatory_2026-07-28/canonical_companies_regulatory.json"),
    )
    parser.add_argument(
        "--funding",
        type=Path,
        default=Path("outputs/canada_funding_2026-07-28/canonical_companies_with_funding.json"),
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--delay", type=float, default=0.2)
    args = parser.parse_args()
    output_dir = args.output_dir or Path("outputs") / f"canada_product_news_{args.run_date}"
    summary = run_product_news_enrichment(
        args.companies,
        output_dir,
        args.run_date,
        limit=args.limit,
        regulatory_path=args.regulatory,
        funding_path=args.funding,
        delay=args.delay,
    )
    print(json.dumps({"output_dir": str(output_dir), **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
