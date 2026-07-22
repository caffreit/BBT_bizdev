import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [sourcePath, campaignPath, outputPath, previewPath] = process.argv.slice(2);
if (!sourcePath || !campaignPath || !outputPath || !previewPath) {
  throw new Error("Usage: node build_bizdev_handoff.mjs source.xlsx campaign.xlsx output.xlsx preview.png");
}
const outputDir = outputPath.replace(/[\\/][^\\/]+$/, "");

const source = await SpreadsheetFile.importXlsx(await FileBlob.load(sourcePath));
const campaign = await SpreadsheetFile.importXlsx(await FileBlob.load(campaignPath));
const contactsValues = source.worksheets.getItem("Contacts").getUsedRange(true).values;
const companiesValues = source.worksheets.getItem("Companies").getUsedRange(true).values;
const campaignContactsValues = campaign.worksheets.getItem("Contact Decisions").getUsedRange(true).values;
const campaignCompaniesValues = campaign.worksheets.getItem("Company Decisions").getUsedRange(true).values;

const toIndex = (header) => Object.fromEntries(header.map((name, i) => [String(name ?? ""), i]));
const contactIndex = toIndex(contactsValues[0]);
const companyIndex = toIndex(companiesValues[0]);
const campaignContactIndex = toIndex(campaignContactsValues[0]);
const campaignCompanyIndex = toIndex(campaignCompaniesValues[0]);
const companyById = new Map(companiesValues.slice(1).map((row) => [row[companyIndex["Company ID"]], row]));
const campaignContactById = new Map(campaignContactsValues.slice(1).map((row) => [row[campaignContactIndex["Record ID"]], row]));
const campaignCompanyById = new Map(campaignCompaniesValues.slice(1).map((row) => [row[campaignCompanyIndex["Company ID"]], row]));

const headers = [
  "First Name", "Last Name", "Email", "Email Domain", "Original Company", "Resolved Company",
  "Job Title", "Seniority", "Buying Role", "Primary Service Relevance", "Campaign Segment",
  "Website", "Website Status", "Redirect Target", "Company Type", "Employee Band", "Maturity Stage",
  "Product Profile", "Regulatory Signals", "Recommended Services", "Evidence Summary",
];

const contactField = (row, name) => row[contactIndex[name]] ?? null;
const companyField = (row, name) => row ? (row[companyIndex[name]] ?? null) : null;
const campaignContactField = (row, name) => row ? (row[campaignContactIndex[name]] ?? null) : null;
const campaignCompanyField = (row, name) => row ? (row[campaignCompanyIndex[name]] ?? null) : null;
const rows = contactsValues.slice(1).map((contact) => {
  const companyId = contactField(contact, "Company ID");
  const company = companyById.get(companyId);
  const campaignContact = campaignContactById.get(contactField(contact, "Record ID"));
  const campaignCompany = campaignCompanyById.get(companyId);
  const originalCompany = contactField(contact, "Original Company");
  return [
    contactField(contact, "First Name"),
    contactField(contact, "Last Name"),
    contactField(contact, "Email"),
    contactField(contact, "Email Domain"),
    originalCompany === "#NAME?" ? null : originalCompany,
    campaignContactField(campaignContact, "Company") ?? contactField(contact, "Resolved Company"),
    campaignContactField(campaignContact, "Job Title") ?? contactField(contact, "Job Title"),
    campaignContactField(campaignContact, "Seniority") ?? contactField(contact, "Seniority"),
    campaignContactField(campaignContact, "Buying Role") ?? contactField(contact, "Buying Role"),
    contactField(contact, "Primary Service Relevance"),
    contactField(contact, "Campaign Segment"),
    companyField(company, "Website"),
    companyField(company, "Website Status"),
    companyField(company, "Redirect Target"),
    campaignCompanyField(campaignCompany, "Company Type") ?? companyField(company, "Company Type"),
    campaignCompanyField(campaignCompany, "Employee Band") ?? companyField(company, "Employee Band"),
    campaignCompanyField(campaignCompany, "Maturity Stage") ?? companyField(company, "Maturity Stage"),
    campaignCompanyField(campaignCompany, "Product Profile") ?? companyField(company, "Product Profile"),
    campaignCompanyField(campaignCompany, "Regulatory Signals") ?? companyField(company, "Regulatory Signals"),
    campaignCompanyField(campaignCompany, "Recommended Services") ?? companyField(company, "Recommended Services"),
    campaignCompanyField(campaignCompany, "Evidence Summary") ?? companyField(company, "Evidence Summary"),
  ];
});

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Biz Dev Contacts");
sheet.showGridLines = false;
sheet.getRangeByIndexes(0, 0, rows.length + 1, headers.length).values = [headers, ...rows];

const lastRow = rows.length + 1;
const table = sheet.tables.add(`A1:U${lastRow}`, true, "BizDevContacts");
table.style = "TableStyleMedium2";
table.showBandedRows = true;
table.showFilterButton = true;

sheet.getRange("A1:U1").format = {
  fill: "#163A5F",
  font: { bold: true, color: "#FFFFFF", size: 10 },
  verticalAlignment: "center",
  wrapText: true,
  borders: { bottom: { style: "medium", color: "#0B2740" } },
};
sheet.getRange("A1:U1").format.rowHeight = 34;
sheet.getRange(`A2:U${lastRow}`).format = {
  font: { color: "#172B3A", size: 10 },
  verticalAlignment: "top",
};
sheet.getRange(`A2:U${lastRow}`).format.rowHeight = 22;

const widths = {
  A: 14, B: 18, C: 29, D: 22, E: 26, F: 26, G: 28, H: 15, I: 25, J: 24, K: 32,
  L: 29, M: 17, N: 29, O: 17, P: 16, Q: 21, R: 24, S: 22, T: 28, U: 64,
};
for (const [col, width] of Object.entries(widths)) sheet.getRange(`${col}1:${col}${lastRow}`).format.columnWidth = width;
sheet.getRange(`A2:T${lastRow}`).format.wrapText = false;
sheet.getRange(`U2:U${lastRow}`).format.wrapText = false;
sheet.getRange(`C2:C${lastRow}`).setNumberFormat("@");
sheet.freezePanes.freezeRows(1);
sheet.freezePanes.freezeColumns(3);

await fs.mkdir(outputDir, { recursive: true });
const preview = await workbook.render({ sheetName: "Biz Dev Contacts", range: "A1:U18", scale: 1, format: "png" });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const inspect = await workbook.inspect({
  kind: "table",
  range: "Biz Dev Contacts!A1:U8",
  include: "values,formulas",
  tableMaxRows: 8,
  tableMaxCols: 21,
  maxChars: 12000,
});
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
const missingCompanyJoins = contactsValues.slice(1).filter((row) => !companyById.has(contactField(row, "Company ID"))).length;
const missingCampaignContactJoins = contactsValues.slice(1).filter((row) => !campaignContactById.has(contactField(row, "Record ID"))).length;
const missingCampaignCompanyJoins = contactsValues.slice(1).filter((row) => !campaignCompanyById.has(contactField(row, "Company ID"))).length;
console.log(JSON.stringify({ outputPath, previewPath, contacts: rows.length, companies: companyById.size, missingCompanyJoins, missingCampaignContactJoins, missingCampaignCompanyJoins }));
console.log(inspect.ndjson);
console.log(errors.ndjson);
