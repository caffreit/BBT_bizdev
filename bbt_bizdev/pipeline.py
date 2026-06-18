from __future__ import annotations

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
from .adapters.search import run_google_news_search
from .adapters.university import run_university_spinout_pages
from .adapters.vc import run_atlantic_bridge, run_fountain_healthcare, run_seroba_life_sciences
from .config import ADAPTER_STATUS_NAMES, COMPANY_REGISTRY, JOB_BOARD_ADAPTERS, SOURCES, TRIGGER_SOURCES, UNIVERSITY_SPINOUT_ADAPTERS
from .http import fetch_text, fetch_raw_text
from .models import CompanyRecord, DiscoveryHit, Source, TriggerEvent
from .text import text_from_html


def run_discovery(sources: list[Source]) -> tuple[list[DiscoveryHit], list[TriggerEvent], list[list[str]]]:
    discovery_hits: list[DiscoveryHit] = []
    trigger_events: list[TriggerEvent] = []
    run_log: list[list[str]] = []
    for source in sources:
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
        if source.adapter in UNIVERSITY_SPINOUT_ADAPTERS:
            hits, triggers, result = run_university_spinout_pages(source)
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

def score_company(record: CompanyRecord) -> tuple[dict[str, int], int, str, str, str, str]:
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
    persona = "AI/SaMD or healthtech company from approved source"
    quadrant = "Advisory"
    secondary = "Design/dev" if "imaging" in text or "diagnostic" in text else "Embedded support"
    pain = "Likely needs a defensible regulatory, validation, claims, or productisation story before broader commercial expansion."
    return flags, score, band, persona, quadrant, secondary, pain

def primary_discovery(record: CompanyRecord) -> DiscoveryHit:
    return sorted(record.discovery_hits, key=lambda h: h.source_name)[0]

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
    output = write_workbook(companies, discovery_hits, trigger_events, run_log)
    print(output.resolve())
    print(f"discovery_hits={len(discovery_hits)} companies={len(companies)} trigger_events={len(trigger_events)}")
