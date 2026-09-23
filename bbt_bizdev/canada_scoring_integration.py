from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any

from .canada_regulatory_integration import regulatory_signal_semantics
from .canada_scoring import COMPLETE_STATUSES, score_company


ROLE_TO_NEED = {
    "qa": "quality_systems",
    "regulatory": "regulatory",
    "v&v/design assurance": "verification_validation",
    "clinical": "clinical_validation",
    "manufacturing": "manufacturing_transfer",
    "software medical product": "software_assurance",
    "r&d/product": "product_development",
}
EVENT_TO_NEED = {
    "regulatory submission claim": "regulatory",
    "regulatory submission": "regulatory",
    "validation": "verification_validation",
    "clinical study": "clinical_validation",
    "manufacturing": "manufacturing_transfer",
    "product launch": "product_development",
}
MILESTONE_TYPES = {
    "regulatory submission claim": "regulatory_submission",
    "regulatory submission": "regulatory_submission",
    "regulatory approval": "regulatory_approval",
    "validation": "clinical_validation",
    "clinical study": "clinical_study_started",
    "manufacturing": "manufacturing_scale_up",
    "product launch": "product_launch",
    "prototype": "prototype",
}
TRIGGER_TYPES = {
    "partnership": "partnership",
    "deployment": "deployment",
    "expansion": "expansion",
    "licensing agreement": "licensing_agreement",
    "new indication": "new_indication",
    "new geography": "new_geography",
}


def _group(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    values: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("company_id"):
            values[row["company_id"]].append(row)
    return values


def _stable_id(prefix: str, *values: Any) -> str:
    digest = hashlib.sha256("|".join(str(value or "") for value in values).encode()).hexdigest()[:20]
    return f"{prefix}-{digest}"


def _status(value: Any) -> str:
    return str(value or "").strip().casefold()


def combine_product_news_status(product: dict[str, Any], news: dict[str, Any]) -> str:
    statuses = {_status(product.get("status")), _status(news.get("status"))}
    if statuses <= COMPLETE_STATUSES:
        return "complete_matches" if "complete_matches" in statuses else "complete_zero"
    for value in ("failed", "blocked", "partial", "manual_review", "no_source", "not_run"):
        if value in statuses:
            return value
    return "not_run"


def build_scoring_inputs(
    companies: list[dict[str, Any]], *,
    provenance: list[dict[str, Any]],
    hiring: list[dict[str, Any]],
    hiring_companies: list[dict[str, Any]],
    funding_events: list[dict[str, Any]],
    backing: list[dict[str, Any]],
    funding_companies: list[dict[str, Any]],
    regulatory: list[dict[str, Any]],
    regulatory_companies: list[dict[str, Any]],
    product_profiles: list[dict[str, Any]],
    product_events: list[dict[str, Any]],
    product_completeness: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped = {
        "provenance": _group(provenance), "hiring": _group(hiring),
        "funding": _group(funding_events), "backing": _group(backing),
        "regulatory": _group([regulatory_signal_semantics(row) for row in regulatory]),
        "profiles": _group(product_profiles), "events": _group(product_events),
    }
    hiring_status = {row["company_id"]: row.get("completeness", {}).get("hiring", {}) for row in hiring_companies}
    funding_status = {row["company_id"]: row.get("completeness", {}).get("funding", {}) for row in funding_companies}
    regulatory_status = {row["company_id"]: row.get("completeness", {}).get("regulatory", {}) for row in regulatory_companies}
    product_status = {row["company_id"]: row for row in product_completeness}
    output = []
    for company in companies:
        cid = company["company_id"]
        prov = grouped["provenance"].get(cid, [])
        roles = grouped["hiring"].get(cid, [])
        regs = grouped["regulatory"].get(cid, [])
        profiles = grouped["profiles"].get(cid, [])
        events = grouped["events"].get(cid, [])

        profile_evidence = []
        for row in profiles:
            evidence_id = row.get("evidence_id") or _stable_id(
                "product", cid, row.get("evidence_url"), row.get("product_summary")
            )
            if row.get("evidence_url"):
                profile_evidence.append(evidence_id)
        current_authorizations = [row for row in regs if row.get("current_milestone_eligible")]
        category = str(company.get("product_category") or "").casefold()
        regulated_category = any(value in category for value in ("medical device", "diagnostic", "samd"))
        if current_authorizations:
            deliverable_status = "confirmed"
            deliverable_evidence = [row["evidence_id"] for row in current_authorizations]
        elif profiles and regulated_category:
            deliverable_status = "confirmed"
            deliverable_evidence = profile_evidence
        elif profiles:
            deliverable_status = "probable"
            deliverable_evidence = profile_evidence
        elif regulated_category:
            deliverable_status = "category_only"
            deliverable_evidence = [row.get("provenance_id") for row in prov if row.get("provenance_id")]
        else:
            deliverable_status = "unknown"
            deliverable_evidence = []

        need_evidence: dict[str, list[str]] = defaultdict(list)
        for row in roles:
            need = ROLE_TO_NEED.get(_status(row.get("role_family")))
            if need and row.get("evidence_id"):
                need_evidence[need].append(row["evidence_id"])
        for row in events:
            need = EVENT_TO_NEED.get(_status(row.get("event_type") or row.get("claim_type")))
            if need and row.get("evidence_id"):
                need_evidence[need].append(row["evidence_id"])

        open_roles = [{
            **row,
            "status": "open_verified" if _status(row.get("posting_status")) == "open" else _status(row.get("posting_status")),
        } for row in roles]
        normalized_funding = [{
            **row,
            "evidence_id": row.get("evidence_id") or row.get("funding_event_id"),
            "status": "accepted",
        } for row in grouped["funding"].get(cid, [])]
        normalized_backing = [{**row, "status": "accepted"} for row in grouped["backing"].get(cid, [])]
        milestones = []
        for row in current_authorizations:
            milestones.append({
                "status": "accepted", "evidence_id": row["evidence_id"],
                "evidence_url": row.get("evidence_url"),
                "event_type": "regulatory_clearance",
                "event_date": row.get("decision_or_start_date") or row.get("evidence_date"),
            })
        triggers = []
        for row in events:
            raw_type = _status(row.get("event_type") or row.get("claim_type"))
            normalized = MILESTONE_TYPES.get(raw_type)
            if normalized:
                milestones.append({
                    "status": "accepted", "evidence_id": row.get("evidence_id"),
                    "evidence_url": row.get("evidence_url"), "event_type": normalized,
                    "event_date": row.get("event_date") or row.get("evidence_date"),
                })
            trigger = TRIGGER_TYPES.get(raw_type)
            if trigger:
                triggers.append({
                    "status": "accepted", "evidence_id": row.get("evidence_id"),
                    "evidence_url": row.get("evidence_url"), "event_type": trigger,
                    "event_date": row.get("event_date") or row.get("evidence_date"),
                })

        canada_value = {
            "hq": "hq", "headquarters": "hq",
            "substantial canadian product-development operation": "substantial_product_development",
            "canadian operation": "other_operation", "program location only": "program_only",
        }.get(_status(company.get("canada_relationship")), "unknown")
        canada_evidence = [
            row.get("provenance_id") for row in prov
            if row.get("provenance_id") and row.get("geography")
        ]
        # The original consolidation labelled every company as program-only,
        # even where source provenance carries Canadian geography. Treat that
        # as evidence of an operation, but do not infer headquarters.
        if canada_value == "program_only" and canada_evidence:
            canada_value = "other_operation"
        employee_band = str(company.get("employee_band") or "unknown")
        stage = str(company.get("company_stage") or "unknown")
        pc = product_status.get(cid, {})
        product_news = combine_product_news_status(
            pc.get("product_development", {}), pc.get("news", {})
        )
        output.append({
            "company_id": cid,
            "company_name": company.get("company_name", ""),
            "eligibility": "excluded" if _status(company.get("operating_status")) in {"inactive", "dissolved"} else "eligible",
            "exclusion_reasons": (
                [_status(company.get("operating_status"))]
                if _status(company.get("operating_status")) in {"inactive", "dissolved"} else []
            ),
            "regulated_deliverable": {"status": deliverable_status, "evidence_ids": deliverable_evidence},
            "service_needs": [
                {"need": need, "status": "confirmed", "evidence_ids": sorted(set(ids))}
                for need, ids in sorted(need_evidence.items())
            ],
            "employee_band": {"value": employee_band, "evidence_ids": []},
            "canada_relationship": {"value": canada_value, "evidence_ids": canada_evidence},
            "open_roles": open_roles,
            "milestones": milestones,
            "triggers": triggers,
            "funding_events": normalized_funding,
            "institutional_backing": normalized_backing,
            "completeness": {
                "identity_canada": {"status": "complete_matches" if prov and canada_evidence else "partial"},
                "firmographics": {"status": "complete_matches" if employee_band.casefold() != "unknown" and stage.casefold() != "unknown" else "partial"},
                "hiring": {"status": hiring_status.get(cid, {}).get("status", "not_run")},
                "funding": {"status": funding_status.get(cid, {}).get("status", "not_run")},
                "regulatory": {"status": regulatory_status.get(cid, {}).get("status", "not_run")},
                "product_news": {"status": product_news},
            },
        })
    return output


def score_universe(inputs: list[dict[str, Any]], as_of: str) -> dict[str, Any]:
    records = []
    for item in inputs:
        score = score_company(item, as_of=as_of)
        records.append({"company_name": item.get("company_name", ""), **score})
    records.sort(key=lambda row: (
        not row["eligible"], -row["priority_score"], -row["evidence_confidence"],
        row["company_name"].casefold(),
    ))
    for rank, row in enumerate(records, start=1):
        row["rank"] = rank if row["eligible"] else None
    eligible = [row for row in records if row["eligible"]]
    cutoff = eligible[49]["priority_score"] if len(eligible) >= 50 else (eligible[-1]["priority_score"] if eligible else 0)
    review_queue = [row for row in eligible if row["priority_score"] >= cutoff]
    baseline_top = {row["company_id"] for row in eligible[:50]}
    sensitivity = {}
    for component in ("fit", "timing", "ability_to_buy", "canada_relevance"):
        reordered = sorted(
            eligible,
            key=lambda row: (
                -(row["priority_score"] - row[component]),
                -row["evidence_confidence"], row["company_name"].casefold(),
            ),
        )
        alternate_top = {row["company_id"] for row in reordered[:50]}
        overlap = len(baseline_top & alternate_top)
        sensitivity[component] = {
            "top_50_overlap_count": overlap,
            "top_50_overlap_percent": round(100 * overlap / max(1, len(baseline_top)), 1),
        }
    return {
        "records": records,
        "review_queue": review_queue,
        "leave_one_component_out": sensitivity,
        "summary": {
            "companies": len(records),
            "eligible_companies": len(eligible),
            "comparable_coverage_companies": sum(row["comparable_coverage"] for row in eligible),
            "top_50_cutoff_score": cutoff,
            "review_queue_including_ties": len(review_queue),
            "top_50_comparable_coverage": sum(row["comparable_coverage"] for row in eligible[:50]),
            "release_ready": bool(eligible[:50]) and all(row["comparable_coverage"] for row in eligible[:50]),
        },
    }
