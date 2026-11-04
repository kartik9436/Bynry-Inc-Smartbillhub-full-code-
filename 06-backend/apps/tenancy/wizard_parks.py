# ── Trace ──────────────────────────────────────────────
# Change:   CR-035 step 6 part 2 — the SERVICE behind Park.
#           Screens: S19 move-in · S20 move-out · TRF-02 · DSC-02 · the
#           new-connect wizard — the five that render the park panel and have
#           had nowhere to park to.
# Rules:    BR-SHL-048 (a parked wizard changes NOTHING until it is executed —
#           PO 2026-08-26, verbatim "Option A - Unitl move in executed, no
#           records updates") · BR-SHL-047 (every wizard parks) · BR-SHL-046
#           (one declared step list drives the bar and the resume) ·
#           B19 §12.2 (Save & exit writes nothing; Park records what is
#           awaited) · BR-SHL-025 (server-enforced RBAC) · BR-AUD-006 (PII
#           enters an audit payload masked only) · CLAUDE.md rules 1 · 7
# Defect:   DEF-746 — the control is inert on five of six wizards while a
#           signed rule says every wizard parks.
# Tests:    06-backend/tests/test_cr035_wizard_parks.py
# Impacts:  apps/tenancy/wizard_parks_api.py (its only caller) ·
#           config/urls.py (which mounts that) · 07-frontend's
#           `wizardParkPort()`, which returns null until this is served
# ───────────────────────────────────────────────────────
"""The write path and the read model for `wizard_parks` — a clerk's parked draft.

**BR-SHL-048, in one line: a parked wizard changes NOTHING until it is
executed.** The Product Owner's words, 2026-08-26: *"Option A - Unitl move in
executed, no records updates."* A clerk parks a move-in for **Unit 12, 500 Main
St** on **26 August** waiting on a **$150 deposit** and comes back on
**2 September**; in between **Unit 12 reads Vacant**, no account exists, no
occupancy begins and no bill changes. Everything this module does has to leave
that sentence true.

WHAT THIS SERVICE DELIBERATELY DOES NOT DO — AND WHY EACH ABSENCE IS THE RULE
-----------------------------------------------------------------------------
**(a) It resolves nothing.** `subject_ref` holds the unit, account and premises
ids the clerk chose as **copied values**, and this module never joins to them,
never looks them up to check they exist and never "helpfully" expands them into
a label at write time. BR-SHL-048 (a): an FK is a RELATIONSHIP and the ruling
says there is none until execution. A lookup at park time would re-create the
relationship in code that the schema was shaped to refuse — and the day it
raised on a deleted unit, a draft would have started blocking something.

**(b) It does not validate the DOMAIN CONTENTS of `values`.** Not the unit's
vacancy, not the plan version, not the deposit amount, not the applicant's
email. Everything in a draft was true on the day it was typed; by the day it is
resumed the unit may be taken and the tariff may have a new version. So the
wizard re-runs every check on resume (BR-SHL-048 (b)), and a check duplicated
here would be a second, staler copy of the law that would eventually disagree
with the first. **What IS validated is the ENVELOPE** — the flow is one of five,
the step indexes something, a reason for waiting is present, and nothing is
absurdly large. That is the boundary, and it is drawn on purpose.

**(c) It refuses nothing on discard.** A parked draft is a draft of a FORM.
CLAUDE.md rule 4's financial immutability governs issued invoices, invoice
lines, payments and journal lines; a half-typed move-in is none of those, has
moved no money and has posted nothing. So `discard` deletes the row, and that
is also what makes an erasure request answerable at all for the PII a parked
move-in holds before any customer row exists.

WHAT IT DOES DO
---------------
Park · list · resume · update · discard, every one of them tenant-scoped
(CLAUDE.md rule 1) and every one of them audited (rule 7).

⚠ **`values` NEVER ENTERS AN AUDIT PAYLOAD, AND NEITHER DOES `subject_label`.**
A parked move-in carries the incoming occupant's name, email and phone while
there is no customer row to attach them to, and `subject_label` is a street
address. BR-AUD-006 admits PII to a payload in MASKED form only, and this module
has no masker — so the trail records the ENVELOPE (flow, step, what is awaited,
the reminder, the copied ids) and a `values_fields` count, which is enough to
answer *who parked what and when* without copying a person's phone number into a
second table. Stated here rather than left to a reader to notice.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from django.core import exceptions as django_exceptions
from django.db import transaction
from django.utils import timezone

from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

from apps.tenancy.models import WIZARD_PARK_FLOWS, WizardPark

#: The five flows, re-exported so a caller never re-declares the tuple. The
#: schema's `ck_wizard_parks_flow` holds the same five, so a typo cannot create
#: a sixth flow nothing can resume — this check exists to turn that into a 422
#: the clerk can read rather than an IntegrityError that reads like an outage.
FLOWS: tuple[str, ...] = WIZARD_PARK_FLOWS

#: Matching `customers.ServiceRequest`'s own park (`_text(waiting_on, 120)`).
#: ⚠ Deliberately the SAME NUMBER as the flow where parking already works: one
#: "Waiting on" list cannot carry two contracts for one column, and the nine
#: reasons are what the SCREEN offers — the column stores what was chosen, and
#: the vocabulary stays OPEN (free text) for exactly that reason.
WAITING_ON_MAX_CHARS = 120

#: `service_request_service._MAX_TEXT`, again for the same reason.
NOTE_MAX_CHARS = 2000

#: "Unit 12, 500 Main St" is twenty characters. Two hundred is an envelope
#: bound, not a rule about labels.
LABEL_MAX_CHARS = 200

#: The `values` and `subject_ref` size ceiling, per field. Same 32 KB as
#: BR-SHL-024's preference value — the precedent in this module for "a JSON blob
#: a client hands us", and one number is easier to keep true than two. A draft
#: of a six-step form is a few hundred bytes; this stops a bug, not a clerk.
JSON_MAX_BYTES = 32 * 1024

#: `PositiveSmallIntegerField`'s own ceiling. The lower bound is the rule
#: (`ck_wizard_parks_step`, step >= 1 — a step is an index into a declared list
#: and zero indexes nothing, BR-SHL-046); the upper bound is only here so a
#: nonsense value comes back as a 422 instead of a database error. **No per-flow
#: step count is enforced here**: the declared step lists live in the frontend
#: (`moveShared.tsx`), and duplicating their lengths in Python would be a second
#: copy of BR-SHL-046's "ONE declared step list" that is free to disagree.
STEP_MAX = 32767

_SECONDS_PER_DAY = 86_400


# ── plumbing ────────────────────────────────────────────────────────────────
def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _audit(actor: Any, action: str, park_id: Any, **kw: Any) -> None:
    """CLAUDE.md rule 7 — who, when, before→after, for every act on a draft.

    See the module docstring for what is deliberately NOT in the payload:
    `values` (a person's name, email and phone before any customer row exists)
    and `subject_label` (a street address). BR-AUD-006 admits PII masked only
    and there is no masker here, so the trail carries the envelope instead.
    """
    core_audit.write_row(
        action=action,
        entity_type="wizard_park",
        entity_id=park_id,
        actor_user_id=_actor_id(actor),
        before=kw.get("before"),
        after=kw.get("after"),
    )


def _text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned[:limit] or None


def _refuse(code: str, message_key: str, **params: Any) -> None:
    """Every refusal here is a CATALOG exception with a resolving message key.

    G32: a `message_key` with no catalogue sentence renders as SILENCE now that
    `params.detail` is suppressed (PO 2026-08-19) — so each of the seven keys
    this module raises is written in all eleven catalogues, and G33's twelve-word
    limit is what keeps them readable.
    """
    raise errors.ValidationError(code, message_key=message_key, br_ref="BR-SHL-048", params=params)


# ── envelope validation — and NOTHING about the contents (BR-SHL-048 (b)) ───
def _clean_flow(raw: Any) -> str:
    flow = str(raw or "").strip()
    if not flow:
        _refuse(errors.VAL_REQUIRED, "shell.wizardPark.flowRequired")
    if flow not in FLOWS:
        _refuse(errors.VAL_UNKNOWN_LOOKUP, "shell.wizardPark.flowUnknown", value=flow)
    return flow


def _clean_step(raw: Any) -> int:
    try:
        step = int(raw)
    except (TypeError, ValueError):
        # ONE sentence for both refusals, two CODES — a clerk reads the same
        # true thing either way ("that is not a step"), and the envelope still
        # tells a caller whether the value was the wrong SHAPE (VAL-002) or the
        # wrong SIZE (VAL-003).
        _refuse(errors.VAL_FORMAT, "shell.wizardPark.stepInvalid", value=str(raw))
    if step < 1 or step > STEP_MAX:
        _refuse(errors.VAL_RANGE, "shell.wizardPark.stepInvalid", value=step)
    return step


def _clean_waiting_on(raw: Any) -> str:
    """FREE TEXT, and that is the decision — see WAITING_ON_MAX_CHARS.

    ⚠ **EMPTY IS NOW LAWFUL AND MEANS *A DRAFT* (`CR-122-BRC06`, PO ruling
    2026-09-19).** This function used to refuse it, and its reason was sound
    while it held: *"`Save & exit` leaves quietly and writes no row at all, so
    a row with no reason is a park that forgot the one thing it is for."* The
    PO overruled the premise rather than the reasoning — `Save & exit` now
    writes a row, because a clerk who keyed five steps and a $150.00 deposit
    was losing all of it, unwarned.

    **B19 §12.2's two controls are untouched.** `Park` asks *what are you
    waiting for?* and fills this; `Save & exit` does not ask and leaves it
    empty. Telling the two apart is READING THIS COLUMN and nothing else —
    see `WizardPark.waiting_on` for why there is no second flag.
    """
    return str(_text(raw, WAITING_ON_MAX_CHARS) or "")


#: Which flows take a number the moment their draft is written, and from which
#: series. A flow that is not here allocates nothing — see the docstring below
#: for why that is still the right answer for three of the five.
#:
#: ⚠ **THE VALUE IS THE SERIES THE FINISHED RECORD DRAWS FROM, NOT A NEW ONE.**
#: `core.numbering.MOVE_IN` / `MOVE_OUT` are the same two keys
#: `customers.moves.SERIES_BY_KIND` allocates a completed move from, so a draft
#: and the record it becomes are numbered out of ONE counter. A second scheme
#: would give one job two numbers, which is the cost `move_reads
#: ._requests_by_account_no` already records one table over.
DRAFT_REFERENCE_SERIES: dict[str, str] = {
    "move_in": "move_in",
    "move_out": "move_out",
}

#: `CON-26-0129` is eleven characters. Sixty-four is an envelope bound, not a
#: rule about numbering — the same posture `LABEL_MAX_CHARS` takes above.
REFERENCE_MAX_CHARS = 64

#: **`BR-SHL-048 (d)` — the number a park CARRIES from the record it is already
#: working on** (PO ruling 2026-09-21, verbatim: *"this is big problem - we
#: cannot create two build - you can update the existing build"*).
#:
#: ⚠ **THIS IS A COPIED VALUE AND NOT A SERIES ALLOCATION, WHICH IS THE WHOLE
#: DISTINCTION.** `DRAFT_REFERENCE_SERIES` above MINTS a number for work that
#: does not exist yet. A New Connect wizard opened on a build an approval
#: already raised is finishing `CON-26-0129`, which HAS a number, and minting a
#: second one would be the paper half of the defect this clause was ruled on.
#: So the wizard copies the record's own number onto `subject_ref` — clause
#: (a)'s copied values, never a foreign key — and the park takes it verbatim.
#:
#: ⚠ **A FLOW THAT CARRIES NOTHING IS UNCHANGED.** A New Connect started from
#: scratch has no record, sends no `connection_no`, and parks with no reference
#: exactly as it did before; `BR-MET-112` — nothing is written until the last
#: button — is untouched.
#: ⚠ **`move_in_no` JOINED 2026-09-22 (`BR-CUS-1090`), AND IT IS THE SAME
#: CLAUSE AND NOT A SECOND MECHANISM.** Approving a service request now raises a
#: move-in job that takes `MVI-{YY}-{0000}` from the `move_in` series on the
#: spot, and a clerk has been quoting it since the moment they pressed. A wizard
#: opened on that job is FINISHING a move-in that already has a number, exactly
#: as a New Connect opened on a raised build is finishing `CON-26-0129`, so it
#: carries the number instead of minting a second one. **A move-in wizard opened
#: from scratch carries nothing, sends no `move_in_no`, and mints from
#: `DRAFT_REFERENCE_SERIES` exactly as it did before** — that path is untouched.
#: ⊕ **`request_no` JOINED 2026-10-05 (`CR-171-BRC10` P1.08, J3) — SAME CLAUSE
#: AGAIN.** *Edit* on a move-in REQUEST opens the four-step Add form and parks
#: what is not the request's own (`customers.move_in_request`). That draft is
#: the request's, which already has `SR-26-0014`; minting an `MVI-` number for
#: it would spend one before anybody approved anything, and approval then raises
#: the job under ANOTHER — two numbers for one move-in. Last in the tuple, so a
#: park that also carries a job or build number still takes that one first.
CARRIED_REFERENCE_KEYS: tuple[str, ...] = ("connection_no", "move_in_no", "request_no")


def _carried_reference(subject_ref: dict[str, Any]) -> str | None:
    """The existing record's own number off `subject_ref`, or None.

    `BR-SHL-048 (d)`. It reads a COPIED VALUE out of the park's own payload and
    resolves nothing — no query against the record, no join, no foreign key.
    Clause (a) is untouched and is what makes this possible at all.

    ⚠ **A NUMBER ANOTHER DRAFT ALREADY HOLDS IS DECLINED, NOT REFUSED.**
    `uq_wizard_parks_tenant_reference_ci` is one number to one draft, so two
    clerks with the same build open in two tabs would otherwise meet that
    constraint as a 500 and lose an afternoon's typing. The posture is
    `_allocate_draft_reference`'s, in its own words: *"A MISSING SERIES IS
    REPORTED BY ABSENCE, NOT BY REFUSAL … losing an afternoon's typing because
    a lookup table is empty would be the original defect wearing a new hat."*
    The second draft parks with a blank reference — which is what every New
    Connect park did until today — and still carries the build's id in
    `subject_ref`, so it still FINISHES that build rather than minting a second
    one. **The number is the label; the id is the ruling.**

    ⚠ **AND THE HONEST LIMIT OF THAT, SAID OUT LOUD: THIS IS A CHECK-THEN-
    INSERT, SO IT COVERS THE SEQUENTIAL CASE AND NOT A DEAD HEAT.** Two parks of
    one build in the SAME instant both read no row and both insert, and the
    second meets `uq_wizard_parks_tenant_reference_ci` as an `IntegrityError`.
    That is rarer than the case this removes by orders of magnitude — a clerk
    opens a second tab minutes later, not microseconds — and it is recorded
    rather than papered over, because a comment claiming a guarantee is not the
    guarantee (CLAUDE.md hard-won law 1). **It is not caught here on purpose:**
    an `except IntegrityError` inside this `atomic()` block would be carrying on
    inside a transaction PostgreSQL has already poisoned, which loses the park
    at COMMIT anyway and passes green on this repo's SQLite suite (law 14). The
    cure is a SAVEPOINT around the insert, and it belongs with a measurement
    that says the race happens.
    """
    for key in CARRIED_REFERENCE_KEYS:
        carried = _text(subject_ref.get(key), REFERENCE_MAX_CHARS)
        if carried is None:
            continue
        taken = WizardPark.objects.filter(
            tenant_id=_tenant_id(), reference__iexact=carried
        ).exists()
        return None if taken else carried
    return None


def _draft_reference(flow: str, subject_ref: dict[str, Any]) -> str | None:
    """The reference a new draft is written with — **carried, else allocated**.

    Two mechanisms and the order is the ruling: a park finishing a record that
    already exists takes THAT record's number (`BR-SHL-048 (d)`); a park of
    work that does not exist yet mints one from its own series
    (`CR-122-BRC06`). Nothing takes both, and a park that carries one burns no
    counter.
    """
    carried = _carried_reference(subject_ref)
    if carried is not None:
        return carried
    return _allocate_draft_reference(flow)


def _allocate_draft_reference(flow: str, *, on: Any = None) -> str | None:
    """`MVI-{YY}-{0000}` for a move-in draft, `MVO-{YY}-{0000}` for a move-out,
    or None — and **None is a real answer, never an error** (`CR-122-BRC06`).

    ⚠ **THE SAME SERIES THE FINISHED RECORD DRAWS FROM**, so the number a clerk
    quotes while the job is in their hands is the number it is filed under.
    `customers.services.move_in` and `.move_out` both ADOPT this rather than
    allocating a second; `moves.MoveRecord.move_no`'s own docstring is where
    the other half lives.

    ⚠ **`move_out` JOINED ON 2026-09-20 AND THE REASON IT WAS EXCLUDED IS THE
    REASON IT IS NOW IN** (PO ruling of that date, option A — decision log
    *"TEN MOVE-OUT RULINGS IN ONE SITTING"* item 9; `OQ-CUS-12489` closes).
    This docstring read *"ONLY `move_in` ALLOCATES, DELIBERATELY … minting
    numbers for four other flows THAT NOTHING DISPLAYS would be a series
    burning through its counter with no screen to show for it"*. That was
    exactly right the day it was written and the condition it rests on stopped
    holding the same week: the Move-outs tab now lists unfinished move-outs
    (PO ruling 2026-09-19, verbatim `yes`) and the blueprint's p117 draws that
    row WITH a reference — `MVO-26-0087 · 2 of 6 · In progress`.

    ⚠ **AND IT WAS NOT COSMETIC, WHICH IS WHY IT IS WORTH THIS MUCH SPACE
    (`DEF-CUS-5922`).** `/moves/{ref}` is keyed on the reference and
    `move_record_reads._park_by_reference` filters `reference__iexact`, which
    **NULL can never match**. So a parked move-out could not be opened from its
    own record AT ALL, and the `Resume` door built on 2026-09-19 was
    unreachable for it — a screen, a route and a control that were live, tested
    and impossible to get to. Two lanes found it from opposite ends on the same
    evening. Hard-won law 2's mirror: a live screen behind a dead door.

    ⚠ **THE OTHER THREE FLOWS STILL ALLOCATE NOTHING, AND THAT IS THE ORIGINAL
    REASONING STILL HOLDING RATHER THAN AN OVERSIGHT.** `transfer`, `disconnect`
    and `new_connect` drafts appear only in the parked-drafts panel, which
    draws no reference column, so a number minted for one would be spent where
    nobody can read it. Each has its own series ready for the day it gets a
    list of its own; adding a line to `DRAFT_REFERENCE_SERIES` is the whole
    change, and the screen is the condition.

    ⚠ **A MISSING SERIES IS REPORTED BY ABSENCE, NOT BY REFUSAL** — the posture
    `moves._allocate_move_no` takes in as many words: *"A household must not be
    refused a move-in because nobody configured numbering. The move is the
    regulated act; its reference is not."* A draft with no reference is still a
    draft, and losing an afternoon's typing because a lookup table is empty
    would be the original defect wearing a new hat. A tenant provisioned before
    the `move_out` series was seeded gets a move-out draft with no reference —
    which is the state every move-out draft was in until today, so nothing
    regresses and the record page simply cannot address that one.
    """
    series = DRAFT_REFERENCE_SERIES.get(flow)
    if series is None:
        return None
    from core import numbering as core_numbering

    try:
        from apps.customers import seams as customers_seams

        today = on or customers_seams.tenant_today()
        return str(core_numbering.next_number(series, today))
    except Exception:  # noqa: BLE001 - see the docstring: absence, never refusal
        return None


def _clean_json_object(raw: Any, field: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        # ⚠ `field` is a PARAM, not part of the sentence: `values` and
        # `subject_ref` are internal names and G28 keeps internal references off
        # a utility's screen. The envelope still carries it for a developer.
        _refuse(errors.VAL_FORMAT, "shell.wizardPark.objectExpected", field=field)
    try:
        size = len(json.dumps(raw, default=str).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="shell.wizardPark.objectExpected",
            br_ref="BR-SHL-048",
            params={"field": field},
        ) from exc
    if size > JSON_MAX_BYTES:
        raise errors.BizError(
            errors.BIZ_CAP,
            message_key="shell.wizardPark.tooLarge",
            br_ref="BR-SHL-048",
            params={"field": field, "limit": JSON_MAX_BYTES, "size": size},
        )
    return raw


def _clean_remind_on(raw: Any) -> date | None:
    """ISO `YYYY-MM-DD`, or nothing.

    ⚠ **A PAST DATE IS ACCEPTED.** A reminder that has already come round is
    exactly the draft the clerk most needs to see, and refusing one would be a
    rule nobody made — the same reasoning that keeps a park from expiring after
    N days (BR-SHL-047's open half, settled as moot by BR-SHL-048 (c)).
    """
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw).strip())
    except ValueError as exc:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="shell.wizardPark.remindOnFormat",
            br_ref="BR-SHL-048",
            params={"value": str(raw)},
        ) from exc


# ── reads ───────────────────────────────────────────────────────────────────
def park_row(park_id: Any, *, lock: bool = False) -> WizardPark:
    """One draft, tenant-scoped.

    A row belonging to another tenant is a **404, never a 403** (HR-1): the
    boundary must not confirm that the row exists. RLS FORCE refuses it at the
    database too, so this filter is the app half of a two-layer guarantee and
    not the only thing standing there — but it IS the half a bug can remove,
    which is why the isolation suite proves both.
    """
    try:
        qs = WizardPark.objects.filter(tenant_id=_tenant_id(), id=park_id)
        if lock:
            qs = qs.select_for_update()
        row = qs.first()
    except (django_exceptions.ValidationError, ValueError, TypeError) as exc:
        # ⚠ **A MALFORMED ID IS A 404, NOT A 500.** `<str:park_id>` accepts any
        # segment, and Django raises on a value the UUID column cannot hold
        # BEFORE any query runs — an exception the BE-02 handler does not map,
        # so it renders as an unhandled 500 that reads like an outage. A park id
        # that is not a park id names no row, and "names no row" is a 404 by
        # HR-1. The same answer as a foreign tenant's id, byte for byte.
        raise errors.deny_as_not_found("BR-TEN-003") from exc
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def age_days(parked_at: Any, *, now: Any = None) -> int | None:
    """Whole days since the park, floored at zero.

    ⚠ **THE ARITHMETIC MATCHES `parkAgeDays` IN `WizardFrame.tsx` EXACTLY** —
    `floor((now - parkedAt) / 86_400_000)`, negatives clamped to 0 — because the
    same number is rendered in two places (beside the control inside the wizard,
    and in the AGE column of the "Waiting on" list) and two implementations of
    one figure eventually disagree by a day.

    It is load-bearing, not decoration: BR-SHL-048 accepts that a parked
    move-out is invisible and *"the remind-on date and the visible age … are the
    only thing stopping a draft sitting forever"*.
    """
    if parked_at is None:
        return None
    moment = now or timezone.now()
    days = int((moment - parked_at).total_seconds() // _SECONDS_PER_DAY)
    return max(days, 0)


def row_dict(park: WizardPark, *, now: Any = None) -> dict[str, Any]:
    """The wire shape — one shape for the list, the create and the resume.

    `values` and `subject_ref` are handed back verbatim: this row exists so a
    wizard can rehydrate what was typed and land on the step it was parked at
    (CR-035 step 6 part 4), and anything this service reshaped on the way out
    would have to be un-reshaped on the way back in.
    """
    return {
        "id": str(park.id),
        "flow": park.flow,
        "subject_label": park.subject_label,
        "subject_ref": park.subject_ref,
        "step": park.step,
        "values": park.values,
        # `CR-122-BRC06` — the Move-ins tab draws a REFERENCE column over an
        # OPEN counter (blueprint p073), and an open draft is what that counter
        # counts. NULL where no series is configured, and the screen says so
        # rather than printing a dash it invented.
        "reference": park.reference or None,
        # ⚠ **EMPTY IS *A DRAFT*, NOT *NO REASON GIVEN*.** A screen that renders
        # this blank as "waiting on nothing" would be reading a `Save & exit` as
        # a `Park`. See `WizardPark.waiting_on`.
        "waiting_on": park.waiting_on,
        "is_draft": park.waiting_on == "",
        "park_note": park.park_note,
        "remind_on": park.remind_on.isoformat() if park.remind_on else None,
        "parked_at": park.parked_at.isoformat() if park.parked_at else None,
        "parked_by": str(park.parked_by_id) if park.parked_by_id else None,
        # ⚠ **THE NAME AS WELL AS THE ID, AND THE NAME IS THE ONE THE SCREEN
        # USES.** The "Waiting on" list says who is waiting, and an internal
        # uuid on a utility's screen is noise to them and a leak to us (G28).
        # `parked_by` IS a real FK — one of the only two BR-SHL-048 (a) allows —
        # so this is a lawful join, unlike anything in `subject_ref`.
        "parked_by_name": (park.parked_by.full_name or None) if park.parked_by_id else None,
        "age_days": age_days(park.parked_at, now=now),
    }


def parks_queryset(*, flow: str | None = None, mine_user_id: Any = None):
    """The clerk's "Waiting on" list as a **LAZY QUERYSET** — newest first,
    tenant-scoped.

    ⚠ **IT RETURNS A QUERYSET AND NEVER A LIST, AND THAT IS `NFR-3` (DEF-SHL-5748).**
    `StandardPagination.paginate_queryset` slices whatever it is handed. Handed a
    LIST it slices in Python, which means every row of the match set is built
    before fifty are drawn; handed a QUERYSET it slices in SQL and the page is a
    `LIMIT`/`OFFSET` the database applies. The wire envelope is identical either
    way — `count`/`next`/`previous`/`results` — so no test that counts returned
    rows can tell the two apart, and that is exactly how the Python page survived
    (hard-won law 7: ask what would make this check pass wrongly). The proof is a
    QUERY-COUNT and a `LIMIT` assertion, in
    `tests/test_def_shl_5748_wizard_park_paging.py`.

    `mine` is a filter on `parked_by`, not a security boundary: two staff share
    a tenant and both may pick up either draft (there are one to two of them).
    The boundary is `tenant_id`, and it is on every branch of this function.
    """
    qs = WizardPark.objects.filter(tenant_id=_tenant_id())
    if flow is not None:
        qs = qs.filter(flow=_clean_flow(flow))
    if mine_user_id is not None:
        qs = qs.filter(parked_by_id=mine_user_id)
    # `select_related` because `row_dict` reads the parker's name for every row
    # — without it the list is N+1 queries on a screen a clerk opens all day.
    return qs.select_related("parked_by").order_by("-parked_at", "-id")


def list_parks(*, flow: str | None = None, mine_user_id: Any = None) -> list[WizardPark]:
    """The same list, MATERIALISED — for the callers that need a real list.

    ⚠ **KEPT AS A LIST ON PURPOSE AND NOT FOLDED INTO `parks_queryset`.** Its
    remaining caller is `apps.customers.seams.wizard_park_rows`, whose own caller
    `sample_data._remove_cr035_park` **deletes rows while iterating** what it is
    handed. That is safe over a list and is the kind of thing that is safe over a
    queryset only by accident of the result cache. The fixture path is bounded by
    construction (one seeded draft), so nothing is paid for it.

    **The SCREEN does not come through here any more** — `wizard_parks_api` pages
    `parks_queryset` in SQL (`NFR-3`, DEF-SHL-5748).
    """
    return list(parks_queryset(flow=flow, mine_user_id=mine_user_id))


# ── writes ──────────────────────────────────────────────────────────────────
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def park(actor: Any, payload: Any) -> WizardPark:
    """`Park — what are you waiting for?`, for the five wizards that had nowhere.

    The PO's requirement, in their own words: *"in pratcicail life all these
    request does not close in  day, hence user genrllay park them … help them to
    work on these request as per their pace"*.

    **It writes ONE row and touches nothing else in the product** — no account,
    no occupancy, no unit status, no bill. That is BR-SHL-048 and it is the
    whole of what this function is allowed to do.
    """
    body = payload if isinstance(payload, dict) else {}
    flow = _clean_flow(body.get("flow"))
    step = _clean_step(body.get("step", 1))
    waiting_on = _clean_waiting_on(body.get("waiting_on"))
    values = _clean_json_object(body.get("values"), "values")
    subject_ref = _clean_json_object(body.get("subject_ref"), "subject_ref")

    with transaction.atomic():
        row = WizardPark.objects.create(
            tenant_id=_tenant_id(),
            flow=flow,
            subject_label=_text(body.get("subject_label"), LABEL_MAX_CHARS) or "",
            subject_ref=subject_ref,
            step=step,
            values=values,
            waiting_on=waiting_on,
            # `CR-122-BRC06` — the reference is taken INSIDE the same
            # transaction that writes the row (BR-TEN-035), so a draft never
            # exists unnumbered even for the width of a transaction.
            # ⚠ **`BR-SHL-048 (d)` (2026-09-21) — CARRIED BEFORE ALLOCATED.** A
            # wizard finishing a record that already exists copies that
            # record's own number onto `subject_ref`, and this takes it rather
            # than minting a second one beside it.
            reference=_draft_reference(flow, subject_ref),
            park_note=_text(body.get("park_note"), NOTE_MAX_CHARS),
            remind_on=_clean_remind_on(body.get("remind_on")),
            parked_by_id=_actor_id(actor),
        )
        _audit(actor, "wizard_park.parked", row.id, after=_audit_shape(row))
    return row


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def resume(actor: Any, park_id: Any) -> WizardPark:
    """Pick a draft back up — the read behind `GET /wizard-parks/{id}`.

    ⚠ **THIS READ WRITES AN AUDIT ROW, WHICH IS UNUSUAL AND IS THE POINT.** A
    parked move-in holds a person's name, email and phone before any customer
    row exists, so opening one is an access to PII that belongs to somebody who
    is not yet a customer, and CLAUDE.md rule 7 wants the who and the when. The
    cost is stated rather than hidden: **one audit row per open**, so a clerk who
    reopens a draft five times leaves five rows. That is the trade — the
    alternative is a PII read with no trail at all.

    It changes nothing on the row. `parked_at` is NOT reset, because the age is
    the thing that stops a draft sitting forever (BR-SHL-048) and an age that
    resets every time somebody looks at it measures nothing.
    """
    row = park_row(park_id)
    _audit(actor, "wizard_park.resumed", row.id, after=_audit_shape(row))
    return row


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def update_park(actor: Any, park_id: Any, payload: Any) -> WizardPark:
    """Save more of the form into an existing draft — still nothing but a draft.

    Only the five fields a clerk can change from inside the wizard move:
    `step`, `values`, `waiting_on`, `park_note`, `remind_on`. **`flow` never
    moves**, and that is deliberate — a draft that changed which flow it was
    would be a different draft wearing the same id.

    ⚠ **`subject_label` AND `subject_ref` MOVE WHILE THE ROW IS A DRAFT, AND
    FREEZE THE MOMENT IT IS PARKED (`CR-122-BRC06`).** The original rule froze
    them always, and its reason was about a PARK: *"the 'Waiting on' list would
    silently rewrite its own history."* That reason is exact and is kept where
    it applies. It does not describe a DRAFT, which is written the moment the
    wizard opens — before the clerk has reached the unit picker — and whose
    subject is being CHOSEN for the first time rather than changed. Freezing an
    empty label for the life of the draft would put a blank row on the Move-ins
    tab that could never learn which unit it was about.

    **So the boundary is the reason, not the id:** an empty `waiting_on` is a
    draft nobody has committed to a story yet, and a non-empty one is a
    statement on a queue that other people read. Park a new one instead of
    re-pointing a parked one; discarding is free (BR-SHL-048 / rule 4 — a form
    is not a financial record).

    An absent key is left alone; an explicit `null` clears the two nullable
    fields.

    ⚠ **THAT "ABSENT KEY" RULE IS WHAT MAKES AUTOSAVE SAFE, AND IT IS LOAD-
    BEARING NOW IN A WAY IT WAS NOT (`CR-122-BRC06`).** The move-in wizard
    PATCHes `{step, values}` on every change; because `waiting_on` is not in
    that body, a clerk who PARKED a draft with *waiting on a deposit* and then
    carried on typing keeps their reason. A patch helper that sent the whole
    object every time would erase it and turn a park back into a draft.

    ⚠ **THIS PARAGRAPH REPLACED A SENTENCE THAT IS NO LONGER TRUE.** It read
    *"`waiting_on` is never cleared to empty — that is `ck_wizard_parks_
    waiting_on`, and a park with no reason is a `Save & exit`"*. The check was
    DROPPED by `tenancy/0046` and an empty reason is now the DRAFT state; the
    second half of the sentence survives as the distinction itself. B19 §12.2's
    two controls are unchanged.
    """
    body = payload if isinstance(payload, dict) else {}
    with transaction.atomic():
        row = park_row(park_id, lock=True)
        before = _audit_shape(row)

        # CR-122-BRC06 — the subject follows the clerk while this is still a
        # draft, and only while it is. `row.waiting_on` is read BEFORE the
        # block below can change it, so parking and re-pointing in one request
        # cannot smuggle a new unit onto a queue row.
        was_draft = row.waiting_on == ""
        if was_draft and "subject_label" in body:
            row.subject_label = _text(body.get("subject_label"), LABEL_MAX_CHARS) or ""
        if was_draft and "subject_ref" in body:
            row.subject_ref = _clean_json_object(body["subject_ref"], "subject_ref")
        if "step" in body:
            row.step = _clean_step(body["step"])
        if "values" in body:
            row.values = _clean_json_object(body["values"], "values")
        if "waiting_on" in body:
            row.waiting_on = _clean_waiting_on(body["waiting_on"])
        if "park_note" in body:
            row.park_note = _text(body["park_note"], NOTE_MAX_CHARS)
        if "remind_on" in body:
            row.remind_on = _clean_remind_on(body["remind_on"])

        row.save()
        _audit(actor, "wizard_park.updated", row.id, before=before, after=_audit_shape(row))
    return row


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def discard(actor: Any, park_id: Any) -> None:
    """Throw the draft away. **This is a real DELETE and that is lawful.**

    CLAUDE.md rule 4 makes issued invoices, invoice lines, payments and journal
    entries immutable; a parked wizard is none of those. Nothing was posted,
    nothing was charged, no occupancy began — BR-SHL-048 is precisely the ruling
    that *"no records update"* until execution, so there is no record to
    preserve the shape of. Deleting it is also what makes an erasure request
    answerable for the PII a parked move-in holds.

    The audit row is written BEFORE the delete and survives it (`audit_log` is
    append-only, BR-AUD-002), so what was discarded, by whom and when is still
    on the record after the draft is gone.
    """
    _discard_row(actor, park_id)


def _discard_row(actor: Any, park_id: Any) -> None:
    """Audit, then delete. Shared by the clerk's `discard` and the fixture's."""
    with transaction.atomic():
        row = park_row(park_id, lock=True)
        _audit(actor, "wizard_park.discarded", row.id, before=_audit_shape(row))
        row.delete()


def discard_for_sample(park_id: Any) -> None:
    """FIXTURE ONLY — remove a seeded draft when the demo data is removed.

    ⚠ **WHY IT CANNOT JUST CALL `discard`.** `discard` is `@require_role`d, and
    correctly so: it is a clerk throwing their own typing away. The sample
    REMOVAL contract (`apps.<module>.services.remove_sample_records()`) takes
    **no actor at all** — every module's removal deletes unattributed and the
    orchestrator writes the one `sample.removed` row for the whole act — so
    there is no actor here to satisfy that guard with, and inventing one would
    put a fabricated user on an audit row.

    So this does the same two things in the same order through the same helper,
    with the actor recorded as **absent**, which `core.audit.write_row`'s own
    contract already spells *"None = system job"*. It is reachable from no
    route (a test asserts it) and its only caller is
    `apps/customers/sample_data.remove_sample_wizard_parks`.

    **The actor gap belongs to the removal contract, not to this table** —
    `remove_sample_records()` taking no actor is a gap in that contract and is
    reported rather than worked around by minting a user.
    """
    _discard_row(None, park_id)


def backdate_for_sample(park_id: Any, parked_at: Any) -> None:
    """FIXTURE ONLY — move a seeded draft's `parked_at` back so it has an AGE.

    ⚠ **WHY THIS DOOR HAS TO EXIST, AND WHY IT IS UGLY ON PURPOSE.**
    `WizardPark.parked_at` is `auto_now_add`, so a row created by the demo
    seeder is always **zero days old** — and a Waiting-on fixture with age zero
    demonstrates nothing. The AGE column is not decoration: BR-SHL-048 (c)
    accepts in writing that a parked move-out is invisible and names *"the
    remind-on date and the visible age on the 'Waiting on' list"* as the only
    thing standing between a draft and one that sits forever. A demo that cannot
    show a wait cannot show the feature.

    ⚠ **IT IS NOT REACHABLE BY ANY USER.** No route calls it —
    `wizard_parks_api.urlpatterns` mounts `park`, `resume`, `update_park` and
    `discard` and nothing else — and a test asserts that. It takes no `actor`
    for the same reason: nobody is acting, a fixture is being planted.
    `apps/customers/sample_data.py` is its only caller, through
    `apps/customers/seams.py`, because customers may not touch a tenancy table
    directly (B1 / BR-TEN-013: cross-module writes go through the OWNING
    module's own service function, and this is it).

    Tenant-scoped like everything else here: `park_row` reads under
    `app.tenant_id` with RLS `FORCE` on, so a draft in another tenant is a 404
    rather than a silent no-op.
    """
    row = park_row(park_id)
    # `auto_now_add` ignores an assigned value on save(), so this is a queryset
    # UPDATE. It touches ONE column of ONE row of `wizard_parks` — a draft of a
    # form, which CLAUDE.md hard rule 4 does not govern (see the model note).
    WizardPark.objects.filter(pk=row.pk).update(parked_at=parked_at)


def _audit_shape(row: WizardPark) -> dict[str, Any]:
    """The envelope, and ONLY the envelope — BR-AUD-006.

    `values` is a person's name, email and phone before any customer row exists;
    `subject_label` is a street address. Neither enters the payload, because
    BR-AUD-006 admits PII masked only and nothing here masks. `subject_ref` is
    internal ids and does go in — it is what makes the trail answer *which unit*
    without copying a resident's contact details into a second table.
    """
    return {
        "flow": row.flow,
        "step": row.step,
        "waiting_on": row.waiting_on,
        "remind_on": row.remind_on.isoformat() if row.remind_on else None,
        "has_note": bool(row.park_note),
        "subject_ref": row.subject_ref,
        # A COUNT, never the keys' values — enough to see a draft grow, and not
        # enough to reconstruct anybody's contact details from the audit trail.
        "values_fields": len(row.values or {}),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-035 step 6 part 2 (BR-SHL-048 + the PO ruling quoted verbatim in
#         12-governance/02-decision-log.md, 2026-08-26) · part 1's model and
#         migration docstrings are the contract this implements
# generated: 2026-08-26 by the CR-035 park-service lane (PARKSVC)
# checklist: A✔ B=deferred(the frontend half is lane PARKUI's — the port and resume are built against this contract in parallel) C✔ D✔ E=deferred(no-frontend-half in this lane) F✔ G✔ H=deferred(PO)
# gates: see apps/tenancy/wizard_parks_api.py's trailer — one run, both files
# exceptions: `waiting_on` is FREE TEXT, matching `customers.ServiceRequest`;
#         the nine reasons are what the SCREEN offers · no per-flow step count
#         is enforced (BR-SHL-046's declared step lists live in the frontend and
#         a second copy here would be free to disagree) · `resume` writes an
#         audit row on a READ — reasoned in its docstring, cost stated · `flow`
#         and `subject_ref` are immutable after park, by choice, reasoned in
#         `update_park`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
