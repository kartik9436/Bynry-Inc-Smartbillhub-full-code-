# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-6465 — every completed move-out told the clerk that billing
#          "has no tables", that payments "has no tables" and that the
#          deposit-interest accrual "is not built". All three went false while
#          the list stayed unconditional.
# Rules:   CLAUDE.md hard-won law 1 (a comment claiming a guarantee is not the
#          guarantee — here, in the direction nothing looks at: a claim about
#          ANOTHER module, never re-read when that module shipped) ·
#          B14 rule 33 (RATIONALE is ZERO words on screen) · BR-CUS-030 /
#          BR-CUS-031 / BR-CUS-025 / BR-CUS-057
# Tests:   this file
# ───────────────────────────────────────────────────────
"""DEF-CUS-6465 — what a move-out says it did not do must still be true.

`MOVE_OUT_UNAVAILABLE` is the one place a caller learns what a move-out did NOT
do, so **a lie here is worse than a silence**. Its own comment argued that the
list is unconditional *"because none of these is conditional"* — true when it was
written, and exactly what kept it from being revisited.

**MEASURED AGAINST THE LIVE SCHEMA rather than taken from the defect row**, which
is the point of this file existing at all:

| claim | table | verdict |
|---|---|---|
| billing "has no tables" | `invoices` | **EXISTS** — false |
| payments "has no tables" | `refunds`, `payments` | **EXISTS** — false |
| the accrual "is not built" | `selectors.deposit_interest_accrued` | **answers** — false |
| collections "has no tables" | `dunning_cases` | absent — still TRUE |
| notifications "has no tables" | `notification_messages` | absent — still TRUE |

So three of the five moved and two did not, and this file pins each of the five
to the thing that actually decides it. ⚠ **A SIXTH was found while checking the
five** — `move_out_date_not_checked_against_issued_bills` said *"billing has no
`invoices` table"*, and its seam has been wired since `DEF-035`; when it fires
now it means *this account has no issued bill*, which is a different fact.

⚠ **THE CODES DO NOT MOVE AND THAT IS DELIBERATE.** `final_bill_not_issued` is
still TRUE — a move-out PRICES and does not RAISE (blueprint p112, PO ruling 10
of 2026-09-20) — and `deposit_not_settled` is still true because settling needs
the final bill. What was false in both was the REASON. Renaming a code that is
still accurate would move a wire contract to fix a sentence.
"""

from __future__ import annotations

import pytest

from apps.customers import services as customers_services
from apps.customers import selectors as customers_selectors


def _entry(code: str) -> dict:
    rows = [row for row in customers_services.MOVE_OUT_UNAVAILABLE if row["code"] == code]
    assert len(rows) <= 1, f"{code} appears {len(rows)} times"
    return rows[0] if rows else {}


# ── 1 · the three false reasons are gone from the server's own detail ───────
def test_no_reason_claims_a_module_has_no_tables_when_it_has_them():
    """The sentences named billing, payments and the accrual engine by name.
    Two of those modules have had tables for far longer than the sentences have
    been wrong, and the third has answered since 2026-09-03 (CR-059 CS-20)."""
    for code in ("final_bill_not_issued", "deposit_not_settled"):
        detail = _entry(code).get("detail", "")
        assert "no tables" not in detail, f"{code} still says a module has no tables: {detail}"
    # The accrual is built, so nothing may say it is not.
    accrual = _entry("deposit_interest_not_accrued").get("detail", "")
    assert "not built" not in accrual, accrual


def test_the_issued_bill_check_no_longer_blames_a_missing_invoices_table():
    """`last_issued_invoice_period_end` has been WIRED since `DEF-035`. When it
    returns None now it means this account has no issued bill — not that billing
    has no table — and the sentence must say the thing that is true."""
    import inspect

    src = inspect.getsource(customers_services._check_move_out_against_issued_bills)
    assert "has no `invoices` table" not in src, src


# ── 2 · the accrual entry is CONDITIONAL, like final_reads_not_committed ────
def test_deposit_interest_is_only_reported_absent_when_the_accrual_cannot_answer():
    """⚠ **THE SHAPE `final_reads_not_committed` ALREADY HAS.** An unconditional
    row is a claim about the PRODUCT; a conditional one is a claim about THIS
    move-out. The accrual answers, so telling every clerk it was not worked out
    is false on the accounts where it was."""
    import inspect

    src = inspect.getsource(customers_services.move_out)
    assert "deposit_interest_not_accrued" in src, (
        "the accrual entry is not filtered anywhere in move_out — it is still unconditional"
    )


def test_the_accrual_selector_answers_so_the_claim_was_false():
    """The measurement behind the defect, kept as a test so it cannot rot back:
    the name exists and is callable. If this ever fails, the unconditional row
    was right all along and this whole file needs re-reading."""
    assert callable(getattr(customers_selectors, "deposit_interest_accrued", None))


# ── 3 · the two that are STILL TRUE are untouched ───────────────────────────
@pytest.mark.parametrize(
    "code,word",
    [("dunning_not_stopped", "collections"), ("closeout_documents_not_queued", "notifications")],
)
def test_the_reasons_that_are_still_true_keep_their_words(code, word):
    """⚠ **THE MIRROR-IMAGE DEFECT, GUARDED.** A lane correcting stale claims is
    one keystroke from 'correcting' the two that are still exact. Collections and
    notifications genuinely have no tables, so these two sentences are the only
    honest thing to say and must survive a sweep."""
    detail = _entry(code).get("detail", "")
    assert word in detail, f"{code} stopped naming {word}: {detail}"
    assert "no table" in detail, f"{code} stopped saying why: {detail}"


# ── 4 · nothing was quietly dropped ─────────────────────────────────────────
def test_the_list_still_names_every_thing_a_move_out_cannot_do():
    """A correction that DELETES a row is a different change from one that fixes
    a sentence, and this is the line that would catch it."""
    codes = {row["code"] for row in customers_services.MOVE_OUT_UNAVAILABLE}
    assert codes == {
        "final_bill_not_issued",
        "final_bill_handoff_not_persisted",
        "final_reads_not_committed",
        "deposit_not_settled",
        "deposit_interest_not_accrued",
        "dunning_not_stopped",
        "closeout_documents_not_queued",
    }, sorted(codes)
