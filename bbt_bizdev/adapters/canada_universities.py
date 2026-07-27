from __future__ import annotations

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from ..config import USER_AGENT
from ..http import fetch_raw_text
from ..models import DiscoveryHit, Source, TriggerEvent
from ..text import clean_text, extract_links, source_type_trigger_event, text_from_html
from .canada_tier_a import blocks_by_class
from .university import make_university_spinout_hit


MCGILL_EXPECTED_ALL = 43
MCGILL_EXPECTED_SECTORS = {"BioTech/Medtech": 25, "Pharmaceuticals": 5}

MCMASTER_DIRECTORY_EXPECTED = 52
MCMASTER_HEALTH_SECTORS = {
    "biotechnology": ("Biotechnology", 8),
    "cancer": ("Cancer", 6),
    "cell-technology": ("Cell Technology", 1),
    "diagnostics": ("Diagnostics", 3),
    "digital-health": ("Digital Health", 1),
    "drug-discovery": ("Drug Discovery", 6),
    "health-sciences-filter-1": ("Health Sciences", 2),
    "immuno-oncology": ("Immuno-oncology", 2),
    "medical-devices": ("Medical Devices", 4),
}
MCMASTER_EXPECTED_HEALTH_UNIQUE = 24
MCMASTER_AJAX_URL = "https://entrepreneurship.mcmaster.ca/wp/wp-admin/admin-ajax.php"

AXELYS_ALGOLIA_APP_ID = "3PPTJ4011A"
AXELYS_ALGOLIA_API_KEY = "8864cce44f5180fd131261fd4e66e536"
AXELYS_ALGOLIA_INDEX = "Test_Inteum_TechnologyPublisher_axelys"
AXELYS_EXPECTED_STARTUPS = 5

VELOCITY_EXPECTED_ALL = 548
VELOCITY_EXPECTED_HEALTH = 123
VELOCITY_EXPECTED_PAGES = 7


def _university_trigger(source: Source, hit: DiscoveryHit) -> TriggerEvent | None:
    trigger = source_type_trigger_event(source, hit.company)
    if not trigger:
        return None
    return TriggerEvent(
        hit.company,
        trigger[0],
        trigger[1],
        source.name,
        hit.discovery_url,
    )


def _dedupe_with_triggers(
    source: Source, hits: list[DiscoveryHit]
) -> tuple[list[DiscoveryHit], list[TriggerEvent]]:
    deduped: list[DiscoveryHit] = []
    triggers: list[TriggerEvent] = []
    seen: set[str] = set()
    for hit in hits:
        key = hit.company.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
        trigger = _university_trigger(source, hit)
        if trigger:
            triggers.append(trigger)
    return deduped, triggers


def _field_text(block: str, field: str) -> str:
    match = re.search(
        rf'<[^>]+\bfs-cmsfilter-field=["\']{re.escape(field)}["\'][^>]*>(.*?)</[^>]+>',
        block,
        flags=re.I | re.S,
    )
    return text_from_html(match.group(1)) if match else ""


def parse_mcgill_spinouts(
    source: Source, raw_html: str
) -> tuple[list[DiscoveryHit], dict[str, int], int]:
    counts: dict[str, int] = {}
    hits: list[DiscoveryHit] = []
    all_count = 0
    headings = list(
        re.finditer(r"<h3\b[^>]*>(.*?)</h3>", raw_html, flags=re.I | re.S)
    )
    for index, heading in enumerate(headings):
        section = text_from_html(heading.group(1))
        if section not in {"BioTech/Medtech", "Engineering", "Pharmaceuticals", "Software"}:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(raw_html)
        section_html = raw_html[heading.end() : end]
        counts.setdefault(section, 0)
        for record in re.finditer(
            r"<p\b[^>]*>(.*?)</p>", section_html, flags=re.I | re.S
        ):
            block = record.group(0)
            text = text_from_html(block)
            company_match = re.search(
                r"Company:\s*(.*?)\s*Headquarters:\s*(.*?)(?:\s*Learn more)?$",
                text,
                flags=re.I,
            )
            if not company_match:
                continue
            company = clean_text(company_match.group(1))
            headquarters = clean_text(company_match.group(2))
            all_count += 1
            counts[section] += 1
            if section not in MCGILL_EXPECTED_SECTORS:
                continue
            links = extract_links(block, source.url)
            website = next((href for _, href in links if href.startswith("http")), "")
            hit = make_university_spinout_hit(
                source,
                company,
                source.url,
                f"{section}. Headquarters: {headquarters}.",
                website,
                require_bbt_relevance=False,
                trust_official_name=True,
            )
            if hit:
                hit.geography = headquarters or source.geography
                hit.category_or_track = section
                hit.cohort_label = "McGill IP-registered spinoff companies"
                hit.matched_terms = (
                    f"adapter: mcgill_health_spinouts; official McGill sector: {section}"
                )
                hits.append(hit)
    return hits, counts, all_count


