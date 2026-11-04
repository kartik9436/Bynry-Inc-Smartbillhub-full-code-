# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-015 · 016 · 017 · 002 · 004 · 019 (CR-069 wave B) — the
#           fixtures the wave's backend tests share.
# Rules:    BR-INT-003 (the recorded fixture's password is asserted absent
#           from every exit) · hard-won law 2 (the fixtures bind a REAL
#           adapter class to the REAL registry, so the path under test is the
#           product's, not a mock of it)
# ───────────────────────────────────────────────────────
"""Shared fixtures for CR-069 wave B: a bound fixture adapter, a recording
dispatcher, a ready probe, and the request helpers.

Not a test module (no `test_` prefix on the name's stem after the
convention's `test_us_int_` marker? — it IS collected by pytest because of
the prefix, and holds no tests; that is deliberate so `from tests.
test_us_int_helpers_b import *` follows the same shape as
`test_us_met_helpers`).
"""

from __future__ import annotations

from typing import Any

import pytest

from apps.integrations import api as integrations_api
from apps.integrations import conformance, models
from apps.integrations.registry import REGISTRY
from apps.tenancy import models as tenancy_models
from core import jobs as core_jobs
from tests.test_us_ten_helpers import api_call

GOOD_PASSWORD = "Ew3!kQ9-lockbox"
BAD_PASSWORD = "hunter2 "
SMTP_FIELDS = {
    "host": "smtp.brazosbend.example",
    "port": "587",
    "username": "billing@brazosbend.example",
    "password": GOOD_PASSWORD,
    "send_from": "billing@brazosbend.example",
}
LOOKS_LIKE_A_KEY = "sk_live_51H8f2kL0pQz9xW3vT6yU1sR4"
RECIPIENT = "alex@brazosbend.example"


@pytest.fixture()
def smtp_adapter():
    """Bind the recorded SMTP fixture to the REAL registry for one test."""
    REGISTRY.register_adapter("email_smtp", conformance.RecordedSmtpAdapter)
    yield conformance.RecordedSmtpAdapter
    REGISTRY.unregister_adapter("email_smtp")


@pytest.fixture()
def microsoft_adapter():
    """Wave H — bind the recorded Microsoft mailbox for one test.

    The recording overrides only the two network methods, so every rule the
    adapter holds runs through the real class (see `RecordedOAuthMailboxAdapter`).
    `sent` is reset per test because it is class-level by necessity.
    """
    conformance.RecordedOAuthMailboxAdapter.sent = []
    REGISTRY.register_adapter("email_microsoft", conformance.RecordedOAuthMailboxAdapter)
    yield conformance.RecordedOAuthMailboxAdapter
    REGISTRY.unregister_adapter("email_microsoft")
    conformance.RecordedOAuthMailboxAdapter.sent = []


@pytest.fixture()
def lapsed_mailbox_adapter():
    """The same mailbox, with a consent the provider says is over."""
    conformance.LapsedMailboxAdapter.sent = []
    REGISTRY.register_adapter("email_microsoft", conformance.LapsedMailboxAdapter)
    yield conformance.LapsedMailboxAdapter
    REGISTRY.unregister_adapter("email_microsoft")


@pytest.fixture()
def bind_adapter():
    """Bind any fixture adapter under any live key, unbound afterwards."""
    bound: list[str] = []

    def bind(key: str, adapter_cls: type) -> None:
        REGISTRY.register_adapter(key, adapter_cls)
        bound.append(key)

    yield bind
    for key in bound:
        REGISTRY.unregister_adapter(key)


@pytest.fixture()
def ready_probe():
    """A worker IS listening — the question `dispatch_is_ready` asks."""
    previous = core_jobs._dispatch_probe
    core_jobs.set_dispatch_probe(lambda queue=None: (True, "test double"))
    yield
    core_jobs.set_dispatch_probe(previous)


@pytest.fixture()
def not_ready_probe():
    previous = core_jobs._dispatch_probe
    core_jobs.set_dispatch_probe(lambda queue=None: (False, "no worker on the queue"))
    yield
    core_jobs.set_dispatch_probe(previous)


@pytest.fixture()
def recording_dispatcher(ready_probe):
    """The transport double for US-INT-016 TC-1: at the moment it is handed a
    record it reads the `jobs` TABLE and writes down whether the row was
    already there. It publishes nothing — the record rests `queued` until a
    test calls `core_jobs.run_pending` itself."""
    seen: list[dict[str, Any]] = []

    def dispatch(record: dict[str, Any]) -> None:
        row = tenancy_models.Job.objects.filter(id=record["id"]).first()
        seen.append(
            {
                "id": record["id"],
                "kind": record["kind"],
                "row_existed": row is not None,
                "row_status": row.status if row is not None else None,
                "queue": core_jobs.job_queue(record["kind"]),
            }
        )

    previous = core_jobs._dispatcher
    core_jobs.set_job_dispatcher(dispatch)
    yield seen
    core_jobs.set_job_dispatcher(previous)


def call(view, method, tenant, actor, role="system_admin", *, data=None, **kwargs):
    return api_call(
        view,
        method,
        f"/api/{tenant.subdomain}/integrations",
        user=actor.user,
        role=role,
        tenant=tenant,
        data=data,
        **kwargs,
    )


def grid(tenant, actor, role="system_admin"):
    return call(integrations_api.integrations_grid, "get", tenant, actor, role).data


def card(tenant, actor, key):
    return next(one for one in grid(tenant, actor)["providers"] if one["key"] == key)


def post_connect(tenant, actor, key, fields, *, environment="production", cadence="nightly", label=None, role="system_admin"):
    body = {"environment": environment, "cadence": cadence, "fields": fields}
    if label is not None:
        body["label"] = label
    return call(integrations_api.connect, "post", tenant, actor, role, data=body, key=key)


def post_test(tenant, actor, key, recipient=RECIPIENT, role="system_admin"):
    body = {} if recipient is None else {"recipient": recipient}
    return call(integrations_api.test, "post", tenant, actor, role, data=body, key=key)


def patch_connection(tenant, actor, key, changes, role="system_admin"):
    return call(integrations_api.connection, "patch", tenant, actor, role, data=changes, key=key)


def delete_connection(tenant, actor, key, role="system_admin"):
    return call(integrations_api.connection, "delete", tenant, actor, role, key=key)


def post_credential(tenant, actor, key, fields, role="system_admin"):
    return call(integrations_api.credential, "post", tenant, actor, role, data={"fields": fields}, key=key)


def post_run(tenant, actor, key, operation, work=None, role="system_admin"):
    return call(
        integrations_api.run, "post", tenant, actor, role, data={"operation": operation, "work": work or []}, key=key
    )


def counts() -> dict[str, int]:
    """Every row in the two tables a refusal must leave untouched."""
    return {
        "connections": models.IntegrationConnection.objects.count(),
        "credentials": models.IntegrationCredential.objects.count(),
        "runs": models.IntegrationRun.objects.count(),
    }


def run_job(record_or_body) -> None:
    """Run a queued job the way the worker would (`core.jobs.run_pending`)."""
    job_id = record_or_body["job_id"] if "job_id" in record_or_body else record_or_body["id"]
    core_jobs.run_pending(job_id)
