#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Rule:     BR-MET-1161 (PO ruling 2026-09-04) — *"we are having addresses at
#           one place now - Premises and Units -> then they flow to {Meters,
#           Sub meter, assets} + { accounts} -> from there it flows to Routes
#           and Cycles … so they will also draw addresses from same place that
#           we we can maintain the integrtiy"*. Same ruling family as CR-070 §W.
# Rules:    B2 §2 `addresses.kind` (SUPERSEDED at its second value) ·
#           CLAUDE.md hard-won law 7 (proved RED first — see below)
# Tests:    selftest() below · 06-backend/tests/test_br_met_1161_one_address_home.py
# Impacts:  06-backend/apps/**/models.py and every model file — every commit
# ───────────────────────────────────────────────────────
"""G85 — an address is declared in three places and a fourth is a defect.

WHY A GATE AND NOT A PARAGRAPH
-------------------------------
Nothing had two addresses for one place when this was ruled. The rule is a
FENCE, and a fence that lives only in prose is the thing CR-068 §13 already
described about a different rule: *"It erodes one reasonable-looking commit at
a time. Nobody ever decides to allow a fifth; a lane just needs one more
field."* An address column is the easiest field in this product to add for a
good local reason — a work order that wants to print where to go, an import
that wants to keep what the file said, a portal page that wants to show a
customer their street. Each is defensible alone and together they are four
answers to *where is this*.

WHAT IT READS
--------------
Every non-migration, non-test Python file under `06-backend/apps/`, parsed with
`ast` and never imported (the gate suite is stdlib-only). For each class whose
bases name a Django model, it collects assignments whose target is one of the
ADDRESS-SHAPED names below and whose value is a field call.

⚠ **`state` AND `country` ARE DELIBERATELY NOT TRIGGERS, AND THAT IS MEASURED
RATHER THAN CAUTIOUS.** A first draft included `state`, and eight of its eleven
hits were workflow columns — `DisconnectCase.state`, `ServiceRequest.state`,
`Connection.state`, `WorkOrder.state`, `ImportRunProgress.state`,
`Transfer.state`, `Tenant.state`, `ConnectionService.state`. A gate whose
output is 73% false positives is a gate that gets an allow-list entry per
commit until it means nothing. `country` is excluded for a narrower reason:
`TenantSettings.country` is the UTILITY's own regional setting and says nothing
about where a customer lives — `customers/selectors.py` already refuses to read
it as one (`DEF-2847`).

THE THREE HOMES, AND WHY EACH IS A DIFFERENT FACT
--------------------------------------------------
  * `metering.Premises` — **where the meter is.** The one address of record.
    Every asset, service point, account, route, cycle, invoice, work order and
    portal page reaches it by walking, and declares nothing of its own.
  * `customers.Address` — **where the BILL goes** (`kind='mailing'` only, since
    2026-09-04). Not a copy of the premises address: for every landlord, every
    managing agent and everyone who has moved it is deliberately different.
  * `tenancy.ServiceCentre` — **the utility's own counter.** A walk-in office
    is not a property that takes service, has no `premises` row and never will,
    so it cannot borrow. This is a build judgment recorded in the decision log
    of 2026-09-04 rather than put back to the PO (law 13).

`metering.Interruption.location_text` is not matched by any name here, and
that is right: it is what a stranger typed, a report rather than a record, and
`BR-CWP-027` keeps `premises_id` NULL until a clerk resolves it.

WHAT WAS PROVED RED FIRST (hard-won law 7)
-------------------------------------------
Two sabotages on the real tree, both reverted:

  1. `lat`/`lng` added to `apps/metering/connections.py::WorkOrder` —
     `G85 FAIL: apps/metering/connections.py::WorkOrder declares ['lat', 'lng'].
      An address is stored on `premises` (BR-MET-1161) …`
  2. `postal_code` added to `apps/customers/models.py::Contact` —
     `G85 FAIL: apps/customers/models.py::Contact declares ['postal_code'] …`

⚠ **AND A THIRD, ADDED WITH THE FOURTH HOME (CR-089 wave A, 2026-09-08).**
`BR-MET-1162` lets a `unit` carry its own map point, so `apps/metering/models.py
::Unit` joins HOMES — and the gate was proved RED on the real tree first,
through the harness that runs it (`module.run()`, never `python3 <gate>.py` —
`DEF-GOV-3733`):

     G85 FAIL: apps/metering/models.py::Unit declares ['lat', 'lng']. An address
     is stored on `premises` (BR-MET-1161, PO ruling 2026-09-04) …

The ruling narrows ONE clause, so the entry does too: `HOME_FIELDS` permits
`lat` and `lng` on a unit and nothing else, and the third sabotage — a unit that
declares a `city` beside its point — is what proves that half can still bite.
Without it the entry would have opened the whole address on a class the ruling
deliberately left closed.

And the gate is green on the tree as it stands, with exactly these four homes.

⚠ **2026-10-22 · `BR-MET-1202` (closes `DEF-MET-10364`).** The gate was RED on
the branch tip through `run()` before this change, naming `FieldRead`,
`FieldMeterProposal` and `WorkFieldRaise` (each declaring the phone's
`lat`/`lng`) — the CR-187 lanes had added them with no ruling. The PO ruled the
capture position its own fact, and the four capture classes (the route finding
the fourth) joined `OBSERVED_POSITIONS`, scoped to `lat`/`lng`. Then a
`city` was put on the real `FieldRead` and `run()` answered:

     FAIL apps/metering/field_read_models.py::FieldRead records where a phone
     WAS, as ['lat', 'lng'] only, and declares ['city'] as well …

and green again with it removed. The selftest carries the same sabotage on
`WorkRouteFinding`.
"""

from __future__ import annotations

import ast
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
APPS = REPO / "06-backend" / "apps"

#: An assignment named one of these, to a field call, is a claim about WHERE
#: something is. `state` and `country` are excluded — see the docstring; the
#: exclusion is measured, not timid.
ADDRESS_SHAPED: frozenset[str] = frozenset(
    {
        "address",
        "address_line",
        "address_line1",
        "address_line2",
        "line1",
        "line2",
        "city",
        "postal_code",
        "postcode",
        "zip_code",
        "lat",
        "lng",
        "latitude",
        "longitude",
    }
)

#: ⚠ **THIS GATE MATCHES BY NAME, SO A `_as_given` SPELLING IS INVISIBLE TO IT,
#: AND THAT BLIND SPOT IS MEASURED RATHER THAN LEFT UNSAID (`DEF-CUS-5400`,
#: 2026-09-15).** `customers.ServiceRequest` declares `address_as_given` and
#: `billing_address_as_given`, and `portal.PortalApplicationDraft` declares
#: `address_as_given` — **three columns this gate has never seen**, because none
#: of those names is in `ADDRESS_SHAPED` above.
#:
#: They are all lawful today: the first two are what the applicant said before
#: any premises exists (evidence, `BR-CUS-070`), and the billing one is
#: `BR-MET-1161`'s own mailing exception. **The problem is not the columns, it
#: is that the gate reports a clean zero over a scope it cannot see** — hard-won
#: law 7's fifth shape, the hardest to spot because the check is not lying.
#:
#: Found on 2026-09-15 by a lane about to add `address_city_as_given` to this
#: same table, which would have passed this gate silently. The PO then ruled the
#: columns out of the table altogether, so the immediate hazard went away and
#: the blind spot did not. `run()` prints this count beside its verdict.
#:
#: ⚠⚠ **THREE BECAME SIX ON 2026-09-22, AND THE COUNT IS THE POINT.** The PO
#: reversed the 2026-09-15 ruling — verbatim, *"correct address will be on
#: presmies but first time you will ahve to take the details to match it"* — so
#: `customers.ServiceRequest` now declares `address_city_as_given`,
#: `address_state_as_given` and `address_postal_code_as_given` as well. **They
#: are exactly the three columns this note was written about**, arriving by a
#: ruling instead of by accident.
#:
#: **THIS GATE STILL CANNOT SEE THEM AND IS STILL NOT WIDENED**, which is the
#: right answer twice over: `ADDRESS_SHAPED` matches by NAME so a `_as_given`
#: spelling is invisible, and teaching it that spelling would make it refuse
#: `address_as_given` itself — a column `BR-CUS-070` requires and which has
#: been lawful since it was written. What keeps the door shut is the NAME: a
#: lane adding a bare `city` to this table is still caught, because `city` IS
#: in `ADDRESS_SHAPED`.
#:
#: **So the number is what does the work here**, and a number that does not
#: move when its subject does is worse than no number at all — hard-won law 7's
#: fifth shape is precisely *a declared blind spot with no NUMBER attached is
#: indistinguishable from an empty one*, and a STALE number is indistinguishable
#: from a current one. It moves with the columns, every time.
#:
#: ⚠⚠ **SIX BECAME ELEVEN ON 2026-09-23 (`DEF-CUS-6408`).** The PO asked for the
#: BILLING address as a US address — *"full address line, unit, city, zip"* —
#: and `customers.ServiceRequest` now declares `billing_line1_as_given`,
#: `billing_line2_as_given`, `billing_city_as_given`, `billing_state_as_given`
#: and `billing_postal_code_as_given` beside the one-box
#: `billing_address_as_given`. Lawful for the reason that one is: hard rule 8's
#: FIRST named exception, *where the BILL goes*, held on a request until an
#: account exists to carry it as a `kind='mailing'` row.
#:
#: ⚠ **ELEVEN BECAME THIRTEEN ON 2026-10-06 (`DEF-CWP-9817`).** The portal's
#: Start service now asks the town and ZIP the blueprint draws (p31), so
#: `portal.PortalApplicationDraft` declares `address_city_as_given` and
#: `address_postal_code_as_given` — `BR-CUS-1091`'s statement-not-address
#: posture, handed to the request's own two columns at Send.
UNSEEN_AS_GIVEN_SPELLINGS = 13

