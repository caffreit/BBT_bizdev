from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date
from html.parser import HTMLParser
from http.client import InvalidURL
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

import requests
from requests import Response
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import RequestException, SSLError, Timeout


MODEL = "openai/gpt-5.6-luna"
REASONING_EFFORT = "medium"
ENRICHMENT_VERSION = "source_attribution_v4_resilient_web"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
UNKNOWN = "Unknown"
MISSING = {"", "n/a", "na", "none", "null", "unknown", "-"}
PERSONAL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "live.com", "icloud.com", "me.com", "aol.com", "msn.com", "protonmail.com",
    "proton.me", "gmx.com", "mail.com",
}

COMPANY_TYPES = ["Startup", "University spinout", "Scaleup", "Mid-market", "Enterprise", "Academic/non-commercial", "Other", UNKNOWN]
EMPLOYEE_BANDS = ["1–10", "11–50", "51–200", "201–1,000", "1,001–5,000", "5,001+", UNKNOWN]
PRODUCT_PROFILES = ["Physical medical device", "Connected device", "SaMD/digital health", "Diagnostic/IVD", "AI-enabled health", "Biotech/pharma", "Non-regulated/wellness", "Other", UNKNOWN]
MATURITY_STAGES = ["Research/spinout", "Prototype/preclinical", "Clinical/validation", "Regulatory", "Commercial", "Scaling", UNKNOWN]
SERVICE_FITS = ["Product engineering", "Software development", "V&V", "QA/QMS", "Regulatory support", "IEC 62304", "ISO 13485", "Cybersecurity", "AI implementation"]
REGULATORY_SIGNALS = ["FDA clearance/approval", "510(k)", "De Novo", "CE mark", "ISO 13485", "IEC 62304", "Clinical study/validation", "QMS/quality system", "Cybersecurity requirement", "Regulatory pathway stated"]
CONTACT_FUNCTIONS = ["Founder/executive", "R&D/engineering/product", "QA/regulatory", "Clinical/medical", "Operations/manufacturing", "Commercial", "HR", "Academic", "Other"]


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def missing(value: object) -> bool:
    return clean(value).lower() in MISSING


def normalize_email(value: object) -> str:
    return clean(value).lower()


def email_domain(email: str) -> str:
    if email.count("@") != 1:
        return ""
    domain = email.rsplit("@", 1)[1].strip(" .").lower()
    return domain if re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain) else ""


def company_slug(value: str) -> str:
    value = clean(value).lower().replace("&", " and ")
    value = re.sub(r"\b(incorporated|inc|limited|ltd|llc|plc|corp(?:oration)?|company|co|group)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", "", value)


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha1(value.encode('utf-8')).hexdigest()[:12]}"


def domain_label(domain: str) -> str:
    stem = domain.lower().removeprefix("www.").split(".")[0]
    stem = re.sub(r"[-_]", " ", stem)
    return " ".join(word.capitalize() for word in stem.split())


def title_bucket(title: str) -> tuple[str, str, str]:
    text = clean(title).lower()
    if not text or text in MISSING:
        return "Other", UNKNOWN, "Unknown role"
    if re.search(r"founder|co-founder|chief executive|\bceo\b|president|chair(?:man|woman)?|owner|managing director", text):
        function = "Founder/executive"
    elif re.search(r"quality|regulatory|compliance|validation|design assurance|qms", text):
        function = "QA/regulatory"
    elif re.search(r"r&d|research and development|engineer|engineering|product|technology|technical|\bcto\b|software|development", text):
        function = "R&D/engineering/product"
    elif re.search(r"clinical|medical|physician|doctor|surgeon|nurse|chief scientific|scientist", text):
        function = "Clinical/medical"
    elif re.search(r"operations|manufactur|supply|procurement|programme|program|project", text):
        function = "Operations/manufacturing"
    elif re.search(r"sales|marketing|commercial|business development|account|partnership", text):
        function = "Commercial"
    elif re.search(r"human resources|\bhr\b|talent|people", text):
        function = "HR"
    elif re.search(r"professor|lecturer|academic|student|postdoc|researcher", text):
        function = "Academic"
    else:
        function = "Other"

    if re.search(r"chief|\bc[a-z]o\b|founder|president|chair|owner|partner", text):
        seniority = "Executive"
    elif re.search(r"vice president|\bvp\b|head of|director", text):
        seniority = "Director/VP"
    elif re.search(r"manager|lead|principal", text):
        seniority = "Manager/lead"
    elif re.search(r"intern|student|assistant|associate|specialist|engineer|scientist", text):
        seniority = "Individual contributor"
    else:
        seniority = UNKNOWN

    buying_role = {
        "Founder/executive": "Economic buyer / sponsor",
        "QA/regulatory": "Technical buyer / influencer",
        "R&D/engineering/product": "Technical buyer / delivery owner",
        "Clinical/medical": "Clinical influencer",
        "Operations/manufacturing": "Operational buyer / influencer",
        "Commercial": "Commercial influencer",
        "HR": "Low-priority contact",
        "Academic": "Spinout / research influencer",
        "Other": "Role requires review",
    }[function]
    return function, seniority, buying_role


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._anchor: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        if tag == "a":
            self._href = dict(attrs).get("href", "")
            self._anchor = []

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        if tag == "a" and self._href:
            self.links.append((self._href, clean(" ".join(self._anchor))))
            self._href = ""
            self._anchor = []

    def handle_data(self, data):
        if self._skip:
            return
        self.text.append(data)
        if self._href:
            self._anchor.append(data)


def normalize_http_url(url: str) -> str:
    """Return an absolute HTTP(S) URL safe for urllib, or an empty string."""
    try:
        parsed = urlparse(html.unescape(url).strip())
    except (TypeError, ValueError):
        return ""
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    return urlunparse(parsed._replace(
        path=quote(parsed.path, safe="/%:@!$&'()*+,;=-._~"),
        params=quote(parsed.params, safe="%:@!$&'()*+,;=-._~"),
        query=quote(parsed.query, safe="=&?/:@!$'()*+,;%-._~"),
        fragment="",
    ))


@dataclass
class WebsiteFetch:
    text: str = ""
    links: list[tuple[str, str]] | None = None
    final_url: str = ""
    state: str = "unavailable"
    detail: str = ""

    def __post_init__(self):
        if self.links is None:
            self.links = []


def _response_to_fetch(response: Response) -> WebsiteFetch:
    final_url = normalize_http_url(response.url)
    status = int(response.status_code)
    if status in {401, 403, 407, 429}:
        return WebsiteFetch(final_url=final_url, state="blocked", detail=f"HTTP {status}")
    if status >= 400:
        state = "unavailable" if status in {404, 410, 451} else "transient"
        return WebsiteFetch(final_url=final_url, state=state, detail=f"HTTP {status}")
    raw_bytes = response.content[:750_000]
    encoding = response.encoding or response.apparent_encoding or "utf-8"
    raw = raw_bytes.decode(encoding, "ignore")
    parser = PageParser()
    try:
        parser.feed(raw)
    except Exception:
        pass
    page_text = clean(html.unescape(" ".join(parser.text)))[:30_000]
    if not page_text:
        content_type = clean(response.headers.get("Content-Type", "response"))
        page_text = f"[Website responded successfully: HTTP {status}; {content_type}]"
    links: list[tuple[str, str]] = []
    for href, anchor in parser.links:
        absolute = normalize_http_url(urljoin(final_url, html.unescape(href).strip()))
        if not absolute:
            continue
        if urlparse(absolute).netloc.lower().removeprefix("www.") != urlparse(final_url).netloc.lower().removeprefix("www."):
            continue
        links.append((absolute, anchor))
    return WebsiteFetch(page_text, links, final_url, "available", f"HTTP {status}")


def fetch_page_detail(url: str, timeout: int = 20) -> WebsiteFetch:
    url = normalize_http_url(url)
    if not url:
        return WebsiteFetch(detail="Invalid URL")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    verify = True
    for attempt in range(2):
        try:
            response = requests.get(url, headers=headers, timeout=(min(10, timeout), timeout), allow_redirects=True, verify=verify)
            return _response_to_fetch(response)
        except SSLError as exc:
            if verify:
                verify = False
                continue
            return WebsiteFetch(state="blocked", detail=f"TLS error: {clean(exc)[:160]}")
        except Timeout as exc:
            if attempt == 0:
                time.sleep(0.25)
                continue
            return WebsiteFetch(state="transient", detail=f"Timeout: {clean(exc)[:160]}")
        except RequestsConnectionError as exc:
            return WebsiteFetch(state="unavailable", detail=f"Connection error: {clean(exc)[:160]}")
        except RequestException as exc:
            return WebsiteFetch(state="transient", detail=f"Request error: {clean(exc)[:160]}")
    return WebsiteFetch(state="transient", detail="Request failed")


def fetch_page(url: str, timeout: int = 20) -> tuple[str, list[tuple[str, str]], str]:
    result = fetch_page_detail(url, timeout)
    return result.text, list(result.links or []), result.final_url


def fetch_website(domain: str, timeout: int = 20) -> WebsiteFetch:
    domain = clean(domain).lower().removeprefix("www.")
    candidates = [f"https://{domain}", f"https://www.{domain}", f"http://{domain}", f"http://www.{domain}"]
    fallback: WebsiteFetch | None = None
    for candidate in candidates:
        result = fetch_page_detail(candidate, timeout)
        if result.state == "available":
            return result
        if fallback is None or (fallback.state == "unavailable" and result.state in {"blocked", "transient"}):
            fallback = result
    return fallback or WebsiteFetch(detail="No URL variant responded")


def score_internal_link(url: str, anchor: str) -> tuple[int, str]:
    text = clean(f"{anchor} {urlparse(url).path.replace('-', ' ').replace('_', ' ')}").lower()
    if re.search(r"\b(privacy|terms|cookie|legal|login|sign in|contact|careers?|jobs?|investors?|events?|blog|news|press|media)\b", text):
        return -1, "Excluded"
    categories = [
        ("Regulatory/quality", 100, r"\b(regulatory|quality|compliance|certifications?|iso 13485|fda|medical affairs)\b"),
        ("Product/technology", 80, r"\b(products?|solutions?|technology|platform|devices?|software|what we do)\b"),
        ("About/company", 60, r"\b(about|company|who we are|our story|mission)\b"),
    ]
    for category, score, pattern in categories:
        if re.search(pattern, text):
            depth_penalty = max(0, urlparse(url).path.strip("/").count("/") - 1) * 5
            return score - depth_penalty, category
    return 0, "Other"


def select_internal_pages(links: list[tuple[str, str]], limit: int = 3) -> list[dict[str, str | int]]:
    ranked = []
    seen = set()
    for url, anchor in links:
        key = url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        score, category = score_internal_link(url, anchor)
        if score > 0:
            ranked.append({"url": url, "anchor": clean(anchor), "category": category, "score": score})
    ranked.sort(key=lambda item: (-int(item["score"]), str(item["url"])))
    selected = []
    used_categories = set()
    for item in ranked:
        if item["category"] in used_categories:
            continue
        selected.append(item)
        used_categories.add(item["category"])
        if len(selected) >= limit:
            return selected
    for item in ranked:
        if item not in selected:
            selected.append(item)
            if len(selected) >= limit:
                break
    return selected


def score_news_item(company: str, title: str, description: str) -> int:
    company_norm = clean(re.sub(r"[^a-z0-9]+", " ", company.lower()))
    text = clean(re.sub(r"[^a-z0-9]+", " ", f"{title} {description}".lower()))
    if len(company_norm) < 4 or company_norm not in text:
        return -1
    score = 60 if company_norm in clean(re.sub(r"[^a-z0-9]+", " ", title.lower())) else 35
    signals = [
        (30, r"\b(fda|510 k|de novo|ce mark|regulatory|approval|clearance)\b"),
        (25, r"\b(funding|raises|raised|series [a-f]|seed|grant|investment|acquisition)\b"),
        (20, r"\b(launch|clinical trial|clinical study|validation|partnership)\b"),
        (15, r"\b(product|platform|device|software|diagnostic|medical|health)\b"),
    ]
    for points, pattern in signals:
        if re.search(pattern, text):
            score += points
    return score


def parse_google_news(company: str, raw: str, limit: int = 5) -> list[dict[str, str | int]]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    ranked = []
    for index, item in enumerate(root.findall(".//item")):
        title = clean(html.unescape(item.findtext("title") or ""))
        description = clean(re.sub(r"<[^>]+>", " ", html.unescape(item.findtext("description") or "")))
        url = clean(item.findtext("link") or "")
        source = clean(item.findtext("source") or "")
        published_at = clean(item.findtext("pubDate") or "")
        score = score_news_item(company, title, description)
        if score >= 0 and url:
            ranked.append({"title": title, "description": description, "url": url, "source": source, "published_at": published_at, "score": score, "feed_order": index})
    ranked.sort(key=lambda item: (-int(item["score"]), int(item["feed_order"])))
    return ranked[:limit]


