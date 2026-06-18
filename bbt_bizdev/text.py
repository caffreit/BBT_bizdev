from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, unquote

from .config import COMPANY_REGISTRY, DISCOVERY_TERMS, SOURCE_TRIGGER_TYPES
from .models import SearchResult, Source


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()

class LinkTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href_stack: list[str | None] = []
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        self._href_stack.append(href)
        self._current_text.append("")

    def handle_data(self, data: str):
        if self._href_stack:
            self._current_text[-1] += data

    def handle_endtag(self, tag: str):
        if tag.lower() != "a" or not self._href_stack:
            return
        href = self._href_stack.pop()
        text = clean_text(self._current_text.pop())
        if href and text:
            self.links.append((text, href))

def extract_links(raw_html: str, base_url: str) -> list[tuple[str, str]]:
    parser = LinkTextParser()
    try:
        parser.feed(raw_html)
    except Exception:
        return []
    return [(text, urljoin(base_url, href)) for text, href in parser.links]

def text_from_html(raw_html: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", raw_html, flags=re.I | re.S)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()

def article_title_without_publisher(title: str) -> str:
    if " - " in title:
        return title.rsplit(" - ", 1)[0].strip()
    return title.strip()

def known_company_from_text(text: str) -> str | None:
    lower_text = text.lower()
    for company, meta in COMPANY_REGISTRY.items():
        if any(alias.lower() in lower_text for alias in meta["aliases"]):
            return company
    return None

def tidy_company_name(candidate: str) -> str:
    candidate = re.sub(r"^[^A-Za-z0-9]+", "", candidate.strip())
    if re.search(r"['’]s\s+", candidate):
        candidate = re.split(r"['’]s\s+", candidate, maxsplit=1)[0]
    candidate = candidate.split(",", 1)[0]
    candidate = re.sub(
        r"\b(Exclusive|MedTech|Med-tech|Healthtech|Health-care|Digital health|Medical device|AI|Startup|Company|Maker|Developer|Platform|Provider|Firm|French|Estonian|Irish|Female-led|Europe-first|Vienna-based|SA-based|New)\b[:\s-]*",
        "",
        candidate,
        flags=re.I,
    )
    candidate = re.split(r"\s+(?:after|as|for|from|in|on|to|with)\s+", candidate, maxsplit=1, flags=re.I)[0]
    candidate = re.sub(r"['’]s$", "", candidate.strip(" :-,.;"))
    return re.sub(r"\s+", " ", candidate).strip()

def extract_company_from_search_result(result: SearchResult) -> str | None:
    combined = f"{result.title} {result.summary}"
    known = known_company_from_text(combined)
    if known:
        return known

    title = article_title_without_publisher(result.title)
    trigger_verbs = (
        r"raises?|raised|lands?|landed|secures?|secured|closes?|closed|bags?|bagged|nabs?|nabbed|"
        r"announces?|announced|launches?|launched|unveils?|unveiled|wins?|won|receives?|received|"
        r"gets?|got|earns?|earned|scores?|scored|obtains?|obtained|gains?|gained"
    )
    patterns = [
        rf"^(?P<company>[A-Z][A-Za-z0-9&.,'’\- ]{{1,80}}?)\s+(?:{trigger_verbs})\b",
        rf"^(?P<company>[A-Z][A-Za-z0-9&.,'’\- ]{{1,80}}?)\s+.*?\b(?:Series [A-Z]|seed|funding|FDA clearance|510\(k\)|De Novo|CE mark)\b",
        rf"\b(?:startup|company|maker|developer|provider)\s+(?P<company>[A-Z][A-Za-z0-9&.,'’\- ]{{1,60}}?)\s+(?:{trigger_verbs})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, title, flags=re.I)
        if not match:
            continue
        company = tidy_company_name(match.group("company"))
        if is_plausible_company_name(company):
            return company
    return None

def is_plausible_company_name(company: str) -> bool:
    if len(company) < 2 or len(company) > 70:
        return False
    if company[0].islower():
        return False
    words = company.split()
    if len(words) > 4:
        return False
    blocked = {
        "FDA", "AI", "The", "This", "What", "How", "Why", "Medical", "Digital", "Health",
        "Medtech", "More", "Big", "Paris", "Irish", "Diagnostics", "Assessing", "Quality",
        "Stroke", "Ultrasound", "Weekly", "Apple Watch", "X-Ray Software", "Powered MRI Software",
        "Next-Gen powered Coronary Imaging", "Six Aussie startups that",
    }
    blocked_terms = {
        "certified", "tool", "figure", "factors", "physiotherapist", "gpt-powered", "study",
        "trial", "programme", "program", "powered", "automating", "diagnostic", "next-gen",
        "x-ray", "software",
    }
    if company in blocked or company.lower() in blocked_terms:
        return False
    if any(word.lower() in blocked_terms for word in words):
        return False
    if words[-1].lower() in {"to", "for", "with", "and"}:
        return False
    return bool(re.search(r"[A-Za-z]", company))

def clean_page_candidate(text: str) -> str:
    candidate = clean_text(text)
    category_prefix = r"^(Acquired Core|Exited Core|IPO Core|MD Start|Capital|Core|Crossover|Digital Medicine|Industrial Biotech|Biovelocita)(?=[A-Z\s])\s*"
    previous = None
    while previous != candidate:
        previous = candidate
        candidate = re.sub(category_prefix, "", candidate)
    candidate = re.sub(r"\s+(Inc\.?|Ltd\.?|Limited|LLC|GmbH|AG|Corp\.?|Corporation|PLC)\b\.?", "", candidate, flags=re.I)
    candidate = candidate.strip(" :-,.;|")
    return re.sub(r"\s+", " ", candidate)

def is_plausible_page_candidate(candidate: str) -> bool:
    candidate = clean_page_candidate(candidate)
    if not is_plausible_company_name(candidate):
        return False
    lower = candidate.lower()
    blocked = {
        "about", "contact", "team", "news", "events", "portfolio", "companies", "apply", "program",
        "programs", "search", "login", "register", "privacy", "terms", "careers", "jobs", "blog",
        "resources", "learn more", "read more", "view all", "home", "menu", "investors", "partners",
        "speakers", "sponsors", "exhibitors", "agenda", "tickets", "subscribe", "download", "more",
        "skip to search", "skip to topics menu", "skip to common links", "follow fda", "en español",
        "food", "drugs", "medical devices", "radiation-emitting products", "vaccines, blood & biologics",
        "animal & veterinary", "cosmetics", "tobacco products", "fda home", "databases", "help",
        "product code", "quick search", "clear form", "de novo", "cfr title 21", "about us",
        "at a glance", "budget", "cms", "healthcare", "exhibiting at rsna", "eic portfolios",
        "linkedIn(opens in new window)", "linkedin-in", "donate",
    }
    if lower in blocked:
        return False
    if any(marker in lower for marker in ["@", "http", "cookie", "copyright", "javascript", "privacy policy", "linkedin", ", md", "sc.d", "mph"]):
        return False
    if re.search(r"\b(read|learn|view|see|contact|apply|register|download|submit)\b", lower):
        return False
    source_words = {
        "company", "companies", "cohort", "accelerator", "exhibitor", "exhibitors", "sponsor",
        "sponsors", "sponsorship", "portfolio", "dashboard", "application", "portal", "funding",
        "grant", "grants", "challenge", "challenges", "opportunities", "programme", "program",
        "resources", "directory", "profile", "presentation", "presentations", "videos", "news",
        "linkedin", "attending", "become", "interested", "planning", "partnership", "manager",
        "services", "material", "schedule", "agenda", "report", "committee", "council",
        "core", "acquired", "exited", "ipo", "bas", "budget", "cms", "host", "join",
        "log", "logistics", "manage", "investments", "international", "healthcare",
        "horizon", "advice", "contacts", "events", "dinner", "offer", "traffic",
    }
    if any(word.lower().strip("&") in source_words for word in candidate.split()):
        return False
    first_names = {
        "adaeze", "andrew", "anita", "brooke", "charlie", "dave", "david", "isaac",
        "jannine", "jeremy", "joe", "julius", "justin", "kate", "katherine", "matt",
        "matthew", "mike", "navin", "otto", "sam", "siva", "sylvia",
    }
    if len(candidate.split()) >= 2 and candidate.split()[0].lower().strip(",") in first_names:
        return False
    if lower.endswith((" us", " your award", " your offer")):
        return False
    return True

def is_relevant_candidate_link(source: Source, link_text: str, href: str) -> bool:
    lower_href = href.lower()
    if lower_href.startswith(("javascript:", "mailto:", "tel:")) or "#" in lower_href:
        return False
    negative_href_terms = [
        "team", "people", "staff", "advisor", "board", "speaker", "agenda", "event", "news",
        "blog", "login", "application", "apply", "contact", "about", "resource", "service",
    ]
    if any(term in lower_href for term in negative_href_terms):
        return False
    if source.source_type in {"Regulatory database", "Jobs"}:
        return False
    path_terms = {
        "Accelerator": ["compan", "startup", "cohort", "portfolio", "accelerator", "alumni"],
        "Conference": ["exhibitor", "sponsor", "startup", "compan", "showcase"],
        "VC portfolio": ["portfolio", "compan", "investment"],
        "Grant/funding": ["project", "award", "funding", "portfolio", "compan", "grant"],
        "University/spinout": ["spin", "startup", "start-up", "venture", "compan", "portfolio", "commercial"],
    }
    terms = path_terms.get(source.source_type, [])
    if terms and not any(term in lower_href for term in terms):
        return False
    return is_plausible_page_candidate(link_text)

def infer_page_product_type(source: Source, context: str) -> str:
    text = f"{source.notes} {context}".lower()
    if "samd" in text:
        return "SaMD / health software"
    if "medical device" in text or "medtech" in text:
        return "Medical device / medtech"
    if "diagnostic" in text or "imaging" in text:
        return "Diagnostics / imaging"
    if "ai" in text:
        return "AI health / medtech"
    if "digital health" in text:
        return "Digital health"
    return source.source_type

def infer_yc_product_type(context: str) -> str:
    text = context.lower()
    if "medical device" in text or "medtech" in text:
        return "Medical device / medtech"
    if "diagnostic" in text or "imaging" in text or "radiology" in text:
        return "Diagnostics / imaging"
    if "clinic" in text or "provider" in text or "healthcare it" in text:
        return "Healthcare operations / IT"
    if "health insurance" in text or "insurance" in text:
        return "Health insurance / payer"
    if "therapeutic" in text or "biotech" in text or "gene therapy" in text or "drug" in text:
        return "Biotech / therapeutics"
    if "ai" in text or "artificial intelligence" in text:
        return "AI health"
    if "healthcare" in text or "digital health" in text:
        return "Digital health"
    return "Healthcare startup"

def source_type_trigger_event(source: Source, company: str) -> tuple[str, str] | None:
    trigger_type = SOURCE_TRIGGER_TYPES.get(source.source_type)
    if not trigger_type:
        return None
    if source.source_type == "Regulatory database":
        return trigger_type, f"{company} appeared on regulatory source '{source.name}'."
    if source.source_type == "Grant/funding":
        return trigger_type, f"{company} appeared on grant/funding source '{source.name}'."
    if source.source_type == "VC portfolio":
        return trigger_type, f"{company} appeared on investor portfolio source '{source.name}'."
    if source.source_type == "Jobs":
        return trigger_type, f"{company} appeared on jobs/careers signal source '{source.name}'."
    if source.source_type == "Accelerator":
        return trigger_type, f"{company} appeared on accelerator/cohort source '{source.name}'."
    if source.source_type == "Conference":
        return trigger_type, f"{company} appeared on conference/exhibitor source '{source.name}'."
    if source.source_type == "University/spinout":
        return trigger_type, f"{company} appeared on university spinout/startup source '{source.name}'."
    return None

