# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-003 (global search) — the `work_orders`,
#           `work_order_templates`, `parts` and `workforce` groups, NEW
#           2026-09-05.  Screens: shell chrome (the topbar popover, every
#           authenticated screen)
# Change:   CR-073 — PO 2026-09-05, *"Extend universal search to include work
#           order , template, parts"* and *"Don't add reads and finance - add
#           work related items"*
# Rules:    BR-SHL-005 AS AMENDED 2026-09-05 (fifteen groups; ≤5;
#           prefix-then-recency; by their identifiers) · BR-SHL-006
#           (app.tenant_id + RLS FORCE; role-invisible groups OMITTED) ·
#           BR-WRK-002 (Work reads other modules only through seams/ and
#           writes none of them — G78) · BR-MET-1161 (an address is derived by
#           walking to the premises) · B14 rule 31 (no database id is ever the
#           visible value of a field)
# Tests:    06-backend/tests/test_cr073_search_work_rating.py ·
#           06-backend/tests/test_cr073_search_isolation.py
# Impacts:  core.search registry (apps/work/apps.py registers this) ·
#           GET /search (apps/tenancy/search_api.py)
# ───────────────────────────────────────────────────────
"""The Work module's global-search sources — four groups, added by `CR-073`.

WHAT A PERSON QUOTES, WHICH IS THE ONLY QUESTION THIS FILE ANSWERS
------------------------------------------------------------------
`BR-SHL-005` says these groups match on IDENTIFIERS rather than on free text,
so each source below had to decide what its identifier actually is. The rule
for the decision is not "what is unique" — it is **what does a person read
somewhere else and then type into the box**.

  · **A work order** is `WO-0011`. One identifier, and it is the number on the
    dispatch board, on the phone call and in the audit line.
  · **A template** is *Meter set*. It ALSO carries `template_no` (`ST-0004`)
    since `CR-070` wave C — **both are searched** (see below).
  · **A part** is `MTR-W58` **and** *Water meter*, and those two are NOT the
    same kind of thing (see below).
  · **A person or a crew** is a NAME, and the three kinds are ONE group
    (see below).

⚠ **THE uuid IS CARRIED FOR THE DEEP LINK AND FOR NOTHING ELSE** (B14 rule 31,
ratified as *"no Databse ID on screen - that is a rule"*). It is never the
label and never the context line. `assets/search_sources.py` spells the same
trap out for three identifiers; every group here has the same shape.

THE TEMPLATE'S TWO NUMBERS — AND WHY THE NAME IS THE LABEL
-----------------------------------------------------------
`work_order_templates.template_no` is `ST-0004`, allocated from the tenant's
own series **on publish** and therefore NULL on every draft and on all 24
seeded starters (`BR-WRK-021`). So it cannot be the label: two thirds of a
tenant's templates would render an absence. **The NAME is the label and both
columns are searched**, with `template_no` in the prefix band beside the name —
the `assets` posture, where `asset_no` and `serial_no` are both quotable and
both rank first. The number rides in the CONTEXT line when it exists.

THE PART'S NUMBER AND ITS DESCRIPTION ARE NOT THE SAME KIND OF THING
---------------------------------------------------------------------
`apps/assets/search_sources.py` faced the neighbouring question — a
MANUFACTURER'S serial versus OUR asset number — and put **both** in the prefix
band, because both are identifiers in the same sense and demoting one would put
the wrong meter first for the person most likely to be reading it.

**This is a different question and it gets a different answer.** `part_no` is
an identifier; `name` is a DESCRIPTION. *Water meter 5/8"* is not a thing that
identifies one row — a tenant may hold six of them from three suppliers. So:

  · `part_no` alone is in the PREFIX band, and a `MTR-` prefix always wins;
  · `name` is in the MATCH band, so typing *Water meter* still finds the part,
    ranked below any part number that starts with what was typed.

That is exactly the split `core.search.matches_any` was built to express, and
its own docstring gives the reasoning: substring admission exists so that
non-prefix matches are *in the set to be ranked below* prefix ones. It also
matches what the parts screen itself claims to search (`searchFields:
["part_no", "name"]`, B14 rule 19), so the box at the top of the page and the
box in the topbar cannot disagree.

ONE WORKFORCE GROUP, NOT THREE — BECAUSE THE SCREEN IS ONE TABLE
------------------------------------------------------------------
`Work-023` draws people, crews and contractors as rows in ONE table with one
sort (*people first, then name*), and `workforce.crews_page` composes exactly
that list. Search follows the screen (B14 rule 20's one-table law read across
to this surface): three groups in the popover would present a division the
product does not otherwise make, and would let a crew crowd out a person from a
≤5 cap for reasons a reader could not see.

⚠ **A PERSON'S NAME IS NOT WORK'S COLUMN — IT IS IDENTITY'S**, so this source
reads it through `seams/identity_seam.py`'s join and never imports
`apps.identity.models` (`BR-WRK-002`; G78 fails the import, not just the
write). A technician with no name yet falls back to their email, which is what
`workforce.technician_slug` already does and for the same reason: an invited
login has no name and a blank row is not a row.

⚠ **AND THE WORKFORCE ROW OPENS THE LIST, NOT A DETAIL SCREEN — DELIBERATELY.**
A technician HAS a detail screen (`/work/crews/:slug`); a crew and a contractor
do NOT. One group cannot carry two destinations through `resultPath`, and a
link that resolves for two thirds of its rows and 404s for the rest is worse
than one that always lands somewhere true. So every workforce row opens
`/work/crews?q=<name>` — the crews list filtered to that row, which is the
`customers`/`payments` precedent in `searchDestinations.ts`. **REPORTED rather
than smoothed over**, and the honest cost is one extra click for a person.

WHY THE TABLES ARE REACHED THE WAY THEY ARE
--------------------------------------------
`parts` is Work's OWN table (`apps/work/models.py`) and is read directly.
`work_orders` and `work_order_templates` are still METERING's rows — they live
in `apps/metering/connections.py` and `03-field-map.md` §4 has not yet said
where they move — so they are read through `seams/metering_seam.py`, which is
the whole point of the seam: when the models relocate, that file changes and
this one does not.

WHAT IS NOT HERE, AND WHY — reported, not silently skipped
-----------------------------------------------------------
* **`work_order_rules`.** Considered and left out. Its `name` is a real
  identifier — unique per tenant, and printed on `Work-007` after *Raised by:*
  — but **`App.tsx` serves `/work/rules` and `/work/rules/new` and no detail
  route**, so a result row could only open a single short page a tenant has
  five rows on. A group whose best outcome is *the screen you would have
  clicked anyway* earns nothing (`CR-073` §2a).
* **`work_orders.external_ref`** — the contractor's OWN reference on an
  `external`-mode order. Not searched, for the reason `assets` does not search
  `external_ref`: it is a third party's identifier with a different owner, and
  folding it into the same column as `order_no` makes a field that holds
  either.
* **`work_orders.type`** (the free-text job kind) and `type_ref.name`. The
  dispatch list matches both because its box says *Search WO #, premise…*;
  universal search matches identifiers, and *Meter set* typed here is answered
  by the TEMPLATE group, which is the row a person actually wants.
* **Skills, safety kits, part categories, priorities, order types, template
  child rows, device registrations, cost lines.** Structure — picked from a
  list on the screen that owns them, never looked up.
"""

from typing import Any

from core import errors
from core import search as core_search
from core import tenancy as core_tenancy

#: `WO-0011`. One identifier and one band — see the module docstring.
_ORDER_PREFIX_FIELDS = ("order_no",)
_ORDER_MATCH_FIELDS = ("order_no",)

#: The name AND the published number both rank first (the `assets` posture).
_TEMPLATE_PREFIX_FIELDS = ("name", "template_no")
_TEMPLATE_MATCH_FIELDS = ("name", "template_no")

#: ⚠ THE BANDS DIFFER ON PURPOSE — the number identifies, the name describes.
_PART_PREFIX_FIELDS = ("part_no",)
_PART_MATCH_FIELDS = ("part_no", "name")


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-SHL-006")
    return tenant_id


def search_work_orders(term: str, limit: int) -> list[dict[str, Any]]:
    """Work orders by their number.

    The context line is the job kind and where it is — *Meter set · 77 Cedar
    Ct* — which is what tells five `WO-01…` numbers apart on a dispatch board.

    ⚠ **AN ORDER WITH NO NUMBER CANNOT APPEAR HERE, AND THAT IS THE RULE
    WORKING RATHER THAN A GAP BEING HIDDEN.** `order_no` is nullable
    (`metering/0044`) and a NULL never matches `icontains`, so such a row is
    excluded by construction. It has no identifier to render, and rule 31
    forbids falling back to its uuid. The dispatch list is where a numberless
    order surfaces — it also matches type and address.
    """
    from apps.work import selectors as work_selectors
    from apps.work.seams import metering_seam

    qs = metering_seam.search_work_orders_queryset().filter(
        core_search.matches_any(term, _ORDER_MATCH_FIELDS)
    )
    rows = list(core_search.prefix_then_recency(qs, term, _ORDER_PREFIX_FIELDS)[:limit])
    result: list[dict[str, Any]] = []
    for row in rows:
        # The catalogue name when the order carries one, else the words a clerk
        # typed (BR-WRK-017 keeps both, and an unmatched string stays a string).
        kind = row.type_ref.name if row.type_ref_id and row.type_ref is not None else row.type
        parts = [part for part in (kind,) if part]
        # BR-MET-1161 — the address is WALKED to, through the module's own
        # walk, so a search result and the row on the board cannot disagree
        # about where a job is.
        premise = work_selectors._premise_of(row)
        if premise and premise.get("address"):
            parts.append(premise["address"])
        result.append(
            {
                "id": str(row.id),
                "label": row.order_no,
                "context": " · ".join(parts) or None,
                "amount": None,
                "currency": None,
            }
        )
    return result


def search_work_order_templates(term: str, limit: int) -> list[dict[str, Any]]:
    """Work-order templates by name, and by their published number.

    The context line names the SERVICE, because that is the column that tells
    four templates called *Meter set* apart (`BR-WRK-010`), plus the number
    where the template has been published and therefore has one.
    """
    from apps.work.seams import metering_seam

    qs = metering_seam.search_work_order_templates_queryset().filter(
        core_search.matches_any(term, _TEMPLATE_MATCH_FIELDS)
    )
    rows = list(core_search.prefix_then_recency(qs, term, _TEMPLATE_PREFIX_FIELDS)[:limit])
    result: list[dict[str, Any]] = []
    for row in rows:
        parts: list[str] = []
        if row.service_id and row.service is not None:
            parts.append(row.service.name)
        # Shown only when it exists AND was not the thing typed — B14 rule 32's
        # repetition clause, the same read `assets` makes of a serial.
        if row.template_no and row.template_no.lower() != (term or "").lower():
            parts.append(row.template_no)
        result.append(
            {
                "id": str(row.id),
                "label": row.name,
                "context": " · ".join(parts) or None,
                "amount": None,
                "currency": None,
            }
        )
    return result


def search_parts(term: str, limit: int) -> list[dict[str, Any]]:
    """Parts by part number, and by description ranked below it.

    ⚠ **NO PRICE RIDES IN THE `amount` FIELD, THOUGH `parts.unit_cost` IS
    MONEY.** The popover's money slot is for what a row IS worth to the person
    reading it — a bill's total, a payment's amount. A part's unit cost is a
    catalogue price that means nothing without a quantity, and printing
    `$92.40` beside `MTR-W58` in a search result invites it to be read as the
    cost of a job. `Work-025` is where it belongs, with its unit beside it
    (hard rule 3).
    """
    from apps.work import models as work_models

    qs = work_models.Part.objects.filter(tenant_id=_tenant_id()).select_related("category")
    qs = qs.filter(core_search.matches_any(term, _PART_MATCH_FIELDS))
    rows = list(core_search.prefix_then_recency(qs, term, _PART_PREFIX_FIELDS)[:limit])
    result: list[dict[str, Any]] = []
    for row in rows:
        parts = [row.name]
        if row.category_id and row.category is not None:
            parts.append(row.category.name)
        result.append(
            {
                "id": str(row.id),
                "label": row.part_no,
                "context": " · ".join(part for part in parts if part) or None,
                "amount": None,
                "currency": None,
            }
        )
    return result


def search_workforce(term: str, limit: int) -> list[dict[str, Any]]:
    """People, crews and contractors — ONE group, in the crews screen's order.

    ⚠ **TWO TABLES, ONE GROUP, AND THE CAP IS APPLIED TO THE MERGED LIST.**
    Taking five from each table and then merging would let a crew push a person
    off a ≤5 group depending only on which query ran first. The two are ranked
    independently (each source table has its own columns), merged in the
    screen's own order — **people first, then name** — and cut to `limit` once.

    The context line is the row's ROLE (*Senior technician*, *Network crew*),
    which is `Work-023`'s own second column and the thing that distinguishes
    two people with similar names.
    """
    from apps.work import models as work_models

    tenant_id = _tenant_id()

    technicians = (
        work_models.Technician.objects.filter(tenant_id=tenant_id)
        .select_related("user")
        .filter(core_search.matches_any(term, ("user__full_name", "user__email")))
    )
    technicians = core_search.prefix_then_recency(
        technicians, term, ("user__full_name", "user__email")
    )[:limit]

    crews = work_models.Crew.objects.filter(tenant_id=tenant_id).filter(
        core_search.matches_any(term, ("name",))
    )
    crews = core_search.prefix_then_recency(crews, term, ("name",))[:limit]
    # `CR-168-BRC10` P3.44 — the bracket is the COUNTED members, the same figure
    # `workforce.crews_page` serves; the typed `headcount` is no longer read.
    from apps.work import workforce

    members = {
        str(row.id): row.members
        for row in work_models.Crew.objects.filter(id__in=[c.id for c in crews]).annotate(
            members=workforce._member_counts()
        )
    }

    result: list[dict[str, Any]] = []
    for row in technicians:
        # The identity seam's own fallback, restated here because this row is
        # the visible label: an invited login has no name yet.
        name = (row.user.full_name or row.user.email or "").strip()
        if not name:
            continue
        result.append(
            {
                "id": str(row.id),
                "label": name,
                "context": row.role_label or None,
                "amount": None,
                "currency": None,
            }
        )
    for row in crews:
        # *Crew B (3)* — the headcount is part of the NAME on screen, composed
        # here exactly as `workforce.crews_page` composes it, so the count in a
        # search result and the count on the row are ONE fact.
        count = members.get(str(row.id), 0)
        label = f"{row.name} ({count})" if count else row.name
        result.append(
            {
                "id": str(row.id),
                "label": label,
                "context": row.role_label or None,
                "amount": None,
                "currency": None,
            }
        )
    return result[:limit]


def register() -> None:
    """Register the four Work groups with the BE-08 kernel.

    Called from `WorkConfig.ready()`. Default `visible_to` — every tenant role
    — and that is a MEASURED choice rather than a default taken quietly: every
    read route behind these four surfaces is read-by-all-three today
    (`work_orders` is `WorkOrdersReadAnyWriteAdminOrClerk`, `parts` and
    `templates` are `SettingsReadAnyWriteSystemAdmin`, crews is
    `AnyTenantRole`), so narrowing the group would make search disagree with
    the screens — a row a role can open but cannot find reads as broken data.

    `BR-SHL-006`'s omission clause is enforced in the kernel, where it cannot
    be forgotten, and guards the day this product grows a dispatcher role that
    a billing clerk is not.
    """
    core_search.register_search_source("work_orders", search_work_orders)
    core_search.register_search_source("work_order_templates", search_work_order_templates)
    core_search.register_search_source("parts", search_parts)
    core_search.register_search_source("workforce", search_workforce)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-003 (EP-SHL-01) + CR-073 (PO rulings of 2026-09-05)
# generated: 2026-09-05 by the CR-073 universal-search lane
# checklist: A✔ B✔ C✔ D✔ E✔(the popover is wired in this lane) F✔ G✔ H=deferred(PO)
# exceptions: E3 `work_order_rules` is NOT a group — considered, and left out
#         because no rule detail route exists (CR-073 §2a) · E3
#         `work_orders.external_ref` and the free-text `type` are NOT searched
#         — reported, with reasons, in the module docstring · E3 the workforce
#         row opens the crews LIST rather than a detail screen, because the
#         group is mixed and only a person has one
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
