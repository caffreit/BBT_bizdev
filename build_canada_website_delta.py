from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build companies newly supplied with resolved canonical websites.")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--enriched", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8-sig")).get("companies", [])
    enriched_payload = json.loads(args.enriched.read_text(encoding="utf-8-sig"))
    enriched = enriched_payload.get("companies", [])
    old_websites = {row["company_id"]: row.get("website", "") for row in baseline}
    delta = [
        row for row in enriched
        if row.get("website") and not old_websites.get(row["company_id"])
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "schema_version": "1.0",
        "baseline": str(args.baseline),
        "enriched": str(args.enriched),
        "companies": delta,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"companies": len(delta), "output": str(args.output)}))


if __name__ == "__main__":
    main()
