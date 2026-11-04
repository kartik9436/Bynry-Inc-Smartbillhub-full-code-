# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-005 (chart of accounts — TC-1: *"Tenant provisioned →
#           seeded chart present (incl. AR + opening-clearing rows per r9 #3);
#           codes UNIQUE per tenant"*)   Screens: S56
# Rules:    BR-LED-015 (every chart change writes audit_log) · BR-TEN-012
#           (versioned fixture seeding: tenant-touched rows are never
#           overwritten) · BR-BIL-010 (the service → revenue GL attributes this
#           seed hands tenancy) · CLAUDE.md rule 1 (tenant scoping) · rule 7
#           (every money action audits) · PO ruling 2026-08-11 closing OQ-115
#           (the seeded pointer is a default the tenant may override — STANDS;
#           ⚠ its narrowing half, "a tenant is seeded only the revenue accounts
#           for the services it actually sells", is SUPERSEDED by CR-010 B-9,
#           PO 2026-08-17 verbatim "9 - A full ~40 accounts for every tenant,
#           as you said" — the FULL 33-row chart seeds for every tenant)
# Tests:    06-backend/tests/test_us_led_005_gl_designations.py
# Impacts:  apps/tenancy/services.py (calls this at provisioning through
#           apps/tenancy/seams.py — a cross-module WRITE would be forbidden,
#           so tenancy asks and this module writes) · apps/ledger/selectors.py
#           (reads what this seeds) · apps/ledger/tenancy_seam.py (the read of
#           WHICH services a tenant sells, which now decides what is seeded)
# ───────────────────────────────────────────────────────
"""ledger service layer — the ONLY write path into this module's tables (B1
boundary rule). Other modules call these functions; they never touch this
module's ORM directly.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this seeds the chart of accounts every
journal entry in the product will be posted against, and stamps the eleven GL
designations. AI-authored 2026-08-11 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

WHAT IS HERE: `seed_chart_of_accounts()` (US-LED-005 TC-1),
`ensure_service_revenue_accounts()` (the per-service half, PO 2026-08-11) and
the liveness probe tenancy validates a tenant's own GL override against. WHAT IS
NOT: the S56 chart CRUD (US-LED-005's write half), and the GL mapping SCREEN
(the PO placed configuration *"during GL code mapping in settings"*, which is a
frontend story in another lane).

⚠ **THE POSTING SERVICE IS NOT HERE EITHER, AND IT IS NO LONGER A STUB**
(amended 2026-08-11 — this paragraph used to call it one). It lives in
`apps/ledger/posting.py` and is the ONLY writer of `journal_entries` /
`journal_lines` (CLAUDE.md rule 5, now enforced by a trigger in
`migrations/0004_posting_guard.py`). Nothing in THIS module writes a journal
row; `_create_missing_accounts` below touches `ledger_accounts` only.

────────────────────────────────────────────────────────────────────────────
THE THREE RULES THE SEED OBEYS, AND WHY EACH ONE IS LOAD-BEARING
────────────────────────────────────────────────────────────────────────────
**1 · IT NEVER OVERWRITES A TENANT'S CHART.** US-LED-005 makes the chart
tenant-customizable: a utility may rename `1200 Accounts receivable` to `1150
Trade debtors`, move the `accounts_receivable` designation onto a different
account, or deactivate an account it does not use. A re-run of this function —
a re-provision, a repair script, a future migration that calls it — must leave
every one of those edits standing. So an account whose CODE already exists is
LEFT ALONE, entirely: not renamed, not re-typed, not re-designated. The pattern
is `apps/tenancy/services._seed_us_holidays`'s (insert-missing only, so a
renamed holiday keeps its label), applied to money.

**2 · IT NEVER FIGHTS THE UNIQUE INDEX.** At most one live account per tenant
may carry a designation (`uq_ledger_accounts_designation`). A tenant that
deactivated `1200` and moved `accounts_receivable` onto a new `1150` has a
chart where the code `1200` is free but the designation is not. A naive re-seed
would insert `1200` carrying `accounts_receivable` and hit an IntegrityError in
the middle of provisioning. So the designation is claimed only if it is
genuinely free, and the account is created WITHOUT one otherwise — the account
exists, the tenant's own pointer is untouched, and the summary says so
(`designations_already_placed`) rather than swallowing it.

**3 · IT SEEDS THE FULL CHART — ⚠ REVERSED 2026-08-18 (CR-010 B-9).** This rule
read *"IT SEEDS ONLY THE SERVICES THE TENANT SELLS"* under the PO's OQ-115
closure (2026-08-11, *"every Utility may not have all the services"*): Silver
Creek Water was seeded 4110/4115/4120 and NOT 4100/4105/4130/4140/4145/4150.
The PO reversed that on 2026-08-17 — CR-010 B-9, verbatim: *"9 - A full ~40
accounts for every tenant, as you said"*, with New mandate 4 alongside it
(*"more is better ; less is contraint"*). So the seed now plants EVERY row:
all 25 of `SEED_CHART` (4180 included) plus the 8 cost rows — **33 accounts
for every tenant**, whatever it sells. ⚠ **34 SINCE 2026-08-28**: the PO's
discount ruling adds **4300 Customer discounts (contra-revenue)** to
`SEED_CHART`, so the signed chart is 26 rows and the seed is 34. A tenant that wants fewer lines
deactivates rows on S56, which rule 1 already protects. No signed figure
moved; only which rows land.

Rules 1 and 2 together give the property the tests assert: **seed → re-point →
re-seed leaves the re-pointing intact.** Rule 1 covers a tenant's ACCOUNTS; the
tenant's SERVICE→ACCOUNT pointer is protected on tenancy's side, by
`apps/tenancy/services.update_tenant_service` writing it and nothing here ever
writing it back (`ensure_service_revenue_accounts` RETURNS ids, and the caller
only stores them when it is creating the service row for the first time).

────────────────────────────────────────────────────────────────────────────
THE ORDERING PROBLEM OLD RULE 3 CREATED — DISSOLVED 2026-08-18, KEPT ON RECORD
────────────────────────────────────────────────────────────────────────────
Under the narrowed seed (2026-08-11 → 2026-08-17) the chart depended on which
services the tenant sold and the services depended on the chart, so the
dependency was REMOVED: the seed wrote the shared rows, and
`ensure_service_revenue_accounts()` minted a service's accounts AT THE MOMENT
it was switched on, from both paths that switch one on (signup and the S8
toggle). **CR-010 B-9 dissolves the ordering problem** — the full seed knows
everything it needs with no service enabled — but the function's shape is KEPT,
deliberately:

  * `ensure_service_revenue_accounts()` stays the **lookup + top-up** path. On
    a freshly provisioned tenant it finds every account already seeded and
    creates nothing; on a tenant provisioned during the narrowing era it MINTS
    the account the narrowed seed never gave them, the day they enable the
    service. Hard-won law 4: a provisioning change never reaches a tenant that
    already has a chart, and this function is that tenant's repair door.
  * Both enablement paths still call it, so neither can drift from the other.

**Existing tenants keep every account they already have.** Nothing here deletes
or deactivates: a tenant provisioned under the narrowed seed grows a missing
account when it enables the service (above) or when a repair run re-seeds it —
`manage.py`'s seed path calls this same function, which now tops the chart up
to the full set.

⚠ **AND A REPAIR RUN IS NOT SOMETHING AN OPERATOR HAS TO REMEMBER — THIS
PARAGRAPH SAID *"nothing backfills either"* UNTIL 2026-09-23 AND IT HAD BEEN
OVERTAKEN (`DEF-LED-6223`).** `tenancy.services.seed_reference_data_for_tenant`
calls `seed_chart_of_accounts` UNCONDITIONALLY (CR-066 task A3), and
`tenancy.reference_sweep.sweep()` runs that door over **every tenant** —
`Tenant.objects.all()` — from `06-backend/docker-entrypoint.sh`, automatically,
after `migrate` (OQ-087, CLOSED 2026-08-10). So a chart row added to
`chart.SEED_CHART` DOES reach the tenants that already exist, at the next
deploy, insert-missing. Two things that does NOT change: a code the tenant
already holds is still left exactly as the tenant has it (rule 1), and a
designation the tenant has already claimed is still theirs (rule 2).

────────────────────────────────────────────────────────────────────────────
AUDIT (BR-LED-015 · CLAUDE.md rule 7)
────────────────────────────────────────────────────────────────────────────
One `ledger_account.created` row per account actually created — the same action
code US-LED-005 TC-2 names for a hand-added account, because a seeded account
and a typed one are the same kind of event to whoever reads the trail. The
seed writes nothing when it creates nothing, so a replayed provisioning does
not spray a second set of rows. `actor_user_id` is the provisioning owner when
tenancy passes an actor and NULL for a system run, which `core.audit` already
documents as "system job".
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.ledger import chart, models, selectors, tenancy_seam
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

#: "this argument was not supplied" — distinct from `None`, which MEANS clear it.
#: See `set_export_codes`, where conflating the two would wipe a Xero ref every
#: time somebody typed a QuickBooks one.
_UNSET = object()


def _tenant_id() -> UUID:
    """CLAUDE.md rule 1: no tenant table is touched without `app.tenant_id`.

    Refuses rather than defaulting. A seed that ran with no tenant context
    would either be blocked by RLS (Postgres) or write a chart belonging to
    nobody (SQLite) — neither is a thing to let happen quietly.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _live_designations(tenant_id: UUID) -> set[str]:
    """Designations already claimed by a LIVE account of this tenant.

    `deleted_at__isnull=True` matches `uq_ledger_accounts_designation` exactly —
    the constraint and this read have to agree on what "already taken" means or
    the seed either fights the index or silently skips a free slot.
    """
    return set(
        models.LedgerAccount.objects.filter(
            tenant_id=tenant_id, designation__isnull=False, deleted_at__isnull=True
        ).values_list("designation", flat=True)
    )


def _create_missing_accounts(
    tenant_id: UUID, rows: tuple[chart.SeedAccount, ...], actor: Any, source: str
) -> dict[str, Any]:
    """Insert the seed rows this tenant does not already have. Rules 1 and 2.

    `source` lands in the audit row so the trail distinguishes an account minted
    at signup from one minted the day a service was switched on — the same event
    to the reader, different stories about WHY it appeared.
    """
    existing_codes = set(
        models.LedgerAccount.objects.filter(tenant_id=tenant_id).values_list("code", flat=True)
    )
    # ⚠ **`CR-196-BRC10`, our judgment 5a (decision log 2026-10-29).** Since
    # the PO's ruling of that day a System Admin may RENUMBER a seeded account
    # — `4150` becomes the utility's own `0117-080-1000-0000-7127` — so the
    # code alone no longer says whether this tenant already holds the seeded
    # Solar account. The reference sweep runs this on every `migrate`, and
    # matched by code it would mint an EMPTY `4150 Solar` beside the renamed
    # one on the very next deploy. `seed_key` is the slot, set when the
    # account was seeded and never moved by a code edit; a held slot is
    # skipped exactly as a held code always was (rule 1).
    held_slots = set(
        models.LedgerAccount.objects.filter(
            tenant_id=tenant_id, seed_key__isnull=False
        ).values_list("seed_key", flat=True)
    )
    claimed = _live_designations(tenant_id)

    created: list[str] = []
    placed: list[str] = []
    deferred: list[str] = []
    for row in rows:
        if row.code in existing_codes or row.code in held_slots:
            continue  # rule 1: the tenant's chart is the tenant's (5a: by slot too)
        designation = row.designation
        if designation is not None and designation in claimed:
            deferred.append(designation)  # rule 2: their pointer, not ours
            designation = None
        account = models.LedgerAccount.objects.create(
            tenant_id=tenant_id,
            code=row.code,
            name=row.name,
            type=row.type,
            designation=designation,
            # CR-061 statement (1) — the chart HEADING travels with the row.
            # A tenant that renumbers this account keeps it (US-LED-005 rule 1),
            # which is the whole reason it is stored rather than derived from
            # the code (see the column's own comment on the model).
            category=row.category,
            # CR-196-BRC10 5a — the slot this account fills, for good.
            seed_key=row.code,
        )
        existing_codes.add(row.code)
        held_slots.add(row.code)
        created.append(row.code)
        if designation is not None:
            claimed.add(designation)
            placed.append(designation)
        # BR-LED-015 — a chart change, seeded or typed, is an audited event.
        core_audit.write_row(
            action="ledger_account.created",
            entity_type="ledger_account",
            entity_id=account.id,
            actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            after={
                "code": row.code,
                "name": row.name,
                "type": row.type,
                "designation": designation,
                "category": row.category,
                "source": source,
                # Judgment call 2 in chart.py: a row may exist on a PO ruling
                # while its finance re-sign (HUMAN-GUIDE §6) is still owed. The
                # trail says so at the moment the account is minted, because
                # that is the row a finance reviewer will be reading. Since the
                # 2026-08-18 re-sign every seeded row is `signed=True`, so this
                # records True for all of them — the mechanism is unchanged and
                # `tests/test_us_led_017_cost_chart.py` drives it from a
                # synthetic unsigned row so it cannot rot into a constant.
                "finance_signed": row.signed,
            },
        )

    return {
        "accounts_created": len(created),
        "codes_created": tuple(created),
        "designations_placed": tuple(placed),
        "designations_already_placed": tuple(deferred),
        "already_present": len(existing_codes & {row.code for row in rows}) - len(created),
    }


def _wanted_rows() -> tuple[chart.SeedAccount, ...]:
    """THE FULL CHART — every signed row, 4180, and the whole cost section.

    ⚠ **REWRITTEN 2026-08-18 (CR-010 B-9).** Until then this function took the
    tenant's enabled service codes and answered *shared rows + the rows of the
    services it sells* (OQ-115's narrowing, 2026-08-11). The PO reversed that —
    verbatim: *"9 - A full ~40 accounts for every tenant, as you said"* — so
    the answer is now unconditional: all rows of `SEED_CHART` plus the 8 of
    `COST_OF_SERVICE_CHART` — **33 accounts** until 2026-08-28 and **34** since,
    when the PO's discount ruling added 4300 — in chart order (the signed chart
    first in its own order, then the proposed cost ladder in its own — a stable
    order matters because `created_at` is what an audit reader scrolls).

    ⚠ **AMENDED 2026-08-18 — THE EIGHT COST ROWS AND 4180 ARE NOW SIGNED.**
    This said they were UNSIGNED (`signed=False`, BR-LED-037's section awaiting
    its finance re-sign and 4180 awaiting the one CR-010 B-8 named). The Product
    Owner finance re-signed all nine that day, having been shown their codes and
    names in plain English with no dollar figure attached to any of them, so
    every row of both tuples now carries `signed=True`. **The mechanism is
    untouched:** each row's own flag travels into its audit row as
    `finance_signed`, so the trail says at the moment an account is minted
    whether finance had signed it — which is the row a finance reviewer will be
    reading, and which is what a future unsigned row will need.

    ⚠ **AMENDED 2026-09-01 (CR-060 C15 · task T5) — 48 ACCOUNTS, NOT 34.**
    `chart.WIDENED_COST_CHART`'s fourteen rows join the answer: O&M splits into
    labour, materials and contract services; customer accounts, administrative
    & general and the utility's own taxes arrive. **Every one of the fourteen
    carries `signed=False`** and lands in `chart.PENDING_FINANCE_RE_SIGN_COST`,
    so the `finance_signed` flag this function's caller writes into each audit
    row says **False** for them and **True** for the other 34 — which is the
    mechanism above doing exactly what it was built for, on real rows again for
    the first time since the 2026-08-18 re-sign.

    ⚠ **AMENDED 2026-09-02 (CR-061 statement (1)) — 125 ACCOUNTS, NOT 58.**
    `chart.UTILITY_BOOKS_CHART`'s **67** rows join the answer: petty cash and
    the clearing accounts, inventory, utility plant, construction in progress,
    accumulated depreciation, payables, debt, grants, non-operating income,
    interfund transfers and net position. **Every one of the 67 carries
    `signed=False`** and lands in `chart.PENDING_FINANCE_RE_SIGN_BOOKS`, so the
    `finance_signed` flag this function's caller writes into each audit row says
    **False** for them and **True** for the 33 that finance has signed.

    They are places a utility records what THIS PRODUCT NEVER POSTS, reachable
    through the S57 manual journal entry — which is what the PO was doing when
    they reported, on 2026-09-01, *"I tried to assigned using existing code,
    they are not sufficiencnt"*.

    ⚠ **AMENDED 2026-09-02 (CR-060 T7f) — ONE MORE ROW.**
    `chart.PERIOD_MATCHING_CHART` joins the answer: **5700 Depreciation
    expense**, `signed=False` and in `chart.PENDING_FINANCE_RE_SIGN_MATCHING`.
    It is here because the PO's own 111-row reference chart carries four
    accumulated-depreciation accounts and nothing to charge against them, which
    is half a double entry — and C20 (*"post depreciation"*) cannot be built
    without the other half. **The two designations that change hands alongside
    it mint NO account:** `accrued_expenses` and `accumulated_depreciation` are
    placed on `2100` and `1730`, which this seed already creates, by
    `ensure_period_matching_accounts` below.
    """
    return (
        chart.SEED_CHART
        + chart.COST_OF_SERVICE_CHART
        + chart.WIDENED_COST_CHART
        + chart.UTILITY_BOOKS_CHART
        + chart.PERIOD_MATCHING_CHART
    )


def ensure_cost_category_account(category: str, actor: Any = None) -> Any:
    """The tenant's account for a cost CATEGORY, minted on first use if absent.

    ⚠ **THIS EXISTS BECAUSE OF HARD-WON LAW 4** (*"a template change never
    reaches a host that already has a `.env`"*), and CR-060's T5 is that law's
    exact shape: `seed_chart_of_accounts` runs at PROVISIONING and nowhere else,
    so a tenant provisioned before today would have got fourteen new categories
    in their picker and **no account in their chart to point any of them at.**
    The capture would refuse — correctly, and with a message telling them to
    pick an account that does not exist.

    **It is the lookup-and-top-up path `ensure_service_revenue_accounts`
    already uses**, and for the same stated reason (BR-LED-038's worked case:
    *"Silver Creek enables Gas on 2026-09-01 → 5140 is minted AT THAT MOMENT,
    not before"*). One function, called from the one place a category first
    needs its account, so a mint that only happens when a test calls the ledger
    directly cannot happen (hard-won law 2).

    **A DEACTIVATED ACCOUNT IS NOT RESURRECTED.** Rule 1 of the seed says the
    code stays the tenant's: `_create_missing_accounts` matches on code across
    ALL rows including deleted ones, so a tenant who retired 5510 keeps it
    retired and the capture asks them for an account instead. That is IS-1's
    deactivate-first posture and it is deliberate.

    Returns the live account or `None` — `None` for a code this chart does not
    name, and for a code the tenant has retired. The caller reports the absence;
    nothing here invents a code.
    """
    code = chart.COST_CATEGORY_ACCOUNTS.get(category)
    if code is None:
        return None
    tenant_id = _tenant_id()
    rows = tuple(
        row for row in chart.WIDENED_COST_CHART + chart.COST_OF_SERVICE_CHART if row.code == code
    )
    if rows:
        _create_missing_accounts(tenant_id, rows, actor, source="cost_category_first_use")
    return (
        models.LedgerAccount.objects.filter(
            tenant_id=tenant_id, code=code, type="expense", deleted_at__isnull=True
        )
        .order_by("code")
        .first()
    )


def ensure_period_matching_accounts(actor: Any = None) -> dict[str, str | None]:
    """The three pointers the month-end postings resolve through — CR-060 T7b/T7f.

    HUMAN-REVIEW-PENDING — this decides WHICH GL account two new postings land
    in, a CLAUDE.md 🔒 sensitive path. Row in
    `12-governance/09-human-review-ledger.md`.

    Returns `{designation: account id or None}` for `accrued_expenses`,
    `depreciation_expense` and `accumulated_depreciation`, having placed each on
    the tenant's chart if it was not already there.

    ⚠ **THIS EXISTS FOR HARD-WON LAW 4** — *"a template change never reaches a
    host that already has a `.env`"* — and it is the same shape
    `ensure_cost_category_account` above takes, for the same measured reason:
    a seed edit does not reach a tenant that already has a chart at the moment
    the code ships, so **every tenant that existed that day would have got two
    new postings and no account to put either side in.** The accrual would
    refuse, correctly, with a message telling a clerk to designate an account
    that is not on their chart.

    ⚠ **THIS SAID `seed_chart_of_accounts` RUNS "AT PROVISIONING AND NOWHERE
    ELSE" AND THAT IS NO LONGER TRUE (`DEF-LED-6223`, 2026-09-23).** The
    post-migrate reference sweep runs it for every tenant — see the module
    docstring above and `ensure_cash_over_short_account` below, which states the
    chain once with the files that make it true. The function is KEPT and its
    value is unchanged: it covers the window before the sweep runs, a sweep that
    FAILED for one tenant (BR-TEN-074 isolates and carries on), and — the part
    the sweep cannot do at all — PLACING a designation on an account that is
    already there.

    **THREE RULES, AND THE ORDER MATTERS.**

    1. **A designation the tenant has already claimed WINS and is never moved.**
       `_live_designations` is read first, exactly as `_create_missing_accounts`
       reads it, and `uq_ledger_accounts_designation` is the database half of
       the same promise. A utility that pointed `accrued_expenses` at their own
       `2050` keeps it, and re-running this changes nothing.
    2. **A designation with a PLACEMENT lands on the account that is already
       there** — `chart.PERIOD_MATCHING_PLACEMENTS`, `2100 Accrued expenses` and
       `1730 Accumulated depreciation — meters`. Both are `UTILITY_BOOKS_CHART`
       rows the PO ruled into existence on 2026-09-01/02, so minting a second
       accrued-expenses account beside `2100` would be CR-060 §4's *"a live
       account nothing consumes"* smell reproduced one row later.
       **AND THE NAME IS CHECKED, NOT ONLY THE CODE.** A tenant may renumber
       anything (US-LED-005 rule 1), so a `2100` that has been renamed *"Payroll
       clearing"* is somebody else's account and this leaves it alone rather
       than quietly making it the one every month-end accrual credits. That is
       the only place a code appears in this path at all, and it decides a SEED
       DEFAULT rather than resolving a posting — `chart.py`'s law about
       `code == "1200"` is about the latter, and the posting services below
       resolve by designation and never see a number.
    3. **A designation with no placement is MINTED** from
       `chart.PERIOD_MATCHING_CHART` — today that is `5700 Depreciation
       expense` alone, because the PO's 111-row reference chart has no
       depreciation expense account of any kind and C20 cannot post without one.

    **A `None` IN THE ANSWER IS A REAL STATE AND THE CALLER MUST REFUSE ON IT**,
    never substitute: it means the code is taken by an account that is somebody
    else's, and choosing a different one would put a month of cost somewhere
    nobody agreed to — which hard rule 4 leaves no way to move afterwards.
    """
    tenant_id = _tenant_id()
    claimed = _live_designations(tenant_id)
    placements = dict(chart.PERIOD_MATCHING_PLACEMENTS)
    mintable = {row.designation: row for row in chart.PERIOD_MATCHING_CHART}
    wanted = (
        chart.ACCRUED_EXPENSES,
        chart.DEPRECIATION_EXPENSE,
        chart.ACCUMULATED_DEPRECIATION,
    )
    # The names the placement rule expects to find, taken from the seed rows
    # rather than typed, so this and `chart.UTILITY_BOOKS_CHART` cannot drift.
    seed_names = {row.code: row.name for row in _wanted_rows()}

    answer: dict[str, str | None] = {}
    for designation in wanted:
        if designation in claimed:
            answer[designation] = selectors.gl_account_id_for_designation(designation)
            continue
        code = placements.get(designation)
        if code is not None:
            row = (
                models.LedgerAccount.objects.filter(
                    tenant_id=tenant_id,
                    code=code,
                    designation__isnull=True,
                    deleted_at__isnull=True,
                    name=seed_names.get(code, ""),
                )
                .order_by("code")
                .first()
            )
            if row is None:
                # Either that account is not on this tenant's chart, or it is
                # and it is not the account this rule means. Both are answered
                # the same way and for the same reason: this function does not
                # invent a home for somebody else's money.
                answer[designation] = None
                continue
            row.designation = designation
            row.save(update_fields=["designation", "updated_at"])
            claimed.add(designation)
            # BR-LED-015 — a chart change, seeded or typed, is an audited event.
            core_audit.write_row(
                action="ledger_account.designated",
                entity_type="ledger_account",
                entity_id=row.id,
                actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
                after={
                    "code": row.code,
                    "name": row.name,
                    "designation": designation,
                    "source": "period_matching_top_up",
                    "finance_signed": False,
                },
            )
            answer[designation] = str(row.id)
            continue
        seed_row = mintable.get(designation)
        if seed_row is None:  # pragma: no cover — the three are enumerated above
            answer[designation] = None
            continue
        _create_missing_accounts(
            tenant_id, (seed_row,), actor, source="period_matching_top_up"
        )
        answer[designation] = selectors.gl_account_id_for_designation(designation)
    return answer


def ensure_allowance_account(actor: Any = None) -> str | None:
    """`1290 Allowance for doubtful accounts`, minted on the day it is needed.

    HUMAN-REVIEW-PENDING — this decides WHICH GL account a month-end estimate
    and every subsequent write-off land in, a CLAUDE.md 🔒 sensitive path. Row in
    `12-governance/09-human-review-ledger.md`.

    Returns the account id, or the id it already had. Idempotent: a tenant that
    has already claimed `allowance_doubtful_accounts` — on `1290` or on a number
    of their own — keeps it, exactly as rule 1 of
    `ensure_period_matching_accounts` above.

    ⚠ **IT IS NOT IN THE PROVISIONING SEED AND THAT IS THE POINT, NOT AN
    OVERSIGHT.** Every other pointer in this file is topped up because a seed
    edit does not reach a tenant that already has a chart on the day it ships
    (hard-won law 4 — and see `DEF-LED-6223`: the post-migrate sweep closes that
    gap at the next deploy, which this docstring used to deny). This one has a
    SECOND reason and it is `chart.py` judgment 3 surviving
    the ruling that spent the first half of it: **an allowance account on a
    chart is an offer of an accounting policy**, and one of the three reasons
    the PO was shown before choosing to build this is that *most utilities under
    3,000 connections are not audited and never book one.* So the row appears
    when a tenant switches the policy on, and everyone else's chart stays at
    125 accounts.

    **CALLED FROM `apps/ledger/allowance.py` ONLY**, at the top of the estimate,
    for the same reason `accrue_unpaid_costs` calls its own top-up there: a
    posting that refuses because a pointer is missing is a posting a clerk
    cannot fix from the screen they are on.
    """
    tenant_id = _tenant_id()
    if chart.ALLOWANCE_DOUBTFUL_ACCOUNTS in _live_designations(tenant_id):
        return selectors.gl_account_id_for_designation(chart.ALLOWANCE_DOUBTFUL_ACCOUNTS)
    _create_missing_accounts(tenant_id, chart.ALLOWANCE_CHART, actor, source="allowance_top_up")
    return selectors.gl_account_id_for_designation(chart.ALLOWANCE_DOUBTFUL_ACCOUNTS)


