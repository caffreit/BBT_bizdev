from __future__ import annotations

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from ..http import fetch_raw_text
from ..models import DiscoveryHit, Source, TriggerEvent
from ..text import clean_text, extract_links, infer_page_product_type, source_type_trigger_event, text_from_html
from .canada_tier_a import blocks_by_class


LUMIRA_EXPECTED = 59
LUMIRA_EXPECTED_CURRENT = 34
LUMIRA_EXPECTED_EXITS = 25
GENESYS_EXPECTED_ACTIVE = 12
AMPLITUDE_EXPECTED = 24
AMPLITUDE_EXPECTED_ACTIVE = 20
AMPLITUDE_EXPECTED_EXITS = 4
BDC_EXPECTED_HEALTH = 31
FACIT_EXPECTED_TOTAL = 81
FACIT_EXPECTED_COMPANY_LIKE = 56

BDC_FILTER_URL = "https://www.bdc.ca/en/bdc-capital/venture-capital/portfolio/FilterByFund"
BDC_VIEW_MORE_URL = "https://www.bdc.ca/features/pages/landingpage/viewmorecompanies?pageLink=6918&language=en-CA"
BDC_HEALTH_SECTORS = [
    "Biotechnology", "Devices", "Digitalhealth", "Drugs", "Medicalhealth", "Healthcareservices",
]
FACIT_INSTITUTION_ASSET_PREFIX = re.compile(
    r"^(?:OICR|Robarts Research Institute|Ottawa Hospital Research Institute|"
    r"Sunnybrook Research Institute|University of Toronto|Queen.s University|"
    r"McMaster University|UHN \()",
    flags=re.I,
)

LUMIRA_NAME_MAP = {
    "Aurinia": "Aurinia Pharmaceuticals",
    "BardyDx": "Bardy Diagnostics",
    "corus": "Corus Pharmaceuticals",
    "Edesa Bio": "Edesa Biotech",
    "ESSA Pharma": "ESSA Pharmaceuticals",
    "Fusion Pharma": "Fusion Pharmaceuticals",
    "ISTA": "ISTA Pharmaceuticals",
    "KAI Pharma": "KAI Pharmaceuticals",
    "Congruence Tx Logo": "Congruence Therapeutics",
    "Biotheryx": "BioTheryX",
}


def _tag_text(raw_html: str, tag: str) -> str:
    match = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", raw_html, flags=re.I | re.S)
    return text_from_html(match.group(1)) if match else ""


def _meta_description(raw_html: str) -> str:
    match = re.search(
        r'<meta\b[^>]*(?:name|property)=["\'](?:description|og:description)["\'][^>]*'
        r'content=["\']([^"\']*)',
        raw_html,
        flags=re.I,
    )
    return clean_text(html.unescape(match.group(1))) if match else ""


def fetch_investor_browser_text(url: str) -> tuple[str, str | None]:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    try:
        raw = urlopen(request, timeout=30).read()
    except (OSError, URLError) as exc:
        return "", str(exc)
    return raw.decode("utf-8", "ignore"), None


def _external_website(raw_html: str, base_url: str, excluded_domain: str) -> str:
    for _, href in extract_links(raw_html, base_url):
        if href.startswith("http") and excluded_domain not in href.lower() and "linkedin.com" not in href.lower():
            return href
    for href in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\']', raw_html, flags=re.I):
        absolute = urljoin(base_url, html.unescape(href))
        if absolute.startswith("http") and excluded_domain not in absolute.lower() and "linkedin.com" not in absolute.lower():
            return absolute
    return ""


def _investor_hit(
    source: Source,
    company: str,
    evidence_url: str,
    *,
    status: str,
    category: str = "",
    description: str = "",
    website: str = "",
    geography: str = "",
    matched: str = "",
) -> DiscoveryHit:
    context = " ".join([category, description])
    return DiscoveryHit(
        company=clean_text(company),
        source_name=source.name,
        source_type=source.source_type,
        discovery_url=evidence_url,
        discovery_rationale=f"{source.name} adapter extracted this company from an official investment portfolio.",
        product_type=infer_page_product_type(source, context),
        geography=geography or source.geography,
        website=website,
        matched_terms=matched or f"adapter: {source.adapter}",
        accelerator_program=source.name,
        cohort_label=f"{source.name} {status.lower()} portfolio",
        category_or_track="; ".join(value for value in [status, category] if value),
        company_description=description,
    )


