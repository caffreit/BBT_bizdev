from __future__ import annotations

from pathlib import Path

from .models import Source, TODAY


OUT = Path("BlueBridge_TOFU_BizDev_V1.xlsx")
USER_AGENT = "Mozilla/5.0 (compatible; BBT-bizdev-pipeline/1.0)"

CORE_SEARCH_QUERIES = [
    "MedTech AI Funding",
    "SaMD Series A",
    "medical device",
    "FDA clearance AI",
    "digital health regulatory clearance",
]

UNIVERSITY_SPINOUT_SEARCH_UNIVERSITIES = [
    "Trinity College Dublin",
    "RCSI",
    "UCD",
    "University of Galway",
    "University of Limerick",
    "University College Cork",
    "Queen's University Belfast",
    "University of Bristol",
    "University of Oxford",
    "University of Cambridge",
    "Imperial College London",
    "King's College London",
    "UCL",
    "University of Edinburgh",
    "University of Manchester",
    "University of Leeds",
    "University of Sheffield",
    "ETH Zurich",
    "KU Leuven",
    "EPFL",
    "Technical University of Denmark",
    "TU Delft",
    "Karolinska Institutet",
    "Technical University of Munich",
    "Stanford",
    "MIT",
    "Harvard",
    "Johns Hopkins",
    "Mayo Clinic",
    "UC Berkeley",
    "UCSF",
    "University of Pennsylvania",
    "University of Toronto",
]

UNIVERSITY_SPINOUT_SEARCH_PATTERNS = [
    '"{university}" spinout medical device',
    '"{university}" spinout digital health',
    '"{university}" spinout medtech',
    '"{university}" spinout diagnostics',
    '"{university}" "campus company" health',
    '"{university}" startup healthcare',
    '"{university}" startup "medical device"',
    '"{university}" commercialisation health startup',
]


def build_university_spinout_search_queries() -> list[str]:
    return [
        pattern.format(university=university)
        for university in UNIVERSITY_SPINOUT_SEARCH_UNIVERSITIES
        for pattern in UNIVERSITY_SPINOUT_SEARCH_PATTERNS
    ]


UNIVERSITY_SPINOUT_SEARCH_QUERIES = build_university_spinout_search_queries()
SEARCH_QUERIES = CORE_SEARCH_QUERIES

SOURCE_TYPE_ADAPTERS = {
    "Conference": "conference_page",
    "VC portfolio": "vc_portfolio_page",
    "Grant/funding": "grant_funding_page",
    "Regulatory database": "regulatory_page",
    "University/spinout": "university_spinout_page",
    "Jobs": "jobs_page",
}

DISCOVERY_TERMS = {
    "Accelerator": ["accelerator", "cohort", "startup", "health", "medtech", "medical device", "digital health", "diagnostic", "ai"],
    "Conference": ["exhibitor", "sponsor", "startup", "medtech", "medical device", "digital health", "diagnostic", "imaging", "ai"],
    "VC portfolio": ["portfolio", "investment", "company", "health", "medtech", "medical device", "digital health", "diagnostic", "ai"],
    "Grant/funding": ["grant", "award", "funding", "project", "health", "medtech", "medical device", "digital health", "diagnostic", "ai"],
    "Regulatory database": ["fda", "clearance", "cleared", "510(k)", "de novo", "medical device", "software", "ai", "diagnostic"],
    "University/spinout": ["spinout", "spin-off", "startup", "venture", "licensing", "innovation", "health", "medtech", "medical device", "digital health", "diagnostic", "ai"],
    "Jobs": ["regulatory", "quality", "design assurance", "v&v", "clinical", "medical device", "digital health", "ai"],
}

ADAPTER_STATUS_NAMES = {
    "yc_healthcare": "YC Healthcare directory adapter",
    "medtech_innovator": "MedTech Innovator adapter",
    "digitalhealth_london": "DigitalHealth.London adapter",
    "mayo_accelerate": "Mayo Clinic Platform Accelerate adapter",
    "eit_health_catapult": "EIT Health Catapult adapter",
    "bioinnovate_ireland": "BioInnovate Ireland adapter",
    "arc_hub_healthtech": "ARC Hub for HealthTech adapter",
    "health_innovation_hub_ireland": "Health Innovation Hub Ireland adapter",
    "dogpatch_ndrc": "Dogpatch Labs / NDRC adapter",
    "fountain_healthcare": "Fountain Healthcare Partners adapter",
    "seroba_life_sciences": "Seroba Life Sciences adapter",
    "atlantic_bridge": "Atlantic Bridge adapter",
    "tcd_spinouts": "Trinity university spinout adapter",
    "ucd_spinouts": "UCD university spinout adapter",
    "oxford_spinouts": "Oxford university spinout adapter",
    "cambridge_spinouts": "Cambridge university spinout adapter",
    "imperial_spinouts": "Imperial university spinout adapter",
    "bristol_spinouts": "Bristol university spinout adapter",
    "qubis_spinouts": "QUBIS university spinout adapter",
    "edinburgh_spinouts": "Edinburgh university spinout adapter",
    "university_spinout_directory": "University spinout directory adapter",
    "conference_page": "Conference page adapter",
    "vc_portfolio_page": "VC portfolio adapter",
    "grant_funding_page": "Grant/funding adapter",
    "regulatory_page": "Regulatory adapter",
    "jobs_page": "Jobs page adapter",
    "greenhouse_jobs": "Greenhouse jobs adapter",
    "lever_jobs": "Lever jobs adapter",
    "ashby_jobs": "Ashby jobs adapter",
    "workable_jobs": "Workable jobs adapter",
    "smartrecruiters_jobs": "SmartRecruiters jobs adapter",
    "recruitee_jobs": "Recruitee jobs adapter",
    "biospace_jobs": "BioSpace jobs adapter",
    "builtin_jobs": "Built In jobs adapter",
    "nhs_jobs": "NHS Jobs adapter",
    "generic_page_scan": "Generic page scan",
}

SOURCE_TRIGGER_TYPES = {
    "Accelerator": "Accelerator/cohort",
    "Conference": "Conference presence",
    "VC portfolio": "Investor backing",
    "Grant/funding": "Grant/public funding",
    "Regulatory database": "Regulatory listing",
    "University/spinout": "University/spinout origin",
    "Jobs": "Hiring signal",
}

LEAD_PERSONAS = [
    "Early startup",
    "Funded startup",
    "University/spinout",
    "Scaleup",
    "Established medtech",
    "Jobs-led capability gap",
    "Regulatory-led opportunity",
]

BBT_QUADRANTS = [
    "Advisory",
    "Design/dev",
    "Embedded support",
    "Regulatory/validation",
    "Commercial readiness",
]

LEAD_SECONDARY_TAGS = [
    "SaMD/AI",
    "Diagnostics",
    "Medical device",
    "Clinical validation",
    "Regulatory pathway",
    "QMS/quality",
    "Hiring gap",
    "Funding trigger",
    "Accelerator/cohort",
]

LEAD_ENRICHMENT_PROMPT_VERSION = "lead_enrichment_v1"
LEAD_ENRICHMENT_CACHE_DIR = ".lead_enrichment_cache"
LEAD_ENRICHMENT_API_KEY_ENV = "BBT_LEAD_ENRICHMENT_API_KEY"
LEAD_ENRICHMENT_MODEL_ENV = "BBT_LEAD_ENRICHMENT_MODEL"
LEAD_ENRICHMENT_DEFAULT_MODEL = "gemini-1.5-flash"
LEAD_ENRICHMENT_DISABLED_ENV = "BBT_LEAD_ENRICHMENT_DISABLED"
LEAD_ENRICHMENT_FETCH_EVIDENCE_ENV = "BBT_LEAD_ENRICHMENT_FETCH_EVIDENCE"

LINKEDIN_ENRICHMENT_CACHE_DIR = ".linkedin_enrichment_cache"
LINKEDIN_ENRICHMENT_CACHE_VERSION = "linkedin_enrichment_v1"
LINKEDIN_CONTACT_TARGET_YEAR = "2026"
LINKEDIN_ENRICHMENT_DISABLED_ENV = "BBT_LINKEDIN_ENRICHMENT_DISABLED"
LINKEDIN_SEARCH_MIN_INTERVAL_SECONDS = 1.25
LINKEDIN_MAX_TEAM_PAGES = 3

YC_ALGOLIA_APP_ID = "45BWZJ1SGC"
YC_ALGOLIA_API_KEY = "NzllNTY5MzJiZGM2OTY2ZTQwMDEzOTNhYWZiZGRjODlhYzVkNjBmOGRjNzJiMWM4ZTU0ZDlhYTZjOTJiMjlhMWFuYWx5dGljc1RhZ3M9eWNkYyZyZXN0cmljdEluZGljZXM9WUNDb21wYW55X3Byb2R1Y3Rpb24lMkNZQ0NvbXBhbnlfQnlfTGF1bmNoX0RhdGVfcHJvZHVjdGlvbiZ0YWdGaWx0ZXJzPSU1QiUyMnljZGNfcHVibGljJTIyJTVE"
YC_HEALTHCARE_QUERY = "Healthcare"
MEDTECH_INNOVATOR_PORY_CONFIG_ID = "66eb41bc87c0d05ea2b410b8"
MEDTECH_INNOVATOR_PORY_APP_URL = "https://medtechinnovator-portfolio.pory.app"
MEDTECH_INNOVATOR_PORY_RECORDS_URL = f"https://app.pory.dev/data/{MEDTECH_INNOVATOR_PORY_CONFIG_ID}/records"
MAYO_READER_PREFIX = "https://r.jina.ai/http://"
JOB_BOARD_ADAPTERS = {
    "lever_jobs": "lever",
    "ashby_jobs": "ashby",
    "workable_jobs": "workable",
    "smartrecruiters_jobs": "smartrecruiters",
    "recruitee_jobs": "recruitee",
}
MAX_MATCHED_JOBS_PER_COMPANY = 5
GREENHOUSE_SEARCH_QUERIES = [
    'site:boards.greenhouse.io regulatory "medical device"',
    'site:boards.greenhouse.io "regulatory affairs" medtech',
    'site:boards.greenhouse.io "quality engineer" medtech',
    'site:boards.greenhouse.io "design assurance" "medical device"',
    'site:boards.greenhouse.io "clinical validation" "digital health"',
    'site:boards.greenhouse.io "V&V" "medical device"',
    'site:boards.greenhouse.io SaMD FDA',
    'site:boards.greenhouse.io diagnostic imaging clinical',
]
BIOSPACE_SEARCH_QUERIES = [
    "regulatory affairs",
    "quality engineer",
    "design assurance",
    "clinical validation",
    "medical device",
    "SaMD",
    "FDA",
    "diagnostic imaging",
    "clinical quality",
]
BUILTIN_SEARCH_QUERIES = [
    "regulatory affairs",
    "quality engineer",
    "clinical",
    "healthcare",
    "machine learning healthcare",
    "data healthcare",
    "AI clinical",
]
NHS_SEARCH_QUERIES = [
    "clinical safety",
    "clinical informatics",
    "digital health",
    "clinical systems",
    "quality improvement",
    "patient safety",
    "clinical governance",
    "AI",
]

ACCELERATOR_SOURCE_PAGES = {
    "MedTech Innovator": ["https://medtechinnovator.org/2026cohort/", "https://medtechinnovator.org/portfolio/"],
    "DigitalHealth.London Accelerator": ["https://digitalhealth.london/innovation-directory/companies"],
    "Mayo Clinic Platform Accelerate": ["https://www.mayoclinicplatform.org/focus-areas/digital-health/accelerate/accelerate-cohort-landing-page/"],
    "EIT Health Catapult": ["https://eithealth.eu/programmes/catapult/"],
    "BioInnovate Ireland": ["https://www.bioinnovate.ie/bioinnovate/alumni/", "https://www.bioinnovate.ie/bioinnovate/alumni/directory/"],
    "ARC Hub for HealthTech": ["https://www.universityofgalway.ie/innovation/", "https://www.universityofgalway.ie/our-research/"],
    "Health Innovation Hub Ireland": ["https://hih.ie/product-portfolio/", "https://hih.ie/case-studies/"],
    "Dogpatch Labs / NDRC": [
        "https://www.ndrc.ie/accelerator-cohort-2025",
        "https://www.ndrc.ie/accelerator-cohort-2024-h2",
        "https://www.ndrc.ie/accelerator-cohort-2024-h1",
        "https://www.ndrc.ie/accelerator-cohort-2023-h2",
        "https://www.ndrc.ie/accelerator-cohort-2023-h1",
        "https://www.ndrc.ie/accelerator-cohort-2022-h2",
        "https://www.ndrc.ie/accelerator-cohort-2022-h1",
        "https://www.ndrc.ie/accelerator-cohort-2021",
    ],
    "TMC Innovation": ["https://www.tmc.edu/innovation/accelerator-healthtech/"],
    "Techstars Healthcare": ["https://www.techstars.com/portfolio"],
    "StartX Med": ["https://startx.com/companies"],
    "MassChallenge HealthTech": ["https://masschallenge.org/startups/"],
    "Plug and Play Health": ["https://www.plugandplaytechcenter.com/health/"],
}

UNIVERSITY_SPINOUT_ADAPTERS = {
    "tcd_spinouts",
    "ucd_spinouts",
    "oxford_spinouts",
    "cambridge_spinouts",
    "imperial_spinouts",
    "bristol_spinouts",
    "qubis_spinouts",
    "edinburgh_spinouts",
    "university_spinout_directory",
}

UNIVERSITY_SPINOUT_SOURCE_PAGES = {
    # Only add verified company/alumni/portfolio directory pages here.
    # Homepages, news pages, commercialisation guidance pages, and guessed URLs stay out.
    "Trinity College Dublin spinouts": [
        "https://www.tcd.ie/innovation/portal/entrepreneurship/launchbox/launchbox-alumni/",
        "https://www.abven.com/university-bridge-fund/",
        "https://www.abven.com/university-bridge-fund/portfolio/",
    ],
    "RCSI spinouts": [
        "https://www.rcsi.com/dublin/research-and-innovation/innovation/investors-entrepreneurs-and-spin-outs",
    ],
    "UCD spinouts": [
        "https://www.ucd.ie/innovation/start-ups/novaucd-start-up-community/",
        "https://www.ucd.ie/innovation/start-ups/novaucd-alumni-community/",
    ],
    "University of Galway spinouts": [
        "https://www.bioinnovate.ie/bioinnovate/alumni/",
        "https://www.bioinnovate.ie/bioinnovate/about-us/eybioinnovatesocioeconomicimpactreport/",
        "https://www.abven.com/university-bridge-fund/portfolio/",
    ],
    "University of Oxford spinouts": [
        "https://innovation.ox.ac.uk/investing/our-portfolio-companies",
        "https://www.oxfordinnovationfinance.co.uk/portfolio/",
    ],
    "University of Cambridge spinouts": [
        "https://www.enterprise.cam.ac.uk/portfolio/",
    ],
    "Imperial College London spinouts": [
        "https://www.imperial.ac.uk/neurotechnology/spinouts-industry/spinouts/",
        "https://www.imperial.ac.uk/news/264937/imperial-founders-innovators-alumni-shine-forbes/",
    ],
    "University of Bristol spinouts": [
        "https://www.bristol.ac.uk/business/innovate-and-grow/research-commercialisation/our-spin-out-companies/all-spin-out-companies-list/",
    ],
    "Queen's University Belfast spinouts": [
        "https://www.qubis.co.uk/portfolio/all",
    ],
    "University of Edinburgh spinouts": [
        "https://bayes-centre.ed.ac.uk/programmes/vbi/cohorts",
        "https://bayes-centre.ed.ac.uk/programmes/vbi/cohorts/6.0",
        "https://edinburgh-innovations.ed.ac.uk/news?expertise=startups-and-spinouts#results",
        "https://www.ed.ac.uk/ai/ecosystem/entrepreneurial",
    ],
    "ETH Zurich spinouts": [
        "https://entrepreneurship.ethz.ch/startup-stories/explore-startup-portraits-and-success-stories/uebersicht-eth-spin-offs.html",
    ],
    "KU Leuven spinouts": [
        "https://lrd.kuleuven.be/en/spinoff/spin-off-companies",
    ],
    "EPFL spinouts": [
        "https://www.epfl.ch/innovation/startup/",
        "https://www.epfl-innovationpark.ch/companies/",
    ],
    "TU Delft spinouts": [
        "https://yesdelft.com/startups",
        "https://yesdelft.com/wp-json/wp/v2/startups?sectors=49&per_page=100",
    ],
    "Karolinska Institutet spinouts": [
        "https://www.kiinnovation.se/incubator-companies/",
    ],
}

CURATED_UNIVERSITY_SPINOUTS = {
    # Fallback rows for official pages that are sparse, JS-rendered, PDF-only, or
    # otherwise difficult to extract deterministically. These still enter the
    # normal Discovery Hits and Leads workbook sheets.
    "RCSI spinouts": [
        {"company": "Inthelia Therapeutics", "evidence_url": "https://www.rcsi.com/dublin/research-and-innovation/innovation/investors-entrepreneurs-and-spin-outs", "description": "RCSI spin-out developing therapeutics for sepsis.", "website": ""},
        {"company": "PrOBMet", "evidence_url": "https://www.rcsi.com/dublin/research-and-innovation/innovation/investors-entrepreneurs-and-spin-outs", "description": "RCSI spin-out developing precision oncology therapeutics.", "website": ""},
        {"company": "KelAda Pharmachem", "evidence_url": "https://www.rcsi.com/dublin/research-and-innovation/innovation/investors-entrepreneurs-and-spin-outs", "description": "RCSI spin-out focused on greener pharmaceutical manufacturing chemistry.", "website": ""},
        {"company": "Pumpinheart", "evidence_url": "https://www.rcsi.com/dublin/research-and-innovation/innovation/investors-entrepreneurs-and-spin-outs", "description": "RCSI spin-out developing an implantable cardiac assist device.", "website": ""},
        {"company": "OncoLize", "evidence_url": "https://www.rcsi.com/dublin/research-and-innovation/innovation/investors-entrepreneurs-and-spin-outs", "description": "RCSI spin-out developing targeted oncology drug delivery.", "website": "https://www.oncolize.com"},
        {"company": "Vertigenius", "evidence_url": "https://www.rcsi.com/dublin/research-and-innovation/innovation/investors-entrepreneurs-and-spin-outs", "description": "RCSI spin-out developing digital therapeutics for vertigo.", "website": ""},
        {"company": "Phyxiom", "evidence_url": "https://www.rcsi.com/dublin/research-and-innovation/innovation/investors-entrepreneurs-and-spin-outs", "description": "RCSI spin-out developing an AI respiratory care platform.", "website": ""},
        {"company": "LEP Biomedical", "evidence_url": "https://www.rcsi.com/dublin/research-and-innovation/innovation/investors-entrepreneurs-and-spin-outs", "description": "RCSI emerging spin-out targeting glaucoma post-surgery inflammation and fibrosis.", "website": ""},
        {"company": "Renovate Pharma", "evidence_url": "https://www.rcsi.com/dublin/research-and-innovation/innovation/investors-entrepreneurs-and-spin-outs", "description": "RCSI emerging spin-out developing inhaled antifibrotic respiratory therapeutics.", "website": ""},
        {"company": "Tympulse Medical", "evidence_url": "https://www.rcsi.com/dublin/research-and-innovation/innovation/investors-entrepreneurs-and-spin-outs", "description": "RCSI emerging spin-out developing tympanic membrane repair technology.", "website": ""},
        {"company": "DocLeaf", "evidence_url": "https://www.rcsi.com/dublin/research-and-innovation/innovation/investors-entrepreneurs-and-spin-outs", "description": "RCSI emerging spin-out developing chronic wound tissue repair device technology.", "website": ""},
    ],
    "Trinity College Dublin spinouts": [
        {"company": "ProVerum Medical", "evidence_url": "https://www.abven.com/university-bridge-fund/", "description": "University Bridge Fund evidence says ProVerum spun out from TCD; urology device company.", "website": "https://www.proverummedical.com"},
        {"company": "CroiValve", "evidence_url": "https://www.abven.com/university-bridge-fund/", "description": "University Bridge Fund evidence says CroiValve spun out of TCD; tricuspid valve medtech company.", "website": "https://www.croivalve.com"},
        {"company": "KineMo", "evidence_url": "https://www.tcd.ie/innovation/about/news-and-events/2024/sbp100/", "description": "Trinity campus company developing AI motion analysis for athletes and medical professionals.", "website": "https://www.kine-mo.com"},
    ],
    "University of Galway spinouts": [
        {"company": "Luminate Medical", "evidence_url": "https://www.bioinnovate.ie/bioinnovate/alumni/", "description": "University of Galway and BioInnovate-linked medtech company developing cancer-care devices.", "website": "https://www.luminatemed.com"},
        {"company": "Loci Orthopaedics", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "Medical device spin-off from KU Leuven and National University of Ireland Galway developing a thumb-base joint implant.", "website": "https://www.lociorthopaedics.com"},
        {"company": "Neurent Medical", "evidence_url": "https://www.abven.com/university-bridge-fund/portfolio/", "description": "Irish university spinout portfolio company developing chronic rhinitis treatment technology.", "website": "https://neurentmedical.com"},
        {"company": "Luma Vision", "evidence_url": "https://www.abven.com/university-bridge-fund/portfolio/", "description": "University-linked medtech company developing AI-driven cardiac imaging and data technology.", "website": "https://lumavision.com"},
    ],
    "ETH Zurich spinouts": [
        {"company": "Baxiva", "evidence_url": "https://ethz.ch/content/dam/ethz/associates/entrepreneurship-dam/documents/ETH_Ventures_Report_2025.pdf", "description": "ETH 2025 venture listed in biotechnology and pharmaceuticals context.", "website": ""},
        {"company": "DNAir", "evidence_url": "https://ethz.ch/content/dam/ethz/associates/entrepreneurship-dam/documents/ETH_Ventures_Report_2025.pdf", "description": "ETH 2025 spin-off candidate with DNA and diagnostics relevance.", "website": ""},
        {"company": "FY Cappa Biologics", "evidence_url": "https://ethz.ch/content/dam/ethz/associates/entrepreneurship-dam/documents/ETH_Ventures_Report_2025.pdf", "description": "ETH 2025 spin-off candidate in biologics.", "website": ""},
        {"company": "Immitra Bio", "evidence_url": "https://ethz.ch/content/dam/ethz/associates/entrepreneurship-dam/documents/ETH_Ventures_Report_2025.pdf", "description": "ETH 2025 spin-off candidate in biotechnology.", "website": ""},
        {"company": "Kalligo Medical", "evidence_url": "https://ethz.ch/content/dam/ethz/associates/entrepreneurship-dam/documents/ETH_Ventures_Report_2025.pdf", "description": "ETH 2025 start-up candidate with medical device relevance.", "website": ""},
        {"company": "MYNERVA", "evidence_url": "https://ethz.ch/content/dam/ethz/associates/entrepreneurship-dam/documents/ETH_Ventures_Report_2025.pdf", "description": "ETH 2025 spin-off developing neuro/medical technology.", "website": ""},
        {"company": "Nerai Bioscience", "evidence_url": "https://ethz.ch/content/dam/ethz/associates/entrepreneurship-dam/documents/ETH_Ventures_Report_2025.pdf", "description": "ETH 2025 spin-off candidate in bioscience.", "website": ""},
    ],
    "EPFL spinouts": [
        {"company": "MoleSense", "evidence_url": "https://actu.epfl.ch/news/smart-sweat-patch-helps-doctors-monitor-high-ris-2/", "description": "EPFL spin-off developing a sweat-biomarker patch for high-risk pregnancy monitoring.", "website": "https://www.molesense.ch"},
        {"company": "Volumina Medical", "evidence_url": "https://www.epfl.ch/innovation/startup/", "description": "EPFL Startup Launchpad example company in regenerative soft-tissue reconstruction.", "website": ""},
        {"company": "Distalmotion", "evidence_url": "https://www.epfl.ch/innovation/startup/", "description": "EPFL Startup Launchpad example company developing Dexter surgical robotics.", "website": "https://www.distalmotion.com"},
        {"company": "SwissIonics", "evidence_url": "https://actu.epfl.ch/news/three-ignition-grants-fueling-medical-innovation/", "description": "EPFL-based biotech startup developing RNA analytics for drug development and manufacturing.", "website": ""},
        {"company": "Juturna Bio", "evidence_url": "https://actu.epfl.ch/news/three-ignition-grants-fueling-medical-innovation/", "description": "EPFL medical innovation project developing gene therapy for Alzheimer's disease.", "website": ""},
        {"company": "PolyDefine", "evidence_url": "https://actu.epfl.ch/news/three-ignition-grants-fueling-medical-innovation/", "description": "EPFL medical innovation project developing polymer-lipid materials for RNA therapeutics.", "website": ""},
    ],
    "TU Delft spinouts": [
        {"company": "Neurophonic", "evidence_url": "https://yesdelft.com/startups/kneepkens-medical/", "description": "YES!Delft profile states this is a TU Delft spin-off developing tinnitus therapy.", "website": "https://neurophonic.io/"},
        {"company": "Corbotics", "evidence_url": "https://yesdelft.com/startups/corbotics/", "description": "YES!Delft Health and Pharma company developing an autonomous cardiac echo robot.", "website": "https://www.corbotics.com"},
        {"company": "Access2bone", "evidence_url": "https://yesdelft.com/startups/access2bone/", "description": "YES!Delft Health and Pharma company developing bone regeneration materials.", "website": "https://access2bone.com"},
        {"company": "RespiQ", "evidence_url": "https://yesdelft.com/startups/respiq/", "description": "YES!Delft Health and Pharma company developing breath analysis for COPD and other conditions.", "website": "https://respiq.com/"},
        {"company": "uPatch", "evidence_url": "https://yesdelft.com/startups/upatch/", "description": "YES!Delft Health and Pharma company developing microneedle delivery technology.", "website": "https://upatch.nl/"},
        {"company": "Momo Medical", "evidence_url": "https://yesdelft.com/startups/momo-medical/", "description": "YES!Delft Health and Pharma company developing pressure ulcer prevention and care workload tools.", "website": "https://momomedical.nl"},
    ],
    "KU Leuven spinouts": [
        {"company": "ADx NeuroSciences", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "KU Leuven LRD portfolio company developing dementia and neurodegenerative disease biomarkers and companion diagnostics.", "website": "https://www.adxneurosciences.com"},
        {"company": "Aelin Therapeutics", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "KU Leuven LRD portfolio biotech company developing antibiotics and first-in-class therapeutics.", "website": "https://aelintx.com"},
        {"company": "ArtiQ", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "KU Leuven LRD portfolio company developing AI medical software for pulmonary function tests and lung disease diagnosis.", "website": "https://www.artiq.eu"},
        {"company": "AstriVax Therapeutics", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "KU Leuven LRD portfolio vaccine spin-off from the Rega Institute.", "website": "https://astrivax.com"},
        {"company": "Augustine Therapeutics", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "KU Leuven LRD portfolio biotech company developing neuromuscular disease therapeutics.", "website": "https://augustinetx.com"},
        {"company": "Brainphonics", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "KU Leuven LRD portfolio spin-off developing medical software for objective hearing diagnosis in children.", "website": "https://brainphonics.com"},
        {"company": "Cartagenia", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "KU Leuven LRD portfolio company providing genetic diagnostic interpretation software.", "website": "https://www.cartagenia.com"},
        {"company": "CoMoveIT", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "KU Leuven LRD portfolio spin-off developing smart wheelchair control using sensors and AI.", "website": "https://comoveit.com"},
        {"company": "Gynaia", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "KU Leuven LRD portfolio spin-off developing AI diagnostics in gynecology and oncology.", "website": "https://www.gynaia.com"},
        {"company": "Hemastatx", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "KU Leuven LRD portfolio spin-off developing therapeutics for severe bleeding disorders.", "website": "https://www.hemastatx.com"},
        {"company": "icometrix", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "KU Leuven LRD portfolio company developing biomedical image analysis software.", "website": "https://www.icometrix.com"},
        {"company": "InnVentAir", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "KU Leuven LRD portfolio company developing AI-supported mechanical ventilation technology.", "website": "https://www.innventair.com"},
        {"company": "Pulsify Medical", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "KU Leuven LRD portfolio company developing wearable ultrasound patches for cardiac monitoring.", "website": "https://pulsify-medical.com"},
        {"company": "Qaelum", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "KU Leuven LRD portfolio company developing radiology quality and patient safety software.", "website": "https://www.qaelum.com"},
        {"company": "VIPUN Medical", "evidence_url": "https://lrd.kuleuven.be/en/spinoff/spin-off-companies", "description": "KU Leuven LRD portfolio company developing a gastric monitoring system for medical nutrition decisions.", "website": "https://www.vipunmedical.com"},
    ],
    "Karolinska Institutet spinouts": [
        {"company": "3N Bio", "evidence_url": "https://www.kiinnovation.se/incubator-companies/", "description": "KI Innovation incubator company developing rapid antimicrobial resistance diagnostics.", "website": "https://www.3n-bio.com"},
        {"company": "AAX Biotech", "evidence_url": "https://www.kiinnovation.se/incubator-companies/", "description": "KI Innovation incubator biotech company developing antibody technologies for therapy.", "website": "https://www.aaxbiotech.com"},
        {"company": "AnaCardio", "evidence_url": "https://www.kiinnovation.se/incubator-companies/", "description": "KI Innovation incubator biopharmaceutical company developing heart failure therapeutics.", "website": "https://anacardio.com"},
        {"company": "AsthmaTuner", "evidence_url": "https://www.kiinnovation.se/incubator-companies/", "description": "KI Innovation incubator company developing digital health tools for asthma care.", "website": "https://asthmatuner.se"},
        {"company": "Clinsight", "evidence_url": "https://www.kiinnovation.se/incubator-companies/", "description": "KI Innovation incubator company developing prostate cancer diagnostics software.", "website": "https://www.clinsight.net"},
        {"company": "Collective Minds Radiology", "evidence_url": "https://www.kiinnovation.se/incubator-companies/", "description": "KI Innovation incubator company developing radiology collaboration and AI services.", "website": "https://www.cmrad.com"},
        {"company": "Eyedentity", "evidence_url": "https://www.kiinnovation.se/incubator-companies/", "description": "KI Innovation incubator company building eye diagnostics technology.", "website": "https://eyedentity.ai"},
        {"company": "FenoMark Diagnostics", "evidence_url": "https://www.kiinnovation.se/incubator-companies/", "description": "KI Innovation incubator company developing cancer treatment-matching diagnostics.", "website": "https://www.fenomarkdiagnostics.com"},
        {"company": "Geras Solutions", "evidence_url": "https://www.kiinnovation.se/incubator-companies/", "description": "KI Innovation incubator company developing dementia diagnostic support digital health tools.", "website": "https://gerassolutions.com"},
        {"company": "Gesynta Pharma", "evidence_url": "https://www.kiinnovation.se/incubator-companies/", "description": "KI Innovation incubator biotech company developing inflammation therapeutics.", "website": "https://www.gesynta.se"},
        {"company": "Microcardix", "evidence_url": "https://www.kiinnovation.se/incubator-companies/", "description": "KI Innovation incubator medtech company developing catheter-based biopsy technology.", "website": "https://www.microcardix.com"},
        {"company": "OneTwo Analytics", "evidence_url": "https://www.kiinnovation.se/incubator-companies/", "description": "KI Innovation incubator company developing diabetes digital decision support.", "website": "https://onetwo-analytics.com"},
        {"company": "StratiPath", "evidence_url": "https://www.kiinnovation.se/incubator-companies/", "description": "KI Innovation incubator company developing AI precision diagnostics for cancer treatment decisions.", "website": "https://www.stratipath.com"},
        {"company": "Thermaiscan", "evidence_url": "https://www.kiinnovation.se/incubator-companies/", "description": "KI Innovation incubator company developing portable AI thermal breast cancer pre-screening.", "website": "https://www.thermaiscan.com"},
        {"company": "Zerocyte", "evidence_url": "https://www.kiinnovation.se/incubator-companies/", "description": "KI Innovation incubator medtech company developing treatment for postpartum hemorrhage.", "website": "https://www.zerocyte.com"},
    ],
}

SOURCES: list[Source] = [
    Source("TIME HealthTech 2025", "Public ranking", "https://time.com/7318020/worlds-top-healthtech-companies-2025/", "Global", "High", "Annual", "Page scan", "Public ranking used as a discovery source for AI, diagnostics, wearables, and digital health companies.", "time_healthtech"),
    Source("Google News / web funding search", "News/search", "https://news.google.com/search?q=medtech%20AI%20medical%20device%20funding", "US/EU/global", "High", "Weekly", "Google News RSS query", "General public search for recent medtech, AI health, SaMD, device, diagnostics, and digital health funding announcements.", "google_news_search"),
    Source("FDA 510(k) database", "Regulatory database", "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm", "US", "High", "Monthly", "Database query/export", "Recent clearances and predicate/category intelligence for medical device and SaMD companies.", "regulatory_page"),
    Source("FDA De Novo database", "Regulatory database", "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/denovo.cfm", "US", "High", "Monthly", "Database query/export", "Recent De Novo decisions and novel device/software categories.", "regulatory_page"),
    Source("FDA AI/ML-enabled medical devices list", "Regulatory database", "https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-and-machine-learning-aiml-enabled-medical-devices", "US", "High", "Monthly", "Page/table extraction", "FDA-maintained list of AI/ML-enabled device authorizations.", "regulatory_page"),
    Source("MedTech Innovator", "Accelerator", "https://medtechinnovator.org/2026cohort/", "US/EU/global", "High", "Quarterly", "Cohort/company page extraction", "Medical device, diagnostic, and digital health startup source.", "medtech_innovator"),
    Source("Mayo Clinic Platform Accelerate", "Accelerator", "https://www.mayoclinicplatform.org/accelerate/", "US/global", "High", "Quarterly", "Cohort/company page extraction", "AI/digital health companies needing validation.", "mayo_accelerate"),
    Source("TMC Innovation", "Accelerator", "https://www.tmc.edu/innovation/accelerator-healthtech/", "US/global", "Medium", "Semiannual", "Cohort/company page extraction", "Texas Medical Center healthtech/medtech startups.", "accelerator_page"),
    Source("EIT Health Catapult", "Accelerator", "https://eithealth.eu/programmes/catapult/", "EU", "High", "Annual", "Finalist/cohort page extraction", "European health startups.", "eit_health_catapult"),
    Source("Y Combinator Healthcare", "Accelerator", "https://www.ycombinator.com/companies", "US/global", "Medium", "Quarterly", "YC Algolia company directory query", "Broad startup source; useful for AI health, care delivery, diagnostics, and workflow software.", "yc_healthcare"),
    Source("Techstars Healthcare", "Accelerator", "https://www.techstars.com/accelerators", "US/global", "Medium", "Quarterly", "Program/cohort extraction", "Healthcare and AI-health accelerator cohorts.", "accelerator_page"),
    Source("StartX Med", "Accelerator", "https://startx.com/", "US", "Medium", "Quarterly", "Portfolio/company extraction", "Stanford-associated health and medtech startups.", "accelerator_page"),
    Source("MassChallenge HealthTech", "Accelerator", "https://masschallenge.org/programs-healthtech/", "US/global", "Medium", "Annual", "Cohort extraction", "Healthtech startups with provider/payer partnerships.", "accelerator_page"),
    Source("Plug and Play Health", "Accelerator", "https://www.plugandplaytechcenter.com/health/", "US/global", "Medium", "Quarterly", "Portfolio/cohort extraction", "Corporate innovation and health startup pipeline.", "accelerator_page"),
    Source("DigitalHealth.London Accelerator", "Accelerator", "https://digitalhealth.london/programmes/accelerator/", "UK", "High", "Annual", "Cohort/company page extraction", "NHS-facing digital health accelerator with strong UK provider access.", "digitalhealth_london"),
    Source("NHS Innovation Accelerator", "Accelerator", "https://nhsaccelerator.com/", "UK", "High", "Annual", "Fellow/innovation page extraction", "NHS-backed innovation accelerator for adopted healthcare innovations.", "accelerator_page"),
    Source("NHS Clinical Entrepreneur Programme", "Accelerator", "https://nhscep.com/", "UK", "High", "Annual", "Programme/company page extraction", "NHS clinical founder programme with healthtech and medtech ventures.", "accelerator_page"),
    Source("Health Innovation Hub Ireland", "Accelerator", "https://hih.ie/product-portfolio/", "Ireland", "High", "Quarterly", "Innovation/company page extraction", "Irish healthcare innovation hub connected to hospitals and SMEs.", "health_innovation_hub_ireland"),
    Source("BioInnovate Ireland", "Accelerator", "https://www.bioinnovate.ie/", "Ireland", "High", "Annual", "Fellowship/company page extraction", "Irish needs-led medtech innovation programme.", "bioinnovate_ireland"),
    Source("ARC Hub for HealthTech", "Accelerator", "https://www.universityofgalway.ie/innovation/", "Ireland", "High", "Quarterly", "Commercialisation/company page extraction", "University of Galway healthtech commercialisation hub connected to BioInnovate and clinical trials.", "arc_hub_healthtech"),
    Source("Dogpatch Labs / NDRC", "Accelerator", "https://www.ndrc.ie/", "Ireland", "Medium", "Quarterly", "Portfolio/company page extraction", "Dogpatch-operated Irish national accelerator with occasional health and digital health companies.", "dogpatch_ndrc"),
    Source("Startupbootcamp Digital Health", "Accelerator", "https://www.startupbootcamp.org/accelerator/digital-health/", "EU/global", "High", "Annual", "Cohort/company page extraction", "Digital health-focused Startupbootcamp programme and alumni source.", "accelerator_page"),
    Source("NLC Health", "Accelerator", "https://nlc.health/", "EU", "High", "Quarterly", "Venture/company page extraction", "European healthtech venture builder focused on health innovations.", "accelerator_page"),
    Source("YES!Delft MedTech", "Accelerator", "https://www.yesdelft.com/", "EU", "Medium", "Quarterly", "Startup/company page extraction", "Dutch deeptech accelerator with medtech and health startups.", "accelerator_page"),
    Source("Bayer G4A", "Accelerator", "https://www.g4a.health/", "EU/global", "High", "Annual", "Startup/company page extraction", "Bayer digital health partnership and accelerator programme.", "accelerator_page"),
    Source("Roche Startup Creasphere", "Accelerator", "https://www.startupcreasphere.com/", "EU/global", "High", "Annual", "Startup/company page extraction", "Roche-backed digital health and diagnostics startup programme.", "accelerator_page"),
    Source("Novartis Biome", "Accelerator", "https://www.biome.novartis.com/", "EU/global", "Medium", "Quarterly", "Partner/company page extraction", "Novartis digital health innovation network and startup source.", "accelerator_page"),
    Source("Philips HealthWorks", "Accelerator", "https://www.philips.com/a-w/about/innovation/healthworks.html", "EU/global", "Medium", "Quarterly", "Startup/company page extraction", "Philips health innovation programme and venture collaboration source.", "accelerator_page"),
    Source("Health Venture Lab", "Accelerator", "https://www.healthventurelab.eu/", "EU", "Medium", "Annual", "Cohort/company page extraction", "European health venture builder and accelerator source.", "accelerator_page"),
    Source("EIT Health Wild Card", "Accelerator", "https://eithealth.eu/programmes/wild-card/", "EU", "Medium", "Annual", "Team/company page extraction", "EIT Health challenge-driven venture creation programme.", "accelerator_page"),
    Source("Cedars-Sinai Accelerator", "Accelerator", "https://www.cedars-sinai.edu/research/innovation/accelerator.html", "US", "High", "Annual", "Portfolio/company page extraction", "Provider-backed healthcare accelerator with clinical deployment relevance.", "accelerator_page"),
    Source("Dreamit Healthtech", "Accelerator", "https://www.dreamit.com/healthtech", "US", "High", "Annual", "Portfolio/company page extraction", "US healthtech accelerator and investor-backed startup source.", "accelerator_page"),
    Source("MATTER", "Accelerator", "https://matter.health/", "US/global", "High", "Quarterly", "Startup/member page extraction", "Healthcare startup hub and accelerator source.", "accelerator_page"),
    Source("Health Wildcatters", "Accelerator", "https://www.healthwildcatters.com/", "US", "High", "Annual", "Portfolio/company page extraction", "Healthcare and life-sciences accelerator with alumni companies.", "accelerator_page"),
    Source("Johnson & Johnson JLABS", "Accelerator", "https://jlabs.jnjinnovation.com/", "US/EU/Asia/global", "High", "Quarterly", "Company/resident page extraction", "Global life-sciences incubator and startup network.", "accelerator_page"),
    Source("Illumina Accelerator", "Accelerator", "https://www.illumina.com/science/accelerator.html", "US/UK", "High", "Annual", "Portfolio/company page extraction", "Genomics and diagnostics accelerator backed by Illumina.", "accelerator_page"),
    Source("IndieBio", "Accelerator", "https://indiebio.co/", "US/global", "Medium", "Annual", "Company page extraction", "SOSV biotech and life-sciences accelerator.", "accelerator_page"),
    Source("HAX", "Accelerator", "https://hax.co/", "US/Asia/global", "Medium", "Quarterly", "Portfolio/company page extraction", "SOSV hardtech accelerator relevant for connected devices and medtech hardware.", "accelerator_page"),
    Source("Fogarty Innovation", "Accelerator", "https://www.fogartyinnovation.org/", "US", "High", "Annual", "Company/program page extraction", "Medtech innovation incubator and company-building source.", "accelerator_page"),
    Source("UCSF Rosenman Institute", "Accelerator", "https://rosenmaninstitute.org/", "US", "High", "Annual", "Portfolio/company page extraction", "UCSF health technology accelerator and innovation network.", "accelerator_page"),
    Source("Berkeley SkyDeck", "Accelerator", "https://skydeck.berkeley.edu/", "US/global", "Medium", "Quarterly", "Portfolio/company page extraction", "University accelerator with healthtech, AI, and medical device startups.", "accelerator_page"),
    Source("MedTech Actuator", "Accelerator", "https://medtechactuator.com/", "Australia/Asia", "High", "Annual", "Portfolio/company page extraction", "Asia-Pacific medtech accelerator and venture source.", "accelerator_page"),
    Source("MedTech Innovator Asia Pacific", "Accelerator", "https://medtechinnovator.org/asia-pacific/", "Asia-Pacific", "High", "Annual", "Cohort/company page extraction", "Asia-Pacific medtech accelerator cohort source.", "accelerator_page"),
    Source("HealthTech Hub Africa", "Accelerator", "https://www.healthtechhubafrica.org/", "Africa/global", "Medium", "Annual", "Cohort/company page extraction", "Pan-African healthtech accelerator and innovation source.", "accelerator_page"),
    Source("Villgro Africa", "Accelerator", "https://www.villgroafrica.org/", "Africa/global", "Medium", "Annual", "Portfolio/company page extraction", "Healthcare and life-sciences impact accelerator in Africa.", "accelerator_page"),
    Source("SGInnovate", "Accelerator", "https://www.sginnovate.com/", "Asia", "Medium", "Quarterly", "Startup/company page extraction", "Singapore deeptech innovation source with medtech and health AI companies.", "accelerator_page"),
    Source("Trinity College Dublin spinouts", "University/spinout", "https://www.tcd.ie/innovation/", "Ireland", "High", "Quarterly", "Spinout/company page review", "TCD innovation and spinout pipeline; useful for very early Irish medtech, diagnostics, AI, and digital health ventures.", "tcd_spinouts"),
    Source("RCSI spinouts", "University/spinout", "https://www.rcsi.com/innovation", "Ireland", "High", "Quarterly", "Spinout/company page review", "Health-sciences university source for clinician-led and translational healthcare ventures."),
    Source("UCD spinouts", "University/spinout", "https://www.ucd.ie/innovation/", "Ireland", "High", "Quarterly", "Spinout/company page review", "Irish university innovation source with life-sciences, diagnostics, medtech, and software spinouts.", "ucd_spinouts"),
    Source("University of Galway spinouts", "University/spinout", "https://www.universityofgalway.ie/innovation/", "Ireland", "High", "Quarterly", "Spinout/company page review", "Galway medtech cluster university source for early device and health innovation companies."),
    Source("University of Limerick spinouts", "University/spinout", "https://www.ul.ie/research/innovation", "Ireland", "Medium", "Quarterly", "Spinout/company page review", "Irish research and innovation source for early health, engineering, and device-adjacent companies."),
    Source("University College Cork spinouts", "University/spinout", "https://www.ucc.ie/en/innovation/", "Ireland", "High", "Quarterly", "Spinout/company page review", "Irish university innovation source with health, diagnostics, medtech, and digital health spinouts."),
    Source("Queen's University Belfast spinouts", "University/spinout", "https://www.qubis.co.uk/portfolio/all", "Ireland/UK", "Medium", "Quarterly", "Spinout/company page review", "QUBIS portfolio source for Queen's University Belfast spinouts, including life-sciences, diagnostics, digital, and health ventures.", "qubis_spinouts"),
    Source("University of Oxford spinouts", "University/spinout", "https://innovation.ox.ac.uk/", "UK", "High", "Quarterly", "Spinout/company page review", "Oxford University Innovation source for deeptech, life-sciences, AI, diagnostics, and medical technology spinouts.", "oxford_spinouts"),
    Source("University of Cambridge spinouts", "University/spinout", "https://www.enterprise.cam.ac.uk/", "UK", "High", "Quarterly", "Spinout/company page review", "Cambridge Enterprise source for early science, engineering, AI, and healthcare spinouts.", "cambridge_spinouts"),
    Source("Imperial College London spinouts", "University/spinout", "https://www.imperial.ac.uk/enterprise/", "UK", "High", "Quarterly", "Spinout/company page review", "Imperial Enterprise source for healthtech, medtech, diagnostics, AI, and engineering spinouts.", "imperial_spinouts"),
    Source("University of Bristol spinouts", "University/spinout", "https://www.bristol.ac.uk/business/innovate-and-grow/research-commercialisation/our-spin-out-companies/all-spin-out-companies-list/", "UK", "High", "Quarterly", "Spinout/company page review", "University of Bristol spinout company list with biotech, diagnostics, device, imaging, and health ventures.", "bristol_spinouts"),
    Source("King's College London spinouts", "University/spinout", "https://www.kcl.ac.uk/business/commercialisation", "UK", "High", "Quarterly", "Spinout/company page review", "KCL commercialisation source for translational health, clinical, and digital ventures."),
    Source("UCL spinouts", "University/spinout", "https://www.uclb.com/", "UK", "High", "Quarterly", "Spinout/company page review", "UCL Business source for life-sciences, health AI, diagnostics, and medical technology spinouts."),
    Source("University of Edinburgh spinouts", "University/spinout", "https://edinburgh-innovations.ed.ac.uk/", "UK", "Medium", "Quarterly", "Spinout/company page review", "Edinburgh Innovations and Bayes Centre source for AI, data, health, and life-sciences startups and spinouts.", "edinburgh_spinouts"),
    Source("University of Manchester spinouts", "University/spinout", "https://www.manchester.ac.uk/collaborate/business-engagement/commercialisation/", "UK", "Medium", "Quarterly", "Spinout/company page review", "Manchester commercialisation source for diagnostics, materials, health, and engineering spinouts."),
    Source("University of Leeds spinouts", "University/spinout", "https://www.leeds.ac.uk/business-commercialisation", "UK", "Medium", "Quarterly", "Spinout/company page review", "Leeds commercialisation source for healthcare, engineering, and life-sciences spinouts."),
    Source("University of Sheffield spinouts", "University/spinout", "https://www.sheffield.ac.uk/business/spinouts", "UK", "Medium", "Quarterly", "Spinout/company page review", "Sheffield spinout source for health, advanced manufacturing, and engineering-led ventures."),
    Source("ETH Zurich spinouts", "University/spinout", "https://ethz.ch/en/industry/entrepreneurship/spin-offs.html", "Europe", "High", "Quarterly", "Spinout/company page review", "ETH spin-off source for deeptech, AI, medical device, diagnostics, and health ventures."),
    Source("KU Leuven spinouts", "University/spinout", "https://lrd.kuleuven.be/en/spinoff", "Europe", "High", "Quarterly", "Spinout/company page review", "KU Leuven Research & Development spin-off source for health, diagnostics, medtech, and biotech ventures."),
    Source("EPFL spinouts", "University/spinout", "https://www.epfl.ch/innovation/startups/", "Europe", "High", "Quarterly", "Spinout/company page review", "EPFL startup source for deeptech, medical technology, AI, and diagnostics ventures."),
    Source("Technical University of Denmark spinouts", "University/spinout", "https://www.dtu.dk/english/collaboration/innovation-and-entrepreneurship", "Europe", "Medium", "Quarterly", "Spinout/company page review", "DTU innovation source for medtech, diagnostics, engineering, and digital health companies."),
    Source("TU Delft spinouts", "University/spinout", "https://www.tudelft.nl/en/innovation-impact/", "Europe", "Medium", "Quarterly", "Spinout/company page review", "TU Delft innovation source for medical technology, robotics, AI, and engineering spinouts."),
    Source("Karolinska Institutet spinouts", "University/spinout", "https://karolinskainnovations.ki.se/", "Europe", "High", "Quarterly", "Spinout/company page review", "Karolinska Innovations source for translational medicine, diagnostics, and digital health companies."),
    Source("Technical University of Munich spinouts", "University/spinout", "https://www.tum.de/en/innovation/entrepreneurship", "Europe", "Medium", "Quarterly", "Spinout/company page review", "Additional European deeptech and health innovation source with strong entrepreneurship pipeline."),
    Source("Stanford spinouts", "University/spinout", "https://otl.stanford.edu/", "US", "High", "Quarterly", "Spinout/company page review", "Stanford OTL source for health AI, medtech, diagnostics, and life-sciences ventures."),
    Source("MIT spinouts", "University/spinout", "https://tlo.mit.edu/", "US", "High", "Quarterly", "Spinout/company page review", "MIT Technology Licensing source for AI, engineering, device, diagnostics, and health spinouts."),
    Source("Harvard spinouts", "University/spinout", "https://otd.harvard.edu/", "US", "High", "Quarterly", "Spinout/company page review", "Harvard OTD source for translational healthcare, diagnostics, digital health, and life-sciences ventures."),
    Source("Johns Hopkins spinouts", "University/spinout", "https://ventures.jhu.edu/", "US", "High", "Quarterly", "Spinout/company page review", "Johns Hopkins Technology Ventures source for clinical, medtech, diagnostics, and digital health spinouts."),
    Source("Mayo Clinic spinouts", "University/spinout", "https://businessdevelopment.mayoclinic.org/", "US", "High", "Quarterly", "Spinout/company page review", "Mayo Clinic business development and ventures source for clinically grounded health companies."),
    Source("UC Berkeley spinouts", "University/spinout", "https://ipira.berkeley.edu/", "US", "Medium", "Quarterly", "Spinout/company page review", "UC Berkeley IPIRA source for AI, engineering, biology, and health-adjacent spinouts."),
    Source("UCSF spinouts", "University/spinout", "https://innovation.ucsf.edu/", "US", "High", "Quarterly", "Spinout/company page review", "UCSF Innovation Ventures source for translational medicine, digital health, and medtech spinouts."),
    Source("University of Pennsylvania spinouts", "University/spinout", "https://pci.upenn.edu/", "US", "Medium", "Quarterly", "Spinout/company page review", "Additional US translational healthcare and life-sciences commercialization source."),
    Source("University of Toronto spinouts", "University/spinout", "https://research.utoronto.ca/innovation-partnerships", "Canada", "High", "Quarterly", "Spinout/company page review", "U of T innovation and partnership source for AI, medtech, diagnostics, and health spinouts."),
    Source("The MedTech Conference", "Conference", "https://themedtechconference.com/", "US/global", "High", "Annual", "Exhibitor/company directory extraction", "US/global medtech exhibitors, sponsors, startups, and presenting companies.", "conference_page"),
    Source("MEDICA exhibitor index", "Conference", "https://www.medica-tradefair.com/", "Global", "High", "Annual", "Exhibitor directory extraction", "Large global medical technology exhibitor universe.", "conference_page"),
    Source("MedTech Forum", "Conference", "https://www.themedtechforum.eu/", "EU", "High", "Annual", "Sponsor/exhibitor extraction", "European medical technology industry source.", "conference_page"),
    Source("RSNA exhibitors", "Conference", "https://www.rsna.org/annual-meeting", "Global", "High", "Annual", "Exhibitor/category extraction", "Radiology, imaging AI, and diagnostic software companies.", "conference_page"),
    Source("HLTH exhibitors/sponsors", "Conference", "https://www.hlth.com/", "US/global", "Medium", "Annual", "Sponsor/exhibitor extraction", "Digital health and AI health ecosystem.", "conference_page"),
    Source("ViVE exhibitors/sponsors", "Conference", "https://www.viveevent.com/", "US/global", "Medium", "Annual", "Sponsor/exhibitor extraction", "Digital health, provider, payer, and healthcare AI companies.", "conference_page"),
    Source("HIMSS exhibitors", "Conference", "https://www.himss.org/global-conference", "Global", "Medium", "Annual", "Exhibitor/category extraction", "Healthcare IT, clinical workflow, and digital health vendors.", "conference_page"),
    Source("DMEA exhibitors", "Conference", "https://www.dmea.de/en/", "EU", "Medium", "Annual", "Exhibitor/category extraction", "European digital health and healthcare IT companies.", "conference_page"),
    Source("HealthQuest Capital portfolio", "VC portfolio", "https://www.healthquestcapital.com/portfolio/", "US", "High", "Monthly", "Portfolio/news page extraction", "Medtech and healthcare growth companies.", "vc_portfolio_page"),
    Source("Lightstone Ventures portfolio", "VC portfolio", "https://www.lightstonevc.com/portfolio/", "US/EU", "High", "Monthly", "Portfolio/news page extraction", "Life sciences, medtech, and diagnostics companies.", "vc_portfolio_page"),
    Source("7wireVentures portfolio", "VC portfolio", "https://www.7wireventures.com/portfolio/", "US", "Medium", "Monthly", "Portfolio/news page extraction", "Digital health and healthcare services/software companies.", "vc_portfolio_page"),
    Source("Rock Health portfolio", "VC portfolio", "https://rockhealth.com/portfolio/", "US", "Medium", "Monthly", "Portfolio/news page extraction", "Digital health companies and market signals.", "vc_portfolio_page"),
    Source("Define Ventures portfolio", "VC portfolio", "https://www.definevc.com/portfolio", "US", "Medium", "Monthly", "Portfolio/news page extraction", "Healthcare software and digital health startups.", "vc_portfolio_page"),
    Source("Flare Capital portfolio", "VC portfolio", "https://www.flarecapital.com/portfolio", "US", "Medium", "Monthly", "Portfolio/news page extraction", "Healthcare technology and services companies.", "vc_portfolio_page"),
    Source("Lux Capital portfolio", "VC portfolio", "https://www.luxcapital.com/companies", "US/global", "Medium", "Monthly", "Portfolio/news page extraction", "Deeptech, AI, bio, and health companies.", "vc_portfolio_page"),
    Source("Khosla Ventures healthcare portfolio", "VC portfolio", "https://www.khoslaventures.com/portfolio/", "US/global", "Medium", "Monthly", "Portfolio/news page extraction", "AI and healthcare venture-backed companies.", "vc_portfolio_page"),
    Source("Sofinnova Partners portfolio", "VC portfolio", "https://www.sofinnovapartners.com/portfolio/", "EU/US", "Medium", "Monthly", "Portfolio/news page extraction", "European life sciences, medtech, and digital medicine companies.", "vc_portfolio_page"),
    Source("Fountain Healthcare Partners portfolio", "VC portfolio", "https://www.fh-partners.com/portfolio", "Ireland/EU/US", "High", "Monthly", "Portfolio/news page extraction", "Ireland-based life sciences investor focused on therapeutics, medtech, diagnostics, and specialty pharma.", "fountain_healthcare"),
    Source("Seroba Life Sciences portfolio", "VC portfolio", "http://seroba-lifesciences.com/portfolio/", "EU/Ireland", "High", "Monthly", "Portfolio/news page extraction", "Ireland/EU-relevant life sciences and medtech portfolio.", "seroba_life_sciences"),
    Source("Atlantic Bridge portfolio", "VC portfolio", "https://www.abven.com/portfolio/", "Ireland/EU/US", "High", "Monthly", "Portfolio/news page extraction", "Ireland-based deeptech and university spinout investor with health technology exposure.", "atlantic_bridge"),
    Source("General Catalyst healthcare portfolio", "VC portfolio", "https://www.generalcatalyst.com/companies", "US/global", "Medium", "Monthly", "Portfolio/news page extraction", "Healthcare, AI, and care-delivery companies backed by a large multi-stage investor.", "vc_portfolio_page"),
    Source("Andreessen Horowitz Bio + Health portfolio", "VC portfolio", "https://a16z.com/portfolio/", "US/global", "Medium", "Monthly", "Portfolio/news page extraction", "Bio, healthcare AI, and digital health portfolio companies.", "vc_portfolio_page"),
    Source("Bessemer healthcare portfolio", "VC portfolio", "https://www.bvp.com/portfolio", "US/global", "Medium", "Monthly", "Portfolio/news page extraction", "Healthcare cloud, AI, and digital health companies.", "vc_portfolio_page"),
    Source("GV portfolio", "VC portfolio", "https://www.gv.com/portfolio/", "US/global", "Medium", "Monthly", "Portfolio/news page extraction", "Life sciences, healthcare, AI, and diagnostics companies.", "vc_portfolio_page"),
    Source("F-Prime Capital portfolio", "VC portfolio", "https://fprimecapital.com/portfolio/", "US/global", "High", "Monthly", "Portfolio/news page extraction", "Healthcare, therapeutics, medtech, and digital health companies.", "vc_portfolio_page"),
    Source("Polaris Partners healthcare portfolio", "VC portfolio", "https://www.polarispartners.com/portfolio/", "US", "Medium", "Monthly", "Portfolio/news page extraction", "Healthcare, life sciences, and technology companies.", "vc_portfolio_page"),
    Source("NEA healthcare portfolio", "VC portfolio", "https://www.nea.com/portfolio", "US/global", "Medium", "Monthly", "Portfolio/news page extraction", "Large healthcare, life sciences, and digital health venture portfolio.", "vc_portfolio_page"),
    Source("Venrock healthcare portfolio", "VC portfolio", "https://www.venrock.com/portfolio/", "US", "Medium", "Monthly", "Portfolio/news page extraction", "Healthcare, biotech, and technology companies.", "vc_portfolio_page"),
    Source("ARCH Venture Partners portfolio", "VC portfolio", "https://www.archventure.com/portfolio", "US/global", "Medium", "Monthly", "Portfolio/news page extraction", "Life sciences and diagnostics companies with translational health relevance.", "vc_portfolio_page"),
    Source("Third Rock Ventures portfolio", "VC portfolio", "https://www.thirdrockventures.com/portfolio", "US", "Medium", "Monthly", "Portfolio/news page extraction", "Life sciences and platform companies with clinical development signals.", "vc_portfolio_page"),
    Source("OrbiMed portfolio", "VC portfolio", "https://www.orbimed.com/en/portfolio", "US/global", "Medium", "Monthly", "Portfolio/news page extraction", "Global healthcare and life-sciences companies.", "vc_portfolio_page"),
    Source("RA Capital portfolio", "VC portfolio", "https://www.racap.com/portfolio/", "US/global", "Medium", "Monthly", "Portfolio/news page extraction", "Healthcare and life-sciences companies, including diagnostics and enabling technologies.", "vc_portfolio_page"),
    Source("Deerfield portfolio", "VC portfolio", "https://deerfield.com/portfolio", "US", "Medium", "Monthly", "Portfolio/news page extraction", "Healthcare companies across therapeutics, devices, diagnostics, and services.", "vc_portfolio_page"),
    Source("Canaan healthcare portfolio", "VC portfolio", "https://www.canaan.com/portfolio", "US/global", "Medium", "Monthly", "Portfolio/news page extraction", "Healthcare, digital health, and life-sciences venture-backed companies.", "vc_portfolio_page"),
    Source("Menlo Ventures healthcare portfolio", "VC portfolio", "https://menlovc.com/portfolio/", "US", "Medium", "Monthly", "Portfolio/news page extraction", "Healthcare AI, digital health, and enterprise workflow companies.", "vc_portfolio_page"),
    Source("Norwest healthcare portfolio", "VC portfolio", "https://www.nvp.com/portfolio/", "US/global", "Medium", "Monthly", "Portfolio/news page extraction", "Healthcare, software, and medical technology companies.", "vc_portfolio_page"),
    Source("Mayfield healthcare portfolio", "VC portfolio", "https://www.mayfield.com/portfolio/", "US", "Medium", "Monthly", "Portfolio/news page extraction", "AI, health, and enterprise software companies.", "vc_portfolio_page"),
    Source("Transformation Capital portfolio", "VC portfolio", "https://transformation.capital/portfolio/", "US", "High", "Monthly", "Portfolio/news page extraction", "Digital health and healthcare technology companies.", "vc_portfolio_page"),
    Source("LRVHealth portfolio", "VC portfolio", "https://www.lrvhealth.com/portfolio/", "US", "High", "Monthly", "Portfolio/news page extraction", "Provider-connected healthcare technology and digital health companies.", "vc_portfolio_page"),
    Source("Echo Health Ventures portfolio", "VC portfolio", "https://echohealthventures.com/portfolio/", "US", "High", "Monthly", "Portfolio/news page extraction", "Healthcare technology companies backed by strategic health investors.", "vc_portfolio_page"),
    Source("Health Velocity Capital portfolio", "VC portfolio", "https://www.healthvelocitycapital.com/portfolio/", "US", "High", "Monthly", "Portfolio/news page extraction", "Healthcare software, services, and digital health companies.", "vc_portfolio_page"),
    Source("Town Hall Ventures portfolio", "VC portfolio", "https://townhallventures.com/portfolio/", "US", "Medium", "Monthly", "Portfolio/news page extraction", "Healthcare companies focused on underserved populations and care delivery.", "vc_portfolio_page"),
    Source("Frist Cressey Ventures portfolio", "VC portfolio", "https://fcventures.com/portfolio/", "US", "Medium", "Monthly", "Portfolio/news page extraction", "Healthcare services, software, and technology companies.", "vc_portfolio_page"),
    Source("Wavemaker Three-Sixty Health portfolio", "VC portfolio", "https://wavemaker360.com/portfolio/", "US", "High", "Monthly", "Portfolio/news page extraction", "Healthcare seed-stage companies across digital health, medtech, and diagnostics.", "vc_portfolio_page"),
    Source("Nina Capital portfolio", "VC portfolio", "https://www.nina.capital/portfolio", "EU/global", "High", "Monthly", "Portfolio/news page extraction", "European health technology and digital health portfolio companies.", "vc_portfolio_page"),
    Source("Heal Capital portfolio", "VC portfolio", "https://www.healcapital.com/portfolio/", "EU", "High", "Monthly", "Portfolio/news page extraction", "European digital health and healthtech companies.", "vc_portfolio_page"),
    Source("Crista Galli Ventures portfolio", "VC portfolio", "https://www.cristagalli.com/portfolio", "EU/UK", "High", "Monthly", "Portfolio/news page extraction", "European healthtech, deeptech, and digital health companies.", "vc_portfolio_page"),
    Source("MTIP portfolio", "VC portfolio", "https://www.mtip.ch/portfolio/", "EU", "High", "Monthly", "Portfolio/news page extraction", "European healthtech growth companies.", "vc_portfolio_page"),
    Source("Ysios Capital portfolio", "VC portfolio", "https://ysioscapital.com/portfolio/", "EU", "Medium", "Monthly", "Portfolio/news page extraction", "European life-sciences, diagnostics, and healthcare companies.", "vc_portfolio_page"),
    Source("Kurma Partners portfolio", "VC portfolio", "https://www.kurmapartners.com/portfolio/", "EU", "Medium", "Monthly", "Portfolio/news page extraction", "European healthcare, biotech, and diagnostics companies.", "vc_portfolio_page"),
    Source("BioGeneration Ventures portfolio", "VC portfolio", "https://www.biogenerationventures.com/portfolio/", "EU", "Medium", "Monthly", "Portfolio/news page extraction", "European life-sciences and medtech-adjacent companies.", "vc_portfolio_page"),
    Source("EQT Life Sciences portfolio", "VC portfolio", "https://eqtgroup.com/current-portfolio/fund/eqt-life-sciences/", "EU/US", "Medium", "Monthly", "Portfolio/news page extraction", "Life-sciences and healthcare companies from the EQT Life Sciences platform.", "vc_portfolio_page"),
    Source("Forbion portfolio", "VC portfolio", "https://forbion.com/en/portfolio/", "EU/US", "Medium", "Monthly", "Portfolio/news page extraction", "Life-sciences, diagnostics, and therapeutic platform companies.", "vc_portfolio_page"),
    Source("Gilde Healthcare portfolio", "VC portfolio", "https://gildehealthcare.com/portfolio/", "EU/US", "High", "Monthly", "Portfolio/news page extraction", "Healthcare, medtech, diagnostics, and digital health companies.", "vc_portfolio_page"),
    Source("Endeavour Vision portfolio", "VC portfolio", "https://www.endeavourvision.com/portfolio/", "EU/US", "High", "Monthly", "Portfolio/news page extraction", "Medtech and digital health growth companies.", "vc_portfolio_page"),
    Source("SHS Capital portfolio", "VC portfolio", "https://www.shs-capital.eu/en/portfolio/", "EU", "High", "Monthly", "Portfolio/news page extraction", "European healthcare, medtech, diagnostics, and digital health companies.", "vc_portfolio_page"),
    Source("Panakes Partners portfolio", "VC portfolio", "https://www.panakes.it/portfolio/", "EU", "High", "Monthly", "Portfolio/news page extraction", "European medtech, diagnostics, and digital health companies.", "vc_portfolio_page"),
    Source("Vesalius Biocapital portfolio", "VC portfolio", "https://vesaliusbiocapital.com/portfolio/", "EU", "Medium", "Monthly", "Portfolio/news page extraction", "European life-sciences and medtech companies.", "vc_portfolio_page"),
    Source("Asabys Partners portfolio", "VC portfolio", "https://asabys.com/portfolio/", "EU", "High", "Monthly", "Portfolio/news page extraction", "European health innovation, medtech, and digital health companies.", "vc_portfolio_page"),
    Source("AlbionVC healthcare portfolio", "VC portfolio", "https://albion.vc/portfolio/", "UK/EU", "Medium", "Monthly", "Portfolio/news page extraction", "UK and European digital health, software, and life-sciences companies.", "vc_portfolio_page"),
    Source("CORDIS", "Grant/funding", "https://cordis.europa.eu/projects", "EU", "High", "Monthly", "Search/export", "EU-funded health, AI, and medtech projects.", "grant_funding_page"),
    Source("NIH RePORTER", "Grant/funding", "https://reporter.nih.gov/", "US", "High", "Monthly", "API/search export", "SBIR/STTR and translational research awards with abstracts.", "grant_funding_page"),
    Source("SBIR.gov awards", "Grant/funding", "https://www.sbir.gov/sbirsearch/award/all", "US", "High", "Monthly", "Award search/export", "US startup grant funding for translational health, AI, device, and diagnostics projects.", "grant_funding_page"),
    Source("ARPA-H portfolio", "Grant/funding", "https://arpa-h.gov/explore-funding/portfolio", "US", "High", "Monthly", "Portfolio review", "High-value translational health programs and awardees.", "grant_funding_page"),
    Source("EIC Accelerator", "Grant/funding", "https://eic.ec.europa.eu/eic-funding-opportunities/eic-accelerator_en", "EU", "High", "Quarterly", "Selected companies/results review", "European deep-tech startups with grant/equity funding.", "grant_funding_page"),
    Source("Innovate UK", "Grant/funding", "https://www.ukri.org/councils/innovate-uk/", "UK", "Medium", "Monthly", "Award/news search", "UK health innovation and medtech funding.", "grant_funding_page"),
    Source("SBRI Healthcare", "Grant/funding", "https://sbrihealthcare.co.uk/", "UK", "High", "Quarterly", "Competition/award review", "NHS-facing innovation awards.", "grant_funding_page"),
    Source("Enterprise Ireland", "Grant/funding", "https://www.enterprise-ireland.com/", "Ireland", "High", "Quarterly", "Portfolio/news review", "Irish startup and medtech funding.", "grant_funding_page"),
    Source("LinkedIn Jobs", "Jobs", "https://www.linkedin.com/jobs/", "US/EU/global", "High", "Weekly", "Manual search", "Hiring gaps for regulatory, QA, design assurance, V&V.", "jobs_page"),
    Source("Wellfound jobs", "Jobs", "https://wellfound.com/jobs", "US/EU/global", "Medium", "Weekly", "Manual search", "Paused for automation: public jobs and company pages return 403.", None),
    Source("Greenhouse job boards", "Jobs", "https://www.greenhouse.com/", "US/EU/global", "Medium", "Weekly", "Manual/company board search", "Paused for automation: no reliable Greenhouse-wide public discovery endpoint.", None),
    Source("Lever job boards", "Jobs", "https://www.lever.co/", "US/EU/global", "Medium", "Weekly", "Company careers page search", "Direct company hiring gaps exposed through Lever-hosted job pages.", "lever_jobs"),
    Source("Indeed jobs", "Jobs", "https://www.indeed.com/", "US/EU/global", "Medium", "Weekly", "Manual search", "Broad hiring signal source for regulatory, quality, clinical, product, and engineering roles.", "jobs_page"),
    Source("Glassdoor jobs", "Jobs", "https://www.glassdoor.com/Job/", "US/EU/global", "Medium", "Weekly", "Manual search", "Broad job-board source with company hiring and role-context signals.", "jobs_page"),
    Source("ZipRecruiter jobs", "Jobs", "https://www.ziprecruiter.com/jobs-search", "US", "Medium", "Weekly", "Manual search", "US hiring signal source for regulatory, QA, clinical, and product roles.", "jobs_page"),
    Source("Google Jobs search", "Jobs", "https://www.google.com/search?q=medtech+regulatory+quality+jobs", "US/EU/global", "Medium", "Weekly", "Manual search", "Search-based discovery for company career pages and recent role postings.", "jobs_page"),
    Source("Built In jobs", "Jobs", "https://builtin.com/jobs", "US", "Medium", "Weekly", "Built In role search", "Technology startup hiring signals, including healthtech and AI companies.", "builtin_jobs"),
    Source("Welcome to the Jungle jobs", "Jobs", "https://www.welcometothejungle.com/en/jobs", "EU/US", "Medium", "Weekly", "Manual search", "Startup and scaleup hiring signals across Europe and the US.", "jobs_page"),
    Source("Remote OK jobs", "Jobs", "https://remoteok.com/", "Global", "Low", "Weekly", "Manual search", "Remote startup hiring signals for product, engineering, and operations roles.", "jobs_page"),
    Source("Workable job boards", "Jobs", "https://www.workable.com/job-board", "US/EU/global", "Medium", "Weekly", "Company careers page search", "Direct company hiring gaps exposed through Workable-hosted job pages.", "workable_jobs"),
    Source("Ashby job boards", "Jobs", "https://www.ashbyhq.com/", "US/EU/global", "Medium", "Weekly", "Company careers page search", "Direct company hiring gaps exposed through Ashby-hosted job pages.", "ashby_jobs"),
    Source("SmartRecruiters job boards", "Jobs", "https://www.smartrecruiters.com/", "US/EU/global", "Medium", "Weekly", "Company careers page search", "Direct company hiring gaps exposed through SmartRecruiters-hosted job pages.", "smartrecruiters_jobs"),
    Source("Recruitee job boards", "Jobs", "https://recruitee.com/", "EU/global", "Medium", "Weekly", "Company careers page search", "Direct company hiring gaps exposed through Recruitee-hosted job pages.", "recruitee_jobs"),
    Source("Workday careers pages", "Jobs", "https://www.workday.com/", "US/EU/global", "Low", "Weekly", "Company careers page search", "Enterprise-hosted career pages for larger medtech and healthcare companies.", "jobs_page"),
    Source("BioSpace jobs", "Jobs", "https://www.biospace.com/jobs/", "US/global", "High", "Weekly", "BioSpace role search", "Life-sciences hiring signals, including diagnostics, clinical, regulatory, and quality roles.", "biospace_jobs"),
    Source("MedReps jobs", "Jobs", "https://www.medreps.com/medical-sales-jobs", "US", "Medium", "Weekly", "Manual search", "Medical device commercial hiring signals and market-entry clues.", "jobs_page"),
    Source("NHS Jobs", "Jobs", "https://www.jobs.nhs.uk/", "UK", "Medium", "Weekly", "NHS role search", "UK provider-side digital, clinical, and innovation hiring signals.", "nhs_jobs"),
    Source("HealthJobsUK", "Jobs", "https://www.healthjobsuk.com/", "UK", "Medium", "Weekly", "Manual search", "UK healthcare hiring signals for digital, clinical, implementation, and operational roles.", "jobs_page"),
]


