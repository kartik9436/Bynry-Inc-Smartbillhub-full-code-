# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-070 (EP-CWP-12) — branding READ from Company → Profile ·
#           US-CWP-001 — the utility's own name and colours on the front page ·
#           US-CWP-072 · US-CWP-073 · US-CWP-074 (wave D, 2026-09-04) — the
#           published help answers, the one tip and the service centres, read
#           through this seam and written through none of it.
# Rules:    BR-CWP-012 (read through the owning module's published seam; no
#           second copy) · BR-CWP-005 (the tenant in context is the tenant on
#           the path — asserted, never assumed) · BR-CWP-093 (nothing shows
#           until something is published) · blueprint B2 (logo, name and the
#           two colours are edited once, in Company → Profile)
# Tests:    06-backend/tests/test_us_cwp_070_branding.py TC-1 · TC-6
# Impacts:  apps/tenancy/models.Tenant (one indexed read, eight columns —
#           NFR-41) · apps/tenancy/brand.brand_mark (the mark, computed) ·
#           apps/tenancy/models.Service / TenantService (the pick list)
# ───────────────────────────────────────────────────────
"""What the portal reads from `tenancy`: branding, the tenant's services, and
the two published-content counts the front page's links hang on.

⚠ NOTHING HERE WRITES, and the portal keeps no copy of anything read here.
`branding()` is answered by `apps.tenancy.selectors.company_profile()` — the
same read Company → Profile renders — so a colour changed there reaches the
portal on the next request without a sync (US-CWP-070 TC-6).
"""

from __future__ import annotations

import uuid
from typing import Any

from apps.tenancy import brand
from apps.tenancy import models as tenancy_models
from apps.tenancy import published_content
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import service_size_classes
from core.tenancy import current_tenant_id


def _assert_in_context(tenant_id: Any) -> None:
    """BR-CWP-005: the tenancy selectors read the CONTEXT tenant. A caller
    asking for one tenant while another is in context is a wiring fault and is
    refused here rather than answered with the wrong utility's colours."""
    current = current_tenant_id()
    if current is None or str(current) != str(tenant_id):
        raise RuntimeError(
            "portal seam asked for tenant "
            f"{tenant_id} while {current!r} is in context — BR-CWP-005: the tenant is "
            "resolved from the path before anything is read"
        )


#: The columns the portal reads off the tenant row — and only these. `only()`
#: keeps the EIN and the logo BYTES out of a read a stranger can trigger.
_BRANDING_COLUMNS = (
    "name",
    "subdomain",
    "dba_name",
    "legal_name",
    "brand_primary_hex",
    "brand_accent_hex",
    "logo_file_id",
    "logo_content_type",
)


