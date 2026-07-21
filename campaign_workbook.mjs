import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [mode, inputPath, outputPath, previewDir] = process.argv.slice(2);
if (!mode || !inputPath || !outputPath || !["build", "extract"].includes(mode)) {
  throw new Error("Usage: node campaign_workbook.mjs build result.json review.xlsx [preview_dir] | extract review.xlsx approved.json");
}

if (mode === "extract") {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
  const sheet = workbook.worksheets.getItem("Contact Decisions");
  const values = sheet.getUsedRange(true).values;
  const headers = (values[0] ?? []).map((value) => String(value ?? ""));
  const rows = values.slice(1).filter((row) => row.some((value) => value !== null && value !== "")).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index] ?? ""])));
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.writeFile(outputPath, JSON.stringify(rows, null, 2), "utf8");
  console.log(JSON.stringify({ extractedRows: rows.length, outputPath }));
  process.exit(0);
}

const data = JSON.parse(await fs.readFile(inputPath, "utf8"));
const workbook = Workbook.create();
const navy = "#16324F";
const blue = "#1F6E8C";
const teal = "#2A9D8F";
const pale = "#EAF3F7";
const amber = "#F4A261";
const red = "#E76F51";
const green = "#DDEFE8";
const grey = "#F3F4F6";
const yellow = "#FFF2CC";

function colName(index) {
  let result = "";
  for (let value = index + 1; value; value = Math.floor((value - 1) / 26)) {
    result = String.fromCharCode(65 + ((value - 1) % 26)) + result;
  }
  return result;
}

function rowsMatrix(headers, rows) {
  return [headers, ...rows.map((row) => headers.map((header) => row[header] ?? ""))];
}

function setWidths(sheet, headers) {
  headers.forEach((header, index) => {
    let width = 14;
    if (/name|company|title|function|role/i.test(header)) width = 22;
    if (/email|domain|url/i.test(header)) width = 28;
    if (/criteria|reason|summary|angle/i.test(header)) width = 34;
    if (/score|rank|confidence|decision|status|selection/i.test(header)) width = 15;
    sheet.getRange(`${colName(index)}:${colName(index)}`).format.columnWidth = width;
  });
}

function addTableSheet(name, headers, rows, tableName, freezeColumns = 1) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  const values = rowsMatrix(headers, rows);
  const endCol = colName(headers.length - 1);
  const endRow = values.length;
  sheet.getRange(`A1:${endCol}${endRow}`).values = values;
  sheet.getRange(`A1:${endCol}1`).format = {
    fill: navy,
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    verticalAlignment: "center",
    rowHeight: 32,
  };
  if (endRow > 1) {
    sheet.getRange(`A2:${endCol}${endRow}`).format = { font: { color: "#243444" }, verticalAlignment: "top", wrapText: false, rowHeight: 22 };
    const table = sheet.tables.add(`A1:${endCol}${endRow}`, true, tableName);
    table.style = "TableStyleMedium2";
    table.showBandedRows = true;
    table.showFilterButton = true;
  }
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(freezeColumns);
  setWidths(sheet, headers);
  return sheet;
}

function flattenTarget(dimension) {
  return `Required: ${(dimension.required ?? []).join("; ") || "None"} | Preferred: ${(dimension.preferred ?? []).join("; ") || "None"} | Excluded: ${(dimension.excluded ?? []).join("; ") || "None"}`;
}

const profile = data.profile;
const target = profile.contact_targets;
const briefRows = [
  ["Campaign name", profile.campaign_name, "LLM-extracted; editable profile JSON is the approved source"],
  ["Subject", profile.subject, "From the campaign draft"],
  ["Theme", profile.theme, "Campaign topic summary"],
  ["Primary Bluebridge service", profile.primary_service, "Controlled service taxonomy"],
  ["Company types", flattenTarget(profile.company_targets.company_types), "Required/preferred/excluded"],
  ["Employee bands", flattenTarget(profile.company_targets.employee_bands), "Required/preferred/excluded"],
  ["Maturity stages", flattenTarget(profile.company_targets.maturity_stages), "Required/preferred/excluded"],
  ["Product profiles", flattenTarget(profile.company_targets.product_profiles), "Required/preferred/excluded"],
  ["Services", flattenTarget(profile.company_targets.services), "Required/preferred/excluded"],
  ["Regulatory signals", flattenTarget(profile.company_targets.regulatory_signals), "Required/preferred/excluded"],
  ["Primary contact functions", target.primary_functions.join("; "), "40 contact-score points"],
  ["Secondary contact functions", target.secondary_functions.join("; "), "28 contact-score points"],
  ["Excluded contact functions", target.excluded_functions.join("; "), "Hard contact exclusion"],
  ["Preferred seniorities", target.preferred_seniorities.join("; "), "25 contact-score points"],
  ["Preferred buying roles", target.preferred_buying_roles.join("; "), "15 contact-score points"],
  ["Title keywords", target.title_keywords.join("; "), "15 contact-score points"],
  ["Business-unit keywords", target.business_unit_keywords.join("; "), target.require_business_unit_match ? "Required" : "Enterprise warning only"],
  ["Company threshold", profile.company_score_threshold, "Balanced default: 60"],
  ["Contact threshold", profile.contact_score_threshold, "Balanced default: 65"],
  ["Minimum classification confidence", profile.minimum_classification_confidence, "Below this is review-only"],
  ["Profile confidence", profile.confidence, "Below 0.60 fails profile creation"],
  ["Rationale", profile.rationale, "Why the targeting profile fits the draft"],
  ["Draft hash", profile.metadata?.draft_sha256 ?? "", "Confirms which draft was classified"],
  ["Model", profile.metadata?.model ?? "Manual profile", `Reasoning: ${profile.metadata?.reasoning_effort ?? "Not recorded"}`],
];

const brief = workbook.worksheets.add("Campaign Brief");
brief.showGridLines = false;
brief.getRange("A1:C1").merge();
brief.getRange("A1").values = [["Bluebridge Campaign Targeting Brief"]];
brief.getRange("A1:C1").format = { fill: navy, font: { bold: true, color: "#FFFFFF", size: 18 }, verticalAlignment: "center", rowHeight: 38 };
brief.getRange("A3:C3").values = [["Field", "Value", "Interpretation"]];
brief.getRange("A3:C3").format = { fill: teal, font: { bold: true, color: "#FFFFFF" } };
brief.getRange(`A4:C${briefRows.length + 3}`).values = briefRows;
brief.getRange(`A4:C${briefRows.length + 3}`).format = { wrapText: true, verticalAlignment: "top", borders: { preset: "inside", style: "thin", color: "#D9E2E8" } };
brief.getRange(`A4:A${briefRows.length + 3}`).format.font = { bold: true, color: navy };
brief.getRange(`B4:B${briefRows.length + 3}`).format.fill = pale;
brief.getRange("A:A").format.columnWidth = 29;
brief.getRange("B:B").format.columnWidth = 76;
brief.getRange("C:C").format.columnWidth = 37;
brief.getRange("B23:B24").format.numberFormat = "0%";
brief.freezePanes.freezeRows(3);

const companyHeaders = ["Company ID", "Company", "Domain", "Company Type", "Employee Band", "Maturity Stage", "Product Profile", "Recommended Services", "Regulatory Signals", "Classification Confidence", "Company Score", "Decision", "Matched Criteria", "Exclusion Reasons", "Review Reasons", "Evidence Summary", "Evidence URLs", "Research Date"];
const contactHeaders = ["Campaign", "Record ID", "Company ID", "Company", "First Name", "Last Name", "Email", "Job Title", "Contact Function", "Seniority", "Buying Role", "Contact Score", "Decision", "Matched Criteria", "Exclusion Reasons", "Review Reasons", "Warnings", "Company Score", "Company Decision", "Contact Rank", "Selection", "Approval Status", "Suppression Status", "Personalisation Angle", "Personalisation Evidence URL"];
const contactRows = data.contact_decisions.map((row) => ({ "Campaign": profile.campaign_name, ...row }));
const reviewHeaders = ["Level", "ID", "Company", "Contact", "Decision", "Reasons", "Evidence URLs"];
const companies = addTableSheet("Company Decisions", companyHeaders, data.company_decisions, "CompanyDecisionsTable", 2);
const contacts = addTableSheet("Contact Decisions", contactHeaders, contactRows, "ContactDecisionsTable", 4);
const review = addTableSheet("Review Queue", reviewHeaders, data.review_queue, "CampaignReviewQueueTable", 2);

const companyEnd = data.company_decisions.length + 1;
const contactEnd = contactRows.length + 1;
const reviewEnd = data.review_queue.length + 1;
if (companyEnd > 1) {
  companies.getRange(`J2:J${companyEnd}`).format.numberFormat = "0%";
  companies.getRange(`K2:K${companyEnd}`).format.numberFormat = "0";
  companies.getRange(`J2:K${companyEnd}`).conditionalFormats.add("colorScale", { colors: [red, amber, teal], thresholds: ["min", "50%", "max"] });
  companies.getRange(`L2:L${companyEnd}`).conditionalFormats.add("containsText", { text: "Eligible", format: { fill: green, font: { color: "#176B4D", bold: true } } });
  companies.getRange(`L2:L${companyEnd}`).conditionalFormats.add("containsText", { text: "Review", format: { fill: yellow, font: { color: "#7F6000" } } });
  companies.getRange(`L2:L${companyEnd}`).conditionalFormats.add("containsText", { text: "Excluded", format: { fill: "#FCE8E6", font: { color: "#9C2B1B" } } });
}
if (contactEnd > 1) {
  contacts.getRange(`L2:L${contactEnd}`).format.numberFormat = "0";
  contacts.getRange(`R2:R${contactEnd}`).format.numberFormat = "0";
  contacts.getRange(`V2:V${contactEnd}`).format.fill = yellow;
  contacts.getRange(`V2:V${contactEnd}`).dataValidation = { rule: { type: "list", values: ["Pending", "Approved", "Rejected"] } };
  contacts.getRange(`M2:M${contactEnd}`).conditionalFormats.add("containsText", { text: "Eligible", format: { fill: green, font: { color: "#176B4D", bold: true } } });
  contacts.getRange(`M2:M${contactEnd}`).conditionalFormats.add("containsText", { text: "Review", format: { fill: yellow, font: { color: "#7F6000" } } });
  contacts.getRange(`M2:M${contactEnd}`).conditionalFormats.add("containsText", { text: "Excluded", format: { fill: "#FCE8E6", font: { color: "#9C2B1B" } } });
  contacts.getRange(`U2:U${contactEnd}`).conditionalFormats.add("containsText", { text: "Primary", format: { fill: pale, font: { bold: true, color: navy } } });
  contacts.getRange(`V2:V${contactEnd}`).conditionalFormats.add("containsText", { text: "Approved", format: { fill: green, font: { color: "#176B4D", bold: true } } });
}
if (reviewEnd > 1) {
  review.getRange(`E2:E${reviewEnd}`).conditionalFormats.add("containsText", { text: "Excluded", format: { fill: "#FCE8E6", font: { color: "#9C2B1B" } } });
  review.getRange(`E2:E${reviewEnd}`).conditionalFormats.add("containsText", { text: "Review", format: { fill: yellow, font: { color: "#7F6000" } } });
}

const summary = workbook.worksheets.add("Run Summary");
summary.showGridLines = false;
summary.getRange("A1:G1").merge();
summary.getRange("A1").values = [["Bluebridge Campaign Selection Summary"]];
summary.getRange("A1:G1").format = { fill: navy, font: { bold: true, color: "#FFFFFF", size: 18 }, verticalAlignment: "center", rowHeight: 38 };
summary.getRange("A3:D3").values = [["Metric", "Value", "Metric", "Value"]];
summary.getRange("A3:D3").format = { fill: blue, font: { bold: true, color: "#FFFFFF" } };
summary.getRange("A4:A9").values = [["Source companies"], ["Eligible companies"], ["Source contacts"], ["Eligible contacts"], ["Selected primaries"], ["Selected backups"]];
summary.getRange("C4:C9").values = [["Review queue items"], ["Suppression check"], ["Company threshold"], ["Contact threshold"], ["Approved primaries"], ["Campaign"]];
summary.getRange("B4:B9").formulas = [
  [`=COUNTA('Company Decisions'!$A$2:$A$${companyEnd})`],
  [`=COUNTIF('Company Decisions'!$L$2:$L$${companyEnd},"Eligible")`],
  [`=COUNTA('Contact Decisions'!$B$2:$B$${contactEnd})`],
  [`=COUNTIF('Contact Decisions'!$M$2:$M$${contactEnd},"Eligible")`],
  [`=COUNTIFS('Contact Decisions'!$U$2:$U$${contactEnd},"Primary",'Contact Decisions'!$M$2:$M$${contactEnd},"Eligible")`],
  [`=COUNTIFS('Contact Decisions'!$U$2:$U$${contactEnd},"Backup",'Contact Decisions'!$M$2:$M$${contactEnd},"Eligible")`],
];
summary.getRange("D4:D9").formulas = [
  [`=COUNTA('Review Queue'!$A$2:$A$${reviewEnd})`],
  [`="${data.summary.suppression_checked}"`],
  [`=${profile.company_score_threshold}`],
  [`=${profile.contact_score_threshold}`],
  [`=COUNTIFS('Contact Decisions'!$U$2:$U$${contactEnd},"Primary",'Contact Decisions'!$V$2:$V$${contactEnd},"Approved")`],
  [`="${String(profile.campaign_name).replaceAll('"', '""')}"`],
];
summary.getRange("B4:D9").format = { fill: pale, borders: { preset: "inside", style: "thin", color: "#D9E2E8" } };
summary.getRange("A12:C12").values = [["Company scoring component", "Points", "Rule"]];
summary.getRange("A12:C12").format = { fill: teal, font: { bold: true, color: "#FFFFFF" } };
summary.getRange("A13:C19").values = [
  ["Product profile", 25, "Full points for required/preferred overlap"], ["Recommended service", 20, "Full points for required/preferred overlap"],
  ["Regulatory signal", 15, "Full points for required/preferred overlap"], ["Maturity stage", 15, "Full points for required/preferred overlap"],
  ["Company type", 10, "Full points for required/preferred overlap"], ["Employee band", 10, "Full points for required/preferred overlap"],
  ["Evidence", 5, "Confidence, URL and freshness threshold"],
];
summary.getRange("E12:G12").values = [["Contact scoring component", "Points", "Rule"]];
summary.getRange("E12:G12").format = { fill: teal, font: { bold: true, color: "#FFFFFF" } };
summary.getRange("E13:G17").values = [
  ["Function", 40, "28 points for a secondary function"], ["Seniority", 25, "Preferred or neutral when unrestricted"],
  ["Buying role", 15, "Preferred or neutral when unrestricted"], ["Title keyword", 15, "Match or neutral when unrestricted"],
  ["Data quality", 5, "Valid, unique, non-generic email"],
];
summary.getRange("A21:G21").merge();
summary.getRange("A21").values = [["Approval workflow: review primary rows on Contact Decisions, change Approval Status to Approved, save the workbook, then run campaign_matcher.py export with the suppression file."]];
summary.getRange("A21:G21").format = { fill: yellow, font: { bold: true, color: "#7F6000" }, wrapText: true, rowHeight: 36 };
summary.getRange("A:A").format.columnWidth = 29;
summary.getRange("B:B").format.columnWidth = 15;
summary.getRange("C:C").format.columnWidth = 38;
summary.getRange("D:D").format.columnWidth = 18;
summary.getRange("E:E").format.columnWidth = 29;
summary.getRange("F:F").format.columnWidth = 15;
summary.getRange("G:G").format.columnWidth = 38;
summary.freezePanes.freezeRows(1);

const errorChecks = [];
for (const [sheetId, range] of [
  ["Campaign Brief", `A1:C${briefRows.length + 3}`],
  ["Company Decisions", `A1:R${companyEnd}`],
  ["Contact Decisions", `A1:Y${contactEnd}`],
  ["Review Queue", `A1:G${reviewEnd}`],
  ["Run Summary", "A1:H21"],
]) {
  errorChecks.push((await workbook.inspect({ kind: "match", sheetId, range, searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: `formula error scan ${sheetId}` })).ndjson);
}
const inspections = {
  brief: (await workbook.inspect({ kind: "table", range: `Campaign Brief!A1:C${briefRows.length + 3}`, include: "values,formulas", tableMaxRows: 30, tableMaxCols: 4 })).ndjson,
  summary: (await workbook.inspect({ kind: "table", range: "Run Summary!A1:G21", include: "values,formulas", tableMaxRows: 24, tableMaxCols: 8 })).ndjson,
  errors: errorChecks.join("\n"),
};

await fs.mkdir(path.dirname(outputPath), { recursive: true });
if (previewDir) {
  await fs.mkdir(previewDir, { recursive: true });
  await fs.writeFile(path.join(previewDir, "inspection.json"), JSON.stringify(inspections, null, 2));
  const previews = [
    ["Campaign Brief", `A1:C${briefRows.length + 3}`, 0.9],
    ["Company Decisions", `A1:L${Math.min(companyEnd, 20)}`, 0.7],
    ["Company Decisions", `M1:R${Math.min(companyEnd, 20)}`, 0.7],
    ["Contact Decisions", `A1:M${Math.min(contactEnd, 22)}`, 0.65],
    ["Contact Decisions", `N1:Y${Math.min(contactEnd, 22)}`, 0.65],
    ["Review Queue", `A1:G${Math.min(reviewEnd, 18)}`, 0.7],
    ["Run Summary", "A1:G21", 0.9],
  ];
  for (const [sheetName, range, scale] of previews) {
    const preview = await workbook.render({ sheetName, range, scale, format: "png" });
    const suffix = range.split(":")[0].replace(/[^A-Z]/g, "");
    await fs.writeFile(path.join(previewDir, `${sheetName.replaceAll(" ", "_")}_${suffix}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
}
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, sheets: 5, companies: data.company_decisions.length, contacts: contactRows.length, previewDir: previewDir ?? "" }));
