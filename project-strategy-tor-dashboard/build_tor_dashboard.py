#!/usr/bin/env python3
"""
Build the Project Strategy TOR (Terms of Reference) Dashboard workbook.

Monthly team reporting pack that tracks live project delivery against what each
project's Terms of Reference actually committed to: scope, deliverables,
milestones, budget, governance (RACI) and risk.

Run:  python3 build_tor_dashboard.py
Then: python3 <xlsx-skill>/scripts/recalc.py Project_Strategy_TOR_Dashboard.xlsx

Regenerating overwrites the workbook, so edit this script rather than the .xlsx
if you want to change structure; edit the .xlsx directly for month-to-month data.
"""

import datetime as dt
import os

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "Project_Strategy_TOR_Dashboard.xlsx")

# ---------------------------------------------------------------- styling ----
FONT = "Arial"

NAVY = "1F3864"
SLATE = "44546A"
LIGHT = "D9E2F3"
BAND = "F2F5FB"
GREY = "808080"

BLUE_INPUT = "0000FF"   # hardcoded input typed by the user
GREEN_LINK = "008000"   # value pulled from another sheet
BLACK = "000000"        # formula computed on this sheet
YELLOW_FILL = "FFFF00"  # cells the user is expected to fill in

RAG_FILL = {
    "Red": PatternFill("solid", fgColor="F4B7B7"),
    "Amber": PatternFill("solid", fgColor="FFE39A"),
    "Green": PatternFill("solid", fgColor="C2E0C2"),
}

CUR = '$#,##0;($#,##0);-'
PCT = '0.0%;(0.0%);-'
INT = '#,##0;(#,##0);-'
DATE = 'yyyy-mm-dd'
MONTH = 'yyyy-mm'

thin = Side(style="thin", color="BFBFBF")
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)

# Sheet-row capacity. Formulas span these ranges so added rows are picked up
# automatically without anyone editing a formula.
TOR_FIRST, TOR_LAST = 4, 43
LOG_FIRST, LOG_LAST = 4, 303
DEL_FIRST, DEL_LAST = 4, 203
RSK_FIRST, RSK_LAST = 4, 203


def title_block(ws, title, subtitle, width):
    ws["A1"] = title
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor=NAVY)
    ws["A1"].alignment = Alignment(vertical="center", indent=1)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=width)
    ws.row_dimensions[1].height = 26

    ws["A2"] = subtitle
    ws["A2"].font = Font(name=FONT, size=9, italic=True, color=SLATE)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=width)


def header_row(ws, row, headers, wrap=True):
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = Font(name=FONT, size=9, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=SLATE)
        c.alignment = Alignment(horizontal="center", vertical="center",
                                wrap_text=wrap)
        c.border = BOX
    ws.row_dimensions[row].height = 32


def widths(ws, spec):
    for col, w in spec.items():
        ws.column_dimensions[col].width = w


def body(cell, *, fmt=None, color=BLACK, bold=False, wrap=False,
         align=None, fill=None):
    cell.font = Font(name=FONT, size=9, color=color, bold=bold)
    cell.border = BOX
    if fmt:
        cell.number_format = fmt
    if fill:
        cell.fill = PatternFill("solid", fgColor=fill)
    cell.alignment = Alignment(horizontal=align, vertical="top" if wrap else "center",
                               wrap_text=wrap)


def band(ws, first, last, ncols):
    """Zebra-stripe alternate rows so long registers stay readable."""
    for r in range(first, last + 1):
        if (r - first) % 2 == 1:
            for c in range(1, ncols + 1):
                cell = ws.cell(row=r, column=c)
                if cell.fill.fgColor.rgb in (None, "00000000"):
                    cell.fill = PatternFill("solid", fgColor=BAND)


# ------------------------------------------------------------ example data ---
# EXAMPLE PORTFOLIO — replace with the team's real projects. Names are
# placeholders, not real people.
MONTHS = [dt.date(2026, 3, 1), dt.date(2026, 4, 1), dt.date(2026, 5, 1),
          dt.date(2026, 6, 1), dt.date(2026, 7, 1), dt.date(2026, 8, 1)]
REPORT_MONTH = MONTHS[-1]

PROJECTS = [
    # id, name, pillar, sponsor, pm, tor approved, start, end, budget,
    # planned milestones, planned deliverables, objective, in scope, out of scope
    ("P-001", "Client Portal Rebuild", "Digital Experience", "A. Mensah",
     "R. Patel", dt.date(2026, 2, 10), dt.date(2026, 3, 1), dt.date(2026, 11, 30),
     500000, 9, 12,
     "Replace the legacy client portal to cut self-service failure rate by half.",
     "Portal UI, auth, self-service billing, migration of active accounts",
     "Mobile app, partner API, archived account history"),
    ("P-002", "Data Platform Migration", "Data & Infrastructure", "L. Njoku",
     "S. Kowalski", dt.date(2026, 2, 3), dt.date(2026, 3, 1), dt.date(2027, 1, 29),
     820000, 12, 15,
     "Move reporting workloads off the on-prem warehouse to the cloud platform.",
     "ETL rebuild, warehouse cutover, BI re-point, decommission plan",
     "ML feature store, real-time streaming, third-party data contracts"),
    ("P-003", "Regulatory Reporting Uplift", "Risk & Compliance", "D. Ferreira",
     "M. Haddad", dt.date(2026, 2, 17), dt.date(2026, 3, 1), dt.date(2026, 10, 30),
     340000, 8, 10,
     "Meet the new quarterly disclosure standard ahead of the Q1 2027 deadline.",
     "Control redesign, evidence automation, submission templates, sign-off flow",
     "Historic restatements, group consolidation changes"),
    ("P-004", "Market Expansion - APAC", "Growth", "A. Mensah",
     "T. Yamamoto", dt.date(2026, 2, 24), dt.date(2026, 3, 1), dt.date(2027, 2, 26),
     610000, 10, 11,
     "Stand up sales and support operations in two APAC markets.",
     "Entity setup, local hiring, pricing localisation, support coverage",
     "Manufacturing footprint, local data centre, M&A options"),
    ("P-005", "Cost-to-Serve Optimisation", "Operating Efficiency", "L. Njoku",
     "C. Duarte", dt.date(2026, 2, 6), dt.date(2026, 3, 1), dt.date(2026, 9, 30),
     275000, 7, 9,
     "Reduce cost to serve per account by 15% without lowering CSAT.",
     "Process redesign, tier-1 automation, vendor renegotiation",
     "Headcount reduction, offshoring, product rationalisation"),
]