def ensure_cash_over_short_account(actor: Any = None) -> str | None:
    """`6850 Cash over and short`, resolved — and minted if this tenant predates it.

    HUMAN-REVIEW-PENDING — this decides WHICH GL account every counted drawer
    difference lands in, a CLAUDE.md 🔒 sensitive path. Row in
    `12-governance/09-human-review-ledger.md`.

    Returns the account id, or the id it already had. Idempotent: a tenant that
    has already claimed `cash_over_short` — on `6850` or on a number of their
    own — keeps it, exactly as rule 1 of `ensure_period_matching_accounts`.

    **CR-136-BRC07 §3.3, PO ruling 2026-09-23:** *"A short writes a balanced
    pair to a cash over/short account the day it is declared. Needs one new
    account added to the chart"*. `P2.22` calls this at the top of the posting,
    for the same reason `accrue_unpaid_costs` and the allowance estimate call
    theirs: **a posting that refuses because a pointer is missing is a posting a
    clerk cannot fix from the screen they are on** — and the screen they are on
    is the one where they have just counted a bag of cash.

    ⚠ **UNLIKE `ensure_allowance_account`, THIS ROW *IS* IN THE PROVISIONING
    SEED**, so a tenant created from today resolves it before this function is
    ever called and the call creates nothing. What it exists for is the tenants
    that already exist, and the honest chain — measured on this branch rather
    than assumed — is worth writing down because two other docstrings in this
    file state the opposite:

      * `seed_chart_of_accounts` is NOT only run at provisioning any more.
        `tenancy.services.seed_reference_data_for_tenant` calls it
        unconditionally as a repair door (CR-066 task A3), and
        `tenancy.reference_sweep.sweep()` runs that door over **every tenant**
        — `Tenant.objects.all()` — from `06-backend/docker-entrypoint.sh`,
        automatically, after `migrate` (OQ-087, CLOSED 2026-08-10).
      * `_create_missing_accounts` is insert-missing (*"rule 1: the tenant's
        chart is the tenant's"*), so that sweep plants `6850` on every existing
        tenant and touches nothing they have renumbered, renamed or retired.

    **So the answer to *does an existing tenant get it* is YES, at the next
    deploy.** This function covers the two cases the sweep does not: a tenant
    whose sweep FAILED (BR-TEN-074 isolates a failure per tenant and carries
    on), and any window between a code deploy and the sweep completing. It is
    cheap — one indexed read when the pointer is already there.

    ⚠ **`None` IS A REAL STATE AND `P2.22` MUST REFUSE ON IT, never substitute
    another account.** It means a live account already holds the code `6850`
    under a different name and pointer — a tenant's own re-coded chart can do
    that — so this does not invent a home for somebody else's money. That is
    `ensure_period_matching_accounts`'s rule, and the reason is the same: hard
    rule 4 leaves nobody a way to move a journal line afterwards.
    """
    tenant_id = _tenant_id()
    if chart.CASH_OVER_SHORT in _live_designations(tenant_id):
        return selectors.gl_account_id_for_designation(chart.CASH_OVER_SHORT)
    _create_missing_accounts(
        tenant_id, chart.CASH_OVER_SHORT_CHART, actor, source="cash_over_short_top_up"
    )
    return selectors.gl_account_id_for_designation(chart.CASH_OVER_SHORT)


def seed_chart_of_accounts(actor: Any = None) -> dict[str, Any]:
    """US-LED-005 TC-1 — the seed chart, at provisioning, idempotent.

    Content is `apps/ledger/chart.py`: twenty-two rows transcribed from B5 line
    74 (❄️ finance-signed 2026-08-08), 4160/4170 (finance re-signed 2026-08-11),
    4180 (CR-010 B-8, unsigned pending re-sign) and the eight unsigned cost
    rows; the twelve designations are the PO's enumerations of 2026-08-11
    (OQ-110) and 2026-08-15 (OQ-142). Nothing is chosen here — this function is
    the mechanism, the chart file is the content, and US-LED-005 says in as
    many words that this story *"ships the mechanism, never the numbers"*.

    **WHAT LANDS: THE FULL CHART, 33 ACCOUNTS, FOR EVERY TENANT — ⚠ REVERSED
    2026-08-18 (CR-010 B-9).** This paragraph read *"the shared rows, plus the
    revenue rows of the services this tenant already sells"* under OQ-115's
    narrowing; the PO reversed it on 2026-08-17, verbatim: *"9 - A full ~40
    accounts for every tenant, as you said"*. A re-run for a live tenant tops
    the chart up to the full set without touching anything the tenant has
    (rules 1 and 2 stand unchanged), which is what makes a repair run a repair
    AND what upgrades a narrowing-era tenant when one is re-seeded.

    Returns a summary rather than None so a caller can report what landed:
    `accounts_created`, `designations_placed`, `designations_already_placed`
    (the tenant's own pointer won — see rule 2 in the module docstring),
    `already_present` (wanted codes left untouched) and `services_seeded`
    (kept for callers that report it: the services enabled at the time of this
    run — informational since B-9, no longer what decides the rows).
    """
    tenant_id = _tenant_id()
    services_seeded = tenancy_seam.enabled_service_codes()
    summary = _create_missing_accounts(tenant_id, _wanted_rows(), actor, source="provisioning_seed")
    return {**summary, "services_seeded": services_seeded}


def ensure_service_revenue_accounts(
    service_code: str, actor: Any = None
) -> tuple[str | None, str | None]:
    """Mint this service's revenue accounts if absent, then answer their ids.

    `(revenue_account_id, base_revenue_account_id)` — the pair tenancy stores on
    a brand-new `tenant_services` row (BR-BIL-010: revenue required, base
    OPTIONAL). This is the cross-module call that keeps tenancy out of the
    ledger's ORM (B1 / BR-TEN-013): tenancy asks, this module writes its own
    table, and the two uuids come back.

    **IT IS THE LOOKUP + TOP-UP PATH (CR-010 B-9 keeps it, by name).** Before
    OQ-115 every tenant was seeded every revenue account, so this only looked
    one up; under the narrowing (2026-08-11 → 2026-08-17) it MINTED the account
    the day a service was enabled; since B-9's full seed it finds every account
    already present on a NEW tenant and creates nothing — but the mint stays,
    because a tenant provisioned during the narrowing era has no 4140 and the
    day it enables Gas is still the day 4140 has to exist (hard-won law 4: the
    full seed never reached them). Both paths that enable a service, signup and
    the S8 toggle, call exactly this, which is what stops one of them working
    and the other silently storing NULL (hard-won law 2 — that defect had
    already happened once here, and the comment in `_apply_service_toggle`
    records it).

    It resolves by CODE, which is the only place in this module that is right:
    a code is the key only at the instant an account is seeded. **Every later
    read goes through `apps/ledger/selectors.py` and resolves by designation or
    by the service's own stored attribute — never by code.**

    `(None, None)` for a service no chart line names — none today, since all ten
    catalog services are mapped, but a service added to the catalog without a
    chart line would land here rather than in an invented account. `None` on
    either side also when the tenant has DEACTIVATED the account (IS-1): rule 1
    says the code stays theirs, so nothing resurrects it, and the caller stores
    the NULL for a human to fix on the GL mapping page.
    """
    pairing = chart.SERVICE_REVENUE_ACCOUNTS.get(service_code)
    tenant_id = _tenant_id()
    # ── the COST mirror is minted in the SAME breath (US-LED-017 TC-3) ───────
    # BR-LED-038's worked case: *"Silver Creek enables Gas on 2026-09-01 → 5140
    # is minted AT THAT MOMENT, not before"*. It rides this function and not a
    # second one for the reason the paragraph above gives about 4140: both paths
    # that enable a service call exactly this, and a mint that only happens when
    # a test calls the ledger directly is not a feature (hard-won law 2).
    #
    # It runs BEFORE the revenue early-return, deliberately. The two ladders do
    # not cover the same services — the revenue map has all ten catalog
    # services, the cost map has six — so a service with a cost mirror and no
    # revenue pairing (none today) must still get its cost account, and a
    # service with a revenue pairing and no cost mirror (solar, battery,
    # storm_water, thermal_heat) must still get its revenue accounts.
    cost_rows = chart.cost_rows_for_service(service_code)
    if cost_rows:
        _create_missing_accounts(tenant_id, cost_rows, actor, source="service_enabled")
    if pairing is None:
        return None, None
    _create_missing_accounts(
        tenant_id, chart.seed_rows_for_service(service_code), actor, source="service_enabled"
    )
    usage_code, base_code = pairing
    wanted = [code for code in (usage_code, base_code) if code is not None]
    by_code = {
        account.code: str(account.id)
        for account in models.LedgerAccount.objects.filter(
            tenant_id=tenant_id, code__in=wanted, deleted_at__isnull=True
        )
    }
    return by_code.get(usage_code), (by_code.get(base_code) if base_code else None)


#: The ONE shape this product issues inside the ❄️ signed 2200 series: the
#: series, a hyphen, digits. Deliberately narrower than `chart.is_tax_payable
#: _code`, which accepts anything in the series because a tenant may already
#: run `2200.TX` or `220017` from their accountant's chart (US-LED-005 rule 1).
#: Those are read as a tenant's own codes — they cannot collide with a
#: generated one and they do not move the allocator's high-water mark.
_GENERATED_TAX_CODE_RE = re.compile(rf"^{re.escape(chart.TAX_PAYABLE_SERIES)}-(\d+)$")

#: Zero-padded to two digits, so a tenant with three authorities reads
#: 2200-01/02/03 rather than 2200-1/2/3. Beyond 99 the format WIDENS
#: (`2200-100`) instead of wrapping, which is why the high-water mark is
#: compared as an integer and never as a string — see `_next_tax_payable_code`.
_GENERATED_TAX_CODE_FMT = chart.TAX_PAYABLE_SERIES + "-{:02d}"

#: How many times the allocator will lose the insert race before it gives up.
#: Bounded on purpose: if `uq_ledger_accounts_code` ever started firing for a
#: reason that is NOT contention, an unbounded retry would spin a worker
#: forever instead of surfacing. Twenty-five is far past any real number of
#: staff a <3,000-connection utility has (1–2, per the product brief).
_TAX_CODE_ALLOCATION_ATTEMPTS = 25


def _next_tax_payable_code(tenant_id: UUID) -> str:
    """The next 2200-nn code for THIS tenant — one above the highest ever used.

    ── THE GAP RULE (and it is a rule, not an implementation detail) ─────────
    **Monotonic. A gap stays a gap, forever.** The scan deliberately does NOT
    filter `deleted_at__isnull=True`: a deactivated 2200-02 still counts, so
    the number is retired with the authority rather than re-let. Two reasons,
    and the first one alone settles it:

      * `uq_ledger_accounts_code` is unconditional — it counts soft-deleted
        rows. "Lowest free live code" would therefore hand back 2200-02 and the
        INSERT would fail against a row the caller cannot even see. An
        allocator that walks into its own unique index is not an allocator.
      * A code that meant Harris County in March and the City of Katy in June
        makes every remittance report drawn before the reissue read wrong, and
        read wrong SILENTLY — the numbers still add up, they are just against
        the wrong authority. CLAUDE.md rule 4's reasoning applied to the chart:
        a code a journal line points at is part of a financial record.

    A gap the tenant never filled (they typed 2200-01 and 2200-04 by hand) is
    treated the same way: the next generated code is 2200-05. Backfilling would
    hand out the number a clerk deliberately skipped.

    ── WHAT THIS IS NOT ──────────────────────────────────────────────────────
    It is NOT the collision guarantee. This is a read, and any read-then-write
    allocator has a window between the two. The guarantee is the unique index;
    this function only proposes. See `create_tax_authority_account`.

    Tenant-filtered, so a busy tenant's numbering never pushes a quiet one's
    along and both may hold their own 2200-01 (CLAUDE.md rule 1).
    """
    highest = 0
    prefix = f"{chart.TAX_PAYABLE_SERIES}-"
    # ⚠ **`CR-196-BRC10` — THE KEY COUNTS AS WELL AS THE CODE.** A System Admin
    # may now rename `2200-04` to the utility's own number. Scanning codes only
    # would then answer `2200-04` again for the next authority — a re-let
    # number, which BR-LED-023 forbids — and the insert would also collide with
    # the renamed account's `seed_key` under `uq_ledger_accounts_seed_key`.
    for code, seed_key in models.LedgerAccount.objects.filter(
        Q(code__startswith=prefix) | Q(seed_key__startswith=prefix), tenant_id=tenant_id
    ).values_list("code", "seed_key"):
        for value in (code, seed_key):
            match = _GENERATED_TAX_CODE_RE.match(str(value or ""))
            if match is not None:
                # int(), never a string compare: '2200-9' > '2200-100' lexically.
                highest = max(highest, int(match.group(1)))
    return _GENERATED_TAX_CODE_FMT.format(highest + 1)


def create_tax_authority_account(
    *, code: str | None = None, name: str, actor: Any = None
) -> models.LedgerAccount:
    """Mint ONE 2200-series tax-payable account, because a tenant asked for one.

    ── THE RULE THIS IMPLEMENTS ──────────────────────────────────────────────
    B5 line 74, ❄️ FROZEN and finance-signed 2026-08-08: *"2200-series Tax
    payable per authority (tenant authorities mint their own)"*. And the PO,
    closing OQ-116 on 2026-08-11 (BR-BIL-069), verbatim: *"For each atheority
    have separate account and tagging; but also ensure you allow Use to manage
    it since every utility may not have every account."*

    Both halves are here. **PER AUTHORITY** — one account each, so the $8.30 of
    tax on a $117.01 bill accrues as State of Texas $6.29, Harris County $1.01
    and City of Katy $1.00 in three separate liabilities and the quarterly
    return to each is a query rather than a reconstruction. **MINTED BY THE
    TENANT** — this function is called because a human asked for an account,
    never from `seed_chart_of_accounts`, never from provisioning, and never from
    a fixture. `apps/ledger/chart.py` carries no 2200 row at all and that is the
    signed design, not an omission: seeding one would invent a tax authority no
    tenant created (BR-TEN-037).

    ── NO DESIGNATION, AND THAT IS A RULING ──────────────────────────────────
    The account carries `designation=None`. A single shared `tax_payable`
    designation was option C of OQ-116 and the PO declined it: it would need a
    TWELFTH designation against the eleven ruled on 2026-08-11 (OQ-110, which
    reserved nothing), and it would lose the per-authority split permanently —
    one bucket that has to be taken apart again at remittance time, from data
    that no longer says who it belonged to. Taxes resolve their account through
    `rating.taxes.liability_gl_account_id`, not through a designation.

    ── THE CODE IS GENERATED. THE TENANT DOES NOT TYPE IT (PO 2026-08-12) ────
    **This used to refuse.** Until 2026-08-12, OQ-147 was open and `code=None`
    raised a `NotImplementedError` citing it — because B5 line 74 fixes the
    SERIES and is silent on the two digits after it, and the prime directive
    forbids a lane choosing. The PO chose. Verbatim: *"Generated"*.

    So a tenant adds a tax authority and the product allocates the next code in
    the signed series — `2200-01`, `2200-02`, `2200-03` — rather than making
    somebody type one. It pairs with the same day's OQ-145 ruling: **the tenant
    CHOOSES which account a tax points at; where a new one is needed the product
    NUMBERS it.** Choosing and numbering are different acts, and a hand-typed
    code is how two authorities end up sharing one.

    Three properties, each of which is where this breaks if you get it wrong:

    **1 · THE DATABASE DECIDES THE WINNER, NOT THE READ.** Two clerks adding an
    authority in the same second both read the same high-water mark and both
    compute `2200-03`. `_next_tax_payable_code` cannot stop that and does not
    try — `uq_ledger_accounts_code`, the real UNIQUE index on (tenant, code)
    from ledger migration `0001`, is the guarantee. The INSERT is attempted
    inside a savepoint; the clerk who loses catches `IntegrityError`, re-reads
    and takes `2200-04`. A `SELECT max(...)` followed by an unguarded INSERT
    would have handed both clerks the same code, and the SECOND failure mode is
    the dangerous one: swallowing that error the way the tenant-typed path
    legitimately does would hand clerk B the account that already belongs to
    clerk A's authority, and their tax would remit into someone else's
    liability. That is why the generated path RETRIES where the supplied path
    RETURNS.

    **2 · A GAP IS NEVER RE-LET.** Allocation is monotonic: strictly above every
    `2200-nn` this tenant has ever held, live or DEACTIVATED. Deleting 2200-03
    does not free 2200-03. The full reasoning is in `_next_tax_payable_code`'s
    docstring; the short version is that the unique index counts soft-deleted
    rows, so "lowest free" is not merely unwise, it does not work.

    **3 · PER TENANT.** Two tenants each have their own `2200-01` (CLAUDE.md
    rule 1). The read is tenant-filtered and the constraint leads with `tenant`.

    ── WHAT IT STILL REFUSES, AND WHY THAT IS NOT A STYLE CHOICE ─────────────
    * **a code outside the 2200 series** → refused. That half IS signed, and the
      cost of getting it wrong is a tax liability filed under deposits or,
      worse, under revenue.
    * **NOTHING when a SUPPLIED code already exists.** The existing account is
      returned UNTOUCHED — not renamed, not re-typed. Rule 1 of this module: a
      tenant's chart is the tenant's, and this call is idempotent for the same
      reason `_create_missing_accounts` is. A GENERATED code never takes this
      path; see property 1 above.

    ── A SUPPLIED CODE IS STILL ACCEPTED, AND THAT IS A JUDGMENT CALL ────────
    The ruling settles who NUMBERS a NEW account, so `code=None` — what a caller
    passes when it wants an account and has no opinion about its number — is now
    the ruled path and the default. An explicit `code=` is still honoured,
    because a utility migrating an accountant's chart mapping an authority to an
    account they ALREADY run is OQ-145's half (the tenant chooses), not this
    one, and US-LED-005 rule 1 says their chart stays theirs. **No product
    surface passes a code today** — only tests and the E2E fixture do. If the PO
    wants the typed path gone entirely, deleting the parameter is a one-line
    change and this paragraph is the place it was flagged.

    ── WHAT IT DOES NOT DO ───────────────────────────────────────────────────
    It does not map the account to a tax. That write is RATING's
    (`taxes.liability_gl_account_id`, through `apps.rating.services.update_tax`,
    which validates the account through `account_is_live` below) — a cross-module
    write from here would be exactly the B1 violation this module exists to
    avoid. And **nothing calls this when a jurisdiction is created**: whether
    adding an authority should auto-mint its account is **OQ-145**, and is not
    this lane's to build. What is no longer true is the reason this paragraph
    used to give for that — *"it could not be built anyway until OQ-147 is
    answered"*. OQ-147 is answered; the code exists to mint one.

    Audited as `ledger_account.created`, the same action the seed and a
    hand-typed account write (BR-LED-015 / CLAUDE.md rule 7) — a tax-payable
    account is not a different KIND of event to whoever reads the trail.
    `source` says where it came from and `code_source` says WHO NUMBERED IT
    (`generated` / `tenant_supplied`), because after this ruling that is the
    first question anyone asks when two authorities look wrong.
    """
    if code is not None and not chart.is_tax_payable_code(code):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.chart.tax_account_wrong_series",
            params={"code": str(code), "series": chart.TAX_PAYABLE_SERIES},
        )
    tenant_id = _tenant_id()
    generated = code is None

    if not generated:
        # CR-196-BRC10 — `2200-02` may have been renamed since it was minted;
        # its key still names it, and minting a second would take its slot.
        existing = models.LedgerAccount.objects.filter(
            Q(code=code) | Q(seed_key=code), tenant_id=tenant_id
        ).first()
        if existing is not None:
            # Rule 1 — theirs, not ours. Answered, never rewritten.
            return existing

    account = None
    for _ in range(_TAX_CODE_ALLOCATION_ATTEMPTS):
        # Proposed OUTSIDE the savepoint below, so a rollback of a lost race
        # rolls back only this attempt's INSERT and the re-read that follows
        # sees whoever beat us to it.
        candidate = _next_tax_payable_code(tenant_id) if generated else str(code)
        try:
            with transaction.atomic():
                account = models.LedgerAccount.objects.create(
                    tenant_id=tenant_id,
                    code=candidate,
                    name=name,
                    type=chart.TAX_PAYABLE_TYPE,
                    # See the docstring: a twelfth designation was option C and
                    # was declined by the PO.
                    designation=None,
                    # CR-196-BRC10 5b — the number it was minted under is what
                    # keeps it a TAX account if a System Admin renumbers it.
                    seed_key=candidate,
                )
        except IntegrityError:
            if generated:
                # `uq_ledger_accounts_code` just told us another clerk took this
                # number. Re-read and take the next one — never return theirs.
                continue
            # A SUPPLIED code that appeared between the read above and this
            # INSERT is the same idempotent answer the read would have given.
            existing = models.LedgerAccount.objects.filter(
                Q(code=code) | Q(seed_key=code), tenant_id=tenant_id
            ).first()
            if existing is not None:
                return existing
            raise
        break
    if account is None:
        # Contention this deep is not contention. Fail loudly rather than spin.
        raise errors.SysError(errors.SYS_INTERNAL)

    core_audit.write_row(
        action="ledger_account.created",
        entity_type="ledger_account",
        entity_id=account.id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after={
            "code": account.code,
            "name": name,
            "type": chart.TAX_PAYABLE_TYPE,
            "designation": None,
            "source": "tax_authority",
            # PO 2026-08-12 (OQ-147) — choosing and numbering are different
            # acts, so the trail records which one happened.
            "code_source": "generated" if generated else "tenant_supplied",
            # B5 line 74 signs the 2200 series itself, so unlike 4160/4170 this
            # row needs no finance re-sign. The SUFFIX inside that series is the
            # product's to allocate as of the OQ-147 ruling, and B5 is silent on
            # it either way — so nothing here is claiming a finance signature
            # over the two digits.
            "finance_signed": True,
        },
    )
    return account


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-005's WRITE HALF — the S56 chart CRUD (added 2026-08-16)
# ═══════════════════════════════════════════════════════════════════════════
# This module's docstring said, from the day it was written until today: *"WHAT
# IS NOT: the S56 chart CRUD (US-LED-005's write half)"*. That sentence was
# accurate and it was also the whole defect — the chart is **tenant-
# customizable by design** (US-LED-005 §1: *"add accounts, edit names"*) and no
# human being could add, rename, re-point or retire one line of it. A utility
# that keeps its water revenue in an account of its own numbering had a seeded
# default and no way to change it.
#
# THE FOUR THINGS A HUMAN MAY DO TO A CHART LINE, AND THE ONE THEY MAY NOT
# ────────────────────────────────────────────────────────────────────────────
#   add          `create_account` — a code this tenant does not have
#   rename       `rename_account` — the NAME, always; `type` is frozen the
#                moment anything posts against the row. ⚠ `code` is NOT,
#                since 2026-10-29 (`CR-196-BRC10`): `change_account_code`, a
#                System Admin, even when used — see that function
#   re-point     `set_account_designation` — move `accounts_receivable` from
#                1200 to a 1150 the tenant made
#   retire       `deactivate_account` / `reactivate_account` (IS-1)
#   delete       `delete_account` — ONLY when nothing references it. An account
#                a journal line points at is part of a financial record and is
#                never removed (CLAUDE.md rule 4, IS-1 deactivate-first).
#
# ⚠ AMENDED 2026-10-29 (`CR-196-BRC10`, PO: *"we have to ability to change
# existing GL code as per the given utility … even if they are used"*): the
# CODE no longer freezes — every reference holds the account id, so a renamed
# code restates nothing but the label July's report prints, and the PO ruled
# that is wanted (Q1 A). What follows is the TYPE's reason and still holds; the
# tuple keeps both names only because nothing reads it at runtime.
# WHY `code` AND `type` FREEZE ONCE POSTED AGAINST, and why the name does not.
# US-LED-005 §1: *"its `code`/`type` are frozen once posted against — historical
# books are never restated"*. A trial balance printed in July says `4110 Water
# usage · revenue`; re-typing that row to `expense` in August would silently
# restate July's report the next time anybody opened it, because the Type
# column is read from the account and not stamped on the line. A NAME is a
# label and re-labelling is the tenant's own business — LE-1's own worked
# example renames `1200 Accounts receivable` to `Trade debtors` and every
# figure is unmoved, because code reads the DESIGNATION and never the number
# (chart.py's whole subject).
_CHART_FROZEN_ONCE_POSTED = ("code", "type")

AUDIT_ACCOUNT_CREATED = "ledger_account.created"
AUDIT_ACCOUNT_UPDATED = "ledger_account.updated"
AUDIT_ACCOUNT_DEACTIVATED = "ledger_account.deactivated"
AUDIT_ACCOUNT_REACTIVATED = "ledger_account.reactivated"
AUDIT_ACCOUNT_DELETED = "ledger_account.deleted"

#: The four kinds of thing that make an account UNDELETABLE, each named so a
#: refusal can say WHICH one held it rather than "in use". US-LED-005 §1 names
#: journal lines, GL mappings, charge codes and designations; the first, the
#: fourth and the service pointer are answerable inside this deployment, and
#: the two that are NOT are reported by name rather than assumed absent — an
#: unanswerable reference read as "no reference" is how an account backing a
#: charge code gets deleted (the DEF-127 shape: a zero that means "I don't
#: know").
REFERENCE_KINDS = ("journal_lines", "designation", "service_revenue", "supplier_invoices")

#: The reference reads this deployment CANNOT perform, published on every
#: refusal and on every row of the chart list. `charges.gl_account` is billing's
#: (BR-BIL-010's charge-code mapping) and no billing selector publishes a
#: reverse lookup from a ledger account to the charge codes pointing at it; a
#: cross-module ORM reach would be forbidden (B1/BR-TEN-013) and inventing the
#: answer would be worse than saying so.
UNANSWERABLE_REFERENCE_READS: tuple[dict[str, str], ...] = (
    {
        "code": "charge_code_references_are_not_readable_here",
        "br_ref": "BR-BIL-010",
        "wanted_read": "apps.billing.selectors.charge_codes_using_gl_account(account_id) -> tuple",
    },
    {
        "code": "tax_authority_references_are_not_readable_here",
        "br_ref": "BR-BIL-069",
        "wanted_read": "apps.rating.selectors.tax_authorities_using_gl_account(account_id) -> tuple",
    },
)


def _account_or_404(account_id: Any, *, include_deactivated: bool = False):
    """One of THIS tenant's chart rows, or a 404 that says nothing about whose.

    HR-1 / BR-TEN-003: another tenant's account is NOT FOUND, never FORBIDDEN —
    a 403 would confirm the row exists somewhere, which is the oracle the whole
    isolation posture exists to close.
    """
    query = models.LedgerAccount.objects.filter(tenant_id=_tenant_id(), pk=account_id)
    if not include_deactivated:
        query = query.filter(deleted_at__isnull=True)
    account = query.first()
    if account is None:
        raise errors.NotFoundError()
    return account


def account_references(account_id: Any) -> dict[str, Any]:
    """WHAT points at this account today — counted, per kind, never summed.

    Per kind and not as one total on purpose: *"3 references"* tells a clerk
    nothing they can act on, while *"14 journal lines and the water service's
    revenue pointer"* tells them exactly which two things to look at.

    ⚠ **`answerable` IS FALSE WHENEVER A KIND COULD NOT BE READ**, and a caller
    that treats an unanswerable read as zero is the defect this repo has
    already shipped once (DEF-127 — an account screen showed $0.00 while the
    ledger held an unpaid 108.88, because a cache nobody filled read as "owes
    nothing"). `delete_account` refuses outright when `answerable` is False.
    """
    tenant_id = _tenant_id()
    account = models.LedgerAccount.objects.filter(tenant_id=tenant_id, pk=account_id).first()
    if account is None:
        raise errors.NotFoundError()

    counts: dict[str, int] = {
        "journal_lines": models.JournalLine.objects.filter(
            tenant_id=tenant_id, ledger_account_id=account.pk
        ).count(),
        "designation": 1 if account.designation else 0,
        "supplier_invoices": models.SupplierInvoice.objects.filter(
            tenant_id=tenant_id, ledger_account_id=account.pk
        ).count(),
    }

    # The service pointer lives on tenancy's `tenant_services` row and is read
    # through the seam, never through tenancy's ORM (B1 / BR-TEN-013). A seam
    # that is not wired REFUSES rather than answering zero, so the whole read
    # goes unanswerable and the delete is refused — see the docstring.
    unanswerable = list(UNANSWERABLE_REFERENCE_READS)
    try:
        pointing_services = tuple(
            code
            for code in tenancy_seam.enabled_service_codes()
            for attributes in (tenancy_seam.service_gl_attributes(code) or {},)
            if str(account.pk)
            in {
                str(attributes.get("revenue_account_id") or ""),
                str(attributes.get("base_revenue_account_id") or ""),
            }
        )
        counts["service_revenue"] = len(pointing_services)
    except tenancy_seam.LedgerSeamNotWired:
        pointing_services = ()
        counts["service_revenue"] = 0
        unanswerable = [
            *unanswerable,
            {
                "code": "service_revenue_pointers_are_not_readable_here",
                "br_ref": "BR-BIL-010",
                "wanted_read": "apps.tenancy.selectors.service_gl_attributes(service_code) -> dict",
            },
        ]

    return {
        "account_id": str(account.pk),
        "counts": counts,
        "services": pointing_services,
        "referenced": any(counts.values()),
        # FALSE while any kind is unreadable — see the docstring.
        "answerable": not unanswerable,
        "unavailable": tuple(unanswerable),
    }


def _chart_row(account: models.LedgerAccount, references: dict[str, Any] | None = None):
    """One S56 chart line, with everything the panel's capability row needs.

    ⚠ **`CR-196-BRC10` — `finance_signed` AND `seeded` READ THE SEED SLOT, NOT
    THE CODE.** Both questions are about which SEED ROW this account is, and a
    System Admin may now renumber it. Read by code, a renamed unsigned account
    (`1105 Petty cash` → `0117-…`) would suddenly be served `finance_signed:
    true` — US-LED-017 TC-5's failure, in its first direction. The slot itself
    (`seed_key`) is internal and is NOT put on the row.
    """
    # `getattr`, because this is also handed duck-typed rows (US-LED-017's
    # TC-5 drives it with a bare stand-in) that predate both columns.
    slot = getattr(account, "seed_key", None) or account.code
    history = list(getattr(account, "code_history", None) or [])
    row = {
        "account_id": str(account.pk),
        "code": account.code,
        "name": account.name,
        "type": account.type,
        "designation": account.designation,
        "status": "deactivated" if account.deleted_at else "active",
        "qbo_ref": account.qbo_ref,
        "xero_ref": account.xero_ref,
        "created_at": account.created_at,
        # US-LED-017 TC-5 — *"no surface presents an unsigned code as signed"*.
        # The flag travels on the row rather than being re-derived by the client.
        #
        # ⚠ **DEFECT FIXED 2026-08-18, AND IT IS THE MIRROR OF TC-5.** This read
        # `not chart.is_cost_of_service_code(account.code)` — membership of the
        # cost section, which is NOT the same question as whether finance signed
        # the row. The two answers agreed from 2026-08-15 until the PO re-signed
        # all eight cost codes on 2026-08-18, and from that moment S56 told a
        # finance reviewer that eight RATIFIED accounts still needed their
        # attention. TC-5 forbids presenting an unsigned code as signed; this
        # was the same failure pointed the other way, and it is why the answer
        # now comes from the two pending registers themselves, which are derived
        # from each row's own `signed` field and cannot disagree with it.
        # CR-061 statement (1) — the chart HEADING, `None` for an account
        # nobody has filed (every account on a database provisioned before
        # 2026-09-02, because nothing backfills). The screen renders that as its
        # own group; it never hides the row.
        "category": account.category,
        # ⚠ **THREE REGISTERS, NOT TWO, SINCE 2026-09-02.** CR-061's 67
        # utility-books accounts are unsigned exactly as CR-066's nine and the
        # fourteen widened cost rows are, and US-LED-017 TC-5 is *"no surface
        # presents an unsigned code as signed"*. Omitting the third register
        # here would have served all 67 as finance-signed on the day they
        # arrived — the same defect this line was already fixed for once, on
        # 2026-08-18, in the other direction.
        "finance_signed": (
            slot not in chart.PENDING_FINANCE_RE_SIGN_COST
            and slot not in chart.PENDING_FINANCE_RE_SIGN
            and slot not in chart.PENDING_FINANCE_RE_SIGN_BOOKS
        ),
        # `seeded` IS the membership question, so this is the right caller for
        # `is_cost_of_service_code` — unlike `finance_signed` above.
        "seeded": slot in {row.code for row in chart.SEED_CHART + chart.UTILITY_BOOKS_CHART}
        or chart.is_cost_of_service_code(slot),
        # CR-196-BRC10 (4) — *"formerly 4150"*: the code before the LATEST
        # change, and the whole list. `changed_by` is a user id and the screen
        # never renders it (B14 rule 31).
        "former_code": history[-1]["old_code"] if history else None,
        "code_history": history,
    }
    if references is not None:
        row["references"] = references
    return row


def chart_of_accounts(
    *,
    search: str | None = None,
    account_type: str | None = None,
    category: str | None = None,
    status: str | None = None,
    designation: str | None = None,
    with_references: bool = False,
) -> dict[str, Any]:
    """EP-LED-02's S56 chart panel — the capability row, served.

    Filters are the epic's own (`type`, `status`), the search fields are its own
    (`code`, `name`) and the default sort is its own (`code asc`). `status`
    defaults to EVERYTHING rather than to active: IS-1 is deactivate-first, so
    a chart panel that hid deactivated rows by default would give a tenant no
    way to find the account they retired and now want back.

    **AN UNSIGNED ROW IS SERVED AND MARKED, NEVER HIDDEN** (US-LED-017 TC-5).
    Every row carries `finance_signed`, and the payload also publishes both
    pending registers plus the named source of the signature an unsigned row
    awaits, so a reviewer sees exactly which numbers a human in finance has
    approved and which a lane proposed.

    ⚠ **AMENDED 2026-08-18.** This paragraph said all eight 5xxx cost rows
    appear with `finance_signed: false`. The PO finance re-signed them that day
    (with 4180), so today every seeded row is served `finance_signed: true` and
    both registers are empty. Serving a ratified row as unsigned is the same
    defect as serving an unsigned one as signed, in the other direction — see
    `_chart_row`, where it actually happened.
    """
    rows = models.LedgerAccount.objects.filter(tenant_id=_tenant_id())
    if status == "active":
        rows = rows.filter(deleted_at__isnull=True)
    elif status == "deactivated":
        rows = rows.filter(deleted_at__isnull=False)
    if account_type:
        rows = rows.filter(type=account_type)
    # CR-061 statement (1) — `f.category=none` is the UNCATEGORISED group and is
    # a real filter value, not an absent one: on a database provisioned before
    # 2026-09-02 it is the ONLY group, and a filter that could not name it would
    # leave a utility unable to find the rows it has to file.
    if category:
        if str(category).strip().lower() == "none":
            rows = rows.filter(category__isnull=True)
        else:
            rows = rows.filter(category=category)
    # DEF-LED-6715 / Finance blueprint p025 note 3 — the ROLE filter, which the
    # blueprint marks NOT SERVED and calls "the gap": *"Designation is how 4·1
    # finds the tax accounts and how the exporter finds cash — it is the
    # load-bearing column and you cannot filter by it."*
    #
    # `f.designation=none` is the rows carrying NO role, and it is a real value
    # for the same reason `f.category=none` is one: most of a tenant's own
    # additions carry none, and a filter that could not name them would leave
    # the group unfindable.
    #
    # ⚠ **`needs-account` IS NOT HANDLED HERE, DELIBERATELY.** It asks about
    # ROLES rather than about accounts, and a role with no account has no row to
    # return — so the only honest answer from a row filter is an empty list.
    # It is answered by `roles_needing_account` below, which the screen renders
    # instead of rows. Filtering for it here would return zero rows and read as
    # "nothing is wrong", which is the exact inversion of what it means.
    if designation:
        wanted = str(designation).strip()
        if wanted.lower() == "none":
            rows = rows.filter(designation__isnull=True)
        elif wanted != "needs-account":
            rows = rows.filter(designation=wanted)
    # ⚠ **THIS BLOCK WAS DELETED BY ACCIDENT ON 2026-09-25 AND RESTORED THE SAME
    # HOUR (`DEF-LED-6715`), AND IT IS WORTH THE PARAGRAPH BECAUSE OF HOW.**
    # The lane adding the ROLE filter above replaced a text anchor that HAPPENED
    # TO CONTAIN these four lines and did not put them back. Nothing went red:
    # `tsc`, 214 front-end cases and every ledger test passed, because no test
    # in this repository asks `chart_of_accounts` to find a row by name — the
    # screen's search box simply stopped narrowing anything and went on
    # returning the whole chart, which looks exactly like a chart with no
    # matches excluded. **It was found by typing "cash" into the running
    # product and counting the rows** (hard-won law 6), and by nothing else.
    # Leave it below the filters and above `order_by`; it is not a comment that
    # can be tidied away with the code it guards.
    if search:
        term = str(search).strip()
        if term:
            rows = rows.filter(Q(code__icontains=term) | Q(name__icontains=term))
    ordered = rows.order_by("code")
    return {
        "rows": tuple(
            _chart_row(
                account,
                account_references(account.pk) if with_references else None,
            )
            for account in ordered
        ),
        "types": chart_account_types(),
        # The eighteen headings, published rather than hardcoded on the screen —
        # BR-REP-006 (*"filters and pickers enumerate the LIVE vocabulary"*) and
        # the same reason the two pending registers below are published.
        "categories": chart.CHART_CATEGORIES,
        "designations": chart.GL_DESIGNATIONS,
        # DEF-LED-6715 — THE ROLES WITH NO LIVE ACCOUNT, AND THIS IS A WARNING
        # RATHER THAN A VOCABULARY.
        #
        # ⚠ **WHAT ACTUALLY HAPPENS, MEASURED RATHER THAN QUOTED.** This lane
        # first wrote *"a posting that needs one of these refuses by name
        # (`BR-LED-796`)"*, inherited from its brief and never checked against
        # the code — which is this repository's most-filed rot, a rule citation
        # on a money path that is nearly right. **`selectors.
        # gl_account_for_designation` answers `None` for an unfilled role.** It
        # RAISES only for a designation NAME it does not recognise, and its own
        # docstring says why the two must differ: *"no account is designated
        # accounts receivable"* and *"you asked for `accounts_recievable`"* are
        # different problems.
        #
        # So the failure is the CALLER's, in whatever not-configured branch it
        # has — `BR-LED-796` is the worked example of one (*"a real state the
        # caller must REFUSE on, never substitute"*), not a general refusal
        # covering every designation. **The absence is still a real operational
        # state a clerk has to be able to see**, which is all this field is for;
        # only the mechanism sentence was wrong.
        # It used to be disclosed by a whole panel under the chart — one row per
        # role, each saying *"No live account has this role. Anything that needs
        # it will fail until one does."* The PO merged that panel into this
        # table on 2026-09-25 (*"i will have 1 table only"*), and **a column
        # cannot carry this**: an unfilled role has no account row to appear on.
        #
        # So it is served as its own list, the screen shows a COUNT of it and
        # offers it as a filter value, and `chart_one_table` in the front end is
        # where it is rendered. Deleting the panel without this would have taken
        # a true warning off the screen with every test still green — hard-won
        # law 2's mirror.
        #
        # `PENDING_FINANCE_RESIGN` is subtracted because those are NOT gaps
        # somebody should go and fix: the account is an addition to the ❄️
        # finance-signed chart that no agent may write. It is empty today and
        # the subtraction is kept for the next row that needs it.
        "roles_needing_account": tuple(
            name
            for name, account_id in selectors.designation_map().items()
            if account_id is None and name not in chart.PENDING_FINANCE_RESIGN
        ),
        # chart.py's own two registers, published rather than re-listed here:
        # a screen that hardcoded which codes are unsigned would disagree with
        # the chart file the first time finance re-signs one (hard-won law 1).
        "pending_finance_re_sign": chart.PENDING_FINANCE_RE_SIGN,
        "pending_finance_re_sign_cost": chart.PENDING_FINANCE_RE_SIGN_COST,
        "pending_finance_re_sign_books": chart.PENDING_FINANCE_RE_SIGN_BOOKS,
        "cost_section_source": chart.COST_SECTION_RE_SIGN_SOURCE,
        "utility_books_source": chart.UTILITY_BOOKS_RE_SIGN_SOURCE,
    }


def chart_account_types() -> tuple[str, ...]:
    """The five S56 Type values, from the model rather than re-listed (BR-REP-006:
    a picker enumerates the LIVE vocabulary)."""
    return models.LEDGER_ACCOUNT_TYPES


# ⚠ **EVERY FIELD ERROR BELOW CARRIES ITS OWN `message_key`, AND FIVE OF THEM
# DID NOT UNTIL `DEF-LED-6140` (2026-09-22).**
#
# The front end renders a field error through `envelopeErrors` in
# `components/FormModal.tsx`, which does `t(fieldError.message_key)`. A field
# error with no key resolves to NOTHING, so the input goes red with no sentence
# written beside it — which is hard-won law 7's *reports zero over a scope it
# silently excludes*, one level down, and `core.errors.ApiError.__init__` can
# only assert a key resolves when a caller supplied one.
#
# It cost nothing until now because the chart's add and edit were inline forms
# that rendered no field errors at all. They are `FormModal` dialogs now, so
# these keys are on a clerk's screen and an absent one is silence.
def _clean_code(raw: Any) -> str:
    code = str(raw or "").strip()
    if not code:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.chart.code_required",
            field_errors=[
                {
                    "field": "code",
                    "code": errors.VAL_REQUIRED,
                    "message_key": "ledger.chart.code_required",
                }
            ],
        )
    return code


def _clean_name(raw: Any) -> str:
    name = str(raw or "").strip()
    if not name:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.chart.name_required",
            field_errors=[
                {
                    "field": "name",
                    "code": errors.VAL_REQUIRED,
                    "message_key": "ledger.chart.name_required",
                }
            ],
        )
    return name


def _clean_type(raw: Any) -> str:
    value = str(raw or "").strip()
    if value not in models.LEDGER_ACCOUNT_TYPES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="ledger.chart.type_unknown",
            params={"types": ", ".join(models.LEDGER_ACCOUNT_TYPES)},
            field_errors=[
                {
                    "field": "type",
                    "code": errors.VAL_UNKNOWN_LOOKUP,
                    "message_key": "ledger.chart.type_unknown",
                    "params": {"types": ", ".join(models.LEDGER_ACCOUNT_TYPES)},
                }
            ],
        )
    return value


def _clean_category(raw: Any) -> str | None:
    """One of `chart.CHART_CATEGORIES`, or None. Python-validated, no CHECK.

    Empty is None and is lawful — an account nobody has filed yet. An unknown
    value is REFUSED rather than stored, because a heading nothing groups under
    is a row that vanishes from the screen it was typed on.
    """
    if raw is None or str(raw).strip() == "":
        return None
    value = str(raw).strip()
    if not chart.is_chart_category(value):
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="ledger.chart.category_unknown",
            params={"category": value},
            field_errors=[
                {
                    "field": "category",
                    "code": errors.VAL_UNKNOWN_LOOKUP,
                    "message_key": "ledger.chart.category_unknown",
                    "params": {"category": value},
                }
            ],
        )
    return value


def _clean_designation(raw: Any) -> str | None:
    if raw is None or str(raw).strip() == "":
        return None
    value = str(raw).strip()
    if value not in chart.GL_DESIGNATIONS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="ledger.chart.designation_unknown",
            params={"designation": value},
            field_errors=[
                {
                    "field": "designation",
                    "code": errors.VAL_UNKNOWN_LOOKUP,
                    "message_key": "ledger.chart.designation_unknown",
                    "params": {"designation": value},
                }
            ],
        )
    return value


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-015")
def create_account(
    actor: Any,
    *,
    code: Any,
    name: Any,
    type: Any,  # noqa: A002 — the column is called `type`; a second spelling is a bug farm
    designation: Any = None,
    category: Any = None,
) -> dict[str, Any]:
    """US-LED-005 TC-2 — a chart line a human typed.

    The tenant owns its chart, so nothing here restricts a code to a range: a
    utility numbering receivables 1150 is the worked example US-LED-005 is
    written around. What it DOES refuse is a duplicate code (the tenant already
    has that line — `uq_ledger_accounts_code`) and a designation another live
    account already holds, because at most one account per tenant may BE the AR
    account and a second one would be an ambiguity the posting service resolves
    by `ORDER BY` accident.

    ⚠ **THE 2200 TAX SERIES IS NOT MINTED HERE.** B5 line 74 is explicit —
    *"tenant authorities mint their own"* — and `create_tax_authority_account`
    is the one path that allocates inside that series (PO 2026-08-12, OQ-147:
    the code is GENERATED). A hand-typed `2200-07` would take a number the
    allocator is about to hand out, so it is refused BY NAME with the route out.
    """
    tenant_id = _tenant_id()
    clean_code = _clean_code(code)
    clean_name = _clean_name(name)
    clean_type = _clean_type(type)
    clean_designation = _clean_designation(designation)
    clean_category = _clean_category(category)

    # ⚠ **THESE THREE NAME A FIELD (`DEF-LED-6140`), AND THAT IS THE WHOLE OF
    # THE CHANGE — WHAT IS REFUSED IS EXACTLY WHAT WAS REFUSED BEFORE.** A
    # refusal a clerk can act on is one that points at the box to change: "that
    # number is already used" belongs ON the number, not above a form. The
    # `field` is the client's own payload key, so it matches the input's `id`
    # in `ChartOfAccountsPanel`'s add dialog and lands under it.
    if chart.is_tax_payable_code(clean_code):
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-BIL-069",
            message_key="ledger.chart.tax_series_reserved",
            params={"series": chart.TAX_PAYABLE_SERIES},
            field_errors=[
                {
                    "field": "code",
                    "code": errors.BIZ_STATE,
                    "message_key": "ledger.chart.tax_series_reserved",
                    "params": {"series": chart.TAX_PAYABLE_SERIES},
                }
            ],
        )
    if models.LedgerAccount.objects.filter(tenant_id=tenant_id, code=clean_code).exists():
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-LED-015",
            message_key="ledger.chart.code_taken",
            params={"code": clean_code},
            field_errors=[
                {
                    "field": "code",
                    "code": errors.BIZ_STATE,
                    "message_key": "ledger.chart.code_taken",
                    "params": {"code": clean_code},
                }
            ],
        )
    if clean_designation is not None and clean_designation in _live_designations(tenant_id):
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-LED-014",
            message_key="ledger.chart.designation_taken",
            params={"designation": clean_designation},
            field_errors=[
                {
                    "field": "designation",
                    "code": errors.BIZ_STATE,
                    "message_key": "ledger.chart.designation_taken",
                    "params": {"designation": clean_designation},
                }
            ],
        )

    with transaction.atomic():
        try:
            account = models.LedgerAccount.objects.create(
                tenant_id=tenant_id,
                code=clean_code,
                name=clean_name,
                type=clean_type,
                designation=clean_designation,
                category=clean_category,
            )
        except IntegrityError as clash:
            # Two clerks, one code. The index is the guarantee; the read above
            # is the good message. It names the same FIELD as the read, so the
            # race and the ordinary case put the sentence in the same place.
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-LED-015",
                message_key="ledger.chart.code_taken",
                params={"code": clean_code},
                field_errors=[
                    {
                        "field": "code",
                        "code": errors.BIZ_STATE,
                        "message_key": "ledger.chart.code_taken",
                        "params": {"code": clean_code},
                    }
                ],
            ) from clash
        core_audit.money_action(
            actor,
            AUDIT_ACCOUNT_CREATED,
            "ledger_account",
            str(account.pk),
            after={
                "code": clean_code,
                "name": clean_name,
                "type": clean_type,
                "designation": clean_designation,
                "source": "tenant_typed",
                # A tenant's OWN account is not a finance-signed chart row and
                # is not marked as one either way — nobody proposed it on
                # finance's behalf (chart.is_cost_of_service_code's reasoning).
                "finance_signed": None,
            },
        )
    return _chart_row(account)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-015")
def update_account(
    actor: Any,
    *,
    account_id: Any,
    name: Any = _UNSET,
    designation: Any = _UNSET,
) -> dict[str, Any]:
    """US-LED-005's edit — the NAME and the DESIGNATION, and nothing else.

    `_UNSET` versus `None` again, and for the same reason `set_export_codes`
    gives: omitting `designation` leaves the pointer alone, passing `None`
    CLEARS it. A page that saved both fields every time would drop a tenant's
    AR pointer every time somebody fixed a typo in an account name.

    **`code` AND `type` ARE NOT ACCEPTED HERE.** `type` is frozen (US-LED-005,
    and still so). ⚠ **`code` IS NOT FROZEN ANY MORE (`CR-196-BRC10`, PO
    2026-10-29)** — it changes through `change_account_code`, System Admin
    only, which is a separate function because it is a separate permission and
    writes its own history. This paragraph used to say *"a renumber is a NEW
    account plus a designation re-point, which is two acts with two audit rows
    rather than one silent restatement of last month's trial balance"*; the PO
    ruled the restatement is what they want (Q1 A: past reports show the new
    code, "formerly" kept).

    **A DEACTIVATED ROW IS EDITABLE HERE, and that is load-bearing rather than
    permissive.** `set_account_active` refuses to bring an account back while
    another live row holds its designation, and the ONLY lawful way out of that
    state is to clear the retired row's pointer first — which is this function.
    Restricting the edit to live rows made the two-step impossible and left the
    account retired forever, found by the test that walks the swap end to end.
    """
    account = _account_or_404(account_id, include_deactivated=True)
    before = {"name": account.name, "designation": account.designation}
    changed: list[str] = []

    if name is not _UNSET:
        clean_name = _clean_name(name)
        if clean_name != account.name:
            account.name = clean_name
            changed.append("name")
    if designation is not _UNSET:
        clean_designation = _clean_designation(designation)
        if clean_designation != account.designation:
            if clean_designation is not None and clean_designation in _live_designations(
                _tenant_id()
            ):
                # ⚠ **THE REFUSAL THE PO ACTUALLY HIT (`DEF-LED-6140`).** It is
                # the one a clerk meets editing a chart row, and until now it
                # arrived with no field on it, so the edit dialog had nowhere to
                # put it. It names `designation` — the picker the clerk just
                # changed — and refuses exactly what it refused before.
                raise errors.BizError(
                    errors.BIZ_STATE,
                    br_ref="BR-LED-014",
                    message_key="ledger.chart.designation_taken",
                    params={"designation": clean_designation},
                    field_errors=[
                        {
                            "field": "designation",
                            "code": errors.BIZ_STATE,
                            "message_key": "ledger.chart.designation_taken",
                            "params": {"designation": clean_designation},
                        }
                    ],
                )
            account.designation = clean_designation
            changed.append("designation")

    if not changed:
        return _chart_row(account)
    with transaction.atomic():
        account.save(update_fields=[*changed, "updated_at"])
        core_audit.money_action(
            actor,
            AUDIT_ACCOUNT_UPDATED,
            "ledger_account",
            str(account.pk),
            before={field: before[field] for field in changed},
            after={field: getattr(account, field) for field in changed},
        )
    return _chart_row(account)


# ═══════════════════════════════════════════════════════════════════════════
# CR-196-BRC10 — A CHART ACCOUNT'S CODE CHANGES; EVERYTHING ELSE FOLLOWS BY ID
# ═══════════════════════════════════════════════════════════════════════════
AUDIT_ACCOUNT_CODE_CHANGED = "ledger_account.code_changed"


def tax_payable_account_ids() -> set[str]:
    """Every account of this tenant that IS a tax liability — live or retired.

    `CR-196-BRC10`, judgment 5b: the code prefix OR the minted slot. The set a
    report filters a `gl_totals` row by, so a renamed `2200-01` stays on the tax
    report and in the month-end check. See `chart.is_tax_payable_account`.
    """
    return {
        str(pk)
        for pk in models.LedgerAccount.objects.filter(tenant_id=_tenant_id())
        .filter(selectors.tax_payable_q())
        .values_list("pk", flat=True)
    }


def account_code_usage(account_id: Any) -> dict[str, Any]:
    """What a code change touches — the confirmation's counts and Q2's warning.

    PO 2026-10-29 (2): *"This code is used on N bills and N payments. The new
    code applies everywhere from now on."* and Q2 A: *"Already exported for Sep
    2026. Re-exports will show the new code."*

    Counted from the ledger's OWN journal, so no other module is read:
      * `bills` — distinct invoice-sourced entries with a line on this account;
      * `payments` — distinct payment-sourced entries likewise;
      * `journal_lines` — every line, posted or not, the delete lock's number;
      * `closed_period` — the LATEST closed month whose window holds a posted
        line on this account;
      * `exported_period` — the LATEST export batch whose window does.
    `None` for either period means there is none, which is what keeps the
    warning off an account that was never in a closed or sent month.
    """
    tenant_id = _tenant_id()
    account = models.LedgerAccount.objects.filter(tenant_id=tenant_id, pk=account_id).first()
    if account is None:
        raise errors.NotFoundError()
    lines = models.JournalLine.objects.filter(tenant_id=tenant_id, ledger_account_id=account.pk)

    def _distinct(source_type: str) -> int:
        return (
            lines.filter(journal_entry__source_type=source_type)
            .values("journal_entry__source_id")
            .distinct()
            .count()
        )

    posted_dates = lines.filter(journal_entry__status=models.JE_POSTED).values(
        "journal_entry__entry_date"
    )
    closed = None
    for period in models.FiscalPeriodClose.objects.filter(
        tenant_id=tenant_id, status=models.PERIOD_CLOSED
    ).order_by("-period_end"):
        if posted_dates.filter(
            journal_entry__entry_date__gte=period.period_start,
            journal_entry__entry_date__lte=period.period_end,
        ).exists():
            closed = {
                "start": period.period_start.isoformat(),
                "end": period.period_end.isoformat(),
            }
            break
    exported = None
    for batch in models.ExportBatch.objects.filter(tenant_id=tenant_id).order_by(
        "-period_end", "-created_at"
    ):
        if posted_dates.filter(
            journal_entry__entry_date__gte=batch.period_start,
            journal_entry__entry_date__lte=batch.period_end,
        ).exists():
            exported = {
                "start": batch.period_start.isoformat(),
                "end": batch.period_end.isoformat(),
                "target": batch.target,
            }
            break
    return {
        "bills": _distinct("invoice"),
        "payments": _distinct("payment"),
        "journal_lines": lines.count(),
        "closed_period": closed,
        "exported_period": exported,
    }


def change_account_code(actor: Any, *, account_id: Any, code: Any) -> dict[str, Any]:
    """`CR-196-BRC10` — a System Admin changes an account's CODE, used or not.

    PO ruling 2026-10-29, verbatim: *"in many cases utilities are giving there
    own GL codes; which means we have to ability to change existing GL code as
    per the given utility for that specific tenant; even if they are used ; if
    user update them they should be applicable after the updation."* This
    AMENDS BR-LED-040 / US-LED-005 §1 for the CODE only; `type` is still not
    accepted by `chart_api.account_item` at all.

    **IT APPLIES EVERYWHERE AT ONCE, PAST INCLUDED (Q1 A)** — and needs no
    other write to do so: every journal line, designation, service pointer and
    charge code holds the account's ID, so a report run tomorrow over January
    prints the new code. The September GL report of the PO's example reads
    `0117-080-1000-0000-7110` where it read `4150`.

    **WHO (Q4 A):** a System Admin, and nobody else — refused BY NAME
    (`ledger.chart.code_change_admin_only`) rather than by the generic
    permission sentence, because a clerk who can rename the account will
    otherwise read the refusal as a fault. Checked here, not only at the view,
    so a job or a shell is refused too (BR-SHL-025).

    **WHAT IS REFUSED, each naming the `code` field:** an empty code (the
    create path's `_clean_code`, trimmed); a code another account of this
    tenant holds, retired ones included — `uq_ledger_accounts_code` counts them,
    so the read and the index agree; and moving a NON-tax account into the
    2200 series, which BR-BIL-069 reserves (the create path's refusal, same
    key). A closed month or a sent export is NOT a refusal (Q2 A) — the
    confirmation warns from `account_code_usage`.

    **WHAT IS KEPT:** the old code, on the account (`code_history`) and in an
    audit row `ledger_account.code_changed` {old, new} (hard rule 7). The
    account's `seed_key` is NOT touched — that is the whole point of it.
    """
    if getattr(actor, "role", None) != SYSTEM_ADMIN:
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            br_ref="BR-LED-040",
            message_key="ledger.chart.code_change_admin_only",
        )
    tenant_id = _tenant_id()
    account = _account_or_404(account_id, include_deactivated=True)
    clean_code = _clean_code(code)
    if clean_code == account.code:
        return _chart_row(account)

    def _refuse(message_key: str, br_ref: str, params: dict[str, Any]) -> None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref=br_ref,
            message_key=message_key,
            params=params,
            field_errors=[
                {
                    "field": "code",
                    "code": errors.BIZ_STATE,
                    "message_key": message_key,
                    "params": params,
                }
            ],
        )

    if chart.is_tax_payable_code(clean_code) and not chart.is_tax_payable_account(
        account.code, account.seed_key
    ):
        _refuse(
            "ledger.chart.tax_series_reserved",
            "BR-BIL-069",
            {"series": chart.TAX_PAYABLE_SERIES},
        )
    if (
        models.LedgerAccount.objects.filter(tenant_id=tenant_id, code=clean_code)
        .exclude(pk=account.pk)
        .exists()
    ):
        _refuse("ledger.chart.code_taken", "BR-LED-015", {"code": clean_code})

    old_code = account.code
    with transaction.atomic():
        account.code = clean_code
        try:
            with transaction.atomic():
                account.save(update_fields=["code", "updated_at"])
        except IntegrityError as clash:
            # Two admins, one code. The index is the guarantee; the read above
            # is the good message. The inner atomic is a SAVEPOINT, so the
            # refusal leaves the outer transaction usable on PostgreSQL
            # (hard-won law 14) — and it re-raises rather than carrying on.
            _refuse("ledger.chart.code_taken", "BR-LED-015", {"code": clean_code})
            raise clash  # pragma: no cover — _refuse always raises
        # `updated_at` is the moment the code changed — stamped by the save
        # above, so the history and the row cannot disagree about it.
        account.code_history = [
            *(account.code_history or []),
            {
                "old_code": old_code,
                "new_code": clean_code,
                "changed_at": account.updated_at.isoformat() if account.updated_at else None,
                "changed_by": str(
                    getattr(actor, "id", None) or getattr(actor, "pk", None) or ""
                )
                or None,
            },
        ]
        account.save(update_fields=["code_history"])
        core_audit.money_action(
            actor,
            AUDIT_ACCOUNT_CODE_CHANGED,
            "ledger_account",
            str(account.pk),
            before={"code": old_code},
            after={"code": clean_code},
        )
    return _chart_row(account)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-015")
def set_account_active(actor: Any, *, account_id: Any, active: bool, at: Any) -> dict[str, Any]:
    """IS-1's deactivate-first, both directions. `at` is an INPUT (BR-TEN-043).

    **DEACTIVATING DOES NOT DROP THE DESIGNATION**, and that is deliberate
    rather than an oversight: `uq_ledger_accounts_designation` is partial on
    `deleted_at IS NULL`, so retiring the account frees the designation for the
    replacement automatically, and `apps/ledger/selectors.py` filters the same
    way — a deactivated AR account stops being "the AR account" the moment it is
    retired, with nothing to remember to clear. What it does NOT do is erase
    which designation the row used to carry, which is what an auditor reading a
    July trial balance needs.

    ⚠ **A DEACTIVATED ACCOUNT CARRYING A DESIGNATION LEAVES THAT DESIGNATION
    UNRESOLVABLE** until another account claims it. That is a real state and it
    is reported, not prevented: the tenant may be retiring 1200 precisely
    because 1150 is about to take over, and refusing the first half of a
    two-step would make the swap impossible. `designation_now_unresolved` says
    so on the response, and `GET /ledger/gl-mappings` shows the hole.
    """
    account = _account_or_404(account_id, include_deactivated=True)
    currently_active = account.deleted_at is None
    if currently_active == active:
        return {**_chart_row(account), "changed": False}

    if active and account.designation and account.designation in _live_designations(_tenant_id()):
        # ⚠ **REACTIVATION IS NOT THE MIRROR OF DEACTIVATION, AND THE DATABASE
        # FOUND IT BEFORE A HUMAN DID.** Retiring 1200 frees
        # `accounts_receivable` for the 1150 that replaces it (the constraint is
        # partial on `deleted_at IS NULL`), and bringing 1200 back would then
        # put TWO live accounts on one designation —
        # `uq_ledger_accounts_designation` refuses the write with an
        # IntegrityError and a 500.
        #
        # The two silent repairs were both available and both refused: clearing
        # 1200's designation on the way back in would change WHICH account is
        # the AR account without anybody asking, and moving the designation off
        # 1150 would do the same in the other direction. Either one edits the
        # posting service's answer as a side effect of a Reactivate button. So
        # the act is refused and the refusal NAMES the account holding it —
        # the clerk clears one pointer, deliberately, and then reactivates.
        holder = (
            models.LedgerAccount.objects.filter(
                tenant_id=_tenant_id(),
                designation=account.designation,
                deleted_at__isnull=True,
            )
            .exclude(pk=account.pk)
            .first()
        )
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-LED-014",
            message_key="ledger.chart.reactivate_designation_taken",
            params={
                "code": account.code,
                "designation": account.designation,
                "holder": holder.code if holder else "",
            },
        )

    account.deleted_at = None if active else at
    with transaction.atomic():
        account.save(update_fields=["deleted_at", "updated_at"])
        core_audit.money_action(
            actor,
            AUDIT_ACCOUNT_REACTIVATED if active else AUDIT_ACCOUNT_DEACTIVATED,
            "ledger_account",
            str(account.pk),
            before={"status": "active" if currently_active else "deactivated"},
            after={
                "status": "active" if active else "deactivated",
                "designation": account.designation,
            },
        )
    row = _chart_row(account)
    row["changed"] = True
    row["designation_now_unresolved"] = (
        account.designation if (not active and account.designation) else None
    )
    return row


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-015")
def delete_account(actor: Any, *, account_id: Any) -> dict[str, Any]:
    """IS-1's hard delete — **only when nothing anywhere references the row**.

    US-LED-005 §1: *"an account referenced by journal lines, GL mappings, charge
    codes or designations can be deactivated but never deleted … financial
    records never delete, CLAUDE.md #4"*.

    **AND IT REFUSES WHEN IT CANNOT TELL.** Two of the four reference kinds are
    other modules' reads and neither publishes a reverse lookup, so
    `account_references` answers `answerable: False` and this function refuses
    on that alone. Deleting a chart row because a read was missing is the
    DEF-127 shape — an unanswerable question rendered as a comfortable zero —
    and the cost here is a row nobody can remove versus a row somebody's charge
    code still points at. Deactivate is always available and loses nothing.
    """
    references = account_references(account_id)
    account = _account_or_404(account_id, include_deactivated=True)
    if references["referenced"] or not references["answerable"]:
        # The refusal NAMES what held it. `params` is what the catalogue
        # sentence interpolates, so the clerk reads "1200 Accounts receivable is
        # referenced by 14 journal lines" rather than "in use".
        holding = ", ".join(
            f"{kind}={references['counts'].get(kind, 0)}"
            for kind in REFERENCE_KINDS
            if references["counts"].get(kind)
        )
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-LED-015",
            message_key="ledger.chart.delete_blocked",
            params={
                "code": account.code,
                "references": holding or "unreadable",
                "unreadable": ", ".join(gap["code"] for gap in references["unavailable"]),
            },
        )
    with transaction.atomic():
        core_audit.money_action(
            actor,
            AUDIT_ACCOUNT_DELETED,
            "ledger_account",
            str(account.pk),
            before={"code": account.code, "name": account.name, "type": account.type},
        )
        account.delete()
    return {"account_id": str(account_id), "deleted": True}


# ═══════════════════════════════════════════════════════════════════════════
# CR-008 Tab 1 — IMPORT A CHART OF ACCOUNTS FROM A FILE
# ═══════════════════════════════════════════════════════════════════════════
#: One audit row per import run, over and above `create_account`'s own row per
#: account: a utility that loaded 180 accounts wants to see ONE act, and an
#: auditor tracing a single account wants to see ITS row. Both exist.
AUDIT_CHART_IMPORTED = "ledger_account.imported"

#: What an import row can be, and the whole vocabulary of the preview screen.
#: `existing` is not an error and not a change — see the docstring.
IMPORT_OUTCOMES = ("new", "existing", "duplicate_in_file", "invalid")


@require_role(SYSTEM_ADMIN, br_ref="BR-LED-015")
def import_accounts(
    actor: Any, *, rows: list[dict[str, Any]], commit: bool = False
) -> dict[str, Any]:
    """CR-008 Tab 1's *Import CSV*: validate a whole file, then load it or not.

    **THE PO'S OWN PRINCIPLE, WHICH IS WHY THIS EXISTS AT ALL** (CR-008,
    verbatim): *"your books own the chart of accounts — SMARTBillHub syncs or
    imports it, points at accounts, and never invents them."* The QuickBooks
    SYNC half of that sentence was ruled out on 2026-08-17 (*"we only need file
    no live integration"*), so this file import is the whole of how a utility's
    real chart gets in.

    ── FOUR OUTCOMES, AND `existing` IS THE ONE THAT MATTERS ────────────────
    `new` a code this tenant does not have · `existing` a code it already has ·
    `duplicate_in_file` the same code twice in one upload · `invalid` a row
    that cannot be an account at all.

    **AN `existing` ROW IS SKIPPED AND NEVER UPDATED.** This is the dedupe the
    CR asks for, and the direction is the safety: re-importing a file must not
    rename `1200 Accounts receivable` to whatever the spreadsheet's B-column
    happened to say, because that account carries a DESIGNATION the posting
    service resolves every journal entry through. Renaming is a deliberate,
    audited, one-row act (`update_account`), never a side effect of an import.

    ── COMMIT IS ALL-OR-NOTHING, AND ONLY OVER A CLEAN FILE ─────────────────
    With `commit=False` nothing is written and the caller gets the full report
    — the *validate* step of the CR's *upload → map → validate → load*. With
    `commit=True` the run REFUSES if any row is `invalid` or
    `duplicate_in_file`: a chart half-loaded from a file with three bad lines
    leaves a utility unable to tell which of 180 accounts arrived, and the
    remedy (fix the file, import again) is otherwise unusable because every
    good row now reports `existing`.

    ── SYSTEM ADMIN ONLY, WHICH IS TIGHTER THAN THE ROW-AT-A-TIME WRITE ─────
    `create_account` allows System Admin or Billing Clerk. This route is a
    SETTINGS surface and the PO ruled Settings → Accounting is **System Admin**
    (CR-008 #4), so the bulk door is the narrower of the two. Stated because it
    is a real asymmetry a reader would otherwise read as an oversight: one
    account typed by a clerk is one audited act somebody reviews; 180 arriving
    from a spreadsheet is a chart of accounts.
    """
    if not isinstance(rows, list):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.chart.import_rows_not_a_list",
            field_errors=[{"field": "rows", "code": errors.VAL_FORMAT}],
        )
    tenant_id = _tenant_id()
    taken = set(
        models.LedgerAccount.objects.filter(tenant_id=tenant_id).values_list("code", flat=True)
    )
    seen_in_file: set[str] = set()
    report: list[dict[str, Any]] = []

    for index, raw in enumerate(rows, start=1):
        entry: dict[str, Any] = {"line": index}
        if not isinstance(raw, dict):
            report.append({**entry, "outcome": "invalid", "reason": "row_not_an_object"})
            continue
        code = str(raw.get("code") or "").strip()
        name = str(raw.get("name") or "").strip()
        type_ = str(raw.get("type") or "").strip().lower()
        # CR-061 statement (1) — an OPTIONAL column. A file that names no
        # heading imports exactly as it did before and every row lands
        # uncategorised; a file that names an unknown one is `invalid` with its
        # own reason rather than silently uncategorised, which is the same
        # posture `type_unknown` already takes one line below. Nothing is
        # DERIVED from the code here: `chart.py`'s banner forbids reading an
        # account's meaning off its number, and an imported chart is the one
        # place a utility's numbers are guaranteed not to be ours.
        category = str(raw.get("category") or "").strip().lower()
        entry.update({"code": code, "name": name, "type": type_, "category": category or None})
        if not code:
            report.append({**entry, "outcome": "invalid", "reason": "code_required"})
            continue
        if not name:
            report.append({**entry, "outcome": "invalid", "reason": "name_required"})
            continue
        if type_ not in models.LEDGER_ACCOUNT_TYPES:
            report.append({**entry, "outcome": "invalid", "reason": "type_unknown"})
            continue
        if category and not chart.is_chart_category(category):
            report.append({**entry, "outcome": "invalid", "reason": "category_unknown"})
            continue
        if chart.is_tax_payable_code(code):
            # B5 line 74: *"tenant authorities mint their own"*, and OQ-147
            # made the 2200-nn code GENERATED. A spreadsheet row would take a
            # number the allocator is about to hand out.
            report.append({**entry, "outcome": "invalid", "reason": "tax_series_reserved"})
            continue
        if code in seen_in_file:
            report.append({**entry, "outcome": "duplicate_in_file"})
            continue
        seen_in_file.add(code)
        report.append({**entry, "outcome": "existing" if code in taken else "new"})

    counts = {
        outcome: sum(1 for row in report if row["outcome"] == outcome)
        for outcome in IMPORT_OUTCOMES
    }
    blocked = counts["invalid"] + counts["duplicate_in_file"]
    result: dict[str, Any] = {
        "committed": False,
        "counts": counts,
        "rows": report,
        "types": list(models.LEDGER_ACCOUNT_TYPES),
        "categories": list(chart.CHART_CATEGORIES),
    }
    if not commit:
        return result
    if blocked:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-LED-015",
            message_key="ledger.chart.import_has_bad_rows",
            params={"bad": blocked, "total": len(report)},
        )

    created: list[str] = []
    with transaction.atomic():
        for row in report:
            if row["outcome"] != "new":
                continue
            account = create_account(
                actor,
                code=row["code"],
                name=row["name"],
                type=row["type"],
                designation=None,
                category=row.get("category"),
            )
            created.append(account["code"])
        core_audit.money_action(
            actor,
            AUDIT_CHART_IMPORTED,
            "ledger_account_import",
            str(tenant_id),
            after={
                "created": created,
                "created_count": len(created),
                "skipped_existing": counts["existing"],
                "rows_in_file": len(report),
                "source": "csv_import",
            },
        )
    result["committed"] = True
    result["created"] = created
    return result


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-006 — the export codes on the GL mapping page (BR-LED-014, r13 #5)
# ═══════════════════════════════════════════════════════════════════════════
#: The two target-system refs B2 r13 #5 puts on a ledger account. Named once so
#: the write below, `apps/ledger/exports.REF_FIELD_BY_TARGET` and the mapping
#: read cannot drift into disagreeing about what a QuickBooks ref is called.
EXPORT_REF_FIELDS = ("qbo_ref", "xero_ref")

AUDIT_EXPORT_CODE_UPDATED = "ledger_account.export_code_updated"


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-014")
def set_export_codes(
    actor: Any,
    *,
    account_id: Any,
    qbo_ref: Any = _UNSET,
    xero_ref: Any = _UNSET,
) -> dict[str, Any]:
    """US-LED-006 TC-2 — set one chart row's QuickBooks and Xero account refs.

    BR-LED-014, as amended by the PO on 2026-08-12 (OQ-106 *"Confirm they belong
    with ledger settings"* + OQ-151 *"Confirm: under Configure"*): the export
    codes live on the GL mapping page, which lives under **Settings → Configure**
    with the rest of the ledger's configuration — not on a ninth top-level tab.
    This is that page's write.

    **`_UNSET` versus `None` is the whole signature.** Omitting an argument
    leaves that ref alone; passing `None` CLEARS it. A page that saved both
    fields every time would wipe a Xero ref every time somebody typed a
    QuickBooks one, and the two are edited from different columns of the same
    row.

    **Edits are FORWARD-ONLY, and this function is why that costs nothing**
    (US-LED-006 TC-4): a recorded `export_batches` row keeps the refs it shipped
    with, because `apps/ledger/exports.py` stores the payload it sent and hashes
    it. Changing `4100`'s ref from 79 to 101 on Aug 9 leaves July's batch reading
    79 forever and sends 101 from the next export on. Nothing here has to reach
    back, and nothing may.

    Blank strings are stored as NULL: *"a ref of empty string"* and *"no ref"*
    are the same fact to an export, and keeping two spellings of it would make
    the gap indicator on the mapping page wrong for one of them.
    """
    tenant_id = _tenant_id()
    account = models.LedgerAccount.objects.filter(
        tenant_id=tenant_id, pk=account_id, deleted_at__isnull=True
    ).first()
    if account is None:
        # US-LED-006 TC-7: another tenant's account is not found, and nothing is
        # reported about whose it is (HR-1 — cross-tenant is a 404, never a 403).
        raise errors.NotFoundError()

    before = {field: getattr(account, field) for field in EXPORT_REF_FIELDS}
    changed: list[str] = []
    for field, value in (("qbo_ref", qbo_ref), ("xero_ref", xero_ref)):
        if value is _UNSET:
            continue
        cleaned = str(value).strip() or None if value is not None else None
        if cleaned != getattr(account, field):
            setattr(account, field, cleaned)
            changed.append(field)
    if not changed:
        return export_code_row(account)

    with transaction.atomic():
        account.save(update_fields=[*changed, "updated_at"])
        core_audit.money_action(
            actor,
            AUDIT_EXPORT_CODE_UPDATED,
            "ledger_account",
            str(account.pk),
            before={field: before[field] for field in changed},
            after={field: getattr(account, field) for field in changed},
        )
    return export_code_row(account)


def export_code_row(account: models.LedgerAccount) -> dict[str, Any]:
    """One row of the mapping page: the chart line plus its two target refs."""
    return {
        "account_id": str(account.pk),
        "code": account.code,
        "name": account.name,
        "type": account.type,
        "designation": account.designation,
        "qbo_ref": account.qbo_ref,
        "xero_ref": account.xero_ref,
        # US-LED-006 TC-1: *"gaps render as visible empty states, not silently"*.
        # Computed rather than left to the screen, so the API, the CSV and the
        # page all call a gap the same thing.
        "gaps": tuple(field for field in EXPORT_REF_FIELDS if not getattr(account, field)),
    }


def export_code_map() -> dict[str, Any]:
    """US-LED-006 TC-1 — the mapping page's read, whole chart, code order.

    Every LIVE chart row, each with its QBO and Xero refs and its gap flags, plus
    the per-target counts the S42 export gate will refuse on (US-LED-006 TC-5).
    Deactivated accounts are excluded: IS-1 hides them from the mapping and JE
    pickers, and an export never addresses one.
    """
    rows = [
        export_code_row(account)
        for account in models.LedgerAccount.objects.filter(
            tenant_id=_tenant_id(), deleted_at__isnull=True
        ).order_by("code")
    ]
    return {
        "rows": tuple(rows),
        "missing": {
            field: tuple(row["code"] for row in rows if field in row["gaps"])
            for field in EXPORT_REF_FIELDS
        },
    }


def gl_account_id_for_designation(designation: str) -> str | None:
    """The tenant's live account carrying `designation`, as an id string.

    Published for TENANCY (CR-040 task A2, PO ruling 2026-08-27 closing OQ-490):
    provisioning points every seeded tender at the `undeposited_funds`
    designation, and it may not reach into this module's ORM to find the row
    (B1 / BR-TEN-013). `selectors.gl_account_id_for_designation` already
    answered this question for the modules that import ledger directly; this is
    the same answer on the service layer, where a neighbour is allowed to ask.

    ⚠ **IT RAISES ON AN UNKNOWN DESIGNATION and answers `None` for a chart that
    simply has no such row.** Those are different facts and the selector keeps
    them apart deliberately — a typo answered `None` would be reported to a
    clerk as a mapping gap they have nothing to fix.
    """
    return selectors.gl_account_id_for_designation(designation)


def default_gl_account_id_for_charge_code(
    code: str, *, service: Any = None, is_base: bool = False
) -> str | None:
    """CR-066 table 1 on the SERVICE layer, for RATING to ask.

    Published for the same reason `gl_account_id_for_designation` was published
    for tenancy: the answer lives in this module's chart and this module's
    account table, and a neighbour reaches it through the service layer and
    never through the ORM (B1 / BR-TEN-013).

    ⚠ **THE CALLER IS SEEDING A DEFAULT, NOT DECIDING A POSTING.** Whatever this
    returns is written into `rating.charges.gl_account_id` ONCE, on a row that
    has none, and a tenant may re-point it on S8 → Accounting the minute
    afterwards. Nothing here overwrites a tenant's own choice (`BR-TEN-012`) —
    that discipline belongs to the caller and `apps.rating.services.
    apply_default_gl_accounts` is where it is written down.
    """
    return selectors.default_gl_account_id_for_charge_code(
        code, service=str(service) if service else None, is_base=bool(is_base)
    )


def default_gl_account_id_for_reason_code(code: str) -> str | None:
    """CR-066 table 2 on the SERVICE layer, for TENANCY to ask.

    `reason_codes` is tenancy's table and the account is the ledger's row, which
    is exactly the split `_map_tender_clearing_accounts` already works across.

    ⚠ **NOTHING IN THE BACKEND READS THE COLUMN THIS FILLS.** An adjustment
    credit reverses whatever account the original bill credited; the mapping is
    a fact a tenant can now state and see, not a posting rule that has changed.
    """
    return selectors.default_gl_account_id_for_reason_code(code)


def default_gl_account_id_for_discount() -> str | None:
    """CR-066 table 3 on the SERVICE layer, for RATING to ask — `4760`."""
    return selectors.default_gl_account_id_for_discount()


def account_is_live(account_id: Any) -> bool:
    """Is this id a LIVE account of the current tenant's own chart?

    Published for tenancy, which validates a tenant's GL override against it
    before pointing a service at an account (PO 2026-08-11: *"allow tenant user
    to override it"*). The check belongs here and not there for two reasons that
    are not style: the account table is this module's, and a FK alone would let
    a service point at ANOTHER TENANT's account — the FK constrains existence,
    never ownership. Deactivated accounts (IS-1) answer False, so a tenant
    cannot map revenue onto a row their own trial balance treats as retired.
    """
    return selectors.account_is_live(account_id)


def account_display(account_id: Any) -> dict[str, str] | None:
    """The chart CODE and NAME for a live account of this tenant, or `None`.

    Published for RATING, whose charge, tax and discount rows carry a
    `gl_account_id` uuid that B14 rule 31 forbids a screen to print. A
    neighbouring module reaches this one through its service layer (B1), and the
    query lives in `selectors` (LAW 0).

    ⚠ **THIS IS A DISPLAY READ AND IT NEVER RAISES — UNLIKE `account_is_live`
    BESIDE IT, WHICH IS RIGHT TO.** That one guards a MAPPING that freezes onto
    a bill, so an unanswerable check must stop the write. This one fills a table
    cell: making it raise would turn an unwired ledger into a 500 on the whole
    Charges step, and B14 rule 31 is satisfied by showing nothing. `None` is the
    whole failure mode.
    """
    return selectors.account_display(account_id)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-005@663369d (sources: 04-docs/02-decisions/05-golden-tests.md line 74 seed chart ❄️ · 12-governance/02-decision-log.md 2026-08-11 rows "OQ-106 IS CLOSED" / "OQ-110 CLOSED" / "STORM WATER AND THERMAL HEAT GET REVENUE ACCOUNTS" + 2026-08-12 row "TAX LIABILITY ACCOUNT CODES ARE GENERATED, NOT TYPED" · 12-governance/01-open-questions.md OQ-115 (CLOSED) + OQ-147 (CLOSED) · 04-docs/05-modules/09-ledger/06-epics/EP-LED-02-chart-mapping.md US-LED-005 · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-010)
# generated: 2026-08-11 by Eng-Lead (W5 ledger GL-designation lane) · AMENDED 2026-08-15 by the close-the-books lane (US-LED-006: `set_export_codes` / `export_code_row` / `export_code_map` — the QBO and Xero refs of B2 r13 #5, on the GL mapping page BR-LED-014 puts under Settings → Configure. Role-gated System Admin + Billing Clerk, audited `ledger_account.export_code_updated` with before/after, forward-only by construction because a recorded export batch stores the payload it sent. No existing function is touched) · AMENDED 2026-08-11 by Eng-Lead (OQ-115 lane: conditional per-service seeding · ensure_service_revenue_accounts replaces seeded_revenue_account_ids · account_is_live published for tenancy's override validation) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: `create_tax_authority_account` — one 2200 account per authority) · AMENDED 2026-08-12 by story-coder (OQ-147 lane — PO ruling "Generated": `_next_tax_payable_code` allocates the next code in the ❄️ signed 2200 series; the stub that used to refuse here is GONE, not deprecated, and this file now cites no open question) · AMENDED 2026-08-18 by the CR-008 ledger lane (CR-010 B-9, PO 2026-08-17 "9 - A full ~40 accounts for every tenant, as you said": `_wanted_rows` answers the FULL 33-row chart unconditionally — OQ-115's per-service narrowing SUPERSEDED, quoted in the module docstring; `ensure_service_revenue_accounts` kept by name as the lookup + top-up path for narrowing-era tenants)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the S56 chart endpoints are US-LED-005's write half, not built) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the report and 06-backend/tests/test_us_led_005_gl_designations.py
# exceptions: the seed writes one audit row per account CREATED and none for an
#         account it leaves alone — a replayed provisioning therefore audits
#         nothing, which is the honest trail but does mean "the seed ran again"
#         leaves no mark; REPORTED · `ensure_service_revenue_accounts` is the
#         ONLY function in this module that resolves an account by CODE, and it
#         is confined to the instant a service is switched on, for the reason
#         stated in its docstring · a tenant provisioned BEFORE the OQ-115
#         ruling keeps all 22 accounts: nothing here deletes or deactivates, so
#         the six a water-only tenant does not sell are removed by its own staff
#         on S56 or not at all — REPORTED · no S56 CRUD, no posting service, no
#         GL mapping screen · [OQ-147 lane, 2026-08-12] a GENERATED 2200-nn code
#         is MONOTONIC per tenant, counting soft-deleted rows: a deactivated
#         2200-02 is never re-let and a gap the tenant left is never backfilled.
#         "Next free" in OQ-147's option (b) is read as "next NUMBER", not
#         "lowest unused" — lowest-unused walks into `uq_ledger_accounts_code`,
#         which is unconditional and counts deactivated rows. REPORTED, not a
#         PO ruling · the collision guarantee is that unique index plus an
#         insert-and-retry, NOT the high-water read · `create_tax_authority
#         _account` still ACCEPTS an explicit `code=`; the ruling settles who
#         numbers a NEW account, and no product surface passes one today —
#         REPORTED as a judgment call in the function's docstring · the OQ-147
#         claims in `apps/ledger/chart.py` (2), `07-frontend/src/features/
#         tenancy/README.md` and `08-qa/01-e2e/stack/` (README + fixture) still
#         say the question is OPEN and are now STALE (hard-won law 1); they are
#         outside this lane's touch list and are REPORTED, not edited
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
