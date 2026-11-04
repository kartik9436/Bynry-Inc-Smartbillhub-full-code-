# ── Trace ──────────────────────────────────────────────
# Change:   CR-138-BRC07 · P4.4 (`GET /refunds/{id}`) · P4.25 (one read for
#           refunds AND credits). Blueprint p21 and p23, screen 6·1.
# Rules:    B1 / B2 §2 (payments may not query `credit_notes`) · BR-BIL-074
#           (a credit note's amount is NEGATIVE by CHECK constraint) ·
#           BR-PAY-037 (both approval acts recorded distinctly) · B14 rule 31 ·
#           NFR-3 · NFR-5 · CLAUDE.md hard rule 1 · hard rule 2
# ───────────────────────────────────────────────────────
"""*"Where is my money?"* gets an answer, and the two ways of giving it back
appear in one list **without either lifecycle being flattened.**

═══════════════════════════════════════════════════════════════════════════════
RED PROOF (hard-won law 7) — OBSERVED, NOT PREDICTED
═══════════════════════════════════════════════════════════════════════════════
Run in this lane's own detached worktree at the pinned tip, with each piece
removed in turn and the tree restored afterwards. Verbatim:

  * **`GET /refunds/{id}` did not exist.** With the route removed from
    `refunds_api.urlpatterns`, the address case fails
    `django.urls.exceptions.Resolver404: {'tried': …, 'path':
    'api/brazos/refunds/R-1'}` — which is the state of the branch before this
    commit, and the whole of `P4.4`.
  * **`GET /refunds-and-credits` did not exist**, same failure at
    `'api/brazos/refunds-and-credits'`.
  * **the seam.** With `apps.billing.selectors.credit_note_page` renamed, the
    union case fails `AssertionError: the credit note is missing from the list`
    AND the envelope carries `credit_notes_read_unavailable` — which is the
    behaviour being asserted, so the two are tested apart.
  * **the lifecycle.** With a `"status": "issued"` member added to
    `_row_for_credit_note`, `test_a_credit_note_row_has_no_status_key_at_all`
    fails `AssertionError: a credit note was given a synthesised status
    'issued'` — the assertion `P4.26` exists to keep true.

═══════════════════════════════════════════════════════════════════════════════
WHAT WOULD MAKE THESE CHECKS PASS WRONGLY (law 7, habit 2)
═══════════════════════════════════════════════════════════════════════════════
* **A union list that simply never looked at billing would pass a test that
  only counted refunds.** So the union case asserts the credit note is PRESENT
  by its `credit_note_no`, and asserts the count is the SUM — a list that
  quietly served refunds only would fail on both.
* **An `amount_returned` built with `float()` would pass an equality on
  `57.13`.** So the magnitude case uses a figure a float cannot hold exactly
  and compares the STRING, which is what `NUMERIC(18,6)` produces.
* **A `status` member that is `None` rather than absent reads the same in a
  truthiness test.** So the lifecycle case asserts on `in` — key presence —
  never on the value.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from django.urls import resolve

from apps.billing.models import CreditNote
from apps.payments import models, refunds_and_credits, refunds_api

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_011_refunds import (  # noqa: F401
    an_overpaid_account,
)
from tests.test_us_pay_001_record_payment import PE4_CREDIT

pytestmark = pytest.mark.django_db

from tests.test_us_ten_helpers import api_call  # noqa: E402 — after the star import

#: PE-9's cheque number, the only human token a refund carries. See
#: `refunds_and_credits`'s docstring: refunds have no number series of their own
#: and one was NOT invented here.
CHEQUE = "100482"
REQUESTED_AT = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)

#: ❄️ GT-6's own figure — a **25.00** goodwill credit — stored NEGATIVE by
#: `BR-BIL-074`'s CHECK constraint. The union list must show it as money GIVEN
#: BACK, positive, without touching the signed figure on the source row.
GOODWILL = Decimal("25.000000")


def _get(view, tenant, *, actor, role="billing_clerk", **kw):
    return api_call(view, "get", user=actor.user, role=role, tenant=tenant, **kw)


def _post(view, tenant, *, actor, role="system_admin", data=None, **kw):
    return api_call(view, "post", user=actor.user, role=role, tenant=tenant, data=data or {}, **kw)


def _raised(brazos, marcus, *, role="billing_clerk"):
    """An account carrying PE-4's 57.13 credit, with a refund raised on it."""
    with tenant_ctx(brazos):
        account, recorded = an_overpaid_account(brazos, marcus)
    answered = _post(
        refunds_api.account_refunds,
        brazos,
        actor=marcus,
        role=role,
        data={
            "payment_id": str(recorded.payment_id),
            "amount": str(PE4_CREDIT),
            "method": models.REFUND_METHOD_CHECK,
            # ⚠ **NO `reference` — DEF-PAY-6331, 2026-09-23.** The raise door
            # refuses one by name now: a refund is requested before Finance
            # approves it and before a cheque exists. `_issued` below is what
            # gives a refund its number.
            "reason": "Overpayment",
            "requested_at": REQUESTED_AT.isoformat(),
            "idempotency_key": str(uuid.uuid4()),
        },
        account_id=str(account.pk),
    )
    return account, answered