def regional(tenant_id: Any) -> dict[str, Any]:
    """The tenant's DATE FORMAT and TIME ZONE — the two Regional settings every
    date on every portal screen is rendered against (`IS-8`, `BR-SHL-023`).

    ⚠ **THE PORTAL CANNOT READ THE STAFF ENDPOINT THIS COMES FROM, AND THAT IS
    THE WHOLE REASON THIS FUNCTION EXISTS (`DEF-CWP-3994`).** `ShellWithSession`
    publishes the same two values from `GET /settings/regional`, which is an
    `AnyTenantRole` read; the portal authenticates as `IsPortalCustomer`, so a
    portal screen calling it would 403 on mount. The values travel on the
    portal's own front payload instead, through this seam, because
    `BR-CWP-012` says the portal reads the owning module's tables through a
    published seam and keeps no copy.

    ⚠ **`None` IS RETURNED FOR EITHER FIELD RATHER THAN A DEFAULT, AND THAT IS
    HARD-WON LAW 3 (defaults fail closed).** `DEF-SHL-3964` is a defect made
    entirely of a plausible default: `regionalOf` fell through to
    `SEED_DATE_FORMAT` (`MM/DD/YYYY`) and `SEED_TIME_ZONE` (`UTC`) on every
    screen in the product, forever, with no crash and no blank to notice — a
    Texas utility read every timestamp five hours out. A caller that cannot
    tell *not set* from *the tenant says DD/MM/YYYY* would repeat it, so the
    absence travels as an absence and the front end refuses to render a date
    until it knows.

    ⚠ **`language` RIDES HERE TOO FROM 2026-09-07, AND IT IS THE SAME DEFECT
    ONE FIELD OVER (`DEF-CWP-4440`, `BR-CWP-105`).** The Product Owner, on the
    running product: *"Language setting does not work in customer portal"*. The
    staff shell reads `regional.language` off `GET /shell/display` and calls
    `i18n.changeLanguage` with it; the portal is that shell's SIBLING in the
    route tree and had **zero** i18n references, so a utility that chose
    *Español (México)* got a Spanish staff app and an English portal, with
    nothing red anywhere. `timezone` and `date_format` were put on this payload
    for exactly that reason on 2026-09-06 and the language was not — which is
    why it is added to the FUNCTION THAT ALREADY EXISTS rather than to a new
    one beside it.

    ⚠ **THIS IS THE UTILITY'S DEFAULT AND NEVER A CUSTOMER'S OWN CHOICE.** A
    signed-in customer's `accounts.preferred_language` beats it (`BR-CWP-105`'s
    order, PO ruling 2026-09-07) and travels on the SESSION payload, behind
    `IsPortalCustomer` — this route is anonymous, and what language the account
    at this address prefers is a fact about a person (`BR-CWP-021`).

    ⚠ **`None` IS RETURNED FOR ANY OF THE THREE RATHER THAN A DEFAULT** — see
    the paragraph above; the same argument covers the language, and the front
    end applies nothing rather than pinning English over a tenant whose choice
    simply has not loaded.

    ONE indexed read, the settings row by tenant, three columns (NFR-41) — the
    language is one more column on a row this function already fetched, so the
    query count does not move.
    """
    _assert_in_context(tenant_id)
    row = (
        tenancy_models.TenantSettings.objects.filter(tenant_id=tenant_id)
        .only("timezone", "date_format", "language")
        .first()
    )
    if row is None:
        # A tenant with no settings row is a real state on a fresh sign-up and
        # is not an error here: the screen states the absence rather than
        # inventing a format.
        return {"timezone": None, "date_format": None, "language": None}
    return {
        "timezone": row.timezone,
        "date_format": row.date_format,
        # `""` is not a choice. `tenant_settings.language` is a bare TEXT column
        # and an empty string would reach `changeLanguage("")`, which i18next
        # treats as a language to switch to. Absence travels as absence.
        "language": row.language or None,
    }


def branding(tenant_id: Any) -> dict[str, Any]:
    """The four shared fields (blueprint B2) plus the slug, read and not copied.

    ONE indexed read (NFR-41): the tenant row by primary key, eight columns.
    `company_profile()` — what Company → Profile renders — costs three reads
    (the settings row for the organisation type, the logo reference, the
    row itself) and carries the EIN; a guest page has no use for any of that,
    so this seam reads the row directly and composes the mark the same way
    `tenancy.selectors.company_mark` does, through `tenancy.brand`.

    `trading_name` is the DBA where one is set, else the legal name, else the
    name given at sign-up — the same fallback the letterhead mark uses.
    """
    _assert_in_context(tenant_id)
    row = tenancy_models.Tenant.objects.filter(pk=tenant_id).only(*_BRANDING_COLUMNS).first()
    if row is None:  # unreachable behind require_tenant; stated rather than assumed
        raise RuntimeError(f"no tenant row for {tenant_id}")
    has_logo = bool(row.logo_file_id and row.logo_content_type)
    return {
        "slug": row.subdomain,
        "trading_name": row.dba_name or row.legal_name or row.name,
        "legal_name": row.legal_name,
        "brand_primary_hex": row.brand_primary_hex,
        "brand_accent_hex": row.brand_accent_hex,
        "has_logo": has_logo,
        # CR-172-BRC10 — the logo's reference, which the image address carries
        # (`?v=`) so the portal draws a replaced logo at once. The bytes are
        # served by tenancy's ONE logo address, never through this seam.
        "logo_ref": row.logo_file_id if has_logo else None,
        "logo": (
            {"logo_file_id": row.logo_file_id, "content_type": row.logo_content_type}
            if has_logo
            else None
        ),
        "mark": brand.brand_mark(
            dba_name=row.dba_name,
            legal_name=row.legal_name,
            fallback_name=row.name,
            brand_primary_hex=row.brand_primary_hex,
        ),
    }


