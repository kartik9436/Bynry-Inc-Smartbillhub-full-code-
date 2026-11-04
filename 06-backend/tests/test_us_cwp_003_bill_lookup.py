# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-003 (EP-CWP-02) — find the bill on a number and a postcode ·
#           US-CWP-002 — the lockout in front of it. Screens: CWP-002
# Rules:    BR-CWP-018 (a bill number proves someone is HOLDING the bill, not
#           who they are) · BR-CWP-019 (the lookup answers the amount owing and
#           a MASKED name and NOTHING ELSE) · BR-CWP-020 (`M. A••••••`) ·
#           BR-CWP-021 (a guest sees an amount and a status, never a person) ·
#           BR-CWP-023 (five wrong pairs, fifteen minutes) · BR-CWP-025 (a
#           second fact only the sender would know) · BR-CWP-042 (a corrected
#           bill names its replacement) · CLAUDE.md hard rule 2 (four stored,
#           two displayed) · hard rule 8 (the postcode is walked to on premises)
# Tests:    this file — TC-1..TC-7 of US-CWP-003, and US-CWP-002 TC-3/TC-5 on
#           the quick-pay form specifically (the generic lockout cases are in
#           tests/test_us_cwp_002_lockout.py and are not repeated here)
# Impacts:  apps/portal/selectors.bill_lookup · guest_api.bill_lookup ·
#           seams/billing_seam.py · seams/customers_seam.py
# ───────────────────────────────────────────────────────
"""What a stranger holding a piece of paper may be told, and nothing else.

⚠ **THE DISCLOSURE CASE ASSERTS OVER THE WHOLE BODY AND NOT OVER THREE NAMED
KEYS**, which is the difference between a test that would have caught a leak and
one that reads well. `BR-CWP-019` is an ALLOW-LIST — *"the amount owing and a
masked name, and nothing else about the account"* — so the case freezes the key
set and any field a future serialiser gains goes red, including the one nobody
thought of. `guest_fields.py` and `G92` are the same rule enforced statically;
this is it enforced on the body that actually leaves the server.

⚠ **AND THE TWO REFUSALS ARE COMPARED BYTE FOR BYTE.** `TC-2` (a real bill,
wrong postcode) and `TC-3` (no such bill) are the pair `US-CWP-003` calls out in
its own words — *"a different message would confirm the bill number exists"* —
so the assertion is `==` between two whole response bodies rather than two
`status_code` checks that would pass on two different sentences.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.portal import guest_api, lockout, selectors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_024_balance import allocate
from tests.test_us_cwp_helpers import (
    an_issued_bill,
    elm_street_account,
    switch_on,
)
from tests.test_us_ten_helpers import api_call

#: `US-CWP-003` §4, verbatim.
AUGUST = date(2026, 8, 30)
DUE = date(2026, 9, 14)
BILL = "BL-2608-0141"
POSTCODE = "78702"
WRONG_POSTCODE = "78704"
OWING = "142.1800"
DISPLAY = "$142.18"
PAID_BILL = "BL-2607-0139"
CORRECTED = "BL-2606-0137"
REPLACEMENT = "BL-2606-0147"

GUESSER = "198.51.100.10"
SECOND_ADDRESS = "203.0.113.7"


def _refusal(response) -> dict:
    """A refusal body with its per-request `trace_id` taken out.

    ⚠ **THE TRACE ID IS THE ONE FIELD THAT LEGITIMATELY DIFFERS** — it names
    the request, not the answer, and every error envelope in this product
    carries one. Everything else must match byte for byte, which is what
    `US-CWP-003` TC-2 and TC-3 are asking for.
    """
    return {key: value for key, value in dict(response.data).items() if key != "trace_id"}


def _lookup(tenant, number, postcode, address=SECOND_ADDRESS):
    return api_call(
        guest_api.bill_lookup,
        "post",
        f"/api/{tenant.subdomain}/portal/public/bills/lookup",
        tenant=tenant,
        data={"bill_number": number, "postcode": postcode},
        headers={"X-Forwarded-For": address},
    )


def _elm_bill(tenant, actor, *, number=BILL, total=OWING, status=billing_models.INVOICE_ISSUED):
    """One bill on Maria's `1408 Elm St · A`, whose premises postcode is 78702."""
    switch_on(tenant, actor)
    account = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        row = an_issued_bill(
            tenant, account, number=number, total=total, issued_on=AUGUST, due_on=DUE
        )
        if status != billing_models.INVOICE_ISSUED:
            row.status = status
            row.save(update_fields=["status"])
    return account, row


