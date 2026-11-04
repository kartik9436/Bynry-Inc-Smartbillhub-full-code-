# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-017 (EP-INT-05) — server-side gating of coming-soon
#           providers: refused by the API, with ZERO secret persistence.
#           Screens: S8 · S141
# Rules:    BR-INT-001 (Connect disabled at UI AND API) · BR-INT-003 (zero
#           secret persistence on refusal; no log line carries the key) ·
#           BR-INT-037 (a coming-soon card is the same manifest object with
#           no adapter; an unknown key is 404 identical to absent) ·
#           BR-INT-014 (a refusal is a lifecycle event — audited, no payload)
#           · B14 rule 33 (≤ 6 words) · A1 (a Billing Clerk is refused
#           server-side regardless)
# Tests:    this file — TC-1..6 + the clerk + the live key with no adapter
#           (the product's own state in wave B)
# Impacts:  apps/integrations/api.py · services.py
# ───────────────────────────────────────────────────────
"""US-INT-017 — phase 1's exit test: refused at the API, and the database is byte-for-byte unchanged."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from apps.integrations import api as integrations_api
from apps.integrations import services
from tests.test_us_int_helpers_b import *  # noqa: F401,F403
from tests.test_us_int_helpers_b import (
    LOOKS_LIKE_A_KEY,
    SMTP_FIELDS,
    call,
    counts,
    delete_connection,
    patch_connection,
    post_connect,
    post_credential,
    post_run,
    post_test,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus · audit_rows

LOCALES = Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
ELEVEN = ["de", "en", "es-MX", "es", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR"]

#: ⚠ `payments_card` UNTIL `CR-110-BRC04` — one generic card became five named
#: processors (blueprint p162). Every one of the five carries the SAME W7 hold
#: for the same reason, so this suite exercises the first of them and the
#: refusal it asserts is unchanged. `base_url` is seeded on the manifest as the
#: PO's phase-1 placeholder address, so a connect need not type one.
CARD = "pay_invoicecloud"
CARD_FIELDS = {"merchant_id": "acct_1H8f2kL0", "merchant_secret": LOOKS_LIKE_A_KEY, "client_id": "sbh-web"}


@pytest.mark.django_db
def test_us_int_017_tc1_a_connect_on_a_coming_soon_key_is_refused_and_stores_nothing(
    brazos, dana, caplog, audit_rows
):
    caplog.set_level(logging.DEBUG)
    before = counts()
    response = post_connect(brazos, dana, CARD, CARD_FIELDS)
    assert response.status_code == 409
    assert response.data["code"] == "BIZ-STATE"
    assert response.data["message_key"] == services.REFUSAL_NOT_AVAILABLE
    assert response.data["params"]["wave"] == "W7"
    assert response.data["br_ref"] == "BR-INT-001"
    assert counts() == before, "a refused connect wrote a row"
    assert LOOKS_LIKE_A_KEY not in caplog.text, "the key reached a log line"
    assert LOOKS_LIKE_A_KEY not in json.dumps(response.data)
    assert LOOKS_LIKE_A_KEY not in str(audit_rows)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route",
    ["test", "run", "patch", "credential"],
)
def test_us_int_017_tc2_every_write_route_refuses_a_coming_soon_key_with_one_code(brazos, dana, route):
    before = counts()
    if route == "test":
        response = post_test(brazos, dana, CARD)
    elif route == "run":
        response = post_run(brazos, dana, CARD, "deliver_charge")
    elif route == "patch":
        response = patch_connection(brazos, dana, CARD, {"cadence": "hourly"})
    else:
        response = post_credential(brazos, dana, CARD, {"merchant_secret": LOOKS_LIKE_A_KEY})
    assert response.status_code == 409, route
    assert response.data["message_key"] == services.REFUSAL_NOT_AVAILABLE, route
    assert counts() == before, route


@pytest.mark.django_db
def test_us_int_017_tc2_delete_on_a_coming_soon_key_is_refused_too(brazos, dana):
    before = counts()
    response = delete_connection(brazos, dana, CARD)
    assert response.status_code == 409
    assert response.data["message_key"] == services.REFUSAL_NOT_AVAILABLE
    assert counts() == before


def test_us_int_017_tc3_the_refusal_is_six_words_names_no_rule_and_is_in_all_eleven_catalogues():
    en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    sentence = en[services.REFUSAL_NOT_AVAILABLE]
    assert len(sentence.split()) <= 6, sentence
    assert "BR-" not in sentence and "OQ-" not in sentence
    for code in ELEVEN:
        catalogue = json.loads((LOCALES / f"{code}.json").read_text(encoding="utf-8"))
        assert services.REFUSAL_NOT_AVAILABLE in catalogue, code
        assert catalogue[services.REFUSAL_NOT_AVAILABLE].strip(), code


@pytest.mark.django_db
def test_us_int_017_tc4_a_malformed_connect_on_a_live_key_stores_nothing_not_even_the_connection(
    brazos, dana, smtp_adapter
):
    before = counts()
    response = post_connect(brazos, dana, "email_smtp", {**SMTP_FIELDS, "port": "abc"})
    assert response.status_code == 422
    fields = {one["field"]: one["message_key"] for one in response.data["field_errors"]}
    assert fields == {"port": "integrations.field.port"}
    assert counts() == before, "a malformed connect wrote a partial row"


@pytest.mark.django_db
def test_us_int_017_tc4b_every_field_problem_is_named_in_one_pass(brazos, dana, smtp_adapter):
    response = post_connect(
        brazos,
        dana,
        "email_smtp",
        {"host": "https://smtp.example/x", "port": "70000", "username": "", "password": "", "send_from": "nope"},
    )
    assert response.status_code == 422
    fields = {one["field"]: one["message_key"] for one in response.data["field_errors"]}
    assert fields == {
        "host": "integrations.field.host",
        "port": "integrations.field.port",
        "username": "integrations.field.required",
        "password": "integrations.field.required",
        "send_from": "integrations.field.email",
    }
    assert counts() == {"connections": 0, "credentials": 0, "runs": 0}


@pytest.mark.django_db
def test_us_int_017_tc5_an_unknown_key_is_404_with_a_body_identical_to_any_absent_resource(brazos, dana):
    refused = post_connect(brazos, dana, "nope", {"x": 1})
    assert refused.status_code == 404
    absent = call(integrations_api.connection, "patch", brazos, dana, data={"cadence": "hourly"}, key="also-nope")
    assert absent.status_code == 404
    strip = lambda body: {k: v for k, v in body.items() if k != "trace_id"}  # noqa: E731
    assert strip(refused.data) == strip(absent.data)
    assert refused.data["code"] is None  # G4: no catalogue code exists for 404


@pytest.mark.django_db
def test_us_int_017_tc6_the_refusal_is_one_audit_row_with_the_key_and_the_wave_and_no_payload(
    brazos, dana, audit_rows
):
    post_connect(brazos, dana, CARD, CARD_FIELDS)
    rows = [one for one in audit_rows if one["action"] == services.AUDIT_CONNECT_REFUSED]
    assert len(rows) == 1
    after = rows[0]["after"]
    assert after["provider_key"] == CARD
    assert after["wave"] == "W7"
    assert "fields" not in after and "payload" not in after and "merchant_secret" not in after
    assert LOOKS_LIKE_A_KEY not in json.dumps(rows[0], default=str)


@pytest.mark.django_db
def test_us_int_017_a_billing_clerk_is_refused_server_side_regardless(brazos, marcus):
    before = counts()
    response = post_connect(brazos, marcus, CARD, CARD_FIELDS, role="billing_clerk")
    assert response.status_code == 403
    assert counts() == before


@pytest.mark.django_db
def test_us_int_017_a_live_key_with_no_adapter_bound_is_refused_and_stores_nothing(brazos, dana, audit_rows):
    """The running product's own state in wave B: every LIVE card's adapter is
    wave E's or later, and until it arrives (after core/crypto.py's sign-off)
    a connect is refused rather than a real credential stored."""
    before = counts()
    response = post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    assert response.status_code == 409
    assert response.data["message_key"] == services.REFUSAL_NOT_CONNECTABLE
    assert response.data["br_ref"] == "BR-INT-037"
    assert counts() == before
    assert SMTP_FIELDS["password"] not in str(audit_rows)
    en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    assert len(en[services.REFUSAL_NOT_CONNECTABLE].split()) <= 6
