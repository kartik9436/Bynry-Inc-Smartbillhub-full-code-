"""customers 0077 — `CR-164-BRC10` wave 4: a BILLING-ONLY owner's account.

PO ruling 2026-10-03 (decision log *"TWO PO ANSWERS"*, item 1), verbatim:
*"C By owner type: an owner who lives there holds it; a landlord or builder
doesn't"*. A single-family New Connection whose owner does not live there opens
(Then *"B"*, then *"i dont know yet"* — the owner-occupier half is `OQ-CUS-12785`, OPEN.)
a `regular` account that names the premises and NO unit: it pays the build's
charges and holds nothing, so the home stays vacant for a tenant's Move-in.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).

🔒 HUMAN-REVIEW-PENDING — migration ordering / occupancy path
(`12-governance/09-human-review-ledger.md`, `CR-164-BRC10` wave 4).

ADDITIVE AND SAFE ON EVERY EXISTING ROW: one boolean defaulting to `false`,
so every account written before this migration keeps `billing_only = false`
and both constraints hold for it exactly as `ck_accounts_regular_has_unit`
held before (the relaxed clause is reachable only with the new flag set).
Rollback: reverse this migration — refused by the database while a
billing-only row exists, which is the honest refusal (such a row has no unit
to put back).
"""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0076_cr161_w6_request_custom_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="billing_only",
            field=models.BooleanField(default=False),
        ),
        migrations.RemoveConstraint(
            model_name="account",
            name="ck_accounts_regular_has_unit",
        ),
        migrations.AddConstraint(
            model_name="account",
            constraint=models.CheckConstraint(
                condition=~Q(kind="regular") | Q(unit__isnull=False) | Q(billing_only=True),
                name="ck_accounts_regular_has_unit",
            ),
        ),
        migrations.AddConstraint(
            model_name="account",
            constraint=models.CheckConstraint(
                condition=Q(billing_only=False) | Q(unit__isnull=True),
                name="ck_accounts_billing_only_has_no_unit",
            ),
        ),
    ]
