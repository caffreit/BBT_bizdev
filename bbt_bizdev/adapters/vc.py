from __future__ import annotations

import re

from ..http import fetch_raw_text
from ..models import DiscoveryHit, Source, TriggerEvent
from ..text import clean_text, extract_links, infer_page_product_type, is_plausible_page_candidate, source_type_trigger_event, text_from_html


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

def is_vc_portfolio_company_link(link_text: str, href: str) -> bool:
    if not is_plausible_page_candidate(link_text):
        return False
    lower_href = href.lower()
    if lower_href.startswith(("javascript:", "mailto:", "tel:")) or "#" in lower_href:
        return False
    if any(term in lower_href for term in ["team", "people", "advisor", "news", "blog", "contact", "about", "privacy", "linkedin"]):
        return False
    return any(term in lower_href for term in ["portfolio", "company", "companies", "investment", "venture"])

def parse_vc_portfolio_page(source: Source, raw_html: str, page_url: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    for link_text, href in extract_links(raw_html, page_url):
        if not is_vc_portfolio_company_link(link_text, href):
            continue
        context = context_after_link(raw_html, href) or context_around_link_text(raw_html, link_text)
        category = ""
        for label in ["Sector", "Category", "Stage", "Focus"]:
            match = re.search(rf"{label}\s*:?\s*([A-Za-z0-9 /,&+-]{{3,80}})", context, flags=re.I)
            if match:
                category = clean_text(match.group(1))
                break
        hits.append(
            DiscoveryHit(
                company=clean_text(link_text),
                source_name=source.name,
                source_type=source.source_type,
                discovery_url=href,
                discovery_rationale=f"{source.name} adapter extracted this company from an investor portfolio source.",
                product_type=infer_page_product_type(source, " ".join([category, context])),
                geography=source.geography,
                matched_terms=f"adapter: {source.adapter}; portfolio/company link",
                category_or_track=category,
                company_description=context,
            )
        )
    if not hits:
        hits.extend(parse_vc_portfolio_text_blocks(source, raw_html, page_url))
    return hits

def parse_vc_portfolio_text_blocks(source: Source, raw_html: str, page_url: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    text = text_from_html(raw_html)
    pattern = re.compile(
        r"\b(?P<company>[A-Z][A-Za-z0-9&.+’'\- ]{1,70}?)(?:\s+\([A-Z0-9.:\- ]{1,16}\))?\s+"
        r"(?P<verb>is|are|has|have|helps|offers|provides|produces|uses|allows|connects|develops|developed|developing|commercializing|commercialising|discovers|operates)\b"
        r"(?P<body>.{20,260}?)(?=\s+[A-Z][A-Za-z0-9&.+’'\- ]{1,70}?(?:\s+\([A-Z0-9.:\- ]{1,16}\))?\s+(?:is|are|has|have|helps|offers|provides|produces|uses|allows|connects|develops|developed|developing|commercializing|commercialising|discovers|operates)\b|$)",
        flags=re.S,
    )
    for match in pattern.finditer(text):
        company = clean_text(match.group("company"))
        company = re.sub(r"\s+\([A-Z0-9.:\- ]{1,16}\)$", "", company)
        if not is_plausible_page_candidate(company):
            continue
        context = clean_text(f"{company} {match.group('verb')} {match.group('body')}")
        hits.append(
            DiscoveryHit(
                company=company,
                source_name=source.name,
                source_type=source.source_type,
                discovery_url=page_url,
                discovery_rationale=f"{source.name} adapter extracted this company from investor portfolio page text.",
                product_type=infer_page_product_type(source, context),
                geography=source.geography,
                matched_terms=f"adapter: {source.adapter}; portfolio text block",
                company_description=context,
            )
        )
    return hits

def dedupe_vc_hits_with_triggers(source: Source, hits: list[DiscoveryHit]) -> tuple[list[DiscoveryHit], list[TriggerEvent]]:
    deduped: list[DiscoveryHit] = []
    triggers: list[TriggerEvent] = []
    seen: set[tuple[str, str]] = set()
    for hit in hits:
        if not is_plausible_page_candidate(hit.company):
            continue
        key = (hit.company.lower(), hit.discovery_url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
        trigger = source_type_trigger_event(source, hit.company)
        if trigger:
            triggers.append(TriggerEvent(hit.company, trigger[0], trigger[1], source.name, hit.discovery_url))
    return deduped, triggers

def run_vc_portfolio_adapter(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    raw_html, error = fetch_raw_text(source.url)
    if error:
        return [], [], f"{source.url}: {error}"
    hits, triggers = dedupe_vc_hits_with_triggers(source, parse_vc_portfolio_page(source, raw_html, source.url))
    result = f"1 VC portfolio page scanned; {len(hits)} discovery hits; {len(triggers)} trigger events"
    if not hits:
        result = f"INCOMPLETE {source.name} extraction: no portfolio company links found. " + result
    return hits, triggers, result

def run_fountain_healthcare(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    return run_vc_portfolio_adapter(source)

def run_seroba_life_sciences(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    return run_vc_portfolio_adapter(source)

def run_atlantic_bridge(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    return run_vc_portfolio_adapter(source)
