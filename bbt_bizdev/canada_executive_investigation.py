"""Bounded, replayable executive research. The model proposes work; Python owns evidence."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from bbt_bizdev.adapters.linkedin import canonicalize_linkedin_url, configured_search
from bbt_bizdev.canada_executive_luna import (
    _profile_in_cited_excerpt, _role_in_cited_excerpt, load_api_key,
    same_host, valid_web_url,
)
from bbt_bizdev.canada_website_llm import MODEL, OPENROUTER_URL

VERSION = "executive_investigation_v5"
PILOT_ROWS = (17, 35, 1202, 15, 47, 12, 602, 1502)
BLIND_REPLAY_ROWS = (5, 17, 1202, 35, 15, 12, 1502, 602)
BLIND_HIDDEN_NAMES = ((5, "Dwayne Sansone"), (17, "Manmeet Maggu"),
                      (1202, "Dolma Tsundu"))
RESERVE_USD = 0.05
MAX_COMPANY_REQUESTS = 5
ACTION_KINDS = (
    "search_person_role", "inspect_official", "search_linkedin_post",
    "check_announcement", "check_conflict",
)
CLAIM_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "name": {"type": "string"}, "title": {"type": "string"},
        "linkedin_url": {"type": "string"}, "role_url": {"type": "string"},
        "linkedin_evidence_url": {"type": "string"},
        "verdict": {"enum": ["supported", "uncertain", "wrong-company"]},
        "role_date": {"type": "string"}, "profile_date": {"type": "string"},
        "conflicts": {"type": "array", "items": {"type": "string"}},
        "source_urls": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["name", "title", "linkedin_url", "role_url", "linkedin_evidence_url",
                 "verdict", "role_date", "profile_date", "conflicts", "source_urls"],
}
RESPONSE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "official_website": {"type": "string"},
        "company_verdict": {"enum": ["supported", "uncertain", "wrong-company"]},
        "company_status": {"enum": ["active", "inactive", "acquired", "uncertain"]},
        "actions": {"type": "array", "maxItems": 4, "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"kind": {"enum": list(ACTION_KINDS)}, "query": {"type": "string"},
                           "url": {"type": "string"}, "person": {"type": "string"}},
            "required": ["kind", "query", "url", "person"],
        }},
        "claims": {"type": "array", "maxItems": 5, "items": CLAIM_SCHEMA},
    },
    "required": ["official_website", "company_verdict", "company_status", "actions", "claims"],
}


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value[:10]) else None
    except ValueError:
        return None


def _recent(value: str, today: date) -> bool:
    published = _date(value)
    return bool(published and today - timedelta(days=365) <= published <= today)


def _extract_date(raw: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for key in ("article:published_time", "datePublished", "pubdate", "date"):
        tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if tag and _date(str(tag.get("content", ""))):
            return str(tag["content"])[:10]
    for tag in soup.find_all("time", limit=3):
        value = str(tag.get("datetime", ""))
        if _date(value):
            return value[:10]
    return ""


def _indexed_date(text: str) -> str:
    for match in re.finditer(r"\b(?:20\d{2})-\d{2}-\d{2}\b", text[:500]):
        if _date(match.group()):
            return match.group()
    patterns = (r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2},? 20\d{2}\b",
                r"\b\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* 20\d{2}\b")
    for pattern in patterns:
        for match in re.finditer(pattern, text[:500], re.I):
            value = match.group().replace(".", "")
            for fmt in ("%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y",
                        "%d %b %Y", "%d %B %Y"):
                try:
                    return datetime.strptime(value, fmt).date().isoformat()
                except ValueError:
                    pass
    return ""


def _source_id(kind: str, url: str, excerpt: str) -> str:
    return "ev-" + _digest(f"{kind}|{url}|{excerpt}")[:20]


def _source(kind: str, url: str, title: str, excerpt: str, *, query: str = "",
            fetched: bool = False, final_url: str = "", published_at: str = "",
            error: str = "", raw_hash: str = "") -> dict:
    return {"evidence_id": _source_id(kind, url, excerpt), "kind": kind, "url": url,
            "title": title[:300], "excerpt": excerpt[:5000], "query": query,
            "fetched": fetched, "final_url": final_url, "published_at": published_at,
            "error": error, "content_sha256": raw_hash or _digest(excerpt), "observed_at": _now()}


class Budget:
    def __init__(self, *, max_cost_usd: float, max_requests: int, max_searches: int,
                 max_fetches: int):
        self.max_cost_usd = max_cost_usd
        self.max_requests = max_requests
        self.max_searches = max_searches
        self.max_fetches = max_fetches
        self.requests = 0
        self.searches = 0
        self.fetches = 0
        self.cost_usd = 0.0
        self.missing_usage = False
        self.stopped_reason = ""

    def can_request(self) -> bool:
        if self.missing_usage:
            self.stopped_reason = "missing_cost_data"
        elif self.requests >= self.max_requests:
            self.stopped_reason = "request_limit"
        elif self.cost_usd + RESERVE_USD > self.max_cost_usd:
            self.stopped_reason = "cost_reserve"
        return not self.stopped_reason

    def record_request(self, usage: dict) -> None:
        self.requests += 1
        if not isinstance(usage, dict) or usage.get("cost") is None:
            self.missing_usage = True
            self.stopped_reason = "missing_cost_data"
            return
        self.cost_usd += float(usage["cost"])
        if self.cost_usd > self.max_cost_usd:
            self.stopped_reason = "cost_overshoot"


def _post_json(payload: dict, api_key: str) -> dict:
    request = Request(OPENROUTER_URL, data=json.dumps(payload).encode(), headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
        "User-Agent": "BBTResearch/1.0",
    })
    with urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _citations(message: dict, query: str) -> list[dict]:
    rows = []
    for item in message.get("annotations") or []:
        citation = item.get("url_citation", {}) if isinstance(item, dict) else {}
        url = citation.get("url", "")
        if valid_web_url(url):
            content = citation.get("content", "")
            rows.append(_source("indexed", url, citation.get("title", ""), content,
                                query=query, published_at=(str(citation.get("published_at", ""))[:10]
                                or _indexed_date(content))))
    return rows


def _model_turn(company: dict, prior: list[dict], sources: list[dict], steps: list[dict],
                leads: list[dict],
                api_key: str, budget: Budget, requester=_post_json) -> tuple[dict | None, dict]:
    if not budget.can_request():
        return None, {"error": budget.stopped_reason}
    context = {
        "as_of": date.today().isoformat(),
        "dated_evidence_cutoff": (date.today() - timedelta(days=365)).isoformat(),
        "company": {key: company.get(key, "") for key in
                    ("row_id", "company", "website", "source_website", "province", "product", "identity_issue")},
        "already_accepted": [{"name": r.get("name"), "title": r.get("title")}
                             for r in prior if r.get("decision") == "accept"],
        "unverified_leads": leads[:10],
        "sources": [{key: item.get(key, "") for key in
                     ("evidence_id", "kind", "url", "title", "excerpt", "published_at", "error")}
                    for item in sources[-30:]],
        "steps": steps[-12:],
        "limits": {"actions_this_turn": 4, "candidates": 5},
    }
    prompt = (
        "Investigate CURRENT executives of this exact company. Prioritize CEO, COO, CTO, CFO. "
        "Choose useful next actions; Python will execute them and show you the results. Use exact URLs "
        "from sources only. Check company identity, dated role evidence, exact personal LinkedIn "
        "identity, and conflicting current employment. A blocked page is not negative evidence. "
        "A personal profile alone does not establish a current role. Return claims only when enough "
        "observations exist; mark uncertainty and conflicts. Unverified leads are earlier model "
        "suggestions, not evidence; investigate missing priority executives among them. Each "
        "company has a five-request allowance. Return claims from existing sources immediately. "
        "Request at most one additional action if a decisive role source is missing. Python will "
        "search for an exact personal profile when you leave its URL blank, then run a conflict "
        "search for each new claim. Never guess email or phone. "
        "Use gate_feedback to choose a better source when a proposed role source fails. "
        "Dates must come from source metadata or excerpts.\n\n"
        + json.dumps(context, ensure_ascii=False)
    )
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
               "response_format": {"type": "json_schema", "json_schema": {
                   "name": "executive_investigation", "strict": True, "schema": RESPONSE_SCHEMA}},
               "reasoning": {"effort": "low", "exclude": True}, "max_tokens": 1300}
    attempted = recorded = False
    try:
        attempted = True
        result = requester(payload, api_key)
        usage = result.get("usage") or {}
        budget.record_request(usage)
        recorded = True
        content = result["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if not valid_response(parsed):
            raise ValueError("invalid investigation response schema")
        return parsed, {"request_sha256": _digest(json.dumps(payload, sort_keys=True)),
                        "request": payload, "response": parsed, "usage": usage, "at": _now()}
    except (OSError, KeyError, IndexError, TypeError, ValueError) as error:
        if attempted and not recorded:
            budget.record_request({})
        return None, {"error": f"{type(error).__name__}: {str(error)[:180]}", "at": _now()}


def valid_response(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != set(RESPONSE_SCHEMA["required"]):
        return False
    if not isinstance(value["official_website"], str):
        return False
    if value["company_verdict"] not in {"supported", "uncertain", "wrong-company"}:
        return False
    if value["company_status"] not in {"active", "inactive", "acquired", "uncertain"}:
        return False
    if not isinstance(value["actions"], list) or len(value["actions"]) > 4:
        return False
    for action in value["actions"]:
        if not isinstance(action, dict) or set(action) != {"kind", "query", "url", "person"}:
            return False
        if action["kind"] not in ACTION_KINDS or any(not isinstance(v, str) for v in action.values()):
            return False
    if not isinstance(value["claims"], list) or len(value["claims"]) > 5:
        return False
    for claim in value["claims"]:
        if not isinstance(claim, dict) or set(claim) != set(CLAIM_SCHEMA["required"]):
            return False
        if any(not isinstance(claim[key], str) for key in
               ("name", "title", "linkedin_url", "role_url", "linkedin_evidence_url",
                "verdict", "role_date", "profile_date")):
            return False
        if claim["verdict"] not in {"supported", "uncertain", "wrong-company"}:
            return False
        if not isinstance(claim["conflicts"], list) or not all(isinstance(x, str) for x in claim["conflicts"]):
            return False
        if not isinstance(claim["source_urls"], list) or not all(isinstance(x, str) for x in claim["source_urls"]):
            return False
    return True


def _server_search(query: str, api_key: str, budget: Budget, requester=_post_json) -> tuple[list[dict], str, dict]:
    if not budget.can_request():
        return [], budget.stopped_reason, {}
    payload = {"model": MODEL, "messages": [{"role": "user", "content":
               "Use web search for this exact query and provide source citations: " + query}],
               "tools": [{"type": "openrouter:web_search", "parameters": {
                   "engine": "exa", "max_results": 5, "max_total_results": 5}}],
               "max_tokens": 350, "reasoning": {"effort": "low", "exclude": True}}
    attempted = recorded = False
    try:
        attempted = True
        response = requester(payload, api_key)
        budget.record_request(response.get("usage") or {})
        recorded = True
        hits = _citations(response["choices"][0]["message"], query)
        return hits, "" if hits else "server_search_no_citations", {
            "usage": response.get("usage") or {},
            "request_sha256": _digest(json.dumps(payload, sort_keys=True)),
        }
    except (OSError, KeyError, IndexError, TypeError, ValueError) as error:
        if attempted and not recorded:
            budget.record_request({})
        return [], f"server_search_{type(error).__name__}: {str(error)[:120]}", {}


def search(query: str, cache_dir: Path, api_key: str, budget: Budget,
           searcher=configured_search, server_requester=_post_json) -> dict:
    key = _digest(f"{VERSION}|search|{query}")
    path = cache_dir / f"{key}.json"
    if path.exists():
        result = json.loads(path.read_text(encoding="utf-8"))
        result["cache_hit"] = True
        return result
    if budget.searches >= budget.max_searches:
        return {"query": query, "sources": [], "error": "search_limit", "cache_hit": False}
    budget.searches += 1
    hits, error = searcher(query)
    if hits:
        sources = [_source("indexed", h.url, h.title, h.snippet, query=query,
                           published_at=_indexed_date(h.snippet))
                   for h in hits[:5] if valid_web_url(h.url)]
        backend = "python_search"
        server_trace = {}
    else:
        sources, fallback_error, server_trace = _server_search(query, api_key, budget, server_requester)
        backend = "openrouter_server_search"
        error = fallback_error or error
    result = {"query": query, "backend": backend, "sources": sources,
              "error": "" if sources else (error or "no_results"), "at": _now(),
              "cache_hit": False, **server_trace}
    if sources:
        _save(path, result)
    return result


def fetch(url: str, cache_dir: Path, budget: Budget, fetcher=None) -> dict:
    from research_canada_executives import fetch_page
    key = _digest(f"{VERSION}|fetch|{url}")
    path = cache_dir / f"{key}.json"
    if path.exists():
        result = json.loads(path.read_text(encoding="utf-8"))
        result["cache_hit"] = True
        return result
    if budget.fetches >= budget.max_fetches:
        return {"url": url, "sources": [], "error": "fetch_limit", "cache_hit": False}
    budget.fetches += 1
    if not valid_web_url(url):
        return {"url": url, "sources": [], "error": "invalid_url", "cache_hit": False}
    page, error = (fetcher or fetch_page)(url)
    if error or not page:
        return {"url": url, "sources": [_source("fetch", url, "", "", error=error or "empty_page")],
                "error": error or "empty_page", "cache_hit": False}
    raw = page.raw[:1_000_000]
    soup = BeautifulSoup(raw, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    excerpt = soup.get_text(" ", strip=True)[:5000]
    source = _source("fetch", url, title, excerpt, fetched=True,
                     final_url=getattr(page, "final_url", url), published_at=_extract_date(raw),
                     raw_hash=_digest(raw))
    result = {"url": url, "sources": [source], "raw_html": raw, "error": "", "at": _now(),
              "cache_hit": False}
    _save(path, result)
    return result


def _alias_variant_key(name: str) -> str:
    from research_canada_executives import clean_words
    words = clean_words(name).split()
    # Only trailing legal/industry descriptors; arbitrary aliases remain unresolved.
    while words and words[-1] in {"inc", "incorporated", "ltd", "limited", "corp",
                                  "corporation", "medical", "devices"}:
        words.pop()
    return "".join(words)


def _domain_alias_review(company: dict) -> bool:
    reviews = company.get("identity_reviews", [])
    if not reviews or not company.get("source_website"):
        return False
    key = _alias_variant_key(company["company"])
    if len(key) < 5:
        return False
    for review in reviews:
        if review.get("issue_type") != "shared_domain_different_names":
            return False
        domains, names = review.get("domains", []), review.get("names", [])
        if len(domains) != 1 or len(names) < 2:
            return False
        domain_url = domains[0] if "://" in domains[0] else "https://" + domains[0]
        if not same_host(domain_url, company["source_website"]):
            return False
        if any(_alias_variant_key(name) != key for name in names):
            return False
    return True


def company_identity_evidence(company: dict, sources: list[dict]) -> dict:
    """Verify a supplied site or its observed redirect; retain the resolution chain."""
    from research_canada_executives import clean_words
    website = company.get("website", "")
    if company.get("identity_issue") and not _domain_alias_review(company):
        return {"verified": False, "reason": "unresolved_workbook_alias"}
    if not valid_web_url(website):
        return {"verified": False, "reason": "missing_website"}
    saw_fetch = False
    for item in sources:
        if not item.get("fetched") or item.get("error"):
            continue
        # Trust only a request to the working/workbook site, never an unrelated
        # model-supplied page that happens to mention the company.
        requested = item.get("url", "")
        if not same_host(requested, website) or urlsplit(requested).path.strip("/"):
            continue
        final = item.get("final_url", "")
        if not valid_web_url(final) or urlsplit(final).path.strip("/"):
            continue
        saw_fetch = True
        soup = BeautifulSoup(item.get("raw_html", ""), "html.parser")
        identity_text = " ".join(tag.get_text(" ", strip=True)
                                 for tag in soup.find_all(["title", "h1", "footer"]))
        name = clean_words(company["company"])
        if len(name) >= 5 and re.search(rf"\b{re.escape(name)}\b", clean_words(identity_text)):
            # Alias resolution also needs the observed request on the workbook domain.
            if company.get("identity_issue") and not same_host(requested, company["source_website"]):
                continue
            return {"verified": True, "reason": "verified_domain_name_variants" if company.get("identity_issue")
                    else "verified_homepage" if same_host(final, website) else "verified_homepage_redirect",
                    "website": final, "evidence_ids": [item["evidence_id"]],
                    "requested_url": requested, "final_url": final,
                    "alias_reviews": company.get("identity_reviews", [])}
    return {"verified": False, "reason": "homepage_name_mismatch" if saw_fetch else "homepage_not_retrieved"}


def _company_identity(company: dict, sources: list[dict]) -> bool:
    return company_identity_evidence(company, sources)["verified"]


def _current_role_mention(content: str, name: str, title: str) -> bool:
    from research_canada_executives import ROLE_PATTERNS, clean_words, role_rank
    rank = role_rank(title)
    if rank == 99:
        return False
    words, person = clean_words(content), clean_words(name)
    for match in re.finditer(rf"\b{re.escape(person)}\b", words):
        # A role immediately before the name, or a compound title such as
        # President & CEO immediately after it, is an explicit role association.
        before = words[max(0, match.start()-80):match.start()]
        after = words[match.end():match.end()+95]
        if re.search(r"(?:former|previous|ex)\s+(?:chief [a-z ]+ officer|ceo|coo|cto|cfo|president)\s*$", before):
            continue
        if re.search(r"^\s*(?:(?:is|was)\s+(?:a\s+)?)?(?:former|previous|ex)\b", after):
            continue
        if re.fullmatch(ROLE_PATTERNS[rank][1], before.strip(), re.I):
            return True
        role = re.search(ROLE_PATTERNS[rank][1], after, re.I)
        if role and set(after[:role.start()].split()) <= {
                "president", "founder", "co", "cofounder", "and", "is", "the", "a", "an",
                "our", "serves", "as", "current", "currently", "new", "appointed", "named",
                "md", "phd", "msc", "mba", "cpa", "ca", "frcsc", "frcpc", "cpe", "facc", "fhrs"}:
            return True
    return False


def _same_url(first: str, second: str) -> bool:
    return bool(first and second and first.rstrip("/") == second.rstrip("/"))


def _seed_existing_citations(row_id: str, source_dir: Path) -> list[dict]:
    """Reuse retained provider excerpts without treating old model claims as evidence."""
    seeded = []
    for folder in ("luna_cache", "luna_profile_cache"):
        for path in (source_dir / folder).glob("*.json"):
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if saved.get("row_id") != row_id:
                continue
            for citation in (saved.get("usage") or {}).get("citations") or []:
                if not isinstance(citation, dict):
                    continue
                url = citation.get("url", "")
                if not valid_web_url(url):
                    continue
                content = citation.get("content", "")
                source = _source("indexed", url, citation.get("title", ""), content,
                                 query="retained_luna_citation",
                                 published_at=_indexed_date(content))
                source["observed_at"] = saved.get("requested_at", "")
                if not any(row["evidence_id"] == source["evidence_id"] for row in seeded):
                    seeded.append(source)
    return seeded


def _seed_existing_leads(row_id: str, source_dir: Path, accepted_names: set[str]) -> list[dict]:
    leads = []
    for path in (source_dir / "luna_cache").glob("*.json"):
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if saved.get("row_id") != row_id:
            continue
        for person in (saved.get("decision") or {}).get("people", []):
            if not isinstance(person, dict) or person.get("name", "").casefold() in accepted_names:
                continue
            lead = {key: person.get(key, "") for key in ("name", "title", "linkedin_url", "role_url")}
            if lead["name"] and lead not in leads:
                leads.append(lead)
    return leads


def _resolve_exact_profile(company: dict, claim: dict, sources: list[dict],
                           cache_dir: Path, api_key: str, budget: Budget,
                           searcher=configured_search, requester=_post_json) -> tuple[dict, dict]:
    """Find one exact indexed profile; never construct a URL from a person's name."""
    if canonicalize_linkedin_url(claim.get("linkedin_url", ""), "person"):
        return dict(claim), {"error": "", "sources": [], "cache_hit": True}
    query = f'site:linkedin.com/in/ "{claim["name"]}" "{company["company"]}" {claim["title"]}'
    result = search(query, cache_dir, api_key, budget, searcher, requester)
    matches = []
    for item in result.get("sources", []):
        profile = canonicalize_linkedin_url(item.get("url", ""), "person")
        if profile and _profile_in_cited_excerpt(
                {"url": item["url"], "title": item["title"], "content": item["excerpt"]},
                profile, claim["name"], company["company"]):
            matches.append((profile, item))
    unique = {profile: item for profile, item in matches}
    if len(unique) != 1:
        result["error"] = result.get("error") or (
            "multiple_matching_profiles" if unique else "exact_profile_not_found")
        return dict(claim), result
    profile, source = next(iter(unique.items()))
    resolved = {**claim, "linkedin_url": profile, "linkedin_evidence_url": source["url"],
                "source_urls": list(dict.fromkeys(claim["source_urls"] + [source["url"]]))}
    result["resolved_profile"] = profile
    return resolved, result


