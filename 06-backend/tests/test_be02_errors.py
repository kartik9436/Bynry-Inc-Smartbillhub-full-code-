# ── Trace ──────────────────────────────────────────────
# Component: BE-02 tests (core/errors.py) — envelope shape, HTTP mapping, 404-never-403,
#            attempt-row wiring (BR-AUD-018). No DB, no live endpoints.
# ───────────────────────────────────────────────────────
"""BE-02 unit tests: every error the platform can answer renders the one
ratified envelope {code, message_key, params, field_errors, br_ref, trace_id}
at the HTTP status the B12 r1 series table assigns."""

import uuid

import pytest
from django.test import override_settings
from django.http import Http404
from rest_framework import exceptions as drf_exceptions

from core import audit as core_audit
from core import errors

ENVELOPE_KEYS = {"code", "message_key", "params", "field_errors", "br_ref", "trace_id"}
TENANT = uuid.UUID("00000000-0000-0000-0000-00000000000a")


class FakeUser:
    def __init__(self, user_id=None):
        self.id = user_id
        self.is_authenticated = user_id is not None


class FakeRequest:
    def __init__(self, user=None, method="POST", path="/api/x"):
        self.user = user or FakeUser()
        self.method = method
        self.path = path


def handle(exc, request=None):
    return errors.drf_exception_handler(exc, {"request": request or FakeRequest()})


@pytest.fixture(autouse=True)
def no_audit_sink():
    core_audit.set_audit_sink(None)
    yield
    core_audit.set_audit_sink(None)


@pytest.fixture()
def captured_attempts(monkeypatch):
    """Tenant context + capturing sink so BR-AUD-018 rows can be observed."""
    rows = []
    monkeypatch.setattr(core_audit, "current_tenant_id", lambda: TENANT)
    core_audit.set_audit_sink(rows.append)
    return rows


# ── the envelope shape is universal ─────────────────────────────────────────
@pytest.mark.parametrize(
    "exc",
    [
        errors.AuthError(errors.AUTH_UNAUTHENTICATED),
        errors.ValidationError(errors.VAL_UOM_MISMATCH),
        errors.BizError(errors.BIZ_IMMUTABLE, br_ref="BR-BIL-004"),
        errors.SysError(errors.SYS_PROVIDER),
        errors.NotFoundError(),
        Http404(),
        drf_exceptions.NotAuthenticated(),
        drf_exceptions.PermissionDenied(),
        drf_exceptions.ValidationError({"amount": ["Required."]}),
        drf_exceptions.Throttled(wait=30),
        drf_exceptions.MethodNotAllowed("PUT"),
        drf_exceptions.ParseError(),
        RuntimeError("anything unexpected"),
    ],
)
def test_be02_tc01_every_answer_is_the_six_key_envelope(exc):
    response = handle(exc)
    assert set(response.data.keys()) == ENVELOPE_KEYS
    assert response.data["trace_id"]  # always present, always non-empty


# ── catalog constants + construction guards ─────────────────────────────────
def test_be02_tc02_http_mapping_follows_b12_r1():
    # 409 = conflicts row (immutable/idempotent/locked/state); 422 = semantic refusals.
    assert errors.HTTP_STATUS_BY_CODE[errors.BIZ_IMMUTABLE] == 409
    assert errors.HTTP_STATUS_BY_CODE[errors.BIZ_IDEMPOTENT] == 409
    assert errors.HTTP_STATUS_BY_CODE[errors.BIZ_LOCKED] == 409
    assert errors.HTTP_STATUS_BY_CODE[errors.BIZ_STATE] == 409
    assert errors.HTTP_STATUS_BY_CODE[errors.BIZ_CAP] == 422  # 11b G11
    assert errors.HTTP_STATUS_BY_CODE[errors.BIZ_SOD] == 422
    assert errors.HTTP_STATUS_BY_CODE[errors.AUTH_UNAUTHENTICATED] == 401
    assert errors.HTTP_STATUS_BY_CODE[errors.AUTH_PERMISSION_DENIED] == 403
    assert all(errors.HTTP_STATUS_BY_CODE[c] == 422 for c in errors.VAL_CODES)
    assert errors.HTTP_STATUS_BY_CODE[errors.SYS_PROVIDER] == 503


def test_be02_tc03_an_invented_code_cannot_be_constructed():
    with pytest.raises(ValueError):
        errors.ApiError("MADE-UP-CODE")
    with pytest.raises(ValueError):
        errors.AuthError(errors.BIZ_IMMUTABLE)  # wrong class family, refused too


def test_be02_tc04_biz_error_requires_its_br_ref():
    # B8: every BIZ refusal carries its BR-ID.
    with pytest.raises(TypeError):
        errors.BizError(errors.BIZ_IMMUTABLE)  # type: ignore[call-arg]
    response = handle(errors.BizError(errors.BIZ_IMMUTABLE, br_ref="BR-BIL-004"))
    assert response.status_code == 409
    assert response.data["br_ref"] == "BR-BIL-004"
    assert response.data["code"] == "BIZ-IMMUTABLE"


def test_be02_tc05_caller_message_key_and_params_pass_through():
    # `billing.run.not_draftable` is illustrative and has no catalogue entry:
    # this case asserts that a caller's key and params reach the envelope
    # UNCHANGED, and any two strings would do. core/refusal_catalogue refuses an
    # unresolved key under the test settings, so it is off for this construction.
    with override_settings(REFUSAL_KEYS_MUST_RESOLVE=False):
        exc = errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-BIL-023",
            message_key="billing.run.not_draftable",
            params={"run": "08-A"},
        )
    response = handle(exc)
    assert response.data["message_key"] == "billing.run.not_draftable"
    assert response.data["params"] == {"run": "08-A"}


