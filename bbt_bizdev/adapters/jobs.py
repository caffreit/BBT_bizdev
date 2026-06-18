from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, unquote

from ..config import (
    BIOSPACE_SEARCH_QUERIES, BUILTIN_SEARCH_QUERIES, COMPANY_REGISTRY, GREENHOUSE_SEARCH_QUERIES,
    JOB_BOARD_ADAPTERS, MAX_MATCHED_JOBS_PER_COMPANY, NHS_SEARCH_QUERIES,
)
from ..http import fetch_json_url, fetch_raw_text
from ..models import DiscoveryHit, JobLead, JobPosting, Source, TriggerEvent
from ..text import clean_page_candidate, clean_text, extract_links, infer_page_product_type, is_plausible_company_name


def configured_job_boards(platform: str) -> list[tuple[str, dict, str]]:
    boards: list[tuple[str, dict, str]] = []
    for company, meta in COMPANY_REGISTRY.items():
        for board in meta.get("job_boards", []):
            if board.get("platform") == platform and board.get("account"):
                boards.append((company, meta, board["account"]))
    return boards

def job_board_url(platform: str, account: str) -> str:
    if platform == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{account}/jobs?content=true"
    if platform == "lever":
        return f"https://api.lever.co/v0/postings/{account}?mode=json"
    if platform == "ashby":
        return f"https://api.ashbyhq.com/posting-api/job-board/{account}?includeCompensation=true"
    if platform == "workable":
        return f"https://apply.workable.com/api/v1/widget/accounts/{account}?details=true"
    if platform == "smartrecruiters":
        return f"https://api.smartrecruiters.com/v1/companies/{account}/postings"
    if platform == "recruitee":
        return f"https://{account}.recruitee.com/api/offers/"
    return ""

def greenhouse_search_url(query: str) -> str:
    return "https://www.bing.com/search?" + urlencode({"q": query, "count": "20"})

def biospace_search_url(query: str) -> str:
    return "https://jobs.biospace.com/jobs/?" + urlencode({"keywords": query})

def builtin_search_url(query: str) -> str:
    return "https://builtin.com/jobs?" + urlencode({"search": query})

def nhs_search_url(query: str) -> str:
    return "https://www.jobs.nhs.uk/candidate/search/results?" + urlencode({"keyword": query})

