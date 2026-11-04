"""work 0061 — a fifth "What the technician sees on the job" tick: Balance &
payments (FB-023 F4).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path; `human_owned.txt`).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-31 (FB-023) under the PO ruling of
2026-08-09; its row is in `12-governance/09-human-review-ledger.md`.

WHAT IT DOES
------------
PO 2026-10-31, *"F4 … B a fifth tick 'Balance & payments'"* (decision log,
same date). Two boolean columns, DEFAULT TRUE:

* `wot_details.show_balance_payments` — the template's tick;
* `work_order_details.show_balance_payments` — the job's own copy
  (`BR-WRK-008`, `order_copies`).

TRUE on every existing row, because before this column the phone showed the
balance to every employee: the default keeps today's screen (decision log
FB-023 item 4). The tick only hides the DISPLAY; FB-013's cleared-balance stop
reads the balance whatever it says (coordinator judgment, same entry).

No data step and no RLS change: both tables already carry their policy.

ROLLBACK
--------
`migrate work 0060` drops the two columns; every job then shows the balance
card again, which is what it did before.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0060_def_wrk_10652_visit_message_template_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="workordertemplatedetail",
            name="show_balance_payments",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="workorderdetail",
            name="show_balance_payments",
            field=models.BooleanField(default=True),
        ),
    ]
