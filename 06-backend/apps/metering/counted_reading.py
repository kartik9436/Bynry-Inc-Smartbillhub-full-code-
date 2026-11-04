# ── Trace ──────────────────────────────────────────────
# Change:   DEF-WRK-9642 — PO ruling 2026-10-04 (decision log, "TWO READINGS ON
#           ONE REGISTER ON ONE DAY: BOTH ARE KEPT, AND THE ONE THAT COUNTS IS
#           THE HIGHEST OF THOSE THAT ARE APPROVED AND VALIDATED").
# Rules:    BR-MET-1189 (this file) · supersedes BR-MET-016 / BR-MET-052's
#           refuse-or-replace for a same-register, same-date pair ·
#           BR-MET-053 (committed → billed) · BR-MET-021 (one primary status) ·
#           BR-MET-129 (a warned reading posts) · BR-MET-024 (dispute = hold)
# Impacts:  selectors._read_heads (billing's read selection, the export pair,
#           move-in/out prefill, the runbook history) · services._head_qs (the
#           prior reading a new one is measured from, estimation history, the
#           true-up's standing estimates) · monthly_usage_service._read_rows
#           (consumption and usage) · submeter_reconciliation · the S50 Reads
#           tab (`counts` on every row of a same-day pair)
# 🔒 HUMAN-REVIEW-PENDING — billing-input path (which reading a bill is priced
#           from). Ledger row: 12-governance/09-human-review-ledger.md,
#           "DEF-WRK-9642 — the reading that counts".
# ───────────────────────────────────────────────────────
"""THE READING THAT COUNTS — one register, one date, one answer.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — a billing-input path (which reading a
bill is priced from). Ledger: `12-governance/09-human-review-ledger.md`, row
"DEF-WRK-9642 — the reading that counts".

PO, verbatim (2026-10-04): *"take the reading records in register and use date
and highest consumption reading if it is apprved and validated"*.

**The worked case the PO was shown.** Meter E-5000 holds an office reading of
**3,400 kWh** on 4 October. Technician R. Patel's move-in job WO-0043 posts
**3,412 kWh** the same day. Both readings are KEPT in the register. If both are
approved and validated, **3,412 kWh counts** and 3,400 stays as history. A
higher reading that is not approved, or not validated, never counts.

WHAT *APPROVED* AND *VALIDATED* MEAN HERE — read off the code, not invented
──────────────────────────────────────────────────────────────────────────
This repo has no column called `approved` on a meter read. It has a lifecycle,
and the two words map onto it as follows (recorded in the decision log beside
the ruling):

* **APPROVED** — the reading is IN THE REGISTER as a committed lineage head
  that nobody has objected to:
    - `lifecycle` is `committed` or `billed` (`READ_LIFECYCLES`, BR-MET-053).
      A reading only gets there through a human act: the uploader's
      certification at commit (US-MET-010 — *"the acting user committing the
      wizard IS the person certifying the entry"*) or the office pressing
      Accept on a field job that sat in *Awaiting approval* (BR-MET-110:
      *"utility staff will review these work order, accept them"*). A staged
      row is not a reading yet (BR-MET-012).
    - `superseded_by_id IS NULL` — a corrected reading is history of the
      correction, never a candidate (BR-MET-016/053).
    - NOT under an open dispute (`disputed_at` set and `dispute_cleared_at`
      empty). BR-MET-024: a dispute *"records a marker + reason on the read …
      and the account is HELD"* — a reading someone has formally objected to
      is the opposite of approved until the dispute is cleared.
* **VALIDATED** — the validation engine did not mark the number unusable:
  its one primary status (BR-MET-021) is NOT in
  `selectors.UNBILLABLE_READ_STATUSES` (`missing`, `negative_usage`,
  `mismatch`, `unknown_meter`, `duplicate`, `tou_sum_sanity`). A WARNED
  reading (`high`, `low`, `vacant_unit` …) IS validated: BR-MET-129 posts it
  and BR-MET-022 says *"flags never block billing by themselves"*. That list
  is billing's own existing filter, so "validated" here and "billable" there
  are one set, not two.

WHICH IS *HIGHEST*
──────────────────
The highest register value (`current_value`). Two readings of one register on
one date are both measured from the same earlier reading (`_prior_actual_head`
asks for `read_at < before`, strictly), so the highest dial IS the highest
consumption — the PO's word — on every lineage. An estimate carries no dial
(BR-MET-028) and ranks below any actual reading; ties fall to consumption,
then to the later-written row, so the answer is total and repeatable.

WHEN NOTHING IN THE GROUP IS APPROVED AND VALIDATED
───────────────────────────────────────────────────
Every row stays where it was, and the consumers' existing filters decide
exactly as they did before this rule existed (an unbillable reading is skipped
by billing; a lone reading is untouched). This rule only ever REMOVES a
same-day sibling in favour of an approved, validated one — it never promotes
a reading the old code would have refused.
"""

