from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

from bbt_bizdev.canada_consolidation import normalize_name
from bbt_bizdev.canada_fda import _get_json, fetch_all, result_records
from bbt_bizdev.canada_regulatory import RELEVANT_CATEGORIES, exact_query_names


ENDPOINT = "https://api.fda.gov/device/registrationlisting.json"


def query_url(name: str) -> str:
    return ENDPOINT + "?" + urlencode({
        "search": f'registration.name:"{name}"',
        "limit": 1000,
    })


def record_key(record: dict[str, Any]) -> str:
    registration = record.get("registration") or {}
    products = record.get("products") or []
    product_codes = sorted(
        str(row.get("product_code") or "") for row in products if isinstance(row, dict)
    )
    value = "|".join([
        str(registration.get("registration_number") or ""),
        str(record.get("k_number") or ""),
        str(record.get("pma_number") or ""),
        ";".join(product_codes),
        ";".join(sorted(str(value) for value in record.get("proprietary_name") or [])),
    ])
    return value


def _evidence_id(company_id: str, key: str) -> str:
    digest = hashlib.sha256(
        f"{company_id}|FDA|registration listing|{key}".encode("utf-8")
    ).hexdigest()[:20]
    return "ca-regulatory-evidence-" + digest


def to_evidence(
    company: dict[str, Any],
    record: dict[str, Any],
    captured_at: str,
    matched_name: str,
) -> dict[str, Any]:
    registration = record.get("registration") or {}
    products = [row for row in record.get("products") or [] if isinstance(row, dict)]
    establishment = str(registration.get("name") or "").strip()
    legal = normalize_name(company.get("legal_name", ""))
    canonical = normalize_name(company.get("company_name", ""))
    match_basis = (
        "exact legal name" if legal and normalize_name(establishment) == legal
        else "exact canonical name" if normalize_name(establishment) == canonical
        else "known alias"
    )
    product_names = sorted({
        str(value).strip() for value in record.get("proprietary_name") or []
        if str(value).strip()
    })
    classes = sorted({
        str((row.get("openfda") or {}).get("device_class") or "")
        for row in products if (row.get("openfda") or {}).get("device_class")
    })
    key = record_key(record)
    return {
        "evidence_id": _evidence_id(company["company_id"], key),
        "company_id": company["company_id"],
        "track": "regulatory",
        "claim_type": "FDA device registration and listing",
        "jurisdiction": "US",
        "authority": "FDA",
        "record_type": "listing",
        "record_id": key,
        "legal_manufacturer": establishment,
        "product_name": "; ".join(product_names),
        "device_class": "; ".join(f"Class {value}" for value in classes),
        "status": "registered",
        "decision_or_start_date": None,
        "evidence_url": query_url(matched_name),
        "evidence_date": None,
        "captured_at": captured_at,
        "extraction_method": "openfda_registration_listing_exact_establishment_match",
        "source_type": "regulator",
        "match_basis": match_basis,
        "matched_query_name": matched_name,
        "confidence": "high",
        "registration_number": registration.get("registration_number"),
        "fei_number": registration.get("fei_number"),
        "registration_expiry_year": registration.get("reg_expiry_date_year"),
        "establishment_types": record.get("establishment_type") or [],
        "k_number": record.get("k_number"),
        "pma_number": record.get("pma_number"),
        "product_codes": [
            row.get("product_code") for row in products if row.get("product_code")
        ],
        "interpretation_note": "FDA establishment registration/device listing; not itself premarket clearance or approval.",
        "raw_record": record,
    }


def collect_company(
    company: dict[str, Any],
    getter: Callable[[str], dict[str, Any]] = _get_json,
) -> dict[str, Any]:
    records, queries, errors = [], [], []
    for name in exact_query_names(company):
        url = query_url(name)
        try:
            rows = result_records(getter(url))
        except Exception as exc:
            rows = []
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
        queries.append({"query_name": name, "url": url, "result_count": len(rows)})
        records.extend((row, name) for row in rows)
    return {"company": company, "records": records, "queries": queries, "errors": errors}


