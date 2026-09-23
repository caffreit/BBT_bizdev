import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const sourcePath = "outputs/linkedin_priority_ireland_2026_audit_v3.csv";
const outputDir = "outputs/01a0a56c-feef-7cf2-9be3-baaeca3d6ec4";
const outputPath = `${outputDir}/Irish_Small_Company_Phone_Research_2026-09-15.xlsx`;
const previewPath = `${outputDir}/Irish_Small_Company_Phone_Research_preview.png`;
const verifiedOn = new Date("2026-09-15T00:00:00Z");

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        field += '"';
        i += 1;
      } else if (ch === '"') {
        quoted = false;
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\n") {
      row.push(field.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += ch;
    }
  }
  if (field.length || row.length) {
    row.push(field.replace(/\r$/, ""));
    rows.push(row);
  }
  if (rows[0]?.[0]) rows[0][0] = rows[0][0].replace(/^\uFEFF/, "");
  return rows;
}

const research = [
  {
    company: "Altratech", target: "Yes", size: "11-50", sizeSource: "https://www.linkedin.com/company/altratech-limited/",
    phone: "+353 21 4757 300", phoneType: "Company landline", phoneStatus: "Official current",
    callAction: "Call now", phoneSource: "https://www.altratech.com/", verificationSource: "https://www.altratech.com/news/",
    email: "enquiries@altratech.com", emailSource: "https://www.altratech.com/", nextStep: "Ask for the relevant executive or operations lead."
  },
  {
    company: "Class Medical", target: "Yes", size: "2-10", sizeSource: "https://ie.linkedin.com/company/class-medical",
    phone: "+353 61 358843", phoneType: "Company landline", phoneStatus: "Official current",
    callAction: "Call now", phoneSource: "https://www.classmedical.ie/contact", verificationSource: "https://www.classmedical.ie/",
    email: "", emailSource: "", nextStep: "Ask for the founder, CEO or commercial lead."
  },
  {
    company: "Galenband", target: "Yes", size: "11-50", sizeSource: "https://www.linkedin.com/company/galenband/",
    phone: "", phoneType: "Not published", phoneStatus: "Official site checked",
    callAction: "No public number", phoneSource: "https://galenband.com/contact", verificationSource: "https://galenband.com/",
    email: "", emailSource: "", nextStep: "Use the official form and request a callback."
  },
  {
    company: "CergenX", target: "Yes", size: "11-50", sizeSource: "https://www.linkedin.com/company/cergenx",
    phone: "", phoneType: "Not published", phoneStatus: "Official site checked",
    callAction: "No public number", phoneSource: "https://www.cergenx.com/contact", verificationSource: "https://www.cergenx.com/",
    email: "info@cergenx.com", emailSource: "https://www.cergenx.com/contact", nextStep: "Email the general inbox and request a call."
  },
  {
    company: "NeuroBell", target: "Yes", size: "2-10", sizeSource: "https://ie.linkedin.com/company/neurobell",
    phone: "+353 21 490 1567", phoneType: "Company landline", phoneStatus: "Secondary source; address matched",
    callAction: "Verify first", phoneSource: "https://www.crunchbase.com/organization/neurobell", verificationSource: "https://neurobell.com/contact/",
    email: "info@neurobell.com", emailSource: "https://www.crunchbase.com/organization/neurobell", nextStep: "Confirm the company name when answered before starting the pitch."
  },
  {
    company: "Cymantic Medical", target: "Yes", size: "2-10", sizeSource: "https://www.linkedin.com/company/cymantic-medical",
    phone: "", phoneType: "Not published", phoneStatus: "Official site checked",
    callAction: "No public number", phoneSource: "https://cymanticmedical.com/", verificationSource: "",
    email: "info@cymanticmedical.com", emailSource: "https://cymanticmedical.com/", nextStep: "Email the general inbox and request a call."
  },
  {
    company: "Head Diagnostics", target: "Yes", size: "2-10", sizeSource: "https://ie.linkedin.com/company/head-diagnostics",
    phone: "+353 86 682 3242", phoneType: "Published business mobile", phoneStatus: "Published for named business contact",
    callAction: "Do not cold-call", phoneSource: "https://apps.apple.com/us/app/hdx-cognition/id6742924645", verificationSource: "https://www.readkong.com/page/start-up-showcase-2020-7984542",
    email: "info@headdiagnostics.com", emailSource: "https://headdiagnostics.com/", nextStep: "Use the official email or demo request unless call consent is documented."
  },
  {
    company: "Deciphex", target: "No", size: "201-500", sizeSource: "https://ie.linkedin.com/company/deciphex",
    phone: "+353 1 582 7193", phoneType: "Company landline", phoneStatus: "Official current",
    callAction: "Out of target size", phoneSource: "https://www.deciphex.com/", verificationSource: "",
    email: "info@deciphex.com", emailSource: "https://www.deciphex.com/", nextStep: "Keep outside the small-company campaign."
  },
  {
    company: "XWave Technologies", target: "Yes", size: "11-50", sizeSource: "https://www.linkedin.com/company/xwave-technologies/",
    phone: "", phoneType: "Not published", phoneStatus: "Official site checked",
    callAction: "No public number", phoneSource: "https://www.xwave.ie/contact", verificationSource: "https://www.xwave.ie/",
    email: "info@xwave.ie", emailSource: "https://www.xwave.ie/contact", nextStep: "Use the official email or demo form and request a callback."
  },
  {
    company: "FeelTect", target: "Yes", size: "2-10", sizeSource: "https://ie.linkedin.com/company/feeltect",
    phone: "+353 87 184 0912", phoneType: "Published business mobile", phoneStatus: "Two secondary sources",
    callAction: "Do not cold-call", phoneSource: "https://www.cbinsights.com/company/feeltect", verificationSource: "https://www.gaebler.com/Funded-Company-53D73F17-DF27-4D15-A998-F29ED0CD1EE1-FeelTect",
    email: "info@feeltect.com", emailSource: "https://feeltect.com/faqs/", nextStep: "Use the official email unless call consent is documented."
  },
  {
    company: "Gasgon Medical", target: "Yes", size: "2-10", sizeSource: "https://ie.linkedin.com/company/gasgon-medical",
    phone: "+353 21 202 8204", phoneType: "Company landline", phoneStatus: "Official current",
    callAction: "Call now", phoneSource: "https://www.gasgonmedical.com/contact", verificationSource: "https://www.gasgonmedical.com/team-3",
    email: "info@gasgonmedical.com", emailSource: "https://www.gasgonmedical.com/team-3", nextStep: "Ask for Vincent Forde or the commercial lead."
  },
  {
    company: "AVeta Medical", target: "Yes", size: "2-10", sizeSource: "https://ie.linkedin.com/company/aveta-medical",
    phone: "+353 87 676 5343", phoneType: "Published business mobile", phoneStatus: "Two secondary sources",
    callAction: "Do not cold-call", phoneSource: "https://www.crunchbase.com/organization/aveta-medical", verificationSource: "https://prospeo.io/c/aveta-medical",
    email: "info@avetamedical.com", emailSource: "https://avetamedical.com/contact", nextStep: "Use the official email unless call consent is documented."
  },
  {
    company: "AirCeption airCeption device", target: "Yes", size: "2-10", sizeSource: "https://www.linkedin.com/company/airception",
    phone: "", phoneType: "Not published", phoneStatus: "Official site checked",
    callAction: "No public number", phoneSource: "https://www.airception.com/", verificationSource: "",
    email: "", emailSource: "", nextStep: "Book a demo or email through the official site and request a callback."
  },
  {
    company: "Akara Robotics", target: "Yes", size: "11-50", sizeSource: "https://www.linkedin.com/company/akara-ai",
    phone: "", phoneType: "Not published", phoneStatus: "Official site checked",
    callAction: "No public number", phoneSource: "https://www.akara.ai/contact", verificationSource: "",
    email: "info@akara.ai", emailSource: "https://www.akara.ai/contact", nextStep: "Use the demo form or email and request a callback."
  },
  {
    company: "NUA Surgical", target: "Yes", size: "11-50", sizeSource: "https://www.linkedin.com/company/nua-surgical/",
    phone: "", phoneType: "Not published", phoneStatus: "Official site checked",
    callAction: "No public number", phoneSource: "https://nuasurgical.com/contact-us", verificationSource: "",
    email: "info@nuasurgical.com", emailSource: "https://nuasurgical.com/contact-us", nextStep: "Email the general inbox and request a call."
  },
  {
    company: "Ostoform", target: "Yes", size: "11-50", sizeSource: "https://ie.linkedin.com/company/ostoform",
    phone: "+353 87 989 4167", phoneType: "Published business mobile", phoneStatus: "Secondary product listing",
    callAction: "Do not cold-call", phoneSource: "https://www.medipreis.de/preisvergleich/ostoform-flowassist-seal-stomahautschutzring-l-10-st-ostoform-limited-19288558", verificationSource: "https://ostoform.com/wp-content/uploads/2024/12/04_Symbol-Glossary_OFSG_R1.pdf",
    email: "info@ostoform.com", emailSource: "https://ostoform.com/wp-content/uploads/2024/12/04_Symbol-Glossary_OFSG_R1.pdf", nextStep: "Use the official email unless call consent is documented."
  },
  {
    company: "Bluedrop Medical", target: "Yes", size: "11-50", sizeSource: "https://www.linkedin.com/company/bluedrop-medical",
    phone: "+353 91 762 587", phoneType: "Company landline", phoneStatus: "Two secondary sources; official address matched",
    callAction: "Verify first", phoneSource: "https://www.bizireland.com/bluedrop-medical-091-762-587", verificationSource: "https://www.signalhire.com/companies/bluedrop-medical",
    email: "info@bluedropmedical.com", emailSource: "https://bluedropmedical.com/company/", nextStep: "Confirm the Galway office when answered before starting the pitch."
  },
  {
    company: "Fastform Medical", target: "Yes", size: "1 reported", sizeSource: "https://www.medicalsdir.com/listing/fastform-medical",
    phone: "+353 51 306 912", phoneType: "Company landline", phoneStatus: "Two public sources; older company evidence",
    callAction: "Verify first", phoneSource: "https://www.medicalsdir.com/listing/fastform-medical", verificationSource: "https://hih.ie/fastform-research-announces-north-american-distribution-agreement/",
    email: "", emailSource: "", nextStep: "Confirm FastForm Medical when answered before starting the pitch."
  },
  {
    company: "Hidramed Solutions", target: "Yes", size: "2-10", sizeSource: "https://ie.linkedin.com/company/hidramed-solutions-ltd",
    phone: "+353 1 961 7891", phoneType: "Company landline", phoneStatus: "Official current",
    callAction: "Call now", phoneSource: "https://hidramedsolutions.com/contact/", verificationSource: "https://hidramedsolutions.com/prescriber-information/",
    email: "info@hidramedsolutions.com", emailSource: "https://hidramedsolutions.com/contact/", nextStep: "Ask for the founder, CEO or commercial lead."
  },
  {
    company: "Ecco Spray", target: "Yes", size: "2-10", sizeSource: "https://ie.linkedin.com/company/eccospray",
    phone: "+353 87 245 9010", phoneType: "Published business mobile", phoneStatus: "Secondary company registry profile",
    callAction: "Do not cold-call", phoneSource: "https://companycheck.ie/company/711459", verificationSource: "https://www.pocusspray.com/pages/about-us",
    email: "", emailSource: "", nextStep: "Use the official contact route unless call consent is documented."
  }
];

const csvRows = parseCsv(await fs.readFile(sourcePath, "utf8"));
const headers = csvRows[0];
const dataRows = csvRows.slice(1).filter((row) => row.some((value) => value !== ""));
const companyIndex = headers.indexOf("company");
const nameIndex = headers.indexOf("name");
const titleIndex = headers.indexOf("title");
const contactMap = new Map();
for (const row of dataRows) {
  const company = row[companyIndex];
  if (!contactMap.has(company)) contactMap.set(company, []);
  const name = row[nameIndex]?.trim();
  const title = row[titleIndex]?.trim();
  if (name) contactMap.get(company).push(title ? `${name} (${title})` : name);
}

const workbook = Workbook.create();
const callSheet = workbook.worksheets.add("Call list");
const methodSheet = workbook.worksheets.add("Method");
const sourceSheet = workbook.worksheets.add("Source contacts");
const font = "Arial";

callSheet.showGridLines = false;
callSheet.getRange("A2:P2").merge();
callSheet.getRange("A2").values = [["Irish small-company phone research"]];
callSheet.getRange("A2").format.font = { name: font, size: 16, bold: true, color: "#17233C" };
callSheet.getRange("A3:P3").merge();
callSheet.getRange("A3").values = [["Phone-first sales research. Public business numbers only. Verified 15 September 2026."]];
callSheet.getRange("A3").format.font = { name: font, size: 10, italic: true, color: "#5B6577" };

callSheet.getRange("A5:J5").values = [["Target companies", null, "Call now", null, "Verify first", null, "Do not cold-call", null, "No public number", null]];
callSheet.getRange("A6:J6").values = [[null, null, null, null, null, null, null, null, null, null]];
callSheet.getRange("A6").formulas = [["=COUNTIFS(B9:B28,\"Yes\")"]];
callSheet.getRange("C6").formulas = [["=COUNTIFS(J9:J28,\"Call now\")"]];
callSheet.getRange("E6").formulas = [["=COUNTIFS(J9:J28,\"Verify first\")"]];
callSheet.getRange("G6").formulas = [["=COUNTIFS(J9:J28,\"Do not cold-call\")"]];
callSheet.getRange("I6").formulas = [["=COUNTIFS(J9:J28,\"No public number\")"]];
for (const rangeAddress of ["A5:B6", "C5:D6", "E5:F6", "G5:H6", "I5:J6"]) {
  const range = callSheet.getRange(rangeAddress);
  range.format.fill = "#E8EEF7";
  range.format.borders = { preset: "outside", style: "thin", color: "#B8C4D6" };
}
callSheet.getRange("A5:J5").format.font = { name: font, size: 10, bold: true, color: "#30445F" };
callSheet.getRange("A6:J6").format.font = { name: font, size: 14, bold: true, color: "#17233C" };

const callHeaders = ["Company", "Target", "Size band", "Size source", "Existing contacts from CSV", "Phone", "Phone type", "Phone evidence", "Phone confidence", "Call action", "Phone source", "Verification source", "Business email", "Email source", "Next step", "Verified on"];
const callRows = research.map((item) => [
  item.company,
  item.target,
  item.size,
  item.sizeSource,
  (contactMap.get(item.company) || []).join("; "),
  item.phone,
  item.phoneType,
  item.phoneStatus,
  item.phoneStatus === "Official current" ? "High" : item.phone ? "Medium" : "No number",
  item.callAction,
  item.phoneSource,
  item.verificationSource,
  item.email,
  item.emailSource,
  item.nextStep,
  verifiedOn,
]);
callSheet.getRange("A8:P8").values = [callHeaders];
callSheet.getRange("A9:P28").values = callRows;
callSheet.tables.add("A8:P28", true, "CallListTable").style = "TableStyleMedium2";
callSheet.getRange("A8:P28").format.font = { name: font, size: 10, color: "#1F2937" };
callSheet.getRange("A8:P8").format.font = { name: font, size: 10, bold: true, color: "#FFFFFF" };
callSheet.getRange("A8:P8").format.fill = "#244A73";
callSheet.getRange("A8:P8").format.wrapText = true;
callSheet.getRange("A9:P28").format.verticalAlignment = "top";
callSheet.getRange("C9:C28").format.horizontalAlignment = "center";
callSheet.getRange("B9:B28").format.horizontalAlignment = "center";
callSheet.getRange("F9:F28").format.numberFormat = "@";
callSheet.getRange("P9:P28").format.numberFormat = "dd mmm yyyy";
callSheet.getRange("J9:J28").conditionalFormats.add("containsText", { text: "Call now", format: { fill: "#DDF2E3", font: { bold: true, color: "#1D6B36" } } });
callSheet.getRange("J9:J28").conditionalFormats.add("containsText", { text: "Verify first", format: { fill: "#FFF1CC", font: { bold: true, color: "#8A5A00" } } });
callSheet.getRange("J9:J28").conditionalFormats.add("containsText", { text: "Do not cold-call", format: { fill: "#FCE1E1", font: { bold: true, color: "#A12622" } } });
callSheet.getRange("J9:J28").conditionalFormats.add("containsText", { text: "No public number", format: { fill: "#EEF1F4", font: { color: "#5F6875" } } });
callSheet.getRange("J9:J28").conditionalFormats.add("containsText", { text: "Out of target size", format: { fill: "#EEF1F4", font: { color: "#5F6875" } } });
callSheet.getRange("A8:P28").format.autofitColumns();
callSheet.getRange("A8:P28").format.autofitRows();
const widths = [155, 60, 70, 190, 230, 120, 125, 190, 85, 115, 210, 210, 170, 210, 260, 95];
widths.forEach((width, index) => { callSheet.getRangeByIndexes(0, index, 28, 1).format.columnWidthPx = width; });
callSheet.getRange("A9:P28").format.rowHeightPx = 44;
callSheet.freezePanes.freezeRows(8);
callSheet.freezePanes.freezeColumns(1);
callSheet.tabColor = "#244A73";

methodSheet.showGridLines = false;
methodSheet.getRange("A2:F2").merge();
methodSheet.getRange("A2").values = [["Phone-first research method"]];
methodSheet.getRange("A2").format.font = { name: font, size: 16, bold: true, color: "#17233C" };
methodSheet.getRange("A4:B4").values = [["Step", "Research action"]];
methodSheet.getRange("A5:B11").values = [
  [1, "Start with the company website. Check the footer, Contact, Privacy, Terms, Press, Careers and downloadable PDFs."],
  [2, "Search the exact company name with phone, telephone, town and Eircode."],
  [3, "Check business listings, accelerator profiles, university spin-out pages, investor portfolios and conference directories."],
  [4, "Match a secondary-source number to the official website, address or a second independent source."],
  [5, "Classify each result as company landline, department line, published business mobile or not published."],
  [6, "Never infer extensions, number ranges or personal mobiles. Record a negative result instead."],
  [7, "Call the company number and ask for the named person or relevant role from the source CSV."],
];
methodSheet.getRange("A4:B11").format.font = { name: font, size: 10, color: "#1F2937" };
methodSheet.getRange("A4:B4").format = { fill: "#244A73", font: { name: font, size: 10, bold: true, color: "#FFFFFF" } };
methodSheet.getRange("A13:B13").values = [["Call action", "Meaning"]];
methodSheet.getRange("A14:B18").values = [
  ["Call now", "Current company landline published by the company."],
  ["Verify first", "Landline found in secondary sources. Confirm the company identity when answered."],
  ["Do not cold-call", "Published mobile number. Use only where the organisation has documented consent or another lawful basis."],
  ["No public number", "Use the official email, form or demo request and ask for a callback."],
  ["Out of target size", "Company exceeds the small-company campaign threshold."],
];
methodSheet.getRange("A13:B18").format.font = { name: font, size: 10, color: "#1F2937" };
methodSheet.getRange("A13:B13").format = { fill: "#244A73", font: { name: font, size: 10, bold: true, color: "#FFFFFF" } };
methodSheet.getRange("A20:B20").values = [["Compliance control", "Source"]];
methodSheet.getRange("A21:B23").values = [
  ["Screen numbers against the National Directory Database opt-out register before a campaign.", "https://www.dataprotection.ie/en/organisations/rules-electronic-and-direct-marketing/ndd-faqs"],
  ["Do not make unsolicited marketing calls to mobile numbers without the required consent.", "https://www.dataprotection.ie/en/faqs/direct-marketing/can-my-mobile-phone-be-targeted-marketing-phone-calls"],
  ["Record objections immediately and suppress future marketing contact.", "https://www.dataprotection.ie/en/organisations/rules-electronic-and-direct-marketing"],
];
methodSheet.getRange("A20:B23").format.font = { name: font, size: 10, color: "#1F2937" };
methodSheet.getRange("A20:B20").format = { fill: "#244A73", font: { name: font, size: 10, bold: true, color: "#FFFFFF" } };
methodSheet.getRange("A4:B23").format.borders = { insideHorizontal: { style: "thin", color: "#D9E0E8" }, bottom: { style: "thin", color: "#B8C4D6" } };
methodSheet.getRange("A1:A23").format.columnWidthPx = 170;
methodSheet.getRange("B1:B23").format.columnWidthPx = 720;
methodSheet.getRange("A5:B23").format.wrapText = true;
methodSheet.getRange("A5:B23").format.autofitRows();
methodSheet.tabColor = "#6687A8";

sourceSheet.showGridLines = false;
sourceSheet.getRangeByIndexes(0, 0, csvRows.length, headers.length).values = [headers, ...dataRows];
sourceSheet.tables.add(`A1:R${dataRows.length + 1}`, true, "SourceContactsTable").style = "TableStyleMedium2";
sourceSheet.getRange(`A1:R${dataRows.length + 1}`).format.font = { name: font, size: 9, color: "#1F2937" };
sourceSheet.getRange("A1:R1").format = { fill: "#52677E", font: { name: font, size: 9, bold: true, color: "#FFFFFF" }, wrapText: true };
sourceSheet.getRange(`A1:R${dataRows.length + 1}`).format.autofitColumns();
sourceSheet.getRange("A:R").format.columnWidthPx = 145;
sourceSheet.getRange("A:A").format.columnWidthPx = 140;
sourceSheet.getRange("B:C").format.columnWidthPx = 210;
sourceSheet.getRange("K:L").format.columnWidthPx = 160;
sourceSheet.getRange("Q:R").format.columnWidthPx = 240;
sourceSheet.freezePanes.freezeRows(1);
sourceSheet.freezePanes.freezeColumns(1);

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });
const preview = await workbook.render({ sheetName: "Call list", range: "A1:P28", scale: 1, format: "png" });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const inspect = await workbook.inspect({ kind: "table", range: "Call list!A2:P28", include: "values,formulas", tableMaxRows: 30, tableMaxCols: 16, maxChars: 18000 });
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan" });
console.log(JSON.stringify({ outputPath, previewPath, sourceRows: dataRows.length, researchRows: research.length }));
console.log(inspect.ndjson);
console.log(errors.ndjson);
