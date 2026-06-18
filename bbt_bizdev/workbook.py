from __future__ import annotations

import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .config import OUT, SOURCES, SOURCE_PLAYBOOKS
from .models import CompanyRecord, DiscoveryHit, TODAY, TriggerEvent
from .pipeline import adapter_inventory_label, primary_discovery, primary_trigger, score_company


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

def add_hyperlinks(ws, cols: list[int]):
    for row in range(2, ws.max_row + 1):
        for col in cols:
            cell = ws.cell(row=row, column=col)
            if isinstance(cell.value, str) and cell.value.startswith("http"):
                cell.hyperlink = cell.value
                cell.style = "Hyperlink"

def write_workbook(companies: dict[str, CompanyRecord], discovery_hits: list[DiscoveryHit], trigger_events: list[TriggerEvent], run_log: list[list[str]]):
    wb = Workbook()
    wb.remove(wb.active)

    ws = wb.create_sheet("Pipeline Summary")
    append_excel_row(ws, ["Metric", "Value"])
    append_excel_row(ws, ["Run date", TODAY])
    append_excel_row(ws, ["Approved sources", len(SOURCES)])
    append_excel_row(ws, ["Fetched/skipped sources", len(run_log)])
    append_excel_row(ws, ["Discovery hits", len(discovery_hits)])
    append_excel_row(ws, ["Companies", len(companies)])
    append_excel_row(ws, ["Trigger events", len(trigger_events)])
    style_sheet(ws)
    size_columns(ws, {"A": 28, "B": 24})

    ws = wb.create_sheet("Pipeline Run Log")
    append_excel_row(ws, ["Source", "Source type", "URL", "Status", "Result"])
    for row in run_log:
        append_excel_row(ws, row)
    style_sheet(ws)
    add_hyperlinks(ws, [3])
    size_columns(ws, {"A": 26, "B": 18, "C": 52, "D": 16, "E": 42})

    ws = wb.create_sheet("Source Inventory")
    append_excel_row(ws, ["Source name", "Type", "URL", "Geography", "Priority", "Update cadence", "Extraction method", "Signal / notes", "Automated adapter"])
    for s in SOURCES:
        append_excel_row(ws, [s.name, s.source_type, s.url, s.geography, s.priority, s.update_cadence, s.extraction_method, s.notes, adapter_inventory_label(s)])
    style_sheet(ws)
    add_hyperlinks(ws, [3])
    size_columns(ws, {"A": 30, "B": 20, "C": 54, "H": 58, "I": 22})

    ws = wb.create_sheet("Source Playbooks")
    append_excel_row(ws, ["Source type", "Search/query terms", "Filters", "Output fields", "Expected evidence", "Best-fit BBT wedge"])
    for row in SOURCE_PLAYBOOKS:
        append_excel_row(ws, row)
    style_sheet(ws)
    size_columns(ws, {"A": 22, "B": 56, "C": 44, "D": 44, "E": 44, "F": 22})

    ws = wb.create_sheet("Discovery Hits")
    append_excel_row(ws, ["Company", "Discovery source", "Source type", "Discovery evidence URL", "Discovery rationale", "Matched terms", "Website", "Geography", "Product type", "Accelerator program", "Cohort label", "Cohort year", "Category / track", "Company description", "Captured at"])
    for hit in discovery_hits:
        append_excel_row(ws, [
            hit.company,
            hit.source_name,
            hit.source_type,
            hit.discovery_url,
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
    style_sheet(ws)
    add_hyperlinks(ws, [4, 7])
    size_columns(ws, {"A": 24, "B": 28, "C": 18, "D": 54, "E": 56, "F": 24, "G": 36, "I": 28, "J": 26, "K": 24, "M": 28, "N": 58})

    ws = wb.create_sheet("Lead Intake")
    append_excel_row(ws, ["Company", "Website", "Geography", "Product type", "Accelerator program", "Cohort label", "Cohort year", "Category / track", "Company description", "Discovery source", "Discovery source type", "Discovery evidence URL", "Discovery rationale", "Primary trigger event", "Trigger source", "Trigger evidence URL", "Evidence status", "Date captured"])
    for record in sorted(companies.values(), key=lambda r: r.company):
        hit = primary_discovery(record)
        trigger = primary_trigger(record)
        append_excel_row(ws, [
            record.company,
            record.website,
            record.geography,
            record.product_type,
            hit.accelerator_program,
            hit.cohort_label,
            hit.cohort_year,
            hit.category_or_track,
            hit.company_description,
            hit.source_name,
            hit.source_type,
            hit.discovery_url,
            hit.discovery_rationale,
            trigger.trigger_event if trigger else "",
            trigger.trigger_source if trigger else "",
            trigger.evidence_url if trigger else "",
            "Verified trigger" if trigger else "Discovered only",
            TODAY,
        ])
    style_sheet(ws)
    add_hyperlinks(ws, [2, 12, 16])
    size_columns(ws, {"A": 24, "B": 36, "C": 16, "D": 28, "E": 26, "F": 24, "H": 28, "I": 58, "J": 28, "L": 54, "M": 58, "N": 58, "O": 28, "P": 54})

    ws = wb.create_sheet("Trigger Log")
    append_excel_row(ws, ["Company", "Trigger type", "Trigger event", "Trigger source", "Evidence URL", "Trigger role", "Captured at"])
    for event in trigger_events:
        append_excel_row(ws, [event.company, event.trigger_type, event.trigger_event, event.trigger_source, event.evidence_url, event.trigger_role, event.captured_at])
    style_sheet(ws)
    add_hyperlinks(ws, [5])
    size_columns(ws, {"A": 24, "B": 20, "C": 64, "D": 30, "E": 54, "F": 16})

    ws = wb.create_sheet("Lead Scoring")
    headers = [
        "Company", "Persona", "Primary BBT quadrant", "Secondary tag", "Pain hypothesis",
        "Recently funded +3", "AI/SaMD/device +3", "Hiring QA/reg/V&V +3", "Clinical validation +2",
        "FDA/CE/reg language +2", "Grant/public funding +2", "University/grant origin +2",
        "No obvious reg team +2", "Pre-commercial +1", "Large company -1", "Wellness/non-medical -2",
        "Pharma-only -2", "Score", "Priority band", "Evidence status", "Primary evidence URL",
    ]
    append_excel_row(ws, headers)
    scoring_rows = []
    for record in sorted(companies.values(), key=lambda r: r.company):
        flags, score, band, persona, quadrant, secondary, pain = score_company(record)
        trigger = primary_trigger(record)
        hit = primary_discovery(record)
        evidence_url = trigger.evidence_url if trigger else hit.discovery_url
        status = "Verified trigger" if trigger else "Discovered only"
        append_excel_row(ws, [
            record.company, persona, quadrant, secondary, pain,
            *flags.values(), score, band, status, evidence_url,
        ])
        scoring_rows.append((score, band, status, record, pain, evidence_url))
    style_sheet(ws)
    add_hyperlinks(ws, [21])
    size_columns(ws, {"A": 24, "B": 32, "C": 22, "D": 22, "E": 64, "R": 10, "S": 14, "T": 18, "U": 54})

    scoring_rows.sort(key=lambda row: (row[2] == "Verified trigger", row[0]), reverse=True)
    ws = wb.create_sheet("Weekly Review")
    append_excel_row(ws, ["Rank", "Company", "Score", "Priority band", "Evidence status", "Why shortlisted", "Next action", "Owner", "Status", "Review notes", "Evidence URL"])
    for idx, (score, band, status, record, pain, evidence_url) in enumerate(scoring_rows[:15], start=1):
        append_excel_row(ws, [
            idx,
            record.company,
            score,
            band,
            status,
            pain,
            "Contact research" if status == "Verified trigger" else "Run trigger research before outreach",
            "",
            "Validate",
            "",
            evidence_url,
        ])
    style_sheet(ws)
    add_hyperlinks(ws, [11])
    size_columns(ws, {"A": 8, "B": 24, "C": 10, "D": 14, "E": 18, "F": 62, "G": 36, "K": 54})

    wb.calculation.calcMode = "auto"
    wb.calculation.fullCalcOnLoad = True
    try:
        wb.save(OUT)
        return OUT
    except PermissionError:
        fallback = OUT.with_name("BlueBridge_TOFU_BizDev_V1_pipeline.xlsx")
        wb.save(fallback)
        return fallback