def _role_source(company: dict, claim: dict, sources: list[dict], today: date) -> tuple[dict | None, str]:
    from research_canada_executives import role_rank
    if role_rank(claim["title"]) == 99:
        return None, "ineligible_title"
    for item in sources:
        if not _same_url(item.get("url", ""), claim["role_url"]):
            continue
        if not _current_role_mention(item.get("excerpt", ""), claim["name"], claim["title"]):
            continue
        url = item["url"]
        path = urlsplit(url).path.casefold()
        official = same_host(url, company.get("website", ""))
        if item.get("fetched") and not same_host(item.get("final_url", ""), company.get("website", "")):
            continue
        if item.get("error"):
            continue
        team = bool(re.search(r"/(?:about|team|leadership|people|management|who-we-are|meet-the-team|meet-our-team|our-team)(?:[/\-]|$)", path))
        if (official and item.get("fetched") and claim["linkedin_url"]
                and claim["linkedin_url"] in item.get("raw_html", "")
                and not item.get("published_at")):
            return item, "official_card"
        if official and team and (not item.get("published_at") or _recent(item["published_at"], today)):
            return item, "official_team"
        if official and _recent(item.get("published_at", ""), today):
            return item, "recent_official_announcement"
        if (urlsplit(url).hostname or "").removeprefix("www.") == "linkedin.com" and urlsplit(url).path.startswith("/posts/") and _recent(item.get("published_at", ""), today):
            # Company-post authorship must be tied to an official company link.
            post_author = urlsplit(url).path.split("/posts/", 1)[-1].split("_", 1)[0]
            post_key = re.sub(r"[^a-z0-9]", "", post_author.casefold())
            company_link = False
            for source in sources:
                if not source.get("fetched") or not same_host(source.get("url", ""), company.get("website", "")):
                    continue
                soup = BeautifulSoup(source.get("raw_html", ""), "html.parser")
                for anchor in soup.find_all("a", href=True):
                    linked = canonicalize_linkedin_url(anchor["href"], "company")
                    if not linked:
                        continue
                    company_slug = urlsplit(linked).path.rstrip("/").split("/")[-1]
                    slug_key = re.sub(r"[^a-z0-9]", "", company_slug.casefold())
                    if len(slug_key) >= 5 and post_key == slug_key:
                        company_link = True
            if company_link and company["company"].casefold() in (item.get("title", "") + item.get("excerpt", "")).casefold():
                return item, "recent_company_post"
        release_host = (urlsplit(url).hostname or "").removeprefix("www.")
        issuers = ("newsfilecorp.com", "globenewswire.com", "businesswire.com")
        if _recent(item.get("published_at", ""), today) and any(
                release_host == host or release_host.endswith("." + host) for host in issuers):
            if company["company"].casefold() in (item.get("title", "") + item.get("excerpt", "")).casefold():
                return item, "recent_issued_announcement"
    return None, "role_evidence_insufficient"


