from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .adapters.accelerators import (
    run_arc_hub_healthtech,
    run_bioinnovate_ireland,
    run_digitalhealth_london,
    run_dogpatch_ndrc,
    run_eit_health_catapult,
    run_health_innovation_hub_ireland,
    run_mayo_accelerate,
    run_medtech_innovator,
    run_yc_healthcare,
)
from .adapters.generic import build_source_page_evidence, find_companies_on_source
from .adapters.jobs import run_biospace_jobs, run_builtin_jobs, run_greenhouse_discovery, run_job_board_adapter, run_nhs_jobs
from .adapters.linkedin import enrich_companies_linkedin
from .adapters.search import run_google_news_search
from .adapters.university import run_university_spinout_pages
from .adapters.vc import run_atlantic_bridge, run_fountain_healthcare, run_seroba_life_sciences
from .config import (
    ADAPTER_STATUS_NAMES,
    BBT_QUADRANTS,
    COMPANY_REGISTRY,
    JOB_BOARD_ADAPTERS,
    LEAD_ENRICHMENT_API_KEY_ENV,
    LEAD_ENRICHMENT_CACHE_DIR,
    LEAD_ENRICHMENT_DEFAULT_MODEL,
    LEAD_ENRICHMENT_DISABLED_ENV,
    LEAD_ENRICHMENT_FETCH_EVIDENCE_ENV,
    LEAD_ENRICHMENT_MODEL_ENV,
    LEAD_ENRICHMENT_PROMPT_VERSION,
    LEAD_PERSONAS,
    LEAD_SECONDARY_TAGS,
    LINKEDIN_CONTACT_TARGET_YEAR,
    SOURCES,
    TRIGGER_SOURCES,
)
from .http import fetch_text, fetch_raw_text
from .models import CompanyRecord, DiscoveryHit, LeadEnrichment, Source, TriggerEvent
from .text import text_from_html


