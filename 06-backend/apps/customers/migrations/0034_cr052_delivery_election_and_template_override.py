# ── Trace ──────────────────────────────────────────────
# Change:  CR-052 tasks 12 and 14 — the two facts a bill needs about an ACCOUNT
#          that no column could hold: which channels this customer elected
#          BEYOND the print floor, and which bill template is theirs.
#          Screens: S21 account detail (preferences), S31 step 6 (issue)
# Rules:   BR-BIL-036 (CONFIRMED, PO 2026-08-10 closing OQ-091 — print is the
#          floor; email and SMS are notifications elected ON TOP and can never
#          replace the document) · BR-CUS-028 (the preference capture set) ·
#          BR-BIL-025 (the template resolves per ACCOUNT: account override →
#          category default → tenant fallback) · CLAUDE.md hard-won law 3
#          (defaults fail closed — the unsafe option is the one you type)
# Tests:   06-backend/tests/test_cr052_w4_delivery_election.py
# Impacts: apps/customers/selectors.py (`delivery_channel_election_for_account`
#          — the read `apps/billing/delivery_seam.ELECTION_READ` has named by
#          string since W3 and nobody published) · apps/customers/services.py
#          (the two preferences leave REFUSED_FIELDS and become writable) ·
#          apps/billing/issue.py (the per-account template pin)
# ───────────────────────────────────────────────────────
"""customers 0034 — the delivery election, and BR-BIL-025's missing first leg.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-31 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

THREE ADDITIVE COLUMNS, NO BACKFILL, NO INDEX, NO CONSTRAINT.

**`paperless` and `sms_reminders` are NOT NULL with `default=False`, and the
direction is the whole decision.** `apps/billing/delivery_seam.py` has asked
customers for this election by name since W3 and reported
`delivery_election_unreadable` on every bill ever issued, because the columns
were PROPOSED-SCHEMA. A NULLABLE column would land and change NOTHING: the read
would answer "nobody can tell" for every existing row and the seam would go on
reporting the same absence with a column behind it — a read that exists and
answers nothing (hard-won law 2). `False` is a TRUE statement about every
account in this product: nobody has ever been asked, so nobody has elected, and
`BR-BIL-036` requires exactly one print row for such a bill, which is what the
run already produces. Emailing somebody who never asked is the unsafe option and
it is the one an operator now has to type (hard-won law 3).

**`template_override_id` is a plain uuid with no ForeignKey**, following
`discount_grants.invoice_id` — *"a plain uuid (deferred FK → billing, B11 F-3)"*.
`bill_templates` is billing's table and B2 §2's reviewed cross-module FK set runs
the other way (`invoices.account_id`); adding a second crossing is a schema
review and not a side effect of a wave. NULL means *no override*, which is every
account today, so `BR-BIL-025`'s chain degrades to *category default → fallback*
exactly as it behaves now.

**ROLLBACK** is a clean drop of all three. Nothing reads them before this
migration and no figure on any bill moves: an account that elected nothing gets
the same single print row, and an account with no override resolves the same
template. What changes is that both facts can now be RECORDED and READ.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0033_cr046_c5_account_external_ref"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="paperless",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="account",
            name="sms_reminders",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="account",
            name="template_override_id",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