def _profile_source(company: dict, claim: dict, sources: list[dict],
                    role_source: dict, today: date) -> tuple[dict | None, str]:
    from research_canada_executives import clean_words
    profile = canonicalize_linkedin_url(claim["linkedin_url"], "person")
    if not profile:
        return None, "missing_exact_profile"
    if role_source.get("fetched") and same_host(role_source["url"], company.get("website", "")):
        # A direct card link is strong identity evidence only when the HTML
        # pairs this name and role with one exact personal URL.
        from research_canada_executives import PageParser, verified_site_candidates
        page = PageParser()
        page.raw = role_source.get("raw_html", "")
        for item in verified_site_candidates(company, role_source["url"], page, True):
            if item["linkedin_url"] == profile and clean_words(item["name"]) == clean_words(claim["name"]):
                return role_source, "official_direct_profile"
    for item in sources:
        if _profile_in_cited_excerpt({"url": item.get("url", ""), "title": item.get("title", ""),
                                      "content": item.get("excerpt", "")},
                                     profile, claim["name"], company["company"]):
            return item, "indexed_exact_profile"
    slug = urlsplit(profile).path.rstrip("/").split("/")[-1]
    for item in sources:
        url = item.get("url", "")
        if ((urlsplit(url).hostname or "").removeprefix("www.") != "linkedin.com"
                or not urlsplit(url).path.startswith("/posts/")
                or not _same_url(url, claim["linkedin_evidence_url"])):
            continue
        author = urlsplit(url).path.split("/posts/", 1)[-1]
        if not author.startswith(slug + "_"):
            continue
        if not _recent(item.get("published_at", ""), today):
            continue
        if clean_words(company["company"]) in clean_words(item.get("title", "") + " " + item.get("excerpt", "")):
            return item, "recent_attributable_personal_post"
    return None, "profile_identity_insufficient"


