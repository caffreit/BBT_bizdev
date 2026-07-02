from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from ..config import CURATED_UNIVERSITY_SPINOUTS, UNIVERSITY_SPINOUT_SOURCE_PAGES
from ..http import fetch_raw_text
from ..models import DiscoveryHit, Source, TriggerEvent
from ..text import (
    clean_page_candidate,
    clean_text,
    extract_links,
    infer_page_product_type,
    is_plausible_page_candidate,
    source_type_trigger_event,
)


UNIVERSITY_GENERIC_LINK_TEXT = {
    "about",
    "about us",
    "accessibility",
    "alumni",
    "apply",
    "be a consultant",
    "be inspired",
    "blog",
    "browse innovations",
    "case studies",
    "careers network",
    "careers support",
    "clinical outcome assessments",
    "commercial case studies",
    "consultancy",
    "contact",
    "contact us",
    "department of mechanical engineering",
    "events",
    "explore consultancy",
    "faqs",
    "find a consultant",
    "home",
    "industry",
    "innovation",
    "leadership",
    "licensing",
    "location",
    "login",
    "mres neurotechnology",
    "news",
    "our alumni community",
    "our leadership",
    "portfolio",
    "presenters",
    "privacy",
    "resources",
    "services",
    "skip to footer",
    "skip to main content",
    "skip to navigation",
    "spinouts",
    "start-up community",
    "startups",
    "sustainability",
    "terms",
    "visit the website",
    "website navigation",
}

UNIVERSITY_GENERIC_TEXT_MARKERS = {
    "cookie",
    "privacy policy",
    "accessibility",
    "newsletter",
    "short course",
    "masterclass",
    "research proposal",
    "research groups",
    "our projects",
    "our team",
    "leadership",
    "licensing",
    "consultancy",
    "faq",
    "location",
    "presenter",
    "presentation",
    "community",
    "innovation centre",
    "medtech superconnector",
    "professor",
    "research highlights",
    "social responsibility",
    "spinouts and industry engagement",
    "teaching and learning",
    "structural health monitoring",
}

BBT_RELEVANCE_TERMS = {
    "ai",
    "artificial intelligence",
    "bionic",
    "bioengineering",
    "biomarker",
    "biotech",
    "brain",
    "cancer",
    "cardiac",
    "care",
    "clinical",
    "diagnostic",
    "digital health",
    "drug discovery",
    "health",
    "healthcare",
    "hospital",
    "joint",
    "life science",
    "medical",
    "medtech",
    "neuro",
    "patient",
    "point-of-care",
    "pharma",
    "prosthetic",
    "regulated",
    "rehabilitation",
    "respiratory",
    "samd",
    "surgery",
    "surgical",
    "therapeutic",
    "vaccine",
}

BBT_EXCLUSION_TERMS = {
    "advanced positioning",
    "aviation fuel",
    "biochar",
    "circular economy",
    "cleaner chemicals",
    "food products",
    "food brand",
    "free-from",
    "growers",
    "infrastructure",
    "leather alternative",
    "marine collagen",
    "material identification",
    "paints",
    "photosynthesis",
    "plant based",
    "single-use plastics",
    "structural health monitoring",
    "sustainable alternative",
    "textiles",
}


