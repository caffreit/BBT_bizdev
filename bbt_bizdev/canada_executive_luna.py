"""Cost-limited Luna discovery with independent verification against official pages."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from bbt_bizdev.adapters.linkedin import canonicalize_linkedin_url
from bbt_bizdev.canada_website_llm import MODEL, OPENROUTER_URL

PROMPT_VERSION = "canada_executive_luna_v2_cited_evidence"
PROFILE_PROMPT_VERSION = "canada_executive_profile_lookup_v2"
DEFAULT_KEY_FILE = Path.home() / ".config" / "bbt_bizdev" / "openrouter.key"
SCHEMA = {
    "type": "object",
    "properties": {
        "official_website": {"type": "string"},
        "company_status": {"enum": ["active", "inactive", "uncertain"]},
        "people": {
            "type": "array", "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "title": {"type": "string"},
                    "linkedin_url": {"type": "string"},
                    "role_url": {"type": "string"},
                    "email": {"type": "string"},
                    "email_url": {"type": "string"},
                    "conflict": {"type": "string"},
                },
                "required": ["name", "title", "linkedin_url", "role_url", "email", "email_url", "conflict"],
                "additionalProperties": False,
            },
        },
        "notes": {"type": "string"},
    },
    "required": ["official_website", "company_status", "people", "notes"],
    "additionalProperties": False,
}
PROFILE_SCHEMA = {
    "type": "object",
    "properties": {"people": {"type": "array", "maxItems": 5, "items": {
        "type": "object", "properties": {"name": {"type": "string"},
                                      "linkedin_url": {"type": "string"},
                                      "match_status": {"enum": ["confirmed", "uncertain", "different_company"]},
                                      "conflict": {"type": "string"}},
        "required": ["name", "linkedin_url", "match_status", "conflict"], "additionalProperties": False,
    }}},
    "required": ["people"], "additionalProperties": False,
}


def build_prompt(company: dict, existing: list[dict]) -> str:
    context = {
        "company": company["company"],
        "listed_website": company.get("website", ""),
        "province": company.get("province", ""),
        "product": str(company.get("product", ""))[:500],
        "already_accepted": [row.get("name", "") for row in existing if row.get("decision") == "accept"],
    }
    return (
        "Research the CURRENT executive leadership of this exact company. Prioritize CEO, COO, CTO, "
        "then CFO. Search its official About/Team/Leadership pages, company LinkedIn page, and web "
        "results for each role and exact person name. Search the personal LinkedIn URL separately when "
        "the company page names a person but does not link to their profile. Check for acquisitions, "
        "shutdowns, replacements, "
        "and same-name companies. Return up to five people with a direct role source URL and exact "
        "personal LinkedIn URL. A LinkedIn search-result slug alone is insufficient to claim a match. "
        "Leave any uncertain field blank, report conflicts, and never invent an email or infer an "
        "email pattern. Only report a published individual email with its source URL. If the company "
        "is no longer active, mark inactive and do not list historical executives as current. "
        "Return URLs without tracking parameters.\n\n"
        + json.dumps(context, ensure_ascii=False)
    )


def _request_json_with_citations(prompt: str, schema: dict, schema_name: str,
                                 api_key: str) -> tuple[dict | None, dict, str]:
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
               "plugins": [{"id": "web", "engine": "exa", "max_results": 6}],
               "response_format": {"type": "json_schema", "json_schema": {
                   "name": schema_name, "strict": True, "schema": schema}},
               "reasoning": {"effort": "low", "exclude": True}, "max_tokens": 1800}
    request = Request(OPENROUTER_URL, data=json.dumps(payload).encode("utf-8"), headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
        "User-Agent": "BBTResearch/1.0",
    })
    try:
        with urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
        choice = data["choices"][0]
        message = choice["message"]
        usage = data.get("usage") or {}
        citations = []
        for item in message.get("annotations", []):
            citation = item.get("url_citation", {}) if isinstance(item, dict) else {}
            if valid_web_url(citation.get("url", "")):
                citations.append({"url": citation["url"], "title": citation.get("title", "")[:300],
                                  "content": citation.get("content", "")[:5000]})
        recorded_usage = {"cost": float(usage.get("cost") or 0),
                          "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                          "completion_tokens": int(usage.get("completion_tokens") or 0),
                          "citations": citations[:12]}
        try:
            return json.loads(message["content"]), recorded_usage, ""
        except (ValueError, TypeError) as error:
            sample = repr(message.get("content", ""))[:300]
            return None, recorded_usage, (f"{type(error).__name__}: {str(error)[:120]}; "
                                          f"finish={choice.get('finish_reason')}; content={sample}")
    except HTTPError as error:
        return None, {}, f"OpenRouter HTTP {error.code}"
    except (OSError, URLError, KeyError, IndexError, ValueError, TypeError) as error:
        return None, {}, f"{type(error).__name__}: {str(error)[:200]}"


def request_luna(company: dict, existing: list[dict], api_key: str) -> tuple[dict | None, dict, str]:
    return _request_json_with_citations(build_prompt(company, existing), SCHEMA,
                                        "canadian_executive_candidates", api_key)


def request_profile_lookup(company: dict, people: list[dict], api_key: str) -> tuple[dict | None, dict, str]:
    names = [{"name": person["name"], "title": person["title"],
              "proposed_profile": person.get("linkedin_url", "")}
             for person in people[:5]]
    prompt = (
        "Search separately for each named person's exact personal LinkedIn profile at this company. "
        "A name match alone is insufficient: require evidence that the exact profile belongs to "
        "this company's executive. Check same-name people and past roles. Set match_status to "
        "confirmed only for a current exact-company match, and then leave conflict empty. For an "
        "uncertain or different-company match, return an empty URL and explain the conflict. "
        "Do not invent a LinkedIn slug. Return only the input "
        "names and direct linkedin.com/in URLs, without tracking parameters.\n\n"
        + json.dumps({"company": company["company"], "website": company.get("website", ""),
                      "people": names}, ensure_ascii=False))
    return _request_json_with_citations(prompt, PROFILE_SCHEMA,
                                        "canadian_executive_profile_lookup", api_key)


def same_host(first: str, second: str) -> bool:
    return urlsplit(first).hostname is not None and (
        (urlsplit(first).hostname or "").removeprefix("www.").lower()
        == (urlsplit(second).hostname or "").removeprefix("www.").lower()
    )


def valid_web_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme in {"https", "http"} and bool(parts.hostname)


def load_api_key(key_file: Path | None = None) -> str:
    key = os.getenv("OPENROUTER_API_KEY", "").strip() or os.getenv("BBT_OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    path = key_file or DEFAULT_KEY_FILE
    if not path.exists():
        raise RuntimeError(f"OpenRouter key is absent from this process and {path} does not exist")
    details = path.stat()
    if details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) & 0o077:
        raise RuntimeError(f"OpenRouter key file must be owned by you and readable only by you: {path}")
    key = path.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError(f"OpenRouter key file is empty: {path}")
    return key


def check_openrouter_key(key_file: Path | None = None) -> dict:
    """Validate credentials without a model request or paid research call."""
    request = Request("https://openrouter.ai/api/v1/key", headers={
        "Authorization": f"Bearer {load_api_key(key_file)}", "User-Agent": "BBTResearch/1.0",
    })
    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"OpenRouter key check failed: HTTP {error.code}") from None
    except (OSError, URLError, ValueError) as error:
        raise RuntimeError(f"OpenRouter key check failed: {type(error).__name__}: {str(error)[:160]}") from None
    data = result.get("data") or {}
    return {"authenticated": True, "limit_remaining_usd": data.get("limit_remaining"),
            "expires_at": data.get("expires_at")}


def listed_site_matches_official(company: dict, official_website: str, fetcher=None) -> bool:
    """Accept a changed domain only when the listed site redirects to the named official site."""
    from research_canada_executives import fetch_page, homepage_matches_company

    listed = company.get("website", "")
    if not listed:
        return True
    if not valid_web_url(listed) or not valid_web_url(official_website):
        return False
    if same_host(listed, official_website):
        return True
    page, error = (fetcher or fetch_page)(listed)
    return bool(not error and page and same_host(getattr(page, "final_url", ""), official_website)
                and homepage_matches_company(company, page))


def record_discovered_website(company: dict, official_website: str, fetcher=None,
                              accepted_role_urls: list[str] | None = None) -> bool:
    """Persist a missing site only after its live homepage identifies the company."""
    from research_canada_executives import fetch_page, homepage_matches_company, clean_words

    if company.get("website") or company.get("identity_issue") or not valid_web_url(official_website):
        return False
    page, error = (fetcher or fetch_page)(official_website)
    if error or not page or not same_host(getattr(page, "final_url", ""), official_website):
        return False
    soup = BeautifulSoup(page.raw, "html.parser")
    heading = " ".join(tag.get_text(" ", strip=True) for tag in soup.find_all(["title", "h1"], limit=8))
    footer = " ".join(tag.get_text(" ", strip=True) for tag in soup.find_all("footer", limit=2))
    named_footer = clean_words(company["company"]) in clean_words(footer)
    if not homepage_matches_company(company, page) and not named_footer:
        return False
    named_heading = clean_words(company["company"]) in clean_words(heading)
    accepted_role = any(same_host(url, official_website) for url in (accepted_role_urls or []))
    if not named_heading and not named_footer and not accepted_role:
        return False
    company["website"] = getattr(page, "final_url", official_website)
    company["website_source"] = "luna_discovery_verified_homepage"
    company["website_evidence_url"] = company["website"]
    company["website_checked_at"] = date.today().isoformat()
    company["identity_status"] = "homepage_name_match"
    company["errors"] = [item for item in company.get("errors", []) if item != "missing_website"]
    if company.get("status") in {"access_blocked", "website_missing"}:
        company["status"] = "website_discovered"
    return True


def official_role_title(page, name: str, expected_title: str) -> str:
    """Find a short official team card explicitly pairing the name with the role."""
    from research_canada_executives import clean_words, role_rank

    expected_name = clean_words(name)
    expected_rank = role_rank(expected_title)
    if not expected_name or expected_rank == 99:
        return ""
    soup = BeautifulSoup(page.raw, "html.parser")
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "strong"]):
        raw_name = heading.get_text(" ", strip=True)
        heading_words = clean_words(raw_name)
        if heading_words != expected_name and not heading_words.startswith(expected_name + " "):
            continue
        for card in list(heading.parents)[:3]:
            text = card.get_text(" ", strip=True)
            if len(text) > 250 or not text.startswith(raw_name):
                continue
            title = text[len(raw_name):].strip(" ,;:-")
            if title and len(title) <= 120 and role_rank(title) == expected_rank:
                return title
    return ""


def linkedin_profile_matches(page, profile: str, name: str, company_name: str) -> bool:
    """Require exact public profile URL, name, and current-company headline."""
    from research_canada_executives import clean_words

    final_profile = canonicalize_linkedin_url(getattr(page, "final_url", ""), "person")
    if final_profile != profile:
        return False
    soup = BeautifulSoup(page.raw, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if " - " not in title:
        return False
    profile_name, headline = title.split(" - ", 1)
    if clean_words(profile_name) != clean_words(name):
        return False
    company = clean_words(company_name)
    headline = clean_words(headline.split("| LinkedIn", 1)[0])
    return bool(company and (headline == company or headline.startswith(company + " ")))


def verify_person(company: dict, person: dict, official_website: str,
                  fetcher=None) -> dict | None:
    """Model output is accepted only if the live official page proves every core claim."""
    from research_canada_executives import (
        candidate_id, fetch_page, homepage_matches_company, verified_site_candidates,
    )

    fetcher = fetcher or fetch_page
    if company.get("identity_issue") or person.get("conflict"):
        return None
    profile = canonicalize_linkedin_url(person.get("linkedin_url", ""), "person")
    role_url = person.get("role_url", "")
    if not profile or not valid_web_url(official_website) or not valid_web_url(role_url):
        return None
    if not same_host(official_website, role_url):
        return None
    homepage, home_error = fetcher(official_website)
    if home_error or not homepage or not same_host(official_website, getattr(homepage, "final_url", official_website)):
        return None
    if not homepage_matches_company(company, homepage):
        return None
    page, role_error = fetcher(role_url)
    if role_error or not page or not same_host(official_website, getattr(page, "final_url", role_url)):
        return None
    for item in verified_site_candidates(company, role_url, page, True):
        if item["name"].casefold() != person.get("name", "").strip().casefold():
            continue
        if item["linkedin_url"] != profile:
            continue
        # The official page supplies the title and any published email. The model cannot add either.
        return {
            "candidate_id": candidate_id(company["row_id"], profile, item["name"]),
            "row_id": company["row_id"], "company": company["company"],
            "name": item["name"], "title": item["title"], "linkedin_url": profile,
            "email": item.get("email", ""), "phone": "", "role_url": role_url,
            "linkedin_evidence_url": role_url,
            "email_evidence_url": item.get("email_evidence_url", ""),
            "phone_evidence_url": "", "identity_verified": "yes",
            "employment_verified": "yes", "linkedin_verified": "yes",
            "decision": "accept", "reason": "luna_found_official_team_card",
            "checked_at": date.today().isoformat(),
        }
    title = official_role_title(page, person.get("name", ""), person.get("title", ""))
    if not title:
        return None
    linkedin_page, linkedin_error = fetcher(profile)
    if linkedin_error or not linkedin_page or not linkedin_profile_matches(
        linkedin_page, profile, person.get("name", ""), company["company"]
    ):
        return None
    return {
        "candidate_id": candidate_id(company["row_id"], profile, person["name"]),
        "row_id": company["row_id"], "company": company["company"],
        "name": person["name"], "title": title, "linkedin_url": profile,
        "email": "", "phone": "", "role_url": role_url,
        "linkedin_evidence_url": profile, "email_evidence_url": "", "phone_evidence_url": "",
        "identity_verified": "yes", "employment_verified": "yes", "linkedin_verified": "yes",
        "decision": "accept", "reason": "luna_official_role_and_linkedin_company",
        "checked_at": date.today().isoformat(),
    }


def _role_in_cited_excerpt(content: str, name: str, title: str) -> bool:
    """Require a person's name and the proposed role in one short source excerpt."""
    from research_canada_executives import ROLE_PATTERNS, clean_words, role_rank

    rank = role_rank(title)
    if rank == 99:
        return False
    words = clean_words(content)
    target = clean_words(name)
    for match in re.finditer(rf"\b{re.escape(target)}\b", words):
        nearby = words[match.end():match.end() + 95]
        first_role = min(((found.start(), index)
                          for index, (_, pattern) in enumerate(ROLE_PATTERNS)
                          if (found := re.search(pattern, nearby, re.I))), default=None)
        if first_role and first_role[1] == rank:
            return True
    return False


