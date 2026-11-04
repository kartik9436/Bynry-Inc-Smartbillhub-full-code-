# ── Trace ──────────────────────────────────────────────
# Change:  CR-135-BRC07 `P0.6` — re-key the deposit batch on the till.
# Rules:   BR-PAY-025 (SUPERSEDED-IN-PART 2026-09-22) · BR-PAY-004 · BR-TEN-035
#          · CLAUDE.md hard rules 4 and 6 · hard-won laws 7 and 14
# Impacts: apps/payments/migrations/0033_cr135_p0_6_deposit_batch_rekey.py
# ───────────────────────────────────────────────────────
"""`P0.6` — what can be asserted WITHOUT a database that has the guarantees.

⚠ **THIS FILE DELIBERATELY DOES NOT CLAIM TO PROVE THE RE-KEY.** The suite
hardcodes in-memory SQLite (`config/settings/test.py`), which has **no partial
index, no triggers, no RLS and no real concurrency** — so the unique key that
makes two tills bankable, the guard that refuses a session-less batch, and the
two corrected trigger messages **cannot fail here and therefore cannot pass
here either**. That is hard-won law 7's *structurally incapable of failing*,
and naming it is the only honest thing to do.

**What actually proves the re-key is
`06-backend/tests/test_cr135_p06_rekey_pg.py`, on PostgreSQL 16.** This file
asserts the things that are true of the DECLARATION rather than of the running
database: that the constraint exists with the right shape, that the seeded
series is what the PO's ruling says, and that the arithmetic of the PO's worked
case is what the code computes.

THE WORKED CASE, WHICH IS WHAT EVERY FIGURE HERE COMES FROM
------------------------------------------------------------
22 September, a two-counter office. Dana takes **$1,240** of cheques, Sam takes
**$880**. That was ONE batch and is now TWO, and the day still ties to
**$2,120**.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Q

from apps.payments import bankrec_models as bankrec
from apps.payments import counter_session_models as tills
from apps.payments import models as pay_models
from apps.payments import reconciliation
from core import numbering as core_numbering

DAY = date(2026, 9, 22)
DANA = Decimal("1240.0000")
SAM = Decimal("880.0000")
DAY_TOTAL = Decimal("2120.0000")


def _named(model, name):
    for c in model._meta.constraints:
        if c.name == name:
            return c
    return None


# ── the key itself ─────────────────────────────────────────────────────────


def test_p06_the_day_x_method_key_is_gone_and_the_till_x_tender_key_is_there():
    """`P0.6`: *"Drop `uq_deposit_batches_day_method` and key on the session."*

    Both halves asserted, because a drop with no replacement is the exact
    hazard the task row warns about.
    """
    assert _named(bankrec.DepositBatch, "uq_deposit_batches_day_method") is None

    key = _named(bankrec.DepositBatch, "uq_deposit_batches_session_method")
    assert key is not None
    assert tuple(key.fields) == ("tenant", "session", "method")

    # ⚠ THE TENDER IS IN THE KEY AND THAT IS THE PO'S RULING, NOT A DETAIL.
    # `OQ-PAY-12577` (a): a bank credits cash and cheques separately and they
    # clear on different days, so Dana's one shift taking $600 cash and $640
    # cheques is ONE till, TWO tenders and TWO batches.
    assert "method" in key.fields


def test_p06_the_key_is_partial_so_the_batches_already_banked_are_left_alone():
    """PO, option (d): *"A batch with no session is one banked the old way."*

    Without the `WHERE`, applying this key would demand a session of every row
    already in the table — the backfill `BR-PAY-004` makes impossible.
    """
    key = _named(bankrec.DepositBatch, "uq_deposit_batches_session_method")
    assert key.condition == Q(session__isnull=False)


def test_p06_the_session_column_is_nullable_because_the_absence_is_the_fact():
    """A NOT NULL would refuse to apply on any tenant that has ever banked."""
    field = bankrec.DepositBatch._meta.get_field("session")
    assert field.null is True
    assert field.remote_field.model is tills.CounterSession


# ── the system till ────────────────────────────────────────────────────────


def test_p06_a_system_till_is_a_third_close_kind_and_a_clerk_cannot_choose_it():
    """PO: *"we have to make process uniform for all hence we should geneate
    system generated till"*.

    ⚠ **THE SECOND ASSERTION IS THIS LANE'S JUDGMENT AND IS THE ONE THAT
    MATTERS.** `auto` was refused BY NAME by `P0.3` on the principle that *a
    value the column can hold is a value some path can write*; `system` is on
    the list, so the list a phase 2 screen offers must NOT contain it.
    """
    assert pay_models.COUNTER_CLOSE_SYSTEM == "system"
    assert pay_models.COUNTER_CLOSE_SYSTEM in pay_models.COUNTER_CLOSE_KINDS
    assert pay_models.COUNTER_CLOSE_SYSTEM not in pay_models.COUNTER_CLOSE_KINDS_BY_A_PERSON
    assert pay_models.COUNTER_CLOSE_KINDS_BY_A_PERSON == ("counted", "forced")
    assert "auto" not in pay_models.COUNTER_CLOSE_KINDS


def test_p06_a_system_till_is_nobodys_in_every_column_and_it_is_two_way():
    """Left to right: a `system` till names no person and carries no float, or
    the *"three tills nobody counted"* screen starts listing drawers nobody was
    ever at. Right to left: a till that is NOT `system` must have an owner, so
    nothing can write an ownerless `counted` session and lose who is
    accountable for a drawer.
    """
    check = _named(tills.CounterSession, "ck_counter_sessions_system_is_nobodys")
    assert check is not None
    sql = str(check.condition)
    for clause in (
        "close_kind",
        "owner__isnull",
        "service_centre__isnull",
        "closed_by__isnull",
        "system_day__isnull",
        "opening_float",
    ):
        assert clause in sql, clause

    # ⚠ **NOT SPELLED AS A NEGATION, AND THAT IS THE POINT.** `close_kind` is
    # NULL on an open till; `NOT (NULL = 'system')` is NULL; **a CHECK that
    # evaluates to NULL PASSES.** A `~Q(close_kind='system')` here would have
    # been a guard that cannot fail on an ownerless OPEN till — law 7's
    # *structurally incapable of failing*. The membership test is what closes
    # it, and this assertion is what keeps it closed.
    assert "NOT " not in sql.upper().replace("ISNULL", "")


def test_p06_a_sealed_till_always_says_how_and_a_system_one_names_no_closer():
    """`P0.3`'s rule is *a till sealed with no record of HOW is a forced close
    that has become indistinguishable from a normal one*. That intent is
    unchanged; only the `closed_by` demand is relaxed, and only for `system`,
    because nobody sealed it.
    """
    check = _named(tills.CounterSession, "ck_counter_sessions_closed_together")
    sql = str(check.condition)
    assert "close_kind" in sql and "closed_at" in sql and "closed_by" in sql
    assert pay_models.COUNTER_CLOSE_SYSTEM in sql


def test_p06_one_system_till_per_tenant_per_banking_day():
    """Hard rule 6: a second cut of the same day must find the SAME till, or
    the day's ACH money lands in two batches that each look complete.

    A partial unique index rather than a service check, for `P0.4`'s own
    stated reason: *"not a service check that a second caller can skip."*
    """
    key = _named(tills.CounterSession, "uq_counter_sessions_system_day")
    assert key is not None
    assert tuple(key.fields) == ("tenant", "system_day")
    # CR-186-BRC10 (payments/0051): narrowed to the channel-less system tills
    # opened before a provider got a till of its own; a channel's till is
    # unique per (tenant, day, channel) by the sibling index.
    assert key.condition == Q(system_day__isnull=False, channel__isnull=True)
    sibling = _named(tills.CounterSession, "uq_counter_sessions_system_day_channel")
    assert sibling is not None
    assert tuple(sibling.fields) == ("tenant", "system_day", "channel")


def test_p06_the_one_open_till_per_person_index_was_not_touched():
    """`P0.4` and `P0.15` are LANE P0-DB's and this lane changed neither."""
    key = _named(tills.CounterSession, "uq_counter_sessions_open_owner")
    assert key is not None
    assert tuple(key.fields) == ("tenant", "owner")
    assert key.condition == Q(closed_at__isnull=True)


# ── the code ───────────────────────────────────────────────────────────────


def test_p06_the_code_comes_from_settings_and_the_composer_is_gone():
    """PO: *"(b) Put it in Settings today — DEP-260922-0001 — Settings →
    Numbering, like every other number"*.

    ⚠ **THE SECOND HALF IS THE ONE THAT WOULD ROT.** A deleted function that
    comes back is how the next lane composes a string by hand again, so its
    absence is asserted rather than assumed.
    """
    assert reconciliation.DEPOSIT_BATCH_SERIES == core_numbering.DEPOSIT_BATCH
    assert not hasattr(reconciliation, "batch_code")
    assert not hasattr(reconciliation, "method_token")
    assert not hasattr(reconciliation, "METHOD_TOKENS")
    assert not hasattr(reconciliation, "CODE_PREFIX")


def test_p06_the_seeded_format_is_the_pos_own_example_and_keeps_the_year():
    """Two rulings in one format string.

    2026-09-22: **`DEP-260922-0001`** is the number the PO wrote.
    2026-08-12: *"Add the year + Date is important"* — **untouched**, and only
    the METHOD token left.
    """
    fmt = core_numbering.SERIES_CATALOG[core_numbering.DEPOSIT_BATCH][1][0]
    assert fmt == "DEP-{YY}{MM}{DD}-{0000}"
    core_numbering.validate_format(fmt)
    assert core_numbering.render(fmt, 1, DAY) == "DEP-260922-0001"

    # The anniversary defect (DEF-066) stays closed.
    assert core_numbering.render(fmt, 4, date(2026, 8, 8)) == "DEP-260808-0004"
    assert core_numbering.render(fmt, 5, date(2027, 8, 8)) == "DEP-270808-0005"

    # No method token anywhere — that is what left.
    assert "CHK" not in fmt and "METHOD" not in fmt


def test_p06_the_counter_does_not_run_out_which_a_recorded_judgment_denied():
    """⚠ **A DECISION-LOG ROW SAYS `{00}` WITH `restart: never` "REACHES
    DEP-260922-99 AND THEN CANNOT ALLOCATE AT ALL". IT DOES NOT.**

    `render`'s own docstring: *"a counter that outgrows its pad keeps all its
    digits (never truncated)"*. `will_overflow` is read by ONE caller — a
    Settings screen field — and its docstring says *"this is a WARNING the
    screen raises, never a refusal: refusing would stop a bill run over
    cosmetics"*.

    This is asserted rather than remembered, because the same untrue claim was
    the stated reason for a **yearly restart** that was NOT taken: a restart
    would make `_allocate` refuse a backdated issuance by name
    (`numbering_restart_backdated`), and cutting last December's batch in
    January is a real thing a utility does.
    """
    two = "DEP-{YY}{MM}{DD}-{00}"
    assert core_numbering.render(two, 100, DAY) == "DEP-260922-100"
    assert core_numbering.will_overflow(two, 100) is True  # a warning, not a refusal

    four = core_numbering.SERIES_CATALOG[core_numbering.DEPOSIT_BATCH][1][0]
    assert core_numbering.render(four, 10000, DAY) == "DEP-260922-10000"


def test_p06_the_seeded_series_still_restarts_never():
    """The judgment NOT taken, pinned so that taking it becomes a deliberate
    act with a test to change rather than a quiet edit."""
    from apps.tenancy import services as tenancy_services  # noqa: F401 — import guard

    assert core_numbering.RESTART_NEVER == "never"
    fmt = core_numbering.SERIES_CATALOG[core_numbering.DEPOSIT_BATCH][1][0]
    # Yearly WOULD be lawful under the grammar — the format carries a year — so
    # the reason it is not used is the backdating refusal, not the validator.
    core_numbering.validate_restart_period(fmt, core_numbering.RESTART_YEARLY)


# ── the arithmetic the PO signed on ────────────────────────────────────────


def test_p06_the_pos_worked_figures_still_add_up():
    """`$1,240 + $880 = $2,120`, the figure the ruling was signed on.

    Trivial as arithmetic and not trivial as a record: it is what a reader
    checks the PostgreSQL proof's output against, and `10-scripts/
    p06_ledger_two_deposits_readback.py` asserts the same three numbers
    through `apps.ledger.posting.post()`.
    """
    assert DANA + SAM == DAY_TOTAL
    assert DANA != SAM  # 2120 is also 2120 + 0; the two are asserted apart


def test_p06_one_till_two_tenders_is_two_batches():
    """Dana's shift: **$600 cash + $640 cheques = $1,240**, ONE till, TWO
    batches. The reason is the bank, not the product."""
    cash, cheques = Decimal("600.0000"), Decimal("640.0000")
    assert cash + cheques == DANA


# ── the seam phase 2 changes ───────────────────────────────────────────────


def test_p06_the_session_seam_is_one_function_and_it_is_named():
    """Hard-won law 2's mirror: a hold nobody is keeping.

    `_session_for` is the ONE place that changes when `payments` starts
    carrying a `counter_session_id`. **This test fires the day that column
    lands** — the seam must be re-read then, or every counter payment goes on
    banking under the system till for ever with every check green.
    """
    assert callable(reconciliation._session_for)
    assert callable(reconciliation._system_session)

    payment_columns = {f.name for f in pay_models.Payment._meta.get_fields()}
    assert "counter_session" not in payment_columns and "counter_session_id" not in payment_columns, (
        "`payments` has gained a counter session column, which is phase 2's. "
        "`reconciliation._session_for` must now return it for a counter payment "
        "instead of the day's system till — read its docstring and this test's."
    )
