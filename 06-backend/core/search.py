# ── Trace ──────────────────────────────────────────────
# Component: BE-08 search indexer contract (B13 §3, W0 kernel lane — component packet)
# Contract:  US-SHL-003 (topbar global search; IS-3 mechanics — server-side, min 2
#            chars, grouped popover) · `GET /search?q=` (PROPOSED A11 addition per
#            BR-SHL-005) · A4 addendum (all three roles see all four entities in v1)
# Rules:     BR-SHL-005 (scope accounts/premises+units/bills/payments; grouped ≤5/entity;
#            prefix-then-recency rank; per-group View-all) · BR-SHL-006 (runs under
#            app.tenant_id + RLS FORCE; role-invisible groups omitted)
# Tests:     06-backend/tests/test_be08_search.py (fake sources) · US-SHL-003/TC-1..8
#            land with the /search endpoint story (live selectors per module)
# Impacts:   GET /search endpoint · FE-01 AppShell topbar search · every module that
#            registers a source (customers, premises, billing, payments)
# ───────────────────────────────────────────────────────
"""BE-08 — the ONE global-search contract: modules register sources, the shell
queries them grouped, capped, tenant-scoped, and role-filtered.

Boundary law (B1/B8): core owns NO queries. Each module registers a source for
the entity it owns — the query_fn is that module's selector, so search reads
data only through its owner:

    core.search.register_search_source(
        "accounts", selectors.search_accounts, visible_to=permissions.ROLES)

Source contract:
- query_fn(q, limit) -> list of row dicts, ALREADY ranked prefix-match-first
  then most-recently-updated (BR-SHL-005 — ranking needs the module's columns,
  so it lives in the selector; this kernel enforces the cap, not the order).
- Each row is what the popover renders: identifier + one context line + the
  deep-link target (US-SHL-003). Shapes are per-entity; the kernel passes them
  through untouched.
- The query_fn runs under the AMBIENT tenant context — it never receives a
  tenant parameter, and RLS FORCE scopes every row it can see (BR-SHL-006).
  This kernel refuses to search at all without tenant context: a scope-less
  search would be a cross-tenant query, which is release-blocking law.

Group order is BR-SHL-005's — any future confirmed entity (registered by its
module) follows in registration order. ≤5 rows per group is enforced HERE
(defense in depth: the limit is passed to the source AND the returned list is
truncated). Role-invisible groups are omitted entirely (BR-SHL-006 — in v1 all
three roles read every one of these surfaces through `AnyTenantRole`, so the
parameter guards future roles rather than today's).

⚠ **BR-SHL-005 WAS AMENDED AGAIN 2026-09-05 AND THIS ORDER GREW FROM NINE TO
FIFTEEN (`CR-073`).** PO, verbatim: *"Extend universal search to include work
order , template, parts"*, then, on scope: *"Don't add reads and finance - add
work related items"*. Six groups append at positions 10–15 — `work_orders`,
`work_order_templates`, `parts`, `workforce`, `plans`, `charges` — and **nothing
above them is renumbered**, which is `CR-063`'s fire-at-position-11 posture and
is deliberate: renumbering would move every citation of every existing group at
once.

⚠ **READS AND FINANCE WERE EXCLUDED BY NAME AND ARE NOT AN OVERSIGHT.** A meter
read has no identifier a person quotes and finance's rows are ledger entries;
both were on the table and the PO removed them. Seven further surfaces were
considered and left out WITH REASONS — work-order rules, rate schedules, taxes,
discounts, rate changes and the module lookups — in `CR-073` §2a and in the two
sources' own docstrings. Read those before proposing a sixteenth group.

⚠ **BR-SHL-005 WAS AMENDED 2026-09-03 AND THIS ORDER GREW FROM FOUR TO NINE.**
PO, verbatim: *"Universal search will search premises , unit assets , master,
regular account , customer id, bill, payment, requests - if you have to increase
the length of search bar please increase it"*. Three of the nine are surfaces the
signed rule never contemplated (assets, customers, service requests) and the
master/regular split makes explicit what "accounts" left to inference.
**Everything else in BR-SHL-005 is unchanged and was not relaxed on the way
past**: ≤5 per group, prefix-then-recency, a per-group *View all*, and matching
on B2 IDENTIFIERS rather than on free text.

⚠ **THE RULING SAYS "EIGHT" AND ENUMERATES NINE — THE LIST IS THE CONTENT AND
THE NUMBER IS A POINTER TO IT (DEF-3460).** The PO's sentence has eight commas
because *"unit assets"* is one of them; the decision-log row that records the
ruling reads that as *"units · assets"* and lists nine. This module implements
the ENUMERATION. Anyone reconciling the two should count `GROUP_ORDER`, which is
the thing that runs.

IS-3 mechanics split: min-2-chars is enforced server-side here (a 1-char query
returns no groups, never an error); the 300 ms debounce and ✕-clear are the
frontend's half. Zero-result rendering (A18 §2) is the popover's job — the
kernel just returns no groups.
"""

import logging
import re
from collections.abc import Callable
from typing import Any

from core.tenancy import current_tenant_id

logger = logging.getLogger("smartbillhub.search")

# BR-SHL-005 AS AMENDED 2026-09-05 (CR-073): canonical group order, in the PO's
# own sequence; ≤5 rows per group; server-side min 2 chars (IS-3).
#
# ⚠ THE ORDER IS THE PO's SENTENCE, NOT ALPHABETICAL AND NOT THE SIDEBAR's.
# "premises , unit assets , master, regular account , customer id, bill,
# payment, requests" — a clerk reading the popover should meet the groups in the
# order they were asked for. `master_accounts` precedes `accounts` for the same
# reason, and because a premises master account is the rarer, harder-to-find row:
# below five regular accounts it would be the one crowded out of a ≤5 group,
# which is exactly why the PO named the two separately.
GROUP_ORDER: tuple[str, ...] = (
    "premises",
    "units",
    "assets",
    "master_accounts",
    "accounts",
    "customers",
    "bills",
    "payments",
    "requests",
    # ── CR-073, 2026-09-05 — APPENDED, AND NOTHING ABOVE IS RENUMBERED ──────
    # The PO named three (*"work order , template, parts"*) and then a category
    # (*"add work related items"*), so the first three are in their sentence's
    # order and `workforce` follows as the fourth Work group. `plans` and
    # `charges` come last because Plans & Rates was the other module left in
    # scope, and a reader meeting the popover should meet Work's four together.
    "work_orders",
    "work_order_templates",
    "parts",
    "workforce",
    "plans",
    "charges",
)
GROUP_LIMIT = 5
MIN_QUERY_CHARS = 2

SearchQueryFn = Callable[[str, int], list[dict[str, Any]]]

# entity -> (query_fn, roles that may see the group). Insertion order preserved
# for entities beyond the canonical four.
_sources: dict[str, tuple[SearchQueryFn, frozenset[str]]] = {}


def register_search_source(
    entity: str,
    query_fn: SearchQueryFn,
    *,
    visible_to: frozenset[str] | None = None,
) -> None:
    """Register (or replace) the ONE source for an entity. Modules call this in
    AppConfig.ready(); visible_to=None means every tenant role (A4 v1)."""
    if not entity:
        raise ValueError("an entity key is required (BR-SHL-005 group name)")
    from core import permissions  # local import: kernels stay decoupled at import time

    _sources[entity] = (query_fn, visible_to if visible_to is not None else permissions.ROLES)


def clear_search_sources() -> None:
    """Unregister everything — test isolation only."""
    _sources.clear()


def registered_entities() -> tuple[str, ...]:
    """All registered entity keys in serving order (canonical four first)."""
    canonical = [e for e in GROUP_ORDER if e in _sources]
    extra = [e for e in _sources if e not in GROUP_ORDER]
    return tuple(canonical + extra)


# ── BR-SHL-005's RANK, IN ONE PLACE ────────────────────────────────────────
#
# "ranked prefix-match-first then most-recently-updated". NINE sources share it
# now, and nine private copies of an ordering clause is nine chances for one of
# them to quietly become a plain `icontains` + `-updated_at` — which LOOKS
# right, passes any test that only checks membership, and silently demotes the
# exact identifier a clerk typed below four fuzzy matches.
#
# It lives here rather than in a module because it encodes the RULE, not any
# module's data: no table is named and no column is assumed — the caller passes
# both. Core still owns no queries; this takes a queryset and gives one back.
def prefix_then_recency(
    qs: Any,
    term: str,
    prefix_fields: tuple[str, ...],
    *,
    recency_field: str = "updated_at",
) -> Any:
    """Order `qs` by BR-SHL-005's rank: prefix matches first, then newest.

    `prefix_fields` are the columns a LEADING match counts on — the identifiers.
    A row matching any of them at position 0 sorts into band 0; everything else
    the caller's own filter admitted sorts into band 1. Inside a band the most
    recently updated row wins, and the primary key breaks a tie so the order is
    total (two rows written in one transaction share a timestamp often enough to
    make an unstable sort a flaky test).
    """
    from django.db.models import Case, IntegerField, Value, When

    whens = [When(**{f"{field}__istartswith": term}, then=Value(0)) for field in prefix_fields]
    return qs.annotate(
        _sbh_rank=Case(*whens, default=Value(1), output_field=IntegerField())
    ).order_by("_sbh_rank", f"-{recency_field}", "-id")


def matches_any(term: str, fields: tuple[str, ...]) -> Any:
    """`Q` matching `term` anywhere in any of `fields` — the ADMISSION half.

    Substring rather than prefix on purpose: BR-SHL-005 ranks prefix matches
    FIRST, which only means anything if non-prefix matches are in the set to be
    ranked below them. A prefix-only filter would make the rank unobservable and
    would lose "Cedar" → "Ridge Cedar Apartments" for no gain.
    """
    from django.db.models import Q

    condition = Q()
    for field in fields:
        condition |= Q(**{f"{field}__icontains": term})
    return condition


# ── WORD BY WORD — `CR-200-BRC10` S1 (PO 2026-10-29, Question 3 A) ──────────
#
# *"each typed word may match the address or the unit label"* — "12 Oak 2B"
# finds Apt 2B at 12 Oak St. `matches_any` matches the WHOLE phrase inside ONE
# field, so a phrase whose words live in two fields (street + unit label)
# matched nothing (`DEF-MET-10678`). This is the one shared matcher the staff
# address searches use; each module passes its OWN field list, so core still
# owns no query and names no column.
_WORD_SPLIT = re.compile(r"[\s,]+")


def search_words(term: str | None) -> list[str]:
    """The typed term as words: split on whitespace and commas, empties dropped."""
    return [word for word in _WORD_SPLIT.split(str(term or "").strip()) if word]


def matches_every_word(
    term: str | None,
    fields: tuple[str, ...],
    *,
    also: Callable[[str], Any] | None = None,
) -> Any:
    """`Q` admitting a row only when EVERY word matches at least one field.

    Each word is `matches_any(word, fields)` (substring, case-insensitive), and
    the words are ANDed. One word is therefore exactly `matches_any` — a search
    that worked before works the same. `also(word)` may add a `Q` a word can
    match INSTEAD of a field (a subquery such as *a unit inside this premises
    is labelled 2B*); it must be lazy so the whole search stays ONE statement
    (`NFR-3`). An empty term is an empty `Q()`, which admits everything — the
    caller decides whether an empty search narrows.
    """
    from django.db.models import Q

    condition = Q()
    for word in search_words(term):
        one = matches_any(word, fields)
        if also is not None:
            one |= also(word)
        condition &= one
    return condition


def rank_word(term: str | None) -> str:
    """The word `prefix_then_recency` ranks a multi-word term on: the FIRST.

    Decision log 2026-10-29 (`CR-200-BRC10` lane A): a clerk who leads with a
    number leads with it as the first word, and a whole phrase like "12 Oak 2B"
    can never be the START of an identifier, so ranking on it would put every
    multi-word search in the bottom band. For one word this is the term itself.
    """
    words = search_words(term)
    return words[0] if words else ""


def search(q: str, *, role: str) -> dict[str, list[dict[str, Any]]]:
    """One grouped search: {entity: rows} in serving order, empty groups omitted.

    Raises AUTH-003 without tenant context (BR-SHL-006: the query MUST execute
    under app.tenant_id + RLS FORCE — there is no lawful tenant-less search).
    """
    if current_tenant_id() is None:
        from core import errors

        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-SHL-006")

    query = (q or "").strip()
    if len(query) < MIN_QUERY_CHARS:
        return {}  # IS-3: below the minimum nothing runs — silence, not an error

    results: dict[str, list[dict[str, Any]]] = {}
    for entity in registered_entities():
        query_fn, visible_to = _sources[entity]
        if role not in visible_to:
            continue  # BR-SHL-006: role-invisible groups omitted entirely
        rows = query_fn(query, GROUP_LIMIT)
        if len(rows) > GROUP_LIMIT:
            # A source over-returning is a source bug — cap anyway (BR-SHL-005).
            logger.warning(
                "search source %r returned %d rows (cap %d)", entity, len(rows), GROUP_LIMIT
            )
            rows = rows[:GROUP_LIMIT]
        if rows:
            results[entity] = rows
    return results


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-08@05736ee (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-06..BE-09)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ black✔ pytest tests/test_be08_search.py 12/12✔ (live-selector TCs land with the /search endpoint story) · suite 147/147✔ · run_gates 10-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
# exceptions: none stubbed; E2-candidates reported to the PO batch via the build report (B13 BE-08 row scopes "accounts/premises/METERS/bills" but its governing rule BR-SHL-005 scopes accounts/premises+units/bills/payments — no meters; contract follows the CONFIRMED-adjacent BR, registry row flagged)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
