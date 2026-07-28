from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from .adapters.linkedin import PublicSearchHit, configured_search
from .canada_hiring import FetchResult, fetch_url


EXCLUDED_HOSTS = {
    "app.marsdd.com", "marsdd.com", "linkedin.com", "www.linkedin.com",
    "crunchbase.com", "www.crunchbase.com", "facebook.com", "www.facebook.com",
    "instagram.com", "www.instagram.com", "x.com", "twitter.com", "youtube.com",
    "pitchbook.com", "www.pitchbook.com", "bloomberg.com", "www.bloomberg.com",
    "ucalgary.ca", "utoronto.ca", "ubc.ca", "ualberta.ca", "mcgill.ca",
}
EXCLUDED_SUFFIXES = (
    ".gc.ca", ".canada.ca", ".wikipedia.org", ".newswire.ca",
)
GENERIC_WORDS = {
    "inc", "corp", "corporation", "company", "co", "ltd", "limited", "technologies",
    "technology", "therapeutics", "health", "medical", "bio", "biosciences", "labs",
}


SearchFn = Callable[[str], tuple[list[PublicSearchHit], str | None]]
FetchFn = Callable[[str], FetchResult]


def identity_words(value: str) -> list[str]:
    return [
        word for word in re.findall(r"[a-z0-9]+", (value or "").lower())
        if len(word) > 1 and word not in GENERIC_WORDS
    ]


def canonical_root(url: str) -> str:
    parts = urlsplit(url if url.startswith(("http://", "https://")) else "https://" + url)
    host = parts.netloc.lower().split(":", 1)[0].removeprefix("www.")
    if not host:
        return ""
    return urlunsplit(("https", host, "", "", ""))


def candidate_allowed(url: str) -> bool:
    host = urlsplit(canonical_root(url)).netloc
    if not host or host in EXCLUDED_HOSTS:
        return False
    return not any(host.endswith(suffix) for suffix in EXCLUDED_SUFFIXES)


def candidate_score(company: dict, hit: PublicSearchHit, fetched_text: str = "") -> int:
    name_words = identity_words(company.get("company_name", ""))
    if not name_words:
        return 0
    title_words = set(identity_words(hit.title))
    snippet_words = set(identity_words(hit.snippet))
    page_words = set(identity_words(fetched_text[:10000]))
    domain = urlsplit(canonical_root(hit.url)).netloc.split(".")[0]
    name_key = "".join(name_words)
    score = 0
    if all(word in title_words for word in name_words):
        score += 4
    if all(word in snippet_words for word in name_words):
        score += 2
    if fetched_text and all(word in page_words for word in name_words):
        score += 4
    similarity = SequenceMatcher(None, name_key, re.sub(r"[^a-z0-9]", "", domain)).ratio()
    if similarity >= 0.8:
        score += 4
    elif similarity >= 0.6:
        score += 2
    location_text = f"{hit.title} {hit.snippet} {fetched_text[:3000]}".lower()
    if "canada" in location_text or company.get("province", "").lower() in location_text:
        score += 1
    return score


def website_query(company: dict) -> str:
    name = company.get("company_name", "")
    category = company.get("product_category", "")
    province = company.get("province", "")
    return f'"{name}" {category} {province} Canada official website'.strip()


