# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-001 · US-CUS-003 (the SCHEMA HALF of each story's TCs — the
#           W2 customers models+migrations slice)
# Screens:  S17 · S18 · S8 (Settings → Reference data)
# Rules:    BR-CUS-012 (account attribute set) · BR-CUS-016 (stored status
#           comes from the LOOKUP, aging is derived) · BR-CUS-017 (one account
#           ↔ one unit; the ACTIVE-account half has no DB enforcement — see the
#           boundary test) · BR-CUS-055 (five seeded statuses, behaviour-class
#           mapped) · BR-CUS-045 (contact PII columns) · BR-TEN-036 (seeded,
#           tenant-extensible lookups) · HR-2 (money NUMERIC(18,6) + CHAR(3))
# Note:     Service/API halves land with the account-CRUD slice; this file
#           asserts what the SCHEMA itself must guarantee. RLS halves run in
#           the G5 isolation suite (sqlite cannot enforce RLS) —
#           tests/test_us_cus_schema_and_seed.py.
# ───────────────────────────────────────────────────────
"""W2 customers schema — the constraint/shape half, on the migrated test DB.

Same shape as tests/test_w1_models.py: it asks the migrated model registry
what the tables actually guarantee, so a column quietly dropped or a
constraint quietly renamed fails here rather than in production.
"""

from decimal import Decimal

from django.apps import apps
from django.db import models
from core.money_fields import AMOUNT_PLACES, MONEY_DIGITS, PERCENT_PLACES, RATE_PLACES
from django.test import TestCase


def table(app_label: str, db_table: str):
    """The model backing a physical table, or None when the table is absent."""
    for model in apps.get_app_config(app_label).get_models():
        if model._meta.db_table == db_table:
            return model
    return None


def constraint_names(model) -> set[str]:
    return {c.name for c in model._meta.constraints}


def index_names(model) -> set[str]:
    return {i.name for i in model._meta.indexes}


def field(model, name):
    return model._meta.get_field(name)


def has_field(model, name: str) -> bool:
    try:
        model._meta.get_field(name)
    except Exception:  # FieldDoesNotExist
        return False
    return True


class MoneyColumnMixin:
    """HR-2 / DB-3: money is NUMERIC(18,6) and never a float."""

    def assert_money(self, model, field_name: str) -> None:
        f = field(model, field_name)
        self.assertIsInstance(f, models.DecimalField, f"{field_name} must be Decimal")
        self.assertEqual(f.max_digits, 18, f"{field_name} max_digits")
        self.assertEqual(f.decimal_places, 6, f"{field_name} decimal_places")


class CustomersReferenceSchema(TestCase):
    """r5 #12 [D5] + r5 #20 / BR-CUS-055 — the three reference tables."""

    def test_po_20260917__account_types_are_tenant_scoped_with_a_per_tenant_code(self):
        """⚠ **THIS ASSERTED THE EXACT OPPOSITE UNTIL 2026-09-17 AND IS
        REWRITTEN RATHER THAN DELETED.**

        It was `..._account_types_are_a_platform_table_with_a_global_unique_code`
        and it pinned r5 #12 [D5]'s *platform-seeded* posture: NO `tenant` field,
        so no RLS policy was even possible, and `uq_account_types_code_ci` unique
        across the whole install. **The PO reversed it** — *"utility can get
        their own account types"* (`BR-CUS-1079`) — so the same case now guards
        the new posture at the same point in the file, which keeps the history
        where a reader will meet it."""
        model = table("customers", "account_types")
        self.assertIsNotNone(model, "account_types must exist")
        self.assertTrue(
            has_field(model, "tenant"),
            "account_types is the TENANT's own list since the PO ruling of "
            "2026-09-17 — a missing tenant_id would be that ruling being undone",
        )
        self.assertIn("uq_account_types_tenant_code_ci", constraint_names(model))
        self.assertNotIn(
            "uq_account_types_code_ci",
            constraint_names(model),
            "the GLOBAL unique code is what stops two utilities using one code "
            "for different things — customers.0054 drops it",
        )
        # BR-TEN-036 shape: a seeded row is deactivatable, never deletable.
        self.assertTrue(has_field(model, "is_system"))
        self.assertTrue(has_field(model, "active"))
        # BR-CUS-094's third axis, and the picker order the ruling opened.
        self.assertTrue(has_field(model, "legacy"))
        self.assertTrue(has_field(model, "sort_order"))

    def test_us_cus_003_tc1__account_subtypes_are_tenant_scoped(self):
        """r5 #12 [D5]: 'account_subtypes (tenant-defined, RLS)'."""
        model = table("customers", "account_subtypes")
        self.assertIsNotNone(model)
        self.assertTrue(has_field(model, "tenant"), "tenant-scoped per r5 #12 [D5]")
        self.assertIn("uq_account_subtypes_tenant_code_ci", constraint_names(model))

    def test_us_cus_001_tc1__account_statuses_are_a_lookup_with_a_behaviour_class(self):
        """BR-CUS-055 + BR-CUS-016: the vocabulary is a tenant-scoped, extensible
        TABLE with a behaviour class on every row — never an enum, because a
        tenant may add "Legal hold" (US-CUS-020 TC-3) and billing must still be
        able to classify it."""
        model = table("customers", "account_statuses")
        self.assertIsNotNone(model)
        self.assertTrue(has_field(model, "tenant"))
        self.assertTrue(has_field(model, "behavior_class"))
        self.assertIn("uq_account_statuses_tenant_code_ci", constraint_names(model))


class CustomersAccountSchema(TestCase, MoneyColumnMixin):
    """B2 §2 `accounts` + the addendum columns that name themselves."""

    def test_us_cus_001_tc1__accounts_carry_the_b2_column_set_and_unique_number(self):
        model = table("customers", "accounts")
        self.assertIsNotNone(model)
        # B2 §4 ux_accounts_no — unique WITHIN a tenant, never globally.
        self.assertIn("ux_accounts_no", constraint_names(model))
        # B2 §4 ix_ar_outstanding — the partial index behind Outstandings high→low.
        self.assertIn("ix_ar_outstanding", index_names(model))
        for name in (
            "unit",  # ⚠ cross-module FK → metering (B2 §2 reviewed set)
            "account_no",
            "status",
            "balance",
            "currency",
            "deposit_on_file",
            "credit_tier",
            "autopay",
            "opened_at",
            "closed_at",
        ):
            self.assertTrue(has_field(model, name), f"B2 §2 accounts.{name}")

    def test_us_cus_001_tc1__account_money_columns_are_numeric_18_6_with_char3_currency(self):
        """CLAUDE.md rule 2 / DB-3 — never float, never cents."""
        model = table("customers", "accounts")
        self.assert_money(model, "balance")
        self.assert_money(model, "deposit_on_file")
        self.assertEqual(field(model, "currency").max_length, 3, "HR-2 CHAR(3) currency")
        self.assertEqual(field(model, "currency").default, "USD")

    def test_us_cus_001_tc1__stored_status_is_a_lookup_fk_not_an_enum(self):
        """BR-CUS-016 + r5 #20: B2 §2's `status account_status` enum column is
        replaced by the lookup at this module's build wave. PROTECT is what
        makes the BR-TEN-034 delete-lock real in the database."""
        model = table("customers", "accounts")
        status = field(model, "status")
        self.assertIsInstance(status, models.ForeignKey)
        self.assertEqual(status.related_model._meta.db_table, "account_statuses")
        self.assertEqual(status.db_column, "status_id")
        self.assertEqual(status.remote_field.on_delete.__name__, "PROTECT")

    def test_us_cus_003_tc1__accounts_carry_type_subtype_and_the_finance_columns(self):
        """r5 #19 (type/sub-type) + the B2 2026-08-07 finance confirmations
        (account-level tax exemption, B4.2) + r9 #5 / r12 #8 / r12 #12 / r15 #2."""
        model = table("customers", "accounts")
        account_type = field(model, "account_type")
        self.assertEqual(account_type.related_model._meta.db_table, "account_types")
        self.assertFalse(account_type.null, "r5 #19 marks only the SUB-type NULL")
        self.assertTrue(field(model, "account_subtype").null, "r5 #19: sub-type NULL")
        for name in (
            "tax_exempt",
            "tax_exempt_ref",
            "tax_exempt_expires",
            "deposit_received_on",  # r9 #5 / BR-CUS-050
            "bad_address",  # r12 #8 / BR-PAY-018
            "nsf_count",  # r12 #12 / BR-PAY-013
            "preferred_language",  # r15 #2 / BR-CUS-064
        ):
            self.assertTrue(has_field(model, name), f"accounts.{name}")

    def test_us_cus_001_tc5__one_active_account_per_unit_has_no_database_half(self):
        """BR-CUS-017's PROPOSED enforcement is NOT built, and this test is how
        that stays visible instead of being assumed.

        The proposal is a partial unique index on
        `accounts(tenant_id, unit_id) WHERE status = 'active'`, which assumes
        `status` is B2 §2's ENUM column. r5 #20 / BR-CUS-055 make it a lookup
        FK, and a PostgreSQL partial-index predicate may name only its own
        table's columns — it cannot read `account_statuses.behavior_class`
        through the FK. So the index is not constructible as written, and this
        lane invented no substitute (a denormalized status code, or a
        predicate on `closed_at`, would each be a DIFFERENT rule).

        RULED 2026-08-10 — OQ-092 CLOSED, option (a): service-layer
        enforcement only, "no denormalised column is added — it could drift
        from the status FK and would be a second source of truth for the same
        fact." So this test does NOT flip into a constraint assertion later:
        the ruling names it as the pin that keeps the absence deliberate, and
        the rule itself is enforced (and raced) in
        apps/customers/services.py + tests/test_us_cus_003_account_race.py.
        """
        model = table("customers", "accounts")
        names = constraint_names(model) | index_names(model)
        self.assertNotIn("uq_accounts_one_active_per_unit", names)
        self.assertFalse(
            any("active" in name for name in names),
            "an active-account constraint appeared without BR-CUS-017's enforcement "
            "being decided — update this test together with the ruling",
        )


class CustomersContactSchema(TestCase):
    """B2 §2 `contacts` · `addresses` · `service_agreements`, verbatim."""

    def test_us_cus_003_tc1__contacts_carry_the_pii_column_set(self):
        """BR-CUS-045: the PII columns B2 §2 declares, no more and no fewer.
        `gov_id_last4` is last-four only (tokenized per the OQ-016 closure)."""
        model = table("customers", "contacts")
        self.assertIsNotNone(model)
        for name in ("full_name", "email", "phone", "dob", "gov_id_last4", "is_primary"):
            self.assertTrue(has_field(model, name), f"B2 §2 contacts.{name}")
        self.assertTrue(has_field(model, "deleted_at"), "B2 §2 contacts soft-delete")

    def test_us_cus_003_tc1__addresses_hang_off_the_account_with_a_kind(self):
        model = table("customers", "addresses")
        self.assertIsNotNone(model)
        self.assertEqual(field(model, "kind").default, "mailing")  # B2 §2
        self.assertTrue(has_field(model, "line1"))

    def test_us_cus_003_tc1__service_agreements_are_dated_and_carry_no_tariff(self):
        """B2 §2 shape, minus the column r16 #3 supersedes.

        `service_agreements.tariff_id` is superseded by the BR-CUS-029
        plan-assignment record, so building it would ship known-dead schema.
        Its replacement has no DDL in any signed document, so building THAT
        would be inventing law. Both refused — asserted here so the omission is
        a decision on the record, not a gap someone silently fills in."""
        model = table("customers", "service_agreements")
        self.assertIsNotNone(model)
        self.assertTrue(has_field(model, "started_on"))
        self.assertTrue(field(model, "ended_on").null, "NULL = still in force")
        self.assertFalse(
            has_field(model, "tariff"),
            "r16 #3 supersedes service_agreements.tariff_id — see the models docstring",
        )
        service_point = field(model, "service_point")
        self.assertEqual(service_point.related_model._meta.db_table, "service_points")


