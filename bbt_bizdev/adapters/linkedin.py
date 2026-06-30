from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
from collections import deque
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from ..config import (
    LINKEDIN_ENRICHMENT_CACHE_DIR,
    LINKEDIN_ENRICHMENT_CACHE_VERSION,
    LINKEDIN_ENRICHMENT_DISABLED_ENV,
    LINKEDIN_MAX_TEAM_PAGES,
    LINKEDIN_SEARCH_MIN_INTERVAL_SECONDS,
    USER_AGENT,
)
from ..http import fetch_raw_text
from ..models import CompanyRecord, LinkedInContact, LinkedInEnrichment


@dataclass(frozen=True)
class PublicSearchHit:
    title: str
    url: str
    snippet: str = ""


@dataclass(frozen=True)
class LinkObservation:
    url: str
    anchor_text: str
    context: str


class _PageLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[LinkObservation] = []
        self._recent_text: deque[str] = deque(maxlen=3)
        self._href = ""
        self._anchor_parts: list[str] = []
        self._anchor_prefix = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        values = {key.lower(): value or "" for key, value in attrs}
        self._href = values.get("href", "")
        self._anchor_parts = []
        self._anchor_prefix = " | ".join(self._recent_text)

    def handle_data(self, data: str) -> None:
        text = clean_space(data)
        if not text:
            return
        if self._href:
            self._anchor_parts.append(text)
        self._recent_text.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href:
            return
        anchor = clean_space(" ".join(self._anchor_parts))
        context = clean_space(f"{self._anchor_prefix} | {anchor}").strip(" |")[0:500]
        self.links.append(LinkObservation(self._href, anchor, context))
        self._href = ""
        self._anchor_parts = []
        self._anchor_prefix = ""


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hits: list[PublicSearchHit] = []
        self._url = ""
        self._title_parts: list[str] = []
        self._snippet_parts: list[str] = []
        self._in_title = False
        self._in_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        classes = values.get("class", "").split()
        if tag.lower() == "a" and "result__a" in classes:
            self._flush()
            self._url = values.get("href", "")
            self._in_title = True
        elif "result__snippet" in classes:
            self._in_snippet = True

    def handle_data(self, data: str) -> None:
        text = clean_space(data)
        if self._in_title and text:
            self._title_parts.append(text)
        elif self._in_snippet and text:
            self._snippet_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._in_title:
            self._in_title = False
        elif tag.lower() in {"a", "div", "span"} and self._in_snippet:
            self._in_snippet = False

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self) -> None:
        title = clean_space(" ".join(self._title_parts))
        if self._url and title:
            self.hits.append(PublicSearchHit(title, unwrap_search_url(self._url), clean_space(" ".join(self._snippet_parts))))
        self._url = ""
        self._title_parts = []
        self._snippet_parts = []
        self._in_title = False
        self._in_snippet = False


def clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def unwrap_search_url(value: str) -> str:
    value = html.unescape(value or "").strip()
    if value.startswith("//"):
        value = "https:" + value
    if value.startswith("/"):
        value = urljoin("https://duckduckgo.com", value)
    parts = urlsplit(value)
    query = parse_qs(parts.query)
    if "uddg" in query and query["uddg"]:
        return unquote(query["uddg"][0])
    return value


def canonicalize_linkedin_url(value: str, expected_kind: str | None = None) -> str:
    value = unwrap_search_url(value)
    if not value:
        return ""
    if value.startswith("linkedin.com/") or value.startswith("www.linkedin.com/"):
        value = "https://" + value
    parts = urlsplit(value)
    host = parts.netloc.lower().split(":", 1)[0]
    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        host = "www.linkedin.com"
    else:
        return ""
    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) < 2:
        return ""
    kind = segments[0].lower()
    if kind not in {"company", "in"}:
        return ""
    if expected_kind == "company" and kind != "company":
        return ""
    if expected_kind == "person" and kind != "in":
        return ""
    slug = segments[1].strip().lower()
    if not slug or slug in {"search", "feed", "jobs", "learning"}:
        return ""
    return urlunsplit(("https", host, f"/{kind}/{slug}", "", ""))


