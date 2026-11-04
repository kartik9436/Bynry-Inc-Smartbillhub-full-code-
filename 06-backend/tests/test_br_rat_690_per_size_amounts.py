# ── Trace ──────────────────────────────────────────────
# Rules:   BR-RAT-690 (DEF-2190 — `charge_code_amounts` gets a writer, and a
#          size must be one the tenant configured) · BR-RAT-088 (the CHARGE
#          CODE owns the base; its own worked example is 5/8" $8.00 vs 2"
#          $34.00 on ONE code) · BR-RAT-089/092 (an AMOUNT is stored to four
#          places and displayed at two) · BR-TEN-031/170 (`service_size_classes`
#          is the tenant's own configured list) · CR-013 part 2 ("a code has
#          ONE basis") · CLAUDE.md hard rules 1 (tenant scoping), 2 (money),
#          7 (every money action writes audit_log)
# Defects: DEF-2190 (this file closes it) · DEF-277 (blank is not zero) ·
#          DEF-431 (the read half, already shipped)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""BR-RAT-690 — A UTILITY CAN CHARGE $8.00 FOR A 5/8" AND $34.00 FOR A 2".

WHAT WAS WRONG, WITH THE FIGURES
---------------------------------
`BR-RAT-088` (CONFIRMED, PO 2026-08-20) moved the base amount onto the charge
code and worked its example on a water base that DIFFERS by connection size —
a 5/8" at **$8.00** and a 2" at **$34.00**. `charge_code_amounts` shipped with
a model, a migration and four readers and **no writer at any layer**:
`CHARGE_FIELDS` carried no key for it, so `POST /charges` and `PATCH
/charges/{id}` refused the field by name and nothing else could write it.

So every connection, whatever its size, was billed the single scalar in
`charges.amount`. On that example a 2" connection is billed **$8.00** where the
utility means **$34.00** — **$26.00 a month short, per 2" connection**, and no
test anywhere could see it, because with the table EMPTY a per-size read and a
scalar read agree for every tenant.

THE THREE STATES, WHICH ARE THE WHOLE JOB (DEF-277)
----------------------------------------------------
`DEF-277` was filed for a base *"coerced to 0.00 using `or` rather than `is
None`, so an omitted base, an absent size and a deliberately-typed zero are
indistinguishable"*. TC3, TC4 and TC5 hold them apart end to end:

    no row for the size   nobody priced it        R4 refuses by name
    a row, amount NULL    NOT SERVED              R4 refuses by name
    a row, amount 0.0000  served, FREE            bills a $0.00 line

TC7 is the one that would have caught the original defect: it asserts the write
path exists at all, by round-tripping through `create_charge` rather than by
writing the model directly — which is how the table came to have a test and no
writer.
"""

from decimal import Decimal

import pytest

from apps.rating import models, selectors, services
from core import errors
from core.money_fields import AMOUNT_PLACES

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import audit_actions, tenant_ctx

pytestmark = pytest.mark.django_db


#: BR-TEN-171's own ratified water codes and names, three of the nine.
WATER_SIZES = (("W-58", 'Water 5/8"'), ("W-2", 'Water 2"'), ("W-4", 'Water 4"'))


def _configure_sizes(tenant, rows=WATER_SIZES, active=True):
    """The tenant's own `service_size_classes` rows.

    Written through tenancy's MODEL rather than rating's service layer on
    purpose: rating may not write another module's tables (B1/B8), and the
    point of the test is that rating READS this list.
    """
    from apps.tenancy import models as tenancy_models

    for code, name in rows:
        tenancy_models.MeterSizeClass.objects.update_or_create(
            tenant=tenant,
            code=code,
            defaults={"name": name, "active": active, "is_system": True},
        )


def _base_payload(**overrides):
    payload = {
        "code": "BASE-W",
        "name": "Water base service",
        "charge_type": "recurring",
        "service": "water",
        "amount_rule": "flat",
        "is_base": True,
    }
    payload.update(overrides)
    return payload


def _rows(tenant, charge_id):
    """The served `size_amounts`, keyed by size. Opens its own tenant context —
    `charge_row` is tenant-scoped and refuses without one (hard rule 1)."""
    with tenant_ctx(tenant):
        return {
            row["size_class"]: row
            for row in selectors.charge_row(models.Charge.objects.get(id=charge_id))[
                "size_amounts"
            ]
        }


# ── TC1 — the two figures the whole lane exists for ─────────────────────────
def test_tc1__one_code_prices_a_5_8_inch_at_8_and_a_2_inch_at_34(env):
    """BR-RAT-088's own worked example, expressible for the first time."""
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        charge = services.create_charge(
            env.admin,
            {**(_base_payload(
                size_amounts=[
                    {"size_class": "W-58", "amount": "8.00"},
                    {"size_class": "W-2", "amount": "34.00"},
                ]
            )), "effective_from": "2000-01-01"},
        )
    rows = _rows(env.tenant, charge["id"])
    # DISPLAYED at two (BR-RAT-089: *"deplay on screen is 2 decimal places"*).
    assert rows["W-58"]["amount_display"] == "8.00"
    assert rows["W-2"]["amount_display"] == "34.00"
    # STORED to four (BR-RAT-092, `core.money_fields.AMOUNT_PLACES`), asserted
    # on the COLUMN rather than on the served string: `selectors._money` pads
    # every rating money value to six places by construction, so it serves
    # `8.000000` for a four-place column. Same number, wider string — DEF-2281.
    with tenant_ctx(env.tenant):
        stored = {
            row.size_class: row.amount
            for row in models.ChargeCodeAmount.objects.filter(charge_id=charge["id"])
        }
    assert stored["W-58"].as_tuple().exponent == -AMOUNT_PLACES
    assert stored["W-58"] == Decimal("8.0000")
    assert stored["W-2"] == Decimal("34.0000")
    # $26.00 a month is the difference the table exists to express.
    assert stored["W-2"] - stored["W-58"] == Decimal("26.0000")


# ── TC2 — hard rule 7: the money action is audited, per-size rows included ──
def test_tc2__the_per_size_amounts_are_in_the_audit_row(env, audit_rows):
    _configure_sizes(env.tenant)
    audit_rows.clear()
    with tenant_ctx(env.tenant):
        services.create_charge(
            env.admin,
            {**(_base_payload(size_amounts=[{"size_class": "W-58", "amount": "8.00"}])), "effective_from": "2000-01-01"},
        )
    assert "charge.created" in audit_actions(audit_rows)
    after = next(row for row in audit_rows if row["action"] == "charge.created")["after"]
    assert [(row["size_class"], row["amount_display"]) for row in after["size_amounts"]] == [
        ("W-58", "8.00")
    ]
    assert Decimal(after["size_amounts"][0]["amount"]) == Decimal("8.00")


# ── TC3/TC4/TC5 — DEF-277's three states stay three ─────────────────────────
def test_tc3__a_blank_amount_stores_NULL_and_never_zero(env):
    """A row that exists with no amount says the utility does NOT SERVE this
    size. R4 refuses rather than billing $0.00 for it."""
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        charge = services.create_charge(
            env.admin,
            {**(_base_payload(
                size_amounts=[
                    {"size_class": "W-58", "amount": "8.00"},
                    {"size_class": "W-4", "amount": None},
                ]
            )), "effective_from": "2000-01-01"},
        )
        stored = models.ChargeCodeAmount.objects.get(
            tenant_id=env.tenant.id, charge_id=charge["id"], size_class="W-4"
        )
    assert stored.amount is None  # not Decimal("0") — the DEF-277 coercion
    assert _rows(env.tenant, charge["id"])["W-4"]["amount"] is None
    assert _rows(env.tenant, charge["id"])["W-4"]["amount_display"] is None


def test_tc4__an_empty_string_is_the_same_answer_as_null_not_a_bad_number(env):
    """A screen posts `""` for an empty box. It must mean NOT SERVED, not
    "enter a number" — otherwise the middle state is unsayable from the UI."""
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        charge = services.create_charge(
            env.admin,
            {**(_base_payload(size_amounts=[{"size_class": "W-4", "amount": ""}])), "effective_from": "2000-01-01"},
        )
    assert _rows(env.tenant, charge["id"])["W-4"]["amount"] is None


def test_tc5__a_typed_zero_is_a_PRICE_and_stays_zero(env):
    """`0.00` means served FREE and bills a $0.00 line. It is not an absence."""
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        charge = services.create_charge(
            env.admin,
            {**(_base_payload(size_amounts=[{"size_class": "W-58", "amount": "0.00"}])), "effective_from": "2000-01-01"},
        )
    row = _rows(env.tenant, charge["id"])["W-58"]
    assert row["amount"] is not None  # a PRICE, not an absence
    assert Decimal(row["amount"]) == Decimal("0")
    assert row["amount_display"] == "0.00"


# ── TC6 — a size must be one the tenant configured ──────────────────────────
def test_tc6__a_size_the_tenant_never_configured_is_refused_by_name(env):
    """A typed `W58` where the tenant configured `W-58` would store a row
    nothing ever looks up: the meter resolves `W-58`, R4 finds no amount, and
    the bill refuses for a base the utility believes it set."""
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_charge(
                env.admin,
                {**(_base_payload(size_amounts=[{"size_class": "W58", "amount": "8.00"}])), "effective_from": "2000-01-01"},
            )
    assert caught.value.message_key == "rating.charges.unknown_size_class"
    assert caught.value.params["size_class"] == "W58"


def test_tc6b__a_size_settings_has_RETIRED_still_saves_on_a_code_that_priced_it(env):
    """`ChargeCodeAmount`'s own rule: *"a size Settings RETIRES must not vanish
    from a schedule that already priced it"*. Deactivating a size must not make
    a charge code that already carries it unsaveable."""
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        charge = services.create_charge(
            env.admin,
            {**(_base_payload(size_amounts=[{"size_class": "W-2", "amount": "34.00"}])), "effective_from": "2000-01-01"},
        )
    _configure_sizes(env.tenant, rows=(("W-2", 'Water 2"'),), active=False)
    with tenant_ctx(env.tenant):
        saved = services.update_charge(
            env.admin,
            charge["id"],
            {"name": "Water base service (renamed)", "size_amounts": [
                {"size_class": "W-2", "amount": "34.00"}
            ], "effective_from": "2000-01-01"},
        )
    assert saved["size_amounts"][0]["amount_display"] == "34.00"


# ── TC7 — the write path exists AT ALL, through the validated door ──────────
def test_tc7__the_field_reaches_the_service_layer_and_is_not_rejected_as_unknown(env):
    """DEF-2190 itself: `CHARGE_FIELDS` had no `size_amounts`, so every post of
    it was refused as an unknown field and the table could only be written by a
    test reaching past the service layer."""
    assert "size_amounts" in services.CHARGE_FIELDS
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        charge = services.create_charge(
            env.admin,
            {**(_base_payload(size_amounts=[{"size_class": "W-58", "amount": "8.00"}])), "effective_from": "2000-01-01"},
        )
        assert (
            models.ChargeCodeAmount.objects.filter(
                tenant_id=env.tenant.id, charge_id=charge["id"]
            ).count()
            == 1
        )


# ── TC8 — one basis (CR-013 part 2), refused where a person can still fix it ─
def test_tc8__a_code_may_not_state_both_a_flat_amount_and_a_per_size_table(env):
    """`resolve_charge_codes` refuses this combination ON BILLING DAY —
    *"CR-013 part 2 gives a code one basis; this chain refuses rather than
    choosing which figure the customer is billed"*. Refusing it at the write is
    the same law at the moment somebody can still act on it, and it closes the
    adapter's silent preference for the table."""
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_charge(
                env.admin,
                {**(_base_payload(
                    amount="12.00",
                    size_amounts=[{"size_class": "W-58", "amount": "8.00"}],
                )), "effective_from": "2000-01-01"},
            )
    assert caught.value.message_key == "rating.charges.amount_and_size_table"


def test_tc8b__a_flat_code_with_a_per_size_table_needs_no_scalar_amount(env):
    """The per-size table IS the flat rule's amount, stated once per size."""
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        charge = services.create_charge(
            env.admin,
            {**(_base_payload(size_amounts=[{"size_class": "W-58", "amount": "8.00"}])), "effective_from": "2000-01-01"},
        )
    assert charge["amount"] is None


def test_tc8c__a_flat_code_with_neither_is_still_refused(env):
    """The rule that was there before is untouched: a flat code has to state
    SOME amount."""
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_charge(env.admin, {**(_base_payload()), "effective_from": "2000-01-01"})
    assert caught.value.field_errors[0]["field"] == "amount"


# ── TC9 — replace-the-whole-set, and ABSENT is not EMPTY ────────────────────
def test_tc9__an_empty_list_clears_the_table_and_an_absent_key_leaves_it(env):
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        charge = services.create_charge(
            env.admin,
            {**(_base_payload(
                size_amounts=[
                    {"size_class": "W-58", "amount": "8.00"},
                    {"size_class": "W-2", "amount": "34.00"},
                ]
            )), "effective_from": "2000-01-01"},
        )
    # A payload with NO `size_amounts` key leaves the stored rows alone — the
    # posture `gl_account_id` takes, and the reason it takes it.
    with tenant_ctx(env.tenant):
        services.update_charge(env.admin, charge["id"], {"name": "Renamed", "effective_from": "2000-01-01"})
    assert len(_rows(env.tenant, charge["id"])) == 2

    # Dropping one row on screen actually removes it: the server replaces the
    # whole set, so an omitted row is a deletion and not a silent keep.
    with tenant_ctx(env.tenant):
        services.update_charge(
            env.admin,
            charge["id"],
            {"size_amounts": [{"size_class": "W-58", "amount": "8.00"}], "effective_from": "2000-01-01"},
        )
    assert set(_rows(env.tenant, charge["id"])) == {"W-58"}

    # An explicit empty list is "this code no longer varies by size", and the
    # single amount becomes lawful again in the same call.
    with tenant_ctx(env.tenant):
        saved = services.update_charge(
            env.admin, charge["id"], {"size_amounts": [], "amount": "12.00", "effective_from": "2000-01-01"}
        )
    assert _rows(env.tenant, charge["id"]) == {}
    assert saved["amount_display"] == "12.00"


def test_tc10__the_same_size_twice_is_refused_rather_than_raising_a_500(env):
    """`uq_charge_code_amounts_tenant_charge_size` would answer HTTP 500."""
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_charge(
                env.admin,
                {**(_base_payload(
                    size_amounts=[
                        {"size_class": "W-58", "amount": "8.00"},
                        {"size_class": "W-58", "amount": "9.00"},
                    ]
                )), "effective_from": "2000-01-01"},
            )
    assert caught.value.message_key == "rating.size_rows.duplicate_size"


# ── TC11 — hard rule 1: the rows are the TENANT's ───────────────────────────
def test_tc11__another_tenants_configured_size_is_not_offered_here(env, other_env):
    """The allowed set is THIS tenant's own list (hard rule 1).

    ⚠ The code is a made-up one, and it has to be: a provisioned tenant is
    seeded with BR-TEN-171's whole ratified table, so every real water size is
    configured for BOTH tenants and no ratified code could tell the two lists
    apart. A tenant-added size is the only thing that can.
    """
    _configure_sizes(other_env.tenant, rows=(("W-COOP", "Co-op private main"),))
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_charge(
                env.admin,
                {**(_base_payload(size_amounts=[{"size_class": "W-COOP", "amount": "60.00"}])), "effective_from": "2000-01-01"},
            )
    assert caught.value.message_key == "rating.charges.unknown_size_class"
    # …and the OTHER tenant, which really did configure it, may use it.
    with tenant_ctx(other_env.tenant):
        saved = services.create_charge(
            other_env.admin,
            {**(_base_payload(size_amounts=[{"size_class": "W-COOP", "amount": "60.00"}])), "effective_from": "2000-01-01"},
        )
    assert saved["size_amounts"][0]["amount_display"] == "60.00"


def test_tc11b__the_rows_written_carry_this_tenants_id(env):
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        charge = services.create_charge(
            env.admin,
            {**(_base_payload(size_amounts=[{"size_class": "W-58", "amount": "8.00"}])), "effective_from": "2000-01-01"},
        )
        row = models.ChargeCodeAmount.objects.get(charge_id=charge["id"])
    assert row.tenant_id == env.tenant.id
    assert row.currency == "USD"  # CHAR(3), never a float and never cents


# ── TC12 — a priced code can still be lawfully removed ──────────────────────
def test_tc12__deleting_a_never_referenced_code_takes_its_size_rows_with_it(env):
    """`ChargeCodeAmount.charge` is `on_delete=PROTECT`, so without this the
    write path above would have made a lawful zero-reference delete answer 500.
    """
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        charge = services.create_charge(
            env.admin,
            {**(_base_payload(size_amounts=[{"size_class": "W-58", "amount": "8.00"}])), "effective_from": "2000-01-01"},
        )
        services.delete_charge(env.admin, charge["id"])
        assert models.ChargeCodeAmount.objects.filter(charge_id=charge["id"]).count() == 0
        assert models.Charge.objects.filter(id=charge["id"]).count() == 0


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2190 · BR-RAT-088 · BR-RAT-690 · CR-013 part 2 · DEF-277
# generated: 2026-08-28
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest✔ ruff✔ black✔
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
