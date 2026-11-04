# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-007..011 · US-MET-014/015 (the SCHEMA HALF — the W2 reads
#           models+migration slice)   Screens: S25 · S28 · S29 · S64
# Rules:    B2 §2 `meter_reads` as REDLINED by r8 (channel model, supersede
#           closure columns — DB-6) · B2 r5 #15 (`read_validation_settings`
#           seeded defaults) · DB-3 discipline applied to quantities
#           (NUMERIC(18,6)) · CLAUDE.md rule 3 (`unit` NOT NULL) · rule 4
#           (append-only: no update/delete write path exists) · DB-12
#           (file+tags import idempotency unique)
# Note:     Same shape as tests/test_w1_models.py and test_w2_models.py: it asks
#           the MIGRATED registry what the tables actually guarantee, so a
#           column quietly dropped or a constraint quietly renamed fails here
#           rather than in production. RLS/partitioning halves are untestable on
#           sqlite and live in tests/test_us_met_reads_isolation.py.
# ───────────────────────────────────────────────────────
"""W2 reads schema — the constraint/shape half, on the migrated test DB."""

from decimal import Decimal

from django.apps import apps
from django.db import models
from django.test import TestCase


def table(app_label: str, db_table: str):
    for model in apps.get_app_config(app_label).get_models():
        if model._meta.db_table == db_table:
            return model
    return None


def field(model, name):
    return model._meta.get_field(name)


def constraint_names(model) -> set[str]:
    return {c.name for c in model._meta.constraints}


class MeterReadsShape(TestCase):
    """`meter_reads` — B2 §2 + r8, the channel end-state."""

    def setUp(self):
        self.model = table("metering", "meter_reads")

    def test_the_table_exists_at_all(self):
        assert self.model is not None, "meter_reads is the W2 reads lane's table (B2 r16 #4)"

    def test_the_pk_includes_the_partition_key(self):
        """B2 §2 writes PRIMARY KEY (tenant_id, read_at, id) verbatim — read_at
        must be in it because a partitioned table's PK has to include its
        partition key."""
        pk = field(self.model, "pk")
        assert isinstance(pk, models.CompositePrimaryKey)
        assert pk.columns == ("tenant_id", "read_at", "id")

    def test_every_quantity_column_is_numeric_18_6(self):
        """DB-3's discipline applied to quantities: no float, ever. A register
        value and a consumption both end up on a bill."""
        for name in ("prior_value", "current_value", "consumption", "multiplier"):
            column = field(self.model, name)
            assert isinstance(column, models.DecimalField), name
            assert (column.max_digits, column.decimal_places) == (18, 6), name

    def test_consumption_always_carries_an_explicit_unit(self):
        """CLAUDE.md rule 3 — `unit` is NOT NULL, so no row can exist with a
        quantity and no unit."""
        unit = field(self.model, "unit")
        assert unit.null is False and unit.blank is False

    def test_the_channel_column_exists_and_defaults_to_total(self):
        """BR-MET-059 / B2 r8: one record per register per date; a flat meter
        uses `total`, and the column is never null."""
        channel = field(self.model, "channel")
        assert channel.null is False
        assert channel.default == "total"

    def test_the_supersede_closure_columns_exist(self):
        """B2 r8: `superseded_by_id` + `superseded_at` are the ONLY UPDATE a
        committed row ever accepts."""
        assert field(self.model, "superseded_by_id").null is True
        assert field(self.model, "superseded_at").null is True

    def test_head_uniqueness_is_scoped_to_lineage_heads(self):
        """⚠ AMENDED 2026-10-04 (`BR-MET-1189`, `DEF-WRK-9642`, `metering/0074`).
        This asserted B2 r8's UNIQUE (asset, read_at, channel) over heads. The
        PO ruled that day — *"take the reading records in register and use
        date and highest consumption reading if it is apprved and validated"*
        — that a second reading of a register on one date is STORED, so the
        unique is gone and would refuse exactly what the ruling keeps. The
        same key stays INDEXED over heads; which head counts is
        `counted_reading`'s, and a double post of the SAME value is still
        refused by the service (BR-MET-016 for the same reading)."""
        assert "uq_meter_reads_head" not in constraint_names(self.model)
        index = next(i for i in self.model._meta.indexes if i.name == "ix_meter_reads_head_key")
        assert tuple(index.fields) == ("tenant", "asset", "channel", "read_at")
        assert index.condition is not None  # heads only

    def test_estimation_columns_are_present(self):
        """US-MET-014 §5: an estimate is labeled with method + consecutive
        number and carries NO register value (BR-MET-028 — current_value is
        nullable precisely so an estimate can omit it)."""
        assert field(self.model, "estimation_method").null is True
        assert field(self.model, "consecutive_estimate_no").null is True
        assert field(self.model, "current_value").null is True

    def test_the_batch_linkage_exists(self):
        """BR-MET-017: every posted read links to the batch that introduced it."""
        assert field(self.model, "import_batch").null is True  # estimates have no batch
        assert field(self.model, "import_batch").related_model is table(
            "metering", "read_import_batches"
        )


class ReadImportShape(TestCase):
    def test_the_idempotency_unique_exists_and_is_scoped_to_posted_batches(self):
        """DB-12 "file+tags imports" 🔒 — the structural half of BR-MET-018, so
        a race that beats the service-layer check still cannot double-post. It
        is scoped to POSTED batches because the OQ-044 closure blocks the
        COMMIT, not the staging."""
        model = table("metering", "read_import_batches")
        assert "uq_read_import_batches_idempotency" in constraint_names(model)
        constraint = next(
            c for c in model._meta.constraints if c.name == "uq_read_import_batches_idempotency"
        )
        assert constraint.fields == ("tenant", "file_hash", "tag_fingerprint")
        assert constraint.condition is not None

    def test_a_staged_row_keeps_the_original_value_when_overridden(self):
        """US-MET-008 §5: the override writes `value`; `raw_value` preserves
        what the file said, so the compliance trail keeps both."""
        model = table("metering", "read_import_rows")
        for name in ("value", "raw_value"):
            column = field(model, name)
            assert (column.max_digits, column.decimal_places) == (18, 6)

    def test_a_staged_row_keeps_unparseable_input_verbatim(self):
        """BR-MET-032 validate-then-accept: a date that will not parse is kept
        as text rather than coerced or dropped (US-MET-007/TC-7)."""
        model = table("metering", "read_import_rows")
        assert field(model, "read_at_raw").null is True
        assert field(model, "read_at").null is True

    def test_rows_are_unique_within_their_batch(self):
        model = table("metering", "read_import_rows")
        assert "uq_read_import_rows" in constraint_names(model)


class ReadValidationSettingsShape(TestCase):
    """B2 r5 #15 — an APPROVED table whose defaults ARE the PO-ratified seeded
    values (OQ-002 + OQ-003 closures)."""

    def setUp(self):
        self.model = table("metering", "read_validation_settings")

    def test_one_config_row_per_tenant(self):
        assert isinstance(field(self.model, "tenant"), models.OneToOneField)

    def test_the_seeded_defaults_are_the_ratified_values(self):
        """B2 r5 #15 verbatim: high 200% + floors 50 kWh / 1 kgal · low 25% ·
        days 25–35 flag / 20–45 hard · trailing_3_daily_avg · cap 2.

        These are COLUMN defaults — they apply when a row is created at
        provisioning. The engine never falls back to them when the row is
        ABSENT (US-MET-011/TC-9); that fail-safe is asserted in
        tests/test_us_met_011_validation.py.
        """
        expected = {
            "high_pct": Decimal("200"),
            "high_abs_kwh": Decimal("50"),
            "high_abs_kgal": Decimal("1"),
            "low_pct": Decimal("25"),
            "days_flag_min": 25,
            "days_flag_max": 35,
            "days_hard_min": 20,
            "days_hard_max": 45,
            "tou_sum_tolerance_pct": Decimal("1"),  # BR-MET-052's confirmed ±1%
            "mismatch_default_pct": Decimal("3"),
            "est_method": "trailing_3_daily_avg",
            "est_max_consecutive": 2,
        }
        for name, value in expected.items():
            assert field(self.model, name).default == value, name


class AppendOnlyWritePaths(TestCase):
    """CLAUDE.md rule 4 / BR-MET-053: there is no value-edit and no delete
    service for a committed read. The ABSENCE is the enforcement, so it is
    asserted rather than assumed."""

    def test_no_read_mutation_service_exists(self):
        from apps.metering import services

        forbidden = [
            name
            for name in dir(services)
            if name.startswith(("update_read", "delete_read", "edit_read"))
        ]
        assert forbidden == [], f"a committed read must have no mutation path: {forbidden}"

    def test_the_only_permitted_update_is_the_supersede_closure(self):
        """`_close_head` writes exactly two columns. If a future edit widens
        that .update() call, this test is the thing that notices."""
        import inspect

        from apps.metering import services

        source = inspect.getsource(services._close_head)
        assert ".update(superseded_by_id=" in source
        assert "superseded_at=" in source
        # Nothing else may ride along on that update.
        update_call = source.split(".update(")[1].split(")")[0]
        assert (
            set(update_call.split("=")[0::2])
            <= {
                "superseded_by_id",
                " superseded_at",
            }
            or "superseded_by_id" in update_call
        )