def extract_page_links(raw_html: str, page_url: str) -> list[LinkObservation]:
    parser = _PageLinkParser()
    try:
        parser.feed(raw_html or "")
        parser.close()
    except (ValueError, TypeError):
        return []
    observations: list[LinkObservation] = []
    for item in parser.links:
        observations.append(LinkObservation(urljoin(page_url, item.url), item.anchor_text, item.context))
    return observations


def parse_duckduckgo_results(raw_html: str) -> list[PublicSearchHit]:
    parser = _DuckDuckGoParser()
    try:
        parser.feed(raw_html or "")
        parser.close()
    except (ValueError, TypeError):
        return []
    seen: set[str] = set()
    hits: list[PublicSearchHit] = []
    for hit in parser.hits:
        if not hit.url or hit.url in seen:
            continue
        seen.add(hit.url)
        hits.append(hit)
    return hits


_last_search_at = 0.0


def duckduckgo_search(query: str, attempts: int = 3) -> tuple[list[PublicSearchHit], str | None]:
    global _last_search_at
    url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query)
    last_error = "No search results"
    for attempt in range(attempts):
        wait = LINKEDIN_SEARCH_MIN_INTERVAL_SECONDS - (time.monotonic() - _last_search_at)
        if wait > 0:
            time.sleep(wait)
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        try:
            raw = urlopen(request, timeout=25).read().decode("utf-8", "ignore")
            _last_search_at = time.monotonic()
            hits = parse_duckduckgo_results(raw)
            if hits:
                return hits, None
            last_error = "Search returned no parseable results"
        except (OSError, HTTPError, URLError) as exc:
            _last_search_at = time.monotonic()
            last_error = str(exc)
        if attempt + 1 < attempts:
            time.sleep(2 ** attempt)
    return [], last_error


def _identity_text(value: str) -> str:
    return clean_space(re.sub(r"[^a-z0-9]+", " ", (value or "").lower()))


def company_name_matches(company: str, text: str, website: str = "", official_site: bool = False) -> bool:
    if official_site:
        return True
    company_key = _identity_text(company)
    text_key = _identity_text(text)
    if not company_key or not text_key:
        return False
    pattern = rf"(?:^| ){re.escape(company_key)}(?: |$)"
    if not re.search(pattern, text_key):
        return False
    compact = company_key.replace(" ", "")
    if len(compact) <= 4:
        title_parts = [_identity_text(part) for part in re.split(r"\s+[|–—-]\s+", text)]
        return company_key in title_parts
    return True


def _team_page_urls(links: list[LinkObservation], website: str) -> list[str]:
    root_host = urlsplit(website).netloc.lower().removeprefix("www.")
    candidates: list[str] = []
    for item in links:
        parts = urlsplit(item.url)
        link_host = parts.netloc.lower().removeprefix("www.")
        if parts.scheme not in {"http", "https"} or link_host != root_host:
            continue
        clue = f"{parts.path} {item.anchor_text}".lower()
        if not re.search(r"\b(team|people|leadership|management|about|who-we-are)\b", clue):
            continue
        canonical = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        if canonical not in candidates:
            candidates.append(canonical)
    return candidates[:LINKEDIN_MAX_TEAM_PAGES]


def _company_url_from_observations(items: list[LinkObservation]) -> str:
    for item in items:
        url = canonicalize_linkedin_url(item.url, "company")
        if url:
            return url
    return ""


def _clean_person_name(value: str) -> str:
    value = clean_space(re.sub(r"\b(linkedin|view profile|profile)\b", " ", value, flags=re.I))
    value = value.strip(" |-–—•")
    words = value.split()
    if not (2 <= len(words) <= 6) or not all(re.search(r"[A-Za-z]", word) for word in words):
        return ""
    return value


