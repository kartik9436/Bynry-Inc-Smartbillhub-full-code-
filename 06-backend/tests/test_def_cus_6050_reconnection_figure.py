# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-6050 — after a cut the reconnection figure double-counts the
#           $75.00 fee. Reproduced in a browser on `A-11340` / `DSC-26-0001`
#           (2026-09-21): the record read `Owed $8,315.00` and `To clear first
#           $8,390.00` on the same screen, with nothing paid in between.
# Rules:    BR-CUS-104 (PO 2026-08-25, OQ-381 — *"does reconnection need
#           $8,315.00 - this is correct"*) · PO ruling 2026-08-27 / DEF-708 (the
#           fee is a REAL charge, issued at the cut) · BR-BIL-007 (a fee is the
#           tenant's charge code, never a literal) · CLAUDE.md rule 2 (money 4dp
#           stored, 2dp displayed as a string) · rule 4 (this is a READ and
#           writes nothing) · hard-won law 7 (proved RED first, through the
#           harness that runs it)
# ───────────────────────────────────────────────────────
"""**$8,315.00 ON BOTH SIDES OF THE CUT — the figure means two things and says one.**

`BR-CUS-104` is signed over `A-11340`: **$8,240.00 arrears + $75.00 fee =
$8,315.00 to clear**. Before the cut the fee is a QUOTE and the ledger position
does not contain it, so the arithmetic is an addition. The instant `commit_cut`
issues the fee bill the fee is a RECEIVABLE, the position already contains it,
and the same addition quotes it twice.

⚠ **WHY NO TEST SAW THIS FOR THREE WEEKS, AND IT IS THE REASON THIS FILE
EXISTS.** Until 2026-09-20 no cut in this product had ever committed — the
completion code looked for a charge code no tenant had — so the only state the
figure was ever read in is the one where it is right. **Every existing test
quotes it pre-cut.** So the cases below are deliberately paired: the same signed
figure, asked on each side of the commit, because one of them passed while the
product was wrong by a whole fee on every cut customer.

⚠ **AND THE POST-CUT BALANCE IS NOT SIMPLY ASSERTED INTO EXISTENCE.** The W7
fixtures stand the AR boundary up with `_owes`, which answers ONE constant for
any account and therefore cannot show a fee arriving. So `_position_after_the_cut`
below goes to the LEDGER for what the cut actually posted and adds it to the
arrears the ladder walked — the position a real AR read would return — and only
then hands that to the seam. The $75.00 in these figures comes from a journal
line, not from a literal in this file.

**RED PROVED FIRST (hard-won law 7), through `pytest`, which is the harness that
runs these.** The two modules were restored from `HEAD` and the file run against
them: **5 failed, 23 passed** (the 23 are W7's own cases, imported with the
fixtures and untouched by any of this). Quoted verbatim:

    TC1  KeyError: 'basis'
    TC2  AssertionError: assert '8390.0000' == '8315.0000'
    TC3  AssertionError: the quote and the gate differ by 75.000000
         assert Decimal('8390.0000') == Decimal('8315.000000')
    TC4  AssertionError: assert '8390.00' == '8315.00'
    TC5  assert 'DEF-CUS-6050' in 'BR-CUS-104 (PO 2026-08-25) · `OQ-CUS-12518`'
"""

from decimal import Decimal as D

import pytest
from django.utils import timezone

from apps.customers import disconnect_record, disconnects

