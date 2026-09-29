# Canadian executive contact research

The source is `outputs/canada_company_enrichment_wp6_2026-07-30/Canada_Company_Enrichment_Work_Package_6.xlsx`. The research script uses the `Companies` rows as its stable input. It does not merge repeated company names. Research files and the enriched workbook go in `outputs/canada_executive_research/`.

Install `requirements.txt` in the project's Python environment. The workbook exporter requires `@oai/artifact-tool` from the approved Codex spreadsheet runtime. `collect` makes no model/API calls. The optional `luna` pass uses OpenRouter. Both passes require outbound access to public websites; Luna also requires access to OpenRouter.

An environment variable exported in a terminal is visible to processes launched from that terminal, but not to an independently launched Codex execution session. To make the key available to either session without pasting it into chat or putting it in a command line, save it as a private file outside this repository. Run these commands in the terminal where the key is set; if it is no longer set, the first line prompts for it without echoing it:

```bash
if [ -z "${OPENROUTER_API_KEY:-}" ]; then read -rsp "OpenRouter key: " OPENROUTER_API_KEY; echo; fi
install -d -m 700 "$HOME/.config/bbt_bizdev"
(umask 077; printf '%s' "$OPENROUTER_API_KEY" > "$HOME/.config/bbt_bizdev/openrouter.key")
python3 research_canada_executives.py check-openrouter
```

`check-openrouter` calls OpenRouter's key-status endpoint, prints only authentication status and the remaining key limit, and does not run a model. The script uses `OPENROUTER_API_KEY` from its own environment first, then `~/.config/bbt_bizdev/openrouter.key`. It refuses a key file that other users can read. An alternative path can be supplied with `--key-file /path/to/private/key`. Do not store the key in the research output or paste it into chat.

```bash
python3 research_canada_executives.py prepare
python3 research_canada_executives.py collect --pilot --limit 25
python3 research_canada_executives.py luna --pilot --limit 5 --max-cost-usd 1
python3 research_canada_executives.py review
```

`prepare` creates 1,503 source-row records and a 25-row pilot. Pilot membership uses the source workbook website field and stays stable when a missing website is discovered later. `collect` saves progress after each company. Repeating it skips processed rows; `--refresh` rechecks selected rows. The default batch is 50; `--limit` changes it. Omit `--pilot` after reviewing the pilot to process the remaining rows in workbook rank order.

If the configured public search provider is unavailable, use `collect --pilot --limit 25 --refresh --no-search` for official-site-only collection. `--rows 3,9,18` targets source worksheet rows for a smaller refresh. `website_missing` means the source row has no website; `site_unavailable` means a listed URL failed to load; `no_candidates` means the site was fetched but no contact met the acceptance rule. The collector follows a team or leadership link from an About page, within a 12-page limit, and records `pages_visited` for diagnosis. Search failure and blank cells do not establish that a company has no executives. The first 25-company run and its spot check are recorded in `outputs/canada_executive_research/Pilot_25_Spot_Check_2026-09-24.md`.

`luna` is a second pass for companies with fewer than three accepted executives. It makes at most `--limit` new model calls per run; the default is five. It stops launching new calls once *reported* spend reaches `--max-cost-usd`, default $1. The final call can exceed the threshold because its cost is known only afterward, so the call count is the firmer control. Discovery responses are cached by company, model, and prompt version under `luna_cache/`. When a role is found without a profile URL, one targeted profile-lookup call can follow; its responses are cached under `luna_profile_cache/`. The limit counts both calls. A rerun reads successful cached responses without another model call. `luna_last_run.json` records new calls, cache hits, accepted contacts, review items, reported new spend, and cumulative reported spend across cached calls. Cached responses include cited search-provider excerpts and model usage but never the API key. `luna_cited_evidence.json` keeps the role and profile excerpts used for citation-based acceptance. `--rows 4,5,6` targets specific source worksheet rows and is useful for replaying cached decisions after verifier changes.

Luna searches for current executives, role pages, and exact LinkedIn profiles. Its answer alone never verifies a record. The script fetches the proposed official homepage, checks the company name, and requires the role page to stay on that domain. It accepts a person when the official page pairs their name with the executive role and either directly links to their exact personal LinkedIn profile, or the fetched public LinkedIn page independently has the exact person's name and current-company headline. If direct fetching is blocked, a narrower fallback checks extractive search-provider citations: the role must appear beside the name on an official current team/about page, and the exact personal LinkedIn URL must have the person's name and current company in its own indexed excerpt. The fallback requires the verified company domain and records both excerpts. Old news releases alone cannot pass this fallback. A changed website domain is accepted only when the workbook's listed site redirects to the proposed official domain and its homepage names the company. An unresolved `Alias Review` issue, reported person-level conflict, missing evidence, or mismatched profile leaves the result unaccepted. Unverified people go into `decisions.csv` as `pending` with emails blank. The model cannot supply an email to the workbook; only a matching `mailto:` link on the official team card can. Check `luna_cache/`, `luna_profile_cache/`, and `luna_cited_evidence.json` for the full evidence when spot-checking.

When the source website is blank, Luna can also fill the working `companies.json` record after a live homepage identifies the company in its title, main heading, or legal-name footer. A previously accepted official role page on the same domain can confirm a site whose homepage uses a generic title, as with KA Imaging. The working record keeps `source_website`, `website_source`, `website_evidence_url`, and `website_checked_at`; the source workbook is not changed. A model suggestion for another same-name company is rejected by the homepage check. Failed or truncated model responses can be retried; successful responses remain cached. Site discovery and executive verification remain separate decisions.

The collector automatically accepts a contact only when the workbook website's homepage names the company and an official team-page card contains one person's name, an executive title, and one exact personal LinkedIn link. An individual email is added only when a `mailto:` link in the same card contains the person's surname. Company rows flagged in `Alias Review` cannot pass this automatic check. Each automatic decision carries the official page as its role, LinkedIn, and email evidence URL. The script never constructs an email address from a pattern. These accepted records go directly into `decisions.csv` and are identified by `reason=automated_official_team_card`.

Other entries in `candidates.csv` are leads, not verified contacts. Search results and snippets never auto-accept. `review` merges them into `decisions.csv` without replacing prior decisions. A reviewer checks company identity, current role, and the precise LinkedIn profile. Enter `yes` in `identity_verified`, `employment_verified`, and `linkedin_verified` only with supporting evidence. Supply the person's name, exact title, role source URL, and LinkedIn source URL. Set `decision` to `accept` only after those checks. A published individual business email needs its own `email_evidence_url`; a published individual phone needs `phone_evidence_url`. Leave unsupported fields blank. For a researched batch, put the reviewed names and evidence URLs in `outputs/canada_executive_research/reviewed_additions.csv`, then run `python3 scripts/import_canada_executive_reviews.py`. The import is keyed by candidate ID, so re-running it updates the same review rows rather than duplicating them. The current review and seven deliberately empty companies are documented in `outputs/canada_executive_research/Pilot_25_Research_Followup.md`.

```bash
python3 research_canada_executives.py validate
node scripts/build_canada_executive_workbook.mjs
```

`validate` rejects incomplete accepted records and selects at most three distinct people per company in CEO, COO, CTO, CFO, then other executive order. The exporter adds an `Executive Contacts` sheet to a copy of the source workbook. Every source company gets either contact rows or an explicit no-contact status row. The original workbook remains the baseline.

If the collector cannot access a site or search service, it records `access_blocked` and the errors in `companies.json`. Access failure is not a negative finding. Live collection requires outbound network access. Search-result snippets remain unverified leads and cannot fill the review fields by themselves.

The five-call Luna trial and its evidence review are recorded in `outputs/canada_executive_research/Luna_Pilot_Spot_Check_2026-09-25.md`. Inspect the accepted records and unresolved queue before increasing the call limit. Run `validate` and the workbook exporter after any new accepted contacts.

After `validate`, run `python3 -m scripts.report_canada_executive_coverage` to regenerate `Pilot_25_Coverage.csv`. This separates three-contact companies, partial companies, unverified websites, blocked official sites, pending evidence, and fetched sites with no verified candidate. `companies.json` status tracks the last research pass and is not a count of verified contacts.

## Bounded investigation loop

`investigate` lets Luna choose search and official-page inspection actions. Python executes them, records results, and makes the acceptance decision. Use an isolated output directory to preserve the current pilot ledger:

```bash
python3 research_canada_executives.py investigate --pilot \
  --out outputs/canada_executive_research/investigation_pilot_2026-09-25 \
  --max-cost-usd 1 --max-requests 24 --max-searches 48 --max-fetches 32
```

The first isolated run copies `companies.json`, `decisions.csv`, and `manifest.json` from the main directory. `--pilot` selects eight investigation rows; `--rows` selects other explicit source rows. The command refuses an unrestricted 1,503-company run. `investigation_records.json` links claim decisions to source IDs, excerpts, dates, fetch hashes, model responses, and cost. `investigation_cache/` retains query and page snapshots. `investigation_last_run.json` records spend, limits, pending contacts, and unfinished rows. A completed row is reused on rerun.

New investigation acceptances require a verified company homepage, exact personal LinkedIn URL, current role evidence, and a completed conflict search with no unresolved conflict. Official team cards, indexed exact profiles, attributable personal posts, company posts linked to an official company page, and recent announcements can form eligible combinations. Dated posts and announcements older than 12 months need newer independent role evidence. A blocked LinkedIn page, a personal profile alone, a wrong-company result, or a failed search leaves a contact pending. Existing accepted contacts remain unchanged; new conflicts involving them are recorded as baseline flags. Email and phone remain blank unless separately published and verified.

For new CLI runs, `collect` and the older fixed-call `luna` pass now place newly found automatic contacts in `pending` until `investigate` applies the shared evidence and conflict gate. Previously accepted records stay accepted. The older auto-accept descriptions above document how the 37-contact baseline was built.

For a repeatable blinded replay, use `investigate --blind-replay` with a separate `--out` directory. The command copies the baseline, hides Dwayne Sansone, Manmeet Maggu, and Dolma Tsundu from the model input, and stores their exact expected matches in `blinded_truth.json` for scoring only. It then investigates those three companies and the Optina, Radialis, Swiftsure, Janpix, and Kyva traps. The summary reports exact-profile recoveries and any accepted trap contact. Rerunning the same completed directory uses its saved records without another paid request.

## 28 September 2026 bounded investigation update

Implemented role-source gate feedback, stricter redirect/date/company-post checks, hashed excerpts, and a durable request journal that blocks paid restart when billing is unknown. The focused suite passes 39 tests. The new isolated eight-company pilot retained 37 selected contacts, added zero accepted contacts, and recorded eight pending decisions (six previously unseen people). It cost $0.09933135 over 24 requests; Janpix remained unfinished. A blinded Flutter Care check cost $0.01824215 and stayed pending for insufficient current-role evidence. Both ledgers validated, and offline replay added no spend. Total task spend is approximately $0.504 of the authorized $1. See the latest section of `CANADA_EXECUTIVE_AUTOMATION.md` for the full audit and remaining limits. The original ledger and the 1,503-company batch were not changed.

## Broad research on all 25 pilot companies

The broader experiment uses **$1 per company**, superseding the former $1 total allowance. Run it in a fresh isolated directory:

```bash
python3 -m bbt_bizdev.canada_executive_broad \
  --out outputs/canada_executive_research/broad_new_run \
  --per-company-usd 1 --workers 3
python3 -m scripts.report_broad_executive_benchmark \
  outputs/canada_executive_research/broad_new_run
```

This always selects the original 25-company pilot. It does not expose historical contacts or previous Luna leads to the model. Two research rounds allow multiple adaptive server searches; a third call returns structured claims. Per-company `record.json` files retain request payloads, responses, citations, fetches, costs and decisions. A completed record replays without paid calls. An interrupted or unknown-cost record stops for reconciliation. `--repackage` re-extracts claims from completed retained dossiers, preserving initial claims and decisions; it may incur model and conflict-search costs. The reporting command's `--reassess` option replays the current deterministic acceptance gate without network calls and preserves the previous decisions.

The 28 September experiment attempted all 25 and completed 24, with AssistIQ stopped on an HTTP error with unknown usage. After programmatic output-contract and conflict-parser fixes, it proposed 64 candidates including 29 of the historical 37 exact profiles. Seven contacts passed the gate, all already known; 57 remained pending. Reported cumulative experiment spend was $3.19439329, excluding one unreported request. See `outputs/canada_executive_research/broad_25_structured_v2_2026-09-28/REPORT.md` for all 25 company comparisons. The historical ledger remains at 37 selected contacts. The broader research is useful, but the identity and evidence interpretation checks remain the largest limits on recovery.

### Offline identity and role replay

The latest gate uses verified homepage redirects, narrowly resolved single-domain workbook name variants, additional official team-page paths, and safer person/title association. It preserves old decisions and source-workbook alias provenance. To reassess an isolated copy of a completed run with current workbook identity metadata:

```bash
python3 -m scripts.report_broad_executive_benchmark PATH_TO_ISOLATED_COPY \
  --reassess --sync-identity
python3 -m scripts.diagnose_canada_executive_gate PATH_TO_PREVIOUS_RUN PATH_TO_ISOLATED_COPY
```

The saved `broad_25_gate_v5_2026-09-28` replay raises selected contacts from 7 to 12 without additional searches or spend. Identity/activity failures fall from 33 to 19 and role failures from 11 to 9. The combined category falls from 44 to 28, with some candidates now blocked at a later profile/conflict check. There are 52 pending claims, and the original 37-contact ledger is unchanged. See the replay's `BOTTLENECK_REPORT.md` for individual transitions. The focused suite passes 51 tests.

### Fresh research with gate feedback

The current broad runner adds a draft structured call between its two research rounds. Python sends missing identity, current-role and exact-profile evidence checks back to Luna before the second round. It starts fresh from workbook company details, retains the strict gate and keeps a $1 per-company ceiling.

The completed `fresh_feedback_25_2026-09-28` experiment covered all 25 companies for $3.18496872. It proposed 32 of the 37 historical exact profiles, versus 29 in the previous run. There were 13 raw automatic acceptances versus 12 previously. Cross-run conflict checks flag one of those acceptances, leaving 12 unflagged contacts and 53 pending in `review_safe_decisions.csv`. The original ledger remains unchanged. The focused suite passes 52 tests.

Rebuild the comparison without API calls:

```bash
python3 -m scripts.report_broad_executive_benchmark outputs/canada_executive_research/fresh_feedback_25_2026-09-28
python3 -m scripts.compare_canada_executive_runs \
  outputs/canada_executive_research/broad_25_gate_v5_2026-09-28 \
  outputs/canada_executive_research/fresh_feedback_25_2026-09-28
```

`FRESH_COMPARISON.md` distinguishes raw acceptance from the review-safe list. A previous unresolved conflict is conservatively held pending for reconciliation even if a fresh run does not find it. This comparison step makes no manual per-contact evidence decisions and does not alter raw experimental records.
