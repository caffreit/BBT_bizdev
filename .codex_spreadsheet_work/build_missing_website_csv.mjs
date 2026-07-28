import fs from "node:fs/promises";
import path from "node:path";
import { Workbook } from "@oai/artifact-tool";

const workspace = "C:/Users/Admin/Documents/BBT_bizdev";
const companiesPath = path.join(
  workspace,
  "outputs/canada_website_manual_updates_2026-07-28/canonical_companies_manual_websites_enriched.json",
);
const provenancePath = path.join(
  workspace,
  "outputs/canada_company_identity_2026-07-27/source_provenance.json",
);
const outputDir = path.join(workspace, "outputs/canada_missing_websites_2026-07-28");
const outputPath = path.join(outputDir, "canada_companies_missing_websites_2026-07-28_updated.csv");
const previewPath = path.join(outputDir, "canada_companies_missing_websites_updated_preview.png");

const companiesPayload = JSON.parse(await fs.readFile(companiesPath, "utf8"));
const provenancePayload = JSON.parse(await fs.readFile(provenancePath, "utf8"));
const provenanceByCompany = new Map();
for (const row of provenancePayload.records ?? []) {
  if (!provenanceByCompany.has(row.company_id)) provenanceByCompany.set(row.company_id, []);
  provenanceByCompany.get(row.company_id).push(row);
}

const clean = (value) => String(value ?? "").replace(/\s+/g, " ").trim();
const missing = (companiesPayload.companies ?? [])
  .filter((row) => !clean(row.website))
  .sort((a, b) => clean(a.company_name).localeCompare(clean(b.company_name), "en"));

const rows = missing.map((company) => {
  const provenance = provenanceByCompany.get(company.company_id) ?? [];
  const sources = [...new Set(provenance.map((row) => clean(row.source_name)).filter(Boolean))];
  const category = clean(company.product_category);
  let summary = clean(company.product_summary);
  if (!summary) {
    summary = clean(provenance.map((row) => row.description).find(Boolean));
  }
  const productContext = [category && category !== "unknown" ? category : "", summary]
    .filter(Boolean)
    .join(" — ");
  return [clean(company.company_name), sources.join("; "), productContext];
});

if (rows.length !== 443) {
  throw new Error(`Expected 443 missing-website companies, found ${rows.length}`);
}

const csvEscape = (value) => {
  const text = clean(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};
const matrix = [
  ["Company", "Source(s)", "Product / context"],
  ...rows,
];
const csvText = matrix.map((row) => row.map(csvEscape).join(",")).join("\r\n") + "\r\n";

await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(outputPath, "\uFEFF" + csvText, "utf8");

const workbook = await Workbook.fromCSV(csvText, { sheetName: "Missing Websites" });
const sheet = workbook.worksheets.getItem("Missing Websites");
sheet.getRange("A1:C1").format = {
  fill: "#17365D",
  font: { bold: true, color: "#FFFFFF" },
};
sheet.getRange(`A1:C${matrix.length}`).format.wrapText = true;
sheet.getRange(`A1:A${matrix.length}`).format.columnWidth = 28;
sheet.getRange(`B1:B${matrix.length}`).format.columnWidth = 38;
sheet.getRange(`C1:C${matrix.length}`).format.columnWidth = 90;
sheet.freezePanes.freezeRows(1);

const inspection = await workbook.inspect({
  kind: "table",
  range: "Missing Websites!A1:C12",
  include: "values",
  tableMaxRows: 12,
  tableMaxCols: 3,
  maxChars: 7000,
});
console.log(inspection.ndjson);

const preview = await workbook.render({
  sheetName: "Missing Websites",
  range: "A1:C18",
  scale: 1,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

console.log(JSON.stringify({
  outputPath,
  previewPath,
  rows: rows.length,
  header: matrix[0],
}, null, 2));
