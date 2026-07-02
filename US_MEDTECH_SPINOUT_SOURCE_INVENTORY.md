# US Medtech Spinout Source Inventory

This is the first-pass expansion target for US university and hospital-origin medtech leads. It is intentionally an inventory, not a new scraper build.

## Consolidated Prioritization Sources

| Source | Use | Pipeline treatment |
| --- | --- | --- |
| AUTM Licensing Survey / STATT | Rank institutions by tech-transfer, licensing, patent, and startup output. | Source inventory only; paid/subscription data is not a lead-ready company directory. |
| BRIMR NIH rankings | Prioritize biomedical-heavy universities, hospitals, departments, and PIs. | Source inventory only; ranking signal for institution selection. |

## US Institution Targets

| Cluster | Public source candidate | Automation status |
| --- | --- | --- |
| MIT / Harvard / MGB / Broad | MIT TLO, Harvard Innovation Labs, Mass General Brigham Innovation, Broad partnering | MIT TLO and Harvard i-lab directories verified as scrapeable HTML and wired into source-page extraction. Harvard i-lab is broader venture discovery, not guaranteed OTD spinout provenance. MGB/Broad remain inventory-only. |
| Johns Hopkins | Johns Hopkins Technology Ventures | Inventory added; portfolio page hit bot/CAPTCHA protection in direct fetch, so keep inventory-only pending browser/API/manual fallback. |
| Stanford | Stanford OTL plus StartX Med accelerator source | Inventory already present; StartX remains accelerator-led until a reliable directory is validated. |
| UCSF / UC Berkeley | UCSF Innovation Ventures, Berkeley IPIRA, Rosenman, SkyDeck | Inventory added/present; UCSF venture portfolio hit Cloudflare in direct fetch. Accelerator sources already exist for Rosenman and SkyDeck. |
| Mayo Clinic | Mayo business development plus Mayo Platform Accelerate | Inventory present; accelerator adapter already exists. |
| Penn / CHOP | Penn Center for Innovation, CHOP technology transfer | Inventory added; Penn portfolio hit bot/CAPTCHA protection in direct fetch. Pediatric and hospital-origin spinouts remain high-fit. |
| UW / Fred Hutch | UW CoMotion, Fred Hutch technology transfer | UW CoMotion startup directory found, but first pass did not expose normal company cards in static HTML. Keep inventory-only pending API/browser/manual fallback. |
| Michigan | U-M Innovation Partnerships | Inventory added; initial startup URL was not a stable static directory. Needs corrected ventures page/API validation or curated fallback. |
| Duke / UNC / NC State | Duke OTC, UNC Innovate Carolina, NC State commercialization | Inventory added; Duke hit bot protection, UNC startup database URL was not live, and NC State appears to route startups through Flintbox. Treat Triangle as a combined region. |
| UC San Diego / Scripps | UCSD innovation, Scripps technology development | Inventory added; strong diagnostics and translational biotech relevance. |
| Georgia Tech / Emory | Georgia Tech VentureLab, Emory OTT | Inventory added; Emory startup page is guidance/resources rather than a company directory. Good medtech engineering plus clinical pairing. |
| Columbia / Cornell / Weill Cornell / NYU | Columbia Technology Ventures, Cornell CTL, Weill Cornell CTL, NYU TOV | Inventory added; Cornell page currently looks news/guidance-like, not a full company directory. Prioritize health-specific company pages where available. |
| CMU / Pitt | CMU CTTEC, Pitt Innovation Institute | Inventory added; CMU page is startup-license guidance rather than a company directory. Strong AI, robotics, clinical, and device overlap. |
| Rice / Baylor / TMC / UT Austin / MD Anderson | Rice OTI, Baylor commercialization, TMC Innovation, UT Austin OTC, MD Anderson OTC | Inventory added; TMC company page is live and relevant but first static pass did not expose normal company cards. TMC accelerator source already exists separately. |
| Vanderbilt | Vanderbilt CTTC | Inventory added; ventures page is live but first static pass did not expose straightforward company cards. High-fit medical center commercialization source. |

## Next Adapter Gate

Only add `UNIVERSITY_SPINOUT_SOURCE_PAGES` entries after verifying that a page is an official company/startup/portfolio directory, not a homepage, news page, or commercialization guidance page. If the page is JS-rendered, sparse, protected, or PDF-only, use browser/API discovery or curated fallback rows instead of brittle extraction.

## Wired Pages

| Institution | Page | Shape | Status |
| --- | --- | --- | --- |
| MIT | https://tlo.mit.edu/industry-entrepreneurs/startups/ | Static HTML startup cards with internal profile links and health/technology tags. | Added to `UNIVERSITY_SPINOUT_SOURCE_PAGES` with `mit_spinouts`. |
| Harvard | https://innovationlabs.harvard.edu/ventures/ plus `/p2`-`/p4` | Static HTML venture cards with internal profile links and descriptions; broader than a pure OTD spinout list. | Added to `UNIVERSITY_SPINOUT_SOURCE_PAGES` with `harvard_ventures`. |

## Initial Live Check

Run on 2026-07-01 after wiring the two verified pages:

| Source | Hits | Sample companies |
| --- | ---: | --- |
| MIT spinouts | 3 | MuscleMetrix; Omnipulse Biosciences; Artificial Axon Labs |
| Harvard spinouts | 88 | Abscotx; Adolescent Health Champions; Adventus Robotics; AI Pathology; Aidra Health; Aira Health; Aldatu Biosciences; Vital Bites; Alvus Health; Anise Health |
