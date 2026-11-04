# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-001 (EP-CWP-01) — the guest surface reaches four writes and
#           nothing else · US-CWP-007 (EP-CWP-03) — *report a problem*, the
#           first of the four to be built.
# Rules:    BR-CWP-001 · BR-CWP-002 · BR-CWP-003 (every public function here is
#           one declared row of write_points.py; G81 refuses a fifth) ·
#           BR-CWP-026 (no guest write may change an account) · BR-CWP-076
#           (every request raised here carries channel `customer_portal`) ·
#           BR-CWP-027 (the reporter need not be a customer) · BR-CWP-012 (the
#           interruption belongs to `metering` and is written through ITS
#           service, never by this module reaching into its tables)
# Tests:    06-backend/tests/test_us_cwp_007_report.py ·
#           10-scripts/gates/g81_portal_write_points.py
# Impacts:  apps/portal/write_points.py (the register this file must match) ·
#           apps/portal/guest_api.py
# ───────────────────────────────────────────────────────
"""The portal SURFACE's write paths — the six of BR-CWP-001 and nothing else.

⚠ **IT WAS FOUR UNTIL 2026-09-04.** `contact_detail` is a Product Owner ruling
(`OQ-CWP-1562`): a signed-in customer may fix their own email, mobile and
postal address, and it updates the utility's master records. `account_link` is
a defect in our own extraction (`DEF-CWP-3768`) — `BR-CWP-009` specified that
write from the blueprint and the *four* never counted it. `write_points.py`
carries both provenances on the rows themselves.

FOUR of the six are built: the `service_request` kind (wave B's report, wave
C's application and quick asks), the `preference` kind (wave C's paperless
consent), and wave G's two — `contact_detail` and `account_link`. The other two
arrive with their waves and `write_points.py` says which. Each is ONE public
function here whose name is written into its row first, so G81 goes green on
the pair and red on either half alone.

⚠ **THE TWO WAVE-G FUNCTIONS WRITE NOTHING THEMSELVES.** `contacts`,
`addresses` and `customer_accounts` belong to `customers`, and a cross-module
write is forbidden — so both call `apps.customers.portal_self_service`, which
is that module's own named door. That is why `MODULE_WRITE_TABLES` did not have
to grow for either: a CALL is not an ORM write, and G84 can still say this file
writes exactly one model.

⚠ **ONE FUNCTION, THREE SHAPES, TWO WAVES — AND IT HAS TO BE ONE.** G81 allows
exactly one public function per declared kind, so a second `def` for the
application would fail the build BY NAME. Wave B built this as
`report_a_problem`; wave C renamed it `raise_service_request` and made the
report one `shape` of it, because *report a problem* is not a name an
application can live under and a rename is cheaper than the alternative — which
is a portal write nobody declared. The bodies are unchanged and private:
`_report`, `_application`, `_quick_ask`.

The back office's write to `portal_settings` is NOT here — it is a signed-in
System Admin's action on the utility's own row, in `settings_service.py`.

⚠ **WHY ONE FUNCTION WRITES TWO ROWS, AND WHY THAT IS NOT A FIFTH WRITE POINT.**
A report raises an INTERRUPTION (the network fact — `metering` owns it,
`CP-15`) and a SERVICE REQUEST (the clerk's worklist row — `customers` owns it,
`BR-CWP-076`). `BR-CWP-001`'s four KINDS were written before the interruption
record existed as anything but a drawing, and G81 requires the four to be
exactly four — so adding a fifth `kind=` would break the gate that encodes a
CONFIRMED rule. The honest shape is the one below: **the interruption is the
companion row of the service-request write point, created in the same
transaction by the owning module's own service, and `write_points.py` names it
in a `companions` field so it is DATA and not a paragraph.** Decision log
2026-09-04, with the reasoning and what would have to change to allow a fifth.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.customers import portal_self_service, service_request_service, temporary_stop
from apps.customers import service_request_documents
from apps.metering import interruptions as interruption_models
from apps.portal import applications, models, selectors, wording
from apps.portal.seams import customers_seam, tenancy_seam
from core import errors


SHAPE_REPORT = "report"
SHAPE_APPLICATION = "application"
SHAPE_QUICK_ASK = "quick_ask"
#: ⚠ **THE FOURTH SHAPE, 2026-09-04 (`US-CWP-051`) — AND IT IS A SHAPE RATHER
#: THAN A SEVENTH WRITE POINT BECAUSE `BR-CWP-066` SAYS SO IN ITS OWN WORDS:**
#: the control reads *"Ask for a payment plan"* and *"raises an ordinary service
#: request under `CR-072`, **never a request of a new kind**"*. `write_points.py`
#: is untouched, and G81 still sees exactly one public function per declared
#: kind. PO 2026-09-04, `OQ-1391` closed option (a), verbatim: *"Utility Clark
#: will di it for Consumer; COnsumer cannot do it by themself; these are special
#: cases"*.
SHAPE_PLAN_REQUEST = "plan_request"
#: ⚠ **THE FIFTH SHAPE, 2026-09-04 (`US-CWP-058`) — AND IT IS A SHAPE FOR THE
#: SAME REASON THE FOURTH IS.** `BR-CWP-089`: *"the portal never grants a
#: protection; each needs a person and a document"*, so *Send a certificate*
#: raises an ordinary service request a clerk judges and writes no
#: `AccountProtection` row. `write_points.py` is untouched.
SHAPE_HARDSHIP_ASK = "hardship_ask"

# ══ CR-068 wave R, 2026-09-04 — FOUR MORE SHAPES, AND TWO OF THEM DO NOT
#    CREATE ANYTHING ═══════════════════════════════════════════════════════
#
# ⚠ **THE NAME OF THE FUNCTION BELOW SAYS `raise` AND TWO OF ITS EIGHT SHAPES
# RAISE NOTHING — AND IT IS DELIBERATELY NOT RENAMED.** `G81` allows exactly
# ONE public function per declared write point, so this is the `service_request`
# kind's DOOR and `shape` is the ACT. `BR-CWP-075` (CONFIRMED) is what puts a
# withdrawal and a note behind that same door: *"The customer may make exactly
# four of the eleven request transitions: create a draft, submit, answer a
# question, withdraw."* Those four are the write point, not four write points.
#
# ⚠ **AND A RENAME IS EXACTLY WHAT PRODUCED `DEF-CWP-3735` — a 500 on a live
# guest screen, twelve hours ago.** Wave C renamed `report_a_problem` to this
# name and updated its OWN callers; a sibling lane's call site was invisible
# from its worktree and `POST /public/reports` broke for the whole branch. The
# same hazard is live right now with several lanes in several worktrees. So the
# MEANING is written here instead, which is the reading `STAFF_WRITE_MODULES`
# in `write_points.py` already takes of its own wrong name.
#
# `write_points.py` IS UNTOUCHED. Six kinds, one function, eight shapes.

#: `CWP-055` — *this bill is wrong*. **A MARKER BESIDE THE BILL, NEVER AN EDIT
#: OF IT** (`BR-CWP-042`, CLAUDE.md hard rule 4).
SHAPE_DISPUTE = "dispute"
#: `CWP-054` — *I do not understand this bill*, attached to the bill it is about.
SHAPE_QUESTION = "question"
#: `CWP-051` — the customer stops their own request (`BR-CWP-079`).
SHAPE_WITHDRAW = "withdraw"
#: `CWP-051` — the customer answers the clerk's question (`BR-CWP-075`).
SHAPE_NOTE = "note"
#: ⚠ **ONE MORE SHAPE, 2026-09-04 (`US-CWP-062`), AND A SHAPE FOR THE SAME
#: REASON EVERY OTHER ONE IS.** *Stop or restart service* is an ordinary
#: request a clerk works: `BR-CWP-075` allows the customer four of the eleven
#: transitions and a disconnect is one of them, and `BR-CWP-080` is explicit
#: that the account STAYS OPEN — so nothing here closes an account, moves a
#: balance or touches a service agreement. `write_points.py` is untouched and
#: G81 still sees exactly one public function per declared kind.
#:
#: ⚠ **THIS COMMENT CARRIED AN ORDINAL AND IT WENT STALE TWICE.** It said
#: *the fifth shape* until it was merged, was corrected to *a ninth*, and by
#: the end of the same day two more shapes had landed from sibling worktrees
#: and it was the tenth. Every lane counted correctly from what it could see —
#: the same mistake law 11's third family records for ids — so the ordinal is
#: GONE rather than corrected again. `dispatch` below is the list, it is four
#: lines away, and it cannot go stale. A count in prose that has been wrong
#: twice is a claim, not a fact (law 1).
SHAPE_STOP_RESTART = "stop_restart"
#: `CR-183-BRC10` B4 — *Restart my service now*, while a temporary stop is on.
#: A shape of the SAME write point, for the stop ask's reason.
SHAPE_RESTART_NOW = "restart_now"
#: `DEF-CWP-9049` (2026-10-02) — the applicant answers a clerk's *Ask for more*
#: with a file, from the Track page. A shape of the SAME write point, for the
#: reason the note and the withdrawal are: it is a move on a service request
#: the portal already raised, and `G81` allows one public function per kind.
SHAPE_REPLY_DOCUMENT = "reply_document"

#: What a quick ask records so a clerk can read it in words. `service_requests`
#: has NO `category` column — `US-CWP-015` §5 types the category as a
#: tenant-configurable FK and the code has neither the column nor the table
#: (`DEF-CWP-3701`) — so the chosen card's own label goes into
#: `what_they_said`, the column the product already keeps *"the applicant's own
#: words"* in.
QUICK_ASK_NOTE = customers_seam.QUICK_ASK_MARKER + " {label}"


def raise_service_request(tenant_id: Any, *, shape: str, payload: dict[str, Any]) -> dict[str, Any]:
    """THE `service_request` WRITE POINT — the one place a guest's form becomes
    work on the clerk's worklist.

    `BR-CWP-028`: every guest flow ends on a REFERENCE, because a guest has no
    inbox we hold and the reference is the entire record of the interaction.

    ⚠ **IT CHANGES NO ACCOUNT, EVER** (`BR-CWP-026`). `US-CWP-015` TC-3 is the
    test that says so out loud: somebody asking through *Something else* to have
    an account put in another name creates a request a clerk judges, and *"the
    account row is byte-identical afterwards"*.
    """
    if shape == SHAPE_REPORT:
        return _report(tenant_id, **payload)
    if shape == SHAPE_APPLICATION:
        return _application(tenant_id, payload)
    if shape == SHAPE_QUICK_ASK:
        return _quick_ask(tenant_id, payload)
    if shape == SHAPE_PLAN_REQUEST:
        return _plan_request(tenant_id, payload)
    if shape == SHAPE_HARDSHIP_ASK:
        return _hardship_ask(tenant_id, payload)
    if shape == SHAPE_DISPUTE:
        return _dispute(tenant_id, payload)
    if shape == SHAPE_QUESTION:
        return _question(tenant_id, payload)
    if shape == SHAPE_WITHDRAW:
        return _withdraw(tenant_id, payload)
    if shape == SHAPE_NOTE:
        return _note(tenant_id, payload)
    if shape == SHAPE_STOP_RESTART:
        return _stop_restart(tenant_id, payload)
    if shape == SHAPE_RESTART_NOW:
        return _restart_now(tenant_id, payload)
    if shape == SHAPE_REPLY_DOCUMENT:
        return _reply_document(tenant_id, payload)
    raise errors.ValidationError(
        errors.VAL_UNKNOWN_LOOKUP,
        message_key="portal.request.shapeUnknown",
        params={"value": str(shape)},
    )


#: The three shapes of the ONE `preference` write point. ⚠ **SHAPES RATHER
#: THAN THREE PUBLIC FUNCTIONS, AND IT IS NOT A STYLE CHOICE:** `G81` allows
#: exactly one public function per declared kind, and a second `def` in this
#: file fails the build by name. `raise_service_request` set the precedent on
#: 2026-09-04 when the payment-plan ask became its fourth shape; this is the
#: same move on the kind next door, and `write_points.py` is amended rather
#: than grown.
SHAPE_PAPERLESS_CONSENT = "paperless_consent"
SHAPE_WITHDRAW_PAPERLESS = "withdraw_paperless"
SHAPE_DELIVERY = "delivery_preferences"


def record_preference(tenant_id: Any, *, shape: str, payload: dict[str, Any]) -> Any:
    """THE `preference` WRITE POINT — how a customer wants to be reached.

    `BR-CWP-001` names *"a preference on the account"*; `BR-CWP-087` decides its
    SHAPE for paperless — *"a timestamp, the wording version, and a way to
    withdraw — not a toggle"* — and `CWP-025` adds the two channel switches and
    the language a customer may actually change.

    ⚠ **IT WAS CALLED `record_paperless_consent` UNTIL 2026-09-05** and took the
    consent's arguments directly. Renaming it is what `write_points.py`'s row
    means by *"one function, three shapes"*; nothing about the consent's
    behaviour moved, and `_paperless_consent` below is that function's body
    unchanged.
    """
    if shape == SHAPE_PAPERLESS_CONSENT:
        return _paperless_consent(tenant_id, **payload)
    if shape == SHAPE_WITHDRAW_PAPERLESS:
        return _withdraw_paperless(tenant_id, **payload)
    if shape == SHAPE_DELIVERY:
        return portal_self_service.update_delivery_preferences(
            payload["actor"],
            tenant_id=tenant_id,
            account_ids=list(payload["account_ids"]),
            payload=dict(payload["fields"]),
        )
    raise errors.ValidationError(
        errors.VAL_UNKNOWN_LOOKUP,
        message_key="portal.request.shapeUnknown",
        params={"value": str(shape)},
    )


def _withdraw_paperless(tenant_id: Any, *, account_ids: list[Any]) -> dict[str, Any]:
    """`US-CWP-028` TC-5 — **the row gains `withdrawn_on` and is NOT deleted.**

    ⚠ **A WITHDRAWN CONSENT AND AN ABSENT ONE ARE DIFFERENT FACTS** and the
    model's own docstring says so: *"the record of a consent that was given and
    then withdrawn is not the same fact as no consent at all"*. Deleting the row
    would also destroy the wording version — the only evidence of what the
    person was shown when they agreed.

    ⚠ **A ROW ALREADY WITHDRAWN IS LEFT ALONE**, so a double click does not move
    the date. The first withdrawal is when they changed their mind; a second
    stamp would quietly rewrite that.
    """
    stamped = 0
    for row in models.PortalConsent.objects.filter(
        tenant_id=tenant_id,
        account_id__in=[str(one) for one in account_ids],
        kind=models.PortalConsent.KIND_PAPERLESS,
        withdrawn_on__isnull=True,
    ):
        row.withdrawn_on = timezone.now()
        row.save(update_fields=["withdrawn_on"])
        stamped += 1
    return {"withdrawn": stamped}


def _paperless_consent(
    tenant_id: Any,
    *,
    service_request_id: Any,
    taken_on_screen: str,
    account_id: Any = None,
) -> models.PortalConsent:
    """The `paperless_consent` SHAPE — paperless, recorded.

    `BR-CWP-087`, verbatim: *"Paperless is a **recorded consent** — a timestamp,
    the wording version, and a way to withdraw — not a toggle."* So this writes
    a ROW and never a boolean on an account, which is the whole reason it is a
    preference write and not an account one.

    ⚠ **THE VERSION IS READ HERE, NEVER PASSED IN.** A browser that could name
    its own wording version could record a consent against words it never showed
    anybody. `wording.current_version()` is the one source.

    ⚠ **AND `agreed_on` IS THE SERVER'S CLOCK.** `03-field-map.md`: *"May never
    be in the future"* — the blueprint shipped a consent dated nineteen days
    after its own today. The database refuses a future value outright (migration
    `portal/0003`, on PostgreSQL); this is the other half, and it is why no
    caller may supply the timestamp.
    """
    return models.PortalConsent.objects.create(
        tenant_id=tenant_id,
        account_id=account_id,
        service_request_id=service_request_id,
        kind=models.PortalConsent.KIND_PAPERLESS,
        wording_version=wording.current_version("paperless"),
        agreed_on=timezone.now(),
        taken_on_screen=taken_on_screen,
    )


def update_own_contact_details(
    tenant_id: Any,
    *,
    actor: Any,
    account_ids: list[Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """THE `contact_detail` WRITE POINT — `BR-CWP-001` kind ⑤, and the first
    thing this portal may CHANGE in the utility's own books.

    The Product Owner's ruling of 2026-09-04 (`OQ-CWP-1562`), verbatim:
    *"maria can change her phone number and email ID and it will udpaet our
    master records also … once you login we ahve to allow them to change the
    details, otherwise it will not help"*.

    ⚠ **`BR-CWP-103` IS WHY THERE IS NO SECOND PASSWORD PROMPT HERE, AND IT IS
    NOT *NO CHECKS*.** The defence sits at the door — the one-time code to a
    stored contact, three tries, the lockout, the session's lifetime — and
    `BR-CWP-010`'s account-set intersection is still in every query below, so a
    landlord reaching for a tenant's contact row is refused exactly as before.
    What the ruling removes is friction on a customer editing their OWN record.

    ⚠ **`account_ids` COMES FROM THE SESSION AND NEVER FROM THE BODY.** The
    endpoint passes `principal.account_ids`; a payload that named accounts
    would be a customer choosing whose contact row to write.
    """
    return portal_self_service.update_contact_details(
        actor,
        tenant_id=tenant_id,
        account_ids=list(account_ids),
        payload=payload,
    )


def add_account_to_login(
    tenant_id: Any,
    *,
    actor: Any,
    customer_id: Any,
    account_id: Any,
) -> dict[str, Any]:
    """THE `account_link` WRITE POINT — `BR-CWP-001` kind ⑥ (`DEF-CWP-3768`).

    ⚠ **THE CALLER HAS ALREADY PROVED THE CODE, AND THIS FUNCTION CANNOT CHECK
    THAT.** `BR-CWP-033` puts a one-time code between *matched* and *linked*,
    and the code went to the contact **on the account being added** — never to
    the person adding it, or anyone with one account and a stolen bill number
    collects a second (`US-CWP-027` TC-3). The endpoint consumes the code and
    only then calls here; this docstring is where that contract is written
    down, because the function signature cannot express it.

    ⚠ **NOTHING IS COMBINED** (`BR-CWP-015`). One link row, no merged balance,
    no merged bill — `US-CWP-027` TC-7 asserts it.
    """
    return portal_self_service.link_account(
        actor,
        tenant_id=tenant_id,
        customer_id=customer_id,
        account_id=account_id,
    )


def submit_meter_reading(
    tenant_id: Any,
    *,
    actor: Any,
    account: Any,
    payload: dict[str, Any],
    today: Any,
) -> dict[str, Any]:
    """THE `meter_reading` WRITE POINT — `BR-CWP-001` kind ③, built
    2026-10-17 (`DEF-CWP-10175`, gap E of the PO's *"we need to clsoe these
    gaps"*; `US-CWP-042`).

    ⚠ **THREE CHECKS ARE HERE AND THE REST ARE METERING'S, UNCHANGED.**
      1. **The switch** (`CR-068` R8, `US-CWP-042` TC-7): `self_read_enabled`
         is the ONE portal switch that is OFF for a new tenant. Refused at the
         edge, never only hidden on the screen (`BR-CWP-002`).
      2. **The account** came off the signed-in session intersected IN THE
         QUERY (`api._account_in_set`, `BR-CWP-010`) — the body never names it.
      3. **The meter** must be one CURRENTLY assigned to that account's unit;
         `customer_reads.record_customer_read` answers a 404 for any other.

    Everything that JUDGES the figure is `BR-CWP-067`'s *one validation, two
    sources*: `apps.metering.customer_reads` stages, validates and commits it
    through the staff pipeline, accepts a warned reading WITH its flag and
    stamps the fourth source `customer` on every row (`BR-CWP-074`). This
    module writes no `meter_reads` row itself — a call, not an ORM write, so
    `MODULE_WRITE_TABLES` does not grow (the `contact_detail` precedent).

    ⚠ **A MASTER ACCOUNT HAS NO UNIT AND NO METER A CUSTOMER READS**
    (`BR-CUS-1010`) — refused as not found, the same answer a meter on
    somebody else's unit gets.
    """
    from apps.metering import customer_reads
    from apps.portal.seams.customers_seam import CHANNEL_CUSTOMER_PORTAL

    settings = selectors.settings_view(tenant_id)
    if not settings["is_live"] or not settings["self_read_enabled"]:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-002",
            message_key="portal.selfRead.notOffered",
        )
    if not getattr(account, "unit_id", None):
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    body = payload if isinstance(payload, dict) else {}
    return customer_reads.record_customer_read(
        unit_id=account.unit_id,
        meter=body.get("meter"),
        register=body.get("register"),
        value=body.get("value"),
        read_on=body.get("read_on"),
        today=today,
        actor={
            "portal_customer_id": str(getattr(actor, "customer_id", "") or "") or None,
            "portal_session_id": str(getattr(actor, "session_id", "") or "") or None,
            "account_id": str(account.pk),
            "channel": CHANNEL_CUSTOMER_PORTAL,
        },
    )


def _report(
    tenant_id: Any,
    *,
    kind: str,
    location_text: str,
    notes: str | None,
    reporter_name: str,
    reporter_phone: str,
) -> dict[str, Any]:
    """A passer-by reports a burst main. **ONE row, and its number is theirs.**

    Returns what `CWP-007` draws: the reference, when, where, what, and whether
    somebody has already reported the same street.

    ⚠ **THIS WROTE TWO ROWS UNTIL 2026-09-04 AND NOW WRITES ONE (`CR-072`).**
    It created the service request AND an `interruptions` row, and handed the
    stranger the INTERRUPTION's `RP-26-0412` while withholding the `SR-26-0049`
    the same call had just made. A clerk had two rows; the customer held the
    number of the one that is not the request. The Product Owner saw it on the
    live deployment and ruled: *"all the request coming from portal should go in
    Service request. if we have to icnrease the defination of Service request we
    should do it"*.

    **THE REPORT IS THE REQUEST** — somebody is asking the utility to do
    something, which is what a service request is. The CONFIRMED INTERRUPTION —
    *supply is off on Elm St between 1400 and 1500, back by 18:00* — is not a
    request at all: it is the utility's own operational record, opened by a
    CLERK who has judged the reports real, and it may gather MANY of them
    (`apps/customers/service_request_api.py`, the Interruption section).
    **A stranger's form cannot settle whether something is an outage**, and
    before this it was answering that question by writing the answer down.

    ⚠ **`gas_smell` NEVER REACHES THIS FUNCTION.** The guest edge answers the
    emergency phone number and calls nothing (`US-CWP-007` TC-3: *"the form
    returns (512) 555-0100 and creates nothing"*). The routing decision is at
    the EDGE rather than here because a service that "creates nothing" still had
    to be called to decide that, and the test that matters counts ROWS after the
    call.

    ⚠ **NO ACCOUNT IS TOUCHED, LINKED OR LOOKED UP** (`BR-CWP-026`). The
    reporter is not a customer, the address is free text, and no premises is
    resolved until a clerk does it (`BR-CWP-027`). Widening the request record
    did not weaken that: `problem_kind` is a radio button, not an account.
    """
    if kind not in interruption_models.STORABLE_KINDS:
        # Not a customer sentence: the edge refuses an unknown kind long before
        # this, and `gas_smell` is routed there. Reaching here is a wiring fault.
        raise ValueError(f"kind {kind!r} is not one this path may store")
    # ⚠ **ASKED BEFORE THE WRITE, AND THAT ORDER IS A TEST CASE.** Asked after,
    # the query finds the row this very call just created and every first report
    # is told somebody has already reported it (`US-CWP-007` TC-7 caught this on
    # the first run).
    already = selectors.already_reported_street(tenant_id, location_text)
    # ⚠ **ONE WRITE, SO NO `transaction.atomic()` HERE.** `create_from_portal`
    # opens its own — the number allocation, the state event and the audit row
    # are one act inside it. A wrapper around a single call would read as
    # though a second write were coming.
    request = service_request_service.create_from_portal(
        {
            "applicant_name": reporter_name,
            "applicant_phone": reporter_phone,
            "address_as_given": location_text,
            "what_they_said": notes,
            "problem_kind": kind,
        }
    )
    return {
        # ⚠ **THE `SR-` NUMBER, AND IT IS SERVED TO THE GUEST** (`BR-CWP-024`
        # as amended by `CR-072`: one reference, and it is the request's). The
        # `RP-` series is no longer customer-facing at all.
        "reference": request.request_no,
        "kind": request.problem_kind,
        "location_text": request.address_as_given,
        "reported_at": request.received_at.isoformat(),
        "status": selectors.report_progress_status(request),
        # `US-CWP-007` TC-7 — a sentence, never a refusal.
        "already_reported_street": already,
    }


# ── wave C's two shapes ─────────────────────────────────────────────────────


def _application(tenant_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /public/applications/{token}/submit` — `CWP-009`'s commit.

    ⚠ **WHAT THIS DELIBERATELY DOES NOT DO** (`US-CWP-014` §1): it demands no
    document up front, because *"a checklist you cannot yet upload to would
    stop the application dead"*.

    ⛔ **SUPERSEDED 2026-10-23 (`CR-191-BRC10`):** this paragraph also read *"it
    takes no money — fees are collected after approval"*. The PO ruled *"if
    there is a application or service fee then consumer will have to pay it
    online; they can't say pay later"*, so an application fee above $0.00 is
    now charged by card HERE, before the request exists
    (`_charge_the_application_fee`), and recorded with it.

    ⚠ **BUT IT CARRIES ANY DOCUMENT THE APPLICANT CHOSE TO ATTACH — `CR-158-BRC10`,
    PO 2026-10-01** (*"save those document to server for that Utility - and then
    clark should able to view those document in new request"*; `DF-4`
    superseded for this request only). Attaching stays OPTIONAL — the sentence
    above still holds — and every file held on the draft is handed, inside this
    same transaction, to the CUSTOMERS module's own door
    (`service_request_documents.attach_from_portal`), which files it in the
    document store and on the request. The draft's held copy is then deleted. If
    the hand-over fails, the whole submit rolls back: no request without its
    files, and no files without a request.

    ⚠ **AND WHAT IT REFUSES TO CARRY.** The applicant's date of birth and, for a
    business, their tax ID were collected for ONE purpose — recognising somebody
    who has held an account here before — and `PORTAL_CAPTURE_FIELDS` does not
    include either. So the VERDICT is recorded as an internal note in words, the
    identifiers are copied nowhere, and the draft's own copy of the date of
    birth is blanked the moment it has been used. A business applicant's tax ID
    stays on the draft, inside the tenant, behind RLS — and that is now a
    RULING rather than a wait: `OQ-CWP-1560` CLOSED 2026-09-04, option (b),
    *"stores a government identifier once instead of twice"*. It is READ from
    the draft by `customers.portal_seam.application_tax_id` — the request page
    shows its last four and the request's account doors carry it into a new
    company customer (`DEF-CWP-9045`, which found that this docstring still
    said OPEN and that nothing read the draft at all).
    """
    token = payload.get("token")
    paperless = bool(payload.get("paperless"))
    draft = applications.draft_row(tenant_id, token)
    if draft is None:
        raise errors.NotFoundError()
    if draft.submitted_at is not None:
        # TC-5 — a double-click is one request, one reference, one consent row.
        consent = models.PortalConsent.objects.filter(
            tenant_id=tenant_id, service_request_id=draft.service_request_id
        ).first()
        return {
            "reference": customers_seam.request_reference(draft.service_request_id),
            "request_id": str(draft.service_request_id),
            "consent_recorded": consent is not None,
            "idempotent_replay": True,
            # CR-191-BRC10 — a replay says what the FIRST attempt took, read
            # off the request, and charges nothing.
            "fee_paid": _fee_cell(customers_seam.request_fee_paid(draft.service_request_id)),
        }
    missing = applications.missing_before_submit(draft)
    if missing:
        # ⚠ THE DRAFT IS KEPT (US-CWP-013 TC-5). The refusal names the step.
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="portal.application.stepIncomplete",
            params={"step": missing[0]},
        )
    # 🔒 CR-191-BRC10 — a fee above $0.00 is charged HERE, before anything is
    # written; a decline or a silent provider raises and nothing is written.
    paid = _charge_the_application_fee(tenant_id, draft, payload)
    returning = _looks_like_a_returning_customer(draft)
    try:
        return _write_application(tenant_id, draft, paid=paid, paperless=paperless, returning=returning)
    except Exception as failure:
        if paid is None:
            raise
        # ⛔ THE CARD WAS APPROVED AND THE APPLICATION COULD NOT BE WRITTEN.
        # The request was not kept, so the customer is told so — never a
        # reference. The APPROVAL was kept on the draft before this write
        # (`_keep_the_approval`), so any later attempt — the same visit or
        # after a reload — records it and charges nothing (DEF-PAY-10554).
        from apps.portal.seams import payments_seam

        raise payments_seam.fee_not_recorded(paid.get("reference"), failure) from failure


#: 🔒 `DEF-PAY-10554` — the key the provider dedupes on, made by the SERVER from
#: the draft and its fee and KEPT ON THE DRAFT, so a reload, a double press and
#: a retry after a failed write all present the same key. ⛔ It read
#: `appfee:{tenant}:{draft token}:{browser attempt token}` until 2026-10-23,
#: and a reload minted a new browser token — a NEW key, so a second debit.
#: `declines` moves it on after a definite decline only, because a provider
#: answers a reused key with its FIRST answer (decision log 2026-10-23, *"one
#: charge per application, even across a reload"*). The draft's database id,
#: not its link token: this string goes to the provider and into the receipt's
#: `confirmation`, and the link token is the applicant's secret.
APPLICATION_FEE_KEY = "appfee:{tenant}:{draft}:{fee}:{declines}"


def _charge_the_application_fee(
    tenant_id: Any, draft: models.PortalApplicationDraft, payload: dict[str, Any]
) -> dict[str, Any] | None:
    """🔒 HUMAN-REVIEW-PENDING — `CR-191-BRC10` (PO 2026-10-23): *"if there is a
    application or service fee then consumer will have to pay it online; they
    can't say pay later"*.

    **None when there is nothing to pay** — no code marked, or a fee of $0.00
    (*"many time utilities charger 0 application fees"*): no card is asked
    for, and one sent is not charged. Otherwise the card is charged through the
    portal's existing rails (`payments_seam.charge_application_fee` →
    `gateway.charge()`), and what the provider approved is returned for
    `create_from_portal` to record.

    ⚠ **THE FEE IS RE-READ AND THE SCREEN'S FIGURE IS ONLY COMPARED**
    (`BR-CWP-058`'s reasoning, quick pay's guard): a price that moved since the
    applicant looked is refused BEFORE the card is touched. Compared as a
    Decimal, never a string or a float (hard rule 2).

    🔒 **ONE CHARGE PER DRAFT, WHATEVER THE BROWSER DOES (`DEF-PAY-10554`).**
    An approval this draft already holds is returned FIRST, before the fee,
    the card or the screen's figure is read: the money moved, so it is
    recorded and the provider is not asked again (decision log 2026-10-23,
    judgments 2 and 4). Otherwise the key is the server's (`_fee_key`), the
    approval is kept on the draft before anything else is written
    (`_keep_the_approval`), and a definite decline moves the key on.
    """
    from decimal import Decimal, InvalidOperation

    from apps.portal.seams import payments_seam, rating_seam

    held = _approved_charge_on(tenant_id, draft)
    if held is not None:
        return held
    fee = rating_seam.application_fee(tenant_id)
    if fee is None or fee <= 0:
        return None
    instrument = payload.get("instrument")
    if not isinstance(instrument, dict) or not str(instrument.get("token") or "").strip():
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="portal.quickPay.instrumentRequired",
            params={},
        )
    try:
        seen = Decimal(str(payload.get("fee_amount")))
    except (InvalidOperation, TypeError, ValueError):
        seen = None
    if seen is None or seen != fee:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-058",
            message_key="portal.quickPay.amountMoved",
        )
    key = _fee_key(tenant_id, draft, fee)
    try:
        paid = payments_seam.charge_application_fee(
            tenant_id,
            amount=fee,
            currency=customers_seam.tenant_currency(),
            instrument=instrument,
            idempotency_key=key,
        )
    except Exception as refusal:
        if payments_seam.charge_was_declined(refusal):
            # A definite NO: the next press needs a new key, or the provider
            # repeats this decline for ever. A silence keeps its key.
            _fee_declined(tenant_id, draft)
        raise
    approved = {
        "amount": str(paid["amount"]),
        "currency": paid["currency"],
        "reference": paid["reference"],
        "brand": paid.get("method_brand"),
        "last_four": paid.get("method_last_four"),
        "run_id": paid.get("run_id"),
        "environment": paid.get("environment"),
    }
    try:
        _keep_the_approval(tenant_id, draft, approved)
    except Exception as failure:
        # The money moved and not even the marker could be kept. The KEY was
        # kept before the charge, so a retry presents it again and the
        # provider dedupes; the applicant is told nothing was recorded.
        raise payments_seam.fee_not_recorded(approved["reference"], failure) from failure
    return approved