def run_discovery(sources: list[Source]) -> tuple[list[DiscoveryHit], list[TriggerEvent], list[list[str]]]:
    discovery_hits: list[DiscoveryHit] = []
    trigger_events: list[TriggerEvent] = []
    run_log: list[list[str]] = []
    for source in sources:
        if source.source_type == "University/spinout":
            hits, triggers, result = run_university_spinout_pages(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            status = ADAPTER_STATUS_NAMES.get(source.adapter or "university_spinout_directory", "University spinout directory adapter")
            run_log.append([source.name, source.source_type, source.url, status, result])
            continue
        if not source.adapter:
            run_log.append([source.name, source.source_type, source.url, "Skipped", "No automated adapter yet"])
            continue
        if source.source_type == "Accelerator" and source.adapter == "accelerator_page":
            run_log.append([source.name, source.source_type, source.url, "Skipped", "No source-specific accelerator adapter yet"])
            continue
        if source.adapter == "google_news_search":
            hits, triggers, result = run_google_news_search(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, "Fetched", result])
            continue
        if source.adapter == "yc_healthcare":
            hits, triggers, result = run_yc_healthcare(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, "YC Healthcare directory adapter", result])
            continue
        if source.adapter == "medtech_innovator":
            hits, triggers, result = run_medtech_innovator(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        if source.adapter == "digitalhealth_london":
            hits, triggers, result = run_digitalhealth_london(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        if source.adapter == "mayo_accelerate":
            hits, triggers, result = run_mayo_accelerate(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        if source.adapter == "eit_health_catapult":
            hits, triggers, result = run_eit_health_catapult(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        if source.adapter == "bioinnovate_ireland":
            hits, triggers, result = run_bioinnovate_ireland(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        if source.adapter == "arc_hub_healthtech":
            hits, triggers, result = run_arc_hub_healthtech(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        if source.adapter == "health_innovation_hub_ireland":
            hits, triggers, result = run_health_innovation_hub_ireland(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        if source.adapter == "dogpatch_ndrc":
            hits, triggers, result = run_dogpatch_ndrc(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        if source.adapter == "fountain_healthcare":
            hits, triggers, result = run_fountain_healthcare(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        if source.adapter == "seroba_life_sciences":
            hits, triggers, result = run_seroba_life_sciences(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        if source.adapter == "atlantic_bridge":
            hits, triggers, result = run_atlantic_bridge(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        if source.adapter == "greenhouse_jobs":
            hits, triggers, result = run_greenhouse_discovery(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        if source.adapter == "biospace_jobs":
            hits, triggers, result = run_biospace_jobs(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        if source.adapter == "builtin_jobs":
            hits, triggers, result = run_builtin_jobs(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        if source.adapter == "nhs_jobs":
            hits, triggers, result = run_nhs_jobs(source)
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        if source.adapter in JOB_BOARD_ADAPTERS:
            hits, triggers, result = run_job_board_adapter(source, JOB_BOARD_ADAPTERS[source.adapter])
            discovery_hits.extend(hits)
            trigger_events.extend(triggers)
            run_log.append([source.name, source.source_type, source.url, ADAPTER_STATUS_NAMES[source.adapter], result])
            continue
        raw_html, error = fetch_raw_text(source.url)
        if error:
            run_log.append([source.name, source.source_type, source.url, "Fetch failed", error])
            continue
        source_triggers: list[TriggerEvent] = []
        if source.adapter in ADAPTER_STATUS_NAMES:
            hits, source_triggers = build_source_page_evidence(source, raw_html)
            trigger_events.extend(source_triggers)
        else:
            hits = find_companies_on_source(source, text_from_html(raw_html))
        discovery_hits.extend(hits)
        status = ADAPTER_STATUS_NAMES.get(source.adapter or "", "Fetched")
        run_log.append([source.name, source.source_type, source.url, status, f"{len(hits)} discovery hits; {len(source_triggers)} trigger events"])
    return discovery_hits, trigger_events, run_log

def adapter_inventory_label(source: Source) -> str:
    if source.source_type == "Accelerator" and source.adapter == "accelerator_page":
        return "Manual/not implemented"
    if source.source_type == "University/spinout":
        return ADAPTER_STATUS_NAMES.get(source.adapter or "university_spinout_directory", "University spinout directory adapter")
    if source.adapter:
        return ADAPTER_STATUS_NAMES.get(source.adapter, source.adapter)
    return "Manual/not implemented"

def normalize_companies(discovery_hits: list[DiscoveryHit]) -> dict[str, CompanyRecord]:
    companies: dict[str, CompanyRecord] = {}
    for hit in discovery_hits:
        record = companies.setdefault(hit.company, CompanyRecord(company=hit.company))
        record.discovery_hits.append(hit)
        record.website = record.website or hit.website
        record.geography = record.geography or hit.geography
        record.product_type = record.product_type or hit.product_type
    return companies

def attach_trigger_events(companies: dict[str, CompanyRecord], trigger_events: list[TriggerEvent]) -> list[TriggerEvent]:
    attached: list[TriggerEvent] = []
    seen: set[tuple[str, str, str]] = set()
    for event in trigger_events:
        record = companies.get(event.company)
        if not record:
            continue
        key = (event.company.lower(), event.trigger_type, event.evidence_url)
        if key in seen:
            continue
        seen.add(key)
        record.triggers.append(event)
        attached.append(event)
    return attached

def mark_primary_triggers(companies: dict[str, CompanyRecord]) -> None:
    for record in companies.values():
        for idx, trigger in enumerate(record.triggers):
            trigger.trigger_role = "Primary" if idx == 0 else "Secondary"

def run_trigger_research(companies: dict[str, CompanyRecord]) -> list[TriggerEvent]:
    trigger_events: list[TriggerEvent] = []
    discovered = set(companies)
    for source in TRIGGER_SOURCES:
        text, error = fetch_text(source["url"])
        if error:
            continue
        lower_text = text.lower()
        for company in source["companies"]:
            if company not in discovered:
                continue
            aliases = COMPANY_REGISTRY[company]["aliases"]
            if any(alias.lower() in lower_text for alias in aliases):
                event = TriggerEvent(
                    company=company,
                    trigger_type=source["trigger_type"],
                    trigger_event=source["trigger_event"],
                    trigger_source=source["name"],
                    evidence_url=source["url"],
                )
                trigger_events.append(event)
    return attach_trigger_events(companies, trigger_events)

def lead_text(record: CompanyRecord) -> str:
    return " ".join(
        [record.product_type, record.company, record.website, record.geography]
        + [h.source_type for h in record.discovery_hits]
        + [h.discovery_rationale for h in record.discovery_hits]
        + [h.company_description for h in record.discovery_hits]
        + [h.category_or_track for h in record.discovery_hits]
        + [h.accelerator_program for h in record.discovery_hits]
        + [h.cohort_label for h in record.discovery_hits]
        + [t.trigger_type for t in record.triggers]
        + [t.trigger_event for t in record.triggers]
    ).lower()


def score_company_metrics(record: CompanyRecord) -> tuple[dict[str, int], int, str]:
    text = " ".join(
        [record.product_type, record.company]
        + [h.discovery_rationale for h in record.discovery_hits]
        + [h.company_description for h in record.discovery_hits]
        + [h.category_or_track for h in record.discovery_hits]
        + [t.trigger_event for t in record.triggers]
    ).lower()
    flags = {
        "Recently funded +3": int(any(t.trigger_type == "Funding" for t in record.triggers)),
        "AI/SaMD/device +3": int(any(term in text for term in ["ai", "samd", "medical device", "diagnostic", "imaging", "wearable", "stethoscope"])),
        "Hiring QA/reg/V&V +3": int(any(term in text for term in ["regulatory affairs", "quality engineer", "design assurance", "v&v"])),
        "Clinical validation +2": int(any(term in text for term in ["clinical", "diagnostic", "screening", "validation"])),
        "FDA/CE/reg language +2": int(any(term in text for term in ["fda", "ce ", "samd", "regulated"])),
        "Grant/public funding +2": int(any(h.source_type == "Grant/funding" for h in record.discovery_hits)),
        "University/grant origin +2": int(any(h.source_type in ["University/spinout", "Grant/funding"] for h in record.discovery_hits)),
        "No obvious reg team +2": 0,
        "Pre-commercial +1": int(any(h.source_type == "Accelerator" for h in record.discovery_hits)),
        "Large company -1": 0,
        "Wellness/non-medical -2": -1 if "wellness" in text else 0,
        "Pharma-only -2": -1 if "pharma-only" in text else 0,
    }
    score = (
        flags["Recently funded +3"] * 3
        + flags["AI/SaMD/device +3"] * 3
        + flags["Hiring QA/reg/V&V +3"] * 3
        + flags["Clinical validation +2"] * 2
        + flags["FDA/CE/reg language +2"] * 2
        + flags["Grant/public funding +2"] * 2
        + flags["University/grant origin +2"] * 2
        + flags["No obvious reg team +2"] * 2
        + flags["Pre-commercial +1"]
        + flags["Large company -1"] * -1
        + flags["Wellness/non-medical -2"] * 2
        + flags["Pharma-only -2"] * 2
    )
    band = "Strong" if score >= 10 else "Good" if score >= 7 else "Maybe" if score >= 4 else "Low"
    return flags, score, band


def normalize_geography_region(raw_geography: str) -> str:
    """Collapse city/country strings into stable commercial regions."""
    text = (raw_geography or "").strip().lower()
    if not text or text in {"unknown", "remote"}:
        return "Unknown"
    exact_regions = {"uk": "UK", "us": "US", "eu": "Europe", "global": "Global"}
    if text in exact_regions:
        return exact_regions[text]

    region_terms = [
        ("Ireland", ["ireland", "dublin", "galway", "cork", "limerick"]),
        ("UK", ["united kingdom", "england", "scotland", "wales", "northern ireland", " uk", "uk/", "london", "oxford", "cambridge, england"]),
        ("US", ["united states", " usa", "usa", "us/", "/us", "puerto rico"]),
        ("Canada", ["canada"]),
        ("Australia/New Zealand", ["australia", "new zealand"]),
        ("Europe", [
            "eu/", " eu", "europe", "france", "germany", "switzerland", "netherlands", "spain",
            "belgium", "denmark", "italy", "sweden", "finland", "austria", "bulgaria", "greece",
            "iceland", "latvia", "lithuania", "luxembourg", "poland", "portugal", "norway",
        ]),
        ("Asia-Pacific", [
            "singapore", "india", "japan", "south korea", "korea, s", "china", "hong kong", "taiwan",
            "pakistan", "malaysia", "philippines", "indonesia", "nepal", "thailand", "vietnam",
        ]),
        ("Middle East", ["israel", "united arab emirates", "dubai", "saudi arabia", "qatar"]),
        ("Africa", ["nigeria", "ghana", "kenya", "south africa", "egypt"]),
        ("Latin America", ["mexico", "colombia", "ecuador", "chile", "brazil", "argentina"]),
        ("Global", ["global"]),
    ]

    matches: list[tuple[int, int, str]] = []
    for priority, (region, terms) in enumerate(region_terms):
        positions = [text.find(term) for term in terms if text.find(term) >= 0]
        if positions:
            matches.append((min(positions), priority, region))
    return min(matches)[2] if matches else "Unknown"


def lead_filter_fields(record: CompanyRecord, enrichment: LeadEnrichment) -> dict[str, str]:
    """Derive conservative, filterable lead attributes from collected evidence."""
    evidence_year, evidence_basis, evidence_hit = latest_evidence_context(record)
    if evidence_year:
        age = date.today().year - int(evidence_year)
        evidence_recency = "This year" if age <= 0 else "1 year ago" if age == 1 else "2 years ago" if age == 2 else "3+ years ago"
    else:
        evidence_recency = "Unknown"

    matching_triggers = [trigger for trigger in record.triggers if trigger.evidence_url == evidence_hit.discovery_url]
    trigger = matching_triggers[0] if matching_triggers else primary_trigger(record)
    trigger_type = trigger.trigger_type if trigger else "No verified trigger"

    text = lead_text(record)
    source_types = {hit.source_type for hit in record.discovery_hits}
    trigger_types = {item.trigger_type for item in record.triggers}

    if re.search(r"\b(ai|artificial intelligence|machine learning|samd|software as a medical device)\b", text):
        product_area = "AI / SaMD"
    elif re.search(r"\b(diagnostic|diagnostics|screening|imaging)\b", text):
        product_area = "Diagnostics / imaging"
    elif re.search(r"\b(medical device|device|wearable|implant|sensor)\b", text):
        product_area = "Medical device"
    elif re.search(r"\b(biotech|pharma|therapeutic|drug discovery)\b", text):
        product_area = "Biotech / pharma"
    elif re.search(r"\b(digital health|health software|platform|telehealth|remote monitoring)\b", text):
        product_area = "Digital health"
    else:
        product_area = "Other / unclear"

    funding_stage = "Unknown"
    funding_patterns = [
        (r"\bseries\s+([a-f])\b", lambda match: f"Series {match.group(1).upper()}"),
        (r"\bpre[- ]seed\b", lambda _: "Pre-seed"),
        (r"\bseed(?: round| funding)?\b", lambda _: "Seed"),
        (r"\b(grant|award|sbir|sttr)\b", lambda _: "Grant / public funding"),
    ]
    for pattern, label in funding_patterns:
        match = re.search(pattern, text)
        if match:
            funding_stage = label(match)
            break
    if funding_stage == "Unknown" and ("Funding" in trigger_types or "Grant/funding" in source_types):
        funding_stage = "Funding reported - stage unknown"

    hiring_signal = "Yes" if "Hiring signal" in trigger_types or "Jobs" in source_types else "No"

    if enrichment.persona == "University/spinout" or "University/spinout" in source_types:
        company_type = "University spinout"
    elif enrichment.persona in {"Early startup", "Funded startup"} or "Accelerator" in source_types:
        company_type = "Startup"
    elif enrichment.persona in {"Scaleup", "Jobs-led capability gap"}:
        company_type = "Scaleup / growing company"
    elif enrichment.persona == "Established medtech":
        company_type = "Established company"
    else:
        company_type = "Unknown"

    if trigger_types.intersection({"Regulatory clearance", "Approval", "Launch"}):
        company_stage = "Regulatory / commercial"
    elif hiring_signal == "Yes" or enrichment.persona == "Scaleup":
        company_stage = "Scaling"
    elif enrichment.persona in {"Early startup", "Funded startup", "University/spinout"}:
        company_stage = "Early-stage / validation"
    else:
        company_stage = "Unknown"

    return {
        "Evidence year": str(evidence_year),
        "Evidence basis": evidence_basis,
        "Evidence recency": evidence_recency,
        "Trigger type": trigger_type,
        "Geography": normalize_geography_region(record.geography or evidence_hit.geography),
        "Company type": company_type,
        "Company stage": company_stage,
        "Product area": product_area,
        "Hiring signal": hiring_signal,
        "Funding stage": funding_stage,
    }


def latest_evidence_context(record: CompanyRecord) -> tuple[str, str, DiscoveryHit]:
    dated_hits: list[tuple[int, str, DiscoveryHit]] = []
    for hit in record.discovery_hits:
        for basis, raw_year in (("Article year", hit.article_year), ("Cohort year", hit.cohort_year)):
            if str(raw_year).isdigit() and 1900 <= int(raw_year) <= date.today().year + 1:
                dated_hits.append((int(raw_year), basis, hit))

    if dated_hits:
        evidence_year, evidence_basis, evidence_hit = max(dated_hits, key=lambda item: item[0])
        return str(evidence_year), evidence_basis, evidence_hit
    else:
        return "", "Unknown", primary_discovery(record)


def is_linkedin_contact_target(record: CompanyRecord) -> bool:
    evidence_year, _, _ = latest_evidence_context(record)
    return evidence_year == LINKEDIN_CONTACT_TARGET_YEAR


def classify_company_rules(record: CompanyRecord, fallback_reason: str = "") -> LeadEnrichment:
    text = lead_text(record)
    source_types = {hit.source_type for hit in record.discovery_hits}
    trigger_types = {trigger.trigger_type for trigger in record.triggers}

    has_jobs = "Jobs" in source_types or "Hiring signal" in trigger_types
    has_regulatory = "Regulatory database" in source_types or any("regulatory" in t.lower() or "clearance" in t.lower() for t in trigger_types)
    has_funding = any(t in trigger_types for t in ["Funding", "Grant/public funding"]) or "Grant/funding" in source_types
    has_university = "University/spinout" in source_types
    has_accelerator = "Accelerator" in source_types or "Accelerator/cohort" in trigger_types
    has_market_presence = bool(source_types.intersection({"Conference", "VC portfolio", "Public ranking"}))

    if has_jobs:
        persona = "Jobs-led capability gap"
        quadrant = "Embedded support"
        secondary = "Hiring gap"
        pain = "Likely has an active regulatory, quality, validation, or clinical workload that the team is trying to staff."
        value_prop = "Provide experienced embedded support to reduce hiring pressure and keep regulated delivery moving."
        outreach = "Reference the open role or hiring signal and offer targeted regulatory, QA, V&V, or clinical delivery support."
        rationale = "Hiring signal takes priority because it indicates an active capability gap."
        confidence = 0.86
    elif has_regulatory:
        persona = "Regulatory-led opportunity"
        quadrant = "Regulatory/validation"
        secondary = "Regulatory pathway"
        pain = "Likely needs help turning regulatory movement into a defensible validation, claims, or post-market plan."
        value_prop = "Help translate regulatory status into practical evidence, documentation, and next-market readiness."
        outreach = "Lead with a focused regulatory or validation review tied to the clearance, listing, or regulatory evidence."
        rationale = "Regulatory source or clearance trigger indicates pathway and evidence needs."
        confidence = 0.84
    elif has_funding:
        persona = "Funded startup"
        quadrant = "Advisory"
        secondary = "Funding trigger"
        pain = "Likely has fresh budget and pressure to convert a funded plan into validated regulated product work."
        value_prop = "Help sequence regulatory, validation, product, and quality work before hiring or scaling too far."
        outreach = "Congratulate them on the funding and offer a short planning review for the next regulated-product milestones."
        rationale = "Funding or grant evidence suggests budget and a time-bound planning window."
        confidence = 0.82
    elif has_university:
        persona = "University/spinout"
        quadrant = "Advisory"
        secondary = "Clinical validation" if "clinical" in text else "Medical device"
        pain = "Likely needs to turn academic or translational evidence into a product, regulatory, and validation story."
        value_prop = "Help shape the first credible pathway from research output to regulated product development."
        outreach = "Offer early advisory support around product definition, validation evidence, and regulatory pathfinding."
        rationale = "University or spinout source indicates an early translational company."
        confidence = 0.76
    elif has_accelerator:
        persona = "Early startup"
        quadrant = "Design/dev" if any(term in text for term in ["prototype", "device", "diagnostic", "imaging"]) else "Advisory"
        secondary = "Accelerator/cohort"
        pain = "Likely needs to sharpen product, evidence, and regulatory assumptions while still early enough to influence direction."
        value_prop = "Provide lightweight advisory or design-development input before costly product and evidence choices harden."
        outreach = "Reference the current cohort and offer a compact product, validation, or regulatory readiness conversation."
        rationale = "Accelerator/cohort evidence points to an early-stage but reachable lead."
        confidence = 0.74
    elif has_market_presence:
        persona = "Scaleup"
        quadrant = "Commercial readiness"
        secondary = "SaMD/AI" if any(term in text for term in ["ai", "samd", "software"]) else "Medical device"
        pain = "Likely needs to align product, evidence, and claims as it expands commercially or enters new channels."
        value_prop = "Help strengthen regulated-product readiness for commercial expansion and customer scrutiny."
        outreach = "Reference the market signal and offer a readiness review around claims, evidence, and delivery risk."
        rationale = "Conference, ranking, or investor presence suggests market-facing activity."
        confidence = 0.68
    else:
        persona = "Established medtech"
        quadrant = "Advisory"
        secondary = "SaMD/AI" if any(term in text for term in ["ai", "samd", "software"]) else "Medical device"
        pain = "Likely needs a defensible regulatory, validation, claims, or productisation story before broader commercial expansion."
        value_prop = "Help clarify the regulated-product path and reduce avoidable evidence or delivery risk."
        outreach = "Open with the strongest public evidence and offer a short fit conversation around regulatory and validation needs."
        rationale = "No stronger trigger found, so classification uses broad company and source relevance."
        confidence = 0.55

    if secondary not in LEAD_SECONDARY_TAGS:
        secondary = "Medical device"
    if quadrant not in BBT_QUADRANTS:
        quadrant = "Advisory"
    if persona not in LEAD_PERSONAS:
        persona = "Established medtech"

    return LeadEnrichment(
        persona=persona,
        primary_quadrant=quadrant,
        secondary_tag=secondary,
        pain_hypothesis=pain,
        value_prop=value_prop,
        outreach_angle=outreach,
        confidence=confidence,
        rationale=rationale,
        method="rules",
        llm_used=False,
        fallback_reason=fallback_reason,
    )


def lead_enrichment_llm_config() -> tuple[str | None, str | None]:
    disabled = os.environ.get(LEAD_ENRICHMENT_DISABLED_ENV, "").strip().lower()
    if disabled in {"1", "true", "yes", "on"}:
        return None, None
    api_key = os.environ.get(LEAD_ENRICHMENT_API_KEY_ENV, "").strip()
    if not api_key:
        return None, None
    model = os.environ.get(LEAD_ENRICHMENT_MODEL_ENV, LEAD_ENRICHMENT_DEFAULT_MODEL).strip()
    return api_key, model or LEAD_ENRICHMENT_DEFAULT_MODEL


def lead_enrichment_cache_key(record: CompanyRecord) -> str:
    trigger = primary_trigger(record)
    hit = primary_discovery(record)
    evidence_url = trigger.evidence_url if trigger else hit.discovery_url
    raw = json.dumps(
        {
            "company": record.company,
            "evidence_url": evidence_url,
            "prompt_version": LEAD_ENRICHMENT_PROMPT_VERSION,
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_cached_llm_enrichment(record: CompanyRecord) -> dict | None:
    path = Path(LEAD_ENRICHMENT_CACHE_DIR) / f"{lead_enrichment_cache_key(record)}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_cached_llm_enrichment(record: CompanyRecord, payload: dict) -> None:
    path = Path(LEAD_ENRICHMENT_CACHE_DIR) / f"{lead_enrichment_cache_key(record)}.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        return


def build_lead_enrichment_prompt(record: CompanyRecord, evidence_text: str = "") -> str:
    hit = primary_discovery(record)
    trigger = primary_trigger(record)
    context = {
        "company": record.company,
        "website": record.website,
        "geography": record.geography,
        "product_type": record.product_type,
        "discovery_source_type": hit.source_type,
        "discovery_rationale": hit.discovery_rationale,
        "company_description": hit.company_description,
        "category_or_track": hit.category_or_track,
        "trigger_type": trigger.trigger_type if trigger else "",
        "trigger_event": trigger.trigger_event if trigger else "",
        "evidence_text": evidence_text[:4000],
    }
    return (
        "Classify this BlueBridge Technologies business-development lead. "
        "Return strict JSON only with keys: persona, primary_quadrant, secondary_tag, "
        "pain_hypothesis, value_prop, outreach_angle, confidence, rationale. "
        f"Choose persona from {LEAD_PERSONAS}. "
        f"Choose primary_quadrant from {BBT_QUADRANTS}. "
        f"Choose secondary_tag from {LEAD_SECONDARY_TAGS}. "
        "Do not invent evidence. Use low confidence when the public evidence is thin. "
        "Keep pain_hypothesis, value_prop, and outreach_angle to one concise sentence each.\n\n"
        f"Lead context JSON:\n{json.dumps(context, indent=2, sort_keys=True)}"
    )


def _call_lead_enrichment_llm(prompt: str, api_key: str, model: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model, safe='')}:generateContent?key={quote(api_key, safe='')}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
    }
    req = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        raw = urlopen(req, timeout=45).read()
    except (OSError, URLError) as exc:
        raise RuntimeError(f"llm_error: {exc}") from exc
    try:
        response = json.loads(raw.decode("utf-8", "ignore"))
        text = response["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_json") from exc


def lead_enrichment_from_payload(payload: dict, method: str) -> LeadEnrichment:
    required = [
        "persona",
        "primary_quadrant",
        "secondary_tag",
        "pain_hypothesis",
        "value_prop",
        "outreach_angle",
        "confidence",
        "rationale",
    ]
    if not isinstance(payload, dict) or any(not payload.get(key) for key in required):
        raise ValueError("invalid_json")
    if payload["persona"] not in LEAD_PERSONAS or payload["primary_quadrant"] not in BBT_QUADRANTS or payload["secondary_tag"] not in LEAD_SECONDARY_TAGS:
        raise ValueError("invalid_taxonomy")
    try:
        confidence = float(payload["confidence"])
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_json") from exc
    confidence = max(0.0, min(confidence, 1.0))
    return LeadEnrichment(
        persona=str(payload["persona"]),
        primary_quadrant=str(payload["primary_quadrant"]),
        secondary_tag=str(payload["secondary_tag"]),
        pain_hypothesis=str(payload["pain_hypothesis"]),
        value_prop=str(payload["value_prop"]),
        outreach_angle=str(payload["outreach_angle"]),
        confidence=confidence,
        rationale=str(payload["rationale"]),
        method=method,
        llm_used=True,
        fallback_reason="",
    )


def classify_company(record: CompanyRecord) -> LeadEnrichment:
    disabled = os.environ.get(LEAD_ENRICHMENT_DISABLED_ENV, "").strip().lower()
    if disabled in {"1", "true", "yes", "on"}:
        return classify_company_rules(record, "cache_miss_llm_disabled")

    api_key, model = lead_enrichment_llm_config()
    if not api_key or not model:
        return classify_company_rules(record, "llm_not_configured")

    cached = load_cached_llm_enrichment(record)
    if cached:
        try:
            return lead_enrichment_from_payload(cached, "llm_cache")
        except ValueError as exc:
            return classify_company_rules(record, str(exc))

    evidence_text = ""
    if os.environ.get(LEAD_ENRICHMENT_FETCH_EVIDENCE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}:
        trigger = primary_trigger(record)
        hit = primary_discovery(record)
        evidence_url = trigger.evidence_url if trigger else hit.discovery_url
        evidence_text, _ = fetch_text(evidence_url)

    prompt = build_lead_enrichment_prompt(record, evidence_text)
    try:
        payload = _call_lead_enrichment_llm(prompt, api_key, model)
        enrichment = lead_enrichment_from_payload(payload, "llm")
    except ValueError as exc:
        return classify_company_rules(record, str(exc))
    except RuntimeError:
        return classify_company_rules(record, "llm_error")

    save_cached_llm_enrichment(record, payload)
    return enrichment


def score_company(record: CompanyRecord) -> tuple[dict[str, int], int, str, str, str, str, str]:
    flags, score, band = score_company_metrics(record)
    enrichment = classify_company(record)
    return flags, score, band, enrichment.persona, enrichment.primary_quadrant, enrichment.secondary_tag, enrichment.pain_hypothesis

def primary_discovery(record: CompanyRecord) -> DiscoveryHit:
    def metadata_score(hit: DiscoveryHit) -> tuple[int, int, int, int, int, str]:
        return (
            1 if hit.cohort_year else 0,
            1 if hit.cohort_label else 0,
            1 if hit.website else 0,
            1 if hit.company_description else 0,
            1 if hit.category_or_track else 0,
            hit.source_name,
        )

    return sorted(record.discovery_hits, key=metadata_score, reverse=True)[0]

def primary_trigger(record: CompanyRecord) -> TriggerEvent | None:
    primary = [t for t in record.triggers if t.trigger_role == "Primary"]
    return primary[0] if primary else None



def main():
    from .workbook import write_workbook

    discovery_hits, search_trigger_events, run_log = run_discovery(SOURCES)
    companies = normalize_companies(discovery_hits)
    trigger_events = attach_trigger_events(companies, search_trigger_events)
    trigger_events.extend(run_trigger_research(companies))
    mark_primary_triggers(companies)
    linkedin_metrics = enrich_companies_linkedin(companies, is_linkedin_contact_target)
    run_log.append([
        "LinkedIn public-web enrichment",
        "Enrichment",
        "https://html.duckduckgo.com/html/",
        "Completed",
        (
            f"{linkedin_metrics['company_urls']}/{linkedin_metrics['companies']} company URLs; "
            f"{linkedin_metrics['targeted']} contact targets; {linkedin_metrics['complete']} complete; "
            f"{linkedin_metrics['partial']} partial; {linkedin_metrics['empty']} empty/errors"
        ),
    ])
    output = write_workbook(companies, discovery_hits, trigger_events, run_log)
    print(output.resolve())
    print(f"discovery_hits={len(discovery_hits)} companies={len(companies)} trigger_events={len(trigger_events)}")
