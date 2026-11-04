# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-015 (single-bill correction — the credit note it writes) ·
#           US-BIL-016 (bulk corrections — the same note, in quantity) ·
#           US-BIL-005 (the release sign-off panel, which READS this column to
#           net what the customers on a run owe now)
#           Screens: S30 · S31
# Rules:    BR-BIL-074 (a credit note's amount is never positive — this
#           migration IS that rule) · BR-BIL-014 (the correction workflow) ·
#           BR-BIL-041 (the class taxonomy: R credits the original in full, C
#           credits part of it) · BR-BIL-004 / CLAUDE.md rule 4 (an ISSUED
#           credit note is frozen — which is why this migration refuses rather
#           than rewrites) · CLAUDE.md rule 2 (money is NUMERIC(18,6) + CHAR(3);
#           a signed column with no stated direction is half a number) ·
#           rule 1 (RLS inherited: a constraint on an already-policied table)
# Tests:    06-backend/tests/test_def_085_credit_note_sign.py
# ───────────────────────────────────────────────────────
"""billing 0020 — `credit_notes.amount <= 0`, the sign convention as a constraint.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path, and this
constraint decides how every future reader interprets a money column).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-15 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md.

════════════════════════════════════════════════════════════════════════════
THE DEFECT, WITH ITS NUMBER
════════════════════════════════════════════════════════════════════════════
**DEF-085.** `credit_notes.amount` shipped with no stated direction and TWO
WRITERS STORING OPPOSITE ONES: `corrections.execute_credit_only` writes
`-25.000000`, the older correction fixtures write `+25.00`, and the column
refused neither. Money code then began READING it — the release sign-off panel
nets it into what a run's customers owe — and a signed Σ across the two
conventions read **$272.30 on a run where the customer owes $222.30**. The
credit ADDED itself to the bill.

The panel works today only because it sums MAGNITUDES per row
(`Sum(Abs(...))`, never `abs(Sum(...))`) and applies the direction once. That
is a reader compensating for an unconstrained column, and DEF-085 names it for
what it is: *"how the next reader gets it wrong"*.

════════════════════════════════════════════════════════════════════════════
THE DIRECTION, AND WHY THIS IS AN ENGINEERING CALL AND NOT A RULING
════════════════════════════════════════════════════════════════════════════
**NEGATIVE.** DEF-085's own words: *"Pick a direction (negative reads naturally
as 'a credit against the bill'), constrain it, and migrate the existing rows."*
Both live writers already write negative; this makes it the only thing writable.

Choosing the STORAGE SIGN of a column is a schema decision. **No signed figure
moves and none could:** ❄️ GT-6 is *$25.00 credit against a $247.30 invoice →
the customer owes $222.30*, and 222.30 is reached from `-25.000000` exactly as
it was reached before — the frozen figure is the MAGNITUDE and the balance, and
neither is a function of how the column stores its direction. If this had moved
a B4/B5 figure it would have been an OQ for finance and not a migration.

**`<= 0`, NOT `< 0`.** A class-R restatement credits the ORIGINAL TOTAL in full
(`corrections.execute_restatement` writes `-impact.original_total`) and a $0.00
bill is a real document this product issues — BR-BIL-041/043 turn on exactly
that case. A strict `< 0` would make correcting a zero-total bill impossible in
order to tidy a sign that zero does not have. The rule this states is therefore
the useful one: **a credit note never INCREASES what a customer owes.**

════════════════════════════════════════════════════════════════════════════
IT REFUSES OVER OFFENDING ROWS. IT DOES NOT UPDATE THEM. HARD RULE 4.
════════════════════════════════════════════════════════════════════════════
DEF-085 asks to *"migrate the existing rows"*, and on this table that phrase has
to be read against the immutability the table already carries.
`billing/0002_rls_w3_and_immutability` installs `billing_credit_note_immutable()`,
which refuses any UPDATE that changes `amount` on a row whose `issued_at` is
set — and refuses a DELETE outright. So an issued credit note's amount **cannot
be flipped by anything, including a migration**, and CLAUDE.md rule 4 says the
correction for an immutable row is a NEW ROW.

A new row is exactly what must NOT happen here. A second credit note "fixing"
the sign of the first would be a SECOND CREDIT: the customer would be given the
money twice, in the books and on their bill. The sign is an ENCODING error, not
a money error — the amount was always right and only its direction was
ambiguous — and there is no append-only operation that re-encodes a fact.

So this migration takes the only honest remaining option: **it counts the rows
that violate the constraint and, if any exist, it REFUSES to install itself and
names them.** A human then decides, with the numbers in front of them, between
the two real choices — reverse and reissue the affected corrections through
`apps/billing/corrections.py` (new rows, correct signs, the ledger following),
or install the constraint `NOT VALID` so it binds every future row and leaves
history alone. **Neither is a decision a migration may take**, and a migration
that silently rewrote frozen financial history to make its own constraint pass
would be the worst of the three by a distance.

On the tree this was written against, the count is **ZERO**: nothing in the
product has ever written a positive amount. The refusal is for the databases
this lane cannot see.

════════════════════════════════════════════════════════════════════════════
WHAT THIS DOES NOT CHANGE
════════════════════════════════════════════════════════════════════════════
  * **The release panel keeps summing magnitudes.** With the constraint in
    place `Sum(Abs(amount))` and `-Sum(amount)` are the same number, so there
    is no figure to move and no reason to touch a money reader in another
    lane's live file to prove a point. Its docstring's *"it belongs on
    `CreditNote` as a constraint, and that is another lane's table"* is now
    satisfied and stays as the record of why it was written that way.
  * **No RLS change.** `credit_notes` was policied in `0002` and a CHECK
    constraint adds no visibility.
  * **No trigger change.** Immutability is untouched; this only narrows what
    may be INSERTed.
"""

from __future__ import annotations

from django.db import migrations, models
from django.db.models import Q

#: Every row this constraint would reject, with enough on each to identify the
#: correction it came from. `%` is not used anywhere in this SQL — see DEF-064:
#: a literal percent inside migration SQL must be escaped `%%` or the cursor's
#: parameter interpolation eats it, and the SQLite tier cannot see that defect.
OFFENDING_ROWS_SQL = """
SELECT id, tenant_id, original_invoice_id, amount, currency, issued_at
FROM credit_notes
WHERE amount > 0
ORDER BY issued_at NULLS LAST, id
"""


def refuse_over_positive_rows(apps_registry, schema_editor):
    """Count the rows that violate BR-BIL-074 and REFUSE if there are any.

    Runs BEFORE `AddConstraint` so the failure a human sees is this explanation
    rather than a bare `CheckViolation` from Postgres naming a constraint they
    have never heard of. The rows are NOT modified: see the module docstring —
    an issued credit note's amount is frozen by `0002`'s trigger, and a
    compensating row would give the customer the money twice.
    """
    if schema_editor.connection.vendor != "postgresql":
        # SQLite is the developer tier and has neither the immutability trigger
        # nor a meaningful production history to protect. The CONSTRAINT below
        # still applies there — it is the guard that matters — and a check that
        # pretended to inspect production data on a throwaway database would be
        # theatre (the same reasoning `0002` gives for its own vendor guard).
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(OFFENDING_ROWS_SQL)
        rows = cursor.fetchall()
    if not rows:
        return
    listed = "\n".join(
        f"    credit_note {row[0]} tenant {row[1]} bill {row[2]} "
        f"amount {row[3]} {row[4]} issued_at {row[5]}"
        for row in rows[:20]
    )
    more = f"\n    …and {len(rows) - 20} more" if len(rows) > 20 else ""
    raise RuntimeError(
        "DEF-085 / BR-BIL-074: this database holds "
        f"{len(rows)} credit note(s) with a POSITIVE amount, and the sign convention "
        "cannot be installed over them:\n"
        f"{listed}{more}\n\n"
        "THEY ARE NOT REWRITTEN BY THIS MIGRATION, DELIBERATELY. An ISSUED credit note's "
        "amount is frozen by billing/0002's `billing_credit_note_immutable()` trigger "
        "(CLAUDE.md hard rule 4), and the append-only correction for an immutable row — a "
        "new row — would be a SECOND CREDIT here: the customer would be given the money "
        "twice. The sign is an ENCODING error, not a money error, and nothing append-only "
        "re-encodes a fact.\n\n"
        "A HUMAN DECIDES, with the rows above in front of them:\n"
        "  (a) reverse and reissue the affected corrections through "
        "apps/billing/corrections.py, so the replacements carry the correct sign and the "
        "ledger follows; or\n"
        "  (b) install the constraint NOT VALID, so it binds every future row and leaves "
        "history alone — and record WHY in 12-governance/02-decision-log.md, because a "
        "NOT VALID constraint is a rule with a documented exception and the next reader "
        "must not discover that by accident.\n\n"
        "Neither is a choice a migration may make."
    )


def no_reverse(apps_registry, schema_editor):
    """Nothing to undo: the forward step reads and raises, and writes nothing."""
    return


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0019_rls_bill_templates"),
    ]

    operations = [
        migrations.RunPython(refuse_over_positive_rows, no_reverse),
        migrations.AddConstraint(
            model_name="creditnote",
            constraint=models.CheckConstraint(
                condition=Q(amount__lte=0),
                name="ck_credit_notes_amount_not_positive",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-015@e9d5a48 (sources this slice was authored from, in order: 12-governance/10-defect-log.csv DEF-085 · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-074 + BR-BIL-014/041/043 · 04-docs/02-decisions/05-golden-tests.md GT-6 ❄️ · 06-backend/apps/billing/migrations/0002_rls_w3_and_immutability.py, whose trigger is why this refuses rather than rewrites)
# generated: 2026-08-15 by the money-correctness lane (DEF-085)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN on live PostgreSQL. (1) The CONSTRAINT: an
#         INSERT of +25.000000 is refused by the database —
#         `django.db.utils.IntegrityError: new row for relation "credit_notes"
#         violates check constraint "ck_credit_notes_amount_not_positive"` — and
#         the same insert succeeded before it existed. (2) The REFUSAL: with one
#         positive row planted, `migrate` stopped with the DEF-085 message
#         naming that row's id, amount and bill, and the constraint was NOT
#         created. (3) GREEN: -25.000000 and 0.000000 both insert; GT-6's
#         $222.30 is unmoved; golden-verify 33 PASS.
# exceptions: `<= 0` and not `< 0` — a class-R restatement credits the ORIGINAL
#         TOTAL in full and a $0.00 bill is a real document (BR-BIL-041/043), so
#         a strict inequality would refuse a legitimate correction to tidy a
#         sign that zero does not have · the migration REFUSES over violating
#         rows and never UPDATEs them: an issued credit note's amount is frozen
#         by 0002's trigger, and the append-only alternative (a new row) would
#         credit the customer TWICE · the vendor guard on the pre-check is
#         deliberate and narrower than 0002's: the CONSTRAINT applies on both
#         tiers, only the production-history INSPECTION is Postgres-only
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