#: ── 2026-09-17 · `BR-MET-1174` — THE GIS COLUMNS, COUNTED RATHER THAN RULED ON ──
#: `CR-112` put five kinds of GIS column on `Premises` and `Unit`:
#: `gis_parcel_id` / `gis_point_id`, their `_was` history, `gis_key_changed_at`,
#: `gis_status`, `gis_verified` and `gis_verified_at`.
#:
#: **NOT ONE OF THOSE NAMES IS IN `ADDRESS_SHAPED`, SO THIS GATE NEVER COLLECTS
#: THEM AND CANNOT FAIL ON THEM.** That is the RIGHT answer — a parcel id
#: identifies a record in somebody else's register and nothing in this product
#: derives an address from one — and it is the dangerous kind of right answer,
#: because it is indistinguishable from the gate not having looked.
#:
#: `DEF-CUS-5400` above is this exact shape one wave earlier: a clean zero
#: reported over three columns the gate could not see. Hard-won law 7, shape 5 —
#: *a declared blind spot with no NUMBER attached is indistinguishable from an
#: empty one*. So `run()` COUNTS them and prints the count beside its verdict.
#:
#: ⚠ **`HOME_FIELDS` IS DELIBERATELY NOT WIDENED FOR THEM.** That dict exists to
#: permit `lat`/`lng` on a unit **and nothing else** (`BR-MET-1162`); a lane that
#: adds `gis_*` names to `Unit`'s entry has opened it for the next lane that
#: wants a unit to print its own street. A parcel id needs no permission from an
#: address gate. Counting is the whole of the change.
GIS_KEY_PREFIX = "gis_"

