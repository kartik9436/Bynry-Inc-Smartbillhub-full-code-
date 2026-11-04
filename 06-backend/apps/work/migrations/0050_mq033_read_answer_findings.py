"""work 0050 — a route finding may be of kind `read_answer`, converted
`by_read_format` (MQ-033, `CR-192-BRC10`, lane MQ033-SERVER, 2026-10-24).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-24 under the PO ruling of
2026-08-09; the review-ledger row is written in the same commit.

TWO CHECK CONSTRAINTS WIDENED BY ONE VALUE EACH, NOTHING ELSE. No row
changes, no column, no RLS change (`work/0049`'s policy stands). Every value
the old constraints admitted is still admitted, so the migration cannot
refuse an existing row. A read-format question that raises a job is handed to
Work's own raise path (`route_findings.raise_for_read_answer`), which stores
the finding and converts it in one savepoint, exactly like a rule's raise.
"""


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0049_rls_force_route_findings"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="workroutefinding",
            name="ck_work_route_findings_kind",
        ),
        migrations.RemoveConstraint(
            model_name="workroutefinding",
            name="ck_work_route_findings_converted",
        ),
        migrations.AddConstraint(
            model_name="workroutefinding",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "kind__in",
                        (
                            "leak",
                            "damaged_meter",
                            "broken_seal",
                            "suspected_tamper",
                            "unsafe_access",
                            "something_else",
                            "meter_mismatch",
                            "read_answer",
                        ),
                    )
                ),
                name="ck_work_route_findings_kind",
            ),
        ),
        migrations.AddConstraint(
            model_name="workroutefinding",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("conversion__isnull", True),
                        ("status", "open"),
                        ("work_order__isnull", True),
                    ),
                    models.Q(
                        ("conversion__in", ("by_rule", "by_hand", "by_read_format")),
                        ("status", "work_order_created"),
                    ),
                    _connector="OR",
                ),
                name="ck_work_route_findings_converted",
            ),
        ),
    ]
