from __future__ import annotations

import hashlib
import html
from http.client import IncompleteRead
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from .adapters.jobs import JOB_PARSERS, job_board_url
from .config import USER_AGENT
from .models import JobPosting
from .text import clean_text, extract_links


ATS_PATTERNS = (
    ("greenhouse", re.compile(r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([^/?#&\"'<>\s]+)", re.I)),
    ("lever", re.compile(r"jobs\.lever\.co/([^/?#\"'<>\s]+)", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([^/?#\"'<>\s]+)", re.I)),
    ("workable", re.compile(r"apply\.workable\.com/([^/?#\"'<>\s]+)", re.I)),
    ("smartrecruiters", re.compile(r"jobs\.smartrecruiters\.com/([^/?#\"'<>\s]+)", re.I)),
    ("recruitee", re.compile(r"https?://([^.]+)\.recruitee\.com", re.I)),
)
CAREERS_TEXT = re.compile(r"\b(careers?|jobs?|join (?:us|our team)|work with us|opportunit(?:y|ies))\b", re.I)
JOB_PATH = re.compile(r"/(?:jobs?|careers?|positions?|openings?|opportunities?)(?:/|$)", re.I)
JOB_DETAIL_PATH = re.compile(r"/(?:jobs?|positions?|openings?)/[^/?#]+", re.I)
BLOCKED_MARKERS = (
    "captcha", "access denied", "verify you are human",
    "attention required! | cloudflare", "cf-chl-",
)

ROLE_RULES = (
    ("QA", ("quality", "qms", "iso 13485", "supplier quality")),
    ("regulatory", ("regulatory", "submission", "market authorization")),
    ("V&V/design assurance", ("verification", "validation", "v&v", "design assurance", "test engineer")),
    ("clinical", ("clinical", "medical affairs")),
    ("manufacturing", ("manufacturing", "process development", "design transfer", "tech transfer", "operations scale")),
    ("software medical product", ("samd", "iec 62304", "cybersecurity", "product safety", "software quality")),
    ("R&D/product", (
        "r&d", "research and development", "research engineer", "research scientist",
        "product development", "product engineer", "biomedical", "systems engineer",
        "mechanical engineer", "electrical engineer", "firmware", "machine learning",
        "mlops", "full stack", "backend", "infrastructure engineer", "data scientist",
        "bioinformatics", "computational",
    )),
    ("commercial expansion", ("country manager", "market access", "reimbursement", "implementation", "partnerships")),
)
SENIOR_RULES = (
    ("VP/executive", re.compile(r"\b(vp|vice president|chief|c[etos]o)\b", re.I)),
    ("director", re.compile(r"\b(director|head of)\b", re.I)),
    ("manager", re.compile(r"\b(manager|lead)\b", re.I)),
)


@dataclass(frozen=True)
class FetchResult:
    url: str
    body: str = ""
    status: int = 0
    error: str = ""
    content_type: str = ""


Fetcher = Callable[[str], FetchResult]


def fetch_url(url: str) -> FetchResult:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"})
    try:
        with urlopen(request, timeout=25) as response:
            try:
                raw = response.read()
            except IncompleteRead as exc:
                raw = exc.partial
            content_type = response.headers.get("Content-Type", "")
            return FetchResult(
                url=response.geturl(), body=raw.decode("utf-8", "ignore"),
                status=getattr(response, "status", 200), content_type=content_type,
            )
    except HTTPError as exc:
        return FetchResult(url=url, status=exc.code, error=str(exc))
    except (OSError, URLError) as exc:
        return FetchResult(url=url, error=str(exc))


def detect_ats(url: str) -> tuple[str, str]:
    for provider, pattern in ATS_PATTERNS:
        match = pattern.search(url)
        if match:
            account = match.group(1).strip().lower()
            if account not in {"embed", "jobs", "careers"}:
                return provider, account
    return "", ""


def _identity_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def board_matches_company(account: str, company: dict) -> bool:
    board = _identity_token(account)
    if not board:
        return False
    names = [
        company.get("company_name", ""), company.get("legal_name", ""),
        *company.get("aliases", []),
    ]
    for value in names:
        token = _identity_token(value)
        if len(token) >= 4 and (token in board or board in token):
            return True
    return False


def discover_careers(homepage_url: str, raw_html: str) -> list[str]:
    candidates: list[str] = []
    for label, href in extract_links(raw_html, homepage_url):
        absolute = urljoin(homepage_url, html.unescape(href))
        if absolute.startswith(("http://", "https://")) and (
            CAREERS_TEXT.search(clean_text(label)) or JOB_PATH.search(urlparse(absolute).path)
            or detect_ats(absolute)[0]
        ):
            candidates.append(absolute)
    seen: set[str] = set()
    return [url for url in candidates if not (url in seen or seen.add(url))][:8]


def parse_static_jobs(raw_html: str, page_url: str) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    seen: set[str] = set()
    for label, href in extract_links(raw_html, page_url):
        title = clean_text(label)
        url = urljoin(page_url, html.unescape(href))
        path = urlparse(url).path
        if not title or len(title) > 180 or url in seen:
            continue
        if JOB_DETAIL_PATH.search(path) and path.rstrip("/") != urlparse(page_url).path.rstrip("/"):
            seen.add(url)
            jobs.append(JobPosting(title=title, url=url))
    return jobs


def classify_role(posting: JobPosting) -> tuple[str, str, str]:
    text = " ".join((posting.title, posting.department)).lower()
    family = "other"
    for candidate, terms in ROLE_RULES:
        if any(term in text for term in terms):
            family = candidate
            break
    if family == "other" and re.search(r"\b(software|firmware|product|systems?) engineer\b", text):
        regulated_terms = ("samd", "iec 62304", "medical device", "regulated product", "clinical software")
        if any(term in posting.description.lower() for term in regulated_terms):
            family = "software medical product"
    seniority = "individual contributor"
    for candidate, pattern in SENIOR_RULES:
        if pattern.search(posting.title):
            seniority = candidate
            break
    if not posting.title:
        seniority = "unclear"
    remote = "yes" if re.search(r"\b(remote.*canada|canada.*remote)\b", text) else "unclear"
    return family, seniority, remote


def _job_id(posting: JobPosting) -> str:
    if posting.job_id:
        return posting.job_id
    parts = [part for part in urlparse(posting.url).path.split("/") if part]
    return parts[-1] if parts else hashlib.sha1(f"{posting.title}|{posting.url}".encode()).hexdigest()[:16]


def _evidence_id(company_id: str, posting: JobPosting) -> str:
    value = f"{company_id}|{_job_id(posting)}|{posting.url}"
    return "hire-" + hashlib.sha1(value.encode()).hexdigest()[:20]


def _blocked(result: FetchResult) -> bool:
    body = result.body.lower()
    return result.status in {401, 403, 429} or any(marker in body for marker in BLOCKED_MARKERS)


def _parse_ats(provider: str, body: str) -> tuple[list[JobPosting], str]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        return [], f"ATS JSON decode failed: {exc}"
    return JOB_PARSERS[provider](payload), ""


def _normalize_posted_at(value: str) -> str | None:
    if not value:
        return None
    if value.isdigit():
        try:
            from datetime import datetime, timezone
            stamp = int(value)
            if stamp > 10_000_000_000:
                stamp //= 1000
            return datetime.fromtimestamp(stamp, timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    match = re.match(r"(\d{4}-\d{2}-\d{2})", value)
    return match.group(1) if match else None


def enrich_company_hiring(company: dict, run_date: str, fetcher: Fetcher = fetch_url) -> dict:
    company_id = company["company_id"]
    website = company.get("website", "")
    base = {
        "company_id": company_id, "company_name": company.get("company_name", ""),
        "careers_url": "", "ats_provider": "none", "ats_board_id": "",
        "raw_count": None, "accepted_count": None, "status": "not_run",
        "attempted_at": run_date, "notes": "", "evidence": [],
    }
    if not website:
        return {**base, "status": "no_source", "notes": "No official company website in canonical table"}

    homepage = fetcher(website)
    if homepage.error or homepage.status >= 400:
        status = "blocked" if _blocked(homepage) else "partial"
        return {**base, "status": status, "careers_url": website, "notes": homepage.error or f"HTTP {homepage.status}"}
    if _blocked(homepage):
        return {**base, "status": "blocked", "careers_url": homepage.url, "notes": "Access challenge on official website"}

    careers_urls = discover_careers(homepage.url, homepage.body)
    provider, account = ("", "")
    for candidate in careers_urls:
        provider, account = detect_ats(candidate)
        if provider:
            break
    selected_url = ""
    if provider:
        selected_url = job_board_url(provider, account)
        if not board_matches_company(account, company):
            return {
                **base, "status": "manual_review", "careers_url": selected_url,
                "ats_provider": provider, "ats_board_id": account,
                "notes": f"ATS account '{account}' does not match canonical company identity",
            }
    else:
        for candidate in careers_urls:
            provider, account = detect_ats(candidate)
            if provider:
                selected_url = job_board_url(provider, account)
                break

    postings: list[JobPosting] = []
    notes = ""
    if provider:
        result = fetcher(selected_url)
        if result.error or result.status >= 400 or _blocked(result):
            status = "blocked" if _blocked(result) else "partial"
            return {
                **base, "status": status, "careers_url": selected_url,
                "ats_provider": provider, "ats_board_id": account,
                "notes": result.error or f"HTTP {result.status}",
            }
        postings, notes = _parse_ats(provider, result.body)
    elif careers_urls:
        selected_url = careers_urls[0]
        result = fetcher(selected_url)
        if result.error or result.status >= 400 or _blocked(result):
            status = "blocked" if _blocked(result) else "partial"
            return {**base, "status": status, "careers_url": selected_url, "notes": result.error or f"HTTP {result.status}"}
        second_provider, second_account = detect_ats(result.url + " " + result.body)
        if second_provider:
            provider, account = second_provider, second_account
            selected_url = job_board_url(provider, account)
            if not board_matches_company(account, company):
                return {
                    **base, "status": "manual_review", "careers_url": selected_url,
                    "ats_provider": provider, "ats_board_id": account,
                    "notes": f"ATS account '{account}' does not match canonical company identity",
                }
            ats_result = fetcher(selected_url)
            if ats_result.error or ats_result.status >= 400 or _blocked(ats_result):
                status = "blocked" if _blocked(ats_result) else "partial"
                return {
                    **base, "status": status, "careers_url": selected_url,
                    "ats_provider": provider, "ats_board_id": account,
                    "notes": ats_result.error or f"HTTP {ats_result.status}",
                }
            postings, notes = _parse_ats(provider, ats_result.body)
        else:
            postings = parse_static_jobs(result.body, result.url)
            notes = "Static official careers page; only visible linked postings counted"
    else:
        home_root = f"{urlparse(homepage.url).scheme}://{urlparse(homepage.url).netloc}"
        probe_results = []
        for path in ("/careers", "/jobs"):
            probe = fetcher(home_root + path)
            probe_results.append(probe)
            if not probe.error and probe.status < 400 and CAREERS_TEXT.search(clean_text(probe.body)):
                selected_url = probe.url
                postings = parse_static_jobs(probe.body, probe.url)
                notes = "Static official careers route discovered by bounded path check"
                break
        if not selected_url:
            blocked = any(_blocked(probe) for probe in probe_results)
            return {
                **base, "status": "blocked" if blocked else "no_source",
                "careers_url": homepage.url,
                "notes": "Official careers path blocked" if blocked else "No official careers route identified",
            }

    evidence: list[dict] = []
    relevant: list[tuple[JobPosting, str, str, str]] = []
    for posting in postings:
        family, seniority, remote = classify_role(posting)
        if family != "other":
            relevant.append((posting, family, seniority, remote))
    high_signal = len(relevant) >= 3 or any(row[2] in {"director", "VP/executive"} for row in relevant)
    strength = "high" if high_signal else ("medium" if relevant else "low")
    for posting, family, seniority, remote in relevant:
        evidence.append({
            "evidence_id": _evidence_id(company_id, posting), "company_id": company_id,
            "track": "hiring", "claim_type": "open_job", "careers_url": selected_url,
            "ats_provider": provider or "custom", "ats_board_id": account,
            "job_id": _job_id(posting), "job_title": posting.title,
            "department": posting.department, "location": posting.location,
            "remote_canada": remote, "posted_at": _normalize_posted_at(posting.posted_at),
            "job_url": posting.url or selected_url,
            "role_family": family, "seniority": seniority, "signal_strength": strength,
            "captured_at": run_date, "posting_status": "open",
            "evidence_url": posting.url or selected_url, "evidence_date": None,
            "extraction_method": f"{provider or 'custom'}_official_careers",
            "confidence": "high" if provider else "medium", "source_type": "company",
            "summary": f"Open {family} role: {posting.title}",
        })
    status = "complete_matches" if evidence else "complete_zero"
    return {
        **base, "status": status, "careers_url": selected_url,
        "ats_provider": provider or ("custom" if careers_urls else "none"),
        "ats_board_id": account, "raw_count": len(postings),
        "accepted_count": len(evidence), "notes": notes, "evidence": evidence,
    }


def run_hiring_enrichment(
    input_path: Path, output_dir: Path, run_date: str | None = None,
    workers: int = 8, limit: int | None = None, fetcher: Fetcher = fetch_url,
) -> tuple[dict, dict[str, Path]]:
    run_date = run_date or date.today().isoformat()
    payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
    companies = payload.get("companies", [])
    if limit is not None:
        companies = companies[:limit]
    domain_counts: dict[str, int] = {}
    for row in companies:
        domain = row.get("domain", "")
        if domain:
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
    ambiguous_ids = {
        row["company_id"] for row in companies
        if row.get("domain") and domain_counts.get(row["domain"], 0) > 1
    }
    results: list[dict] = []
    for row in companies:
        if row["company_id"] in ambiguous_ids:
            results.append({
                "company_id": row["company_id"], "company_name": row.get("company_name", ""),
                "careers_url": row.get("website", ""), "ats_provider": "none",
                "ats_board_id": "", "raw_count": None, "accepted_count": None,
                "status": "manual_review", "attempted_at": run_date,
                "notes": f"Canonical identity shares domain {row.get('domain')} with another company",
                "evidence": [],
            })
    runnable = [row for row in companies if row["company_id"] not in ambiguous_ids]
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(enrich_company_hiring, row, run_date, fetcher): row for row in runnable}
        for future in as_completed(futures):
            company = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({
                    "company_id": company["company_id"],
                    "company_name": company.get("company_name", ""),
                    "careers_url": company.get("website", ""),
                    "ats_provider": "none", "ats_board_id": "",
                    "raw_count": None, "accepted_count": None,
                    "status": "partial", "attempted_at": run_date,
                    "notes": f"Unexpected site-processing error: {type(exc).__name__}: {str(exc)[:300]}",
                    "evidence": [],
                })
    results.sort(key=lambda row: (row["company_name"].lower(), row["company_id"]))

    route_groups: dict[str, list[dict]] = {}
    for row in results:
        if row["ats_board_id"]:
            route = f"{row['ats_provider']}:{row['ats_board_id']}"
        elif row["careers_url"] and row["ats_provider"] == "custom":
            route = f"custom:{row['careers_url'].lower().rstrip('/')}"
        else:
            continue
        route_groups.setdefault(route, []).append(row)
    for route, grouped in route_groups.items():
        if len({row["company_id"] for row in grouped}) < 2:
            continue
        for row in grouped:
            row["status"] = "manual_review"
            row["raw_count"] = None
            row["accepted_count"] = None
            row["notes"] = f"Careers route is shared by multiple canonical identities: {route}"
            row["evidence"] = []

    evidence = [item for row in results for item in row["evidence"]]
    by_id = {row["company_id"]: row for row in results}
    enriched_companies = []
    for company in payload.get("companies", []):
        copied = json.loads(json.dumps(company))
        result = by_id.get(company["company_id"])
        if result:
            copied["completeness"]["hiring"] = {
                "status": result["status"], "attempted_at": run_date,
                "source_url": result["careers_url"], "raw_count": result["raw_count"],
                "accepted_count": result["accepted_count"], "notes": result["notes"],
            }
            copied["last_enriched_at"] = run_date
        enriched_companies.append(copied)

    counts: dict[str, int] = {}
    for row in results:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    complete = counts.get("complete_matches", 0) + counts.get("complete_zero", 0)
    summary = {
        "schema_version": "1.0", "generated_at": run_date,
        "canonical_companies": len(payload.get("companies", [])), "companies_attempted": len(results),
        "companies_with_websites_attempted": sum(bool(row.get("website")) for row in companies),
        "status_counts": counts, "complete_or_complete_zero": complete,
        "completion_rate": round(complete / len(results), 4) if results else 0,
        "raw_open_jobs": sum(row["raw_count"] or 0 for row in results),
        "relevant_open_jobs": len(evidence),
        "companies_with_relevant_jobs": counts.get("complete_matches", 0),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "companies": output_dir / "canonical_companies_hiring_enriched.json",
        "evidence": output_dir / "hiring_evidence.json",
        "completeness": output_dir / "hiring_completeness.json",
        "summary": output_dir / "run_summary.json",
    }
    files["companies"].write_text(json.dumps({"schema_version": "1.0", "generated_at": run_date, "companies": enriched_companies}, indent=2, ensure_ascii=False), encoding="utf-8")
    files["evidence"].write_text(json.dumps({"schema_version": "1.0", "generated_at": run_date, "records": evidence}, indent=2, ensure_ascii=False), encoding="utf-8")
    files["completeness"].write_text(json.dumps({"schema_version": "1.0", "generated_at": run_date, "records": [{key: value for key, value in row.items() if key != "evidence"} for row in results]}, indent=2, ensure_ascii=False), encoding="utf-8")
    files["summary"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary, files