def _approved_charge_on(tenant_id: Any, draft: models.PortalApplicationDraft) -> dict[str, Any] | None:
    """🔒 `DEF-PAY-10554` — the provider's approval this draft already holds, or
    None. Re-read from the row, never from the object the request started
    with: a sibling press may have written it a moment ago."""
    held = (
        models.PortalApplicationDraft.objects.filter(tenant_id=tenant_id, pk=draft.pk)
        .values_list("fee_charge_approved", flat=True)
        .first()
    )
    return dict(held) if isinstance(held, dict) and held.get("reference") else None


def _fee_key(tenant_id: Any, draft: models.PortalApplicationDraft, fee: Any) -> str:
    """🔒 `DEF-PAY-10554` — the key for THIS draft at THIS fee, written to the
    draft BEFORE the card is charged, in its own transaction block (a savepoint
    when nested — law 14), so it outlives a failed write and a reload.
    Deterministic, so two presses racing to make it make the same string."""
    from decimal import Decimal

    declines = (
        models.PortalApplicationDraft.objects.filter(tenant_id=tenant_id, pk=draft.pk)
        .values_list("fee_declines", flat=True)
        .first()
    ) or 0
    key = APPLICATION_FEE_KEY.format(
        tenant=tenant_id,
        draft=draft.pk,
        fee=Decimal(str(fee)).quantize(Decimal("0.0001")),
        declines=int(declines),
    )
    with transaction.atomic():
        models.PortalApplicationDraft.objects.filter(tenant_id=tenant_id, pk=draft.pk).update(
            fee_idempotency_key=key
        )
    return key


