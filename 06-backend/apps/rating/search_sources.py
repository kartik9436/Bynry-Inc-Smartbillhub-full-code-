# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-003 (global search) — the `plans` and `charges` groups,
#           NEW 2026-09-05.  Screens: shell chrome (every authenticated screen)
# Change:   CR-073 — PO 2026-09-05, *"Don't add reads and finance - add work
#           related items"*, with Plans & Rates left in scope
# Rules:    BR-SHL-005 AS AMENDED 2026-09-05 (fifteen groups; ≤5;
#           prefix-then-recency; by their identifiers) · BR-SHL-006
#           (app.tenant_id + RLS FORCE; role-invisible groups OMITTED) ·
#           B14 rule 31 (no database id is ever the visible value of a field)
# Tests:    06-backend/tests/test_cr073_search_work_rating.py ·
#           06-backend/tests/test_cr073_search_isolation.py
# Impacts:  core.search registry (apps/rating/apps.py registers this) ·
#           GET /search (apps/tenancy/search_api.py)
# ───────────────────────────────────────────────────────
"""Plans & Rates' global-search sources — two groups, added by `CR-073`.

⚠ **THIS FILE IS NOT A 🔒 SENSITIVE PATH AND MUST NOT BECOME ONE.** The rating
module's MATH is 🔒 (B4, finance-signed and ❄️ FROZEN). Nothing here reads an
amount, a tier, a season, a time-of-use window or a formula: it reads two
catalogue columns, `code` and `name`, off two tables, and returns strings. **No
money rides in the `amount` field of either group** — a plan has no single
price and a charge code's amount is a SEED rather than a constant (`BR-RAT-035`,
and B4 §NSF says so in as many words), so printing one beside a search result
would state a figure the engine may not use.

WHAT WENT IN AND WHAT STAYED OUT
---------------------------------
The PO's scope ruling excluded reads and finance by name and left Plans & Rates
in. That module has a great deal of internal structure, so each of its six tabs
was put to the one question this feature asks — *does a person read this
somewhere else and then type it?* — and the answer was yes twice.

  · **Plans.** `code` (`RES-W`) and `name` (*Residential Water*), **both unique
    per tenant, case-insensitively**. A plan is what a clerk puts an account or
    a unit on, and it is named on the account screen they are looking at when
    they go to find it.
  · **Charge codes.** `code` (`LATE-FEE`) and `name` (*Late payment fee*).
    **This is the strongest quoting path in the product**: a charge code is
    printed on a bill LINE, and a customer telephoning about a line on their
    bill is the commonest reason anybody searches for anything.

**Left out, each with its reason** (`CR-073` §2a):

  · **Rate schedules (tariffs).** The tab's own search box matches `name` and
    nothing else, and a schedule is named *Water Residential 2026 v3* —
    structure, not a thing said out loud. It is reached from the plan that uses
    it, and the plan IS searchable.
  · **Taxes and fees.** Searched on the screen by name and AUTHORITY, which is
    a filter rather than an identifier; a tax is read off a bill as a line, and
    the bill is already a group.
  · **Discounts.** The closest call of the three, and it has a `code`. Left out
    because nothing prints a discount code anywhere a person reads it. It can
    be added at position 16 by the same posture that added these two, and this
    paragraph is here so that lane does not have to re-derive the question.
  · **Rate changes.** A batch, not a record anybody looks up by name.

BOTH COLUMNS ARE IDENTIFIERS HERE, AND BOTH RANK FIRST
-------------------------------------------------------
Unlike `parts` — where the number identifies and the description merely
describes — a plan's NAME and a charge's NAME are as much the thing a person
quotes as their codes are, and both are unique per tenant. So this is the
`assets` posture rather than the `parts` posture: **both columns in the prefix
band**, exactly as `asset_no` and `serial_no` are. It is also what each tab
claims to search (`["name", "code"]` and `["code", "name"]`, B14 rule 19), so
the box on the page and the box in the topbar cannot disagree.

⚠ The uuid is carried for the deep link and is NEVER rendered (B14 rule 31).
"""

from typing import Any

from core import errors
from core import search as core_search
from core import tenancy as core_tenancy

#: Both columns identify — see the module docstring.
_PLAN_FIELDS = ("code", "name")
_CHARGE_FIELDS = ("code", "name")


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-SHL-006")
    return tenant_id


def search_plans(term: str, limit: int) -> list[dict[str, Any]]:
    """Rate plans by code or name.

    The context line is the plan's NAME beside its code — the label is the
    code, because that is the shorter thing a clerk quotes — and its status
    where the plan is not published, so a draft is never mistaken for something
    an account can be put on today (`BR-RAT-030`).
    """
    from apps.rating import models as rating_models

    qs = rating_models.RatePlan.objects.filter(tenant_id=_tenant_id()).filter(
        core_search.matches_any(term, _PLAN_FIELDS)
    )
    rows = list(core_search.prefix_then_recency(qs, term, _PLAN_FIELDS)[:limit])
    result: list[dict[str, Any]] = []
    for row in rows:
        parts = [row.name]
        # Stated only when it is NOT the ordinary case, which is B14 rule 32's
        # budget: a published plan needs no word, a draft or archived one does.
        if row.status and row.status != "published":
            parts.append(row.status)
        result.append(
            {
                "id": str(row.id),
                "label": row.code,
                "context": " · ".join(part for part in parts if part) or None,
                "amount": None,
                "currency": None,
            }
        )
    return result


def search_charges(term: str, limit: int) -> list[dict[str, Any]]:
    """Charge codes by code or name.

    The context line is the charge's NAME and, where it is scoped to one
    service, that service — because `LATE-FEE` for water and `LATE-FEE` for
    electric are different rows to a tenant that scopes them (`charges.service`
    is NULL for *any service*).

    ⚠ **NO AMOUNT.** `charges.amount` is a SEED, never a constant (`BR-RAT-035`,
    B4 §NSF) — the engine resolves what is actually charged from the plan and
    the tariff version in force. A figure printed here would be read as the
    price and would be wrong the moment a plan overrode it.
    """
    from apps.rating import models as rating_models

    qs = (
        rating_models.Charge.objects.filter(tenant_id=_tenant_id())
        .select_related("service")
        .filter(core_search.matches_any(term, _CHARGE_FIELDS))
    )
    rows = list(core_search.prefix_then_recency(qs, term, _CHARGE_FIELDS)[:limit])
    result: list[dict[str, Any]] = []
    for row in rows:
        parts = [row.name]
        if row.service_id and row.service is not None:
            parts.append(row.service.name)
        result.append(
            {
                "id": str(row.id),
                "label": row.code,
                "context": " · ".join(part for part in parts if part) or None,
                "amount": None,
                "currency": None,
            }
        )
    return result


def register() -> None:
    """Register the two Plans & Rates groups with the BE-08 kernel.

    Called from `RatingConfig.ready()`. Default `visible_to` — every tenant
    role — because both screens read through `AnyTenantRole`-equivalent
    read-any routes, so a narrower group would make search disagree with the
    screens. `BR-SHL-006`'s omission clause lives in the kernel and guards a
    future role.
    """
    core_search.register_search_source("plans", search_plans)
    core_search.register_search_source("charges", search_charges)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-003 (EP-SHL-01) + CR-073 (PO rulings of 2026-09-05)
# generated: 2026-09-05 by the CR-073 universal-search lane
# checklist: A✔ B✔ C✔ D✔ E✔(the popover is wired in this lane) F✔ G✔ H=deferred(PO)
# exceptions: E3 rate schedules, taxes, discounts and rate changes are NOT
#         groups — each considered and left out with its reason in the module
#         docstring and CR-073 §2a · E3 neither group carries money, and the
#         reason is BR-RAT-035's seed-not-constant rule rather than tidiness
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