def _a_credit_note(brazos, account, *, number="CM-0001"):
    """ONE credit note on this account, written the way `corrections` writes it.

    The amount is NEGATIVE — `BR-BIL-074`'s constraint, and the whole reason
    `amount_returned` is a magnitude. `issued_at` is set in the same `create`,
    which is the fact behind *"a credit note has no state column at all"*.
    """
    with tenant_ctx(brazos):
        return CreditNote.objects.create(
            tenant_id=brazos.id,
            account_id=account.pk,
            original_invoice=None,
            credit_note_no=number,
            amount=-GOODWILL,
            currency="USD",
            reason="Goodwill",
            issued_at=REQUESTED_AT,
        )


# ══════════════════════════════════════════════════════════════════════════
# P4.4 · THE DETAIL VIEW THAT DID NOT EXIST
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "path,view_name",
    [
        ("/api/brazos/refunds/R-1", "refund_item"),
        ("/api/brazos/refunds-and-credits", "refunds_and_credits_list"),
    ],
)
def test_the_two_new_refund_reads_are_mounted(path, view_name):
    """Both addresses resolve, and neither eats one of the four act routes.

    `refunds/<id>` is TWO segments and every act is three, so `approve`,
    `issue`, `clear` and `void` cannot be read as a refund id — the
    `deposits/import` shape this module's siblings record.

    ⚠ **IDENTITY, NOT `__name__`.** A `@api_view`-decorated function is wrapped,
    so `resolve(...).func.__name__` is the string `"view"` for EVERY route in
    this product — an assertion that would have passed on any address at all
    and failed on the right one. Found by running it (law 7, habit 2: ask what
    would make a check pass wrongly; this one could only ever fail).
    """
    assert resolve(path).func is getattr(refunds_api, view_name)


def test_the_detail_route_does_not_shadow_the_four_acts():
    """The act routes still resolve to themselves, asserted rather than assumed."""
    for verb in ("approve", "issue", "clear", "void"):
        match = resolve(f"/api/brazos/refunds/R-1/{verb}")
        assert match.func is getattr(refunds_api, f"refund_{verb}"), verb


def test_a_refund_can_be_opened_and_read_without_acting_on_it(brazos, marcus):
    """P4.4's whole point: LOOK at a refund without changing it.

    Before this route the only way to see a refund's row was to approve, issue,
    clear or void it — every one of which is an act on money.
    """
    account, raised = _raised(brazos, marcus)
    refund_id = raised.data["id"]

    opened = _get(refunds_api.refund_item, brazos, actor=marcus, refund_id=str(refund_id))

    assert opened.status_code == 200
    assert opened.data["id"] == str(refund_id)
    assert opened.data["account_id"] == str(account.pk)
    assert opened.data["amount"] == str(PE4_CREDIT.quantize(Decimal("0.000001")))
    assert opened.data["currency"] == "USD"
    # DEF-PAY-6331 — a REQUESTED refund names no cheque, because none is
    # written. The detail route serves the absence rather than a guess.
    assert opened.data["reference"] is None
    # BR-PAY-037 — both acts stay separate facts, neither folded into a boolean.
    assert "requested_by" in opened.data and "approved_by" in opened.data
    assert opened.data["status"] == models.REFUND_REQUESTED

    # And nothing moved: the row is exactly as it was.
    with tenant_ctx(brazos):
        row = models.Refund.objects.get(pk=refund_id)
    assert row.status == models.REFUND_REQUESTED
    assert row.approved_at is None and row.issued_at is None


