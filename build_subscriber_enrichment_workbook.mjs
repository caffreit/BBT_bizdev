import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [inputJson, outputXlsx, previewDir] = process.argv.slice(2);
if (!inputJson || !outputXlsx || !previewDir) {
  throw new Error("Usage: node build_subscriber_enrichment_workbook.mjs input.json output.xlsx preview_dir");
}

const data = JSON.parse(await fs.readFile(inputJson, "utf8"));
const workbook = Workbook.create();
const navy = "#16324F";
const blue = "#1F6E8C";
const teal = "#2A9D8F";
const pale = "#EAF3F7";
const amber = "#F4A261";
const red = "#E76F51";
const green = "#DDEFE8";
const grey = "#F3F4F6";

function colName(index) {
  let result = "";
  for (let value = index + 1; value; value = Math.floor((value - 1) / 26)) {
    result = String.fromCharCode(65 + ((value - 1) % 26)) + result;
  }
  return result;
}

function matrix(headers, rows) {
  return [headers, ...rows.map((row) => headers.map((header) => row[header] ?? ""))];
}

function setWidths(sheet, headers, maxRows = 120) {
  headers.forEach((header, index) => {
    const sample = sheet.getRangeByIndexes(0, index, Math.min(maxRows, sheet.getUsedRange().rowCount), 1).values.flat();
    const maxLen = Math.max(header.length, ...sample.map((v) => String(v ?? "").length));
    let width = Math.min(34, Math.max(10, maxLen + 2));
    if (/evidence|angle|reason|source|service|segment|message/i.test(header)) width = 32;
    if (/id$|email|domain|website/i.test(header)) width = Math.min(28, Math.max(width, 18));
    sheet.getRange(`${colName(index)}:${colName(index)}`).format.columnWidth = width;
  });
}

function addTableSheet(name, headers, rows, tableName, options = {}) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  const values = matrix(headers, rows);
  const endCol = colName(headers.length - 1);
  const endRow = values.length;
  sheet.getRange(`A1:${endCol}${endRow}`).values = values;
  const header = sheet.getRange(`A1:${endCol}1`);
  header.format = { fill: navy, font: { bold: true, color: "#FFFFFF" }, wrapText: true, verticalAlignment: "center" };
  header.format.rowHeight = 30;
  if (endRow > 1) {
    const body = sheet.getRange(`A2:${endCol}${endRow}`);
    body.format = { font: { color: "#243444" }, verticalAlignment: "top" };
    const table = sheet.tables.add(`A1:${endCol}${endRow}`, true, tableName);
    table.style = "TableStyleMedium2";
    table.showBandedRows = true;
    table.showFilterButton = true;
  }
  sheet.freezePanes.freezeRows(1);
  if (options.freezeColumns) sheet.freezePanes.freezeColumns(options.freezeColumns);
  setWidths(sheet, headers);
  return sheet;
}

const rawHeaders = ["Record ID", "First Name", "Last Name", "Email", "Phone", "Form Message", "Job Title", "Company", "Lead Source", "Normalized Email", "Email Domain", "Email Valid", "Duplicate Email", "Original Company Missing"];
const companyHeaders = ["Company ID", "Canonical Company", "Domain", "Website", "Website Status", "Redirect Target", "Company Resolution", "Resolution Confidence", "Contact Count", "Missing Company Count", "Company Conflict", "Company Type", "Employee Band", "Maturity Stage", "Product Profile", "Regulatory Signals", "Recommended Services", "Classification Confidence", "Evidence Summary", "Evidence URLs Used", "Homepage URL", "Internal Page URLs", "News Article URLs", "All Source URLs", "Research Date", "Method", "LLM Used", "Model", "Reasoning Effort", "Prompt Tokens", "Completion Tokens", "Estimated Cost USD", "Errors", "LLM Error", "Runtime Seconds"];
const companyRows = data.companies.map((row) => ({
  "Company ID": row.company_id, "Canonical Company": row.canonical_company, "Domain": row.domain, "Website": row.website,
  "Website Status": row.website_status, "Redirect Target": row.redirect_target,
  "Company Resolution": row.company_resolution, "Resolution Confidence": row.resolution_confidence, "Contact Count": row.contact_count,
  "Missing Company Count": row.missing_company_count, "Company Conflict": row.company_conflict, "Company Type": row.company_type,
  "Employee Band": row.employee_band, "Maturity Stage": row.maturity_stage, "Product Profile": row.product_profile,
  "Regulatory Signals": row.regulatory_signals, "Recommended Services": row.services, "Classification Confidence": row.confidence,
  "Evidence Summary": row.evidence_summary, "Evidence URLs Used": row.evidence_urls, "Homepage URL": row.homepage_url, "Internal Page URLs": row.internal_page_urls,
  "News Article URLs": row.news_article_urls, "All Source URLs": row.source_urls, "Research Date": row.research_date, "Method": row.method,
  "LLM Used": row.llm_used, "Model": row.model, "Reasoning Effort": row.reasoning_effort, "Prompt Tokens": row.prompt_tokens, "Completion Tokens": row.completion_tokens,
  "Estimated Cost USD": row.estimated_cost_usd, "Errors": row.errors, "LLM Error": row.llm_error, "Runtime Seconds": row.runtime_seconds,
}));

