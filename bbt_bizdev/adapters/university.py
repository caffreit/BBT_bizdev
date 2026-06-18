from __future__ import annotations

import re

from ..config import UNIVERSITY_SPINOUT_SOURCE_PAGES
from ..http import fetch_raw_text
from ..models import DiscoveryHit, Source, TriggerEvent
from ..text import clean_page_candidate, clean_text, extract_links, infer_page_product_type, is_plausible_page_candidate, source_type_trigger_event, text_from_html
from .accelerators import dedupe_hits_with_triggers
from .generic import find_companies_on_source


def is_relevant_university_spinout_link(link_text: str, href: str) -> bool:
    lower_href = href.lower()
    if lower_href.startswith(("javascript:", "mailto:", "tel:")) or "#" in lower_href:
        return False
    blocked_href_terms = [
        "team", "people", "staff", "advisor", "board", "event", "login", "application",
        "apply", "contact", "privacy", "cookie", "terms", "accessibility",
    ]
    if any(term in lower_href for term in blocked_href_terms):
        return False
    positive_href_terms = [
        "spin", "startup", "start-up", "venture", "compan", "portfolio", "commercial",
        "innovation", "news", "story", "stories", "case",
    ]
    positive_text_terms = [
        "spinout", "spin-out", "startup", "start-up", "campus company", "company",
        "venture", "launch", "raises", "funding", "healthtech", "medtech",
    ]
    lower_text = clean_text(link_text).lower()
    return any(term in lower_href for term in positive_href_terms) or any(term in lower_text for term in positive_text_terms)

def make_university_spinout_hit(source: Source, company: str, evidence_url: str, context: str = "") -> DiscoveryHit | None:
    company = clean_page_candidate(company)
    if re.search(r"\b(announces|collaborates|launches|partners|raises|secures|wins)\b", company, flags=re.I):
        return None
    if not is_plausible_page_candidate(company):
        return None
    return DiscoveryHit(
        company=company,
        source_name=source.name,
        source_type=source.source_type,
        discovery_url=evidence_url,
        discovery_rationale=f"{source.name} adapter found a company-like listing on university innovation, spinout, portfolio, or news pages.",
        product_type=infer_page_product_type(source, context or company),
        geography=source.geography,
        matched_terms=f"adapter: {source.adapter}; university spinout page scan",
        company_description=clean_text(context)[:1000],
    )

def build_university_spinout_evidence(source: Source, raw_html: str) -> tuple[list[DiscoveryHit], list[TriggerEvent]]:
    discovery_hits = find_companies_on_source(source, text_from_html(raw_html))
    trigger_events: list[TriggerEvent] = []
    seen_companies = {hit.company.lower() for hit in discovery_hits}

    for hit in discovery_hits:
        hit.matched_terms = hit.matched_terms or f"adapter: {source.adapter}; registry alias"
        trigger = source_type_trigger_event(source, hit.company)
        if trigger:
            trigger_events.append(TriggerEvent(hit.company, trigger[0], trigger[1], source.name, hit.discovery_url))

    for link_text, href in extract_links(raw_html, source.url):
        if not is_relevant_university_spinout_link(link_text, href):
            continue
        hit = make_university_spinout_hit(source, link_text, href, link_text)
        if not hit or hit.company.lower() in seen_companies:
            continue
        seen_companies.add(hit.company.lower())
        discovery_hits.append(hit)
        trigger = source_type_trigger_event(source, hit.company)
        if trigger:
            trigger_events.append(TriggerEvent(hit.company, trigger[0], trigger[1], source.name, hit.discovery_url))
    return discovery_hits, trigger_events

def run_university_spinout_pages(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = UNIVERSITY_SPINOUT_SOURCE_PAGES.get(source.name, [source.url])
    all_hits: list[DiscoveryHit] = []
    all_triggers: list[TriggerEvent] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for url in urls:
        page_source = Source(source.name, source.source_type, url, source.geography, source.priority, source.update_cadence, source.extraction_method, source.notes, source.adapter)
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
    result = f"{len(urls)} university spinout pages; {len(all_hits)} discovery hits; {len(all_triggers)} trigger events"
    if errors:
        result += "; errors: " + " | ".join(errors[:5])
    return all_hits, all_triggers, result

def run_accelerator_pages(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    urls = ACCELERATOR_SOURCE_PAGES.get(source.name, [source.url])
    all_hits: list[DiscoveryHit] = []
    all_triggers: list[TriggerEvent] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for url in urls:
        page_source = Source(source.name, source.source_type, url, source.geography, source.priority, source.update_cadence, source.extraction_method, source.notes, source.adapter)
        raw_html, error = fetch_raw_text(url)
        if error:
            errors.append(f"{url}: {error}")
            continue
        hits, triggers = build_source_page_evidence(page_source, raw_html)
        for hit in hits:
            key = (hit.company.lower(), hit.discovery_url)
            if key in seen:
                continue
            seen.add(key)
            all_hits.append(hit)
        all_triggers.extend(triggers)
    result = f"{len(urls)} accelerator pages; {len(all_hits)} discovery hits; {len(all_triggers)} trigger events"
    if errors:
        result += "; errors: " + " | ".join(errors)
    return all_hits, all_triggers, result

