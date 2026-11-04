# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-019 (S7 — the landing screen, and every tile either carries
#           the owner's figure or says it cannot answer)   Screens: S7
# Rules:    BR-REP-024 (a dashboard tile never computes a figure) ·
#           BR-REP-002 (read-models only; never a side-maintained number) ·
#           BR-REP-001 (every money figure labels its basis) · BR-REP-012
#           (the Active-connections classes) · B1 / BR-TEN-013 (a module never
#           touches a neighbour's ORM) · CLAUDE.md rule 1 (tenant scoping) ·
#           rule 2 (money is NUMERIC(18,6) + CHAR(3), never a float)
# Tests:    06-backend/tests/test_us_rep_019_dashboard.py
# Impacts:  apps/reports/dashboard.py (the ONLY caller) · nothing else — this
#           file reads and never writes, anywhere, to anything.
# ───────────────────────────────────────────────────────
"""reports → other-module SEAMS for S7. Every figure the dashboard shows.

**THE DASHBOARD OWNS NO FACT.** It is the densest collection of money-and-volume
claims in this product, and not one of them is its own: AR belongs to the
ledger, failed payments to payments, connections to customers, unbilled reads to
metering. So every number on S7 is fetched from the module that owns it, through
one of the callables documented below, **resolved BY NAME at call time** — the
same pattern `apps/tenancy/seams.py` uses and for the same reason: the moment an
owner publishes its read, the tile starts showing it with nothing here re-wired.

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS AT ALL, IN NUMBERS THIS PRODUCT HAS ALREADY PAID FOR
════════════════════════════════════════════════════════════════════════════
Two rows in the defect register are the whole argument.

**DEF-104** — four surfaces disagreed about ONE customer's balance. The account
screen said **$0.00** while the ledger held an issued, unpaid **$108.88**. Each
surface had computed the figure for itself, each was internally consistent, and
the one a clerk would quote to the customer was the wrong one.

**DEF-075** — `financial_records_exist()` resolved to `None` for billing, `None`
was read as *"this module has nothing"* when it meant *"this module cannot
answer"*, and a tenant holding issued bill BL-2606-000001 (**108.88 USD**)
re-denominated its books at **HTTP 200**.

Together they give the rule this file enforces, which is BR-REP-024:

    A DASHBOARD TILE NEVER COMPUTES A FIGURE. It renders the owner's published
    figure, or it REPORTS BY NAME THAT IT CANNOT ANSWER — never 0, never a
    client-side sum, never a second query over another module's tables.

`None` from any function here therefore means *"the owner does not publish this
read"*, and `apps/reports/dashboard.py` turns every one into an `unavailable`
entry with a stable `code` the screen renders in the user's own language. There
is no branch anywhere in this module that turns a `None` into a number.

════════════════════════════════════════════════════════════════════════════
THE CONTRACTS — five wired, three dark, and the dark ones say so
════════════════════════════════════════════════════════════════════════════
WIRED (the owner publishes it today; the figure on the tile is the owner's own):

  apps.ledger.reporting.revenue_and_ar(*, start, end, ytd_start=None) -> dict
    ONE call answers three tiles — **AR outstanding** (`kpis.still_owed`),
    **Revenue this period** (`kpis.billed`) and the **Service mix** panel
    (`revenue_by_service`) — and that is deliberate rather than convenient: a
    second call could straddle a posting and hand the screen a KPI and a panel
    that do not add up. It also carries the `currency` its figures ARE, derived
    from the entries summed (DEF-081), so the dashboard never labels an amount
    with a code it did not come from. The result's own `aging` is `None` with a
    named reason and is passed through untouched — see the AR-aging note below.

  apps.tenancy.selectors.regional_settings() -> dict
    The tenant's declared `currency` — the CHAR(3) every amount is labelled with
    when the books themselves derive none.

  apps.tenancy.selectors.tenant_today() -> date
    THE UTILITY'S OWN calendar day, in the utility's timezone. Read ONLY when
    the caller passed no `as_of` — see `tenant_today` below for why that leaves
    BR-TEN-043 intact, and DEF-299 for what its absence cost.

  apps.tenancy.selectors.current_period(reference_date=None) -> dict | None
    The accounting window (BR-TEN-022: periods are COMPUTED from fiscal settings
    and never stored). The SAME read S36, S59 and S60 head their pages with, so
    no two screens in this product can disagree about which month a figure
    belongs to. `reference_date` is an ARGUMENT and never a clock (BR-TEN-043),
    which is what lets a caller ask for last month and a test ask for July.
    Absent ⇒ the page head says the fiscal calendar is not configured and asks
    for no figures at all, rather than defaulting to the browser's month.

  apps.payments.summary.summary(*, as_of) -> SummaryView
    Read for the ops facts payments publishes as COUNTS — `chips.returned_mail`
    and `chips.autopay_scheduled` — and NOT for a failed-payment count; see the
    dark list. `as_of` is an argument and never a clock (BR-TEN-043).

  apps.customers.selectors.accounts_rollup() -> dict
    The S17 header roll-up. Read for `accounts` (how many accounts exist), which
    is NOT the BR-REP-012 Active-connections KPI and is never rendered as one.

  apps.billing.selectors.invoices_rollup() -> dict
    The S30 header roll-up — `bills` lifetime and `unresolved_from_last_run`
    (BR-BIL-015's queue for the most recent run, `None` when the tenant has
    never run one, because "0 unresolved" and "there has never been a run" are
    different facts and this module keeps them different).

DARK — the owner publishes NO such read, so the tile reports that it cannot
answer. Each is parked in `10-scripts/gates/seam_known_gaps.txt` with
`fallback=reports-absent guard=none`, because no arrival can make an absence a
lie; the day the owner publishes one, the park expires and G20 goes red until
this file and that row are updated together.

  apps.metering.selectors.unbilled_read_rollup() -> dict | None
    The prototype's *"1,247 unbilled reads · 312 pending routes"*. Metering owns
    `meter_reads` and publishes `read_list` (a paginated LIST for S25) and no
    count of committed-but-unbilled reads. **Counting them from here would mean
    reports querying metering's tables**, which B1 forbids and G6 greps for —
    and it would be a second counter of a fact metering owns, which is how
    DEF-104 starts.

  apps.customers.selectors.account_status_class_counts() -> dict | None
    BR-REP-012, verbatim: Active-connections = **Active + Marked disconnect +
    Vacation hold**; Pending activation and Closed excluded. That is a sum over
    three named status classes and customers publishes no such breakdown.
    `accounts_rollup()["accounts"]` is available and is **NOT** substituted:
    it answers *how many accounts exist*, which on the seeded fixture includes
    pending and closed ones, so rendering it under the Active-connections label
    would be a wrong number rather than a partial one — DEF-075's exact shape.

  apps.payments.summary.failed_payment_count(*, as_of) -> int | None
    `summary().failed` is a LIST and it is sliced `[:50]` for S32's panel. Its
    length is therefore a count of *rows payments chose to show*, not of failed
    payments: a tenant with 80 failures would read **50** on the first screen
    after sign-in, and 50 is not a smaller truth than 80, it is a false one.
    The honest tile says it cannot answer and names this.

AR AGING is a fourth absence and is NOT a seam gap: the ledger DOES publish the
read, and the read's own answer is `aging: None` with the reason (a journal line
carries no due date, and `account_opening_buckets` is unbuilt). The dashboard
passes that reason through and — following S60's precedent — QUANTIFIES the
refusal by showing the receivable total the missing bands would have to add up
to. An empty four-row table would read as *"nothing is overdue"* to the one
person who most needs to know otherwise.

RECENT ACTIVITY is a fifth, and it is not a seam either: no module publishes an
event read-model of any kind, so there is no owner to name. It is reported as a
gap against US-REP-016, whose §1 is where the feed is specified.

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE WILL NOT DO
════════════════════════════════════════════════════════════════════════════
  · **No arithmetic on money.** Not a sum, not a ratio, not a difference. Every
    amount leaves here as the Decimal the owner produced.
  · **No ORM.** There is not one `objects.` in this module. If a fact is not
    published by its owner it is absent, and absent is a legal answer.
  · **No clock.** Every window is an argument (BR-TEN-043), so the dashboard can
    be asked for yesterday and reconciled against yesterday's day-end.
"""

from collections.abc import Callable
from importlib import import_module
from typing import Any

#: The four modules S7 reads from, and the published file in each that answers.
#: Named as constants so G20 can substitute them into the `resolve()` call sites
#: statically — a module bound from a loop variable is exactly the shape that
#: hid DEF-075's missing leg from every static reader.
LEDGER_MODULE = "ledger"
LEDGER_KIND = "reporting"
TENANCY_MODULE = "tenancy"
TENANCY_KIND = "selectors"
PAYMENTS_MODULE = "payments"
PAYMENTS_KIND = "summary"
CUSTOMERS_MODULE = "customers"
CUSTOMERS_KIND = "selectors"
BILLING_MODULE = "billing"
BILLING_KIND = "selectors"


def resolve(module: str, function: str, kind: str = "selectors") -> Callable[..., Any] | None:
    """The owning module's published callable, or None while it is not authored.

    getattr AT CALL TIME, never at import: the day a lane lands its read, every
    tile that wants it starts showing it with nothing here re-wired. This is
    `apps/tenancy/seams.py::resolve` with a `kind` parameter, because the reads
    S7 needs live in `reporting`, `selectors` and `summary` rather than all in
    `services` — and DEF-035 is what happens when a seam points at the wrong
    file: `last_issued_invoice_period_end` resolved `services` instead of
    `selectors`, returned None on EVERY call, and silently recorded
    `move_out_date_not_checked_against_issued_bills` on every move-out in the
    product.
    """
    try:
        published = import_module(f"apps.{module}.{kind}")
    except ImportError:
        return None
    found = getattr(published, function, None)
    return found if callable(found) else None


# ── ledger — the money on the books (WIRED) ─────────────────────────────────
def revenue_and_ar(**kwargs: Any) -> dict[str, Any] | None:
    """S36's own read model: AR, billed, the service slice, and its own gaps.

    None while unwired — the dashboard then reports every money tile as
    unavailable. It does NOT fall back to another module's cached balance:
    `accounts.balance` is exactly the column DEF-104's $0.00 came out of.
    """
    found = resolve(LEDGER_MODULE, "revenue_and_ar", kind=LEDGER_KIND)
    return found(**kwargs) if found is not None else None


# ── tenancy — whose month is it (WIRED) ─────────────────────────────────────
def regional_settings() -> dict[str, Any] | None:
    """The tenant's declared CHAR(3), for labelling a book that derives none."""
    found = resolve(TENANCY_MODULE, "regional_settings", kind=TENANCY_KIND)
    return found() if found is not None else None


def tenant_today(**kwargs: Any) -> Any | None:
    """THE UTILITY'S OWN CALENDAR DAY — the read moment when the caller gave none.

    Added by CR-015 for DEF-299. `dashboard_summary` needs the read moment as a
    VALUE it can clamp into the selected period (BR-REP-036), and before this
    the only place a clock was reached was INSIDE `current_period`, which never
    handed the day back — so the assembled payload could label itself with the
    period end and nothing had the other date to compare it against.

    ⚠ **THIS DOES NOT WEAKEN BR-TEN-043** and the distinction is worth stating
    once. The rule is that a window is an ARGUMENT rather than a clock, and it
    survives exactly as before: pass `as_of` and this function is never called,
    so the whole read model is a pure function of its arguments and can be
    tested against a signed figure. It is reached ONLY when the caller supplied
    nothing, which is precisely when `current_period()` already read the same
    clock — one clock read, at the boundary, turned into a value immediately.

    It is the TENANT's today, in the utility's own timezone, not the server's:
    a dashboard headed with the host's date is wrong by a day for half of every
    day in half the world.
    """
    found = resolve(TENANCY_MODULE, "tenant_today", kind=TENANCY_KIND)
    return found(**kwargs) if found is not None else None


def current_period(**kwargs: Any) -> dict[str, Any] | None:
    """The tenant's COMPUTED accounting window (BR-TEN-022).

    None when the tenant has no fiscal calendar — and then EVERY money figure on
    S7 is served null with `fiscal_period_not_configured`, because a KPI headed
    "this period" over a substituted calendar month is a wrong number wearing a
    right label.
    """
    found = resolve(TENANCY_MODULE, "current_period", kind=TENANCY_KIND)
    return found(**kwargs) if found is not None else None


# ── payments — the ops counts payments publishes (WIRED) ────────────────────
def enabled_service_codes() -> tuple[str, ...] | None:
    """WHICH SERVICES THIS TENANT SELLS — the row set of the service-mix panel.

    Added by the PO ruling of 2026-08-19, decision 1, verbatim: *"draw the
    tenant's own configured services — always all of them"*. Until that ruling
    the panel drew a hard-coded five (`electric, water, sewer, trash, gas`), so
    a broadband-and-water utility met five rows, three permanently empty, and
    its real revenue in the remainder footnote.

    `apps.tenancy.selectors.enabled_service_codes()` already publishes exactly
    this, ENABLED-only and in the platform catalogue's own `sort` order, which
    IS BR-RAT-024's seed order. It is read through the seam like every other
    fact on this screen rather than imported, so a tenancy that cannot answer
    degrades to a named gap instead of a traceback.

    **`None` and `()` are different answers and both are honest.** `None` is
    "tenancy could not say", and the panel then draws the services that
    actually billed and reports the gap by name. `()` is "this tenant has
    enabled no service", which draws no rows at all — and is not turned into
    the old five, because a row list nobody configured is an invention.
    """
    found = resolve(TENANCY_MODULE, "enabled_service_codes", kind=TENANCY_KIND)
    if found is None:
        return None
    codes = found()
    return None if codes is None else tuple(str(code) for code in codes)


def payments_summary(**kwargs: Any) -> Any | None:
    """S32's summary view. Read for `chips`, never for a failed-payment count."""
    found = resolve(PAYMENTS_MODULE, "summary", kind=PAYMENTS_KIND)
    return found(**kwargs) if found is not None else None


def failed_payment_count(**kwargs: Any) -> int | None:
    """DARK. None means *payments cannot answer*, and the tile says so.

    `summary().failed` exists and is deliberately NOT counted here: it is sliced
    to fifty rows for S32's panel, so its length answers a different question.
    """
    found = resolve(PAYMENTS_MODULE, "failed_payment_count", kind=PAYMENTS_KIND)
    return int(found(**kwargs)) if found is not None else None


# ── customers — who is connected (one WIRED, one DARK) ──────────────────────
def accounts_rollup() -> dict[str, Any] | None:
    """How many accounts exist. NOT the BR-REP-012 KPI; never rendered as one."""
    found = resolve(CUSTOMERS_MODULE, "accounts_rollup", kind=CUSTOMERS_KIND)
    return found() if found is not None else None


def account_status_class_counts() -> dict[str, Any] | None:
    """DARK. BR-REP-012's three classes. None ⇒ the tile refuses.

    Nothing here substitutes `accounts_rollup()["accounts"]`. That total counts
    Pending activation and Closed accounts, which BR-REP-012 EXCLUDES, so it is
    a wrong figure under this label rather than an approximate one.
    """
    found = resolve(CUSTOMERS_MODULE, "account_status_class_counts", kind=CUSTOMERS_KIND)
    return found() if found is not None else None


# ── metering — the reads not yet billed (DARK) ──────────────────────────────
def unbilled_read_rollup() -> dict[str, Any] | None:
    """DARK. None ⇒ the tile refuses and names metering as the owner."""
    found = resolve("metering", "unbilled_read_rollup", kind="selectors")
    return found() if found is not None else None


# ── billing — what has been billed (WIRED) ──────────────────────────────────
def invoices_rollup() -> dict[str, Any] | None:
    """The S30 roll-up: lifetime bills + BR-BIL-015's unresolved queue."""
    found = resolve(BILLING_MODULE, "invoices_rollup", kind=BILLING_KIND)
    return found() if found is not None else None


# ═══════════════════════════════════════════════════════════════════════════
# CR-012 · DSH-01 — the five regions the PO's requirement added or changed.
#
# Same law as everything above it: resolved BY NAME at call time, `None` means
# *the owner does not publish this read*, and nothing here substitutes.
# ═══════════════════════════════════════════════════════════════════════════


# ── metering — WHICH CYCLE CLOSES NEXT (WIRED) ──────────────────────────────
def cycles_list(**kwargs: Any) -> list[dict[str, Any]] | None:
    """SET-07's own cycle definitions (BR-REP-027).

    `apps.metering.selectors.cycles_list` is the read S27 and the SET-07 landing
    page already draw, and each row carries what the status line needs: `code`,
    `read_day_to`, `bill_day`, `lifecycle_status` and — the tie-breaker the PO
    named — `accounts`, which metering counts through `service_points.cycle_id`
    and its own account seam.

    **Reports does not query `cycles` and must not.** The cycle table is
    metering's (B2), the meaning of *"which accounts bill on this cycle"* is
    metering's rule (BR-MET-033), and a second implementation of it here is
    DEF-104's shape wearing a date instead of a balance.
    """
    found = resolve("metering", "cycles_list", kind="selectors")
    return list(found(**kwargs)) if found is not None else None


# ── payments — THE FIVE AGING BANDS (WIRED) ────────────────────────────────
def outstandings(**kwargs: Any) -> Any | None:
    """S34's `OutstandingsView`, whose `.ageing()` IS DSH-01's five buckets.

    ⚠ **THIS IS THE READ THAT MAKES BR-REP-030's ARRANGEMENT RULE TRUE, and it
    is true because of where the bucket comes from rather than because anything
    here checks for it.** `apps.payments.outstandings` buckets an account on the
    age of its OLDEST UNPAID BILL (`bucket_for(days_late)`), and reads
    `payment_plans.status` only as a column on the row. So an account 45 days
    late that is on an active arrangement is already in `31-60` there, which is
    exactly what the PO ruled — *"accounts on an active payment arrangement
    count in their true bucket, not Current"* — and this module has nothing to
    do but not undo it.

    **NOT `apps.payments.reporting.ar_aging`**, which answers A14's FOUR-column
    question: it folds Current and 1–30 into one `current` column, and DSH-01
    draws them as two different rows. A four-band answer rendered under five
    labels would be a wrong figure, not a coarser one.
    """
    found = resolve(PAYMENTS_MODULE, "outstandings", kind="outstandings")
    return found(**kwargs) if found is not None else None


# ── audit — THE ACTIVITY FEED (WIRED, and the old gap note was stale) ───────
def audit_recent(*, tenant_id: Any, since: Any, until: Any) -> list[dict[str, Any]] | None:
    """The last day's trail rows, newest first (BR-REP-031).

    ⚠ **`GAP_ACTIVITY` used to say *"no module in this product publishes an
    event read-model at all, so there is no owner to ask"*. That was true of the
    OPERATIONAL modules and was never true of `apps.audit`,** which has published
    `audit_queryset` and `audit_page` since the S61 viewer shipped — hard-won law
    1, a note claiming an absence is not the absence. The feed reads them.

    Two calls and not one, because that is the shape audit publishes: the
    queryset applies BR-AUD-007/009/013 (tenant scope, the retention floor, the
    window), and `audit_page` serialises a page with ONE actor-name lookup for
    the whole page rather than one per row.
    """
    query = resolve("audit", "audit_queryset", kind="selectors")
    page = resolve("audit", "audit_page", kind="selectors")
    if query is None or page is None:
        return None
    rows = list(
        query(
            tenant_id,
            filters={"from": str(since), "to": str(until)},
            sort="created_at",
            direction="desc",
        )[:ACTIVITY_SCAN_LIMIT]
    )
    return list(page(tenant_id, rows))


#: How many trail rows are serialised before the operator-relevance filter runs.
#: The PANEL shows six; the filter drops settings edits, sign-ins and user
#: administration, so scanning exactly six would show three rows on a busy day.
#: A bounded scan, because an unbounded one on the landing page is a full-table
#: read on the first screen after every sign-in.
ACTIVITY_SCAN_LIMIT = 120


# ── tenancy — THE TYPED REVENUE TARGET (DARK) ──────────────────────────────
def monthly_revenue_target() -> Any | None:
    """DARK. BR-REP-034's typed target; `None` ⇒ the tile shows the figure alone.

    **The PO ruled option "B" on 2026-08-18** — a per-tenant monthly revenue
    target typed by the utility in Settings — and ruled the untyped fallback in
    the same breath: *"With no target typed, the tile degrades to option A — the
    figure alone, no sub-line"*. That fallback is not a stub. It is the state
    **every tenant on this deployment is in**, it is the state the tile is
    proved in first, and it stays correct forever for a utility that never types
    one.

    ⚠ **THE FIELD ITSELF IS `apps/tenancy`'S TO ADD AND IS NOT THIS LANE'S.**
    The contract wanted here, by name and shape, so the day it exists this seam
    lights up with no edit on either side:

        apps.tenancy.selectors.monthly_revenue_target() -> Decimal | None

    a NUMERIC(18,6) in the tenant's own CHAR(3) (CLAUDE.md rule 2), whole-tenant
    and not per-service unless the PO rules otherwise. **Four questions the PO's
    signature explicitly does NOT cover** and which the owning lane must put to
    them rather than decide: where in Settings the field lives, who may edit it,
    whether it is per-service or whole-tenant, and what a mid-month edit does.
    """
    found = resolve(TENANCY_MODULE, "monthly_revenue_target", kind=TENANCY_KIND)
    return found() if found is not None else None


# ── tenancy — THE SUBSCRIPTION'S CONNECTION ALLOWANCE (DARK) ───────────────
def current_subscription() -> dict[str, Any] | None:
    """DARK. r10's *"of 1,000 plan · Growth"* sub-line on Active connections.

    Derivable in principle — `subscriptions.plan_id → subscription_plans` holds
    `max_accounts` and the plan's name — and derivable ONLY by tenancy: those are
    its tables, `subscription_plans` is RLS-exempt platform data (B2 §3), and
    reports reaching into either would be a cross-module read B1 forbids and G6
    greps for. The read wanted, by name:

        apps.tenancy.selectors.current_subscription()
            -> {"plan_code", "plan_name", "max_accounts"} | None

    Until it exists the sub-line is absent rather than invented. It costs
    nothing today in any case: the Active-connections FIGURE itself refuses
    (BR-REP-012's classes are not published), and a plan allowance printed under
    a tile that has no count would be a denominator with no numerator.
    """
    found = resolve(TENANCY_MODULE, "current_subscription", kind=TENANCY_KIND)
    return found() if found is not None else None


# ── tenancy — THE ONBOARDING CHECKLIST (WIRED) ─────────────────────────────
def onboarding_checklist() -> dict[str, Any] | None:
    """S62's checklist, COMPUTED from live data at read time (BR-TEN-015).

    The PO's requirement for a brand-new tenant: *"New tenants show `—` KPIs
    with 'No billing history yet' and remaining onboarding steps in To do."*
    This is where those steps come from, and because the checklist is computed
    rather than stored, an item disappears from the dashboard the moment the
    work is done in the owning module — which is BR-REP-032's clearing rule
    satisfied by construction rather than by a job.
    """
    found = resolve(TENANCY_MODULE, "checklist", kind=TENANCY_KIND)
    return found() if found is not None else None


# ── the three to-do owners that publish nothing yet (DARK) ─────────────────
def pending_rate_approvals() -> Any | None:
    """DARK. BR-REP-032's `review` kind — *"rate approval"*.

    Wanted: `apps.rating.selectors.pending_approval_count() -> int | None`.
    Rating owns what "pending approval" means (BR-RAT-*), and counting draft
    schedules from here would be reports deciding a rating lifecycle question.
    """
    found = resolve("rating", "pending_approval_count", kind="selectors")
    return found() if found is not None else None


def disconnect_eligible_count() -> Any | None:
    """DARK. BR-REP-032's second `review` — *"disconnect eligibility"*.

    Wanted: `apps.customers.selectors.disconnect_eligible_count() -> int | None`.
    Eligibility is A15's rule set — arrears, the medical hold, the collection
    tier — and it is emphatically not "balance > 0", which is the number a
    dashboard would reach for. **A wrong count here proposes disconnecting a
    household**, which is why it refuses rather than approximates.
    """
    found = resolve(CUSTOMERS_MODULE, "disconnect_eligible_count", kind=CUSTOMERS_KIND)
    return found() if found is not None else None


def open_finance_close() -> Any | None:
    """DARK. BR-REP-032's `draft` kind — *"finance close"*.

    Wanted: `apps.ledger.selectors.open_close_period() -> dict | None` naming the
    period a close is outstanding for. The ledger owns period state (BR-TEN-023/
    038) and a dashboard that decided a month was "still open" would be a second
    opinion on the one fact a finance officer plans their week around.
    """
    found = resolve(LEDGER_MODULE, "open_close_period", kind="selectors")
    return found() if found is not None else None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-REP-019@f9ccd14 (story+rules snapshot — 04-docs/05-modules/12-reports/06-epics/EP-REP-05-dashboards.md §US-REP-019 · 12-reports/02-business-rules.md BR-REP-001/002/012/024 · 05-prototype/UtilityBilling.html lines 653-711 · 04-docs/01-spec/11-api-contracts.md S7 row)
# screens: S7   (DEF-137's screen-id stamp — see 10-scripts/gates/g25_screen_coverage.py)
# generated: 2026-08-16 by story-coder (DEF-129 lane — the first screen after every sign-in did not exist) · AMENDED 2026-08-19 by story-coder (CR-012 closing lane — `enabled_service_codes`, the tenancy read that decides which service rows DSH-01 draws)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_us_rep_019_dashboard.py could not import `apps.reports.dashboard_seams` before this file existed. ruff✔ black✔ pytest✔ run_gates✔
# exceptions: (1) THREE DOCUMENTED SEAMS ARE DARK — `metering.selectors.unbilled_read_rollup`, `customers.selectors.account_status_class_counts`, `payments.summary.failed_payment_count`. Each is parked in 10-scripts/gates/seam_known_gaps.txt as `reports-absent guard=none`, and every one of the three has a plausible substitute available in the same module that is deliberately NOT used: the read list, the account total, and the fifty-row failed list. Substituting any of them is DEF-075's shape, so the tile refuses instead · (2) this file resolves `reporting`, `selectors` and `summary` rather than only `services`, because that is where these owners publish; the `kind` parameter is why DEF-035 (a seam pointing at the wrong file, returning None on every call for weeks) cannot recur silently here — a wrong kind is G20's never-parkable R1 · (3) no ORM, no arithmetic and no clock appear in this module at all
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
