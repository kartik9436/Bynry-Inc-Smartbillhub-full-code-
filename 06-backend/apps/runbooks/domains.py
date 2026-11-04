# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-039 (EP-RBS-05) — CR-075 wave T: inputs with tenant-resolved
#           domains.
# Rules:    BR-RBS-042 (a runbook is one fixed process with declared inputs; a
#           domain per input, resolved PER TENANT; one value, several, or *all*;
#           *all* stored as the WORD and resolved at run start) · BR-RBS-009
#           (scope resolved once and pinned — which is where *all* resolves) ·
#           BR-RBS-039 (every foreign read goes through this module's own seam)
#           · NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
#           B14 rule 31 (no database id is ever the visible value of a field)
# Tests:    06-backend/tests/test_us_rbs_039_inputs.py
# Impacts:  apps/runbooks/services.py (run_parameters) · apps/runbooks/api.py
#           (GET /runbooks/{key}/domains/{parameter}) · contract.DOMAINS
# ───────────────────────────────────────────────────────
"""WHAT A TENANT MAY CHOOSE FROM — read from the tenant's own data, every time.

`BR-RBS-042` clause 2, PO verbatim 2026-09-06: *"please note every utility will
not have all utility services or all combinations of Plans and rates, so we ahve
to work in variables"*. **A two-service utility's *Services* list offers two.**
A hardcoded list of eleven offers a utility services it does not sell, and an
input set to one of them filters every run down to nothing while the screen
looks perfectly healthy.

TWO ENTRY POINTS, AND THEY ANSWER DIFFERENT QUESTIONS
------------------------------------------------------
* `page(name, …)` — **what a person may pick**, one page at a time. The setup
  screen's picker asks this.
* `members(name)` — **every value in the domain**, which is what the word *all*
  expands to when a RUN starts. Nothing draws this; `services.run_parameters()`
  is its only caller.

⚠ **THEY ARE DELIBERATELY NOT THE SAME FUNCTION.** A screen must never read the
whole of an unbounded domain (`NFR-3`), and a run must never see only a page of
one. Writing one function for both is how a run silently acts on the first fifty
accounts of forty thousand — a truncation that looks like a completed run.

WHY `all` IS THE WORD AND NEVER A LIST — the clause a build gets wrong
----------------------------------------------------------------------
Store `["water", "sewer"]` at the moment an admin presses Save and the utility
that enables **Trash** next month is silently outside every runbook set to
*all*: no error, no screen change, nothing anywhere to see. `PARAM_ALL` is
stored, and this module expands it **when the run starts**, after which
`BR-RBS-009` pins the resolved set for that run. A utility that sets *all
services* with Water and Sewer gets **three** on the next run after Trash
arrives, with nothing to reconfigure.

WHAT IS BOUNDED AND WHAT IS NOT, DECLARED RATHER THAN ASSUMED
---------------------------------------------------------------
`DOMAIN_IS_BOUNDED` says, per domain, whether its size is a fact about the
PLATFORM or a fact about the UTILITY:

* `service` — **bounded**: eleven in the catalogue, of which a tenant enables
  some. Reading all of them is one small read and `members()` is cheap.
* `period` — **bounded**: the accounting months this tenant has POSTED into.
  One row per month the books hold, so it grows by twelve a year and by nothing
  else. `ledger.selectors.posted_months` is the read and its own docstring gives
  the reasoning: *the last twelve months* would offer eleven empty files to a
  utility that went live in August.
* `account` — **unbounded**: 40,000 at the top of T5 and no ceiling above it
  (`NFR-5`). Its page is sliced **in SQL** inside `customers_seam`, and it may
  not be a `multi` domain until somebody has a reason for *all accounts* that a
  pinned set of forty thousand can honour.

⚠ **THE BOUNDED FLAG IS ENFORCED, NOT DOCUMENTED.** `members()` refuses an
unbounded domain by name. A `multi` parameter over `account` would otherwise
make *all* mean *read every account row into memory to compose a scope*, which
is the shape `NFR-3` exists to stop, and it would arrive as a one-word change to
a definition.

WHAT AN EMPTY DOMAIN DOES
-------------------------
It says so. `page()` returns zero rows and a `total` of `0`; the screen draws a
sentence rather than an empty dropdown, which reads as broken (`TC-RBS-039.3`).
Nothing here invents a placeholder row.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from apps.runbooks import contract
from apps.runbooks.seams import customers_seam, ledger_seam, tenancy_seam

#: Is this domain's size a fact about the PLATFORM (bounded) or about the
#: UTILITY (unbounded)? See the module docstring — `members()` refuses an
#: unbounded domain rather than reading forty thousand rows to expand a word.
DOMAIN_IS_BOUNDED: dict[str, bool] = {
    contract.DOMAIN_SERVICE: True,
    contract.DOMAIN_PERIOD: True,
    contract.DOMAIN_ACCOUNT: False,
}


class UnknownDomain(LookupError):
    """A domain name nothing resolves. A caller's bug, never a clerk's refusal."""


def _service_rows() -> list[dict[str, str]]:
    """Every service this tenant SELLS, in catalogue order, with its own name.

    `tenancy_seam.service_basis()` already filters to `enabled`, and its own
    docstring records why the two-state *is it metered* question is retired: a
    `share` service like sewer has no unit BY DESIGN and asking the wrong
    question reddened sewer at every utility that sells it (`DEF-2409`).

    ⚠ **`value` IS THE SERVICE CODE AND `label` IS THE TENANT'S OWN NAME.** The
    code is a stable business code rather than a database id, so it is what a
    stored parameter points at; the chip on screen shows the name. B14 rule 31
    is about what a field RENDERS.
    """
    return [
        {"value": str(row["service"]), "label": str(row.get("name") or row["service"])}
        for row in tenancy_seam.service_basis()
    ]


def _service_page(*, q: str, page: int, per: int) -> dict[str, Any]:
    """The services domain, paged.

    ⚠ **IT PAGES IN PYTHON AND THAT IS LAWFUL HERE, WHICH IS WHY IT IS SAID OUT
    LOUD.** `NFR-3` is about serving a set whose size grows with the utility
    without a page — the four breaches CLAUDE.md names are all of that shape.
    This set is the ENABLED SUBSET OF AN ELEVEN-ROW PLATFORM CATALOGUE, so the
    whole of it is already in memory the moment `tenancy` answers, and slicing
    it costs nothing. The route still pages it, because a picker that pages for
    one domain and not another is a client that has to know which is which.
    """
    rows = _service_rows()
    term = q.strip().casefold()
    if term:
        rows = [row for row in rows if term in row["label"].casefold() or term in row["value"]]
    start = max(0, (max(1, page) - 1) * max(1, per))
    return {"rows": rows[start : start + max(1, per)], "total": len(rows)}


def _period_rows() -> list[dict[str, str]]:
    """Every accounting month this tenant has posted into, oldest first.

    ⚠ **THE VALUE IS `YYYY-MM` AND IT IS THE ACCOUNTING EXPORT'S OWN LABEL.**
    `definitions/accounting_export.month_label` composes exactly this string and
    `resolve()` matches a saved value against it, so the picker and the run
    agree on one spelling of a month. Changing this format is changing what a
    saved parameter means, which is why the two are stated together rather than
    left to be inferred.

    ⚠ **POSTED ONLY.** A month whose only entries are drafts is not an
    accounting month, and offering it would produce a file of zeroes that reads
    as *"nothing happened in July"* — `ledger.selectors.posted_months` draws
    that line and this repeats none of it.
    """
    return [
        {"value": f"{first.year:04d}-{first.month:02d}", "label": f"{first.year:04d}-{first.month:02d}"}
        for first, _last in ledger_seam.posted_months()
    ]


def _period_page(*, q: str, page: int, per: int) -> dict[str, Any]:
    """The posted-months domain, paged. Bounded by the books' own age."""
    rows = _period_rows()
    term = q.strip()
    if term:
        rows = [row for row in rows if term in row["value"]]
    start = max(0, (max(1, page) - 1) * max(1, per))
    return {"rows": rows[start : start + max(1, per)], "total": len(rows)}


def _account_page(*, q: str, page: int, per: int) -> dict[str, Any]:
    """The accounts domain, sliced in SQL by the seam — see `customers_seam`."""
    return dict(customers_seam.account_domain_page(q=q, page=page, per=per))


#: One resolver per domain. Adding a row here is the whole of adding a domain,
#: and it is why `contract.DOMAINS` is closed: a name with no row is a picker
#: that draws nothing, and a row with no name is unreachable.
_PAGERS: dict[str, Callable[..., dict[str, Any]]] = {
    contract.DOMAIN_SERVICE: _service_page,
    contract.DOMAIN_PERIOD: _period_page,
    contract.DOMAIN_ACCOUNT: _account_page,
}


def page(name: str, *, q: str = "", page: int = 1, per: int = 50) -> dict[str, Any]:
    """One page of a domain, as `{"rows": [{value, label}], "page", "per", "total"}`.

    The same four keys every selector in this module returns, so `api._envelope`
    renames them to `{count, next, previous, results}` exactly as it does for
    every other list — `07-frontend/src/api/paginated.ts` is the ONE description
    of those four names on the client and `G114` fails a second one.
    """
    if name not in _PAGERS:
        raise UnknownDomain(name)
    size = max(1, int(per))
    number = max(1, int(page))
    answer = _PAGERS[name](q=str(q or ""), page=number, per=size)
    return {
        "rows": list(answer["rows"]),
        "page": number,
        "per": size,
        "total": int(answer["total"]),
    }


def members(name: str) -> tuple[str, ...]:
    """Every value in a BOUNDED domain — what the word *all* expands to.

    Called once, when a run starts (`services.run_parameters`), and never by a
    screen. `BR-RBS-009` pins whatever this returns for the life of that run.
    """
    if name not in _PAGERS:
        raise UnknownDomain(name)
    if not DOMAIN_IS_BOUNDED.get(name, False):
        raise UnknownDomain(
            f"domain {name!r} grows with the utility — 40,000 accounts at the top of T5 — so "
            "'all' of it cannot be expanded into a pinned set here (NFR-3). A multi-value input "
            "over an unbounded domain needs a scope the engine resolves in SQL, not a word."
        )
    if name == contract.DOMAIN_SERVICE:
        return tuple(row["value"] for row in _service_rows())
    if name == contract.DOMAIN_PERIOD:
        return tuple(row["value"] for row in _period_rows())
    raise UnknownDomain(name)  # pragma: no cover — the map above is exhaustive


def labels(name: str, values) -> dict[str, str]:
    """`{value: label}` for values a tenant has ALREADY CHOSEN — never the domain.

    ⚠ **B14 RULE 31 IS THE WHOLE REASON THIS IS SEPARATE FROM `page()`.** A
    saved `ref:object` value is an account id; a Scope row that printed it would
    put a uuid on a clerk's screen. `page()` cannot help — the chosen account
    may be on page 700 of the picker — so the labels for a CHOICE are resolved
    by id, and the read is bounded by how many a person picked rather than by
    how many the utility has.

    An unresolvable value comes back missing rather than as itself, so a caller
    can tell *"this account was deleted"* from *"this account is called 40021"*.
    """
    wanted = [str(one) for one in (values or []) if one is not None]
    if not wanted:
        return {}
    if name == contract.DOMAIN_ACCOUNT:
        return {k: v for k, v in customers_seam.account_labels(wanted).items() if v}
    if name == contract.DOMAIN_SERVICE:
        rows = {row["value"]: row["label"] for row in _service_rows()}
        return {one: rows[one] for one in wanted if one in rows}
    if name == contract.DOMAIN_PERIOD:
        rows = {row["value"]: row["label"] for row in _period_rows()}
        return {one: rows[one] for one in wanted if one in rows}
    raise UnknownDomain(name)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-039 (EP-RBS-05; CR-075 wave T) · BR-RBS-042 (PO 2026-09-06, quoted verbatim in 02-business-rules.md) · BR-RBS-009 · NFR-3 · NFR-5
# generated: 2026-09-07 by the CR-075 wave T build lane
# checklist: A✔ B=n/a(no screen in this file) C✔ D✔(GET /runbooks/{key}/domains/{parameter}) E=n/a F✔ G✔ H=n/a(no 🔒 path — no money, no idempotency key, no ledger line; the wave's MIGRATION is 🔒 and carries its own marker and ledger row)
# gates: pytest tests/test_us_rbs_039_inputs.py · G115 (every foreign read resolves to a seam) · G6 (no ORM in api.py)
# exceptions: `_service_page` slices in Python and says why in its own docstring — the set is the enabled subset of an eleven-row PLATFORM catalogue, not a per-tenant list that grows
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
