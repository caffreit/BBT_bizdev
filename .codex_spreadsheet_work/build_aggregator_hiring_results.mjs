import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const workspace = "C:/Users/Admin/Documents/BBT_bizdev";
const runDir = path.join(workspace, "outputs/canada_aggregator_hiring_2026-07-28_full_v1");
const aggregatorPath = path.join(runDir, "aggregator_hiring_evidence.json");
const completenessPath = path.join(runDir, "aggregator_hiring_completeness.json");
const officialPath = path.join(
  workspace,
  "outputs/canada_hiring_after_all_source_websites_2026-07-28/hiring_evidence.json",
);
const canonicalPath = path.join(
  workspace,
  "outputs/canada_hiring_after_all_source_websites_2026-07-28/canonical_companies_hiring_enriched.json",
);
const workbookPath = path.join(runDir, "canada_aggregator_hiring_results_2026-07-28.xlsx");
const csvPath = path.join(runDir, "canada_aggregator_hiring_roles_2026-07-28.csv");

const aggregator = JSON.parse(await fs.readFile(aggregatorPath, "utf8"));
const completeness = JSON.parse(await fs.readFile(completenessPath, "utf8"));
const official = JSON.parse(await fs.readFile(officialPath, "utf8"));
const canonical = JSON.parse(await fs.readFile(canonicalPath, "utf8"));
const companyById = new Map(canonical.companies.map((row) => [row.company_id, row]));
const clean = (value) => String(value ?? "").replace(/\s+/g, " ").trim();
const normalize = (value) => clean(value).toLowerCase().replace(/[^a-z0-9]+/g, "");
const identityFor = (row) => {
  const company = companyById.get(row.company_id) ?? {};
  return clean(company.domain).toLowerCase() || normalize(row.company_name);
};
const keyFor = (row) => `${identityFor(row)}|${normalize(row.job_title)}`;

const officialKeys = new Set(official.records.map(keyFor));
const grouped = new Map();
for (const row of aggregator.records) {
  const key = keyFor(row);
  if (!grouped.has(key)) grouped.set(key, []);
  grouped.get(key).push(row);
}
const sourceRank = (row) => {
  const url = clean(row.job_url).toLowerCase();
  if (row.confidence === "high") return 3;
  if (/greenhouse|lever|ashby|workable|smartrecruiters|myworkday|linkedin\.com\/jobs\/view|indeed.*[?&](?:v?jk)=/.test(url)) return 2;
  return 1;
};
const deduped = [...grouped.values()]
  .map((rows) => rows.sort((a, b) => sourceRank(b) - sourceRank(a))[0])
  .sort((a, b) => (
    clean(a.company_name).localeCompare(clean(b.company_name), "en")
    || clean(a.job_title).localeCompare(clean(b.job_title), "en")
  ));

const headers = [
  "Company", "Job title", "Role family", "Seniority", "Location", "Posted at",
  "Source", "Confidence", "Verification basis", "Previously found officially",
  "Job URL", "Evidence summary",
];
const rows = deduped.map((row) => [
  clean(row.company_name),
  clean(row.job_title),
  clean(row.role_family),
  clean(row.seniority),
  clean(row.location),
  clean(row.posted_at),
  clean(row.source),
  clean(row.confidence),
  row.verification_level === "specific_listing" ? "Specific listing URL" : "Indexed careers/results page",
  officialKeys.has(keyFor(row)) ? "Yes" : "No",
  clean(row.job_url),
  clean(row.evidence_summary),
]);
const highRows = rows.filter((row) => row[7] === "high");
const mediumRows = rows.filter((row) => row[7] === "medium");
const companiesWithRoles = new Set(deduped.map((row) => identityFor(row))).size;

const manualHeaders = ["Company", "Rationale", "Review candidates"];
const manualRows = completeness.records
  .filter((row) => row.status === "manual_review")
  .map((row) => [
    clean(row.company_name),
    clean(row.notes),
    (row.manual_review_candidates ?? [])
      .map((item) => `${clean(item.job_title)} — ${clean(item.job_url)}`)
      .join("; "),
  ])
  .sort((a, b) => a[0].localeCompare(b[0], "en"));

const workbook = Workbook.create();
const summary = workbook.worksheets.add("Summary");
const all = workbook.worksheets.add("All Accepted");
const high = workbook.worksheets.add("High Confidence");
const medium = workbook.worksheets.add("Medium Confidence");
const review = workbook.worksheets.add("Manual Review");

summary.getRange("A1:C1").values = [["Aggregator hiring outcome", "Count", "Meaning"]];
summary.getRange("A2:A8").values = [
  ["Deduplicated accepted roles"],
  ["Specific-listing / high confidence"],
  ["Indexed-page / medium confidence"],
  ["Companies with accepted roles"],
  ["Exact overlaps with official run"],
  ["New versus official run"],
  ["Manual-review companies"],
];
summary.getRange("B2:B8").values = [
  [rows.length],
  [highRows.length],
  [mediumRows.length],
  [companiesWithRoles],
  [rows.filter((row) => row[9] === "Yes").length],
  [rows.filter((row) => row[9] === "No").length],
  [manualRows.length],
];
summary.getRange("C2:C8").values = [
  ["One row per company/domain and normalized title"],
  ["Direct job-detail or ATS listing URL"],
  ["Current indexed careers or results page; review before outreach"],
  ["Unique company/domain identities"],
  ["Same normalized company/domain and title as official-careers evidence"],
  ["Not present in the seven-role official-careers result"],
  ["Promising but not accepted automatically"],
];

const writeSheet = (sheet, sheetRows, tableName) => {
  const matrix = [headers, ...sheetRows];
  sheet.getRangeByIndexes(0, 0, matrix.length, headers.length).values = matrix;
  sheet.getRange(`A1:L1`).format = {
    fill: "#17365D", font: { bold: true, color: "#FFFFFF" }, wrapText: true,
  };
  sheet.getRange(`A1:L${matrix.length}`).format.wrapText = true;
  const widths = [25, 38, 22, 20, 28, 16, 20, 14, 28, 22, 62, 80];
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, matrix.length, 1).format.columnWidth = width;
  });
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
  sheet.tables.add(`A1:L${matrix.length}`, true, tableName);
};
writeSheet(all, rows, "AllAggregatorRoles");
writeSheet(high, highRows, "HighConfidenceRoles");
writeSheet(medium, mediumRows, "MediumConfidenceRoles");

const reviewMatrix = [manualHeaders, ...manualRows];
review.getRangeByIndexes(0, 0, reviewMatrix.length, 3).values = reviewMatrix;
review.getRange("A1:C1").format = {
  fill: "#7F6000", font: { bold: true, color: "#FFFFFF" }, wrapText: true,
};
review.getRange(`A1:C${reviewMatrix.length}`).format.wrapText = true;
review.getRange(`A1:A${reviewMatrix.length}`).format.columnWidth = 28;
review.getRange(`B1:B${reviewMatrix.length}`).format.columnWidth = 85;
review.getRange(`C1:C${reviewMatrix.length}`).format.columnWidth = 85;
review.freezePanes.freezeRows(1);
review.showGridLines = false;
review.tables.add(`A1:C${reviewMatrix.length}`, true, "ManualReviewCandidates");

summary.getRange("A1:C1").format = {
  fill: "#17365D", font: { bold: true, color: "#FFFFFF" },
};
summary.getRange("A1:A8").format.columnWidth = 35;
summary.getRange("B1:B8").format.columnWidth = 14;
summary.getRange("C1:C8").format.columnWidth = 68;
summary.showGridLines = false;

const inspection = await workbook.inspect({
  kind: "table",
  range: "Summary!A1:C8",
  include: "values,formulas",
  tableMaxRows: 8,
  tableMaxCols: 3,
  maxChars: 5000,
});
console.log(inspection.ndjson);
const errorScan = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "final formula error scan",
});
console.log(errorScan.ndjson);

for (const [sheetName, range] of [
  ["Summary", "A1:C8"],
  ["All Accepted", "A1:L12"],
  ["High Confidence", "A1:L12"],
  ["Medium Confidence", "A1:L12"],
  ["Manual Review", "A1:C12"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(
    path.join(runDir, `${sheetName.toLowerCase().replaceAll(" ", "_")}_preview.png`),
    new Uint8Array(await preview.arrayBuffer()),
  );
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(workbookPath);

const csvEscape = (value) => {
  const text = clean(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};
await fs.writeFile(
  csvPath,
  "\uFEFF" + [headers, ...rows].map((row) => row.map(csvEscape).join(",")).join("\r\n") + "\r\n",
  "utf8",
);

console.log(JSON.stringify({
  workbookPath,
  csvPath,
  raw_roles: aggregator.records.length,
  deduplicated_roles: rows.length,
  high_confidence: highRows.length,
  medium_confidence: mediumRows.length,
  companies_with_roles: companiesWithRoles,
  manual_review_companies: manualRows.length,
}, null, 2));