# Cumulative-to-date figures per project, one value per month in MONTHS.
LOG = {
    "P-001": dict(
        ms_plan=[2, 3, 5, 6, 8, 9],       ms_done=[2, 3, 4, 5, 7, 7],
        dl_due=[2, 4, 5, 7, 9, 11],       dl_acc=[2, 4, 4, 6, 8, 9],
        spend=[72000, 140000, 205000, 286000, 352000, 412000],
        cr_raised=[0, 1, 1, 2, 3, 3],     cr_appr=[0, 1, 1, 1, 2, 2],
        risks=[3, 4, 4, 5, 4, 3],         high=[0, 1, 1, 1, 1, 1],
        gaps=[1, 1, 0, 0, 2, 2],
        rag=["Green", "Green", "Amber", "Amber", "Amber", "Amber"],
        note=["Kick-off complete, TOR baselined.",
              "Auth vendor confirmed; first CR raised on billing scope.",
              "Design sign-off slipped 2 weeks; one milestone missed.",
              "Migration dry-run failed once, retest scheduled.",
              "Two deliverables awaiting sponsor acceptance.",
              "Recovery plan agreed; hit rate improving but still behind TOR."]),
    "P-002": dict(
        ms_plan=[1, 2, 4, 6, 8, 10],      ms_done=[1, 2, 4, 6, 7, 9],
        dl_due=[1, 3, 4, 6, 8, 10],       dl_acc=[1, 3, 4, 5, 7, 9],
        spend=[95000, 190000, 300000, 430000, 560000, 690000],
        cr_raised=[1, 1, 2, 2, 2, 3],     cr_appr=[0, 1, 1, 1, 1, 2],
        risks=[5, 5, 6, 6, 5, 5],         high=[1, 1, 2, 1, 1, 0],
        gaps=[2, 1, 1, 0, 0, 0],
        rag=["Amber", "Amber", "Amber", "Green", "Green", "Green"],
        note=["Two RACI gaps flagged at TOR review.",
              "Ownership resolved for ETL workstream.",
              "Cutover risk raised to high pending capacity test.",
              "Capacity test passed; back on plan.",
              "One milestone slipped into next month, no scope impact.",
              "Tracking to TOR; decommission CR approved."]),
    "P-003": dict(
        ms_plan=[2, 3, 4, 5, 7, 8],       ms_done=[2, 3, 3, 3, 4, 5],
        dl_due=[2, 3, 4, 6, 8, 10],       dl_acc=[2, 3, 3, 4, 5, 6],
        spend=[58000, 112000, 168000, 232000, 296000, 351000],
        cr_raised=[0, 0, 1, 3, 4, 5],     cr_appr=[0, 0, 1, 2, 3, 4],
        risks=[4, 5, 7, 8, 9, 9],         high=[1, 1, 2, 3, 3, 3],
        gaps=[0, 1, 2, 3, 3, 4],
        rag=["Green", "Amber", "Amber", "Red", "Red", "Red"],
        note=["Baselined against draft standard.",
              "Regulator clarification pending, first slip.",
              "Scope grew: evidence automation added by CR.",
              "Budget forecast breached; escalated to sponsor.",
              "Four unowned deliverables, accountability unresolved.",
              "Overspent vs TOR budget. Re-baseline decision needed at SteerCo."]),
    "P-004": dict(
        ms_plan=[1, 2, 3, 5, 6, 8],       ms_done=[1, 2, 3, 5, 6, 8],
        dl_due=[1, 2, 3, 4, 6, 8],        dl_acc=[1, 2, 3, 4, 6, 8],
        spend=[60000, 125000, 190000, 268000, 340000, 415000],
        cr_raised=[0, 0, 0, 1, 1, 1],     cr_appr=[0, 0, 0, 1, 1, 1],
        risks=[2, 2, 3, 3, 2, 2],         high=[0, 0, 0, 0, 0, 0],
        gaps=[0, 0, 0, 0, 0, 0],
        rag=["Green", "Green", "Green", "Green", "Green", "Green"],
        note=["Entity setup started on schedule.",
              "Local counsel engaged, no issues.",
              "Hiring pipeline ahead of plan.",
              "Pricing CR approved, budget unchanged.",
              "First market live.",
              "Both markets on track to TOR end date."]),
    "P-005": dict(
        ms_plan=[1, 2, 3, 4, 6, 7],       ms_done=[1, 2, 3, 4, 5, 6],
        dl_due=[1, 2, 3, 5, 7, 9],        dl_acc=[1, 2, 3, 4, 6, 7],
        spend=[30000, 62000, 95000, 138000, 180000, 224000],
        cr_raised=[0, 1, 1, 1, 2, 2],     cr_appr=[0, 0, 0, 0, 1, 1],
        risks=[3, 3, 3, 4, 4, 3],         high=[0, 0, 1, 1, 1, 0],
        gaps=[1, 1, 1, 0, 0, 1],
        rag=["Green", "Green", "Amber", "Amber", "Green", "Green"],
        note=["Baseline agreed with operations.",
              "Vendor renegotiation opened.",
              "Automation vendor risk raised to high.",
              "Mitigation in place, second vendor shortlisted.",
              "Vendor risk closed; CR approved for extra automation.",
              "Two deliverables pending acceptance, otherwise on plan."]),
}

DELIVERABLES = [
    # id, project, deliverable, TOR ref, R, A, C, I, due, status
    ("D-001", "P-001", "Portal design system sign-off", "TOR 4.1", "R. Patel", "A. Mensah", "Design guild", "Steering group", dt.date(2026, 4, 30), "Accepted"),
    ("D-002", "P-001", "Authentication service cutover", "TOR 4.2", "K. Osei", "R. Patel", "Security", "Service desk", dt.date(2026, 7, 31), "Submitted"),
    ("D-003", "P-001", "Self-service billing module", "TOR 4.3", "K. Osei", "", "Finance ops", "Client services", dt.date(2026, 9, 30), "In Progress"),
    ("D-004", "P-001", "Active account migration", "TOR 4.4", "J. Silva", "", "Data team", "Steering group", dt.date(2026, 10, 30), "Not Started"),
    ("D-005", "P-002", "ETL rebuild - phase 1", "TOR 3.1", "S. Kowalski", "L. Njoku", "Platform", "BI users", dt.date(2026, 5, 29), "Accepted"),
    ("D-006", "P-002", "Warehouse cutover runbook", "TOR 3.2", "N. Abebe", "S. Kowalski", "Ops", "All staff", dt.date(2026, 8, 31), "Submitted"),
    ("D-007", "P-002", "BI re-point and validation", "TOR 3.3", "N. Abebe", "S. Kowalski", "Finance", "BI users", dt.date(2026, 10, 30), "In Progress"),
    ("D-008", "P-003", "Control redesign pack", "TOR 2.1", "M. Haddad", "D. Ferreira", "Internal audit", "Board", dt.date(2026, 5, 29), "Accepted"),
    ("D-009", "P-003", "Evidence automation build", "TOR 2.4 (CR-03)", "P. Lindqvist", "", "Compliance", "Board", dt.date(2026, 8, 31), "In Progress"),
    ("D-010", "P-003", "Submission template set", "TOR 2.2", "P. Lindqvist", "", "Regulator liaison", "Board", dt.date(2026, 9, 30), "Not Started"),
    ("D-011", "P-003", "Sign-off workflow", "TOR 2.3", "M. Haddad", "", "Legal", "Board", dt.date(2026, 10, 30), "Not Started"),
    ("D-012", "P-003", "Historic restatement review", "TOR 2.5 (CR-04)", "M. Haddad", "", "Finance", "Board", dt.date(2026, 10, 30), "Not Started"),
    ("D-013", "P-004", "APAC entity registration", "TOR 5.1", "T. Yamamoto", "A. Mensah", "Legal", "Exec", dt.date(2026, 5, 29), "Accepted"),
    ("D-014", "P-004", "Localised pricing model", "TOR 5.2", "H. Tran", "T. Yamamoto", "Finance", "Sales", dt.date(2026, 7, 31), "Accepted"),
    ("D-015", "P-004", "Regional support coverage", "TOR 5.3", "H. Tran", "T. Yamamoto", "Support", "Clients", dt.date(2026, 11, 30), "In Progress"),
    ("D-016", "P-005", "Process redesign blueprint", "TOR 6.1", "C. Duarte", "L. Njoku", "Ops leads", "Exec", dt.date(2026, 5, 29), "Accepted"),
    ("D-017", "P-005", "Tier-1 automation release", "TOR 6.2", "E. Boateng", "C. Duarte", "Service desk", "Ops", dt.date(2026, 8, 31), "Submitted"),
    ("D-018", "P-005", "Vendor contract renegotiation", "TOR 6.3", "E. Boateng", "", "Procurement", "Finance", dt.date(2026, 9, 30), "In Progress"),
]