def run_mcgill_health_spinouts(source: Source, fetcher=fetch_raw_text):
    raw_html, error = fetcher(source.url)
    if error:
        return [], [], f"INCOMPLETE {source.name}: fetch failed: {error}"
    hits, counts, all_count = parse_mcgill_spinouts(source, raw_html)
    hits, triggers = _dedupe_with_triggers(source, hits)
    expected_health = sum(MCGILL_EXPECTED_SECTORS.values())
    result = (
        f"{len(hits)}/{expected_health} health-sector spinouts from "
        f"{all_count}/{MCGILL_EXPECTED_ALL} official McGill spinoffs"
    )
    if (
        all_count != MCGILL_EXPECTED_ALL
        or len(hits) != expected_health
        or any(counts.get(name) != expected for name, expected in MCGILL_EXPECTED_SECTORS.items())
    ):
        result = f"INCOMPLETE {source.name}: {result}; sector counts {counts}"
    return hits, triggers, result


def parse_mcmaster_cards(source: Source, raw_html: str) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    for block in blocks_by_class(raw_html, "div", "col-lg-3"):
        title_match = re.search(
            r'<h3\b[^>]*class=["\'][^"\']*\bcard-title\b[^"\']*["\'][^>]*>(.*?)</h3>',
            block,
            flags=re.I | re.S,
        )
        if not title_match:
            continue
        links = extract_links(title_match.group(1), source.url)
        company = text_from_html(title_match.group(1))
        website = next((href for _, href in links if href.startswith("http")), "")
        description_match = re.search(
            r'<div\b[^>]*class=["\'][^"\']*\bcard-text\b[^"\']*["\'][^>]*>(.*?)</div>',
            block,
            flags=re.I | re.S,
        )
        description = text_from_html(description_match.group(1)) if description_match else ""
        hit = make_university_spinout_hit(
            source,
            company,
            source.url,
            description,
            website,
            require_bbt_relevance=False,
            trust_official_name=True,
        )
        if hit:
            hits.append(hit)
    return hits


def fetch_mcmaster_sector(sector_slug: str) -> tuple[str, str | None]:
    payload = {
        "tax_query,resource_type,0": sector_slug,
        "search-input": "",
        "event_time": "",
        "post_type": "resources",
        "template": "/opt/builds/live/wp-main/web/app/plugins/macsites-resources/templates/loop-resources.php",
        "in_plugin": "1",
        "post_id": "1601",
        "action": "macstrap_filter_process",
        "must_have": "startups",
        "sort_order": "title",
        "sort_direction": "ASC",
        "posts_per_page": "0",
        "paged": "1",
    }
    request = Request(
        MCMASTER_AJAX_URL,
        data=urlencode(payload).encode("utf-8"),
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://entrepreneurship.mcmaster.ca/startups/",
        },
    )
    try:
        raw = urlopen(request, timeout=30).read()
    except (OSError, URLError) as exc:
        return "", str(exc)
    return raw.decode("utf-8", "ignore"), None


