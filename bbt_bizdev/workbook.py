from __future__ import annotations

import re
from urllib.parse import quote, urlsplit, urlunsplit

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .config import OUT, SOURCES, SOURCE_PLAYBOOKS
from .models import CompanyRecord, DiscoveryHit, TODAY, TriggerEvent
from .pipeline import adapter_inventory_label, classify_company, lead_filter_fields, primary_discovery, primary_trigger


EXPECTED_WORKBOOK_SHEETS = [
    "Pipeline Summary",
    "Pipeline Run Log",
    "Source Inventory",
    "Source Playbooks",
    "Discovery Hits",
    "Leads",
    "Trigger Log",
]


def excel_safe(value):
    if isinstance(value, str):
        value = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", value)
        if value and value[0] in ("=", "+", "-", "@"):
            return "'" + value
    return value


def append_excel_row(ws, row):
    ws.append([excel_safe(value) for value in row])


def style_sheet(ws):
    header_fill = PatternFill("solid", fgColor="1F4E78")
    thin = Side(style="thin", color="D9E2F3")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = Font(name="Aptos", size=10, color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name="Aptos", size=10)
            cell.border = Border(bottom=thin)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    ws.sheet_view.showGridLines = False

def size_columns(ws, widths=None):
    widths = widths or {}
    for col in range(1, ws.max_column + 1):
        letter = get_column_letter(col)
        if letter in widths:
            ws.column_dimensions[letter].width = widths[letter]
            continue
        max_len = max((len(str(cell.value)) for cell in ws[letter] if cell.value is not None), default=10)
        ws.column_dimensions[letter].width = min(max(max_len + 2, 12), 48)

