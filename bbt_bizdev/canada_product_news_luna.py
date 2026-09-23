from __future__ import annotations

import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .canada_hiring import FetchResult, fetch_url
from .config import USER_AGENT
from .text import clean_text


MODEL = "openai/gpt-5.6-luna"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PROMPT_VERSION = "canada_product_news_luna_v1"
EVENT_TYPES = {
    "funding", "product launch", "partnership", "acquisition",
    "regulatory approval", "regulatory submission", "clinical study",
    "manufacturing", "validation", "patent", "prototype",
    "pipeline prioritization", "expansion", "deployment",
}
PRIMARY_SOURCE_TYPES = {
    "company", "regulator", "clinical_registry", "government", "investor",
    "newswire", "professional_society",
}
EVENT_TERMS = {
    "funding": ("funding", "financing", "raises", "investment", "grant", "series "),
    "product launch": ("launch", "unveil", "introduc", "commercially available"),
    "partnership": ("partnership", "collaboration", "agreement", "partner"),
    "acquisition": ("acquisition", "acquire", "merger", "purchased"),
    "regulatory approval": ("approval", "clearance", "cleared", "authorized", "licence", "510(k)", "ce mark"),
    "regulatory submission": ("submission", "submitted", "filing", "application"),
    "clinical study": ("clinical trial", "clinical study", "first patient", "phase 1", "phase 2", "phase 3"),
    "manufacturing": ("manufacturing", "production", "facility", "scale-up"),
    "validation": ("validation", "validated", "performance study"),
    "patent": ("patent",), "prototype": ("prototype",),
    "pipeline prioritization": ("pipeline", "priorit"),
    "expansion": ("expansion", "expand"), "deployment": ("deployment", "deployed"),
}
REJECTION_REASONS = {
    "identity_mismatch", "passing_mention", "duplicate_or_syndication",
    "historical_or_retrospective", "immaterial", "speculation",
    "no_primary_source", "invalid_date", "other",
}
DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "candidate_decisions": {
            "type": "array", "maxItems": 20,
            "items": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string"},
                    "decision": {"enum": ["verified", "rejected", "needs_review"]},
                    "rejection_reason": {"enum": sorted(REJECTION_REASONS | {"none"})},
                    "identity_confidence": {"enum": ["high", "medium", "low"]},
                    "event_type": {"enum": sorted(EVENT_TYPES)},
                    "event_date": {"type": "string"},
                    "canonical_title": {"type": "string"},
                    "summary": {"type": "string"},
                    "product_or_program": {"type": "string"},
                    "primary_url": {"type": "string"},
                    "primary_source_type": {"enum": sorted(PRIMARY_SOURCE_TYPES | {"other"})},
                    "materiality": {"enum": ["high", "medium", "low"]},
                    "confidence": {"enum": ["high", "medium", "low"]},
                    "rationale": {"type": "string"},
                },
                "required": [
                    "candidate_id", "decision", "rejection_reason", "identity_confidence",
                    "event_type", "event_date", "canonical_title", "summary",
                    "product_or_program", "primary_url", "primary_source_type",
                    "materiality", "confidence", "rationale",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["candidate_decisions"],
    "additionalProperties": False,
}


def candidate_id(row: dict[str, Any]) -> str:
    raw = "|".join(str(row.get(key) or "") for key in (
        "company_id", "event_date", "event_type", "title", "discovery_url",
    ))
    return "news-candidate-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def prepare_candidates(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    prepared, rejected = [], []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        enriched = {**row, "candidate_id": candidate_id(row)}
        if row.get("freshness") != "recent_24_months":
            rejected.append({**enriched, "verification_status": "rejected_historical"})
            continue
        key = (str(row.get("company_id")), str(row.get("discovery_url")))
        if key in seen:
            rejected.append({**enriched, "verification_status": "rejected_exact_duplicate"})
            continue
        seen.add(key)
        prepared.append(enriched)
    return prepared, rejected


