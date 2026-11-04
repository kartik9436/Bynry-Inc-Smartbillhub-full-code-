# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-069 (EP-CWP-12) TC-6 — *requests from the portal*, counted.
# Rules:    BR-CWP-076 (every request raised through the portal carries channel
#           `customer_portal` — a value the record has always had a field for)
#           · BR-CWP-012 (read through a seam, no second copy)
# Tests:    06-backend/tests/test_us_cwp_069_settings.py TC-6
# Impacts:  apps/customers/models.ServiceRequest.channel (free text,
#           `customers/models.py` ~1504) — wave B's writer uses the constant
#           below (`write_points.py` names it)
#           ⊕ 2026-09-04, CR-068 wave C: US-CWP-012 TC-3 (is somebody
#           living there — a MOVE-IN, and never who) · US-CWP-013 TC-2/TC-7
#           (a returning customer recognised through the EXISTING matcher)
# ───────────────────────────────────────────────────────
"""What the portal reads from `customers`: one count (wave A), and the
progress of one request a guest holds the reference to (wave B).

⚠ NOTHING HERE WRITES. The portal's one write goes through
`apps/portal/services.py`, which G81 makes the only file in this module that
may; a seam that wrote would be a second door onto the same rule.
"""

from __future__ import annotations

from typing import Any

from apps.customers import models as customers_models
from apps.customers import service_request as customers_rules
from core import tenancy as core_tenancy



def _may_withdraw(state: str) -> bool:
    """Is a customer's own withdrawal lawful from `state`?

    ⚠ **ASKED OF `TRANSITIONS`, NEVER OF A LIST TYPED OUT HERE** — see
    `DEF-CUS-5874`. The seam is allowed to READ the customers module's rules;
    what it may not do is keep its own copy of them.

    Since the PO's ruling of 2026-09-19 (`OQ-CUS-12486`) `withdraw` is not in
    the table at all, so this is `False` in every state — *"if customer dont
    want it - they will call and clark will refuse it. thats'it . keep it
    simple"*. It is written as a lookup rather than as `return False` so that
    the day the move comes back, the button does too.
    """
    allowed = customers_rules.TRANSITIONS.get(customers_rules.WITHDRAW)
    return bool(allowed) and state in allowed[0]


def _tenant():
    """The tenant this request is scoped to, for the QUERY (`BR-CWP-010`).

    ⚠ **RLS `FORCE` ALREADY ENFORCES THIS AND THAT IS NOT ENOUGH** (`G96`,
    `DEF-CWP-3775`). The rule says *in the query*, and hard-won law 14 is why:
    the suite runs on in-memory SQLite, which has no row-level security at all,
    so a read that omits the tenant passes every test here — forever, and
    indistinguishably from one that does not.
    """
    return core_tenancy.current_tenant_id()

#: The channel value BR-CWP-076 names. `service_request.channel` is free text
#: (CR-068 §0 row 6 — no enum, no migration); wave B writes the first row
#: carrying it through `service_request_service.create_request`, and this
#: constant is the ONE spelling both the writer and this count use.
CHANNEL_CUSTOMER_PORTAL = "customer_portal"

#: `accounts.kind` for a MASTER account — the owner's row over a building's
#: common supply (`BR-CUS-068`, PO 2026-08-22). Re-exported here rather than
#: imported from `apps.customers.services` at each call site, which is what a
#: seam is for: one place names the other module's spelling.
#:
#: ⚠ **THE PORTAL READS THIS COLUMN AND MUST NOT INFER IT FROM THE SHAPE
#: (`DEF-CWP-3765`).** *A master has a premises and no unit* is true only for
#: rows created after migration `customers/0036`; `CR-056` W1 kept older rows
#: on the anchor they were created with. `create_master_account` is the only
#: door to this value — every other account path refuses the field — so the
#: column is exact where the shape is a coincidence.
ACCOUNT_KIND_MASTER = "master"


def request_by_number(tenant_id: Any, number: str) -> Any:
    """The request carrying `SR-26-0056`, or None. Case-insensitive, because a
    stranger reads it off a letter and types it back."""
    return customers_models.ServiceRequest.objects.filter(
        tenant_id=tenant_id, request_no__iexact=str(number).strip()
    ).first()


#: The request states that mean *this is finished, one way or another* —
#: `ServiceRequest.TERMINAL_STATES`, read and never copied. The portal needs
#: them to answer *resolved* to a guest (`selectors.report_progress_status`).
CLOSED_REQUEST_STATES: tuple[str, ...] = customers_models.ServiceRequest.TERMINAL_STATES

#: *The job is running.* The one non-terminal state the portal distinguishes.
STATE_IN_FULFILMENT: str = customers_models.ServiceRequest.IN_FULFILMENT


def is_report(row: Any) -> bool:
    """Is this request a REPORT — somebody saying something is broken?

    ⚠ **THE TEST IS `problem_kind`, AND IT IS THE ONLY ONE.** `CR-072` widened
    `service_requests` by exactly that column so a report could stop needing a
    second record; a row that carries it came off `CWP-006`'s radio list, and a
    row that does not is an application, a quick ask or a clerk's own work.
    """
    return bool(getattr(row, "problem_kind", None))


def open_report_on_street(tenant_id: Any, street: str) -> Any:
    """A report still open on this street, or None (`US-CWP-007` TC-7).

    ⚠ **THIS QUERY MOVED TABLES ON 2026-09-04 (`CR-072`) AND THE SENTENCE IT
    ANSWERS DID NOT.** It used to scan `interruptions`, because a report WAS an
    interruption. A report is a service request now, so *"somebody has already
    reported this street"* is a question about `service_requests` — and had this
    not moved with it, the second person to ring about the Elm St burst would
    have been told nothing at all, on a screen that still promised to tell them.

    ⚠ **IT NEVER REFUSES ANYTHING.** *"Two reports of one burst is the desired
    behaviour — we would rather hear twice than not at all."* It answers a
    sentence on a confirmation screen and nothing else, which is also why the
    match is `icontains` on the street words and not something cleverer.
    """
    if not street:
        return None
    return (
        customers_models.ServiceRequest.objects.filter(
            tenant_id=tenant_id,
            problem_kind__isnull=False,
            address_as_given__icontains=street,
        )
        .exclude(state__in=customers_models.ServiceRequest.TERMINAL_STATES)
        .order_by("-received_at")
        .first()
    )


def request_progress_view(row: Any) -> dict[str, Any]:
    """One request as PROGRESS AND NEVER DATA (`BR-CWP-024`).

    ⚠ **READ THE KEYS AS THE RULE.** The state and three dates. **Not the
    applicant's name, not the address, not what they wrote, not the fee, not
    the outcome reason, and not the account.** `US-CWP-010` TC-2 asks for
    *"the move-out's progress and its dates"* and this is exactly that — a
    field that is served and merely not drawn is still served.

    ⚠ **AND NOT THE TIMELINE EITHER.** `US-CWP-009` TC-4: a clerk's internal
    routing note must never appear. Every `service_request_events` row this
    product writes carries `internal=True` (`service_request_service._event`),
    so *"filter the timeline to the customer-safe half"* would today be a
    filter with nothing on the safe side. Serving the four state dates instead
    of an empty list is the honest shape, and the customer-visible note flag is
    the wave that builds `US-CWP-062`'s.
    """
    # ⊕ **`DEF-CWP-9049` — WHETHER THE APPLICANT MAY ANSWER WITH A FILE, AND
    # HOW MANY MORE.** Two facts about the applicant's OWN act, not about the
    # record: a request in `more_info` takes a reply (`attach_reply_from_
    # portal`), and the five-file figure counts what they already sent. No
    # name, no file name, no clerk's words — `BR-CWP-024` still holds.
    from apps.customers import service_request_documents

    asked = row.state == customers_models.ServiceRequest.MORE_INFO
    left = (
        max(
            service_request_documents.MAX_APPLICANT_DOCUMENTS
            - service_request_documents.applicant_documents_held(row.pk),
            0,
        )
        if asked
        else 0
    )
    return {
        "series": "request",
        "reference": row.request_no,
        "status": row.state,
        "reported_at": row.received_at.isoformat() if row.received_at else None,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "can_add_document": asked and left > 0,
        "documents_left": left,
    }