def _fee_declined(tenant_id: Any, draft: models.PortalApplicationDraft) -> None:
    """A definite decline moves the key on by one (`DEF-PAY-10554` judgment 3)."""
    from django.db.models import F

    with transaction.atomic():
        models.PortalApplicationDraft.objects.filter(tenant_id=tenant_id, pk=draft.pk).update(
            fee_declines=F("fee_declines") + 1, fee_idempotency_key=None
        )


def _keep_the_approval(
    tenant_id: Any, draft: models.PortalApplicationDraft, approved: dict[str, Any]
) -> None:
    """⚠ `DEF-PAY-10554` — THE APPROVAL IS WRITTEN BEFORE THE REQUEST IS.

    In its OWN `transaction.atomic()`: with no outer transaction (a live
    request; there is no `ATOMIC_REQUESTS`) it COMMITS here; nested, it is a
    savepoint the request write's rollback cannot reach, because that write is
    a separate block opened after this one closes (law 14; proved on
    PostgreSQL by `test_cr191_portal_application_fee_online.py`). Any later
    attempt finds it (`_approved_charge_on`) and records it instead of
    charging. Our gateway adapters offer no way to ask a provider *"did you
    already approve this key?"*, which is why the draft has to remember."""
    with transaction.atomic():
        models.PortalApplicationDraft.objects.filter(tenant_id=tenant_id, pk=draft.pk).update(
            fee_charge_approved=approved
        )


def _write_application(
    tenant_id: Any,
    draft: models.PortalApplicationDraft,
    *,
    paid: dict[str, Any] | None,
    paperless: bool,
    returning: bool,
) -> dict[str, Any]:
    """`_application`'s one transaction, lifted out so a failure after an
    approved charge can be answered as such (`CR-191-BRC10`). Every line below
    is as it was, plus `online_fee=paid` and the lock below."""
    with transaction.atomic():
        # ⚠ CR-191-BRC10 — TWO PRESSES IN FLIGHT AT ONCE ARE ONE APPLICATION.
        # Each was charged under the SAME key (one debit at the provider); the
        # draft row is locked here and re-read, so the second waits for the
        # first and then answers its reference instead of writing a second
        # request and a second receipt (hard rule 6).
        locked = (
            models.PortalApplicationDraft.objects.select_for_update()
            .filter(tenant_id=tenant_id, pk=draft.pk)
            .only("id", "submitted_at", "service_request_id")
            .first()
        )
        if locked is not None and locked.submitted_at is not None:
            return {
                "reference": customers_seam.request_reference(locked.service_request_id),
                "request_id": str(locked.service_request_id),
                "consent_recorded": models.PortalConsent.objects.filter(
                    tenant_id=tenant_id, service_request_id=locked.service_request_id
                ).exists(),
                "idempotent_replay": True,
                "fee_paid": _fee_cell(customers_seam.request_fee_paid(locked.service_request_id)),
            }
        request = service_request_service.create_from_portal(
            {
                "applicant_kind": draft.applicant_kind or applications.KIND_PERSON,
                "applicant_name": _applicant_name(draft),
                "applicant_email": draft.email,
                "applicant_phone": draft.phone,
                "address_as_given": draft.address_as_given,
                "address_unit_as_given": draft.address_unit_as_given,
                # DEF-CWP-9817 — the town and ZIP typed on step 1, into the
                # request's own `BR-CUS-1091` columns (what was SAID), so the
                # Approve window matches on them as it does for a clerk.
                "address_city_as_given": draft.address_city_as_given,
                "address_postal_code_as_given": draft.address_postal_code_as_given,
                # ⊕ DEF-CWP-10541 — the state the form showed (the matched
                # premises', else the utility's own); the portal asks none.
                "address_state_as_given": selectors.draft_service_state(draft),
                "requested_start": draft.requested_start,
                "what_they_said": _what_they_said(draft),
                # `DEF-CWP-9046` — a PERSON's date of birth reaches the request
                # (stored once, there; blanked on the draft below). A business
                # carries none: the request refuses it for that kind.
                **(
                    {"date_of_birth": draft.date_of_birth}
                    if draft.date_of_birth and draft.applicant_kind != applications.KIND_BUSINESS
                    else {}
                ),
                # ⊕ DEF-CUS-10250 — Move-in's fields, carried as typed (PO
                # 2026-10-18: *"ALSO DATA COLECTED IS NOT LOST"*), onto the
                # SAME request columns the staff capture writes (lane CF-1's
                # `customers/0087`), so the move-in prefill reads one place.
                # The co-applicant travels only when the box was ticked: an
                # unticked card's leftovers are not somebody on the account.
                **_co_applicant_of(draft),
                "contact_by": draft.contact_by,
                # ⊕ DEF-CUS-10252 — the mailing block onto the request's own
                # `mailing_*` columns, so the move-in prefills it.
                **_mailing_of(draft),
                # The draft's NULL (*not said*) is the request's `False`: the
                # request's Preferences are two plain ticks.
                "paperless": bool(draft.paperless),
                "sms_reminders": bool(draft.text_reminders),
                "preferred_language": draft.preferred_language,
            },
            # 🔒 DEF-CUS-10225 — the SSN last four, its own keyword, encrypted
            # on the request; blanked on the draft below.
            ssn_last4=draft.ssn_last4,
            # `DEF-CUS-9034` — the ticks become the request's service rows, so
            # the clerk's Services table and the job it raises are not empty.
            service_codes=draft.service_codes,
            # ⊕ `CR-161-BRC10` W7 — the answers to the utility's own questions,
            # narrowed to the fields STILL asked on the portal (one switched to
            # *Don't ask* since it was typed does not travel). They land on the
            # request's own copy, where Request detail shows them read-only and
            # Approve copies them with the side-by-side pick (W6).
            custom_data=tenancy_seam.application_custom_answers(tenant_id, draft.custom_data),
            # 🔒 DEF-CUS-9819 (PO 2026-10-06, option (a)) — an application
            # arrives with the utility's application fee already on it.
            application=True,
            # ⊕ `DEF-CWP-9818` — the applicant's category pick (PO ruling
            # 2026-10-06, option b); the clerk can still change it.
            category={
                "account_type_code": draft.account_type_code,
                "account_subtype_code": draft.account_subtype_code,
            },
            # 🔒 CR-191-BRC10 — what the card provider approved, or None.
            online_fee=paid,
            # ⊕ CR-200-BRC10 S9 — the premises the draft's own check matched
            # and the apartment picked by label, so the request arrives linked
            # (`applications.place_for`; nothing a browser sent names a row).
            resolved_place=applications.place_for(
                tenant_id, draft.matched_premises_id, draft.address_unit_as_given
            ),
        )
        if returning:
            # ⚠ A FLAG FOR A CLERK, IN WORDS, AND NOTHING FOR THE APPLICANT
            # (US-CWP-013 TC-2). It names no candidate and no identifier: what a
            # clerk needs is to run their own search, which they can.
            service_request_service.note_from_portal(
                request.id,
                note=(
                    "The details on this application match somebody already on file. "
                    "Check before opening a new customer record."
                ),
                note_type="possible_returning_customer",
            )
        consent = None
        if paperless:
            consent = _paperless_consent(
                tenant_id,
                service_request_id=request.id,
                taken_on_screen=wording.SCREEN_NEW_CONNECTION,
            )
        # CR-158-BRC10 — the applicant's files travel with the application.
        staged = applications.staged_files(draft)
        if staged:
            service_request_documents.attach_from_portal(request.id, staged)
            applications.discard_staged(draft)
        draft.service_request_id = request.id
        draft.submitted_at = timezone.now()
        # Used, and now gone (see the docstring). `tax_id` stays — OQ-CWP-1560
        # (b): stored once, here, and read through `customers.portal_seam`.
        draft.date_of_birth = None
        # DEF-CUS-10225 — the SSN last four is stored once, on the request.
        draft.ssn_last4 = None
        draft.save(
            update_fields=[
                "service_request_id",
                "submitted_at",
                "date_of_birth",
                "ssn_last4",
                "updated_at",
            ]
        )
    return {
        "reference": request.request_no,
        "request_id": str(request.id),
        # ⚠ TC-2: sending it UNTICKED succeeds and writes NO consent row. An
        # absent consent is not a withdrawn one, so nothing is written to say
        # they declined — there is simply no row.
        "consent_recorded": consent is not None,
        "idempotent_replay": False,
        # CR-191-BRC10 — `{amount, currency}` the applicant paid, or None.
        "fee_paid": _fee_cell(customers_seam.request_fee_paid(request.id)),
    }