# This registry is not a lead list. It is the vocabulary adapters look for on approved sources.
# A company is included only if an approved source page actually contains its configured names.
COMPANY_REGISTRY = {
    "Qure.ai": {"aliases": ["Qure AI", "Qure.ai"], "website": "https://qure.ai/", "geography": "India/US/EU", "product_type": "AI medical imaging", "job_boards": [{"platform": "greenhouse", "account": "qureai"}]},
    "Canary Speech": {"aliases": ["Canary Speech"], "website": "https://www.canaryspeech.com/", "geography": "US", "product_type": "Voice biomarkers / diagnostics"},
    "Fedo": {"aliases": ["Fedo"], "website": "https://fedo.ai/", "geography": "India/global", "product_type": "AI vitals / risk scoring"},
    "Oura": {"aliases": ["Oura"], "website": "https://ouraring.com/", "geography": "Finland/US", "product_type": "Wearable health device", "job_boards": [{"platform": "greenhouse", "account": "oura"}]},
    "Cera": {"aliases": ["Cera"], "website": "https://www.cera.care/", "geography": "UK", "product_type": "AI home care / risk prediction"},
    "Sword Health": {"aliases": ["Sword Health", "SWORD Health"], "website": "https://swordhealth.com/", "geography": "Portugal/US", "product_type": "Digital MSK / AI care", "job_boards": [{"platform": "greenhouse", "account": "swordhealth"}]},
    "Eko Health": {"aliases": ["Eko Health", "Eko"], "website": "https://www.ekohealth.com/", "geography": "US", "product_type": "AI-enabled digital stethoscope", "job_boards": [{"platform": "greenhouse", "account": "ekohealth"}]},
    "Aidoc": {"aliases": ["Aidoc", "AIDoc"], "website": "https://www.aidoc.com/", "geography": "Israel/US", "product_type": "Clinical AI / radiology triage", "job_boards": [{"platform": "greenhouse", "account": "aidoc"}]},
    "Quibim": {"aliases": ["Quibim"], "website": "https://www.quibim.com/", "geography": "Spain/US", "product_type": "AI imaging biomarkers"},
    "Outcomes4Me": {"aliases": ["Outcomes4Me"], "website": "https://outcomes4me.com/", "geography": "US/EU", "product_type": "Oncology digital health"},
    "Alimetry": {"aliases": ["Alimetry"], "website": "https://www.alimetry.com/", "geography": "New Zealand/US/EU", "product_type": "Gastric mapping medical device"},
}


TRIGGER_SOURCES = [
    {
        "name": "Axios Aidoc funding",
        "url": "https://www.axios.com/2026/04/29/exclusive-clinical-ai-provider-aidoc-raises-150m-series-e",
        "companies": ["Aidoc"],
        "trigger_type": "Funding",
        "trigger_event": "Raised $150M Series E for clinical AI expansion.",
    },
    {
        "name": "TechCrunch Eko funding",
        "url": "https://techcrunch.com/2024/06/05/eko-health-scores-41m-to-detect-heart-disease-earlier-and-more-accurately/",
        "companies": ["Eko Health"],
        "trigger_type": "Funding",
        "trigger_event": "Raised $41M Series D to expand AI stethoscope business.",
    },
    {
        "name": "TechCrunch Quibim funding",
        "url": "https://techcrunch.com/2025/01/28/quibim-raises-50m-to-develop-ai-models-for-medical-imaging/",
        "companies": ["Quibim"],
        "trigger_type": "Funding",
        "trigger_event": "Raised $50M Series A to develop AI models for medical imaging.",
    },
    {
        "name": "TechCrunch Sword funding",
        "url": "https://techcrunch.com/2024/06/04/sword-health-raises-130m-and-its-valuation-soars-to-3b/",
        "companies": ["Sword Health"],
        "trigger_type": "Funding",
        "trigger_event": "Raised $130M at a reported $3B valuation for AI-powered digital MSK care.",
    },
    {
        "name": "TIME HealthTech 2025",
        "url": "https://time.com/7318020/worlds-top-healthtech-companies-2025/",
        "companies": ["Qure.ai", "Canary Speech", "Fedo", "Oura", "Cera"],
        "trigger_type": "Market recognition",
        "trigger_event": "Recognized in TIME's 2025 HealthTech ranking.",
    },
]