def _unresolved_conflict(source: dict, company_name: str, person_name: str) -> bool:
    if source.get("kind") != "indexed":
        return False
    text = re.sub(r"\s+", " ", source.get("title", "") + " " + source.get("excerpt", ""))[:1400]
    company = re.escape(company_name)
    person = re.escape(person_name)
    closure = r"(?:winding down|shut down|closed (?:its )?(?:doors|operations|business)|ceased (?:operations|trading)|acquired)"
    if re.search(rf"\b{company}\b.{{0,100}}\b{closure}\b", text, re.I):
        return True
    if re.search(rf"\b{closure}\b.{{0,100}}\b{company}\b", text, re.I):
        return True
    personal = (
        rf"\bformer\s+(?:chief executive officer|ceo|coo|cto|cfo|founder)\b.{{0,45}}\b{person}\b",
        rf"\b{person}\b[^.!?]{{0,45}}\b(?:is|was|became|described as)\s+(?:a\s+)?former\b",
        rf"\b{person}\b[^.!?]{{0,75}}\b(?:left|departed|was replaced|now at|joined another)\b",
        rf"\b{person}\b[^.!?]{{0,85}}\b(?:resigned from|stepped down from)\b",
    )
    return any(re.search(pattern, text, re.I) for pattern in personal)