def report_progress_view(row: Any, *, status: str, expected_back_on: Any = None) -> dict[str, Any]:
    """A REPORT as progress — the same eight keys the `RP-` lookup answered
    before `CR-072`, now served off the request itself.

    ⚠ **BYTE-FOR-BYTE THE SAME KEY SET, AND THAT IS THE POINT.** `US-CWP-010`
    TC-4 asserts the RESPONSE BODY names no customer field, on a frozen set of
    keys. Moving the record was not licence to widen what a stranger can read,
    so the shape is unchanged and only where each value comes from moved:
    `kind` ← `problem_kind`, `location_text` ← `address_as_given` (which
    `BR-CUS-070` keeps verbatim, so it is still what the person typed).

    ⚠ **`reporter_name` AND `reporter_phone` ARE STILL ABSENT.** They live on
    the row as `applicant_name` / `applicant_phone` now; the person tracking a
    reference is USUALLY the person who gave them, and *usually* is not a
    check. Echoing a name back to whoever holds the reference is exactly the
    disclosure route `BR-CWP-024` exists to close.

    `status` and `expected_back_on` are passed IN rather than read here,
    because both may belong to the confirmed interruption this report is
    attached to — a fact `metering` owns and this seam may not reach for.
    """
    return {
        "series": "report",
        "reference": row.request_no,
        "kind": row.problem_kind,
        "location_text": row.address_as_given,
        "status": status,
        "reported_at": row.received_at.isoformat() if row.received_at else None,
        "resolved_at": row.closed_at.isoformat() if row.closed_at else None,
        "expected_back_on": expected_back_on,
    }


def account_premises_id(tenant_id: Any, account_id: Any) -> Any:
    """Which premises an account takes service at — the first half of the walk
    hard rule 8 makes every address take.

    ⚠ **AN ACCOUNT HAS NO ADDRESS AND MUST NOT GROW ONE** (CLAUDE.md hard rule
    8, PO 2026-09-04: an address is stored on `premises` and NOWHERE else).
    Two shapes reach one: the ordinary account hangs off a **unit**, and a
    master account over a building's common areas hangs off the **premises**
    directly (`BR-CUS-1010`). Both are answered here so a caller never has to
    know which it is holding.

    ⚠ **`credentials.py` WALKS THE SAME TWO STEPS AND IS NOT CALLED FROM HERE,
    AND THAT IS A CONSTRAINT RATHER THAN A CHOICE.** That file is `HUMAN-OWNED`
    (`10-scripts/gates/human_owned.txt`), so a lane may not refactor it to
    share this. What is shared is the METERING read below — `premises_postcode`
    — which is the half that could actually disagree; this function returns an
    id and nothing about an address at all.
    """
    if not account_id:
        return None
    row = (
        customers_models.Account.objects.filter(tenant_id=tenant_id, pk=account_id)
        .select_related("unit")
        .only("id", "premises_id", "unit__premises_id")
        .first()
    )
    if row is None:
        return None
    return row.premises_id or getattr(row.unit, "premises_id", None)


def premises_postcode(premises_id: Any) -> str | None:
    """The postcode of one premises — the second fact `BR-CWP-025` accepts once
    a clerk has resolved a free-text address to a record. One indexed read of
    one column; nothing else about the premises reaches the portal."""
    from apps.metering import models as metering_models

    row = (
        metering_models.Premises.objects.filter(tenant_id=_tenant(), pk=premises_id)
        .only("postal_code")
        .first()
        if premises_id
        else None
    )
    return getattr(row, "postal_code", None)


def requests_from_portal(tenant_id: Any) -> int:
    """How many service requests arrived through the portal — a real zero on a
    tenant where none has (US-CWP-069 TC-6), never a placeholder."""
    return customers_models.ServiceRequest.objects.filter(
        tenant_id=tenant_id, channel=CHANNEL_CUSTOMER_PORTAL
    ).count()


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave C — occupancy, the residential class, and recognition
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **EVERY ONE OF THESE ANSWERS THE SMALLEST THING THAT WORKS.**
# `premises_is_occupied` returned True or False and never the account, the
# customer or the name (deleted 2026-10-30, see below) — `BR-CWP-021` is *"a guest sees an amount and a status,
# never a person"*, and the safest way to keep a rule like that is to make the
# value that would break it unavailable. `recognise_returning_customer` is the
# same shape one step further: it hands the evidence to the matcher
# `apps.customers.identity_match` ALREADY OWNS (`US-CWP-013` TC-7 — *"the
# encrypted, blind-indexed identity fields are used through the existing
# matching service; the portal does not read them directly"*) and returns
# **True or False**. Nothing about the candidate crosses this line, so nothing
# about the candidate can reach a screen.


def home_account_type_id() -> Any:
    """The `account_types` row a HOME is opened under, for THIS tenant, or None.

    ⚠ **THIS WAS `residential_account_type_id` AND IT READ ONE TYPED LITERAL
    UNTIL 2026-09-17.** `BR-CUS-094a` (PO, verbatim: *"utility can get their own
    account types"*, *"we have to ensure it is not hard coded"*) makes the
    platform seven a SEED rather than the vocabulary, so a hand-typed
    `code__iexact="residential"` is a live bug: a utility whose home class is
    spelled anything else gets nothing.

    ── WHAT THIS IS FOR, WHICH DECIDES THE FALLBACK ──────────────────────────
    A visitor on `CWP-008` has not said what kind of customer they are. The
    screen quotes the deposit somebody moving into a house would pay and says
    *"deposit on your first bill"* rather than promising a final figure. So the
    question this answers is narrow: **which row is this utility's HOME class?**

    ⚠ **AND WHEN THERE IS NO ANSWER THE HONEST ONE IS `None`, NOT A SUBSTITUTE.**
    The tempting fallback — the tenant's first active row — would quote a
    COMMERCIAL deposit to somebody moving into a house. That is a money figure
    shown to a member of the public for a class they do not belong to, and it
    would be indistinguishable on screen from a correct one. `rating_seam.
    deposit` already returns `None` for a missing class and `CWP-008` then shows
    no figure at all, so **withholding the number is a state the product already
    renders** and guessing it is not. There is no safe substitute for the class
    somebody actually belongs to.

    ── THE THREE OUTCOMES, `metering._resolve_unit_type`'s shape (BR-MET-084) ─
      · the tenant HAS a home-class row and it is ACTIVE → its id;
      · it has one and DEACTIVATED it → `None`. `BR-TEN-034`: a deactivated row
        stops being pickable, and this must not resurrect it;
      · it has no such row at all → `None`, and no deposit is quoted.

    ⚠ **THE CODE ITSELF IS READ FROM THE MODEL THAT OWNS IT**, never typed here.
    `SEVEN_CATEGORIES[0]` is BR-CUS-094's own ruling order and its first entry
    IS the home class, so the day the PO renames it this follows instead of
    silently returning `None` for every utility on the platform.
    """
    model = customers_models.AccountType
    home_code = model.SEVEN_CATEGORIES[0][0]
    qs = model.objects.all()
    # ⚠ **TENANT-FILTERED THE MOMENT THE COLUMN EXISTS, AND THIS IS HARD RULE 1
    # RATHER THAN TIDINESS.** `AccountType` had NO `tenant_id` while it was a
    # platform table — a filter would have raised `FieldError` and `G96` once
    # flagged this read for its absence, wrongly. A sibling lane is now making
    # the table tenant-owned under the same ruling, and on the day that lands an
    # unfiltered `.first()` starts returning ANOTHER UTILITY's row. Asking the
    # model means neither lane has to land first and there is no window where
    # this file is wrong.
    if any(f.attname == "tenant_id" for f in model._meta.concrete_fields):
        qs = qs.filter(tenant_id=_tenant())
    row = qs.filter(code__iexact=home_code, active=True).only("id").first()
    return row.id if row is not None else None


def home_account_type_code() -> str | None:
    """The CODE of the row `home_account_type_id` answers, or None — the
    customer class a move-in fee is priced for (`rating.move_in_fees` reads a
    class by code, `BR-RAT-108`). Same fallback as the id: no active home row,
    no class, and the caller quotes no class-restricted figure. `DEF-CWP-10690`."""
    home_id = home_account_type_id()
    if home_id is None:
        return None
    row = customers_models.AccountType.objects.filter(pk=home_id).only("code").first()
    return row.code if row is not None else None


def offered_categories(tenant_id: Any) -> list[dict[str, Any]]:
    """`DEF-CWP-9818` — the categories (and their live sub-categories) a new
    record may be given: the customers module's own list, as codes and names.
    Nothing here decides what is offered; `service_request_service` does."""
    from apps.customers import service_request_service

    return service_request_service.offered_categories(tenant_id)


def portal_category_problem(type_code: Any, subtype_code: Any) -> str | None:
    """`None`, `"category"` or `"subcategory"` — see the customers function."""
    from apps.customers import service_request_service

    return service_request_service.portal_category_problem(type_code, subtype_code)


