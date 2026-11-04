# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-042 (EP-INT-12) — the picked candidate becomes a premises.
#           CR-069 §11: one seam file per module integrations touches.
# Rules:    BR-INT-048 (`C16` — the parcel is re-checked against live GIS at
#           the moment of the write) · OQ-INT-1728 RULED 2026-09-06 option (a)
#           (a person's SYNCHRONOUS write on a screen stays with the module
#           that owns the screen) · OQ-INT-1471 RULED 2026-09-04 option (b)
#           (typed past an unreachable City, marked unchecked) · B2 §2 /
#           CLAUDE.md module map (no cross-module write — this calls metering's
#           own service and touches no metering row itself) · hard rule 8 (an
#           address is stored on `premises` and nowhere else)
# Tests:    06-backend/tests/test_us_int_042_gis.py
# Impacts:  apps/metering/services.create_premises (the reviewed interface —
#           it gained `gis_unchecked`, `lat` and `lng` on the CREATE path) ·
#           apps/metering/models.Premises.gis_unchecked (migration 0054) ·
#           apps/integrations/gis.py (the only caller)
# ───────────────────────────────────────────────────────
"""integrations → metering: a candidate the clerk picked, written as a premises.

⚠ **THIS IS THE ONE SEAM IN THE MODULE THAT WRITES, AND THE RULING THAT PUT IT
HERE IS DATED.** Every other seam file reads. `BR-INT-054` as amended
2026-09-06 sends *record updates* to Runbooks, and on a literal reading this
write went with them — `CR-069` §20.4's wave `M` row said so in as many words.
`OQ-INT-1728` was put to the PO and ruled **option (a)** on 2026-09-06:

    *"(a). Every other Runbooks example is a batch nobody is watching. Routing
    a form submit through a runbook to write one row while somebody waits is a
    different animal, and slower for no benefit. Keeps ~3 of wave M's 4 weeks
    here. - we provide both option schedule it as a batch job or you run it one
    time as a batch job"*

So: **a record update a person makes synchronously on a screen stays with the
module that owns the screen.** The boundary is about UNATTENDED processing.

⚠ **AND THE CLAUSE AFTER THE DASH IS AN ADDITION RATHER THAN A RESTATEMENT.**
The same job must ALSO exist as a batch, in TWO forms — **scheduled**, and
**run once on demand** — so there are three ways to do one job and all three
get built. Neither batch form is built here and neither is sized anywhere:
scheduling is Runbooks' under `BR-INT-054`, and for the run-once button the
TRIGGER is the screen's while the RUNNING is Runbooks'. Nothing in this file is
a stub waiting for that; it is a different piece of work that has not started.

IT DOES NOT WRITE A METERING ROW ITSELF
----------------------------------------
`create` below calls `apps.metering.services.create_premises`, which is
metering's own audited, transactional, role-gated service (B2 §2 forbids a
cross-module write; a service call is the reviewed interface). So the premise
number comes from the tenant's series, the row is audited, the area cascade
runs, and none of that is reimplemented here — which is the difference between
a seam and a second copy of a module.

⚠ **THE PARCEL IS RE-CHECKED AT THE MOMENT OF THE WRITE, AND THE RE-CHECK IS
THE CALLER'S** (`C16`). This file takes a candidate that has ALREADY been
re-checked; `gis.py` owns the ordering, because it owns the connection, the
breaker and the run row.
"""

from __future__ import annotations

from typing import Any

#: The fields a FORM may never send, on either branch. They are facts about what
#: the City said, not about what a clerk typed, and a client that posted
#: `gis_unchecked: false` past an unreachable City would erase `OQ-INT-1471`'s
#: ruling from the one row it is about.
#:
#: ⚠ **`gis_parcel_id` REPLACED `external_ref` HERE ON 2026-09-17
#: (`BR-MET-1173`), AND THE OLD SPELLING WAS A COLLISION WAITING FOR A
#: MIGRATED UTILITY.** `OQ-INT-1470` ruled on 2026-09-04 that the GIS
#: parameters are the match key, and this file then put the City's parcel into
#: `premises.external_ref` on the strength of that column's comment,
#: *"the utility's own / GIS ref"*. But `CR-046` had already given
#: `external_ref` a second, load-bearing job — `BR-MET-403`'s **import match
#: key**, under `uq_premises_tenant_external_ref_ci`, one value per tenant —
#: and `units.external_ref`'s own comment calls it *"the LEGACY id"*.
#:
#: **A utility that migrated from other software already has values there.** The
#: first City pick would have met that unique index and reached the clerk as
#: *the parcel is already on another property* about a property with no parcel
#: at all. Two facts, two columns. `external_ref` keeps its own job and is still
#: refused from a form here, because it is still not a thing the City tells us.
NEVER_FROM_A_FORM = (
    "external_ref",
    "gis_parcel_id",
    "gis_status",
    "lat",
    "lng",
    "gis_unchecked",
)

