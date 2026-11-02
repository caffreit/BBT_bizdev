"""Adapters for the three national AI institutes: Vector, Amii and Mila.

None of the institutes publishes a complete startup directory, so each runner
targets the official page that names companies and filters to health/life
sciences. Counts are checked against the live pages recorded in
CANADA_TIER_A_ADAPTER_PLAN.md.
"""
from __future__ import annotations

import json
import re

from ..http import fetch_raw_text
from ..models import DiscoveryHit, Source, TriggerEvent
from ..text import clean_text, text_from_html
from .accelerators import dedupe_hits_with_triggers, make_accelerator_hit
from .canada_tier_a import _tag_text, blocks_by_class


HEALTH_SECTOR_TERMS = (
    "health", "medical", "clinical", "biotech", "life science", "pharma",
    "drug", "therapeut", "antibod", "neuro", "diagnos", "genomic", "oncology", "cancer",
    "dental", "surgical",
)

CITY_PROVINCES = {
    "calgary": "AB", "edmonton": "AB",
    "vancouver": "BC", "surrey": "BC",
    "saint john": "NB",
    "halifax": "NS",
    "toronto": "ON", "ottawa": "ON", "kingston": "ON", "kitchener-waterloo": "ON", "waterloo": "ON",
    "montreal": "QC", "montréal": "QC", "quebec city": "QC", "québec": "QC",
    "saskatoon": "SK",
}

# Vector AI20: editions are WordPress posts; add new editions here as Vector publishes them.
VECTOR_AI20_EDITIONS = [
    ("Vector AI20 for 2023", "2023", "vectors-ai20-for-2023"),
]
VECTOR_AI20_POST_API = "https://vectorinstitute.ai/wp-json/wp/v2/posts?slug={slug}&_fields=link,content"
VECTOR_AI20_EXPECTED_TOTAL = 20
VECTOR_AI20_EXPECTED_HEALTH = 4
# Five 2023 profile modals are published empty; sector and HQ for those rows are curated.
VECTOR_AI20_CURATED_PROFILES = {
    "BrainBox AI": ("Building energy management", "Montreal"),
    "Certn": ("Background screening", "Victoria"),
    "co:here": ("Large language models", "Toronto"),
    "DarwinAI": ("Manufacturing visual inspection", "Waterloo"),
    "Deep Genomics": ("Health / drug discovery", "Toronto"),
}

VECTOR_HEALTHSPARK_EXPECTED = 7
VECTOR_HEALTHSPARK_COHORT = "HealthSpark 2026-2027"

AMII_LEVEL_UP_HEALTH_EXPECTED = 9

# Mila no longer publishes a startup list; every record cites a mila.quebec
# announcement that the runner re-fetches to confirm the company is named.
MILA_STARTUP_STATUS_URL = "https://mila.quebec/en/news/four-new-companies-obtain-the-mila-startup-status"
MILA_STARTUPS = [
    # company, evidence URL, sector, geography
    ("Apex", MILA_STARTUP_STATUS_URL, "Economic simulation", "Canada"),
    ("Chapa", MILA_STARTUP_STATUS_URL, "Financial services", "Ethiopia"),
    ("Raiv Computers", MILA_STARTUP_STATUS_URL, "Neurotechnology", "Canada"),
    ("Wise Algorithms", MILA_STARTUP_STATUS_URL, "Antibody drug discovery", "Canada"),
    ("Korbit", "https://mila.quebec/en/news/korbit-a-startup-born-in-mila-raises-2-million-to-transform-education", "Education", "Montreal, QC"),
    ("Entalpic", "https://mila.quebec/en/news/entalpic-a-startup-leveraging-generative-ai-to-reduce-co2-emissions", "Materials discovery", ""),
    ("SilicoLabs", "https://mila.quebec/en/news/modernizing-cognitive-health-research-with-silicolabs", "Cognitive health research", "Montreal, QC"),
]
MILA_STARTUPS_EXPECTED_HEALTH = 3
MILA_HEALTH_PARTNERS = [
    ("Gray Oncology Solutions", "https://mila.quebec/en/news/mila-announces-partnership-with-gray-oncology-solutions-a-quebec-based-startup-optimizing", "Oncology patient flow", "Montreal, QC"),
    ("iCAD Dental", "https://mila.quebec/en/news/mila-announces-partnership-with-icad-dental-to-bolster-ai-technologies-in-dental-design", "Dental prosthesis design", "Montreal, QC"),
    ("Momentum Health", "https://mila.quebec/en/news/momentum-health-partners-with-mila-to-accelerate-the-integration-of-momentum-spine-into-the", "Digital health / 3D imaging", "Montreal, QC"),
    ("MUUTAA", "https://mila.quebec/en/news/muutaa-and-mila-announce-partnership-to-advance-ai-in-healthcare-supply-chains", "Healthcare supply chain", "Quebec City, QC"),
    ("Linda Lifetech", "https://mila.quebec/en/news/canadian-healthtech-linda-lifetech-announces-partnership-with-mila-to-advance-ai-in-breast", "Breast cancer detection", "Toronto, ON"),
    ("Linearis", "https://mila.quebec/en/news/linearis-partners-with-mila-in-a-vast-biomanufacturing-funding-initiative", "Metabolomics / drug discovery", "Quebec City, QC"),
    ("Ability Biologics", "https://mila.quebec/en/news/mila-partners-with-ability-biologics-to-advance-ai-innovations-in-antibody-discovery", "Antibody discovery", "Quebec, Canada"),
    ("Vetted Medical", "https://mila.quebec/en/news/mila-and-vetted-medical-join-forces-to-promote-responsible-adoption-of-ai-in-healthcare", "Medical AI validation", "Montreal, QC"),
    ("Secai", "https://mila.quebec/en/news/secai-partners-with-mila-to-transform-healthcare-workflow-with-ai", "Clinical workflow AI", "Montreal, QC"),
]
MILA_HEALTH_PARTNERS_EXPECTED = 9


def is_health_sector(sector: str) -> bool:
    lowered = sector.lower()
    return any(term in lowered for term in HEALTH_SECTOR_TERMS)


def institute_geography(location: str) -> str:
    """Return 'City, PROV' when the city is known, so consolidation can read both."""
    location = clean_text(location)
    match = re.match(r"(.+?),\s*([A-Za-z]{2})$", location)
    if match:
        province = match.group(2).upper()
        return f"{match.group(1)}, {'QC' if province == 'PQ' else province}"
    province = CITY_PROVINCES.get(location.lower())
    return f"{location}, {province}" if province else (location or "Canada")


def _counts(included: int, excluded: int) -> str:
    return f"{included} health included, {excluded} non-health excluded"


def parse_vector_ai20(source: Source, raw_html: str, evidence_url: str, cohort: str, year: str) -> tuple[list[DiscoveryHit], int, int]:
    """Return (health hits, listed companies, non-health excluded)."""
    names = [_tag_text(block, "p") for block in blocks_by_class(raw_html, "article", "institutions__institution")]
    slides = blocks_by_class(raw_html, "div", "modal__slide")
    hits, excluded = [], 0
    for index, company in enumerate(names):
        slide = slides[index] if index < len(slides) else ""
        sector = _labelled_value(slide, "Sector")
        headquarters = _labelled_value(slide, "Headquarters")
        curated = ""
        if not sector and company in VECTOR_AI20_CURATED_PROFILES:
            sector, headquarters = VECTOR_AI20_CURATED_PROFILES[company]
            curated = "; sector/HQ curated because the official profile modal is empty"
        if not is_health_sector(sector):
            excluded += 1
            continue
        website = re.search(r'class="modal__link".*?href="([^"]+)"', slide, flags=re.S)
        description = next(
            (text_from_html(p) for p in re.findall(r"<p>(.*?)</p>", slide, flags=re.S) if "<strong>" not in p),
            "",
        )
        hit = make_accelerator_hit(
            source, company, evidence_url, accelerator_program="Vector Institute",
            cohort_label=cohort, cohort_year=year, category_or_track=sector,
            company_description=description, website=website.group(1) if website else "",
            geography=institute_geography(headquarters),
            matched_terms=f"adapter: vector_ai20; official sector: {sector}{curated}",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits, len(names), excluded


def _labelled_value(block: str, label: str) -> str:
    match = re.search(rf"<strong>\s*{label}\s*</strong>\s*([^<]*)", block, flags=re.I)
    return clean_text(match.group(1)) if match else ""


def run_vector_ai20(source: Source, fetcher=fetch_raw_text):
    hits, errors, total, excluded = [], [], 0, 0
    for cohort, year, slug in VECTOR_AI20_EDITIONS:
        url = VECTOR_AI20_POST_API.format(slug=slug)
        raw, error = fetcher(url)
        if error:
            errors.append(f"{url}: {error}")
            continue
        try:
            post = json.loads(raw)[0]
        except (json.JSONDecodeError, IndexError, KeyError) as exc:
            errors.append(f"{url}: unexpected API payload: {exc}")
            continue
        edition_hits, listed, dropped = parse_vector_ai20(
            source, post["content"]["rendered"], post.get("link") or source.url, cohort, year
        )
        hits.extend(edition_hits)
        total += listed
        excluded += dropped
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{len(hits)}/{VECTOR_AI20_EXPECTED_HEALTH} health companies from {total}/{VECTOR_AI20_EXPECTED_TOTAL} AI20 companies; {_counts(len(hits), excluded)}"
    if total != VECTOR_AI20_EXPECTED_TOTAL or len(hits) != VECTOR_AI20_EXPECTED_HEALTH or errors:
        result = f"INCOMPLETE {source.name}: {result}" + (f"; {' | '.join(errors)}" if errors else "")
    return hits, triggers, result


def parse_vector_healthspark(source: Source, raw_html: str) -> list[DiscoveryHit]:
    start = raw_html.find("Current HealthSpark members")
    if start < 0:
        return []
    end = raw_html.find("<h2", start + 1)
    scope = raw_html[start:end] if end > 0 else raw_html[start:]
    names = re.findall(r'class="partners__logo"[^>]*aria-label="([^"]+)"', scope)
    descriptions = [text_from_html(block) for block in blocks_by_class(scope, "div", "modal__description")]
    hits = []
    for index, company in enumerate(names):
        hit = make_accelerator_hit(
            source, clean_text(company), source.url, accelerator_program="Vector Institute HealthSpark",
            cohort_label=VECTOR_HEALTHSPARK_COHORT, cohort_year="2026",
            category_or_track="Health AI (program is health-only)",
            company_description=descriptions[index] if index < len(descriptions) else "",
            geography="Southern Ontario, Canada",
            matched_terms="adapter: vector_healthspark; official current-member list",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits


def run_vector_healthspark(source: Source, fetcher=fetch_raw_text):
    raw_html, error = fetcher(source.url)
    if error:
        return [], [], f"INCOMPLETE {source.name}: page fetch failed: {error}"
    hits, triggers = dedupe_hits_with_triggers(source, parse_vector_healthspark(source, raw_html))
    result = f"{len(hits)}/{VECTOR_HEALTHSPARK_EXPECTED} {VECTOR_HEALTHSPARK_COHORT} members; {len(triggers)} trigger events"
    if len(hits) != VECTOR_HEALTHSPARK_EXPECTED:
        result = f"INCOMPLETE {source.name}: {result}"
    return hits, triggers, result


def parse_amii_level_up_health(source: Source, raw_html: str) -> list[DiscoveryHit]:
    start = raw_html.find("Meet the Cohort")
    if start < 0:
        return []
    end = raw_html.find("</ul>", start)
    scope = raw_html[start:end] if end > 0 else raw_html[start:]
    hits = []
    for item in re.findall(r"<li\b[^>]*>(.*?)</li>", scope, flags=re.S):
        link = re.search(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', item, flags=re.S)
        location = re.search(r"\(([^()]+)\)\s*(?:</p>)?\s*$", item)
        company = text_from_html(link.group(2)) if link else re.sub(r"\(.*", "", text_from_html(item))
        hit = make_accelerator_hit(
            source, company, source.url, accelerator_program="Amii Level Up",
            cohort_label="Amii Level Up health-tech cohort (inaugural)", cohort_year="2025",
            category_or_track="Health tech (program is health-only)",
            website=link.group(1) if link else "",
            geography=institute_geography(location.group(1)) if location else "Canada",
            matched_terms="adapter: amii_level_up_health; official cohort announcement",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits


def run_amii_level_up_health(source: Source, fetcher=fetch_raw_text):
    raw_html, error = fetcher(source.url)
    if error:
        return [], [], f"INCOMPLETE {source.name}: page fetch failed: {error}"
    hits, triggers = dedupe_hits_with_triggers(source, parse_amii_level_up_health(source, raw_html))
    result = f"{len(hits)}/{AMII_LEVEL_UP_HEALTH_EXPECTED} Level Up health-track companies; {len(triggers)} trigger events"
    if len(hits) != AMII_LEVEL_UP_HEALTH_EXPECTED:
        result = f"INCOMPLETE {source.name}: {result}"
    return hits, triggers, result


def _sentence_naming(raw_html: str, company: str) -> str:
    """First article-body sentence that names the company (skips title and navigation)."""
    paragraphs = [text_from_html(p) for p in re.findall(r"<p\b[^>]*>(.*?)</p>", raw_html, flags=re.I | re.S)]
    # Multi-company announcements give each company its own paragraph led by its name.
    paragraphs.sort(key=lambda text: not text.lower().startswith(company.lower()))
    for paragraph in paragraphs:
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            if company.lower() in sentence.lower() and len(sentence) > len(company) + 20:
                return sentence[:400]
    return ""


def _run_mila_curated(source: Source, records, label: str, fetcher) -> tuple[list[DiscoveryHit], list[TriggerEvent], int, list[str]]:
    pages: dict[str, str] = {}
    hits, errors, excluded = [], [], 0
    for company, url, sector, geography in records:
        if not is_health_sector(sector):
            excluded += 1
            continue
        if url not in pages:
            raw_html, error = fetcher(url)
            if error:
                errors.append(f"{url}: {error}")
            pages[url] = "" if error else raw_html
        if not pages[url]:
            continue
        if company.lower() not in text_from_html(pages[url]).lower():
            errors.append(f"{url}: missing {company}")
            continue
        hit = make_accelerator_hit(
            source, company, url, accelerator_program="Mila - Quebec AI Institute",
            cohort_label=label, category_or_track=sector,
            company_description=_sentence_naming(pages[url], company),
            geography=institute_geography(geography) if geography else "",
            matched_terms=f"adapter: {source.adapter}; curated from official Mila announcement, live-verified",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    return hits, triggers, excluded, errors


def run_mila_startups(source: Source, fetcher=fetch_raw_text):
    hits, triggers, excluded, errors = _run_mila_curated(source, MILA_STARTUPS, "Mila Startup", fetcher)
    result = f"{len(hits)}/{MILA_STARTUPS_EXPECTED_HEALTH} named Mila Startups; {_counts(len(hits), excluded)}"
    if len(hits) != MILA_STARTUPS_EXPECTED_HEALTH or errors:
        result = f"INCOMPLETE {source.name}: {result}" + (f"; {' | '.join(errors)}" if errors else "")
    return hits, triggers, result


def run_mila_health_partners(source: Source, fetcher=fetch_raw_text):
    hits, triggers, excluded, errors = _run_mila_curated(
        source, MILA_HEALTH_PARTNERS, "Mila industry partner (health)", fetcher
    )
    result = f"{len(hits)}/{MILA_HEALTH_PARTNERS_EXPECTED} Canadian health-AI Mila partners; {_counts(len(hits), excluded)}"
    if len(hits) != MILA_HEALTH_PARTNERS_EXPECTED or errors:
        result = f"INCOMPLETE {source.name}: {result}" + (f"; {' | '.join(errors)}" if errors else "")
    return hits, triggers, result