def _profile_in_cited_excerpt(citation: dict, profile: str, name: str, company_name: str) -> bool:
    """Use only the exact personal URL and its own indexed headline/experience."""
    from research_canada_executives import clean_words

    if canonicalize_linkedin_url(citation.get("url", ""), "person") != profile:
        return False
    title = clean_words(citation.get("title", ""))
    name_key = clean_words(name)
    company_key = clean_words(company_name)
    if not title.startswith(name_key) or not company_key:
        return False
    if company_key in title:
        return True
    content = clean_words(citation.get("content", "")[:700])
    if not content.startswith(name_key):
        return False
    return bool(re.search(rf"\b(?:at|with) {re.escape(company_key)}\b", content)
                or re.search(rf"\b(?:experience|current) {re.escape(company_key)}\b", content)
                or re.search(rf"\b(?:chief [a-z ]{{3,50}}|ceo|coo|cto|cfo|president) "
                             rf"{re.escape(company_key)} current\b", content))


def verify_cited_person(company: dict, person: dict, official_website: str,
                        citations: list[dict]) -> dict | None:
    """Accept search-provider evidence when direct sites/LinkedIn block Python.

    Luna selects candidates. Python checks the source URL, quoted role, exact
    personal profile URL, name and current-company evidence independently.
    """
    from research_canada_executives import candidate_id, clean_words, role_rank

    if company.get("identity_issue") or person.get("conflict") or role_rank(person.get("title", "")) == 99:
        return None
    profile = canonicalize_linkedin_url(person.get("linkedin_url", ""), "person")
    role_url = person.get("role_url", "")
    if not profile or not valid_web_url(official_website) or not valid_web_url(role_url):
        return None
    if not same_host(role_url, official_website):
        return None
    # Indexed announcements can remain online years after a leadership change.
    # The citation-only path requires a current leadership/about page.
    if not re.search(r"/(?:about|team|leadership|people|management|who-we-are)(?:[/\-]|$)",
                     urlsplit(role_url).path.casefold()):
        return None
    # A model-proposed website does not establish the workbook entity.
    if not company.get("website") or not same_host(company["website"], official_website):
        return None
    role_source = next((source for source in citations if isinstance(source, dict)
                        and source.get("url", "").rstrip("/") == role_url.rstrip("/")
                        and same_host(source["url"], official_website)
                        and (company.get("identity_status") == "homepage_name_match"
                             or clean_words(company["company"]) in clean_words(
                                 source.get("title", "") + " " + source.get("content", "")[:1200]))
                        and _role_in_cited_excerpt(source.get("content", ""),
                                                   person.get("name", ""), person.get("title", ""))), None)
    profile_source = next((source for source in citations if isinstance(source, dict)
                           and _profile_in_cited_excerpt(source, profile,
                                                         person.get("name", ""), company["company"])), None)
    if not role_source or not profile_source:
        return None
    return {
        "candidate_id": candidate_id(company["row_id"], profile, person["name"]),
        "row_id": company["row_id"], "company": company["company"],
        "name": person["name"], "title": person["title"], "linkedin_url": profile,
        "email": "", "phone": "", "role_url": role_source["url"],
        "linkedin_evidence_url": profile_source["url"],
        "email_evidence_url": "", "phone_evidence_url": "",
        "identity_verified": "yes", "employment_verified": "yes", "linkedin_verified": "yes",
        "decision": "accept", "reason": "luna_cited_official_role_and_exact_profile",
        "checked_at": date.today().isoformat(),
        "_cited_evidence": {"role": role_source, "profile": profile_source},
    }


