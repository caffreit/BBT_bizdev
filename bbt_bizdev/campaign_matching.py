from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .subscriber_enrichment import (
    COMPANY_TYPES,
    CONTACT_FUNCTIONS,
    EMPLOYEE_BANDS,
    MATURITY_STAGES,
    MODEL,
    OPENROUTER_URL,
    PRODUCT_PROFILES,
    REASONING_EFFORT,
    REGULATORY_SIGNALS,
    SERVICE_FITS,
    USER_AGENT,
    email_domain,
    normalize_email,
)


SENIORITIES = ["Executive", "Director/VP", "Manager/lead", "Individual contributor", "Unknown"]
BUYING_ROLES = [
    "Economic buyer / sponsor",
    "Technical buyer / influencer",
    "Technical buyer / delivery owner",
    "Clinical influencer",
    "Operational buyer / influencer",
    "Commercial influencer",
    "Low-priority contact",
    "Spinout / research influencer",
    "Role requires review",
    "Unknown role",
]
COMPANY_WEIGHTS = {
    "product_profiles": 25,
    "services": 20,
    "regulatory_signals": 15,
    "maturity_stages": 15,
    "company_types": 10,
    "employee_bands": 10,
    "evidence": 5,
}
CONTACT_WEIGHTS = {"function": 40, "seniority": 25, "buying_role": 15, "title": 15, "data_quality": 5}
GENERIC_PREFIXES = {"admin", "contact", "hello", "info", "office", "sales", "support", "team", "enquiries", "inquiries"}
PROFILE_VERSION = "campaign_profile_v1"


def _target_schema(enum: list[str]) -> dict[str, Any]:
    item = {"type": "string", "enum": enum}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "required": {"type": "array", "items": item, "uniqueItems": True},
            "preferred": {"type": "array", "items": item, "uniqueItems": True},
            "excluded": {"type": "array", "items": item, "uniqueItems": True},
        },
        "required": ["required", "preferred", "excluded"],
    }


def campaign_profile_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "campaign_name": {"type": "string"},
            "subject": {"type": "string"},
            "theme": {"type": "string"},
            "primary_service": {"type": "string", "enum": SERVICE_FITS},
            "company_targets": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "company_types": _target_schema(COMPANY_TYPES),
                    "employee_bands": _target_schema(EMPLOYEE_BANDS),
                    "maturity_stages": _target_schema(MATURITY_STAGES),
                    "product_profiles": _target_schema(PRODUCT_PROFILES),
                    "services": _target_schema(SERVICE_FITS),
                    "regulatory_signals": _target_schema(REGULATORY_SIGNALS),
                },
                "required": ["company_types", "employee_bands", "maturity_stages", "product_profiles", "services", "regulatory_signals"],
            },
            "contact_targets": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "primary_functions": {"type": "array", "items": {"type": "string", "enum": CONTACT_FUNCTIONS}, "uniqueItems": True},
                    "secondary_functions": {"type": "array", "items": {"type": "string", "enum": CONTACT_FUNCTIONS}, "uniqueItems": True},
                    "excluded_functions": {"type": "array", "items": {"type": "string", "enum": CONTACT_FUNCTIONS}, "uniqueItems": True},
                    "preferred_seniorities": {"type": "array", "items": {"type": "string", "enum": SENIORITIES}, "uniqueItems": True},
                    "preferred_buying_roles": {"type": "array", "items": {"type": "string", "enum": BUYING_ROLES}, "uniqueItems": True},
                    "title_keywords": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
                    "excluded_title_keywords": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
                    "business_unit_keywords": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
                    "require_business_unit_match": {"type": "boolean"},
                },
                "required": ["primary_functions", "secondary_functions", "excluded_functions", "preferred_seniorities", "preferred_buying_roles", "title_keywords", "excluded_title_keywords", "business_unit_keywords", "require_business_unit_match"],
            },
            "company_score_threshold": {"type": "integer", "minimum": 0, "maximum": 100},
            "contact_score_threshold": {"type": "integer", "minimum": 0, "maximum": 100},
            "minimum_classification_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "rationale": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["campaign_name", "subject", "theme", "primary_service", "company_targets", "contact_targets", "company_score_threshold", "contact_score_threshold", "minimum_classification_confidence", "rationale", "confidence"],
    }


def _enum_values(schema: dict[str, Any], path: tuple[str, ...]) -> set[str]:
    node: Any = schema
    for key in path:
        node = node[key]
    return set(node)


def validate_profile(profile: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(profile, dict):
        raise ValueError("Campaign profile must be a JSON object")
    required_top = set(campaign_profile_schema()["required"])
    missing = sorted(required_top - set(profile))
    if missing:
        raise ValueError("Missing profile fields: " + ", ".join(missing))
    allowed_dimensions = {
        "company_types": set(COMPANY_TYPES),
        "employee_bands": set(EMPLOYEE_BANDS),
        "maturity_stages": set(MATURITY_STAGES),
        "product_profiles": set(PRODUCT_PROFILES),
        "services": set(SERVICE_FITS),
        "regulatory_signals": set(REGULATORY_SIGNALS),
    }
    company_targets = profile.get("company_targets")
    if not isinstance(company_targets, dict) or set(company_targets) != set(allowed_dimensions):
        raise ValueError("company_targets must contain exactly the six controlled dimensions")
    for dimension, enum in allowed_dimensions.items():
        target = company_targets[dimension]
        if not isinstance(target, dict) or set(target) != {"required", "preferred", "excluded"}:
            raise ValueError(f"Invalid target structure for {dimension}")
        sets: list[set[str]] = []
        for bucket in ("required", "preferred", "excluded"):
            values = target[bucket]
            if not isinstance(values, list) or any(value not in enum for value in values):
                raise ValueError(f"Invalid {dimension}.{bucket} value")
            sets.append(set(values))
        if (sets[0] & sets[2]) or (sets[1] & sets[2]):
            raise ValueError(f"Excluded {dimension} values cannot also be required or preferred")
    contacts = profile.get("contact_targets")
    required_contact = {"primary_functions", "secondary_functions", "excluded_functions", "preferred_seniorities", "preferred_buying_roles", "title_keywords", "excluded_title_keywords", "business_unit_keywords", "require_business_unit_match"}
    if not isinstance(contacts, dict) or set(contacts) != required_contact:
        raise ValueError("Invalid contact_targets structure")
    for key, enum in (("primary_functions", CONTACT_FUNCTIONS), ("secondary_functions", CONTACT_FUNCTIONS), ("excluded_functions", CONTACT_FUNCTIONS), ("preferred_seniorities", SENIORITIES), ("preferred_buying_roles", BUYING_ROLES)):
        if not isinstance(contacts[key], list) or any(value not in enum for value in contacts[key]):
            raise ValueError(f"Invalid contact target: {key}")
    if (set(contacts["primary_functions"]) | set(contacts["secondary_functions"])) & set(contacts["excluded_functions"]):
        raise ValueError("A contact function cannot be both targeted and excluded")
    for key in ("title_keywords", "excluded_title_keywords", "business_unit_keywords"):
        if not isinstance(contacts[key], list) or any(not isinstance(value, str) or not value.strip() for value in contacts[key]):
            raise ValueError(f"Invalid keyword list: {key}")
    if not isinstance(contacts["require_business_unit_match"], bool):
        raise ValueError("require_business_unit_match must be boolean")
    if profile["primary_service"] not in SERVICE_FITS:
        raise ValueError("Invalid primary_service")
    for key, default in (("company_score_threshold", 60), ("contact_score_threshold", 65)):
        value = profile.get(key, default)
        if not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError(f"{key} must be an integer from 0 to 100")
    for key in ("minimum_classification_confidence", "confidence"):
        value = profile.get(key)
        if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
            raise ValueError(f"{key} must be from 0 to 1")
    return profile


def _extract_subject(draft: str) -> str:
    match = re.search(r"(?im)^\s*subject\s*:\s*(.+)$", draft)
    return match.group(1).strip() if match else ""


def profile_request_payload(draft: str, model: str, reasoning_effort: str) -> dict[str, Any]:
    prompt = (
        "Convert this Bluebridge outreach email into a conservative targeting profile. "
        "The profile will be reviewed before use. Use only the controlled enum values. "
        "Required means the company must have evidence for at least one listed value; prefer preferred values for scoring; use excluded only for a clear mismatch. "
        "Use balanced defaults: company_score_threshold 60, contact_score_threshold 65, minimum_classification_confidence 0.55. "
        "Do not invent recipient, company, or campaign facts. This input contains the email draft only.\n\n"
        f"EMAIL DRAFT\n{draft}"
    )
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "reasoning": {"effort": reasoning_effort, "exclude": True},
        "response_format": {"type": "json_schema", "json_schema": {"name": "campaign_targeting_profile", "strict": True, "schema": campaign_profile_schema()}},
        "provider": {"require_parameters": True},
    }


def create_profile(draft: str, api_key: str, model: str = MODEL, reasoning_effort: str = REASONING_EFFORT) -> dict[str, Any]:
    if not draft.strip():
        raise ValueError("Email draft is empty")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY or BBT_OPENROUTER_API_KEY is not configured")
    payload = profile_request_payload(draft, model, reasoning_effort)
    request = Request(OPENROUTER_URL, data=json.dumps(payload).encode("utf-8"), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "User-Agent": USER_AGENT})
    try:
        raw = json.loads(urlopen(request, timeout=90).read().decode("utf-8", "ignore"))
        result = json.loads(raw["choices"][0]["message"]["content"])
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:500]
        raise RuntimeError(f"OpenRouter HTTP {exc.code}: {detail or exc.reason}") from exc
    except Exception as exc:
        raise RuntimeError(f"OpenRouter profile extraction failed: {str(exc)[:300]}") from exc
    validate_profile(result)
    if float(result["confidence"]) < 0.60:
        raise ValueError("Campaign profile confidence is below 0.60; edit or classify the draft manually")
    result["metadata"] = {
        "profile_version": PROFILE_VERSION,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "draft_sha256": hashlib.sha256(draft.encode("utf-8")).hexdigest(),
        "draft_subject_detected": _extract_subject(draft),
        "usage": raw.get("usage", {}),
    }
    return result


def _split(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(";") if item.strip()]


def _text_hit(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(keyword.strip().lower() in lower for keyword in keywords if keyword.strip())


def _dimension_score(value: Any, target: dict[str, list[str]], weight: int, label: str) -> tuple[int, list[str], list[str], list[str]]:
    actual = set(_split(value))
    required, preferred, excluded = (set(target[key]) for key in ("required", "preferred", "excluded"))
    matched: list[str] = []
    exclusions: list[str] = []
    review: list[str] = []
    if actual & excluded:
        exclusions.append(f"Excluded {label}: {', '.join(sorted(actual & excluded))}")
    if required and not actual.intersection(required):
        review.append(f"Required {label} not evidenced")
    desired = required | preferred
    if not desired:
        return weight, matched, exclusions, review
    overlap = actual & desired
    if overlap:
        matched.append(f"{label}: {', '.join(sorted(overlap))}")
        return weight, matched, exclusions, review
    return 0, matched, exclusions, review


def score_company(company: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    mappings = {
        "product_profiles": (company.get("product_profile"), "product profile"),
        "services": (company.get("services"), "service"),
        "regulatory_signals": (company.get("regulatory_signals"), "regulatory signal"),
        "maturity_stages": (company.get("maturity_stage"), "maturity"),
        "company_types": (company.get("company_type"), "company type"),
        "employee_bands": (company.get("employee_band"), "employee band"),
    }
    score = 0
    matched: list[str] = []
    exclusions: list[str] = []
    review: list[str] = []
    substantive = False
    targets = profile["company_targets"]
    for dimension, (value, label) in mappings.items():
        points, hits, fails, needs_review = _dimension_score(value, targets[dimension], COMPANY_WEIGHTS[dimension], label)
        score += points
        matched.extend(hits)
        exclusions.extend(fails)
        review.extend(needs_review)
        if dimension in {"product_profiles", "services", "regulatory_signals", "maturity_stages"} and hits:
            substantive = True
    confidence = float(company.get("confidence") or 0)
    research_date = str(company.get("research_date") or "")
    fresh = False
    try:
        fresh = (date.today() - date.fromisoformat(research_date)).days <= 548
    except ValueError:
        pass
    if confidence >= float(profile["minimum_classification_confidence"]) and fresh and _split(company.get("source_urls") or company.get("evidence_urls")):
        score += COMPANY_WEIGHTS["evidence"]
        matched.append("evidence quality/freshness")
    else:
        review.append("Classification confidence, source evidence, or research freshness is insufficient")
    if not substantive:
        review.append("No substantive product, service, regulatory, or maturity match")
    company_id = str(company.get("company_id") or "")
    domain = str(company.get("domain") or "").lower()
    if not company_id or not domain or float(company.get("resolution_confidence") or 0) <= 0:
        exclusions.append("Company identity is unresolved")
    eligible = not exclusions and not review and score >= int(profile["company_score_threshold"])
    status = "Eligible" if eligible else ("Excluded" if exclusions else "Review")
    return {
        "Company ID": company_id,
        "Company": company.get("canonical_company", ""),
        "Domain": domain,
        "Company Type": company.get("company_type", "Unknown"),
        "Employee Band": company.get("employee_band", "Unknown"),
        "Maturity Stage": company.get("maturity_stage", "Unknown"),
        "Product Profile": company.get("product_profile", "Unknown"),
        "Recommended Services": company.get("services", ""),
        "Regulatory Signals": company.get("regulatory_signals", ""),
        "Classification Confidence": confidence,
        "Company Score": score,
        "Decision": status,
        "Matched Criteria": "; ".join(matched),
        "Exclusion Reasons": "; ".join(exclusions),
        "Review Reasons": "; ".join(review),
        "Evidence Summary": company.get("evidence_summary", ""),
        "Evidence URLs": company.get("evidence_urls") or company.get("source_urls", ""),
        "Research Date": research_date,
    }


def _is_generic(email: str) -> bool:
    local = email.split("@", 1)[0].lower() if "@" in email else ""
    return local in GENERIC_PREFIXES or any(local.startswith(prefix + ".") for prefix in GENERIC_PREFIXES)


def score_contact(contact: dict[str, Any], company_decision: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    target = profile["contact_targets"]
    function = str(contact.get("Contact Function") or "Other")
    seniority = str(contact.get("Seniority") or "Unknown")
    buying_role = str(contact.get("Buying Role") or "Unknown role")
    title = str(contact.get("Job Title") or "").strip()
    email = normalize_email(contact.get("Email"))
    matched: list[str] = []
    exclusions: list[str] = []
    review: list[str] = []
    warnings: list[str] = []
    score = 0
    if function in target["excluded_functions"]:
        exclusions.append(f"Excluded contact function: {function}")
    if function in target["primary_functions"]:
        score += CONTACT_WEIGHTS["function"]
        matched.append(f"primary function: {function}")
    elif function in target["secondary_functions"]:
        score += 28
        matched.append(f"secondary function: {function}")
    if not target["preferred_seniorities"]:
        score += CONTACT_WEIGHTS["seniority"]
    elif seniority in target["preferred_seniorities"]:
        score += CONTACT_WEIGHTS["seniority"]
        matched.append(f"seniority: {seniority}")
    if not target["preferred_buying_roles"]:
        score += CONTACT_WEIGHTS["buying_role"]
    elif buying_role in target["preferred_buying_roles"]:
        score += CONTACT_WEIGHTS["buying_role"]
        matched.append(f"buying role: {buying_role}")
    if target["excluded_title_keywords"] and _text_hit(title, target["excluded_title_keywords"]):
        exclusions.append("Excluded title keyword")
    if not target["title_keywords"]:
        score += CONTACT_WEIGHTS["title"]
    elif _text_hit(title, target["title_keywords"]):
        score += CONTACT_WEIGHTS["title"]
        matched.append("title keyword")
    if target["business_unit_keywords"]:
        if _text_hit(title, target["business_unit_keywords"]):
            matched.append("business-unit keyword")
        elif target["require_business_unit_match"]:
            review.append("Required business-unit match is missing")
        elif company_decision.get("Company Type") == "Enterprise":
            warnings.append("Enterprise business unit not established")
    domain = email_domain(email)
    duplicate = str(contact.get("Duplicate Email") or "").lower() == "yes"
    if domain and not duplicate and not _is_generic(email):
        score += CONTACT_WEIGHTS["data_quality"]
    else:
        review.append("Invalid, duplicate, or generic email")
    if not title or function == "Other" or seniority == "Unknown":
        review.append("Missing or unclassifiable job title")
    if company_decision["Decision"] != "Eligible":
        review.append(f"Company decision is {company_decision['Decision']}")
    eligible = not exclusions and not review and company_decision["Decision"] == "Eligible" and score >= int(profile["contact_score_threshold"])
    status = "Eligible" if eligible else ("Excluded" if exclusions else "Review")
    angle = contact.get("Outreach Angle") or f"Discuss {profile['primary_service'].lower()} in relation to {profile['theme']}"
    return {
        "Record ID": contact.get("Record ID", ""),
        "Company ID": contact.get("Company ID", ""),
        "Company": contact.get("Resolved Company") or company_decision.get("Company", ""),
        "First Name": contact.get("First Name", ""),
        "Last Name": contact.get("Last Name", ""),
        "Email": email,
        "Job Title": title,
        "Contact Function": function,
        "Seniority": seniority,
        "Buying Role": buying_role,
        "Contact Score": score,
        "Decision": status,
        "Matched Criteria": "; ".join(matched),
        "Exclusion Reasons": "; ".join(exclusions),
        "Review Reasons": "; ".join(review),
        "Warnings": "; ".join(warnings),
        "Company Score": company_decision["Company Score"],
        "Company Decision": company_decision["Decision"],
        "Contact Rank": "",
        "Selection": "",
        "Approval Status": "Pending",
        "Suppression Status": "Not checked",
        "Personalisation Angle": angle,
        "Personalisation Evidence URL": str(company_decision.get("Evidence URLs", "")).split(";")[0].strip(),
    }


def load_suppressions(path: Path | None) -> tuple[set[str], set[str]]:
    emails: set[str] = set()
    domains: set[str] = set()
    if path is None:
        return emails, domains
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            lowered = {str(key).strip().lower(): value for key, value in row.items() if key is not None}
            email = normalize_email(lowered.get("email") or lowered.get("email address"))
            domain = str(lowered.get("domain") or "").strip().lower().removeprefix("@")
            if email_domain(email):
                emails.add(email)
            if re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain):
                domains.add(domain)
    return emails, domains


def apply_suppression(rows: list[dict[str, Any]], emails: set[str], domains: set[str], clear_status: str) -> None:
    for row in rows:
        email = normalize_email(row.get("Email"))
        domain = email_domain(email)
        if email in emails:
            row["Suppression Status"] = "Suppressed email"
            row["Decision"] = "Excluded"
            row["Exclusion Reasons"] = "; ".join(filter(None, [row.get("Exclusion Reasons", ""), "Suppressed email"]))
        elif domain in domains:
            row["Suppression Status"] = "Suppressed domain"
            row["Decision"] = "Excluded"
            row["Exclusion Reasons"] = "; ".join(filter(None, [row.get("Exclusion Reasons", ""), "Suppressed domain"]))
        else:
            row["Suppression Status"] = clear_status


def match_campaign(enrichment: dict[str, Any], profile: dict[str, Any], suppression_path: Path | None = None, waive_suppression: bool = False) -> dict[str, Any]:
    validate_profile(profile)
    companies = enrichment.get("companies")
    contacts = enrichment.get("contacts")
    if not isinstance(companies, list) or not isinstance(contacts, list):
        raise ValueError("Enrichment JSON must contain companies and contacts arrays")
    if suppression_path is None and not waive_suppression:
        suppression_checked = False
    else:
        suppression_checked = suppression_path is not None
    company_rows = [score_company(company, profile) for company in companies]
    company_by_id = {row["Company ID"]: row for row in company_rows}
    contact_rows = [score_contact(contact, company_by_id.get(str(contact.get("Company ID")), {"Company ID": contact.get("Company ID", ""), "Company": contact.get("Resolved Company", ""), "Company Type": "Unknown", "Company Score": 0, "Decision": "Review", "Evidence URLs": ""}), profile) for contact in contacts]
    suppression_emails, suppression_domains = load_suppressions(suppression_path)
    clear_status = "Clear" if suppression_checked else ("Waived" if waive_suppression else "Not checked")
    apply_suppression(contact_rows, suppression_emails, suppression_domains, clear_status)
    by_company: dict[str, list[dict[str, Any]]] = {}
    for row in contact_rows:
        if row["Decision"] == "Eligible":
            by_company.setdefault(str(row["Company ID"]), []).append(row)
    seniority_order = {"Executive": 0, "Director/VP": 1, "Manager/lead": 2, "Individual contributor": 3, "Unknown": 4}
    for rows in by_company.values():
        rows.sort(key=lambda row: (-int(row["Contact Score"]), seniority_order.get(str(row["Seniority"]), 9), str(row["Record ID"])))
        for rank, row in enumerate(rows, 1):
            row["Contact Rank"] = rank
            if rank == 1:
                row["Selection"] = "Primary"
            elif rank == 2:
                row["Selection"] = "Backup"
            else:
                row["Selection"] = "Not retained"
                row["Decision"] = "Review"
                row["Review Reasons"] = "; ".join(filter(None, [row.get("Review Reasons", ""), "Below per-company primary/backup cap"]))
    review_rows: list[dict[str, Any]] = []
    for row in company_rows:
        if row["Decision"] != "Eligible":
            review_rows.append({"Level": "Company", "ID": row["Company ID"], "Company": row["Company"], "Contact": "", "Decision": row["Decision"], "Reasons": row["Exclusion Reasons"] or row["Review Reasons"], "Evidence URLs": row["Evidence URLs"]})
    for row in contact_rows:
        if row["Decision"] != "Eligible":
            review_rows.append({"Level": "Contact", "ID": row["Record ID"], "Company": row["Company"], "Contact": row["Email"], "Decision": row["Decision"], "Reasons": row["Exclusion Reasons"] or row["Review Reasons"], "Evidence URLs": row["Personalisation Evidence URL"]})
    summary = {
        "run_date": date.today().isoformat(),
        "campaign_name": profile["campaign_name"],
        "source_companies": len(companies),
        "source_contacts": len(contacts),
        "eligible_companies": sum(row["Decision"] == "Eligible" for row in company_rows),
        "eligible_contacts": sum(row["Decision"] == "Eligible" for row in contact_rows),
        "primary_contacts": sum(row["Selection"] == "Primary" and row["Decision"] == "Eligible" for row in contact_rows),
        "backup_contacts": sum(row["Selection"] == "Backup" and row["Decision"] == "Eligible" for row in contact_rows),
        "review_items": len(review_rows),
        "suppression_checked": "Yes" if suppression_checked else ("Waived" if waive_suppression else "No"),
        "company_threshold": profile["company_score_threshold"],
        "contact_threshold": profile["contact_score_threshold"],
    }
    return {"profile": profile, "summary": summary, "company_decisions": company_rows, "contact_decisions": contact_rows, "review_queue": review_rows}


def _node_command() -> str:
    configured = os.getenv("BBT_NODE", "").strip()
    node = configured or shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required to create or read the review workbook; set BBT_NODE to its executable path")
    return node


def _workbook_script() -> Path:
    return Path(__file__).resolve().parent.parent / "campaign_workbook.mjs"


def build_workbook(result_json: Path, workbook_path: Path, preview_dir: Path | None = None) -> None:
    command = [_node_command(), str(_workbook_script()), "build", str(result_json), str(workbook_path)]
    if preview_dir:
        command.append(str(preview_dir))
    subprocess.run(command, check=True)


def extract_approved(workbook_path: Path) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="bbt-campaign-export-") as temp_dir:
        extracted = Path(temp_dir) / "approved.json"
        subprocess.run([_node_command(), str(_workbook_script()), "extract", str(workbook_path), str(extracted)], check=True)
        return json.loads(extracted.read_text(encoding="utf-8"))


def export_approved(rows: list[dict[str, Any]], output_csv: Path, suppression_path: Path | None, waive_suppression: bool) -> int:
    if suppression_path is None and not waive_suppression:
        raise ValueError("A suppression CSV is required for final export; use --waive-suppression to record an explicit waiver")
    emails, domains = load_suppressions(suppression_path)
    seen: set[str] = set()
    exported: list[dict[str, Any]] = []
    for row in rows:
        email = normalize_email(row.get("Email"))
        if str(row.get("Approval Status", "")).strip().lower() != "approved" or str(row.get("Selection", "")) != "Primary":
            continue
        domain = email_domain(email)
        if not domain or email in emails or domain in domains or email in seen or _is_generic(email):
            continue
        seen.add(email)
        exported.append({
            "Campaign": row.get("Campaign", ""), "Record ID": row.get("Record ID", ""), "Company ID": row.get("Company ID", ""),
            "Company": row.get("Company", ""), "First Name": row.get("First Name", ""), "Last Name": row.get("Last Name", ""),
            "Email": email, "Job Title": row.get("Job Title", ""), "Personalisation Angle": row.get("Personalisation Angle", ""),
            "Personalisation Evidence URL": row.get("Personalisation Evidence URL", ""),
        })
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = ["Campaign", "Record ID", "Company ID", "Company", "First Name", "Last Name", "Email", "Job Title", "Personalisation Angle", "Personalisation Evidence URL"]
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(exported)
    return len(exported)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create targeting profiles and select Bluebridge campaign contacts")
    subparsers = parser.add_subparsers(dest="command", required=True)
    profile_parser = subparsers.add_parser("profile", help="Extract a controlled campaign profile from one email draft")
    profile_parser.add_argument("--email-draft", type=Path, required=True)
    profile_parser.add_argument("--output-profile", type=Path, required=True)
    profile_parser.add_argument("--model", default=MODEL)
    profile_parser.add_argument("--reasoning-effort", choices=["none", "minimal", "low", "medium", "high", "xhigh", "max"], default=REASONING_EFFORT)
    match_parser = subparsers.add_parser("match", help="Score companies and contacts locally and create a review workbook")
    match_parser.add_argument("--enrichment-json", type=Path, required=True)
    match_parser.add_argument("--campaign-profile", type=Path, required=True)
    match_parser.add_argument("--output-json", type=Path, required=True)
    match_parser.add_argument("--review-workbook", type=Path, required=True)
    match_parser.add_argument("--suppression-csv", type=Path)
    match_parser.add_argument("--waive-suppression", action="store_true")
    match_parser.add_argument("--preview-dir", type=Path)
    export_parser = subparsers.add_parser("export", help="Export approved primary contacts from the review workbook")
    export_parser.add_argument("--review-workbook", type=Path, required=True)
    export_parser.add_argument("--output-csv", type=Path, required=True)
    export_parser.add_argument("--suppression-csv", type=Path)
    export_parser.add_argument("--waive-suppression", action="store_true")
    args = parser.parse_args()
    if args.command == "profile":
        draft = args.email_draft.read_text(encoding="utf-8-sig")
        key = os.getenv("OPENROUTER_API_KEY", "").strip() or os.getenv("BBT_OPENROUTER_API_KEY", "").strip()
        profile = create_profile(draft, key, args.model, args.reasoning_effort)
        args.output_profile.parent.mkdir(parents=True, exist_ok=True)
        args.output_profile.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Created campaign profile: {args.output_profile}")
        return 0
    if args.command == "match":
        enrichment = json.loads(args.enrichment_json.read_text(encoding="utf-8-sig"))
        profile = json.loads(args.campaign_profile.read_text(encoding="utf-8-sig"))
        result = match_campaign(enrichment, profile, args.suppression_csv, args.waive_suppression)
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        build_workbook(args.output_json, args.review_workbook, args.preview_dir)
        print(json.dumps(result["summary"], indent=2))
        return 0
    rows = extract_approved(args.review_workbook)
    count = export_approved(rows, args.output_csv, args.suppression_csv, args.waive_suppression)
    print(f"Exported {count} approved primary contacts to {args.output_csv}")
    return 0