const contactHeaders = ["Record ID", "Company ID", "First Name", "Last Name", "Email", "Email Domain", "Original Company", "Resolved Company", "Job Title", "Contact Function", "Seniority", "Buying Role", "Primary Service Relevance", "Outreach Angle", "Campaign Segment", "Duplicate Email"];
const reviewHeaders = ["Company ID", "Company", "Domain", "Review Status", "Priority", "Review Reasons", "Reviewer Notes", "Source URLs"];

const raw = addTableSheet("Raw Contacts", rawHeaders, data.raw_contacts, "RawContactsTable", { freezeColumns: 1 });
const companies = addTableSheet("Companies", companyHeaders, companyRows, "CompaniesTable", { freezeColumns: 2 });
const contacts = addTableSheet("Contacts", contactHeaders, data.contacts, "ContactsTable", { freezeColumns: 2 });
const review = addTableSheet("Review Queue", reviewHeaders, data.review_queue, "ReviewQueueTable", { freezeColumns: 2 });

raw.getRange(`L2:N${data.raw_contacts.length + 1}`).conditionalFormats.add("containsText", { text: "Yes", format: { fill: "#FCE8E6", font: { color: "#9C2B1B" } } });
companies.getRange(`H2:H${companyRows.length + 1}`).format.numberFormat = "0%";
companies.getRange(`R2:R${companyRows.length + 1}`).format.numberFormat = "0%";
companies.getRange(`AF2:AF${companyRows.length + 1}`).format.numberFormat = "$0.000000";
companies.getRange(`Y2:Y${companyRows.length + 1}`).format.numberFormat = "yyyy-mm-dd";
companies.getRange(`H2:H${companyRows.length + 1}`).conditionalFormats.add("colorScale", { colors: [red, amber, teal], thresholds: ["min", "50%", "max"] });
companies.getRange(`R2:R${companyRows.length + 1}`).conditionalFormats.add("colorScale", { colors: [red, amber, teal], thresholds: ["min", "50%", "max"] });
companies.getRange(`L2:O${companyRows.length + 1}`).conditionalFormats.add("containsText", { text: "Unknown", format: { fill: "#FFF2CC", font: { color: "#7F6000" } } });
companies.getRange(`E2:E${companyRows.length + 1}`).conditionalFormats.add("containsText", { text: "Available", format: { fill: green, font: { color: "#176B4D" } } });
companies.getRange(`E2:E${companyRows.length + 1}`).conditionalFormats.add("containsText", { text: "Unavailable", format: { fill: "#FCE8E6", font: { color: "#9C2B1B" } } });
companies.getRange(`E2:E${companyRows.length + 1}`).conditionalFormats.add("containsText", { text: "External redirect", format: { fill: "#FFF2CC", font: { color: "#7F6000" } } });
review.getRange(`D2:D${data.review_queue.length + 1}`).dataValidation = { rule: { type: "list", values: ["Pending manual validation", "Validated", "Corrected", "Rejected"] } };
review.getRange(`E2:E${data.review_queue.length + 1}`).dataValidation = { rule: { type: "list", values: ["High", "Medium", "Low"] } };
review.getRange(`D2:D${data.review_queue.length + 1}`).conditionalFormats.add("containsText", { text: "Pending", format: { fill: "#FFF2CC", font: { color: "#7F6000" } } });
review.getRange(`E2:E${data.review_queue.length + 1}`).conditionalFormats.add("containsText", { text: "High", format: { fill: "#FCE8E6", font: { color: "#9C2B1B", bold: true } } });

const summary = workbook.worksheets.add("Taxonomy & Run Summary");
summary.showGridLines = false;
summary.getRange("A1:H1").merge();
summary.getRange("A1").values = [["Bluebridge Subscriber Enrichment Pilot"]];
summary.getRange("A1:H1").format = { fill: navy, font: { bold: true, color: "#FFFFFF", size: 18 }, verticalAlignment: "center" };
summary.getRange("A1:H1").format.rowHeight = 38;
summary.getRange("A3:D3").values = [["Metric", "Value", "Metric", "Value"]];
summary.getRange("A3:D3").format = { fill: blue, font: { bold: true, color: "#FFFFFF" } };
summary.getRange("A4:A10").values = [["Source contacts"], ["Unique email domains"], ["Pilot companies"], ["Pilot contacts"], ["Missing-company rows"], ["Same-domain recoverable"], ["Invalid email rows"]];
summary.getRange("C4:C10").values = [["Unknown product profile"], ["Unknown employee band"], ["Unknown company type"], ["Unknown maturity"], ["Website failures"], ["Manual reviews pending"], ["Estimated model cost (USD)"]];
const rawEnd = data.raw_contacts.length + 1;
const companyEnd = companyRows.length + 1;
const contactEnd = data.contacts.length + 1;
const reviewEnd = data.review_queue.length + 1;
summary.getRange("B4:B10").formulas = [
  [`=COUNTA('Raw Contacts'!$A$2:$A$${rawEnd})`],
  [`=${data.stats.unique_domains}`],
  [`=COUNTA('Companies'!$A$2:$A$${companyEnd})`],
  [`=COUNTA('Contacts'!$A$2:$A$${contactEnd})`],
  [`=COUNTIF('Raw Contacts'!$N$2:$N$${rawEnd},"Yes")`],
  [`=${data.stats.same_domain_recoverable_rows}`],
  [`=COUNTIF('Raw Contacts'!$L$2:$L$${rawEnd},"No")`],
];
summary.getRange("D4:D10").formulas = [
  [`=COUNTIF('Companies'!$O$2:$O$${companyEnd},"Unknown")`],
  [`=COUNTIF('Companies'!$M$2:$M$${companyEnd},"Unknown")`],
  [`=COUNTIF('Companies'!$L$2:$L$${companyEnd},"Unknown")`],
  [`=COUNTIF('Companies'!$N$2:$N$${companyEnd},"Unknown")`],
  [`=COUNTIF('Companies'!$E$2:$E$${companyEnd},"Unavailable")`],
  [`=COUNTIF('Review Queue'!$D$2:$D$${reviewEnd},"Pending manual validation")`],
  [`=SUM('Companies'!$AF$2:$AF$${companyEnd})`],
];
summary.getRange("B4:D10").format = { fill: pale, borders: { preset: "inside", style: "thin", color: "#D9E2E8" } };
summary.getRange("B4:B10").format.numberFormat = "#,##0";
summary.getRange("D4:D9").format.numberFormat = "#,##0";
summary.getRange("D10").format.numberFormat = "$0.000000";
summary.getRange("A12:H12").merge();
summary.getRange("A12").values = [[`Run date: ${data.stats.run_date} | Model: ${data.stats.model} | Reasoning: ${data.stats.reasoning_effort ?? "Not configured"} | Precision-first policy: unsupported classifications remain Unknown.`]];
summary.getRange("A12:H12").format = { fill: grey, font: { italic: true, color: "#435466" }, wrapText: true };

const taxonomy = [
  ["Company type", "Startup; University spinout; Scaleup; Mid-market; Enterprise; Academic/non-commercial; Other; Unknown", "Organisation form and scale category"],
  ["Employee band", "1–10; 11–50; 51–200; 201–1,000; 1,001–5,000; 5,001+; Unknown", "Only populated when supported by sourced evidence"],
  ["Product profile", "Physical medical device; Connected device; SaMD/digital health; Diagnostic/IVD; AI-enabled health; Biotech/pharma; Non-regulated/wellness; Other; Unknown", "Primary product modality"],
  ["Maturity stage", "Research/spinout; Prototype/preclinical; Clinical/validation; Regulatory; Commercial; Scaling; Unknown", "Most advanced stage supported by evidence"],
  ["Service fit", "Product engineering; Software development; V&V; QA/QMS; Regulatory support; IEC 62304; ISO 13485; Cybersecurity; AI implementation", "Multi-select Bluebridge relevance"],
  ["Contact function", "Founder/executive; R&D/engineering/product; QA/regulatory; Clinical/medical; Operations/manufacturing; Commercial; HR; Academic; Other", "Derived primarily from job title"],
];
summary.getRange("A14:C14").values = [["Field", "Controlled values", "Definition"]];
summary.getRange("A14:C14").format = { fill: teal, font: { bold: true, color: "#FFFFFF" } };
summary.getRange(`A15:C${14 + taxonomy.length}`).values = taxonomy;
summary.getRange(`A15:C${14 + taxonomy.length}`).format = { wrapText: true, verticalAlignment: "top", borders: { preset: "inside", style: "thin", color: "#D9E2E8" } };
summary.getRange("A23:C23").values = [["Colour", "Meaning", "Action"]];
summary.getRange("A23:C23").format = { fill: blue, font: { bold: true, color: "#FFFFFF" } };
summary.getRange("A24:C26").values = [["Red", "Identity conflict or high-priority review", "Resolve before campaign use"], ["Amber", "Unknown or pending validation", "Check sources and confirm"], ["Green", "Higher evidence confidence", "Still requires pilot validation"]];
summary.getRange("A24").format.fill = "#FCE8E6";
summary.getRange("A25").format.fill = "#FFF2CC";
summary.getRange("A26").format.fill = green;
summary.getRange("A28:C28").values = [["Source selection", "Implemented rule", "Purpose"]];
summary.getRange("A28:C28").format = { fill: teal, font: { bold: true, color: "#FFFFFF" } };
summary.getRange("A29:C32").values = [
  ["Homepage", "Resolved email-domain homepage after redirects", "Canonical first-party evidence"],
  ["Internal pages", "Up to three scored same-site pages: regulatory/quality, product/technology, and About/company", "Broader first-party coverage"],
  ["News articles", "Up to five exact-company Google News results scored for regulatory, funding, clinical, launch and product signals", "Current external evidence"],
  ["Confidence", "Capped when the website is unavailable, redirects externally, or fewer than two URLs support the classification", "Avoid unsupported high confidence"],
];
summary.getRange("A29:C32").format = { wrapText: true, verticalAlignment: "top", borders: { preset: "inside", style: "thin", color: "#D9E2E8" } };
summary.getRange("A:C").format.columnWidth = 30;
summary.getRange("B:B").format.columnWidth = 72;
summary.getRange("D:D").format.columnWidth = 16;
summary.freezePanes.freezeRows(1);

await fs.mkdir(path.dirname(outputXlsx), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const inspections = {};
inspections.summary = (await workbook.inspect({ kind: "table", range: "Taxonomy & Run Summary!A1:D32", include: "values,formulas", tableMaxRows: 36, tableMaxCols: 8 })).ndjson;
inspections.companies = (await workbook.inspect({ kind: "table", range: `Companies!A1:P${Math.min(12, companyEnd)}`, include: "values,formulas", tableMaxRows: 12, tableMaxCols: 16 })).ndjson;
const errorChecks = [];
for (const [sheetId, range] of [["Companies", `A1:AI${companyEnd}`], ["Contacts", `A1:P${contactEnd}`], ["Review Queue", `A1:H${reviewEnd}`], ["Taxonomy & Run Summary", "A1:H32"]]) {
  errorChecks.push((await workbook.inspect({ kind: "match", sheetId, range, searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: `formula error scan ${sheetId}` })).ndjson);
}
inspections.errors = errorChecks.join("\n");
await fs.writeFile(path.join(previewDir, "inspection.json"), JSON.stringify(inspections, null, 2));

const previewSpecs = [
  ["Raw Contacts", "A1:N25", 0.75, "Raw_Contacts"],
  ["Companies", "A1:R20", 0.65, "Companies_left"],
  ["Companies", "S1:AI20", 0.65, "Companies_right"],
  ["Contacts", "A1:P25", 0.7, "Contacts"],
  ["Review Queue", "A1:H25", 0.85, "Review_Queue"],
  ["Taxonomy & Run Summary", "A1:H32", 1.0, "Taxonomy_and_Run_Summary"],
];
for (const [sheetName, range, scale, fileName] of previewSpecs) {
  const preview = await workbook.render({ sheetName, range, scale, format: "png" });
  await fs.writeFile(path.join(previewDir, `${fileName}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputXlsx);
console.log(JSON.stringify({ outputXlsx, previewDir, sheets: 5, companies: companyRows.length, contacts: data.contacts.length }));
