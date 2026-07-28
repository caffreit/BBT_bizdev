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

from .canada_hiring import FetchResult, fetch_url
from .canada_websites import (
    candidate_allowed, candidate_score, canonical_root,
)
from .adapters.linkedin import PublicSearchHit
from .config import USER_AGENT


MODEL = "openai/gpt-5.6-luna"
PROMPT_VERSION = "canada_website_luna_v3"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"enum": ["verified", "inactive", "ambiguous", "not_found"]},
        "official_website": {"type": "string"},
        "confidence": {"enum": ["high", "medium", "low"]},
        "candidate_urls": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "identity_signals": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "conflicting_signals": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "rationale": {"type": "string"},
    },
    "required": [
        "decision", "official_website", "confidence", "candidate_urls",
        "identity_signals", "conflicting_signals", "rationale",
    ],
    "additionalProperties": False,
}


def build_prompt(company: dict, provenance: list[dict]) -> str:
    source_context = [
        {
            "source": row.get("source_name", ""),
            "source_company_name": row.get("source_company_name", ""),
            "description": row.get("description", "")[:1200],
            "evidence_url": row.get("evidence_url", ""),
        }
        for row in provenance[:5]
    ]
    context = {
        "company_id": company["company_id"],
        "company_name": company.get("company_name", ""),
        "aliases": company.get("aliases", []),
        "province": company.get("province", ""),
        "product_category": company.get("product_category", ""),
        "product_summary": company.get("product_summary", "")[:1800],
        "canada_relationship": company.get("canada_relationship", ""),
        "source_context": source_context,
    }
    return (
        "Find and identity-check the official public website for this Canadian company. "
        "Run multiple searches: the exact company name in quotes; the name plus Canada/location; "
        "and the name plus product, founder, accelerator, or investor context. "
        "Do not select LinkedIn, Crunchbase, a university, accelerator, investor, directory, "
        "news article, app store, or social profile. Do not select a similarly named foreign "
        "company. Foreign headquarters alone does not disqualify an exact entity match when "
        "the company name, product, and supplied program context align; record that location "
        "difference as a conflicting signal. A redirect to an acquirer is ambiguous unless the target clearly preserves "
        "the named company as an active business. Return verified only when the official domain "
        "is strongly supported by company name plus product/location or a trusted source. "
        "Return inactive when reliable evidence shows the company was dissolved, acquired, merged, "
        "or shut down and no longer has a standalone active business. Otherwise return ambiguous "
        "or not_found. Use an empty official_website unless the decision is verified.\n\n"
        + json.dumps(context, ensure_ascii=False)
    )