def run_mcmaster_health_startups(
    source: Source, page_fetcher=fetch_raw_text, sector_fetcher=fetch_mcmaster_sector
):
    directory_html, error = page_fetcher(source.url)
    if error:
        return [], [], f"INCOMPLETE {source.name}: directory fetch failed: {error}"
    directory_count = len(parse_mcmaster_cards(source, directory_html))
    by_company: dict[str, DiscoveryHit] = {}
    categories: dict[str, list[str]] = {}
    sector_counts: dict[str, int] = {}
    errors: list[str] = []
    for slug, (label, expected) in MCMASTER_HEALTH_SECTORS.items():
        raw_html, sector_error = sector_fetcher(slug)
        if sector_error:
            errors.append(f"{slug}: {sector_error}")
            continue
        sector_hits = parse_mcmaster_cards(source, raw_html)
        sector_counts[slug] = len(sector_hits)
        if len(sector_hits) != expected:
            errors.append(f"{slug}: {len(sector_hits)}/{expected}")
        for hit in sector_hits:
            key = hit.company.casefold()
            by_company.setdefault(key, hit)
            categories.setdefault(key, []).append(label)
    hits = list(by_company.values())
    for hit in hits:
        labels = categories[hit.company.casefold()]
        hit.category_or_track = ", ".join(labels)
        hit.cohort_label = "McMaster official startup showcase"
        hit.matched_terms = (
            "adapter: mcmaster_health_startups; official McMaster sectors: "
            + ", ".join(labels)
        )
    hits, triggers = _dedupe_with_triggers(source, hits)
    result = (
        f"{len(hits)}/{MCMASTER_EXPECTED_HEALTH_UNIQUE} unique health startups "
        f"from {directory_count}/{MCMASTER_DIRECTORY_EXPECTED} showcase records"
    )
    if (
        directory_count != MCMASTER_DIRECTORY_EXPECTED
        or len(hits) != MCMASTER_EXPECTED_HEALTH_UNIQUE
        or errors
    ):
        result = f"INCOMPLETE {source.name}: {result}; " + "; ".join(errors)
    return hits, triggers, result


def fetch_axelys_startups() -> tuple[dict, str | None]:
    endpoint = (
        f"https://{AXELYS_ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/"
        f"{AXELYS_ALGOLIA_INDEX}/query"
    )
    request = Request(
        endpoint,
        data=json.dumps(
            {"query": "", "filters": "keywords:Startup", "hitsPerPage": 1000}
        ).encode("utf-8"),
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "X-Algolia-Application-Id": AXELYS_ALGOLIA_APP_ID,
            "X-Algolia-API-Key": AXELYS_ALGOLIA_API_KEY,
        },
    )
    try:
        raw = urlopen(request, timeout=30).read()
        return json.loads(raw.decode("utf-8", "ignore")), None
    except (OSError, URLError, json.JSONDecodeError) as exc:
        return {}, str(exc)


def parse_axelys_startups(source: Source, payload: object) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    records = payload.get("hits") or [] if isinstance(payload, dict) else []
    for record in records:
        if not isinstance(record, dict):
            continue
        company = text_from_html(
            str(record.get("EnglishTitle") or record.get("title") or "")
        )
        description = text_from_html(
            html.unescape(
                str(record.get("descriptionFull") or record.get("descriptionTruncated") or "")
            )
        )
        category_path = clean_text(str(record.get("finalPathCategories") or ""))
        website_match = re.search(r"https?://[^\s<>\"]+", description)
        website = website_match.group(0).rstrip(".,)") if website_match else ""
        evidence_url = clean_text(str(record.get("Url") or source.url))
        hit = make_university_spinout_hit(
            source,
            company,
            evidence_url,
            description,
            website,
            require_bbt_relevance=False,
            trust_official_name=True,
        )
        if hit:
            hit.category_or_track = category_path
            hit.cohort_label = "Axelys supported startups"
            hit.matched_terms = (
                "adapter: axelys_supported_startups; official Axelys Startup keyword"
            )
            hits.append(hit)
    return hits


def run_axelys_supported_startups(
    source: Source, fetcher=fetch_axelys_startups, detail_fetcher=fetch_raw_text
):
    payload, error = fetcher()
    if error:
        return [], [], f"INCOMPLETE {source.name}: public index fetch failed: {error}"
    hits = parse_axelys_startups(source, payload)
    detail_errors: list[str] = []
    for hit in hits:
        raw_html, detail_error = detail_fetcher(hit.discovery_url)
        if detail_error:
            detail_errors.append(f"{hit.company}: {detail_error}")
            continue
        for _, href in extract_links(raw_html, hit.discovery_url):
            host_text = href.casefold()
            if (
                href.startswith("http")
                and "axelys.ca" not in host_text
                and "inteum.com" not in host_text
                and "microsoft.com" not in host_text
            ):
                hit.website = href
                break
    hits, triggers = _dedupe_with_triggers(source, hits)
    nb_hits = int(payload.get("nbHits") or 0) if isinstance(payload, dict) else 0
    result = (
        f"{len(hits)}/{AXELYS_EXPECTED_STARTUPS} official Axelys-supported startups; "
        f"{sum(bool(hit.website) for hit in hits)}/{AXELYS_EXPECTED_STARTUPS} websites"
    )
    if (
        nb_hits != AXELYS_EXPECTED_STARTUPS
        or len(hits) != AXELYS_EXPECTED_STARTUPS
        or detail_errors
    ):
        result = (
            f"INCOMPLETE {source.name}: {result}; index nbHits {nb_hits}; "
            f"detail errors {len(detail_errors)}"
        )
    return hits, triggers, result


