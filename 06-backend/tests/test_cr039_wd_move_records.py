# ── Trace ──────────────────────────────────────────────
# Change:   CR-039 wave D tasks 17–19 — *"decide what a move-in and move-out
#           ARE"* · *"build and number that record"* · *"seed one or two of
#           each"*, against the CR's trace finding 5: *"move-in and move-out
#           have NO RECORD AT ALL"*, consequence *"A clerk cannot quote a
#           reference; nothing on a bill can point at the job that caused a
#           change."*
# Rules:    BR-CUS-150 (a record of the JOB) · BR-CUS-151 (provenance, and
#           nothing that already has an owner) · BR-CUS-152 (append-only in
#           spirit) · BR-CUS-153 (its own series per flow) · BR-TEN-035
#           (allocated in the issuing transaction; never reused) · BR-TEN-043
#           (the event date is an input) · BR-CUS-021 (readings travel through
#           the metering door)
# Ruling:   PO 2026-08-27, verbatim and in full: *"you cna keep them as records
#           for audit perpuses"* — decision log, *"a move-in and a move-out ARE
#           records, kept for audit"*.
# ───────────────────────────────────────────────────────
"""What this file holds the build to, stated as the four things that could go
wrong and be invisible.

**1 · A RECORD THAT COPIES WHAT IT SHOULD POINT AT.** The ruling's own reason
for the shape is that *"a record that duplicated them would be a second copy of
a fact that already has an owner, which is how two numbers come to disagree"*.
That is not testable by reading the model — a column list looks fine either way
— so it is tested as a NEGATIVE over the model's own field names.

**2 · A NUMBER ALLOCATED OUTSIDE THE TRANSACTION.** BR-TEN-035's whole content.
Proved by making the INSERT fail and reading the counter back, which is the
device `test_cr039_wd_transfer_and_case_numbers` uses one flow over — a test
that only allocates successfully would pass against an allocator that ran first
and committed separately.

**3 · THREE ABSENCES COLLAPSING INTO ONE DASH.** DEF-127's shape, and DEF-182's
lesson about how a test can fail to see it: reading the CONSTANTS proves nothing
about which one the branch picks. `move_reference_cell` is a named function so
this file can call the branch itself.

**4 · A MOVE-IN's `from_account` LEFT NULL.** The link is the one fact
`services.move_in` has always returned and never stored. If it is dropped, every
other assertion here still passes.

**RED PROVED FIRST for every guard** (hard-won law 7). Each was broken in this
lane's own worktree, run, and the failure quoted in the lane report — r11 §2d's
own instruction, *"mutate in a `git worktree` … never in the shared tree"*.
"""

from datetime import date, timedelta

import pytest

from apps.customers import models as customers_models
from apps.customers import move_reads, moves, services
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from core import numbering as core_numbering

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    marcus,
    tenant_ctx,
)
from tests.test_w7_transfers import _mover

pytestmark = pytest.mark.django_db

#: ⚠ **A PROBE, NOT A PROPOSAL** — the device `test_cr039_wd_transfer_and_case
#: _numbers` uses and for the same reason: no catalogue would ever seed this, so
#: a pass cannot come from a real seeded default happening to match.
PROBE_FORMAT = "ZZPROBE-{YY}-{0000}"

TODAY = date(2026, 8, 25)


def _current_tenant_id():
    from core import tenancy as core_tenancy

    return core_tenancy.current_tenant_id()


def _forget_series(series: str) -> None:
    """A tenant provisioned BEFORE 2026-08-27 — a real state, not a contrivance.

    `_seed_number_series` is `get_or_create` per series, so a host already
    running when these two rows joined the catalogue keeps no `move_in` /
    `move_out` row until somebody runs `manage.py seed_demo --tenant
    <subdomain>`. Deleting the row is the only way to reach that branch now that
    provisioning seeds it.
    """
    tenancy_models.NumberSeries.objects.filter(
        tenant_id=_current_tenant_id(), series=series
    ).delete()


@pytest.fixture(autouse=True)
def series_sink():
    """The REAL sink the real callers use — `AppConfig.ready` registers it."""
    core_numbering.set_series_sink(tenancy_services.allocate_series_number)
    yield
    core_numbering.set_series_sink(tenancy_services.allocate_series_number)


def _moved_out(actor, tenant, *, label="18 Marten Row", name="Iversen, Britt"):
    """One account taken through the REAL `services.move_out`.

    Never `MoveRecord.objects.create(...)`: the thing under test is that the
    FLOW leaves a record, and a fixture that wrote the row itself would pass
    against a `move_out` that writes none.
    """
    _customer, account, unit = _mover(actor, tenant, label=label, name=name)
    payload = services.move_out(
        actor, str(account.id), {"moved_out_on": account.opened_at.isoformat()}
    )
    return account, unit, payload


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE SHAPE THE RULING DECIDED — the JOB, not its effects
# ═══════════════════════════════════════════════════════════════════════════
def test_the_record_copies_nothing_that_already_has_an_owner():
    """⛔ **A NEGATIVE, AND IT IS THE ONLY WAY THIS RULE IS CHECKABLE.**

    PO ruling 2026-08-27, and the sentence that decides the columns: *"It
    records the job, not its effects. The occupancy change and the account state
    are already written and are not moved here — a record that duplicated them
    would be a second copy of a fact that already has an owner, which is how two
    numbers come to disagree."*

    Every name below has an owner named beside it. A later lane adding one
    *"so the tab does not have to join"* is exactly the change this refuses,
    and the failure message says where the fact lives instead.
    """
    owned_elsewhere = {
        "status": "accounts.status — written by the same transaction",
        "status_id": "accounts.status",
        "opened_at": "accounts.opened_at (`effective_on` is the JOB's date, not a copy)",
        "closed_at": "accounts.closed_at",
        "occupied": "DERIVED from the status class (BR-MET-036); no column exists to copy",
        "unit_id": "accounts.unit_id — reachable through `account`",
        "final_read_state": "accounts.final_read_state (CR-038 W9 task 4)",
        "reads": "meter_reads, via the BR-CUS-021 event door",
        "readings": "meter_reads",
        "balance": "the LEDGER; `accounts.balance` is itself only a cache",
        "deposit_on_file": "accounts.deposit_on_file (BR-CUS-023 — a lookup)",
        "settlement": "computed at read time by `move_out_settlement`, with its gaps",
    }
    fields = {f.name for f in moves.MoveRecord._meta.get_fields()}
    trespassing = sorted(fields & set(owned_elsewhere))
    assert not trespassing, {name: owned_elsewhere[name] for name in trespassing}


def test_the_deposit_election_is_refused_by_name_rather_than_stored(brazos):
    """⛔ **DEF-921 — THE RULING NAMES A FACT NEITHER WIZARD HOLDS.**

    The decision-log entry enumerates *"the clerk, the moment, the effective
    date, the reads taken, **the deposit election**"* and calls that *"exactly
    the set of facts a wizard currently holds and then discards"*. Measured:
    `services.REFUSED_FIELDS` refuses `deposit_on_file` on every door that edits
    an account, S19 draws no deposit radios and S20 draws no disposition radios,
    both by name, both citing BR-CUS-023/024.

    So a `deposit_carry_elected` column here would be a slot nothing can fill —
    hard-won law 2 on data. This pins the refusal in BOTH directions so neither
    a lane adding the column nor a lane quietly opening the door can move it
    without reading DEF-921 and OQ-510.
    """
    fields = {f.name for f in moves.MoveRecord._meta.get_fields()}
    assert "deposit_carry_elected" not in fields, (
        "a deposit-election column has appeared on `move_records`. The PO ruled the "
        "RECORD and a signature covers only what was shown — NEITHER wizard collects an "
        "election today (BR-CUS-023/024), so this column has no writer. If S19/S20 now "
        "offer one, OQ-510 has been answered and DEF-921 closes; say so before adding it."
    )
    # The other half of the same fact, so this test fails if the wizards start
    # accepting one without the record learning about it.
    assert "deposit_on_file" in services.REFUSED_FIELDS
    assert "deposit_carry_elected" not in services.MOVE_IN_FIELDS
    assert "deposit_disposition" not in services.MOVE_OUT_FIELDS


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE FLOWS LEAVE ONE — and the number is the tenant's own
# ═══════════════════════════════════════════════════════════════════════════
def test_a_move_out_leaves_a_numbered_record_of_the_job(brazos, marcus):
    """CR-039 finding 5 closed for the move-out half: a clerk can quote one.

    The expected number is RE-DERIVED through the product's own `render` from
    the tenant's stored format rather than typed as a literal — a literal here
    would be DEF-615 again, a test and a catalogue each picking one. The literal
    `MVO-26-0001` is asserted exactly once, further down.
    """
    with tenant_ctx(brazos):
        row = tenancy_models.NumberSeries.objects.get(
            tenant_id=_current_tenant_id(), series=moves.MOVE_OUT_SERIES
        )
        counter = row.next_number
        account, _unit, payload = _moved_out(marcus, brazos)
        expected = core_numbering.render(row.format, counter, account.opened_at)
        stored = moves.MoveRecord.objects.get(id=payload["move_record_id"])

    assert payload["move_no"] == expected
    assert payload["move_no_unavailable"] is None
    # ON THE ROW, not merely in the response — a number that exists only in an
    # HTTP answer is not a record.
    assert stored.move_no == payload["move_no"]
    assert stored.kind == moves.KIND_MOVE_OUT
    assert stored.account_id == account.id
    # BR-CUS-151 — the provenance, and the WHO is the acting clerk rather than
    # whoever happens to own the account.
    assert stored.performed_by_id == marcus.id
    assert stored.effective_on == account.opened_at
    # BR-TEN-043 — the BUSINESS date and the WALL CLOCK are different columns
    # and a backdated move must not collapse them into one.
    assert stored.performed_at is not None


def test_a_move_in_records_the_outgoing_account_it_followed(brazos, marcus):
    """⚠ **THE FACT `move_in` HAS ALWAYS RETURNED AND NEVER STORED.**

    `services.move_in` puts `moved_in_after_account_id` in its response and
    nothing writes it down, so reopening the page tomorrow loses the chain from
    the tenancy that ended to the one that began. BR-CUS-151 says that is
    exactly what this record is for.
    """
    with tenant_ctx(brazos):
        account, unit, _out = _moved_out(marcus, brazos, label="3 Kestrel Close")
        result = services.move_in(
            marcus,
            str(account.id),
            {
                "account_type": "residential",
                "opened_at": (account.opened_at + timedelta(days=1)).isoformat(),
                "contact": {"full_name": "Haddad, Nour"},
                # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
                # customer identifies nobody, and this fixture's own name went in above.
                # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
                "customer": identity_fixtures.customer_block(
                    "Haddad, Nour", account_type="residential"
                ),
            },
        )
        stored = moves.MoveRecord.objects.get(id=result["move_record_id"])

    assert stored.kind == moves.KIND_MOVE_IN
    assert str(stored.account_id) == result["id"], "the record names the NEW account"
    assert stored.from_account_id == account.id, (
        "the move-in record dropped the outgoing account. That link is returned as "
        "`moved_in_after_account_id` and stored nowhere else in this product."
    )
    # The two are different accounts — a record naming the same one on both
    # sides would satisfy the assertions above and mean nothing.
    assert stored.from_account_id != stored.account_id
    # The move-in draws from the MOVE-IN series, never the move-out's — two
    # counters is the whole point of BR-CUS-153's two rows.
    assert result["move_no"].startswith("MVI-")
    assert unit is not None


def test_the_first_move_in_and_move_out_on_a_new_tenant_are_mvi_and_mvo_26_0001():
    """⚠ **THE BUILD'S FIGURES, PINNED SO DRIFT GOES RED — AND THEY ARE NOT
    RULED FIGURES.**

    The PO ruled the RECORD (*"you cna keep them as records for audit
    perpuses"*) and the decision log states in as many words that the ruling
    *"DOES NOT SETTLE D18's NUMBERING"*. The build EXTENDS the disconnect's
    ruling of the same day — a disconnect is a one-account job and got its own
    series, so the argument that a one-account job needs none is dead — and
    records that as an extension. **One word from the PO reverses it**, and this
    is the assertion that would then have to be changed deliberately rather than
    drifting.

    Deterministic on purpose: the issue date is a literal, so this says the same
    thing in 2027.
    """
    move_in_default = tenancy_services.SERIES_DEFAULTS[core_numbering.MOVE_IN]
    move_out_default = tenancy_services.SERIES_DEFAULTS[core_numbering.MOVE_OUT]
    assert move_in_default == "MVI-{YY}-{0000}"
    assert move_out_default == "MVO-{YY}-{0000}"
    assert core_numbering.render(move_in_default, 1, date(2026, 8, 27)) == "MVI-26-0001"
    assert core_numbering.render(move_out_default, 1, date(2026, 8, 27)) == "MVO-26-0001"
    # ⛔ TWO SERIES, NOT ONE. A shared `MV-` would make `MV-26-0004` unreadable
    # as an arrival or a departure, which is the property they were split to
    # keep. This is what makes "two counters" checkable rather than promised.
    assert core_numbering.MOVE_IN != core_numbering.MOVE_OUT
    assert core_numbering.literal_prefix(move_in_default) != core_numbering.literal_prefix(
        move_out_default
    )


def test_a_move_with_no_series_reports_the_absence_and_never_invents_a_number(brazos, marcus):
    """A host provisioned before 2026-08-27, which is every existing one.

    Three things must hold at once, and the third is the one a later lane is
    tempted to "fix": the number is NULL, a REASON is served beside it, and the
    reason does not carry an internal id into a clerk's sentence (DEF-332).
    """
    with tenant_ctx(brazos):
        _forget_series(moves.MOVE_OUT_SERIES)
        _account, _unit, payload = _moved_out(marcus, brazos, label="7 Tanner Way")
        stored = moves.MoveRecord.objects.get(id=payload["move_record_id"])

    assert (
        payload["move_no"] is None
    ), f"a number was invented where no series exists: {payload['move_no']!r}"
    assert stored.move_no is None
    absence = payload["move_no_unavailable"]
    assert absence is not None, "an absent move number served no reason at all"
    assert absence["code"] == moves.NUMBERING_SERIES_MISSING
    assert absence["series"] == moves.MOVE_OUT_SERIES
    assert "number series for move-outs has not been set up" in absence["detail"]
    # ⛔ The MOVE still happened. A numbering gap must never refuse a household.
    assert payload["closed_at"] is not None


def test_two_move_outs_get_two_numbers_and_the_counter_moves_forward(brazos, marcus):
    """BR-TEN-035: forward-only, never reused.

    Kept separate from the cases above because each of those allocates exactly
    once, which would pass identically against an allocator returning a
    constant.
    """
    with tenant_ctx(brazos):
        _a1, _u1, first = _moved_out(marcus, brazos, label="18 Marten Row")
        _a2, _u2, second = _moved_out(marcus, brazos, label="3 Kestrel Close", name="Haddad, Nour")

    assert first["move_no"] != second["move_no"]
    assert first["move_no"].endswith("-0001")
    assert second["move_no"].endswith("-0002")


# ═══════════════════════════════════════════════════════════════════════════
# 3 · IN THE TRANSACTION — the rule that makes the number trustworthy
# ═══════════════════════════════════════════════════════════════════════════
class Boom(RuntimeError):
    """The INSERT itself failing — a unique-index clash, a constraint, a
    connection dropping between two statements."""


def _make_the_insert_fail():
    """Make `MoveRecord.objects.create(...)` raise, and nothing before it.

    ⚠ **THIS SHAPE IS BORROWED FROM `test_cr039_wd_transfer_and_case_numbers
    ._make_the_insert_fail` BECAUSE THAT LANE ALREADY PROVED THE OBVIOUS SHAPE
    CANNOT TELL THE TWO WORLDS APART.** Its note, which applies here word for
    word: a version that wrapped the call in an `atomic()` of its own and raised
    AFTER it returned **passes in both worlds**, because the outer block rolls
    back to ITS savepoint and takes the counter with it whether the allocation
    happened inside the writer's transaction or outside it.

    What separates them is the WRITE failing while the ALLOCATION stands.
    `record_move` allocates FIRST and creates SECOND, so raising from `create`
    lands strictly after the number was drawn — with the allocation inside
    `move_out`'s `atomic()` the two unwind together; with it outside, the
    counter has moved and survives, and the tenant's next move-out carries a
    number with a hole before it that nothing accounts for.

    ⚠ **IT TAKES A PRIVATE `pytest.MonkeyPatch()` AND NOT THE `monkeypatch`
    FIXTURE, AND THAT IS DEF-922 — A TRAP WORTH READING BEFORE WRITING ANY TEST
    IN THIS SUITE.** `tests/test_us_ten_helpers.sqlite_guc` is an **autouse**
    fixture that patches `core.tenancy.connection` with a recording fake,
    because *"sqlite has no set_config"*. It does that through the SAME
    function-scoped `monkeypatch` instance every test in the file shares. So a
    test that calls `monkeypatch.undo()` to lift its OWN patch **also lifts the
    autouse one**, `core.tenancy.connection` becomes the real sqlite
    connection, and the very next `tenant_ctx` dies on

        sqlite3.OperationalError: no such function: set_config

    — a failure that looks like a broken transaction and is a disarmed fixture.
    `undo()` reads as local and is global to the instance; nothing warns.
    `tests/test_us_bil_surface_apis.py` had already found the safe shape and is
    the precedent followed here: a private instance, undone in a `finally`, so
    the window is exactly this one patch.
    """
    from pytest import MonkeyPatch

    def boom(*_args, **_kwargs):
        raise Boom("the row could not be written")

    patch = MonkeyPatch()
    patch.setattr(moves.MoveRecord.objects, "create", boom)
    return patch


def test_a_rolled_back_move_out_leaves_no_record_and_no_stranded_number(brazos, marcus):
    """BR-TEN-035 — *"allocated INSIDE the issuing transaction"*, and the whole
    reason this is a rule rather than a preference.

    If the allocation ran in its own transaction, the counter would advance for
    a move-out that never happened and the next real one would carry a number
    with a hole before it that nobody could account for. Gaps ARE permitted by
    BR-TEN-035 — from a rolled-back transaction — and what is NOT permitted is
    the counter surviving a rollback, because then the gap is invisible.

    The INSERT is made to fail rather than the flow, so the failure lands
    strictly AFTER the allocation — see `_make_the_insert_fail`. A test that
    failed earlier would pass against an allocator that had never run.
    """

    def _counter() -> int:
        return tenancy_models.NumberSeries.objects.get(
            tenant_id=_current_tenant_id(), series=moves.MOVE_OUT_SERIES
        ).next_number

    # ⚠ **ONE `tenant_ctx` BLOCK, exactly as the transfer's twin has** — and the
    # patch is undone in a `finally` so the mutation window is precisely the
    # call it is about. An earlier version split this into three blocks to work
    # around what looked like a soured connection; the real cause was
    # `monkeypatch.undo()` disarming an autouse fixture (DEF-922, and see
    # `_make_the_insert_fail`), so the split was a workaround for a diagnosis
    # that was wrong and is gone with it.
    with tenant_ctx(brazos):
        _customer, account, _unit = _mover(marcus, brazos, label="9 Harrow Lane")
        before = _counter()

        patch = _make_the_insert_fail()
        try:
            with pytest.raises(Boom):
                services.move_out(
                    marcus, str(account.id), {"moved_out_on": account.opened_at.isoformat()}
                )
        finally:
            patch.undo()

        after = _counter()
        records = moves.MoveRecord.objects.filter(account_id=account.id).count()
        reread = customers_models.Account.objects.get(id=account.id)

    assert records == 0, "a record survived a rolled-back move-out"
    assert after == before, (
        "the counter advanced for a move-out that never happened — the allocation is "
        "running outside the flow's transaction (BR-TEN-035)"
    )
    # And the ACCOUNT is untouched: one transaction, BR-SHL-019.
    assert reread.closed_at is None


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE THREE ABSENCES — DEF-127's shape, DEF-182's lesson
# ═══════════════════════════════════════════════════════════════════════════
def test_the_three_reasons_a_move_reference_can_be_empty_are_not_the_same_reason():
    """⚠ **THE BRANCH IS CALLED, NOT THE CONSTANTS READ (DEF-182).**

    `disconnect_reads`'s equivalent test read its two constants and stayed GREEN
    when both arms of the decision were collapsed onto one of them. Three arms
    is a stronger version of the same trap, so this calls
    `move_reference_cell` itself.

    (a) a real record with a number · (b) a real record with none — a tenant
    with no series row · (c) no record: the job predates 2026-08-27 · (d) a
    move-in that has not completed, so no job has happened at all.
    """
    numbered = move_reads.move_reference_cell(
        {"move_no": "MVO-26-0001", "move_no_unavailable": None}
    )
    unnumbered = move_reads.move_reference_cell(
        {
            "move_no": None,
            "move_no_unavailable": dict(moves.MOVE_NUMBER_UNAVAILABLE[moves.KIND_MOVE_OUT]),
        }
    )
    no_record = move_reads.move_reference_cell(None)
    draft = move_reads.move_reference_cell(None, drafted=True)

    assert numbered["move_no"] == "MVO-26-0001"
    assert numbered["move_no_unavailable"] is None

    codes = {
        "unnumbered": unnumbered["move_no_unavailable"]["code"],
        "no_record": no_record["move_no_unavailable"]["code"],
        "draft": draft["move_no_unavailable"]["code"],
    }
    assert (
        len(set(codes.values())) == 3
    ), f"two of the three absences share a code, so a screen cannot tell them apart: {codes}"
    # And the SENTENCES, not only the codes — a clerk reads the sentence.
    assert "number series for move-outs" in unnumbered["move_no_unavailable"]["detail"]
    assert (
        "number series" not in no_record["move_no_unavailable"]["detail"]
    ), "a job that predates the record must not be described as a settings gap"
    assert "number series" not in draft["move_no_unavailable"]["detail"]
    # ⚠ **THIS LINE READ `"has not completed" in …` UNTIL 2026-10-02, AND WAS
    # RED FROM 2026-09-22 (`922a640fc`).** `BR-CUS-1090` (PO ruling 2026-09-22,
    # *"do you ahve move in request ID in numbering?"* … *"fix all these
    # issues"*) numbers a move-in the moment it is APPROVED, not when it
    # completes, so the sentence was rightly rewritten: a draft move-in is no
    # longer waiting for completion, it is waiting for an approval or a wizard.
    # The case asserts the ruled sentence; the codes stay three, as above.
    assert "No number has been issued" in draft["move_no_unavailable"]["detail"]
    assert "approved" in draft["move_no_unavailable"]["detail"]
    assert "has not completed" not in draft["move_no_unavailable"]["detail"]


def test_the_move_outs_tab_carries_the_reference_and_the_move_ins_tab_states_why_it_cannot(
    brazos, marcus
):
    """2b — **a number a clerk cannot SEE is not a number.**

    The asymmetry is the interesting assertion. §5.6's list is CLOSED accounts,
    so the column fills; §5.5's list is BR-CUS-018 DRAFTS — *"a row LEAVES this
    list when the move-in completes"* — so no job has happened yet and the cell
    states that rather than showing a dash a clerk has to interpret.
    """
    with tenant_ctx(brazos):
        account, _unit, payload = _moved_out(marcus, brazos, label="21 Foundry Row")
        outs = move_reads.move_outs_list()
        ins = move_reads.move_ins_list()

    assert outs["columns"][0] == "reference", "the reference must LEAD, as it does on S89/S90"
    assert ins["columns"][0] == "reference"
    row = next(r for r in outs["rows"] if r["account_id"] == str(account.id))
    assert row["move_no"] == payload["move_no"]
    assert row["move_no_unavailable"] is None
    for draft_row in ins["rows"]:
        assert draft_row["move_no"] is None
        assert draft_row["move_no_unavailable"]["code"] == "move_in_not_completed"


# ── Lifecycle ─────────────────────────────────────────────
# generated: 2026-08-27, CR-039 wave D tasks 16–19 lane
# exceptions: E1 this file asserts nothing about the SEEDED records (task 19) —
#             `tests/test_w5_move_in_out_cases.py` owns the W5 fixture's
#             dispositions and the seeder's own idempotence is asserted there,
#             and a second opinion about which rows are plantable is exactly the
#             drift `w5_move_fixture_report` exists to prevent
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
