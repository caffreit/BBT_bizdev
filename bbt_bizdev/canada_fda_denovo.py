from __future__ import annotations

import hashlib
import html
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from bbt_bizdev.canada_consolidation import normalize_name
from bbt_bizdev.canada_regulatory import RELEVANT_CATEGORIES, USER_AGENT, exact_query_names


SEARCH_URL = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/denovo.cfm"


def query_url(name: str) -> str:
    return SEARCH_URL + "?" + urlencode({
        "Applicant": name,
        "Denovo": "on",
        "start_search": 1,
    })


def _get(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", fragment))).strip()


def parse_results(page: str) -> list[dict[str, str]]:
    records = []
    for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", page):
        cells = re.findall(r"(?is)<td[^>]*>(.*?)</td>", row)
        number_match = re.search(r"\bDEN\d+\b", _text(row), re.I)
        if len(cells) < 5 or not number_match:
            continue
        link = re.search(r'href="([^"]*denovo\.cfm\?id=DEN\d+)"', row, re.I)
        records.append({
            "device_name": _text(cells[0]),
            "requester": _text(cells[1]),
            "de_novo_number": number_match.group(0).upper(),
            "k_number": _text(cells[3]),
            "decision_date_published": _text(cells[4]),
            "evidence_url": urljoin(SEARCH_URL, html.unescape(link.group(1))) if link else "",
        })
    return records


def iso_date(value: str) -> str | None:
    try:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def _evidence_id(company_id: str, record_id: str) -> str:
    digest = hashlib.sha256(
        f"{company_id}|FDA|De Novo|{record_id}".encode("utf-8")
    ).hexdigest()[:20]
    return "ca-regulatory-evidence-" + digest


def to_evidence(
    company: dict[str, Any],
    record: dict[str, str],
    captured_at: str,
    matched_name: str,
) -> dict[str, Any]:
    requester = record["requester"]
    legal = normalize_name(company.get("legal_name", ""))
    canonical = normalize_name(company.get("company_name", ""))
    match_basis = (
        "exact legal name" if legal and normalize_name(requester) == legal
        else "exact canonical name" if normalize_name(requester) == canonical
        else "known alias"
    )
    decision_date = iso_date(record["decision_date_published"])
    return {
        "evidence_id": _evidence_id(company["company_id"], record["de_novo_number"]),
        "company_id": company["company_id"],
        "track": "regulatory",
        "claim_type": "FDA De Novo classification order",
        "jurisdiction": "US",
        "authority": "FDA",
        "record_type": "De Novo",
        "record_id": record["de_novo_number"],
        "legal_manufacturer": requester,
        "product_name": record["device_name"],
        "device_class": "",
        "status": "cleared",
        "decision_or_start_date": decision_date,
        "evidence_url": record["evidence_url"] or query_url(matched_name),
        "evidence_date": decision_date,
        "captured_at": captured_at,
        "extraction_method": "fda_denovo_database_exact_requester_match",
        "source_type": "regulator",
        "match_basis": match_basis,
        "matched_query_name": matched_name,
        "confidence": "high",
        "related_510k_number": record["k_number"],
        "raw_record": record,
    }


def collect_company(
    company: dict[str, Any], getter: Callable[[str], str] = _get
) -> dict[str, Any]:
    records, queries, errors = [], [], []
    for name in exact_query_names(company):
        url = query_url(name)
        try:
            rows = parse_results(getter(url))
        except Exception as exc:
            rows = []
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
        queries.append({"query_name": name, "url": url, "result_count": len(rows)})
        records.extend((row, name) for row in rows)
    return {"company": company, "records": records, "queries": queries, "errors": errors}


def run_denovo_enrichment(
    companies_path: Path,
    output_dir: Path,
    run_date: str | None = None,
    workers: int = 4,
    company_ids: set[str] | None = None,
    getter: Callable[[str], str] = _get,
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
            normalized = normalize_name(record["requester"])
            reason = ""
            if normalized not in accepted_names:
                reason = "non_exact_fda_requester_name"
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
            "source_url": SEARCH_URL,
            "raw_count": len(result["records"]),
            "accepted_count": len(company_evidence),
            "notes": "; ".join(result["errors"]) or (
                "FDA De Novo database searched by exact canonical/legal/alias names."
            ),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "denovo_regulatory_evidence.json": {"schema_version": "1.0", "generated_at": run_date, "records": evidence},
        "denovo_completeness.json": {"schema_version": "1.0", "generated_at": run_date, "records": completeness},
        "denovo_manual_review.json": {"schema_version": "1.0", "generated_at": run_date, "records": review},
        "denovo_query_audit.json": {"schema_version": "1.0", "generated_at": run_date, "records": audit},
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
        "manual_review_candidates": len(review),
        "failed_companies": sum(row["status"] == "failed" for row in completeness),
        "partial_companies": sum(row["status"] == "partial" for row in completeness),
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary
