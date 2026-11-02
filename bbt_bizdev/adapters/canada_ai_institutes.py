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
    "dental", "surgical", "patient", "vaccine", "therapy",
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
VECTOR_HEALTHSPARK_PAST_COHORT = "HealthSpark past cohorts"

# FastLane success stories are the only named participants Vector publishes for its
# general startup programs; DaRMoD names none. Sector is read from the story text.
VECTOR_FASTLANE_EXPECTED_TOTAL = 30
VECTOR_FASTLANE_EXPECTED_HEALTH = 8

AMII_LEVEL_UP_HEALTH_EXPECTED = 13
AMII_LEVEL_UP_WRAP_URL = "https://www.amii.ca/updates-insights/Amii-First-Health-Tech-Startup-Cohort-Wraps"
# The wrap-up says 15 startups completed the delivery but names fewer. Tutred is named in
# the text; the others appear only as logos on that page, so they are flagged as such.
AMII_LEVEL_UP_WRAP_COMPANIES = [
    ("Tutred", "named in wrap-up text"),
    ("Zeon AI", "named only by logo on wrap-up page"),
    ("NurseGPT", "named only by logo on wrap-up page"),
    ("Askelle Corporation", "named only by logo on wrap-up page"),
]

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
    ("Ubenwa", "https://mila.quebec/en/news/ubenwa-the-doctor-will-hear-you-now", "Infant health / voice AI", "Canada"),
    ("Dreamfold", "https://mila.quebec/en/news/natures-building-blocks-ai-for-health-and-protein-design", "Protein design / life sciences", "Canada"),
]
MILA_STARTUPS_EXPECTED_HEALTH = 5
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
    ("Toboggan Labs", "https://mila.quebec/en/news/toboggan-labs-joins-milas-industry-partner-network-to-strengthen-healthcare-ai-capabilities", "Healthcare AI consultancy", "Canada"),
    ("AI4Eyes", "https://mila.quebec/en/news/mila-and-ai4eyes-partner-to-advance-ai-innovation-in-ophthalmology", "Ophthalmology medical device software (SaMD)", "Canada"),
    ("SEVO Bioscience", "https://mila.quebec/en/news/ai-meets-synthetic-biology-as-mila-and-sevo-bioscience-forge-strategic-partnership", "Synthetic biology / vaccines", "Montreal, QC"),
    ("Intrepid Labs", "https://mila.quebec/en/news/mila-partners-with-intrepid-labs-to-advance-ai-driven-drug-formulation", "Drug formulation / automation", "Canada"),
    ("Vopemed", "https://mila.quebec/en/news/mila-and-vopemed-announce-partnership-to-advance-ai-driven-surgical-visualization", "Surgical vision medtech", "Montreal, QC"),
    ("DiaGen AI", "https://mila.quebec/en/news/diagen-and-mila-announce-partnership-to-scale-protein-design-in-diagnostics-and-drug-discovery", "Protein design / diagnostics", "Vancouver, BC"),
    ("SonoNurse", "https://mila.quebec/en/news/mila-and-sononurse-partner-to-improve-medical-verification-for-patient-safety", "Medication safety / patient safety", "Montreal, QC"),
    ("Bioeureka", "https://mila.quebec/en/news/bioeureka-and-mila-join-forces-to-accelerate-ai-assisted-pathogen-identification", "Pathogen identification / diagnostics", "Montreal, QC"),
    ("Medeloop", "https://mila.quebec/en/news/medeloop-partners-with-mila-to-leverage-artificial-intelligence-in-health-technology", "Clinical research health technology", "Canada"),
    ("Simmunome", "https://mila.quebec/en/news/simmunome-and-mila-announce-partnership-to-advance-ai-in-drug-development", "Drug development techbio", "Montreal, QC"),
    ("Paraza Pharma", "https://mila.quebec/en/news/paraza-and-mila-announce-partnership-to-advance-ai-in-drug-discovery", "Drug discovery", "Montreal, QC"),
    ("MoCA Cognition", "https://mila.quebec/en/news/mila-and-moca-cognition-partner-up-in-battle-against-alzheimers-and-dementia", "Cognitive impairment diagnostics", "Canada"),
    ("Lixa", "https://mila.quebec/en/news/mila-and-lixa-partner-to-tackle-antimicrobial-resistance", "Biotechnology / antimicrobial resistance", "Canada"),
    ("LUCID", "https://mila.quebec/en/news/lucid-announces-partnership-with-mila-to-advance-machine-learning-in-therapeutic-music", "Digital music therapy", "Toronto, ON"),
]
MILA_HEALTH_PARTNERS_EXPECTED = 23


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
    past_at = scope.find("Past cohorts include")
    if past_at >= 0:
        sections = [(scope[:past_at], VECTOR_HEALTHSPARK_COHORT, "2026"), (scope[past_at:], VECTOR_HEALTHSPARK_PAST_COHORT, "")]
    else:
        sections = [(scope, VECTOR_HEALTHSPARK_COHORT, "2026")]
    hits = []
    for section, cohort, year in sections:
        names = re.findall(r'class="partners__logo"[^>]*aria-label="([^"]+)"', section)
        modals = blocks_by_class(section, "div", "modal__description")
        for index, company in enumerate(names):
            modal = modals[index] if index < len(modals) else ""
            link = re.search(r'href="(https?://(?!(?:www\.)?vectorinstitute\.ai)[^"]+)"', modal)
            hit = make_accelerator_hit(
                source, clean_text(company), source.url, accelerator_program="Vector Institute HealthSpark",
                cohort_label=cohort, cohort_year=year,
                category_or_track="Health AI (program is health-only)",
                company_description=text_from_html(modal), website=link.group(1) if link else "",
                geography="Southern Ontario, Canada",
                matched_terms="adapter: vector_healthspark; official member list",
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
    result = f"{len(hits)}/{VECTOR_HEALTHSPARK_EXPECTED} HealthSpark members (current and past cohorts); {len(triggers)} trigger events"
    if len(hits) != VECTOR_HEALTHSPARK_EXPECTED:
        result = f"INCOMPLETE {source.name}: {result}"
    return hits, triggers, result


def parse_vector_fastlane(source: Source, raw_html: str) -> tuple[list[DiscoveryHit], int, int]:
    """Return (health hits, listed companies, non-health excluded) from FastLane success stories."""
    names = [_tag_text(block, "p") for block in blocks_by_class(raw_html, "article", "institutions__institution")]
    slides = blocks_by_class(raw_html, "div", "modal__slide")
    hits, excluded = [], 0
    for index, company in enumerate(names):
        story = text_from_html(slides[index]) if index < len(slides) else ""
        if not is_health_sector(story):
            excluded += 1
            continue
        link = re.search(r'href="(https?://[^"]+)"', slides[index])
        hit = make_accelerator_hit(
            source, company, source.url, accelerator_program="Vector Institute FastLane",
            cohort_label="FastLane success stories", category_or_track="Health AI (FastLane success story)",
            company_description=story[len(company):].strip()[:400], website=link.group(1) if link else "",
            geography="Canada", matched_terms="adapter: vector_fastlane; health terms in official success story",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits, len(names), excluded


def run_vector_fastlane(source: Source, fetcher=fetch_raw_text):
    raw_html, error = fetcher(source.url)
    if error:
        return [], [], f"INCOMPLETE {source.name}: page fetch failed: {error}"
    hits, listed, excluded = parse_vector_fastlane(source, raw_html)
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{len(hits)}/{VECTOR_FASTLANE_EXPECTED_HEALTH} health companies from {listed}/{VECTOR_FASTLANE_EXPECTED_TOTAL} FastLane success stories; {_counts(len(hits), excluded)}"
    if listed != VECTOR_FASTLANE_EXPECTED_TOTAL or len(hits) != VECTOR_FASTLANE_EXPECTED_HEALTH:
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


def _amii_wrap_hits(source: Source, wrap_html: str) -> list[DiscoveryHit]:
    squashed = re.sub(r"[^a-z0-9]", "", wrap_html.lower())
    hits = []
    for company, evidence in AMII_LEVEL_UP_WRAP_COMPANIES:
        if re.sub(r"[^a-z0-9]", "", company.lower()) not in squashed:
            continue
        hit = make_accelerator_hit(
            source, company, AMII_LEVEL_UP_WRAP_URL, accelerator_program="Amii Level Up",
            cohort_label="Amii Level Up health-tech cohort (inaugural)", cohort_year="2025",
            category_or_track="Health tech (program is health-only)", geography="Canada",
            matched_terms=f"adapter: amii_level_up_health; {evidence}",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits


def run_amii_level_up_health(source: Source, fetcher=fetch_raw_text):
    raw_html, error = fetcher(source.url)
    if error:
        return [], [], f"INCOMPLETE {source.name}: page fetch failed: {error}"
    hits = parse_amii_level_up_health(source, raw_html)
    wrap_html, wrap_error = fetcher(AMII_LEVEL_UP_WRAP_URL)
    if not wrap_error:
        hits += _amii_wrap_hits(source, wrap_html)
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{len(hits)}/{AMII_LEVEL_UP_HEALTH_EXPECTED} Level Up health-track companies (cohort of 15 per Amii; 13 named online); {len(triggers)} trigger events"
    if len(hits) != AMII_LEVEL_UP_HEALTH_EXPECTED or wrap_error:
        result = f"INCOMPLETE {source.name}: {result}" + (f"; wrap-up page fetch failed: {wrap_error}" if wrap_error else "")
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


# Companies named by an institute's own page, report or social post but outside a list the
# other runners can parse. check "live" re-fetches the URL and requires the name on the page;
# "manual" entries come from a LinkedIn post or PDF the runner cannot read and are flagged.
INSTITUTE_MENTIONS = [
    # company, institute, program, evidence URL, check, sector, geography
    ("Spheroid AI", "Mila", "Entrepreneurship Lab Demo Day 2023", "https://mila.quebec/en/news/demo-day-2023", "live", "Ovarian cancer detection", "Canada"),
    ("LightX Innovations", "Mila", "Mila research collaboration (2024-25 impact report)", "https://mila.quebec/en/about/impact-reports/impact-report-2024-2025", "live", "Eye care / diabetic retinopathy", "Canada"),
    ("H2OM Technologies", "Mila", "Mila Ventures Launchpad", "LinkedIn: Mila Ventures Launchpad cohort post", "manual", "Molecular health monitoring", "Saint-Bruno-de-Montarville, QC"),
    ("Medtech Insurance", "Mila", "Mila Ventures Founder in Residence", "LinkedIn: Mila Ventures Founder in Residence cohort post", "manual", "Insurance for medical technology firms (health-adjacent)", "Montreal, QC"),
    ("Fawkes Biodata", "Vector", "FastLane Demo Day 2026", "https://vectorinstitute.ai/demo-day-how-the-vector-institute-helps-canadian-startups-turn-innovative-ideas-into-commercial-reality/", "live", "Medical records / clinical-trial matching", "Canada"),
    ("JVPLabs", "Vector", "FastLane Demo Day 2026", "https://vectorinstitute.ai/demo-day-how-the-vector-institute-helps-canadian-startups-turn-innovative-ideas-into-commercial-reality/", "live", "Heart-failure monitoring device", "Canada"),
    ("A.I. Vali", "Vector", "FastLane 2022-23", "https://vectorinstitute.ai/case-studies/how-ai-vali-helps-clinicians-improve-patient-care-through-vectors-fastlane-program/", "live", "Cancer detection / clinician decision support", "Canada"),
    ("16 Bit", "Vector", "FastLane 2021-22", "Vector Institute 2021-22 annual report (PDF)", "manual", "Health diagnostics machine learning", "Canada"),
    ("HelpWear", "Amii", "Level Up Cohort 4 (2024)", "https://www.amii.ca/updates-insights/startups-level-up-cohort-4", "live", "Wearable ECG medical device", "Toronto, ON"),
    ("Deep Breathe", "Amii", "Level Up Cohort 4 (2024)", "https://www.amii.ca/updates-insights/startups-level-up-cohort-4", "live", "Portable AI lung imaging", "London, ON"),
    ("Wound³", "Amii", "Level Up Cohort 4 (2024)", "https://www.amii.ca/updates-insights/startups-level-up-cohort-4", "live", "Chronic wound scanning (health inferred from Alberta Innovates funding record)", "Edmonton, AB"),
    ("Ora-Q", "Amii", "Level Up (past participant)", "https://www.amii.ca/updates-insights/amii-teams-up-with-can-health-network-and-boxone-ventures-to-support-canadian-health-tech-innovation", "live", "Dental care AI", "Calgary, AB"),
    ("Drugbank", "Amii", "Amii Innovates Innovation Affiliates (2019)", "https://betakit.com/amii-innovates-announces-first-cohort-looks-to-accelerate-ai-adoption/", "live", "Drug database / NLP", "Edmonton, AB"),
    ("Mikata Health", "Amii", "Amii Innovates Innovation Affiliates (2019)", "https://betakit.com/amii-innovates-announces-first-cohort-looks-to-accelerate-ai-adoption/", "live", "Digital health", "Calgary, AB"),
    ("Medo.AI", "Amii", "Amii Innovates Innovation Affiliates (2019)", "https://betakit.com/amii-innovates-announces-first-cohort-looks-to-accelerate-ai-adoption/", "live", "Ultrasound AI for infant hip diagnosis (acquired by Exo in 2022)", "Alberta"),
]
INSTITUTE_MENTIONS_EXPECTED = 15
# Health companies reported near an institute but without a confirmed institute link; kept out of
# the snapshots and listed only in the review workbook.
INSTITUTE_UNCONFIRMED_LEADS = [
    ("NeuralDrive", "Mila", "Search snippet quotes a Mila 'Mila Startup' page that could not be opened"),
    ("AwakeAI", "Mila", "Search snippet only; Montreal senior-care monitoring"),
    ("Mohana", "Mila", "Search snippet only; chronic-condition wellbeing"),
    ("Avitia", "Mila", "Looks like a Mila partner, not a startup Mila supports"),
    ("Leynek Medical", "Vector", "Company says it joined FastLane in Aug 2023; not on any Vector page"),
    ("Sifio Health", "Vector", "Listed as a FastLane investment on PitchBook only"),
    ("Cynthetix.ai", "Amii", "Level Up Cohort 4 member; health focus could not be confirmed"),
    ("Cognitive Diagnosis", "Amii", "Amii Innovates 2019 member; health relevance inferred from the name"),
]


def run_institute_mentions(source: Source, fetcher=fetch_raw_text):
    pages: dict[str, str] = {}
    hits, errors = [], []
    for company, institute, program, evidence, check, sector, geography in INSTITUTE_MENTIONS:
        note = "manually sourced, not live-verified"
        if check == "live":
            if evidence not in pages:
                raw_html, error = fetcher(evidence)
                if error:
                    errors.append(f"{evidence}: {error}")
                pages[evidence] = "" if error else text_from_html(raw_html)
            if not pages[evidence]:
                continue
            squashed = re.sub(r"[^a-z0-9]", "", pages[evidence].lower())
            if re.sub(r"[^a-z0-9]", "", company.lower()) not in squashed:
                errors.append(f"{evidence}: missing {company}")
                continue
            note = "live-verified"
        hit = make_accelerator_hit(
            source, company, evidence if check == "live" else source.url,
            accelerator_program=f"{institute}: {program}", cohort_label=program, category_or_track=sector,
            geography=institute_geography(geography),
            matched_terms=f"adapter: institute_mentions; {institute}; {note}" + ("" if check == "live" else f"; evidence: {evidence}"),
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{len(hits)}/{INSTITUTE_MENTIONS_EXPECTED} curated institute-linked health companies"
    if len(hits) != INSTITUTE_MENTIONS_EXPECTED or errors:
        result = f"INCOMPLETE {source.name}: {result}" + (f"; {' | '.join(errors)}" if errors else "")
    return hits, triggers, result
