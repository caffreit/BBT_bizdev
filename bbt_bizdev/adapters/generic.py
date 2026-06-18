from __future__ import annotations

from ..config import COMPANY_REGISTRY
from ..models import DiscoveryHit, Source, TriggerEvent
from ..text import (
    clean_page_candidate, extract_links, infer_page_product_type, is_plausible_page_candidate,
    is_relevant_candidate_link, source_type_trigger_event, text_from_html,
)


def build_source_page_evidence(source: Source, raw_html: str, max_candidates: int = 25) -> tuple[list[DiscoveryHit], list[TriggerEvent]]:
    text = text_from_html(raw_html)
    discovery_hits = find_companies_on_source(source, text)
    trigger_events: list[TriggerEvent] = []
    seen_companies = {hit.company.lower() for hit in discovery_hits}

    for hit in discovery_hits:
        trigger = source_type_trigger_event(source, hit.company)
        if trigger:
            trigger_events.append(TriggerEvent(hit.company, trigger[0], trigger[1], source.name, hit.discovery_url))

    for link_text, href in extract_links(raw_html, source.url):
        if not is_relevant_candidate_link(source, link_text, href):
            continue
        company = clean_page_candidate(link_text)
        if company.lower() in seen_companies:
            continue
        seen_companies.add(company.lower())
        matched_terms = f"adapter: {source.adapter}; link text"
        discovery_hits.append(
            DiscoveryHit(
                company=company,
                source_name=source.name,
                source_type=source.source_type,
                discovery_url=href,
                discovery_rationale=f"{source.source_type} adapter found company-like link text on '{source.name}'.",
                product_type=infer_page_product_type(source, link_text),
                geography=source.geography,
                website="",
                matched_terms=matched_terms,
            )
        )
        trigger = source_type_trigger_event(source, company)
        if trigger:
            trigger_events.append(TriggerEvent(company, trigger[0], trigger[1], source.name, href))
        if len(discovery_hits) >= max_candidates:
            break
    return discovery_hits, trigger_events

def find_companies_on_source(source: Source, text: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    lower_text = text.lower()
    for company, meta in COMPANY_REGISTRY.items():
        matched = [alias for alias in meta["aliases"] if alias.lower() in lower_text]
        if not matched:
            continue
        rationale = f"Company name appeared on approved discovery source '{source.name}'."
        if source.name == "TIME HealthTech 2025":
            rationale = "Company appeared in TIME HealthTech 2025 ranking/article."
        hits.append(
            DiscoveryHit(
                company=company,
                source_name=source.name,
                source_type=source.source_type,
                discovery_url=source.url,
                discovery_rationale=rationale,
                product_type=meta["product_type"],
                geography=meta["geography"],
                website=meta["website"],
                matched_terms=", ".join(matched),
            )
        )
    return hits