def enabled_services(tenant_id: Any) -> list[dict[str, Any]]:
    """The tenant's OWN enabled services, in catalogue order — the only
    services CWP-070 may offer as front-page chips (US-CWP-070 TC-5).

    `id` is the platform `services.id` (what `portal_settings.front_page_
    service_ids` stores); `code`/`name`/`color` are what a screen shows. The
    id never reaches a customer screen (B14 rule 31) — `selectors.front`
    strips it.
    """
    _assert_in_context(tenant_id)
    rows = (
        tenancy_models.TenantService.objects.filter(tenant_id=tenant_id, enabled=True)
        .select_related("service")
        .order_by("service__sort", "service__code")
    )
    return [
        {
            "id": str(row.service_id),
            "code": row.service.code,
            "name": row.service.name,
            "color": row.service.color,
        }
        for row in rows
        if row.service.active
    ]


def published_help_answer_count(tenant_id: Any) -> int:
    """How many help answers this tenant has PUBLISHED (BR-CWP-093 — the Help
    card and link exist only when this is above zero).

    ⚠ Wave A answered 0 for every tenant because the table did not exist yet.
    CR-068 wave D built it, and this is the `status = published` query wave A
    said it owed — same name, same caller, a real number (2026-09-04).
    """
    _assert_in_context(tenant_id)
    return published_content.published_answer_count(tenant_id)


def published_help_answers(tenant_id: Any, *, topic: str | None = None) -> list[dict[str, Any]]:
    """`CWP-011`'s list. ⚠ `status = published` is in the QUERY, one level
    down in `tenancy.published_content` (BR-CWP-094) — a draft never reaches
    this seam, so it can never reach a screen."""
    _assert_in_context(tenant_id)
    return published_content.published_answers(tenant_id, topic=topic)


def published_help_answer(tenant_id: Any, slug: str, *, locale: str | None) -> dict[str, Any]:
    """One answer, in the reader's language when there is one and in English
    when there is not — and the answer SAYS which (BR-CWP-094)."""
    _assert_in_context(tenant_id)
    return published_content.published_answer(tenant_id, slug, locale=locale)


def help_topics(tenant_id: Any) -> list[str]:
    """The topics that actually have a published answer, in portal order — the
    chip row on `CWP-011`. ⚠ A chip that filters to nothing is a container with
    nothing in it (BR-CWP-093), so the list is derived and never a constant."""
    _assert_in_context(tenant_id)
    seen: list[str] = []
    for row in published_content.published_answers(tenant_id):
        if row["topic"] not in seen:
            seen.append(row["topic"])
    return seen


def shown_service_centre_count(tenant_id: Any) -> int:
    """How many service centres this tenant SHOWS to customers (BR-CWP-093 —
    *Visit us* exists only when this is above zero).

    ⚠ Wave A answered 0 for the same reason as the help count; wave D built the
    table and this is the real query (2026-09-04).
    """
    _assert_in_context(tenant_id)
    return published_content.shown_centre_count(tenant_id)


def shown_service_centres(tenant_id: Any) -> list[dict[str, Any]]:
    """`CWP-013` — the centres marked *shown to customers*, each with today's
    state computed from the clock and the tenant's holiday calendar. ⚠ Raises
    404 when none is shown: the page cannot exist empty (BR-CWP-093)."""
    _assert_in_context(tenant_id)
    return published_content.public_centres(tenant_id)


def shown_service_centre(tenant_id: Any, slug: str) -> dict[str, Any]:
    """`CWP-014` — one centre, what it can do, what it CANNOT, what it takes,
    its week and the next holiday that closes it."""
    _assert_in_context(tenant_id)
    return published_content.public_centre(tenant_id, slug)


def tip_for_screen(tenant_id: Any, screen: str) -> dict[str, Any] | None:
    """At most one tip — on, in season, top of the list (BR-CWP-095). ⚠ `None`
    is a NORMAL answer: the slot closes up and nobody can tell it was there."""
    _assert_in_context(tenant_id)
    return published_content.tip_for_screen(tenant_id, screen)


