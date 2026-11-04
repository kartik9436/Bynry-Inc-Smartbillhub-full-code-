# ── Trace ──────────────────────────────────────────────
# Change:   CR-008 second-set ruling 1 (PO 2026-08-17, *"Im good with all"*) —
#           the tender → cash/clearing account column. Answers OQ-264 option
#           (ii) with the half the PO ruled: the COLUMN.
#           Screens: SET-11 GL mapping (section 3, Payments & deposits) ·
#           S8 → Configure → Reference data → Payment methods (the same rows)
# Rules:    BR-BIL-069 / BR-BIL-010 (a money pointer names the account it
#           lands in, and the ledger validates it) · BR-TEN-036 (the flat
#           reference-list shape this column extends) · B11 F-3 (deferred FK:
#           a uuid column, no cross-module constraint) · B2 §2 (cross-module
#           FKs are the reviewed interface set) · CLAUDE.md rule 1 (tenant
#           scoping) · CLAUDE.md rule 2 (money never moves because of a
#           settings column alone)
# ───────────────────────────────────────────────────────
"""tenancy 0015 — `payment_methods.clearing_gl_account_id`, nullable.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-17 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human."*), implementing the PO's CR-008 second-set
ruling of 2026-08-17. The gap was put to them in plain English: *"a utility
taking card, cheque, cash and IVR has nowhere to say that card lands in a
merchant clearing account and cheques in the bank"*, and the PO ruled on the
three-item list containing it: *"Im good with all"*.

────────────────────────────────────────────────────────────────────────────
WHY THE NAME IS `clearing_gl_account_id` AND NOT `gl_account_id`
────────────────────────────────────────────────────────────────────────────
`rating.charges.gl_account_id` and `rating.plan_services.gl_account_id` are
**revenue** pointers — where the money a bill EARNS lands. This one is the
**cash** side — where the money a customer HANDS OVER lands. They are opposite
sides of the same transaction and a reader who confuses them maps a tender onto
an income account without a single field name objecting.

That is not hypothetical here: CR-008's own record contains a worked example of
exactly this failure mode one field away — `write_off_threshold_amount` ($5.00,
capped at $50, an automatic small-balance rule) sitting on the same card as a
$5,000 manual approval threshold, which the PO was asked about and which was
resolved by giving the two unmistakably different labels. A name is the cheapest
place to prevent it.

"Clearing" rather than "cash" because for a cheque the account genuinely is the
bank and for a card it is a merchant clearing account — *clearing* is the term
that covers both, and a bank account used this way is the clearing account for
that tender.

────────────────────────────────────────────────────────────────────────────
WHY IT IS A UUID AND NOT A FOREIGN KEY
────────────────────────────────────────────────────────────────────────────
Identical reasoning to `0014_cr008_reason_code_gl`, and deliberately the same
words: `ledger_accounts` is another module's table, B2 §2 makes cross-module FKs
*the reviewed interface set* — a list, not a thing a lane extends on its own —
so this follows the three columns that already point the same way (B11 F-3).

The validation is not weaker for it; it is stronger. **An FK proves the row
EXISTS and never proves it is THIS TENANT's**, which in a money path is the only
question that matters. `apps.tenancy.services.PaymentMethodLookupHandler` asks
the ledger through `seams.ledger_account_is_live`, which answers ownership AND
liveness in one read — so a deactivated account (IS-1) is refused too, and a
crafted id belonging to another utility's chart is refused by the same branch.

────────────────────────────────────────────────────────────────────────────
RLS: NOTHING NEW, AND THAT IS CHECKED RATHER THAN ASSUMED
────────────────────────────────────────────────────────────────────────────
**No table is created — this adds ONE COLUMN.** `payment_methods` is already
ENABLE + FORCE under `payment_methods_tenant_isolation` from
`db/rls_tenancy_w0.sql`, applied by `0003_rls_w0_policies`. The policy gates the
ROW, so a column on a gated row is gated; writing a second policy here would
shadow the signed original. Same posture as `0014_cr008_reason_code_gl`,
`0011_uom_service_scope` and `0006_service_gl_attributes`.

The claim is backed by the sweep and not by this paragraph:
`tests/test_tenant_isolation.py` walks every tenant-scoped table rather than a
hand-kept list. PostgreSQL only — the sqlite test database cannot exercise RLS
and says so.

────────────────────────────────────────────────────────────────────────────
⚠ NOTHING POSTS DIFFERENTLY BECAUSE OF THIS MIGRATION, AND THE REASON IS
MEASURED RATHER THAN DEFERRED
────────────────────────────────────────────────────────────────────────────
Stated loudly because "built is not wired" (hard-won law 2) is the trap this
shape sits in, and because a column called *clearing account* reads like a
posting change.

`apps/payments/ledger_seam.post_payment_cleared` debits **undeposited funds**
for every tender and never reads the payment method (PO ruling 2026-08-11,
OQ-143: *"until bank record and reconcilaition confirm it it is not realised"*).
`apps/payments/reconciliation.py:68` then posts the SECOND half — *DR cash / CR
undeposited funds* — when the bank statement confirms it.

**Those two legs must move together or the trial balance goes out.** If the
receipt leg debited a per-tender clearing account while reconciliation kept
crediting undeposited funds, reconciliation would credit an account that was
never debited, by the amount of every card payment. So teaching the posting path
to prefer this column is a change to BOTH files, both on the 🔒 ledger-posting
path, and it is a separate act on a separate review — which is what OQ-264
option (ii) said in advance (*"and teach the posting service to prefer it, which
is a change to the 🔒 ledger posting path and needs its own review"*).

What ships today is therefore CONFIGURATION a utility can record, see and audit,
with **no reader in `apps/payments` or `apps/ledger`** — and the screen says so
in words rather than implying a posting that does not happen. OQ-264 stays OPEN
carrying exactly that remainder.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0014_cr008_reason_code_gl"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentmethod",
            name="clearing_gl_account_id",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
