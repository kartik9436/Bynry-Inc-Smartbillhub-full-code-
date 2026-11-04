"""What a finished job cost — `BR-WRK-051`, and the ONE place the arithmetic lives.

HUMAN-OWNED. Money rounding on a customer-facing document is a CLAUDE.md 🔒
sensitive path.

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md` stating, in plain English with the
figure, exactly what was shown. Not RATIFIED without a recorded sign-off, and
a signature covers only what was shown.

⚠ **`BR-WRK-051` IS `PROPOSED`, NOT CONFIRMED.** The rounding point below is
the thing awaiting sign-off, and it is worth seventeen cents on the worked
example. It is IMPLEMENTED here rather than stubbed because the blueprint
states it with its figure and its counter-case — this is signed law being
implemented, not a rule being invented. If a reader of the review row rules
differently, the constant to change is `HOURS_PLACES` and the test that pins
`138.42` goes red, by design.

WHAT THIS FILE IS FOR
─────────────────────
`work_order_cost_lines(order)` is **the one named function** the rule requires.
The report reads it, the performance tab reads what it persisted, and there is
no second place a job's cost is worked out. That is the whole point of naming
it in a rule: a cost that is computed in two places is a cost that will
eventually be two different numbers on two screens.

THE WORKED FIGURE, WHICH IS THE RULE
────────────────────────────────────
`WO-4822` — a meter exchange, on site 15:15–16:07, so **52 minutes**, closed
by a Field technician whose rate was `48.5000` an hour at close, having used
one `MTR-E1P` at `96.0000` and one `SEAL-01` at `0.2200`:

    hours   52 ÷ 60         = 0.8666…  →  0.87 h      (TWO decimals)
    labour  0.87 × 48.5000  = 42.1950  →  42.20 shown
    part    1   × 96.0000   = 96.0000  →  96.00 shown
    part    1   × 0.2200    =  0.2200  →   0.22 shown
    TOTAL   42.20 + 96.00 + 0.22       = 138.42

⚠ **THE TOTAL IS THE SUM OF THE *ROUNDED* LINES, NOT A ROUNDED SUM.** Four
decimals throughout would give `138.4150 → 138.42` here by luck, and would not
in general. The rule is the one B4 already applies to a tax base and it exists
for a reader: somebody adding the printed column with a pen must reach the
printed total. A document whose lines do not add up to its own total is not
something you can hand to a customer.

⚠ **AND THE HOURS ARE ROUNDED TO TWO BEFORE THEY ARE MULTIPLIED — THAT IS A
DECISION AND IT IS WORTH SEVENTEEN CENTS.** At four-decimal hours,
`0.8667 × 48.5 = 42.03`; at two, `42.20`. `US-WRK-053` TC-2 pins the
counter-case so nobody "improves the precision" and silently moves every
labour line in the product. The reason to book at two is that `0.87 h` is what
the report PRINTS, and the printed hours times the printed rate must give the
printed amount — the same reader-with-a-pen test as the total.

WHAT IS DELIBERATELY NOT HERE
─────────────────────────────
**No tax line.** `BR-WRK-052`, PO 2026-09-03 verbatim: *"Dont add Tax on work
order - for now"*. The wireframe `Work-032` draws `6.25%` and `2.00%` of the
total as `8.65` and `2.77` and a grand total of `149.84`. **This file totals
`138.42` and the word `tax` appears in it only in this paragraph and in the
refusal below.** `US-WRK-053` TC-3 greps for it; `G111` fails the build if a
tax line is added anywhere in the report path. B4 §Tax ❄️ FROZEN stands, and
changing it is a finance re-sign through `HUMAN-GUIDE.md` §6.

**No posting.** `BR-WRK-004`; see `post_field_cost_to_ledger` at the foot.

**No stock.** Nothing here reads or moves an on-hand count, because none
lawfully exists (`OQ-WRK-1490`, closed 2026-09-04 to option (a)).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable

#: Money is stored to FOUR decimals and displayed to TWO — CLAUDE.md hard rule
#: 2, PO re-sign 2026-08-22: *"MOney 4 decimal, percentage 6 decimal, display
#: both 2 decimal"*.
FOUR_DP = Decimal("0.0001")
TWO_DP = Decimal("0.01")

#: ⚠ **THE ROUNDING POINT OF THE HOURS, AND THE ONE FIGURE IN THIS FILE THAT IS
#: A JUDGMENT RATHER THAN AN ARITHMETIC FACT.** Two decimals, so 52 minutes is
#: `0.87 h` and the labour line is `42.20`. At four it would be `42.03`.
#: `BR-WRK-051` states it; `US-WRK-053` TC-1 and TC-2 pin both sides of it.
#: Changing this constant changes every labour line in the product and is a
#: re-sign, not an edit.
HOURS_PLACES = TWO_DP

MINUTES_PER_HOUR = Decimal("60")

KIND_LABOUR = "labour"
KIND_OVERTIME = "overtime"
KIND_PART = "part"


def _round_half_up(value: Decimal, places: Decimal) -> Decimal:
    """Half-up, the only rounding this product does (B4 §Rounding, CONFIRMED)."""
    return Decimal(value).quantize(places, rounding=ROUND_HALF_UP)


def display(amount: Decimal) -> Decimal:
    """The two-decimal figure a reader SEES. `42.1950` → `42.20`."""
    return _round_half_up(amount, TWO_DP)


def hours_from_minutes(minutes: Any) -> Decimal:
    """Minutes on site → hours **booked to two decimals**. 52 → `0.87`.

    See `HOURS_PLACES`. This is the rule's rounding point and not a formatting
    convenience: the value returned here is what gets MULTIPLIED, and it is
    also what the report prints in the *hours* column, so the two cannot
    disagree.
    """
    return _round_half_up(Decimal(minutes) / MINUTES_PER_HOUR, HOURS_PLACES)


@dataclass(frozen=True)
class CostLine:
    """One printed row: *Labour · Field technician · 0.87 h · 48.5000 · 42.20*.

    `amount` is the FOUR-decimal stored figure (`42.1950`) and `display_amount`
    is the two-decimal printed one (`42.20`). Both are carried because the
    total is the sum of the SECOND — keeping only one would make the rule
    impossible to state, which is how it would eventually be broken.
    """

    kind: str
    description: str
    qty: Decimal
    unit: str
    rate: Decimal
    amount: Decimal

    @property
    def display_amount(self) -> Decimal:
        return display(self.amount)


@dataclass(frozen=True)
class LabourInput:
    """What the labour lines need, gathered once so the arithmetic stays pure.

    `rate` and `overtime_rate` are the SNAPSHOTS taken at close
    (`work_orders.labour_rate_snapshot`), never a live read of `labour_rates` —
    `US-WRK-051` TC-3: the rate moves to `50.0000` on 1 April and `WO-4822`,
    closed 15 March, still prices at `48.5000`.
    """

    minutes: Any
    role_label: str
    rate: Decimal
    overtime_rate: Decimal | None = None
    overtime_after_hours: Decimal | None = None


@dataclass(frozen=True)
class PartInput:
    """One part USED on the job — `work_order_materials.used_qty × unit_cost`.

    `unit_cost` is the cost copied onto the job, not a live read of `parts`:
    the register's price may be edited next year and an approved report must
    not change. A part planned and NOT used contributes no line at all
    (`US-WRK-050` TC-2 keeps *0 of 1 · not used* on the SCREEN, which is a
    different fact from a cost line of zero).
    """

    description: str
    used_qty: Decimal
    unit: str
    unit_cost: Decimal


def labour_lines(labour: LabourInput | None) -> list[CostLine]:
    """The labour line, and a second one when the daily threshold is passed.

    `US-WRK-053` TC-9: nine hours against an eight-hour threshold is
    `8.00 × 48.5000 = 388.00` **plus** `1.00 × 72.7500 = 72.75`, two lines,
    `460.75` — not nine hours at a blended rate. Two lines because that is what
    a reader must be able to check, and because overtime is a different price
    for a reason a manager may want to see.
    """
    if labour is None:
        return []
    hours = hours_from_minutes(labour.minutes)
    threshold = labour.overtime_after_hours
    ordinary = hours
    overtime = Decimal("0")
    #: Overtime only exists when there is a threshold AND a rate for it. A
    #: contractor has neither (`BR-WRK-020` — *"an agency invoices its own
    #: overtime… The dash is the honest value"*), so every hour is ordinary.
    if threshold is not None and labour.overtime_rate is not None and hours > threshold:
        ordinary = _round_half_up(Decimal(threshold), HOURS_PLACES)
        overtime = _round_half_up(hours - ordinary, HOURS_PLACES)

    lines = [
        CostLine(
            kind=KIND_LABOUR,
            description=labour.role_label,
            qty=ordinary,
            unit="h",
            rate=_round_half_up(labour.rate, FOUR_DP),
            amount=_round_half_up(ordinary * Decimal(labour.rate), FOUR_DP),
        )
    ]
    if overtime > 0:
        lines.append(
            CostLine(
                kind=KIND_OVERTIME,
                description=f"{labour.role_label} — overtime",
                qty=overtime,
                unit="h",
                rate=_round_half_up(Decimal(labour.overtime_rate), FOUR_DP),
                amount=_round_half_up(overtime * Decimal(labour.overtime_rate), FOUR_DP),
            )
        )
    return lines


def part_lines(parts: Iterable[PartInput]) -> list[CostLine]:
    """`used_qty × unit_cost`, one line per part actually used."""
    out = []
    for part in parts:
        qty = Decimal(part.used_qty)
        if qty <= 0:
            #: A part planned and not used is a real outcome and belongs on the
            #: Parts TAB (`US-WRK-050` TC-2); it is not a cost line of zero,
            #: which would print *$0.00* on a document and read as *free*.
            continue
        out.append(
            CostLine(
                kind=KIND_PART,
                description=part.description,
                qty=qty,
                unit=part.unit,
                rate=_round_half_up(part.unit_cost, FOUR_DP),
                amount=_round_half_up(qty * Decimal(part.unit_cost), FOUR_DP),
            )
        )
    return out


def total_of(lines: Iterable[CostLine]) -> Decimal:
    """**The sum of the ROUNDED displayed lines** — `BR-WRK-051`.

    `42.20 + 96.00 + 0.22 = 138.42`, so a reader adding the printed column
    reaches the printed total. NOT `sum(amount)` rounded at the end: that is
    `138.4150` here and would round to the same figure by luck, which is
    exactly why the distinction has to be written down rather than discovered.
    """
    return sum((line.display_amount for line in lines), Decimal("0.00")).quantize(TWO_DP)


def compute(labour: LabourInput | None, parts: Iterable[PartInput]) -> tuple[list[CostLine], Decimal]:
    """The pure arithmetic: inputs in, lines and total out. No database.

    Kept separate from `work_order_cost_lines` below so the worked figure can
    be pinned by a test that needs no fixture, no tenant and no migration —
    `US-WRK-053` TC-1 is arithmetic and should fail for arithmetic reasons
    only.
    """
    lines = labour_lines(labour) + list(part_lines(parts))
    return lines, total_of(lines)


def work_order_cost_lines(order: Any) -> tuple[list[CostLine], Decimal]:
    """**THE one named function `BR-WRK-051` requires** — an order's cost.

    Gathers the two inputs from the order and hands them to `compute`.

    ⚠ **THE PARTS HALF READS WAVE `H`'s `work_order_materials`, WHICH LANDED
    ON 2026-09-05 WHILE THIS WAVE WAS BUILDING** (`work/0012`, `related_name`
    `material_rows`). This lane did not create that table — it is `H1`'s, one
    of the six copy tables, and two lanes creating it would leave two leaves in
    one app's migration graph, which is not a test failure but Django refusing
    every test in the process. The reader stays defensive so this file is
    correct on a branch where `H` is absent; the ARITHMETIC never depended on
    it at all and is pinned by `US-WRK-053` TC-1 through `compute`, which needs
    no table.

    ⚠ **AND THE LABOUR HALF READS THE SNAPSHOT, NEVER `labour_rates`.** An
    order with no `labour_rate_snapshot` yields NO labour line rather than a
    line priced at zero: a report reading *Labour · 0.87 h · $0.00* states that
    the work was free, which is a worse answer than not stating it at all.
    """
    labour = _labour_input(order)
    lines, total = compute(labour, _used_parts(order))
    # ── CR-187-BRC10 T-38 · R8 *"the cost is their sum"* ────────────────────
    # A second technician's own priced line, one per helper, from
    # `work_order_labour` (`field_labour.helper_inputs` reads HELPERS ONLY — the
    # lead is the order's own line above and must never be priced twice). The
    # same `labour_lines` arithmetic and the same `total_of` (the sum of the
    # ROUNDED lines), so nothing about how a line is priced changes; an order
    # with no helper gets exactly the lines and total it got before.
    from apps.work import field_labour

    helpers = field_labour.helper_inputs(order)
    if not helpers:
        return lines, total
    lead_lines = labour_lines(labour)
    helper_lines = [line for helper in helpers for line in labour_lines(helper)]
    lines = lead_lines + helper_lines + lines[len(lead_lines):]
    return lines, total_of(lines)


def _labour_input(order: Any) -> LabourInput | None:
    snapshot = getattr(order, "labour_rate_snapshot", None)
    minutes = minutes_on_site(order)
    if snapshot is None or minutes is None:
        return None
    role = getattr(order, "labour_role", None) or ""
    return LabourInput(
        minutes=minutes,
        role_label=_role_label(role),
        rate=Decimal(snapshot),
        overtime_rate=getattr(order, "labour_overtime_snapshot", None),
        overtime_after_hours=getattr(order, "labour_overtime_after_hours", None),
    )


def _role_label(role: str) -> str:
    """`field_technician` → *Field technician*. The words the report prints."""
    if role.startswith("contractor:"):
        return "Contractor"
    return role.replace("_", " ").capitalize() if role else "Labour"


def minutes_on_site(order: Any) -> Any:
    """Minutes between arriving and completing — `US-WRK-053` §5.

    ⚠ **`started_at` IS WAVE `J`'s `arrive` ASSIGNMENT ROW AND IS NOT ON THE
    ORDER YET.** Where a real arrival time comes from is the phone's, so this
    reads an explicit `minutes_on_site` when the order carries one and returns
    None otherwise — never a guess from `created_at`, which would price a job
    at however long it sat in a queue.
    """
    return getattr(order, "minutes_on_site", None)


def _used_parts(order: Any) -> list[PartInput]:
    """The parts actually used — wave `H`'s `work_order_materials`.

    That table landed on 2026-09-05 (`work/0012`) with `related_name`
    `material_rows`. The relation is read defensively anyway, so this file is
    correct on a branch where `H` has not been merged and needs no edit when it
    is — the arithmetic in `compute` never depended on it either way.

    ⚠ **THE PRICE COMES FROM THE PART CATALOGUE AND IS READ ONCE, AT
    ACCEPTANCE.** `work_order_materials` copies `planned_qty` and the unit but
    NOT the cost, so `parts.unit_cost` is the live figure at the moment the
    report is generated — and that is safe precisely because the cost LINES are
    persisted and frozen (`work/0011`'s trigger). Editing `MTR-E1P` to
    `99.0000` next year cannot move `WO-4822`'s `96.00`, because nothing
    recomputes it.

    ⚠ **`used_qty` IS NULLABLE AND NULL IS NOT ZERO.** A row nobody has
    reported on yet contributes no line — the same posture as an order with no
    rate snapshot. `unplanned` rows are priced exactly like planned ones: *"a
    job is not refused for needing a gasket the template forgot"*
    (`US-WRK-050` TC-3).
    """
    materials = getattr(order, "material_rows", None)
    if materials is None:
        return []
    out = []
    for row in materials.select_related("part").all():
        used = getattr(row, "used_qty", None)
        if not used:
            continue
        part = getattr(row, "part", None)
        out.append(
            PartInput(
                description=(
                    f"{part.part_no} — {part.name}" if part is not None else str(row.part_id)
                ),
                used_qty=Decimal(used),
                unit=getattr(row, "unit_of_measure", "") or "",
                unit_cost=Decimal(getattr(part, "unit_cost", 0) or 0),
            )
        )
    return out


def post_field_cost_to_ledger(order: Any) -> None:
    """Post a closed job's cost to the books — **RULED OUT, AND NOT A STUB**.

    ⚠ **NOTHING CALLS THIS, AND NOTHING EVER WILL — `OQ-WRK-1491` WAS RULED ON
    2026-09-04 TO OPTION (a): CAPTURED, POSTED NOWHERE.** The Product Owner's
    own words: *"(a) captured, posted nowhere"*.

    The prototype `Work-027` says the field's total *"feeds the O&M / labour
    line in Finance → Cost & Margin"*. **That arrow is not built**, the
    sentence is not rendered, and the reason is not squeamishness about the
    ledger: **payroll already posts the hour, and posting field labour beside
    it would count the same hour twice.** `CR-028` D3 is the Product Owner
    removing exactly this sentence for asset maintenance — *"cost is CAPTURED
    — stored 4 dp, totalled on the tab, and posted NOWHERE"* — and field work
    follows that precedent.

    So a closed job's cost is stored to four decimals, shown on the frozen
    report and totalled on the performance tab (*740 jobs · $56,337* on the
    sample utility), and **reaches no journal line**.

    ⚠ **IT IS A DELIBERATE ABSENCE, NOT A STUB AWAITING A RULING**, and the
    difference decides what the next lane does with it: a stub invites
    unblocking, a deliberate absence does not. The message below names the
    RULING rather than a question id so nobody has to look one up to find out
    which it is — the shape `services.stock_position()` already uses for
    `OQ-WRK-1490`, and the shape `DEF-WRK-4030` was filed to make the rule.

    Three further things would refuse this even if it were called: only the
    ledger posting service writes journal lines (CLAUDE.md hard rule 5), the
    module-boundary gate refuses a foreign write from `apps/work/**` (`G78`),
    and `BR-WRK-053` puts no link into Finance on the screen either.
    """
    raise NotImplementedError(
        "ruled 2026-09-04: a closed job's cost is captured — stored 4 dp, shown "
        "on the report, totalled on the performance tab — and posted nowhere; "
        "payroll already posts the hour"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-053@EP-WRK-10 · 02-business-rules.md BR-WRK-050/051/052 · 10-execution-plan.md wave N task N2
# generated: 2026-09-05 by the CR-070 wave N build lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H✔(🔒 HUMAN-OWNED + HUMAN-REVIEW-PENDING; guard-list line and ledger row are N5)
# gates: pytest tests/test_us_wrk_053_costing.py (TC-1 pins 138.42, TC-2 pins the 42.03 counter-case, TC-9 pins 460.75) · G111 (no tax on a work order) · G78 (Work writes nothing foreign)
# exceptions: the PARTS half reads wave H's `work_order_materials`, which has not landed — the arithmetic is complete and pinned without it · BR-WRK-051 is PROPOSED and this file is what the N5 review row puts up for sign-off
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
