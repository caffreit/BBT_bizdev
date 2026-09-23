from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_RULES_PATH = Path(__file__).resolve().parents[1] / "data" / "canada_scoring_v2_rules.json"
COMPLETE_STATUSES = {"complete_matches", "complete_zero"}
SENIOR_LEVELS = {"director", "head", "vp", "vice president", "executive", "chief"}


def load_rules(path: Path = DEFAULT_RULES_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clean(value: Any) -> str:
    return str(value or "").strip().casefold()


def normalize_employee_band(value: Any) -> str:
    text = _clean(value).replace("–", "-").replace("—", "-").replace(",", "")
    if not text or text == "unknown":
        return "unknown"
    if any(token in text for token in ("501+", "500+", "1000", "5000")):
        return "501+"
    if any(token in text for token in ("201-500", "200-500")):
        return "201-500"
    if any(token in text for token in ("51-200", "50-200", "51-201")):
        return "51-200"
    if any(token in text for token in ("20-50", "21-50", "11-50")):
        return "20-50"
    if any(token in text for token in ("1-19", "1-10", "2-10", "1-20")):
        return "1-19"
    return "unknown"


def _accepted(record: dict[str, Any], *, dated: bool = False) -> bool:
    if _clean(record.get("status")) not in {"accepted", "open_verified", "current_verified"}:
        return False
    if not record.get("evidence_id") or not record.get("evidence_url"):
        return False
    if dated and not (record.get("event_date") or record.get("evidence_date")):
        return False
    return True


def _age_days(value: Any, as_of: date) -> int | None:
    if not value:
        return None
    try:
        return (as_of - date.fromisoformat(str(value)[:10])).days
    except ValueError:
        return None


def _recency_factor(value: Any, as_of: date, rules: dict[str, Any]) -> float:
    age = _age_days(value, as_of)
    if age is None or age < 0:
        return 0.0
    for band in rules["timing"]["recency_factors"]:
        if age <= int(band["maximum_age_days"]):
            return float(band["factor"])
    return 0.0


def _add_rule(
    fired: list[dict[str, Any]], rule_id: str, points: float,
    evidence_ids: list[str] | None = None, detail: str = "",
) -> None:
    if points <= 0:
        return
    fired.append({
        "rule_id": rule_id,
        "points": round(points, 2),
        "evidence_ids": sorted(set(evidence_ids or [])),
        "detail": detail,
    })


def score_company(
    company: dict[str, Any], *, as_of: str, rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules = rules or load_rules()
    as_of_date = date.fromisoformat(as_of)
    fired: list[dict[str, Any]] = []
    missing: list[str] = []

    eligibility = _clean(company.get("eligibility", "eligible"))
    exclusion_reasons = list(company.get("exclusion_reasons") or [])
    if eligibility == "excluded" and not exclusion_reasons:
        exclusion_reasons.append("explicitly_excluded")

    deliverable = company.get("regulated_deliverable") or {}
    deliverable_status = _clean(deliverable.get("status")) or "unknown"
    fit_deliverable = float(rules["fit"]["regulated_deliverable"].get(deliverable_status, 0))
    _add_rule(
        fired, f"fit.regulated_deliverable.{deliverable_status}", fit_deliverable,
        list(deliverable.get("evidence_ids") or []),
    )
    if deliverable_status == "unknown":
        missing.append("regulated_deliverable")

    eligible_needs = set(rules["fit"]["eligible_service_needs"])
    accepted_needs = {
        _clean(item.get("need")): item
        for item in company.get("service_needs") or []
        if _clean(item.get("status")) == "confirmed"
        and _clean(item.get("need")) in eligible_needs
        and item.get("evidence_ids")
    }
    fit_needs = min(
        float(rules["fit"]["service_need_cap"]),
        len(accepted_needs) * float(rules["fit"]["service_need_points_each"]),
    )
    _add_rule(
        fired, "fit.confirmed_service_needs", fit_needs,
        [evidence_id for item in accepted_needs.values() for evidence_id in item.get("evidence_ids", [])],
        ", ".join(sorted(accepted_needs)),
    )
    if not company.get("service_needs"):
        missing.append("service_needs")

    employee_band = normalize_employee_band((company.get("employee_band") or {}).get("value"))
    employee_evidence = list((company.get("employee_band") or {}).get("evidence_ids") or [])
    fit_stage = float(rules["fit"]["stage_suitability"].get(employee_band, 0)) if employee_evidence else 0.0
    _add_rule(fired, f"fit.stage_suitability.{employee_band}", fit_stage, employee_evidence)
    if employee_band == "unknown" or not employee_evidence:
        missing.append("employee_band")
    fit = min(35.0, fit_deliverable + fit_needs + fit_stage)

    roles = [row for row in company.get("open_roles") or [] if _accepted(row)]
    role_points = min(
        float(rules["timing"]["role_points_cap"]),
        len(roles) * float(rules["timing"]["role_points_each"]),
    )
    _add_rule(fired, "timing.verified_open_roles", role_points, [row["evidence_id"] for row in roles])
    if any(_clean(row.get("seniority")) in SENIOR_LEVELS for row in roles):
        bonus = float(rules["timing"]["senior_role_bonus"])
        _add_rule(fired, "timing.senior_role", bonus, [row["evidence_id"] for row in roles])
        role_points += bonus
    role_points = min(12.0, role_points)

    milestone_candidates: list[tuple[float, dict[str, Any]]] = []
    for row in company.get("milestones") or []:
        if not _accepted(row, dated=True):
            continue
        event_type = _clean(row.get("event_type"))
        base = float(rules["timing"]["milestone_points"].get(event_type, 0))
        points = base * _recency_factor(row.get("event_date") or row.get("evidence_date"), as_of_date, rules)
        milestone_candidates.append((points, row))
    milestone_points, milestone = max(milestone_candidates, default=(0.0, {}), key=lambda item: item[0])
    _add_rule(
        fired, f"timing.milestone.{_clean(milestone.get('event_type'))}",
        milestone_points, [milestone.get("evidence_id", "")],
    )

    trigger_candidates: list[tuple[float, dict[str, Any]]] = []
    for row in company.get("triggers") or []:
        if not _accepted(row, dated=True):
            continue
        event_type = _clean(row.get("event_type"))
        base = float(rules["timing"]["trigger_points"].get(event_type, 0))
        points = base * _recency_factor(row.get("event_date") or row.get("evidence_date"), as_of_date, rules)
        trigger_candidates.append((points, row))
    trigger_points, trigger = max(trigger_candidates, default=(0.0, {}), key=lambda item: item[0])
    _add_rule(
        fired, f"timing.trigger.{_clean(trigger.get('event_type'))}",
        trigger_points, [trigger.get("evidence_id", "")],
    )
    timing = min(30.0, role_points + milestone_points + trigger_points)

    funding_candidates: list[tuple[str, dict[str, Any]]] = []
    for row in company.get("funding_events") or []:
        if _accepted(row, dated=True):
            funding_candidates.append((str(row.get("event_date") or row.get("evidence_date"))[:10], row))
    latest_funding = max(funding_candidates, default=("", {}), key=lambda item: item[0])[1]
    funding_points = 0.0
    if latest_funding:
        funding_type = _clean(latest_funding.get("funding_type")) or "undisclosed"
        type_factor = float(rules["ability_to_buy"]["funding_type_factors"].get(funding_type, 0.4))
        recency = _recency_factor(
            latest_funding.get("event_date") or latest_funding.get("evidence_date"),
            as_of_date, rules,
        )
        recency_points = float(rules["ability_to_buy"]["funding_recency_points"]) * recency * type_factor
        amount = float(latest_funding.get("amount_cad") or 0)
        amount_points = 0.0
        for band in rules["ability_to_buy"]["funding_amount_points"]:
            if amount >= float(band["minimum_cad"]):
                amount_points = float(band["points"]) * type_factor
                break
        funding_points = min(15.0, recency_points + amount_points)
        _add_rule(
            fired, f"ability.funding.{funding_type}", funding_points,
            [latest_funding["evidence_id"]],
        )

    backing = [row for row in company.get("institutional_backing") or [] if _accepted(row)]
    backing_points = float(rules["ability_to_buy"]["institutional_backing_points"]) if backing else 0.0
    _add_rule(fired, "ability.institutional_backing", backing_points, [row["evidence_id"] for row in backing])
    employee_points = float(rules["ability_to_buy"]["employee_band_points"].get(employee_band, 0)) if employee_evidence else 0.0
    _add_rule(fired, f"ability.employee_band.{employee_band}", employee_points, employee_evidence)
    ability = min(25.0, funding_points + backing_points + employee_points)

    canada = company.get("canada_relationship") or {}
    canada_value = _clean(canada.get("value")) or "unknown"
    canada_evidence = list(canada.get("evidence_ids") or [])
    canada_points = float(rules["canada_relevance"].get(canada_value, 0)) if canada_evidence else 0.0
    _add_rule(fired, f"canada.{canada_value}", canada_points, canada_evidence)
    if canada_value == "unknown" or not canada_evidence:
        missing.append("canada_relationship")

    completeness = company.get("completeness") or {}
    confidence = 0.0
    comparable = True
    for track, weight in rules["confidence"]["track_weights"].items():
        row = completeness.get(track) or {}
        status = _clean(row.get("status")) or "not_run"
        factor = float(rules["confidence"]["status_factors"].get(status, 0))
        quality_factor = max(0.0, min(1.0, float(row.get("quality_factor", 1.0))))
        confidence += float(weight) * factor * quality_factor
        if track in rules["confidence"]["comparable_required_tracks"] and status not in COMPLETE_STATUSES:
            comparable = False

    priority = 0.0 if exclusion_reasons else fit + timing + ability + canada_points
    return {
        "company_id": company.get("company_id", ""),
        "scoring_version": rules["scoring_version"],
        "as_of": as_of,
        "eligible": not exclusion_reasons,
        "exclusion_reasons": exclusion_reasons,
        "fit": round(fit, 2),
        "timing": round(timing, 2),
        "ability_to_buy": round(ability, 2),
        "canada_relevance": round(canada_points, 2),
        "priority_score": round(priority, 2),
        "evidence_confidence": round(confidence, 2),
        "comparable_coverage": comparable,
        "missing_data_flags": sorted(set(missing)),
        "fired_rules": fired,
    }
