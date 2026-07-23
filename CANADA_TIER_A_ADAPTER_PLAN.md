# Canada Tier A Adapter Implementation Plan

No adapter code should be written until the current source has passed the discovery gate below. Sources are handled **one at a time**, in this order, and the next source starts only after the current source has a tested extraction and a credible completeness result.

## Source Order

1. MaRS Health Sciences
2. University of Toronto Entrepreneurship / Technology & Startup Explorer
3. Toronto Innovation Acceleration Partners (TIAP)
4. adMare BioInnovations
5. Creative Destruction Lab – Health
6. Centech – Medtech
7. CTS Santé
8. District 3 – Bio and Health
9. OBIO
10. MEDTEQ+
11. Innovate Calgary / UCeed Health
12. University of Alberta Health Innovation Hub
13. Innovation UBC

CDL Health already has a custom adapter in the codebase. Its step will therefore be a Canada-specific completeness audit and repair, not an automatic rewrite.

## Per-Source Workflow

### 1. Discovery Gate

Before coding:

- Identify the official portfolio, venture, cohort, alumni, or funded-project pages.
- Check pagination, filters, “load more” behaviour, archive years, and language variants.
- Inspect page HTML and network calls for JSON, REST, GraphQL, WordPress, Algolia, Airtable/Pory, or other structured endpoints.
- Establish what counts as a company and whether entries are current ventures, alumni, projects, tenants, or general ecosystem members.
- Record an expected count or defensible count range from page totals, annual reports, filter totals, sitemaps, or manual card counts.
- Select the authoritative extraction route before adding the source to configuration.

### 2. Access Strategy

Use the least fragile permitted route:

1. Official public JSON/API endpoint.
2. Static HTML parsed with source-specific selectors/BeautifulSoup-style logic.
3. Browser-rendered public page when content requires JavaScript.
4. Official paginated search, sitemap, archive, or bilingual mirror.
5. Curated official-source fallback when automated extraction is not dependable.

For 403, bot protection, or CAPTCHA:

- Log the status and affected URL explicitly.
- Do not retry aggressively or attempt CAPTCHA bypass.
- Check for an official API, embedded data, reader page, sitemap, feed, or other public first-party representation.
- If normal browser rendering works without solving a challenge, a browser-assisted extraction route may be used.
- Otherwise mark the source `manual/not automated` and retain curated rows with source evidence.
- The pipeline must not silently fall back to a broad generic adapter.

### 3. Adapter Contract

Each source gets:

- A unique adapter name and runner.
- Source-specific parser functions.
- Explicit pagination/archive traversal.
- Company name, profile URL, external website, description, geography, cohort/year, program/track, and source provenance where available.
- Health-category filtering that retains medtech, diagnostics, SaMD/digital health, and relevant biotech platforms.
- Deduplication without losing multiple-source provenance.
- Clear run-log output: pages/endpoints scanned, raw records, accepted companies, rejected records, and errors.

### 4. Completeness Gate

An adapter is not complete merely because it returns some companies. It must:

- Match the official total or fall within the documented expected range.
- Traverse all relevant pages, archive years, and health filters.
- Be manually spot-checked at the beginning, middle, and end of the directory.
- Explain exclusions such as non-health ventures, duplicate alumni, acquired companies, or projects without a company.
- Return `INCOMPLETE` when actual results are materially below expectation.
- Never report success with zero or a suspiciously small subset.

Suggested thresholds:

- **Pass:** at least 90% of the known eligible entries, with explained exclusions.
- **Review:** 70–89%, or no reliable official denominator.
- **Fail/incomplete:** below 70%, missing pagination/archive coverage, or unexplained count collapse.

### 5. Test Gate

Before moving to the next source:

- Parser fixture covering real page/data shape.
- Pagination or archive traversal test.
- Health inclusion and non-health exclusion test.
- Duplicate-handling test.
- Missing-field and changed-markup behaviour.
- 403/error test with an explicit incomplete/manual result.
- Runner test confirming discovery hits, trigger events, provenance, and count reporting.
- Existing test suite remains green.

## Source-Specific Discovery Questions

| Source | Questions to answer before coding |
| --- | --- |
| MaRS | Is there a complete public health portfolio, a searchable venture directory, event presenter lists, or only selected stories? How are 300+ health startups exposed? |
| U of T | Does the Technology & Startup Explorer expose structured search data? Can health, faculty, institution, and spinout status be filtered separately? |
| TIAP | Is the portfolio complete and paginated? Does it distinguish active companies, exits, programs, and technologies not yet incorporated? |
| adMare | Are companies split across portfolio, academy, accelerator, alumni, and regional pages? Which are actual Canadian operating companies? |
| CDL Health | Does the existing adapter traverse every Health result and preserve Canadian geography? Is the official directory total consistent with extraction? |
| Centech | Are Medtech companies available through a portfolio filter/API? Are current and graduate companies separated? Is French content more complete? |
| CTS Santé | Is there a full portfolio or only testimonials/news? Are company cohorts recoverable from archives and French pages? |
| District 3 | The startup page appears filterable; identify its underlying data and validate the reported total against Bio and Health filters. |
| OBIO | Are company lists distributed across different programs/cohorts? Decide whether each program needs a sub-parser under one OBIO runner. |
| MEDTEQ+ | Determine whether funded projects, members, and portfolio companies are separate lead types. Extract company partners rather than universities alone. |
| Innovate Calgary / UCeed | Separate UCeed Health, Child Health, general portfolio, and university spinouts while retaining shared provenance. |
| Alberta Health Innovation Hub | Determine whether it publishes a venture/alumni directory or only program news and success stories. Establish a reliable denominator before automation. |
| Innovation UBC | Validate all pagination and filters for `Human Health`, `Spin-off`, and supported ventures; avoid accidentally extracting planetary-health entries. |

