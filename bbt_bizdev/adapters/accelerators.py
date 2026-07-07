from __future__ import annotations

import json
import re
from urllib.parse import urlencode, urljoin, urlparse

from ..config import (
    ACCELERATOR_SOURCE_PAGES,
    MEDTECH_INNOVATOR_PORY_APP_URL, MEDTECH_INNOVATOR_PORY_RECORDS_URL, MAYO_READER_PREFIX,
    YC_ALGOLIA_API_KEY, YC_ALGOLIA_APP_ID, YC_HEALTHCARE_QUERY,
)
from ..http import fetch_json, fetch_json_url, fetch_raw_text
from ..models import DiscoveryHit, Source, TriggerEvent
from ..models import TODAY
from ..text import clean_page_candidate, clean_text, extract_links, infer_page_product_type, infer_yc_product_type, is_plausible_page_candidate, is_relevant_candidate_link, source_type_trigger_event, text_from_html


def yc_company_url(hit: dict) -> str:
    if hit.get("ycdc_company_url"):
        return hit["ycdc_company_url"]
    slug = hit.get("slug") or hit.get("objectID")
    return f"https://www.ycombinator.com/companies/{slug}" if slug else "https://www.ycombinator.com/companies"

def infer_yc_batch_year(batch: str) -> str:
    year = infer_cohort_year(batch)
    if year:
        return year
    match = re.search(r"\b[WSF](\d{2})\b", batch or "", flags=re.I)
    return f"20{match.group(1)}" if match else ""

def run_yc_healthcare(source: Source, max_hits: int = 1000) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    endpoint = f"https://{YC_ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/YCCompany_production/query"
    hits: list[dict] = []
    page = 0
    nb_hits = 0
    while len(hits) < max_hits:
        payload = {"query": YC_HEALTHCARE_QUERY, "hitsPerPage": 100, "page": page}
        data, error = fetch_json(endpoint, payload)
        if error:
            return [], [], f"YC Algolia fetch failed: {error}"
        nb_hits = int(data.get("nbHits") or 0)
        page_hits = data.get("hits") or []
        hits.extend(page_hits)
        if page >= int(data.get("nbPages") or 0) - 1 or not page_hits:
            break
        page += 1

    hits = sorted(hits[:max_hits], key=lambda item: item.get("launched_at") or 0, reverse=True)
    discovery_hits: list[DiscoveryHit] = []
    trigger_events: list[TriggerEvent] = []
    seen: set[str] = set()
    for hit in hits:
        company = clean_page_candidate(hit.get("name") or "")
        if not company or company.lower() in seen:
            continue
        seen.add(company.lower())
        url = yc_company_url(hit)
        tags = ", ".join(hit.get("tags") or [])
        batch = hit.get("batch") or hit.get("batch_name") or ""
        cohort_year = infer_yc_batch_year(batch)
        description = hit.get("one_liner") or hit.get("long_description") or ""
        matched = f"query: {YC_HEALTHCARE_QUERY}; batch: {batch}; tags: {tags}".strip("; ")
        discovery_hits.append(
            DiscoveryHit(
                company=company,
                source_name=f"{source.name}: {YC_HEALTHCARE_QUERY} search",
                source_type=source.source_type,
                discovery_url=url,
                discovery_rationale=f"YC company directory search for '{YC_HEALTHCARE_QUERY}', sorted by launch date, returned this company.",
                product_type=infer_yc_product_type(f"{description} {tags}"),
                geography=hit.get("all_locations") or hit.get("location") or source.geography,
                website=hit.get("website") or "",
                matched_terms=matched,
                accelerator_program="Y Combinator",
                cohort_label=f"Y Combinator {batch}".strip(),
                cohort_year=cohort_year,
                company_description=description,
            )
        )
        trigger = source_type_trigger_event(source, company)
        if trigger:
            trigger_events.append(TriggerEvent(company, trigger[0], trigger[1], f"{source.name}: {YC_HEALTHCARE_QUERY} search", url))
    return discovery_hits, trigger_events, f"YC Algolia query '{YC_HEALTHCARE_QUERY}'; {nb_hits} matches; {len(discovery_hits)} discovery hits"

def infer_cohort_year(*values: str) -> str:
    for value in values:
        match = re.search(r"\b(20\d{2})\b", value or "")
        if match:
            return match.group(1)
    return ""

def infer_accelerator_product_type(context: str) -> str:
    text = context.lower()
    if any(term in text for term in ["medical device", "medtech", "device"]):
        return "Medical device / medtech"
    if any(term in text for term in ["diagnostic", "imaging", "radiology", "biomarker"]):
        return "Diagnostics / imaging"
    if any(term in text for term in ["ehr", "workflow", "provider", "hospital", "clinical workflow"]):
        return "Healthcare operations / IT"
    if any(term in text for term in ["ai", "machine learning", "artificial intelligence"]):
        return "AI health"
    if any(term in text for term in ["digital health", "virtual care", "remote monitoring", "platform"]):
        return "Digital health"
    if any(term in text for term in ["therapeutic", "biotech", "pharma", "drug"]):
        return "Biotech / therapeutics"
    return "Accelerator company"

def accelerator_trigger(source: Source, hit: DiscoveryHit) -> TriggerEvent | None:
    trigger = source_type_trigger_event(source, hit.company)
    if not trigger:
        return None
    detail = trigger[1]
    if hit.cohort_label:
        detail = f"{hit.company} appeared in {hit.cohort_label} for '{source.name}'."
    return TriggerEvent(hit.company, trigger[0], detail, hit.source_name, hit.discovery_url)

def make_accelerator_hit(
    source: Source,
    company: str,
    evidence_url: str,
    *,
    accelerator_program: str | None = None,
    cohort_label: str = "",
    cohort_year: str = "",
    category_or_track: str = "",
    company_description: str = "",
    website: str = "",
    geography: str = "",
    matched_terms: str = "",
    trust_curated_name: bool = False,
) -> DiscoveryHit | None:
    company = clean_page_candidate(company)
    if not trust_curated_name and not is_plausible_page_candidate(company):
        return None
    context = " ".join([category_or_track, company_description, source.notes])
    rationale = f"{source.name} adapter extracted this company from an accelerator cohort/directory source."
    if cohort_label:
        rationale += f" Cohort/source label: {cohort_label}."
    return DiscoveryHit(
        company=company,
        source_name=source.name,
        source_type=source.source_type,
        discovery_url=evidence_url,
        discovery_rationale=rationale,
        product_type=infer_accelerator_product_type(context),
        geography=geography or source.geography,
        website=website,
        matched_terms=matched_terms or f"adapter: {source.adapter}",
        accelerator_program=accelerator_program or source.name,
        cohort_label=cohort_label,
        cohort_year=cohort_year,
        category_or_track=category_or_track,
        company_description=company_description,
    )

