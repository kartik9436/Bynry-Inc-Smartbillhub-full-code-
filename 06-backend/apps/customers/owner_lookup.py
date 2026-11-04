# ── Trace ──────────────────────────────────────────────
# Change:   CR-164-BRC10 item 11 (lane NC-C, 2026-10-02) — New Connection step 1
#           loses its *Customer ID* search box and looks the owner up by itself.
# Rules:    PO ruling Q5 of 2026-10-02 (decision log *"NEW CONNECTION — THE PO'S
#           SCREEN-BY-SCREEN REVIEW BECOMES ONE PROGRAMME"*), verbatim:
#           *"customer match within the tenant: SSN or DL exact = match; name +
#           DOB = possible match; name alone or DOB alone = no match"* ·
#           BR-CUS-019 (the duplicate check is ADVISORY — staff decides) ·
#           BR-CUS-092(c) (last four only, never a full identifier on a read) ·
#           BR-CUS-1022 (a person and a company are never the same party) ·
#           B14 rule 31 (the customer NUMBER is shown, the id is a handle).
# Change:   CR-171-BRC10 P1.09 + P1.11 read side (lane MVI-IDN, 2026-10-05) —
#           the move-in's *Search customer ID* is the SAME door asked a second
#           question (`purpose: "search_customer_id"`): Found / Possible / New
#           (Q5's rule since the 2026-10-05 ruling below; it was the MONEY
#           test until then), with each candidate's accounts, addresses,
#           states, outstanding and a total. See `search` below.
# Rules:    decision log 2026-10-05 *"SEARCH CUSTOMER ID" ON THE CUSTOMER STEP,
#           USING THE MATCH RULES WE ALREADY HAVE* · BR-CUS-089 / BR-CUS-1022
#           (found) · BR-CUS-019 (possible is advisory) · BR-CUS-092 (last
#           four) · BR-CUS-054 as amended by CR-060 C16 (the statement's money
#           rules) · hard rule 8 (address walked to premises) · DEF-127
#           (balance is the ledger's, never the cache).
# Change:   CR-171-BRC10 lane RULINGS (2026-10-05) — the search's verdicts ARE
#           Q5's. PO ruling, decision log *"FOUR PO RULINGS IN ONE REPLY"* (1),
#           verbatim: *"if match based on our logic then we say match if it is
#           not then we dont say it"*. A name-only hit is no longer shown and
#           there is no possible tier wider than Q5's own.
# Change:   CR-181-BRC10 B1 (lane REOPEN, 2026-10-13) — two levels BELOW Q5's
#           on the move-in's search: *same name and phone* and *the unit's last
#           occupant*, each with what its accounts owe, plus the *Reopen AC-…*
#           offer. PO verbatim: *"Q1 C both"* — SUPERSEDES IN PART the
#           2026-10-05 ruling above for this search only; New Connection's
#           answer (`_q5_lookup`) is unchanged.
# ───────────────────────────────────────────────────────
"""THE OWNER LOOKUP NEW CONNECTION STEP 1 RUNS WHILE THE CLERK TYPES.

**IT LINKS NOTHING AND WRITES NOTHING.** It answers one question — *is this
somebody we already hold?* — and the clerk answers the next one with *Use this
customer* or *Not this person*. Using the customer puts its id on the commit
payload (`customer.customer_id`), exactly as the search box it replaces did.

── WHY THIS IS NOT `identity_match.recognise` ────────────────────────────────
`recognise` answers the MONEY question (BR-CUS-089: name + date of birth + one
government ID before a deposit may move). Q5 answers a narrower, earlier one —
*should the clerk be shown this row?* — and the PO drew its lines differently:

  * **MATCH** — a person's SSN or driving licence, or a company's Tax ID, is
    exactly the one on file. That is `identity_match.REUSE_ID_FIELDS`, the same
    test that already stops a second customer row being made for one SSN
    (`DEF-2587`), so the screen and the door that writes cannot disagree.
  * **POSSIBLE** — the name AND the date of birth both agree (a person only;
    a company has no date of birth, `OQ-1241`).
  * **NOTHING** — a name alone, a date of birth alone, a phone alone.

Neither verdict moves money or links anything, so neither touches BR-CUS-089:
a clerk who presses *Use this customer* is making BR-CUS-019's explicit choice,
and the commit's own link step still applies the money test to its own tier.

⚠ **THE COMPARISON IS `identity_match`'s, NOT A SECOND ONE.** Candidates come
from `find_candidates` (blind-index equality plus an exact name, narrowed to
the kind) and agreement from `agreed_facts` (absent never agrees). This file
only sorts what those two return into the PO's three verdicts.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from apps.customers import identity_match, models, seams, selectors
from core.crypto import last_four

VERDICT_MATCH = "match"
VERDICT_POSSIBLE = "possible"

#: How many candidates a screen is shown. Bounded because this is a read a
#: clerk triggers by typing; a name shared by hundreds of rows would otherwise
#: be an unbounded payload (NFR-3). The verdict is decided over EVERY candidate
#: the probes return — only the list handed back is cut.
MAX_SHOWN = 5


def verdict_for(agreed: list[str], kind: str | None) -> str | None:
    """Q5's three answers over the facts `agreed_facts` found to agree."""
    facts = set(agreed)
    ids = identity_match.REUSE_ID_FIELDS.get(kind or "", ())
    if any(field in facts for field in ids):
        return VERDICT_MATCH
    if (
        kind == identity_match.KIND_PERSON
        and identity_match.FACT_NAME in facts
        and identity_match.FACT_DOB in facts
    ):
        return VERDICT_POSSIBLE
    return None


