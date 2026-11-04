"""work 0059 — `work_orders.outcome` may read `not_done_payment_received`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path; `human_owned.txt`).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-28 (FB-013, `DEF-WRK-10641`) under
the PO ruling of 2026-08-09; its row is in `12-governance/09-human-review-ledger.md`.

WHAT IT DOES
------------
Widens `ck_work_orders_outcome` (`metering/0076`, state moved to work by
`work/0046`) from five tokens to SIX: the five of B18 §8.3 plus
`not_done_payment_received`, the PO's outcome of 2026-10-28 (ruling (b): the
technician found the balance cleared on a fresh read and closed the job
*"Not done — payment received"*). Nothing else moves: no column, no data, no
RLS change (`work_orders` keeps ENABLE + FORCE). Every existing row passes the
wider check unchanged.

ROLLBACK
--------
`migrate work 0058` restores the five-token check — and is REFUSED by the
database if a paid close has been written since, which is the correct answer:
such a row is lawful only under this migration.
"""

from django.db import migrations, models

FIVE = ("passed", "failed", "partially_done", "cancelled", "waiting_on_someone_else")
SIX = (*FIVE, "not_done_payment_received")


def _check(tokens):
    return models.CheckConstraint(
        condition=models.Q(("outcome__isnull", True), ("outcome__in", tokens), _connector="OR"),
        name="ck_work_orders_outcome",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0058_def_wrk_10625_signature_photo_ids"),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="workorder", name="ck_work_orders_outcome"),
        migrations.AddConstraint(model_name="workorder", constraint=_check(SIX)),
    ]
