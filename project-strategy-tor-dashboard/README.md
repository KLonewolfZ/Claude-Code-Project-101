# Project Strategy TOR Dashboard

A team reporting pack that tracks live delivery against what each project's
**Terms of Reference** actually committed to — scope, deliverables, milestones, budget,
governance (RACI) and risk.

It runs at **two cadences off one dashboard**:

| Cadence | Source | Purpose |
|---|---|---|
| **Daily** | `Daily Log` | Spot slippage inside the month, while there's still time to act |
| **Monthly** | `Monthly Log` | The governance / SteerCo record, and the monthly trend history |

Set `Dashboard!C3` to Daily or Monthly and `Dashboard!C4` to the reporting date — every
metric, tile and RAG follows.

| File | What it is |
|---|---|
| `Project_Strategy_TOR_Dashboard.xlsx` | The workbook. This is the deliverable. |
| `build_tor_dashboard.py` | Generator that produces the workbook from scratch. |

## How the two cadences join

Both logs hold the **same cumulative-to-date figures**, so the last daily row of a month
*is* that month's monthly row. That is a property of the design, not a convention to
remember: the shipped example data demonstrates it, with Daily @ 2026-08-31 producing
byte-identical figures to Monthly @ 2026-08 across every project and every portfolio tile.

The **month-end roll-up** block on `Daily Log` (set the date in `R3`) reads any date and
shows each project's figures ready to copy into the Monthly Log — no double entry, no drift
between the two views.

## The daily routine — two minutes per project

1. On `Daily Log`, copy yesterday's block down, change the date, update what moved.
   Figures are **cumulative to date**, not in-day.
2. On `Dashboard`, set Cadence to Daily and today's date in `C4`. Red and Amber rows are
   today's problem.

## The monthly cycle — five steps

1. **Update the registers** — `Deliverables & RACI` and `Risks & Issues` as things move.
2. **Roll the month up** — put the month-end date in `Daily Log!R3` and copy the resulting
   row into `Monthly Log`. (Teams that don't log daily just type the month's figures
   straight into `Monthly Log`.)
3. **Copy the live counts** — Open Risks and High Risks from `Risks & Issues`, RACI Gaps
   from `Deliverables & RACI`. Freezing them into the log is what gives the trend charts
   their history; the registers only ever show today.
4. **Set cadence and month** — `Dashboard!C3` = Monthly, `C4` = first day of the month.
5. **Review** — walk the Dashboard exception table, then `Charts`.

## Tabs

| Tab | Purpose |
|---|---|
| **Read Me** | Both cadences, metric definitions, colour legend, capacity notes. |
| **TOR Register** | The approved baseline: objective, scope boundaries, dates, budget, planned milestone and deliverable counts. Change only via an approved CR. |
| **Daily Log** | Day-by-day entry, one row per project per working day. Carries the month-end roll-up block. |
| **Monthly Log** | One row per project per month. The governance record and the source of the monthly trend charts. |
| **Deliverables & RACI** | TOR deliverables mapped to clauses with R/A/C/I. A blank *Accountable* is counted automatically as a governance gap. |
| **Risks & Issues** | Register with likelihood × impact scoring, derived severity, and live per-project counts. |
| **Dashboard** | Portfolio tiles plus a per-project table, for whichever cadence `C3` selects. |
| **Charts** | Monthly trend, per-project comparisons, and daily trend for the current month — 8 charts. |
| **Lists** | Dropdown values, including the Daily / Monthly cadence list. |

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

Thresholds are editable inputs (yellow cells), defaulting to: milestone hit rate Amber below
90% / Red below 75%; budget used Amber above 95% / Red above 100%; 2 or more unclosed
high-severity risks forces Red.

## Colour convention

- **Blue text** — a value you type. Safe to edit.
- **Yellow fill** — key input you are expected to set (cadence, reporting date, RAG
  thresholds, roll-up date).
- **Black text** — formula on that sheet. Don't overwrite.
- **Green text** — pulled from another sheet. Don't overwrite.

## Example data

The workbook ships with example data for **five fictional projects**: six months on
`Monthly Log` and the 21 working days of August 2026 on `Daily Log`. Names and figures are
invented; there is no external data source behind them. Delete row 4 downwards on
*TOR Register*, *Daily Log*, *Monthly Log*, *Deliverables & RACI* and *Risks & Issues*
before real use.

The example is internally consistent in two ways worth checking as a smoke test:

- Daily @ 2026-08-31 equals Monthly @ 2026-08 for every project and every portfolio tile.
- Every August snapshot reconciles exactly with the live register counts, demonstrating
  step 3 of the monthly cycle.

## Capacity

Formulas already span the full ranges, so new rows need no formula editing:
TOR Register 40 projects · Daily Log 1,500 rows · Monthly Log 300 rows · Deliverables and
Risks 200 rows each · monthly trend 24 months · daily trend 65 days. The Dashboard table and
the roll-up block are both driven off the TOR Register — add a project there and it appears
automatically.

Enter dates as the **actual date** on `Daily Log`, and the **first day of the month** on
`Monthly Log` (e.g. `2026-09-01`); the Dashboard matches on the exact date, so a mid-month
date won't be picked up in Monthly cadence.

The per-project comparison block on `Charts` is sized to the projects present when the
workbook was generated. Re-run the generator after adding projects if you want them in
those two charts; the trend charts and the Dashboard extend on their own.

## Regenerating

Edit `build_tor_dashboard.py` for structural change; edit the `.xlsx` directly for
day-to-day data. Regenerating overwrites the workbook.

```bash
python3 build_tor_dashboard.py
```

Requires `openpyxl`. The workbook contains 4,432 formulas and recalculates clean with zero
formula errors.
