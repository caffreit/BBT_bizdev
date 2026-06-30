# Legacy Lead Scoring Rules

This documents the legacy rule-based score helper. These fields are no longer shown in the user-facing workbook; the `Leads` tab now uses filterable attributes, persona, and BBT quadrant instead of scores.

The score text is built from:

- company product type
- company name
- discovery rationale
- company description
- category / track
- trigger event text

It does **not** currently parse the full evidence URL page for scoring. It uses the fields already captured by the discovery and trigger adapters.

## Legacy Score Flags

| Workbook column | Score flag | Current rule |
| --- | --- | --- |
| L | `Recently funded +3` | `1` if any attached trigger has trigger type exactly `Funding` |
| M | `AI/SaMD/device +3` | `1` if score text contains any of: `ai`, `samd`, `medical device`, `diagnostic`, `imaging`, `wearable`, `stethoscope` |
| N | `Hiring QA/reg/V&V +3` | `1` if score text contains any of: `regulatory affairs`, `quality engineer`, `design assurance`, `v&v` |
| O | `Clinical validation +2` | `1` if score text contains any of: `clinical`, `diagnostic`, `screening`, `validation` |
| P | `FDA/CE/reg language +2` | `1` if score text contains any of: `fda`, `ce `, `samd`, `regulated` |
| Q | `Grant/public funding +2` | `1` if any discovery hit has source type exactly `Grant/funding` |
| R | `University/grant origin +2` | `1` if any discovery hit has source type `University/spinout` or `Grant/funding` |
| S | `No obvious reg team +2` | Always `0` currently; placeholder for future research |
| T | `Pre-commercial +1` | `1` if any discovery hit has source type exactly `Accelerator` |
| U | `Large company -1` | Always `0` currently; placeholder for future firmographic logic |
| V | `Wellness/non-medical -2` | `-1` if score text contains `wellness`; otherwise `0` |
| W | `Pharma-only -2` | `-1` if score text contains `pharma-only`; otherwise `0` |

## Funding Logic

`Recently funded +3` currently means “we have a funding trigger attached to the company.”

It does **not** currently check:

- how recent the funding date is
- how much money was raised
- whether it was seed, Series A, grant, debt, etc.

The “recently” part is implied by the trigger source/search process, not calculated from dates.

## Keyword Logic

The keyword-driven flags are broad text checks. For example:

- `AI/SaMD/device +3` fires if the captured evidence text includes `ai`, `samd`, `medical device`, etc.
- `Clinical validation +2` fires if the text includes `clinical`, `diagnostic`, `screening`, or `validation`.
- `FDA/CE/reg language +2` fires if the text includes `fda`, `ce `, `samd`, or `regulated`.

This means the current system is good for a first-pass prioritisation signal, but it can over-match. For example, `ai` is a very broad substring check.

## Negative Flags

The negative columns are currently basic placeholders:

- `Wellness/non-medical -2` applies a penalty when `wellness` appears in score text.
- `Pharma-only -2` applies a penalty when `pharma-only` appears in score text.
- `Large company -1` is not implemented yet and always stays `0`.

Because the negative flag values are stored as `-1`, the formula multiplies them by `2`, creating a `-2` score effect.

## Priority Band

After flags are calculated, the total score maps to:

| Score | Priority band |
| --- | --- |
| `10+` | `Strong` |
| `7-9` | `Good` |
| `4-6` | `Maybe` |
| `0-3` | `Low` |

## Current Limitations

- Funding amount and funding recency are not parsed.
- Hiring score is based on role keywords in captured text, not solely on job-source hits.
- Evidence pages are not re-fetched for scoring.
- “No obvious reg team” and “Large company” are placeholders.
- The score is not yet persona-weighted.
