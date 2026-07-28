import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const workspace = "C:/Users/Admin/Documents/BBT_bizdev";
const runDir = path.join(workspace, "outputs/canada_website_luna_2026-07-28_all_sources_v3");
const canonicalPath = path.join(runDir, "canonical_companies_luna_websites_enriched.json");
const evidencePath = path.join(runDir, "luna_website_resolution_evidence.json");
const provenancePath = path.join(
  workspace,
  "outputs/canada_company_identity_2026-07-27/source_provenance.json",
);
const workbookPath = path.join(runDir, "canada_website_search_results_2026-07-28.xlsx");
const unresolvedCsvPath = path.join(runDir, "canada_active_companies_unresolved_websites_2026-07-28.csv");

const canonical = JSON.parse(await fs.readFile(canonicalPath, "utf8"));
const evidence = JSON.parse(await fs.readFile(evidencePath, "utf8"));
const provenance = JSON.parse(await fs.readFile(provenancePath, "utf8"));
const companiesById = new Map(canonical.companies.map((row) => [row.company_id, row]));
const provenanceById = new Map();
for (const row of provenance.records ?? []) {
  if (!provenanceById.has(row.company_id)) provenanceById.set(row.company_id, []);
  provenanceById.get(row.company_id).push(row);
}

const clean = (value) => String(value ?? "").replace(/\s+/g, " ").trim();
const category = (row) => {
  if (row.status === "manual_review" && row.notes === "Luna-resolved domain already belongs to another canonical identity") {
    return "duplicate_identity";
  }
  return row.status;
};
const contextFor = (company, sourceRows) => {
  const productCategory = clean(company?.product_category);
  const summary = clean(company?.product_summary)
    || clean(sourceRows.map((row) => row.description).find(Boolean));
  return [productCategory && productCategory !== "unknown" ? productCategory : "", summary]
    .filter(Boolean)
    .join(" — ");
};

const headers = [
  "Company", "Source(s)", "Candidate / resolved website", "Status",
  "Product / context", "Decision notes", "Evidence URLs",
];
const resultRows = evidence.records
  .map((row) => {
    const company = companiesById.get(row.company_id) ?? {};
    const sourceRows = provenanceById.get(row.company_id) ?? [];
    const sources = [...new Set(sourceRows.map((item) => clean(item.source_name)).filter(Boolean))];
    const evidenceUrls = [...new Set((row.citations ?? []).map((item) => clean(item.url)).filter(Boolean))];
    return [
      clean(row.company_name),
      sources.join("; "),
      clean(row.website),
      category(row),
      contextFor(company, sourceRows),
      clean(row.notes),
      evidenceUrls.slice(0, 4).join("; "),
    ];
  })
  .sort((a, b) => a[0].localeCompare(b[0], "en"));

const activeUnresolved = resultRows.filter((row) => ["manual_review", "not_found"].includes(row[3]));
if (resultRows.length !== 443 || activeUnresolved.length !== 204) {
  throw new Error(`Unexpected row counts: all=${resultRows.length}, active_unresolved=${activeUnresolved.length}`);
}

const workbook = Workbook.create();
const summary = workbook.worksheets.add("Summary");
const allResults = workbook.worksheets.add("All Results");
const unresolved = workbook.worksheets.add("Active Unresolved");

summary.getRange("A1:C1").values = [["Website search outcome", "Count", "Meaning"]];
summary.getRange("A2:A6").values = [
  ["resolved"], ["inactive"], ["duplicate_identity"], ["manual_review"], ["not_found"],
];
summary.getRange("B2").formulas = [["=COUNTIF('All Results'!$D$2:$D$444,A2)"]];
summary.getRange("B2:B6").fillDown();
summary.getRange("C2:C6").values = [
  ["Official website accepted"],
  ["Dissolved, acquired, merged, or shut down"],
  ["Likely duplicate canonical record; domain already assigned"],
  ["Plausible lead requiring review"],
  ["No reliable website match"],
];
summary.getRange("A8:B10").values = [
  ["Metric", "Value"],
  ["Companies searched", 443],
  ["Active unresolved", 204],
];

allResults.getRangeByIndexes(0, 0, resultRows.length + 1, headers.length).values = [headers, ...resultRows];
unresolved.getRangeByIndexes(0, 0, activeUnresolved.length + 1, headers.length).values = [headers, ...activeUnresolved];

for (const sheet of [summary, allResults, unresolved]) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
}
for (const sheet of [allResults, unresolved]) {
  const rowCount = sheet === allResults ? resultRows.length + 1 : activeUnresolved.length + 1;
  sheet.getRange(`A1:G1`).format = {
    fill: "#17365D",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  sheet.getRange(`A1:G${rowCount}`).format.wrapText = true;
  sheet.getRange(`A1:A${rowCount}`).format.columnWidth = 27;
  sheet.getRange(`B1:B${rowCount}`).format.columnWidth = 34;
  sheet.getRange(`C1:C${rowCount}`).format.columnWidth = 34;
  sheet.getRange(`D1:D${rowCount}`).format.columnWidth = 19;
  sheet.getRange(`E1:E${rowCount}`).format.columnWidth = 70;
  sheet.getRange(`F1:F${rowCount}`).format.columnWidth = 75;
  sheet.getRange(`G1:G${rowCount}`).format.columnWidth = 60;
  sheet.tables.add(`A1:G${rowCount}`, true, sheet === allResults ? "AllWebsiteResults" : "ActiveUnresolvedWebsites");
}
summary.getRange("A1:C1").format = { fill: "#17365D", font: { bold: true, color: "#FFFFFF" } };
summary.getRange("A8:B8").format = { fill: "#D9EAF7", font: { bold: true, color: "#17365D" } };
summary.getRange("A1:A10").format.columnWidth = 26;
summary.getRange("B1:B10").format.columnWidth = 14;
summary.getRange("C1:C10").format.columnWidth = 55;

const inspection = await workbook.inspect({
  kind: "table",
  range: "Summary!A1:C10",
  include: "values,formulas",
  tableMaxRows: 10,
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
  ["Summary", "A1:C10"],
  ["All Results", "A1:G12"],
  ["Active Unresolved", "A1:G12"],
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
const csvText = [headers, ...activeUnresolved]
  .map((row) => row.map(csvEscape).join(","))
  .join("\r\n") + "\r\n";
await fs.writeFile(unresolvedCsvPath, "\uFEFF" + csvText, "utf8");

console.log(JSON.stringify({
  workbookPath,
  unresolvedCsvPath,
  all_results: resultRows.length,
  active_unresolved: activeUnresolved.length,
}, null, 2));
