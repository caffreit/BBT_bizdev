from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from bbt_bizdev.subscriber_enrichment import (
    MODEL,
    REASONING_EFFORT,
    SERVICE_FITS,
    REGULATORY_SIGNALS,
    UNKNOWN,
    _review_row,
    clean,
    contact_angle,
    extract_employee_band,
    openrouter_classify,
    rules_classify,
)


def classify(item: dict, row: dict, api_key: str, model: str, reasoning_effort: str) -> tuple[dict | None, dict, str]:
    url = item.get("final_url") or item.get("requested_url") or row.get("homepage_url")
    text = clean(
        " ".join(
            [
                str(item.get("title", "")),
                str(item.get("description", "")),
                " ".join(item.get("h1") or []),
                " ".join(item.get("sections") or []),
            ]
        )
    )
    evidence = [{"source_type": "Browser-verified first-party homepage", "url": url, "text": text}]
    return openrouter_classify(
        {"company": row["canonical_company"], "domain": row["domain"], "evidence": evidence},
        api_key,
        model,
        reasoning_effort,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-json", type=Path, required=True)
    parser.add_argument("--browser-evidence", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--reasoning-effort", default=REASONING_EFFORT)
    parser.add_argument("--max-workers", type=int, default=12)
    args = parser.parse_args()

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip() or os.getenv("BBT_OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY or BBT_OPENROUTER_API_KEY is required")

    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    evidence = json.loads(args.browser_evidence.read_text(encoding="utf-8"))
    by_id = {row["company_id"]: row for row in payload["companies"]}
    usable = [item for item in evidence if item.get("browser_status") == "Available in browser" and item["company_id"] in by_id]
    completed = 0
    incremental_cost = 0.0

    with ThreadPoolExecutor(max_workers=min(args.max_workers, 12)) as pool:
        futures = {
            pool.submit(classify, item, by_id[item["company_id"]], api_key, args.model, args.reasoning_effort): item
            for item in usable
        }
        for future in as_completed(futures):
            item = futures[future]
            row = by_id[item["company_id"]]
            result, usage, error = future.result()
            if not result:
                row["errors"] = "; ".join(filter(None, [row.get("errors", ""), f"Browser-evidence LLM error: {error}"]))
                continue

            url = item.get("final_url") or item.get("requested_url") or row.get("homepage_url")
            text = clean(" ".join([str(item.get("title", "")), str(item.get("description", "")), " ".join(item.get("h1") or []), " ".join(item.get("sections") or [])]))
            rules = rules_classify(text, row["domain"])
            result["services"] = list(dict.fromkeys(service for service in result.get("services", []) if service in SERVICE_FITS))
            result["regulatory_signals"] = list(dict.fromkeys(signal for signal in result.get("regulatory_signals", []) if signal in REGULATORY_SIGNALS))
            result["evidence_urls"] = [value for value in result.get("evidence_urls", []) if value == url]
            if result.get("employee_band") != UNKNOWN and extract_employee_band(text) == UNKNOWN:
                result["employee_band"] = UNKNOWN
            result["confidence"] = min(float(result.get("confidence", 0)), 0.60 if row["website_status"] == "External redirect" else 0.75)
            rules.update(result)

            for field in ("company_type", "employee_band", "product_profile", "maturity_stage", "confidence"):
                row[field] = rules[field]
            row["services"] = "; ".join(rules.get("services", []))
            row["regulatory_signals"] = "; ".join(rules.get("regulatory_signals", []))
            row["evidence_summary"] = clean(result.get("evidence_summary"))
            row["evidence_urls"] = "; ".join(result.get("evidence_urls", []))
            row["source_urls"] = "; ".join(dict.fromkeys([url, *[value.strip() for value in str(row.get("source_urls", "")).split(";") if value.strip()]]))
            row["research_date"] = date.today().isoformat()
            row["method"] = "OpenRouter structured extraction from browser-verified first-party evidence"
            row["llm_used"] = "Yes"
            row["model"] = args.model
            row["reasoning_effort"] = args.reasoning_effort
            row["prompt_tokens"] = int(usage.get("prompt_tokens", 0) or 0)
            row["completion_tokens"] = int(usage.get("completion_tokens", 0) or 0)
            cost = float(usage.get("cost") or ((row["prompt_tokens"] * 1.00 + row["completion_tokens"] * 6.00) / 1_000_000)) if args.model == MODEL else 0.0
            row["estimated_cost_usd"] = round(cost, 6)
            row["llm_error"] = ""
            row["errors"] = "; ".join(
                part.strip()
                for part in str(row.get("errors", "")).split(";")
                if part.strip() and part.strip() != "Selective re-enrichment fetch did not reproduce recovery"
            )
            completed += 1
            incremental_cost += cost

    for contact in payload["contacts"]:
        company = by_id.get(contact["Company ID"])
        if not company:
            continue
        primary, angle, segment = contact_angle(contact["Contact Function"], company["services"], company["maturity_stage"])
        contact["Primary Service Relevance"] = primary
        contact["Outreach Angle"] = angle
        contact["Campaign Segment"] = segment

    prior_review = {row["Company ID"]: row for row in payload.get("review_queue", [])}
    payload["review_queue"] = [_review_row(row, prior_review.get(row["company_id"])) for row in payload["companies"]]
    payload["stats"].update(
        {
            "run_date": date.today().isoformat(),
            "selectively_reenriched": int(payload["stats"].get("selectively_reenriched", 0)) + completed,
            "selective_llm_cost_usd": round(float(payload["stats"].get("selective_llm_cost_usd", 0)) + incremental_cost, 6),
            "llm_used_companies": sum(row.get("llm_used") == "Yes" for row in payload["companies"]),
            "estimated_cost_usd": round(sum(float(row.get("estimated_cost_usd", 0)) for row in payload["companies"]), 6),
            "unknown_company_type": sum(row["company_type"] == UNKNOWN for row in payload["companies"]),
            "unknown_employee_band": sum(row["employee_band"] == UNKNOWN for row in payload["companies"]),
            "unknown_product_profile": sum(row["product_profile"] == UNKNOWN for row in payload["companies"]),
            "unknown_maturity": sum(row["maturity_stage"] == UNKNOWN for row in payload["companies"]),
            "browser_evidence_llm_completed": completed,
        }
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload["stats"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
