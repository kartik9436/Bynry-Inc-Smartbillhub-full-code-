# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-INT-9707 — on a two-host deployment the API refused to be framed
#          by the app (frame-ancestors 'self'), so the bill layout previews
#          read "refused to connect". Found by lane LOGO, 2026-10-05.
# ───────────────────────────────────────────────────────
"""The API's documents may be framed by the app origins it already trusts — and nobody else."""

from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from apps.integrations.middleware import PagePolicyMiddleware


def _ancestors(origins):
    with override_settings(CORS_ALLOWED_ORIGINS=origins):
        response = PagePolicyMiddleware(lambda request: HttpResponse(b"%PDF-"))(
            RequestFactory().get("/api/brazosbend/bill-templates/layouts/x/preview.pdf")
        )
    header = response["Content-Security-Policy"]
    directive = next(p.strip() for p in header.split(";") if p.strip().startswith("frame-ancestors"))
    return directive.split()[1:]


def test_def_int_9707__the_app_origin_may_frame_the_api():
    assert _ancestors(["https://app-dev.bynry.com"]) == ["'self'", "https://app-dev.bynry.com"]


def test_def_int_9707__nothing_else_may_and_never_a_wildcard():
    assert _ancestors([]) == ["'self'"]
    assert "*" not in _ancestors(["https://app-dev.bynry.com"])


def test_def_int_9707__a_malformed_origin_is_not_written_into_the_header():
    assert _ancestors(["https://app.bynry.com; script-src *"]) == ["'self'"]
