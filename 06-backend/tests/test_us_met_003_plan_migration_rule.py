# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-003 (S16 default-plan panel)   Screens: S16
# Rules:    BR-MET-040 (a plan is REQUIRED at account activation — which is
#           what makes an unconverted unit surface instead of pricing) ·
#           BR-RAT-025 (plan-as-bundle) · CLAUDE.md prime directive (never
#           resolve an open question by choosing a value)
# ───────────────────────────────────────────────────────
"""The migration that repoints a unit's plan never guesses which plan it is.

`metering 0005` converts `units.default_tariff_id` (one service's rate
schedule) to `units.rate_plan_id` (the bundle), finding the plan through
`plan_rate_schedules`. The conversion is the only part of that migration that
makes a JUDGEMENT, and getting it wrong puts a real customer on prices nobody
chose — so it is the part that needs a test.

WHY THIS TESTS A FUNCTION AND NOT THE MIGRATION. Once the migration has run,
`default_tariff_id` no longer exists in the schema, so no test running against
the migrated database can construct the pre-migration state to drive the loop.
That is a property of destructive migrations, not a shortcut: the choice is
between testing the rule in isolation and testing nothing. The rule is
therefore a module-level function in the migration and this exercises it
directly. What is NOT covered here is the surrounding loop — the queryset, the
save, the reporting — and that is stated rather than implied.

The safety property in one line: **more than one candidate plan is not a
tie-break, it is a refusal.**
"""

from importlib import import_module

# Migration modules begin with a digit, so they cannot be imported by name.
_migration = import_module("apps.metering.migrations.0005_unit_rate_plan")
plan_for_tariff = _migration.plan_for_tariff

PLAN_A = "0199c0de-0000-7000-8000-00000000000a"
PLAN_B = "0199c0de-0000-7000-8000-00000000000b"


def test_us_met_003_tc8__one_candidate_plan_converts():
    """The ordinary case: the tariff sits in exactly one plan."""
    assert plan_for_tariff([PLAN_A]) == PLAN_A


def test_us_met_003_tc8__a_repeated_candidate_is_still_one_plan():
    """A plan listing the tariff for two services is ONE candidate, not two.

    `plan_rate_schedules` is (plan × service → tariff), so a plan that prices
    the same tariff under two services yields the same plan id twice. Counting
    rows instead of distinct plans would have read that as ambiguity and
    stranded a unit that had a perfectly good answer.
    """
    assert plan_for_tariff([PLAN_A, PLAN_A]) == PLAN_A


def test_us_met_003_tc8__no_candidate_plan_refuses():
    """An unattached rate schedule: no plan contains it, so there is no answer."""
    assert plan_for_tariff([]) is None


def test_us_met_003_tc8__several_candidate_plans_refuse_rather_than_pick():
    """THE ONE THAT MATTERS. Two plans price this tariff; the unit was on one.

    Which one is a product fact the migration does not have. Picking the first,
    the newest, or the only published one would silently put a customer on
    prices nobody chose — CLAUDE.md's "guesses in billing become silent
    production errors", with a customer's money attached.

    Returning None is not a dead end: the unit is left planless and named in
    the migration's output, and BR-MET-040 blocks account activation on a
    planless unit — so the gap surfaces at the point where it would otherwise
    start pricing, which is the earliest a machine can raise it.
    """
    assert plan_for_tariff([PLAN_A, PLAN_B]) is None
    assert plan_for_tariff([PLAN_B, PLAN_A]) is None  # order must not decide it
    assert plan_for_tariff([PLAN_A, PLAN_B, PLAN_A]) is None  # nor multiplicity


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-003@220125b (same four sources as the migration it guards)
# generated: 2026-08-11 by Eng-Lead
# checklist: A✔ B✔ C✔ D=deferred(no API — a migration rule) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved RED before green — replacing the rule body with `return
#         unique[0] if unique else None` (i.e. "just take the first plan", the
#         plausible shortcut) turns the several-candidates test RED and leaves
#         the other three GREEN. That is the exact mutation this file exists to
#         catch, and it is the one a reader would most likely write.
# exceptions: covers the RULE only. The surrounding migration loop — queryset,
#         save, and the printed report of unconverted units — is NOT exercised
#         here and cannot be: the migration drops `default_tariff_id`, so the
#         pre-migration state is unbuildable once it has run. Stated rather
#         than left to look like full coverage of the migration.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
