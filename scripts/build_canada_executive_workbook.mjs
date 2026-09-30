import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import os from "node:os";

let artifact;
try {
  artifact = createRequire(import.meta.url)("@oai/artifact-tool");
} catch {
  const runtime = path.join(os.homedir(), ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/package.json");
  artifact = createRequire(runtime)("@oai/artifact-tool");
}
const { FileBlob, SpreadsheetFile } = artifact;

const source = path.resolve(process.argv[2] || "outputs/canada_company_enrichment_wp6_2026-07-30/Canada_Company_Enrichment_Work_Package_6.xlsx");
const researchDir = path.resolve(process.argv[3] || "outputs/canada_executive_research");
const destination = path.resolve(process.argv[4] || "outputs/canada_executive_research/Canada_Company_Enrichment_With_Executive_Contacts.xlsx");

let companies;
try {
  companies = JSON.parse(await fs.readFile(path.join(researchDir, "companies.json"), "utf8"));
} catch (error) {
  if (error.code !== "ENOENT") throw error;
  companies = JSON.parse(await fs.readFile(path.join(researchDir, "company_inputs.json"), "utf8"));
}
const selected = JSON.parse(await fs.readFile(path.join(researchDir, "selected.json"), "utf8"));
const contactsByRow = new Map();
for (const contact of selected) {
  if (!contactsByRow.has(contact.row_id)) contactsByRow.set(contact.row_id, []);
  contactsByRow.get(contact.row_id).push(contact);
}

const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
if (wb.worksheets.items.some(sheet => sheet.name === "Executive Contacts")) {
  throw new Error("Executive Contacts already exists in the source workbook");
}
const sheet = wb.worksheets.add("Executive Contacts");
sheet.showGridLines = false;
sheet.tabColor = "#236D7A";

const headers = ["Company", "Source row", "Research ID", "Listed website", "Identity", "Priority", "Name", "Exact title", "LinkedIn profile", "Business email", "Phone", "Role source", "LinkedIn source", "Email source", "Phone source", "Contact status", "Research status", "Checked at", "Issues"];
const rows = [];
for (const company of companies) {
  const contacts = contactsByRow.get(company.row_id) || [];
  if (!contacts.length) {
    const contactStatus = company.status === "not_started" ? "Not researched" : company.status === "access_blocked" ? "Access blocked" : "No verified contact";
    rows.push([company.company, company.source_row, company.row_id, company.website, company.identity_status, "", "", "", "", "", "", "", "", "", "", contactStatus, company.status, "", (company.errors || []).slice(0, 2).join("; ")]);
    continue;
  }
  for (const [index, contact] of contacts.entries()) {
    const researchStatus = ["automated_official_team_card", "luna_found_official_team_card", "luna_official_role_and_linkedin_company", "luna_cited_official_role_and_exact_profile"].includes(contact.reason) ? "Auto verified" : "Reviewed";
    rows.push([company.company, company.source_row, company.row_id, company.website, "verified", index + 1, contact.name, contact.title, contact.linkedin_url, contact.email, contact.phone, contact.role_url, contact.linkedin_evidence_url, contact.email_evidence_url, contact.phone_evidence_url, contact.email ? "Email sourced" : "Email not found", researchStatus, contact.checked_at, contact.reason]);
  }
}

sheet.getRange("A1:S1").values = [["Executive contacts research", ...Array(18).fill("")]];
sheet.getRange("A2:S2").values = [["One row per selected executive; companies without accepted contacts have a status row.", ...Array(18).fill("")]];
sheet.getRange("A4:D5").values = [["Workbook companies", companies.length, "Pilot verified contacts", selected.length], ["Contacts with email", selected.filter(c => c.email).length, "Pilot companies with contacts", contactsByRow.size]];
sheet.getRange("A7:S7").values = [headers];
if (rows.length) sheet.getRangeByIndexes(7, 0, rows.length, headers.length).values = rows;
sheet.getRange("A1:S1").format = { fill: "#173F53", font: { name: "Aptos", size: 16, bold: true, color: "#FFFFFF" } };
sheet.getRange("A2:S2").format.font = { name: "Aptos", size: 10, color: "#516579" };
sheet.getRange("A7:S7").format = { fill: "#236D7A", font: { name: "Aptos", size: 10, bold: true, color: "#FFFFFF" }, rowHeight: 28 };
sheet.getRange(`A8:S${7 + rows.length}`).format.font = { name: "Aptos", size: 10, color: "#1C3140" };
for (const [col, width] of Object.entries({ A: 28, B: 12, C: 21, D: 31, E: 18, F: 10, G: 23, H: 27, I: 41, J: 31, K: 20, L: 42, M: 42, N: 42, O: 42, P: 22, Q: 18, R: 16, S: 38 })) {
  sheet.getRange(`${col}:${col}`).format.columnWidth = width;
}
sheet.freezePanes.freezeRows(7);
sheet.tables.add(`A7:S${7 + rows.length}`, true, "ExecutiveContacts");

wb.recalculate();
const preview = await wb.render({ sheetName: "Executive Contacts", range: "A1:J12", scale: 1, format: "png" });
await fs.mkdir(path.dirname(destination), { recursive: true });
await fs.writeFile(path.join(researchDir, "executive_contacts_preview.png"), new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(wb);
await output.save(destination);
console.log(JSON.stringify({ destination, companies: companies.length, selected: selected.length, rows: rows.length }));
