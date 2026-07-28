from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit


SCHEMA_VERSION = "1.0"
TRACKS = ("hiring", "funding", "regulatory", "product_development", "news")
PROVINCES = {
    "ab": "Alberta", "alberta": "Alberta",
    "bc": "British Columbia", "british columbia": "British Columbia",
    "mb": "Manitoba", "manitoba": "Manitoba",
    "nb": "New Brunswick", "new brunswick": "New Brunswick",
    "nl": "Newfoundland and Labrador", "newfoundland": "Newfoundland and Labrador",
    "ns": "Nova Scotia", "nova scotia": "Nova Scotia",
    "nt": "Northwest Territories", "northwest territories": "Northwest Territories",
    "nu": "Nunavut", "nunavut": "Nunavut",
    "on": "Ontario", "ontario": "Ontario",
    "pe": "Prince Edward Island", "pei": "Prince Edward Island",
    "prince edward island": "Prince Edward Island",
    "qc": "Quebec", "quebec": "Quebec", "québec": "Quebec",
    "sk": "Saskatchewan", "saskatchewan": "Saskatchewan",
    "yt": "Yukon", "yukon": "Yukon",
}
LEGAL_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "ltd", "limited", "ulc", "lp",
    "llp", "llc", "co", "company", "societe", "société", "sarl", "sa",
}
NON_COMPANY_HOSTS = {
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "vessel.co",
}
INSTITUTIONAL_HOST_SUFFIXES = (
    ".utoronto.ca", ".ualberta.ca", ".ubc.ca", ".ucalgary.ca",
)


@dataclass
class SourceRecord:
    index: int
    snapshot_file: str
    snapshot_date: str
    source_name: str
    source_type: str
    source_url: str
    company_name: str
    normalized_name: str
    match_name: str
    website: str
    domain: str
    evidence_url: str
    geography: str
    description: str
    product_type: str
    raw_record: dict[str, Any]

    @property
    def record_key(self) -> str:
        value = "|".join(
            (normalize_name(self.source_name), self.normalized_name, self.evidence_url)
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def clean(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("rendered") or value.get("title") or value.get("url") or ""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", clean(value).casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    words = re.findall(r"[a-z0-9]+", value)
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def normalize_domain(value: str) -> str:
    value = clean(value)
    if not value:
        return ""
    if "://" not in value:
        value = "https://" + value
    try:
        host = (urlsplit(value).hostname or "").casefold().rstrip(".")
        if host.startswith("www."):
            host = host[4:]
        host = host.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return ""
    if not host or "." not in host or any(
        host == blocked or host.endswith("." + blocked) for blocked in NON_COMPANY_HOSTS
    ):
        return ""
    return host


def canonical_website(value: str) -> str:
    domain = normalize_domain(value)
    if not domain:
        return ""
    scheme = "http" if clean(value).casefold().startswith("http://") else "https"
    return urlunsplit((scheme, domain, "", "", ""))


def stable_id(value: str) -> str:
    return "ca-company-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def snapshot_date(payload: dict[str, Any], path: Path) -> str:
    value = clean(payload.get("snapshot_date") or payload.get("collected_at"))
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    match = re.search(r"(\d{4}-\d{2}-\d{2})(?=\.json$)", path.name)
    return match.group(1) if match else ""


def source_metadata(payload: dict[str, Any], path: Path) -> tuple[str, str, str]:
    source = payload.get("source")
    if isinstance(source, dict):
        name = clean(source.get("name"))
        source_type = clean(source.get("source_type"))
        url = clean(source.get("url"))
    else:
        name, source_type, url = clean(payload.get("source_name") or source), "", ""
    name = name or path.stem.rsplit("_", 1)[0].replace("_", " ")
    urls = payload.get("source_urls")
    url = (
        url
        or clean(payload.get("source_url"))
        or (clean(urls[0]) if isinstance(urls, list) and urls else "")
    )
    return name, source_type, url


def _record_name(row: dict[str, Any]) -> str:
    return clean(row.get("company") or row.get("company_name") or row.get("name") or row.get("title"))


def _record_website(row: dict[str, Any]) -> str:
    candidate = clean(row.get("website"))
    acf = row.get("acf")
    if not candidate and isinstance(acf, dict):
        website = acf.get("startups_website_en") or acf.get("startups_website")
        candidate = clean(website.get("url") if isinstance(website, dict) else website)
    return candidate


def _is_profile_or_login_url(value: str) -> bool:
    try:
        parts = urlsplit(value if "://" in value else "https://" + value)
    except ValueError:
        return True
    host = (parts.hostname or "").casefold()
    path = parts.path.casefold().rstrip("/")
    return (
        path.endswith("/login")
        or any(host.endswith(suffix) for suffix in INSTITUTIONAL_HOST_SUFFIXES)
    )


def _record_evidence_url(row: dict[str, Any], source_url: str) -> str:
    for key in ("discovery_url", "detail_url", "profile_url", "portfolio_url", "link"):
        value = clean(row.get(key))
        if value.startswith(("http://", "https://")):
            return value
    return source_url


def _record_description(row: dict[str, Any]) -> str:
    acf = row.get("acf")
    nested = ""
    if isinstance(acf, dict):
        nested = clean(acf.get("startups_description_en") or acf.get("startups_description"))
    return clean(row.get("company_description") or row.get("description") or nested)


def _record_geography(row: dict[str, Any]) -> str:
    locations = row.get("directory_locations")
    if isinstance(locations, list):
        locations = "; ".join(clean(value) for value in locations)
    return clean(row.get("geography") or row.get("location") or locations)


def _record_product_type(row: dict[str, Any]) -> str:
    categories = row.get("categories")
    if isinstance(categories, list) and all(isinstance(value, str) for value in categories):
        categories = "; ".join(categories)
    return clean(
        row.get("product_type")
        or row.get("line_of_business")
        or row.get("category_or_track")
        or row.get("stream")
        or categories
    )


def load_source_records(
    paths: Iterable[Path], aliases: dict[str, str] | None = None
) -> tuple[list[SourceRecord], list[dict[str, str]]]:
    aliases = {normalize_name(k): normalize_name(v) for k, v in (aliases or {}).items()}
    records: list[SourceRecord] = []
    rejected: list[dict[str, str]] = []
    for path in sorted(paths):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            rejected.append({"snapshot_file": str(path), "reason": f"invalid_snapshot: {exc}"})
            continue
        if not isinstance(payload, dict):
            rejected.append({"snapshot_file": str(path), "reason": "top_level_not_object"})
            continue
        rows = payload.get("records") or payload.get("hits") or []
        if not isinstance(rows, list):
            rejected.append({"snapshot_file": str(path), "reason": "records_not_array"})
            continue
        snap_date = snapshot_date(payload, path)
        source_name, source_type, source_url = source_metadata(payload, path)
        source_domain = normalize_domain(source_url)
        for row_number, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                rejected.append({
                    "snapshot_file": str(path), "reason": f"record_{row_number}_not_object"
                })
                continue
            company = _record_name(row)
            normalized = normalize_name(company)
            if not normalized:
                rejected.append({
                    "snapshot_file": str(path), "reason": f"record_{row_number}_missing_company"
                })
                continue
            evidence_url = _record_evidence_url(row, source_url)
            website_value = _record_website(row)
            domain = normalize_domain(website_value)
            # Portfolio/profile/login URLs are evidence, not an official company website.
            if domain and (
                _is_profile_or_login_url(website_value)
                or any(domain == blocked or domain.endswith("." + blocked) for blocked in NON_COMPANY_HOSTS)
                or domain == source_domain
                or (evidence_url and domain == normalize_domain(evidence_url))
            ):
                website_value, domain = "", ""
            match_name = aliases.get(normalized, normalized)
            records.append(SourceRecord(
                index=len(records),
                snapshot_file=path.name,
                snapshot_date=snap_date,
                source_name=clean(row.get("source_name")) or source_name,
                source_type=clean(row.get("source_type")) or source_type,
                source_url=source_url,
                company_name=company,
                normalized_name=normalized,
                match_name=match_name,
                website=canonical_website(website_value) if domain else "",
                domain=domain,
                evidence_url=evidence_url,
                geography=_record_geography(row),
                description=_record_description(row),
                product_type=_record_product_type(row),
                raw_record=row,
            ))
    return records, rejected


class UnionFind:
    def __init__(self, size: int):
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left, right = self.find(left), self.find(right)
        if left != right:
            self.parent[right] = left


def _preferred(values: Iterable[str]) -> str:
    counts = Counter(value for value in values if value)
    return sorted(counts, key=lambda value: (-counts[value], len(value), value.casefold()))[0] if counts else ""


def _province(geographies: Iterable[str]) -> str:
    for geography in geographies:
        lowered = clean(geography).casefold()
        tokens = re.findall(r"[a-zà-ÿ]+", lowered)
        for width in (3, 2, 1):
            for index in range(len(tokens) - width + 1):
                candidate = " ".join(tokens[index:index + width])
                if candidate in PROVINCES:
                    return PROVINCES[candidate]
    return ""


def _city(geographies: Iterable[str]) -> str:
    for geography in geographies:
        text = clean(geography)
        match = re.match(r"([^,;]+),\s*(?:AB|BC|MB|NB|NL|NS|NT|NU|ON|PEI?|QC|SK|YT)\b", text, re.I)
        if match:
            return match.group(1).strip()
    return ""


def _product_category(values: Iterable[str], descriptions: Iterable[str]) -> str:
    text = " ".join([*values, *descriptions]).casefold()
    rules = [
        ("diagnostics", ("diagnostic", "imaging", "biomarker")),
        ("SaMD", ("samd", "digital health", "healthtech", "software", "artificial intelligence", " ai ")),
        ("medical device", ("medical device", "medtech", "prosthe", "surgical")),
        ("therapeutics", ("therapeutic", "biopharma", "pharmaceutical", "drug discovery")),
        ("research tools", ("research tool", "laboratory", "lab equipment")),
        ("biotech platform", ("biotech", "biotechnology", "platform")),
    ]
    return next((category for category, terms in rules if any(term in f" {text} " for term in terms)), "unknown")


def _prior_id_map(previous_payload: dict[str, Any] | None) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = defaultdict(set)
    for company in (previous_payload or {}).get("companies", []):
        company_id = clean(company.get("company_id"))
        for key in company.get("identity_keys", []):
            if company_id and clean(key):
                mapping[clean(key)].add(company_id)
    return mapping


def consolidate(
    records: list[SourceRecord],
    captured_at: str,
    previous_payload: dict[str, Any] | None = None,
    company_id_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    uf = UnionFind(len(records))
    by_name: dict[str, list[SourceRecord]] = defaultdict(list)
    for record in records:
        by_name[record.match_name].append(record)
    ambiguous: list[dict[str, Any]] = []
    for match_name, members in by_name.items():
        domains = sorted({row.domain for row in members if row.domain})
        if len(domains) <= 1:
            for row in members[1:]:
                uf.union(members[0].index, row.index)
        else:
            # Preserve the conflicting-domain split, but still collapse records
            # that agree on the same name and same domain (or all lack a domain).
            buckets: dict[str, list[SourceRecord]] = defaultdict(list)
            for row in members:
                buckets[row.domain].append(row)
            for bucket in buckets.values():
                for row in bucket[1:]:
                    uf.union(bucket[0].index, row.index)
            ambiguous.append({
                "issue_type": "same_name_conflicting_domains",
                "normalized_name": match_name,
                "company_names": sorted({row.company_name for row in members}),
                "domains": domains,
                "source_records": len(members),
                "review_status": "pending",
            })

    by_domain: dict[str, list[SourceRecord]] = defaultdict(list)
    for record in records:
        if record.domain:
            by_domain[record.domain].append(record)
    for domain, members in by_domain.items():
        names = sorted({row.match_name for row in members})
        if len(names) > 1:
            ambiguous.append({
                "issue_type": "shared_domain_different_names",
                "normalized_name": "; ".join(names),
                "company_names": sorted({row.company_name for row in members}),
                "domains": [domain],
                "source_records": len(members),
                "review_status": "pending",
            })
    non_unique_domains = {
        domain for domain, members in by_domain.items()
        if len({row.match_name for row in members}) > 1
    }

    groups: dict[int, list[SourceRecord]] = defaultdict(list)
    for record in records:
        groups[uf.find(record.index)].append(record)
    prior_ids = _prior_id_map(previous_payload)
    overrides = {normalize_name(key): value for key, value in (company_id_overrides or {}).items()}
    companies, provenance, duplicates = [], [], []
    for members in groups.values():
        names = [row.company_name for row in members]
        company_name = _preferred(names)
        domains = sorted({row.domain for row in members if row.domain})
        domain = _preferred(row.domain for row in members)
        website = _preferred(row.website for row in members if row.domain == domain)
        aliases = sorted({name for name in names if name.casefold() != company_name.casefold()}, key=str.casefold)
        identity_keys = sorted({
            *(f"domain:{value}" for value in domains),
            *(f"name:{row.match_name}" for row in members),
            *(f"source:{row.record_key}" for row in members),
        })
        prior = {value for key in identity_keys for value in prior_ids.get(key, set())}
        override = overrides.get(normalize_name(company_name)) or overrides.get(domain)
        if override:
            company_id = override
        elif len(prior) == 1:
            company_id = next(iter(prior))
        else:
            identity_seed = (
                f"domain:{domain}|name:{members[0].match_name}"
                if domain in non_unique_domains
                else (f"domain:{domain}" if domain else f"name:{members[0].match_name}")
            )
            company_id = stable_id(identity_seed)
        geographies = [row.geography for row in members if row.geography]
        descriptions = [row.description for row in members if row.description]
        product_types = [row.product_type for row in members if row.product_type]
        completeness = {
            track: {
                "status": "not_run",
                "attempted_at": None,
                "source_url": "",
                "raw_count": None,
                "accepted_count": None,
                "notes": "",
            }
            for track in TRACKS
        }
        companies.append({
            "company_id": company_id,
            "company_name": company_name,
            "legal_name": "",
            "aliases": aliases,
            "website": website,
            "domain": domain,
            "city": _city(geographies),
            "province": _province(geographies),
            "country": "",
            "canada_relationship": "program location only",
            "employee_band": "unknown",
            "product_category": _product_category(product_types, descriptions),
            "product_summary": _preferred(descriptions),
            "company_stage": "unknown",
            "source_provenance_ids": sorted(row.record_key for row in members),
            "identity_keys": identity_keys,
            "completeness": completeness,
            "last_enriched_at": captured_at,
        })
        if len(members) > 1:
            duplicates.append({
                "company_id": company_id,
                "canonical_company": company_name,
                "aliases": aliases,
                "normalized_name": members[0].match_name,
                "domain": domain,
                "source_records": len(members),
                "sources": sorted({row.source_name for row in members}),
                "resolution": "automatic_exact_normalized_name",
            })
        for row in members:
            provenance.append({
                "provenance_id": row.record_key,
                "company_id": company_id,
                "source_name": row.source_name,
                "source_type": row.source_type,
                "snapshot_file": row.snapshot_file,
                "snapshot_date": row.snapshot_date,
                "source_url": row.source_url,
                "evidence_url": row.evidence_url,
                "source_company_name": row.company_name,
                "source_website": row.website,
                "source_domain": row.domain,
                "geography": row.geography,
                "product_type": row.product_type,
                "description": row.description,
                "captured_at": captured_at,
                "extraction_method": "dated_snapshot_consolidation",
                "raw_record": row.raw_record,
            })

    companies.sort(key=lambda row: (row["company_name"].casefold(), row["company_id"]))
    provenance.sort(key=lambda row: (row["company_id"], row["source_name"], row["provenance_id"]))
    duplicates.sort(key=lambda row: row["canonical_company"].casefold())
    ambiguous.sort(key=lambda row: (row["issue_type"], row["normalized_name"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": captured_at,
        "companies": companies,
        "source_provenance": provenance,
        "duplicate_review": duplicates,
        "ambiguous_name_review": ambiguous,
    }


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(value) for key, value in row.items()})


def write_outputs(
    payload: dict[str, Any],
    output_dir: Path,
    rejected: list[dict[str, str]] | None = None,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "canonical": output_dir / "canonical_companies.json",
        "provenance": output_dir / "source_provenance.json",
        "duplicates": output_dir / "duplicate_review.csv",
        "ambiguous": output_dir / "ambiguous_name_review.csv",
        "rejected": output_dir / "rejected_source_records.csv",
        "summary": output_dir / "run_summary.json",
    }
    canonical = {
        "schema_version": payload["schema_version"],
        "generated_at": payload["generated_at"],
        "companies": payload["companies"],
    }
    files["canonical"].write_text(json.dumps(canonical, ensure_ascii=False, indent=2), encoding="utf-8")
    files["provenance"].write_text(
        json.dumps({
            "schema_version": payload["schema_version"],
            "generated_at": payload["generated_at"],
            "records": payload["source_provenance"],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(files["duplicates"], payload["duplicate_review"], [
        "company_id", "canonical_company", "aliases", "normalized_name", "domain",
        "source_records", "sources", "resolution",
    ])
    write_csv(files["ambiguous"], payload["ambiguous_name_review"], [
        "issue_type", "normalized_name", "company_names", "domains",
        "source_records", "review_status",
    ])
    write_csv(files["rejected"], rejected or [], ["snapshot_file", "reason"])
    summary = {
        "schema_version": payload["schema_version"],
        "generated_at": payload["generated_at"],
        "source_records": len(payload["source_provenance"]),
        "canonical_companies": len(payload["companies"]),
        "automatic_duplicate_groups": len(payload["duplicate_review"]),
        "ambiguous_groups": len(payload["ambiguous_name_review"]),
        "rejected_records": len(rejected or []),
        "companies_with_domains": sum(bool(row["domain"]) for row in payload["companies"]),
        "companies_without_domains": sum(not row["domain"] for row in payload["companies"]),
        "track_initial_state": "not_run",
    }
    files["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return files


def run_consolidation(
    input_dir: Path,
    output_dir: Path,
    run_date: str | None = None,
    previous_path: Path | None = None,
    overrides_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Path]]:
    run_date = run_date or date.today().isoformat()
    overrides: dict[str, Any] = {}
    if overrides_path and overrides_path.exists():
        overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
    previous = None
    if previous_path and previous_path.exists():
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
    paths = list(input_dir.glob("*_????-??-??.json"))
    records, rejected = load_source_records(paths, overrides.get("aliases", {}))
    payload = consolidate(
        records,
        run_date,
        previous_payload=previous,
        company_id_overrides=overrides.get("company_ids", {}),
    )
    return payload, write_outputs(payload, output_dir, rejected)