def unwrap_search_url(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    for key in ["q", "url", "u"]:
        value = params.get(key, [""])[0]
        if value.startswith(("http://", "https://")):
            return unquote(value)
    return url

def extract_greenhouse_job_urls(raw_html: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    candidates = [href for _, href in extract_links(raw_html, "https://www.bing.com/")]
    candidates.extend(re.findall(r"https?://(?:job-)?boards\.greenhouse\.io/[^\s\"'<>]+", raw_html, flags=re.I))
    for candidate in candidates:
        url = unwrap_search_url(html.unescape(candidate)).rstrip(").,;")
        if "boards.greenhouse.io" not in url.lower():
            continue
        if greenhouse_board_token_from_url(url) and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls

def greenhouse_board_token_from_url(url: str) -> str:
    parsed = urlparse(url)
    if "boards.greenhouse.io" not in parsed.netloc.lower():
        return ""
    parts = [part for part in parsed.path.split("/") if part]
    if parts:
        return parts[0]
    query_token = parse_qs(parsed.query).get("for", [""])[0]
    return query_token

def html_to_text(value: str) -> str:
    return clean_text(re.sub(r"<[^>]+>", " ", html.unescape(value or "")))

def nested_text(value: object) -> str:
    if isinstance(value, str):
        return html_to_text(value)
    if isinstance(value, list):
        return " ".join(nested_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(nested_text(item) for item in value.values())
    return ""

def job_location(value: object) -> str:
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, dict):
        return clean_text(value.get("name") or value.get("location") or value.get("city") or nested_text(value))
    if isinstance(value, list):
        return "; ".join(filter(None, [job_location(item) for item in value]))
    return ""

def parse_greenhouse_jobs(data: object) -> list[JobPosting]:
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    postings: list[JobPosting] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        postings.append(
            JobPosting(
                title=clean_text(job.get("title", "")),
                url=job.get("absolute_url") or job.get("internal_job_id") or "",
                description=html_to_text(job.get("content", "")),
                location=job_location(job.get("location")),
                department=job_location(job.get("departments")),
            )
        )
    return postings

def parse_lever_jobs(data: object) -> list[JobPosting]:
    jobs = data if isinstance(data, list) else []
    postings: list[JobPosting] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        postings.append(
            JobPosting(
                title=clean_text(job.get("text", "")),
                url=job.get("hostedUrl") or job.get("applyUrl") or "",
                description=html_to_text(job.get("description") or job.get("descriptionPlain") or nested_text(job.get("lists", []))),
                location=job_location(job.get("categories", {}).get("location") if isinstance(job.get("categories"), dict) else ""),
                department=job_location(job.get("categories", {}).get("team") if isinstance(job.get("categories"), dict) else ""),
            )
        )
    return postings

def parse_ashby_jobs(data: object) -> list[JobPosting]:
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    postings: list[JobPosting] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        postings.append(
            JobPosting(
                title=clean_text(job.get("title", "")),
                url=job.get("jobUrl") or job.get("url") or "",
                description=html_to_text(job.get("descriptionHtml") or job.get("description") or ""),
                location=job_location(job.get("location") or job.get("locations")),
                department=job_location(job.get("department")),
            )
        )
    return postings

def parse_workable_jobs(data: object) -> list[JobPosting]:
    jobs = data.get("jobs") or data.get("results") or [] if isinstance(data, dict) else []
    postings: list[JobPosting] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        url = job.get("url") or job.get("shortlink") or job.get("application_url") or ""
        shortcode = job.get("shortcode")
        if not url and shortcode:
            url = f"https://apply.workable.com/j/{shortcode}/"
        postings.append(
            JobPosting(
                title=clean_text(job.get("title", "")),
                url=url,
                description=html_to_text(job.get("description") or nested_text(job.get("requirements", ""))),
                location=job_location(job.get("location") or job.get("locations")),
                department=job_location(job.get("department")),
            )
        )
    return postings

def parse_smartrecruiters_jobs(data: object) -> list[JobPosting]:
    jobs = data.get("content") or data.get("jobs") or [] if isinstance(data, dict) else []
    postings: list[JobPosting] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        ref = job.get("ref") if isinstance(job.get("ref"), str) else ""
        postings.append(
            JobPosting(
                title=clean_text(job.get("name") or job.get("title") or ""),
                url=job.get("url") or ref,
                description=html_to_text(job.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", "") if isinstance(job.get("jobAd"), dict) else job.get("description", "")),
                location=job_location(job.get("location")),
                department=job_location(job.get("department")),
            )
        )
    return postings

def parse_recruitee_jobs(data: object) -> list[JobPosting]:
    jobs = data.get("offers") or data.get("jobs") or [] if isinstance(data, dict) else []
    postings: list[JobPosting] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        postings.append(
            JobPosting(
                title=clean_text(job.get("title", "")),
                url=job.get("careers_url") or job.get("url") or "",
                description=html_to_text(job.get("description") or job.get("description_html") or ""),
                location=job_location(job.get("location") or job.get("locations")),
                department=job_location(job.get("department")),
            )
        )
    return postings

def html_attr_value(raw_html: str, attr: str) -> str:
    match = re.search(rf"\b{re.escape(attr)}=[\"']([^\"']+)[\"']", raw_html, flags=re.I)
    return html.unescape(match.group(1)).strip() if match else ""

def parse_biospace_jobs(raw_html: str, page_url: str, query: str = "") -> list[JobLead]:
    leads: list[JobLead] = []
    items = re.findall(r"<li\b[^>]*class=[\"'][^\"']*\blister__item\b[^\"']*[\"'][^>]*>.*?</li>\s*(?=<li\b[^>]*class=[\"'][^\"']*\blister__item\b|</ul>)", raw_html, flags=re.I | re.S)
    for item in items:
        title_match = re.search(r"<h3\b[^>]*class=[\"'][^\"']*lister__header[^\"']*[\"'][^>]*>.*?<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", item, flags=re.I | re.S)
        if not title_match:
            continue
        url = urljoin(page_url, clean_text(title_match.group(1)))
        title = clean_text(title_match.group(2))
        location_match = re.search(r"class=[\"'][^\"']*lister__meta-item--location[^\"']*[\"'][^>]*>(.*?)</li>", item, flags=re.I | re.S)
        company_match = re.search(r"class=[\"'][^\"']*lister__meta-item--recruiter[^\"']*[\"'][^>]*>(.*?)</li>", item, flags=re.I | re.S)
        description_match = re.search(r"class=[\"'][^\"']*lister__description[^\"']*[\"'][^>]*>(.*?)</p>", item, flags=re.I | re.S)
        company = clean_page_candidate(clean_text(company_match.group(1) if company_match else ""))
        if not title or not company or not is_plausible_company_name(company):
            continue
        posting = JobPosting(
            title=title,
            url=url,
            description=clean_text(description_match.group(1) if description_match else ""),
            location=clean_text(location_match.group(1) if location_match else ""),
        )
        leads.append(JobLead(company=company, posting=posting, query=query))
    return leads

def parse_builtin_jobs(raw_html: str, page_url: str, query: str = "") -> list[JobLead]:
    leads: list[JobLead] = []
    starts = [match.start() for match in re.finditer(r"<div\b[^>]*(?:id=[\"']job-card-\d+[\"']|data-id=[\"']job-card[\"'])", raw_html, flags=re.I)]
    cards = [raw_html[start:end] for start, end in zip(starts, starts[1:] + [len(raw_html)])]
    for card in cards:
        company_match = re.search(r"<a\b(?=[^>]*data-id=[\"']company-title[\"'])[^>]*>(.*?)</a>", card, flags=re.I | re.S)
        title_match = re.search(r"<a\b(?=[^>]*data-id=[\"']job-card-title[\"'])[^>]*>(.*?)</a>", card, flags=re.I | re.S)
        if not company_match or not title_match:
            continue
        href = html_attr_value(title_match.group(0), "href")
        if not href:
            continue
        company = clean_page_candidate(clean_text(company_match.group(1)))
        title = clean_text(title_match.group(1))
        url = urljoin(page_url, href)
        location = ""
        location_match = re.search(r"fa-location-dot.*?</i>\s*</div>\s*<div><span[^>]*>(.*?)</span>", card, flags=re.I | re.S)
        if location_match:
            location = clean_text(location_match.group(1))
        description_parts = re.findall(r"<span\b[^>]*class=[\"'][^\"']*font-barlow text-gray-04[^\"']*[\"'][^>]*>(.*?)</span>", card, flags=re.I | re.S)
        description = " ".join(clean_text(part) for part in description_parts)
        if not title or not company or not is_plausible_company_name(company):
            continue
        leads.append(
            JobLead(
                company=company,
                posting=JobPosting(title=title, url=url, description=description, location=location),
                query=query,
            )
        )
    return leads

def parse_nhs_jobs(raw_html: str, page_url: str, query: str = "") -> list[JobLead]:
    leads: list[JobLead] = []
    starts = [match.start() for match in re.finditer(r"<li\b(?=[^>]*data-test=[\"']search-result[\"'])", raw_html, flags=re.I)]
    items = [raw_html[start:end] for start, end in zip(starts, starts[1:] + [len(raw_html)])]
    for item in items:
        title_match = re.search(r"<a\b(?=[^>]*data-test=[\"']search-result-job-title[\"'])[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", item, flags=re.I | re.S)
        location_section = re.search(r"<div\b(?=[^>]*data-test=[\"']search-result-location[\"'])[^>]*>.*?<h3[^>]*>(.*?)</h3>", item, flags=re.I | re.S)
        if not title_match or not location_section:
            continue
        title = clean_text(title_match.group(2))
        url = urljoin(page_url, html.unescape(title_match.group(1)).strip())
        section_html = location_section.group(1)
        location_match = re.search(r"<div\b[^>]*class=[\"'][^\"']*location-font-size[^\"']*[\"'][^>]*>(.*?)</div>", section_html, flags=re.I | re.S)
        location = clean_text(location_match.group(1) if location_match else "")
        company_html = re.sub(r"<div\b[^>]*class=[\"'][^\"']*location-font-size[^\"']*[\"'][^>]*>.*?</div>", " ", section_html, flags=re.I | re.S)
        company = clean_page_candidate(clean_text(company_html).replace(location, "").strip())
        description_parts = []
        for data_test in ["search-result-salary", "search-result-publicationDate", "search-result-jobType", "search-result-workingPattern"]:
            match = re.search(rf"<li\b[^>]*data-test=[\"']{data_test}[\"'][^>]*>(.*?)</li>", item, flags=re.I | re.S)
            if match:
                description_parts.append(clean_text(match.group(1)))
        if not title or not company or not is_plausible_nhs_employer(company):
            continue
        leads.append(
            JobLead(
                company=company,
                posting=JobPosting(title=title, url=url, description="; ".join(description_parts), location=location),
                query=query,
            )
        )
    return leads

def relevant_nhs_job_terms(lead: JobLead) -> list[str]:
    text = " ".join([lead.posting.title, lead.posting.description]).lower()
    terms = [
        "clinical safety", "clinical informatics", "digital health", "clinical systems",
        "quality improvement", "patient safety", "clinical governance", "innovation",
        "ai", "data", "analytics", "transformation", "implementation",
    ]
    return [term for term in terms if term in text]

def is_plausible_nhs_employer(name: str) -> bool:
    lower = name.lower()
    blocked = {"nhs", "jobs", "search", "save this job", "create job alert"}
    if lower in blocked:
        return False
    return bool(re.search(r"[A-Za-z]", name))


JOB_PARSERS = {
    "greenhouse": parse_greenhouse_jobs,
    "lever": parse_lever_jobs,
    "ashby": parse_ashby_jobs,
    "workable": parse_workable_jobs,
    "smartrecruiters": parse_smartrecruiters_jobs,
    "recruitee": parse_recruitee_jobs,
}

JOB_PARSERS = {
    "greenhouse": parse_greenhouse_jobs,
    "lever": parse_lever_jobs,
    "ashby": parse_ashby_jobs,
    "workable": parse_workable_jobs,
    "smartrecruiters": parse_smartrecruiters_jobs,
    "recruitee": parse_recruitee_jobs,
}


def relevant_job_terms(posting: JobPosting, company_meta: dict) -> list[str]:
    text = " ".join([posting.title, posting.description, posting.department, posting.location, company_meta.get("product_type", "")]).lower()
    role_terms = [
        "regulatory", "regulatory affairs", "quality", "quality engineer", "design assurance",
        "v&v", "verification", "validation", "clinical", "clinical validation", "medical device",
        "medtech", "digital health", "samd", "fda", "qa", "diagnostic", "imaging", "ai",
    ]
    context_terms = ["ai", "machine learning", "medical device", "medtech", "health", "clinical", "diagnostic", "imaging", "digital health", "samd", "fda"]
    matched = [term for term in role_terms if term in text]
    title_lower = posting.title.lower()
    if not matched and re.search(r"\b(engineer|engineering|product|software|ml|ai)\b", title_lower) and any(term in text for term in context_terms):
        matched = [term for term in context_terms if term in text]
    return matched

def relevant_builtin_job_terms(lead: JobLead) -> list[str]:
    terms = relevant_job_terms(lead.posting, {})
    if not terms:
        return []
    text = " ".join([lead.company, lead.posting.title, lead.posting.description, lead.query]).lower()
    strong_terms = [
        "regulatory affairs", "clinical", "healthcare", "medical", "medical device", "fda",
        "diagnostic", "imaging", "biotech", "pharma", "therapeutic", "hospital",
    ]
    if any(term in text for term in strong_terms):
        return terms
    broad_only = {"quality", "quality engineer", "qa", "verification", "validation", "ai"}
    if set(terms).issubset(broad_only):
        return []
    return terms

def registry_meta_for_company(company: str) -> dict:
    lower_company = company.lower()
    for registry_company, meta in COMPANY_REGISTRY.items():
        aliases = [registry_company] + meta.get("aliases", [])
        if lower_company in {alias.lower() for alias in aliases}:
            return meta
    return {}

def infer_job_product_type(source: Source, postings: list[JobPosting], fallback: str = "") -> str:
    context = " ".join([fallback] + [posting.title for posting in postings] + [posting.description for posting in postings])
    return infer_page_product_type(source, context)

def run_greenhouse_discovery(source: Source, queries: list[str] | None = None) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    queries = queries or GREENHOUSE_SEARCH_QUERIES
    job_urls: list[str] = []
    search_errors: list[str] = []
    for query in queries:
        raw_html, error = fetch_raw_text(greenhouse_search_url(query))
        if error:
            search_errors.append(f"{query}: {error}")
            continue
        job_urls.extend(extract_greenhouse_job_urls(raw_html))

    tokens = sorted({greenhouse_board_token_from_url(url) for url in job_urls if greenhouse_board_token_from_url(url)})
    discovery_hits: list[DiscoveryHit] = []
    trigger_events: list[TriggerEvent] = []
    errors: list[str] = []
    skipped = 0
    seen: set[tuple[str, str]] = set()

    for token in tokens:
        board_data, board_error = fetch_json_url(f"https://boards-api.greenhouse.io/v1/boards/{token}")
        if board_error:
            errors.append(f"{token} board: {board_error}")
            continue
        jobs_data, jobs_error = fetch_json_url(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
        if jobs_error:
            errors.append(f"{token} jobs: {jobs_error}")
            continue
        company = clean_text(board_data.get("name", "")) if isinstance(board_data, dict) else ""
        if not company:
            company = clean_page_candidate(token.replace("-", " ").replace("_", " ").title())
        postings = parse_greenhouse_jobs(jobs_data)
        meta = registry_meta_for_company(company)
        matched_jobs = [posting for posting in postings if posting.title and relevant_job_terms(posting, meta)]
        if not matched_jobs:
            skipped += 1
            continue

        key = (company.lower(), token.lower())
        if key in seen:
            continue
        seen.add(key)
        selected = matched_jobs[:MAX_MATCHED_JOBS_PER_COMPANY]
        role_titles = "; ".join(posting.title for posting in selected)
        evidence_url = selected[0].url or f"https://boards.greenhouse.io/{token}"
        matched_terms = sorted({term for posting in selected for term in relevant_job_terms(posting, meta)})
        product_type = meta.get("product_type") or infer_job_product_type(source, selected)
        geography = meta.get("geography") or source.geography
        website = meta.get("website", "")
        discovery_hits.append(
            DiscoveryHit(
                company=company,
                source_name=source.name,
                source_type=source.source_type,
                discovery_url=evidence_url,
                discovery_rationale=f"Greenhouse search found relevant open roles: {role_titles}",
                product_type=product_type,
                geography=geography,
                website=website,
                matched_terms=f"adapter: greenhouse_jobs; board: {token}; roles: {role_titles}; terms: {', '.join(matched_terms)}",
                company_description=" ".join([posting.description for posting in selected])[:1000],
            )
        )
        trigger_events.append(
            TriggerEvent(
                company=company,
                trigger_type="Hiring signal",
                trigger_event=f"Relevant Greenhouse hiring signal: {role_titles}",
                trigger_source=source.name,
                evidence_url=evidence_url,
            )
        )

    result = f"{len(queries)} search queries; {len(job_urls)} job URLs found; {len(tokens)} board tokens fetched; {len(discovery_hits)} discovery hits; {len(trigger_events)} trigger events; {skipped} boards with no matching jobs"
    all_errors = search_errors + errors
    if all_errors:
        result += "; errors: " + " | ".join(all_errors[:5])
    return discovery_hits, trigger_events, result

def run_biospace_jobs(source: Source, queries: list[str] | None = None) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    queries = queries or BIOSPACE_SEARCH_QUERIES
    leads: list[JobLead] = []
    errors: list[str] = []
    for query in queries:
        url = biospace_search_url(query)
        raw_html, error = fetch_raw_text(url)
        if error:
            errors.append(f"{query}: {error}")
            continue
        leads.extend(parse_biospace_jobs(raw_html, url, query))

    grouped: dict[str, list[JobLead]] = {}
    for lead in leads:
        if not relevant_job_terms(lead.posting, {}):
            continue
        grouped.setdefault(lead.company, []).append(lead)

    discovery_hits: list[DiscoveryHit] = []
    trigger_events: list[TriggerEvent] = []
    for company, company_leads in sorted(grouped.items()):
        selected = company_leads[:MAX_MATCHED_JOBS_PER_COMPANY]
        postings = [lead.posting for lead in selected]
        role_titles = "; ".join(posting.title for posting in postings)
        matched_terms = sorted({term for posting in postings for term in relevant_job_terms(posting, {})})
        queries_seen = sorted({lead.query for lead in selected if lead.query})
        meta = registry_meta_for_company(company)
        discovery_hits.append(
            DiscoveryHit(
                company=company,
                source_name=source.name,
                source_type=source.source_type,
                discovery_url=postings[0].url or source.url,
                discovery_rationale=f"BioSpace role search found relevant open roles: {role_titles}",
                product_type=meta.get("product_type") or infer_job_product_type(source, postings, source.notes),
                geography=meta.get("geography") or source.geography,
                website=meta.get("website", ""),
                matched_terms=f"adapter: biospace_jobs; queries: {', '.join(queries_seen)}; roles: {role_titles}; terms: {', '.join(matched_terms)}",
                company_description=" ".join([posting.description for posting in postings])[:1000],
            )
        )
        trigger_events.append(
            TriggerEvent(
                company=company,
                trigger_type="Hiring signal",
                trigger_event=f"Relevant BioSpace hiring signal: {role_titles}",
                trigger_source=source.name,
                evidence_url=postings[0].url or source.url,
            )
        )

    result = f"{len(queries)} search queries; {len(leads)} job cards parsed; {len(discovery_hits)} discovery hits; {len(trigger_events)} trigger events"
    if errors:
        result += "; errors: " + " | ".join(errors[:5])
    return discovery_hits, trigger_events, result

def run_builtin_jobs(source: Source, queries: list[str] | None = None) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    queries = queries or BUILTIN_SEARCH_QUERIES
    leads: list[JobLead] = []
    errors: list[str] = []
    for query in queries:
        url = builtin_search_url(query)
        raw_html, error = fetch_raw_text(url)
        if error:
            errors.append(f"{query}: {error}")
            continue
        leads.extend(parse_builtin_jobs(raw_html, url, query))

    grouped: dict[str, list[JobLead]] = {}
    for lead in leads:
        if not relevant_builtin_job_terms(lead):
            continue
        grouped.setdefault(lead.company, []).append(lead)

    discovery_hits: list[DiscoveryHit] = []
    trigger_events: list[TriggerEvent] = []
    for company, company_leads in sorted(grouped.items()):
        selected = company_leads[:MAX_MATCHED_JOBS_PER_COMPANY]
        postings = [lead.posting for lead in selected]
        role_titles = "; ".join(posting.title for posting in postings)
        matched_terms = sorted({term for lead in selected for term in relevant_builtin_job_terms(lead)})
        queries_seen = sorted({lead.query for lead in selected if lead.query})
        meta = registry_meta_for_company(company)
        discovery_hits.append(
            DiscoveryHit(
                company=company,
                source_name=source.name,
                source_type=source.source_type,
                discovery_url=postings[0].url or source.url,
                discovery_rationale=f"Built In role search found relevant open roles: {role_titles}",
                product_type=meta.get("product_type") or infer_job_product_type(source, postings, source.notes),
                geography=meta.get("geography") or source.geography,
                website=meta.get("website", ""),
                matched_terms=f"adapter: builtin_jobs; queries: {', '.join(queries_seen)}; roles: {role_titles}; terms: {', '.join(matched_terms)}",
                company_description=" ".join([posting.description for posting in postings])[:1000],
            )
        )
        trigger_events.append(
            TriggerEvent(
                company=company,
                trigger_type="Hiring signal",
                trigger_event=f"Relevant Built In hiring signal: {role_titles}",
                trigger_source=source.name,
                evidence_url=postings[0].url or source.url,
            )
        )

    result = f"{len(queries)} search queries; {len(leads)} job cards parsed; {len(discovery_hits)} discovery hits; {len(trigger_events)} trigger events"
    if errors:
        result += "; errors: " + " | ".join(errors[:5])
    return discovery_hits, trigger_events, result

def run_nhs_jobs(source: Source, queries: list[str] | None = None) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    queries = queries or NHS_SEARCH_QUERIES
    leads: list[JobLead] = []
    errors: list[str] = []
    for query in queries:
        url = nhs_search_url(query)
        raw_html, error = fetch_raw_text(url)
        if error:
            errors.append(f"{query}: {error}")
            continue
        leads.extend(parse_nhs_jobs(raw_html, url, query))

    grouped: dict[str, list[JobLead]] = {}
    for lead in leads:
        if not relevant_nhs_job_terms(lead):
            continue
        grouped.setdefault(lead.company, []).append(lead)

    discovery_hits: list[DiscoveryHit] = []
    trigger_events: list[TriggerEvent] = []
    for company, company_leads in sorted(grouped.items()):
        selected = company_leads[:MAX_MATCHED_JOBS_PER_COMPANY]
        postings = [lead.posting for lead in selected]
        role_titles = "; ".join(posting.title for posting in postings)
        matched_terms = sorted({term for lead in selected for term in relevant_nhs_job_terms(lead)})
        queries_seen = sorted({lead.query for lead in selected if lead.query})
        discovery_hits.append(
            DiscoveryHit(
                company=company,
                source_name=source.name,
                source_type=source.source_type,
                discovery_url=postings[0].url or source.url,
                discovery_rationale=f"NHS Jobs role search found relevant open roles: {role_titles}",
                product_type=infer_job_product_type(source, postings, source.notes),
                geography=source.geography,
                website="",
                matched_terms=f"adapter: nhs_jobs; queries: {', '.join(queries_seen)}; roles: {role_titles}; terms: {', '.join(matched_terms)}",
                company_description=" ".join([posting.description for posting in postings])[:1000],
            )
        )
        trigger_events.append(
            TriggerEvent(
                company=company,
                trigger_type="Hiring signal",
                trigger_event=f"Relevant NHS Jobs hiring signal: {role_titles}",
                trigger_source=source.name,
                evidence_url=postings[0].url or source.url,
            )
        )

    result = f"{len(queries)} search queries; {len(leads)} job cards parsed; {len(discovery_hits)} discovery hits; {len(trigger_events)} trigger events"
    if errors:
        result += "; errors: " + " | ".join(errors[:5])
    return discovery_hits, trigger_events, result

def run_job_board_adapter(source: Source, platform: str) -> tuple[list[DiscoveryHit], list[TriggerEvent], str]:
    boards = configured_job_boards(platform)
    if not boards:
        return [], [], f"No registry companies configured for {platform} job boards"
    discovery_hits: list[DiscoveryHit] = []
    trigger_events: list[TriggerEvent] = []
    errors: list[str] = []
    no_matches = 0
    fetched = 0
    for company, meta, account in boards:
        data, error = fetch_json_url(job_board_url(platform, account))
        if error:
            errors.append(f"{company}: {error}")
            continue
        fetched += 1
        postings = JOB_PARSERS[platform](data)
        matched_jobs = [posting for posting in postings if posting.title and relevant_job_terms(posting, meta)]
        if not matched_jobs:
            no_matches += 1
            continue
        selected = matched_jobs[:MAX_MATCHED_JOBS_PER_COMPANY]
        role_titles = "; ".join(posting.title for posting in selected)
        evidence_url = selected[0].url or meta.get("website") or source.url
        matched_terms = sorted({term for posting in selected for term in relevant_job_terms(posting, meta)})
        discovery_hits.append(
            DiscoveryHit(
                company=company,
                source_name=source.name,
                source_type=source.source_type,
                discovery_url=evidence_url,
                discovery_rationale=f"{company} has relevant open roles on {source.name}: {role_titles}",
                product_type=meta.get("product_type", ""),
                geography=meta.get("geography", source.geography),
                website=meta.get("website", ""),
                matched_terms=f"adapter: {source.adapter}; roles: {role_titles}; terms: {', '.join(matched_terms)}",
                company_description=" ".join([posting.description for posting in selected])[:1000],
            )
        )
        trigger_events.append(
            TriggerEvent(
                company=company,
                trigger_type="Hiring signal",
                trigger_event=f"Relevant hiring signal from {source.name}: {role_titles}",
                trigger_source=source.name,
                evidence_url=evidence_url,
            )
        )
    result = f"{fetched}/{len(boards)} configured boards fetched; {len(discovery_hits)} discovery hits; {len(trigger_events)} trigger events; {no_matches} boards with no matching jobs"
    if errors:
        result += "; errors: " + " | ".join(errors[:5])
    return discovery_hits, trigger_events, result

