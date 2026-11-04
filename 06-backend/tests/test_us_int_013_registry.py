# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-013 (EP-INT-05) — the manifest registry. US-INT-018 TC-3 (zero
#           operations refused). Screens: S8
# Rules:    BR-INT-037 · BR-INT-028 · BR-INT-001 · BR-INT-030 · BR-INT-033 ·
#           BR-INT-043 · BR-INT-053 · CR-069 §13 gate 3
# Tests:    this file — TC-1 (through the API, every card not_set_up),
#           TC-2, TC-3, TC-4, TC-6, TC-7 (isolation through the API); TC-5 is
#           the gate 10-scripts/gates/g77_provider_key_branches.py
# Impacts:  apps/integrations/registry.py · manifests/ · apps.py · selectors.py
# ───────────────────────────────────────────────────────
"""US-INT-013 — a provider is one declarative object, refused at load if wrong.

The registry reads nothing and calls nothing, so most of these cases need no
database: they build a manifest, hand it to a fresh `Registry`, and read the
refusal's words. The two that go through `GET /integrations` (TC-1, TC-7) use
the shared two-tenant fixtures and run under each tenant's own context.
"""

import dataclasses

import pytest

from apps.integrations import api as integrations_api
from apps.integrations import manifests, registry
from apps.integrations.registry import (
    Auth,
    Conformance,
    Disposition,
    Field,
    Idempotency,
    ManifestError,
    Operation,
    Registry,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_ten_helpers import api_call

#: ⚠ **EIGHTEEN SINCE 2026-09-05, AND THE NUMBER IS ASSERTED ON PURPOSE.**
#: `US-INT-013` §4 lists seventeen and the grid draws what is registered, so a
#: provider added without a line here goes RED rather than quietly appearing on
#: every tenant's Settings screen.
#:
#: ⚠ **EIGHTEEN UNTIL `CR-110-BRC04` (2026-09-16).** The Integration Blueprint
#: draws twenty-eight and numbers them in its own catalogue (p161–p162), so the
#: count and the ORDER both moved: ten files were added, four keys retired, and
#: thirteen of the ten additions came out of splitting four manifests we already
#: had. The order below is the blueprint's, because under B14 rule 42 the drawing
#: owns the layout and this list IS what a clerk sees on Settings.
#:
#: ⚠ The full accounting of what became what lives in
#: `tests/test_cr110_connectors.py`, which also asserts the four retired keys are
#: GONE — a split being undone by accident is the failure this list cannot see.
#:
#: ⚠ **28 → 29 ON 2026-09-17, AND THE ONE IS `pay_invoicecloud_partner`**
#: (`CR-111-BRC04`, `DEF-INT-5574`, PO ruling of that date). It is the FIRST row
#: the blueprint's catalogue does not draw — InvoiceCloud runs in both directions
#: and a manifest declares ONE `auth.mode`, so the reading half is a second row
#: beside the card one. It sits at position 11, immediately after
#: `pay_invoicecloud`, because this list IS the order a clerk sees and two rows
#: with one company name have to be adjacent to read as one relationship.
#: ⚠ **Two rows is an accommodation of a product limitation and NOT the design**
#: — `BR-INT-072`.
#: ⚠ **29 → 30 ON 2026-09-17** (`CR-115-BRC05`). The one connector is
#: `postmark`: the blueprint draws ONE unnamed *Bulk email service* at row 04,
#: the PO named two ESPs and both accounts exist, so row 04 became `sendgrid`
#: and `postmark` sits beside it. **A RENAME IS NOT AN ARRIVAL** — only
#: `postmark` moves this number.
#: ⚠ **30 → 31 ON 2026-09-22** (`CR-132-BRC07`). The one connector is
#: `erp_newworld` — Tyler's New World / Logos, a sixth named ERP, for a real
#: municipal utility going live on it. One manifest file and no screen code.
SHIPPED_PROVIDERS = 31


def _op(**overrides):
    base = dict(
        name="send_message",
        label="Send messages",
        direction="out",
        initiative="us",
        transport="https",
        trigger="dispatcher",
        idempotency=Idempotency(mode="refuse", source="queue_row_id"),
        completion="immediate",
        # `CR-110-BRC04` — every operation names its ceiling or the registry
        # refuses it at load. A fixture needs one for the same reason a
        # manifest does: it is a guard, and there is no default.
        rate_limit_per_minute=60,
    )
    base.update(overrides)
    return Operation(**base)


def _manifest(**overrides):
    base = dict(
        key="example_provider",
        category="email",
        display_name="Example",
        summary="One sentence.",
        auth=Auth(mode="we_hold_theirs", placement="header"),
        # `DEF-INT-5488` / `CR-110-BRC04` — an operation WE dial names the
        # config field holding its address, and the registry now refuses a
        # name that resolves to nothing. A fixture declares one for the same
        # reason a manifest does.
        fields=(Field(name="base_url", label="Service address", kind="host"),),
        operations=(_op(),),
    )
    base.update(overrides)
    return registry.Manifest(**base)


# ── the twenty-nine, as shipped ─────────────────────────────────────────────


def test_us_int_013_the_shipped_manifests_are_in_seed_order():
    """⚠ **THE NUMBER CAME OUT OF THIS CASE'S NAME ON 2026-09-17.** It read
    `…_are_eighteen_in_seed_order` while `SHIPPED_PROVIDERS` had been 28 since
    2026-09-16 and is 29 today — a name that had been wrong for a day and would
    be wrong again on the next connector, which is a test named after an
    assertion it does not make (hard-won law 7). The count lives in
    `SHIPPED_PROVIDERS` and in the list below; the name says what the case is
    FOR, which is the ORDER."""
    keys = [one.key for one in manifests.MANIFESTS]
    assert len(keys) == SHIPPED_PROVIDERS
    assert keys == [
        "email_microsoft",
        "email_google",
        "email_smtp",
        "sendgrid",
        "postmark",
        "sms_twilio",
        "meters_neptune360",
        "meters_badger",
        "meters_itron",
        "meters_sensus",
        "pay_invoicecloud",
        # ⚠ **THE TWENTY-NINTH, AND IT IS HERE RATHER THAN AT THE END.** See
        # `SHIPPED_PROVIDERS` above and `BR-INT-072`.
        "pay_invoicecloud_partner",
        "pay_paymentus",
        "pay_uspayments",
        "pay_worldpay",
        "pay_globalpayments",
        "payments_kiosk",
        "payments_sandbox",
        "erp_aclarian",
        "erp_workday",
        "erp_sap",
        "erp_infor",
        "erp_msgp",
        # ⚠ **`erp_newworld` — CR-132-BRC07, 2026-09-22.** A sixth named ERP,
        # appended after the five `gl_partner` was split into, nothing
        # renumbered. The seed order IS what a clerk sees on Settings.
        "erp_newworld",
        "accounting_file",
        "bank_lockbox_file",
        "print_vendor",
        "gis_esri",
        "geocoder_census",
        "map_tiles_public",
        "sso",
    ]


def test_us_int_013_every_shipped_manifest_registers_on_a_fresh_registry():
    fresh = manifests.register_all(Registry())
    assert len(fresh) == SHIPPED_PROVIDERS
    # register_all is idempotent for identical declarations (ready() + tests).
    assert len(manifests.register_all(fresh)) == SHIPPED_PROVIDERS


def test_us_int_013_the_process_registry_was_filled_at_ready():
    """apps.py registered them when Django started this test process."""
    assert registry.REGISTRY.keys() == [one.key for one in manifests.MANIFESTS]


def test_us_int_013_the_kiosk_has_three_operations_and_neptune_sixteen():
    kiosk = registry.REGISTRY.require("payments_kiosk")
    assert [one.label for one in kiosk.operations] == ["Payments", "Account lookup", "Returns"]
    assert len(registry.REGISTRY.require("meters_neptune360").operations) == 16


def test_us_int_013_the_coming_soon_cards_carry_their_wave_label():
    """BR-INT-001: the v1 connector matrix, as data.

    ⚠ **FOUR UNTIL `CR-110-BRC04`, AND THE TWELVE ARE NOT TWELVE NEW HOLDS.**
    `payments_card` became five named processors and `meters_mdm` became two, so
    two cards became seven carrying the SAME two reasons: the payment rails are
    W7, and AMI ingestion waits for the B6 capacity re-run under `BR-INT-012`.
    Badger BEACON joins the meters for that second reason. The genuinely new
    holds were the bulk email service and `print_vendor`, whose vendor the PO
    deliberately had not named (2026-09-16).

    ⚠ **THE ESP BECAME TWO NAMED VENDORS ON 2026-09-17 AND BOTH ARE STILL
    HELD** (`CR-115-BRC05`): `sendgrid` (renamed from `email_bulk`) and
    `postmark`. Naming a vendor released nothing, because neither has an
    adapter — so their expiry test moved from *is the name still generic* to
    *does `adapter_for()` still answer None*, in
    `test_cr115_email_connectors.py`. `print_vendor` keeps the name-shaped hold
    in `test_cr110_connectors.py`, which goes RED the day ITS vendor is named.
    """
    by_key = {one.key: one for one in manifests.MANIFESTS}
    # `sms_twilio` is LIVE since `CR-198-BRC10` (PO 2026-10-29, *"1A … start"*).
    assert by_key["sms_twilio"].disposition.kind == "live"
    assert by_key["sso"].disposition.wave == "v2"
    # `pay_uspayments` is LIVE since `CR-174-BRC10` (PO D4, 2026-10-07).
    for key in ("pay_invoicecloud", "pay_paymentus", "pay_worldpay", "pay_globalpayments"):
        assert by_key[key].disposition.wave == "W7", key
    for key in ("meters_badger", "meters_itron", "meters_sensus"):
        assert by_key[key].disposition.wave == "v2", key
    coming = sorted(k for k, m in by_key.items() if m.disposition.coming_soon)
    assert coming == [
        "meters_badger",
        "meters_itron",
        "meters_sensus",
        "pay_globalpayments",
        "pay_invoicecloud",
        "pay_paymentus",
        "pay_worldpay",
        "postmark",
        "print_vendor",
        "sendgrid",
        "sso",
    ]


# ── TC-2 · TC-3 · TC-4 · TC-6 — refused at load, by name ────────────────────


def test_us_int_013_tc2_an_operation_with_no_idempotency_mode_is_refused_naming_it():
    fresh = Registry()
    bad = _manifest(operations=(_op(idempotency=None),))
    with pytest.raises(ManifestError) as refused:
        fresh.register(bad)
    assert "example_provider · send_message" in str(refused.value)
    assert "idempotency mode" in str(refused.value)
    assert len(fresh) == 0  # nothing half-registered


def test_us_int_013_tc2_an_operation_with_no_completion_mode_is_refused_naming_it():
    fresh = Registry()
    bad = _manifest(operations=(_op(completion=None),))
    with pytest.raises(ManifestError) as refused:
        fresh.register(bad)
    assert "example_provider · send_message" in str(refused.value)
    assert "completion mode" in str(refused.value)


def test_us_int_013_tc2_the_shipped_kiosk_without_its_completion_is_refused_the_same_way():
    """The terminal proof of demo step 7, as a test: strip `completion` from the
    kiosk's payments operation and the registry names `payments_kiosk · payments`."""
    kiosk = registry.REGISTRY.require("payments_kiosk")
    stripped = tuple(
        dataclasses.replace(one, completion=None) if one.name == "payments" else one
        for one in kiosk.operations
    )
    broken = dataclasses.replace(kiosk, operations=stripped)
    with pytest.raises(ManifestError) as refused:
        Registry().register(broken)
    assert "payments_kiosk · payments" in str(refused.value)


def test_us_int_013_tc3_a_reply_before_authenticate_is_refused():
    fresh = Registry()
    bad = _manifest(
        operations=(
            _op(
                name="payments",
                direction="in",
                initiative="them",
                trigger="webhook",
                respond_after="receive",  # authenticate's predecessor
                envelope_status={"ok": 200},
            ),
        )
    )
    with pytest.raises(ManifestError) as refused:
        fresh.register(bad)
    assert "before `authenticate`" in str(refused.value)
    assert "BR-INT-030" in str(refused.value)
    assert "example_provider · payments" in str(refused.value)


def test_us_int_013_tc3_a_partner_call_with_no_reply_position_is_refused():
    fresh = Registry()
    bad = _manifest(
        operations=(
            _op(
                name="payments",
                direction="in",
                initiative="them",
                trigger="webhook",
                envelope_status={"ok": 200},
            ),
        )
    )
    with pytest.raises(ManifestError, match="no reply position"):
        fresh.register(bad)


def test_us_int_013_tc4_certified_with_no_certificate_id_is_refused_and_self_declared_loads():
    fresh = Registry()
    certified = _manifest(
        conformance=Conformance(standard="MultiSpeak", claim="certified", evidence="none")
    )
    with pytest.raises(ManifestError) as refused:
        fresh.register(certified)
    assert "certificate id" in str(refused.value)
    assert "BR-INT-053" in str(refused.value)
    declared = _manifest(
        conformance=Conformance(standard="MultiSpeak", claim="self_declared", evidence="tests")
    )
    fresh.register(declared)
    assert fresh.get("example_provider") is declared


def test_us_int_013_an_unregistered_codec_is_refused_by_name_with_the_list_of_what_exists():
    fresh = Registry()
    with pytest.raises(ManifestError) as refused:
        fresh.register(_manifest(codecs=("edi_x12",)))
    text = str(refused.value)
    assert "'edi_x12'" in text and "bai2" in text and "BR-INT-033" in text


def test_us_int_013_an_unknown_field_kind_is_refused():
    fresh = Registry()
    bad = _manifest(fields=(Field(name="pin", label="PIN", kind="password"),))
    with pytest.raises(ManifestError) as refused:
        fresh.register(bad)
    assert "'password'" in str(refused.value) and "BR-INT-043" in str(refused.value)


def test_us_int_018_tc3_a_provider_with_zero_operations_is_refused_naming_it():
    fresh = Registry()
    with pytest.raises(ManifestError) as refused:
        fresh.register(_manifest(operations=()))
    assert "example_provider" in str(refused.value)
    assert "BR-INT-028" in str(refused.value)


def test_us_int_013_a_coming_soon_disposition_needs_its_wave_label():
    fresh = Registry()
    with pytest.raises(ManifestError, match="wave label"):
        fresh.register(_manifest(disposition=Disposition(kind="coming_soon")))


def test_us_int_013_tc6_a_coming_soon_provider_has_no_adapter_and_nothing_raises():
    # ⚠ `payments_card` until `CR-110-BRC04`, when one generic card became five
    # named processors. `pay_invoicecloud` is the first of the five and carries
    # the same W7 hold for the same reason: the payment rails are not v1.
    assert registry.REGISTRY.require("pay_invoicecloud").disposition.coming_soon
    assert registry.REGISTRY.adapter_for("pay_invoicecloud") is None  # a VALUE, not a raise
    with pytest.raises(ManifestError, match="no adapter"):
        registry.REGISTRY.register_adapter("pay_invoicecloud", object)


def test_us_int_013_the_categories_are_generated_in_first_appearance_order():
    # ⚠ THE ORDER IS FIRST APPEARANCE IN THE SEED LIST, so `CR-110-BRC04`
    # reordering the grid reorders these too — and `erp` is a new value, added by
    # five manifests and by no line of code, which is `BR-INT-037` visible in a
    # test: `Manifest.category` is free text and the filter chips are generated.
    assert registry.REGISTRY.categories() == [
        "email",
        "messaging",
        "meters",
        "payments",
        "erp",
        "accounting",
        "banking",
        "print",
        "maps",
        "identity",
    ]


# ── TC-1 · TC-7 — through the API, under each tenant's own context ──────────


@pytest.mark.django_db
def test_us_int_013_tc1_brazos_bend_with_no_connections_gets_every_card_all_not_set_up(
    brazos, dana
):
    response = api_call(
        integrations_api.integrations_grid,
        "get",
        "/api/brazosbend/integrations",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
    )
    assert response.status_code == 200
    providers = response.data["providers"]
    assert len(providers) == SHIPPED_PROVIDERS
    assert {one["state"] for one in providers} == {"not_set_up"}
    assert {one["display_state"] for one in providers} == {"not_set_up"}
    assert all(one["connection"] is None for one in providers)
    # every operation row of every card reads not_set_up too
    assert {op["state"] for one in providers for op in one["operations"]} == {"not_set_up"}
    assert response.data["counts"] == {"providers": SHIPPED_PROVIDERS, "connected": 0}


@pytest.mark.django_db
def test_us_int_013_tc7_lone_star_ridge_sees_the_same_set_and_nothing_of_brazos_bend(
    brazos, dana, lonestar, erin
):
    from apps.integrations import services
    from tests.test_us_met_helpers import tenant_ctx

    with tenant_ctx(brazos):
        services.connect(
            actor=dana,
            tenant_id=brazos.id,
            provider_key="email_smtp",
            environment="production",
            label="Billing mailbox",
            config={"host": "smtp.brazosbend.example", "port": 587},
        )
    response = api_call(
        integrations_api.integrations_grid,
        "get",
        "/api/lonestarridge/integrations",
        user=erin.user,
        role="system_admin",
        tenant=lonestar,
    )
    assert response.status_code == 200
    providers = response.data["providers"]
    assert len(providers) == SHIPPED_PROVIDERS
    assert {one["state"] for one in providers} == {"not_set_up"}
    assert "Billing mailbox" not in str(response.data)
    assert "brazosbend.example" not in str(response.data)
    # and Brazos Bend's own read sees its row
    own = api_call(
        integrations_api.integrations_grid,
        "get",
        "/api/brazosbend/integrations",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
    )
    smtp = next(one for one in own.data["providers"] if one["key"] == "email_smtp")
    assert smtp["connection"]["label"] == "Billing mailbox"
    assert smtp["state"] == "untested"