def dedupe_hits_with_triggers(source: Source, hits: list[DiscoveryHit]) -> tuple[list[DiscoveryHit], list[TriggerEvent]]:
    deduped: list[DiscoveryHit] = []
    triggers: list[TriggerEvent] = []
    seen: set[tuple[str, str]] = set()
    for hit in hits:
        key = (hit.company.lower(), hit.discovery_url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
        trigger = accelerator_trigger(source, hit)
        if trigger:
            triggers.append(trigger)
    return deduped, triggers

def extract_meta_description(raw_html: str) -> str:
    patterns = [
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_html, flags=re.I | re.S)
        if match:
            return clean_text(match.group(1))
    paragraphs = re.findall(r"<p\b[^>]*>(.*?)</p>", raw_html, flags=re.I | re.S)
    for paragraph in paragraphs:
        text = clean_text(paragraph)
        if len(text) >= 30:
            return text
    return ""

def context_after_link(raw_html: str, href: str, window: int = 1200) -> str:
    idx = raw_html.find(href)
    if idx < 0:
        return ""
    return text_from_html(raw_html[idx : idx + window])

def context_around_link_text(raw_html: str, link_text: str, window: int = 1200) -> str:
    idx = raw_html.lower().find(link_text.lower())
    if idx < 0:
        return ""
    start = max(0, idx - window // 4)
    return text_from_html(raw_html[start : idx + window])

def context_for_priority_link_block(raw_html: str, link_text: str, window: int = 800) -> str:
    idx = raw_html.lower().find(link_text.lower())
    if idx < 0:
        return ""
    next_link_idx = raw_html.lower().find("<a ", idx + len(link_text))
    end = next_link_idx if next_link_idx >= 0 else idx + window
    return text_from_html(raw_html[idx:end])

def context_for_external_link_card(raw_html: str, link_text: str, window: int = 800) -> str:
    idx = raw_html.lower().find(link_text.lower())
    if idx < 0:
        return ""
    previous_link_end = raw_html.lower().rfind("</a>", 0, idx)
    start = previous_link_end + len("</a>") if previous_link_end >= 0 else max(0, idx - window)
    current_link_end = raw_html.lower().find("</a>", idx)
    end = current_link_end + len("</a>") if current_link_end >= 0 else idx + window
    return text_from_html(raw_html[start:end])

def normalize_priority_company_candidate(link_text: str) -> str:
    candidate = clean_page_candidate(link_text)
    by_match = re.search(
        r"\bBy\s+(.+?)(?:\s+(?:is|are|has|have|helps|offers|provides|produces|uses|allows|connects|develops|developed|designed|gives|enables)\b|$)",
        candidate,
        flags=re.I,
    )
    if by_match:
        product = clean_page_candidate(candidate.split(" By ", 1)[0])
        candidate = clean_page_candidate(by_match.group(1))
        candidate = re.sub(r"^The\s+", "", candidate, flags=re.I)
        if product and candidate.lower().endswith(" " + product.lower()):
            candidate = candidate[: -len(product)].strip()
        candidate = re.sub(r"\s+The\s+", " ", candidate, flags=re.I)
        words = candidate.split()
        if len(words) >= 2 and len(words) % 2 == 0:
            half = len(words) // 2
            if " ".join(words[:half]).lower() == " ".join(words[half:]).lower():
                candidate = " ".join(words[:half])
    if candidate and candidate[0].islower() and re.search(r"[A-Z]", candidate[1:]):
        candidate = candidate[:1].upper() + candidate[1:]
    return candidate

def is_priority_accelerator_company_link(source: Source, link_text: str, href: str) -> bool:
    lower_text = clean_text(link_text).lower()
    if lower_text in {"portfolio", "case studies", "supports", "initiatives", "innovation supports", "innovation tools", "alumni", "bioinnovate alumni", "alumni directory", "expand all", "logo", "aa", "anormal", "alarger", "ahigh contrast"}:
        return False
    if "go to page" in lower_text:
        return False
    if not is_plausible_page_candidate(normalize_priority_company_candidate(link_text)):
        return False
    lower_href = href.lower()
    if lower_href.startswith(("javascript:", "mailto:", "tel:")) or "#" in lower_href:
        return False
    if any(term in lower_href for term in ["contact", "about", "team", "people", "event", "apply", "privacy", "login", "news/"]):
        return False
    path_terms = {
        "bioinnovate_ireland": ["compan", "alumni", "portfolio", "startup", "venture"],
        "arc_hub_healthtech": ["compan", "spin", "startup", "commercial", "portfolio", "/projects/"],
        "health_innovation_hub_ireland": ["/products/", "/case-studies/"],
        "dogpatch_ndrc": ["portfolio", "compan", "startup", "cohort", "alumni"],
    }
    terms = path_terms.get(source.adapter or "", ["compan", "startup", "portfolio"])
    return any(term in lower_href for term in terms)

def is_ndrc_external_company_link(href: str, page_url: str) -> bool:
    if "accelerator-cohort" not in page_url.lower():
        return False
    parsed = urlparse(href)
    host = parsed.netloc.lower().removeprefix("www.")
    if not host or host.endswith("ndrc.ie") or host.endswith("dogpatchlabs.com") or host.endswith("ndrc.click"):
        return False
    blocked_hosts = {"accelerator.ndrc.ie", "linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com", "youtube.com"}
    return not any(host == blocked or host.endswith("." + blocked) for blocked in blocked_hosts)

def company_from_ndrc_link(link_text: str, href: str) -> str:
    parsed = urlparse(href)
    host = parsed.netloc.removeprefix("www.")
    label = clean_text(link_text)
    if "." in label and len(label.split()) <= 3:
        label = host.split(".", 1)[0]
    elif not label:
        label = host.split(".", 1)[0]
    label = re.sub(r"[-_]+", " ", label)
    label = re.sub(r"\b(?:website|site)\b", "", label, flags=re.I)
    return clean_page_candidate(label.title())

NDRC_HEALTHCARE_KEYWORDS = [
    "health",
    "healthcare",
    "medical",
    "clinical",
    "patient",
    "care",
    "medtech",
    "medical device",
    "device",
    "diagnostic",
    "diagnostics",
    "imaging",
    "wearable",
    "remote monitoring",
    "digital health",
    "healthtech",
    "telehealth",
    "virtual care",
    "samd",
    "clinical workflow",
    "ehr",
    "hospital",
    "biotech",
    "life sciences",
    "therapeutic",
    "pharma",
    "pharmaceutical",
    "drug discovery",
    "genomics",
    "biomarker",
    "mental health",
    "women's health",
    "womens health",
    "elderly care",
    "rehab",
    "physiotherapy",
    "nutrition",
]

def matched_ndrc_healthcare_keywords(context: str) -> list[str]:
    text = clean_text(context).lower()
    matched: list[str] = []
    for keyword in NDRC_HEALTHCARE_KEYWORDS:
        if " " in keyword:
            found = keyword in text
        else:
            found = re.search(rf"\b{re.escape(keyword)}\b", text) is not None
        if found:
            matched.append(keyword)
    return matched

def parse_priority_accelerator_page(source: Source, raw_html: str, page_url: str, cohort_label: str = "") -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    page_text = text_from_html(raw_html)
    default_cohort = cohort_label or f"{source.name} {infer_cohort_year(page_text, page_url)}".strip()
    for link_text, href in extract_links(raw_html, page_url):
        ndrc_external_link = source.adapter == "dogpatch_ndrc" and is_ndrc_external_company_link(href, page_url)
        if not ndrc_external_link and not is_priority_accelerator_company_link(source, link_text, href):
            continue
        company = company_from_ndrc_link(link_text, href) if ndrc_external_link else normalize_priority_company_candidate(link_text)
        if not is_plausible_page_candidate(company):
            continue
        context = context_for_external_link_card(raw_html, link_text) if ndrc_external_link else context_after_link(raw_html, href) or context_around_link_text(raw_html, link_text)
        matched_terms = f"adapter: {source.adapter}; company/startup link"
        if source.adapter == "dogpatch_ndrc":
            healthcare_context = context if ndrc_external_link else context_for_priority_link_block(raw_html, link_text) or context
            healthcare_keywords = matched_ndrc_healthcare_keywords(" ".join([company, healthcare_context]))
            if not healthcare_keywords:
                continue
            matched_terms = f"{matched_terms}; healthcare keywords: {', '.join(healthcare_keywords)}"
        category = ""
        for label in ["Sector", "Category", "Track", "Programme", "Program"]:
            match = re.search(rf"{label}\s*:?\s*([A-Za-z0-9 /,&+-]{{3,80}})", context, flags=re.I)
            if match:
                category = clean_text(match.group(1))
                break
        hit = make_accelerator_hit(
            source,
            company,
            href,
            cohort_label=default_cohort,
            cohort_year=infer_cohort_year(default_cohort, context, page_url),
            category_or_track=category,
            company_description=context,
            matched_terms=matched_terms,
        )
        if hit:
            hits.append(hit)
    return hits

def run_priority_accelerator_pages(source: Source, incomplete_label: str = "priority accelerator") -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = ACCELERATOR_SOURCE_PAGES.get(source.name, [source.url])
    hits: list[DiscoveryHit] = []
    errors: list[str] = []
    scanned = 0
    for url in urls:
        raw_html, error = fetch_raw_text(url)
        scanned += 1
        if error:
            errors.append(f"{url}: {error}")
            continue
        hits.extend(parse_priority_accelerator_page(source, raw_html, url))
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{scanned} {incomplete_label} pages scanned; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if not hits:
        result = f"INCOMPLETE {source.name} extraction: no company/startup links found. " + result
    if errors:
        result += "; errors: " + " | ".join(errors)
    return hits, triggers, result

def bioinnovate_collection_urls(raw_html: str) -> list[str]:
    urls = re.findall(r"https://data\.shorthand\.com/[^\"'\\\s<>]+/items\.json", raw_html)
    return list(dict.fromkeys(urls))

def bioinnovate_embed_urls(raw_html: str) -> list[str]:
    urls = re.findall(r"https://stories\.universityofgalway\.ie/bioinnovate/start-ups/embed\.js", raw_html)
    return list(dict.fromkeys(urls))

def parse_bioinnovate_collection(source: Source, payload: object, collection_url: str) -> list[DiscoveryHit]:
    if not isinstance(payload, dict):
        return []
    hits: list[DiscoveryHit] = []
    collection_title = clean_text(str(payload.get("title") or "BioInnovate Alumni Companies"))
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        company = clean_page_candidate(str(item.get("title") or ""))
        if not company:
            continue
        description = clean_text(str(item.get("description") or ""))
        url = str(item.get("url") or collection_url)
        hit = make_accelerator_hit(
            source,
            company,
            url,
            cohort_label=collection_title,
            category_or_track="BioInnovate alumni",
            company_description=description,
            matched_terms="adapter: bioinnovate_ireland; shorthand alumni collection",
            trust_curated_name=True,
        )
        if hit:
            hit.website = url if url.startswith(("http://", "https://")) else ""
            hits.append(hit)
    return hits

def run_bioinnovate_ireland(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = ACCELERATOR_SOURCE_PAGES.get(source.name, [source.url])
    hits: list[DiscoveryHit] = []
    errors: list[str] = []
    scanned = 0
    collections_scanned = 0
    for url in urls:
        raw_html, error = fetch_raw_text(url)
        scanned += 1
        if error:
            errors.append(f"{url}: {error}")
            continue
        collection_urls = bioinnovate_collection_urls(raw_html)
        for embed_url in bioinnovate_embed_urls(raw_html):
            embed_html, embed_error = fetch_raw_text(embed_url)
            scanned += 1
            if embed_error:
                errors.append(f"{embed_url}: {embed_error}")
                continue
            collection_urls.extend(bioinnovate_collection_urls(embed_html))
        collection_urls = list(dict.fromkeys(collection_urls))
        if not collection_urls:
            hits.extend(parse_priority_accelerator_page(source, raw_html, url))
            continue
        for collection_url in collection_urls:
            payload, json_error = fetch_json_url(collection_url)
            collections_scanned += 1
            if json_error:
                errors.append(f"{collection_url}: {json_error}")
                continue
            hits.extend(parse_bioinnovate_collection(source, payload, collection_url))
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{scanned} BioInnovate pages scanned; {collections_scanned} alumni collections scanned; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if not hits:
        result = f"INCOMPLETE {source.name} extraction: no alumni companies found. " + result
    if errors:
        result += "; errors: " + " | ".join(errors)
    return hits, triggers, result


def run_arc_hub_healthtech(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    return run_priority_accelerator_pages(source, "ARC Hub")

def run_health_innovation_hub_ireland(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    return run_priority_accelerator_pages(source, "Health Innovation Hub Ireland")

def run_dogpatch_ndrc(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    return run_priority_accelerator_pages(source, "Dogpatch/NDRC")

EU_ACCELERATOR_COMPANY_PATH_TERMS = [
    "compan",
    "startup",
    "start-up",
    "portfolio",
    "venture",
    "alumni",
    "cohort",
    "resident",
    "member",
    "incubat",
    "accelerat",
    "project",
    "innovation",
]


def is_eu_accelerator_company_link(link_text: str, href: str) -> bool:
    lower_text = clean_text(link_text).lower()
    if lower_text in {
        "portfolio",
        "startups",
        "companies",
        "members",
        "alumni",
        "cohort",
        "apply",
        "learn more",
        "read more",
        "view all",
        "website",
        "linkedin",
    }:
        return False
    if not is_plausible_page_candidate(clean_page_candidate(link_text)):
        return False
    lower_href = href.lower()
    if lower_href.startswith(("javascript:", "mailto:", "tel:")) or "#" in lower_href:
        return False
    if any(term in lower_href for term in ["contact", "about", "team", "people", "event", "apply", "privacy", "login", "news/", "blog/"]):
        return False
    return any(term in lower_href for term in EU_ACCELERATOR_COMPANY_PATH_TERMS)


def eu_accelerator_has_health_relevance(source: Source, company: str, context: str) -> bool:
    company_context = " ".join([company, context]).lower()
    if matched_ndrc_healthcare_keywords(company_context) or re.search(r"\b(sa?md|medtech|medical devices?|healthtech|health tech|life sciences?)\b", company_context):
        return True
    if not clean_text(context):
        source_context = " ".join([source.name, source.notes]).lower()
        return bool(matched_ndrc_healthcare_keywords(source_context) or re.search(r"\b(sa?md|medtech|medical devices?|healthtech|health tech|life sciences?)\b", source_context))
    return False


def parse_eu_accelerator_json_records(source: Source, payload: object, page_url: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []

    def records(value: object) -> list[dict]:
        found: list[dict] = []
        if isinstance(value, list):
            for item in value:
                found.extend(records(item))
        elif isinstance(value, dict):
            if any(key in value for key in ["company", "name", "title", "post_title"]):
                found.append(value)
            for item in value.values():
                if isinstance(item, (list, dict)):
                    found.extend(records(item))
        return found

    for record in records(payload):
        title = record.get("company") or record.get("name") or record.get("post_title") or record.get("title") or ""
        if isinstance(title, dict):
            title = title.get("rendered") or title.get("name") or ""
        company = clean_page_candidate(str(title))
        if not is_plausible_page_candidate(company):
            continue
        description = " ".join(
            clean_text(str(value.get("rendered") if isinstance(value, dict) else value))
            for key, value in record.items()
            if key.lower() in {"description", "excerpt", "content", "summary", "sector", "category", "tags"}
        )
        url = str(record.get("url") or record.get("link") or record.get("website") or page_url)
        if not eu_accelerator_has_health_relevance(source, company, description):
            continue
        hit = make_accelerator_hit(
            source,
            company,
            url,
            cohort_label=f"{source.name} directory",
            company_description=description,
            website=url if url.startswith(("http://", "https://")) and urlparse(url).netloc not in urlparse(page_url).netloc else "",
            matched_terms="adapter: eu_accelerator_directory; json directory record",
        )
        if hit:
            hits.append(hit)
    return hits


def parse_eu_accelerator_directory_page(source: Source, raw_html: str, page_url: str) -> list[DiscoveryHit]:
    stripped = raw_html.strip()
    if stripped.startswith(("{", "[")):
        try:
            return parse_eu_accelerator_json_records(source, json.loads(stripped), page_url)
        except json.JSONDecodeError:
            pass

    hits: list[DiscoveryHit] = []
    default_cohort = f"{source.name} {infer_cohort_year(raw_html, page_url)}".strip()
    for link_text, href in extract_links(raw_html, page_url):
        if not is_eu_accelerator_company_link(link_text, href):
            continue
        company = normalize_priority_company_candidate(link_text)
        context = context_for_priority_link_block(raw_html, link_text) or context_after_link(raw_html, href) or context_around_link_text(raw_html, link_text)
        if not eu_accelerator_has_health_relevance(source, company, context):
            continue
        hit = make_accelerator_hit(
            source,
            company,
            href,
            cohort_label=default_cohort,
            cohort_year=infer_cohort_year(default_cohort, context, page_url),
            company_description=context,
            matched_terms="adapter: eu_accelerator_directory; company/startup link",
        )
        if hit:
            hits.append(hit)
    return hits


def run_eu_accelerator_directory(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = ACCELERATOR_SOURCE_PAGES.get(source.name, [source.url])
    hits: list[DiscoveryHit] = []
    errors: list[str] = []
    scanned = 0
    for url in urls:
        raw_html, error = fetch_raw_text(url)
        scanned += 1
        if error:
            errors.append(f"{url}: {error}")
            continue
        hits.extend(parse_eu_accelerator_directory_page(source, raw_html, url))
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{scanned} EU accelerator directory pages scanned; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if not hits:
        result = f"INCOMPLETE {source.name} extraction: no health-relevant company/startup links found. " + result
    if errors:
        result += "; errors: " + " | ".join(errors)
    return hits, triggers, result

def title_from_slug(slug: str) -> str:
    words = [word for word in re.split(r"[-_/]+", slug) if word]
    title = " ".join(word.upper() if word.lower() in {"ai", "xr", "nhs", "ml"} else word.capitalize() for word in words)
    replacements = {
        "Aido": "AIDO",
        "Pephealth": "PEP Health",
        "Ipd": "IPD",
        "Mladx": "ML Diagnostics",
        "Nicolab": "Nicolab",
        "Lumabs": "LUMICKS",
    }
    return replacements.get(title, title)

def company_from_nhs_innovation_link(link_text: str, href: str) -> str:
    slug = urlparse(href).path.strip("/").split("/")[-1]
    fallback = title_from_slug(slug)
    text = clean_page_candidate(link_text)
    candidate = re.split(
        r"\s+(?:is|are|supports|helps|provides|uses|offers|enables|develops|delivers|connects|aims|has|have|will|can|by)\b",
        text,
        maxsplit=1,
        flags=re.I,
    )[0]
    words = candidate.split()
    if len(words) >= 2 and len(words) % 2 == 0:
        half = len(words) // 2
        if " ".join(words[:half]).lower() == " ".join(words[half:]).lower():
            candidate = " ".join(words[:half])
    if 1 <= len(candidate.split()) <= 6 and is_plausible_page_candidate(candidate):
        return candidate
    return fallback

def parse_nhs_innovation_accelerator_page(source: Source, raw_html: str, page_url: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    seen: set[str] = set()
    for link_text, href in extract_links(raw_html, page_url):
        path = urlparse(href).path.rstrip("/") + "/"
        if "/innovations/" not in path or path == "/innovations/":
            continue
        company = company_from_nhs_innovation_link(link_text, href)
        if company.lower() in seen:
            continue
        seen.add(company.lower())
        context = context_after_link(raw_html, href) or context_around_link_text(raw_html, link_text)
        hit = make_accelerator_hit(
            source,
            company,
            href,
            cohort_label="NHS Innovation Accelerator innovations",
            company_description=context,
            matched_terms="adapter: nhs_innovation_accelerator; innovation profile link",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits

def run_nhs_innovation_accelerator(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = ACCELERATOR_SOURCE_PAGES.get(source.name, [source.url])
    hits: list[DiscoveryHit] = []
    errors: list[str] = []
    scanned = 0
    for url in urls:
        raw_html, error = fetch_raw_text(url)
        scanned += 1
        if error:
            errors.append(f"{url}: {error}")
            continue
        hits.extend(parse_nhs_innovation_accelerator_page(source, raw_html, url))
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{scanned} NHS innovation pages scanned; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if not hits:
        result = f"INCOMPLETE {source.name} extraction: no innovation profile links found. " + result
    if errors:
        result += "; errors: " + " | ".join(errors)
    return hits, triggers, result

NLC_HOST_COMPANY_NAMES = {
    "aido": "AIDO",
    "pephealth": "PEP Health",
    "mladx": "ML Diagnostics",
    "ipd": "IPD",
    "ncbiomatrix": "NC Biomatrix",
    "scinvivo": "SC Invivo",
}

def company_from_external_hostname(href: str) -> str:
    host = urlparse(href).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    label = host.split(".", 1)[0]
    if label in NLC_HOST_COMPANY_NAMES:
        return NLC_HOST_COMPANY_NAMES[label]
    return clean_page_candidate(title_from_slug(label))

def is_external_portfolio_website(href: str, source_url: str) -> bool:
    parsed = urlparse(href)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    source_host = urlparse(source_url).netloc.lower()
    host = parsed.netloc.lower()
    if source_host and host.endswith(source_host):
        return False
    if re.search(r"\.(?:png|jpe?g|webp|gif|svg|css|js|pdf)(?:$|\?)", parsed.path, flags=re.I):
        return False
    return not any(
        blocked in host
        for blocked in [
            "linkedin.com",
            "facebook.com",
            "twitter.com",
            "x.com",
            "instagram.com",
            "youtube.com",
            "loopia.com",
            "hubspot",
            "website-files.com",
            "webflow",
            "cdn",
        ]
    )

def parse_nlc_health_page(source: Source, raw_html: str, page_url: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    seen: set[str] = set()
    for link_text, href in extract_links(raw_html, page_url):
        if not is_external_portfolio_website(href, page_url):
            continue
        text_company = clean_page_candidate(link_text)
        if text_company.lower() in {"visit website", "website", "learn more", "read more"} or not is_plausible_page_candidate(text_company):
            company = company_from_external_hostname(href)
        else:
            company = text_company
        if company.lower() in {"investor login", "cdn", "assets", "privacy policy"}:
            continue
        if company.lower() in seen:
            continue
        seen.add(company.lower())
        context = context_after_link(raw_html, href) or context_for_external_link_card(raw_html, link_text)
        hit = make_accelerator_hit(
            source,
            company,
            page_url,
            cohort_label="NLC Health portfolio",
            company_description=context,
            website=href,
            matched_terms="adapter: nlc_health; external portfolio website",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits

def run_nlc_health(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = ACCELERATOR_SOURCE_PAGES.get(source.name, [source.url])
    hits: list[DiscoveryHit] = []
    errors: list[str] = []
    scanned = 0
    for url in urls:
        raw_html, error = fetch_raw_text(url)
        scanned += 1
        if error:
            errors.append(f"{url}: {error}")
            continue
        hits.extend(parse_nlc_health_page(source, raw_html, url))
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{scanned} NLC portfolio pages scanned; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if not hits:
        result = f"INCOMPLETE {source.name} extraction: no external portfolio websites found. " + result
    if errors:
        result += "; errors: " + " | ".join(errors)
    return hits, triggers, result

def parse_yesdelft_medtech_payload(source: Source, payload: object, page_url: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    if not isinstance(payload, list):
        return hits
    for record in payload:
        if not isinstance(record, dict):
            continue
        title = record.get("title") or {}
        company = title.get("rendered") if isinstance(title, dict) else title
        company = clean_page_candidate(str(company or ""))
        if not company:
            continue
        description = " ".join(
            clean_text(str(value.get("rendered") if isinstance(value, dict) else value))
            for key, value in record.items()
            if key.lower() in {"excerpt", "content", "description"}
        )
        url = clean_text(str(record.get("link") or page_url))
        hit = make_accelerator_hit(
            source,
            company,
            url,
            cohort_label="YES!Delft Health and Pharma startups",
            company_description=description,
            matched_terms="adapter: yesdelft_medtech; Health and Pharma WP JSON record",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits

def run_yesdelft_medtech(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = ACCELERATOR_SOURCE_PAGES.get(source.name, [source.url])
    hits: list[DiscoveryHit] = []
    errors: list[str] = []
    scanned = 0
    for url in urls:
        if "wp-json" in url:
            payload, error = fetch_json_url(url)
            scanned += 1
            if error:
                errors.append(f"{url}: {error}")
                continue
            hits.extend(parse_yesdelft_medtech_payload(source, payload, url))
            continue
        raw_html, error = fetch_raw_text(url)
        scanned += 1
        if error:
            errors.append(f"{url}: {error}")
            continue
        hits.extend(parse_eu_accelerator_directory_page(source, raw_html, url))
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{scanned} YES!Delft pages/endpoints scanned; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if not hits:
        result = f"INCOMPLETE {source.name} extraction: no Health and Pharma startup records found. " + result
    if errors:
        result += "; errors: " + " | ".join(errors)
    return hits, triggers, result

def names_from_bii_terms(record: dict, key: str) -> list[str]:
    values = record.get(key) or []
    if not isinstance(values, list):
        return []
    return [clean_text(str(item.get("name") or "")) for item in values if isinstance(item, dict) and item.get("name")]

def parse_bioinnovation_institute_payload(source: Source, payload: object, page_url: str) -> list[DiscoveryHit]:
    records = payload.get("projectItems") if isinstance(payload, dict) else []
    if not isinstance(records, list):
        return []
    hits: list[DiscoveryHit] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        focus_areas = names_from_bii_terms(record, "focusAreas")
        if focus_areas and not any(area.lower() == "human health" for area in focus_areas):
            continue
        company = clean_page_candidate(str(record.get("title") or ""))
        if not company:
            continue
        summary = clean_text(str(record.get("summary") or ""))
        programs = names_from_bii_terms(record, "programs")
        sub_areas = names_from_bii_terms(record, "subAreas")
        website = clean_text(str(record.get("externalLink") or record.get("url") or ""))
        hit = make_accelerator_hit(
            source,
            company,
            "https://bii.dk/community/start-ups-projects/",
            cohort_label=", ".join(programs) or "BII start-ups and projects",
            category_or_track=", ".join(sub_areas),
            company_description=summary,
            website=website if website.startswith(("http://", "https://")) else "",
            matched_terms="adapter: bioinnovation_institute; GetProjects human-health record",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits

def run_bioinnovation_institute(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = ACCELERATOR_SOURCE_PAGES.get(source.name, [source.url])
    hits: list[DiscoveryHit] = []
    errors: list[str] = []
    scanned = 0
    for url in urls:
        payload, error = fetch_json_url(url)
        scanned += 1
        if error:
            errors.append(f"{url}: {error}")
            continue
        hits.extend(parse_bioinnovation_institute_payload(source, payload, url))
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{scanned} BII project endpoints scanned; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if not hits:
        result = f"INCOMPLETE {source.name} extraction: no human-health project records found. " + result
    if errors:
        result += "; errors: " + " | ".join(errors)
    return hits, triggers, result

NUCLEATE_LOCATIONS = [
    "San diego",
    "New york city",
    "New haven",
    "Bayarea",
    "Bay area",
    "San francisco",
    "Los angeles",
    "All locations",
    "Boston",
    "Baltimore",
    "Cambridge",
    "London",
    "Oxford",
    "Paris",
    "Berlin",
    "Zurich",
    "Toronto",
    "Montreal",
    "Vancouver",
    "Seattle",
    "Chicago",
    "Houston",
    "Atlanta",
]

NUCLEATE_CATEGORY_TERMS = [
    "Medical Devices",
    "Digital Health",
    "Therapeutics",
    "Diagnostics",
    "Platform",
    "Eco",
]

CDL_HEALTH_STREAMS = {
    "advanced therapies",
    "biomedical engineering",
    "biotech",
    "cancer",
    "computational health",
    "health",
    "health & wellness",
    "healthcare robotics",
    "neuro",
}


def split_nucleate_header(header: str) -> tuple[str, str]:
    header = clean_text(header)
    for location in sorted(NUCLEATE_LOCATIONS, key=len, reverse=True):
        if header.lower().endswith(" " + location.lower()):
            return clean_page_candidate(header[: -len(location)].strip()), clean_text(location)
    return clean_page_candidate(header), ""

def split_nucleate_category_and_description(value: str) -> tuple[str, str]:
    value = clean_text(value)
    for category in sorted(NUCLEATE_CATEGORY_TERMS, key=len, reverse=True):
        if value.lower().startswith(category.lower() + " "):
            return category, clean_text(value[len(category) :])
    return "", value

def parse_nucleate_activator_page(source: Source, markdown: str, page_url: str) -> list[DiscoveryHit]:
    body = markdown.split("Markdown Content:", 1)[-1]
    body = re.sub(r"\n[ \t]+", "\n", body)
    body = re.split(r"\n#{1,3}\s+Activator|Activator Program|© COPYRIGHT", body, maxsplit=1, flags=re.I)[0]
    pattern = re.compile(
        r"(?P<header>[^\n]{2,120})\n+\s*Launched\s+(?P<year>20\d{2})\s*\n+\s*(?P<body>.*?)(?=\n[A-Z0-9][^\n]{2,120}\n+\s*Launched\s+20\d{2}\s*\n+|$)",
        flags=re.S,
    )
    hits: list[DiscoveryHit] = []
    for match in pattern.finditer(body):
        company, geography = split_nucleate_header(match.group("header"))
        category, description = split_nucleate_category_and_description(match.group("body"))
        context = " ".join([company, category, description])
        if category.lower() == "eco" and not eu_accelerator_has_health_relevance(source, company, description):
            continue
        if not eu_accelerator_has_health_relevance(source, company, context):
            continue
        hit = make_accelerator_hit(
            source,
            company,
            "https://nucleate.org/companies",
            cohort_label=f"Nucleate Activator {match.group('year')}",
            cohort_year=match.group("year"),
            category_or_track=category,
            company_description=description,
            geography=geography or source.geography,
            matched_terms="adapter: nucleate_activator; reader company record",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits

def run_nucleate_activator(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = ACCELERATOR_SOURCE_PAGES.get(source.name, [source.url])
    hits: list[DiscoveryHit] = []
    errors: list[str] = []
    scanned = 0
    for url in urls:
        raw_text, error = fetch_raw_text(url)
        scanned += 1
        if error:
            errors.append(f"{url}: {error}")
            continue
        hits.extend(parse_nucleate_activator_page(source, raw_text, url))
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{scanned} Nucleate pages scanned; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if not hits:
        result = f"INCOMPLETE {source.name} extraction: no health-relevant Nucleate company records found. " + result
    if errors:
        result += "; errors: " + " | ".join(errors)
    return hits, triggers, result

def parse_cdl_health_page(source: Source, raw_html: str, page_url: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    card_pattern = re.compile(
        r'<a\s+href=["\'](?P<href>[^"\']+)["\'][^>]*class=["\'][^"\']*company[^"\']*["\'][^>]*>(?P<body>.*?)</a>',
        flags=re.I | re.S,
    )
    for match in card_pattern.finditer(raw_html):
        body = match.group("body")
        name_match = re.search(r'class=["\']companybio-location["\'][^>]*>(.*?)</p>', body, flags=re.I | re.S)
        stream_match = re.search(r'class=["\']companybio-stream["\'][^>]*>(.*?)</p>', body, flags=re.I | re.S)
        if not name_match or not stream_match:
            continue
        company = clean_page_candidate(name_match.group(1))
        stream = clean_text(stream_match.group(1))
        if stream.lower() not in CDL_HEALTH_STREAMS:
            continue
        hit = make_accelerator_hit(
            source,
            company,
            urljoin(page_url, match.group("href")),
            cohort_label="Creative Destruction Lab companies",
            category_or_track=stream,
            matched_terms="adapter: cdl_health; health stream company card",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits

def run_cdl_health(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = ACCELERATOR_SOURCE_PAGES.get(source.name, [source.url])
    hits: list[DiscoveryHit] = []
    errors: list[str] = []
    scanned = 0
    for url in urls:
        raw_html, error = fetch_raw_text(url)
        scanned += 1
        if error:
            errors.append(f"{url}: {error}")
            continue
        hits.extend(parse_cdl_health_page(source, raw_html, url))
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{scanned} CDL company pages scanned; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if not hits:
        result = f"INCOMPLETE {source.name} extraction: no health stream company cards found. " + result
    if errors:
        result += "; errors: " + " | ".join(errors)
    return hits, triggers, result

def masschallenge_category_for_link(content_before_link: str) -> str:
    text = text_from_html(content_before_link)
    categories = ["BIOTECHNOLOGY", "MEDTECH", "DIGITAL HEALTH & AI"]
    positions = [(category, text.upper().rfind(category)) for category in categories]
    positions = [(category, pos) for category, pos in positions if pos >= 0]
    if not positions:
        return ""
    return max(positions, key=lambda item: item[1])[0].title().replace("Ai", "AI")

MASSCHALLENGE_HEALTHCARE_2026_COHORT = [
    ("Adipothera", "Biotechnology", "https://adipothera.com/"),
    ("Dense Immune", "Biotechnology", "https://www.denseimmune.com/"),
    ("Environ", "Biotechnology", ""),
    ("EtiraRx", "Biotechnology", "https://etira.life/"),
    ("Jibe Therapeutics", "Biotechnology", "https://jibetx.com/"),
    ("Miyako Bio", "Biotechnology", ""),
    ("MyImmune Corporation", "Biotechnology", "https://www.myimmune.ai/"),
    ("OmniNano Pharmaceuticals", "Biotechnology", "https://www.omninanopharma.com/"),
    ("Sarxion", "Biotechnology", ""),
    ("Spry Bio", "Biotechnology", "https://www.sprybio.com/"),
    ("Telos Biotech", "Biotechnology", "https://www.telosbio.com/"),
    ("VirVa Health", "Biotechnology", "https://virvah.com/"),
    ("YAXIE Inc.", "Biotechnology", "https://www.yaxie.jp/"),
    ("ZEeST Bio", "Biotechnology", "https://zeest.bio/"),
    ("Advanced Nanolytics Inc.", "Medtech", "https://aninano.com/"),
    ("Any-Edge Inc.", "Medtech", "https://viamonte1114.wixsite.com/website"),
    ("CircuCare", "Medtech", "https://www.circucare.com/"),
    ("Curiva", "Medtech", "https://www.curiva.co/"),
    ("Freyya", "Medtech", "https://freyya.com/"),
    ("Hoopsy", "Medtech", "https://hoopsy.com/"),
    ("Innovations Unlimited LLC", "Medtech", "https://innovationsunlimitedllc.com/"),
    ("Latde Diagnostics", "Medtech", "https://latde-dx.com/"),
    ("Leaf Guardian", "Medtech", "https://leafguardian.co/"),
    ("Microvitality", "Medtech", "https://www.microvitalitybio.com/"),
    ("Motilix", "Medtech", "https://www.linkedin.com/company/motilix/"),
    ("Pollen Sense Inc.", "Medtech", "https://pollensense.com/"),
    ("SafeBVM Corp.", "Medtech", "https://safebvm.com/"),
    ("SilkMed, Inc.", "Medtech", "https://silkmedsolutions.com/"),
    ("Sympal", "Medtech", "https://www.thesympal.com/"),
    ("Zephyr Apnea Technologies", "Medtech", "https://www.linkedin.com/company/zephyr-apnea-technologies/"),
    ("Kairos", "Digital Health & AI", "https://kairoshealthai.com/"),
    ("LastMinute", "Digital Health & AI", "https://www.trylastminute.com/"),
    ("MindMuscle", "Digital Health & AI", "https://mindmuscle.health/"),
    ("NtelCare", "Digital Health & AI", "https://www.ntelcare.com/"),
    ("Revella Health", "Digital Health & AI", "https://revellahealth.com/"),
    ("SeeInMe", "Digital Health & AI", "https://seeinme.com/"),
    ("TheraMotive", "Digital Health & AI", "https://www.theramotive.com/"),
    ("Trialynx", "Digital Health & AI", "https://www.trialynx.io/"),
    ("VITAL-IT", "Digital Health & AI", "https://www.vital-it.com/"),
    ("With U", "Digital Health & AI", "https://withuai.com/"),
    ("Zendra Health", "Digital Health & AI", "https://www.zendrahealth.com/"),
]

def masschallenge_healthcare_snapshot_hits(source: Source) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    evidence_url = "https://masschallenge.org/articles/healthcare-life-sciences-traction-cohort-2026/"
    for company, category, website in MASSCHALLENGE_HEALTHCARE_2026_COHORT:
        hit = make_accelerator_hit(
            source,
            company,
            evidence_url,
            cohort_label="MassChallenge Healthcare & Life Sciences Traction 2026",
            cohort_year="2026",
            category_or_track=category,
            website=website,
            company_description=category,
            matched_terms="adapter: masschallenge_healthcare; official cohort snapshot fallback",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits

def parse_masschallenge_healthcare_content(source: Source, content: str, link: str, title: str = "") -> list[DiscoveryHit]:
    cohort_year = infer_cohort_year(title, content)
    segment = content
    meet = re.search(r"MEET\s+THE\s+COHORT", segment, flags=re.I)
    if meet:
        segment = segment[meet.end() :]
    end = re.search(r"BUILDING\s+THE\s+FUTURE", segment, flags=re.I)
    if end:
        segment = segment[: end.start()]
    hits: list[DiscoveryHit] = []
    for match in re.finditer(r'<a\s+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<text>.*?)</a>', segment, flags=re.I | re.S):
        company = clean_page_candidate(match.group("text"))
        if not company or company.lower() in {"ginkgo bioworks", "flywire", "tomorrow.io", "oklo", "spring health"}:
            continue
        before = segment[: match.start()]
        category = masschallenge_category_for_link(before)
        hit = make_accelerator_hit(
            source,
            company,
            link,
            cohort_label=f"MassChallenge Healthcare & Life Sciences Traction {cohort_year}".strip(),
            cohort_year=cohort_year,
            category_or_track=category,
            website=match.group("href"),
            company_description=category,
            matched_terms="adapter: masschallenge_healthcare; cohort article company link",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits

def parse_masschallenge_healthcare_article(source: Source, payload: object, page_url: str) -> list[DiscoveryHit]:
    if isinstance(payload, dict):
        content = ""
        if isinstance(payload.get("content"), dict):
            content = str(payload["content"].get("rendered") or "")
        link = str(payload.get("link") or page_url)
        title = ""
        if isinstance(payload.get("title"), dict):
            title = clean_text(str(payload["title"].get("rendered") or ""))
        return parse_masschallenge_healthcare_content(source, content, link, title)
    if isinstance(payload, str):
        title_match = re.search(r"<title[^>]*>(.*?)</title>", payload, flags=re.I | re.S)
        title = clean_text(title_match.group(1)) if title_match else ""
        return parse_masschallenge_healthcare_content(source, payload, page_url, title)
    return []

def run_masschallenge_healthcare(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = ACCELERATOR_SOURCE_PAGES.get(source.name, [source.url])
    hits: list[DiscoveryHit] = []
    errors: list[str] = []
    scanned = 0
    for url in urls:
        scanned += 1
        if "wp-json" in url:
            payload, error = fetch_json_url(url)
            if error:
                errors.append(f"{url}: {error}")
                continue
            hits.extend(parse_masschallenge_healthcare_article(source, payload, url))
            continue
        raw_html, error = fetch_raw_text(url)
        if error:
            errors.append(f"{url}: {error}")
            continue
        hits.extend(parse_masschallenge_healthcare_article(source, raw_html, url))
    used_snapshot = False
    if not hits:
        hits.extend(masschallenge_healthcare_snapshot_hits(source))
        used_snapshot = bool(hits)
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{scanned} MassChallenge healthcare cohort endpoints scanned; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if used_snapshot:
        result += "; live fetch blocked, used official 2026 cohort snapshot fallback"
    if not hits:
        result = f"INCOMPLETE {source.name} extraction: no cohort company links found. " + result
    if errors:
        result += "; errors: " + " | ".join(errors)
    return hits, triggers, result

def parse_rockstart_health_payload(source: Source, payload: object, page_url: str) -> list[DiscoveryHit]:
    if not isinstance(payload, list):
        return []
    hits: list[DiscoveryHit] = []
    for record in payload:
        if not isinstance(record, dict):
            continue
        title = record.get("title") or {}
        company = title.get("rendered") if isinstance(title, dict) else title
        company = clean_page_candidate(str(company or ""))
        if not company:
            continue
        cohort_year = ""
        if isinstance(record.get("date"), str):
            cohort_year = infer_cohort_year(record["date"])
        hit = make_accelerator_hit(
            source,
            company,
            str(record.get("link") or "https://rockstart.com/portfolio/vertical-healthcare/"),
            cohort_label=f"Rockstart Healthcare {cohort_year}".strip(),
            cohort_year=cohort_year,
            category_or_track="Healthcare",
            matched_terms="adapter: rockstart_health; WP healthcare vertical record",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits

def parse_rockstart_health_page(source: Source, raw_html: str, page_url: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    for href, inner in re.findall(r'<h5[^>]*>.*?<a\s+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>.*?</h5>', raw_html, flags=re.I | re.S):
        company = clean_page_candidate(inner)
        if not company or company.lower() in {"portfolio", "healthcare"}:
            continue
        context = context_after_link(raw_html, href) or context_around_link_text(raw_html, company)
        hit = make_accelerator_hit(
            source,
            company,
            page_url,
            cohort_label="Rockstart Healthcare",
            category_or_track="Healthcare",
            company_description=context,
            website=href if href.startswith(("http://", "https://")) else "",
            matched_terms="adapter: rockstart_health; healthcare vertical page card",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits

def reader_json_payload(reader_text: str) -> object | None:
    body = reader_text.split("Markdown Content:", 1)[-1].strip()
    if not body.startswith(("[", "{")):
        return None
    try:
        return json.JSONDecoder().raw_decode(body)[0]
    except json.JSONDecodeError:
        return None

def run_rockstart_health(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = ACCELERATOR_SOURCE_PAGES.get(source.name, [source.url])
    hits: list[DiscoveryHit] = []
    errors: list[str] = []
    scanned = 0
    for url in urls:
        scanned += 1
        if "wp-json" in url:
            payload, error = fetch_json_url(url)
            if error:
                errors.append(f"{url}: {error}")
                reader_text, reader_error = fetch_raw_text(MAYO_READER_PREFIX + url)
                scanned += 1
                if reader_error:
                    errors.append(f"{MAYO_READER_PREFIX + url}: {reader_error}")
                    continue
                payload = reader_json_payload(reader_text)
                if payload is None:
                    errors.append(f"{MAYO_READER_PREFIX + url}: reader JSON parse failed")
                    continue
                hits.extend(parse_rockstart_health_payload(source, payload, url))
                continue
            hits.extend(parse_rockstart_health_payload(source, payload, url))
            continue
        raw_html, error = fetch_raw_text(url)
        if error:
            errors.append(f"{url}: {error}")
            continue
        hits.extend(parse_rockstart_health_page(source, raw_html, url))
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{scanned} Rockstart healthcare endpoints scanned; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if not hits:
        result = f"INCOMPLETE {source.name} extraction: no healthcare portfolio records found. " + result
    if errors:
        result += "; errors: " + " | ".join(errors)
    return hits, triggers, result

def sbri_table_value(block: str, label: str) -> str:
    pattern = rf"<th[^>]*>\s*{re.escape(label)}\s*</th>\s*<td[^>]*>(.*?)</td>"
    match = re.search(pattern, block, flags=re.I | re.S)
    return clean_text(match.group(1)) if match else ""

def parse_sbri_healthcare_page(source: Source, raw_html: str, page_url: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    for block in re.findall(r'<div\s+class=["\']directory-item["\'][^>]*>(.*?)</div>\s*</div>', raw_html, flags=re.I | re.S):
        name_match = re.search(r"<h3[^>]*>(.*?)</h3>", block, flags=re.I | re.S)
        company = clean_page_candidate(name_match.group(1)) if name_match else ""
        if not company:
            continue
        project = sbri_table_value(block, "Project")
        description = sbri_table_value(block, "Description")
        innovation_partner = sbri_table_value(block, "Health Innovation Network Partner")
        website_match = re.search(r'<a[^>]+href=["\']([^"\']+)["\']', block, flags=re.I)
        website = website_match.group(1) if website_match else ""
        hit = make_accelerator_hit(
            source,
            company,
            page_url,
            cohort_label="SBRI Healthcare innovation portfolio",
            category_or_track=innovation_partner,
            company_description=" ".join([project, description]).strip(),
            website=website,
            matched_terms="adapter: sbri_healthcare; innovation portfolio directory item",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits

def run_sbri_healthcare(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = ACCELERATOR_SOURCE_PAGES.get(source.name, [source.url])
    hits: list[DiscoveryHit] = []
    errors: list[str] = []
    scanned = 0
    for url in urls:
        raw_html, error = fetch_raw_text(url)
        scanned += 1
        if error:
            errors.append(f"{url}: {error}")
            continue
        hits.extend(parse_sbri_healthcare_page(source, raw_html, url))
    by_company: dict[str, DiscoveryHit] = {}
    for hit in hits:
        by_company.setdefault(hit.company.lower(), hit)
    hits = list(by_company.values())
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{scanned} SBRI portfolio pages scanned; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if not hits:
        result = f"INCOMPLETE {source.name} extraction: no innovation portfolio directory items found. " + result
    if errors:
        result += "; errors: " + " | ".join(errors)
    return hits, triggers, result

def digitalhealth_london_profile_urls(raw_html: str, page_url: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for _, href in extract_links(raw_html, page_url):
        if "/innovation-directory/profile/" not in href or href in seen:
            continue
        seen.add(href)
        urls.append(href)
    return urls

def infer_digitalhealth_london_cohort(profile_text: str, page_text: str = "", href: str = "") -> str:
    context = " ".join([profile_text or "", page_text or "", href or ""])
    patterns = [
        r"\b(?:Accelerator|Launchpad|Cohort|cohort|programme|program)\s*(?:cohort)?\s*[:/\-–—]?\s*(20\d{2})\b",
        r"\b(20\d{2})\s*(?:Accelerator|Launchpad|Cohort|cohort|programme|program)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, context, flags=re.I)
        if match:
            return f"DigitalHealth.London {match.group(1)}"
    year = infer_cohort_year(context)
    return f"DigitalHealth.London {year}" if year else ""

def parse_digitalhealth_london_page(source: Source, raw_html: str, page_url: str, profile_html_by_url: dict[str, str] | None = None) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    profile_html_by_url = profile_html_by_url or {}
    seen_urls: set[str] = set()
    page_text = text_from_html(raw_html)
    for link_text, href in extract_links(raw_html, page_url):
        if "/innovation-directory/profile/" not in href or href in seen_urls:
            continue
        seen_urls.add(href)
        company = re.split(r"\s+Company\s+", link_text, maxsplit=1, flags=re.I)[0]
        card_description = ""
        if re.search(r"\s+Company\s+", link_text, flags=re.I):
            card_description = re.split(r"\s+Company\s+", link_text, maxsplit=1, flags=re.I)[1]
        profile_html = profile_html_by_url.get(href, "")
        profile_text = text_from_html(profile_html) if profile_html else context_after_link(raw_html, href)
        description = (extract_meta_description(profile_html) if profile_html else "") or card_description or profile_text
        cohort = infer_digitalhealth_london_cohort(profile_text, page_text, href)
        track_parts = []
        for label in ["Sector", "Technology", "Area innovation", "Area of innovation"]:
            match = re.search(rf"{label}\s*:?\s*([A-Za-z0-9 /,&+-]{{3,80}})", profile_text, flags=re.I)
            if match:
                track_parts.append(clean_text(match.group(1)))
        hit = make_accelerator_hit(
            source,
            company,
            href,
            cohort_label=cohort,
            cohort_year=infer_cohort_year(cohort, profile_text),
            category_or_track="; ".join(dict.fromkeys(track_parts)),
            company_description=description,
            matched_terms="adapter: digitalhealth_london; profile link",
        )
        if hit:
            hits.append(hit)
    return hits

def run_digitalhealth_london(source: Source, max_pages: int = 50) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    base_url = ACCELERATOR_SOURCE_PAGES[source.name][0]
    all_hits: list[DiscoveryHit] = []
    errors: list[str] = []
    profiles_fetched = 0
    pages_scanned = 0
    page = 1
    while page <= max_pages:
        url = base_url if page == 1 else f"{base_url}/page/{page}"
        raw_html, error = fetch_raw_text(url)
        pages_scanned += 1
        if error:
            if page == 1:
                errors.append(f"{url}: {error}")
            break
        profile_html_by_url: dict[str, str] = {}
        for profile_url in digitalhealth_london_profile_urls(raw_html, url):
            profile_html, profile_error = fetch_raw_text(profile_url)
            if profile_error:
                errors.append(f"{profile_url}: {profile_error}")
                continue
            profile_html_by_url[profile_url] = profile_html
            profiles_fetched += 1
        page_hits = parse_digitalhealth_london_page(source, raw_html, url, profile_html_by_url)
        if not page_hits:
            break
        all_hits.extend(page_hits)
        if f"/companies/page/{page + 1}" not in raw_html:
            break
        page += 1
    hits, triggers = dedupe_hits_with_triggers(source, all_hits)
    result = f"{pages_scanned} directory pages scanned; {profiles_fetched} profiles fetched; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if errors:
        result += "; errors: " + " | ".join(errors)
    return hits, triggers, result

def parse_medtech_innovator_showcase(source: Source, raw_html: str, page_url: str, cohort_label: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    current_track = ""
    parts = re.split(r"(<h[1-4]\b.*?</h[1-4]>|<a\b.*?</a>)", raw_html, flags=re.I | re.S)
    for part in parts:
        if re.match(r"<h[1-4]\b", part, flags=re.I):
            heading = clean_text(part)
            if heading and len(heading) <= 80:
                current_track = heading
            continue
        if not re.match(r"<a\b", part, flags=re.I):
            continue
        href_match = re.search(r"href=[\"']([^\"']+)[\"']", part, flags=re.I)
        text = clean_text(part)
        href = urljoin(page_url, href_match.group(1)) if href_match else page_url
        if not text or text.lower() in {"website", "learn more", "view profile"}:
            continue
        if not current_track:
            continue
        if not is_relevant_candidate_link(Source(source.name, source.source_type, page_url, source.geography, source.priority, source.update_cadence, source.extraction_method, source.notes, "accelerator_page"), text, href):
            host = urlparse(href).netloc.lower()
            if any(domain in host for domain in ["medtechinnovator.org", "medtechinnovator.asia", "biotoolsinnovator.org", "pro.innovator.org"]):
                continue
        hit = make_accelerator_hit(
            source,
            text,
            href,
            cohort_label=cohort_label,
            cohort_year=infer_cohort_year(cohort_label, page_url),
            category_or_track=current_track,
            company_description=context_after_link(raw_html, href),
            matched_terms="adapter: medtech_innovator; showcase/company link",
        )
        if hit:
            hits.append(hit)
    return hits

def pory_value(fields: dict, *names: str) -> str:
    for name in names:
        value = fields.get(name)
        if value is None:
            continue
        if isinstance(value, list):
            return ", ".join(clean_text(str(item)) for item in value if clean_text(str(item)))
        return clean_text(str(value))
    return ""

def parse_medtech_innovator_pory_records(source: Source, records: list[dict]) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    for record in records:
        fields = record.get("fields") or {}
        company = pory_value(fields, "Company", "fld4BXQlB6TZgMSJa")
        if not company:
            continue
        year = pory_value(fields, "Year.", "Year", "flddSysOAMNrvWgLE")
        program = pory_value(fields, "Program.", "Program", "fldtA2KHphCLDbQXy") or "MedTech Innovator portfolio"
        if program in {"US", "APAC", "BTI"}:
            program = f"MedTech Innovator {program}"
        category = pory_value(
            fields,
            "Clinical Categories",
            "Device Categories",
            "Digital Categories",
            "Diagnostic Categories",
            "Thematic Categories",
            "Primary Industry Group",
        )
        description = pory_value(fields, "Product Short Description", "Description", "Long Description", "fld3ZsMoNwuiP15vS")
        website = pory_value(fields, "Website", "fldSEQbd6GpIJBF6J")
        geography = pory_value(fields, "Company Country/Territory", "Company Country/Territory (Old Field)", "Country")
        record_id = clean_text(str(record.get("id") or ""))
        evidence_url = f"{MEDTECH_INNOVATOR_PORY_RECORDS_URL}/{record_id}" if record_id else MEDTECH_INNOVATOR_PORY_APP_URL
        hit = make_accelerator_hit(
            source,
            company,
            evidence_url,
            accelerator_program=program,
            cohort_label=f"{program} {year}".strip(),
            cohort_year=year,
            category_or_track=category,
            company_description=description,
            website=website,
            geography=geography,
            matched_terms="adapter: medtech_innovator; pory portfolio records",
        )
        if hit:
            hits.append(hit)
    return hits

def fetch_medtech_innovator_pory_records(max_pages: int = 100) -> tuple[list[dict], list[str]]:
    records: list[dict] = []
    errors: list[str] = []
    offset = ""
    for _ in range(max_pages):
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        url = MEDTECH_INNOVATOR_PORY_RECORDS_URL + "?" + urlencode(params)
        data, error = fetch_json_url(url)
        if error:
            errors.append(f"{url}: {error}")
            break
        page_records = data.get("records") if isinstance(data, dict) else []
        if not page_records:
            break
        records.extend(page_records)
        offset = data.get("offset") if isinstance(data, dict) else ""
        if not offset:
            break
    return records, errors

def run_medtech_innovator(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    cohort_url = ACCELERATOR_SOURCE_PAGES[source.name][0]
    cohort_html, error = fetch_raw_text(cohort_url)
    errors: list[str] = []
    if error:
        errors.append(f"{cohort_url}: {error}")
        cohort_html = ""
    expected = 65
    expected_match = re.search(r"\b(\d{2,3})\s+(?:companies|startups)\b", text_from_html(cohort_html), flags=re.I)
    if expected_match:
        expected = int(expected_match.group(1))
    cohort_label = f"MedTech Innovator {infer_cohort_year(cohort_url, cohort_html) or TODAY[:4]} cohort"
    showcase_urls = []
    for _, href in extract_links(cohort_html, cohort_url):
        if "pro.innovator.org/showcase" in href or "flippingbook.com" in href:
            showcase_urls.append(href)
    hits: list[DiscoveryHit] = []
    current_hits: list[DiscoveryHit] = []
    for url in dict.fromkeys(showcase_urls):
        showcase_html, showcase_error = fetch_raw_text(url)
        if showcase_error:
            errors.append(f"{url}: {showcase_error}")
            continue
        current_hits.extend(parse_medtech_innovator_showcase(source, showcase_html, url, cohort_label))
    if not current_hits and cohort_html:
        current_hits.extend(parse_medtech_innovator_showcase(source, cohort_html, cohort_url, cohort_label))
    hits.extend(current_hits)

    pory_records, pory_errors = fetch_medtech_innovator_pory_records()
    errors.extend(pory_errors)
    hits.extend(parse_medtech_innovator_pory_records(source, pory_records))

    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{len(showcase_urls) or 1} cohort/showcase pages scanned; {len(pory_records)} Pory portfolio records; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if len(current_hits) < expected:
        result = f"INCOMPLETE current-cohort extraction: expected about {expected} current-cohort companies; found {len(current_hits)} in HTML/showcase. " + result
    if errors:
        result += "; errors: " + " | ".join(errors)
    return hits, triggers, result

def parse_mayo_accelerate_page(source: Source, raw_html: str, page_url: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    cohort_year = infer_cohort_year(raw_html, page_url)
    chunks = re.split(r"(<h[2-4]\b.*?</h[2-4]>)", raw_html, flags=re.I | re.S)
    for idx, chunk in enumerate(chunks):
        if not re.match(r"<h[2-4]\b", chunk, flags=re.I):
            continue
        company = clean_text(chunk)
        body = text_from_html(" ".join(chunks[idx + 1 : idx + 3]))
        if not body or len(body) < 20:
            continue
        hit = make_accelerator_hit(
            source,
            company,
            page_url,
            cohort_label=f"Mayo Clinic Platform Accelerate {cohort_year}".strip(),
            cohort_year=cohort_year,
            company_description=body,
            matched_terms="adapter: mayo_accelerate; cohort heading",
        )
        if hit:
            hits.append(hit)
    if not hits and "Markdown Content:" in raw_html:
        hits.extend(parse_mayo_accelerate_markdown(source, raw_html, page_url))
    return hits

def markdown_to_text(value: str) -> str:
    value = re.sub(r"\[!\[[^\]]+\]\([^)]+\)\]\([^)]+\)", " ", value)
    value = re.sub(r"!\[[^\]]+\]\([^)]+\)", " ", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = value.replace("**", "")
    return clean_text(value)

def parse_mayo_accelerate_markdown(source: Source, markdown: str, page_url: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    body = markdown.split("Markdown Content:", 1)[-1]
    body = body.split("### Interested in learning more?", 1)[0]
    body = body.split("## Meet the Newest Cohort", 1)[-1]
    cohort_year = infer_cohort_year(markdown, page_url)
    sections = re.split(r"\n(?=\s*(?:\[!\[Image|\!\[Image))", body)
    for section in sections:
        if not re.search(r"(?:\[!\[Image|\!\[Image)", section):
            continue
        website = ""
        linked_image = re.search(r"\[!\[[^\]]+\]\([^)]+\)\]\((https?://[^)]+)\)", section)
        if linked_image:
            website = linked_image.group(1)
        text = markdown_to_text(section)
        if len(text) < 30:
            continue
        quoted_name = re.match(r"[\"“]([^\"”]+)[\"”]\s+is\b", text)
        bold_names = [clean_text(match) for match in re.findall(r"\*\*([^*]+)\*\*", section)]
        company = quoted_name.group(1) if quoted_name else (bold_names[0] if bold_names else "")
        company = re.sub(r"[’']s$", "", company)
        if not company:
            continue
        hit = make_accelerator_hit(
            source,
            company,
            page_url,
            cohort_label=f"Mayo Clinic Platform Accelerate {cohort_year}".strip(),
            cohort_year=cohort_year,
            company_description=text,
            website=website,
            matched_terms="adapter: mayo_accelerate; live reader page",
        )
        if hit:
            hits.append(hit)
    return hits

def mayo_reader_url(url: str) -> str:
    return MAYO_READER_PREFIX + url

def run_mayo_accelerate(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = ACCELERATOR_SOURCE_PAGES[source.name]
    hits: list[DiscoveryHit] = []
    errors: list[str] = []
    scanned = 0
    for url in urls:
        raw_html, error = fetch_raw_text(url)
        scanned += 1
        if error:
            errors.append(f"{url}: {error}")
        else:
            hits.extend(parse_mayo_accelerate_page(source, raw_html, url))
        if hits:
            continue
        reader_url = mayo_reader_url(url)
        reader_text, reader_error = fetch_raw_text(reader_url)
        scanned += 1
        if reader_error:
            errors.append(f"{reader_url}: {reader_error}")
            continue
        hits.extend(parse_mayo_accelerate_page(source, reader_text, url))
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{scanned} cohort/live-reader pages scanned; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if not hits:
        result = "INCOMPLETE Mayo extraction: live Mayo page and reader fetch returned no companies. " + result
    if errors:
        result += "; errors: " + " | ".join(errors)
    return hits, triggers, result

def parse_eit_health_catapult_page(source: Source, raw_html: str, page_url: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    previous_match = re.search(r"previous\s+winners", raw_html, flags=re.I)
    if previous_match:
        raw_html = raw_html[previous_match.start() :]
    page_text = text_from_html(raw_html)
    default_year = infer_cohort_year(page_text, page_url)
    current_track = ""
    current_award = ""
    parts = re.split(r"(<h[2-4]\b.*?</h[2-4]>|<img\b[^>]*>|<a\b.*?</a>)", raw_html, flags=re.I | re.S)
    for part in parts:
        if re.match(r"<h[2-4]\b", part, flags=re.I):
            heading = clean_text(part)
            if re.search(r"\b(BioTech|MedTech|Digital Health|Winner|Award|Edition|Final)\b", heading, flags=re.I):
                if "winner" in heading.lower() or "award" in heading.lower():
                    current_award = heading
                else:
                    current_track = heading
            continue
        company = ""
        href = page_url
        if re.match(r"<img\b", part, flags=re.I):
            alt_match = re.search(r"alt=[\"']([^\"']+)[\"']", part, flags=re.I)
            company = clean_text(alt_match.group(1)) if alt_match else ""
        elif re.match(r"<a\b", part, flags=re.I):
            href_match = re.search(r"href=[\"']([^\"']+)[\"']", part, flags=re.I)
            href = urljoin(page_url, href_match.group(1)) if href_match else page_url
            company = clean_text(part)
        if not company:
            continue
        if not current_track and not current_award:
            continue
        track = "; ".join([value for value in [current_track, current_award] if value])
        hit = make_accelerator_hit(
            source,
            company,
            href,
            cohort_label=f"EIT Health Catapult {default_year}".strip(),
            cohort_year=default_year,
            category_or_track=track,
            company_description=context_after_link(raw_html, href),
            matched_terms="adapter: eit_health_catapult; previous winner/finalist",
        )
        if hit:
            hits.append(hit)
    return hits

def run_eit_health_catapult(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    url = ACCELERATOR_SOURCE_PAGES[source.name][0]
    raw_html, error = fetch_raw_text(url)
    if error:
        return [], [], f"{url}: {error}"
    hits, triggers = dedupe_hits_with_triggers(source, parse_eit_health_catapult_page(source, raw_html, url))
    return hits, triggers, f"Previous winners/finalists page scanned; {len(hits)} discovery hits; {len(triggers)} trigger events"