def parse_velocity_directory_page(
    source: Source, raw_html: str
) -> tuple[list[DiscoveryHit], int]:
    hits: list[DiscoveryHit] = []
    blocks = blocks_by_class(raw_html, "div", "company_list_item_wrapper")
    for block in blocks:
        if _field_text(block, "Sector") != "Health":
            continue
        company = _field_text(block, "company")
        status = _field_text(block, "Status")
        year = _field_text(block, "year")
        description_match = re.search(
            r'<div\b[^>]*class=["\'][^"\']*\bdescription\b[^"\']*["\'][^>]*>(.*?)</div>',
            block,
            flags=re.I | re.S,
        )
        description = text_from_html(description_match.group(1)) if description_match else ""
        links = extract_links(block, source.url)
        evidence_url = next(
            (href for label, href in links if "view company" in label.casefold()),
            source.url,
        )
        hit = make_university_spinout_hit(
            source,
            company,
            evidence_url,
            description,
            require_bbt_relevance=False,
            trust_official_name=True,
        )
        if hit:
            hit.category_or_track = f"Health; {status}".strip("; ")
            hit.cohort_label = "Velocity Health company directory"
            hit.cohort_year = year
            hit.matched_terms = (
                "adapter: velocity_health_companies; official Velocity sector: Health"
            )
            hits.append(hit)
    return hits, len(blocks)


def parse_velocity_detail(raw_html: str, base_url: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for block in blocks_by_class(raw_html, "div", "detail_item"):
        text = text_from_html(block)
        for label, key in [
            ("Location:", "location"),
            ("Status:", "status"),
            ("Year joined:", "year"),
            ("Tags:", "tags"),
        ]:
            if text.startswith(label):
                values[key] = clean_text(text[len(label) :])
    for label, href in extract_links(raw_html, base_url):
        if label.casefold() == "visit company":
            values["website"] = href
            break
    return values


def run_velocity_health_companies(
    source: Source, fetcher=fetch_raw_text, max_workers: int = 12
):
    hits: list[DiscoveryHit] = []
    total_records = 0
    pages_fetched = 0
    errors: list[str] = []
    for page in range(1, 20):
        url = source.url if page == 1 else f"{source.url}?c17588c1_page={page}"
        raw_html, error = fetcher(url)
        if error:
            errors.append(f"page {page}: {error}")
            break
        page_hits, page_total = parse_velocity_directory_page(source, raw_html)
        if not page_total:
            break
        pages_fetched += 1
        total_records += page_total
        hits.extend(page_hits)
        if "w-pagination-next" not in raw_html:
            break
    hits, _ = _dedupe_with_triggers(source, hits)

    def enrich(hit: DiscoveryHit) -> tuple[DiscoveryHit, str | None]:
        raw_html, error = fetcher(hit.discovery_url)
        if error:
            return hit, error
        detail = parse_velocity_detail(raw_html, hit.discovery_url)
        hit.website = detail.get("website", "")
        hit.geography = detail.get("location", "") or source.geography
        hit.cohort_year = detail.get("year", "") or hit.cohort_year
        tags = detail.get("tags", "")
        if tags:
            hit.category_or_track = f"Health; {detail.get('status', '')}; {tags}".strip("; ")
            hit.matched_terms += f"; tags: {tags}"
        return hit, None

    enriched: list[DiscoveryHit] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(enrich, hit): hit for hit in hits}
        for future in as_completed(futures):
            hit, error = future.result()
            enriched.append(hit)
            if error:
                errors.append(f"{hit.company}: {error}")
    enriched.sort(key=lambda hit: hit.company.casefold())
    enriched, triggers = _dedupe_with_triggers(source, enriched)
    result = (
        f"{len(enriched)}/{VELOCITY_EXPECTED_HEALTH} Health companies from "
        f"{total_records}/{VELOCITY_EXPECTED_ALL} directory records across "
        f"{pages_fetched}/{VELOCITY_EXPECTED_PAGES} pages"
    )
    if (
        len(enriched) != VELOCITY_EXPECTED_HEALTH
        or total_records != VELOCITY_EXPECTED_ALL
        or pages_fetched != VELOCITY_EXPECTED_PAGES
        or errors
    ):
        result = f"INCOMPLETE {source.name}: {result}; detail/page errors {len(errors)}"
    return enriched, triggers, result