def request_luna(
    company: dict, provenance: list[dict], api_key: str,
    model: str = MODEL,
) -> tuple[dict | None, dict, str]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": build_prompt(company, provenance)}],
        "plugins": [{"id": "web", "engine": "exa", "max_results": 8}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "official_company_website",
                "strict": True,
                "schema": DECISION_SCHEMA,
            },
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
        annotations = message.get("annotations") or []
        citations = []
        for item in annotations:
            citation = item.get("url_citation", {}) if isinstance(item, dict) else {}
            if citation.get("url"):
                citations.append({
                    "url": citation["url"],
                    "title": citation.get("title", ""),
                    "content": citation.get("content", "")[:1200],
                })
        usage = response.get("usage") or {}
        usage["citations"] = citations
        return decision, usage, ""
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:500]
        return None, {}, f"OpenRouter HTTP {exc.code}: {detail or exc.reason}"
    except (OSError, URLError, KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        return None, {}, f"OpenRouter request failed: {str(exc)[:500]}"


LunaFn = Callable[[dict, list[dict], str, str], tuple[dict | None, dict, str]]
FetchFn = Callable[[str], FetchResult]


def validate_luna_decision(
    company: dict, decision: dict | None, usage: dict, error: str,
    run_date: str, fetcher: FetchFn = fetch_url,
) -> dict:
    base = {
        "company_id": company["company_id"],
        "company_name": company.get("company_name", ""),
        "status": "not_found", "website": "", "domain": "",
        "confidence": "low", "captured_at": run_date, "model": MODEL,
        "decision": decision or {}, "citations": usage.get("citations", []),
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "estimated_cost_usd": float(usage.get("cost") or 0),
        "notes": error,
    }
    if error or not decision:
        return {**base, "status": "llm_error"}
    if decision.get("decision") == "inactive":
        return {
            **base, "status": "inactive",
            "confidence": decision.get("confidence", "low"),
            "notes": decision.get("rationale", ""),
        }
    if decision.get("decision") != "verified" or decision.get("confidence") != "high":
        return {
            **base,
            "status": "manual_review" if decision.get("decision") == "ambiguous" else "not_found",
            "confidence": decision.get("confidence", "low"),
            "notes": decision.get("rationale", ""),
        }
    website = canonical_root(decision.get("official_website", ""))
    if not website or not candidate_allowed(website):
        return {**base, "status": "manual_review", "notes": "Luna returned an excluded or invalid domain"}
    result = fetcher(website)
    website_host = urlsplit(website).netloc.removeprefix("www.")
    official_citations = [
        citation for citation in usage.get("citations", [])
        if (
            urlsplit(citation.get("url", "")).netloc.removeprefix("www.") == website_host
            or urlsplit(citation.get("url", "")).netloc.removeprefix("www.").endswith("." + website_host)
        )
    ]
    if result.error or result.status >= 400 or not result.body:
        if official_citations:
            return {
                **base, "status": "resolved", "website": website,
                "domain": website_host, "confidence": "high",
                "notes": (
                    "Luna high-confidence identity decision corroborated by indexed official-domain "
                    f"search evidence ({len(official_citations)} citation(s)); live fetch blocked: "
                    f"{result.error or result.status}"
                ),
            }
        return {
            **base, "status": "manual_review", "website": website,
            "domain": website_host,
            "notes": f"Luna selected a domain but live verification failed: {result.error or result.status}",
        }
    score = candidate_score(
        company,
        PublicSearchHit(company.get("company_name", ""), website, ""),
        result.body,
    )
    if score < 8:
        if official_citations and score >= 4:
            return {
                **base, "status": "resolved", "website": website,
                "domain": website_host, "confidence": "high",
                "notes": (
                    "Luna high-confidence identity decision corroborated by indexed official-domain "
                    f"search evidence and partial live-page identity match ({score})"
                ),
            }
        return {
            **base, "status": "manual_review", "website": website,
            "domain": website.removeprefix("https://"),
            "confidence": "medium",
            "notes": f"Luna high-confidence selection failed local homepage identity threshold ({score})",
        }
    return {
        **base, "status": "resolved", "website": website,
        "domain": website_host, "confidence": "high",
        "notes": f"Luna high-confidence identity decision plus live homepage verification ({score})",
    }


def run_luna_resolution(
    input_path: Path, provenance_path: Path, output_dir: Path,
    run_date: str | None = None, source_filter: str = "",
    limit: int | None = None, max_workers: int = 4,
    model: str = MODEL, luna_fn: LunaFn = request_luna,
    fetcher: FetchFn = fetch_url,
) -> tuple[dict, dict[str, Path]]:
    run_date = run_date or date.today().isoformat()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip() or os.getenv("BBT_OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY or BBT_OPENROUTER_API_KEY is required")
    payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
    provenance_payload = json.loads(provenance_path.read_text(encoding="utf-8-sig"))
    provenance_by_id: dict[str, list[dict]] = {}
    eligible_ids: set[str] = set()
    for row in provenance_payload.get("records", []):
        provenance_by_id.setdefault(row["company_id"], []).append(row)
        if not source_filter or source_filter.lower() in row.get("source_name", "").lower():
            eligible_ids.add(row["company_id"])
    targets = [
        row for row in payload.get("companies", [])
        if not row.get("website") and row["company_id"] in eligible_ids
    ]
    if limit is not None:
        targets = targets[:limit]
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / "cache"
    cache_dir.mkdir(exist_ok=True)

    def research(company: dict) -> dict:
        cache_key = hashlib.sha1(f"{PROMPT_VERSION}|{model}|{company['company_id']}".encode()).hexdigest()[:20]
        cache_path = cache_dir / f"{cache_key}.json"
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return validate_luna_decision(
                company, cached.get("decision"), cached.get("usage", {}),
                cached.get("error", ""), run_date, fetcher,
            )
        decision, usage, error = luna_fn(
            company, provenance_by_id.get(company["company_id"], []), api_key, model
        )
        cache_path.write_text(json.dumps({
            "company_id": company["company_id"], "decision": decision,
            "usage": usage, "error": error,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        return validate_luna_decision(company, decision, usage, error, run_date, fetcher)

    records = []
    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        futures = {pool.submit(research, row): row for row in targets}
        for future in as_completed(futures):
            records.append(future.result())
    records.sort(key=lambda row: (row["company_name"].lower(), row["company_id"]))

    existing_domains = {row.get("domain") for row in payload.get("companies", []) if row.get("domain")}
    by_id = {}
    for row in records:
        if row["status"] == "resolved" and row["domain"] in existing_domains:
            row["status"] = "manual_review"
            row["notes"] = "Luna-resolved domain already belongs to another canonical identity"
        elif row["status"] == "resolved":
            by_id[row["company_id"]] = row
    grouped: dict[str, list[dict]] = {}
    for row in records:
        if row["status"] == "resolved":
            grouped.setdefault(row["domain"], []).append(row)
    for domain, rows in grouped.items():
        if len(rows) > 1:
            for row in rows:
                row["status"] = "manual_review"
                row["notes"] = f"Luna-resolved domain is shared by {len(rows)} identities"
                by_id.pop(row["company_id"], None)

    companies = []
    for company in payload.get("companies", []):
        copied = json.loads(json.dumps(company))
        resolved = by_id.get(company["company_id"])
        if resolved:
            copied["website"] = resolved["website"]
            copied["domain"] = resolved["domain"]
            copied.setdefault("identity_keys", []).append(f"domain:{resolved['domain']}")
        companies.append(copied)
    counts: dict[str, int] = {}
    for row in records:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    summary = {
        "schema_version": "1.0", "generated_at": run_date, "model": model,
        "source_filter": source_filter, "companies_attempted": len(records),
        "status_counts": counts, "websites_resolved": counts.get("resolved", 0),
        "prompt_tokens": sum(row["prompt_tokens"] for row in records),
        "completion_tokens": sum(row["completion_tokens"] for row in records),
        "estimated_cost_usd": round(sum(row["estimated_cost_usd"] for row in records), 6),
        "missing_websites_after": sum(not row.get("website") for row in companies),
    }
    files = {
        "companies": output_dir / "canonical_companies_luna_websites_enriched.json",
        "evidence": output_dir / "luna_website_resolution_evidence.json",
        "summary": output_dir / "run_summary.json",
    }
    files["companies"].write_text(json.dumps({"schema_version": "1.0", "generated_at": run_date, "companies": companies}, indent=2, ensure_ascii=False), encoding="utf-8")
    files["evidence"].write_text(json.dumps({"schema_version": "1.0", "generated_at": run_date, "records": records}, indent=2, ensure_ascii=False), encoding="utf-8")
    files["summary"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary, files