def _dedupe(source: Source, hits: list[DiscoveryHit]) -> tuple[list[DiscoveryHit], list[TriggerEvent]]:
    output, triggers, seen = [], [], set()
    for hit in hits:
        key = (hit.company.lower(), hit.discovery_url)
        if not hit.company or key in seen:
            continue
        seen.add(key)
        output.append(hit)
        trigger = source_type_trigger_event(source, hit.company)
        if trigger:
            triggers.append(TriggerEvent(hit.company, trigger[0], trigger[1], source.name, hit.discovery_url))
    return output, triggers


def parse_lumira_portfolio(source: Source, raw_html: str) -> list[DiscoveryHit]:
    status_by_id: dict[str, str] = {}
    for card in blocks_by_class(raw_html, "div", "grid-item"):
        target = re.search(r'data-bs-target=["\']#([^"\']+)', card, flags=re.I)
        if not target:
            continue
        classes = re.search(r'class=["\']([^"\']*)', card, flags=re.I)
        status = "Exited" if classes and "exits" in classes.group(1).split() else "Current"
        status_by_id[target.group(1)] = status

    hits = []
    for modal in blocks_by_class(raw_html, "div", "portfolio-madal"):
        modal_id = re.search(r'id=["\']([^"\']+)', modal, flags=re.I)
        if not modal_id or modal_id.group(1) not in status_by_id:
            continue
        image = re.search(
            r'class=["\'][^"\']*member-img-modal[^"\']*["\'].*?<img\b[^>]*alt=["\']([^"\']*)',
            modal, flags=re.I | re.S,
        )
        name = clean_text(html.unescape(image.group(1))) if image else ""
        desc_blocks = blocks_by_class(modal, "div", "modal-member-desc")
        description = text_from_html(desc_blocks[0]) if desc_blocks else ""
        if not name and "Sound Blade Medical" in description:
            name = "Sound Blade Medical"
        if not name and description.startswith("Contraline "):
            name = "Contraline"
        if not name and description.startswith("Navion "):
            name = "Navion"
        name = LUMIRA_NAME_MAP.get(name, name)
        industry = ""
        headquarters = ""
        industry_match = re.search(r"Industry:\s*(.*?)(?:\||Headquarters:|Website|$)", description, flags=re.I)
        headquarters_match = re.search(r"Headquarters:\s*(.*?)(?:\||Website|$)", description, flags=re.I)
        if industry_match:
            industry = clean_text(industry_match.group(1))
        if headquarters_match:
            headquarters = clean_text(headquarters_match.group(1))
        hits.append(
            _investor_hit(
                source, name, source.url, status=status_by_id[modal_id.group(1)],
                category=industry, description=description,
                website=_external_website(modal, source.url, "lumiraventures.com"),
                geography=headquarters or source.geography,
                matched=f"adapter: lumira_portfolio; status: {status_by_id[modal_id.group(1)]}; headquarters: {headquarters}",
            )
        )
    return hits


def run_lumira(source: Source, fetcher=fetch_raw_text):
    raw_html, error = fetcher(source.url)
    if error:
        return [], [], f"INCOMPLETE {source.name}: {error}"
    hits, triggers = _dedupe(source, parse_lumira_portfolio(source, raw_html))
    current = sum("Current" in hit.category_or_track for hit in hits)
    exits = sum("Exited" in hit.category_or_track for hit in hits)
    canadian = sum(bool(re.search(r"\b(?:Canada|Ontario|Quebec|Québec|Alberta|British Columbia|BC|Nova Scotia)\b", hit.geography, re.I)) for hit in hits)
    result = f"{len(hits)}/{LUMIRA_EXPECTED} investments; {current}/{LUMIRA_EXPECTED_CURRENT} current; {exits}/{LUMIRA_EXPECTED_EXITS} exited; {canadian} Canadian-headquartered/presence records"
    if len(hits) != LUMIRA_EXPECTED or current != LUMIRA_EXPECTED_CURRENT or exits != LUMIRA_EXPECTED_EXITS:
        result = f"INCOMPLETE {source.name}: {result}"
    return hits, triggers, result


def parse_genesys_index(raw_html: str, page_url: str) -> list[str]:
    links = []
    for href in re.findall(r'<a\b[^>]*href=["\']([^"\']*/investments/[^"\']+)["\']', raw_html, flags=re.I):
        url = urljoin(page_url, html.unescape(href))
        if url.endswith("/coming-soon") or url in links:
            continue
        links.append(url)
    return links


