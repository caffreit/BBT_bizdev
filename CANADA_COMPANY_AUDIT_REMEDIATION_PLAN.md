# Canada Company Enrichment — Audit Remediation Programme

## Purpose

This programme turns the Work Package 6 audit into an ordered implementation backlog. The objective is not merely to add more data. It is to produce a reproducible, evidence-bound ranking whose meaning, uncertainty, and limitations are explicit.

The current workbook remains a research queue. It must not be described as a validated ordering until the release gates in WP10 pass.

## Governing Rules

1. Unknown evidence is not negative evidence and earns no positive points.
2. Capture date, evidence date, and event date remain separate.
3. A track may be `complete_zero` only after its documented source set and traversal gate complete.
4. Every scored fact must identify the evidence record(s) and scoring rule that produced it.
5. Scoring is deterministic. LLMs may discover or classify candidates, but accepted facts require rule-based validation and evidence.
6. A company cannot gain a ranking advantage merely because it was researched more deeply than another company.
7. Fit, timing, ability to buy, and evidence confidence are separate outputs.
8. The top-50 boundary must include tie handling and uncertainty, not alphabetical selection disguised as rank precision.

## Execution Order

### WP0 — Baseline, Reproducibility, and Release Manifest

**Status:** foundational work complete; refresh-age enforcement remains.

Jobs:

- Record the current WP6 workbook, input files, run dates, row counts, coverage rates, score distributions, cutoff ties, and known defects.
- Move the workbook builder from the ignored output directory into tracked source control.
- Add an input manifest containing file paths, schema versions, checksums, and generation dates.
- Add one command that rebuilds the workbook from the manifest.
- Fail the build when a required input is absent or materially older than its declared refresh policy.

Acceptance:

- A fresh checkout plus declared input snapshots can reproduce the same company rows and component scores.
- The release manifest explains which code and evidence created the workbook.

### WP1 — ICP, Fit Definition, and Scoring Contract

**Status:** complete as version `2.0-draft.1`; calibration remains under WP9.

Jobs:

- Define an eligible prospect and explicit exclusions.
- Define `fit` as suitability for BlueBridge services—not merely presence of medtech keywords.
- Separate outputs into `fit`, `timing`, `ability_to_buy`, `evidence_confidence`, and `priority`.
- Define observable criteria, point values, caps, penalties, and required evidence for every rule.
- Define missing-data treatment: unknown contributes zero and creates a confidence/completeness penalty, not an inferred fact.
- Make every score return a rule-level explanation and evidence identifiers.
- Version the scoring contract and preserve historical versions.

Acceptance:

- The same normalized inputs always return the same score and explanations.
- No rule depends on free-form LLM judgment at scoring time.
- No company receives stage/size or Canada-location points when those fields are unknown.

### WP2 — Identity, Location, Stage, and Firmographics

**Status:** in progress; employee-band and operating-status evidence remain the largest gaps.

Jobs:

- Resolve legal entity, trading name, parent, subsidiaries, acquisitions, former names, and product brands.
- Propagate supported city/province/HQ evidence into the canonical company table.
- Add employee-band evidence with source date and confidence.
- Add operating status: active, acquired, inactive, dissolved, or uncertain.
- Add firmographic completeness and manual-review queues.
- Re-audit shared domains and generic or same-name identities.

Acceptance:

- At least 90% of top-100 candidates have evidence-backed stage/size and Canada relationship.
- Ambiguous identities cannot automatically receive scored evidence.
- Acquired/inactive status is checked before inclusion in the outreach queue.

### WP3 — Hiring Evidence Hardening

**Status:** correctness fixes complete; equivalent-coverage run and labelled recall test remain.

Jobs:

- Re-fetch every accepted job URL and require a successful, current, company-matched listing.
- Do not treat a recognized ATS hostname alone as proof that a role is open.
- Treat parser/JSON errors as `partial` or `failed`, never `complete_zero`.
- Fetch job-detail content before role-family classification.
- Apply explicit Canada/remote-Canada rules and retain global roles separately.
- Preserve distinct same-title roles by job ID/location rather than collapsing by title.
- Add expiry/recheck logic and prevent validation date from masquerading as posting date.
- Measure false positives and missed roles against a labelled sample.

Acceptance:

- Every scored role has a live official URL, checked-at date, identity match, location, and role-family explanation.
- A closed or inaccessible listing cannot contribute commercial-intent points.

### WP4 — Funding Coverage and Semantics

**Status:** correctness fixes complete; full-universe source run and recall test remain.

Jobs:

- Search all eligible companies, not only companies already known to have investor backing.
- Search legal names, aliases, former names, and parent/subsidiary names without a silent three-name cap.
- Ingest company newsrooms, investor announcements, original newswires, and relevant government/provincial sources.
- Merge funding events found by product/news research into the canonical funding-event table.
- Distinguish equity, debt, grant, repayable contribution, non-repayable contribution, loan, and portfolio backing.
- Separate announcement, agreement/start, closing, and publication dates.
- Deduplicate the same round across company, investor, newswire, and government sources.
- Record incomplete pagination and count collapse.

Acceptance:

- `complete_zero` means the defined funding source set was searched for that company.
- Latest-round fields reconcile with all accepted event sources.
- Portfolio presence alone never becomes a dated round or disclosed ability-to-buy amount.

### WP5 — Regulatory Semantics and Recall

**Status:** semantics hardened; alias/product-name recall audit remains.

Jobs:

- Search legal names, aliases, parents, subsidiaries, manufacturers, and product names.
- Expand beyond exact pre-classified categories while retaining strict attachment rules.
- Preserve active, archived, suspended, withdrawn, and uncertain states.
- Verify MDEL status/expiry and retain a record-specific URL where possible.
- Keep MDEL, device listing, clinical trial, submission claim, licence, clearance, and approval as distinct signals.
- Add explicit parent/distributor/foreign-manufacturer review routes.
- Score only currently relevant regulatory milestones; historical records remain context.

Acceptance:

- MDEL or establishment listing cannot be presented or scored as product approval.
- Archived or inactive records cannot create a current milestone without a separate current event.
- A stratified manual audit estimates false-negative and false-positive rates by regulator.

### WP6 — Product Development and News Recall

**Status:** correctness and default-scope fixes complete; full-universe run remains.

Jobs:

- Run equivalent first-pass coverage across the full eligible universe before final ranking.
- Traverse sitemap, RSS/Atom, newsroom archive, pagination, structured data, and relevant product/clinical pages.
- Query canonical name plus aliases using separate funding, regulatory, clinical, launch, manufacturing, expansion, partnership, and acquisition searches.
- Add an explicit outlet/source inventory and report which sources were attempted.
- Replace hard-coded accepted-event constants with stored review decisions tied to discovered candidates and fetched evidence.
- Require an accepted event to reference its actual discovery candidate or a documented independent discovery route.
- Distinguish current product state from historical statements embedded in navigation, archives, and footers.
- Treat a homepage-only check or one empty Google News query as incomplete, not `complete_zero`.

Acceptance:

- Every eligible company has an equivalent documented first-pass source set.
- All accepted events have identity, materiality, date, source-quality, and deduplication decisions.
- Hard-coded company-specific acceptance branches are removed.

### WP7 — Coverage Equalisation and Circular-Bias Removal

**Status:** in progress; the diagnostic release currently has zero comparable-coverage companies.

Jobs:

- Create a universally available pre-research score used only to select the next research batch.
- Research in batches, recompute evidence scores, and continue until the top set stabilises.
- Do not award a track's points when comparable companies have not received the same track coverage.
- Publish per-company coverage vectors and a comparable-coverage flag.
- Include all companies tied at a cutoff or use a documented secondary business rule.

Acceptance:

- Final top prospects have comparable coverage across score-bearing tracks.
- The top-50 set changes by less than the agreed threshold after the final research batch.
- No company is included or excluded solely by alphabetical tie-breaking.

### WP8 — Deterministic Scoring V2 and Uncertainty

**Status:** deterministic scorer implemented and tested; sensitivity and workbook integration remain.

Jobs:

- Implement the versioned scoring contract in tracked Python code and machine-readable rules.
- Produce component scores, evidence IDs, rule explanations, missing-data flags, and a confidence grade.
- Keep absolute exclusions separate from penalties.
- Add recency decay by event type rather than one generic window.
- Add sensitivity results: leave-one-component-out, plausible missing-data ranges, and cutoff stability.
- Make workbook ranking formula- or build-driven from scoring outputs; do not retain static row rank after inputs change.

Acceptance:

- Scores reconcile exactly between JSON output, tests, and workbook.
- A score is never displayed without completeness/confidence.
- The scorer passes boundary, missing-data, conflict, and regression tests.

### WP9 — Labelled Audit Set and Calibration

**Status:** deterministic 100-company sample created; independent labels remain.

Jobs:

- Label the current top 50, at least 25 companies around the cutoff, and at least 25 random companies.
- Independently review identity, fit, live hiring, funding, regulatory status, current product activity, and news.
- Record false positives, false negatives, disagreements, and reviewer confidence.
- Compare rankings with reviewer ordering and, when available, outreach/meeting/opportunity outcomes.
- Tune weights only against the labelled set; retain a holdout set for final evaluation.

Acceptance:

- Publish precision/recall for evidence tracks and ranking-quality metrics.
- The release meets agreed thresholds on the holdout set.
- Weight changes include a before/after impact report.

### WP10 — Workbook Rebuild and Release Gate

**Status:** pending.

Jobs:

- Rebuild Companies, supporting evidence, incomplete-source, methodology, and top-prospect tabs from Scoring V2 outputs.
- Show fit, timing, ability to buy, confidence, comparable coverage, score range, and review status separately.
- Correct freshness to use fact/event dates; show capture/check dates independently.
- Link every component to rule explanations and evidence IDs.
- Make review fields have one source of truth between Companies and Top Prospects.
- Verify formulas, tied cutoffs, completeness counts, hyperlinks, and visual layout.

Acceptance:

- No formula errors or static-rank drift.
- Workbook totals reconcile with normalized JSON outputs.
- Top prospects pass manual review before outreach.
- The release manifest and limitations are included.

### WP11 — Monitoring and Operating Controls

**Status:** pending.

Jobs:

- Add source-level raw/accepted/rejected counts, parser-version tracking, and count-collapse alerts.
- Add freshness SLA alerts by track and priority band.
- Add regression fixtures from real response shapes.
- Add monthly false-positive/false-negative sampling.
- Preserve append-only history and recompute current state from evidence.

Acceptance:

- Failed, blocked, partial, and zero remain visibly distinct.
- Material source drift or coverage collapse fails the run rather than silently lowering scores.

## Release Dashboard

The programme should report these gates on every candidate release:

- Comparable coverage percentage for top 50 and top 100
- Unknown stage/size percentage
- Evidence-backed Canada relationship percentage
- Track precision/recall on the audit set
- Top-50 cutoff ties and tie policy
- Top-50 stability after the final enrichment batch
- Leave-one-component-out top-50 overlap
- Percentage of scored facts with primary URLs and fact dates
- Formula/JSON reconciliation failures
- Manual-review completion for top prospects

## Latest Diagnostic Checkpoint — 2026-08-04

Scoring V2 was run locally against the existing WP6 evidence for all 1,503 companies. This is a diagnostic result, not a releasable ranking.

- Release ready: **no**
- Companies with comparable coverage: **0 / 1,503**
- Top-50 companies with comparable coverage: **0 / 50**
- Nominal score cutoff: **20 points**, with **62 companies** at or above the cutoff because of ties
- Product/news: **1,453 not run**, 31 complete matches, 7 complete zero, and 12 blocked
- Funding: **1,234 not run**, 103 complete matches, and 166 partial
- Firmographics: **1,503 partial**; every current top-50 company lacks evidence-backed employee band
- Current top-50 missing flags: employee band 50, service need 48, Canada relationship 8
- Leave-one-component-out top-50 overlap: fit 94%, timing 70%, ability to buy 88%, Canada relevance 100%

Interpretation: the present ordering is most sensitive to timing evidence and is still materially shaped by unequal research coverage. A numeric score may be useful for directing the next research batch, but must not yet be represented as a validated prospect rank.

The corrected product/news collector passed a local execution smoke test, but outbound requests were blocked by the execution environment. A live refresh requires explicit authorization to send company-name research queries to company websites and Google News.

## Immediate Sequence

1. Complete WP0 and WP1.
2. Fix high-risk correctness defects in WP3, WP4, WP5, and WP6.
3. Complete identity/firmographics in WP2.
4. Equalise coverage through WP7.
5. Implement and validate Scoring V2 in WP8 and WP9.
6. Regenerate the workbook through WP10.
7. Put WP11 controls into the recurring refresh process.
