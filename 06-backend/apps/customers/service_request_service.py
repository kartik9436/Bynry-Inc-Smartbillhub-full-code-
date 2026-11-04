# ── Trace ──────────────────────────────────────────────
# Story:    CR-031 (PO 2026-08-24, verbatim in 12-governance/11-change-requests.md)
#           B19 = 04-docs/02-decisions/19-cr031-service-request-capture.md
#           Screens: REQ-01 list · REQ-02 detail · REQ-03.1..6 capture · REQ-03.sent
# Rules:    BR-CUS-079 · BR-CUS-080 · BR-CUS-070 · B18 §4.6 (never posts to the
#           ledger) · CLAUDE.md rules 1 (tenant scoping), 2 (money 4 dp /
#           CHAR(3)), 4 (events are append-only), 6 (idempotent numbering),
#           7 (every money action audits)
#           ── PO rulings 2026-08-24, all CONFIRMED ──
#           BR-CUS-090 · BR-CUS-091 · BR-CUS-093 · BR-CUS-094 · BR-CUS-095
# Questions: OQ-355 · OQ-356 (STILL OPEN) · OQ-357 ✅ CLOSED 2026-09-23 as "both" · OQ-351 ✅ CLOSED
# Defects:  DEF-634 ✅ · DEF-635 ✅ · DEF-637 ✅ · DEF-638 12.a ✅ — all closed
#           2026-08-24 · DEF-632 ruled (BR-CUS-092) and NOT built here
# Tests:    06-backend/tests/test_cr031_service_request.py
# Impacts:  apps/customers/service_request.py (the rules) ·
#           apps/customers/service_request_reads.py (the read model)
# ───────────────────────────────────────────────────────
"""CR-031 — the service-request WRITE path. The sole writer of the five tables.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — idempotent number allocation is a
CLAUDE.md 🔒 path and the fee lines are money columns. AI-authored 2026-08-24
under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.

────────────────────────────────────────────────────────────────────────────
FIVE REFUSALS LIFTED ON 2026-08-24, AND WHAT REPLACED EACH
────────────────────────────────────────────────────────────────────────────
This file shipped that morning with nine refusals by name. Five of them were
contradictions between two things the PO had drawn; all five were put to the PO
and ruled the same day. **The rulings are the authority — none of what follows
is a lane's judgment, and none may be re-litigated in code.**

* **`allocate_number` IS CALLED, AT CREATION → BR-CUS-093.** *"At creation —
  every draft is numbered"*, chosen over numbering-at-submit and over the
  screen's own claim that the number arrives when the fee is collected. The
  reason the PO gave IS the requirement: the clerk quotes `SR-26-0048` down the
  phone while the form is half-filled. `submit` allocates NOTHING, which makes
  idempotency simpler rather than harder (consequence (e)) — see `submit`.
* **`set_customer_category` ACCEPTS SEVEN → BR-CUS-094.** *"Expand the signed
  list to seven."* What it refuses now is a LEGACY code (`government`), by name,
  and that is a different refusal with a different fix: a human re-points the
  record.
* **`fee_total_to_collect` AND `collect_fee` ARE BUILT → BR-CUS-090.** *"we
  acept it and in finance we will reconcile ; here segregation of
  responsibilitys, accept it and mark it as cash."* The two figures were both
  right: $130.00 quoted, $25.00 collected, $105.00 outstanding.
* **`decide_outcome(..., outcome="disconnect")` COMMITS → BR-CUS-091.** *"Yes
  customer can request it."*
* **The document checklist EXISTS → BR-CUS-095**, closing OQ-351.
  `set_document_requirement` / `document_requirements` below, shipping empty.

────────────────────────────────────────────────────────────────────────────
AND THE REFUSALS THAT STAND, EACH WITH THE ROW THAT WILL LIFT IT
────────────────────────────────────────────────────────────────────────────
* ✅ **`BR-CUS-092`(a) IS FINISHED — PO 2026-08-27 (the SSN) AND PO 2026-09-15
  (the date of birth and the driving licence).** 2026-09-15, verbatim: *"ensure
  user is able to inputs both these on step 1 - Date of birth and driver's
  licence on step 1"*. Clause (a) has read *"both identifiers are captured on the
  service request"* since 2026-08-24 and this is the rest of it landing — **no
  signed statement was overridden, and the PO's offer to authorise one was
  declined as unnecessary on both dates.** `ssn`, `date_of_birth` and
  `drivers_licence` are ordinary `CAPTURE_FIELDS` members;
  `service_request_reads` serves the LAST FOUR of each identifier and nothing
  else, and the date of birth in full. Clause (d)'s hold on the *"stored
  encrypted"* sentence is lifted for both identifiers.
* ⚠ **`capture_applicant_identifier` IS GONE, NOT SILENCED.** It existed to
  state that the licence had no home; it has one. Deleting a stub whose subject
  is built is the opposite of deleting a stated absence that is still true.
* `suggest_customer_matches` → **BR-CUS-089**. Its old reason — *"this schema
  carries neither the identifier nor the date of birth"* — stopped being true on
  2026-09-15 and was corrected in the same commit. What stands is that NOBODY HAS
  BUILT THE MATCHER for this surface; the evidence it needs is now there
  (`identity_match.evidence_from_service_request`), and a `strong` tier moves a
  **$150.00** deposit, so it is built deliberately by a lane that can prove it.
* ✅ `remove_fee_line` IS built — **OQ-357 closed 2026-09-23 as "both"** (the
  PO approved the step-5 layout carrying a Waive tick AND a remove icon): a
  line is REMOVED while the request is a draft, and WAIVED with a reason after.
  This bullet read *"is not built → OQ-357"* until that day.
* Nothing here issues a RECEIPT. `collect_fee` records the number the counter
  wrote; payments owns the `RCT-` series and its tables (hard rule 5).

────────────────────────────────────────────────────────────────────────────
WHAT THIS MODULE NEVER DOES
────────────────────────────────────────────────────────────────────────────
**It never decides an outcome.** `resolve_address` writes EVIDENCE;
`decide_outcome` writes a judgment a named human committed, and when that
judgment contradicts the evidence it is RECORDED (`decided_against_evidence`
plus the verdict table as it stood) rather than refused — CR-031 ruled that the
clerk decides.

**It never posts to the ledger and never issues an invoice** (B18 §4.6, hard
rules 4 and 5). Fee rows are a quote. Adding or waiving one is still a money
action and writes `audit_log` (hard rule 7).

**It never overwrites `address_as_given`** (BR-CUS-070). After submission the
field is refused outright; the resolver writes the resolved ids into their own
columns beside it.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from core import audit as core_audit
from core import crypto
from core import errors
from core import numbering as core_numbering
from core import tenancy as core_tenancy
from core.money_fields import AMOUNT_QUANTUM
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

from apps.customers import (
    applicant_messages,
    identity_match,
    models,
    notifications_seam,
    payments_seam,
    request_custom_fields,
    request_extra_messages,
    seams,
    service_request as rules,
)

SERVICE_REQUEST_SERIES = core_numbering.SERVICE_REQUEST  # `SR-{YY}-{0000}`

_SR = models.ServiceRequest
_MAX_TEXT = 2000


# ── plumbing ────────────────────────────────────────────────────────────────
def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _audit(actor: Any, action: str, request_id: Any, **kw: Any) -> None:
    """CLAUDE.md rule 7. Every write in this module lands its who/when/
    before→after row — the fee paths because they are money, the rest because a
    service request is the record of a decision somebody is accountable for."""
    core_audit.write_row(
        action=action,
        entity_type="service_request",
        entity_id=request_id,
        actor_user_id=_actor_id(actor),
        # BR-CUS-092(c) — the identifier never reaches the trail in full.
        before=_mask_audit_blob(kw.get("before")),
        after=_mask_audit_blob(kw.get("after")),
    )


def _text(value: Any, limit: int = _MAX_TEXT) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned[:limit] or None


def _refuse(code: str, message_key: str, *, br_ref: str | None = None, **params: Any) -> None:
    raise errors.BizError(code, br_ref=br_ref, message_key=message_key, params=params)


def request_row(request_id: Any, *, lock: bool = False) -> models.ServiceRequest:
    """One request, tenant-scoped. A row belonging to another tenant is a 404,
    never a 403 (HR-1 — the boundary must not confirm the row exists)."""
    qs = models.ServiceRequest.objects.filter(tenant_id=_tenant_id(), id=request_id)
    if lock:
        qs = qs.select_for_update()
    row = qs.first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _refuse_unless_editable(request: models.ServiceRequest) -> None:
    """**An edit is refused once the request is decided — `DEF-CUS-6427`.**

    `rules.EDITABLE_STATES` is the list (Draft · Submitted · Under review ·
    More info needed). A CLOSED request keeps the refusal it always had
    (`terminalNoEdit`); one past an approval — `approved`, `in_fulfilment`,
    `on_hold` — now gets its own (`approvedNoEdit`), where before it got
    nothing at all and the write went through.

    Called by every write the capture wizard makes on an existing request:
    the PATCH, the category and the services. The resolver is not one of them
    — it writes EVIDENCE, never what the applicant said — and neither are the
    documents and fees, each of which has its own rule for what may still
    move.
    """
    if rules.is_editable(request.state):
        return
    if rules.is_terminal(request.state):
        _refuse(
            errors.BIZ_STATE,
            "customers.serviceRequest.terminalNoEdit",
            br_ref="CR-031",
            state=request.state,
        )
    _refuse(
        errors.BIZ_STATE,
        "customers.serviceRequest.approvedNoEdit",
        br_ref="DEF-CUS-6427",
        state=request.state,
    )


def _event(
    request: models.ServiceRequest,
    actor: Any,
    *,
    kind: str,
    note: str | None = None,
    note_type: str | None = None,
    from_state: str | None = None,
    to_state: str | None = None,
    internal: bool = True,
) -> models.ServiceRequestEvent:
    """One APPEND-ONLY timeline row. Nothing in this module ever updates one.

    ⚠ **`internal` WAS HARDCODED `True` UNTIL 2026-09-04, WITH THE REASON
    *"there is no portal"* WRITTEN BESIDE IT — AND THERE IS ONE NOW**
    (`US-CWP-063`, `BR-CWP-078`). It stays `True` BY DEFAULT, so every existing
    caller writes exactly the row it wrote yesterday; the one caller that passes
    `False` is `note_from_portal(customer_visible=True)`, which records a note
    **the customer typed themselves** on `CWP-051`. A person cannot be hidden
    from their own sentence.

    ⚠ **THE CLERK STILL HAS NO WAY TO MARK A NOTE CUSTOMER-VISIBLE, AND THAT IS
    A DEFECT RATHER THAN A DESIGN** (`DEF-CWP-3880`). `add_note` — the History
    tab's own control, badged `Internal · never shown to the customer` — passes
    nothing here, so `BR-CWP-078`'s *"notes flagged customer-visible"* half can
    only ever be the customer's own words until somebody builds the clerk's
    side. The portal READ honours the flag today; what is missing is a writer,
    which is hard-won law 2 seen from the other end.
    """
    return models.ServiceRequestEvent.objects.create(
        tenant_id=request.tenant_id,
        request=request,
        at=timezone.now(),
        actor_id=_actor_id(actor),
        kind=kind,
        from_state=from_state,
        to_state=to_state,
        note=_text(note),
        note_type=_text(note_type, 120),
        internal=internal,
    )


# ═══════════════════════════════════════════════════════════════════════════
# NUMBERING — AT CREATION (BR-CUS-093), idempotent, audited
# ═══════════════════════════════════════════════════════════════════════════
def _allocate_number(actor: Any, request_id: Any) -> dict[str, Any]:
    """Give this request its `SR-26-0056`, once and only once.

    **IDEMPOTENT (CLAUDE.md rule 6).** A second call returns the number the
    first one allocated and consumes nothing from the series — the row is
    locked, re-read inside the transaction and short-circuited. TC-REQ-2 is
    exactly this: *"the same draft submitted twice → one number, not two"*.

    ✅ **`create_request` CALLS THIS — BR-CUS-093 (CONFIRMED, PO 2026-08-24),
    closing DEF-634.** Three statements on one screen disagreed about the moment
    a request is numbered (the header's *"when the fee is collected"*, every
    footer's *"nothing is created until you submit"*, `Collect later`'s *"the
    request is created now"*). The PO was shown all three and chose the first
    reading of the three offered: ***"At creation — every draft is numbered"***.

    **The reason the PO gave is the requirement, and it is why the number cannot
    wait for submit:** the clerk reads `SR-26-0048` out over the phone while the
    form is still half-filled. Worked, from the ruling: a clerk opens the form
    on Tuesday, the request is `SR-26-0048` from that moment, the applicant
    rings back on Thursday quoting it, the clerk finds it in `Draft` and
    finishes it.

    ⚠ **GAPS ARE NORMAL AND MUST NOT BE TREATED AS LOSS — consequence (a).** An
    abandoned draft burns its number permanently. **Nothing renumbers, backfills
    or reuses**, and no report may present a gap as a missing record. There is
    no compaction path in this module and there must not be one: the whole value
    of the ruling is that the number a clerk read out on Tuesday still finds the
    same request on Thursday.

    This stays a separately callable, role-gated door for the row that predates
    the ruling and for the retry path, and it stays idempotent for both.
    """
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        if request.request_no:
            return {"request_no": request.request_no, "allocated": False}
        issue_date = request.received_at.date() if request.received_at else seams.tenant_today()
        try:
            number = core_numbering.next_number(SERVICE_REQUEST_SERIES, issue_date)
        except core_numbering.NumberingError as exc:
            # The `service_request` series IS seeded at provisioning
            # (SERIES_CATALOG → SERIES_DEFAULTS), so a missing row is a real
            # fault. Fail loudly rather than invent a number.
            raise errors.SysError(
                errors.SYS_INTERNAL,
                message_key="customers.serviceRequest.numberingUnavailable",
                params={"series": SERVICE_REQUEST_SERIES},
            ) from exc
        request.request_no = number
        request.save(update_fields=["request_no", "updated_at"])
        _event(
            request,
            actor,
            kind=models.ServiceRequestEvent.KIND_SYSTEM,
            note=number,
            note_type="number_allocated",
        )
        _audit(actor, "service_request.numbered", request.id, after={"request_no": number})
    return {"request_no": number, "allocated": True}


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def allocate_number(actor: Any, request_id: Any) -> dict[str, Any]:
    """The role-gated door onto `_allocate_number` — see its docstring.

    ⚠ **THE BODY MOVED DOWN ONE FUNCTION ON 2026-09-04 (CR-068 wave B) AND
    NOTHING ELSE CHANGED.** `create_from_portal` numbers a request raised by
    somebody who is not signed in and never will be (`BR-CWP-027`), so it needs
    the allocation without the role check — and reaching that by calling
    `allocate_number.__wrapped__` would be a bypass hidden inside an attribute
    lookup. The split makes it a named function with a stated caller instead:
    **every path a STAFF member can reach still runs this gate**, and the one
    path that does not is the guest report, which is role-free by rule and
    narrow by construction.
    """
    return _allocate_number(actor, request_id)


# ═══════════════════════════════════════════════════════════════════════════
# CAPTURE
# ═══════════════════════════════════════════════════════════════════════════
#: What REQ-03 may set. `request_no`, `state`, `outcome*`, `decided_*`,
#: `resolution_kind` and the match columns are NOT here: each has its own
#: audited door, which is what stops a PATCH from deciding an outcome.
CAPTURE_FIELDS = frozenset(
    {
        "channel",
        "applicant_kind",
        "applicant_name",
        "applicant_email",
        "applicant_phone",
        "preferred_language",
        # ✅ BR-CUS-092(a) — ALL THREE OF IT. `ssn` opened 2026-08-27;
        # `date_of_birth` and `drivers_licence` opened 2026-09-15 on the PO's
        # ruling of that date. See IDENTIFIER_FIELDS below for what did NOT.
        "ssn",
        "date_of_birth",
        "drivers_licence",
        "co_applicant_name",
        "co_applicant_email",
        "co_applicant_phone",
        "requested_start",
        "address_as_given",
        "address_unit_as_given",
        # ⊕ `BR-CUS-1055`, PO ruling 2026-09-15 — *"How many units are on this
        # property?"*, helped by *"What the applicant says is there"* (p077).
        # A CLAIM about the property, not a count of anything on file.
        #
        # ⚠⚠ **THESE THREE ARE ACCEPTED SINCE 2026-09-22, AND THIS COMMENT
        # SAID *"Do not re-add them"* UNTIL THAT DAY.** The refusal was correct
        # under the ruling it cited and the PO has ruled the other way since,
        # so the whole chain is written out here rather than left to be
        # inferred.
        #
        # **WHAT IT SAID, AND IT WAS RIGHT AT THE TIME:** they were added on
        # 2026-09-15 and taken out the same hour, before anything was pushed,
        # because the PO ruled *"if we have unit or street address then we
        # should take it from premises/Unit - it means its a search and if not
        # foudn them alow user to add them"*. Capture is a SEARCH of the
        # premises register; the town, state and postcode are the matched
        # premises' facts, walked to — `CLAUDE.md` hard rule 8. `BR-CUS-1055`
        # records that near-miss.
        #
        # **WHAT REVERSED IT — PO ruling 2026-09-22, verbatim:** *"correct
        # address will be on presmies but first time you will ahve to take the
        # details to match it"*. Said in answer to this lane's predecessor
        # refusing to capture the parts at all. **The rule was quoted correctly
        # and applied to the wrong act**: `BR-MET-1161` governs where an
        # address is STORED as the truth and says nothing about what a clerk
        # may TYPE, and a request that cannot take a city and a ZIP cannot find
        # the premises it is about.
        #
        # ⚠ **SO `BR-MET-1161` IS NOT NARROWED AND NO FOURTH HOME IS CREATED.**
        # Every one of these is WHAT THE APPLICANT SAID — `_as_given`, the same
        # posture as `address_as_given` and as
        # `interruptions.location_text` — and once `premises_id` is set the
        # PREMISES is what every screen shows. `service_request_reads.
        # resolved_place` is still where a matched request's locality comes
        # from, and nothing downstream reads these as the service address.
        "address_city_as_given",
        "address_state_as_given",
        "address_postal_code_as_given",
        "units_on_property",
        "billing_address_same",
        "billing_address_as_given",
        # ✅ **WHERE THE BILL GOES, IN PARTS — `DEF-CUS-6408`, PO report
        # 2026-09-23** (*"it should full address line, unit, city, zip it
        # shoould be match how address taken in USA ;do'nt make it
        # mandatory"*). Hard rule 8's FIRST named exception, held on the
        # request until an account exists to carry it; see the model. None is
        # required and none is format-checked here: what the applicant said is
        # kept as said (`BR-CUS-070`), and the capture screen checks a ZIP's
        # shape before it is sent. `billing_address_as_given` stays accepted
        # so a caller holding the old one-box value can still send it, and the
        # capture wizard no longer does.
        "billing_line1_as_given",
        "billing_line2_as_given",
        "billing_city_as_given",
        "billing_state_as_given",
        "billing_postal_code_as_given",
        "plot_or_parcel",
        "what_is_being_built",
        "property_type",
        "what_they_said",
        # ⊕ CR-072, 2026-09-04 — what sort of problem, on a request that is a
        # REPORT. A clerk taking one over the counter sets it through the same
        # door as the portal does; the vocabulary is metering's and is checked
        # below rather than copied here.
        "problem_kind",
        "eligibility_claimed",
        "eligibility_note",
        "fee_timing",
        "fee_due_by",
        "fee_method",
        # ⊕ **THE PICK — CR-094 capture lane E, PO ruling 2026-09-15.** Verbatim:
        # *"if we have unit or street address then we should take it from
        # premises/Unit - it means its a search and if not foudn them alow user
        # to add them"*. Step 3 stopped being five typed boxes; the clerk
        # SEARCHES the register and picks. See `PICK_FIELDS` below — neither of
        # these is a column, and that is deliberate.
        "picked_premises_id",
        "picked_unit_id",
        # ⊕ **LANE CF-1 (2026-10-18) — THE SHARED CUSTOMER FORM, AND EVERY VALUE
        # IT ASKS IS KEPT.** Decision log *"2026-10-18 — CUSTOMER DATA AND UI
        # CONSISTENT ACROSS THE CREATE SCREENS"*: every create screen uses
        # Move-in's pieces and *"saves everything it asks"*.
        #   · `tax_id` — `DEF-CUS-10223`: the staff request DREW a business Tax
        #     ID / EIN box and never sent it (`TAX_ID_CAPTURE_ACCEPTED=false`).
        #     A business's only (BR-CUS-1022 — refused on a person, by name).
        #   · `gov_id_last4`, `contact_by` — Move-in's Identity and Who fields.
        #   · `co_applicants` — the full co-applicant cards (Move-in's co-owner
        #     card), validated by `move_in_people`'s own card rules.
        #   · `mailing_*` — WHERE THE BILL GOES, under the name every other
        #     screen uses. `billing_*` stays accepted for a caller still holding
        #     the old spelling; `customers/0087` copied every stored value.
        #   · `paperless`, `sms_reminders` — the request's Preferences (no
        #     autopay: it needs a saved payment method, PO 2026-10-18).
        "tax_id",
        "gov_id_last4",
        "contact_by",
        "co_applicants",
        "mailing_same",
        "mailing_line1",
        "mailing_line2",
        "mailing_city",
        "mailing_state",
        "mailing_postal_code",
        "paperless",
        "sms_reminders",
    }
)

#: The two names a PICK arrives under, and **neither is a column on this table.**
#:
#: ⚠ **THE MATCH COLUMNS STAY OUT OF `CAPTURE_FIELDS`, WHICH IS WHY THESE TWO
#: ARE IN IT.** The note above that set says `resolution_kind` and the match
#: columns each have their own audited door, *"which is what stops a PATCH from
#: deciding an outcome"* — and that reasoning survives the ruling intact. A
#: caller naming `resolution_kind` is still refused as an unknown field. What a
#: caller may now do is name a ROW IN THE REGISTER, and `_clean_capture` reads
#: that row and works out the evidence itself. The clerk picks the address; the
#: server still decides what the address MEANS.
#:
#: ⚠ **THEY ARE NOT IN `PORTAL_CAPTURE_FIELDS` AND MUST NOT BE.** A guest on
#: the public form is refused by name, exactly as they are for a fee column:
#: picking off the premises register is a clerk's act at a counter, and a
#: stranger who could name any premises id could attach their application to
#: somebody else's building.
PICK_FIELDS = frozenset({"picked_premises_id", "picked_unit_id"})

#: Lane CF-1 — each mailing field and the older column it is mirrored into.
MAILING_TO_BILLING: tuple[tuple[str, str], ...] = (
    ("mailing_same", "billing_address_same"),
    ("mailing_line1", "billing_line1_as_given"),
    ("mailing_line2", "billing_line2_as_given"),
    ("mailing_city", "billing_city_as_given"),
    ("mailing_state", "billing_state_as_given"),
    ("mailing_postal_code", "billing_postal_code_as_given"),
)


# ⚠ **`_clean_unit_count` WAS DEFINED TWICE IN THIS FILE UNTIL 2026-09-15, AND
# THE SECOND COPY (the one Python actually bound) IS THE ONE LEFT BELOW.** Two
# lanes added the identical function on the same day — `b87b9655` (the address
# is picked from the premises register) and `e4092d3e` (name the matched
# premises and unit) — and the bodies were byte-identical apart from trailing
# blank lines, so deleting the first is provably a no-op. `G119` was red on it,
# naming this file, which is how a red on somebody else's work acquires the
# colouring of yours: filed as `DEF-CUS-5408` against the two commits that
# caused it. Python binds the LAST definition silently, and the day the two
# copies stop agreeing is the day a clerk's unit count is validated by whichever
# one happened to be pasted second.
def _clean_unit_count(value: Any) -> int | None:
    """`How many units are on this property?` — a whole number of units, or none.

    ⚠ **NO MAXIMUM, BY RULE.** `NFR-5` forbids a hard cap anywhere in this
    product and `CLAUDE.md`'s flexibility clause makes that load-bearing rather
    than tidy, so nothing here asks how big a building is allowed to be.

    ⚠ **AND NO GUESS AT THE OTHER END EITHER.** A negative count is refused
    because it cannot be a number of units; **zero is ACCEPTED**, because vacant
    land with a connection request on it genuinely has none, and refusing it
    would make a clerk type `1` about a field with no building on it.

    ⚠ **NO NEW LOCALE KEY WAS MINTED, DELIBERATELY, AND THE REUSE IS REPORTED
    RATHER THAN HIDDEN.** `G15` requires all ELEVEN catalogues to carry every
    English key with a real translation in that language's own vocabulary
    (B14 rule 35), so one new backend refusal obliges eleven frontend files from
    a backend lane while two sibling lanes are live in those same files — the
    reasoning the `CR-023` P3/P4 lane recorded in the decision log of
    2026-08-21 and the collision `CLAUDE.md` law 11 exists to prevent.
    `customers.plan.wholeNumber` — *"This must be a whole number."* — is in this
    module, is already translated eleven times, takes no parameters, and says
    exactly the true thing about both `"six"` and `-3`.
    """
    if value is None or value == "":
        return None
    try:
        count = int(str(value).strip())
    except (TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.plan.wholeNumber",
            params={"field": "units_on_property", "value": str(value)},
        ) from None
    if count < 0:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.plan.wholeNumber",
            params={"field": "units_on_property", "value": str(value)},
        )
    return count
#: Every field name a caller might reasonably send for the applicant's
#: government identifier. Each is REFUSED BY NAME rather than silently dropped
#: — a silently dropped identifier is a screen that says *"stored encrypted"*
#: over a field that went nowhere, which is DEF-632 wearing a different hat.
#:
#: ✅ **`ssn` CAME OUT OF THIS SET ON 2026-08-27 AND NOTHING ELSE DID —
#: BR-CUS-092(a)/(b), PO ruling closing DEF-632.** PO verbatim: *"We need to
#: capture SSN and encript it; we have to ensure it is working"*. It is now in
#: `CAPTURE_FIELDS` above and lands in `ServiceRequest.ssn`, a
#: `core.crypto.EncryptedTextField` — AES-256-GCM, a fresh 96-bit nonce per
#: write, AAD `service_requests.ssn` binding the ciphertext to its column.
#:
#: ⚠ **THE OTHER THIRTEEN STAY REFUSED, DELIBERATELY.** The PO ruled on the
#: Social Security number, not on identifiers in general, and the widening is
#: exactly the size of what was built and proved. `gov_id`, `gov_id_number`,
#: `id_number`, `national_id`, `ein`, `tin`, `gov_id_last4`, `ssn_last4`,
#: `date_of_birth`, `dob` and `acting_for` each still answer `BIZ_STATE`.
#: `social_security_number` stays refused too — there is ONE canonical name for
#: this field and an alias that silently works is how two payload shapes start.
#:
#: ⚠ **`ssn_last4` IS NOT UNBLOCKED AND MUST NOT BE.** There is no `ssn_last4`
#: COLUMN: the last four is a READ projection computed by
#: `service_request_reads` with `crypto.last_four()`. Accepting a caller-supplied
#: last-four would store four digits of the identifier in the clear beside the
#: ciphertext and make BR-CUS-092(c) false while every test still passed.
#:
#: ⊕ **`gov_id_last4` LEFT THIS SET ON 2026-10-18 (lane CF-1), AND NOTHING ELSE
#: DID.** The decision log of that date has every create screen ask Move-in's
#: customer form and *"save everything it asks"*, and the staff request's
#: drawing (customer-forms set, image 03) asks Move-in's *Government ID*. That
#: field has only ever been kept as its LAST FOUR — BR-CUS-045, exactly as
#: `contacts.gov_id_last4` holds it — and no full government ID is stored
#: anywhere, so there is no ciphertext for four clear digits to sit beside:
#: the objection to `ssn_last4` above does not reach it. The rest stay refused.
IDENTIFIER_FIELDS = frozenset(
    {
        "social_security_number",
        "gov_id",
        "gov_id_number",
        "id_number",
        "national_id",
        "ein",
        "tin",
        "ssn_last4",
        "drivers_licence_last4",
        "acting_for",
    }
)


#: A name that means a field this table now HAS, spelled a way this table does
#: not use. Refused BY NAME, with the canonical spelling in the refusal.
#:
#: ⚠ **THIS SET EXISTS BECAUSE THE REFUSAL ABOVE BECAME A LIE ON 2026-09-15.**
#: `dob` used to answer *"that identifier cannot be stored here"*, which was
#: true. The date of birth IS stored here now, so the same sentence over the
#: same field would send a clerk away from a field that works. A refusal that is
#: no longer true is worse than no refusal, because somebody believes it.
#:
#: ⚠ **AND THE LICENCE HAS TWO SPELLINGS IN THIS PRODUCT, WHICH IS A HAZARD
#: RATHER THAN A CHOICE.** `service_requests.drivers_licence` is what the PO
#: ruling of 2026-09-15 and `BR-CUS-092`'s amendment both name;
#: `customers.driving_licence` shipped in `customers 0036` on 2026-08-31.
#: Renaming either moves every citation in every register, docstring and test at
#: once, so neither is renamed and BOTH are answered: a caller that guesses the
#: other spelling is told which one this table uses, instead of being told the
#: field does not exist.
#:
#: `social_security_number` is deliberately NOT here. It stays in
#: `IDENTIFIER_FIELDS` with the sentence it has carried since 2026-08-27,
#: because moving it would change the refusal code on a shipped path for no
#: reason a caller would notice.
ALIASED_FIELDS: dict[str, str] = {
    "dob": "date_of_birth",
    "date_of_birth_iso": "date_of_birth",
    "driving_licence": "drivers_licence",
    "drivers_license": "drivers_licence",
    "driving_license": "drivers_licence",
    "dl": "drivers_licence",
}


#: What `_audit` replaces with a mask before a value reaches `audit_log`.
#: BR-CUS-092(c), verbatim: *"the full value is never in a list response, an
#: export, a log line or an audit `details` blob"*.
#:
#: ⚠ **THE MASKING LIVES IN `_audit`, NOT AT THE CALL SITES, AND THAT IS THE
#: WHOLE POINT.** `update_request` builds `before` with
#: `getattr(request, "ssn")` — which is the DECRYPTED attribute, because that is
#: what an `EncryptedTextField` hands back — and `after` from the cleaned
#: payload. Both were cleartext. Masking at each call site would work until the
#: next caller in this module forgot, and a forgotten one is invisible: the row
#: writes, nothing raises, and the number sits in `audit_log` forever. Masking
#: at the boundary means a new writer gets it for free.
#:
#: ⚠ **`drivers_licence` JOINED IT ON 2026-09-15 IN THE SAME COMMIT AS THE
#: COLUMN.** Adding an encrypted identifier and adding it to this set are two
#: acts, and only the first one feels like the work — an identifier left off this
#: set writes to `audit_log` in full, nothing raises, and the number sits there
#: forever. `tests/test_br_cus_092_licence_and_dob_capture.py` asserts the set
#: covers every `EncryptedTextField` on the model, so the next one cannot be
#: forgotten quietly.
#:
#: `date_of_birth` is deliberately NOT masked: `BR-CUS-092` names two government
#: identifiers and a date of birth is neither (`BR-CUS-1020`, in as many words).
#: It is served in full on the detail payload, so masking it in the one record
#: that answers *"what was the old value"* would protect nothing.
AUDIT_MASKED_FIELDS = frozenset({"ssn", "drivers_licence", "tax_id"})

#: Lane CF-1 — a co-applicant card's two identifiers, held as ciphertext in
#: `co_applicants` and never written to `audit_log` in any form.
CO_APPLICANT_SECRET_FIELDS = ("ssn", "driving_licence")


def _mask_audit_blob(blob: Any) -> Any:
    """Replace every sensitive value in an audit `before`/`after` with its mask.

    `'123456789'` becomes `'•••••6789'` — enough for a reviewer to tell one
    identifier from another, never enough to be the identifier. A co-applicant
    card's SSN and licence are replaced by a bare mask: the row holds
    ciphertext, and not even that reaches the audit blob.
    """
    if not isinstance(blob, dict):
        return blob
    masked = dict(blob)
    for field in AUDIT_MASKED_FIELDS & set(masked):
        value = masked[field]
        masked[field] = crypto.mask(value) if isinstance(value, str) else value
    if isinstance(masked.get("co_applicants"), list):
        masked["co_applicants"] = [
            {
                key: ("••••" if key in CO_APPLICANT_SECRET_FIELDS and value else value)
                for key, value in row.items()
            }
            if isinstance(row, dict)
            else row
            for row in masked["co_applicants"]
        ]
    return masked


def _clean_tax_id(value: Any) -> str | None:
    """`DEF-CUS-10223` — a business applicant's Tax ID / EIN, stored as typed.

    The one refusal is `_clean_ssn`'s and for its reason: every read projects
    the LAST FOUR (BR-CUS-092(c)), so fewer than four alphanumerics could not
    render what the rule requires. No EIN shape is invented here. The refusal
    carries no part of the value.
    """
    text = _text(value)
    if text is None:
        return None
    if len(crypto.normalise_identifier(text)) < 4:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.ssnTooShort",
            params={"field": "tax_id"},
        )
    return text


def _clean_gov_id_last4(value: Any) -> str | None:
    """Move-in's *Government ID* — the LAST FOUR alphanumerics and nothing
    else (BR-CUS-045, as `contacts.gov_id_last4` keeps it). A longer value is
    cut to its last four here, so a full number is never stored."""
    text = _text(value)
    if text is None:
        return None
    cleaned = crypto.normalise_identifier(text)
    return cleaned[-4:] if cleaned else None


def _clean_contact_by(value: Any) -> str | None:
    """Move-in's *Contact by* — `models.CONTACT_BY`, one vocabulary for the
    holder, a co-owner and a contact person (§9.1)."""
    text = _text(value)
    if text is None:
        return None
    if text not in models.CONTACT_BY:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.moveIn.people.choiceUnknown",
            params={"field": "contact_by"},
        )
    return text


def _clean_co_applicants(value: Any) -> dict[str, Any]:
    """The full co-applicant cards, by Move-in's own card rules.

    Each card is validated by `move_in_people._clean_person` — the move-in's
    co-owner validator, so a card a request accepts is a card the move-in it
    leads to accepts — and an OFFICER's fields are refused by name (an
    applicant's co-applicant is a co-owner, never an officer). The SSN and the
    licence are ENCRYPTED into the row (`core.crypto`, one context each); the
    date of birth is stored as ISO. The three `co_applicant_*` columns are
    mirrored from the FIRST card so every reader of them keeps working.
    """
    from apps.customers import move_in_people

    if value in (None, ""):
        rows: list[Any] = []
    elif isinstance(value, list):
        rows = value
    else:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.account.unknown_field",
            params={"field": "co_applicants"},
        )
    fe: list[dict[str, Any]] = []
    stored: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        at = f"co_applicants[{index}]"
        cleaned = move_in_people._clean_person(row, at, fe)
        if cleaned is None:
            continue
        for name in sorted(cleaned["_sent"] & move_in_people.OFFICER_ONLY):
            fe.append(
                {
                    "field": f"{at}.{name}",
                    "code": errors.VAL_FORMAT,
                    "message_key": "customers.account.unknown_field",
                    "params": {},
                }
            )
        dob = cleaned.get("date_of_birth")
        stored.append(
            identity_match.seal_co_applicant(
                {
                    "full_name": cleaned["full_name"],
                    "relationship": cleaned.get("relationship"),
                    "phone": cleaned.get("phone"),
                    "email": cleaned.get("email"),
                    "contact_by": cleaned.get("contact_by"),
                    "date_of_birth": dob.isoformat() if dob else None,
                    "responsible_for_bills": bool(cleaned.get("responsible_for_bills")),
                    "ssn": cleaned.get("ssn"),
                    "driving_licence": cleaned.get("driving_licence"),
                }
            )
        )
    if fe:
        raise errors.ValidationError(
            fe[0]["code"],
            message_key=fe[0]["message_key"],
            params=fe[0]["params"],
            field_errors=fe,
        )
    first = stored[0] if stored else {}
    return {
        "co_applicants": stored,
        "co_applicant_name": first.get("full_name"),
        "co_applicant_email": first.get("email"),
        "co_applicant_phone": first.get("phone"),
    }


def _keep_stored_secrets(rows: list[dict[str, Any]], stored: Any) -> list[dict[str, Any]]:
    """A re-sent card with no SSN / licence keeps the stored ciphertext of the
    card of the same name (see `update_request`)."""
    old = {
        str(row.get("full_name") or "").strip().lower(): row
        for row in (stored if isinstance(stored, list) else [])
        if isinstance(row, dict)
    }
    out = []
    for row in rows:
        previous = old.get(str(row.get("full_name") or "").strip().lower())
        if previous is not None:
            row = dict(row)
            for key in CO_APPLICANT_SECRET_FIELDS:
                if not row.get(key) and previous.get(key):
                    row[key] = previous[key]
        out.append(row)
    return out


def co_applicant_rows(request: Any, *, decrypt: bool = False) -> list[dict[str, Any]]:
    """The request's co-applicant cards — for a READ (last four of each
    identifier, never the value) or, with `decrypt=True`, for the ONE server
    path that carries them into the move-in or new connect's co-owners.

    A request written before lane CF-1 holds only the three `co_applicant_*`
    columns; it is read as ONE card so the person is never lost.
    """
    raw = request.co_applicants if isinstance(getattr(request, "co_applicants", None), list) else []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict) or not row.get("full_name"):
            continue
        opened = identity_match.open_co_applicant(row)
        ssn = opened.get("ssn")
        licence = opened.get("driving_licence")
        card = {
            key: row.get(key)
            for key in (
                "full_name",
                "relationship",
                "phone",
                "email",
                "contact_by",
                "date_of_birth",
                "responsible_for_bills",
            )
        }
        if decrypt:
            card["ssn"] = ssn
            card["driving_licence"] = licence
        else:
            card["ssn_last4"] = crypto.last_four(ssn)
            card["driving_licence_last4"] = crypto.last_four(licence)
        out.append(card)
    if not out and getattr(request, "co_applicant_name", None):
        out.append(
            {
                "full_name": request.co_applicant_name,
                "relationship": None,
                "phone": request.co_applicant_phone,
                "email": request.co_applicant_email,
                "contact_by": None,
                "date_of_birth": None,
                "responsible_for_bills": False,
                **({"ssn": None, "driving_licence": None} if decrypt else {"ssn_last4": None, "driving_licence_last4": None}),
            }
        )
    return out


def _clean_ssn(value: Any) -> str | None:
    """Validate and normalise the applicant's Social Security number.

    **What is stored is EXACTLY WHAT THE APPLICANT TYPED** — `crypto`'s own
    normalisation applies to a blind index, never to the ciphertext, and this
    column has no index. `123-45-6789` stays `123-45-6789`.

    ⚠ **NO FORMAT RULE IS INVENTED HERE, AND THE ONE CHECK THAT EXISTS IS
    DERIVED RATHER THAN CHOSEN.** Nothing signed says a Social Security number
    must be nine digits in this product, and asserting it would refuse an ITIN
    and every applicant a non-US deployment might have. So the only refusal is
    the one BR-CUS-092(c) forces: the sole read projection this product offers
    is **the last four**, so a value with fewer than four alphanumerics cannot
    render the thing the rule requires and would be stored to be shown as
    something else. Whether a stricter check is wanted is **OQ-781** — open,
    non-blocking, and NOT resolved here by picking a length.

    ⚠ **THE REFUSAL CARRIES NO PART OF THE VALUE.** Every neighbouring validator
    in this file answers `params={"value": str(...)}`; this one may not, because
    an error message is rendered, logged and frequently pasted into a ticket.
    """
    text = _text(value)
    if text is None:
        return None
    if len(crypto.normalise_identifier(text)) < 4:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.ssnTooShort",
            # NO `value` param. See the docstring.
            params={"field": "ssn"},
        )
    return text


def _clean_drivers_licence(value: Any) -> str | None:
    """Validate and normalise the applicant's driving licence number.

    🔒 SENSITIVE PATH. **`_clean_ssn` is this function's model and the two are
    deliberately the same shape**, because the promise BR-CUS-092(c) makes about
    them is the same promise.

    **What is stored is EXACTLY WHAT THE APPLICANT TYPED.** `crypto`'s
    normalisation applies to the BLIND INDEX and never to the ciphertext, so
    `TX-1234882` stays `TX-1234882` while `TX1234882` typed on Thursday still
    matches it — `crypto.normalise_identifier` strips punctuation and upper-cases
    for the index alone.

    ⚠ **NO FORMAT RULE IS INVENTED HERE, AND THE ONE CHECK THAT EXISTS IS
    DERIVED RATHER THAN CHOSEN.** A driving licence number is a different length
    and a different alphabet in each of the fifty states, so any length or
    pattern this lane picked would refuse a real applicant somewhere in order to
    catch a hypothetical typo. The only refusal is the one BR-CUS-092(c) forces:
    the sole read projection this product offers is **the last four**, so a value
    with fewer than four alphanumerics cannot render the thing the rule requires
    and would be stored to be shown as something else. This is `_clean_ssn`'s
    reasoning applied to a second column, not a second rule; whether a stricter
    check is wanted for the SSN is `OQ-781`, open, and the same answer will apply
    here when it arrives.

    ⚠ **THE REFUSAL CARRIES NO PART OF THE VALUE.** Every neighbouring validator
    in this file answers `params={"value": str(...)}`; this one may not, because
    an error message is rendered, logged and frequently pasted into a ticket.
    """
    text = _text(value)
    if text is None:
        return None
    if len(crypto.normalise_identifier(text)) < 4:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.driversLicenceTooShort",
            # NO `value` param. See the docstring.
            params={"field": "drivers_licence"},
        )
    return text


def _clean_date_of_birth(value: Any) -> date | None:
    """The applicant's date of birth — a plain, comparable date.

    `BR-CUS-1020` settled the type and the reason: *"it must be COMPARABLE,
    `contacts.dob` is a plain date too, and `BR-CUS-092` names two identifiers of
    which it is not one."* It is the MIDDLE CLAUSE of `BR-CUS-089`'s
    *name + date of birth + one government ID*, so a string that the matcher
    cannot compare is worth nothing at all.

    ⚠ **NO PLAUSIBILITY RULE IS INVENTED HERE, AND THE ABSENCE IS DELIBERATE
    RATHER THAN AN OVERSIGHT.** A future date, an implausibly old one and an age
    below eighteen are each refusable and none of them is ruled.
    `customers.date_of_birth` — the column this one will be compared against —
    has carried no such check since `customers 0036`, so adding one HERE alone
    would mean the same date could be captured at the counter and refused on the
    request, or the reverse, with nothing saying which surface was right. If a
    check is wanted it belongs on both columns at once and it belongs to somebody
    who has ruled it.
    """
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.serviceRequest.dateOfBirthInvalid",
            params={"field": "date_of_birth"},
        ) from None


#: What each kind of applicant may be asked for on this form — `BR-CUS-1022`,
#: PO ruling 2026-09-01, verbatim: *"Customer can be person or company - in case
#: of person , if we have SSN, or DL or Phone number, we create the Customer ID
#: and attached these to custoemr ID ; if it is Company then we ask for Tax ID"*.
#:
#: ⚠ **THE RULE'S OWN WORDS ARE WHY THIS IS A REFUSAL AND NOT A DROP:** *"a
#: company is never asked for a driving licence and a person is never asked for a
#: Tax ID, refused BY NAME rather than dropped, because asking for both and
#: leaving one blank turns a rule into a habit and the blank field eventually
#: gets filled with something."*
#:
#: ⚠ **THIS GATES ONLY THE TWO FIELDS THE RULING OF 2026-09-15 PUT ON STEP 1.**
#: `ssn` is NOT gated here and a business request may still carry one, which is
#: `BR-CUS-1022` unapplied to a path that shipped four days before the rule was
#: ruled. Narrowing a shipped capture path is a different change with its own
#: blast radius — existing draft rows, the portal door, the SSN proof suite — so
#: it is FILED as **`DEF-CUS-5409`** rather than done in passing. A finding
#: written only in the file you happen to be in is a finding nobody can count
#: (CLAUDE.md hard rule 4), which is why it has a row and not a paragraph.
#:
#: ⚠ **THE SPELLING GAP IS REAL AND IS STATED RATHER THAN SMOOTHED.**
#: `service_requests.applicant_kind` is `person | business`;
#: `customers.kind` is `person | company`. `identity_match.normalise_kind`
#: returns `business` unchanged, so a business request can never reach a STRONG
#: tier — which is the safe direction and is `identity_match`'s own documented
#: position, not a bug introduced here.
KIND_FORBIDDEN_FIELDS: dict[str, tuple[str, ...]] = {
    _SR.APPLICANT_BUSINESS: ("date_of_birth", "drivers_licence"),
    # Lane CF-1 — BR-CUS-1022: a person is never asked for a Tax ID, so one
    # sent for a person is refused by name rather than stored where nothing
    # would ever read it.
    _SR.APPLICANT_PERSON: ("tax_id",),
}


def _refuse_fields_for_kind(kind: Any, present: set[str]) -> None:
    """Refuse, BY NAME, a field this kind of applicant is not asked for.

    Called twice and with one table: from `_clean_capture`, where the kind comes
    from the payload or falls to the column default, and from `update_request`,
    where **the kind on the ROW decides** — which is `customer_edit._validate`'s
    posture and it is the right one, because a PATCH that sets only a licence
    says nothing about who the applicant is.

    An unstated kind is `person`, which is the column's own default
    (`ServiceRequest.applicant_kind`) and therefore what the row will actually
    hold. Guessing is not involved: the alternative is refusing every request the
    capture screen sends today, because `CR-033` removed the control and the
    field has not been sent since 2026-08-27.
    """
    forbidden = KIND_FORBIDDEN_FIELDS.get(
        str(kind or _SR.APPLICANT_PERSON), KIND_FORBIDDEN_FIELDS[_SR.APPLICANT_PERSON]
    )
    clash = sorted(present & set(forbidden))
    if clash:
        _refuse(
            errors.BIZ_STATE,
            "customers.serviceRequest.notAskedOfThisApplicant",
            br_ref="BR-CUS-1022",
            field=clash[0],
            applicant_kind=str(kind or _SR.APPLICANT_PERSON),
        )


def _storable_problem_kinds() -> tuple[str, ...]:
    """The report kinds a row may carry — `metering`'s list, read and never
    copied (`CR-072`).

    ⚠ **THE VOCABULARY DID NOT MOVE WHEN THE RECORD DID.** `CR-072` makes the
    REPORT a service request; the CONFIRMED INTERRUPTION stays `metering`'s
    (B2 §2), and the six kinds describe the network fact rather than the
    paperwork. Two spellings of one list is how they drift, so this reads
    theirs.

    ⚠ **`gas_smell` IS NOT IN IT AND MUST NOT BE.** It is offered by the form
    and routed to a phone number; `US-CWP-007` TC-3 asserts that the call
    creates NOTHING, and a request row carrying it would be exactly the queue
    that test exists to keep it off.

    The import is LOCAL: `apps.metering.models` imports `interruptions` at its
    own foot to register the model, and a module-level import here would tie
    `customers`' import order to that.
    """
    from apps.metering import interruptions as interruption_models

    return interruption_models.STORABLE_KINDS


def _clean_capture(
    data: dict[str, Any], *, partial: bool, require_address: bool = True
) -> dict[str, Any]:
    """⚠ **`require_address` IS THE DRAFT MINIMUM, AND IT DEFAULTS TO THE OLD
    BEHAVIOUR ON PURPOSE** — PO ratification 2026-09-20 (decision log, *"SEVEN
    PO RATIFICATIONS FROM ONE SITTING"*, §3; `DEF-CUS-6006`). PO, verbatim:
    *"this is correct"* on the gate table.

    Only `create_request` passes `False`. `create_from_portal` goes STRAIGHT to
    `submitted` in the same transaction — its own comment: *"a guest has no
    draft to come back to"* — so for that door create-time IS submit-time and
    the SUBMIT minimum is the one that applies. A flag that defaulted the other
    way would have taken the address off the public form silently.
    """
    present = set(data) & IDENTIFIER_FIELDS
    if present:
        _refuse(
            errors.BIZ_STATE,
            "customers.serviceRequest.identifierNotStorable",
            br_ref="DEF-632",
            field=sorted(present)[0],
        )
    # ⚠ **BEFORE the `unknown` branch, because these names are NOT unknown.**
    # Each one means a column this table has, spelled a way this table does not
    # use, and answering *"field not accepted"* would send a caller looking for a
    # field that is right there. The refusal names the canonical spelling.
    aliased = sorted(set(data) & set(ALIASED_FIELDS))
    if aliased:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.useCanonicalFieldName",
            params={"field": aliased[0], "canonical": ALIASED_FIELDS[aliased[0]]},
        )
    unknown = set(data) - CAPTURE_FIELDS
    if unknown:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.fieldNotAccepted",
            params={"field": sorted(unknown)[0]},
        )
    # The pick is lifted out BEFORE the text loop below: `picked_premises_id` is
    # an id to look up, not a string to store, and there is no column of that
    # name to store it in. `_resolution_from_pick` turns it into the four
    # resolution columns at the foot of this function.
    picks = {key: data.pop(key) for key in sorted(PICK_FIELDS) if key in data}
    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        if key == "ssn":
            cleaned[key] = _clean_ssn(value)
        elif key == "drivers_licence":
            cleaned[key] = _clean_drivers_licence(value)
        elif key == "date_of_birth":
            cleaned[key] = _clean_date_of_birth(value)
        elif key == "units_on_property":
            cleaned[key] = _clean_unit_count(value)
        elif key in (
            "billing_address_same",
            "eligibility_claimed",
            "mailing_same",
            "paperless",
            "sms_reminders",
        ):
            cleaned[key] = bool(value)
        elif key == "tax_id":
            cleaned[key] = _clean_tax_id(value)
        elif key == "gov_id_last4":
            cleaned[key] = _clean_gov_id_last4(value)
        elif key == "contact_by":
            cleaned[key] = _clean_contact_by(value)
        elif key == "co_applicants":
            cleaned.update(_clean_co_applicants(value))
        elif key in ("requested_start", "fee_due_by"):
            cleaned[key] = value if isinstance(value, date) or value is None else value
        else:
            cleaned[key] = _text(value)
    # Lane CF-1 — the MAILING address is the one name for where the bill goes;
    # the `billing_*` columns are written alongside it so every reader that
    # predates the rename keeps reading the same answer (`customers/0087`
    # copied the stored values the other way).
    # A caller still sending the old spelling is written into the new one, so
    # the two never disagree whichever name arrives.
    for new, old in MAILING_TO_BILLING:
        if new in cleaned:
            cleaned[old] = cleaned[new]
        elif old in cleaned:
            cleaned[new] = cleaned[old]
    kind = cleaned.get("applicant_kind")
    if kind is not None and kind not in _SR.APPLICANT_KINDS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.applicantKindUnknown",
            params={"value": str(kind)},
        )
    # BR-CUS-1022 — a company has no date of birth and is never asked for a
    # driving licence. On a PARTIAL update the kind may not be in the payload at
    # all, so `update_request` runs the same gate again against the ROW's kind;
    # this call catches a create, and an update that states the kind itself.
    _refuse_fields_for_kind(
        kind, {key for key, value in cleaned.items() if value not in (None, "")}
    )
    prop = cleaned.get("property_type")
    if prop is not None and prop not in _SR.PROPERTY_TYPES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.propertyTypeUnknown",
            params={"value": str(prop)},
        )
    problem = cleaned.get("problem_kind")
    if problem is not None and problem not in _storable_problem_kinds():
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.problemKindUnknown",
            params={"value": str(problem)},
        )
    timing = cleaned.get("fee_timing")
    if timing is not None and timing not in _SR.FEE_TIMINGS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.feeTimingUnknown",
            params={"value": str(timing)},
        )
    if not partial:
        # ⚠ **WHICH FIELDS ARE REQUIRED DEPENDS ON WHO RAISED IT — BR-CUS-091
        # (PO 2026-08-24, *"Yes customer can request it"*).** The rule's own
        # consequence clause: *"a request may now ORIGINATE from STAFF
        # (collections) rather than an applicant, so `channel` must distinguish
        # them and applicant-identity fields are not required on a staff-raised
        # disconnect."* Collections raising a disconnect on `500 Main` is not
        # somebody applying for anything, and demanding an applicant name would
        # make the clerk invent one — which is worse than an empty column,
        # because an invented name is indistinguishable from a real one.
        #
        # ⚠ **THE ADDRESS IS REQUIRED AT SUBMIT AND NO LONGER AT CREATE — PO
        # ratification 2026-09-20 (`DEF-CUS-6006`).** This block read *"The
        # ADDRESS is required either way. There is no such thing as a service
        # request about nowhere"*, which is still true of a request and was
        # never true of a DRAFT: `address_as_given` is captured on **step 3** of
        # REQ-03 while `Save as draft` is a header action on **every** step, so
        # the control was permanently disabled on steps 1 and 2 for every
        # request type in the product — and `create_request`'s own docstring
        # said the opposite (*"a row has to exist before step 2"*). Intent and
        # validation contradicted each other and validation won.
        #
        # **The requirement MOVED; it did not disappear.** `_require_submit_
        # minimum` below is where it now lives, and BR-CUS-070 is untouched:
        # the address is still stored verbatim and still immutable once the row
        # leaves DRAFT.
        required_fields: tuple[str, ...] = ("address_as_given",) if require_address else ()
        if str(cleaned.get("channel") or "") not in _SR.STAFF_RAISED_CHANNELS:
            required_fields = ("applicant_name", *required_fields)
        for required in required_fields:
            if not cleaned.get(required):
                raise errors.ValidationError(
                    errors.VAL_REQUIRED,
                    message_key="customers.serviceRequest.fieldRequired",
                    params={"field": required},
                )
    # ══════════════════════════════════════════════════════════════════════
    # ⚠ **A BLANK ADDRESS IS `""`, NEVER `None` — `DEF-CUS-6008`, AND THE
    # BROWSER IS WHAT FOUND IT.**
    # ══════════════════════════════════════════════════════════════════════
    # `ServiceRequest.address_as_given` is `models.TextField()` — **NOT NULL
    # and no default** — and `_text("")` returns `None` for an empty string. So
    # the moment `DEF-CUS-6006` let a draft be created without an address, the
    # capture screen's own payload (`address_as_given: ""`, which is what the
    # form holds on step 1) reached PostgreSQL as a NULL and the create died:
    #
    #     psycopg.errors.NotNullViolation: null value in column
    #     "address_as_given" of relation "service_requests"
    #
    # ⚠ **EIGHT GREEN BACKEND CASES PASSED OVER IT, AND THEY WERE WRONG IN THE
    # SAME WAY AS EACH OTHER.** Every one of them OMITTED the key, so Django's
    # own `TextField` default put `""` in the column and the model layer hid the
    # difference. The SCREEN never omits it — a controlled input always sends a
    # string — so the shape under test was a shape the product does not send.
    # That is hard-won law 7 habit (2) exactly: *ask what would make this check
    # pass wrongly*, and the answer here was "a payload no browser builds".
    # Found by clicking, which is the only instrument that could (law 6).
    #
    # It is normalised HERE rather than at the four call sites so a PATCH that
    # clears the address on a draft cannot reach the same constraint by another
    # door — `update_request` is `partial=True` and sends the same `""`.
    if "address_as_given" in cleaned and cleaned["address_as_given"] is None:
        cleaned["address_as_given"] = ""
    elif not partial and "address_as_given" not in cleaned:
        # Explicit, rather than relying on `TextField.get_default()`. A NOT NULL
        # column whose blank depends on a framework subtlety is the subtlety
        # this comment exists because of.
        cleaned["address_as_given"] = ""
    cleaned.update(_resolution_from_pick(picks))
    return cleaned


def _resolution_from_pick(picks: dict[str, Any]) -> dict[str, Any]:
    """Turn a clerk's PICK off the premises register into the four resolution
    columns — PO ruling 2026-09-15.

    ⚠ **`address_as_given` AND `address_unit_as_given` ARE NOT TOUCHED HERE AND
    NEVER WILL BE.** `BR-CUS-070`, and the blueprint says it twice on p077 in
    its own words: *"The address is the APPLICANT'S, not a record. It is matched
    against the premises register below it and the match is shown beside it —
    never written over it"*, and *"The match is evidence, never a decision."* A
    pick SITS BESIDE what the applicant said. If a lane ever finds itself
    copying `premises.address_line` into `address_as_given` to tidy a screen up,
    that is the rule being broken, not a formatting improvement.

    Four shapes, and the third is the one the four stored values could not say
    before this ruling:

      * **nothing sent** → `{}`. A PATCH about the fee does not clear a pick.
      * **sent empty** → the pick is UNDONE: back to `unresolved`, every column
        null, `no_premise_flag` false. A clerk who picked the wrong building has
        to be able to say so.
      * **a premises, no unit** → `premise_no_unit`. Lawful and ordinary:
        `BR-CUS-1010` puts the owner's account at an ADDRESS with no unit named.
      * **a unit** → its building comes with it, and the evidence is the unit's
        own — served and vacant, or served and somebody holds a live account.

    ⚠ **A UNIT FROM ANOTHER BUILDING IS REFUSED BY NAME.** Sending
    `picked_premises_id` of one property with `picked_unit_id` of a unit in
    another would leave the two columns disagreeing about where the request is,
    silently, and every screen would then pick whichever one it happened to
    read. There is no repair for that afterwards, because nothing records which
    of the two the clerk meant.

    Both ids go through the seam, so an id belonging to ANOTHER TENANT gets
    metering's own 404-never-403 (HR-1) rather than a boundary re-implemented
    here — and a request cannot be pointed at a building its tenant does not own.
    """
    if not picks:
        return {}
    premises_id = _text(picks.get("picked_premises_id"), 64)
    unit_id = _text(picks.get("picked_unit_id"), 64)
    if premises_id is None and unit_id is None:
        return {
            "resolved_premises_id": None,
            "resolved_unit_id": None,
            "resolution_kind": _SR.RESOLUTION_UNRESOLVED,
            "lookup_found": None,
            "no_premise_flag": False,
            "resolved_at": None,
        }
    if unit_id is not None:
        unit = seams.unit_row(unit_id)  # HR-1 for an id this tenant cannot see
        unit_premises_id = str(getattr(unit, "premises_id", "") or "")
        if premises_id is not None and premises_id != unit_premises_id:
            # A `ValidationError` and not a `BizError`: nothing about the
            # RECORDS is wrong — both rows exist and both belong to this tenant
            # — the PAYLOAD contradicts itself, which is the same fault as an
            # unknown `property_type` above and takes the same shape.
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="customers.serviceRequest.pickedUnitNotAtPremises",
                params={"unit": str(unit_id)},
            )
        premises_id = unit_premises_id
        kind, found = _unit_resolution(unit_id)
    else:
        seams.premises_ref(premises_id)  # HR-1 again, and it proves the row exists
        kind, found = _SR.RESOLUTION_PREMISE_NO_UNIT, LOOKUP_PREMISE_NO_UNIT
    return {
        "resolved_premises_id": premises_id,
        "resolved_unit_id": unit_id,
        "resolution_kind": kind,
        "lookup_found": found,
        # A picked row IS a premises on record, so the red panel on p077 — *"An
        # address that matches nothing is not refused"* — is not this case.
        "no_premise_flag": False,
        "resolved_at": timezone.now(),
    }


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def create_request(actor: Any, payload: Any) -> models.ServiceRequest:
    """Open a `draft`, **and number it** — BR-CUS-093.

    REQ-03's `Save as draft` is a header action on every one of the six steps,
    so a row has to exist before step 2. What the row now also has, from the
    same instant, is its identity: **`SR-26-0048` before the applicant has
    finished spelling their surname.**

    ✅ **PO ruling 2026-08-24, verbatim: *"At creation — every draft is
    numbered"*.** Six consequences came with it and this function is where three
    of them start:

      * **(a) gaps are normal** — an abandoned draft burns its number
        permanently. Nothing here or anywhere else renumbers, backfills or
        reuses one.
      * **(b) the footer copy CHANGES.** Every step read *"Step N of 6 · nothing
        is created until you submit"* and that is now FALSE: something is
        created. It becomes ***"Step N of 6 · saved as draft SR-26-0048"***,
        naming the number the clerk can quote. The catalogue key is
        `customers.serviceRequest.capture.draftFooter` and the read model serves
        the number it needs.
      * **(f) the collect-later fee invoice has a parent from the first
        keystroke**, which was the sharpest edge in DEF-634: a $130.00 fee
        invoice raised before the request existed had nothing to hang on.

    ⚠ **THE ALLOCATION IS INSIDE THIS TRANSACTION ON PURPOSE.** A row that
    committed without a number would be exactly the state the ruling abolishes,
    and it would be indistinguishable from a pre-ruling draft. If the series
    cannot answer, the request is not created at all — failing loudly beats
    handing a clerk a nameless row (`allocate_number` raises `SysError` rather
    than inventing a number).
    """
    data = dict(payload) if isinstance(payload, dict) else dict(payload or {})
    # ⊕ `CR-161-BRC10` W6 — the utility's own fields typed on Staff New
    # Request, lifted out BEFORE `_clean_capture`: they are not capture columns
    # and each record type's answers are judged by that type's own validator.
    custom = (
        request_custom_fields.clean(data.pop("custom_data"), existing={})
        if "custom_data" in data
        else {}
    )
    # ⚠ **`require_address=False` — THE DRAFT MINIMUM, PO 2026-09-20.** A draft
    # is created from the applicant's NAME ALONE, and a staff-raised one from
    # NOTHING (BR-CUS-091). See `_require_submit_minimum` for where the address
    # requirement went.
    cleaned = _clean_capture(dict(data), partial=False, require_address=False)
    with transaction.atomic():
        request = models.ServiceRequest.objects.create(
            tenant_id=_tenant_id(),
            state=_SR.DRAFT,
            received_at=timezone.now(),
            received_by_id=_actor_id(actor),
            custom_data=custom,
            **cleaned,
            # BR-CUS-092(a) — an encrypted identifier and its blind index are
            # written in ONE act. A ciphertext with no token is an applicant the
            # matcher cannot see: unfindable, and every test still green.
            **identity_match.request_blind_index(cleaned),
        )
        _event(request, actor, kind=models.ServiceRequestEvent.KIND_STATE, to_state=_SR.DRAFT)
        allocate_number(actor, request.id)
        request.refresh_from_db(fields=["request_no"])
        # 🔒 DEF-CUS-9819 (PO 2026-10-06, option (a)) — the utility's
        # application fee, at its live price, on every new request.
        add_application_fee_line(actor, request.id)
        _audit(
            actor,
            "service_request.created",
            request.id,
            after={
                "state": _SR.DRAFT,
                "request_no": request.request_no,
                "address_as_given": request.address_as_given,
            },
        )
    return request


# ═══════════════════════════════════════════════════════════════════════════
# THE PORTAL'S DOOR — BR-CWP-076, and the ONLY unauthenticated write this
# module has ever had
# ═══════════════════════════════════════════════════════════════════════════
#: `service_request.channel` for a row raised by a customer or a passer-by on
#: the utility's own web portal (`BR-CWP-076`). The column has always existed
#: and the detail header has always rendered the label *Customer portal*
#: (`models.py`, the `channel` comment); until CR-068 wave B nothing wrote it.
CHANNEL_CUSTOMER_PORTAL = "customer_portal"

#: What a guest may set on a request, and it is a quarter of `CAPTURE_FIELDS`.
#: Everything else — the identifiers, the fee columns, the eligibility claim,
#: the co-applicant — is a CLERK's field, and a payload naming one is refused by
#: name rather than dropped.
#:
#: ⚠ **TWO FIELDS JOINED THE SET ON 2026-09-04 (CR-068 wave C), AND THE
#: SENTENCE ABOVE USED TO NAME ONE OF THEM AS A CLERK'S.** It said *"the
#: requested start — is a CLERK's field"*, which was true of the only guest
#: screen that existed when it was written: a burst-main report has no start
#: date. `CWP-047` — *Start service · about you* — asks *"When do you want
#: service to start?"*, and `US-CWP-013` §5 maps that box to
#: `service_request.requested_start` by name. A field the signed story sends and
#: this set refuses would be an application that cannot say when it wants
#: service.
#:
#: `applicant_kind` joins it for the same reason and no other: `CWP-047` asks
#: *"Are you a person or a business?"*, `US-CWP-013` TC-4 turns the answer into
#: which identity fields are asked for, and the column already exists with
#: `person` as its default. **Neither widening touches an identifier, a fee or
#: an account** — the three things this set exists to keep out.
#:
#: ⚠ **A THIRD JOINED IT ON 2026-09-04 (`CR-072`), AND IT IS THE ONE THE
#: PRODUCT OWNER ASKED FOR BY NAME.** *"if we have to icnrease the defination
#: of Service request we should do it"*. `problem_kind` is what a passer-by
#: picked off `CWP-006`'s radio list — a leak, no water, low pressure, a missed
#: collection, a damaged meter. Before it, the report's kind had nowhere on
#: this row to go, which is why the same act wrote a SECOND record and handed
#: the stranger that one's reference instead of this one's.
#:
#: **It passes the same test the last two widenings passed**: it is not an
#: identifier, not a fee and not an account. It is a radio button on a public
#: form, and the vocabulary it is checked against is `metering`'s, not one
#: copied into this file.
PORTAL_CAPTURE_FIELDS = frozenset(
    {
        "applicant_name",
        "applicant_phone",
        "applicant_email",
        "applicant_kind",
        "address_as_given",
        "address_unit_as_given",
        "requested_start",
        "what_they_said",
        "preferred_language",
        "problem_kind",
        # ⊕ **`DEF-CWP-9046` — THE APPLICANT'S DATE OF BIRTH.** The portal
        # discarded it at Send because this table had no column for it (CR-068
        # wave C, 2026-09-04); the column arrived with the PO ruling of
        # 2026-09-15 (*"Date of birth and driver's licence on step 1"*) and this
        # door was never widened to it. It is not a government identifier
        # (`BR-CUS-1020`) and it is stored ONCE — here — the draft's copy still
        # blanked at Send. `_refuse_fields_for_kind` still refuses it for a
        # business.
        "date_of_birth",
        # ⊕ **`DEF-CWP-9817` — THE TOWN AND THE ZIP THE APPLICANT TYPED.** The
        # portal's step 1 asks them as the blueprint draws them (p31), and they
        # are `BR-CUS-1091`'s own two columns: a record of what was SAID, so
        # the Approve window's address match (`premises_matching_address`) can
        # use town and ZIP on a portal request exactly as it does on a clerk's.
        # The portal asks no state (the blueprint draws none) — ⊕ but
        # `DEF-CWP-10541`: the application form SHOWS one (the matched
        # premises', else the utility's own) and the request now carries the
        # state the applicant saw on Check and send, so the acknowledgement's
        # address reads as the screen did.
        "address_city_as_given",
        "address_state_as_given",
        "address_postal_code_as_given",
        # ⊕ **DEF-CUS-10250 — MOVE-IN'S FIELDS, FROM THE PORTAL FORM** (PO
        # 2026-10-18: the portal asks the same fields, order and rules as
        # Move-in, so the request it becomes carries every one), on the SAME
        # columns the staff capture writes (lane CF-1, `customers/0087`), so
        # the move-in prefill reads one place. The co-applicant is ONE card in
        # `co_applicants`, cleaned by Move-in's own card rules; *How should we
        # contact you?* and the Preferences panel's two ticks. The SSN last
        # four is NOT here: it is an identifier and travels as its own keyword
        # (`ssn_last4=`), stored encrypted.
        "co_applicants",
        "contact_by",
        "paperless",
        "sms_reminders",
        # ⊕ **DEF-CUS-10252 — WHERE THE BILL GOES, ON THE REQUEST'S OWN
        # COLUMNS.** The portal's mailing block was kept on the draft alone
        # (`portal_seam.application_mailing_address`), so the clerk SAW it on
        # the request and the move-in it became never prefilled it. Hard rule
        # 8's first named exception, held on the request until an account
        # exists, under CF-1's one name (`mailing_*`; the capture cleaner
        # mirrors it into `billing_*_as_given` for older readers).
        "mailing_same",
        "mailing_line1",
        "mailing_line2",
        "mailing_city",
        "mailing_state",
        "mailing_postal_code",
    }
)


def offered_categories(tenant_id: Any = None) -> list[dict[str, Any]]:
    """The categories a NEW record may be given, each with its live sub-types —
    `DEF-CWP-9818`, the portal's step 3 list.

    ⚠ **THE SAME LIST THE CLERK PICKS FROM, READ THE SAME WAY.** A category is
    offered when it is `active` and not `legacy` — `GET /service-requests/
    categories`' `selectable`, and Settings › Account types' *Stop offering*
    sets `legacy` (`DEF-CUS-9808`); a sub-type when it is `active`
    (`GET /accounts/subcategories`). Ordered as both of those are, so the two
    screens list the same rows in the same order.

    ⚠ **CODES, NEVER IDS.** The caller is the anonymous guest surface, where no
    id of any kind travels; both codes are unique per tenant
    (`uq_account_types_tenant_code_ci`, `uq_account_subtypes_tenant_code_ci`).
    """
    tid = tenant_id or _tenant_id()
    types = [
        row
        for row in models.AccountType.objects.filter(tenant_id=tid).order_by(
            "sort_order", "code", "id"
        )
        if row.active and not row.legacy
    ]
    children: dict[Any, list[dict[str, str]]] = {}
    for sub in (
        models.AccountSubtype.objects.filter(tenant_id=tid, active=True)
        .exclude(account_type_id__isnull=True)
        .order_by("name", "code", "id")
    ):
        children.setdefault(sub.account_type_id, []).append({"code": sub.code, "name": sub.name})
    return [
        {"code": row.code, "name": row.name, "subcategories": children.get(row.id, [])}
        for row in types
    ]


def portal_category_problem(type_code: Any, subtype_code: Any) -> str | None:
    """Why this pick may NOT be put on a portal application, or `None`.

    `"category"` — the category is not one this utility offers on new records;
    `"subcategory"` — the sub-category is not a live child of that category (a
    sub-category with no category is the same answer). Judged against
    `offered_categories`, so the screen and the server agree by construction.
    """
    code = str(type_code or "").strip().lower()
    sub = str(subtype_code or "").strip().lower()
    if not code:
        return "subcategory" if sub else None
    offered = {row["code"].lower(): row for row in offered_categories()}
    row = offered.get(code)
    if row is None:
        return "category"
    if sub and sub not in {child["code"].lower() for child in row["subcategories"]}:
        return "subcategory"
    return None


def _portal_category(request: models.ServiceRequest, category: Any) -> dict[str, Any] | None:
    """`DEF-CWP-9818` — put the applicant's own pick on the request, or nothing.

    PO ruling 2026-10-06 (b), verbatim: *"Show the full Category and
    Sub-category dropdowns from Settings on step 3, and let the applicant pick
    from all seven categories and their sub-categories. The clerk can still
    change it."* The clerk changes it with `set_customer_category`, unchanged.

    ⚠ **NOT `set_customer_category`, DELIBERATELY.** That is the CLERK's act
    under a staff role; a stranger has none, and borrowing one would put the
    decision to bypass a guard in the caller (`create_from_portal`'s own
    reasoning). This writes the same two columns from the same offered list.

    ⚠ **A PICK THAT STOPPED BEING OFFERED BETWEEN STEP 3 AND SEND WRITES
    NOTHING AND IS NOT REFUSED** — `_portal_service_rows`' rule for a service
    switched off in the same window: refusing would lose a stranger's whole
    application at the last button, and the request then arrives *Not yet
    classified* for the clerk, which is exactly today's behaviour.
    """
    pick = category if isinstance(category, dict) else {}
    code = str(pick.get("account_type_code") or "").strip()
    sub = str(pick.get("account_subtype_code") or "").strip()
    if not code or portal_category_problem(code, sub) is not None:
        return None
    account_type = models.AccountType.objects.filter(
        tenant_id=request.tenant_id, code__iexact=code
    ).first()
    subtype = (
        models.AccountSubtype.objects.filter(
            tenant_id=request.tenant_id, code__iexact=sub, account_type=account_type
        ).first()
        if sub
        else None
    )
    request.account_type = account_type
    request.account_subtype = subtype
    request.save(update_fields=["account_type", "account_subtype", "updated_at"])
    return {
        "account_type": account_type.code,
        "account_subtype": str(subtype.id) if subtype else None,
    }


class _PortalReporter:
    """The actor a GUEST write carries: no id, and no role.

    ⚠ **IT DELIBERATELY GRANTS NOTHING.** It is not a staff user with a role
    borrowed for the occasion — `_PlantActor` does that for provisioning and it
    is the wrong shape here, because provisioning is performed FOR the tenant's
    own System Admin and a burst-main report is performed by a stranger. This
    object exists so `_event` and `_audit` have something to ask for an id, and
    the answer they get is `None`: *"we do not know who asked"*, which is the
    truthful entry for this path and is what `BR-CWP-021` (the portal is never a
    person) requires the trail to say.

    Because it carries no role, **passing it to any `@require_role` function in
    this module raises `AUTH-002`** — which is the property that makes it safe
    to hand around: the guest path can only reach what is explicitly role-free.
    """

    __slots__ = ()
    id = None
    pk = None
    role = None
    is_authenticated = False


PORTAL_REPORTER = _PortalReporter()


def create_from_portal(
    payload: Any,
    *,
    service_codes: Any = None,
    custom_data: Any = None,
    application: bool = False,
    category: Any = None,
    ssn_last4: Any = None,
    online_fee: dict[str, Any] | None = None,
    resolved_place: dict[str, Any] | None = None,
) -> models.ServiceRequest:
    """Raise a request from the customer portal — created, numbered, submitted.

    ⊕ **`resolved_place` — `CR-200-BRC10` S9 (PO 2026-10-29, 2A and Ask-us A).**
    `{premises_id, unit_id}` the PORTAL'S SERVER worked out from the address the
    applicant picked — street, town and ZIP re-matched through metering's own
    matcher, and the apartment by its LABEL — so the request arrives linked and
    *"the clerk does not look it up"*. It runs through `_resolution_from_pick`,
    the clerk's own pick path, so the four resolution columns mean exactly what
    they mean for a counter capture. ⚠ **IT IS A KEYWORD AND NOT A FIELD, FOR
    `PICK_FIELDS`' OWN REASON:** a guest naming `picked_premises_id` in the
    payload is still refused by name — a stranger who could name an id could
    attach their request to somebody else's building. Nothing a browser sends
    reaches this keyword; `apps/portal` derives it from text after the fact.

    ⊕ 🔒 **`online_fee` — `CR-191-BRC10` (PO 2026-10-23).** An application whose
    fee is above $0.00 is paid by card BEFORE it is submitted (*"they can't say
    pay later"*). The portal charges the card first and passes what the
    provider approved — `{amount, currency, reference, brand, last_four}` —
    and it is recorded HERE, inside this transaction, before the
    acknowledgement: see `_record_online_fee`. `None` is every other caller,
    unchanged.

    **NO `actor` PARAMETER, AND THAT IS THE SIGNATURE SAYING WHAT IT IS.** There
    is nobody signed in: `BR-CWP-027` — *"reporting an outage, a leak or no water
    does not require the reporter to be a customer"*. `create_request` above is
    `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` and stays that way; this is a
    SECOND, NARROWER door beside it rather than a widening of the first, because
    widening the first would let every staff path lose its gate to reach this
    one case.

    **WHY THE DOOR IS IN THIS MODULE AND NOT IN `apps/portal`.** The module that
    owns the rule owns the exception to it (B2 §2). A portal-side function that
    fabricated a clerk actor to get past `@require_role` would put the decision
    to bypass a guard in the module the guard was written to constrain, where no
    reviewer of `customers` would ever see it.

    **WHAT IT CANNOT DO, and this list is the guard:**
      * it accepts ONLY the fields `PORTAL_CAPTURE_FIELDS` names and refuses
        every other by name — no Social Security number, no fee, no eligibility
        claim, no account, no customer link. ⚠ **This sentence used to say
        *"seven fields"* and the set held nine** (`DEF-CWP-3744`, 2026-09-04):
        two waves widened the set and neither moved the count, so the docstring
        described a NARROWER guard than the code has. The set is named instead
        of counted now, because a count in prose beside a literal set is a
        number that goes stale every time somebody does the work;
      * `channel` is FORCED to `customer_portal` and a caller cannot set it —
        `BR-CWP-076`, and it is what makes the row identifiable on the worklist
        and in every count;
      * it links no account and changes none. `BR-CWP-026`: *"a public form may
        create work and may never change an account."*

    **A PHONE IS REQUIRED** (`US-CWP-007` TC-4). The form's own promise is *"we
    ring you only if we need to"*, and a promise to ring needs a way to ring.

    ⚠ **THE ACKNOWLEDGEMENT IS SENT WHEN THE EMAIL IS VALID — AMENDED
    2026-10-22 (`DEF-CWP-10539`).** This paragraph read *"NO ACKNOWLEDGEMENT IS
    SENT AND THE REASON IS RECORDED ON THE ROW"*, on `BR-CWP-028` (*"the
    reference is the entire record of the interaction"*). The PO ruled that a
    portal request gets the same letter a clerk's submit sends when the
    applicant gave a valid email (*"yes if we have valid email"*). So once the
    request is submitted, `_send_acknowledgement` — the staff function's own
    body — runs with `PORTAL_REPORTER`. With no email or a malformed one
    nothing is queued and the row keeps `ACK_NO_ADDRESS`, written at creation
    rather than left blank, so a clerk reads why nothing was sent.
    """
    data = payload if isinstance(payload, dict) else dict(payload or {})
    unknown = set(data) - PORTAL_CAPTURE_FIELDS
    if unknown:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.fieldNotAccepted",
            params={"field": sorted(unknown)[0]},
        )
    if not _text(data.get("applicant_phone")):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.fieldRequired",
            params={"field": "applicant_phone"},
        )
    data["channel"] = CHANNEL_CUSTOMER_PORTAL
    cleaned = _clean_capture(dict(data), partial=False)
    if resolved_place and (resolved_place.get("premises_id") or resolved_place.get("unit_id")):
        # CR-200-BRC10 S9 — the server-resolved place (see the docstring).
        cleaned.update(
            _resolution_from_pick(
                {
                    "picked_premises_id": resolved_place.get("premises_id"),
                    "picked_unit_id": resolved_place.get("unit_id"),
                }
            )
        )
    # 🔒 ⊕ DEF-CUS-10225 — the applicant's SSN LAST FOUR (PO 2026-10-18: *"last
    # 4 of SSN only"* online). Four digits or nothing; stored encrypted in
    # `applicant_ssn_last4` (see the model). A separate keyword, never a
    # widening of `PORTAL_CAPTURE_FIELDS`, because `ssn_last4` stays refused BY
    # NAME on every staff door (`IDENTIFIER_FIELDS`).
    last4 = _text(ssn_last4)
    if last4 is not None:
        if not re.fullmatch(r"\d{4}", last4):
            raise errors.ValidationError(
                errors.VAL_FORMAT, message_key="customers.serviceRequest.ssnLast4Format"
            )
        cleaned["applicant_ssn_last4"] = last4
    # ⊕ `CR-161-BRC10` W7 — the applicant's answers to the utility's own
    # questions. **A SEPARATE KEYWORD, NOT A WIDENING OF
    # `PORTAL_CAPTURE_FIELDS`**, for `service_codes`' reason: that set is the
    # guest's whitelist of COLUMNS, and this is the tenant's own vocabulary,
    # judged here again by the request's own rules — and ONLY against the
    # fields the utility asks on the portal, so a stranger cannot write a field
    # the utility keeps internal even by calling this door directly.
    custom = request_custom_fields.clean_from_portal(custom_data)
    with transaction.atomic():
        request = models.ServiceRequest.objects.create(
            tenant_id=_tenant_id(),
            state=_SR.DRAFT,
            received_at=timezone.now(),
            received_by_id=None,  # nobody took this call — see _PortalReporter
            acknowledgement_state=ACK_NOT_SENT,
            acknowledgement_absence_reason=ACK_NO_ADDRESS,
            custom_data=custom,
            **cleaned,
        )
        _event(request, PORTAL_REPORTER, kind=models.ServiceRequestEvent.KIND_STATE, to_state=_SR.DRAFT)
        _allocate_number(PORTAL_REPORTER, request.id)
        request.refresh_from_db(fields=["request_no"])
        asked = _portal_service_rows(request, service_codes)
        # 🔒 DEF-CUS-9819 — a Start service APPLICATION carries the utility's
        # application fee (PO 2026-10-06, option (a)); a report, a question or
        # any other ask this door also writes does not (decision log, same day).
        if application:
            add_application_fee_line(PORTAL_REPORTER, request.id)
        if online_fee is not None:
            # 🔒 CR-191-BRC10 — BEFORE the acknowledgement below, so the
            # letter pins the class that states the money (BR-CUS-090 (3)).
            _record_online_fee(request.id, online_fee, application=application)
        # ⊕ `DEF-CWP-9818` — the applicant's category pick, a SEPARATE keyword
        # for `service_codes`' reason (the tenant's own vocabulary, judged here
        # again, not a column on the guest's whitelist).
        picked = _portal_category(request, category)
        if picked is not None:
            _audit(
                PORTAL_REPORTER,
                "service_request.category_set",
                request.id,
                before={"account_type": None, "account_subtype": None},
                after=picked,
            )
        _audit(
            PORTAL_REPORTER,
            "service_request.created_from_portal",
            request.id,
            after={
                "state": _SR.DRAFT,
                "channel": CHANNEL_CUSTOMER_PORTAL,
                "request_no": request.request_no,
                "address_as_given": request.address_as_given,
                "services": asked,
                # W7 — what the applicant answered, as stored on the request.
                **({"custom_data": custom} if custom else {}),
            },
        )
        # Straight to `submitted`: a guest has no draft to come back to, and a
        # report sitting in `draft` is invisible on the clerk's worklist, which
        # is the one place US-CWP-007 TC-1 requires it to appear.
        _apply(
            PORTAL_REPORTER,
            request.id,
            rules.SUBMIT,
            audit_action="service_request.submitted_from_portal",
        )
        # ⊕ DEF-CWP-10539 (PO 2026-10-22, *"yes if we have valid email"*) — the
        # same acknowledgement a clerk's submit sends, through the same body.
        # No email or a malformed one: nothing is queued and the row keeps the
        # `ACK_NO_ADDRESS` it was created with.
        # ⊕ DEF-CWP-10540 — and only a request that NAMES A SERVICE. The ruling
        # was about service requests and the letter is written for one (*"your
        # request for {service_type} … target date"*); a question, a dispute or
        # a copy of a bill would read *"your request for ——"*. Those keep their
        # pre-10539 behaviour exactly (decision log 2026-10-22, our judgment).
        if asked and _valid_email(request.applicant_email):
            _send_acknowledgement(PORTAL_REPORTER, request.id)
    return request_row(request.id)


def _record_online_fee(request_id: Any, paid: dict[str, Any], *, application: bool) -> None:
    """🔒 HUMAN-REVIEW-PENDING — `CR-191-BRC10`: a portal application fee the
    card provider has APPROVED, recorded exactly as the counter records a paid
    fee and earned at once.

    PO, verbatim (2026-10-23): *"if there is a application or service fee then
    consumer will have to pay it online"* and *"That is application fee it is
    not refunded"*.

    Three acts, all inside `create_from_portal`'s transaction (decision log
    2026-10-23, *"how it is built"* 1–3):

      1. the request's fee columns, as `collect_fee` writes them — method
         `card`, receipt number = the request number (judgment 6), so the
         fee condition reads `$0.00` outstanding and approval asks nothing;
      2. `payments.record_counter_receipt` — DR the card's clearing account,
         else `1010` · CR `2400`, the provider's reference in `confirmation`;
      3. `payments.release_counter_receipt(outcome="paid_online")` — DR `2400`
         · CR the charge code's OWN revenue account, state `earned`.

    **Worked (Ann Arbor):** fee line `APP-FEE` $10.0000, card approved for
    $10.0000 → DR 1010 10.0000 / CR 2400 10.0000, then DR 2400 10.0000 / CR
    4600 10.0000; `fee_total_to_collect` → quoted 10.0000, collected 10.0000,
    outstanding 0.0000.

    ⚠ **THE AMOUNT MUST EQUAL THE FEE LINE OR NOTHING IS WRITTEN.** The portal
    re-reads the price before charging, so a mismatch here means the price
    moved between that read and this one; raising rolls the whole request back
    and the edge answers *"We could not record that payment."* — never a
    request carrying a fee that disagrees with the money (*"all or waived"*,
    BR-CUS-090). Money is `Decimal` at four places (hard rule 2).

    Idempotent by construction: the request is new inside this transaction,
    `uq_counter_receipts_source` allows one receipt per request, and the
    ledger's posting keys allow one entry per event (hard rule 6). Every act
    writes `audit_log` (hard rule 7).
    """
    if not application:
        raise errors.SysError(
            errors.SYS_INTERNAL,
            message_key="portal.quickPay.notRecorded",
            params={"detail": "only an application carries an application fee"},
        )
    amount = Decimal(str(paid.get("amount"))).quantize(AMOUNT_QUANTUM)
    reference = _text(paid.get("reference"), 120)
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        quote = fee_total_to_collect(request.id)
        owing = (quote["quoted"] - quote["settled"] - quote["collected"]).quantize(AMOUNT_QUANTUM)
        currency = quote["currency"] or _currency()
        if amount <= 0 or amount != owing or not reference or (
            paid.get("currency") and str(paid["currency"]).upper() != str(currency).upper()
        ):
            raise errors.SysError(
                errors.SYS_INTERNAL,
                message_key="portal.quickPay.notRecorded",
                params={"detail": "the approved amount is not the application fee"},
            )
        method = _SR.FEE_METHOD_CARD
        now = timezone.now()
        request.fee_quoted = quote["quoted"]
        request.fee_collected = amount
        request.fee_currency = currency
        request.fee_method = method
        request.fee_receipt_no = request.request_no
        request.fee_collected_at = now
        request.fee_collected_by_id = None
        request.save(
            update_fields=[
                "fee_quoted",
                "fee_collected",
                "fee_currency",
                "fee_method",
                "fee_receipt_no",
                "fee_collected_at",
                "fee_collected_by",
                "updated_at",
            ]
        )
        payments_seam.record_counter_receipt(
            source_type=payments_seam.SOURCE_SERVICE_REQUEST,
            source_id=request.id,
            source_ref=request.request_no,
            receipt_no=request.request_no,
            amount=amount,
            currency=currency,
            method_code=method,
            taken_at=now,
            taken_by_id=None,
            card={"last4": paid.get("last_four"), "brand": paid.get("brand")},
            cheque=None,
            actor=None,
            posted_on=seams.tenant_today(),
            confirmation=reference,
            memo=None,
        )
        payments_seam.release_counter_receipt(
            source_type=payments_seam.SOURCE_SERVICE_REQUEST,
            source_id=request.id,
            outcome="paid_online",
            fee_lines=_fee_lines_for_release(request.id),
            released_at=now,
            released_by_id=None,
            actor=None,
        )
        _event(
            request,
            PORTAL_REPORTER,
            kind=models.ServiceRequestEvent.KIND_SYSTEM,
            note=request.request_no,
            note_type=f"fee_collected:{method}",
        )
        _audit(
            PORTAL_REPORTER,
            "service_request.fee_paid_online",
            request.id,
            before={"fee_collected": None, "fee_receipt_no": None},
            after={
                "quoted": str(quote["quoted"]),
                "collected": str(amount),
                "outstanding": "0.0000",
                "currency": currency,
                "method": method,
                "receipt_no": request.request_no,
                "confirmation": reference,
                "card_last_four": _text(paid.get("last_four"), 4),
            },
        )


def _valid_email(value: Any) -> bool:
    """A well-formed address by Django's own `validate_email` — the check the
    portal's sign-in and account forms use (`portal.credentials.email_refusal`).
    A format check, never a deliverability one."""
    from django.core.validators import validate_email

    if not isinstance(value, str) or not value.strip():
        return False
    try:
        validate_email(value.strip())
    except DjangoValidationError:
        return False
    return True


def _portal_service_rows(request: models.ServiceRequest, service_codes: Any) -> list[str]:
    """`DEF-CUS-9034` — **the services the applicant ticked become the request's
    own service rows**, exactly as a clerk's capture step 2 writes them.

    Until 2026-10-01 a portal application carried its services ONLY as a
    sentence in `what_they_said` (*"Applied through the customer portal for:
    water, sewer"*), so the request's Services table, the move-in job's
    *services asked for* (`move_in_jobs.services_asked_for`) and the build's
    prefill all read EMPTY, and the clerk retyped from prose what the customer
    had already ticked. Found walking a portal request to an active customer
    for the PO ruling of that day.

    ⚠ **A SEPARATE KEYWORD, NOT A WIDENING OF `PORTAL_CAPTURE_FIELDS`.** That
    set is the guest's whitelist of COLUMNS; this is a list of the utility's
    own service codes, each checked against the services the utility has
    switched on, and only the portal's own application door passes it.

    ⚠ **A CODE THE UTILITY DOES NOT SELL WRITES NO ROW AND IS NOT REFUSED.**
    The applicant picked from the utility's own list, so this happens only when
    a service was switched off between their tick and their send; refusing
    would lose a stranger's whole application at the last button. The code is
    still in their own words beside it, which the clerk reads.

    Each row carries the applicant's one requested start (`BR-CUS-1070` makes
    the date per service; the portal form asks it once). `available` stays
    NULL — *not yet asked* (REQ-03.3).
    """
    from apps.tenancy import models as tenancy_models

    codes: list[str] = []
    for raw in service_codes or ():
        code = str(raw or "").strip()
        if code and code not in codes:
            codes.append(code)
    if not codes:
        return []
    sold = set(seams.enabled_service_codes())
    known = {
        row.code: row
        for row in tenancy_models.Service.objects.filter(code__in=[c for c in codes if c in sold])
    }
    written: list[str] = []
    for code in codes:
        if code not in known:
            continue
        models.ServiceRequestService.objects.create(
            tenant_id=request.tenant_id,
            request=request,
            service=known[code],
            requested_start=request.requested_start,
        )
        written.append(code)
    return written


def note_from_portal(
    request_id: Any,
    *,
    note: str,
    note_type: str | None = None,
    customer_visible: bool = False,
) -> Any:
    """A note on a request the portal raised — **INTERNAL unless the CUSTOMER
    typed it themselves.**

    ⚠ **`customer_visible` ARRIVED 2026-09-04 WITH `US-CWP-063` AND DEFAULTS
    `False`, SO EVERY EXISTING CALLER IS UNCHANGED.** The one caller that passes
    `True` is `CWP-051`'s *Add a note* — the customer's own sentence on their own
    request — and `BR-CWP-075` signs that as one of the four transitions a
    customer may make. Hiding a person's own words from them would be the flag
    doing the opposite of its job.

    ⚠ **WAVE C NEEDS EXACTLY ONE THING FROM THIS AND IT IS WORTH NAMING.**
    `US-CWP-013` TC-2: a date of birth matching somebody on file *"flags a
    possible returning customer **for a clerk**. ⚠ It does not link the records
    and does not tell the applicant."* There is no column for *"this might be
    somebody we know"* — `matched_customer` is what a clerk sets when they have
    DECIDED — so the flag is a sentence in the history, which is where a clerk
    reads it and where it cannot be mistaken for a decision.

    ⚠ **AND NOTHING WRITTEN HERE IS AN IDENTIFIER.** `BR-CUS-092(c)` keeps the
    full value of an identifier out of a log line, and a note is a log line: the
    caller passes the VERDICT in words and never the date of birth that produced
    it (`apps/portal/services._application`).

    `add_note` above is `@require_role`'d and stays that way; this is the same
    second, narrower door `create_from_portal` is, carrying the same role-free
    `PORTAL_REPORTER` so `_event` records *"we do not know who asked"*.
    """
    text = _text(note)
    if not text:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.noteRequired",
            params={},
        )
    return _event(
        request_row(request_id),
        PORTAL_REPORTER,
        kind=models.ServiceRequestEvent.KIND_NOTE,
        note=text,
        note_type=note_type,
        internal=not customer_visible,
    )


def withdraw_from_portal(request_id: Any) -> models.ServiceRequest:
    """`BR-CWP-079` — the customer stops their own request, **and the account is
    not touched.**

    ⚠ **THE STATE TABLE IS THE PERMISSION, AND IT IS NOT RESTATED HERE.**
    `service_request.TRANSITIONS[WITHDRAW]` already names the four states a
    withdrawal is lawful from — `draft`, `submitted`, `under_review`,
    `more_info` — so a request a clerk has APPROVED refuses by the same code
    path a clerk's own withdrawal would (`US-CWP-063` TC-5). A second list of
    states in this function would be a second answer to the one question
    `BR-CWP-075` settles.

    ⚠ **NOTHING BUT `state`, `closed_at` AND ONE TIMELINE ROW MOVES**
    (`BR-CWP-079`: *"withdrawing does not touch the account"*, `BR-CWP-026`).
    `_apply` is the only door through which a state moves and it writes no
    account column; `US-CWP-063` TC-4 asserts the account is byte-identical
    afterwards.

    `transition` above is `@require_role`'d and stays that way; this is the same
    second, narrower door `create_from_portal` and `note_from_portal` are,
    carrying the role-free `PORTAL_REPORTER` so the trail records *"we do not
    know who asked"* (`BR-CWP-021`) rather than inventing a clerk.
    """
    return _apply(
        PORTAL_REPORTER,
        request_id,
        rules.WITHDRAW,
        audit_action="service_request.withdrawn_from_portal",
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def update_request(actor: Any, request_id: Any, payload: Any) -> models.ServiceRequest:
    """Edit the capture fields while the state allows.

    ⚠ **`address_as_given` IS REFUSED ONCE THE REQUEST IS SUBMITTED —
    BR-CUS-070.** *"The address as the applicant gave it is kept verbatim and
    never overwritten by the resolved record."* B18 makes it *"a column, not a
    convention"* and TC-REQ-6 asks for it byte-identical to submission. The
    resolver writes `resolved_premises_id` / `resolved_unit_id` beside it and
    never through it.

    ⚠ **IT IS STILL ONE FIELD AND NOT FOUR, WHICH IS WORTH SAYING BECAUSE IT
    NEARLY BECAME FOUR.** On 2026-09-15 this refusal was briefly widened to a
    set, for three city/state/postcode columns that the PO then ruled out of
    this table altogether (*"we should take it from premises/Unit"*). The
    address the applicant gave is one line plus a unit label; the rest of it
    belongs to the premises the search matched.
    """
    data = dict(payload) if isinstance(payload, dict) else dict(payload or {})
    # ⊕ `CR-161-BRC10` W6 — see `create_request`. Validated against the ROW's
    # copy below, so an edit names only what changed and the rest is kept.
    custom_submitted = data.pop("custom_data", None)
    custom_present = custom_submitted is not None
    cleaned = _clean_capture(dict(data), partial=True)
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        # ⚠ **WAS `rules.is_terminal` ALONE, WHICH LET AN APPROVED REQUEST BE
        # EDITED (`DEF-CUS-6427`).** See `_refuse_unless_editable`.
        _refuse_unless_editable(request)
        if custom_present:
            custom_before = request_custom_fields.stored(request)
            request.custom_data = request_custom_fields.clean(
                custom_submitted, existing=request.custom_data
            )
        if "address_as_given" in cleaned and request.state != _SR.DRAFT:
            _refuse(
                errors.BIZ_IMMUTABLE,
                "customers.serviceRequest.addressAsGivenImmutable",
                br_ref="BR-CUS-070",
                state=request.state,
            )
        # BR-CUS-1022 — the kind on the ROW decides on a partial update, the
        # same posture `customer_edit._validate` takes and for the same reason: a
        # PATCH that sets only a licence says nothing about who the applicant is.
        # Evaluated against the state the row will be IN, so setting the kind and
        # the field in one call is refused too.
        effective_kind = cleaned.get("applicant_kind", request.applicant_kind)
        _refuse_fields_for_kind(
            effective_kind,
            {
                field
                for field in KIND_FORBIDDEN_FIELDS.get(str(effective_kind or ""), ())
                if (cleaned[field] if field in cleaned else getattr(request, field))
                not in (None, "")
            },
        )
        if "co_applicants" in cleaned:
            # Lane CF-1 — a card re-sent with a blank SSN or licence is a card
            # read back as its LAST FOUR and not retyped: the stored
            # ciphertext stays (matched by name), never wiped by a screen that
            # was never shown the value.
            cleaned["co_applicants"] = _keep_stored_secrets(
                cleaned["co_applicants"], request.co_applicants
            )
        before = {key: getattr(request, key) for key in cleaned}
        for key, value in cleaned.items():
            setattr(request, key, value)
        # ⚠ **AFTER `before`/`after` ARE BUILT, DELIBERATELY.** The blind index is
        # a keyed token rather than the value, but it is not something a reviewer
        # of the trail can use either, and BR-CUS-092(c) keeps `audit_log` to the
        # MASK. So it moves with the identifier and never into the blob.
        for key, value in identity_match.request_blind_index(cleaned).items():
            setattr(request, key, value)
        request.save()
        audit_before, audit_after = before, dict(cleaned)
        if custom_present:
            audit_before = {**before, "custom_data": custom_before}
            audit_after = {**audit_after, "custom_data": request.custom_data}
        _audit(actor, "service_request.updated", request.id, before=audit_before, after=audit_after)
    return request


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def set_customer_category(
    actor: Any, request_id: Any, *, account_type_code: str, account_subtype_id: Any = None
) -> models.ServiceRequest:
    """REQ-03.2's `Customer category` + `Sub-category`.

    ✅ **ALL SEVEN CHIPS ARE REAL — BR-CUS-094 (PO 2026-08-24), closing
    DEF-635.** `Residential · Commercial · Industrial · Agricultural ·
    Institutional · Municipal · Builder or developer` is what REQ-03.2 renders,
    and until today only four of them existed. The PO was shown that the four
    are a SIGNED vocabulary (B2 r5 #12 [D5]) that **plans, deposits and tax
    treatment key off** — the sub-category help text says the category *"sets
    which plans are eligible"*, so it is load-bearing on price — and chose
    *"Expand the signed list to seven"*: the four new ones are REAL categories a
    plan can be priced for, not display labels. Migration 0019 seeds them.

    ⚠ **AND ONE CODE IS REFUSED HERE THAT WAS ACCEPTED YESTERDAY: `government`,
    because it is LEGACY.** This is the part BR-CUS-094 says it could not settle
    for us: *"Municipal and Institutional are both plausible readings of it — a
    city water department and a state university are different things and the
    stored value cannot tell them apart. So no row is re-labelled by guess."* So
    the migration is ADDITIVE and `government` is flagged rather than rewritten:
    it **stops being selectable on new records and changes nothing else** —
    still a valid FK, still filterable, still priceable, every existing account
    keeps it and bills exactly as it did yesterday.

    The refusal therefore has a completely different fix from the one it
    replaces. Yesterday's said *nobody has ruled this vocabulary*; this one says
    *a human must decide whether this record is Municipal or Institutional*, and
    it names the code so they can.
    """
    code = _text(account_type_code, 60)
    # Tenant-scoped since the PO ruling of 2026-09-17: the category a request
    # carries is a row of THIS utility's own list.
    account_type = models.AccountType.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), code=code
    ).first()
    if account_type is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.categoryNotSeeded",
            params={"category": str(code)},
        )
    if account_type.legacy:
        _refuse(
            errors.BIZ_STATE,
            "customers.serviceRequest.categoryIsLegacy",
            br_ref="BR-CUS-094",
            category=str(code),
        )
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        _refuse_unless_editable(request)  # DEF-CUS-6427
        subtype = None
        if account_subtype_id is not None:
            subtype = models.AccountSubtype.objects.filter(
                tenant_id=request.tenant_id, id=account_subtype_id
            ).first()
            if subtype is None:
                raise errors.deny_as_not_found("BR-TEN-003")
        before = {
            "account_type": request.account_type_id,
            "account_subtype": request.account_subtype_id,
        }
        request.account_type = account_type
        request.account_subtype = subtype
        request.save(update_fields=["account_type", "account_subtype", "updated_at"])
        _audit(
            actor,
            "service_request.category_set",
            request.id,
            before=before,
            after={"account_type": code, "account_subtype": str(subtype.id) if subtype else None},
        )
    return request


def suggest_customer_matches(*_args: Any, **_kwargs: Any) -> None:
    """⛔ STILL NOT BUILT — **BR-CUS-089** — AND THE REASON CHANGED ON 2026-09-15.

    ⚠ **THE OLD REASON IS NO LONGER TRUE AND IS RECORDED HERE RATHER THAN
    QUIETLY REPLACED.** It read: *"The detail's `Customer match` panel is badged
    `Strong` and states `Matched on: ID number and date of birth`. This schema
    carries NEITHER."* The schema carries **both** since the PO's ruling of
    2026-09-15 — `ssn`, `drivers_licence` and `date_of_birth` are captured —
    and `identity_match.evidence_from_service_request` lifts all three. A
    refusal whose stated reason has expired is the mirror of dead UI and nothing
    in this repo can see it (hard-won law 2, `DEF-CWP-3925`), so it is corrected
    in the commit that made it false.

    **What stands is that nobody has built the matcher for THIS surface.**
    `apps/customers/identity_match.py` weighs evidence against a CUSTOMER and
    `recognise` / `reuse_candidate` are its doors; pointing one of them at a
    service request is a wave with its own proof, not a line added here.
    `BR-CUS-089` lets a `strong` match MOVE MONEY — a **$150.00** deposit,
    **$153.50** with `BR-CUS-057`'s interest — so a tier this module produced
    without proving it would be a money bug, and the criteria are signed and may
    not be widened to fit what is easy to compute.

    A clerk still links a customer explicitly — that is the Decision tab's own
    search and its `Linked ✓` — through `link_customer` below.
    """
    raise NotImplementedError(
        "BR-CUS-089: the evidence exists on this row since 2026-09-15 (name, "
        "date of birth, ssn, drivers_licence) and no matcher has been built "
        "over it for service requests. identity_match.recognise is the matcher "
        "for a customer; aiming it here is a wave with its own proof."
    )


# ═══════════════════════════════════════════════════════════════════════════
# SERVICES REQUESTED — the multiselect on capture step 2, and BR-CUS-1070's
# per-service start beneath it
# ═══════════════════════════════════════════════════════════════════════════
def _clean_service_start(value: Any, code: str) -> date | None:
    """One service's own requested start, or None for *the clerk gave none*.

    NULL is a real answer here and is never a stand-in for the job's
    `Connection date` — see `set_services` for why the drawing settles that.
    """
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = _text(value, 40)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.serviceRequest.requestedStartNotADate",
            params={"service": code, "value": text},
            field_errors=[{"field": "services", "code": errors.VAL_FORMAT}],
        ) from None


def _clean_service_entries(entries: Any) -> list[tuple[str, date | None]]:
    """The list `set_services` takes, normalised to `(code, start)` pairs.

    **Two shapes are accepted on purpose.** A bare `"electric"` is what every
    caller sent until 2026-09-15 and means *this service, no date given*; an
    object `{"code": …, "requested_start": …}` is BR-CUS-1070's per-service
    start. Keeping the flat list costs one branch here and means the guest
    portal, the sample seeder and every stored payload keep working — versioning
    the endpoint would have moved every caller for a widening that takes nothing
    away.

    ⚠ **A REPEATED CODE IS REFUSED HERE RATHER THAN BY THE DATABASE.**
    `ux_sr_services_request_service` is UNIQUE on (request, service), so a
    repeat used to surface as an `IntegrityError` — a 500 with no sentence a
    clerk could read. A list of objects makes a repeat far easier to send than a
    list of bare codes did, so the guard moves in front of the constraint.
    """
    cleaned: list[tuple[str, date | None]] = []
    seen: set[str] = set()
    for entry in entries or []:
        if isinstance(entry, dict):
            code = _text(entry.get("code"), 40)
            start = _clean_service_start(entry.get("requested_start"), code or "")
        else:
            code = _text(entry, 40)
            start = None
        if not code:
            continue
        if code in seen:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="customers.serviceRequest.serviceRepeated",
                params={"service": code},
                field_errors=[{"field": "services", "code": errors.VAL_UNKNOWN_LOOKUP}],
            )
        seen.add(code)
        cleaned.append((code, start))
    return cleaned


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def set_services(actor: Any, request_id: Any, service_codes: Any) -> list[str]:
    """Replace the requested-service set, **each service carrying its own start**.

    `available` stays NULL on every new row: REQ-03.3's CHECK callout says *"we
    cannot confirm which of the requested services are available. That is
    settled at review."* — so *not yet asked* is stored as NULL and is never
    spelled the same way as *no*.

    ✅ **BR-CUS-1070, 2026-09-15 — `requested_start` IS THE CLERK'S, PER
    SERVICE, AND NO LONGER A COPY OF THE JOB'S `Connection date`.** This
    function used to create every row with
    `requested_start=request.requested_start`, which meant a clerk could never
    give two services different dates: the column existed, was written, and was
    not theirs to set.

    ⚠ **THE COPY IS GONE IN BOTH DIRECTIONS AND THE DRAWING IS WHY — WRITTEN
    OUT HERE BECAUSE THE ONE-LINE FALLBACK IS THE OBVIOUS "SIMPLIFICATION" FOR
    WHOEVER READS THIS NEXT.** Blueprint entry 06 `p080`, the step-6 review
    block, draws two adjacent rows of ONE request: `Requested start →
    05/12/2026, all three` and `Connection date → — not given`. **No fallback
    can produce that state.** If a service's date came from the job's, three
    given dates could not sit over a blank job date; if the job's were derived
    from the services', it could not read *not given*. They are two facts, and
    `p076` says so in its own words: *"Each service carries its own start. A
    block that needs electric on the 12th and sewer a fortnight later is one
    request and not two."*

    ⚠ **NOTHING WAS BACKFILLED AND NOTHING WAS OWED**: counted on the demo
    tenant the day this changed, `service_requests` held 8 rows and
    `service_request_services` held **0** — `sample_data.py` never called this
    function, so the join table had never had a row in it.

    ⚠ **THE SECOND HALF OF THAT SENTENCE STOPPED BEING TRUE ON 2026-09-16
    (`DEF-CUS-5423`), AND IT IS AMENDED HERE RATHER THAN LEFT TO BE INFERRED.**
    `sample_data._drive_cr030_request` now calls this at capture step 2, so a
    freshly seeded tenant carries **12 service rows across 7 of its 8 sample
    requests** — one of them asking for electric and water a fortnight apart,
    which is the case `p076` argues for and the only one that proves this
    column is a clerk's answer rather than a copy. **The backfill statement
    still stands**: nothing was written over the rows that already existed, and
    the demo tenant planted before that date still holds none.
    """
    from apps.tenancy import models as tenancy_models

    entries = _clean_service_entries(service_codes)
    codes = [code for code, _ in entries]
    known = {s.code: s for s in tenancy_models.Service.objects.filter(code__in=codes)}
    missing = [c for c in codes if c not in known]
    if missing:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.serviceUnknown",
            params={"service": missing[0]},
        )
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        _refuse_unless_editable(request)  # DEF-CUS-6427
        before = list(
            models.ServiceRequestService.objects.filter(request=request).values_list(
                "service__code", flat=True
            )
        )
        models.ServiceRequestService.objects.filter(request=request).delete()
        for code, start in entries:
            models.ServiceRequestService.objects.create(
                tenant_id=request.tenant_id,
                request=request,
                service=known[code],
                requested_start=start,
            )
        _audit(
            actor,
            "service_request.services_set",
            request.id,
            before={"services": sorted(before)},
            # The DATES are in the audit as well as the codes, because the whole
            # point of BR-CUS-1070 is that they are the clerk's own answer and a
            # record of *which services* no longer says what changed.
            after={
                "services": sorted(codes),
                "requested_start": {
                    code: (start.isoformat() if start else None) for code, start in entries
                },
            },
        )
    return codes


# ═══════════════════════════════════════════════════════════════════════════
# THE ADDRESS RESOLVER — EVIDENCE, never a decision
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def resolve_address(actor: Any, request_id: Any) -> rules.Evidence:
    """`Resolved to` · `Consequence` · `What the address lookup found`.

    B19 §4 is the reconciliation this function implements: B18 §6.4 proposed
    *"the system classifies"*, CR-031 ruled *"the clerk decides"*, and the
    screens show **both, doing different jobs** — the system RESOLVES the
    address and the clerk DECIDES the outcome afterwards. *"The resolution is
    evidence, the decision is a judgment."*

    So this writes `resolution_kind`, `lookup_found` and the resolved ids, and
    **writes no outcome**. BR-CUS-071 as worded (*vacant unit → move-in ·
    nothing → new connection · live account → refused*) is not implemented and
    is not a rule (CR-031 §4: it is a §6.4 proposal, not in the business-rule
    register).

    `address_as_given` is untouched — BR-CUS-070 — and that is the whole reason
    the resolved ids are separate columns.
    """
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        reference = request.address_unit_as_given or request.address_as_given
        unit_id = seams.unit_id_for_reference(reference) if reference else None
        if unit_id is None and request.address_as_given:
            unit_id = seams.unit_id_for_reference(request.address_as_given)

        # ⚠ **A FRESH RUN MAY NOT WIPE A CLERK'S PICK — CR-094 lane E, PO ruling
        # 2026-09-15.** This resolver matches on UNITS only
        # (`unit_id_for_reference`), so it answers *no premise record* for
        # `500 Main St` — a real property with 31 units on it — the moment the
        # applicant named no unit. Before the ruling that was merely a weak
        # match; now that a clerk PICKS the row, re-running this over a picked
        # request would replace `P-00053` with *"This address is not on record"*
        # and raise `no_premise_flag`, which opens the add-a-premises path over
        # a building that exists. Nothing is written and the STORED evidence is
        # returned, so the clerk's answer is what survives. A run that would
        # find MORE is not blocked — only the downgrade is.
        if unit_id is None and request.resolved_premises_id:
            return evidence_for(request)

        evidence = _evidence_for(request, unit_id)
        request.resolution_kind = evidence.resolution_kind
        request.lookup_found = evidence.lookup_found
        request.resolved_unit_id = unit_id
        request.resolved_premises_id = _premises_of(unit_id)
        request.no_premise_flag = evidence.resolution_kind == _SR.RESOLUTION_NO_PREMISE
        request.resolved_at = timezone.now()
        request.save()
        _event(
            request,
            actor,
            kind=models.ServiceRequestEvent.KIND_SYSTEM,
            note=evidence.lookup_found,
            note_type="address_resolved",
        )
        _audit(
            actor,
            "service_request.address_resolved",
            request.id,
            after={
                "resolution_kind": evidence.resolution_kind,
                "lookup_found": evidence.lookup_found,
                "resolved_unit_id": str(unit_id) if unit_id else None,
            },
        )
    return evidence


#: The three sentences the resolver may store, as CATALOGUE KEYS. `lookup_found`
#: holds the key, not English: the sentence renders on a customer-facing-ish
#: screen and the 2026-08-19 ruling says a screen's words come from the
#: catalogue entry and from nothing else (G32/G33).
LOOKUP_NO_PREMISE = "customers.serviceRequest.lookup.noPremiseRecord"
LOOKUP_SERVED_VACANT = "customers.serviceRequest.lookup.servedAndVacant"
LOOKUP_SERVED_OCCUPIED = "customers.serviceRequest.lookup.servedAndOccupied"
#: ⊕ **A FOURTH, 2026-09-15** — the sentence for a building picked with no unit
#: named inside it (`_SR.RESOLUTION_PREMISE_NO_UNIT`).
LOOKUP_PREMISE_NO_UNIT = "customers.serviceRequest.lookup.premiseNoUnit"


def _unit_resolution(unit_id: Any, *, vacant: bool | None = None) -> tuple[str, str]:
    """The stored pair — kind and sentence — for a unit that EXISTS.

    ⚠ **ONE DEFINITION, TWO CALLERS, ON PURPOSE** (hard-won law 1). The pick
    (`_resolution_from_pick`) and the fuzzy resolver (`_evidence_for`) must
    write the same two values for the same unit, or a request would say
    different things about one flat depending on how the clerk got there.
    Vacancy is `BR-MET-036`'s DERIVED occupancy, asked of customers' own
    selector — it is never a column on the unit.

    `vacant` is passed in by a caller that has ALREADY asked, so this costs one
    query and not two; left out, it asks.
    """
    if vacant is None:
        from apps.customers import selectors

        vacant = selectors.active_account_for_unit(unit_id) is None
    if vacant:
        return _SR.RESOLUTION_SERVED_VACANT, LOOKUP_SERVED_VACANT
    return _SR.RESOLUTION_SERVED_OCCUPIED, LOOKUP_SERVED_OCCUPIED


def _premises_of(unit_id: Any) -> Any:
    if unit_id is None:
        return None
    unit = seams.unit_row(unit_id)
    return getattr(unit, "premises_id", None)


def _evidence_for(
    request: models.ServiceRequest, unit_id: Any, premises_id: Any = None
) -> rules.Evidence:
    """The evidence for one unit, or — since 2026-09-15 — for one BUILDING.

    ⚠ **`premise_exists` USED TO BE ANSWERED FROM THE UNIT, AND THAT WAS A
    CONFLATION THE PICK MADE VISIBLE.** Its own docstring in
    `service_request.py` reads *"A premises row exists for the address as
    given"*, and this function answered `False` whenever no UNIT resolved — so a
    clerk who picked `500 Main St` and named no flat got *there is no premises
    record here*, and `_verdict_for` reads exactly that term to decide whether a
    NEW CONNECTION is possible. It would have argued for a new connection at an
    address the clerk had just found in the register.

    The premises is taken from the caller where given (the pick) and from the
    stored column otherwise (the read-back), so `evidence_for` and
    `resolve_address` cannot disagree about one request.
    """
    from apps.customers import selectors

    if premises_id is None:
        premises_id = request.resolved_premises_id
    if unit_id is None:
        if premises_id:
            return rules.Evidence(
                resolution_kind=_SR.RESOLUTION_PREMISE_NO_UNIT,
                premise_exists=True,
                lookup_found=LOOKUP_PREMISE_NO_UNIT,
            )
        return rules.Evidence(
            resolution_kind=_SR.RESOLUTION_NO_PREMISE,
            premise_exists=False,
            lookup_found=LOOKUP_NO_PREMISE,
        )
    served = bool(seams.service_points_for(unit_id))
    occupier = selectors.active_account_for_unit(unit_id)
    vacant = occupier is None
    holds_here = False
    if occupier is not None and request.matched_customer_id is not None:
        holds_here = _customer_holds_account(request.matched_customer_id, occupier.get("id"))
    kind, found = _unit_resolution(unit_id, vacant=vacant)
    return rules.Evidence(
        resolution_kind=kind,
        premise_exists=True,
        unit_is_served=served,
        unit_is_vacant=vacant,
        applicant_holds_account_here=holds_here,
        applicant_holds_live_account_anywhere=_customer_holds_any_live_account(
            request.matched_customer_id
        ),
        lookup_found=found,
    )


def customer_account_ids(customer_id: Any) -> list[str]:
    """Every account this customer is linked to — the set the arrears condition
    asks the ledger about. PUBLISHED (not underscore-private) because the read
    model next door is a legitimate caller, and a private name reached across a
    module boundary is a contract nobody agreed to."""
    if customer_id is None:
        return []
    return [
        str(v)
        for v in models.CustomerAccount.objects.filter(
            tenant_id=_tenant_id(), customer_id=customer_id
        ).values_list("account_id", flat=True)
    ]


def _customer_holds_account(customer_id: Any, account_id: Any) -> bool:
    return account_id is not None and str(account_id) in set(customer_account_ids(customer_id))


def _customer_holds_any_live_account(customer_id: Any) -> bool:
    """A live account ANYWHERE — what a transfer moves (*"A transfer moves a
    live account between two of your addresses"*).

    "Live" keys off the status BEHAVIOUR CLASS, never its label, exactly as
    `occupying_accounts_for_unit` does — BR-CUS-055: *"billing keys off the
    CLASS"*, so a tenant renaming a status does not move this boundary.
    """
    from apps.customers import services as customer_services

    ids = customer_account_ids(customer_id)
    if not ids:
        return False
    return models.Account.objects.filter(
        tenant_id=_tenant_id(),
        id__in=ids,
        closed_at__isnull=True,
        status__behavior_class__in=customer_services.OCCUPYING_BEHAVIOR_CLASSES,
    ).exists()


def evidence_for(request: models.ServiceRequest) -> rules.Evidence:
    """Read back the EVIDENCE AS STORED, without re-resolving.

    Deliberately not a fresh lookup: `lookup_found` is stored on the request
    (B19 §7) precisely so the sentence a clerk decided on survives the premises
    being created the next day. Fresh facts are what `resolve_address` is for.
    """
    if request.resolution_kind == _SR.RESOLUTION_UNRESOLVED:
        return rules.Evidence(lookup_found=None)
    return _evidence_for(request, request.resolved_unit_id)


# ═══════════════════════════════════════════════════════════════════════════
# THE CUSTOMER LINK — the clerk's, never the system's
# ═══════════════════════════════════════════════════════════════════════════
MATCH_TIERS = ("strong", "probable", "weak")


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def link_customer(
    actor: Any,
    request_id: Any,
    *,
    customer_id: Any = None,
    tier: str | None = None,
    basis: str | None = None,
) -> models.ServiceRequest:
    """The Decision tab's `Existing customer` search and its `Linked ✓`.

    `customer_id=None` records **"searched, and there is no prior customer"** —
    which is a real answer and not an omission. It is what makes the arrears
    condition clearable for a genuine first-time applicant: the condition asks
    *has anybody looked*, and a search that found nothing is somebody having
    looked (`match_confirmed_at` is what carries that fact).

    ⚠ `tier` is the clerk's, not ours. BR-CUS-089 lets only a `strong` match
    move money, and there is no automatic matcher here (see
    `suggest_customer_matches` — DEF-632 / DEF-638).
    """
    if tier is not None and tier not in MATCH_TIERS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.matchTierUnknown",
            params={"value": str(tier)},
        )
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        customer = None
        if customer_id is not None:
            customer = models.Customer.objects.filter(
                tenant_id=request.tenant_id, id=customer_id
            ).first()
            if customer is None:
                raise errors.deny_as_not_found("BR-TEN-003")
            if tier is None:
                raise errors.ValidationError(
                    errors.VAL_REQUIRED,
                    message_key="customers.serviceRequest.matchTierRequired",
                    params={},
                )
        before = {
            "matched_customer": str(request.matched_customer_id or "") or None,
            "match_tier": request.match_tier,
        }
        request.matched_customer = customer
        request.match_tier = tier if customer is not None else None
        request.match_basis = _text(basis, 400)
        request.match_confirmed_by_id = _actor_id(actor)
        request.match_confirmed_at = timezone.now()
        request.save()
        _event(
            request,
            actor,
            kind=models.ServiceRequestEvent.KIND_SYSTEM,
            note_type="customer_linked",
            note=str(customer.id) if customer else None,
        )
        _audit(
            actor,
            "service_request.customer_linked",
            request.id,
            before=before,
            after={
                "matched_customer": str(customer.id) if customer else None,
                "match_tier": request.match_tier,
                "match_basis": request.match_basis,
            },
        )
    return request


# ═══════════════════════════════════════════════════════════════════════════
# DOCUMENTS — two gates
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def attach_document(
    actor: Any,
    request_id: Any,
    *,
    doc_type: str,
    name: str | None = None,
    storage_ref: str | None = None,
    size: int | None = None,
    what_it_proves: str | None = None,
    document_number: str | None = None,
    required: bool = False,
) -> models.ServiceRequestDocument:
    """**GATE ONE: attaching never blocks CREATION.** REQ-03.4's `NOT BLOCKING`
    callout, verbatim: *"A missing document does not stop the request being
    created. It is verified at review, and the request shows as waiting on
    documents until then."*

    Lands `not_checked`, always. A file is not a verification (the detail's own
    `BLOCKING` callout: *"attaching a file is not the same as verifying it"*).

    `required` on THIS row means *a clerk marked this attachment required on this
    request*. The tenant-wide rule is the BR-CUS-095 checklist below
    (`set_document_requirement`), which ships entirely unticked; the two are
    different facts and both feed the same approval gate.

    ⚠ **`doc_type` IS A CLOSED VOCABULARY SINCE BR-CUS-095, and it has to be.**
    The checklist says *"for each request type, tick which documents are
    required"*, and a tick can only be satisfied if the thing attached carries
    the same name as the thing ticked. Free text would let a utility require
    `proof_of_identity` while every clerk attaches `photo_id`, and the request
    would sit blocked with the document sitting on it. The eight designed types
    are `ServiceRequestDocument.DESIGNED_DOC_TYPES`, plus the ninth value B19 §5
    draws — `other`, badged *Optional · "Whatever the applicant brought that
    helps"* — which is attachable and can never be ticked.
    """
    doc_type_code = _text(doc_type, 120) or ""
    if doc_type_code not in models.ServiceRequestDocument.ATTACHABLE_DOC_TYPES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.documentTypeUnknown",
            params={"value": doc_type_code},
        )
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        document = models.ServiceRequestDocument.objects.create(
            tenant_id=request.tenant_id,
            request=request,
            doc_type=doc_type_code,
            what_it_proves=_text(what_it_proves, 300),
            # ⚠ **KEPT WHOLE AND SHOWN AS FOUR** — PO ruling 2026-09-22. The
            # clerk may have to read it back to a customer, so it is stored; no
            # read path serves more than its last four (`BR-CUS-092(c)`).
            document_number=_text(document_number, 120),
            name=_text(name, 300),
            storage_ref=_text(storage_ref, 500),
            size=size,
            uploaded_by_id=_actor_id(actor) if storage_ref else None,
            uploaded_at=timezone.now() if storage_ref else None,
            required_flag=bool(required),
            verification_state=models.ServiceRequestDocument.NOT_CHECKED,
        )
        _audit(
            actor,
            "service_request.document_attached",
            request.id,
            after={"document_id": str(document.id), "doc_type": document.doc_type},
        )
    return document


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def verify_document(actor: Any, document_id: Any) -> models.ServiceRequestDocument:
    """**GATE TWO: verifying is what unblocks APPROVAL.** A document with no
    file cannot be verified — that would be a clerk certifying nothing."""
    with transaction.atomic():
        document = _document_row(document_id, lock=True)
        if not document.storage_ref:
            _refuse(
                errors.BIZ_COMPLETENESS,
                "customers.serviceRequest.documentHasNoFile",
                br_ref="CR-031",
                doc_type=document.doc_type,
            )
        before = {"verification_state": document.verification_state}
        document.verification_state = models.ServiceRequestDocument.VERIFIED
        document.verified_by_id = _actor_id(actor)
        document.verified_at = timezone.now()
        document.reject_reason = None
        document.save()
        _audit(
            actor,
            "service_request.document_verified",
            document.request_id,
            before=before,
            after={"document_id": str(document.id), "verification_state": "verified"},
        )
    return document


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def reject_document(actor: Any, document_id: Any, *, reason: str) -> models.ServiceRequestDocument:
    """`Reject` on the Documents tab. A reason is required — a rejected document
    is what puts the request into `More info needed` and somebody on a phone has
    to be able to say why."""
    text = _text(reason, 500)
    if not text:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.rejectReasonRequired",
            params={},
        )
    with transaction.atomic():
        document = _document_row(document_id, lock=True)
        before = {"verification_state": document.verification_state}
        document.verification_state = models.ServiceRequestDocument.REJECTED
        document.verified_by_id = _actor_id(actor)
        document.verified_at = timezone.now()
        document.reject_reason = text
        document.save()
        _audit(
            actor,
            "service_request.document_rejected",
            document.request_id,
            before=before,
            after={"document_id": str(document.id), "reason": text},
        )
    return document


def _document_row(document_id: Any, *, lock: bool = False) -> models.ServiceRequestDocument:
    qs = models.ServiceRequestDocument.objects.filter(tenant_id=_tenant_id(), id=document_id)
    if lock:
        qs = qs.select_for_update()
    row = qs.first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


# ═══════════════════════════════════════════════════════════════════════════
# BR-CUS-095 — THE CHECKLIST. `(request_type × document_type) → required`
# ═══════════════════════════════════════════════════════════════════════════
#: The tenant's own answer to *"which of the eight are compulsory?"*, and the PO
#: answered the half only they could (2026-08-24, closing OQ-351):
#:
#:     "who decides which of those eight are compulsory? If the answer is each
#:      utility decides for itself, then Settings grows a checklist — for each
#:      request type, tick which documents are required. We ship with nothing
#:      ticked, and a utility that configures nothing blocks nothing."
#:
#: ⚠ **THERE IS NO SEED AND THERE MUST NEVER BE ONE.** Not a helpful pre-tick of
#: `proof_of_identity`, however reasonable it looks. The reason BR-CUS-095 gives
#: is a product constraint, not a preference: **the product ships with NO
#: OPINION about any jurisdiction's law**, and a product that blocks approvals
#: out of the box for a rule its customer never chose is worse than one that
#: blocks none. Reading (B), the fixed list with a tenant-editable tail, was put
#: to the PO and REJECTED.


@require_role(SYSTEM_ADMIN, br_ref="BR-SHL-025")
def set_document_requirement(
    actor: Any, *, request_type: str, doc_type: str, required: bool
) -> models.ServiceRequestDocumentRequirement:
    """Tick, or un-tick, one box on the Settings checklist. **System Admin only.**

    A tenant SETTING, not a per-request act: it changes what every future
    approval of that job type demands, which is why it sits behind the same role
    every other lookup and policy screen does (A4 / BR-SHL-025) rather than
    behind the Billing Clerk role the capture path uses.

    `required=False` is STORED rather than deleted, deliberately: the settings
    screen must be able to show a deliberate *"no"* differently from *"never
    opened"*, and `updated_by` is the record of who decided.

    ⚠ `request_type` is one of the FIVE job outcomes and `doc_type` one of the
    EIGHT designed types — not the ninth, drawn `other`. Both are refused by
    name rather than stored loosely: a checklist row nothing can satisfy is a
    request nobody can approve, and the row would look perfectly valid.
    """
    kind = _text(request_type, 60) or ""
    code = _text(doc_type, 120) or ""
    if kind not in _SR.JOB_OUTCOMES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.requestTypeUnknown",
            params={"value": kind},
        )
    if code not in models.ServiceRequestDocument.DESIGNED_DOC_TYPES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.documentTypeNotTickable",
            params={"value": code},
        )
    with transaction.atomic():
        qs = models.ServiceRequestDocumentRequirement.objects.filter(
            tenant_id=_tenant_id(), request_type=kind, doc_type=code
        )
        row = qs.select_for_update().first()
        # `None` and `False` are DIFFERENT and the audit row must keep them
        # apart: nobody ever looked, versus somebody said no.
        before = {"required": row.required if row is not None else None}
        if row is None:
            row = models.ServiceRequestDocumentRequirement.objects.create(
                tenant_id=_tenant_id(),
                request_type=kind,
                doc_type=code,
                required=bool(required),
                updated_by_id=_actor_id(actor),
            )
        else:
            row.required = bool(required)
            row.updated_by_id = _actor_id(actor)
            row.save(update_fields=["required", "updated_by", "updated_at"])
        core_audit.write_row(
            action="service_request.document_requirement_set",
            entity_type="service_request_document_requirement",
            entity_id=row.id,
            actor_user_id=_actor_id(actor),
            before=before,
            after={"request_type": kind, "doc_type": code, "required": row.required},
        )
    return row


def required_document_types(request_type: str | None) -> tuple[str, ...]:
    """The doc types this tenant TICKED for `request_type`, in designed order.

    **The shipped answer is `()` and that is the point** — *"a utility that
    configures nothing blocks nothing"*. An empty tuple is not a missing answer
    and must never be treated as one.

    `request_type=None` — a request whose outcome the clerk has not decided —
    also returns `()`, and that is not a gap either: `approve` refuses without
    an outcome before any condition is evaluated, so there is no state in which
    an undecided request could be blocked by a checklist that has not been
    selected yet.
    """
    if not request_type:
        return ()
    ticked = set(
        models.ServiceRequestDocumentRequirement.objects.filter(
            tenant_id=_tenant_id(), request_type=request_type, required=True
        ).values_list("doc_type", flat=True)
    )
    # Designed order, not insertion order: the clerk reads this list.
    return tuple(
        code for code in models.ServiceRequestDocument.DESIGNED_DOC_TYPES if code in ticked
    )


def document_requirements(request_type: str | None = None) -> list[dict[str, Any]]:
    """The whole checklist as the Settings screen renders it — every
    `(request_type × doc_type)` cell, ticked or not, whether or not a row exists.

    Served as the full grid rather than as the stored rows, because a checklist
    that only lists what somebody already touched cannot be ticked for the first
    time. An untouched cell is `required=False, configured=False`, which is how
    the screen tells *"we said no"* from *"nobody has looked"*.
    """
    kinds = (request_type,) if request_type else _SR.JOB_OUTCOMES
    stored = {
        (row.request_type, row.doc_type): row
        for row in models.ServiceRequestDocumentRequirement.objects.filter(
            tenant_id=_tenant_id(), request_type__in=kinds
        )
    }
    grid: list[dict[str, Any]] = []
    for kind in kinds:
        for code in models.ServiceRequestDocument.DESIGNED_DOC_TYPES:
            row = stored.get((kind, code))
            grid.append(
                {
                    "request_type": kind,
                    "doc_type": code,
                    "required": bool(row.required) if row else False,
                    "configured": row is not None,
                    "updated_at": row.updated_at.isoformat() if row else None,
                }
            )
    return grid


def unmet_required_documents(
    request: models.ServiceRequest, *, outcome: str | None = None
) -> tuple[str, ...]:
    """The ticked doc types this request has not both ATTACHED and VERIFIED.

    **GATE TWO, and only gate two.** BR-CUS-095 joins rather than replaces the
    behaviour half already ruled (B19 §5): *attaching never blocks CREATION; an
    unverified required document blocks APPROVAL.* Nothing in this function is
    consulted before `approve`.

    **Worked, from the ruling itself:** a utility ticks `proof_of_identity` and
    `signed_service_agreement` for `move_in` only → a move-in request submits
    and sits happily in `Under review` with neither attached, and this returns
    both, so `approve` refuses by name until each is attached AND verified. The
    same tenant's `transfer` requests tick nothing, this returns `()`, and they
    approve with no documents at all.

    ⚠ **ATTACHED IS NOT ENOUGH — a file is not a verification** (the detail's own
    `BLOCKING` callout: *"attaching a file is not the same as verifying it"*), so
    a required type satisfied by an unverified upload is still unmet.
    """
    # ⚠ `outcome` is the CONSIDERED pick and defaults to the STORED one
    # (`DEF-CUS-5427`). The checklist is keyed on the outcome, so a caller
    # asking *what would this request need if it became a move-in* has to be
    # able to say so — the Approve dialog is asking exactly that, and reading
    # the stored pick answered about an outcome the clerk had not made yet.
    ticked = required_document_types(outcome or request.outcome)
    if not ticked:
        return ()
    verified = set(
        models.ServiceRequestDocument.objects.filter(
            tenant_id=request.tenant_id,
            request=request,
            doc_type__in=ticked,
            verification_state=models.ServiceRequestDocument.VERIFIED,
        )
        .exclude(storage_ref__isnull=True)
        .exclude(storage_ref="")
        .values_list("doc_type", flat=True)
    )
    return tuple(code for code in ticked if code not in verified)


def documents_for_origin(request_id: Any) -> list[models.ServiceRequestDocument]:
    """**BR-CUS-080's third clause, and the whole of it: documents move BY
    REFERENCE, NOT BY COPY.**

    This is the read a child job (a move-in, a new connect) makes through its own
    `origin_service_request_id`. There is no `copy_documents_to(...)` in this
    module and there must not be one: *"one uploaded file stays ONE row and the
    audit trail of who supplied it survives the hand-off, where a copy would
    fork it."* BR-CUS-073's *"carry over… and are not re-uploaded"* then holds
    literally rather than approximately.
    """
    return list(
        models.ServiceRequestDocument.objects.filter(
            tenant_id=_tenant_id(), request_id=request_id
        ).order_by("created_at", "id")
    )


# ═══════════════════════════════════════════════════════════════════════════
# FEES — a QUOTE. Never the ledger, never a total to collect (DEF-637)
# ═══════════════════════════════════════════════════════════════════════════
def _catalogue_price(charge_code: str) -> dict[str, Any]:
    """The tenant's OWN live price for a charge code, or a refusal by name.

    ⚠ **THE SERVER PRICES A FEE LINE, AND THE CALLER NEVER DOES — `DEF-CUS-6416`
    (2026-09-23).** `add_fee_line` stored whatever `unit_amount` it was handed,
    so a caller could quote `CC-REQFEE` at **$0.01** against a **$25.00** catalogue
    price and every screen would have printed $0.01 as the fee. The one screen
    that calls it sends the right figure, which is exactly why nothing caught it.

    Read through `rating.selectors.charge_by_code` — the same published read
    billing prices a fee bill from (`BR-BIL-007`), so a fee line and the bill that
    later settles it cannot come to disagree about where a price comes from.

    **Refused, never guessed:** an unknown code, a deactivated one (IS-1) and
    another tenant's are one answer (HR-1); a `percent` rule has no flat price
    this door could quote, and `charge_by_code` answers `None` for its amount
    precisely so that no caller charges a number nobody computed.
    """
    read_charge = seams.resolve("rating", "charge_by_code", kind="selectors")
    charge = read_charge(str(charge_code)) if read_charge is not None else None
    if not charge or charge.get("amount") is None:
        _refuse(
            errors.BIZ_STATE,
            "customers.serviceRequest.feeCodeNotPriced",
            br_ref="BR-BIL-007",
            charge_code=str(charge_code)[:60],
        )
    return dict(charge)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def add_fee_line(
    actor: Any,
    request_id: Any,
    *,
    charge_code: str,
    unit_amount: Decimal,
    quantity: Decimal = Decimal("1"),
    basis: str | None = None,
    description: str | None = None,
    charge_code_id: Any = None,
) -> models.ServiceRequestFee:
    """REQ-03.5's `+ Add a fee` — one row of the fee table.

    A MONEY ACTION: it writes `audit_log` (hard rule 7). It writes **no journal
    line and no invoice** — B18 §4.6.

    ✅ **THE PRICE IS THE CATALOGUE'S, READ AT THE MOMENT OF THE ADD, AND IT IS
    LOCKED ON THE LINE FROM THEN ON (`DEF-CUS-6416`).** `unit_amount` is the
    figure the caller SHOWED the clerk; it must equal the charge code's live
    price or the Add is REFUSED by name (`feePriceMoved`), never silently
    corrected — a refusal tells a stale screen the price moved, where a quiet
    correction would put a figure on the request that nobody saw. **Worked:**
    `CC-REQFEE` at $25.0000 in the catalogue, posted at $0.01 → refused; posted
    at $25.00 → a line of $25.0000. If the utility then raises `CC-REQFEE` to
    $30.00, this line stays $25.0000 and the request still owes $25.00: `quoted`
    sums the LINES (`fee_total_to_collect`) and nothing reads the catalogue again.

    `charge_code_id` and, where the caller gave none, `description` are the
    catalogue's too — the caller's id is not trusted to name the row it priced.

    `amount = quantity × unit_amount`, quantised to four places, `Decimal`
    throughout and never float (CLAUDE.md rule 2). Display rounds to two;
    nothing here does.
    """
    qty = Decimal(str(quantity))
    offered = Decimal(str(unit_amount))
    if offered < 0 or qty <= 0:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="customers.serviceRequest.feeAmountInvalid",
            params={},
        )
    charge = _catalogue_price(charge_code)
    price = Decimal(str(charge["amount"]))
    if offered != price:
        # ⚠ BOTH FIGURES AT FOUR PLACES — the precision hard rule 2 writes money
        # in — so the sentence never puts `0.0100` beside `25.000000`.
        _refuse(
            errors.BIZ_STATE,
            "customers.serviceRequest.feePriceMoved",
            br_ref="BR-BIL-007",
            charge_code=str(charge["code"]),
            offered=str(offered.quantize(AMOUNT_QUANTUM)),
            current=str(price.quantize(AMOUNT_QUANTUM)),
        )
    return _write_fee_line(
        actor,
        request_id,
        charge,
        price=price,
        quantity=qty,
        basis=basis,
        description=description,
        charge_code=charge_code,
        charge_code_id=charge_code_id,
    )


def _write_fee_line(
    actor: Any,
    request_id: Any,
    charge: dict[str, Any],
    *,
    price: Decimal,
    quantity: Decimal,
    basis: str | None,
    description: str | None,
    charge_code: str,
    charge_code_id: Any = None,
) -> models.ServiceRequestFee:
    """The row `add_fee_line` and `add_application_fee_line` both write, at the
    price the CATALOGUE gave them — one body, so the two doors cannot come to
    write a fee line two ways. Not role-guarded: both callers are."""
    qty = quantity
    amount_in = price
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        # ⚠ **ONE MORE THAN THE HIGHEST, NOT ONE MORE THAN THE COUNT.** A
        # draft's line can now be REMOVED (`remove_fee_line`, OQ-357 closed
        # 2026-09-23 as "both"), and after lines 1 and 2 lose line 1 a count
        # says the next is 2 — which `ux_sr_fees_request_line` refuses, because
        # line 2 is still standing. A removed line in the MIDDLE leaves a gap;
        # a removed LAST line's number can be taken again, which is harmless:
        # the removal's audit row names the code and the amount, not only the
        # number.
        line_no = (
            models.ServiceRequestFee.objects.filter(request=request)
            .order_by("-line_no")
            .values_list("line_no", flat=True)
            .first()
            or 0
        ) + 1
        amount = (qty * amount_in).quantize(AMOUNT_QUANTUM)
        fee = models.ServiceRequestFee.objects.create(
            tenant_id=request.tenant_id,
            request=request,
            line_no=line_no,
            charge_code_id=charge.get("id") or charge_code_id,
            charge_code=_text(charge.get("code") or charge_code, 60) or "",
            description=_text(description, 300) or _text(charge.get("name"), 300),
            basis=_text(basis, 60),
            quantity=qty.quantize(AMOUNT_QUANTUM),
            unit_amount=amount_in.quantize(AMOUNT_QUANTUM),
            amount=amount,
            currency=_currency(),
        )
        _audit(
            actor,
            "service_request.fee_quoted",
            request.id,
            after={
                "line_no": line_no,
                "charge_code": fee.charge_code,
                "amount": str(fee.amount),
                "currency": fee.currency,
            },
        )
    return fee


def add_application_fee_line(actor: Any, request_id: Any) -> models.ServiceRequestFee | None:
    """🔒 HUMAN-REVIEW-PENDING — `DEF-CUS-9819`, PO rulings 2026-10-06.

    PO, verbatim: *"Should the application fee be added to every request
    automatically? I recommend (a)."* — (a) read *"Every new request, from the
    portal or the counter, gets the utility's application fee line
    automatically at its current price: $10.00 for Ann Arbor, $0.00 for a
    utility that charges nothing. The clerk then takes it or waives it."* And
    before it, *"No - we wil ahve application fees as zero and pprovide option
    to waive off"*: there is no setting, a utility without a fee prices its
    code at $0.00.

    So: the code the utility marked *Application fee* (`rating.selectors.
    application_fee_charge`) is added as ONE line, quantity 1, at the price the
    catalogue gives NOW — the same read and the same lock `add_fee_line` uses
    (`DEF-CUS-6416`), through the same row writer. **Worked:** `APP-FEE` at
    $10.0000 → a line of $10.0000 on Kyle Mark's portal request; at $0.0000 →
    a line of $0.0000, which owes nothing and does not block approval
    (`service_request.fee_condition` reads `outstanding > 0`).

    **NEVER A REFUSAL.** No code marked, or a marked code that cannot be priced
    flat today (retired, percent, per-case) → nothing is added and the request
    is created exactly as before; the clerk's picker still works. **ONCE:** a
    request that already holds a line for the code gets no second one.

    NOT role-guarded on purpose: it is called from inside `create_request`
    (which is) and `create_from_portal` (the guest door, whose actor carries no
    role — see `_PortalReporter`). It is not routed by any endpoint.
    """
    read = seams.resolve("rating", "application_fee_charge", kind="selectors")
    charge = read() if read is not None else None
    if not charge or charge.get("amount") is None:
        return None
    code = str(charge["code"])
    if models.ServiceRequestFee.objects.filter(
        tenant_id=_tenant_id(), request_id=request_id, charge_code=code
    ).exists():
        return None
    return _write_fee_line(
        actor,
        request_id,
        charge,
        price=Decimal(str(charge["amount"])),
        quantity=Decimal("1"),
        basis=None,
        description=None,
        charge_code=code,
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def waive_fee_line(actor: Any, fee_id: Any, *, reason: str) -> models.ServiceRequestFee:
    """`Waive the fee` — REQ-03.5, verbatim: **"A reason is required and
    recorded against your name."** Both halves are enforced here: no reason, no
    waiver, and `waived_by` is the acting user rather than a flag.

    A waived line stops being an outstanding fee for the approval condition —
    which is the only thing a waiver has to change, because nothing was posted.
    """
    text = _text(reason, 500)
    if not text:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.waiveReasonRequired",
            params={},
        )
    with transaction.atomic():
        fee = _fee_row(fee_id, lock=True)
        if fee.settled_at is not None:
            _refuse(
                errors.BIZ_STATE,
                "customers.serviceRequest.feeAlreadySettled",
                br_ref="B18 §4.6",
                charge_code=fee.charge_code,
            )
        before = {"waived": fee.waived, "amount": str(fee.amount)}
        fee.waived = True
        fee.waive_reason = text
        fee.waived_by_id = _actor_id(actor)
        fee.waived_at = timezone.now()
        fee.save()
        _audit(
            actor,
            "service_request.fee_waived",
            fee.request_id,
            before=before,
            after={
                "line_no": fee.line_no,
                "charge_code": fee.charge_code,
                "amount": str(fee.amount),
                "reason": text,
            },
        )
    return fee


def _fee_row(fee_id: Any, *, lock: bool = False) -> models.ServiceRequestFee:
    """One fee line, tenant-scoped, addressed by PRIMARY KEY.

    ⚠ **A MALFORMED ID IS A REFUSAL, NOT A CRASH — `DEF-CUS-6096`
    (2026-09-21).** `id` is a uuid7, and Django's uuid field VALIDATES before
    it queries: hand it `"1"` and `filter()` itself raises
    `django.core.exceptions.ValidationError`, which is not one of our typed
    refusals and therefore left the API as a **500**. The screen that sent it
    swallowed the failure and changed in no way, so the clerk pressed `Waive`
    four times and the server threw four times in silence.

    The screen's half of that defect is fixed where it belongs — the payload
    now serves `id` and the row action sends it. **This half is the second line
    of defence and it is deliberate:** any caller that addresses a row with
    something that is not an id gets the same answer as one that addresses a
    row belonging to another tenant, which is a 404 (`HR-1` — the boundary must
    not confirm what exists). A 500 tells a clerk nothing and tells an operator
    the product is broken; a 404 is the truth, and it is the truth in a shape
    every screen in this product already knows how to render.
    """
    try:
        qs = models.ServiceRequestFee.objects.filter(tenant_id=_tenant_id(), id=fee_id)
        if lock:
            qs = qs.select_for_update()
        row = qs.first()
    except (DjangoValidationError, ValueError, TypeError):
        raise errors.deny_as_not_found("BR-TEN-003") from None
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _currency() -> str:
    code = seams.tenant_currency()
    if not code or len(code) != 3:
        raise errors.SysError(
            errors.SYS_INTERNAL, message_key="customers.account.tenant_currency_missing"
        )
    return code


def outstanding_fee_lines(request_id: Any) -> int:
    """How many quote lines are neither settled nor waived.

    Kept beside `fee_total_to_collect` rather than replaced by it: the count
    answers *are there unsettled lines at all*, which stays true for a legacy
    request that carries lines and no collection record. `fee_condition` uses
    the FIGURE where one exists and falls back to this count where it does not,
    because *unknown* may never be spelled the same way as *paid*."""
    return models.ServiceRequestFee.objects.filter(
        tenant_id=_tenant_id(), request_id=request_id, waived=False, settled_at__isnull=True
    ).count()


def quote_lines_for_request(request_id: Any) -> list[dict[str, Any]]:
    """The UNWAIVED quote lines of a request, for whoever raises the invoice.

    ⚠ **ADDED 2026-09-16 (`CR-109`) SO THAT A BUILD'S QUOTE CAN REACH A BOOK.**
    `ServiceRequestFee` has carried `invoice_ref`, `settled_at` and
    `settlement_ref` since it was created, above the note *"Set by whatever
    raises the invoice — NOT by this module"*. Nothing ever raised one, so the
    columns sat empty and `metering.connections.commit_connection` recorded a
    build's total on the connection and posted it nowhere. This is the READ half
    of the door that closes that.

    **WAIVED LINES ARE EXCLUDED, and that is the same filter `fee_total_to_
    collect` and `unsettled_fee_line_count` already use.** A waiver is a decision
    that the customer does not owe the line, taken by a named person with a
    recorded reason (`waive_fee_line`); billing it anyway would overturn that
    decision silently. Excluded here rather than at the caller, so the three
    readers of this table cannot come to disagree about what *waived* means.

    **ALREADY-INVOICED LINES ARE EXCLUDED TOO.** A line whose `invoice_ref` is
    set has been raised once, and hard rule 4 makes an issued invoice immutable —
    so raising it again would be a second debt for one charge rather than a
    correction. A caller that gets an empty list has nothing left to raise.

    ⚠ **`unit_amount` IS RETURNED AND IT IS NOT FOR BILLING WITH.** It is the
    price the customer was QUOTED, and `add_fee_line` takes that figure as a
    caller-supplied argument, so it is a free-typed amount in the sense
    `BR-BIL-020` forbids on any bill. Billing prices from the tenant's own
    charge-code catalogue and uses this only to CHECK the two agree — see
    `OQ-BIL-12376`. It is returned so that check is possible, never so a bill can
    be built from it.

    Read-only, tenant-scoped (hard rule 1), and it writes nothing.
    """
    rows = (
        models.ServiceRequestFee.objects.filter(
            tenant_id=_tenant_id(),
            request_id=request_id,
            waived=False,
            invoice_ref__isnull=True,
        )
        .order_by("line_no")
        .values(
            "id",
            "line_no",
            "charge_code",
            "charge_code_id",
            "description",
            "basis",
            "quantity",
            "unit_amount",
            "amount",
            "currency",
        )
    )
    return [dict(row) for row in rows]


def mark_quote_lines_invoiced(
    actor: Any,
    request_id: Any,
    *,
    invoice_ref: str,
) -> int:
    """Stamp `invoice_ref` on the quote lines an invoice has just raised.

    The WRITE half of `quote_lines_for_request`, and it lives here for the
    reason `close_if_field_work_done` does: `service_request_fees` is
    **customers'** table, cross-module writes are forbidden (B2 §2), and a
    caller in billing or metering reaching for the ORM would skip the tenant
    scope and the audit row.

    ⚠ **IT STAMPS `invoice_ref` AND NOTHING ELSE. RAISING IS NOT SETTLING.**
    `settled_at` and `settlement_ref` mean the customer has PAID, and an invoice
    that has just been issued is a debt rather than a payment —
    `fee_total_to_collect` subtracts `settled` from `quoted`, so stamping it
    here would report a build's charges as already collected the moment they
    were raised, and the developer's outstanding balance would read $0.00 while
    they owed $3,030.00.

    **A MONEY ACTION: it writes `audit_log`** (hard rule 7). The count is
    returned so a caller can state how many lines it raised rather than assume.

    Idempotent by construction: the filter excludes anything already stamped, so
    a replayed commit updates nothing and returns 0.
    """
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        rows = list(
            models.ServiceRequestFee.objects.filter(
                tenant_id=request.tenant_id,
                request_id=request.id,
                waived=False,
                invoice_ref__isnull=True,
            ).order_by("line_no")
        )
        if not rows:
            return 0
        stamped = models.ServiceRequestFee.objects.filter(
            id__in=[row.id for row in rows]
        ).update(invoice_ref=_text(invoice_ref, 120))
        _audit(
            actor,
            "service_request.fees_invoiced",
            request.id,
            after={
                "invoice_ref": _text(invoice_ref, 120),
                "lines": [
                    {
                        "line_no": row.line_no,
                        "charge_code": row.charge_code,
                        "amount": str(row.amount),
                    }
                    for row in rows
                ],
            },
        )
    return stamped


def fee_total_to_collect(request_id: Any) -> dict[str, Any]:
    """**BR-CUS-090 (CONFIRMED, PO 2026-08-24), closing DEF-637: the QUOTE, what
    was TAKEN, and the difference.**

    This function refused to exist yesterday, and the reason was real: REQ-03.5
    totals three lines to **$130.00** (`CC-REQFEE` $25.00 + `CC-EXPED` $60.00 +
    `CC-METERT` $45.00) while the confirmation's `Form fee` panel reads **$25.00
    · Cash · Receipt RCP-26-4471** for the same payment. No lane could pick one
    without silently deciding what a clerk reads out to somebody holding cash.

    **The PO did not pick either. Both screens were right about their own
    half**, verbatim: *"we acept it and in finance we will reconcile ; here
    segregation of responsibilitys, accept it and mark it as cash"*. So:

        quoted      Σ of the fee LINES that are not waived — the quote
        settled     Σ of those lines an INVOICE has settled (`settled_at`)
        collected   what the COUNTER took (`fee_collected`), receipt and all
        outstanding quoted − settled − collected — the open fee balance

    **Worked, on the screen that raised the defect:** quoted **$130.0000**,
    settled $0, collected **$25.0000**, receipt `RCP-26-4471` → outstanding
    **$105.0000**, which the review step reads (`fee_condition`) and which the
    request shows as *"$25.00 collected of $130.00 quoted · $105.00
    outstanding"*.

    ⚠ **`outstanding` IS SIGNED, and is not clamped at zero.** If a counter took
    more than the quote, that is finance's to reconcile too and hiding it would
    be the same silence in the other direction. The approval condition blocks on
    `> 0` only.

    Money is `Decimal` at four places throughout with the tenant's `CHAR(3)`
    currency beside it (CLAUDE.md rule 2); rounding to two happens at display,
    in the read model, and never here. **Nothing in this function posts to the
    ledger or issues an invoice** (B18 §4.6, hard rules 4 and 5) — it reads.
    """
    rows = list(
        models.ServiceRequestFee.objects.filter(tenant_id=_tenant_id(), request_id=request_id)
    )
    request = request_row(request_id)
    quoted = sum((f.amount for f in rows if not f.waived), Decimal("0")).quantize(AMOUNT_QUANTUM)
    settled = sum(
        (f.amount for f in rows if not f.waived and f.settled_at is not None), Decimal("0")
    ).quantize(AMOUNT_QUANTUM)
    collected = Decimal(request.fee_collected or "0").quantize(AMOUNT_QUANTUM)
    currency = request.fee_currency or (rows[0].currency if rows else None)
    return {
        "quoted": quoted,
        "settled": settled,
        "collected": collected,
        "outstanding": (quoted - settled - collected).quantize(AMOUNT_QUANTUM),
        "currency": currency,
        "method": request.fee_method,
        "receipt_no": request.fee_receipt_no,
        "collected_at": request.fee_collected_at,
        # The snapshot the clerk was holding a receipt AGAINST, which is not the
        # live quote if a line was added afterwards. Both are served; neither
        # overwrites the other.
        "quoted_at_collection": (
            Decimal(request.fee_quoted).quantize(AMOUNT_QUANTUM)
            if request.fee_quoted is not None
            else None
        ),
        # ── CR-094-BRC01 lane H · PO ruling 2026-09-15 ────────────────────
        # What PAYMENTS holds against this request: the tender detail the
        # counter captured, the state of the money (`held` · `applied` ·
        # `earned`), the journal entries it made and what `2400` still holds.
        # None when no money was taken, which is most applications.
        #
        # ⚠ **IT IS SERVED FROM PAYMENTS AND NOT COPIED INTO CUSTOMERS.** The
        # card's last four, its authorisation code and the cheque's number,
        # bank and date are payments' facts (hard rule 8's reasoning, applied
        # to a tender rather than to an address): one home, and every other
        # reader walks to it.
        "counter_receipt": payments_seam.counter_receipt_for_request(request_id),
    }


def _fee_lines_for_release(request_id: Any) -> list[dict[str, Any]]:
    """The quote as payments needs it to earn against — UNWAIVED lines, in order.

    A waived line is a fee nobody paid (BR-CUS-073), so it earns nothing and is
    not sent. A settled line has already been invoiced and posted by billing;
    sending it would earn the same money twice, which is why `settled_at` is
    filtered here rather than left for the far side to notice.

    Customers names the CODE and never the account: which account a code earns
    into is `rating.charges.gl_account_id`, and payments reads it (BR-BIL-010).
    """
    return [
        {
            "charge_code": fee.charge_code,
            "charge_code_id": fee.charge_code_id,
            "amount": Decimal(fee.amount).quantize(AMOUNT_QUANTUM),
        }
        for fee in models.ServiceRequestFee.objects.filter(
            tenant_id=_tenant_id(), request_id=request_id, waived=False, settled_at__isnull=True
        ).order_by("line_no")
    ]


def normalised_fee_method(method: Any) -> str:
    """The tender as this product spells it — **`check`, never `cheque`**.

    PO ruling 2026-09-29, verbatim: *"use american english check = not
    cheque"*, given with the REQ-03 four-step drawings. It is not a label
    ruling: `cheque` was the value STORED in `service_requests.fee_method`,
    and it was the only British spelling of a tender left in the product —
    `payments` has said `check` since `BR-PAY-026`, `tenancy.PaymentMethod`
    seeds `check`, and `payments.counter_receipts.FEE_METHOD_TO_TENDER` exists
    only to bridge the two.

    ⚠ **NORMALISED AT THE WRITE DOOR AND NOWHERE ELSE**, so the column holds
    one spelling from here on while a caller that still sends the old word
    keeps working. Retiring the input outright is `DEF-CUS-3653`'s mistake —
    an absence is invisible to every check this repo has.

    PUBLISHED rather than private because the API layer needs the same answer
    for the tender-detail object's key, and a second copy of a one-line
    mapping is how two spellings come back.
    """
    spelt = _text(method, 40)
    return _SR.FEE_METHOD_ALIASES.get(spelt, spelt)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def collect_fee(
    actor: Any,
    request_id: Any,
    *,
    amount: Decimal,
    method: str,
    receipt_no: str,
    card: dict[str, Any] | None = None,
    cheque: dict[str, Any] | None = None,
    posted_on: date | None = None,
    confirmation: str | None = None,
    memo: str | None = None,
) -> dict[str, Any]:
    """**BR-CUS-090: the counter takes THE WHOLE application fee, or it is
    waived — `OQ-CUS-12624`, PO ruling 2026-09-24 (`DEF-CUS-6455`).**

    PO, verbatim: *"p4 - i already calrified this - all or waived"*, restating
    `OQ-CUS-12617` (*"either fee is paid or waived - no other condition"*).
    **`amount` must equal the fee still owing** — the quote less what an
    invoice has settled — and anything else is refused BEFORE a row is
    written, naming the figure: quoted $130.00, `amount=25.00` → refused,
    *"Take the full $130.00. Or waive it."*
    (`customers.serviceRequest.feeTakeInFull`, params `amount` stored at four
    places and `currency`). The way out of a fee the customer will not pay in
    full is BR-CUS-073's waiver, an explicit act with a reason on a LINE
    (`waive_fee_line`) — never a short payment.

    ⛔ **SUPERSEDED 2026-09-24 — the desk clause this docstring used to open
    with:** *"A SHORTFALL IS NOT REFUSED. THAT IS THE WHOLE RULING"*, on the
    PO's 2026-08-24 *"we acept it and in finance we will reconcile"*. Read by
    date, *"all or waived"* supersedes it for application fees, because a short
    payment is the only road to a part-paid fee and a part-paid fee is the one
    state that ruling excludes. **A more-than-owed amount is refused by the same
    check** — *"all"* is the fee, not more than it; that reading is recorded in
    the decision log of 2026-09-24. **Requests part-paid before this ruling
    keep what was taken**: the second collection below is still refused, so the
    rest can only be waived.

    ⚠ **THE TWO ROLES STAY SEPARATE, which is the reason the PO gave.** The
    person who takes the money records it; finance agrees it against the cash
    count. So **this never adjusts the quote to match the cash** — no line is
    written, waived or re-priced here — and nothing in finance may reach back
    into the request to change what the clerk recorded. The reconciliation is a
    finance act against both numbers, and it needs both numbers to survive.

    ⚠ **IDEMPOTENT ON THE RECEIPT NUMBER (CLAUDE.md rule 6), because the desk is
    exactly where a double-click happens.** BR-CUS-090 says ONE receipt number.
    A repeat with the SAME receipt returns the recorded collection and adds
    nothing; a second collection with a DIFFERENT receipt is refused by name
    rather than summed, because two receipts against one request is a fact this
    rule does not describe and guessing it would move money.

    ⚠ **NO RECEIPT IS ALLOCATED HERE AND NO PAYMENT ROW IS WRITTEN.** `RCP-26-4471`
    is the number the counter wrote on the slip; payments owns the `RCT-` series
    and its tables, and cross-module writes are forbidden (hard rule 5).

    ⚠ **AND IT POSTS, SINCE 2026-09-15 — THE SENTENCE THAT USED TO END THAT
    PARAGRAPH IS REVERSED BY A PO RULING AND IS NOT LEFT STANDING.** It read
    *"Nothing posts to the ledger either (B18 §4.6)"*, and the blueprint said the
    same in red on p079: *"This takes money and posts nothing. No journal line,
    no invoice, no account."* PO, shown Sarah Miller's **$25.00** against receipt
    `RCP-26-4471` and a four-row table proving it appeared in payments, in the
    ledger and on the finance screens as **nothing**: *"payemnt should show in
    payments, in ledge and in fiannce books"*.

    **HALF OF THE OLD SENTENCE SURVIVES AND IS STILL ENFORCED HERE: no invoice
    and no customer account.** There genuinely is neither at capture and nothing
    below creates one — a balanced pair needs neither.

    **WHAT IT DOES NOW, THROUGH THE SEAM AND NEVER DIRECTLY** (hard rule 5 —
    customers writes no payment row and no journal line): payments records a
    `counter_receipts` row and posts **DR the tender's clearing account, else
    `1010 Undeposited funds` · CR `2400 Customer credit balances`** for what was
    taken. Worked: $25.00 cash → `DR 1010 25.0000 · CR 2400 25.0000`, held and
    not yet earned. It is released to revenue only by a TERMINAL outcome —
    `approve` or `refuse_request` below.

    ⚠ **THE TENDER DETAIL GOES TO PAYMENTS AND IS NOT COPIED ONTO THIS ROW.**
    `card={"last4", "brand", "auth_code"}` and `cheque={"number", "bank",
    "date"}` — PO, 2026-09-15: *"we need to allow to take payment detials, card
    detial scheck details here curerntly is is not taking inputs"*. **Never the
    full card number**, which nothing in this product reads and which would put
    the whole database under card-industry rules.

    ⚠ **AND IT TAKES RECORD A PAYMENT'S THREE FACTS — `DEF-CUS-6376`, PO on
    SR-26-0016:** *"it should be similar to record payment form so pasting
    date, type of payment , memo and it will take only application fee"*.
    `posted_on` is the business day the money counts for — the collection
    entry's date — and when the caller names none it is the TENANT's today
    (BR-TEN-081), never the date of a UTC instant; `confirmation` is the
    instrument's own number; `memo` is free text. All three go to payments on
    the receipt and all three are on the audit row below. **The receipt number
    is unchanged and still required**: it is the slip THE CLERK handed back,
    and this function is idempotent on it. `method` may now be any of the
    tenant's ACTIVE payment methods (the list Record a payment offers) as well
    as the request's own `cash · card · cheque`.

    A MONEY ACTION, so it writes `audit_log` (hard rule 7) — with the quote, the
    cash, the shortfall and the receipt in one row, which is what a finance
    reconciliation will be read against.
    """
    taken = Decimal(str(amount))
    if taken < 0:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="customers.serviceRequest.feeAmountInvalid",
            params={},
        )
    taken = taken.quantize(AMOUNT_QUANTUM)
    how = normalised_fee_method(method)
    # DEF-CUS-6376 — the tenant's own list is asked of payments, which owns it.
    if how not in _SR.FEE_METHODS and not payments_seam.is_live_tender(how):
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.feeMethodUnknown",
            params={"value": str(how)},
        )
    receipt = _text(receipt_no, 120)
    if not receipt:
        # BR-CUS-090 names it: the request stores fee_quoted, fee_collected,
        # method and ONE receipt number. Cash with no receipt is cash nobody can
        # reconcile.
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.feeReceiptRequired",
            params={},
        )
    # BR-TEN-081: the tenant's day, read through the seam — never `date.today()`
    # and never `timezone.now().date()`, which is UTC's.
    posting_day = posted_on if posted_on is not None else seams.tenant_today()
    reference = _text(confirmation, 120)
    note = _text(memo, 500)
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        if request.fee_receipt_no:
            if request.fee_receipt_no == receipt:
                return fee_total_to_collect(request.id)
            _refuse(
                errors.BIZ_IDEMPOTENT,
                "customers.serviceRequest.feeAlreadyCollected",
                br_ref="BR-CUS-090",
                receipt_no=request.fee_receipt_no,
            )
        quote = fee_total_to_collect(request.id)
        # ── OQ-CUS-12624 · THE WHOLE FEE OR NOTHING (BR-CUS-090, 2026-09-24) ──
        # After the idempotent replay above (a double-click of a FULL payment
        # must still return, not be refused against an owing of $0.00) and
        # BEFORE any write: this is a Python refusal, not a failed statement,
        # so an enclosing PostgreSQL transaction stays usable (hard-won law 14,
        # proved by 10-scripts/def_cus_6455_whole_fee_pg_proof.py).
        owing = (quote["quoted"] - quote["settled"] - quote["collected"]).quantize(
            AMOUNT_QUANTUM
        )
        if taken != owing:
            _refuse(
                errors.BIZ_COMPLETENESS,
                "customers.serviceRequest.feeTakeInFull",
                br_ref="BR-CUS-090",
                amount=str(owing),
                currency=quote["currency"] or _currency(),
            )
        before = {"fee_collected": None, "fee_receipt_no": None}
        request.fee_quoted = quote["quoted"]
        request.fee_collected = taken
        request.fee_currency = quote["currency"] or _currency()
        request.fee_method = how
        request.fee_receipt_no = receipt
        request.fee_collected_at = timezone.now()
        request.fee_collected_by_id = _actor_id(actor)
        request.save(
            update_fields=[
                "fee_quoted",
                "fee_collected",
                "fee_currency",
                "fee_method",
                "fee_receipt_no",
                "fee_collected_at",
                "fee_collected_by",
                "updated_at",
            ]
        )
        outstanding = (quote["quoted"] - quote["settled"] - taken).quantize(AMOUNT_QUANTUM)
        # ── THE MONEY REACHES THE BOOKS, IN THIS TRANSACTION ──────────────
        # PO ruling 2026-09-15. Inside the atomic block on purpose, exactly as
        # `record_payment`'s posting is: the alternative — record here, post
        # afterwards, outside — produces the one state nothing can repair, a
        # money row with no entry in the books and no code path left that would
        # ever write one.
        #
        # ⚠ A REFUSAL FROM THE FAR SIDE IS NOT SWALLOWED. Money that cannot be
        # recorded must not be taken, so the clerk sees it and the whole
        # collection rolls back — including the columns above.
        payments_seam.record_counter_receipt(
            source_type=payments_seam.SOURCE_SERVICE_REQUEST,
            source_id=request.id,
            source_ref=request.request_no,
            receipt_no=receipt,
            amount=taken,
            currency=request.fee_currency,
            method_code=how,
            taken_at=request.fee_collected_at,
            taken_by_id=_actor_id(actor),
            card=card,
            cheque=cheque,
            actor=actor,
            posted_on=posting_day,
            confirmation=reference,
            memo=note,
        )
        _event(
            request,
            actor,
            kind=models.ServiceRequestEvent.KIND_SYSTEM,
            note=receipt,
            note_type=f"fee_collected:{how}",
        )
        _audit(
            actor,
            "service_request.fee_collected",
            request.id,
            before=before,
            after={
                "quoted": str(quote["quoted"]),
                "collected": str(taken),
                "outstanding": str(outstanding),
                "currency": request.fee_currency,
                "method": how,
                "receipt_no": receipt,
                # DEF-CUS-6376 — the day the books say, and the clerk's words.
                "posted_on": posting_day.isoformat(),
                "confirmation": reference,
                "memo": note,
            },
        )
    return fee_total_to_collect(request.id)


# ═══════════════════════════════════════════════════════════════════════════
# PARK AND SAVE-AND-EXIT — the PO's practicality requirement, and it is TWO
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def park(
    actor: Any,
    request_id: Any,
    *,
    waiting_on: str,
    note: str | None = None,
    remind_on: date | None = None,
) -> models.ServiceRequest:
    """`Park this — what are you waiting for?`

    CR-031 statement 9, in the requester's own words: *"all these request can
    happen in 1 go or dur to pratical cases only step will be executed in such
    case we have to give save and exit opition t utility clark."* B19 §12.2
    answers it with **two** controls, not one, and this is the louder of them:
    it records WHAT is awaited, a note and a reminder date.

    **`waiting_on` stays orthogonal to `STATE` and the register proves it:**
    `SR-26-0046` is drawn `Approved` AND waiting on a *scheduled date*, while
    `SR-26-0042` is `Under review` waiting on *a supervisor*. Two facts, two
    columns — which is why parking writes `waiting_on` / `park_note` /
    `remind_on` in EVERY state and clears nothing.

    ⚠ **AND FROM 2026-09-19 IT MOVES EXACTLY ONE STATE: `submitted` →
    `under_review`, and nothing else, ever.** The PO's ruling that day left the
    request five states and removed `pick_up` — *"not required - you map this
    state when it is submitted - dont take seperate approval / or confirmation
    - it is confusion for user"* — which would have left `under_review`
    reachable by nothing at all. **A clerk who parks a submitted request has
    self-evidently picked it up**, and the blueprint's own register draws
    `SR-26-0042` as *Under review, waiting on a supervisor*, which is precisely
    a parked request. So this is the drawing being read, not a mechanism
    invented to fill a hole.

    ⚠ **IT IS DELIBERATELY NOT IN `TRANSITIONS`.** Park is not a lifecycle
    move a clerk chooses off a list; it is a note with a side effect in one
    state. Putting it in the table would make it appear in `actions_available`
    and therefore offerable from states where it must move nothing.

    *"Everything entered stays. The request shows as waiting in the list, and
    the note goes on its timeline."* — so nothing is cleared and the note is an
    event row.
    """
    reason = _text(waiting_on, 120)
    if not reason:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.waitingOnRequired",
            params={},
        )
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        if rules.is_terminal(request.state):
            _refuse(
                errors.BIZ_STATE,
                "customers.serviceRequest.terminalNoPark",
                br_ref="CR-031",
                state=request.state,
            )
        before = {
            "waiting_on": request.waiting_on,
            "remind_on": request.remind_on,
            "state": request.state,
        }
        request.waiting_on = reason
        request.park_note = _text(note)
        request.remind_on = remind_on
        request.parked_at = timezone.now()
        request.parked_by_id = _actor_id(actor)
        # ⚠ **THE ONE STATE PARK MOVES — PO ruling 2026-09-19.** See the
        # docstring. `submitted` → `under_review` and no other pair: a parked
        # `more_info` request is still waiting on the APPLICANT, and moving it
        # would take it off the queue the applicant's answer belongs to.
        moved_from = request.state
        if request.state == rules.SUBMITTED:
            request.state = rules.UNDER_REVIEW
        request.save()
        _event(
            request,
            actor,
            kind=models.ServiceRequestEvent.KIND_NOTE,
            note=_text(note),
            note_type=f"parked:{reason}",
            # ⚠⚠ **THE MOVE GOES ON THE TIMELINE ROW, AND IT DID NOT UNTIL
            # 2026-09-19.** Park wrote a bare note because park moved nothing.
            # It moves `submitted` → `under_review` now, and a state change that
            # leaves no timeline row is a change the append-only record cannot
            # account for — the one thing this table exists to prevent.
            #
            # **It is also what the customer sees.** The portal ladder dates its
            # *we picked it up* step from events carrying a `to_state`
            # (`progress_steps`), so without this the step went `current` with
            # no date on it — true, undated, and silently so.
            #
            # `None` when nothing moved, so a parked `more_info` request writes
            # the note it always wrote and claims no move it did not make.
            from_state=moved_from if moved_from != request.state else None,
            to_state=request.state if moved_from != request.state else None,
        )
        _audit(
            actor,
            "service_request.parked",
            request.id,
            before=before,
            after={"waiting_on": reason, "remind_on": str(remind_on) if remind_on else None},
        )
    return request


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def resume(actor: Any, request_id: Any, *, note: str | None = None) -> models.ServiceRequest:
    """Clear the park — *"the oldest thing waiting is the thing to look at"*, and
    this is what takes a row off that list. The park NOTE stays on the timeline;
    only the live `waiting_on` clears, so the record of what was awaited and for
    how long survives."""
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        before = {"waiting_on": request.waiting_on}
        request.waiting_on = None
        request.park_note = None
        request.remind_on = None
        request.parked_at = None
        request.parked_by = None
        request.save()
        _event(
            request,
            actor,
            kind=models.ServiceRequestEvent.KIND_NOTE,
            note=_text(note),
            note_type="resumed",
        )
        _audit(
            actor, "service_request.resumed", request.id, before=before, after={"waiting_on": None}
        )
    return request


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def save_and_exit(actor: Any, request_id: Any, payload: Any = None) -> models.ServiceRequest:
    """`Save & exit` — B19 §12.2's **quieter** control, and a separate thing from
    `Park`.

    It saves whatever is on the form and leaves. It records no reason, sets no
    reminder and puts nothing in the `WAITING ON` column — which is exactly what
    distinguishes it: *"A request rarely settles in one sitting. Leave it and it
    keeps its place."* A timeline row is still written, because the next person
    needs to know somebody had it open.
    """
    request = update_request(actor, request_id, payload) if payload else request_row(request_id)
    _event(
        request, actor, kind=models.ServiceRequestEvent.KIND_SYSTEM, note_type="saved_and_exited"
    )
    return request


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def add_note(
    actor: Any, request_id: Any, *, note: str, note_type: str | None = None
) -> models.ServiceRequestEvent:
    """The History tab's `Add a note`, badged **`Internal · never shown to the
    customer`** — and that badge is currently the whole truth, because this
    function passes no `internal` and `_event` defaults it `True`.

    ⚠ **THE PARAGRAPH THAT USED TO BE HERE SAID *"there must not be one: the
    customer portal is out of v1 scope, so a flag saying a note is visible would
    be a permission with nothing to permit"*. IT WAS TRUE WHEN IT WAS WRITTEN
    (`CR-031`) AND STOPPED BEING TRUE ON 2026-09-04, WHEN THE PORTAL SHIPPED**
    (`DEF-CWP-3880`, corrected 2026-09-05). It is hard-won law 1 in its most
    expensive form — not a comment claiming a guarantee the code does not give,
    but a comment **forbidding work the product now needs**, which a lane
    reading this file would have obeyed.

    ⚠ **WHAT IS ACTUALLY MISSING, STATED AS A BUILD GAP AND NOT REWRITTEN AWAY.**
    `BR-CWP-078` is **CONFIRMED** and reads: *"The customer-safe request history
    shows the transitions and the notes flagged customer-visible, and hides
    internal routing comments."* The READ honours the flag today
    (`portal/seams/customers_seam._customer_visible_events`) and exactly one
    writer can raise it — `note_from_portal(customer_visible=True)`, the
    customer's own sentence on `CWP-051`. **No clerk-side writer exists**, so
    the signed rule's *"notes flagged customer-visible"* half can only ever be
    the customer's own words, and a clerk who needs two more documents cannot
    say so on the request the customer is watching.

    ⚠ **DO NOT CLOSE THIS BY WIDENING THIS SIGNATURE ALONE.** A
    `customer_visible=` parameter no screen passes is hard-won law 2 from the
    write end — the same shape as the column this defect is about. Closing it
    needs the History tab's control, its badge copy in all eleven catalogues
    (B14 rules 34 and 35), and one judgment nothing signed has made: **whether a
    Billing Clerk may publish text to a customer, or only a System Admin.**
    `BR-CWP-078` says what is SHOWN and is silent on who may flag it. That is a
    story, and it does not have one.
    """
    text = _text(note)
    if not text:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.noteRequired",
            params={},
        )
    request = request_row(request_id)
    return _event(
        request, actor, kind=models.ServiceRequestEvent.KIND_NOTE, note=text, note_type=note_type
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def transition(
    actor: Any,
    request_id: Any,
    action: str,
    *,
    reason: str | None = None,
    info_needed: Any = None,
    message_to_applicant: str | None = None,
) -> models.ServiceRequest:
    """Move one request one step. **The only door through which `state` moves.**

    Guards, in order: the action must exist, it must be lawful from the current
    state (`service_request.TRANSITIONS`), and where the screen says a reason is
    required it is required here (`REASON_REQUIRED` — refuse, manual close,
    reopen, ask-for-more, hold).

    `approve` and `refuse` have their own doors below, because approving carries
    the condition gate and refusing carries a reason code. Calling them through
    here is refused rather than silently allowed to skip those.

    ⚠ **`request_info` IS DELEGATED RATHER THAN GIVEN A SECOND DOOR
    (`DEF-CUS-5389`, 2026-09-15).** Ask-for-more grew a tick list and a message
    to the applicant, and the tempting move was a new endpoint beside `refuse`.
    That would have left the door every screen in the product already calls
    still moving the state and telling the applicant nothing — a live control
    doing quietly less than the new one, which is hard-won law 2's mirror. So
    this door gained the two fields and hands the whole act to `ask_for_more`.
    A caller that passes neither gets exactly the behaviour it got yesterday.
    """
    if action in (rules.APPROVE, rules.REFUSE):
        _refuse(
            errors.BIZ_STATE,
            "customers.serviceRequest.useDedicatedAction",
            br_ref="CR-031",
            action=action,
        )
    if action == rules.REQUEST_INFO:
        return ask_for_more(
            actor,
            request_id,
            reason=reason or "",
            info_needed=info_needed,
            message_to_applicant=message_to_applicant,
        )
    return _apply(actor, request_id, action, reason=reason)


def _apply(
    actor: Any,
    request_id: Any,
    action: str,
    *,
    reason: str | None = None,
    extra: dict[str, Any] | None = None,
    audit_action: str | None = None,
) -> models.ServiceRequest:
    text = _text(reason)
    if action in rules.REASON_REQUIRED and not text:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.reasonRequired",
            params={"action": action},
        )
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        try:
            lands_in = rules.next_state(request.state, action)
        except rules.ServiceRequestRuleError as exc:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="CR-031",
                message_key="customers.serviceRequest.transitionNotAllowed",
                params={"action": action, "state": request.state},
            ) from exc
        before = {"state": request.state}
        request.state = lands_in
        if action == rules.SUBMIT:
            request.submitted_at = timezone.now()
        if lands_in in rules.TERMINAL_STATES:
            request.closed_at = timezone.now()
        # ⚠ **THE `reopen` BRANCH THAT STOOD HERE IS DELETED — PO ruling
        # 2026-09-19.** It cleared `closed_at`, `outcome`, `reason_code`,
        # `decided_at`, `decided_by`, `refusal_reason` and the letter so a
        # reopened request stopped displaying the refusal it was under. There
        # is no reopen any more: **refuse is terminal, and a reapplication is a
        # NEW request.** p085 names `Reopen` and this is the one place the
        # state table knowingly contradicts the drawing, on the ruling.
        # `next_state` refuses the action before this line is ever reached, so
        # the branch was unreachable code holding a rule that no longer exists.
            # ⚠ ADDED 2026-09-15 with the two columns beside them
            # (`DEF-CUS-5389`). Same clause, same reason: a reopened request
            # must not go on displaying the reason it was refused for or the
            # letter that was sent, because it is UNDER REVIEW again and the
            # decision tab reads both. **Nothing is lost** — the refusal is on
            # the append-only timeline (TC-REQ-10) and the letter is on the
            # outbound queue, which is the record of what a utility sent.
            request.decision_reason = None
            request.refusal_message = None
        for key, value in (extra or {}).items():
            setattr(request, key, value)
        request.save()
        _event(
            request,
            actor,
            kind=models.ServiceRequestEvent.KIND_STATE,
            from_state=before["state"],
            to_state=lands_in,
            note=text,
        )
        _audit(
            actor,
            audit_action or f"service_request.{action}",
            request.id,
            before=before,
            after={"state": lands_in, "reason": text},
        )
    return request


# ═══════════════════════════════════════════════════════════════════════════
# CR-070 WAVE P · ROUTING AN APPROVED APPLICATION SENDS SOMEBODY (US-WRK-039)
# ═══════════════════════════════════════════════════════════════════════════


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def route(actor: Any, request_id: Any, *, template_ids: Any = None) -> dict[str, Any]:
    """`approved` → `in_fulfilment`, **and the field work that fulfils it.**

    `CR-070` §W.12: *before a new module builds a screen, find the flow that
    already owns that moment.* Routing IS that moment for a service request —
    the application is approved, somebody now has to go and build the thing —
    and until today this transition moved a word on a screen and told nobody.

    **THE JOBS ARE OFFERED, NOT AUTOMATIC** (judgment 7). `template_ids` is what
    a clerk ticked on `Work-029`'s panel; an empty list is a complete answer and
    routes the request with no jobs at all.

    ⚠ **AND THE REQUEST IS ROUTED WHETHER OR NOT THE JOBS COULD BE RAISED.**
    `BR-WRK-055`. The state moves in its own committed transaction FIRST and the
    raise happens after it, so a field module that is down, unpublished or
    refusing cannot hold an approved application in `approved` for ever. What
    comes back instead is `work_orders_not_raised` and the clerk can raise the
    job from the dispatcher.

    ⚠ **A REQUEST WITH NO RESOLVED ADDRESS RAISES NOTHING** (judgment 8).
    `resolve_address` can leave a request with no unit and no premises — one
    taken by phone for a building nobody has entered yet. Work refuses it by
    name before writing anything; this door reports that refusal and routes the
    request anyway, because the address gets resolved later and the application
    is no less approved in the meantime.
    """
    request = _apply(actor, request_id, rules.ROUTE)
    outcome = _raise_flow_work(
        actor,
        flow_kind="service_request",
        flow_id=request.id,
        template_ids=template_ids,
    )
    return {"request": request, **outcome}


def _raise_flow_work(
    actor: Any, *, flow_kind: str, flow_id: Any, template_ids: Any, orders: Any = ()
) -> dict[str, Any]:
    """**ONE FUNCTION, NOT TWO — `CR-171-BRC10` P1.19 (lane MVI-WIZ-UNIT).**

    This module carried its own copy of `services._raise_flow_work` — the same
    broad catch (`BR-WRK-055`: every failure is one fact, *the visit was not
    booked*, and none of them may fail the flow), the same sentence — but the
    copy took only `template_ids`, so a request door could never raise the
    typed rows a clerk adds on a *Field visit* table. Two copies of one posture
    is the drift that function's own docstring says it exists to prevent.

    So this NAME stays (the approve door calls it, and tests patch it here) and
    the BODY is the one in `services`. Imported at call time because
    `services` imports this module at load.
    """
    from apps.customers import services as customer_services

    return customer_services._raise_flow_work(
        actor, flow_kind=flow_kind, flow_id=flow_id, template_ids=template_ids, orders=orders
    )


def close_if_field_work_done(actor: Any, request_no: Any) -> dict[str, Any]:
    """**B19 §12.3's promise, made executable** — *"A request closes on its own
    when the job it created finishes."*

    ⚠ **EVERY JOB, NOT THE FIRST ONE, AND THAT DISTINCTION IS THE WHOLE POINT.**
    A new water connection is *Site inspection & mark-out*, *Tap and service
    line* and *Meter set* — three jobs, days apart. Closing the request when the
    inspector's report is accepted would mark the application finished before
    anybody had dug the trench, and the customer would have no service and no
    open record saying so.

    Called by metering the moment a field result is ACCEPTED (`BR-MET-110`: the
    human act between a field report and a service going live), through
    `apps/metering/seams.py` — metering never writes a `service_requests` row
    and this is the door it asks through instead.

    **A no-op is the normal answer.** A request not in fulfilment, a request
    that raised no jobs at all, or one with a job still outstanding all return
    `{"closed": False}` and change nothing.
    """
    # ⚠⚠ **THIS PROMISE WAS WITHDRAWN ON 2026-09-19 AND THE FUNCTION STAYS A
    # SAFE NO-OP RATHER THAN A RAISE.** The PO left the request five states —
    # *"once requets is approved then in move in or new connect we take all
    # those decision to in fulfill etc"* — so `complete` is a retired move and
    # `in_fulfilment` is a state nothing can put a request into any more.
    #
    # **Two different rows reach here and only one of them is obvious.** A
    # request raised since the ruling can never be `in_fulfilment`, so the
    # `not_in_fulfilment` line below already answers it. But **existing rows
    # keep their state and nothing is migrated**, so a row that was routed
    # BEFORE the ruling is still sitting in `in_fulfilment` today, and the day
    # its last field job is accepted it would reach `_apply(COMPLETE)` and
    # raise `BIZ_STATE` — an exception thrown across a module seam, into
    # metering's accept path, for a request nobody is looking at.
    #
    # So the retirement is answered HERE, as a named reason, and it is read
    # from `RETIRED_ACTIONS` rather than hardcoded — a second copy of a state
    # list is the defect `DEF-CUS-5874` records one module over.
    if rules.COMPLETE in rules.RETIRED_ACTIONS:
        return {"closed": False, "reason": "request_completion_retired"}
    if not request_no:
        return {"closed": False, "reason": "no_reference"}
    row = (
        models.ServiceRequest.objects.filter(tenant_id=_tenant_id(), request_no=request_no)
        .only("id", "state")
        .first()
    )
    if row is None or row.state != rules.IN_FULFILMENT:
        return {"closed": False, "reason": "not_in_fulfilment"}
    tally = seams.flow_work_acceptance(flow_kind="service_request", source_ref=request_no)
    if tally is None:
        # Work cannot answer, so nothing is concluded. Closing a request on an
        # unreadable tally would be the same error as closing it on the first
        # acceptance, arrived at from the other direction.
        return {"closed": False, "reason": "acceptance_unreadable"}
    if tally["total"] < 1 or tally["accepted"] < tally["total"]:
        return {
            "closed": False,
            "reason": "work_outstanding",
            "accepted": tally["accepted"],
            "total": tally["total"],
        }
    _apply(
        actor,
        row.id,
        rules.COMPLETE,
        audit_action="service_request.completed_by_field_work",
    )
    return {"closed": True, "accepted": tally["accepted"], "total": tally["total"]}


# ═══════════════════════════════════════════════════════════════════════════
# THE SUBMIT MINIMUM — where the address requirement went (PO 2026-09-20)
# ═══════════════════════════════════════════════════════════════════════════
#: PO ratification of 2026-09-20 (decision log §3, `DEF-CUS-6006`), verbatim:
#: *"this is correct"*. A DRAFT is created from the applicant's name alone —
#: nothing at all on a staff-raised channel — because `address_as_given` is
#: captured on step 3 of REQ-03 while `Save as draft` is a header action on
#: every step. **The address requirement MOVES here; it does not disappear.**
#:
#: ⚠ **THE NAME IS STILL CHANNEL-CONDITIONAL AND THAT IS NOT A LIBERTY TAKEN
#: WITH THE RULING.** The ratified table's `Submit` row reads *"applicant name
#: + address"*, and `BR-CUS-091` is a SIGNED rule saying applicant-identity
#: fields are not required on a staff-raised disconnect — *"demanding an
#: applicant name would make the clerk invent one"*. An unconditional name at
#: submit would reverse a signed rule by implication, which law 13 puts back to
#: the PO rather than assuming. So the whole old CREATE gate moves here intact,
#: and the ruling's `Submit` row is satisfied for every channel it was written
#: about. Recorded in the decision log rather than decided in this comment.
#:
#: ⚠ **IT IS CHECKED HERE AND NOT IN `_clean_capture`, BECAUSE A SUBMIT SENDS
#: NO PAYLOAD.** The values being tested are on the ROW by then — `update_
#: request` is `partial=True` and enforces no required field, so a name blanked
#: after creation is caught at exactly this gate and nowhere earlier.
SUBMIT_REQUIRED_FIELDS = ("applicant_name", "address_as_given")


def _require_submit_minimum(request: Any) -> None:
    """Refuse a submit that leaves a request about nobody or about nowhere."""
    required = SUBMIT_REQUIRED_FIELDS
    if str(getattr(request, "channel", "") or "") in _SR.STAFF_RAISED_CHANNELS:
        required = ("address_as_given",)
    for field in required:
        if not getattr(request, field, None):
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="customers.serviceRequest.fieldRequired",
                params={"field": field},
            )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def submit(actor: Any, request_id: Any) -> dict[str, Any]:
    """`draft` → `submitted`, and BR-CUS-079's acknowledgement.

    ✅ **THIS ALLOCATES NOTHING, AND SINCE BR-CUS-093 THAT IS THE ANSWER RATHER
    THAN THE GAP.** B18 §5.3.8 gave `POST …/submit` the job (*"Allocates the
    number"*) and the PO ruled otherwise on 2026-08-24: *"At creation — every
    draft is numbered"*. `create_request` does it; by the time anything reaches
    this function the row already has its identity.

    ⚠ **AND THAT IS WHY THIS IS IDEMPOTENT — consequence (e), verbatim:
    *"IDEMPOTENCY GETS SIMPLER, NOT HARDER (hard rule 6): `submit` no longer
    allocates anything, so a repeated submit is a state transition on a row that
    already has its identity — the idempotency key is the request itself."***

    So a second submit is not a refusal and not a second anything: it returns
    the request and the acknowledgement already recorded, **without a second
    state event, a second timeline row or a second acknowledgement to the
    customer.** `submitted_at` is what carries the fact, so the short-circuit
    survives the request having moved on to `under_review` — a double-click
    forty minutes late is still the same click.

    A request that was WITHDRAWN or REFUSED and is being submitted again is a
    different act and is not short-circuited here: it reaches `_apply` and is
    refused by the state machine, because `reopen` (with a reason) is the door
    B18 §5.3.3 provides for that.
    """
    existing = request_row(request_id)
    if existing.submitted_at is not None:
        return {
            "request": existing,
            "acknowledgement": {
                "state": existing.acknowledgement_state,
                "reason": existing.acknowledgement_absence_reason,
                "ref": existing.acknowledgement_ref,
                "sent": False,
                "fee_statement": fee_statement(existing),
            },
            # Named in the payload so a caller can tell "accepted" from
            # "accepted again" without diffing timestamps.
            "idempotent_replay": True,
        }
    # ⚠ **AFTER THE REPLAY SHORT-CIRCUIT, NEVER BEFORE IT.** A request that has
    # already been submitted has passed this gate once; re-testing it would turn
    # a double-click into a refusal on a row that is lawfully on its way, and
    # BR-CUS-093 consequence (e) makes the repeat a no-op by design.
    _require_submit_minimum(existing)
    # ⊕ `CR-161-BRC10` W6 — a field placed Input AND required on Staff New
    # Request must be answered before the request leaves draft. A draft may be
    # saved without it; the submit is where *required* means required.
    request_custom_fields.refuse_unless_complete(existing)
    request = _apply(actor, request_id, rules.SUBMIT, audit_action="service_request.submitted")
    acknowledgement = send_acknowledgement(actor, request.id)
    # `DEF-CUS-10042` — the clerk's added messages waiting for the submit. Only
    # on the FIRST submit: a replay returned above and fires nothing.
    request_extra_messages.fire(
        actor, request_row(request.id), request_extra_messages.EXTRA_ON_SUBMIT
    )
    return {
        "request": request_row(request.id),
        "acknowledgement": acknowledgement,
        "idempotent_replay": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# BR-CUS-079 — the acknowledgement, and the ABSENCE of a way to send it
# ═══════════════════════════════════════════════════════════════════════════
ACK_QUEUED = "queued"
ACK_NOT_SENT = "not_sent"

#: Why nothing left the building, in the shape `ArPositions.unavailable` uses —
#: a code, the rule, and a sentence that says what is missing rather than what
#: happened.
ACK_NO_ADAPTER = "no_delivery_adapter_in_this_product"
ACK_NO_QUEUE = "notifications_publishes_no_queue_document"
ACK_NO_ADDRESS = "applicant_supplied_no_email_or_phone"
#: ⚠ **THE APPLICANT GAVE A PHONE AND NO EMAIL.** All four service-request
#: classes are EMAIL classes and an SMS carries 160 characters, so a phone
#: number alone cannot carry any of these letters. Named apart from
#: `ACK_NO_ADDRESS` because *"they left no way to reach them"* and *"they left a
#: way we have not written wording for"* are different facts and only the second
#: one is ours to fix.
ACK_NO_EMAIL = "applicant_supplied_no_email_address"
#: ⚠ **THIS FIRED ON EVERY SUBMISSION IN THE PRODUCT UNTIL 2026-09-15 AND IT WAS
#: A REAL FINDING, NOT A PLACEHOLDER — IT IS CLOSED NOW (`DEF-CUS-5389`).** It
#: read: *"`apps.notifications.models.SOURCE_TYPES` is a CONSTANT vocabulary of
#: eight … and `service_request` is not one of them. So BR-CUS-079's
#: acknowledgement cannot even be QUEUED until notifications adds the source
#: kind, which is that module's own write and not this lane's."* The kind was
#: added, with the four classes and the three writers behind it
#: (`apps/notifications/service_request_events.py`), and this acknowledgement
#: now reaches the queue.
#:
#: **The constant is KEPT rather than deleted** so a deployment that still holds
#: an older notifications module reports the same stable code a screen already
#: keys off, and so a reader who met the old sentence can find out that it
#: moved.
ACK_SOURCE_TYPE_UNKNOWN = "notifications_has_no_service_request_source_type"


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def send_acknowledgement(actor: Any, request_id: Any) -> dict[str, Any]:
    """**BR-CUS-079 (CONFIRMED, PO 2026-08-24):** *"when you take and submit SR -
    we have to send email or text messge to customer - im talimg about that"*.
    B19 §11.3 confirms it as drawn — badged `Sent automatically`, to the email
    captured at step 1, *"the moment the request was created"*, carrying the SR
    number.

    ⚠ **AND IT RENDERS ITS OWN ABSENCE RATHER THAN A FABRICATED `sent` STATE.**
    BR-CUS-079 says so itself: the acknowledgement is a NOTIFICATION, and **no
    delivery adapter exists in this product** — the same posture as W7 task
    7.10's `LAST NOTICE` and the same law as `ArPositions` (an absent answer is
    never spelled the same way as a real one). So the best this can honestly
    reach is **QUEUED** into `outbound_messages`, which is a row somebody could
    later send; when even that is unreachable it records WHY.

    ⚠ **AND THE DRAWN EMAIL BODY IS FALSE WHEN MONEY WAS TAKEN — BR-CUS-090
    CLAUSE (3), which is a RULING now and not a defect note.** Verbatim: *"THE
    ACKNOWLEDGEMENT MAY NOT SAY 'Nothing is charged' WHEN MONEY WAS TAKEN ...
    Where a fee WAS taken the sentence states the amount, the method and the
    receipt number; where none was, it may stand. It is the FIRST thing an
    applicant receives and it is customer-facing, so a false sentence there is a
    money defect, not a copy nit."*

    **This module does not compose the body — notifications owns the template —
    so what it does instead is make the false sentence impossible to reach
    accidentally:** the acknowledgement record carries `fee_taken`, the amount,
    the method and the receipt, and `nothing_is_charged_may_be_said` is a served
    boolean rather than a judgment the template has to make. The read model
    serves the same four facts to the screen (`decision_tab`). A template that
    prints *"Nothing is charged"* over `fee_taken=True` is then a visible
    contradiction rather than an invisible one.

    ⚠ **THE COPY WAS OWED FOR THREE WEEKS AND ARRIVED 2026-09-15.** This
    paragraph read: *"THE COPY ITSELF IS STILL OWED and is not this lane's to
    write … the notifications template that would use it does not exist (there
    is no `service_request` source type)."* Both halves are closed. The source
    kind exists, and the fee clause is not a sentence a template has to
    remember: `notifications` carries **two** acknowledgement classes and the
    one with the amount, the method and the receipt number is pinned when and
    only when a receipt exists. A body that says *nothing is charged* over money
    taken is now unreachable rather than discouraged.

    ⚠ **EMAIL ONLY.** All four classes are email classes; an SMS carries 160
    characters and none of this wording has been written for one. An applicant
    who left a phone and no email records `ACK_NO_EMAIL` and gets nothing, which
    is a named absence rather than a letter crammed into a text message.

    ⊕ **`DEF-CWP-10539` — THE BODY IS `_send_acknowledgement`, SHARED WITH THE
    PORTAL DOOR.** PO 2026-10-22: a portal request gets this same letter when
    the applicant gave a valid email (*"yes if we have valid email"*). This
    function keeps its role guard and adds nothing; `create_from_portal` calls
    the same body with the role-free `PORTAL_REPORTER`, so there is one way the
    acknowledgement is composed, not two.
    """
    return _send_acknowledgement(actor, request_id)


def _send_acknowledgement(actor: Any, request_id: Any) -> dict[str, Any]:
    """`send_acknowledgement`'s body, role-free — see its docstring.

    Called by `send_acknowledgement` (staff, guarded) and by
    `create_from_portal` (the guest door, `PORTAL_REPORTER`, only once the
    email has passed `_valid_email`). Routed by no endpoint.
    """
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        if not (request.applicant_email or request.applicant_phone):
            return _record_acknowledgement(actor, request, ACK_NOT_SENT, ACK_NO_ADDRESS, None)
        if not request.applicant_email:
            return _record_acknowledgement(actor, request, ACK_NOT_SENT, ACK_NO_EMAIL, None)
        fee = fee_statement(request)
        outcome = notifications_seam.queue_request_acknowledgement(
            request_id=request.id,
            request_no=request.request_no,
            applicant_email=request.applicant_email,
            # `DEF-CUS-10445` — name, address (as PARTS), service type and
            # target date, every one decided here and only carried there.
            **acknowledgement_facts(request),
            # BR-CUS-090 clause (3): passing a receipt is what pins the class
            # that states the money. Two decimals (hard rule 2 — four stored,
            # two displayed) because a template cannot round.
            # CR-190-BRC10 — a VALUE plus its currency (PO 2026-10-22); the
            # renderer writes `$25.00` from the utility's region.
            fee_amount=request.fee_collected,
            fee_currency=request.fee_currency,
            fee_method=request.fee_method,
            receipt_no=request.fee_receipt_no,
            actor=actor,
            # The applicant's stated language first, where the utility
            # published this letter in it; the utility's default otherwise
            # (PO option B, 2026-10-29 — `language` is the FALLBACK). The
            # captured language is also carried to the account, where it
            # drives the customer portal and every later message.
            language=seams.tenant_default_language(),
            preferred_language=request.preferred_language,
        )
        return _record_applicant_outcome(
            actor,
            request,
            outcome,
            occasion="acknowledgement",
            fee_statement_override=fee,
        )


def fee_statement(request: models.ServiceRequest) -> dict[str, Any]:
    """**BR-CUS-090 clause (3), as data rather than as prose.**

    PUBLISHED (not underscore-private) because the read model next door is a
    legitimate caller and a private name reached across a file boundary is a
    contract nobody agreed to — the same reasoning `customer_account_ids`
    carries.

    The one thing a template must never do is print *"Nothing is charged"*
    beneath a panel confirming cash was taken. So the fact is served, not
    inferred: `taken` is True when a receipt was recorded, and
    `nothing_is_charged_may_be_said` is its negation, stated once here so no
    caller has to work it out and get it wrong.
    """
    taken = bool(request.fee_receipt_no)
    return {
        "taken": taken,
        "amount": str(request.fee_collected) if request.fee_collected is not None else None,
        "currency": request.fee_currency,
        "method": request.fee_method,
        "receipt_no": request.fee_receipt_no,
        "collected_at": (
            request.fee_collected_at.isoformat() if request.fee_collected_at else None
        ),
        # Where no fee was taken the drawn sentence may stand — the ruling says
        # so in as many words.
        "nothing_is_charged_may_be_said": not taken,
        "message_key": (
            "customers.serviceRequest.acknowledgement.feeCollected"
            if taken
            else "customers.serviceRequest.acknowledgement.nothingCharged"
        ),
    }


def _applicant_address(request: models.ServiceRequest) -> str:
    """The address the letter says the request is FOR — the applicant's own words.

    ⚠ **`address_as_given`, NEVER THE RESOLVED PREMISES.** `BR-CUS-070` keeps
    the applicant's text byte-identical and never overwrites it, and a request
    may not resolve to a premises at all — the commonest refusal reason drawn on
    the blueprint is *Not our service area*, where by definition there is no
    premises of ours to walk to. Hard rule 8 is not in tension with this: the
    rule governs where an address is STORED, and this reads a verbatim field
    this table already owns rather than declaring an address of its own.
    """
    parts = [request.address_as_given or "", request.address_unit_as_given or ""]
    return " ".join(part.strip() for part in parts if part and part.strip())


def acknowledgement_facts(request: models.ServiceRequest) -> dict[str, Any]:
    """Every fact the acknowledgement prints about THIS request — `DEF-CUS-10445`.

    The PO's report of 2026-10-22: the acknowledgement *"shows dashes for name,
    address, service type, target date and phone"*. Ruled the same day (decision
    log *"Service request acknowledgement: target date, default 15 days, service
    type name"*), and each key below is one clause of that ruling:

    * **`applicant_name`** — the applicant's own name as typed. A request raised
      for somebody already on file may carry none; `account_id` is then the
      matched customer's ONE account, and notifications fills the name from the
      account holder through the shared customer-details builder. Two accounts
      or none → no account named, because picking one would be a guess.
    * **`service_address_parts`** — hard rule 8: where the request names a
      premises or a unit (a clerk picked it at capture, or the resolver matched
      it), the address is WALKED to there — the building's street, the unit's
      label, the town, state and postcode. With no premises — a new connection
      at an address we do not serve yet — it is the address as the applicant
      gave it, in the same parts. `service_address` stays the one-line typed
      form for a caller that cannot read parts.
    * **`service_type`** — the requested services' NAMES as Settings → Services
      holds them, in the catalogue's order (`Water, Sewer`); never a code (B14
      rule 31). No service asked for → `None`, the named absence.
    * **`target_date`** — the customer's preferred date: the request's own
      connection date, else the earliest date given against one of its
      services. With none, the REQUEST DATE (the day it was submitted, on the
      utility's clock) plus `service_request_default_target_days` WORKING days —
      a Settings number seeded 15, never a constant here (*"don't do any
      hardcoding"*). A DATE, so the renderer writes it in the Regional format.

    ⚠ **THIS NARROWS `_applicant_address`'s POSTURE FOR THE ACKNOWLEDGEMENT
    ALONE, AND ONLY WHERE A PREMISES IS KNOWN.** That helper keeps the typed
    text because a request may resolve to nothing; the ruling names *"the
    premises, or the typed address for a new connection"*, which is exactly the
    two cases here. `address_as_given` itself is untouched (`BR-CUS-070`).

    ⚠ **THE DEFAULT COUNTS WORKING DAYS, AND IT IS THE SAME NUMBER THAT OPENS A
    NEW REQUEST'S `Connection date`.** That prefill was ruled on 2026-09-22
    (*"make it default add 15 working days"*) and sat in a constant; the ruling
    of 2026-10-22 (*"Default 15 days"*, *"don't do any hardcoding"*) is the same
    fact for a request that arrived without one. One setting now drives both,
    counted one way, so a clerk who leaves the prefill alone and an applicant
    whose date is blank are told the same day.
    """
    rows = list(
        request.services.select_related("service").order_by("service__sort", "service__code")
    )
    names = [row.service.name for row in rows if row.service is not None and row.service.name]
    preferred = request.requested_start or min(
        (row.requested_start for row in rows if row.requested_start is not None), default=None
    )
    target = preferred
    if target is None:
        days = seams.service_request_default_target_days()
        requested_on = _request_day(request)
        if days is not None and requested_on is not None:
            # WORKING days, weekends and this utility's holidays out — the same
            # count, through the same function, that opens a new request's
            # `Connection date` (`service_request_api.service_request_capture_
            # defaults`), so an untouched prefill and this fallback agree.
            from apps.customers import cut_date

            target = cut_date.business_days_after(requested_on, days, seams.tenant_holidays())
    accounts = customer_account_ids(request.matched_customer_id)
    return {
        "applicant_name": request.applicant_name,
        "service_address": _applicant_address(request),
        "service_address_parts": _acknowledged_address_parts(request),
        "account_id": accounts[0] if len(accounts) == 1 else None,
        "service_type": ", ".join(names) or None,
        "target_date": target,
    }


def _request_day(request: models.ServiceRequest) -> date | None:
    """The day the request was made, on the utility's clock (`BR-TEN-043`)."""
    moment = request.submitted_at or request.received_at
    if moment is None:
        return seams.tenant_today()
    zone = seams.tenant_timezone()
    return timezone.localtime(moment, zone).date() if zone is not None else moment.date()


def _acknowledged_address_parts(request: models.ServiceRequest) -> dict[str, Any] | None:
    """The premises' envelope parts (hard rule 8), else the typed parts."""
    unit_id = request.resolved_unit_id
    premises_id = request.resolved_premises_id
    if unit_id or premises_id:
        found = seams.envelope_addresses(
            unit_ids=[unit_id] if unit_id else (),
            premises_ids=[premises_id] if premises_id and not unit_id else (),
        )
        if found:
            env = (found.get("units") or {}).get(str(unit_id)) if unit_id else None
            env = env or (found.get("premises") or {}).get(str(premises_id))
            if env and (env.get("line1") or "").strip():
                return {
                    "line1": env.get("line1"),
                    "unit_label": env.get("unit_label"),
                    "city": env.get("city"),
                    "state": env.get("state"),
                    "postal_code": env.get("postal_code"),
                }
    typed = (request.address_as_given or "").strip()
    if not typed:
        return None
    return {
        "line1": typed,
        "unit_label": request.address_unit_as_given,
        "city": request.address_city_as_given,
        "state": request.address_state_as_given,
        "postal_code": request.address_postal_code_as_given,
    }


def _record_applicant_outcome(
    actor: Any,
    request: models.ServiceRequest,
    outcome: dict[str, Any],
    *,
    occasion: str,
    fee_statement_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Turn one seam outcome into a timeline row, an audit row and a result.

    ⚠ **THE STATE IS DERIVED FROM WHETHER A ROW EXISTS, NEVER FROM WHETHER THE
    CALL RETURNED.** `queued` is true only when the seam names a `message_id`.
    Hard-won law 1 in its original form: a function that came back without
    raising is not a guarantee that anything was written, and *"we told them"*
    is the one claim on a service request that must never be made loosely.

    `sent` is False on every path and is not a field anybody sets. No delivery
    adapter exists on any channel (`BR-NOT-013`), so QUEUED is the truest thing
    this product can say — the same posture `ArPositions` takes for an
    unreadable balance.
    """
    ref = outcome.get("message_id")
    queued = bool(ref)
    state = ACK_QUEUED if queued else ACK_NOT_SENT
    reason = ACK_NO_ADAPTER if queued else str(outcome.get("code") or ACK_NO_QUEUE)
    if occasion == "acknowledgement":
        result = _record_acknowledgement(actor, request, state, reason, ref)
        if fee_statement_override is not None:
            result["fee_statement"] = fee_statement_override
        result["address"] = outcome.get("address")
        result["template_code"] = outcome.get("template_code")
        return result
    _event(
        request,
        actor,
        kind=models.ServiceRequestEvent.KIND_SYSTEM,
        note=_text(outcome.get("detail")),
        note_type=f"applicant_message:{occasion}:{state}",
    )
    _audit(
        actor,
        f"service_request.applicant_message.{occasion}",
        request.id,
        after={
            "state": state,
            "reason": reason,
            "ref": ref,
            "template_code": outcome.get("template_code"),
            "address": outcome.get("address"),
        },
    )
    return {
        "occasion": occasion,
        "state": state,
        "reason": reason,
        "ref": ref,
        "sent": False,
        "address": outcome.get("address"),
        "template_code": outcome.get("template_code"),
        "detail": outcome.get("detail"),
        "problems": list(outcome.get("problems") or ()),
    }


def _record_acknowledgement(
    actor: Any, request: models.ServiceRequest, state: str, reason: str, ref: str | None
) -> dict[str, Any]:
    request.acknowledgement_state = state
    request.acknowledgement_absence_reason = reason
    request.acknowledgement_ref = ref
    request.acknowledgement_at = timezone.now()
    request.save(
        update_fields=[
            "acknowledgement_state",
            "acknowledgement_absence_reason",
            "acknowledgement_ref",
            "acknowledgement_at",
            "updated_at",
        ]
    )
    _event(
        request,
        actor,
        kind=models.ServiceRequestEvent.KIND_SYSTEM,
        note=reason,
        note_type=f"acknowledgement:{state}",
    )
    _audit(
        actor,
        "service_request.acknowledgement",
        request.id,
        after={"state": state, "reason": reason, "ref": ref},
    )
    return {
        "state": state,
        "reason": reason,
        "ref": ref,
        "sent": False,
        "fee_statement": fee_statement(request),
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE DECISION — the clerk's, recorded with the evidence it was made against
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def decide_outcome(
    actor: Any, request_id: Any, *, outcome: str, note: str | None = None
) -> models.ServiceRequest:
    """`WHAT SHOULD THIS BECOME?` — the `Commit` panel's pick, badged `Nothing
    picked` until it is made.

    **FIVE outcomes, not three** (B19 §12.4, drawn twice — the decision panel
    offers all five and the list's `TYPE` column renders all five). CR-031 named
    three; the confirmation hedged *"or one of the other job types"*; this is
    the answer.

    **The clerk's choice is never overruled by the evidence.** If they pick an
    option the verdict table marked `not_possible`, the pick STANDS and the
    disagreement is recorded — `decided_against_evidence`, plus the verdict table
    exactly as it stood, in `evidence_snapshot`. CR-031 ruled the clerk decides,
    and a system that refused would be B18 §6.4's classifier wearing a different
    hat.

    ✅ **`disconnect` COMMITS — BR-CUS-091 (CONFIRMED, PO 2026-08-24), closing
    DEF-638 12.a.** Two artefacts disagreed: the Requests list draws `SR-26-0048
    · DISCONNECT · Ridge Coffee Co. · Under review`, and REQ-02's decision panel
    disabled the option with the reason *"a disconnect ... is only ever started
    by collections, never from a customer request"*. The PO ruled *"Yes customer
    can request it"* — **the list was right, that reason is WITHDRAWN and the
    control is enabled.**

    ⚠ **WHAT THE WITHDRAWN REASON GOT RIGHT SURVIVES, AND THIS FUNCTION IS WHERE
    IT IS ENFORCED.** A disconnect and a move-out are DIFFERENT OUTCOMES: a
    move-out CLOSES the account and settles the deposit (BR-CUS-030); a
    disconnect leaves it OPEN AND ACCRUING (BR-MET-105's base charge keeps
    running). BR-CUS-091: *"the capture form must not quietly convert one into
    the other; where an applicant describes ending service, the clerk picks the
    outcome and the request records which was picked."*

    **So there is no mapping, no inference and no fallback here** — `outcome` is
    stored exactly as the clerk sent it, and an applicant saying *"I want to end
    service"* produces whichever of the two a named human chose. The evidence
    verdict for `disconnect` is `possible` (never `fits_the_evidence`, which no
    screen draws for it — OQ-356), so the clerk is neither steered nor blocked.
    """
    if outcome not in _SR.JOB_OUTCOMES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.outcomeUnknown",
            params={"value": str(outcome)},
        )
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        # ⊕ `CR-183-BRC10` — a TEMPORARY STOP (or its *Restart now*) is not a
        # job: it is approved through `temporary_stop.approve_request`, which
        # checks the limits (B3) and schedules the hold. Offering it a New
        # connection or a Move-in is the defect the PO reported on SR-26-0017,
        # so the generic outcome door refuses it by name.
        from apps.customers import temporary_stop

        if temporary_stop.kind_of(request) is not None:
            _refuse(
                errors.BIZ_STATE,
                temporary_stop.KEY_USE_OWN_APPROVAL,
                br_ref=temporary_stop.BR_STOP,
            )
        # ⚠⚠ **THIS WAS A SECOND COPY OF THE STATE RULE AND IT SILENTLY UNDID THE
        # PO's RULING OF 2026-09-19.** It read
        # `if request.state not in (_SR.UNDER_REVIEW, _SR.MORE_INFO)`, hand-typed.
        # That day's ruling gave `APPROVE` the `SUBMITTED` state — *"a is
        # correct"*, decisions work straight from Submitted — and moved it in
        # `TRANSITIONS` and nowhere else. **Picking the outcome is the first half
        # of approving**, so with this line unchanged every clerk deciding a
        # submitted request met *"Pick this up for review before deciding"* — an
        # instruction to press a control the same ruling had deleted. Twenty-three
        # tests went red on it and the screen would have refused every decision.
        #
        # **So it ASKS the table instead of holding an opinion**, which is the
        # lesson `DEF-CUS-5874` recorded one module over on the same day: a
        # hand-typed copy of a state list is one ruling away from being false, and
        # nothing in this repository compares a copy with its original.
        if request.state not in rules.TRANSITIONS[rules.APPROVE][0]:
            _refuse(
                errors.BIZ_STATE,
                "customers.serviceRequest.decideUnderReviewOnly",
                br_ref="CR-031",
                state=request.state,
            )
        evidence = evidence_for(request)
        verdicts = rules.outcome_verdicts(evidence)
        chosen = next(row for row in verdicts if row["outcome"] == outcome)
        before = {"outcome": request.outcome}
        request.outcome = outcome
        request.decided_by_id = _actor_id(actor)
        request.decided_at = timezone.now()
        request.decision_reason = _text(note)
        request.decided_against_evidence = chosen["verdict"] == rules.NOT_POSSIBLE
        request.evidence_snapshot = {
            "resolution_kind": evidence.resolution_kind,
            "lookup_found": evidence.lookup_found,
            "verdicts": verdicts,
            "decided": outcome,
        }
        request.save()
        _event(
            request,
            actor,
            kind=models.ServiceRequestEvent.KIND_SYSTEM,
            note=_text(note),
            note_type=f"outcome:{outcome}",
        )
        _audit(
            actor,
            "service_request.outcome_decided",
            request.id,
            before=before,
            after={
                "outcome": outcome,
                "verdict": chosen["verdict"],
                "against_evidence": request.decided_against_evidence,
            },
        )
    return request


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def approve(actor: Any, request_id: Any, *, note: str | None = None) -> models.ServiceRequest:
    """`Approve` — gated by the outcome AND by every blocking condition.

    Two guards, both drawn:

      * `Commit` badged `Nothing picked` — *"Pick what this becomes before
        approving. Until then there is no job to start."*
      * `Conditions` — from REQ-03.5, *"the review step lists the unpaid fee as
        a blocking condition. **Nothing is refused — it simply cannot be
        approved yet.**"*

    ⚠ **THE SECOND GUARD USED TO QUOTE A DOCUMENTS SENTENCE HERE AND THAT
    SENTENCE IS SUPERSEDED — PO 2026-09-16, *"lets not make it mandetory"*.** It
    read *"Cannot approve yet — documents verified: 2 of 3 — check the rest
    before approving."* **Documents no longer block**; they are reported to the
    clerk before the press and carried into the draft job's own wizard. The
    arrears question still blocks, and so does an unsettled fee.

    That last sentence is why this raises a `BIZ_*` refusal naming the blocking
    conditions rather than moving the request to `Refused`: not being approvable
    is not a refusal, and conflating the two would put a reason on a customer's
    record that nobody gave.

    ⚠ **SINCE `CR-094-BRC01` THIS IS A THIN WRAPPER OVER `approve_and_raise`,
    and the two guards moved WITH the approval rather than staying here.** They
    had to: a second door that approved without re-asking them is exactly how a
    blocked request would get a job raised for it, and no check in this repo
    would ever have said so.

    ⚠ **IT TAKES NO `outcome` AND THAT IS DELIBERATE.** `approve_and_raise` now
    accepts one so the dialog can decide and approve in a single transaction
    (`DEF-CUS-5427`); this signature is the one every existing caller and test
    uses, and widening it would mean touching all of them for nothing. A caller
    that wants both calls `approve_and_raise`.
    """
    return approve_and_raise(actor, request_id, note=note)["request"]


def _record_address_declared_new(actor: Any, request_id: Any) -> None:
    """`DEF-CUS-6350` — the clerk said a near match is a DIFFERENT place.

    An audit row and a history line, naming the property they were shown, so a
    duplicate that later turns out to be the same building can be traced to the
    decision and the person who made it (PO decision 3's *"clerk decides"*
    carries the clerk's name). Nothing is written when there was no near match
    to decline: the flag then changed nothing and a row saying otherwise would
    be a record of a decision nobody took.
    """
    request = request_row(request_id)
    match = seams.premises_matching_address(
        request.address_as_given,
        city=request.address_city_as_given,
        postal_code=request.address_postal_code_as_given,
    )
    if not match or match.get("match") != "near":
        return
    shown = (match.get("candidates") or [{}])[0]
    _event(
        request,
        actor,
        kind=models.ServiceRequestEvent.KIND_SYSTEM,
        note=shown.get("premise_no") or shown.get("label"),
        note_type="address_declared_new",
    )
    _audit(
        actor,
        "service_request.address_declared_new",
        request.id,
        after={
            "as_given": request.address_as_given,
            "near_match_premise_no": shown.get("premise_no"),
            "near_match_label": shown.get("label"),
        },
    )


#: The outcomes that open an ACCOUNT, and so need its category (`DEF-CUS-10251`).
CATEGORY_OUTCOMES = (_SR.OUTCOME_MOVE_IN, _SR.OUTCOME_NEW_CONNECTION)


def category_to_be_set(request: models.ServiceRequest, outcome: str | None = None) -> bool:
    """`DEF-CUS-10251` — **Category to be set**: a request from the PORTAL with
    no category, about to be approved into an account.

    PO 2026-10-18 (decision log *"CUSTOMER DATA AND UI CONSISTENT ACROSS THE
    CREATE SCREENS"*, *"Same day"*): *"they may not able to provide cargory
    etc upfront"* → the portal form asks none, and *"this is correct"* to
    staff setting it before Approve. Only the portal channel: a clerk's capture
    gates on the category at step 2, and a request with another outcome (a
    report, a question) opens no account and needs none. `outcome` asks *what
    if this were the pick* for the Approve window; default reads the row's.
    """
    picked = outcome if outcome is not None else request.outcome
    return (
        request.channel == CHANNEL_CUSTOMER_PORTAL
        and request.account_type_id is None
        and (picked in CATEGORY_OUTCOMES or not picked)
    )


def _refuse_unless_approvable(request_id: Any, *, address_is_new: bool = False) -> None:
    """The two drawn guards, in one place because two doors now need them.

    ⊕ **AND SINCE 2026-09-23 THE PLACE IS ONE OF THEM (`DEF-CUS-6350`).** A
    move-in is refused unless its address is in Premises, a unit is chosen, the
    unit is free and no other move-in is waiting for it; a new connection is
    refused at an address already in Premises. They are CONDITIONS, so they
    arrive here through `conditions_for` like the arrears question does, and
    the Approve window greys its button on the same rows — there is no second
    list to drift. `address_is_new` is the clerk's answer to a near match, sent
    with the approval that relies on it.

    ⚠ **WHAT IS IN `blocking_conditions` MOVED ON 2026-09-16 AND THIS FUNCTION
    DID NOT.** The PO ruled that unchecked documents no longer block an
    approval, and that ruling is implemented where the condition is BUILT
    (`service_request.documents_condition`, `blocking=False`) rather than by an
    exception here. So this still refuses on every blocking condition, there is
    still exactly one list, and the arrears question still stops the press.

    ⚠ **NOT FOLDED INTO `_apply`.** These are APPROVAL's conditions and no other
    transition has them; folding them in would make every lifecycle move pay for
    a read it does not need, and would put approval's own rule somewhere a
    reader of `approve` cannot see it.
    """
    from apps.customers import service_request_reads as reads

    with transaction.atomic():
        request = request_row(request_id, lock=True)
        # ⊕ `CR-183-BRC10` — see `decide_outcome`: never approved as a job.
        from apps.customers import temporary_stop

        if temporary_stop.kind_of(request) is not None:
            _refuse(
                errors.BIZ_STATE,
                temporary_stop.KEY_USE_OWN_APPROVAL,
                br_ref=temporary_stop.BR_STOP,
            )
        if not request.outcome:
            _refuse(
                errors.BIZ_COMPLETENESS, "customers.serviceRequest.outcomeRequired", br_ref="CR-031"
            )
        if category_to_be_set(request):
            # ⊕ DEF-CUS-10251 — PO 2026-10-18, *"this is correct"*: a portal
            # application arrives with no category (the customer is not asked
            # for internal classifications) and staff set it before approving.
            # Refused HERE, on the server, and not only greyed on the screen.
            _refuse(
                errors.BIZ_COMPLETENESS,
                "customers.serviceRequest.categoryFirst",
                br_ref="DEF-CUS-10251",
            )
        blocking = rules.blocking_conditions(
            reads.conditions_for(request, address_is_new=address_is_new)
        )
        if blocking:
            first = blocking[0]
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="CR-031",
                message_key=first.message_key or "customers.serviceRequest.conditionsNotClear",
                params={
                    **first.params,
                    "condition": first.key,
                    "blocking": ",".join(c.key for c in blocking),
                },
            )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def approve_and_raise(
    actor: Any,
    request_id: Any,
    *,
    note: str | None = None,
    outcome: str | None = None,
    address_is_new: bool = False,
    custom_field_picks: Any = None,
) -> dict[str, Any]:
    """`Approve and raise the build` — **the drawn button, and what it does.**

    `CR-094-BRC01`, PO 2026-09-15: *"pass all information to create the new
    connect requets or move -in request based on selction"*. Drawn p083–p084
    (images, scale 2): the modal's footer reads `Cancel` / **`Approve and raise
    the build`**, and the `WHAT APPROVING WILL DO` table's second row is *"A
    build is raised on the New connects tab, naming this request"*.

    Returns `{"request": …, "job": {"raised"|"not_raised": …}}`. `approve` above
    keeps returning the request alone, so every existing caller and test is
    unchanged; this is the door that answers what was created.

    ⚠ **THE STATE COMMITS FIRST AND THE JOB IS RAISED AFTER IT, and that order
    is `route`'s, for `route`'s reason (`BR-WRK-055`):** a neighbouring module
    that is down, unpublished or refusing must not hold an approved application
    in review for ever. So `request_jobs.raise_job` never raises — it reports —
    and the clerk sees a named absence rather than a job that silently is not
    there. Everything the drawn table promises EXCEPT the job row has already
    happened by the time that call is made.

    ⚠⚠ **`outcome` DECIDES AND APPROVES IN ONE TRANSACTION, AND IT EXISTS
    BECAUSE THE TWO-POST ORDER LOST A CLERK'S WORK IN THE OTHER DIRECTION
    (`DEF-CUS-5427`, 2026-09-16).** The Approve dialog used to fire
    `POST .../decision` and then `POST .../approve`, in that order and for a
    stated reason — *"If the first fails nothing is approved; the alternative
    would leave an approved request carrying no outcome."* True, and the REVERSE
    had not been considered: when the SECOND fails, the outcome is already
    written and the request sits at `Under review` looking decided while being
    nothing of the kind. Measured on `SR-26-0003`: outcome saved, approval 422,
    request left carrying `move_in`.
    **So the outcome may now travel WITH the approval.** It is written here,
    inside the same transaction as the guards and the state change, so a refused
    approval rolls it back and leaves nothing behind. `POST .../decision` is
    untouched and is still the Decision tab's own door — a clerk who decides
    today and approves tomorrow is a real shape and this does not take it away.
    **`None` is every existing caller, unchanged.**

    ⚠ **THE DOCUMENT GATE NO LONGER EXISTS — PO ruling 2026-09-16, verbatim:
    *"lets not make it mandetory"*.** This paragraph said *"the document gate
    still runs first and is unchanged"* until that day. `documents_condition`
    now reports instead of blocking, so an unchecked required document is told
    to the clerk before the press and carried into the draft job's own wizard.
    **What still runs first, and every word of it is unchanged:** the outcome
    must be picked, and every REMAINING blocking condition — the arrears
    question above all — must be clear. *"Nothing is refused — it simply cannot
    be approved yet."* Both doors reach the raise only through
    `_refuse_unless_approvable`, so there is no path that creates a job for a
    request that could not be approved.
    """
    from apps.customers import request_jobs

    # ⚠ ONE TRANSACTION OVER THE DECIDE, THE GUARDS AND THE STATE. A refusal
    # below is a Python exception and not a database error, so the rollback is
    # clean on PostgreSQL and nothing is left half-written (hard-won law 14 is
    # about the other case — a FAILED STATEMENT — and does not apply here, which
    # is why this can be one block rather than a savepoint dance).
    with transaction.atomic():
        if outcome is not None:
            # The clerk's pick, written first so the guards below can see it —
            # the document checklist is keyed on it (`BR-CUS-095`). `note` is
            # the APPROVAL's note and is not the decision's; the dialog has
            # always sent none for the decision and that does not change.
            decide_outcome(actor, request_id, outcome=outcome)
        # ⚠ THE TWO DRAWN GUARDS, FIRST AND ALWAYS. Both doors pass through
        # here, so there is no path that raises a job for a request that could
        # not be approved.
        _refuse_unless_approvable(request_id, address_is_new=address_is_new)
        if address_is_new:
            # ⊕ `DEF-CUS-6350` — the clerk's *It's a new address*, recorded
            # with the approval that relied on it. The near match they looked at
            # is read back and written beside it, so the audit says what was
            # declined rather than merely that something was.
            _record_address_declared_new(actor, request_id)
        request = _apply(
            actor,
            request_id,
            rules.APPROVE,
            reason=note,
            extra={"decided_by_id": _actor_id(actor), "decided_at": timezone.now()},
            audit_action="service_request.approved",
        )
        # ⊕ **`CR-161-BRC10` W6 — THE ANSWERS TYPED ON STAFF NEW REQUEST ARE
        # COPIED TO THE RECORDS THAT EXIST** (PO Part 2 row 15, *"On approval,
        # copied to Customer / Account / Premises"*), with R5's pick: a key the
        # record already holds differently keeps the EXISTING value unless the
        # clerk picked *Requested* (`custom_field_picks`). INSIDE this
        # transaction, so a refused copy leaves the request unapproved; the
        # request's own copy is never touched. See `request_custom_fields`.
        request_custom_fields.apply_on_approval(actor, request, custom_field_picks)
        # ⚠ **AND IT EARNS THE COUNTER FEE (PO ruling 2026-09-15).** *"when it
        # is approved you can attached it to account"*. The held credit is
        # applied to the application fee, which is where it becomes revenue:
        # DR `2400 Customer credit balances` · CR the charge code's own revenue
        # account, through the payments seam and never written here (hard rule
        # 5). Worked: $25.00 taken against a `CC-REQFEE` $25.00 line → `DR 2400
        # 25.0000 · CR <that code's account> 25.0000`.
        #
        # INSIDE the state change's transaction, unlike the job below: an
        # approved application whose fee is still sitting as a liability is a
        # book that disagrees with itself, while an approved application whose
        # build has not been raised yet is a queue somebody works through.
        #
        # ⚠ **THE ATTACH ITSELF IS NOT DONE HERE AND CANNOT BE —
        # `DEF-PAY-5394`.** Approval raises WORK; it opens no account, and
        # `customers.Account` carries no link back to a request, so there is
        # nothing to put a `Payment` on at this moment. The MONEY is complete
        # without it; `payments.counter_receipts.attach_to_account` is the act
        # still waiting for a caller, and the defect row says so rather than a
        # comment claiming it is handled.
        _release_counter_fee(actor, request, outcome="approved")
    # ⚠ **AND THE APPLICANT IS TOLD — ROW FIVE OF THE DRAWN STEP-6 BLOCK
    # (`BR-CUS-1076`, PO question 2026-09-15: *"at the time of approval we are
    # also linking notification and templates to the modal - are you ensuring
    # it will work?"*).** It did not: approving queued nothing, so somebody
    # could apply for service, be approved, and never hear a word.
    #
    # OUTSIDE the transaction and after it, for `route`'s reason and the
    # refusal letter's: the approval has committed and a queue that refuses
    # must never undo it. The seam's own savepoint is what makes that safe on
    # PostgreSQL (hard-won law 14), and nothing here can raise.
    decision_message = applicant_messages.on_decision(
        actor, request, decision=applicant_messages.DECISION_APPROVED
    )
    # `DEF-CUS-10042` — the clerk's added messages waiting for approval, after
    # it and outside it for the same reason as the line above.
    request_extra_messages.fire(actor, request, request_extra_messages.EXTRA_ON_APPROVE)
    job = request_jobs.raise_job(actor, request)
    # Re-read: `link_child` wrote `outcome_kind` / `outcome_ref` on its own row
    # inside its own transaction, and the object in hand predates that write.
    approved = request_row(request_id)
    approved.applicant_message = decision_message
    return {"request": approved, "job": job, "applicant_message": decision_message}


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def refuse_request(
    actor: Any,
    request_id: Any,
    *,
    reason: str,
    reason_code: str | None = None,
    message_to_applicant: str | None = None,
) -> models.ServiceRequest:
    """`Refuse` (danger tier) — *"Refusing keeps the request and its reason on
    record. The chain ends at the application — no job is created and there is
    nothing to follow."*

    A reason is required (TC-REQ-9). The row is KEPT, never deleted — cost #4:
    *someone turned down for arrears at a previous address simply reapplies* —
    and the refusal stays in `service_request_events` even after a reopen
    (TC-REQ-10), because that table is append-only.

    ⚠ **THREE THINGS ARRIVED ON 2026-09-15 (`DEF-CUS-5389`), AND THEY ARE THREE
    DIFFERENT AUDIENCES FOR ONE ACT.** The blueprint's Refuse dialog (p084–p085,
    read as an image) draws all three and the product had one:

      * `reason` — what the clerk tells the REGISTER. Free text, unchanged, and
        it stays internal.
      * `reason_code` — what the utility FILES the refusal under, now one of the
        five drawn values (`service_request.REFUSAL_REASONS`) rather than any
        string at all. The column has been accepted since CR-031 and no screen
        ever set it, so a register of refusals could not answer *why does this
        utility turn people down* — five values group and five hundred typed
        sentences do not.
      * `message_to_applicant` — the dialog's `What to tell them`, whose helper
        line reads *"Goes into the refusal letter."* It is the letter's body,
        stored on `refusal_message`, and it is the only one of the three an
        applicant ever reads. **No reason code reaches them** (B14 rule 32 keeps
        our vocabulary off a customer's screen, and a letter outlives a screen).

    ⚠ **THE LETTER RIDES ALONG AND MAY NEVER UNDO THE REFUSAL.** It is queued
    after the transition has committed, through a seam that cannot raise; the
    outcome comes back on `request.applicant_message` so the clerk is told
    whether it went, instead of the screen guessing. Passing no message refuses
    nothing and queues nothing — the timeline says so.
    """
    code = _text(reason_code, 60)
    if code is not None and code not in rules.REFUSAL_REASONS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.refusalReasonUnknown",
            params={"value": code},
        )
    letter = _text(message_to_applicant)
    with transaction.atomic():
        request = _apply_refusal(actor, request_id, reason=reason, code=code, letter=letter)
        # ⊕ `CR-183-BRC10` — a refused temporary-stop ask leaves its hold row
        # `refused`, in the same transaction, so nothing can ever schedule it.
        from apps.customers import temporary_stop

        temporary_stop.on_request_refused(actor, request)
        # ⚠ **REFUSING DOES NOT UNDO THE MONEY, AND SINCE 2026-09-15 IT EARNS
        # IT (PO ruling).** *"if it is refuse then it is application fees non
        # refundable - it stya in books"*. The held credit is released to the
        # charge code's own revenue account — DR `2400 Customer credit
        # balances` · CR that account — the identical pair approval posts,
        # because in double entry *applied to the fee* and *earned because it
        # is non-refundable* are one act.
        #
        # ⚠ **THE DRAWN HEDGE IS WITHDRAWN.** p085's modal says the request
        # closes *"holding `$25.00` that may have to be given back"*. It does
        # not have to be given back. The same panel's other half stands and is
        # the reasoning this acts on: *"a refusal that silently wrote off a
        # receipt is how a cash drawer stops reconciling."*
        #
        # ⚠ **A CHART GAP NEVER BLOCKS A REFUSAL.** An unmapped charge code
        # leaves the liability in 2400 with `release_error` saying why; the
        # refusal goes through. A clerk stuck at a counter with a person in
        # front of them is the worse failure.
        _release_counter_fee(actor, request, outcome="refused")
    request.applicant_message = _tell_the_applicant(
        actor,
        request,
        occasion="refusal",
        message_body=letter,
        no_message_reason=APPLICANT_NO_REFUSAL_MESSAGE,
    )
    # ⚠ **THE REFUSAL LETTER *IS* ROW FIVE ON THIS PATH, SO NOTHING SECOND IS
    # QUEUED — IT IS RECORDED (`BR-CUS-1076`).** The drawn step-6 row reads
    # *"The decision, when it is made · On approve or refuse"*, and on a refusal
    # a clerk is standing at the request typing the letter in the modal. That
    # present act outranks a tick set at capture (the `queue_account_message`
    # argument: a rule that silently swallowed a clerk's own words would leave
    # them believing they had written to somebody when nothing was written), and
    # queueing a second generic letter would tell one applicant twice about one
    # decision. So the row is stamped with the SAME queue row the letter above
    # produced.
    applicant_messages.on_decision(
        actor,
        request,
        decision=applicant_messages.DECISION_REFUSED,
        already=request.applicant_message,
    )
    # `DEF-CUS-10042` — the clerk's added messages waiting for a refusal.
    request_extra_messages.fire(actor, request, request_extra_messages.EXTRA_ON_REFUSE)
    return request


def _apply_refusal(
    actor: Any, request_id: Any, *, reason: str, code: str | None, letter: str | None
) -> models.ServiceRequest:
    """The refusal's own transition, lifted out so the money can join it.

    Split from `refuse_request` on 2026-09-15 for ONE reason and nothing else:
    the fee release has to be in the same transaction as the state change, so
    that a refused request and an earned fee are one fact. Every column and
    every comment below is exactly as `DEF-CUS-5389`'s lane wrote it.
    """
    return _apply(
        actor,
        request_id,
        rules.REFUSE,
        reason=reason,
        extra={
            "outcome": _SR.OUTCOME_REFUSED,
            "reason_code": code,
            # ⚠ **THIS COLUMN WAS NEVER FILLED BY A REFUSAL AND THAT WAS A GAP,
            # NOT A DESIGN (found by this wave's own test, 2026-09-15).** A
            # refusal already stamped `outcome`, `reason_code`, `decided_by` and
            # `decided_at` — every decision column but the one saying WHY — so
            # the Decision tab's own `reason` row rendered empty on every
            # refused request in the product and the reason was readable only by
            # scrolling the timeline. `decide_outcome` has always written it for
            # the other five outcomes; refusing now writes it too.
            "decision_reason": _text(reason),
            "refusal_message": letter,
            "decided_by_id": _actor_id(actor),
            "decided_at": timezone.now(),
        },
        audit_action="service_request.refused",
    )


def _release_counter_fee(actor: Any, request: models.ServiceRequest, *, outcome: str) -> None:
    """Hand a TERMINAL outcome to payments so the held counter fee is earned.

    **DR `2400 Customer credit balances` · CR the charge code's own revenue
    account**, through the seam. Customers writes no journal line and picks no
    account (hard rule 5, BR-BIL-010).

    ⚠ **ONLY THE TWO TERMINAL OUTCOMES REACH HERE, AND THAT IS THE RULING'S
    THIRD CLAUSE RATHER THAN AN OMISSION.** PO: *"if it is ask more then it
    stays in all 3 places in payment, in ledger and in finance"*. Ask for more is
    not a decision about the money — the request stays open (p085: *"It stays
    open and stops waiting on you"*) and the $25.00 stays exactly where
    collection put it. **No entry is made and none is reversed.** It is written
    down because a reader of only the approve and refuse clauses would reasonably
    wonder whether the third door needed a posting of its own, and would then
    invent one.

    Returns nothing: the receipt is payments' row and a caller that needed it
    reads `fee_total_to_collect(...)["counter_receipt"]`, which is the one
    published shape.
    """
    payments_seam.release_counter_receipt(
        source_type=payments_seam.SOURCE_SERVICE_REQUEST,
        source_id=request.id,
        outcome=outcome,
        fee_lines=_fee_lines_for_release(request.id),
        released_at=request.decided_at or timezone.now(),
        released_by_id=_actor_id(actor),
        actor=actor,
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def ask_for_more(
    actor: Any,
    request_id: Any,
    *,
    reason: str,
    info_needed: Any = None,
    message_to_applicant: str | None = None,
) -> models.ServiceRequest:
    """`Ask for more` — *"It stays open and stops waiting on you"*.

    ⚠ **UNTIL 2026-09-15 THIS SENT ONE FIXED SENTENCE TO EVERY REQUEST IN THE
    PRODUCT AND NOTHING AT ALL TO THE APPLICANT** (`DEF-CUS-5389`). The words
    were *"More information is needed before this can be reviewed."* — the same
    on a missing site plan, an unchecked identity and an unknown connection
    date, so a clerk could not say what was actually needed.

    The blueprint's Ask-for-more dialog (p085–p086, read as an image) draws two
    controls where the product had none:

      * `WHAT IS NEEDED` — a tick list of four
        (`service_request.INFO_NEEDED_KINDS`). It is the CLERK's checklist: it
        is stored on the request and kept on its history, and it is NOT in the
        letter, because the drawing attaches *Sent to them* to the message box
        alone.
      * `Message to the applicant` — *"Sent to them and kept on the request's
        history."* This is what goes out.

    The state move is `request_info`, exactly as it was, so every existing
    caller of `transition` still works. This door exists for the same reason
    `refuse` has one: it carries guards `transition` does not.
    """
    needed = _clean_info_needed(info_needed)
    message = _text(message_to_applicant)
    request = _apply(
        actor,
        request_id,
        rules.REQUEST_INFO,
        reason=reason,
        extra={"info_needed": needed, "info_message": message},
        audit_action="service_request.info_requested",
    )
    request.applicant_message = _tell_the_applicant(
        actor,
        request,
        occasion="more_info",
        message_body=message,
        no_message_reason=APPLICANT_NO_INFO_MESSAGE,
    )
    return request


#: The action name `resend_the_ask` refuses under when the request is not
#: waiting on the applicant. Not a lifecycle move — `TRANSITIONS` does not hold
#: it and must not — so it is named here, beside the one door that uses it.
RESEND_THE_ASK = "resend_ask"


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def resend_the_ask(actor: Any, request_id: Any) -> models.ServiceRequest:
    """`Resend the ask` — the *Waiting on customer* details view's secondary
    button (`CR-171-BRC10` P1.06, image 05; the PO's actions table of
    2026-10-05: *"Waiting on customer — Approve ✓ · Resend the ask · More: Edit,
    Decline…"*).

    **It queues the SAME words again and moves nothing.** The request is already
    `more_info`; the clerk is not asking anything new, they are nudging an
    applicant who has not answered. So this is NOT `ask_for_more` a second time:
    that would write a `more_info → more_info` state row and an
    `info_requested` audit row for an ask nobody made, and would let a resend
    overwrite the stored `info_message` with whatever the screen happened to
    send. The message is read off the row, never off the caller.

    ⚠ **IT GOES THROUGH `_tell_the_applicant`, WHICH IS THE ONE DOOR TO
    `notifications_seam.queue_request_more_info`.** That function writes its
    own timeline row FIRST and keys the queue on that row's id, so a resend is
    a second outbound row rather than a dedupe into the first — the same reason
    a second ask is (`test_a_second_ask_writes_a_second_message_not_a_dedupe`).
    It never raises and never undoes anything: the seam's savepoint is what
    makes that true on PostgreSQL (hard-won law 14).

    ⚠ **AN ASK THAT CARRIED NO MESSAGE RESENDS NOTHING, AND SAYS SO.** A clerk
    may ask for more with a reason and no message (the old `transitions` door
    still allows it). There is then nothing to send again; the outcome comes
    back `not_sent` with `no_message_to_the_applicant_was_written`, exactly as
    the original ask's did, rather than inventing a generic sentence.

    Refused unless the request is `more_info` — from any other state there is
    no outstanding ask to resend, and the refusal is the existing
    `transitionNotAllowed` sentence naming this action.
    """
    request = request_row(request_id)
    if request.state != rules.MORE_INFO:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="CR-171-BRC10",
            message_key="customers.serviceRequest.transitionNotAllowed",
            params={"action": RESEND_THE_ASK, "state": request.state},
        )
    outcome = _tell_the_applicant(
        actor,
        request,
        occasion="more_info",
        message_body=_text(request.info_message),
        no_message_reason=APPLICANT_NO_INFO_MESSAGE,
    )
    _audit(
        actor,
        "service_request.info_resent",
        request.id,
        after={"state": outcome.get("state"), "ref": outcome.get("ref")},
    )
    request.applicant_message = outcome
    return request


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def reopen_declined_move_in(actor: Any, request_id: Any, *, reason: str) -> models.ServiceRequest:
    """`Reopen` — the *Declined* move-in's one action (image 08, More ▾).

    PO ruling 2026-10-05, `OQ-CUS-12789` CLOSED → (a), verbatim: *"Reopen:
    SR-26-0014 goes back to "To approve". Same number, her documents stay, and
    the decline stays in its history."* Each clause, as built:

      * **"goes back to To approve"** — `refused` → `submitted`, through
        `rules.next_state(..., move_in=True)`; nothing else moves a state.
      * **"Same number"** — the SAME row. No request is created, nothing is
        renumbered, `request_no` is not written.
      * **"her documents stay"** — nothing here touches documents, answers,
        services or fee lines. They are the application, and it is reopened.
      * **"the decline stays in its history"** — the REFUSED timeline row (with
        its reason) is append-only and is not touched; the reopen is a NEW
        `KIND_STATE` row beside it. The decision COLUMNS (`outcome`,
        `reason_code`, `decision_reason`, `refusal_message`, `decided_*`,
        `closed_at`) are lifted, because the request is undecided again and the
        details view must not show a live request under a refusal — and the
        values lifted go into the `audit_log` row's `before` (hard rule 7).
        That is exactly the clearing the retired `reopen` branch of `_apply`
        did (its comment survives there), restored for move-ins only.

    ⚠ **SCOPE: A MOVE-IN REQUEST ONLY.** The ruling supersedes 2026-09-19's
    *"refuse is terminal"* for move-ins and for nothing else, so a declined
    request whose resolver did not suggest a move-in (`rules.suggests_move_in`)
    is refused by name (`reopenNotAMoveIn`) and stays refused.

    ⚠ **THE MONEY IS NOT TOUCHED.** A refusal earned the held counter fee (PO
    2026-09-15, *"application fees non refundable - it stya in books"*); a
    reopen does not reverse that — no ruling says it should, and reversing an
    earned fee would be a new money rule. A later approval's release call posts
    nothing (`counter_receipts.release_counter_receipt`: *"A SECOND CALL POSTS
    NOTHING"*).

    ⚠ **NO LETTER IS QUEUED.** The PO's three clauses say nothing about telling
    the applicant, and the next decision (approve, ask for more, decline) writes
    its own letter. Our judgment, recorded in the decision log.

    ⚠ **A REASON IS REQUIRED — `BR-CUS-072` (CONFIRMED): *"REOPENING REQUIRES A
    REASON"*.** Image 08 draws only the menu item, and a drawing that does not
    show the dialog does not overrule a confirmed rule; the reason lands on the
    new timeline row beside the decline, which is where the next clerk reads
    why the application came back.
    """
    text = _text(reason)
    if not text:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.reasonRequired",
            params={"action": rules.REOPEN},
        )
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        if request.state == rules.REFUSED and not rules.suggests_move_in(
            request.resolution_kind
        ):
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="OQ-CUS-12789",
                message_key="customers.serviceRequest.reopenNotAMoveIn",
                params={"action": rules.REOPEN, "state": request.state},
            )
        try:
            lands_in = rules.next_state(request.state, rules.REOPEN, move_in=True)
        except rules.ServiceRequestRuleError as exc:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="OQ-CUS-12789",
                message_key="customers.serviceRequest.transitionNotAllowed",
                params={"action": rules.REOPEN, "state": request.state},
            ) from exc
        lifted = (
            "outcome",
            "reason_code",
            "decision_reason",
            "refusal_message",
            "decided_at",
            "decided_by_id",
            "closed_at",
        )
        before = {"state": request.state, **{k: getattr(request, k) for k in lifted}}
        request.state = lands_in
        for key in lifted:
            setattr(request, key, None)
        request.save()
        _event(
            request,
            actor,
            kind=models.ServiceRequestEvent.KIND_STATE,
            from_state=before["state"],
            to_state=lands_in,
            note=text,
        )
        _audit(
            actor,
            "service_request.reopened",
            request.id,
            before=before,
            after={"state": lands_in, "reason": text},
        )
    return request


