"""customers 0078 — `DEF-CUS-9521`: the deposit size a clerk picked.

PO ruling 2026-10-04 (decision log *"THREE PO ANSWERS"*, item 3), verbatim:
*"(c) Let the clerk pick the size on the Deposit step."* A plan whose deposit
is priced by meter size asks the connection's size; a vacant unit with no
meter fitted has none, so the clerk picks one and the account keeps it — the
first bill reads it back and asks the same figure the counter took.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).

🔒 HUMAN-REVIEW-PENDING — migration ordering
(`12-governance/09-human-review-ledger.md`, `DEF-CUS-9521`).

ADDITIVE AND SAFE ON EVERY EXISTING ROW: three nullable columns, NULL on every
account written before this migration (*no size was picked*). Rollback:
reverse this migration; the picks are lost and an account opened on a picked
size would have its first bill refused by name (`size_not_recorded`) rather
than billed without its deposit.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0077_cr164_w4_billing_only_owner_account"),
        ("identity", "0005_cr070_f_field_technician"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="deposit_size_class",
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
        migrations.AddField(
            model_name="account",
            name="deposit_size_picked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="account",
            name="deposit_size_picked_by",
            field=models.ForeignKey(
                blank=True,
                db_column="deposit_size_picked_by",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="identity.user",
            ),
        ),
    ]