from tests.test_w7_cut_reconnect import *  # noqa: F401,F403 — W7's own fixtures
from tests.test_w7_cut_reconnect import (  # noqa: F401
    CUT_ON,
    RECONNECT_FEE,
    TODAY,
    _account_row,
    _owes,
    _scheduled,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: BR-CUS-104's own worked pair. The difference between them is the defect.
A_11340_ARREARS = D("8240.00")
A_11340_TO_CLEAR = D("8315.00")
#: What the screen said instead, on the first cut this product ever completed.
THE_WRONG_FIGURE = D("8390.00")


def _position_after_the_cut(monkeypatch, account_id) -> D:
    """Point the AR seam at the position the cut REALLY left, and return it.

    ⚠ **THE FEE HALF COMES OUT OF THE LEDGER.** `_owes` is a stand-in for the
    arrears — no bill, no journal line — so the only real money on this account
    is what the cut posted. Asking `ledger.reporting.ar_positions` for it means
    the $75.00 in the figures below is a BOOKED amount and cannot be arriving
    from this file. (`test_def_708_the_fee_is_a_real_charge` reasons identically
    and for the same reason.)
    """
    from apps.ledger import reporting as ledger_reporting

    answer = ledger_reporting.ar_positions(account_ids=[str(account_id)], as_of=None)
    assert answer.get("available"), (
        f"the ledger's AR read is unavailable ({answer.get('unavailable')}); "
        "this test cannot conclude anything"
    )
    posted = D(str((answer.get("positions") or {}).get(str(account_id)) or "0"))
    assert posted == RECONNECT_FEE, (
        "the cut should have posted exactly the reconnection fee to the books; "
        f"the ledger says {posted}"
    )
    position = A_11340_ARREARS + posted
    _owes(monkeypatch, position)
    return position


# ══════════════════════════════════════════════════════════════════════════
# TC1 · BEFORE THE CUT — the fee is a quote, so it is ADDED
# ══════════════════════════════════════════════════════════════════════════
def test_def_cus_6050_tc1__before_the_cut_the_quote_is_the_arrears_plus_the_fee(
    brazos, marcus, monkeypatch
):
    """$8,240.00 + $75.00 = **$8,315.00**, and the basis says the fee is outside.

    This half was always right and is asserted so the fix cannot be "simplified"
    into never adding: a quote given before the cut that omitted the fee would
    let somebody back in **$75.00 under**, which is DEF-708 restored.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, owed=A_11340_ARREARS)
        case = disconnects.open_case_for(account["id"])
        assert case.cut_on is None

        terms = disconnects.reconnection_terms(account["id"], case=case)
        figure = terms["to_clear"]

        assert figure["arrears"]["display"] == "8240.00"
        assert figure["fee"]["display"] == "75.00"
        assert figure["total"] == {"stored": "8315.0000", "display": "8315.00"}
        assert figure["basis"]["code"] == disconnects.TO_CLEAR_BEFORE_THE_CUT["code"]
        assert figure["basis"]["fee_in_arrears"] is False


# ══════════════════════════════════════════════════════════════════════════
# TC2 · AFTER THE CUT — the fee IS the position, so it is NOT added again
# ══════════════════════════════════════════════════════════════════════════
def test_def_cus_6050_tc2__after_the_cut_the_fee_is_not_added_to_a_position_that_holds_it(
    brazos, marcus, monkeypatch
):
    """**$8,315.00, not $8,390.00** — the defect, asserted on the signed figure.

    The cut issues the fee bill inside its own transaction, so the position the
    ledger returns afterwards already contains it. Adding the quoted fee to that
    position quotes one fee too much on the number that decides whether a
    household gets its power back.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, owed=A_11340_ARREARS)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        position = _position_after_the_cut(monkeypatch, account["id"])
        assert position == A_11340_TO_CLEAR

        case = disconnects.open_case_for(account["id"])
        assert case.cut_on == CUT_ON
        terms = disconnects.reconnection_terms(account["id"], case=case)
        figure = terms["to_clear"]

        assert figure["total"]["stored"] == "8315.0000"
        assert figure["total"]["display"] == "8315.00"
        assert figure["total"]["stored"] != f"{THE_WRONG_FIGURE:.4f}"
        assert figure["basis"]["code"] == disconnects.TO_CLEAR_AFTER_THE_CUT["code"]
        assert figure["basis"]["fee_in_arrears"] is True
        # The fee is still STATED — it is what the customer is paying for — and
        # it is simply no longer a second addend (`FEE_POSTED`'s own words:
        # *"a caller states both and never adds them together"*).
        assert figure["fee"]["display"] == "75.00"