SOURCE_PLAYBOOKS = [
    ["News/search", "Weekly searches: medtech AI funding; SaMD raises; digital health Series A; medical device seed funding; diagnostic AI funding.", "Result must name a company, date, funding/launch/regulatory event, and source URL.", "Company, trigger article, amount/event, date, geography, product clues", "Recent public trigger; discovery and trigger may be same URL.", "Advisory"],
    ["Public ranking", "Scan ranking page for configured medtech/AI-health company aliases.", "Company must appear on the approved ranking page.", "Company, source page, matched terms, rationale", "The source itself proves discovery; trigger may be separate.", "Advisory"],
    ["Accelerator", "Scan cohort/program pages for configured company aliases and category terms.", "Company must appear on the accelerator page.", "Company, cohort/source page, matched terms", "Curated early-stage medtech/digital health company.", "Advisory/design-dev"],
    ["Conference", "Extract exhibitors/sponsors/startups, then filter category text for AI, software, digital health, imaging, diagnostics, wearables, remote monitoring.", "Company must appear on event directory or sponsor/exhibitor page.", "Company, event, category, booth/profile URL, product summary", "Commercial presence in relevant market.", "Advisory/design-dev"],
    ["VC portfolio", "Extract portfolio pages and news pages; filter for medical device, diagnostics, digital health, AI healthcare, SaMD, clinical workflow.", "Company must appear on public portfolio/news page; paid databases excluded.", "Company, investor, portfolio URL, category, funding/news URL if present", "Funded or investor-backed company with likely budget/urgency.", "Advisory/design-dev"],
    ["Grant/funding", "Use API/export where available; search project abstract for SaMD, AI diagnostic, wearable, remote monitoring.", "Recipient must be company or startup-like organization.", "Company, award, abstract, amount, date, URL", "Funded translational program.", "Advisory"],
    ["Regulatory database", "Query FDA AI/ML list, 510(k), and De Novo databases for AI, software, imaging, diagnostics, monitoring, decision support.", "Company/product must have a regulatory record or listing.", "Company, product, decision/date, regulation number, source URL", "Regulatory pathway or market-entry signal.", "Advisory"],
    ["University/spinout", "Review university tech-transfer, innovation, spinout, and startup directories for health, medtech, diagnostics, AI, device, and digital health companies.", "Company must be listed by the university, tech-transfer office, or affiliated innovation/commercialisation unit.", "Company, university, spinout/startup URL, category, product clues", "Very early academic-origin venture before broad accelerator or investor visibility.", "Advisory/design-dev"],
    ["Jobs", "Search regulatory/QA/design assurance terms against public job pages.", "Role must be recent and company must be relevant to medtech/health AI.", "Company, role, job URL, gap hypothesis", "Capability gap or urgent workload.", "Embedded support/advisory"],
]


