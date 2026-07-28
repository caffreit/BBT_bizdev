from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .canada_hiring import classify_role
from .config import USER_AGENT
from .models import JobPosting


MODEL = "openai/gpt-5.6-luna"
PROMPT_VERSION = "canada_aggregator_hiring_v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
ALLOWED_HOST_SUFFIXES = (
    "linkedin.com", "indeed.com", "indeed.ca", "glassdoor.com", "glassdoor.ca",
    "jobbank.gc.ca", "biospace.com", "builtin.com", "ziprecruiter.com",
    "simplyhired.com", "talent.com", "jooble.org", "greenhouse.io", "lever.co",
    "ashbyhq.com", "workable.com", "smartrecruiters.com", "recruitee.com",
    "myworkdayjobs.com", "myworkdaysite.com", "icims.com", "dayforcehcm.com",
    "ultipro.com", "oraclecloud.com", "biotalent.ca", "trabajo.org",
)
ROLE_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"enum": ["found", "no_relevant_open_roles", "manual_review"]},
        "roles": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "job_title": {"type": "string"},
                    "job_url": {"type": "string"},
                    "source": {"type": "string"},
                    "location": {"type": "string"},
                    "department": {"type": "string"},
                    "posted_at": {"type": "string"},
                    "company_match": {"enum": ["exact", "uncertain", "wrong"]},
                    "posting_status": {"enum": ["open", "uncertain", "closed"]},
                    "evidence": {"type": "string"},
                },
                "required": [
                    "job_title", "job_url", "source", "location", "department",
                    "posted_at", "company_match", "posting_status", "evidence",
                ],
                "additionalProperties": False,
            },
        },
        "rationale": {"type": "string"},
    },
    "required": ["decision", "roles", "rationale"],
    "additionalProperties": False,
}


def build_prompt(company: dict) -> str:
    context = {
        "company_name": company.get("company_name", ""),
        "legal_name": company.get("legal_name", ""),
        "aliases": company.get("aliases", []),
        "website": company.get("website", ""),
        "province": company.get("province", ""),
        "product_category": company.get("product_category", ""),
        "product_summary": company.get("product_summary", "")[:1200],
    }
    return (
        "Find currently open, relevant jobs for the exact company below. Search indexed job "
        "aggregators and job boards, including LinkedIn Jobs, Indeed, Glassdoor, Canada Job Bank, "
        "BioSpace, Built In, ZipRecruiter, Talent.com, and ATS pages such as Greenhouse, Lever, "
        "Ashby, Workable, SmartRecruiters, and Recruitee. Try the exact company name in quotes "
        "with jobs/careers and with the relevant role families.\n\n"
        "Relevant roles: quality/QA/QMS/ISO 13485; regulatory/submissions; verification, validation "
        "or design assurance; clinical or medical affairs; manufacturing/process/design transfer; "
        "medical-product software, cybersecurity or product safety; R&D/product/biomedical/systems/"
        "mechanical/electrical/firmware engineering; and senior commercial expansion, market access, "
        "reimbursement, implementation or partnerships roles.\n\n"
        "Only return a role as open when a current listing page or current indexed job-board result "
        "supports it. Reject expired, closed, cached-only, generic talent-pool, recruiter reposts "
        "without a clear employer, similarly named companies, and roles outside the listed families. "
        "Use manual_review when a promising role cannot be confirmed as both current and attributable "
        "to the exact company. Use an empty roles array when none qualify.\n\n"
        + json.dumps(context, ensure_ascii=False)
    )


def request_luna(company: dict, api_key: str, model: str = MODEL) -> tuple[dict | None, dict, str]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": build_prompt(company)}],
        "plugins": [{"id": "web", "engine": "exa", "max_results": 10}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "aggregator_jobs", "strict": True, "schema": ROLE_SCHEMA},
        },
        "reasoning": {"effort": "low", "exclude": True},
    }
    request = Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        raw = urlopen(request, timeout=90).read().decode("utf-8", "ignore")
        response = json.loads(raw)
        message = response["choices"][0]["message"]
        decision = json.loads(message.get("content") or "{}")
        citations = []
        for item in message.get("annotations") or []:
            citation = item.get("url_citation", {}) if isinstance(item, dict) else {}
            if citation.get("url"):
                citations.append({
                    "url": citation["url"],
                    "title": citation.get("title", ""),
                    "content": citation.get("content", "")[:1000],
                })
        usage = response.get("usage") or {}
        usage["citations"] = citations
        return decision, usage, ""
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:500]
        return None, {}, f"OpenRouter HTTP {exc.code}: {detail or exc.reason}"
    except (OSError, URLError, KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        return None, {}, f"OpenRouter request failed: {str(exc)[:500]}"


def allowed_job_url(url: str, company_website: str = "") -> bool:
    host = urlsplit(url).netloc.lower().removeprefix("www.")
    official_host = urlsplit(company_website).netloc.lower().removeprefix("www.")
    return bool(host) and (
        any(host == suffix or host.endswith("." + suffix) for suffix in ALLOWED_HOST_SUFFIXES)
        or (official_host and (host == official_host or host.endswith("." + official_host)))
    )


def job_url_verification_level(url: str) -> str:
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.lower().rstrip("/")
    query = parts.query.lower()
    segments = [part for part in path.split("/") if part]
    if (
        "/jobs/view/" in path
        or "/job-listing/" in path
        or any(token in query for token in ("jk=", "vjk=", "jobid=", "job_id="))
        or (
            any(host == suffix or host.endswith("." + suffix) for suffix in (
                "greenhouse.io", "lever.co", "ashbyhq.com", "workable.com",
                "smartrecruiters.com", "recruitee.com", "myworkdayjobs.com",
                "myworkdaysite.com", "icims.com", "dayforcehcm.com",
            ))
            and len([part for part in path.split("/") if part]) >= 2
        )
        or "/job-" in path
        or path.count("/") >= 3
        or (
            len(segments) >= 2
            and segments[0] in {"job", "jobs", "career", "careers", "position", "positions"}
        )
    ):
        return "specific_listing"
    return "indexed_careers_or_results_page"


def validate_decision(company: dict, decision: dict | None, usage: dict, error: str, run_date: str) -> dict:
    base = {
        "company_id": company["company_id"],
        "company_name": company.get("company_name", ""),
        "status": "no_relevant_open_roles",
        "captured_at": run_date,
        "model": MODEL,
        "decision": decision or {},
        "citations": usage.get("citations", []),
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "estimated_cost_usd": float(usage.get("cost") or 0),
        "notes": error,
        "evidence": [],
    }
    if error or not decision:
        return {**base, "status": "llm_error"}

    accepted = []
    review = []
    for role in decision.get("roles") or []:
        posting = JobPosting(
            title=role.get("job_title", ""),
            url=role.get("job_url", ""),
            department=role.get("department", ""),
            location=role.get("location", ""),
            posted_at=role.get("posted_at", ""),
        )
        family, seniority, remote = classify_role(posting)
        valid = (
            role.get("company_match") == "exact"
            and role.get("posting_status") == "open"
            and family != "other"
            and allowed_job_url(posting.url, company.get("website", ""))
        )
        verification_level = job_url_verification_level(posting.url)
        item = {
            "company_id": company["company_id"],
            "company_name": company.get("company_name", ""),
            "job_title": posting.title,
            "department": posting.department,
            "location": posting.location,
            "posted_at": posting.posted_at or None,
            "job_url": posting.url,
            "source": role.get("source", ""),
            "role_family": family,
            "seniority": seniority,
            "remote_canada": remote,
            "posting_status": role.get("posting_status", ""),
            "confidence": "high" if valid and verification_level == "specific_listing" else "medium",
            "verification_level": verification_level,
            "evidence_summary": role.get("evidence", ""),
            "captured_at": run_date,
        }
        if valid:
            accepted.append(item)
        elif role.get("company_match") != "wrong" and role.get("posting_status") != "closed":
            review.append(item)
    seen = set()
    deduped = []
    for item in accepted:
        key = (item["job_url"].lower().rstrip("/"), item["job_title"].lower())
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    if deduped:
        return {
            **base,
            "status": "matches",
            "notes": decision.get("rationale", ""),
            "evidence": deduped,
            "manual_review_candidates": review,
        }
    if review or decision.get("decision") == "manual_review":
        return {
            **base,
            "status": "manual_review",
            "notes": decision.get("rationale", ""),
            "manual_review_candidates": review,
        }
    return {**base, "notes": decision.get("rationale", "")}


LunaFn = Callable[[dict, str, str], tuple[dict | None, dict, str]]


def run_aggregator_hiring(
    input_path: Path,
    website_evidence_path: Path,
    output_dir: Path,
    run_date: str | None = None,
    limit: int | None = None,
    workers: int = 6,
    model: str = MODEL,
    company_names: list[str] | None = None,
    luna_fn: LunaFn = request_luna,
) -> tuple[dict, dict[str, Path]]:
    run_date = run_date or date.today().isoformat()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip() or os.getenv("BBT_OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY or BBT_OPENROUTER_API_KEY is required")
    payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
    website_evidence = json.loads(website_evidence_path.read_text(encoding="utf-8-sig"))
    excluded_ids = {
        row["company_id"] for row in website_evidence.get("records", [])
        if row.get("status") == "inactive"
        or (
            row.get("status") == "manual_review"
            and row.get("notes") == "Luna-resolved domain already belongs to another canonical identity"
        )
    }
    targets = [row for row in payload.get("companies", []) if row["company_id"] not in excluded_ids]
    if company_names:
        wanted = {name.lower() for name in company_names}
        targets = [row for row in targets if row.get("company_name", "").lower() in wanted]
    if limit is not None:
        targets = targets[:limit]

    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / "cache"
    cache_dir.mkdir(exist_ok=True)

    def research(company: dict) -> dict:
        key = hashlib.sha1(
            f"{PROMPT_VERSION}|{model}|{company['company_id']}".encode()
        ).hexdigest()[:20]
        cache_path = cache_dir / f"{key}.json"
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return validate_decision(
                company, cached.get("decision"), cached.get("usage", {}),
                cached.get("error", ""), run_date,
            )
        decision, usage, error = luna_fn(company, api_key, model)
        cache_path.write_text(json.dumps({
            "company_id": company["company_id"],
            "decision": decision,
            "usage": usage,
            "error": error,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        return validate_decision(company, decision, usage, error, run_date)

    records = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(research, company): company for company in targets}
        for future in as_completed(futures):
            company = futures[future]
            try:
                records.append(future.result())
            except Exception as exc:
                records.append(validate_decision(
                    company, None, {}, f"{type(exc).__name__}: {str(exc)[:300]}", run_date
                ))
    records.sort(key=lambda row: (row["company_name"].lower(), row["company_id"]))
    evidence = [item for row in records for item in row.get("evidence", [])]
    counts: dict[str, int] = {}
    for row in records:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    summary = {
        "schema_version": "1.0",
        "generated_at": run_date,
        "model": model,
        "companies_attempted": len(records),
        "companies_excluded_inactive_or_duplicate": len(excluded_ids),
        "status_counts": counts,
        "relevant_open_jobs": len(evidence),
        "companies_with_relevant_jobs": counts.get("matches", 0),
        "prompt_tokens": sum(row["prompt_tokens"] for row in records),
        "completion_tokens": sum(row["completion_tokens"] for row in records),
        "estimated_cost_usd": round(sum(row["estimated_cost_usd"] for row in records), 6),
    }
    files = {
        "evidence": output_dir / "aggregator_hiring_evidence.json",
        "completeness": output_dir / "aggregator_hiring_completeness.json",
        "summary": output_dir / "run_summary.json",
    }
    files["evidence"].write_text(json.dumps({
        "schema_version": "1.0", "generated_at": run_date, "records": evidence,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    files["completeness"].write_text(json.dumps({
        "schema_version": "1.0", "generated_at": run_date, "records": records,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    files["summary"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary, files
