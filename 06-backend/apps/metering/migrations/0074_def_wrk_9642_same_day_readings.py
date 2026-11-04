# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-9642 — PO ruling 2026-10-04, verbatim: *"take the reading
#           records in register and use date and highest consumption reading if
#           it is apprved and validated"*.
# Rule:     BR-MET-1189 (supersedes BR-MET-016 / BR-MET-052's refuse-or-replace
#           for a same-register, same-date pair).
# 🔒 HUMAN-REVIEW-PENDING — migration ordering (CLAUDE.md sensitive paths);
#           ledger row "DEF-WRK-9642 — the reading that counts".
# ───────────────────────────────────────────────────────
"""Drop `uq_meter_reads_head`; keep the same key INDEXED, non-unique.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path; review-ledger row "DEF-WRK-9642 — the reading that counts".

A second reading of one register on one date is now stored beside the first,
so B2 r8's UNIQUE (asset, read_at, channel) over lineage heads cannot stand.
The replacement index carries the same partial condition (heads only) and the
same columns, ordered for `counted_reading.only_counted`'s per-row probe
(tenant, asset, channel, read_at).

On PostgreSQL `meter_reads` is the partitioned parent: dropping the parent
index drops every attached partition's copy, and the new index is created on
the parent and cascades to every attached partition (PG 11+). A DETACHED
archive partition keeps whatever it had, the posture `0032` and `0067` state.

Reverse: re-creating the unique index succeeds only while no register holds
two heads on one date — which is the honest answer, not a defect.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metering", "0073_cr168_est_duration_from_task_minutes"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="meterread",
            name="uq_meter_reads_head",
        ),
        migrations.AddIndex(
            model_name="meterread",
            index=models.Index(
                condition=models.Q(("superseded_by_id__isnull", True)),
                fields=["tenant", "asset", "channel", "read_at"],
                name="ix_meter_reads_head_key",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-WRK-9642 · BR-MET-1189 (PO 2026-10-04)
# generated: 2026-10-04 by lane SAMEDAY
# checklist: A✔ B✔ C=n/a D=n/a E=n/a F✔ G✔ H✔ (🔒 migration ordering → review-ledger row)
# gates: makemigrations --check · migrate up on PostgreSQL 16 · reverse refused while a register holds two readings on one date (proved)
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
