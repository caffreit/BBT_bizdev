# Lead Classification Rules

This documents the rule-based fallback classifier used when the LLM is not configured, disabled, errors, or returns invalid output. The rules are ordered: the first matching rule wins.

## Persona Rules

| Order | Persona | When it matches |
| --- | --- | --- |
| 1 | Jobs-led capability gap | Source type is `Jobs`, or trigger type is `Hiring signal` |
| 2 | Regulatory-led opportunity | Source type is `Regulatory database`, or any trigger type contains `regulatory` or `clearance` |
| 3 | Funded startup | Trigger type is `Funding` or `Grant/public funding`, or source type is `Grant/funding` |
| 4 | University/spinout | Source type is `University/spinout` |
| 5 | Early startup | Source type is `Accelerator`, or trigger type is `Accelerator/cohort` |
| 6 | Scaleup | Source type is `Conference`, `VC portfolio`, or `Public ranking` |
| 7 | Established medtech | Catch-all if nothing above matches |

Precedence is:

```text
Jobs > Regulatory > Funding > University > Accelerator > Market presence > Catch-all
```

Example: if a company is both in an accelerator and hiring for regulatory roles, it becomes `Jobs-led capability gap` because jobs are checked first.

## Quadrant Rules

The quadrant is assigned inside the same winning rule as the persona.

| Persona | Primary BBT quadrant |
| --- | --- |
| Jobs-led capability gap | `Embedded support` |
| Regulatory-led opportunity | `Regulatory/validation` |
| Funded startup | `Advisory` |
| University/spinout | `Advisory` |
| Early startup | `Design/dev` if text mentions `prototype`, `device`, `diagnostic`, or `imaging`; otherwise `Advisory` |
| Scaleup | `Commercial readiness` |
| Established medtech | `Advisory` |

If a quadrant somehow falls outside the configured taxonomy, it is reset to `Advisory`.

## Secondary Tag Rules

The secondary tag is also assigned from the winning persona rule.

| Persona | Secondary tag |
| --- | --- |
| Jobs-led capability gap | `Hiring gap` |
| Regulatory-led opportunity | `Regulatory pathway` |
| Funded startup | `Funding trigger` |
| University/spinout | `Clinical validation` if lead text contains `clinical`; otherwise `Medical device` |
| Early startup | `Accelerator/cohort` |
| Scaleup | `SaMD/AI` if lead text contains `ai`, `samd`, or `software`; otherwise `Medical device` |
| Established medtech | `SaMD/AI` if lead text contains `ai`, `samd`, or `software`; otherwise `Medical device` |

If a tag somehow falls outside the configured taxonomy, it is reset to `Medical device`.

## Pain, Value Prop, and Outreach Logic

Pain hypothesis, value prop, and outreach angle are directly linked to the winning persona rule. They are not separately scored.

| Persona | Pain hypothesis | Value prop | Outreach angle |
| --- | --- | --- | --- |
| Jobs-led capability gap | Active regulatory, quality, validation, or clinical workload that the team is trying to staff. | Embedded support to reduce hiring pressure and keep regulated delivery moving. | Reference the open role or hiring signal and offer targeted regulatory, QA, V&V, or clinical delivery support. |
| Regulatory-led opportunity | Needs help turning regulatory movement into validation, claims, or post-market planning. | Translate regulatory status into practical evidence, documentation, and next-market readiness. | Lead with a regulatory or validation review tied to the clearance, listing, or regulatory evidence. |
| Funded startup | Fresh budget and pressure to convert a funded plan into regulated product work. | Sequence regulatory, validation, product, and quality work before hiring or scaling too far. | Congratulate them on funding and offer a planning review for the next regulated-product milestones. |
| University/spinout | Needs to turn academic or translational evidence into a product, regulatory, and validation story. | Shape the first credible pathway from research output to regulated product development. | Offer early advisory support around product definition, validation evidence, and regulatory pathfinding. |
| Early startup | Needs to sharpen product, evidence, and regulatory assumptions while still early. | Lightweight advisory or design-development input before costly choices harden. | Reference the cohort and offer a compact product, validation, or regulatory readiness conversation. |
| Scaleup | Needs to align product, evidence, and claims while expanding commercially or entering new channels. | Strengthen regulated-product readiness for commercial expansion and customer scrutiny. | Reference the market signal and offer a readiness review around claims, evidence, and delivery risk. |
| Established medtech | Broad need for defensible regulatory, validation, claims, or productisation support. | Clarify the regulated-product path and reduce avoidable evidence or delivery risk. | Open with the strongest public evidence and offer a short fit conversation around regulatory and validation needs. |

## LLM Use and Fallback

If LLM enrichment is configured, the model can classify the lead using the same allowed taxonomy. If the LLM is not used or fails validation, the rule-based classifier above is used instead.

The workbook records this explicitly:

| Column | Meaning |
| --- | --- |
| `LLM used` | `Yes` if a valid LLM classification was used; otherwise `No` |
| `Fallback reason` | Why rules were used, such as `llm_not_configured`, `llm_error`, `invalid_json`, `invalid_taxonomy`, or `cache_miss_llm_disabled` |