# ══ TC-1 — the pair on the paper opens step 2 ══════════════════════════════


@pytest.mark.django_db
def test_tc1_the_number_and_the_postcode_answer_the_amount_owing(pine_hill, sarah):
    _elm_bill(pine_hill, sarah)
    response = _lookup(pine_hill, BILL, POSTCODE)
    assert response.status_code == 200, response.data
    body = response.data
    assert body["number"] == BILL
    assert body["status"] == selectors.BILL_PAYABLE
    #: Hard rule 2 — FOUR decimals stored travel beside TWO displayed, and the
    #: pair must agree. A test that read only `display` could not tell a
    #: rounding rule from a truncation.
    assert body["amount"]["amount"] == OWING
    assert body["amount"]["display"] == DISPLAY
    assert body["due_on"] == DUE.isoformat()


@pytest.mark.django_db
def test_tc1_the_masked_name_is_first_initial_and_a_fixed_width_surname(pine_hill, sarah):
    """`BR-CWP-020` — `M. A••••••`, computed on the SERVER.

    The fixture's customer is *Maria Alvarez*, so the mask is derived from her
    real display name rather than compared against a string this file typed.
    """
    _elm_bill(pine_hill, sarah)
    body = _lookup(pine_hill, BILL, POSTCODE).data
    assert body["masked_name"] == "M. A" + selectors.NAME_MASK
    assert body["masked_name"].startswith("M. A")
    #: `US-CWP-004` TC-4 — fixed width, never one dot per letter, or the mask
    #: is a length oracle on a public endpoint.
    assert len(selectors.masked_name("M O")) == len(selectors.masked_name("Maria Alvarez"))


@pytest.mark.django_db
def test_br_cwp_019_the_whole_body_is_the_allow_list_and_nothing_more(pine_hill, sarah):
    """⚠ **THE KEY SET IS FROZEN, NOT SAMPLED.**

    `BR-CWP-019` says *"and nothing else about the account — not the other
    bills, not the usage, not the history"*. Asserting that three named fields
    are absent would pass on the fourth one somebody adds next month; asserting
    the whole set is what fails then.
    """
    _elm_bill(pine_hill, sarah)
    body = _lookup(pine_hill, BILL, POSTCODE).data
    assert set(body) == {"number", "amount", "status", "due_on", "masked_name", "replaced_by"}
    #: The money cell is `apps/portal/money.py`'s and carries no fifth member.
    assert set(body["amount"]) == {"kind", "amount", "display", "currency"}
    #: Belt and braces, on the SERIALISED body rather than on the source:
    #: nothing anywhere in it is a person, an account or an address.
    flat = str(body).lower()
    for forbidden in ("alvarez", "maria", "elm st", "78702", "account", "@"):
        assert forbidden not in flat, f"{forbidden!r} reached a guest response"


# ══ TC-2 · TC-3 — two misses, one sentence ═════════════════════════════════


@pytest.mark.django_db
def test_tc2_and_tc3_a_wrong_postcode_and_an_unknown_bill_answer_identically(pine_hill, sarah):
    _elm_bill(pine_hill, sarah)
    wrong_postcode = _lookup(pine_hill, BILL, WRONG_POSTCODE)
    unknown_bill = _lookup(pine_hill, "BL-9999-9999", POSTCODE)
    assert wrong_postcode.status_code == unknown_bill.status_code
    #: ⚠ **BYTE-IDENTICAL, WHOLE BODY.** Two 400s carrying two different
    #: sentences is exactly the leak this pair exists to catch.
    assert _refusal(wrong_postcode) == _refusal(unknown_bill)


@pytest.mark.django_db
def test_a_draft_bill_is_refused_identically_to_one_that_does_not_exist(pine_hill, sarah):
    """Nobody can be HOLDING a draft — it was never sent (`BR-CWP-018`)."""
    _elm_bill(pine_hill, sarah, number="BL-2609-0150", status=billing_models.INVOICE_DRAFT)
    draft = _lookup(pine_hill, "BL-2609-0150", POSTCODE)
    unknown = _lookup(pine_hill, "BL-9999-9999", POSTCODE)
    assert draft.status_code == unknown.status_code
    assert _refusal(draft) == _refusal(unknown)


# ══ TC-4 — a paid bill is an ANSWER, not a refusal ═════════════════════════


