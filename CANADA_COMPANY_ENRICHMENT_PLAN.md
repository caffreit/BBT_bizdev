# Canada Company Enrichment Plan

## Purpose

Enrich the deduplicated Canadian company universe with evidence-backed signals for:

1. Hiring and expansion
2. Funding and ability to buy
3. Regulatory status
4. Active product development
5. Recent news and material events

This is an enrichment workflow, not a new broad company-discovery exercise. It starts from the companies already collected from accelerators, university spinout sources, investors, and commercialization platforms.

## Guiding Principles

- Prefer structured first-party or government sources.
- Use search and aggregators to discover evidence, not as the sole authority for material claims.
- Store the exact evidence URL, evidence date, capture date, and extraction method for every claim.
- Distinguish “no result found” from “confirmed zero” and from “source blocked.”
- Never infer a pending confidential regulatory submission from silence or indirect hints.
- Never treat accelerator membership, investor portfolio membership, or a job advert as proof of a funding round, regulatory approval, or company headquarters.
- Preserve historical events instead of overwriting the prior value with the latest value.
- Do not bypass CAPTCHAs, authentication, paywalls, robots controls, or access restrictions.

## Scope and Execution Order

### Phase 0 — Canonical Company Identity

Complete before enriching signals:

- Merge all Canadian source snapshots into one canonical company table.
- Preserve every source record and provenance link.
- Resolve official website and canonical domain.
- Record legal name, trading name, known aliases, former names, and acquired status where supported.
- Resolve Canadian city, province, and role of the Canadian operation: headquarters, R&D office, commercial office, or unclear.
- Assign a stable `company_id` that does not change when the display name changes.

### Phase 1 — Hiring and Expansion

Run first because hiring is the strongest current-intent signal and can be collected directly from known company websites.

### Phase 2 — Funding

Attach dated rounds, grants, loans, and strategic investments. Funding is mandatory for prioritization, but absence of public funding is not a negative conclusion.

### Phase 3 — Regulatory and Product Development

Run against the medtech, diagnostics, SaMD, and enabling-platform subset. Apply the most expensive manual/news research to the highest-priority companies first.

### Phase 4 — Recent News

Use news to confirm and contextualize product, clinical, regulatory, funding, partnership, manufacturing, launch, and expansion events.

### Phase 5 — Consolidated Review Workbook

Create a filterable spreadsheet with one company row plus separate evidence/event tabs.

## Canonical Data Model

### Company Table

| Field | Description |
| --- | --- |
| `company_id` | Stable internal identifier |
| `company_name` | Current public trading name |
| `legal_name` | Legal manufacturer/company name where evidenced |
| `aliases` | Former names, abbreviations, spelling variants |
| `website` | Canonical official website |
| `domain` | Normalized domain used for matching |
| `city` | Best-supported Canadian city |
| `province` | Canadian province |
| `country` | Country of headquarters |
| `canada_relationship` | HQ, R&D office, commercial office, program location only, or unclear |
| `employee_band` | `1–9`, `10–19`, `20–49`, `50–99`, `100–199`, `200–499`, `500+`, or unknown |
| `product_category` | Medical device, diagnostics, SaMD, digital health, biotech platform, therapeutics, research tools, or non-health |
| `product_summary` | One evidence-backed sentence |
| `company_stage` | Pre-company, pre-seed, seed, Series A, Series B/C, growth, public, acquired, inactive, or unknown |
| `source_provenance` | All accelerator, university, investor, and funding-source records |
| `last_enriched_at` | Most recent completed enrichment run |

### Hiring Evidence Table

| Field | Description |
| --- | --- |
| `company_id` | Canonical company |
| `careers_url` | Official careers page |
| `ats_provider` | Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee, Workday, custom, or none |
| `ats_board_id` | Verified public board/account slug |
| `job_id` | Source-native identifier |
| `job_title` | Exact title |
| `department` | Source department/team |
| `location` | Exact source location |
| `remote_canada` | Yes, no, or unclear |
| `posted_at` | Source date when provided |
| `job_url` | Exact posting URL |
| `role_family` | QA, regulatory, R&D/product, V&V/design assurance, clinical, manufacturing, software medical product, commercial expansion, or other |
| `seniority` | Individual contributor, manager, director, VP/executive, or unclear |
| `signal_strength` | High, medium, or low |
| `captured_at` | Collection date |
| `posting_status` | Open, closed since prior snapshot, or unknown |

### Funding Event Table

