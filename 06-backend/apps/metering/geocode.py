# ── Trace ──────────────────────────────────────────────
# Change:   CR-028 AST-W5 T3 (B16 §4.6 · §10-D6 RULED 2026-08-22: "third-party
#           tiles accepted + a geocoder to be picked — the selection is an
#           engineering decision recorded at build")
# Rules:    §10-D6 (the acceptance) · CLAUDE.md rule 1 (tenant scoping — every
#           write here runs inside the caller's tenant context) · rule 7 is
#           N/A (coordinates are not money and post nothing)
# Tests:    06-backend/tests/test_cr028_new_tabs.py (stubbed transport ONLY —
#           no test touches the network; the command is the live path)
# Impacts:  apps/metering/models.py (premises.lat/lng, migration 0018) ·
#           management/commands/geocode_premises.py · the sample seed writes
#           coordinates WITHOUT this module (deterministic, offline)
# ───────────────────────────────────────────────────────
"""THE GEOCODER — the §10-D6 engineering selection, recorded here.

THE SELECTION: the **US Census Bureau geocoder**
(`https://geocoding.geo.census.gov`), one-line-address endpoint, benchmark
`Public_AR_Current`. Why this one:

* **Free, no API key, no account** — a 1–2-staff utility (this product's
  whole audience) configures nothing and signs nothing.
* **US coverage is the deployment's coverage** — every tenant of this
  deployment is a US utility; the demo plant is Texas-shaped.
* **A government data service, not an ad-supported one** — the address of a
  metered premises is customer-adjacent data (D6 accepted the egress; this
  choice keeps it to a public-sector endpoint with published terms).
* **Stable, documented answer shape** — `result.addressMatches[n]
  .coordinates.{x,y}` where `x` is LONGITUDE and `y` is LATITUDE.

THE WORKED ADDRESS (the D6 record's required example — the Census Bureau's
own documented sample, their headquarters):

    GET https://geocoding.geo.census.gov/geocoder/locations/onelineaddress
        ?address=4600+Silver+Hill+Rd%2C+Washington%2C+DC+20233
        &benchmark=Public_AR_Current&format=json

    → result.addressMatches[0].coordinates = { "x": -76.92744, "y": 38.845985 }
    → geocode_address(...) = (Decimal("38.845985"), Decimal("-76.92744"))
      i.e. lat 38.845985 · lng -76.92744 — Suitland, MD.

⚠ Those figures are the endpoint's DOCUMENTED sample answer (exact decimals
drift slightly across benchmark vintages); this build environment's egress
proxy refused the live call (CONNECT 403), so the worked example was recorded
from the published documentation and must be re-run once from a deployed host
— stated in the lane report rather than smoothed over.

DESIGN RULES, EACH LOAD-BEARING:

* **Tests never touch the network.** Every function takes a `transport`
  callable (url → parsed JSON); the default (`_urllib_transport`) is the ONLY
  place `urllib` is used and only the management command exercises it live.
* **A failure is a `None` and a log line, never an exception** — one
  unmatchable address must not kill a 44-premises batch, and an invented
  coordinate is worse than a missing one.
* **A set coordinate is NEVER overwritten** (`geocode_missing` filters on
  `lat IS NULL`): an operator who hand-corrected a pin owns that pin.
* **Idempotent**: filled rows are never re-asked; only still-blank rows cost
  a request on a re-run.
"""

from __future__ import annotations

import logging
import urllib.parse
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger("smartbillhub.metering")

#: The one endpoint (see module docstring for the selection record).
CENSUS_ONELINE_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
CENSUS_BENCHMARK = "Public_AR_Current"
#: NUMERIC(9,6) — quantize to the column, never store more than it holds.
COORD_QUANTUM = Decimal("0.000001")
REQUEST_TIMEOUT_SECONDS = 10

Transport = Callable[[str], dict[str, Any]]