def run_registration_enrichment(
    companies_path: Path,
    output_dir: Path,
    run_date: str | None = None,
    workers: int = 2,
    company_ids: set[str] | None = None,
    getter: Callable[[str], dict[str, Any]] = _get_json,
) -> dict[str, Any]:
    run_date = run_date or date.today().isoformat()
    companies = json.loads(companies_path.read_text(encoding="utf-8"))["companies"]
    companies = [
        row for row in companies
        if str(row.get("product_category") or "").casefold()
        in {value.casefold() for value in RELEVANT_CATEGORIES}
    ]
    if company_ids:
        companies = [row for row in companies if row["company_id"] in company_ids]
    owners: dict[str, set[str]] = defaultdict(set)
    for company in companies:
        for name in exact_query_names(company):
            owners[normalize_name(name)].add(company["company_id"])

    results = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(collect_company, row, getter) for row in companies]
        for future in as_completed(futures):
            results.append(future.result())

    evidence, review, completeness, audit = [], [], [], []
    for result in sorted(results, key=lambda row: row["company"]["company_name"].casefold()):
        company = result["company"]
        accepted_names = {normalize_name(name): name for name in exact_query_names(company)}
        company_evidence = []
        for record, matched_name in result["records"]:
            establishment = str((record.get("registration") or {}).get("name") or "")
            normalized = normalize_name(establishment)
            reason = ""
            if normalized not in accepted_names:
                reason = "non_exact_fda_establishment_name"
            elif len(owners.get(normalized, set())) != 1:
                reason = "ambiguous_canonical_name"
            if reason:
                review.append({
                    "company_id": company["company_id"],
                    "company_name": company["company_name"],
                    "review_reason": reason,
                    "candidate": record,
                })
            else:
                company_evidence.append(to_evidence(
                    company, record, run_date, accepted_names[normalized]
                ))
        company_evidence = list({row["evidence_id"]: row for row in company_evidence}.values())
        evidence.extend(company_evidence)
        audit.extend({
            "company_id": company["company_id"],
            "company_name": company["company_name"],
            **query,
        } for query in result["queries"])
        has_review = any(row["company_id"] == company["company_id"] for row in review)
        status = (
            "partial" if result["errors"] and (result["records"] or company_evidence)
            else "failed" if result["errors"]
            else "manual_review" if has_review and not company_evidence
            else "complete_matches" if company_evidence
            else "complete_zero"
        )
        completeness.append({
            "company_id": company["company_id"],
            "company_name": company["company_name"],
            "status": status,
            "attempted_at": run_date,
            "source_url": ENDPOINT,
            "raw_count": len(result["records"]),
            "accepted_count": len(company_evidence),
            "notes": "; ".join(result["errors"]) or (
                "openFDA registration/listing searched by exact establishment name; "
                "listing is not itself clearance or approval."
            ),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "registration_regulatory_evidence.json": {"schema_version": "1.0", "generated_at": run_date, "records": evidence},
        "registration_completeness.json": {"schema_version": "1.0", "generated_at": run_date, "records": completeness},
        "registration_manual_review.json": {"schema_version": "1.0", "generated_at": run_date, "records": review},
        "registration_query_audit.json": {"schema_version": "1.0", "generated_at": run_date, "records": audit},
    }
    for filename, payload in outputs.items():
        (output_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    summary = {
        "schema_version": "1.0",
        "generated_at": run_date,
        "companies_searched": len(companies),
        "companies_with_records": len({row["company_id"] for row in evidence}),
        "listing_records": len(evidence),
        "manual_review_candidates": len(review),
        "failed_companies": sum(row["status"] == "failed" for row in completeness),
        "partial_companies": sum(row["status"] == "partial" for row in completeness),
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def run_registration_enrichment_bulk(
    companies_path: Path,
    output_dir: Path,
    run_date: str | None = None,
    company_ids: set[str] | None = None,
    getter: Callable[[str], dict[str, Any]] = _get_json,
) -> dict[str, Any]:
    run_date = run_date or date.today().isoformat()
    companies = json.loads(companies_path.read_text(encoding="utf-8"))["companies"]
    companies = [
        row for row in companies
        if str(row.get("product_category") or "").casefold()
        in {value.casefold() for value in RELEVANT_CATEGORIES}
    ]
    if company_ids:
        companies = [row for row in companies if row["company_id"] in company_ids]
    owners: dict[str, set[str]] = defaultdict(set)
    display_names: dict[str, str] = {}
    for company in companies:
        for name in exact_query_names(company):
            normalized = normalize_name(name)
            owners[normalized].add(company["company_id"])
            display_names.setdefault(normalized, name)

    errors, audit = [], []
    try:
        raw_records, audit = fetch_all(
            ENDPOINT, 'registration.iso_country_code:"CA"', getter
        )
    except Exception as exc:
        raw_records = []
        errors.append(f"Canada registration bulk query: {type(exc).__name__}: {exc}")

    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unmatched = 0
    for record in raw_records:
        normalized = normalize_name((record.get("registration") or {}).get("name", ""))
        target_ids = owners.get(normalized, set())
        if not target_ids:
            unmatched += 1
        for company_id in target_ids:
            candidates[company_id].append(record)

    evidence, review, completeness = [], [], []
    for company in sorted(companies, key=lambda row: row["company_name"].casefold()):
        company_evidence = []
        for record in candidates.get(company["company_id"], []):
            normalized = normalize_name((record.get("registration") or {}).get("name", ""))
            if len(owners.get(normalized, set())) != 1:
                review.append({
                    "company_id": company["company_id"],
                    "company_name": company["company_name"],
                    "review_reason": "ambiguous_canonical_name",
                    "candidate": record,
                })
                continue
            company_evidence.append(to_evidence(
                company, record, run_date, display_names[normalized]
            ))
        company_evidence = list({
            row["evidence_id"]: row for row in company_evidence
        }.values())
        evidence.extend(company_evidence)
        has_review = any(row["company_id"] == company["company_id"] for row in review)
        status = (
            "partial" if errors and company_evidence
            else "failed" if errors
            else "manual_review" if has_review and not company_evidence
            else "complete_matches" if company_evidence
            else "complete_zero"
        )
        completeness.append({
            "company_id": company["company_id"],
            "company_name": company["company_name"],
            "status": status,
            "attempted_at": run_date,
            "source_url": ENDPOINT,
            "raw_count": len(candidates.get(company["company_id"], [])),
            "accepted_count": len(company_evidence),
            "notes": "; ".join(errors) or (
                "openFDA Canadian registration/listing records matched locally "
                "by exact canonical/legal/alias name; listing is not approval."
            ),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "registration_regulatory_evidence.json": {"schema_version": "1.0", "generated_at": run_date, "records": evidence},
        "registration_completeness.json": {"schema_version": "1.0", "generated_at": run_date, "records": completeness},
        "registration_manual_review.json": {"schema_version": "1.0", "generated_at": run_date, "records": review},
        "registration_query_audit.json": {
            "schema_version": "1.0", "generated_at": run_date,
            "unmatched_bulk_candidates": unmatched, "records": audit,
        },
    }
    for filename, payload in outputs.items():
        (output_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    summary = {
        "schema_version": "1.0",
        "generated_at": run_date,
        "companies_searched": len(companies),
        "companies_with_records": len({row["company_id"] for row in evidence}),
        "listing_records": len(evidence),
        "manual_review_candidates": len(review),
        "failed_companies": sum(row["status"] == "failed" for row in completeness),
        "partial_companies": sum(row["status"] == "partial" for row in completeness),
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary
