import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const inputPath = "C:/Users/Admin/Documents/BBT_bizdev/outputs/linkedin_enrichment_full/BlueBridge_TOFU_BizDev_V1_LinkedIn.xlsx";
const outputDir = "C:/Users/Admin/Documents/BBT_bizdev/outputs/lead_filter_distributions";
const outputPath = `${outputDir}/Lead_Filtering_Distributions.xlsx`;

const input = await FileBlob.load(inputPath);
const sourceWb = await SpreadsheetFile.importXlsx(input);
const sourceSheet = sourceWb.worksheets.getItem("Lead Filtering");
const raw = sourceSheet.getRange("A1:AX3015").values;
const headers = raw[0];
const sourceRows = raw.slice(1).filter((row) => String(row[0] ?? "").trim() !== "");

const wanted = [
  "Company",
  "Evidence year",
  "Trigger type",
  "Geography",
  "Company type",
  "Company stage",
  "Product area",
  "Hiring signal",
  "Funding stage",
  "Primary BBT quadrant",
  "Legacy priority band",
];
const sourceIndexes = wanted.map((name) => headers.indexOf(name));
const dataRows = sourceRows.map((row) => sourceIndexes.map((idx) => row[idx] ?? null));

const countValues = (header) => {
  const idx = headers.indexOf(header);
  const counts = new Map();
  for (const row of sourceRows) {
    const value = row[idx];
    const key = value == null || String(value).trim() === "" ? "(Blank)" : String(value).trim();
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
};

const workbook = Workbook.create();
const dashboard = workbook.worksheets.add("Dashboard");
const summaries = workbook.worksheets.add("Summary Tables");
const data = workbook.worksheets.add("Lead Data");
dashboard.showGridLines = false;
summaries.showGridLines = false;
data.showGridLines = false;

data.getRangeByIndexes(0, 0, 1, wanted.length).values = [wanted];
data.getRangeByIndexes(1, 0, dataRows.length, wanted.length).values = dataRows;
data.getRange(`A1:K${dataRows.length + 1}`).format.font = { name: "Aptos", size: 10 };
data.getRange("A1:K1").format = {
  fill: "#17365D",
  font: { name: "Aptos", size: 10, bold: true, color: "#FFFFFF" },
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: "#17365D" },
};
data.getRange("A:A").format.columnWidth = 26;
data.getRange("B:B").format.columnWidth = 14;
data.getRange("C:C").format.columnWidth = 24;
data.getRange("D:D").format.columnWidth = 18;
data.getRange("E:E").format.columnWidth = 24;
data.getRange("F:F").format.columnWidth = 25;
data.getRange("G:G").format.columnWidth = 22;
data.getRange("H:H").format.columnWidth = 14;
data.getRange("I:I").format.columnWidth = 30;
data.getRange("J:J").format.columnWidth = 24;
data.getRange("K:K").format.columnWidth = 20;
data.freezePanes.freezeRows(1);
data.tables.add(`A1:K${dataRows.length + 1}`, true, "LeadDataTable");

const total = dataRows.length;
const specs = [
  { title: "Companies by Evidence Year", header: "Evidence year", dataCol: "B", order: ["2026","2025","2024","2023","2022","2021","2020","2019","2018","2017","2016","2015","2014","2013","2012","2011","2010","(Blank)"], pos: ["A5", "N20"], color: "#2F75B5" },
  { title: "Companies by Trigger Type", header: "Trigger type", dataCol: "C", pos: ["P5", "AC20"], color: "#00A6A6" },
  { title: "Companies by Product Area", header: "Product area", dataCol: "G", pos: ["A23", "N38"], color: "#5B9BD5" },
  { title: "Companies by Geography", header: "Geography", dataCol: "D", pos: ["P23", "AC38"], color: "#70AD47" },
  { title: "Companies by Company Stage", header: "Company stage", dataCol: "F", pos: ["A41", "N56"], color: "#8064A2" },
  { title: "Companies by Funding Stage", header: "Funding stage", dataCol: "I", pos: ["P41", "AC56"], color: "#ED7D31" },
  { title: "Companies by BBT Quadrant", header: "Primary BBT quadrant", dataCol: "J", pos: ["A59", "N74"], color: "#4472C4" },
  { title: "Companies by Priority Band", header: "Legacy priority band", dataCol: "K", pos: ["P59", "AC74"], color: "#C55A11" },
];

dashboard.getRange("A1:AC2").merge();
dashboard.getRange("A1").values = [["Lead Filtering — Company Distribution Dashboard"]];
dashboard.getRange("A1:AC2").format = {
  fill: "#17365D",
  font: { name: "Aptos Display", size: 20, bold: true, color: "#FFFFFF" },
  verticalAlignment: "center",
};
dashboard.getRange("A3:F3").merge();
dashboard.getRange("A3").values = [[`Companies analysed: ${total.toLocaleString("en-IE")}`]];
dashboard.getRange("A3:F3").format = { fill: "#D9EAF7", font: { name: "Aptos", size: 11, bold: true, color: "#17365D" } };
dashboard.getRange("G3:AC3").merge();
dashboard.getRange("G3").values = [["Source: Lead Filtering tab in BlueBridge_TOFU_BizDev_V1_LinkedIn.xlsx"]];
dashboard.getRange("G3:AC3").format = { font: { name: "Aptos", size: 10, italic: true, color: "#595959" } };

summaries.getRange("A1:D1").merge();
summaries.getRange("A1").values = [["Distribution Tables"]];
summaries.getRange("A1:D1").format = { fill: "#17365D", font: { name: "Aptos Display", size: 16, bold: true, color: "#FFFFFF" } };

let summaryRow = 3;
for (const spec of specs) {
  const categories = spec.order || countValues(spec.header).map(([label]) => label);
  const start = summaryRow;
  summaries.getRange(`A${start}:C${start}`).values = [[spec.title, "Count", "Share"]];
  summaries.getRange(`A${start}:C${start}`).format = {
    fill: "#D9EAF7",
    font: { name: "Aptos", size: 10, bold: true, color: "#17365D" },
    borders: { preset: "outside", style: "thin", color: "#9EADBA" },
  };
  const end = start + categories.length;
  summaries.getRange(`A${start + 1}:A${end}`).values = categories.map((x) => [x]);
  const countFormulas = categories.map((label, i) => {
    const r = start + 1 + i;
    return [label === "(Blank)"
      ? `=COUNTBLANK('Lead Data'!$${spec.dataCol}$2:$${spec.dataCol}$${total + 1})`
      : `=COUNTIF('Lead Data'!$${spec.dataCol}$2:$${spec.dataCol}$${total + 1},A${r})`];
  });
  summaries.getRange(`B${start + 1}:B${end}`).formulas = countFormulas;
  summaries.getRange(`C${start + 1}:C${start + 1}`).formulas = [[`=B${start + 1}/${total}`]];
  summaries.getRange(`C${start + 1}:C${end}`).fillDown();
  summaries.getRange(`B${start + 1}:B${end}`).format.numberFormat = "#,##0";
  summaries.getRange(`C${start + 1}:C${end}`).format.numberFormat = "0.0%";
  summaries.getRange(`A${start + 1}:C${end}`).format.font = { name: "Aptos", size: 10 };
  summaries.getRange(`A${start}:C${end}`).format.borders = { preset: "outside", style: "thin", color: "#B7C9D6" };

  const chart = dashboard.charts.add("bar", summaries.getRange(`A${start}:B${end}`));
  chart.title = spec.title;
  chart.titleTextStyle.fontSize = 13;
  chart.hasLegend = false;
  chart.yAxis = { numberFormatCode: "#,##0" };
  chart.setPosition(spec.pos[0], spec.pos[1]);
  if (chart.series.items.length) chart.series.items[0].fill = spec.color;
  summaryRow = end + 3;
}

summaries.getRange("A:C").format.columnWidth = 22;
summaries.getRange("A:A").format.columnWidth = 32;
summaries.freezePanes.freezeRows(2);
dashboard.getRange("A:AC").format.columnWidth = 10;
dashboard.getRange("A1:AC74").format.font = { name: "Aptos", size: 10 };
dashboard.getRange("A1:AC2").format.font = { name: "Aptos Display", size: 20, bold: true, color: "#FFFFFF" };
dashboard.freezePanes.freezeRows(3);

await fs.mkdir(outputDir, { recursive: true });
const preview = await workbook.render({ sheetName: "Dashboard", range: "A1:AC74", scale: 1, format: "png" });
await fs.writeFile(`${outputDir}/dashboard_preview.png`, new Uint8Array(await preview.arrayBuffer()));
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);

const keyCheck = await workbook.inspect({ kind: "table", sheetId: "Summary Tables", range: "A1:C30", include: "values,formulas", tableMaxRows: 30, tableMaxCols: 3, maxChars: 10000 });
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan", maxChars: 4000 });
console.log(keyCheck.ndjson);
console.log(errors.ndjson);
console.log(outputPath);