def test_another_tenants_refund_reads_as_absent_and_never_as_forbidden(
    brazos, lonestar, marcus, erin
):
    """404-never-403 — hard rule 1 / HR-1.

    A 403 confirms the row exists, which is the one thing a stranger must not
    learn from a refusal.
    """
    _account, raised = _raised(brazos, marcus)
    refund_id = str(raised.data["id"])

    # DRF turns a catalog exception into a RESPONSE rather than letting it out
    # of the view, so the assertion is on the STATUS. `pytest.raises` here would
    # be a check that can only fail — the mirror of the `__name__` one above.
    answered = _get(
        refunds_api.refund_item,
        lonestar,
        actor=erin,
        role="system_admin",
        refund_id=refund_id,
    )
    assert answered.status_code == 404, answered.data


# ══════════════════════════════════════════════════════════════════════════
# P4.25 · ONE LIST, TWO MODULES, TWO LIFECYCLES
# ══════════════════════════════════════════════════════════════════════════


def test_the_list_unions_payments_refunds_with_billings_credit_notes(brazos, marcus):
    """One list, both sources, and the count is the SUM of the two.

    A list that quietly served refunds only would pass any assertion that
    merely counted rows — so the credit note is asserted PRESENT by its own
    number, and the total by arithmetic.
    """
    account, raised = _raised(brazos, marcus)
    note = _a_credit_note(brazos, account)

    listed = _get(refunds_and_credits_view(), brazos, actor=marcus)

    assert listed.status_code == 200
    assert listed.data["count"] == 2, listed.data
    kinds = {row["kind"] for row in listed.data["rows"]}
    assert kinds == {"refund", "credit_note"}, "the credit note is missing from the list"
    numbers = {row["number"] for row in listed.data["rows"]}
    assert note.credit_note_no in numbers
    # ⚠ **THE REFUND IS STILL `requested`, SO IT HAS NO NUMBER YET
    # (DEF-PAY-6331)** — and `_refund_number` already had a branch for exactly
    # this, which is now the ordinary state of every cheque refund between
    # raise and issue rather than an edge case. The list says WHY rather than
    # printing a blank.
    assert CHEQUE not in numbers
    refund_row = next(row for row in listed.data["rows"] if row["kind"] == "refund")
    assert refund_row["number"] is None
    assert refund_row["number_absence"] == refunds_and_credits.NUMBER_ABSENT_NO_SERIES
    assert str(raised.data["id"]) in {row["id"] for row in listed.data["rows"]}
    assert listed.data["problems"] == []


def refunds_and_credits_view():
    return refunds_api.refunds_and_credits_list


def test_a_credit_note_row_has_no_status_key_at_all(brazos, marcus):
    """**P4.26's requirement, asserted at the read.**

    *"The columns must not flatten the two lifecycles: a refund is raised,
    approved, issued, cleared; a credit note has no state column at all."*

    The assertion is on KEY PRESENCE and never on a value, because `None` and
    absent read the same in a truthiness test and only one of them is honest.
    """
    account, _raised_response = _raised(brazos, marcus)
    _a_credit_note(brazos, account)

    listed = _get(refunds_and_credits_view(), brazos, actor=marcus)
    by_kind = {row["kind"]: row for row in listed.data["rows"]}

    assert "status" in by_kind["refund"], "a refund HAS a lifecycle and must carry it"
    assert "status" not in by_kind["credit_note"], (
        f"a credit note was given a synthesised status "
        f"{by_kind['credit_note'].get('status')!r}. It has no state column at all — "
        "every value this key could hold is false (P4.26)."
    )

    # And the envelope SAYS so, so a screen draws a stated absence (B14 rule 32)
    # rather than an empty cell.
    assert listed.data["lifecycles"]["refund"]["has_state"] is True
    assert listed.data["lifecycles"]["credit_note"]["has_state"] is False
    assert listed.data["lifecycles"]["credit_note"]["states"] == []


def test_the_credit_notes_signed_amount_is_untouched_and_the_column_is_a_magnitude(brazos, marcus):
    """`BR-BIL-074` stores a credit NEGATIVE; the shared column shows money BACK.

    `DEF-085` is what happens when one column carries two conventions: a signed
    Σ read **$272.30 on a run where the customer owed $222.30**. So the source
    row keeps its sign and the shared column is the magnitude — compared as a
    STRING, because a float comparison would pass over the very defect hard
    rule 2 exists to prevent.
    """
    account, _ = _raised(brazos, marcus)
    _a_credit_note(brazos, account)

    listed = _get(refunds_and_credits_view(), brazos, actor=marcus)
    note_row = next(row for row in listed.data["rows"] if row["kind"] == "credit_note")

    assert note_row["amount_returned"] == "25.000000"
    assert note_row["source"]["amount"] == "-25.000000", "the signed figure must not be rewritten"
    assert isinstance(note_row["amount_returned"], str)