def lookup(payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /customers/match` — the verdict and the rows a clerk may look at.

    With `purpose: "search_customer_id"` the answer ALSO carries `search`
    (CR-171 P1.09). Without it the answer is byte-for-byte New Connection's,
    which `test_cr164_owner_lookup.py` pins — that screen calls this while the
    clerk types, and must not pay for a ledger read per keystroke.
    """
    answer = _q5_lookup(payload)
    if isinstance(payload, dict) and payload.get("purpose") == PURPOSE_SEARCH:
        answer["search"] = search(payload)
    return answer


def _q5_lookup(payload: dict[str, Any]) -> dict[str, Any]:
    evidence = identity_match.from_payload(payload)
    if not evidence.has_any():
        return {"verdict": None, "candidates": []}

    found: list[dict[str, Any]] = []
    for customer in identity_match.find_candidates(evidence):
        agreed = identity_match.agreed_facts(evidence, customer)
        verdict = verdict_for(agreed, customer.kind)
        if verdict is None:
            continue
        found.append(
            {
                "id": str(customer.id),
                "customer_no": customer.customer_no,
                "display_name": customer.display_name,
                "kind": customer.kind,
                "verdict": verdict,
                "agreed": agreed,
                "date_of_birth": (
                    customer.date_of_birth.isoformat() if customer.date_of_birth else None
                ),
                "phone": customer.phone or None,
                "ssn_last4": last_four(customer.ssn) if customer.ssn else None,
                "driving_licence_last4": (
                    last_four(customer.driving_licence) if customer.driving_licence else None
                ),
                "tax_id_last4": last_four(customer.tax_id) if customer.tax_id else None,
            }
        )
    # A match outranks a possible match; within a verdict the older row first,
    # which is `find_candidates`' own order.
    found.sort(key=lambda row: 0 if row["verdict"] == VERDICT_MATCH else 1)
    verdict = found[0]["verdict"] if found else None
    return {"verdict": verdict, "candidates": found[:MAX_SHOWN]}


# ═══════════════════════════════════════════════════════════════════════════
# CR-171 P1.09 — THE MOVE-IN'S *SEARCH CUSTOMER ID*
# ═══════════════════════════════════════════════════════════════════════════
#: The `purpose` that asks this door the move-in's question.
PURPOSE_SEARCH = "search_customer_id"

RESULT_FOUND = "found"
RESULT_POSSIBLE = "possible"
RESULT_NEW = "new"
#: CR-181-BRC10 Q1 (C) — the two levels BELOW Q5's, on the move-in's search
#: only. *Same name and phone*: both agree, and nothing Q5 counts does.
#: *Last occupant*: the name typed is the name of whoever held the unit's most
#: recently closed account — the case the PO tested (Viktor Valdez, whose
#: record holds only a name and a phone, typed with a different phone).
RESULT_NAME_PHONE = "name_phone"
RESULT_LAST_OCCUPANT = "last_occupant"

#: Q5's verdict → the search's word for it. ONE mapping, so the search can
#: never show a customer New Connection would not, or call them anything else
#: (PO ruling 2026-10-05, *"if match based on our logic then we say match if it
#: is not then we dont say it"*).
_SEARCH_WORD = {VERDICT_MATCH: RESULT_FOUND, VERDICT_POSSIBLE: RESULT_POSSIBLE}
#: The whole vocabulary a screen may draw, strongest first — the order rows
#: are listed in and `result` is the first of. ⚠ It read *"There is no third
#: verdict"* until CR-181-BRC10 (PO 2026-10-13, *"Q1 C both"*) added two.
SEARCH_VERDICTS: tuple[str, ...] = (
    RESULT_FOUND,
    RESULT_POSSIBLE,
    RESULT_NAME_PHONE,
    RESULT_LAST_OCCUPANT,
)
SEARCH_RESULTS: tuple[str, ...] = (*SEARCH_VERDICTS, RESULT_NEW)
_RANK = {verdict: rank for rank, verdict in enumerate(SEARCH_VERDICTS)}

#: How many of ONE customer's accounts are listed beside them. The count and
#: the totals are over EVERY account; only the rows handed back are cut, the
#: same posture as `MAX_SHOWN` (NFR-3: a landlord holding 300 accounts is a
#: T5 fact, and this panel is a read a clerk triggers by pressing a button).
#: Rows that owe something come first, so a cut never hides the debt.
MAX_ACCOUNTS_SHOWN = 10

_ZERO = Decimal("0")


def search(payload: dict[str, Any]) -> dict[str, Any]:
    """*Search customer ID* — **found**, **possible** or **new**, and why.

    ⚖️ **THE VERDICT IS Q5's — THE SAME RULE NEW CONNECTION USES — AND NOTHING
    ELSE.** PO ruling 2026-10-05 (decision log *"FOUR PO RULINGS IN ONE
    REPLY"* (1)), verbatim: *"if match based on our logic then we say match if
    it is not then we dont say it"*. So each customer is judged by
    `verdict_for`, exactly as `_q5_lookup` judges it:

      * **found** — Q5's *match*: a person's SSN or driving licence, or a
        company's Tax ID, is the one on file;
      * **possible** — Q5's *possible*: a person's name AND date of birth;
      * **not shown** — anything less: a name alone, a date of birth alone, a
        phone. Rosa typed with a different date of birth is NOT a possible
        match; image 35's *"Only the name matches."* is superseded and not
        built.

    ⚠ **THIS REVERSES LANE MVI-IDN's JUDGMENTS (1)–(4) OF 2.522.0**, which made
    *found* the money test (`tier_for`) and *possible* every row
    `find_candidates` surfaced. `tier` is still served beside each customer —
    it is what the commit's own link step will apply (`BR-CUS-089`) — but it is
    NOT the verdict and a screen must not draw it as one.

    Two customers both matching (two rows holding one SSN) are BOTH found, as
    New Connection shows them; the clerk picks one with *Use this customer*.

    ⚠ **THE OUTSTANDING AMOUNT IS SHOWN, NEVER MOVED.** This function writes
    nothing; the figures are `customer_statement`'s, which are the LEDGER's
    (`DEF-127`), never `accounts.balance`.

    `result` is `None` when there is nothing to judge (no kind, or no fact but
    a name) — not *new*: *new* is a claim that nobody is on file.

    ⊕ **CR-181-BRC10 (PO 2026-10-13, *"Q1 C both"*) — TWO WEAKER LEVELS,
    BELOW Q5's, ON THIS SEARCH ONLY:**

      * **name_phone** — the name AND the phone agree and nothing Q5 counts
        does (a record holding only a name and a phone can never reach Q5);
      * **last_occupant** — `unit_id` names the move-in's unit and the name
        typed is the name of a customer on that unit's most recently closed
        account. A name alone is enough HERE, because the unit narrows it to
        one household; it is never enough anywhere else.

    Every row the unit is given for also carries `reopen` — the customer's
    closed account on THIS unit, whether it may be reopened and what it owes
    (`move_in_reopen.offer_for`) — and `last_occupant: true` when the customer
    held the unit's last account. An `email` in the body is IGNORED: a
    customer row holds no email (it lives on an account's contact), so there
    is nothing on file to compare it with.
    """
    unit_id = _unit_id(payload.get("unit_id") if isinstance(payload, dict) else None)
    return search_evidence(identity_match.from_payload(payload), unit_id=unit_id)


def _unit_id(raw: Any) -> str | None:
    """A well-formed unit id, or None. Checked HERE rather than caught at the
    query: on PostgreSQL a malformed uuid in a filter aborts the transaction
    (hard-won law 14), so it must never reach one."""
    if raw in (None, ""):
        return None
    try:
        return str(UUID(str(raw)))
    except (TypeError, ValueError):
        return None


def search_for_request(request: Any) -> dict[str, Any]:
    """`DEF-CUS-10043` (PO 2026-10-11) — the Approve dialog's *Search customer*,
    asked with the identity the APPLICATION already holds (name, date of birth,
    SSN, driving licence, phone — `identity_match.evidence_from_service_request`).
    PO, verbatim: *"please use existing customer ID search function. We already
    build this compotent and rules - use existing rule"* — so this is the
    move-in's *Search customer ID*, the same verdicts, asked a second way; no
    identifier crosses the wire in either direction (last four only)."""
    return search_evidence(identity_match.evidence_from_service_request(request))


def _name_phone(agreed: list[str]) -> bool:
    facts = set(agreed)
    return identity_match.FACT_NAME in facts and identity_match.FACT_PHONE in facts


def _last_occupants(unit_id: str | None, evidence: Any) -> tuple[set[str], list[Any]]:
    """`(ids of every customer on the unit's last closed account, those whose
    NAME is the one typed)`. A cancelled move-in never lived there."""
    from apps.customers import move_in_cancel

    if not unit_id:
        return set(), []
    previous = selectors.last_closed_account_for_unit(unit_id)
    if previous is None or move_in_cancel.is_cancelled(previous):
        return set(), []
    holders = list(
        models.Customer.objects.filter(
            tenant_id=previous.tenant_id,
            pk__in=models.CustomerAccount.objects.filter(account_id=previous.id).values(
                "customer_id"
            ),
        ).order_by("created_at")
    )
    typed = identity_match.normalise_name(evidence.name)
    named = [
        customer
        for customer in holders
        if typed
        and identity_match.normalise_name(customer.display_name) == typed
        and (evidence.kind is None or customer.kind == evidence.kind)
    ]
    return {str(customer.id) for customer in holders}, named


def search_evidence(evidence: Any, *, unit_id: str | None = None) -> dict[str, Any]:
    """`search`'s body over evidence already lifted, so two doors share one rule."""
    holders, named = _last_occupants(unit_id, evidence)
    if not evidence.has_any() and not named:
        return {"result": None, "count": 0, "customers": []}

    assessed = []
    seen: set[str] = set()
    for customer in identity_match.find_candidates(evidence):
        agreed = identity_match.agreed_facts(evidence, customer)
        verdict = verdict_for(agreed, customer.kind)
        if verdict is not None:
            word = _SEARCH_WORD[verdict]
        elif _name_phone(agreed):
            word = RESULT_NAME_PHONE  # CR-181 Q1 (C) — the weaker level
        else:
            continue  # our rule does not call this a match, so it is not said
        assessed.append((customer, agreed, word))
        seen.add(str(customer.id))
    for customer in named:
        if str(customer.id) in seen:
            continue
        # The name agreed — that is what put them here — and nothing else did.
        assessed.append((customer, [identity_match.FACT_NAME], RESULT_LAST_OCCUPANT))
        seen.add(str(customer.id))
    if not assessed:
        return {"result": RESULT_NEW, "count": 0, "customers": []}

    # Strongest first; within a level `find_candidates`' own order (oldest
    # first) — `_q5_lookup`'s order, so the two screens list alike.
    assessed.sort(key=lambda row: _RANK[row[2]])
    shown = assessed[:MAX_SHOWN]

    customers = []
    for customer, agreed, verdict in shown:
        customers.append(
            {
                "id": str(customer.id),
                "customer_no": customer.customer_no,
                "display_name": customer.display_name,
                "kind": customer.kind,
                "verdict": verdict,
                "tier": identity_match.tier_for(agreed, customer.kind),
                "agreed": agreed,
                "basis": identity_match.basis_sentence(agreed),
                "ssn_last4": last_four(customer.ssn) if customer.ssn else None,
                "driving_licence_last4": (
                    last_four(customer.driving_licence) if customer.driving_licence else None
                ),
                "tax_id_last4": last_four(customer.tax_id) if customer.tax_id else None,
                # Lane CF-1 (2026-10-18) — the results table's *Date of birth*
                # and *Phone* columns (customer-forms drawing set, image 01).
                # The date is not an identifier under BR-CUS-092 (BR-CUS-1020)
                # and is served in full, as the request's is; the phone is its
                # LAST FOUR only, as every identifier on this read is.
                "date_of_birth": (
                    customer.date_of_birth.isoformat() if customer.date_of_birth else None
                ),
                "phone_last4": last_four(customer.phone) if customer.phone else None,
                "accounts": customer_accounts(customer),
                # A contact's email and phone are served only on a FOUND
                # company — under Q5 its Tax ID is the one on file.
                "company": (
                    company_facts(customer)
                    if verdict == RESULT_FOUND and customer.kind == identity_match.KIND_COMPANY
                    else None
                ),
                # CR-181-BRC10 — did they hold the unit's last account, and
                # may their closed account on this unit be reopened?
                "last_occupant": str(customer.id) in holders,
                "reopen": _reopen_offer(unit_id, customer),
            }
        )
    return {
        "result": shown[0][2],
        "count": len(assessed),
        "customers": customers,
    }


def _reopen_offer(unit_id: str | None, customer: models.Customer) -> dict[str, Any] | None:
    if not unit_id:
        return None
    from apps.customers import move_in_reopen

    return move_in_reopen.offer_for(unit_id, customer.id)


def customer_accounts(customer: models.Customer) -> dict[str, Any]:
    """One customer's accounts: number, address, state, balance, outstanding.

    ⚠ **THE MONEY IS `customer_statement`'s, NOT A SECOND DERIVATION.** Its
    rules hold here: sum within this customer only; a joint account at full
    value; a weak or untiered link SHOWN and MARKED — and, since
    `DEF-CUS-9756`, COUNTED in `outstanding_total` (so the total foots to the
    rows drawn above it), with `unconfident_outstanding` stating how much of it
    rides on such links; no live account is an empty answer. Nothing is
    recomputed from `accounts.balance`.

    **Outstanding is the POSITIVE position** — `accounts_rollup`'s meaning of
    the word: a credit on one account reduces nothing owed on another, so the
    total sums what is owed and `balance` keeps the signed figure beside it.

    **The address is WALKED (hard rule 8):** account → unit → premises, or the
    premises an owner's account names, through `seams.envelope_addresses` —
    two queries for the whole set. The unit travels as a LABEL.
    """
    statement = selectors.customer_statement(str(customer.id)) or {
        "rows": [],
        "available": False,
        "unavailable": (),
        "currency": None,
        "basis": None,
    }
    rows = statement["rows"]
    ids = [row["id"] for row in rows]
    places = {
        str(row["id"]): row
        for row in models.Account.objects.filter(tenant_id=customer.tenant_id, pk__in=ids).values(
            "id", "unit_id", "premises_id", "closed_at"
        )
    }
    envelopes = (
        seams.envelope_addresses(
            unit_ids=[p["unit_id"] for p in places.values() if p["unit_id"]],
            premises_ids=[p["premises_id"] for p in places.values() if p["premises_id"]],
        )
        if places
        else None
    ) or {"units": {}, "premises": {}}

    available = bool(statement["available"])
    total = _ZERO
    unconfident = _ZERO
    out: list[dict[str, Any]] = []
    for row in rows:
        place = places.get(row["id"], {})
        balance = Decimal(row["balance"]) if row["balance"] is not None else None
        owed = max(balance, _ZERO) if balance is not None else None
        if owed is not None:
            # `DEF-CUS-9756` — the total is what the LEDGER says this customer
            # owes across EVERY linked account, the same rows the screen draws
            # under it. It counted strong/probable links only, and every link
            # the product writes itself (a counter create, a move-in, an
            # import) carries no tier — so Rosa, owing $50.00 + $34.20, read
            # $0.00. `unconfident_outstanding` still states how much of the
            # total rides on a weak or untiered link. `customer_statement`
            # (C16's report) keeps its own rule and is not changed here.
            total += owed
            if not row["confident"]:
                unconfident += owed
        out.append(
            {
                "id": row["id"],
                "account_no": row["account_no"],
                "status_code": row["status_code"],
                "status_name": row["status_name"],
                "closed_at": place["closed_at"].isoformat() if place.get("closed_at") else None,
                "address": _address(place, envelopes),
                "balance": row["balance"],
                "outstanding": selectors._money(owed),
                "confident": row["confident"],
                "held_with": row["held_with"],
            }
        )
    # Owed first (largest first), then by number — so a cut never hides debt.
    out.sort(
        key=lambda r: (-(Decimal(r["outstanding"]) if r["outstanding"] else _ZERO), r["account_no"])
    )
    return {
        "count": len(out),
        # Lane CF-1 — *Accounts: 2 · 0 open* counts EVERY account, so it is
        # counted here, before the rows are cut at `MAX_ACCOUNTS_SHOWN`.
        "open_count": sum(1 for row in out if row["closed_at"] is None),
        "rows": out[:MAX_ACCOUNTS_SHOWN],
        "outstanding_total": selectors._money(total) if available else None,
        "unconfident_outstanding": selectors._money(unconfident) if available else None,
        "currency": statement["currency"],
        "basis": statement["basis"],
        "available": available,
        "unavailable": tuple(statement["unavailable"]),
    }


def _address(place: dict[str, Any], envelopes: dict[str, Any]) -> dict[str, Any] | None:
    """The premises' street, town, state and postcode, and the unit's label."""
    env = None
    if place.get("unit_id"):
        env = envelopes["units"].get(str(place["unit_id"]))
    if env is None and place.get("premises_id"):
        env = envelopes["premises"].get(str(place["premises_id"]))
    if env is None:
        return None
    return {key: env.get(key) for key in ("line1", "unit_label", "city", "state", "postal_code")}


def company_facts(customer: models.Customer) -> dict[str, Any]:
    """CR-171 P1.11, READ SIDE — what this product already holds about a company.

    Image 40 asks for legal name, trading as, business type, EIN, registered
    in, a contact person, *Bills go to* and a PO on bills. Every one has a home
    since `customers/0080` (CR-171 §9.1):

      * **legal name, trading as, business type, registered in** — the
        customer row (`display_name` and the three 0080 columns);
      * **PO on bills, bills go to** — `accounts.po_number` and
        `accounts.bills_go_to` of the company's NEWEST account (the one a
        returning company most recently set up; `None` = account holder);
      * **contact person** — the primary `contacts` row (name, job title,
        email, phone, contact by) of the newest account that has one;
      * **mailing address** — that account's `addresses kind='mailing'` row
        (hard rule 8's exception: where the BILL goes), served as
        `bills_go_to_address`.

    The EIN rides as `tax_id_last4` beside this block (`BR-CUS-092`).

    ⚠ **SERVED ONLY ON A SURE MATCH.** An email and a phone are a stranger's
    PII until the match is sure, and the screen prefills from this only after
    *Link customer* — so a possible match carries `company: None`.
    """
    links = (
        models.CustomerAccount.objects.filter(tenant_id=customer.tenant_id, customer_id=customer.id)
        .select_related("account")
        .order_by("-account__created_at", "account__account_no")
    )
    account_by_id = {link.account_id: link.account for link in links}
    order = list(account_by_id)
    newest = account_by_id[order[0]] if order else None

    contact = None
    contacts = models.Contact.objects.filter(
        tenant_id=customer.tenant_id, account_id__in=order, deleted_at__isnull=True
    ).order_by("-is_primary", "created_at", "id")
    first_contact: dict[Any, Any] = {}
    for row in contacts:
        first_contact.setdefault(row.account_id, row)
    for account_id in order:
        row = first_contact.get(account_id)
        if row is not None:
            contact = {
                "full_name": row.full_name,
                "job_title": row.job_title or None,
                "contact_by": row.contact_by or None,
                "email": row.email or None,
                "phone": row.phone or None,
                "account_no": account_by_id[account_id].account_no,
            }
            break

    bills = None
    mailing = models.Address.objects.filter(
        tenant_id=customer.tenant_id, account_id__in=order, kind="mailing", deleted_at__isnull=True
    ).order_by("created_at", "id")
    first_mailing: dict[Any, Any] = {}
    for row in mailing:
        first_mailing.setdefault(row.account_id, row)
    for account_id in order:
        row = first_mailing.get(account_id)
        if row is not None:
            bills = {
                "line1": row.line1,
                "line2": row.line2 or None,
                "city": row.city,
                "state": row.state,
                "postal_code": row.postal_code,
                "country": row.country or None,
                "account_no": account_by_id[account_id].account_no,
            }
            break

    return {
        "legal_name": customer.display_name,
        "trading_as": customer.trading_as or None,
        "business_type": customer.business_type or None,
        "registered_in": customer.registered_in or None,
        "po_number": (newest.po_number or None) if newest is not None else None,
        "bills_go_to": (newest.bills_go_to or None) if newest is not None else None,
        "contact_person": contact,
        "bills_go_to_address": bills,
    }