RISKS = [
    # id, project, type, description, likelihood, impact, owner, mitigation, status, raised, target
    ("R-001", "P-001", "Risk", "Auth vendor cannot meet the agreed cutover window", 3, 4, "R. Patel", "Parallel-run window booked; fallback to extended legacy support", "Mitigating", dt.date(2026, 4, 14), dt.date(2026, 9, 30)),
    ("R-002", "P-001", "Issue", "Design sign-off slipped two weeks against the TOR schedule", 5, 3, "R. Patel", "Recovery plan agreed with sponsor; two milestones re-sequenced", "Open", dt.date(2026, 5, 12), dt.date(2026, 9, 15)),
    ("R-003", "P-001", "Risk", "Billing scope creep beyond TOR 4.3 without an approved CR", 3, 3, "A. Mensah", "CR-02 tabled at SteerCo for decision", "Open", dt.date(2026, 7, 8), dt.date(2026, 9, 30)),
    ("R-004", "P-002", "Risk", "Cutover exceeds the agreed maintenance window", 2, 5, "S. Kowalski", "Capacity test passed; rehearsal booked for October", "Mitigating", dt.date(2026, 5, 6), dt.date(2026, 10, 15)),
    ("R-005", "P-002", "Risk", "Legacy warehouse licence renews before decommission", 3, 3, "L. Njoku", "Decommission CR approved; renewal deferred to monthly terms", "Closed", dt.date(2026, 4, 2), dt.date(2026, 8, 1)),
    ("R-006", "P-003", "Issue", "Forecast spend exceeds the TOR-approved budget", 5, 5, "D. Ferreira", "Re-baseline paper going to SteerCo; scope freeze in force", "Open", dt.date(2026, 6, 10), dt.date(2026, 9, 15)),
    ("R-007", "P-003", "Issue", "Four deliverables have no accountable owner", 5, 4, "D. Ferreira", "Accountability workshop scheduled with the sponsor", "Open", dt.date(2026, 7, 3), dt.date(2026, 9, 12)),
    ("R-008", "P-003", "Risk", "Regulator clarification may reopen the control design", 3, 4, "M. Haddad", "Formal query submitted; contingency in the plan", "Open", dt.date(2026, 4, 21), dt.date(2026, 10, 30)),
    ("R-009", "P-003", "Risk", "Scope added by CR-03/CR-04 not funded in the TOR", 4, 4, "D. Ferreira", "Funding request bundled with the re-baseline paper", "Open", dt.date(2026, 6, 25), dt.date(2026, 9, 15)),
    ("R-010", "P-004", "Risk", "Local hiring lead times slip in the second market", 2, 3, "T. Yamamoto", "Agency retained; pipeline running two candidates deep", "Mitigating", dt.date(2026, 5, 18), dt.date(2026, 11, 30)),
    ("R-011", "P-004", "Risk", "Currency movement erodes the localised pricing margin", 2, 3, "H. Tran", "Quarterly price review clause added to contracts", "Open", dt.date(2026, 7, 15), dt.date(2026, 12, 18)),
    ("R-012", "P-005", "Risk", "Automation vendor stability after the funding round", 2, 4, "C. Duarte", "Second vendor shortlisted; source code escrow agreed", "Closed", dt.date(2026, 5, 20), dt.date(2026, 8, 14)),
    ("R-013", "P-005", "Risk", "Benefit realisation depends on a CSAT floor being held", 3, 3, "C. Duarte", "CSAT tracked weekly; rollback trigger defined", "Mitigating", dt.date(2026, 6, 30), dt.date(2026, 9, 30)),
    ("R-014", "P-002", "Risk", "Source system owners slow to sign off data contracts", 3, 3, "S. Kowalski", "Contract templates pre-agreed; weekly chase in the workstream call", "Open", dt.date(2026, 6, 8), dt.date(2026, 10, 30)),
    ("R-015", "P-002", "Risk", "BI report parity testing may run past the agreed window", 3, 4, "N. Abebe", "Parity suite automated; top 40 reports prioritised", "Mitigating", dt.date(2026, 7, 1), dt.date(2026, 11, 27)),
    ("R-016", "P-002", "Issue", "Two ETL jobs exceed the nightly batch window", 4, 3, "N. Abebe", "Partitioning rework in flight; interim staggered schedule", "Open", dt.date(2026, 7, 22), dt.date(2026, 9, 30)),
    ("R-017", "P-002", "Risk", "Cloud run-rate tracking above the TOR estimate", 2, 4, "S. Kowalski", "Reserved capacity purchased; monthly cost review added", "Mitigating", dt.date(2026, 8, 5), dt.date(2026, 12, 18)),
    ("R-018", "P-003", "Risk", "Evidence automation depends on a single contractor", 3, 4, "M. Haddad", "Knowledge transfer sessions booked; handover pack required", "Mitigating", dt.date(2026, 6, 17), dt.date(2026, 10, 15)),
    ("R-019", "P-003", "Risk", "Template changes require a second legal review", 3, 3, "M. Haddad", "Legal slot pre-booked for the October cycle", "Open", dt.date(2026, 7, 9), dt.date(2026, 10, 16)),
    ("R-020", "P-003", "Issue", "Control testing environment unavailable for two weeks in September", 4, 3, "P. Lindqvist", "Testing re-sequenced; shared environment booked as fallback", "Open", dt.date(2026, 8, 12), dt.date(2026, 9, 26)),
    ("R-021", "P-003", "Risk", "Sign-off workflow tooling licence not yet procured", 3, 3, "D. Ferreira", "Procurement raised; manual workflow as interim", "Open", dt.date(2026, 8, 3), dt.date(2026, 9, 30)),
    ("R-022", "P-003", "Risk", "Reporting calendar clashes with year-end close", 2, 4, "D. Ferreira", "Dates agreed with finance; submission moved one week earlier", "Mitigating", dt.date(2026, 8, 19), dt.date(2026, 11, 30)),
    ("R-023", "P-005", "Risk", "Process redesign adoption varies by region", 3, 3, "C. Duarte", "Regional champions appointed; adoption tracked weekly", "Open", dt.date(2026, 7, 14), dt.date(2026, 9, 30)),
    ("R-024", "P-005", "Risk", "Benefit baseline disputed by finance", 2, 4, "C. Duarte", "Baseline restated with finance and re-signed by the sponsor", "Mitigating", dt.date(2026, 8, 7), dt.date(2026, 9, 26)),
]

LIST_RAG = ["Green", "Amber", "Red"]
LIST_DSTATUS = ["Not Started", "In Progress", "Submitted", "Accepted", "Descoped"]
LIST_RSTATUS = ["Open", "Mitigating", "Closed"]
LIST_RTYPE = ["Risk", "Issue"]
LIST_SCORE = [1, 2, 3, 4, 5]

wb = Workbook()

# =============================================================== READ ME =====
ws = wb.active
ws.title = "Read Me"
ws.sheet_properties.tabColor = NAVY
ws.sheet_view.showGridLines = False
widths(ws, {"A": 3, "B": 26, "C": 96})

title_block(ws, "  Project Strategy TOR Dashboard - monthly team pack",
            "  Tracks delivery against what each project's Terms of Reference committed to. "
            "One reporting cycle per month.", 4)

r = 4


def section(text):
    global r
    c = ws.cell(row=r, column=2, value=text)
    c.font = Font(name=FONT, size=11, bold=True, color=NAVY)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
    ws.cell(row=r, column=2).border = Border(bottom=Side(style="medium", color=LIGHT))
    r += 1


def line(label, text, label_color=SLATE):
    global r
    a = ws.cell(row=r, column=2, value=label)
    a.font = Font(name=FONT, size=9, bold=True, color=label_color)
    a.alignment = Alignment(vertical="top", wrap_text=True)
    b = ws.cell(row=r, column=3, value=text)
    b.font = Font(name=FONT, size=9)
    b.alignment = Alignment(vertical="top", wrap_text=True)
    r += 1


def gap(n=1):
    global r
    r += n


section("What this workbook is for")
line("", "A single monthly pack the team can walk through in a governance or SteerCo meeting. "
         "Every metric answers one question: is this project still delivering what its Terms of "
         "Reference said it would, for the money and by the dates the TOR approved?")
gap()

section("The monthly cycle - five steps")
line("1.  Update registers",
     "Add or update rows on 'Deliverables & RACI' and 'Risks & Issues' as things change during the month.")
line("2.  Add the month's rows",
     "On 'Monthly Log', add one row per active project for the new month. Copy the previous month's "
     "block down and update the numbers. All figures are CUMULATIVE TO DATE, not in-month.")
line("3.  Copy the live counts",
     "Copy Open Risks and High Risks from 'Risks & Issues', and RACI Gaps from 'Deliverables & RACI', "
     "into the month's row. Both sheets show these per project at the top right. Freezing them into the "
     "log is what gives the trend charts their history - the registers only ever show today.")
line("4.  Set the reporting month",
     "On 'Dashboard', set the reporting month in cell C4. Everything else recalculates.")
line("5.  Review and present",
     "Walk the Dashboard exception table, then 'Charts' for the trend. Red and Amber rows are the agenda.")
gap()

section("Tab guide")
line("Read Me", "This page.")
line("TOR Register", "The baseline. One row per project holding what the signed TOR committed to: "
                     "objective, scope boundaries, dates, approved budget, planned milestone and "
                     "deliverable counts. Change this only through an approved change request.")
line("Monthly Log", "The data entry surface. One row per project per month, cumulative to date. "
                    "This is the only sheet that needs touching in a normal month.")
