# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-032 (EP-RBS-05) — CR-075 wave Q′: runbook 20, *GIS
#           reconciliation* — seven steps over a landed parcel batch, five read
#           and two write.
# Rules:    BR-RBS-004 (an Action always produces a PLAN first) · BR-RBS-002
#           (a Check is constructed with no writer — this is an Action and
#           holds one named port) · BR-RBS-006 (a cap REFUSES the run; it never
#           truncates) · BR-RBS-009 (scope resolved ONCE and pinned) ·
#           BR-RBS-010 (every record states the rule that decided it, in words
#           a clerk can read) · BR-RBS-011 (a failure names its fix route) ·
#           BR-RBS-012 (a guard is absolute and runs before any step) ·
#           BR-RBS-019 (the declared unit of work) · BR-RBS-020 (the report is
#           composed at close and frozen) · BR-RBS-021 (twelve blocks) ·
#           BR-RBS-022 (a write is a named port; a work item is the ENGINE's) ·
#           BR-RBS-023 (a step declares its mode) · BR-RBS-027 (a stopped run
#           reads *Never reached* on every later step) · BR-RBS-035 (a volume
#           runbook keeps a row for what it acted on and a COUNT for the rest) ·
#           BR-RBS-039 (every foreign read through a seam this module owns) ·
#           RBR-17 / BR-INT-051 🔒 (the never-touch list is fixed on the
#           money-path fields and a tenant cannot widen it) · RBR-03 (policy
#           lives in Settings and is never duplicated on a card) ·
#           CLAUDE.md hard rule 8 (an address lives on `premises` and nowhere
#           else) · hard rule 7 (every money action writes audit_log — the
#           ENGINE's, BR-RBS-015) · hard-won law 2 · law 7 · B14 rules 31, 32
# Tests:    06-backend/tests/test_us_rbs_032_gis_reconciliation.py ·
#           06-backend/tests/test_rbs_sync_runbooks_pg.py (PostgreSQL only)
# Impacts:  apps/runbooks/definitions/__init__.py (the one line that registers
#           it) · apps/runbooks/seams/metering_seam.py ·
#           apps/runbooks/seams/integrations_seam.py ·
#           apps/metering/selectors.py (the two reads the owning module added)
#           · 04-docs/05-modules/17-runbooks/11-catalogue/RB-120-gis-reconciliation.md
# ───────────────────────────────────────────────────────
"""Runbook 20 — **GIS reconciliation**.

The county says one thing about a property and we say another. This takes the
parcels that landed, puts them beside our premises, and **says which of the two
values is which** — *Ours* and *Theirs*, on every row a person has to decide.
Nobody reads two systems side by side and remembers which screen said what.

WHO STARTS IT, AND WHY THAT IS NOT THE EVENT THE CARD NAMES
------------------------------------------------------------
`RB-120`'s trigger row reads ⚡ `batch.landed`. **A person starts this runbook.**
`batch.landed` is emitted by nothing — zero occurrences anywhere in the backend,
verified 2026-09-06 — and it is `CR-069`'s work, currently scoped to nobody.
`models.py` already rules that *"a runbook whose only trigger is an unbuilt
event is not runnable, and a screen must SAY so rather than offering a Run ▶
that refuses"*, so this declares **manual and schedule**, both of which wait on
nothing, and the event joins them the day it exists.

"NO CONNECTION" IS AN ANSWER, AND IT IS STEP 1
-----------------------------------------------
PO ruling 2026-09-06, verbatim: *"we should complete our runbooks, if we need to
do a check of integration and APIs, we should do it, in absence of API
conenctions you will not find anything and you can stop the job saying APi or
conenct not available; that is a valid case and state for us"*. So step 1 asks
where today's parcels come from and the run **STOPS** when the answer is
nowhere: one red chain cell naming what is missing and six honestly reading
*Never reached* (`BR-RBS-027`). That is a designed answer, not a crash.

⚠ **AND IT IS NOT A CONNECTION CHECK ALONE — THERE ARE TWO DOORS, WHICH IS
WAVE `P`'s LESSON APPLIED RATHER THAN REDISCOVERED.** A clerk who has just
uploaded the county's parcel export does not need to be told the GIS API is not
wired up; the work is in front of them. So the doors are **a live GIS
connection** and **a parcel file somebody uploaded** — an import run for
`premises` that has been staged and validated and **not loaded** — and the run
stops only when BOTH are shut.

⚠ **THE SECOND DOOR IS A JUDGMENT AND IT IS WRITTEN DOWN RATHER THAN ASSUMED.**
`RB-120`'s scope names one source, the GIS connection. This product has no
parcel table and no parcel importer; what it has is `import_runs` with
`target = "premises"`, which is where a utility without a GIS API puts the
county's file today. A run at `validated` has been read, mapped and judged and
has written nothing — which is exactly what *a landed batch* means to a runbook
that plans before it acts. Reconciling it is not the importer's job doubled: the
importer LOADS by write mode, and this classifies every difference and applies
only the ones the utility said to apply. Recorded in `12-governance/02-decision-log.md`,
2026-09-06.

⚠ **THE CITY DOOR IS BOUND — 2026-10-07, `DEF-INT-9848` (PO GIS review gap 2).**
Until that date a tenant with a working connection and no uploaded file met the
stop *"Nothing has landed yet"* on every run, because `reconcile_parcels` was
bound to nothing. PO ruling 2026-10-07 (decision log, *"PO RULINGS — GIS: NO NEW
NIGHTLY CODE; THE PARCEL CHECK WILL RUN THROUGH RUNBOOK 20, FIRST BY HAND AND
ONLY LATER ON A SCHEDULE FOR ONE NAMED UTILITY"*): step 1 now asks the City's
OWN parcel check — `apps.integrations.gis.reconcile`, in PREVIEW, through
`seams/integrations_seam.city_parcels` — once per run, and steps 2–4 report its
answer rather than matching again (see *the City door* above step 1 for why a
second match would be a second implementation). An uploaded file still wins
when there is one. The **`pages`** input (*City pages to read*, empty = the
whole register) stops the City's walk after that many pages, and every report
then says *Stopped after N of M pages* (`DEF-INT-9849`); `started_by_name` is
the engine's own override naming the person who pressed **Run ▶**
(`services.request_run`, `CR-173-BRC10`), carried to the City check's attempt
row. ⚠ Declaring `pages` changed the shipped document, so a utility holding
a SAVED VERSION of this runbook sees *Template updated · Review →* once and its runs
wait for that press (`BR-RBS-038`) — the decision log of 2026-10-07 records the
judgment. **What an unattended run does with the answer is deferred by the PO**
(*"not rightnnow"*); nothing here schedules anything.

WHAT IT PLANS AND WHAT IT ACTUALLY DOES TODAY
-----------------------------------------------
**Nothing is written.** `apply_premise_change` IS bound (`CR-075` task `L2`,
to `apps.metering.runbook_ports.apply_premise_change`), and
`engine.acts.LIVE_ENABLED_RUNBOOKS` is an **empty frozenset**, so every runbook
in the catalogue is handed a writer-less copy of its ports and the port refuses
by name. That is phase 2's dry half — the risky code runs against real premises,
in production, unable to do anything — and wave `N` turns the first runbook on.

⚠ **THE PORT IS CALLED ANYWAY AND THE REFUSAL IS RECORDED — THERE IS NO
`if is_bound` BRANCH HERE.** `BR-RBS-003` says dry and live are ONE code path
differing only in whether the writer is bound; a branch would be a second path
that proves nothing about the first.

THE NEVER-TOUCH LIST, WHICH IS THE ONE THING IN HERE THAT CANNOT MOVE
-----------------------------------------------------------------------
**Inside city limits · City · State** are never written, whatever the difference
class says (`RB-120` step 5, `RBR-17` restating the integration substrate's
C25). They are fixed on the money-path fields and **a tenant cannot widen the
list**, which is why they are a constant here and not a parameter.

⚠ **`inside_city_limits` DECIDES WHAT AN ADDRESS IS CHARGED**, and
`apply_premise_change`'s own docstring says a runbook must not be pointed at it.
That docstring gives the reason as *"`OQ-423` … is OPEN"* — **`OQ-423` closed on
2026-08-27** (*"(a) Forward only, and nothing else"* → `BR-RAT-103`), which is
`DEF-MET-4349`, filed before it was corrected. **The instruction survives
its stale reason**: `RBR-17` forbids the write outright and does not depend on
that question at all, and a county disagreeing with us about a city boundary is
worth KNOWING, which is why the twelve never-touch conflicts are listed rather
than hidden.

FOUR PLACES THIS DIVERGES FROM `RB-120`, EACH STAMPED
-------------------------------------------------------
1. **The KPI strip says *To apply* while nothing is applied.** The card's word
   is *Applied*. A tile reading **980 Applied** over a run that applied nothing
   is the most dangerous sentence this screen could print. The card's word
   returns the day a writer is bound.
2. **Two of the card's nine fields are not columns in this product.** *Lot area*
   and *Zoning* exist on no premises here, so they are not offered as
   dispositions and the count of card fields this product cannot compare is
   REPORTED (`fields_the_product_does_not_hold`) rather than silently dropped —
   hard-won law 7's *declared blind spot with a number attached*.
3. **`Most changes per run` is not a parameter.** The cap is a column on the
   runbook row (`runbooks.cap`) and duplicating it as a parameter would be two
   copies of one policy, which is `RBR-03` exactly. Step 5 READS it, as the
   card's own step 5 asks.
4. **The chain is drawn only when the run STOPPED.** The frame draws a run that
   finished; a stopped run is a state it does not cover, and the chain is the
   only block that can say *this step never ran*.

WHAT WOULD MAKE THIS RUNBOOK REPORT WRONGLY, ANSWERED IN WRITING
-----------------------------------------------------------------
Hard-won law 7's second habit. **A run that examined nothing and a run that
found nothing wrong must not read the same.** Every step returns a `checked`
mapping saying what it looked at; the KPI strip carries the landed parcel count
beside the difference counts; and a premises whose type could not be read is
named in `checked` rather than counted as agreeing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from collections.abc import Mapping
from typing import Any

from apps.runbooks import models
from apps.runbooks.boundary import PortNotBound
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_ENUM,
    PARAM_REF_OBJECT,
    PARAM_REF_SETTING,
    PARAM_TEXT,
    PARAM_TOGGLE,
    Block,
    Guard,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import integrations_seam, metering_seam

KEY = "gis_reconciliation"

# ── the two doors work arrives through ────────────────────────────────────
#
# The maps manifests, verified against `06-backend/apps/integrations/manifests/`
# on 2026-09-06 and named as VALUES rather than imported: a manifest key
# crossing the seam is data, and importing `apps.integrations.manifests` is
# exactly what `G115` refuses (`BR-RBS-039`).
#
# ⚠ **`gis_esri` IS THE ONLY ONE THAT LANDS PARCELS.** `geocoder_census` turns
# an address into a point and `map_tiles_public` draws a picture; neither has a
# parcel to reconcile. They are excluded BY NAME rather than by category, so a
# tenant with a map connected and no GIS is told the truth.
# ⚠ `gis_city` until `CR-110-BRC04` — renamed to `gis_esri`, nothing else
# about the connector moved.
GIS_PROVIDER_KEYS = ("gis_esri",)

#: The import target a parcel file is uploaded against in this product. See the
#: module docstring for why this is the second door.
PARCEL_IMPORT_TARGET = "premises"

# ── the seven difference classes, in the card's own order ─────────────────

CLASS_NEW_VALUE = "new_value"
CLASS_BLANK_HERE = "blank_here"
CLASS_BLANK_THERE = "blank_there"
CLASS_CONFLICT = "conflict"
CLASS_TWO_PREMISES_ONE_PARCEL = "two_premises_one_parcel"
CLASS_ONE_PREMISE_TWO_PARCELS = "one_premise_two_parcels"
CLASS_UNMATCHED = "unmatched"
#: ⚠ **THE CITY DOOR'S EIGHTH, AND IT IS THE OTHER DIRECTION** (`DEF-INT-9848`).
#: *Parcel with no premise* is a row of THEIRS we do not have — the City's
#: parcel check counts those and raises nothing (its ruling 8, *"c) ignore"*).
#: This is a premises of OURS no City parcel matched, which the City's check
#: queues for a person; folding it into *unmatched* would print the City's
#: question under our label.
CLASS_PREMISE_NO_PARCEL = "premise_no_parcel"

CLASS_LABELS = {
    CLASS_NEW_VALUE: "New value where we had one",
    CLASS_BLANK_HERE: "Blank here, value there",
    CLASS_BLANK_THERE: "Blank there, value here",
    CLASS_CONFLICT: "Conflict on a field",
    CLASS_TWO_PREMISES_ONE_PARCEL: "Two premises share one parcel",
    CLASS_ONE_PREMISE_TWO_PARCELS: "One premise on two parcels",
    CLASS_UNMATCHED: "Parcel with no premise",
    CLASS_PREMISE_NO_PARCEL: "Premise with no parcel",
}

# ── the disposition per field ─────────────────────────────────────────────

DISPOSITION_AUTO = "auto"
DISPOSITION_QUEUE = "queue"
DISPOSITION_NEVER = "never"

#: What a clerk calls each field. The KEY is the `premises` column; nothing
#: here is a database id reaching a screen (B14 rule 31) — a column name is the
#: engine's handle and `FIELD_LABELS` is what the row draws.
FIELD_LABELS = {
    "postal_code": "Postal code",
    "address_line": "Address line",
    "owner_manager": "Owner name",
    "premises_type": "Premise type",
    "inside_city_limits": "Inside city limits",
    "city": "City",
    "state": "State",
}

#: ⚠ **FIXED, AND A TENANT CANNOT WIDEN IT** (`RBR-17`, restating the
#: integration substrate's C25). These three decide what an address is CHARGED,
#: so they are a constant in code rather than a parameter on a screen — the
#: unsafe option is the one you type (hard-won law 3). A difference on one of
#: them is LISTED and nothing is written.
NEVER_TOUCH = ("inside_city_limits", "city", "state")

#: The card's `Apply automatically` and `Queue for a person` rows, minus the two
#: fields this product does not hold. See divergence 2 in the module docstring.
DEFAULT_AUTO_FIELDS = ("postal_code",)
DEFAULT_QUEUE_FIELDS = ("address_line", "owner_manager", "premises_type")

#: ⚠ **NAMED, COUNTED AND REPORTED RATHER THAN DROPPED.** `RB-120`'s disposition
#: table offers *Lot area* and *Zoning*; `premises` holds neither, in this
#: product or in B2. A runbook that quietly offered seven of nine fields would
#: report a clean reconciliation over two the county can disagree about and
#: nobody would ever see the gap — `G32`'s shape, which reported `0 unresolved`
#: truthfully over 21 live refusals.
FIELDS_THE_PRODUCT_DOES_NOT_HOLD = ("lot_area", "zoning")

# ── the outcomes one parcel can reach ─────────────────────────────────────
#
# ⚠ **`planned` IS NOT `skipped`.** A planned change is one this run WOULD make
# and did not; a skipped one is one nothing is going to do. `BR-RBS-035` counts
# every outcome including the ones with no record row, so a word collapsing the
# two would make the totals unreadable.
OUTCOME_APPLIED = "applied"
OUTCOME_PLANNED = "planned"
OUTCOME_NEEDS_A_PERSON = "needs_a_person"
OUTCOME_NEVER_TOUCHED = "never_touched"
OUTCOME_AGREES = "agrees"
OUTCOME_SKIPPED = "skipped"

# ── the steps, in the card's own order ────────────────────────────────────

STEP_GATHER = "gather_the_landed_batch"
STEP_MATCH = "match_parcels_to_premises"
STEP_CLASSIFY = "classify_each_difference"
STEP_DISPOSITION = "look_up_the_disposition_per_field"
STEP_CAP = "check_the_cap_and_the_guards"
STEP_APPLY = "apply_the_automatic_changes"
STEP_RAISE = "raise_the_rest_as_work_items"

STEP_LABELS = {
    STEP_GATHER: "Gather the landed batch",
    STEP_MATCH: "Match parcels to premises",
    STEP_CLASSIFY: "Classify each difference",
    STEP_DISPOSITION: "Look up the disposition per field",
    STEP_CAP: "Check the cap and the guards",
    STEP_APPLY: "Apply the automatic changes",
    STEP_RAISE: "Raise the rest as work items",
}

# ── fix routes ────────────────────────────────────────────────────────────
#
# ⚠ **EVERY ONE IS A PATH THIS PRODUCT ACTUALLY MOUNTS, VERIFIED AGAINST
# `07-frontend/src/App.tsx` ON 2026-09-06.** A fix route resolving to nothing is
# a dead button over a live finding — hard-won law 2's mirror, the shape that
# left the customer portal with two working doors out of eight — and nothing in
# the backend suite can see it, because a string is a string. Tenant-relative:
# the shell prefixes `/:tenant/`.
FIX_PREMISES = "premises"
FIX_IMPORT = "import"
FIX_INTEGRATIONS = "settings/integrations"


@dataclass(frozen=True)
class Difference:
    """One thing the county and we disagree about.

    A **field** difference carries `field`; a **structural** one — an unmatched
    parcel, a shared parcel — carries `None`, because the disagreement is about
    which rows are which and not about a value.

    ⚠ **NO FIELD HERE CARRIES A DATABASE ID AS A VISIBLE VALUE** (B14 rule 31).
    `premises_id` is the handle the port needs; `premises_label` is the premise
    number or its address, which is what a clerk can act on.

    ⚠ **`reason` IS A SENTENCE AND NEVER A RULE ID** (`BR-RBS-010`, B14 rule
    32). The rule travels in `decided_by_rule`, carried in `ReportRow.meta` and
    drawn by no block.
    """

    parcel_key: str
    parcel_row_no: int
    premises_id: str | None
    premises_label: str
    field: str | None
    field_label: str
    ours: str | None
    theirs: str | None
    difference_class: str
    disposition: str
    outcome: str
    reason: str
    decided_by_rule: str
    fix_route: str
    fix_label: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("a difference with no reason says nothing to anybody")
        if not self.fix_route.strip():
            raise ValueError(
                f"parcel {self.parcel_key!r} names no fix route. BR-RBS-011: a failure names "
                "its fix route, and a failure with no route is a defect in the runbook — a "
                "clerk reads what is wrong and has nowhere to go."
            )

    def as_row(self) -> dict[str, Any]:
        return {
            "parcel_key": self.parcel_key,
            "parcel_row_no": self.parcel_row_no,
            "premises_id": self.premises_id,
            "premises_label": self.premises_label,
            "field": self.field,
            "field_label": self.field_label,
            "ours": self.ours,
            "theirs": self.theirs,
            "difference_class": self.difference_class,
            "disposition": self.disposition,
            "outcome": self.outcome,
            "reason": self.reason,
            "decided_by_rule": self.decided_by_rule,
            "fix_route": self.fix_route,
            "fix_label": self.fix_label,
        }


@dataclass
class _StepResult:
    """What every set step returns — what it decided, and what it looked at.

    `checked` is not decoration. A step reporting nothing over an empty batch
    and a step reporting nothing over a batch that agrees are the same sentence
    with very different meanings, and a check whose output cannot tell a reader
    which is which is worse than no check at all (hard-won law 7).

    `reached` is `False` on every step after a stop — what the chain draws as
    `notReached`, rather than a blank cell, which reads as *nothing wrong*.
    """

    reached: bool = True
    stop: dict[str, Any] | None = None
    plan: list[dict[str, Any]] = field(default_factory=list)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "reached": self.reached,
            "plan": list(self.plan),
            "checked": dict(self.checked),
        }
        if self.stop is not None:
            out["stop"] = dict(self.stop)
        return out


# ── helpers ───────────────────────────────────────────────────────────────

_PUNCTUATION = re.compile(r"[^a-z0-9 ]+")
_SPACES = re.compile(r"\s+")


def _text(raw: Any) -> str | None:
    """A stored value as a clerk would read it, or `None` where there is none.

    An empty string and a `None` are the same fact — *nobody recorded this* —
    and collapsing them here is what makes *blank here* a class rather than two.
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        return "Yes" if raw else "No"
    value = str(raw).strip()
    return value or None


