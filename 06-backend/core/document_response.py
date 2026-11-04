# ── Trace ──────────────────────────────────────────────
# Change:   CR-158-BRC10 (the clerk opens a portal applicant's file) ·
#           DEF-CWP-9166 (2026-10-02 — the APPLICANT opens their own file
#           from the start-service form; PO: *"document upload is working but
#           user not able to view give view button"*)
# Rules:    B14 rule 43 — one piece of serving code, not a copy per door
# Impacts:  apps/customers/service_request_api.py · apps/customers/api.py ·
#           apps/portal/guest_api.py
# ───────────────────────────────────────────────────────
"""ONE way to hand a stored file back to a browser — the headers ARE the safety.

⚠ **MOVED HERE FROM `customers/service_request_api.py` ON 2026-10-02, UNCHANGED,
WHEN A SECOND MODULE NEEDED IT.** The portal's applicant now opens the file they
attached (`DEF-CWP-9166`), and the alternative was a second copy of the policy
string and the disposition builder in `apps/portal` — two places that could
disagree about whether a stranger's upload may run script. The customers module
re-exports both names, so every existing caller is unchanged.

Each header is there for a reason:

  * `Content-Disposition` — `inline` only where the caller says a browser may
    draw it (a PDF, PNG or JPEG asked for with `as=view`); everything else is
    `attachment`, so a browser saves it rather than rendering it;
  * `X-Content-Type-Options: nosniff` — the browser draws the type we declare
    and never guesses a more dangerous one from the bytes;
  * `Content-Security-Policy` — no script runs inside a served file;
  * `Cache-Control: private, no-store` — somebody's licence is not kept in a
    shared cache or on disk by the browser.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

#: The policy every served document carries. `default-src 'none'` forbids
#: script, frames, fetches and fonts outright, so nothing inside a served file
#: can run against the app's origin; `object-src 'self'` is what lets a
#: browser's own viewer still draw a PDF.
DOCUMENT_CSP = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; object-src 'self'; frame-ancestors 'self'"


def content_disposition(inline: bool, name: str) -> str:
    """`inline` or `attachment`, with the name in BOTH forms RFC 6266 gives.

    The plain `filename=` is ASCII with quotes and backslashes removed, so a
    name like `lease "final".pdf` cannot end the header early; `filename*=` is
    the exact name, percent-encoded UTF-8, which a modern browser prefers.
    """
    plain = "".join(ch for ch in name if 32 <= ord(ch) < 127 and ch not in '"\\;') or "document"
    disposition = "inline" if inline else "attachment"
    return f"{disposition}; filename=\"{plain}\"; filename*=UTF-8''{quote(name, safe='')}"


def document_http_response(*, payload: bytes, content_type: str, name: str, inline: bool) -> Any:
    """The file as an `HttpResponse`, carrying all four safety headers."""
    from django.http import HttpResponse

    response = HttpResponse(payload, content_type=content_type)
    response["Content-Disposition"] = content_disposition(inline, name)
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = DOCUMENT_CSP
    response["Cache-Control"] = "private, no-store"
    response["Content-Length"] = str(len(payload))
    return response
