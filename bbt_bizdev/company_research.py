from __future__ import annotations

import re
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from .adapters.search import google_news_rss_url, parse_google_news_rss
from .http import fetch_raw_text
from .text import article_title_without_publisher, clean_text


FUNDING_TERMS = re.compile(
    r"\b(funding|funded|raises?|raised|series\s+[a-z]|seed|pre-seed|investment|invests?|grant|"
    r"acquisition|acquires?|acquired|partnership|partners?|revenue|\$\d|€\d|£\d)\b",
    re.I,
)
PEOPLE_TERMS = re.compile(r"\b(team|people|leadership|founders?|management|board|about)\b", re.I)
COMPANY_PAGE_TERMS = re.compile(r"\b(news|blog|press|media|insights|updates|about)\b", re.I)
COMMON_PATHS = (
    "/about",
    "/about-us",
    "/team",
    "/people",
    "/leadership",
    "/news",
    "/blog",
    "/press",
    "/media",
)


@dataclass(frozen=True)
class ResearchLink:
    title: str
    url: str
    source: str
    published_at: str = ""

    def to_dict(self) -> dict[str, str]:
        payload = {"title": self.title, "url": self.url, "source": self.source}
        if self.published_at:
            payload["publishedAt"] = self.published_at
        return payload


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.title_parts: list[str] = []
        self._href = ""
        self._text_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "a":
            self._href = attrs_dict.get("href", "")
            self._text_parts = []
        elif tag == "title":
            self._in_title = True

    def handle_data(self, data):
        if self._href:
            self._text_parts.append(data)
        if self._in_title:
            self.title_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            text = clean_text(" ".join(self._text_parts))
            self.links.append((self._href, text))
            self._href = ""
            self._text_parts = []
        elif tag == "title":
            self._in_title = False

    @property
    def title(self) -> str:
        return clean_text(" ".join(self.title_parts))


def normalize_website(website: str) -> str:
    website = website.strip()
    if not website:
        return ""
    if not re.match(r"https?://", website, re.I):
        website = "https://" + website
    parsed = urlparse(website)
    if not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def parse_pubdate(pubdate: str):
    if not pubdate:
        return None
    try:
        return parsedate_to_datetime(pubdate)
    except (TypeError, ValueError):
        return None


def link_key(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment="", query=parsed.query if "news.google.com" in parsed.netloc else "").geturl().rstrip("/")


def is_same_site(base_url: str, candidate_url: str) -> bool:
    base = urlparse(base_url).netloc.lower().removeprefix("www.")
    candidate = urlparse(candidate_url).netloc.lower().removeprefix("www.")
    return bool(base and candidate and (candidate == base or candidate.endswith("." + base)))


def title_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        return "Company website"
    slug = path.rstrip("/").split("/")[-1]
    return clean_text(slug.replace("-", " ").replace("_", " ")).title()


def classify_company_page(url: str, title: str) -> str | None:
    text = f"{url} {title}"
    if PEOPLE_TERMS.search(text):
        return "peopleTeam"
    if COMPANY_PAGE_TERMS.search(text):
        return "companyPages"
    return None


def discover_company_pages(website: str, fetch=fetch_raw_text) -> dict[str, list[ResearchLink]]:
    base_url = normalize_website(website)
    grouped = {"companyPages": [], "peopleTeam": []}
    if not base_url:
        return grouped

    seen: set[str] = set()

    def add(url: str, title: str, source: str):
        absolute_url = urljoin(base_url + "/", url)
        if not is_same_site(base_url, absolute_url):
            return
        kind = classify_company_page(absolute_url, title)
        if not kind:
            return
        key = link_key(absolute_url)
        if key in seen:
            return
        seen.add(key)
        grouped[kind].append(ResearchLink(title=title or title_from_url(absolute_url), url=absolute_url, source=source))

    html, error = fetch(base_url)
    if not error and html:
        parser = LinkParser()
        parser.feed(html)
        for href, text in parser.links:
            add(href, text or title_from_url(href), "Company website")

    for path in COMMON_PATHS:
        url = urljoin(base_url + "/", path.lstrip("/"))
        if link_key(url) in seen:
            continue
        html, error = fetch(url)
        if error or not html:
            continue
        parser = LinkParser()
        parser.feed(html[:100000])
        add(url, parser.title or title_from_url(url), "Company website")

    for key in grouped:
        grouped[key] = grouped[key][:8]
    return grouped


def research_news(company: str, fetch=fetch_raw_text) -> dict[str, list[ResearchLink]]:
    company = clean_text(company)
    grouped = {"news": [], "funding": []}
    if not company:
        return grouped

    query = f'"{company}"'
    xml_text, error = fetch(google_news_rss_url(query))
    if error or not xml_text:
        return grouped

    seen: set[str] = set()
    results = parse_google_news_rss(xml_text, query)
    results.sort(key=lambda result: parse_pubdate(result.published_at) or parsedate_to_datetime("Thu, 01 Jan 1970 00:00:00 GMT"), reverse=True)

    for result in results:
        key = link_key(result.link)
        if key in seen:
            continue
        seen.add(key)
        title = article_title_without_publisher(result.title) or result.title
        link = ResearchLink(title=title, url=result.link, source=result.publisher or "Google News", published_at=result.published_at)
        if FUNDING_TERMS.search(f"{result.title} {result.summary}"):
            grouped["funding"].append(link)
        else:
            grouped["news"].append(link)

    grouped["funding"] = grouped["funding"][:8]
    grouped["news"] = grouped["news"][:10]
    return grouped


def company_research(company: str, website: str = "", fetch=fetch_raw_text) -> dict[str, list[dict[str, str]]]:
    news = research_news(company, fetch=fetch)
    pages = discover_company_pages(website, fetch=fetch)
    return {
        "news": [link.to_dict() for link in news["news"]],
        "funding": [link.to_dict() for link in news["funding"]],
        "companyPages": [link.to_dict() for link in pages["companyPages"]],
        "peopleTeam": [link.to_dict() for link in pages["peopleTeam"]],
    }