def attached_answer(tenant_id: Any, screen: str, *, locale: str | None) -> dict[str, Any] | None:
    """The one published answer a clerk pinned to this screen, or `None`.

    ⚠ **THIS FUNCTION WAS WRITTEN TWICE, BY TWO LANES, IN ONE HOUR, AND BOTH
    COPIES REACHED THE BRANCH (`DEF-CWP-4031`).** `DEF-CWP-3985` needed it for
    the BILL (`CWP-061`) and `DEF-CWP-3945` needed it for the OVERDUE screen
    (`CWP-057`); the two bodies were byte-identical and Python silently kept
    the second, leaving the first as dead code that reads exactly like the live
    one. Folded here, with both docstrings merged so neither lane's reasoning
    is lost. **The lesson is not "look harder": neither lane could see the
    other, because a sibling working in its own worktree has its commits in
    none of the places a listing can see until it pushes** — the same blind
    spot `allocate.py` exists for on ids, one level up at a function.

    ⚠ **THIS SEAM DID NOT EXIST AND THAT IS THE WHOLE OF BOTH DEFECTS.**
    `help_answer.also_show_on_screen` is a column; `SettingsPortalHelp.tsx`
    writes it, with a picker and a summary line; `published_content
    .attached_answer` reads it and its docstring names the placement. Every end
    was built and **`apps/portal/` could not reach the read at all**, so a
    utility ticked *also show this on the bill* — or on the overdue screen —
    the tick saved, and the answer appeared nowhere. The clerk got a
    confirmation either way, which is why nobody looked.

    ⚠ **ONE FIELD, TWO PLACEMENTS, NEVER A SECOND ROW** (`US-CWP-071` §1). The
    utility writes the answer ONCE on the help screen and ticks
    `also_show_on_screen`; every placement is that same row read again, so the
    answer under a bill and the answer in Help cannot drift apart.
    `ALSO_SHOW_SCREENS` is the closed set (`bill`, `usage`, `overdue`).

    ⚠ **`None` IS A NORMAL ANSWER AND THE SLOT CLOSES UP** (`BR-CWP-093`,
    *nothing empty ever appears*) — exactly as `tip_for_screen` behaves one
    content type over, which is the worked example this copies end to end.

    ⚠ **THE LOCALE IS THE READER'S**, and a locale with no variant gets the
    answer in English with a line saying so rather than a blank
    (`BR-CWP-094`: *a missing translation is better than a missing answer*).
    """
    _assert_in_context(tenant_id)
    return published_content.attached_answer(tenant_id, screen, locale=locale)


def service_ids_are_the_tenants_own(tenant_id: Any, ids: list[str]) -> list[str]:
    """The ids in `ids` that are NOT among the tenant's enabled services."""
    own = {row["id"] for row in enabled_services(tenant_id)}
    return [one for one in ids if one not in own]


def us_state_code(value: Any) -> str | None:
    """`Texas` or `TX` → `TX`; anything else → None — the ONE list the staff
    side's address forms accept (`tenancy.selectors.US_STATES`), read here so a
    portal applicant's mailing address (`DEF-CWP-9163`) cannot be held to a
    second copy of it. Pure: it reads no row and needs no tenant."""
    return tenancy_selectors.us_state_code(str(value or ""))


# ═══════════════════════════════════════════════════════════════════════════
# `CR-161-BRC10` W7 — THE UTILITY'S OWN QUESTIONS ON THE NEW-SERVICE FORM
# ═══════════════════════════════════════════════════════════════════════════
#
# PO, Part 2 row 16: *"Portal new-service form (applicant) · Staff Request
# detail · Customer → clerk · Off by default per field; a utility turns each
# one on"*; the Rules table: *"One utility only — Another utility never sees a
# utility's fields or answers, including on the portal"*.
#
# ⚠ **THREE LOCKS ON "ONE UTILITY", AND THIS SEAM IS THE MIDDLE ONE.** The
# registry is read under the tenant the PATH names (`_assert_in_context`), its
# rows are filtered by that tenant and RLS-FORCEd (`tenancy/0008`), and its
# cache key carries the tenant id (BR-TEN-053). And what leaves is the public
# view only — `custom_fields.PORTAL_PUBLIC_KEYS` — never a field switched to
# *Don't ask*, never a switched-off one, never the placement map.


def utility_state(tenant_id: Any) -> str | None:
    """The utility's own state as a two-letter code, or None — `DEF-CWP-9817`.

    Start service asks a street, a town and a ZIP and NO state, because the
    blueprint (p31) draws none: a utility serves its own state. So an address
    we do not hold is written out in US form with THIS state, the company
    profile's (`tenants.state`), normalised the way a typed mailing state is.
    `None` when the profile holds none or something that is not a state — the
    line is then written without one rather than with a guess (law 3).
    """
    _assert_in_context(tenant_id)
    row = tenancy_models.Tenant.objects.filter(pk=tenant_id).only("state").first()
    return us_state_code(row.state) if row is not None and row.state else None


