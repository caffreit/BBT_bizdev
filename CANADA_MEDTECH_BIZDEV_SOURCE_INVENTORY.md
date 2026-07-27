# Canada Medtech / Biotech Business-Development Source Inventory

First-pass source map for finding Canadian medtech, diagnostics, digital-health, and product-development-led biotech companies. The aim is to produce client prospects, not a general ecosystem directory.

## Recommended Work Order

1. **Ecosystem discovery:** extract companies from health accelerators, startup hubs, and university spinout portfolios.
2. **Commercial-intent enrichment:** attach funding stage, latest funding date, estimated employee band, and active hiring signals.
3. **Prioritisation:** rank companies, then review regulatory/product-development news only for the best prospects.

This order avoids broad news scraping before there is a credible company universe.

The operational methodology for steps 2–3 is in
[`CANADA_COMPANY_ENRICHMENT_PLAN.md`](CANADA_COMPANY_ENRICHMENT_PLAN.md).

## Priority 1 — Accelerators, Hubs, and Commercialisation Platforms

| Tier | Organisation / source | Geography | Why it matters | Lead access |
| --- | --- | --- | --- | --- |
| A | MaRS Health Sciences / VentureConnect | Toronto / national | 42-company curated Health showcase plus 508 companies under VentureConnect’s Healthcare & Life Sciences parent filter; companies range from startup to scale-up | Official 42-company API; verified browser-assisted 508-company directory pending a stable automated data route |
| A | University of Toronto Entrepreneurship + Technology & Startup Explorer | Toronto | 171/171 official Health & Life Sciences directory records collected through the public REST endpoint; 167 unique company names after four duplicated profiles | Dedicated REST adapter plus dated JSON/CSV snapshot |
| A | Toronto Innovation Acceleration Partners (TIAP) | Toronto | 57/57 official portfolio companies collected: 41 active and 16 exited; 45 company websites available | Dedicated static-page adapter plus dated JSON/CSV snapshot |
| A | adMare BioInnovations | Montréal / Vancouver / national | 52/52 official records collected: 39 companies helped build and 13 current/past accelerator companies; 43 websites, 39 LinkedIn pages, 48 descriptions | Dedicated portfolio/detail-page adapter plus dated JSON/CSV snapshot |
| A | Creative Destruction Lab – Health | Toronto / Vancouver | 226/226 unique health-related Canadian-site companies collected: 139 Toronto and 117 Vancouver, with 30-company overlap; 217 websites and 226 descriptions | Dedicated Canadian-site directory/detail-page adapter plus dated JSON/CSV snapshot; program location is not verified company headquarters |
| A | Centech – Medtech | Montréal | 95/95 BioTech, Digital Health, Medical Device, and Medtech program records collected, covering 92 unique companies; 88 websites, 82 LinkedIn pages, and 95 descriptions | Dedicated official-API adapter plus dated JSON/CSV snapshot |
| A | CTS Santé | Québec | 21/21 official health-technology portfolio companies collected; 12 websites and 20 descriptions | Dedicated sitemap/company-page adapter plus dated JSON/CSV snapshot |
| A | District 3 – Bio and Health | Montréal | 12/12 Healthcare or Biotech companies collected from all 25 live startup cards; the page’s “of 100” label is stale | Dedicated paginated directory adapter plus dated JSON/CSV snapshot |
| A | OBIO | Ontario / national | 25/25 publicly named WiHI and WeSEED cohort records collected, covering 24 unique company names | Dedicated official cohort-announcement adapter; no public all-member company directory |
| A | MEDTEQ+ | Québec / national | 17/17 company-level investment portfolio records collected; 145 live funded-project cards are separate project leads without consistently exposed company partners | Dedicated investment-portfolio adapter plus dated JSON/CSV snapshot |
| A | Innovate Calgary – Life Sciences / UCeed Health | Calgary | 42/42 Health Fund and Child Health and Wellness Fund records collected, covering 34 unique company names | Dedicated two-fund portfolio adapter plus dated JSON/CSV snapshot |
| A | Health Innovation Hub, University of Alberta | Edmonton | 44/44 official company-directory records collected; 31 company websites | Dedicated company-card adapter with ordinary browser-header access and official preview-host fallback |
| A | Innovation UBC | British Columbia | 152/152 Human Health companies collected from all 385 portfolio rows across seven pages: 124 spin-offs, 17 spin-off/supported ventures, and 11 supported ventures | Dedicated paginated exact-impact-area adapter plus dated JSON/CSV snapshot |
| B | Biomedical Zone | Toronto | Hospital-linked health-tech incubator associated with Toronto Metropolitan University and St. Michael’s | Alumni/company pages where current |
| B | Velocity | Waterloo | Large university-linked incubator; broad sector mix but good medtech engineering flow | Portfolio/founder stories |
| B | SFU VentureLabs | British Columbia | Science and technology venture support, including health companies | Client/company stories |
| B | Volta | Atlantic Canada | Major Atlantic startup hub; broad rather than health-specific | Cohorts and resident directory |
| B | Emergence Bioscience Business Incubator | Prince Edward Island / Atlantic | Specialist bioscience incubation | Client portfolio |
| B | Springboard Atlantic | Atlantic Canada | Commercialisation network spanning Atlantic universities and colleges | Institutional and company announcements |
| B | CDL Atlantic / CDL Vancouver health-relevant streams | Atlantic / BC | Selective science-led cohorts; filter by healthcare relevance | Cohort announcements |
| C | DMZ | Toronto | High-quality but broad technology accelerator; useful mainly for digital health | Portfolio |
| C | Communitech | Waterloo Region | Strong scale-up and hiring visibility, but broad sector coverage | Member/team and news sources |
| C | Invest Ottawa / Bayview Yards | Ottawa | Broad innovation hub with health and hospital connections | Company stories and program cohorts |