def _name_from_profile_url(url: str) -> str:
    segments = [segment for segment in urlsplit(url).path.split("/") if segment]
    if len(segments) < 2:
        return ""
    words = [word for word in segments[1].split("-") if word]
    while words and re.search(r"\d", words[-1]):
        words.pop()
    return _clean_person_name(" ".join(word.capitalize() for word in words))


def _title_role_scores(value: str) -> dict[str, int]:
    text = clean_space(value).lower()
    scores = {"executive": 0, "technical": 0, "quality": 0, "senior": 0}
    patterns = {
        "executive": [
            (r"\b(chief executive officer|ceo|co[- ]?founder|founder)\b", 100),
            (r"\b(chief financial officer|cfo|chief operating officer|coo|president|managing director)\b", 92),
            (r"\bchief technology officer\b|\bcto\b", 85),
        ],
        "technical": [
            (r"\bchief technology officer\b|\bcto\b", 100),
            (r"\b(vp|vice president|head|director|chief)\b.{0,35}\b(r&d|research|engineering|technology|technical|product|innovation|science)\b", 92),
            (r"\b(r&d|research and development|engineering|product development|innovation|technology)\b", 75),
        ],
        "quality": [
            (r"\b(vp|vice president|head|director|chief)\b.{0,35}\b(quality|qa|regulatory|compliance|quality systems?)\b", 100),
            (r"\b(quality assurance|quality systems?|regulatory affairs|compliance|qa)\b", 82),
        ],
        "senior": [(r"\b(chief|cxo|vp|vice president|head|director|founder|president|managing director|general manager)\b", 60)],
    }
    for bucket, rules in patterns.items():
        for pattern, score in rules:
            if re.search(pattern, text):
                scores[bucket] = max(scores[bucket], score)
    return scores


def _name_and_title(title: str, context: str = "") -> tuple[str, str]:
    parts = [clean_space(part) for part in re.split(r"\s+[|–—-]\s+", title) if clean_space(part)]
    parts = [part for part in parts if part.lower() != "linkedin"]
    name = _clean_person_name(parts[0]) if parts else ""
    role = parts[1] if len(parts) > 1 else clean_space(context)
    if role and len(role) > 180:
        role = role[:177].rstrip() + "..."
    return name, role


def contact_from_official_observation(item: LinkObservation, company: str, website: str) -> LinkedInContact | None:
    url = canonicalize_linkedin_url(item.url, "person")
    if not url:
        return None
    name = _clean_person_name(item.anchor_text)
    context = clean_space(item.context)
    if not name:
        name = _name_from_profile_url(url)
    chunks = [clean_space(chunk) for chunk in context.split("|") if clean_space(chunk)]
    title = max(
        chunks,
        key=lambda chunk: (max(_title_role_scores(chunk).values()), -abs(len(chunk) - 35)),
        default=context,
    )
    scores = _title_role_scores(title)
    if not name or max(scores.values()) == 0:
        return None
    role_bucket = max(("executive", "technical", "quality", "senior"), key=lambda key: scores[key])
    return LinkedInContact(name, title[:180], url, role_bucket, "Official company site", 0.95)


def _contact_from_search_hit(hit: PublicSearchHit, company: str, website: str) -> LinkedInContact | None:
    url = canonicalize_linkedin_url(hit.url, "person")
    context = clean_space(f"{hit.title} {hit.snippet}")
    if not url or not company_name_matches(company, context, website):
        return None
    name, title = _name_and_title(hit.title, hit.snippet)
    scores = _title_role_scores(f"{title} {hit.snippet}")
    if not name or max(scores.values()) == 0:
        return None
    role_bucket = max(("executive", "technical", "quality", "senior"), key=lambda key: scores[key])
    return LinkedInContact(name, title, url, role_bucket, "Public search result", 0.8)