def build_batches(rows: list[dict[str, Any]], batch_size: int = 20) -> list[list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["company_id"], []).append(row)
    batches = []
    for company_id in sorted(grouped):
        company_rows = sorted(grouped[company_id], key=lambda row: (
            row.get("event_date", ""), row.get("event_type", ""), row["candidate_id"],
        ), reverse=True)
        batches.extend(company_rows[index:index + batch_size] for index in range(0, len(company_rows), batch_size))
    return batches


def build_prompt(company: dict[str, Any], profile: dict[str, Any], batch: list[dict[str, Any]], as_of: str) -> str:
    context = {
        "as_of": as_of,
        "company": {
            "company_id": company["company_id"],
            "company_name": company.get("company_name", ""),
            "legal_name": company.get("legal_name", ""),
            "aliases": company.get("aliases", []),
            "website": company.get("website", ""),
            "province": company.get("province", ""),
            "product_category": company.get("product_category", ""),
            "product_summary": company.get("product_summary", "")[:1500],
            "verified_product_profile": (profile or {}).get("product_summary", "")[:1500],
        },
        "candidates": [{
            key: row.get(key, "") for key in (
                "candidate_id", "event_date", "event_type", "title", "publisher", "discovery_url",
            )
        } for row in batch],
    }
    return (
        "Verify these news-discovery candidates for the exact company. Search the web for a "
        "primary source for each plausible material event. Do not accept the Google News RSS URL, "
        "a Yahoo/TradingView mirror, a passing mention, similarly named company, ordinary use of a "
        "generic company word, retrospective article, speculation, market-price commentary, job ad, "
        "listicle, or duplicate syndication as a new event.\n\n"
        "A verified decision requires: exact entity identity; a material event in the allowed event "
        "taxonomy; an event date supported by the source; and a primary URL from the company, "
        "regulator, clinical registry, government, investor, issuing newswire, or professional society. "
        "Use needs_review when the event is plausible but any required element is uncertain. Return one "
        "decision for every candidate_id. Multiple candidates may describe the same event; give them the "
        "same canonical title, date, type, product/program and primary URL so they can be deduplicated. "
        "Use empty strings for unavailable text/URL/date fields, not invented values.\n\n"
        + json.dumps(context, ensure_ascii=False)
    )


