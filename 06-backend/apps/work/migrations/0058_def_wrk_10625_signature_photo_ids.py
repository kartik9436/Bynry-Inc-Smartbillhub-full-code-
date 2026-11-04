"""work 0058 — a signature names the phone's photograph by the phone's own
photo id (DEF-WRK-10625; decision log 2026-10-27, PO *"start ... the signature
fix"*).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-27 under the PO ruling of
2026-08-09; the review-ledger row is written in the same commit.

The field app declares every photograph with the data and uploads its bytes
later on signal (`work_photo_links`, BR-WRK-062), so a signature captured on a
phone has no attachment and no stored document to point at when it arrives.
Every refusal recorded on a phone was therefore refused (*"A refusal needs a
door-hanger photo."*) and a signed mark could not travel at all.

TWO NULL-SAFE uuid COLUMNS ON `work_order_signatures` AND THE SHAPE CHECK
WIDENED BY EXACTLY THEM:
  * `door_hanger_photo_id` — a refusal's door-hanger photograph, by the phone's
    photo id; a refusal needs `door_hanger_attachment_id` OR this.
  * `image_photo_id` — the signed mark, by the phone's photo id; a signature
    needs `image_document_id` OR this.
Never both shapes: a signed row carries no door-hanger id of either kind, a
refused row no image of either kind (`ck_work_order_signatures_shape`). Every
existing row satisfies the new check unchanged (both new columns NULL, and the
old check required the file itself). No RLS change: `work/0017`'s `ENABLE` +
`FORCE` covers the table and its new columns. The reverse drops the columns
and restores the old check — refused if a phone row has been written since,
which is the correct answer: such a row is lawful only under this migration.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0057_rls_force_cr194_refused_items"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="workordersignature",
            name="ck_work_order_signatures_shape",
        ),
        migrations.AddField(
            model_name="workordersignature",
            name="door_hanger_photo_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workordersignature",
            name="image_photo_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="workordersignature",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("decline_reason__isnull", True),
                        ("door_hanger__isnull", True),
                        ("door_hanger_photo_id__isnull", True),
                        ("printed_name__isnull", False),
                        ("refused", False),
                        models.Q(
                            ("image__isnull", False),
                            ("image_photo_id__isnull", False),
                            _connector="OR",
                        ),
                    ),
                    models.Q(
                        ("decline_reason__isnull", False),
                        ("image__isnull", True),
                        ("image_photo_id__isnull", True),
                        ("printed_name__isnull", True),
                        ("refused", True),
                        models.Q(
                            ("door_hanger__isnull", False),
                            ("door_hanger_photo_id__isnull", False),
                            _connector="OR",
                        ),
                    ),
                    _connector="OR",
                ),
                name="ck_work_order_signatures_shape",
            ),
        ),
    ]
