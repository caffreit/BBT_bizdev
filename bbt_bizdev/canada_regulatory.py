from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bbt_bizdev.canada_consolidation import normalize_name


BASE_URL = "https://health-products.canada.ca/api/medical-devices"
COMPANY_URL = BASE_URL + "/company/"
LICENCE_URL = BASE_URL + "/licence/"
USER_AGENT = "BlueBridge-regulatory-research/1.0"
RELEVANT_CATEGORIES = {"medical device", "diagnostics", "SaMD"}
STATUS_CODES = {
    "C": "archived",
    "D": "active",
    "I": "active",
    "M": "archived",
    "O": "archived",
    "P": "active",
    "Q": "suspended",
    "R": "archived",
    "S": "suspended",
    "W": "archived",
    "X": "archived",
}


def api_records(payload: Any) -> list[dict[str, Any]]:
    """Normalize MDALL's single-object, array, and wrapped response shapes."""
    if isinstance(payload, dict) and isinstance(payload.get("result"), list):
        payload = payload["result"]
    elif isinstance(payload, dict) and isinstance(payload.get("result"), dict):
        payload = payload["result"]
    if isinstance(payload, dict):
        return [payload] if payload else []
    return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []


def _get_json(url: str, timeout: int = 30, retries: int = 2) -> Any:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception:
            if attempt == retries:
                raise
            time.sleep(0.5 * (attempt + 1))
    return []


def company_query_url(name: str) -> str:
    return COMPANY_URL + "?" + urlencode({"company_name": name, "type": "json"})


def licence_query_url(company_id: int | str, state: str) -> str:
    return LICENCE_URL + "?" + urlencode({
        "company_id": company_id,
        "state": state,
        "lang": "en",
        "type": "json",
    })


def exact_query_names(company: dict[str, Any]) -> list[str]:
    values = [
        company.get("legal_name", ""),
        company.get("company_name", ""),
        *company.get("aliases", []),
    ]
    output = []
    seen = set()
    for value in values:
        value = str(value or "").strip()
        normalized = normalize_name(value)
        if value and normalized and normalized not in seen:
            output.append(value)
            seen.add(normalized)
    return output[:6]


def _evidence_id(company_id: str, licence_number: Any) -> str:
    digest = hashlib.sha256(
        f"{company_id}|Health Canada|MDALL|{licence_number}".encode("utf-8")
    ).hexdigest()[:20]
    return "ca-regulatory-evidence-" + digest


def licence_to_evidence(
    company: dict[str, Any],
    manufacturer: dict[str, Any],
    licence: dict[str, Any],
    requested_state: str,
    captured_at: str,
    matched_name: str,
) -> dict[str, Any]:
    licence_number = licence.get("original_licence_no")
    status = STATUS_CODES.get(str(licence.get("licence_status") or "").upper())
    if not status:
        status = "archived" if requested_state == "archived" or licence.get("end_date") else "active"
    manufacturer_name = str(manufacturer.get("company_name") or "").strip()
    canonical_name = normalize_name(company.get("company_name", ""))
    legal_name = normalize_name(company.get("legal_name", ""))
    match_basis = (
        "exact legal name"
        if legal_name and normalize_name(manufacturer_name) == legal_name
        else "exact canonical name"
        if normalize_name(manufacturer_name) == canonical_name
        else "known alias"
    )
    evidence_url = LICENCE_URL + "?" + urlencode({
        "id": licence_number,
        "lang": "en",
        "type": "json",
    })
    return {
        "evidence_id": _evidence_id(company["company_id"], licence_number),
        "company_id": company["company_id"],
        "track": "regulatory",
        "claim_type": "Health Canada medical device licence",
        "jurisdiction": "Canada",
        "authority": "Health Canada",
        "record_type": "MDL/MDALL",
        "record_id": str(licence_number),
        "legal_manufacturer": manufacturer_name,
        "product_name": str(licence.get("licence_name") or "").strip(),
        "device_class": (
            f"Class {licence['appl_risk_class']}"
            if licence.get("appl_risk_class") not in (None, "")
            else ""
        ),
        "status": status,
        "decision_or_start_date": licence.get("first_licence_status_dt"),
        "evidence_url": evidence_url,
        "evidence_date": licence.get("first_licence_status_dt"),
        "captured_at": captured_at,
        "extraction_method": "health_canada_mdall_api_exact_manufacturer_match",
        "source_type": "regulator",
        "match_basis": match_basis,
        "matched_query_name": matched_name,
        "confidence": "high",
        "regulator_company_id": manufacturer.get("company_id"),
        "regulator_company_status": manufacturer.get("company_status"),
        "licence_type": licence.get("licence_type_desc"),
        "last_refresh_date": licence.get("last_refresh_dt"),
        "end_date": licence.get("end_date"),
        "raw_record": {"manufacturer": manufacturer, "licence": licence},
    }


def collect_company(
    company: dict[str, Any], getter: Callable[[str], Any] = _get_json
) -> dict[str, Any]:
    candidates: dict[str, dict[str, Any]] = {}
    queries = []
    errors = []
    for name in exact_query_names(company):
        url = company_query_url(name)
        try:
            rows = api_records(getter(url))
        except Exception as exc:
            rows = []
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
        queries.append({"query_name": name, "url": url, "result_count": len(rows)})
        for row in rows:
            key = str(row.get("company_id") or json.dumps(row, sort_keys=True))
            candidates[key] = row
    return {
        "company": company,
        "queries": queries,
        "candidates": list(candidates.values()),
        "errors": errors,
    }


def run_mdall_enrichment(
    companies_path: Path,
    output_dir: Path,
    run_date: str | None = None,
    workers: int = 4,
    relevant_only: bool = True,
    company_ids: set[str] | None = None,
    getter: Callable[[str], Any] = _get_json,
) -> dict[str, Any]:
    run_date = run_date or date.today().isoformat()
    payload = json.loads(companies_path.read_text(encoding="utf-8"))
    companies = payload["companies"]
    if relevant_only:
        companies = [
            row for row in companies
            if str(row.get("product_category") or "").casefold() in {
                value.casefold() for value in RELEVANT_CATEGORIES
            }
        ]
    if company_ids:
        companies = [row for row in companies if row["company_id"] in company_ids]

    name_owners: dict[str, set[str]] = defaultdict(set)
    for company in companies:
        for name in exact_query_names(company):
            name_owners[normalize_name(name)].add(company["company_id"])

    searches = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(collect_company, company, getter) for company in companies]
        for future in as_completed(futures):
            searches.append(future.result())

    evidence = []
    review = []
    completeness = []
    query_audit = []
    for result in sorted(searches, key=lambda row: row["company"]["company_name"].casefold()):
        company = result["company"]
        accepted_names = {
            normalize_name(name): name for name in exact_query_names(company)
        }
        query_audit.extend({
            "company_id": company["company_id"],
            "company_name": company["company_name"],
            **query,
        } for query in result["queries"])
        accepted_manufacturers = []
        for candidate in result["candidates"]:
            candidate_name = str(candidate.get("company_name") or "")
            normalized = normalize_name(candidate_name)
            reason = ""
            if normalized not in accepted_names:
                reason = "substring_or_non_exact_manufacturer_name"
            elif len(name_owners.get(normalized, set())) != 1:
                reason = "ambiguous_canonical_name"
            if reason:
                review.append({
                    "company_id": company["company_id"],
                    "company_name": company["company_name"],
                    "review_reason": reason,
                    "candidate": candidate,
                })
            else:
                accepted_manufacturers.append((candidate, accepted_names[normalized]))

        licence_errors = []
        raw_licence_count = 0
        company_evidence = []
        for manufacturer, matched_name in accepted_manufacturers:
            for state in ("active", "archived"):
                url = licence_query_url(manufacturer["company_id"], state)
                try:
                    licences = api_records(getter(url))
                except Exception as exc:
                    licences = []
                    licence_errors.append(f"{state}: {type(exc).__name__}: {exc}")
                raw_licence_count += len(licences)
                for licence in licences:
                    company_evidence.append(licence_to_evidence(
                        company, manufacturer, licence, state, run_date, matched_name
                    ))
        # MDALL may repeat a record when company_id and state filters are combined.
        # Licence number is the stable regulator identifier, so count it once.
        company_evidence = list({
            row["evidence_id"]: row for row in company_evidence
        }.values())
        evidence.extend(company_evidence)
        errors = [*result["errors"], *licence_errors]
        has_review = any(row["company_id"] == company["company_id"] for row in review)
        status = (
            "partial" if errors and (result["candidates"] or company_evidence)
            else "failed" if errors
            else "manual_review" if has_review and not accepted_manufacturers
            else "complete_matches" if company_evidence
            else "complete_zero"
        )
        completeness.append({
            "company_id": company["company_id"],
            "company_name": company["company_name"],
            "status": status,
            "attempted_at": run_date,
            "source_url": COMPANY_URL,
            "raw_count": len(result["candidates"]) + raw_licence_count,
            "accepted_count": len(company_evidence),
            "notes": "; ".join(errors) or (
                "Exact manufacturer-name queries completed against MDALL; "
                "active and archived licences checked for accepted matches."
            ),
        })

    evidence = list({row["evidence_id"]: row for row in evidence}.values())
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "mdall_regulatory_evidence.json": {
            "schema_version": "1.0", "generated_at": run_date, "records": evidence,
        },
        "mdall_completeness.json": {
            "schema_version": "1.0", "generated_at": run_date, "records": completeness,
        },
        "mdall_manual_review.json": {
            "schema_version": "1.0", "generated_at": run_date, "records": review,
        },
        "mdall_query_audit.json": {
            "schema_version": "1.0", "generated_at": run_date, "records": query_audit,
        },
    }
    for filename, data in outputs.items():
        (output_dir / filename).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    summary = {
        "schema_version": "1.0",
        "generated_at": run_date,
        "companies_searched": len(companies),
        "companies_with_licences": len({row["company_id"] for row in evidence}),
        "licence_records": len(evidence),
        "manual_review_candidates": len(review),
        "failed_companies": sum(row["status"] == "failed" for row in completeness),
        "partial_companies": sum(row["status"] == "partial" for row in completeness),
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary
