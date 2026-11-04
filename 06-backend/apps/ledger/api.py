# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-007 (GET /finance/revenue-ar — S36's KPI strip, revenue by
#           service, cash, adjustments and the tie-out figure) · US-LED-008
#           (GET /ledger/trial-balance — S56's table and its balanced footer) ·
#           US-LED-013 (GET /ledger/journal-entries — the S56 journal list and
#           its BR-LED-012 capability row) · US-LED-014 (GET /finance/taxes —
#           S41's dual-basis remittance table)
#           Screens: S36 · S41 · S56
# Rules:    BR-LED-016 (the S36 strip is dimension-derived) · BR-LED-009 (trial
#           balance: period filter, balanced footer) · BR-LED-012 (the journal
#           list carries the full IS-5 capability row) · BR-LED-013 (remittance
#           per authority: billed · collected · remitted · outstanding) ·
#           BR-LED-002 (BOTH bases always computed) · BR-LED-007 (tie-out; any
#           drift is a red flag, never a silent fix) · BR-LED-003 (a posted
#           entry is immutable — this surface serves no write verb at all) ·
#           BR-REP-001 (every money group labels its date basis) · BR-REP-002
#           (read-models over journal-line dimensions, never a side-maintained
#           number) · BR-REP-006 (filters enumerate LIVE vocabularies) ·
#           BR-REP-008 (the FULL source vocabulary) · BR-SHL-011 (list grammar
#           q/sort/dir/page/per/f.<name>) · BR-SHL-025 / BR-IDN-009
#           (server-enforced RBAC) · BR-TEN-003 / HR-1 (cross-tenant reads as
#           absent) · BR-TEN-022 (periods are COMPUTED from fiscal settings) ·
#           BR-TEN-042 (the tenant's currency) · BR-TEN-043 (event time is an
#           input — there is no clock in this file) · CLAUDE.md rule 1 (tenant
#           scoping) · rule 2 (money on the wire is a decimal string + CHAR(3))
#           · rule 5 (only the posting service writes; this file writes NOTHING)
# Tests:    06-backend/tests/test_us_led_ledger_api.py
# Impacts:  config/urls.py inclusion (`urlpatterns` exported here) ·
#           apps/ledger/wire.py (the shared serializer) ·
#           06-backend/openapi/schema.json (the committed contract snapshot
#           moves with any endpoint added here — BE-11 TC05) · 07-frontend
#           features/ledger + features/reports — S36 shipped 2026-08-11 and
#           S41/S56 on 2026-08-15 (DEF-112); every route below now has a caller,
#           and `07-frontend/src/api/endpoints.ts` is the one place they are
#           spelled
# ───────────────────────────────────────────────────────
"""ledger API endpoints per A11 as amended by 11b §1 + §2.10 (bodies in §2.10b).

THIN by law (B8 / LAW 0): parse the params → call ONE read model → serialize.
There is no ORM here (G6 greps every api.py for a model manager), no money
arithmetic, no clock, and every refusal leaves this file as a `core.errors`
catalog exception (G9).

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS TODAY AND NOT YESTERDAY
════════════════════════════════════════════════════════════════════════════
`apps/ledger/reporting.py` is 1,500 lines of complete, tested, G7-guarded read
model behind FIVE finance screens, and until this commit **no human being could
reach one figure of it.** This file was a one-line docstring and `config/urls.py`
named no ledger include, so `GET /ledger/trial-balance` — the one report an
auditor asks for first — answered 404.

That is hard-won law 2 for the third time in this repository, and it is the
same defect, in the same shape, as the two the root URLconf already carries
comments about: billing shipped S30's list and detail against a 404, and the
payments WRITE PATH landed complete while nobody could record a payment. The
test that keeps it fixed is not a shape test — it resolves every path below
through the REAL root URLconf and then calls it over real HTTP, because an
`api.py` exporting `urlpatterns` is not an endpoint until something includes it.

════════════════════════════════════════════════════════════════════════════
THE FOUR ROWS THIS SLICE SERVES
════════════════════════════════════════════════════════════════════════════
    GET /finance/revenue-ar      US-LED-007   S36   11b §2.10, verbatim
    GET /ledger/trial-balance    US-LED-008   S56   11b §2.10, verbatim
    GET /ledger/journal-entries  US-LED-013   S56   11b §2.10, verbatim
    GET /finance/taxes           US-LED-014   S41   11b §1 ("OK", amended:
                                                     dual-basis always)

S59 and S60 are NOT here. They are served at `GET /reports/{key}` from
`apps/reports/api.py` — 11b §1 line 32 puts them on that path and
04-docs/05-modules/12-reports/01-overview.md settles the ownership split
("**ledger owns** the TB/account-ledger/by-premises/remittance STORIES …
**reports owns** the report CENTER"). The read models they call are still
`apps.ledger.reporting`'s; only the viewer route belongs to the other module.

════════════════════════════════════════════════════════════════════════════
NOT SERVED — each for a stated reason, and NONE of them stubbed
════════════════════════════════════════════════════════════════════════════
A route that answers 501 is a promise, so nothing below is mounted empty.

  · **`GET /ledger/journal-entries/{id}` — 11b §2.10 NAMES IT AND IT IS NOT
    SERVED.** The row's own requirement is *"lines expand to dimensions"*, and
    THERE IS NO READ MODEL FOR IT: `apps/ledger/reporting.py` publishes
    `journal_entry_list` (entry-level rows with Σ debit/credit) and nothing
    that returns one entry's LINES with their service / account / premises /
    source / authority dimensions. `reporting.py` and `selectors.py` are both
    on the G7 human-owned list and are not this lane's to extend, and an
    api.py may not reach the ORM itself (G6). The three dishonest ways to
    close the gap were all available and all refused: serving the LIST row
    filtered to one id (a "detail" with no lines, which is the column the
    screen opens the detail FOR), writing a second lines-read in an unguarded
    module (two derivations of what an entry contains — the defect
    `reporting.py` exists to prevent, and outside G7 besides), or stubbing a
    501. **REPORTED, with the read named:**
    `apps.ledger.reporting.journal_entry_detail(entry_id) -> dict` returning
    the entry plus its lines with every dimension column and the same
    `unavailable` channel the list carries.
  · `GET /ledger/accounts` · `GET /ledger/gl-mappings` · `PUT /ledger/gl-mappings`
    (11b §2.10) — the chart and its maps are US-LED-005/US-LED-006's, a
    different epic (EP-LED-02) with a write verb in it. `apps/ledger/selectors`
    resolves a designation to an account; it publishes no chart LIST.
  · every WRITE on §2.10 — `POST/PATCH/DELETE /ledger/journal-entries`,
    `.../post`, `.../reverse` (S57, EP-LED-04), `POST /finance/periods/{p}/close`
    (US-LED-015), `POST /finance/taxes/remittances` (US-LED-014's write half).
    This lane is the READ API. Two of them are additionally blocked on
    **OQ-175**: BR-LED-003 makes reverse+repost a *Finance/Owner* action and
    this product's implemented role vocabulary is `system_admin` /
    `billing_clerk` / `executive`, which contains neither word. Mapping three
    roles onto two decides who may correct the books, so it is raised, not
    chosen. **It does not block the reads below** — A4's matrix gives
    Staff/Clerk `R` on Finance and `R/run` on Reports, and Executive full on
    both, so `AnyTenantRole` is the correct gate for a GET and no mapping is
    needed to state it.
  · `POST /reports/{key}/export` and the IS-11 download half of every story
    here (BR-REP-018) — the export lane is sequenced behind the job runner
    (PO 2026-08-09 decision-log ruling), and there is no job runner on this
    deployment (TD-17).

════════════════════════════════════════════════════════════════════════════
NO WRITE VERB EXISTS ON ANY PATH IN THIS FILE
════════════════════════════════════════════════════════════════════════════
Hard rule 4 / BR-LED-003: a posted journal entry is immutable forever and the
only "edit" is reverse + repost, which writes two NEW entries through the
posting service. Every route below is `GET` only, so a forged POST, PUT, PATCH
or DELETE is refused by the ROUTER with a 405 before any view runs.

`urlpatterns` is exported for inclusion by config/urls.py.
"""

from datetime import date
from typing import Any
from uuid import UUID

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.ledger import reporting, wire
from apps.tenancy import selectors as tenancy_selectors
from core import errors  # noqa: F401 — the catalog this file's refusals come from (G9)
from core.pagination import parse_list_params, prepaged
from core.permissions import AnyTenantRole
from core.tenancy import require_tenant


def _tenant_currency() -> str | None:
    """The tenant's declared CHAR(3), through tenancy's OWN published read.

    **THE FALLBACK, not the answer — see `_currency_of` below.** This is the
    tenant's DECLARED code (BR-TEN-042), read through
    `apps.tenancy.selectors.regional_settings()` rather than by reaching into
    `apps.tenancy.models`, which B1 forbids and G6 greps for.

    Kept because a report over an EMPTY window has no derived code to publish —
    a new tenant's first month is a real request and the honest label for its
    0.00 is the currency it says it bills in. Every window that posted anything
    labels itself from the books instead.
    """
    return tenancy_selectors.regional_settings().get("currency")


def _currency_of(result: dict[str, Any]) -> str | None:
    """The code a result's figures ACTUALLY ARE — from the books, then the tenant.

    **DEF-081, the constructive half.** Until 2026-08-15 this module labelled
    every figure with `_tenant_currency()` and this docstring said so in as many
    words: *"It is a LABEL and not a derivation … a tenant whose books hold two
    currencies would have them summed by the read model without complaint.
    Nothing in this lane can see that."* Both halves have now moved:

      * `apps/ledger/reporting.py` REFUSES a Σ over lines carrying more than one
        currency (`MixedCurrencyBook`, catalog `BIZ-STATE` → 409), so no mixed
        total can reach this layer to be labelled at all; and
      * every result it returns now publishes `currency`, DERIVED from the
        entries it summed, which is what this reads.

    The distinction is not academic. A tenant that changed its declared code
    while holding issued bills — which BR-TEN-042 forbids and DEF-075 let happen
    at 200 OK — has books in the OLD money and a settings row saying the new
    one. Labelling from settings put a Canadian sign on American money;
    labelling from the books does not.

    Falls back to the declared code ONLY when the result derived none, which
    means the window posted nothing. A 0.00 is the same 0.00 in any currency, so
    the fallback cannot mislabel a figure that exists.
    """
    return result.get("currency") or _tenant_currency()


def _date_param(params: Any, name: str, *, required: bool = False) -> date | None:
    """One ISO calendar date from the query string, or a refusal naming it.

    `date.fromisoformat` and nothing looser, for the reason
    `apps/billing/api._date_field` gives: a period bound decides which month's
    money a finance officer is reading, and a date parsed by guessing at a
    format would put two different windows under one request in two regions
    (BR-TEN-020).

    ABSENT, `null` and `""` are ONE answer — *nobody chose a bound* — which for
    a cumulative read like the AR control is a real and useful request (`to`
    with no `from` is "everything the books have ever held up to this day").
    """
    raw = params.get(name)
    if raw is None or str(raw).strip() == "":
        if required:
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="ledger.report.period_required",
                field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
            )
        return None
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.report.date_invalid",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from problem


#: An id no row can carry, used when a dimension filter is unparseable. uuid7
#: primary keys are time-ordered and never all-zero, so a filter on this matches
#: nothing — which is the point. See `_optional_uuid`.
_MATCHES_NOTHING = UUID(int=0)


def _optional_uuid(params: Any, name: str) -> UUID | None:
    """One dimension id from the query string. **Never silently no filter.**

    **CR-060 C24 / C23 — the ONE invariant here is that a filter must not stop
    applying without anyone noticing.** A parameter that swallowed an
    unparseable id and answered anyway would return the WHOLE ledger while the
    screen showed a property selected in its dropdown. That is the failure
    `reporting.GAP_PREMISES_FILTER_NOT_OFFERED` names as the worse one — *"a
    parameter that took a premises and changed nothing would make the report
    LOOK filtered"* — and it is worse than any error, because the numbers are
    real, they foot, and they are about the wrong thing.

    ABSENT, `null` and `""` are ONE answer — *no filter* — matching
    `_date_param`, so a screen clears a dropdown by sending an empty value.

    ⚠ **AN UNPARSEABLE VALUE YIELDS AN EMPTY REPORT RATHER THAN A REFUSAL, AND
    THAT IS A CONSTRAINED CHOICE RATHER THAN THE BEST ONE.** The first version
    raised `ValidationError(VAL_FORMAT)` under a new key,
    `ledger.report.dimension_invalid`. **G32 refuses that, and its reason is
    decisive:** a raised key with no catalogue entry *"renders as SILENCE now
    that `params.detail` is suppressed (PO ruling 2026-08-19)"*, so the clerk
    would get a failed request explaining nothing. Writing the sentence requires
    **eleven** locale catalogues, which are another lane's files.

    So the value falls back to `_MATCHES_NOTHING`: the report comes back EMPTY,
    which is the same answer a well-formed id for a property with no lines gets
    (`test_c24_tc4`), and is never the unfiltered book. **The invariant holds;
    the diagnosis is what is lost.** In practice the picker only ever serves ids
    from `dimension_seam.premises_options`, so an unparseable value means a
    hand-edited URL rather than a clerk's mistake.
    **OWED, and REPORTED rather than done here: the refusal sentence in all
    eleven catalogues**, after which this falls back to raising and a clerk is
    told the filter was malformed instead of shown an empty table.

    **An id that parses but names nothing is likewise not refused**, and that
    one is deliberate rather than constrained: it is the true answer for a
    property with no lines, and refusing it would need a cross-module existence
    read this module may not make (B1).
    """
    raw = params.get(name)
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return UUID(str(raw).strip())
    except (TypeError, ValueError):
        return _MATCHES_NOTHING


# ═══════════════════════════════════════════════════════════════════════════
# P0.14 — ONE SPELLING FOR THE PREMISES FILTER
# ═══════════════════════════════════════════════════════════════════════════
# **The same filter, on the same tab, had two names.** The journal list reads
# `f.premises` (`BR-SHL-011`'s `f.<name>` grammar, which every other filter in
# Finance uses); the trial balance read a bare `premises`, because it landed
# first (CR-060 C24) and the grammar had not reached it. A clerk who narrows
# the journal to one property and then opens the trial balance sends a
# parameter the second endpoint does not recognise, and it comes back
# UNFILTERED AND FOOTING — which is `_optional_uuid`'s own named nightmare
# (*"a report that LOOKS filtered"*) reached from the other side.
#
# **BOTH ARE ACCEPTED AND `f.premises` WINS.** The bare spelling is DEPRECATED,
# not removed: `GET /ledger/trial-balance?premises=<id>` has been served since
# 2026-09-03 and cutting off a live caller costs more than carrying one alias.
# Measured 2026-09-24: nothing in `07-frontend/src/api/endpoints.ts` sends it —
# `getTrialBalance` offers `from` and `to` only — so the alias is for
# hand-built URLs, saved links and anything outside this repo.
#
# `f.premises` is read FIRST, so a request carrying BOTH — which is exactly
# what a half-migrated caller sends — takes the grammar's answer and never
# silently prefers the legacy one.
PREMISES_FILTER = "f.premises"
PREMISES_FILTER_DEPRECATED = "premises"


def _premises_filter(params: Any) -> UUID | None:
    """The premises id from either spelling — `f.premises` wins.

    Returns `None` only when NEITHER is present or both are empty, so clearing
    the dropdown still clears the filter under either name.
    """
    modern = _optional_uuid(params, PREMISES_FILTER)
    if modern is not None:
        return modern
    return _optional_uuid(params, PREMISES_FILTER_DEPRECATED)


def _window(params: Any, *, required: bool) -> tuple[date | None, date | None]:
    """`from`/`to`, refusing an inverted range rather than answering it empty.

    US-LED-009 TC-6 states the rule for the account ledger — *"Param validation
    rejects the range … never an empty-but-plausible report"* — and it is
    applied to every period read here for the same reason: a report that
    answers `from=2026-08-01&to=2026-07-31` with zero rows tells a finance
    officer their July was empty.

    `reporting.account_ledger` raises the identical refusal itself; this check
    exists so the three reads that DON'T carry their own guard are covered too,
    and so the message is one sentence in one place.
    """
    start = _date_param(params, "from", required=required)
    end = _date_param(params, "to", required=required)
    if start is not None and end is not None and start > end:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="ledger.report.range_inverted",
            params={"from": start.isoformat(), "to": end.isoformat()},
            field_errors=[
                {"field": "from", "code": errors.VAL_RANGE},
                {"field": "to", "code": errors.VAL_RANGE},
            ],
        )
    return start, end


# ═══════════════════════════════════════════════════════════════════════════
# S36 — Revenue & AR (US-LED-007 · 11b §2.10 `GET /finance/revenue-ar`)
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Finance = R for Staff/Clerk, CRUD for Executive
def revenue_ar(request: Any) -> Response:
    """S36's whole tab, out of journal-line dimensions and nothing else.

    Params: `from` + `to` (both REQUIRED — a KPI strip with no period states a
    money figure over an unstated window, which is BR-REP-001's whole subject),
    and `ytd_start`, the first day of the tenant's fiscal year for the
    *Written off YTD* KPI.

    **`ytd_start` IS NOT DEFAULTED AND IS NOT DERIVED HERE.** BR-TEN-022 makes
    periods COMPUTED from fiscal settings and never stored, so no row holds it;
    `reporting.revenue_and_ar` takes it as an input for exactly that reason and
    says so. Omitting it makes the read model sum write-offs from the beginning
    of the books — a real number that is not a year-to-date one — so this
    endpoint serves `written_off_ytd: null` with the reason attached rather
    than mislabelling it (`wire.WRITTEN_OFF_YTD_WINDOW_UNSTATED`). The screen
    passes the day it reads off S8's Regional tab and the KPI fills in.

    NOT PAGINATED, and that is not an oversight of 11b G5. This is a DASHBOARD
    resource, not a list: its `revenue_by_service` table is bounded by the
    tenant's enabled service set (six, BR-REP-006) and its KPI strip is the
    DENOMINATOR those rows foot to. A page of it would make the footer a page
    total — the same reasoning `GET /billing/runs/{id}/findings` records.
    """
    require_tenant(request)
    start, end = _window(request.query_params, required=True)
    ytd_start = _date_param(request.query_params, "ytd_start")
    result = reporting.revenue_and_ar(start=start, end=end, ytd_start=ytd_start)
    return Response(
        wire.revenue_ar_dict(
            result, currency=_currency_of(result), ytd_window_stated=ytd_start is not None
        )
    )


# ═══════════════════════════════════════════════════════════════════════════
# S56 — trial balance (US-LED-008 · 11b §2.10 `GET /ledger/trial-balance`)
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def trial_balance(request: Any) -> Response:
    """LE-1's table and its footer — *"Totals 598.69 | 598.69 ✔"*.

    Params: `from` + `to`, both OPTIONAL and deliberately so. A trial balance
    with no `from` is the cumulative position — which is what makes the AR row
    equal the Still-owed KPI on S36 (one derivation, two presentations) — and
    an open end is a legitimate request a required bound would refuse.

    **NOT PAGINATED, and the footer is why.** US-LED-008 TC-1 requires the
    table to foot to 598.69 = 598.69 over ALL rows; a page would make
    `total_debit` a page total and the word *Balanced* a claim about a page.
    The row count is bounded by the tenant's CHART OF ACCOUNTS — the eleven
    designations plus their tax authorities and whatever the tenant added — not
    by transaction volume, so it does not grow with the books. `GET /payments`
    pages because it lists transactions; this lists accounts.

    **THE PREMISES FILTER OF BR-LED-009 IS NOW SERVED — `?f.premises=<id>`
    (CR-060 C24, 2026-09-03; renamed by `P0.14`, 2026-09-24).** ⚠ **IT WAS A
    BARE `?premises=` UNTIL 2026-09-24 AND THE JOURNAL LIST ON THE SAME TAB
    TOOK `?f.premises=`** — one filter, two spellings, so a clerk carrying a
    property from one screen to the other got an unfiltered, footing report.
    **Both are accepted and `f.premises` wins**; the bare one is deprecated
    rather than removed, so no saved link breaks. See `_premises_filter`.
    This paragraph has been corrected twice before and the
    chain is kept, because each correction was true when it was written and the
    pair is the record of how the blocker shrank. It first read *"`journal_lines.
    premises_id` is NULL on every row in the product (US-LED-002 unbuilt), so a
    `premises` param would accept a value and change nothing"* — hard-won law 1
    in a served docstring, corrected 2026-09-02 by `DEF-3382` when US-LED-002
    turned out to have landed on **2026-08-16**. It then read that the filter was
    *"not served because nothing calls it (LAW 0)"*, which was also true: no
    screen asked. **The finance-screens lane then verified the dimension, removed
    the General Ledger's own false sentence, and could not ship the dropdown
    because this endpoint took no property.** So the param exists now for the
    reason LAW 0 wants — a caller is waiting for it.

    ⚠ **AND THE FILTERED TABLE DOES NOT FOOT, WHICH THE BODY SAYS RATHER THAN
    THE SCREEN GUESSING.** `balanced` comes back **`null`** — never `false` —
    with `a_trial_balance_narrowed_to_one_premises_does_not_foot` on
    `unavailable`. Balance is a property of an ENTRY: a receipt's cash leg
    carries no property at all, so narrowing removes it and leaves the AR leg.
    See `reporting.GAP_FILTERED_BALANCE_IS_NOT_A_VERDICT` for the argument.

    **An unbalanced UNFILTERED period is still served unbalanced.**
    `balanced: false` with the `difference` on it is the BR-LED-007 red flag
    reaching a human; there is no branch here that hides, rounds or "corrects"
    it (US-LED-008 TC-5). That is exactly why the filtered case may not borrow
    the same word for a different fact.
    """
    require_tenant(request)
    start, end = _window(request.query_params, required=False)
    result = reporting.trial_balance(
        start=start, end=end, premises_id=_premises_filter(request.query_params)
    )
    return Response(wire.trial_balance_dict(result, currency=_currency_of(result)))


# ═══════════════════════════════════════════════════════════════════════════
# S56 — the journal list (US-LED-013 · 11b §2.10 `GET /ledger/journal-entries`)
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def journal_entries(request: Any) -> Response:
    """The S56 list, with drafts, posted entries, reversals and links all
    first-class visible (BR-LED-012 / US-LED-013 §1).

    The capability row's filters, under BR-SHL-011's `f.<name>` grammar and the
    period params the other reads use:

        f.type          standard | accrual | reversing
        f.status        draft | posted
        f.source_type   the raw journal source (invoice, payment, manual_je, …)
        f.premises      entries with a LINE carrying this property   (C24)
        f.ledger_account  entries with a LINE on this chart account  (C23)
        q               searches the JE #, the MEMO and — since `DEF-LED-10071`
                        J1 (PO 2026-10-12) — what any LINE belongs to: account
                        number, customer number, customer name, premises
                        address, unit label. Still one SQL query, still paged;
                        the row is the whole entry.
        from / to       the entry-date window (the matrix's "period" filter)

    **THE TWO NEWEST FILTERS SELECT AN ENTRY BY WHAT ITS LINES CARRY, AND THE
    ROW REMAINS THE WHOLE ENTRY (CR-060 C24 · C23).** Debit and credit are still
    totalled over ALL of an entry's lines, so a filtered row still balances and
    `balanced` keeps meaning what it means everywhere else on this screen. Half
    an entry is not an entry: totalling only the matching lines would show
    `balanced: false` on entries that are perfectly balanced, which is a false
    alarm of exactly the kind the trial balance refuses to raise one endpoint
    over. See `reporting.journal_entry_list` for why this differs, correctly,
    from `trial_balance`'s choice to narrow its sums.

    **`f.ledger_account` IS HOW C23's *"open a trial-balance line to its
    entries"* IS SERVED**, and it is the cheaper of the two shapes that were on
    the table: the row a clerk clicks IS a chart account and this list already
    sits on the same screen, so it needs no new read model, no new route and no
    new serializer. The alternative was `journal_entry_detail(entry_id)`, a
    second read model for one entry — a larger surface for a smaller question.
    ⚠ **WHAT IT ANSWERS AND WHAT IT DOES NOT:** it says WHICH ENTRIES TOUCHED
    the account; it does not say what each entry contributed TO it. That figure
    is the dimension expansion and is still unbuilt — stated here so a screen
    does not present an entry's full debit as its contribution to one account.

    **`q` SEARCHES BOTH FIELDS THE MATRIX NAMES — "JE #, memo" — SINCE
    BR-LED-021.** OQ-176 is CLOSED (PO 2026-08-12, *"Approve a JE- series"*):
    `journal_entries.number` carries a `JE-` number allocated per tenant under
    BR-TEN-035 and stamped AT POST, so the clerk told to *"look at JE-105"* can
    now type exactly that. Every row carries `je_number`, and it is **null on a
    draft by ruling** (*"a draft has NO number"*). A POSTED row with a null
    number means this tenant has no `journal_entry` series row — reported in
    `unavailable` as `posted_entries_without_a_je_number`, never faked.

    **`f.status=reversed` IS NOT ACCEPTED**, though the matrix lists it beside
    draft and posted. "Reversed" is not a status a row carries — it is the
    presence of a `reversed_by_entry_id` link, and `journal_entries.status`
    holds exactly two values (B2 r13 #2). The LINK is served on every row in
    both directions, so the screen can render the state; inventing a third
    status here would put a value in a filter that no column can ever equal.
    REPORTED.

    **DRAFTS APPEAR HERE AND NOWHERE ELSE.** Every money figure in this module
    filters `status='posted'`, because a draft is not in the books; this one
    list exists to show that a draft EXISTS so somebody can finish or delete
    it. `status` keeps the two facts apart and `balanced` says whether the
    draft may post at all (BR-LED-003).

    ⚠ **THE PAGE IS TAKEN IN THE DATABASE SINCE 2026-09-24 (`DEF-LED-6493` ·
    `NFR-3` · `P1.8`), AND THIS PARAGRAPH RECORDED THE OPPOSITE.** It read *"THE
    PAGE IS TAKEN IN MEMORY, NOT IN THE DATABASE — a stated deviation … the
    QUERY is not [bounded], which is a performance note the next lane should
    have rather than a correctness one."* At T7 that note was fair; at the top
    of T5 it is **40,000 entries built to draw fifty**, which is `NFR-3`
    breached rather than noted. Measured on the old code: **67 statements over
    60 entries and 307 over 300**, one per entry.

    `reporting.journal_entry_list` now takes `offset`/`limit`/`sort`/`direction`
    and returns `total` from a `COUNT(*)`, so the LIMIT and the OFFSET are in
    SQL and the cost of this screen no longer follows the book. The envelope is
    unchanged — `core.pagination.prepaged` builds byte-for-byte the four keys
    `StandardPagination` served, with the three extra keys after them exactly
    where they were.

    **`sort` ACCEPTS TWO NAMES AND `number` IS NOT ONE OF THEM IN SQL.** The
    drawing puts a `⇅` on ENTRY NO. and DATE; `JE-{MM}{DD}{YY}-{0000}` does not
    sort chronologically as text, so `?sort=number` orders by `entry_date`
    (`P1.18`, `reporting.JOURNAL_SORT_COLUMNS`).
    """
    require_tenant(request)
    start, end = _window(request.query_params, required=False)
    params = request.query_params
    currency = _tenant_currency()
    listing = parse_list_params(
        params,
        allowed_sorts=reporting.JOURNAL_SORTS,
        default_sort=reporting.JOURNAL_DEFAULT_SORT,
        default_dir="desc",
    )

    # The one read, closed over the filters, so `prepaged` can re-run it when it
    # clamps an out-of-range page (BR-SHL-011: clamp, never error).
    captured: dict[str, Any] = {}

    def fetch(page_params: Any) -> tuple[list[dict[str, Any]], int]:
        result = reporting.journal_entry_list(
            start=start,
            end=end,
            entry_type=params.get("f.type") or None,
            status=params.get("f.status") or None,
            source_type=params.get("f.source_type") or None,
            search=params.get("q") or None,
            premises_id=_premises_filter(params),
            ledger_account_id=_optional_uuid(params, "f.ledger_account"),
            sort=page_params.sort,
            direction=page_params.dir,
            offset=max(page_params.page - 1, 0) * page_params.per,
            limit=page_params.per,
        )
        captured.update(result)
        return (
            [wire.journal_entry_row(row, currency=currency) for row in result["rows"]],
            result["total"],
        )

    response = prepaged(request, listing, fetch)
    # Beside the DRF envelope, exactly as `GET /invoices` carries its roll-up
    # and `GET /payments` its totals: the basis label BR-REP-001 requires on
    # every money group, and the two columns of the capability matrix the books
    # cannot fill (the JE # where a tenant has no series, and the actor, which
    # lives in `audit_log`). All three are facts about the FILTERED SET rather
    # than about the page — see the read model.
    response.data["basis"] = captured["basis"]
    response.data["currency"] = currency
    response.data["unavailable"] = wire.gaps(captured["unavailable"])
    return response


# ═══════════════════════════════════════════════════════════════════════════
# S41 — dual-basis remittance (US-LED-014 · 11b §1 `GET /finance/taxes`)
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def finance_taxes(request: Any) -> Response:
    """S41 Taxes & Remittance — BOTH bases, always (BR-LED-002 / BR-LED-013).

    11b §1 marks this row **OK** with one amendment: *"dual-basis always —
    billed AND collected per authority + basis indicator + remitted/outstanding
    columns"*, superseding the prototype's collected-only table. The amendment
    is honoured in the only way the books allow it to be: the billed basis is
    real (LE-3's **47.38** across the three July bills, split State 13.87 ·
    County 2.22 · City 4.44 · PUC 0.44), `remitted` is real (Σ debits from
    remittance-sourced entries — the JE that drains the liability), and the
    COLLECTED column is served **null with its reason** rather than filled with
    the billed figure.

    That null is BR-LED-002's own definition refusing to be guessed: *"tax
    inside cleared payments via allocation"*, and an `allocations` row carries
    no line class (OQ-129). LE-3's signed **20.97** works only because that
    allocation covered its tax lines IN FULL; what a PARTIAL payment meets —
    tax pro-rata, first, or last — is a money rule nobody has signed, and one
    invented here would decide permanently and invisibly how much tax a utility
    remits.

    `remitting_basis` is null per authority for the same class of reason: r13
    #3 puts the setting on `tax_remittances`, that table does not exist, and
    LE-3 has State on COLLECTED while County is on BILLED — so `outstanding` is
    given PER BASIS and never as one number, because a default would be wrong
    for one of them in the first month it ran.

    Params `from` + `to` are REQUIRED: a remittance table is always *for a
    period* (an authority is filed with quarterly or monthly), and an unstated
    window would make "outstanding" mean something different to every reader.
    """
    require_tenant(request)
    start, end = _window(request.query_params, required=True)
    result = reporting.remittance_by_authority(start=start, end=end)
    return Response(wire.remittance_dict(result, currency=_currency_of(result)))


urlpatterns = [
    # 11b §2.10, verbatim. `finance/…` and `ledger/…` are two prefixes because
    # the audit gives two: S36's read-model is a FINANCE tab and the journal /
    # trial balance are the LEDGER itself. Neither collides with payments'
    # `finance/deposits…` family (unbuilt) or with customers' `accounts/…`.
    path("finance/revenue-ar", revenue_ar),
    path("finance/taxes", finance_taxes),
    path("ledger/trial-balance", trial_balance),
    path("ledger/journal-entries", journal_entries),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-007@e419f62 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-03-trial-balance-reports.md — US-LED-007 + US-LED-008 — · 04-docs/05-modules/09-ledger/06-epics/EP-LED-04-manual-je.md — US-LED-013 — · 04-docs/05-modules/09-ledger/06-epics/EP-LED-05-remittance-close-export.md — US-LED-014 — · 04-docs/05-modules/09-ledger/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §1 + §2.10 + the §2.10b body contract this lane WROTE; co-packets US-LED-008/013/014, same five sources)
# generated: 2026-08-11 by story-coder (W5 ledger read-API lane — the four routes S36, S41 and S56 had no way to reach a complete read model through)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests/test_us_led_ledger_api.py (RED-PROVED FIRST: django.urls.exceptions.Resolver404 on every path and AttributeError on every view name — verbatim in the lane report) · pytest tests -m isolation✔ · pytest tests -m golden✔ · run_gates✔ · openapi/schema.json REGENERATED (BE-11 TC05 diffs it, so an endpoint added without it goes red)
# exceptions: (1) **GET /ledger/journal-entries/{id} IS NAMED BY 11b §2.10 AND IS NOT SERVED** — there is no read model for an entry's LINES with their dimensions, `apps/ledger/reporting.py` + `selectors.py` are G7 human-owned and not this lane's to extend, and an api.py may not reach the ORM (G6). Not stubbed (a 501 is a promise); the read that closes it is named: `apps.ledger.reporting.journal_entry_detail(entry_id)` · (2) `written_off_ytd` is NULL unless the caller passes `ytd_start` — BR-TEN-022 stores no fiscal year and the read model's fallback is an ALL-TIME total that would be mislabelled year-to-date · (3) ⚠ **CORRECTED 2026-09-24 (`P0.14`) — THIS READ *"the BR-LED-009 PREMISES filter on the trial balance is NOT offered"* AND HAD BEEN FALSE SINCE 2026-09-03.** CR-060 C24 served it and this exceptions line was never amended, so the file's own summary contradicted its own docstring for three weeks. The filter IS offered, as **`f.premises`**, with the bare `premises` accepted as a deprecated alias; the filtered table returns `balanced: null` rather than a verdict, which is the real exception and is the one now stated · (4) `f.status=reversed` is NOT accepted though EP-LED-04's matrix lists it — "reversed" is a LINK (`reversed_by_entry_id`, served both ways on every row), not a value `journal_entries.status` can ever hold · (5) ⚠ **CORRECTED 2026-09-24 (`P0.3`) — THIS READ *"`q` searches the MEMO only … a journal entry has no number and `core/numbering.KNOWN_SERIES` has no series for one"* AND BOTH HALVES WERE FALSE.** `OQ-176` closed on 2026-08-12, `core.numbering.JOURNAL_ENTRY` has existed since 2026-08-15, and the docstring twelve lines above this line already said `q` searches both fields. The remaining, TRUE exception is narrower and is what now stands: a POSTED entry whose tenant has no `journal_entry` series row carries **no number at all**, for ever (hard rule 4 freezes `number` at post), and the list reports that by name as `posted_entries_without_a_je_number` rather than faking one · (6) the journal list's PAGE is taken in memory, not in the database: `reporting.journal_entry_list` returns a tuple, so the wire response is bounded (11b G5) and the query is not — a performance note, reported, fixable only inside a G7 file · (7) revenue-ar, the trial balance and the tax table are NOT paginated at all: each is a footing whole (KPI denominators, a balanced footer, a per-authority total) and each is bounded by the CHART or the enabled service set rather than by transaction volume · (8) `currency` is the TENANT's declared CHAR(3) via tenancy's published `regional_settings()`, not a Σ-derived one — see apps/ledger/wire.py, and the mixed-currency exposure reported with it · (9) no write verb exists on any path here, so a forged POST/PUT/PATCH/DELETE is a router 405 before any view runs (hard rule 4 / BR-LED-003) · (10) OQ-175 (Finance/Owner is not a role this product has) does NOT gate these reads — A4 gives Staff/Clerk R on Finance and R/run on Reports — but it still blocks every WRITE on §2.10, none of which is served
# amended:   2026-08-15 by story-coder (DEF-112 lane) — NO CODE CHANGED. Two claims in this file went stale the moment the screens landed and hard-won law 1 applies to a trailer as much as to a docstring: the Impacts note said S36/S41/S56 "have no screen yet" (S36 shipped 2026-08-11, S41 and S56 on 2026-08-15) and the checklist marked `E=deferred(no-frontend-half)` for a frontend half that now exists — `GeneralLedgerPage.tsx` calls `GET /ledger/trial-balance` and `GET /ledger/journal-entries`, `RemittancePage.tsx` calls `GET /finance/taxes`, and `RevenueArPage.tsx` has called `GET /finance/revenue-ar` since 2026-08-11. The WRITE half of this module lives in `apps/ledger/finance_api.py`, deliberately NOT here: this file's guarantee that no write verb exists on any of its paths is what gives the four read routes their router-level 405 (hard rule 4 / BR-LED-003), and adding a POST would retire it silently.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
