# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-013 (S34 Outstandings: AR high→low, ageing KPIs, bulk
#           actions) · US-PAY-005 (the S32 Summary panels, computed over the
#           same read-model so the two screens can never disagree)
#           Screens: S34 · S32
# Rules:    BR-PAY-029 (S34: AR high→low, bulk actions reminder/notice/plan/
#           write-off) · BR-PAY-032 (days late = today − the OLDEST UNPAID
#           invoice's due date) · BR-PAY-021 (money POSTED by the due date is
#           not outstanding, even before it clears) · BR-PAY-015 (the autopay
#           column is enrolment + intent state — there is NO retry action) ·
#           BR-PAY-018 (bad address is a column and a filter) · BR-PAY-017 (the
#           collection tier and next-step date) · BR-CUS-015 (`accounts.balance`
#           is a CACHE — this list does not use it) · BR-REP-011 (DSO) ·
#           CLAUDE.md rule 1 (tenant scoping)
# Tests:    06-backend/tests/test_us_pay_013_outstandings.py
# Impacts:  apps/payments/api.py (GET /outstandings) ·
#           apps/payments/billing_seam.outstanding_positions (the balances) ·
#           apps/payments/ladder.py (sets the tier this list renders) ·
#           07-frontend/src/features/payments/PaymentsPage.tsx (S34 tab)
# ───────────────────────────────────────────────────────
"""S34 — every account that owes money, worst first.

BR-PAY-029, CONFIRMED: *"S34 Outstandings: AR high→low, bulk actions
(reminder/notice/plan/write-off)"*.

════════════════════════════════════════════════════════════════════════════
THE BALANCE IS COMPUTED FROM BILLS, NOT READ FROM `accounts.balance`
════════════════════════════════════════════════════════════════════════════
`accounts.balance` is customers' CACHED column and B2 says the ledger is the
truth (BR-CUS-015). A collections list driven off a cache chases people for
money they have already paid — which is the single most expensive defect a
utility can ship, because the customer receives the letter. Every figure here is
Σ(issued bill totals) − Σ(allocation rows), computed in two queries by
`billing_seam.outstanding_positions`.

That also gives BR-PAY-021 for free: money POSTED by the due date has written
its allocation rows, so the bill is settled and the row simply is not in the
list — no special case, no "exclude recent payments" clause (US-PAY-013 TC-3).

════════════════════════════════════════════════════════════════════════════
DAYS LATE, AND THE HONEST NULL
════════════════════════════════════════════════════════════════════════════
BR-PAY-032: *"Days late everywhere = today − the OLDEST UNPAID invoice's due
date"*. An unpaid bill with NO due date cannot be placed in time; its balance is
counted (the customer owes it) and it contributes to no ageing bucket, and the
list says so through `problems` rather than dropping it into 1–30 where it would
look like a fresh debt.

**THE AGEING BUCKETS ARE A2's FOUR** — 1–30 / 31–60 / 61–90 / 90+ — and an
account not yet past due sits in NONE of them. `current` is reported separately
so the KPI strip's tiles foot to the header total exactly (US-PAY-013 TC-1's
*"KPI strip bucket totals tie to the rows exactly"*).

════════════════════════════════════════════════════════════════════════════
WHAT THIS MODULE DOES NOT DO
════════════════════════════════════════════════════════════════════════════
  * **It writes nothing.** US-PAY-013 TC-6: the list is a read-model and every
    bulk action routes to its owning story — reminder/notice to US-PAY-015,
    plan to US-PAY-017, write-off to US-PAY-012. There is no mutation entry
    point in this file at all.
  * **There is no autopay RETRY.** BR-PAY-015 makes v1 capture-only, so the
    autopay column reports enrolment and intent state and offers no action. A2's
    "Retry autopay" row action is superseded and is not rendered.
  * **The DSO tile is served, and it is NOT computed here.** BR-REP-011 owns the
    formula and reports own the read; this module reports `dso_days: None` with
    the reason attached rather than inventing a second implementation of a
    finance figure (field-map P-1 resolved the FORMULA, not the ownership).
  * **The medical-hold column is not rendered from here.** The hold is a
    customers-owned clinical fact with no published selector, so it is reported
    as unavailable — the posture `notices.py` and `ladder.py` both take.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.db.models import Max

from core import tenancy as core_tenancy

from apps.payments import balance_rule, billing_seam, models
from apps.payments.collections_models import (
    LIVE_PLAN_STATUSES,
    AccountCollectionState,
    NoticeHistory,
    PaymentPlan,
)

ZERO = Decimal("0")

#: A2 §S34's four bands, and `current` for everything not yet past due. Ordered,
#: because the KPI strip renders them in this order and a dict's insertion order
#: is a weaker promise than a tuple.
BUCKET_CURRENT = "current"
BUCKET_1_30 = "1-30"
BUCKET_31_60 = "31-60"
BUCKET_61_90 = "61-90"
BUCKET_90_PLUS = "90+"
AGEING_BUCKETS: tuple[str, ...] = (
    BUCKET_CURRENT,
    BUCKET_1_30,
    BUCKET_31_60,
    BUCKET_61_90,
    BUCKET_90_PLUS,
)

#: The SAME bands, in the shape the SQL `CASE` needs (`CR-138-BRC07` `P4.1`).
#: ⚠ Built FROM the names above rather than beside them: two lists of the same
#: five bands is how a tile and a row start disagreeing about what "61-90"
#: means, and `test_cr138_p41_outstandings_sql.py` asserts this agrees with
#: `bucket_for` on every boundary day.
AGEING_BANDS = billing_seam.AgeingBands(
    current=BUCKET_CURRENT,
    thresholds=((BUCKET_1_30, 30), (BUCKET_31_60, 60), (BUCKET_61_90, 90)),
    overflow=BUCKET_90_PLUS,
)

#: Carried on every result — a caller must not have to infer an absence.
OUTSTANDINGS_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "dso_not_computed_here",
        "br_ref": "BR-REP-011",
        "detail": "DSO = (AR ÷ billed last 12 months) × 365 on the posting basis (BR-REP-011). "
        "The formula is ratified and reports own the read; computing it here would be a second "
        "implementation of a finance figure, free to disagree with the one on S36. Served as "
        "null with this reason rather than as a number.",
    },
    {
        "code": "medical_hold_not_readable",
        "br_ref": "BR-CUS-039",
        "detail": "`apps/customers` publishes no medical-hold selector, so the A15 exclusion "
        "cannot be shown as a column here. It is passed IN to every send (`notices.py`, "
        "`ladder.py`) by the caller that knows it; inferring a clinical fact in this module "
        "would put it in the wrong place.",
    },
)


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def bucket_for(days_late: int | None) -> str:
    """A2 §S34's band for one age. `None` days late is CURRENT, never 90+.

    An account whose oldest unpaid bill is not yet due is current; so is one
    whose bills carry no due date, and the list reports the second case through
    `problems` rather than ageing it on a date it does not have.
    """
    if days_late is None or days_late <= 0:
        return BUCKET_CURRENT
    if days_late <= 30:
        return BUCKET_1_30
    if days_late <= 60:
        return BUCKET_31_60
    if days_late <= 90:
        return BUCKET_61_90
    return BUCKET_90_PLUS


@dataclass(frozen=True)
class OutstandingRow:
    """One S34 row (A2 §S34's column set)."""

    account_id: str
    account_no: str | None
    customer_name: str | None
    balance: Decimal
    days_late: int | None
    bucket: str
    open_bills: int
    last_payment_on: Any = None
    notice_summary: str | None = None
    collection_tier: str | None = None
    next_step_due: Any = None
    plan_status: str | None = None
    autopay: bool = False
    bad_address: bool = False
    # ── CR-059 CS-38 · task 25 ──────────────────────────────────────────────
    # ⛔ **`balance` HAS BEEN NET OF THE ACCOUNT'S CREDIT SINCE 2026-09-02 AND
    # THIS ROW DROPPED BOTH HALVES ON THE FLOOR.** `billing_seam` carries
    # `gross_balance` and `credit_applied` and says in its own docstring why —
    # *"a clerk asked why a notice says 222.30 when the bill says 247.30 needs
    # the two halves and not a subtraction they have to guess at"* — and this
    # read model took `position.balance` and nothing else. So a 25.00 goodwill
    # concession, posted to the books and WRITTEN TO THE CUSTOMER, moved the
    # figure on this screen and was invisible on it: the row read 222.30 with
    # no way to tell that from a bill of 222.30. Hard-won law 2, on a field
    # rather than a component.
    #
    # `gross_balance` is None on a deployment whose seam predates the change,
    # and None is NOT `balance`: "we do not know what the bills alone said" and
    # "the bills said exactly this" are different answers (DEF-127).
    gross_balance: Decimal | None = None
    credit_applied: Decimal = ZERO

    def as_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "account_no": self.account_no,
            "customer_name": self.customer_name,
            # Money on the wire carries FOUR decimals and the screen shows two —
            # `MoneyCell` is the single formatter and nothing here rounds.
            "balance": f"{self.balance:.4f}",
            "days_late": self.days_late,
            "bucket": self.bucket,
            "open_bills": self.open_bills,
            "last_payment_on": self.last_payment_on.isoformat()
            if self.last_payment_on is not None
            else None,
            # CS-38 — the two halves of the figure above, so a screen can say
            # WHY it is not the bill total. Four decimals like every other money
            # figure here, and `gross_balance` stays null when the seam could
            # not state it rather than echoing `balance` back.
            "gross_balance": (
                None if self.gross_balance is None else f"{self.gross_balance:.4f}"
            ),
            "credit_applied": f"{self.credit_applied:.4f}",
            "notice_summary": self.notice_summary,
            "collection_tier": self.collection_tier,
            "next_step_due": self.next_step_due.isoformat()
            if self.next_step_due is not None
            else None,
            "plan_status": self.plan_status,
            "autopay": self.autopay,
            "bad_address": self.bad_address,
        }


@dataclass(frozen=True)
class OutstandingsView:
    """S34's rows and its KPI strip, computed from the same rows.

    One computation, two renderings — US-PAY-013 TC-1 requires the tiles to tie
    to the list exactly, and the only way to guarantee that is for the tiles to
    be a fold over the rows rather than a second query.
    """

    rows: tuple[OutstandingRow, ...]
    as_of: date
    problems: tuple[dict[str, Any], ...] = OUTSTANDINGS_UNAVAILABLE
    # ⚠ **THE TILES AND THE TOTALS ARE THE WHOLE FILTERED SET, THE ROWS ARE ONE
    # PAGE OF IT (`CR-138-BRC07` `P4.1`).** US-PAY-013 TC-1 requires the KPI
    # strip to tie to the DEBT and not to the page, and the reason this list
    # stayed unpaginated for five weeks was the belief that a fold over the
    # rows was the only way to guarantee that. It is not — both are SQL
    # aggregates over the same filtered set, computed in one statement — and
    # `test_cr138_p41_outstandings_sql.py` asserts page 1's tiles equal the
    # tiles of every page summed.
    ageing_totals: dict[str, tuple[Decimal, int]] = field(default_factory=dict)
    total_accounts: int = 0
    total_owed_all: Decimal = ZERO
    page: int = 1
    #: ⚠ **`None` MEANS THE CALLER ASKED FOR NO PAGE AND GOT THE WHOLE
    #: FILTERED LIST.** It is not a cap of any kind (`NFR-5`); it is the
    #: absence of a window, and the body says so rather than inventing a
    #: number. `outstanding_positions_page` explains which callers do that
    #: and why screen 7·1 is still one of them.
    per: int | None = 50

    @property
    def total_owed(self) -> Decimal:
        """What the WHOLE filtered list owes — never this page's sum."""
        return self.total_owed_all

    def ageing(self) -> list[dict[str, Any]]:
        """Per-bucket $, account count and share — A2's KPI strip."""
        total = self.total_owed
        out = []
        for bucket in AGEING_BUCKETS:
            amount, accounts = self.ageing_totals.get(bucket, (ZERO, 0))
            out.append(
                {
                    "bucket": bucket,
                    "amount": f"{amount:.4f}",
                    "accounts": accounts,
                    # A share of nothing is not 0% — it is undefined, and a tile
                    # reading "0%" when a utility has no debtors is a claim.
                    "share": (
                        f"{(amount / total * 100):.1f}" if total > ZERO else None
                    ),
                }
            )
        return out

    def as_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of.isoformat(),
            "rows": [row.as_dict() for row in self.rows],
            # ⚠ **THE PAGE FACTS ARE NESTED, AND THAT IS A RULE RATHER THAN A
            # STYLE.** `G114` fails a reply that declares `rows` beside a
            # top-level `per`/`pages`: those are the SELECTOR's page dict, and
            # a body that carries both reads as the standard list envelope
            # `{count, next, previous, results}` when it is not one — this
            # read also carries `totals`, `ageing` and `problems`, which that
            # envelope has no room for. `<key>_window` is the shape A11 r7
            # already uses for the asset reads, for the same reason.
            "debtors_window": {
                "page": self.page,
                # `null` when no page was asked for — a page size the caller
                # did not choose must not be reported as one it did.
                "per": self.per,
                # `NFR-3`: the caller is told how many rows exist, so a pager
                # can exist at all. `NFR-5`: it is a COUNT, never a cap.
                "count": self.total_accounts,
                "pages": 1 if self.per is None else max(1, -(-self.total_accounts // self.per)),
            },
            "totals": {
                "accounts": self.total_accounts,
                "owed": f"{self.total_owed:.4f}",
                # BR-REP-011's figure, deliberately null — see the module
                # docstring and `OUTSTANDINGS_UNAVAILABLE`.
                "dso_days": None,
            },
            "ageing": self.ageing(),
            "problems": [dict(problem) for problem in self.problems],
        }


def outstandings(
    *,
    as_of: date,
    bucket: str | None = None,
    bad_address_only: bool = False,
    account_ids: Any = None,
    page: int = 1,
    per: int | None = 50,
    sort: str = "balance",
    direction: str = "desc",
) -> OutstandingsView:
    """ONE PAGE of the accounts that owe money, filtered, sorted and paged in SQL.

    `as_of` is an argument and never a clock (BR-TEN-043): the ageing a clerk
    sees at 23:58 and the ageing a job takes at 00:02 must be explainable, and a
    function that read the system date could not be asked for yesterday's.

    ════════════════════════════════════════════════════════════════════════
    THIS WAS UNPAGINATED AND SORTED IN PYTHON UNTIL `CR-138-BRC07` `P4.1`
    ════════════════════════════════════════════════════════════════════════
    `CLAUDE.md` named it on its first page — *"Unpaginated ON PURPOSE … one row
    per DEBTOR at a utility under 3,000 connections"*, and it **sorted in
    Python, not SQL** — and called it *"correct at T7, 13× short of T5"*
    (`DEF-PAY-4221`). The ICP's ceiling moved from 3,000 accounts to 40,000 on
    2026-09-06 and this read did not.

    ⚠ **AT THE TOP OF THE ICP IT DID NOT ANSWER AT ALL, WHICH IS THE PART
    NOBODY HAD MEASURED.** On real PostgreSQL 16, one page of fifty
    (`10-scripts/cr138_p4_debtor_cost.py`, median of 3 after a discarded
    warm-up, 2026-09-23):

        2,046 debtors    before   3.089 s ·  2,041 statements · 2,030 rows
                         after    0.232 s ·     13 statements ·    50 rows
        40,046 debtors   before  61.539 s · 40,041 statements · 40,030 rows
                         after    3.746 s ·     12 statements ·    50 rows

    A web worker is given **60 seconds** (`docker-entrypoint.sh`,
    `GUNICORN_TIMEOUT:-60`). **61.539 s is past it**, so at the ICP's own
    ceiling this screen was not slow, it was killed — and 2,046 debtors is
    two thirds of the OLD 3,000 ceiling, so three seconds of pure server time
    was already being spent inside the tier the docstring called correct.

    **Two faults, not one:** the seam materialised every open bill of the
    tenant, AND this function drew the Name cell one query per debtor —
    `primary_contact_names_for` has existed since `DEF-2723` and nothing here
    called it.

    ⚠ **`NFR-5` — PAGED, NEVER CAPPED.** There is no maximum row count and no
    per-tenant ceiling: `per` clamps to `core.pagination.PAGE_SIZES` like every
    other list, and the last page of a 40,000-row list is served like the first.

    ⚠⚠ **`per=None` ASKS FOR NO PAGE AT ALL AND IS THE DEFAULT THE ENDPOINT
    STILL USES — `DEF-PAY-4221` IS NOT CLOSED.** Screen 7·1 declares ten
    sortable columns, a search over account number and customer name and four
    filters; this read honours three sorts and two filters, because the rest
    live on customers' and on the collection-state and plan tables a
    billing-composed queryset does not join. A page cut underneath those
    controls is a search box that searches fifty rows of forty thousand —
    worse than the breach. `DEF-PAY-6271` sizes the join; `apps/payments/
    api.py` carries the reasoning at the call site so a reader meets it where
    the decision is taken.

    ⚠ **THE TILES STILL FOOT TO THE DEBT (US-PAY-013 TC-1).** They are a SQL
    aggregate over the whole filtered set rather than a fold over the page —
    which is what the old docstring said a paginated body could not do, and it
    was the one claim in it that was simply untested.
    """
    view = billing_seam.outstanding_positions_page(
        as_of=as_of,
        bands=AGEING_BANDS,
        bucket=bucket,
        bad_address_only=bad_address_only,
        account_ids=account_ids,
        page=page,
        per=per,
        sort=sort,
        direction=direction,
    )
    positions = view.positions
    if not positions:
        return OutstandingsView(
            rows=(),
            as_of=as_of,
            problems=OUTSTANDINGS_UNAVAILABLE + tuple(view.problems),
            ageing_totals=view.ageing,
            total_accounts=view.total_accounts,
            total_owed_all=view.total_owed,
            page=view.page,
            per=per,
        )

    # Every read below is batched over the PAGE — fifty ids, not the tenant.
    ids = [position.account_id for position in positions]
    accounts = _accounts_by_id(ids)
    names = _customer_names(ids)
    last_payments = {
        row["account_id"]: row["last"]
        for row in models.Payment.objects.filter(tenant_id=_tenant_id(), account_id__in=ids)
        .filter(status__in=balance_rule.RECEIPT_STATUSES)  # CR-186-BRC10: a receipt that stands
        .values("account_id")
        .annotate(last=Max("posted_at"))
    }
    states = {
        state.account_id: state
        for state in AccountCollectionState.objects.filter(
            tenant_id=_tenant_id(), account_id__in=ids
        )
    }
    plans = {
        plan.account_id: plan.status
        for plan in PaymentPlan.objects.filter(
            tenant_id=_tenant_id(), account_id__in=ids, status__in=LIVE_PLAN_STATUSES
        )
    }
    # ⚠ **THE STORED FLAG, NOT THIS MODULE'S RETURN EVENTS (`DEF-PAY-6342`).**
    # The account page reads `accounts.bad_address`; this cell derived its own
    # answer from unresolved returns, so the two screens could disagree about
    # one customer. `accounts` rows for the page are already in hand from
    # customers' own queryset, so this costs no statement at all.
    flagged = {pk for pk, account in accounts.items() if getattr(account, "bad_address", False)}
    notice_counts = _notice_summaries(ids)

    rows: list[OutstandingRow] = []
    for position in positions:
        days_late = (
            (as_of - position.oldest_due_on).days if position.oldest_due_on is not None else None
        )
        account = accounts.get(position.account_id)
        state = states.get(position.account_id)
        last = last_payments.get(position.account_id)
        rows.append(
            OutstandingRow(
                account_id=str(position.account_id),
                account_no=getattr(account, "account_no", None),
                customer_name=names.get(str(position.account_id)),
                balance=position.balance,
                days_late=days_late,
                # The band is decided in SQL so that the FILTER and the tiles
                # can be; `bucket_for` is still the one statement of the rule
                # and a test asserts the two agree on every boundary day.
                bucket=bucket_for(days_late),
                open_bills=position.invoice_count,
                last_payment_on=last.date() if last is not None else None,
                notice_summary=notice_counts.get(position.account_id),
                collection_tier=state.tier if state else None,
                next_step_due=state.next_step_due if state else None,
                plan_status=plans.get(position.account_id),
                # Carried, never recomputed: the subtraction is the seam's and a
                # second one here would be a second place it can drift.
                gross_balance=position.gross_balance,
                credit_applied=position.credit_applied,
                # BR-PAY-015: enrolment state only. There is no retry action
                # anywhere on this screen and none exists to call.
                autopay=bool(getattr(account, "autopay", False)),
                bad_address=position.account_id in flagged,
            )
        )

    # ⚠ **NOTHING SORTS HERE ANY MORE.** BR-PAY-029's balance high→low is an
    # `ORDER BY` in the statement above; a `rows.sort` would re-order a page
    # that was already cut, which is the exact shape of `DEF-PAY-4221`.
    return OutstandingsView(
        rows=tuple(rows),
        as_of=as_of,
        problems=OUTSTANDINGS_UNAVAILABLE + tuple(view.problems),
        ageing_totals=view.ageing,
        total_accounts=view.total_accounts,
        total_owed_all=view.total_owed,
        # The page SERVED, which BR-SHL-011 clamps into range — never the page
        # asked for, or a client that overshoots is told it is on page 9,999.
        page=view.page,
        per=per,
    )


def _accounts_by_id(ids: list[Any]) -> dict[Any, Any]:
    """Account rows through customers' OWN published queryset (B1/BR-TEN-013).

    No customers model is imported and no ORM of theirs is walked — the read is
    resolved by name, exactly as `billing_seam` resolves billing's.
    """
    queryset = _resolve("customers", "account_queryset")
    if queryset is None:  # pragma: no cover - customers publishes it
        return {}
    return {account.pk: account for account in queryset().filter(pk__in=ids)}


def _customer_name(account: Any) -> str | None:
    """ONE account's contact name. Kept for callers outside the list.

    ⚠ **THE LIST DOES NOT USE THIS AND MUST NOT GO BACK TO IT** — see
    `_customer_names`. It is the singular, and a singular called in a loop is
    what `DEF-2723` cost the accounts list and what `P4.1` cost this one.
    """
    if account is None:
        return None
    read = _resolve("customers", "primary_contact_name")
    if read is None:  # pragma: no cover - customers publishes it
        return None
    return read(account)


def _customer_names(ids: list[Any]) -> dict[str, str | None]:
    """A PAGE's contact names — one query, through customers' own batched read.

    ⛔ **THIS LIST CALLED THE SINGULAR ONCE PER ROW UNTIL `CR-138-BRC07`
    `P4.1`.** `primary_contact_names_for` has been published since `DEF-2723`
    closed exactly this defect on the accounts list, and nothing here called
    it: at 2,046 debtors that was 2,030 round trips for one column, and it is
    most of why the read made 2,041 statements to serve one screen.

    Falls back to the singular per account when customers publishes no batched
    read, because a Name column that silently emptied would be worse than a
    slow one — and it says so here rather than in a comment somewhere else.
    """
    if not ids:
        return {}
    batched = _resolve("customers", "primary_contact_names_for")
    if batched is not None:
        return {str(key): value for key, value in batched(ids).items()}
    accounts = _accounts_by_id(ids)  # pragma: no cover - customers publishes it
    return {str(key): _customer_name(account) for key, account in accounts.items()}


def _notice_summaries(ids: list[Any]) -> dict[Any, str]:
    """A2 §S34's "Notice history" cell — e.g. *"1st + 2nd sent"*.

    Built from `notice_history` SENDS only. A skip is in the trail (J4 step 2
    requires it) and is not a notice the customer received, so it does not
    appear in a column that answers *"what have we told them?"*.
    """
    summaries: dict[Any, list[str]] = {}
    rows = (
        NoticeHistory.objects.filter(tenant_id=_tenant_id(), account_id__in=ids, outcome="sent")
        .exclude(tier=None)
        .values("account_id", "tier")
        .distinct()
    )
    for row in rows:
        summaries.setdefault(row["account_id"], []).append(row["tier"])
    return {
        account_id: " + ".join(sorted(set(tiers))) + " sent"
        for account_id, tiers in summaries.items()
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-013@3c9f5a1 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/08-payments/06-epics/EP-PAY-04-outstandings-collections.md US-PAY-013 · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-029/032/021 · 04-docs/05-modules/08-payments/03-field-map.md §4 · 04-docs/01-spec/02-data-dictionary.md §S34 · 08-qa/01-e2e/journeys/J4-collections.md)
# generated: 2026-08-15 by story-coder (payments visible-half lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_pay_013_outstandings.py (the balance-desc order and the bucket tie-out were driven RED first) · pytest tests -m isolation✔
# exceptions: (1) THE BALANCE IS COMPUTED, NEVER `accounts.balance` — that column is customers' CACHE (BR-CUS-015) and a ladder driven off a cache posts letters to people who have paid
#         (2) NO DSO FIGURE. BR-REP-011 ratifies the formula and reports own the read; served as null with the reason rather than as a second implementation of a finance number
#         (3) NO MEDICAL-HOLD COLUMN — `apps/customers` publishes no selector for it; reported, and the exclusion is applied where the sends happen
#         (4) THIS MODULE WRITES NOTHING (US-PAY-013 TC-6). Every bulk action routes to its owning story and there is no mutation entry point in the file
#         (5) NO CSV EXPORT — `POST /exports` registers no `outstandings` resource (BR-SHL-010). REPORTED, not stubbed
#         (6) ⛔ **RETIRED 2026-09-23 BY `CR-138-BRC07` `P4.1`, AND `CLAUDE.md` QUOTED THIS EXACT SENTENCE AS THE `NFR-3` BREACH IT NAMES BY NAME (`DEF-PAY-4221`).** It read: *"SORTING HAPPENS IN PYTHON, not SQL: the balance is a figure across two modules' tables and no column holds it. At this product's ceiling (<3,000 connections) the list is bounded by the debtor count"*. **Both halves were wrong.** The balance IS expressible in SQL — billing publishes `amount_due_expression` and `open_invoice_amounts_queryset`, so the whole computation groups in one statement — and the ceiling moved 3,000 → 40,000 on 2026-09-06. Measured before it was retired: at 40,046 debtors the unpaged read took **61.539 s** against a **60-second** worker timeout, so *"bounded by the debtor count"* meant *"does not load"*. Filter, band, sort, count and page are all SQL now
#         (7) THE COLLECTIONS BOARD THIS MODULE FEEDS IS STILL UNPAGED — `P4.2` removed its two N+1s (244,195 statements to 20 at 40,046 debtors) and `P4.9` owns the page. Named here so it is a stated absence rather than a silence
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
