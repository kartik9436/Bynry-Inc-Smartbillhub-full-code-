# ── Trace ──────────────────────────────────────────────
# Change:   CR-169-BRC10 §2 row 9 (PO 2026-10-04) — business events sent from
#           the server AFTER COMMIT, off without a key, never to another
#           environment's project, no PII.
# Code:     config/product_analytics.py · payments/services.py record_payment ·
#           billing/issue.py finish_issue_pass · metering/connections.py
#           submit_field_result
# ───────────────────────────────────────────────────────
"""Server-side product analytics: the four rules `config/product_analytics.py`
keeps, each with a case, and the payment path proving rule 3 end to end.

RED FIRST: written before `config/product_analytics.py` existed; the first run
failed at collection on `ModuleNotFoundError: No module named
'config.product_analytics'`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction
from django.test import override_settings

from apps.payments import services as payment_services
from config import product_analytics

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

POSTED_AT = datetime(2026, 8, 18, 10, 30, tzinfo=UTC)

PROD_KEY = "phc_production_key_for_tests"
DEV_KEY = "phc_dev_key_for_tests"


class FakeClient:
    def __init__(self) -> None:
        self.captured: list[tuple[str, dict[str, Any]]] = []

    def capture(self, event: str, **kwargs: Any) -> None:
        self.captured.append((event, kwargs))


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    client = FakeClient()
    monkeypatch.setattr(product_analytics, "client_factory", lambda key, host: client)
    product_analytics.reset_for_tests()
    yield client
    product_analytics.reset_for_tests()


ON = {
    "POSTHOG_KEY": DEV_KEY,
    "POSTHOG_ENVIRONMENT": "dev",
    "POSTHOG_PROD_KEY_FINGERPRINT": product_analytics.fingerprint(PROD_KEY),
}


# ── rule 1 · off unless configured ───────────────────────────────────────────
@override_settings(POSTHOG_KEY="", POSTHOG_ENVIRONMENT="dev")
def test_cr169__no_key_sends_nothing_and_builds_no_client(fake: FakeClient) -> None:
    assert product_analytics.send_now("work_order_completed", tenant_id=None) is False
    assert fake.captured == []


@override_settings(POSTHOG_KEY=DEV_KEY, POSTHOG_ENVIRONMENT="")
def test_cr169__a_key_with_no_environment_is_off(fake: FakeClient) -> None:
    assert product_analytics.send_now("work_order_completed", tenant_id=None) is False
    assert fake.captured == []


# ── rule 2 · never another environment's project ─────────────────────────────
@override_settings(
    POSTHOG_KEY=PROD_KEY,
    POSTHOG_ENVIRONMENT="sandbox",
    POSTHOG_PROD_KEY_FINGERPRINT=product_analytics.fingerprint(PROD_KEY),
)
def test_cr169__a_sandbox_server_handed_the_production_key_refuses(fake: FakeClient) -> None:
    assert product_analytics.send_now("work_order_completed", tenant_id=None) is False
    assert fake.captured == []


@override_settings(
    POSTHOG_KEY=PROD_KEY,
    POSTHOG_ENVIRONMENT="production",
    POSTHOG_PROD_KEY_FINGERPRINT=product_analytics.fingerprint(PROD_KEY),
)
def test_cr169__production_sends_with_its_own_key_and_says_so(fake: FakeClient) -> None:
    assert product_analytics.send_now("work_order_completed", tenant_id=None, properties={"source": "field"})
    event, kwargs = fake.captured[0]
    assert event == "work_order_completed"
    assert kwargs["properties"]["environment"] == "production"
    assert kwargs["distinct_id"] == "server"


# DEF-TEN-9651 — the server failed OPEN where the web build fails closed.
@override_settings(POSTHOG_KEY=PROD_KEY, POSTHOG_ENVIRONMENT="sandbox", POSTHOG_PROD_KEY_FINGERPRINT="")
def test_def_ten_9651__a_key_with_no_fingerprint_is_off(fake: FakeClient) -> None:
    assert product_analytics.send_now("work_order_completed", tenant_id=None) is False
    assert fake.captured == []


@override_settings(
    POSTHOG_KEY=DEV_KEY,
    POSTHOG_ENVIRONMENT="production",
    POSTHOG_PROD_KEY_FINGERPRINT=product_analytics.fingerprint(PROD_KEY),
)
def test_def_ten_9651__a_production_server_with_another_key_is_off(fake: FakeClient) -> None:
    assert product_analytics.send_now("work_order_completed", tenant_id=None) is False
    assert fake.captured == []


def test_cr169__fingerprint_matches_the_front_end_spelling() -> None:
    # 07-frontend/scripts/deployConfig.mjs keyFingerprint: sha256 hex, first 16.
    import hashlib

    assert product_analytics.fingerprint("abc") == hashlib.sha256(b"abc").hexdigest()[:16]


# ── rule 4 · allow-list, no PII ──────────────────────────────────────────────
def test_cr169__unknown_property_and_non_scalar_are_dropped() -> None:
    cleaned = product_analytics.clean_properties(
        "payment_recorded",
        {"method": "check", "amount": "247.30", "account": "AC-2026-00012", "cleared": True, "x": {"a": 1}},
    )
    assert cleaned == {"method": "check", "cleared": True}


def test_cr169__unknown_event_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="EVENTS"):
        product_analytics.clean_properties("payment_amount_seen", {})


# ── rule 3 · after commit, never inside it ───────────────────────────────────
@pytest.mark.django_db(transaction=True)
@override_settings(**ON)
def test_cr169__a_rolled_back_transaction_sends_nothing(fake: FakeClient) -> None:
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            product_analytics.capture_after_commit("work_order_completed", tenant_id=None)
            raise RuntimeError("the money path failed")
    assert fake.captured == []


@pytest.mark.django_db(transaction=True)
@override_settings(**ON)
def test_cr169__a_committed_transaction_sends_once_and_only_after_commit(fake: FakeClient) -> None:
    with transaction.atomic():
        product_analytics.capture_after_commit("work_order_completed", tenant_id=None, dedupe_key="o1")
        assert fake.captured == [], "sent while the transaction was still open"
    assert len(fake.captured) == 1
    assert fake.captured[0][1]["uuid"]


@pytest.mark.django_db
@override_settings(**ON)
def test_cr169__recording_a_payment_sends_payment_recorded_with_no_amount(
    fake: FakeClient, brazos: Any, marcus: Any, django_capture_on_commit_callbacks: Any
) -> None:
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        with django_capture_on_commit_callbacks(execute=True):
            result = payment_services.record_payment(
                marcus,
                account_id=account.pk,
                amount=Decimal("247.30"),
                posted_at=POSTED_AT,
                cleared_at=POSTED_AT,
                method_code="check",
                confirmation="4471",
            )
    sent = [kwargs for event, kwargs in fake.captured if event == "payment_recorded"]
    assert len(sent) == 1
    properties = sent[0]["properties"]
    assert properties["method"] == "check"
    assert properties["cleared"] is True
    assert properties["tenant"] == brazos.subdomain
    assert sent[0]["groups"] == {"tenant": brazos.subdomain}
    assert sent[0]["distinct_id"] == str(marcus.pk)
    flat = repr(sent)
    for secret in ("247.30", "4471", str(account.pk), result.payment_no):
        assert secret not in flat
