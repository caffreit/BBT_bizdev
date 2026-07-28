"""Build the canonical, official-only hiring dataset for work package 2."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _domain(url: str) -> str:
    host = urlparse(url or "").netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _company_identity(company: dict) -> str:
    return (
        company.get("domain")
        or _domain(company.get("website", ""))
        or f"name:{_norm(company.get('company_name', ''))}"
    )


def merge_official_roles(
    official_records: list[dict],
    validation_records: list[dict],
    companies: list[dict],
) -> list[dict]:
    """Merge and deduplicate official evidence, preferring direct career-run records."""
    company_by_id = {c["company_id"]: c for c in companies}
    identity_by_id = {cid: _company_identity(c) for cid, c in company_by_id.items()}
    merged: dict[tuple[str, str], dict] = {}

    for record in official_records:
        company = company_by_id.get(record.get("company_id"), {})
        item = dict(record)
        item["company_name"] = company.get("company_name", "")
        item["company_domain"] = company.get("domain") or _domain(company.get("website", ""))
        item["discovery_source"] = "official_careers_run"
        item["validation_method"] = "direct_official_careers"
        item["validated_at"] = record.get("captured_at")
        item["evidence_date"] = (
            record.get("evidence_date")
            or record.get("posted_at")
            or record.get("captured_at")
        )
        key = (
            identity_by_id.get(record.get("company_id"), record.get("company_id", "")),
            _norm(record.get("job_title", "")),
        )
        merged[key] = item

    for record in validation_records:
        if record.get("validation_status") != "official_open":
            continue
        key = (
            identity_by_id.get(record.get("company_id"), record.get("company_id", "")),
            _norm(record.get("job_title", "")),
        )
        if key in merged:
            continue
        company = company_by_id.get(record.get("company_id"), {})
        item = {
            "company_id": record.get("company_id", ""),
            "company_name": record.get("company_name") or company.get("company_name", ""),
            "company_domain": company.get("domain") or _domain(company.get("website", "")),
            "job_title": record.get("job_title", ""),
            "department": record.get("department", ""),
            "location": record.get("location", ""),
            "remote_canada": record.get("remote_canada", "unclear"),
            "posted_at": record.get("posted_at", ""),
            "job_url": record.get("official_job_url", ""),
            "evidence_url": record.get("official_job_url", ""),
            "aggregator_url": record.get("job_url", ""),
            "role_family": record.get("role_family", ""),
            "seniority": record.get("seniority", ""),
            "posting_status": "open",
            "confidence": "high",
            "captured_at": record.get("validated_at", ""),
            "evidence_date": (
                record.get("posted_at")
                if record.get("posted_at") not in ("", "Not stated", None)
                else record.get("validated_at", "")
            ),
            "discovery_source": record.get("source", ""),
            "official_source_type": record.get("official_source_type", ""),
            "validation_method": record.get("validation_method", ""),
            "validation_notes": record.get("validation_notes", ""),
            "validated_at": record.get("validated_at", ""),
        }
        merged[key] = item

    return sorted(
        merged.values(),
        key=lambda r: (_norm(r.get("company_name", "")), _norm(r.get("job_title", ""))),
    )


def update_companies(companies: list[dict], roles: list[dict], run_date: str) -> list[dict]:
    by_company: dict[str, list[dict]] = defaultdict(list)
    for role in roles:
        by_company[role["company_id"]].append(role)
    for company in companies:
        matches = by_company.get(company["company_id"], [])
        if matches:
            company["completeness"]["hiring"] = {
                "status": "complete_matches",
                "attempted_at": run_date,
                "source_url": matches[0].get("job_url", ""),
                "raw_count": len(matches),
                "accepted_count": len(matches),
                "notes": "WP2 official-only consolidated hiring evidence",
            }
        company["last_enriched_at"] = run_date
    return companies


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-evidence", type=Path, required=True)
    parser.add_argument("--validation-evidence", type=Path, required=True)
    parser.add_argument("--aggregator-evidence", type=Path, required=True)
    parser.add_argument("--aggregator-completeness", type=Path, required=True)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-date", required=True)
    args = parser.parse_args()

    official = _load(args.official_evidence)["records"]
    validation = _load(args.validation_evidence)["records"]
    aggregator = _load(args.aggregator_evidence)["records"]
    completeness = _load(args.aggregator_completeness)["records"]
    canonical_doc = _load(args.canonical)
    companies = canonical_doc["companies"]
    company_by_id = {c["company_id"]: c for c in companies}
    identity_by_id = {cid: _company_identity(c) for cid, c in company_by_id.items()}

    roles = merge_official_roles(official, validation, companies)
    validated_keys = {
        (
            identity_by_id.get(r.get("company_id"), r.get("company_id", "")),
            _norm(r.get("job_title", "")),
        )
        for r in validation
        if r.get("validation_status") == "official_open"
    }
    validation_by_key = {
        (
            identity_by_id.get(r.get("company_id"), r.get("company_id", "")),
            _norm(r.get("job_title", "")),
        ): r
        for r in validation
    }
    backlog = []
    seen = set()
    for record in aggregator:
        key = (
            identity_by_id.get(record.get("company_id"), record.get("company_id", "")),
            _norm(record.get("job_title", "")),
        )
        if key in validated_keys or key in seen:
            continue
        seen.add(key)
        item = dict(record)
        check = validation_by_key.get(key)
        item["review_reason"] = (
            f"high_confidence_{check.get('validation_status')}"
            if check
            else "medium_confidence_not_officially_validated"
        )
        backlog.append(item)
    manual_companies = [
        {
            "company_id": r.get("company_id", ""),
            "company_name": r.get("company_name", ""),
            "review_reason": "aggregator_search_manual_review",
            "notes": r.get("notes", ""),
        }
        for r in completeness
        if r.get("status") == "manual_review"
    ]

    companies = update_companies(companies, roles, args.run_date)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "canonical_hiring_evidence.json").write_text(
        json.dumps(
            {"schema_version": "1.0", "generated_at": args.run_date, "records": roles},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (args.output_dir / "canonical_companies_hiring_wp2_complete.json").write_text(
        json.dumps(
            {
                "schema_version": canonical_doc.get("schema_version", "1.0"),
                "generated_at": args.run_date,
                "companies": companies,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (args.output_dir / "hiring_review_backlog.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": args.run_date,
                "role_records": backlog,
                "manual_review_companies": manual_companies,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    fieldnames = [
        "company_name", "job_title", "role_family", "seniority", "department",
        "location", "posted_at", "job_url", "aggregator_url", "discovery_source",
        "validation_method", "validated_at", "company_id",
    ]
    with (args.output_dir / "canonical_hiring_roles.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(roles)

    summary = {
        "schema_version": "1.0",
        "generated_at": args.run_date,
        "companies_total": len(companies),
        "official_careers_roles_input": len(official),
        "aggregator_high_roles_validated": len(validation),
        "validation_status_counts": dict(Counter(r["validation_status"] for r in validation)),
        "canonical_official_open_roles": len(roles),
        "companies_with_official_open_roles": len({r["company_id"] for r in roles}),
        "role_review_backlog": len(backlog),
        "manual_review_companies": len(manual_companies),
    }
    (args.output_dir / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
