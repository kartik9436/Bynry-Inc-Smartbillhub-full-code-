# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-7990 — One-time bill step 2 called a named customer
#          nameless, and the sentence it printed was about the wrong thing.
# Rules:   BR-CUS-054 (the customer entity; an account may have no link and
#          therefore no name) · B14 rule 31 (no database id on screen) ·
#          B1 (billing reads customers through a seam, never a model)
# Screens: S30 One-time bill, step 2 · S82 the three-step redraw, step 2
# ───────────────────────────────────────────────────────
"""The preview names WHO, not only WHICH ACCOUNT — and the two nulls differ.

**The defect was not a missing field; it was two nulls wearing one sentence.**
Step 1 of the One-time bill builds its label from the account picker, which
carries `{account_no, name}`, so a clerk reads *"AC-2026-00058 — Rostan
Chase"*. Step 2 rendered `one_time.preview`'s payload, which carried
`account_no` and nothing else, and its only fallback for a null was
`billing.oneTime.accountUnnamed` — *"Account with no name on file"*.

`preview` sets `account_no` to `None` **whenever the prepare pass resolved no
READY account** (`prepared.ready[0].account_no if prepared.ready else None`).
That is a statement about BILLABILITY. The sentence it triggered is a statement
about the CUSTOMER RECORD. So on the one screen where a clerk most needs to
know why a bill will not price, they were told a false fact about the customer
instead of the true one about the account.

⚠ **THE NEGATIVE HALF IS THE DELIVERABLE HERE TOO.** `None` stays a lawful
answer: `BR-CUS-054` lets an account exist with no `customer_accounts` link,
and such an account genuinely has no name. What must never happen again is the
two nulls being rendered as one sentence — so this file asserts that a named
account is NAMED, that the name travels for a kind that carries no window of
its own, and that an unlinked account still answers `None` rather than
inventing a placeholder.
"""

import pytest

from apps.billing import customers_seam, one_time
from tests.test_us_bil_001_prepare import (  # noqa: F401 — shared fixtures
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_bil_012_one_time import INTERIM_END, INTERIM_START
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _an_account(brazos, dana, *, account_no="A-97990", asset_no="M-9799", label="N"):
    cycle = a_cycle(brazos)
    plan = a_priced_plan(brazos)
    unit = a_billed_unit(dana, brazos, cycle, plan, asset_no=asset_no, label=label)
    return an_account(brazos, unit["id"], account_no)


def test_def_bil_7990__the_preview_carries_the_customer_name_beside_the_number(brazos, dana):
    """The field exists on the payload for the ordinary interim preview.

    Asserted as a KEY ON THE BODY rather than as a particular string, because
    what the screen needed was a place for the answer to travel. Whether this
    fixture's account has a linked customer is the fixture's business; whether
    the payload has somewhere to put the answer is this module's.
    """
    with tenant_ctx(brazos):
        account = _an_account(brazos, dana)
        body = one_time.preview(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_INTERIM,
                period_start=INTERIM_START,
                period_end=INTERIM_END,
            )
        )
        assert "name" in body, (
            "step 2 reads this payload for WHO the bill is for. Without the key it "
            "falls back to a sentence about a missing name, which is a different "
            "fact from the one `account_no: None` states."
        )
        expected = customers_seam.primary_contact_names_for([str(account.id)])
        assert body["name"] == (None if expected is None else expected.get(str(account.id))), (
            "the payload must carry what the OWNING module answers and never a "
            "second opinion — billing does not decide who a customer is (B1)."
        )


def test_def_bil_7990__the_name_is_on_the_body_for_every_kind_not_one_branch(brazos):
    """It is set where all six kinds share it, not inside one kind's branch.

    ⚠ **THIS IS THE ASSERTION THAT STOPS THE DEFECT COMING BACK IN A NEW
    PLACE.** `preview` has five `return`s — a fee, the two sub-period kinds, a
    final and a first — and each builds its own sub-body. A `name` added to any
    one of them would fix the screenshot the defect was filed from and leave
    the other five saying nothing. Reading the SOURCE is the only way to assert
    *"exactly once, before the branching"*; a behavioural test would need a
    priceable fixture per kind and would still pass if a sixth branch were
    added tomorrow without one.
    """
    import inspect

    source = inspect.getsource(one_time.preview)
    head, _, tail = source.partition("if kind in CHARGE_CODE_KINDS:")
    assert tail, "the fee branch is the first `return`; this test reads the body before it"
    assert '"name": _customer_name(request.account_id)' in head, (
        "`name` must be set on the shared body ABOVE the first kind branch, or "
        "five of the six kinds serve a payload with no customer in it."
    )
    assert '"name":' not in tail, (
        "a second `name` inside a kind branch is a second opinion about who the "
        "customer is — the shape `DEF-BIL-5326` and `DEF-BIL-5317` were both."
    )


def test_def_bil_7990__an_unpublished_seam_answers_none_and_never_a_placeholder(monkeypatch):
    """`None` travels; nothing is substituted for it.

    A substituted `""` or `"Unknown"` would be this defect's mirror — a screen
    that says it knows the customer has no name when the truth is that nobody
    could ask. The screen is what decides how to say that, and it can only
    decide if the two reach it as different values.
    """
    monkeypatch.setattr(
        customers_seam, "primary_contact_names_for", lambda ids: None, raising=True
    )
    assert one_time._customer_name("01a0e800-11a5-73a9-9009-8f27a8c4996d") is None

    monkeypatch.setattr(customers_seam, "primary_contact_names_for", lambda ids: {}, raising=True)
    assert one_time._customer_name("01a0e800-11a5-73a9-9009-8f27a8c4996d") is None


def test_def_bil_7990__it_asks_for_one_id_through_the_batched_read(monkeypatch):
    """ONE id, ONE query, through the seam the module already owns.

    The singular `customers.primary_contact_name` takes an account ROW, which
    this function does not have and would have to fetch — a second read of the
    account inside a payload that has already resolved it. `P2.12` moved four
    callers onto the batched read for that reason and this is the fifth.
    """
    seen: list[list[str]] = []

    def spy(ids):
        seen.append([str(one) for one in ids])
        return {str(one): "Rostan Chase" for one in ids}

    monkeypatch.setattr(customers_seam, "primary_contact_names_for", spy, raising=True)
    assert one_time._customer_name("acc-58") == "Rostan Chase"
    assert seen == [["acc-58"]], "one call, one id — never a per-row read"


# ── Lifecycle ─────────────────────────────────────────────
# generated: 2026-09-29 by the wave-E One-time bill lane (DEF-BIL-7990)
# gates: every assertion RED-proved first. Verbatim from the runs —
#   · `carries the customer name` failed with
#     `AssertionError: step 2 reads this payload for WHO the bill is for…`
#     assert 'name' in {...}` with the key removed from `preview`'s body.
#   · `on the body for every kind` failed with
#     `AssertionError: `name` must be set on the shared body ABOVE the first
#      kind branch…` when the line was moved below `if kind in CHARGE_CODE_KINDS`.
#   · `answers none and never a placeholder` failed with
#     `AssertionError: assert '' is None` when `_customer_name` returned `""`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
