#!/usr/bin/env python3
"""Build Toronto executive research scope and coverage from the source workbook.

The workbook is the only source of company scope. Candidate evidence is recorded
separately in contacts.csv and is never imported from the previous GTA run.
"""

from __future__ import annotations

import csv
import json
import re
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/canada_company_enrichment_wp6_2026-07-30/Canada_Company_Enrichment_Work_Package_6.xlsx"
OUT = ROOT / "outputs/canada_toronto_executive_research_2026-09-30"
NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def workbook_sheet(zf: zipfile.ZipFile, wanted: str) -> ET.Element:
    book = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    targets = {item.attrib["Id"]: item.attrib["Target"] for item in rels}
    for sheet in book.find("m:sheets", NS):
        if sheet.attrib["name"] == wanted:
            target = targets[sheet.attrib[f"{{{NS['r']}}}id"]]
            path = target.lstrip("/")
            if not path.startswith("xl/"):
                path = "xl/" + path
            return ET.fromstring(zf.read(path))
    raise ValueError(f"Missing worksheet: {wanted}")


def shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in si.findall(".//m:t", NS))
            for si in root.findall("m:si", NS)]


def cell_value(cell: ET.Element, strings: list[str]) -> str:
    value = cell.find("m:v", NS)
    if value is None:
        inline = cell.find("m:is", NS)
        return "" if inline is None else "".join(t.text or "" for t in inline.findall(".//m:t", NS))
    raw = value.text or ""
    return strings[int(raw)] if cell.attrib.get("t") == "s" else raw


def rows_from_workbook() -> list[dict[str, str]]:
    with zipfile.ZipFile(SOURCE) as zf:
        strings = shared_strings(zf)
        sheet = workbook_sheet(zf, "Companies")
        rows = []
        for row in sheet.findall(".//m:sheetData/m:row", NS)[1:]:
            values = {}
            for cell in row.findall("m:c", NS):
                col = re.sub(r"\d", "", cell.attrib["r"])
                values[col] = cell_value(cell, strings)
            if values.get("D", "").strip().casefold() != "toronto":
                continue
            rows.append({
                "source_row": row.attrib["r"],
                "company": values.get("B", "").strip(),
                "city": values.get("D", "").strip(),
                "website": values.get("C", "").strip(),
                "product_category": values.get("G", "").strip(),
                "product_summary": values.get("H", "").strip(),
            })
        return rows


def read_contacts() -> list[dict[str, str]]:
    path = OUT / "contacts.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    companies = rows_from_workbook()
    if len(companies) != 19:
        raise SystemExit(f"Expected the source workbook's 19 exact Toronto rows; found {len(companies)}")
    scope_fields = ["source_row", "company", "city", "website", "product_category", "product_summary"]
    write_csv(OUT / "companies.csv", companies, scope_fields)

    contacts = read_contacts()
    known_rows = {row["source_row"] for row in companies}
    if any(item["source_row"] not in known_rows for item in contacts):
        raise SystemExit("contacts.csv contains a company outside exact Toronto workbook scope")
    accepted_by_row: dict[str, int] = {}
    for item in contacts:
        if item["decision"] == "verified":
            accepted_by_row[item["source_row"]] = accepted_by_row.get(item["source_row"], 0) + 1
    coverage = []
    for company in companies:
        count = accepted_by_row.get(company["source_row"], 0)
        coverage.append({**company, "verified_contacts": count,
                         "coverage_status": "complete" if count >= 3 else "below_target",
                         "target": 3})
    write_csv(OUT / "coverage.csv", coverage,
              scope_fields + ["verified_contacts", "coverage_status", "target"])

    verified = sum(item["decision"] == "verified" for item in contacts)
    pending = sum(item["decision"] == "pending" for item in contacts)
    complete = sum(item["coverage_status"] == "complete" for item in coverage)
    lines = [
        "# Toronto executive research — 30 September 2026", "",
        "## Scope and method", "",
        f"Company scope is extracted directly from the linked WP6 workbook's `Companies` sheet where `City` equals `Toronto` exactly: **{len(companies)} companies**. "
        "Each source worksheet row remains separate. This ledger was researched independently; no prior GTA research or contact records were used.", "",
        "Discovery used company leadership/team pages, company announcements, credible institutional sources, web search, and LinkedIn. Search snippets and third-party databases were treated as leads. A contact is counted as verified only when the company and role have current evidence and the exact person's LinkedIn profile matches the person and company. Unresolved records remain pending.", "",
        "## Coverage", "",
        f"- Verified contacts: **{verified}**", f"- Pending candidate records: **{pending}**",
        f"- Companies with three verified executives: **{complete}/{len(companies)}**", "",
        "| Workbook row | Company | Verified | Pending candidates | Status |", "|---:|---|---:|---:|---|",
    ]
    for company, cover in zip(companies, coverage):
        pend = sum(x["source_row"] == company["source_row"] and x["decision"] == "pending" for x in contacts)
        lines.append(f"| {company['source_row']} | {company['company']} | {cover['verified_contacts']} | {pend} | {cover['coverage_status']} |")
    lines += ["", "## Limits", "", "Public information did not support three verified executives for every company in this pass. Pending records identify leads or role claims that still need exact-profile, company identity, or current-role corroboration. The workbook has not been modified.", "",
              "## Files", "", "- `companies.csv`: exact Toronto company scope from the workbook.", "- `contacts.csv`: person-level evidence ledger, including pending candidates.", "- `coverage.csv`: verified counts and three-contact target status per company.", "- `build_toronto_executive_research.py`: deterministic scope/coverage builder.", ""]
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
