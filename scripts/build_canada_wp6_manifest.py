from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any


INPUTS = {
    "canonical_companies": ("outputs/canada_company_identity_2026-07-27/canonical_companies.json", "companies"),
    "source_provenance": ("outputs/canada_company_identity_2026-07-27/source_provenance.json", "records"),
    "hiring_evidence": ("outputs/canada_hiring_wp2_final_2026-07-28/canonical_hiring_evidence.json", "records"),
    "hiring_companies": ("outputs/canada_hiring_wp2_final_2026-07-28/canonical_companies_hiring_wp2_complete.json", "companies"),
    "funding_events": ("outputs/canada_funding_2026-07-28/funding_events.json", "events"),
    "funding_backing": ("outputs/canada_funding_2026-07-28/funding_backing_evidence.json", "records"),
    "funding_companies": ("outputs/canada_funding_2026-07-28/canonical_companies_with_funding.json", "companies"),
    "regulatory_evidence": ("outputs/canada_regulatory_2026-07-28/regulatory_evidence.json", "records"),
    "regulatory_companies": ("outputs/canada_regulatory_2026-07-28/canonical_companies_regulatory.json", "companies"),
    "product_profiles": ("outputs/canada_product_news_2026-07-30/product_profiles.json", "profiles"),
    "product_news_completeness": ("outputs/canada_product_news_2026-07-30/product_news_completeness.json", "companies"),
    "verified_product_news": ("outputs/canada_product_news_2026-07-30/recent_verification/verified_recent_events.json", "events"),
    "duplicate_review": ("outputs/canada_company_identity_2026-07-27/duplicate_review.csv", None),
    "ambiguous_review": ("outputs/canada_company_identity_2026-07-27/ambiguous_name_review.csv", None),
    "baseline_builder": ("scripts/build_canada_wp6_workbook.mjs", None),
}


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def input_metadata(root: Path, relative: str, collection: str | None) -> dict[str, Any]:
    path = root / relative
    if not path.exists():
        raise FileNotFoundError(f"Required WP6 input is missing: {relative}")
    count = None
    generated_at = None
    schema_version = None
    if path.suffix.casefold() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        generated_at = payload.get("generated_at")
        schema_version = payload.get("schema_version")
        values = payload.get(collection, []) if collection else []
        count = len(values) if isinstance(values, list) else None
    elif path.suffix.casefold() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            count = sum(1 for _ in csv.DictReader(handle))
    return {
        "path": relative.replace("\\", "/"),
        "sha256": checksum(path),
        "bytes": path.stat().st_size,
        "record_count": count,
        "generated_at": generated_at,
        "schema_version": schema_version,
    }


def git_revision(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the reproducibility manifest for the audited WP6 release.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/canada_wp6_release_manifest_2026-07-30.json"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = {
        "schema_version": "1.0",
        "release_id": "canada-wp6-2026-07-30-baseline",
        "manifest_created_at": date.today().isoformat(),
        "git_revision": git_revision(root),
        "scoring_model": "WP6 V1 baseline; comparison only",
        "inputs": {
            name: input_metadata(root, relative, collection)
            for name, (relative, collection) in INPUTS.items()
        },
    }
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "inputs": len(manifest["inputs"])}))


if __name__ == "__main__":
    main()