def probable_domains(company_name: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", company_name.lower())
    while words and words[-1] in {"inc", "ltd", "limited", "corp", "corporation", "ulc"}:
        words.pop()
    if not words:
        return []
    labels = ["".join(words)]
    if len(words) > 1:
        labels.append("-".join(words))
    seen: set[str] = set()
    return [
        f"https://{label}.{tld}"
        for label in labels for tld in ("com", "ca", "io", "ai", "health")
        if not (f"{label}.{tld}" in seen or seen.add(f"{label}.{tld}"))
    ]


def resolve_by_domain_probe(
    company: dict, run_date: str, fetcher: FetchFn = fetch_url,
) -> dict:
    base = {
        "company_id": company["company_id"], "company_name": company.get("company_name", ""),
        "query": "direct_domain_probe", "website": "", "domain": "", "status": "not_found",
        "confidence": "low", "evidence_url": "", "captured_at": run_date, "notes": "",
    }
    name_words = identity_words(company.get("company_name", ""))
    for candidate in probable_domains(company.get("company_name", "")):
        fetched = fetcher(candidate)
        if fetched.error or fetched.status >= 400 or not fetched.body:
            continue
        root = canonical_root(fetched.url or candidate)
        if not candidate_allowed(root):
            continue
        hit = PublicSearchHit(company.get("company_name", ""), root, "")
        score = candidate_score(company, hit, fetched.body)
        if score < 8:
            continue
        page_lower = fetched.body[:15000].lower()
        context_terms = [
            company.get("province", "").lower(), "canada",
            *identity_words(company.get("product_category", "")),
        ]
        context_match = any(term and term not in {"unknown"} and term in page_lower for term in context_terms)
        if len(name_words) == 1 and not context_match:
            return {
                **base, "status": "manual_review", "website": root,
                "domain": urlsplit(root).netloc, "confidence": "medium",
                "evidence_url": fetched.url or candidate,
                "notes": "Plausible direct domain for a generic company name; contextual confirmation required",
            }
        return {
            **base, "status": "resolved", "website": root,
            "domain": urlsplit(root).netloc, "confidence": "high",
            "evidence_url": fetched.url or candidate,
            "notes": f"Official identity verified on plausible direct domain; identity score {score}",
        }
    return {**base, "notes": "No plausible direct domain passed live identity verification"}


def resolve_company_website(
    company: dict, run_date: str, search_fn: SearchFn = configured_search,
    fetcher: FetchFn = fetch_url,
) -> dict:
    base = {
        "company_id": company["company_id"], "company_name": company.get("company_name", ""),
        "query": website_query(company), "website": "", "domain": "", "status": "not_found",
        "confidence": "low", "evidence_url": "", "captured_at": run_date, "notes": "",
    }
    hits, error = search_fn(base["query"])
    if error and not hits:
        return {**base, "status": "search_error", "notes": error}
    candidates = []
    for hit in hits[:10]:
        root = canonical_root(hit.url)
        if not candidate_allowed(root):
            continue
        fetched = fetcher(root)
        page_text = fetched.body if not fetched.error and fetched.status < 400 else ""
        score = candidate_score(company, hit, page_text)
        candidates.append((score, root, hit, fetched))
    candidates.sort(key=lambda row: (-row[0], row[1]))
    if not candidates or candidates[0][0] < 6:
        return {**base, "notes": "No candidate met the official-domain identity threshold"}
    best = candidates[0]
    tied = [row for row in candidates[1:] if row[0] >= best[0] - 1 and row[1] != best[1]]
    if tied:
        return {
            **base, "status": "manual_review", "website": best[1],
            "domain": urlsplit(best[1]).netloc, "confidence": "medium",
            "evidence_url": best[2].url,
            "notes": "Multiple plausible official domains: " + ", ".join([best[1], *[row[1] for row in tied[:3]]]),
        }
    return {
        **base, "status": "resolved", "website": best[1],
        "domain": urlsplit(best[1]).netloc,
        "confidence": "high" if best[0] >= 9 else "medium",
        "evidence_url": best[2].url,
        "notes": f"Identity score {best[0]}; search title: {best[2].title}",
    }


def run_website_resolution(
    input_path: Path, output_dir: Path, run_date: str | None = None,
    limit: int | None = None, search_fn: SearchFn = configured_search,
    fetcher: FetchFn = fetch_url, probe_only: bool = False, workers: int = 12,
) -> tuple[dict, dict[str, Path]]:
    run_date = run_date or date.today().isoformat()
    payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
    targets = [row for row in payload.get("companies", []) if not row.get("website")]
    if limit is not None:
        targets = targets[:limit]
    if probe_only:
        records = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {
                pool.submit(resolve_by_domain_probe, row, run_date, fetcher): row
                for row in targets
            }
            for future in as_completed(futures):
                records.append(future.result())
        records.sort(key=lambda row: (row["company_name"].lower(), row["company_id"]))
    else:
        records = [resolve_company_website(row, run_date, search_fn, fetcher) for row in targets]
    by_id = {row["company_id"]: row for row in records if row["status"] == "resolved"}
    existing_domains = {
        row.get("domain") for row in payload.get("companies", [])
        if row.get("domain")
    }
    for row in records:
        if row["status"] == "resolved" and row["domain"] in existing_domains:
            row["status"] = "manual_review"
            row["notes"] = "Resolved domain already belongs to another canonical identity"
            by_id.pop(row["company_id"], None)
    resolved_domains: dict[str, list[str]] = {}
    for row in records:
        if row["status"] == "resolved":
            resolved_domains.setdefault(row["domain"], []).append(row["company_id"])
    for domain, company_ids in resolved_domains.items():
        if len(company_ids) > 1:
            for row in records:
                if row["company_id"] in company_ids:
                    row["status"] = "manual_review"
                    row["notes"] = f"Resolved domain is shared by {len(company_ids)} unresolved identities"
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
        "schema_version": "1.0", "generated_at": run_date,
        "missing_websites_before": sum(not row.get("website") for row in payload.get("companies", [])),
        "companies_attempted": len(records), "status_counts": counts,
        "websites_resolved": counts.get("resolved", 0),
        "missing_websites_after": sum(not row.get("website") for row in companies),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "companies": output_dir / "canonical_companies_websites_enriched.json",
        "evidence": output_dir / "website_resolution_evidence.json",
        "summary": output_dir / "run_summary.json",
    }
    files["companies"].write_text(json.dumps({"schema_version": "1.0", "generated_at": run_date, "companies": companies}, indent=2, ensure_ascii=False), encoding="utf-8")
    files["evidence"].write_text(json.dumps({"schema_version": "1.0", "generated_at": run_date, "records": records}, indent=2, ensure_ascii=False), encoding="utf-8")
    files["summary"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary, files
