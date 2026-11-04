# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 2 · P2.22 (THE MONEY TASK — a footer that cannot
#           lawfully sum shows an em-dash and the reason, on screen AND in the
#           CSV, never a number).  Screens: 2·1 footer.
# Rules:    CLAUDE.md hard rule 2 (money 4 dp stored / DISPLAY 2 / never a
#           float — and a total that cannot be trusted is not a money value at
#           all) · hard rule 3 (a quantity carries its unit; gallons plus
#           kilowatt-hours is not a number) · B14 rule 33 (a FACT is six words;
#           RATIONALE is ZERO words on screen) · brief §7.2.2 p85, read as an
#           image per B14 rule 42
# Tests:    06-backend/tests/test_rep_p2_22_unlawful_total.py
# Impacts:  apps/reports/queries.py (every `totals={...}` passes through
#           `footer`) · apps/reports/exports.py (the CSV footer row) ·
#           apps/tenancy/exports.py (`write_csv`'s optional footer) ·
#           07-frontend/src/features/reports/ReportTotalsRow.tsx
# ───────────────────────────────────────────────────────
"""THE FOOTER THAT CAN REFUSE — RENDER TIME, WHERE `assert_summable` IS NOT.

WHAT P0.16 ALREADY DID, AND WHY THIS IS A DIFFERENT THING
─────────────────────────────────────────────────────────
`datasets.assert_summable` RAISES `UnlawfulTotal`, and `runner.validate` calls
it when a definition is SAVED. That is build time, and it is the right place
for it: a stored definition that groups AR Ageing by month and totals the
balance never gets written.

**It does nothing whatever about the number a clerk is looking at right now.**
A footer is computed at RENDER time, over whatever the query returned, and
`queries.py` builds `totals` as a plain `{name: "48221.1400"}` map that travels
to the screen with nothing between it and a `<td>`. Every report in the module
does this, and every one of them would render a confident figure for a sum that
means nothing — which is §7.2.2's *"nothing stops you today"*, still true after
P0.16 shipped, because P0.16 closed the door a definition comes through and
this is the door a REQUEST comes through.

⚠ **SO THE TWO ARE NOT ALTERNATIVES AND NEITHER REPLACES THE OTHER.** A raise
at save time is a refusal a clerk can act on before any harm; a raise at render
time would be an error page over a report that is mostly fine. This module
therefore does NOT raise. It REPLACES the unlawful figure with an em-dash and a
reason and leaves every lawful figure exactly as it found it — which is p84's
own wording: *"A total that is not lawful shows an em-dash and its reason,
never a number"*, and not *"a report with an unlawful total is refused"*.

THE THREE CASES, AND WHY THEY ARE THE THREE
───────────────────────────────────────────
§7.2.2 names four additivity classes and three of them can be got wrong:

  **semi-additive** — an AR balance, deposits held, accounts active. Sums
  across ACCOUNTS and never across TIME. A balance is a stock and not a flow:
  add July's closing receivable to August's and you have counted every account
  that owed money in both months twice, and the answer is not a receivable at
  all. *This is the one the PO found on AR Ageing.*

  **non-additive** — DSO, collection rate, % share, average days overdue. These
  are RATIOS, and a ratio of sums is not the sum of ratios. Four routes with
  DSOs of 20, 30, 40 and 90 do not give a utility DSO of 45; the utility's DSO
  is its own receivable over its own daily sales, which may be 26 or 71. There
  is no direction in which averaging one of these is safe, which is why this
  class refuses over an EMPTY `across` too.

  **additive within one service** — consumption. 26.24 kgal + 684 kWh has no
  unit, so it is not a quantity, so it is not a number. Hard rule 3 already
  forbids it in prose; the model states it as metadata so a machine can see it.

The fourth class, **fully additive** — invoiced amount, payment amount, tax
collected — sums freely in any direction and this module must leave it alone.
A version that refused everything would satisfy every refusal test in the
suite and be worthless, which is hard-won law 7's *"ask what would make this
check pass wrongly"* turned on this file.

WHY THE REASON IS SIX WORDS AND NOT SIXTY
─────────────────────────────────────────
B14 rule 33: a FACT is capped at six words, and RATIONALE — *why* the product
works this way — is **ZERO words on screen**. *"Balances do not sum across
time"* is a fact about this cell and it is six words. The four paragraphs above
are rationale and they live here, in the code, which is what a docstring is
FOR (hard-won law 10's fourth row).

⚠ **WHY THE EM-DASH IS A `display` FIELD AND NOT A `null` THE SCREEN DECORATES.**
A `null` total already means something in this module — *"not counted yet"*,
the KPI pattern `BR-REP-033` settled — and it is rendered by a different
component with a different sentence. Two different absences rendered by one
branch is how *"we could not read the ledger control total"* comes to say
*"balances do not sum across time"*. So a refusal is its own shape, it carries
`refused: true` as the thing a renderer branches on, and `value` stays `None`
so that any caller which ignores this module entirely still cannot print a
figure.

⚠ **AND NO DIGIT OF THE REFUSED FIGURE TRAVELS.** The first draft kept the
computed number in a `detail` field so a tooltip could show *"the unlawful sum
would have been 48,221.14"*. That is a number on the wire, one CSS rule away
from being a number on screen, and a clerk who can see it will quote it. It is
dropped on the floor here and a test asserts the digits are gone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from apps.reports import datasets

#: U+2014. The one character p84 asks for, named so no caller types a hyphen.
EM_DASH = "—"

# ── The reason codes (stable wire values) ───────────────────────────────────
#: A balance, summed across time. §7.2.2's first trap.
REASON_NOT_ACROSS_TIME = "balance_does_not_sum_across_time"
#: A ratio, aggregated in any direction at all. §7.2.2's second trap.
REASON_RECOMPUTE_NEVER_AVERAGE = "recomputed_from_components_never_averaged"
#: A quantity, summed across services. Hard rule 3 as metadata.
REASON_ONE_SERVICE_ONLY = "quantities_differ_between_services"

#: ⚠ **THE ENGLISH IS HERE SO A TEST CAN COUNT ITS WORDS** (B14 rule 33 caps a
#: FACT at six). The ELEVEN catalogues carry the translated copy under
#: `reports.totals.<code>`; this map is the source the fan-in was built from
#: and the thing `G33`'s six-word cap is asserted against in-process.
REASON_SENTENCES: dict[str, str] = {
    REASON_NOT_ACROSS_TIME: "Balances do not sum across time",
    REASON_RECOMPUTE_NEVER_AVERAGE: "Recomputed from components, never averaged",
    REASON_ONE_SERVICE_ONLY: "Quantities differ between services",
}


@dataclass(frozen=True)
class RefusedTotal:
    """One footer cell that will not carry a number.

    Frozen, and carrying no figure of any kind — see the docstring above. What
    it carries is the MEASURE (so the reader knows which column), the REASON
    CODE (so eleven catalogues can say it in their own language, B14 rule 35)
    and the DIRECTION that made it unlawful (so *"regroup by class"* is an
    action the reader can take rather than a guess).
    """

    measure: str
    reason_code: str
    across: tuple[str, ...] = ()

    @property
    def sentence(self) -> str:
        return REASON_SENTENCES[self.reason_code]

    def as_dict(self) -> dict[str, Any]:
        return {
            # ⚠ `None`, always. A caller that ignores `refused` entirely still
            # cannot print a figure — the number is not here to be printed.
            "value": None,
            "display": EM_DASH,
            "refused": True,
            "measure": self.measure,
            "reason_code": self.reason_code,
            "reason": self.sentence,
            "across": list(self.across),
        }

    def cell(self) -> str:
        """The one CSV cell: the em-dash and its reason, together.

        Together and not in two columns, because a file whose footer spreads a
        refusal across columns is a file that reads as data to a spreadsheet.
        """
        return f"{EM_DASH} {self.sentence}"


def refusal_for(
    dataset_code: str, measure_name: str, across: tuple[str, ...] = ()
) -> RefusedTotal | None:
    """`assert_summable`'s non-raising sibling, for the render path.

    Returns `None` when the total is lawful — and when `measure_name` is not a
    measure at all, because an ATTRIBUTE is never totalled and there is nothing
    to refuse or to permit. The two share `datasets`' declaration rather than a
    second copy of the rules, so the save-time refusal and the render-time
    refusal can never disagree about the same measure.
    """
    dataset = datasets.BY_CODE.get(dataset_code)
    if dataset is None:
        return None
    meas = dataset.measure(measure_name)
    if meas is None:
        return None
    if meas.additivity == datasets.ADD_NON:
        # No direction is safe, including no grouping at all — a footer over a
        # flat listing is still an aggregate of a ratio.
        return RefusedTotal(
            measure=measure_name,
            reason_code=REASON_RECOMPUTE_NEVER_AVERAGE,
            across=tuple(across),
        )
    crossed = tuple(dim for dim in meas.forbidden_across if dim in tuple(across))
    if not crossed:
        return None
    code = (
        REASON_ONE_SERVICE_ONLY
        if meas.additivity == datasets.ADD_WITHIN_SERVICE
        else REASON_NOT_ACROSS_TIME
    )
    return RefusedTotal(measure=measure_name, reason_code=code, across=crossed)


def footer(
    dataset_code: str, totals: Mapping[str, Any], across: tuple[str, ...] = ()
) -> dict[str, Any]:
    """The served `totals` map with every unlawful figure replaced.

    ⚠ **IT REPLACES, PER KEY, AND LEAVES EVERYTHING ELSE IDENTICAL.** One
    unlawful column must not poison a row: AR Ageing grouped by month refuses
    its balance total and goes on reporting how many accounts it counted,
    because a count of accounts is fully additive and the clerk needs it.

    ⚠ **KEYS THAT ARE NOT MEASURES PASS THROUGH UNTOUCHED.** `queries.py` puts
    bookkeeping in `totals` — `ar_control`, `population_accounts`, `filtered` —
    and those are not measures of the dataset, so `refusal_for` returns `None`
    and they travel as they always did. A version that wrapped every key would
    have broken the ageing's tie-out line, which reads `ar_control` directly.
    """
    served: dict[str, Any] = {}
    for name, value in totals.items():
        refusal = refusal_for(dataset_code, name, across)
        served[name] = refusal.as_dict() if refusal is not None else value
    return served


def refused_measures(totals: Mapping[str, Any]) -> tuple[str, ...]:
    """The names this footer refused, for a caller that needs the list rather
    than the row — the export's audit line and the viewer's own test."""
    return tuple(
        name
        for name, value in totals.items()
        if isinstance(value, Mapping) and value.get("refused") is True
    )


def csv_footer_row(
    *, columns: tuple[str, ...], totals: Mapping[str, Any], label: str = "Total"
) -> list[str]:
    """The ONE row the export appends under the data (`P2.22`, *"and in the CSV"*).

    ⚠ **THIS IS A KNOWN TENSION WITH `IS-11`'s STRICT CSV CONTRACT AND IT IS
    REPORTED RATHER THAN RESOLVED HERE.** `BR-REP-018` says *"no metadata
    rows"*, and `apps/tenancy/exports.py::write_csv`'s own docstring says *"one
    header row, then the data — nothing else ever goes in the file"*. `P2.22`
    says the refusal appears *"on screen **and in the CSV**"*. Both are signed
    statements and they disagree, so per CLAUDE.md hard-won law 13 the
    supersession is PUT TO THE PO and never assumed: `OQ-REP-12740`.

    **What ships in the meantime is the reading that cannot produce a wrong
    number in either direction:** the footer row is written ONLY when the file
    would otherwise have carried a figure that is not lawful. A file whose
    totals are all lawful is byte-identical to the file it is today, so IS-11
    is intact everywhere it is currently true, and the only files that gain a
    row are the ones whose alternative is an auditor reading a number that
    means nothing.

    The first cell is the label; every other cell is that column's total, or
    the em-dash with its reason.
    """
    row = [label]
    for column in columns[1:]:
        value = totals.get(column)
        if isinstance(value, Mapping) and value.get("refused") is True:
            row.append(f"{EM_DASH} {value.get('reason') or ''}".strip())
        elif value is None:
            row.append("")
        else:
            row.append(str(value))
    return row


def has_refusal(totals: Mapping[str, Any]) -> bool:
    """True when this footer must be written at all — see `csv_footer_row`."""
    return bool(refused_measures(totals))


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 2 · P2.22 (05-prototype/09 Reports Build Brief.pdf p13, p84, p85 read as images per B14 rule 42)
# screens: 2·1 footer
# generated: 2026-09-27 by lane REP-P2-MODEL
# checklist: A✔ B✔ C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_rep_p2_22_unlawful_total.py was shown red on all three cases before this file existed, and red again on the three assertions with `refusal_for` stubbed to return None
# exceptions: (1) the CSV footer row is a known tension with IS-11's "no metadata rows" — filed as OQ-REP-12740 and written so a lawful file is byte-identical to today's · (2) this module does NOT raise; P0.16's save-time raise is unchanged and neither replaces the other
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING (money rounding / money-path — 🔒)
# ──────────────────────────────────────────────────────────