def parse_genesys_detail(source: Source, raw_html: str, url: str) -> DiscoveryHit:
    company = _tag_text(raw_html, "h1")
    paragraphs = [text_from_html(value) for value in re.findall(r"<p\b[^>]*>(.*?)</p>", raw_html, flags=re.I | re.S)]
    description = max(paragraphs, key=len, default=_meta_description(raw_html))
    website = _external_website(raw_html, url, "genesyscapital.com")
    return _investor_hit(
        source, company, url, status="Current", category="Healthcare / life sciences",
        description=description, website=website, geography="Canada / North America",
        matched="adapter: genesys_portfolio; official active investment detail",
    )


def run_genesys(source: Source, fetcher=fetch_raw_text):
    raw_html, error = fetcher(source.url)
    if error:
        return [], [], f"INCOMPLETE {source.name}: {error}"
    urls = parse_genesys_index(raw_html, source.url)
    hits, errors = [], []
    for url in urls:
        detail, detail_error = fetcher(url)
        if detail_error:
            errors.append(f"{url}: {detail_error}")
            continue
        hits.append(parse_genesys_detail(source, detail, url))
    hits, triggers = _dedupe(source, hits)
    result = f"{len(hits)}/{GENESYS_EXPECTED_ACTIVE} active Genesys investments; excluded placeholder and acquired/divested past-success cards"
    if len(urls) != GENESYS_EXPECTED_ACTIVE or len(hits) != GENESYS_EXPECTED_ACTIVE or errors:
        result = f"INCOMPLETE {source.name}: {result}"
    return hits, triggers, result


def parse_amplitude_portfolio(source: Source, raw_html: str) -> list[DiscoveryHit]:
    match = re.search(r':portfolios="(\[.*?\])"', raw_html, flags=re.S)
    if not match:
        return []
    records = json.loads(html.unescape(match.group(1)))
    hits = []
    for record in records:
        status_data = record.get("portfolio_status") or {}
        status = "Exited" if status_data.get("value") == "exited" else "Current"
        categories = ", ".join(record.get("categories") or [])
        description = clean_text(record.get("content") or "")
        location_match = re.search(r"(?:Headquartered|based)\s+in\s+([^.;]+)", description, flags=re.I)
        linkedin = clean_text(record.get("linkedin_link") or "")
        hits.append(
            _investor_hit(
                source, record.get("title") or "", source.url, status=status,
                category=categories, description=description,
                website=clean_text(record.get("website") or ""),
                geography=location_match.group(1) if location_match else source.geography,
                matched=f"adapter: amplitude_portfolio; status: {status}; partnered year: {record.get('partnered_year') or ''}; LinkedIn: {linkedin}",
            )
        )
    return hits


def run_amplitude(source: Source, fetcher=fetch_raw_text):
    raw_html, error = fetcher(source.url)
    if error:
        return [], [], f"INCOMPLETE {source.name}: {error}"
    hits, triggers = _dedupe(source, parse_amplitude_portfolio(source, raw_html))
    current = sum("Current" in hit.category_or_track for hit in hits)
    exits = sum("Exited" in hit.category_or_track for hit in hits)
    result = f"{len(hits)}/{AMPLITUDE_EXPECTED} portfolio companies; {current}/{AMPLITUDE_EXPECTED_ACTIVE} active; {exits}/{AMPLITUDE_EXPECTED_EXITS} exited"
    if len(hits) != AMPLITUDE_EXPECTED or current != AMPLITUDE_EXPECTED_ACTIVE or exits != AMPLITUDE_EXPECTED_EXITS:
        result = f"INCOMPLETE {source.name}: {result}"
    return hits, triggers, result


def parse_bdc_cards(raw_html: str, page_url: str) -> list[tuple[str, str]]:
    records = []
    for anchor in re.findall(r"<a\b[^>]*>", raw_html, flags=re.I):
        href_match = re.search(r'href=["\']([^"\']*/en/bdc-capital/venture-capital/portfolio/[^"\']+)', anchor, flags=re.I)
        title_match = re.search(r'title=["\']([^"\']+)', anchor, flags=re.I)
        if not href_match or not title_match:
            continue
        href, title = href_match.group(1), title_match.group(1)
        record = (clean_text(html.unescape(title)), urljoin(page_url, html.unescape(href)))
        if record not in records:
            records.append(record)
    return records


def parse_bdc_detail(source: Source, company: str, raw_html: str, url: str, sectors: list[str]) -> DiscoveryHit:
    text = text_from_html(raw_html)
    region = ""
    fund = ""
    region_match = re.search(r"Region\s+(.+?)\s+Industry sector", text, flags=re.I)
    fund_match = re.search(r"Fund\s+(.+?)(?:\s+Region|\s+Contact|$)", text, flags=re.I)
    if region_match:
        region = clean_text(region_match.group(1))
    if fund_match:
        fund = clean_text(fund_match.group(1))
    description = _meta_description(raw_html)
    website = _external_website(raw_html, url, "bdc.ca")
    return _investor_hit(
        source, company, url, status="Current", category=", ".join(sectors),
        description=description, website=website, geography=region or "Canada",
        matched=f"adapter: bdc_health_portfolio; official sector filters: {', '.join(sectors)}; fund: {fund}",
    )


