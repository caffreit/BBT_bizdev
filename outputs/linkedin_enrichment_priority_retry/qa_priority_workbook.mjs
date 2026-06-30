import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const path = "C:/Users/Admin/Documents/BBT_bizdev/outputs/linkedin_enrichment_priority_retry/BlueBridge_TOFU_BizDev_V1_LinkedIn_67_Leads.xlsx";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(path));
const sheet = workbook.worksheets.getItem("Lead Filtering");
const used = sheet.getUsedRange();
const values = used.values;
const headers = values[0];
const companyCol = headers.indexOf("Company");
const companyUrlCol = headers.indexOf("LinkedIn company URL");
const companyStatusCol = headers.indexOf("LinkedIn company status");
const contactStatusCol = headers.indexOf("LinkedIn contact status");
const results = JSON.parse(await fs.readFile("C:/Users/Admin/Documents/BBT_bizdev/outputs/linkedin_enrichment_full/full_enrichment.json", "utf8"));
const resultNames = new Set(results.map((row) => row.company));
const matched = values.slice(1).filter((row) => resultNames.has(String(row[companyCol] ?? "")));
if (matched.length !== 67) throw new Error(`Expected 67 scoped rows, got ${matched.length}`);

const check = {
  rows: matched.length,
  companyUrls: matched.filter((row) => String(row[companyUrlCol] ?? "").trim()).length,
  complete: matched.filter((row) => String(row[contactStatusCol] ?? "").startsWith("Complete")).length,
  partial: matched.filter((row) => String(row[contactStatusCol] ?? "").startsWith("Partial")).length,
  statusesPresent: matched.every((row) => String(row[companyStatusCol] ?? "").trim() && String(row[contactStatusCol] ?? "").trim()),
};
console.log(JSON.stringify(check));

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
  maxChars: 3000,
});
console.log(errors.ndjson);

const preview = await workbook.render({
  sheetName: "Lead Filtering",
  range: "AN405:AX412",
  scale: 1,
  format: "png",
});
await fs.writeFile("C:/Users/Admin/Documents/BBT_bizdev/outputs/linkedin_enrichment_priority_retry/full_67_preview.png", new Uint8Array(await preview.arrayBuffer()));