def test_an_unknown_kind_is_refused_rather_than_answered_with_an_empty_list(brazos, marcus):
    """An empty list and an unanswerable one look identical on a screen.

    `refund_queue`'s own recorded trap, and `write_off_queue`'s before it.
    """
    _raised(brazos, marcus)
    answered = _get(refunds_and_credits_view(), brazos, actor=marcus, query={"f.kind": "voucher"})
    # 422 VAL-005 `VAL_UNKNOWN_LOOKUP`, with the closed set in the params.
    assert answered.status_code == 422, answered.data
    assert "credit_note" in str(answered.data), answered.data


def test_the_unknown_kind_refusal_reaches_a_clerk_as_WORDS(brazos, marcus):
    """`G32`'s defect at the raise site: a refusal with no catalogue sentence.

    Since the PO's ruling of 2026-08-19 the server's `detail` never reaches a
    screen, so a `message_key` no catalogue defines arrives as **silence** — the
    click does nothing and no sentence appears. `core.refusal_catalogue` asserts
    this at the raise site, which is where `G32` could not see it; this case
    pins the key so a later rename cannot quietly remove the sentence.
    """
    from core import refusal_catalogue

    refusal_catalogue.assert_resolves(
        "payments.refundsAndCredits.kind_unknown", raised_by="ValidationError"
    )


def test_the_kind_filter_narrows_to_one_source(brazos, marcus):
    """`?f.kind=` serves one source, and the count follows the filter."""
    account, _ = _raised(brazos, marcus)
    _a_credit_note(brazos, account)

    only_credits = _get(
        refunds_and_credits_view(), brazos, actor=marcus, query={"f.kind": "credit_note"}
    )
    assert only_credits.data["count"] == 1
    assert {row["kind"] for row in only_credits.data["rows"]} == {"credit_note"}

    only_refunds = _get(
        refunds_and_credits_view(), brazos, actor=marcus, query={"f.kind": "refund"}
    )
    assert only_refunds.data["count"] == 1
    assert {row["kind"] for row in only_refunds.data["rows"]} == {"refund"}


def test_the_list_is_paged_and_no_row_is_beyond_the_last_page(brazos, marcus):
    """`NFR-3` and `NFR-5` together: a window, and every row reachable behind it.

    Two rows, one per page. The union must not lose the second to the merge —
    which is the failure a federated page makes when the two sides are sliced
    independently instead of merged and then windowed.
    """
    account, _ = _raised(brazos, marcus)
    _a_credit_note(brazos, account)

    # ⚠ THE WINDOW IS ASSERTED AT THE SERVICE, NOT THROUGH THE ROUTE, AND THAT
    # IS NOT A SHORTCUT. `core.pagination.clamp_page_size` clamps `per` to the
    # platform's own set — **50, 100, 200, 500, 1000** — so `?per=1` is served
    # as 50 and a two-row fixture cannot exercise a page boundary through HTTP
    # at all. `page()` takes the raw window, which is where the merge lives.
    with tenant_ctx(brazos):
        first = refunds_and_credits.page(offset=0, limit=1)
        second = refunds_and_credits.page(offset=1, limit=1)

    assert first["count"] == 2 and second["count"] == 2
    assert len(first["rows"]) == 1 and len(second["rows"]) == 1
    seen = {first["rows"][0]["id"], second["rows"][0]["id"]}
    assert len(seen) == 2, "the same row was served on both pages — the merge is unstable"
    assert {first["rows"][0]["kind"], second["rows"][0]["kind"]} == {
        "refund",
        "credit_note",
    }


def test_the_route_clamps_per_to_the_platform_page_sizes(brazos, marcus):
    """`?per=1` is served as 50 — `BR-SHL-011`'s "never error", not a bug.

    Asserted because the case above sidesteps the route, and a reader would
    otherwise reasonably wonder whether the route pages at all.
    """
    account, _ = _raised(brazos, marcus)
    _a_credit_note(brazos, account)
    answered = _get(
        refunds_and_credits_view(), brazos, actor=marcus, query={"per": "1", "page": "1"}
    )
    assert answered.data["limit"] == 50
    assert answered.data["page"] == 1
    assert len(answered.data["rows"]) == 2


