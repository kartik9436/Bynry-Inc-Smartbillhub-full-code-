# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-009 (the bounce) · US-PAY-014 (the collection ladder)
#           CR-059 CS-5, the DEFECT half: `reverse_payment` declared and
#           documented `resume_collections` and never read it, so
#           `ladder.restart_after_bounce` had no caller and two docstrings
#           asserted a guarantee the code did not provide.
#           Screens: S33 · S34 · S35
# Rules:    BR-PAY-016 as amended 2026-08-12 (after a BOUNCE the ladder
#           restarts at rung 1 — OQ-133, PO verbatim *"Restart from the
#           beginning"*) · BR-PAY-013 (the bounce itself) · BR-PAY-017 (the
#           ladder) · CLAUDE.md rule 1 (tenant scoping) · rule 7 (every money
#           action writes audit_log) · hard-won law 1 (a comment claiming a
#           guarantee is not the guarantee) · hard-won law 2 (built is not
#           wired) · hard-won law 7 (prove it RED first)
# ───────────────────────────────────────────────────────
"""The bounce actually restarts the ladder now, and the docstrings are pinned.

**WHY THIS FILE EXISTS.** Every figure below was already ruled, built and
tested — and none of it ran. `ladder.restart_after_bounce` was written, audited
and covered by `test_us_pay_014_tc5b`; `reverse_payment` declared
`resume_collections`, documented in eleven lines what it did, and **never read
it**. The one existing test that passed `resume_collections=True`
(`test_us_pay_009_the_two_rulings_of_20260812_are_built`) asserted only
`created is True`, so the whole ruling was green with nothing wired.

    the ruling      after a bounce the ladder restarts at RUNG 1, not by age
    why             J12's account is 58 days overdue the moment its cheque
                    comes back, so resuming BY AGE makes a certified 48-hour
                    disconnection notice the customer's FIRST contact about a
                    **$1,842.10** bill they believed they had paid
    what ran        nothing

**THE FOUR PROOFS, AND THE TWO SHAPES THEY TAKE.** Two are behavioural — the
bounce moves the state row, and the default does not. Two are STRUCTURAL, and
they are the ones that would have caught this in August: a parameter that
nothing reads, and a docstring naming a caller that does not exist, are both
visible in the syntax tree of the file that makes the claim.

**RED BEFORE GREEN (hard-won law 7).** All four were run against the unfixed
`reversal.py` first and the transcripts are in the CR-059 CS-5 report:
`assert state.tier is None` failed with `TIER_SECOND_5_DAY`;
`collection_ladder_restarted` was absent from a result carrying
`collection_ladder_paused`; the parameter check named
`['resume_collections']`; and `restart_after_bounce` appeared **nowhere** in
`reversal.py`, not even in prose.
"""

import ast
import pathlib
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import ladder, models, reversal
from apps.payments.collections_models import (
    TIER_FRIENDLY,
    TIER_SECOND_5_DAY,
    AccountCollectionState,
)

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import a_payment, pe1_bills
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: J12's own dates, copied from `test_us_pay_009_nsf.py` rather than recomputed.
RETURNED_ON = datetime(2026, 8, 3, 11, 15, tzinfo=UTC)
#: The tier the account had already reached before the cheque came back — the
#: 5-day disconnect notice. The next rung by AGE would be the certified final.
REACHED = date(2026, 7, 20)


def a_bounce(actor, payment_id, **overrides):
    """The PE-7 bounce through the real service — no ORM shortcuts.

    Copied from `test_us_pay_009_nsf.py` rather than imported: importing a test
    module for one helper drags its fixtures and its `pytestmark` in with it.
    """
    values = dict(
        payment_id=payment_id,
        returned_on=RETURNED_ON,
        reason=models.REVERSAL_REASON_NSF,
        idempotency_reference=uuid.uuid4(),
    )
    values.update(overrides)
    return reversal.reverse_payment(actor, **values)


def _bounceable(tenant, actor, *, account_no):
    """An account mid-ladder, with PE-1's bills and a cleared cheque on them."""
    account = an_account(actor, tenant, account_no=account_no)
    pe1_bills(tenant, account)
    recorded = a_payment(actor, account)
    AccountCollectionState.objects.create(
        tenant=tenant,
        account=account,
        tier=TIER_SECOND_5_DAY,
        tier_sent_on=REACHED,
        last_notice_on=REACHED,
    )
    return account, recorded


# ── 1 · THE RULING, END TO END ─────────────────────────────────────────────
def test_cr059_cs5__a_bounce_that_resumes_collections_restarts_the_ladder_at_rung_1(
    brazos, marcus, dana, audit_rows
):
    """OQ-133, PO 2026-08-12: *"Restart from the beginning"*.

    The account has already had its 5-day disconnect notice. Its cheque comes
    back. The next thing it hears must be the FRIENDLY REMINDER — rung 1 — and
    not the certified 48-hour final its age would select.
    """
    with tenant_ctx(brazos):
        account, recorded = _bounceable(brazos, marcus, account_no="A-11031")

        result = a_bounce(dana, recorded.payment_id, resume_collections=True)

        state = AccountCollectionState.objects.get(account=account)
        assert state.tier is None, (
            "the bounce did not reset the collection state, so the next evaluation "
            "resumes at the tier this account had already reached"
        )
        assert state.tier_sent_on is None
        # The reset is only worth anything if the ladder then OFFERS rung 1.
        assert (
            ladder.decide(
                account_id=account.pk,
                as_of=date(2026, 9, 30),
                balance=Decimal("1842.10"),
                oldest_due_on=date(2026, 7, 6),
                balance_floor=Decimal("25.00"),
                partial_pause_percent=None,
                current_rung=state.tier,
            ).rung
            == TIER_FRIENDLY
        )

        # The result SAYS what it did — the reversal never leaves an absence or
        # a presence to be inferred (the `REVERSE_UNAVAILABLE` discipline).
        codes = {problem["code"] for problem in result.problems}
        assert "collection_ladder_restarted" in codes
        assert "collection_ladder_paused" not in codes, (
            "a static 'this ladder is paused' beside a per-bounce 'it was restarted' "
            "is two answers to one question"
        )

        # hard rule 7 — the restart is a real consequence for a real person.
        restarts = [row for row in audit_rows if row["action"] == ladder.AUDIT_LADDER_RESTART]
        assert len(restarts) == 1
        assert restarts[0]["entity_id"] == str(account.pk)


# ── 2 · THE DEFAULT, WHICH IS THE OTHER HALF OF THE RULING ─────────────────
def test_cr059_cs5__the_default_pauses_and_leaves_the_ladder_exactly_where_it_stands(
    brazos, marcus, dana, audit_rows
):
    """A bounce PAUSES and a person resumes — the ruling settled WHERE it
    restarts, not that it should happen with nobody asking.

    So the wiring must not become an automatic restart on every bounce. This is
    the test that fails if a later lane "simplifies" the flag away.
    """
    with tenant_ctx(brazos):
        account, recorded = _bounceable(brazos, marcus, account_no="A-11032")

        result = a_bounce(dana, recorded.payment_id)  # the default

        state = AccountCollectionState.objects.get(account=account)
        assert state.tier == TIER_SECOND_5_DAY
        assert state.tier_sent_on == REACHED
        codes = {problem["code"] for problem in result.problems}
        assert "collection_ladder_paused" in codes
        assert "collection_ladder_restarted" not in codes
        assert not [row for row in audit_rows if row["action"] == ladder.AUDIT_LADDER_RESTART]


def test_cr059_cs5__an_unpublished_ladder_is_reported_by_name_and_the_bounce_still_lands(
    brazos, marcus, dana, monkeypatch
):
    """The seam REPORTS; it never assumes and it never takes the money down.

    `_restart_ladder` resolves `restart_after_bounce` by name, so this deletes
    the attribute and lets the real resolve fail — the same posture
    `_record_nsf` takes when customers publishes no `record_nsf`, and the same
    posture customers' own `record_nsf` takes when it cannot read the privilege
    threshold: report by name, decide nothing.

    **A bounce that reached the books must be recorded whatever happens next.**
    The reversing row, the reversed allocations and the ledger mirror are the
    fact; the collection reset is a consequence, and losing the record of
    returned money to a missing consequence would be the worse failure.
    """
    with tenant_ctx(brazos):
        account, recorded = _bounceable(brazos, marcus, account_no="A-11033")
        monkeypatch.delattr(ladder, "restart_after_bounce")

        result = a_bounce(dana, recorded.payment_id, resume_collections=True)

        assert result.created is True
        assert result.amount == -Decimal("292.87")  # PE-7's reversing row, exact
        codes = {problem["code"] for problem in result.problems}
        assert "collection_ladder_not_restarted" in codes
        assert "collection_ladder_restarted" not in codes
        # It is NOT reported as a pause either: nobody paused anything, and a
        # wrong reason is as unusable to a clerk as no reason.
        assert "collection_ladder_paused" not in codes
        assert AccountCollectionState.objects.get(account=account).tier == TIER_SECOND_5_DAY


# ── 3 · THE STRUCTURAL PROOFS — hard-won laws 1 and 2, in the syntax tree ──
def _function(module, name):
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{module.__name__} declares no function {name!r}")


def _names_called_or_reached(module):
    """Every name this module's CODE reaches — prose excluded, deliberately.

    A docstring is `ast.Expr(Constant(str))` and is skipped; a name is counted
    only where it is an attribute access or a string handed to a call, which is
    how a by-name seam resolve (`_resolve("payments", "x", "ladder")`) reads.
    A `detail` string sitting in a dict is NOT counted — that is prose with a
    comma in it, and counting it would let this test pass on the very defect it
    was written for.
    """
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    reached: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            reached.add(node.attr)
        elif isinstance(node, ast.Call):
            for argument in [*node.args, *(kw.value for kw in node.keywords)]:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    reached.add(argument.value)
    return reached


def test_cr059_cs5__every_parameter_reverse_payment_declares_is_read_in_its_body():
    """Hard-won law 2 — *built is not wired* — asserted on the signature.

    `resume_collections` was accepted, documented in eleven lines and read by
    nothing: a caller passing `True` got the default behaviour, silently, and
    every test stayed green. A parameter that no statement in the body loads is
    that defect, whatever it is called next time.
    """
    function = _function(reversal, "reverse_payment")
    declared = {
        argument.arg
        for argument in [*function.args.args, *function.args.kwonlyargs]
        if argument.arg != "self"
    }
    read = {
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    assert declared <= read, (
        f"`reverse_payment` declares {sorted(declared - read)} and its body never reads "
        "them. A documented parameter nothing reads is a promise the code does not keep "
        "(CLAUDE.md hard-won laws 1 and 2, CR-059 CS-5)."
    )


def test_cr059_cs5__the_ladder_docstrings_claim_of_a_caller_is_true_in_code():
    """Hard-won law 1 — *a comment claiming a guarantee is not the guarantee*.

    `ladder.py` states that `reversal.py` calls `restart_after_bounce`. For
    three weeks that sentence was simply false, and nothing could see it because
    no gate in this repo reads prose. This test makes the claim and the call one
    fact: the sentence must name the CONDITION (the caller's
    `resume_collections` choice), and `reversal.py` must actually reach the
    function by name.

    **If a later lane takes CR-059's other branch and DELETES the flag, this
    test is meant to fail** — delete it in the same commit, deliberately, rather
    than leaving the claim standing.
    """
    ladder_source = pathlib.Path(ladder.__file__).read_text(encoding="utf-8")
    assert "restart_after_bounce" in ladder_source
    assert "resume_collections" in ladder_source, (
        "ladder.py tells the next reader that `reversal.py` calls "
        "`restart_after_bounce`. That call is CONDITIONAL on `reverse_payment`'s "
        "`resume_collections` argument, and a sentence that does not name the "
        "condition is the CR-059 CS-5 defect wearing a fix."
    )
    assert "restart_after_bounce" in _names_called_or_reached(reversal), (
        "`ladder.py` says the reversal calls `restart_after_bounce`, and no statement "
        "in `reversal.py` reaches that name. That is the sentence being false again."
    )