def run_luna_pass(companies: list[dict], decisions: list[dict], output_dir: Path,
                  *, pilot_only: bool = False, limit: int = 5, max_cost_usd: float = 1.0,
                  key_file: Path | None = None, source_rows: set[int] | None = None,
                  requester=request_luna,
                  profile_requester=request_profile_lookup,
                  verifier=verify_person) -> tuple[list[dict], dict]:
    from research_canada_executives import candidate_id, pilot, role_rank, save_json

    api_key = load_api_key(key_file)
    if limit < 1 or max_cost_usd <= 0:
        raise ValueError("limit and max_cost_usd must be positive")
    cache_dir = output_dir / "luna_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    profile_cache_dir = output_dir / "luna_profile_cache"
    profile_cache_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = output_dir / "luna_cited_evidence.json"
    cited_evidence = (json.loads(evidence_path.read_text(encoding="utf-8"))
                      if evidence_path.exists() else {})

    def retain_evidence(contact: dict) -> dict:
        evidence = contact.pop("_cited_evidence", None)
        if evidence:
            cited_evidence[contact["candidate_id"]] = {
                "row_id": contact["row_id"], "name": contact["name"],
                "checked_at": contact["checked_at"], **evidence,
            }
            save_json(evidence_path, cited_evidence)
        return contact
    targets = pilot(companies) if pilot_only else companies
    if source_rows:
        targets = [company for company in targets if company["source_row"] in source_rows]
    total_cost = 0.0
    calls = accepted = queued = cache_hits = 0
    for company in targets:
        prior = [row for row in decisions if row.get("row_id") == company["row_id"]]
        if len([row for row in prior if row.get("decision") == "accept"]) >= 3:
            continue
        cache_key = hashlib.sha256(f"{PROMPT_VERSION}|{MODEL}|{company['row_id']}".encode()).hexdigest()[:20]
        cache_path = cache_dir / f"{cache_key}.json"
        cached_result = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else None
        if cached_result and not cached_result.get("error"):
            result = cached_result
            cache_hits += 1
        else:
            if calls >= limit or total_cost >= max_cost_usd:
                break
            decision, usage, error = requester(company, prior, api_key)
            result = {"row_id": company["row_id"], "model": MODEL, "prompt_version": PROMPT_VERSION,
                      "decision": decision, "usage": usage, "error": error,
                      "requested_at": date.today().isoformat()}
            save_json(cache_path, result)
            calls += 1
            total_cost += float(usage.get("cost") or 0)
        data = result.get("decision") or {}
        if result.get("error"):
            company["status"] = "luna_error"
            continue
        official = data.get("official_website", "")
        site_agrees = valid_web_url(official) and listed_site_matches_official(company, official)
        website_found = (record_discovered_website(
            company, official,
            accepted_role_urls=[row.get("role_url", "") for row in prior if row.get("decision") == "accept"])
            if site_agrees else False)
        if data.get("company_status") == "inactive":
            company["status"] = "inactive_needs_review"
            continue
        if data.get("company_status") != "active":
            company["status"] = "luna_unresolved"
            continue
        if not valid_web_url(official):
            company["status"] = "luna_unresolved"
            continue
        # A conflicting listed website requires human identity review.
        if not site_agrees:
            company["status"] = "identity_needs_review"
            continue
        for person in data.get("people", [])[:5]:
            if len([row for row in prior if row.get("decision") == "accept"]) >= 3:
                break
            if not isinstance(person, dict) or role_rank(person.get("title", "")) == 99:
                continue
            profile = canonicalize_linkedin_url(person.get("linkedin_url", ""), "person")
            if not profile:
                continue
            existing = next((row for row in prior if row.get("linkedin_url") == profile), None)
            if existing and existing.get("decision") != "pending":
                continue
            verified = verifier(company, person, official)
            if not verified:
                verified = verify_cited_person(company, person, official,
                                               (result.get("usage") or {}).get("citations", []))
            if verified:
                verified = retain_evidence(verified)
                if existing:
                    existing.clear()
                    existing.update(verified)
                else:
                    decisions.append(verified)
                    prior.append(verified)
                accepted += 1
            elif not existing:
                pending = {
                    "candidate_id": candidate_id(company["row_id"], profile, person.get("name", "")),
                    "row_id": company["row_id"], "company": company["company"],
                    "name": person.get("name", ""), "title": person.get("title", ""),
                    "linkedin_url": profile, "email": "", "phone": "",
                    "role_url": person.get("role_url", ""), "linkedin_evidence_url": "",
                    "email_evidence_url": "", "phone_evidence_url": "",
                    "identity_verified": "", "employment_verified": "", "linkedin_verified": "",
                    "decision": "pending", "reason": "luna_unverified", "checked_at": date.today().isoformat(),
                }
                decisions.append(pending)
                prior.append(pending)
                queued += 1
        missing_profiles = [person for person in data.get("people", [])[:5]
                            if isinstance(person, dict) and person.get("name")
                            and not canonicalize_linkedin_url(person.get("linkedin_url", ""), "person")
                            and role_rank(person.get("title", "")) != 99
                            and not person.get("conflict")
                            and not any(row.get("decision") == "accept"
                                        and row.get("name", "").casefold() == person["name"].casefold()
                                        for row in prior)]
        if missing_profiles and len([row for row in prior if row.get("decision") == "accept"]) < 3:
            names_key = json.dumps([(p["name"], p["title"]) for p in missing_profiles], ensure_ascii=False)
            digest = hashlib.sha256(f"{PROFILE_PROMPT_VERSION}|{MODEL}|{company['row_id']}|{names_key}".encode()).hexdigest()[:20]
            profile_cache_path = profile_cache_dir / f"{digest}.json"
            profile_result = (json.loads(profile_cache_path.read_text(encoding="utf-8"))
                              if profile_cache_path.exists() else None)
            if profile_result and not profile_result.get("error"):
                cache_hits += 1
            elif calls < limit and total_cost < max_cost_usd:
                proposed, usage, error = profile_requester(company, missing_profiles, api_key)
                profile_result = {"row_id": company["row_id"], "model": MODEL,
                                  "prompt_version": PROFILE_PROMPT_VERSION,
                                  "decision": proposed, "usage": usage, "error": error,
                                  "requested_at": date.today().isoformat()}
                save_json(profile_cache_path, profile_result)
                calls += 1
                total_cost += float(usage.get("cost") or 0)
            else:
                profile_result = None
            if profile_result and not profile_result.get("error"):
                by_name = {p.get("name", "").casefold(): p
                           for p in (profile_result.get("decision") or {}).get("people", [])
                           if isinstance(p, dict)}
                citations = ((result.get("usage") or {}).get("citations", [])
                             + (profile_result.get("usage") or {}).get("citations", []))
                for person in missing_profiles:
                    if len([row for row in prior if row.get("decision") == "accept"]) >= 3:
                        break
                    match = by_name.get(person["name"].casefold(), {})
                    if match.get("match_status") != "confirmed" or match.get("conflict"):
                        continue
                    profile = canonicalize_linkedin_url(match.get("linkedin_url", ""), "person")
                    if not profile:
                        continue
                    proposed_person = {**person, "linkedin_url": profile}
                    verified = verifier(company, proposed_person, official)
                    if not verified:
                        verified = verify_cited_person(company, proposed_person, official, citations)
                    if verified:
                        verified = retain_evidence(verified)
                        old = next((row for row in prior if row.get("linkedin_url") == profile), None)
                        if old and old.get("decision") == "pending":
                            old.clear(); old.update(verified)
                        elif not old:
                            decisions.append(verified); prior.append(verified)
                        accepted += 1
                    elif not any(row.get("linkedin_url") == profile for row in prior):
                        pending = {"candidate_id": candidate_id(company["row_id"], profile, person["name"]),
                                   "row_id": company["row_id"], "company": company["company"],
                                   "name": person["name"], "title": person["title"],
                                   "linkedin_url": profile, "email": "", "phone": "",
                                   "role_url": person.get("role_url", ""), "linkedin_evidence_url": "",
                                   "email_evidence_url": "", "phone_evidence_url": "",
                                   "identity_verified": "", "employment_verified": "",
                                   "linkedin_verified": "", "decision": "pending",
                                   "reason": "luna_profile_unverified", "checked_at": date.today().isoformat()}
                        decisions.append(pending); prior.append(pending); queued += 1
        company["status"] = ("auto_verified" if any(row.get("decision") == "accept" for row in prior)
                             else "needs_review" if prior else "website_discovered" if website_found
                             else "no_candidates")
    cached = [json.loads(path.read_text(encoding="utf-8"))
              for directory in (cache_dir, profile_cache_dir) for path in directory.glob("*.json")]
    cumulative_cost = sum(float((row.get("usage") or {}).get("cost") or 0) for row in cached)
    return decisions, {"calls": calls, "cache_hits": cache_hits, "accepted": accepted,
                       "queued": queued, "reported_cost_usd": round(total_cost, 6),
                       "cached_company_count": len(cached),
                       "cumulative_reported_cost_usd": round(cumulative_cost, 6),
                       "cost_limit_usd": max_cost_usd}