def _clean_info_needed(value: Any) -> list[str]:
    """The tick list, refused rather than silently dropped when it is unknown.

    A code this product does not have is a clerk's screen and this server
    disagreeing about what can be waited for, and the honest answer is to say
    so. Order is the drawing's, not the caller's, so two clerks ticking the same
    two boxes store the same list and a report can group on it.
    """
    if value is None:
        return []
    if isinstance(value, str) or not hasattr(value, "__iter__"):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.infoNeededList",
            params={"value": str(value)},
        )
    chosen = {str(item).strip() for item in value if str(item).strip()}
    unknown = sorted(chosen - set(rules.INFO_NEEDED_KINDS))
    if unknown:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.serviceRequest.infoNeededUnknown",
            params={"value": ",".join(unknown)},
        )
    return [code for code in rules.INFO_NEEDED_KINDS if code in chosen]


#: Why nothing was queued, when the act itself was fine. Distinct codes because
#: *"the clerk typed nothing"* and *"the applicant left no email"* are different
#: facts and only one of them is anybody's mistake.
APPLICANT_NO_REFUSAL_MESSAGE = "no_refusal_message_was_written"
APPLICANT_NO_INFO_MESSAGE = "no_message_to_the_applicant_was_written"
APPLICANT_NO_EMAIL = ACK_NO_EMAIL


def _tell_the_applicant(
    actor: Any,
    request: models.ServiceRequest,
    *,
    occasion: str,
    message_body: str | None,
    no_message_reason: str,
) -> dict[str, Any]:
    """Queue the one letter this act promises, and record what happened.

    ⚠ **THE OCCASION ROW IS THE IDEMPOTENCY KEY, AND THE OBVIOUS CHOICE IS A
    TRAP.** The queue's key is (tenant, source kind, source id, channel, copy
    no). Keying on the REQUEST would mean a request asked for more twice, or
    refused, reopened and refused again, meets the key on the second message:
    the queue reports `created=False`, the clerk is told it was queued, and the
    applicant is sent the FIRST letter's contents and never the second's. So
    each act writes its own append-only timeline row first and that row's id is
    the key — the `move` precedent, one module over, for the same reason.

    ⚠ **IT NEVER RAISES AND IT NEVER UNDOES THE ACT IT DESCRIBES.** The refusal
    or the ask has already committed by the time this runs. The seam's savepoint
    is what makes that safe on PostgreSQL (hard-won law 14): a failed statement
    aborts the whole transaction there, so a plain `try` would lose the refusal
    at COMMIT and pass the entire suite on SQLite, which has no such state.
    """
    if not message_body:
        return {
            "occasion": occasion,
            "state": ACK_NOT_SENT,
            "reason": no_message_reason,
            "ref": None,
            "sent": False,
            "address": None,
            "template_code": None,
            "detail": None,
            "problems": [],
        }
    if not request.applicant_email:
        return _record_applicant_outcome(
            actor,
            request,
            {
                "code": APPLICANT_NO_EMAIL,
                "message_id": None,
                "template_code": None,
                "address": None,
                "detail": "this applicant gave no email address, so there was nowhere to "
                "send it. The decision stands and is on the record.",
                "problems": (),
            },
            occasion=occasion,
        )
    occasion_row = _event(
        request,
        actor,
        kind=models.ServiceRequestEvent.KIND_SYSTEM,
        note=message_body,
        note_type=f"applicant_message:{occasion}",
    )
    write = (
        notifications_seam.queue_request_refused
        if occasion == "refusal"
        else notifications_seam.queue_request_more_info
    )
    outcome = write(
        occasion_id=occasion_row.id,
        request_no=request.request_no,
        applicant_name=request.applicant_name,
        applicant_email=request.applicant_email,
        service_address=_applicant_address(request),
        message_body=message_body,
        actor=actor,
        # The applicant's language first, the utility's as the fallback — see
        # the acknowledgement above (PO option B, 2026-10-29).
        language=seams.tenant_default_language(),
        preferred_language=request.preferred_language,
    )
    return _record_applicant_outcome(actor, request, outcome, occasion=occasion)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def manual_close(actor: Any, request_id: Any, *, reason: str) -> models.ServiceRequest:
    """`Manual close`, badged `Rarely needed` — *"A request closes on its own
    when the job it created finishes. Close it by hand only when the job will
    never run…"*. Reason required.

    Lands in `closed` and not in `completed`, deliberately: `completed` means
    *"Service is live"* (B18 §5.3.3) and the whole point of this control is a job
    that never ran. **B19 draws the control and does not name the state it lands
    in** — recorded here as a lane judgment rather than left to be discovered.
    """
    return _apply(
        actor,
        request_id,
        rules.MANUAL_CLOSE,
        reason=reason,
        extra={"outcome": _SR.OUTCOME_CLOSED},
        audit_action="service_request.manually_closed",
    )


# ═══════════════════════════════════════════════════════════════════════════
# BR-CUS-080 — the link to the child job
# ═══════════════════════════════════════════════════════════════════════════
#: What an outcome opens. The CHILD TABLES DO NOT EXIST YET — move-in/move-out
#: are W5, new connect is W6, transfer is W7 — so this module writes its own
#: half of the link (`outcome_kind` + `outcome_ref`) and publishes
#: `documents_for_origin` for the child to read through. The child's
#: `origin_service_request_id` column lands with the child table.
OUTCOME_CHILD_KINDS = {
    _SR.OUTCOME_NEW_CONNECTION: "connection",
    _SR.OUTCOME_MOVE_IN: "move_in",
    _SR.OUTCOME_MOVE_OUT: "move_out",
    _SR.OUTCOME_TRANSFER: "transfer",
    # BR-CUS-091 — a disconnect is now a committable outcome, so it needs a
    # child kind of its OWN. ⚠ It is deliberately NOT mapped onto `move_out`:
    # the two do different things to the account (a move-out closes it and
    # settles the deposit, BR-CUS-030; a disconnect leaves it open and accruing,
    # BR-MET-105), and collapsing them here is exactly the quiet conversion the
    # rule forbids. The disconnect JOB itself is W7's; this is the link.
    _SR.OUTCOME_DISCONNECT: "disconnect",
}


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def link_child(
    actor: Any, request_id: Any, *, child_ref: str, child_kind: str | None = None
) -> models.ServiceRequest:
    """**BR-CUS-080 (CONFIRMED, PO 2026-08-24), this module's half.**

    Ratified in the PO's own words: *"origin_service_request_id; SR keeps outcome
    + outcome_ref so it alone answers 'what happened to this application';
    documents move by reference, not copy"*. Three consequences, each
    load-bearing, and this function is where two of them are enforced:

      * **the SR alone answers *"what happened to this application"*** — after
        this call, `outcome` + `outcome_kind` + `outcome_ref` on one row do it,
        with no scan of two other tables;
      * **one SR cannot silently produce two live children for one decision** —
        `ux_service_requests_outcome_ref` is unique per tenant, and a second
        `link_child` on a request that already has one refuses by name.

    The third — documents move BY REFERENCE — is `documents_for_origin`, and it
    is enforced by there being no copier anywhere in this module.

    ⚠ **`child_ref` is TEXT, not a foreign key, and that is not laziness.** The
    child tables are not built (W5/W6/W7). A nullable FK to a table that does
    not exist cannot be declared, and inventing the child table here to hang one
    on would be authoring another wave's schema. When the child lands it carries
    `origin_service_request_id` pointing back, which is the half BR-CUS-080
    actually names.
    """
    ref = _text(child_ref, 120)
    if not ref:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.childRefRequired",
            params={},
        )
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        if not request.outcome or request.outcome not in _SR.JOB_OUTCOMES:
            _refuse(
                errors.BIZ_COMPLETENESS,
                "customers.serviceRequest.outcomeRequired",
                br_ref="BR-CUS-080",
            )
        if request.outcome_ref:
            _refuse(
                errors.BIZ_IDEMPOTENT,
                "customers.serviceRequest.childAlreadyLinked",
                br_ref="BR-CUS-080",
                outcome_ref=request.outcome_ref,
            )
        kind = _text(child_kind, 60) or OUTCOME_CHILD_KINDS[request.outcome]
        before = {"outcome_ref": None}
        request.outcome_kind = kind
        request.outcome_ref = ref
        request.outcome_linked_at = timezone.now()
        request.save(
            update_fields=["outcome_kind", "outcome_ref", "outcome_linked_at", "updated_at"]
        )
        _event(
            request,
            actor,
            kind=models.ServiceRequestEvent.KIND_SYSTEM,
            note=ref,
            note_type=f"child_linked:{kind}",
        )
        _audit(
            actor,
            "service_request.child_linked",
            request.id,
            before=before,
            after={"outcome": request.outcome, "outcome_kind": kind, "outcome_ref": ref},
        )
    return request


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def attach_interruption(
    actor: Any, request_id: Any, *, interruption_id: Any
) -> models.ServiceRequest:
    """A clerk says *"this report is about that burst main"* — `CR-072` §4.

    **THIS IS THE HALF OF THE RULING THAT MAKES THE OTHER HALF SAFE.** A
    stranger's form cannot settle whether something is an outage, so a report no
    longer opens one. Somebody has to, and it is a person who has read the
    reports: this function is that act, and `BR-CWP-101` is the rule.

    **MANY REPORTS, ONE INTERRUPTION.** Nothing here is unique — twelve people
    ringing about one burst main attach twelve requests to one operational
    record, which is the shape `CR-072` §4 asks for and the reason the link
    moved onto this table.

    ⚠ **ONLY A REPORT MAY CARRY ONE.** A move-in is not about a burst main, and
    a section that could render on any request would be an empty frame on every
    application in the product. `problem_kind` is the test, and it is refused by
    name rather than ignored.

    ⚠ **A REQUEST ALREADY ATTACHED IS REFUSED, THE SAME WAY `link_child`
    REFUSES A SECOND CHILD**, and for the same reason: a silent re-point would
    move a report off a record a clerk has already told somebody about. Moving a
    mis-attached report needs the clerk to be able to SEE the interruptions —
    and there is no list of them in this product, only the section on a report.
    That wave owns the correction; recorded in the decision log rather than
    guessed at here.

    **The interruption itself is written by `metering`'s own door** — this
    module never touches that table (B2 §2). All this writes is one nullable
    column on its own row, plus the event and the audit row every write here
    lands.
    """
    if not interruption_id:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.serviceRequest.fieldRequired",
            params={"field": "interruption_id"},
        )
    with transaction.atomic():
        request = request_row(request_id, lock=True)
        if not request.problem_kind:
            _refuse(
                errors.BIZ_STATE,
                "customers.serviceRequest.notAReport",
                br_ref="BR-CWP-101",
            )
        if request.interruption_id:
            _refuse(
                errors.BIZ_IDEMPOTENT,
                "customers.serviceRequest.interruptionAlreadyAttached",
                br_ref="BR-CWP-101",
            )
        request.interruption_id = interruption_id
        request.save(update_fields=["interruption_id", "updated_at"])
        _event(
            request,
            actor,
            kind=models.ServiceRequestEvent.KIND_SYSTEM,
            note=str(interruption_id),
            note_type="interruption_attached",
        )
        _audit(
            actor,
            "service_request.interruption_attached",
            request.id,
            before={"interruption_id": None},
            after={"interruption_id": str(interruption_id)},
        )
    return request


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def remove_fee_line(actor: Any, fee_id: Any, *, request_id: Any = None) -> models.ServiceRequest:
    """The fee table's remove icon on capture step 5 — **OQ-357 closed
    2026-09-23 as "both"**, because the PO approved the step-5 layout with both
    controls (*"i like this please use this"*): a Waive tick AND a remove icon
    on step 5, which is reachable only while the request is a DRAFT, and
    neither control on the review, the detail or the confirmation.

    **So: REMOVE while the request is a draft nobody has been quoted from; WAIVE,
    with a reason, once it has been** — OQ-357's own third reading, falling out
    of what was shown rather than added to it.

    **Refused, each by name:** a request that is no longer a DRAFT
    (`feeRemoveNotDraft` — the per-line waive is the door from then on); a line
    already WAIVED (`feeRemoveWaived` — a waiver is a decision somebody signed
    their name to, and removing the line would erase it); and a line already
    PAID (`feeRemovePaid`) — settled or invoiced, OR any counter money taken on
    the request, because a receipt was written against the quote this line is
    part of and removing it would leave the drawer disagreeing with the request.

    ⚠ **THE LINE IS DELETED AND THE AUDIT ROW IS WHAT REMAINS** (hard rule 7):
    `service_request.fee_removed` carries the line's code, quantity, unit price,
    amount and currency. **Worked:** a draft holding `CC-REQFEE` $25.00 and
    `CONN` $60.00 added by mistake → remove `CONN` → one line, quoted $25.00,
    and an audit row naming the $60.0000.

    ⚠ **HARD RULE 4 IS NOT TOUCHED.** A quote line on a draft is not an issued
    invoice, an invoice line, a payment or a journal entry, and nothing here
    posts: `service_request_fees` never reaches the ledger (B18 §4.6).
    """
    with transaction.atomic():
        fee = _fee_row(fee_id, lock=True)
        # A line addressed through ANOTHER request's URL is not this request's
        # to remove, and the answer is the one a missing row gets (HR-1).
        if request_id is not None and str(fee.request_id) != str(request_id):
            raise errors.deny_as_not_found("BR-TEN-003")
        request = request_row(fee.request_id, lock=True)
        if request.state != _SR.DRAFT:
            _refuse(
                errors.BIZ_STATE,
                "customers.serviceRequest.feeRemoveNotDraft",
                br_ref="OQ-357",
                charge_code=fee.charge_code,
            )
        if fee.waived:
            _refuse(
                errors.BIZ_STATE,
                "customers.serviceRequest.feeRemoveWaived",
                br_ref="OQ-357",
                charge_code=fee.charge_code,
            )
        taken = Decimal(request.fee_collected or "0") > 0
        if fee.settled_at is not None or fee.invoice_ref or taken:
            _refuse(
                errors.BIZ_STATE,
                "customers.serviceRequest.feeRemovePaid",
                br_ref="OQ-357",
                charge_code=fee.charge_code,
            )
        before = {
            "line_no": fee.line_no,
            "charge_code": fee.charge_code,
            "quantity": str(fee.quantity),
            "unit_amount": str(fee.unit_amount),
            "amount": str(fee.amount),
            "currency": fee.currency,
        }
        fee.delete()
        _audit(actor, "service_request.fee_removed", request.id, before=before, after=None)
    return request