@pytest.mark.django_db
def test_tc4_a_paid_bill_opens_at_zero_and_offers_no_payment(pine_hill, sarah):
    """*"Not a refusal, because the holder is entitled to know it is paid."*"""
    account, invoice = _elm_bill(pine_hill, sarah, number=PAID_BILL, total="138.4400")
    with tenant_context(pine_hill.id):
        #: ⚠ **A REAL ALLOCATION, NOT A FLIPPED STATUS COLUMN.** The word this
        #: screen shows is derived from what `payments` says is still open — the
        #: same single source `CWP-027` and `CWP-028` read — so a fixture that
        #: only edited `invoices.status` would prove the assertion and not the
        #: behaviour.
        allocate(pine_hill, account, invoice, "138.4400")
        invoice.status = billing_models.INVOICE_PAID
        invoice.save(update_fields=["status"])
    body = _lookup(pine_hill, PAID_BILL, POSTCODE).data
    assert body["status"] == selectors.BILL_SETTLED
    assert body["amount"]["amount"] == "0.0000"
    assert body["amount"]["display"] == "$0.00"


# ══ TC-5 — a voided bill reads *cancelled* ═════════════════════════════════


@pytest.mark.django_db
def test_tc5_a_voided_bill_reads_cancelled_and_shows_nothing_payable(pine_hill, sarah):
    _elm_bill(pine_hill, sarah, number="BL-2608-0199", status=billing_models.INVOICE_VOID)
    body = _lookup(pine_hill, "BL-2608-0199", POSTCODE).data
    assert body["status"] == selectors.BILL_CANCELLED
    #: ⚠ `$0.00` AND NOT THE FACE VALUE — a figure beside the word *cancelled*
    #: is the one thing on this screen somebody might act on.
    assert body["amount"]["display"] == "$0.00"


# ══ TC-6 — a lookup is per tenant, before any customer row is read ═════════


