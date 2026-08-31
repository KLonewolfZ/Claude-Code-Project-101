"""
Time model for the Project Strategy TOR reporting workflow.

Produces the numbers behind WORKFLOW_CHART.md. Nothing here is asserted by
hand: change an assumption below and every figure in the chart moves with it.

    python3 workflow_time_model.py

The model costs one reporting month of analyst time, as-is and to-be, at a
given portfolio size. It is deliberately conservative: where a figure could
be argued either way, the as-is number is the cheaper reading and the to-be
number the dearer one, so the saving is understated rather than sold.
"""

from dataclasses import dataclass, field

# --------------------------------------------------------------- assumptions

WORKING_DAYS = 21          # working days in a reporting month
EXCEPTION_RATE = 0.30      # share of projects Red/Amber in a given review

# The Daily Log row is 14 fields per project per working day:
#   Date, Project, Ms Planned, Ms Achieved, Dl Due, Dl Accepted, Spend,
#   CR Raised, CR Approved, Open Risks, High Risks, RACI Gaps, PM RAG, Note
#
# As-is, all 14 are hand-entered. The breakdown below sums to 2.00 min per
# project per day, which is the figure the workbook's own Read Me states for
# the daily routine - so the model is anchored to the process as documented,
# not to a number invented for this analysis.
AS_IS_DAILY = {
    "Copy prior block down, correct the date":            0.30,
    "Re-key 5 fields the registers already compute":      0.55,
    "Re-key 6 fields that did not change since yesterday": 0.45,
    "Note and PM RAG judgement":                          0.35,
    "Find and fix re-keying errors":                      0.35,
}

# To-be, the same row is mostly formula. Five fields come from the registers
# by date+project lookup; six carry forward from the prior day unless
# overtyped. A project-day therefore costs either a glance or a short edit.
CHANGE_RATE = 0.30         # share of project-days where something actually moved
EDIT_MINUTES = 0.55        # typing only the deltas on a day that moved
GLANCE_MINUTES = 0.02      # a day that did not move: the row is already right


@dataclass
class Step:
    name: str
    as_is_fixed: float = 0.0      # minutes per month, independent of portfolio
    as_is_per_project: float = 0.0
    to_be_fixed: float = 0.0
    to_be_per_project: float = 0.0
    note: str = ""
    daily: bool = False           # cost recurs every working day
    exception_only: bool = False  # per-project cost applies to exceptions only


def as_is_daily_total() -> float:
    return sum(AS_IS_DAILY.values())


def to_be_daily_total() -> float:
    return CHANGE_RATE * EDIT_MINUTES + (1 - CHANGE_RATE) * GLANCE_MINUTES


STEPS = [
    Step("Daily Log data entry",
         as_is_per_project=as_is_daily_total(),
         to_be_per_project=to_be_daily_total(),
         daily=True,
         note="THE BOTTLENECK. Registers feed the log; carry-forward fills the rest."),
    Step("Daily dashboard read",
         as_is_fixed=6.0, to_be_fixed=2.0, daily=True,
         note="Opens filtered to today's exceptions instead of the full table."),
    Step("M1 Update registers",
         as_is_per_project=4.0, to_be_per_project=4.0,
         note="Unchanged, and deliberately so - risk scoring and ownership are judgement."),
    Step("M2 Month-end roll-up",
         as_is_per_project=1.5, to_be_per_project=0.15,
         note="Roll-up block already exists; paste-values becomes one action for all rows."),
    Step("M3 Copy live register counts",
         as_is_per_project=1.5, to_be_per_project=0.0,
         note="Eliminated: the counts are already in the row by the time the month ends."),
    Step("M4 Set cadence and month",
         as_is_fixed=1.0, to_be_fixed=0.0,
         note="Dashboard defaults to the current period."),
    Step("M5 Review and present",
         as_is_fixed=25.0, as_is_per_project=1.0,
         to_be_fixed=25.0, to_be_per_project=1.0, exception_only=True,
         note="Protected. This is the value-add - it is not a target."),
    Step("M6 Reconcile the two views",
         as_is_fixed=25.0, to_be_fixed=5.0,
         note="Little left to reconcile once the log stops being re-keyed."),
]


def cost(step: Step, projects: int, to_be: bool) -> float:
    fixed = step.to_be_fixed if to_be else step.as_is_fixed
    per = step.to_be_per_project if to_be else step.as_is_per_project
    heads = projects * (EXCEPTION_RATE if step.exception_only else 1.0)
    days = WORKING_DAYS if step.daily else 1
    return (fixed + per * heads) * days


def totals(projects: int) -> tuple[float, float]:
    return (sum(cost(s, projects, False) for s in STEPS),
            sum(cost(s, projects, True) for s in STEPS))


def hm(minutes: float) -> str:
    return f"{minutes:7.0f} min ({minutes / 60:5.1f} h)"


def report(projects: int) -> None:
    print(f"\n{'=' * 78}")
    print(f"  ONE REPORTING MONTH - {projects} projects, {WORKING_DAYS} working days")
    print(f"{'=' * 78}")
    print(f"  {'Step':<32}{'As-is':>13}{'To-be':>13}{'Saved':>13}  {'Share':>6}")
    print(f"  {'-' * 74}")
    a_tot, b_tot = totals(projects)
    for s in STEPS:
        a, b = cost(s, projects, False), cost(s, projects, True)
        print(f"  {s.name:<32}{a:>9.0f} min{b:>9.0f} min{a - b:>9.0f} min"
              f"{a / a_tot:>7.0%}")
    print(f"  {'-' * 74}")
    print(f"  {'TOTAL':<32}{a_tot:>9.0f} min{b_tot:>9.0f} min{a_tot - b_tot:>9.0f} min")
    print(f"\n  As-is  {hm(a_tot)}     To-be {hm(b_tot)}")
    print(f"  Reduction in working time: {1 - b_tot / a_tot:.1%}")
    new_top = max(STEPS, key=lambda s: cost(s, projects, True))
    print(f"  New constraint: {new_top.name} "
          f"({cost(new_top, projects, True) / b_tot:.0%} of remaining time)")


def sensitivity() -> None:
    print(f"\n{'=' * 78}")
    print("  SENSITIVITY - where the 80% holds")
    print(f"{'=' * 78}")
    print(f"  {'Projects':>9}{'As-is (h)':>12}{'To-be (h)':>12}{'Reduction':>12}   Verdict")
    print(f"  {'-' * 74}")
    for n in (5, 10, 15, 20, 25, 30, 40):
        a, b = totals(n)
        r = 1 - b / a
        verdict = "meets 80% target" if r >= 0.80 else "fixed costs still dominate"
        print(f"  {n:>9}{a / 60:>12.1f}{b / 60:>12.1f}{r:>11.1%}   {verdict}")

    print(f"\n  Sensitivity to the daily change rate (at 20 projects):")
    print(f"  {'Change rate':>12}{'To-be (h)':>12}{'Reduction':>12}")
    print(f"  {'-' * 36}")
    global CHANGE_RATE
    keep = CHANGE_RATE
    for cr in (0.20, 0.30, 0.40, 0.50, 0.60):
        CHANGE_RATE = cr
        STEPS[0].to_be_per_project = to_be_daily_total()
        a, b = totals(20)
        print(f"  {cr:>11.0%}{b / 60:>12.1f}{1 - b / a:>11.1%}")
    CHANGE_RATE = keep
    STEPS[0].to_be_per_project = to_be_daily_total()


def keystrokes(projects: int) -> None:
    fields = 14
    rows = projects * WORKING_DAYS
    derived = 5   # Dl Due, Dl Accepted, Open Risks, High Risks, RACI Gaps
    carried = 6   # Ms Planned, Ms Achieved, Spend, CR Raised, CR Approved, PM RAG
    print(f"\n{'=' * 78}")
    print(f"  WHAT IS ACTUALLY BEING TYPED - {projects} projects")
    print(f"{'=' * 78}")
    print(f"  Daily Log rows per month          {rows:>8,}")
    print(f"  Hand-entered fields per month     {rows * fields:>8,}")
    print(f"  ...already computed elsewhere     {rows * derived:>8,}"
          f"   ({derived}/{fields} of every row)")
    print(f"  ...unchanged since yesterday      "
          f"{rows * carried * (1 - CHANGE_RATE):>8,.0f}   (at a "
          f"{CHANGE_RATE:.0%} change rate)")
    remaining = rows * fields - rows * derived - rows * carried * (1 - CHANGE_RATE)
    print(f"  ...genuinely new information      {remaining:>8,.0f}"
          f"   {remaining / (rows * fields):>6.0%} of the typing")

def attribution(projects: int) -> None:
    """Which of the four changes earns which minutes. Must sum to the total saved."""
    def c(prefix: str, to_be: bool) -> float:
        return next(cost(s, projects, to_be) for s in STEPS if s.name.startswith(prefix))

    a_tot, b_tot = totals(projects)
    daily_saved = c("Daily Log", False) - c("Daily Log", True)
    lookup = AS_IS_DAILY["Re-key 5 fields the registers already compute"] * projects * WORKING_DAYS
    rows = [
        ("1  Register lookup", lookup),
        ("2  Carry-forward default", daily_saved - lookup),
        ("3  One-action roll-up",
         (c("M2", False) - c("M2", True)) + (c("M3", False) - c("M3", True))),
        ("4  Exception-first views",
         (c("Daily dashboard", False) - c("Daily dashboard", True))
         + (c("M4", False) - c("M4", True)) + (c("M6", False) - c("M6", True))),
    ]
    print(f"\n{'=' * 78}")
    print(f"  WHERE THE SAVING COMES FROM - {projects} projects")
    print(f"{'=' * 78}")
    for name, mins in rows:
        print(f"  {name:<32}{mins:>9.0f} min{mins / (a_tot - b_tot):>8.0%} of the saving")
    total = sum(m for _, m in rows)
    print(f"  {'-' * 58}")
    print(f"  {'Sum of the four changes':<32}{total:>9.0f} min")
    print(f"  {'Total saved':<32}{a_tot - b_tot:>9.0f} min")
    assert abs(total - (a_tot - b_tot)) < 0.01, "attribution does not reconcile"
    print("  Reconciles.")


def cost_of_the_alternative(projects: int) -> None:
    """What deleting every monthly step except the registers and the review would buy."""
    a_tot, _ = totals(projects)
    strip = sum(cost(s, projects, False) for s in STEPS
                if s.name.startswith(("M2", "M3", "M4", "M6")))
    print(f"\n{'=' * 78}")
    print(f"  WHY FIXING ANYTHING ELSE DOES NOT WORK - {projects} projects")
    print(f"{'=' * 78}")
    print(f"  Delete M2, M3, M4 and M6 entirely - four whole steps.")
    print(f"  Month falls from {a_tot / 60:.1f} h to {(a_tot - strip) / 60:.1f} h "
          f"- a saving of {strip / a_tot:.1%}.")
    print(f"  The constraint sets the pace; work anywhere else is invisible.")


if __name__ == "__main__":
    for n in (5, 20, 40):
        report(n)
    keystrokes(20)
    attribution(20)
    cost_of_the_alternative(20)
    sensitivity()
    print()