class W2MoneyPrecisionSweep(TestCase, MoneyColumnMixin):
    """Every decimal column the W2 customers slice adds, swept in one place.

    ⚠ **THIS SWEEP DEMANDED `(18,6)` EXACTLY UNTIL 2026-08-24, AND BY THEN THAT
    WAS THE SUPERSEDED RULE — SO IT REPORTED SIX CORRECT COLUMNS AS OFFENDERS.**
    Reported by the PO, in these words: *"An old sweep still asserts 18,6 and
    flags the new bucket column, which is correct under the new rule."*

    The rule it was written under is gone. PO re-sign 2026-08-22, verbatim:
    *"We already confirmed this - MOney 4 decimal, percentage 6 decimal ,
    display both 2 decimal"* — so an AMOUNT declares four places, a PERCENT six,
    and the pre-existing `(18,6)` amount columns stay lawful CONTAINERS because
    the rule governs what is WRITTEN and what NEW columns declare.

    The six it was flagging are every one of them right:
    `account_opening_buckets.amount`, `service_requests.fee_quoted` /
    `.fee_collected`, and `service_request_fees.quantity` / `.unit_amount` /
    `.amount` — the first declared `(18,4)` by hand and the rest through
    `core.money_fields.money_field()`, which IS the ratified helper.

    ⚠ **A STALE CHECK IS WORSE THAN A MISSING ONE.** It does not merely fail to
    help: it argues for the superseded rule with a gate's authority, and the
    obvious way to make it pass is to widen six correct columns back to six
    places. Its red also normalises — this test is one of the branch's standing
    failures (DEF-665), so every real regression it might have caught since the
    re-sign was hidden behind a failure everybody had learned to skip.

    **The fix is not a wider literal — it is no literal at all.** The lawful
    shapes now come from `core.money_fields`, the same module the columns
    themselves are declared through, so this sweep cannot disagree with the rule
    again without the rule's own constants moving. That is the difference
    between fixing this instance and closing the class.

    `W1`'s twin sweep (`test_w1_models.py`) was amended for the re-sign and this
    one was not, which is how a rule reaches one document and not its neighbour.
    """

    def test_us_cus_001_tc2__all_w2_decimal_money_columns_hold_a_ratified_precision(self):
        #: PERCENT and RATE are both six; an AMOUNT is four, and (18,6) stays
        #: lawful for the amount columns that predate the re-sign.
        lawful = {
            (MONEY_DIGITS, AMOUNT_PLACES),
            (MONEY_DIGITS, PERCENT_PLACES),
            (MONEY_DIGITS, RATE_PLACES),
        }
        offenders = []
        for model in apps.get_app_config("customers").get_models():
            for f in model._meta.get_fields():
                if isinstance(f, models.DecimalField):
                    shape = (f.max_digits, f.decimal_places)
                    if shape not in lawful:
                        offenders.append(f"{model._meta.db_table}.{f.name} {shape}")
        self.assertEqual(
            offenders,
            [],
            f"columns off the RATIFIED precisions (PO re-sign 2026-08-22): {offenders}",
        )

    def test_us_cus_001_tc3__decimal_round_trip_keeps_six_places(self):
        """A Decimal in is a Decimal out — no float ever enters the path."""
        model = table("customers", "accounts")
        f = field(model, "balance")
        value = Decimal("1234.567891")
        self.assertEqual(f.to_python(value), value)
        self.assertIsInstance(f.to_python(value), Decimal)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-001@a2e1d59 (story+rules snapshot — EP-CUS-01 lead story; co-packets EP-CUS-02@bbed56d · customers 02-business-rules@f125a9c)
# generated: 2026-08-10 by story-coder (W2 customers SCHEMA + SEAM slice)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half in this slice) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests/test_w2_models.py✔ · run_gates 14-PASS/0-FAIL/1-SKIP✔
# exceptions: TC-5 asserts the ABSENCE of BR-CUS-017's enforcement rather than its presence — the proposed partial index is not constructible once status is a lookup FK, and pinning the absence is how the gap stays visible until the PO/Eng-Lead rule on it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
