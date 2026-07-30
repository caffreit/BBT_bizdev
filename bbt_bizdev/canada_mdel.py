from __future__ import annotations

import hashlib
import html
import http.cookiejar
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener

from bbt_bizdev.canada_consolidation import normalize_name
from bbt_bizdev.canada_regulatory import RELEVANT_CATEGORIES, USER_AGENT, exact_query_names


BASE_URL = "https://health-products.canada.ca"
SEARCH_URL = BASE_URL + "/mdel-leim/"


def clean_html(page: str) -> str:
    page = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", page)
    page = re.sub(r"(?s)<[^>]+>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(page)).strip()


def parse_mdel_detail(page: str) -> dict[str, Any] | None:
    text = clean_html(page)
    patterns = {
        "licence_number": r"Licence number \(maximum of 6 numbers\):\s*(\d+)",
        "company_id": r"Company Id \(maximum of 6 numbers\):\s*(\d+)",
        "company_name": r"Company name\s*:\s*(.*?)\s+Address:",
        "address": r"Address:\s*(.*?)\s+Senior official name",
        "senior_official": r"Senior official name\s*:\s*(.*?)\s+Activities for device classes:",
    }
    values = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        values[key] = match.group(1).strip() if match else ""
    if not values["licence_number"] or not values["company_name"]:
        return None
    activity = re.search(
        r"Activities for device classes:\s*(.*?)\s+(?:New search|Related links)",
        text,
        re.I,
    )
    values["authorized_activities"] = activity.group(1).strip() if activity else ""
    return values


class MdelSession:
    def __init__(self) -> None:
        jar = http.cookiejar.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(jar))
        self.action_url = ""

    def _request(self, url: str, data: bytes | None = None) -> str:
        request = Request(
            url,
            data=data,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with self.opener.open(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")

    def search(self, company_name: str) -> str:
        if not self.action_url:
            page = self._request(SEARCH_URL)
            match = re.search(
                r'<form\s+name="searchMdelForm"[^>]*action="([^"]+)"',
                page,
                re.I,
            )
            if not match:
                raise ValueError("MDEL search form action was not found")
            self.action_url = urljoin(BASE_URL, html.unescape(match.group(1)))
        payload = urlencode({
            "licence": "",
            "companyId": "",
            "company": company_name,
            "activityId": "",
            "countryId": "",
            "regionId": "",
            "action": "Search",
        }).encode("utf-8")
        return self._request(self.action_url, payload)


def _evidence_id(company_id: str, licence_number: str) -> str:
    digest = hashlib.sha256(
        f"{company_id}|Health Canada|MDEL|{licence_number}".encode("utf-8")
    ).hexdigest()[:20]
    return "ca-regulatory-evidence-" + digest


def mdel_to_evidence(
    company: dict[str, Any],
    record: dict[str, Any],
    captured_at: str,
    matched_name: str,
) -> dict[str, Any]:
    manufacturer = record["company_name"]
    legal = normalize_name(company.get("legal_name", ""))
    canonical = normalize_name(company.get("company_name", ""))
    match_basis = (
        "exact legal name" if legal and normalize_name(manufacturer) == legal
        else "exact canonical name" if normalize_name(manufacturer) == canonical
        else "known alias"
    )
    return {
        "evidence_id": _evidence_id(company["company_id"], record["licence_number"]),
        "company_id": company["company_id"],
        "track": "regulatory",
        "claim_type": "Health Canada medical device establishment licence",
        "jurisdiction": "Canada",
        "authority": "Health Canada",
        "record_type": "MDEL",
        "record_id": record["licence_number"],
        "legal_manufacturer": manufacturer,
        "product_name": "",
        "device_class": "",
        "status": "active",
        "decision_or_start_date": None,
        "evidence_url": SEARCH_URL,
        "evidence_date": None,
        "captured_at": captured_at,
        "extraction_method": "health_canada_mdel_session_search_exact_company_match",
        "source_type": "regulator",
        "match_basis": match_basis,
        "matched_query_name": matched_name,
        "confidence": "high",
        "regulator_company_id": record["company_id"],
        "address": record["address"],
        "authorized_activities": record["authorized_activities"],
        "interpretation_note": "Establishment licensing evidence; not approval of a specific device.",
        "raw_record": record,
    }


def collect_company(
    company: dict[str, Any],
    session_factory: Callable[[], Any] = MdelSession,
) -> dict[str, Any]:
    session = session_factory()
    records = []
    queries = []
    errors = []
    for name in exact_query_names(company):
        try:
            page = session.search(name)
            record = parse_mdel_detail(page)
        except Exception as exc:
            record = None
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
        queries.append({"query_name": name, "result_count": int(record is not None)})
        if record:
            records.append((record, name))
    return {"company": company, "records": records, "queries": queries, "errors": errors}


def run_mdel_enrichment(
    companies_path: Path,
    output_dir: Path,
    run_date: str | None = None,
    workers: int = 4,
    company_ids: set[str] | None = None,
    session_factory: Callable[[], Any] = MdelSession,
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
    owners: dict[str, set[str]] = {}
    for company in companies:
        for name in exact_query_names(company):
            owners.setdefault(normalize_name(name), set()).add(company["company_id"])

    results = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [
            executor.submit(collect_company, company, session_factory)
            for company in companies
        ]
        for future in as_completed(futures):
            results.append(future.result())

    evidence, review, completeness, audit = [], [], [], []
    for result in sorted(results, key=lambda row: row["company"]["company_name"].casefold()):
        company = result["company"]
        accepted_names = {
            normalize_name(name): name for name in exact_query_names(company)
        }
        accepted = []
        for record, matched_name in result["records"]:
            normalized = normalize_name(record["company_name"])
            if normalized not in accepted_names:
                review.append({
                    "company_id": company["company_id"],
                    "company_name": company["company_name"],
                    "review_reason": "non_exact_establishment_name",
                    "candidate": record,
                })
            elif len(owners.get(normalized, set())) != 1:
                review.append({
                    "company_id": company["company_id"],
                    "company_name": company["company_name"],
                    "review_reason": "ambiguous_canonical_name",
                    "candidate": record,
                })
            else:
                accepted.append(mdel_to_evidence(company, record, run_date, matched_name))
        accepted = list({row["evidence_id"]: row for row in accepted}.values())
        evidence.extend(accepted)
        audit.extend({
            "company_id": company["company_id"],
            "company_name": company["company_name"],
            **query,
        } for query in result["queries"])
        has_review = any(row["company_id"] == company["company_id"] for row in review)
        status = (
            "partial" if result["errors"] and (result["records"] or accepted)
            else "failed" if result["errors"]
            else "manual_review" if has_review and not accepted
            else "complete_matches" if accepted
            else "complete_zero"
        )
        completeness.append({
            "company_id": company["company_id"],
            "company_name": company["company_name"],
            "status": status,
            "attempted_at": run_date,
            "source_url": SEARCH_URL,
            "raw_count": len(result["records"]),
            "accepted_count": len(accepted),
            "notes": "; ".join(result["errors"]) or (
                "Active MDEL listing searched by exact canonical/legal/alias names. "
                "MDEL is establishment evidence, not product approval."
            ),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "mdel_regulatory_evidence.json": {"schema_version": "1.0", "generated_at": run_date, "records": evidence},
        "mdel_completeness.json": {"schema_version": "1.0", "generated_at": run_date, "records": completeness},
        "mdel_manual_review.json": {"schema_version": "1.0", "generated_at": run_date, "records": review},
        "mdel_query_audit.json": {"schema_version": "1.0", "generated_at": run_date, "records": audit},
    }
    for filename, payload in outputs.items():
        (output_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
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