from __future__ import annotations

from typing import Any, Iterable

from django.db.models import Case, F, IntegerField, Q, QuerySet, Sum, Value, When, Window
from django.db.models.functions import RowNumber

from . import models

#: The rule id this module implements.
BR_REF = "BR-MET-1189"

#: BR-MET-053 — the two states a reading in the register can be in.
APPROVED_LIFECYCLES: tuple[str, ...] = ("committed", "billed")


def _not_validated_statuses() -> frozenset[str]:
    # Lazy: `selectors` imports this module, and the set is selectors' own —
    # one list, never a second copy (hard-won law 5).
    from .selectors import UNBILLABLE_READ_STATUSES

    return UNBILLABLE_READ_STATUSES


def approved_and_validated_q() -> Q:
    """The predicate, in SQL. See the module docstring for every clause."""
    return (
        Q(superseded_by_id__isnull=True, lifecycle__in=APPROVED_LIFECYCLES)
        & ~Q(status__in=sorted(_not_validated_statuses()))
        & (Q(disputed_at__isnull=True) | Q(dispute_cleared_at__isnull=False))
    )


def is_approved(read: Any) -> bool:
    return (
        getattr(read, "superseded_by_id", None) is None
        and getattr(read, "lifecycle", None) in APPROVED_LIFECYCLES
        and (
            getattr(read, "disputed_at", None) is None
            or getattr(read, "dispute_cleared_at", None) is not None
        )
    )


def is_validated(read: Any) -> bool:
    return getattr(read, "status", None) not in _not_validated_statuses()


def is_approved_and_validated(read: Any) -> bool:
    return is_approved(read) and is_validated(read)


#: Highest first: a dial beats no dial, then the dial, then consumption, then
#: the later-written row. The SQL and the Python below MUST order alike.
RANK = (
    F("current_value").desc(nulls_last=True),
    F("consumption").desc(nulls_last=True),
    F("id").desc(),
)


def _rank_key(read: Any) -> tuple:
    current = getattr(read, "current_value", None)
    consumption = getattr(read, "consumption", None)
    return (
        current is not None,
        current if current is not None else 0,
        consumption is not None,
        consumption if consumption is not None else 0,
        str(getattr(read, "id", "")),
    )


#: The (register, date) a reading belongs to — one window partition.
_PARTITION = (F("tenant_id"), F("asset_id"), F("channel"), F("read_at"))


def _eligible_flag() -> Case:
    return Case(
        When(approved_and_validated_q(), then=Value(1)),
        default=Value(0),
        output_field=IntegerField(),
    )


