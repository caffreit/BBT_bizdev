from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

from bbt_bizdev.canada_consolidation import normalize_name
from bbt_bizdev.canada_regulatory import _get_json, api_records, exact_query_names


BASE_URL = "https://health-products.canada.ca/api/clinical-trial"
SPONSOR_URL = BASE_URL + "/sponsor/"
PRODUCT_URL = BASE_URL + "/drugproduct/"
PROTOCOL_URL = BASE_URL + "/protocol/"
STATUS_URL = BASE_URL + "/status/"
def resource_url(base: str, record_id: Any | None = None) -> str:
    params = {"lang": "en", "type": "json"}
    if record_id is not None:
        params["id"] = record_id
    return base + "?" + urlencode(params)


def _evidence_id(company_id: str, protocol_id: Any) -> str:
    digest = hashlib.sha256(
        f"{company_id}|Health Canada|clinical trial|{protocol_id}".encode("utf-8")
    ).hexdigest()[:20]
    return "ca-regulatory-evidence-" + digest


def protocol_to_evidence(
    company: dict[str, Any],
    sponsor: dict[str, Any],
    products: list[dict[str, Any]],
    protocol: dict[str, Any],
    statuses: dict[Any, str],
    captured_at: str,
) -> dict[str, Any]:
    protocol_id = protocol["protocol_id"]
    product_names = sorted({
        str(row.get("brand_name") or "").strip() for row in products
        if str(row.get("brand_name") or "").strip()
    })
    raw_status = statuses.get(protocol.get("status_id"), "UNKNOWN")
    status = {
        "ONGOING": "active",
        "PENDING": "registered",
        "ENDED": "archived",
    }.get(raw_status.upper(), "unknown")
    sponsor_name = str(sponsor.get("manufacturer_name") or "").strip()
    legal = normalize_name(company.get("legal_name", ""))
    canonical = normalize_name(company.get("company_name", ""))
    match_basis = (
        "exact legal name" if legal and normalize_name(sponsor_name) == legal
        else "exact canonical name" if normalize_name(sponsor_name) == canonical
        else "known alias"
    )
    evidence_date = protocol.get("nol_date") or protocol.get("start_date")
    return {
        "evidence_id": _evidence_id(company["company_id"], protocol_id),
        "company_id": company["company_id"],
        "track": "regulatory",
        "claim_type": "Health Canada drug/biologic clinical trial",
        "jurisdiction": "Canada",
        "authority": "Health Canada",
        "record_type": "trial",
        "record_id": str(protocol_id),
        "legal_manufacturer": sponsor_name,
        "product_name": "; ".join(product_names),
        "device_class": "",
        "status": status,
        "decision_or_start_date": evidence_date,
        "evidence_url": resource_url(PROTOCOL_URL, protocol_id),
        "evidence_date": evidence_date,
        "captured_at": captured_at,
        "extraction_method": "health_canada_clinical_trial_api_exact_sponsor_match",
        "source_type": "regulator",
        "match_basis": match_basis,
        "confidence": "high",
        "protocol_number": protocol.get("protocol_no"),
        "submission_number": protocol.get("submission_no"),
        "trial_status": raw_status,
        "start_date": protocol.get("start_date"),
        "end_date": protocol.get("end_date"),
        "no_objection_letter_date": protocol.get("nol_date"),
        "protocol_title": protocol.get("protocol_title"),
        "medical_conditions": [
            row.get("med_condition") for row in protocol.get("medConditionList", [])
            if isinstance(row, dict) and row.get("med_condition")
        ],
        "study_populations": [
            row.get("study_population") for row in protocol.get("studyPopulationList", [])
            if isinstance(row, dict) and row.get("study_population")
        ],
        "raw_record": {"sponsor": sponsor, "products": products, "protocol": protocol},
    }


