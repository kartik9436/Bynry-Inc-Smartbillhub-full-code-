# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 · AMENDMENT 1, seed task (backfill half) — existing tenants'
#           enabled electric/water gain their per-service VEE rows.  Screens: S64
# Rules:    BR-MET-020 · CLAUDE.md hard rule 1 · see _0031_helpers.py, which is
#           the logic and the full docstring; this file is deliberately thin so
#           the migration-guard never has to block a logic fix (DEF-639's
#           lesson, via the _0018_helpers precedent).
# ───────────────────────────────────────────────────────
"""metering 0031 — backfill `read_validation_service_settings` for existing
tenants. 🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (migration ordering + writes
under per-tenant RLS context); ledger row is the orchestrator's to write.

Reverse is a NOOP by design: by the time anyone reverses, a tenant may have
EDITED its rows through S64, and un-migrating must not eat a tenant's config.
Reversing 0030 drops the whole table anyway; nothing is stranded.
"""

from django.db import migrations

from apps.metering.migrations import _0031_helpers


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0030_cr038_read_validation_service_settings_rls"),
    ]

    operations = [
        migrations.RunPython(_0031_helpers.run_backfill, migrations.RunPython.noop),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 Amendment 1 (2026-08-26)
# generated: 2026-08-26 by the CR-038 A1 S64 lane
# checklist: (carried by _0031_helpers.py — this file is the RunPython shell)
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
