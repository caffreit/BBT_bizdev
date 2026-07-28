from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
INVESTOR_SOURCES = {
    "Lumira Ventures portfolio",
    "Genesys Capital portfolio",
    "Amplitude Ventures portfolio",
    "BDC current health and life-sciences portfolio",
}
FUNDER_SOURCES = {
    "FACIT oncology investment portfolio",
    "Innovate Calgary / UCeed Health",
    "MEDTEQ+",
}
DEVELOPMENT_SOURCES = {"Toronto Innovation Acceleration Partners (TIAP)"}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _id(prefix: str, *values: str) -> str:
    digest = hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def backing_type(source_name: str) -> str:
    if source_name in INVESTOR_SOURCES:
        return "investor_portfolio"
    if source_name in FUNDER_SOURCES:
        return "funder_portfolio"
    if source_name in DEVELOPMENT_SOURCES:
        return "funded_or_developed_portfolio"
    return ""


def provenance_to_backing(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence = []
    seen = set()
    for row in records:
        kind = backing_type(_clean(row.get("source_name")))
        if not kind:
            continue
        key = (row["company_id"], row["source_name"], row.get("evidence_url", ""))
        if key in seen:
            continue
        seen.add(key)
        evidence.append({
            "evidence_id": _id("ca-funding-backing", *key),
            "company_id": row["company_id"],
            "track": "funding",
            "claim_type": "institutional_backing",
            "backing_type": kind,
            "backer": row["source_name"],
            "evidence_url": row.get("evidence_url") or row.get("source_url", ""),
            "evidence_date": row.get("snapshot_date") or None,
            "captured_at": row.get("captured_at") or row.get("snapshot_date"),
            "extraction_method": "official_portfolio_provenance_conversion",
            "confidence": "high",
            "source_type": row.get("source_type", ""),
            "summary": (
                f"{row.get('source_company_name', 'Company')} appears in the official "
                f"{row['source_name']} portfolio. This proves backing/portfolio presence, "
                "not a dated funding event or disclosed amount."
            ),
            "provenance_id": row.get("provenance_id", ""),
        })
    return evidence


def _first(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _clean(row.get(key))
        if value:
            return value
    return ""


def extract_structured_event(row: dict[str, Any]) -> dict[str, Any] | None:
    """Extract only explicit, structured event fields; never mine portfolio prose."""
    event_date = _first(row, ("event_date", "announcement_date", "award_date", "date"))
    amount = _first(row, ("amount_original", "amount", "award_amount"))
    funding_type = _first(row, ("funding_type", "financing_type", "award_type"))
    stage = _first(row, ("stage", "round_stage"))
    if not event_date or not (amount or funding_type or stage):
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", event_date):
        return None
    return {
        "event_date": event_date,
        "funding_type": funding_type or "undisclosed",
        "stage": stage or "unknown",
        "amount_original": amount,
        "currency": _first(row, ("currency", "amount_currency")),
        "amount_cad": row.get("amount_cad"),
        "investors_or_funders": row.get("investors_or_funders") or row.get("funders") or [],
        "lead_investor": _first(row, ("lead_investor", "lead_funder")),
        "use_of_funds": row.get("use_of_funds") or [],
        "evidence_url": _first(row, ("evidence_url", "announcement_url", "source_url")),
        "source_type": _first(row, ("source_type",)),
        "confidence": _first(row, ("confidence",)) or "high",
    }


def extract_events(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    seen = set()
    for row in records:
        event = extract_structured_event(row)
        if not event or not row.get("company_id") or not event["evidence_url"]:
            continue
        key = (row["company_id"], event["event_date"], event["evidence_url"], event["amount_original"])
        if key in seen:
            continue
        seen.add(key)
        event.update({
            "funding_event_id": _id("ca-funding-event", *key),
            "company_id": row["company_id"],
            "captured_at": row.get("captured_at") or event["event_date"],
            "extraction_method": "structured_funding_event_extraction",
        })
        events.append(event)
    return events


def run_funding_enrichment(
    canonical_path: Path, provenance_path: Path, output_dir: Path, run_date: str
) -> dict[str, Any]:
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    companies = canonical["companies"]
    records = provenance["records"]
    backing = provenance_to_backing(records)
    # Existing source snapshots are portfolio records. This hook accepts future
    # announcement/government records only when they expose explicit event fields.
    events = extract_events(records)

    backing_by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
    events_by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in backing:
        backing_by_company[row["company_id"]].append(row)
    for row in events:
        events_by_company[row["company_id"]].append(row)

    statuses = []
    enriched = []
    for company in companies:
        cid = company["company_id"]
        company_backing = backing_by_company.get(cid, [])
        company_events = sorted(
            events_by_company.get(cid, []), key=lambda x: x["event_date"], reverse=True
        )
        if company_events:
            status = "complete_matches"
            notes = "Explicit structured funding event(s) extracted; broader source search may still be required."
        elif company_backing:
            status = "partial"
            notes = "Official portfolio backing captured; portfolio presence is not treated as a dated funding event."
        else:
            status = "not_run"
            notes = "No qualifying investor/funder provenance; announcement and government searches not yet run."
        statuses.append({
            "company_id": cid,
            "company_name": company["company_name"],
            "status": status,
            "attempted_at": run_date if company_backing or company_events else None,
            "source_url": company_backing[0]["evidence_url"] if company_backing else "",
            "raw_count": len(company_backing) + len(company_events),
            "accepted_count": len(company_events),
            "backing_evidence_count": len(company_backing),
            "notes": notes,
        })
        copy = dict(company)
        copy["funding_backing_count"] = len(company_backing)
        copy["funding_backers"] = sorted({x["backer"] for x in company_backing})
        copy["funding_event_count"] = len(company_events)
        copy["latest_funding_event"] = company_events[0] if company_events else None
        copy["completeness"] = dict(copy.get("completeness", {}))
        copy["completeness"]["funding"] = {
            key: statuses[-1][key]
            for key in ("status", "attempted_at", "source_url", "raw_count", "accepted_count", "notes")
        }
        enriched.append(copy)

    output_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "funding_backing_evidence.json": {"schema_version": SCHEMA_VERSION, "generated_at": run_date, "records": backing},
        "funding_events.json": {"schema_version": SCHEMA_VERSION, "generated_at": run_date, "events": events},
        "funding_completeness.json": {"schema_version": SCHEMA_VERSION, "generated_at": run_date, "records": statuses},
        "canonical_companies_with_funding.json": {
            "schema_version": canonical.get("schema_version", SCHEMA_VERSION),
            "generated_at": run_date,
            "companies": enriched,
        },
    }
    for name, payload in payloads.items():
        (output_dir / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with (output_dir / "funding_backing_evidence.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = [
            "evidence_id", "company_id", "backing_type", "backer", "evidence_url",
            "evidence_date", "captured_at", "confidence", "provenance_id", "summary",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(backing)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": run_date,
        "companies": len(companies),
        "backing_evidence_records": len(backing),
        "companies_with_backing": len(backing_by_company),
        "funding_events": len(events),
        "companies_with_events": len(events_by_company),
        "status_counts": dict(Counter(row["status"] for row in statuses)),
        "backing_type_counts": dict(Counter(row["backing_type"] for row in backing)),
        "next_step": "Ingest company/investor announcements and government disclosures with explicit event fields.",
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary
