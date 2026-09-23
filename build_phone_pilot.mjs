import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "/home/ivan/Projects/BBT/BBT_bizdev/outputs/phone_pilot_20260915";
const outputPath = `${outputDir}/Irish_startup_phone_pilot_25.xlsx`;
const researchedOn = new Date("2026-09-15T00:00:00Z");

const rows = [
  [1, 851, "Eila Connect", "Eila Connect (Crothers Security Ltd)", "Dublin", "Employee count not found", "Unverified", "+353 1 456 7949", "Company office line", 1, "Official website", "https://eilaconnect.ie/company-news/winter-special-offer-eila-connect/", "https://eilaconnect.ie/privacy-policy/", "Office line found", "Hold for NDD screening", "Official page contains a minor conflicting international-format number elsewhere; use the displayed 01 456 7949 only after validation.", researchedOn],
  [2, 1145, "Head Diagnostics", "Head Diagnostics Limited", "Dublin", "Micro company", "Likely <=25", "", "", "", "", "", "https://www.solocheck.ie/Irish-Company/Head-Diagnostics-Limited-633484", "No public office line found", "No number", "Company identity and micro-company status verified from an Irish company directory.", researchedOn],
  [3, 52, "AVeta Medical", "AVeta Medical", "Galway", "Employee count not found", "Unverified", "", "", "", "", "", "https://avetamedical.com/contact", "No public office line found", "No number", "Official contact page lists an office and email but no telephone number.", researchedOn],
  [4, 2758, "Tympany Medical", "Tympany Medical Ltd", "Galway", "11 public employee profiles; LinkedIn band 11-50", "Likely <=25", "+353 91 330 985", "Company administration line", 1, "Official website", "https://tympanymedical.com/thank-you/", "https://www.linkedin.com/company/tympany-medical/", "Office line found", "Hold for NDD screening", "Official site labels this for administration and general queries.", researchedOn],
  [5, 2539, "Spiorad Medical", "Spiorad Medical", "Ireland", "Employee count not found", "Unverified", "", "", "", "", "", "https://spioradmedical.com/privacy-policy/", "No public office line found", "No number", "Official site provides email only.", researchedOn],
  [6, 1837, "NeuroBell", "NeuroBell", "Cork", "LinkedIn band 2-10", "Likely <=25", "", "", "", "", "", "https://ie.linkedin.com/company/neurobell", "No public office line found", "No number", "Company and size verified; no public office line located.", researchedOn],
  [7, 810, "EAltra", "eAltra Limited", "Kilkenny", "Employee count not found", "Unverified", "", "Mobile only, excluded", 4, "Official public procurement profile", "https://www.etenders.gov.ie/epps/prepareViewCAOrganisation.do?id=149273", "https://www.etenders.gov.ie/epps/prepareViewCAOrganisation.do?id=149273", "Mobile-only result excluded", "Do not call", "A mobile was published in the procurement profile. It is intentionally omitted.", researchedOn],
  [8, 1891, "Novaerus", "Novaerus (Ireland) Limited", "Dublin", "Irish directory says small company; current ownership needs review", "Review ownership/size", "+353 1 907 2750", "Company international office line", 1, "Official partner portal", "https://partners.novaerus.com/", "https://www.solocheck.ie/Irish-Company/Novaerus-Ireland-Limited-509993", "Office line found", "Hold for NDD screening", "Number is published by Novaerus. Confirm that the Irish entity still fits the target profile.", researchedOn],
  [9, 1726, "Mirai Medical", "Mirai Medical", "Oranmore, Galway", "19 public employee profiles; LinkedIn band 11-50", "Likely <=25", "", "", "", "", "", "https://ie.linkedin.com/company/mirai-medical", "No public office line found", "No number", "Current public profile suggests about 19 employees, but no office line was found.", researchedOn],
  [10, 762, "DigiAcademy", "DigiAcademy Technology", "Dublin", "LinkedIn band 2-10", "Likely <=25", "", "", "", "", "", "https://ie.linkedin.com/company/digiacademy-technology", "No public office line found", "No number", "Public contact is email only.", researchedOn],
  [11, 168, "Altratech", "AltraTech Limited", "Cork", "Official company document says team of 17", "Likely <=25", "+353 21 475 7300", "Company office line", 1, "Official website", "https://www.altratech.com/", "https://altratech.com/wp-content/uploads/2026/01/About_Altratech.pdf", "Office line found", "Hold for NDD screening", "Strong match: official company address, telephone and a current team-size statement.", researchedOn],
  [12, 1955, "OneTouch Telecare", "OneTouch Health", "Galway", "LinkedIn band 51-200", "Out of scope >25", "+353 91 398 133", "Ireland company line", 1, "Official website", "https://www.onetouchhealth.net/contact/", "https://www.linkedin.com/company/onetouch-health/", "Office line found; size fails", "Do not prioritise", "Good phone data, but the current size band is outside this pilot's target.", researchedOn],
  [13, 2699, "Think Biosolution", "Think Biosolution Limited", "Dublin", "LinkedIn band 2-10", "Likely <=25", "", "Mobile only, excluded", 3, "Official company PDF / website", "https://www.thinkbiosolution.com/contact/", "https://ie.linkedin.com/company/thinkbiosolution", "Mobile-only result excluded", "Do not call", "Current official website has no office line. An older public company document contains a mobile, which is intentionally omitted.", researchedOn],
  [14, 1274, "Incereb", "Incereb Limited", "Dublin", "Irish sources say small / 0-9 employees", "Likely <=25", "+353 1 685 2245", "Company landline", 3, "Irish company directory", "https://www.vision-net.ie/Company-Info/Incereb-Limited-498694", "https://www.bizireland.com/incereb_1a-01-685-2245", "Office line found", "Hold for NDD screening", "Two secondary Irish sources agree on the number; the company appears to have been acquired, so confirm routing.", researchedOn],
  [15, 870, "Empeal", "Empeal", "Dublin", "Employee count not found", "Unverified", "", "Mobile/WhatsApp only, excluded", 1, "Official website", "https://empeal.com/company", "https://empeal.com/company", "Mobile-only result excluded", "Do not call", "Official site lists an overseas WhatsApp/mobile number, not an Irish office line.", researchedOn],
  [16, 1050, "Gasgon Medical", "Gasgon Medical", "Carrigaline, Cork", "Official team page shows four operating team members plus advisers", "Likely <=25", "+353 21 202 8204", "Company office line", 1, "Official website", "https://www.gasgonmedical.com/contact", "https://www.gasgonmedical.com/team-3", "Office line found", "Hold for NDD screening", "Strong match from the official contact page.", researchedOn],
  [17, 2866, "Vetex Medical", "VETEX Medical Ltd", "Galway", "4 public employee profiles; LinkedIn band 11-50", "Likely <=25", "+353 91 394 795", "Company landline", 4, "EUDAMED mirror", "https://beudamed.com/manufacturers/91ec2f60-460e-4ac8-9df9-8a6d5fa5352d", "https://ie.linkedin.com/company/vetex-medical-ltd", "Office line found", "Hold for NDD screening", "Medium confidence because the number comes from a registry mirror rather than the company's own website.", researchedOn],
  [18, 292, "AventaMed", "AventaMed DAC", "Cork", "Acquired by KARL STORZ", "Review ownership/size", "+353 21 492 8980", "Company office line", 1, "Official website", "https://aventamed.com/contact/", "https://companycheck.ie/company/532080", "Office line found", "Do not prioritise", "The Irish office line is current, but the company is no longer an independent startup.", researchedOn],
  [19, 1486, "Lifelet Medical", "Lifelet Medical Ltd", "Galway", "LinkedIn band 2-10; EI directory expected 12 in 2026", "Likely <=25", "", "Personal/mobile result excluded", 5, "Business-card directory", "", "https://www.linkedin.com/company/lifelet-medical", "Mobile-only result excluded", "Do not call", "A founder mobile appeared in a public business-card listing. It is intentionally omitted.", researchedOn],
  [20, 1788, "NUA Surgical", "NUA Surgical", "Galway", "Small startup; exact employee count not found", "Likely <=25", "", "", "", "", "", "https://nuasurgical.com/", "No public office line found", "No number", "Official website provides location and contact form but no telephone number.", researchedOn],
  [21, 1675, "Medytrak", "MediCareTags Limited trading as Medytrak", "Galway", "Small named team; exact employee count not found", "Likely <=25", "", "", "", "", "", "https://www.medytrak.com/aboutmedytrak", "No public office line found", "No number", "Official website provides email but no telephone number.", researchedOn],
  [22, 2073, "PatientMpower", "patientMpower", "Dublin", "LinkedIn band 11-50; exact count not established", "Uncertain 11-50", "+353 1 903 8558", "Ireland company line", 1, "Official website", "https://patientmpower.com/", "https://www.linkedin.com/company/patientmpower", "Office line found", "Hold for NDD screening", "Phone is current and official. Confirm employee count before treating it as a <=25 lead.", researchedOn],
  [23, 696, "Cushla Health Systems", "Cushla Health Systems Limited", "Dublin", "Employee count not found", "Unverified", "", "Mobile only, excluded", 2, "Google Play business listing", "https://play.google.com/store/apps/details?id=com.cushla.app", "https://cushla.io/", "Mobile-only result excluded", "Do not call", "Public listing exposes a mobile number. It is intentionally omitted.", researchedOn],
  [24, 406, "Bluedrop Medical", "Bluedrop Medical Ltd", "Galway", "Employee count not found", "Unverified", "", "US support line only", 1, "Official website", "https://bluedropmedical.com/provider-resources/", "https://bluedropmedical.com/company/", "No Irish office line found", "No number", "Official site gives an Irish address but only a US customer-support telephone number.", researchedOn],
  [25, 415, "Brace", "Brace Social / Brace", "Dublin", "LinkedIn band 2-10; EI directory expected 12 in 2026", "Likely <=25", "", "", "", "", "", "https://ie.linkedin.com/company/bracesocial", "No public office line found", "No number", "The similarly named brace.ie organisation is unrelated and was rejected as a false match.", researchedOn],
];

const wb = Workbook.create();
const summary = wb.worksheets.add("Summary");
const log = wb.worksheets.add("Research log");
summary.showGridLines = false;
log.showGridLines = false;
summary.tabColor = "#1F4E78";
log.tabColor = "#9EADBA";

summary.getRange("A2:H2").merge();
summary.getRange("A2").values = [["Irish startup phone pilot"]];
summary.getRange("A3:H3").merge();
summary.getRange("A3").values = [["25 semi-random Republic of Ireland leads from the BlueBridge pipeline, researched 15 September 2026"]];
summary.getRange("A5:B10").values = [
  ["Metric", "Result"],
  ["Companies reviewed", 25],
  ["Irish office/company numbers found", null],
  ["Numbers on likely <=25 leads", null],
  ["Mobile-only results excluded", null],
  ["Records not confirmed at <=25 employees", null],
];
summary.getRange("B7").formulas = [["=COUNTIFS('Research log'!$N$10:$N$34,\"Office line found\")+COUNTIFS('Research log'!$N$10:$N$34,\"Office line found; size fails\")"]];
summary.getRange("B8").formulas = [["=COUNTIFS('Research log'!$N$10:$N$34,\"Office line found\",'Research log'!$G$10:$G$34,\"Likely <=25\")"]];
summary.getRange("B9").formulas = [["=COUNTIFS('Research log'!$N$10:$N$34,\"Mobile-only result excluded\")"]];
summary.getRange("B10").formulas = [["=COUNTIFS('Research log'!$G$10:$G$34,\"<>Likely <=25\")"]];

summary.getRange("D5:H5").values = [["Company", "Office number", "Why it is here", "Source type", "Calling status"]];
const priorityRows = [13, 20, 23, 25, 26];
for (let i = 0; i < priorityRows.length; i++) {
  const dst = 6 + i;
  const src = priorityRows[i];
  summary.getRange(`D${dst}:H${dst}`).formulas = [[
    `='Research log'!D${src}`,
    `='Research log'!H${src}`,
    `='Research log'!F${src}`,
    `='Research log'!K${src}`,
    `='Research log'!O${src}`,
  ]];
}
summary.getRange("A12:H12").merge();
summary.getRange("A12").values = [["Interpretation"]];
summary.getRange("A13:H15").merge();
summary.getRange("A13").values = [["The useful result is five public company landlines attached to leads that look likely to have 25 employees or fewer. Every number remains on hold until the caller checks the current National Directory Database marketing preference and the company has not opted out directly. The pilot also found five mobile-only results, all omitted from this workbook."]];
summary.getRange("A17:H17").merge();
summary.getRange("A17").values = [["Sampling note"]];
summary.getRange("A18:H20").merge();
summary.getRange("A18").values = [["The source pool was Geography = Ireland and Persona = Early startup. A fixed random seed of 20260915 created the candidate order. Obvious headings, programmes, publishers and non-company records were rejected and replaced. Employee counts are public estimates, not payroll records."]];

const headers = ["Sample", "Pipeline row", "Pipeline company", "Verified company", "Irish location", "Size evidence", "Scope status", "Public office phone", "Number type", "Source priority", "Phone source class", "Phone source URL", "Identity / size source", "Research outcome", "Calling status", "Notes", "Researched on"];
log.getRange("A2:Q2").merge();
log.getRange("A2").values = [["Irish startup phone research log"]];
log.getRange("A3:Q3").merge();
log.getRange("A3").values = [["Public office and company landlines only. Mobile numbers are excluded."]];
log.getRange("A5:B8").values = [
  ["Pilot rule", "Value"],
  ["Geography", "Republic of Ireland"],
  ["Target size", "25 employees or fewer where public evidence exists"],
  ["Calling gate", "NDD screening and internal suppression check required"],
];
log.getRange("A9:Q9").values = [headers];
log.getRange("A10:Q34").values = rows;
log.getRange("Q10:Q34").format.numberFormat = "dd mmm yyyy";

const font = "Arial";
summary.getRange("A2:H20").format.font = { name: font, size: 10, color: "#1F2937" };
log.getRange("A2:Q34").format.font = { name: font, size: 10, color: "#1F2937" };
summary.getRange("A2").format.font = { name: font, size: 16, bold: true, color: "#1F2937" };
log.getRange("A2").format.font = { name: font, size: 16, bold: true, color: "#1F2937" };
summary.getRange("A3").format.font = { name: font, size: 10, italic: true, color: "#5B6573" };
log.getRange("A3").format.font = { name: font, size: 10, italic: true, color: "#5B6573" };
summary.getRange("A5:B5").format = { fill: "#1F4E78", font: { name: font, size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center" };
summary.getRange("D5:H5").format = { fill: "#1F4E78", font: { name: font, size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };
summary.getRange("D6:H10").format.wrapText = true;
summary.getRange("D6:H10").format.rowHeight = 34;
summary.getRange("A12:H12").format = { fill: "#D9E7F3", font: { name: font, size: 10, bold: true, color: "#1F2937" } };
summary.getRange("A17:H17").format = { fill: "#D9E7F3", font: { name: font, size: 10, bold: true, color: "#1F2937" } };
summary.getRange("A13:H15").format.wrapText = true;
summary.getRange("A18:H20").format.wrapText = true;
summary.getRange("A5:B10").format.borders = { preset: "outside", style: "thin", color: "#B8C2CC" };
summary.getRange("D5:H10").format.borders = { preset: "outside", style: "thin", color: "#B8C2CC" };
summary.getRange("B6:B10").format.horizontalAlignment = "right";

log.getRange("A5:B5").format = { fill: "#D9E7F3", font: { name: font, size: 10, bold: true, color: "#1F2937" } };
log.getRange("A9:Q9").format = { fill: "#1F4E78", font: { name: font, size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };
log.getRange("A10:Q34").format.verticalAlignment = "top";
log.getRange("F10:G34").format.wrapText = true;
log.getRange("N10:P34").format.wrapText = true;
log.getRange("A9:Q34").format.borders = { insideHorizontal: { style: "thin", color: "#E5E7EB" }, bottom: { style: "thin", color: "#B8C2CC" } };
log.getRange("G10:G34").conditionalFormats.add("containsText", { text: "Likely <=25", format: { fill: "#E7F4EA", font: { color: "#1F6B3A" } } });
log.getRange("G10:G34").conditionalFormats.add("containsText", { text: "Out of scope", format: { fill: "#FDE8E7", font: { color: "#A61B1B", bold: true } } });
log.getRange("O10:O34").conditionalFormats.add("containsText", { text: "Hold", format: { fill: "#FFF4CE", font: { color: "#7A5200", bold: true } } });
log.getRange("O10:O34").conditionalFormats.add("containsText", { text: "Do not", format: { fill: "#FDE8E7", font: { color: "#A61B1B", bold: true } } });

summary.getRange("A2:H20").format.verticalAlignment = "center";
summary.getRange("A2:H20").format.autofitRows();
log.getRange("A2:Q34").format.autofitRows();
log.getRange("A9:Q9").format.rowHeight = 32;
log.getRange("A10:Q34").format.rowHeight = 36;
summary.getRange("A:A").format.columnWidth = 31;
summary.getRange("B:B").format.columnWidth = 12;
summary.getRange("C:C").format.columnWidth = 3;
summary.getRange("D:D").format.columnWidth = 24;
summary.getRange("E:E").format.columnWidth = 20;
summary.getRange("F:F").format.columnWidth = 31;
summary.getRange("G:G").format.columnWidth = 42;
summary.getRange("H:H").format.columnWidth = 23;
log.getRange("A:A").format.columnWidth = 9;
log.getRange("B:B").format.columnWidth = 12;
log.getRange("C:D").format.columnWidth = 24;
log.getRange("E:E").format.columnWidth = 19;
log.getRange("F:F").format.columnWidth = 34;
log.getRange("G:G").format.columnWidth = 22;
log.getRange("H:H").format.columnWidth = 20;
log.getRange("I:I").format.columnWidth = 24;
log.getRange("J:J").format.columnWidth = 14;
log.getRange("K:K").format.columnWidth = 25;
log.getRange("L:M").format.columnWidth = 44;
log.getRange("N:O").format.columnWidth = 24;
log.getRange("P:P").format.columnWidth = 54;
log.getRange("Q:Q").format.columnWidth = 16;
log.freezePanes.freezeRows(9);
log.freezePanes.freezeColumns(4);

summary.tables.add("A5:B10", true, "PilotMetrics");
summary.tables.add("D5:H10", true, "PriorityNumbers");
log.tables.add("A9:Q34", true, "PhoneResearchLog");

wb.recalculate();
await fs.mkdir(outputDir, { recursive: true });
const summaryPreview = await wb.render({ sheetName: "Summary", autoCrop: "all", scale: 1, format: "png" });
await fs.writeFile(`${outputDir}/summary_preview.png`, new Uint8Array(await summaryPreview.arrayBuffer()));
const logPreview = await wb.render({ sheetName: "Research log", range: "A1:Q18", scale: 1, format: "png" });
await fs.writeFile(`${outputDir}/log_preview.png`, new Uint8Array(await logPreview.arrayBuffer()));

const check = await wb.inspect({ kind: "table", range: "Summary!A1:H20", include: "values,formulas", tableMaxRows: 25, tableMaxCols: 10, maxChars: 8000 });
console.log(check.ndjson);
const errors = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan" });
console.log(errors.ndjson);
const output = await SpreadsheetFile.exportXlsx(wb);
await output.save(outputPath);
const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const savedCheck = await saved.inspect({ kind: "table", range: "Summary!A5:H10", include: "values,formulas", tableMaxRows: 10, tableMaxCols: 10, maxChars: 5000 });
console.log(savedCheck.ndjson);
console.log(`OUTPUT=${outputPath}`);