def local_context_for_link(raw_html: str, link_text: str, href: str, window: int = 900) -> str:
    needles = [href, link_text]
    lower_html = raw_html.lower()
    start = -1
    for needle in needles:
        if not needle:
            continue
        start = lower_html.find(needle.lower())
        if start >= 0:
            break
    if start < 0:
        return clean_text(link_text)
    anchor_start = lower_html.rfind("<a", 0, start + 1)
    anchor_end = lower_html.find("</a>", start)
    next_anchor = lower_html.find("<a", anchor_end + 4) if anchor_end >= 0 else -1
    if anchor_start >= 0 and anchor_end >= 0:
        snippet_end = next_anchor if next_anchor >= 0 else min(len(raw_html), anchor_start + window)
        if snippet_end > anchor_start and snippet_end - anchor_start <= window * 2:
            return clean_text(raw_html[anchor_start:snippet_end])
    block_starts = [lower_html.rfind(tag, 0, start) for tag in ("<article", "<li", "<tr", "<div", "<section")]
    block_start = max(block_starts)
    block_ends = []
    for tag in ("article", "li", "tr", "div", "section"):
        end_tag = f"</{tag}>"
        index = lower_html.find(end_tag, start)
        if index >= 0:
            block_ends.append(index + len(end_tag))
    block_end = min(block_ends) if block_ends else -1
    if block_start >= 0 and block_end > block_start and block_end - block_start <= window * 3:
        return clean_text(raw_html[block_start:block_end])
    snippet = raw_html[max(0, start - window) : start + window]
    return clean_text(snippet)


def is_external_company_website(source_url: str, href: str) -> bool:
    source_host = urlparse(source_url).netloc.lower().removeprefix("www.")
    href_host = urlparse(href).netloc.lower().removeprefix("www.")
    return bool(href_host and source_host and href_host != source_host)


def is_candidate_company_website(source_url: str, href: str) -> bool:
    lower_href = href.lower()
    href_host = urlparse(href).netloc.lower().removeprefix("www.")
    blocked_hosts = (
        "linkedin.com",
        "cam.ac.uk",
        "imperial.ac.uk",
        "bristol.ac.uk",
        "enterprise.cam.ac.uk",
        "innovation.ox.ac.uk",
        "qubis.co.uk",
        "bayes-centre.ed.ac.uk",
        "ed.ac.uk",
        "edinburgh-innovations.ed.ac.uk",
        "ucd.ie",
    )
    if any(host in href_host for host in blocked_hosts):
        return False
    if any(marker in lower_href for marker in ["/team/", "/people/", "/profile", "forbes.com"]):
        return False
    return is_external_company_website(source_url, href)


def is_bbt_relevant_university_context(context: str) -> bool:
    lower_context = clean_text(context).lower()
    if any(term in lower_context for term in BBT_EXCLUSION_TERMS):
        return False
    if re.search(r"\b[a-z0-9-]*dx\b|\bbio\b|\b[a-z0-9-]*bio\b", lower_context):
        return True
    for term in BBT_RELEVANCE_TERMS:
        if term in {"ai", "artificial intelligence"}:
            continue
        if term == "care" and re.search(r"\bcare\b", lower_context):
            return True
        if len(term) > 4 and term in lower_context:
            return True
    return False


def is_plausible_university_company_name(company: str) -> bool:
    company = clean_page_candidate(company)
    lower = company.lower()
    if not is_plausible_page_candidate(company):
        return False
    if lower in UNIVERSITY_GENERIC_LINK_TEXT:
        return False
    if lower.startswith(("be ", "browse ", "explore ", "find ", "our ", "read ", "view ")):
        return False
    if re.search(r"\b(announces|collaborates|launches|partners|raises|secures|wins)\b", company, flags=re.I):
        return False
    if ":" in company:
        return False
    if any(marker in lower for marker in UNIVERSITY_GENERIC_TEXT_MARKERS):
        return False
    return True


def company_name_from_profile_slug(href: str) -> str:
    slug = urlparse(href).path.rstrip("/").rsplit("/", 1)[-1]
    if not slug or slug.lower() in {"all", "digital", "life-science", "environmental", "scientific", "engineering", "timeline"}:
        return ""
    words = [word.upper() if word in {"ai", "dx"} else word.capitalize() for word in re.split(r"[-_]+", slug) if word]
    return clean_page_candidate(" ".join(words))


