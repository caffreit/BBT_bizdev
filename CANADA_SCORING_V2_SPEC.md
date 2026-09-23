# Canada Prospect Scoring V2 — Contract

## Status

Draft implementation contract for WP1 and WP8 of `CANADA_COMPANY_AUDIT_REMEDIATION_PLAN.md`.

## Outputs

Scoring V2 returns five separate outputs:

| Output | Range | Meaning |
| --- | ---: | --- |
| Fit | 0–35 | Suitability for BlueBridge's product-development, validation, quality, and regulatory services |
| Timing | 0–30 | Evidence that relevant work or change is happening now |
| Ability to buy | 0–25 | Evidence of resources and an appropriately sized operating company |
| Canada relevance | 0–10 | Evidence-backed Canadian decision-making or product-development presence |
| Evidence confidence | 0–100 | Comparable coverage and quality of the evidence supporting the other outputs |

`Priority score` is the deterministic sum of Fit, Timing, Ability to buy, and Canada relevance. Evidence confidence is never added to that total and must always be displayed beside it.

## Fit Definition

Fit is not a synonym for `medical device` or `diagnostic`. A high-fit prospect must have:

1. A regulated or clinically consequential deliverable relevant to BlueBridge's work.
2. One or more observable service-need areas: product development, design controls, verification/validation, quality systems, regulatory strategy/submission, clinical validation, software product assurance, manufacturing transfer, or scale-up.
3. An operating model and stage where external specialist support is plausible.

Product category alone can establish broad eligibility but cannot earn maximum fit.

## Missing and Conflicting Data

- Unknown earns zero points for the affected rule.
- Unknown creates a missing-data flag and lowers Evidence confidence.
- `complete_zero` may create a true zero only for the documented source set represented by that completeness record.
- Conflicting facts remain separate until a deterministic precedence rule or manual decision resolves them.
- Manual-review, blocked, failed, partial, and not-run evidence cannot independently create positive points.

## Accepted Evidence

A score-bearing fact must contain:

- stable evidence ID;
- company ID;
- claim/event type;
- evidence URL;
- evidence or event date when the claim is time-sensitive;
- capture/check date;
- source type and confidence;
- accepted/current status;
- deterministic identity attachment.

LLM output without these controls remains candidate evidence.

## Component Contract

### Fit — 35

- Regulated/clinically consequential deliverable: 0–15.
- Evidence-backed BlueBridge service-need areas: 0–15.
- Operating-model/stage suitability: 0–5.

Maximum fit requires both deliverable alignment and service-need evidence. Category text alone is capped below maximum.

### Timing — 30

- Verified currently open relevant roles: 0–12.
- Current product/regulatory/clinical/manufacturing milestone: 0–12.
- Current expansion, deployment, partnership, or other material trigger: 0–6.

Each event family has its own recency window. Historical regulatory presence is context, not current timing.

### Ability to Buy — 25

- Dated, semantically classified financing or award: 0–15.
- Current credible institutional backing: 0–4.
- Evidence-backed employee band/stage: 0–6.

Portfolio presence does not imply a recent round. Government funding types remain distinct.

### Canada Relevance — 10

- Canadian headquarters/decision-making: 10.
- Substantial Canadian product-development operation: 7.
- Other evidence-backed Canadian operation: 4.
- Programme participation or uncertain relationship only: 1.
- Unknown/non-Canadian: 0.

### Evidence Confidence — 100

Confidence measures whether score-bearing tracks were comparably and successfully checked. The first implementation uses weighted completeness:

- Identity and Canada relationship: 15.
- Firmographics/stage: 15.
- Hiring: 15.
- Funding: 20.
- Regulatory: 15.
- Product development/news: 20.

Track factors are: complete = 1.0; partial = 0.5; manual review = 0.25; blocked, failed, no source, or not run = 0.0. Missing primary URLs or fact dates reduce the affected track's factor.

## Ranking and Ties

- Rank only companies meeting the eligibility gate.
- Show Priority score and Evidence confidence together.
- A release top 50 must meet the comparable-coverage gate.
- Include all exact cutoff ties in the review queue, or apply a documented business secondary rule. Alphabetical order is never a ranking rule.
- Publish leave-one-component-out overlap and a plausible score range for incomplete companies.

## Versioning

Every scoring record contains:

- `scoring_version`;
- rules-file checksum;
- as-of date;
- component values;
- fired rule IDs and evidence IDs;
- missing-data flags;
- exclusions and penalties;
- confidence and comparable-coverage status.