def request_luna(company: dict[str, Any], profile: dict[str, Any], batch: list[dict[str, Any]], api_key: str, as_of: str, model: str = MODEL) -> tuple[dict | None, dict, str]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": build_prompt(company, profile, batch, as_of)}],
        "plugins": [{"id": "web", "engine": "exa", "max_results": 10}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "canada_product_news_verification", "strict": True, "schema": DECISION_SCHEMA,
        }},
        "reasoning": {"effort": "low", "exclude": True},
    }
    request = Request(OPENROUTER_URL, data=json.dumps(payload).encode("utf-8"), headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "User-Agent": USER_AGENT,
    })
    try:
        response = json.loads(urlopen(request, timeout=120).read().decode("utf-8", "ignore"))
        message = response["choices"][0]["message"]
        decision = json.loads(message.get("content") or "{}")
        usage = response.get("usage") or {}
        usage["citations"] = [
            item.get("url_citation", {}) for item in message.get("annotations") or []
            if isinstance(item, dict) and item.get("url_citation", {}).get("url")
        ]
        return decision, usage, ""
    except HTTPError as exc:
        return None, {}, f"OpenRouter HTTP {exc.code}: {exc.read().decode('utf-8', 'ignore')[:500]}"
    except (OSError, URLError, KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        return None, {}, f"OpenRouter request failed: {str(exc)[:500]}"


LunaFn = Callable[[dict, dict, list[dict], str, str, str], tuple[dict | None, dict, str]]
FetchFn = Callable[[str], FetchResult]


def _host(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


def _identity_supported(company: dict[str, Any], profile: dict[str, Any], body: str, primary_url: str) -> bool:
    official = _host(company.get("website", ""))
    source = _host(primary_url)
    if official and (source == official or source.endswith("." + official)):
        return True
    text = clean_text(body).casefold()
    names = [company.get("company_name", ""), company.get("legal_name", ""), *company.get("aliases", [])]
    strong_names = [name.casefold() for name in names if len(re.sub(r"[^a-z0-9]", "", name.casefold())) >= 6]
    if any(name and name in text for name in strong_names):
        return True
    # Generic one-word names need corroborating product language.
    product_text = " ".join((company.get("product_summary", ""), (profile or {}).get("product_summary", ""))).casefold()
    anchors = [word for word in re.findall(r"[a-z0-9]{6,}", product_text) if word not in {"company", "medical", "healthcare", "platform", "technology", "developing"}]
    name = company.get("company_name", "").casefold()
    return bool(name and re.search(rf"\b{re.escape(name)}\b", text) and sum(word in text for word in set(anchors[:20])) >= 2)


def validate_decision(company: dict[str, Any], profile: dict[str, Any], candidate: dict[str, Any], decision: dict[str, Any], as_of: str, fetcher: FetchFn = fetch_url) -> dict[str, Any]:
    base = {**candidate, "luna_decision": decision, "verification_status": "needs_review", "verification_notes": ""}
    if decision.get("decision") != "verified":
        status = "rejected" if decision.get("decision") == "rejected" else "needs_review"
        return {**base, "verification_status": status, "verification_notes": decision.get("rationale", "")}
    if decision.get("confidence") != "high" or decision.get("identity_confidence") != "high":
        return {**base, "verification_notes": "Luna verification did not reach high identity and event confidence"}
    if decision.get("event_type") not in EVENT_TYPES or decision.get("primary_source_type") not in PRIMARY_SOURCE_TYPES:
        return {**base, "verification_notes": "Unsupported event or primary-source type"}
    url = str(decision.get("primary_url") or "")
    if not url.startswith(("http://", "https://")) or "news.google." in _host(url):
        return {**base, "verification_notes": "Missing or invalid primary URL"}
    if urlsplit(url).path.rstrip("/") == "":
        return {**base, "verification_notes": "Primary URL is only a site homepage, not event-specific evidence"}
    try:
        event_date = date.fromisoformat(str(decision.get("event_date") or "")[:10])
        cutoff = date.fromisoformat(as_of)
    except ValueError:
        return {**base, "verification_notes": "Invalid event date"}
    if event_date > cutoff or event_date < cutoff - timedelta(days=731):
        return {**base, "verification_notes": "Event date is future-dated or outside the recent window"}
    result = fetcher(url)
    if result.error or result.status >= 400 or not result.body:
        return {**base, "verification_notes": f"Primary URL fetch failed: {result.error or result.status}"}
    if not _identity_supported(company, profile, result.body, result.url or url):
        return {**base, "verification_notes": "Fetched primary source did not pass deterministic entity identity checks"}
    body_text = clean_text(result.body).casefold()
    if not any(term in body_text for term in EVENT_TERMS.get(decision["event_type"], ())):
        return {**base, "verification_notes": "Fetched source did not contain language supporting the proposed event type"}
    evidence_id = "news-event-" + hashlib.sha256("|".join((
        company["company_id"], decision["event_type"], event_date.isoformat(),
        str(decision.get("product_or_program") or ""), url,
    )).encode("utf-8")).hexdigest()[:20]
    return {
        **base, "verification_status": "accepted", "verification_notes": "High-confidence Luna decision passed local primary-source, date and identity validation.",
        "accepted_event": {
            "evidence_id": evidence_id, "company_id": company["company_id"],
            "company_name": company.get("company_name", ""), "event_type": decision["event_type"],
            "event_date": event_date.isoformat(), "title": decision.get("canonical_title", ""),
            "summary": decision.get("summary", ""), "product_or_program": decision.get("product_or_program", ""),
            "evidence_url": url, "source_type": decision["primary_source_type"],
            "confidence": "high", "captured_at": as_of, "candidate_ids": [candidate["candidate_id"]],
            "extraction_method": PROMPT_VERSION + "+deterministic_primary_validation",
        },
    }


def deduplicate_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for event in events:
        product = re.sub(r"[^a-z0-9]+", "", str(event.get("product_or_program") or event.get("title") or "").casefold())[:80]
        key = (event["company_id"], event["event_type"], event["event_date"], product)
        if key in chosen:
            chosen[key]["candidate_ids"] = sorted(set(chosen[key]["candidate_ids"] + event.get("candidate_ids", [])))
        else:
            chosen[key] = event
    return sorted(chosen.values(), key=lambda row: (row["company_id"], row["event_date"], row["event_type"], row["evidence_id"]))


def _usage_cost(usage: dict[str, Any]) -> float:
    if usage.get("cost") is not None:
        return float(usage.get("cost") or 0)
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    return (prompt * 1.0 + completion * 6.0) / 1_000_000


def run_verification(candidates_path: Path, companies_path: Path, profiles_path: Path, output_dir: Path, as_of: str, *, workers: int = 3, max_companies: int | None = None, dry_run: bool = False, progress_every: int = 10, model: str = MODEL, luna_fn: LunaFn = request_luna, fetcher: FetchFn = fetch_url) -> dict[str, Any]:
    candidates = json.loads(candidates_path.read_text(encoding="utf-8-sig")).get("candidates", [])
    companies = json.loads(companies_path.read_text(encoding="utf-8-sig")).get("companies", [])
    profiles = json.loads(profiles_path.read_text(encoding="utf-8-sig")).get("profiles", [])
    company_by_id = {row["company_id"]: row for row in companies}
    profile_by_id = {row["company_id"]: row for row in profiles}
    prepared, deterministic_rejections = prepare_candidates(candidates)
    if max_companies is not None:
        allowed = set(sorted({row["company_id"] for row in prepared})[:max_companies])
        prepared = [row for row in prepared if row["company_id"] in allowed]
    batches = build_batches(prepared)
    manifest = [{"batch_id": f"batch-{index:04d}", "company_id": batch[0]["company_id"], "candidate_ids": [row["candidate_id"] for row in batch]} for index, batch in enumerate(batches, start=1)]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "batch_manifest.json").write_text(json.dumps({"schema_version": "1.0", "batches": manifest}, indent=2), encoding="utf-8")
    if dry_run:
        summary = {"as_of": as_of, "recent_candidates": len(prepared), "deterministic_rejections": len(deterministic_rejections), "companies": len({row['company_id'] for row in prepared}), "batches": len(batches), "dry_run": True}
        (output_dir / "verification_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required unless --dry-run is used")

    raw_results: list[tuple[list[dict[str, Any]], dict | None, dict, str]] = []
    batch_dir = output_dir / "batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    resumed_batches = 0
    recorded_cost = 0.0
    session_cost = 0.0
    prompt_tokens = 0
    completion_tokens = 0
    candidates_returned = 0
    error_batches = 0
    progress_path = output_dir / "progress.jsonl"

    def report_progress() -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "completed_batches": len(raw_results), "total_batches": len(batches),
            "completed_percent": round(100 * len(raw_results) / max(1, len(batches)), 1),
            "candidates_returned": candidates_returned, "error_batches": error_batches,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "session_cost_usd": round(session_cost, 6),
            "cumulative_recorded_cost_usd": round(recorded_cost, 6),
            "resumed_batches": resumed_batches,
        }
        with progress_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        print(json.dumps({"progress": payload}), flush=True)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {}
        for index, batch in enumerate(batches, start=1):
            batch_id = f"batch-{index:04d}"
            checkpoint = batch_dir / f"{batch_id}.json"
            if checkpoint.exists():
                saved = json.loads(checkpoint.read_text(encoding="utf-8-sig"))
                saved_decision = saved.get("decision")
                saved_usage = saved.get("usage", {})
                saved_error = saved.get("error", "")
                raw_results.append((batch, saved_decision, saved_usage, saved_error))
                resumed_batches += 1
                recorded_cost += _usage_cost(saved_usage)
                prompt_tokens += int(saved_usage.get("prompt_tokens") or 0)
                completion_tokens += int(saved_usage.get("completion_tokens") or 0)
                candidates_returned += len((saved_decision or {}).get("candidate_decisions", []))
                error_batches += bool(saved_error)
                continue
            company = company_by_id[batch[0]["company_id"]]
            future = pool.submit(luna_fn, company, profile_by_id.get(company["company_id"], {}), batch, api_key, as_of, model)
            futures[future] = (batch, batch_id)
        for future in as_completed(futures):
            batch, batch_id = futures[future]
            try:
                decision, usage, error = future.result()
            except Exception as exc:
                decision, usage, error = None, {}, f"Unexpected Luna error: {type(exc).__name__}: {exc}"
            checkpoint = batch_dir / f"{batch_id}.json"
            temporary = checkpoint.with_suffix(".tmp")
            temporary.write_text(json.dumps({
                "schema_version": "1.0", "batch_id": batch_id,
                "candidate_ids": [row["candidate_id"] for row in batch],
                "decision": decision, "usage": usage, "error": error,
            }, indent=2, ensure_ascii=False), encoding="utf-8")
            temporary.replace(checkpoint)
            raw_results.append((batch, decision, usage, error))
            cost = _usage_cost(usage)
            session_cost += cost
            recorded_cost += cost
            prompt_tokens += int(usage.get("prompt_tokens") or 0)
            completion_tokens += int(usage.get("completion_tokens") or 0)
            candidates_returned += len((decision or {}).get("candidate_decisions", []))
            error_batches += bool(error)
            if len(raw_results) % max(1, progress_every) == 0 or len(raw_results) == len(batches):
                report_progress()

    decisions_out = list(deterministic_rejections)
    accepted = []
    usage_totals = {"prompt_tokens": 0, "completion_tokens": 0, "estimated_cost_usd": 0.0}
    for batch, payload, usage, error in raw_results:
        usage_totals["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
        usage_totals["completion_tokens"] += int(usage.get("completion_tokens") or 0)
        usage_totals["estimated_cost_usd"] += _usage_cost(usage)
        returned = {row.get("candidate_id"): row for row in (payload or {}).get("candidate_decisions", [])}
        company = company_by_id[batch[0]["company_id"]]
        profile = profile_by_id.get(company["company_id"], {})
        for candidate in batch:
            decision = returned.get(candidate["candidate_id"])
            if error or not decision:
                decisions_out.append({**candidate, "verification_status": "llm_error", "verification_notes": error or "Luna omitted candidate_id"})
                continue
            validated = validate_decision(company, profile, candidate, decision, as_of, fetcher)
            decisions_out.append({key: value for key, value in validated.items() if key != "accepted_event"})
            if validated.get("accepted_event"):
                accepted.append(validated["accepted_event"])
    accepted = deduplicate_events(accepted)
    (output_dir / "candidate_decisions.json").write_text(json.dumps({"schema_version": "1.0", "generated_at": as_of, "decisions": decisions_out}, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "verified_events.json").write_text(json.dumps({"schema_version": "1.0", "generated_at": as_of, "events": accepted}, indent=2, ensure_ascii=False), encoding="utf-8")
    counts: dict[str, int] = {}
    for row in decisions_out:
        counts[row["verification_status"]] = counts.get(row["verification_status"], 0) + 1
    summary = {"as_of": as_of, "recent_candidates": len(prepared), "companies": len({row['company_id'] for row in prepared}), "batches": len(batches), "resumed_batches": resumed_batches, "accepted_events": len(accepted), "decision_counts": counts, **usage_totals, "dry_run": False}
    (output_dir / "verification_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
