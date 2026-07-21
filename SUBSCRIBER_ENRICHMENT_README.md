# Subscriber Enrichment Pilot

Build evidence-bound company and contact segmentation from the subscriber CSV.

## Run

```powershell
$env:OPENROUTER_API_KEY = "..."  # optional; omitted runs conservative evidence rules
python subscriber_enrichment.py `
  --input "C:\path\to\subscribers.csv" `
  --output-json "outputs\subscriber_enrichment_pilot\pilot_data.json" `
  --sample-size 150
```

The default model is `openai/gpt-5.6-luna` with medium reasoning. Company research is cached in
`.subscriber_enrichment_cache/`; cache entries contain public company evidence only.

Generate the workbook with the bundled Codex Node runtime and `@oai/artifact-tool`:

```powershell
node build_subscriber_enrichment_workbook.mjs `
  outputs\subscriber_enrichment_pilot\pilot_data.json `
  outputs\subscriber_enrichment_pilot\Bluebridge_Subscriber_Enrichment_Pilot.xlsx `
  outputs\subscriber_enrichment_pilot\previews
```

All classifications are constrained to the workbook taxonomy. Unsupported facts remain
`Unknown`; redirects, conflicts, low-confidence records, and every pilot company are placed
in the manual review queue.

## Evidence selection

- The resolved homepage is always the primary first-party source when available.
- Up to three same-site pages are scored and selected across regulatory/quality,
  product/technology, and About/company categories.
- Up to five Google News articles must mention the exact company name and are ranked for
  regulatory, funding, clinical, launch, partnership, and product signals.
- The workbook stores the exact selected URLs and the subset cited by the LLM.
- Employee bands require explicit numeric workforce evidence; confidence is capped when
  first-party evidence is missing, redirects externally, or has weak URL support.
