from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bbt_bizdev.canada_consolidation import normalize_name
from bbt_bizdev.canada_regulatory import RELEVANT_CATEGORIES, USER_AGENT, exact_query_names


FDA_510K_URL = "https://api.fda.gov/device/510k.json"
FDA_PMA_URL = "https://api.fda.gov/device/pma.json"


def _get_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        if exc.code == 404:
            return {"results": []}
        raise
    # Keep unauthenticated openFDA traffic under its documented rate limit.
    time.sleep(0.5)
    return payload if isinstance(payload, dict) else {"results": []}


def applicant_query_url(endpoint: str, name: str) -> str:
    discovery_name = safe_discovery_name(name)
    return endpoint + "?" + urlencode({
        "search": f'applicant:"{discovery_name}"',
        "limit": 1000,
    })


def safe_discovery_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^A-Za-z0-9 .,'&-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def result_records(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    return [row for row in payload.get("results", []) if isinstance(row, dict)]


def fetch_all(
    endpoint: str,
    search: str,
    getter: Callable[[str], dict[str, Any]] = _get_json,
    limit: int = 1000,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records, audit = [], []
    skip = 0
    while True:
        url = endpoint + "?" + urlencode({
            "search": search,
            "limit": limit,
            "skip": skip,
        })
        payload = getter(url)
        rows = result_records(payload)
        records.extend(rows)
        total = int(((payload.get("meta") or {}).get("results") or {}).get("total") or len(rows))
        audit.append({"url": url, "result_count": len(rows), "total": total})
        skip += len(rows)
        if not rows or skip >= total or len(rows) < limit:
            break
        if skip > 25000:
            raise ValueError("openFDA result set exceeds supported skip window")
    return records, audit


def batched(values: list[str], size: int = 15) -> list[list[str]]:
    return [values[index:index + size] for index in range(0, len(values), size)]


def lucene_phrase(value: str) -> str:
    return re.sub(r'([+\-!(){}\[\]^"~*?:\\/&|])', r'\\\1', value)


def missing_original_pma_batch_company_ids(
    companies: list[dict[str, Any]], audit_rows: list[dict[str, Any]]
) -> list[str]:
    owners: dict[str, set[str]] = defaultdict(set)
    display_names: dict[str, str] = {}
    for company in companies:
        for name in exact_query_names(company):
            normalized = normalize_name(name)
            owners[normalized].add(company["company_id"])
            display_names.setdefault(normalized, name)
    observed = {row.get("url") for row in audit_rows}
    missing = []
    for batch in batched(sorted(owners)):
        search = "(" + " OR ".join(
            f'applicant:"{display_names[value]}"' for value in batch
        ) + ")"
        url = FDA_PMA_URL + "?" + urlencode({
            "search": search, "limit": 1000, "skip": 0,
        })
        if url not in observed:
            missing.extend(
                company_id for value in batch for company_id in owners[value]
            )
    return list(dict.fromkeys(missing))


def _evidence_id(company_id: str, record_type: str, record_id: str) -> str:
    digest = hashlib.sha256(
        f"{company_id}|FDA|{record_type}|{record_id}".encode("utf-8")
    ).hexdigest()[:20]
    return "ca-regulatory-evidence-" + digest


def iso_date(value: Any) -> str | None:
    value = str(value or "")
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return value or None


def fda_record_to_evidence(
    company: dict[str, Any],
    record: dict[str, Any],
    record_type: str,
    captured_at: str,
    matched_name: str,
) -> dict[str, Any]:
    is_510k = record_type == "510(k)"
    base_id = str(record.get("k_number") if is_510k else record.get("pma_number") or "")
    supplement = str(record.get("supplement_number") or "").strip()
    record_id = base_id if is_510k or not supplement else f"{base_id}/{supplement}"
    applicant = str(record.get("applicant") or "").strip()
    product_name = str(
        record.get("device_name") if is_510k
        else record.get("trade_name") or record.get("generic_name") or ""
    ).strip()
    evidence_url = (
        FDA_510K_URL + "?" + urlencode({"search": f'k_number:"{base_id}"'})
        if is_510k
        else FDA_PMA_URL + "?" + urlencode({"search": f'pma_number:"{base_id}"'})
    )
    legal = normalize_name(company.get("legal_name", ""))
    canonical = normalize_name(company.get("company_name", ""))
    match_basis = (
        "exact legal name" if legal and normalize_name(applicant) == legal
        else "exact canonical name" if normalize_name(applicant) == canonical
        else "known alias"
    )
    evidence_date = iso_date(record.get("decision_date"))
    return {
        "evidence_id": _evidence_id(company["company_id"], record_type, record_id),
        "company_id": company["company_id"],
        "track": "regulatory",
        "claim_type": f"FDA device {record_type} record",
        "jurisdiction": "US",
        "authority": "FDA",
        "record_type": record_type,
        "record_id": record_id,
        "legal_manufacturer": applicant,
        "product_name": product_name,
        "device_class": "",
        "status": "cleared" if is_510k else "approved",
        "decision_or_start_date": evidence_date,
        "evidence_url": evidence_url,
        "evidence_date": evidence_date,
        "captured_at": captured_at,
        "extraction_method": f"openfda_{'510k' if is_510k else 'pma'}_exact_applicant_match",
        "source_type": "regulator",
        "match_basis": match_basis,
        "matched_query_name": matched_name,
        "confidence": "high",
        "decision_code": record.get("decision_code"),
        "decision_description": record.get("decision_description"),
        "product_code": record.get("product_code"),
        "supplement_number": supplement,
        "city": record.get("city"),
        "state": record.get("state"),
        "country_code": record.get("country_code"),
        "raw_record": record,
    }


def collect_company(
    company: dict[str, Any],
    getter: Callable[[str], dict[str, Any]] = _get_json,
) -> dict[str, Any]:
    candidates: dict[tuple[str, str], tuple[dict[str, Any], str]] = {}
    queries = []
    errors = []
    for name in exact_query_names(company):
        for record_type, endpoint in (("510(k)", FDA_510K_URL), ("PMA", FDA_PMA_URL)):
            url = applicant_query_url(endpoint, name)
            try:
                rows = result_records(getter(url))
            except Exception as exc:
                rows = []
                errors.append(f"{record_type}/{name}: {type(exc).__name__}: {exc}")
            queries.append({
                "query_name": name,
                "record_type": record_type,
                "url": url,
                "result_count": len(rows),
            })
            id_field = "k_number" if record_type == "510(k)" else "pma_number"
            for row in rows:
                key = (record_type, str(row.get(id_field) or json.dumps(row, sort_keys=True)))
                candidates[key] = (row, name)
    return {
        "company": company,
        "candidates": candidates,
        "queries": queries,
        "errors": errors,
    }


def run_fda_enrichment(
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
        futures = [executor.submit(collect_company, company, getter) for company in companies]
        for future in as_completed(futures):
            results.append(future.result())

    evidence, review, completeness, audit = [], [], [], []
    for result in sorted(results, key=lambda row: row["company"]["company_name"].casefold()):
        company = result["company"]
        accepted_names = {
            normalize_name(name): name for name in exact_query_names(company)
        }
        company_evidence = []
        for (record_type, _), (record, matched_name) in result["candidates"].items():
            applicant = str(record.get("applicant") or "")
            normalized = normalize_name(applicant)
            reason = ""
            if normalized not in accepted_names:
                reason = "non_exact_fda_applicant_name"
            elif len(owners.get(normalized, set())) != 1:
                reason = "ambiguous_canonical_name"
            if reason:
                review.append({
                    "company_id": company["company_id"],
                    "company_name": company["company_name"],
                    "record_type": record_type,
                    "review_reason": reason,
                    "candidate": record,
                })
            else:
                company_evidence.append(fda_record_to_evidence(
                    company, record, record_type, run_date, accepted_names[normalized]
                ))
        company_evidence = list({
            row["evidence_id"]: row for row in company_evidence
        }.values())
        evidence.extend(company_evidence)
        audit.extend({
            "company_id": company["company_id"],
            "company_name": company["company_name"],
            **query,
        } for query in result["queries"])
        has_review = any(row["company_id"] == company["company_id"] for row in review)
        status = (
            "partial" if result["errors"] and (result["candidates"] or company_evidence)
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
            "source_url": "https://open.fda.gov/apis/device/",
            "raw_count": len(result["candidates"]),
            "accepted_count": len(company_evidence),
            "notes": "; ".join(result["errors"]) or (
                "openFDA 510(k) and PMA applicant searches completed for exact "
                "canonical/legal/alias names."
            ),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "fda_regulatory_evidence.json": {"schema_version": "1.0", "generated_at": run_date, "records": evidence},
        "fda_completeness.json": {"schema_version": "1.0", "generated_at": run_date, "records": completeness},
        "fda_manual_review.json": {"schema_version": "1.0", "generated_at": run_date, "records": review},
        "fda_query_audit.json": {"schema_version": "1.0", "generated_at": run_date, "records": audit},
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
        "regulatory_records": len(evidence),
        "records_by_type": {
            record_type: sum(row["record_type"] == record_type for row in evidence)
            for record_type in ("510(k)", "PMA")
        },
        "manual_review_candidates": len(review),
        "failed_companies": sum(row["status"] == "failed" for row in completeness),
        "partial_companies": sum(row["status"] == "partial" for row in completeness),
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def run_fda_enrichment_bulk(
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
    company_by_id = {row["company_id"]: row for row in companies}
    owners: dict[str, set[str]] = defaultdict(set)
    display_names: dict[str, str] = {}
    for company in companies:
        for name in exact_query_names(company):
            normalized = normalize_name(name)
            owners[normalized].add(company["company_id"])
            display_names.setdefault(normalized, name)

    audit, global_errors, raw_records = [], [], []
    try:
        rows, pages = fetch_all(FDA_510K_URL, 'country_code:"CA"', getter)
        raw_records.extend(("510(k)", row) for row in rows)
        audit.extend({"record_type": "510(k)", **page} for page in pages)
    except Exception as exc:
        global_errors.append(f"510(k) Canada bulk query: {type(exc).__name__}: {exc}")

    normalized_names = sorted(owners)
    pma_errors_by_company: dict[str, list[str]] = defaultdict(list)
    for batch in batched(normalized_names):
        terms = [
            f'applicant:"{lucene_phrase(display_names[value])}"' for value in batch
        ]
        search = "(" + " OR ".join(terms) + ")"
        try:
            rows, pages = fetch_all(FDA_PMA_URL, search, getter)
            raw_records.extend(("PMA", row) for row in rows)
            audit.extend({"record_type": "PMA", **page} for page in pages)
        except Exception as exc:
            message = f"PMA applicant batch: {type(exc).__name__}: {exc}"
            for normalized in batch:
                for company_id in owners[normalized]:
                    pma_errors_by_company[company_id].append(message)

    candidates: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    unmatched = 0
    for record_type, record in raw_records:
        normalized = normalize_name(record.get("applicant", ""))
        target_ids = owners.get(normalized, set())
        if not target_ids:
            unmatched += 1
        for company_id in target_ids:
            candidates[company_id].append((record_type, record))

    evidence, review, completeness = [], [], []
    for company in sorted(companies, key=lambda row: row["company_name"].casefold()):
        company_evidence = []
        for record_type, record in candidates.get(company["company_id"], []):
            normalized = normalize_name(record.get("applicant", ""))
            if len(owners.get(normalized, set())) != 1:
                review.append({
                    "company_id": company["company_id"],
                    "company_name": company["company_name"],
                    "record_type": record_type,
                    "review_reason": "ambiguous_canonical_name",
                    "candidate": record,
                })
                continue
            company_evidence.append(fda_record_to_evidence(
                company, record, record_type, run_date, display_names[normalized]
            ))
        company_evidence = list({
            row["evidence_id"]: row for row in company_evidence
        }.values())
        evidence.extend(company_evidence)
        errors = [
            *global_errors,
            *pma_errors_by_company.get(company["company_id"], []),
        ]
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
            "source_url": "https://open.fda.gov/apis/device/",
            "raw_count": len(candidates.get(company["company_id"], [])),
            "accepted_count": len(company_evidence),
            "notes": "; ".join(errors) or (
                "openFDA Canadian 510(k) records and batched PMA applicant searches "
                "matched locally by exact canonical/legal/alias name."
            ),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "fda_regulatory_evidence.json": {"schema_version": "1.0", "generated_at": run_date, "records": evidence},
        "fda_completeness.json": {"schema_version": "1.0", "generated_at": run_date, "records": completeness},
        "fda_manual_review.json": {"schema_version": "1.0", "generated_at": run_date, "records": review},
        "fda_query_audit.json": {
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
        "regulatory_records": len(evidence),
        "records_by_type": {
            record_type: sum(row["record_type"] == record_type for row in evidence)
            for record_type in ("510(k)", "PMA")
        },
        "manual_review_candidates": len(review),
        "failed_companies": sum(row["status"] == "failed" for row in completeness),
        "partial_companies": sum(row["status"] == "partial" for row in completeness),
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary
