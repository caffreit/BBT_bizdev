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

from .config import USER_AGENT


MODEL = "openai/gpt-5.6-luna"
PROMPT_VERSION = "canada_hiring_official_validation_v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
ATS_SUFFIXES = (
    "greenhouse.io", "lever.co", "ashbyhq.com", "workable.com",
    "smartrecruiters.com", "recruitee.com", "myworkdayjobs.com",
    "myworkdaysite.com", "icims.com", "dayforcehcm.com", "ultipro.com",
    "oraclecloud.com",
)
SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"enum": ["official_open", "official_not_found", "closed", "ambiguous"]},
        "official_job_url": {"type": "string"},
        "official_source_type": {"enum": ["employer", "ats", "none"]},
        "identity_signals": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
        "current_signals": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
        "rationale": {"type": "string"},
    },
    "required": [
        "decision", "official_job_url", "official_source_type",
        "identity_signals", "current_signals", "rationale",
    ],
    "additionalProperties": False,
}


def _host(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


def is_official_or_ats(url: str, company_website: str) -> tuple[bool, str]:
    host = _host(url)
    official_host = _host(company_website)
    if official_host and (host == official_host or host.endswith("." + official_host)):
        return True, "employer"
    if any(host == suffix or host.endswith("." + suffix) for suffix in ATS_SUFFIXES):
        return True, "ats"
    return False, "none"


def build_prompt(company: dict, role: dict) -> str:
    context = {
        "company_name": company.get("company_name", ""),
        "legal_name": company.get("legal_name", ""),
        "aliases": company.get("aliases", []),
        "official_company_website": company.get("website", ""),
        "job_title": role.get("job_title", ""),
        "aggregator_url": role.get("job_url", ""),
        "aggregator_source": role.get("source", ""),
        "location": role.get("location", ""),
        "aggregator_evidence": role.get("evidence_summary", ""),
    }
    return (
        "Verify whether this exact role is currently open using only the employer's own website "
        "or an employer-controlled ATS page (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, "
        "Recruitee, Workday, iCIMS, Dayforce, Oracle or equivalent). Search the exact company and "
        "job title, including distinctive title fragments. Do not treat LinkedIn, Indeed, "
        "Glassdoor, BioSpace, Built In, Trabajo, Talent.com, recruiter pages, or search snippets "
        "as official evidence. Return official_open only when an employer-domain or ATS page "
        "supports both the exact company and a currently open substantially matching role. "
        "Return closed if official evidence says it is closed; official_not_found if no official "
        "page can be found; ambiguous if the official page exists but identity/current status is "
        "unclear. Leave official_job_url empty unless decision is official_open.\n\n"
        + json.dumps(context, ensure_ascii=False)
    )


def request_luna(company: dict, role: dict, api_key: str, model: str = MODEL) -> tuple[dict | None, dict, str]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": build_prompt(company, role)}],
        "plugins": [{"id": "web", "engine": "exa", "max_results": 8}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "official_job_validation", "strict": True, "schema": SCHEMA},
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
        usage = response.get("usage") or {}
        return decision, usage, ""
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:500]
        return None, {}, f"OpenRouter HTTP {exc.code}: {detail or exc.reason}"
    except (OSError, URLError, KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        return None, {}, f"OpenRouter request failed: {str(exc)[:500]}"


def validate_result(company: dict, role: dict, decision: dict | None, usage: dict, error: str, run_date: str) -> dict:
    result = {
        **role,
        "validation_status": "validation_error" if error or not decision else decision.get("decision", "ambiguous"),
        "official_job_url": "",
        "official_source_type": "none",
        "validation_method": "luna_official_search",
        "validation_notes": error or (decision or {}).get("rationale", ""),
        "validated_at": run_date,
        "validation_prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "validation_completion_tokens": int(usage.get("completion_tokens") or 0),
        "validation_cost_usd": float(usage.get("cost") or 0),
    }
    if error or not decision or decision.get("decision") != "official_open":
        return result
    url = decision.get("official_job_url", "")
    allowed, source_type = is_official_or_ats(url, company.get("website", ""))
    if not allowed:
        return {
            **result,
            "validation_status": "ambiguous",
            "validation_notes": "Luna returned a non-employer/non-ATS URL",
        }
    return {
        **result,
        "validation_status": "official_open",
        "official_job_url": url,
        "official_source_type": source_type,
    }


LunaFn = Callable[[dict, dict, str, str], tuple[dict | None, dict, str]]


def run_official_validation(
    aggregator_evidence_path: Path,
    canonical_path: Path,
    output_dir: Path,
    run_date: str | None = None,
    workers: int = 6,
    model: str = MODEL,
    luna_fn: LunaFn = request_luna,
) -> tuple[dict, dict[str, Path]]:
    run_date = run_date or date.today().isoformat()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip() or os.getenv("BBT_OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY or BBT_OPENROUTER_API_KEY is required")
    evidence = json.loads(aggregator_evidence_path.read_text(encoding="utf-8-sig"))
    canonical = json.loads(canonical_path.read_text(encoding="utf-8-sig"))
    by_id = {row["company_id"]: row for row in canonical.get("companies", [])}
    roles = [row for row in evidence.get("records", []) if row.get("confidence") == "high"]

    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / "cache"
    cache_dir.mkdir(exist_ok=True)

    def validate(role: dict) -> dict:
        company = by_id[role["company_id"]]
        direct, source_type = is_official_or_ats(role.get("job_url", ""), company.get("website", ""))
        if direct:
            return {
                **role,
                "validation_status": "official_open",
                "official_job_url": role["job_url"],
                "official_source_type": source_type,
                "validation_method": "direct_official_or_ats_url",
                "validation_notes": "Specific listing URL is on the employer domain or a recognized ATS",
                "validated_at": run_date,
                "validation_prompt_tokens": 0,
                "validation_completion_tokens": 0,
                "validation_cost_usd": 0.0,
            }
        key = hashlib.sha1(
            f"{PROMPT_VERSION}|{model}|{role['company_id']}|{role['job_title']}|{role['job_url']}".encode()
        ).hexdigest()[:20]
        cache_path = cache_dir / f"{key}.json"
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return validate_result(
                company, role, cached.get("decision"), cached.get("usage", {}),
                cached.get("error", ""), run_date,
            )
        decision, usage, error = luna_fn(company, role, api_key, model)
        cache_path.write_text(json.dumps({
            "company_id": role["company_id"],
            "job_title": role["job_title"],
            "decision": decision,
            "usage": usage,
            "error": error,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        return validate_result(company, role, decision, usage, error, run_date)

    records = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(validate, role): role for role in roles}
        for future in as_completed(futures):
            role = futures[future]
            try:
                records.append(future.result())
            except Exception as exc:
                records.append({
                    **role,
                    "validation_status": "validation_error",
                    "official_job_url": "",
                    "official_source_type": "none",
                    "validation_method": "exception",
                    "validation_notes": f"{type(exc).__name__}: {str(exc)[:300]}",
                    "validated_at": run_date,
                    "validation_prompt_tokens": 0,
                    "validation_completion_tokens": 0,
                    "validation_cost_usd": 0.0,
                })
    records.sort(key=lambda row: (row["company_name"].lower(), row["job_title"].lower()))
    counts: dict[str, int] = {}
    for row in records:
        counts[row["validation_status"]] = counts.get(row["validation_status"], 0) + 1
    summary = {
        "schema_version": "1.0",
        "generated_at": run_date,
        "roles_attempted": len(records),
        "status_counts": counts,
        "official_open_roles": counts.get("official_open", 0),
        "direct_official_or_ats": sum(row["validation_method"] == "direct_official_or_ats_url" for row in records),
        "luna_searches": sum(row["validation_method"] == "luna_official_search" for row in records),
        "estimated_cost_usd": round(sum(row["validation_cost_usd"] for row in records), 6),
    }
    files = {
        "evidence": output_dir / "official_validation_evidence.json",
        "summary": output_dir / "run_summary.json",
    }
    files["evidence"].write_text(json.dumps({
        "schema_version": "1.0", "generated_at": run_date, "records": records,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    files["summary"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary, files
