# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-005 (AR aging + DSO) · US-REP-006 (Billing register +
#           Revenue by service & rate) · US-REP-007 (Payments by method) ·
#           US-REP-002 (the viewer's LIVE parameter vocabularies)
#           Screens: S44 · S46
# Rules:    BR-REP-002 (a report is a READ-MODEL over the owning module's rows,
#           never a side-maintained number) · BR-REP-006 (filters enumerate
#           LIVE vocabularies, never a hardcoded list) · BR-REP-024 (a surface
#           renders the OWNER's figure or reports by name that it cannot
#           answer — never 0, never a client-side sum) · B1 / BR-TEN-013 (a
#           module never touches a neighbour's ORM)
# Tests:    06-backend/tests/test_us_rep_canned_reports.py
# Impacts:  apps/reports/queries.py (the ONLY caller) · this file reads and
#           writes nothing, anywhere
# ───────────────────────────────────────────────────────
"""reports → other-module SEAMS for the S44 catalogue and the S46 viewer.

`dashboard_seams.py` is the twin of this file and carries the full argument for
why it exists (DEF-104: four surfaces disagreed about one balance; DEF-075: a
seam that could not answer returned a falsy value and a tenant's books were
re-denominated at HTTP 200). The rule both files enforce is BR-REP-024:

    RENDER THE OWNER'S FIGURE, OR REPORT BY NAME THAT YOU CANNOT ANSWER.

`None` from any function here means *the owner does not publish this read* — it
never means zero, and `apps/reports/queries.py` turns every one into an entry
the screen renders as a sentence in the user's own language.

════════════════════════════════════════════════════════════════════════════
THE CONTRACTS — all WIRED, and each names the module that owns the fact
════════════════════════════════════════════════════════════════════════════
  apps.billing.reporting.billing_register(*, start, end, bill_type=None,
                                          service_code=None) -> dict
      Every bill ISSUED in the window (POSTING basis), typed, with its usage in
      its own units. Billing owns `invoices`; reports may not read them.

  apps.billing.reporting.revenue_by_service_and_rate(*, start, end) -> dict
      A14 item 9's invoice-line read-model. A rate schedule is NOT a journal
      dimension, so the ledger structurally cannot answer this one and billing
      is the only module that can.

  apps.payments.reporting.ar_aging(*, as_of, account_class=None) -> dict
      Open bills aged on their OWN due dates. Payments is the only module that
      sees both halves — billing's due dates and its own allocations.

  apps.payments.reporting.payments_by_method(*, start, end, purpose=None) -> dict
      POSTING basis since 2026-10-21 (DEF-PAY-10321), purposes on their own
      lines (BR-REP-014).

  apps.ledger.reporting.revenue_and_ar(*, start, end) -> dict
      The AR control total the ageing FOOTS TO (BR-REP-008 / US-REP-005 TC-3).
      Read here so the tie-out is stated ON the report rather than left for a
      reader to perform against another screen.

  apps.ledger.reporting.ar_control(*, as_of) -> Decimal
      The same total as at a DATE — what the DSO numerator is (BR-REP-011).

  apps.ledger.reporting.account_ledger(account_id, *, start, end)      → S59
  apps.ledger.reporting.by_premises_summary(*, start, end)             → S60
  apps.ledger.wire.account_ledger_dict(result, *, currency)            → S59
  apps.ledger.wire.by_premises_dict(result, *, currency)               → S60
      `CR-142-BRC07` `P0.14`. The two ledger-OWNED report viewers. Added here
      on 2026-09-26; until then `api.py` imported both modules at its own top
      level, and a deployment without them lost the whole reports API rather
      than these two reports.

  apps.tenancy.exports.artifact_retention_days() -> int
  apps.tenancy.exports.ARTIFACT_RETENTION_DAYS   -> int        (a CONSTANT)
      `CR-142-BRC07` `P4.6`. How long a generated file is kept. The FUNCTION is
      this tenant's own setting (`BR-REP-018`'s tenant-configurable half, built
      2026-09-27); the CONSTANT is the platform default it falls back to, and
      both live in the export kernel because the kernel is what keeps the file.
      Reports reads and never writes either — the card that CHANGES it is
      served by tenancy's own `PUT /settings/reports`.

  apps.tenancy.exports.default_download_format() -> str
      `CR-142-BRC07` `P4.6`. What a download IS unless the clerk asks otherwise.
      Read where a SCHEDULE is created without naming a format, so the card is
      a setting that does something rather than a stored preference nobody
      consults. Reports reads and never writes it.

  apps.payments.models.PAYMENT_PURPOSES  -> tuple[str, ...]   (a CONSTANT)
  apps.billing.reporting.BILL_TYPES      -> tuple[str, ...]   (a CONSTANT)
      `CR-142-BRC07` `P0.13`. Read through `resolve_constant`, because
      `resolve` refuses anything that is not callable.

  apps.tenancy.selectors.enabled_service_codes() -> tuple[str, ...]
  apps.tenancy.selectors.current_period(reference_date=None) -> dict | None
  apps.tenancy.selectors.regional_settings() -> dict
      BR-REP-006's live vocabularies and BR-TEN-022's computed window — the SAME
      period S7, S36, S59 and S60 head their pages with, so no two screens in
      this product can disagree about which month a figure belongs to.

**THE ACCOUNT-CLASS VOCABULARY IS NOT A SEAM AND DELIBERATELY SO.** BR-REP-006
requires the class filter to enumerate the live four (Government included, never
the prototype's Residential/Commercial/Industrial trio), and this product already
serves that list at **`GET /lookups/account_types`** — a platform table with its
own registered handler (`apps/customers/lookups.AccountTypeLookupHandler`). The
viewer reads THAT, live, on the screen where the filter is drawn. Minting a
second read of the same rows here would be a second vocabulary free to drift
from the one S18's customer-type select already uses, which is the failure
BR-REP-006 exists to prevent rather than an implementation of it.

A class value the tenant does not have therefore reaches the read model, matches
no account, and renders IS-7's zero-results-after-filter state — never a silent
full-set render (US-REP-002 TC-6).
"""

from collections.abc import Callable
from typing import Any

#: Named as module-level constants rather than inlined, so G20 can substitute
#: them into the `resolve()` call sites statically — a module bound from a loop
#: variable is exactly the shape that hid DEF-075's missing leg from every
#: static reader.
BILLING_MODULE = "billing"
BILLING_KIND = "reporting"
PAYMENTS_MODULE = "payments"
PAYMENTS_KIND = "reporting"
LEDGER_MODULE = "ledger"
LEDGER_KIND = "reporting"
TENANCY_MODULE = "tenancy"
TENANCY_KIND = "selectors"


LEDGER_WIRE_KIND = "wire"

#: `DEF-REP-7052` — ledger's own dimension seam, where an id already stamped on
#: a journal line is turned into the WORD a person reads. Its own `kind` for
#: `DEF-035`'s reason and for `LEDGER_DATASET_KIND`'s: naming the file a
#: function actually lives in is what makes a broken seam a failure rather than
#: a permanent `None`.
LEDGER_DIMENSION_KIND = "dimension_seam"


def resolve_constant(module: str, name: str, kind: str = "models") -> Any | None:
    """A neighbour's published CONSTANT, read at call time. None ⇒ not published.

    ⚠ **`resolve()` ABOVE REFUSES A NON-CALLABLE, WHICH IS WHY THIS EXISTS**
    (`CR-142-BRC07` `P0.13`). Two vocabularies in this module — payments'
    `PAYMENT_PURPOSES` and billing's `BILL_TYPES` — are tuples rather than
    functions, so the only way to read them was
    `import_module("apps.payments.models")` **inside `queries.py`**, which is a
    cross-module boundary crossing OUTSIDE the seam file. It read a constant and
    touched no ORM, so nothing was wrong with the VALUE; what was wrong is that
    the one file whose job is to list what this module reads from its
    neighbours did not mention either of them, and `G20` reads that file.

    The module a constant is read from is NAMED by the caller and never built
    from a loop variable — the same reason `resolve()` takes its module as a
    literal (DEF-075).
    """
    from importlib import import_module

    try:
        published = import_module(f"apps.{module}.{kind}")
    except ImportError:
        return None
    return getattr(published, name, None)


def resolve(module: str, function: str, kind: str = "selectors") -> Callable[..., Any] | None:
    """The owning module's published callable, or None while it is not authored.

    getattr AT CALL TIME, never at import — `dashboard_seams.resolve`'s twin,
    and DEF-035 is why the `kind` is explicit: a seam pointing at the wrong FILE
    (`services` instead of `selectors`) returned None on every call for weeks
    and silently recorded a guard as "not checked" on every move-out.
    """
    from importlib import import_module

    try:
        published = import_module(f"apps.{module}.{kind}")
    except ImportError:
        return None
    found = getattr(published, function, None)
    return found if callable(found) else None


# ── CR-185-BRC10 D4 — the owner summary's two reads (WIRED) ─────────────────
CUSTOMERS_MODULE_FOR_OWNERS = "customers"
CUSTOMERS_OWNERS_KIND = "selectors"


def owner_properties(account_id: Any, **kwargs: Any) -> dict[str, Any] | None:
    """customers' answer to *whose master account is this, and which others
    do they hold*. `None` ⇒ no such account here, or customers publishes no
    such read — the viewer refuses by name either way."""
    found = resolve(CUSTOMERS_MODULE_FOR_OWNERS, "owner_properties", kind=CUSTOMERS_OWNERS_KIND)
    return found(account_id, **kwargs) if found is not None else None


def owner_bill_summary(**kwargs: Any) -> dict[str, Any] | None:
    """billing's owner bills, summed per owner account into the three sections.
    `None` ⇒ billing publishes no such read on this deployment."""
    found = resolve(BILLING_MODULE, "owner_bill_summary", kind=BILLING_KIND)
    return found(**kwargs) if found is not None else None


# ── billing — what was billed (WIRED) ───────────────────────────────────────
def billing_register(**kwargs: Any) -> dict[str, Any] | None:
    """A14's register. None ⇒ the card refuses and names billing as the owner."""
    found = resolve(BILLING_MODULE, "billing_register", kind=BILLING_KIND)
    return found(**kwargs) if found is not None else None


def revenue_by_service_and_rate(**kwargs: Any) -> dict[str, Any] | None:
    """A14 item 9's invoice-line read-model, with its drill-back ids."""
    found = resolve(BILLING_MODULE, "revenue_by_service_and_rate", kind=BILLING_KIND)
    return found(**kwargs) if found is not None else None


def invoices_dataset(**kwargs: Any) -> dict[str, Any] | None:
    """ONE PAGE of the `invoices` dataset — the brief's left read path.

    None ⇒ billing publishes no dataset query on this deployment, and the card
    refuses NAMING billing as the owner rather than rendering nothing. An empty
    result and an absent owner look identical on screen, which is why the
    refusal carries the module.
    """
    found = resolve(BILLING_MODULE, "invoices_dataset", kind=BILLING_KIND)
    return found(**kwargs) if found is not None else None


def invoices_dataset_stream(**kwargs: Any) -> Any | None:
    """EVERY ROW of the `invoices` dataset, from a generator — the right path.

    A SEPARATE seam from the one above, deliberately: §8.2 p91 says *"the left
    path never fetches more than a page; the right path never holds one"*, and
    one seam taking a `per` argument is precisely how the export inherited the
    screen's fifty rows on the register the day it started paging.
    """
    found = resolve(BILLING_MODULE, "invoices_dataset_stream", kind=BILLING_KIND)
    return found(**kwargs) if found is not None else None


def invoices_dataset_constant(name: str) -> Any | None:
    """A declared tuple from billing's dataset query — its sorts, its
    searchable columns, the filters it actually serves.

    Read at call time rather than copied here for `BR-REP-006`'s reason and for
    hard-won law 2's mirror: a sort this module offers and the read model
    declines would be a live caret over a dead control.
    """
    return resolve_constant(BILLING_MODULE, name, kind=BILLING_KIND)


# ── payments — what is owed and what came in (WIRED) ────────────────────────
def ar_aging(**kwargs: Any) -> dict[str, Any] | None:
    """Open bills aged on their own due dates, POSTING basis."""
    found = resolve(PAYMENTS_MODULE, "ar_aging", kind=PAYMENTS_KIND)
    return found(**kwargs) if found is not None else None


def payments_by_method(**kwargs: Any) -> dict[str, Any] | None:
    """Counted payments by the tenant's OWN methods, POSTING basis (PO 2026-10-21)."""
    found = resolve(PAYMENTS_MODULE, "payments_by_method", kind=PAYMENTS_KIND)
    return found(**kwargs) if found is not None else None


# ── payments — THE `payments` DATASET (WIRED 2026-09-27, lane REP-UNBLOCK) ──
#
# ⚠ **ITS OWN `kind`, FOR THE REASON `LEDGER_DATASET_KIND` ALREADY RECORDS.**
# `apps.payments.reporting` is the module's aggregate file; the dataset query
# lives in `apps/payments/payments_dataset.py` and naming that file is what makes
# a missing owner visible the first time somebody runs the report (DEF-035).
PAYMENTS_DATASET_KIND = "payments_dataset"


def payments_dataset(**kwargs: Any) -> dict[str, Any] | None:
    """THE `payments` dataset — one row per payment, paged and sorted in SQL.

    POSTING basis (BR-REP-001; PO 2026-10-21), `NFR-3`. `None` ⇒ payments does not publish it on
    this deployment, and the card refuses with payments NAMED as the owner rather
    than showing a zero (BR-REP-024).
    """
    found = resolve(PAYMENTS_MODULE, "payments_dataset", kind=PAYMENTS_DATASET_KIND)
    return found(**kwargs) if found is not None else None


def payments_dataset_stream(**kwargs: Any) -> Any | None:
    """EVERY ROW of the `payments` dataset, from a generator — the right path.

    A SEPARATE seam from the one above, for the reason the invoices pair is
    separate: §8.2 p91's *"the left path never fetches more than a page; the right
    path never holds one"*, and one seam taking a `per` is how the billing
    register's export inherited the screen's fifty rows.
    """
    found = resolve(
        PAYMENTS_MODULE, "payments_dataset_stream", kind=PAYMENTS_DATASET_KIND
    )
    return found(**kwargs) if found is not None else None


def payments_dataset_constant(name: str) -> Any | None:
    """A declared tuple from payments' dataset query — its sorts, its filters,
    its SQL group levels. Read at call time for hard-won law 2's mirror: a sort or
    a group level this module offered and the read model declined would be a live
    control over a dead one."""
    return resolve_constant(PAYMENTS_MODULE, name, kind=PAYMENTS_DATASET_KIND)


# ── payments — RECEIVABLES BY SERVICE (`CR-184-BRC10`, 2026-10-14) ──────────
#
# ⚠ **ITS OWN `kind`, FOR THE REASON `PAYMENTS_DATASET_KIND` RECORDS ABOVE.**
# The read model is `apps/payments/receivables_by_service.py`, and naming that
# file is what makes a missing owner visible the first time the report runs.
PAYMENTS_RECEIVABLES_KIND = "receivables_by_service"


def receivables_dataset(**kwargs: Any) -> dict[str, Any] | None:
    """THE `receivables` dataset — one row per account × service, POSTING basis,
    paged after the whole filtered set is totalled (`NFR-3`)."""
    found = resolve(PAYMENTS_MODULE, "receivables_dataset", kind=PAYMENTS_RECEIVABLES_KIND)
    return found(**kwargs) if found is not None else None


def receivables_dataset_stream(**kwargs: Any) -> Any | None:
    """EVERY ROW of the `receivables` dataset — the export's path, no `per`."""
    found = resolve(
        PAYMENTS_MODULE, "receivables_dataset_stream", kind=PAYMENTS_RECEIVABLES_KIND
    )
    return found(**kwargs) if found is not None else None


def receivables_over_90_by_service(**kwargs: Any) -> dict[str, Any] | None:
    """R3 — one row per service (and class row), over 90 days, POSTING basis."""
    found = resolve(PAYMENTS_MODULE, "over_90_by_service", kind=PAYMENTS_RECEIVABLES_KIND)
    return found(**kwargs) if found is not None else None


def receivables_constant(name: str) -> Any | None:
    """A declared tuple from the receivables read model — its sorts."""
    return resolve_constant(PAYMENTS_MODULE, name, kind=PAYMENTS_RECEIVABLES_KIND)


def journal_lines_constant(name: str) -> Any | None:
    """A declared tuple from ledger's dataset query — same reasoning."""
    return resolve_constant(LEDGER_MODULE, name, kind=LEDGER_DATASET_KIND)


# ── ledger — the tie-out the ageing must foot to (WIRED) ────────────────────
def revenue_and_ar(**kwargs: Any) -> dict[str, Any] | None:
    """S36's own read model. Read here ONLY for the AR control total and the
    period's billed figure — never re-derived, never adjusted."""
    found = resolve(LEDGER_MODULE, "revenue_and_ar", kind=LEDGER_KIND)
    return found(**kwargs) if found is not None else None


def ar_control(**kwargs: Any) -> Any | None:
    """The AR control balance as at a date — BR-REP-011's numerator."""
    found = resolve(LEDGER_MODULE, "ar_control", kind=LEDGER_KIND)
    return found(**kwargs) if found is not None else None


def balance_to_owner_moves(**kwargs: Any) -> Any | None:
    """`DEF-REP-10158` — every balance moved tenant → owner in a book-date
    window, from the journal entries themselves. None ⇒ not published."""
    found = resolve(LEDGER_MODULE, "balance_to_owner_moves", kind=LEDGER_KIND)
    return found(**kwargs) if found is not None else None


def ar_positions(**kwargs: Any) -> dict[str, Any] | None:
    """`DEF-REP-10158` — what each named account owes in the books at a date
    (the ledger's per-account Σ over AR). None ⇒ not published."""
    found = resolve(LEDGER_MODULE, "ar_positions", kind=LEDGER_KIND)
    return found(**kwargs) if found is not None else None


# ── tenancy — whose month, whose services, whose currency (WIRED) ───────────
def current_period(**kwargs: Any) -> dict[str, Any] | None:
    """BR-TEN-022's COMPUTED accounting window. None ⇒ no fiscal calendar, and
    then no money figure is computed over a substituted calendar month."""
    found = resolve(TENANCY_MODULE, "current_period", kind=TENANCY_KIND)
    return found(**kwargs) if found is not None else None


#: identity's published reads. ⚠ **`kind="selectors"` AND NOT `"services"` —
#: `run_history.actor_names` records at length what the wrong `kind` costs: a
#: seam pointing at the wrong FILE returns `None` on every call, silently, and
#: the screen says the wrong thing for weeks (DEF-035).
IDENTITY_MODULE = "identity"
IDENTITY_KIND = "selectors"


def user_list(tenant_id: Any) -> Any | None:
    """Every staff MEMBERSHIP of ONE tenant — the recipients picker's options.

    ⚠ **THIS IS THE READ THAT MAKES `BR-REP-020` ENFORCEABLE RATHER THAN
    DOCUMENTED.** *"Internal staff only"* is only a rule if something can say
    who the internal staff ARE; without it the API would have to take the
    caller's word for a list of ids, which is the free-text email box the
    ruling forbids wearing a uuid costume.

    ⚠ **IT RETURNS `TenantMembership` ROWS AND NOT `User` ROWS, AND THE FIRST
    DRAFT OF THE CALLER ASSUMED OTHERWISE.** The function is NAMED `user_list`
    and `identity.selectors.user_list` returns
    `TenantMembership.objects.filter(...).select_related("user", "role")` — so
    `row.pk` is the MEMBERSHIP's id, not the person's, and
    `row.full_name` does not exist at all. A recipients list built from
    membership ids would have been refused against every real user id a screen
    sent back, on a rule whose whole point is that the refusal is correct.
    **Caught by reading the selector rather than its name** — the brief's own
    standing instruction, and the measured failure is in
    `tests/test_cr142_p4_schedules.py`'s first run of the recipients cases.
    `schedules.tenant_staff` walks `membership.user`, and this docstring says
    so here so the next caller does not re-derive it.

    ⚠ **`sort="name"` AND NOT `"full_name"`** — `USER_LIST_SORTS` is a five-key
    ALLOW LIST (`name` · `email` · `role` · `last_active` · `status`) and an
    unknown key falls back to *last active*, silently. So the picker would have
    been ordered by who logged in most recently, which re-shuffles under a
    clerk between two openings and reads as the product being broken. A
    `.get(..., default)` that answers for a typo is law 7's *passes wrongly*
    one layer down.
    """
    found = resolve(IDENTITY_MODULE, "user_list", kind=IDENTITY_KIND)
    if found is None:
        return None
    return found(tenant_id, sort="name", direction="asc")


def live_tenants() -> tuple[str, ...]:
    """Every utility that finished provisioning — the sweep's outer loop.

    ⚠ **THIS IS THE ONE READ IN THIS MODULE MADE WITH NO TENANT CONTEXT SET,
    AND IT IS LAWFUL.** `tenants` is the RLS-EXEMPT REGISTRY (`BR-TEN-003`),
    not a tenant-hosted table, so resolving *who are the utilities* reaches no
    utility's data. `apps/reports/schedules.sweep_all_tenants` then enters each
    tenant's context before it touches a single `report_schedules` row (hard
    rule 1).

    ⚠ **AN ENVIRONMENT VARIABLE WOULD HAVE BEEN THE OBVIOUS SHORTCUT AND IT IS
    A DEFECT WITH A NUMBER** (`DEF-3422`). The notification dispatcher paced its
    cycle from `NOTIFICATIONS_DISPATCH_TENANTS`; unset — which is every
    deployment — **every firing dispatched to nobody**, silently. A report
    scheduler with the same hole would fire for no utility at all while every
    screen went on saying *Next 1 Oct*.
    """
    found = resolve(TENANCY_MODULE, "live_tenant_subdomains", kind=TENANCY_KIND)
    return tuple(found()) if found is not None else ()


def tenant_timezone() -> Any | None:
    """`BR-TEN-081`'s clock — whose morning 06:00 is. `None` ⇒ not published.

    ⚠ **THE FALLBACK IS THE OWNER'S AND NOT OURS.**
    `apps.tenancy.selectors.tenant_timezone` already answers UTC for a tenant
    with nothing configured; `schedules.tenant_zone` inherits that rather than
    choosing a second one, because two fallbacks for one fact is how two
    surfaces come to disagree about what day it is.
    """
    found = resolve(TENANCY_MODULE, "tenant_timezone", kind=TENANCY_KIND)
    return found() if found is not None else None


def regional_settings() -> dict[str, Any] | None:
    """The tenant's declared CHAR(3) and its formats."""
    found = resolve(TENANCY_MODULE, "regional_settings", kind=TENANCY_KIND)
    return found() if found is not None else None


def enabled_service_codes() -> tuple[str, ...] | None:
    """BR-REP-006's service filter: the tenant's ENABLED set, never a trio."""
    found = resolve(TENANCY_MODULE, "enabled_service_codes", kind=TENANCY_KIND)
    return tuple(found()) if found is not None else None


def services_overview() -> list[dict[str, Any]] | None:
    """The enabled services with their names, for the filter's labels."""
    found = resolve(TENANCY_MODULE, "services_overview", kind=TENANCY_KIND)
    return found() if found is not None else None


# ── payments · billing — the two filter VOCABULARIES (WIRED, CR-142 P0.13) ──
#
# Both are tuples and neither is a function, so they come through
# `resolve_constant` rather than `resolve`. `()` means *the owner does not
# publish this vocabulary* — the filter then offers nothing rather than a
# hardcoded trio, which is BR-REP-006 stated as an absence.
def payment_purposes() -> tuple[str, ...]:
    """BR-PAY-012's purposes, read from payments' own module at call time."""
    found = resolve_constant(PAYMENTS_MODULE, "PAYMENT_PURPOSES", kind="models")
    return tuple(found) if found is not None else ()


def bill_types() -> tuple[str, ...]:
    """A14 item 6's vocabulary, read from billing's own tuple at call time."""
    found = resolve_constant(BILLING_MODULE, "BILL_TYPES", kind=BILLING_KIND)
    return tuple(found) if found is not None else ()


# ── ledger — S59 and S60, the module's two most important reports ───────────
#
# ⚠ **THESE TWO WERE THE ONLY READS IN THIS MODULE THAT BYPASSED THIS FILE**
# (`CR-142-BRC07` `P0.14`). `apps/reports/api.py` carried
# `from apps.ledger import reporting, wire` at module scope, so a deployment
# without `apps.ledger.reporting` did not refuse the two reports — it failed to
# IMPORT THE REPORTS API AT ALL, taking every other route in this module with
# it. An `ImportError` at module load is not a refusal a user can read, and it
# is the one failure BR-REP-024 exists to convert into a sentence.
#
# Resolved BY NAME AT CALL TIME like every other seam here, so a missing owner
# is a NAMED GAP on one report rather than a dead module.
def account_ledger(*args: Any, **kwargs: Any) -> Any | None:
    """S59's read model. None ⇒ ledger does not publish it on this deployment."""
    found = resolve(LEDGER_MODULE, "account_ledger", kind=LEDGER_KIND)
    return found(*args, **kwargs) if found is not None else None


def unit_ledger(*args: Any, **kwargs: Any) -> Any | None:
    """`P2.15`'s read model — ONE UNIT's running record, across its tenancies.

    `BR-REP-043`. None ⇒ ledger does not publish it on this deployment, and the
    `unit` subject then refuses BY NAME rather than answering with an account's
    statement under a unit's heading (hard-won law 2's mirror).
    """
    found = resolve(LEDGER_MODULE, "unit_ledger", kind=LEDGER_KIND)
    return found(*args, **kwargs) if found is not None else None


# ── ledger — THE NAMES BEHIND THE IDS (`DEF-REP-7052`) ──────────────────────
#
# ⚠ **THE STATEMENT HAD NEVER NAMED THE RECORD IT WAS ABOUT.** `subject.py` has
# published `head_from` since `P2.14` — `("account_no", "customer_name")` for an
# account, `("premises_address", "unit_label")` for a unit — and NOTHING read
# it, on the server or on the screen. So a clerk printed a page of somebody's
# money with the report's name above it and no indication whose money it was,
# and the shipped account statement had never done it either.
#
# These three are `apps.ledger.dimension_seam`'s, resolved BY NAME AT CALL TIME
# like every other seam here. The ids they turn into words are ids this report
# already holds; none of them is a lookup that could widen what is read.
def account_labels(ids: Any) -> dict[str, str]:
    """`{account_id: "AC-2026-00032"}`. `{}` ⇒ ledger publishes no such read."""
    found = resolve(LEDGER_MODULE, "account_labels", kind=LEDGER_DIMENSION_KIND)
    return dict(found(ids)) if found is not None else {}


def customer_labels(ids: Any) -> dict[str, str]:
    """`{customer_id: "Marisol Vega"}`. `{}` ⇒ ledger publishes no such read."""
    found = resolve(LEDGER_MODULE, "customer_labels", kind=LEDGER_DIMENSION_KIND)
    return dict(found(ids)) if found is not None else {}


def customer_id_for_account(account_id: Any) -> str | None:
    """WHO HOLDS this account, or None. Never guessed, never refused."""
    found = resolve(
        LEDGER_MODULE, "customer_id_for_account", kind=LEDGER_DIMENSION_KIND
    )
    return found(account_id) if found is not None else None


def by_premises_summary(**kwargs: Any) -> Any | None:
    """S60's read model. None ⇒ ledger does not publish it on this deployment."""
    found = resolve(LEDGER_MODULE, "by_premises_summary", kind=LEDGER_KIND)
    return found(**kwargs) if found is not None else None


def account_ledger_dict(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
    """Ledger's OWN wire shape for S59 — never re-derived here."""
    found = resolve(LEDGER_MODULE, "account_ledger_dict", kind=LEDGER_WIRE_KIND)
    return found(*args, **kwargs) if found is not None else None


def by_premises_dict(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
    """Ledger's OWN wire shape for S60 — never re-derived here."""
    found = resolve(LEDGER_MODULE, "by_premises_dict", kind=LEDGER_WIRE_KIND)
    return found(*args, **kwargs) if found is not None else None


# ── ledger — THE `journal_lines` DATASET (WIRED 2026-09-26, lane DS-LEDGER) ──
#
# ⚠ **ITS OWN `kind`, AND THAT IS NOT TIDINESS.** `apps.ledger.reporting` is
# 3,663 lines and importing it to read one line-level query drags nine
# aggregates and their own cross-module seams in with it. More to the point,
# DEF-035 is about a seam pointing at the wrong FILE and returning None on every
# call for weeks: naming the file the query actually lives in is what makes a
# missing owner visible the first time somebody runs the report.
LEDGER_DATASET_KIND = "journal_lines_dataset"


def journal_lines(**kwargs: Any) -> dict[str, Any] | None:
    """THE `journal_lines` dataset — one row per posted journal line.

    Paged, sorted and filtered IN SQL (`NFR-3`, brief §7.5), POSTING basis
    (BR-REP-001). `None` ⇒ ledger does not publish it on this deployment, and
    the card then refuses with ledger NAMED as the owner rather than showing a
    zero (BR-REP-024).
    """
    found = resolve(LEDGER_MODULE, "journal_lines", kind=LEDGER_DATASET_KIND)
    return found(**kwargs) if found is not None else None


def trial_balance(**kwargs: Any) -> dict[str, Any] | None:
    """R15's aggregate over the same lines — ledger's own, never re-derived.

    A SEPARATE seam from `journal_lines` on purpose: a trial balance is Σ per GL
    account and an aggregate cannot be un-aggregated, so the two are two reads
    of one dataset rather than one read somebody post-processes. There is
    exactly one derivation of a period's debits and credits in this product and
    it is `apps.ledger.reporting`'s.
    """
    found = resolve(LEDGER_MODULE, "trial_balance", kind=LEDGER_KIND)
    return found(**kwargs) if found is not None else None


def remittance_by_authority(**kwargs: Any) -> dict[str, Any] | None:
    """R18's dual-basis table (US-LED-014 · BR-LED-002). Ledger owns it."""
    found = resolve(LEDGER_MODULE, "remittance_by_authority", kind=LEDGER_KIND)
    return found(**kwargs) if found is not None else None


LEDGER_TIEOUT_KIND = "tie_out"
LEDGER_EXPORTS_KIND = "exports"


def tie_outs(**kwargs: Any) -> dict[str, Any] | None:
    """R21's control-vs-register checks, and `release_blocked` (BR-LED-007).

    Read rather than recomputed, and the verdict is READ TOO. A screen that
    worked out its own blocker could render three red rows and no blocker,
    which is this check developing the fault it exists to detect — so
    `release_blocked` and `dismissible` come off the wire exactly as ledger
    published them.
    """
    found = resolve(LEDGER_MODULE, "tie_outs", kind=LEDGER_TIEOUT_KIND)
    return found(**kwargs) if found is not None else None


def export_history(**kwargs: Any) -> tuple[dict[str, Any], ...] | None:
    """R16's batch table — what has been sent to the ERP, newest first.

    ⚠ `None` ⇒ not published; an EMPTY TUPLE ⇒ nothing has been exported yet.
    They are different facts and the viewer renders them differently: the first
    is a named refusal, the second is a `last_export` tile carrying
    `nothing_has_been_exported_yet`. Collapsing them is DEF-075's shape, where a
    seam that could not answer returned a falsy value.
    """
    found = resolve(LEDGER_MODULE, "export_history", kind=LEDGER_EXPORTS_KIND)
    return found(**kwargs) if found is not None else None


# ════════════════════════════════════════════════════════════════════════════
# THE SIX REMAINING DATASET QUERIES (WIRED 2026-09-27, lane REP-WIRE)
# ════════════════════════════════════════════════════════════════════════════
#
# ⚠ **EVERY ONE OF THESE QUERIES EXISTED, WAS MEASURED AND WAS TESTED BEFORE
# THIS FILE MENTIONED ANY OF THEM (`DEF-REP-6894`).** Four sibling lanes pushed
# `meter_reads`, `work_orders`, `assets`, `rate_schedules`, `accounts` and
# `audit_log` between 2026-09-26 and 2026-09-27; `apps/reports` had no seam to
# any of them, so `queries_for` found no dataset fallback and **eighteen** of
# the forty-six seeded definitions raised `DatasetNotExecutable` over datasets
# that were, in fact, executable. That is hard-won law 2 — built is not wired —
# and the refusal was true of the registry and false of the product.
#
# ⚠ **EACH GETS ITS OWN `kind`, FOR THE REASON `LEDGER_DATASET_KIND` RECORDS.**
# The module's aggregate file is not where the dataset query lives, and naming
# the FILE is what makes a missing owner visible the first time somebody runs
# the report rather than silently returning None for weeks (DEF-035).
#
# ⚠ **THREE FUNCTIONS PER DATASET AND NEVER TWO.** A page, a generator and a
# constant reader. §8.2 (p91): *"the left path never fetches more than a page;
# the right path never holds one"* — one seam taking a `per` is how the billing
# register's export inherited the screen's fifty rows.
METERING_MODULE = "metering"
METER_READS_DATASET_KIND = "meter_reads_dataset"
ASSETS_MODULE = "assets"
ASSETS_DATASET_KIND = "assets_dataset"
CUSTOMERS_MODULE = "customers"
ACCOUNTS_DATASET_KIND = "accounts_dataset"
RATING_MODULE = "rating"
RATE_SCHEDULES_DATASET_KIND = "rate_schedules_dataset"
AUDIT_MODULE = "audit"
AUDIT_LOG_DATASET_KIND = "audit_log_dataset"
WORK_MODULE = "work"
WORK_ORDERS_DATASET_KIND = "work_orders_dataset"


def meter_reads_dataset(**kwargs: Any) -> dict[str, Any] | None:
    """THE `meter_reads` dataset — one row per committed lineage head.

    EVENT basis (the read date). `None` ⇒ metering does not publish it on this
    deployment and the card refuses with metering NAMED as the owner.
    """
    found = resolve(METERING_MODULE, "meter_reads_dataset", kind=METER_READS_DATASET_KIND)
    return found(**kwargs) if found is not None else None


def meter_reads_dataset_stream(**kwargs: Any) -> Any | None:
    """EVERY ROW of the `meter_reads` dataset, from a generator.

    ⚠ The dataset where the separation costs most: §7.6 (p087) puts a year of
    read history at T5 at ~480,000 rows, so an export that inherited a screen's
    fifty would be short by four hundred and seventy-nine thousand and would
    still open cleanly in a spreadsheet.
    """
    found = resolve(METERING_MODULE, "meter_reads_dataset_stream", kind=METER_READS_DATASET_KIND)
    return found(**kwargs) if found is not None else None


def meter_reads_dataset_constant(name: str) -> Any | None:
    """A declared tuple or map from metering's dataset query — its sorts, its
    filters, the per-definition refusals it publishes. Read at call time so a
    control this module offers and the read model declines cannot exist."""
    return resolve_constant(METERING_MODULE, name, kind=METER_READS_DATASET_KIND)


def assets_dataset(**kwargs: Any) -> dict[str, Any] | None:
    """THE `assets` dataset — one row per asset, as at a date."""
    found = resolve(ASSETS_MODULE, "assets_dataset", kind=ASSETS_DATASET_KIND)
    return found(**kwargs) if found is not None else None


def assets_dataset_stream(**kwargs: Any) -> Any | None:
    """EVERY ROW of the `assets` dataset, from a generator."""
    found = resolve(ASSETS_MODULE, "assets_dataset_stream", kind=ASSETS_DATASET_KIND)
    return found(**kwargs) if found is not None else None


def assets_dataset_constant(name: str) -> Any | None:
    """A declared tuple or map from the assets dataset query."""
    return resolve_constant(ASSETS_MODULE, name, kind=ASSETS_DATASET_KIND)


def accounts_dataset(**kwargs: Any) -> dict[str, Any] | None:
    """THE `accounts` dataset — one row per account, as at a date."""
    found = resolve(CUSTOMERS_MODULE, "accounts_dataset", kind=ACCOUNTS_DATASET_KIND)
    return found(**kwargs) if found is not None else None


def accounts_dataset_stream(**kwargs: Any) -> Any | None:
    """EVERY ROW of the `accounts` dataset, from a generator."""
    found = resolve(CUSTOMERS_MODULE, "accounts_dataset_stream", kind=ACCOUNTS_DATASET_KIND)
    return found(**kwargs) if found is not None else None


def accounts_dataset_constant(name: str) -> Any | None:
    """A declared tuple or map from the accounts dataset query — including its
    `UNSERVABLE_HERE` refusals, which are read rather than retyped here."""
    return resolve_constant(CUSTOMERS_MODULE, name, kind=ACCOUNTS_DATASET_KIND)


def rate_schedules_dataset(**kwargs: Any) -> dict[str, Any] | None:
    """THE `rate_schedules` dataset — one row per rate-schedule VERSION."""
    found = resolve(RATING_MODULE, "rate_schedules_dataset", kind=RATE_SCHEDULES_DATASET_KIND)
    return found(**kwargs) if found is not None else None


def rate_schedules_dataset_stream(**kwargs: Any) -> Any | None:
    """EVERY ROW of the `rate_schedules` dataset, from a generator."""
    found = resolve(
        RATING_MODULE, "rate_schedules_dataset_stream", kind=RATE_SCHEDULES_DATASET_KIND
    )
    return found(**kwargs) if found is not None else None


def rate_schedules_dataset_constant(name: str) -> Any | None:
    """A declared tuple or map from rating's dataset query — its two scales
    among them, which is why this is read and never assumed: hard rule 2 stores
    money to 4 and percentages to 6 and R37 displays what the rule stores."""
    return resolve_constant(RATING_MODULE, name, kind=RATE_SCHEDULES_DATASET_KIND)


def audit_log_dataset(**kwargs: Any) -> dict[str, Any] | None:
    """THE `audit_log` dataset — one row per audit EVENT."""
    found = resolve(AUDIT_MODULE, "audit_log_dataset", kind=AUDIT_LOG_DATASET_KIND)
    return found(**kwargs) if found is not None else None


def audit_log_dataset_stream(**kwargs: Any) -> Any | None:
    """EVERY ROW of the `audit_log` dataset, from a generator."""
    found = resolve(AUDIT_MODULE, "audit_log_dataset_stream", kind=AUDIT_LOG_DATASET_KIND)
    return found(**kwargs) if found is not None else None


def audit_log_dataset_constant(name: str) -> Any | None:
    """A declared tuple or map from the audit dataset query."""
    return resolve_constant(AUDIT_MODULE, name, kind=AUDIT_LOG_DATASET_KIND)


def work_orders_dataset(**kwargs: Any) -> dict[str, Any] | None:
    """THE `work_orders` dataset — one row per work order."""
    found = resolve(WORK_MODULE, "work_orders_dataset", kind=WORK_ORDERS_DATASET_KIND)
    return found(**kwargs) if found is not None else None


def work_orders_dataset_stream(**kwargs: Any) -> Any | None:
    """EVERY ROW of the `work_orders` dataset, from a generator."""
    found = resolve(WORK_MODULE, "work_orders_dataset_stream", kind=WORK_ORDERS_DATASET_KIND)
    return found(**kwargs) if found is not None else None


def work_orders_dataset_constant(name: str) -> Any | None:
    """A declared tuple or map from work's dataset query."""
    return resolve_constant(WORK_MODULE, name, kind=WORK_ORDERS_DATASET_KIND)



# ── THE JOINING READS (`P6.11`) — a report that needs MORE THAN ONE SOURCE ───
#
# ⚠ **THESE ARE NOT DATASET QUERIES AND THE DIFFERENCE IS THE WHOLE POINT.** A
# dataset query serves every definition seeded onto ONE dataset, at that
# dataset's ONE declared grain. Each read below serves ONE report whose drawing
# states a grain no dataset holds — a lifecycle EVENT, an import BATCH, a USER —
# and each is registered as a per-KEY viewer, which `runner.queries_for` checks
# FIRST so the dataset it is seeded on never sees the call.
#
# ⚠ **THE JOIN LIVES IN THE MODULE THAT OWNS THE SPINE, NEVER HERE.** Reports
# imports no other module's models (`CR-142-BRC07` §3), so a read that joins
# `move_records` to `transfers` is customers' own file and this seam resolves it
# by name at call time. A join composed in `apps/reports/` would be a
# cross-module query with a boundary file's name on it.
IDENTITY_ACCESS_KIND = "access_review"
METERING_IMPORT_LOG_KIND = "read_import_log"
CUSTOMERS_ACTIVITY_KIND = "account_activity"


def access_review(**kwargs: Any) -> dict[str, Any] | None:
    """R36 — one row per USER OF THIS TENANT. None ⇒ identity has not authored it.

    ⚠ **IDENTITY, NOT AUDIT.** R36 is seeded on `audit_log` and its drawing's
    eyebrow reads *identity + audit*; measured against the drawing, seven of
    seven columns and four of four tiles are identity's and audit contributes
    nothing (`DEF-REP-6921`). The audit dataset refuses it correctly, because a
    user who has never signed in has written no audit event and is exactly the
    row this report exists to find.
    """
    found = resolve(IDENTITY_MODULE, "access_review", kind=IDENTITY_ACCESS_KIND)
    return None if found is None else found(**kwargs)


def access_review_stream(**kwargs: Any) -> Any | None:
    """EVERY row of R36 — a generator, with no `page` and no `per`."""
    found = resolve(IDENTITY_MODULE, "access_review_stream", kind=IDENTITY_ACCESS_KIND)
    return None if found is None else found(**kwargs)


def access_review_constant(name: str) -> Any | None:
    """One published constant of identity's access review — its sort vocabulary."""
    return resolve_constant(IDENTITY_MODULE, name, kind=IDENTITY_ACCESS_KIND)


def read_import_log(**kwargs: Any) -> dict[str, Any] | None:
    """R32 — one row per READ-IMPORT BATCH. None ⇒ metering has not authored it.

    ⚠ **NOT `jobs` AND NOT `meter_reads`**, which is what the drawing's eyebrow
    names. `jobs` is tenancy's export-job table and a rejected row never reaches
    `meter_reads` at all, so the REJECTED tile could not be computed from either
    (`DEF-REP-6921`). The sources are `read_import_batches` and its own
    `read_import_rows`.
    """
    found = resolve(METERING_MODULE, "read_import_log", kind=METERING_IMPORT_LOG_KIND)
    return None if found is None else found(**kwargs)


def read_import_log_stream(**kwargs: Any) -> Any | None:
    """EVERY row of R32 — a generator, with no `page` and no `per`."""
    found = resolve(METERING_MODULE, "read_import_log_stream", kind=METERING_IMPORT_LOG_KIND)
    return None if found is None else found(**kwargs)


def read_import_log_constant(name: str) -> Any | None:
    """One published constant of metering's import log — its sort vocabulary."""
    return resolve_constant(METERING_MODULE, name, kind=METERING_IMPORT_LOG_KIND)


def account_activity(**kwargs: Any) -> dict[str, Any] | None:
    """R23 — one row per ACCOUNT-LIFECYCLE EVENT. None ⇒ customers has not authored it.

    ⚠ **TWO TABLES, ONE GRAIN.** `move_records` holds the move-in and the
    move-out; `transfers` holds the third drawn word, because `moves.KINDS` is a
    two-tuple and a transfer is *"one job, not a move-out followed by a
    move-in"*. The UNION is cut, ordered and sliced in SQL inside customers.
    """
    found = resolve(CUSTOMERS_MODULE, "account_activity", kind=CUSTOMERS_ACTIVITY_KIND)
    return None if found is None else found(**kwargs)


def account_activity_stream(**kwargs: Any) -> Any | None:
    """EVERY row of R23 — a generator, with no `page` and no `per`."""
    found = resolve(CUSTOMERS_MODULE, "account_activity_stream", kind=CUSTOMERS_ACTIVITY_KIND)
    return None if found is None else found(**kwargs)


def account_activity_constant(name: str) -> Any | None:
    """One published constant of customers' activity read — its sort vocabulary."""
    return resolve_constant(CUSTOMERS_MODULE, name, kind=CUSTOMERS_ACTIVITY_KIND)


# ── THE JOINING READS, WAVE 2 (`P6.11`, lane REP-P6-W2, 2026-09-27) ──────────
CUSTOMERS_DISCONNECT_KIND = "disconnect_reconnect"


def disconnect_reconnect(**kwargs: Any) -> dict[str, Any] | None:
    """R34 — one row per ACCOUNT, latest case. None ⇒ customers has not authored it.

    ⚠ **CUSTOMERS, NOT WORK.** R34 is seeded on `work_orders` and its drawing's
    eyebrow reads *work orders + accounts*. `BR-REP-039` (PO ruling 2026-09-27)
    puts the spine on `customers.disconnect_cases`, where one row is one whole
    cut-and-restore SEQUENCE — so an account cut and restored twice contributes
    once and the BALANCE column cannot read `$395` for money nobody owed at
    once. **`work`'s refusal stays where it is** and is true of that dataset.
    """
    found = resolve(CUSTOMERS_MODULE, "disconnect_reconnect", kind=CUSTOMERS_DISCONNECT_KIND)
    return None if found is None else found(**kwargs)


def disconnect_reconnect_stream(**kwargs: Any) -> Any | None:
    """EVERY row of R34 — a generator, with no `page` and no `per`."""
    found = resolve(
        CUSTOMERS_MODULE, "disconnect_reconnect_stream", kind=CUSTOMERS_DISCONNECT_KIND
    )
    return None if found is None else found(**kwargs)


def disconnect_reconnect_constant(name: str) -> Any | None:
    """One published constant of customers' disconnect read — its sort vocabulary."""
    return resolve_constant(CUSTOMERS_MODULE, name, kind=CUSTOMERS_DISCONNECT_KIND)


# ── THE JOINING READS, WAVE 3 (`P6.11`, lane REP-P6-W3, 2026-09-27) ──────────
LEDGER_TREND_KIND = "trend_pack"


def trend_pack(**kwargs: Any) -> dict[str, Any] | None:
    """R43 — one row per FISCAL PERIOD. None ⇒ the ledger has not authored it.

    ⚠ **THE LEDGER, AND IT IS ALSO WHERE THE SEEDED DATASET POINTS.** R43 is
    seeded on `journal_lines` and its money IS the ledger's — what changes is
    the GRAIN: one accounting period rather than one posted line. That is why
    `queries.JOURNAL_LINES_DEFINITIONS_NOT_SERVED` names `trend_pack` and goes
    on naming it — `runner.queries_for` checks `VIEWERS` first, so this read
    bypasses the refusal without deleting a sentence that stays true of the
    dataset (`DEF-REP-6937`).
    """
    found = resolve(LEDGER_MODULE, "trend_pack", kind=LEDGER_TREND_KIND)
    return None if found is None else found(**kwargs)


def trend_pack_stream(**kwargs: Any) -> Any | None:
    """EVERY row of R43 — a generator, with no `page` and no `per`.

    ⚠ **BOUNDED AND STILL A GENERATOR, ON PURPOSE.** Without it `stream_for`
    falls through to the `journal_lines` DATASET stream and writes the ledger's
    own lines into a file headed *Trend Pack* — `DEF-REP-6937` again, on the
    path nobody looks at.
    """
    found = resolve(LEDGER_MODULE, "trend_pack_stream", kind=LEDGER_TREND_KIND)
    return None if found is None else found(**kwargs)


def trend_pack_constant(name: str) -> Any | None:
    """One published constant of the ledger's trend read — its default periods."""
    return resolve_constant(LEDGER_MODULE, name, kind=LEDGER_TREND_KIND)


# ⚠ **THERE IS NO `notifications` SEAM HERE AND THE ABSENCE IS THE FACT.**
# `apps/notifications/notifications_dataset.py` is built, measured and tested —
# lane DS-ACCOUNTS wrote it for **R8 Bill Delivery** rather than bending R8 onto
# the audit trail — but `apps/reports/datasets.py` declares NINE datasets and
# `notifications` is not one of them, and `reports/0003_seed_catalogue.py` seeds
# R8's `dataset` column as `audit_log`. `runner.bind` looks the definition's
# dataset up in `datasets.BY_CODE` and raises `DatasetNotExecutable` BEFORE
# `queries_for` is consulted, so a seam here would answer no call that can
# happen. A seam nothing can reach is the dead UI of hard-won law 2 wearing a
# boundary file's clothes, and `G20` reads this file as the list of what reports
# genuinely reads from its neighbours.
# What that dataset needs before it can be wired is a `NOTIFICATIONS` entry in
# `datasets.py` (with its slicer, drill-through, calendar and additivity rows)
# and a MIGRATION moving R8's seeded `dataset` from `audit_log` — a re-seed and
# not an edit of `0003`, because law 4's shape applies to a seed too: amending a
# migration that has already run reaches no deployment that has run it. It is
# reported, not done here: see `DEF-REP-6895`.


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-REP-001@c6c35b2 (co-packets US-REP-002/005/006/007; 04-docs/05-modules/12-reports/06-epics/EP-REP-01-report-center.md + EP-REP-02-canned-reports.md · 12-reports/02-business-rules.md BR-REP-001..024 · 04-docs/01-spec/14-reports-and-exports.md)
# screens: S44 · S46
# generated: 2026-08-16 by story-coder (reports lane); amended 2026-09-27 by lane REP-WIRE (DEF-REP-6894 — six dataset seams added, one per owning module, each a page + a stream + a constant reader)
# checklist: A✔ B✔ C=deferred(a seam — it serves no route of its own; queries.py does) D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_us_rep_canned_reports.py could not import this module before it existed. ruff✔ black✔ pytest✔ run_gates✔
# exceptions: (1) every documented seam here is WIRED — nothing in this file is dark, so nothing is parked in seam_known_gaps.txt; `notifications` is deliberately ABSENT rather than dark, because `datasets.py` declares no such dataset and a seam nothing can reach is dead code (DEF-REP-6895) · (2) no ORM, no arithmetic on money and no clock appears in this module at all
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ── THE JOINING READS, WAVE 4 (`P6.11`, lane REP-P6-W4, 2026-09-27) ──────────
BILLING_READINESS_KIND = "bill_run_readiness"


def bill_run_readiness(**kwargs: Any) -> dict[str, Any] | None:
    """R4 — one row per HELD ACCOUNT. None ⇒ billing has not authored it.

    ⚠ **BILLING, AND THE SEEDED DATASET AGREES WITHOUT BEING ABLE TO SERVE IT.**
    R4 is seeded on `invoices` and `queries.INVOICES_DEFINITIONS_NOT_SERVED`
    refuses it BY NAME, correctly and permanently: *"a bill does not exist yet
    for a held account"*. That sentence stays true of the dataset.
    `runner.queries_for` checks `VIEWERS` first, so this read bypasses the
    refusal without deleting a sentence that is right — the arrangement
    `trend_pack` and `disconnect_reconnect` already have, and for the same
    reason (`DEF-REP-6937`).
    """
    found = resolve(BILLING_MODULE, "bill_run_readiness", kind=BILLING_READINESS_KIND)
    return None if found is None else found(**kwargs)


def bill_run_readiness_stream(**kwargs: Any) -> Any | None:
    """EVERY row of R4 — a generator, with no `page` and no `per`.

    ⚠ **WITHOUT THIS REGISTRATION `stream_for` FALLS THROUGH TO THE `invoices`
    DATASET STREAM** and the download button writes a BILL REGISTER into a file
    headed *Bill Run Readiness* — a file of the accounts that DID bill, under the
    title of the ones that did not. That is `DEF-REP-6937` surviving on the path
    nobody looks at.
    """
    found = resolve(BILLING_MODULE, "bill_run_readiness_stream", kind=BILLING_READINESS_KIND)
    return None if found is None else found(**kwargs)


def bill_run_readiness_constant(name: str) -> Any | None:
    """One published constant of billing's readiness read — its sort vocabulary."""
    return resolve_constant(BILLING_MODULE, name, kind=BILLING_READINESS_KIND)


# ── R27 PLANS & DISCOUNTS — THREE PROGRAMMES, THREE MODULES (`P6.11` wave 4) ──
# ⚠ **THREE SEAMS FOR ONE REPORT, AND THE COUNT IS THE POINT.** `BR-REP-040`
# makes R27 a k-way merge of `billing.account_budget_status`,
# `payments.payment_plans` and `rating.discount_enrolments`. B1 forbids the
# cross-module query, so each module publishes its own slice — already sorted,
# already limited — and `apps/reports/plans_and_discounts.py` merges them. The
# merge lives in `reports` because it is the only place allowed to see all
# three; putting it in any one of them would be that module reading the other
# two's tables.
BILLING_LEVEL_PAY_KIND = "level_pay_enrolments"
PAYMENTS_PLAN_KIND = "plan_enrolments"
RATING_DISCOUNT_KIND = "discount_enrolments_read"
CUSTOMERS_ACCOUNTS_DATASET_KIND = "accounts_dataset"


def level_pay_enrolments(**kwargs: Any) -> Any | None:
    """R27's LEVEL PAY stream. None ⇒ billing has not authored it."""
    found = resolve(BILLING_MODULE, "level_pay_enrolments", kind=BILLING_LEVEL_PAY_KIND)
    return None if found is None else found(**kwargs)


def plan_enrolments(**kwargs: Any) -> Any | None:
    """R27's PAYMENT PLAN stream. None ⇒ payments has not authored it."""
    found = resolve(PAYMENTS_MODULE, "plan_enrolments", kind=PAYMENTS_PLAN_KIND)
    return None if found is None else found(**kwargs)


def discount_enrolments(**kwargs: Any) -> Any | None:
    """R27's ASSISTANCE stream. None ⇒ rating has not authored it."""
    found = resolve(RATING_MODULE, "discount_enrolments", kind=RATING_DISCOUNT_KIND)
    return None if found is None else found(**kwargs)


def accounts_on_the_books(**kwargs: Any) -> int | None:
    """The DENOMINATOR of p061's `16.3%` — customers' own as-at membership count.

    ⚠ **READ RATHER THAN RE-DERIVED, AND THAT IS HARD-WON LAW 5.** *Membership
    as at a date* is decided in exactly one place; a second derivation here would
    make the census and this report state two different sizes for one utility on
    one day, and the difference would be invisible because both numbers are
    plausible and neither screen shows the other.
    """
    found = resolve(
        CUSTOMERS_MODULE, "accounts_on_the_books", kind=CUSTOMERS_ACCOUNTS_DATASET_KIND
    )
    return None if found is None else found(**kwargs)


REPORTS_PLANS_KIND = "plans_and_discounts"


def plans_and_discounts(**kwargs: Any) -> dict[str, Any] | None:
    """R27 — one row per ENROLMENT, merged from three modules' streams.

    ⚠ **THIS SEAM POINTS AT `reports` ITSELF AND THAT IS NOT A MISTAKE.** R27's
    spine is owned by nobody: `BR-REP-040` makes it a merge of three tables in
    three modules, and B1 forbids any one of them from reading the other two. So
    the merge is `reports`' own read, and it is reached through this file for the
    same reason every other report is — `G20` reads this file as the list of
    what reports genuinely reads, and a read that bypassed it would be invisible
    to that check.
    """
    found = resolve("reports", "plans_and_discounts", kind=REPORTS_PLANS_KIND)
    return None if found is None else found(**kwargs)


def plans_and_discounts_stream(**kwargs: Any) -> Any | None:
    """EVERY row of R27 — a generator, with no `page` and no `per`."""
    found = resolve("reports", "plans_and_discounts_stream", kind=REPORTS_PLANS_KIND)
    return None if found is None else found(**kwargs)


def plans_and_discounts_constant(name: str) -> Any | None:
    """One published constant of the merge — its sort vocabulary."""
    return resolve_constant("reports", name, kind=REPORTS_PLANS_KIND)


# ── CR-179-BRC10 · THE RATE IMPACT REPORT (`apps/reports/rate_impact.py`) ────
#
# Four owners, one question each, and every one is a READ:
#
#   apps.rating.rate_impact_reads.items(service_codes)                 -> list
#   apps.rating.rate_impact_reads.versions(tariff_ids, charge_ids)     -> list
#   apps.rating.rate_impact_reads.capacities(refs)                     -> dict
#   apps.rating.rate_impact_reads.version_model(tariff_id, version_id) -> dict
#   apps.rating.rate_impact_reads.units_on_items(tariff_ids, charge_ids, start, end)
#       Plans & Rates: what can be modelled, its versions, the sizes each
#       version uses with the figures on file, and which units' plans carried
#       each item in the window (process steps 1–2).
#   apps.customers.selectors.accounts_on_units_in_window(unit_ids, start, end)
#   apps.customers.selectors.account_type_options()
#       The accounts open in the period on those units, with their class
#       (step 3), and the class vocabulary for the input.
#   apps.metering.selectors.monthly_usage_by_account(account_ids, service_code, start_month, end_month)
#   apps.metering.selectors.connection_sizes_for_units(unit_ids, service_code)
#   apps.metering.selectors.billable_size_groups_for_units(unit_ids, service_code, as_of)
#   apps.metering.selectors.bills_one_line_per_size(service_code)
#       The usage the bill prints (step 6), today's meter size (step 4,
#       confirmed rule 4) and today's items by size (confirmed rule 5) — both
#       read from ASSETS by metering's own seam, never joined here — and
#       whether a service bills a COUNT of items (trash, fire).
#   apps.billing.reporting.rate_impact_billed(tariff_ids, charge_ids, start, end)
#       Revenue now — issued bills' lines, corrections included (step 5).
#
# `None` from any of these means *the owner does not publish this read*, and
# the report refuses by name rather than reading it as an empty utility.
RATING_RATE_IMPACT_KIND = "rate_impact_reads"


def tenant_today() -> Any | None:
    """`apps.tenancy.selectors.tenant_today()` — the utility's own business
    date, from which *"last month"* is counted (CR-179 §1 row 3)."""
    found = resolve(TENANCY_MODULE, "tenant_today", kind=TENANCY_KIND)
    return found() if found is not None else None


def rate_impact_items(service_codes: Any) -> list[dict[str, Any]] | None:
    found = resolve("rating", "items", kind=RATING_RATE_IMPACT_KIND)
    return None if found is None else found(service_codes)


def rate_impact_versions(tariff_ids: Any, charge_ids: Any) -> list[dict[str, Any]] | None:
    found = resolve("rating", "versions", kind=RATING_RATE_IMPACT_KIND)
    return None if found is None else found(tariff_ids, charge_ids)


def rate_impact_capacities(refs: Any) -> dict[str, list[dict[str, Any]]] | None:
    found = resolve("rating", "capacities", kind=RATING_RATE_IMPACT_KIND)
    return None if found is None else found(refs)


def rate_impact_version_model(tariff_id: Any, version_id: Any) -> dict[str, Any] | None:
    found = resolve("rating", "version_model", kind=RATING_RATE_IMPACT_KIND)
    return None if found is None else found(tariff_id, version_id)


def rate_impact_units(
    tariff_ids: Any, charge_ids: Any, start: Any, end: Any
) -> dict[str, list[str]] | None:
    found = resolve("rating", "units_on_items", kind=RATING_RATE_IMPACT_KIND)
    return None if found is None else found(tariff_ids, charge_ids, start, end)


def rate_impact_accounts(unit_ids: Any, start: Any, end: Any) -> list[dict[str, Any]] | None:
    found = resolve("customers", "accounts_on_units_in_window")
    return None if found is None else found(unit_ids, start, end)


def account_type_options() -> list[dict[str, Any]] | None:
    found = resolve("customers", "account_type_options")
    return None if found is None else found()


def rate_impact_usage(
    account_ids: Any, service_code: str, start_month: Any, end_month: Any
) -> dict[str, list[dict[str, Any]]] | None:
    found = resolve("metering", "monthly_usage_by_account")
    return None if found is None else found(account_ids, service_code, start_month, end_month)


def rate_impact_connection_sizes(unit_ids: Any, service_code: str) -> dict[str, Any] | None:
    found = resolve("metering", "connection_sizes_for_units")
    return None if found is None else found(unit_ids, service_code)


def rate_impact_size_groups(unit_ids: Any, service_code: str, as_of: Any) -> dict[str, Any] | None:
    found = resolve("metering", "billable_size_groups_for_units")
    return None if found is None else found(unit_ids, service_code, as_of)


def bills_one_line_per_size(service_code: str) -> bool | None:
    found = resolve("metering", "bills_one_line_per_size")
    return None if found is None else bool(found(service_code))


def rate_impact_billed(**kwargs: Any) -> list[dict[str, Any]] | None:
    found = resolve(BILLING_MODULE, "rate_impact_billed", kind=BILLING_KIND)
    return None if found is None else found(**kwargs)
