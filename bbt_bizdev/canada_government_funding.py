from __future__ import annotations

import hashlib
import html
import json
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

from bbt_bizdev.canada_consolidation import normalize_name


BASE_URL = "https://search.open.canada.ca"
SEARCH_URL = BASE_URL + "/grants/"
USER_AGENT = "BlueBridge-company-funding-research/1.0"
LEGAL_ENDINGS = re.compile(
    r"\b(?:incorporated|inc|corporation|corp|limited|ltd|ulc|llc|lp)\.?\s*$",
    re.IGNORECASE,
)


def _text(fragment: str) -> str:
    fragment = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(fragment)).strip()


def _field(block: str, label: str) -> str:
    match = re.search(
        rf"(?is)<strong>{re.escape(label)}:</strong>\s*(.*?)(?=<strong>|</div>\s*<div class=\"col-sm-12|$)",
        block,
    )
    return _text(match.group(1)) if match else ""


def parse_search_results(page: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    blocks = re.split(
        r'(?is)<div class="row mrgn-bttm-xl mrgn-lft-md">\s*', page
    )[1:]
    for block in blocks:
        block = block.split('<div class="text-center">', 1)[0]
        link = re.search(r'(?is)<a href="(/grants/record/[^"]+)">\s*(.*?)</a>', block)
        if not link:
            continue
        amount_date = re.search(
            r'(?is)<div class="col-sm-4 text-right">.*?<h4[^>]*>(.*?)</h4>\s*<h5[^>]*>(.*?)</h5>',
            block,
        )
        rows.append({
            "recipient_name": _text(link.group(2)),
            "evidence_url": urljoin(BASE_URL, html.unescape(link.group(1))),
            "amount_original": _text(amount_date.group(1)) if amount_date else "",
            "event_date_published": _text(amount_date.group(2)) if amount_date else "",
            "agreement_title": _field(block, "Agreement"),
            "agreement_number": _field(block, "Agreement Number"),
            "description": _field(block, "Description"),
            "funder": _field(block, "Organization"),
            "program": _field(block, "Program Name"),
            "location": _field(block, "Location"),
        })
    return rows


def parse_detail(page: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for label, value in re.findall(
        r'(?is)<div class="col-sm-4"><strong>(.*?):</strong></div>\s*'
        r'<div class="col-sm-8">(.*?)</div>',
        page,
    ):
        values[_text(label)] = _text(value)
    return values


def published_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%b %d, %Y").date().isoformat()
    except ValueError:
        return ""


def amount_cad(value: str) -> float | None:
    cleaned = re.sub(r"[^0-9.\-]", "", value)
    try:
        return float(cleaned)
    except ValueError:
        return None


def classify_use_of_funds(title: str, description: str) -> list[str]:
    text = f"{title} {description}".casefold()
    rules = {
        "hiring": ("hire", "hiring", "employment", "coordinator", "youth"),
        "R&D": ("research", "develop", "prototype", "innovation", "design"),
        "clinical": ("clinical", "trial", "patient", "study"),
        "regulatory": ("regulatory", "approval", "licen", "submission"),
        "manufacturing": ("manufactur", "production", "scale-up", "scale up"),
        "market entry": ("market", "commercial", "export", "sales"),
    }
    return [label for label, terms in rules.items() if any(term in text for term in terms)] or ["other"]


def _get(url: str, timeout: int = 30, retries: int = 2) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception:
            if attempt == retries:
                raise
            time.sleep(0.5 * (attempt + 1))
    return ""


def query_url(name: str, page: int = 1) -> str:
    phrase = f'"{name}"'
    return (
        f"{SEARCH_URL}?sort=agreement_start_date+desc"
        f"&search_text={quote(phrase)}&page={page}"
    )


def query_names(company: dict[str, Any]) -> list[str]:
    names = [company.get("company_name", ""), *company.get("aliases", [])]
    cleaned = []
    for name in names:
        name = re.sub(r"\s*\([^)]*\)\s*$", "", str(name)).strip()
        if name and name not in cleaned:
            cleaned.append(name)
    return cleaned[:3]


def collect_company_candidates(company: dict[str, Any], max_pages: int = 3) -> dict[str, Any]:
    accepted_names = {
        normalize_name(name)
        for name in query_names(company)
        if normalize_name(name)
    }
    found: dict[str, dict[str, str]] = {}
    checked_urls = []
    error = ""
    for name in query_names(company):
        for page_number in range(1, max_pages + 1):
            url = query_url(name, page_number)
            checked_urls.append(url)
            try:
                rows = parse_search_results(_get(url))
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                break
            for row in rows:
                if normalize_name(row["recipient_name"]) in accepted_names:
                    found[row["evidence_url"]] = row
            if len(rows) < 10:
                break
    return {
        "company_id": company["company_id"],
        "company_name": company["company_name"],
        "accepted_names": sorted(accepted_names),
        "checked_urls": checked_urls,
        "candidates": list(found.values()),
        "error": error,
    }


def _event_id(company_id: str, url: str) -> str:
    digest = hashlib.sha256(f"{company_id}|{url}".encode("utf-8")).hexdigest()[:20]
    return "ca-funding-event-" + digest


def candidate_to_event(
    company_id: str, row: dict[str, str], detail: dict[str, str], captured_at: str
) -> dict[str, Any] | None:
    event_date = published_date(row["event_date_published"])
    agreement_type = detail.get("Agreement Type", "").casefold()
    funding_type = {
        "grant": "grant",
        "contribution": "contribution",
        "other transfer payment": "undisclosed",
    }.get(agreement_type, "undisclosed")
    if not event_date or amount_cad(row["amount_original"]) is None:
        return None
    title = detail.get("Title") or row["agreement_title"]
    description = detail.get("Description") or row["description"]
    return {
        "funding_event_id": _event_id(company_id, row["evidence_url"]),
        "company_id": company_id,
        "event_date": event_date,
        "funding_type": funding_type,
        "stage": "grant" if funding_type == "grant" else "unknown",
        "amount_original": row["amount_original"],
        "currency": "CAD",
        "amount_cad": amount_cad(row["amount_original"]),
        "investors_or_funders": [detail.get("Organization") or row["funder"]],
        "lead_investor": "",
        "use_of_funds": classify_use_of_funds(title, description),
        "evidence_url": row["evidence_url"],
        "source_type": "government",
        "confidence": "high",
        "captured_at": captured_at,
        "extraction_method": "government_grants_exact_recipient_match",
        "recipient_legal_name": detail.get("Recipient's Legal Name") or row["recipient_name"],
        "agreement_number": detail.get("Agreement Number") or row["agreement_number"],
        "agreement_title": title,
        "description": description,
        "program": detail.get("Program") or row["program"],
        "location": detail.get("Location") or row["location"],
        "recipient_business_number": detail.get("Recipient Business Number", ""),
    }


def run_government_funding(
    companies_path: Path,
    output_dir: Path,
    run_date: str,
    workers: int = 4,
    backed_only: bool = True,
) -> dict[str, Any]:
    payload = json.loads(companies_path.read_text(encoding="utf-8"))
    companies = payload["companies"]
    if backed_only:
        companies = [row for row in companies if row.get("funding_backing_count", 0)]

    name_owners: dict[str, set[str]] = {}
    for company in companies:
        for name in query_names(company):
            normalized = normalize_name(name)
            name_owners.setdefault(normalized, set()).add(company["company_id"])

    results = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(collect_company_candidates, row): row for row in companies}
        for index, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if index % 25 == 0 or index == len(futures):
                print(f"searched {index}/{len(futures)} companies", flush=True)

    events = []
    review = []
    candidate_jobs = []
    accepted_counts: dict[str, int] = defaultdict(int)
    for result in sorted(results, key=lambda row: row["company_name"].casefold()):
        for candidate in result["candidates"]:
            normalized = normalize_name(candidate["recipient_name"])
            owners = name_owners.get(normalized, set())
            if len(owners) != 1:
                review.append({
                    **candidate,
                    "queried_company_id": result["company_id"],
                    "queried_company_name": result["company_name"],
                    "review_reason": "ambiguous_canonical_name",
                    "candidate_company_ids": sorted(owners),
                })
                continue
            candidate_jobs.append((result, candidate))

    def fetch_detail(job: tuple[dict[str, Any], dict[str, str]]) -> tuple[
        dict[str, Any], dict[str, str], dict[str, str] | None, str
    ]:
        result, candidate = job
        try:
            return result, candidate, parse_detail(_get(candidate["evidence_url"])), ""
        except Exception as exc:
            return result, candidate, None, f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(fetch_detail, job) for job in candidate_jobs]
        for index, future in enumerate(as_completed(futures), start=1):
            result, candidate, detail, error = future.result()
            if error:
                review.append({
                    **candidate,
                    "queried_company_id": result["company_id"],
                    "queried_company_name": result["company_name"],
                    "review_reason": f"detail_fetch_failed: {error}",
                })
                continue
            try:
                assert detail is not None
                event = candidate_to_event(result["company_id"], candidate, detail, run_date)
            except Exception:
                event = None
            legal_normalized = normalize_name(detail.get("Recipient's Legal Name", ""))
            if legal_normalized not in result["accepted_names"]:
                review.append({
                    **candidate,
                    "queried_company_id": result["company_id"],
                    "queried_company_name": result["company_name"],
                    "review_reason": "detail_legal_name_mismatch",
                    "detail_legal_name": detail.get("Recipient's Legal Name", ""),
                })
            elif event:
                events.append(event)
                accepted_counts[result["company_id"]] += 1
            if index % 50 == 0 or index == len(futures):
                print(f"validated {index}/{len(futures)} award records", flush=True)

    statuses = []
    for result in sorted(results, key=lambda row: row["company_name"].casefold()):
        accepted_count = accepted_counts[result["company_id"]]
        status = (
            "failed" if result["error"]
            else "complete_matches" if accepted_count
            else "complete_zero"
        )
        statuses.append({
            "company_id": result["company_id"],
            "company_name": result["company_name"],
            "status": status,
            "attempted_at": run_date,
            "source_url": SEARCH_URL,
            "raw_count": len(result["candidates"]),
            "accepted_count": accepted_count,
            "notes": result["error"] or "Exact-phrase federal grants search completed.",
        })

    # Detail URLs are unique government records; remove repeats caused by aliases.
    events = list({row["funding_event_id"]: row for row in events}.values())
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "government_funding_events.json": {"schema_version": "1.0", "generated_at": run_date, "events": events},
        "government_funding_completeness.json": {"schema_version": "1.0", "generated_at": run_date, "records": statuses},
        "government_funding_review.json": {"schema_version": "1.0", "generated_at": run_date, "records": review},
    }
    for filename, data in outputs.items():
        (output_dir / filename).write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    summary = {
        "schema_version": "1.0",
        "generated_at": run_date,
        "companies_searched": len(companies),
        "companies_with_events": len({row["company_id"] for row in events}),
        "accepted_events": len(events),
        "manual_review_candidates": len(review),
        "failed_searches": sum(row["status"] == "failed" for row in statuses),
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary
