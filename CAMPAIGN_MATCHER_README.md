# Bluebridge Campaign Matcher

The matcher leaves the enrichment JSON unchanged. Only the email draft is sent to OpenRouter; company and contact scoring runs locally.

## 1. Create and review a campaign profile

```powershell
python campaign_matcher.py profile `
  --email-draft "drafts\ai-validation.txt" `
  --output-profile "outputs\campaigns\ai-validation\profile.json" `
  --model "openai/gpt-5.6-luna" `
  --reasoning-effort medium
```

Review and, if necessary, edit the profile JSON. The checked-in `examples\ai_validation_campaign_profile.json` shows the complete schema.

## 2. Match locally and create the review workbook

```powershell
python campaign_matcher.py match `
  --enrichment-json "outputs\subscriber_enrichment_pilot\pilot_data.json" `
  --campaign-profile "outputs\campaigns\ai-validation\profile.json" `
  --suppression-csv "suppression.csv" `
  --output-json "outputs\campaigns\ai-validation\decisions.json" `
  --review-workbook "outputs\campaigns\ai-validation\review.xlsx"
```

On `Contact Decisions`, review rows marked `Primary` and change `Approval Status` from `Pending` to `Approved`. Save the workbook. Backups remain available but are never exported automatically.

If suppression will be applied in another controlled system, replace `--suppression-csv` with `--waive-suppression`. The waiver is recorded in the run summary.

## 3. Export approved primary contacts

```powershell
python campaign_matcher.py export `
  --review-workbook "outputs\campaigns\ai-validation\review.xlsx" `
  --suppression-csv "suppression.csv" `
  --output-csv "outputs\campaigns\ai-validation\approved_recipients.csv"
```

The export rechecks suppression, invalid/generic addresses and duplicates. It does not send email.
