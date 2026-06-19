from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


TODAY = date.today().isoformat()


@dataclass(frozen=True)
class Source:
    name: str
    source_type: str
    url: str
    geography: str
    priority: str
    update_cadence: str
    extraction_method: str
    notes: str
    adapter: str | None = None


@dataclass
class DiscoveryHit:
    company: str
    source_name: str
    source_type: str
    discovery_url: str
    discovery_rationale: str
    product_type: str = ""
    geography: str = ""
    website: str = ""
    matched_terms: str = ""
    article_year: str = ""
    captured_at: str = TODAY
    accelerator_program: str = ""
    cohort_label: str = ""
    cohort_year: str = ""
    category_or_track: str = ""
    company_description: str = ""


@dataclass
class TriggerEvent:
    company: str
    trigger_type: str
    trigger_event: str
    trigger_source: str
    evidence_url: str
    trigger_role: str = "Secondary"
    captured_at: str = TODAY


@dataclass(frozen=True)
class SearchResult:
    query: str
    title: str
    link: str
    summary: str = ""
    publisher: str = ""
    published_at: str = ""


@dataclass(frozen=True)
class JobPosting:
    title: str
    url: str
    description: str = ""
    location: str = ""
    department: str = ""


@dataclass(frozen=True)
class JobLead:
    company: str
    posting: JobPosting
    query: str = ""


@dataclass
class LeadEnrichment:
    persona: str
    primary_quadrant: str
    secondary_tag: str
    pain_hypothesis: str
    value_prop: str
    outreach_angle: str
    confidence: float
    rationale: str
    method: str
    llm_used: bool = False
    fallback_reason: str = ""


@dataclass
class CompanyRecord:
    company: str
    website: str = ""
    geography: str = ""
    product_type: str = ""
    discovery_hits: list[DiscoveryHit] = field(default_factory=list)
    triggers: list[TriggerEvent] = field(default_factory=list)
