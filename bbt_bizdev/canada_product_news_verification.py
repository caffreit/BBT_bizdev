from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


PRIMARY_EVENTS: tuple[dict[str, Any], ...] = (
    {
        "company": "AmacaThera", "candidate_pattern": r"Pacira partnership",
        "event_date": "2025-11-04", "event_type": "partnership",
        "title": "AmacaThera signs exclusive global licensing agreement with Pacira BioSciences",
        "summary": "Pacira licensed AMT-143 and will collaborate on its planned Phase 2 clinical program, with up to US$230 million in upfront and milestone payments.",
        "product_or_program": "AMT-143; AmacaGel", "development_stage": "clinical",
        "evidence_url": "https://amacathera.com/pdfs/FINAL_AmacaThera%20License%20Agreement%20PR.pdf",
        "source_type": "company", "confidence": "high",
    },
    {
        "company": "AmacaThera", "candidate_pattern": r"Merck Animal Health",
        "event_date": "2025-05-01", "event_type": "partnership",
        "title": "AmacaThera and Merck Animal Health announce collaboration in animal health",
        "summary": "The companies signed an evaluation and option agreement to develop long-acting animal-health formulations using AmacaThera's hydrogel platform.",
        "product_or_program": "AmacaGel", "development_stage": "research",
        "evidence_url": "https://www.amacathera.com/amacathera-and-merck-animalhealth",
        "source_type": "company", "confidence": "high",
    },
    {
        "company": "Aurinia Pharmaceuticals", "candidate_pattern": r"Acquisition Of Kezar",
        "event_date": "2026-03-30", "event_type": "acquisition",
        "title": "Aurinia Pharmaceuticals enters agreement to acquire Kezar Life Sciences",
        "summary": "Aurinia agreed to acquire Kezar, adding clinical-stage autoimmune and oncology programs including zetomipzomib.",
        "product_or_program": "zetomipzomib", "development_stage": "clinical",
        "evidence_url": "https://www.auriniapharma.com/press-releases/aurinia-pharmaceuticals-to-acquire-kezar-life-sciences-for-6-955-in-cash-per-share-plus-a-contingent-value-right",
        "source_type": "company", "confidence": "high",
    },
    {
        "company": "Cosm Medical", "candidate_pattern": r"Licensing and Collaboration Agreement",
        "event_date": "2026-05-27", "event_type": "partnership",
        "title": "Cosm Medical enters licensing and collaboration agreement for post-surgical pelvic recovery",
        "summary": "Cosm licensed technology from Duke Health and Mayo Clinic to develop and validate personalized Gynethotics Recovery devices.",
        "product_or_program": "Gynethotics Recovery", "development_stage": "validation",
        "evidence_url": "https://www.businesswire.com/news/home/20260527607633/en/Cosm-Medical-Announces-Licensing-and-Collaboration-Agreement-to-Advance-Post-Surgical-Pelvic-Recovery-with-Personalized-Gynethotics-Devices",
        "source_type": "newswire", "confidence": "high",
    },
    {
        "company": "Cosm Medical", "candidate_pattern": r"Seed\+ Financing",
        "event_date": "2025-06-05", "event_type": "funding",
        "title": "iGan Partners leads Seed+ financing for Cosm Medical",
        "summary": "The first close will support U.S. expansion, clinical validation, commercial growth, and new applications for the Gynethotics platform.",
        "product_or_program": "Gynethotics", "development_stage": "validation",
        "evidence_url": "https://iganpartners.com/blog/portfolio/igan-partners-leads-seed-financing-for-cosm-medical-to-advance-personalized-gynecological-devices",
        "source_type": "investor", "confidence": "high",
    },
    {
        "company": "Exact Imaging", "candidate_pattern": r"\$10 Million|US\$10m|10 Million Raised",
        "event_date": "2026-02-10", "event_type": "funding",
        "title": "iGan Partners leads $10 million financing of Exact Imaging",
        "summary": "The financing is intended to accelerate clinical validation and global commercialization of the ExactVu micro-ultrasound platform.",
        "product_or_program": "ExactVu", "development_stage": "scale-up",
        "evidence_url": "https://www.prnewswire.com/news-releases/igan-partners-leads-10-million-financing-of-exact-imaging-the-worlds-leading-prostate-cancer-detection-platform-302682128.html",
        "source_type": "investor newswire", "confidence": "high",
    },
    {
        "company": "Fluid Biomed", "candidate_pattern": r"27.?[Mm]illion|27M",
        "event_date": "2024-12-16", "event_type": "funding",
        "title": "Fluid Biomed raises US$27 million Series A",
        "summary": "The financing supports additional human clinical trials of the ReSolv bioabsorbable stent for brain aneurysms.",
        "product_or_program": "ReSolv", "development_stage": "clinical",
        "evidence_url": "https://fluidbiomed.com/news/fluid-biomed-inc-raises-27-million-usd-in-oversubscribed-series-a-financing-to-advance-worlds-first-bioabsorbable-polymer-based-stent-to-treat-brain-aneurysms/",
        "source_type": "company", "confidence": "high",
    },
    {
        "company": "HDAX Therapeutics", "candidate_pattern": r"3\.2",
        "event_date": "2024-09-05", "event_type": "funding",
        "title": "HDAX Therapeutics announces first close of seed financing",
        "summary": "The US$3.2 million first close supports preclinical candidate nomination and advancement of HDAC6-targeted pipeline programs.",
        "product_or_program": "HDAC6-targeted pipeline", "development_stage": "preclinical",
        "evidence_url": "https://hdaxtx.com/hdax-announces-first-close-of-oversubscribed-seed-financing/",
        "source_type": "company", "confidence": "high",
    },
    {
        "company": "Hyivy Health", "candidate_pattern": r"\$2M in Seed Funding",
        "event_date": "2024-09-27", "event_type": "funding",
        "title": "Hyivy Health closes $2 million seed financing",
        "summary": "The financing supports development of Hyivy's Pelvic Health Rehabilitation System for chronic pelvic pain.",
        "product_or_program": "Pelvic Health Rehabilitation System", "development_stage": "clinical",
        "evidence_url": "https://facit.ca/news/hyivy-seed-financing",
        "source_type": "investor", "confidence": "high",
    },
    {
        "company": "Milestone Pharmaceuticals", "candidate_pattern": r"approval|Approval",
        "event_date": "2025-12-12", "event_type": "regulatory approval",
        "title": "FDA approves CARDAMYST for adults with PSVT",
        "summary": "FDA approved CARDAMYST (etripamil) nasal spray for conversion of acute symptomatic PSVT episodes to sinus rhythm in adults.",
        "product_or_program": "CARDAMYST (etripamil)", "development_stage": "launch",
        "evidence_url": "https://investors.milestonepharma.com/news-releases/news-release-details/milestone-receives-fda-approval-cardamysttm-etripamil-first-and/",
        "source_type": "company", "confidence": "high",
    },
    {
        "company": "Milestone Pharmaceuticals", "candidate_pattern": r"Heart Rhythm Society",
        "event_date": "2026-05-27", "event_type": "partnership",
        "title": "Heart Rhythm Society and Milestone Pharmaceuticals partner on SVT education",
        "summary": "The partnership expanded free SVT patient-education resources through the Heart Rhythm Society's UpBeat.org platform.",
        "product_or_program": "UpBeat.org SVT education", "development_stage": "launch",
        "evidence_url": "https://www.hrsonline.org/news/expansion-svt-education-upbeat/",
        "source_type": "professional society", "confidence": "high",
    },
    {
        "company": "PurposeMed", "candidate_pattern": r"True North Fund",
        "event_date": "2025-03-04", "event_type": "funding",
        "title": "True North Fund leads growth investment in PurposeMed",
        "summary": "The investment, with participation from BDC Capital and Panache Ventures, supports PurposeMed's digital-health growth in Canada and the United States.",
        "product_or_program": "PurposeMed virtual-care platform", "development_stage": "scale-up",
        "evidence_url": "https://www.linkedin.com/posts/true-north-fund1_true-north-fund-completes-fourth-investment-activity-7302682922958958593-pwrj",
        "source_type": "investor", "confidence": "medium",
    },
    {
        "company": "Puzzle Medical Devices", "candidate_pattern": r"raises \$30M",
        "event_date": "2025-04-11", "event_type": "funding",
        "title": "Puzzle Medical Devices closes C$43 million financing",
        "summary": "The financing supports refinement and clinical studies of Puzzle Medical's percutaneous heart pump for advanced heart failure.",
        "product_or_program": "Percutaneous heart pump", "development_stage": "clinical",
        "evidence_url": "https://www.desjardins.com/en/news/desjardins-capital-co-leads-43-m-funding-round-puzzle-medical-devices.html",
        "source_type": "investor", "confidence": "high",
    },
    {
        "company": "Rehabtronics", "candidate_pattern": r"Prelivia Device",
        "event_date": "2024-08-22", "event_type": "regulatory approval",
        "title": "Rehabtronics announces Health Canada approval for Prelivia",
        "summary": "Rehabtronics announced Canadian authorization for Prelivia, a neurostimulation device intended to increase local blood circulation in patients at risk of pressure injuries.",
        "product_or_program": "Prelivia", "development_stage": "launch",
        "evidence_url": "https://www.prnewswire.com/news-releases/rehabtronics-announces-health-canada-approval-for-prelivia-device-302227633.html",
        "source_type": "company newswire", "confidence": "medium",
    },
    {
        "company": "Sonic Incytes", "candidate_pattern": r"Velacur ONE",
        "event_date": "2025-08-12", "event_type": "regulatory approval",
        "title": "FDA grants 510(k) clearance for Velacur ONE",
        "summary": "FDA granted 510(k) clearance for Velacur ONE, an AI-guided point-of-care ultrasound elastography device for chronic liver disease management.",
        "product_or_program": "Velacur ONE", "development_stage": "launch",
        "evidence_url": "https://www.sonicincytes.com/fda-grants-510k-clearance-to-sonic-incytes-velacur-one/",
        "source_type": "company", "confidence": "high",
    },
    {
        "company": "VoxNeuro", "candidate_pattern": r"cfNI",
        "event_date": "2026-06-12", "event_type": "regulatory approval",
        "title": "FDA clears VoxNeuro Cognitive Function Neuroimaging software",
        "summary": "FDA 510(k) K253015 covers VoxNeuro's prescription-use cfNI software for adults aged 18 to 70.",
        "product_or_program": "Cognitive Function Neuroimaging (cfNI) Software", "development_stage": "launch",
        "evidence_url": "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfTPLC/tplc.cfm?ID=4105&manufacturer=VOXNEURO%2C+INC.&min_report_year=2019&pmndecision=SUBSTANTIALLY+EQUIVALENT",
        "source_type": "regulator", "confidence": "high",
    },
    {
        "company": "Zymeworks", "candidate_pattern": r"First Patient Dosed",
        "event_date": "2024-11-05", "event_type": "clinical study",
        "title": "Zymeworks doses first patient in Phase 1 trial of ZW191",
        "summary": "The first-in-human Phase 1 trial is evaluating ZW191 in advanced FR-alpha-expressing solid tumors.",
        "product_or_program": "ZW191; NCT06555744", "development_stage": "clinical",
        "evidence_url": "https://ir.zymeworks.com/news-releases/news-release-details/zymeworks-announces-first-patient-dosed-phase-1-clinical-trial-0",
        "source_type": "company", "confidence": "high",
    },
    {
        "company": "Zymeworks", "candidate_pattern": r"New Phase 1 Data",
        "event_date": "2026-04-21", "event_type": "clinical study",
        "title": "Zymeworks presents Phase 1 data for ZW191 at AACR 2026",
        "summary": "Zymeworks reported dose-escalation results for its FR-alpha-targeting antibody-drug conjugate ZW191.",
        "product_or_program": "ZW191", "development_stage": "clinical",
        "evidence_url": "https://ir.zymeworks.com/news-releases/news-release-details/zymeworks-presents-new-phase-1-data-zw191-folate-receptor-alpha",
        "source_type": "company", "confidence": "high",
    },
    {
        "company": "Zymeworks", "candidate_pattern": r"Royalty-Backed Note Financing",
        "event_date": "2026-03-02", "event_type": "funding",
        "title": "Zymeworks and Royalty Pharma enter $250 million royalty-backed financing",
        "summary": "The non-recourse financing is backed by a portion of Ziihera royalties and extends Zymeworks' stated cash runway beyond 2028.",
        "product_or_program": "Ziihera (zanidatamab-hrii)", "development_stage": "launch",
        "evidence_url": "https://ir.zymeworks.com/news-releases/news-release-details/zymeworks-and-royalty-pharma-enter-250-million-royalty-backed/",
        "source_type": "company", "confidence": "high",
    },
    {
        "company": "Zymeworks", "candidate_pattern": r"pauses plans",
        "event_date": "2025-03-05", "event_type": "pipeline prioritization",
        "title": "Zymeworks prioritizes ZW251 and pauses Phase 1 preparations for ZW220",
        "summary": "Zymeworks reprioritized resources to accelerate ZW251 toward an IND submission and paused preparations to begin Phase 1 studies of ZW220.",
        "product_or_program": "ZW251; ZW220", "development_stage": "preclinical",
        "evidence_url": "https://ir.zymeworks.com/news-releases/news-release-details/zymeworks-provides-corporate-update-and-reports-fourth-quarter/",
        "source_type": "company", "confidence": "high",
    },
)

IDENTITY_MISMATCH_COMPANIES = {"16 Bit", "BlueDot", "Hypercare", "Swift Medical", "Xpan"}


def _event_id(company_id: str, event: dict[str, Any]) -> str:
    value = f"{company_id}|{event['event_type']}|{event['event_date']}|{event['product_or_program']}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def verify_recent_candidates(candidates: list[dict[str, Any]], captured_at: str) -> dict[str, Any]:
    recent = [row for row in candidates if row.get("freshness") == "recent_24_months"]
    events, decisions = [], []
    event_ids: dict[int, str] = {}
    company_ids = {row["company_name"]: row["company_id"] for row in recent}
    for index, event in enumerate(PRIMARY_EVENTS):
        company_id = company_ids.get(event["company"])
        if not company_id:
            continue
        evidence_id = _event_id(company_id, event)
        event_ids[index] = evidence_id
        events.append({
            "evidence_id": evidence_id,
            "company_id": company_id,
            "track": "product_development" if event["event_type"] in {
                "partnership", "regulatory approval", "clinical study", "pipeline prioritization"
            } else "news",
            "claim_type": event["event_type"],
            **{key: value for key, value in event.items() if key not in {"company", "candidate_pattern"}},
            "evidence_date": event["event_date"],
            "captured_at": captured_at,
            "extraction_method": "manual primary-source verification of RSS candidate",
        })
    for candidate in recent:
        matched_index = next((
            index for index, event in enumerate(PRIMARY_EVENTS)
            if event["company"] == candidate["company_name"]
            and re.search(event["candidate_pattern"], candidate["title"], re.I)
        ), None)
        if matched_index is not None and matched_index in event_ids:
            decisions.append({
                **candidate,
                "verification_status": "verified_supporting_candidate",
                "accepted_evidence_id": event_ids[matched_index],
                "verification_notes": "Identity and material event verified; syndicated candidates deduplicated to the primary event.",
            })
        elif candidate["company_name"] in IDENTITY_MISMATCH_COMPANIES:
            decisions.append({
                **candidate,
                "verification_status": "rejected_identity_mismatch",
                "accepted_evidence_id": "",
                "verification_notes": "The title uses the company words for an unrelated entity or as ordinary descriptive text.",
            })
        elif candidate["company_name"] == "Endotronix":
            decisions.append({
                **candidate,
                "verification_status": "rejected_retrospective",
                "accepted_evidence_id": "",
                "verification_notes": "The article is retrospective commentary; the acquisition occurred in 2024 and is not a new 2025 event.",
            })
        elif candidate["company_name"] == "Zymeworks" and re.search(r"Gandeeva|partner maps", candidate["title"], re.I):
            decisions.append({
                **candidate,
                "verification_status": "rejected_passing_mention",
                "accepted_evidence_id": "",
                "verification_notes": "No new Zymeworks event was found in a first-party source; the headline concerns another company's work.",
            })
        else:
            decisions.append({
                **candidate,
                "verification_status": "unresolved_primary_source",
                "accepted_evidence_id": "",
                "verification_notes": "Plausible company event, but no adequate primary source was located in this pass.",
            })
    return {"events": events, "decisions": decisions}


def run_recent_verification(candidates_path: Path, output_dir: Path, run_date: str) -> dict[str, Any]:
    payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    result = verify_recent_candidates(payload["candidates"], run_date)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "verified_recent_events.json").write_text(
        json.dumps({"schema_version": "1.0", "generated_at": run_date, "events": result["events"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "recent_candidate_decisions.json").write_text(
        json.dumps({"schema_version": "1.0", "generated_at": run_date, "decisions": result["decisions"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    counts: dict[str, int] = {}
    for row in result["decisions"]:
        status = row["verification_status"]
        counts[status] = counts.get(status, 0) + 1
    summary = {
        "run_date": run_date,
        "recent_candidates_reviewed": len(result["decisions"]),
        "accepted_deduplicated_events": len(result["events"]),
        "candidate_decision_counts": dict(sorted(counts.items())),
    }
    (output_dir / "verification_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
