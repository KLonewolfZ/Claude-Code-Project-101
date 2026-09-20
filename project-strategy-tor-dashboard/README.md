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
| **CEO Brief** | Five decision-led bullets — money, benefits, delivery, strategic pillar, scope drift — with computed ACT NOW / WATCH / OK flags and a bottom-line summary. Every line is a live formula off the Dashboard. The file opens here. |
| **TOR Register** | The approved baseline: objective, scope boundaries, dates, budget, **target benefit and benefits-start date**, planned milestone and deliverable counts. Change only via an approved CR. |
| **Daily Log** | Day-by-day entry, one row per project per working day. Carries the month-end roll-up block. |
| **Monthly Log** | One row per project per month. The governance record and the source of the monthly trend charts. |
| **Deliverables & RACI** | TOR deliverables mapped to clauses with R/A/C/I. A blank *Accountable* is counted automatically as a governance gap. |
| **Risks & Issues** | Register with likelihood × impact scoring, derived severity, and live per-project counts. |
| **Dashboard** | Portfolio tiles plus a per-project table, for whichever cadence `C3` selects. |
| **Charts** | Monthly trend, per-project comparisons, spend-vs-benefit, and daily trend for the current month — 9 charts. |
| **Lists** | Dropdown values, including the Daily / Monthly cadence list. |

## CEO Brief

Five decision-led bullets, each with a computed triage flag so the reader can prioritise in
seconds:

| Flag | Meaning |
|---|---|
| **ACT NOW** | Needs a decision this cycle |
| **WATCH** | Deteriorating, not yet actionable |
| **OK** | Nothing required |

The five, in the order a CEO needs them:

1. **Money** — spend against the TOR-authorised budget, any overspend, remaining headroom.
2. **Benefits realisation** — value delivered against what the TOR promised.
3. **Delivery** — milestones hit and deliverables *accepted*, with direction of travel.
4. **Strategic pillar** — which strategic *bet* is weakest, not which project.
5. **Scope drift** — approved change requests against a budget that hasn't moved.

Each is three lines: the fact with its number, one line of consequence, and a **Decision:**
line naming what to do or ask. Above them sits a computed *Bottom line* sentence carrying
the portfolio position and the open high-severity risk count.

Everything — flags included — is a live formula off the Dashboard, so the brief follows the
cadence/date and cannot be edited into a more flattering story. The wording *branches* on the
data rather than interpolating numbers into fixed text: with nothing over budget, bullet 1
flips to **OK** and reads *"Decision: none this cycle. Re-test when budget used passes 95%."*

### The benefits guard

Benefits realisation counts **only projects whose `Benefits Start` date has passed**. A
project that hasn't reached its benefits start is *excluded from the ratio*, not counted as
zero — otherwise every healthy early-stage project would look like a failure. The bullet
states the denominator on its face ("measured across the 4 of 5 reporting projects whose
benefits have started").

In the shipped example this matters a lot: P-004 carries a $2.2m target that starts in
November. Excluded, the portfolio reads 17.8% realised; counted as a zero-realiser it would
read 10.8%.

The bullet compares realisation against spend as a **gap in percentage points**, because
benefits legitimately lag spend. The thresholds (`Dashboard!C12:C13`) are set on the size of
that gap, not on the realisation level, and the Decision line says plainly that the workbook
records *when* benefits start but not *how they phase* — so a large gap is normal for
back-loaded benefits and a problem otherwise.

### Strategic pillar

Groups the portfolio by the `Strategic Pillar` column on the TOR Register — pick from the
dropdown so grouping stays consistent. The weakest pillar is the lowest milestone hit rate
among pillars that have something reporting; a pillar with no reporting projects is excluded
rather than ranked at zero.

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

## What the team has to maintain

Beyond the existing monthly figures, benefits realisation adds three fields:

| Sheet | Column | Filled |
|---|---|---|
| `TOR Register` | **Target Benefit ($)** | Once, from the signed TOR |
| `TOR Register` | **Benefits Start** | Once, from the signed TOR |
| `Daily Log` + `Monthly Log` | **Benefit Realised to Date ($)** | Each cycle, cumulative |

The log column sits immediately right of `Budget Spent to Date ($)` so money out and money
back are adjacent for whoever is typing.

Strategic pillar needs no new data — it groups the `Strategic Pillar` column that was already
on the TOR Register. It now has a dropdown so the grouping stays consistent.

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

Requires `openpyxl`. The workbook contains 5,170 formulas and recalculates clean with zero
formula errors.
