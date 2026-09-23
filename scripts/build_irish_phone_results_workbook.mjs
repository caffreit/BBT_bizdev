import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "outputs/irish_phone_extractor_20260915";
const inputPath = `${outputDir}/irish_phone_results.json`;
const outputPath = `${outputDir}/irish_phone_results.xlsx`;
const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const records = [...payload.records].sort((a, b) => {
  const order = { found: 0, site_error: 1, extractor_error: 2, not_found: 3 };
  return (order[a.phone_status] ?? 9) - (order[b.phone_status] ?? 9)
    || a.company_name.localeCompare(b.company_name);
});
const mobileRecords = [...(payload.mobile_records || [])].sort((a, b) =>
  a.company_name.localeCompare(b.company_name) || a.phone_e164.localeCompare(b.phone_e164)
);

const workbook = Workbook.create();
const summary = workbook.worksheets.add("Summary");
const results = workbook.worksheets.add("Results");
const mobiles = workbook.worksheets.add("Mobile numbers");
summary.showGridLines = false;
results.showGridLines = false;
mobiles.showGridLines = false;
summary.tabColor = "#17365D";
results.tabColor = "#5B9BD5";
mobiles.tabColor = "#ED7D31";

const font = "Arial";
const navy = "#17365D";
const blue = "#D9EAF7";
const paleGreen = "#E2F0D9";
const paleAmber = "#FFF2CC";
const paleRed = "#FCE4D6";
const muted = "#666666";

function formatNational(value) {
  const digits = String(value || "").replace(/\D/g, "");
  if (!digits) return "";
  if (digits.startsWith("01") && digits.length === 9) return `${digits.slice(0, 2)} ${digits.slice(2, 5)} ${digits.slice(5)}`;
  if (digits.length === 10) return `${digits.slice(0, 3)} ${digits.slice(3, 6)} ${digits.slice(6)}`;
  if (digits.length === 9) return `${digits.slice(0, 3)} ${digits.slice(3, 6)} ${digits.slice(6)}`;
  return digits;
}

function formatInternational(value) {
  const digits = String(value || "").replace(/\D/g, "").replace(/^353/, "");
  if (!digits) return "";
  if (digits.startsWith("1") && digits.length === 8) return `+353 1 ${digits.slice(1, 4)} ${digits.slice(4)}`;
  if (digits.length === 9) return `+353 ${digits.slice(0, 2)} ${digits.slice(2, 5)} ${digits.slice(5)}`;
  if (digits.length === 8) return `+353 ${digits.slice(0, 2)} ${digits.slice(2, 5)} ${digits.slice(5)}`;
  return `+353 ${digits}`;
}

summary.getRange("A2:H2").merge();
summary.getRange("A2").values = [["Irish company phone extraction"]];
summary.getRange("A2").format.font = { name: font, size: 16, bold: true, color: navy };
summary.getRange("A3:H3").format.borders = { bottom: { style: "thin", color: "#9EADBA" } };
summary.getRange("A4:H4").merge();
summary.getRange("A4").values = [[`Public business numbers only. Run date: ${payload.summary.generated_at}`]];
summary.getRange("A4").format.font = { name: font, size: 10, italic: true, color: muted };

summary.getRange("A6:B6").values = [["Metric", "Result"]];
summary.getRange("A6:B6").format = {
  fill: navy,
  font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
};
summary.getRange("A7:A16").values = [
  ["Irish source rows"],
  ["Distinct company names"],
  ["Company rows with landline"],
  ["Unique landline numbers"],
  ["Company-mobile rows"],
  ["Unique mobile numbers"],
  ["Mobile occurrences found"],
  ["No public landline found"],
  ["Website errors"],
  ["Websites verified or supplied"],
];
const lastResultRow = records.length + 4;
const lastMobileRow = mobileRecords.length + 4;
summary.getRange("B7").values = [[payload.summary.irish_source_rows]];
summary.getRange("B8:B9").formulas = [
  [`=COUNTA(Results!A5:A${lastResultRow})`],
  [`=COUNTIF(Results!E5:E${lastResultRow},"found")`],
];
summary.getRange("B10").values = [[new Set(records.filter((row) => row.phone_status === "found").map((row) => row.phone_e164)).size]];
summary.getRange("B11").formulas = [[`=COUNTA('Mobile numbers'!A5:A${lastMobileRow})`]];
summary.getRange("B12:B13").values = [[payload.summary.unique_mobile_numbers], [payload.summary.mobile_occurrences_found]];
summary.getRange("B14:B16").formulas = [
  [`=COUNTIF(Results!E5:E${lastResultRow},"not_found")`],
  [`=COUNTIF(Results!E5:E${lastResultRow},"site_error")+COUNTIF(Results!E5:E${lastResultRow},"extractor_error")`],
  [`=COUNTIF(Results!F5:F${lastResultRow},"resolved")+COUNTIF(Results!F5:F${lastResultRow},"supplied")`],
];
summary.getRange("A7:B16").format.font = { name: font, size: 10 };
summary.getRange("B7:B16").format.numberFormat = "#,##0";
summary.getRange("A7:B16").format.borders = { insideHorizontal: { style: "thin", color: "#D9E1F2" } };
summary.getRange("A9:B10").format.fill = paleGreen;
summary.getRange("A11:B13").format.fill = paleAmber;
summary.getRange("A15:B15").format.fill = paleRed;

summary.getRange("D6:H6").merge();
summary.getRange("D6").values = [["Method and limits"]];
summary.getRange("D6:H6").format = {
  fill: blue,
  font: { name: font, size: 10, bold: true, color: navy },
};
summary.getRange("D7:H12").merge(true);
summary.getRange("D7:D12").values = [
  ["1. Existing website from the pipeline."],
  ["2. Official link recovered from the recorded discovery page."],
  ["3. Verified direct-domain candidates."],
  ["4. Free web search, stopped after repeated network failures."],
  ["Mobile numbers are retained on their own tab. Repeated appearances are deduplicated within each company."],
  ["A blank phone means no qualifying number was found on the pages checked. It does not prove that the company has no phone number."],
];
summary.getRange("D7:H12").format = { font: { name: font, size: 10 }, wrapText: true, verticalAlignment: "top" };
summary.getRange("D7:H12").format.rowHeight = 30;
summary.getRange("A18:H18").merge();
summary.getRange("A18").values = [["Use Results for landlines and Mobile numbers for the newly included mobiles. Every accepted number includes its source page."]];
summary.getRange("A18").format = { fill: paleAmber, font: { name: font, size: 10, bold: true, color: "#7F6000" }, wrapText: true };
summary.getRange("A18:H18").format.rowHeight = 32;
summary.getRange("A1:H19").format.verticalAlignment = "center";
summary.getRange("A:A").format.columnWidth = 29;
summary.getRange("B:B").format.columnWidth = 14;
summary.getRange("C:C").format.columnWidth = 3;
summary.getRange("D:H").format.columnWidth = 18;

results.getRange("A2:N2").merge();
results.getRange("A2").values = [["Irish company landline results"]];
results.getRange("A2").format.font = { name: font, size: 16, bold: true, color: navy };
results.getRange("A3:N3").merge();
results.getRange("A3").values = [["Sorted with found numbers first. Filter by status, company, or website method."]];
results.getRange("A3").format.font = { name: font, size: 10, italic: true, color: muted };

const headers = [
  "Company", "Phone", "E.164", "Phone type", "Phone status", "Website status",
  "Official website", "Phone source URL", "Website method", "Pages checked",
  "Candidates", "Mobile occurrences", "Pipeline row(s)", "Context or notes",
];
const rows = records.map((row) => [
  row.company_name,
  formatNational(row.phone_display),
  formatInternational(row.phone_e164),
  row.phone_type,
  row.phone_status,
  row.website_status,
  row.resolved_website,
  row.source_url,
  row.website_method,
  row.pages_checked,
  row.candidate_count,
  row.excluded_mobile_count,
  row.source_rows,
  row.context || row.notes,
]);
results.getRange("A4:N4").values = [headers];
results.getRange("A5").write(rows);
results.getRange("A4:N4").format = {
  fill: navy,
  font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { insideVertical: { style: "thin", color: "#FFFFFF" } },
};
results.getRange(`A5:N${lastResultRow}`).format.font = { name: font, size: 9 };
results.getRange(`A5:N${lastResultRow}`).format.verticalAlignment = "top";
results.getRange(`J5:L${lastResultRow}`).format.numberFormat = "#,##0";
results.getRange(`M5:M${lastResultRow}`).format.numberFormat = "@";
results.getRange(`B5:C${lastResultRow}`).format.numberFormat = "@";
results.getRange(`A5:N${lastResultRow}`).format.borders = { insideHorizontal: { style: "thin", color: "#E7E6E6" } };
results.getRange(`E5:E${lastResultRow}`).conditionalFormats.add("containsText", { text: "found", format: { fill: paleGreen, font: { bold: true, color: "#375623" } } });
results.getRange(`E5:E${lastResultRow}`).conditionalFormats.add("containsText", { text: "error", format: { fill: paleRed, font: { bold: true, color: "#9C0006" } } });
results.getRange(`F5:F${lastResultRow}`).conditionalFormats.add("containsText", { text: "search_error", format: { fill: paleAmber, font: { color: "#7F6000" } } });
results.getRange(`A4:N${lastResultRow}`).format.wrapText = false;
results.getRange(`N5:N${lastResultRow}`).format.wrapText = true;
results.getRange(`N5:N${lastResultRow}`).format.rowHeight = 30;
results.getRange("A:A").format.columnWidth = 30;
results.getRange("B:C").format.columnWidth = 16;
results.getRange("D:F").format.columnWidth = 18;
results.getRange("G:H").format.columnWidth = 42;
results.getRange("I:I").format.columnWidth = 24;
results.getRange("J:M").format.columnWidth = 14;
results.getRange("N:N").format.columnWidth = 52;
results.freezePanes.freezeRows(4);
results.freezePanes.freezeColumns(1);
const table = results.tables.add(`A4:N${lastResultRow}`, true, "IrishPhoneResultsTable");
table.style = "TableStyleMedium2";

mobiles.getRange("A2:H2").merge();
mobiles.getRange("A2").values = [["Irish company mobile numbers"]];
mobiles.getRange("A2").format.font = { name: font, size: 16, bold: true, color: navy };
mobiles.getRange("A3:H3").merge();
mobiles.getRange("A3").values = [["Deduplicated by company and number. A shared number can appear for more than one company."]];
mobiles.getRange("A3").format.font = { name: font, size: 10, italic: true, color: muted };
const mobileHeaders = [
  "Company", "Mobile", "E.164", "Phone source URL", "Official website",
  "Extraction method", "Pipeline row(s)", "Context",
];
const mobileRows = mobileRecords.map((row) => [
  row.company_name,
  formatNational(row.phone_display),
  formatInternational(row.phone_e164),
  row.source_url,
  row.resolved_website,
  row.extraction_method,
  row.source_rows,
  row.context,
]);
mobiles.getRange("A4:H4").values = [mobileHeaders];
mobiles.getRange("A5").write(mobileRows);
mobiles.getRange("A4:H4").format = {
  fill: navy,
  font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { insideVertical: { style: "thin", color: "#FFFFFF" } },
};
mobiles.getRange(`A5:H${lastMobileRow}`).format = {
  font: { name: font, size: 9 },
  verticalAlignment: "top",
  borders: { insideHorizontal: { style: "thin", color: "#E7E6E6" } },
};
mobiles.getRange(`B5:C${lastMobileRow}`).format.numberFormat = "@";
mobiles.getRange(`H5:H${lastMobileRow}`).format.wrapText = true;
mobiles.getRange(`H5:H${lastMobileRow}`).format.rowHeight = 34;
mobiles.getRange("A:A").format.columnWidth = 30;
mobiles.getRange("B:C").format.columnWidth = 18;
mobiles.getRange("D:E").format.columnWidth = 44;
mobiles.getRange("F:F").format.columnWidth = 20;
mobiles.getRange("G:G").format.columnWidth = 16;
mobiles.getRange("H:H").format.columnWidth = 58;
mobiles.freezePanes.freezeRows(4);
mobiles.freezePanes.freezeColumns(1);
const mobileTable = mobiles.tables.add(`A4:H${lastMobileRow}`, true, "IrishMobileResultsTable");
mobileTable.style = "TableStyleMedium2";

workbook.recalculate();
const summaryCheck = await workbook.inspect({
  kind: "table", range: "Summary!A2:H18", include: "values,formulas",
  tableMaxRows: 20, tableMaxCols: 10,
});
console.log(summaryCheck.ndjson);
const resultCheck = await workbook.inspect({
  kind: "table", range: `Results!A4:N${Math.min(lastResultRow, 12)}`, include: "values,formulas",
  tableMaxRows: 12, tableMaxCols: 14,
});
console.log(resultCheck.ndjson);
const mobileCheck = await workbook.inspect({
  kind: "table", range: `Mobile numbers!A4:H${lastMobileRow}`, include: "values,formulas",
  tableMaxRows: 15, tableMaxCols: 8,
});
console.log(mobileCheck.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

for (const sheetName of ["Summary", "Results", "Mobile numbers"]) {
  const preview = await workbook.render({
    sheetName,
    range: sheetName === "Results" ? "A1:N32" : sheetName === "Mobile numbers" ? `A1:H${lastMobileRow}` : "A1:H19",
    scale: 1,
    format: "png",
  });
  await fs.writeFile(`${outputDir}/${sheetName.toLowerCase()}_preview.png`, new Uint8Array(await preview.arrayBuffer()));
}

await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, recordCount: records.length, mobileRecordCount: mobileRecords.length, lastResultRow, lastMobileRow }));
