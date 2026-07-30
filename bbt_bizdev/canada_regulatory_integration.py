from __future__ import annotations

import json
import hashlib
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any


SOURCE_FILES = {
    "mdall": (
        "mdall_regulatory_evidence.json",
        "mdall_completeness.json",
        "mdall_manual_review.json",
    ),
    "mdel": (
        "mdel_regulatory_evidence.json",
        "mdel_completeness.json",
        "mdel_manual_review.json",
    ),
    "health_canada_trials": (
        "clinical_trial_regulatory_evidence.json",
        "clinical_trial_completeness.json",
        "clinical_trial_manual_review.json",
    ),
    "fda": (
        "fda_regulatory_evidence.json",
        "fda_completeness.json",
        "fda_manual_review.json",
    ),
    "fda_denovo": (
        "denovo_regulatory_evidence.json",
        "denovo_completeness.json",
        "denovo_manual_review.json",
    ),
    "fda_registration": (
        "registration_regulatory_evidence.json",
        "registration_completeness.json",
        "registration_manual_review.json",
    ),
}


def _records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [row for row in payload.get("records", []) if isinstance(row, dict)]


def denovo_from_registration(row: dict[str, Any]) -> dict[str, Any] | None:
    number = str(row.get("k_number") or "").strip().upper()
    if not number.startswith("DEN"):
        return None
    digest = hashlib.sha256(
        f"{row['company_id']}|FDA|De Novo|{number}".encode("utf-8")
    ).hexdigest()[:20]
    return {
        "evidence_id": "ca-regulatory-evidence-" + digest,
        "company_id": row["company_id"],
        "track": "regulatory",
        "claim_type": "FDA De Novo classification referenced by active device listing",
        "jurisdiction": "US",
        "authority": "FDA",
        "record_type": "De Novo",
        "record_id": number,
        "legal_manufacturer": row.get("legal_manufacturer", ""),
        "product_name": row.get("product_name", ""),
        "device_class": row.get("device_class", ""),
        "status": "cleared",
        "decision_or_start_date": None,
        "evidence_url": (
            "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/"
            f"denovo.cfm?id={number}"
        ),
        "evidence_date": None,
        "captured_at": row.get("captured_at"),
        "extraction_method": "openfda_active_listing_denovo_identifier",
        "source_type": "regulator",
        "match_basis": row.get("match_basis"),
        "confidence": "high",
        "source_listing_evidence_id": row.get("evidence_id"),
        "raw_record": row.get("raw_record"),
    }


def aggregate_status(
    source_rows: list[dict[str, Any]], evidence_count: int, review_count: int
) -> str:
    statuses = {row.get("status") for row in source_rows}
    if evidence_count and statuses & {"failed", "partial"}:
        return "partial"
    if evidence_count:
        return "complete_matches"
    if statuses == {"failed"}:
        return "failed"
    if statuses & {"failed", "partial"}:
        return "partial"
    if review_count or "manual_review" in statuses:
        return "manual_review"
    if source_rows and statuses <= {"complete_zero", "no_source"}:
        return "complete_zero"
    return "not_run"