## Priority 1 — Universities and Hospital Spinout Sources

| Tier | Institution / cluster | Primary commercialisation source | Medtech / biotech rationale |
| --- | --- | --- | --- |
| A | University of Toronto + University Health Network + Sinai Health + SickKids + Sunnybrook | U of T IPO/Startup Explorer; TIAP; hospital innovation offices | Canada’s deepest academic-health cluster; devices, diagnostics, AI, therapeutics |
| A | UBC + BC Children’s + Vancouver Coastal Health | Innovation UBC portfolio | Strong biomedical engineering, digital health, genomics, diagnostics; public portfolio filters |
| A | McGill + McGill University Health Centre | McGill official IP-registered spinoff directory: 30/30 health-sector companies collected from 43/43 total | Large biomedical research base and strong Montréal life-sciences cluster |
| A | McMaster + Hamilton Health Sciences | McMaster official startup showcase: 24/24 unique companies across nine native health filters, audited against all 52/52 showcase records | Official startup showcase; strong health, diagnostics, engineering and hospital integration |
| A | University of Alberta + Alberta Health Services | Health Innovation Hub / TEC Edmonton legacy sources | Major health-research and AI cluster |
| A | University of Calgary + Alberta Health Services | Innovate Calgary / UCeed | Life-sciences commercialisation plus directly relevant venture funds |
| A | Université de Montréal + CHUM + Sainte-Justine | Shared Axelys public supported-startup index: 5/5 records and websites collected; institution of origin is not exposed | Large health-sciences research and hospital network; records remain cluster-level rather than being attributed without evidence |
| A | Université Laval + CHU de Québec | Shared Axelys public supported-startup index: 5/5 records and websites collected; institution of origin is not exposed | Strong optics, diagnostics, medical technology and health research; shared Axelys records are not duplicated |
| A | University of Waterloo | Velocity: 123/123 native Health companies collected from 548/548 records across seven pages, with all detail pages enriched; WatCo exposes technologies, not a public company directory | Exceptional engineering/startup output; Velocity affiliation is not treated as proof of Waterloo-owned IP |
| B | University of Ottawa + Ottawa Hospital Research Institute + CHEO | Innovation Support Services and hospital commercialisation | Devices, imaging, digital health, clinical research |
| B | Queen’s University | Queen’s Partnerships and Innovation | Health sciences, engineering, medical devices |
| B | Western University + Lawson Research Institute | WORLDiscoveries | Medical imaging, devices, health research |
| B | Dalhousie University + IWK + Nova Scotia Health | Dal Innovates / Springboard Atlantic | Principal Atlantic health-research cluster |
| B | Université de Sherbrooke | TransferTech Sherbrooke / ACET | Medical devices, engineering, life sciences |
| B | Toronto Metropolitan University + Unity Health | Biomedical Zone / Zone Learning | Hospital-connected digital health and devices |
| B | University of Manitoba | UM Knowledge Exchange / Manitoba health research ecosystem | Prairie health and diagnostics pipeline |
| C | Simon Fraser University | SFU VentureLabs / Technology Licensing Office | Useful secondary BC source; filter for health |
| C | University of Saskatchewan | Innovation Enterprise / VIDO ecosystem | Strong bioscience and infectious-disease research; more biotech than medtech |
| C | Memorial University | Springboard Atlantic / Memorial innovation | Smaller pipeline, useful for regional completeness |

### University Ranking Signals

Use these to rank institutions before extraction:

- Number of research-based startups/spinouts in the latest annual report.
- Public, company-level portfolio availability.
- Affiliated teaching hospitals and medical school.
- Biomedical research intensity and clinical-trial activity.
- Presence of biomedical engineering, diagnostics, imaging, robotics, or digital-health programs.
- Recent commercialisation funding and accelerator participation.

## Priority 2 — Investors and Funding Sources

### Specialist or High-Relevance Investors

| Tier | Investor / funder | Stage / relevance | Prospect-discovery use |
| --- | --- | --- | --- |
| A | Lumira Ventures | 59/59 official investments collected: 34 current and 25 exited; 22 records show Canadian headquarters or presence | Dedicated current/exited portfolio adapter plus dated JSON/CSV snapshot |
| A | Genesys Capital | 12/12 active healthcare investments collected with detail pages; placeholder and acquired/divested past-success cards excluded | Dedicated active-investment index/detail adapter plus dated JSON/CSV snapshot |
| A | Amplitude Ventures | 24/24 precision-medicine portfolio companies collected: 20 active and 4 exited | Dedicated embedded-data adapter plus dated JSON/CSV snapshot |
| A | BDC Capital Life Sciences Venture Fund | Newly launched fund has no named portfolio yet; 31/31 current direct BDC health/life-science companies collected across six official portfolio-sector filters | Dedicated filtered current-portfolio/detail adapter; fund-investment records excluded |
| A | FACIT | 56/56 company-like funded oncology entities collected from all 81 portfolio records; 25 institution-owned pre-company assets excluded | Dedicated full-portfolio adapter with explicit entity rule plus dated JSON/CSV snapshot |
| A | TIAP | Existing 57-company extraction is already TIAP’s funded/developed portfolio; no separate investor directory found | Reuse existing TIAP portfolio snapshot; do not duplicate |
| A | adMare Ventures / adMare programs | No separate public adMare Ventures investment directory found beyond the existing 52 company-creation/accelerator records | Reuse existing adMare snapshot; monitor for a distinct investment portfolio |
| A | UCeed Health / UCeed Child Health | Existing extraction already covers 42 funded records across the two health funds, representing 34 company names | Reuse existing UCeed investment snapshots; do not duplicate |
| A | MEDTEQ+ | Existing 17-company extraction came from the dedicated MEDTEQ+ funds investment portfolio | Reuse existing MEDTEQ+ investment snapshot; funded projects remain a separate lead type |
| A | Investissement Québec / BioMed Propulsion | Official reporting says 12 companies received historical BioMed Propulsion investment, but neither IQ nor Québec publishes a company-level directory; program intake is suspended | Documented manual/news treatment; no partial adapter presented as complete |
| B | Fonds de solidarité FTQ | Québec growth capital, including life sciences | Portfolio filter plus funding news |
| B | Desjardins Capital / Desjardins–Innovatech | Québec venture/growth investing, including health tech | Portfolio and deal announcements |
| B | Anges Québec / AQC Capital | Angel and seed deals; filter for health/life science | Investment announcements |
| B | Pender Ventures | Canadian health technology among broader B2B tech | Portfolio filtering |
| B | MaRS IAF | Ontario seed-stage health, IT and cleantech | Portfolio/investment announcements |
| B | StandUp Ventures | Seed investing in women-led companies; includes health | Portfolio filtering |
| B | Radical Ventures / Inovia / OMERS Ventures | Larger Canadian technology investors | Secondary source for AI/digital-health scale-ups only |
| C | Family offices | No dependable comprehensive public directory | Discover through cap-table/funding announcements; do not make this a first-pass source |

### Government, Grant, and Non-Dilutive Funding

| Priority | Source | Signal |
| --- | --- | --- |
| A | NRC Industrial Research Assistance Program (IRAP) | Company is actively conducting and staffing R&D |
| A | Innovative Solutions Canada | Challenge winners and funded SMEs provide named company leads |
| A | Genome Canada + regional genome centres | Genomics product/platform development and translational partnerships |
| A | MEDTEQ+ funded projects | Direct medtech R&D and commercialisation signal |
| A | OBIO programs and funded cohorts | Canadian health-science SMEs reaching investment/commercial milestones |
| A | Provincial agencies: Investissement Québec, Ontario Centre of Innovation, Alberta Innovates, Innovate BC | Named award recipients and project partners |
| B | CIHR | Best for investigator and university prioritisation; company leads appear mainly in partnered grants |
| B | NSERC Alliance / Lab to Market | University-industry partner and commercialisation signals |
| B | Regional development agencies: FedDev Ontario, PacifiCan, PrairiesCan, CED Québec, ACOA | Scale-up, manufacturing, hiring, and market-expansion awards |
| B | Strategic Innovation Fund | Usually later-stage/high-value expansion; fewer but stronger prospects |
| C | SR&ED tax credits | Strong conceptual signal but recipient-level data is not generally public |

## Priority 3 — Hiring and Expansion Signals

Hiring should enrich the company universe rather than discover every Canadian employer from scratch.

### Roles to Capture

| Signal family | Example job titles | Likely business need |
| --- | --- | --- |
| Quality systems | Quality Engineer, QA Manager, Design Quality, Supplier Quality, QMS Lead | ISO 13485/QMS buildout, design transfer, supplier control |
| Regulatory | Regulatory Affairs Specialist/Manager, Regulatory CMC, Submission Manager | Health Canada/FDA/CE submissions or market expansion |
| Product development | R&D Engineer, Biomedical Engineer, Systems Engineer, Mechanical/Electrical Engineer | Device/product development |
| Verification and validation | V&V Engineer, Test Engineer, Design Assurance, Software Quality | Design controls and evidence generation |
| Clinical | Clinical Affairs, Clinical Operations, Clinical Research, Medical Affairs | Trials, validation, evidence, launch preparation |
| Manufacturing | Manufacturing Engineer, Process Development, Tech Transfer, Operations Scale-up | Design transfer and production scale-up |
| Software medical product | SaMD, ML Validation, Cybersecurity, Product Safety, IEC 62304 | Regulated software development |
| Commercial expansion | Country Manager, Market Access, Reimbursement, Partnerships | Launch or geographic expansion |

### Sources and Method

1. Use official careers pages and structured ATS endpoints first: Greenhouse, Lever, Ashby, Workable, SmartRecruiters, and Recruitee.
2. Use LinkedIn Jobs and Indeed as discovery/validation sources, subject to access and terms.
3. Search specialist boards such as BioSpace plus incubator and portfolio job boards.
4. Capture title, location, posting date, department, URL, and keywords.
5. Score the **company-level pattern**, not a single job: three relevant roles or a senior QA/RA leader is stronger than one generic engineer.

## Company Prioritisation Model

Start with a transparent 100-point score:

| Dimension | Weight | High-score definition |
| --- | ---: | --- |
| Medtech / regulated-product fit | 25 | Medical device, diagnostic, SaMD, combination product, or enabling platform with regulated deliverable |
| Commercial intent | 20 | Relevant QA/RA/R&D/clinical/manufacturing hiring or explicit product-development milestone |
| Funding and ability to buy | 20 | Recent seed–Series C, meaningful non-dilutive award, or credible institutional backing |
| Stage / size fit | 15 | Approximately 20–500 employees; prioritise 20–200 first |
| Product/regulatory milestone | 10 | Clinical validation, submission, licence, trial, design transfer, or manufacturing scale-up |
| Source quality | 5 | Official portfolio, government award, regulator, or company primary source |
| Canada relevance | 5 | Canadian HQ or substantial Canadian product-development operation |

Apply exclusions/penalties for pharma-only discovery companies without a relevant device, platform, diagnostics, quality, or product-development requirement; wellness-only products; consultancies; acquired/inactive companies; and very large enterprises.

## Regulatory and Product-Development Signals

- **Health Canada Medical Devices Active Licence Listing (MDALL):** searchable by company/device/licence. Useful proof of an active licence and product maturity.
- **Medical Device Establishment Licence listing:** useful for manufacturers/importers/distributors but noisier for product-development prospects.
- **Drug and Health Product Submissions Under Review:** useful for drugs and biologics, not a complete medical-device submissions feed.
- **ClinicalTrials.gov and Health Canada clinical-trial databases:** useful for sponsors and active clinical development.
- **Recalls and safety alerts:** product-presence signal, but generally not a positive outreach trigger.
- **Company press releases, grant awards, trial registrations, patents, and partner announcements:** use after prioritisation.

Confidential applications in progress are not a dependable public lead source. MDALL is therefore an approval/licensing signal, not a comprehensive feed of pending submissions.

## Deliverables for the Three Tasks

### Task 1 — Ecosystem Company Universe

- Validate the public directory/cohort URL for every Tier A source.
- Extract company name, source, source URL, geography, cohort/year, description, and sector.
- Tag medtech, diagnostics, SaMD/digital health, biotech platform, therapeutics-only, and non-health.
- Deduplicate and retain provenance from every source.

### Task 2 — Funding Enrichment

- Extract specialist investor portfolios and named government award recipients.
- For each company capture latest round/award date, amount, stage, investors/funder, and evidence URL.
- Flag Seed–Series C and companies likely within 20–500 employees.

### Task 3 — Hiring Enrichment

- Resolve official company website and careers/ATS page.
- Pull currently open Canadian and remote-Canada roles.
- Classify QA, regulatory, clinical, V&V, R&D, manufacturing, and market-expansion signals.
- Re-rank the list and manually review the top 50 prospects.

## Initial Source Links

- MaRS Health Sciences: https://www.marsdd.com/myhealth/
- U of T Innovation & Partnerships / Startup Explorer: https://research.utoronto.ca/ipo
- Innovation UBC portfolio: https://innovation.ubc.ca/entrepreneurship-ventures/portfolio-companies
- McMaster Entrepreneurship: https://entrepreneurship.mcmaster.ca/
- University of Waterloo Entrepreneurship: https://uwaterloo.ca/entrepreneurship/
- District 3: https://www.district3.co/
- CTS Santé: https://ctssante.com/en/
- OBIO: https://www.obio.ca/
- Lumira Ventures: https://www.lumiraventures.com/
- BDC Life Sciences Venture Fund: https://www.bdc.ca/en/bdc-capital/venture-capital/funds/life-sciences-venture-fund
- Health Canada MDALL: https://health-products.canada.ca/mdall-limh/
- Government of Canada research funding: https://www.canada.ca/en/services/science/researchfunding.html