def _fee_cell(paid: dict[str, str] | None) -> dict[str, Any] | None:
    """The paid fee as the guest surface's one money cell (`portal/money.py`):
    the stored four places and the displayed two, both on the wire."""
    from apps.portal import money

    if paid is None:
        return None
    return money.amount(paid["amount"], currency=paid["currency"])


def _mailing_of(draft: Any) -> dict[str, Any]:
    """The applicant's *Mailing address*, as the request's mailing columns.

    DEF-CUS-10252: ticked *Same as service address* → `mailing_same` and
    nothing else; unticked → the five parts as typed (already checked for
    shape on the draft: a state code, a US ZIP). The capture cleaner mirrors
    them into `billing_*_as_given` (lane CF-1's `MAILING_TO_BILLING`).
    """
    if draft.mailing_same_as_service:
        return {"mailing_same": True}
    return {
        "mailing_same": False,
        "mailing_line1": draft.mailing_line1,
        "mailing_line2": draft.mailing_line2,
        "mailing_city": draft.mailing_city,
        "mailing_state": draft.mailing_state,
        "mailing_postal_code": draft.mailing_postal_code,
    }


def _co_applicant_of(draft: Any) -> dict[str, Any]:
    """The co-applicant card, as ONE of the request's `co_applicants` — or
    nothing.

    DEF-CUS-10250: only a TICKED *Add a co-applicant* carries a person; the
    draft keeps what was typed into a card later unticked, and that is not
    somebody the applicant put on the account. The card is Move-in's co-owner
    card (lane CF-1's `co_applicants`, cleaned by `move_in_people`'s own
    rules), so the move-in the request becomes opens with it. The portal asks
    no SSN, licence or *responsible for bills* for a co-applicant (image
    `04-portal.png`), so none is sent; the request mirrors the first card into
    `co_applicant_name/email/phone` itself.
    """
    if not draft.co_applicant:
        return {}
    dob = draft.co_applicant_date_of_birth
    card = {
        "full_name": draft.co_applicant_name,
        "relationship": draft.co_applicant_relationship,
        "phone": draft.co_applicant_phone,
        "email": draft.co_applicant_email,
        "date_of_birth": dob.isoformat() if dob else None,
    }
    return {"co_applicants": [{key: value for key, value in card.items() if value not in (None, "")}]}