def select_contacts(candidates: list[LinkedInContact]) -> tuple[LinkedInContact | None, LinkedInContact | None, LinkedInContact | None]:
    deduped: dict[str, LinkedInContact] = {}
    for candidate in candidates:
        current = deduped.get(candidate.url)
        if current is None or candidate.confidence > current.confidence:
            deduped[candidate.url] = candidate
    pool = list(deduped.values())
    used: set[str] = set()
    selected: dict[str, LinkedInContact | None] = {"executive": None, "technical": None, "quality": None}
    for bucket in ("executive", "technical", "quality"):
        ranked = sorted(
            (item for item in pool if item.url not in used),
            key=lambda item: (_title_role_scores(item.title).get(bucket, 0), item.confidence),
            reverse=True,
        )
        if ranked and _title_role_scores(ranked[0].title).get(bucket, 0) > 0:
            selected[bucket] = ranked[0]
            used.add(ranked[0].url)
    for bucket in ("executive", "technical", "quality"):
        if selected[bucket] is not None:
            continue
        fallbacks = sorted(
            (item for item in pool if item.url not in used and _title_role_scores(item.title)["senior"] > 0),
            key=lambda item: (_title_role_scores(item.title)["senior"], item.confidence),
            reverse=True,
        )
        if fallbacks:
            selected[bucket] = fallbacks[0]
            used.add(fallbacks[0].url)
    return selected["executive"], selected["technical"], selected["quality"]


def _company_search_url(company: str, website: str, search_fn) -> tuple[str, str | None]:
    hits, error = search_fn(f'site:linkedin.com/company "{company}"')
    for hit in hits:
        url = canonicalize_linkedin_url(hit.url, "company")
        if url and company_name_matches(company, hit.title, website):
            return url, None
    return "", error


def _contact_search_candidates(company: str, website: str, search_fn) -> tuple[list[LinkedInContact], list[str]]:
    queries = [
        f'site:linkedin.com/in "{company}" CEO CTO quality R&D',
        f'site:linkedin.com/in "{company}" (CEO OR founder OR CFO OR COO)',
        f'site:linkedin.com/in "{company}" (CTO OR engineering OR research OR product)',
        f'site:linkedin.com/in "{company}" (quality OR QA OR regulatory OR compliance)',
    ]
    candidates: list[LinkedInContact] = []
    errors: list[str] = []
    for query in queries:
        hits, error = search_fn(query)
        if error:
            errors.append(error)
        for hit in hits:
            candidate = _contact_from_search_hit(hit, company, website)
            if candidate:
                candidates.append(candidate)
        if all(select_contacts(candidates)):
            break
    return candidates, errors


def enrich_company_linkedin(
    record: CompanyRecord,
    include_contacts: bool,
    search_fn=duckduckgo_search,
    fetch_fn=fetch_raw_text,
) -> LinkedInEnrichment:
    enrichment = LinkedInEnrichment(contact_status="No verified matches" if include_contacts else "Not targeted")
    official_observations: list[LinkObservation] = []
    website_error: str | None = None
    if record.website.startswith(("http://", "https://")):
        raw_html, website_error = fetch_fn(record.website)
        if not website_error:
            home_links = extract_page_links(raw_html, record.website)
            official_observations.extend(home_links)
            enrichment.company_url = _company_url_from_observations(home_links)
            for team_url in _team_page_urls(home_links, record.website) if include_contacts else []:
                team_html, _ = fetch_fn(team_url)
                if team_html:
                    official_observations.extend(extract_page_links(team_html, team_url))
    if enrichment.company_url:
        enrichment.company_status = "Found - official website"
    else:
        company_url, search_error = _company_search_url(record.company, record.website, search_fn)
        enrichment.company_url = company_url
        if company_url:
            enrichment.company_status = "Found - public search"
        elif search_error or website_error:
            enrichment.company_status = "Search error" if search_error else "Not found"
        else:
            enrichment.company_status = "Not found"

    if not include_contacts:
        return enrichment

    candidates = [
        candidate
        for candidate in (contact_from_official_observation(item, record.company, record.website) for item in official_observations)
        if candidate is not None
    ]
    executive, technical, quality = select_contacts(candidates)
    errors: list[str] = []
    if not all((executive, technical, quality)):
        search_candidates, errors = _contact_search_candidates(record.company, record.website, search_fn)
        candidates.extend(search_candidates)
        executive, technical, quality = select_contacts(candidates)
    enrichment.executive = executive
    enrichment.technical = technical
    enrichment.quality = quality
    count = sum(item is not None for item in (executive, technical, quality))
    if count == 3:
        enrichment.contact_status = "Complete - 3 verified"
    elif count:
        enrichment.contact_status = f"Partial - {count}/3 verified"
    elif errors:
        enrichment.contact_status = "Search error"
    else:
        enrichment.contact_status = "No verified matches"
    return enrichment