def _standardised(address: Any) -> str:
    """An address as a MATCH KEY — lower case, no punctuation, single spaces.

    ⚠ **THIS IS A KEY AND NEVER A STORED VALUE.** `premises.address_line` is the
    product's one address home (hard rule 8) and nothing here writes back a
    standardised form; a normalisation used as a comparison is a different thing
    from an address a clerk reads, and writing one over the other is how a
    utility ends up posting to `101 SMOKE TEST LN`.
    """
    text = _text(address) or ""
    return _SPACES.sub(" ", _PUNCTUATION.sub(" ", text.lower())).strip()


def _same(ours: str | None, theirs: str | None) -> bool:
    """Do these two say the same thing? Case- and space-insensitive, never fuzzy."""
    if ours is None or theirs is None:
        return ours is theirs
    return _SPACES.sub(" ", ours.strip().lower()) == _SPACES.sub(" ", theirs.strip().lower())


def _pair(
    column: str, premises: dict[str, Any], theirs_row: dict[str, Any]
) -> tuple[str | None, str | None, str | None, str | None]:
    """`(ours to compare, ours to show, theirs to compare, theirs to show)`.

    ⚠ **A COMPARISON VALUE AND A DISPLAY VALUE ARE DIFFERENT THINGS FOR EXACTLY
    ONE FIELD, AND GETTING IT WRONG REPORTS A DIFFERENCE ON EVERY ROW.** The
    premises TYPE is a lookup: the importer resolves a file's *"Single-family"*
    onto this tenant's own code `single_family`, so the codes are what agree or
    disagree, while `Single-family` and the file's own words are what a clerk
    reads on the row. Every other field is one value doing both jobs.
    """
    ours = _text(premises.get(column))
    theirs = _text(theirs_row.get(column))
    if column != "premises_type":
        return ours, ours, theirs, theirs
    return (
        ours,
        _text(premises.get("premises_type_label")) or ours,
        theirs,
        _text(theirs_row.get("premises_type_raw")) or theirs,
    )


