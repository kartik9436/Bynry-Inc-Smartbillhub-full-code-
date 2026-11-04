# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-003 (global search) — this module's FOUR of the nine groups
#           Screens: shell chrome (the topbar popover, every authenticated screen)
# Rules:    BR-SHL-005 AS AMENDED 2026-09-03 (nine groups; ≤5 each;
#           prefix-then-recency; by their B2 IDENTIFIERS) ·
#           BR-SHL-006 (runs under app.tenant_id + RLS FORCE; role-invisible
#           groups omitted) · BR-CUS-068 (a master account is an `accounts` row
#           with kind='master') · B14 rule 31 (no database id is ever the
#           visible value of a field)
# Tests:    06-backend/tests/test_us_shl_003_search.py (rank, shape, caps) ·
#           06-backend/tests/test_us_shl_003_search_isolation.py (TC-7, the
#           mandatory live-Postgres RLS probe)
# Impacts:  core.search registry (apps/customers/apps.py registers these four) ·
#           GET /search (apps/tenancy/search_api.py)
# ───────────────────────────────────────────────────────
"""The customers module's global-search sources: accounts, master accounts,
customers and service requests.

WHY THIS IS A FILE OF ITS OWN AND NOT FOUR MORE FUNCTIONS IN `selectors.py`
---------------------------------------------------------------------------
`selectors.py` is 1,500 lines and is edited by nearly every customers lane.
These four functions are read-only, share one shape, and are registered
together; keeping them here means a lane touching global search never has to
open the file every other lane is in (CLAUDE.md law 11 — the cheapest way to
avoid a shared-file revert is not to share the file). They are SELECTORS by
layer — reads only, no ORM writes, no rule decided here.

THE SHAPE EVERY SOURCE RETURNS, AND WHY IT HAS THESE FIELDS
------------------------------------------------------------
    {"id": …, "label": …, "context": …, "amount": …, "currency": …}

`label` is the B2 IDENTIFIER — the thing a person quotes and the only value the
popover shows large. `context` is ONE plain line that tells them they have the
right row. `id` is carried for the deep link and **is never rendered** (B14 rule
31, ratified in the words *"no Databse ID on screen - that is a rule"*); the
frontend uses it to build a route and nothing else. Money rides as an exact
decimal string beside its CHAR(3) currency and is formatted for display by the
client — hard rule 2, which forbids a float on the wire and re-rounding here.

⚠ **TENANT SCOPING IS BELT AND BRACES AND BOTH BELTS ARE LOAD-BEARING.** Every
queryset filters `tenant_id=_tenant_id()` (the app layer) AND runs under
`app.tenant_id` with RLS FORCE (the database). `core.search.search()` refuses to
run at all without tenant context, so there is no path here that can execute
tenant-less. That is BR-SHL-006 and it is release-blocking: a global search is
the one surface that reads every table at once, so it is the one surface where a
scoping mistake leaks everything rather than one screen's worth.

WHAT THESE SOURCES MATCH ON, AND THE ONE PLACE A NAME IS ACCEPTED
-----------------------------------------------------------------
BR-SHL-005 says *by their B2 identifiers*, and the amendment of 2026-09-03
repeats it as a thing not to relax. So:
  · accounts / master accounts — `account_no`, **plus the primary contact's
    full name**, which is in the SIGNED field list (*"Accounts —
    accounts.account_no, primary contacts.full_name"*) and is how a clerk finds
    the person on the phone;
  · customers — `customer_no` ONLY. The PO's words are *"customer id"*, and the
    ruling reads that as the customer NUMBER rather than the database id. A name
    typed into the box already finds its account through the clause above, so
    accepting `display_name` here would add a second row for the same human
    under a different heading;
  · service requests — `request_no`. A request is *"one numbered application,
    whatever channel it arrived by"* and the number is its identifier.
Both narrowings are recorded in 12-governance/02-decision-log.md with the
reasoning, so a later lane can widen them deliberately rather than by accident.
"""

from typing import Any

from apps.customers import models
from core import search as core_search
from core import tenancy as core_tenancy
from core import errors

# The columns a LEADING match ranks first (BR-SHL-005's prefix band). The
# identifier only: a person typing "A-104" means the account number, and letting
# a name prefix share band 0 would rank "A. Delgado" alongside "A-10432".
_ACCOUNT_PREFIX_FIELDS = ("account_no",)
# ⚠ The account MATCH set is built by hand in `_account_rows` rather than through
# `core_search.matches_any`, because the contact half needs a second condition
# (`deleted_at__isnull=True`) INSIDE the same `Q` and that helper builds one
# lookup per field. See the comment there — it is a correctness point, not style.


def _account_kinds() -> tuple[str, str]:
    """`(regular, master)` resolved from services, lazily.

    A local import for the reason `selectors.services_master_kind()` already
    gives: `apps.customers.services` imports the selector layer, so a
    module-level import here would close the cycle. Resolving it rather than
    re-spelling `"master"` is what keeps this file from drifting the day
    BR-CUS-068's vocabulary changes — a private copy of a constant is a
    constant that is right until it is not, and nothing would go red.
    """
    from apps.customers import services

    return services.ACCOUNT_KIND_REGULAR, services.ACCOUNT_KIND_MASTER


def _tenant_id() -> Any:
    """The ambient tenant, or a refusal. Never a parameter — see BR-SHL-006."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-SHL-006")
    return tenant_id


def _primary_contact_names(account_ids: list[Any]) -> dict[str, str]:
    """{account_id: primary contact name} in ONE query for the whole group.

    A per-row lookup would be five queries per group and twenty across the four
    groups this module serves, on a keystroke-driven surface. `-is_primary`
    first so the flagged contact wins; `created_at` breaks the tie the same way
    `selectors.primary_contact_name` does, so the popover and the account screen
    never disagree about whose name this is.
    """
    # ⚠ `DEF-CUS-9776` — DELEGATES NOW. This held its own copy of the contact
    # rule, so when the account's name became its CUSTOMER's name (a company's
    # legal name, not its contact person's) a copy here would have gone on
    # naming *Ruth Okafor* in the popover beside *Grace Fellowship* on the page.
    from apps.customers import selectors

    return {
        key: name for key, name in selectors.primary_contact_names_for(account_ids).items() if name
    }


def _account_rows(term: str, limit: int, *, kind: str) -> list[dict[str, Any]]:
    """One ranked, capped page of accounts of `kind` (BR-CUS-068's column)."""
    from django.db.models import Q

    # ⚠ THE NAME CLAUSE CARRIES `deleted_at__isnull=True` IN THE SAME `Q`, NOT
    # BESIDE IT. Two separate filters would ask "this account has SOME matching
    # contact AND SOME undeleted contact" — which is true of an account whose
    # match is a DELETED contact and whose live contact is somebody else. Inside
    # one `Q` it is one join condition and asks the question meant: is there a
    # LIVE contact whose name matches. `_primary_contact_names` below already
    # excludes deleted rows, so without this a search on a removed person's name
    # returned their account labelled with a DIFFERENT person's name.
    matches = (
        Q(account_no__icontains=term)
        | Q(contact__full_name__icontains=term, contact__deleted_at__isnull=True)
        # `DEF-CUS-9776` — the name the row is LABELLED with is the current
        # customer's, so a clerk typing *Grace Fellowship* must find it. Same
        # one-`Q` rule as the contact clause: a live link, in one join.
        | Q(
            customeraccount__customer__display_name__icontains=term,
            customeraccount__ended_at__isnull=True,
        )
    )
    qs = models.Account.objects.filter(tenant_id=_tenant_id(), kind=kind).filter(matches)
    # A name match joins `contacts`, so one account with two matching contacts
    # would arrive twice. `distinct()` before the cap, or the cap counts a
    # duplicate as one of the five rows a clerk is allowed to see.
    qs = core_search.prefix_then_recency(qs.distinct(), term, _ACCOUNT_PREFIX_FIELDS)
    accounts = list(qs[:limit])
    names = _primary_contact_names([a.id for a in accounts])
    return [
        {
            "id": str(account.id),
            "label": account.account_no,
            "context": names.get(str(account.id)),
            "amount": None,
            "currency": None,
        }
        for account in accounts
    ]


def search_accounts(term: str, limit: int) -> list[dict[str, Any]]:
    """REGULAR accounts — the everyday occupant account (BR-CUS-068)."""
    return _account_rows(term, limit, kind=_account_kinds()[0])


def search_master_accounts(term: str, limit: int) -> list[dict[str, Any]]:
    """MASTER accounts — the premises' owner account over its common areas.

    Its own group by PO ruling 2026-09-03 rather than mixed in with the regular
    ones, and the ≤5 cap is why that matters: a master account is the rarer row,
    so in a shared group it is the one that falls off the bottom.
    """
    return _account_rows(term, limit, kind=_account_kinds()[1])


def search_customers(term: str, limit: int) -> list[dict[str, Any]]:
    """Customers by CUSTOMER NUMBER (the PO's *"customer id"*, BR-CUS-054).

    ⚠ `customer_no`, never `customers.id`. Reading *"customer id"* as the
    database id would put a uuid in the label — B14 rule 31 — on the very screen
    this feature is being built for, and the ruling of 2026-09-03 says so in as
    many words.
    """
    qs = models.Customer.objects.filter(tenant_id=_tenant_id()).filter(
        core_search.matches_any(term, ("customer_no",))
    )
    rows = list(core_search.prefix_then_recency(qs, term, ("customer_no",))[:limit])
    return [
        {
            "id": str(row.id),
            "label": row.customer_no,
            "context": row.display_name or None,
            "amount": None,
            "currency": None,
        }
        for row in rows
    ]


def search_requests(term: str, limit: int) -> list[dict[str, Any]]:
    """Service requests by REQUEST NUMBER.

    The context line is the applicant's name — the second thing a clerk checks
    after the number, and the reason they can tell two requests apart at all.
    The `state` is deliberately NOT appended: it is a machine token on this
    model (`submitted`, `under_review`) and printing it raw is the DEF-2417
    class of defect that the 2026-09-01 ruling closed. A state BADGE belongs to
    the requests list screen, which has the copy for it.
    """
    qs = models.ServiceRequest.objects.filter(tenant_id=_tenant_id()).filter(
        core_search.matches_any(term, ("request_no",))
    )
    rows = list(core_search.prefix_then_recency(qs, term, ("request_no",))[:limit])
    return [
        {
            "id": str(row.id),
            "label": row.request_no,
            "context": row.applicant_name or None,
            "amount": None,
            "currency": None,
        }
        for row in rows
    ]


def register() -> None:
    """Register this module's four groups with the BE-08 kernel.

    Called from `CustomersConfig.ready()`. `visible_to` is left at the default —
    every tenant role — because all four surfaces are served by `AnyTenantRole`
    today (A4: Accounts is Admin Full · Clerk Full · Executive View, and a
    search is a READ). BR-SHL-006's omission clause is what guards a future role
    that may not see one of them, and it is enforced in the kernel.
    """
    core_search.register_search_source("master_accounts", search_master_accounts)
    core_search.register_search_source("accounts", search_accounts)
    core_search.register_search_source("customers", search_customers)
    core_search.register_search_source("requests", search_requests)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-003 (EP-SHL-01) + the PO ruling of 2026-09-03 (BR-SHL-005 amended)
# generated: 2026-09-03 by story-coder (universal-search lane)
# checklist: A✔ B✔ C✔ D✔ E✔(the popover is wired in the same lane) F✔ G✔ H=deferred(PO)
# exceptions: `customers` matches customer_no ONLY and `bills` matches invoice_no
#         only — both narrowings are BR-SHL-005's "by their B2 identifiers" read
#         strictly, and both are recorded in the decision log with the reasoning
#         so a later widening is a decision rather than a drift
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