# ⚠ **`premises_is_occupied` AND `unit_is_occupied` WERE DELETED HERE ON
# 2026-10-30 (`DEF-CWP-10690`, PO ruling A: *"A, move-in"*).** They told
# `CWP-008` whether a live account held an address, because the portal judged
# move-in against new connection by OCCUPANCY. The signed rule the staff Approve
# window keeps judges it by PRESENCE in Premises (2026-09-23, 2026-10-11): an
# address — and picked apartment — already in Premises is a move-in, occupied or
# empty. So occupancy no longer needs to leave the server for a guest at all,
# and the safest way to keep `BR-CWP-021` is for the value not to exist here.


def recognise_returning_customer(
    *,
    kind: str | None,
    name: str | None,
    date_of_birth: Any = None,
    phone: str | None = None,
    tax_id: str | None = None,
) -> bool:
    """Has this applicant held an account with this utility before?
    **True or False, and nothing else leaves this function.**

    `US-CWP-013` TC-2, verbatim: *"Flags a possible returning customer **for a
    clerk**. ⚠ It does **not** link the records and does **not** tell the
    applicant."* TC-7: *"The **encrypted, blind-indexed** identity fields are
    used through the existing matching service — the portal does not read them
    directly."* Both are honoured by handing `apps.customers.identity_match` the
    evidence and keeping only whether it found anybody.

    `identity_match.recognise` returns a verdict, a tier, a basis sentence and
    the candidate rows. **The candidates are dropped here, deliberately**: a
    boolean cannot be leaked into a response body by a later serialiser, and a
    list of half-matched customers can. What a clerk needs is the flag and their
    own search; what the applicant is told is nothing.

    ⚠ **`BR-CWP-031` PERMITS THIS AND FORBIDS THE OTHER DOOR.** Date of birth
    may be matched on HERE, because a person reads the flag and decides. It may
    NOT be matched on at enrolment, where anyone can hammer a public form.
    """
    from apps.customers import identity_match  # local: the matcher pulls crypto

    evidence = identity_match.IdentityEvidence(
        name=name or None,
        kind=kind or None,
        date_of_birth=date_of_birth or None,
        phone=phone or None,
        tax_id=tax_id or None,
    )
    if not evidence.has_any():
        return False
    verdict = identity_match.recognise(evidence)
    return bool(verdict.get("matched")) or bool(verdict.get("candidates"))


def request_reference(request_id: Any) -> str | None:
    """`SR-26-0049` — the number the row was given AT CREATION (`BR-CUS-093`).

    The one read both the write path and the draft read use, so the reference a
    submit returns and the reference a reopened draft link shows can never be
    computed two different ways.
    """
    if not request_id:
        return None
    row = (
        customers_models.ServiceRequest.objects.filter(tenant_id=_tenant(), pk=request_id)
        .only("request_no")
        .first()
    )
    return row.request_no if row is not None else None


def request_fee_paid(request_id: Any) -> dict[str, str] | None:
    """`CR-191-BRC10` — what the applicant PAID for this request online, or None.

    Read off the request's own fee columns (`_record_online_fee` writes them),
    as `{"amount": "10.0000", "currency": "USD"}` — four places, a string,
    never a float (hard rule 2). The screen formats it; this computes nothing.
    """
    if not request_id:
        return None
    row = (
        customers_models.ServiceRequest.objects.filter(tenant_id=_tenant(), pk=request_id)
        .only("fee_collected", "fee_currency", "fee_receipt_no")
        .first()
    )
    if row is None or row.fee_collected is None or not row.fee_receipt_no:
        return None
    from decimal import Decimal

    return {
        "amount": str(Decimal(row.fee_collected).quantize(Decimal("0.0001"))),
        "currency": row.fee_currency,
    }


def tenant_currency() -> str | None:
    """The utility's CHAR(3) currency, through customers' own read (BR-TEN-021)."""
    from apps.customers import seams as customers_seams

    return customers_seams.tenant_currency()


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave F · `CWP-065` — the facts about an account that are not on a bill
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THREE READS AND NOT ONE OF THEM TOUCHES `credit_tier`, `match_tier` OR
# `match_basis`** (`BR-CWP-052`, blueprint §17). Those three are held back from
# a customer ON PURPOSE — a credit tier is the utility's own assessment of the
# person reading the screen — and the surest way to keep them off a response is
# for the code that builds it never to select them. `US-CWP-031` TC-7 asserts
# their absence on the BODY, which is the check that survives a refactor.


def deposit_interest(account_id: Any, as_of: Any):
    """What the deposit has earned by `as_of` — `Decimal`, or None if unknown.

    ⚠ **READ, NEVER RECOMPUTED HERE** (`US-CWP-031` §7). `BR-CUS-057`'s
    arithmetic lives once, in `apps/customers/deposit_interest.py`, and is
    finance-signed against ❄️ `GT-61` (`150.00 × 0.02 × 89 ÷ 12 = 22.25`). A
    second implementation on a portal screen is how a figure a customer reads
    comes to disagree with the figure their final bill settles — which
    `US-CWP-031` §7 names as *the defect this test exists to catch*.

    ⚠ **`None` IS A REAL ANSWER AND MUST NOT BECOME `0.00`.** Both existing
    callers — `move_out_settlement` and `billing.final_bill` — fail CLOSED on a
    `None` rather than paying out principal alone, and this screen takes the
    same posture: it says the interest is not known, never that it is nothing.
    """
    from apps.customers import selectors as customers_selectors

    return customers_selectors.deposit_interest_accrued(account_id, as_of)


def live_tax_exemptions(account_id: Any) -> list[dict[str, Any]]:
    """The account's LIVE per-tax exemption certificates, as a customer reads
    them: `[{"tax": <the tax it removes>, "until": <ISO date or None>}]`.

    ⚠ **THE STAFF PAGE'S OWN READ, NEVER A SECOND ONE** (`DEF-CWP-9795`).
    `customers.seams.account_tax_exemptions` → rating's
    `exemption_certificates_for_account`, whose `state` is derived exactly as
    the bill run derives it — so the portal, the staff account page and the
    bill cannot disagree. PO ruling (A) 2026-10-05 (`DEF-CUS-9724`): a
    certificate removes only the tax it names and leaves the blanket
    `tax_exempt` flag false, which is why reading that flag alone showed M5's
    church no exemption at all.

    Revoked rows never arrive (rating leaves them out). EXPIRED rows are
    dropped here: an expired certificate has reinstated the tax, so it is not
    an exemption the customer holds. ⚠ **AND THE CERTIFICATE NUMBER IS NOT
    PASSED ON** — `US-CWP-031` TC-5: the number is the utility's record; the
    customer needs the tax and the date.
    """
    from apps.customers import seams as customers_seams

    return [
        {"tax": row.get("tax_name"), "until": row.get("expires_on")}
        for row in customers_seams.account_tax_exemptions(account_id)
        if row.get("state") == "live"
    ]


