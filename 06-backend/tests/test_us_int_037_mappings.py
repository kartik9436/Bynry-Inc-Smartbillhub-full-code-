# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-037 (EP-INT-10) — their words for our things. Screens: S143
# Rules:    BR-INT-032 (a row, UNIQUE on the external side; two of theirs may
#           share one of ours) · BR-INT-031 (an unmapped inbound value records
#           as `other`, shows red; `R02` is OQ-INT-1487's) · B14 rule 31 (no id
#           is a visible value) · A4 `settings_lookups` (a clerk is refused) ·
#           CLAUDE.md hard rule 7 (a mapping writes audit_log)
# Tests:    this file — TC-1 (fourteen red rows, unmapped first; ACHCHECK and
#           ACHSAVINGS both → Bank transfer, both green) · TC-4 (`Bitcoin` is
#           refused as not one of ours) · TC-5 (an inbound CASHAPP is a red row
#           with last seen) · TC-6 (Lone Star Ridge sees its own rows only) ·
#           the same word twice in one request · R02 · the API's two verbs and
#           its role gate. TC-2 (the UNIQUE) and TC-3 (a fourth partner, no
#           migration) are PostgreSQL's — tests/test_us_int_037_pg.py.
# Impacts:  apps/integrations/mappings.py · mappings_api.py · manifests/payments_kiosk.py
# ───────────────────────────────────────────────────────
"""US-INT-037 on SQLite — the rows, the refusals, the read, the API.

`brazos_tenders` gives Brazos Bend the story's five payment methods — *Cash ·
Cheque · Card · Bank transfer · Money order* — through the tenant-extensible
lookup, exactly as a utility would on Settings → Reference data.
"""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

import pytest

from apps.integrations import mappings, models, selectors, services
from apps.integrations import mappings_api
from apps.integrations.manifests.payments_kiosk import KIOSK_TENDER_WORDS
from apps.tenancy.models import PaymentMethod
from core import errors
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · marcus · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

KIOSK = "payments_kiosk"
FIVE = (
    ("cash", "Cash"),
    ("cheque", "Cheque"),
    ("card", "Card"),
    ("bank_transfer", "Bank transfer"),
    ("money_order", "Money order"),
)


def _tenders(tenant, five=FIVE):
    """The utility's own words — a tenant-extensible lookup, not an enum."""
    PaymentMethod.objects.filter(tenant=tenant).update(active=False)
    for code, name in five:
        PaymentMethod.objects.update_or_create(
            tenant=tenant, code=code, defaults={"name": name, "active": True}
        )


@pytest.fixture()
def brazos_tenders(brazos):
    with tenant_ctx(brazos):
        _tenders(brazos)
    return brazos


def _rows(entity_type, **pairs):
    return [
        {"entity_type": entity_type, "external_value": word, "local_value": value}
        for word, value in pairs.items()
    ]


def _api(tenant, actor, role, method="get", data=None):
    return api_call(
        mappings_api.mappings_view,
        method,
        f"/api/{tenant.subdomain}/integrations/{KIOSK}/mappings",
        user=actor.user,
        role=role,
        tenant=tenant,
        data=data,
        key=KIOSK,
    )


# ── TC-1 — fourteen red rows, then two of theirs share one of ours ──────────


@pytest.mark.django_db
def test_us_int_037_tc1_the_kiosk_ships_fourteen_words_all_red_and_unmapped_first(
    brazos_tenders, dana
):
    brazos = brazos_tenders
    with tenant_ctx(brazos):
        served = mappings.view(brazos.id, KIOSK)
    assert len(KIOSK_TENDER_WORDS) == 14
    assert served["counts"] == {"rows": 14, "unmapped": 14}
    assert {one["external_value"] for one in served["rows"]} == set(KIOSK_TENDER_WORDS)
    assert all(one["state"] == "unmapped" and one["local_value"] is None for one in served["rows"])
    assert [one["entity_type"] for one in served["types"]] == ["tender"]
    choices = served["types"][0]["choices"]
    assert [one["label"] for one in choices] == [
        "Bank transfer",
        "Card",
        "Cash",
        "Cheque",
        "Money order",
    ]
    # B14 rule 31: the wire carries words and codes, never a database id.
    assert all(set(one) == {"value", "label"} for one in choices)
    assert models.IntegrationTargetReference.objects.count() == 0, "shipped words cost no row yet"


@pytest.mark.django_db
def test_us_int_037_tc1_achcheck_and_achsavings_both_map_to_bank_transfer_and_both_go_green(
    brazos_tenders, dana, audit_rows
):
    brazos = brazos_tenders
    with tenant_ctx(brazos):
        written = services.set_mappings(
            actor=dana,
            tenant_id=brazos.id,
            provider_key=KIOSK,
            rows=_rows("tender", ACHCHECK="bank_transfer", ACHSAVINGS="bank_transfer"),
        )
        served = mappings.view(brazos.id, KIOSK)
    assert len(written) == 2
    bank = PaymentMethod.objects.get(tenant=brazos, code="bank_transfer")
    assert all(row.entity_id == bank.id and row.local_value == "bank_transfer" for row in written)

    by_word = {one["external_value"]: one for one in served["rows"]}
    assert by_word["ACHCHECK"]["state"] == "mapped"
    assert by_word["ACHSAVINGS"]["state"] == "mapped"
    assert (
        by_word["ACHCHECK"]["local_label"]
        == "Bank transfer"
        == by_word["ACHSAVINGS"]["local_label"]
    )
    assert served["counts"] == {"rows": 14, "unmapped": 12}
    # unmapped first, then their word
    states = [one["state"] for one in served["rows"]]
    assert states == ["unmapped"] * 12 + ["mapped"] * 2
    assert [one["external_value"] for one in served["rows"][-2:]] == ["ACHCHECK", "ACHSAVINGS"]
    # hard rule 7: a mapping decides where money lands on a report
    actions = [one["action"] for one in audit_rows]
    assert actions.count("integration.mapping.set") == 2
    row = next(one for one in audit_rows if one["action"] == "integration.mapping.set")
    assert row["after"]["external_value"] in ("ACHCHECK", "ACHSAVINGS")
    assert row["after"]["local_value"] == "bank_transfer"
    assert row["before"] is None


@pytest.mark.django_db
def test_us_int_037_a_remap_updates_the_one_row_and_an_empty_value_unmaps_it(
    brazos_tenders, dana, audit_rows
):
    brazos = brazos_tenders
    with tenant_ctx(brazos):
        services.set_mappings(
            actor=dana, tenant_id=brazos.id, provider_key=KIOSK, rows=_rows("tender", CASH="cash")
        )
        services.set_mappings(
            actor=dana, tenant_id=brazos.id, provider_key=KIOSK, rows=_rows("tender", CASH="cheque")
        )
        assert models.IntegrationTargetReference.objects.filter(external_value="CASH").count() == 1
        assert mappings.local_for(brazos.id, KIOSK, "tender", "CASH")["value"] == "cheque"
        services.set_mappings(
            actor=dana, tenant_id=brazos.id, provider_key=KIOSK, rows=_rows("tender", CASH=None)
        )
        row = models.IntegrationTargetReference.objects.get(external_value="CASH")
        assert row.entity_id is None and row.local_value is None, "unmapped, and the row is kept"
        assert mappings.local_for(brazos.id, KIOSK, "tender", "CASH") is None
        assert mappings.view(brazos.id, KIOSK)["counts"]["unmapped"] == 14
    remap = [one for one in audit_rows if one["action"] == "integration.mapping.set"][1]
    assert remap["before"]["local_value"] == "cash" and remap["after"]["local_value"] == "cheque"


# ── the same word twice in one request is a second meaning ──────────────────


@pytest.mark.django_db
def test_us_int_037_one_of_their_words_cannot_carry_two_meanings_in_one_request(
    brazos_tenders, dana
):
    brazos = brazos_tenders
    twice = [
        {"entity_type": "tender", "external_value": "ACHCHECK", "local_value": "bank_transfer"},
        {"entity_type": "tender", "external_value": "ACHCHECK", "local_value": "cash"},
    ]
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            services.set_mappings(actor=dana, tenant_id=brazos.id, provider_key=KIOSK, rows=twice)
        assert refused.value.message_key == "integrations.refusal.mapping_twice"
        assert refused.value.params == {"word": "ACHCHECK"}
        assert models.IntegrationTargetReference.objects.count() == 0, "nothing half-written"


# ── TC-4 — a value that is not one of ours ──────────────────────────────────


@pytest.mark.django_db
def test_us_int_037_tc4_bitcoin_is_refused_as_not_one_of_our_values(brazos_tenders, dana):
    brazos = brazos_tenders
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            services.set_mappings(
                actor=dana,
                tenant_id=brazos.id,
                provider_key=KIOSK,
                rows=_rows("tender", CRYPTO="Bitcoin"),
            )
        assert refused.value.code == errors.VAL_UNKNOWN_LOOKUP
        assert refused.value.message_key == "integrations.refusal.mapping_not_ours"
        assert refused.value.params == {"value": "Bitcoin"}
        assert models.IntegrationTargetReference.objects.count() == 0


@pytest.mark.django_db
def test_us_int_037_a_kind_of_thing_we_do_not_have_and_a_blank_word_are_refused(
    brazos_tenders, dana
):
    brazos = brazos_tenders
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as kind:
            services.set_mappings(
                actor=dana,
                tenant_id=brazos.id,
                provider_key=KIOSK,
                rows=[{"entity_type": "colour", "external_value": "RED", "local_value": "cash"}],
            )
        assert kind.value.message_key == "integrations.refusal.mapping_type"
        with pytest.raises(errors.ValidationError) as blank:
            services.set_mappings(
                actor=dana,
                tenant_id=brazos.id,
                provider_key=KIOSK,
                rows=[{"entity_type": "tender", "external_value": "  ", "local_value": "cash"}],
            )
        assert blank.value.message_key == "integrations.refusal.mapping_word"


# ── R02 — the writer refuses, and now BY RULING (OQ-INT-1487, closed) ───────


@pytest.mark.django_db
def test_us_int_037_r01_maps_to_not_enough_money_and_r02_is_refused_by_ruling(brazos, dana):
    """`OQ-INT-1487`, closed 2026-09-04 to option (b): `R02` records as `other`
    with the raw code kept, the four signed reasons are NOT widened to five, and
    option (c) — mapping it onto one of them — was declined. So the refusal that
    used to be a `NotImplementedError` naming an open question is now an ordinary
    ValidationError a clerk can read, and the screen says *always records as
    Other* instead of *waiting for a decision*."""
    bank = "bank_lockbox_file"
    with tenant_ctx(brazos):
        services.set_mappings(
            actor=dana,
            tenant_id=brazos.id,
            provider_key=bank,
            rows=_rows("reversal_reason", R01="nsf"),
        )
        served = mappings.view(brazos.id, bank)
        by_word = {one["external_value"]: one for one in served["rows"]}
        assert by_word["R01"]["local_label"] == "Not enough money"
        assert by_word["R02"]["state"] == "unmapped"
        assert by_word["R02"]["stays_other"] is True
        assert by_word["R01"]["stays_other"] is False
        with pytest.raises(errors.ValidationError) as r02:
            services.set_mappings(
                actor=dana,
                tenant_id=brazos.id,
                provider_key=bank,
                rows=_rows("reversal_reason", R02="bank_chargeback"),
            )
        assert r02.value.message_key == "integrations.refusal.mapping_r02_stays_other"
        assert r02.value.params["word"] == "R02"
        # the four signed reasons are not widened to hold a third party's word
        assert [one["value"] for one in served["types"][0]["choices"]] == [
            "nsf",
            "bank_chargeback",
            "data_entry_error",
            "customer_dispute",
        ]


def test_us_int_037_retiring_the_two_vendor_columns_is_ruled_shut_and_says_so():
    """`OQ-INT-1480` was HELD on 2026-09-04 — *"we will use our GL code only"* —
    so this is a deliberate absence, not a stub. The message must name the
    RULING rather than a question: a lane reading it should stop, not unblock."""
    with pytest.raises(NotImplementedError) as held:
        mappings.retire_vendor_columns()
    assert "ruled 2026-09-04" in str(held.value)
    assert "OQ-" not in str(held.value)


# ── TC-5 — an inbound word nobody mapped is a red row with last seen ────────


@pytest.mark.django_db
def test_us_int_037_tc5_cashapp_arriving_unmapped_becomes_a_red_row_with_last_seen(
    brazos_tenders, dana
):
    brazos = brazos_tenders
    seen_at = datetime(2026, 9, 3, 6, 15, tzinfo=dt_timezone.utc)
    with tenant_ctx(brazos):
        connection = services.connect(
            actor=dana,
            tenant_id=brazos.id,
            provider_key=KIOSK,
            environment="production",
            label="Kiosk network",
        )
        row = services.record_unknown_value(
            connection=connection, entity_type="tender", external_value="CASHAPP", seen_at=seen_at
        )
        assert row.entity_id is None and row.local_value is None
        assert mappings.local_for(brazos.id, KIOSK, "tender", "CASHAPP") is None, "→ Other"
        served = mappings.view(brazos.id, KIOSK)
    assert served["counts"] == {"rows": 15, "unmapped": 15}
    cashapp = next(one for one in served["rows"] if one["external_value"] == "CASHAPP")
    assert cashapp["state"] == "unmapped" and cashapp["shipped"] is False
    assert cashapp["last_seen_at"] == "2026-09-03T06:15:00+00:00"
    # a second arrival moves last seen and adds no second row
    with tenant_ctx(brazos):
        services.record_unknown_value(
            connection=connection, entity_type="tender", external_value="CASHAPP"
        )
        assert (
            models.IntegrationTargetReference.objects.filter(external_value="CASHAPP").count() == 1
        )
        connection.refresh_from_db()
        assert connection.config["last_seen"]["tender:CASHAPP"] > "2026-09-03T06:15:00"


