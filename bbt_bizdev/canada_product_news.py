from __future__ import annotations

import hashlib
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen

from bbt_bizdev.canada_consolidation import normalize_name


USER_AGENT = "BBT-Canada-Product-Enrichment/1.0 (+research; evidence-bound)"
PRODUCT_CATEGORIES = {
    "diagnostics": r"\b(diagnostic|assay|biomarker|screening|pathology|imaging|genotyping|genetic test)\b",
    "SaMD": r"\b(samd|software as a medical device|clinical software|digital therapeutic)\b",
    "digital health": r"\b(digital health|telehealth|remote monitoring|virtual care)\b",
    "medical device": r"\b(medical device|device|implant|catheter|trocar|surgical|robot|prosthe|wearable|sensor)\b",
    "therapeutics": r"\b(therapeutic|therapies|pharmaceutical|biopharmaceutical|drug|medicine|medicines|treatment|molecule|vaccine|antibody|cell therapy|gene therapy)\b",
    "biotech platform": r"\b(biotech|drug discovery|discovery platform|omics|bioinformatics)\b",
    "research tools": r"\b(research tool|laboratory|lab automation|reagent|sequencing)\b",
}
EVENT_PATTERNS = (
    ("regulatory approval", r"\b(approved|approval|cleared|clearance|licensed|ce mark)\b"),
    ("regulatory submission claim", r"\b(submission|submitted|files? for|510\(k\)|de novo)\b"),
    ("clinical study", r"\b(clinical trial|clinical study|patient enrollment|first patient)\b"),
    ("validation", r"\b(validation|validated|verification|performance study)\b"),
    ("product launch", r"\b(launch(?:es|ed)?|commercially available|introduces?|unveils?)\b"),
    ("prototype", r"\b(prototype|proof of concept|proof-of-concept)\b"),
    ("manufacturing", r"\b(manufactur|design transfer|scale[- ]up|production)\b"),
    ("partnership", r"\b(partner|partnership|collaboration|licensing agreement|deployment|pilot)\b"),
    ("patent", r"\b(patent|intellectual property)\b"),
    ("funding", r"\b(raises?|raised|financing|funding|grant|investment|series [a-f]|seed round)\b"),
    ("acquisition", r"\b(acquir|acquisition|merger)\b"),
)
STAGE_PATTERNS = (
    ("launch", r"\b(launch(?:es|ed)?|commercially available|marketed)\b"),
    ("regulatory", r"\b(regulatory|submission|510\(k\)|de novo|clearance|approval|ce mark)\b"),
    ("validation", r"\b(validation|verification|performance study)\b"),
    ("clinical", r"\b(clinical|patient enrollment|first patient)\b"),
    ("preclinical", r"\b(preclinical|animal study|in vivo|in vitro)\b"),
    ("prototype", r"\b(prototype|proof of concept|proof-of-concept)\b"),
    ("scale-up", r"\b(scale[- ]up|design transfer|manufactur|production)\b"),
    ("research", r"\b(research|discovery|investigational)\b"),
)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.text_parts: list[str] = []
        self.title = ""
        self.description = ""
        self._href = ""
        self._anchor: list[str] = []
        self._in_title = False
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag == "a":
            self._href = values.get("href") or ""
            self._anchor = []
        if tag == "meta":
            key = (values.get("name") or values.get("property") or "").casefold()
            if key in {"description", "og:description"} and not self.description:
                self.description = clean(values.get("content"))

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._href:
            self.links.append((self._href, clean(" ".join(self._anchor))))
            self._href = ""
            self._anchor = []

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        value = clean(data)
        if not value:
            return
        self.text_parts.append(value)
        if self._in_title:
            self.title = clean(f"{self.title} {value}")
        if self._href:
            self._anchor.append(value)


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def fetch_html(url: str, timeout: int = 20) -> tuple[str, str, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            if "html" not in content_type.casefold():
                return "", response.geturl(), f"unsupported content type: {content_type}"
            raw = response.read(1_500_000).decode("utf-8", errors="replace")
            return raw, response.geturl(), ""
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return "", url, f"{type(exc).__name__}: {clean(exc)[:180]}"


def parse_page(raw_html: str, base_url: str) -> dict[str, Any]:
    parser = PageParser()
    try:
        parser.feed(raw_html)
    except Exception:
        pass
    links = []
    for href, anchor in parser.links:
        absolute = urljoin(base_url, href)
        if urlparse(absolute).scheme in {"http", "https"}:
            links.append((absolute.split("#", 1)[0], anchor))
    return {
        "title": parser.title,
        "description": parser.description,
        "text": clean(" ".join(parser.text_parts)),
        "links": links,
    }


def same_site(url: str, website: str) -> bool:
    left = (urlparse(url).hostname or "").casefold().removeprefix("www.")
    right = (urlparse(website).hostname or "").casefold().removeprefix("www.")
    return bool(left and right) and (left == right or left.endswith("." + right) or right.endswith("." + left))


def rank_company_links(links: list[tuple[str, str]], website: str, limit: int = 5) -> list[dict[str, Any]]:
    patterns = (
        ("product", 100, r"\b(products?|solutions?|devices?|platform|technology|pipeline|programs?)\b"),
        ("clinical", 90, r"\b(clinical|trials?|studies|evidence|validation)\b"),
        ("newsroom", 80, r"\b(news|newsroom|press|media|updates|blog)\b"),
    )
    ranked, seen = [], set()
    for url, anchor in links:
        key = url.rstrip("/").casefold()
        if key in seen or not same_site(url, website):
            continue
        seen.add(key)
        haystack = clean(f"{anchor} {urlparse(url).path.replace('-', ' ').replace('_', ' ')}").casefold()
        if re.search(r"\b(privacy|terms|cookie|login|careers?|jobs?|contact)\b", haystack):
            continue
        for page_type, score, pattern in patterns:
            if re.search(pattern, haystack):
                depth = max(0, urlparse(url).path.strip("/").count("/") - 1)
                ranked.append({"url": url, "anchor": anchor, "page_type": page_type, "score": score - depth * 5})
                break
    ranked.sort(key=lambda row: (-row["score"], row["url"]))
    selected, types = [], set()
    for row in ranked:
        if row["page_type"] not in types:
            selected.append(row)
            types.add(row["page_type"])
    for row in ranked:
        if row not in selected:
            selected.append(row)
    return selected[:limit]


def infer_product_category(text: str, fallback: str = "") -> str:
    value = text.casefold()
    scores = {
        category: len(re.findall(pattern, value))
        for category, pattern in PRODUCT_CATEGORIES.items()
    }
    best = max(scores, key=scores.get, default="")
    return best if best and scores[best] else fallback


def infer_stage(text: str) -> str:
    value = text.casefold()
    for stage, pattern in STAGE_PATTERNS:
        if re.search(pattern, value):
            return stage
    return "unknown"


def classify_event(text: str) -> str:
    value = text.casefold()
    for event_type, pattern in EVENT_PATTERNS:
        if re.search(pattern, value):
            return event_type
    return ""


def extract_date(text: str) -> str | None:
    patterns = (
        r"\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b",
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+([0-3]?\d),?\s+(20\d{2})\b",
    )
    match = re.search(patterns[0], text, re.I)
    if match:
        year, month, day = map(int, match.groups())
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    match = re.search(patterns[1], text, re.I)
    if match:
        try:
            return datetime.strptime(" ".join(match.groups()), "%B %d %Y").date().isoformat()
        except ValueError:
            return None
    return None


def product_profile(company: dict[str, Any], page: dict[str, Any], url: str, captured_at: str) -> dict[str, Any] | None:
    source = clean(f"{page.get('title')} {page.get('description')} {page.get('text')}")
    if not identity_supported(company, page):
        return None
    product_signal = sum(len(re.findall(pattern, source.casefold())) for pattern in PRODUCT_CATEGORIES.values())
    if product_signal == 0:
        return None
    summary = clean(page.get("description"))
    if re.search(r"\b(skip to content|open menu|close menu|page excerpt|displayed for search results)\b", summary, re.I):
        summary = ""
    if not summary:
        sentences = re.split(r"(?<=[.!?])\s+", source)
        summary = next((
            item for item in sentences
            if 40 <= len(item) <= 400
            and infer_product_category(item)
            and not re.search(r"\b(skip to content|open menu|close menu)\b", item, re.I)
        ), "")
    category_context = clean(f"{company.get('company_name')} {page.get('title')} {summary}")
    category = infer_product_category(category_context)
    if not category:
        category = infer_product_category(source, company.get("product_category", ""))
    return {
        "company_id": company["company_id"],
        "company_name": company["company_name"],
        "product_category": category,
        "product_summary": summary[:500],
        "development_stage": infer_stage(clean(f"{page.get('title')} {summary}")),
        "evidence_url": url,
        "evidence_date": extract_date(source),
        "captured_at": captured_at,
        "source_type": "company",
        "confidence": "high",
        "extraction_method": "deterministic first-party page classification",
    }


def official_event(company: dict[str, Any], page: dict[str, Any], url: str, captured_at: str) -> dict[str, Any] | None:
    text = clean(f"{page.get('title')} {page.get('description')} {page.get('text')}")
    # Index pages commonly contain unrelated event terms and today's footer date.
    # Require both the material signal and date in page-level metadata.
    event_metadata = clean(f"{page.get('title')} {page.get('description')}")
    if is_generic_index_url(url) or not identity_supported(company, page):
        return None
    event_type = classify_event(event_metadata)
    event_date = extract_date(event_metadata)
    if not event_type or not event_date:
        return None
    title = clean(page.get("title")) or company["company_name"]
    key = f"{company['company_id']}|{event_type}|{event_date}|{normalize_name(title)}"
    return {
        "evidence_id": hashlib.sha256(key.encode("utf-8")).hexdigest()[:24],
        "company_id": company["company_id"],
        "track": "product_development" if event_type not in {"funding", "acquisition"} else "news",
        "claim_type": event_type,
        "event_date": event_date,
        "event_type": event_type,
        "title": title[:300],
        "summary": clean(page.get("description"))[:500],
        "product_or_program": "",
        "development_stage": infer_stage(text),
        "evidence_url": url,
        "evidence_date": event_date,
        "captured_at": captured_at,
        "source_type": "company",
        "confidence": "high",
        "extraction_method": "deterministic first-party page classification",
    }


def is_generic_index_url(url: str) -> bool:
    path = urlparse(url).path.casefold().rstrip("/")
    return path in {"", "/news", "/newsroom", "/press", "/media", "/blog", "/updates", "/articles"}


def identity_supported(company: dict[str, Any], page: dict[str, Any]) -> bool:
    material = normalize_name(clean(f"{page.get('title')} {page.get('description')} {page.get('text')}"))
    names = [company.get("company_name", ""), company.get("legal_name", ""), *(company.get("aliases") or [])]
    normalized = [normalize_name(name) for name in names if len(normalize_name(name)) >= 4]
    if any(name in material for name in normalized):
        return True
    website = urlparse(company.get("website", ""))
    if website.path.strip("/"):
        return False
    host = normalize_name((website.hostname or "").removeprefix("www.").split(".")[0])
    generic = {"medical", "health", "therapeutics", "technologies", "technology", "pharmaceuticals", "inc"}
    company_tokens = [token for token in normalize_name(company.get("company_name", "")).split() if token not in generic]
    # A product-led homepage may omit the legal name, but its official domain must
    # still have a distinctive company-name token.
    return any(len(token) >= 4 and token in host for token in company_tokens)


def google_news_url(company_name: str) -> str:
    query = f'"{company_name}" (launch OR product OR platform OR clinical OR validation OR partnership)'
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=en-CA&gl=CA&ceid=CA:en"


def parse_google_news(company: dict[str, Any], raw: str, captured_at: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    names = [company.get("company_name", ""), company.get("legal_name", ""), *(company.get("aliases") or [])]
    normalized_names = [normalize_name(name) for name in names if len(normalize_name(name)) >= 4]
    candidates = []
    for item in root.findall(".//item"):
        title = clean(item.findtext("title"))
        description = clean(re.sub(r"<[^>]+>", " ", item.findtext("description") or ""))
        material = clean(f"{title} {description}")
        normalized_material = normalize_name(material)
        if not normalized_names or not any(name in normalized_material for name in normalized_names):
            continue
        event_type = classify_event(material)
        if not event_type:
            continue
        published = clean(item.findtext("pubDate"))
        try:
            event_date = parsedate_to_datetime(published).date().isoformat()
        except (TypeError, ValueError, OverflowError):
            event_date = None
        candidates.append({
            "company_id": company["company_id"],
            "company_name": company["company_name"],
            "event_date": event_date,
            "event_type": event_type,
            "title": title,
            "summary": description[:500],
            "discovery_url": clean(item.findtext("link")),
            "publisher": clean(item.findtext("source")),
            "captured_at": captured_at,
            "freshness": (
                "recent_24_months"
                if event_date and (date.fromisoformat(captured_at) - date.fromisoformat(event_date)).days <= 731
                else "historical"
            ),
            "review_status": "manual_review",
            "notes": "RSS discovery candidate; verify identity and replace with primary evidence URL before acceptance.",
        })
    return candidates


def fetch_news(company: dict[str, Any], timeout: int = 20) -> tuple[list[dict[str, Any]], str, str]:
    url = google_news_url(company["company_name"])
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(750_000).decode("utf-8", errors="replace")
        return parse_google_news(company, raw, date.today().isoformat()), url, ""
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return [], url, f"{type(exc).__name__}: {clean(exc)[:180]}"


def provisional_priority(
    company: dict[str, Any],
    regulatory: dict[str, Any] | None = None,
    funding: dict[str, Any] | None = None,
) -> int:
    category = clean(company.get("product_category")).casefold()
    score = 0
    if re.search(r"medical device|diagnostic|samd", category):
        score += 25
    elif re.search(r"digital health|biotech|therapeutic|research tool", category):
        score += 15
    if company.get("website"):
        score += 10
    if company.get("product_summary"):
        score += 5
    score += min(20, int((regulatory or {}).get("regulatory_record_count") or 0) * 4)
    score += min(20, int((funding or {}).get("funding_event_count") or 0) * 4)
    score += min(10, int((funding or {}).get("funding_backing_count") or 0) * 2)
    if company.get("canada_relationship") == "HQ":
        score += 5
    return score


def _load_companies(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["companies"] if isinstance(payload, dict) else payload


def _by_id(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path or not path.exists():
        return {}
    return {row["company_id"]: row for row in _load_companies(path)}


def run_product_news_enrichment(
    companies_path: Path,
    output_dir: Path,
    run_date: str,
    *,
    limit: int = 50,
    regulatory_path: Path | None = None,
    funding_path: Path | None = None,
    fetcher: Callable[[str, int], tuple[str, str, str]] = fetch_html,
    news_fetcher: Callable[[dict[str, Any], int], tuple[list[dict[str, Any]], str, str]] = fetch_news,
    delay: float = 0.2,
) -> dict[str, Any]:
    companies = _load_companies(companies_path)
    regulatory, funding = _by_id(regulatory_path), _by_id(funding_path)
    ranked = sorted(
        companies,
        key=lambda row: (
            -provisional_priority(row, regulatory.get(row["company_id"]), funding.get(row["company_id"])),
            row["company_name"].casefold(),
        ),
    )
    selected = [row for row in ranked if row.get("website")][:limit]
    profiles, events, news_candidates, checks = [], [], [], []
    dedupe_events: set[tuple[str, str, str, str]] = set()
    for company in selected:
        website = company["website"]
        raw, final_url, homepage_error = fetcher(website, 20)
        checked_urls, page_errors = [], []
        company_profiles, company_events = [], []
        pages: list[tuple[str, dict[str, Any], str]] = []
        if raw:
            homepage = parse_page(raw, final_url)
            pages.append((final_url, homepage, "homepage"))
            for candidate in rank_company_links(homepage["links"], final_url):
                child_raw, child_url, child_error = fetcher(candidate["url"], 20)
                if child_raw:
                    pages.append((child_url, parse_page(child_raw, child_url), candidate["page_type"]))
                elif child_error:
                    page_errors.append(f"{candidate['url']}: {child_error}")
                if delay:
                    time.sleep(delay)
        for url, page, page_type in pages:
            checked_urls.append(url)
            if page_type in {"homepage", "product", "clinical"}:
                profile = product_profile(company, page, url, run_date)
                if profile:
                    company_profiles.append(profile)
            if page_type in {"newsroom", "clinical", "product"}:
                event = official_event(company, page, url, run_date)
                if event:
                    event_key = (event["company_id"], event["event_type"], event["event_date"], normalize_name(event["title"]))
                    if event_key not in dedupe_events:
                        dedupe_events.add(event_key)
                        company_events.append(event)
        if company_profiles:
            company_profiles.sort(key=lambda row: (row["evidence_url"] != final_url, -len(row["product_summary"])))
            profiles.append(company_profiles[0])
        events.extend(company_events)
        candidates, news_url, news_error = news_fetcher(company, 20)
        news_candidates.extend(candidates)
        product_status = "complete_matches" if company_profiles else ("blocked" if homepage_error else "complete_zero")
        news_status = "complete_matches" if candidates else ("blocked" if news_error else "complete_zero")
        checks.append({
            "company_id": company["company_id"],
            "company_name": company["company_name"],
            "provisional_priority_score": provisional_priority(
                company, regulatory.get(company["company_id"]), funding.get(company["company_id"])
            ),
            "checked_urls": checked_urls,
            "product_development": {
                "status": product_status,
                "attempted_at": run_date,
                "source_url": final_url if raw else website,
                "raw_count": len(pages),
                "accepted_count": (1 if company_profiles else 0) + len(company_events),
                "notes": "; ".join(([homepage_error] if homepage_error else []) + page_errors)[:1000],
            },
            "news": {
                "status": news_status,
                "attempted_at": run_date,
                "source_url": news_url,
                "raw_count": len(candidates),
                "accepted_count": 0,
                "notes": (news_error or "Candidates require primary-source verification before acceptance.")[:1000],
            },
        })
        if delay:
            time.sleep(delay)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "product_profiles.json": {"schema_version": "1.0", "generated_at": run_date, "profiles": profiles},
        "product_news_events.json": {"schema_version": "1.0", "generated_at": run_date, "events": events},
        "news_candidates.json": {"schema_version": "1.0", "generated_at": run_date, "candidates": news_candidates},
        "product_news_completeness.json": {"schema_version": "1.0", "generated_at": run_date, "companies": checks},
    }
    for filename, payload in artifacts.items():
        (output_dir / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "run_date": run_date,
        "companies_selected": len(selected),
        "product_profiles": len(profiles),
        "accepted_official_events": len(events),
        "news_candidates_for_review": len(news_candidates),
        "product_status_counts": dict(_counts(row["product_development"]["status"] for row in checks)),
        "news_status_counts": dict(_counts(row["news"]["status"] for row in checks)),
        "selection_method": "provisional WP5 priority score; official 100-point model is not yet consolidated",
    }
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _counts(values: Any) -> dict[str, int]:
    counts: defaultdict[str, int] = defaultdict(int)
    for value in values:
        counts[value] += 1
    return dict(sorted(counts.items()))