def services_held(tenant_id: Any, account_id: Any) -> list[dict[str, Any]]:
    """Each service this account is on, and since when — `service_agreements`.

    ⚠ **THE START DATE IS THE AGREEMENT'S, NOT THE ACCOUNT'S.** A household that
    took water in 2021 and added trash in 2024 has two different answers, and
    showing the account's opening date against both would be wrong on the second
    the day somebody checks it against their first trash bill.

    ⚠ **AN ENDED AGREEMENT IS NOT LISTED.** `ended_on` is null while the service
    is in force; a service that stopped is history this screen does not draw,
    and `US-CWP-031`'s panel is *your services*, present tense.

    ⚠ **WHAT IS DELIBERATELY ABSENT: *what it is billed on*** — the wireframe's
    *meter · share of water · 96 gal cart*. That fact lives in the RATE PLAN's
    component for the service, in a vocabulary this module cannot read, and
    deriving it from *does the service point have a meter* would be a proxy for
    a column — which is exactly `DEF-CWP-3765`, filed the same day. The panel
    ships without it rather than with a guess.
    """
    rows = (
        customers_models.ServiceAgreement.objects.filter(
            tenant_id=tenant_id, account_id=account_id, ended_on__isnull=True
        )
        .select_related("service_point__service")
        .order_by("started_on", "service_point__service__code")
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        service = getattr(getattr(row, "service_point", None), "service", None)
        if service is None:
            continue
        out.append(
            {
                "code": service.code,
                #: The utility's OWN word for the service, exactly as the front
                #: page words its chips — never a code this product translates.
                "name": service.name,
                "since": row.started_on.isoformat() if row.started_on else None,
            }
        )
    return out


#: ⚠ **`opened_by` IS NOT HERE, AND ITS ABSENCE IS A FINDING RATHER THAN A
#: DEFERRAL (2026-09-04, `DEF-CWP-3767`).** `US-CWP-031` §5 asks for a *move
#: history* read from a `MoveRecord` table, and **there is no such model in this
#: product and never has been.** A move is a `service_requests` row carrying
#: `outcome = 'move_in'` — but that row has **no `account_id`**: the link runs
#: the other way through `outcome_ref`, free text, whose matching
#: `origin_service_request_id` on the child is documented in the model's own
#: words as *"it does not exist yet"*.
#:
#: **So an account cannot be walked back to the move that opened it**, and a
#: first draft of this seam tried and was refused by Django itself —
#: `FieldError: Cannot resolve keyword 'account_id'`, which is the database
#: saying the relationship the story assumes is not modelled.
#:
#: What `CWP-065` says instead is what it can honestly say: `accounts.opened_at`,
#: *this account opened on 4 March 2021*. The move that caused it waits for the
#: child-table link, and no lane should reconstruct it from `outcome_ref` by
#: matching strings — that is a join on prose.


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave G · `CWP-024` — the details a customer may fix (US-CWP-028)
# ═══════════════════════════════════════════════════════════════════════════

#: Hard rule 8's first named exception — where the BILL goes, which for a
#: landlord is a different building from any premises they hold.
#: ⚠ `kind='service'` is RETIRED (`G85`) and is never read here.
ADDRESS_MAILING = "mailing"


def holder_display_name(tenant_id: Any, account_id: Any) -> str | None:
    """Whose account this is — read ONLY so it can be MASKED (`BR-CWP-020`).

    ⚠ **THE CALLER IS `selectors.bill_lookup` AND IT NEVER PUTS THIS VALUE ON
    THE WIRE.** `masked_name` turns *Maria Alvarez* into `M. A••••••` before
    anything leaves the server (`US-CWP-004` §5: *"Never send the full name and
    mask in the browser"*), and `G92` refuses `display_name` as a key of any
    guest response whatever an allow-list says. This function exists so the
    masking has something to mask; a second caller that returned it raw would
    be the leak the whole guest-fields declaration is written to catch.

    `None` when the account has no customer linked, which masks to the dots
    alone rather than to an empty string somebody would read as a bug.
    """
    link = (
        customers_models.CustomerAccount.objects.filter(
            tenant_id=tenant_id, account_id=account_id
        )
        .select_related("customer")
        .first()
    )
    return getattr(getattr(link, "customer", None), "display_name", None)


def delivery_election(tenant_id: Any, account_ids: list[Any]) -> dict[str, Any]:
    """What this login's accounts have elected BEYOND the print floor.

    ⚠ **`customers.selectors.channel_preference_for_account` IS THE
    PUBLISHED READ AND IT IS PER ACCOUNT** (`DEF-BIL-10535`, 2026-10-22: it was
    `delivery_channel_election_for_account`, which since the PO's Q2 ruling
    elects email for every account with an email on file — a BILL rule; this
    switch shows what the CUSTOMER chose) — customers' own answer, so a portal that computed the election from the columns
    itself would be a second answer to *how does this customer want their bills*
    and the two would drift on the first amendment (`12-reuse-map.md`'s whole
    rule). This asks it once per account and folds the answers.

    ⚠ **`varies` IS SERVED RATHER THAN RESOLVED.** Maria holds four accounts and
    the screen offers one switch; when the four disagree, saying so beats
    silently showing one of them — the same posture `contact_details` takes one
    function up, and for the same reason.

    A `None` from the published read is *nobody could look* (the account is not
    this tenant's) and is skipped rather than counted as *elected nothing*.
    """
    from apps.customers import selectors as customers_selectors

    answers: list[tuple[bool, bool]] = []
    for account_id in [str(one) for one in account_ids]:
        elected = customers_selectors.channel_preference_for_account(account_id)
        if elected is None:
            continue
        answers.append(("email" in elected, "sms" in elected))
    if not answers:
        return {"email_on": False, "text_on": False, "varies": False, "answered": 0}
    return {
        "email_on": any(email for email, _ in answers),
        "text_on": any(text for _, text in answers),
        "varies": len(set(answers)) > 1,
        "answered": len(answers),
    }


def _primary_contact(tenant_id: Any, account_id: Any):
    return (
        customers_models.Contact.objects.filter(
            tenant_id=tenant_id, account_id=account_id, deleted_at__isnull=True, is_primary=True
        )
        .order_by("created_at")
        .first()
    )


def _mailing_address(tenant_id: Any, account_id: Any):
    return (
        customers_models.Address.objects.filter(
            tenant_id=tenant_id,
            account_id=account_id,
            kind=ADDRESS_MAILING,
            deleted_at__isnull=True,
        )
        .order_by("created_at")
        .first()
    )


def contact_details(tenant_id: Any, account_ids: list[Any]) -> dict[str, Any]:
    """The email, mobile and postal address this login may edit — ONE set.

    ⚠ **ONE ANSWER ACROSS EVERY ACCOUNT, BECAUSE THE SCREEN OFFERS ONE FIELD**
    (`US-CWP-028` TC-10: *one save, four accounts updated*). `contacts` hangs
    off the ACCOUNT, so Maria Alvarez with four accounts has four rows — and a
    screen with four email boxes would be asking her to keep them in step by
    hand, which is exactly the job the product is for.

    ⚠ **SO WHEN THE FOUR DISAGREE, THIS SAYS SO RATHER THAN PICKING ONE.**
    `email_varies` / `phone_varies` / `postal_varies` are true when the login's
    accounts do not already hold the same value, and the screen shows the most
    common one with a line saying the others differ. Silently displaying one of
    four would tell a customer their email is right on accounts where it is not.

    ⚠ **THE LEGAL NAME IS RETURNED AND IS NOT EDITABLE** (`BR-CWP-026`). It is
    here because the screen must SHOW what it will not let you change — an
    absent field reads as an oversight, a present one with *ask us to change
    this* reads as a rule.
    """
    ids = [str(one) for one in account_ids]
    emails: list[str] = []
    phones: list[str] = []
    postals: list[dict[str, Any]] = []
    names: list[str] = []
    returned_post = 0
    for account_id in ids:
        contact = _primary_contact(tenant_id, account_id)
        if contact is not None:
            if contact.email:
                emails.append(str(contact.email))
            if contact.phone:
                phones.append(str(contact.phone))
            if contact.full_name:
                names.append(str(contact.full_name))
        address = _mailing_address(tenant_id, account_id)
        if address is not None:
            postals.append(
                {
                    "line1": address.line1 or None,
                    "line2": address.line2,
                    "city": address.city,
                    "state": address.state,
                    "postal_code": address.postal_code,
                    "country": address.country,
                }
            )
        account = (
            customers_models.Account.objects.filter(tenant_id=tenant_id, id=account_id)
            .only("id", "bad_address")
            .first()
        )
        if account is not None and getattr(account, "bad_address", False):
            returned_post += 1

    return {
        "email": _most_common(emails),
        "email_varies": _varies(emails, len(ids)),
        "phone": _most_common(phones),
        "phone_varies": _varies(phones, len(ids)),
        "postal": _thawed(postals),
        "postal_varies": _varies([str(_frozen(one)) for one in postals], len(ids)),
        #: `BR-CWP-026` — shown, never editable.
        "legal_name": _most_common(names),
        #: `BR-CWP-086` — how many of this login's accounts have post coming
        #: back. The screen says *two letters came back from this address*
        #: ABOVE the address field, which is where somebody about to correct it
        #: is already looking.
        "returned_post_accounts": returned_post,
        "account_count": len(ids),
    }


def _most_common(values: list[Any]) -> Any:
    if not values:
        return None
    counts: dict[Any, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    best = max(counts, key=lambda key: (counts[key], key))
    for value in values:
        if str(value) == best:
            return value
    return None


def _varies(values: list[Any], account_count: int) -> bool:
    """True when the accounts do not agree — including when some have NO value.

    ⚠ **A MISSING VALUE IS A DISAGREEMENT.** Three accounts with an email and
    one with none is not *they all say the same thing*; it is one bill going
    nowhere, and the screen has to be able to say so.
    """
    if account_count <= 1:
        return False
    return len({str(one) for one in values}) > 1 or len(values) != account_count


def _frozen(postal: dict[str, Any]) -> tuple:
    return tuple(str(postal.get(key) or "") for key in sorted(postal))


def _thawed(postals: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not postals:
        return None
    wanted = _most_common([str(_frozen(one)) for one in postals])
    for one in postals:
        if str(_frozen(one)) == wanted:
            return one
    return postals[0]


def account_by_number_and_postcode(tenant_id: Any, *, account_no: str, postcode: str) -> Any:
    """`US-CWP-027` — the account being ADDED, matched on the two facts printed
    on its own paper bill.

    ⚠ **A WRONG POSTCODE IS REFUSED IDENTICALLY TO AN UNKNOWN NUMBER**
    (`US-CWP-027` TC-2). Both return `None`; the endpoint answers one sentence
    for both, so this form cannot be used to learn which account numbers exist.

    ⚠ **AND IT DELEGATES TO THE ENROLMENT MATCHER RATHER THAN RE-IMPLEMENTING
    IT.** `credentials.find_account` already walks account → unit → premises →
    postcode and normalises both sides; a second walk here would be a second
    answer to *which account is this*, and the two would drift on the first
    premises change.
    """
    from apps.portal import credentials

    return credentials.find_account_by_postcode(
        tenant_id, account_no=account_no, postcode=postcode
    )




# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave L1 · `CWP-057`, `CWP-056` and `CWP-064` — the ladder, the three
# doors and the three protections (US-CWP-057 · US-CWP-058 · US-CWP-059)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **NOT ONE RULE ABOUT COLLECTIONS IS AUTHORED HERE.** `apps/customers/
# disconnects.py` owns the tier vocabulary, the three protections and their
# three lifetimes, the halt decision, the reconnection quote and the
# `TIER_UNMAPPED` absence. Every function below CALLS one of those and none
# restates one — the posture `disconnect_reads.py` already took on the staff
# side, and `12-reuse-map.md`'s whole point: *"the portal's job is the same
# facts in a customer's words — never a second arithmetic."*
#
# ⚠ **AND THE ONE THING THIS SEAM MUST NEVER DO IS INVENT A DATE.** `US-CWP-057`
# §1: *"a rung the tier vocabulary cannot name is rendered as an absence, never
# rounded"*, because showing a customer at the five-day notice as though they
# were at the ten-day one **moves the date they think they have.** The same
# reasoning covers a step with no recorded date at all: it travels with
# `on: None`, and the screen says so in words.


def disconnect_case(account_id: Any) -> Any:
    """This account's OPEN disconnection case, or `None` — `US-CWP-057` TC-4.

    ⚠ **`None` MEANS *nothing is being chased*, NOT *unknown*.** `CWP-057` is
    absent altogether for an account with no case (TC-10), and the endpoint
    answers that rather than an empty timeline, which would read as *we have
    already sent everything* to the person least able to check.
    """
    from apps.customers import disconnects

    return disconnects.open_case_for(account_id)


def case_view(case: Any) -> dict[str, Any]:
    """The case as `disconnects.case_payload` serialises it — one implementation.

    The staff `S90` row reads the same dict. A second serialisation of a
    disconnection is two answers to *what has been sent to this household*, and
    the two would drift on the first tier that moved.
    """
    from apps.customers import disconnects

    return disconnects.case_payload(case)


def ladder_position(account_id: Any, *, as_of: Any) -> dict[str, Any]:
    """Whether the ladder is running for this account today, and why not if not.

    `disconnects.ladder_state` is COMPUTED on every call and never read from a
    stored flag — its own docstring's reason is *"a RUN cached on a row outlives
    the debt, and that is the customer who paid on Friday and got a certified
    letter on Monday."* A portal that memoised it would be that cache with a
    shorter lifetime and the same failure.
    """
    from apps.customers import disconnects

    return disconnects.ladder_state(account_id, as_of=as_of).as_dict()


def reconnection_quote(account_id: Any, *, case: Any = None) -> dict[str, Any]:
    """What it costs to get service back — `disconnects.reconnection_terms`.

    ⚠ **THE PORTAL COMPUTES NO FEE AND NO DEPOSIT.** That read is the ONE place
    the figure comes from — *"the wizard shows it at step 4, the tier-3 letter
    prints the same figure … one read, so the letter and the screen and the
    record cannot quote three different prices."* `CWP-057` is the fourth
    surface on it and adds no fifth price.

    ⚠ **AND IT CARRIES ITS OWN ABSENCES.** `fee` is `None` with a reason when
    the tenant's `CC-RECON` row is unset or is a percentage; `deposit
    .new_deposit_required` is `None` when no election is recorded. Neither is a
    zero, and the sum on `CWP-057` refuses to add a figure that is not there.
    """
    from apps.customers import disconnects

    return disconnects.reconnection_terms(account_id, case=case)


def protections(account_id: Any, *, as_of: Any) -> tuple[dict[str, Any], ...]:
    """Every protection on this account with its LIFETIME — `BR-CWP-090`.

    Three kinds and three shapes, and the shape is what `CWP-064` renders:
    `expires_on_a_date` (a certificate, which must carry an end date),
    `derived_from_the_plan` (which must NOT — it lifts the day an instalment is
    missed, `OQ-170` closed 2026-08-12), `regulator_date_window` (a start and an
    end nobody applies for).

    ⚠ **A LIFTED PROTECTION COMES BACK, MARKED LIFTED** (`US-CWP-059` TC-7).
    `protections_for` returns every stored row with `in_force` computed, and the
    portal filters none of them out: a hold that vanished from the screen the day
    it lapsed is the customer who did not know it had.
    """
    from apps.customers import disconnects

    return disconnects.protections_for(account_id, as_of=as_of)


def protection_kinds() -> dict[str, str]:
    """The three kinds, in `customers`' own spelling, named in ONE place.

    A screen comparing against a string literal is a screen that goes on
    rendering after a rename — `DEF-CUS-3653`'s shape exactly (a retired value
    left a header composing an address that would have been null forever).
    """
    from apps.customers import disconnects

    return {
        "medical": disconnects.PROTECTION_MEDICAL,
        "plan": disconnects.PROTECTION_PLAN,
        "moratorium": disconnects.PROTECTION_MORATORIUM,
    }


def tier_unmapped() -> str:
    """`disconnects.TIER_UNMAPPED` — the rung B18 draws no chip for.

    `BR-CWP-092`: it renders as an **absence**, never rounded to a neighbour.
    Named through the seam so the portal never spells `"unmapped_rung"` itself.
    """
    from apps.customers import disconnects

    return disconnects.TIER_UNMAPPED


def ladder_tiers() -> tuple[str, ...]:
    """The three chips B18 §5.8.2 draws, in order — `disconnects.LADDER_TIERS`.

    The LAST of them is the final notice, which is what `CWP-056` needs to know
    whether an account is past it. Named through the seam so the portal never
    spells `"tier_3_48_hour"` itself (`DEF-CUS-3653`'s lesson: a screen
    comparing against a literal goes on rendering after a rename).
    """
    from apps.customers import disconnects

    return disconnects.LADDER_TIERS


def tier_chips(*, case: Any, protections: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """WHICH TIER THIS ACCOUNT IS ON — `disconnect_reads.chips_for`, reused.

    ⚠ **THE PORTAL DOES NOT DECIDE THIS AND MUST NOT.** The staff Disconnects
    tab (`S90`) already answers *which chip*, and its answer is subtle in three
    ways a second implementation would get wrong within a week:

      * a stored tier the vocabulary does not know (payments' `second_5_day`)
        is `unmapped_rung` and renders as an ABSENCE — never TIER 2 and never
        TIER 3, because *"both are statements to a regulator about what a
        customer was told"* (`BR-CWP-092`);
      * a NULL tier is a DIFFERENT absence — `no_tier_reached`, *"nothing has
        been sent"* — and reading the two as one would tell a customer at the
        five-day notice that nothing had been sent to them;
      * a protection in force is itself a chip, and **more than one chip can
        apply with no rule ranking them** (`OQ-374`), so nothing is chosen.

    `12-reuse-map.md`: *"a second read of the same facts is a second ANSWER, and
    the two surfaces are a clerk and a customer arguing with each other on the
    phone."*
    """
    from apps.customers import disconnect_reads

    return disconnect_reads.chips_for(case=case, protections=protections)


def notices_on(case: Any) -> list[dict[str, Any]]:
    """Every notice already recorded against this case, oldest first.

    ⚠ **TENANT AND CASE ARE BOTH IN THE QUERY** (`BR-CWP-010`, `G96`). RLS
    `FORCE` would catch the tenant on PostgreSQL and the suite runs on SQLite,
    which has no row-level security at all (hard-won law 14).

    ⚠ **`delivery_state` IS NULL ON EVERY ROW THIS PRODUCT WRITES** and the
    reason travels with the case rather than being inferred here — there is no
    email, SMS or print adapter, so a notice records that it was WRITTEN and
    never that it arrived (`disconnects.DELIVERY_UNAVAILABLE`, `BR-NOT-005`).
    A portal that drew *"emailed 1 September"* would be telling a customer they
    were warned.
    """
    from apps.customers import disconnects

    rows = disconnects.DisconnectNotice.objects.filter(
        tenant_id=_tenant(), case_id=case.pk
    ).order_by("issued_on", "id")
    return [
        {
            "tier": row.tier,
            "issued_on": row.issued_on.isoformat() if row.issued_on else None,
            #: HOW it was served, when a person has recorded proof — never
            #: guessed, and `None` where nobody has (`BR-CUS-100`: the send and
            #: the proof are two different records).
            "served_channel": row.service_channel,
            "served_on": row.served_on.isoformat() if row.served_on else None,
        }
        for row in rows
    ]


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave R — TRACK YOUR REQUEST · QUERY A BILL · ASK A QUESTION
# (US-CWP-063 · US-CWP-065 · US-CWP-066 — CWP-051 · CWP-055 · CWP-054)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE CUSTOMER-VISIBLE HALF OF A READ THAT ALREADY EXISTS, PROJECTED — NOT
# A SECOND READ** (`12-reuse-map.md`, PO 2026-09-04: *"all the services that are
# required for Consumer portal - you will find it same set of services,
# endpoints are already available for Accounts"*). `service_request_reads.
# history_tab` is the CLERK's timeline and this file DROPS FROM IT; a second
# walk of `service_request_events` would be a second ANSWER, and the two
# surfaces are a clerk and a customer arguing on the telephone.
#
# ⚠ **THE RULE SPLITS THE ROWS IN TWO AND SO DOES THIS — READ `BR-CWP-078` IN
# ITS OWN WORDS:** *"the customer-safe request history shows **the
# transitions** and **the notes flagged customer-visible**, and hides internal
# routing comments."* Two clauses, two treatments, and a first draft that
# filtered every row on `internal` got it wrong in a way worth recording: every
# STATE row this product writes carries `internal=True`, so the customer's
# progress timeline came back **with no dates on any step at all**.
#
#   * **STATE rows are transitions and are ALWAYS shown** — `at` and `to_state`.
#     They are what *how far along is my request* means.
#   * **Their `note` is DROPPED**, with one exception the rules require: the
#     transition into `refused`, because `BR-CWP-077` is CONFIRMED — *"a refusal
#     always carries a reason, and the portal shows it"* — and `refuse_request`
#     puts that reason on the EVENT rather than on the row. Every other
#     transition's reason is a clerk's working note (`hold`, `request_info`,
#     `manual_close`, `reopen`) and stays inside.
#   * **NOTE and SYSTEM rows are shown ONLY when `internal` is False** — the
#     flag `BR-CWP-078`'s second clause names, and `US-CWP-063` TC-2 asserts
#     *"route to Tuesday crew, low priority"* appears nowhere in the BODY.
#
# ⚠ **WHAT IS DROPPED FROM EVERY SURVIVING ROW, BY NAME** (B14 rule 31,
# `BR-CWP-052`):
#
#   * `id` — a database id is never a visible value and never on the wire
#     either, because a field that is served and merely not drawn is still
#     served;
#   * `actor` — the staff user's UUID. The customer is told a step HAPPENED and
#     WHEN; who inside the utility touched it is the utility's business, and a
#     uuid would tell them nothing anyway;
#   * `from_state` — *"we moved it from under review to more info"* is the
#     clerk's vocabulary for one event, and a customer reads one step at a time.
#     `to_state` survives because it is what the step IS;
#   * `internal` — the flag itself. Serving it would tell a reader that
#     something was withheld, which is the shape `BR-CWP-094` refuses one screen
#     along (*"no count of what is hidden"*).
#
# **WHAT SURVIVES:** `at`, `kind`, `to_state`, `note`, `note_type`. Five keys,
# and the test asserts the key SET rather than four named absences — the same
# posture `report_progress_view` takes above, for the same reason.

#: The words every portal QUERY of a bill starts with — the marker
#: `open_query_on_bill` matches on and the sentence a clerk reads first.
#: A CONSTANT, so a grep for it finds the writer and the reader together.
DISPUTE_MARKER = "Queried through the customer portal"

#: The same, for a QUESTION (`CWP-054`). Different words on purpose: the two
#: land on one worklist and a clerk must be able to tell *"this bill is wrong"*
#: from *"I do not understand this bill"* at a glance.
QUESTION_MARKER = "Asked through the customer portal about"

#: ⚠ **THE OTHER FOUR MARKERS, MOVED HERE FROM `services.py` SO THE WRITER AND
#: THE READER SHARE ONE CONSTANT** — the rule `DISPUTE_MARKER` states three
#: lines up, applied to the shapes that had never needed a reader before.
#: `services.py` composes its note templates FROM these, so the string a clerk
#: reads and the string this file matches on cannot drift apart.
#: (`CR-085` `CPB-05`, 2026-09-08 — `request_kind` below is why a reader
#: exists at all now.)
QUICK_ASK_MARKER = "Asked through the customer portal:"
STOP_RESTART_MARKER = "Asked through the customer portal to stop service on account"
PLAN_ASK_MARKER = "Asked through the customer portal for a payment plan on account"
HARDSHIP_ASK_MARKER = "Asked through the customer portal for help paying on account"
#: `CR-183-BRC10` B4 — *Restart my service now*.
RESTART_NOW_MARKER = "Asked through the customer portal to restart service now on account"

#: marker → the KIND CODE a catalogue writes into a customer-facing title.
#:
#: ⚠ **A CODE TRAVELS AND THE CATALOGUE WRITES THE WORD** (B14 rule 35). Not
#: one of the sentences these markers open is written for a customer: every one
#: is a clerk's worklist row, in the third person, about the person reading it
#: (`DEF-CWP-4198`).
#:
#: ⚠ **SORTED LONGEST FIRST, AND THAT IS LOAD-BEARING RATHER THAN TIDY.** Five
#: of the six begin *"Asked through the customer portal"*, so matching in
#: declaration order would file a payment-plan ask and a stop-service ask alike
#: under whichever happened to be written first. `sorted(key=len)` makes the
#: ordering mechanical, so a seventh marker added below cannot get it wrong.
PORTAL_REQUEST_KINDS: tuple[tuple[str, str], ...] = tuple(
    sorted(
        (
            (DISPUTE_MARKER, "bill_query"),
            (QUESTION_MARKER, "question"),
            (STOP_RESTART_MARKER, "stop_service"),
            (PLAN_ASK_MARKER, "payment_plan"),
            (HARDSHIP_ASK_MARKER, "help_paying"),
            (RESTART_NOW_MARKER, "restart_now"),
            (QUICK_ASK_MARKER, "quick_ask"),
        ),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
)


def request_kind(said: Any) -> dict[str, Any] | None:
    """What this request IS, as a code a catalogue can write — or `None`.

    ⚠ **WHY A DERIVATION AND NOT A COLUMN.** `service_requests` carries no
    category and no kind (`DEF-CWP-3701`, filed again as `DEF-CWP-3881`), so
    every portal shape puts its facts in `what_they_said` — the column this
    product keeps *"the applicant's own words"* in — and a clerk's composed
    sentence therefore sits where the customer's own words are supposed to be.
    `open_query_on_bill` already classifies a request by matching
    `DISPUTE_MARKER` in that column; this is that mechanism widened to all six
    portal shapes rather than a new one.

    ⚠ **`None` IS THE RIGHT ANSWER FOR A REPORT AND AN APPLICATION**, and it is
    not a failure: those shapes write what the customer actually typed, so
    there is nothing to replace and the screen goes on showing their words.

    ⚠ **THE BILL NUMBER IS READ BACK OUT OF A SENTENCE THIS MODULE WROTE**,
    which is the only reason it is safe — `DISPUTE_NOTE`'s next word after the
    marker is literally `bill`, and both halves are constants in these two
    files. Where it cannot be read the kind survives without it (`number: None`)
    so no screen can print *"Query about bill "* with nothing after it.
    """
    text = str(said or "").strip()
    if not text:
        return None
    for marker, kind in PORTAL_REQUEST_KINDS:
        if not text.startswith(marker):
            continue
        number = None
        if kind == "bill_query":
            rest = text[len(marker) :].strip()
            if rest.startswith("bill "):
                number = rest[len("bill ") :].split(" ", 1)[0].strip() or None
        return {"kind": kind, "number": number}
    return None


#: `ServiceRequestEvent.KIND_STATE`, read and never copied.
KIND_STATE: str = customers_models.ServiceRequestEvent.KIND_STATE
#: The one transition whose clerk-written reason the customer is entitled to
#: (`BR-CWP-077`, CONFIRMED).
STATE_REFUSED: str = customers_models.ServiceRequest.REFUSED


def _customer_visible_events(request: Any) -> list[dict[str, Any]]:
    """`history_tab`, split and projected. See the block comment above."""
    from apps.customers import service_request_reads

    kept: list[dict[str, Any]] = []
    for event in service_request_reads.history_tab(request):
        # ⚠⚠ **A ROW THAT MOVED THE STATE IS A TRANSITION, WHATEVER KIND IT IS
        # LABELLED (2026-09-19).** This asked `kind == KIND_STATE` alone, which
        # was the same thing until the PO's ruling that day made PARK move
        # `submitted` → `under_review`. Park writes a `KIND_NOTE` row, and that
        # row is `internal`, so the customer's ladder dropped it — *we picked it
        # up* went `current` with **no date beside it**, truthfully and
        # silently, because the step's date comes from this list.
        #
        # **So it asks what the row SAYS rather than what it was called.** The
        # note is still withheld below: a park reason is a clerk's working note
        # and only a refusal's reason is the customer's (`BR-CWP-077`), and that
        # branch keys off this same flag — which is why widening it here does
        # not widen what is READABLE by one word.
        is_transition = event["kind"] == KIND_STATE or event["to_state"] is not None
        if not is_transition and event.get("internal"):
            continue
        note = event["note"]
        if is_transition and event["to_state"] != STATE_REFUSED:
            # A clerk's reason for holding, parking or asking for more is a
            # working note. Only the refusal's is the customer's (BR-CWP-077).
            note = None
        kept.append(
            {
                "at": event["at"],
                "kind": event["kind"],
                "to_state": event["to_state"],
                "note": note,
                "note_type": event["note_type"],
            }
        )
    return kept


def refusal_reason(request: Any) -> str | None:
    """The sentence a refused request carries, or None (`BR-CWP-077`).

    ⚠ **IT IS NOT ON THE ROW AND THAT SURPRISED THIS LANE.**
    `service_requests.decision_reason` is written by `decide_outcome` — the
    clerk choosing what the job BECOMES — and `refuse_request` puts its own
    reason on the timeline EVENT instead (`_apply(..., reason=...)` →
    `_event(note=...)`). So a request refused without an outcome first has
    `decision_reason` NULL and its reason sitting one table over. Both are read
    here, the row first, so the portal shows a reason wherever the product put
    one rather than showing none wherever it looked in the wrong place.
    """
    stored = getattr(request, "decision_reason", None)
    if stored:
        return stored
    for event in _customer_visible_events(request):
        if event["to_state"] == STATE_REFUSED and event["note"]:
            return event["note"]
    return None


#: The six steps `CWP-051` draws, in order, and the request states each is
#: reached by. **The LABELS are the eleven catalogues' — this is the skeleton.**
#:
#: ⚠ **IT IS A PROJECTION OF THE ELEVEN STATES ONTO SIX AND NOT A SECOND STATE
#: MACHINE.** `ServiceRequest.STATES` is the vocabulary; `08-screen-layouts.md`
#: `P37` draws six boxes; a customer does not need `on_hold` and `in_fulfilment`
#: as separate ideas. Nothing here can move a state — `_apply` is the only door.
PROGRESS_STEPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("sent", ("draft", "submitted")),
    ("picked_up", ("under_review",)),
    ("we_need_something", ("more_info",)),
    ("we_decide", ("approved", "refused")),
    ("in_hand", ("in_fulfilment", "on_hold")),
    ("finished", ("completed", "closed", "withdrawn")),
)


def _step_index(state: str | None) -> int:
    for index, (_, states) in enumerate(PROGRESS_STEPS):
        if state in states:
            return index
    return 0


def progress_steps(request: Any) -> list[dict[str, Any]]:
    """The six steps, each `done` · `current` · `future`, with when it happened.

    ⚠ **THE DATE COMES OFF THE TIMELINE THE CUSTOMER CAN ALREADY SEE**, so no
    step can claim a moment no visible row carries.
    """
    reached = _step_index(request.state)
    at_step: dict[int, str] = {}
    for event in _customer_visible_events(request):
        if event["to_state"] is None:
            continue
        at_step.setdefault(_step_index(event["to_state"]), event["at"])
    return [
        {
            "key": key,
            "state": "done" if index < reached else ("current" if index == reached else "future"),
            "at": at_step.get(index),
        }
        for index, (key, _) in enumerate(PROGRESS_STEPS)
    ]


def contact_phones(tenant_id: Any, account_ids: list[Any]) -> list[str]:
    """EVERY distinct phone on this login's accounts — not the most common one.

    ⚠ **`contact_details` ANSWERS ONE VALUE BECAUSE THE SCREEN OFFERS ONE FIELD;
    THIS ANSWERS THEM ALL BECAUSE IT IS A FILTER.** Maria's four accounts may
    carry three different numbers, and a request raised against the fourth would
    be invisible to her if this narrowed to the modal one.
    """
    rows = (
        customers_models.Contact.objects.filter(
            tenant_id=tenant_id,
            account_id__in=[str(one) for one in account_ids],
            deleted_at__isnull=True,
            is_primary=True,
        )
        .exclude(phone__isnull=True)
        .exclude(phone="")
        .values_list("phone", flat=True)
    )
    return sorted({str(one) for one in rows})


def my_requests(tenant_id: Any, *, phones: list[str]):
    """Every request THIS LOGIN raised through the portal — tenant and the
    login's own contact facts, **both in the QUERY** (`BR-CWP-010`, `G96`).

    ⚠ **THE PHONE IS A PROXY FOR AN ACCOUNT LINK THAT DOES NOT EXIST, AND THAT
    IS `OQ-CWP-1680`.** `create_from_portal` *"links no account and changes
    none"* (`BR-CWP-026`), so a service request carries no `account_id` and no
    customer — there is literally no column to intersect the session's account
    set against. What the row DOES carry is `applicant_phone`, which every
    portal write takes from `contact_details` of the accounts already proved to
    be in this session's set (the shape `plan_request` established on
    2026-09-04, and which refuses outright when there is no phone).
    **So the filter is: this tenant · this channel · a phone one of my own
    accounts holds — three clauses, all three in the query.**
    **What it does not stop, stated so nobody has to discover it:** two
    customers of one utility who share a telephone number would see each other's
    portal requests. That is narrower than the guest tracker ships with today (a
    reference plus one public fact) and it is not narrow enough to be the
    permanent answer, which is why the question is minted rather than decided.
    """
    if not phones:
        # ⚠ **THE TENANT IS NAMED EVEN ON THE ANSWER THAT CANNOT RETURN A ROW**
        # (`G96`). `.objects.none()` was the first draft and the gate refused
        # it, correctly: `BR-CWP-010` is about the QUERY'S TEXT, not about how
        # many rows it happens to return, and a chain that omits the tenant is
        # one refactor away from omitting it where it matters.
        return customers_models.ServiceRequest.objects.filter(tenant_id=tenant_id, pk__in=[])
    return customers_models.ServiceRequest.objects.filter(
        tenant_id=tenant_id,
        channel=CHANNEL_CUSTOMER_PORTAL,
        applicant_phone__in=list(phones),
    ).order_by("-received_at", "-id")


def my_request(tenant_id: Any, *, reference: str, phones: list[str]) -> Any:
    """One of mine, by its `SR-` number, or None.

    ⚠ **ONE ANSWER FOR THREE FAILURES** — an unknown reference, another
    customer's reference and another tenant's reference all return `None`, so
    the endpoint's 404 cannot be used to learn that a reference exists
    (`US-CWP-063` TC-7, and `selectors.track`'s own reasoning one screen along).
    """
    typed = str(reference or "").strip()
    if not typed:
        return None
    return my_requests(tenant_id, phones=phones).filter(request_no__iexact=typed).first()


def open_query_on_bill(tenant_id: Any, *, bill_number: str, phones: list[str]) -> Any:
    """An OPEN query this login already raised about this bill, or None
    (`US-CWP-065` TC-9).

    ⚠ **IT MATCHES THE SENTENCE THE WRITE PUT THERE, BECAUSE THERE IS NO COLUMN
    TO MATCH ON.** `US-CWP-066` §5 maps *which bill* to
    `service_request.invoice_id` and **there is no such column** — the same
    finding `DEF-CWP-3701` recorded for `category`, filed again as
    `DEF-CWP-3881`. So the bill number travels in `what_they_said`, the column
    this product already keeps *"the applicant's own words"* in, and this reads
    it back.
    **Both halves are matched — the query's own marker AND the number** — so a
    QUESTION about the same bill (`CWP-054`, which writes a different marker) is
    not mistaken for a query of it. The posture is `open_report_on_street`'s,
    deliberately: an `icontains` over words a write of OURS put there, and
    nothing cleverer.
    """
    typed = str(bill_number or "").strip()
    if not typed:
        return None
    return (
        my_requests(tenant_id, phones=phones)
        .filter(what_they_said__icontains=DISPUTE_MARKER)
        .filter(what_they_said__icontains=typed)
        .exclude(state__in=customers_models.ServiceRequest.TERMINAL_STATES)
        .first()
    )


def request_detail_view(request: Any, *, today: Any) -> dict[str, Any]:
    """`CWP-051` whole — **the customer-safe half and nothing beside it.**

    ⚠ **READ THE KEYS AS THE RULE** (`BR-CWP-078`, B14 rule 31). The REFERENCE
    is the identity — never `request.id`, which is not on the wire at all. There
    is no applicant name, no fee, no assigned clerk, no evidence snapshot and no
    resolved premises id; a field that is served and merely not drawn is still
    served.

    ⚠ **`open_for` IS COMPUTED AND NEVER STORED** (`US-CWP-063` TC-9, §5 —
    *"now − raised"*). A stored age is wrong by one every midnight.

    ⚠ **A REFUSAL ALWAYS CARRIES ITS REASON AND THE PORTAL SHOWS IT**
    (`BR-CWP-077`, TC-10). `decision_reason` is the clerk's own sentence; where
    a refused request somehow carries none, the key is `null` and the screen
    says so — it never invents one.
    """
    raised_on = request.received_at or request.submitted_at
    open_for = None
    if raised_on is not None:
        open_for = (today - raised_on.date()).days
    return {
        "reference": request.request_no,
        #: ⚠ **WHAT THIS REQUEST IS, AND IT IS NOT `what_they_said`**
        #: (`CR-085` `CPB-05`/`CPB-12`, `DEF-CWP-4201`). `CWP-051` headed every
        #: request *"Track your request"*, so a customer with two open could
        #: not tell from the head which one they had opened. See `request_kind`
        #: for why this is derived rather than stored.
        "title": request_kind(request.what_they_said),
        #: The channel, as the row carries it — the drawing's *through the
        #: portal* under the first step. Served rather than assumed by the
        #: screen (hard-won law 1), even though `my_requests` can only ever
        #: return a portal row.
        "raised_through": request.channel,
        "status": request.state,
        "is_open": request.state not in customers_models.ServiceRequest.TERMINAL_STATES,
        #: ⚠⚠ **`DEF-CUS-5874` — THIS LINE CLAIMED TO READ THE STATE TABLE AND
        #: DID NOT.** The comment above it said the control was *"drawn from
        #: the SAME table the write refuses on, so a screen cannot offer a
        #: withdrawal the server denies"* — and the four states were typed out
        #: here by hand, a second copy that nothing compared with the first.
        #: A comment claiming a guarantee is not the guarantee (hard-won law 1).
        #:
        #: **It was true the day it was written and it was one ruling from
        #: being false.** On 2026-09-19 the PO left the request five states and
        #: `withdraw` left `TRANSITIONS` — so this hardcoded list would have
        #: gone on drawing a **Withdraw** button on a customer's own screen
        #: over a write the server now refuses, which is hard-won law 2's
        #: mirror on a customer-facing page.
        #:
        #: It asks the table now. `withdraw` is not in it, so this is `False`
        #: everywhere, the button is not drawn, and if the PO ever puts the
        #: move back the button returns with it and nothing here changes.
        "may_withdraw": _may_withdraw(request.state),
        "raised_at": raised_on.isoformat() if raised_on else None,
        "open_for_days": open_for,
        #: What the applicant said, which is what they typed. Never the clerk's
        #: `lookup_found` beside it — that is the utility's working note.
        "what_they_said": request.what_they_said,
        #: `waiting_on` is ORTHOGONAL to state (the model's own word) and is the
        #: one thing a customer most wants: *what are you waiting for?*
        "waiting_on": request.waiting_on,
        #: `BR-CWP-077` — and it is read from wherever the product put it; see
        #: `refusal_reason` for why that is two places.
        "refusal_reason": (
            refusal_reason(request)
            if request.state == customers_models.ServiceRequest.REFUSED
            else None
        ),
        "closed_at": request.closed_at.isoformat() if request.closed_at else None,
        "steps": progress_steps(request),
        "timeline": _customer_visible_events(request),
    }
# ═══════════════════════════════════════════════════════════════════════════
# CR-068 · `CWP-046` — WHAT A REQUEST IS STILL WAITING FOR (US-CWP-060)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **WHICH REQUESTS ARE *MINE* IS ANSWERED BY `my_requests` ABOVE AND NOT
# HERE.** This lane wrote a second implementation of that read — matching on
# the EMAIL the customer signed in with rather than on a phone their accounts
# carry — before seeing the sibling's, which landed first and is the one the
# hub now calls. Two reads of one fact are two answers, which is the whole of
# `12-reuse-map.md`; the duplicate was deleted at merge rather than kept.
# `OQ-CWP-1680` is the open question behind both, and this lane's `OQ-CWP-1640`
# was dropped into it for the same reason (law 13 — never ask one thing twice).


def documents_still_wanted(tenant_id: Any, request_ids: list[Any]) -> dict[str, int]:
    """`{request_id: how many required documents are not yet VERIFIED}`.

    ⚠ **VERIFIED, NOT ATTACHED — THE MODEL DRAWS THAT LINE AND SO DOES THIS.**
    `ServiceRequestDocument`'s own words: *"attaching a file is not the same as
    verifying it"*, and the two live in different columns. A customer who has
    sent a document that nobody has checked yet is still waiting on it, so it is
    still counted; telling them otherwise would have them wonder why the request
    has not moved.

    Only `required_flag` rows count. An optional attachment the applicant
    volunteered is not something we are waiting for.
    """
    ids = [str(one) for one in request_ids]
    if not ids:
        return {}
    rows = customers_models.ServiceRequestDocument.objects.filter(
        tenant_id=tenant_id,
        request_id__in=ids,
        required_flag=True,
    ).exclude(verification_state=customers_models.ServiceRequestDocument.VERIFIED)
    counts: dict[str, int] = {}
    for request_id in rows.values_list("request_id", flat=True):
        key = str(request_id)
        counts[key] = counts.get(key, 0) + 1
    return counts


def temporary_stop_view(account_id: Any) -> dict[str, Any]:
    """`CR-183-BRC10` T8 — the account's temporary stop, CUSTOMER-SAFE.

    The live hold (scheduled or running) with its two dates and whether a
    restart ask may be sent (B4), and — when no hold is live — the latest ask
    still waiting for a clerk, by its REFERENCE and state. **What is dropped,
    by name:** every id, the work-order numbers, the clerk who approved, the
    channel. A customer is told what is happening to their supply and when.
    """
    from apps.customers import temporary_stop
    from apps.customers.temporary_stop_models import STATUS_REQUESTED, TemporaryStop

    live = temporary_stop.live_for_account(account_id)
    verdict = temporary_stop.can_ask_restart(account_id)
    pending = None
    if live is None:
        asked = (
            TemporaryStop.objects.select_related("request")
            .filter(tenant_id=_tenant(), account_id=account_id, status=STATUS_REQUESTED)
            .order_by("-created_at")
            .first()
        )
        if asked is not None and asked.request is not None:
            pending = {
                "reference": asked.request.request_no,
                "state": asked.request.state,
                "stop_from": asked.stop_from.isoformat(),
                "restart_on": asked.restart_on.isoformat() if asked.restart_on else None,
            }
    current = None
    if live is not None:
        restart = live.restart_request
        current = {
            "status": live.status,
            "stop_from": live.stop_from.isoformat(),
            "restart_on": live.restart_on.isoformat() if live.restart_on else None,
            "restart_reference": restart.request_no if restart else None,
            "restart_state": restart.state if restart else None,
        }
    return {
        "current": current,
        "pending": pending,
        "can_restart_now": bool(verdict["allowed"]),
        "billed_during_hold": temporary_stop.BILLED_DURING_HOLD,
    }
