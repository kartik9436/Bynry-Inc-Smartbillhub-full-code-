# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-015 (single-bill correction — it writes the credit note) ·
#           US-BIL-016 (bulk corrections — the same note in quantity) ·
#           US-BIL-005 (the release sign-off panel, the money code that READS
#           the column and read $272.30 where the customer owed $222.30)
#           Screens: S30 · S31
# Rules:    BR-BIL-074 (a credit note's amount is never positive) · BR-BIL-014
#           (the correction workflow) · BR-BIL-041 (class R credits the original
#           in FULL, class C credits part of it) · BR-BIL-004 / CLAUDE.md rule 4
#           (an issued credit note is frozen — why the sign can only be set at
#           INSERT) · CLAUDE.md rule 2 (money is NUMERIC(18,6) + CHAR(3))
# Golden:   ❄️ GT-6 — a $25.00 goodwill credit against a $247.30 invoice leaves
#           the customer owing $222.30. UNMOVED by this change, and that is the
#           assertion that matters most in this file.
# Tests:    this file (DEF-085)
# Impacts:  06-backend/apps/billing/models.CreditNote (the constraint) ·
#           apps/billing/migrations/0020_credit_note_sign.py (which REFUSES
#           rather than rewriting frozen rows) · apps/billing/release.py's
#           `_credit_magnitude`, whose magnitude-summing is now provably
#           equivalent and is deliberately left alone
# ───────────────────────────────────────────────────────
"""DEF-085 — a money column with two writers and no stated direction.

**THE DEFECT.** `credit_notes.amount` carried no sign convention.
`corrections.execute_credit_only` wrote **−25.000000**; the older correction
fixtures wrote **+25.00**. The column refused neither, and then money code
started reading it: the release sign-off panel nets credits into what a run's
customers owe. A signed Σ across the two conventions read **$272.30 on a run
where the customer owes $222.30** — the credit ADDED itself to the bill. The
panel survived only by summing MAGNITUDES per row and applying the direction
once, which is a reader compensating for an unconstrained column, and DEF-085
names that for what it is: *"how the next reader gets it wrong"*.

**THE FIX IS AT THE COLUMN, WHERE EVERY FUTURE READER MEETS IT.**
`ck_credit_notes_amount_not_positive` (billing/0020, BR-BIL-074): a credit
note's amount is `<= 0`, because a credit REDUCES what the customer owes.

**`<= 0` AND NOT `< 0`.** A class-R restatement credits the ORIGINAL TOTAL in
full and a $0.00 bill is a real document (BR-BIL-041/043 turn on that case), so
a strict inequality would refuse a legitimate correction in order to tidy a sign
that zero does not have. The rule stated is the useful one: **a credit note
never INCREASES what a customer owes.**

**NOTHING FROZEN MOVED, and this file proves it rather than claiming it.**
GT-6's $222.30 is reached from `-25.000000` exactly as before: the frozen figure
is the MAGNITUDE and the resulting balance, and neither is a function of how the
column stores its direction.
"""

from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction

from apps.billing import models, release

from tests.test_us_bil_016_bulk_corrections import (
    ISSUED_AT,
    ORIGINAL_TOTAL,
    an_issued_bill,
)
from tests.test_w3_billing_models import a_run, an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: ❄️ GT-6, verbatim: a **$25.00** goodwill credit against a **$247.30** invoice
#: leaves the customer owing **$222.30**. The magnitude and the balance are what
#: finance signed; the storage sign is not, and that is the whole distinction
#: this file exists to hold.
GT6_BILL = Decimal("247.30")
GT6_CREDIT_MAGNITUDE = Decimal("25.00")
GT6_BALANCE = Decimal("222.300000")

#: The constraint's name, spelled once. A test that matched on the message text
#: instead would pass on SQLite for the wrong reason.
CONSTRAINT = "ck_credit_notes_amount_not_positive"


def _a_note(tenant, account, bill, amount, **overrides):
    values = {
        "tenant": tenant,
        "account": account,
        "original_invoice": bill,
        "amount": amount,
        "currency": "USD",
        "reason": "goodwill",
        "issued_at": ISSUED_AT,
    }
    values.update(overrides)
    return models.CreditNote.objects.create(**values)


# ═══════════════════════════════════════════════════════════════════════════
# THE CONSTRAINT — what may be written, and what may not
# ═══════════════════════════════════════════════════════════════════════════
def test_def_085__a_positive_credit_note_is_refused_by_the_database(brazos, dana):
    """**THE CASE THE DEFECT WAS WRITTEN FOR.** +25.00 no longer exists.

    Asserted at the DATABASE and not at a service, deliberately. A service check
    protects the one path that calls it; a CHECK constraint protects the column
    from every path, including the two the product does not have yet, a data
    import, and a hand-typed `UPDATE` in a console at 2am. DEF-085's own
    prescription is *"on the MODEL as a check constraint"* for exactly that
    reason.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos, account_no="A-DEF085-1")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2607-085001")

        with pytest.raises(IntegrityError) as refusal, transaction.atomic():
            _a_note(brazos, account, bill, GT6_CREDIT_MAGNITUDE)
        assert CONSTRAINT in str(refusal.value)


def test_def_085__the_ruled_direction_and_a_zero_are_both_accepted(brazos, dana):
    """NEGATIVE is the convention, and ZERO is allowed on purpose.

    The zero is not an oversight to be tightened later. A class-R restatement
    credits the ORIGINAL TOTAL in full (`corrections.execute_restatement` writes
    `-impact.original_total`), and a $0.00 bill is a document this product
    issues — BR-BIL-041/043 turn on precisely that case. A strict `< 0` would
    make correcting a zero-total bill impossible in order to tidy a sign that
    zero does not have, which is a rule getting in the way of the thing it
    exists to protect.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos, account_no="A-DEF085-2")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2607-085002")
        zero_bill = an_issued_bill(brazos, account, run, invoice_no="BL-2607-085003")

        credit = _a_note(brazos, account, bill, -GT6_CREDIT_MAGNITUDE)
        assert credit.amount == -GT6_CREDIT_MAGNITUDE

        nothing = _a_note(brazos, account, zero_bill, Decimal("0.00"))
        assert nothing.amount == Decimal("0.00"), "a zero-total bill is restatable"


# ═══════════════════════════════════════════════════════════════════════════
# THE FROZEN FIGURE — the assertion that decides whether this was safe
# ═══════════════════════════════════════════════════════════════════════════
def test_def_085__gt6s_ratified_222_30_is_unmoved_by_the_constraint(brazos, dana):
    """❄️ GT-6: $25.00 against $247.30 → **$222.30**, from the stored −25.000000.

    The one question a sign convention on a money column has to answer is
    whether it moved a signed figure. It did not, and it could not: what finance
    signed is the credit's MAGNITUDE and the balance it leaves, and neither is a
    function of how the column stores its direction. **Had this moved 222.30,
    the change would have been an OQ for a finance re-sign (HUMAN-GUIDE §6) and
    not a migration** — B4 and B5 are ❄️ FROZEN and no lane edits them.

    The panel is read through `release.summary_for`, the real caller — the one
    that read $272.30 across the two conventions — rather than through a
    re-derivation here.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos, account_no="A-DEF085-3")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2607-085004", total=GT6_BILL)
        _a_note(brazos, account, bill, -GT6_CREDIT_MAGNITUDE, credit_note_no="CN-2607-085004")

        summary = release.summary_for(run)
        assert summary.amount == GT6_BALANCE
        assert summary.gross_amount == Decimal("247.300000"), "the bill's own total never moves"
        assert summary.credits_applied == Decimal("25.000000"), "the MAGNITUDE, as GT-6 states it"


def test_def_085__the_signed_sum_and_the_magnitude_sum_now_agree(brazos, dana):
    """With one convention there is only one answer — the point of constraining.

    The panel keeps summing magnitudes and that is deliberate: under the
    constraint `Sum(Abs(amount))` and `-Sum(amount)` are provably the same
    number, so there is no figure to move and no reason to rewrite a money
    reader in another lane's live file to make a point. This case asserts the
    equivalence rather than asserting it in a comment, so the day someone DOES
    simplify the reader they have the proof that it is safe.

    Two notes, on two bills, **−25.00 and −247.87**: signed Σ **−272.87**,
    magnitude Σ **272.87**. Before the constraint those two could be −222.87 and
    272.87 on the same rows, and $50 of difference is a support call.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos, account_no="A-DEF085-4")
        first = an_issued_bill(brazos, account, run, invoice_no="BL-2607-085005")
        second = an_issued_bill(brazos, account, run, invoice_no="BL-2607-085006")
        _a_note(brazos, account, first, -GT6_CREDIT_MAGNITUDE)
        _a_note(brazos, account, second, -ORIGINAL_TOTAL)

        from django.db.models import Sum
        from django.db.models.functions import Abs

        notes = models.CreditNote.objects.filter(
            tenant=brazos, original_invoice__in=[first, second]
        )
        signed = notes.aggregate(total=Sum("amount"))["total"]
        magnitude = notes.aggregate(total=Sum(Abs("amount")))["total"]

        assert signed == -(GT6_CREDIT_MAGNITUDE + ORIGINAL_TOTAL)
        assert magnitude == GT6_CREDIT_MAGNITUDE + ORIGINAL_TOTAL
        assert -signed == magnitude, "one convention, one answer — DEF-085 closed"


# ═══════════════════════════════════════════════════════════════════════════
# THE IMMUTABILITY THE MIGRATION HAD TO RESPECT
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="the immutability trigger is billing/0002 PL/pgSQL — SQLite has no triggers, and a "
    "bare skip here would hide the exact reason 0020 refuses instead of rewriting history",
)
def test_def_085__an_issued_credit_notes_amount_cannot_be_flipped_afterwards(brazos, dana):
    """**WHY `0020` REFUSES OVER OFFENDING ROWS RATHER THAN UPDATING THEM.**

    `billing_credit_note_immutable()` (billing/0002) refuses any UPDATE that
    changes `amount` on a row whose `issued_at` is set. So a data migration
    CANNOT flip an issued credit note's sign — and hard rule 4's append-only
    alternative, a new row, would be a SECOND CREDIT: the customer given the
    money twice, in the books and on their bill. The sign was an ENCODING error,
    not a money error, and nothing append-only re-encodes a fact.

    That is the whole reason `0020` counts violating rows, names them and stops,
    leaving a human to choose between reissuing the corrections properly and
    installing the constraint `NOT VALID`. This case is the evidence for that
    design decision, asserted rather than asserted-in-prose.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos, account_no="A-DEF085-5")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2607-085007")
        note = _a_note(brazos, account, bill, -GT6_CREDIT_MAGNITUDE)

        note.amount = GT6_CREDIT_MAGNITUDE
        with pytest.raises(Exception) as refusal, transaction.atomic():
            note.save(update_fields=["amount"])
        assert "hard rule 4" in str(refusal.value) or "BR-BIL-004" in str(refusal.value)

        assert models.CreditNote.objects.get(pk=note.pk).amount == -GT6_CREDIT_MAGNITUDE


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-015@e9d5a48 (sources, in order: 12-governance/10-defect-log.csv DEF-085 · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-074 + BR-BIL-014/041/043 · 04-docs/02-decisions/05-golden-tests.md GT-6 ❄️ · 06-backend/apps/billing/migrations/0002_rls_w3_and_immutability.py)
# generated: 2026-08-15 by the money-correctness lane (DEF-085)
# checklist: A✔ B✔ C✔ D=deferred(no API half — a column constraint) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN on live PostgreSQL — with the constraint
#         dropped, test_def_085__a_positive_credit_note_is_refused_by_the_database
#         fails `Failed: DID NOT RAISE <class 'django.db.utils.IntegrityError'>`
#         and the +25.00 row is written without complaint, which IS the defect
# exceptions: the immutability case carries a vendor skipif rather than a bare
#         skip, and names what is unproven on SQLite — the trigger it asserts is
#         PL/pgSQL and does not exist there (DEF-117's lesson: the default test
#         tier cannot see a whole family of database-level defects)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