## Tracking Record

Maintain one row per source:

| Source | Discovery status | Access route | Expected eligible count | Extracted count | Coverage | Test status | Decision / blocker |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| MaRS | Complete with dated VentureConnect snapshot | WordPress REST API plus verified browser-assisted VentureConnect directory snapshot | 42 showcase ventures; 508 Healthcare & Life Sciences directory companies | 42 API + 508 snapshot | 100% of both | Passed; full suite 136/136 | 29 direct name matches, 479 directory companies beyond the showcase, and 13 showcase names not directly matched; union is approximately 521 before alias review |
| U of T | Complete | Public WordPress REST `filterposts` endpoint, category 58 | 171 official Health & Life Sciences records | 171 records / 167 unique company names | 100% of official records | Passed; full suite 139/139 | Four names have duplicate official profiles; alternate profile URLs are retained in provenance |
| TIAP | Complete | Static official `/portfolio/` page; source-specific card parser | 57 portfolio companies: 41 active, 16 exited | 57 | 100% | Dedicated tests passed; full suite 142/142 passed | Current portfolio page is authoritative; four-item `/our-portfolio/` page is a legacy archive and is excluded |
| adMare | Complete | Official static portfolio pages plus all company detail pages | 52 records: 39 companies helped build and 13 current/past accelerator companies | 52 | 100% | Dedicated tests passed; full suite 145/145 passed | Live directory cards are authoritative; site headline counters are stale. Captured 43 websites, 39 LinkedIn pages, 48 descriptions, and 35 line-of-business values |
| CDL Health | Complete | Toronto/Vancouver directory filters plus every company detail page | 226 unique Canadian-site health companies: 139 Toronto and 117 Vancouver, with 30-company overlap | 226 | 100% | Dedicated tests passed; full suite 146/146 passed | Repaired multi-stream omissions; captured 217 websites, 226 descriptions, and 225 cohort-year values. CDL site is a program-location signal, not verified company headquarters |
| Centech | Complete | Official WordPress startup API filtered to BioTech, Digital Health, Medical Device, and Medtech | 95 program records covering 92 unique companies | 95 | 100% | Passed; full suite 157/157 | Three companies have separate official repeat-cohort records; captured 88 websites, 82 LinkedIn pages, 95 descriptions, and 93 cohort years |
| CTS Santé | Complete | Official portfolio sitemap plus every company page; normal browser headers used because the pipeline-identifying user agent receives 403 | 21 portfolio URLs | 21 | 100% | Passed; full suite 157/157 | Captured 12 websites and 20 descriptions; no CAPTCHA or challenge bypass |
| District 3 | Complete | Two live pages of official startup cards; exact Healthcare and Biotech stream filter | 12 eligible among 25 live cards | 12 | 100% | Passed; full suite 157/157 | The rendered “of 100” counter is stale; later pages are empty and sector history is not treated as a current company denominator |
| OBIO | Complete for publicly named cohorts | Official WiHI and joint OBIO/FACIT WeSEED cohort announcements | 25 cohort records | 25 records / 24 unique names | 100% of selected named cohorts | Passed; full suite 157/157 | OBIO reports 350+ historically supported companies but publishes no complete company-level directory; no unsupported all-member total is claimed |
| MEDTEQ+ | Complete for company portfolio | Official investment portfolio on financing page | 17 companies | 17 | 100% | Passed; full suite 157/157 | The separate funded-project directory currently has 145 project cards but does not reliably expose company collaborators, so projects and universities are not misclassified as companies |
| Innovate Calgary / UCeed | Complete | Official UCalgary Health Fund and Child Health and Wellness Fund portfolio sections | 42 fund records | 42 records / 34 unique names | 100% | Passed; full suite 157/157 | Both funds retain separate provenance where the same company appears in each |
| Alberta Health Innovation Hub | Complete | Official UAlberta company-card directory; production route with official preview-host fallback | 44 live cards | 44 | 100% | Passed; full suite 157/157 | Captured 31 websites; directory headline says “nearly 50,” while 44 is the exact live-card denominator |
| Innovation UBC | Complete | Seven official portfolio pages; exact `Human Health` impact-area match | 152 eligible among 385 live rows | 152 | 100% | Passed; full suite 157/157 | 124 Spin-off, 17 Spin-off/Supported Venture, and 11 Supported Venture records; planetary-health-only rows excluded |

## Definition of Done for Tier A

- Every source has either a validated custom adapter or a documented manual/curated treatment.
- Every automated source has an expected-count check and explicit incomplete state.
- No Tier A source uses the retired generic accelerator adapter.
- Counts and sample companies have been manually verified.
- The combined output is deduplicated while preserving source/program provenance.
- A short run report identifies coverage, blockers, and sources requiring manual refresh.