#: The subset of the above a CLERK MAY STATE, and only when the City did not
#: answer. `DEF-MET-5604`, 2026-09-17.
#:
#: ⚠ **THE FORM OFFERED BOXES FOR EXACTLY THE THREE FACTS THIS FILE REFUSED TO
#: TAKE FROM A FORM, AND THE SAVE SUCCEEDED ANYWAY.** The create screen's
#: `✎ Change these` panel draws a parcel, a latitude and a longitude; every one
#: of them was stripped here, the write answered `201`, and nothing on any
#: screen told the clerk their three values had been thrown away. Walked at the
#: tip on 2026-09-17: `P-00104`, parcel typed by hand, all four columns EMPTY.
#:
#: **Which way to settle it was already ruled, twice.** `OQ-INT-1471` ruled
#: 2026-09-04 option (b) — *"type it, marked unchecked"* — and the PO ruled it
#: again on 2026-09-17 (`CR-115-BRC05` R24): when the City is unreachable while
#: creating a premises, **let them type it, mark it UNVERIFIED, the sync fixes
#: it later**. A clerk reading a parcel off a paper record is doing what both
#: rulings describe; the wave that built the boxes and the wave that built the
#: strip list simply never met.
#:
#: **WHAT IS STILL REFUSED, AND WHY EACH ONE STAYS:**
#:   * `gis_unchecked` — a form that posted `false` past an unreachable City
#:     would erase the ruling from the one row it is about. It is SET below,
#:     never taken.
#:   * `gis_status` — the City's own word for its own record. A clerk has no way
#:     to know it and a typed one would be indistinguishable from a real one.
#:   * `external_ref` — `BR-MET-403`'s import match key, a different fact that
#:     the City does not tell us (see the note above).
#:   * all three of these, on the PICKED branch — there the City has spoken and
#:     what it said is what is written.
TYPED_BY_A_CLERK = ("gis_parcel_id", "lat", "lng")


def _services() -> Any:
    """Imported inside the call so the module graph stays a DAG — integrations
    loads at `AppConfig.ready()` and metering must not have to."""
    from apps.metering import services as metering_services

    return metering_services


def payload_from(
    candidate: dict[str, Any] | None,
    typed: dict[str, Any],
    *,
    unit_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The `create_premises` payload for a pick, or for a typed address.

    ⚠ **IT STARTS FROM THE WHOLE TYPED FORM AND REPLACES ONLY WHAT THE CITY
    OWNS, AND THAT SHAPE IS THE FIX FOR A BUG THIS FILE ALREADY HAD.** The
    first draft listed the fields to carry forward — `name`, `premises_type`,
    `area_code`, `services_available` — and silently dropped every other one
    the create form sends. `owner_id` was among them, and `create_premises`
    REQUIRES an owner, so picking a candidate refused with
    *`metering.premises.owner_required`* while typing the same address
    succeeded. An allow-list of another module's fields goes stale the day that
    module adds one; taking the form as given and replacing only what the City
    owns cannot.

    ⚠ **A TYPED ADDRESS CARRIES `gis_unchecked = True` AND NO `external_ref`,
    AND BOTH HALVES MATTER.** Leaving the parcel key empty is what stops the
    row claiming a City record it does not have; the mark is what stops the
    absence being invisible (`OQ-INT-1471`, ruled option (b)).

    ⚠ **AND *TYPED* HERE MEANS EVERY PATH THAT IS NOT A PICK — WIDER THAN THE
    ONE CASE THE DOCUMENTS DESCRIBED (`DEF-INT-4266`).** `candidate is None`
    covers the City being unreachable, a clerk who typed the address without
    searching, and a clerk who saw the candidates and typed her own anyway.
    All three are the same fact — **the City has not confirmed this address** —
    and marking all three is the conservative reading the question asked for.

    ⚠ **AND NO FORM MAY SEND ANY OF `NEVER_FROM_A_FORM` — a client that posted
    `gis_unchecked: false` past an unreachable City would erase the ruling from
    the one row it is about.** The four are stripped on both branches and set
    from what actually happened.
    """
    form = dict(typed)
    payload = {key: value for key, value in form.items() if key not in NEVER_FROM_A_FORM}
    if candidate is None:
        # ── DEF-MET-5604 · `OQ-INT-1471` (b) and `CR-115-BRC05` R24 ──────────
        # The City did not speak, so what the clerk typed is the only evidence
        # there is — and it is KEPT rather than dropped in silence. The row is
        # still marked unchecked below, which is the half of the ruling that was
        # already honoured and is what makes a typed key distinguishable from a
        # confirmed one on every screen and in the nightly reconciliation.
        #
        # ⚠ **WHO TYPED IT IS THE AUDIT ROW'S JOB, NOT A COLUMN'S.**
        # `metering.services.create_premises` writes `premises.created` with the
        # actor and the whole after-state (hard rule 7), and `_gis_check_stamp`
        # CLEARS `gis_checked_by`/`gis_checked_at` whenever `gis_unchecked` is
        # true — so nobody is ever named as having checked a parcel they typed.
        for key in TYPED_BY_A_CLERK:
            if key in form and str(form[key]).strip() != "":
                payload[key] = form[key]
        payload["gis_unchecked"] = True
        return {key: value for key, value in payload.items() if value is not None}

    payload.update(
        {
            "address_line": candidate.get("address_line"),
            "city": candidate.get("city"),
            "state": candidate.get("state"),
            "postal_code": candidate.get("postal_code"),
            # ⚠ `external_ref` UNTIL 2026-09-17 — see `NEVER_FROM_A_FORM` above
            # for the collision that spelling had waiting for any migrated
            # utility (`BR-MET-1173`).
            "gis_parcel_id": candidate.get("parcel"),
            # The City's own word for this record, stored as given and never
            # filtered (ruling 10, 2026-09-17).
            "gis_status": candidate.get("status"),
            # The City answered, so the address is checked by construction.
            "gis_unchecked": False,
            # ⚠ **THE CITY'S OWN PIN, AT CREATION.** `premises.lat/lng` names
            # two writers — the sample seed and `geocode_premises` — and says
            # *"a set value is never overwritten by either"*. This is a third,
            # and it is recorded rather than slipped in: it writes at CREATE,
            # where the row is empty by construction, so that rule is
            # untouched; and a coordinate the City returned for the parcel it
            # also returned is better evidence than a geocoder's guess at the
            # same address. The frame it arrives in is `BR-INT-049`'s and is
            # checked by `gis.py` before this payload is built.
            "lat": candidate.get("lat"),
            "lng": candidate.get("lng"),
        }
    )
    if unit_candidate is not None:
        # `DEF-MET-10013` — a UNIT row was picked. The building's own point key
        # names no unit this create makes, so it goes nowhere; the unit's goes
        # onto the unit carrying the City's label.
        payload = _with_the_units_own_point(payload, unit_candidate)
    else:
        payload = _with_the_point_key(payload, candidate)
    return {key: value for key, value in payload.items() if value is not None}


def _with_the_units_own_point(
    payload: dict[str, Any], unit_candidate: dict[str, Any]
) -> dict[str, Any]:
    """`DEF-MET-10013` · `BR-MET-1162` — the picked unit's point and key on ITS unit.

    ⚠ **MATCHED BY LABEL, AND ONLY BY LABEL.** The screen names the first unit
    after the City's `Unit` when a unit row is picked. A create whose units
    carry no such label (the clerk renamed it, or asked for none) gets the
    unit's point NOWHERE: putting unit A's point on a unit called *1* would be
    a claim the City never made. Hard rule 8 stands — a unit carries a point
    and a key, never an address.
    """
    label = str(unit_candidate.get("unit") or "").strip().lower()
    extra: dict[str, Any] = {
        key: value
        for key, value in (
            ("gis_point_id", str(unit_candidate.get("point") or "").strip() or None),
            ("gis_status", unit_candidate.get("status")),
            ("lat", unit_candidate.get("lat")),
            ("lng", unit_candidate.get("lng")),
        )
        if value is not None
    }
    if not label or not extra:
        return payload
    units = payload.get("units")
    if isinstance(units, list):
        # ⚠ **NEW DICTS, NEVER A MUTATION** — the nested dicts are the caller's.
        return {
            **payload,
            "units": [
                {**one, **extra}
                if isinstance(one, dict) and str(one.get("label") or "").strip().lower() == label
                else one
                for one in units
            ],
        }
    one = payload.get("unit")
    if payload.get("auto_create_unit") and isinstance(one, dict):
        if str(one.get("label") or "").strip().lower() == label:
            return {**payload, "unit": {**one, **extra}}
    return payload


#: ⚠ **THE CITY'S ADDRESS POINT IS THE **UNIT'S** KEY, NOT THE PREMISES'
#: (`DEF-INT-5600`).** The mapping ruled 2026-09-17 is explicit: `PIN` →
#: `premises.gis_parcel_id`, `FULLPIN` → `unit.gis_point_id`. One picked
#: candidate IS one address point — *500 Main St Apt 1* is a different point
#: from *500 Main St* — so it names at most one of the units this create makes.
#:
#: **SO IT IS WRITTEN ONLY WHEN THE CREATE MAKES EXACTLY ONE UNIT, AND THAT
#: RESTRAINT IS THE DECISION RATHER THAN A LIMITATION.** With four flats the
#: City's one point belongs to one of them and we do not know which; writing it
#: to all four would be four claims where the City made one, and writing it to
#: the first would be a guess a reconciliation run could never tell from a fact.
#: The nightly run (`gis_parcels`) is what fills the rest, matching point by
#: point — and `BR-INT-073` already makes a disagreement there a difference a
#: person judges. Recorded in the decision log of 2026-09-17 with its figure.
def _with_the_point_key(
    payload: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Put the City's point key and status on the ONE unit this create makes."""
    point = str(candidate.get("point") or "").strip()
    if not point:
        return payload
    extra: dict[str, Any] = {"gis_point_id": point}
    status = candidate.get("status")
    if status:
        extra["gis_status"] = status
    units = payload.get("units")
    if isinstance(units, list):
        if len(units) == 1 and isinstance(units[0], dict):
            # ⚠ **A NEW DICT, NEVER A MUTATION.** `payload` is built from the
            # request body and its nested dicts are still the CALLER's; writing
            # into one would edit the body a view is holding.
            return {**payload, "units": [{**units[0], **extra}]}
        return payload
    if payload.get("auto_create_unit"):
        one = payload.get("unit")
        return {**payload, "unit": {**(one if isinstance(one, dict) else {}), **extra}}
    return payload


def _selectors() -> Any:
    """Metering's own read side, imported the same way its services are."""
    from apps.metering import selectors as metering_selectors

    return metering_selectors


def parcel_is_taken(tenant_id: Any, parcel: Any) -> bool:
    """`DEF-INT-4273` — is this parcel key already on a property here?

    ⚠ **THE SEAM IMPORTS A SELECTOR, NEVER A MODEL** (G78's shape, and the
    lifecycle note below says so). `tenant_id` is taken for the caller's
    benefit and asserted against the context rather than used to filter:
    metering's selectors scope themselves from `app.tenant_id`, and a second
    way of saying which tenant is how the two come to disagree.
    """
    from core import tenancy as core_tenancy

    current = core_tenancy.current_tenant_id()
    if str(current) != str(tenant_id):
        # ⚠ **A `raise`, NOT AN `assert`.** `python -O` strips assertions, and
        # this one stands in front of hard rule 1: a silent mismatch here would
        # answer a question about one tenant with another tenant's rows.
        raise RuntimeError(
            "the tenant context and the tenant asked about are different — "
            f"context {current}, asked {tenant_id}"
        )
    return bool(_selectors().premises_gis_parcel_taken(parcel))


def parcel_holder_address(tenant_id: Any, parcel: Any) -> str | None:
    """`DEF-MET-9847` — the address of the property already holding this
    parcel, for the refusal sentence. Same tenant assertion as
    `parcel_is_taken` above, same reason (hard rule 1)."""
    from core import tenancy as core_tenancy

    current = core_tenancy.current_tenant_id()
    if str(current) != str(tenant_id):
        raise RuntimeError(
            "the tenant context and the tenant asked about are different — "
            f"context {current}, asked {tenant_id}"
        )
    return _selectors().premises_holding_parcel(parcel, column="gis_parcel_id")


def create(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Write the premises through metering's own service. Returns its dict.

    The only caller is Add Premises with a City connected, so the custom-field
    screen is that form's (`"S16"`, `CR-161-BRC10` W2): a required field placed
    Input there binds on this door exactly as on `POST /premises`."""
    return _services().create_premises(actor, payload, custom_fields_screen="S16")


# ═══════════════════════════════════════════════════════════════════════════
# 2026-09-17 · `CR-115-BRC05` R31 — the parcel reconciliation's read and writes
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **`gis_parcels.run` HAD NO CALLER AT ALL UNTIL THIS WAVE (`DEF-INT-5601`).**
# 2,044 lines across `gis_parcels`, `gis_layer`, `gis_match` and `gis_search`,
# never invoked outside their own tests — hard-won law 2 in its purest form: it
# was built, it was tested, and no door opened onto it. These three functions
# are the seam half of that door; `apps/integrations/gis.py::reconcile` is the
# service half and `POST /integrations/gis_esri/reconcile` is the screen's.
#
# ⚠ **THEY ARE STILL A SEAM AND STILL WRITE NO METERING ROW.** Each calls
# metering's own audited, role-gated service, which is the reviewed interface
# (B2 §2). The *reason* this seam may write at all is dated and recorded above:
# `OQ-INT-1728`, ruled option (a) on 2026-09-06 — a record update a person makes
# synchronously on a screen stays with the module that owns the screen. **A
# scheduled nightly run is the OTHER half of that ruling** (*"we provide both
# option schedule it as a batch job or you run it one time as a batch job"*) and
# is Runbooks' under `BR-INT-054`; it is not built here and nothing below is a
# stub waiting for it.


def reconciliation_set() -> dict[str, Any]:
    """Our whole register — premises and their units — in TWO queries.

    ⚠ **TWO QUERIES FOR 40,000 PREMISES, NEVER TWO PER PREMISES** (`BR-INT-073`,
    PO ruling 4 of 2026-09-17: *"please ensure you dont call ArcGis Apis for
    every Premsies or unit again and again … against thse format match in loop
    with our premsies and units"*). The City is read once by `gis_layer.walk`,
    our side is read once here, and the matching is arithmetic over two lists.

    Sample rows are EXCLUDED by the selector's own default, which is what stops
    a demo utility's fixtures being reconciled against a real city's register.
    """
    return _selectors().gis_reconciliation_set()


def update_premises(actor: Any, premises_id: Any, patch: dict[str, Any]) -> dict[str, Any]:
    """One premises, through metering's own audited service.

    ⚠ **CALLED ONCE PER ROW INSIDE A SAVEPOINT THE CALLER OPENS**, never in a
    bulk update — `gis_parcels._persist` wraps each call in a nested
    `transaction.atomic()` so one refused row does not lose the other 39,999
    (hard-won law 14, and on PostgreSQL that is the only option rather than the
    tidy one).
    """
    return _services().update_premises(actor, premises_id, patch)


def update_unit(actor: Any, unit_id: Any, patch: dict[str, Any]) -> dict[str, Any]:
    """One unit, through metering's own audited service. See `update_premises`."""
    return _services().update_unit(actor, unit_id, patch)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-042@this-commit (EP-INT-12 story + OQ-INT-1728/1471 rulings verbatim)
# generated: 2026-09-06 by the CR-069 wave M build lane
# checklist: A✔ B=n/a C✔ D=n/a(no route of its own) E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_042_gis.py · G78's shape (no foreign model is imported here — only a service)
# exceptions: this is a THIRD writer of premises.lat/lng (create only) and the note beside the payload names it as one
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
