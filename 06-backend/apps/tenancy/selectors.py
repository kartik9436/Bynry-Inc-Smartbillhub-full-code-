# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-001/004 (subdomain resolver + live availability, S110/S114) ·
#           US-TEN-003 (S62 checklist computed from live data) · US-TEN-005 /
#           US-TEN-006 (S8 company + regional reads, current-period card) ·
#           US-TEN-007/008 (S8 services table) · US-TEN-009/010/011 (S8
#           reference-data cards + list reads) · US-TEN-012 (S8 numbering reads
#           + live preview)   Screens: S1, S8, S62, S110–S114
#           AMENDED 2026-08-09 (settings rule-page + logo gap lane): the five
#           rule-page reads (US-TEN-009 / EP-TEN-07 scope addendum; US-MET-011
#           for the S64 field set) + the logo reference (US-TEN-005)
#           Screens += S64, S66, S69, S70, S71
#           AMENDED 2026-08-15 (tenant custom-fields lane): US-TEN-014/017 (EP-TEN-09 — the S8 management read, the S8 card count, and
#           the BR-TEN-053 tenant-keyed registry cache every placed screen reads)
# Rules:    BR-TEN-003 (tenant resolved server-side — the BE-01 resolver; the source is
#           the /api/{tenant}/ path segment since the PO ruling 2026-08-10) ·
#           BR-TEN-011 (subdomain law) · BR-TEN-015 (checklist computed live) ·
#           BR-TEN-022 (period card computed, never stored) · BR-TEN-029 (counts
#           live, never cached) · BR-TEN-035 (preview allocates nothing) ·
#           BR-TEN-039 (holiday card) · BR-MET-020 (thresholds read from config,
#           never constants) · BR-TEN-019 (logo reference, never the bytes)
# Tests:    06-backend/tests/test_us_ten_*.py (per-story files)
#           AMENDED 2026-08-11 (tenant custom-fields lane): `document_safe_custom_fields`,
#           PUBLISHED FOR BILLING (B2 r17.1/r17.3; the three filters are
#           CLAUDE.md rule 1, BR-TEN-050 and the OQ-076 fail-closed ruling).
#           Its test cases live in tests/test_us_bil_028_custom_snapshot.py.
# Impacts:  core.tenancy resolver registration (apps.py) · apps/tenancy/api.py ·
#           S62 checklist · S8 Settings tabs · GET /public/* surfaces
# ───────────────────────────────────────────────────────
"""tenancy read path (LAW 0: api thin → services sole writer → selectors read).

Everything here is read-only and tenant-scoped through app.tenant_id context
(RLS on Postgres; the explicit tenant filters below keep the same law true on
the sqlite test DB — no cross-tenant queryset, CLAUDE.md rule 1). Platform
tables (tenants, subscription_plans, services) are RLS-exempt per B2 §3 and
read here for the public surfaces.

Also hosts the small PURE helpers shared with services (subdomain grammar,
US-state normalization) so validation and availability answer identically.
"""

import hashlib
import json
import logging
import re
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db.models import Q
from django.utils import timezone

from apps.tenancy import brand, models, sample_data, seams, settings_families
from apps.tenancy import logo as logo_law
from core import errors
from core import batch_reads
from core import numbering as core_numbering
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.tenancy")

# ── pure helpers (shared with services) ─────────────────────────────────────
_SUBDOMAIN_CHARSET_RE = re.compile(r"^[a-z0-9-]+$")

# BR-TEN-011 reserved labels — kept in services too? No: single source HERE.
#
# PO ruling 2026-08-10 (path-based tenancy): the value is now the first PATH
# segment of `/api/{tenant}/…`, so the list has to reserve everything that
# could shadow a ROUTE as well as everything that could shadow a hostname. A
# tenant named `api` would shadow the whole API surface; one named `jobs` or
# `exports` would be permanently unreachable at its own endpoints, because
# core.tenancy.NON_TENANT_SEGMENTS resolves those segments to "no tenant"
# BEFORE the resolver is ever called. The original DNS-era names all carry over
# unchanged (the ruling says so in as many words).
#
# `tenants` is the one name here the ruling did not enumerate: it is added
# because `POST /api/tenants` is a real route and the ruling's stated principle
# is to reserve anything that could collide with one. REPORTED in the build
# report rather than left implicit.
RESERVED_SUBDOMAINS = frozenset(
    {
        # DNS-era reservations (carried over unchanged, BR-TEN-011)
        "www",
        "app",
        "api",
        "admin",
        "mail",
        "billing",
        "support",
        "status",
        "help",
        "bynry",
        "smartbillhub",
        # route collisions under path tenancy (PO 2026-08-10)
        "signup",
        "signin",
        "pricing",
        "static",
        "assets",
        "public",
        "jobs",
        "exports",
        "health",
        "tenants",
        # CR-198-BRC10 — `/api/hooks/twilio/reply` is a no-tenant route.
        "hooks",
        # ⚠ ADDED 2026-09-16 (`CR-110-BRC04` phase 2, `DEF-INT-5546`). The
        # partner surface moved to `/api/partner/v1/…` — one base URL for every
        # partner and every utility, with the utility resolved from the key —
        # so `partner` became a real no-tenant first segment. A utility allowed
        # to take that slug would be unreachable at its own API, which is the
        # 2026-08-10 ruling's stated principle: reserve anything that could
        # collide with a route. `test_be01_tc16` asserts this set is a superset
        # of `core.tenancy.NON_TENANT_SEGMENTS`, so the two cannot drift.
        "partner",
        # ⚠ ADDED 2026-10-24 (`DEF-FLD-10580`, beta MQ-006). The field app's
        # first call is `POST /api/auth/activation/lookup` — no utility in the
        # path, because the code from the office is what names the utility —
        # so `auth` became a real no-tenant first segment.
        "auth",
    }
)

# US state / DC / PR vocabulary (US-TEN-001 §5). Names and USPS codes accepted.
US_STATES: dict[str, str] = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
    "puerto rico": "PR",
}
_STATE_CODES = frozenset(US_STATES.values())


def us_state_code(value: str) -> str | None:
    """'Texas' → 'TX' · 'TX' → 'TX' · unknown → None."""
    cleaned = value.strip()
    if cleaned.upper() in _STATE_CODES:
        return cleaned.upper()
    return US_STATES.get(cleaned.lower())


def subdomain_problem(subdomain: str) -> str | None:
    """BR-TEN-011 grammar: lowercase label [a-z0-9-], 3–63 chars, no edge
    hyphen, reserved names blocked. Returns the problem code or None (valid).

    The grammar is unchanged by the 2026-08-10 path ruling — the value is a URL
    path segment now instead of a DNS label, and every DNS constraint is a
    strict subset of what a path segment allows. Only RESERVED_SUBDOMAINS grew.
    """
    if not subdomain:
        return "required"
    if not _SUBDOMAIN_CHARSET_RE.match(subdomain):
        return "charset"
    if not 3 <= len(subdomain) <= 63:
        return "length"
    if subdomain[0] == "-" or subdomain[-1] == "-":
        return "edge_hyphen"
    if subdomain in RESERVED_SUBDOMAINS:
        return "reserved"
    return None


# ── tenant resolution + public surfaces (S110/S1) ───────────────────────────
def tenant_id_for_subdomain(subdomain: str) -> UUID | None:
    """The BE-01 resolver (registered via apps.py): slug → tenant_id or None.
    Platform read on the RLS-exempt tenants table (BR-TEN-003).

    Name and column stay `subdomain` after the 2026-08-10 path ruling: B2's
    column is unchanged and the decision-log row keeps that stored value as the
    slug. What changed is only what the kernel hands in — the first segment of
    `/api/{tenant}/…` instead of the Host's first DNS label.
    """
    return (
        models.Tenant.objects.filter(subdomain=subdomain.strip().lower(), deleted_at__isnull=True)
        .values_list("id", flat=True)
        .first()
    )


def subdomain_for_tenant(tenant_id: UUID | str | None) -> str | None:
    """The reverse of `tenant_id_for_subdomain`: id → slug, or None.

    `CR-198-BRC10` — the platform's text sender and the Twilio status-callback
    path both key on the utility's slug (`/api/{utility}/…`), and integrations
    may not read `tenants` through somebody else's ORM (BR-TEN-013). Platform
    read on the RLS-exempt registry, like its twin above.
    """
    if not tenant_id:
        return None
    return (
        models.Tenant.objects.filter(pk=tenant_id, deleted_at__isnull=True)
        .values_list("subdomain", flat=True)
        .first()
    )


def tenant_is_live(tenant_id: UUID | str | None = None) -> bool:
    """Is THIS utility one that may be served — not removed, and provisioned?

    `CR-110-BRC04` phase 2, PO 2026-09-16: *"you have to also check whether
    connector is activae whether tenant is active"*. The partner door asks this
    on every call, so the answer has to be one read and it has to be tenancy's,
    never integrations reading `tenants` through somebody else's ORM
    (`BR-TEN-013`, `B1`).

    **LIVE IS THE SAME TWO COLUMNS `live_tenant_subdomains` ALREADY USES**, and
    that is the point of putting it here rather than writing the predicate a
    second time in integrations: `deleted_at IS NULL AND provisioned_at IS NOT
    NULL`. A second copy would part company with this one the first time either
    moved, which is `DEF-094`'s shape.

    ⚠ **THE PATH RESOLVER ALREADY REFUSES A REMOVED UTILITY AND DOES NOT
    REFUSE AN UNPROVISIONED ONE.** `tenant_id_for_subdomain` filters
    `deleted_at__isnull=True` and nothing else, so a signup that stopped
    half-way resolves, sets a tenant context, and would have served a partner
    key issued against it. That half is what this read adds; the removed half
    is belt and braces, and belt and braces is the house style on this path for
    the reason `runners/serve._connection_for` records — the suite runs on
    SQLite, where RLS does not exist.

    `None` is refused rather than defaulted to the session's tenant: a caller
    that cannot say which utility it means must not be told yes (hard-won law 3).
    """
    if tenant_id is None:
        return False
    try:
        wanted = tenant_id if isinstance(tenant_id, UUID) else UUID(str(tenant_id))
    except (TypeError, ValueError):
        return False
    return models.Tenant.objects.filter(
        id=wanted, deleted_at__isnull=True, provisioned_at__isnull=False
    ).exists()


def live_tenant_subdomains() -> tuple[str, ...]:
    """Every utility that finished provisioning and has not been removed.

    **DEF-3422 — THE READ THIS MODULE WAS ASKED FOR BY NAME AND DID NOT HAVE.**
    `apps/notifications/schedule.py` paces one dispatch cycle per tenant and
    could not ask who the tenants were: B1 and BR-TEN-013 forbid it reading
    `tenancy.Tenant`, and this module published no *"every live tenant"* read.
    So the tenant list was an environment variable
    (`NOTIFICATIONS_DISPATCH_TENANTS`) and, unset — which is every deployment —
    **every firing dispatched to nobody**. Messages were queued correctly and
    delivered never, which is hard-won law 3 upside down: the default was the
    unsafe option, and it failed silently in a log nobody reads. That module's
    own exception note named this function as the one thing that would change
    when it existed; this is it.

    Platform read on the RLS-exempt `tenants` table (BR-TEN-003), the same
    posture as `tenant_id_for_subdomain` two functions up — it resolves the
    REGISTRY, never a tenant-hosted table, so it needs no tenant context and
    reaches no tenant's data.

    `provisioned_at` is the LIVE test rather than mere existence: a signup that
    crashed part-way leaves a row and no working utility, and pacing a dispatch
    cycle for it would report a refusal every five minutes forever.
    """
    return tuple(
        models.Tenant.objects.filter(deleted_at__isnull=True, provisioned_at__isnull=False)
        .order_by("subdomain")
        .values_list("subdomain", flat=True)
    )


def subdomain_availability(subdomain: Any) -> dict[str, Any]:
    """S110 live check — ADVISORY only; commit re-checks (BR-TEN-011)."""
    cleaned = str(subdomain or "").strip().lower()
    problem = subdomain_problem(cleaned)
    if problem is None and tenant_id_for_subdomain(cleaned) is not None:
        problem = "taken"
    return {"subdomain": cleaned, "available": problem is None, "problem": problem}


def pricing_plans() -> list[dict[str, Any]]:
    """S1/S112 public catalog (B10). Connection ranges are ADVISORY, never
    enforced (BR-TEN-002 — max_accounts is a commercial tier bound)."""
    return [
        {
            "id": str(plan.id),
            "code": plan.code,
            "name": plan.name,
            "price_month": str(plan.price_month),
            "currency": plan.currency,
            "min_accounts": plan.min_accounts,
            "max_accounts": plan.max_accounts,
        }
        for plan in models.SubscriptionPlan.objects.filter(deleted_at__isnull=True).order_by(
            "price_month", "code"
        )
    ]


def etag_for(payload: Any) -> str:
    """Weak content ETag for cacheable lookup GETs (11b G6 / B12 r1 3xx row)."""
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return f'"{digest[:16]}"'


# ── tenant-scoped helpers ───────────────────────────────────────────────────
def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _tenant_row() -> models.Tenant:
    row = models.Tenant.objects.filter(pk=_tenant_id()).first()
    if row is None:
        raise errors.NotFoundError()
    return row


def _settings_row() -> models.TenantSettings | None:
    return models.TenantSettings.objects.filter(tenant_id=_tenant_id()).first()


# ── The tenant's own clock (BR-TEN-020 · BR-TEN-043 · BR-TEN-081) ───────────
# A1 §S8's eight US zones — "8 US zones incl. Phoenix (no DST), Anchorage,
# Honolulu, Puerto Rico". This is the OFFERED set, not the ACCEPTED set:
# `services._validate_regional_changes` still takes any name ZoneInfo resolves,
# so a tenant already holding a zone outside these eight is never refused and
# never silently re-chosen. Narrowing acceptance to this tuple would break such
# a tenant's next save, which is why the two sets are deliberately different.
#
# It lives HERE rather than beside the SEED_* tuples in services.py only because
# services imports selectors and not the reverse; `tests/test_def_082_tenant_
# timezone.py` pins it against services.US_STATE_TIMEZONES (every zone signup
# can seed must be one a human can pick back) and against the frontend's
# mirrored TIMEZONE_OPTIONS, so neither copy can drift unnoticed.
TIMEZONE_CHOICES: tuple[str, ...] = (
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
    "America/Puerto_Rico",
)


def timezone_options(stored: str | None) -> tuple[str, ...]:
    """The zones a settings screen must offer given what the tenant HOLDS.

    DEF-082 (PO 2026-08-12): the shipped control offered a fixed eight and
    rendered EMPTY for a utility whose stored zone was not among them — the
    clock was set and invisible, and any later save of the tab read as a
    deliberate choice of blank. A list of choices that cannot express the
    current value is not a choice, so the stored zone always leads the list.
    """
    if stored and stored not in TIMEZONE_CHOICES:
        return (stored, *TIMEZONE_CHOICES)
    return TIMEZONE_CHOICES


def tenant_timezone() -> ZoneInfo:
    """**THE ONE DERIVATION of "what clock is this utility on"** (BR-TEN-081).

    Published as a selector — rather than left inline in `tenant_today` — so the
    WRITE half of BR-TEN-081 can read the same answer instead of computing its
    own. That is DEF-094: `tenant_today()` shipped reading the tenant's zone
    while `apps/payments/api._moment` went on anchoring a typed date at midnight
    **UTC**, so a Houston clerk typing *22 August* stored `2026-08-22T00:00:00Z`
    — 21 August 19:00 Central — and every screen then read it back through THIS
    function and displayed **21 August**. Two halves of one rule, each correct
    on its own terms, disagreeing by a day. A second copy of the fallback rule
    below would have been the same defect waiting to happen again, so there is
    exactly one.

    **UTC IS THE ANSWER FOR A TENANT THAT HAS NOT CHOSEN**, and it is a real
    answer rather than a guess: provisioning prefills the zone from the signup
    state (`services.default_timezone_for_state`) and leaves it NULL only when
    the state is unknown — *"an unset zone the user must choose beats a wrong
    zone they never noticed"*. Every screen in the product renders that tenant's
    dates in UTC, so anchoring their typed dates in UTC is what keeps the day
    they see equal to the day that was stored. **The mis-dating DEF-094 is about
    is the two halves DISAGREEING, not UTC itself.**

    An UNPARSEABLE stored name falls back the same way for the same reason.
    Tenancy validates the zone on save (`services._validate_regional_changes`),
    so this can only be reached by data that got in another way; answering UTC
    keeps the read and the write agreeing on such a tenant, which is the
    property that matters, and the two would part company the moment one of them
    raised and the other did not.

    Callers OUTSIDE tenancy must reach this BY NAME through their own seam
    (`apps/payments/settings_seam.tenant_timezone`), never by importing tenancy
    — B1 / BR-TEN-013.
    """
    settings_row = _settings_row()
    tz_name = settings_row.timezone if settings_row and settings_row.timezone else "UTC"
    try:
        return ZoneInfo(tz_name)
    except (KeyError, ValueError):
        return ZoneInfo("UTC")


def tenant_today() -> date:
    """Today in the tenant's timezone (Regional setting; UTC until it is set).
    Display-time only — never stamped into storage (BR-TEN-020/043).

    This is the read half of BR-TEN-081: the utility's OWN clock decides what
    day it is for every date the product derives, so the value a human picks on
    Settings → Company → Regional is what a numbering preview, an asset install
    date and a read window all answer under.

    **THE WRITE HALF IS LIVE SINCE 2026-08-15 (DEF-094)** and it reads
    `tenant_timezone()` above — the same function this one reads. This docstring
    used to say the write half *"belongs to whichever module collects it
    (apps/payments/api._moment is the live case) and is not done here"*, which
    was true and was exactly the hole: closing DEF-082 made the rule LOOK
    shipped while a typed date was still anchored at midnight UTC.
    """
    return timezone.now().astimezone(tenant_timezone()).date()


def tenant_now() -> datetime:
    """This instant, on the utility's OWN clock — `tenant_today()`'s sibling.

    ⚠ **IT IS HERE BECAUSE IT CANNOT BE ANYWHERE ELSE.** Gate G6 bans
    `timezone.now()` outright in `/rating/`, `/billing/`, `/ledger/` and
    `/payments/` (BR-TEN-043, the event-time law), and that ban is the whole
    point: a server clock read inside a money path decides a business day in the
    SERVER's timezone. Tenancy is where the utility's clock already lives —
    `tenant_today()` above is the same read, truncated — so a money path that
    needs the current instant resolves it through its own seam BY NAME, exactly
    as `apps/payments/settings_seam.tenant_timezone` already does.
    **One clock, one zone, one place.**

    First caller: `apps/payments/counters_api._required_moment`, which bounds a
    counter moment to the utility's own business day — PO ruling 2026-09-23,
    *"(b) Backdate within the same day"*. Deriving *"now"* there instead would
    be both a G6 violation and a second definition of the utility's day.

    Display and validation only — never stamped into storage (BR-TEN-020/043).
    A moment a person states still travels from the person.
    """
    return timezone.now().astimezone(tenant_timezone())


# ── S62 checklist (US-TEN-003 · BR-TEN-015) ─────────────────────────────────
# (code, kind): computed items complete from live data only; advisory items may
# be manually marked done (recorded + audited).
CHECKLIST_ITEMS: tuple[tuple[str, str], ...] = (
    ("company_profile", "computed"),
    ("services_uom", "computed"),
    ("rates_taxes", "advisory"),
    ("fiscal_billing", "computed"),
    ("numbering_documents", "advisory"),
    ("invite_team", "advisory"),
)
CHECKLIST_TARGETS = {
    "company_profile": "settings/company",
    "services_uom": "settings/services",
    "rates_taxes": "plans-rates",
    "fiscal_billing": "settings/regional",
    "numbering_documents": "settings/number-series",
    "invite_team": "settings/users",
}


def checklist() -> dict[str, Any]:
    """Computed from LIVE data at read time — never a stored to-do (BR-TEN-015).
    Advisory items whose owning module is not wired yet fall back to their
    recorded manual mark."""
    tenant = _tenant_row()
    manual = dict((tenant.checklist_state or {}).get("manual_done") or {})
    items: list[dict[str, Any]] = []
    for code, kind in CHECKLIST_ITEMS:
        computed = _checklist_item_state(code, tenant)
        manually = code in manual
        done = bool(computed) or (kind == "advisory" and manually)
        row = {
            "item": code,
            "kind": kind,
            "done": done,
            "source": "computed" if computed else ("manual" if done else None),
            "target": CHECKLIST_TARGETS[code],
        }
        notice = _checklist_item_notice(code)
        if notice is not None:
            row["notice"] = notice
        items.append(row)
    done_count = sum(1 for item in items if item["done"])
    return {
        "items": items,
        "progress": {"done": done_count, "total": len(items)},
        "complete": done_count == len(items),
    }


def _checklist_item_notice(code: str) -> dict[str, Any] | None:
    """A completed item that is nonetheless INCOMPLETE in a way that costs money.

    ⚠ **THIS IS `DEF-254`, AND THE SHAPE IS THE WHOLE DECISION.** Tax
    JURISDICTIONS are seeded at provisioning and tax RATES are not, so a tenant
    that declines the sample data has authorities and no prices — and issues
    every bill with **no tax at all**, silently. `rates_taxes` computes `done`
    from the SCHEDULE COUNT alone, so that tenant's checklist reads finished
    while the gap is wide open. Nothing else in the product asks the question:
    `issue.py` refuses a tax LINE whose authority has no liability account, by
    name, and cannot refuse a line that never gets created.

    ⚠ **A NOTICE AND NOT A REFUSAL, AND NOT A SEEDED RATE — the alternatives
    were considered and both are worse (decision log 2026-08-28).** SEEDING a
    rate is refused by the PO's own ruling: a wrong rate charges real customers
    real money, which is why the scaffold is rate-less on purpose and this must
    not reverse it. REFUSING on the path to issue is refused because *no tax* is
    a perfectly lawful configuration — a utility in a jurisdiction that taxes
    nothing would be unable to bill at all, and a product that cannot tell
    "nobody priced these" from "these are genuinely free" must not act as though
    it can. So the fact is REPORTED, with both numbers, and a human decides.

    ⚠ **`done` IS DELIBERATELY UNTOUCHED.** Flipping it would strand the
    no-tax utility on an onboarding checklist they can never complete, which is
    the same failure wearing the other coat.
    """
    if code != "rates_taxes":
        return None
    gap = seams.tax_pricing_gap()
    if gap is None:
        # Rating has not published the read — a different fact from "no
        # authorities", and not one to report to a person as though it were.
        return None
    if gap["jurisdictions"] == 0 or gap["priced"] > 0:
        return None
    return {
        "code": "tax_rates_unpriced",
        "jurisdictions": gap["jurisdictions"],
        "priced": 0,
    }


def _checklist_item_state(code: str, tenant: models.Tenant) -> bool:
    if code == "company_profile":
        # BR-TEN-015's example predicate: legal name + EIN + mailing + remit-to.
        return all((tenant.legal_name, tenant.ein, tenant.mailing_address, tenant.remit_to_address))
    if code == "services_uom":
        return models.TenantService.objects.filter(tenant_id=tenant.id, enabled=True).exists()
    if code == "rates_taxes":
        count = seams.rate_schedule_count()
        return bool(count) if count is not None else False
    if code == "fiscal_billing":
        settings_row = _settings_row()
        return bool(
            settings_row
            and settings_row.fy_start_month
            and settings_row.accounting_method
            and settings_row.close_cadence
        )
    if code == "invite_team":
        count = seams.member_count()
        return count is not None and count > 1
    return False  # numbering_documents: advisory-only (defaults are pre-seeded)


# ── CR-060 C7 / task T2 — what kind of organisation this tenant is ──────────
def organisation_type() -> str:
    """BR-TEN-1050 — `utility` · `sub_metering` · `hoa`, and NEVER a surprise.

    **THE FALLBACK IS THE RULE, NOT DEFENSIVE PROGRAMMING.** CR-060 C8's stated
    proof is *"an unknown value falls back rather than erroring"*, which is why
    `organisation_type` carries no CHECK constraint and why every read goes
    through here. Three states reach this function and all three answer
    `utility`:

    * **a tenant with no settings row at all** — reachable before the S8 tabs
      are first saved on any path that does not run `provision_tenant`;
    * **a row written before tenancy 0029** — impossible on a migrated host,
      because the migration backfills, and cheap to survive anyway;
    * **a value nobody recognises** — an import, a future migration, or a
      fourth type added to the vocabulary and rolled back.

    A screen that got a 500 here would be a Settings page that cannot load
    because of a single unrecognised word, which is a worse failure than
    showing the default and letting a human correct it in one click.
    """
    row = _settings_row()
    value = getattr(row, "organisation_type", None) if row is not None else None
    if value in models.ORGANISATION_TYPES:
        return str(value)
    return models.ORGANISATION_TYPE_UTILITY


# ── S8 Company profile reads (US-TEN-005) ───────────────────────────────────
def tenant_subdomain() -> str:
    """The tenant-in-context's slug — the `<tenant>` of every customer-facing
    address (`/<slug>/portal`). `DEF-NOT-10649`: the post-cut notice's link
    to the portal's pay page is built from it and `core.public_origin`."""
    return _tenant_row().subdomain


def company_profile() -> dict[str, Any]:
    tenant = _tenant_row()
    logo = logo_reference(tenant)
    ein_display = None
    if tenant.ein:
        ein_display = f"{tenant.ein[:2]}-{tenant.ein[2:]}" if len(tenant.ein) == 9 else tenant.ein
    return {
        "legal_name": tenant.legal_name,
        "dba_name": tenant.dba_name,
        # CR-060 C7 — an identity FACT, served beside legal name and DBA
        # because that is where identity lives and where the field is edited.
        # Read through `organisation_type()` so the screen inherits the ruled
        # fallback rather than rendering a raw column.
        "organisation_type": organisation_type(),
        "organisation_types": list(models.ORGANISATION_TYPES),
        "ein": ein_display,  # BR-TEN-018: displayed NN-NNNNNNN
        "state_utility_id": tenant.state_utility_id,
        "mailing_address": tenant.mailing_address,
        "support_phone": tenant.support_phone,
        "support_email": tenant.support_email,
        "website": tenant.website,
        "logo_file_id": tenant.logo_file_id,
        "logo": logo,
        # CR-048 wave D. `has_logo` is the ONE thing a renderer branches on, and
        # `mark` is always present beside it — so no caller has to work out
        # which of two fields is authoritative, and a screen can preview the
        # fallback without deleting the logo to see it.
        "has_logo": logo is not None,
        # CR-172-BRC10 — the cache key every `<img>` of the logo carries.
        "logo_ref": tenant.logo_file_id if logo is not None else None,
        "mark": company_mark(tenant),
        "brand_primary_hex": tenant.brand_primary_hex,
        "brand_accent_hex": tenant.brand_accent_hex,
        # CR-199-BRC10 S5 — where the logo in a customer email points (1A).
        "brand_logo_link_url": tenant.brand_logo_link_url,
        "remit_to_address": tenant.remit_to_address,
        # US-TEN-005 §5: payable-to defaults to DBA for display.
        "remit_payable_to": tenant.remit_payable_to or tenant.dba_name,
        "service_hours": tenant.service_hours,
    }


def logo_reference(tenant: models.Tenant | None = None) -> dict[str, Any] | None:
    """BR-TEN-019: the stored logo's REFERENCE — never the bytes.

    `logo_file_id` is the id of the logo's document in the common store
    (`CR-172-BRC10`); a row the move has not reached yet still carries its old
    `sha256:` reference and its bytes. The size is read from the stored
    document's own record (metadata only — no object is fetched).
    """
    row = tenant if tenant is not None else _tenant_row()
    if not row.logo_file_id or not row.logo_content_type:
        return None
    size: int | None = None
    if row.logo_bytes is not None:
        size = len(bytes(row.logo_bytes))
    else:
        stored = _stored_logo(row)
        size = stored.byte_length if stored is not None else None
    return {
        "logo_file_id": row.logo_file_id,
        "content_type": row.logo_content_type,
        "size_bytes": size,
    }


def _stored_logo(row: models.Tenant) -> Any:
    """The logo's stored-document record, under the session's tenant — or None.

    `document_store.reference()` resolves the row with the caller's own tenant
    filter (and RLS), so an id from another utility resolves to nothing here.
    """
    from apps.tenancy import document_store

    if not row.logo_file_id or str(row.logo_file_id).startswith("sha256:"):
        return None
    try:
        return document_store.reference(row.logo_file_id)
    except (document_store.DocumentStoreError, ValueError):
        return None


def logo_current_reference() -> str | None:
    """The session tenant's logo reference, read from its row alone — the ETag
    the logo route answers a revalidation with, without a trip to the store."""
    row = _tenant_row()
    if not row.logo_file_id or not row.logo_content_type:
        return None
    if row.logo_content_type == logo_law.SVG_CONTENT_TYPE:
        return _png_reference(row)  # DEF-TEN-10618 — served as its PNG copy
    return str(row.logo_file_id)


def logo_bytes(tenant: models.Tenant | None = None) -> tuple[bytes, str, str] | None:
    """The logo's BYTES for the one route that streams them:
    `(content, content_type, reference)`, or None when none is on file.

    ⚠ **READ FROM THE COMMON DOCUMENT STORE SINCE 2026-10-05 (`CR-172-BRC10`).**
    `document_store.fetch()` re-hashes what comes back and refuses a mismatch.
    A row the move has not reached yet (storage was down when `tenancy/0061`
    ran) still holds its bytes, and those are served — so a logo never
    disappears while it waits to be moved.

    **TENANT SCOPING IS THE WHOLE OF THE SECURITY HERE AND IT IS NOT OPTIONAL.**
    The function takes no tenant argument from a caller: `_tenant_row()`
    resolves the tenant from `app.tenant_id` and nothing else, and the stored
    document is resolved under that same context, so there is no parameter
    anyone could pass to reach another utility's logo. `tenants` is RLS-EXEMPT
    by B2 §3 and `stored_documents` is RLS-forced; both are proved in
    tests/test_cr172_logo_document_store.py on both vendors.
    """
    from apps.tenancy import document_store

    row = tenant if tenant is not None else _tenant_row()
    if not row.logo_file_id or not row.logo_content_type:
        return None
    if row.logo_content_type == logo_law.SVG_CONTENT_TYPE:
        return _legacy_svg_as_png(row)
    if row.logo_bytes is not None:
        return bytes(row.logo_bytes), row.logo_content_type, row.logo_file_id
    if _stored_logo(row) is None:
        return None
    return document_store.fetch(row.logo_file_id), row.logo_content_type, row.logo_file_id


def _png_reference(row: models.Tenant) -> str:
    """The ETag of a legacy SVG logo served as PNG — NOT the bare reference,
    so a browser that cached the SVG under the old ETag fetches the PNG."""
    return f"{row.logo_file_id}.png"


def _legacy_svg_as_png(row: models.Tenant) -> tuple[bytes, str, str] | None:
    """`DEF-TEN-10618` — an SVG logo stored before 2026-10-27 is SERVED as its
    PNG copy, never as the SVG itself (PO 2026-10-27: *"Allow PNG, JPG"*; the
    VAPT stored-XSS finding). The data is kept, not deleted: the SVG and its
    PNG rendering stay in the store on one `source_id`, and the PNG is the one
    `CR-172-BRC10` already made for print. A row the move has not reached yet
    still holds the cleaned SVG bytes, and those are rendered here (they were
    sanitised at upload, which is what makes `raster_png` safe to call)."""
    from apps.tenancy import document_models, document_store

    if row.logo_bytes is not None:
        return logo_law.raster_png(bytes(row.logo_bytes)), logo_law.PNG_CONTENT_TYPE, _png_reference(row)
    stored = _stored_logo(row)
    if stored is None:
        return None
    printed = document_store.for_source(
        source_type=document_models.SOURCE_TENANT_LOGO,
        source_id=stored.source_id,
        content_type=logo_law.PNG_CONTENT_TYPE,
    )
    if not printed.found:
        return None
    return document_store.fetch(printed.document.id), logo_law.PNG_CONTENT_TYPE, _png_reference(row)


def bill_logo() -> dict[str, Any] | None:
    """WHICH LOGO A BILL IS STAMPED WITH — published for billing (`CR-172-BRC10`).

    `{"document_id", "content_type": "image/png"}` naming the PNG a printed
    document draws (an SVG logo's rendering, or the PNG itself), or None when
    the utility has no logo in the store. BR-TEN-017: stamped at issue, so the
    bill keeps this exact picture whatever is uploaded later — the stored
    document is write-once. A logo still waiting on the row (not yet moved) is
    not stamped: a bill may only point at a write-once object.
    """
    from apps.tenancy import document_models, document_store

    row = _tenant_row()
    stored = _stored_logo(row)
    if stored is None:
        return None
    if stored.content_type == "image/png":
        return {"document_id": str(stored.id), "content_type": "image/png"}
    printed = document_store.for_source(
        source_type=document_models.SOURCE_TENANT_LOGO,
        source_id=stored.source_id,
        content_type="image/png",
    )
    if not printed.found:
        return None
    return {"document_id": str(printed.document.id), "content_type": "image/png"}


#: A logo is a few kilobytes and its stored document never changes, so the
#: decoded bytes are kept per process by (tenant, document) — a 36,000-bill run
#: fetches the picture once, not once per bill. Bounded; oldest out first.
_DOCUMENT_LOGO_CACHE: dict[tuple[str, str], bytes] = {}
_DOCUMENT_LOGO_CACHE_MAX = 64


def logo_png_for_documents(document_id: Any) -> bytes | None:
    """The PNG a printed document draws, by the id a bill was stamped with.

    Resolved under the session's tenant (`document_store.fetch`, which also
    verifies the hash), so a bill can only ever draw its own utility's logo.
    None — never an exception — when it cannot be read: a bill whose logo the
    store cannot return still prints, without the picture.
    """
    from apps.tenancy import document_storage, document_store

    if not document_id:
        return None
    key = (str(core_tenancy.current_tenant_id()), str(document_id))
    cached = _DOCUMENT_LOGO_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        ref = document_store.reference(document_id)
        if ref.kind != "tenant_logo" or ref.content_type != "image/png":
            return None
        payload = document_store.fetch(document_id)
    except (document_store.DocumentStoreError, document_storage.DocumentStorageError, ValueError):
        return None
    except Exception:  # noqa: BLE001 — a storage client error must not stop a bill printing
        return None
    if len(_DOCUMENT_LOGO_CACHE) >= _DOCUMENT_LOGO_CACHE_MAX:
        _DOCUMENT_LOGO_CACHE.pop(next(iter(_DOCUMENT_LOGO_CACHE)))
    _DOCUMENT_LOGO_CACHE[key] = payload
    return payload


def company_mark(tenant: models.Tenant | None = None) -> dict[str, Any]:
    """CR-048 wave D — the generated two-letter mark (CR-007, PO 2026-08-16).

    The letters come from the trading name falling back to the legal name, then
    to `tenants.name` — the one name a tenant has from the signup form, so the
    mark is never blank. The colour is the tenant's own `brand_primary_hex` and
    the LETTERS are black or white, whichever is readable on it. The rule, the
    threshold and the reason we choose the ink rather than refusing a colour
    are all in `apps/tenancy/brand.py`.
    """
    row = tenant if tenant is not None else _tenant_row()
    return brand.brand_mark(
        dba_name=row.dba_name,
        legal_name=row.legal_name,
        fallback_name=row.name or "",
        brand_primary_hex=row.brand_primary_hex,
    )


# ── S8 Regional + fiscal reads (US-TEN-006 · BR-TEN-022) ────────────────────
def currency_options() -> list[dict[str, Any]]:
    """The currencies a tenant may choose — `P0.8`, served rather than typed.

    Settings → Company drew Currency as a **free-text box** over a value the
    server already refused when unknown, so a clerk could type `US$`, press
    save, and be told no — with nothing on screen having ever said what the
    lawful answers were. The options now travel beside the value, out of
    `tenancy.Currency` (`P0.6`), so the control can be a picker.

    ⚠ **SERVED, NOT TYPED OUT IN THE FRONT END, AND THAT IS THE WHOLE POINT.**
    `CLAUDE.md`'s hard-won law 2 records what a hand-typed list costs: an
    eleventh utility service never appeared on screen while the row existed,
    the API served it, `tsc` passed and every test passed — because
    `SignupWizard.tsx` and `ratingShared.tsx` each held their own copy of the
    list. A currency added to the platform must appear in the picker with no
    front-end edit at all.

    Inactive rows are left out: `BR-TEN-036` makes a seeded row deactivatable
    and never deletable, so *withdrawn* has to mean *not offered* while the
    books that already reference it stay valid.
    """
    from apps.tenancy import models as tenancy_models  # local — import cycle

    return [
        {"code": row.code, "name": row.name, "symbol": row.symbol}
        for row in tenancy_models.Currency.objects.filter(is_active=True).order_by(
            "sort", "code"
        )
    ]


def regional_settings() -> dict[str, Any]:
    tenant = _tenant_row()
    settings_row = _settings_row()

    def s(field: str) -> Any:
        return getattr(settings_row, field) if settings_row else None

    return {
        "country": s("country"),
        "state": tenant.state,
        "timezone": s("timezone"),
        "language": s("language"),
        "first_day_of_week": s("first_day_of_week"),
        "currency": tenant.currency,
        #: `P0.8` — the picker's options travel with the value, so the screen
        #: never types the list out by hand. See `currency_options`.
        "currency_options": currency_options(),
        "number_format": s("number_format"),
        "date_format": s("date_format"),
        "time_format": s("time_format"),
        "fy_start_month": s("fy_start_month"),
        "fy_start_day": s("fy_start_day"),
        "accounting_method": s("accounting_method"),
        "close_cadence": s("close_cadence"),
        "close_day": s("close_day"),
        "lock_closed_periods": bool(s("lock_closed_periods")),
        "current_period": current_period(),
    }




# ── The shell's boot read (DEF-SHL-4272 · BR-SHL-252) ───────────────────────
#: The regional fields that are about DRAWING a value. Named as a constant and
#: not as a slice of `regional_settings()`, because the whole point of this
#: endpoint is the fields it does NOT carry: `accounting_method`,
#: `close_cadence`, `close_day` and `lock_closed_periods` are finance policy,
#: and `fy_start_month`/`fy_start_day` are the raw accounting-calendar
#: CONFIGURATION. A clerk needs none of them to print a date.
#:
#: ⚠ The computed period CARD is a separate constant below and IS served —
#: `DEF-SHL-4283` amended `BR-SHL-252` for it on 2026-09-06. Read that note
#: before assuming the calendar is absent from this endpoint; half of it is.
SHELL_DISPLAY_REGIONAL_FIELDS: tuple[str, ...] = (
    "country",
    "timezone",
    "language",
    "first_day_of_week",
    "currency",
    "number_format",
    "date_format",
    "time_format",
    #: `DEF-SHL-10116` (2026-10-14) — the utility's OWN state, which New
    #: Connection step 2 compares a typed address against (`CR-164-BRC10` Q7,
    #: *"City/State mismatch reason"*). It is where the utility is, not a
    #: finance policy, and step 2 read it from the Admin/Executive
    #: `GET /settings/regional` — so a Billing Clerk got 403 and silently lost
    #: the reason. `BR-SHL-252` amended the same day.
    "state",
)

#: The company fields the shell PAINTS: the name in the sidebar, the mark
#: beside it (which already carries the brand colour and its readable ink —
#: see `company_mark`), whether a logo exists at all, and the brand colour
#: itself. No EIN, no address, no support contacts, no remit-to.
SHELL_DISPLAY_COMPANY_FIELDS: tuple[str, ...] = (
    "legal_name",
    "dba_name",
    "has_logo",
    # CR-172-BRC10 — the logo's REFERENCE, which the front end puts in the
    # image address (`?v=`) so a replaced logo is a new address and is drawn at
    # once rather than from the browser's copy of the old one.
    "logo_ref",
    "mark",
    "brand_primary_hex",
)

#: The computed period card, MINUS `close_by` — `DEF-SHL-4283`, 2026-09-06.
#:
#: ⚠ **THIS IS THE HALF OF THE ACCOUNTING CALENDAR THAT A SCREEN NEEDS IN
#: ORDER TO DRAW ITSELF, AND WITHHOLDING IT LOCKED A BILLING CLERK OUT OF TWO
#: SCREENS A4 GIVES THEM.** `Reports → By premises` runs its report over
#: `current_period`, so a clerk who could not read the period got *"Set the
#: fiscal year start to see the current period."* — a false sentence, telling
#: them to do a thing only a System Admin can do — and the report never ran at
#: all. `Payments → Refunds` (A4 `payments_record`, Clerk **Full**, and the
#: screen the clerk RAISES refunds on) drew the same sentence in its header.
#:
#: **`close_by` IS DELIBERATELY NOT HERE, AND IT IS THE ONE FIELD OF THE CARD
#: THAT IS POLICY.** It is `close_day` in another shape — *"hand off to your
#: bookkeeper by Sep 3"* — a finance-close deadline belonging to the
#: `finance_reconcile_export` cell a Billing Clerk does not hold. `PeriodRollup`
#: has rendered the card without it since it was written (a tenant with no
#: `close_day` set gets exactly this), so nothing new has to be designed for
#: its absence. What a screen NEEDS is which period it is in and what window it
#: covers; when that period must be handed off is not a drawing fact.
SHELL_DISPLAY_PERIOD_FIELDS: tuple[str, ...] = (
    "fy_label",
    "period",
    "start",
    "end",
    "status",
)


def shell_display() -> dict[str, Any]:
    """BR-SHL-252 — the values every authenticated screen needs to draw itself.

    ⚠ **THIS EXISTS BECAUSE A BILLING CLERK COULD NOT USE THE PRODUCT AT ALL FOR
    SIXTEEN DAYS.** `DEF-SHL-4272`: the shell booted on `GET /settings/company`
    and `GET /settings/regional`, both gated `SettingsReadAnyWriteSystemAdmin`
    (`{system_admin, executive}`, because A4's `settings_lookups` row gives a
    Billing Clerk no cell), so a clerk signed in and every screen rendered
    *"We couldn't load your regional settings."* with a Retry that could not
    succeed.

    **The fix is a separation, not a widening.** Formatting and branding are
    not settings ADMINISTRATION — they are what a renderer needs before it can
    print a date or draw a sidebar. So this selector composes the DISPLAY half
    of two admin-only reads and nothing else. The four finance-policy fields on
    `regional_settings()` — accounting method, close cadence, close day,
    closed-period lock — and the raw calendar CONFIGURATION `fy_start_month` /
    `fy_start_day` are deliberately absent: a clerk should not receive a
    utility's close policy in order to render `03/04/2026`.

    ⚠ **AND THE COMPUTED PERIOD CARD IS SERVED, WHICH REVERSES ONE CLAUSE OF
    THAT SENTENCE AS IT WAS FIRST WRITTEN (`DEF-SHL-4283`, 2026-09-06).** The
    first cut of this selector excluded `current_period` alongside the four
    policy fields, because the only consumer under consideration was the app
    shell and the shell does not draw a period. Seven other screens do, and two
    of them are screens A4 gives a Billing Clerk: `Reports → By premises`
    (`reports`, Clerk **Run**) runs its report over the period and therefore did
    not run at all, and `Payments → Refunds` (`payments_record`, Clerk **Full**)
    headed itself *"Set the fiscal year start to see the current period."* over
    a tenant whose fiscal year start is set. **A period label is a drawing fact
    in exactly the way a date format is** — it is what a screen puts on a figure
    before there is a permission to have an opinion about. `close_by` is the one
    field of the card that is not, and `SHELL_DISPLAY_PERIOD_FIELDS` above says
    why it stays behind.

    **Composed from the two existing selectors rather than re-reading the rows**,
    so there is exactly one place that knows how a mark is built or how a
    currency is resolved, and this endpoint cannot drift from the Settings
    screen that edits the same values.

    The two families stay NESTED (`regional` / `company`) rather than flattened
    into one bag, because `country` and `legal_name` are facts about different
    things and a flat payload would invite the next lane to add a third fact
    with nowhere obvious to put it.
    """
    regional = regional_settings()
    company = company_profile()
    #: `current_period()` returns None when the tenant has not set a fiscal year
    #: start. That is a real state and it is published as `null` rather than as
    #: an invented calendar month — the same argument `tenantRegionalOf` makes
    #: for a date format it cannot draw (`DEF-SHL-3964` decision D3).
    card = regional["current_period"]
    return {
        "regional": {field: regional[field] for field in SHELL_DISPLAY_REGIONAL_FIELDS},
        "company": {field: company[field] for field in SHELL_DISPLAY_COMPANY_FIELDS},
        "period": (
            None if card is None else {field: card[field] for field in SHELL_DISPLAY_PERIOD_FIELDS}
        ),
    }

_ORDINAL_RE = re.compile(r"^(\d+)(?:st|nd|rd|th)?(?:\s+(business))?\s*day?s?$", re.IGNORECASE)


def current_period(reference_date: date | None = None) -> dict[str, Any] | None:
    """BR-TEN-022: the current-period card is COMPUTED from the fiscal fields,
    never stored. Status is 'open' — period close/lock enforcement is the
    ledger posting service's story (BR-TEN-023/038, wave 5)."""
    settings_row = _settings_row()
    if not settings_row or not settings_row.fy_start_month:
        return None
    ref = reference_date or tenant_today()
    month = settings_row.fy_start_month
    day = settings_row.fy_start_day or 1
    fy_start = _safe_date(ref.year, month, day)
    if ref < fy_start:
        fy_start = fy_start.replace(year=fy_start.year - 1)
    fy_end_year = fy_start.year + 1 if month > 1 or day > 1 else fy_start.year
    months_per_period = 3 if settings_row.close_cadence == "quarterly" else 1
    months_elapsed = (ref.year - fy_start.year) * 12 + (ref.month - fy_start.month)
    if ref.day < fy_start.day:
        months_elapsed -= 1
    period_index = months_elapsed // months_per_period  # 0-based
    period_start = _add_months(fy_start, period_index * months_per_period)
    period_end = _add_months(period_start, months_per_period) - timedelta(days=1)
    close_by = _close_by_date(settings_row.close_day, period_end)
    return {
        "fy_label": f"FY{fy_end_year}",
        "period": period_index + 1,
        "start": period_start.isoformat(),
        "end": period_end.isoformat(),
        "status": "open",
        "close_by": close_by.isoformat() if close_by else None,
    }


def _add_months(anchor: date, months: int) -> date:
    month_index = anchor.month - 1 + months
    return _safe_date(anchor.year + month_index // 12, month_index % 12 + 1, anchor.day)


def _safe_date(year: int, month: int, day: int) -> date:
    """A real calendar date, clamping day into the month (Feb 29 → 28 off-leap)."""
    lengths = [31, 29 if _leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(year, month, min(day, lengths[month - 1]))


def _leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _close_by_date(close_day: str | None, period_end: date) -> date | None:
    """'3rd business day' → the 3rd business day after period end (Mon–Fri,
    tenant holidays skipped); '5 days' → calendar days. Unparseable → None."""
    if not close_day:
        return None
    match = _ORDINAL_RE.match(close_day.strip())
    if not match:
        return None
    count, business = int(match.group(1)), bool(match.group(2))
    if count < 1:
        return None
    if not business:
        return period_end + timedelta(days=count)
    holidays = set(
        models.HolidayCalendar.objects.filter(
            tenant_id=_tenant_id(),
            holiday_date__gt=period_end,
            holiday_date__lte=period_end + timedelta(days=count * 4 + 10),
        ).values_list("holiday_date", flat=True)
    )
    cursor, seen = period_end, 0
    while seen < count:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5 and cursor not in holidays:
            seen += 1
    return cursor


# ── S64/S66/S69/S70/S71 rule-page reads (11b §2.3 · BR-TEN-043) ─────────────
def settings_family(slug: str) -> dict[str, Any]:
    """One rule page's CURRENT parameter set (flat document, decimals as
    strings). Unknown slug → 404 through the framework, never a guessed page.

    Values are what the tenant stored; a parameter the stored document does not
    carry yet renders its ratified seeded default (settings_families.merge) —
    the row itself is seeded at migration and rewritten in full on every save,
    so the database, not a constant, is what engines read (BR-MET-020)."""
    family = settings_families.FAMILIES.get(slug)
    if family is None:
        raise errors.NotFoundError()
    row = _settings_row()
    document = getattr(row, family.document_field, None) if row else None
    columns = {p.column: getattr(row, p.column) for p in family.params if p.column} if row else {}
    return settings_families.merge(family, document, columns)



# ── S107 Settings → Billing plan (11b §2.16 · DEF-1092) ─────────────────────
#
# ⚠ **WHAT A UTILITY PAYS BYNRY, AND NOTHING ELSE.** Every figure below comes
# from the four PLATFORM tables `tenancy/0021` calls out by name — a different
# class of money from what a utility's customers pay them — and none of it may
# ever appear in Billing, Payments, Finance or Reports. That boundary is A1's
# own sentence on the S107–S109 rows and it is why this read lives here rather
# than anywhere a bill can reach it.
#
# ⚠ **THIS READ EXISTS BECAUSE `DEF-1092` SAID IT DID NOT.** `subscriptions`
# has been seeded since `tenancy/0005` — sixteen days — `implementation_orders`
# since `0021`, and until this function nothing in the product could render
# either. A tenant carried a quotable `IMPL-26-0001` that no human being could
# see anywhere.
#
# ⚠ **THREE THINGS r10 SET-15 DRAWS ARE DELIBERATELY NOT SERVED, and each has
# a reason rather than an omission** (hard-won law 1 — a comment claiming a
# guarantee is not the guarantee, so these are claims about ABSENCE and each
# names what would close it):
#
#   1. **A PER-CONNECTION RATE** — r10 draws `$0.85 / connection` × `1,247`
#      = `$1,059.95`. No such column exists in `subscription_plans` and the
#      commercial model the PO gave on 2026-08-26 is BANDED
#      (`$1,000` / `$5,000` / `$8,000`). Serving a rate would be inventing the
#      money this screen is about. **`DEF-1220`.**
#   2. **THE CONNECTION COUNT** — the band is real (`min_accounts` /
#      `max_accounts`) and the word *connection* is defined in no glossary and
#      no contract in this repo. Accounts, units, service points and meters are
#      four different figures on one tenant and the band boundary between
#      `$5,000` and `$8,000` sits on exactly that ratio, so the count is served
#      as `null` beside its reason. **`OQ-660`**, open.
#   3. **PLATFORM INVOICES AND A PAYMENT METHOD** — S108 and S109. There is no
#      invoice table, no payment-method column and no route on the platform
#      side of this product; the register carries all three in
#      `screen_story_coverage.txt`, and OQ-015 ruled that v1 takes no card at
#      all. Served as stated absences so the screen can say so.


def _order_dict(order: models.ImplementationOrder) -> dict[str, Any]:
    """One implementation order, exactly as stored.

    Money is a STRING beside its `CHAR(3)`, never a float and never a number
    the JSON layer may re-render (CLAUDE.md hard rule 2): stored to 4 decimals,
    displayed to 2 by the screen. `duration_months` is an INT of months —
    A1 still prices four packages in WEEKS and the PO ruled months on
    2026-08-27, which is `DEF-1222`; this serves the column, not the spec.
    """
    return {
        "order_no": order.order_no,
        "duration_months": order.duration_months,
        "price": str(order.price),
        "currency": order.currency,
        "instalments": order.instalments,
        "status": order.status,
        "started_on": order.started_on.isoformat() if order.started_on else None,
        "delivered_on": order.delivered_on.isoformat() if order.delivered_on else None,
        #: The PO's own word for a zero-month order, answered from the DATA by
        #: the model's own property — never recomputed here, because two places
        #: that can each say whether an order is self-serve is two places that
        #: can disagree.
        "is_self_serve": order.is_self_serve,
    }


def _tenant_addon_dict(row: models.TenantAddon) -> dict[str, Any]:
    """One add-on this tenant holds, with the price that actually applies.

    `tenant_addons.price_month` is NULLABLE and null means *whatever the
    catalogue says today* (the model's own rule). So the payload carries BOTH:
    `price_month` is the effective figure and `price_source` says which row it
    came from, because a screen showing one number cannot otherwise tell a
    negotiated price from a catalogue price — and a catalogue price change
    reaches the second and not the first.
    """
    negotiated = row.price_month is not None
    return {
        "code": row.addon.code,
        "name": row.addon.name,
        "price_month": str(row.price_month if negotiated else row.addon.price_month),
        "currency": row.addon.currency,
        "price_source": "negotiated" if negotiated else "catalogue",
        #: FALSE until somebody sets a real price on the CATALOGUE row. A
        #: negotiated figure is a price somebody chose, so it is always priced.
        #: The $1.00 default is the PO's placeholder (2026-08-27, verbatim:
        #: *"we will add price latet currently you default it to $1"*) and a
        #: dollar that means nothing must not look like a considered price.
        "priced": True if negotiated else row.addon.priced,
        "started_on": row.started_on.isoformat() if row.started_on else None,
        "ended_on": row.ended_on.isoformat() if row.ended_on else None,
    }


def subscription_overview() -> dict[str, Any]:
    """S107 — what this tenant buys from Bynry: plan, implementation, add-ons.

    ⚠ **CORRECTED 2026-09-07 (`DEF-TEN-4446`) — THIS PARAGRAPH USED TO SAY THE
    OPPOSITE, AND IT WAS TRUE WHEN IT WAS WRITTEN.** It read: *"Tenant-scoped by
    an EXPLICIT filter and not by RLS. These four tables are RLS-EXEMPT platform
    data on purpose … the `tenant_id=` below is the only thing that stops one
    utility reading another's price."* That was an accurate description of a
    database in which `implementation_orders` and `tenant_addons` carried no
    policy — which B2 §3 never permitted, and which `tenancy/0042` has fixed.
    Leaving the sentence would have left the next reader believing an app-layer
    filter is the only guard, which is exactly the reading that produced the
    hole (hard-won law 1: a comment claiming a guarantee is not the guarantee).

    **What is true now:** all four tables are tenant-scoped in the DATABASE.
    `subscriptions`, `implementation_orders` and `tenant_addons` each carry the
    B2 §3 policy with FORCE, so a read with no `app.tenant_id` returns zero rows
    and a read under another utility's context cannot reach these. `addons` is
    the platform CATALOGUE and has no `tenant_id` at all — nothing in it belongs
    to a utility. The `tenant_id=` filters below stay, and are now belt-and-
    braces rather than the whole belt: they keep this selector honest on sqlite,
    where row-level security does not exist and every test in the default suite
    runs. `test_def1092__the_read_is_scoped_to_the_calling_tenant` holds the app
    half; `tests/test_def_ten_4446_commercial_rls.py` holds the database half.

    ⚠ **AND THE SCREEN STILL SHOWS THE PLAN.** This read reaches the database
    inside the tenant's own context — `TenantContextMiddleware` resolves the
    slug from the path and SETs `app.tenant_id` before any view runs, and
    `require_tenant(request)` in `api.subscription` refuses the request when it
    did not. Checked rather than assumed: a policy over a context-free read is a
    live screen going blank, not a test going red.

    Every absence is STATED with the id that would close it, never rendered as
    a zero: `null` here means *nobody can answer this*, and `0` would mean
    *the answer is none* (the DEF-127 distinction this product turns on).
    """
    tenant_id = _tenant_id()
    subscription = (
        models.Subscription.objects.select_related("plan")
        .filter(tenant_id=tenant_id)
        .order_by("created_at")
        .first()
    )
    order = (
        models.ImplementationOrder.objects.filter(tenant_id=tenant_id)
        .order_by("created_at")
        .first()
    )
    addons = [
        _tenant_addon_dict(row)
        for row in models.TenantAddon.objects.select_related("addon")
        .filter(tenant_id=tenant_id)
        .order_by("started_on", "created_at")
    ]
    plan = subscription.plan if subscription is not None else None
    return {
        "subscription": (
            None
            if subscription is None
            else {
                "status": subscription.status,
                "trial_ends_at": (
                    subscription.trial_ends_at.isoformat()
                    if subscription.trial_ends_at
                    else None
                ),
                "started_at": (
                    subscription.started_at.isoformat() if subscription.started_at else None
                ),
            }
        ),
        "plan": (
            None
            if plan is None
            else {
                "code": plan.code,
                "name": plan.name,
                "price_month": str(plan.price_month),
                "currency": plan.currency,
                "min_accounts": plan.min_accounts,
                "max_accounts": plan.max_accounts,
            }
        ),
        "implementation_order": None if order is None else _order_dict(order),
        "addons": addons,
        #: The number of rows in the platform CATALOGUE, so the screen can tell
        #: *this tenant has taken none* from *there is nothing to take*. Seeded
        #: EMPTY by ruling: the PO named no add-on and gave only the placeholder
        #: price, and inventing a product's name is the same class of error as
        #: inventing its price.
        "addon_catalogue_size": models.Addon.objects.filter(active=True).count(),
        #: ── The three stated absences, each with what closes it ────────────
        #: r10's entitlement line counts "connections"; the word is defined
        #: nowhere and the band boundary it decides is $5,000 against $8,000.
        "connections": None,
        "connections_unavailable": "OQ-660",
        #: r10 draws three subscription invoices from Bynry. No platform
        #: invoice table, column or route exists (S108, W8).
        "invoices": None,
        "invoices_unavailable": "S108",
        #: r10 draws "card on file ending 4242". OQ-015 ruled v1 takes no card
        #: at all, so there is nothing to store and nothing stores it (S109).
        "payment_method": None,
        "payment_method_unavailable": "S109",
    }


# ── S8 Services & UoM reads (US-TEN-007/008) ────────────────────────────────
def services_overview() -> list[dict[str, Any]]:
    """One row per ACTIVE platform catalog service (closed set, BR-TEN-025) in
    catalog sort order; counts live via owning-module seams (None while a
    neighbor lane is unwired — rendered '—', never guessed as 0 on screen)."""
    # `DEF-TEN-8731` — the active-account column is counted ONCE for every
    # service, not once per row: eleven per-service passes over every open
    # agreement were 13.6 s at 10,015 accounts and a 60 s worker kill at 40,000.
    counts = seams.active_account_counts()
    return [
        service_row(code, active_account_counts=counts)
        for code in models.Service.objects.filter(active=True)
        .order_by("sort", "code")
        .values_list("code", flat=True)
    ]


_COUNT_EACH = object()


def service_row(service_code: str, *, active_account_counts: Any = _COUNT_EACH) -> dict[str, Any]:
    service = models.Service.objects.filter(code=service_code, active=True).first()
    if service is None:
        raise errors.NotFoundError()
    row = (
        models.TenantService.objects.filter(tenant_id=_tenant_id(), service=service)
        .select_related(
            "primary_uom", "alt_uom", "billed_uom", "revenue_account", "base_revenue_account"
        )
        .first()
    )
    return {
        "service": service.code,
        "name": service.name,
        "enabled": bool(row and row.enabled),
        # ── BR-RAT-081 + r6.4, SERVED SINCE 2026-08-28 (DEF-2310 / DEF-2311) ──
        # The three columns a utility could not reach from anywhere. They are
        # served for a service that is OFF as well as one that is on, because
        # the S8 table renders them on every row: a declaration a tenant cannot
        # SEE is the shape that let `metered` sit unwritten for eight days.
        #
        # ⚠ **`metered` IS GONE FROM THIS PAYLOAD AND `billing_basis` REPLACES
        # IT — `BR-TEN-1180`, 2026-09-02, a CLEAN CUT WITH NO SHIM.** The PO
        # ruled the cut allowable in as many words: *"we are in beta stage - so
        # no real utility is actually onboarded yet - so there is no real data
        # yet - hence you can fix it; I will delete the DB and relaunch"*.
        # Serving both keys would let a screen keep asking the two-state
        # question and get a confident answer for a service that is neither
        # metered nor counted — which is `DEF-2409` exactly, one layer up.
        #
        # The value DEFAULTS to `metered` on a tenant provisioned before the
        # row existed, for the reason the boolean defaulted True: a tenant with
        # no row for a service has declared NOTHING, and "nothing declared" is
        # metered (hard-won law 3 — the unsafe option is the one you type).
        "billing_basis": models.BILLING_BASIS_METERED if row is None else row.billing_basis,
        # `DEF-RAT-10220` — the unit this service's size classes SUM in, or
        # `None` when they do not sum (`service_size_classes.
        # capacity_uom_for_service`, configuration, never a name list). Settings
        # asks a size class for its capacity exactly when this is set.
        "capacity_uom": _capacity_uom(service.code),
        "primary_uom": row.primary_uom.code if row and row.primary_uom else None,
        "alt_uom": row.alt_uom.code if row and row.alt_uom else None,
        # `None` means *the register's own unit is what is billed* and is the
        # ordinary answer — never "unconfigured, refuse" (see
        # `service_billed_uoms`, whose reading this must not contradict).
        "billed_uom": row.billed_uom.code if row and row.billed_uom else None,
        # 4-dp money / 6-dp percentages travel as STRINGS beside their meaning
        # (CLAUDE.md rule 2); a factor is NUMERIC(18,6) and takes the same
        # treatment, so no JSON float ever carries one.
        "conversion_factor": (
            None if row is None or row.conversion_factor is None else str(row.conversion_factor)
        ),
        # The GL half (PO ruling 2026-08-11, OQ-115 — *"allow tenant user to
        # override it"*). Rendered here rather than only in the ledger's own
        # read because `update_tenant_service` RETURNS this row: a tenant who
        # re-points water revenue has to see where it now points, and a write
        # whose response cannot show what it wrote is a screen nobody can trust.
        # Both id AND code travel: the id is what an edit sends back, the code
        # is what a human recognises.
        "revenue_account": _account_ref(row.revenue_account if row else None),
        "base_revenue_account": _account_ref(row.base_revenue_account if row else None),
        "rate_schedules": seams.rate_schedule_count(service_code=service.code),
        # A caller drawing the whole table hands in the one-pass counts
        # (`services_overview`); a caller asking for one row counts that one.
        # `None` from the batch means customers is unwired — the singular's own
        # None — never a zero.
        "active_accounts": (
            seams.active_account_count(service.code)
            if active_account_counts is _COUNT_EACH
            else (
                None
                if active_account_counts is None
                else active_account_counts.get(service.code, 0)
            )
        ),
    }


def service_scope_filter(service_code: str) -> Q:
    """THE rule, as ONE expression, for EVERY service-scoped reference list: a
    row is valid for a service when it is scoped to that service or scoped to
    none.

    **NULL is a VALUE and the two lists read it differently while behaving
    identically.** On `uoms` it is *"All services"* (PO 2026-08-16); on
    `service_size_classes` it is *"nobody has said"* (CR-065, PO 2026-09-02) —
    a size class a tenant added that carries no tag. Either way the row is
    OFFERED, because `BR-TEN-071` forbids deleting a tenant's own row and a row
    a tenant owns that no screen will show them is worse than an untidy list.

    It lives here, alone, because it is asked in places that must never drift —
    a picker decides what to OFFER and a write decides what to ACCEPT, and a
    screen that draws the right options while the API accepts anything is the
    shape DEF-184 already took once.
    """
    return Q(service__isnull=True) | Q(service__code__iexact=service_code)


def _capacity_uom(service_code: str) -> str | None:
    """`service_size_classes.capacity_uom_for_service`, with an unruled
    dimension (`SizeClassNotRuled`, OQ-560) or an unknown code answering
    `None` — *do not sum* is the right answer to all three."""
    from apps.tenancy import service_size_classes as ladder

    try:
        return ladder.capacity_uom_for_service(service_code)
    except (KeyError, ladder.SizeClassNotRuled):
        return None


def size_class_capacities(service_code: str) -> dict[str, Any]:
    """**How much each of THIS tenant's sizes of one service IS** —
    `{code.casefold(): Decimal}` for every `service_size_classes` row tagged to
    `service_code` that carries a capacity. `DEF-RAT-10220` (PO 2026-10-17).

    The ONE read behind a capacity total: `metering.seams.
    total_installed_capacity` hands this to `service_size_classes.
    total_capacity`, where a row here wins over the ratified ladder. Built-in
    sizes carry the ladder's figure in the same column (seeded and back-filled
    by `tenancy/0064`), so a tenant-added `SOL-P47.84` at 47.84 kW is read
    exactly as the built-in `SOL-P10` at 10 kW is — no code list, no name read.

    Only rows TAGGED to the service count: an untagged row (*"nobody has
    said"*) has no unit to be a quantity in (hard rule 3). Explicit tenant
    filter AND RLS (hard rule 1), so another tenant's figure can never answer.
    Codes are keyed case-folded because a code is unique per tenant
    case-insensitively (`uq_meter_size_classes_tenant_code_ci`).

    No tenant in context (a platform-level caller) answers `{}` — the ladder
    alone, which is the platform's own figure — rather than raising.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        return {}
    rows = models.MeterSizeClass.objects.filter(
        tenant_id=tenant_id,
        service__code__iexact=service_code,
        capacity__isnull=False,
    ).values_list("code", "capacity")
    return {str(code).strip().casefold(): capacity for code, capacity in rows}


def uom_scope_filter(service_code: str) -> Q:
    """The UoM reading of `service_scope_filter` — see it for the rule.

    ⚠ **KEPT AS A NAME, NOT AS A SECOND COPY (CR-065).** `uoms` was the only
    scoped list from CR-004 until 2026-09-02, so this expression was written
    for it and is cited by name from `uoms_for_service`, from
    `_apply_service_uom` and from the DEF-184 tests. A second list became scoped
    that day; the RULE moved up to `service_scope_filter` and this stayed, so
    those citations still resolve and there is still exactly one expression.
    """
    return service_scope_filter(service_code)


def uoms_for_service(service_code: str, *, include_inactive: bool = False) -> list[dict[str, Any]]:
    """The units a SET-03 picker may offer for one utility service (DEF-184).

    **The rule, in one line: scoped to THIS service, PLUS everything scoped to
    none.** A NULL `service` means "All services" (PO ruling 2026-08-16, CR-004
    task A3), so an unscoped unit — a tenant's own `GJ`, or a seeded unit two
    services both claim like `ccf` — is offered everywhere, and a unit scoped to
    another service is offered nowhere else. With today's seed a water service
    is offered `kgal`, `ccf` and `month` and is NOT offered `therm`, `kWh` or
    `kW`, which is the defect this closes.

    BR-TEN-029 still applies and is applied FIRST: a deactivated entry leaves
    every picker, scoped or not. `include_inactive` exists for the one caller
    that must render a row whose stored unit has since been deactivated — it
    widens the list and is never the default.

    An unknown or misspelled `service_code` returns only the unscoped units
    rather than raising: this is a picker feed, and the screen that asks about a
    service it cannot name has a bigger problem than an empty dropdown. The
    WRITE is where a bad service is refused (`update_tenant_service`).
    """
    qs = models.Uom.objects.filter(tenant_id=_tenant_id())
    if not include_inactive:
        qs = qs.filter(active=True)  # BR-TEN-029
    qs = qs.filter(uom_scope_filter(service_code))
    return [
        {
            "id": str(row.id),
            "code": row.code,
            "name": row.name,
            # None is the VALUE "All services", not a missing field — the same
            # shape UomLookupHandler.serialize publishes, so a picker and the
            # list view read one contract.
            "service": row.service.code if row.service_id else None,
        }
        for row in qs.select_related("service").order_by("code", "id")  # IS-2 stable secondary
    ]


def _account_ref(account: Any) -> dict[str, str] | None:
    """`{"id", "code", "name"}` for a mapped GL account, or None for unmapped.

    None is a REAL answer on this screen — a service with no revenue account
    cannot have its lines stamped at issue (BR-BIL-010) — so it is rendered as
    a gap rather than hidden behind a blank string.
    """
    if account is None:
        return None
    return {"id": str(account.id), "code": account.code, "name": account.name}


# ── S8 Reference data reads (US-TEN-009/010/011 · BR-TEN-029) ───────────────
def lookup_cards() -> list[dict[str, Any]]:
    """The card grid: one card per WIRED list with its live count (BR-TEN-029 —
    computed at render, never cached). Lists whose owning lane has not landed
    are absent (skip-until-wired); the Document & message templates card is
    client navigation only — tenancy stores nothing for it (BR-TEN-033).

    ⚠ **IT IS BUILT FROM `reference_data_report()` NOW, AND THAT IS DEF-336.**
    This function used to walk `LOOKUP_LISTS` itself and serve `{list, owner,
    count}`. Two consequences, both invisible until the PO photographed the
    grid:

    * **A card carried no STATE**, so the screen had to infer one from a bare
      number. It could tell "12" from "no card at all" and nothing else, which
      is why every non-list card rendered as a naked chevron.
    * **`if definition.handler is None: continue` dropped a SEEDED list.** The
      report has had a name for that case since DEF-026 — `uncounted`: no
      handler to count it live, but `reference_seed_runs` PROVES rows landed.
      The report said so and the grid silently omitted the card, so the one
      list whose data exists and whose count cannot be taken was the one list
      a System Admin never saw.

    Building from the report makes the screen and the seeder read the SAME
    sentence about the same list — they can no longer disagree, which is what
    `e2e/DEF-336-reference-counts.spec.ts` asserts in a browser. `state` is the
    report's own vocabulary (`seeded` · `empty` · `uncounted` · `unwired` ·
    `UNEXPLAINED`); the screen maps it to three renderings and never invents a
    fourth. The report's `reason` is deliberately NOT served: it names
    `apps.<module>`, `register_lookup_handler` and BR-TEN-031, and that is
    internal provenance (CR-016 / G28). The screen writes its own sentence.
    """
    from apps.tenancy import services  # late import: services imports selectors

    report = {row["list"]: row for row in services.reference_data_report()["lists"]}
    cards = []
    for code, definition in services.LOOKUP_LISTS.items():
        row = report.get(code)
        if row is None:  # a list in no report row cannot be described honestly
            continue
        # skip-until-wired, UNCHANGED except for the one case DEF-336 found: a
        # list with no handler is still absent from the grid, UNLESS the seed-run
        # ledger proves its rows exist, in which case it appears and says so.
        if row["count"] is None and row["state"] != "uncounted":
            continue
        cards.append(
            {
                "list": code,
                "owner": definition.owner,
                "count": row["count"],
                "state": row["state"],
            }
        )
    # EP-TEN-09 (BR-TEN-047): custom fields are a card in THIS grid, counted the
    # same way and in the same request. They are NOT a lookup list — a
    # definition has an entity, a data type and a placement map and no
    # `code`/`used_by` at all — so the card is appended here rather than faked
    # into LOOKUP_LISTS, where a handler that cannot answer `used_by` would have
    # to invent one.
    card = custom_field_card()
    cards.append(
        {
            "list": card["list"],
            "owner": card["owner"],
            "count": card["count"],
            # Not in LOOKUP_LISTS and so not in the report; its state is its own
            # count, on the report's own vocabulary rather than a new word.
            "state": "seeded" if card["count"] else "empty",
        }
    )
    return cards


def service_size_class_names() -> dict[str, str]:
    """`code` → the tenant's own NAME for it, for EVERY utility-service size
    class this tenant holds — `W-58` → `Water 5/8"`, `FL-2` → `Fire line 2"`.

    ⛔ **THIS EXISTS SO A LIST CAN PRINT A SIZE WITHOUT PRINTING A CODE.**
    `assets.selectors.asset_page_rows` is the caller: `Asset.size_class` is
    TEXT holding a `service_size_classes.code` (BR-AST-500), and a code is an
    internal reference that B14 rule 32 keeps out of clerk-facing copy. The
    portal settled the identical question one module along (`DEF-CWP-4848` —
    *"the size class as a person reads it, not the code"*), and this is the
    staff-side half of the same answer, read through the same vocabulary the
    tenant's own S8 card draws.

    ⚠ **IT IS NOT `service_size_class_index()` AND THE DIFFERENCE IS
    DELIBERATE, IN BOTH DIRECTIONS.** That one answers *does this tenant
    currently allow this size* and therefore folds case and skips INACTIVE
    rows, because it judges what a NEW row may name. This one answers *what is
    this size called* and therefore keeps the code's own spelling and includes
    the RETIRED rows — BR-AST-500 is explicit that *"a size Settings RETIRES
    must not vanish from a record that already priced it"*, so a meter still
    carrying `W-4` after Settings deactivated it must still print `Water 1"`.
    Filtering to `active` here would blank the column on exactly the rows a
    clerk is most likely to be auditing.

    ⚠ **A CODE WITH NO ROW IS ABSENT FROM THE MAP RATHER THAN MAPPED TO
    ITSELF.** Falling back to the code would put `W-58` on screen, which is the
    single thing this function exists to prevent; the caller draws its own
    absence instead. Empty is a lawful answer (BR-TEN-031, the list unwired on
    this deployment) and costs the column, never the row.

    ONE query for the whole page, read once by the caller (DEF-324).
    """
    from apps.tenancy import services  # late import: services imports selectors

    try:
        handler = services.lookup_handler("service_size_classes")
    except errors.NotFoundError:
        return {}
    return {str(row.code): str(row.name) for row in handler.search(None)}


def service_size_class_index() -> dict[str, str]:
    """`code` and `name`, both case-folded, → the code, for the tenant's ACTIVE
    utility-service size classes (`service_size_classes` — BR-TEN-170/171).

    ⛔ **THIS EXISTS SO THE METER IMPORT CAN JUDGE A SIZE CELL WITHOUT READING
    TENANCY'S TABLES** (B1/B2 §2 — a module may not query another's ORM).
    `apps.metering.seams.service_size_class_index` is the only caller, and the
    shape is deliberately `assets.selectors.import_lookup_index`'s, because the
    meters target already resolves `meter_type` and `read_method` through that
    exact shape and a fourth lookup that behaved differently would be a branch
    the runner does not have (BR-MET-096).

    ⚠ **IT READS THE TENANT'S OWN ROWS, NOT `apps.tenancy.service_size_classes`.**
    The module holds the forty RATIFIED codes; this table holds what THIS
    utility actually has — which is the ratified set minus anything Settings
    deactivated, plus (BR-TEN-071) anything a pre-2026-08-27 provisioning left
    behind. An import that judged against the ratified constant would refuse a
    code the tenant can see on its own S8 card, and accept one it deactivated.

    ⚠ **ACTIVE ROWS ONLY, AND THAT IS NOT THE SAME QUESTION AS BR-AST-500's.**
    The COLUMN keeps a retired size forever — *"a size Settings RETIRES must not
    vanish from a record that already priced it"* — so nothing here rewrites or
    clears a stored value. This is about what a NEW row may NAME, and naming a
    size the utility has retired is exactly the typo the ruling of 2026-08-28
    asked the import to catch.

    Read ONCE per run by the caller, for DEF-324's measured reason.
    """
    from apps.tenancy import services  # late import: services imports selectors

    try:
        handler = services.lookup_handler("service_size_classes")
    except errors.NotFoundError:
        # Skip-until-wired (BR-TEN-031): the list 404s on this deployment, so
        # the index is EMPTY and every named size flags as unknown. That is the
        # honest answer — the same posture `assets_lookup_index` documents —
        # and it is never a silently-accepted value.
        return {}
    index: dict[str, str] = {}
    for row in handler.search(None):
        if not getattr(row, "active", True):
            continue
        index[str(row.code).lower()] = str(row.code)
        index[str(row.name).lower()] = str(row.code)
    return index


def asset_upload_scopes() -> dict[str, dict[str, Any]]:
    """⛔ **WHICH SERVICE EACH ACTIVE SIZE CLASS AND EACH ACTIVE UNIT OF MEASURE
    BELONGS TO — the asset upload's plan-U4 checks (PO ruling 2026-09-30).**

    Three maps, ONE read of each table (DEF-324 — the caller reads this once per
    run, never per row):
      * ``size_service`` — size code → its service code, ``None`` when the row
        carries no tag (``CR-065``: *"nobody has said"*, offered everywhere).
      * ``uom_index``    — lowered UoM code and name → the code, so a file may
        say ``kWh`` or ``Kilowatt hour``.
      * ``uom_service``  — UoM code → its service code, ``None`` = all services.

    ⚠ **THE RULE IS `service_scope_filter`'s, RESTATED AS DATA, NOT RE-DECIDED:**
    a size or a unit is lawful for a row's service when it is scoped to that
    service or to none. Metering applies it through its seam; it may not read
    these tables (B1/B2 §2).
    """
    from apps.tenancy import models as tenancy_models

    tenant_id = _tenant_id()
    size_service: dict[str, Any] = {}
    for code, service_code in tenancy_models.MeterSizeClass.objects.filter(
        tenant_id=tenant_id, active=True
    ).values_list("code", "service__code"):
        size_service[str(code)] = service_code
    uom_index: dict[str, str] = {}
    uom_service: dict[str, Any] = {}
    for code, name, service_code in tenancy_models.Uom.objects.filter(
        tenant_id=tenant_id, active=True
    ).values_list("code", "name", "service__code"):
        uom_index[str(code).lower()] = str(code)
        if name:
            uom_index.setdefault(str(name).lower(), str(code))
        uom_service[str(code)] = service_code
    return {"size_service": size_service, "uom_index": uom_index, "uom_service": uom_service}


def lookup_page(
    list_code: str, q: str | None, service_code: str | None = None
) -> list[dict[str, Any]]:
    """Serialized rows for one list (IS-3 search: server-side, min 2 chars);
    api.py paginates. Unknown/unwired list → 404 via the framework.

    ⚠ **`service_code` IS `BR-SHL-011`'s `f.service_code` AND IT IS HONOURED
    ONLY BY A LIST THAT HAS A SCOPE (CR-065).** A handler carrying
    `ServiceScopeLookupMixin` publishes `scope_filter`; every other handler does
    not, and the filter is then IGNORED rather than refused.

    **Ignored and not refused, deliberately.** This is a picker feed, the same
    posture `uoms_for_service` takes for a service code it does not recognise:
    an unscoped list has no rows to exclude, so the honest answer to *"give me
    the payment methods for fire"* is every payment method, not an error. The
    WRITE is where a bad service is refused.
    """
    from apps.tenancy import services

    handler = services.lookup_handler(list_code)
    rows = handler.search(q)
    narrow = getattr(handler, "scope_filter", None)
    if service_code and narrow is not None:
        rows = narrow(rows, service_code)
    return [handler.serialize(row) for row in rows]


# ── S8 Numbering reads (US-TEN-012) ─────────────────────────────────────────
def number_series_overview() -> list[dict[str, Any]]:
    """Every series this tenant has, in the order r10's SET-08 table prints them
    — grouped, and inside a group in catalog order rather than alphabetically.

    THE ORDER IS PART OF THE SCREEN. CR-005 asks for *"Section kickers per group
    (CUSTOMERS & PREMISES, BILLING & PAYMENTS, WORK, ASSETS & READS)"*, and a
    table sorted by series key puts Account under Adjustment and Bill under
    Asset — which reads as an accident, because it is one. A series the catalog
    does not know (a row from an older build, or a hand-written one) still
    appears, last, rather than vanishing from the tab that governs it.
    """
    catalog_order = {series: index for index, series in enumerate(core_numbering.SERIES_CATALOG)}
    rows = [
        _series_dict(row)
        for row in models.NumberSeries.objects.filter(tenant_id=_tenant_id()).order_by("series")
    ]
    rows.sort(key=lambda row: catalog_order.get(row["series"], len(catalog_order)))
    return _flag_duplicate_prefixes(rows)


def number_series_row(series: str) -> dict[str, Any]:
    row = models.NumberSeries.objects.filter(tenant_id=_tenant_id(), series=series).first()
    if row is None:
        raise errors.NotFoundError()
    return _series_dict(row)


def _flag_duplicate_prefixes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """CR-005: *"duplicate prefixes across entities → warning (not blocking)"*.

    Computed HERE and not on the screen because it is a fact about the tenant's
    stored configuration, and the screen already has to compute the same thing
    live over UNSAVED edits — two answers to one question is how they drift. The
    server answers for what is saved; the client answers for what is being
    typed, from the same rule.

    An EMPTY prefix is never a duplicate: `{00000}` is the plain option CR-005
    makes mandatory in every category, so treating twenty-two prefix-free
    formats as twenty-two collisions would warn about the configuration the
    requirement asks for.
    """
    counts: dict[str, int] = {}
    for row in rows:
        prefix = row["prefix"]
        if prefix:
            counts[prefix] = counts.get(prefix, 0) + 1
    for row in rows:
        row["duplicate_prefix"] = counts.get(row["prefix"], 0) > 1
    return rows


def _series_dict(row: models.NumberSeries) -> dict[str, Any]:
    """Preview = what the NEXT number would look like today (tenant timezone) —
    validates + renders only, allocates nothing (BE-06 preview contract).

    `options` and `group` travel WITH the row rather than being a second
    endpoint the screen has to fetch and join: a dropdown that offers a format
    the server would refuse is the defect this shape makes impossible.
    """
    try:
        preview = core_numbering.preview(row.format, row.next_number, tenant_today())
    except Exception:  # malformed stored format must not break the tab read
        preview = None
    group, options = core_numbering.SERIES_CATALOG.get(row.series, ("", ()))
    return {
        "series": row.series,
        "group": group,
        "format": row.format,
        "next_number": row.next_number,
        "restart_period": row.restart_period,
        "preview": preview,
        # The ready-made list ALWAYS contains what this tenant currently has,
        # even when an admin typed something custom — a picker that silently
        # drops the current value reads as "your format was reset".
        "options": list(options) + ([row.format] if row.format not in options else []),
        "prefix": core_numbering.literal_prefix(row.format),
        # CR-005 edge case: *"counter overflow (counter exceeds pad length) →
        # keep issuing, widen number, surface a warning banner"*. The banner is
        # the screen's; the JUDGEMENT is the server's, so both halves cannot
        # disagree about when a number got wider.
        "overflow": core_numbering.will_overflow(row.format, row.next_number),
    }


# ── BE-07 job poll read (GET /jobs/{id} — 11b §2.17) ────────────────────────
# The record contract the poll serves, and nothing else: payload, scope_key and
# checkpoint are the RUNNER's business (they can carry filter state and internal
# markers), so they never leave the server on this resource.
JOB_POLL_FIELDS = ("id", "kind", "status", "progress", "result_link", "error")


def job_poll(job_id: Any) -> dict[str, Any] | None:
    """One job of THIS tenant, or None.

    Tenant-scoped like every other read here (BR-TEN-003 + RLS on Postgres):
    another tenant's job id is ABSENT under this scope, so the endpoint answers
    a plain 404 — never 403, which would confirm the id exists (HR-1 / 11b G4).
    A malformed id is absent for the same reason.
    """
    target = _uuid_or_none(job_id)
    if target is None:
        return None
    job = models.Job.objects.filter(tenant_id=_tenant_id(), id=target).first()
    if job is None:
        return None
    payload = {
        "id": str(job.id),
        "kind": job.kind,
        "status": job.status,  # core.jobs.STATUSES
        "progress": job.progress or models.job_progress_default(),
        # ⚠ DEF-3280 — THE JOB HAS WRITTEN THIS SINCE 2026-08-19 AND NOTHING
        # COULD READ IT. `run_provisioning_plant` calls `jobs.record_progress(…,
        # checkpoint=label)` after every block, so the record has always known
        # WHICH step a tenant was on; this dict served six keys and not that
        # one, so `GET /api/jobs/{id}` could say "11 of 17" and never "Meter
        # reads". Hard-won law 2 — built is not wired — on a field that costs
        # one line to serve. Any job kind may set it (TD-17 also uses it as a
        # resume marker) and any job kind now serves it: a poll that answered
        # differently per kind would be a second contract.
        "checkpoint": job.checkpoint,
        "result_link": job.result_link,
        "error": job.error,
    }
    # ── CR-064 tasks A1 · A3 · A4 (PO 2026-09-02) ───────────────────────────
    # *"list down all 17 steps and show 1 by 1 when they finish - if step
    #  breaks - then show the reason behind it at that step itself"*.
    #
    # ⚠ IT RIDES ON THE POLL THE SCREEN IS ALREADY MAKING, AND THAT IS THE
    # DESIGN DECISION. The sign-up screen polls this record every 1.5 s and has
    # no other authenticated read of its own; a second endpoint would be a
    # second round trip, a second thing to keep in step with the first, and a
    # second place for the two to disagree about which block was last.
    #
    # ⚠ ONLY FOR THE PLANT KIND. An export job has no blocks and twenty-eight
    # `not_started` steps on it would be a lie about a job that never had any.
    # The key is ABSENT rather than empty for every other kind, which is the
    # DEF-127 posture this module keeps everywhere: a list nothing wrote is not
    # an empty list.
    if job.kind == sample_data.PLANT_JOB_KIND:
        payload["steps"] = sample_data.step_states()
    return payload


def job_artifact(job_id: Any) -> dict[str, Any] | None:
    """The DOWNLOAD-relevant facts of one job of THIS tenant, or None.

    Separate from job_poll() because it serves a different consumer: job_poll
    answers the client (and therefore withholds the payload), while this read
    answers GET /exports/{job_id}/file inside the server and needs the one
    payload key the runner wrote — the artifact's path on disk.

    Tenant-scoped exactly like job_poll (BR-TEN-003 + RLS on Postgres): another
    tenant's job id is ABSENT under this scope, and the endpoint renders that
    absence as the same plain 404 as every other refusal (HR-1 / 11b G4).
    Nothing here decides whether the file may be served — that is
    exports.resolve_artifact's law; this is a read.
    """
    target = _uuid_or_none(job_id)
    if target is None:
        return None
    job = models.Job.objects.filter(tenant_id=_tenant_id(), id=target).first()
    if job is None:
        return None
    # No path and no key: `exports.resolve_artifact` finds the file through the
    # job's `job_artifacts` row (PO 2026-10-02, exports in S3).
    return {"id": str(job.id), "kind": job.kind, "status": job.status}


#: `GET /reports/history`'s page size and its ceiling (`NFR-3`). The default is
#: the kit's own 50 — the number `DataTable` pages with everywhere else — and
#: the ceiling exists so one request cannot ask for a tenant's whole run
#: history. ⚠ **IT IS NOT AN ACCOUNT CAP AND `NFR-5` IS UNTOUCHED**: every row
#: is reachable, one page at a time, which is what `NFR-3` asks for.
REPORT_RUN_PAGE_DEFAULT = 50
REPORT_RUN_PAGE_MAX = 200


def report_runs(
    *,
    resources: Sequence[str],
    kinds: Sequence[str],
    q: str = "",
    resource: str | None = None,
    status: str | None = None,
    fresh_since: Any = None,
    page: int = 1,
    per: int = REPORT_RUN_PAGE_DEFAULT,
) -> dict[str, Any]:
    """THIS tenant's report runs, newest first, ONE PAGE — `CR-142-BRC07` `P3.1`.

    ⚠ **THERE IS NO `report_runs` TABLE AND THERE MUST NOT BE ONE.** The
    brief's own words: *"No new table — the job record is the run record, and
    the module already says so"*. `apps/reports/exports.py` has said so in
    prose since 2026-08-16 (*"A stored run row … the JOB record is the run
    record"*, at line 60 of that file — checked, not cited); this read is that
    sentence becoming code.

    ⚠ **THE FILTER IS A PAIR AND BOTH HALVES ARE THE CALLER'S.** `kinds` is the
    job KIND allow-list and `resources` is the set of `payload.resource` values
    the reports module owns. Neither is compiled in here, because `jobs` is a
    PLATFORM table this module happens to host: a list of report names living
    in tenancy would be reports' vocabulary in somebody else's file, and it
    would go stale the first time a report was added.

    ⚠ **PAGED IN SQL, SORTED IN SQL** — `NFR-3`, and `DEF-PAY-4221` is what the
    other shape costs. `-created_at` is the drawing's *newest first*; `-id` is
    the tie-break, and it is not decoration: `uuid7_pk` is time-ordered, so two
    runs sharing a timestamp still come back in a stable order and page two
    cannot repeat a row page one already showed.

    Tenant-scoped by an explicit filter on top of RLS FORCE, exactly like
    `job_poll` beside it (CLAUDE.md rule 1 / BR-TEN-003).
    """
    wanted = tuple(str(name) for name in resources)
    size = _report_run_per(per)
    if not wanted:
        # A caller that owns no export resources has no runs — an empty page,
        # never every job on the platform. Fail CLOSED (hard-won law 3).
        return {"rows": [], "total": 0, "page": 1, "per": size, "pages": 0}
    rows = models.Job.objects.filter(
        tenant_id=_tenant_id(), kind__in=tuple(kinds), payload__resource__in=wanted
    )
    if resource is not None and resource in wanted:
        rows = rows.filter(payload__resource=resource)
    if status is not None:
        # ⚠ **`ready` AND `expired` ARE ONE STORED STATUS, AND THE CUTOFF IS
        # WHAT SEPARATES THEM — IN SQL, NOT AFTER THE PAGE IS CUT.** Both are
        # `succeeded`; the difference is whether the run is younger than the
        # retention window. Splitting them in Python after `[offset:offset+n]`
        # would give a page of fifty rows with nine on it and a pager counting
        # the other forty-one — a filter that reads as working and is not
        # (hard-won law 7, *looking at the wrong thing*).
        #
        # ⚠ **AND `fresh_since` IS THE CALLER'S, FOR THE SAME REASON `kinds`
        # IS.** The retention window is `BR-REP-018`'s and reports owns it; a
        # `days=3` in this file would be that rule's second home.
        if status in ("ready", "expired") and fresh_since is not None:
            rows = rows.filter(status="succeeded")
            rows = (
                rows.filter(created_at__gte=fresh_since)
                if status == "ready"
                else rows.filter(created_at__lt=fresh_since)
            )
        else:
            rows = rows.filter(status=status)
    text = (q or "").strip()
    if text != "":
        # ⚠ **WHAT THE SERVER CAN MATCH, AND IT IS NOT THE REPORT'S NAME.** The
        # displayed name is a catalogue string the CLIENT translates
        # (`reports.card.<key>.name`) and no column holds it, so a server-side
        # search over it is impossible without duplicating eleven catalogues
        # into SQL. It matches the report KEY and the stored parameters, which
        # is what the row actually holds. Stated here rather than implied: a
        # search box quietly matching less than a user assumes is a check that
        # cannot fail, one control along.
        rows = rows.filter(
            Q(payload__resource__icontains=text) | Q(payload__filters__icontains=text)
        )
    total = rows.count()
    pages = (total + size - 1) // size if total else 0
    wanted_page = max(1, int(page or 1))
    if pages:
        wanted_page = min(wanted_page, pages)
    offset = (wanted_page - 1) * size
    window = list(rows.order_by("-created_at", "-id")[offset : offset + size])
    return {
        "rows": _with_artifact_statuses([_report_run_row(job) for job in window]),
        "total": total,
        "page": wanted_page,
        "per": size,
        "pages": pages,
    }


def _report_run_per(per: Any) -> int:
    try:
        size = int(per)
    except (TypeError, ValueError):
        return REPORT_RUN_PAGE_DEFAULT
    return max(1, min(size, REPORT_RUN_PAGE_MAX))


def report_run(
    job_id: Any, *, resources: Sequence[str], kinds: Sequence[str]
) -> dict[str, Any] | None:
    """ONE report run of this tenant, or None — the record behind screen `5·2`.

    A job that exists but is not a REPORT run is absent here, and the endpoint
    renders that absence as the same plain 404 every other refusal gets (HR-1 /
    11b G4): a distinguishable message would confirm the id.
    """
    target = _uuid_or_none(job_id)
    if target is None:
        return None
    job = models.Job.objects.filter(
        tenant_id=_tenant_id(),
        id=target,
        kind__in=tuple(kinds),
        payload__resource__in=tuple(str(name) for name in resources),
    ).first()
    return None if job is None else _with_artifact_statuses([_report_run_row(job)])[0]


def _with_artifact_statuses(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stamp each run row with its export file's state — ONE query for the page.

    `pending` / `stored` / `deleted`, or None when the run left no file (it
    failed, it ran before exports moved to S3 on 2026-10-02, or it is still
    running). `apps/reports/run_history.py` reads it to decide *ready* vs
    *expired*; the bucket is never asked (PO 2026-10-02).
    """
    from apps.tenancy import export_store

    statuses = export_store.statuses_for_jobs([row["id"] for row in rows])
    for row in rows:
        row["artifact_status"] = statuses.get(row["id"])
    return rows


def _report_run_row(job: Any) -> dict[str, Any]:
    """One `jobs` row as a RUN — the fields `5·1` draws and nothing else.

    ⚠ **`jobs` HAS NO ACTOR COLUMN, NO PARAMETERS COLUMN AND NO ROW-COUNT
    COLUMN — MEASURED ON THE RUNNING PRODUCT, NOT ASSUMED.** The twelve are
    `id · tenant · kind · status · progress · checkpoint · result_link ·
    error · scope_key · payload · created_at · updated_at`, and `job_status`'s
    own docstring already reports the actor gap. So three of the drawing's
    seven columns come out of `payload`: who from `actor_user_id` (which
    `request_list_export` writes), the parameters from `filters`, and the row
    count from `progress.done`. Nothing is invented and no column is added.

    ⚠ **`started_by_id` IS AN ID AND IT NEVER REACHES A SCREEN.** B14 rule 31
    puts no database id on screen; `apps/reports/run_history.py` turns it into
    a NAME and drops the id before the response is built.

    ⚠ **THE NAME IS NOT RESOLVED HERE, AND THE REASON IS A DEFECT THIS LANE
    ALMOST SHIPPED.** The first draft called `seams.resolve("identity",
    "user_in_tenant")` from this file. **That resolver imports
    `apps.<module>.services` and NOTHING ELSE**, `user_in_tenant` lives in
    identity's SELECTORS, and so it returned `None` on every row — silently,
    with no error anywhere — and every run Dana Whitfield had started would
    have been drawn as *Schedule*. It is DEF-035's shape exactly, which
    `apps/reports/report_seams.py` records in its own `resolve` docstring:
    *"a seam pointing at the wrong FILE (`services` instead of `selectors`)
    returned None on every call for weeks"*. Nothing caught it; RUNNING the
    endpoint and reading a column that should have said a name did.

    ⚠ **NO STORAGE KEY OR PATH IS IN THIS ROW.** `artifact_status` is the
    export file's state from its `job_artifacts` row and nothing else; a key
    on a clerk's screen would be G28's leak and rule 31's id at once.
    """
    payload = job.payload or {}
    actor_id = payload.get("actor_user_id")
    return {
        "id": str(job.id),
        "resource": payload.get("resource"),
        "status": job.status,
        "progress": job.progress or models.job_progress_default(),
        "error": job.error,
        "ran_at": job.created_at.isoformat() if job.created_at else None,
        "started_by_id": str(actor_id) if actor_id not in (None, "") else None,
        "filters": payload.get("filters") or {},
        "columns": payload.get("columns") or [],
        # The export file's state, from its `job_artifacts` row — filled in for
        # a whole page in ONE query by the caller (`_with_artifact_statuses`).
        "artifact_status": None,
    }


def _uuid_or_none(value: Any) -> UUID | None:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None


# ── service GL attributes (BR-BIL-010; PO ruling 2026-08-11, OQ-106) ────────
def service_gl_attributes(service_code: str) -> dict[str, str | None] | None:
    """The GL half of a tenant's service row — PUBLISHED FOR THE LEDGER.

    The PO closed OQ-106 with *"using attributes on accounts and Utility
    services - we can derive how it sum up at Ledger."* This is the read that
    makes the second half of that sentence possible without the ledger touching
    `tenant_services` (B1 / BR-TEN-013): `apps/ledger/tenancy_seam.py` resolves
    this callable by name, and `apps/ledger/selectors.py` derives the roll-up.

    `None` means the tenant has NO row for that service — it is not enabled
    here. A row with nothing mapped comes back as a dict of Nones, which is a
    different fact (enabled, unmapped, a visible gap on the GL mapping page)
    and is kept different on purpose. Tenant scoping is the same explicit
    filter every read in this module uses (CLAUDE.md rule 1).

    `enabled` travels with the accounts because a DISABLED service still bills
    nothing new but its historical lines still have to roll up — the caller
    decides what that means; this read does not decide for it.
    """
    row = (
        models.TenantService.objects.filter(tenant_id=_tenant_id(), service__code=service_code)
        .only("enabled", "revenue_account_id", "base_revenue_account_id")
        .first()
    )
    if row is None:
        return None
    return {
        "service": service_code,
        "enabled": bool(row.enabled),
        "revenue_account_id": (str(row.revenue_account_id) if row.revenue_account_id else None),
        "base_revenue_account_id": (
            str(row.base_revenue_account_id) if row.base_revenue_account_id else None
        ),
    }


def enabled_service_codes() -> tuple[str, ...]:
    """The services this tenant actually SELLS — PUBLISHED FOR THE LEDGER.

    ⚠ AMENDED 2026-08-18: this read no longer decides which accounts the chart
    seed creates. Under OQ-115's narrowing (2026-08-11) the seed asked it to
    pick per-service revenue rows; CR-010 B-9 (PO 2026-08-17, *"9 - A full ~40
    accounts for every tenant, as you said"*) made the seed unconditional, so
    the ledger now reads this only to REPORT which services were enabled at
    seed time (`services_seeded` in the seed summary) and on the S56 GL-mapping
    services section. Since New mandate 4 every catalog service has a
    `tenant_services` row at provisioning; this answers the ENABLED subset.

    ENABLED ONLY, still deliberate: a present-but-off row (mandate 4) and a
    switched-off service both stay out, because "what does this tenant sell"
    is the question every caller is asking. Order is the catalog's own, so the
    answer reads in the same order the S8 screen lists.

    ⚠ AMENDED 2026-08-19 (DEF-324): `service__active=True` joined the filter so
    this and `services_overview()` cannot disagree. `services_overview` has
    always walked ACTIVE catalog rows only (BR-TEN-025's closed set), and
    `apps.metering.seams.enabled_service_codes` derived its answer from that
    payload — 155 ms and ~150 queries per call — while this cheap read was
    published one file away and did not carry the active filter. Pointing the
    seam here (which is what DEF-324 does) would have been a semantic change
    without this line; with it, the two reads are the same question asked once.
    It is a NO-OP against today's data — all ten catalog rows are active and
    nothing in the product deactivates one — which is exactly why it is safe to
    make the definitions agree now rather than after one diverges.
    """
    return tuple(
        models.TenantService.objects.filter(
            tenant_id=_tenant_id(), enabled=True, service__active=True
        )
        .order_by("service__sort", "service__code")
        .values_list("service__code", flat=True)
    )


def service_default_uom(service_code: str) -> str | None:
    """The tenant's own primary UoM for **ONE** service — in ONE query.

    ⛔ **DEF-1549 — THE SINGULAR LOOKUP USED TO COST A WHOLE SCREEN, AND THAT
    IS WHAT KILLED THE PRODUCT OWNER'S IMPORT A SECOND TIME.** Until this
    existed, `apps.metering.seams.service_default_uom` answered the question by
    walking `service_catalog()` → `services_overview()` — the **S8 SCREEN
    read** — and picking one field out of it:

        for row in service_catalog():
            if row["service"] == service_code:
                return row.get("primary_uom")

    `services_overview()` builds `service_row(code)` for **every active catalog
    service**, and each of those makes four `select_related` joins plus two
    counting seams — one of which, `customers.active_account_count`, issued a
    query **per service point** on the tenant. `assets._create_asset_inner`
    calls this **once per asset row**, so a twenty-row meter import paid

        20 rows × ~10 services × (the row's joins + 2 queries per service point)

    — multiplicative, invisible at 0.2 ms in this harness, and a `[CRITICAL]
    WORKER TIMEOUT` at 15–20 ms against a real database. `DEF-1075` had just
    removed the FIRST N+1 on that same path and uncovered this larger one
    behind it.

    ⚠ **THIS IS THE SAME MISTAKE `DEF-324` ALREADY DIAGNOSED ONCE**, one
    function along: see `apps.metering.seams.enabled_service_codes`, whose
    docstring records a provisioning request spending 47 of 118 seconds
    answering a one-column question with a screen payload. The cure built then
    — `service_default_uoms()` below — was never reached by this call site
    because it answers the **plural** question and no singular equivalent was
    published. This is that missing equivalent.

    ⚠ **THE ANSWER IS BYTE-FOR-BYTE THE ONE `service_row` GIVES, DELIBERATELY —
    INCLUDING FOR A PRESENT-BUT-OFF SERVICE.** This is NOT
    `service_default_uoms().get(code)`: the plural filters `enabled=True`, and
    a tenant with a `tenant_services` row switched off (New mandate 4) still
    has a stored unit that `service_row` reports and that metering's existing
    readers rely on. Narrowing that here would turn a performance fix into a
    silent `unit_missing` refusal on every meter of a disabled service — a
    regression wearing a speed-up's clothes. So the filter is
    `service__active=True` and nothing else, exactly as `services_overview()`
    walks the active catalog.

    **`None` IS A REAL ANSWER AND MUST STAY ONE** — an unknown code, a service
    with no `tenant_services` row, and a row whose `primary_uom` is NULL all
    answer `None`, which is what the walk above returned for each of them.
    CLAUDE.md hard rule 3 means the caller REPORTS that; there is no fallback
    unit here and there must not be one (see `service_default_uoms` below).
    """
    return (
        models.TenantService.objects.filter(
            tenant_id=_tenant_id(), service__code=service_code, service__active=True
        )
        .values_list("primary_uom__code", flat=True)
        .first()
    ) or None


def service_default_uoms() -> dict[str, str | None]:
    """`{service_code: the tenant's own primary UoM}` for every ENABLED service.

    ONE query with one join — published for CR-039 wave A, which needs to know
    what unit each service is measured in BEFORE it creates a meter in it.

    ⚠ **THE TENANT'S STORED UNIT, NOT THE MODULE CONSTANT.** `SERVICE_DEFAULT_
    UOMS` in `apps/tenancy/services.py` is what `_default_uoms_for` STAMPS on a
    `tenant_services` row when a service is switched on; the row is what the
    tenant actually holds, and a tenant is entitled to change it. Reading the
    constant would hand a fixture a unit the tenant does not use, which is
    CLAUDE.md rule 3's failure in a subtler form.

    **`None` IS A REAL ANSWER AND MUST STAY ONE.** Four of the ten catalog
    services — sewer, solar, thermal/heat, battery — have no design-stated
    default, so a tenant that enables one carries a NULL. The caller REPORTS
    that by name; it must never fall back to a unit of its own choosing (the
    rule has no "assume kWh" branch, and metering's validation errors
    `unit_missing` on exactly that meter).

    Why here rather than through `services_overview()`: that is the S8 SCREEN
    read — ten rows, four `select_related` joins each and two counting seams per
    row, ~150 queries (DEF-324). Asking it "what unit is water in" costs the
    whole screen.
    """
    return {
        str(code): (unit or None)
        for code, unit in models.TenantService.objects.filter(
            tenant_id=_tenant_id(), enabled=True, service__active=True
        )
        .select_related("primary_uom")
        .values_list("service__code", "primary_uom__code")
    }


def service_billed_uoms() -> dict[str, dict[str, Any]]:
    """`{service_code: {"billed_uom", "conversion_factor"}}` for every ENABLED
    service — B2 r6.4's register→billed gate as the TENANT holds it.

    Published for BR-MET-143 (PO 2026-08-27): the sample plant has to know what
    unit a service is BILLED in before it can decide what multiplier the meter
    it plants needs, and `service_default_uoms` above answers only what the
    REGISTER reads. One query with one join, for the DEF-324 reason that one
    states: asking `services_overview()` costs the whole S8 screen.

    **`None` on both keys is the ordinary answer and must stay one.** `r6.4`
    made `billed_uom` and `conversion_factor` a per-service OPTION and nothing
    seeds them, so a fresh tenant carries NULLs — which means "the register's
    own unit is what is billed" and NOT "unconfigured, refuse". The caller
    reads it that way (`sample_fixture._resolve_multiplier`), and the OQ-004
    closure's *"no silent conversion"* applies to the case where the two units
    DIFFER and no factor is on file.
    """
    return {
        str(code): {"billed_uom": billed or None, "conversion_factor": factor}
        for code, billed, factor in models.TenantService.objects.filter(
            tenant_id=_tenant_id(), enabled=True, service__active=True
        )
        .select_related("billed_uom")
        .values_list("service__code", "billed_uom__code", "conversion_factor")
    }


@batch_reads.memoised
def unmetered_service_codes() -> tuple[str, ...]:
    """The services this tenant sells that are NOT MEASURED BY DESIGN — BR-RAT-081.

    **THE FIRST READER `tenant_services.metered` HAS EVER HAD (DEF-495 closed,
    DEF-161 fixed).** The column shipped 2026-08-20 with BR-RAT-081 — PO
    verbatim, *"yes we have to say service is meter or unmetered"* — and until
    this function existed `grep` across `apps/` found the migration, the model
    and two comments and not one query. A declaration nothing reads is a
    declaration that cannot reach a bill, which is exactly what DEF-161 was:
    the run went on treating a trash service point with no cart meter as a
    MISSING READ and refused the whole account.

    ⚠ **THE ANSWER IS THE COMPLEMENT OF THE DEFAULT, AND THAT IS DELIBERATE.**
    `metered` defaults to **True**, so this returns the services a tenant has
    explicitly declared unmetered and nothing else. A tenant that has never
    touched the setting gets an EMPTY tuple, every service stays measured, and
    every bill in the product prices exactly as it did before this read existed
    — which is what makes DEF-161's fix safe to land under ❄️ frozen B4/B5.

    ⚠ **AND IT IS A NARROW SET ON PURPOSE — see `metering.selectors
    .billing_reads_for_unit`.** Being on this list means *no read is ever owed
    for this service*. Being off it means a service point with no meter is a
    CONFIGURATION PROBLEM a human must see (`no_meter`), not a bill that
    quietly charges base only. DEF-161's ruling names that distinction as the
    whole deliverable: *"a meter that exists and was not read keeps refusing
    exactly as it does now"*.

    ENABLED + ACTIVE only, the same filter `enabled_service_codes()` carries
    and for DEF-324's reason: the two reads must answer the same question about
    the same rows or they will disagree the day one of them is amended.

    ── **WHICH OF THE THREE BASES THIS FILTER ASKS FOR (`BR-TEN-1180`,
    2026-09-02)** ────────────────────────────────────────────────────────────
    The column this read was written against was a BOOLEAN and this filter said
    `metered=False`. The vocabulary is now three values, so the filter had to
    choose, and the choice is **`capacity` ALONE — not `NOT metered`.**

    **The reason is the sentence three paragraphs up: being on this list means
    NO READ IS EVER OWED for this service.** That is a statement about how the
    quantity is obtained, and `BR-RAT-090` answers it in exactly one way — a
    COUNT OF THE UNIT'S ASSETS. `capacity` is the basis that means that: carts,
    ERUs, panels, Mbps, kW. Three carts × `$15.00` = `$45.00`; take one away and
    the next bill is `$30.00`.

    **`share` is deliberately NOT here, and `DEF-2409` is the reason the
    distinction had to be made at all.** Sewer reads no register either, so on
    the old boolean it was the case that fitted NEITHER value — it is a
    PERCENTAGE of the water usage charge (`BR-RAT-015`), and a sewer connection
    has no assets, so routing it through the asset count would price it at 0.
    `core.sample_fixture` already recorded this in prose — *"Trash is priced by
    counting things and sewer is priced by a percentage of other money; only the
    first is what this declaration means"* — and `sewer` is deliberately absent
    from `UNMETERED_ESTATE_SERVICES` for it. **The widened column is what lets
    that sentence be a QUERY instead of a comment**, and returning `share` here
    would re-introduce the exact mispricing the ruling was made to prevent.

    **So the filter narrows rather than negating**, and it is the narrower of
    the two readings on purpose: a service wrongly ON this list bills a count of
    assets it does not have, while a service wrongly OFF it is refused with
    `no_meter` — a configuration problem a human SEES (`DEF-161`'s ruling names
    that distinction as the whole deliverable). Wrong-and-visible beats
    wrong-and-billed.
    """
    return tuple(
        models.TenantService.objects.filter(
            tenant_id=_tenant_id(),
            enabled=True,
            service__active=True,
            billing_basis=models.BILLING_BASIS_CAPACITY,
        )
        .order_by("service__sort", "service__code")
        .values_list("service__code", flat=True)
    )


def metered_service_codes() -> tuple[str, ...]:
    """WHICH of this tenant's enabled services are billed on a METERED basis —
    the ones a meter can actually serve (BR-RAT-081, BR-TEN-1180).

    `DEF-MET-9056`: *has a unit* was used as a stand-in for this, and `CR-081`
    gave SEWER a unit (90% of the water volume) while sewer still has no meter.
    `share` and `capacity` are the two bases a meter never serves.
    """
    return tuple(
        models.TenantService.objects.filter(
            tenant_id=_tenant_id(),
            enabled=True,
            service__active=True,
            billing_basis=models.BILLING_BASIS_METERED,
        )
        .order_by("service__sort", "service__code")
        .values_list("service__code", flat=True)
    )


def service_ids_by_code() -> dict[str, str]:
    """`{code: id}` for every ACTIVE catalog service — PUBLISHED FOR BILLING.

    `invoice_lines.service_id → tenancy.services` is a reviewed cross-module FK
    (B2 §2 / DB-16) and billing must fill it: BR-BIL-010 keys the service →
    revenue-account map on the service, so a line that cannot name its service
    cannot be stamped and the whole bill refuses at issue. Billing holds the
    CODE (it is what rating priced against) and needs the ID, and B1 forbids it
    reaching into this module's ORM for the translation — so the translation is
    published here, once, and `apps/billing/tenancy_seam.py` resolves it.

    THE WHOLE CATALOG, NOT THE TENANT'S ENABLED SUBSET, and that is deliberate.
    `services` is the closed PLATFORM catalog (BR-TEN-025) and is RLS-EXEMPT —
    ids are not tenant secrets. A tenant that disables a service mid-cycle still
    has to be able to issue the bills already priced for it; filtering on
    `enabled` here would make those lines unstampable for a reason nobody could
    see on the bill. `active=False` IS excluded: a service the platform has
    retired is not one a new line may point at.

    A dict rather than one lookup per code because the caller is stage 6 of the
    bill run, writing every line of a bill in one pass — a query per line would
    be a round trip per line for a fact that changes about once a year.
    """
    return {
        code: str(pk)
        for pk, code in models.Service.objects.filter(active=True).values_list("id", "code")
    }


def bill_masthead() -> dict[str, str | None]:
    """WHO SENT THIS BILL — three strings, PUBLISHED FOR BILLING (`DEF-2865`).

    A19 §1.1 mastheads a bill with the utility's name, its address and how to
    reach it. `documents._masthead` has asked `bill_payload` for exactly these
    three keys since it was written and found none of them, so **every bill this
    product has issued printed an em-dash where the utility's name belongs** —
    on the PO's own BL-2608-000048, which is where it was noticed. BR-BIL-030
    lists *"tenant identity and branding reference"* among what the locked
    instance carries; nothing carried it.

    **A PURPOSE-BUILT READ RATHER THAN `company_profile()` ABOVE, and the reason
    is that they answer different questions.** `company_profile` serves the S8
    company tab — fifteen keys including the EIN, the logo bytes' reference and
    the brand colours — and a bill needs three strings. Billing asking for the
    tab's payload would make every future column on that tab a column billing
    receives, and it would put the EIN one dictionary lookup away from a
    document. This states what a bill may know.

    **THE NAME IS THE DBA FIRST.** US-TEN-005 §5 already makes the DBA the
    display name for remittance; a customer knows the utility by the name on the
    truck, not by the district's legal name. The legal name is the fallback and
    the tenant's provisioning name is the last one — never the subdomain, which
    is a routing fact and not a name anybody chose.

    **EVERY VALUE MAY BE `None`, AND `None` IS THE HONEST ANSWER.** A tenant that
    has not filled in its company profile has not filled it in; `documents._field`
    turns that into a named absence citing BR-BIL-030, which is what makes the
    S62 checklist item actionable. Nothing here composes an address out of
    fragments or invents a name.

    ⚠ **THE ADDRESS HAS A FALLBACK CHAIN SINCE 2026-09-30 (`DEF-BIL-8283`).**
    The PO's one-time bill BL-2609-000081 printed *"This bill did not record
    it"* under *Who sent it* while the utility HAD written where it can be
    found — just not in the company tab's mailing-address box. So the address
    is, in order: the company **mailing address** · the **remit-to address**
    (the tenant's own words for where a payment is posted, which is an address
    the utility chose to print) · the address of the first **service centre it
    shows to customers** (`service_centres`, the utility's own counter — one of
    hard rule 8's named exceptions; a hidden depot is never printed). The
    contact falls back to that centre's phone the same way. Each is an address
    the tenant typed for the public; none is composed from fragments.
    """
    tenant = _tenant_row()

    def text(value: Any) -> str | None:
        return str(value).strip() or None if isinstance(value, str) and value.strip() else None

    contact = " · ".join(
        part for part in (text(tenant.support_phone), text(tenant.support_email)) if part
    )
    address = text(tenant.mailing_address) or text(tenant.remit_to_address)
    if address is None or not contact:
        from apps.tenancy import published_content_models as content

        centre = (
            content.ServiceCentre.objects.filter(tenant_id=tenant.id, is_shown_to_customers=True)
            .order_by("position", "created_at")
            .values("address", "phone")
            .first()
        ) or {}
        address = address or text(centre.get("address"))
        contact = contact or (text(centre.get("phone")) or "")
    return {
        "utility_name": text(tenant.dba_name) or text(tenant.legal_name) or text(tenant.name),
        "utility_address": address,
        "utility_contact": contact or None,
    }


def service_names_by_code() -> dict[str, str]:
    """`{code: name}` for every ACTIVE catalog service — PUBLISHED FOR BILLING.

    The twin of `service_ids_by_code` above and published for the same reason:
    billing holds the CODE, needs the word a customer reads, and B1 forbids it
    reaching into this module's ORM for the translation.

    ⚠ **DEF-2852 — THE BILL PRINTED `Service 01a046d3-090d-7eca-…` WHERE THE
    CUSTOMER SHOULD HAVE READ `Water`.** `invoice_lines.service_id` names the
    service (that is what `service_ids_by_code` is for) and nothing anywhere
    could turn that id back into a word, so the document printed the id — on
    the most public surface the product has, against B14 rule 31 (PO
    2026-08-30: *"no Databse ID on screen - that is a rule"*).

    **THE NAME IS READ ONCE, AT DRAFT TIME, AND FROZEN INTO THE BILL'S OWN
    SNAPSHOT.** BR-BIL-030 forbids the document joining this table while it
    renders — a service renamed next year must not re-title a bill already
    sent — so this read belongs to stage 6 and never to the renderer.

    THE WHOLE CATALOG AND NOT THE TENANT'S SUBSET, `active=True` only, for the
    reasons `service_ids_by_code` states at length: `services` is the closed
    PLATFORM catalog (BR-TEN-025) and is RLS-exempt.
    """
    return {
        code: name
        for code, name in models.Service.objects.filter(active=True).values_list("code", "name")
    }


# ── custom-field registry (B2 r17.1; EP-TEN-09; OQ-076 closure) ─────────────
def document_safe_custom_fields(entity: str) -> list[dict[str, Any]]:
    """The definitions a DOCUMENT may stamp for one entity — PUBLISHED FOR BILLING.

    Resolved by name from `apps/billing/custom_snapshot.py`, the single module
    DB-17 allows to touch tenant-defined data inside a money path. Billing never
    imports `apps.tenancy.models` (B1 / G6 module boundary); it asks, and this
    answers.

    THREE FILTERS, AND EVERY ONE OF THEM IS A RULE:

    * `tenant_id` — CLAUDE.md rule 1. RLS FORCE is the database's half; this
      explicit filter is the application's, and both are required.
    * `is_active` — BR-TEN-050 / US-BIL-028 TC-6: a deactivated field is
      excluded from NEW snapshots while already-issued invoices keep theirs.
    * `is_document_safe` — OQ-076, PO 2026-08-10 (*"Dont put SSN on invoices"*),
      mechanism confirmed INVERTED the same day. A field is NOT stamped onto a
      document unless the tenant explicitly marked it safe. Fail-closed, so the
      failure mode of a tenant who never touches the flag is an empty snapshot
      rather than a Social Security number frozen into an append-only table that
      BR-TEN-044's day-91 deletion cannot reach.

    Ordered by `display_order` then `id` — IS-2's stable secondary — so a
    reprint iterates the registry in the same order every time.
    """
    return [
        {"key": row.key, "data_type": row.data_type, "label": row.label}
        for row in models.CustomField.objects.filter(
            tenant_id=_tenant_id(),
            entity=entity,
            is_active=True,
            is_document_safe=True,
        ).order_by("display_order", "id")
    ]


# ── the custom-field registry every placed screen reads (US-TEN-017) ────────
#
# BR-TEN-053, and the whole reason it is a rule rather than an optimisation:
# this read happens on nearly every screen and is written about once a quarter.
# The cache key is `cf:v{version}:{tenant_id}:{entity}` — **tenant identity is
# part of the key, always**. Redis has no RLS: it hands over any key it is
# asked for, with none of the database's guardrails in the way, so a key that
# omitted `tenant_id` would be a silent cross-tenant leak that no isolation
# probe on Postgres could ever see. `tests/isolation/` asserts it against the
# cache directly for exactly that reason.
#
# INVALIDATION IS BY VERSION, NOT BY DELETE. `tenant_settings.custom_field_
# version` is bumped in the SAME TRANSACTION as any definition write
# (services._bump_custom_field_version), so the next read computes a new key
# and the old one simply ages out. There is no delete fan-out to get wrong and
# no window where a write has landed and a stale key is still authoritative.
def _custom_field_cache() -> Any:
    from django.core.cache import cache

    return cache


def _custom_field_version() -> int:
    row = (
        models.TenantSettings.objects.filter(tenant_id=_tenant_id())
        .only("custom_field_version")
        .first()
    )
    return int(getattr(row, "custom_field_version", 0) or 0)


def custom_field_cache_key(entity: str, version: int, tenant_id: Any = None) -> str:
    """BR-TEN-053's key, in one place so a test can assert its shape."""
    return f"cf:v{version}:{tenant_id or _tenant_id()}:{entity}"


def _registry_rows(entity: str) -> list[dict[str, Any]]:
    return [
        {
            "id": str(row.id),
            "key": row.key,
            "label": row.label,
            "help_text": row.help_text or "",
            "data_type": row.data_type,
            "options": list(row.options or []),
            "is_required": row.is_required,
            "display_order": row.display_order,
            "placement": dict(row.placement or {}),
        }
        for row in models.CustomField.objects.filter(
            tenant_id=_tenant_id(), entity=entity, is_active=True
        ).order_by(
            "display_order", "id"
        )  # IS-2 stable secondary
    ]


def custom_field_registry(
    entity: str, *, screen: str | None = None, mode: str | None = None
) -> list[dict[str, Any]]:
    """The ACTIVE definitions for one entity, optionally narrowed to one slot.

    BR-TEN-050: only `is_active` rows are returned, so a deactivated field
    disappears from every screen while its stored values stay in the row.

    US-TEN-017 TC-6 — **a cache outage degrades to Postgres and never fails the
    request.** Every cache touch is wrapped: a dead Redis logs a warning and the
    read continues against the database. A registry that 500s would take every
    screen in the product down with it, which is a far worse failure than a slow
    one.
    """
    from apps.tenancy import custom_fields as cf_law

    version = _custom_field_version()
    key = custom_field_cache_key(entity, version)
    rows: list[dict[str, Any]] | None = None
    cache = _custom_field_cache()
    try:
        cached = cache.get(key)
        if isinstance(cached, list):
            rows = cached
    except Exception:  # pragma: no cover - cache outage path (TC-6)
        logger.warning("custom-field registry cache read failed; falling back to postgres")
    if rows is None:
        rows = _registry_rows(entity)
        try:
            cache.set(key, rows, 3600)
        except Exception:  # pragma: no cover - cache outage path (TC-6)
            logger.warning("custom-field registry cache write failed; serving from postgres")
    if screen is None:
        return rows
    wanted = (screen or "").strip().upper()
    return [row for row in rows if wanted in cf_law.screens_for(row["placement"], mode or "view")]


def custom_field_rows(
    q: str | None = None, entity: str | None = None, status: str | None = None
) -> list[dict[str, Any]]:
    """The S8 management table (US-TEN-014 §capability matrix).

    Sort: Entity A→Z, then display order, then id — IS-2's stable secondary, so
    two fields sharing a display order never swap places between reloads.
    Search covers Label and Key (US-TEN-014 TC-3); IS-3's 2-character minimum is
    the same one the lookup framework applies.
    """
    qs = models.CustomField.objects.filter(tenant_id=_tenant_id())
    if entity:
        qs = qs.filter(entity=entity)
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    if q and len(q.strip()) >= 2:
        term = q.strip()
        qs = qs.filter(Q(label__icontains=term) | Q(key__icontains=term))
    return [_custom_field_dict(row) for row in qs.order_by("entity", "display_order", "id")]


def custom_field_row(field_id: Any) -> dict[str, Any]:
    row = models.CustomField.objects.filter(tenant_id=_tenant_id(), pk=field_id).first()
    if row is None:
        raise errors.NotFoundError()
    return _custom_field_dict(row)


def _custom_field_dict(row: models.CustomField) -> dict[str, Any]:
    from apps.tenancy import custom_fields as cf_law

    placement = dict(row.placement or {})
    return {
        "id": str(row.id),
        "entity": row.entity,
        "key": row.key,
        "label": row.label,
        "help_text": row.help_text or "",
        "data_type": row.data_type,
        "options": list(row.options or []),
        "is_required": row.is_required,
        "is_active": row.is_active,
        "is_document_safe": row.is_document_safe,
        "placement": placement,
        # `DEF-TEN-9153`: the screens that SHOW it — a stored choice on a slot no
        # screen renders yet is kept but not counted, because it shows nowhere.
        "placement_count": cf_law.rendered_placement_count(row.entity, placement),
        "display_order": row.display_order,
        "eligible_slots": {
            mode: list(screens) for mode, screens in cf_law.eligible_slots(row.entity).items()
        },
        # `CR-161-BRC10` W1 — the RENDERED slots, named and grouped, from the one
        # list in `custom_fields.SLOTS`; and what collects the field today.
        "slots": [cf_law.slot_dict(slot) for slot in cf_law.rendered_slots(row.entity)],
        "input_route": cf_law.input_route(row.entity, placement),
    }


def custom_field_card() -> dict[str, Any]:
    """The S8 grid card (US-TEN-014 TC-1/TC-2): a LIVE count of ACTIVE fields
    (US-TEN-014 §5 — `COUNT over custom_field WHERE is_active`), plus the
    per-entity breakdown the management view groups by."""
    rows = models.CustomField.objects.filter(tenant_id=_tenant_id(), is_active=True).values_list(
        "entity", flat=True
    )
    by_entity: dict[str, int] = {}
    for entity in rows:
        by_entity[entity] = by_entity.get(entity, 0) + 1
    return {
        "list": "custom_fields",
        "owner": "tenancy",
        "count": sum(by_entity.values()),
        "by_entity": by_entity,
    }


# ── the reason-code GL mapping (CR-008 ruling 9 · CR-059 CS-35) ────────────
def reason_code_gl_account(code: str) -> dict[str, Any] | None:
    """One ACTIVE reason code of this tenant, with the GL account it maps to.

    **PUBLISHED 2026-09-02 FOR CR-059 CS-35**, which rules that a manual credit
    or adjustment *"posts to its own ledger account, not to undeposited funds"*
    and *"carries a reason from a tenant-maintained list"*. Those are one fact,
    not two: `reason_codes.default_gl_account_id` landed on 2026-08-17 under
    CR-008 ruling 9, the PO's own *"make it separate"*, precisely so that a
    billing-error credit and a goodwill credit can post to different accounts —
    and until today **nothing had ever read that column**.

    Returns `None` when this tenant has no ACTIVE row with that code, so the
    caller can refuse by name rather than posting under a reason nobody
    recognises. A row that exists with `default_gl_account_id` NULL is a real
    and different answer: the reason is valid and simply unmapped, which is what
    the model's own docstring says (*"NULL = unmapped, which is a real state"*),
    and the caller falls back to the designation the ruling already gives it.

    Tenant scoping is this module's own `_tenant_id()` filter under RLS FORCE
    (hard rule 1). The GL id is a DEFERRED FK (B11 F-3) and is NOT validated
    here — liveness and ownership are the LEDGER's to answer, through
    `seams.ledger_account_is_live`, and answering it in two places is how the
    two answers start to differ.
    """
    row = (
        models.ReasonCode.objects.filter(tenant_id=_tenant_id(), active=True)
        .filter(code__iexact=code)
        .first()
    )
    if row is None:
        return None
    return {
        "code": row.code,
        "name": row.name,
        "gl_account_id": row.default_gl_account_id,
    }


def active_reason_codes() -> list[dict[str, Any]]:
    """This tenant's live adjustment/credit reasons (BR-TEN-036), code order.

    CR-059 CS-35's *"a reason from a tenant-maintained list, so 'how much did we
    give away last year, and why' is a question with an answer"*. The list is
    the SAME rows `reason_code_gl_account` validates against, so a screen can
    never offer a reason the recording path would then refuse.
    """
    return [
        {"code": row.code, "name": row.name}
        for row in models.ReasonCode.objects.filter(tenant_id=_tenant_id(), active=True).order_by(
            "code"
        )
    ]


# ── S63 holidays read (BR-TEN-039) ──────────────────────────────────────────
def holidays() -> list[dict[str, Any]]:
    return [
        {"id": str(row.id), "date": row.holiday_date.isoformat(), "label": row.label}
        for row in models.HolidayCalendar.objects.filter(tenant_id=_tenant_id()).order_by(
            "holiday_date"
        )
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-001@d5f8c32 (story+rules snapshot hash — EP-TEN-03 lead story; co-packets EP-TEN-05@0733260 · EP-TEN-06@53479d6 · EP-TEN-07@178c282 · EP-TEN-08@80cdedf · EP-MET-04@34f14b6)
# generated: 2026-08-09 by story-coder v1 (W0 tenancy provisioning + settings lane) · AMENDED 2026-08-09 by story-coder (settings rule-page + reference-data + logo gap lane) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10) · AMENDED 2026-08-11 by Eng-Lead (OQ-115 lane — enabled_service_codes published for the ledger's conditional chart seed; service_row carries the two GL accounts so a tenant's override is readable where it is written) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: `service_ids_by_code` published for billing's stage 6) · AMENDED 2026-08-15 by story-coder v1 (DEF-082 tenant-timezone lane — TIMEZONE_CHOICES and timezone_options() give the OFFERED zone set a home on the server, and tenant_today() now says which half of BR-TEN-081 it is) · AMENDED 2026-08-15 by story-coder (tenant custom-fields lane) · AMENDED 2026-08-19 by story-coder (CR-017 lane — DEF-324: `enabled_service_codes` gained `service__active=True` so it and `services_overview()` cannot disagree; a no-op against today's all-active catalogue, which is why it is safe to make them agree now)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F select, same bar the baseline passes) black✔ pytest tests/test_us_ten_*: 86 passed / 2 skipped (logo lane · identity-seam skip-until-wired) / 2 isolation→G5✔ · suite 335 passed, 7 skipped, 20 deselected✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently) · [gap lane 2026-08-09 FINAL] ruff --select E4,E7,E9,F✔ black✔ · migrate from empty✔ makemigrations --check --dry-run✔ · suite `pytest tests -m "not golden and not isolation"` 682 passed / 7 skipped / 47 deselected (594 was the baseline when this lane started; 62 of the new tests are this lane's, the rest arrived from the concurrent audit-viewer / identity / rating lanes) · `-m isolation` 14 passed / 22 postgres-only skipped · [path-tenancy lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · no migration in this lane · [DEF-082 lane 2026-08-15] tests/test_def_082_tenant_timezone.py 4 passed, 3 of them shown RED FIRST on `AttributeError: module 'apps.tenancy.selectors' has no attribute 'TIMEZONE_CHOICES'` (law 7) · full backend suite 2081 passed / 132 skipped / 1 xfailed✔ · ruff --select E4,E7,E9,F✔ black✔ · run_gates 19 PASS / 1 FAIL / 0 SKIP on both runs, and the FAIL was a DIFFERENT other-lane file each time (G8 on apps/billing/backbill.py, then G7 on apps/ledger/migrations/0006 once that lane landed) — neither file is touched by this lane. Every gate that could see this lane's work is green: G1/G2/G3/G10/G11/G13/G14/G15/G18/G19/G20 PASS, with G15 holding 3542 keys across all 11 catalogues and G18 finding a call site for the new key and none for the retired one · no migration in this lane: tenant_settings.timezone has existed since tenancy/0001
# exceptions: current-period card always reports status "open" — close/lock state is the ledger W5 lane (BR-TEN-023/038); counts from unwired seams surface as null, never fabricated zeros on screen rows · [gap lane 2026-08-09] logo_reference() returns the reference + content type + size, never the bytes: no signed-URL/document-delivery contract exists in core, so nothing streams a logo over HTTP (REPORTED) · rule-page reads merge ratified defaults over the stored document so a parameter added to the registry later renders on an older row — the row itself is seeded by migration 0004 and rewritten in full on every save · [path-tenancy lane 2026-08-10] RESERVED_SUBDOMAINS gained the route-collision names (PO ruling) plus `tenants`, which the ruling did not enumerate — added because POST /api/tenants is a real route and the ruling's stated principle is to reserve anything that could collide with one; REPORTED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