@pytest.mark.django_db
def test_tc6_pine_hills_bill_number_is_not_found_under_oak_ridge(
    pine_hill, sarah, oak_ridge, elena
):
    _elm_bill(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    mine = _lookup(pine_hill, BILL, POSTCODE)
    theirs = _lookup(oak_ridge, BILL, POSTCODE)
    assert mine.status_code == 200
    assert theirs.status_code != 200
    #: The tenant is in the QUERY (`BR-CWP-010`, `G96`) — the suite is SQLite
    #: and has no RLS, so a read leaning on the database alone would pass here
    #: forever (law 14).
    with tenant_context(oak_ridge.id):
        assert selectors.bill_lookup(oak_ridge.id, bill_number=BILL, postcode=POSTCODE) is None


# ══ TC-7 — a corrected bill names its replacement ══════════════════════════


@pytest.mark.django_db
def test_tc7_a_corrected_bill_reads_replaced_and_names_the_bill_that_replaced_it(
    pine_hill, sarah
):
    account, original = _elm_bill(pine_hill, sarah, number=CORRECTED, total="154.9000")
    with tenant_context(pine_hill.id):
        replacement = an_issued_bill(
            pine_hill, account, number=REPLACEMENT, total="129.0200",
            issued_on=AUGUST, due_on=DUE,
        )
        replacement.corrects_invoice = original
        replacement.save(update_fields=["corrects_invoice"])
        original.status = billing_models.INVOICE_CORRECTED
        original.save(update_fields=["status"])
    body = _lookup(pine_hill, CORRECTED, POSTCODE).data
    assert body["status"] == selectors.BILL_REPLACED
    assert body["replaced_by"] == REPLACEMENT
    #: Payment is directed at the replacement, so nothing is payable here.
    assert body["amount"]["display"] == "$0.00"


# ══ US-CWP-002 — the lockout, on THIS form ═════════════════════════════════


@pytest.mark.django_db
def test_us_cwp_002_tc3_six_wrong_pairs_lock_quick_pay_and_a_right_one_is_refused(
    pine_hill, sarah
):
    _elm_bill(pine_hill, sarah)
    for guess in range(2, 7):  # BL-2608-0142 … 0146 — US-CWP-002 §4
        _lookup(pine_hill, f"BL-2608-014{guess}", POSTCODE, address=GUESSER)
    assert lockout.is_locked(str(pine_hill.id), lockout.FORM_QUICK_PAY, GUESSER)
    #: ⚠ **A CORRECT PAIR INSIDE THE WINDOW IS STILL REFUSED** — that is what
    #: makes it a lockout rather than a delay.
    correct = _lookup(pine_hill, BILL, POSTCODE, address=GUESSER)
    assert correct.status_code != 200
    #: TC-4 — and a second address is untouched.
    assert _lookup(pine_hill, BILL, POSTCODE, address=SECOND_ADDRESS).status_code == 200


@pytest.mark.django_db
def test_us_cwp_002_tc5_locking_quick_pay_does_not_lock_track(pine_hill, sarah):
    """Two doors, two locks. A person guessing bill numbers is not a person
    guessing references (`lockout.py`'s own words)."""
    _elm_bill(pine_hill, sarah)
    for guess in range(2, 7):
        _lookup(pine_hill, f"BL-2608-014{guess}", POSTCODE, address=GUESSER)
    assert lockout.is_locked(str(pine_hill.id), lockout.FORM_QUICK_PAY, GUESSER)
    assert not lockout.is_locked(str(pine_hill.id), lockout.FORM_TRACK, GUESSER)


@pytest.mark.django_db
def test_a_utility_that_switched_quick_pay_off_refuses_the_endpoint(pine_hill, sarah):
    """`BR-CWP-002` — the refusal is at the EDGE, not at the screen."""
    _elm_bill(pine_hill, sarah)
    switch_on(pine_hill, sarah, quick_pay_enabled=False)
    assert _lookup(pine_hill, BILL, POSTCODE).status_code != 200


@pytest.mark.django_db
def test_the_owing_figure_is_payments_own_and_not_a_subtraction_here(pine_hill, sarah):
    """`US-CWP-003` §7 — *"a read of existing arithmetic"*.

    A part-paid bill is the case that separates the two: `142.18` charged with
    `40.00` allocated owes `102.18`, and a lookup that served `total` would
    read `$142.18` and be wrong by the amount somebody has already paid.
    """
    from apps.portal.seams import payments_seam

    account, invoice = _elm_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        allocate(pine_hill, account, invoice, "40.0000")
        expected = None
        for row in payments_seam.account_balance(account.pk).get("bills") or ():
            if row.get("number") == BILL:
                expected = Decimal(row["open_balance"])
    assert expected == Decimal("102.1800"), expected
    body = _lookup(pine_hill, BILL, POSTCODE).data
    assert Decimal(body["amount"]["amount"]) == expected


@pytest.mark.django_db
def test_the_lookup_writes_nothing_at_all(pine_hill, sarah):
    """`BR-CWP-026` — a public form may create work and may never change an
    account; this one does not even create work."""
    account, invoice = _elm_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        before = billing_models.Invoice.objects.get(pk=invoice.pk)
        snapshot = (before.status, before.total, before.due_date)
    _lookup(pine_hill, BILL, POSTCODE)
    _lookup(pine_hill, BILL, WRONG_POSTCODE)
    with tenant_context(pine_hill.id):
        after = billing_models.Invoice.objects.get(pk=invoice.pk)
        assert (after.status, after.total, after.due_date) == snapshot


# ══ DEF-CWP-10711 (audit L1-07) — the number as a person types it ══════════


@pytest.mark.django_db
def test_def_cwp_10711_a_lower_case_number_with_spaces_finds_the_bill(pine_hill, sarah):
    """Worked case from the audit: `" bl-2610-000079 "` with ZIP 78611 read
    *"We cannot find that bill."* for a real bill. Same shape on this fixture:
    `" bl-2608-0141 "` with 78702 must answer what `BL-2608-0141` answers."""
    _elm_bill(pine_hill, sarah)
    typed = _lookup(pine_hill, f"  {BILL.lower()} ", POSTCODE)
    exact = _lookup(pine_hill, BILL, POSTCODE)
    assert typed.status_code == 200, typed.data
    assert typed.data == exact.data
    assert typed.data["number"] == BILL


@pytest.mark.django_db
def test_def_cwp_10711_a_miss_in_lower_case_is_still_the_one_refusal(pine_hill, sarah):
    """Normalising the number must not open a second sentence: a lower-case
    real number with the WRONG postcode and a lower-case unknown number answer
    byte for byte the same (`BR-CWP-025`)."""
    _elm_bill(pine_hill, sarah)
    wrong_postcode = _lookup(pine_hill, BILL.lower(), WRONG_POSTCODE)
    unknown = _lookup(pine_hill, "bl-2608-9999", POSTCODE)
    assert wrong_postcode.status_code == unknown.status_code
    assert _refusal(wrong_postcode) == _refusal(unknown)
