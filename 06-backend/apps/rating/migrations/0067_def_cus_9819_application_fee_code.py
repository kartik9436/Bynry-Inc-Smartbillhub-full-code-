"""rating 0067 — the utility marks ONE charge code as its application fee.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering on a money path
(service-request fee lines). Row in `12-governance/09-human-review-ledger.md`
(*"2026-10-06 · THE APPLICATION FEE IS ADDED AUTOMATICALLY"*).

WHY. PO rulings 2026-10-06 (`DEF-CUS-9819`), verbatim: *"No - we wil ahve
application fees as zero and pprovide option to waive off"* (no setting; a
utility without a fee prices it at $0.00), then *"Should the application fee be
added to every request automatically? I recommend (a)."* — every new request
gets the utility's application-fee line automatically at its current price.

WHAT IT CHANGES
1. `charges.is_application_fee` boolean, NOT NULL DEFAULT FALSE — so every
   existing code is unmarked and no request anywhere changes until a utility
   marks one (hard-won law 3: the default is the safe one).
2. A partial unique index: at most ONE live (not retired) marked code per
   tenant.

No data is written. DOWN PATH: drop the index and the column; requests go back
to having their fee added by hand, and lines already added stay (nothing raised
is rewritten).
"""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0066_late_fee_grace_on_charge_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="charge",
            name="is_application_fee",
            field=models.BooleanField(default=False),
        ),
        migrations.AddConstraint(
            model_name="charge",
            constraint=models.UniqueConstraint(
                condition=Q(is_application_fee=True, deleted_at__isnull=True),
                fields=("tenant",),
                name="ux_charges_one_application_fee",
            ),
        ),
    ]