line("Deliverables & RACI", "Deliverable-level register mapped back to TOR clauses, with Responsible / "
                            "Accountable / Consulted / Informed. A blank Accountable is a governance gap "
                            "and is counted for you.")
line("Risks & Issues", "Risk and issue register with likelihood x impact scoring and live counts per project.")
line("Dashboard", "The monthly view. Portfolio tiles, then a per-project table with a calculated RAG.")
line("Charts", "Six-plus month trend for the portfolio, plus per-project comparison charts.")
line("Lists", "Dropdown values. Extend here if the team uses different status wording.")
gap()

section("How each metric is defined")
line("Scope adherence %", "Deliverables accepted to date / deliverables due to date. Measures whether "
                          "the TOR's promised outputs are actually landing and being accepted, not just started.")
line("Milestone hit rate %", "Milestones achieved to date / milestones planned to date. Schedule health "
                             "against the TOR baseline.")
line("Budget used %", "Spend to date / TOR-approved budget. Over 100% means the project has spent past "
                      "what the TOR authorised, regardless of how much work remains.")
line("Budget variance", "TOR-approved budget less spend to date. Negative means overspent.")
line("Approved scope changes", "Cumulative change requests approved. A rising count with a flat budget is "
                               "the classic TOR drift signal - scope grew, funding did not.")
line("RACI gaps", "Deliverables with no accountable owner named. Any number above zero is a governance "
                  "finding, not a delivery one.")
line("Calculated RAG", "Computed objectively from the thresholds in Dashboard C10:C14, so it cannot be "
                       "talked up or down. Shown next to the PM's own RAG - a disagreement between the "
                       "two is itself worth discussing.")
gap()

section("Colour legend")
for lbl, col, fil, desc in [
    ("Blue text", BLUE_INPUT, None, "A number or value you type in. Safe to edit."),
    ("Yellow fill", BLACK, YELLOW_FILL, "Key input you are expected to set - reporting month and RAG thresholds."),
    ("Black text", BLACK, None, "Formula calculated on that sheet. Do not overwrite."),
    ("Green text", GREEN_LINK, None, "Value pulled from another sheet. Do not overwrite."),
]:
    a = ws.cell(row=r, column=2, value=lbl)
    a.font = Font(name=FONT, size=9, bold=True, color=col)
    if fil:
        a.fill = PatternFill("solid", fgColor=fil)
    a.alignment = Alignment(vertical="center")
    b = ws.cell(row=r, column=3, value=desc)
    b.font = Font(name=FONT, size=9)
    r += 1
gap()

section("Capacity and assumptions")
line("Row capacity", f"TOR Register {TOR_LAST - TOR_FIRST + 1} projects; Monthly Log "
                     f"{LOG_LAST - LOG_FIRST + 1} rows (that is {(LOG_LAST - LOG_FIRST + 1) // 12} "
                     f"projects for 12 months); Deliverables and Risks {DEL_LAST - DEL_FIRST + 1} rows each. "
                     "Formulas already cover every row in those ranges - just type into the next empty row.")
line("Month format", "Always enter the FIRST DAY of the month (e.g. 2026-09-01). The Dashboard matches "
                     "on the exact date, so a mid-month date will not be picked up.")
line("Example data", "The workbook ships with six months of EXAMPLE data for five fictional projects so "
                     "the formulas and charts can be seen working. Names and figures are invented. "
                     "Delete rows 4 and below on TOR Register, Monthly Log, Deliverables & RACI and "
                     "Risks & Issues before real use.")
line("Currency", "All money is in whole dollars. Change the number formats if the team reports in another unit.")
line("Source", "Structure and metric definitions were specified for this request; there is no external "
               "data source behind the example figures.")

for row in ws.iter_rows(min_row=4, max_row=r, min_col=2, max_col=3):
    for c in row:
        if c.alignment.wrap_text is None:
            c.alignment = Alignment(vertical="top", wrap_text=True)

# ========================================================== TOR REGISTER =====
tor = wb.create_sheet("TOR Register")
tor.sheet_properties.tabColor = SLATE
TOR_H = ["Project ID", "Project Name", "Strategic Pillar", "Sponsor",
         "Project Manager", "TOR Approved", "Planned Start", "Planned End",
         "TOR Approved Budget ($)", "Planned Milestones (total)",
         "Planned Deliverables (total)", "TOR Objective",
         "Key In-Scope (per TOR)", "Key Out-of-Scope (per TOR)"]
title_block(tor, "  TOR Register - the approved baseline",
            "  One row per project, straight from the signed Terms of Reference. "
            "Change only via an approved CR. EXAMPLE DATA - replace with the team's projects.",
            len(TOR_H))
header_row(tor, 3, TOR_H)
widths(tor, {"A": 10, "B": 26, "C": 20, "D": 14, "E": 15, "F": 13, "G": 13,
             "H": 13, "I": 18, "J": 13, "K": 13, "L": 46, "M": 42, "N": 38})

for i, p in enumerate(PROJECTS):
    row = TOR_FIRST + i
    for j, v in enumerate(p, start=1):
        c = tor.cell(row=row, column=j, value=v)
        fmt = DATE if j in (6, 7, 8) else (CUR if j == 9 else (INT if j in (10, 11) else None))
        body(c, fmt=fmt, color=BLUE_INPUT, wrap=j >= 12,
             align="center" if j in (1, 6, 7, 8) else None)
    tor.row_dimensions[row].height = 30

for row in range(TOR_FIRST + len(PROJECTS), TOR_LAST + 1):
    for j in range(1, len(TOR_H) + 1):
        fmt = DATE if j in (6, 7, 8) else (CUR if j == 9 else (INT if j in (10, 11) else None))
        body(tor.cell(row=row, column=j), fmt=fmt, color=BLUE_INPUT)
band(tor, TOR_FIRST, TOR_LAST, len(TOR_H))
tor.freeze_panes = "C4"
tor.auto_filter.ref = f"A3:{get_column_letter(len(TOR_H))}{TOR_LAST}"

# =========================================================== MONTHLY LOG =====
log = wb.create_sheet("Monthly Log")
log.sheet_properties.tabColor = SLATE
LOG_H = ["Month (1st of month)", "Project ID", "Milestones Planned to Date",
         "Milestones Achieved to Date", "Deliverables Due to Date",
         "Deliverables Accepted to Date", "Budget Spent to Date ($)",
         "Change Requests Raised (cum.)", "Change Requests Approved (cum.)",
         "Open Risks (snapshot)", "High Risks (snapshot)",
         "RACI Gaps (snapshot)", "PM RAG", "Commentary", "Match Key (auto)"]
title_block(log, "  Monthly Log - the only sheet to update each month",
            "  One row per project per month. ALL FIGURES ARE CUMULATIVE TO DATE. "
            "Enter the first day of the month. EXAMPLE DATA - delete before real use.",
            len(LOG_H))
header_row(log, 3, LOG_H)
widths(log, {"A": 15, "B": 10, "C": 12, "D": 12, "E": 12, "F": 12, "G": 16,
             "H": 12, "I": 12, "J": 11, "K": 10, "L": 10, "M": 9, "N": 52, "O": 18})

row = LOG_FIRST
for m_i, month in enumerate(MONTHS):
    for pid in [p[0] for p in PROJECTS]:
        d = LOG[pid]
        vals = [month, pid, d["ms_plan"][m_i], d["ms_done"][m_i], d["dl_due"][m_i],
                d["dl_acc"][m_i], d["spend"][m_i], d["cr_raised"][m_i],
                d["cr_appr"][m_i], d["risks"][m_i], d["high"][m_i], d["gaps"][m_i],
                d["rag"][m_i], d["note"][m_i]]
        for j, v in enumerate(vals, start=1):
            c = log.cell(row=row, column=j, value=v)
            fmt = MONTH if j == 1 else (CUR if j == 7 else (INT if 3 <= j <= 12 else None))
            body(c, fmt=fmt, color=BLUE_INPUT, wrap=(j == 14),
                 align="center" if j in (1, 2, 13) else None)
        row += 1

