from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.error import URLError
from urllib.request import Request, urlopen

from ..http import fetch_raw_text
from ..models import DiscoveryHit, Source, TriggerEvent
from ..text import clean_text, extract_links, text_from_html
from .accelerators import dedupe_hits_with_triggers, make_accelerator_hit


CTS_SITEMAP_URL = "https://ctssante.com/portfolio-sitemap.xml"
CTS_EXPECTED = 21
DISTRICT3_EXPECTED_TOTAL = 25
DISTRICT3_EXPECTED_HEALTH = 12
MEDTEQ_EXPECTED = 17
UALBERTA_EXPECTED = 44
UBC_EXPECTED_TOTAL = 385
UBC_EXPECTED_HEALTH = 152

OBIO_COHORTS = [
    (
        "WiHI Seed 2023",
        "2023",
        "https://www.obio.ca/obio-backup/obio1/2024/1/obio-celebrates-the-advancement-of-women-in-health-science-with-wihi-seed-program-and-leadership-awards",
        [
            "A.I. VALI", "Atorvia", "Cove Neurosciences",
            "HDAX Therapeutics", "ImaginAble Solutions", "mDETECT", "MoxyPatch",
            "Noa Therapeutics", "Paradox Immunotherapeutics", "Tenomix",
            "Vessl Prosthetics",
        ],
    ),
    (
        "WiHI Seed 2025",
        "2025",
        "https://www.obio.ca/obio-backup/obio1/2025/10/obio-introduces-the-future-female-leaders-in-life-sciences",
        [
            "20/20 OptimEyes Technologies", "Arche Biotechnologies",
            "BLOCK Biosciences", "Fibra", "Hada Medtech", "NodeAI Diagnostics",
            "NuvoBio", "Savyn Tech", "Virano Therapeutics",
        ],
    ),
    (
        "WeSEED 2025",
        "2025",
        "https://facit.ca/news/launch-weseed",
        [
            "A.I. VALI Inc.", "Genetics Adviser Inc.", "AiimSense Inc.",
            "Asima Health Inc.", "Cura Therapeutics Inc.",
        ],
    ),
]

MEDTEQ_COMPANIES = [
    "Swiftsure Innovations", "Gray Oncology Solutions", "Arbutus Medical",
    "Sonic Incytes", "Aerial", "Aifred Health", "Densitas", "Eli",
    "Nanology Labs", "Optina Diagnostics", "RNA Diagnostics", "SeamlessMD",
    "Spring Loaded Technology", "Thorasys", "Spinologics", "HALEO", "LUCID",
]

UCEED_PAGES = [
    ("UCeed Health Fund", "https://ucalgary.ca/uceed/funds/health-fund", 26),
    (
        "UCeed Child Health and Wellness Fund",
        "https://ucalgary.ca/uceed/funds/child-health-and-wellness-fund",
        16,
    ),
]


class _BlockParser(HTMLParser):
    """Collect complete HTML blocks whose opening tag has a target class."""

    def __init__(self, tag: str, class_name: str):
        super().__init__(convert_charrefs=False)
        self.tag = tag
        self.class_name = class_name
        self.depth = 0
        self.parts: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag, attrs):
        raw = self.get_starttag_text()
        classes = dict(attrs).get("class", "").split()
        if not self.depth and tag == self.tag and self.class_name in classes:
            self.depth = 1
            self.parts = [raw]
        elif self.depth:
            self.parts.append(raw)
            if tag == self.tag:
                self.depth += 1

    def handle_startendtag(self, tag, attrs):
        if self.depth:
            self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if not self.depth:
            return
        self.parts.append(f"</{tag}>")
        if tag == self.tag:
            self.depth -= 1
            if not self.depth:
                self.blocks.append("".join(self.parts))
                self.parts = []

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)

    def handle_entityref(self, name):
        if self.depth:
            self.parts.append(f"&{name};")

    def handle_charref(self, name):
        if self.depth:
            self.parts.append(f"&#{name};")


def blocks_by_class(raw_html: str, tag: str, class_name: str) -> list[str]:
    parser = _BlockParser(tag, class_name)
    parser.feed(raw_html)
    return parser.blocks


def _tag_text(block: str, tag: str, class_name: str = "") -> str:
    class_pattern = (
        rf'(?=[^>]*class=["\'][^"\']*\b{re.escape(class_name)}\b[^"\']*["\'])'
        if class_name else ""
    )
    match = re.search(
        rf"<{tag}\b{class_pattern}[^>]*>(.*?)</{tag}>", block, flags=re.I | re.S
    )
    return text_from_html(match.group(1)) if match else ""


def _external_website(block: str, base_url: str) -> str:
    for label, href in extract_links(block, base_url):
        if href.startswith("http") and "linkedin.com" not in href.lower():
            return href
    return ""


def _hrefs(block: str, base_url: str) -> list[str]:
    return [
        urljoin(base_url, href)
        for href in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\']', block, flags=re.I)
    ]


def fetch_cts_browser_text(url: str) -> tuple[str, str | None]:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        raw = urlopen(request, timeout=25).read()
    except (OSError, URLError) as exc:
        return "", str(exc)
    return raw.decode("utf-8", "ignore"), None


def parse_cts_company(source: Source, page_url: str, raw_html: str) -> DiscoveryHit | None:
    company = _tag_text(raw_html, "h1")
    description_match = re.search(
        r'<meta\b[^>]*(?:name|property)=["\'](?:description|og:description)["\'][^>]*content=["\']([^"\']*)',
        raw_html, flags=re.I,
    )
    description = clean_text(description_match.group(1)) if description_match else ""
    website = ""
    for label, href in extract_links(raw_html, page_url):
        if "website" in label.lower() and href.startswith("http"):
            website = href
            break
    return make_accelerator_hit(
        source, company, page_url, accelerator_program="CTS Santé",
        cohort_label="CTS Santé portfolio", category_or_track="Health sciences",
        company_description=description, website=website, geography="Canada",
        matched_terms="adapter: cts_sante_portfolio; official portfolio sitemap",
        trust_curated_name=True,
    )


def run_cts_sante(source: Source, fetcher=None):
    fetcher = fetcher or fetch_cts_browser_text
    sitemap, error = fetcher(CTS_SITEMAP_URL)
    if error:
        return [], [], f"INCOMPLETE {source.name}: sitemap fetch failed: {error}"
    urls = re.findall(r"<loc>\s*(https?://[^<]+)\s*</loc>", sitemap, flags=re.I)
    urls = [url for url in urls if "/portfolio/" in url]
    hits, errors = [], []
    for url in urls:
        raw_html, page_error = fetcher(url)
        if page_error:
            errors.append(f"{url}: {page_error}")
            continue
        hit = parse_cts_company(source, url, raw_html)
        if hit:
            hits.append(hit)
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{len(hits)}/{CTS_EXPECTED} CTS Santé portfolio companies; {len(triggers)} trigger events"
    if len(urls) != CTS_EXPECTED or len(hits) != CTS_EXPECTED or errors:
        result = f"INCOMPLETE {source.name}: {result}; sitemap URLs {len(urls)}"
    return hits, triggers, result


def parse_district3_page(source: Source, raw_html: str) -> list[DiscoveryHit]:
    hits = []
    for block in blocks_by_class(raw_html, "div", "startup_grid-card"):
        stream = _tag_text(block, "div", "tag")
        if stream.lower() not in {"healthcare", "biotech"}:
            continue
        links = extract_links(block, source.url)
        company = next((label for label, href in links if href.startswith("http")), "")
        website = next((href for label, href in links if href.startswith("http")), "")
        description = _tag_text(block, "div", "news_grid-card-text")
        hit = make_accelerator_hit(
            source, company, source.url, accelerator_program="District 3",
            cohort_label="District 3 startup directory", category_or_track=stream,
            company_description=description, website=website, geography="Canada",
            matched_terms=f"adapter: district3_health; official stream: {stream}",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits


def run_district3(source: Source, fetcher=fetch_raw_text):
    hits, total, errors = [], 0, []
    for page in range(1, 10):
        url = source.url if page == 1 else f"{source.url}?37e06a8e_page={page}"
        raw_html, error = fetcher(url)
        if error:
            errors.append(f"{url}: {error}")
            break
        cards = blocks_by_class(raw_html, "div", "startup_grid-card")
        if not cards:
            break
        total += len(cards)
        hits.extend(parse_district3_page(source, raw_html))
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = (
        f"{len(hits)}/{DISTRICT3_EXPECTED_HEALTH} Healthcare/Biotech companies "
        f"from {total}/{DISTRICT3_EXPECTED_TOTAL} live startup cards; {len(triggers)} trigger events"
    )
    if total != DISTRICT3_EXPECTED_TOTAL or len(hits) != DISTRICT3_EXPECTED_HEALTH or errors:
        result = f"INCOMPLETE {source.name}: {result}"
    return hits, triggers, result


def run_obio(source: Source, fetcher=fetch_raw_text):
    hits, errors = [], []
    for cohort, year, url, companies in OBIO_COHORTS:
        raw_html, error = fetcher(url)
        if error:
            errors.append(f"{url}: {error}")
            continue
        page_text = text_from_html(raw_html).lower()
        for company in companies:
            token = re.sub(r"\binc\.?$", "", company, flags=re.I).strip().lower()
            if token not in page_text:
                errors.append(f"{url}: missing {company}")
                continue
            hit = make_accelerator_hit(
                source, company, url, accelerator_program="OBIO",
                cohort_label=cohort, cohort_year=year,
                category_or_track="Life sciences / health science",
                geography="Canada",
                matched_terms=f"adapter: obio_cohorts; official cohort: {cohort}",
                trust_curated_name=True,
            )
            if hit:
                hits.append(hit)
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    expected = sum(len(item[3]) for item in OBIO_COHORTS)
    result = f"{len(hits)}/{expected} public named OBIO cohort records; {len({h.company.lower() for h in hits})} unique names"
    if len(hits) != expected or errors:
        result = f"INCOMPLETE {source.name}: {result}; " + " | ".join(errors)
    return hits, triggers, result


def run_medteq(source: Source, fetcher=fetch_raw_text):
    raw_html, error = fetcher(source.url)
    if error:
        return [], [], f"INCOMPLETE {source.name}: portfolio fetch failed: {error}"
    portfolio = re.search(
        r'class=["\'][^"\']*mosaique-logos[^"\']*["\'](.*?)(?:</section>|<footer)',
        raw_html, flags=re.I | re.S,
    )
    scope = portfolio.group(1) if portfolio else raw_html
    blocks = blocks_by_class(scope, "div", "box")
    hits = []
    for index, company in enumerate(MEDTEQ_COMPANIES):
        block = blocks[index] if index < len(blocks) else ""
        description = text_from_html(block)
        hit = make_accelerator_hit(
            source, company, source.url, accelerator_program="MEDTEQ+",
            cohort_label="MEDTEQ+ investment portfolio",
            category_or_track="Medical technology investment",
            company_description=description, website=_external_website(block, source.url),
            geography="Canada",
            matched_terms="adapter: medteq_portfolio; official investment portfolio",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = f"{len(hits)}/{MEDTEQ_EXPECTED} MEDTEQ+ investment portfolio companies; {len(blocks)} live logo cards"
    if len(hits) != MEDTEQ_EXPECTED or len(blocks) != MEDTEQ_EXPECTED:
        result = f"INCOMPLETE {source.name}: {result}"
    return hits, triggers, result


def parse_uceed_page(source: Source, raw_html: str, url: str, cohort: str) -> list[DiscoveryHit]:
    heading = re.search(r"<h2\b[^>]*>.*?Portfolio.*?</h2>", raw_html, flags=re.I | re.S)
    if not heading:
        return []
    rest = raw_html[heading.end():]
    next_h2 = re.search(r"<h2\b", rest, flags=re.I)
    scope = rest[:next_h2.start()] if next_h2 else rest
    matches = list(re.finditer(r"<h3\b[^>]*>(.*?)</h3>", scope, flags=re.I | re.S))
    hits = []
    for index, match in enumerate(matches):
        block = scope[match.end():matches[index + 1].start()] if index + 1 < len(matches) else scope[match.end():]
        company = text_from_html(match.group(1)).lstrip("•·–— \ufeff")
        hit = make_accelerator_hit(
            source, company, url, accelerator_program="Innovate Calgary / UCeed",
            cohort_label=cohort, category_or_track="Health innovation investment",
            company_description=text_from_html(block),
            website=_external_website(block, url), geography="Canada",
            matched_terms=f"adapter: uceed_health; official fund: {cohort}",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits


def run_uceed(source: Source, fetcher=fetch_raw_text):
    hits, errors, counts = [], [], []
    for cohort, url, expected in UCEED_PAGES:
        raw_html, error = fetcher(url)
        if error:
            errors.append(f"{url}: {error}")
            continue
        page_hits = parse_uceed_page(source, raw_html, url, cohort)
        counts.append((cohort, len(page_hits), expected))
        hits.extend(page_hits)
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    expected_total = sum(item[2] for item in UCEED_PAGES)
    unique = len({hit.company.lower() for hit in hits})
    result = f"{len(hits)}/{expected_total} UCeed health fund records; {unique} unique company names"
    if any(actual != expected for _, actual, expected in counts) or errors:
        result = f"INCOMPLETE {source.name}: {result}; counts {counts}"
    return hits, triggers, result


def parse_ualberta(source: Source, raw_html: str, evidence_url: str) -> list[DiscoveryHit]:
    hits = []
    for block in blocks_by_class(raw_html, "div", "card"):
        company = _tag_text(block, "span")
        if not company:
            continue
        body = _tag_text(block, "div", "card-body")
        hit = make_accelerator_hit(
            source, company, evidence_url,
            accelerator_program="University of Alberta Health Innovation Hub",
            cohort_label="Health Innovation Hub companies",
            category_or_track="Health innovation",
            company_description=body, website=_external_website(block, evidence_url),
            geography="Alberta, Canada",
            matched_terms="adapter: ualberta_health_hub; official company directory",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits


def run_ualberta(source: Source, fetcher=fetch_raw_text):
    urls = [
        source.url,
        "https://www.preview.ualberta.ca/en/medicine/research/health-innovation-hub/companies.html",
    ]
    errors = []
    for url in urls:
        raw_html, error = fetcher(url)
        if error:
            errors.append(f"{url}: {error}")
            continue
        hits, triggers = dedupe_hits_with_triggers(source, parse_ualberta(source, raw_html, url))
        if hits:
            result = f"{len(hits)}/{UALBERTA_EXPECTED} Health Innovation Hub companies; route: {url}"
            if len(hits) != UALBERTA_EXPECTED:
                result = f"INCOMPLETE {source.name}: {result}"
            return hits, triggers, result
    return [], [], f"INCOMPLETE {source.name}: no usable company directory; {' | '.join(errors)}"


def parse_ubc_page(source: Source, raw_html: str, url: str) -> tuple[list[DiscoveryHit], int]:
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", raw_html, flags=re.I | re.S)
    hits = []
    total = 0
    for row in rows:
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, flags=re.I | re.S)
        if len(cells) < 5:
            continue
        total += 1
        impact = text_from_html(cells[2])
        if "Human Health" not in [clean_text(value) for value in re.split(r"[,|]", impact)]:
            continue
        company = _tag_text(cells[0], "h5") or text_from_html(cells[0])
        links = _hrefs(cells[4], url)
        website = next((href for href in links if "linkedin.com" not in href.lower()), "")
        linkedin = next((href for href in links if "linkedin.com" in href.lower()), "")
        venture_type = text_from_html(cells[3])
        location = text_from_html(cells[1])
        hit = make_accelerator_hit(
            source, company, url, accelerator_program="Innovation UBC",
            cohort_label="Innovation UBC Human Health portfolio",
            category_or_track=venture_type, website=website,
            geography=location or "British Columbia, Canada",
            matched_terms=f"adapter: innovation_ubc_health; impact area: Human Health; LinkedIn: {linkedin}",
            trust_curated_name=True,
        )
        if hit:
            hits.append(hit)
    return hits, total


def run_innovation_ubc(source: Source, fetcher=fetch_raw_text):
    hits, total, errors, pages = [], 0, [], 0
    for page in range(20):
        url = source.url if page == 0 else f"{source.url}?page={page}"
        raw_html, error = fetcher(url)
        if error:
            errors.append(f"{url}: {error}")
            break
        page_hits, page_total = parse_ubc_page(source, raw_html, url)
        if not page_total:
            break
        pages += 1
        total += page_total
        hits.extend(page_hits)
    hits, triggers = dedupe_hits_with_triggers(source, hits)
    result = (
        f"{len(hits)}/{UBC_EXPECTED_HEALTH} Human Health companies from "
        f"{total}/{UBC_EXPECTED_TOTAL} portfolio rows across {pages}/7 pages"
    )
    if len(hits) != UBC_EXPECTED_HEALTH or total != UBC_EXPECTED_TOTAL or pages != 7 or errors:
        result = f"INCOMPLETE {source.name}: {result}"
    return hits, triggers, result