def regulatory_summary(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    counts = Counter((row.get("authority"), row.get("record_type")) for row in records)
    parts = [
        f"{authority} {record_type}: {count}"
        for (authority, record_type), count in sorted(
            counts.items(), key=lambda item: (str(item[0][0]), str(item[0][1]))
        )
    ]
    return "; ".join(parts)


def integrate_regulatory_outputs(
    companies_path: Path,
    source_dirs: dict[str, Path | list[Path]],
    output_dir: Path,
    run_date: str | None = None,
) -> dict[str, Any]:
    run_date = run_date or date.today().isoformat()
    payload = json.loads(companies_path.read_text(encoding="utf-8"))
    evidence, completeness, review = [], [], []
    source_summaries = {}
    for source, directories in source_dirs.items():
        if source not in SOURCE_FILES:
            raise ValueError(f"Unsupported regulatory source: {source}")
        evidence_file, completeness_file, review_file = SOURCE_FILES[source]
        directories = directories if isinstance(directories, list) else [directories]
        source_evidence_rows, source_completeness_rows, source_review_rows = [], [], []
        for directory_index, directory in enumerate(directories):
            source_evidence_rows.extend(_records(directory / evidence_file))
            rows = _records(directory / completeness_file)
            if source == "fda" and directory_index == 0 and len(directories) > 1:
                for row in rows:
                    notes = str(row.get("notes") or "")
                    if (
                        "PMA applicant batch:" in notes
                        and "510(k) Canada bulk query:" not in notes
                    ):
                        row["status"] = (
                            "complete_matches"
                            if row.get("accepted_count")
                            else "complete_zero"
                        )
                        row["notes"] = (
                            "Canadian 510(k) bulk query and this company's PMA "
                            "batch completed, or its failed PMA batch is overlaid "
                            "by a targeted retry."
                        )
            source_completeness_rows.extend(rows)
            source_review_rows.extend(_records(directory / review_file))
        source_evidence = list({
            row["evidence_id"]: row for row in source_evidence_rows
        }.values())
        if source == "fda_registration":
            derived = [
                value for value in (
                    denovo_from_registration(row) for row in source_evidence
                ) if value
            ]
            source_evidence.extend(derived)
        # Later directories are retries and replace the earlier status for the
        # same company without discarding successful records for other companies.
        source_completeness = list({
            row["company_id"]: row for row in source_completeness_rows
        }.values())
        source_review = list({
            json.dumps(row, ensure_ascii=False, sort_keys=True): row
            for row in source_review_rows
        }.values())
        evidence.extend({**row, "regulatory_source": source} for row in source_evidence)
        completeness.extend({**row, "regulatory_source": source} for row in source_completeness)
        review.extend({**row, "regulatory_source": source} for row in source_review)
        source_summaries[source] = {
            "evidence_records": len(source_evidence),
            "companies_checked": len(source_completeness),
            "review_records": len(source_review),
        }

    evidence = list({row["evidence_id"]: row for row in evidence}.values())
    evidence.sort(key=lambda row: (
        row["company_id"], str(row.get("authority")), str(row.get("record_type")),
        str(row.get("record_id")),
    ))
    by_company_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_company_completeness: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_company_review: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence:
        by_company_evidence[row["company_id"]].append(row)
    for row in completeness:
        by_company_completeness[row["company_id"]].append(row)
    for row in review:
        by_company_review[row["company_id"]].append(row)

    company_statuses = []
    for company in payload["companies"]:
        company_id = company["company_id"]
        records = by_company_evidence.get(company_id, [])
        source_rows = by_company_completeness.get(company_id, [])
        reviews = by_company_review.get(company_id, [])
        status = aggregate_status(source_rows, len(records), len(reviews))
        aggregate = {
            "status": status,
            "attempted_at": run_date if source_rows else None,
            "source_url": "",
            "raw_count": sum((row.get("raw_count") or 0) for row in source_rows),
            "accepted_count": len(records),
            "notes": (
                f"Combined {len(source_rows)} regulatory source checks; "
                f"{len(reviews)} unresolved review candidates."
            ),
        }
        company.setdefault("completeness", {})["regulatory"] = aggregate
        company["regulatory_record_count"] = len(records)
        company["regulatory_summary"] = regulatory_summary(records)
        company["regulatory_authorities"] = sorted({
            str(row.get("authority")) for row in records if row.get("authority")
        })
        company["regulatory_unresolved_count"] = len(reviews)
        if records or source_rows:
            company["last_enriched_at"] = run_date
        company_statuses.append({
            "company_id": company_id,
            "company_name": company["company_name"],
            **aggregate,
            "regulatory_summary": company["regulatory_summary"],
            "sources_checked": sorted({
                row["regulatory_source"] for row in source_rows
            }),
            "unresolved_review_count": len(reviews),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "regulatory_evidence.json": {
            "schema_version": "1.0", "generated_at": run_date, "records": evidence,
        },
        "regulatory_source_completeness.json": {
            "schema_version": "1.0", "generated_at": run_date, "records": completeness,
        },
        "regulatory_company_completeness.json": {
            "schema_version": "1.0", "generated_at": run_date, "records": company_statuses,
        },
        "regulatory_manual_review.json": {
            "schema_version": "1.0", "generated_at": run_date, "records": review,
        },
        "canonical_companies_regulatory.json": {
            "schema_version": payload.get("schema_version", "1.0"),
            "generated_at": run_date,
            "companies": payload["companies"],
        },
    }
    for filename, data in outputs.items():
        (output_dir / filename).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    summary = {
        "schema_version": "1.0",
        "generated_at": run_date,
        "canonical_companies": len(payload["companies"]),
        "regulatory_evidence_records": len(evidence),
        "companies_with_regulatory_evidence": len(by_company_evidence),
        "manual_review_records": len(review),
        "company_status_counts": dict(Counter(row["status"] for row in company_statuses)),
        "source_summaries": source_summaries,
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary
