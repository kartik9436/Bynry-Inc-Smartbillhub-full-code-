# ── Trace ──────────────────────────────────────────────
# Story:    CR-110-BRC04 phase 2 wave 2 — the Customer API. PO 2026-09-16,
#           verbatim: *"Customers = accounts"* and *"send service address"*.
#           CR-069 §11: one seam file per module integrations reads from.
# Rules:    CLAUDE.md hard rule 8 / BR-MET-1161 (an address is stored on
#           `premises` and NOWHERE else; every other entity derives it by
#           walking there) · BR-CUS-1010 (an owner's account names no unit and
#           hangs off the premises) · BR-CUS-055 (account status is a TENANT
#           lookup, not an enum) · BR-INT-054 (integrations LANDS and HANDS
#           OVER; it does not interpret) · BR-TEN-003 (the tenant is the path)
#           · CLAUDE.md hard rule 1 (no tenant argument) · B14 rule 31 (no
#           database id is ever the visible value of a field) · NFR-3 (the
#           page is taken in SQL)
# Tests:    06-backend/tests/test_cr110_phase2_partner_customers.py
# Impacts:  apps/integrations/partner_api.partner_customers (the one caller) ·
#           apps/integrations/reference.account_statuses (the same lookup,
#           published to the same partner — the test asserts they agree)
# ───────────────────────────────────────────────────────
"""integrations → customers: the CUSTOMERS a partner may collect, which are our
`accounts`.

⚠ **"CUSTOMER" IS AN ACCOUNT HERE AND NOT A `customers` ROW, BY PO RULING.**
2026-09-16, verbatim: *"Customers = accounts"*. So `consumer_no` is the ACCOUNT
number and `customer_name` is the ACCOUNT name — the name on the account, which
is its primary contact's (`selectors.primary_contact_name`'s own rule, because
`BR-CUS-054`'s first-class customer entity is not what a bill is addressed to).
⚠ **EXCEPT FOR A COMPANY, FROM 2026-10-06 (`DEF-INT-9796`, PO ruling D3 (a),
verbatim: *"From the next release, send the company's legal name for company
accounts, and say so in the release notes."*).** A company account is sent
under the company's LEGAL NAME, read from `customers.selectors.company_names_for`
— the same current-customer link the account page names it by
(`DEF-CUS-9776`) — never from a copy here. See `as_record`.
Reading it the other way round would hand a landlord ONE record where the
partner's ledger has fourteen accounts to post against, and every posting after
that would be wrong in a way neither side could see.

⚠ **`id` IS THE ACCOUNT NUMBER AND NOT THE UUID, AND THE SUPPLIED DOCUMENT
SHOWS OTHERWISE.** The vendor's reference prints `"id": 1001`. `seams/billing
.as_record` states the rule for this whole surface — *"a partner keyed on our
uuid is coupled to our storage forever"* — and B14 rule 31 says the same thing
one layer out. `A-10432` is the number a clerk, a customer and their own books
already use; it is recorded as a divergence on the CR rather than quietly
resolved either way.

THE SERVICE ADDRESS IS WALKED TO. IT IS NOT STORED HERE AND NEVER WAS
----------------------------------------------------------------------
PO 2026-09-16: *"send service address"*. Hard rule 8 is what makes that a walk
rather than a column read: **an address lives on `premises` and nowhere else**,
and an account declares none of its own. The walk is the one the customers
module already performs (`selectors._premise_locality`) and it has two legs,
because `BR-CUS-1010` gave an owner's account the right to name no unit:

    account.unit    → unit.premises_id  → premises      (a regular account)
    account.premises_id                 → premises      (a master account)

⚠ **IT IS NOT `customers.addresses` `kind='mailing'`, AND THAT IS THE WHOLE
POINT OF THE PO'S RULING.** The mailing address is where the BILL goes, which
for a landlord is a different building from the one taking service. A finance
system given the mailing address as the service address would reconcile
consumption to the wrong property.

⚠ **AND IT IS NOT `kind='service'` EITHER — THAT KIND IS RETIRED AND IS
REFUSED BY NAME.** `DEF-CUS-3653` is what it cost the last time a screen line
was composed from it: null on every account forever, with `tsc` and every test
green. So every case in this seam's test file reads the VALUE back and compares
it against the `premises` row the fixture built, never merely asserting the key
is present.

WHY THERE IS NO `since` / `until`, UNLIKE BILLS AND PAYMENTS
-------------------------------------------------------------
The CR records the paging trap in as many words: *"Paging by page number over a
moving table SKIPS rows … so every moving set is bounded by `since`/`until`
BEFORE paging."* That is a rule about a set sorted NEWEST FIRST, where a row
arriving between two calls pushes every later row across a page boundary.

**Accounts are not that set.** They are ordered by `account_no` ASCENDING, which
is unique within a tenant (`ux_accounts_no`) and is allocated from the tenant's
own monotonic series (`BR-TEN-035`), so a new account appears at the END of the
order — after any cursor a partner has already passed — and no account number is
ever reused or deleted (every FK onto `accounts` is `PROTECT`). A page walk
therefore cannot skip a row, and a date window would only be able to hide one.

⚠ **THE ONE CASE THAT CAN STILL INSERT MID-ORDER IS NAMED RATHER THAN
WAVED AWAY:** an import that supplies its own account numbers can land a row
BEFORE the cursor. That is what `total_records` in the envelope is for — the
partner's job compares what it pulled against what we said existed, rather than
trusting that it reached the end.

⚠ **AND THE PAGE IS TAKEN IN SQL** (`NFR-3`, and B6's rule that no code path
may enforce a maximum account count per tenant). `collectable()` is the ONE
thing here that leaves as a queryset, and that is the reason: 40,000 accounts
at 1,000 a page is 40 calls, and a seam that returned a list would have
materialised all 40,000 on the first of them.

THREE QUERIES A PAGE, WHATEVER THE PAGE HOLDS
----------------------------------------------
⚠ **A WALK PERFORMED PER ROW IS 40,000 QUERIES AND LOOKS PERFECT ON A DEMO
TENANT WITH TWELVE ACCOUNTS.** That is `DEF-2723` one module along — nine
statements per row behind a 562 ms list — and it is why `page_facts()` exists
and why `as_record()` REFUSES to resolve its own: the keyword is required, so a
loop that forgot to batch cannot be written by accident. Three reads answer a
whole page:

    1 · the accounts themselves, with `status` and `unit` joined in
    2 · the premises for every id the walk resolved, in one `pk__in`
    3 · the primary contact for every account, in one `account_id__in`
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from core.tenancy import current_tenant_id

#: The order a partner's pages are cut in, and the reason there is no date
#: window — see the module docstring. `id` is the tiebreaker rather than the
#: sort: `account_no` is already unique per tenant, and a second column costs
#: nothing and cannot be wrong.
ORDER_BY = ("account_no", "id")

#: Which contact IS "the" name, email and phone of an account when it has
#: several. ⚠ **IT IS `selectors.primary_contact_name`'s ORDER, VERBATIM, AND
#: IT HAS TO BE.** A partner payload that sorted differently would name a
#: different person from the one the account screen shows, for the same
#: account, and nothing on either side could see it (`primary_contact_names_for`
#: says the same thing about its own batched form).
CONTACT_ORDER = ("-is_primary", "created_at", "id")


def _model() -> Any:
    """Imported inside the call so the module graph stays a DAG — integrations
    is loaded at `AppConfig.ready()` and customers must not have to be. `G6`
    refuses a module-scope import of another app's models from here."""
    from apps.customers import models as customers_models

    return customers_models.Account


def _contact_model() -> Any:
    from apps.customers import models as customers_models

    return customers_models.Contact


def _premises_model() -> Any:
    """Metering's `premises` — the ONE home of an address (hard rule 8).

    ⚠ **A MODEL AND NOT A PUBLISHED SELECTOR, WHICH IS A DEPARTURE FROM
    `seams/metering.py` NEXT DOOR AND IS RECORDED AS ONE.** Metering publishes
    `premises_refs()` (plural, but the street line only) and
    `premises_locality()` (city/state/postcode, but SINGULAR). Composing an
    address from those two means calling the singular once per account, which
    is 40,000 statements on the largest utility this product models — the exact
    trap this wave was briefed on. The right long-term shape is a plural
    address read on metering's own selectors; adding one is a cross-module edit
    while three sibling lanes are live in this module (law 11), so it is in
    this lane's report as a recommendation and the one-query read lives here
    meanwhile. `seams/billing.py` and `seams/payments.py` read their
    neighbour's models exactly this way.
    """
    from apps.metering import models as metering_models

    return metering_models.Premises


#: `customers.addresses.kind` — the ONE value this surface reads. Hard rule 8:
#: `mailing` is where the BILL goes and is one of the three lawful homes for an
#: address outside `premises`. ⚠ `service` IS RETIRED and is never asked for
#: here; see `billing_address_map`.
ADDRESS_KIND_MAILING = "mailing"


def _address_model() -> Any:
    """`customers.Address` — the mailing address, the first of hard rule 8's
    three exceptions. Imported inside the call for `_model`'s reason."""
    from apps.customers import models as customers_models

    return customers_models.Address


def _assignment_model() -> Any:
    """`rating.UnitPlanAssignment` — a plan is assigned to a UNIT (B2 r16 #6).

    A model rather than a published selector, which is a departure recorded on
    `plan_code_map` and in this file's lifecycle block: rating publishes the
    singular form only, and composing a page from it is one statement per
    account.
    """
    from apps.rating import models as rating_models

    return rating_models.UnitPlanAssignment


def collectable() -> Any:
    """The queryset a partner's page is cut from. No tenant ARGUMENT — the
    tenant is on the session (hard rule 1).

    ⚠ **NO STATUS FILTER, UNLIKE BILLS AND PAYMENTS, AND THE DIFFERENCE IS
    REAL RATHER THAN AN OMISSION.** Those two withhold a draft and an
    unsettled payment because handing one over would make a finance system post
    a record that is not yet a financial fact. An account has no such state: a
    `closed` account still owns every bill it was ever issued, and a partner
    that could not resolve it would hold postings against a customer it has
    never heard of. Every account this tenant holds is handed over, and its
    status travels WITH it so the partner can decide what to do about it.

    ⚠ **THE `tenant_id` FILTER IS BELT AND BRACES AND IT IS THE SAME PARAGRAPH
    ITS TWO SIBLINGS CARRY.** RLS `FORCE` scopes this on PostgreSQL, so it is
    redundant in production. **The suite runs on SQLite, which has no RLS**
    (`config/settings/test.py` hardcodes it), so a first draft relying on RLS
    alone would let one utility read another's customers and pass the entire
    suite — the one mechanism that stops it does not exist on the vendor the
    suite runs on (law 7, *structurally incapable of failing*). The tenant is
    stated twice so the isolation case can go red on either vendor.

    `select_related` joins the two rows every record needs — the status lookup
    for its label, and the unit for the first leg of the address walk — so a
    page of a thousand is still ONE statement here.
    """
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return _model().objects.none()
    return (
        _model()
        .objects.filter(tenant_id=tenant_id)
        .select_related("status", "unit")
        .order_by(*ORDER_BY)
    )


def premises_id_for(account: Any) -> str | None:
    """Which premises this account's service address is AT — the walk itself.

    Two legs, in `BR-CUS-1010`'s own precedence: an account that names a
    premises directly is an owner's account and that is its address; otherwise
    it is reached through the unit.

    ⚠ **`None` HERE IS DEFENSIVE AND NOT THE ABSENCE A PARTNER MEETS**, which
    is a fact about the schema and was measured rather than assumed:
    `ck_accounts_anchored` refuses a row with neither a unit nor a premises, so
    no lawful account reaches the end of this function empty-handed. The
    absence that DOES reach a payload is a premises id resolving to no row —
    see `address_map`, which is where `address: null` is decided.

    ⚠ **CUSTOMERS OWNS THIS PRECEDENCE AND PUBLISHES IT AS
    `selectors.premises_id_for_account`. THIS IS THE BATCHED FORM OF THAT READ
    AND IT IS DELIBERATELY NOT A SECOND OPINION.** `billing/statement.py`
    already names the hazard in as many words — *"a second walk here would be a
    second statement of `BR-CUS-1010`'s precedence and the one that drifts"* —
    and it reads the answer rather than repeating the walk, correctly, because
    it is asking about ONE account. This surface asks about a thousand, and the
    published read reaches metering through `seams.unit_row` + `unit_dict`,
    which is **a round trip per account**: 40,000 of them on the largest
    utility this product models, invisible on a demo tenant with twelve.

    So the unit leg is taken off the row `collectable()` already joined in, and
    the drift is closed by a TEST rather than by a comment:
    `test_the_walk_agrees_with_the_customers_modules_own_published_read` asserts
    the two answer identically for every shape in the fixture — the unit leg,
    the `premises_id` leg, and the account that resolves to neither. If either
    precedence moves, that case goes red and names the account.
    """
    direct = getattr(account, "premises_id", None)
    if direct not in (None, ""):
        return str(direct)
    unit = getattr(account, "unit", None)
    premises_id = getattr(unit, "premises_id", None) if unit is not None else None
    return str(premises_id) if premises_id not in (None, "") else None


def compose_address(row: Any) -> str | None:
    """One premises row → *"123 Main Street, Austin, TX 78704"*.

    ⚠ **COMPOSED HERE BECAUSE THE PARTNER'S FIELD IS ONE STRING**, which is the
    shape their own specification prints. `billing/statement.py` composes the
    same three locality columns for the same reason — *"a sentence a person
    reads"* — and writes the comma after the CITY only, so this reads the way
    every other address in the product reads.

    A premises whose city was never typed composes to its street line alone.
    That is a fact rather than a failed derivation: nobody recorded the rest,
    and inventing a state or a postcode to fill the shape would be worse than
    the gap.
    """
    if not row:
        return None
    street = str(row.get("address_line") or "").strip()
    locality = [
        str(row.get(part)).strip()
        for part in ("city", "state", "postal_code")
        if str(row.get(part) or "").strip()
    ]
    tail = ""
    if locality:
        tail = locality[0] if len(locality) == 1 else f"{locality[0]}, {' '.join(locality[1:])}"
    parts = [one for one in (street, tail) if one]
    return ", ".join(parts) or None


def address_map(accounts: Any) -> dict[str, str | None]:
    """`{account_id: "123 Main Street, Austin, TX 78704" | None}` — **ONE query
    for a whole page**, both legs of the walk together.

    ⚠ **`None` IS A REAL ANSWER AND THE RECORD IS STILL SERVED.** Three
    ordinary states produce it and none of them is a reason to withhold a
    customer from a partner who is trying to post against it: an account whose
    `premises_id` the `customers 0036` backfill could not resolve (the model's
    own column comment says so), a premises this tenant no longer holds, and —
    on a tenant that has never been migrated — neither leg answering. A record
    dropped from the page would move `total_records` and the partner would
    reconcile a shortfall it cannot explain; a fabricated address would be
    reconciled against the wrong property, which is worse. The field is `null`
    and says nothing it does not know.
    """
    wanted = {str(one.id): premises_id_for(one) for one in accounts}
    ids = sorted({one for one in wanted.values() if one})
    if not ids:
        return {key: None for key in wanted}
    rows = {
        str(row["id"]): row
        for row in _premises_model()
        .objects.filter(tenant_id=current_tenant_id(), pk__in=ids)
        .values("id", "address_line", "city", "state", "postal_code")
    }
    return {
        key: (compose_address(rows.get(premises_id)) if premises_id else None)
        for key, premises_id in wanted.items()
    }


def contact_map(accounts: Any) -> dict[str, dict[str, Any]]:
    """`{account_id: {name, email, phone}}` — **ONE query for a whole page.**

    The FIRST contact per account in `CONTACT_ORDER` wins, which is
    `.first()` applied to a page and is the singular's rule unchanged. An
    account with no contact is absent from the map and its three fields serve
    `null`; a soft-deleted contact is not a contact.
    """
    ids = [str(one.id) for one in accounts]
    if not ids:
        return {}
    found: dict[str, dict[str, Any]] = {}
    for account_id, full_name, email, phone in (
        _contact_model()
        .objects.filter(
            tenant_id=current_tenant_id(), account_id__in=ids, deleted_at__isnull=True
        )
        .order_by(*CONTACT_ORDER)
        .values_list("account_id", "full_name", "email", "phone")
    ):
        found.setdefault(
            str(account_id),
            {"name": full_name or None, "email": email or None, "phone": phone or None},
        )
    return found


def company_map(accounts: Any) -> dict[str, str]:
    """`{account_id: legal name}` for the accounts a COMPANY holds — ONE query
    for a page, and NOT this module's own rule.

    ⚠ **IT IS `customers.selectors.company_names_for`, CALLED, NOT COPIED
    (`DEF-INT-9796`).** `CONTACT_ORDER` above is a copy of a customers rule
    *"verbatim, and it has to be"*, and the day that rule moved to the
    customer's name (`DEF-CUS-9776`, 2.549.8) the copy could not follow — a
    church went to partners as *Ruth Okafor* while its own account page read
    *Grace Fellowship of Cedar Ford*. The company half is read from the module
    that owns it so it cannot drift again.
    """
    from apps.customers import selectors as customers_selectors

    return customers_selectors.company_names_for([one.id for one in accounts])


# ═══════════════════════════════════════════════════════════════════════════
# CR-111-BRC04 · THE SIX FIELDS INVOICE CLOUD'S DOCUMENT ASKS FOR
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **EVERY ONE OF THESE IS A FACT WE ALREADY HOLD, RE-KEYED — NOT A NEW
# TRUTH.** A partner's field names are the SHAPE's business (`shapes.py`), and
# nothing below renames anything: the seam composes OUR record in OUR words and
# the shape re-keys it on the way out. What the seam adds is the six facts the
# record did not carry — a name in two halves, the phone under the name their
# document uses for it, the status as a word, the plan, what the account owes,
# and the two addresses — because a shape may move a value and may never go and
# find one.


def split_name(full_name: Any) -> tuple[str | None, str | None]:
    """*"Marisol Ruiz"* → `("Marisol", "Ruiz")`. The FIRST space splits.

    ⚠ **THIS IS THE ONE PLACE ON THIS SURFACE WHERE A VALUE IS TAKEN APART, AND
    IT IS IN THE SEAM RATHER THAN IN A SHAPE ON PURPOSE.** `shapes.py` may
    rename a field, rename an envelope, reformat a date, flatten, nest or omit
    — and it may not COMPUTE. Splitting a name is a rule about names (which
    space? what about *"van der Berg"*? what about a company?), and a rule is
    computation. Putting it in a shape would have given the money path a second
    home for logic, which is hard-won law 5's shape; putting it here means there
    is exactly one answer and every partner gets the same one.

    ⚠ **THE FIRST SPACE AND NOT THE LAST, AND THE CHOICE COSTS SOMEBODY.** With
    the first space, *"Maria de la Cruz"* gives `("Maria", "de la Cruz")`, which
    is right, and *"Mary Jane Watson"* gives `("Mary", "Jane Watson")`, which is
    wrong. With the last space the two swap places. There is no split that is
    right for both, because the information is not in the string — **we never
    asked for a first and last name, we asked for a name** (`Contact.full_name`
    is one column). So this is a presentation of a fact we do not hold, and the
    honest form of it keeps the WHOLE name recoverable: `first + " " + last`
    reassembles the original exactly, for every input, which
    `test_the_split_is_lossless` asserts over the fixture and over the awkward
    cases above. A partner that needs the real thing joins them back.

    A name with no space at all is a FIRST name and a null last name — not the
    other way round — because a one-word name is far more often a business or a
    mononym than a surname, and `null` says *we were not told* rather than
    inventing an empty string.
    """
    text = str(full_name or "").strip()
    if not text:
        return None, None
    first, space, rest = text.partition(" ")
    return first, (rest.strip() or None) if space else None


def billing_address_map(accounts: Any) -> dict[str, str | None]:
    """`{account_id: "PO Box 12, Austin, TX 78704" | None}` — **ONE query for a
    whole page** — the address the BILL goes to.

    ⚠ **`kind='mailing'`, AND `kind='service'` IS NEVER ASKED FOR.** Hard rule 8
    names exactly three lawful homes for an address outside `premises`, and this
    is the first of them: where the bill goes, which for a landlord is another
    building entirely. **`kind='service'` is RETIRED** — it held zero rows, was
    read by nothing, and a write asking for it is refused BY NAME — so this
    filter names `mailing` explicitly rather than excluding `service`, which
    would start answering differently the day a fourth kind is added.

    ⚠ **THE FALLBACK IS PART OF THE ANSWER, NOT A CONSOLATION.** An account with
    no mailing row is billed where it takes service, which is what this product
    actually does, so the partner is told the same address our own envelope
    carries. Returning `null` instead would tell a finance system *we do not know
    where to send this* about an account we post to every month. The two are
    still distinguishable in the payload: `territory_data` carries both legs, so
    a partner that cares can see that the billing address IS the service address
    rather than being told it separately.

    ⚠ **AND IT IS DELIBERATELY NOT `DEF-CUS-3653`'s MISTAKE.** That defect was a
    screen line composed from the retired kind, which returned null on every
    account for ever with `tsc` and every test green. So the test for this
    function reads the VALUE back and compares it against the `addresses` row the
    fixture wrote, and asserts the fallback separately — never merely that the
    key is present.
    """
    wanted = [str(one.id) for one in accounts]
    if not wanted:
        return {}
    found: dict[str, str | None] = {}
    for row in (
        _address_model()
        .objects.filter(
            tenant_id=current_tenant_id(), account_id__in=wanted, kind=ADDRESS_KIND_MAILING
        )
        .order_by("account_id", "created_at", "id")
        .values("account_id", "line1", "line2", "city", "state", "postal_code")
    ):
        key = str(row["account_id"])
        if key in found:
            continue  # the FIRST mailing row per account, deterministically
        found[key] = compose_address(
            {
                "address_line": " ".join(
                    part for part in (row.get("line1"), row.get("line2")) if str(part or "").strip()
                ),
                "city": row.get("city"),
                "state": row.get("state"),
                "postal_code": row.get("postal_code"),
            }
        )
    return {key: found.get(key) for key in wanted}


def plan_code_map(accounts: Any) -> dict[str, str | None]:
    """`{account_id: "RES-E-01" | None}` — **ONE query for a whole page** — the
    rate plan in force on the unit each account is at.

    ⚠ **PO 2026-09-17, verbatim: `remote_plan_id` is *"this rate plan ID for
    that account"*, AND IN `consumer-info` ONLY** — they were asked *"in which
    APis is this required"* and it appears in no other payload of their
    document. `as_record(..., with_detail=True)` is the one caller.

    ⚠ **AN ACCOUNT HAS NO PLAN; A UNIT DOES.** `unit_plan_assignments` is
    rating-owned (B2 r16 #6) and is keyed on the UNIT, so the read is
    account → unit → the assignment with no `assigned_to`, which is the open
    stretch. That is the product's own precedence and not a second opinion:
    `rating.selectors` asks the identical question with the identical filter
    wherever it needs the plan in force, and `DEF-RAT-4664` is what it cost the
    last time a lane called a count of units a count of accounts.

    ⚠ **THE CODE, NOT THE UUID** — B14 rule 31, and this seam's own rule that a
    partner keyed on our uuid is coupled to our storage for ever. PO 2026-09-17
    on how our ids travel: *"a) they store our text exactly as we send it"*, so
    `RES-E-01` goes out and `RES-E-01` comes back. There is no integer to mint
    and no second identity to keep.

    ⚠ **A MASTER ACCOUNT NAMES NO UNIT (`BR-CUS-1010`) AND THEREFORE HAS NO
    PLAN HERE, AND `null` IS THE TRUE ANSWER.** An owner's account hangs off the
    premises; the plan lives on the units below it, and there may be fourteen of
    them on four different plans. Picking one would be inventing.

    ⚠ **THIS READS `rating.models.UnitPlanAssignment` DIRECTLY, WHICH IS A
    DEPARTURE AND IS RECORDED AS ONE** — the same departure, for the same
    reason, that `_premises_model` above already carries. Rating publishes
    `unit_plan_assignments_in(unit_id, …)`, which is SINGULAR: composing a page
    from it is one statement per account, 40,000 of them on the largest utility
    this product models, and invisible on a demo tenant with twelve. A plural
    read on rating's own selectors is the right long-term shape and is in this
    lane's report as a recommendation; it is not taken here while other lanes
    are live in this module (law 11).
    """
    by_unit: dict[str, list[str]] = {}
    for one in accounts:
        unit_id = getattr(one, "unit_id", None)
        if unit_id not in (None, ""):
            by_unit.setdefault(str(unit_id), []).append(str(one.id))
    if not by_unit:
        return {str(one.id): None for one in accounts}
    codes: dict[str, str | None] = {}
    for unit_id, code in (
        _assignment_model()
        .objects.filter(
            tenant_id=current_tenant_id(),
            unit_id__in=sorted(by_unit),
            assigned_to__isnull=True,
        )
        .order_by("unit_id", "-assigned_from", "-created_at")
        .values_list("unit_id", "rate_plan__code")
    ):
        codes.setdefault(str(unit_id), str(code) if code else None)
    answer = {str(one.id): None for one in accounts}
    for unit_id, account_ids in by_unit.items():
        for account_id in account_ids:
            answer[account_id] = codes.get(unit_id)
    return answer


def balance_map(accounts: Any) -> dict[str, str | None]:
    """`{account_id: "142.1800" | None}` — what each account owes NOW.

    ⚠ **FOUR DECIMALS ON THE WIRE, NOT TWO (hard rule 2).** Money is stored to
    four and DISPLAYED to two, and this is not a display: a finance system posts
    from it. `seams/billing.display_amount` quantizes to two because the bill
    payload is what a person reads on a partner's screen; an `opening_balance`
    a partner reconciles against is the stored figure, as text, never a float.

    ⚠ **A STRING AND NEVER A NUMBER.** JSON has one numeric type and it is
    binary floating point, so `142.18` serialised as a number is `142.18000000
    000000682121026329696178436279296875` at the far end, and a partner summing
    a page of them drifts. Every money field on this surface is a string for
    that reason, which `seams/billing` already does and says.

    ⚠ **WHAT "OPENING BALANCE" MEANS HERE IS OUR READING AND IS RECORDED AS
    ONE.** Their document names the field `opening_balance`; we serve **what the
    account owes now**, which is `billing.open_balance` — the same figure the
    bill payload calls `amount` and the same one a clerk sees on the account. The
    other reading — *the balance at the start of some period* — needs a period
    nobody has named, and this surface has no period on the customer route at
    all. **This is exactly the trap `CR-110-BRC04` recorded when the phase-1
    routes were retired** — one key, two meanings, and a finance system cannot
    see the difference — so it is written down here and in this lane's report
    rather than left to be discovered by a reconciliation that will not balance.

    `None` where the balance could not be computed, never `0.00`: a partner told
    an account in arrears is square posts that.
    """
    keys = [str(one.id) for one in accounts]
    if not keys:
        return {}
    from apps.billing import open_balance

    positions = open_balance.open_balances_for_accounts(keys)
    answer: dict[str, str | None] = {}
    for key in keys:
        position = positions.get(key)
        value = getattr(position, "open_balance", None) if position is not None else None
        answer[key] = None if value is None else str(Decimal(str(value)).quantize(Decimal("0.0001")))
    return answer


def page_facts(accounts: Any, *, detail: bool = False) -> dict[str, Any]:
    """Every page-wide read, resolved ONCE for the whole page.

    ⚠⚠ **`detail` EXISTS BECAUSE `opening_balance` AND `remote_plan_id` ARE NOT
    BOTH FREE, AND THE EXISTING N+1 CASE CAUGHT IT (`DEF-INT-5587`).** Written
    with all five maps resolved for every page, this cost **10 statements for two
    accounts and 14 for four** — two extra PER ACCOUNT — which is 2,000 extra
    statements on a thousand-row page and 80,000 over a 40,000-account walk.
    `billing.open_balance.open_balances_for_accounts` says so in its own
    docstring: *"Billing's half is ONE query for the whole cohort; the seam is
    then asked per account"*, because it will not reach past payments' and
    customers' seams to batch what they have not published as a batch (B1). That
    is billing being right about the module boundary, and it makes the read
    unsuitable for a list.

    **So the LIST route does not carry it and `consumer-info` does.** That is not
    a workaround — it is where their document puts it, and it is the same
    division `remote_plan_id` already has by PO ruling. A partner looking up one
    account by number gets its balance; a partner walking 40,000 accounts gets
    four statements a page.

    ⚠ **THE RESIDUAL IS RECORDED RATHER THAN HIDDEN:** `consumer-info` accepts
    many `consumer_numbers`, so a partner naming a thousand still pays the
    per-account cost. It is bounded by the page and by a route nobody walks, and
    it is `DEF-INT-5587`'s second half.

    ⚠ **THIS FUNCTION IS THE N+1 GUARD AND IT IS WHY `as_record` HAS A REQUIRED
    KEYWORD.** `DEF-2723` is the same mistake one module along: a per-row read
    that is invisible on a demo tenant and is 40,000 statements on the largest
    utility this product models. A lane cannot write the slow version here by
    accident, because `as_record(account)` alone is a `TypeError`.
    """
    rows = list(accounts)
    facts: dict[str, Any] = {
        "addresses": address_map(rows),
        "contacts": contact_map(rows),
        # `DEF-INT-9796` — the accounts a COMPANY holds, by its legal name.
        # ONE more page-wide read (five a page, whatever the page holds).
        "companies": company_map(rows),
        # ── `CR-111-BRC04` · ONE more page-wide read, and still not one per row.
        # Four queries a page instead of three, whatever the page holds:
        # accounts · premises · contacts · mailing addresses.
        "billing_addresses": billing_address_map(rows),
    }
    if detail:
        facts["plans"] = plan_code_map(rows)
        facts["balances"] = balance_map(rows)
    return facts


def status_of(account: Any) -> dict[str, str]:
    """The account's status as `{code, label}`, from THE TENANT'S OWN LOOKUP.

    ⚠ **A LOOKUP AND NOT AN ENUM, WHICH IS WHY IT SHIPS INLINE.** `BR-CUS-055`
    made `account_statuses` tenant-extensible, so two utilities legitimately
    answer differently and a hardcoded vocabulary would be wrong on the first
    tenant that added *Legal hold*. `reference.account_statuses()` publishes
    the same rows off the same table with the same `str(name or code)` rule,
    and `test_the_status_label_is_the_reference_endpoints_own_word` asserts the
    two agree for every active status — so they cannot drift without something
    going red.

    ⚠ **IT IS READ FROM THE ACCOUNT'S OWN JOINED ROW RATHER THAN FROM A MAP
    BUILT OUT OF THE REFERENCE LIST**, and the difference is a real case: the
    reference endpoint filters `active=True`, and an account may still hold a
    status a clerk has since deactivated. Built from the list, that account's
    label would be missing. Read from the row, it is right — and because the
    PO ruled every coded field ships as `{code, label}` inline, a partner can
    resolve it even though it is not in the published list.

    ⚠ **THE BEHAVIOUR CLASS DOES NOT TRAVEL** — `billable`,
    `billable_base_only`, `non_billable` and `terminal` are how OUR billing
    keys off a tenant's label. Publishing them would invite a finance system to
    make billing decisions from them, which is the same line
    `reference.account_statuses` already draws.
    """
    status = getattr(account, "status", None)
    code = str(getattr(status, "code", "") or "")
    name = getattr(status, "name", None)
    return {"code": code, "label": str(name or code)}


def as_record(
    account: Any, *, facts: dict[str, Any], with_detail: bool = False
) -> dict[str, Any]:
    """One customer, in the fields that are ours to hand over.

    `facts` is REQUIRED and is `page_facts()`'s answer for the page this
    account is on — see that function for why it is not optional.

    The record is the account AS WE HOLD IT, in OUR words. Nothing here is
    translated into a partner's vocabulary: `BR-INT-054` and `CR-069` §20.4 put
    that in Runbooks, and the PO's ruling that struck the clerk mapping screen
    says why in one sentence — *"for a READ the partner maps at THEIR end"*.
    **What a partner's own field names are is `shapes.py`'s business**, and a
    shape may re-key this record on the way out; it may not add to it.

    ⚠ **`with_detail` IS THE DIFFERENCE BETWEEN `/accounts` AND
    `consumer-info`, AND IT IS A FIELD RATHER THAN A SECOND COMPOSER.** PO
    2026-09-17, asked in which APIs `remote_plan_id` is required: it is in
    `consumer-info` and in no other payload of their document. One
    implementation, two addresses — a second `as_consumer_record` would be two
    answers to *what is a customer* and the day they disagreed nothing would
    see it.
    """
    key = str(account.id)
    contact = (facts.get("contacts") or {}).get(key) or {}
    # ── `DEF-INT-9796` · PO ruling 2026-10-06 D3 (a) ──────────────────────
    # A COMPANY account is sent under the company's LEGAL NAME. The whole
    # legal name is `first_name` and `last_name` is null — `split_name`'s own
    # rule for a name that is not a person's — so `first + " " + last` still
    # reassembles `customer_name`, and no partner receives *"Grace"* /
    # *"Fellowship of Cedar Ford"*. `organization_name` says which records are
    # organisations; it is null for a person. `email` and `phone` stay the
    # contact's: the ruling moved the NAME, not how the partner reaches them.
    # A PERSON account is unchanged, byte for byte, apart from that null key.
    organization = (facts.get("companies") or {}).get(key)
    if organization:
        name, first, last = organization, organization, None
    else:
        name = contact.get("name")
        first, last = split_name(name)
    status = status_of(account)
    service_address = (facts.get("addresses") or {}).get(key)
    billing_address = (facts.get("billing_addresses") or {}).get(key)
    record: dict[str, Any] = {
        # B14 rule 31 / `seams/billing.as_record` — the NUMBER, never the uuid.
        # ⚠ **AND IT TRAVELS AS OUR TEXT, BY PO RULING 2026-09-17** — asked how
        # our ids travel when their samples are integers and ours are account
        # numbers: *"a) they store our text exactly as we send it"*. So there is
        # no integer to mint, no lookup table to keep and no second identity to
        # reconcile: `A-10432` goes out and `A-10432` comes back.
        "id": account.account_no,
        "consumer_no": account.account_no,
        "customer_name": name,
        # ⚠ **BOTH HALVES AND THE WHOLE, WHICH IS NOT REDUNDANCY.** We hold ONE
        # name column, so the split is a presentation of a fact we do not have
        # (`split_name`). Keeping `customer_name` beside the halves means a
        # partner that disagrees with our split has the original to work from,
        # and it is what makes the split LOSSLESS rather than lossy.
        "first_name": first,
        "last_name": last,
        # `DEF-INT-9796` — the legal name of a company account; null for a
        # person. Added 2026-10-06 and announced in the release notes.
        "organization_name": organization or None,
        "email": contact.get("email"),
        "phone": contact.get("phone"),
        # ⚠ **THERE IS NO `contact_number` HERE AND THAT IS THE SHAPE
        # MECHANISM EARNING ITS PLACE.** Their document calls this field
        # `contact_number`. That is a NAME for a fact we already serve, so it is
        # a rename and renaming is exactly what a shape is for
        # (`shapes.INVOICE_CLOUD`). Carrying both keys here would be one value
        # under two names in one payload, which is `DEF-014`, and it would put a
        # partner's vocabulary in the seam — the thing `BR-INT-054` and the PO's
        # *"for a READ the partner maps at THEIR end"* both forbid.
        "status": status,
        # The status as a WORD, for a partner that shows it to a person rather
        # than branching on it. It is `status["label"]` — the tenant's own
        # lookup — and not a second vocabulary (`BR-CUS-055`).
        "status_display": status["label"],
        # ── hard rule 8, both legs, in one place ──────────────────────────
        # ⚠ **THE SERVICE ADDRESS IS WALKED TO THE PREMISES AND IS NEVER A
        # COLUMN ON THIS ROW**; the billing address is the account's own
        # `kind='mailing'` row, falling back to the service address when there
        # is none. `kind='service'` is RETIRED and is asked for nowhere.
        # Serving both under one key rather than two top-level fields is what
        # lets a partner see that they are THE SAME address for most accounts,
        # which is the ordinary case and is information.
        "territory_data": {
            "service_address": service_address,
            "billing_address": billing_address or service_address,
        },
        # Kept at the top level as well, unchanged, because it is what
        # `/accounts` has served since wave 2 and a partner already reads it.
        "address": service_address,
    }
    if with_detail:
        # ⚠ **`consumer-info` ONLY** — both of these cost a statement per account
        # (see `page_facts`), and the list route may not. `remote_plan_id` is
        # also consumer-info-only by PO ruling 2026-09-17, asked in which APIs it
        # is required; `opening_balance` joins it because it cannot be batched.
        record["remote_plan_id"] = (facts.get("plans") or {}).get(key)
        record["opening_balance"] = (facts.get("balances") or {}).get(key)
    return record


def as_records(accounts: Any, *, with_detail: bool = False) -> list[dict[str, Any]]:
    """One page of customers, with every page-wide read resolved once.

    This is what the door calls. It exists so the N+1 is unrepresentable at the
    call site as well as inside the seam.
    """
    rows = list(accounts)
    facts = page_facts(rows, detail=with_detail)
    return [as_record(one, facts=facts, with_detail=with_detail) for one in rows]


__all__ = [
    "ADDRESS_KIND_MAILING",
    "CONTACT_ORDER",
    "ORDER_BY",
    "address_map",
    "balance_map",
    "billing_address_map",
    "company_map",
    "plan_code_map",
    "split_name",
    "as_record",
    "as_records",
    "collectable",
    "compose_address",
    "contact_map",
    "page_facts",
    "premises_id_for",
    "status_of",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-110-BRC04 phase 2 wave 2 (PO rulings of 2026-09-16, verbatim)
# generated: 2026-09-16 by the CR-110-BRC04 phase 2 lane B build lane
# checklist: A✔ B=n/a(no screen — this is a partner payload) C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_cr110_phase2_partner_customers.py
# exceptions: reads `metering.models.Premises` directly rather than through a
#   published plural selector — metering publishes the street line in bulk and
#   the locality only one row at a time, and composing from those two is a
#   query per account (see `_premises_model`). Recommended to metering as a
#   plural address read; not taken here while three lanes are live (law 11)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