| Field | Description |
| --- | --- |
| `company_id` | Canonical company |
| `event_date` | Announced/award date |
| `funding_type` | Equity, convertible, debt, grant, contribution, loan, strategic investment, or undisclosed |
| `stage` | Pre-seed, seed, Series A/B/C, growth, public financing, grant, or unknown |
| `amount_original` | Amount exactly as published |
| `currency` | Published currency |
| `amount_cad` | Optional normalized amount with conversion date |
| `investors_or_funders` | Named participants |
| `lead_investor` | Lead when explicitly stated |
| `use_of_funds` | Hiring, R&D, clinical, regulatory, manufacturing, market entry, or other |
| `evidence_url` | Primary evidence |
| `secondary_url` | Corroborating evidence |
| `confidence` | High, medium, or low |

### Regulatory Evidence Table

| Field | Description |
| --- | --- |
| `company_id` | Canonical company |
| `jurisdiction` | Canada, US, EU, UK, or other |
| `authority` | Health Canada, FDA, European Commission/notified-body evidence, MHRA, etc. |
| `record_type` | MDL/MDALL, MDEL, 510(k), De Novo, PMA, listing, trial, recall, or other |
| `record_id` | Licence, clearance, trial, or recall identifier |
| `legal_manufacturer` | Name shown by the authority |
| `product_name` | Regulated product/device |
| `device_class` | Class where published |
| `status` | Active, archived, cleared, approved, registered, suspended, recalled, or unknown |
| `decision_or_start_date` | Authority date |
| `evidence_url` | Exact regulator/database record |
| `match_basis` | Exact legal name, known alias, company ID/address, product/website corroboration, or manual review |
| `confidence` | High, medium, or low |

### Product Development and News Event Table

| Field | Description |
| --- | --- |
| `company_id` | Canonical company |
| `event_date` | Event/publication date |
| `event_type` | Product launch, prototype, design freeze, clinical study, validation, regulatory submission claim, approval, partnership, manufacturing, patent, hiring expansion, funding, acquisition, or other |
| `title` | Source title |
| `summary` | Short evidence-bound summary |
| `product_or_program` | Named product, platform, trial, or program |
| `development_stage` | Research, prototype, preclinical, clinical, validation, regulatory, launch, scale-up, or unknown |
| `evidence_url` | Primary evidence |
| `source_type` | Company, government, regulator, clinical registry, investor, university, newswire, or media |
| `confidence` | High, medium, or low |

## Identity Resolution Method

### Normalization

- Case-fold names and remove punctuation for matching.
- Remove legal suffixes only for comparison: Inc., Corp., Corporation, Ltd., Limited, ULC, LP, and French equivalents.
- Preserve the original legal name in evidence.
- Normalize domains by removing protocol, `www`, trailing slash, and tracking parameters.
- Maintain explicit alias mappings rather than relying only on fuzzy similarity.

### Automatic Match Requirements

An event may be attached automatically when one of these is true:

1. Exact canonical/legal/known-alias match plus matching official domain.
2. Exact legal/alias match in a government or regulator record plus corroborating address, company ID, product, or prior legal-name evidence.
3. Exact company name in a first-party company, investor, university, or government announcement.

### Manual Review Requirements

Require review when:

- The company name is short or generic.
- Two companies share the same normalized name.
- A regulator lists a parent, subsidiary, distributor, or foreign manufacturer rather than the target company.
- A funding article names a similarly named company in another country or sector.
- A company has rebranded, merged, or been acquired.
- Only fuzzy name similarity supports the match.

No ambiguous match should affect scoring before review.

## Track 1 — Hiring and Expansion

### Source Priority

1. Official company careers page.
2. Public structured ATS endpoint discovered from the official page.
3. Static or server-rendered first-party job pages.
4. Specialist boards such as BioSpace for discovery and corroboration.
5. LinkedIn Jobs, Indeed, Google Jobs, and similar aggregators for manual discovery only where automated access is not appropriate.

### Supported Structured ATS Routes

| ATS | Public route pattern | Method |
| --- | --- | --- |
| Greenhouse | `https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true` | Public Job Board API |
| Lever | `https://api.lever.co/v0/postings/{site}?mode=json` | Public Postings API |
| Ashby | `https://api.ashbyhq.com/posting-api/job-board/{board}` | Public Job Postings API |
| SmartRecruiters | `https://api.smartrecruiters.com/v1/companies/{company}/postings` | Public Posting API |
| Workable | Company-specific public careers/API route discovered from the official careers page | Validate per account before use |
| Recruitee | Company-specific public offers endpoint discovered from the official careers page | Validate per account before use |
| Workday/custom | Public rendered careers search | Bespoke adapter only; do not assume a universal endpoint |

Public API documentation:

- Greenhouse: https://developer.greenhouse.io/job-board.html
- Lever: https://github.com/lever/postings-api
- Ashby: https://developers.ashbyhq.com/docs/public-job-posting-api
- SmartRecruiters: https://developers.smartrecruiters.com/docs/endpoints

### Collection Workflow

1. Fetch the official homepage.
2. Find `Careers`, `Jobs`, `Join us`, or equivalent links.
3. Resolve redirects and detect the ATS provider/board slug.
4. Validate that the board belongs to the target company.
5. Pull all currently published jobs and follow pagination.
6. Preserve the raw total before relevance filtering.
7. Classify every relevant role using title, department, location, and description.
8. Compare with the prior snapshot to identify new and removed postings.
9. Aggregate company-level signals.

### Role Classification

| Role family | Indicative terms |
| --- | --- |
| Quality systems | Quality Engineer, QA Manager, Design Quality, Supplier Quality, QMS, ISO 13485 |
| Regulatory | Regulatory Affairs, Submission, Regulatory Strategy, Regulatory CMC, Market Authorization |
| Product/R&D | R&D Engineer, Product Development, Biomedical, Systems, Mechanical, Electrical, Firmware |
| V&V/design assurance | Verification, Validation, Test, Design Assurance, Software Quality |
| Clinical | Clinical Affairs, Clinical Operations, Clinical Research, Medical Affairs |
| Manufacturing | Manufacturing Engineer, Process Development, Design Transfer, Tech Transfer, Operations Scale-up |
| Software medical product | SaMD, IEC 62304, ML Validation, Cybersecurity, Product Safety |
| Commercial expansion | Country Manager, Market Access, Reimbursement, Implementation, Partnerships |

### Signal Strength

- **High:** senior QA/RA/clinical/product/manufacturing leader; three or more relevant open roles; or a new Canadian expansion team.
- **Medium:** one or two specific regulated-product roles.
- **Low:** generic software, sales, administrative, or research hiring without a clear regulated-product connection.

### Hiring Completeness Gate

Per company, store one state:

- `complete_matches`: careers source checked and relevant jobs found.
- `complete_zero`: verified official careers/ATS source successfully returned zero open jobs.
- `partial`: some pages/locations could not be traversed.
- `blocked`: access challenge or login prevented inspection.
- `no_careers_source`: no official careers route could be identified.
- `not_run`: company not yet attempted.

Zero jobs is only valid when the official source was successfully checked.

## Track 2 — Funding

### Source Priority

1. Company newsroom or press release.
2. Lead investor/funder announcement.
3. Government award or grants-and-contributions record.
4. Official accelerator/fund portfolio record.
5. SEDAR+ or exchange filing for public companies.
6. Reputable newswire or media report.
7. Google News RSS/search for discovery and triangulation.

### Canadian Funding Sources

- Existing Tier A investor adapters: Lumira, Genesys, Amplitude, BDC, FACIT, UCeed, and MEDTEQ+.
- Government of Canada proactive disclosure of grants and contributions: https://search.open.canada.ca/grants/
- NRC IRAP company announcements and program news.
- Regional development agencies: FedDev Ontario, PacifiCan, PrairiesCan, CED Québec, ACOA, FedNor, and CanNor.
- Provincial sources: Investissement Québec, Ontario Centre of Innovation, Alberta Innovates, and Innovate BC.
- Strategic Innovation Fund and other ISED announcements.
- Company and investor press releases distributed through CNW, GlobeNewswire, Business Wire, or equivalent.

### Collection Workflow

1. Search the company newsroom and known investor/funder sources.
2. Query exact company name and aliases with funding terms.
3. Capture each distinct event rather than only a single “total funding” value.
4. Prefer the announcement date; store closing date separately if published.
5. Record amount and currency exactly as stated.
6. Normalize to CAD only as an additional field, with the conversion date and rate source.
7. Extract stage only when explicitly stated or unambiguous from the primary evidence.
8. Capture use-of-funds language, especially hiring, product development, clinical work, regulatory work, manufacturing, and expansion.
9. Deduplicate syndicated versions of the same announcement.

### Funding Evidence Rules

- Investor portfolio membership alone means “investor-backed,” not a dated funding event.
- An undisclosed investment must remain amount/stage unknown.
- Government contributions, repayable contributions, grants, and loans must remain distinct.
- “Raised to date” must not be stored as the latest round amount.
- Conflicting amounts/stages remain separate evidence until reviewed.

### Funding Completeness Gate

- Every company receives a dated search/capture record even when no public event is found.
- Top-priority companies require at least one first-party or government source check.
- Events affecting score require high- or medium-confidence evidence.
- Funding recency is calculated from `event_date`, not from the article appearing in a current search.

## Track 3 — Regulatory Status

### Canada Sources

| Source | Use | Important limitation |
| --- | --- | --- |
| Health Canada MDALL/API | Active Class II–IV medical-device licences and product/manufacturer details | Class I devices and confidential pending applications are absent |
| Health Canada MDEL listing | Active establishment licences and authorized activities | Does not approve a particular Class II–IV product |
| Health Canada Clinical Trials Database/API | Canadian Phase I–III pharmaceutical and biologic trials | Not a comprehensive medical-device trial database |
| Health Canada recalls and safety alerts | Product-presence and post-market evidence | Negative/risk evidence, not a positive sales trigger |
| Drug and Health Product Submissions Under Review | Drug/biologic review activity | Not a complete medical-device submission feed |

Official sources:

- MDALL: https://health-products.canada.ca/mdall-limh/
- MDALL open API/data record: https://open.canada.ca/data/en/dataset/c801a084-210b-4cd2-8513-26a00b66eb6f
- MDEL: https://health-products.canada.ca/mdel-leim/
- Health Canada Clinical Trials API: https://health-products.canada.ca/api/clinical-trial/

### Other Jurisdictions

Use where relevant to a Canadian company:

- FDA 510(k), De Novo, PMA, device listing, and AI/ML-enabled device records.
- ClinicalTrials.gov API and trial registry.
- EU/UK regulatory claims only where supported by a regulator, notified-body certificate evidence, or a precise first-party announcement. A generic “CE ready” claim is not the same as CE certification.

### Collection Workflow

1. Generate regulator queries from legal name, aliases, former names, parent/subsidiary names, and product names.
2. Search company/manufacturer records first.
3. Retrieve licence/device/trial detail records.
4. Match using legal name plus company ID, address, product name, or documented corporate relationship.
5. Preserve every matching product/licence; do not collapse multiple licences into one field.
6. Separate active and archived records.
7. Store the regulator’s exact manufacturer name.
8. Route parent, distributor, and foreign-manufacturer matches to review.

### Regulatory Interpretation Rules

- MDALL presence is strong evidence of Canadian commercial maturity for a Class II–IV device.
- MDEL presence is operational/commercial evidence, not product approval.
- No MDALL match does not prove that a company is unregulated, pre-market, or inactive.
- Press-release claims of a submission are product-development evidence unless the regulator provides a public record.
- Recall evidence must be shown separately and should not automatically raise commercial-intent score.

### Regulatory Completeness Gate

- Query every known legal/alias name for prioritized medtech companies.
- Record query terms and result counts.
- Require a regulator URL/identifier before marking `licensed`, `cleared`, or `approved`.
- Mark ambiguous manufacturer matches `manual_review`; do not attach them automatically.

## Track 4 — Active Product Development

### Source Priority

1. Official product, technology, pipeline, clinical, and newsroom pages.
2. Regulatory and clinical-trial records.
3. Government grant project descriptions.
4. University, hospital, accelerator, and investor announcements.
5. Relevant job descriptions.
6. Patent records as supporting evidence only.
7. Reputable news reports.

### Product-Development Event Taxonomy

- Research concept or pre-company project
- Prototype or proof of concept
- Preclinical development
- Clinical study/trial started
- Clinical validation result
- Design verification/validation
- Regulatory submission claimed
- Licence/clearance/approval
- Product launch
- Design transfer or manufacturing scale-up
- Commercial pilot or health-system implementation
- Product partnership/licensing agreement
- New indication, feature, or geographic launch

### Evidence Rules

- Use the source’s wording; do not promote “pilot” to “clinical validation.”
- Hiring is supporting evidence of activity, not proof that a named product milestone occurred.
- A patent proves an IP event, not an active product, regulatory plan, or commercial launch.
- Grant project descriptions may indicate intended development but not completed milestones.
- Prefer events from the last 24 months; retain older regulatory and product-history records separately.

### Product-Development Completeness Gate

- Top-priority companies require review of homepage, product/technology page, newsroom, and clinical/trial page where present.
- Store checked URLs even if no material milestone is found.
- A product stage requires at least one dated source or a current first-party product/pipeline statement.

## Track 5 — Recent News

### Source Priority

1. Official company newsroom.
2. Government, regulator, clinical registry, investor, university, or hospital source.
3. Original newswire release.
4. Reputable sector/business media.
5. Google News RSS as discovery.

### Search Method

For each company and known alias, use bounded queries such as:

- `"{company}" funding OR raises OR investment`
- `"{company}" Health Canada OR FDA OR clearance OR licence`
- `"{company}" clinical trial OR validation OR study`
- `"{company}" launch OR product OR platform`
- `"{company}" manufacturing OR facility OR expansion`
- `"{company}" partnership OR hospital OR deployment`
- `site:{official_domain} news OR press OR blog`

### News Filtering

Accept an article only when:

- The exact company/alias is in the title or body; and
- The geography, product, people, domain, or investor context confirms identity; and
- The event falls within an allowed enrichment category.

Reject:

- Passing mentions without a company event.
- Duplicate syndications when the original release is available.
- SEO/listicle content without primary evidence.
- Articles about a different same-name company.
- Undated pages unless they describe a current first-party product state.

### News Deduplication

Canonical event key:

`company_id + event_type + normalized_event_date + primary_subject`

Also normalize:

- Tracking parameters
- Syndicated titles
- Newswire mirrors
- Updated/reposted company releases

Keep the best primary URL and optional corroborating URLs.

## Evidence Confidence

### High

- Government/regulator database record
- Official company announcement
- Official investor/funder announcement
- Clinical registry record
- Exact public ATS job record

### Medium

- Official university, hospital, accelerator, or partner announcement
- Original newswire release
- Reputable media with named sources and specific event details

### Low

- Search snippet without accessible evidence
- Aggregator-only claim
- Fuzzy name match
- Undated or vague marketing statement

Low-confidence evidence may guide manual research but must not independently create a high-priority score.

## Access and Scraping Methodology

Use the least fragile permitted route:

1. Official open API or downloadable dataset.
2. Structured JSON embedded in a first-party page.
3. Static HTML with a bespoke source adapter.
4. Sitemap, RSS/Atom feed, pagination, or archive.
5. Browser-rendered public page when JavaScript is required.
6. Manual review when the source requires a challenge, login, or unsupported interaction.

For every adapter:

- Use normal request rates and caching.
- Identify pagination and official denominators.
- Store raw response metadata and capture date.
- Retry transient errors conservatively.
- Return `INCOMPLETE` on partial traversal or unexplained count collapse.
- Never silently substitute a broad generic scraper.
- Never solve or bypass a CAPTCHA.

## Adapter Contract

Each source-specific enrichment adapter must provide:

- Unique adapter name and runner.
- Source URL and access route.
- Parser tests based on the real response shape.
- Pagination or archive traversal.
- Raw and accepted record counts.
- Explicit result status: complete, complete-zero, partial, blocked, or failed.
- Dated JSON snapshot and normalized output rows.
- Stable evidence identifiers where the source provides them.
- Deduplication without losing multiple evidence URLs.

## Testing and Completeness

Every adapter needs:

- Successful parser fixture.
- Pagination test.
- Zero-result test.
- Duplicate-event test.
- Alias/legal-name matching test.
- Ambiguous-name rejection test.
- Missing-field test.
- 403/access-error test producing an incomplete state.
- Count-collapse test.
- Runner test confirming evidence URLs, dates, confidence, and run log.

Run-level quality report:

| Metric | Requirement |
| --- | --- |
| Companies attempted | Exact denominator from canonical company table |
| Complete or complete-zero | Report count and percentage by enrichment track |
| Partial/blocked/not run | Report separately; never combine with zero |
| Evidence with dates | Percentage |
| Evidence with primary URLs | Percentage |
| Automatic ambiguous matches | Must be zero |
| Duplicate events | Report before/after counts |
| Stale records | Report by refresh policy |

## Refresh Cadence

| Track | Default cadence | Priority-company cadence |
| --- | --- | --- |
| Hiring | Weekly | Weekly |
| Funding | Monthly | Weekly news check |
| Regulatory | Monthly | Weekly after a known submission/launch signal |
| Clinical trials | Monthly | Weekly for active trials |
| Product development | Monthly | Weekly news check |
| General news | Monthly | Weekly |
| Employee band/location | Quarterly | Monthly after expansion or funding |

Historical records are append-only. Current-state fields are recomputed from the latest evidence.

## Prioritization

Use the 100-point model already recorded in `CANADA_MEDTECH_BIZDEV_SOURCE_INVENTORY.md`:

| Dimension | Weight |
| --- | ---: |
| Medtech / regulated-product fit | 25 |
| Commercial intent | 20 |
| Funding and ability to buy | 20 |
| Stage / size fit | 15 |
| Product/regulatory milestone | 10 |
| Source quality | 5 |
| Canada relevance | 5 |

Implementation rules:

- Calculate funding recency from dated events.
- Calculate hiring strength from open roles, not keyword mentions in unrelated text.
- Separate product approval from establishment licensing.
- Penalize acquired/inactive, wellness-only, non-health, pharma-only-without-relevant-platform, and 500+ employee companies.
- Retain the component scores and evidence used, not just the total.
- Review the top 50 before outreach.

## Spreadsheet Deliverable

### `Companies`

One row per canonical company with:

- Company, website, city, province, Canada relationship
- Product category and summary
- Employee band and stage
- Latest funding date, amount, stage, and investors
- Open jobs and strongest hiring signal
- Health Canada/FDA/EU/UK regulatory summary
- Latest product-development milestone
- Latest material news
- Priority score, band, and review status
- Evidence freshness and unresolved flags

### Supporting Tabs

- `Source Provenance`
- `Hiring Evidence`
- `Funding Events`
- `Regulatory Evidence`
- `Product & News Events`
- `Alias Review`
- `Incomplete & Blocked Sources`
- `Run Summary`

The supporting tabs remain the audit trail; the company row contains concise derived summaries.

## Implementation Work Packages

### Work Package 1 — Consolidation and Identity

- Build canonical Canada company table from all dated source snapshots.
- Resolve websites/domains and aliases.
- Add evidence/completeness schemas.
- Produce duplicate and ambiguous-name review files.

### Work Package 2 — Hiring

- **Status: complete (2026-07-28).** Final official-only output: 53 open roles across 32 companies; unconfirmed and blocked cases remain in an explicit review backlog.
- Discover official careers routes for every company with a website.
- Use existing Greenhouse, Lever, Ashby, Workable, SmartRecruiters, and Recruitee parsers where applicable.
- Add company-targeted board discovery rather than broad global job scraping.
- Add custom careers-page adapters only where needed.
- Snapshot and score relevant current roles.

### Work Package 3 — Funding

- Convert existing investor/funder provenance into backing evidence.
- Add event extraction from company/investor announcements and government disclosure.
- Add dated amount/stage/use-of-funds fields.
- Separate portfolio presence from funding events.

### Work Package 4 — Regulatory

- Build Health Canada MDALL API adapter first.
- Add MDEL company lookup.
- Add Health Canada clinical-trial API for relevant drug/biologic companies.
- Reuse/add FDA adapters for Canadian companies with US activity.
- Add strict legal-manufacturer matching and manual review.

### Work Package 5 — Product Development and News

- Resolve company newsroom/product/pipeline feeds.
- Run bounded company-specific Google News RSS searches.
- Classify and deduplicate material events.
- Review the highest-scoring 50 companies first.

### Work Package 6 — Presentation

- Generate the filterable workbook.
- Add component scores and evidence hyperlinks.
- Add completeness and freshness reporting.
- Produce a concise top-prospect review tab.

## Definition of Done

- Every canonical company has a per-track completeness state.
- Every material claim has an evidence URL, evidence date, and capture date.
- Hiring signals come from currently open official postings.
- Funding recency, stage, and amount are parsed where published.
- Regulatory claims require regulator records or are clearly labelled company claims.
- Product-development stages are evidence-bound and not inflated.
- News is identity-checked and event-deduplicated.
- Blocked and manual sources are explicit.
- All adapters pass count, error, identity, and regression tests.
- The workbook is filterable, auditable, and suitable for prioritizing the top 50 Canadian prospects.

## Related Documents

- `CANADA_MEDTECH_BIZDEV_SOURCE_INVENTORY.md`
- `CANADA_TIER_A_ADAPTER_PLAN.md`
- `PIPELINE_EXPLAINER.md`
- `LEAD_SCORING_RULES.md`
- `LEAD_CLASSIFICATION_RULES.md`
