# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-INT-10019 (PO report 2026-10-07 — the City of Ann Arbor's
#           Cloudflare refused every request with 403 "error code: 1010")
# Ruling:   decision log 2026-10-07, "PO RULING — EVERY CITY MAP REQUEST CARRIES
#           `User-Agent: SMARTBillHub-GIS/<product version> (support@bynry.io)`
#           FROM ONE FUNCTION …"
# Tests:    06-backend/tests/test_def_int_10019_gis_user_agent.py
# Impacts:  apps/integrations/gis_layer.py · apps/integrations/adapters/gis_city.py ·
#           apps/integrations/adapters/geocoder_census.py · apps/metering/geocode.py
# ───────────────────────────────────────────────────────
"""THE ONE PLACE A MAP OR ADDRESS SERVICE IS DIALLED FROM OUR SERVER.

WHY THIS FILE EXISTS (DEF-INT-10019)
------------------------------------
Every address search and every parcel check against the City of Ann Arbor
answered *"The city rejected our key"* — on a connection that stores no key.
The PO proved the cause on the live server: Python's `urllib` sends
``User-Agent: Python-urllib/3.x``, the City's Cloudflare refuses that agent with
``403`` and the body ``error code: 1010``, the same URL with
``User-Agent: SMARTBillHub-GIS/1.0 (support@bynry.io)`` answers ``200`` with
features. Three files each had their own ``urlopen`` and none set a header, so
the fix was always going to be three fixes unless it became one.

PO, verbatim in substance: *every request to a city's ArcGIS service sends*
``User-Agent: SMARTBillHub-GIS/<product version> (support@bynry.io)``;
*"Do not copy or spoof a browser signature"*; *find every place that fetches a
GIS URL and make ONE function set the header.*

So: :func:`fetch_json` is the only ``urlopen`` for GIS and geocoding, and
:func:`gis_request` is the only place the header is written.
``tests/test_def_int_10019_gis_user_agent.py`` fails if any file on those paths
calls ``urlopen`` itself, so a fourth fetcher goes red rather than going around.

⚠ **WE NAME OURSELVES, WE NEVER PRETEND TO BE A BROWSER.** A Chrome agent also
gets a 200 from that Cloudflare — the PO measured it — and is exactly what we
must not send: a city's firewall team allow-lists a product by its honest name
and has a support address to write to when it misbehaves.

⚠ **THE VERSION IS READ, NEVER WRITTEN HERE.** ``core.diagnostics.release()`` —
a deployment's ``PRODUCT_VERSION`` stamp, else ``pyproject.toml``'s version, which
moves on every release (`13-change-process.md` step 7). A literal here would be
one more copy of the release number for a human to keep in step.

THE BODY OF A REFUSAL IS EVIDENCE
---------------------------------
A ``403`` from ArcGIS carries ArcGIS JSON (``{"error": {...}}``); a ``403`` from a
firewall in front of it carries ``error code: 1010`` or a *Just a moment…* page.
The status alone cannot tell the two apart, and reading every ``403`` as *our
key* sent a utility to rotate a credential it does not have.
:func:`error_body` reads the body of an ``HTTPError`` (bounded, never raising) so
the classifier and the run row can see who refused us.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

#: Where a city's GIS or firewall team writes when our requests misbehave.
CONTACT = "support@bynry.io"
#: The product token. `GIS` says which part of the product is calling.
PRODUCT_TOKEN = "SMARTBillHub-GIS"

#: How much of a refusal's body is read off the wire. A firewall page is a few
#: kilobytes; reading more would only hold memory for text nobody keeps.
BODY_READ_LIMIT = 4096
#: How much of it is KEPT on the run row — the PO's number.
EVIDENCE_CHARS = 200


def user_agent() -> str:
    """``SMARTBillHub-GIS/<product version> (support@bynry.io)`` — exactly."""
    from core import diagnostics

    return f"{PRODUCT_TOKEN}/{diagnostics.release()} ({CONTACT})"


def gis_request(url: str) -> urllib.request.Request:
    """The request every GIS or geocoder fetch sends. The header lives HERE only."""
    return urllib.request.Request(  # noqa: S310 — https, built by our own URL builders
        url,
        headers={"User-Agent": user_agent(), "Accept": "application/json"},
        method="GET",
    )


def fetch_json(url: str, timeout_s: float) -> Any:
    """url → parsed JSON. THE ONE ``urlopen`` on the GIS and geocoder paths.

    Every ``_urllib_transport`` on those paths is one line that calls this, so
    the injected-transport seam each adapter has (tests pass a fake ``send``)
    is untouched: only the LIVE default changed.
    """
    with urllib.request.urlopen(gis_request(url), timeout=timeout_s) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def error_body(exc: BaseException) -> str:
    """The body of an ``HTTPError``, read once, bounded, decoded safely — or ``""``.

    Never raises: a refusal whose body cannot be read is still a refusal, and
    the classifier then falls back to the status alone. The text is cached on
    the exception so a second reader (the classifier, then the run row) sees
    the same words instead of an already-drained stream.
    """
    cached = getattr(exc, "_smartbillhub_body", None)
    if isinstance(cached, str):
        return cached
    text = ""
    try:
        raw = exc.read(BODY_READ_LIMIT) if hasattr(exc, "read") else b""  # type: ignore[attr-defined]
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
        elif isinstance(raw, str):
            text = raw
    except Exception:  # noqa: BLE001 — an unreadable body is an empty one
        text = ""
    try:
        setattr(exc, "_smartbillhub_body", text)
    except Exception:  # noqa: BLE001
        pass
    return text


def is_arcgis_error(body: Any) -> bool:
    """Is this ArcGIS's own voice — a JSON object carrying an ``error``?

    A firewall page, a CDN's one-liner and an empty body are not, and that is
    the whole distinction between *the City refused our key* and *something in
    front of the City refused us*.
    """
    if isinstance(body, dict):
        return "error" in body
    try:
        parsed = json.loads(str(body or ""))
    except (TypeError, ValueError):
        return False
    return isinstance(parsed, dict) and "error" in parsed


def is_json_object(body: Any) -> bool:
    """Does this body parse as a JSON object at all — a service's own voice?

    The Census geocoder is not ArcGIS and answers its errors as
    ``{"errors": [...]}``; for it, *any* JSON object is the service speaking and
    anything else in a ``403`` is something in front of it.
    """
    try:
        return isinstance(json.loads(str(body or "")), dict)
    except (TypeError, ValueError):
        return False


def evidence(status: Any, body: Any) -> str:
    """``"<status>, <first 200 characters of the body>"`` — e.g. ``403, error code: 1010``.

    What the run row keeps so the next person understands a refusal without
    access to the server. Whitespace is folded so an HTML page reads as one line;
    ``services.finish_run`` scrubs it before it is stored.
    """
    if isinstance(body, (dict, list)):
        text = json.dumps(body, separators=(",", ":"))
    else:
        text = str(body or "")
    text = " ".join(text.split())[:EVIDENCE_CHARS]
    return f"{status}, {text}" if text else f"{status}"


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-INT-10019 (decision log 2026-10-07, the PO's Cloudflare 403 ruling)
# generated: 2026-10-07 by the GIS-CF403 lane
# checklist: A✔ B=n/a(no screen) C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_def_int_10019_gis_user_agent.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