def _stopped(ctx) -> dict[str, Any] | None:
    """The stop an earlier step recorded, or `None`. Read by every step after it."""
    for key in (STEP_GATHER, STEP_CAP):
        result = ctx.set_results.get(key) or {}
        stop = result.get("stop")
        if stop:
            return dict(stop)
    return None


def _never_reached(stop: dict[str, Any]) -> dict[str, Any]:
    return _StepResult(reached=False, checked={"never_reached_because": stop["headline"]}).as_dict()


def _plan(ctx) -> list[dict[str, Any]]:
    """The plan as the LAST step that touched it left it.

    Steps 2 to 5 each rewrite the whole plan rather than annotating rows in
    place, so the plan a later step reads is always one object with one author.
    Two steps editing one list is how a difference ends up carrying the class
    from one rule and the disposition from another.
    """
    for key in (STEP_CAP, STEP_DISPOSITION, STEP_CLASSIFY, STEP_MATCH):
        result = ctx.set_results.get(key) or {}
        if result.get("reached") and result.get("plan") is not None:
            return list(result["plan"])
    return []


def _batch(ctx) -> dict[str, Any] | None:
    """The landed batch this run is pinned to — read once per step that needs it.

    A run that names no batch takes the most recently staged one, which is what a
    person starting the run by hand means by *the file I just uploaded*. A run
    that NAMES one takes that one or nothing — never a different file, because
    silently reconciling against something else is how a clerk approves changes
    they never looked at.
    """
    named = _named_file(ctx)
    if ctx.params.get("batch") and named is None:
        # `DEF-INT-9850` — not a file id at all (the City's own hand-off, or a
        # value nobody could have uploaded). Never handed to a UUID lookup,
        # which raised inside the Apply request and answered the clerk 500.
        return None
    return metering_seam.staged_import_batch(PARCEL_IMPORT_TARGET, named)


def _named_file(ctx) -> str | None:
    """The parcel FILE this run was started with — an import run's id — or `None`.

    ⚠ **`DEF-INT-9850`: THE `batch` PARAMETER CARRIES TWO DIFFERENT THINGS.** A
    person names an uploaded file by its import run's id; the City's own
    *Apply* (`integrations.seams.runbooks.hand_off_gis_batch`) hands over a
    DESCRIPTION of what it pulled — `{"source": "gis", "rows": 7, "pages": 3}`.
    Until 2026-10-07 the second was passed straight to a UUID lookup, which
    raised `ValidationError` and turned every Apply at a utility that had added
    this runbook into a 500. A description is not a file: it opens the City
    door, and only a real id can be *"That parcel file is not here."*
    """
    import uuid

    raw = ctx.params.get("batch")
    if raw is None or isinstance(raw, Mapping):
        return None
    try:
        return str(uuid.UUID(str(raw).strip()))
    except (ValueError, AttributeError, TypeError):
        return None


def _city_hand_off(ctx) -> bool:
    """Was this run started by the City's own Apply (`DEF-INT-9850`)?"""
    raw = ctx.params.get("batch")
    return isinstance(raw, Mapping) and str(raw.get("source") or "") == "gis"


def _parcel_rows(batch: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Every parcel in the batch, sample rows INCLUDED.

    ⚠ **THE SAMPLE EXCLUSION IS A GUARD AND NOT A FILTER HERE, AND THAT IS THE
    WHOLE DIFFERENCE** (`BR-RBS-012`). A guarded subject is still pinned, still
    counted (`BR-RBS-035`) and still drawn on `RBS-004.4` with its reason; a row
    quietly dropped inside a read is invisible on every screen and its guard is
    a check that can never fire. So this returns what landed and
    `_sample_parcel_keys` marks which ones the guard will take.
    """
    if batch is None:
        return []
    return list(batch.get("rows") or [])


def _sample_parcel_keys(batch: dict[str, Any] | None) -> frozenset[str]:
    """Which parcels are SAMPLE data (`BR-TEN-057`, `RB-120`'s *Never include*).

    A sample import run is sample throughout, so the batch's own flag marks
    every row in it; a real run may still carry sample rows one at a time.
    """
    if batch is None:
        return frozenset()
    whole = bool(batch.get("is_sample"))
    return frozenset(
        _parcel_key(row)
        for row in (batch.get("rows") or [])
        if whole or row.get("is_sample")
    )


def _cap(ctx) -> int | None:
    """The tenant's own `Most changes per run`, from the runbook row.

    ⚠ **IT IS A COLUMN AND NOT A PARAMETER** (`RBR-03`, and divergence 3). One
    policy, one home; a parameter of the same name would be a second copy free
    to disagree with the one the Settings screen writes.
    """
    if ctx.run_id is None:
        return None
    return (
        models.RunbookRun.objects.filter(pk=ctx.run_id)
        .values_list("runbook__cap", flat=True)
        .first()
    )


# ── the City door (`DEF-INT-9848`, PO ruling 2026-10-07) ──────────────────
#
# ⚠ **THE CITY'S CHECK MATCHES AND CLASSIFIES; THIS RUNBOOK DOES NOT DO IT
# AGAIN.** Steps 2–4 below were written for a parcel FILE, matched on
# `external_ref` — a migrating utility's own import key (`BR-MET-403`). The
# City's parcel number lives in `gis_parcel_id` (`BR-MET-1173`), and the City's
# check (`apps.integrations.gis_match`) already matches on it, falls back to
# the address, walks units, and applies `R28`'s *never touch by default*. A
# second match here would be a second implementation that disagrees with the
# Integrations screen's *Preview* about the same City on the same morning. So
# for the City door, step 1 gathers the check's answer ONCE and steps 2–4 report
# it in the runbook's own words and classes.

#: The City check's difference classes → this card's.
_CITY_CLASS = {
    "conflict": CLASS_CONFLICT,
    "new_value": CLASS_NEW_VALUE,
    "blank_theirs": CLASS_BLANK_THERE,
    "blank_ours": CLASS_BLANK_HERE,
    "two_premises_one_parcel": CLASS_TWO_PREMISES_ONE_PARCEL,
    "one_premises_two_parcels": CLASS_ONE_PREMISE_TWO_PARCELS,
    "unmatched": CLASS_PREMISE_NO_PARCEL,
}

#: The City check's dispositions → this card's. ⚠ `never_touch` is what `R28`
#: makes of EVERY address field today; nothing here can turn one on.
_CITY_DISPOSITION = {
    "never_touch": DISPOSITION_NEVER,
    "apply": DISPOSITION_AUTO,
    "queue": DISPOSITION_QUEUE,
}

#: What a clerk calls the fields the City's check compares that a parcel FILE
#: does not carry. Merged over `FIELD_LABELS` for City rows only.
CITY_FIELD_LABELS = {
    **FIELD_LABELS,
    "lat": "Latitude",
    "lng": "Longitude",
    "gis_status": "City status",
    "gis_parcel_id": "Parcel",
}

#: Where a City stop sends a person: the connection, which is where a key, an
#: address or a switch is changed.
FIX_LABEL_CONNECTION = "Open the connection"


def _city(ctx_or_view) -> dict[str, Any] | None:
    """What step 1 gathered from the City this run, or `None` for the file door."""
    return ((ctx_or_view.set_results.get(STEP_GATHER) or {}).get("city")) or None


def _pages_sentence(city: dict[str, Any]) -> str:
    """*Stopped after 3 of 70 pages.* — said whenever the City was not read whole.

    `DEF-INT-9849`: a run a person limited to a few pages must never read as
    the register. Empty when the walk was complete.
    """
    if city.get("complete", True):
        return ""
    read, total = city.get("pages_read"), city.get("pages_total")
    if total:
        return f"Stopped after {read} of {total} pages."
    return f"Stopped after {read} pages; the city has more."


def _city_sent(city: dict[str, Any]) -> str:
    """*The city sent 7 rows over 3 pages.* — singular where it is one."""
    rows, pages = int(city.get("city_rows") or 0), int(city.get("pages_read") or 0)
    return (
        f"The city sent {rows} {'row' if rows == 1 else 'rows'} over "
        f"{pages} {'page' if pages == 1 else 'pages'}."
    )


def _rows_from_city(report: dict[str, Any]) -> list[dict[str, Any]]:
    """The City check's differences and queue as this card's rows (`Difference`).

    Every row carries `source = "city"`, which is how step 4 knows to KEEP the
    City's disposition rather than re-derive one from `apply_automatically` —
    whose default (`postal_code`) would otherwise plan an address change `R28`
    forbids by default.
    """
    rows: list[dict[str, Any]] = []
    for one in report.get("differences") or ():
        klass = _CITY_CLASS.get(str(one.get("class")), CLASS_CONFLICT)
        disposition = _CITY_DISPOSITION.get(str(one.get("disposition")), DISPOSITION_QUEUE)
        structural = klass in (
            CLASS_TWO_PREMISES_ONE_PARCEL, CLASS_ONE_PREMISE_TWO_PARCELS, CLASS_PREMISE_NO_PARCEL,
        )
        field_name = None if structural else str(one.get("field") or "") or None
        label = CITY_FIELD_LABELS.get(field_name or "", "Parcel")
        ours, theirs = _text(one.get("ours")), _text(one.get("theirs"))
        if klass == CLASS_TWO_PREMISES_ONE_PARCEL:
            parcel = theirs or "—"
            reason = "More than one of our premises sits on this parcel."
            rule = "An ambiguous match is decided by a person, never by order"
        elif klass == CLASS_PREMISE_NO_PARCEL:
            parcel = _text(one.get("parcel")) or "—"
            reason = "The city has no address point for this premises."
            rule = "A premises the city cannot answer about is listed, never changed"
        elif disposition == DISPOSITION_NEVER:
            parcel = _text(one.get("parcel")) or "—"
            reason = f"{label} differs. It is never changed by default."
            rule = (
                "An address field is never written from the city's register until the "
                "utility turns it on"
            )
        elif disposition == DISPOSITION_AUTO:
            parcel = _text(one.get("parcel")) or "—"
            reason = f"{label} is set to apply automatically."
            rule = "The disposition per field is the utility's own setting"
        else:
            parcel = _text(one.get("parcel")) or "—"
            reason = f"{label} differs. A person decides."
            rule = "Every difference is classified before anything is decided"
        outcome = {
            DISPOSITION_NEVER: OUTCOME_NEVER_TOUCHED,
            DISPOSITION_AUTO: OUTCOME_PLANNED,
        }.get(disposition, OUTCOME_NEEDS_A_PERSON)
        row = Difference(
            parcel_key=parcel,
            parcel_row_no=0,
            premises_id=None,
            premises_label=str(one.get("label") or "—"),
            field=field_name,
            field_label=label,
            ours=ours,
            theirs=theirs,
            difference_class=klass,
            disposition=disposition,
            outcome=outcome,
            reason=reason,
            decided_by_rule=rule,
            fix_route=FIX_PREMISES,
            fix_label="Open premises →",
        ).as_row()
        row["source"] = "city"
        rows.append(row)

    for one in report.get("queue") or ():
        candidates = [str(key) for key in (one.get("candidates") or ()) if key]
        klass = CLASS_ONE_PREMISE_TWO_PARCELS if len(candidates) > 1 else CLASS_PREMISE_NO_PARCEL
        said = str(one.get("reason") or "").strip()
        reason = (said[:1].upper() + said[1:] + ("" if said.endswith(".") else ".")) if said else (
            "No single city parcel matched this premises."
        )
        row = Difference(
            parcel_key=" · ".join(candidates[:3]) or "—",
            parcel_row_no=0,
            premises_id=None,
            premises_label=str(one.get("label") or "—"),
            field=None,
            field_label="Parcel",
            ours="—",
            theirs=" · ".join(candidates[:3]) or None,
            difference_class=klass,
            disposition=DISPOSITION_QUEUE,
            outcome=OUTCOME_NEEDS_A_PERSON,
            reason=reason,
            decided_by_rule="An ambiguous match is decided by a person, never by order",
            fix_route=FIX_PREMISES,
            fix_label="Open premises →",
        ).as_row()
        row["source"] = "city"
        rows.append(row)
    return rows


def _gather_from_the_city(ctx, checked: dict[str, Any], names: list[Any]) -> dict[str, Any]:
    """Step 1's City door — ONE call to the City's check, pinned to this run.

    ⚠ **EVERY WAY IT CAN FAIL IS A STOP WITH A SENTENCE, NEVER A RAISE.** A
    refusal before dialling (switched off, sandbox, no layer), a City that
    answered *no* (`DEF-INT-9846`: our key, a moved layer, their error), a City
    that went silent, and a City that sent nothing each reach the run as one red
    chain cell and six *Never reached* (`BR-RBS-027`).
    """
    answer = integrations_seam.city_parcels(
        pages=ctx.params.get("pages"),
        started_by_name=ctx.params.get("started_by_name"),
    )
    checked["source"] = "city"
    if answer.get("refused"):
        checked["city_refused"] = answer.get("message_key") or "refused"
        return _StepResult(
            stop={
                "headline": str(answer.get("headline") or integrations_seam.CITY_REFUSED_GENERAL),
                "detail": (
                    "Nothing was compared and nothing was changed. Check the GIS connection, "
                    "then run this again."
                ),
                "fix_route": FIX_INTEGRATIONS,
                "fix_label": FIX_LABEL_CONNECTION,
            },
            checked=checked,
        ).as_dict()
    if answer.get("stopped"):
        checked["city_stop_reason"] = answer.get("stop_reason_key")
        return _StepResult(
            stop={
                "headline": str(answer.get("headline") or integrations_seam.CITY_REFUSED_GENERAL),
                "detail": (
                    "The city's register was not read, so nothing was compared and nothing "
                    "was changed. Check the GIS connection's address and key, then run this again."
                ),
                "fix_route": FIX_INTEGRATIONS,
                "fix_label": FIX_LABEL_CONNECTION,
            },
            checked=checked,
        ).as_dict()

    counts = dict(answer.get("counts") or {})
    city = {
        "rows": _rows_from_city(answer),
        "city_rows": int(counts.get("city_rows") or 0),
        "pages_read": int(counts.get("city_pages") or 0),
        "pages_total": counts.get("city_pages_total"),
        "complete": bool(answer.get("complete", True)),
        "premises_examined": int(counts.get("premises_examined") or 0),
        "units_examined": int(counts.get("units_examined") or 0),
        "premises_with_no_parcel": int(counts.get("unmatched_ours") or 0),
        "city_rows_with_no_premises": int(counts.get("city_rows_ignored") or 0),
        "differences_found": int(counts.get("differences_found") or 0),
        "fields_set_to_never_touch": int(counts.get("fields_set_to_never_touch") or 0),
        "queued": int(counts.get("queued") or 0),
    }
    checked.update(
        city_rows_read=city["city_rows"],
        city_pages_read=city["pages_read"],
        city_pages_total=city["pages_total"],
        city_read_whole=city["complete"],
        parcels_in_the_batch=city["city_rows"],
    )
    if city["city_rows"] == 0:
        # The City answered and sent no rows. On this deployment that used to be
        # the ONLY answer, because the fetch was a stub; it is now a real one.
        return _StepResult(
            stop={
                "headline": "Nothing has landed yet.",
                "detail": (
                    f"{', '.join(str(one) for one in names)} is connected and the city sent "
                    "no parcels for this run. Upload the county's parcel file, or start this "
                    "again later."
                ),
                "fix_route": FIX_IMPORT,
                "fix_label": "Upload parcels",
            },
            checked=checked,
        ).as_dict()
    result = _StepResult(checked=checked).as_dict()
    result["city"] = city
    return result


# ── step 1 · where today's parcels come from ──────────────────────────────


def step_gather_the_landed_batch(ctx, subjects) -> dict[str, Any]:
    """1 · Two doors, and the run STOPS when both are shut.

    `RB-120` step 1 reads *"Gather the landed batch — from the GIS connection,
    once, pinned to this run"*. The Product Owner's ruling of 2026-09-06 makes
    that one step with two halves: a **connection** may bring the parcels, and a
    **person** may upload them. This looks for both and says which it found.

    ⚠ **THE STOP IS A RESULT AND IT IS WRITTEN AS ONE.** `RUN_STATUS_STOPPED`
    already existed beside `done` and `failed`; nothing here raises and every
    later step reads *Never reached* (`BR-RBS-027`). The headline names BOTH
    absences, because *"no GIS connection"* alone would send somebody to
    Settings for an afternoon when uploading the county's file takes two
    minutes.
    """
    connections = integrations_seam.live_connections(GIS_PROVIDER_KEYS)
    working = [one for one in connections if one.get("enabled") and one.get("status") == "working"]
    batch = _batch(ctx)
    rows = _parcel_rows(batch)

    checked: dict[str, Any] = {
        "gis_connections_looked_for": len(GIS_PROVIDER_KEYS),
        "gis_connections_found": len(connections),
        "gis_connections_working": len(working),
        "connection_names": [one.get("display_name") or one.get("key") for one in working],
        "file_uploaded": batch is not None,
        "file_name": (batch or {}).get("file_name"),
        "file_status": (batch or {}).get("status"),
        "parcels_in_the_batch": len(rows),
        "sample_parcels_guarded": len(_sample_parcel_keys(batch)),
    }

    if batch is None and ctx.params.get("batch") and not _city_hand_off(ctx):
        # ⚠ **A FILE THAT WAS ASKED FOR AND IS NOT THERE IS ITS OWN SENTENCE.**
        # Telling a clerk *"nobody has uploaded a parcel file"* when they chose
        # one and it has since been loaded or rolled back would send them to do
        # something they have already done. A batch that has been LOADED is no
        # longer a batch — its rows are premises — which is the common way this
        # happens and the reason the detail says so.
        return _StepResult(
            stop={
                "headline": "That parcel file is not here.",
                "detail": (
                    "The file this run was started with is not waiting to be reconciled. "
                    "It may already have been loaded, or rolled back. Choose the file to "
                    "compare, or upload the county's parcels again."
                ),
                "fix_route": FIX_IMPORT,
                "fix_label": "Choose a parcel file",
            },
            checked=checked,
        ).as_dict()

    if batch is None and not working:
        # ⚠ BOTH DOORS SHUT. The headline names both, in the order a clerk can
        # act on them.
        offline = [one for one in connections if not one.get("enabled")]
        detail = (
            "A GIS connection is set up and switched off."
            if offline
            else "No GIS connection is set up."
        )
        return _StepResult(
            stop={
                "headline": "Nothing to compare.",
                "detail": (
                    f"{detail} Nobody has uploaded a parcel file either, so there is nothing "
                    "to put beside our premises. Upload the county's parcel file, or connect "
                    "a GIS service."
                ),
                "fix_route": FIX_IMPORT,
                "fix_label": "Upload parcels",
            },
            checked=checked,
        ).as_dict()

    if batch is None:
        # ── `DEF-INT-9848` · A LIVE CONNECTION AND NO FILE: ASK THE CITY ────
        # ⚠ **THIS BRANCH WAS A STOP UNTIL 2026-10-07** — *"Nothing has landed
        # yet."* on every run with a working connection, because the fetch it
        # waited for (`reconcile_parcels`) was bound to nothing. It now asks
        # the City's own parcel check, once, through this module's seam. A file
        # somebody uploaded still wins: a person who chose a file meant it.
        return _gather_from_the_city(ctx, checked, checked["connection_names"])

    checked["source"] = "file"
    return _StepResult(checked=checked).as_dict()


# ── step 2 · the match ladder ─────────────────────────────────────────────


def _parcel_key(row: dict[str, Any]) -> str:
    """What the county calls this parcel — its own reference, or the row number.

    Never a database id (B14 rule 31), and never blank: a parcel a clerk cannot
    name is a row they cannot find in their own file.
    """
    mapped = row.get("mapped") or {}
    for candidate in (mapped.get("external_ref"), row.get("source_key")):
        text = _text(candidate)
        if text:
            return text
    return f"Row {row.get('row_no')}"


def step_match_parcels_to_premises(ctx, subjects) -> dict[str, Any]:
    """2 · By parcel id, then by standardised address (the card's own ladder).

    Two key tiers and no third. **A name is not an identifier and neither is a
    postcode**: matching on anything looser would attach the county's opinion to
    the wrong building, and this port is the only one in the thirteen that can
    move an address (hard rule 8).

    ⚠ **BOTH DIRECTIONS OF AMBIGUITY ARE CLASSES, NOT ERRORS.** Two premises
    carrying one parcel reference, and one premises matching two parcels in the
    file, are things a county's records genuinely do. Each is queued for a
    person with both sides shown; neither is silently taken by the first match,
    which is what a `dict` keyed on the reference would have done.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    city = _city(ctx)
    if city is not None:
        # `DEF-INT-9848` — the City's check matched; this reports its counts.
        # The plan stays empty here and step 3 takes the City's rows whole.
        return _StepResult(
            plan=[],
            checked={
                "matched_by": "the city's parcel check (parcel number, then address)",
                "parcels_examined": city["city_rows"],
                "city_pages_read": city["pages_read"],
                "city_pages_total": city["pages_total"],
                "city_read_whole": city["complete"],
                "premises_on_file": city["premises_examined"],
                "units_on_file": city["units_examined"],
                "premises_with_no_parcel": city["premises_with_no_parcel"],
                "city_rows_with_no_premises": city["city_rows_with_no_premises"],
            },
        ).as_dict()

    # ⚠ **THE SET STEP WALKS `subjects`, WHICH IS THE PINNED SET WITH THE
    # GUARDED SUBJECTS ALREADY REMOVED** (`executor.execute` hands a set step
    # `walked`). Re-reading the batch and ignoring this argument would walk the
    # sample parcels a guard had just excluded — a guard the run reports and
    # does not honour, which is worse than no guard at all.
    in_scope = {str(one.subject_id) for one in subjects}
    rows = [row for row in _parcel_rows(_batch(ctx)) if _parcel_key(row) in in_scope]
    # ⚠ **OUR SIDE IS FILTERED IN THE STEP AND THE EXCLUSION IS COUNTED.** A
    # premises is not a subject of this run, so there is no guard to draw for it
    # — but *Never include: Sample* applies to both sides, and a comparison
    # against a sample estate would report every real property as unmatched. The
    # number that was left out travels beside the number that was compared,
    # because a filter with no figure beside it is indistinguishable from an
    # empty one (hard-won law 7).
    everything = metering_seam.premises_for_reconciliation(include_sample=True)
    ours = [one for one in everything if not one.get("is_sample")]

    by_ref: dict[str, list[dict[str, Any]]] = {}
    by_address: dict[str, list[dict[str, Any]]] = {}
    for premises in ours:
        ref = _text(premises.get("external_ref"))
        if ref:
            by_ref.setdefault(ref.lower(), []).append(premises)
        key = _standardised(premises.get("address_line"))
        if key:
            by_address.setdefault(key, []).append(premises)

    matches: list[dict[str, Any]] = []
    claimed: dict[str, list[str]] = {}
    on_ref = on_address = unmatched = ambiguous = 0
    for row in rows:
        mapped = row.get("mapped") or {}
        parcel_key = _parcel_key(row)
        ref = _text(mapped.get("external_ref"))
        candidates = by_ref.get(ref.lower()) if ref else None
        matched_on = "parcel id"
        if not candidates:
            candidates = by_address.get(_standardised(mapped.get("address_line")))
            matched_on = "standardised address"
        if not candidates:
            matched_on = ""
            unmatched += 1
        elif len(candidates) > 1:
            ambiguous += 1
        elif matched_on == "parcel id":
            on_ref += 1
        else:
            on_address += 1
        for premises in candidates or []:
            claimed.setdefault(str(premises["premises_id"]), []).append(parcel_key)
        matches.append(
            {
                "parcel_key": parcel_key,
                "row_no": int(row.get("row_no") or 0),
                "theirs": dict(mapped),
                "candidates": list(candidates or []),
                "matched_on": matched_on,
            }
        )

    return _StepResult(
        plan=matches,
        checked={
            "parcels_examined": len(rows),
            "premises_on_file": len(ours),
            "premises_excluded_as_sample": len(everything) - len(ours),
            "premises_with_a_parcel_id": len(by_ref),
            "matched_on_parcel_id": on_ref,
            "matched_on_standardised_address": on_address,
            "matched_more_than_one_premises": ambiguous,
            "no_premises_found": unmatched,
            "premises_claimed_by_two_parcels": len(
                [one for one, keys in claimed.items() if len(keys) > 1]
            ),
        },
    ).as_dict()


# ── step 3 · the seven classes ────────────────────────────────────────────


def _difference_class(ours: str | None, theirs: str | None) -> str | None:
    """Which of the four VALUE classes this pair is, or `None` when they agree.

    *New value* and *conflict* are the same arithmetic and different words, and
    the card keeps them apart for a reason: a field the utility has never filled
    in is a gap somebody can close, and one where the two systems each hold a
    considered value is an argument somebody has to settle. This product cannot
    tell those apart from the values alone, so **a difference on a field a
    person must decide is a conflict and everything else is a new value** — the
    disposition, not a guess about intent, is what separates them.
    """
    if _same(ours, theirs):
        return None
    if ours is None and theirs is not None:
        return CLASS_BLANK_HERE
    if ours is not None and theirs is None:
        return CLASS_BLANK_THERE
    return CLASS_NEW_VALUE


def step_classify_each_difference(ctx, subjects) -> dict[str, Any]:
    """3 · Every disagreement in exactly one class (`RB-120`'s design note).

    The by-class table is the audit: each difference appears once, and the
    disposition column says what the utility's own settings did with it.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    city = _city(ctx)
    if city is not None:
        # `DEF-INT-9848` — the City's check already put each difference in one
        # class; its rows are this card's rows, each counted once.
        rows = list(city["rows"])
        tally: dict[str, int] = {}
        for one in rows:
            tally[one["difference_class"]] = tally.get(one["difference_class"], 0) + 1
        return _StepResult(
            plan=rows,
            checked={
                "differences_found": len(rows),
                "classified_by": "the city's parcel check",
                "fields_set_to_never_touch": city["fields_set_to_never_touch"],
                "fields_the_product_does_not_hold": list(FIELDS_THE_PRODUCT_DOES_NOT_HOLD),
                "by_class": tally,
            },
        ).as_dict()

    matches = _plan(ctx)
    claimed: dict[str, list[str]] = {}
    for match in matches:
        for premises in match["candidates"]:
            claimed.setdefault(str(premises["premises_id"]), []).append(match["parcel_key"])

    # ⚠ **A COLUMN THE FILE DOES NOT CARRY IS NOT A BLANK — IT IS A QUESTION
    # NOBODY ASKED, AND CONFLATING THE TWO WOULD REPORT *blank there, value
    # here* ON EVERY PREMISES FOR EVERY UNMAPPED FIELD.** A county export with
    # no state column would then produce one finding per property, all of them
    # meaningless, and the real differences would be lost inside them. So the
    # comparison is limited to the columns the batch actually holds, and the
    # ones it does not are counted and named.
    columns_in_the_file = {
        column
        for match in matches
        for column in (match["theirs"] or {})
    }

    plan: list[Difference] = []
    unreadable = 0
    for match in matches:
        candidates = match["candidates"]
        if not candidates:
            plan.append(
                Difference(
                    parcel_key=match["parcel_key"],
                    parcel_row_no=match["row_no"],
                    premises_id=None,
                    premises_label="No premises found",
                    field=None,
                    field_label="Parcel",
                    ours=None,
                    theirs=_text((match["theirs"] or {}).get("address_line")),
                    difference_class=CLASS_UNMATCHED,
                    disposition=DISPOSITION_NEVER,
                    outcome=OUTCOME_NEEDS_A_PERSON,
                    reason="This parcel is not one of ours, so nothing is created from it.",
                    decided_by_rule=(
                        "Whether the utility serves a parcel is a decision about the utility, "
                        "not a fact the county can state"
                    ),
                    fix_route=FIX_PREMISES,
                    fix_label="Open premises →",
                )
            )
            continue
        if len(candidates) > 1:
            plan.append(
                Difference(
                    parcel_key=match["parcel_key"],
                    parcel_row_no=match["row_no"],
                    premises_id=None,
                    premises_label=" · ".join(str(one["label"]) for one in candidates[:3]),
                    field=None,
                    field_label="Parcel",
                    ours="—",
                    theirs=f"Shared by {len(candidates)} premises",
                    difference_class=CLASS_TWO_PREMISES_ONE_PARCEL,
                    disposition=DISPOSITION_QUEUE,
                    outcome=OUTCOME_NEEDS_A_PERSON,
                    reason="More than one of our premises matches this parcel.",
                    decided_by_rule="An ambiguous match is decided by a person, never by order",
                    fix_route=FIX_PREMISES,
                    fix_label="Open both →",
                )
            )
            continue

        premises = candidates[0]
        parcels_here = claimed.get(str(premises["premises_id"]), [])
        if len(set(parcels_here)) > 1:
            plan.append(
                Difference(
                    parcel_key=match["parcel_key"],
                    parcel_row_no=match["row_no"],
                    premises_id=str(premises["premises_id"]),
                    premises_label=str(premises["label"]),
                    field=None,
                    field_label="Parcel",
                    ours=str(premises["label"]),
                    theirs=" · ".join(sorted(set(parcels_here))[:3]),
                    difference_class=CLASS_ONE_PREMISE_TWO_PARCELS,
                    disposition=DISPOSITION_QUEUE,
                    outcome=OUTCOME_NEEDS_A_PERSON,
                    reason="This premises matches more than one parcel in the file.",
                    decided_by_rule="An ambiguous match is decided by a person, never by order",
                    fix_route=FIX_PREMISES,
                    fix_label="Open premises →",
                )
            )
            continue

        theirs_row = match["theirs"] or {}
        for column, label in FIELD_LABELS.items():
            if column not in columns_in_the_file:
                continue
            ours_value, ours_shown, theirs_value, theirs_shown = _pair(
                column, premises, theirs_row
            )
            if column == "premises_type" and theirs_value is None:
                # The file named a type this tenant's own table does not hold,
                # so the importer could not resolve it — a half this step cannot
                # answer, counted rather than passed over as agreement
                # (hard-won law 7).
                unreadable += 1
                continue
            klass = _difference_class(ours_value, theirs_value)
            if klass is None:
                continue
            plan.append(
                Difference(
                    parcel_key=match["parcel_key"],
                    parcel_row_no=match["row_no"],
                    premises_id=str(premises["premises_id"]),
                    premises_label=str(premises["label"]),
                    field=column,
                    field_label=label,
                    ours=ours_shown,
                    theirs=theirs_shown,
                    difference_class=klass,
                    disposition=DISPOSITION_QUEUE,
                    outcome=OUTCOME_NEEDS_A_PERSON,
                    reason=f"{label} differs. Matched on {match['matched_on']}.",
                    decided_by_rule="Every difference is classified before anything is decided",
                    fix_route=FIX_PREMISES,
                    fix_label="Open premises →",
                )
            )

    by_class: dict[str, int] = {}
    for one in plan:
        by_class[one.difference_class] = by_class.get(one.difference_class, 0) + 1

    return _StepResult(
        plan=[one.as_row() for one in plan],
        checked={
            "differences_found": len(plan),
            "fields_compared_per_premises": len(
                [one for one in FIELD_LABELS if one in columns_in_the_file]
            ),
            "fields_the_file_does_not_carry": sorted(
                FIELD_LABELS[one] for one in FIELD_LABELS if one not in columns_in_the_file
            ),
            "fields_the_product_does_not_hold": list(FIELDS_THE_PRODUCT_DOES_NOT_HOLD),
            "premise_types_the_file_did_not_name": unreadable,
            "by_class": by_class,
        },
    ).as_dict()


# ── step 4 · the disposition per field ────────────────────────────────────


def _disposition_for(row: dict[str, Any], params) -> str:
    """Auto, queue, or never — the utility's own table, with never fixed.

    ⚠ **`never` IS CHECKED FIRST AND IS NOT READ FROM THE PARAMETERS.** A tenant
    who put `city` in *Apply automatically* would otherwise widen the never-touch
    list through the back door, which `RBR-17` forbids by name.

    ⚠ **A STRUCTURAL DIFFERENCE TAKES ITS DISPOSITION FROM ITS CLASS AND NOT
    FROM A FIELD IT DOES NOT HAVE.** An ambiguous match is a person's decision
    whatever the field table says; a parcel with no premises is *listed only*
    while *Create premises we do not have* is off, which is the card's own
    disposition column — `OQ-INT-1472` closed **no** on 2026-09-04, because
    whether the utility serves a parcel is a decision about the utility rather
    than a fact the county can state.
    """
    field_name = row["field"]
    if field_name is None:
        if row["difference_class"] != CLASS_UNMATCHED:
            return DISPOSITION_QUEUE
        return (
            DISPOSITION_QUEUE
            if params.get("create_premises_we_do_not_have")
            else DISPOSITION_NEVER
        )
    if field_name in NEVER_TOUCH:
        return DISPOSITION_NEVER
    auto = params.get("apply_automatically") or DEFAULT_AUTO_FIELDS
    if isinstance(auto, str):
        auto = (auto,)
    if field_name in tuple(auto):
        return DISPOSITION_AUTO
    return DISPOSITION_QUEUE


def step_look_up_the_disposition_per_field(ctx, subjects) -> dict[str, Any]:
    """4 · Auto · queue · never, from the utility's own table.

    ⚠ **A NEVER-TOUCH FIELD IS SKIPPED WHATEVER THE CLASS SAYS** (`RB-120` step
    5, `RBR-17`). The conflict is still LISTED — a county disagreeing with us
    about a city boundary is worth knowing even when we refuse to change it —
    and its outcome is *never touched* rather than *needs a person*, because
    there is nothing a person is being asked to decide.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    plan = _plan(ctx)
    out: list[dict[str, Any]] = []
    counts = {DISPOSITION_AUTO: 0, DISPOSITION_QUEUE: 0, DISPOSITION_NEVER: 0}
    for one in plan:
        row = dict(one)
        if row.get("source") == "city":
            # `DEF-INT-9848` — KEPT, never re-derived. The City's check decided
            # this under `R28` (*never touch by default*); re-deriving it from
            # `apply_automatically` would plan a postal-code change the PO's
            # ruling forbids by default.
            counts[row["disposition"]] = counts.get(row["disposition"], 0) + 1
            out.append(row)
            continue
        disposition = _disposition_for(row, ctx.params)
        counts[disposition] = counts.get(disposition, 0) + 1
        row["disposition"] = disposition
        if disposition == DISPOSITION_NEVER and row["field"] is not None:
            row["outcome"] = OUTCOME_NEVER_TOUCHED
            row["difference_class"] = CLASS_CONFLICT
            row["reason"] = (
                f"{row['field_label']} differs and is never changed from an outside feed."
            )
            row["decided_by_rule"] = (
                "The fields that decide what an address is charged are never written by a feed"
            )
        elif disposition == DISPOSITION_NEVER:
            # An unmatched parcel while *Create premises we do not have* is off.
            # It is LISTED — a parcel the county serves and we do not is worth
            # knowing — and nothing is created from it.
            row["outcome"] = OUTCOME_NEVER_TOUCHED
        elif disposition == DISPOSITION_AUTO:
            row["outcome"] = OUTCOME_PLANNED
            row["reason"] = f"{row['field_label']} is set to apply automatically."
            row["decided_by_rule"] = "The disposition per field is the utility's own setting"
        out.append(row)

    return _StepResult(
        plan=out,
        checked={
            "differences_dispositioned": len(out),
            "apply_automatically": counts[DISPOSITION_AUTO],
            "queue_for_a_person": counts[DISPOSITION_QUEUE],
            "never_touch": counts[DISPOSITION_NEVER],
            "never_touch_fields": list(NEVER_TOUCH),
        },
    ).as_dict()


# ── step 5 · the cap and the guards ───────────────────────────────────────


def step_check_the_cap_and_the_guards(ctx, subjects) -> dict[str, Any]:
    """5 · **A cap REFUSES the run; it never truncates** (`BR-RBS-006`).

    The card's own step 5. `runbooks.cap` is the tenant's *Most changes per run*
    and this compares the number of automatic changes against it: over the cap,
    the run **stops** with the two numbers in the sentence and nothing is
    written — a truncated run would apply 500 of 640 changes and leave nobody
    able to say which 140 were left.

    ⚠ **THE ENGINE-LEVEL REFUSAL IS `CR-075` TASK `L4`'s AND IS NOT BUILT.**
    `runbooks.cap` is a column that nothing reads today (`BR-RBS-006` has no
    implementation anywhere in the backend, verified 2026-09-06). This step is
    the card's, not a second copy of the engine's: when `L4` lands the run will
    be refused before step 1 and this step will agree with it. **A cap of `None`
    is not a limit of zero** — it is a tenant who has not set one, and the run
    proceeds with the absence reported.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    plan = _plan(ctx)
    automatic = [one for one in plan if one["disposition"] == DISPOSITION_AUTO]
    cap = _cap(ctx)
    checked = {
        "automatic_changes_planned": len(automatic),
        "most_changes_per_run": cap,
        "never_touch_fields": list(NEVER_TOUCH),
        "guarded_by_never_touch": len(
            [one for one in plan if one["disposition"] == DISPOSITION_NEVER]
        ),
    }

    if cap is not None and len(automatic) > int(cap):
        return _StepResult(
            plan=plan,
            stop={
                "headline": "More changes than this runbook may make.",
                "detail": (
                    f"{len(automatic)} changes would be applied and the limit is {cap}. "
                    "Nothing has been changed. Raise the limit, narrow what applies "
                    "automatically, or work through the list by hand."
                ),
                "fix_route": FIX_PREMISES,
                "fix_label": "Open premises",
            },
            checked=checked,
        ).as_dict()

    return _StepResult(plan=plan, checked=checked).as_dict()


# ── step 6 · apply the automatic changes ──────────────────────────────────


def step_apply_the_automatic_changes(ctx, subject) -> dict[str, Any]:
    """6 · Through the metering service, one field on one premises (`BR-RBS-022`).

    ⚠ **THE RUNBOOK NEVER WRITES A PREMISES ROW.** `apply_premise_change` is a
    named port into `metering`'s own `update_premises`, which is `S14`'s edit:
    ONE transaction, audited with the full before-and-after (`BR-MET-048`). The
    before-and-after this card promises is that audit row, not a second copy
    kept here.

    ⚠ **PER-RECORD, SO EACH PARCEL RUNS INSIDE ITS OWN SAVEPOINT.** The executor
    opens a nested `transaction.atomic()` around this call. On PostgreSQL that
    is the ONLY thing that lets the run continue after one refused row —
    without it the first `IntegrityError` aborts the whole transaction and every
    later change is lost at COMMIT, and the suite's in-memory SQLite cannot see
    the difference (hard-won law 14).
    """
    if _stopped(ctx):
        return {
            "outcome": OUTCOME_SKIPPED,
            "reason": "The run stopped before this step.",
            "decided_by_rule": "A required step failing makes every later step Never reached",
            "fix_route": FIX_PREMISES,
        }

    key = str(subject.subject_id)
    mine = [one for one in _plan(ctx) if one["parcel_key"] == key]
    if not mine:
        return {
            "outcome": OUTCOME_AGREES,
            "reason": "This parcel says the same as our premises.",
            "decided_by_rule": "A parcel with nothing to change is reported, never acted on",
            "fix_route": FIX_PREMISES,
            "data": {"label": subject.label, "parcel": key},
        }

    automatic = [one for one in mine if one["disposition"] == DISPOSITION_AUTO]
    queued = [one for one in mine if one["disposition"] == DISPOSITION_QUEUE]
    never = [one for one in mine if one["disposition"] == DISPOSITION_NEVER]
    label = mine[0]["premises_label"]

    if not automatic:
        outcome = OUTCOME_NEEDS_A_PERSON if queued else OUTCOME_NEVER_TOUCHED
        first = (queued or never)[0]
        return {
            "outcome": outcome,
            "reason": first["reason"],
            "decided_by_rule": first["decided_by_rule"],
            "fix_route": first["fix_route"],
            "data": {
                "label": label,
                "parcel": key,
                "queued": len(queued),
                "never_touched": len(never),
            },
        }

    changes = {one["field"]: one["theirs"] for one in automatic}
    try:
        ctx.port("apply_premise_change").call(
            actor=None,
            premises_id=automatic[0]["premises_id"],
            changes=changes,
        )
    except PortNotBound as refusal:
        # ⚠ **THE PORT IS ALWAYS CALLED AND ITS OWN REFUSAL IS THE OUTCOME.**
        # There is no `if is_bound` branch: `BR-RBS-003` makes dry and live one
        # code path, and a branch would be a second path proving nothing about
        # the first. The refusal is raised before any SQL is issued, so
        # hard-won law 14's aborted-transaction trap is not in play — and the
        # savepoint above covers the day a bound writer refuses for real.
        return {
            "outcome": OUTCOME_PLANNED,
            "reason": (
                f"{len(automatic)} change(s) ready to apply. Nothing is changed yet."
            ),
            "decided_by_rule": str(refusal),
            "fix_route": FIX_PREMISES,
            "data": {
                "label": label,
                "parcel": key,
                "planned": len(automatic),
                "queued": len(queued),
                "never_touched": len(never),
            },
        }
    applied = ctx.set_results.setdefault("applied", [])
    applied.append(key)
    return {
        "outcome": OUTCOME_APPLIED,
        "reason": f"{len(automatic)} change(s) applied from the county's records.",
        "decided_by_rule": "The disposition per field is the utility's own setting",
        "fix_route": FIX_PREMISES,
        "data": {
            "label": label,
            "parcel": key,
            "applied": len(automatic),
            "queued": len(queued),
            "never_touched": len(never),
        },
    }


def step_raise_the_rest_as_work_items(ctx, subjects) -> dict[str, Any]:
    """7 · Both values shown, so a person decides in one look.

    ⚠ **A WORK ITEM IS AN ENGINE ACT AND NOT A PORT** (`BR-RBS-022`,
    `12-the-contract.md` §6). `raise_work_item` is refused BY NAME as a port
    precisely so a Check can populate the work list while holding no writer at
    all; the engine's upsert-by-fingerprint is `CR-075` task `H1`, which is
    **phase 4**. Until it lands the queued rows are readable on this run's own
    result screen and are not yet gathered into `RBS-007` with every other open
    item — the rows are not lost, only ungathered, and the execution plan says
    so in as many words.

    So this step COUNTS what a person is being handed and reports it. It
    declares `writes=True` because the act it names is a write, exactly as the
    card marks it — the claim is about the STEP, and a step that stopped
    claiming it would be a quieter runbook doing the same thing.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)
    plan = _plan(ctx)
    queued = [one for one in plan if one["disposition"] == DISPOSITION_QUEUE]
    return _StepResult(
        plan=plan,
        checked={
            "queued_for_a_person": len(queued),
            "work_items_raised": 0,
            "work_list_state": (
                "The work list is built in a later wave; these are on this run's own screen."
            ),
            "parcels_changed": len(list(ctx.set_results.get("applied") or [])),
        },
    ).as_dict()


# ── the report ────────────────────────────────────────────────────────────


def _plan_from_view(view) -> list[dict[str, Any]]:
    for key in (STEP_RAISE, STEP_CAP, STEP_DISPOSITION, STEP_CLASSIFY):
        result = view.set_results.get(key) or {}
        if result.get("reached") and result.get("plan"):
            return list(result["plan"])
    return []


def _chain(view, stop: dict[str, Any]) -> Block:
    """Seven cells: the one that stopped the run, and the ones that never ran."""
    stopped_at = STEP_GATHER
    for key in (STEP_GATHER, STEP_CAP):
        if (view.set_results.get(key) or {}).get("stop"):
            stopped_at = key
            break
    cells = []
    seen_stop = False
    for index, key in enumerate(STEP_LABELS, start=1):
        if key == stopped_at:
            seen_stop = True
            state, note = "bad", stop["headline"]
        elif seen_stop:
            state, note = "notReached", "Never reached"
        else:
            state, note = "good", "Done"
        cells.append(
            {
                "id": key,
                "position": index,
                "label": STEP_LABELS[key],
                "state": state,
                "note": note,
            }
        )
    return Block(
        block="chain",
        payload={
            "label": f"The run stopped at step {[*STEP_LABELS].index(stopped_at) + 1}.",
            "cells": cells,
        },
    )


def _queue_columns() -> list[dict[str, Any]]:
    return [
        {"key": "premises", "label": "Premises"},
        {"key": "field", "label": "Field"},
        {"key": "ours", "label": "Ours"},
        {"key": "theirs", "label": "Theirs"},
        {"key": "class", "label": "Class"},
    ]


def _queue_row(index: int, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"difference-{index}",
        "cells": {
            "premises": {"kind": "text", "text": row["premises_label"]},
            "field": {"kind": "text", "text": row["field_label"]},
            "ours": {"kind": "text", "text": row["ours"] or "—"},
            "theirs": {"kind": "text", "text": row["theirs"] or "—"},
            "class": {"kind": "text", "text": CLASS_LABELS[row["difference_class"]]},
        },
        # ⚠ CARRIED, NEVER DRAWN — the renderer walks `columns`, so nothing here
        # reaches a screen. `decided_by_rule` MUST NOT: B14 rule 32 forbids a
        # rule id in clerk-facing copy. It is here because the result file and
        # the conformance test both read it, and the report is the only frozen
        # artefact.
        "meta": {
            "decided_by_rule": row["decided_by_rule"],
            "outcome": row["outcome"],
            "parcel": row["parcel_key"],
        },
    }


def _records_columns() -> list[dict[str, Any]]:
    return [
        {"key": "parcel", "label": "Parcel"},
        {"key": "premises", "label": "Premises"},
        {"key": "field", "label": "Field"},
        {"key": "why", "label": "Why"},
        {"key": "fix", "label": "Fix"},
    ]


def _record_row(index: int, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"row-{index}",
        "cells": {
            "parcel": {"kind": "text", "text": row["parcel_key"]},
            "premises": {"kind": "text", "text": row["premises_label"]},
            "field": {"kind": "text", "text": row["field_label"]},
            "why": {"kind": "text", "text": row["reason"]},
            "fix": {"kind": "link", "label": row["fix_label"], "to": row["fix_route"]},
        },
        "meta": {
            "decided_by_rule": row["decided_by_rule"],
            "outcome": row["outcome"],
            "class": row["difference_class"],
        },
    }


def report(view) -> list[Block]:
    """Composed from records and counts at CLOSE, then frozen (`BR-RBS-020`).

    Two compositions, because a stopped run and a finished one are two states
    and one shape cannot say both:

    * **stopped** — `Verdict` · `Sentence` · `Chain` · `Records` (empty). The
      chain draws *Never reached* on the steps that did not run, and the KPI
      strip is deliberately ABSENT: a strip reading *0 applied · 0 queued · 0
      never touched* over a run that examined nothing is indistinguishable from
      a morning on which the county agreed with us about everything, which is
      precisely the failure hard-won law 7 is about.
    * **finished** — `Verdict` · `KPIs` · `Breakdown` · `Row decisions` ·
      `Records` · `Downloads`, which is `RB-120`'s own block list plus the
      verdict the header consumes.

    Every name is one of the twelve (`BR-RBS-021`); no thirteenth is minted.
    """
    stop = None
    for key in (STEP_GATHER, STEP_CAP):
        stop = (view.set_results.get(key) or {}).get("stop")
        if stop:
            break

    if stop:
        return [
            Block(
                block="verdict",
                payload={
                    "word": "Stopped",
                    "tone": "warning",
                    "count": stop["headline"],
                    "detail": stop["detail"],
                },
            ),
            Block(
                block="sentence",
                payload={"tone": "muted", "label": "What to do", "text": stop["detail"]},
            ),
            _chain(view, stop),
            Block(
                block="records",
                payload={
                    "columns": _records_columns(),
                    "rows": [],
                    "total": 0,
                    "empty": {"title": stop["headline"], "helper": stop["detail"]},
                },
            ),
        ]

    plan = _plan_from_view(view)
    acted = any(record.outcome == OUTCOME_APPLIED for record in view.records)
    gathered = (view.set_results.get(STEP_GATHER) or {}).get("checked") or {}
    matched = (view.set_results.get(STEP_MATCH) or {}).get("checked") or {}
    classified = (view.set_results.get(STEP_CLASSIFY) or {}).get("checked") or {}

    automatic = [one for one in plan if one["disposition"] == DISPOSITION_AUTO]
    queued = [one for one in plan if one["disposition"] == DISPOSITION_QUEUE]
    unmatched = [one for one in plan if one["difference_class"] == CLASS_UNMATCHED]
    shared = [one for one in plan if one["difference_class"] == CLASS_TWO_PREMISES_ONE_PARCEL]
    # ⚠ **THE TILES MUST ADD UP AND THE CARD'S OWN FIVE OVERLAP IF READ NAIVELY.**
    # *Never touched* is a FIELD we refuse to change; *Parcels unmatched* is a
    # parcel with no premises, which also has nothing written. Counting the
    # second inside the first would show one difference in two tiles and the
    # by-class table would not agree with the strip.
    never = [
        one
        for one in plan
        if one["disposition"] == DISPOSITION_NEVER and one["field"] is not None
    ]
    # ⚠ **ONLY FIELD DIFFERENCES REACH `row_decisions`, AND THAT IS A STATED
    # DIVERGENCE FROM `RB-120`'s QUEUED TABLE.** *Accept theirs → · Keep ours*
    # is a choice between two named VALUES — `RowDecisionsBlock`'s own rule —
    # and there are no two values on *two premises share one parcel*, whose card
    # row carries *Open both →* instead. One block cannot draw two different
    # pairs of buttons, so the ambiguities are drawn in `Records` with their own
    # fix route and the decision table stays a decision table.
    decidable = [one for one in queued if one["field"] is not None]
    # ⚠ `DEF-INT-9848` — a premises NO City parcel matched is queued with no
    # field too, and it is not AMBIGUOUS: nothing matched, rather than two
    # things. Counting it under *Ambiguous match* labelled 16 of 16 wrongly on
    # the first walkthrough.
    ambiguous = [
        one
        for one in queued
        if one["field"] is None and one["difference_class"] != CLASS_PREMISE_NO_PARCEL
    ]
    word = "Applied" if acted else "To apply"
    detail = (
        f"{gathered.get('parcels_in_the_batch', 0)} parcels landed · "
        f"{classified.get('differences_found', 0)} differences."
        if acted
        else "Nothing is changed until a writer is bound for this runbook."
    )
    city = _city(view)
    if city is not None:
        # `DEF-INT-9848` / `DEF-INT-9849` — say WHERE the parcels came from and
        # HOW MUCH of the City was read, first, so a run limited to three pages
        # cannot be read as the register.
        detail = " ".join(
            part
            for part in (
                _city_sent(city),
                _pages_sentence(city),
                detail,
            )
            if part
        )

    by_class: dict[str, dict[str, int]] = {}
    for one in plan:
        tally = by_class.setdefault(
            one["difference_class"], {"count": 0, "auto": 0, "queue": 0, "never": 0}
        )
        tally["count"] += 1
        tally[one["disposition"]] += 1

    return [
        Block(
            block="verdict",
            payload={
                "word": word,
                "tone": "success" if not queued else "warning",
                "count": (
                    f"{len(automatic)} {'applied' if acted else 'to apply'}. "
                    f"{len(queued)} need you."
                ),
                "detail": detail,
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "applied",
                        "label": word,
                        "value": {"kind": "text", "text": str(len(automatic))},
                        "detail": None if acted else "Planned — nothing is changed yet",
                    },
                    {
                        "id": "queued",
                        "label": "Queued for you",
                        "value": {"kind": "text", "text": str(len(queued))},
                    },
                    {
                        "id": "never",
                        "label": "Never touched",
                        "value": {"kind": "text", "text": str(len(never))},
                        "detail": "Listed, nothing changed",
                    },
                    {
                        "id": "unmatched",
                        "label": "Parcels unmatched",
                        "value": {"kind": "text", "text": str(len(unmatched))},
                    },
                    {
                        "id": "shared",
                        "label": "Two premises, one parcel",
                        "value": {"kind": "text", "text": str(len(shared))},
                    },
                ]
            },
        ),
        Block(
            block="breakdown",
            payload={
                "heading": "By difference class",
                "columns": [
                    {"key": "class", "label": "Class"},
                    {"key": "count", "label": "Count", "numeric": True},
                    {"key": "disposition", "label": "Disposition"},
                    {"key": "happened", "label": "What happened"},
                ],
                "rows": [
                    {
                        "id": f"class-{name}",
                        "cells": {
                            "class": {"kind": "text", "text": CLASS_LABELS[name]},
                            "count": {"kind": "text", "text": str(tally["count"])},
                            "disposition": {
                                "kind": "text",
                                "text": " · ".join(
                                    part
                                    for part, key in (
                                        ("Auto", "auto"),
                                        ("Queue", "queue"),
                                        ("Never", "never"),
                                    )
                                    if tally[key]
                                )
                                or "—",
                            },
                            "happened": {
                                "kind": "text",
                                "text": (
                                    f"{tally['auto']} {'applied' if acted else 'to apply'} · "
                                    f"{tally['queue']} queued · {tally['never']} listed"
                                ),
                            },
                        },
                    }
                    for name, tally in sorted(
                        by_class.items(), key=lambda pair: -pair[1]["count"]
                    )
                ],
            },
        ),
        Block(
            block="row_decisions",
            payload={
                "heading": "Queued for a person",
                "columns": _queue_columns(),
                "rows": [_queue_row(index, row) for index, row in enumerate(decidable, start=1)],
                "choices": [
                    {"id": "accept_theirs", "label": "Accept theirs →"},
                    {"id": "keep_ours", "label": "Keep ours"},
                ],
            },
        ),
        Block(
            block="records",
            payload={
                "columns": _records_columns(),
                "rows": [
                    _record_row(index, row)
                    for index, row in enumerate(queued + never + unmatched, start=1)
                ],
                "total": len(queued) + len(never) + len(unmatched),
                "chips": [
                    {
                        "id": "all",
                        "label": "All",
                        "count": len(queued) + len(never) + len(unmatched),
                    },
                    {"id": "queued", "label": "Queued for you", "count": len(queued)},
                    {"id": "ambiguous", "label": "Ambiguous match", "count": len(ambiguous)},
                    {"id": "never", "label": "Never touched", "count": len(never)},
                    {"id": "unmatched", "label": "Unmatched", "count": len(unmatched)},
                ],
                "empty": {
                    "title": "The county and our records agree.",
                    "helper": (
                        f"{matched.get('parcels_examined', 0)} parcels compared against "
                        f"{matched.get('premises_on_file', 0)} premises. Nothing is waiting "
                        "for you."
                    ),
                },
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"id": "applied", "label": word, "format": "csv"},
                    {"id": "queued", "label": "Queued", "format": "csv"},
                ]
            },
        ),
    ]


# ── the guard and the pinned scope ────────────────────────────────────────


#: Where `resolve()` leaves the guard its answer, so the guard costs no query.
#: `apply_guards` runs once per subject immediately after `pin_scope`, and a
#: guard that re-read the batch would read it once per parcel.
SAMPLE_KEYS = "_sample_parcel_keys"


def _is_sample(ctx, subject) -> bool:
    """`RB-120`'s *Never include: Sample* (`BR-TEN-057`, `BR-RBS-012`).

    ⚠ **IT IS A GUARD AND NOT A FILTER INSIDE A READ, WHICH IS THE WHOLE
    DIFFERENCE.** A guarded subject is still pinned and still counted
    (`BR-RBS-035`), and `RBS-004.4` draws the control disabled WITH its reason
    rather than hiding it; a row quietly dropped inside `resolve()` is invisible
    on every screen and its guard is a check that can never fire.
    """
    return str(subject.subject_id) in (ctx.set_results.get(SAMPLE_KEYS) or frozenset())


def resolve(ctx):
    """The pinned set: **one subject per parcel in the batch** (`BR-RBS-019`).

    ⚠ **THE UNIT IS THE PARCEL AND NOT THE DIFFERENCE.** The card's *subject and
    unit of work* row reads *Parcel ↔ premise*: the batch is what lands and the
    PARCEL is what gets decided, one record row and one savepoint each. The
    DIFFERENCES are counted by class and drawn as rows — `BR-RBS-035`, a volume
    runbook keeps a row for what it acted on and a count per outcome for the
    rest.

    ⚠ **RESOLVED ONCE AND FROZEN** (`BR-RBS-009`). A premises somebody edits
    while the run is going is not re-read; the fingerprint the executor computes
    is how a later reader proves the set did not move.

    ⚠ **AN EMPTY SET IS THE CORRECT ANSWER WHEN THE RUN IS ABOUT TO STOP**, and
    it is not an error. Step 1 says why in a sentence a clerk can read; a
    `resolve()` that raised would turn a designed outcome into a stack trace.
    """
    batch = _batch(ctx)
    rows = _parcel_rows(batch)
    # The guard's answer, computed once here rather than once per subject.
    ctx.set_results[SAMPLE_KEYS] = _sample_parcel_keys(batch)
    return [
        SubjectRef(
            subject_type="parcel",
            subject_id=_parcel_key(row),
            label=_parcel_key(row),
        )
        for row in rows
    ]


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="GIS reconciliation",
    kind=models.KIND_ACTION,
    category="data_sync",
    subject_type="parcel",
    unit_of_work="a parcel matched to a premises",
    # ⚠ MANUAL AND SCHEDULE, NOT `batch.landed` — see the module docstring. A
    # person starts it, and the event is emitted by nothing (`CR-069`).
    triggers=(models.TRIGGER_MANUAL, models.TRIGGER_SCHEDULE),
    tags=("Service points",),
    parameters=(
        Parameter(
            name="batch",
            type=PARAM_REF_OBJECT,
            label="The parcel file",
        ),
        Parameter(
            name="match_on",
            type=PARAM_ENUM,
            label="Match on",
            required=True,
            default="parcel_id_then_standardised_address",
            # ⚠ ONE CHOICE, AND IT IS THE LADDER THE CARD NAMES. A dropdown
            # offering a looser key would let a county's opinion be attached to
            # the wrong building through the one port that can move an address.
            choices=("parcel_id_then_standardised_address",),
        ),
        Parameter(
            name="apply_automatically",
            type=PARAM_ENUM,
            label="Apply automatically",
            default="postal_code",
            # Two of the card's three — *Lot area* and *Zoning* — are columns
            # this product does not hold; see divergence 2.
            choices=("postal_code", "address_line", "owner_manager", "premises_type"),
        ),
        Parameter(
            name="never_touch",
            type=PARAM_REF_SETTING,
            label="Never touch",
            setting_key="integrations.gis.never_touch",
        ),
        Parameter(
            name="create_premises_we_do_not_have",
            type=PARAM_TOGGLE,
            label="Create premises we do not have",
            # ⚠ **OFF, AND `OQ-INT-1472` CLOSED THAT WAY ON 2026-09-04.**
            # Whether the utility serves a parcel is a decision about the
            # utility, not a fact the county can state.
            default=False,
        ),
        Parameter(
            name="pages",
            type=PARAM_TEXT,
            label="City pages to read",
            # ⚠ `DEF-INT-9849` — EMPTY MEANS THE WHOLE REGISTER, and that is the
            # right default here: this runbook runs on the runbooks worker, not
            # inside a web request, so the 60-second limit that makes the
            # Integrations screen's *Preview* stop at three pages does not apply.
            # A number is for a person testing the City by hand (PO 2026-10-07,
            # *"we will call APi manually and test it first"*); every report
            # then says *Stopped after N of M pages*.
            # ⚠ **TEXT, NOT INTEGER, ON PURPOSE.** The **Run ▶** dialog
            # (`RunbookSetupPage.tsx`, `CR-173-BRC10`) offers a box for the
            # TEXT inputs only, so an integer input would be declared and
            # untypeable at the one moment a person runs this by hand —
            # hard-won law 2. The number is checked where it is used:
            # `gis.pages_or_refuse` stops step 1 with *"Give pages as a whole
            # number."* rather than reading a bad value as the whole register.
            default=None,
        ),
    ),
    guards=(
        Guard(key="sample", label="Never include: Sample", applies=_is_sample),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(
            key=STEP_GATHER,
            label=STEP_LABELS[STEP_GATHER],
            mode=MODE_SET,
            run=step_gather_the_landed_batch,
        ),
        Step(
            key=STEP_MATCH,
            label=STEP_LABELS[STEP_MATCH],
            mode=MODE_SET,
            run=step_match_parcels_to_premises,
        ),
        Step(
            key=STEP_CLASSIFY,
            label=STEP_LABELS[STEP_CLASSIFY],
            mode=MODE_SET,
            run=step_classify_each_difference,
        ),
        Step(
            key=STEP_DISPOSITION,
            label=STEP_LABELS[STEP_DISPOSITION],
            mode=MODE_SET,
            run=step_look_up_the_disposition_per_field,
        ),
        Step(
            key=STEP_CAP,
            label=STEP_LABELS[STEP_CAP],
            mode=MODE_SET,
            run=step_check_the_cap_and_the_guards,
        ),
        # ⚠ THE ONLY PER-RECORD STEP, AND THE ONLY ONE THAT CALLS A PORT. One
        # parcel, one savepoint (hard-won law 14), one record row carrying the
        # plan and the outcome together.
        Step(
            key=STEP_APPLY,
            label=STEP_LABELS[STEP_APPLY],
            mode=MODE_PER_RECORD,
            run=step_apply_the_automatic_changes,
            writes=True,
        ),
        Step(
            key=STEP_RAISE,
            label=STEP_LABELS[STEP_RAISE],
            mode=MODE_SET,
            run=step_raise_the_rest_as_work_items,
            writes=True,
        ),
    ),
    ports=("apply_premise_change",),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-032 (EP-RBS-05; CR-075 wave Q′)
# generated: 2026-09-06 by the CR-075 wave Q′ integration-runbooks lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — every runbooks route is a GET and POST /runbooks/{key}/runs is wave L) E=n/a(no screen — RBS-004 and RBS-006 render any runbook; RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_032_gis_reconciliation.py · pytest tests/test_rbs_sync_runbooks_pg.py (PostgreSQL) · pytest tests/test_us_rbs_015_conformance.py · G115 (the import census) · G20 (the seam implementers)
# exceptions: nothing is changed — `engine.acts.LIVE_ENABLED_RUNBOOKS` is empty so every port is handed writer-less; the KPI strip says "To apply" while nothing is applied; *Lot area* and *Zoning* are not columns in this product and the count is reported rather than dropped; the engine-level cap refusal is task L4's and step 5 is the card's own check
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