def test_the_page_is_taken_in_sql_on_both_sides(brazos, marcus):
    """The seam is asked for a WINDOW, never for everything.

    Asserted at the seam rather than by counting queries: `credit_notes_page`
    is called with the caller's `offset + limit` and nothing larger, which is
    the property `NFR-3` is about. A regression that fetched the table and
    sliced in Python would pass every other case in this file.
    """
    account, _ = _raised(brazos, marcus)
    _a_credit_note(brazos, account)

    seen: list[dict] = []
    real = refunds_and_credits.billing_seam.credit_notes_page

    def spy(*, offset, limit):
        seen.append({"offset": offset, "limit": limit})
        return real(offset=offset, limit=limit)

    refunds_and_credits.billing_seam.credit_notes_page = spy
    try:
        _get(refunds_and_credits_view(), brazos, actor=marcus, query={"per": "50", "page": "2"})
    finally:
        refunds_and_credits.billing_seam.credit_notes_page = real

    assert seen, "the seam was never called — the list is not reading billing at all"
    # Page 2 at 50 a page = the first 100 rows, merged, then windowed. Bounded
    # by the PAGE and never by the table, which is the `NFR-3` property.
    assert seen[0]["limit"] == 100, seen
    assert seen[0]["offset"] == 0, seen


def test_a_missing_credit_note_read_shortens_the_list_OUT_LOUD(brazos, marcus):
    """`G32`'s defect, refused: a true zero over a scope it silently excluded.

    With billing publishing no credit-note read, the refunds half still serves
    — and the envelope SAYS the other half is missing, with a code, rather than
    answering a short list that looks complete.
    """
    account, _ = _raised(brazos, marcus)
    _a_credit_note(brazos, account)

    from apps.billing import selectors as billing_selectors

    kept = billing_selectors.credit_note_page
    kept_count = billing_selectors.credit_note_count
    del billing_selectors.credit_note_page
    del billing_selectors.credit_note_count
    try:
        listed = _get(refunds_and_credits_view(), brazos, actor=marcus)
    finally:
        billing_selectors.credit_note_page = kept
        billing_selectors.credit_note_count = kept_count

    codes = {problem["code"] for problem in listed.data["problems"]}
    assert "credit_notes_read_unavailable" in codes, listed.data["problems"]
    assert listed.data["count"] == 1, "the count must not silently include what it could not read"
    assert {row["kind"] for row in listed.data["rows"]} == {"refund"}


def test_a_refund_with_no_cheque_number_says_WHICH_absence_it_is(brazos, marcus):
    """`DEF-127`'s shape: a dash reads as *this record has no reference*.

    Refunds have no number COLUMN (see `refunds_and_credits`'s docstring), so
    an ACH refund has no number at all and the row must say which of the two
    reasons applies rather than serving a uuid (B14 rule 31) or an empty cell.

    ⚠ **`OQ-PAY-12605` WAS RAISED BY THIS WORK AND CLOSED THE SAME DAY** — PO,
    *"(a) Its own series, RFD-26-0001"*. The catalogue row and the `refund_no`
    column are OWED; when they land, `_refund_number` serves the number first
    and this case's ACH refund keeps its stated absence only while the column
    is genuinely null.
    """
    account, raised = _raised(brazos, marcus)
    with tenant_ctx(brazos):
        row = models.Refund.objects.get(pk=raised.data["id"])
        row.method = models.REFUND_METHOD_ACH
        row.reference = None
        row.save(update_fields=["method", "reference"])

    listed = _get(refunds_and_credits_view(), brazos, actor=marcus, query={"f.kind": "refund"})
    refund_row = listed.data["rows"][0]

    assert refund_row["number"] is None
    assert refund_row["number_absence"] == refunds_and_credits.NUMBER_ABSENT_NOT_A_CHEQUE
    # B14 rule 31 — the id is never offered as the visible value.
    assert refund_row["number"] != refund_row["id"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-138-BRC07 §3 P4.4 + P4.25 · 05-prototype/06 Payments Page
#         Blueprint.pdf p21/p23 + screen 6·1 · apps/payments/refunds_api.py ·
#         apps/payments/refunds_and_credits.py · apps/payments/billing_seam.py ·
#         apps/billing/selectors.py
# generated: 2026-09-23 by the CR-138 lane P4-READS
# gates: RED PROVED FIRST — the four mutations are quoted verbatim in this
#        file's own docstring, each observed rather than predicted.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