def run_bdc_health(source: Source, fetcher=None, max_workers: int = 8):
    fetcher = fetcher or fetch_investor_browser_text
    companies: dict[str, dict[str, object]] = {}
    errors = []
    for sector in BDC_HEALTH_SECTORS:
        params = {
            "filterCompanyBy": "Region", "pageNumber": 1, "has-more-companies": "True",
            "fundId": "", "industrySector": sector, "regionExit": "ALL", "isManagement": "false",
        }
        url = f"{BDC_FILTER_URL}?{urlencode(params)}"
        raw_html, error = fetcher(url)
        if error:
            errors.append(f"{sector}: {error}")
            continue
        for company, detail_url in parse_bdc_cards(raw_html, source.url):
            record = companies.setdefault(detail_url, {"company": company, "sectors": []})
            record["sectors"].append(sector)

    hits = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetcher, url): (url, record)
            for url, record in companies.items()
        }
        for future in as_completed(futures):
            url, record = futures[future]
            raw_html, error = future.result()
            if error:
                errors.append(f"{url}: {error}")
                continue
            hits.append(parse_bdc_detail(source, str(record["company"]), raw_html, url, list(record["sectors"])))
    hits.sort(key=lambda hit: hit.company.lower())
    hits, triggers = _dedupe(source, hits)
    result = f"{len(hits)}/{BDC_EXPECTED_HEALTH} current direct health/life-science companies across six official BDC sector filters"
    if len(companies) != BDC_EXPECTED_HEALTH or len(hits) != BDC_EXPECTED_HEALTH or errors:
        result = f"INCOMPLETE {source.name}: {result}; errors: {' | '.join(errors)}"
    return hits, triggers, result


def parse_facit_portfolio(source: Source, raw_html: str) -> tuple[list[DiscoveryHit], int, list[str]]:
    articles = re.findall(r"<article\b[^>]*id=[\"']portfolio-[^\"']+[\"'][^>]*>(.*?)</article>", raw_html, flags=re.I | re.S)
    hits, excluded = [], []
    for article in articles:
        company = _tag_text(article, "h1")
        if FACIT_INSTITUTION_ASSET_PREFIX.search(company):
            excluded.append(company)
            continue
        terms = {}
        for term in blocks_by_class(article, "div", "term"):
            labels = blocks_by_class(term, "div", "label")
            values = blocks_by_class(term, "div", "value")
            if labels and values:
                terms[text_from_html(labels[0]).rstrip(":")] = text_from_html(values[0])
        innovation = blocks_by_class(article, "div", "innovation")
        description = text_from_html(innovation[0]) if innovation else ""
        detail_match = re.search(r'<a\b[^>]*href=["\']([^"\']*/portfolio/[^"\']+)', article, flags=re.I)
        detail_url = urljoin(source.url, detail_match.group(1)) if detail_match else source.url
        category = "; ".join(
            value for value in [
                terms.get("Innovation Type", ""), terms.get("Cancer Type", ""),
                terms.get("Funding Stage", ""), terms.get("Fund", ""),
            ] if value
        )
        hits.append(
            _investor_hit(
                source, company, detail_url,
                status=terms.get("Funding Stage", "Funded"),
                category=category, description=description,
                geography="Ontario, Canada",
                matched=f"adapter: facit_portfolio; fund: {terms.get('Fund', '')}; institution-owned pre-company assets excluded",
            )
        )
    return hits, len(articles), excluded


def run_facit(source: Source, fetcher=fetch_raw_text):
    raw_html, error = fetcher(source.url)
    if error:
        return [], [], f"INCOMPLETE {source.name}: {error}"
    parsed, total, excluded = parse_facit_portfolio(source, raw_html)
    hits, triggers = _dedupe(source, parsed)
    result = f"{len(hits)}/{FACIT_EXPECTED_COMPANY_LIKE} company-like funded entities from {total}/{FACIT_EXPECTED_TOTAL} portfolio records; {len(excluded)} institution-owned pre-company assets excluded"
    if total != FACIT_EXPECTED_TOTAL or len(hits) != FACIT_EXPECTED_COMPANY_LIKE:
        result = f"INCOMPLETE {source.name}: {result}"
    return hits, triggers, result
