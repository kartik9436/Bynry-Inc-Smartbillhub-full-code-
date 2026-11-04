# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 task `P4.14`
#          (*"BI tier 2 — scheduled delivery"*), brief p015 and §7.8 p088–p090,
#          read as IMAGES per B14 rule 42.
# Rules:   **RULED, p090, FINAL:** *"A scheduled file may leave the product —
#          Yes — admin-set destinations, encrypted in transit, every delivery
#          logged."* · CLAUDE.md hard rule 1 (tenant scoping — this route is
#          the ONE place in reports that opens a tenant from something other
#          than a session, and it does so from a SIGNED claim) · HR-1/G4 (one
#          404 for every no; existence must not leak) · hard-won law 3
#          (defaults fail closed) · law 7 (prove a guard RED first)
# Tests:   06-backend/tests/test_cr142_p4_14_signed_delivery.py
# Impacts: config/urls.py (one platform route) · apps/reports/signed_links.py
# ───────────────────────────────────────────────────────
"""THE ONE UNAUTHENTICATED ROUTE IN `reports`, AND WHY IT IS SAFE.

`GET /api/reports/delivery/{token}` streams ONE report artifact to a machine
that holds a link the scheduler minted. There is no session, no cookie and no
role — which is exactly why everything this route trusts is INSIDE a signature
it verifies before reading anything else.

⚠ **A SEPARATE FILE AND A PLATFORM PATH, NOT A ROUTE IN `apps/reports/api.py`.**
Two reasons, and the second is the load-bearing one:
  · `api.py`'s `urlpatterns` are spliced by INDEX at the bottom of that file
    (*"`_CATCH_ALL` is re-computed and not reused"*), so appending to it is
    the one edit there that is genuinely fragile.
  · **Every route in `api.py` sits under the tenant prefix `/{utility}/…` and
    this one must not.** A BI tool is handed a URL and told to fetch it; a
    utility slug in that URL is a second, unsigned assertion about which tenant
    the caller wants, sitting beside the signed one. `/api/jobs/{id}`,
    `/api/exports/{id}/file` and the partner surface are all no-tenant platform
    paths for the same family of reason, and the partner one says it in the
    PO's own words: *"we agreed not to use utility names in partner apis"*.

WHAT IT CHECKS, IN ORDER, AND WHY THE ORDER IS THE DESIGN
─────────────────────────────────────────────────────────
  1 · the SIGNATURE, before the payload is read as anything but bytes. Reading
      `exp` out of an unverified body and honouring it is how a verifier ends
      up trusting an attacker's expiry.
  2 · the EXPIRY, against the clock.
  3 · the TENANT — the context is opened from the signed `t` claim and from
      nothing the caller said.
  4 · the JOB — and, inside that tenant's context, RLS and the `jobs` read
      decide whether this artifact exists at all. **A token for tenant A and a
      job belonging to tenant B resolves to nothing**, because the lookup
      happens inside A's context; the two are not compared by hand, which is
      the check somebody would eventually forget.

⚠ **ONE 404 FOR EVERY NO.** A malformed token, a forged signature, an expired
link, a job that never existed, a job whose file was swept by `BR-REP-018`'s
retention, and a token naming another tenant's job all answer byte-identically.
`tenancy.api.export_file` takes the same posture over its own five noes and
says why: distinguishing them tells a holder which half of their guess was
right, and a 403 leaks it loudest.

⚠ **THE LINK IS A CREDENTIAL AND THE RESPONSE SAYS SO TO EVERY CACHE.** A
shared proxy that stored this body would hand the file to the next caller of
the same URL, which is a different reader with no link at all.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from django.http import StreamingHttpResponse
from django.urls import path
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny

from core import errors
from core.tenancy import stream_within_tenant_context, tenant_context

from apps.reports import signed_links


@api_view(["GET"])
# ⚠ **BOTH, AND `authentication_classes([])` IS THE HALF THAT MATTERS.**
# `IdentitySessionAuthentication` is the DRF DEFAULT in this product
# (config/settings/base.py), so without this line a machine presenting a stale
# cookie alongside its link would enter THAT session's tenant context — a
# second, unsigned assertion about who is asking. The four public tenancy
# endpoints opt out for the same reason and record it.
@authentication_classes([])
@permission_classes([AllowAny])
def delivery_file(request: Any, token: str) -> Any:
    """`GET /api/reports/delivery/{token}` — the file, once the link checks out."""
    from apps.tenancy import export_store, exports, selectors

    now = datetime.now(tz=UTC)
    # Raises `NotFoundError` on a bad prefix, a forged signature, a malformed
    # body or an expired link — one refusal for all four.
    claim = signed_links.verify(token, now=now)

    with tenant_context(claim["tenant_id"]):
        # Inside the SIGNED tenant's context, so RLS is what answers *is this
        # job yours* — never a comparison this function performs.
        row = exports.resolve_artifact(selectors.job_artifact(claim["job_id"]))
    if row is None:
        raise errors.NotFoundError()

    # ⚠ STREAMED FROM S3, NOT REDIRECTED (PO-approved design, 2026-10-02). The
    # in-app Download button redirects to a signed link; THIS route answers a
    # machine, and a machine client that does not follow redirects would read
    # a 302 as a failure — so the contract stays "the body is the file". The
    # bytes come from the export store through the file's `job_artifacts` row;
    # the body re-enters the signed tenant's context (G58) although it reads no
    # rows, so the rule stays one shape everywhere.
    response = StreamingHttpResponse(
        stream_within_tenant_context(claim["tenant_id"], export_store.stream(row)),
        content_type=row.content_type,
    )
    # The artifact's own IS-11 name, never recomposed — `export_file` says why.
    response["Content-Disposition"] = f'attachment; filename="{row.display_name}"'
    if row.byte_length is not None:
        response["Content-Length"] = str(row.byte_length)
    # See the module docstring: this body is addressed by a credential.
    response["Cache-Control"] = "no-store, private"
    return response


urlpatterns = [
    path("api/reports/delivery/<str:token>", delivery_file),
]

# gates: pytest tests/test_cr142_p4_14_signed_delivery.py
# exceptions: this is the only route in `reports` with no authentication class.
#   Everything it trusts is inside a signature it verifies first, and the
#   module docstring lists the four checks in the order they run.
# status: VERIFIED-UNRATIFIED
