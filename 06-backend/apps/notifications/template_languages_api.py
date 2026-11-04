# ── Trace ──────────────────────────────────────────────
# Change:   CR-199-BRC10 lane TPL-SRV-LANG (task S8, the count half)
# Rules:    BR-NOT-006 as amended 2026-10-29 (PO option B — a message goes in
#           the customer's preferred language) · CLAUDE.md rule 1 (tenant
#           scoping) · NFR-3/NFR-5 (an aggregate; no cap, no unpaginated list)
# Tests:    06-backend/tests/test_cr199_messages_follow_the_customers_language.py
# Impacts:  config/urls.py inclusion · the Templates screen's language line
#           (drawing `05-prototype/templates-redesign-2026-10-29/images/16-spanish.png`)
# ───────────────────────────────────────────────────────
"""`GET /template-languages` — how many customers prefer each language.

THIN by law (B8 / LAW 0): parse → call → serialize. The fold is
`message_language.customers_by_language`, one grouped statement over accounts
read through customers' own selector; this route knows about HTTP and nothing
else.

A literal path of its own rather than a segment under `template-catalog/`,
because `template-catalog/<str:code>` would read any word put there as a
message class.
"""

from __future__ import annotations

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.notifications import message_language
from core.permissions import AnyTenantRole
from core.tenancy import require_tenant


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def template_languages(request: Any) -> Response:
    """`{default_language, languages: [{language, accounts, is_default,
    no_preference}], total}` for the tenant in context."""
    require_tenant(request)
    return Response(message_language.customers_by_language())


urlpatterns = [
    path("template-languages", template_languages),
]