def _quick_ask(tenant_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /public/requests` — `CWP-010`'s six cards.

    Each is the same request record with a different category, and the category
    comes from the utility's own list (`selectors.quick_service_categories`) —
    never a hardcoded one (`US-CWP-015` TC-7).
    """
    category = payload.get("category") or {}
    # ⊕ CR-200-BRC10 S9 — *Ask us for something* gets the SAME suggestions as
    # Start service (PO 2026-10-29, *"-A"*): a picked one arrives as its parts
    # and is re-matched HERE, so the request is linked to that premises (and
    # the apartment picked) and *"the clerk does not look it up"*. An address
    # with no match is still accepted exactly as typed (`BR-CUS-070`).
    street = str(payload.get("street") or "").strip()
    city = str(payload.get("city") or "").strip()
    postal_code = str(payload.get("postal_code") or "").strip()
    unit_label = str(payload.get("unit") or "").strip()
    place = applications.place_from_parts(
        tenant_id, street, city=city, postal_code=postal_code, unit_label=unit_label
    )
    said: dict[str, Any] = {"address_as_given": payload.get("address")}
    if place is not None:
        said = {
            "address_as_given": street,
            "address_city_as_given": city or None,
            "address_postal_code_as_given": postal_code or None,
            "address_unit_as_given": unit_label or None,
        }
    request = service_request_service.create_from_portal(
        {
            "applicant_kind": applications.KIND_PERSON,
            "applicant_name": payload.get("name"),
            "applicant_email": payload.get("email"),
            "applicant_phone": payload.get("phone"),
            **said,
            "what_they_said": _quick_ask_words(category, payload),
        },
        resolved_place=place,
    )
    return {"reference": request.request_no, "request_id": str(request.id)}




# ── wave M's shape — *ask for a payment plan* (US-CWP-051) ──────────────────


#: What the clerk reads on their worklist. **The whole previewed schedule in one
#: sentence**, because `create_from_portal` refuses an account and every other
#: field this ask needs (`PORTAL_CAPTURE_FIELDS`), so `what_they_said` is where
#: the facts go — the column this product already keeps *"the applicant's own
#: words"* in.
#:
#: ⚠ **THE ACCOUNT IS NAMED BY ITS NUMBER** (B14 rule 31): `ACC-10519-C`, the
#: number printed on the paper bill, never a row id and never part of one.
PLAN_ASK_NOTE = (
    customers_seam.PLAN_ASK_MARKER + " {account_no}: "
    "{balance} spread over {months} monthly instalments from {first_due_on}, "
    "with {down_payment} up front. {base_count} instalments of {base_amount} and a "
    "final {final_amount}, totalling {spread}."
)


def _plan_request(tenant_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST accounts/{id}/plans/request` — the customer ASKS; a clerk grants.

    ⚠ **NOTHING ACTIVATES AND NOTHING IS HELD.** No `payment_plan` row is
    written, no instalment is scheduled, no late fee stops and the collections
    ladder keeps running until a clerk grants the plan through the S24 wizard
    that has existed since 2026-08-16. `BR-CWP-066` (PO 2026-09-04, `OQ-1391`
    closed option (a)): *"A PAYMENT PLAN IS GRANTED BY A CLERK. A CUSTOMER MAY
    ASK FOR ONE AND MAY NOT CREATE, ACTIVATE OR AUTO-QUALIFY FOR ONE."*

    ⚠ **THERE IS NO SELF-SERVE PATH TO STUB, AND THAT IS WHY `US-CWP-051` TC-10
    ASSERTS A REFUSAL RATHER THAN A `NotImplementedError`.** `J41` step 5 was
    written while `OQ-1391` was open and says the activation path *"raises
    `NotImplementedError("OQ-1391")`"*; the question CLOSED on 2026-09-04 and the
    answer is that the path does not exist at all. A stub would be a door.

    ⚠ **THE SCHEDULE IS QUOTED, NEVER RE-DERIVED.** The figures in the sentence
    below are the ones `payments_seam.plan_preview` served the screen, which came
    out of `payment_plan.build_schedule` — ❄️ GT-47. Recomputing them here would
    put a third answer between the customer's screen and the clerk's wizard.

    ⚠ **THE CALLER HAS ALREADY INTERSECTED THE ACCOUNT WITH THE SESSION'S SET**
    (`BR-CWP-010`) and passes the account NUMBER, so nothing here looks an
    account up and `create_from_portal`'s *"it links no account and changes
    none"* (`BR-CWP-026`) is untouched.
    """
    request = service_request_service.create_from_portal(
        {
            "applicant_kind": applications.KIND_PERSON,
            "applicant_name": payload.get("name"),
            "applicant_email": payload.get("email"),
            "applicant_phone": payload.get("phone"),
            # ⚠ **REQUIRED BY `create_from_portal` — *"there is no such thing as
            # a service request about nowhere"* (`BR-CUS-070`) — AND IT IS
            # DERIVED BY WALKING TO THE PREMISES, NEVER STORED HERE** (hard rule
            # 8, `BR-MET-1161`). The caller reads it off the account it has
            # already proved is in this session's set; this module holds no
            # address column and looks nothing up.
            "address_as_given": payload.get("address"),
            "what_they_said": _plan_ask_words(payload),
        }
    )
    return {
        "reference": request.request_no,
        #: ⚠ **STATED ON THE WIRE SO NO SCREEN CAN IMPLY OTHERWISE.** A customer
        #: who pressed *Ask for this plan* has a request on a clerk's worklist
        #: and no plan; the confirmation says exactly that.
        "plan_created": False,
        "granted_by": "clerk",
    }


def _plan_ask_words(payload: dict[str, Any]) -> str:
    """The clerk's sentence. Every figure is the preview's, carried not computed."""
    words = str(payload.get("note") or "").strip()
    line = PLAN_ASK_NOTE.format(
        account_no=str(payload.get("account_no") or "not stated"),
        balance=str(payload.get("balance") or "0.00"),
        months=str(payload.get("term_months") or "?"),
        first_due_on=str(payload.get("first_due_on") or "not stated"),
        down_payment=str(payload.get("down_payment") or "0.00"),
        base_count=str(payload.get("base_instalment_count") or "?"),
        base_amount=str(payload.get("base_amount") or "0.00"),
        final_amount=str(payload.get("final_amount") or "0.00"),
        spread=str(payload.get("spread") or "0.00"),
    )
    if words:
        line = f"{line} {words}"
    return line[:2000]

# ── wave R's four shapes — query a bill, ask a question, withdraw, add a note ─


#: What the clerk reads when a customer QUERIES a bill. The whole claim in one
#: sentence, because `create_from_portal` refuses an invoice, an account and
#: every other field this ask needs (`PORTAL_CAPTURE_FIELDS`) — so
#: `what_they_said` is where the facts go, the column this product already keeps
#: *"the applicant's own words"* in.
#:
#: ⚠ **IT OPENS WITH `customers_seam.DISPUTE_MARKER`, AND THAT IS LOAD-BEARING
#: RATHER THAN DECORATIVE.** `open_query_on_bill` matches on those words to
#: answer *"you have already queried this bill"* (`US-CWP-065` TC-9), because
#: `service_requests` has no `invoice_id` column to match on (`DEF-CWP-3881`).
#: The writer and the reader therefore share ONE constant and a grep finds both.
#:
#: ⚠ **THE BILL IS NAMED BY ITS NUMBER** (B14 rule 31): `BL-2608-0141`, printed
#: on the paper the customer is holding, never a row id.
DISPUTE_NOTE = (
    "{marker} bill {bill_number} ({period}, {total}): {what}. "
    "Their reason: {reason}."
)
#: Appended only when the customer read their own meter today. ⚠ **EVIDENCE ON
#: THE QUERY AND NOT A METER READ** (`US-CWP-065` §5, TC-8) — a figure a customer
#: typed into a complaint form has not been through `metering`'s validation, its
#: rollover check or its review state, and writing it as a read would put an
#: unverified number where the bill run looks.
OWN_READING_NOTE = " They read the meter themselves today: {reading}."

QUESTION_NOTE = "{marker} {topic}. {what}"
QUESTION_BILL_NOTE = " About bill {bill_number}."


def _dispute(tenant_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST bills/{number}/dispute` — `CWP-055`. **A MARKER, NEVER AN EDIT.**

    ⚠ **THE BILL IS NOT TOUCHED, AND THAT IS CLAUDE.md HARD RULE 4 WEARING A
    SCREEN.** No `Invoice` row is read for writing, no total moves, no line is
    added and no status changes: this function creates ONE service request
    beside the bill and returns its reference. `US-CWP-065` TC-2 asserts the
    invoice is byte-identical afterwards, field by field, because a screen that
    appeared to edit a bill would be describing a database this product does not
    have.

    ⚠ **AND IT DOES NOT WRITE THE `meter_reads` DISPUTE MARKER EITHER — THAT IS
    `OQ-CWP-1681`, MINTED RATHER THAN CHOSEN.** `US-CWP-065` TC-1 says the
    reading *"shows a dispute marker"*, and `metering.services.dispute_read` is
    `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` under `BR-MET-035`, holds the
    account out of the next bill run (`BR-MET-024`) and is cleared only by a
    System Admin. A customer reaching it would be a customer holding themselves
    out of a bill run on their own say-so, and it is not one of `BR-CWP-001`'s
    six kinds of portal write. **So a clerk raises the marker after reading the
    request** — which is the same shape `BR-CWP-066` gives a payment plan — and
    the question of whether the portal should trigger it automatically is put to
    the Product Owner rather than answered here.

    ⚠ **NOTHING IS HELD AND THE SCREEN SAYS SO.** `US-CWP-065`'s consequence box
    promises *"we hold collection on `$142.18` · no late fee while we look"*.
    `BR-MET-133` clause 4 is built and needs the DISPUTED AMOUNT, and **nothing
    in this product records one** — `OQ-420`, OPEN since 2026-08-26, where
    `late_fee.ageable_portion` raises rather than choosing between the two
    fallbacks that are `$137.20` apart on the rule's own bill. Printing the
    promise anyway would be hard-won law 1 on a customer's money.
    """
    bill_number = str(payload.get("bill_number") or "").strip()
    request = service_request_service.create_from_portal(
        {
            "applicant_kind": applications.KIND_PERSON,
            "applicant_name": payload.get("name"),
            "applicant_email": payload.get("email"),
            "applicant_phone": payload.get("phone"),
            "address_as_given": payload.get("address"),
            "what_they_said": _dispute_words(payload),
        }
    )
    _keep_their_own_words(request, payload.get("what"), payload.get("reason"))
    return {
        "reference": request.request_no,
        "bill_number": bill_number,
        #: ⚠ **STATED ON THE WIRE SO NO SCREEN CAN IMPLY OTHERWISE** — the same
        #: posture `plan_created: false` takes one screen along.
        "bill_changed": False,
        "collection_held": False,
        "reading_marked": False,
    }


def _question(tenant_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST questions` — `CWP-054`, and the bill travels with it.

    ⚠ **ATTACHING THE QUESTION TO A BILL IS THE WHOLE STORY** (`US-CWP-066` §1:
    *"a free-text message with no context becomes a phone call anyway"*). The
    clerk's worklist row NAMES the bill in its first sentence — TC-1 — so
    nobody has to ring back to find out which one is meant.

    ⚠ **A QUESTION WITH NO BILL IS ACCEPTED** (TC-5): it is a general question,
    routed by its topic, and refusing it would send somebody to the telephone
    for the crime of not knowing which bill they meant.
    """
    request = service_request_service.create_from_portal(
        {
            "applicant_kind": applications.KIND_PERSON,
            "applicant_name": payload.get("name"),
            "applicant_email": payload.get("email"),
            "applicant_phone": payload.get("phone"),
            "address_as_given": payload.get("address"),
            "what_they_said": _question_words(payload),
        }
    )
    _keep_their_own_words(request, payload.get("what"))
    return {
        "reference": request.request_no,
        "bill_number": str(payload.get("bill_number") or "").strip() or None,
    }


def _keep_their_own_words(request: Any, *parts: Any) -> None:
    """Keep what the CUSTOMER typed as the CUSTOMER's own entry on the thread.

    ⚠ **WHY THIS EXISTS, AND IT IS `DEF-CWP-4198` SEEN FROM THE OTHER END.**
    `what_they_said` is documented as *"the applicant's own words"* and four
    portal shapes compose a CLERK's sentence into it instead, because there is
    no other column for the facts (`DEF-CWP-3881`). `CWP-046` printed that
    sentence in a column headed WHAT and `CWP-051` printed it in the thread
    under **You** — so Ana read, of herself, *"Queried through the customer
    portal bill BL-2608-000044 (2026-07-01 to 2026-07-31, 843.36 USD): … Their
    reason: …"*. Measured on the live demo on 2026-09-08: **271 characters**,
    two ISO dates and the third person.

    ⚠ **THE CLERK'S SENTENCE IS NOT TOUCHED.** It stays exactly as it was —
    `open_query_on_bill` matches on it, the worklist reads it, and a change
    there would be a change to a staff surface this wave has no business
    making. What is added is a SECOND row carrying only the customer's own
    text, flagged `customer_visible`, which is what `note_from_portal` was
    built for (`BR-CWP-078`).

    ⚠ **BEST EFFORT, BY DESIGN.** A note is a nicety on a request that already
    exists; failing the whole write because the thread could not be decorated
    would refuse a customer's query over a cosmetic row. The exception is
    swallowed and named. ⚠ **AND IT IS A SAVEPOINT** (CLAUDE.md hard-won law
    14): on PostgreSQL a failed statement poisons the whole transaction, so a
    bare `except` here would lose the REQUEST as well — the suite runs on
    SQLite, which has no such state, and would pass either way.
    """
    from django.db import transaction as _transaction

    #: ⚠ **JOINED WITH A FULL STOP, BECAUSE THE TWO HALVES ARE TWO SENTENCES.**
    #: `CWP-055` sends the reason the customer PICKED off the list and the one
    #: they TYPED, and the first carries no punctuation — a bare space made
    #: *"The amount is higher than I expected We were away…"*, read live on
    #: 2026-09-08 before this line existed.
    written: list[str] = []
    for part in parts:
        text = str(part or "").strip()
        if not text:
            continue
        written.append(text if text[-1] in ".?!" else f"{text}.")
    said = " ".join(written)
    if not said:
        return
    try:
        with _transaction.atomic():
            service_request_service.note_from_portal(
                request.pk,
                note=said[:2000],
                note_type="customer_note",
                customer_visible=True,
            )
    except Exception:  # noqa: BLE001 — see the docstring: the request stands.
        return


def _withdraw(tenant_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST requests/{ref}/withdraw` — `CWP-051`, `BR-CWP-079`.

    ⚠ **THE CALLER HAS ALREADY PROVED THE REQUEST IS THIS LOGIN'S**
    (`customers_seam.my_request`, tenant and the login's own contact facts in
    the query) and passes the ROW ID it found. Nothing here looks a reference
    up: a function that did would be a second answer to *whose request is this*.

    ⚠ **THE REFUSAL AFTER APPROVAL IS THE STATE TABLE'S, NOT THIS FILE'S**
    (TC-5). `withdraw_from_portal` reaches `_apply`, which asks
    `service_request.TRANSITIONS` and raises `BIZ_STATE` — so the portal cannot
    drift from the rule a clerk's own withdrawal obeys.
    """
    request = service_request_service.withdraw_from_portal(payload["request_id"])
    return {
        "reference": request.request_no,
        "status": request.state,
        #: `BR-CWP-079`, said on the wire: *"withdrawing does not touch the
        #: account"*. `US-CWP-063` TC-4 asserts the account row afterwards.
        "account_changed": False,
    }


def _note(tenant_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST requests/{ref}/notes` — the customer answers the clerk's question.

    ⚠ **`customer_visible=True`, AND IT IS THE FIRST ROW IN THIS PRODUCT THAT
    CARRIES IT.** `service_request_events.internal` has defaulted `True` since
    the table was created, with *"there is no portal"* written beside it; there
    is one now (`BR-CWP-078`). A customer hidden from their own sentence would
    be the flag doing the opposite of its job.
    """
    event = service_request_service.note_from_portal(
        payload["request_id"],
        note=str(payload.get("note") or ""),
        note_type="customer_note",
        customer_visible=True,
    )
    return {"at": event.at.isoformat(), "customer_visible": not event.internal}


def _reply_document(tenant_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /portal/public/track/documents` — the file a clerk asked for.

    ⚠ **THE CALLER HAS ALREADY PROVED THE REQUEST** with its reference and the
    second fact `track` asks for (`selectors.tracked_request_id`) and passes
    the ROW ID plus a file `applications.read_upload` has already judged. The
    state rule (only `more_info`), the five-file figure, the store, the audit
    and the History row are all customers' (`attach_reply_from_portal`).
    """
    service_request_documents.attach_reply_from_portal(
        payload["request_id"],
        name=payload["name"],
        content_type=payload["content_type"],
        payload=payload["payload"],
    )
    return {"sent": payload["name"]}


def _dispute_words(payload: dict[str, Any]) -> str:
    """The clerk's sentence. Every figure is the SERVER's — the bill's own total
    and period as the bill read serves them, carried and never recomputed."""
    line = DISPUTE_NOTE.format(
        marker=customers_seam.DISPUTE_MARKER,
        bill_number=str(payload.get("bill_number") or "not stated"),
        period=str(payload.get("period") or "not stated"),
        total=str(payload.get("total") or "not stated"),
        what=str(payload.get("what") or "not stated"),
        reason=str(payload.get("reason") or "not stated"),
    )
    reading = str(payload.get("own_reading") or "").strip()
    if reading:
        line = f"{line}{OWN_READING_NOTE.format(reading=reading)}"
    return line[:2000]


def _question_words(payload: dict[str, Any]) -> str:
    line = QUESTION_NOTE.format(
        marker=customers_seam.QUESTION_MARKER,
        topic=str(payload.get("topic") or "something else"),
        what=str(payload.get("what") or "").strip(),
    )
    bill = str(payload.get("bill_number") or "").strip()
    if bill:
        line = f"{line}{QUESTION_BILL_NOTE.format(bill_number=bill)}"
    return line.strip()[:2000]


# ── *stop or restart service* (US-CWP-062) ─────────────────────────────────


#: What the clerk reads on their worklist. **The dates, the reason, and the
#: sentence that stops the misunderstanding.**
#:
#: ⚠ **THE ACCOUNT IS NAMED BY ITS NUMBER** (B14 rule 31), like the plan ask
#: above: `ACC-10519-C` is what is printed on the paper bill.
#:
#: ⚠ **AND IT SAYS *the account stays open* IN THE CLERK'S SENTENCE TOO**
#: (`BR-CWP-080`). The customer was told it on `CWP-052`; a worklist row that
#: did not repeat it is a clerk one keystroke from closing an account nobody
#: asked to close.
STOP_RESTART_NOTE = (
    customers_seam.STOP_RESTART_MARKER + " {account_no} from "
    "{stop_from}{restart}. The account stays open and standing charges keep running."
)


def _stop_restart(tenant_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST accounts/{id}/stop-or-restart` — the customer ASKS; a clerk acts.

    ⚠ **NOTHING IS DISCONNECTED AND NOTHING IS SCHEDULED.** No service agreement
    ends, no meter is turned off, no work order is raised and no bill stops:
    this writes ONE `service_requests` row on a clerk's worklist, exactly as
    every other portal ask does (`BR-CWP-026` — *"a public form may create work
    and may never change an account"*).

    ⚠ **AND `BR-CWP-080` IS THE WHOLE REASON THIS SCREEN EXISTS:** a disconnect
    leaves the account OPEN and standing charges keep running. The sentence
    travels into the clerk's own row rather than living only on the customer's
    screen.

    ⚠ **A RESTART BEFORE THE STOP IS REFUSED HERE AS WELL AS AT THE EDGE**
    (`US-CWP-062` TC-5). The edge refuses it so the customer sees a field error;
    this refuses it so a caller that skipped the screen cannot write a row a
    clerk would have to work out was impossible.
    """
    stop_from = str(payload.get("stop_from") or "").strip()
    start_again = str(payload.get("start_again") or "").strip()
    if not stop_from:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-CWP-080",
            message_key="portal.stopRestart.stopFromRequired",
            field_errors=[{"field": "stop_from", "code": errors.VAL_REQUIRED}],
        )
    if start_again and start_again <= stop_from:
        # ISO dates compare correctly as strings; both arrive already parsed and
        # re-formatted by the edge, so there is no format to normalise here.
        raise errors.ValidationError(
            errors.VAL_RANGE,
            br_ref="BR-CWP-080",
            message_key="portal.stopRestart.restartBeforeStop",
            field_errors=[{"field": "start_again", "code": errors.VAL_RANGE}],
        )
    with transaction.atomic():
        request = service_request_service.create_from_portal(
            {
                "applicant_kind": applications.KIND_PERSON,
                "applicant_name": payload.get("name"),
                "applicant_email": payload.get("email"),
                "applicant_phone": payload.get("phone"),
                # ⚠ Required by `create_from_portal` (`BR-CUS-070` — *"there is
                # no such thing as a service request about nowhere"*) and
                # DERIVED BY WALKING TO THE PREMISES by the caller (hard rule
                # 8): this module holds no address column and looks nothing up.
                "address_as_given": payload.get("address"),
                "what_they_said": _stop_restart_words(payload),
            }
        )
        # ⊕ `CR-183-BRC10` T1 — the ask's account, dates and reason are STORED
        # with the request by the module that owns them (a call, not a write
        # from here — B2 §2), so staff see a *Temporary stop* and not an
        # unclassified sentence. The sentence above still goes to the clerk.
        # Nothing on the account moves until a clerk approves (BR-CWP-026).
        # One transaction: an ask whose facts could not be stored leaves no row.
        if payload.get("account_id"):
            temporary_stop.record_from_portal(
                request.id,
                account_id=payload["account_id"],
                stop_from=stop_from,
                restart_on=start_again or None,
                reason=payload.get("reason"),
            )
    return {
        "reference": request.request_no,
        #: ⚠ **STATED ON THE WIRE SO NO SCREEN CAN IMPLY OTHERWISE.** Pressing
        #: *Request this* puts a row on a worklist; the supply is still on and
        #: the account is still open until a clerk acts.
        "supply_stopped": False,
        "account_stays_open": True,
    }


#: What the clerk reads for B4's ask. The marker opens it (`request_kind`).
RESTART_NOW_NOTE = customers_seam.RESTART_NOW_MARKER + " {account_no}, from today."


def _restart_now(tenant_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST accounts/{id}/temporary-stop/restart` — B4, *Restart my service now*.

    Refused unless a temporary stop is scheduled or running on the account and
    no restart ask is already waiting — the same check the portal's button
    reads, asked again here so a caller that skipped the screen cannot write a
    row a clerk would have to work out was impossible. Nothing on the account
    moves until a clerk approves; from that day billing is normal again.
    """
    temporary_stop.refuse_unless_restart_allowed(payload["account_id"])
    with transaction.atomic():
        request = service_request_service.create_from_portal(
            {
                "applicant_kind": applications.KIND_PERSON,
                "applicant_name": payload.get("name"),
                "applicant_email": payload.get("email"),
                "applicant_phone": payload.get("phone"),
                "address_as_given": payload.get("address"),
                "what_they_said": RESTART_NOW_NOTE.format(
                    account_no=str(payload.get("account_no") or "not stated")
                ),
            }
        )
        temporary_stop.record_restart_from_portal(request.id, account_id=payload["account_id"])
    return {"reference": request.request_no, "supply_restarted": False}


def _stop_restart_words(payload: dict[str, Any]) -> str:
    """The clerk's sentence. The customer's reason is appended verbatim."""
    start_again = str(payload.get("start_again") or "").strip()
    line = STOP_RESTART_NOTE.format(
        account_no=str(payload.get("account_no") or "not stated"),
        stop_from=str(payload.get("stop_from") or "not stated"),
        restart=f", starting again on {start_again}" if start_again else ", with no restart date given",
    )
    words = str(payload.get("reason") or "").strip()
    if words:
        line = f"{line} {words}"
    return line[:2000]


# ── private helpers (G81: a public `def` here would be a fifth write point) ──


def _applicant_name(draft: models.PortalApplicationDraft) -> str | None:
    if draft.applicant_kind == applications.KIND_BUSINESS:
        return draft.company_name
    parts = [draft.first_name, draft.last_name]
    return " ".join(part for part in parts if part) or None


def _what_they_said(draft: models.PortalApplicationDraft) -> str:
    """The applicant's own words, in the column `customers` keeps them in.

    B19 §12.3 labels this pair *"The application never asked what kind of job
    this is — that is decided here"*, so this says what they ASKED FOR and never
    what the job IS: the clerk decides between a move-in and a new connection.
    """
    services = ", ".join(draft.service_codes or []) or "not stated"
    return f"Applied through the customer portal for: {services}."


def _quick_ask_words(category: dict[str, Any], payload: dict[str, Any]) -> str:
    label = str(category.get("label") or category.get("code") or "something else")
    words = str(payload.get("details") or "").strip()
    bill = str(payload.get("bill_number") or "").strip()
    line = QUICK_ASK_NOTE.format(label=label)
    if bill:
        line = f"{line} Bill {bill}."
    if words:
        line = f"{line} {words}"
    return line[:2000]


def _looks_like_a_returning_customer(draft: models.PortalApplicationDraft) -> bool:
    return customers_seam.recognise_returning_customer(
        kind=draft.applicant_kind or applications.KIND_PERSON,
        name=_applicant_name(draft),
        date_of_birth=draft.date_of_birth,
        phone=draft.phone,
        tax_id=draft.tax_id,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-007@d6d31c46 (EP-CWP-03 story + BR-CWP-001..028/076 snapshot)
# generated: 2026-09-03 by the CR-068 wave A build lane · AMENDED 2026-09-04 by the wave B lane (the first write point is built) · AMENDED 2026-09-04 by the wave C lane (the report becomes one SHAPE of `raise_service_request`, and the `preference` point is built)
# checklist: A✔ B✔ C✔ D✔(guest_api.py) E✔(portal/guest/ReportProblem.tsx) F✔ G✔ H=n/a(no 🔒 path — the 🔒 half of this wave is metering/0047)
# gates: pytest tests/test_us_cwp_007_report.py · G81 (this file is the ONLY portal file that may write, and its one public function is write_points.py's `service_request` row)
# exceptions: the interruption is the COMPANION row of the service-request write point rather than a fifth kind — declared as data in write_points.py, reasoned in the module docstring and in the decision log
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ── wave L1's shape — *someone here is unwell* (US-CWP-058) ─────────────────


#: What the clerk reads on their worklist. **The whole ask in one sentence**,
#: because `create_from_portal` refuses an account and every other field this
#: ask needs, so `what_they_said` is where the facts go — the column this
#: product already keeps *"the applicant's own words"* in, and the same place
#: `PLAN_ASK_NOTE` puts a plan ask.
#:
#: ⚠ **THE ACCOUNT IS NAMED BY ITS NUMBER** (B14 rule 31): `ACC-10519-C`, the
#: number printed on the paper bill, never a row id and never part of one.
#:
#: ⚠ **AND THE SENTENCE SAYS THE CERTIFICATE IS NOT ATTACHED**, because it
#: cannot be — consumer upload is a signed deferral (`DF-4`, PO 2026-08-08) and
#: the route ends at the counter. A clerk reading *"a certificate is coming"*
#: and finding no document would ring the customer to ask for one they were
#: already told to bring.
HARDSHIP_ASK_NOTE = (
    customers_seam.HARDSHIP_ASK_MARKER + " {account_no}: "
    "{route}. No document is attached — the portal cannot accept an upload, and the "
    "customer has been told to bring it to the office."
)

#: The three routes `CWP-056` offers, in `selectors`' own spelling. A fourth is
#: a fourth kind of hardship help and needs a ruling, not a string.
HARDSHIP_ROUTE_WORDS: dict[str, str] = {
    "medical_certificate": "someone in the household is unwell and a doctor's certificate is "
    "being brought in",
    "level_pay": "the customer would like to level out next year's payments",
}


def _hardship_ask(tenant_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST accounts/{id}/help-paying/ask` — the customer ASKS; a person judges.

    ⚠ **NO PROTECTION ROW IS WRITTEN AND NONE CAN BE** (`BR-CWP-089`,
    `US-CWP-058` TC-4). *"The portal may never grant a protection itself —
    every one needs a person and a document."* This raises a service request and
    nothing else; `AccountProtection` is `customers`' table and `write_points.py`
    does not name it, so `G84` refuses one from this module outright.

    ⚠ **IT IS A SHAPE AND NOT A SEVENTH WRITE POINT**, for the reason
    `SHAPE_PLAN_REQUEST` gives in its own comment: `BR-CWP-066` says a portal
    ask *"raises an ordinary service request under `CR-072`, **never a request
    of a new kind**"*, and the same reading covers this one. `write_points.py`
    is untouched and `G81` still sees one public function per declared kind.

    ⚠ **THE CALLER HAS ALREADY INTERSECTED THE ACCOUNT WITH THE SESSION'S SET**
    (`BR-CWP-010`) and passes the account NUMBER, so nothing here looks an
    account up and `create_from_portal`'s *"it links no account and changes
    none"* (`BR-CWP-026`) is untouched.
    """
    request = service_request_service.create_from_portal(
        {
            "applicant_kind": applications.KIND_PERSON,
            "applicant_name": payload.get("name"),
            "applicant_email": payload.get("email"),
            "applicant_phone": payload.get("phone"),
            # Required by `create_from_portal` (`BR-CUS-070`) and DERIVED BY
            # WALKING TO THE PREMISES, never stored here (hard rule 8).
            "address_as_given": payload.get("address"),
            "what_they_said": _hardship_ask_words(payload),
        }
    )
    return {
        "reference": request.request_no,
        #: ⚠ **STATED ON THE WIRE SO NO SCREEN CAN IMPLY OTHERWISE.** A customer
        #: who pressed *Send a certificate* has a request on a clerk's worklist
        #: and no hold on their supply.
        "protection_created": False,
        "granted_by": "clerk",
        #: ⚠ **THE ROUTE ENDS AT THE COUNTER** (TC-5). Said by the server so the
        #: confirmation cannot promise an upload that does not exist.
        "bring_the_document": True,
    }


def _hardship_ask_words(payload: dict[str, Any]) -> str:
    route = str(payload.get("route") or "")
    words = HARDSHIP_ROUTE_WORDS.get(route)
    if words is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            br_ref="BR-CWP-089",
            message_key="portal.helpPaying.routeUnknown",
            params={"value": route},
        )
    line = HARDSHIP_ASK_NOTE.format(
        account_no=str(payload.get("account_no") or ""), route=words
    )
    note = str(payload.get("note") or "").strip()
    if note:
        line = f"{line} {note}"
    return line[:2000]