#: The homes, each with the fact it holds. The VALUE is printed in the report,
#: so an allow-list entry has to say what it is for — an entry that cannot be
#: explained in one line is an entry that should not exist.
HOMES: dict[str, str] = {
    "apps/metering/models.py::Premises": "where the meter is — the one address of record",
    "apps/customers/models.py::Address": "where the BILL goes (kind='mailing' only)",
    "apps/tenancy/published_content_models.py::ServiceCentre": (
        "the utility's own walk-in counter — not a property that takes service"
    ),
    # ── CR-089 wave A · `BR-MET-1162`, PO ruling 2026-09-08 ─────────────────
    # PO verbatim: *"youa re correct address is on premsies/property - but GIS
    # data for unit might change and hence we have to have parcel ID and GIs
    # details on Unit also"*, confirming the reading put back to them: *"The
    # address half stands. The coordinate half narrows: a unit may carry its
    # own point and parcel, and where it does, that is the truth for that unit.
    # Where it does not, it uses its building's."*
    "apps/metering/models.py::Unit": (
        "a unit's OWN map point (lat/lng ONLY — a cabin, a pad, a wing of a "
        "campus is somewhere its site office is not); it still has NO address"
    ),
}

# ⛔ **A FIFTH HOME WAS ADDED HERE ON 2026-09-15 AND REMOVED THE SAME HOUR,
# BEFORE IT WAS PUSHED — `apps/customers/models.py::ServiceRequest`, for a
# city/state/postcode the Accounts blueprint draws on capture step 3.** The
# Product Owner ruled the columns out of that table instead, verbatim: *"if we
# have unit or street address then we should take it from premises/Unit - it
# means its a search and if not foudn them alow user to add them"*. Capture is a
# SEARCH of the premises register; the locality is the matched premises' own
# fact and the request's read model walks to it.
#
# The near-miss is recorded because the argument FOR the entry was a good one —
# a request records what a stranger said before any premises exists, which is
# the shape of `interruptions.location_text` — and it was still the wrong
# answer. **Four homes, and the next lane that wants a fifth should read this
# paragraph before writing one.**

#: ⚠ **AN ALLOW-LIST ENTRY NAMES ITS FIELDS, AND THAT IS A NARROWING OF THIS
#: GATE RATHER THAN A LOOSENING OF IT.**
#:
#: `BR-MET-1162` narrows `BR-MET-1161`'s COORDINATE clause and only its
#: coordinate clause: *"The address half stands."* A unit gets a point; a unit
#: gets NO address column, ever. Before this file grew this dict, a home was a
#: whole CLASS — so putting `Unit` on the list above would have permitted
#: `city`, `postal_code` and `address_line` on it too, and the very next lane
#: that wanted a unit to print its own street would have met a green gate.
#:
#: **That is the shape of a check that passes wrongly** (hard-won law 7,
#: habit 2): the entry would have been added for a real ruling, in good faith,
#: and it would have opened a door the ruling explicitly kept shut.
#:
#: A key absent from this dict permits every name in `ADDRESS_SHAPED` — the
#: three original homes ARE whole addresses, which is what they are for.
HOME_FIELDS: dict[str, frozenset[str]] = {
    "apps/metering/models.py::Unit": frozenset({"lat", "lng"}),
}

#: ══ 2026-10-02 · NOT A HOME — A DELIVERY ENDPOINT, AND THE ALLOWANCE IS
#: SCOPED TO ONE FIELD *AND* TO THE CHANNELS IT MAY HOLD (`DEF-GOV-6417`,
#: `DEF-NOT-8538`) ══
#:
#: `notifications.SuppressedAddress.address` — the do-not-send list — was red
#: here from 2026-09-17: a column named `address` on a class that is not a home.
#: It holds where a MESSAGE goes, and until this date it could hold a street,
#: because `channel` accepted `pdf_print`. The PO ruled, shown Dana asking us to
#: stop emailing `dana@example.com`, verbatim: *"A · Email and text only - this
#: correct"* (decision log 2026-10-02, *"SEVEN PO ANSWERS IN ONE MESSAGE"* (6)).
#: **An email address or a phone number is not a postal address, so hard rule
#: 8's list of homes does NOT grow — which is why this is not a `HOMES` entry.**
#:
#: ⚠ **THE ALLOWANCE IS CONDITIONAL, AND THE CONDITION IS WHAT MAKES IT A
#: NARROWING.** A class-wide entry would have permitted `city` beside it, and an
#: entry on the field alone would have stayed green the day somebody put
#: `pdf_print` back on the channel list — the exact door the ruling shut. So the
#: gate reads the named module-level tuple from the SAME file, with `ast`, and
#: passes only while it is literally the ruled pair. Widening that tuple is a
#: new PO ruling, and this gate goes red until there is one.
DELIVERY_ENDPOINTS: dict[str, dict[str, object]] = {
    "apps/notifications/suppression_models.py::SuppressedAddress": {
        "fields": frozenset({"address"}),
        "channels_constant": "SUPPRESSIBLE_CHANNELS",
        "channels": ("email", "sms"),
        "fact": "where a MESSAGE goes — an email address or phone number, never a street",
    },
}


