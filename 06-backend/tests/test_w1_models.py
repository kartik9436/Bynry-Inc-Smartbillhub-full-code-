# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-001/004/008/010/014 · US-MET-001..006 · US-AST-001..004/006..010
#           (the SCHEMA HALF of each story's TCs — the W1 models+migrations lane)
# Screens:  S9–S16 · S49–S55
# Rules:    BR-RAT-030 (plan lifecycle) · BR-RAT-035 (charge codes) · BR-RAT-037
#           (append-only versions) · BR-MET-033 (route walk order) · BR-MET-046
#           (unit never leaves its premises) · BR-AST-026/033 (3-identifier model)
#           · BR-AST-030 (retire terminal) · HR-2 (money NUMERIC(18,6)+currency)
# Note:     Service/API halves of these TCs land with each feature-story lane; this
#           file asserts what the schema itself must guarantee. RLS halves run in
#           the G5 isolation suite (sqlite cannot enforce RLS).
# ───────────────────────────────────────────────────────
from decimal import Decimal

from django.apps import apps
from django.db import models
from django.test import TestCase


def table(app_label: str, db_table: str):
    """The model backing a physical table, or None when the table is absent."""
    for model in apps.get_app_config(app_label).get_models():
        if model._meta.db_table == db_table:
            return model
    return None


def constraint_names(model) -> set[str]:
    return {c.name for c in model._meta.constraints}


def field(model, name):
    return model._meta.get_field(name)


class MoneyColumnMixin:
    """HR-2: money is NUMERIC(18,6) and never a float — asserted per money column."""

    def assert_money(self, model, field_name: str) -> None:
        f = field(model, field_name)
        self.assertIsInstance(f, models.DecimalField, f"{field_name} must be Decimal")
        self.assertEqual(f.max_digits, 18, f"{field_name} max_digits")
        self.assertEqual(f.decimal_places, 6, f"{field_name} decimal_places")


class RatingSchema(TestCase, MoneyColumnMixin):
    """EP-RAT-01..04 — Plans & Rates tables."""

    def test_us_rat_001_tc1__rate_plans_table_with_lifecycle_and_unique_code(self):
        model = table("rating", "rate_plans")
        self.assertIsNotNone(model, "rate_plans must exist (r16 rename honored — no table 'plans')")
        self.assertIn("uq_rate_plans_tenant_code_ci", constraint_names(model))
        # BR-RAT-030 lifecycle draft→published→archived: the column carries the state and
        # starts at draft; the legal transitions are enforced by the rating service (its
        # own TCs), not by a DB enum — the schema half asserts the starting state only.
        self.assertEqual(field(model, "status").default, "draft")
        self.assert_money(model, "minimum_bill_amount")

    def test_us_rat_004_tc1__tariff_versions_are_append_only_and_carry_currency(self):
        versions = table("rating", "tariff_versions")
        self.assertIsNotNone(versions)
        self.assert_money(versions, "base_charge")
        self.assertEqual(field(versions, "currency").max_length, 3, "HR-2 CHAR(3) currency")
        # BR-RAT-037: a version is effective-dated, never edited in place.
        for name in ("effective_from", "effective_to"):
            self.assertIsNotNone(field(versions, name))
        tiers = table("rating", "rate_tiers")
        self.assertIn("uq_rate_tiers_version_seq", constraint_names(tiers))
        self.assert_money(tiers, "unit_price")

    def test_us_rat_008_tc1__charge_codes_unique_per_tenant_with_money_rules(self):
        model = table("rating", "charges")
        self.assertIsNotNone(model)
        self.assertIn("uq_charges_tenant_code", constraint_names(model))
        for money_field in ("amount", "min_amount", "max_amount"):
            self.assert_money(model, money_field)

    def test_us_rat_010_tc1__taxes_hang_off_jurisdictions(self):
        taxes = table("rating", "taxes")
        jurisdictions = table("rating", "tax_jurisdictions")
        self.assertIsNotNone(taxes)
        self.assertIsNotNone(jurisdictions)
        self.assertEqual(field(taxes, "jurisdiction").related_model, jurisdictions)
        self.assert_money(taxes, "flat_amount")

    def test_us_rat_014_tc1__rate_changes_are_batched_and_logged(self):
        batches = table("rating", "rate_change_batches")
        log = table("rating", "rate_change_log")
        self.assertIsNotNone(batches, "BR-RAT-040 one atomic batch")
        self.assertIsNotNone(log)
        self.assertEqual(field(log, "batch").related_model, batches)
        # Before/after captured so a bulk change is reconstructable, never re-run.
        for name in ("before", "after", "reason", "actor"):
            self.assertIsNotNone(field(log, name))


class MeteringSchema(TestCase):
    """EP-MET-01/02 — Premises, Units, Routes & Cycles."""

    def test_us_met_001_tc1__premises_unique_number_per_tenant(self):
        model = table("metering", "premises")
        self.assertIsNotNone(model)
        self.assertIn("uq_premises_tenant_premise_no", constraint_names(model))

    def test_us_met_002_tc1__units_belong_to_one_premises_and_are_unique_within_it(self):
        model = table("metering", "units")
        self.assertIsNotNone(model)
        self.assertEqual(field(model, "premises").related_model, table("metering", "premises"))
        self.assertIn("uq_units_tenant_premises_label", constraint_names(model))
        # BR-MET-036: occupancy is DERIVED — no settable occupancy column exists.
        self.assertNotIn("occupancy", {f.name for f in model._meta.fields})

    def test_us_met_003_tc1__service_points_link_unit_service_route_cycle(self):
        model = table("metering", "service_points")
        self.assertIsNotNone(model)
        for name in ("unit", "service", "route", "cycle"):
            self.assertIsNotNone(field(model, name))

    def test_us_met_004_tc1__routes_unique_code_per_tenant(self):
        model = table("metering", "routes")
        self.assertIsNotNone(model)
        self.assertIn("uq_routes_tenant_code", constraint_names(model))

    def test_us_met_005_tc1__cycles_carry_their_schedule_and_due_days(self):
        """⚠ **RENAMED AND REPOINTED BY CR-029 W5-T2.** It asserted
        `window_start` / `window_end` / `bill_date` / `due_days` — US-MET-005
        TC-1's original four. metering 0021 dropped the first two: the read
        window is DERIVED from `start_day` + `days_to_complete` (B17 §2), which
        is what this now asserts.

        ⚠ **AMENDED AGAIN 2026-08-23 (RC-W6): `bill_date` IS GONE TOO.** It was
        asserted PRESENT here because it was the one deprecated column W5-T2 did
        not take — billing's due-terms fallback read it and no ruling said what
        replaced it. **OQ-344 ruled it** (PO: *"I'd say B - these are defualt -
        user can override"*, the bill DAY in the month after the period ends),
        metering 0023 dropped it, and the assertion moves from the PRESENT list
        to the GONE list rather than being deleted. `due_days` and `bill_day` —
        D9's two surviving defaults — are asserted present in its place.
        """
        model = table("metering", "cycles")
        self.assertIsNotNone(model)
        self.assertIn("uq_cycles_tenant_code", constraint_names(model))
        for name in ("start_day", "days_to_complete", "frequency", "bill_day", "due_days"):
            self.assertIsNotNone(field(model, name))
        for gone in ("window_start", "window_end"):
            with self.assertRaises(Exception, msg=f"cycles.{gone} was dropped by metering 0021"):
                field(model, gone)
        with self.assertRaises(Exception, msg="cycles.bill_date was dropped by metering 0023"):
            field(model, "bill_date")

    def test_us_met_006_tc1__route_membership_is_units_with_optional_walk_order(self):
        """⚠ **AMENDED 2026-08-17 by CR-006 / BR-MET-074.** This asserted the
        single constraint `uq_route_memberships_unit` — "a unit sits on one
        route". A route now carries a SERVICE, and a house on water and
        electric is legitimately read by two crews on two routes, so the old
        constraint made the product's own multi-service story unrepresentable.

        **The invariant is not weakened, it is qualified:** a unit sits on one
        route PER SERVICE. It takes TWO constraints because SQL treats NULLs
        as distinct — one over (tenant, unit, service) where the service is
        set, one over (tenant, unit) where it is NULL — and a single
        three-column unique would have let two legacy all-service routes hold
        the same unit, which is the very thing the original stopped.
        """
        model = table("metering", "route_memberships")
        self.assertIsNotNone(model, "BR-MET-033 membership model, not sequence ranges")
        names = constraint_names(model)
        self.assertIn(
            "uq_route_memberships_unit_service", names, "a unit sits on one route per service"
        )
        self.assertIn(
            "uq_route_memberships_unit_no_service",
            names,
            "…and on one all-service route, because SQL NULLs are distinct",
        )
        self.assertIn("uq_route_memberships_walk_order", names)
        self.assertIsNotNone(field(model, "service_id"), "BR-MET-074's denormalized stamp")

    def test_cr006_route_and_cycle_carry_their_new_columns(self):
        """BR-MET-071/073/076/077 — the shapes the wizards write, asserted at
        the schema so a dropped column goes RED here and not on a screen."""
        route = table("metering", "routes")
        for name in ("service_id", "area_id", "notes", "status"):
            self.assertIsNotNone(field(route, name), f"routes.{name} (CR-006)")
        cycle = table("metering", "cycles")
        # ⚠ **CR-006 SHIPPED FOUR DAY-OF-MONTH COLUMNS AND ONE SURVIVES
        # (CR-029 D2/D9, W5-T2).** `read_day_from`/`read_day_to` are superseded
        # by `start_day` + `days_to_complete`; `due_day` by `due_days`, the
        # COUNT billing adds to the bill date (BR-BIL-024). `bill_day` STAYS —
        # D9 keeps it as the cycle's default which the run may override.
        for name in (
            "name",
            "frequency",
            "start_day",
            "days_to_complete",
            "bill_day",
            "due_days",
            "status",
            "first_run_date",
        ):
            self.assertIsNotNone(field(cycle, name), f"cycles.{name} (CR-006 + CR-029)")
        self.assertIsNotNone(field(table("metering", "premises"), "area_id"), "BR-MET-071")
        exclusions = table("metering", "route_meter_exclusions")
        self.assertIsNotNone(exclusions, "BR-MET-075 stores the NEGATIVE, per route+asset")
        self.assertIn("uq_route_meter_exclusions", constraint_names(exclusions))


class AssetsSchema(TestCase):
    """EP-AST-01..04 — Asset registry, detail, lifecycle, import."""

    def test_us_ast_001_tc1__type_and_lifecycle_catalogs_exist(self):
        types = table("assets", "asset_types")
        stages = table("assets", "asset_lifecycle_stages")
        self.assertIsNotNone(types)
        self.assertIsNotNone(stages)
        self.assertIn("uq_asset_types_tenant_code_ci", constraint_names(types))
        # A5 v4 behavior classes drive what each stage allows.
        self.assertIsNotNone(field(stages, "behavior_class"))

    def test_us_ast_002_tc1__three_identifier_model_with_unique_asset_number(self):
        model = table("assets", "assets")
        self.assertIsNotNone(model)
        names = {f.name for f in model._meta.fields}
        self.assertTrue({"asset_no", "serial_no", "id"} <= names, "BR-AST-026 three identifiers")
        self.assertIn("uq_assets_tenant_no", constraint_names(model), "BR-AST-033 hard dup guard")

    def test_us_ast_003_tc1__asset_detail_relations_are_reachable(self):
        model = table("assets", "assets")
        self.assertEqual(field(model, "type").related_model, table("assets", "asset_types"))
        self.assertIsNotNone(field(model, "service_point"), "billing chain (BR-AST-039)")
        self.assertIsNotNone(field(model, "parent_asset"), "sub-meter hierarchy")

    def test_us_ast_004_tc1__assignments_capture_period_and_final_read(self):
        model = table("assets", "asset_assignments")
        self.assertIsNotNone(model)
        for name in ("from_date", "to_date", "final_read_id"):
            self.assertIsNotNone(field(model, name))
        self.assertIn(
            "uq_asset_assignments_current", constraint_names(model), "one live assignment per asset"
        )

    def test_us_ast_006_tc1__maintenance_log_is_append_only_shaped(self):
        model = table("assets", "asset_maintenance")
        self.assertIsNotNone(model)
        names = {f.name for f in model._meta.fields}
        self.assertTrue({"kind", "date", "detail", "resulting_status"} <= names)
        # BR-AST-018: entries are appended; there is no updated_at to rewrite.
        self.assertNotIn("updated_at", names)

    def test_us_ast_007_tc1__retirement_is_a_status_not_a_delete(self):
        # BR-AST-031: lifecycle is DATA-DRIVEN — status points at the stage catalog
        # (so a tenant's stage set is reference data, not a hardcoded enum), and PROTECT
        # means a stage in use can never be deleted out from under its assets.
        # BR-AST-030 terminality itself is a service rule, tested in the assets lane.
        model = table("assets", "assets")
        status = field(model, "status")
        self.assertEqual(status.related_model, table("assets", "asset_lifecycle_stages"))
        self.assertEqual(status.remote_field.on_delete.__name__, "PROTECT")

    def test_us_ast_008_tc1__reassignment_uses_the_assignment_table(self):
        assignments = table("assets", "asset_assignments")
        self.assertEqual(field(assignments, "asset").related_model, table("assets", "assets"))
        self.assertEqual(field(assignments, "unit").related_model, table("metering", "units"))

    def test_us_ast_009_tc1__multiplier_and_unit_are_explicit_on_every_asset(self):
        model = table("assets", "assets")
        self.assertIsInstance(field(model, "multiplier"), models.DecimalField)
        self.assertIsNotNone(field(model, "unit"), "HR-3 consumption never unitless")

    def test_us_ast_010_tc1__import_batches_stage_rows_before_commit(self):
        batches = table("assets", "asset_import_batches")
        rows = table("assets", "asset_import_rows")
        self.assertIsNotNone(batches)
        self.assertIsNotNone(rows)
        self.assertEqual(field(rows, "batch").related_model, batches)
        self.assertIsNotNone(field(batches, "committed_at"), "staged: nothing live until commit")
        self.assertIn("uq_asset_import_rows", constraint_names(rows))


class MoneyPrecisionSweep(TestCase, MoneyColumnMixin):
    """HR-2 sweep, re-pointed at the RATIFIED precisions (DEF-519 closed).

    ⚠ **THE BAR CHANGED BY PO RE-SIGN, 2026-08-22** — verbatim: *"We already
    confirmed this - MOney 4 decimal, percentage 6 decimal , display both 2
    decimal"*. This sweep was caught between two signed statements (hard rule
    2's 18,6 vs BR-RAT-092's store-4) and RED for a day on
    `charge_code_amounts.amount`; the ruling resolved it FOR store-4. So the
    lawful precisions are: **4 decimals** for a money column (BR-RAT-092's
    `money_field`), **6** for a rate/percentage column, and the legacy (18,6)
    stays lawful as a CONTAINER for money written to 4 — the rule governs what
    is WRITTEN and what NEW columns declare, so this sweep accepts both and a
    THIRD precision goes RED.
    """

    def test_us_rat_001_tc2__all_w1_decimal_money_columns_hold_a_ratified_precision(self):
        offenders = []
        money_names = ("amount", "price", "charge", "minimum", "fee", "balance", "total")
        rate_names = ("rate",)
        for app_label in ("rating", "metering", "assets"):
            for model in apps.get_app_config(app_label).get_models():
                for f in model._meta.fields:
                    if not isinstance(f, models.DecimalField):
                        continue
                    is_money = any(token in f.name for token in money_names)
                    is_rate = any(token in f.name for token in rate_names)
                    if not (is_money or is_rate):
                        continue  # quantities/multipliers carry their own precision
                    lawful = (
                        {(18, 4), (18, 6)} if is_money
                        # a percentage/rate stores 6 (the PO's own second clause);
                        # (18,6) is both the ratified rate precision and the
                        # legacy container, so rates allow exactly one shape.
                        else {(18, 6)}
                    )
                    if (f.max_digits, f.decimal_places) not in lawful:
                        offenders.append(
                            f"{model._meta.db_table}.{f.name} "
                            f"({f.max_digits},{f.decimal_places})"
                        )
        self.assertEqual(
            offenders, [], f"columns off the RATIFIED precisions (PO 2026-08-22): {offenders}"
        )

    def test_us_rat_001_tc3__decimal_round_trip_keeps_six_places(self):
        plans = table("rating", "rate_plans")
        f = field(plans, "minimum_bill_amount")
        self.assertEqual(f.to_python("15.123456"), Decimal("15.123456"))