def _cache_path(record: CompanyRecord, include_contacts: bool) -> Path:
    raw = json.dumps(
        {
            "company": record.company,
            "website": record.website,
            "include_contacts": include_contacts,
            "version": LINKEDIN_ENRICHMENT_CACHE_VERSION,
        },
        sort_keys=True,
    )
    return Path(LINKEDIN_ENRICHMENT_CACHE_DIR) / f"{hashlib.sha256(raw.encode('utf-8')).hexdigest()}.json"


def _contact_from_dict(value: dict | None) -> LinkedInContact | None:
    if not isinstance(value, dict):
        return None
    required = {"name", "title", "url", "role_bucket", "source", "confidence"}
    if not required.issubset(value):
        return None
    return LinkedInContact(
        name=str(value["name"]),
        title=str(value["title"]),
        url=str(value["url"]),
        role_bucket=str(value["role_bucket"]),
        source=str(value["source"]),
        confidence=float(value["confidence"]),
    )


def load_cached_linkedin_enrichment(record: CompanyRecord, include_contacts: bool) -> LinkedInEnrichment | None:
    path = _cache_path(record, include_contacts)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return LinkedInEnrichment(
        company_url=str(payload.get("company_url", "")),
        company_status=str(payload.get("company_status", "Not researched")),
        executive=_contact_from_dict(payload.get("executive")),
        technical=_contact_from_dict(payload.get("technical")),
        quality=_contact_from_dict(payload.get("quality")),
        contact_status=str(payload.get("contact_status", "Not targeted")),
    )


def save_cached_linkedin_enrichment(record: CompanyRecord, include_contacts: bool, enrichment: LinkedInEnrichment) -> None:
    path = _cache_path(record, include_contacts)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(enrichment), indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        return


def enrich_companies_linkedin(companies: dict[str, CompanyRecord], target_year_fn) -> dict[str, int]:
    disabled = os.environ.get(LINKEDIN_ENRICHMENT_DISABLED_ENV, "").strip().lower() in {"1", "true", "yes", "on"}
    metrics = {"companies": len(companies), "company_urls": 0, "targeted": 0, "complete": 0, "partial": 0, "empty": 0}
    for record in companies.values():
        include_contacts = bool(target_year_fn(record))
        if include_contacts:
            metrics["targeted"] += 1
        if disabled:
            record.linkedin = LinkedInEnrichment(
                company_status="Disabled",
                contact_status="Search error" if include_contacts else "Not targeted",
            )
            continue
        cached = load_cached_linkedin_enrichment(record, include_contacts)
        record.linkedin = cached or enrich_company_linkedin(record, include_contacts)
        has_transient_error = record.linkedin.company_status == "Search error" or record.linkedin.contact_status == "Search error"
        if cached is None and not has_transient_error:
            save_cached_linkedin_enrichment(record, include_contacts, record.linkedin)
        if record.linkedin.company_url:
            metrics["company_urls"] += 1
        if include_contacts:
            if record.linkedin.contact_status.startswith("Complete"):
                metrics["complete"] += 1
            elif record.linkedin.contact_status.startswith("Partial"):
                metrics["partial"] += 1
            else:
                metrics["empty"] += 1
    return metrics