def is_known_university_profile_link(source: Source, href: str) -> bool:
    parsed = urlparse(href)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()
    if source.adapter == "qubis_spinouts":
        return host == "qubis.co.uk" and path.startswith("/portfolio/")
    if source.adapter == "edinburgh_spinouts":
        return host == "bayes-centre.ed.ac.uk" and "/cohort-" in path
    if source.adapter == "mit_spinouts":
        return host == "tlo.mit.edu" and path.startswith("/industry-entrepreneurs/startups/")
    if source.adapter == "harvard_ventures":
        return host == "innovationlabs.harvard.edu" and path.startswith("/venture/")
    return False


def extract_university_profile_link_hits(source: Source, raw_html: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    seen_companies: set[str] = set()
    for link_text, href in extract_links(raw_html, source.url):
        if not is_known_university_profile_link(source, href):
            continue
        company = clean_page_candidate(link_text)
        if not is_plausible_university_company_name(company):
            company = company_name_from_profile_slug(href)
        context = local_context_for_link(raw_html, link_text, href)
        hit = make_university_spinout_hit(source, company, href, context)
        if not hit or hit.company.lower() in seen_companies:
            continue
        seen_companies.add(hit.company.lower())
        hits.append(hit)
    return hits


def make_university_spinout_hit(
    source: Source,
    company: str,
    evidence_url: str,
    context: str = "",
    website_url: str = "",
    require_bbt_relevance: bool = True,
) -> DiscoveryHit | None:
    company = clean_page_candidate(company)
    context = clean_text(context or company)
    if not is_plausible_university_company_name(company):
        return None
    if require_bbt_relevance and not is_bbt_relevant_university_context(f"{company} {context}"):
        return None
    website = website_url if is_candidate_company_website(source.url, website_url) else ""
    product_source = source
    if not require_bbt_relevance:
        product_source = Source(
            source.name,
            source.source_type,
            source.url,
            source.geography,
            source.priority,
            source.update_cadence,
            source.extraction_method,
            "",
            source.adapter,
        )
    return DiscoveryHit(
        company=company,
        source_name=source.name,
        source_type=source.source_type,
        discovery_url=evidence_url,
        discovery_rationale=f"{source.name} directory listed this university spinout, startup, alumni, or portfolio company.",
        product_type=infer_page_product_type(product_source, context),
        geography=source.geography,
        website=website,
        matched_terms=f"adapter: {source.adapter or 'university_spinout_directory'}; official university directory",
        company_description=context[:1000],
    )


def website_from_context_links(source: Source, raw_html: str) -> str:
    for link_text, href in extract_links(raw_html, source.url):
        lower_text = clean_text(link_text).lower()
        if lower_text in {"read more", "learn more", "visit the website", "website"}:
            continue
        if is_candidate_company_website(source.url, href):
            return href
    for _, href in extract_links(raw_html, source.url):
        if is_candidate_company_website(source.url, href):
            return href
    return ""


def company_from_repeated_card_text(text: str) -> tuple[str, str]:
    text = clean_text(text)
    if not text:
        return "", ""
    words = text.split()
    max_prefix_words = min(6, len(words) // 2)
    for length in range(max_prefix_words, 0, -1):
        prefix = " ".join(words[:length])
        remainder = " ".join(words[length:])
        if remainder.lower().startswith(prefix.lower()):
            return clean_page_candidate(prefix), clean_text(remainder[len(prefix) :])
        first_word = re.sub(r"[^A-Za-z0-9]+", "", words[0]).lower()
        remainder_start = re.sub(r"[^A-Za-z0-9’' ]+", "", remainder[:80]).lower()
        if first_word and (
            remainder_start.startswith(f"{first_word}'s ")
            or remainder_start.startswith(f"{first_word}’s ")
            or remainder_start.startswith(f"the {first_word} ")
        ):
            return clean_page_candidate(prefix), clean_text(remainder)
    match = re.match(r"^([A-Z][A-Za-z0-9&.'’+-]+(?:\s+[A-Z][A-Za-z0-9&.'’+-]+){0,4})\s+(.+)$", text)
    if match:
        return clean_page_candidate(match.group(1)), clean_text(match.group(2))
    return "", text


def looks_like_rcsi_company_card(text: str) -> bool:
    lower = clean_text(text).lower()
    return bool(
        re.search(
            r"\b(is developing|has developed|developed a|develops? |company|project|mission is|first product|platform|therapeutics|treatment|patients?)\b",
            lower,
        )
    )


def extract_rcsi_spinout_hits(source: Source, raw_html: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    seen: set[str] = set()
    for link_text, href in extract_links(raw_html, source.url):
        if not looks_like_rcsi_company_card(link_text):
            continue
        context = local_context_for_link(raw_html, link_text, href)
        company, description = company_from_repeated_card_text(link_text)
        if not company:
            company, description = company_from_repeated_card_text(context)
        hit = make_university_spinout_hit(source, company, href or source.url, description or context, require_bbt_relevance=False)
        if hit and hit.company.lower() not in seen:
            seen.add(hit.company.lower())
            hits.append(hit)
    return hits


def extract_heading_directory_hits(source: Source, raw_html: str, heading_pattern: str = r"h[3-5]") -> list[DiscoveryHit]:
    heading_re = re.compile(rf"(?is)<(?P<tag>{heading_pattern})\b[^>]*>(?P<title>.*?)</(?P=tag)>")
    matches = list(heading_re.finditer(raw_html))
    hits: list[DiscoveryHit] = []
    seen: set[str] = set()
    for index, match in enumerate(matches):
        chunk_end = matches[index + 1].start() if index + 1 < len(matches) else min(len(raw_html), match.end() + 3500)
        chunk = raw_html[match.start() : chunk_end]
        company = clean_page_candidate(clean_text(match.group("title")))
        context = clean_text(chunk)
        website = website_from_context_links(source, chunk)
        hit = make_university_spinout_hit(source, company, source.url, context, website, require_bbt_relevance=False)
        if hit and hit.company.lower() not in seen:
            seen.add(hit.company.lower())
            hits.append(hit)
    return hits


def rendered_json_text(value) -> str:
    if isinstance(value, dict):
        return clean_text(str(value.get("rendered") or " ".join(rendered_json_text(item) for item in value.values())))
    if isinstance(value, list):
        return clean_text(" ".join(rendered_json_text(item) for item in value))
    if value is None:
        return ""
    return clean_text(str(value))


def extract_wordpress_api_hits(source: Source, raw_text: str) -> list[DiscoveryHit]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return []
    records = payload if isinstance(payload, list) else payload.get("items", []) if isinstance(payload, dict) else []
    hits: list[DiscoveryHit] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        company = rendered_json_text(record.get("title"))
        guid = record.get("guid")
        guid_url = guid.get("rendered") if isinstance(guid, dict) else ""
        evidence_url = str(record.get("link") or guid_url or source.url)
        context_parts = [
            rendered_json_text(record.get("excerpt")),
            rendered_json_text(record.get("content")),
            rendered_json_text(record.get("acf")),
        ]
        context = clean_text(" ".join(part for part in context_parts if part))
        website = website_from_context_links(source, str(record.get("content", {}).get("rendered") or ""))
        hit = make_university_spinout_hit(source, company, evidence_url, context, website, require_bbt_relevance=False)
        if hit and hit.company.lower() not in seen:
            seen.add(hit.company.lower())
            hits.append(hit)
    return hits


def extract_oxford_innovation_finance_hits(source: Source, raw_html: str) -> list[DiscoveryHit]:
    starts = [match.start() for match in re.finditer(r'(?is)<div\s+data-elementor-type="loop-item"', raw_html)]
    hits: list[DiscoveryHit] = []
    seen: set[str] = set()
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else min(len(raw_html), start + 8000)
        chunk = raw_html[start:end]
        if "portfolio type-portfolio" not in chunk or "company-name" not in chunk:
            continue
        website_match = re.search(r'(?is)<a\b[^>]+class="[^"]*loop-card[^"]*"[^>]+href="([^"]+)"', chunk)
        company_match = re.search(r'(?is)company-name.*?<p[^>]*>(.*?)</p>', chunk)
        if not website_match or not company_match:
            continue
        company = clean_text(company_match.group(1))
        website = website_match.group(1)
        context = clean_text(chunk)
        if "category-health-science" not in chunk and "Health & Science" not in context and not is_bbt_relevant_university_context(context):
            continue
        hit = make_university_spinout_hit(source, company, source.url, context, website)
        if hit and hit.company.lower() not in seen:
            seen.add(hit.company.lower())
            hits.append(hit)
    return hits


def extract_university_company_card_hits(source: Source, raw_html: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    if "oxfordinnovationfinance.co.uk" in source.url:
        return extract_oxford_innovation_finance_hits(source, raw_html)
    starts = [match.start() for match in re.finditer(r'(?is)<div\s+about="/company/', raw_html)]
    if not starts:
        starts = [match.start() for match in re.finditer(r'(?is)<div\s+id="company-', raw_html)]
    chunks = []
    lower_html = raw_html.lower()
    for index, start in enumerate(starts):
        candidates = []
        if index + 1 < len(starts):
            candidates.append(starts[index + 1])
        for marker in ('class="pager', 'class="pagination', "<footer"):
            marker_index = lower_html.find(marker, start + 1)
            if marker_index >= 0:
                candidates.append(marker_index)
        end = min(candidates) if candidates else min(len(raw_html), start + 5000)
        chunks.append(raw_html[start:end])
    if not chunks:
        chunks = re.split(r'(?i)<div[^>]+class="[^"]*(?:company-card|portfolio-card)[^"]*"[^>]*>', raw_html)
    for chunk in chunks:
        if not re.search(r"(?i)(company-card|portfolio|spinout|startup|start-up|id=\"company-)", chunk):
            continue
        heading = re.search(r"(?is)<h[2-4][^>]*>(.*?)</h[2-4]>", chunk)
        if not heading:
            continue
        company = clean_page_candidate(clean_text(heading.group(1)))
        context_chunk = re.split(r"(?is)<div[^>]*class=\"[^\"]*related-articles", chunk, maxsplit=1)[0]
        website = ""
        for link_text, href in extract_links(context_chunk, source.url):
            if clean_text(link_text).lower() == "visit the website" and is_candidate_company_website(source.url, href):
                website = href
                break
        if not website:
            for link_text, href in extract_links(context_chunk, source.url):
                if is_candidate_company_website(source.url, href):
                    website = href
                    break
        if website and "linkedin.com/" in website.lower():
            website = ""
        hit = make_university_spinout_hit(source, company, source.url, clean_text(context_chunk), website)
        if hit:
            hits.append(hit)
    return hits


def has_structured_company_cards(raw_html: str) -> bool:
    return bool(re.search(r'(?is)<div\s+(?:about="/company/|id="company-|data-elementor-type="loop-item")', raw_html))


def extract_university_link_hits(source: Source, raw_html: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    seen_companies: set[str] = set()
    for link_text, href in extract_links(raw_html, source.url):
        context = local_context_for_link(raw_html, link_text, href)
        hit = make_university_spinout_hit(source, link_text, source.url, context, href)
        if not hit or hit.company.lower() in seen_companies:
            continue
        if not hit.website:
            continue
        seen_companies.add(hit.company.lower())
        hits.append(hit)
    return hits


def build_university_spinout_evidence(source: Source, raw_html: str) -> tuple[list[DiscoveryHit], list[TriggerEvent]]:
    discovery_hits: list[DiscoveryHit] = []
    if "wp-json/wp/v2/startups" in source.url:
        discovery_hits = extract_wordpress_api_hits(source, raw_html)
    elif "rcsi.com" in source.url and "spin-outs" in source.url:
        discovery_hits = extract_rcsi_spinout_hits(source, raw_html)
    elif "lrd.kuleuven.be" in source.url and "spin-off-companies" in source.url:
        discovery_hits = extract_heading_directory_hits(source, raw_html, "h4")
    elif "kiinnovation.se" in source.url and "incubator-companies" in source.url:
        discovery_hits = extract_heading_directory_hits(source, raw_html, "h5")
    if not discovery_hits:
        discovery_hits = extract_university_profile_link_hits(source, raw_html)
    if not discovery_hits and has_structured_company_cards(raw_html):
        discovery_hits = extract_university_company_card_hits(source, raw_html)
    trigger_events: list[TriggerEvent] = []
    if not discovery_hits and not has_structured_company_cards(raw_html):
        discovery_hits = extract_university_link_hits(source, raw_html)

    for hit in discovery_hits:
        trigger = source_type_trigger_event(source, hit.company)
        if trigger:
            trigger_events.append(TriggerEvent(hit.company, trigger[0], trigger[1], source.name, hit.discovery_url))
    return discovery_hits, trigger_events


def curated_university_spinout_hits(source: Source) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    for item in CURATED_UNIVERSITY_SPINOUTS.get(source.name, []):
        context = clean_text(str(item.get("description") or ""))
        hit = make_university_spinout_hit(
            source,
            str(item.get("company") or ""),
            str(item.get("evidence_url") or source.url),
            context,
            str(item.get("website") or ""),
            require_bbt_relevance=False,
        )
        if hit:
            hit.company_description = context
            hit.matched_terms = f"adapter: {source.adapter or 'university_spinout_directory'}; curated official source fallback"
            hits.append(hit)
    return hits


def run_university_spinout_pages(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = UNIVERSITY_SPINOUT_SOURCE_PAGES.get(source.name, [])
    if not urls:
        curated_hits = curated_university_spinout_hits(source)
        curated_triggers = []
        for hit in curated_hits:
            trigger = source_type_trigger_event(source, hit.company)
            if trigger:
                curated_triggers.append(TriggerEvent(hit.company, trigger[0], trigger[1], source.name, hit.discovery_url))
        if not curated_hits:
            return [], [], "0 configured university directory pages; skipped fail-closed"
        return curated_hits, curated_triggers, f"0 configured university directory pages; {len(curated_hits)} curated fallback hits"

    all_hits: list[DiscoveryHit] = []
    all_triggers: list[TriggerEvent] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    curated_count = 0
    for url in urls:
        adapter = source.adapter or "university_spinout_directory"
        page_source = Source(source.name, source.source_type, url, source.geography, source.priority, source.update_cadence, source.extraction_method, source.notes, adapter)
        raw_html, error = fetch_raw_text(url)
        if error:
            errors.append(f"{url}: {error}")
            continue
        hits, triggers = build_university_spinout_evidence(page_source, raw_html)
        for hit in hits:
            key = (hit.company.lower(), hit.discovery_url)
            if key in seen:
                continue
            seen.add(key)
            all_hits.append(hit)
        all_triggers.extend(triggers)
    for hit in curated_university_spinout_hits(source):
        key = (hit.company.lower(), hit.discovery_url)
        if key in seen:
            continue
        seen.add(key)
        all_hits.append(hit)
        curated_count += 1
        trigger = source_type_trigger_event(source, hit.company)
        if trigger:
            all_triggers.append(TriggerEvent(hit.company, trigger[0], trigger[1], source.name, hit.discovery_url))
    result = f"{len(urls)} configured university directory pages; {len(all_hits)} discovery hits; {len(all_triggers)} trigger events"
    if curated_count:
        result += f"; {curated_count} curated fallback hits"
    if errors:
        result += "; errors: " + " | ".join(errors[:5])
    return all_hits, all_triggers, result