def _urllib_transport(url: str) -> dict[str, Any]:
    """The LIVE transport — the only network touch in this module. Honors the
    process's proxy environment (urllib does by default; this deployment's
    egress is proxied).

    `DEF-INT-10019` — through `core.gis_http.fetch_json`, the one function that
    sends `User-Agent: SMARTBillHub-GIS/<version> (support@bynry.io)` on every
    map and address request; a bare `urlopen` here sent Python's default agent.
    """
    from core import gis_http

    return gis_http.fetch_json(url, REQUEST_TIMEOUT_SECONDS)


def geocode_address(
    address: str, *, transport: Transport | None = None
) -> tuple[Decimal, Decimal] | None:
    """One-line address → ``(lat, lng)`` as Decimals at the column's 6 dp,
    or ``None`` — no match and transport failure are BOTH None-with-a-log,
    never an exception and never a made-up coordinate.

    Census serves ``coordinates.x`` = LONGITUDE, ``y`` = LATITUDE; this
    function returns the conventional (lat, lng) order the premises columns
    and every map library expect — the swap happens exactly once, here.
    """
    cleaned = str(address or "").strip()
    if not cleaned:
        return None
    query = urllib.parse.urlencode(
        {"address": cleaned, "benchmark": CENSUS_BENCHMARK, "format": "json"}
    )
    url = f"{CENSUS_ONELINE_URL}?{query}"
    send = transport or _urllib_transport
    try:
        payload = send(url)
    except Exception as exc:  # noqa: BLE001 — reported by name, batch survives
        logger.info("geocode: %r failed (%s: %s)", cleaned, type(exc).__name__, exc)
        return None
    matches = ((payload or {}).get("result") or {}).get("addressMatches") or []
    if not matches:
        return None
    coordinates = (matches[0] or {}).get("coordinates") or {}
    try:
        lat = Decimal(str(coordinates["y"])).quantize(COORD_QUANTUM)
        lng = Decimal(str(coordinates["x"])).quantize(COORD_QUANTUM)
    except (KeyError, InvalidOperation, TypeError):
        logger.info("geocode: %r answered an unreadable coordinate shape", cleaned)
        return None
    return (lat, lng)


def geocode_missing(*, transport: Transport | None = None) -> dict[str, Any]:
    """Fill ``lat``/``lng`` on every premises of the CURRENT tenant that has
    none — the batch behind the ``geocode_premises`` command.

    Runs inside the caller's tenant context (CLAUDE.md rule 1 — the command
    opens it; tests use ``tenant_ctx``). Rows already carrying a latitude are
    never touched, so the batch is idempotent and an operator's hand-set pin
    survives every re-run. Failures come back BY NAME in ``failed`` and are
    logged, never silently skipped (the BR-TEN-060 posture).

    A DIRECT write on this module's OWN table (metering owns premises), the
    established sample-path disposition — no service accepts coordinates and
    inventing one for a batch backfill would be scope, not safety.
    """
    from apps.metering import models
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    filled = 0
    failed: list[str] = []
    rows = models.Premises.objects.filter(
        tenant_id=tenant_id, lat__isnull=True, deleted_at__isnull=True
    ).order_by("address_line", "id")
    for row in rows:
        parts = [row.address_line, row.city, row.state, row.postal_code]
        address = ", ".join(str(part) for part in parts if part)
        result = geocode_address(address, transport=transport)
        if result is None:
            failed.append(row.address_line)
            logger.info("geocode: no coordinates for premises %r", row.address_line)
            continue
        row.lat, row.lng = result
        row.save(update_fields=["lat", "lng", "updated_at"])
        filled += 1
    return {"filled": filled, "failed": failed}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-028/B16@2026-08-22 §4.6 + §10-D6 (AST-W5 T3)
# generated: 2026-08-22 by the CR-028 AST-W5 lane
# checklist: A✔ B✔ C✔ D=n/a(no API half — the command is the operator surface) E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_cr028_new_tabs.py (stubbed transport; RED-first `ImportError: cannot import name 'geocode' from 'apps.metering'` quoted in the lane report) · ruff✔ black✔
# exceptions: the worked address's figures are the Census documentation's own sample answer — this build environment's egress proxy refused the live call (CONNECT 403), recorded in the module docstring and the lane report; re-run once from a deployed host · geocode_missing writes premises rows DIRECTLY (metering's own table, the sample-path disposition) because no service accepts coordinates
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