def application_custom_fields(tenant_id: Any) -> dict[str, list[dict[str, Any]]]:
    """`{customers: […], accounts: […], premises: […]}` — the fields this
    utility switched to *Ask the customer*, as the form may be told them."""
    from apps.tenancy import custom_fields as cf_law

    _assert_in_context(tenant_id)
    return {
        entity: cf_law.portal_public_view(tenancy_selectors.custom_field_registry(entity))
        for entity in cf_law.PORTAL_ENTITIES
    }


def application_custom_answers(tenant_id: Any, stored: Any) -> dict[str, dict[str, Any]]:
    """A draft's stored answers narrowed to the fields STILL asked — a field
    switched to *Don't ask* (or off) since it was typed is neither shown back
    nor carried to the request; the answer stays on the draft, unread."""
    from apps.tenancy import custom_fields as cf_law

    _assert_in_context(tenant_id)
    held = stored if isinstance(stored, dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for entity in cf_law.PORTAL_ENTITIES:
        asked = {
            d["key"]
            for d in cf_law.portal_definitions(tenancy_selectors.custom_field_registry(entity))
        }
        answers = held.get(entity) if isinstance(held.get(entity), dict) else {}
        kept = {key: value for key, value in answers.items() if key in asked}
        if kept:
            out[entity] = kept
    return out


def application_unanswered(tenant_id: Any, stored: Any) -> list[str]:
    """The record types with a REQUIRED asked field still blank on this draft,
    in `PORTAL_ENTITIES` order — what `missing_before_submit` turns into the
    step that holds Send."""
    from apps.tenancy import custom_fields as cf_law

    _assert_in_context(tenant_id)
    held = stored if isinstance(stored, dict) else {}
    out: list[str] = []
    for entity in cf_law.PORTAL_ENTITIES:
        answers = held.get(entity) if isinstance(held.get(entity), dict) else {}
        for definition in cf_law.portal_definitions(tenancy_selectors.custom_field_registry(entity)):
            if not definition.get("is_required"):
                continue
            value = answers.get(definition["key"])
            if value is None or value == [] or (isinstance(value, str) and not value.strip()):
                out.append(entity)
                break
    return out


def _entity_field(exc: Any, entity: str) -> Any:
    """`custom_data.<key>` → `custom_data.<entity>.<key>`: three record types
    share one form, and two may use the same key (*Gate code* on the customer
    and on the property), so a refusal must name the box, not just the key."""
    for problem in exc.field_errors:
        field = str(problem.get("field") or "")
        if field.startswith("custom_data."):
            problem["field"] = f"custom_data.{entity}.{field[len('custom_data.'):]}"
    return exc


def clean_application_custom_answers(
    tenant_id: Any, submitted: Any, *, existing: Any, require: bool
) -> dict[str, dict[str, Any]]:
    """Validate what the applicant typed and return the MERGED blob to store.

    Each record type's answers are judged by tenancy's own validator against
    ONLY the fields asked on the portal — so a key the utility keeps internal
    (or another utility's key, or one that never existed) is refused exactly as
    an unknown key is, by the same sentence, and nothing tells a stranger which
    of the three it was. `require=False` while the form is being typed (a
    draft is unfinished by definition); `True` at Send, where a field the
    utility marked required must hold an answer (*"Required means required
    only where it's typed in"* — and here is where it is typed in).
    """
    from apps.tenancy import custom_fields as cf_law
    from core import errors as core_errors

    _assert_in_context(tenant_id)
    if submitted is None:
        submitted = {}
    if not isinstance(submitted, dict):
        raise core_errors.ValidationError(
            core_errors.VAL_FORMAT, message_key="portal.application.fieldNotAccepted",
            params={"field": "custom_data"},
        )
    unknown = sorted(set(submitted) - set(cf_law.PORTAL_ENTITIES))
    if unknown:
        raise core_errors.ValidationError(
            core_errors.VAL_UNKNOWN_LOOKUP,
            message_key="portal.application.fieldNotAccepted",
            params={"field": f"custom_data.{unknown[0]}"},
        )
    held = existing if isinstance(existing, dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for entity in cf_law.PORTAL_ENTITIES:
        before = dict(held.get(entity) or {}) if isinstance(held.get(entity), dict) else {}
        if entity not in submitted and not require:
            if before:
                out[entity] = before
            continue
        definitions = cf_law.portal_definitions(tenancy_selectors.custom_field_registry(entity))
        try:
            merged = cf_law.validate_custom_data(
                definitions,
                submitted.get(entity) or {},
                require_input=require,
                screen=cf_law.PORTAL_SCREEN,
                existing=before,
            )
        except core_errors.ValidationError as exc:
            raise _entity_field(exc, entity) from None
        if merged:
            out[entity] = merged
    return out


def is_uuid(value: Any) -> bool:
    try:
        uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return False
    return True


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave H — WHAT A SERVICE IS BILLED ON (`BR-CWP-073`, US-CWP-040)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE COLUMN, NOT A PROXY FOR IT.** `DEF-CWP-3765`'s standing lesson, in
# its own words: *"when a model has an exact column for a fact, read the
# column. A shape that implies it is a rule in disguise, and rules move."*
# `customers_seam.services_held` ships WITHOUT *what it is billed on* and says
# so, because deriving it from *does the service point have a meter* would be
# exactly that proxy. The exact column is one module over.
#
# `tenant_services.billing_basis` has held three values since `BR-TEN-1180`
# (2026-09-02) and they are `BR-CWP-073`'s three cases, one for one:
#
#   metered   — a register is read. `CWP-033` draws a chart.
#   share     — a PERCENTAGE of another service's money (`BR-RAT-015` — sewer
#               is a share of the water usage charge). **No chart, no zero
#               series**: nothing measures it, and a sewer connection has no
#               assets either, so counting them would price it at 0 (`DEF-2409`).
#   capacity  — a COUNT OF THE UNIT'S ASSETS (`BR-RAT-090`). Carts, ERUs,
#               panels, Mbps, kW. **No chart**; the panel names the equipment.

#: The three, re-exported so the portal names ONE spelling of each. A
#: re-exported constant is a second copy until something compares them, so
#: `test_us_cwp_040_usage.py` asserts these are the tenancy module's own.
BASIS_METERED = tenancy_models.BILLING_BASIS_METERED
BASIS_SHARE = tenancy_models.BILLING_BASIS_SHARE
BASIS_CAPACITY = tenancy_models.BILLING_BASIS_CAPACITY


def service_billing_bases(tenant_id: Any) -> dict[str, str]:
    """`{service_code: billing_basis}` for every ACTIVE catalogue service.

    `apps.tenancy.selectors.services_overview()` — the same read the S8
    Services & UoM card draws, so a utility that changes a basis on Settings
    sees `CWP-033` change with it.

    ⚠ **A SERVICE WITH NO TENANT ROW ANSWERS `metered`, AND THAT IS TENANCY'S
    OWN DEFAULT RATHER THAN THIS SEAM'S GUESS** — *"a tenant with no row for a
    service has declared NOTHING, and nothing declared is metered"* (hard-won
    law 3: the unsafe option is the one you type). The consequence on this
    screen is the safe one: a service nobody has declared draws a chart from
    whatever months exist, and draws nothing at all when there are none.
    """
    _assert_in_context(tenant_id)
    return {
        row["service"]: row["billing_basis"]
        for row in tenancy_selectors.services_overview()
    }


def size_class_names(service_code: str) -> dict[str, str]:
    """`{code: name}` for a service's RATIFIED size classes — `T-96` → `96 gal cart`.

    `apps.tenancy.service_size_classes.size_classes_for_service`, the ratified
    vocabulary itself. It is what lets a `capacity` service's panel read *your
    96 gal cart* instead of *your T-96*, and it is a pure function over a
    signed list rather than a query.

    An empty map is a normal answer for a service with no ratified bands, and
    the caller then names the equipment by its own kind (*your refuse cart*)
    rather than by a code.
    """
    try:
        rows = service_size_classes.size_classes_for_service(service_code)
    except Exception:  # pragma: no cover — an unruled service is not an outage
        return {}
    return {code: name for code, name in rows}


def support_phone(tenant_id: Any) -> str | None:
    """The utility's own phone, as typed on Settings → Company → Profile.

    `CR-189-BRC10` (PO 2026-10-22, *"call the office"*): the update-email dead
    end shows it, read here and never typed into a screen. One indexed read,
    one column. `None` when none is entered; the screen then leaves it out.
    """
    _assert_in_context(tenant_id)
    value = (
        tenancy_models.Tenant.objects.filter(pk=tenant_id)
        .values_list("support_phone", flat=True)
        .first()
    )
    text = str(value or "").strip()
    return text or None