def clean_hyperlink_target(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value.startswith(("http://", "https://")):
        return None
    if any(ord(char) < 32 for char in value):
        return None
    parts = urlsplit(value)
    if not parts.netloc:
        return None
    path = quote(parts.path, safe="/%:@")
    query = quote(parts.query, safe="=&?/%:@,+;")
    fragment = quote(parts.fragment, safe="=&?/%:@,+;")
    return urlunsplit((parts.scheme, parts.netloc, path, query, fragment))

def add_hyperlinks(ws, cols: list[int]):
    for row in range(2, ws.max_row + 1):
        for col in cols:
            cell = ws.cell(row=row, column=col)
            target = clean_hyperlink_target(cell.value)
            if target:
                cell.value = target
                cell.hyperlink = target
                cell.style = "Hyperlink"


def linkedin_contact_values(contact):
    if contact is None:
        return ["", "", ""]
    return [contact.name, contact.title, contact.url]


def na_if_blank(value):
    return value if value not in ("", None) else "N/A"


def style_linkedin_columns(ws, start_col: int) -> None:
    fill = PatternFill("solid", fgColor="0F6B78")
    for cell in ws[1][start_col - 1:]:
        cell.fill = fill

def finish_sheet(ws, widths=None, hyperlink_cols: list[int] | None = None) -> None:
    style_sheet(ws)
    if hyperlink_cols:
        add_hyperlinks(ws, hyperlink_cols)
    size_columns(ws, widths)


def write_pipeline_summary_sheet(wb, companies: dict[str, CompanyRecord], discovery_hits: list[DiscoveryHit], trigger_events: list[TriggerEvent], run_log: list[list[str]]) -> None:
    ws = wb.create_sheet("Pipeline Summary")
    append_excel_row(ws, ["Metric", "Value"])
    append_excel_row(ws, ["Run date", TODAY])
    append_excel_row(ws, ["Approved sources", len(SOURCES)])
    append_excel_row(ws, ["Fetched/skipped sources", len(run_log)])
    append_excel_row(ws, ["Discovery hits", len(discovery_hits)])
    append_excel_row(ws, ["Companies", len(companies)])
    append_excel_row(ws, ["Trigger events", len(trigger_events)])
    append_excel_row(ws, ["LinkedIn company URLs", sum(bool(record.linkedin.company_url) for record in companies.values())])
    append_excel_row(ws, ["LinkedIn contact targets", sum(record.linkedin.contact_status != "Not targeted" for record in companies.values())])
    append_excel_row(ws, ["LinkedIn contact sets complete", sum(record.linkedin.contact_status.startswith("Complete") for record in companies.values())])
    append_excel_row(ws, ["LinkedIn contact sets partial", sum(record.linkedin.contact_status.startswith("Partial") for record in companies.values())])
    finish_sheet(ws, {"A": 28, "B": 24})


def write_pipeline_run_log_sheet(wb, run_log: list[list[str]]) -> None:
    ws = wb.create_sheet("Pipeline Run Log")
    append_excel_row(ws, ["Source", "Source type", "URL", "Status", "Result"])
    for row in run_log:
        append_excel_row(ws, row)
    finish_sheet(ws, {"A": 26, "B": 18, "C": 52, "D": 16, "E": 42}, [3])


def write_source_inventory_sheet(wb) -> None:
    ws = wb.create_sheet("Source Inventory")
    append_excel_row(ws, ["Source name", "Type", "URL", "Geography", "Priority", "Update cadence", "Extraction method", "Signal / notes", "Automated adapter"])
    for s in SOURCES:
        append_excel_row(ws, [s.name, s.source_type, s.url, s.geography, s.priority, s.update_cadence, s.extraction_method, s.notes, adapter_inventory_label(s)])
    finish_sheet(ws, {"A": 30, "B": 20, "C": 54, "H": 58, "I": 22}, [3])


def write_source_playbooks_sheet(wb) -> None:
    ws = wb.create_sheet("Source Playbooks")
    append_excel_row(ws, ["Source type", "Search/query terms", "Filters", "Output fields", "Expected evidence", "Best-fit BBT wedge"])
    for row in SOURCE_PLAYBOOKS:
        append_excel_row(ws, row)
    finish_sheet(ws, {"A": 22, "B": 56, "C": 44, "D": 44, "E": 44, "F": 22})


def write_discovery_hits_sheet(wb, discovery_hits: list[DiscoveryHit]) -> None:
    ws = wb.create_sheet("Discovery Hits")
    append_excel_row(ws, ["Company", "Discovery source", "Source type", "Discovery evidence URL", "Article year", "Discovery rationale", "Matched terms", "Website", "Geography", "Product type", "Accelerator program", "Cohort label", "Cohort year", "Category / track", "Company description", "Captured at"])
    for hit in discovery_hits:
        append_excel_row(ws, [
            hit.company,
            hit.source_name,
            hit.source_type,
            hit.discovery_url,
            hit.article_year,
            hit.discovery_rationale,
            hit.matched_terms,
            hit.website,
            hit.geography,
            hit.product_type,
            hit.accelerator_program,
            hit.cohort_label,
            hit.cohort_year,
            hit.category_or_track,
            hit.company_description,
            hit.captured_at,
        ])
    finish_sheet(ws, {"A": 24, "B": 28, "C": 18, "D": 54, "E": 14, "F": 56, "G": 24, "H": 36, "J": 28, "K": 26, "L": 24, "N": 28, "O": 58}, [4, 8])


def write_trigger_log_sheet(wb, trigger_events: list[TriggerEvent]) -> None:
    ws = wb.create_sheet("Trigger Log")
    append_excel_row(ws, ["Company", "Trigger type", "Trigger event", "Trigger source", "Evidence URL", "Trigger role", "Captured at"])
    for event in trigger_events:
        append_excel_row(ws, [event.company, event.trigger_type, event.trigger_event, event.trigger_source, event.evidence_url, event.trigger_role, event.captured_at])
    finish_sheet(ws, {"A": 24, "B": 20, "C": 64, "D": 30, "E": 54, "F": 16}, [5])


def write_leads_sheet(wb, companies: dict[str, CompanyRecord]) -> None:
    ws = wb.create_sheet("Leads")
    headers = [
        "Company", "Company website", "Company description", "Product type", "Product area",
        "Company type", "Company stage", "Hiring signal", "Geography", "Funding stage",
        "Accelerator program", "Cohort label", "Cohort year", "Category / track",
        "Evidence year", "Evidence status", "Source name", "Source type", "Source URL",
        "Discovery rationale", "Matched terms", "Trigger type", "Persona", "BBT quadrant",
        "LinkedIn company URL", "LinkedIn company status",
        "Executive contact name", "Executive contact title", "Executive LinkedIn URL",
        "Technical/R&D contact name", "Technical/R&D contact title", "Technical/R&D LinkedIn URL",
        "Quality/QA contact name", "Quality/QA contact title", "Quality/QA LinkedIn URL",
        "LinkedIn contact status", "Date captured",
    ]
    append_excel_row(ws, headers)
    for record in sorted(companies.values(), key=lambda r: r.company):
        enrichment = classify_company(record)
        filter_fields = lead_filter_fields(record, enrichment)
        trigger = primary_trigger(record)
        hit = primary_discovery(record)
        status = "Verified trigger" if trigger else "Discovered only"
        append_excel_row(ws, [
            record.company,
            record.website,
            hit.company_description,
            record.product_type,
            filter_fields["Product area"],
            filter_fields["Company type"],
            filter_fields["Company stage"],
            filter_fields["Hiring signal"],
            filter_fields["Geography"],
            filter_fields["Funding stage"],
            na_if_blank(hit.accelerator_program),
            na_if_blank(hit.cohort_label),
            na_if_blank(hit.cohort_year),
            na_if_blank(hit.category_or_track),
            filter_fields["Evidence year"],
            status,
            hit.source_name,
            hit.source_type,
            hit.discovery_url,
            hit.discovery_rationale,
            hit.matched_terms,
            filter_fields["Trigger type"],
            enrichment.persona,
            enrichment.primary_quadrant,
            record.linkedin.company_url,
            record.linkedin.company_status,
            *linkedin_contact_values(record.linkedin.executive),
            *linkedin_contact_values(record.linkedin.technical),
            *linkedin_contact_values(record.linkedin.quality),
            record.linkedin.contact_status,
            TODAY,
        ])
    style_sheet(ws)
    style_linkedin_columns(ws, 25)
    add_hyperlinks(ws, [2, 19, 25, 29, 32, 35])
    size_columns(ws, {
        "A": 24, "B": 36, "C": 58, "D": 28, "E": 24, "F": 24, "G": 24, "H": 14,
        "I": 16, "J": 28, "K": 26, "L": 24, "M": 14, "N": 28, "O": 14,
        "P": 18, "Q": 28, "R": 18, "S": 54, "T": 58, "U": 24, "V": 22,
        "W": 28, "X": 22, "Y": 42, "Z": 24, "AA": 25, "AB": 38, "AC": 42,
        "AD": 25, "AE": 38, "AF": 42, "AG": 25, "AH": 38, "AI": 42, "AJ": 26,
        "AK": 16,
    })


def write_workbook(companies: dict[str, CompanyRecord], discovery_hits: list[DiscoveryHit], trigger_events: list[TriggerEvent], run_log: list[list[str]]):
    wb = Workbook()
    wb.remove(wb.active)

    write_pipeline_summary_sheet(wb, companies, discovery_hits, trigger_events, run_log)
    write_pipeline_run_log_sheet(wb, run_log)
    write_source_inventory_sheet(wb)
    write_source_playbooks_sheet(wb)
    write_discovery_hits_sheet(wb, discovery_hits)
    write_leads_sheet(wb, companies)
    write_trigger_log_sheet(wb, trigger_events)

    wb.calculation.calcMode = "auto"
    wb.calculation.fullCalcOnLoad = True
    try:
        wb.save(OUT)
        return OUT
    except PermissionError:
        fallback = OUT.with_name("BlueBridge_TOFU_BizDev_V1_pipeline.xlsx")
        wb.save(fallback)
        return fallback

