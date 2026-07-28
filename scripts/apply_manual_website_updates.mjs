import fs from "node:fs/promises";
import path from "node:path";

const workspace = "C:/Users/Admin/Documents/BBT_bizdev";
const inputPath = path.join(
  workspace,
  "outputs/canada_website_luna_2026-07-28_pilot_v2/canonical_companies_luna_websites_enriched.json",
);
const outputDir = path.join(workspace, "outputs/canada_website_manual_updates_2026-07-28");
const outputPath = path.join(outputDir, "canonical_companies_manual_websites_enriched.json");
const evidencePath = path.join(outputDir, "manual_website_evidence.json");

const updates = [
  {
    company_id: "ca-company-69913e8412900a9e",
    company_name: "26 Therapeutics",
    submitted_url: "https://www.26therapeutics.com/en/",
    website: "https://www.26therapeutics.com/en/",
    domain: "26therapeutics.com",
    status: "active_verified",
    evidence_url: "https://www.26therapeutics.com/en/",
    notes: "Official company site. Automated direct access is challenge-protected, but current official pages are indexed.",
  },
  {
    company_id: "ca-company-d1ce240abe77c2e6",
    company_name: "Angiochem Inc.",
    submitted_url: "https://www.angiochem.com/careers",
    website: "https://www.angiochem.com/",
    domain: "angiochem.com",
    status: "active_verified",
    evidence_url: "https://www.angiochem.com/",
    notes: "Official company site; canonicalized from the supplied careers URL to the site root.",
  },
  {
    company_id: "ca-company-4598d4f54a152020",
    company_name: "SpecificiT Pharma",
    submitted_url: "https://amorchem.com/portfolio/specificit-pharma-inc/",
    website: "",
    domain: "specificitpharma.com",
    status: "dissolved_historical_site",
    evidence_url: "https://amorchem.com/portfolio/specificit-pharma-inc/",
    notes: "Investor portfolio page identifies the historical company domain. Federal-company records report dissolution on 2021-06-15, so this is not treated as an active hiring website.",
  },
];

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const byId = new Map((payload.companies ?? []).map((company) => [company.company_id, company]));

for (const update of updates.filter((item) => item.status === "active_verified")) {
  const company = byId.get(update.company_id);
  if (!company) throw new Error(`Company not found: ${update.company_id}`);
  company.website = update.website;
  company.domain = update.domain;
  company.last_enriched_at = "2026-07-28";
}

payload.generated_at = new Date().toISOString();
await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
await fs.writeFile(
  evidencePath,
  `${JSON.stringify(
    {
      schema_version: "1.0",
      generated_at: new Date().toISOString(),
      records: updates.map((item) => ({ ...item, reviewed_at: "2026-07-28" })),
    },
    null,
    2,
  )}\n`,
  "utf8",
);

console.log(JSON.stringify({ outputPath, evidencePath, active_updates: 2, inactive_records: 1 }, null, 2));
