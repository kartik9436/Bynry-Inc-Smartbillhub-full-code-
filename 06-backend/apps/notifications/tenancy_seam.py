# ── Trace ──────────────────────────────────────────────
# Epics:    EP-NOT-01 (the dispatcher needs the tenant's CLOCK before it can
#           honour a send window) · EP-NOT-02 (the renderer needs the tenant's
#           date format, currency and identity)   Screens: S8
#           NOTE: no US-ID is cited in this header ON PURPOSE. G10 reads a
#           Trace-header US-ID as "this file ships that story's test cases";
#           this file ships two cross-module reads, not a story. Same precedent
#           as apps/billing/settings_seam.py and apps/billing/tenancy_seam.py.
# Rules:    BR-TEN-013 (a module NEVER touches another module's ORM; a
#           cross-module read resolves the owner's published callable) ·
#           BR-NOT-009 (quiet hours are "08:00–21:00 TENANT TIME" — the zone is
#           tenancy's Regional setting, not this module's guess) · BR-TEN-017
#           (identity values are stamped AT RENDER; issued documents keep the
#           ones they were rendered with) · BR-TEN-020 (a tenant's own clock
#           decides what day it is) · CLAUDE.md rule 2 (money is Decimal, and
#           its CURRENCY is a tenant fact, never a constant)
# Tests:    06-backend/tests/test_us_not_002_dispatcher.py ·
#           06-backend/tests/test_us_not_005_rendering.py
# Impacts:  apps/notifications/dispatcher.py (the quiet-hours window) ·
#           apps/notifications/rendering.py (dates, currency, identity stamp)
# ───────────────────────────────────────────────────────
"""notifications → tenancy SEAM: the tenant's clock, formats and identity.

Two reads, both PUBLISHED today, both resolved BY NAME at call time so nothing
here imports tenancy's internals (B1 / BR-TEN-013):

  apps.tenancy.selectors.regional_settings() -> dict
    The S8 Regional page. This module uses four of its keys and ignores the
    rest: `timezone` (BR-NOT-009's *"tenant time"*), `date_format` and
    `number_format` (A19's header rule — *"dates per tenant Regional
    settings"*), and `currency` (which is the TENANT's, set once and locked by
    BR-TEN-042 — a renderer that printed a `$` would be wrong for every tenant
    that is not in dollars).

  apps.tenancy.selectors.company_profile() -> dict
    The utility's own identity, for BR-TEN-017's stamp at render: legal/DBA
    name, mailing and remit-to address, support phone and email, website. A
    document renders with the values in force AT RENDER and an issued document
    is never re-rendered, so this read answers the question "who was this
    utility on the day this went out?" and nothing caches it.

╔══════════════════════════════════════════════════════════════════════════╗
║  A MISSING TIMEZONE IS NOT UTC, AND THAT IS THE WHOLE POINT OF THIS FILE. ║
╚══════════════════════════════════════════════════════════════════════════╝

`tenant_timezone()` REFUSES when tenancy cannot answer, and refuses again when
the stored zone is not a zone this machine knows. It does not fall back to UTC.

The reason is BR-NOT-009 and it is worth the extra branch: quiet hours are
08:00–21:00 **tenant time**, and a utility in America/Chicago silently evaluated
against UTC has a window that is 03:00–16:00 on its own clock. The dispatcher
would then refuse to send at 09:00 on a Tuesday morning and would happily text
late-payment reminders at 22:00 — which is precisely T5-23's incident, produced
by a fallback rather than by a bug. There is no safe default for a clock, so the
only honest answer to "which zone?" is either the tenant's or a refusal.

`regional_formats()` and `company_identity()` take the OPPOSITE posture and say
so on the value they return: a rendered document with an unformatted date is
still a document a customer can read and act on, and OQ-117's ruling (PO
2026-08-12, *"issue and report it"*) settled that a document with a NAMED
absence goes out rather than being refused. So those two report what they could
not read instead of raising — the absence travels with the artifact and is
countable, which is the same discipline `apps/billing/documents.py` applies to
a bill it can render but cannot total.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

#: The tenancy reads this module depends on, named once so each contract is
#: greppable from BOTH sides of the boundary — the discipline
#: `apps/billing/settings_seam.py` states and G20 harvests.
TENANCY_MODULE = "tenancy"
REGIONAL_READ = "regional_settings"
IDENTITY_READ = "company_profile"
#: The S70 Collections & notices page (BR-PAY-017's ladder intervals,
#: BR-REP-016's stage days). Added 2026-08-15 by the CONTENT lane for the ONE
#: thing US-NOT-010 needs from it: the DAY NUMBERS that render on a reminder.
#: `apps/payments/settings_seam.py` names the same contract from the other side.
SETTINGS_FAMILY_READ = "settings_family"
COLLECTIONS_FAMILY = "collections"


class TenantClockUnavailable(RuntimeError):
    """The tenant's timezone cannot be read, so no send window can be evaluated.

    Deliberately NOT one of the `core.errors` catalog exceptions: those carry an
    HTTP status because they answer a request, and this is raised inside a
    dispatch cycle that runs as a job. The dispatcher catches it and records the
    cycle as REFUSED with this message, rather than dispatching against a clock
    nobody could read.
    """


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one.

    getattr at CALL time — the idiom `apps/notifications/services.py`,
    `apps/billing/settings_seam.py` and `apps/metering/seams.py` all use. No
    import statement binds notifications to tenancy's internals, and the day a
    lane moves a selector this file needs no re-wiring (hard-won law 2).
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def tenant_timezone() -> ZoneInfo:
    """The tenant's own clock. REFUSES rather than assuming one — see the box.

    Tenant scoping is not added here and cannot be lost here: the value comes
    from tenancy's own read, which filters on `app.tenant_id` under RLS FORCE
    (CLAUDE.md hard rule 1). This module issues no query of its own.
    """
    read = _resolve(TENANCY_MODULE, REGIONAL_READ)
    if read is None:
        raise TenantClockUnavailable(
            f"apps.{TENANCY_MODULE}.selectors.{REGIONAL_READ} is not published, so this "
            "tenant's timezone cannot be read. BR-NOT-009's send window is 08:00–21:00 "
            "TENANT time; evaluating it against UTC instead would hold back a 09:00 "
            "Tuesday send and release a 22:00 one. Dispatch is refused rather than run "
            "against a clock nobody could read."
        )
    name = (read() or {}).get("timezone")
    if not name:
        raise TenantClockUnavailable(
            "this tenant's Regional settings carry no timezone, so BR-NOT-009's send "
            "window has no clock to be evaluated on. Settings → Company → Regional is "
            "where it is set. Nothing here substitutes UTC: a quiet-hours window "
            "measured in the wrong zone is not a smaller guarantee, it is a different "
            "and wrong one."
        )
    try:
        return ZoneInfo(str(name))
    except (ZoneInfoNotFoundError, KeyError, ValueError) as bad:
        raise TenantClockUnavailable(
            f"this tenant's stored timezone {name!r} is not a zone this system knows, so "
            "the send window cannot be evaluated. Refused rather than silently resolved "
            "to UTC (BR-NOT-009)."
        ) from bad



#: `CR-188-BRC10` — the product's language registry (Settings → Regional's
#: vocabulary). Named, not copied: PO 2026-10-22, *"don't do any hardcoding"*.
LANGUAGE_REGISTRY_MODULE = "services"
LANGUAGE_REGISTRY = "SEED_LANGUAGES"


def platform_languages() -> tuple[str, ...]:
    """Every language a utility may choose — tenancy's own registry, read at
    call time. Empty when it cannot be read; the caller then seeds only the
    `default` variant and says so."""
    try:
        target = import_module(f"apps.{TENANCY_MODULE}.{LANGUAGE_REGISTRY_MODULE}")
    except ImportError:  # pragma: no cover - defensive
        return ()
    found = getattr(target, LANGUAGE_REGISTRY, ())
    return tuple(str(code) for code in found or ())


#: `DEF-NOT-10649` — the customer portal's quick-pay page, `CWP-002`.
SUBDOMAIN_READ = "tenant_subdomain"
PORTAL_PAY_PATH = "/{tenant}/portal/pay"


def portal_pay_link() -> str | None:
    """`PUBLIC_APP_ORIGIN` + `/<tenant>/portal/pay`, or None when either half
    cannot be read — never a relative link nobody can open (law 3)."""
    from core import public_origin

    origin = public_origin.public_app_origin()
    read = _resolve(TENANCY_MODULE, SUBDOMAIN_READ)
    if origin is None or read is None:
        return None
    try:
        slug = read()
    except Exception:  # noqa: BLE001 — a missing link drops its paragraph, never the message
        return None
    return f"{origin}{PORTAL_PAY_PATH.format(tenant=slug)}" if slug else None


#: `CR-199-BRC10` S7 — the customer portal's front door, `/<tenant>/portal`.
PORTAL_HOME_PATH = "/{tenant}/portal"


def _tenant_slug() -> str | None:
    read = _resolve(TENANCY_MODULE, SUBDOMAIN_READ)
    if read is None:
        return None
    try:
        slug = read()
    except Exception:  # noqa: BLE001 — a missing link prints its label, never breaks a message
        return None
    return str(slug) if slug else None


def portal_home_link() -> str | None:
    """`{portal_link}` — `PUBLIC_APP_ORIGIN` + `/<tenant>/portal`, or None.
    Built the way `portal_pay_link` is; never a hand-built host (law 3)."""
    from core import public_origin

    origin = public_origin.public_app_origin()
    slug = _tenant_slug()
    if origin is None or slug is None:
        return None
    return f"{origin}{PORTAL_HOME_PATH.format(tenant=slug)}"


#: `CR-199-BRC10` S6 — the ONE logo address (`tenancy.api.company_logo_file`,
#: readable without signing in), on the API's PUBLIC host. An email is opened
#: far from the app, so it needs an absolute address; `PUBLIC_API_BASE_URL` is
#: the server setting that names that host (`CR-198-BRC10`).
LOGO_FILE_PATH = "/api/{tenant}/settings/company/logo/file"


def logo_image_url(identity: dict[str, Any]) -> str | None:
    """The logo's absolute address for an email `<img>`, or None — then the
    header carries the utility's name alone. `?v=` is the logo's reference, so
    a replaced logo is a new address (`CR-172-BRC10`)."""
    from urllib.parse import quote

    from django.conf import settings

    if not identity.get("has_logo"):
        return None
    base = str(getattr(settings, "PUBLIC_API_BASE_URL", "") or "").strip().rstrip("/")
    slug = _tenant_slug()
    if not base.startswith(("https://", "http://")) or slug is None:
        return None
    address = f"{base}{LOGO_FILE_PATH.format(tenant=quote(slug, safe=''))}"
    ref = identity.get("logo_ref")
    return f"{address}?v={quote(str(ref), safe='')}" if ref else address


def tenant_default_language() -> str | None:
    """The utility's Regional default language, or None when unset — the
    FALLBACK language of every message since 2026-10-29 (PO option B,
    `BR-NOT-006` amended): the customer's own language is asked first
    (`message_language.language_for`). The same read
    `apps.metering.seams.tenant_default_language` makes."""
    read = _resolve(TENANCY_MODULE, REGIONAL_READ)
    if read is None:  # pragma: no cover - tenancy publishes this today
        return None
    code = (read() or {}).get("language")
    return str(code) if code else None

def regional_formats() -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """(formats, problems) — the tenant's date/number/currency conventions.

    Reports rather than refuses, and the caller carries the report onto the
    artifact. A19's header makes money 2dp and dates tenant-formatted; a
    document that renders an ISO date because the format could not be read is
    still a document the customer can act on, and OQ-117's closure (PO
    2026-08-12, *"issue and report it"*) is the ruling that says such a document
    goes out with its absence NAMED rather than being refused.
    """
    read = _resolve(TENANCY_MODULE, REGIONAL_READ)
    if read is None:  # pragma: no cover - tenancy publishes this today
        return {}, (
            {
                "code": "regional_settings_unavailable",
                "br_ref": "BR-TEN-020",
                "detail": f"apps.{TENANCY_MODULE}.selectors.{REGIONAL_READ} is not "
                "published, so dates render in ISO form and money carries no currency "
                "code. The document states this rather than implying the tenant chose "
                "those conventions.",
            },
        )
    values = dict(read() or {})
    problems: list[dict[str, Any]] = []
    for key, br_ref in (("date_format", "BR-TEN-020"), ("currency", "BR-TEN-042")):
        if not values.get(key):
            problems.append(
                {
                    "code": f"{key}_not_set",
                    "br_ref": br_ref,
                    "detail": f"this tenant's Regional settings carry no {key}. The "
                    "rendered document names the absence instead of guessing a "
                    "convention — a date that reads 03/04/2026 in the wrong order and a "
                    "figure with no currency are both wrong in a way nobody can see.",
                }
            )
    return values, tuple(problems)


def company_identity() -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """(identity, problems) — who this utility is, AT RENDER (BR-TEN-017).

    Reports rather than refuses, for `regional_formats`' reason. The values are
    read at every render and never cached: BR-TEN-017 says an identity edit
    affects FUTURE documents only, and the way that stays true is that an issued
    document is never re-rendered — not that this module holds a stale copy.
    """
    read = _resolve(TENANCY_MODULE, IDENTITY_READ)
    if read is None:  # pragma: no cover - tenancy publishes this today
        return {}, (
            {
                "code": "company_identity_unavailable",
                "br_ref": "BR-TEN-017",
                "detail": f"apps.{TENANCY_MODULE}.selectors.{IDENTITY_READ} is not "
                "published, so the document carries no masthead, no support phone and no "
                "remit-to address. A customer cannot pay a bill that does not say who to "
                "pay; the absence is named on the artifact.",
            },
        )
    return dict(read() or {}), ()


class CollectionsConfigUnavailable(RuntimeError):
    """The tenant's collection-ladder settings cannot be read, so no day number
    can be rendered.

    REFUSES rather than falling back to BR-REP-016's seeded 7/14/30, and that is
    the whole point of the class existing. US-NOT-007 TC-3 and US-NOT-010 TC-3
    are the same assertion from two sides — *"day numbers are seeds, not
    constants"* — so a renderer that quietly printed 7/14/30 when the tenant had
    configured 10/20/35 would put a WRONG DATE on a letter chasing a real
    customer, and every test would still pass. An unreachable setting is not a
    setting.
    """


def collections_config() -> dict[str, Any]:
    """The S70 ladder/cadence parameters for THIS tenant (BR-PAY-017/BR-REP-016).

    Tenant scoping is not added here and cannot be lost here: the value comes
    from tenancy's own read, which filters on `app.tenant_id` under RLS FORCE.
    This module issues no query of its own.
    """
    read = _resolve(TENANCY_MODULE, SETTINGS_FAMILY_READ)
    if read is None:
        raise CollectionsConfigUnavailable(
            f"apps.{TENANCY_MODULE}.selectors.{SETTINGS_FAMILY_READ} is not published, so "
            "this tenant's collection-ladder intervals cannot be read. Nothing here falls "
            "back to BR-REP-016's seeded 7/14/30: those are SEEDS of a tenant setting "
            "(*'day numbers are always tenant config, never constants'* — 04-flows.md §3), "
            "and a reminder rendered with the wrong day number tells a customer the wrong "
            "date to pay by."
        )
    return dict(read(COLLECTIONS_FAMILY) or {})


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-002@7d4e0c5 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/10-notifications/06-epics/EP-NOT-01-outbound-queue.md · EP-NOT-02-templates-rendering.md — US-NOT-005 §1, the A19 header rule — · 10-notifications/02-business-rules.md — BR-NOT-009 — · 08-qa/01-e2e/journeys/T5-23-quiet-hours-hold.md)
# generated: 2026-08-15 by story-coder (W3 notifications delivery-core lane)
# checklist: A✔ B✔ C✔ D=deferred(not an API surface — two cross-module reads) E=deferred(no-frontend-half; the S8 Regional and Company cards that WRITE these values are tenancy's and already ship) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · G20: both declared contracts resolve at the declared kind (apps.tenancy.selectors) — no parked row is needed for this seam · tests/test_us_not_002_dispatcher.py proves the clock REFUSAL goes red when the zone is unreadable
# exceptions: (1) `tenant_timezone` REFUSES and does not default to UTC, while
#         the other two REPORT and return partial values. The asymmetry is
#         deliberate and is the file's main claim: a wrong clock silently
#         INVERTS a compliance rule, whereas a missing date format produces a
#         readable document with a named gap (OQ-117's ruling).
#         (2) This seam reads FOUR keys out of `regional_settings` and decides
#         nothing. Which format string maps to which rendering is the renderer's
#         (`apps/notifications/rendering.py`), stated where A19 is cited.
#         (2b) AMENDED 2026-08-15 (CONTENT lane): a THIRD read was added —
#         `apps.tenancy.selectors.settings_family("collections")`, the S70 page —
#         for the day numbers BR-REP-016 makes tenant config. It REFUSES like the
#         clock rather than reporting like the formats, because a wrong day
#         number on a dunning letter is a wrong date to pay by, not a cosmetic
#         gap. Resolves today; no parked G20 row is needed.
#         (3) NO tenant-language read. BR-NOT-006 puts the LANGUAGE variant on
#         the template pin, and the pin travels on the queue row — so the
#         language a message renders in is decided at QUEUE time by its writer,
#         not looked up here at dispatch. A read here would re-resolve a pinned
#         fact and break the reprint guarantee.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
