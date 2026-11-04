# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 · the BR-MET-136 follow-up — the per-rule ENABLED switch the
#           S64 lane shipped without.
# Rules:    BR-MET-136 (PO 2026-08-26, verbatim: "yes every rule that is
#           enabled always run - you ahve to keep default - all enabled")
#           clause 1 (a judgment rule carries an ENABLED flag per (tenant,
#           service)) and clause 2 (the default is ALL ENABLED, for every
#           service, at provisioning AND on backfill) · BR-MET-020 (the switch
#           is NOT a threshold — see below) · CLAUDE.md rule 1 (no data pass
#           touches rows here — one column, so no tenant predicate is needed;
#           the table's RLS ENABLE+FORCE was set in metering 0030 and a column
#           addition neither weakens nor re-states it)
# Tests:    06-backend/tests/test_cr038_br_met_136_rule_switch.py
# ───────────────────────────────────────────────────────
"""metering 0036 — `rule_enabled` on `read_validation_service_settings`.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-26 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). The G7 ledger row is APPENDED by this lane to
12-governance/09-human-review-ledger.md in the same commit.

THE BACKFILL IS THE COLUMN DEFAULT, AND THAT IS THE POINT
---------------------------------------------------------
BR-MET-136 clause 2 is *"the default is ALL ENABLED, for every service, at
provisioning and on backfill"*, and the follow-up brief states the acceptance
condition sharply: **there must be no state in which an existing tenant
silently acquires a disabled rule.**

The map is keyed by rule name and **an absent key means ENABLED**
(`validation.rule_switches`). So the empty object every existing row receives
from `default=dict` IS all-enabled — not a value a data migration has to write
correctly, but the absence of any choice at all. There is no window between the
`ALTER TABLE` and a `RunPython` pass in which a row could hold something else,
because there is no `RunPython` pass: Django's AddField writes the default into
every existing row inside the same DDL statement.

That is why this migration has ONE operation and no data function. A
sixteen-boolean-column shape would have needed sixteen correct `default=True`
declarations and would have put clause 2 at the mercy of each one; this shape
makes the clause structural. `models.ReadValidationServiceSettings.rule_enabled`
carries the full argument.

NOT A THRESHOLD, so BR-MET-020's "never default a figure nobody ratified" does
not reach it. That law forbids the engine GUESSING a number finance has not
signed. This default was ruled in the PO's own words — *"you ahve to keep
default - all enabled"* — and it defaults to running MORE checks, never fewer.

CLAUSE 4 IS NOT ENFORCED HERE, DELIBERATELY. The seven INTEGRITY rules are not
switchable, and a CHECK constraint spelling those seven names into DDL would
freeze the engine's own vocabulary into the database — the thing this shape
exists to avoid. The lock is enforced at both doors that can act on the map
instead: `services.save_read_validation_service` refuses the attempt BY NAME
(422, the rule named), and `validation.rule_switches` forces every integrity
rule back to True whatever a row says, so a value written by a shell, a fixture
or a future migration cannot turn one off either. Both are proved RED by test.

REVERSIBLE. Dropping the column loses every tenant's switch choices and returns
the engine to running every rule — the pre-CR-038 behaviour, and the safe
direction to fail in. Nothing else depends on it.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0035_cr038_w9_event_context"),
    ]

    operations = [
        migrations.AddField(
            model_name="readvalidationservicesettings",
            name="rule_enabled",
            field=models.JSONField(default=dict),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 · BR-MET-136 (04-docs/05-modules/04-metering/02-business-rules.md)
# generated: 2026-08-26 by the CR-038 BR-MET-136 rule-switch lane
# checklist: A✔ B=n/a(migration) C✔ D=n/a E=n/a F✔ G✔ H=PENDING (🔒 migration —
#         row appended to 12-governance/09-human-review-ledger.md)
# gates: python3 manage.py makemigrations --check --dry-run → "No changes
#        detected" · ruff✔ black✔ · tests/test_cr038_br_met_136_rule_switch.py
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