for r_ in range(LOG_FIRST, LOG_LAST + 1):
    if r_ >= row:
        for j in range(1, 15):
            fmt = MONTH if j == 1 else (CUR if j == 7 else (INT if 3 <= j <= 12 else None))
            body(log.cell(row=r_, column=j), fmt=fmt, color=BLUE_INPUT,
                 align="center" if j in (1, 2, 13) else None)
    k = log.cell(row=r_, column=15,
                 value=f'=IF($B{r_}="","",TEXT($A{r_},"YYYY-MM")&"|"&$B{r_})')
    body(k, color=GREY, align="center")

band(log, LOG_FIRST, LOG_LAST, len(LOG_H))
log.freeze_panes = "C4"
log.auto_filter.ref = f"A3:{get_column_letter(len(LOG_H))}{LOG_LAST}"

# ==================================================== DELIVERABLES & RACI =====
dl = wb.create_sheet("Deliverables & RACI")
dl.sheet_properties.tabColor = SLATE
DL_H = ["Deliverable ID", "Project ID", "Deliverable (per TOR)", "TOR Clause Ref",
        "Responsible", "Accountable", "Consulted", "Informed", "Due Date", "Status"]
title_block(dl, "  Deliverables & RACI - TOR outputs and who owns them",
            "  A blank Accountable is a governance gap and is counted automatically. "
            "EXAMPLE DATA - delete before real use.", len(DL_H))
header_row(dl, 3, DL_H)
widths(dl, {"A": 13, "B": 10, "C": 36, "D": 17, "E": 15, "F": 15, "G": 17,
            "H": 15, "I": 12, "J": 13, "K": 3, "L": 10, "M": 13, "N": 13, "O": 13})

for i, d in enumerate(DELIVERABLES):
    r_ = DEL_FIRST + i
    for j, v in enumerate(d, start=1):
        c = dl.cell(row=r_, column=j, value=v)
        body(c, fmt=DATE if j == 9 else None, color=BLUE_INPUT, wrap=(j == 3),
             align="center" if j in (1, 2, 9, 10) else None)
        if j == 6 and v == "":
            c.fill = PatternFill("solid", fgColor="FCE4E4")
for r_ in range(DEL_FIRST + len(DELIVERABLES), DEL_LAST + 1):
    for j in range(1, len(DL_H) + 1):
        body(dl.cell(row=r_, column=j), fmt=DATE if j == 9 else None,
             color=BLUE_INPUT, align="center" if j in (1, 2, 9, 10) else None)
band(dl, DEL_FIRST, DEL_LAST, len(DL_H))

# live per-project counts (step 3 of the monthly cycle)
dl["L2"] = "Live register counts"
dl["L2"].font = Font(name=FONT, size=9, bold=True, italic=True, color=NAVY)
for j, h in enumerate(["Project", "In Register", "Accepted",
                       "RACI Gaps -> copy to log"], start=12):
    c = dl.cell(row=3, column=j, value=h)
    c.font = Font(name=FONT, size=9, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=SLATE)
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    c.border = BOX
for i, p in enumerate(PROJECTS):
    r_ = 4 + i
    body(dl.cell(row=r_, column=12, value=p[0]), color=GREEN_LINK, align="center")
    body(dl.cell(row=r_, column=13,
                 value=f'=COUNTIFS($B${DEL_FIRST}:$B${DEL_LAST},$L{r_})'),
         fmt=INT, align="center")
    body(dl.cell(row=r_, column=14,
                 value=f'=COUNTIFS($B${DEL_FIRST}:$B${DEL_LAST},$L{r_},'
                       f'$J${DEL_FIRST}:$J${DEL_LAST},"Accepted")'), fmt=INT, align="center")
    body(dl.cell(row=r_, column=15,
                 value=f'=COUNTIFS($B${DEL_FIRST}:$B${DEL_LAST},$L{r_},'
                       f'$F${DEL_FIRST}:$F${DEL_LAST},"")'), fmt=INT, align="center")
note = dl.cell(row=4 + len(PROJECTS) + 1, column=12,
               value="Only the RACI gap count is copied into the Monthly Log. This register holds the "
                     "major TOR deliverables and their ownership; the log's 'due / accepted' counts come "
                     "from the full delivery plan, so they are normally the larger number.")
note.font = Font(name=FONT, size=8, italic=True, color=GREY)
note.alignment = Alignment(vertical="top", wrap_text=True)
dl.merge_cells(start_row=4 + len(PROJECTS) + 1, start_column=12,
               end_row=4 + len(PROJECTS) + 3, end_column=15)
dl.freeze_panes = "C4"
dl.auto_filter.ref = f"A3:{get_column_letter(len(DL_H))}{DEL_LAST}"

# ========================================================= RISKS & ISSUES =====
rk = wb.create_sheet("Risks & Issues")
rk.sheet_properties.tabColor = SLATE
RK_H = ["ID", "Project ID", "Type", "Description", "Likelihood (1-5)",
        "Impact (1-5)", "Score", "Severity", "Owner", "Mitigation / Action",
        "Status", "Raised", "Target Close"]
title_block(rk, "  Risks & Issues register",
            "  Score = likelihood x impact. Severity and the live counts are calculated. "
            "EXAMPLE DATA - delete before real use.", len(RK_H))
header_row(rk, 3, RK_H)
widths(rk, {"A": 9, "B": 10, "C": 9, "D": 46, "E": 11, "F": 10, "G": 8, "H": 11,
            "I": 14, "J": 46, "K": 12, "L": 12, "M": 12, "N": 3, "O": 10,
            "P": 11, "Q": 11, "R": 11})

for i, k in enumerate(RISKS):
    r_ = RSK_FIRST + i
    rid, pid, typ, desc, lik, imp, owner, mit, status, raised, target = k
    vals = [rid, pid, typ, desc, lik, imp, None, None, owner, mit, status, raised, target]
    for j, v in enumerate(vals, start=1):
        c = rk.cell(row=r_, column=j, value=v)
        body(c, fmt=DATE if j in (12, 13) else None, color=BLUE_INPUT,
             wrap=j in (4, 10), align="center" if j in (1, 2, 3, 5, 6, 11, 12, 13) else None)
for r_ in range(RSK_FIRST, RSK_LAST + 1):
    if r_ >= RSK_FIRST + len(RISKS):
        for j in list(range(1, 7)) + list(range(9, 14)):
            body(rk.cell(row=r_, column=j), fmt=DATE if j in (12, 13) else None,
                 color=BLUE_INPUT, align="center" if j in (1, 2, 3, 5, 6, 11, 12, 13) else None)
    body(rk.cell(row=r_, column=7, value=f'=IF($E{r_}="","",$E{r_}*$F{r_})'),
         fmt=INT, align="center")
    body(rk.cell(row=r_, column=8,
                 value=f'=IF($G{r_}="","",IF($G{r_}>=15,"High",IF($G{r_}>=8,"Medium","Low")))'),
         align="center", bold=True)
band(rk, RSK_FIRST, RSK_LAST, len(RK_H))

rk["O2"] = "Live counts - copy into the Monthly Log"
rk["O2"].font = Font(name=FONT, size=9, bold=True, italic=True, color=NAVY)
for j, h in enumerate(["Project", "Open Risks -> copy to log",
                       "High Risks -> copy to log"], start=15):
    c = rk.cell(row=3, column=j, value=h)
    c.font = Font(name=FONT, size=9, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=SLATE)
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    c.border = BOX
for i, p in enumerate(PROJECTS):
    r_ = 4 + i
    body(rk.cell(row=r_, column=15, value=p[0]), color=GREEN_LINK, align="center")
    # "Open" for reporting purposes = anything not yet closed.
    body(rk.cell(row=r_, column=16,
                 value=f'=COUNTIFS($B${RSK_FIRST}:$B${RSK_LAST},$O{r_},'
                       f'$K${RSK_FIRST}:$K${RSK_LAST},"Open")'
                       f'+COUNTIFS($B${RSK_FIRST}:$B${RSK_LAST},$O{r_},'
                       f'$K${RSK_FIRST}:$K${RSK_LAST},"Mitigating")'), fmt=INT, align="center")
    body(rk.cell(row=r_, column=17,
                 value=f'=COUNTIFS($B${RSK_FIRST}:$B${RSK_LAST},$O{r_},'
                       f'$H${RSK_FIRST}:$H${RSK_LAST},"High",'
                       f'$K${RSK_FIRST}:$K${RSK_LAST},"<>Closed")'), fmt=INT, align="center")

for col, rng in (("H", "H"),):
    rk.conditional_formatting.add(
        f"{col}{RSK_FIRST}:{col}{RSK_LAST}",
        CellIsRule(operator="equal", formula=['"High"'], fill=RAG_FILL["Red"]))
    rk.conditional_formatting.add(
        f"{col}{RSK_FIRST}:{col}{RSK_LAST}",
        CellIsRule(operator="equal", formula=['"Medium"'], fill=RAG_FILL["Amber"]))
    rk.conditional_formatting.add(
        f"{col}{RSK_FIRST}:{col}{RSK_LAST}",
        CellIsRule(operator="equal", formula=['"Low"'], fill=RAG_FILL["Green"]))
rk.freeze_panes = "C4"
rk.auto_filter.ref = f"A3:{get_column_letter(len(RK_H))}{RSK_LAST}"

# ============================================================== DASHBOARD =====
db = wb.create_sheet("Dashboard")
db.sheet_properties.tabColor = "C00000"
db.sheet_view.showGridLines = False
DB_H = ["Project ID", "Project Name", "PM", "TOR Budget ($)", "Spent to Date ($)",
        "Budget Used %", "Budget Variance ($)", "Milestones Planned",
        "Milestones Achieved", "Milestone Hit Rate %", "Deliverables Due",
        "Deliverables Accepted", "Scope Adherence %", "Approved Scope Changes",
        "Open Risks", "High Risks", "RACI Gaps", "PM RAG", "Calculated RAG",
        "PM Commentary"]
title_block(db, "  Monthly Dashboard - delivery against TOR",
            "  Set the reporting month in C4. Everything below recalculates. "
            "Red and Amber rows are the meeting agenda.", len(DB_H))
widths(db, {"A": 10, "B": 25, "C": 14, "D": 14, "E": 15, "F": 12, "G": 15,
            "J": 13, "M": 14, "N": 13, "O": 10, "P": 10, "Q": 10, "R": 10,
            "S": 13, "T": 56})
for col in "HIKL":
    db.column_dimensions[col].width = 11

# --- controls
db["B4"] = "Reporting month:"
db["B4"].font = Font(name=FONT, size=10, bold=True, color=NAVY)
db["C4"] = REPORT_MONTH
db["C4"].font = Font(name=FONT, size=10, bold=True, color=BLUE_INPUT)
db["C4"].fill = PatternFill("solid", fgColor=YELLOW_FILL)
db["C4"].number_format = MONTH
db["C4"].alignment = Alignment(horizontal="center")
db["C4"].border = BOX
db["D4"] = "<- type the FIRST DAY of the month, e.g. 2026-09-01"
db["D4"].font = Font(name=FONT, size=9, italic=True, color=GREY)

db["B6"] = "RAG thresholds (edit to match the team's tolerance)"
db["B6"].font = Font(name=FONT, size=10, bold=True, color=NAVY)
THRESHOLDS = [
    ("Milestone hit rate - Amber below", 0.90, PCT,
     "Below this, schedule is off the TOR baseline enough to flag."),
    ("Milestone hit rate - Red below", 0.75, PCT,
     "Below this, the TOR schedule is not credible without a re-baseline."),
    ("Budget used - Amber above", 0.95, PCT,
     "Approaching the TOR-authorised budget."),
    ("Budget used - Red above", 1.00, PCT,
     "Spent past what the TOR authorised."),
    ("High risks - Red at or above", 2, INT,
     "This many unclosed high-severity risks forces a Red."),
]
for i, (lbl, val, fmt, note) in enumerate(THRESHOLDS):
    r_ = 7 + i
    a = db.cell(row=r_, column=2, value=lbl)
    a.font = Font(name=FONT, size=9, color=SLATE)
    c = db.cell(row=r_, column=3, value=val)
    body(c, fmt=fmt, color=BLUE_INPUT, bold=True, align="center", fill=YELLOW_FILL)
    n = db.cell(row=r_, column=4, value=note)
    n.font = Font(name=FONT, size=8, italic=True, color=GREY)
T_MS_AMBER, T_MS_RED, T_BU_AMBER, T_BU_RED, T_HR_RED = ("$C$7", "$C$8", "$C$9", "$C$10", "$C$11")

# --- portfolio tiles
db["G6"] = "Portfolio this month"
db["G6"].font = Font(name=FONT, size=10, bold=True, color=NAVY)

PROW_FIRST = 16
PROW_LAST = PROW_FIRST + (TOR_LAST - TOR_FIRST)  # mirrors TOR Register capacity

TILES = [
    ("Projects reporting", f'=COUNTIFS(\'Monthly Log\'!$A${LOG_FIRST}:$A${LOG_LAST},$C$4)', INT),
    ("TOR budget ($)", f'=SUMIF($A${PROW_FIRST}:$A${PROW_LAST},"<>",$D${PROW_FIRST}:$D${PROW_LAST})', CUR),
    ("Spent to date ($)", f'=SUM($E${PROW_FIRST}:$E${PROW_LAST})', CUR),
    ("Budget used %", f'=IF(SUM($D${PROW_FIRST}:$D${PROW_LAST})=0,"",'
                      f'SUM($E${PROW_FIRST}:$E${PROW_LAST})/SUM($D${PROW_FIRST}:$D${PROW_LAST}))', PCT),
    ("Milestone hit rate %", f'=IF(SUM($H${PROW_FIRST}:$H${PROW_LAST})=0,"",'
                             f'SUM($I${PROW_FIRST}:$I${PROW_LAST})/SUM($H${PROW_FIRST}:$H${PROW_LAST}))', PCT),
    ("Scope adherence %", f'=IF(SUM($K${PROW_FIRST}:$K${PROW_LAST})=0,"",'
                          f'SUM($L${PROW_FIRST}:$L${PROW_LAST})/SUM($K${PROW_FIRST}:$K${PROW_LAST}))', PCT),
    ("Open risks", f'=SUM($O${PROW_FIRST}:$O${PROW_LAST})', INT),
    ("High risks", f'=SUM($P${PROW_FIRST}:$P${PROW_LAST})', INT),
    ("RACI gaps", f'=SUM($Q${PROW_FIRST}:$Q${PROW_LAST})', INT),
    ("Projects Red", f'=COUNTIF($S${PROW_FIRST}:$S${PROW_LAST},"Red")', INT),
    ("Projects Amber", f'=COUNTIF($S${PROW_FIRST}:$S${PROW_LAST},"Amber")', INT),
    ("Projects Green", f'=COUNTIF($S${PROW_FIRST}:$S${PROW_LAST},"Green")', INT),
]
for i, (lbl, formula, fmt) in enumerate(TILES):
    col = 7 + (i % 6) * 2          # G, I, K, M, O, Q
    r_ = 7 if i < 6 else 10
    a = db.cell(row=r_, column=col, value=lbl)
    a.font = Font(name=FONT, size=8, bold=True, color="FFFFFF")
    a.fill = PatternFill("solid", fgColor=SLATE)
    a.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    a.border = BOX
    db.merge_cells(start_row=r_, start_column=col, end_row=r_, end_column=col + 1)
    v = db.cell(row=r_ + 1, column=col, value=formula)
    v.font = Font(name=FONT, size=12, bold=True, color=NAVY)
    v.number_format = fmt
    v.alignment = Alignment(horizontal="center", vertical="center")
    v.fill = PatternFill("solid", fgColor=LIGHT)
    v.border = BOX
    db.merge_cells(start_row=r_ + 1, start_column=col, end_row=r_ + 1, end_column=col + 1)
    db.row_dimensions[r_].height = 24
    db.row_dimensions[r_ + 1].height = 22

# --- per-project table
db["A14"] = "Project detail for the reporting month"
db["A14"].font = Font(name=FONT, size=11, bold=True, color=NAVY)
header_row(db, 15, DB_H)

L_ID = f"'TOR Register'!$A${TOR_FIRST}:$A${TOR_LAST}"


def tor_lookup(col_letter, r_):
    return (f"=IFERROR(INDEX('TOR Register'!${col_letter}${TOR_FIRST}:${col_letter}${TOR_LAST},"
            f"MATCH($A{r_},{L_ID},0)),\"\")")