def assess_claim(company: dict, claim: dict, sources: list[dict], *,
                 company_verdict: str, company_status: str, conflict_checked: bool,
                 today: date | None = None) -> tuple[bool, str, dict]:
    today = today or date.today()
    identity = company_identity_evidence(company, sources)
    if company_verdict != "supported" or company_status != "active" or not identity["verified"]:
        return False, "company_identity_or_activity_unverified", {"company_identity": identity,
            "company_verdict": company_verdict, "company_status": company_status}
    company = {**company, "website": identity["website"]}
    if claim["verdict"] != "supported" or claim["conflicts"]:
        return False, "model_uncertain_or_conflicted", {}
    if not conflict_checked:
        return False, "conflict_search_incomplete", {}
    if any(_unresolved_conflict(s, company["company"], claim["name"]) for s in sources):
        return False, "unresolved_conflicting_evidence", {}
    role, role_kind = _role_source(company, claim, sources, today)
    if not role:
        return False, role_kind, {}
    profile, profile_kind = _profile_source(company, claim, sources, role, today)
    if not profile:
        return False, profile_kind, {}
    return True, f"{role_kind}+{profile_kind}", {"role": role["evidence_id"],
                                                  "profile": profile["evidence_id"], "company_identity": identity}


def run_investigation(companies: list[dict], decisions: list[dict], output_dir: Path,
                      *, source_rows: set[int], max_cost_usd: float = 1.0,
                      max_requests: int = 24, max_searches: int = 48,
                      max_fetches: int = 32, key_file: Path | None = None,
                      target_order: tuple[int, ...] | None = None,
                      searcher=configured_search, fetcher=None,
                      requester=_post_json) -> tuple[list[dict], dict]:
    from research_canada_executives import candidate_id, role_rank
    if not source_rows or max_cost_usd <= 0 or min(max_requests, max_searches, max_fetches) < 1:
        raise ValueError("explicit rows and positive investigation limits are required")
    api_key = load_api_key(key_file)
    cache_dir = output_dir / "investigation_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / "investigation_records.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {}
    budget = Budget(max_cost_usd=max_cost_usd, max_requests=max_requests,
                    max_searches=max_searches, max_fetches=max_fetches)
    for prior_record in ledger.values():
        for turn in prior_record.get("model_turns", []):
            usage = turn.get("usage")
            if isinstance(usage, dict) and usage.get("cost") is not None:
                budget.requests += 1
                budget.cost_usd += float(usage["cost"])
        for step in prior_record.get("steps", []):
            if step.get("cache_hit") is not False:
                continue
            if step.get("kind") in ACTION_KINDS and step.get("kind") != "inspect_official":
                budget.searches += 1
            elif step.get("kind") in {"inspect_official", "homepage", "verify_website"}:
                budget.fetches += 1
    for cached_path in cache_dir.glob("*.json"):
        try:
            cached = json.loads(cached_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if cached.get("backend") == "openrouter_server_search":
            usage = cached.get("usage")
            if isinstance(usage, dict) and usage.get("cost") is not None:
                budget.requests += 1
                budget.cost_usd += float(usage["cost"])
    previous_summary_path = output_dir / "investigation_last_run.json"
    if previous_summary_path.exists():
        previous_summary = json.loads(previous_summary_path.read_text(encoding="utf-8"))
        budget.requests = int(previous_summary.get("openrouter_requests", budget.requests))
        budget.searches = int(previous_summary.get("searches", budget.searches))
        budget.fetches = int(previous_summary.get("fetches", budget.fetches))
        budget.cost_usd = float(previous_summary.get("reported_cost_usd", budget.cost_usd))
    # Persist the reservation before the network call. An interrupted request
    # with unknown billing blocks paid replay instead of silently resetting spend.
    journal_path = output_dir / "request_journal.json"
    journal = (json.loads(journal_path.read_text()) if journal_path.exists() else
               {"base_cost": budget.cost_usd, "base_requests": budget.requests, "requests": []})
    if journal_path.exists():
        budget.requests = journal["base_requests"] + len(journal["requests"])
        budget.cost_usd = journal["base_cost"] + sum(
            float(r["usage"]["cost"]) for r in journal["requests"]
            if isinstance(r.get("usage", {}).get("cost"), (int, float)))
        budget.missing_usage = any(r.get("usage", {}).get("cost") is None
                                   for r in journal["requests"])
    network_requester = requester
    def journaled_requester(payload, key):
        entry = {"at": _now(), "request": payload, "state": "in_flight", "usage": {}}
        journal["requests"].append(entry)
        _save(journal_path, journal)
        result = network_requester(payload, key)
        entry.update(state="returned", usage=result.get("usage") or {}, response=result)
        _save(journal_path, journal)
        return result
    requester = journaled_requester
    targets = [c for c in companies if c.get("source_row") in source_rows]
    if target_order:
        order = {row: index for index, row in enumerate(target_order)}
        targets.sort(key=lambda c: order.get(c["source_row"], len(order)))
    completed = []
    cache_hits = 0
    accepted = pending = 0
    for company in targets:
        row_id = company["row_id"]
        if row_id in ledger and ledger[row_id].get("completed"):
            completed.append(row_id)
            cache_hits += 1
            continue
        if not budget.can_request():
            break
        prior = [r for r in decisions if r.get("row_id") == row_id]
        record = ledger.get(row_id, {"row_id": row_id, "company": company["company"],
                                     "version": VERSION, "sources": [], "steps": [],
                                     "model_turns": [], "claim_decisions": []})
        sources = record["sources"]
        steps = record["steps"]
        if not sources:
            citation_dir = output_dir.parent if (output_dir.parent / "luna_cache").exists() else output_dir
            sources.extend(_seed_existing_citations(row_id, citation_dir))
            steps.append({"kind": "seed_retained_citations", "source_ids":
                          [s["evidence_id"] for s in sources]})
        else:
            citation_dir = output_dir.parent if (output_dir.parent / "luna_cache").exists() else output_dir
        accepted_names = {r.get("name", "").casefold() for r in prior if r.get("decision") == "accept"}
        leads = _seed_existing_leads(row_id, citation_dir, accepted_names)
        record["candidate_leads"] = leads
        prior_company_requests = sum(bool(t.get("usage")) for t in record["model_turns"]) + sum(
            bool(t.get("usage")) and not t.get("cache_hit", False) for t in steps)
        company_request_start = budget.requests - prior_company_requests
        # Homepage identity is always checked by Python, even when the model
        # already proposes an official site or the workbook lists one.
        website = company.get("website", "")
        if valid_web_url(website) and not any(s.get("fetched") and
               same_host(s.get("final_url", ""), website) and
               not urlsplit(s.get("final_url", "")).path.strip("/") for s in sources):
            result = fetch(website, cache_dir, budget, fetcher)
            cache_hits += int(result.get("cache_hit", False))
            sources.extend(result.get("sources", []))
            if result.get("raw_html") and sources:
                sources[-1]["raw_html"] = result["raw_html"]
            steps.append({"kind": "homepage", "url": website, "error": result.get("error", ""),
                          "cache_hit": result.get("cache_hit", False)})
        # Fetch up to two official role pages suggested by older model runs.
        # The suggestions are leads only; their page content must pass the gate.
        role_hints = list(dict.fromkeys(lead.get("role_url", "") for lead in leads
                                        if same_host(lead.get("role_url", ""), website)))
        for role_url in role_hints[:2]:
            if any(s.get("fetched") and _same_url(s.get("url", ""), role_url) for s in sources):
                continue
            result = fetch(role_url, cache_dir, budget, fetcher)
            cache_hits += int(result.get("cache_hit", False))
            for source in result.get("sources", []):
                if result.get("raw_html"):
                    source["raw_html"] = result["raw_html"]
                if not any(s["evidence_id"] == source["evidence_id"] for s in sources):
                    sources.append(source)
            steps.append({"kind": "fetch_role_hint", "url": role_url,
                          "error": result.get("error", ""),
                          "cache_hit": result.get("cache_hit", False)})
        last_response = None
        for _ in range(max(0, 3 - len(record["model_turns"]))):
            if budget.requests - company_request_start >= MAX_COMPANY_REQUESTS:
                steps.append({"kind": "company_request_limit"})
                break
            response, turn = _model_turn(company, prior, sources, steps, leads, api_key, budget, requester)
            record["model_turns"].append(turn)
            _save(ledger_path, {**ledger, row_id: record})
            if not response:
                break
            if budget.stopped_reason:
                break
            last_response = response
            proposed_site = response["official_website"]
            if not website and valid_web_url(proposed_site):
                homepage_result = fetch(proposed_site, cache_dir, budget, fetcher)
                cache_hits += int(homepage_result.get("cache_hit", False))
                for source in homepage_result.get("sources", []):
                    if homepage_result.get("raw_html"):
                        source["raw_html"] = homepage_result["raw_html"]
                    if not any(s["evidence_id"] == source["evidence_id"] for s in sources):
                        sources.append(source)
                final_url = (homepage_result.get("sources") or [{}])[0].get("final_url", "")
                if (homepage_result.get("raw_html") and same_host(final_url, proposed_site)
                        and _company_identity({**company, "website": final_url}, sources)):
                    website = final_url
                    company["website"] = website
                    company["website_source"] = "investigation_verified_homepage"
                    company["website_evidence_url"] = final_url
                    company["website_checked_at"] = date.today().isoformat()
                    company["identity_status"] = "homepage_name_match"
                steps.append({"kind": "verify_website", "url": proposed_site,
                              "error": homepage_result.get("error", ""),
                              "cache_hit": homepage_result.get("cache_hit", False)})
            missing_roles = [c for c in response["claims"]
                             if c["verdict"] == "supported" and not c["conflicts"]
                             and not _role_source(company, c, sources, date.today())[0]]
            follow_up = bool(missing_roles and len(record["model_turns"]) < 3
                             and budget.requests - company_request_start < MAX_COMPANY_REQUESTS - 2
                             and response["company_verdict"] == "supported"
                             and _company_identity(company, sources))
            actions = list(response["actions"])
            if follow_up:
                person_claim = missing_roles[0]
                steps.append({"kind": "gate_feedback", "person": person_claim["name"],
                              "reason": "role_evidence_insufficient",
                              "role_url": person_claim["role_url"], "at": _now()})
                if not actions:
                    actions = [{"kind": "search_person_role", "url": "",
                                "person": person_claim["name"],
                                "query": f'"{person_claim["name"]}" "{company["company"]}" "{person_claim["title"]}" current leadership'}]
            if not follow_up and response["claims"] and any(
                    claim["verdict"] == "supported" and not canonicalize_linkedin_url(
                        claim["linkedin_url"], "person") for claim in response["claims"]):
                for skipped in actions:
                    steps.append({"kind": "deferred_action", "requested_kind": skipped["kind"],
                                  "query": skipped["query"], "url": skipped["url"],
                                  "reason": "prioritize_exact_profile_search"})
                actions = []
            if not actions:
                break
            for skipped in actions[1:]:
                steps.append({"kind": "deferred_action", "requested_kind": skipped["kind"],
                              "query": skipped["query"], "url": skipped["url"],
                              "reason": "one_action_per_turn"})
            for action in actions[:1]:
                kind = action["kind"]
                if kind != "inspect_official" and budget.requests - company_request_start >= MAX_COMPANY_REQUESTS - 1:
                    steps.append({"kind": "deferred_search", "query": action["query"],
                                  "reason": "reserve_company_request_for_conflict"})
                    continue
                if kind == "inspect_official":
                    url = action["url"]
                    if not same_host(url, website):
                        result = {"sources": [], "error": "non_official_fetch_rejected"}
                    else:
                        result = fetch(url, cache_dir, budget, fetcher)
                else:
                    query = action["query"].strip()
                    result = search(query, cache_dir, api_key, budget, searcher, requester) if query else {
                        "sources": [], "error": "empty_query"}
                cache_hits += int(result.get("cache_hit", False))
                for source in result.get("sources", []):
                    if result.get("raw_html"):
                        source["raw_html"] = result["raw_html"]
                    if not any(s["evidence_id"] == source["evidence_id"] for s in sources):
                        sources.append(source)
                steps.append({"kind": kind, "query": action["query"], "url": action["url"],
                              "person": action["person"], "error": result.get("error", ""),
                              "backend": result.get("backend", ""),
                              "cache_hit": result.get("cache_hit", False),
                              "source_ids": [s["evidence_id"] for s in result.get("sources", [])],
                              "usage": result.get("usage", {})})
                _save(ledger_path, {**ledger, row_id: record})
            if budget.stopped_reason:
                break
            if response["claims"] and not follow_up:
                break
        if last_response and not budget.stopped_reason:
            for original_claim in sorted(last_response["claims"][:5], key=lambda c: role_rank(c["title"])):
                claim = dict(original_claim)
                if role_rank(claim["title"]) == 99 or not claim["name"].strip():
                    continue
                person = claim["name"].strip()
                if any(r.get("decision") == "accept" and r.get("name", "").casefold() == person.casefold()
                       for r in prior):
                    # Existing accepts are historical baseline. Record conflicts without mutation.
                    if claim["conflicts"] or claim["verdict"] != "supported":
                        record.setdefault("baseline_flags", []).append({"name": person,
                            "conflicts": claim["conflicts"], "verdict": claim["verdict"]})
                    continue
                if claim["verdict"] == "supported" and not claim["conflicts"] and not canonicalize_linkedin_url(
                        claim["linkedin_url"], "person") and budget.requests - company_request_start < MAX_COMPANY_REQUESTS - 1:
                    claim, profile_result = _resolve_exact_profile(
                        company, claim, sources, cache_dir, api_key, budget, searcher, requester)
                    cache_hits += int(profile_result.get("cache_hit", False))
                    for source in profile_result.get("sources", []):
                        if not any(s["evidence_id"] == source["evidence_id"] for s in sources):
                            sources.append(source)
                    steps.append({"kind": "resolve_exact_profile", "person": person,
                                  "query": profile_result.get("query", ""),
                                  "error": profile_result.get("error", ""),
                                  "source_ids": [s["evidence_id"] for s in profile_result.get("sources", [])],
                                  "resolved_profile": profile_result.get("resolved_profile", ""),
                                  "usage": profile_result.get("usage", {})})
                conflict_query = f'"{person}" "{company["company"]}" former OR departed OR replaced OR current'
                should_check = (claim["verdict"] == "supported" and not claim["conflicts"]
                                and canonicalize_linkedin_url(claim["linkedin_url"], "person"))
                conflict_result = (search(conflict_query, cache_dir, api_key, budget, searcher, requester)
                                   if should_check and budget.requests - company_request_start < MAX_COMPANY_REQUESTS
                                   else {"sources": [], "error": "not_checked_or_company_request_limit",
                                         "cache_hit": False})
                cache_hits += int(conflict_result.get("cache_hit", False))
                sources.extend(s for s in conflict_result.get("sources", [])
                               if not any(t["evidence_id"] == s["evidence_id"] for t in sources))
                steps.append({"kind": "check_conflict", "query": conflict_query,
                              "person": person, "error": conflict_result.get("error", ""),
                              "backend": conflict_result.get("backend", ""),
                              "cache_hit": conflict_result.get("cache_hit", False),
                              "source_ids": [s["evidence_id"] for s in conflict_result.get("sources", [])],
                              "usage": conflict_result.get("usage", {})})
                checked = not conflict_result.get("error") and bool(conflict_result.get("sources"))
                ok, reason, refs = assess_claim(company, claim, sources,
                    company_verdict=last_response["company_verdict"],
                    company_status=last_response["company_status"], conflict_checked=checked)
                profile = canonicalize_linkedin_url(claim["linkedin_url"], "person")
                cid = candidate_id(row_id, profile or claim["role_url"], person)
                record["claim_decisions"].append({"candidate_id": cid, "name": person,
                    "verdict": claim["verdict"], "accepted": ok, "reason": reason,
                    "evidence_ids": refs, "claim": claim, "assessed_at": _now(),
                    "retrieval_errors": [s for s in steps if s.get("error")],
                    "policy_version": VERSION})
                existing = next((r for r in decisions if r.get("candidate_id") == cid), None)
                if existing and existing.get("decision") == "accept":
                    continue
                row = {"candidate_id": cid, "row_id": row_id, "company": company["company"],
                       "name": person, "title": claim["title"], "linkedin_url": profile,
                       "email": "", "phone": "", "role_url": claim["role_url"],
                       "linkedin_evidence_url": claim["linkedin_evidence_url"] if ok else "",
                       "email_evidence_url": "", "phone_evidence_url": "",
                       "identity_verified": "yes" if ok else "",
                       "employment_verified": "yes" if ok else "",
                       "linkedin_verified": "yes" if ok else "",
                       "decision": "accept" if ok else "pending",
                       "reason": "investigation_" + reason,
                       "checked_at": date.today().isoformat(),
                       "evidence_record_id": row_id}
                if existing:
                    existing.update(row)
                else:
                    decisions.append(row)
                accepted += int(ok)
                pending += int(not ok)
        # Write decisions before marking the record complete. A restart can
        # safely replay an incomplete record without losing a saved decision.
        from research_canada_executives import write_csv
        write_csv(output_dir / "decisions.csv", decisions)
        record["completed"] = bool(last_response) and not budget.stopped_reason and (
            bool(last_response["claims"]) or not last_response["actions"])
        record["finished_at"] = _now()
        ledger[row_id] = record
        _save(ledger_path, ledger)
        if record["completed"]:
            completed.append(row_id)
        if budget.stopped_reason:
            break
    unique_new = {r["candidate_id"]: r for record in ledger.values()
                  for r in record.get("claim_decisions", [])}
    completed = [c["row_id"] for c in targets if ledger.get(c["row_id"], {}).get("completed")]
    return decisions, {"baseline_selected": 37, "newly_accepted": sum(r["accepted"] for r in unique_new.values()),
        "new_pending": sum(not r["accepted"] for r in unique_new.values()),
        "accepted_this_invocation": accepted, "pending_this_invocation": pending,
        "completed_rows": completed,
        "attempted_rows": [c["row_id"] for c in targets if c["row_id"] in ledger],
        "unfinished_rows": [c["row_id"] for c in targets
                            if c["row_id"] in ledger and c["row_id"] not in completed],
        "never_started_rows": [c["row_id"] for c in targets if c["row_id"] not in ledger],
        "unprocessed_rows": [c["row_id"] for c in targets if c["row_id"] not in completed],
        "openrouter_requests": budget.requests, "searches": budget.searches,
        "fetches": budget.fetches, "cache_hits": cache_hits,
        "reported_cost_usd": round(budget.cost_usd, 6),
        "cost_limit_usd": max_cost_usd, "cost_overshoot_usd": round(max(0.0, budget.cost_usd-max_cost_usd), 6),
        "stopped_reason": budget.stopped_reason,
        "conflict_flags": sum(len(x.get("baseline_flags", [])) for x in ledger.values())}
