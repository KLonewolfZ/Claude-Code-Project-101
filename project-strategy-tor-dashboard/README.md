# Project Strategy TOR Dashboard

A monthly team reporting pack that tracks live delivery against what each project's
**Terms of Reference** actually committed to — scope, deliverables, milestones, budget,
governance (RACI) and risk.

| File | What it is |
|---|---|
| `Project_Strategy_TOR_Dashboard.xlsx` | The workbook. This is the deliverable. |
| `build_tor_dashboard.py` | Generator that produces the workbook from scratch. |

## The monthly cycle

1. **Update the registers** — add or amend rows on *Deliverables & RACI* and *Risks & Issues*
   as things move during the month.
2. **Add the month's rows** — on *Monthly Log*, one row per active project. Copy the previous
   month's block down and update the numbers. **All figures are cumulative to date**, not in-month.
3. **Copy the live counts** — Open Risks and High Risks from *Risks & Issues*, RACI Gaps from
   *Deliverables & RACI*. Freezing them into the log is what gives the trend charts their history;
   the registers only ever show today.
4. **Set the reporting month** — *Dashboard* cell `C4`, first day of the month. Everything
   recalculates.
5. **Review** — walk the Dashboard exception table, then *Charts* for the trend. Red and Amber
   rows are the agenda.

## Tabs

| Tab | Purpose |
|---|---|
| **Read Me** | Cycle, metric definitions, colour legend, capacity notes. |
| **TOR Register** | The approved baseline: objective, scope boundaries, dates, budget, planned milestone and deliverable counts. Change only via an approved CR. |
| **Monthly Log** | The data-entry surface — the only sheet that needs touching in a normal month. |
| **Deliverables & RACI** | TOR deliverables mapped to clauses with R/A/C/I. A blank *Accountable* is counted automatically as a governance gap. |
| **Risks & Issues** | Register with likelihood × impact scoring, derived severity, and live per-project counts. |
| **Dashboard** | The monthly view: portfolio tiles plus a per-project table with a calculated RAG. |
| **Charts** | Portfolio trend across months, plus per-project comparisons. |
| **Lists** | Dropdown values. |

## Metric definitions

| Metric | Definition |
|---|---|
| Scope adherence % | Deliverables accepted ÷ deliverables due to date. Whether the TOR's promised outputs are landing *and being accepted*. |
| Milestone hit rate % | Milestones achieved ÷ planned to date. Schedule health against the TOR baseline. |
| Budget used % | Spend to date ÷ TOR-approved budget. Over 100% means spending past what the TOR authorised. |
| Budget variance | Approved budget less spend to date. Negative = overspent. |
| Approved scope changes | Cumulative CRs approved. A rising count against a flat budget is the classic TOR drift signal. |
| RACI gaps | Deliverables with no accountable owner. Any number above zero is a governance finding. |
| Calculated RAG | Derived only from the thresholds in `Dashboard!C7:C11` and the raw counts, so it is reproducible and cannot be talked up or down. |

**Calculated RAG next to PM RAG is deliberate.** Where the two disagree, that gap *is* the
discussion — in the shipped example data, P-005 is self-reported Green but calculates Amber
on an 85.7% milestone hit rate.

Thresholds are editable inputs (yellow cells, `Dashboard!C7:C11`), defaulting to:
milestone hit rate Amber below 90% / Red below 75%; budget used Amber above 95% / Red above 100%;
2 or more unclosed high-severity risks forces Red.

## Colour convention

- **Blue text** — a value you type. Safe to edit.
- **Yellow fill** — key input you are expected to set (reporting month, RAG thresholds).
- **Black text** — formula on that sheet. Don't overwrite.
- **Green text** — pulled from another sheet. Don't overwrite.

## Example data

The workbook ships with **six months of example data for five fictional projects** so the
formulas and charts can be seen working. Names and figures are invented; there is no external
data source behind them. Delete row 4 downwards on *TOR Register*, *Monthly Log*,
*Deliverables & RACI* and *Risks & Issues* before real use.

The example is internally consistent: every August snapshot in the Monthly Log reconciles
exactly with the live counts on the registers, demonstrating step 3 of the cycle.

## Capacity

Formulas already span the full ranges, so new rows are picked up with no formula editing:
TOR Register 40 projects · Monthly Log 300 rows · Deliverables and Risks 200 rows each ·
Charts trend 24 months. The Dashboard table is driven off the TOR Register — add a project
there and it appears automatically.

Enter months as the **first day of the month** (e.g. `2026-09-01`); the Dashboard matches on
the exact date, so a mid-month date will not be picked up.

## Regenerating

Edit `build_tor_dashboard.py` for structural change; edit the `.xlsx` directly for
month-to-month data. Regenerating overwrites the workbook.

```bash
python3 build_tor_dashboard.py
```

Requires `openpyxl`. The workbook contains 1,802 formulas and recalculates clean with zero
formula errors.
