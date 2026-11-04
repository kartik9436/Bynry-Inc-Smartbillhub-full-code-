"""work 0044 — `technician_devices` learns the native app's device registration.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path) · HUMAN-REVIEW-PENDING —
review-ledger row "SRV-AUTH — NATIVE SIGN-IN" (2026-10-21).

`CR-187-BRC10` (Security §4, `07-endpoints.md` N24). Additive only:

* `device_uid` — the handset's own id; one row per (device, technician), so a
  shared tablet holds a registration for each technician who signs in on it;
* `token` becomes NULLABLE — a handset is registered by NAME at activation,
  before or without any push permission (push reads only rows with a token);
* `signed_out_at` / `signed_out_by` — the office's remote sign-out (`R115`);
* `capture_epoch` — bumped by a remote sign-out, so a capture credential minted
  before it names a signed-out registration and its items are HELD, never lost.

HUMAN-REVIEW-PENDING — 🔒 auth, AI-authored 2026-10-21. No RLS change: the
table already carries ENABLE + FORCE (`work/0015`), and a column inherits it.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0043_cr187_field_orders"),
    ]

    operations = [
        migrations.AddField(
            model_name="techniciandevice",
            name="capture_epoch",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="techniciandevice",
            name="device_uid",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="techniciandevice",
            name="signed_out_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="techniciandevice",
            name="signed_out_by",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="techniciandevice",
            name="token",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="techniciandevice",
            index=models.Index(fields=["tenant", "device_uid"], name="ix_tech_devices_uid"),
        ),
        migrations.AddConstraint(
            model_name="techniciandevice",
            constraint=models.UniqueConstraint(
                condition=models.Q(("device_uid__isnull", False)),
                fields=("tenant", "device_uid", "technician"),
                name="uq_technician_devices_uid_tech",
            ),
        ),
    ]
