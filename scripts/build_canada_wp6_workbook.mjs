import fs from "node:fs/promises";
import path from "node:path";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

// Reproducible baseline builder for the audited 2026-07-30 WP6 workbook.
// Its V1 scoring rules are intentionally frozen for comparison only. A new
// release must use the Scoring V2 outputs defined in CANADA_SCORING_V2_SPEC.md.

const repo = path.resolve(process.cwd());
const outDir = path.resolve(process.argv[2] || "outputs/canada_company_enrichment_wp6_current");
const asOf = new Date("2026-07-30T00:00:00Z");
await fs.mkdir(outDir, { recursive: true });

async function readJson(rel) {
  return JSON.parse(await fs.readFile(path.join(repo, rel), "utf8"));
}

function parseCsv(text) {
  const rows = [];
  let row = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i], next = text[i + 1];
    if (quoted) {
      if (ch === '"' && next === '"') { field += '"'; i++; }
      else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { row.push(field); field = ""; }
    else if (ch === "\n") { row.push(field.replace(/\r$/, "")); rows.push(row); row = []; field = ""; }
    else field += ch;
  }
  if (field.length || row.length) { row.push(field.replace(/\r$/, "")); rows.push(row); }
  const headers = (rows.shift() || []).map(h => h.replace(/^\uFEFF/, ""));
  return rows.filter(r => r.some(v => v !== "")).map(r => Object.fromEntries(headers.map((h, i) => [h, r[i] ?? ""])));
}

function dateVal(v) {
  if (!v || v === "Not stated") return null;
  const d = new Date(`${String(v).slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

function latest(list, fields = ["event_date", "evidence_date", "captured_at"]) {
  return [...list].sort((a, b) => {
    const av = fields.map(k => a[k]).find(Boolean) || "";
    const bv = fields.map(k => b[k]).find(Boolean) || "";
    return String(bv).localeCompare(String(av));
  })[0] || null;
}

function groupBy(items, key = "company_id") {
  const map = new Map();
  for (const item of items) {
    const k = item[key];
    if (!map.has(k)) map.set(k, []);
    map.get(k).push(item);
  }
  return map;
}

function joinList(v) {
  return Array.isArray(v) ? v.filter(Boolean).join("; ") : (v || "");
}

function truncate(v, n = 500) {
  const s = String(v || "").replace(/\s+/g, " ").trim();
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

const canonical = (await readJson("outputs/canada_company_identity_2026-07-27/canonical_companies.json")).companies;
const provenance = (await readJson("outputs/canada_company_identity_2026-07-27/source_provenance.json")).records;
const hiringDoc = await readJson("outputs/canada_hiring_wp2_final_2026-07-28/canonical_hiring_evidence.json");
const hiringCompanies = (await readJson("outputs/canada_hiring_wp2_final_2026-07-28/canonical_companies_hiring_wp2_complete.json")).companies;
const fundingDoc = await readJson("outputs/canada_funding_2026-07-28/funding_events.json");
const backingDoc = await readJson("outputs/canada_funding_2026-07-28/funding_backing_evidence.json");
const fundingCompanies = (await readJson("outputs/canada_funding_2026-07-28/canonical_companies_with_funding.json")).companies;
const regulatoryDoc = await readJson("outputs/canada_regulatory_2026-07-28/regulatory_evidence.json");
const regulatoryCompanies = (await readJson("outputs/canada_regulatory_2026-07-28/canonical_companies_regulatory.json")).companies;
const productDoc = await readJson("outputs/canada_product_news_2026-07-30/product_profiles.json");
const productCompleteness = (await readJson("outputs/canada_product_news_2026-07-30/product_news_completeness.json")).companies;
const verifiedDoc = await readJson("outputs/canada_product_news_2026-07-30/recent_verification/verified_recent_events.json");
const duplicateReview = parseCsv(await fs.readFile(path.join(repo, "outputs/canada_company_identity_2026-07-27/duplicate_review.csv"), "utf8"));
const ambiguousReview = parseCsv(await fs.readFile(path.join(repo, "outputs/canada_company_identity_2026-07-27/ambiguous_name_review.csv"), "utf8"));

const hiring = hiringDoc.records;
const fundingEvents = fundingDoc.events;
const backing = backingDoc.records;
const regulatory = regulatoryDoc.records;
const products = productDoc.profiles;
const productNews = verifiedDoc.events;

const byHiring = groupBy(hiring);
const byFunding = groupBy(fundingEvents);
const byBacking = groupBy(backing);
const byReg = groupBy(regulatory);
const byProduct = groupBy(products);
const byNews = groupBy(productNews);
const byProv = groupBy(provenance);
const hComp = new Map(hiringCompanies.map(c => [c.company_id, c.completeness?.hiring || {}]));
const fComp = new Map(fundingCompanies.map(c => [c.company_id, c.completeness?.funding || {}]));
const rComp = new Map(regulatoryCompanies.map(c => [c.company_id, c.completeness?.regulatory || {}]));
const pComp = new Map(productCompleteness.map(c => [c.company_id, c]));

function signalFamily(roles) {
  const families = [...new Set(roles.map(r => r.role_family).filter(Boolean))];
  return families.length ? families.join("; ") : "";
}

function newestDate(items, fields) {
  const d = latest(items, fields);
  return d ? dateVal(fields.map(k => d[k]).find(Boolean)) : null;
}

function jsComponents(c) {
  const hs = byHiring.get(c.company_id) || [];
  const fe = byFunding.get(c.company_id) || [];
  const be = byBacking.get(c.company_id) || [];
  const re = byReg.get(c.company_id) || [];
  const pe = byNews.get(c.company_id) || [];
  const cat = `${c.product_category || ""} ${c.product_summary || ""}`.toLowerCase();
  let fit = /medical device|diagnostic/.test(cat) ? 25 : /samd/.test(cat) ? 23 : /digital health/.test(cat) ? 18 : /platform|biotech/.test(cat) ? 15 : /therapeutic|pharma/.test(cat) ? 8 : 5;
  let commercial = Math.min(20, hs.length * 4 + (pe.length ? 4 : 0) + (re.length ? 4 : 0));
  const lf = latest(fe);
  let funding = 0;
  if (lf) {
    const eventDate = dateVal(lf.event_date);
    const recentCutoff = new Date(asOf); recentCutoff.setUTCDate(recentCutoff.getUTCDate() - 730);
    const olderCutoff = new Date(asOf); olderCutoff.setUTCDate(olderCutoff.getUTCDate() - 1825);
    funding += eventDate >= recentCutoff ? 14 : eventDate >= olderCutoff ? 9 : 5;
    const amt = Number(lf.amount_cad || 0);
    funding += amt >= 5_000_000 ? 6 : amt >= 500_000 ? 3 : 0;
  } else if (be.length) funding = 5;
  funding = Math.min(20, funding + (be.length && lf ? 2 : 0));
  const band = String(c.employee_band || "").toLowerCase();
  let stage = /20|50|100|200/.test(band) && !/500/.test(band) ? 15 : /201|500/.test(band) ? 12 : /1-19|early|startup/.test(`${band} ${c.company_stage || ""}`.toLowerCase()) ? 10 : 8;
  const milestone = Math.min(10, (re.length ? 6 : 0) + (pe.length ? 4 : 0));
  const quality = Math.min(5, (re.length ? 2 : 0) + (lf ? 1 : 0) + (hs.length ? 1 : 0) + ((byProv.get(c.company_id) || []).length ? 1 : 0));
  const canada = /headquarters|hq|canadian/i.test(c.canada_relationship || "") ? 5 : c.province ? 4 : 2;
  let penalty = 0;
  const all = `${cat} ${c.company_stage || ""} ${c.employee_band || ""}`;
  if (/acquired|inactive/.test(all)) penalty += 12;
  if (/wellness|consultancy|consulting/.test(all)) penalty += 8;
  if (/500\+|501|1000/.test(all)) penalty += 8;
  if (/therapeutic|pharma/.test(cat) && !/device|diagnostic|samd|platform/.test(cat)) penalty += 8;
  return { fit, commercial, funding, stage, milestone, quality, canada, penalty, total: Math.max(0, fit + commercial + funding + stage + milestone + quality + canada - penalty) };
}

const companyModel = canonical.map(c => {
  const hs = byHiring.get(c.company_id) || [];
  const fe = byFunding.get(c.company_id) || [];
  const be = byBacking.get(c.company_id) || [];
  const re = byReg.get(c.company_id) || [];
  const pp = byProduct.get(c.company_id) || [];
  const pn = byNews.get(c.company_id) || [];
  const pv = byProv.get(c.company_id) || [];
  const lf = latest(fe);
  const lm = latest(pn);
  const lr = latest(re, ["decision_or_start_date", "evidence_date", "captured_at"]);
  const lprod = latest(pp, ["evidence_date", "captured_at"]);
  const dates = [
    newestDate(hs, ["evidence_date", "captured_at"]),
    newestDate(fe, ["event_date", "captured_at"]),
    newestDate(be, ["evidence_date", "captured_at"]),
    newestDate(re, ["decision_or_start_date", "evidence_date", "captured_at"]),
    newestDate(pp, ["evidence_date", "captured_at"]),
    newestDate(pn, ["event_date", "evidence_date", "captured_at"]),
    newestDate(pv, ["snapshot_date", "captured_at"]),
  ].filter(Boolean).sort((a, b) => b - a);
  const pc = pComp.get(c.company_id) || {};
  const statuses = {
    hiring: hComp.get(c.company_id) || { status: "not_run" },
    funding: fComp.get(c.company_id) || { status: "not_run" },
    regulatory: rComp.get(c.company_id) || { status: "not_run" },
    product: pc.product_development || { status: "not_run" },
    news: pc.news || { status: "not_run" },
  };
  const unresolved = Object.entries(statuses).filter(([, v]) => !["complete_matches", "complete_zero"].includes(v.status || "")).map(([k, v]) => `${k}:${v.status || "not_run"}`);
  const evidenceUrl = lm?.evidence_url || lr?.evidence_url || lf?.evidence_url || hs[0]?.evidence_url || lprod?.evidence_url || pv[0]?.evidence_url || "";
  const funders = [...new Set([...fe.flatMap(x => x.investors_or_funders || []), ...be.map(x => x.backer).filter(Boolean)])];
  return {
    c, hs, fe, be, re, pp, pn, pv, lf, lm, latestEvidence: dates[0] || null, statuses,
    hiringSignal: signalFamily(hs),
    funders,
    regulatorySummary: re.length ? `${re.length} record(s): ${[...new Set(re.map(x => `${x.authority} ${x.record_type}`.trim()))].slice(0, 4).join("; ")}` : "",
    milestone: lm ? `${lm.event_type}: ${lm.title}` : lprod ? `${lprod.development_stage || "stage unknown"}: ${lprod.product_summary}` : "",
    unresolved: unresolved.join("; "),
    evidenceUrl,
    js: jsComponents(c),
  };
}).sort((a, b) => b.js.total - a.js.total || a.c.company_name.localeCompare(b.c.company_name));

const wb = Workbook.create();
const sheetNames = ["Top Prospects", "Companies", "Source Provenance", "Hiring Evidence", "Funding Events", "Regulatory Evidence", "Product & News Events", "Alias Review", "Incomplete & Blocked Sources", "Run Summary", "Methodology"];
const sheets = Object.fromEntries(sheetNames.map(n => [n, wb.worksheets.add(n)]));

const navy = "#17324D", blue = "#2563EB", teal = "#0F766E", pale = "#E8F1F8", paleGreen = "#E7F6EF", paleAmber = "#FFF4D6", paleRed = "#FCE8E6", gray = "#667085", light = "#F7F9FC", white = "#FFFFFF";

function title(sheet, range, text, subtitle = "") {
  range.merge();
  range.values = [[text]];
  range.format = { fill: navy, font: { bold: true, color: white, size: 18 }, rowHeight: 34, verticalAlignment: "center" };
  if (subtitle) {
    const below = range.offset(1, 0).resize(1, range.columnCount);
    below.merge();
    below.values = [[subtitle]];
    below.format = { fill: pale, font: { color: navy, italic: true }, rowHeight: 26, verticalAlignment: "center" };
  }
  sheet.showGridLines = false;
}

function formatHeader(range) {
  range.format = { fill: navy, font: { bold: true, color: white }, wrapText: true, verticalAlignment: "center", rowHeight: 30, borders: { preset: "inside", style: "thin", color: "#B9C7D5" } };
}

function addTable(sheet, range, name, style = "TableStyleMedium2") {
  const t = sheet.tables.add(range, true, name);
  t.style = style;
  t.showFilterButton = true;
  return t;
}

// Methodology first so cross-sheet formulas have valid targets.
const meth = sheets["Methodology"];
title(meth, meth.getRange("A1:H1"), "Canada Company Enrichment — Scoring Methodology", "As-of date, component rules, completeness definitions, and refresh policy");
meth.getRange("A3:B4").values = [["Model as-of date", asOf], ["Maximum score", 100]];
meth.getRange("B3").format.numberFormat = "yyyy-mm-dd";
meth.getRange("A3:A4").format = { fill: pale, font: { bold: true, color: navy } };
meth.getRange("A6:D14").values = [
  ["Dimension", "Weight", "Workbook implementation", "Evidence used"],
  ["Medtech / regulated-product fit", 25, "Category and product-summary classification", "Canonical product category / summary"],
  ["Commercial intent", 20, "Open relevant roles plus verified regulatory and product/news activity", "Official open roles; verified records/events"],
  ["Funding and ability to buy", 20, "Recency, disclosed amount, and institutional backing", "Dated funding events; official portfolios"],
  ["Stage / size fit", 15, "Employee band and company stage; unknown remains neutral", "Canonical employee band / stage"],
  ["Product/regulatory milestone", 10, "Regulator records and verified product-development events", "Regulatory and product/news evidence"],
  ["Source quality", 5, "Regulator, official funding, official hiring, and provenance coverage", "Supporting evidence tabs"],
  ["Canada relevance", 5, "Canadian HQ/relationship and Canadian location", "Canonical identity fields"],
  ["Penalty", 0, "Acquired/inactive, wellness/consulting, very large, or pharma-only without relevant platform", "Canonical stage, size, category, summary"],
];
formatHeader(meth.getRange("A6:D6"));
addTable(meth, "A6:D14", "ScoringMethodology", "TableStyleMedium2");
meth.getRange("A16:D22").values = [
  ["Completeness status", "Meaning", "Treatment in scores", "Presentation"],
  ["complete_matches", "Source checked and accepted evidence found", "Evidence may contribute", "Green"],
  ["complete_zero", "Source checked; no qualifying evidence found", "True zero for that source", "Green"],
  ["manual_review", "Candidate evidence requires identity/manual review", "Does not contribute", "Amber"],
  ["blocked", "Source could not be checked", "Never treated as zero", "Red"],
  ["no_source", "No official route/source available", "Never treated as zero", "Amber"],
  ["not_run", "Coverage not yet attempted", "Never treated as zero", "Grey"],
];
formatHeader(meth.getRange("A16:D16"));
addTable(meth, "A16:D22", "CompletenessDefinitions", "TableStyleMedium4");
meth.getRange("A24:C30").values = [
  ["Track", "Default cadence", "Priority-company cadence"],
  ["Hiring", "Weekly", "Weekly"],
  ["Funding", "Monthly", "Weekly news check"],
  ["Regulatory", "Monthly", "Weekly after known submission/launch"],
  ["Clinical trials", "Monthly", "Weekly for active trials"],
  ["Product development", "Monthly", "Weekly news check"],
  ["General news", "Monthly", "Weekly"],
];
formatHeader(meth.getRange("A24:C24"));
addTable(meth, "A24:C30", "RefreshPolicy", "TableStyleMedium9");
meth.getRange("A32:H34").merge();
meth.getRange("A32").values = [["Important: the score is a transparent prioritisation aid, not a clinical, regulatory, or investment conclusion. Missing or blocked coverage is shown separately and is not silently converted to a zero. Funding remains incomplete because company/investor announcement ingestion is outstanding; product/news coverage is currently the reviewed top-50 pass."]];
meth.getRange("A32:H34").format = { fill: paleAmber, font: { color: "#7A4E00" }, wrapText: true, verticalAlignment: "center", borders: { preset: "outside", style: "thin", color: "#E5B83F" } };
meth.getRange("A:D").format.columnWidth = 22;
meth.getRange("C:C").format.columnWidth = 42;
meth.getRange("D:D").format.columnWidth = 35;
meth.getRange("A7:D14").format.wrapText = true;
meth.getRange("A7:D14").format.rowHeight = 34;
meth.getRange("A17:D22").format.wrapText = true;
meth.getRange("A17:D22").format.rowHeight = 30;
meth.freezePanes.freezeRows(2);

// Companies
const comp = sheets["Companies"];
const compHeaders = ["Rank", "Company", "Website", "City", "Province", "Canada Relationship", "Product Category", "Product Summary", "Employee Band", "Company Stage", "Open Relevant Roles", "Strongest Hiring Signal", "Latest Funding Date", "Latest Funding Amount (CAD)", "Latest Funding Stage", "Funders / Backers", "Regulatory Records", "Regulatory Summary", "Latest Product / News Date", "Latest Product / News", "Source Count", "Latest Evidence Date", "Evidence Age (days)", "Freshness", "Hiring Completeness", "Funding Completeness", "Regulatory Completeness", "Product Completeness", "News Completeness", "Unresolved Flags", "Fit (25)", "Commercial Intent (20)", "Funding (20)", "Stage / Size (15)", "Milestone (10)", "Source Quality (5)", "Canada Relevance (5)", "Penalty", "Priority Score", "Priority Band", "Review Status", "Primary Evidence URL"];
const compData = companyModel.map((m, i) => [
  i + 1, m.c.company_name, m.c.website || "", m.c.city || "", m.c.province || "", m.c.canada_relationship || "",
  m.c.product_category || "", truncate(m.c.product_summary, 650), m.c.employee_band || "unknown", m.c.company_stage || "unknown",
  m.hs.length, m.hiringSignal, dateVal(m.lf?.event_date), Number(m.lf?.amount_cad || 0) || null, m.lf?.stage || "",
  joinList(m.funders), m.re.length, truncate(m.regulatorySummary, 450), dateVal(m.lm?.event_date || latest(m.pp, ["evidence_date", "captured_at"])?.evidence_date), truncate(m.milestone, 650),
  m.pv.length, m.latestEvidence, null, null,
  m.statuses.hiring.status || "not_run", m.statuses.funding.status || "not_run", m.statuses.regulatory.status || "not_run", m.statuses.product.status || "not_run", m.statuses.news.status || "not_run",
  m.unresolved, null, null, null, null, null, null, null, null, null, null, i < 50 ? "Needs review" : "Not prioritized", m.evidenceUrl
]);
comp.getRangeByIndexes(0, 0, 1, compHeaders.length).values = [compHeaders];
comp.getRangeByIndexes(1, 0, compData.length, compHeaders.length).values = compData;
const lastComp = compData.length + 1;
for (let r = 2; r <= lastComp; r++) {
  comp.getRange(`W${r}`).formulas = [[`='Methodology'!$B$3-V${r}`]];
  comp.getRange(`X${r}`).formulas = [[`=IF(V${r}="","Unknown",IF(W${r}<=30,"Current",IF(W${r}<=90,"Monitor","Stale")))`]];
  comp.getRange(`AE${r}`).formulas = [[`=IF(OR(ISNUMBER(SEARCH("medical device",G${r}&H${r})),ISNUMBER(SEARCH("diagnostic",G${r}&H${r}))),25,IF(ISNUMBER(SEARCH("samd",G${r}&H${r})),23,IF(ISNUMBER(SEARCH("digital health",G${r}&H${r})),18,IF(OR(ISNUMBER(SEARCH("platform",G${r}&H${r})),ISNUMBER(SEARCH("biotech",G${r}&H${r}))),15,IF(OR(ISNUMBER(SEARCH("therapeutic",G${r}&H${r})),ISNUMBER(SEARCH("pharma",G${r}&H${r}))),8,5)))))`]];
  comp.getRange(`AF${r}`).formulas = [[`=MIN(20,K${r}*4+IF(S${r}<>"",4,0)+IF(Q${r}>0,4,0))`]];
  comp.getRange(`AG${r}`).formulas = [[`=MIN(20,IF(M${r}<>"",IF(M${r}>='Methodology'!$B$3-730,14,IF(M${r}>='Methodology'!$B$3-1825,9,5))+IF(N${r}>=5000000,6,IF(N${r}>=500000,3,0)),IF(P${r}<>"",5,0))+IF(AND(M${r}<>"",P${r}<>""),2,0))`]];
  comp.getRange(`AH${r}`).formulas = [[`=IF(AND(OR(ISNUMBER(SEARCH("20",I${r})),ISNUMBER(SEARCH("50",I${r})),ISNUMBER(SEARCH("100",I${r})),ISNUMBER(SEARCH("200",I${r}))),NOT(ISNUMBER(SEARCH("500",I${r})))),15,IF(OR(ISNUMBER(SEARCH("201",I${r})),ISNUMBER(SEARCH("500",I${r}))),12,IF(OR(ISNUMBER(SEARCH("1-19",I${r})),ISNUMBER(SEARCH("early",J${r})),ISNUMBER(SEARCH("startup",J${r}))),10,8)))`]];
  comp.getRange(`AI${r}`).formulas = [[`=MIN(10,IF(Q${r}>0,6,0)+IF(S${r}<>"",4,0))`]];
  comp.getRange(`AJ${r}`).formulas = [[`=MIN(5,IF(Q${r}>0,2,0)+IF(M${r}<>"",1,0)+IF(K${r}>0,1,0)+IF(U${r}>0,1,0))`]];
  comp.getRange(`AK${r}`).formulas = [[`=IF(OR(ISNUMBER(SEARCH("headquarters",F${r})),ISNUMBER(SEARCH("canadian",F${r})),ISNUMBER(SEARCH(" hq",F${r}))),5,IF(E${r}<>"",4,2))`]];
  comp.getRange(`AL${r}`).formulas = [[`=IF(OR(ISNUMBER(SEARCH("acquired",H${r}&J${r})),ISNUMBER(SEARCH("inactive",H${r}&J${r}))),12,0)+IF(OR(ISNUMBER(SEARCH("wellness",G${r}&H${r})),ISNUMBER(SEARCH("consult",G${r}&H${r}))),8,0)+IF(OR(ISNUMBER(SEARCH("500+",I${r})),ISNUMBER(SEARCH("1000",I${r}))),8,0)+IF(AND(OR(ISNUMBER(SEARCH("therapeutic",G${r}&H${r})),ISNUMBER(SEARCH("pharma",G${r}&H${r}))),NOT(OR(ISNUMBER(SEARCH("device",G${r}&H${r})),ISNUMBER(SEARCH("diagnostic",G${r}&H${r})),ISNUMBER(SEARCH("samd",G${r}&H${r})),ISNUMBER(SEARCH("platform",G${r}&H${r}))))),8,0)`]];
  comp.getRange(`AM${r}`).formulas = [[`=MAX(0,SUM(AE${r}:AK${r})-AL${r})`]];
  comp.getRange(`AN${r}`).formulas = [[`=IF(AM${r}>=70,"Tier A",IF(AM${r}>=55,"Tier B",IF(AM${r}>=40,"Tier C","Longlist")))`]];
}
formatHeader(comp.getRange(`A1:AP1`));
addTable(comp, `A1:AP${lastComp}`, "CompaniesTable", "TableStyleMedium2");
comp.freezePanes.freezeRows(1);
comp.freezePanes.freezeColumns(2);
comp.showGridLines = false;
comp.getRange(`M2:M${lastComp}`).format.numberFormat = "yyyy-mm-dd";
comp.getRange(`S2:S${lastComp}`).format.numberFormat = "yyyy-mm-dd";
comp.getRange(`V2:V${lastComp}`).format.numberFormat = "yyyy-mm-dd";
comp.getRange(`N2:N${lastComp}`).format.numberFormat = '"$"#,##0';
comp.getRange(`A2:A${lastComp}`).format.numberFormat = "0";
comp.getRange(`K2:K${lastComp}`).format.numberFormat = "0";
comp.getRange(`Q2:Q${lastComp}`).format.numberFormat = "0";
comp.getRange(`U2:U${lastComp}`).format.numberFormat = "0";
comp.getRange(`W2:W${lastComp}`).format.numberFormat = "0";
comp.getRange(`AE2:AM${lastComp}`).format.numberFormat = "0";
comp.getRange(`AO2:AO${lastComp}`).dataValidation = { rule: { type: "list", values: ["Needs review", "Reviewed—pursue", "Reviewed—hold", "Reviewed—exclude", "Not prioritized"] } };
comp.getRange(`AM2:AM${lastComp}`).conditionalFormats.add("colorScale", { thresholds: ["min", "50%", "max"], colors: ["#FEE2E2", "#FEF3C7", "#DCFCE7"] });
for (const col of ["Y", "Z", "AA", "AB", "AC"]) {
  comp.getRange(`${col}2:${col}${lastComp}`).conditionalFormats.add("containsText", { text: "complete", format: { fill: paleGreen, font: { color: "#166534" } } });
  comp.getRange(`${col}2:${col}${lastComp}`).conditionalFormats.add("containsText", { text: "blocked", format: { fill: paleRed, font: { color: "#991B1B" } } });
  comp.getRange(`${col}2:${col}${lastComp}`).conditionalFormats.add("containsText", { text: "review", format: { fill: paleAmber, font: { color: "#854D0E" } } });
}
const widths = { A: 7, B: 24, C: 30, D: 16, E: 15, F: 22, G: 18, H: 48, I: 14, J: 15, K: 10, L: 25, M: 14, N: 17, O: 14, P: 34, Q: 11, R: 38, S: 14, T: 48, U: 10, V: 14, W: 11, X: 12, Y: 16, Z: 16, AA: 16, AB: 16, AC: 16, AD: 35, AE: 10, AF: 12, AG: 10, AH: 11, AI: 10, AJ: 11, AK: 12, AL: 9, AM: 11, AN: 12, AO: 17, AP: 38 };
for (const [col, w] of Object.entries(widths)) comp.getRange(`${col}:${col}`).format.columnWidth = w;
comp.getRange(`H2:H${lastComp}`).format.wrapText = true;
comp.getRange(`R2:R${lastComp}`).format.wrapText = true;
comp.getRange(`T2:T${lastComp}`).format.wrapText = true;

// Top 50 presentation sheet.
const top = sheets["Top Prospects"];
title(top, top.getRange("A1:P1"), "Top 50 Canadian Prospects", "Formula-linked review queue; edit the yellow workflow cells and filter by evidence, completeness, or priority");
top.getRange("A4:P4").values = [["Rank", "Company", "Score", "Band", "Product Category", "Why now", "Open Roles", "Latest Funding", "Regulatory Signal", "Latest Milestone", "Completeness Gaps", "Review Status", "Owner", "Next Action", "Evidence URL", "Company Row"]];
for (let i = 0; i < 50; i++) {
  const tr = i + 5, cr = i + 2;
  top.getRange(`A${tr}:K${tr}`).formulas = [[
    `='Companies'!A${cr}`, `='Companies'!B${cr}`, `='Companies'!AM${cr}`, `='Companies'!AN${cr}`, `='Companies'!G${cr}`,
    `=IF('Companies'!K${cr}>0,"Hiring: "&'Companies'!L${cr},IF('Companies'!S${cr}<>"","Milestone: "&'Companies'!T${cr},IF('Companies'!M${cr}<>"","Funding signal","Evidence-led priority")))`,
    `='Companies'!K${cr}`, `=IF('Companies'!M${cr}="","",TEXT('Companies'!M${cr},"yyyy-mm-dd")&" | "&'Companies'!O${cr}&" | "&TEXT('Companies'!N${cr},"$#,##0"))`,
    `='Companies'!R${cr}`, `='Companies'!T${cr}`, `='Companies'!AD${cr}`
  ]];
  top.getRange(`L${tr}:N${tr}`).values = [["Needs review", "", ""]];
  top.getRange(`O${tr}:P${tr}`).formulas = [[`='Companies'!AP${cr}`, `=ROW('Companies'!A${cr})`]];
}
formatHeader(top.getRange("A4:P4"));
addTable(top, "A4:P54", "TopProspectsTable", "TableStyleMedium2");
top.freezePanes.freezeRows(4);
top.freezePanes.freezeColumns(2);
top.showGridLines = false;
top.getRange("C5:C54").format.numberFormat = "0";
top.getRange("G5:G54").format.numberFormat = "0";
top.getRange("L5:L54").dataValidation = { rule: { type: "list", values: ["Needs review", "Reviewed—pursue", "Reviewed—hold", "Reviewed—exclude"] } };
top.getRange("L5:N54").format.fill = paleAmber;
top.getRange("C5:C54").conditionalFormats.add("colorScale", { thresholds: ["min", "50%", "max"], colors: ["#FEE2E2", "#FEF3C7", "#DCFCE7"] });
const topWidths = [7, 24, 9, 10, 18, 36, 10, 28, 34, 42, 36, 18, 16, 30, 38, 12];
for (let i = 0; i < topWidths.length; i++) top.getRangeByIndexes(0, i, 54, 1).format.columnWidth = topWidths[i];
top.getRange("F5:K54").format.wrapText = true;
top.getRange("A:P").format.verticalAlignment = "top";

function makeEvidenceSheet(name, headers, rows, tableName, dateCols = [], currencyCols = []) {
  const s = sheets[name];
  s.getRangeByIndexes(0, 0, 1, headers.length).values = [headers];
  if (rows.length) s.getRangeByIndexes(1, 0, rows.length, headers.length).values = rows;
  formatHeader(s.getRangeByIndexes(0, 0, 1, headers.length));
  addTable(s, s.getRangeByIndexes(0, 0, rows.length + 1, headers.length).address, tableName, "TableStyleMedium2");
  s.freezePanes.freezeRows(1);
  s.showGridLines = false;
  for (const i of dateCols) s.getRangeByIndexes(1, i, Math.max(rows.length, 1), 1).format.numberFormat = "yyyy-mm-dd";
  for (const i of currencyCols) s.getRangeByIndexes(1, i, Math.max(rows.length, 1), 1).format.numberFormat = '"$"#,##0';
  return s;
}

const provRows = provenance.map(x => [x.company_id, x.source_company_name, x.source_name, x.source_type, x.snapshot_file, dateVal(x.snapshot_date), x.source_url, x.evidence_url, x.geography, x.product_type, truncate(x.description, 500), dateVal(x.captured_at), x.extraction_method]);
const provSheet = makeEvidenceSheet("Source Provenance", ["Company ID", "Source Company Name", "Source Name", "Source Type", "Snapshot File", "Snapshot Date", "Source URL", "Evidence URL", "Geography", "Product Type", "Description", "Captured At", "Extraction Method"], provRows, "SourceProvenanceTable", [5, 11]);
for (const [c, w] of [["A",24],["B",24],["C",28],["D",18],["E",32],["F",13],["G",38],["H",38],["I",14],["J",20],["K",55],["L",13],["M",28]]) provSheet.getRange(`${c}:${c}`).format.columnWidth = w;
provSheet.getRange(`K2:K${provRows.length + 1}`).format.wrapText = true;

const hiringRows = hiring.map(x => [x.company_id, x.company_name, x.job_title, x.role_family, x.seniority, x.department, x.location, x.remote_canada, x.posting_status, x.confidence, dateVal(x.evidence_date), dateVal(x.captured_at), x.job_url, x.evidence_url, x.aggregator_url, x.official_source_type, x.validation_method, truncate(x.validation_notes, 500)]);
const hireSheet = makeEvidenceSheet("Hiring Evidence", ["Company ID", "Company", "Job Title", "Role Family", "Seniority", "Department", "Location", "Remote Canada", "Status", "Confidence", "Evidence Date", "Captured At", "Job URL", "Evidence URL", "Aggregator URL", "Official Source Type", "Validation Method", "Validation Notes"], hiringRows, "HiringEvidenceTable", [10, 11]);
for (const [c, w] of [["A",24],["B",23],["C",36],["D",19],["E",18],["F",22],["G",28],["H",14],["I",12],["J",12],["K",13],["L",13],["M",38],["N",38],["O",38],["P",18],["Q",24],["R",48]]) hireSheet.getRange(`${c}:${c}`).format.columnWidth = w;
hireSheet.getRange(`R2:R${hiringRows.length + 1}`).format.wrapText = true;

const fundingRows = [
  ...fundingEvents.map(x => ["Dated event", x.company_id, x.funding_event_id, dateVal(x.event_date), x.funding_type, x.stage, x.amount_original, x.currency, Number(x.amount_cad || 0) || null, joinList(x.investors_or_funders), x.lead_investor || "", joinList(x.use_of_funds), x.source_type, x.confidence, x.evidence_url, dateVal(x.captured_at), truncate(x.description || x.agreement_title, 500)]),
  ...backing.map(x => ["Institutional backing", x.company_id, x.evidence_id, dateVal(x.evidence_date), x.backing_type, "", "", "", null, x.backer, "", "", x.source_type, x.confidence, x.evidence_url, dateVal(x.captured_at), truncate(x.summary, 500)])
];
const fundSheet = makeEvidenceSheet("Funding Events", ["Evidence Kind", "Company ID", "Evidence ID", "Event / Evidence Date", "Funding Type", "Stage", "Amount Original", "Currency", "Amount CAD", "Investors / Funders", "Lead Investor", "Use of Funds", "Source Type", "Confidence", "Evidence URL", "Captured At", "Summary / Description"], fundingRows, "FundingEvidenceTable", [3, 15], [8]);
for (const [c, w] of [["A",20],["B",24],["C",28],["D",16],["E",18],["F",13],["G",16],["H",10],["I",16],["J",34],["K",22],["L",26],["M",16],["N",12],["O",42],["P",13],["Q",58]]) fundSheet.getRange(`${c}:${c}`).format.columnWidth = w;
fundSheet.getRange(`Q2:Q${fundingRows.length + 1}`).format.wrapText = true;

const regRows = regulatory.map(x => [x.company_id, x.evidence_id, x.authority, x.jurisdiction, x.record_type, x.claim_type, x.record_id, x.legal_manufacturer, x.product_name, x.device_class, x.status, dateVal(x.decision_or_start_date), x.confidence, x.match_basis, x.evidence_url, dateVal(x.evidence_date), dateVal(x.captured_at), x.extraction_method, truncate(x.interpretation_note, 400)]);
const regSheet = makeEvidenceSheet("Regulatory Evidence", ["Company ID", "Evidence ID", "Authority", "Jurisdiction", "Record Type", "Claim Type", "Record ID", "Legal Manufacturer", "Product Name", "Device Class", "Status", "Decision / Start Date", "Confidence", "Match Basis", "Evidence URL", "Evidence Date", "Captured At", "Extraction Method", "Interpretation Note"], regRows, "RegulatoryEvidenceTable", [11, 15, 16]);
for (const [c, w] of [["A",24],["B",28],["C",20],["D",13],["E",15],["F",30],["G",16],["H",28],["I",34],["J",12],["K",12],["L",16],["M",12],["N",22],["O",42],["P",13],["Q",13],["R",36],["S",44]]) regSheet.getRange(`${c}:${c}`).format.columnWidth = w;
regSheet.getRange(`S2:S${regRows.length + 1}`).format.wrapText = true;

const pnRows = [
  ...products.map(x => ["Product profile", x.company_id, x.company_name, x.claim_type || "current product", "", x.product_category, x.development_stage, truncate(x.product_summary, 500), "", "", x.source_type, x.confidence, x.evidence_url, dateVal(x.evidence_date), dateVal(x.captured_at), x.extraction_method]),
  ...productNews.map(x => [x.track, x.company_id, companyModel.find(m => m.c.company_id === x.company_id)?.c.company_name || "", x.claim_type, x.event_type, x.product_or_program, x.development_stage, truncate(x.summary, 500), x.title, dateVal(x.event_date), x.source_type, x.confidence, x.evidence_url, dateVal(x.evidence_date), dateVal(x.captured_at), x.extraction_method])
];
const pnSheet = makeEvidenceSheet("Product & News Events", ["Record Kind", "Company ID", "Company", "Claim Type", "Event Type", "Product / Program", "Development Stage", "Summary", "Title", "Event Date", "Source Type", "Confidence", "Evidence URL", "Evidence Date", "Captured At", "Extraction Method"], pnRows, "ProductNewsTable", [9, 13, 14]);
for (const [c, w] of [["A",20],["B",24],["C",24],["D",22],["E",22],["F",28],["G",18],["H",56],["I",48],["J",13],["K",17],["L",12],["M",44],["N",13],["O",13],["P",38]]) pnSheet.getRange(`${c}:${c}`).format.columnWidth = w;
pnSheet.getRange(`H2:I${pnRows.length + 1}`).format.wrapText = true;

const aliasHeaders = ["Review Type", "Group / Name", "Company ID", "Canonical Company", "Source Company", "Domain / Website", "Reason / Decision", "Raw Record"];
const aliasRows = [
  ...ambiguousReview.map(x => ["Ambiguous name", x.normalized_name || "", "", "", x.company_names || "", x.domains || "", `${x.issue_type || ""}; status: ${x.review_status || ""}`, truncate(JSON.stringify(x), 700)]),
  ...duplicateReview.map(x => ["Duplicate review", x.normalized_name || "", x.company_id || "", x.canonical_company || "", x.aliases || "", x.domain || "", x.resolution || "", truncate(JSON.stringify(x), 700)])
];
const aliasSheet = makeEvidenceSheet("Alias Review", aliasHeaders, aliasRows, "AliasReviewTable");
for (const [c, w] of [["A",18],["B",25],["C",24],["D",25],["E",25],["F",30],["G",38],["H",60]]) aliasSheet.getRange(`${c}:${c}`).format.columnWidth = w;
aliasSheet.getRange(`H2:H${aliasRows.length + 1}`).format.wrapText = true;

const incompleteRows = [];
for (const m of companyModel) {
  const statusItems = [
    ["Hiring", m.statuses.hiring], ["Funding", m.statuses.funding], ["Regulatory", m.statuses.regulatory],
    ["Product development", m.statuses.product], ["News", m.statuses.news]
  ];
  for (const [track, s] of statusItems) {
    if (!["complete_matches", "complete_zero"].includes(s.status || "")) {
      incompleteRows.push([m.c.company_id, m.c.company_name, track, s.status || "not_run", dateVal(s.attempted_at), s.source_url || "", Number(s.raw_count ?? 0), Number(s.accepted_count ?? 0), truncate(s.notes || "", 600), m.c.website || ""]);
    }
  }
}
const incSheet = makeEvidenceSheet("Incomplete & Blocked Sources", ["Company ID", "Company", "Track", "Status", "Attempted At", "Source URL", "Raw Count", "Accepted Count", "Notes", "Company Website"], incompleteRows, "IncompleteSourcesTable", [4]);
for (const [c, w] of [["A",24],["B",25],["C",20],["D",16],["E",14],["F",42],["G",12],["H",14],["I",60],["J",38]]) incSheet.getRange(`${c}:${c}`).format.columnWidth = w;
incSheet.getRange(`I2:I${incompleteRows.length + 1}`).format.wrapText = true;
incSheet.getRange(`D2:D${incompleteRows.length + 1}`).conditionalFormats.add("containsText", { text: "blocked", format: { fill: paleRed, font: { color: "#991B1B" } } });
incSheet.getRange(`D2:D${incompleteRows.length + 1}`).conditionalFormats.add("containsText", { text: "review", format: { fill: paleAmber, font: { color: "#854D0E" } } });

// Run Summary
const run = sheets["Run Summary"];
title(run, run.getRange("A1:J1"), "Canada Company Enrichment — Run Summary", "Coverage, freshness, and audit metrics as at 2026-07-30");
run.getRange("A4:B10").values = [
  ["Metric", "Value"],
  ["Canonical companies", canonical.length],
  ["Companies with websites", canonical.filter(c => c.website).length],
  ["Verified open roles", hiring.length],
  ["Dated funding events", fundingEvents.length],
  ["Institutional-backing records", backing.length],
  ["Regulatory records", regulatory.length],
];
run.getRange("D4:E9").values = [
  ["Metric", "Value"],
  ["Companies with regulatory evidence", new Set(regulatory.map(x => x.company_id)).size],
  ["Product profiles (reviewed top 50)", products.length],
  ["Verified product/news events", productNews.length],
  ["Ambiguous identity groups", ambiguousReview.length],
  ["Duplicate-review rows", duplicateReview.length],
];
formatHeader(run.getRange("A4:B4"));
formatHeader(run.getRange("D4:E4"));
run.getRange("A12:C18").values = [
  ["Track", "Complete / checked", "Incomplete / blocked / not run"],
  ["Hiring", canonical.filter(c => ["complete_matches", "complete_zero"].includes(hComp.get(c.company_id)?.status)).length, canonical.filter(c => !["complete_matches", "complete_zero"].includes(hComp.get(c.company_id)?.status)).length],
  ["Funding", canonical.filter(c => ["complete_matches", "complete_zero"].includes(fComp.get(c.company_id)?.status)).length, canonical.filter(c => !["complete_matches", "complete_zero"].includes(fComp.get(c.company_id)?.status)).length],
  ["Regulatory", canonical.filter(c => ["complete_matches", "complete_zero"].includes(rComp.get(c.company_id)?.status)).length, canonical.filter(c => !["complete_matches", "complete_zero"].includes(rComp.get(c.company_id)?.status)).length],
  ["Product development", canonical.filter(c => ["complete_matches", "complete_zero"].includes(pComp.get(c.company_id)?.product_development?.status)).length, canonical.filter(c => !["complete_matches", "complete_zero"].includes(pComp.get(c.company_id)?.product_development?.status)).length],
  ["News", canonical.filter(c => ["complete_matches", "complete_zero"].includes(pComp.get(c.company_id)?.news?.status)).length, canonical.filter(c => !["complete_matches", "complete_zero"].includes(pComp.get(c.company_id)?.news?.status)).length],
  ["Total track states", canonical.length * 5, incompleteRows.length],
];
formatHeader(run.getRange("A12:C12"));
addTable(run, "A12:C18", "CoverageSummary", "TableStyleMedium4");
run.getRange("A21:B26").values = [
  ["Freshness Band", "Company Count"],
  ["Current (≤30 days)", null],
  ["Monitor (31–90 days)", null],
  ["Stale (>90 days)", null],
  ["Unknown", null],
  ["Total", null],
];
for (const [r, label] of [[22, "Current"], [23, "Monitor"], [24, "Stale"], [25, "Unknown"]]) {
  run.getRange(`B${r}`).formulas = [[`=COUNTIF('Companies'!$X$2:$X$${lastComp},"${label}")`]];
}
run.getRange("B26").formulas = [[`=SUM(B22:B25)`]];
formatHeader(run.getRange("A21:B21"));
addTable(run, "A21:B26", "FreshnessSummary", "TableStyleMedium9");
run.getRange("G4:H14").values = [["Top Prospect", "Priority Score"], ...Array.from({length: 10}, () => ["", null])];
for (let i = 0; i < 10; i++) {
  run.getRange(`G${i + 5}:H${i + 5}`).formulas = [[`='Top Prospects'!B${i + 5}`, `='Top Prospects'!C${i + 5}`]];
}
formatHeader(run.getRange("G4:H4"));
const chart = run.charts.add("bar", run.getRange("G4:H14"));
chart.title = "Highest-priority prospects (score / 100)";
chart.hasLegend = false;
chart.xAxis = { axisType: "textAxis", textStyle: { fontSize: 9 } };
chart.yAxis = { numberFormatCode: "0", min: 0, max: 100 };
chart.setPosition("D12", "J28");
run.getRange("A29:J32").merge();
run.getRange("A29").values = [["Coverage caveat: hiring and regulatory automated passes are complete; funding announcement ingestion remains outstanding; product and news coverage is currently limited to the reviewed top-50 automated pass. The Incomplete & Blocked Sources tab preserves these distinctions."]];
run.getRange("A29:J32").format = { fill: paleAmber, font: { color: "#7A4E00" }, wrapText: true, verticalAlignment: "center", borders: { preset: "outside", style: "thin", color: "#E5B83F" } };
for (const [c, w] of [["A",28],["B",15],["C",25],["D",28],["E",15],["F",4],["G",28],["H",14],["I",4],["J",4]]) run.getRange(`${c}:${c}`).format.columnWidth = w;
run.showGridLines = false;
run.freezePanes.freezeRows(2);

// Compact number/date formatting and visual basics across evidence tabs.
for (const name of ["Source Provenance", "Hiring Evidence", "Funding Events", "Regulatory Evidence", "Product & News Events", "Alias Review", "Incomplete & Blocked Sources"]) {
  sheets[name].getUsedRange().format.verticalAlignment = "top";
}

// Inspect and render all sheet heads before export.
const inspectSummary = await wb.inspect({ kind: "sheet", include: "id,name", maxChars: 4000 });
await fs.writeFile(path.join(outDir, "sheet_inventory.ndjson"), inspectSummary.ndjson, "utf8");
const companyInspect = await wb.inspect({ kind: "table", range: "Companies!A1:AP12", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 42, maxChars: 18000 });
await fs.writeFile(path.join(outDir, "companies_inspect.ndjson"), companyInspect.ndjson, "utf8");
const errorScan = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan", maxChars: 12000 });
await fs.writeFile(path.join(outDir, "formula_error_scan.ndjson"), errorScan.ndjson, "utf8");

const renderRanges = {
  "Top Prospects": "A1:P16",
  "Companies": "A1:AP12",
  "Source Provenance": "A1:M12",
  "Hiring Evidence": "A1:R12",
  "Funding Events": "A1:Q12",
  "Regulatory Evidence": "A1:S12",
  "Product & News Events": "A1:P12",
  "Alias Review": "A1:H12",
  "Incomplete & Blocked Sources": "A1:J12",
  "Run Summary": "A1:J32",
  "Methodology": "A1:H34",
};
for (const [name, range] of Object.entries(renderRanges)) {
  const preview = await wb.render({ sheetName: name, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(outDir, `preview_${name.replace(/[^A-Za-z0-9]+/g, "_")}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(wb);
await output.save(path.join(outDir, "Canada_Company_Enrichment_Work_Package_6.xlsx"));
console.log(JSON.stringify({
  workbook: path.join(outDir, "Canada_Company_Enrichment_Work_Package_6.xlsx"),
  companies: canonical.length,
  topProspects: 50,
  evidence: { provenance: provenance.length, hiring: hiring.length, fundingEvents: fundingEvents.length, backing: backing.length, regulatory: regulatory.length, productProfiles: products.length, productNews: productNews.length },
  incompleteRows: incompleteRows.length,
  sheets: sheetNames,
}, null, 2));