# ── 404-never-403: absent and cross-tenant are indistinguishable ────────────
def test_be02_tc06_cross_tenant_body_equals_plain_absent_body():
    plain = handle(errors.NotFoundError())
    denied = handle(errors.deny_as_not_found())
    assert plain.status_code == denied.status_code == 404

    def strip(d):
        return {k: v for k, v in d.items() if k != "trace_id"}

    assert strip(plain.data) == strip(denied.data)  # byte-identical minus trace_id
    assert denied.data["br_ref"] is None  # the rule never serializes (no leak)
    assert denied.data["code"] is None  # no invented catalog code for 404 (G1)


def test_be02_tc07_django_and_drf_not_found_map_the_same():
    for exc in (Http404(), drf_exceptions.NotFound()):
        response = handle(exc)
        assert response.status_code == 404
        assert response.data["code"] is None


# ── auth mapping ────────────────────────────────────────────────────────────
def test_be02_tc08_unauthenticated_is_401_auth_001():
    for exc in (drf_exceptions.NotAuthenticated(), drf_exceptions.AuthenticationFailed()):
        response = handle(exc)
        assert (response.status_code, response.data["code"]) == (401, "AUTH-001")


def test_be02_tc09_in_tenant_role_denial_is_403_auth_002():
    response = handle(drf_exceptions.PermissionDenied())
    assert (response.status_code, response.data["code"]) == (403, "AUTH-002")
    assert response.data["br_ref"] == "BR-IDN-009"


# ── validation mapping ──────────────────────────────────────────────────────
def test_be02_tc10_drf_validation_becomes_val_field_errors():
    detail = {
        "amount": [drf_exceptions.ErrorDetail("Required.", code="required")],
        "unit": [drf_exceptions.ErrorDetail("Bad choice.", code="invalid_choice")],
    }
    response = handle(drf_exceptions.ValidationError(detail))
    assert response.status_code == 422
    by_field = {fe["field"]: fe["code"] for fe in response.data["field_errors"]}
    assert by_field == {"amount": "VAL-001", "unit": "VAL-005"}
    assert response.data["code"] in ("VAL-001", "VAL-005")  # top code from the details


# ── throttling + malformed ──────────────────────────────────────────────────
def test_be02_tc11_throttled_is_429_with_retry_after():
    response = handle(drf_exceptions.Throttled(wait=30))
    assert response.status_code == 429
    assert response["Retry-After"] == "30"


def test_be02_tc12_parse_error_is_400_method_not_allowed_405():
    assert handle(drf_exceptions.ParseError()).status_code == 400
    assert handle(drf_exceptions.MethodNotAllowed("PUT")).status_code == 405
    assert handle(drf_exceptions.UnsupportedMediaType("application/zip")).status_code == 415


# ── 500 leaks nothing ───────────────────────────────────────────────────────
def test_be02_tc13_unexpected_exception_is_sys_internal_with_no_internals():
    secret = "connection to db-prod-7 refused for user svc_billing"
    response = handle(RuntimeError(secret))
    assert (response.status_code, response.data["code"]) == (500, "SYS-INTERNAL")
    assert secret not in str(response.data)  # trace_id only, no internals (r1 5xx row)


# ── BR-AUD-018 attempt rows, written centrally ──────────────────────────────
def test_be02_tc14_biz_refusal_writes_one_attempt_row(captured_attempts):
    handle(
        errors.BizError(errors.BIZ_IMMUTABLE, br_ref="BR-BIL-004"),
        request=FakeRequest(user=FakeUser(user_id=42)),
    )
    assert len(captured_attempts) == 1
    row = captured_attempts[0]
    assert row["action"] == core_audit.REFUSAL_ATTEMPT_ACTION
    assert row["actor_user_id"] == 42
    assert row["after"]["code"] == "BIZ-IMMUTABLE"
    assert row["after"]["br_ref"] == "BR-BIL-004"
    assert row["before"] is None  # terminal event, no prior state


def test_be02_tc15_permission_denial_and_cross_tenant_denial_write_rows(captured_attempts):
    handle(drf_exceptions.PermissionDenied())
    handle(errors.deny_as_not_found(br_ref="BR-TEN-003"))
    assert [r["after"]["code"] for r in captured_attempts] == ["AUTH-002", "AUTH-002"]
    assert captured_attempts[1]["after"]["br_ref"] == "BR-TEN-003"


def test_be02_tc16_plain_404_and_val_errors_write_no_attempt_row(captured_attempts):
    handle(errors.NotFoundError())  # genuinely absent — not a refusal
    handle(drf_exceptions.ValidationError({"amount": ["Required."]}))  # input error
    handle(drf_exceptions.NotAuthenticated())  # not in the BR-AUD-018 list
    assert captured_attempts == []


def test_be02_tc17_attempt_row_failure_never_masks_the_refusal(monkeypatch):
    monkeypatch.setattr(core_audit, "current_tenant_id", lambda: TENANT)

    def exploding_sink(row):
        raise RuntimeError("audit store down")

    core_audit.set_audit_sink(exploding_sink)
    response = handle(errors.BizError(errors.BIZ_LOCKED, br_ref="BR-TEN-042"))
    assert response.status_code == 409  # the lawful refusal still answered


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-02@87ece49 (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-01..BE-05)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ black✔ pytest 29/29✔ (this file) · suite 92/92✔ · run_gates 10-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
# exceptions: none stubbed; E2-candidates reported to the PO batch via the build report (404/40x codes absent from the B12 §3 catalog · BR-AUD-018 attempt-row event code pending SC-3 · G7 guard list lacks core/tenancy.py)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
