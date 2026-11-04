# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-001 (EP-INT-01) — S8's card grid, `GET /integrations`.
#           Screens: S8
# Rules:    BR-INT-001 (coming-soon cards carry the wave label; connect is
#           refused at the API) · BR-INT-002 (`GET /integrations`) · BR-INT-003
#           (no credential material in any grid payload) · BR-INT-004 (no
#           provider hardcoded) · A4 settings_lookups
# Tests:    this file — TC-1 (the grid renders per-card state), TC-2 (the four
#           coming-soon cards and their labels), TC-4 (a Billing Clerk is
#           refused server-side), TC-5 (connect on a coming-soon provider is
#           refused by the service the API will mount), TC-6 (no credential
#           material in the payload), TC-7 (isolation — with US-INT-013 TC-7)
# Impacts:  apps/integrations/api.py · selectors.py · config/urls.py
# ───────────────────────────────────────────────────────
"""US-INT-001 — the grid's data source, and who may read it."""

import pytest

from apps.integrations import api as integrations_api
from apps.integrations import services
from apps.integrations.manifests import CONNECTOR_COUNT
from core import errors
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · marcus
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call


def _grid(tenant, actor, role):
    return api_call(
        integrations_api.integrations_grid,
        "get",
        f"/api/{tenant.subdomain}/integrations",
        user=actor.user,
        role=role,
        tenant=tenant,
    )


@pytest.mark.django_db
def test_us_int_001_tc1_the_grid_serves_per_card_state_category_and_kicker(brazos, dana):
    data = _grid(brazos, dana, "system_admin").data
    # ⚠ THE CHIPS ARE GENERATED FROM FIRST APPEARANCE IN THE SEED LIST, never
    # typed — so `CR-110-BRC04` reordering the grid to the blueprint's catalogue
    # reordered these, and `erp` appeared as a TENTH value added by five manifest
    # files and no line of code. That is `BR-INT-037` visible on a screen.
    assert [one["key"] for one in data["categories"]] == [
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
    smtp = next(one for one in data["providers"] if one["key"] == "email_smtp")
    assert smtp["category"] == "email"
    assert smtp["kicker"] == {"direction": "out", "initiative": "us"}  # EMAIL · WE SEND
    kiosk = next(one for one in data["providers"] if one["key"] == "payments_kiosk")
    assert kiosk["kicker"] == {"direction": "in", "initiative": "them"}  # PAYMENTS · THEY SEND
    # ⚠ `gl_partner` until `CR-110-BRC04`, when the one generic finance card
    # became five NAMED ERPs. The kicker is unchanged — it is read from the
    # first operation's direction and initiative, and the relationship did not
    # move: a finance system still reads FROM us. Only the category word did,
    # from `accounting` to `erp`, which is `Manifest.category` being free text
    # and the filter chips being generated (`BR-INT-037`).
    partner = next(one for one in data["providers"] if one["key"] == "erp_workday")
    assert partner["kicker"] == {"direction": "out", "initiative": "them"}  # ERP · THEY READ
    meters = next(one for one in data["providers"] if one["key"] == "meters_neptune360")
    assert meters["kicker"] == {"direction": "in", "initiative": "us"}  # METERS · WE COLLECT


@pytest.mark.django_db
def test_us_int_001_tc2_the_coming_soon_cards_carry_their_wave_label_and_no_adapter(brazos, dana):
    data = _grid(brazos, dana, "system_admin").data
    coming = {
        one["key"]: one["disposition"]
        for one in data["providers"]
        if one["disposition"]["kind"] == "coming_soon"
    }
    # ⚠ FOUR UNTIL `CR-110-BRC04`. Two of the four were SPLIT — one card
    # processor into five and one meter cloud into two — so seven of the twelve
    # carry the two original reasons unchanged (the payment rails are W7;
    # `BR-INT-012` holds AMI ingestion for the B6 capacity re-run). Badger BEACON
    # joins the meters for that same second reason. **The genuinely new holds are
    # two**: the bulk email service and `print_vendor`, whose vendor the PO
    # deliberately had not named (2026-09-16), and those two carried their own
    # expiry test.
    #
    # ⚠ **THE ESP IS NOW TWO NAMED VENDORS AND STILL HELD (`CR-115-BRC05`,
    # 2026-09-17).** `email_bulk` became `sendgrid` and `postmark` joined it;
    # naming a vendor did NOT release either card, because neither has an
    # adapter bound and a card offered as live with nothing behind it is
    # `DEF-INT-4224`. Their hold is re-aimed at `adapter_for()` in
    # `test_cr115_email_connectors.py`.
    assert coming == {
        "postmark": {"kind": "coming_soon", "wave": "v1.1", "phase": 2},
        "sendgrid": {"kind": "coming_soon", "wave": "v1.1", "phase": 2},
        "meters_badger": {"kind": "coming_soon", "wave": "v2", "phase": None},
        "meters_itron": {"kind": "coming_soon", "wave": "v2", "phase": None},
        "meters_sensus": {"kind": "coming_soon", "wave": "v2", "phase": None},
        "pay_globalpayments": {"kind": "coming_soon", "wave": "W7", "phase": 5},
        "pay_invoicecloud": {"kind": "coming_soon", "wave": "W7", "phase": 5},
        "pay_paymentus": {"kind": "coming_soon", "wave": "W7", "phase": 5},
        "pay_worldpay": {"kind": "coming_soon", "wave": "W7", "phase": 5},
        "print_vendor": {"kind": "coming_soon", "wave": "v1.1", "phase": 4},
        "sso": {"kind": "coming_soon", "wave": "v2", "phase": None},
    }
    # ⚠ THIS ASSERTED `not one["adapter_registered"]` FOR *EVERY* PROVIDER —
    # "wave A registers no adapter; the first arrives with wave E" — and it has
    # been RED since an adapter arrived (`DEF-INT-4021`). Two are bound now,
    # `email_smtp` and `payments_sandbox` (`CR-068` phase 5), and the sentence
    # was a statement about a WAVE rather than about a rule, so it was going to
    # expire the day the wave landed and nothing was watching for that.
    #
    # THE INVARIANT UNDERNEATH IT IS THE ONE WORTH KEEPING AND IT DOES NOT
    # EXPIRE: a card a utility CANNOT CONNECT must not have a live adapter
    # sitting behind it. `BR-INT-001` refuses the connect; an adapter bound to a
    # coming-soon key would be a door around that refusal.
    assert all(
        not one["adapter_registered"]
        for one in data["providers"]
        if one["disposition"]["kind"] == "coming_soon"
    ), "a provider nobody may connect must not carry an adapter (BR-INT-001)"


@pytest.mark.django_db
def test_us_int_001_tc4_a_billing_clerk_is_refused_server_side_and_an_executive_may_read(
    brazos, dana, marcus
):
    """A4: Billing Clerk has no settings_lookups cell; Executive has View."""
    refused = _grid(brazos, marcus, "billing_clerk")
    assert refused.status_code == 403
    executive = _grid(brazos, dana, "executive")
    assert executive.status_code == 200
    # ⚠ **THE LITERAL IS GONE — 28 → `CONNECTOR_COUNT`, 2026-09-17.** It read
    # 28 (18 before `CR-110-BRC04`; 17 before `CR-068` phase 5 added
    # `payments_sandbox`, `DEF-INT-4021`), and its twin one file along read 18
    # and had been red for a day — `DEF-INT-5575`. `CONNECTOR_COUNT` is the one
    # place the number is declared and `tests/test_cr110_connectors.py` locks it
    # against `len(MANIFESTS)` and the loaded registry, so this is neither a
    # literal nor a `len()` of the thing under test.
    #
    # The number is incidental to what TC-4 is for, which is that a Billing
    # Clerk is refused server-side and an Executive may read; it is kept because
    # "the grid an Executive sees is the WHOLE grid" is the half that would
    # otherwise go unasserted.
    assert len(executive.data["providers"]) == CONNECTOR_COUNT


@pytest.mark.django_db
def test_us_int_001_tc5_connecting_a_coming_soon_provider_is_refused_by_the_service(brazos, dana):
    """BR-INT-001 — the refusal wave B's POST route mounts is already here."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as refused:
            services.connect(
                actor=dana,
                tenant_id=brazos.id,
                # `payments_card` until `CR-110-BRC04`; each of the five named
                # processors it became carries the same W7 hold.
                provider_key="pay_invoicecloud",
                environment="production",
            )
    assert refused.value.code == errors.BIZ_STATE
    assert refused.value.br_ref == "BR-INT-001"
    assert refused.value.message_key == "integrations.refusal.not_available"
    assert refused.value.params["wave"] == "W7"


@pytest.mark.django_db
def test_us_int_001_tc6_the_payload_carries_masked_refs_and_no_credential_material(brazos, dana):
    with tenant_ctx(brazos):
        row = services.connect(
            actor=dana,
            tenant_id=brazos.id,
            provider_key="email_smtp",
            environment="production",
            label="Billing mailbox",
            config={"host": "smtp.brazosbend.example", "port": 587, "username": "billing"},
        )
        services.record_credential(
            actor=dana, connection=row, payload="the-real-password", masked_hint="••••3F9A"
        )
    body = str(_grid(brazos, dana, "system_admin").data)
    assert "••••3F9A" in body
    assert "the-real-password" not in body
    assert "payload_enc" not in body
    assert "sbh1:" not in body  # not even the ciphertext envelope


@pytest.mark.django_db
def test_us_int_001_an_unknown_provider_key_is_refused_by_name_with_the_list(brazos, dana):
    from apps.integrations.registry import ManifestError

    with tenant_ctx(brazos):
        with pytest.raises(ManifestError) as refused:
            services.connect(
                actor=dana, tenant_id=brazos.id, provider_key="stripe", environment="production"
            )
    assert "'stripe'" in str(refused.value) and "email_smtp" in str(refused.value)
