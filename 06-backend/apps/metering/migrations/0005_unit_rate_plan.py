# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-003 (S16 unit wizard — the default-plan panel) ·
#           US-CUS-003/US-CUS-005 (the account reads its plan THROUGH the unit)
#           Screens: S16 · S21 · S23
# Rules:    BR-CUS-014 (the unit plan is binding; the account derives from it) ·
#           BR-CUS-010/011/013 (dated assignment history + version snapshot) ·
#           BR-MET-007 (plan lock) · BR-MET-040 (a plan is required at account
#           activation) · BR-RAT-025 (plan-as-bundle) · BR-RAT-030 (only a
#           published plan is assignable)
# ───────────────────────────────────────────────────────
"""metering 0005 — a unit holds a PLAN, not one service's rate schedule.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), implementing the PO ruling
of 2026-08-11 ("from unit you will derive the plan … — A"). Row in
12-governance/09-human-review-ledger.md.

WHY
---
`units.default_tariff_id` pointed at `rating.tariffs` — ONE service's prices.
Everything else in the product says a unit carries a PLAN, which is a bundle
across services:

  * the S16 panel is labelled "default plan"
  * the S23 change-plan flow picks "compatible published plans for the unit's
    services" — plural
  * `unit_plan_assignments` stores `rate_plan_id` + `plan_version`

A house taking electric + water + trash is on one plan. The old column could
record one of those three services and no more, so a multi-service unit could
not state its own plan — and the assignment-history row could never be written,
because writing a tariff id into a `rate_plan_id` foreign key fails outright.
That is the actual reason `history_recorded: false` came back from every plan
assignment since W1 (the PO's "gap 1"). The column was the outlier; this
migration makes it agree with the rest of the product.

DATA — WHAT HAPPENS TO EXISTING ROWS
------------------------------------
A tariff belongs to a plan through `plan_rate_schedules` (rate_plan × service →
tariff). So for every unit carrying a tariff:

  * EXACTLY ONE plan contains that tariff → the unit is converted to that plan.
  * ZERO plans contain it (an unattached schedule), or MORE THAN ONE do → the
    unit's plan is left NULL and the unit is NAMED in the migration's output.

The ambiguous case is not resolved by picking the first, the newest, or the
only published one. Which plan a unit was meant to be on is a product fact this
migration does not have, and guessing it would put a customer on prices nobody
chose — the exact failure mode CLAUDE.md's "guesses in billing become silent
production errors" describes. A unit left NULL is not silent: BR-MET-040 blocks
account activation on a planless unit, so the gap surfaces at the point where
it would otherwise start pricing.

On the deployment this was authored against, `seed_demo` sets no unit plan and
the count is zero — the conversion is written for tenants that did.
"""

import django.db.models.deletion
from django.db import migrations, models


def plan_for_tariff(plan_ids):
    """THE CONVERSION RULE, isolated so it can be tested on its own.

    Takes the plan ids that contain a unit's tariff; returns the one to convert
    to, or None. Exactly one match converts. Zero or several do NOT — and this
    returning None is the whole safety property of the migration, so it is a
    function with a test (tests/test_us_met_003_plan_migration_rule.py) rather
    than three lines buried in a loop that nothing can reach.

    Kept at module level because a migration body is otherwise untestable after
    it has run: the old column is gone from the schema, so no post-migration
    test can build the pre-migration state to exercise the loop against.
    """
    unique = sorted(set(plan_ids))
    return unique[0] if len(unique) == 1 else None


def convert_tariffs_to_plans(apps_registry, schema_editor):
    """Map each unit's tariff to the one plan that contains it, or leave NULL."""
    Unit = apps_registry.get_model("metering", "Unit")
    PlanRateSchedule = apps_registry.get_model("rating", "PlanRateSchedule")

    ambiguous: list[str] = []
    unattached: list[str] = []
    converted = 0

    for unit in Unit.objects.exclude(default_tariff_id=None).iterator():
        plan_ids = [
            str(plan_id)
            for plan_id in PlanRateSchedule.objects.filter(
                tenant_id=unit.tenant_id, tariff_id=unit.default_tariff_id
            ).values_list("rate_plan_id", flat=True)
        ]
        resolved = plan_for_tariff(plan_ids)
        if resolved is not None:
            unit.rate_plan_id = resolved
            unit.save(update_fields=["rate_plan_id"])
            converted += 1
        elif not plan_ids:
            unattached.append(str(unit.pk))
        else:
            ambiguous.append(f"{unit.pk} (tariff in {len(set(plan_ids))} plans)")

    if converted:
        print(f"  metering 0005: {converted} unit(s) converted from tariff to plan")
    for label, units in (("in NO plan", unattached), ("in SEVERAL plans", ambiguous)):
        if units:
            print(
                f"  metering 0005: {len(units)} unit(s) left WITHOUT a plan — their "
                f"rate schedule is {label}, and which plan they belong to is not "
                f"derivable here. Assign each one on S16; account activation is "
                f"blocked on them until you do (BR-MET-040). Units: {units}"
            )


def unconvert(apps_registry, schema_editor):
    """Reverse: put back the tariff for the unit's own service, where unique.

    A plan spans services and a tariff does not, so this direction LOSES
    information whenever a plan carries more than one schedule — there is no
    single tariff to choose. Those units come back with no tariff rather than
    an arbitrary one. Recorded here so the reverse is understood as lossy
    rather than assumed symmetric.
    """
    Unit = apps_registry.get_model("metering", "Unit")
    PlanRateSchedule = apps_registry.get_model("rating", "PlanRateSchedule")
    for unit in Unit.objects.exclude(rate_plan_id=None).iterator():
        tariff_ids = sorted(
            {
                str(tariff_id)
                for tariff_id in PlanRateSchedule.objects.filter(
                    tenant_id=unit.tenant_id, rate_plan_id=unit.rate_plan_id
                ).values_list("tariff_id", flat=True)
            }
        )
        if len(tariff_ids) == 1:
            unit.default_tariff_id = tariff_ids[0]
            unit.save(update_fields=["default_tariff_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0004_rls_w2_reads_policies"),
        ("rating", "0004_schedule_drafts_and_plan_eligibility"),
    ]

    operations = [
        # Added BEFORE the old column is dropped so the conversion can read both.
        migrations.AddField(
            model_name="unit",
            name="rate_plan",
            field=models.ForeignKey(
                blank=True,
                db_column="rate_plan_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="rating.rateplan",
            ),
        ),
        migrations.RunPython(convert_tariffs_to_plans, unconvert),
        migrations.RemoveField(model_name="unit", name="default_tariff"),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-003@220125b (sha1[:7] of the four source documents this was
#         authored from, concatenated in order: 04-docs/05-modules/04-metering/
#         06-epics/EP-MET-01-premises-units.md · 04-metering/02-business-rules.md
#         · 03-customers/02-business-rules.md · 06-rating/02-business-rules.md —
#         so a later change to any of them makes this stamp findable as stale in
#         one grep). PO ruling 2026-08-11 ("from unit you will derive the plan
#         … — A"), which also unblocks the PO's gap 1
# generated: 2026-08-11 by Eng-Lead
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved RED before green — on the RULE, which is the part that makes a
#         judgement: replacing `plan_for_tariff` with the plausible shortcut
#         ("just take the first candidate") turns the several-candidates test
#         RED and leaves the other three GREEN.
#         ⚠ AN EARLIER DRAFT OF THIS TRAILER CLAIMED A RED-PROOF THAT HAD NOT
#         BEEN RUN — "with the RunPython step removed, a unit … comes out NULL
#         and the conversion test names it" — describing a test that did not
#         exist. It was written as intent and would have read as evidence.
#         Corrected to what was actually executed (hard-won law 1: a comment
#         claiming a guarantee is not the guarantee), and the missing test was
#         then written: tests/test_us_met_003_plan_migration_rule.py.
#         Also verified: makemigrations --check clean, forward and reverse both
#         applied, full backend suite green.
# exceptions: the conversion NEVER guesses an ambiguous unit (tariff in zero or
#         several plans) — it leaves the plan NULL and prints the unit ids, on
#         the reasoning that BR-MET-040 then blocks activation rather than
#         letting an unchosen price reach a bill · the reverse migration is
#         LOSSY by nature (a plan spans services, a tariff does not) and is
#         documented as such rather than presented as symmetric
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