def log_sum(col_letter, r_):
    return (f"=SUMIFS('Monthly Log'!${col_letter}${LOG_FIRST}:${col_letter}${LOG_LAST},"
            f"'Monthly Log'!$A${LOG_FIRST}:$A${LOG_LAST},$C$4,"
            f"'Monthly Log'!$B${LOG_FIRST}:$B${LOG_LAST},$A{r_})")


def log_text(col_letter, r_):
    return (f"=IFERROR(INDEX('Monthly Log'!${col_letter}${LOG_FIRST}:${col_letter}${LOG_LAST},"
            f"MATCH(TEXT($C$4,\"YYYY-MM\")&\"|\"&$A{r_},"
            f"'Monthly Log'!$O${LOG_FIRST}:$O${LOG_LAST},0)),\"\")")


for i in range(PROW_LAST - PROW_FIRST + 1):
    r_ = PROW_FIRST + i
    tor_row = TOR_FIRST + i
    has_data = i < len(PROJECTS)

    # A: project id mirrors the TOR Register so the table grows with it
    body(db.cell(row=r_, column=1, value=f"=IF('TOR Register'!$A{tor_row}=\"\",\"\","
                                         f"'TOR Register'!$A{tor_row})"),
         color=GREEN_LINK, align="center", bold=True)
    body(db.cell(row=r_, column=2, value=tor_lookup("B", r_)), color=GREEN_LINK)
    body(db.cell(row=r_, column=3, value=tor_lookup("E", r_)), color=GREEN_LINK)
    body(db.cell(row=r_, column=4, value=tor_lookup("I", r_)), fmt=CUR, color=GREEN_LINK)
    body(db.cell(row=r_, column=5, value=log_sum("G", r_)), fmt=CUR, color=GREEN_LINK)
    body(db.cell(row=r_, column=6,
                 value=f'=IF(N($D{r_})=0,"",$E{r_}/$D{r_})'), fmt=PCT, align="center")
    body(db.cell(row=r_, column=7,
                 value=f'=IF($A{r_}="","",$D{r_}-$E{r_})'), fmt=CUR)
    body(db.cell(row=r_, column=8, value=log_sum("C", r_)), fmt=INT, color=GREEN_LINK, align="center")
    body(db.cell(row=r_, column=9, value=log_sum("D", r_)), fmt=INT, color=GREEN_LINK, align="center")
    body(db.cell(row=r_, column=10,
                 value=f'=IF($H{r_}=0,"",$I{r_}/$H{r_})'), fmt=PCT, align="center", bold=True)
    body(db.cell(row=r_, column=11, value=log_sum("E", r_)), fmt=INT, color=GREEN_LINK, align="center")
    body(db.cell(row=r_, column=12, value=log_sum("F", r_)), fmt=INT, color=GREEN_LINK, align="center")
    body(db.cell(row=r_, column=13,
                 value=f'=IF($K{r_}=0,"",$L{r_}/$K{r_})'), fmt=PCT, align="center", bold=True)
    body(db.cell(row=r_, column=14, value=log_sum("I", r_)), fmt=INT, color=GREEN_LINK, align="center")
    body(db.cell(row=r_, column=15, value=log_sum("J", r_)), fmt=INT, color=GREEN_LINK, align="center")
    body(db.cell(row=r_, column=16, value=log_sum("K", r_)), fmt=INT, color=GREEN_LINK, align="center")
    body(db.cell(row=r_, column=17, value=log_sum("L", r_)), fmt=INT, color=GREEN_LINK, align="center")
    body(db.cell(row=r_, column=18, value=log_text("M", r_)), color=GREEN_LINK,
         align="center", bold=True)

    # Calculated RAG - recomputed from raw counts, never from the display rates,
    # so an empty "nothing due yet" cell cannot read as 0%.
    rag = (
        f'=IF($A{r_}="","",'
        f'IF(AND($H{r_}=0,$K{r_}=0,$E{r_}=0),"Not started",'
        f'IF(OR('
        f'AND($D{r_}>0,$E{r_}/$D{r_}>{T_BU_RED}),'
        f'AND($H{r_}>0,$I{r_}/$H{r_}<{T_MS_RED}),'
        f'$P{r_}>={T_HR_RED}'
        f'),"Red",'
        f'IF(OR('
        f'AND($D{r_}>0,$E{r_}/$D{r_}>{T_BU_AMBER}),'
        f'AND($H{r_}>0,$I{r_}/$H{r_}<{T_MS_AMBER}),'
        f'AND($K{r_}>0,$L{r_}/$K{r_}<{T_MS_AMBER}),'
        f'$P{r_}>0,'
        f'$Q{r_}>0'
        f'),"Amber","Green"))))'
    )
    body(db.cell(row=r_, column=19, value=rag), align="center", bold=True)
    body(db.cell(row=r_, column=20, value=log_text("N", r_)), color=GREEN_LINK, wrap=True)
    db.row_dimensions[r_].height = 26 if has_data else 15

for col in ("R", "S"):
    for label, fill in RAG_FILL.items():
        db.conditional_formatting.add(
            f"{col}{PROW_FIRST}:{col}{PROW_LAST}",
            CellIsRule(operator="equal", formula=[f'"{label}"'], fill=fill))
db.freeze_panes = "D16"

# --- footnotes
fn = PROW_LAST + 2
db.cell(row=fn, column=1, value="Notes and assumptions").font = Font(
    name=FONT, size=10, bold=True, color=NAVY)
for i, t in enumerate([
    "All Monthly Log figures are cumulative to date, so every metric here is "
    "'position at the end of the reporting month', not in-month activity.",
    "Scope adherence = deliverables accepted / deliverables due to date. Approved scope changes are "
    "shown separately: a rising CR count against a flat TOR budget is scope drift, even when the "
    "adherence percentage looks healthy.",
    "Calculated RAG is derived only from the thresholds in C7:C11 and the raw counts, so it is "
    "reproducible. Where it disagrees with the PM RAG, the difference is the discussion.",
    "'Not started' appears when a project has no milestones due, no deliverables due and no spend "
    "in the reporting month.",
    "Rows are driven by the TOR Register: add a project there and it appears here automatically, "
    "up to the register's capacity.",
    "Open risks counts anything not Closed (Open + Mitigating) on the Risks & Issues register at "
    "the point the month's snapshot was taken.",
], start=0):
    c = db.cell(row=fn + 1 + i, column=1, value=f"- {t}")
    c.font = Font(name=FONT, size=8, italic=True, color=GREY)
    c.alignment = Alignment(vertical="top", wrap_text=True)
    db.merge_cells(start_row=fn + 1 + i, start_column=1, end_row=fn + 1 + i, end_column=13)
    db.row_dimensions[fn + 1 + i].height = 22

# ================================================================= CHARTS =====
ch = wb.create_sheet("Charts")
ch.sheet_properties.tabColor = "2E75B6"
ch.sheet_view.showGridLines = False
title_block(ch, "  Trend and comparison charts",
            "  The trend block is driven by the Monthly Log across all projects. "
            "Add a month to column A and the charts extend.", 12)

TREND_H = ["Month", "Milestones Planned", "Milestones Achieved", "Milestone Hit Rate %",
           "Deliverables Due", "Deliverables Accepted", "Scope Adherence %",
           "Budget Spent to Date ($)", "Open Risks", "High Risks", "RACI Gaps"]
header_row(ch, 4, TREND_H)
widths(ch, {"A": 13, "B": 12, "C": 12, "D": 12, "E": 12, "F": 12, "G": 12,
            "H": 17, "I": 10, "J": 10, "K": 10})

