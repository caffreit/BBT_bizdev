from __future__ import annotations

import csv
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from ..http import fetch_raw_text
from ..models import DiscoveryHit, Source, TriggerEvent
from ..text import clean_page_candidate, clean_text, extract_links, infer_page_product_type, is_plausible_page_candidate, text_from_html
from .accelerators import matched_ndrc_healthcare_keywords


SIFTED_CSV_DIR_ENV = "BBT_SIFTED_CSV_DIR"


def sifted_has_health_relevance(source: Source, context: str) -> bool:
    text = context.lower()
    if matched_ndrc_healthcare_keywords(text) or re.search(r"\b(sa?md|medtech|healthtech|health tech|biotech|life sciences?)\b", text):
        return True
    if not clean_text(context):
        source_text = f"{source.name} {source.notes}".lower()
        return bool(matched_ndrc_healthcare_keywords(source_text) or re.search(r"\b(sa?md|medtech|healthtech|health tech|biotech|life sciences?)\b", source_text))
    return False


def sifted_local_csv_candidates(source: Source) -> list[Path]:
    base = Path(os.environ.get(SIFTED_CSV_DIR_ENV, "data/sifted"))
    slug = re.sub(r"[^a-z0-9]+", "-", source.name.lower()).strip("-")
    return [base / f"{slug}.csv", base / "sifted.csv"]


def parse_sifted_csv(source: Source, csv_text: str, evidence_url: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    reader = csv.DictReader(csv_text.splitlines())
    for row in reader:
        company = clean_page_candidate(row.get("Company") or row.get("company") or row.get("Name") or row.get("name") or "")
        if not is_plausible_page_candidate(company):
            continue
        context = " ".join(clean_text(str(value)) for value in row.values() if value)
        if not sifted_has_health_relevance(source, context):
            continue
        website = row.get("Website") or row.get("website") or row.get("URL") or row.get("url") or ""
        hits.append(
            DiscoveryHit(
                company=company,
                source_name=source.name,
                source_type=source.source_type,
                discovery_url=website or evidence_url,
                discovery_rationale=f"{source.name} Sifted CSV export listed this health-relevant company.",
                product_type=infer_page_product_type(source, context),
                geography=row.get("Location") or row.get("location") or source.geography,
                website=website,
                matched_terms="adapter: sifted_ranking; local csv",
                company_description=context,
            )
        )
    return hits


def parse_sifted_ranking_page(source: Source, raw_html: str, page_url: str) -> tuple[list[DiscoveryHit], bool]:
    hits: list[DiscoveryHit] = []
    anonymized = "Anonymized Company" in raw_html
    page_text = text_from_html(raw_html)
    seen: set[str] = set()
    for link_text, href in extract_links(raw_html, page_url):
        host = urlparse(href).netloc.lower()
        if not host or host.endswith("sifted.eu"):
            continue
        company = clean_page_candidate(link_text)
        if company.lower() in seen or not is_plausible_page_candidate(company):
            continue
        context_match = re.search(rf"{re.escape(link_text)}(.{{0,600}})", page_text, flags=re.I | re.S)
        context = clean_text(context_match.group(0) if context_match else link_text)
        if not sifted_has_health_relevance(source, context):
            continue
        seen.add(company.lower())
        hits.append(
            DiscoveryHit(
                company=company,
                source_name=source.name,
                source_type=source.source_type,
                discovery_url=href,
                discovery_rationale=f"{source.name} public Sifted ranking listed this health-relevant company.",
                product_type=infer_page_product_type(source, context),
                geography=source.geography,
                website=href,
                matched_terms="adapter: sifted_ranking; public ranking page",
                company_description=context,
            )
        )
    return hits, anonymized and not hits


def run_sifted_ranking(source: Source) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    csv_hits: list[DiscoveryHit] = []
    for path in sifted_local_csv_candidates(source):
        if not path.exists():
            continue
        try:
            csv_hits.extend(parse_sifted_csv(source, path.read_text(encoding="utf-8-sig"), str(path)))
        except OSError:
            continue
    if csv_hits:
        return csv_hits, [], f"Local Sifted CSV import; {len(csv_hits)} health-relevant discovery hits"

    raw_html, error = fetch_raw_text(source.url)
    if error:
        return [], [], f"{source.url}: {error}"
    hits, anonymized = parse_sifted_ranking_page(source, raw_html, source.url)
    if anonymized:
        return [], [], "Sifted page is anonymized/paywalled; prioritization only"
    result = f"Sifted public ranking page scanned; {len(hits)} health-relevant discovery hits"
    if not hits:
        result += "; prioritization only"
    return hits, [], result
