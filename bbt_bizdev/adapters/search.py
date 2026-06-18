from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from ..config import COMPANY_REGISTRY, SEARCH_QUERIES
from ..http import fetch_raw_text, fetch_text
from ..models import DiscoveryHit, SearchResult, Source, TriggerEvent
from ..text import article_title_without_publisher, clean_text, extract_company_from_search_result


def google_news_rss_url(query: str) -> str:
    return "https://news.google.com/rss/search?" + urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})

def parse_google_news_rss(xml_text: str, query: str) -> list[SearchResult]:
    root = ET.fromstring(xml_text)
    results: list[SearchResult] = []
    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title", ""))
        link = clean_text(item.findtext("link", ""))
        summary = clean_text(item.findtext("description", ""))
        publisher = clean_text(item.findtext("source", ""))
        published_at = clean_text(item.findtext("pubDate", ""))
        if title and link:
            results.append(SearchResult(query=query, title=title, link=link, summary=summary, publisher=publisher, published_at=published_at))
    return results

def classify_search_trigger(result: SearchResult) -> tuple[str, str] | None:
    text = f"{result.title} {result.summary}".lower()
    title = article_title_without_publisher(result.title)
    if re.search(r"\b(series [a-z]|seed|pre-seed|funding|raises?|raised|lands?|landed|secures?|secured|closes?|closed|\$\d)", text):
        return "Funding", f"Funding signal from Google News result: {title}"
    if re.search(r"\b(fda clearance|fda clears|510\(k\)|de novo|ce mark|regulatory clearance|clearance|cleared)\b", text):
        return "Regulatory clearance", f"Regulatory clearance signal from Google News result: {title}"
    if re.search(r"\b(launches?|launched|unveils?|unveiled|commercial launch)\b", text):
        return "Launch", f"Launch signal from Google News result: {title}"
    if re.search(r"\b(approval|approved|authori[sz]ed)\b", text):
        return "Approval", f"Approval signal from Google News result: {title}"
    return None

def infer_product_type(result: SearchResult, company: str) -> str:
    registry_meta = COMPANY_REGISTRY.get(company)
    if registry_meta:
        return registry_meta["product_type"]
    text = f"{result.query} {result.title} {result.summary}".lower()
    if "samd" in text:
        return "SaMD / health software"
    if "medical device" in text or "device" in text:
        return "Medical device"
    if "fda" in text or "clearance" in text or "regulatory" in text:
        return "Regulated digital health / device"
    if "ai" in text:
        return "AI health / medtech"
    return "Digital health / medtech"

def infer_geography(company: str) -> str:
    registry_meta = COMPANY_REGISTRY.get(company)
    return registry_meta["geography"] if registry_meta else "Unknown"

def infer_website(company: str) -> str:
    registry_meta = COMPANY_REGISTRY.get(company)
    return registry_meta["website"] if registry_meta else ""

def search_result_matched_terms(result: SearchResult, trigger_type: str | None) -> str:
    terms = [f"query: {result.query}"]
    if trigger_type:
        terms.append(f"trigger: {trigger_type}")
    return "; ".join(terms)

def build_google_news_evidence(source: Source, results: list[SearchResult]) -> tuple[list[DiscoveryHit], list[TriggerEvent]]:
    discovery_hits: list[DiscoveryHit] = []
    trigger_events: list[TriggerEvent] = []
    seen_discovery: set[tuple[str, str]] = set()
    seen_trigger: set[tuple[str, str, str]] = set()

    for result in results:
        company = extract_company_from_search_result(result)
        if not company:
            continue
        trigger = classify_search_trigger(result)
        discovery_key = (company.lower(), result.link)
        if discovery_key not in seen_discovery:
            seen_discovery.add(discovery_key)
            discovery_hits.append(
                DiscoveryHit(
                    company=company,
                    source_name=f"{source.name}: {result.query}",
                    source_type=source.source_type,
                    discovery_url=result.link,
                    discovery_rationale=f"Google News result for query '{result.query}' named the company in the title/snippet.",
                    product_type=infer_product_type(result, company),
                    geography=infer_geography(company),
                    website=infer_website(company),
                    matched_terms=search_result_matched_terms(result, trigger[0] if trigger else None),
                )
            )
        if trigger:
            trigger_key = (company.lower(), trigger[0], result.link)
            if trigger_key in seen_trigger:
                continue
            seen_trigger.add(trigger_key)
            trigger_events.append(
                TriggerEvent(
                    company=company,
                    trigger_type=trigger[0],
                    trigger_event=trigger[1],
                    trigger_source=f"{source.name}: {result.query}",
                    evidence_url=result.link,
                )
            )
    return discovery_hits, trigger_events

def run_google_news_search(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    all_results: list[SearchResult] = []
    errors: list[str] = []
    for query in SEARCH_QUERIES:
        rss_url = google_news_rss_url(query)
        xml_text, error = fetch_raw_text(rss_url)
        if error:
            errors.append(f"{query}: {error}")
            continue
        try:
            all_results.extend(parse_google_news_rss(xml_text, query))
        except ET.ParseError as exc:
            errors.append(f"{query}: RSS parse failed: {exc}")
    discovery_hits, trigger_events = build_google_news_evidence(source, all_results)
    result = f"{len(all_results)} RSS items; {len(discovery_hits)} discovery hits; {len(trigger_events)} trigger events"
    if errors:
        result += "; errors: " + " | ".join(errors)
    return discovery_hits, trigger_events, result

