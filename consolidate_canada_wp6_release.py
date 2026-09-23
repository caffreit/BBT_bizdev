from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path("outputs")


def load(path: Path, key: str) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8-sig")).get(key, [])


def write(path: Path, key: str, rows: list[dict[str, Any]], generated_at: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": "2.0", "generated_at": generated_at, key: rows}, indent=2, ensure_ascii=False), encoding="utf-8")


def dedupe(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = next((str(row.get(field)) for field in keys if row.get(field)), "")
        if not key:
            key = hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()
        chosen[key] = row
    return sorted(chosen.values(), key=lambda row: (str(row.get("company_id", "")), str(row.get(keys[0], ""))))


def nested_company_rows(companies: list[dict[str, Any]], track: str, status_rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for company in companies:
        copied = json.loads(json.dumps(company))
        row = status_rows.get(company["company_id"], {})
        copied.setdefault("completeness", {})[track] = {
            "status": row.get("status", "not_run"),
            "attempted_at": row.get("attempted_at"), "source_url": row.get("source_url", ""),
            "raw_count": row.get("raw_count"), "accepted_count": row.get("accepted_count"),
            "notes": row.get("notes", ""),
        }
        output.append(copied)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolidate refreshed Canada WP6 evidence into a scored-release input set.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()
    out = args.output_dir

    canonical_path = ROOT / "canada_website_luna_2026-07-28_all_sources_v3/canonical_companies_luna_websites_enriched.json"
    canonical = load(canonical_path, "companies")
    provenance = load(ROOT / "canada_company_identity_2026-07-27/source_provenance.json", "records")

    hiring_dir = ROOT / "canada_wp6_release_2026-08-06/data/hiring"
    hiring = load(hiring_dir / "hiring_evidence.json", "records")
    hiring_companies = load(hiring_dir / "canonical_companies_hiring_enriched.json", "companies")

    old_funding = load(ROOT / "canada_funding_2026-07-28/funding_events.json", "events")
    government_funding = load(ROOT / "canada_full_universe_refresh_2026-08-04/government_funding/government_funding_events.json", "events")
    funding_events = dedupe(old_funding + government_funding, ("funding_event_id", "evidence_id"))
    backing = load(ROOT / "canada_funding_2026-07-28/funding_backing_evidence.json", "records")
    old_funding_companies = load(ROOT / "canada_funding_2026-07-28/canonical_companies_with_funding.json", "companies")
    old_funding_status = {row["company_id"]: row.get("completeness", {}).get("funding", {}) for row in old_funding_companies}
    gov_status = {row["company_id"]: row for row in load(ROOT / "canada_full_universe_refresh_2026-08-04/government_funding/government_funding_completeness.json", "records")}
    funding_counts: dict[str, int] = {}
    for row in funding_events:
        funding_counts[row["company_id"]] = funding_counts.get(row["company_id"], 0) + 1
    funding_status: dict[str, dict[str, Any]] = {}
    for company in canonical:
        cid = company["company_id"]
        old, gov = old_funding_status.get(cid, {}), gov_status.get(cid, {})
        if funding_counts.get(cid):
            status = "complete_matches"
        elif gov.get("status") == "failed":
            status = "failed"
        elif old.get("status") == "complete_zero" and gov.get("status") == "complete_zero":
            status = "complete_zero"
        else:
            status = "partial"
        funding_status[cid] = {
            "status": status, "attempted_at": gov.get("attempted_at") or old.get("attempted_at"),
            "source_url": gov.get("source_url") or old.get("source_url", ""),
            "raw_count": int(gov.get("raw_count") or 0), "accepted_count": funding_counts.get(cid, 0),
            "notes": "Government grants plus prior institutional-backing/event sources consolidated; broader private financing recall remains partial." if status == "partial" else gov.get("notes", ""),
        }
    funding_companies = nested_company_rows(canonical, "funding", funding_status)

    old_regulatory = load(ROOT / "canada_regulatory_2026-07-28/regulatory_evidence.json", "records")
    mdall = load(ROOT / "canada_full_universe_refresh_2026-08-04/regulatory/mdall_regulatory_evidence.json", "records")
    regulatory = dedupe(old_regulatory + mdall, ("evidence_id",))
    old_reg_companies = load(ROOT / "canada_regulatory_2026-07-28/canonical_companies_regulatory.json", "companies")
    old_reg_status = {row["company_id"]: row.get("completeness", {}).get("regulatory", {}) for row in old_reg_companies}
    mdall_status = {row["company_id"]: row for row in load(ROOT / "canada_full_universe_refresh_2026-08-04/regulatory/mdall_completeness.json", "records")}
    regulatory_counts: dict[str, int] = {}
    for row in regulatory:
        regulatory_counts[row["company_id"]] = regulatory_counts.get(row["company_id"], 0) + 1
    regulatory_status: dict[str, dict[str, Any]] = {}
    for company in canonical:
        cid = company["company_id"]
        old, current = old_reg_status.get(cid, {}), mdall_status.get(cid, {})
        if regulatory_counts.get(cid):
            status = "complete_matches"
        elif current.get("status") == "failed":
            status = "failed"
        elif "manual_review" in {current.get("status"), old.get("status")}:
            status = "manual_review"
        elif current.get("status") == "complete_zero" and old.get("status") == "complete_zero":
            status = "complete_zero"
        else:
            status = "partial"
        regulatory_status[cid] = {
            "status": status, "attempted_at": current.get("attempted_at") or old.get("attempted_at"),
            "source_url": current.get("source_url") or old.get("source_url", ""),
            "raw_count": int(current.get("raw_count") or 0), "accepted_count": regulatory_counts.get(cid, 0),
            "notes": current.get("notes") or old.get("notes", ""),
        }
    regulatory_companies = nested_company_rows(canonical, "regulatory", regulatory_status)

    main_product = ROOT / "canada_full_universe_refresh_2026-08-04/product_news"
    supplement = ROOT / "canada_full_universe_refresh_2026-08-04/product_news_website_supplement"
    products = dedupe(load(main_product / "product_profiles.json", "profiles") + load(supplement / "product_profiles.json", "profiles"), ("evidence_id", "evidence_url"))
    events = dedupe(
        load(main_product / "product_news_events.json", "events")
        + load(supplement / "product_news_events.json", "events")
        + load(ROOT / "canada_full_universe_refresh_2026-08-04/product_news_luna_verification/verified_events.json", "events"),
        ("evidence_id",),
    )
    completeness_by_id = {row["company_id"]: row for row in load(main_product / "product_news_completeness.json", "companies")}
    completeness_by_id.update({row["company_id"]: row for row in load(supplement / "product_news_completeness.json", "companies")})
    decisions = load(ROOT / "canada_full_universe_refresh_2026-08-04/product_news_luna_verification/candidate_decisions.json", "decisions")
    accepted_counts: dict[str, int] = {}
    unresolved_counts: dict[str, int] = {}
    for event in events:
        accepted_counts[event["company_id"]] = accepted_counts.get(event["company_id"], 0) + 1
    for decision in decisions:
        if decision.get("verification_status") in {"needs_review", "llm_error"}:
            unresolved_counts[decision["company_id"]] = unresolved_counts.get(decision["company_id"], 0) + 1
    product_completeness = []
    for company in canonical:
        cid = company["company_id"]
        row = json.loads(json.dumps(completeness_by_id.get(cid, {
            "company_id": cid, "company_name": company.get("company_name", ""),
            "product_development": {"status": "not_run"}, "news": {"status": "not_run"},
        })))
        news = row.setdefault("news", {})
        if unresolved_counts.get(cid):
            news["status"] = "manual_review"
        elif accepted_counts.get(cid):
            news["status"] = "complete_matches"
        elif news.get("status") == "manual_review":
            news["status"] = "partial"
        news["accepted_count"] = accepted_counts.get(cid, 0)
        news["unresolved_count"] = unresolved_counts.get(cid, 0)
        product_completeness.append(row)

    write(out / "canonical_companies.json", "companies", canonical, args.as_of)
    write(out / "source_provenance.json", "records", provenance, args.as_of)
    write(out / "hiring_evidence.json", "records", hiring, args.as_of)
    write(out / "canonical_companies_hiring.json", "companies", hiring_companies, args.as_of)
    write(out / "funding_events.json", "events", funding_events, args.as_of)
    write(out / "funding_backing_evidence.json", "records", backing, args.as_of)
    write(out / "canonical_companies_funding.json", "companies", funding_companies, args.as_of)
    write(out / "regulatory_evidence.json", "records", regulatory, args.as_of)
    write(out / "canonical_companies_regulatory.json", "companies", regulatory_companies, args.as_of)
    write(out / "product_profiles.json", "profiles", products, args.as_of)
    write(out / "product_news_events.json", "events", events, args.as_of)
    write(out / "product_news_completeness.json", "companies", product_completeness, args.as_of)
    write(out / "news_candidate_decisions.json", "decisions", decisions, args.as_of)

    outputs = sorted(path for path in out.glob("*.json"))
    manifest = {
        "schema_version": "2.0", "generated_at": args.as_of,
        "counts": {
            "companies": len(canonical), "companies_with_websites": sum(bool(row.get("website")) for row in canonical),
            "hiring_evidence": len(hiring), "funding_events": len(funding_events), "backing_records": len(backing),
            "regulatory_evidence": len(regulatory), "product_profiles": len(products), "product_news_events": len(events),
            "news_decisions": len(decisions),
        },
        "files": [{
            "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size,
        } for path in outputs],
    }
    (out / "release_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest["counts"]))


if __name__ == "__main__":
    main()
