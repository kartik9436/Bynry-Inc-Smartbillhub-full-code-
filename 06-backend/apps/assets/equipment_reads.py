# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-043 (EP-CWP-08) — *Meters and equipment at the property*.
#           Screen: CWP-037 (blueprint `P23`)
# Change:   CR-068 wave H (2026-09-04)
# Rules:    BR-CWP-073 (equipment is what an unmeasured service is billed on) ·
#           B14 rule 31 (no database id is ever the visible value of a field —
#           this payload carries `asset_id` for the caller's own JOIN and the
#           portal drops it before serving) · BR-AST-026 (three identifiers:
#           the hidden uuid, the manufacturer's SERIAL and our own asset_no) ·
#           BR-AST-007 (a test cadence is a DERIVED display state; the stored
#           status never changes) · BR-AST-017 (assignment is append-only and
#           `to_date IS NULL` is the current one)
# Tests:    06-backend/tests/test_us_cwp_043_equipment.py
# Impacts:  apps/metering/seams.py `equipment_on_unit` →
#           apps/metering/portal_reads.py → apps/portal/seams/metering_seam.py
# ───────────────────────────────────────────────────────
"""What a CUSTOMER is shown about the equipment on their own unit.

READ-ONLY. Nothing here writes, and it is a separate module from `selectors.py`
for the reason `connection_reads.py` and `monthly_usage_reads.py` are separate
from theirs: one purpose, one file, and two lanes can build beside each other.

⚠ **IT IS NOT `assets_on_unit` WITH MORE KEYS, AND WIDENING THAT ONE WAS THE
FIRST DRAFT.** `selectors.assets_on_unit` answers the S15 *Meters* cell — id,
number, qualifier, type, size class — and is read by the routes picker, the
delete guard and the bill run's asset count. **A customer's row needs facts
none of those want** (the serial on the box, where it is fitted, when it was
fitted, its status word and its next test) and wants none of the qualifier
machinery. Widening the shared dict would have made every one of those callers
pay for four joins to draw a number they already had.

⚠ **THE VISIBLE IDENTIFIER IS THE SERIAL, AND `asset_no` IS THE FALLBACK — NOT
THE OTHER WAY ROUND** (`US-CWP-043` §5, TC-5). `serial_no` is the number
stamped on the device on the wall, which is the one a customer can walk outside
and check. `asset_no` is OUR number from the tenant's series; it is still not a
database id, so a row with no serial recorded is shown by it rather than by
nothing. The uuid never leaves the portal seam.

⚠ **A CART IS EQUIPMENT.** `BR-CWP-073`: some services are billed on the thing
at the kerb rather than on any reading, so the refuse cart is a row here beside
the water meter — with an EMPTY last-read cell, never a zero (`US-CWP-043`
TC-2). This module does not read meter reads at all; `metering` joins them on,
because `meter_reads` is metering's table.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.assets import models, seams, selectors


#: `category` → the `maintained_by` an asset type is SEEDED with (assets `0012`,
#: `CR-085` `CPB-10`). ⚠ **A STARTING VALUE, NOT A RULE.** It is applied once, by
#: the migration, and never consulted again: a utility that owns the battery it
#: installed changes the TYPE and the customer's screen follows. Reading it live
#: would be `DEF-CWP-3765`'s *"a shape that implies it is a rule in disguise"* —
#: and this map is here rather than only in the migration so a test can assert
#: what was seeded without importing a migration module.
SEEDED_MAINTAINED_BY: dict[str, str] = {
    "meters": "utility",
    "sub_meters": "utility",
    "behind_the_meter": "customer",
}


def equipment_on_unit(unit_id: Any, *, today: date | None = None) -> list[dict[str, Any]]:
    """Every asset CURRENTLY assigned to this unit, as a customer reads it.

    ⚠ **CURRENTLY — `to_date IS NULL`** (`BR-AST-017`). A meter that was swapped
    out last year is history the utility keeps and the customer is not shown; a
    sub-meter belonging to the flat next door was never assigned here at all,
    which is what makes `US-CWP-043` TC-4 hold by construction rather than by a
    filter somebody has to remember.

    `today` is a PARAMETER (`BR-TEN-043` — the event date is an argument, never
    a clock read in a read model). `None` falls back to the tenant's own today,
    which is what `selectors.test_due` already does.

    An empty list is a REAL answer and the caller must state it rather than
    score it (`US-CWP-043` TC-8: an empty state, not a blank table).
    """
    asset_ids = list(
        models.AssetAssignment.objects.filter(
            tenant_id=selectors._tenant_id(), unit_id=unit_id, to_date__isnull=True
        ).values_list("asset_id", flat=True)
    )
    if not asset_ids:
        return []
    rows = selectors._base_qs().filter(id__in=asset_ids).order_by("type__name", "asset_no", "id")
    out: list[dict[str, Any]] = []
    for asset in rows:
        out.append(
            {
                #: ⚠ **FOR THE CALLER'S JOIN, NEVER FOR A SCREEN** (B14 rule 31).
                #: `metering.portal_reads` uses it to ask for the last read and
                #: then drops it; `apps/portal/selectors.py` never serves it.
                "asset_id": str(asset.id),
                #: The manufacturer's serial — the number on the box.
                "serial_no": asset.serial_no,
                #: Our own number from the tenant's series (`BR-AST-049` says
                #: why the two are different columns). The fallback when the
                #: serial was never recorded; still not a database id.
                "asset_no": asset.asset_no,
                #: The tenant's OWN word for the kind of thing this is —
                #: *Water meter*, *Refuse cart*, *Backflow device*. Rendered
                #: verbatim, never translated (B14 rule 35's precedent: a
                #: utility's own wording is not ours to restate).
                "kind": asset.type.name,
                "kind_code": asset.type.code,
                #: `meters` · `sub_meters` · `behind_the_meter` (`BR-AST-004`).
                "category": asset.type.category,
                #: Which utility service it stands on, or None for a device on
                #: no service point.
                "service": selectors._service_of(asset),
                #: *front boundary box*, *rear alley* — the utility's own note,
                #: ≤280 chars by service law. None renders as a quiet dash.
                "where": asset.location_note,
                "fitted_on": asset.install_date.isoformat() if asset.install_date else None,
                #: The tenant's own status word, and the behaviour class beside
                #: it so a screen can choose a tone without matching on prose.
                "status": asset.status.name,
                "status_code": asset.status.code,
                "behavior_class": asset.status.behavior_class,
                #: `BR-AST-007` — DERIVED, and the stored status never moves.
                #: `next_test` is the explicit `certification_due` when one was
                #: captured, else `last_test_date + test_interval_months`, else
                #: None; `test_due` says whether that date has passed. A screen
                #: renders *TEST DUE NOV* from the DATE in the reader's own
                #: language rather than from a sentence this module writes.
                "test_due_on": selectors.next_test_date(asset),
                "test_due": selectors.test_due(asset, today=today),
                #: ⚠ **WHOSE IT IS — `utility` · `customer`** (`CPB-10`). A
                #: CODE; the catalogue writes *Ours* and *Yours* (B14 rule 35).
                #: It settles the repair-bill question, which is the drawing's
                #: own reason for the column: *"Equipment marked Ours is
                #: maintained by us at no cost to you."*
                "maintained_by": asset.type.maintained_by,
                #: `BR-AST-500` — the connection's size class code, or None when
                #: nobody recorded one. It is what names a `capacity` service's
                #: billing basis on `CWP-033` (*your 96 gal cart*).
                "size_class": asset.size_class,
            }
        )
    return out


def equipment_service_codes(unit_id: Any) -> list[str]:
    """Which services have equipment standing on this unit — no duplicates.

    Small on purpose: `CWP-033`'s *billed on* panel asks *"is there a cart
    behind this trash charge?"* and nothing more, and answering it from the row
    list above would make the caller re-derive a set two screens need.
    """
    seen: list[str] = []
    for row in equipment_on_unit(unit_id):
        code = row.get("service")
        if code and code not in seen:
            seen.append(code)
    return seen


#: Kept so a reader of this module can see the one seam it uses. `seams` is
#: imported for `selectors._service_of`'s benefit rather than called here; the
#: reference stops a tidying lane from dropping the import that read needs.
_SEAMS = seams


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-043@this-commit (EP-CWP-08 story + BR-CWP-073, BR-AST-007/017/026 verbatim)
# generated: 2026-09-04 by the CR-068 wave H build lane
# checklist: A✔ B=n/a(no frontend half in this module) C✔ D=n/a(no endpoint here — apps/portal/api.py serves it) E=n/a F✔ G✔ H=n/a(reads no money)
# gates: pytest tests/test_us_cwp_043_equipment.py · G81 (nothing here is under apps/portal; the portal seam that calls it performs no ORM write)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
