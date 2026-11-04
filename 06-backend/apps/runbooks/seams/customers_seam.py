# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4.
# Rules:    BR-RBS-039 (read through a seam this module owns, by name, in
#           process, under the tenant context) · CLAUDE.md hard rule 1
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  B2 Addendum r25 (this seam's row in the cross-module interface
#           register, added in the same commit as this file)
# ───────────────────────────────────────────────────────
"""operations → customers — accounts, contacts, flags and protections. READ ONLY.

Every Check that walks an account reads it here: the collections ladder needs a
balance and a tier, the pre-bill sweep needs an account's status, and the
medical-protection and dispute guards — which are ABSOLUTE skips evaluated
before any step and cannot be switched off (`BR-RBS-014`) — read their flags
through this file and nowhere else.

⚠ **AN ACCOUNT HAS NO ADDRESS AND THIS SEAM WILL NEVER SERVE ONE** (hard rule 8,
`BR-MET-1161`). An address is stored on `premises` and nowhere else; a runbook
that wants one WALKS TO THE PREMISES through `metering_seam`. The one thing
customers legitimately holds is `addresses` `kind='mailing'` — where the BILL
goes, which for a landlord is another building — and that is a different fact,
not a second copy.

⚠ **THIS FILE DECLARES THE PAIR AND HOLDS NO CALLABLE YET, ON PURPOSE.** Wave A
builds the module and its boundary; the first Check arrives in wave C and brings
the reads it actually needs. A selector written here now would be a function
nothing calls (hard-won law 2), and naming one in prose that no module exposes
would fail `G20` — which is a guard worth not blunting, since it is what caught
`DEF-075`. The selectors this module will need and customers does not offer
today are inventoried in `17-runbooks/13-selector-inventory.md`, and **customers
adds each of them**, never this file reaching past the seam.
"""

from apps.runbooks.boundary import SeamDeclaration

SEAM = SeamDeclaration(
    module="customers",
    pair="operations → customers",
    crosses="accounts, contacts, flags, protections",
)


# ── CR-075 wave C · the reads runbook 1 makes (US-RBS-001) ────────────────
#
# Added with `definitions/configuration_check.py` in the same commit. The one
# call below resolves `apps.customers.selectors.account_queryset`, which
# `customers` already publishes.


def account_type_counts() -> dict[str, int]:
    """How many consumer categories THIS tenant has, and how many it can pick.

    ⚠ **THIS SEAM COULD NOT EXIST BEFORE 2026-09-17.** `account_types` was a
    PLATFORM table with no `tenant_id` and no RLS, so there was no tenant-scoped
    read of it to make and runbook 1 step 2 declared it as a blind spot IN
    PROSE. The PO ruled *"utility can get their own account types"*
    (`BR-CUS-1079`) and the rows became the utility's, so the step has a real
    number to check and a real thing a tenant can get wrong: switching every
    category off, which leaves no account creatable at all.

    `selectable` is what a NEW record may pick — active and not legacy — and it
    is deliberately narrower than `total`, because `BR-CUS-094`'s legacy axis
    keeps a code lawful everywhere it already is while closing the picker. A
    check counting only rows would report a utility healthy with eight rows and
    nothing anybody could choose.
    """
    from apps.customers import models as customers_models
    from core import tenancy as core_tenancy

    rows = list(
        customers_models.AccountType.objects.filter(
            tenant_id=core_tenancy.current_tenant_id()
        ).values_list("active", "legacy")
    )
    return {
        "total": len(rows),
        "selectable": sum(1 for active, legacy in rows if active and not legacy),
    }


def account_anchors() -> list[dict[str, object]]:
    """Every account with the two things it can hang off — its unit and its
    premises — **no address of its own** (hard rule 8, `BR-MET-1161`), and
    whether the post has been coming back.

    ⚠ **THIS SEAM ANSWERS ONLY WHAT `customers` OWNS, AND STOPS.** Whether the
    unit and the premises it names still EXIST is metering's fact, read through
    `metering_seam.resolve_anchors`; joining the two is runbook 1 step 6's job.
    A version of this function that walked into metering to answer *is the chain
    unbroken* would be a cross-module read reimplemented inside this module,
    which is what `BR-RBS-039` forbids and what `G115` catches.

    ⚠ **`kind` TRAVELS BECAUSE THE TWO KINDS ARE ANCHORED DIFFERENTLY, AND A
    CHECK THAT IGNORED IT WOULD REPORT EVERY MASTER ACCOUNT AS BROKEN.**
    `BR-CUS-1010`: a Master Account is the OWNER'S account at an ADDRESS, so it
    names a premises and **no unit at all**, lawfully. A `regular` account must
    name a unit — `ck_accounts_regular_has_unit` refuses one that does not — and
    `ck_accounts_anchored` refuses any account naming neither. Both landed with
    `CR-056` W1 on 2026-09-01.
    """
    from apps.customers import selectors as customers_selectors

    return [
        {
            "id": str(row.id),
            "account_no": row.account_no,
            "kind": row.kind,
            "unit_id": str(row.unit_id) if row.unit_id else None,
            "premises_id": str(row.premises_id) if row.premises_id else None,
            # ⚠ **`bad_address` TRAVELS FROM 2026-09-07 AND IT IS `DEF-RBS-4348`.**
            # Runbook 8's *"Check the address works"* step asked whether this
            # dict was NON-EMPTY — i.e. whether the ACCOUNT exists — so on wave
            # `M`'s cycle **23 accounts flagged `bad_address` were each planned
            # a letter** and the `undeliverable` outcome was unreachable by any
            # input. The column is `customers`' own (`r12 #8`, written by
            # returned-mail handling under `BR-PAY-018` and by no edit), so
            # carrying it is reading the fact rather than a copy of it.
            "bad_address": bool(row.bad_address),
            # ⚠ ADDED BY `CR-075` WAVE S, AND IT TRAVELS RATHER THAN FILTERING.
            # `BR-TEN-056` fills a new tenant with deletable sample records, and
            # runbook 19 must be able to say *"0 items, and 71 of 72 accounts
            # here are sample records"* — a read that dropped them would make
            # those two answers identical (hard-won law 7). Runbook 1 ignores
            # the key, so nothing it reports moves.
            "is_sample": bool(getattr(row, "is_sample", False)),
        }
        for row in customers_selectors.account_queryset().order_by("account_no", "id")
    ]


# ── CR-075 wave L · the reads runbook 8's GUARDS make (US-RBS-010) ────────
#
# Added with `definitions/dunning.py` in the same commit. Both resolve
# functions `customers` already publishes — `apps.customers.selectors.
# account_queryset` and `apps.customers.disconnects.medical_hold_for` — and
# neither reimplements a rule that lives on the far side.


def sample_account_ids() -> frozenset[str]:
    """Every account tagged as SAMPLE data (`BR-TEN-057`).

    ⚠ **THIS IS `BR-RBS-014`'s WHOLE MECHANISM: *a sample record is never acted
    on by an Action*, in any tenant, at any time.** It is a GUARD rather than a
    check, so it is evaluated before any step and wins over everything below it
    (`BR-RBS-012`) — a demo account cannot be reasoned out of the exclusion by a
    later rule, which is the difference between a guard and a rule.

    `is_sample` lives on the OWNING row rather than in a central registry
    (`BR-TEN-057`), written only by this module's own service on the sample
    path, and `BR-TEN-061` deletes on that predicate and on nothing else. So
    reading the column is reading the fact rather than a copy of it.
    """
    from apps.customers import selectors as customers_selectors

    return frozenset(
        str(account_id)
        for account_id in customers_selectors.account_queryset()
        .filter(is_sample=True)
        .values_list("id", flat=True)
    )


def medical_hold(account_id, *, as_of) -> bool:
    """Is this account excluded from every collection step on `as_of`?

    `apps.customers.disconnects.medical_hold_for` — A15 via `BR-CUS-039`.

    ⚠ **THIS IS THE FUNCTION `apps/payments/outstandings.py` RECORDED AS
    MISSING, AND RUNBOOK 8'S GUARD IS ITS FIRST CALLER.** Its own docstring
    carries the note *"AND NOTHING CALLS IT YET (hard-won law 2 — built is not
    wired)"*; payments and notifications still take the hold as an argument
    because of that absence, and the ladder board this module reads takes it as
    an argument too — which is why the guard resolves it HERE and passes the set
    down, rather than payments inferring a clinical fact it has no business
    holding.

    ⚠ **ONE READ PER ACCOUNT, AND THE COST IS STATED RATHER THAN HIDDEN.**
    `medical_hold_for` answers for one account, so a ladder over 1,004 accounts
    makes 1,004 reads. Runbook 8's guard memoises the answer for the length of
    one run, so it is 1,004 and not 3,012; a batched form is `customers`' to
    publish and is not invented here, because a set-shaped copy of `in_force`
    would be a second statement of a rule whose plan half reads payments.

    `as_of` is an ARGUMENT and never a clock read (`BR-TEN-043`, gate `G6`): a
    certificate that expired yesterday must protect a run re-taken for last
    week.
    """
    from apps.customers import disconnects as customers_disconnects

    return bool(customers_disconnects.medical_hold_for(account_id, as_of=as_of))


# ── CR-075 wave F · the read runbook 23 makes (US-RBS-004) ────────────────


def account_facts(account_id) -> dict[str, object] | None:
    """Does this account exist for THIS tenant, and what does a clerk call it?

    Runbook 23's scope is one account a person picked, and `resolve()` needs two
    things before any step runs: whether the id is real, and a LABEL. B14 rule
    31 — *no database id is ever the visible value of a field* — so a
    `SubjectRef` with no label produces a result file whose Subject column is
    empty and a screen with nothing to name the account by.

    `None` for an id this tenant does not hold, which is the same answer as *"no
    such account"* by design: `account_or_404` refuses a cross-tenant id
    identically to an absent one (`HR-1`, hard rule 1), and this seam does not
    unpick that distinction — the run simply resolves an empty scope and the
    report says nothing was priced.

    ⚠ **NO ADDRESS IS READ OR CARRIED HERE.** Hard rule 8: an address lives on
    `premises` and every other entity walks to it. The account's premise LABEL
    travels for the same reason its number does — it is what a clerk reads —
    and it arrives from `account_row`, which already does the walking.
    """
    from apps.customers import selectors as customers_selectors
    from core import errors as core_errors

    try:
        account = customers_selectors.account_or_404(account_id)
    except core_errors.NotFoundError:
        return None
    row = customers_selectors.account_row(account)
    return {
        "account_no": row.get("account_no"),
        # The words a clerk uses for this account: the customer's name where
        # there is one, the account number otherwise. Never the id.
        "label": row.get("name") or row.get("account_no"),
        "unit_label": row.get("unit_label"),
        "premise": row.get("premise"),
        "status": row.get("status"),
        # ⚠ **ADDED BY `CR-075` WAVE S, AND ITS ABSENCE WAS A CHECK REPORTING A
        # CLEAN RESULT OVER SOMETHING IT NEVER LOOKED AT.** `RB-104` step 6 asks
        # whether the METER changed between two bills, and the meter is reached
        # through the unit. A first build read `unit_id` off this dict, got
        # `None` on every account, and reported *"not anchored to a unit"* for
        # all of them — true of nothing, and green in every test (hard-won law
        # 7). It is a HANDLE for a seam call and never a visible value (B14 rule
        # 31); `unit_label` is what a clerk reads.
        "unit_id": str(account.unit_id) if account.unit_id else None,
    }


# ── CR-075 wave Q′ · the read runbook 22 makes (US-RBS-034) ────────────────


def contact_channels_for(account_ids) -> dict[str, dict[str, object]]:
    """What each account can be reached ON — email → text → post → none.

    `apps.customers.selectors.contact_channels_for`, one read for the whole
    morning's feedback. `RB-122` step 4's ladder in that order, and the order is
    fixed by the owning module rather than composed here, so a fall-back policy
    cannot be re-ordered by a caller.

    ⚠ **PRESENT MEANS *ON FILE*, NEVER *WORKING*.** Nothing in `customers`
    records that a channel stopped working or when — which is the reason the
    `suppress_channel` port binds no writer (`DEF-RBS-4331`) and the reason this
    runbook can plan a fall-back and cannot perform one.
    """
    from apps.customers import selectors as customers_selectors

    return dict(customers_selectors.contact_channels_for(list(account_ids or [])))


# ── CR-075 wave S · the reads runbooks 16 and 19 make ─────────────────────
#
# Both resolve selectors `customers` publishes — `duplicate_customer_groups`
# (`13-selector-inventory.md` **S-9**) and `account_types_for` — added by the
# owning module in the same commit, never reached past this seam.


def duplicate_customer_groups() -> dict[str, object]:
    """Customers that look like one person — same phone, tax id or email.

    `RB-119` step 1. ⚠ **`RB-119`'s own stated absence governs what this can
    be**: *"phone numbers are encrypted with a blind index, so 'same phone' here
    means a blind-index match. Fuzzy phone matching is not possible on an
    encrypted column."* So it is EQUALITY on a token, never similarity, and a
    utility with two spellings of one phone number gets two customers here and
    always will.

    ⚠ **NO MATCHED VALUE CROSSES THIS SEAM** — not the phone, not the tax id,
    not the email. `matched_on` names WHICH of the three it was, which is what a
    clerk needs to decide, and the sensitive half stays in `customers`.
    """
    from apps.customers import selectors as customers_selectors

    return dict(customers_selectors.duplicate_customer_groups())


def account_types_for(account_ids) -> dict[str, dict[str, object]]:
    """`{account_id: {type_code, type_name}}` — Residential · Irrigation · …

    `RB-116`'s *Group by: account type*. One read for a whole cycle's bills;
    asking per bill would be 1,410 queries for one grouping.
    """
    from apps.customers import selectors as customers_selectors

    return dict(customers_selectors.account_types_for(list(account_ids or [])))


# ── CR-075 wave T · the two reads a tenant-resolved domain needs ──────────
#
# `BR-RBS-042` clause 2 — *every domain is tenant-resolved, never hardcoded*.
# Both resolve selectors `customers` already publishes; nothing new was asked
# of the owning module for this wave.


def account_domain_page(*, q: str = "", page: int = 1, per: int = 50) -> dict[str, object]:
    """One PAGE of *the accounts this tenant has*, sliced in SQL — `NFR-3`.

    ⚠ **THIS IS THE DOMAIN THAT SCALES WITH THE UTILITY, AND IT IS THE WHOLE
    REASON THE DOMAIN ENDPOINT PAGES.** `service` is bounded by the platform
    catalogue at eleven; `account` is **40,000 at the top of T5**, and CLAUDE.md
    names four shipped lists that are unpaginated *"on purpose"* because a
    utility under 3,000 connections could carry it — correct at T7 and **13×
    short of T5** (`DEF-PAY-4221`). A picker that read every account to draw a
    dropdown would be the fifth, and it would be written by a lane that had just
    read the paragraph forbidding it.

    So: `account_queryset()` is customers' own tenant-scoped queryset, the
    filter and the ORDER are applied to it, `.count()` is one `COUNT(*)`, and
    exactly one page of rows is materialised. **Nothing here calls `list()` on
    an unsliced queryset** and nothing sorts in Python.

    ⚠ **THE ORDER IS TOTAL** (`account_no`, then `id`). A slice of a
    non-totally-ordered queryset is a different set of rows each time it is
    asked, which reads on screen as a list that shuffles between page 1 and
    page 2.

    ⚠ **`label` IS THE ACCOUNT NUMBER, NEVER THE ID** (B14 rule 31, and the
    ladder board's `_account_no` takes the same care). The `value` IS the id,
    because that is what a stored parameter must point at and what the run
    resolves — a rule about what a screen RENDERS, not about what a payload
    carries.
    """
    from apps.customers import selectors as customers_selectors

    queryset = customers_selectors.account_queryset()
    term = str(q or "").strip()
    if term:
        queryset = queryset.filter(account_no__icontains=term)
    queryset = queryset.order_by("account_no", "id")
    total = queryset.count()
    size = max(1, int(per))
    start = max(0, (max(1, int(page)) - 1) * size)
    rows = [
        {"value": str(row.id), "label": str(row.account_no or "")}
        for row in queryset[start : start + size].only("id", "account_no")
    ]
    return {"rows": rows, "total": total}


def service_codes_for_account_ids(account_ids) -> dict[str, list[str]]:
    """`{account_id: [service codes]}` — which services each account takes.

    `apps.customers.selectors.service_codes_for_accounts` is customers' own
    read and takes ACCOUNT ROWS; this resolves the ids through customers'
    published queryset first, so no model of another module is imported here
    (`BR-RBS-039`, `G115`).

    ⚠ **ONE CALL FOR THE WHOLE PINNED SET.** The owning selector's docstring is
    explicit that it exists to be *"a constant number of queries for a whole
    page"* — `DEF-2723` cost six statements per row before it did. A runbook
    asking per account would put that back, one module along.
    """
    from apps.customers import selectors as customers_selectors

    ids = [str(one) for one in (account_ids or []) if one]
    if not ids:
        return {}
    rows = list(customers_selectors.account_queryset().filter(id__in=ids))
    return {
        str(key): [str(code) for code in codes]
        for key, codes in customers_selectors.service_codes_for_accounts(rows).items()
    }


def accounts_opted_in_to_text(account_ids) -> dict[str, bool]:
    """Which of these accounts have asked to be texted — `RB-119` step 5.

    `apps.customers.selectors.text_opt_in_for`. ⚠ **AN ELECTION, NOT A CONSENT
    RECORD**: `accounts.sms_reminders` carries no date, no capture channel and
    no withdrawal trail, so *"1,350 reachable by text"* means *a mobile is on
    file AND the account has asked for texts* and never *we can prove they
    agreed on the 4th*. The runbook says *not opted in* for that reason.
    """
    from apps.customers import selectors as customers_selectors

    return dict(customers_selectors.text_opt_in_for(list(account_ids or [])))

def account_labels(account_ids) -> dict[str, str]:
    """`{account_id: account_no}` for the ids a person has already CHOSEN.

    ⚠ **B14 RULE 31 IS WHY THIS EXISTS AT ALL.** A saved `ref:object` value is
    an account id, and a Scope row that printed it would put a uuid on a clerk's
    screen — *"no database id is ever the visible value of a field"*, and the
    account header lost a whole line to the same class of miss (`DEF-CUS-3653`).
    So the id is what is stored and the NUMBER is what is drawn.

    Bounded by the CHOICE rather than by the estate: it resolves the handful of
    ids a tenant picked, never the domain (`account_domain_page` pages that).
    """
    from apps.customers import selectors as customers_selectors

    ids = [str(one) for one in (account_ids or []) if one]
    if not ids:
        return {}
    # ⚠ **`values_list`, NOT `.only(...)` — `DEF-RBS-4397`, AND IT RAISED ON
    # EVERY CALL FROM THE COMMIT THAT ADDED IT UNTIL 2026-09-07.**
    # `account_queryset()` carries `select_related("status")`, and Django
    # refuses that combined with a deferral by name: *"Field Account.status
    # cannot be both deferred and traversed using select_related at the same
    # time."* It never showed on the unit tier because the empty-list path
    # returns `{}` before touching the database, and the one caller —
    # `domains.labels("account", …)`, which turns a saved `ref:object` id into
    # the account NUMBER a setup screen draws (B14 rule 31) — was never run
    # against real rows. Asking for two COLUMNS instead of two fields of a model
    # cannot collide with anything the owning module puts on its queryset.
    return {
        str(account_id): str(account_no or "")
        for account_id, account_no in customers_selectors.account_queryset()
        .filter(id__in=ids)
        .values_list("id", "account_no")
    }


# ── CR-075 wave R′ · the two reads runbook 15 makes (US-RBS-027) ──────────
#
# ⚠ **BOTH OF THESE ARE `customers`' AND NEITHER IS `payments`', WHICH IS NOT
# WHERE A READER WOULD LOOK FIRST.** A deposit lives on `accounts` (B2 r9 #5)
# and its interest is `BR-CUS-057` — so although runbook 15 is a *Collections*
# runbook whose ports are all payments', the figure a regulator asks about is
# read across this seam.


def deposit_interest_accrued(account_id, *, as_of):
    """❄️ **`GT-61`'s figure for one account — FROZEN, and READ, never computed.**

    `apps.customers.selectors.deposit_interest_accrued`, which is
    `apps/customers/deposit_interest.py`'s published name. The signed figure is
    **$150 @ 2.0%, 89 months → $22.25** (B5, finance-signed 2026-08-08) and that
    module asserts it directly.

    ⚠ **A RUNBOOK MUST NEVER RE-DERIVE THIS.** Deposit interest is money math on
    a 🔒 path: B4/B5 are frozen, a change needs a finance re-sign through
    HUMAN-GUIDE §6, and a second implementation living in a runbook would be a
    copy of a signed rule sitting where finance's reviewers never read it. This
    seam exists so runbook 15 can put the number on a screen without owning it.

    ⚠ **`None` IS *WE COULD NOT FIND OUT* AND ZERO IS *THIS UTILITY PAYS NO
    INTEREST*.** The owning module is explicit that the two are opposite
    answers, and `RB-115`'s result must not print one as the other: `None`
    arrives when no day was stated, when the deposit has no receipt date, or
    when the tenant's rate could not be read at all.

    `as_of` is an argument and never a clock read (`BR-TEN-043`, gate `G6`): a
    deposit review re-taken for the 1st must give the 1st's figure.
    """
    from apps.customers import selectors as customers_selectors

    return customers_selectors.deposit_interest_accrued(account_id, as_of)


def deposit_interest_rate_annual():
    """This utility's rate, as a PERCENTAGE — or `None` where it cannot be read.

    `apps.customers.deposit_interest.annual_rate_percent`, which reads the S66
    Billing-defaults page through tenancy's own selector. `RBR-03`: policy lives
    in Settings and a card never carries a second copy — `RB-115`'s *"From
    Settings · 2.0% simple · state rule"* is the CARD's illustration and not a
    figure any deployment holds, so a runbook falling back to it would pay
    interest out of a number nobody chose.

    Read beside the accrual and not instead of it: the FIGURE answers *how much*,
    and the rate answers *has anybody set this up* — which is the sentence a
    clerk needs when every accrual comes back zero.

    ⚠ **PERCENTAGES ARE STORED TO SIX DECIMALS AND DISPLAYED TO TWO** (hard rule
    2). A `Decimal` crosses this seam, never a float.
    """
    from apps.customers import deposit_interest

    return deposit_interest.annual_rate_percent()


# ── CR-075 wave R′ · the reads runbook 27 starts from (US-RBS-037) ────────
#
# Both resolve a selector `customers` publishes:
# `apps.customers.selectors.closing_accounts` (added in the same commit as this
# file) and `apps.customers.selectors.mailing_address_for_account` (already
# published, for billing's print hand-over).


def closing_accounts(*, as_of, window_days: int = 14) -> list[dict[str, object]]:
    """Every account closing inside the window, plus every one already closed.

    `apps.customers.selectors.closing_accounts` — `RB-127`'s scope in one query,
    and the window reaches BACKWARDS as well as forwards: *any closed account
    with no final bill, however old* is the half that catches the move-out
    somebody processed in March and never billed.

    ⚠ **NO ADDRESS COMES BACK ON THE ACCOUNT** (CLAUDE.md hard rule 8): a
    `premises_id` does, and the caller walks to the one address home. The
    FORWARDING address is a different fact and comes from
    `mailing_address_for_account` below.

    ⚠ `deposit_held` crosses as a STRING at four decimals (hard rule 2), never
    a float and never pre-rounded.
    """
    from apps.customers import selectors as customers_selectors

    return list(customers_selectors.closing_accounts(as_of=as_of, window_days=window_days))


def mailing_address_for_account(account_id) -> dict[str, object] | None:
    """Where the BILL goes — hard rule 8's FIRST stated exception, and a READ.

    `apps.customers.selectors.mailing_address_for_account`. An address lives on
    `premises` and nowhere else; `customers.addresses` at `kind='mailing'` is
    not a second copy of it but a different fact — for a landlord it is another
    building entirely, and for somebody who has just moved out it is the only
    address a final bill can reach.

    ⚠ **`kind='service'` IS RETIRED AND NOTHING HERE ASKS FOR IT.** The selector
    reads the mailing kind only and returns `missing` naming the parts it cannot
    supply, so *"the forwarding address is not captured"* is a fact this runbook
    REPORTS rather than a null it swallows — `DEF-CUS-3653` is what an absence
    costs when nothing names it.

    ⚠ **IT RETURNS DISCRETE COLUMNS AND NEVER A COMPOSED STRING**
    (`BR-NOT-029` (a)). Splitting or assembling an address is guessing, and a
    guessed address is mail delivered to the wrong house.
    """
    from apps.customers import selectors as customers_selectors

    return customers_selectors.mailing_address_for_account(account_id)


def accounts_for_units(unit_ids) -> dict[str, dict[str, object]]:
    """The account occupying each unit — ONE query for a whole batch of meters.

    `apps.customers.selectors.accounts_for_units`. The leak alert walks
    meter → service point → unit on metering's side of the seam and arrives
    here with 1,840 unit ids; a per-meter read would be 1,840 round trips at
    07:30 every morning, which is `service_point_graph`'s own stated cost and
    the one this runbook must not repeat.

    ⚠ **A UNIT WITH NO ACCOUNT IS ABSENT FROM THE MAPPING, NOT PRESENT WITH
    `None`.** A meter on an empty unit is a real and ordinary state — the
    property is between tenancies — and a runbook that told nobody about a leak
    there must say so as *nobody to tell* rather than silently dropping the row.
    """
    from apps.customers import selectors as customers_selectors

    return dict(customers_selectors.accounts_for_units([str(one) for one in (unit_ids or [])]))


def move_out_settlement(account_id, *, as_of, final_bill=None) -> dict[str, object]:
    """What the deposit settles and what — if anything — comes back. A **READ**.

    `apps.customers.move_out_settlement.settlement_for`, which is `S20` step 3's
    own read model and the arithmetic a clerk already sees on the move-out
    wizard. **This runbook does not re-derive it**: a second implementation of a
    money decision is two answers that eventually disagree about one customer,
    and `BR-CUS-025`'s five landings are 🔒 human-owned.

    ⚠ **IT WRITES NO AUDIT ROW, BECAUSE NOTHING MOVED** — its own docstring says
    so. The money ACTS are `raise_refund` and `post_credit`, each a named port,
    and hard rule 7's row is written where the action is.

    ⚠ **EVERY FIGURE COMES BACK AS A `{stored, display}` PAIR OF STRINGS**
    (hard rule 2: money stored to 4 decimals, displayed at 2, never a float).
    A runbook that re-rounded one of these would be a second rounding on a money
    path, which is what B4's *round only at finalisation* forbids.

    ⚠ **`final_bill` IS STATED BY THE CALLER AND IS NOT INVENTED HERE.** Billing
    publishes no per-account final-bill total, so a settlement run without one
    reports the gap `final_bill_not_stated` and **states no landing at all**
    rather than settling a deposit against a bill nobody read. That is the
    fail-closed half of `DEF-127`, on an account nobody will look at again.

    ⚠ **`as_of` IS THE CALLER'S TOO** (`BR-TEN-043`, gate `G6`): `BR-CUS-057`'s
    deposit interest accrues to a DAY, and a money path may not read a clock.
    """
    from apps.customers import move_out_settlement as customers_move_out

    return dict(
        customers_move_out.settlement_for(
            None, account_id, final_bill=final_bill, as_of=as_of
        )
    )


# ── CR-075 wave S · the two reads runbook 18 makes ────────────────────────

def pending_move_ins() -> dict[str, list[dict[str, object]]]:
    """`{premises_id: the open applications to start service there}`.

    `RB-118` step 4: *"Check for a move-in already pending — someone applied;
    this is not a finding."* A premises with an application in flight is already
    somebody's job, and a runbook that listed it would put the same work on two
    desks.

    ⚠ **OPEN MEANS *NOT TERMINAL*, WHICH IS `ServiceRequest`'s OWN WORD.**
    `TERMINAL_STATES` is `completed · refused · withdrawn · closed`; everything
    before that is a person still working on it. Reading the list the other way
    round — naming the four live states — would go stale the day a fifth is
    added, and the request module owns that vocabulary.

    ⚠ **AND IT IS KEYED ON THE RESOLVED PREMISES, NOT ON THE ADDRESS AS
    TYPED.** `BR-CUS-070` keeps `address_as_given` verbatim and never overwrites
    it; the resolved ids sit beside it, and only they can be joined to anything.
    An application nobody has resolved to a premises yet cannot be matched here
    and is counted rather than guessed at.
    """
    from apps.customers import models as customers_models

    rows = customers_models.ServiceRequest.objects.filter(
        outcome__in=(
            customers_models.ServiceRequest.OUTCOME_MOVE_IN,
            customers_models.ServiceRequest.OUTCOME_NEW_CONNECTION,
        )
    ).exclude(state__in=customers_models.ServiceRequest.TERMINAL_STATES)
    out: dict[str, list[dict[str, object]]] = {}
    unresolved = 0
    for row in rows:
        if not row.resolved_premises_id:
            unresolved += 1
            continue
        out.setdefault(str(row.resolved_premises_id), []).append(
            {
                # B14 rule 31 — the request's NUMBER, never its id.
                "request_no": row.request_no,
                "state": row.state,
                "outcome": row.outcome,
                "unit_id": str(row.resolved_unit_id) if row.resolved_unit_id else None,
            }
        )
    # Hard-won law 7 — the number beside the blind spot, carried under a key no
    # premises id can collide with.
    out["_applications_not_resolved_to_a_premises"] = [{"count": unresolved}]
    return out


def last_closed_account_for_units(unit_ids) -> dict[str, dict[str, object]]:
    """`{unit_id: who was here last}` — the unit's most recent FINISHED tenancy.

    `apps.customers.selectors.last_closed_account_for_unit`, asked for a list.
    `RB-118` needs it twice: to say WHO was last billed at a premises now using
    water, and to date the comparison against what they used.

    ⚠ **"FINISHED" IS THE TERMINAL BEHAVIOUR CLASS WITH A `closed_at` ON IT**,
    which is `customers`' own definition — a terminal account with no date is
    SKIPPED there rather than treated as *closed on some unknown day*, and this
    seam does not unpick that.

    ⚠ **ONE READ PER UNIT, AND THE COST IS STATED.** `customers` publishes the
    single-unit form only, so an estate of 2,862 premises is 2,862 reads. A bulk
    form is `customers`' to publish (`13-selector-inventory.md` §4's own last
    bullet names this class of gap) and is not assembled here out of a queryset
    this module does not own.
    """
    from apps.customers import selectors as customers_selectors

    out: dict[str, dict[str, object]] = {}
    for unit_id in [one for one in (unit_ids or []) if one]:
        account = customers_selectors.last_closed_account_for_unit(unit_id)
        if account is None:
            continue
        row = customers_selectors.account_row(account)
        out[str(unit_id)] = {
            "id": str(account.id),
            "account_no": row.get("account_no"),
            # B14 rule 31 — the customer's name, or the number. Never the id.
            "label": row.get("name") or row.get("account_no"),
            "closed_on": account.closed_at.date().isoformat() if account.closed_at else None,
        }
    return out


# ── CR-075 wave S · the two reads runbook 12 makes (US-RBS-024) ───────────
#
# Added with `definitions/disconnect_eligibility.py` in the same commit. Both
# resolve `apps.customers.runbook_reads`, which `customers` publishes in that
# same commit — the third kind of module `apps/payments/runbook_reads.py`
# already is, imported BY NAME the way `payments_seam` imports
# `collections_read` (`13-selector-inventory.md` W-1's own resolution).


def final_notice_board(*, as_of, tier: str | None = None) -> dict[str, object]:
    """Every open case at the LAST tier, with the certified letter's own record.

    `apps.customers.runbook_reads.final_notice_board`. `RB-112`'s scope row —
    **Last tier · certified letter sent** — and its step 2 in one read.

    ⚠ **IT ANSWERS *WAS IT SERVED*, WHICH IS NOT *WAS IT DELIVERED*, AND THE
    DIFFERENCE IS THE WHOLE OF `BR-RBS-032`.** `13-selector-inventory.md` W-3
    calls this *"the one that could ship wrong"*: a disconnect list built from
    *queued* would put people on it whose letter came back. Nothing in this
    product can say a letter was DELIVERED — `delivered` and `bounced` are
    provider facts and no adapter exists on any channel, print included — so
    what governs is `BR-CUS-100`'s proof of service, **a record a person
    enters** with the channel, the reference and the date it was signed for.
    That is also the fact `assert_service_proved` already gates a real cut on,
    so the list a supervisor signs and the cut the product would refuse cannot
    disagree.

    `delivery_reported` rides on the answer as `False` with its reason, so the
    runbook prints the blind spot with a number beside it rather than a clean
    tick over channels nobody is listening to (hard-won law 7).

    `as_of` is an ARGUMENT and never a clock read (`BR-TEN-043`, gate `G6`).
    """
    from apps.customers import runbook_reads as customers_runbook_reads

    return dict(customers_runbook_reads.final_notice_board(as_of=as_of, tier=tier))


def protection_board(account_ids, *, as_of) -> dict[str, object]:
    """`B18` §5.8.4 step 2 for a whole list — *medical · plan · moratorium ·
    dispute, each pass or fail with its reason*.

    `apps.customers.runbook_reads.protection_board`, which is
    `disconnects.protection_check` called once per account inside the owning
    module. ⚠ **THE CALL IS BATCHED AND THE RULE IS NOT** — `medical_hold`
    above already states why a set-shaped copy of `in_force` would be a second
    statement of a rule whose plan half reads payments.

    ⚠ **THE FOURTH ROW IS `unavailable`, NEVER `pass`.** `protection_check`'s
    own words: nothing in this repository stores a disputed AMOUNT, so *"a green
    clearance derived from a table that does not exist would authorise a cut."*
    The count of accounts whose dispute could not be checked travels beside the
    findings — `RB-112` prints it, because the most expensive error a utility
    makes is a wrongful disconnect and this is the check it cannot make.

    ⚠ **`RB-112` RE-CHECKS ON THE MORNING RATHER THAN CARRYING THE LETTER'S
    ANSWER FORWARD**, which is why `as_of` is TODAY here and the letter's date
    is only used to window the payment search. A protection recorded after the
    certified letter went out is exactly the row that would have been wrong.
    """
    from apps.customers import runbook_reads as customers_runbook_reads

    return dict(customers_runbook_reads.protection_board(account_ids, as_of=as_of))


def account_names(account_ids) -> dict[str, str]:
    """`{account_id: the words a clerk uses}` — the customer's NAME, or the number.

    `apps.customers.selectors.primary_contact_names_for`, which is the batched
    read `account_row` itself uses — so the name on a runbook's table and the
    name on the accounts screen cannot come out different.

    ⚠ **THIS IS NOT `account_labels` ABOVE, AND THE DIFFERENCE MATTERS ON A
    TABLE.** That one answers the account NUMBER for a `ref:object` a person
    chose, which is what a Scope row needs. `RB-116`'s biggest-mover table draws
    *Marsh Farms* and *Alvarez, M.* — a board reads a name — and `RB-112`'s
    field list is carried by a crew who need to know whose door it is. Both are
    B14 rule 31 answers; neither is an id.

    ONE query for a whole cycle. Asking per bill would be 1,410 reads for a
    column of names.
    """
    from apps.customers import selectors as customers_selectors

    ids = [str(one) for one in (account_ids or []) if one]
    if not ids:
        return {}
    names = customers_selectors.primary_contact_names_for(ids)
    numbers = account_labels(ids)
    return {one: str(names.get(one) or numbers.get(one) or "") for one in ids}
