import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = "C:/Users/Admin/Documents/BBT_bizdev";
const source = `${root}/outputs/linkedin_enrichment_full/BlueBridge_TOFU_BizDev_V1_LinkedIn.xlsx`;
const fullPath = `${root}/outputs/linkedin_enrichment_full/full_enrichment.json`;
const approvedPath = `${root}/outputs/linkedin_enrichment_full/official_pilot_enrichment.json`;
const outputDir = `${root}/outputs/linkedin_enrichment_priority_retry`;
const outputPath = `${outputDir}/BlueBridge_TOFU_BizDev_V1_LinkedIn_Priority_Retry.xlsx`;

const full = JSON.parse(await fs.readFile(fullPath, "utf8"));
const approved = JSON.parse(await fs.readFile(approvedPath, "utf8"));
const approvedCompanies = new Set(approved.map((row) => row.company));
const results = full.filter((row) => approvedCompanies.has(row.company));
if (approved.length !== 23 || results.length !== 23) {
  throw new Error(`Expected 23 approved priority rows; approved=${approved.length}, results=${results.length}`);
}

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const sheet = workbook.worksheets.getItem("Lead Filtering");
const used = sheet.getUsedRange();
const values = used.values;
const headers = values[0];
const col = Object.fromEntries(headers.map((value, index) => [String(value ?? ""), index]));

const fields = [
  ["executive", "Executive contact name", "Executive contact title", "Executive LinkedIn URL"],
  ["technical", "Technical/R&D contact name", "Technical/R&D contact title", "Technical/R&D LinkedIn URL"],
  ["quality", "Quality/QA contact name", "Quality/QA contact title", "Quality/QA LinkedIn URL"],
];
const urlFormula = (url) => url ? `=HYPERLINK("${url.replaceAll('"', '""')}","${url.replaceAll('"', '""')}")` : "";

for (const result of results) {
  const rowIndex = result.row - 1;
  sheet.getCell(rowIndex, col["LinkedIn company URL"]).formulas = [[urlFormula(result.company_url)]];
  sheet.getCell(rowIndex, col["LinkedIn company status"]).values = [[result.company_status]];
  for (const [key, nameHeader, titleHeader, urlHeader] of fields) {
    const contact = result[key];
    sheet.getCell(rowIndex, col[nameHeader]).values = [[contact?.name ?? ""]];
    sheet.getCell(rowIndex, col[titleHeader]).values = [[contact?.title ?? ""]];
    sheet.getCell(rowIndex, col[urlHeader]).formulas = [[urlFormula(contact?.url ?? "")]];
  }
  sheet.getCell(rowIndex, col["LinkedIn contact status"]).values = [[result.contact_status]];
}

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
  maxChars: 3000,
});
console.log(errors.ndjson);

const startCol = col["LinkedIn company URL"];
const endCol = col["LinkedIn contact status"];
const previewRange = sheet.getRangeByIndexes(0, startCol, Math.min(values.length, 45), endCol - startCol + 1);
const preview = await workbook.render({ sheetName: "Lead Filtering", range: previewRange.address, scale: 1, format: "png" });
await fs.writeFile(`${outputDir}/priority_retry_preview.png`, new Uint8Array(await preview.arrayBuffer()));

await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const counts = {
  rows: results.length,
  companyUrls: results.filter((row) => row.company_url).length,
  complete: results.filter((row) => row.contact_status.startsWith("Complete")).length,
  partial: results.filter((row) => row.contact_status.startsWith("Partial")).length,
};
console.log(JSON.stringify({ outputPath, counts }));