# ══════════════════════════════════════════════════════════════════════════
# TC3 · THE QUOTE AND THE GATE ARE ONE FIGURE
# ══════════════════════════════════════════════════════════════════════════
def test_def_cus_6050_tc3__the_gate_and_the_quote_are_the_same_number(brazos, marcus, monkeypatch):
    """What a clerk is told to collect is what `mark_reconnecting` opens on.

    ⛔ **THIS IS THE ASSERTION THE DEFECT WAS ABOUT.** `_to_clear` quotes; this
    gate refuses until it is paid. The two disagreeing by one fee is a household
    told to pay **$8,390.00** to clear a gate that opens at **$8,315.00** — so
    they are pinned to each other here rather than to two literals.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, owed=A_11340_ARREARS)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        position = _position_after_the_cut(monkeypatch, account["id"])

        case = disconnects.open_case_for(account["id"])
        quote = disconnects.reconnection_terms(account["id"], case=case)["to_clear"]
        gate = disconnects._balance_for(account["id"])
        assert (
            D(quote["total"]["stored"]) == gate
        ), f"the quote and the gate differ by {D(quote['total']['stored']) - gate}"
        assert gate == position == A_11340_TO_CLEAR

        # ⚠ `DEF-CUS-8850` — UNTIL 2026-09-25 THIS WAS A REFUSAL. `BR-CUS-1097`
        # (PO: *"Show what's still owed and let the clerk proceed"*) removed the
        # gate: reconnecting while money is owed now SUCCEEDS and the clerk is
        # SHOWN the figure. This case's claim is unchanged and matters more —
        # what the clerk is told is the quote, to the cent, at 2dp as a string
        # (rule 2), never the raw 6dp Decimal and never the fee counted twice.
        payload = disconnects.mark_reconnecting(marcus, account["id"], on_date=CUT_ON)
        assert payload["state"] == disconnects.STATE_RECONNECTING
        assert D(payload["owed_at_reconnection"]["stored"]) == gate == D(quote["total"]["stored"])
        assert payload["owed_at_reconnection"]["display"] == "8315.00"
        owed = [w for w in payload["warnings"] if w["code"] == "money_still_owed"]
        assert len(owed) == 1
        assert "8315.00" in owed[0]["detail"]
        assert "8390" not in owed[0]["detail"]


# ══════════════════════════════════════════════════════════════════════════
# TC4 · THE SCREEN THE PO READ
# ══════════════════════════════════════════════════════════════════════════
def test_def_cus_6050_tc4__the_record_panel_quotes_the_module_and_adds_nothing(
    brazos, marcus, monkeypatch
):
    """p143's `To clear first`, which is where `$8,390.00` was seen.

    The panel used to do its own `Owed + fee`. A second copy of the arithmetic
    is how the two came to disagree, so this asserts the panel is the module's
    answer rather than merely that it now prints the right number.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, owed=A_11340_ARREARS)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        _position_after_the_cut(monkeypatch, account["id"])

        case = disconnects.open_case_for(account["id"])
        panel = disconnect_record._what_a_cut_would_do(case, _account_row(account["id"]))
        cell = panel["to_clear_before_reconnection"]

        assert cell["display"] == "8315.00"
        assert cell["stored"] == "8315.0000"
        assert cell["currency"] == "USD"
        assert cell["unavailable"] is None
        # The fee row still shows the fee — the panel states both facts and adds
        # neither to the other.
        assert panel["reconnection_fee"]["display"] == "75.00"

        module = disconnects.reconnection_terms(account["id"], case=case)["to_clear"]
        assert cell["stored"] == module["total"]["stored"]


# ══════════════════════════════════════════════════════════════════════════
# TC5 · AN UNREADABLE POSITION AFTER THE CUT IS STILL AN ABSENCE
# ══════════════════════════════════════════════════════════════════════════
def test_def_cus_6050_tc5__after_the_cut_an_unreadable_position_states_no_total(
    brazos, marcus, monkeypatch
):
    """`None` with its reason, never `$0.00` — `DEF-127` on the post-cut branch.

    ⚠ **AND THE FEE BEING UNREADABLE NO LONGER BLANKS THE FIGURE.** After the
    cut the fee is not an addend, so a catalogue row RETIRED months later must
    not remove the number that gates a household's supply. Both halves of that
    are asserted here because the obvious "simplification" is to keep requiring
    the fee on both branches.

    ⚠ **THE CHARGE IS RETIRED, NOT DELETED, AND THAT IS THE PRODUCT'S ANSWER
    RATHER THAN A TEST CONVENIENCE.** A first draft called `.delete()` and got
    `ProtectedError: … referenced through protected foreign keys:
    'InvoiceLine.charge'` — the cut's own fee LINE holds the code, so once a fee
    has been billed the row cannot leave. Retiring it (`deleted_at`) is what a
    utility can actually do, and `rating.selectors.charge_by_code` answers
    `None` for it by name: *"a retired charge is not chargeable"* (IS-1).
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, owed=A_11340_ARREARS)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        case = disconnects.open_case_for(account["id"])

        # (a) the books cannot be asked
        _owes(monkeypatch, None, available=False)
        figure = disconnects.reconnection_terms(account["id"], case=case)["to_clear"]
        assert figure["total"] is None
        assert figure["total_absence"]["code"] == "reconnection_total_not_computable"
        assert "DEF-CUS-6050" in figure["total_absence"]["br_ref"]
        assert figure["basis"]["fee_in_arrears"] is True

        # (b) the books answer and the tenant has RETIRED its charge code
        _position_after_the_cut(monkeypatch, account["id"])
        rating_models.Charge.objects.filter(  # noqa: F405 — W7 fixture import
            tenant=brazos, code=disconnects.RECONNECT_CHARGE_CODE
        ).update(deleted_at=timezone.now())
        figure = disconnects.reconnection_terms(account["id"], case=case)["to_clear"]
        assert figure["fee"] is None
        assert figure["total"]["display"] == "8315.00"