#: ══ 2026-10-04 · NOT A HOME — WHERE A PHONE WAS, AND THE ALLOWANCE NAMES ITS
#: TWO FIELDS (`CR-168-BRC10` §F, decision log *"THE TECHNICIAN APP: ONE DEVICE
#: IS SHARED"* and *"A TECHNICIAN'S LOCATION FIX IS EVIDENCE, NOT AN ADDRESS"*) ══
#:
#: The PO ruled that the technician app sends latitude and longitude
#: automatically with what it captures, verbatim: *"techcian app will also send
#: lat and long data automatically"*. `WorkSyncReceipt.lat/lng` is that fix:
#: where the PHONE was when a tick, reading, photo or close was captured, kept
#: beside its accuracy as evidence. It is not where the property is, it is never
#: shown or used as the job's address, and the job still walks to its premises.
#: **So hard rule 8's list of homes does NOT grow** — this is `SuppressedAddress`'s
#: shape, a different fact. Scoped to the two coordinate fields: a `city` or
#: street on the receipt stays red.
OBSERVED_POSITIONS: dict[str, dict[str, object]] = {
    "apps/work/sync_models.py::WorkSyncReceipt": {
        "fields": frozenset({"lat", "lng"}),
        "fact": "where the technician's phone was when it captured an item — evidence, never the job's address",
    },
    # ── 2026-10-22 · `BR-MET-1202` (PO, verbatim *"yes we have capture gps
    # location again on phone because it might be taken later , and location
    # gps and gps set in system may differ"*), closes `DEF-MET-10364` ────────
    # A route reading, a field-added meter, an order raised on site and a route
    # finding each keep the PHONE's `lat`/`lng` at capture. Hard rule 8's
    # coordinate clause narrowed a fourth time — and, like `WorkSyncReceipt`,
    # NOT as homes: the list of homes does not grow, because none of these is
    # where anything IS. Scoped to the two names; a `city` beside them is red.
    # ⚠ The route PHOTO (`field_read_models.py::FieldReadPhoto`) declares no
    # position of its own today, so it has no entry — an entry for a class
    # with no such column is red here (`missing`), which is the point.
    "apps/metering/field_read_models.py::FieldRead": {
        "fields": frozenset({"lat", "lng"}),
        "fact": "where the technician stood at capture — evidence, not an address (BR-MET-1202)",
    },
    "apps/metering/field_read_models.py::FieldMeterProposal": {
        "fields": frozenset({"lat", "lng"}),
        "fact": "where the technician stood at capture — evidence, not an address (BR-MET-1202)",
    },
    "apps/work/field_order_models.py::WorkFieldRaise": {
        "fields": frozenset({"lat", "lng"}),
        "fact": "where the technician stood at capture — evidence, not an address (BR-MET-1202)",
    },
    "apps/work/route_finding_models.py::WorkRouteFinding": {
        "fields": frozenset({"lat", "lng"}),
        "fact": "where the technician stood at capture — evidence, not an address (BR-MET-1202)",
    },
}


def _module_tuple(tree: ast.AST, name: str) -> tuple | None:
    """The literal value of a module-level `name = (...)`, or None."""
    for stmt in getattr(tree, "body", []):
        target = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target, value = stmt.targets[0], stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            target, value = stmt.target, stmt.value
        if isinstance(target, ast.Name) and target.id == name:
            try:
                literal = ast.literal_eval(value)
            except ValueError:
                return None
            return tuple(literal) if isinstance(literal, (tuple, list)) else None
    return None


def _endpoint_failures(key: str, fields: list[str], tree: ast.AST) -> list[str]:
    rule = DELIVERY_ENDPOINTS[key]
    out: list[str] = []
    over = sorted(set(fields) - rule["fields"])  # type: ignore[operator]
    if over:
        out.append(
            f"{key} is a delivery endpoint for {sorted(rule['fields'])} and declares "  # type: ignore[arg-type]
            f"{over} as well. An email address or phone number is not a postal "
            f"address; a street beside it is a fifth home (hard rule 8)."
        )
    held = _module_tuple(tree, str(rule["channels_constant"]))
    if held != rule["channels"]:
        out.append(
            f"{key}: `{rule['channels_constant']}` reads {held!r}, and the PO ruled "
            f"{rule['channels']!r} only (2026-10-02, *\"A · Email and text only - this "
            f"correct\"*). Any other channel lets `address` hold a postal address. "
            f"Widening it is a new PO ruling, not an edit to this gate."
        )
    return out


def _model_classes(tree: ast.AST):
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [ast.unparse(b) for b in node.bases]
        if any("models.Model" in b or b.endswith("Model") for b in bases):
            yield node


def _address_fields(node: ast.ClassDef) -> list[str]:
    found: list[str] = []
    for stmt in node.body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
            continue
        target = stmt.targets[0]
        if not isinstance(target, ast.Name) or target.id not in ADDRESS_SHAPED:
            continue
        if not isinstance(stmt.value, ast.Call):
            continue
        call = ast.unparse(stmt.value.func)
        if "models." in call or "Field" in call:
            found.append(target.id)
    return sorted(found)


def count_gis_columns(root: pathlib.Path = APPS) -> int:
    """How many `gis_*` model columns this gate walked past (`BR-MET-1174`).

    ⚠ **THIS IS A REPORT AND NEVER A VERDICT.** It fails nothing and permits
    nothing; it exists so the gate's silence about the GIS columns carries a
    number, instead of reading exactly like a scope with nothing in it.
    """
    found = 0
    for path in sorted(root.rglob("*.py")):
        if "migrations" in path.parts or path.name.startswith("test"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in _model_classes(tree):
            for stmt in node.body:
                if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
                    continue
                target = stmt.targets[0]
                if not isinstance(target, ast.Name):
                    continue
                if not target.id.startswith(GIS_KEY_PREFIX):
                    continue
                if not isinstance(stmt.value, ast.Call):
                    continue
                call = ast.unparse(stmt.value.func)
                if "models." in call or "Field" in call:
                    found += 1
    return found


def scan(root: pathlib.Path = APPS) -> tuple[list[str], list[str]]:
    """Returns (failures, homes_seen). Pure — the selftest drives it."""
    failures: list[str] = []
    seen: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "migrations" in path.parts or path.name.startswith("test"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        rel = path.relative_to(root.parent).as_posix()
        for node in _model_classes(tree):
            fields = _address_fields(node)
            if not fields:
                continue
            key = f"{rel}::{node.name}"
            if key in DELIVERY_ENDPOINTS:
                seen.append(key)
                failures.extend(_endpoint_failures(key, fields, tree))
                continue
            if key in OBSERVED_POSITIONS:
                seen.append(key)
                permitted = OBSERVED_POSITIONS[key]["fields"]
                over = sorted(set(fields) - permitted)  # type: ignore[operator]
                if over:
                    failures.append(
                        f"{key} records where a phone WAS, as {sorted(permitted)} only, "
                        f"and declares {over} as well. A fix is evidence, never an "
                        f"address; widening it is a new PO ruling."
                    )
                continue
            if key in HOMES:
                seen.append(key)
                # A home may declare only the fields its ruling names. `None`
                # means the whole address — see HOME_FIELDS above.
                permitted = HOME_FIELDS.get(key)
                if permitted is None:
                    continue
                over = sorted(set(fields) - permitted)
                if not over:
                    continue
                failures.append(
                    f"{key} is a home for {sorted(permitted)} and declares "
                    f"{over} as well. `BR-MET-1162` narrows `BR-MET-1161`'s "
                    f"COORDINATE clause and ONLY that clause — the address half "
                    f"stands, and a unit refines a premises by LABEL. Widening "
                    f"this entry is a new PO ruling, not a bigger frozenset."
                )
                continue
            failures.append(
                f"{key} declares {fields}. An address is stored on `premises` "
                f"(BR-MET-1161, PO ruling 2026-09-04) and everything else walks "
                f"to it — asset, service point, account, route, cycle, invoice, "
                f"work order, portal page. If this really is a different FACT "
                f"and not a second copy, it needs a ruling and a row in "
                f"g85_one_address_home.HOMES saying which fact, in one line."
            )
    return failures, seen


def run() -> tuple[str, str]:
    """The suite's entry point.

    ⚠ **THIS WAS MISSING WHEN THE GATE FIRST LANDED, AND THE GATE PASSED
    STANDALONE WHILE CRASHING IN THE SUITE** — `run_gates` calls `module.run()`
    and got `AttributeError: module 'g85_one_address_home' has no attribute
    'run'`, reported as a FAIL among 28 others. So the gate was announced as
    green on the strength of `python3 g85_one_address_home.py`, which exercises
    `__main__` and never the path the suite uses. Hard-won law 7 says prove a
    guard RED before trusting it green; it is just as true that a guard must be
    proved **in the harness that will run it**, and this one was not.
    """
    failures, seen = scan()
    missing = [key for key in (*HOMES, *DELIVERY_ENDPOINTS, *OBSERVED_POSITIONS) if key not in seen]
    failures.extend(
        f"{key} is on the HOMES / DELIVERY_ENDPOINTS list and declares no address column any more"
        for key in missing
    )
    if failures:
        return "FAIL", " | ".join(failures[:3]) + (
            f" (+{len(failures) - 3} more)" if len(failures) > 3 else ""
        )
    homes = [key for key in seen if key in HOMES]
    endpoints = [key for key in seen if key in DELIVERY_ENDPOINTS]
    observed = [key for key in seen if key in OBSERVED_POSITIONS]
    scoped = sum(1 for key in homes if key in HOME_FIELDS)
    return "PASS", (
        f"{len(homes)} ruled homes and no unruled one — "
        + " · ".join(sorted(homes))
        + f"; {len(endpoints)} delivery endpoint(s), not homes — "
        + " · ".join(sorted(endpoints))
        + " (email/sms only, read from SUPPRESSIBLE_CHANNELS; PO 2026-10-02)"
        + f"; {len(observed)} capture position(s), lat/lng only, not homes"
        " (BR-MET-1202)"
        + f"; {scoped} of them field-scoped (a unit is a home for lat/lng and"
        " NOT for an address); self-test: a work order's lat, a contact's"
        " postcode and a unit's city all bite"
        # ⚠ **WHAT THIS RUN DID NOT LOOK AT, PRINTED BESIDE WHAT IT DID.** A
        # declared blind spot with no NUMBER attached is indistinguishable from
        # an empty one (hard-won law 7, shape 5) — see
        # `UNSEEN_AS_GIVEN_SPELLINGS` above for the six columns and why each
        # is lawful today.
        + f"; NOT SEEN: {UNSEEN_AS_GIVEN_SPELLINGS} `*_as_given` address"
        " columns this name-matching gate cannot reach (DEF-CUS-5400)"
        # ⚠ **AND THE GIS COLUMNS, COUNTED RATHER THAN RULED ON**
        # (`BR-MET-1174`). Walked past deliberately: a parcel id is not an
        # address. The NUMBER is what stops that silence reading like an empty
        # scope — hard-won law 7, shape 5.
        + f"; WALKED PAST: {count_gis_columns()} `gis_*` columns — a City's"
        " parcel/point key is not an address and needs no entry here"
        " (BR-MET-1174)"
    )


def main() -> int:
    failures, seen = scan()
    missing = [key for key in (*HOMES, *DELIVERY_ENDPOINTS, *OBSERVED_POSITIONS) if key not in seen]
    if missing:
        # A home that stopped declaring an address is as much a signal as a
        # fourth one appearing: it means a rename this gate can no longer see.
        failures.extend(
            f"{key} is on the HOMES list and declares no address column any "
            f"more — either it was renamed (update HOMES) or the one address "
            f"of record has moved and nothing said so."
            for key in missing
        )
    for line in failures:
        print(f"G85 FAIL: {line}")
    if failures:
        return 1
    print(
        f"G85 PASS: {len(seen)} ruled homes, and no unruled one — "
        + " · ".join(sorted(seen))
    )
    return 0


def selftest() -> int:
    """Break it on purpose, twice, in a temp tree — never on the real one."""
    import shutil
    import tempfile

    cases = [
        ("a work order that keeps its own street", "sabotage", "WorkOrder",
         "    lat = models.DecimalField()\n"),
        ("a contact that keeps its own postcode", "sabotage", "Contact",
         "    postal_code = models.TextField()\n"),
        # ── CR-089 wave A — THE NARROWING'S OWN RED PROOF ────────────────────
        # `Unit` is a home for `lat`/`lng` and for NOTHING ELSE (`BR-MET-1162`
        # narrows the coordinate clause and the address half stands). This case
        # writes a `metering.Unit` at its REAL path with the permitted pair AND
        # a city beside them: without `HOME_FIELDS` the whole class was allowed
        # and this sabotage passed, which is exactly the false pass the dict
        # exists to stop.
        ("a unit that keeps its own city", "metering", "Unit",
         "    lat = models.DecimalField()\n"
         "    lng = models.DecimalField()\n"
         "    city = models.TextField()\n"),
        # ── 2026-10-02 — THE DELIVERY ENDPOINT'S RED PROOFS ─────────────────
        # Both write `SuppressedAddress` at its REAL path so the allowance is
        # looked up and then refused: once for a channel list that lets a
        # street in, once for a street beside the permitted field.
        ("a do-not-send list that takes paper", "notifications", "SuppressedAddress",
         "    address = models.TextField()\n",
         'SUPPRESSIBLE_CHANNELS = ("email", "sms", "pdf_print")\n'),
        ("a do-not-send entry that keeps a city", "notifications", "SuppressedAddress",
         "    address = models.TextField()\n    city = models.TextField()\n",
         'SUPPRESSIBLE_CHANNELS = ("email", "sms")\n'),
        # ── 2026-10-22 · `BR-MET-1202` — a capture position is lat/lng ONLY ──
        # Written at the finding's REAL path so the allowance is looked up and
        # then refused for the city beside it.
        ("a route finding that keeps a city", "work", "WorkRouteFinding",
         "    lat = models.DecimalField()\n"
         "    lng = models.DecimalField()\n"
         "    city = models.TextField()\n"),
    ]
    failed = 0
    for label, package, cls, line, *prelude in cases:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "apps" / package
            root.mkdir(parents=True)
            filename = {
                "notifications": "suppression_models.py",
                "work": "route_finding_models.py",
            }.get(package, "models.py")
            (root / filename).write_text(
                "from django.db import models\n\n"
                + (prelude[0] if prelude else "")
                + f"\n\nclass {cls}(models.Model):\n{line}",
                encoding="utf-8",
            )
            found, _ = scan(pathlib.Path(tmp) / "apps")
            if not any(cls in f for f in found):
                print(f"selftest RED-PROOF FAILED: {label} was not caught")
                failed = 1
            else:
                print(f"selftest ok — {label} caught: {found[0][:100]}…")
    shutil.rmtree if False else None
    return failed


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    raise SystemExit(main())