TR_FIRST = 5
TR_LAST = TR_FIRST + 23          # 24 months of capacity
for i in range(TR_LAST - TR_FIRST + 1):
    r_ = TR_FIRST + i
    val = MONTHS[i] if i < len(MONTHS) else None
    body(ch.cell(row=r_, column=1, value=val), fmt=MONTH, color=BLUE_INPUT, align="center")

    def month_sum(col_letter):
        return (f"=IF($A{r_}=\"\",\"\",SUMIFS('Monthly Log'!${col_letter}${LOG_FIRST}:${col_letter}${LOG_LAST},"
                f"'Monthly Log'!$A${LOG_FIRST}:$A${LOG_LAST},$A{r_}))")

    body(ch.cell(row=r_, column=2, value=month_sum("C")), fmt=INT, align="center")
    body(ch.cell(row=r_, column=3, value=month_sum("D")), fmt=INT, align="center")
    body(ch.cell(row=r_, column=4, value=f'=IF(N($B{r_})=0,"",$C{r_}/$B{r_})'), fmt=PCT, align="center")
    body(ch.cell(row=r_, column=5, value=month_sum("E")), fmt=INT, align="center")
    body(ch.cell(row=r_, column=6, value=month_sum("F")), fmt=INT, align="center")
    body(ch.cell(row=r_, column=7, value=f'=IF(N($E{r_})=0,"",$F{r_}/$E{r_})'), fmt=PCT, align="center")
    body(ch.cell(row=r_, column=8, value=month_sum("G")), fmt=CUR)
    body(ch.cell(row=r_, column=9, value=month_sum("J")), fmt=INT, align="center")
    body(ch.cell(row=r_, column=10, value=month_sum("K")), fmt=INT, align="center")
    body(ch.cell(row=r_, column=11, value=month_sum("L")), fmt=INT, align="center")
band(ch, TR_FIRST, TR_LAST, len(TREND_H))

# per-project comparison block, mirroring the Dashboard for the selected month
CMP_FIRST = TR_LAST + 3
ch.cell(row=CMP_FIRST - 1, column=1,
        value="Per-project comparison - reporting month set on the Dashboard").font = Font(
    name=FONT, size=10, bold=True, color=NAVY)
header_row(ch, CMP_FIRST, ["Project", "TOR Budget ($)", "Spent to Date ($)",
                           "Milestone Hit Rate %", "Scope Adherence %"])
for i in range(len(PROJECTS)):
    r_ = CMP_FIRST + 1 + i
    d_ = PROW_FIRST + i
    body(ch.cell(row=r_, column=1, value=f"=IF(Dashboard!$B{d_}=\"\",\"\",Dashboard!$B{d_})"),
         color=GREEN_LINK)
    body(ch.cell(row=r_, column=2, value=f"=Dashboard!$D{d_}"), fmt=CUR, color=GREEN_LINK)
    body(ch.cell(row=r_, column=3, value=f"=Dashboard!$E{d_}"), fmt=CUR, color=GREEN_LINK)
    body(ch.cell(row=r_, column=4, value=f'=IF(Dashboard!$J{d_}="","",Dashboard!$J{d_})'),
         fmt=PCT, color=GREEN_LINK, align="center")
    body(ch.cell(row=r_, column=5, value=f'=IF(Dashboard!$M{d_}="","",Dashboard!$M{d_})'),
         fmt=PCT, color=GREEN_LINK, align="center")
CMP_LAST = CMP_FIRST + len(PROJECTS)

n_months = len(MONTHS)
TR_END = TR_FIRST + n_months - 1


def style_chart(c, title, y_title, h=8.5, w=17):
    c.title = title
    c.y_axis.title = y_title
    c.x_axis.title = None
    c.height, c.width = h, w
    c.style = 2


c1 = LineChart()
style_chart(c1, "Portfolio delivery against TOR", "Percent")
c1.add_data(Reference(ch, min_col=4, min_row=4, max_row=TR_END), titles_from_data=True)
c1.add_data(Reference(ch, min_col=7, min_row=4, max_row=TR_END), titles_from_data=True)
c1.set_categories(Reference(ch, min_col=1, min_row=TR_FIRST, max_row=TR_END))
c1.y_axis.numFmt = '0%'
ch.add_chart(c1, "M4")

c2 = BarChart()
style_chart(c2, "Portfolio spend to date", "$")
c2.type, c2.grouping = "col", "clustered"
c2.add_data(Reference(ch, min_col=8, min_row=4, max_row=TR_END), titles_from_data=True)
c2.set_categories(Reference(ch, min_col=1, min_row=TR_FIRST, max_row=TR_END))
ch.add_chart(c2, "M22")

c3 = LineChart()
style_chart(c3, "Risk and governance posture", "Count")
c3.add_data(Reference(ch, min_col=9, min_row=4, max_col=11, max_row=TR_END),
            titles_from_data=True)
c3.set_categories(Reference(ch, min_col=1, min_row=TR_FIRST, max_row=TR_END))
ch.add_chart(c3, "M40")

c4 = BarChart()
style_chart(c4, "TOR budget vs spend to date, by project", "$")
c4.type, c4.grouping = "col", "clustered"
c4.add_data(Reference(ch, min_col=2, min_row=CMP_FIRST, max_col=3, max_row=CMP_LAST),
            titles_from_data=True)
c4.set_categories(Reference(ch, min_col=1, min_row=CMP_FIRST + 1, max_row=CMP_LAST))
ch.add_chart(c4, "M58")

c5 = BarChart()
style_chart(c5, "Milestone hit rate and scope adherence, by project", "Percent")
c5.type, c5.grouping = "col", "clustered"
c5.add_data(Reference(ch, min_col=4, min_row=CMP_FIRST, max_col=5, max_row=CMP_LAST),
            titles_from_data=True)
c5.set_categories(Reference(ch, min_col=1, min_row=CMP_FIRST + 1, max_row=CMP_LAST))
c5.y_axis.numFmt = '0%'
ch.add_chart(c5, "M76")

# ================================================================== LISTS =====
ls = wb.create_sheet("Lists")
ls.sheet_properties.tabColor = GREY
title_block(ls, "  Dropdown lists",
            "  Extend a column and the matching dropdown picks it up. "
            "Keep RAG wording as Green / Amber / Red - the Dashboard formulas match on it.", 5)
header_row(ls, 3, ["RAG", "Deliverable Status", "Risk/Issue Status", "Type", "Score 1-5"])
widths(ls, {"A": 14, "B": 20, "C": 20, "D": 12, "E": 12})
for col, vals in enumerate([LIST_RAG, LIST_DSTATUS, LIST_RSTATUS, LIST_RTYPE, LIST_SCORE], start=1):
    for i, v in enumerate(vals):
        body(ls.cell(row=4 + i, column=col, value=v), color=BLUE_INPUT, align="center")

DVS = [
    (log, f"M{LOG_FIRST}:M{LOG_LAST}", f"=Lists!$A$4:$A${3 + len(LIST_RAG)}"),
    (dl, f"J{DEL_FIRST}:J{DEL_LAST}", f"=Lists!$B$4:$B${3 + len(LIST_DSTATUS)}"),
    (rk, f"K{RSK_FIRST}:K{RSK_LAST}", f"=Lists!$C$4:$C${3 + len(LIST_RSTATUS)}"),
    (rk, f"C{RSK_FIRST}:C{RSK_LAST}", f"=Lists!$D$4:$D${3 + len(LIST_RTYPE)}"),
    (rk, f"E{RSK_FIRST}:F{RSK_LAST}", f"=Lists!$E$4:$E${3 + len(LIST_SCORE)}"),
    (tor, f"A{TOR_FIRST}:A{TOR_LAST}", None),
]
for sheet, rng, src in DVS:
    if src is None:
        continue
    dv = DataValidation(type="list", formula1=src, allow_blank=True, showErrorMessage=True)
    dv.error = "Pick a value from the list on the Lists tab."
    dv.errorTitle = "Not a valid entry"
    sheet.add_data_validation(dv)
    dv.add(rng)

# project-ID dropdowns driven by the TOR Register
pid_src = f"='TOR Register'!$A${TOR_FIRST}:$A${TOR_LAST}"
for sheet, rng in ((log, f"B{LOG_FIRST}:B{LOG_LAST}"),
                   (dl, f"B{DEL_FIRST}:B{DEL_LAST}"),
                   (rk, f"B{RSK_FIRST}:B{RSK_LAST}")):
    dv = DataValidation(type="list", formula1=pid_src, allow_blank=True, showErrorMessage=False)
    sheet.add_data_validation(dv)
    dv.add(rng)

# --- finalisation: Arial everywhere, including merged continuation and blank cells
try:
    normal = wb._named_styles["Normal"]
    normal.font = Font(name=FONT, size=10)
except Exception:
    pass

for sheet in wb.worksheets:
    for row in sheet.iter_rows():
        for cell in row:
            f = cell.font
            if f is not None and f.name != FONT:
                cell.font = Font(name=FONT, size=f.size or 10, bold=f.bold,
                                 italic=f.italic, color=f.color)

wb.active = wb.sheetnames.index("Dashboard")
wb.save(OUT)
print("wrote", OUT)