def google_news(company: str) -> tuple[list[dict[str, str | int]], str]:
    from urllib.parse import quote
    url = f"https://news.google.com/rss/search?q={quote(chr(34) + company + chr(34))}&hl=en-IE&gl=IE&ceid=IE:en"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        raw = urlopen(req, timeout=12).read(500_000).decode("utf-8", "ignore")
    except (OSError, HTTPError, URLError) as exc:
        return [], str(exc)[:250]
    return parse_google_news(company, raw), ""


def classify_website_status(domain: str, page_text: str, final_url: str, fetch_state: str = "") -> tuple[str, str]:
    source_host = domain.lower().removeprefix("www.")
    final_host = urlparse(final_url).netloc.lower().removeprefix("www.") if final_url else ""
    same_site = bool(final_host) and (final_host == source_host or final_host.endswith("." + source_host) or source_host.endswith("." + final_host))
    if final_host and not same_site:
        return "External redirect", final_url
    if fetch_state in {"blocked", "transient"}:
        return "Unverified/Blocked", final_url
    if not page_text or not final_url:
        return "Unavailable", ""
    return "Available", ""


def normalize_existing_statuses(input_json: Path, output_json: Path) -> dict:
    payload = json.loads(input_json.read_text(encoding="utf-8"))
    original_flagged = int(payload["stats"].get("website_recovered", 0)) + int(payload["stats"].get("website_failures", 0)) + int(payload["stats"].get("website_unverified_or_blocked", 0))
    for row in payload["companies"]:
        if row.get("website_status") != "Unverified/Blocked" or not row.get("homepage_url"):
            continue
        status, redirect = classify_website_status(row["domain"], "", row["homepage_url"], "blocked")
        if status != "External redirect":
            continue
        row["website_status"] = status
        row["redirect_target"] = redirect
        errors = [item.strip() for item in row.get("errors", "").split(";") if item.strip() and not item.strip().startswith("Website unverified or blocked")]
        errors.append("Website redirected to different domain")
        row["errors"] = "; ".join(dict.fromkeys(errors))
    stats = payload["stats"]
    stats["website_failures"] = sum(row["website_status"] == "Unavailable" for row in payload["companies"])
    stats["website_unverified_or_blocked"] = sum(row["website_status"] == "Unverified/Blocked" for row in payload["companies"])
    stats["website_recovered"] = original_flagged - int(stats["website_failures"]) - int(stats["website_unverified_or_blocked"])
    prior_review = {row["Company ID"]: row for row in payload.get("review_queue", [])}
    payload["review_queue"] = [_review_row(row, prior_review.get(row["company_id"])) for row in payload["companies"]]
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def extract_employee_band(text: str) -> str:
    matches = []
    for pattern in [
        r"(?:over|more than|approximately|around|about)\s+([\d,]{2,})\s+employees",
        r"([\d,]{2,})\+?\s+employees",
        r"(?:employs?|employing|workforce of|team of)\s+(?:over |more than |approximately |around |about )?([\d,]{2,})",
        r"([\d,]{2,})\+?\s+(?:people|colleagues|team members)",
    ]:
        for value in re.findall(pattern, text, re.I):
            try:
                matches.append(int(value.replace(",", "")))
            except ValueError:
                pass
    if not matches:
        return UNKNOWN
    count = max(matches)
    if count <= 10: return "1–10"
    if count <= 50: return "11–50"
    if count <= 200: return "51–200"
    if count <= 1000: return "201–1,000"
    if count <= 5000: return "1,001–5,000"
    return "5,001+"


def rules_classify(text: str, domain: str) -> dict:
    t = text.lower()
    health_context = bool(re.search(r"\b(health|healthcare|medical|clinical|patient|hospital|disease|therapy|therapeutic|pharma|biotech|laborator(?:y|ies)|surgical)\b", t))
    employee_band = extract_employee_band(text)
    if re.search(r"university|college|hospital|health service|research institute", t) and domain.endswith((".edu", ".ac.uk", ".ac.ie")):
        company_type = "Academic/non-commercial"
    elif re.search(r"spin[- ]?out|spun out of", t):
        company_type = "University spinout"
    elif re.search(r"\b(startup|start-up|early-stage company)\b", t):
        company_type = "Startup"
    elif re.search(r"\b(scaleup|scale-up|high-growth company)\b", t):
        company_type = "Scaleup"
    elif employee_band in {"5,001+", "1,001–5,000"}:
        company_type = "Enterprise"
    elif employee_band == "201–1,000":
        company_type = "Mid-market"
    else:
        company_type = UNKNOWN

    if health_context and re.search(r"\b(ai|artificial intelligence|machine learning|deep learning)\b", t):
        product = "AI-enabled health"
    elif re.search(r"\b(ivd|in vitro diagnostic)\b", t) or (health_context and re.search(r"\b(diagnostic|diagnostics|imaging)\b", t)):
        product = "Diagnostic/IVD"
    elif re.search(r"\b(samd|software as a medical device|digital health|telehealth|health platform|clinical software)\b", t):
        product = "SaMD/digital health"
    elif health_context and re.search(r"\b(connected device|wearable|remote monitoring|sensor)\b", t):
        product = "Connected device"
    elif re.search(r"\b(implant|medical device|surgical device|medical technology|medtech)\b", t):
        product = "Physical medical device"
    elif re.search(r"\b(biotech|biopharma|pharmaceutical|therapeutic|drug discovery)\b", t):
        product = "Biotech/pharma"
    elif re.search(r"\b(wellness|wellbeing|fitness)\b", t):
        product = "Non-regulated/wellness"
    else:
        product = UNKNOWN

    if re.search(r"\b(series [b-f]|scaling|scale globally|rapid growth|expansion)\b", t):
        maturity = "Scaling"
    elif re.search(r"\b(commercially available|customers worldwide|marketed|launched|on the market)\b", t):
        maturity = "Commercial"
    elif re.search(r"\b(fda cleared|fda approved|ce marked|regulatory approval|510\(k\)|de novo)\b", t):
        maturity = "Regulatory"
    elif re.search(r"\b(clinical trial|clinical validation|clinical study|validation study)\b", t):
        maturity = "Clinical/validation"
    elif re.search(r"\b(prototype|preclinical|proof of concept|under development)\b", t):
        maturity = "Prototype/preclinical"
    elif company_type == "University spinout" or re.search(r"\bresearch-stage\b", t):
        maturity = "Research/spinout"
    else:
        maturity = UNKNOWN

    services: list[str] = []
    if product in {"Physical medical device", "Connected device", "Diagnostic/IVD"}: services += ["Product engineering", "V&V", "QA/QMS", "Regulatory support", "ISO 13485"]
    if product in {"SaMD/digital health", "Connected device", "AI-enabled health"}: services += ["Software development", "V&V", "IEC 62304", "Cybersecurity", "Regulatory support"]
    if product == "AI-enabled health": services += ["AI implementation"]
    services = [service for service in SERVICE_FITS if service in services]

    regulatory = []
    for label, pattern in [("FDA clearance/approval", r"\bfda\b"), ("510(k)", r"510\(k\)"), ("De Novo", r"\bde novo\b"), ("CE mark", r"\bce mark(?:ed)?\b"), ("ISO 13485", r"\biso\s*13485\b"), ("IEC 62304", r"\biec\s*62304\b"), ("Clinical study/validation", r"\bclinical (?:study|trial|validation)\b"), ("QMS/quality system", r"\b(?:qms|quality management system)\b"), ("Cybersecurity requirement", r"\b(?:cybersecurity|cyber security)\b")]:
        if re.search(pattern, t): regulatory.append(label)
    non_unknown = sum(value != UNKNOWN for value in (company_type, employee_band, product, maturity))
    confidence = min(0.9, 0.35 + non_unknown * 0.12 + (0.08 if regulatory else 0))
    return {"company_type": company_type, "employee_band": employee_band, "product_profile": product, "maturity_stage": maturity, "services": services, "regulatory_signals": regulatory, "confidence": round(confidence, 2)}


def openrouter_classify(context: dict, api_key: str, model: str = MODEL, reasoning_effort: str = REASONING_EFFORT) -> tuple[dict | None, dict, str]:
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "company_type": {"type": "string", "enum": COMPANY_TYPES},
            "employee_band": {"type": "string", "enum": EMPLOYEE_BANDS},
            "product_profile": {"type": "string", "enum": PRODUCT_PROFILES},
            "maturity_stage": {"type": "string", "enum": MATURITY_STAGES},
            "services": {"type": "array", "items": {"type": "string", "enum": SERVICE_FITS}},
            "regulatory_signals": {"type": "array", "items": {"type": "string", "enum": REGULATORY_SIGNALS}},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence_summary": {"type": "string"},
            "evidence_urls": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["company_type", "employee_band", "product_profile", "maturity_stage", "services", "regulatory_signals", "confidence", "evidence_summary", "evidence_urls"],
    }
    prompt = (
        "Classify this company only from the supplied public evidence. Use Unknown whenever the evidence does not support a value. "
        "Do not infer an exact medical-device class. Recommend services only when the product and evidence make them relevant. "
        "Return evidence_urls using only exact URLs supplied in the evidence records; include only URLs that materially support the classification.\n\n" +
        json.dumps(context, ensure_ascii=False)
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "reasoning": {"effort": reasoning_effort, "exclude": True},
        "response_format": {"type": "json_schema", "json_schema": {"name": "company_enrichment", "strict": True, "schema": schema}},
        "provider": {"require_parameters": True},
    }
    req = Request(OPENROUTER_URL, data=json.dumps(payload).encode(), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "User-Agent": USER_AGENT})
    try:
        raw = json.loads(urlopen(req, timeout=60).read().decode("utf-8", "ignore"))
        result = json.loads(raw["choices"][0]["message"]["content"])
        usage = raw.get("usage", {})
        return result, usage, ""
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "ignore")[:500]
        except Exception:
            detail = ""
        return None, {}, f"HTTP {exc.code}: {detail or exc.reason}"
    except Exception as exc:
        return None, {}, str(exc)[:300]


@dataclass
class CompanySeed:
    company_id: str
    domain: str
    canonical_company: str
    company_resolution: str
    resolution_confidence: float
    contact_count: int
    missing_company_count: int
    company_conflict: str


def load_contacts(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    counts = Counter(normalize_email(row.get("Email")) for row in rows)
    output = []
    for index, row in enumerate(rows, 1):
        email = normalize_email(row.get("Email"))
        domain = email_domain(email)
        record = dict(row)
        record.update({
            "Record ID": stable_id("contact", f"{index}|{email}"),
            "Normalized Email": email,
            "Email Domain": domain,
            "Email Valid": "Yes" if domain else "No",
            "Duplicate Email": "Yes" if email and counts[email] > 1 else "No",
            "Original Company Missing": "Yes" if missing(row.get("Company")) else "No",
        })
        output.append(record)
    return output


def build_company_seeds(contacts: list[dict]) -> tuple[list[CompanySeed], dict[str, CompanySeed]]:
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for row in contacts:
        if row["Email Domain"]:
            by_domain[row["Email Domain"]].append(row)
    seeds = []
    for domain, rows in by_domain.items():
        names = [clean(row.get("Company")) for row in rows if not missing(row.get("Company"))]
        normalized = defaultdict(list)
        for name in names:
            normalized[company_slug(name)].append(name)
        ranked = sorted(normalized.items(), key=lambda item: (-len(item[1]), item[0]))
        conflict = ""
        if ranked:
            winner_slug, variants = ranked[0]
            canonical = Counter(variants).most_common(1)[0][0]
            runner_count = len(ranked[1][1]) if len(ranked) > 1 else 0
            if runner_count and runner_count >= len(variants) * 0.5:
                conflict = "Conflicting company names for domain: " + " | ".join(Counter(names).most_common(4)[i][0] for i in range(min(4, len(Counter(names)))))
            method = "Existing company; domain majority"
            confidence = 0.95 if not conflict else 0.55
        elif domain in PERSONAL_DOMAINS:
            canonical, method, confidence = UNKNOWN, "Personal email; not inferred", 0.0
        else:
            canonical, method, confidence = domain_label(domain), "Corporate domain label", 0.55
        seed = CompanySeed(stable_id("company", domain), domain, canonical, method, confidence, len(rows), sum(row["Original Company Missing"] == "Yes" for row in rows), conflict)
        seeds.append(seed)
    return seeds, {seed.domain: seed for seed in seeds}


def select_pilot(seeds: list[CompanySeed], size: int) -> list[CompanySeed]:
    eligible = [seed for seed in seeds if seed.domain not in PERSONAL_DOMAINS and seed.canonical_company != UNKNOWN]
    buckets = [
        sorted([s for s in eligible if s.missing_company_count], key=lambda s: (-s.missing_company_count, s.domain)),
        sorted([s for s in eligible if s.contact_count >= 3], key=lambda s: (-s.contact_count, s.domain)),
        sorted([s for s in eligible if s.company_conflict], key=lambda s: s.domain),
        sorted(eligible, key=lambda s: hashlib.sha1(s.domain.encode()).hexdigest()),
    ]
    chosen: list[CompanySeed] = []
    seen = set()
    targets = [min(35, size), min(40, size), min(15, size), size]
    for bucket, target in zip(buckets, targets):
        for seed in bucket:
            if seed.domain in seen:
                continue
            chosen.append(seed); seen.add(seed.domain)
            if len(chosen) >= target:
                break
    return chosen[:size]


def research_company(seed: CompanySeed, cache_dir: Path, api_key: str, model: str, reasoning_effort: str, force: bool = False) -> dict:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_mode = hashlib.sha1((f"{ENRICHMENT_VERSION}|{model}|{reasoning_effort}" if api_key else f"{ENRICHMENT_VERSION}|evidence-rules").encode()).hexdigest()[:8]
    cache_file = cache_dir / f"{seed.company_id}-{cache_mode}.json"
    if cache_file.exists() and not force:
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if not (api_key and cached.get("llm_error") and cached.get("llm_used") != "Yes"):
                return cached
        except (OSError, json.JSONDecodeError):
            pass
    started = time.time()
    website_fetch = fetch_website(seed.domain)
    homepage, homepage_links, final_url = website_fetch.text, list(website_fetch.links or []), website_fetch.final_url
    errors = []
    website_status, redirect_target = classify_website_status(seed.domain, homepage, final_url, website_fetch.state)
    if website_status == "Unavailable":
        errors.append("Website unavailable")
    elif website_status == "Unverified/Blocked":
        errors.append(f"Website unverified or blocked ({website_fetch.detail})")
    elif website_status == "External redirect":
        errors.append("Website redirected to different domain")
    selected_internal = select_internal_pages(homepage_links)
    internal_pages = []
    homepage_host = urlparse(final_url).netloc.lower().removeprefix("www.") if final_url else ""
    for selected in selected_internal:
        page_text, _, page_url = fetch_page(str(selected["url"]))
        page_host = urlparse(page_url).netloc.lower().removeprefix("www.") if page_url else ""
        if page_text and page_host and (page_host == homepage_host or page_host.endswith("." + homepage_host)):
            internal_pages.append({"url": page_url, "category": selected["category"], "text": clean(page_text[:8000]), "score": selected["score"]})
    news_items, news_error = google_news(seed.canonical_company)
    if news_error:
        errors.append("News search unavailable")
    website_evidence = clean(" ".join([homepage] + [str(page["text"]) for page in internal_pages]))[:40_000]
    news_evidence = clean(" ".join(f"{item['title']} {item['description']}" for item in news_items))[:12_000]
    evidence = clean(f"{website_evidence} {news_evidence}")[:50_000]
    # Public news search is retained as supporting context, but deterministic product
    # classification uses the company's own site to avoid namesake/news false positives.
    rules = rules_classify(website_evidence, seed.domain)
    method = "Evidence rules"
    llm_used = "No"
    usage = {}
    llm_error = ""
    evidence_summary = clean(website_evidence[:650])
    evidence_records = []
    if homepage and final_url:
        evidence_records.append({"source_type": "Homepage", "url": final_url, "text": clean(homepage[:12000])})
    evidence_records.extend({"source_type": str(page["category"]), "url": str(page["url"]), "text": str(page["text"])} for page in internal_pages)
    evidence_records.extend({"source_type": "Google News article", "url": str(item["url"]), "title": str(item["title"]), "publisher": str(item["source"]), "published_at": str(item["published_at"]), "text": clean(f"{item['title']} {item['description']}")} for item in news_items)
    evidence_urls = [str(record["url"]) for record in evidence_records]
    if api_key and evidence:
        result, usage, llm_error = openrouter_classify({"company": seed.canonical_company, "domain": seed.domain, "evidence": evidence_records}, api_key, model, reasoning_effort)
        if result:
            result["evidence_urls"] = [url for url in result.get("evidence_urls", []) if url in evidence_urls]
            result["services"] = list(dict.fromkeys(service for service in result.get("services", []) if service in SERVICE_FITS))
            result["regulatory_signals"] = list(dict.fromkeys(signal for signal in result.get("regulatory_signals", []) if signal in REGULATORY_SIGNALS))
            if result.get("employee_band") != UNKNOWN and extract_employee_band(evidence) == UNKNOWN:
                result["employee_band"] = UNKNOWN
            confidence_cap = 0.95
            if not homepage or "Website redirected to different domain" in errors:
                confidence_cap = 0.60
            elif len(result["evidence_urls"]) < 2:
                confidence_cap = 0.75
            result["confidence"] = min(float(result.get("confidence", 0)), confidence_cap)
            rules.update(result)
            method = "OpenRouter structured extraction"
            llm_used = "Yes"
            evidence_summary = clean(result.get("evidence_summary"))
        else:
            errors.append("LLM error")
    record = {
        **asdict(seed),
        "website": f"https://{seed.domain}",
        "website_status": website_status,
        "redirect_target": redirect_target,
        "homepage_url": final_url,
        "internal_page_urls": "; ".join(str(page["url"]) for page in internal_pages),
        "news_article_urls": "; ".join(str(item["url"]) for item in news_items),
        **rules,
        "services": "; ".join(rules.get("services", [])),
        "regulatory_signals": "; ".join(rules.get("regulatory_signals", [])),
        "evidence_summary": evidence_summary,
        "evidence_urls": "; ".join(rules.get("evidence_urls", [])),
        "source_urls": "; ".join(evidence_urls),
        "research_date": date.today().isoformat(),
        "method": method,
        "llm_used": llm_used,
        "model": model if llm_used == "Yes" else "Not used",
        "reasoning_effort": reasoning_effort if llm_used == "Yes" else "Not used",
        "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
        "estimated_cost_usd": round(float(usage.get("cost") or ((int(usage.get("prompt_tokens", 0) or 0) * 1.00 + int(usage.get("completion_tokens", 0) or 0) * 6.00) / 1_000_000)), 6) if model == "openai/gpt-5.6-luna" else 0.0,
        "errors": "; ".join(errors),
        "llm_error": llm_error,
        "runtime_seconds": round(time.time() - started, 2),
    }
    if "Website redirected to different domain" in errors:
        record["resolution_confidence"] = min(record["resolution_confidence"], 0.55)
    cache_file.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def contact_angle(function: str, services: str, maturity: str) -> tuple[str, str, str]:
    service_list = [item.strip() for item in services.split(";") if item.strip()]
    preferred = {
        "QA/regulatory": ["Regulatory support", "QA/QMS", "V&V", "ISO 13485", "IEC 62304"],
        "R&D/engineering/product": ["Product engineering", "Software development", "V&V", "Cybersecurity"],
        "Clinical/medical": ["V&V", "Regulatory support", "Product engineering"],
        "Operations/manufacturing": ["QA/QMS", "ISO 13485", "Product engineering"],
        "Founder/executive": SERVICE_FITS,
        "Academic": ["Product engineering", "Regulatory support", "V&V"],
        "Commercial": ["Regulatory support", "V&V"],
    }.get(function, SERVICE_FITS)
    primary = next((item for item in preferred if item in service_list), UNKNOWN)
    if primary == UNKNOWN:
        angle = "Insufficient evidence for tailored outreach"
    else:
        angle = f"Discuss {primary.lower()} support for the company’s {maturity.lower() if maturity != UNKNOWN else 'current'} product work"
    segment = f"{maturity} | {function} | {primary}"
    return primary, angle, segment


def build_payload(input_path: Path, output_json: Path, sample_size: int, cache_dir: Path, max_workers: int, model: str, reasoning_effort: str) -> dict:
    contacts = load_contacts(input_path)
    seeds, seed_by_domain = build_company_seeds(contacts)
    pilot = select_pilot(seeds, sample_size)
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip() or os.getenv("BBT_OPENROUTER_API_KEY", "").strip()
    companies = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(research_company, seed, cache_dir, api_key, model, reasoning_effort): seed for seed in pilot}
        for future in as_completed(futures):
            companies.append(future.result())
    companies.sort(key=lambda item: item["canonical_company"].lower())
    company_by_domain = {row["domain"]: row for row in companies}
    enriched_contacts = []
    for row in contacts:
        company = company_by_domain.get(row["Email Domain"])
        if not company:
            continue
        function, seniority, buying_role = title_bucket(row.get("Job Title", ""))
        primary, angle, segment = contact_angle(function, company["services"], company["maturity_stage"])
        enriched_contacts.append({
            "Record ID": row["Record ID"], "Company ID": company["company_id"], "First Name": clean(row.get("First Name")), "Last Name": clean(row.get("Last Name")),
            "Email": row["Normalized Email"], "Email Domain": row["Email Domain"], "Original Company": clean(row.get("Company")), "Resolved Company": company["canonical_company"],
            "Job Title": clean(row.get("Job Title")), "Contact Function": function, "Seniority": seniority, "Buying Role": buying_role,
            "Primary Service Relevance": primary, "Outreach Angle": angle, "Campaign Segment": segment, "Duplicate Email": row["Duplicate Email"],
        })
    review = []
    for company in companies:
        reasons = []
        if company["company_conflict"]: reasons.append(company["company_conflict"])
        if company["resolution_confidence"] < 0.8: reasons.append("Company identity needs confirmation")
        if company["confidence"] < 0.6: reasons.append("Low classification confidence")
        if company["product_profile"] == UNKNOWN: reasons.append("Product profile unknown")
        if company["company_type"] == UNKNOWN: reasons.append("Company type unknown")
        if company["employee_band"] == UNKNOWN: reasons.append("Employee band unknown")
        if company["errors"]: reasons.append(company["errors"])
        review.append({"Company ID": company["company_id"], "Company": company["canonical_company"], "Domain": company["domain"], "Review Status": "Pending manual validation", "Priority": "High" if company["resolution_confidence"] < 0.8 or company["product_profile"] == UNKNOWN else "Medium", "Review Reasons": "; ".join(reasons) or "Validate evidence and classifications", "Reviewer Notes": "", "Source URLs": company["source_urls"]})
    invalid_emails = sum(row["Email Valid"] == "No" for row in contacts)
    duplicate_rows = sum(row["Duplicate Email"] == "Yes" for row in contacts)
    stats = {
        "run_date": date.today().isoformat(), "source_rows": len(contacts), "unique_domains": len(seeds), "pilot_companies": len(companies), "pilot_contacts": len(enriched_contacts),
        "invalid_email_rows": invalid_emails, "duplicate_email_rows": duplicate_rows, "missing_company_rows": sum(row["Original Company Missing"] == "Yes" for row in contacts),
        "same_domain_recoverable_rows": sum(bool(row["Original Company Missing"] == "Yes" and seed_by_domain.get(row["Email Domain"]) and seed_by_domain[row["Email Domain"]].company_resolution.startswith("Existing")) for row in contacts),
        "llm_used_companies": sum(row["llm_used"] == "Yes" for row in companies), "model": model if api_key else "Not configured", "reasoning_effort": reasoning_effort if api_key else "Not configured", "estimated_cost_usd": round(sum(row["estimated_cost_usd"] for row in companies), 6),
        "unknown_company_type": sum(row["company_type"] == UNKNOWN for row in companies), "unknown_employee_band": sum(row["employee_band"] == UNKNOWN for row in companies),
        "unknown_product_profile": sum(row["product_profile"] == UNKNOWN for row in companies), "unknown_maturity": sum(row["maturity_stage"] == UNKNOWN for row in companies),
        "website_failures": sum("Website unavailable" in row["errors"] for row in companies), "manual_reviews_pending": len(review),
    }
    payload = {"stats": stats, "raw_contacts": contacts, "companies": companies, "contacts": enriched_contacts, "review_queue": review}
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def _seed_from_company(row: dict) -> CompanySeed:
    return CompanySeed(
        row["company_id"], row["domain"], row["canonical_company"], row["company_resolution"],
        float(row["resolution_confidence"]), int(row["contact_count"]), int(row["missing_company_count"]), row.get("company_conflict", ""),
    )


def _review_row(company: dict, prior: dict | None = None) -> dict:
    reasons = []
    if company["company_conflict"]: reasons.append(company["company_conflict"])
    if company["resolution_confidence"] < 0.8: reasons.append("Company identity needs confirmation")
    if company["confidence"] < 0.6: reasons.append("Low classification confidence")
    if company["product_profile"] == UNKNOWN: reasons.append("Product profile unknown")
    if company["company_type"] == UNKNOWN: reasons.append("Company type unknown")
    if company["employee_band"] == UNKNOWN: reasons.append("Employee band unknown")
    if company["errors"]: reasons.append(company["errors"])
    return {
        "Company ID": company["company_id"], "Company": company["canonical_company"], "Domain": company["domain"],
        "Review Status": (prior or {}).get("Review Status", "Pending manual validation"),
        "Priority": "High" if company["resolution_confidence"] < 0.8 or company["product_profile"] == UNKNOWN else "Medium",
        "Review Reasons": "; ".join(reasons) or "Validate evidence and classifications",
        "Reviewer Notes": (prior or {}).get("Reviewer Notes", ""), "Source URLs": company["source_urls"],
    }


def repair_existing_payload(input_json: Path, output_json: Path, cache_dir: Path, max_workers: int, model: str, reasoning_effort: str, reenrich: bool = True) -> dict:
    payload = json.loads(input_json.read_text(encoding="utf-8"))
    companies = payload["companies"]
    targets = [row for row in companies if row.get("website_status") == "Unavailable"]

    probes: dict[str, WebsiteFetch] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fetch_website, row["domain"]): row for row in targets}
        for future in as_completed(futures):
            row = futures[future]
            try:
                probes[row["company_id"]] = future.result()
            except Exception as exc:
                probes[row["company_id"]] = WebsiteFetch(state="transient", detail=f"Probe error: {clean(exc)[:160]}")

    recovered_ids = set()
    for row in targets:
        probe = probes[row["company_id"]]
        status, redirect = classify_website_status(row["domain"], probe.text, probe.final_url, probe.state)
        row["website_status"] = status
        row["redirect_target"] = redirect
        if probe.final_url:
            row["homepage_url"] = probe.final_url
        old_errors = [item.strip() for item in row.get("errors", "").split(";") if item.strip() and item.strip() != "Website unavailable"]
        if status == "Unavailable":
            old_errors.append("Website unavailable")
        elif status == "Unverified/Blocked":
            old_errors.append(f"Website unverified or blocked ({probe.detail})")
        else:
            recovered_ids.add(row["company_id"])
        row["errors"] = "; ".join(dict.fromkeys(old_errors))

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip() or os.getenv("BBT_OPENROUTER_API_KEY", "").strip()
    if recovered_ids and reenrich and not api_key:
        raise RuntimeError("An OpenRouter API key is required for selective re-enrichment of recovered websites")
    recovered_rows = [row for row in companies if row["company_id"] in recovered_ids] if reenrich else []
    replacements: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, 12)) as pool:
        futures = {
            pool.submit(research_company, _seed_from_company(row), cache_dir, api_key, model, reasoning_effort, True): row
            for row in recovered_rows
        }
        for future in as_completed(futures):
            original = futures[future]
            try:
                refreshed = future.result()
                # A transient second fetch must not undo a successful status probe.
                if refreshed["website_status"] in {"Available", "External redirect"}:
                    replacements[original["company_id"]] = refreshed
                else:
                    original["errors"] = "; ".join(filter(None, [original.get("errors", ""), "Selective re-enrichment fetch did not reproduce recovery"]))
            except Exception as exc:
                original["errors"] = "; ".join(filter(None, [original.get("errors", ""), f"Selective re-enrichment failed: {clean(exc)[:180]}"]))

    payload["companies"] = [replacements.get(row["company_id"], row) for row in companies]
    company_by_id = {row["company_id"]: row for row in payload["companies"]}
    for contact in payload["contacts"]:
        company = company_by_id.get(contact["Company ID"])
        if not company or company["company_id"] not in recovered_ids:
            continue
        primary, angle, segment = contact_angle(contact["Contact Function"], company["services"], company["maturity_stage"])
        contact["Primary Service Relevance"] = primary
        contact["Outreach Angle"] = angle
        contact["Campaign Segment"] = segment

    prior_review = {row["Company ID"]: row for row in payload.get("review_queue", [])}
    payload["review_queue"] = [_review_row(row, prior_review.get(row["company_id"])) for row in payload["companies"]]
    stats = payload["stats"]
    stats.update({
        "run_date": date.today().isoformat(),
        "website_failures": sum(row["website_status"] == "Unavailable" for row in payload["companies"]),
        "website_unverified_or_blocked": sum(row["website_status"] == "Unverified/Blocked" for row in payload["companies"]),
        "website_recovered": len(recovered_ids),
        "selectively_reenriched": len(replacements),
        "selective_llm_cost_usd": round(sum(float(row.get("estimated_cost_usd", 0)) for row in replacements.values()), 6),
        "llm_used_companies": sum(row.get("llm_used") == "Yes" for row in payload["companies"]),
        "estimated_cost_usd": round(sum(float(row.get("estimated_cost_usd", 0)) for row in payload["companies"]), 6),
        "unknown_company_type": sum(row["company_type"] == UNKNOWN for row in payload["companies"]),
        "unknown_employee_band": sum(row["employee_band"] == UNKNOWN for row in payload["companies"]),
        "unknown_product_profile": sum(row["product_profile"] == UNKNOWN for row in payload["companies"]),
        "unknown_maturity": sum(row["maturity_stage"] == UNKNOWN for row in payload["companies"]),
        "manual_reviews_pending": len(payload["review_queue"]),
    })
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def selective_reenrich_recovered(original_json: Path, repaired_json: Path, output_json: Path, cache_dir: Path, max_workers: int, model: str, reasoning_effort: str) -> dict:
    original = json.loads(original_json.read_text(encoding="utf-8"))
    payload = json.loads(repaired_json.read_text(encoding="utf-8"))
    originally_unavailable = {row["company_id"] for row in original["companies"] if row.get("website_status") == "Unavailable"}
    targets = [row for row in payload["companies"] if row["company_id"] in originally_unavailable and row.get("website_status") in {"Available", "External redirect"}]
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip() or os.getenv("BBT_OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("An OpenRouter API key is required for selective re-enrichment")

    replacements: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, 12)) as pool:
        futures = {
            pool.submit(research_company, _seed_from_company(row), cache_dir, api_key, model, reasoning_effort, True): row
            for row in targets
        }
        for future in as_completed(futures):
            prior = futures[future]
            try:
                refreshed = future.result()
                if refreshed["website_status"] in {"Available", "External redirect"} and refreshed.get("homepage_url"):
                    replacements[prior["company_id"]] = refreshed
                else:
                    prior["errors"] = "; ".join(filter(None, [prior.get("errors", ""), "Selective re-enrichment fetch did not reproduce recovery"]))
            except Exception as exc:
                prior["errors"] = "; ".join(filter(None, [prior.get("errors", ""), f"Selective re-enrichment failed: {clean(exc)[:180]}"]))

    payload["companies"] = [replacements.get(row["company_id"], row) for row in payload["companies"]]
    company_by_id = {row["company_id"]: row for row in payload["companies"]}
    for contact in payload["contacts"]:
        company = company_by_id.get(contact["Company ID"])
        if not company or company["company_id"] not in replacements:
            continue
        primary, angle, segment = contact_angle(contact["Contact Function"], company["services"], company["maturity_stage"])
        contact["Primary Service Relevance"] = primary
        contact["Outreach Angle"] = angle
        contact["Campaign Segment"] = segment

    prior_review = {row["Company ID"]: row for row in payload.get("review_queue", [])}
    payload["review_queue"] = [_review_row(row, prior_review.get(row["company_id"])) for row in payload["companies"]]
    stats = payload["stats"]
    stats.update({
        "run_date": date.today().isoformat(),
        "selective_reenrichment_targets": len(targets),
        "selectively_reenriched": len(replacements),
        "selective_llm_cost_usd": round(sum(float(row.get("estimated_cost_usd", 0)) for row in replacements.values()), 6),
        "website_failures": sum(row["website_status"] == "Unavailable" for row in payload["companies"]),
        "website_unverified_or_blocked": sum(row["website_status"] == "Unverified/Blocked" for row in payload["companies"]),
        "llm_used_companies": sum(row.get("llm_used") == "Yes" for row in payload["companies"]),
        "estimated_cost_usd": round(sum(float(row.get("estimated_cost_usd", 0)) for row in payload["companies"]), 6),
        "unknown_company_type": sum(row["company_type"] == UNKNOWN for row in payload["companies"]),
        "unknown_employee_band": sum(row["employee_band"] == UNKNOWN for row in payload["companies"]),
        "unknown_product_profile": sum(row["product_profile"] == UNKNOWN for row in payload["companies"]),
        "unknown_maturity": sum(row["maturity_stage"] == UNKNOWN for row in payload["companies"]),
    })
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Bluebridge subscriber enrichment pilot data")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--repair-existing", type=Path, help="Repair website statuses in an existing enrichment JSON and selectively re-enrich recovered companies")
    parser.add_argument("--normalize-existing-statuses", type=Path, help="Normalize already-probed redirect statuses without making network requests")
    parser.add_argument("--selective-reenrich", type=Path, help="Repaired JSON whose recovered websites should be selectively re-enriched")
    parser.add_argument("--original-json", type=Path, help="Original JSON used to identify records that were previously unavailable")
    parser.add_argument("--status-only", action="store_true", help="With --repair-existing, update website and redirect fields without sending evidence to the LLM")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--sample-size", type=int, default=150)
    parser.add_argument("--cache-dir", type=Path, default=Path(".subscriber_enrichment_cache"))
    parser.add_argument("--max-workers", type=int, default=12)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--reasoning-effort", choices=["none", "minimal", "low", "medium", "high", "xhigh", "max"], default=REASONING_EFFORT)
    parser.add_argument("--synthetic-smoke-test", action="store_true", help="Test OpenRouter with fictional company evidence only")
    args = parser.parse_args()
    if args.synthetic_smoke_test:
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip() or os.getenv("BBT_OPENROUTER_API_KEY", "").strip()
        if not api_key:
            parser.error("OPENROUTER_API_KEY is not configured")
        result, usage, error = openrouter_classify(
            {
                "company": "Fictional Acme Medical Systems",
                "domain": "fictional-acme.invalid",
                "evidence": [
                    {"source_type": "Homepage", "url": "https://fictional-acme.invalid/", "text": "Fictional Acme Medical Systems develops connected cardiac monitoring devices and medical-device software under an ISO 13485 quality system."},
                    {"source_type": "Regulatory/quality", "url": "https://fictional-acme.invalid/quality", "text": "Its fictional product team performs verification and validation and follows IEC 62304 for software lifecycle processes."},
                ],
            },
            api_key,
            args.model,
            args.reasoning_effort,
        )
        if error or not result:
            raise RuntimeError(error or "OpenRouter returned no result")
        print(json.dumps({"status": "ok", "model": args.model, "reasoning_effort": args.reasoning_effort, "classification": result, "usage": usage}, indent=2))
        return 0
    if args.normalize_existing_statuses:
        if not args.output_json:
            parser.error("--output-json is required with --normalize-existing-statuses")
        payload = normalize_existing_statuses(args.normalize_existing_statuses, args.output_json)
        print(json.dumps(payload["stats"], indent=2))
        return 0
    if args.selective_reenrich:
        if not args.original_json or not args.output_json:
            parser.error("--original-json and --output-json are required with --selective-reenrich")
        payload = selective_reenrich_recovered(args.original_json, args.selective_reenrich, args.output_json, args.cache_dir, args.max_workers, args.model, args.reasoning_effort)
        print(json.dumps(payload["stats"], indent=2))
        return 0
    if args.repair_existing:
        if not args.output_json:
            parser.error("--output-json is required with --repair-existing")
        payload = repair_existing_payload(args.repair_existing, args.output_json, args.cache_dir, args.max_workers, args.model, args.reasoning_effort, not args.status_only)
        print(json.dumps(payload["stats"], indent=2))
        return 0
    if not args.input or not args.output_json:
        parser.error("--input and --output-json are required unless --synthetic-smoke-test is used")
    payload = build_payload(args.input, args.output_json, args.sample_size, args.cache_dir, args.max_workers, args.model, args.reasoning_effort)
    print(json.dumps(payload["stats"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