# ── TC-6 — tenant isolation ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_us_int_037_tc6_lone_star_ridge_sees_its_own_rows_only(
    brazos_tenders, dana, lonestar, erin
):
    brazos = brazos_tenders
    with tenant_ctx(brazos):
        services.set_mappings(
            actor=dana,
            tenant_id=brazos.id,
            provider_key=KIOSK,
            rows=_rows("tender", ACHCHECK="bank_transfer", ACHSAVINGS="bank_transfer"),
        )
    with tenant_ctx(lonestar):
        _tenders(
            lonestar,
            (
                ("cash", "Cash"),
                ("wire", "Wire"),
            ),
        )
        theirs = mappings.view(lonestar.id, KIOSK)
    assert theirs["counts"] == {"rows": 14, "unmapped": 14}, "Brazos Bend's two are absent"
    assert [one["label"] for one in theirs["types"][0]["choices"]] == ["Cash", "Wire"]
    with tenant_ctx(lonestar):
        services.set_mappings(
            actor=erin, tenant_id=lonestar.id, provider_key=KIOSK, rows=_rows("tender", CASH="wire")
        )
    with tenant_ctx(brazos):
        ours = mappings.view(brazos.id, KIOSK)
    assert {one["external_value"] for one in ours["rows"] if one["state"] == "mapped"} == {
        "ACHCHECK",
        "ACHSAVINGS",
    }


# ── the API: two verbs, one role gate, a 404 that looks like any other ──────


@pytest.mark.django_db
def test_us_int_037_the_api_reads_and_sets_rows_and_refuses_a_clerk(brazos_tenders, dana, marcus):
    brazos = brazos_tenders
    read = _api(brazos, dana, "system_admin")
    assert read.status_code == 200
    assert read.data["counts"]["unmapped"] == 14
    assert read.data["provider"] == {"key": KIOSK, "display_name": "Payment kiosk network"}

    put = _api(
        brazos,
        dana,
        "system_admin",
        "put",
        {"rows": _rows("tender", ACHCHECK="bank_transfer", ACHSAVINGS="bank_transfer")},
    )
    assert put.status_code == 200, put.data
    assert put.data["counts"] == {"rows": 14, "unmapped": 12}

    twice = _api(
        brazos,
        dana,
        "system_admin",
        "put",
        {
            "rows": [
                {"entity_type": "tender", "external_value": "ACHCHECK", "local_value": "cash"},
                {"entity_type": "tender", "external_value": "ACHCHECK", "local_value": "cheque"},
            ]
        },
    )
    assert twice.status_code == errors.HTTP_STATUS_BY_CODE[errors.VAL_FORMAT]
    assert twice.data["message_key"] == "integrations.refusal.mapping_twice"

    not_ours = _api(
        brazos, dana, "system_admin", "put", {"rows": _rows("tender", CRYPTO="Bitcoin")}
    )
    assert not_ours.status_code == errors.HTTP_STATUS_BY_CODE[errors.VAL_UNKNOWN_LOOKUP]
    assert not_ours.data["message_key"] == "integrations.refusal.mapping_not_ours"

    # A4 settings_lookups: a Billing Clerk has no cell — refused server-side, both verbs.
    assert _api(brazos, marcus, "billing_clerk").status_code == 403
    assert _api(brazos, marcus, "billing_clerk", "put", {"rows": []}).status_code == 403
    # an Executive may LOOK and may not change
    assert _api(brazos, dana, "executive").status_code == 200
    assert _api(brazos, dana, "executive", "put", {"rows": []}).status_code == 403


@pytest.mark.django_db
def test_us_int_037_an_unknown_provider_key_is_a_plain_404(brazos, dana):
    response = api_call(
        mappings_api.mappings_view,
        "get",
        f"/api/{brazos.subdomain}/integrations/no_such_provider/mappings",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        key="no_such_provider",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_us_int_037_the_grid_card_says_which_kinds_of_words_a_provider_ships(brazos, dana):
    with tenant_ctx(brazos):
        served = selectors.grid(brazos.id)
    by_key = {one["key"]: one for one in served["providers"]}
    assert by_key[KIOSK]["vocabularies"] == [
        {"entity_type": "tender", "label": "How they pay", "count": 14}
    ]
    assert by_key["bank_lockbox_file"]["vocabularies"][0]["entity_type"] == "reversal_reason"
    assert by_key["accounting_file"]["vocabularies"] == [
        {"entity_type": "ledger_account", "label": "Their account codes", "count": 0}
    ]
    assert by_key["email_smtp"]["vocabularies"] == []


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-037@87b94265 (EP-INT-10 story + BR-INT-031 · BR-INT-032 verbatim)
# generated: 2026-09-03 by the CR-069 wave D build lane
# checklist: A✔ B✔ C✔ D✔ E✔(the API cases are what ValueMappingPage.tsx calls) F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_037_mappings.py · tests/test_us_int_037_pg.py (PostgreSQL)
# exceptions: TC-2 and TC-3 are PostgreSQL's and are never faked here (law 14)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