def only_counted(queryset: QuerySet) -> QuerySet:
    """`queryset` (lineage heads) with every same-day sibling that does NOT
    count removed. A reading alone on its date always stays.

    Kept: the row that IS its group's counted reading (row number 1 when the
    group is ordered eligible-first, then `RANK`), or every row of a group
    with NO approved-and-validated reading (the old behaviour, unchanged).

    ⚠ **A WINDOW, NOT A CORRELATED SUBQUERY — MEASURED.** The first version
    asked two correlated subqueries per row. On PostgreSQL 16 against the
    demo tenant's 516 heads over 28 monthly partitions it took **1,401 ms**
    against **49 ms** for the plain heads, and EXPLAIN ANALYZE put 1,374 ms of
    it in JIT compilation — the planner's cost estimate for 28 partitions x
    two sub-plans crossed `jit_above_cost`, and it grows with every partition
    added. The window is one scan and one sort: **54 ms** for the same rows.

    ⚠ **TWO THINGS A CALLER MUST KNOW.** (1) The window sees the rows the
    queryset's OTHER filters leave — Django puts every non-window filter in
    the inner query whatever order it was chained in — so a filter that
    removes one sibling and not the other (`current_value=…`) changes the
    contest. Every consumer today filters by meter, register and date range,
    which keeps whole groups. (2) Do NOT chain `.values(...).annotate(<an
    aggregate>)` onto the result: Django groups by the window columns too and
    the totals come out per row (measured: three `demand` rows instead of
    one). `.aggregate()`, `.count()`, `.exists()`, `.first()` and slicing are
    fine. `selectors.export_rollup_last_month` sums in Python for that reason.
    """
    flag = _eligible_flag()
    return queryset.annotate(
        _counted_rn=Window(
            RowNumber(), partition_by=list(_PARTITION), order_by=[flag.desc(), *RANK]
        ),
        _counted_eligible=Window(Sum(flag), partition_by=list(_PARTITION)),
    ).filter(Q(_counted_rn=1) | Q(_counted_eligible=0))


def counted_among(reads: Iterable[Any]) -> Any | None:
    """The reading that counts among readings of ONE register on ONE date, or
    None when none of them is approved and validated."""
    eligible = [read for read in reads if is_approved_and_validated(read)]
    if not eligible:
        return None
    return max(eligible, key=_rank_key)


def counted_flags(reads: Iterable[Any]) -> dict[str, bool | None]:
    """`{read_id: True | False | None}` for a listing of lineage heads.

    None — the reading is alone on its register and date, so there is nothing
    to tell apart and a screen draws nothing. True — it is the one that
    counts. False — a same-day sibling that is kept as history and does not
    count.
    """
    groups: dict[tuple, list[Any]] = {}
    for read in reads:
        if getattr(read, "superseded_by_id", None) is not None:
            continue
        key = (str(read.asset_id), read.channel, read.read_at)
        groups.setdefault(key, []).append(read)
    out: dict[str, bool | None] = {}
    for group in groups.values():
        if len(group) == 1:
            out[str(group[0].id)] = None
            continue
        winner = counted_among(group)
        for read in group:
            out[str(read.id)] = winner is not None and read.id == winner.id
    return out


def counted_flags_for(asset_id: Any, read_ats: Iterable[Any], tenant_id: Any) -> dict:
    """`counted_flags` over every head of one meter on the given instants —
    so a PAGE of the Reads tab can say which row counts even though its
    siblings are on the same page by construction (one page = whole dates)."""
    rows = models.MeterRead.objects.filter(
        tenant_id=tenant_id,
        asset_id=asset_id,
        read_at__in=list(read_ats),
        superseded_by_id__isnull=True,
    )
    return counted_flags(rows)


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-WRK-9642 · BR-MET-1189 (PO 2026-10-04)
# generated: 2026-10-04 by lane SAMEDAY
# checklist: A✔ B✔ C✔ D=n/a(consumed through selectors/services) E✔(S50 Reads tab) F✔ G✔ H✔ (🔒 billing input → review-ledger row)
# gates: tests/test_def_wrk_9642_same_day_readings.py (11) SQLite + PostgreSQL 16 · tests/golden · 03-golden-verify.py
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