def run_clinical_trial_enrichment(
    companies_path: Path,
    output_dir: Path,
    run_date: str | None = None,
    company_ids: set[str] | None = None,
    getter: Callable[[str], Any] = _get_json,
) -> dict[str, Any]:
    run_date = run_date or date.today().isoformat()
    companies = json.loads(companies_path.read_text(encoding="utf-8"))["companies"]
    # Matching the local company universe against the downloaded sponsor table is
    # inexpensive, and avoids missing drug/biologic companies whose coarse
    # product category was misclassified during source consolidation.
    if company_ids:
        companies = [row for row in companies if row["company_id"] in company_ids]

    dataset_errors = []
    try:
        sponsors = api_records(getter(resource_url(SPONSOR_URL)))
    except Exception as exc:
        sponsors = []
        dataset_errors.append(f"sponsor dataset: {type(exc).__name__}: {exc}")
    try:
        products = api_records(getter(resource_url(PRODUCT_URL)))
    except Exception as exc:
        products = []
        dataset_errors.append(f"drug product dataset: {type(exc).__name__}: {exc}")
    try:
        status_rows = api_records(getter(resource_url(STATUS_URL)))
    except Exception as exc:
        status_rows = []
        dataset_errors.append(f"status dataset: {type(exc).__name__}: {exc}")

    statuses = {row.get("status_id"): str(row.get("status") or "") for row in status_rows}
    products_by_sponsor: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for product in products:
        products_by_sponsor[product.get("manufacturer_id")].append(product)
    sponsors_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sponsor in sponsors:
        sponsors_by_name[normalize_name(sponsor.get("manufacturer_name", ""))].append(sponsor)

    owners: dict[str, set[str]] = defaultdict(set)
    for company in companies:
        for name in exact_query_names(company):
            owners[normalize_name(name)].add(company["company_id"])

    evidence, review, completeness, audit = [], [], [], []
    for company in sorted(companies, key=lambda row: row["company_name"].casefold()):
        matches = {}
        names = exact_query_names(company)
        for name in names:
            normalized = normalize_name(name)
            rows = sponsors_by_name.get(normalized, [])
            audit.append({
                "company_id": company["company_id"],
                "company_name": company["company_name"],
                "query_name": name,
                "result_count": len(rows),
                "source_url": resource_url(SPONSOR_URL),
            })
            for sponsor in rows:
                matches[str(sponsor.get("manufacturer_id"))] = (sponsor, name)

        company_evidence = []
        protocol_errors = []
        for sponsor, matched_name in matches.values():
            normalized = normalize_name(sponsor.get("manufacturer_name", ""))
            if len(owners.get(normalized, set())) != 1:
                review.append({
                    "company_id": company["company_id"],
                    "company_name": company["company_name"],
                    "review_reason": "ambiguous_canonical_sponsor_name",
                    "candidate": sponsor,
                })
                continue
            sponsor_products = products_by_sponsor.get(sponsor.get("manufacturer_id"), [])
            by_protocol: dict[Any, list[dict[str, Any]]] = defaultdict(list)
            for product in sponsor_products:
                by_protocol[product.get("protocol_id")].append(product)
            for protocol_id, protocol_products in by_protocol.items():
                try:
                    protocol_rows = api_records(
                        getter(resource_url(PROTOCOL_URL, protocol_id))
                    )
                except Exception as exc:
                    protocol_errors.append(
                        f"protocol {protocol_id}: {type(exc).__name__}: {exc}"
                    )
                    continue
                for protocol in protocol_rows:
                    company_evidence.append(protocol_to_evidence(
                        company, sponsor, protocol_products, protocol, statuses, run_date
                    ))
        company_evidence = list({
            row["evidence_id"]: row for row in company_evidence
        }.values())
        evidence.extend(company_evidence)
        errors = [*dataset_errors, *protocol_errors]
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
            "source_url": resource_url(SPONSOR_URL),
            "raw_count": len(matches),
            "accepted_count": len(company_evidence),
            "notes": "; ".join(errors) or (
                "Health Canada sponsor dataset matched by exact legal/canonical/alias name; "
                "drug-product and protocol records joined by regulator IDs."
            ),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "clinical_trial_regulatory_evidence.json": {"schema_version": "1.0", "generated_at": run_date, "records": evidence},
        "clinical_trial_completeness.json": {"schema_version": "1.0", "generated_at": run_date, "records": completeness},
        "clinical_trial_manual_review.json": {"schema_version": "1.0", "generated_at": run_date, "records": review},
        "clinical_trial_query_audit.json": {"schema_version": "1.0", "generated_at": run_date, "records": audit},
    }
    for filename, payload in outputs.items():
        (output_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    summary = {
        "schema_version": "1.0",
        "generated_at": run_date,
        "companies_searched": len(companies),
        "companies_with_trials": len({row["company_id"] for row in evidence}),
        "trial_records": len(evidence),
        "manual_review_candidates": len(review),
        "failed_companies": sum(row["status"] == "failed" for row in completeness),
        "partial_companies": sum(row["status"] == "partial" for row in completeness),
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary
