# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-001 (EP-CWP-01) — the front page's read · US-CWP-069 — the
#           overview read · US-CWP-070 — the branding read. Screens: CWP-001 ·
#           CWP-069 · CWP-070
# Rules:    CR-068 R8 (defaults) · R9 (*Check my area* waits — the public
#           status page needs somebody keeping it current out of hours; the
#           card is now SENT and unavailable rather than withheld, PO ruling
#           2026-09-05) · BR-CWP-005 (tenant first) · BR-CWP-021 (a guest sees
#           an amount and a status, never a person — the front page shows
#           neither) · BR-CWP-093 (nothing empty ever appears: a LINK exists
#           only when what it opens exists — the six cards are a catalogue and
#           are exempt by that ruling, the nav words are not) · B14 rule 31
#           (no database id is a visible value — the guest payload carries no
#           id at all; a reason_code is a catalogue key the screen translates,
#           never a string it prints) · hard-won law 3 (defaults fail closed)
# Tests:    06-backend/tests/test_us_cwp_001_front.py · test_us_cwp_069_settings.py ·
#           test_us_cwp_070_branding.py
# Impacts:  guest_api.py (`front`, `availability`, `quick_services`, `draft`) ·
#           backoffice_api.py (`overview`, `branding`)
# ───────────────────────────────────────────────────────
"""portal reads. NOTHING here writes (G81 refuses an ORM write in this file).

THE ONE JUDGMENT WORTH STATING: a tenant with NO `portal_settings` row reads
as the R8 defaults and is NOT written to by a read. The row appears on the
first save (`settings_service`). So "the portal is off for a new tenant" is
literally true — there is no row and `is_live` answers False.
"""

from __future__ import annotations

# ⚠ `DEF-CWP-3769` — `date` is used in several signatures here and was never
# imported. The file worked only because the `__future__` import makes every
# annotation a string, so the undefined name is never evaluated: `ruff check`
# has been RED on this file since `my_details` landed and no gate runs ruff over
# `apps/portal`. Found by a lane adding another function with the same signature
# and reading the linter before committing.
#
# ⚠ **TWO LANES ADDED THIS SAME LINE ON THE SAME AFTERNOON** and the merge kept
# both, which ruff then flagged as a redefinition. One survives. The id above is
# the register's — a resolve script renamed the citation to `DEF-CWP-3770` while
# the register kept `3769` on this defect, and `3770` is the OTHER lane's usage
# tile. Corrected here rather than left, because a citation pointing at the
# wrong row is worse than no citation (`DEF-2804`'s shape).
# ⚠ **AND IT IS NO LONGER ANNOTATIONS-ONLY** (`CR-085` `CPB-15`, 2026-09-08):
# `_months_back` calls `date(...)` at run time to work out the window
# *Download a year* covers, so the import is load-bearing now. Said out loud
# because a comment claiming a guarantee is not the guarantee (hard-won law 1)
# and the next reader would otherwise trust the old sentence and delete it.
from datetime import date  # noqa: F401 - annotations, and _months_back
from decimal import Decimal
from typing import Any

from apps.portal import models, money, paging
from apps.portal.seams import customers_seam, metering_seam, tenancy_seam
from core import errors

#: The six errand cards CWP-001 draws, in the wireframe's order.
CARD_ORDER: tuple[str, ...] = (
    "pay_bill",
    "report_problem",
    "check_my_area",
    "start_service",
    "what_things_cost",
    "help_answers",
)


def settings_row(tenant_id: Any) -> models.PortalSettings | None:
    return models.PortalSettings.objects.filter(tenant_id=tenant_id).first()


def settings_view(tenant_id: Any) -> dict[str, Any]:
    """The row's fields, or the R8 defaults when no row exists yet."""
    row = settings_row(tenant_id)
    if row is None:
        view = dict(models.DEFAULTS)
        view["front_page_service_ids"] = []
        view["exists"] = False
        return view
    return {
        "is_live": row.is_live,
        **{name: getattr(row, name) for name in models.SWITCH_FIELDS},
        "strapline": row.strapline,
        "front_page_service_ids": list(row.front_page_service_ids or []),
        "office_hours_text": row.office_hours_text,
        "emergency_phone": row.emergency_phone,
        "quick_service_categories": list(row.quick_service_categories or []),
        #: US-CWP-060 — `CWP-046`'s errand cards. See `request_errands` below.
        "request_errands": list(row.request_errands or []),
        #: CR-190-BRC10 — how many days an emailed agreement link stays valid.
        "agreement_link_valid_days": row.agreement_link_valid_days,
        #: DEF-BIL-10531 — how many days the bill email's PDF link stays valid.
        "bill_link_valid_days": row.bill_link_valid_days,
        "exists": True,
    }


#: Why a card a visitor can see is not one they can use. THREE codes, and they
#: are different IN KIND — which is the whole reason a code travels rather than
#: a bare `false`. A utility looking at its own front page (`CWP-070` draws this
#: very payload as its preview) can act on two of them and never on the third,
#: and until 2026-09-05 all three looked identical from that chair: the card was
#: simply not there (`DEF-CWP-3953`).
#:
#: They are catalogue KEYS and never English prose — the same posture
#: `apps/reports/catalog.py` takes: the server says which condition holds and
#: the screen says it in the reader's own language (B14 rule 35), in six words
#: or fewer (rule 33), carrying no code of its own (rule 31).
#:
#: ⚠ **NOTHING ELSE MAY JOIN THIS LIST WITHOUT A SENTENCE IN ALL ELEVEN
#: CATALOGUES IN THE SAME COMMIT.** A reason with no wording renders as its own
#: key, which is an internal code on a customer's screen — `DEF-CWP-3952`'s
#: shape, one surface over.

#: The utility turned this off in Settings → Customer portal → *What customers
#: can do*. Reversible by them, today, without asking us.
REASON_SWITCHED_OFF: str = "switched_off_by_the_utility"

#: `CR-068` R9 — outage REPORTING ships and the public status page waits,
#: because it needs somebody keeping it current out of hours. **No switch a
#: utility owns turns this on**; only a reversal of that ruling does, which is
#: why it must not read like the line above.
REASON_STATUS_PAGE_NOT_OFFERED: str = "status_page_not_offered"

#: `BR-CWP-093` — nothing empty ever appears. Nothing is published yet, so
#: there is nothing behind the door. **One published answer turns it on**, for
#: this tenant, today.
REASON_NOTHING_PUBLISHED: str = "nothing_published_yet"


def cards_for(settings: dict[str, Any], links: dict[str, bool]) -> list[dict[str, Any]]:
    """ALL SIX cards CWP-001 draws, in `CARD_ORDER`, each carrying whether a
    visitor may use it and — when they may not — WHY, as a code.

    ⚠ **THIS USED TO FILTER, AND THE FILTERING WAS RIGHT: `US-CWP-001` TC-2
    read *absent, not greyed* and this function honoured it.** PO ruling
    2026-09-05, verbatim: *"Yoi ahev these cards - may be disable them, but for
    completess have them on screen"*. So a card a tenant cannot offer is now
    SENT and DRAWN DISABLED with its reason, and TC-2 is amended in the commit
    that carries this change rather than in a later one.

    **What the reversal buys, and it is not tidiness (`DEF-CWP-3953`):** an
    absence has no empty state, so B14 rule 17 could never reach it and nothing
    in this product told a utility that publishing one help answer is what adds
    *Help & answers* to its own front page. Two cards were missing for reasons
    a week apart in cost — a ruling and a five-minute job — and from the
    utility's chair they looked the same, because they looked like nothing.

    **What did NOT change, and each is deliberate:**

    * **The refusal is still at the EDGE** (`BR-CWP-002`). A drawn card is not
      a mounted door: `quick_pay_enabled = false` still refuses
      `POST /public/bills/lookup`, and TC-2 asserts that half unchanged. A form
      nobody can see is still a form somebody can POST to.
    * **The NAV WORDS still come and go.** A nav word is a destination, not a
      catalogue; a disabled word in a top bar is hard-won law 2's dead control.
      `links.help` and `links.visit` are untouched.
    * **A portal that is not live still draws NO cards** (`front` below,
      TC-3) — a holding page has no grid to disable.
    * **`what_things_cost` is available and always was.** Prices are public;
      its `Start →` is held by `CR-068` R3 because no screen draws them yet,
      which is a different state from this one and stays in the client.
    """
    reasons: dict[str, str | None] = {
        "pay_bill": None if settings["quick_pay_enabled"] else REASON_SWITCHED_OFF,
        "report_problem": None if settings["outage_reporting_enabled"] else REASON_SWITCHED_OFF,
        "check_my_area": REASON_STATUS_PAGE_NOT_OFFERED,
        "start_service": None if settings["requests_enabled"] else REASON_SWITCHED_OFF,
        "what_things_cost": None,
        "help_answers": None if links["help"] else REASON_NOTHING_PUBLISHED,
    }
    return [
        {"key": key, "available": reasons[key] is None, "reason_code": reasons[key]}
        for key in CARD_ORDER
    ]


def _chips(tenant_id: Any, settings: dict[str, Any]) -> list[dict[str, Any]]:
    """The front-page chips, in the ORDER THE UTILITY LISTED THEM. The
    wireframe draws *Water · Sewer · Trash · Electric* — neither the catalogue's
    seed order nor alphabetical — so the stored list is the order, the same
    rule the help answers follow (*the order here is the order on the portal*).
    A ticked id that is no longer one of the tenant's enabled services is
    simply not drawn."""
    by_id = {row["id"]: row for row in tenancy_seam.enabled_services(tenant_id)}
    chips: list[dict[str, Any]] = []
    for one in settings["front_page_service_ids"]:
        row = by_id.get(str(one))
        if row is not None:
            chips.append({"code": row["code"], "name": row["name"], "color": row["color"]})
    return chips


def front(tenant_id: Any) -> dict[str, Any]:
    """`GET /portal/public/front` — everything CWP-001 draws, and nothing a
    guest must not see. No id of any kind travels (B14 rule 31); no person
    (BR-CWP-021); the utility's colours are the tenant's own, read not copied.

    When the portal is OFF the answer is the holding page's: the name and
    colours (so the page is the utility's), `is_live: false`, and no cards,
    no links, no strapline, no switches — bills and letters are unaffected
    because nothing here touches them (US-CWP-001 TC-3).
    """
    brand = tenancy_seam.branding(tenant_id)
    settings = settings_view(tenant_id)
    tenant = {
        "slug": brand["slug"],
        "name": brand["trading_name"],
        "brand_primary_hex": brand["brand_primary_hex"],
        "brand_accent_hex": brand["brand_accent_hex"],
        # CR-172-BRC10 — the portal's header draws the utility's logo (or its
        # generated mark) beside the name, from tenancy's one logo address.
        "has_logo": brand["has_logo"],
        "logo_ref": brand["logo_ref"],
        "mark": brand["mark"],
    }
    # ⚠ **THE TENANT'S DATE FORMAT AND TIME ZONE TRAVEL ON THIS PAYLOAD, AND
    # `DEF-CWP-3994` IS WHY.** `IS-8` says every date renders in the tenant's
    # own format and every instant in the tenant's own zone. The staff app gets
    # that from `GET /settings/regional` and publishes it through
    # `TenantRegionalProvider`; the portal is that provider's SIBLING in the
    # route tree, so it was never inside it, and the endpoint is staff-only
    # anyway (`AnyTenantRole` vs the portal's `IsPortalCustomer`). Every portal
    # date therefore rendered as a raw `2026-08-14` where the drawing reads
    # `31 Aug 2026` — the second half of the defect the Product Owner reported.
    #
    # It rides on the FRONT payload rather than on the session because every
    # portal screen already reads the front for its branding, signed in or not,
    # and a guest receipt carries a date too.
    #
    # The KEYS are `timezone` and `date_format` deliberately: that is the exact
    # shape `ShellWithSession.tenantRegionalOf` already validates, so the portal
    # reuses that mapper rather than writing a second one that could disagree
    # about which of the seven formats are drawable.
    #
    # ⚠ **AND `language` JOINED THEM ON 2026-09-07 — THE SAME HOLE, ONE FIELD
    # OVER** (`DEF-CWP-4440`, `BR-CWP-105`). The staff shell has applied the
    # tenant's language since `BR-SHL-030`; the portal is its SIBLING in the
    # route tree and applied none, so a utility on *Español (México)* had a
    # Spanish staff app and an English portal. It rides HERE, on the guest
    # payload, because the guest half of the portal has no other payload at all
    # and a stranger reading a receipt is entitled to the utility's own
    # language. **This is the utility's DEFAULT.** A signed-in customer's own
    # `accounts.preferred_language` beats it and travels on the SESSION
    # payload instead — never here, because this route is anonymous and what
    # language the account at this address prefers is a fact about a person
    # (`BR-CWP-021`).
    #
    # ⚠ **AND `locales` JOINED IT ON 2026-09-07 — THE LIST THE GUEST'S PICKER
    # OFFERS** (`DEF-CWP-4442`, PO: *"currently in drop down show only 2
    # elnglish and spanish"*). It rides here for the same reason `language`
    # does: the guest half of the portal has no other payload. **It is a
    # different fact from `regional["language"]` one key over** — that is what
    # the utility CHOSE, this is what a visitor may PICK — and a different fact
    # again from the eleven catalogues the bundle can draw. The guest dropdown
    # read the BUNDLE's list until this landed, and so offered nine languages
    # the product does not.
    #
    # It travels on BOTH branches below although the holding page draws no nav
    # and therefore no picker (`US-CWP-001` TC-3): the front end types the field
    # as required, and a field present on one branch and absent on the other is
    # the optional-shape trap `PortalFront.regional` carries its own note about.
    # It is a constant — no tenant data, no query, nothing to leak.
    regional = tenancy_seam.regional(tenant_id)
    if not settings["is_live"]:
        return {
            "tenant": tenant,
            "is_live": False,
            "regional": regional,
            "locales": list(PORTAL_LOCALES),
            "cards": [],
            "links": {"help": False, "visit": False},
            "services": [],
            "strapline": None,
            "office_hours_text": None,
            "emergency_phone": None,
        }
    links = {
        "help": tenancy_seam.published_help_answer_count(tenant_id) > 0,
        "visit": tenancy_seam.shown_service_centre_count(tenant_id) > 0,
    }
    return {
        "tenant": tenant,
        "is_live": True,
        "regional": regional,
        "locales": list(PORTAL_LOCALES),
        "cards": cards_for(settings, links),
        "links": links,
        "switches": {name: bool(settings[name]) for name in models.SWITCH_FIELDS},
        "services": _chips(tenant_id, settings),
        "strapline": settings["strapline"],
        "office_hours_text": settings["office_hours_text"],
        "emergency_phone": settings["emergency_phone"],
    }


def usage(tenant_id: Any, settings: dict[str, Any]) -> list[dict[str, Any]]:
    """WHO IS USING IT — only the counts this product can count TODAY, each a
    real number or a stated reason, never a zero standing in for "not built".

    * `requests_from_portal` — a real count over `service_requests` rows
      carrying the portal channel (0 on a tenant where none has arrived).
    * `readings_sent_in` — when the self-read switch is OFF the row reads
      *Readings are off, so nothing is counted* (US-CWP-069 TC-7): a reason,
      not a zero, because zero would read as nobody using it. When the switch
      is ON the row is absent until wave J creates the reading path that
      would be counted — a row that could only ever say 0 is the silence
      hard-won law 2 warns about.
    * enrolled and signed-in — absent until the credential and session tables
      exist (wave E); the same reasoning. The screen draws the rows it is
      given and invents none.
    """
    rows: list[dict[str, Any]] = [
        {
            "key": "requests_from_portal",
            "count": customers_seam.requests_from_portal(tenant_id),
            "reason": None,
        }
    ]
    if not settings["self_read_enabled"]:
        rows.append({"key": "readings_sent_in", "count": None, "reason": "readings_off"})
    return rows


def address_for(brand: dict[str, Any], origin: str | None) -> dict[str, Any]:
    """The portal address, read from `tenants.subdomain` and never stored
    twice (US-CWP-069 TC-2). `origin` is the environment's public app host
    (`core.public_origin`, `DEF-CWP-9717`) — never the host the request
    arrived on; the path is the PO's ruling made literal — `/{tenant}/portal`."""
    path = f"/{brand['slug']}/portal"
    return {
        "slug": brand["slug"],
        "path": path,
        "url": f"{origin.rstrip('/')}{path}" if origin else None,
    }


def overview(tenant_id: Any, *, origin: str | None) -> dict[str, Any]:
    """`GET /settings/portal` — CWP-069."""
    brand = tenancy_seam.branding(tenant_id)
    settings = settings_view(tenant_id)
    return {
        "address": address_for(brand, origin),
        "is_live": settings["is_live"],
        "switches": {name: bool(settings[name]) for name in models.SWITCH_FIELDS},
        # CR-190-BRC10 — the agreement link's life, days (a setting, seeded 7).
        "agreement_link_valid_days": settings["agreement_link_valid_days"],
        # DEF-BIL-10531 — the bill email link's life, days (a setting, seeded 30).
        "bill_link_valid_days": settings["bill_link_valid_days"],
        "usage": usage(tenant_id, settings),
    }


def branding(tenant_id: Any) -> dict[str, Any]:
    """`GET /settings/portal/branding` — CWP-070: the shared four READ-ONLY
    with where they are edited, the portal-only four, the tenant's own
    services as the pick list, and the front page as a visitor would see it
    (the live preview's data)."""
    brand = tenancy_seam.branding(tenant_id)
    settings = settings_view(tenant_id)
    return {
        "shared": {
            "trading_name": brand["trading_name"],
            "legal_name": brand["legal_name"],
            "brand_primary_hex": brand["brand_primary_hex"],
            "brand_accent_hex": brand["brand_accent_hex"],
            "has_logo": brand["has_logo"],
            "logo_ref": brand["logo_ref"],
            "logo": brand["logo"],
            "mark": brand["mark"],
            "edited_at": "/settings/company",
        },
        "portal_only": {name: settings[name] for name in models.BRANDING_FIELDS},
        "services": tenancy_seam.enabled_services(tenant_id),
        "preview": front(tenant_id),
    }


# ═══════════════════════════════════════════════════════════════════════════
# TRACK ANYTHING — US-CWP-010, and the rule is in the return value
# ═══════════════════════════════════════════════════════════════════════════
#: The reference series a guest may look up, and what each answers with.
#:
#: ⚠ **`"payment"` ARRIVED 2026-09-05 AND THE HOLD ABOVE IT EXPIRED, WHICH IS
#: THE WHOLE POINT OF HAVING WRITTEN THE HOLD DOWN.** This comment read *"`PAY-`
#: IS DELIBERATELY ABSENT AND THIS IS A WAVE ORDER, NOT A GAP"* until wave R
#: landed the guest payment itself. The reason it gave was true and is now
#: spent: a payment's second fact is the postcode of the SERVICE ADDRESS, three
#: joins away (`payment → account → unit → premises`), and the walk did not
#: exist here. It does — `bill_lookup` has taken exactly those two steps since
#: wave P (`customers_seam.account_premises_id` → `premises_postcode`), so the
#: tracker now reuses the same pair rather than inventing a second one.
#:
#: ⚠ **AND WHAT IT ANSWERS IS NARROWER THAN THE RECEIPT, NOT EQUAL TO IT.**
#: `US-CWP-010` TC-7 is explicit — *"Its status and date. ⚠ **Not the amount**
#: — the amount is account data"* — so `payment_progress_view` carries no money
#: at all, while `guest_payment_receipt` (the screen a person is looking at the
#: instant they pay) carries the figure they just agreed to. Two reads of one
#: payment, and the difference is deliberate: `BR-CWP-028` promises the LOOKUP
#: (*"every guest flow ends on a reference … and can be looked up with it"*) and
#: `BR-CWP-024` governs what the lookup RETURNS. `US-CWP-005` TC-3 — *"the
#: receipt is still reachable by reference"* — is satisfied by the first and
#: bounded by the second; neither statement had to move.
#:
#: ⚠ **`"report"` CAME OUT ON 2026-09-04 (`CR-072`) AND THE SURFACE GOT
#: NARROWER, NOT WIDER.** It used to mean *the `RP-` series* — an
#: `interruptions.reference`, looked up here on an unauthenticated endpoint.
#: `CR-072` §4 stops the `RP-` series being customer-facing: nothing hands one
#: to a guest any more, so an anonymous lookup on it was a door with nobody on
#: the other side of it, which is the mirror of hard-won law 2. A report is now
#: tracked by its `SR-` number like every other request.
#:
#: **The word `report` did not vanish — it moved.** A tracked view still
#: ANSWERS `series: "report"`, because that is the SHAPE the screen draws
#: (a kind, a place, and one of three plain words) and both shapes now come out
#: of `service_requests`. What this tuple lists is what a visitor may TYPE.
TRACKABLE_SERIES: tuple[str, ...] = ("request", "payment")


# ── which of three words a stranger reads (CR-072) ──────────────────────────
#
# ⚠ **THIS IS A PRESENTATION RULE AND IT LIVES IN THE PORTAL DELIBERATELY.**
# It is not a fact `customers` holds (the row has eleven states) and not a fact
# `metering` holds (a report with no interruption has no crew). It is the
# portal deciding which of the three words `CWP-007` and `CWP-012` draw a
# stranger should read, and it composes both modules' facts to do it — which
# is what this file is for.
#
# **WHY THE THREE WORDS SURVIVED THE RULING.** `CR-072` moved WHERE the record
# lives; it said nothing about what a passer-by reads, and the PO had already
# seen *Looking into it → Crew on site → Resolved* on the live deployment.
# Serving `Submitted` and `Under review` to somebody standing over a burst main
# would be the staff worklist's vocabulary leaking onto a public page — which
# `B14` rule 32 refuses in its own dialect and which no part of the ruling
# asked for.


def already_reported_street(tenant_id: Any, location_text: str) -> str | None:
    """The street somebody has already told us about, or None
    (`US-CWP-007` TC-7).

    ⚠ **IT ASKS TWO TABLES SINCE `CR-072`, AND ASKING ONLY THE OLD ONE WOULD
    HAVE LOOKED FINE.** Before, a report WAS an interruption, so one scan of
    `interruptions` answered it. A report is a service request now: the ordinary
    case is a street several people have reported and NOBODY has opened an
    interruption for. Left pointed at `interruptions` this would have returned
    None for every real second report — a shipped sentence quietly going silent,
    with `tsc` and every test green, which is the exact shape of hard-won law 2.

    So it asks both, in the order the answers matter:

      1. is there a CONFIRMED interruption still open on this street? — we know,
         and a crew may already be on it;
      2. otherwise, has somebody else already reported it? — we have been told.

    ⚠ **IT NEVER REFUSES ANYTHING.** *"Two reports of one burst is the desired
    behaviour — we would rather hear twice than not at all."*
    """
    street = metering_seam.street_words(location_text)
    if street is None:
        return None
    confirmed = metering_seam.open_interruption_on_street(tenant_id, location_text)
    if confirmed is not None:
        return metering_seam.street_words(confirmed.location_text)
    reported = customers_seam.open_report_on_street(tenant_id, street)
    if reported is None:
        return None
    return metering_seam.street_words(reported.address_as_given) or street


def report_progress_status(row: Any, interruption_status: str | None = None) -> str:
    """The one word a guest reads for a report: *looking into it*, *crew on
    site* or *resolved*.

    **THE CONFIRMED INTERRUPTION WINS WHEN THERE IS ONE.** A crew moves that
    record, and it is the operational truth — a report attached to *crew on
    site* says so even though the request beneath it has not moved. That is the
    whole point of `CR-072`'s many-to-one: twelve people who rang about one
    burst main all see the same crew arrive.

    **WITH NO INTERRUPTION, THE REQUEST'S OWN STATE ANSWERS**, and only three
    answers exist, so the map is short and stated rather than clever:

        completed · closed · refused · withdrawn  →  resolved
        in_fulfilment                             →  crew_on_site
        everything else                           →  looking_into_it

    ⚠ **`refused` READS AS *resolved* AND THAT IS A DECISION, NOT A ROUNDING.**
    A clerk who looked and found nothing has CLOSED IT OFF, which is the fourth
    step `CWP-007`'s own timeline promises. The alternative is a fourth word in
    eleven catalogues for a state a report reaches by the back door, and
    `BR-CWP-024` gives a guest progress and never the reason.
    """
    from apps.metering import interruptions as interruption_models

    if interruption_status:
        return interruption_status
    state = getattr(row, "state", None)
    if state in customers_seam.CLOSED_REQUEST_STATES:
        return interruption_models.STATUS_RESOLVED
    if state == customers_seam.STATE_IN_FULFILMENT:
        return interruption_models.STATUS_CREW_ON_SITE
    return interruption_models.STATUS_LOOKING


def _digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _squashed(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def second_fact_matches(given: Any, *, phones: list[Any], postcodes: list[Any]) -> bool:
    """Does what the visitor typed match a fact only the sender would know?

    `BR-CWP-025`, and the two forms the screen offers are *"the postcode, or the
    phone number you gave us"*. A phone is compared on its DIGITS — nobody types
    `(512) 555-7730` the same way twice — and a postcode on its letters and
    digits, which is how `78702` and ` 78702 ` become one value.

    ⚠ **A PHONE IS MATCHED ON ITS LAST SEVEN DIGITS AND NOT ON THE WHOLE
    STRING.** `(512) 555-7730` and `+1 512 555 7730` are the same telephone and
    a stranger who has it typed it one way or the other. Seven is the local
    number: shorter would start matching different people.
    """
    typed = str(given or "").strip()
    if not typed:
        return False
    typed_digits = _digits(typed)
    if len(typed_digits) >= 7:
        for phone in phones:
            known = _digits(phone)
            if known and known[-7:] == typed_digits[-7:]:
                return True
    typed_squashed = _squashed(typed)
    if len(typed_squashed) >= 3:
        for postcode in postcodes:
            if postcode and _squashed(postcode) == typed_squashed:
                return True
    return False


def _postcodes_in(text: Any) -> list[str]:
    """Every five-digit run in a free-text address line — `"1408 Elm St, Austin
    TX 78702"` → `["78702"]`.

    ⚠ **A HOUSE NUMBER CAN BE FIVE DIGITS TOO.** `"10025 Ranch Rd"` would offer
    `10025` as a postcode, so a visitor typing the house number would get in.
    That is accepted rather than solved: the second fact's job is to stop a
    stranger who has only a guessable reference, and somebody who knows the
    house number of the address they reported is the sender. Stated so the next
    lane knows it was a decision.
    """
    import re as _re

    return _re.findall(r"\b\d{5}\b", str(text or ""))


# ── the words a stranger reads about their own payment (US-CWP-010 TC-7) ─────
#
# ⚠ **AMENDED 2026-10-21 (`DEF-CWP-10341`, `CR-186-BRC10`).** Until then this
# map folded `posted` into *cleared* and every unknown state into *processing*.
# Both were harmless while nothing wrote `posted` — and `CR-186` made EVERY new
# payment `posted` at entry and `cleared` only when its deposit batch is
# reconciled with the bank. So a guest was told *cleared* about money the bank
# had not yet confirmed, and a `cancelled` payment (`payments/0036`) — which no
# entry here named — fell through to *processing*, "still going through",
# about money that had been undone.
#
# **WHAT SURVIVES IS THE ANSWERS A PERSON ACTUALLY ASKS:** is it still going
# through, did you get it, did it not go through, was it called off.
#
# ⚠ **`posted` AND `cleared` READ THE SAME, AS *received*.** Bank
# reconciliation is the utility's bookkeeping, not the payer's question: from
# the moment a payment is posted it is applied to their bills. *Reversed* still
# folds into *failed* — it names a mechanism (a chargeback, a bounced cheque)
# and `BR-CWP-024` gives a guest PROGRESS AND NEVER THE REASON.
# `report_progress_status` folds `refused` into *resolved* on the same reading.
#
# ⚠ **THE WORDS ARE THE PORTAL'S OWN (`portal.money.state.*`)**, the
# vocabulary the signed-in money list (`CWP-041`) already draws, so one payment
# cannot read two ways to one customer. The staff words (`payments.status.*`)
# say *Posted* and *Cleared* — exactly the two ledger facts a customer is not
# shown. (Until 2026-10-21 this screen reused the staff catalogue to avoid a
# second vocabulary; the portal's own was the one it should have reused.)
#
# ⚠ **EVERY STATUS `payments` CAN WRITE HAS AN ENTRY**, and a test reads
# `payments.models.PAYMENT_STATUSES` to prove it, so the fallback below is
# reachable only by a value the database's CHECK would refuse.
PAYMENT_PROGRESS_RECEIVED = "received"
PAYMENT_PROGRESS_PROCESSING = "processing"
PAYMENT_PROGRESS_FAILED = "failed"
PAYMENT_PROGRESS_CANCELLED = "cancelled"
#: ⚠ **THE EXPLICIT FALLBACK, AND IT CLAIMS NOTHING.** *Processing* used to sit
#: here, which is a claim ("it is still going through") about a state nobody
#: had defined. *Status unavailable* is the only word true of every unknown.
PAYMENT_PROGRESS_UNKNOWN = "unknown"

PAYMENT_PROGRESS_WORDS: dict[str, str] = {
    "posted": PAYMENT_PROGRESS_RECEIVED,
    "cleared": PAYMENT_PROGRESS_RECEIVED,
    "processing": PAYMENT_PROGRESS_PROCESSING,
    "failed": PAYMENT_PROGRESS_FAILED,
    "reversed": PAYMENT_PROGRESS_FAILED,
    "cancelled": PAYMENT_PROGRESS_CANCELLED,
}


def payment_progress_status(status: Any) -> str:
    """One customer word for a payment, whatever `payments` calls its state.

    An unknown state reads `unknown` rather than raising — the page still
    answers — and rather than borrowing a real word, which would be a guess.
    """
    return PAYMENT_PROGRESS_WORDS.get(str(status or ""), PAYMENT_PROGRESS_UNKNOWN)


def payment_progress_view(row: dict[str, Any]) -> dict[str, Any]:
    """A PAYMENT as progress — `US-CWP-010` TC-7, and it is the narrowest view
    on this surface.

    ⚠ **NO AMOUNT, AND THAT IS THE TEST CASE'S OWN EMPHASIS** (`TC-7`,
    verbatim: *"Its status and date. ⚠ **Not the amount** — the amount is
    account data"*). `guest_payment_receipt` DOES carry the figure, because the
    person reading it agreed to that figure ten seconds earlier on the same
    screen; whoever types a reference into `CWP-012` a fortnight later may be
    anybody holding a scrap of paper. Same payment, two reads, and the
    difference is who is looking.

    ⚠ **NO `masked_name` EITHER**, which `bill_lookup` does carry. The mask
    exists to let somebody CONFIRM they have the right bill before they pay
    (`BR-CWP-020`); a tracked payment is already named by a reference only the
    payer was given, so there is nothing left for it to do and `BR-CWP-021`
    takes it off. The receipt dropped it for the same reason.

    ⚠ **AND NO `account_id`**, which the seam hands up and this function drops
    on the floor. It is the INPUT to the postcode walk, never an output —
    `guest_fields.NEVER_ON_A_GUEST_RESPONSE` names it, and `G92` reads this
    function every run.

    **BOTH DATES** (`BR-PAY-021`). `reported_at` is the posting date — *when we
    received it* — and it is keyed that way rather than `paid_at` because it is
    the same fact `request_progress_view` puts under that name (`received_at`,
    when the record reached us), and `CWP-012` draws one date row for every
    series. `cleared_at` is NULL while a payment is processing, which is a real
    answer and not a gap.
    """
    posted_at = row.get("posted_at")
    cleared_at = row.get("cleared_at")
    return {
        "series": "payment",
        "reference": row["reference"],
        "status": payment_progress_status(row.get("status")),
        "reported_at": posted_at.isoformat() if hasattr(posted_at, "isoformat") else posted_at,
        "cleared_at": cleared_at.isoformat() if hasattr(cleared_at, "isoformat") else cleared_at,
    }


def _tracked_payment(tenant_id: Any, *, reference: str, second_fact: str) -> dict[str, Any] | None:
    """`PAY-26-08841` + `78702` → progress, or `None` for every miss.

    ⚠ **THE SECOND FACT IS THE POSTCODE AND DELIBERATELY NOT THE PHONE**, which
    the request branch also accepts. A guest payment is made by whoever is
    holding the paper — `US-CWP-004` §4 is explicit that *"a guest may be a
    neighbour"* — so the account holder's telephone number is a fact the payer
    may never have had, and accepting it would let anybody who knows the
    household's number in. The postcode is printed on the bill the payer was
    already asked for at step 1, which is what makes it the right pair here.

    ⚠ **THE WALK IS `bill_lookup`'S, NOT A SECOND ONE.**
    `account_premises_id` → `premises_postcode` is the same pair that read the
    postcode when the payment was taken, so a bill that could be paid on a
    postcode can be tracked on it, by construction rather than by agreement.
    """
    from apps.portal.seams import payments_seam

    payment = payments_seam.payment_by_number(tenant_id, number=reference)
    if payment is None:
        return None
    premises_id = customers_seam.account_premises_id(tenant_id, payment["account_id"])
    postcode = customers_seam.premises_postcode(premises_id)
    if not second_fact_matches(second_fact, phones=[], postcodes=[postcode]):
        return None
    return payment_progress_view(payment)


def _second_fact_fits(request: Any, second_fact: str) -> bool:
    """The applicant's phone or the address's ZIP code — `track`'s own test,
    named once so the reply door below asks exactly the same question."""
    postcodes = _postcodes_in(request.address_as_given)
    if request.resolved_premises_id is not None:
        premises_postcode = customers_seam.premises_postcode(request.resolved_premises_id)
        if premises_postcode:
            postcodes.append(premises_postcode)
    return second_fact_matches(second_fact, phones=[request.applicant_phone], postcodes=postcodes)


def tracked_request_id(tenant_id: Any, *, reference: str, second_fact: str) -> Any:
    """`DEF-CWP-9049` — the id of the REQUEST a reference and its second fact
    name, for the Track page's *Add a document*; or None, identically for every
    miss, exactly as `track` answers (`TC-3`, `TC-6`). A report and a payment
    are None: neither is asked for more. The id never leaves the server — the
    guest edge passes it straight to the write point."""
    typed = str(reference or "").strip()
    if not typed:
        return None
    request = customers_seam.request_by_number(tenant_id, typed)
    if request is None or customers_seam.is_report(request):
        return None
    if not _second_fact_fits(request, second_fact):
        return None
    return request.pk


def track(tenant_id: Any, *, reference: str, second_fact: str) -> dict[str, Any] | None:
    """One reference plus one fact only the sender knows → PROGRESS, NEVER DATA.

    Returns None for *"we cannot find that"* — and returns None **identically**
    for an unknown reference, a reference belonging to another tenant, and a
    real reference with the wrong second fact (`TC-3`, `TC-6`). One answer for
    all three is the whole point: a different answer for *"right reference,
    wrong postcode"* would confirm the reference exists, and confirming that is
    the enumeration this endpoint is guarded against.

    ⚠ **READ THE RETURNED KEYS AS THE RULE (`BR-CWP-024`).** No name, no
    balance, no other reference on the account, no id. `US-CWP-010` TC-4
    asserts it on the RESPONSE BODY and not on the rendered page.

    ⚠ **THREE SHAPES NOW, AND THE THIRD CARRIES NO MONEY.** A request answers
    `series: "request"`, a report `series: "report"`, and — since 2026-09-05 — a
    payment answers `series: "payment"` with its status and its two dates and
    **not its amount** (`US-CWP-010` TC-7, verbatim: *"⚠ Not the amount — the
    amount is account data"*). Every one of the three is declared as data in
    `guest_fields.py` and read statically by `G92`.
    """
    typed = str(reference or "").strip()
    if not typed:
        return None

    # ⚠ **TWO LOOKUPS AGAIN SINCE 2026-09-05, AND THE SECOND IS A DIFFERENT
    # MODULE RATHER THAN A SECOND TABLE IN THE SAME ONE.** `CR-072` took this
    # down to one — the `RP-` series moved onto `service_requests` — and wave R
    # put the `PAY-` series back, which is `TRACKABLE_SERIES`'s expired hold.
    #
    # **THE REQUEST IS ASKED FIRST AND THE ORDER IS NOT ARBITRARY.** A request
    # number and a payment number come off different tenant series and cannot
    # collide today; asking the series that has been answering since wave B
    # first means the payment branch can only ever ADD an answer where there
    # was `None`, so nothing that worked yesterday can move. A miss on both is
    # the SAME `None` an unknown reference has always returned (`TC-3`).
    request = customers_seam.request_by_number(tenant_id, typed)
    if request is None:
        return _tracked_payment(tenant_id, reference=typed, second_fact=second_fact)

    if not _second_fact_fits(request, second_fact):
        return None

    if not customers_seam.is_report(request):
        return customers_seam.request_progress_view(request)

    # A report shows the CONFIRMED interruption's progress when a clerk has
    # opened one — that is the record a crew moves, and the reason many reports
    # may point at one (`CR-072` §4).
    confirmed = (
        metering_seam.progress_of(tenant_id, request.interruption_id)
        if request.interruption_id is not None
        else None
    )
    return customers_seam.report_progress_view(
        request,
        status=report_progress_status(
            request, None if confirmed is None else confirmed["status"]
        ),
        expected_back_on=None if confirmed is None else confirmed["expected_back_on"],
    )




# ═══════════════════════════════════════════════════════════════════════════
# THE FOUR PORTAL LISTS THAT TAKE THEIR PAGE ON THE SERVER — `DEF-CWP-5747`
#
# ⚠ **READ `apps/portal/paging.SQL_PAGED` BEFORE CHANGING ANY OF THESE.** It
# records which portal lists take the page in SQL and which take it in Python
# ON THE SERVER, and why each of these four is the second kind: every one has a
# predicate over a DERIVED figure — a bill's `owing`, a bounce's pairing, an
# account's live balance, a document queue that may be unreachable — and
# re-spelling those in SQL would be a second implementation of a derivation the
# product already has one of (`DEF-387`, `DEF-RAT-5742`).
#
# ⚠ **WHAT MOVED IS STILL THE WHOLE FIX.** The defect is that the BROWSER held
# every row and searched, chipped, sorted and sliced it. All four now happen on
# the server over the whole ordered set, and ONE PAGE crosses the wire — so a
# customer typing a bill number that is on page 7 finds it, which a server page
# under a browser search could not do.
#
# ⚠ **EACH SEARCH LOOKS AT THE ROW'S OWN DATA, AND THE SCREEN RESOLVES ITS OWN
# WORDS.** A customer typing *August* is reading a month name the BROWSER
# rendered in the BROWSER's language, and a server that tried to match it would
# have to own eleven catalogues (B14 rule 35 forbids it owning even one). So
# the screen turns a word it drew into a code the server knows — `f.month`,
# `f.group` — and `q` matches numbers, ISO dates and codes. Stated here once
# because it is the same answer on every list below.
# ═══════════════════════════════════════════════════════════════════════════


def _has(row: dict[str, Any], keys: tuple[str, ...], needle: str) -> bool:
    """Does any of these fields CONTAIN the needle, case-insensitively — the
    browser's own `[a, b].some((v) => (v ?? "").toLowerCase().includes(n))`,
    moved rather than changed."""
    for key in keys:
        value = row.get(key)
        if value is not None and needle in str(value).lower():
            return True
    return False


# ── `CWP-027` bills ────────────────────────────────────────────────────────

#: What a typed string looks at — the fields a customer can SEE (B14 rule 31:
#: never an id, and this row carries none). The two dates whose columns have
#: gone stay in the predicate: they are printed on the paper the customer is
#: holding, so typing one is a reasonable thing to do.
BILL_SEARCH_FIELDS = ("number", "issued_on", "due_on", "period_start", "period_end")
#: `?sort=` — the three sortable headings `bills/Bills.tsx` draws, and nothing
#: else. A sort the screen cannot ask for is surface with no caller.
BILL_SORTS: dict[str, Any] = {
    "bill": lambda row: row.get("number"),
    "covers": lambda row: row.get("period_start"),
    #: A NUMBER, so `$9` sorts below `$10` — the browser's `Number(bill.total)`.
    "amount": lambda row: _as_number(row.get("total")),
}
BILL_DEFAULT_SORT = None
#: `?f.<name>=` — the toolbar's chips, plus the two the SCREEN resolves out of
#: a month name it drew in the reader's own language.
#: ⚠ **THE TOOLBAR HAS ONE CHIP CONTROL, SO ITS TWO OPTIONS ARE ONE FILTER.**
#: `SegmentedChoice` holds a single chosen key — *All | Unpaid | This year* —
#: and two filter names could not express *This year* without also being able
#: to express *neither*, which the control cannot say.
BILL_STATE_UNPAID = "unpaid"
BILL_STATE_THIS_YEAR = "this_year"
#: `?f.<name>=` — the chip, plus the two the SCREEN resolves out of a month
#: name it drew in the reader's own language (see the section header above).
BILL_FILTER_NAMES = ("state", "year", "month")


def _bill_filters(today: date) -> dict[str, Any]:
    """`BILL_FILTER_NAMES`' predicates. `today` is a PARAMETER and never a clock
    read in here (`BR-TEN-043`), so *This year* is the request's own year and a
    test can state the day."""
    return {
        "state": lambda row, value: (
            #: ⚠ **OWING DRIVES *Unpaid*, NOT THE STATE WORD** — a part-paid
            #: bill is unpaid to the person who still owes on it, and
            #: `BR-CWP-043` is why owing is its own column at all.
            (_as_number(row.get("owing")) or 0) > 0
            if value == BILL_STATE_UNPAID
            else (row.get("issued_on") or "").startswith(str(today.year))
            if value == BILL_STATE_THIS_YEAR
            else True
        ),
        #: The year half of a typed *August 2026*.
        "year": lambda row, value: (row.get("issued_on") or "").startswith(value),
        #: The month half. `08`, never *August*: the word is the browser's.
        "month": lambda row, value: (row.get("issued_on") or "")[5:7] == value,
    }


def _as_number(value: Any) -> float | None:
    """A money string as a number for SORTING ONLY. ⚠ **NOTHING HERE IS
    ARITHMETIC ON MONEY** (hard rule 2): the figure is never written back, never
    rounded and never displayed from this — it exists so that `9.00` sorts below
    `10.00` instead of above it, which is what string order would do."""
    if value is None or value == "":
        return None
    try:
        return float(str(value))
    except ValueError:
        return None


def bills_page(
    account_ids: list[Any], *, today: date, params: Any
) -> tuple[dict[str, Any], int]:
    """`CWP-027` — ONE PAGE of bills, searched, chipped and sorted on the
    server (`DEF-CWP-5747`, `NFR-3`).

    Answers `({"bills": [...one page...], "oldest_on": …, "any_owing": …},
    count)`.

    ⚠ **THE ROWS ARE `billing_seam.bills_for`'S, UNCHANGED.** No figure moves
    (hard rule 2), `owing` still comes from `payments.open_bill_position` and
    never from subtraction (`BR-CWP-043`), and a corrected bill is still listed
    with its replacement (`BR-CWP-042`). What changed is that the search, the
    chips, the sort and the slice happen HERE instead of in a browser holding
    every bill the customer has ever had.

    ⚠ **THE TWO WHOLE-SET FACTS ARE SERVED BECAUSE THE SCREEN CAN NO LONGER
    COMPUTE THEM, AND THAT IS THE HALF-FIX TRAP IN MINIATURE.** `Bills.tsx`
    read both off the array it held: the OLDEST bill, for the drawing's *"Every
    bill since you started, Jun 2026 · 3 bills"*, and whether ANYTHING is owed,
    which is what decides the *Pay* control. Over a page the first would say
    *since Aug 2026* on page 1 of eleven years, and the second would HIDE the
    Pay button from a customer whose only unpaid bill was on page 2. Neither is
    arithmetic on money: `oldest_on` is a string comparison over ISO dates and
    `any_owing` is the same `> 0` comparison the *Unpaid* chip makes,
    deliberately the same so the button and the chip cannot disagree.
    """
    from apps.portal.seams import billing_seam

    rows = billing_seam.bills_for(account_ids, today=today)
    issued = [row["issued_on"] for row in rows if row.get("issued_on")]
    page, total = paging.on_the_server(
        rows,
        params,
        search=lambda row, needle: _has(row, BILL_SEARCH_FIELDS, needle),
        sorts=BILL_SORTS,
        filters=_bill_filters(today),
    )
    return (
        {
            "bills": page,
            "oldest_on": min(issued) if issued else None,
            "any_owing": any((_as_number(row.get("owing")) or 0) > 0 for row in rows),
            #: Whether this customer has ANY bills at all, which `count` cannot
            #: say: `count` is the MATCHING set, so a search that finds nothing
            #: would otherwise render *you have no bills* at a customer with
            #: eleven months of them.
            "populated": bool(rows),
        },
        total,
    )


# ── `CWP-031` documents ────────────────────────────────────────────────────

DOCUMENT_SEARCH_FIELDS = ("reference", "sent_on", "queued_on", "period_start", "period_end")
DOCUMENT_SORTS: dict[str, Any] = {
    "document": lambda row: row.get("reference"),
    #: The screen sorts this column on the GROUP's translated word; the code is
    #: the same ordering within one language and is the only thing a server may
    #: sort on (B14 rule 35).
    "kind": lambda row: row.get("group"),
    #: `sent_on` is null on everything this deployment has written, so the
    #: screen's own `sent_on ?? queued_on` is the key here too.
    "sent": lambda row: row.get("sent_on") or row.get("queued_on"),
}
DOCUMENT_FILTERS: dict[str, Any] = {
    #: The three chips — `bill` · `receipt` · `letter` — and the code the
    #: SCREEN resolves out of the translated word a customer typed.
    "group": lambda row, value: row.get("group") == value,
    "kind": lambda row, value: row.get("kind") == value,
}


def documents_page(account: Any, *, params: Any) -> tuple[dict[str, Any], int]:
    """`CWP-031` — ONE PAGE of what we sent, searched and sorted on the server.

    Answers `(body, count)` where `body` carries `documents`, `groups` and
    `unavailable`, because **`documents: null` is not an empty page**: null
    means the queue could not be asked and `[]` means it was asked and this
    account has nothing. A screen drawing one empty state over both would tell
    a customer of eleven months that we never wrote to them — so the two travel
    separately here rather than being flattened into a count of zero.
    """
    body = documents(account)
    if body["documents"] is None:
        return {**body, "populated": False, "any_kept": False}, 0
    everything = body["documents"]
    rows, total = paging.on_the_server(
        everything,
        params,
        search=lambda row, needle: _has(row, DOCUMENT_SEARCH_FIELDS, needle),
        sorts=DOCUMENT_SORTS,
        filters=DOCUMENT_FILTERS,
    )
    #: ⚠ **`count` CANNOT SAY *HAS THIS CUSTOMER ANY POST AT ALL*.** It is the
    #: MATCHING set, so a chip that matches nothing would otherwise render *we
    #: have not written to you* at a customer of eleven months (`BR-CWP-083`'s
    #: screen already distinguishes three states and this is the fourth).
    #:
    #: ⚠ **AND `any_kept` IS THE HOLD ON `CPB-15`'s *Download a year*, WHICH
    #: THE SCREEN COUNTED OFF THE ARRAY IT HELD.** The control is held the
    #: moment there is nothing kept to send, because an archive of nothing
    #: downloads an empty file and looks like the product working. Counted off
    #: a PAGE it would hold the button on page 2 of a customer whose kept
    #: documents are all on page 1 — a refusal that is simply false, which is
    #: hard-won law 2's mirror wearing a page number.
    return (
        {
            **body,
            "documents": rows,
            "populated": bool(everything),
            "any_kept": any(
                (row.get("stored_document") or {}).get("available") for row in everything
            ),
        },
        total,
    )


# ── `CWP-041` payments ─────────────────────────────────────────────────────

MONEY_SEARCH_FIELDS = ("date", "reference", "receipt_reference", "how")
MONEY_SORTS: dict[str, Any] = {
    "date": lambda row: row.get("date"),
    "amount": lambda row: _as_number(row.get("amount")),
}
MONEY_FILTERS: dict[str, Any] = {}


def money_page(
    account_ids: list[Any], *, year: int | None, params: Any
) -> tuple[dict[str, Any], int]:
    """`CWP-041` — ONE PAGE of everything that moved money on this login.

    ⚠ **THE PAIRING IS DONE BEFORE ANYTHING IS SLICED, AND THAT ORDER IS THE
    WHOLE REASON THIS LIST IS NOT PAGED IN SQL.** `BR-CWP-061` puts a reversal
    *directly above* the payment it undoes, anchored at the reversal's date;
    `payments_seam.money_list` builds that adjacency over the whole list. A
    `LIMIT` in SQL would be free to cut between the two rows, and a customer
    would be shown *returned by the bank · −$129.02* at the bottom of page 2
    with the `$129.02` it undoes at the top of page 3.

    ⚠ **THE SORT IS STABLE, SO A SORT CANNOT SEPARATE THEM EITHER** where the
    key cannot tell the pair apart — which is `paging.on_the_server`'s own note,
    and it is the reason it uses `sorted` rather than re-ordering in place.

    ⚠ **`year` STAYS A SERVER PARAMETER AND IS NOT A CHIP PREDICATE.** It is
    already applied by `money_list` before the pairing, so the rows that arrive
    are the answer; narrowing them again here would be the same rows filtered
    twice.
    """
    from apps.portal.seams import payments_seam

    rows = payments_seam.money_list(account_ids, year=year)
    rows = receipts_that_exist(rows, account_ids=account_ids)
    page, total = paging.on_the_server(
        rows,
        params,
        search=lambda row, needle: _has(row, MONEY_SEARCH_FIELDS, needle),
        sorts=MONEY_SORTS,
        filters=MONEY_FILTERS,
    )
    #: ⚠ **`populated` IS *ANY MONEY IN THIS YEAR*, WHICH IS WHAT THE SCREEN
    #: ASKS.** The year is the server's filter and is applied before this, so a
    #: customer who chose *This year* and paid nothing in it still gets the
    #: empty sentence rather than *none of your payments says that*.
    return {"money": page, "populated": bool(rows)}, total


# ── `CWP-023` my accounts ──────────────────────────────────────────────────

MY_ACCOUNT_SEARCH_FIELDS = ("account_no", "service_address")
MY_ACCOUNT_SORTS: dict[str, Any] = {
    "address": lambda row: row.get("service_address"),
    "due": lambda row: row.get("due_on"),
    "balance": lambda row: _as_number(row.get("owing")),
}
MY_ACCOUNT_FILTERS: dict[str, Any] = {
    #: The one chip the screen draws, and it appears only where there is more
    #: than one account — one account has nothing to narrow.
    "state": lambda row, value: row.get("state") != "clear" if value == "owing" else True,
}


def my_accounts_page(principal: Any, *, today: Any, params: Any) -> tuple[dict[str, Any], int]:
    """`CWP-023` — ONE PAGE of the landlord's accounts, with the total intact.

    Answers `(body, count)`: the rows are a page and **`total_owing`,
    `account_count` and `show_total` are the WHOLE SET's**, because
    `BR-CWP-015` says four rows and `$872.82` — a total of the page would be a
    different number on page 2, which is a figure a customer could reasonably
    believe and act on.

    ⚠ **THE SEARCH ALSO LOOKS AT THE SERVICE WORDS, WHICH ARE THE TENANT'S OWN
    DATA AND NOT A CATALOGUE'S.** The utility names its own services in
    Settings, so *Water* here is whatever THEY call it, in whatever language
    they wrote it — matching it on the server is reading their data, not
    translating ours (B14 rule 35 in the other direction).

    ⚠ **`BR-CWP-016` IS UNTOUCHED AND CANNOT BE WEAKENED BY A FILTER MOVING.**
    Every row is built from `principal.accounts`, which is the session's own
    flat set re-derived on this read; there is no query here for a widened
    scope to reach, and a landlord still has no path to a tenant's balance.
    """
    body = my_accounts(principal, today=today)

    def matches(row: dict[str, Any], needle: str) -> bool:
        if _has(row, MY_ACCOUNT_SEARCH_FIELDS, needle):
            return True
        return any(needle in str(one.get("name") or "").lower() for one in row.get("services") or ())

    rows, total = paging.on_the_server(
        body["accounts"],
        params,
        search=matches,
        sorts=MY_ACCOUNT_SORTS,
        filters=MY_ACCOUNT_FILTERS,
    )
    return {**body, "accounts": rows}, total

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-001@87b94265 · US-CWP-069@87b94265 · US-CWP-070@87b94265 · US-CWP-010 TC-7 + US-CWP-005 TC-3 (the payment series, 2026-09-05)
# generated: 2026-09-03 by the CR-068 wave A build lane · AMENDED 2026-09-05 by the CR-068 ending lane (the `PAY-` series joins `TRACKABLE_SERIES`; `payment_progress_view` and `_tracked_payment` are new; the hold's own comment says what it used to say and why the reason is spent)
# checklist: A✔ B✔ C✔ D✔(guest_api.py · backoffice_api.py) E✔(portal/guest/FrontPage.tsx · SettingsCustomerPortalTab.tsx · TrackAnything.tsx + QuickPayDone.tsx for the payment kind) F✔ G✔ H=n/a(read side)
# gates: pytest tests/test_us_cwp_001_front.py tests/test_us_cwp_069_settings.py tests/test_us_cwp_070_branding.py tests/test_us_cwp_005_receipt.py tests/test_us_cwp_010_track.py · G81 (no write here) · G92 (payment_progress_view is declared in guest_fields.py)
# exceptions: enrolled / signed-in counts are ABSENT, not zero, until wave E's tables exist — stated in `usage()` and in the decision log · a tracked payment carries NO amount (US-CWP-010 TC-7) where the receipt does, and both docstrings say why
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave C — what CWP-010 and CWP-047 read
# ═══════════════════════════════════════════════════════════════════════════

#: The six cards `US-CWP-015` §4 names, as the DEFAULT a new tenant is seeded
#: with. It is a seed and not a constant: the cards a visitor is offered are
#: read from `portal_settings.quick_service_categories`, so a utility that
#: renames one sees the new label (TC-7) and a card only Oak Ridge configured is
#: not offered on Pine Hill (TC-6).
#:
#: ⚠ **`label` AND `hint` ARE CATALOGUE KEYS, NOT SENTENCES**, so the six read
#: in the visitor's own language (B14 rule 35). A utility that edits a label
#: replaces the key with its own words, and the screen shows those verbatim —
#: which is right: a utility's own wording is not ours to translate.
DEFAULT_QUICK_SERVICES: tuple[dict[str, Any], ...] = (
    {"code": "re_read", "label": "portal.quick.re_read.title", "hint": "portal.quick.re_read.hint", "needs_bill_number": False},
    {"code": "missed_collection", "label": "portal.quick.missed_collection.title", "hint": "portal.quick.missed_collection.hint", "needs_bill_number": False},
    {"code": "copy_of_bill", "label": "portal.quick.copy_of_bill.title", "hint": "portal.quick.copy_of_bill.hint", "needs_bill_number": False},
    {"code": "low_pressure", "label": "portal.quick.low_pressure.title", "hint": None, "needs_bill_number": False},
    {"code": "bill_question", "label": "portal.quick.bill_question.title", "hint": "portal.quick.bill_question.hint", "needs_bill_number": True},
    {"code": "other", "label": "portal.quick.other.title", "hint": None, "needs_bill_number": False},
)


def quick_service_categories(tenant_id: Any) -> list[dict[str, Any]]:
    """`GET /portal/public/quick-services` — the cards CWP-010 draws.

    ⚠ **NOT A HARDCODED LIST** (`US-CWP-015` §5, verbatim: *"⚠ **Tenant-
    configurable.** Never a hardcoded list"*). The rows come off the utility's
    own settings row; `DEFAULT_QUICK_SERVICES` is what a tenant is SEEDED with
    and is used only when the row has never been configured — the same posture
    `settings_view` takes with the R8 switch defaults, and for the same reason:
    a read never writes.

    ⚠ **AND THE WHOLE SECTION IS ABSENT WHEN THE UTILITY HAS SWITCHED REQUESTS
    OFF** (`US-CWP-015` TC-4: *the cards are absent AND `POST /public/requests`
    refuses*). Absent, not greyed — `BR-CWP-093`, *nothing empty ever appears*.
    """
    settings = settings_view(tenant_id)
    if not settings["is_live"] or not settings["requests_enabled"]:
        return []
    configured = settings.get("quick_service_categories") or []
    rows = configured if configured else list(DEFAULT_QUICK_SERVICES)
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("code"):
            continue
        out.append(
            {
                "code": str(row["code"]),
                "label": row.get("label"),
                "hint": row.get("hint"),
                "needs_bill_number": bool(row.get("needs_bill_number")),
            }
        )
    return out


def quick_service_category(tenant_id: Any, code: Any) -> dict[str, Any] | None:
    """The one card this code names, or None — the check `POST /public/requests`
    makes before it writes anything, so a caller cannot invent a category the
    utility does not offer (`US-CWP-015` TC-6)."""
    wanted = str(code or "")
    for row in quick_service_categories(tenant_id):
        if row["code"] == wanted:
            return row
    return None


def us_address_line(
    line: Any, unit: Any = None, city: Any = None, state: Any = None, postal_code: Any = None
) -> str:
    """ONE address written the way a US envelope reads it — `DEF-CWP-9817`.

        1841 Quarry Hill Ct, Apt 12, Silver Creek, TX 78611

    Street, the unit, the town, then the state and ZIP together; an empty part
    is left out rather than shown as a gap. **The unit is the applicant's label
    as typed** (hard rule 8: a unit refines a premises by LABEL) — except that a
    bare number or letter (`12`, `2B`) gains USPS's `#`, because
    `…Hill Ct, 12, Silver Creek` reads as a second house number (decision log
    2026-10-06). One function, so the head, the rail, Check and send and Track
    cannot write the same address four ways.
    """
    unit_text = str(unit or "").strip()
    if unit_text and " " not in unit_text and any(ch.isdigit() for ch in unit_text[:1]):
        unit_text = f"#{unit_text}"
    tail = " ".join(part for part in [str(state or "").strip(), str(postal_code or "").strip()] if part)
    return ", ".join(
        part
        for part in [str(line or "").strip(), unit_text, str(city or "").strip(), tail]
        if part
    )


def draft_service_state(row: Any) -> str | None:
    """The STATE `draft_service_address` shows — `DEF-CWP-10541`.

    The matched premises' state when the draft holds one, else the utility's
    own (`tenancy_seam.utility_state`), else None. Read by `_application` so
    the request carries the state the applicant saw on Check and send, and
    the acknowledgement's address reads as the screen did. One source for both.
    """
    if row.matched_premises_id:
        held = metering_seam.premises_by_id(row.tenant_id, row.matched_premises_id)
        if held is not None and held.get("state"):
            return held["state"]
    return tenancy_seam.utility_state(row.tenant_id)


def draft_service_address(row: Any) -> str | None:
    """What every step after step 1 SHOWS as the service address — `DEF-CWP-9817`.

    `BR-CUS-1091` (PO 2026-09-22): the typed parts exist to FIND the premises,
    and once one is found **the premises is what every screen shows**. So: the
    MATCHED premises' own address when the draft has one, and only otherwise the
    parts the applicant typed, with the utility's own state (the portal asks
    none). The unit is the applicant's label either way — it refines the
    premises; it is never part of the premises' address.
    """
    typed = (row.address_as_given or "").strip()
    if not typed:
        return None
    unit = row.address_unit_as_given
    if row.matched_premises_id:
        held = metering_seam.premises_by_id(row.tenant_id, row.matched_premises_id)
        if held is not None:
            return us_address_line(
                held["address_line"], unit, held["city"], held["state"], held["postal_code"]
            )
    if not (row.address_city_as_given or row.address_postal_code_as_given):
        # A draft from before step 1 asked the parts: one box, shown as typed.
        return us_address_line(typed, unit)
    return us_address_line(
        typed,
        unit,
        row.address_city_as_given,
        tenancy_seam.utility_state(row.tenant_id),
        row.address_postal_code_as_given,
    )


def draft_view(row: Any) -> dict[str, Any]:
    """A draft as `CWP-047` reads it back after a closed tab (`US-CWP-013`
    TC-1).

    ⚠ **NO REFERENCE UNTIL IT HAS BEEN SENT.** `reference` is present only once
    `submitted_at` is, which is *"no promise has been made"* written as a
    payload rather than as a sentence on a screen.

    ⚠ **AND NO PREMISES ID.** The draft holds one (evidence a clerk uses); the
    guest never sees it, for the reason `availability.py` gives at length.
    """
    # Imported here, not at module scope: `applications` imports
    # `availability`, which reads this module.
    from apps.portal import applications

    submitted = row.submitted_at is not None
    return {
        "token": row.token,
        "address_as_given": row.address_as_given,
        "address_unit_as_given": row.address_unit_as_given,
        # DEF-CWP-9817 — the parts as typed, and the ONE line every later
        # step shows (the matched premises' address, or the typed parts).
        "address_city_as_given": row.address_city_as_given,
        "address_postal_code_as_given": row.address_postal_code_as_given,
        "service_address": draft_service_address(row),
        # DEF-CWP-9818 — the applicant's category pick, as codes.
        "account_type_code": row.account_type_code,
        "account_subtype_code": row.account_subtype_code,
        # ...and the list step 3 offers: Settings › Account types' OFFERED
        # categories with their live sub-categories, codes and names only —
        # the same list the clerk picks from (`offered_categories`).
        "categories": customers_seam.offered_categories(row.tenant_id),
        "service_codes": list(row.service_codes or []),
        "applicant_kind": row.applicant_kind,
        "first_name": row.first_name,
        "last_name": row.last_name,
        "company_name": row.company_name,
        "email": row.email,
        "phone": row.phone,
        "date_of_birth": row.date_of_birth.isoformat() if row.date_of_birth else None,
        "tax_id": row.tax_id,
        "requested_start": row.requested_start.isoformat() if row.requested_start else None,
        # DEF-CUS-10225 — Move-in's fields (portal/0016). The SSN last four is
        # the applicant's OWN typing, read back only to whoever holds the link,
        # and it is gone from the draft once sent.
        "contact_by": row.contact_by,
        "ssn_last4": row.ssn_last4,
        "co_applicant": bool(row.co_applicant),
        "co_applicant_name": row.co_applicant_name,
        "co_applicant_relationship": row.co_applicant_relationship,
        "co_applicant_phone": row.co_applicant_phone,
        "co_applicant_email": row.co_applicant_email,
        "co_applicant_date_of_birth": (
            row.co_applicant_date_of_birth.isoformat() if row.co_applicant_date_of_birth else None
        ),
        "paperless": row.paperless,
        "text_reminders": row.text_reminders,
        "preferred_language": row.preferred_language,
        # ...and the languages the Preferences panel offers — the portal's one
        # offer (`PORTAL_LOCALES`), the same list the top-menu picker reads.
        "locales": list(PORTAL_LOCALES),
        # DEF-CWP-9163 — *"Mailing address, if different"*. The five parts are
        # the applicant's own words; `true` means the bill goes to the service
        # address and the five are not read.
        "mailing_same_as_service": bool(row.mailing_same_as_service),
        **{field: getattr(row, field) for field in applications.MAILING_FIELDS},
        "submitted": submitted,
        "reference": (
            customers_seam.request_reference(row.service_request_id) if submitted else None
        ),
        # CR-158-BRC10 — the files attached so far: name, type, size, when.
        # Never the bytes. Empty once sent, because the files went with it.
        "documents": applications.documents_of(row),
        "document_limits": {
            "types": list(applications.DOCUMENT_TYPES),
            "max_bytes": applications.MAX_DOCUMENT_BYTES,
            "max_files": applications.MAX_DOCUMENTS,
        },
        # DEF-CWP-9167 — the documents asked for, in order: one attach row each
        # on step 3 and one status line each on Check and send. The screen
        # draws exactly these and never a list of its own.
        "document_requirements": list(applications.DOCUMENT_REQUIREMENTS),
        # `CR-161-BRC10` W7 — the utility's own questions, per record type: ONLY
        # the fields switched to *Ask the customer*, told only what drawing the
        # box needs (`custom_fields.PORTAL_PUBLIC_KEYS`), and the applicant's
        # answers to exactly those. A field switched to *Don't ask* since is
        # neither served nor read back. The screen draws these and no list of
        # its own.
        "custom_fields": tenancy_seam.application_custom_fields(row.tenant_id),
        "custom_data": tenancy_seam.application_custom_answers(row.tenant_id, row.custom_data),
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave F · `CWP-023` — all my accounts (US-CWP-026)
#
# ⚠ **UNBLOCKED 2026-09-04.** `OQ-1397` — *does a landlord see a tenant's
# bill?* — was answered **no** (PO: *"(a) no"*), which is exactly how this
# screen was already drawn. `BR-CWP-016` is CONFIRMED and the flat set is not
# a temporary safety posture any more; it is the product.
# ═══════════════════════════════════════════════════════════════════════════


def service_address(account: Any) -> str | None:
    """`1408 Elm St · A` — walked to `premises`, never stored on the account.

    CLAUDE.md hard rule 8: *"an address is stored on `premises` and NOWHERE
    else … every other entity derives it by walking to the premises."* A unit
    refines it by LABEL, which is the ` · A`.

    ⚠ **MOVED HERE FROM `api.py` BY WAVE F, AND THE MOVE IS THE POINT.** Two
    screens now need the same walk, and hard rule 8's whole value is that there
    is ONE place a service address is composed. A second copy in a second file
    is how `DEF-CUS-3653` happened: a header composed a locality from a column
    that had been retired, and nothing could see it because the absence was
    invisible to every check this repo has.
    """
    from apps.metering import models as metering_models

    unit = account.unit
    premises_id = account.premises_id or getattr(unit, "premises_id", None)
    premises = (
        metering_models.Premises.objects.filter(
            # `BR-CWP-010` — the tenant is IN THE QUERY, not left to RLS alone
            # (`G96`, `DEF-CWP-3775`). The suite runs on SQLite, which has no
            # row-level security, so the database's guarantee is invisible to
            # every test here.
            tenant_id=account.tenant_id,
            pk=premises_id,
        )
        .only("address_line")
        .first()
        if premises_id
        else None
    )
    line = getattr(premises, "address_line", None)
    if line is None:
        return None
    label = getattr(unit, "label", None)
    return f"{line} · {label}" if label else line


def services_of(account: Any) -> list[str]:
    """The services this account is billed for, by CODE — Water · Sewer · Trash.

    Read off the unit's own service agreements through metering's rows; the
    SCREEN turns a code into a word in the reader's language, because a server
    that returned *"Water"* would ship English to eleven catalogues (B14 r35).
    """
    from apps.metering import models as metering_models

    unit_id = account.unit_id
    if unit_id is None:
        return []
    return sorted(
        {
            str(code)
            for code in metering_models.ServicePoint.objects.filter(
                tenant_id=account.tenant_id, unit_id=unit_id  # G96 — see above
            )
            .values_list("service__code", flat=True)
            if code
        }
    )


#: The three states `CWP-023`'s status column can read, and nothing else.
#: They are STATES, not sentences: the screen writes the words in the reader's
#: own language (B14 rule 35), and *19 days overdue* is composed there from
#: `days_overdue` rather than shipped as English from a server.
ACCOUNT_STATE_CLEAR = "clear"
ACCOUNT_STATE_DUE = "due"
ACCOUNT_STATE_OVERDUE = "overdue"


def _account_state(owing: Any, due_on: Any, today: Any) -> tuple[str, int | None]:
    """`(state, days_overdue)` from what is owed and when it was due.

    ⚠ **NOTHING OWED IS `clear`, WHATEVER THE DATE SAYS.** An account with a
    due date in the past and a zero balance is settled, not overdue — reading
    the date first would paint a paid-up landlord's row red.
    """
    from decimal import Decimal

    if Decimal(str(owing or "0")) <= 0:
        return ACCOUNT_STATE_CLEAR, None
    if due_on is None:
        return ACCOUNT_STATE_DUE, None
    overdue_by = (today - due_on).days
    if overdue_by > 0:
        return ACCOUNT_STATE_OVERDUE, overdue_by
    return ACCOUNT_STATE_DUE, None


def my_accounts(principal: Any, *, today: Any) -> dict[str, Any]:
    """`CWP-023` — every account this login holds, with a total (`US-CWP-026`).

    ⚠ **FLAT, AND TOTALLED WITHOUT BEING MERGED** (`BR-CWP-013`, `BR-CWP-015`).
    Four rows and `$872.82`; there is no field in this body that could be paid
    as one amount, and the master account is one more row rather than a parent
    with children — what makes it different is that it is BILLED TO THE
    LANDLORD, which is a billing fact and not a permission (`BR-CWP-014`).

    ⚠ **`show_total` IS FALSE FOR A HOUSEHOLDER, AND THAT IS A RULE RATHER THAN
    A TIDINESS PREFERENCE** (`US-CWP-026` TC-5): a total of one number is noise,
    and a screen that draws a `$142.18` row above a `$142.18` total invites the
    reading that the customer owes `$284.36`.

    ⚠ **THE TENANTS' OWN ACCOUNTS ARE NOT HERE AND CANNOT BE** (`BR-CWP-016`,
    ruled 2026-09-04): every row comes from `principal.accounts`, which is the
    session's set, and the set is re-derived from the customer's own links. A
    landlord holding the master over `1408 Elm St` has no path to `· A`'s
    tenant's balance through this read or any other.

    `today` is a PARAMETER and never a clock read in here (`BR-TEN-043`) — the
    caller holds the request's own date, so a test can state the day.
    """
    from apps.customers import models as customers_models
    from apps.portal.seams import payments_seam

    account_ids = list(principal.account_ids)
    accounts = {
        str(row.pk): row
        for row in customers_models.Account.objects.filter(
            tenant_id=principal.tenant_id, pk__in=account_ids
        ).select_related("unit")
    }
    summary = payments_seam.balance_summary(account_ids, as_of=today)
    balances = {row["account_id"]: row for row in summary["accounts"]}
    #: ⚠ **A SERVICE'S WORD COMES FROM THE TENANT, NOT FROM A CATALOGUE.** The
    #: front page already words its chips this way (`selectors.front`): the
    #: utility names its own services in Settings, so *Water* here is whatever
    #: THEY call it, in whatever language they wrote it. Shipping a code and
    #: translating it in eleven catalogues would overwrite the utility's own
    #: word with ours (B14 rule 35 in the other direction).
    named = {row["code"]: row["name"] for row in tenancy_seam.enabled_services(principal.tenant_id)}

    rows: list[dict[str, Any]] = []
    for entry in principal.accounts:
        account = accounts.get(entry.account_id)
        if account is None:
            continue
        balance = balances.get(entry.account_id, {})
        due_iso = balance.get("due_on")
        due_on = _iso_to_date(due_iso)
        state, days_overdue = _account_state(balance.get("owing"), due_on, today)
        rows.append(
            {
                "id": entry.account_id,
                "account_no": account.account_no,
                "service_address": service_address(account),
                "services": [
                    {"code": code, "name": named.get(code, code)}
                    for code in services_of(account)
                ],
                "owing": balance.get("owing"),
                "currency": balance.get("currency"),
                "due_on": due_iso,
                "state": state,
                "days_overdue": days_overdue,
                #: `BR-CWP-014` — the two labels the row reads, as a FACT the
                #: screen words rather than a sentence a server ships in English.
                #:
                #: ⚠ **BOTH READ `kind`, WHICH IS THE COLUMN, NOT THE SHAPE.**
                #: `create_master_account` is the only door to `kind='master'`
                #: and every other account path REFUSES the field, so it is
                #: exact. The tempting proxy — *a master has a premises and no
                #: unit* — is only true for rows created after migration
                #: `customers/0036` and is `DEF-CWP-3765`.
                "billed_to": (
                    "owner"
                    if account.kind == customers_seam.ACCOUNT_KIND_MASTER
                    else "tenant"
                ),
                "is_master": account.kind == customers_seam.ACCOUNT_KIND_MASTER,
            }
        )

    return {
        "as_of": today.isoformat(),
        "accounts": rows,
        "account_count": len(rows),
        "total_owing": summary["total_owing"],
        "currency": summary["currency"],
        "show_total": len(rows) > 1,
        "problems": summary["problems"],
    }


def _iso_to_date(value: Any):
    """`'2026-09-14'` → a date, and anything else → None."""
    from datetime import date as _date

    if value is None:
        return None
    try:
        return _date.fromisoformat(str(value))
    except ValueError:
        return None


def common_area_reconciliation(account_id: Any) -> dict[str, Any]:
    """`CP-54` — the master meter against the sum of its sub-meters.

    ⚠ **STILL UNBUILT, AND NO LONGER FOR `OQ-1397`'s REASON.** That question
    asked whether a landlord may see a TENANT'S BILL and was answered **no** on
    2026-09-04; this read is not a tenant's bill and is not settled by it. What
    stops it is `US-CWP-026` §7: the reconciliation arithmetic is **PROPOSED,
    not finance-signed** — *"the difference the landlord is billed for"* is a
    money figure that decides what somebody pays, and B4's own rule is that a
    lane implements signed law and never invents it.

    ⚠ **THE ACCESS LINE IS DECIDED AND RECORDED SO NOBODY RE-ASKS IT** (law 13,
    decision log 2026-09-04): when this is built, the landlord sees the master
    read, the AGGREGATE of the sub-meters, and the difference they are billed
    for — and **never a per-tenant figure**, because a per-unit consumption
    line is the tenant's business and reads across `BR-CWP-016`. The aggregate
    is what makes the landlord's own bill explicable; the breakdown is not.
    """
    raise NotImplementedError(
        "the common-area reconciliation arithmetic is not finance-signed "
        "(US-CWP-026 section 7); the access line is decided and recorded"
    )


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave F · `CWP-065` — your account (US-CWP-031)
# ═══════════════════════════════════════════════════════════════════════════


def account_summary(tenant_id: Any, account: Any, *, as_of: Any) -> dict[str, Any]:
    """`CWP-065` — the facts about an account that are **not on a bill**.

    Four panels: the deposit we hold, the services and since when, how you are
    billed, and the tax exemption with its expiry.

    ⚠ **THE DEPOSIT IS THE ONE THAT STINGS, AND ITS ABSENCE IS AS IMPORTANT AS
    ITS PRESENCE.** `$150.00` of the customer's money, taken in 2021, visible on
    the day it was quoted and on the day it comes back and invisible for the
    five years between. An account with NO deposit gets **no panel** — not a
    `$0.00`, which reads as *we took nothing from you* rather than *there is
    nothing here* (`US-CWP-031` TC-8).

    ⚠ **AND IT SAYS IT IS NOT MONEY OFF A BILL** (TC-2). A customer who reads a
    held deposit as credit stops paying, and then owes the utility money AND
    still has the deposit. The screen carries that sentence; this read carries
    the flag that makes the screen draw it.

    ⚠ **THE INTEREST IS READ FROM THE SIGNED ENGINE AND MAY COME BACK `None`.**
    `deposit_interest_accrued` answers `None` when it cannot compute — and the
    two callers that settle real money both fail CLOSED on that rather than
    paying principal alone. This screen does the same in its own register: it
    says the interest is not known. **A `None` that became `0.00` here would be
    a figure disagreeing with the customer's own final bill**, which is the
    defect `US-CWP-031` §7 exists to catch.

    ⚠ **NO `credit_tier`, NO `match_tier`, NO `match_basis`** (`BR-CWP-052`).
    They are held back on purpose and the surest guard is that nothing here
    selects them. TC-7 asserts it on the body.
    """
    from apps.portal.seams import rating_seam

    deposit_held = Decimal(str(getattr(account, "deposit_on_file", 0) or 0))
    deposit: dict[str, Any] | None = None
    if deposit_held > 0:
        interest = customers_seam.deposit_interest(account.pk, as_of)
        deposit = {
            "held": str(deposit_held.quantize(Decimal("0.0001"))),
            "taken_on": (
                account.deposit_received_on.isoformat()
                if getattr(account, "deposit_received_on", None)
                else None
            ),
            #: `None` travels as `None`. The screen words it; it is never zero.
            "interest": str(Decimal(interest).quantize(Decimal("0.0001")))
            if interest is not None
            else None,
            "currency": getattr(account, "currency", None),
            #: TC-2 — the sentence a customer needs before they read the number.
            "returns_at_closing": True,
            "is_money_off_a_bill": False,
        }

    exemption: dict[str, Any] | None = None
    if getattr(account, "tax_exempt", False):
        exemption = {
            "until": (
                account.tax_exempt_expires.isoformat()
                if getattr(account, "tax_exempt_expires", None)
                else None
            ),
            #: ⚠ **WHETHER a certificate is on file, never the reference
            #: itself.** The number is the utility's record; what the customer
            #: needs is that it is held and when it runs out.
            "certificate_on_file": bool(getattr(account, "tax_exempt_ref", None)),
            #: `BR-CWP-053` — a message goes out this many days before, so an
            #: exemption never lapses into a bigger bill without warning.
            "reminder_days_before": 30,
            #: The blanket exemption covers every tax; no per-tax list.
            "taxes": [],
        }
    else:
        #: ⚠ **`DEF-CWP-9795` — A CERTIFICATE IS AN EXEMPTION TOO.** Ruling (A)
        #: (2026-10-05) leaves the blanket flag false for a per-tax
        #: certificate, so this block read nothing for M5's church while its
        #: bill dropped the City's tax. One row per live certificate: the tax
        #: it removes and when it runs out — never its number (TC-5).
        taxes = customers_seam.live_tax_exemptions(account.pk)
        if taxes:
            exemption = {
                "until": None,
                "certificate_on_file": True,
                "reminder_days_before": 30,
                "taxes": taxes,
            }

    return {
        "account_id": str(account.pk),
        "opened_on": account.opened_at.isoformat() if getattr(account, "opened_at", None) else None,
        "deposit": deposit,
        "services": customers_seam.services_held(tenant_id, account.pk),
        "billing": (
            rating_seam.plan_history(tenant_id, account.unit_id)
            if getattr(account, "unit_id", None)
            else {"current": None, "before": []}
        ),
        "tax_exemption": exemption,
        #: ⚠ **NO `opened_by`.** `US-CWP-031` §5 asks for a move history from
        #: a `MoveRecord` table that does not exist, and a move-in request
        #: carries no `account_id` to walk back through (`DEF-CWP-3767`).
        #: `opened_on` above is the honest half and is a real column.
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave F · `CWP-022` — the home page (US-CWP-025)
# ═══════════════════════════════════════════════════════════════════════════



#: The home tile's window. Twelve, and it is the Product Owner's own figure —
#: *"last 12 month usage details"* — and the same window the staff Overview
#: panel opens on. The Usage SCREEN offers 12 or 24; a tile offers neither.
HOME_USAGE_MONTHS = 12


def _home_usage_series(
    tenant_id: Any, account_ids: list[Any], *, today: Any = None
) -> list[dict[str, Any]]:
    """Twelve months of stated usage across this login's accounts, oldest first.

    ⚠ **SUMMED ACROSS ACCOUNTS ONLY WITHIN ONE SERVICE AND ONE UNIT.** A
    landlord's four properties all take water in gallons and their months add;
    gallons and therms never do (hard rule 3). The key is
    `(month, service, unit)` and there is no path that drops the last two.

    ⚠ **AN ABSENT MONTH IS NOT A ROW.** `BR-MET-106` serves an unread month as
    `absent: true` with a null quantity, and a tile that rendered it as `0`
    would tell a customer they used nothing. It is skipped here, and the SCREEN
    (`CWP-033`) is where the absence is drawn as a gap in the chart.
    """
    from apps.metering import quantity_display

    buckets: dict[tuple[str, str, str], Decimal] = {}
    estimated: set[tuple[str, str, str]] = set()
    order: list[tuple[str, str, str]] = []
    for account_id in account_ids:
        payload = metering_seam.usage_for_account(
            tenant_id, account_id, months=HOME_USAGE_MONTHS, today=today
        )
        for series in payload.get("series") or ():
            code = (series.get("service") or {}).get("code") or "service"
            for point in series.get("points") or ():
                unit = point.get("unit")
                if point.get("absent") or point.get("quantity") is None or not unit:
                    continue
                key = (point["month"], code, unit)
                if key not in buckets:
                    buckets[key] = Decimal("0")
                    order.append(key)
                buckets[key] += Decimal(point["quantity"])
                if point.get("estimated"):
                    estimated.add(key)
    order.sort()
    return [
        {
            "month": month,
            "service": service,
            "unit": unit,
            "quantity": str(buckets[(month, service, unit)]),
            #: ⚠ **THE DISPLAY STRING IS COMPOSED BY THE SERVER** (`BR-MET-144`,
            #: `DEF-CWP-3770`). The stored figure is `NUMERIC(18,6)`, so a
            #: screen printing `quantity` renders `4820.000000 gal`; two
            #: decimals with trailing zeros trimmed is the ratified display and
            #: composing it once here is what stops two screens disagreeing.
            "quantity_display": quantity_display.quantity_text(
                buckets[(month, service, unit)]
            ),
            #: `BR-MET-106` — *estimates count and are MARKED*. A customer
            #: looking at a month is entitled to know part of it was estimated.
            "estimated": (month, service, unit) in estimated,
        }
        for (month, service, unit) in order
    ]


def _home_usage_latest(
    tenant_id: Any, account_ids: list[Any], *, today: Any = None
) -> list[dict[str, Any]]:
    """The newest STATED month, one row per service — the home tile.

    ⚠ **`[]` IS A REAL ANSWER AND THE TILE CLOSES UP** (`US-CWP-025` TC-5,
    `BR-CWP-093`). A trash-only account has no meter, so there is no tile and
    **no empty chart** — the screen says the service is not measured rather
    than drawing a zero. The same `[]` also means *nobody has read this meter
    yet*, and the tile is absent for that too: both are *we have nothing to
    show you*, and neither is *you used nothing*.
    """
    series = _home_usage_series(tenant_id, account_ids, today=today)
    if not series:
        return []
    newest = series[-1]["month"]
    return [row for row in series if row["month"] == newest]

def _fold_fact(values: list[Any]) -> dict[str, Any]:
    """One fact across a login's accounts — the value, or *they disagree*.

    ⚠ **DISAGREEMENT IS A THIRD ANSWER AND NOT A MISSING ONE.** A landlord's
    four accounts sit at four addresses and share one plan; showing the first
    address would tell them their service is at one building, and dropping the
    row would take the plan with it. So: agreed → the value, disagreed →
    `None` with `varies: true`, and the SCREEN writes *varies by account*
    (B14 rule 35 — the catalogue says it, never this function).

    `None` throughout is ordinary and the row closes up (`BR-CWP-093`).
    """
    known = [one for one in values if one is not None]
    distinct = {str(one) for one in known}
    if len(distinct) > 1:
        return {"value": None, "varies": True}
    return {"value": known[0] if known else None, "varies": False}


def _home_service(tenant_id: Any, account_ids: list[Any]) -> dict[str, Any]:
    """`CWP-022`'s **YOUR SERVICE** panel — *Address / Plan / Billed / Paperless*.

    ⚠ **FOUR FACTS, EACH WITH ITS OWN `varies`, AND THAT IS `contact_details`'
    POSTURE RATHER THAN A NEW ONE.** Maria holds four accounts on one login;
    they share a plan and sit at four addresses. A panel that showed the FIRST
    account's address would tell a landlord their service is at one building,
    and a panel that vanished the moment a set disagreed would take the plan and
    the cadence with it. So each row is folded on its own: agreed → the value,
    disagreed → `None` and `varies: true`, and the SCREEN says *varies by
    account* on exactly the rows that do (B14 rule 35 — the catalogue writes
    that sentence, not this function).

    ⚠ **THE ADDRESS IS WALKED, NEVER READ OFF THE ACCOUNT** (CLAUDE.md hard rule
    8). `service_address` is the one place this product composes one, and
    `DEF-CUS-3653` is what a second copy costs: an account header composed a
    locality from a retired column and would have returned null forever with
    every test green.

    ⚠ **`None` IS AN ORDINARY ANSWER ON EVERY ROW AND THE ROW THEN CLOSES UP**
    (`BR-CWP-093`). A unit with no route has no cadence; an account with no plan
    assignment has no plan. Neither is an error and neither is a dash.
    """
    from apps.customers import models as customers_models
    from apps.customers import selectors as customers_selectors
    from apps.portal.seams import metering_seam, rating_seam

    ids = [str(one) for one in account_ids]
    rows = list(
        customers_models.Account.objects.filter(
            # `BR-CWP-010` — the tenant is IN THE QUERY (`G96`, `DEF-CWP-3775`).
            tenant_id=tenant_id,
            pk__in=ids,
        ).select_related("unit")
    )
    addresses: list[str | None] = []
    plans: list[str | None] = []
    cadences: list[str | None] = []
    paperless: list[bool | None] = []
    for account in rows:
        addresses.append(service_address(account))
        unit_id = account.unit_id
        plan = (
            rating_seam.plan_history(tenant_id, unit_id).get("current")
            if unit_id is not None
            else None
        )
        plans.append(plan.get("name") if plan else None)
        cadences.append(
            metering_seam.billing_frequency_for_unit(tenant_id, unit_id)
            if unit_id is not None
            else None
        )
        elected = customers_selectors.channel_preference_for_account(str(account.pk))
        #: `None` from the published read is *nobody could look*, not *elected
        #: nothing* — the distinction `delivery_election` already draws.
        paperless.append(None if elected is None else ("email" in elected))

    def fold(values: list[Any]) -> dict[str, Any]:
        #: ⚠ **ONE FOLD, NOT TWO** (B14 rule 36). `_fold_fact` is the module's
        #: own, and `_home_identity` below folds the name and the status through
        #: the SAME function — two copies of *do these accounts agree* is two
        #: answers to one question, one card apart.
        return _fold_fact(values)

    return {
        "address": fold(addresses),
        "plan": fold(plans),
        #: One of `schedule.FREQUENCIES` — a WORD the catalogue keys on, never a
        #: sentence (B14 rule 35).
        "billed": fold(cadences),
        #: `BR-BIL-036` — print is the FLOOR, so this says whether email was
        #: ADDED and never that paper stopped. The screen's two words say so.
        "paperless": fold(paperless),
    }


def _home_identity(tenant_id: Any, account_ids: list[Any]) -> dict[str, Any]:
    """`CWP-022`'s account card — *am I in the right place, and is this me?*

    ⚠ **THIS EXISTS BECAUSE THE PRODUCT OWNER SAID THE HOME PAGE HAD NO
    IDENTITY ON IT AT ALL**, verbatim, 2026-09-08: *"once I login as consumer -
    03 Home ... we are not displaying account # of Customer nmae - ther eis no
    identifier"*, then *"can you give big account identifier on home screen -
    name account #, service area, Utility services, assets, phone # and email
    ID, govt ID - last 4 digits etc - you can mask these detials"*, then the
    trim that decides the SHAPE: *"just show IDs not details - Equipment ...
    W-2209, 8841-C, F-0118 - this is enough + account status"*.

    ⚠ **SO EQUIPMENT TRAVELS AS BARE REFERENCES AND NOT AS DESCRIPTIONS.**
    `W-2209`, never *Water meter W-2209 · 5/8 inch*. A customer already knows
    what is fitted at their own property; what they cannot produce from memory
    is the number a clerk asks for on the telephone. Three references fit on one
    line where three descriptions took three, and `CWP-037` is one tap away with
    the sizes, the ownership and the last read on it.

    ⚠ **THE MASKING IS DONE HERE AND NOT ON THE SCREEN** (PO: *"you can mask
    these detials"*). The home page therefore never RECEIVES a full telephone
    number or e-mail address, so no later refactor of a component can reveal
    one; `CWP-024` still serves both in full because that screen edits them.
    `credentials.mask_phone` and `mask_email` are the product's own two masks —
    a third pair here would be a second opinion about what a customer is
    allowed to see (B14 rule 36).

    ⚠ **THREE FIELDS THE DRAWING ASKS FOR ARE NOT SERVED AND ARE NOT INVENTED**
    (`BR-CWP-093`, and the prime directive: a plausible number in front of a
    customer is worse than an absent row):

      * **the government ID** — `customers.Contact.gov_id_last4` holds four
        digits and nothing in `apps/portal/` reads it. WHICH record it comes
        from on a login holding several accounts, and whether the portal may
        read it at all, is a decision nobody has made. The row is absent, which
        is what the drawing itself asks for when there is no ID on file.
      * **the service area, route and cycle** — *Quarry Hill · Route 4 · Cycle
        2*. `metering_seam.billing_frequency_for_unit` walks unit → service
        point → route → cycle and returns the CADENCE alone; no read returns
        their names.
      * **anything the account status cannot say.** The status IS served below;
        *Active since Jun 2, 2026* pairs it with a date this payload does not
        carry on the status itself (`opened_on` is on `CWP-065`'s summary).

    ⚠ **THE ADDRESS AND THE ACCOUNT NUMBER ARE DELIBERATELY NOT HERE.** The
    frame draws them on the account bar, one line above this card, on every
    signed-in screen. Serving them again would put the same two facts twice on
    one screen — which is the *"too much content"* the Product Owner has now
    complained about four times (B14 rule 32).
    """
    from apps.customers import models as customers_models
    from apps.portal import credentials
    from apps.portal.seams import customers_seam, metering_seam

    ids = [str(one) for one in account_ids]
    rows = list(
        customers_models.Account.objects.filter(
            # `BR-CWP-010` — the tenant is IN THE QUERY (`G96`, `DEF-CWP-3775`).
            tenant_id=tenant_id,
            pk__in=ids,
        ).select_related("status", "unit")
    )

    statuses: list[str | None] = []
    #: ⚠ **THE UTILITY'S OWN CLASSIFICATION, NOT A WORD WE INVENT** — the five
    #: `behavior_class` values `BR-CUS-055` seeds (`billable`, `non_billable`,
    #: `billable_base_only`, `terminal`, and a tenant's own). It travels beside
    #: the NAME so the screen can colour the chip without reading the name,
    #: which would break the moment a utility renames *Active* or adds *Legal
    #: hold* — a tenant-extensible lookup is exactly the thing a screen must
    #: not pattern-match on (B14 rule 35's shape, one field over).
    classes: list[str | None] = []
    #: Code → the utility's OWN word for the service, first spelling wins. A
    #: dict rather than a list because a landlord's four accounts take water
    #: four times and the card names each service once.
    services: dict[str, str] = {}
    #: ⚠ ORDERED AND DE-DUPLICATED BY REFERENCE. Two accounts at one premises
    #: share a meter, and the same serial twice on one line reads as two meters.
    equipment: list[str] = []

    for account in rows:
        status_row = getattr(account, "status", None)
        statuses.append(getattr(status_row, "name", None))
        classes.append(getattr(status_row, "behavior_class", None))
        for held in customers_seam.services_held(tenant_id, account.pk):
            services.setdefault(str(held.get("code")), str(held.get("name")))
        if account.unit_id is None:
            continue
        for item in metering_seam.equipment_for_unit(tenant_id, account.unit_id, today=None):
            #: The SERIAL is what is stamped on the thing in the street; the
            #: asset number is the utility's own reference and is the fallback.
            #: Neither is a database id (B14 rule 31) — `CWP-037` takes the same
            #: pair for the same reason.
            reference = item.get("serial_no") or item.get("asset_no")
            if reference and str(reference) not in equipment:
                equipment.append(str(reference))

    #: ⚠ **THE SAME READ `CWP-024` USES, NOT `holder_display_name`.** That one
    #: exists so the GUEST path has something to mask and `G92` refuses its key
    #: on any guest response; this is the signed-in customer's own record, and
    #: `contact_details` is where the product already decides what one login's
    #: several accounts jointly say (`BR-CWP-026`).
    contact = customers_seam.contact_details(tenant_id, ids)
    phone = contact.get("phone")
    email = contact.get("email")

    return {
        "name": _fold_fact([contact.get("legal_name")]),
        #: The utility's own lookup word — `Active`, `Vacation hold`, and a
        #: tenant's own additions (`BR-CUS-055`). Served exactly as the plan
        #: name and the service names already are.
        "status": _fold_fact(statuses),
        "status_class": _fold_fact(classes),
        "services": [{"code": code, "name": name} for code, name in services.items()],
        "equipment": equipment,
        #: ⚠ MASKED, AND `None` WHEN THE ACCOUNTS DISAGREE — a landlord shown
        #: one of four telephone numbers would read it as settled.
        "phone": None if contact.get("phone_varies") or not phone else credentials.mask_phone(phone),
        "phone_varies": bool(contact.get("phone_varies")),
        "email": None if contact.get("email_varies") or not email else credentials.mask_email(email),
        "email_varies": bool(contact.get("email_varies")),
    }


def home(principal: Any, *, today: Any) -> dict[str, Any]:
    """`CWP-022` — *do I owe anything and by when*, above everything else.

    ⚠ **A PANEL WITH NOTHING IN IT RENDERS AS NOTHING** (`BR-CWP-093`), and
    every key below is built to make that possible: `attention` is an empty
    LIST rather than a list of empty things, `tip` is `None` rather than a
    blank, and `usage` is `[]` for an account with no measured service. The
    screen closes the gap up and **nobody can tell the slot was there** — which
    is the difference between a product that has nothing to say today and one
    that looks broken.

    ⚠ **THE ATTENTION PANEL IS THE PORTAL'S ONLY PROACTIVE SURFACE**, so what
    goes in it is deliberately narrow: things the customer can ACT on now. A
    balance owing is one. A reading window is not — the FACT is available now
    (`metering_seam.read_window_for_unit`, published 2026-09-04) but the ACTION
    is `US-CWP-042`, wave 3, and an item whose only control does not exist is
    worse than an absent one. `billing_seam.reading_window_open` carries the
    corrected reason.

    ⚠ **THE USAGE TILE READS THE STORED MONTHS AND NOT BILL LINES — CORRECTED
    2026-09-04 BY PO RULING** (*"We are mainiting last 12 month usage details on
    account - you canuse it"*). It used to sum `invoice_lines`, which meant the
    tile showed what the customer was BILLED for: usage since the last bill
    never appeared, and **an unread month was indistinguishable from a month of
    no use** — the one claim `BR-MET-106` exists to refuse. `billing_seam`'s own
    docstring carries the superseded paragraph and what the mistake cost.

    `today` is a PARAMETER, never a clock read in here (`BR-TEN-043`).
    """
    from apps.portal.seams import billing_seam, payments_seam

    account_ids = list(principal.account_ids)
    balances = payments_seam.balance_summary(account_ids, as_of=today)

    attention: list[dict[str, Any]] = []
    owing = balances.get("total_owing")
    if owing is not None and Decimal(owing) > 0:
        attention.append(
            {
                #: A KIND, not a sentence — the catalogue writes the words and
                #: the amount travels as a figure (B14 rule 35).
                "kind": "pay",
                "amount": owing,
                "currency": balances.get("currency"),
            }
        )
    # ⚠ **`CR-182-BRC10` (PO A1/A5, 2026-10-14) — A READING FLAGGED HIGH IS
    # SOMETHING TO ACT ON, AND IT IS SAID AS SOON AS IT IS FLAGGED.** PO
    # verbatim: *"immedately send it high consumption alert to get in portal in
    # app msage or warning"*. One item per meter whose LATEST reading is flagged
    # and not yet billed — the reading's own BR-MET-020/120 flag, so the
    # customer is told exactly what staff see. The action is *see your
    # readings* (a leak is something they can check). A KIND and figures; the
    # catalogue writes the words (B14 rule 35).
    named_services: dict[str, str] | None = None
    for alert in metering_seam.high_consumption_alerts(principal.tenant_id, account_ids):
        if named_services is None:
            named_services = _service_names(principal.tenant_id)
        code = alert.get("service") or ""
        attention.append(
            {
                "kind": "high_consumption",
                "service": code or None,
                "service_name": named_services.get(code),
                "taken_on": alert.get("taken_on"),
            }
        )
    #: …and once a bill carrying it exists, *Your last bill is higher than
    #: usual · See why →*, which opens that bill's comparison (PO A1).
    high_bill = billing_seam.last_bill_high_usage(account_ids)
    if high_bill:
        attention.append({"kind": "high_bill", "number": high_bill})

    return {
        "as_of": today.isoformat(),
        #: The lead tile, unchanged from wave E — one read, one truth.
        "balances": balances,
        "last_bill": billing_seam.last_bill(account_ids),
        "last_payment": payments_seam.last_payment(account_ids),
        #: ⚠ Each row carries its own UNIT (hard rule 3) and its own SERVICE:
        #: gallons and therms share a month and nothing else, so there is one
        #: row per service and no total anywhere in this payload.
        "usage": _home_usage_latest(principal.tenant_id, account_ids, today=today),
        "usage_series": _home_usage_series(principal.tenant_id, account_ids, today=today),
        #: ⚠ **`today` IS WHAT PUTS THE *Usage* AND *Status* COLUMNS ON THE
        #: HOME TABLE** (`DEF-CWP-3965`, `08-screen-layouts.md` `CWP-022`:
        #: *Bill / Period / Usage / Amount / Status*). The state is
        #: `_bill_state`'s, the same function `CWP-027` paints its chip from.
        "recent_bills": billing_seam.recent_bills(account_ids, today=today),
        #: `CWP-022`'s rail — *Address / Plan / Billed / Paperless*, each folded
        #: across the login's accounts with its own `varies`.
        "service": _home_service(principal.tenant_id, account_ids),
        #: ⚠ **THE ACCOUNT CARD — WHO THIS IS, WHAT THEY TAKE, WHAT IS FITTED.**
        #: PO 2026-09-08: the home page carried no identifier at all. It rides
        #: on THIS read rather than on three of its own: the card needs the
        #: services from `customers`, the equipment from `metering` and the
        #: contact from `contacts`, and a screen making three more round trips
        #: would pay the tenant resolution three more times for a card that must
        #: never delay the figure the page exists to show.
        "identity": _home_identity(principal.tenant_id, account_ids),
        "attention": attention,
        #: `BR-CWP-095` — at most one, on and in season. `None` closes the slot.
        "tip": tenancy_seam.tip_for_screen(principal.tenant_id, "portal_home"),
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave G · `CWP-024` — my details (US-CWP-028)
# ═══════════════════════════════════════════════════════════════════════════

#: THE LANGUAGES THE PORTAL OFFERS. Two.
#:
#: ⚠ **PO RULING 2026-09-07, VERBATIM: *"currently in drop down show only 2
#: elnglish and spanish"*** — confirming their ruling of 2026-09-05, *"Portal
#: languages: English and Spanish only"*, which `DEF-CWP-4442` carried unbuilt
#: for two days because narrowing the list had a customer-data question
#: attached. **This read ELEVEN until then**, and the eleven were the front
#: end's catalogue folder copied across.
#:
#: ⚠ **IT ANSWERS *MAY THE PORTAL OFFER IT*, WHICH IS NOT *CAN THIS BUILD DRAW
#: IT* — `BR-CWP-105` NAMES BOTH AND SAYS DO NOT FOLD THEM.** The second
#: question is the front end's `LOCALE_CODES` (`BR-SHL-041`), it still carries
#: **eleven catalogues**, and NOT ONE WAS REMOVED here: the bundle draws German
#: exactly as it did yesterday. Narrowing the OFFER must never narrow the
#: RESOLUTION, which is why this constant is not what `supportedLocale`
#: validates against and why `test_def_cwp_4440_portal_language.py` asserts a
#: German account still reads German.
#:
#: ⚠ **NOBODY'S STORED CHOICE IS RESET, AND NOTHING HERE VALIDATES A WRITE.**
#: Accounts already hold `de` and `hi`. The Product Owner ruled on what the
#: dropdown OFFERS and said nothing about those rows; the reading taken — in
#: the decision log of 2026-09-07, not to be re-made — is that a customer whose
#: account says German keeps reading German until they change it themselves.
#: A lane that "completed" this by refusing a non-offered `preferred_language`
#: would take a setting away from a person who chose it.
#:
#: ⚠ **THE SPANISH IS `es`, THE CODE WHOSE OWN NAME IS *Español*.** `es-MX`
#: remains a catalogue this build draws and a lawful stored value; it is not
#: one of the two offered. A reader already on it sees it as the third option
#: their own picker adds — see `offeredLocales` in
#: `07-frontend/src/portal/components/language.ts`, which is where "the offer
#: plus this reader's own language" is built, once, for BOTH pickers.
#:
#: ⚠ **THE PRE-EXPANSION SPELLINGS STILL MATTER** (`BR-SHL-041`): `en` and `es`
#: were ratified before the expansion and are STORED in
#: `tenant_settings.default_language` and `accounts.preferred_language`, so
#: renaming them to `en-US`/`es-ES` without a migration would orphan every
#: stored value.
PORTAL_LOCALES: tuple[str, ...] = ("en", "es")


def my_details(principal: Any, *, today: date) -> dict[str, Any]:
    """`CWP-024` — everything the screen draws, in one read.

    ⚠ **THE THREE EDITABLE FIELDS AND THE TWO REFUSED ONES ARRIVE TOGETHER**
    (`BR-CWP-026`). A screen that fetched only what it could change would have
    nowhere to put *ask us to change this*, and a customer who cannot see their
    own name on the page assumes we lost it.

    ⚠ **AND THE SECURITY FACTS ARE FACTS, NOT CONTROLS.** *Password changed on*,
    *codes go to*, *signed in on two devices* — each is something a customer
    checks when they are worried, and each is read here rather than being a
    second endpoint the screen has to remember to call (hard-won law 2: an
    optional prop nothing passes is dead UI).
    """
    account_ids = list(principal.account_ids)
    details = customers_seam.contact_details(principal.tenant_id, account_ids)
    #: ⚠ The principal carries a `credential_id`, not the row — it is a frozen
    #: dataclass built once per request and deliberately holds no ORM object.
    from apps.portal import models as portal_models

    credential = portal_models.PortalCredential.objects.filter(
        tenant_id=principal.tenant_id, pk=principal.credential_id
    ).first()
    return {
        "as_of": today.isoformat(),
        **details,
        #: `BR-CWP-026` — the two the portal refuses, named so the screen can
        #: render them read-only with their route rather than hiding them.
        "refused": ["legal_name", "account_holder"],
        "locales": list(PORTAL_LOCALES),
        #: ⚠ **THE CREDENTIAL CARRIES NO LANGUAGE COLUMN AND ONE WAS NOT
        #: INVENTED HERE.** `PortalCredential` has `email`, `password_hash`,
        #: `password_changed_on`, `otp_channel`, the lockout pair and a status —
        #: no locale. So the picker opens on what the ACCOUNTS agree on, which
        #: is a real value the utility already prints letters in, and on nothing
        #: when they disagree. A per-login column is `US-CWP-030`'s (wave H),
        #: where the preference write point already lives.
        "locale": account_language(principal),
        "security": _security_facts(principal, credential),
    }


def account_language(principal: Any) -> str | None:
    """The language already on file, so the picker opens on the right one.

    ⚠ **`preferred_language` LIVES ON THE ACCOUNT AND THE PICKER IS PER LOGIN**,
    which is a real mismatch and is answered by showing what the accounts agree
    on and nothing when they do not. Guessing would set a customer's portal to
    a language one of their four accounts happens to carry.

    ⚠ **IT WAS `_account_language` AND IS PUBLIC FROM 2026-09-07 BECAUSE A
    SECOND CALLER ARRIVED, NOT BECAUSE PRIVACY STOPPED MATTERING**
    (`DEF-CWP-4440`, `BR-CWP-105`). `GET portal/session` now serves this same
    value so the SHELL can apply it — PO ruling 2026-09-07: *"a signed-in
    customer will get their account's own preferred language"*. Writing a
    second fold over the same column for the shell is exactly how the language
    a customer PICKS on `CWP-024` and the language they READ would come to
    disagree, which is hard-won law 5 (one source, never a second copy) and is
    the whole reason this is one function with two callers.

    ⚠ **AND THE DISAGREEMENT ANSWER IS LOAD-BEARING NOW, NOT COSMETIC.** When a
    landlord's four accounts hold different languages this returns `None`, and
    `BR-CWP-105`'s chain then falls to the tenant's setting — the utility's own
    language rather than whichever of four an ordering happened to put first.
    """
    from apps.customers import models as customers_models

    values = list(
        customers_models.Account.objects.filter(
            tenant_id=principal.tenant_id, id__in=[str(one) for one in principal.account_ids]
        )
        .values_list("preferred_language", flat=True)
        .distinct()
    )
    kept = [str(one) for one in values if one]
    return kept[0] if len(kept) == 1 else None


def _security_facts(principal: Any, credential: Any) -> dict[str, Any]:
    """What `CWP-024`'s right-hand column states. ⚠ **NO CONTROL IS IMPLIED BY
    A FACT BEING HERE** — *sign out everywhere* is its own endpoint
    (`sessions/revoke-all`, wave E) and this read only counts the devices."""
    sessions = 0
    if credential is not None:
        sessions = models.PortalSession.objects.filter(
            tenant_id=principal.tenant_id,
            portal_credential_id=getattr(credential, "id", None),
            revoked_at__isnull=True,
        ).count()
    changed = getattr(credential, "password_changed_on", None)
    return {
        "password_changed_on": changed.date().isoformat() if changed else None,
        #: The channel a one-time code goes to — a fact, and the reason a
        #: customer with a new phone knows to fix the mobile above first.
        "code_channel": getattr(credential, "otp_channel", None),
        "devices_signed_in": sessions,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 · `CWP-031` — DOCUMENTS AND LETTERS (US-CWP-036)
#
# ⚠ **THE ARITHMETIC IS NOT HERE AND NEITHER IS THE QUERY.**
# `apps.notifications.correspondence_reads.account_correspondence` is the
# PUBLISHED read (PO 2026-09-04 — the portal reuses the owning module's read
# rather than writing a second one), reached through
# `seams.notifications_seam`. What this function does is the portal's own three
# jobs and nothing else: name each document in words a customer can quote, sort
# it into the three buckets the screen filters on, and take the database ids
# OUT before anything crosses the wire (B14 rule 31).
# ═══════════════════════════════════════════════════════════════════════════

#: The three filters `CWP-031` draws — *All · Bills · Receipts · Letters*.
#: A PORTAL vocabulary, not the store's: `tenancy.DOCUMENT_KINDS` has 33
#: members and a customer has three questions.
DOC_GROUP_BILL = "bill"
DOC_GROUP_RECEIPT = "receipt"
DOC_GROUP_LETTER = "letter"
DOC_GROUPS = (DOC_GROUP_BILL, DOC_GROUP_RECEIPT, DOC_GROUP_LETTER)

#: ⚠ **`letter` IS THE DEFAULT AND IT IS A DECISION, NOT A FALLBACK.** Every
#: kind that is not a bill or a receipt IS a letter to the person receiving it
#: — a dunning notice, a plan agreement, a move-in welcome — and so is a
#: document whose class `OQ-1164` has not ruled on (`kind is None`). Inventing
#: a fourth bucket for *"we are not sure"* would put a customer's own post
#: somewhere they would never look.
_GROUP_BY_KIND = {
    "bill": DOC_GROUP_BILL,
    "move_out_final_bill": DOC_GROUP_BILL,
    "payment_receipt": DOC_GROUP_RECEIPT,
    "remittance_receipt": DOC_GROUP_RECEIPT,
}


def _document_group(kind: str | None, source_type: str | None = None) -> str:
    """WHICH BUCKET a document belongs in — bill, receipt, or letter.

    ⚠ **THE `source_type` FALLBACK IS `DEF-CWP-3969`, AND IT IS WHY BILLS WERE
    MISSING FROM A SCREEN THAT LISTED THEM.** On the live deployment all 100
    invoice queue rows carry an EMPTY `template_code`, so `document_kind`
    correctly answers `None` — nothing was pinned — and every one of those bills
    was filed as a *letter*. A customer opening *Documents and letters* saw
    their bills and could not tell them from their post, and the *Bills* filter
    matched none of them.

    ⚠ **IT FIRES ONLY WHERE THE KIND IS UNKNOWN, AND THAT ORDER IS THE WHOLE
    SAFETY OF IT.** A `corrected_bill_notice` is `source_type = 'invoice'` and
    is a LETTER ABOUT a bill rather than a bill; a `refund_confirmation` is
    `source_type = 'payment'` and is not a receipt. Both carry a known kind, so
    the map above answers first and this never sees them.

    ⚠ **AND IT IS A GROUP, NOT A KIND.** `correspondence_reads.document_kind`
    declines to derive the KIND from `source_type` and says why — three
    different notices all carry `source_type = 'notice'`, and *"what was that
    letter"* asks for a kind and never for a table. That reasoning holds and is
    not being overturned: `kind` stays `None` on these rows and the screen still
    refuses to name a class nobody ruled on. What is derived here is only WHICH
    OF THREE PILES the row goes in, and a document produced from an invoice is
    in the bill pile whatever template was or was not pinned to it.
    """
    #: ⚠ **THE BRANCH IS ON WHETHER A KIND WAS STATED, NOT ON WHETHER THE MAP
    #: NAMES IT.** `_GROUP_BY_KIND` lists only the bill and receipt kinds —
    #: every other kind is a LETTER by falling off the end — so asking the map
    #: first makes *a known letter kind* and *no kind at all* the same answer,
    #: and `dunning_letter` on an invoice would be filed as a bill. Caught by
    #: `test_def_cwp_3969_a_known_kind_still_decides_the_pile_before_the_source_does`,
    #: which is the case this ordering exists for.
    if kind:
        return _GROUP_BY_KIND.get(kind, DOC_GROUP_LETTER)
    if source_type == "invoice":
        return DOC_GROUP_BILL
    if source_type == "payment":
        return DOC_GROUP_RECEIPT
    return DOC_GROUP_LETTER


def _document_name_facts(
    row: dict[str, Any],
    periods: dict[str, dict[str, Any]],
    amounts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """The four fields a row is NAMED from — or four `None`s, honestly.

    ⚠ **THE SERVER SERVES FACTS AND THE CATALOGUE WRITES THE SENTENCE.**
    Composing *"Bill for August"* here would be composing it in English, on a
    screen that renders in eleven languages (B14 rule 35), and a translated
    server string is the thing rule 35 exists to prevent.
    """
    source_id = row["source_id"]
    period = periods.get(source_id) if row["source_type"] == "invoice" else None
    money = amounts.get(source_id) if row["source_type"] == "payment" else None
    return {
        "period_start": (period or {}).get("period_start"),
        "period_end": (period or {}).get("period_end"),
        "amount": (money or {}).get("amount"),
        "currency": (money or {}).get("currency"),
    }


def _document_numbers(rows: list[dict[str, Any]]) -> dict[str, str]:
    """`{source id: the number printed on the paper}` for a page of documents.

    ⚠ **THE LIST AND THE SERVING PATH RESOLVE THE REFERENCE HERE OR THEY DRIFT**
    (`CR-085` `CPB-14`). `CWP-031` names a document by its number and the file
    route is ADDRESSED by that number, so the two have to agree about what a row
    is called. Two spellings of the same join is how a screen ends up offering a
    copy the server cannot find — the shape `notifications_seam` already records
    for `_stored`, one layer down.

    ⚠ **NO ID EVER COMES BACK FROM HERE.** A source with no minted number is
    ABSENT from the map (`payments_seam.payment_numbers`' own rule), so the
    caller states the absence in words instead of printing eight characters of a
    uuid (B14 rule 31, `DEF-3158`).
    """
    from apps.portal.seams import billing_seam, payments_seam

    invoice_ids = [row["source_id"] for row in rows if row["source_type"] == "invoice"]
    payment_ids = [row["source_id"] for row in rows if row["source_type"] == "payment"]
    numbers: dict[str, str] = {}
    numbers.update(billing_seam.invoice_numbers(invoice_ids))
    numbers.update(payments_seam.payment_numbers(payment_ids))
    return numbers


def documents(account: Any) -> dict[str, Any]:
    """`CWP-031` — what we sent, when, and by which route.

    ⚠ **`documents: null` AND `documents: []` ARE DIFFERENT ANSWERS AND THE
    SCREEN MUST BRANCH ON BOTH.** `null` is the queue unreachable — nobody
    could ask — and `[]` is a customer who has genuinely been sent nothing yet.
    Rendering one empty state over both would tell a customer with eleven
    months of bills that we never wrote to them.

    ⚠ **NOT ONE DATABASE ID LEAVES THIS FUNCTION** (B14 rule 31, `DEF-3158`).
    The published read carries `source_id` because a caller has to resolve the
    human reference; that resolution happens here and the id is dropped. Where
    a document has no human number the row carries `reference: null` and the
    screen says so in words — never eight characters of a uuid, which is the
    same breach as the whole thing.

    ⚠ **`delivery_reported` RIDES EVERY ROW.** Nothing on this deployment can
    report a delivery on any channel (`delivery_ops.UNPOPULATED_STATUSES`), and
    `OQ-1399` closed on 2026-09-04 with the portal as a CONVENIENCE COPY — post
    and email remain the delivery record (`BR-CWP-083`). So the screen may say
    *we sent this* and may never say *you received this*, and the fact travels
    as data rather than as a rule a screen has to remember.
    """
    from apps.portal.seams import billing_seam, notifications_seam, payments_seam

    rows = notifications_seam.account_correspondence(account_ids=[account.pk])
    if rows is None:
        return {
            "documents": None,
            "groups": list(DOC_GROUPS),
            "unavailable": (
                "the queue that records what was sent is not answering on this "
                "deployment, so nothing is listed rather than an empty list that "
                "would read as nothing having been sent"
            ),
        }

    invoice_ids = [row["source_id"] for row in rows if row["source_type"] == "invoice"]
    payment_ids = [row["source_id"] for row in rows if row["source_type"] == "payment"]
    numbers = _document_numbers(rows)
    #: `DEF-CWP-3969` — what NAMES each document, as facts rather than as a
    #: composed English sentence. The words are the catalogue's (B14 rule 35);
    #: what the server owes the screen is the month a bill covers and the
    #: amount a receipt is for. Two queries for the whole list, alongside the
    #: two that already resolve the numbers.
    periods = billing_seam.invoice_periods(invoice_ids)
    amounts = payments_seam.payment_amounts(payment_ids)

    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                #: WHAT it is, as a kind the screen words in the reader's own
                #: language (B14 rule 35). `None` where `OQ-1164` has ruled on
                #: no class for it — a stated absence, and the screen reads
                #: *"a letter from us"* rather than guessing a kind.
                "kind": row["kind"],
                "group": _document_group(row["kind"], row["source_type"]),
                #: `DEF-CWP-3969` — WHICH month this bill covers and HOW MUCH
                #: this receipt was for, so the row can be named after the
                #: document instead of after its class. Every one of these is
                #: `None` on a row that is neither, and the screen falls back
                #: to the kind word rather than composing a name around a
                #: blank. NO id travels: a period and an amount are facts a
                #: customer can read (B14 rule 31).
                **_document_name_facts(row, periods, amounts),
                #: The number on the paper — `BL-2608-0141`, `PMT-2608-0042` —
                #: or `null`. NEVER an id and never part of one.
                "reference": numbers.get(row["source_id"]),
                #: WHEN. `sent_on` is the dispatcher's stamp and is null on
                #: everything this deployment has written; `queued_on` is the
                #: day the document was made and put on the queue, and it is
                #: the date the screen shows with the state beside it.
                "sent_on": row["sent_on"],
                "queued_on": row["queued_on"],
                #: HOW — every route it went by (`BR-CWP-083`), each with its
                #: own state, so *Post · Email* where one leg failed does not
                #: read as though both went.
                "routes": [
                    {
                        "channel": route["channel"],
                        "state": route["state"],
                        "reason": route["reason"],
                        "returned_on": route["returned_on"],
                    }
                    for route in row["routes"]
                ],
                "state": row["state"],
                "delivery_reported": row["delivery_reported"],
                "delivery_not_reported_reason": row["delivery_not_reported_reason"],
                #: `BR-CWP-045` — documents are SERVED, never re-rendered. Where
                #: no copy was kept the control is rendered VISIBLY HELD with
                #: this reason (`BR-CWP-056`), never hidden.
                "stored_document": row["stored_document"],
            }
        )
    return {"documents": out, "groups": list(DOC_GROUPS), "unavailable": None}


# ═══════════════════════════════════════════════════════════════════════════
# `CR-085` `CPB-14` / `CPB-15` — TAKING A COPY OF WHAT WE SENT
#
# ⚠ **`CWP-031` HAS LISTED EVERY DOCUMENT SINCE `US-CWP-036` AND WOULD OPEN
# EXACTLY ONE KIND OF THEM.** The row control's condition was
# `group == "bill" AND a reference AND a kept copy`, so a **receipt** and a
# **letter** were refused with the sentence *"We kept no copy of this."* —
# which is a false statement about a document we did keep, and the customer's
# own receipt was on the screen, named, dated, and unreachable.
#
# ⚠ **NOTHING HERE RENDERS ANYTHING** (`BR-CWP-045`, `BR-NOT-027`). Both
# selectors below serve the frozen artefact through
# `notifications_seam.stored_document_service` and answer a REFUSAL where there
# is none.
#
# ⚠ **ADDRESSED BY THE NUMBER ON THE PAPER, NEVER BY A ROW ID** (B14 rule 31,
# and `bill_in_set`'s own note: *"the number is printed on the paper the
# customer is holding, so it is what the address bar carries"*). That is why
# `documents()` still publishes no `source_id` and why a document with no minted
# number cannot be fetched one at a time — a real limit, stated rather than
# worked around with an id, and the reason `CPB-15`'s bundle exists beside it:
# a document with no number of its own still leaves in the year's ZIP.
# ═══════════════════════════════════════════════════════════════════════════

#: How far back `Download a year` reaches, in months. A YEAR, because that is
#: what the control on `CWP-031` says — the window is the promise, not a
#: setting.
DOCUMENT_BUNDLE_MONTHS = 12

#: The most documents one bundle will carry. `NFR-5` forbids a per-tenant cap
#: and this is not one: it is a bound on ONE RESPONSE, on one account's own
#: mail, and a customer who has more is told so and given the list. Chosen
#: against the estate this product models — a T5 account gets ~12 bills, ~12
#: receipts and a handful of letters a year, so 200 is an order of magnitude
#: clear of an ordinary year and still a file a browser can hold.
DOCUMENT_BUNDLE_MAX = 200


def document_file(account_ids: list[Any], *, reference: str) -> dict[str, Any]:
    """ONE kept document from this LOGIN's mail, by the number printed on it.

    Answers `{"verdict": …, "payload": bytes|None, "content_type": …,
    "filename": …, "account_id": …}`. `not_found` means no row of this login's
    correspondence carries that number — the SAME answer for a number belonging
    to somebody else and a number that never existed, which is `BR-CWP-041`'s
    posture and the reason a customer cannot probe what exists.

    ⚠ **SCOPED TO THE WHOLE SESSION, NOT TO ONE ACCOUNT, AND THAT MATCHES THE
    BILL.** `bill_document_pdf` resolves `BL-2608-000044` against
    `principal.account_ids` and so does this: a number is a number, the screen a
    customer happens to be on is not part of it, and `CWP-041` lists a landlord's
    payments across three accounts at once. `BR-CWP-010`'s two halves are in
    `account_correspondence`'s own query, exactly as they are in `bill_in_set`'s.

    ⚠ **IT RETURNS THE ACCOUNT THE DOCUMENT BELONGS TO, BECAUSE `download` IS A
    PER-ACCOUNT GRANT** (`US-CWP-034` TC-7). The caller checks it. Deciding it
    here would put the permission rule in two places.

    ⚠ **THE FILENAME IS THE NUMBER AND THE STORE'S EXTENSION**, never the
    store's `display_name` — that name is built for an operator unpacking an
    archive (`bill/2026/08/AC-2026-00013-BL-2608-000052.pdf`) and carries
    somebody's ACCOUNT NUMBER and a directory path, neither of which belongs in
    a customer's Downloads folder.
    """
    from apps.portal.seams import notifications_seam

    empty = {
        "verdict": "not_found",
        "payload": None,
        "content_type": None,
        "filename": None,
        "account_id": None,
    }
    rows = notifications_seam.account_correspondence(account_ids=list(account_ids))
    if rows is None:
        return {**empty, "verdict": "unavailable"}
    numbers = _document_numbers(rows)
    wanted = (reference or "").strip()
    if not wanted:
        return dict(empty)
    for row in rows:
        if numbers.get(row["source_id"]) != wanted:
            continue
        verdict, payload, content_type, _name = notifications_seam.stored_document_service(
            source_type=row["source_type"], source_id=row["source_id"]
        )
        return {
            "verdict": verdict,
            "payload": payload,
            "content_type": content_type,
            "filename": _bundle_name(wanted, content_type),
            "account_id": row.get("account_id"),
        }
    return dict(empty)


def _bundle_name(reference: str, content_type: str | None) -> str:
    """`BL-2608-000044.pdf` — the number the customer can read, plus a suffix.

    The suffix comes from the MEDIA TYPE the store recorded, so an HTML letter
    does not arrive named `.pdf`. Anything the map does not know keeps no
    extension at all rather than being guessed into one, because a wrong suffix
    is worse than none — the operating system opens it with the wrong thing.
    """
    suffix = {
        "application/pdf": ".pdf",
        "text/html; charset=utf-8": ".html",
        "text/html": ".html",
        "text/plain; charset=utf-8": ".txt",
        "text/plain": ".txt",
    }.get((content_type or "").strip().lower(), "")
    return f"{reference}{suffix}"


def documents_bundle(account: Any, *, today: date) -> dict[str, Any]:
    """`CPB-15` — a year of this account's kept documents, as ONE zip.

    ⚠ **WHY A ZIP AND NOT A MERGED PDF.** The artefacts are frozen legal
    documents of more than one media type (`frozen_bill` keeps HTML *and* PDF;
    a letter may be either), and merging them would produce a NEW document that
    is not any of the ones the customer was sent — the re-render `BR-CWP-045`
    forbids, wearing a different name. A zip carries each file byte-for-byte
    and adds nothing.

    ⚠ **A DOCUMENT WITH NO KEPT COPY IS SIMPLY ABSENT FROM THE ARCHIVE, AND THE
    COUNT SAYS SO.** `kept` and `listed` are both returned so the screen can say
    *"11 of 14"* rather than handing over a short archive that looks complete.
    A zip that quietly dropped three letters would be a check that cannot fail,
    one layer up.

    ⚠ **A TAMPERED COPY IS LEFT OUT TOO, AND IS COUNTED SEPARATELY**
    (`BR-NOT-027`). It must not be handed over, and it must not be reported as
    *no copy kept* either.

    ⚠ **THE WINDOW IS THE QUEUE'S OWN DAY** (`queued_on`), because that is the
    date the list shows and the only one every row carries — `sent_on` is the
    dispatcher's and is null on everything this deployment has written. A window
    on a column that is always null would return an empty archive on every
    account, green, forever.
    """
    import io
    import zipfile

    from apps.portal.seams import notifications_seam

    rows = notifications_seam.account_correspondence(account_ids=[account.pk])
    if rows is None:
        return {"verdict": "unavailable", "payload": None, "listed": 0, "kept": 0, "filename": None}
    numbers = _document_numbers(rows)
    first_day = _months_back(today, DOCUMENT_BUNDLE_MONTHS)
    window = [
        row
        for row in rows
        if (row.get("queued_on") or "") >= first_day.isoformat()
    ][:DOCUMENT_BUNDLE_MAX]

    buffer = io.BytesIO()
    kept = 0
    used: set[str] = set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, row in enumerate(window, start=1):
            verdict, payload, content_type, _name = notifications_seam.stored_document_service(
                source_type=row["source_type"], source_id=row["source_id"]
            )
            if verdict != notifications_seam.DOCUMENT_OK or payload is None:
                continue
            #: A row with no minted number still leaves in the archive — it is
            #: named by its DAY and its position, which is what a person
            #: opening the folder can read. This is the half `document_file`
            #: cannot serve, and it is why the bundle is not merely a
            #: convenience.
            base = numbers.get(row["source_id"]) or f"{row.get('queued_on') or 'undated'}-{index}"
            name = _bundle_name(base, content_type)
            while name in used:
                name = _bundle_name(f"{base}-{index}", content_type)
            used.add(name)
            archive.writestr(name, payload)
            kept += 1
    if kept == 0:
        return {
            "verdict": "empty",
            "payload": None,
            "listed": len(window),
            "kept": 0,
            "filename": None,
        }
    return {
        "verdict": "ok",
        "payload": buffer.getvalue(),
        "listed": len(window),
        "kept": kept,
        #: The ACCOUNT NUMBER and the window, both of which a customer can read
        #: (B14 rule 31 — an account number is printed on their bill).
        "filename": f"{account.account_no}-{first_day.isoformat()}-{today.isoformat()}.zip",
    }


def receipts_that_exist(
    rows: list[dict[str, Any]], *, account_ids: list[Any]
) -> list[dict[str, Any]]:
    """Stamp each money row with whether its receipt can actually be served.

    ⚠ **`CR-085` `CPB-20`, AND IT IS THE SAME LESSON AS `CPB-19` ONE SCREEN
    OVER.** `payments` knows a payment has a `PMT-` number; only
    `notifications` knows whether a copy of that receipt was frozen. A screen
    that drew the control from the NUMBER alone offers a live download for a
    receipt this deployment never kept — which is exactly the disagreement
    between a promise and a serving path that this wave exists to remove. Found
    by walking `CWP-041` in a browser, not by any test: every fixture that had
    a payment number also had a kept copy.

    `receipt_available` is therefore a THIRD state beside the two the row
    already had, and the screen draws three things: the control, the control
    disabled with *we kept no copy of this*, and nothing at all where there is
    no number (a reversal, a credit, a write-off).

    ⚠ **THE COST, STATED: ONE CORRESPONDENCE READ FOR THE WHOLE LIST.** It is
    the same read `CWP-031` draws, over one customer's own mail, and it is
    asked ONCE rather than once per row. A list with no numbered payment on it
    asks nothing at all.
    """
    from apps.portal.seams import notifications_seam

    wanted = {row.get("receipt_reference") for row in rows if row.get("receipt_reference")}
    if not wanted:
        return rows
    #: ⚠ **THE ACCOUNT SET COMES FROM THE CALLER, BECAUSE A MONEY ROW CARRIES
    #: NO ACCOUNT ID AND MUST NOT START TO.** `payments_seam` drops `id`,
    #: `account_id`, `customer_name` and `memo` on purpose (B14 rule 31), and
    #: putting one back so this function could read it would trade a rule for a
    #: convenience. It is the SAME set `money_list` was scoped to, and the
    #: correspondence read puts `BR-CWP-010`'s two halves in its own query — so
    #: this cannot widen what the login may see.
    kept: set[str] = set()
    correspondence = (
        notifications_seam.account_correspondence(account_ids=list(account_ids))
        if account_ids
        else None
    )
    if correspondence is None:
        #: ⚠ **THE QUEUE COULD NOT BE ASKED, SO NOTHING IS PROMISED.** An
        #: unavailable read is *nobody could look*, never *there is a copy* —
        #: the posture `documents()` takes one function up.
        for row in rows:
            row["receipt_available"] = False
        return rows
    numbers = _document_numbers(correspondence)
    for row in correspondence:
        reference = numbers.get(row["source_id"])
        if reference and row["stored_document"]["available"]:
            kept.add(reference)
    for row in rows:
        reference = row.get("receipt_reference")
        row["receipt_available"] = bool(reference and reference in kept)
    return rows


def _months_back(today: date, months: int) -> date:
    """The first day of the month `months - 1` before `today`'s month.

    A YEAR of documents means twelve calendar months INCLUDING this one, which
    is what somebody pressing *Download a year* in September expects to get:
    October of last year through September of this one.
    """
    total = today.year * 12 + (today.month - 1) - (months - 1)
    return date(total // 12, total % 12 + 1, 1)


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 · `CWP-063` — A PLAN THE UTILITY HAS OFFERED YOU (US-CWP-053)
# ═══════════════════════════════════════════════════════════════════════════

#: `US-CWP-053` TC-9's consequence panel, as CODES a catalogue words rather
#: than as sentences assembled here. Two of the four are read from THIS PLAN's
#: own elections (`BR-CUS-043`: *"late-fee suspension is a per-plan
#: election"*), so a plan with `suspend_late_fees = false` tells the customer
#: fees still apply instead of promising they stop — which is J41 step 4's
#: case and the reason these are not four hardcoded bullets.
CONSEQUENCE_LATE_FEES_STOP = "late_fees_stop"
CONSEQUENCE_LATE_FEES_CONTINUE = "late_fees_continue"
CONSEQUENCE_NO_DISCONNECT = "no_disconnect"
CONSEQUENCE_NEW_BILLS_STILL_DUE = "new_bills_still_due"
#: ⚠ **THIS REPLACED `miss_two_ends_it`, WHICH WAS A PROMISE NOTHING KEEPS
#: (`DEF-CWP-4137`).** The blueprint's `P49` panel, `US-CWP-053` and journey
#: `J42` all end with *"miss two and the plan ends, and the whole balance falls
#: due"*, and this selector served a code that made the screen say it. **The
#: Product Owner ruled the opposite on 2026-08-11**, verbatim: *"nodrop we
#: chase for payments until write off"* — and that is what is BUILT:
#: `apps.customers.payment_plan.record_missed_instalment` returns `active` on
#: the tenth miss exactly as on the first, and `apps/payments/plans.py` carries
#: no `void`, no `defaulted` and no `missed_count`.
#:
#: `OQ-CWP-1720` carries the collision to the Product Owner and is OPEN. Its
#: own row states what ships meanwhile — *the screen says only what the code
#: does* — which is what `CWP-042` has always printed and what `CWP-063` now
#: prints too. Until that question is answered, **no wave M screen may tell a
#: customer a plan ENDS**; answering it is a ruling, not a lane's edit.
CONSEQUENCE_MISSED_WE_GET_IN_TOUCH = "missed_we_get_in_touch"


def plan_offer(account: Any, *, today: date) -> dict[str, Any]:
    """`CWP-063` — the offer, its schedule, and what accepting would do.

    ⚠ **THIS SCREEN CANNOT ACCEPT, DECLINE OR COUNTER, AND THE BODY SAYS SO
    RATHER THAN LETTING A SCREEN DISCOVER IT.** `BR-CWP-001` lists the six
    kinds of row the portal may write and a plan signature is none of them; G81
    fails the build on a seventh, and moving that list is a Product Owner
    ruling rather than a lane's edit. So all three controls carry `held: true`
    with their reason and `08-screen-layouts.md` already draws *Accept this
    plan ✓* held. The ruling is asked as `OQ-CWP-1568`.

    ⚠ **TWO FACTS THE OFFER SHOULD STATE AND THE RECORD DOES NOT HOLD**, each
    served as a NAMED ABSENCE rather than guessed:

      * **when the offer expires.** `US-CWP-053` TC-4 refuses acceptance after
        16 September and the ⓘ panel is supposed to say so on day one — but
        `payment_plans` has `proposed_on`, `agreement_sent_on`, `signed_on` and
        `closed_on` and **no expiry column at all**, and no tenant setting
        carries a standing offer window. `OQ-CWP-1566`.
      * **who set it up.** The story asks for *Sarah at the office* — *"a
        person's name, never a user id"* — and the only record of the clerk is
        the `payment_plan.rows_written` audit row, which is **pruned on a
        retention schedule** and which no module publishes a read of.
        `OQ-CWP-1567`.

    Neither is invented. A screen that showed today + 14 days would be stating
    a deadline this product cannot enforce, and one that showed a user id would
    breach B14 rule 31 twice over.
    """
    from apps.portal.seams import notifications_seam, payments_seam

    plan = payments_seam.plan_offer_for([account.pk], as_of=today)
    if plan is None:
        return {"offer": None}

    instalments = [
        {
            "number": row["seq"],
            "due_on": row["due_date"],
            "amount": row["amount"],
            "currency": row["currency"],
        }
        for row in plan["installments"]
    ]
    consequences = [
        CONSEQUENCE_LATE_FEES_STOP
        if plan["suspend_late_fees"]
        else CONSEQUENCE_LATE_FEES_CONTINUE
    ]
    if plan["suspend_disconnect"]:
        consequences.append(CONSEQUENCE_NO_DISCONNECT)
    # `BR-CWP-063` — *"a plan holds the arrears; it does not pause the current
    # month's bill"*. On the row since 2026-08-11 so no screen has to remember
    # it, and believing otherwise IS `DEF-061`.
    if plan["current_bill_still_due"]:
        consequences.append(CONSEQUENCE_NEW_BILLS_STILL_DUE)
    consequences.append(CONSEQUENCE_MISSED_WE_GET_IN_TOUCH)

    agreement = _plan_agreement_document(notifications_seam, account, plan_id=plan["id"])
    return {
        "offer": {
            #: ⚠ NO `id` — B14 rule 31. The session holds one offer at a time
            #: and nothing on this screen needs to name it to the server.
            "covers": plan["total_amount"],
            "paid_up_front": plan["down_payment"],
            "spread": plan["spread"],
            "currency": plan["currency"],
            "instalment_count": plan["installment_count"],
            "cadence": plan["cadence"],
            "offered_on": plan["agreement_sent_on"] or plan["proposed_on"],
            "first_payment_on": instalments[0]["due_on"] if instalments else None,
            "instalments": instalments,
            "consequences": consequences,
            #: ⚠ **THE EXPIRY IS STILL NULL AND STILL NAMED.** See the
            #: docstring — the column does not exist. A screen renders the
            #: sentence beside the reason and never a substitute value.
            "expires_on": None,
            "expires_on_unavailable": "OQ-CWP-1566",
            #: ⚠ **WHO OFFERED IT — `CR-085` `CPB-21`, `OQ-CWP-1567` CLOSED
            #: 2026-09-08 option (a).** This was `None` with the question's own
            #: id as its reason, because the clerk's identity lived only on an
            #: audit row that the retention schedule deletes. `payment_plans`
            #: now keeps it, so the name is a durable fact about the plan.
            #:
            #: ⚠ **A NAME, NEVER AN ID** (B14 rule 31). `payments` resolves the
            #: person — the portal may not read `identity` (`BR-CWP-004`, `G91`)
            #: — and the id it publishes alongside is dropped here rather than
            #: carried into a body a browser can read.
            #:
            #: ⚠ **`not_recorded` IS A REAL ANSWER AND NOT A FAILURE.** A plan
            #: written before the column existed, or written by a job with no
            #: person behind it, has nobody to name. The screen says so in the
            #: customer's own language (`portal.planOffer.noClerkName`) rather
            #: than inventing an office. No backfill was done, on purpose: the
            #: trail is pruned, so a backfill would be right for recent plans
            #: and fabricated for the rest.
            "offered_by": plan.get("offered_by_name"),
            "offered_by_unavailable": (
                None if plan.get("offered_by_name") else "not_recorded"
            ),
            #: `BR-CWP-045` — the EXISTING agreement document class, served and
            #: never re-rendered. Held with its reason where none was kept.
            "agreement": agreement,
            #: `US-CWP-053` TC-2/5/6 — all three refused at the edge, so the
            #: screen holds all three controls (`BR-CWP-056`) rather than
            #: offering a click that writes nothing (hard-won law 2 inverted).
            "actions_held": True,
            "actions_held_reason": "OQ-CWP-1568",
        }
    }


def _plan_agreement_document(
    notifications_seam: Any, account: Any, *, plan_id: str
) -> dict[str, Any]:
    """Is the signed agreement there to download, and if not, WHY not.

    Asked of the same published correspondence read `CWP-031` uses rather than
    of a second query: a plan agreement IS one of the documents that screen
    lists (`source_type = 'plan'`), and two reads of one fact are two answers.
    """
    rows = notifications_seam.account_correspondence(account_ids=[account.pk])
    if rows is None:
        return {
            "available": False,
            "reason": "the queue that records what was sent is not answering",
        }
    for row in rows:
        if row["source_type"] == "plan" and row["source_id"] == str(plan_id):
            return dict(row["stored_document"])
    return {"available": False, "reason": "document_not_stored"}


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 · `CWP-044` — LEVEL PAY (US-CWP-054)
# ═══════════════════════════════════════════════════════════════════════════


def level_pay(account: Any) -> dict[str, Any]:
    """`CWP-044` — twelve months, the average, the level, and the month it settles.

    ⚠ **ONE ACCOUNT, NAMED IN THE ADDRESS.** Budget billing is enrolled per
    ACCOUNT (`account_budget_status`), so a landlord holding four accounts has
    four answers — adding their bills together would produce a level for a
    CUSTOMER rather than for a property, which is not a thing this product can
    enrol. The account is the one the shell's switcher has open, intersected
    with the session's set in the query by `_account_in_set` before this is
    called (`BR-CWP-010`).

    ⚠ **NOTHING IS RECOMPUTED HERE** (`US-CWP-054` §7). The figure comes from
    `apps.billing.budget.compute_level`, which is ❄️ GT-24's own function, via
    the same three pieces the staff eligibility route composes.

    ⚠ **AND THE JOIN CONTROL IS HELD.** Enrolling is a write to
    `account_budget_status` and the portal may write rows of exactly six kinds;
    budget enrolment is none of them, which is why `08-screen-layouts.md` draws
    *Join level pay ✓* **held** on this screen.
    """
    from apps.portal.seams import billing_seam

    position = billing_seam.level_pay_position(account.pk)
    return {
        "level_pay": {
            **position,
            #: `BR-CWP-001` — enrolment is not one of the six writes.
            "join_held": True,
            "join_held_reason": "OQ-CWP-1568",
        }
    }
# CR-068 wave H · USAGE, READINGS AND EQUIPMENT — US-CWP-040 · 041 · 043
# ═══════════════════════════════════════════════════════════════════════════
#
# Screens `CWP-033`, `CWP-034`, `CWP-037`. Every figure below is a read of what
# the STAFF app already shows, in a customer's words — never a second
# arithmetic (`04-docs/05-modules/15-portal/12-reuse-map.md`).
#
# ⚠ **`BR-CWP-010` IS SATISFIED BY THE CALLER AND SAID AGAIN HERE.**
# `api._account_in_set` intersects the id with the session's set IN THE QUERY
# before any of these run, so an account outside it never reaches this module.
# Each read below still takes the ACCOUNT ROW rather than an id, so there is no
# signature here that a caller could hand a bare id to.

#: The two windows `CWP-033`'s segmented control offers — r10's own filter
#: vocabulary, and `monthly_usage_reads.ALLOWED_WINDOWS` is the authority.
#: Twelve is the DEFAULT because that is the Overview panel's window and the
#: Product Owner's own words: *"We are mainiting last 12 month usage details on
#: account"*.
USAGE_WINDOWS: tuple[int, ...] = (12, 24)
USAGE_DEFAULT_MONTHS = 12



def _with_metrics(
    series: dict[str, Any] | None, metrics: dict[str, Any] | None
) -> dict[str, Any] | None:
    """The chosen window's bars, carrying the TWENTY-FOUR-month metrics.

    ⚠ **`peak` AND `low` ARE NOT READ FROM HERE BY THE SCREEN.** `CWP-033`
    marks the highest and lowest of the bars it actually DRAWS, which is a
    property of the chart rather than of the account; a screen saying *lowest
    3,050 gal* about a month it is not showing would be wrong. What travels for
    the reader is the comparison with last year.
    """
    if series is None:
        return None
    return series if metrics is None else {**series, "metrics": metrics}


def _customer_series(row: dict[str, Any]) -> dict[str, Any]:
    """One service's months, with everything a CUSTOMER may not see removed.

    ⚠ **TWO THINGS COME OUT, AND NEITHER IS COSMETIC.** `service.id` is the
    platform `services` uuid — `tenancy_seam.enabled_services` already records
    that *"the id never reaches a customer screen (B14 rule 31)"* and strips it
    the same way — and `unit_absence.tracks` is an OPEN-QUESTION id, which B14
    rule 32 keeps out of anything a customer reads. The absence itself STAYS,
    because a window whose months disagree about their unit has no summable
    figure at all (hard rule 3) and the screen must say so.
    """
    service = row.get("service") or {}
    absence = row.get("unit_absence")
    return {
        **row,
        "service": {"code": service.get("code"), "name": service.get("name")},
        "unit_absence": ({"reason": absence.get("reason")} if absence else None),
    }

def account_usage(
    principal: Any,
    account: Any,
    *,
    months: int = USAGE_DEFAULT_MONTHS,
    today: date,
    locale: str | None = None,
) -> dict[str, Any]:
    """`CWP-033` — a year of usage, and the services that are NOT measured
    saying what they are billed on instead.

    ⚠ **`BR-CWP-073` IS THE WHOLE SCREEN AND IT IS AN ABSENCE.** Of the eleven
    services this product bills, only some produce a reading; the rest are
    charged on a share of another service's money or on equipment at the kerb.
    A portal that drew an empty chart for sewer *"will be asked where the
    missing graph is"*, so every service comes back with a `basis` and a
    `measured` flag, and only a measured one carries a series.

    ⚠ **THE BASIS IS THE COLUMN, NOT A PROXY FOR IT** —
    `tenant_services.billing_basis`, three values since `BR-TEN-1180`.
    `DEF-CWP-3765`: *"when a model has an exact column for a fact, read the
    column"*.

    ⚠ **NOTHING IS SUMMED ACROSS SERVICES** (hard rule 3). The payload carries
    one series per service, each with its own unit, exactly as the staff Usage
    tab does; there is no total and this read will never compose one.
    """
    window = months if months in USAGE_WINDOWS else USAGE_DEFAULT_MONTHS
    tenant_id = principal.tenant_id
    payload = metering_seam.usage_for_account(
        tenant_id, account.pk, months=window, today=today
    )

    #: ⚠ **THE COMPARISON NEEDS TWENTY-FOUR MONTHS EVEN WHEN THE CHART DRAWS
    #: TWELVE, AND IT IS THE PUBLISHED READ'S OWN ARITHMETIC RATHER THAN A
    #: SECOND ONE.** `_metrics` measures the year-on-year change as the last
    #: twelve months against the twelve BEFORE them, so a twelve-month payload
    #: has no prior year in it and honestly answers `no_prior_reads`.
    #: `US-CWP-040` TC-1 wants the comparison on the DEFAULT twelve-month view,
    #: so the wider payload is asked for and **only its `metrics` are read** —
    #: the bars still come from the window the customer chose. Two reads of one
    #: published function; nothing here computes a percentage.
    wider = (
        payload
        if window >= max(USAGE_WINDOWS)
        else metering_seam.usage_for_account(
            tenant_id, account.pk, months=max(USAGE_WINDOWS), today=today
        )
    )
    metrics_by_code = {
        (row.get("service") or {}).get("code"): row.get("metrics")
        for row in wider.get("series") or ()
    }

    bases = tenancy_seam.service_billing_bases(tenant_id)
    held = customers_seam.services_held(tenant_id, account.pk)
    equipment = (
        metering_seam.equipment_for_unit(tenant_id, account.unit_id, today=today)
        if account.unit_id
        else []
    )
    series_by_code = {
        row["service"]["code"]: _customer_series(row) for row in payload.get("series") or ()
    }

    services: list[dict[str, Any]] = []
    for row in held:
        code = row["code"]
        basis = bases.get(code, tenancy_seam.BASIS_METERED)
        measured = basis == tenancy_seam.BASIS_METERED
        services.append(
            {
                "code": code,
                #: The utility's OWN word for the service (`services_held` says
                #: why): rendered verbatim, never translated.
                "name": row["name"],
                #: `metered` · `share` · `capacity` — a VALUE the catalogue
                #: turns into a sentence, never a sentence from a server.
                "basis": basis,
                "measured": measured,
                #: ⚠ **A MEASURED SERVICE WITH NO STATED MONTH IS STILL
                #: MEASURED**, and its series is simply absent. That is a
                #: different claim from *not measured*, and conflating the two
                #: would tell a customer their water is not metered because
                #: nobody has read it yet.
                "series": (
                    _with_cost(
                        _with_metrics(series_by_code.get(code), metrics_by_code.get(code)),
                        principal,
                        account,
                        code,
                        today,
                    )
                    if measured
                    else None
                ),
                #: What an UNMEASURED service is billed on (`BR-CWP-073`).
                "billed_on": None if measured else _billed_on(code, basis, equipment),
            }
        )

    return {
        "as_of": today.isoformat(),
        "window": payload.get("window"),
        "windows": list(USAGE_WINDOWS),
        "services": services,
        #: ⚠ **`None` CLOSES THE TILE UP** (`BR-CWP-093`). Most days have no
        #: window open and a dash would be worse than nothing.
        "next_reading": (
            metering_seam.read_window_for_unit(tenant_id, account.unit_id, today=today)
            if account.unit_id
            else None
        ),
        #: `BR-CWP-095` — at most one tip, on and in season, or no slot at all.
        #: ⚠ **`usage`, NOT `portal_usage` (`DEF-CWP-4510`).** The screen names
        #: here must come from `published_content.TIP_SCREENS`, which is
        #: `portal_home · usage · usage_looks_high · send_a_reading · overdue ·
        #: every_reading` — and `create_tip` REFUSES anything else, so a tip
        #: aimed at `portal_usage` cannot exist and this lookup answered `None`
        #: on every tenant, forever. It could not fail a test either: `None` is
        #: ALSO the right answer on a day with no tip, so the dead lookup and
        #: the quiet day are the same output. Found in a browser, on the first
        #: tenant that ever had a Usage tip to show.
        "tip": tenancy_seam.tip_for_screen(tenant_id, "usage"),
        #: **THE ANSWER A CLERK PINNED TO THIS SCREEN** (`CWP-060`'s second
        #: placement, `DEF-CWP-3945`).
        #:
        #: ⚠ **`ALSO_SHOW_SCREENS` HAS BEEN `("bill", "usage", "overdue")`
        #: SINCE THE FEATURE SHIPPED AND `usage` WAS THE ONE THAT WENT
        #: NOWHERE.** The bill (`CWP-028`) and the overdue screen (`CWP-057`)
        #: each read this seam; this one never did, so a clerk who ticked *also
        #: show this on the Usage screen* published into nothing — the tick was
        #: accepted, the row was written, and no customer could ever see it.
        #: `DEF-CWP-3945`'s own `prevention` predicted exactly this (*"the bill
        #: and usage placements remain"*) and only the bill half had landed.
        #:
        #: ⚠ **IT RIDES ALONG RATHER THAN TAKING A ROUTE OF ITS OWN**, which
        #: is the posture `bill_detail` records: one screen, one read, and no
        #: second round trip on a page a customer opens to look at a chart.
        #:
        #: ⚠ **`None` IS THE ORDINARY ANSWER AND THE KEY IS STILL
        #: PRESENT** — the screen closes the slot up (`BR-CWP-093`), and a
        #: MISSING key would read as *"this build does not have the feature"*
        #: rather than *"nothing is attached"*. Those need to look different to
        #: the next lane, which is why this row stayed open for six days.
        "attached_answer": tenancy_seam.attached_answer(
            tenant_id, "usage", locale=locale
        ),
    }


def _with_cost(
    series: dict[str, Any] | None, principal: Any, account: Any, code: str, today: date
) -> dict[str, Any] | None:
    """`CPB-08` — what the LATEST stated month of this service actually cost.

    The blueprint's gap, in its own five words: *"Nothing joins a usage month to
    the bill line it produced."* The join is the ISSUED bill whose service
    period covers the month's LAST day, and every figure in the answer is that
    bill's own stored line — *"not a re-calculation"*, which is the
    specification's own requirement and also what keeps this off B4's ❄️ FROZEN
    ground entirely.

    ⚠ **ONE MONTH, NOT TWELVE.** A cost on every point would be twelve bill
    lookups per service per page load — four services is forty-eight — to fill a
    chart that has no room to print them. The question a person arrives with is
    *why does THIS one cost that*, and the latest stated month is the one they
    are looking at.

    ⚠ **THE LATEST STATED MONTH IS USUALLY UNBILLED, AND `None` IS THEREFORE THE
    COMMON ANSWER RATHER THAN THE EDGE.** Ana's August is read and not yet
    billed. The screen states the absence; it does not print `$0.00`.
    """
    if series is None:
        return series
    stated = [
        point
        for point in series.get("points") or ()
        if not point.get("absent") and point.get("quantity") is not None
    ]
    if not stated:
        return {**series, "cost": None}
    from apps.portal.seams import billing_seam

    latest = stated[-1].get("month") or ""
    #: ⚠ **THE LATEST STATED MONTH IS USUALLY NOT BILLED, SO A PANEL TIED TO IT
    #: ALONE WOULD READ *Not billed yet* ON EVERY ACCOUNT, FOREVER.** Measured on
    #: the live `pine-hill` demo: Ana's August is READ (800 kWh, from the reading
    #: of 14 August) and unbilled, while her June and July each cost `$95.50`.
    #: A screen that could only ever say *we cannot tell you* answers nothing —
    #: which is the same shape as `DEF-MET-4684` one panel along.
    #:
    #: So the walk goes BACK to the most recent month that HAS a bill, and the
    #: answer carries its own `month` so the panel names which one it is about.
    #: `is_latest_month` is what lets the screen add *"August is not billed
    #: yet"* above it rather than silently answering about a different month.
    #:
    #: ⚠ **BOUNDED AT THREE LOOKUPS.** Each step is a bill read; an unbounded
    #: walk over a twelve-month window would be twelve per service — forty-eight
    #: on Ana's four — to fill one panel. Three covers *this month unbilled, last
    #: month unbilled, the one before that billed*, which is the worst ordinary
    #: case; older than that and the honest answer is the absence.
    for point in reversed(stated[-3:]):
        month = point.get("month") or ""
        cost = billing_seam.usage_cost_for_month(
            [account.pk], service_code=code, month=month, today=today
        )
        if cost is not None:
            return {**series, "cost": {**cost, "is_latest_month": month == latest}}
    return {**series, "cost": None}


#: The service a `share` basis is a share OF. ⚠ **ONE ENTRY, AND IT IS THE ONLY
#: SHARE THE PRODUCT HAS** — `BR-RAT-015`: sewer is priced as a percentage of
#: the water usage charge. A second share service would add a row here; it is a
#: map rather than a rule so that a wrong guess is impossible: a `share` service
#: NOT in this map says only *not separately metered*, which is true of every
#: share, and names nothing it cannot name.
SHARE_OF: dict[str, str] = {"sewer": "water"}


def _billed_on(code: str, basis: str, equipment: list[dict[str, Any]]) -> dict[str, Any]:
    """What this unmeasured service is charged on — a SHAPE, not a sentence.

    ⚠ **`capacity` NAMES THE EQUIPMENT AND COUNTS IT** (`BR-RAT-090`: an
    unmetered service's quantity is a COUNT OF ITS ASSETS ON THE UNIT, observed
    and never typed). One cart reads *your 96 gal cart*; two read *2 × 96 gal
    cart*, which is also what the bill charges. The size-class NAME comes from
    the ratified vocabulary, so the panel never shows a customer `T-96`.

    ⚠ **AND WHEN THERE IS NO EQUIPMENT ON FILE THE PANEL SAYS SO PLAINLY.** A
    trash service with no cart recorded is a configuration problem a human
    should see — it is exactly the case `BR-RAT-090` bills as zero — so the
    shape carries `count: 0` and no equipment name, and the catalogue writes
    *not measured* without inventing a cart.
    """
    if basis == tenancy_seam.BASIS_SHARE:
        return {"kind": "share", "of": SHARE_OF.get(code)}
    mine = [row for row in equipment if row.get("service") == code]
    names = tenancy_seam.size_class_names(code)
    sized = next((row for row in mine if row.get("size_class") in names), None)
    return {
        "kind": "equipment",
        "count": len(mine),
        #: The size class as a person reads it — `96 gal cart`, never `T-96`.
        "size": names.get(sized.get("size_class")) if sized is not None else None,
        #: …and the tenant's own word for the thing, when no size is recorded.
        "equipment": mine[0]["kind"] if mine else None,
    }


def account_readings(
    principal: Any, account: Any, *, today: date, limit: int | None = None
) -> dict[str, Any]:
    """`CWP-034` — every reading, how it was taken, and why one was corrected.

    ⚠ **THE METHOD IS AS PROMINENT AS THE NUMBER** (`BR-CWP-071`) and it
    travels as a CODE the catalogue writes in words — *Read by a meter reader*,
    *ESTIMATED then corrected*, *You sent it in*. A server that shipped the
    English would make ten of the eleven catalogues impossible (B14 rule 35).

    ⚠ **THE BILL A READING FED IS MATCHED BY PERIOD, AND IS EMPTY WHEN NOTHING
    COVERS IT** (`US-CWP-041` TC-4). `meter_reads` carries no invoice
    reference; the join is the ISSUED bill whose service period contains the
    day the reading was taken, which is the correspondence a customer makes
    holding the paper. A reading nobody has billed shows an empty cell — never
    the nearest bill, which would say they were charged for it.

    ⚠ **ONE QUERY FOR THE BILLS, NOT ONE PER ROW.** Twenty-six readings would
    otherwise be twenty-six invoice lookups for a column.

    ⚠ **AND WHICH METER EACH READING IS OF (`DEF-CWP-3990`, 2026-09-05).**
    Metering serves the serial, the utility's own meter number and the service
    CODE; this joins the tenant's own NAME for that service onto it, from the
    one place a service is named (`tenancy.Service.name`, through the seam
    `_chips` already uses). *Water · 88-40219* is then one cell, and an account
    holding an electric meter and a water meter stops printing two readings on
    the same date with nothing to tell them apart.

    ⚠ **THE NAME IS THE TENANT'S DATA, NOT ENGLISH THIS SERVER WROTE** — the
    same standing that `service_name` already has on a bill line. B14 rule 35
    forbids shipping the words; it does not forbid shipping what the utility
    called its own service, which no catalogue could know.
    """
    from apps.portal.seams import billing_seam

    rows = metering_seam.readings_for_account(principal.tenant_id, account.pk, limit=limit)
    account_ids = [account.pk]
    covering: dict[str, str | None] = {}
    for row in rows:
        taken = row.get("taken_on")
        if taken and taken not in covering:
            covering[taken] = billing_seam.bill_number_covering(
                account_ids, date.fromisoformat(taken)
            )
    named = _service_names(principal.tenant_id)
    return {
        "readings": [
            {
                **row,
                "on_bill": covering.get(row.get("taken_on") or ""),
                "meter_service_name": named.get(row.get("meter_service") or ""),
            }
            for row in rows
        ],
        #: ⚠ **`CPB-09` — WHEN SOMEBODY IS COMING NEXT**, which is the question a
        #: person reading a list of past readings actually has. The blueprint
        #: named the gap exactly: *"The readings data carries no next-read date.
        #: The usage data does, and the screen shows it when it exists."* It is
        #: the SAME derivation the Usage tile reads, through the same seam, so
        #: two screens cannot disagree about one date.
        #:
        #: ⚠ **`None` IS THE ORDINARY ANSWER AND THE LINE CLOSES UP**
        #: (`BR-CWP-093`). Most days have no window open — the `pine-hill` demo
        #: has none at all — and a dash above a list reads as a date we lost.
        "next_read": (
            metering_seam.read_window_for_unit(principal.tenant_id, account.unit_id, today=today)
            if account.unit_id
            else None
        ),
    }


def account_readings_page(
    principal: Any, account: Any, *, params: Any
) -> tuple[list[dict[str, Any]], int]:
    """`CWP-034` — ONE PAGE of readings, **searched and sorted in SQL**.

    Answers `([...one page of rows...], count)` for `apps/portal/paging.windowed`.

    ⚠ **THIS REPLACES A READ OF EVERY READING THE ACCOUNT HAS EVER TAKEN
    (`DEF-CWP-5747`, `NFR-3`).** `account_readings` below was handed
    `limit=None` by its view, so an AMI deployment — an interval reading per
    meter per hour — served ~17,000 rows so that a browser could search, sort
    and slice them. The three predicates move WITH the page, because a server
    page over a browser search silently searches one page of N: a customer
    typing a meter serial that is on page 7 would be told they have no such
    reading.

    ⚠ **THE BILL WINDOWS ARE READ ONCE AND THE COLUMN IS NOW SQL.**
    `account_readings` asked `billing_seam.bill_number_covering` once per
    DISTINCT `taken_on` in its payload; this asks `bill_windows_for` once for
    the account and hands the periods to metering as plain dates, where they
    become a `CASE` that fills the cell, feeds the search and orders the sort.

    ⚠ **THE SERVICE TABS ARE THEIR OWN QUESTION, OVER THE WHOLE ACCOUNT.** The
    screen built them from the payload it held; over one page they would become
    *the services in the newest fifty rows*, and a quarterly-read electric
    meter would lose its tab with every test green.

    ⚠ **`BR-CWP-010` IS UNTOUCHED AND CANNOT BE WEAKENED HERE.** The account is
    already `_account_in_set`'s — intersected with the session's flat set in
    the QUERY by the view — and every query below is keyed on that ONE account
    id. Moving a filter into SQL narrows what is read; it adds no id to the
    set, and a landlord cannot reach a tenant's readings through a sort.
    """
    from apps.portal.seams import billing_seam

    windows = billing_seam.bill_windows_for([account.pk])
    answer = metering_seam.readings_page(
        principal.tenant_id,
        account.pk,
        page=params.page,
        per=params.per,
        q=params.q,
        sort=params.sort,
        dir=params.dir,
        service=params.filters.get("service") or None,
        bill_windows=windows,
    )
    named = _service_names(principal.tenant_id)
    rows = [
        {**row, "meter_service_name": named.get(row.get("meter_service") or "")}
        for row in answer["readings"]
    ]
    return rows, answer["count"]


def account_readings_frame(principal: Any, account: Any, *, today: date) -> dict[str, Any]:
    """Everything on `CWP-034` that is NOT a row — the meter tabs and the next
    read — answered over the WHOLE account rather than over a page.

    ⚠ **SEPARATE FROM THE PAGE BECAUSE IT IS A DIFFERENT QUESTION**
    (`DEF-CWP-5747`). `Readings.tsx` built its tabs from the rows it held, and
    the rows are now one page: tabs built from a page would read *the services
    in the newest fifty readings*, so a meter read once a quarter would lose
    its tab and a customer would be told they have no water readings. It is
    also why this is not inside the page fetch — `paging.windowed` re-asks the
    page once when somebody types `?page=999`, and the tabs must not be
    recomputed to answer that.

    ⚠ **THE TENANT'S OWN WORD FOR EACH TAB IS JOINED HERE** for the same reason
    the row's is: `tenancy.Service.name` is the one place a service is named,
    and shipping English from metering would make ten of the eleven catalogues
    impossible (B14 rule 35).
    """
    named = _service_names(principal.tenant_id)
    return {
        "services": [
            {**one, "name": one.get("name") or named.get(one.get("code") or "")}
            for one in metering_seam.reading_services(principal.tenant_id, account.pk)
        ],
        #: `CPB-09` — unchanged, and still `None` on most days (`BR-CWP-093`).
        "next_read": (
            metering_seam.read_window_for_unit(principal.tenant_id, account.unit_id, today=today)
            if account.unit_id
            else None
        ),
        #: `US-CWP-042` TC-7 (`DEF-CWP-10175`) — whether *Send a reading*
        #: appears at all. OFF means the control is ABSENT, never greyed
        #: (`BR-CWP-093`); the write refuses in the same breath (`BR-CWP-002`).
        "self_read_enabled": self_read_offered(principal.tenant_id, account),
    }


def self_read_offered(tenant_id: Any, account: Any) -> bool:
    """The self-read door is open for this account: the portal is live, the
    utility switched self-read ON (`CR-068` R8 — off for a new tenant), and the
    account names a unit with a meter on it to read. A master account anchors
    on the premises with no unit (`BR-CUS-1010`) and is never offered it."""
    settings = settings_view(tenant_id)
    return bool(settings["is_live"] and settings["self_read_enabled"] and account.unit_id)


def self_read_frame(principal: Any, account: Any, *, today: date) -> dict[str, Any]:
    """`GET accounts/{id}/readings/send` — `CWP-035`, what the form draws.

    ⚠ **SWITCHED OFF IS A REFUSAL, NOT AN EMPTY FORM** (`US-CWP-042` TC-7:
    *the screen is unreachable AND the endpoint refuses*). An empty meter list
    under an *off* switch would read as *you have no meters*, which is a
    different and false fact.

    ⚠ **THE TENANT'S OWN WORD FOR EACH SERVICE IS JOINED HERE** (B14 rule 35),
    the way `account_readings_frame` joins it for the tabs.
    """
    if not self_read_offered(principal.tenant_id, account):
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-002",
            message_key="portal.selfRead.notOffered",
        )
    named = _service_names(principal.tenant_id)
    meters = metering_seam.self_read_meters(principal.tenant_id, account.unit_id, today=today)
    return {
        "today": today.isoformat(),
        "meters": [
            {**meter, "service_name": named.get(meter.get("service") or "")} for meter in meters
        ],
        "window": metering_seam.read_window_for_unit(
            principal.tenant_id, account.unit_id, today=today
        ),
    }


def account_equipment(principal: Any, account: Any, *, today: date) -> dict[str, Any]:
    """`CWP-037` — the meters, carts and devices on this customer's own unit.

    ⚠ **ONLY THIS UNIT'S** (`US-CWP-043` TC-4). The list is the unit's current
    assignments, so a sub-meter on the flat next door is absent by construction
    rather than by a filter somebody has to remember.

    ⚠ **A MASTER ACCOUNT NAMES NO UNIT AND ANSWERS `[]`** — `BR-CUS-1010`: a
    master anchors on the PREMISES with `unit_id` NULL. An empty list is the
    honest answer for it, and the screen states what would fill it rather than
    drawing a blank table (`BR-CWP-093`, TC-8).

    ⚠ **AND EACH ROW IS NAMED FOR WHAT IT IS (`DEF-CWP-3991`, 2026-09-05).**
    The registry serves `kind` — the tenant's own word for the TYPE of thing,
    which is *Meter* out of the seed — and the service it stands on as a code.
    Two meters at one property therefore both read *Meter* and only the serial
    told them apart. The tenant's own name for the service is joined here, so
    the screen can write *Water Meter* and *Refuse cart* the way the drawing
    does. `None` is ordinary — a device on no service point keeps its bare kind.
    """
    rows = (
        metering_seam.equipment_for_unit(principal.tenant_id, account.unit_id, today=today)
        if account.unit_id
        else []
    )
    named = _service_names(principal.tenant_id)
    bases = tenancy_seam.service_billing_bases(principal.tenant_id)
    #: ⚠ **ONE BILL READ PER SERVICE, NOT ONE PER ROW** (`CPB-10`). A property
    #: with three carts asks about `trash` once. `standing_charge_line` opens the
    #: latest bill, so a row-by-row loop would open it three times for one answer.
    charges: dict[str, dict[str, Any] | None] = {}
    from apps.portal.seams import billing_seam

    for row in rows:
        code = row.get("service") or ""
        if not code or code in charges:
            continue
        if _asset_charge_basis(bases.get(code, tenancy_seam.BASIS_METERED)) != "per_item":
            charges[code] = None
            continue
        charges[code] = billing_seam.standing_charge_line(
            [account.pk], service_code=code, today=today
        )
    #: ⚠ **THE SIZE CLASS AS A PERSON READS IT, NOT THE CODE** (`DEF-CWP-4848`,
    #: `CR-085` step 2). `equipment_on_unit` serves `size_class` as a bare code
    #: — `W-58`, `FL-2`, `CART-96` — and B14 rule 32 keeps an internal code off
    #: clerk-facing copy, so the screen has never drawn it at all. The ratified
    #: vocabulary is what names it (`tenancy_seam.size_class_names`), and it is
    #: the SAME call `_billed_on` already makes one screen along: two answers to
    #: *what is a `FL-2`* is the drift `DEF-CWP-3655` records.
    #:
    #: ⚠ **IT MATTERS MOST ON FIRE.** CLAUDE.md's fire rule is that the SIZE
    #: CLASS PICKS THE PRICE and the COUNT multiplies it, so a fire line is the
    #: one row on this screen carrying a monthly charge whose figure cannot be
    #: checked against anything else the screen says. The drawing's own note is
    #: *"Size is stated in inches, as the customer's plumber would."*
    #:
    #: ⚠ **ONE LOOKUP PER SERVICE, NOT ONE PER ROW** — the same shape `charges`
    #: above takes, and for the same reason: three carts ask about `trash` once.
    #: An unruled service answers an empty map (the seam swallows its own raise)
    #: and the row then carries `None`, which the screen closes up rather than
    #: dashing (`BR-CWP-093`).
    sizes: dict[str, dict[str, str]] = {}
    for row in rows:
        code = row.get("service") or ""
        if not code or code in sizes:
            continue
        sizes[code] = tenancy_seam.size_class_names(code)
    return {
        "as_of": today.isoformat(),
        "equipment": [_equipment_row(row, named, bases, charges, sizes) for row in rows],
    }


#: How an asset's own service is charged, which decides whether the THING has a
#: monthly figure at all (`CPB-10`).
#:
#: ⚠ **READ FROM `tenant_services.billing_basis`, AN EXISTING COLUMN**, and never
#: guessed from the kind of thing the asset is (`DEF-CWP-3765`). A water meter is
#: not charged for — the WATER is — and a cart or a fire line IS, because
#: `BR-RAT-090` prices those services as a count of exactly these assets.
def _asset_charge_basis(basis: str) -> str:
    return "per_item" if basis == tenancy_seam.BASIS_CAPACITY else "usage_only"


def _equipment_row(
    row: dict[str, Any],
    named: dict[str, str],
    bases: dict[str, str],
    charges: dict[str, dict[str, Any] | None],
    sizes: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """One line of the drawing's `Equipment · Reference · Installed · Whose · Monthly`.

    ⚠ **`monthly_charge` AND `charge_basis` ARE TWO DIFFERENT ABSENCES AND THE
    SCREEN MUST TELL THEM APART.** *This kind of thing carries no monthly charge*
    (a meter — the drawing writes **No charge**) is a FACT; *we cannot find what
    you were charged for it* (a capacity service whose latest bill has no such
    line) is a GAP. Collapsing both to `null` would print *No charge* over a cart
    the customer is in fact paying for.
    """
    code = row.get("service") or ""
    basis = bases.get(code, tenancy_seam.BASIS_METERED)
    charge = charges.get(code)
    return {
        **row,
        "service_name": named.get(code, ""),
        #: `usage_only` · `per_item`.
        "charge_basis": _asset_charge_basis(basis),
        #: The bill's own rate, at two places (hard rule 2), or `None`.
        "monthly_charge": billing_seam_per_item(charge),
        #: The bill the figure came off, so a customer can go and check it.
        #: ⚠ Its NUMBER — the reference on their own paper — never an id
        #: (B14 rule 31).
        "monthly_charge_bill": (charge or {}).get("bill_number"),
        #: `DEF-CWP-4848` — **the ratified NAME of `size_class`**, or `None`.
        #: `size_class` itself stays on the row because the walkthroughs and the
        #: staff-side callers key on the code; what the SCREEN draws is this.
        #: ⚠ A code with no ratified name answers `None` rather than falling
        #: back to itself: printing `FL-2` to a customer is the breach this
        #: field exists to avoid, and an absence the screen closes up is the
        #: honest alternative.
        "size_class_name": (sizes or {}).get(code, {}).get(row.get("size_class") or ""),
    }


def billing_seam_per_item(line: dict[str, Any] | None) -> str | None:
    from apps.portal.seams import billing_seam

    return billing_seam.per_item_monthly(line)


def _service_names(tenant_id: Any) -> dict[str, str]:
    """`{service code: the tenant's own name for it}` — ONE query.

    ⚠ **THE UTILITY'S OWN WORD, AND NOT `front`'S CHIP LIST.** `_chips` reads
    the same seam and then keeps only `front_page_service_ids` — the handful the
    utility ticked for its front page, in the order it chose. Using that as a
    code→name map here would have been free and silently wrong: a service the
    tenant sells but did not tick would resolve to nothing, and a meter would
    lose its name for a reason nobody could see from the screen.
    """
    return {row["code"]: row["name"] for row in tenancy_seam.enabled_services(tenant_id)}


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 · `CWP-046` — WHAT DO YOU NEED (US-CWP-060)
# ═══════════════════════════════════════════════════════════════════════════

#: The six cards `US-CWP-060` §1 names, in its own order, with the screen each
#: leads to — **the SEED a tenant is given, never the answer.** A utility that
#: has configured its own list gets its own list (TC-8), exactly as
#: `DEFAULT_QUICK_SERVICES` works one screen along, and for the same reason: a
#: read never writes.
#:
#: ⚠ **`screen` IS `None` ON THREE OF THE SIX TODAY AND THAT IS THE HONEST
#: STATE, NOT A PLACEHOLDER.** `CWP-048` (moving out), the move-home form and
#: the add-a-service form are not built; a card that linked to one of them
#: would be hard-won law 2 exactly — a link with no screen behind it. The card
#: renders HELD with its reason instead, so a customer can see the utility does
#: this and can tell the online route is not open yet.
#:
#: ⚠ **IT SAID *FOUR* UNTIL `DEF-CWP-<something_else>` (2026-09-05), AND THE
#: FOURTH WAS A SHUT DOOR OVER A LIVE SCREEN FOR A DAY.** `something_else` was
#: held at 00:14 because *ask us something* did not exist; `CWP-054` landed at
#: **01:27, seventy-three minutes later**, and the card stayed grey — a
#: customer reading *"Not online yet — ring us"* over a routed, tested screen
#: whose own heading is ASK US SOMETHING. That is `DEF-CWP-3925`'s shape for
#: the third time: **landing a screen and releasing the control that points at
#: it are two acts, and only the first one feels like the work.** The cure is
#: `ERRAND_HELD_UNTIL` below — the hold's EXPIRY CONDITION, written down in the
#: same place as the hold — and the test that reads it.
#:
#: ⚠ **`label` AND `hint` ARE CATALOGUE KEYS AND NOT ENGLISH** (B14 rule 35).
#: A tenant that overrides a card may put its own words there, and the screen
#: renders an unknown key as the text itself — the posture
#: `quick_service_categories` already takes.
DEFAULT_REQUEST_ERRANDS: tuple[dict[str, Any], ...] = (
    {"code": "move_out", "label": "portal.errand.move_out.title", "hint": "portal.errand.move_out.hint", "screen": None},
    {"code": "move_home", "label": "portal.errand.move_home.title", "hint": "portal.errand.move_home.hint", "screen": None},
    {"code": "add_service", "label": "portal.errand.add_service.title", "hint": "portal.errand.add_service.hint", "screen": None},
    {"code": "stop_for_a_while", "label": "portal.errand.stop_for_a_while.title", "hint": "portal.errand.stop_for_a_while.hint", "screen": "CWP-052"},
    {"code": "report_problem", "label": "portal.errand.report_problem.title", "hint": "portal.errand.report_problem.hint", "screen": "CWP-006"},
    {"code": "something_else", "label": "portal.errand.something_else.title", "hint": "portal.errand.something_else.hint", "screen": "CWP-054"},
)

#: **THE EXPIRY CONDITION OF EVERY HOLD ABOVE, AND THE ONLY REASON THIS DICT
#: EXISTS** — hard-won law 2's mirror clause, ratified 2026-09-05: *"when you
#: write a hold, write the test that fires when the hold expires, in the same
#: commit."*
#:
#: `code` → the `CWP-###` whose ARRIVAL releases that card, or `None` where no
#: screen has been allocated for the errand at all. A held card is a promise
#: nobody is keeping unless something goes RED on the day it comes due, and
#: nothing in this repo reads rendered output — so the promise is written as
#: DATA here and `tests/test_cwp_holds_expire.py` reads it against the front
#: end's own screen register. The day `CWP-048` appears in `screenIds.ts` that
#: test fails and names *move_out*.
#:
#: ⚠ **A `None` IS A HOLD WITH NO EXPIRY AND IT IS THE WEAKER KIND.** Nothing
#: can go red for the move-home and add-a-service forms because `CR-068` §9
#: allocates no id for either — they are named in prose and nowhere else. The
#: entry is kept so the set of held codes and the set of stated expiries stay
#: equal, which is the part a test CAN enforce: a lane adding a seventh card
#: that is held has to say here what would release it.
ERRAND_HELD_UNTIL: dict[str, str | None] = {
    "move_out": "CWP-048",
    "move_home": None,
    "add_service": None,
}

#: `CWP-###` → the portal sub-path that screen is served at. **Read by the
#: screen, so a card's destination is the SERVER's answer**, and kept here
#: rather than in the front end because the same map decides whether a card is
#: a link or a held control. `routing/screenIds.ts` is the front end's half and
#: `G82` refuses a route with no row there, so the two cannot drift into naming
#: different screens.
ERRAND_ROUTE: dict[str, str] = {
    "CWP-052": "/stop-or-restart",
    "CWP-006": "/report",
    "CWP-054": "/ask-a-question",
}

#: What a card whose screen is not built says, as a CODE the catalogue writes
#: into five or six words (B14 rule 33, `BR-CWP-056`).
ERRAND_HELD = "not_online_yet"


def request_errands(tenant_id: Any) -> list[dict[str, Any]]:
    """`CWP-046`'s six cards — the utility's own list, or the seeded six.

    ⚠ **ABSENT ENTIRELY WHEN REQUESTS ARE SWITCHED OFF** (`US-CWP-060` TC-5),
    the posture `quick_service_categories` takes for the same switch: absent,
    never greyed (`BR-CWP-093`). The endpoint refuses in the same breath, so the
    hub is unreachable rather than empty.
    """
    settings = settings_view(tenant_id)
    if not settings["is_live"] or not settings["requests_enabled"]:
        return []
    configured = settings.get("request_errands") or []
    rows = configured if configured else list(DEFAULT_REQUEST_ERRANDS)
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("code"):
            continue
        screen = row.get("screen") or None
        to = ERRAND_ROUTE.get(str(screen)) if screen else None
        out.append(
            {
                "code": str(row["code"]),
                "label": row.get("label"),
                "hint": row.get("hint"),
                #: The sub-path, or `None` with a reason — never a dead link.
                "to": to,
                "held_reason": None if to else ERRAND_HELD,
            }
        )
    return out


def errand_label_for(tenant_id: Any, code: Any) -> str | None:
    """The card's own label, or None when this utility does not offer it.

    The check `POST /portal/requests` makes before it writes anything, so a
    caller cannot raise a request under a card the utility never published —
    `quick_service_category`'s shape, one screen along.
    """
    wanted = str(code or "")
    for row in request_errands(tenant_id):
        if row["code"] == wanted:
            return str(row["label"] or wanted)
    return None


def request_hub(principal: Any) -> dict[str, Any]:
    """`GET /portal/requests` — the six cards and this customer's open asks.

    ⚠ **WHICH REQUESTS ARE *MINE* IS `customers_seam.my_requests`' ANSWER AND
    NOT A SECOND ONE.** A portal service request carries no account BY RULE
    (`BR-CWP-026` — *"a public form may create work and may never change an
    account"*), so there is no account-scoped read to reuse and the link has to
    be made out of what the row does carry. `my_requests` makes it out of the
    tenant, the channel and any phone one of this login's own accounts holds —
    three clauses, all three in the query (`BR-CWP-010`, `G96`).

    ⚠ **THIS SCREEN HAD ITS OWN VERSION OF THAT READ FOR AN HOUR, MATCHING ON
    THE EMAIL INSTEAD, AND IT WAS DELETED AT MERGE RATHER THAN KEPT.** Two
    lanes in two worktrees each wrote it because neither could see the other,
    which is the same shape law 11 records for ids. Two reads of one fact are
    two answers — `12-reuse-map.md`'s *"a clerk and a customer arguing with
    each other on the phone"* — so the one that landed first survives.

    ⚠ **WHAT THE LINK CANNOT SEE IS STATED ON THE WIRE** (`OQ-CWP-1680`): a
    request a CLERK raised at the counter carries no phone this login holds, so
    it is invisible here. `lists_only_portal_requests` says so and the screen
    says it in words.

    ⚠ **`status` TRAVELS AS THE STATE CODE AND THE CATALOGUE WRITES THE WORD**
    (B14 rule 35). *Waiting for two documents* in eleven languages is eleven
    catalogue lines; one English sentence from a server is ten screens that
    cannot be translated.

    ⚠ **NO ROW ID CROSSES THIS WIRE** (B14 rule 31). `SR-26-0056` is the
    reference a customer would read out on the telephone, and it is the only
    handle the payload carries.
    """
    from apps.portal.seams import customers_seam as seam

    errands = request_errands(principal.tenant_id)
    phones = seam.contact_phones(
        principal.tenant_id, list(getattr(principal, "account_ids", ()) or ())
    )
    rows = list(seam.my_requests(principal.tenant_id, phones=phones))
    wanted = seam.documents_still_wanted(principal.tenant_id, [row.pk for row in rows])
    open_rows = [row for row in rows if row.state not in seam.CLOSED_REQUEST_STATES]
    closed_rows = [row for row in rows if row.state in seam.CLOSED_REQUEST_STATES]

    def _row(row: Any) -> dict[str, Any]:
        return {
            "reference": row.request_no,
            #: ⚠ **WHAT THIS REQUEST IS, DERIVED — AND IT IS THE COLUMN A
            #: CUSTOMER READS FIRST** (`CR-085` `CPB-05`, `DEF-CWP-4198`).
            #: `None` where the customer's own words ARE the answer.
            "title": seam.request_kind(row.what_they_said),
            #: What the customer asked for, in the words they were shown.
            #: `service_requests` has no category column (`DEF-CWP-3701`),
            #: so this is what they typed or the card's own label, which is
            #: what the write put there.
            "what": row.what_they_said,
            "raised_on": row.received_at.date().isoformat() if row.received_at else None,
            "status": row.state,
            #: `US-CWP-060` TC-4 — the COUNT, so the catalogue can say
            #: *we need two documents* through `_one` / `_other`.
            "documents_wanted": wanted.get(str(row.pk), 0),
        }

    return {
        "errands": errands,
        "open_requests": [_row(row) for row in open_rows],
        #: ⚠ **THE ONES THAT ARE FINISHED, AND THEY HAD NO DOOR AT ALL**
        #: (`CR-085` `CPB-11`, `DEF-CWP-4203`). `my_requests` has always read
        #: every request this login raised and this function threw the closed
        #: ones away, so the moment a request was completed, refused, closed or
        #: **withdrawn by the customer themselves**, it left their world: no
        #: list, no link, no way back to the reference they had been given.
        #: Measured on the live demo on 2026-09-08 — a query raised and then
        #: withdrawn left `open_requests` empty with the row still on file.
        "closed_requests": [_row(row) for row in closed_rows],
        #: ⚠ **STATED ON THE WIRE, BECAUSE THE SCREEN MAY NOT IMPLY OTHERWISE.**
        #: A request a clerk raised at the counter is not in the lists above and
        #: cannot be (`OQ-CWP-1680`), so the screen says what this list holds
        #: rather than letting a customer read it as *everything I have asked*.
        "lists_only_portal_requests": True,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 · `CWP-052` — STOP OR RESTART SERVICE (US-CWP-062)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE WHOLE SCREEN IS ONE COMPARISON AND EVERY FIGURE IN IT IS READ.** The
# standing charge is the plan's, through `apps.rating.seams.base_charge_for` —
# the ONE implementation of `BR-RAT-088`'s precedence, and `DEF-154` is what
# having two cost. The connection fee and the deposit are `rating_seam`'s
# existing `connection_fees` and `deposit`, which `CWP-008` has quoted to
# strangers since wave C. **The portal's own arithmetic is two multiplications
# and one comparison, and that is all it may ever be.**
#
# ⚠ **AND THE VERDICT IS COMPUTED, NEVER HARDCODED** (`US-CWP-062` §7: *"a
# screen that always says stopping is cheaper is wrong for a long absence"*).
# Worked, on the story's own figures: five months × `$18.50` = **`$92.50`**
# against `$185.00 + $150.00` = **`$335.00`**, so stopping is cheaper; at
# nineteen months `19 × $18.50` = **`$351.50`**, which exceeds `$335.00`, and
# the screen must then say CLOSING is cheaper. The crossover is
# `$335.00 ÷ $18.50 = 18.1` months.

#: The two answers, and the third that is a refusal rather than a verdict.
CHEAPER_STOPPING = "stopping"
CHEAPER_CLOSING = "closing"

#: ⚠ **A COMPARISON WITH A MISSING SIDE IS NOT A COMPARISON** (`US-CWP-062`
#: TC-8). Each of these is carried instead of a verdict, and the screen says so
#: in words — never `$0.00` presented as a saving.
NO_VERDICT_NO_STANDING = "no_standing_charge"
NO_VERDICT_NO_RESTART_COST = "no_restart_cost"


def _months_between(start: date, end: date) -> int:
    """Whole months from `start` to `end`, counted the way a bill run counts.

    ⚠ **CALENDAR MONTHS, NOT DAYS ÷ 30.** A standing charge is charged once a
    billing cycle, so *1 November to 1 April* is **five** charges and not
    `151 ÷ 30 = 5.03`. The day of the month is what decides the last one: a stop
    that ends on the 20th has still had that month's charge, which is why the
    comparison rounds UP on a part month rather than dropping it.
    """
    whole = (end.year - start.year) * 12 + (end.month - start.month)
    return whole + 1 if end.day > start.day else whole


def stop_or_restart(
    principal: Any, account: Any, *, stop_from: date, start_again: date | None, today: date
) -> dict[str, Any]:
    """`CWP-052` — what stopping costs, what closing costs, and which is less.

    ⚠ **`account_stays_open` IS ON THE WIRE AND IS NEVER INFERRED**
    (`BR-CWP-080`, `US-CWP-062` TC-4). *"It prevents the most expensive
    misunderstanding in the product: assuming a stopped supply stops the
    bill."* A screen that had to derive that sentence could stop saying it.

    ⚠ **A RESTART DATE IS OPTIONAL AND ITS ABSENCE IS NOT AN OPEN-ENDED
    STOP PRICED AT ZERO.** With no date there are no months to multiply, so
    there is no cost of stopping and therefore no verdict — the screen asks for
    a date rather than guessing one.

    ⚠ **THE FEES ARE TODAY'S** (`US-CWP-012` TC-6's rule, inherited): a plan
    whose window has not opened quotes nothing, so a price dated for next
    quarter cannot reach this screen and be compared against a charge that is
    running now.
    """
    from apps.portal.seams import rating_seam

    tenant_id = principal.tenant_id
    plan_id = rating_seam.current_plan_id(tenant_id, account.unit_id)
    services = customers_seam.services_held(tenant_id, account.pk)
    codes = [row["code"] for row in services]
    account_type = getattr(account, "account_type", None)
    standing = rating_seam.standing_charge_monthly(
        tenant_id,
        rate_plan_id=plan_id,
        service_codes=codes,
        customer_class=getattr(account_type, "code", None),
        on=today,
    )

    months = (
        _months_between(stop_from, start_again)
        if start_again is not None and start_again > stop_from
        else None
    )
    monthly = standing["amount"]
    cost_of_stopping = (
        (monthly * Decimal(months)) if (monthly is not None and months is not None) else None
    )

    fees = rating_seam.connection_fees(tenant_id, plan_id, on=today) or {}
    #: The plan-wide charge (`""`) plus one per service this account holds —
    #: the same narrowing the standing charge takes, for the same reason.
    wanted = ["", *codes]
    connection_fee = sum(
        (Decimal(fees[key]) for key in wanted if key in fees), Decimal("0")
    ) if any(key in fees for key in wanted) else None
    deposit = rating_seam.deposit(
        tenant_id, plan_id, getattr(account, "account_type_id", None)
    )
    cost_of_closing = (
        (connection_fee or Decimal("0")) + (deposit or Decimal("0"))
        if (connection_fee is not None or deposit is not None)
        else None
    )

    cheaper: str | None = None
    no_verdict: str | None = None
    if cost_of_stopping is None:
        no_verdict = (
            NO_VERDICT_NO_STANDING if monthly is None else NO_VERDICT_NO_RESTART_COST
        )
    elif cost_of_closing is None:
        no_verdict = NO_VERDICT_NO_RESTART_COST
    else:
        cheaper = CHEAPER_STOPPING if cost_of_stopping <= cost_of_closing else CHEAPER_CLOSING

    return {
        "stop_from": stop_from.isoformat(),
        "start_again": start_again.isoformat() if start_again is not None else None,
        "months": months,
        #: ⚠ `BR-CWP-080`, said rather than implied.
        "account_stays_open": True,
        "standing_charge_monthly": _money(monthly),
        "standing_charge_unavailable": standing["unavailable"],
        "cost_of_stopping": _money(cost_of_stopping),
        "connection_fee": _money(connection_fee),
        "new_deposit": _money(deposit),
        "cost_of_closing": _money(cost_of_closing),
        "cheaper": cheaper,
        "no_verdict": no_verdict,
        #: ⚠ **THE ACCOUNT'S OWN CURRENCY, WHICH IS THE MONEY'S PARTNER**
        #: (CLAUDE.md hard rule 2). Not a tenant-wide setting: every other money
        #: field this module serves travels beside the currency of the row it
        #: came from, and a screen that took one from somewhere else could print
        #: a dollar sign over a figure held in another currency.
        "currency": getattr(account, "currency", None),
        "services": services,
    }


def _money(value: Any) -> str | None:
    """Four decimals on the wire, two on the screen (CLAUDE.md hard rule 2).

    `None` stays `None`. A missing figure that became `"0.0000"` here is exactly
    the `$0.00`-as-a-saving `US-CWP-062` TC-8 forbids, one layer lower down
    where no screen could see it.
    """
    return None if value is None else str(Decimal(value).quantize(Decimal("0.0001")))


# ═══════════════════════════════════════════════════════════════════════════
# CWP-002 · QUICK PAY — FIND THE BILL (US-CWP-003, and the lockout US-CWP-002
# puts in front of it)
#
# ⚠ **THIS IS THE ONE PLACE ON THE GUEST SURFACE WHERE MONEY IS SHOWN TO
# SOMEBODY WHO HAS PROVED NOTHING**, and `guest_fields.py` reserved its
# allow-list before this code existed precisely so the wave that builds the
# response would not also be the wave that decides what it may disclose.
# `BR-CWP-019` is the exception and it is narrow: the amount owing and a MASKED
# name, *"and nothing else about the account — not the other bills, not the
# usage, not the history."*
# ═══════════════════════════════════════════════════════════════════════════

#: The four words `CWP-002` may answer with. WORDS, not sentences: the screen
#: writes the sentence in its own language (B14 rule 35), and a server that
#: assembled one would ship English to ten of the eleven catalogues.
BILL_PAYABLE = "payable"
BILL_SETTLED = "settled"
BILL_CANCELLED = "cancelled"
BILL_REPLACED = "replaced"

#: How many dots stand in for a surname. FIXED, and that is `US-CWP-004` TC-4:
#: *"A surname of one character, 'M. O' — masks without revealing length, the
#: mask is fixed-width, not one dot per letter."* One dot per letter would turn
#: the mask into a length oracle on a public endpoint.
NAME_MASK = "•" * 6


def masked_name(display_name: Any) -> str:
    """`Maria Alvarez` -> `M. A••••••` (`BR-CWP-020`).

    ⚠ **THE POINT OF IT IS CONFIRMATION, NOT IDENTIFICATION** (`US-CWP-004`
    §1). Whoever is holding the bill can tell they have the right one; the page
    does not disclose who lives there. A bill goes astray, gets photographed,
    gets left in a hallway — *"showing the balance is fine; showing the
    customer is not."*

    ⚠ **MASKED ON THE SERVER, ALWAYS** (`US-CWP-004` §5, verbatim: *"Never send
    the full name and mask in the browser"*). A browser that received the full
    name has already been told it, whatever it draws.

    ⚠ **AND IT IS HERE RATHER THAN BESIDE `mask_phone` AND `mask_email`**,
    which is not where it belongs and is not a choice: `credentials.py` is
    `HUMAN-OWNED` (`10-scripts/gates/human_owned.txt`) and a lane may not add
    to it. Stated so the next reader knows it is a constraint and not an
    oversight.
    """
    parts = [part for part in str(display_name or "").replace(",", " ").split() if part]
    if not parts:
        return NAME_MASK
    first = parts[0][:1].upper()
    last = parts[-1][:1].upper()
    return f"{first}. {last}{NAME_MASK}"


def _squashed_postcode(value: Any) -> str:
    """`" 78702 "` and `"78702"` are one value; `78702` and `78704` are not."""
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def bill_lookup(tenant_id: Any, *, bill_number: Any, postcode: Any) -> dict[str, Any] | None:
    """`POST /public/bills/lookup` — `CWP-002`, and `None` for every miss.

    **THE TWO FACTS ARE BOTH PRINTED ON THE PAPER** (`US-CWP-003` §1) and the
    pair is the whole security story: *"a bill number alone is a short
    sequential string; the pair is what stops the form being a way to enumerate
    accounts"* (`BR-CWP-018`, `BR-CWP-025`).

    ⚠ **EVERY MISS RETURNS `None` AND THE EDGE ANSWERS ONE SENTENCE FOR ALL OF
    THEM** (`TC-2`, `TC-3`, `TC-6`). An unknown number, a real number with the
    wrong postcode, a draft, and another utility's number are byte-identical to
    a caller — *"a different message would confirm the bill number exists."*
    That is why the postcode is compared HERE rather than by the caller: a
    function that returned the bill and let somebody else decide would already
    have handed a stranger the answer.

    ⚠ **A MATCH IS NOT AN OPEN DOOR.** What comes back is `BR-CWP-019`'s whole
    list and `guest_fields.py` holds it as data: the amount, its currency, one
    of four status words, the due date, the masked name, and — when the bill was
    corrected — the number that replaced it. No account number, no address, no
    other bill, no history. `G92` reads this function with `ast` every run.

    ⚠ **THE FIGURE IS `payments`' AND IS NOT COMPUTED HERE** (`US-CWP-003` §7:
    *"No GT — this is a read of existing arithmetic"*). `owing_on` asks the
    module that keeps the open-bill position, which is the same number
    `CWP-027` and `CWP-028` show; a subtraction here would be a second answer to
    the one figure a customer rings up about.
    """
    from apps.portal.seams import billing_seam

    wanted_postcode = _squashed_postcode(postcode)
    if not wanted_postcode or not str(bill_number or "").strip():
        return None

    invoice = billing_seam.bill_by_number(tenant_id, number=bill_number)
    if invoice is None:
        return None

    premises_id = customers_seam.account_premises_id(tenant_id, invoice.account_id)
    held = _squashed_postcode(customers_seam.premises_postcode(premises_id))
    if not held or held != wanted_postcode:
        return None

    replaced_by = billing_seam.replacement_number(invoice)
    still_owed = Decimal(billing_seam.owing_on(invoice))
    if invoice.status == billing_seam.VOID:
        state = BILL_CANCELLED
    elif replaced_by is not None:
        state = BILL_REPLACED
    elif still_owed <= 0:
        state = BILL_SETTLED
    else:
        state = BILL_PAYABLE

    #: ⚠ **A CANCELLED OR REPLACED BILL SHOWS `$0.00`, NOT ITS FACE VALUE.**
    #: Neither is owed, and printing `$154.90` beside the word *replaced* would
    #: be the one figure on this screen somebody might act on — and `TC-7` sends
    #: the payment at the replacement rather than at this row.
    payable = Decimal("0") if state in (BILL_CANCELLED, BILL_REPLACED) else still_owed

    return {
        "number": invoice.invoice_no,
        "amount": money.amount(payable, currency=invoice.currency or "USD"),
        "status": state,
        "due_on": invoice.due_date.isoformat() if invoice.due_date else None,
        "masked_name": masked_name(
            customers_seam.holder_display_name(tenant_id, invoice.account_id)
        ),
        "replaced_by": replaced_by,
    }


def guest_payment_receipt(charged: dict[str, Any], *, bill_number: str) -> dict[str, Any]:
    """`POST /public/bills/{number}/pay` — `CWP-004`, what a guest keeps.

    ⚠ **IT SHAPES AND IT COMPUTES NOTHING** (`CR-068` §2d). Every figure here
    came out of the rails; this function turns a settlement into the six things
    `BR-CWP-028` says a guest flow ends on and drops everything else on the
    floor. A second arithmetic here would be a second answer to *how much did I
    pay*, and the receipt document would say the other one.

    ⚠ **SIX KEYS, AND `guest_fields.py` HOLDS THE LIST AS DATA.** No account, no
    address, no person — not even the masked one, which the person has already
    seen at step 2 and which serves no purpose on a receipt (`BR-CWP-021`).
    `against` is the BILL NUMBER off the paper and `reference` is `PAY-26-08841`:
    both are HUMAN references somebody can read down a telephone, never a row id
    (B14 rule 31).

    ⚠ **`receipt_sent` IS A FACT AND THE ADDRESS IS NOT ON IT.** `US-CWP-004` §4
    is deliberate that the receipt address may be a NEIGHBOUR's — *"a guest may
    be a neighbour"* — so echoing it would put somebody's email on a screen that
    anybody holding the bill can reach. The screen needs to know WHETHER it was
    sent, which is what `US-CWP-005` TC-2 turns on, and never WHERE.

    ⚠ **AND THERE IS NO `enrolment_offered` FLAG, WHICH IS A DISCLOSURE
    DECISION.** `US-CWP-005` §1 wants the login offered at *"the single best
    moment in the product"*; a server flag saying *this account has no login
    yet* would answer a question a stranger has no business asking. The offer is
    drawn unconditionally and `/enrol` protects itself — TC-4 requires exactly
    that, *"does not skip the one-time code because a payment just succeeded"*.
    """
    paid_at = charged.get("paid_at")
    return {
        "reference": charged["reference"],
        "amount": money.amount(charged["amount"], currency=charged.get("currency") or "USD"),
        "paid_at": paid_at.isoformat() if hasattr(paid_at, "isoformat") else paid_at,
        "against": bill_number,
        # `BR-CWP-057` — a brand and a last four are what a stored instrument
        # shows a person. The gateway token is NOT here: it is the rails'
        # secret, and a guest screen has no use for it.
        "method": {
            "brand": charged.get("method_brand"),
            "last_four": charged.get("method_last_four"),
        },
        "receipt_sent": bool(charged.get("receipt_sent")),
    }


# CR-068 wave L1 · the four arrears screens — `CWP-057` (the ladder),
# `CWP-056` (three doors), `CWP-064` (three protections), `CWP-045`
# (credits and refunds).  US-CWP-057 · 058 · 059 · 056
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THESE ARE THE SCREENS MOST LIKELY TO FRIGHTEN SOMEBODY WRONGLY**, and two
# disciplines follow from that and are worth stating once for all four:
#
#  1. **NO FIGURE ON THESE SCREENS IS COMPUTED HERE.** The balance comes from
#     `payments`' open-bill position, the reconnection fee from `customers`'
#     `reconnection_terms`, the credits from `billing`'s credit-note read and
#     the refunds from `payments`' own `refund_row`. The ONLY arithmetic in
#     this section is `US-CWP-057` §7's sum of figures the screen is already
#     showing, and it refuses to add a figure that is absent (see
#     `_if_it_goes_that_far`).
#
#  2. **AN ABSENCE IS RENDERED AS AN ABSENCE AND NEVER AS A ZERO OR A
#     NEIGHBOUR'S VALUE.** `BR-CWP-092` says it of an unmapped tier — showing a
#     customer at the five-day notice as though they were at the ten-day one
#     *"moves the date they think they have"* — and the same reading governs a
#     reconnection fee the tenant has not configured and a deposit no rule
#     prices. `collections_read._Thresholds` put it best on the staff side:
#     *"an honest 'I cannot answer that' beats a real-looking next step."*


#: The three hardship routes `CWP-056` offers, in the blueprint's order
#: (`P42`). ⚠ **THE THIRD IS NOT A DOOR** — the moratorium is a window the
#: regulator sets and nobody applies for, so it is stated as a FACT with no
#: control (`US-CWP-058` TC-2).
ROUTE_PLAN = "payment_plan"
ROUTE_CERTIFICATE = "medical_certificate"
ROUTE_LEVEL_PAY = "level_pay"
HARDSHIP_ROUTES: tuple[str, ...] = (ROUTE_PLAN, ROUTE_CERTIFICATE, ROUTE_LEVEL_PAY)

#: ⚠ **`OQ-CWP-1600` — WHAT A NEW DEPOSIT COSTS TO RECONNECT IS PRICED BY NO
#: RULE IN THIS PRODUCT.** `US-CWP-057` §4 quotes `$150.00` and §7 adds it into
#: `$657.60`; measured, `disconnects.reconnection_terms` answers
#: `new_deposit_required` as **True, False or None** and deliberately carries NO
#: amount, because `DSC-02.4` says a new deposit *is required* and names no
#: figure — *"Nothing collects that new deposit and nothing posted the
#: application"*. The one deposit figure the product holds is
#: `rating.PlanDepositRule.amount`, which prices a NEW CONNECTION for a class of
#: customer; whether a reconnection asks the same amount is a utility's policy
#: and nobody has ruled it. So this screen states the requirement in words and
#: quotes no number, and the total below adds only what it is showing.
DEPOSIT_NOT_PRICED: dict[str, Any] = {
    "code": "reconnection_deposit_not_priced",
    "oq_ref": "OQ-CWP-1600",
    "detail": "the case records WHETHER a new deposit will be required (the deposit election "
    "made at the cut) and no rule in this product prices one. `rating.PlanDepositRule` prices a "
    "NEW CONNECTION for a class of customer and nothing says a reconnection asks the same. A "
    "figure invented here would be the first number a frightened customer reads.",
}

#: ⚠ **THE LATE FEE HAS NO ACCOUNT-SCOPED READ.** `P43` draws *Late fee added ·
#: 24 Aug · $8.25* as the third rung of the timeline. A late fee is an INVOICE
#: LINE carrying `billing.decisions.DEFAULT_LATE_FEE_CHARGE_CODE`, and no module
#: publishes *"the late fees charged to this account"* — `apps/billing/late_fee`
#: ASSESSES one and answers no history. So the step is omitted rather than drawn
#: with an empty date, and the reason travels in `problems` where a person can
#: read it (hard-won law 1 — a comment claiming a guarantee is not the
#: guarantee, and this runs the other way too).
LATE_FEE_NOT_READABLE: dict[str, Any] = {
    "code": "late_fee_history_not_readable",
    "detail": "a late fee is an invoice line and no module publishes an account-scoped list of "
    "them. `P43` draws it as the third step of the timeline; drawing a step whose date is blank "
    "would read as *it has not happened yet* on a screen about what has already happened.",
}


def _days_between(earlier: Any, later: Any) -> int | None:
    """Whole days from `earlier` to `later`, or None when either is missing.

    ⚠ **NEVER 0 FOR *UNKNOWN*.** *"`$412.60` is overdue by 0 days"* and *"we
    cannot tell you how long"* are different sentences, and `collections_read`
    makes the same distinction for `days_late` in its own words: *"a bill nobody
    can place in time cannot be chased on a schedule anchored to time."*
    """
    if earlier is None or later is None:
        return None
    return (later - earlier).days


def _timeline(
    *,
    case_view: dict[str, Any],
    notices: list[dict[str, Any]],
    due_on: str | None,
    next_tier: str | None,
    lawful_tiers: tuple[str, ...],
    today: date,
) -> list[dict[str, Any]]:
    """`CWP-057`'s WHERE THINGS STAND — **this account's own record, in order**.

    ⚠ **EVERY ROW COMES OFF THE CASE OR A NOTICE ROW, AND NOT ONE COMES OFF THE
    TENANT'S CADENCE** (`US-CWP-057` TC-4). Two accounts at different tiers show
    different dates because they ARE different records — not because a setting
    was applied to each.

    ⚠ **A STEP WHOSE TIER THE VOCABULARY CANNOT NAME CARRIES `tier: None` AND
    `unmapped: true`** (`BR-CWP-092`, TC-3). `disconnects.tier_for_rung` returns
    `TIER_UNMAPPED` for payments' five-day rung because mapping it onto either
    neighbour *"is a statement to a regulator about what a customer was told"*.
    The screen renders that as an absence; it may not fall back to a neighbour's
    date.

    ⚠ **A FUTURE STEP CARRIES `no earlier than` AND NEVER A PROMISE.** Nothing
    in this product advances a tier on a date — `DisconnectCase.next_step_due`
    is, in `disconnects`' own words, *"a STORED DATE THAT NOTHING WATCHES"*
    (`DEF-320`) — so the date is a floor the utility will not act before, and
    `is_floor` says so on the row rather than in a translator's guess.
    """
    steps: list[dict[str, Any]] = []
    if due_on is not None:
        steps.append(
            {
                "step": "due",
                "tier": None,
                "unmapped": False,
                "on": due_on,
                "is_floor": False,
                "state": "done" if date.fromisoformat(due_on) <= today else "future",
            }
        )
    for notice in notices:
        steps.append(
            {
                "step": "notice_sent",
                #: ⚠ **A TIER THIS VOCABULARY DOES NOT KNOW IS AN ABSENCE**
                #: (`BR-CWP-092`) — the same reading `disconnect_reads
                #: .chips_for` takes of a case, applied to a notice row.
                "tier": notice["tier"] if notice["tier"] in lawful_tiers else None,
                "unmapped": notice["tier"] not in lawful_tiers,
                "on": notice["issued_on"],
                "is_floor": False,
                "state": "done",
                #: ⚠ **HOW it was served, only where a person RECORDED it.**
                #: `delivery_state` is NULL on every row this product writes —
                #: there is no email, SMS or print adapter — so a portal that
                #: drew *"emailed"* would be telling a customer they were warned
                #: (`BR-NOT-005`, `disconnects.DELIVERY_UNAVAILABLE`).
                "served_channel": notice["served_channel"],
                "served_on": notice["served_on"],
            }
        )
    next_due = case_view.get("next_step_due")
    if next_due:
        steps.append(
            {
                "step": "notice_next",
                "tier": next_tier if next_tier in lawful_tiers else None,
                "unmapped": next_tier is not None and next_tier not in lawful_tiers,
                "on": next_due,
                "is_floor": True,
                "state": "current",
            }
        )
    cut_on = case_view.get("cut_on")
    cut_due = case_view.get("cut_scheduled_for")
    if cut_on:
        steps.append(
            {"step": "cut", "tier": None, "unmapped": False, "on": cut_on,
             "is_floor": False, "state": "done"}
        )
    elif cut_due:
        steps.append(
            {"step": "cut", "tier": None, "unmapped": False, "on": cut_due,
             "is_floor": True, "state": "future"}
        )
    return steps


def _stored(amount: Any) -> str | None:
    """`disconnects._money`'s 4dp leg, or `None` — never the display leg.

    ⚠ **THAT READ RETURNS A LABELLED PAIR AND NOT A STRING**
    (`{"stored": "95.0000", "display": "95.00"}`), which is
    `move_out_settlement.serialize`'s idiom: *"a caller never has to decide
    which one it is holding."* This picks the STORED leg because hard rule 2
    rounds once, at display, and adding two display legs would round twice.
    """
    if amount is None:
        return None
    if isinstance(amount, dict):
        return amount.get("stored")
    return str(amount)


def _if_it_goes_that_far(
    *, owed: str | None, fee: Any, currency: str | None, basis: dict[str, Any] | None = None
) -> dict[str, Any]:
    """`US-CWP-057` §7 — **the only arithmetic on this screen**, and it adds
    only what the screen is showing and is not already showing twice.

    Worked, on the story's own account, BEFORE the cut: owed `$412.60` +
    reconnection `$95.00` = **`$507.60`**, and the new deposit is stated as
    required and NOT PRICED (`OQ-CWP-1600`, `DEPOSIT_NOT_PRICED`). §4 of the
    story quotes `$657.60` on a `$150.00` deposit; **no read in this product
    answers that `$150.00`**, and the story is amended with this finding rather
    than the figure being invented here to match it.

    ⛔ **AFTER THE CUT THE FEE IS ALREADY IN WHAT THE CUSTOMER OWES, AND THIS
    ADDED IT A SECOND TIME — `DEF-CWP-6072`.** `commit_cut` raises and ISSUES
    the reconnection fee inside the cut's own transaction (`DEF-708`, PO ruling
    2026-08-27), so from that instant it is an OPEN BILL and the balance read
    above already holds it. Measured on `A-11340` / `DSC-26-0001` on 2026-09-20,
    after the first cut this product has ever completed: **owed `$75.00` +
    reconnection fee `$75.00` = subtotal `$150.00`**, where the `$75.00` owed
    **IS** the fee bill the cut issued. It was correct until the day a cut first
    committed, because until then the fee could only ever be a quote.

    ⚠ **THE FACT IS READ, NOT DERIVED — AND IT IS `customers`' TO STATE.**
    `disconnects` publishes it on the quote as `to_clear.basis.fee_in_arrears`,
    keyed on `case.cut_on` (the fact `commit_cut` writes, in the same
    transaction that issues the fee, and nothing else writes) rather than on a
    list of states, for the reason `DEF-CUS-6050` records. **A third copy of
    this arithmetic is exactly how the two STAFF figures came to disagree**, and
    the fix there deleted one; this screen must not add it back.

    ⚠ **NOT ADDED IS NOT THE SAME AS NOT SHOWN.** The fee keeps its row and its
    amount — a customer has to be able to see what they are being charged — and
    carries `already_owed`, so the screen can say it is inside the figure. A row
    silently dropped would say the fee does not exist; a row left unmarked would
    leave a reader with arithmetic that does not add up.

    ⚠ **A MISSING PART MAKES THE TOTAL MISSING, NOT SMALLER.** `subtotal` is
    `None` — never a partial sum wearing the label *if it goes that far* —
    whenever a part the total NEEDS is absent, and `parts_missing` names which.
    A total that silently omits a fee is a total the customer will discover is
    wrong at the counter (`DEF-708`'s own shape, one surface over). After the
    cut the fee is not one of those parts: it is inside the position, so a
    catalogue row edited or deleted months later cannot blank the figure out.
    """
    fee_amount = _stored(fee)
    #: ⚠ **`False` WHEN THE MODULE DID NOT SAY.** A read that could not see the
    #: case must not guess: guessing *after* quotes a price short by the whole
    #: fee, and only the pre-cut sum is safe to fall back to.
    already_owed = bool((basis or {}).get("fee_in_arrears"))
    missing: list[str] = []
    if owed is None:
        missing.append("owed")
    if fee_amount is None and not already_owed:
        missing.append("reconnection_fee")
    #: The deposit is ALWAYS missing today — see `DEPOSIT_NOT_PRICED`. Named as
    #: a part rather than skipped, so the screen says what is not in the total.
    missing.append("new_deposit")
    parts = [
        {"part": "owed", "amount": owed, "already_owed": False},
        #: ⚠ **`already_owed` IS ABOUT THE TOTAL, NOT ABOUT THE ROW.** It says
        #: this amount is inside `subtotal` already; it never means the charge
        #: was waived.
        {"part": "reconnection_fee", "amount": fee_amount, "already_owed": already_owed},
        {"part": "new_deposit", "amount": None, "already_owed": False},
    ]
    total: str | None = None
    if already_owed:
        # ── The cut has committed: the position IS the answer. Read once. ──
        total = None if owed is None else str(Decimal(owed).quantize(Decimal("0.0001")))
    elif owed is not None and fee_amount is not None:
        total = str((Decimal(owed) + Decimal(fee_amount)).quantize(Decimal("0.0001")))
    return {
        "parts": parts,
        "parts_missing": missing,
        #: ⚠ **THE SUM OF THE PARTS THAT ARE PRESENT**, and it is labelled
        #: `subtotal` rather than `total` for exactly the reason above.
        "subtotal": total,
        "currency": currency,
        #: ⚠ **WHICH QUESTION THE SUBTOTAL ANSWERED**, carried through from
        #: `customers` so no later reader has to infer whether the fee is inside
        #: it (`DEF-CWP-6072`, and `DEF-CUS-6050`'s own posture on the staff
        #: payload). It explains the figure; it does not repair it.
        #:
        #: ⚠ **TWO FIELDS, NOT THE WHOLE STAFF DICT.** `customers` carries a
        #: `detail` worked on `A-11340` by name and a `br_ref` naming defect
        #: ids; that is a note to a reader of the STAFF payload, and putting it
        #: on every customer's wire would ship one account's figures to all of
        #: them. The portal takes the two facts and leaves the prose.
        "basis": (
            None
            if not basis
            else {
                "code": basis.get("code"),
                "fee_in_arrears": bool(basis.get("fee_in_arrears")),
            }
        ),
        "problems": [dict(DEPOSIT_NOT_PRICED)],
    }


def arrears_position(account: Any, *, as_of: date, locale: str | None = None) -> dict[str, Any]:
    """`CWP-057` — what happens if this is not paid, and what it would cost.

    ⚠ **THE SCREEN AND ITS LINK ARE ABSENT WHEN NOTHING IS OVERDUE**
    (`US-CWP-057` TC-10, `BR-CWP-093`). `overdue: false` is the whole answer and
    the body carries no timeline — an empty ladder on an account in good standing
    is a letter nobody sent.

    ⚠ **A PROTECTION IN FORCE SHOWS AS A HOLD, WITH WHY** (TC-6). `BR-CWP-091`:
    *a hold stops a disconnection, not the debt* — so the halt reason travels
    beside the timeline rather than instead of it, and the balance is unchanged.

    ⚠ **THE WRITE-OFF SHOWS ITS AMOUNT AND ITS DATE AND NEVER ITS REASON**
    (`BR-CWP-051`, TC-9). *Bankruptcy* and *deceased, no estate* are the
    utility's judgment about a person; the amount is the person's own money.
    `payments_seam.write_offs_for` is where that guarantee lives.
    """
    from apps.portal.seams import payments_seam

    balance = payments_seam.account_balance(account.pk)
    owing = Decimal(balance.get("owing") or "0")
    due_on = balance.get("due_on")
    overdue = owing > 0 and due_on is not None and date.fromisoformat(due_on) < as_of

    case = customers_seam.disconnect_case(account.pk)
    ladder = customers_seam.ladder_position(account.pk, as_of=as_of)
    unmapped = customers_seam.tier_unmapped()
    protections = customers_seam.protections(account.pk, as_of=as_of)

    case_view = customers_seam.case_view(case) if case is not None else {}
    quote = customers_seam.reconnection_quote(account.pk, case=case)
    notices = customers_seam.notices_on(case) if case is not None else []

    #: ⚠ **WHICH TIER IS `disconnect_reads.chips_for`'S ANSWER, NOT THIS
    #: MODULE'S** — see `customers_seam.tier_chips`. `unmapped` is TRUE only for
    #: `unmapped_rung`; a NULL tier is the OTHER absence (*nothing has been
    #: sent*) and reading the two as one would tell a customer at the five-day
    #: notice that nothing had gone out.
    chips = customers_seam.tier_chips(case=case, protections=protections)
    tier = next((chip["code"] for chip in chips["chips"]), None)
    unmapped_here = any(row["code"] == unmapped for row in chips["unavailable"])
    return {
        "as_of": as_of.isoformat(),
        "overdue": bool(overdue),
        #: **THE ANSWER A CLERK PINNED TO THIS SCREEN** (`CWP-060` second
        #: placement, `DEF-CWP-3945`). ⚠ `None` closes the slot up entirely —
        #: `BR-CWP-093`, and an empty card headed *Why is my bill higher?* with
        #: nothing under it is worse than no card. The utility wrote the answer
        #: ONCE, on the help screen; this is where it is ALSO shown, never a
        #: second row to keep in step.
        "attached_answer": tenancy_seam.attached_answer(
            account.tenant_id, "overdue", locale=locale
        ),
        #: ⚠ **THE SIGN THE SERVER SENT.** `owing` is what `payments` computed;
        #: nothing here negates it and nothing takes an absolute value.
        "owed": balance.get("owing"),
        "currency": balance.get("currency"),
        "due_on": due_on,
        "days_overdue": _days_between(
            date.fromisoformat(due_on) if due_on else None, as_of
        ) if overdue else None,
        #: `BR-CWP-092` — the chip, or `None` with `tier_unmapped: true`.
        #: ⚠ **A PROTECTION IS ITSELF A CHIP** on the staff tab, so `chips`
        #: carries every one that applies and `tier` is the FIRST in the drawn
        #: order. Nothing is ranked here: `OQ-374` records that no rule ranks
        #: them, and the portal does not become the place that does.
        "tier": tier,
        "tier_unmapped": unmapped_here,
        "chips": [chip["code"] for chip in chips["chips"]],
        "tier_reached_on": case_view.get("tier_reached_on"),
        "case_open": case is not None,
        "timeline": _timeline(
            case_view=case_view,
            notices=notices,
            due_on=due_on,
            next_tier=ladder.get("next_tier"),
            lawful_tiers=customers_seam.ladder_tiers(),
            today=as_of,
        ),
        #: ⚠ **WHICH SERVICES WOULD BE CUT, NAMED FROM THE CASE** (TC-5) — the
        #: codes `assert_treatments_expressible` allowed, never every service the
        #: account holds.
        "services_at_risk": list(getattr(case, "services_cut", None) or ()),
        "ladder_running": bool(ladder.get("runs")),
        "halt_code": ladder.get("halt_code"),
        "held_by": [
            {"kind": row["kind"], "lifetime": row["lifetime"]}
            for row in protections
            if row["in_force"]
        ],
        #: ⚠ **THE BASIS TRAVELS WITH IT — `DEF-CWP-6072`.** Whether the
        #: reconnection fee has already been ISSUED into what this account owes
        #: is `customers`' fact to state, off `case.cut_on`, and this screen
        #: reads it rather than deriving a third copy of the same arithmetic.
        "cost": _if_it_goes_that_far(
            owed=balance.get("owing"),
            fee=quote.get("fee"),
            currency=balance.get("currency"),
            basis=(quote.get("to_clear") or {}).get("basis"),
        ),
        "reconnection_fee_absence": quote.get("fee_absence"),
        "new_deposit_required": (quote.get("deposit") or {}).get("new_deposit_required"),
        "write_offs": payments_seam.write_offs_for([account.pk]),
        #: ⚠ **NOTHING IN THIS PRODUCT ADVANCES A TIER ON A DATE** (`DEF-320`).
        #: Carried so the screen's *no earlier than* wording is grounded in the
        #: record rather than in a copywriter's caution.
        "scheduler": ladder.get("scheduler"),
        "problems": [dict(LATE_FEE_NOT_READABLE), *(balance.get("problems") or ())],
    }


def protections_view(account: Any, *, as_of: date) -> dict[str, Any]:
    """`CWP-064` — three lifetimes, three sentences (`US-CWP-059`).

    ⚠ **THE SCREEN AND ITS LINK ARE ABSENT WHEN THERE IS NO PROTECTION AT ALL**
    (TC-6, `BR-CWP-093`) — *"not three empty cards"*. `any: false` says so.

    ⚠ **THE PLAN CARD CARRIES NO END DATE AND ONE IS NOT INVENTED FOR IT**
    (TC-2). `disconnects.PROTECTION_LIFETIME` maps a plan hold to
    `derived_from_the_plan`, and the `ck_protection_lifetime` constraint is what
    holds that difference in the data: it lifts the day an instalment is missed
    (`OQ-170`, CLOSED 2026-08-12 — no grace), and the plan itself stays ACTIVE,
    because *"nodrop we chase for payments until write off"* (PO 2026-08-11).

    ⚠ **A LIFTED PROTECTION IS SHOWN AS LIFTED WITH ITS DATE** (TC-7) — never
    silently removed.

    ⚠ **A CERTIFICATE WITH NO END DATE IS NOT RENDERED** (TC-4). The product's
    own rule refuses one upstream — *a certificate with no end date is a
    permanent exemption nobody signed* — and a row that reached here without one
    is reported as a problem rather than drawn as an open-ended hold.
    """
    kinds = customers_seam.protection_kinds()
    rows = customers_seam.protections(account.pk, as_of=as_of)
    problems: list[dict[str, Any]] = []
    out: list[dict[str, Any]] = []
    for row in rows:
        expires = row["expires_on"]
        if row["kind"] == kinds["medical"] and expires is None and row["lifted_on"] is None:
            problems.append(
                {
                    "code": "certificate_without_an_end_date",
                    "br_ref": "BR-CWP-090",
                    "detail": "a medical certificate must carry an end date — a hold with none is "
                    "a permanent exemption nobody signed. This row is not rendered.",
                }
            )
            continue
        out.append(
            {
                "kind": row["kind"],
                "lifetime": row["lifetime"],
                "in_force": row["in_force"],
                "since": row["effective_from"].isoformat() if row["effective_from"] else None,
                #: ⚠ **`None` ON A PLAN HOLD, ALWAYS** — and the screen says in
                #: words what ends it instead of drawing a blank date cell.
                "ends_on": expires.isoformat() if expires else None,
                "lifted_on": row["lifted_on"].isoformat() if row["lifted_on"] else None,
            }
        )
    return {
        "as_of": as_of.isoformat(),
        "any": bool(out),
        "protections": out,
        #: `BR-CWP-091`, on the screen and not only in help (TC-5). Carried as a
        #: FACT the screen renders rather than a sentence a lane could forget.
        "hold_stops_disconnection_not_debt": True,
        "problems": problems,
    }


def help_paying(tenant_id: Any, account: Any, *, as_of: date) -> dict[str, Any]:
    """`CWP-056` — three doors, and one of them is not a door (`US-CWP-058`).

    ⚠ **NOTHING ON THIS SCREEN GRANTS A PROTECTION** (`BR-CWP-089`). Every one
    needs a person and a document. The certificate route raises an ordinary
    SERVICE REQUEST (`services.SHAPE_HARDSHIP_ASK`) and writes no
    `AccountProtection` row — TC-4 asserts the row count is unchanged.

    ⚠ **THE MORATORIUM IS STATED AS A FACT WITH NO CONTROL** (TC-2) and its
    window is READ FROM THE RECORD (TC-9, `US-CWP-059` TC-9) — never written in
    prose, so changing the record changes the screen. ⚠ **AND WHERE THIS
    ACCOUNT HOLDS NO MORATORIUM ROW THERE IS NO WINDOW TO QUOTE**, so the bar is
    absent rather than stating somebody else's dates: this product stores a
    moratorium as an `AccountProtection` row on an account, not as a state-wide
    setting, and inventing a window would be the `BR-CWP-092` mistake in another
    costume.

    ⚠ **THE PLAN CARD IS ABSENT WHERE THE TENANT HAS PLANS SWITCHED OFF**
    (TC-6) — `portal_settings.plans_enabled`, R8's own switch — **and the other
    two remain.** A customer who cannot have a plan can still send a certificate.

    ⚠ **PAST THE FINAL NOTICE, ALL THREE STAY OPEN — `OQ-CWP-1601`, OPEN.**
    `P42` promises *"ask before the final notice and all three stay open"*,
    which reads as though something closes after it. **Measured, nothing in this
    product closes any of them:** `record_protection` has no tier gate, a clerk
    may grant a plan at any tier (`BR-CWP-066`), and level pay is unrelated to
    the ladder. So `still_open` is true on all three and `past_final_notice`
    carries the urgency instead. **Closing a door the product would still open
    is the one error this screen must never make** — it turns a frightened
    customer away from help they can still get.
    """
    settings = settings_view(tenant_id)
    kinds = customers_seam.protection_kinds()
    rows = customers_seam.protections(account.pk, as_of=as_of)
    moratorium = next(
        (row for row in rows if row["kind"] == kinds["moratorium"] and row["lifted_on"] is None),
        None,
    )
    case = customers_seam.disconnect_case(account.pk)
    case_view = customers_seam.case_view(case) if case is not None else {}
    #: ⚠ **THE LAST CHIP IS THE FINAL NOTICE, NAMED THROUGH THE SEAM** and never
    #: spelled here — `customers_seam.ladder_tiers` is `disconnects`' own tuple,
    #: so a rename moves one line rather than a comparison in a screen.
    past_final = case_view.get("tier") == customers_seam.ladder_tiers()[-1]

    routes: list[dict[str, Any]] = []
    if settings.get("plans_enabled"):
        routes.append(
            {
                "route": ROUTE_PLAN,
                "still_open": True,
                #: `BR-CWP-066` — the control reads *Ask for a payment plan*
                #: and a CLERK grants it. `granted_by` is on the wire so no
                #: screen can imply the customer gives themselves one.
                "granted_by": "clerk",
                "asks_for": "service_request",
            }
        )
    routes.append(
        {
            "route": ROUTE_CERTIFICATE,
            "still_open": True,
            "granted_by": "clerk",
            "asks_for": "service_request",
            #: ⚠ **THE EXPIRY IS PART OF THE OFFER, NOT A FOOTNOTE**
            #: (`BR-CWP-090`, TC-3): a customer who believes a hold is permanent
            #: *"stops paying and is disconnected the week it lapses."*
            "hold_expires": True,
            #: ⚠ **CONSUMER UPLOAD IS DEFERRED** (`DF-4`, PO 2026-08-08) — the
            #: route ends at the counter and the screen says so (TC-5). Stated
            #: as data so no lane has to remember not to draw a file input.
            "upload_available": False,
        }
    )
    routes.append({"route": ROUTE_LEVEL_PAY, "still_open": True, "granted_by": "clerk",
                   "asks_for": "service_request"})
    return {
        "as_of": as_of.isoformat(),
        "routes": routes,
        "plans_enabled": bool(settings.get("plans_enabled")),
        "past_final_notice": bool(past_final),
        "moratorium": (
            {
                "from": moratorium["effective_from"].isoformat(),
                "until": (
                    moratorium["expires_on"].isoformat() if moratorium["expires_on"] else None
                ),
                #: ⚠ **NO CONTROL, EVER.** The regulator sets the window and
                #: nobody applies for it, so this is a FACT on the wire and the
                #: screen renders it in an `InfoBar` with no button (TC-2).
                "apply": False,
                "set_by": moratorium["set_by"],
            }
            if moratorium is not None
            else None
        ),
    }


def money_back(account: Any) -> dict[str, Any]:
    """`CWP-045` — credits and refunds in flight, and they are DIFFERENT THINGS.

    ⚠ **THE SEPARATION IS THE SCREEN'S WHOLE JOB** (`US-CWP-056` TC-5).
    Customers use the two words interchangeably; *a credit comes off your next
    bill, a refund is money sent back*, and a screen that calls both *money
    back* is the defect the story names.

    ⚠ **NOTHING IS CACHED AND NOTHING MAY BE** (`BR-CWP-047`, TC-3): a credit
    real on Tuesday can be spent by Thursday. Both halves are re-read on every
    load and the edge answers `no-store`.

    ⚠ **THE SCREEN AND ITS LINK ARE ABSENT WHEN THERE IS NEITHER** (TC-7,
    `BR-CWP-093`) — `any: false`, not two empty tables.

    ⚠ **A VOIDED REFUND IS LISTED AS VOIDED** (TC-4) rather than removed.

    ⚠ **NO SIGN IS CHANGED ON THE WAY THROUGH.** A credit note's amount is
    stored `<= 0` by a database CHECK (`DEF-085`) and leaves negative; a
    refund's amount is stored positive and leaves positive. Neither is
    normalised, neither is absolute-valued, and the screen renders what the
    server sent.
    """
    from apps.portal.seams import billing_seam, payments_seam

    credits = billing_seam.credits_for(account.pk)
    refunds = payments_seam.refunds_for(account.pk)
    return {
        "any": bool(credits or refunds),
        "refunds": refunds,
        "credits": credits,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave R — `CWP-051`, track your request (US-CWP-063)
# ═══════════════════════════════════════════════════════════════════════════


def my_request_detail(principal: Any, *, reference: str, today: date) -> dict[str, Any] | None:
    """`CWP-051` whole, or None for *we cannot find that*.

    ⚠ **NONE IS RETURNED IDENTICALLY FOR THREE FAILURES** — an unknown
    reference, another customer's reference and another tenant's reference —
    exactly as `track()` does for the guest tracker one screen along, and for
    the same reason: a different answer for *"right reference, wrong customer"*
    would confirm the reference exists (`US-CWP-063` TC-7).

    ⚠ **BOTH HALVES OF `BR-CWP-010` ARE IN THE SEAM'S QUERY** — the tenant and
    the login's own contact facts. `OQ-CWP-1680` carries the fact that a service
    request has no account column to intersect against; `my_requests` says so in
    its own words rather than leaving the next lane to notice.
    """
    row = customers_seam.my_request(
        principal.tenant_id,
        reference=reference,
        phones=customers_seam.contact_phones(
            principal.tenant_id, list(getattr(principal, "account_ids", ()) or ())
        ),
    )
    if row is None:
        return None
    return customers_seam.request_detail_view(row, today=today)


def my_request_row(principal: Any, *, reference: str) -> Any:
    """The ROW behind `CWP-051`'s two write controls, or None.

    ⚠ **THE EDGE NEEDS THE ROW AND THE SCREEN NEEDS THE VIEW, AND THEY ARE TWO
    FUNCTIONS RATHER THAN ONE WITH A FLAG.** `services._withdraw` is handed a
    row id the query has already proved is this login's; nothing downstream
    looks a reference up a second time.
    """
    return customers_seam.my_request(
        principal.tenant_id,
        reference=reference,
        phones=customers_seam.contact_phones(
            principal.tenant_id, list(getattr(principal, "account_ids", ()) or ())
        ),
    )


def open_query_on(principal: Any, *, bill_number: str) -> Any:
    """An open query this login already raised on this bill (`US-CWP-065` TC-9)."""
    return customers_seam.open_query_on_bill(
        principal.tenant_id,
        bill_number=bill_number,
        phones=customers_seam.contact_phones(
            principal.tenant_id, list(getattr(principal, "account_ids", ()) or ())
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 · `CWP-032` — YOUR FINAL BILL (US-CWP-037)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE FINAL BILL IS WHERE A DEPOSIT COMES BACK, AND A DEPOSIT IS MONEY.**
# Every figure here is `apps.billing.final_bill.settle_final_bill`'s — the same
# function that settles the account for a clerk — reached through
# `billing_seam.final_bill_for`. The interest inside it is
# `apps.customers.deposit_interest`, finance-signed against ❄️ `GT-61`. **The
# portal computes nothing on this path**, because a customer and a clerk quoting
# different final figures is the defect `US-CWP-037` §7 exists to catch.
#
# ⚠ **AND THE DEPOSIT FIGURES ARE THE ONES `CWP-065` ALREADY SHOWS** (TC-5).
# Both screens read `accounts.deposit_on_file` and
# `customers.selectors.deposit_interest_accrued`; there is one implementation of
# each, so *held `$150.00` since 4 March 2021, interest `$3.20`* is the same
# sentence on the account page and on the closing bill by construction rather
# than by agreement.


def final_bill(principal: Any, account: Any, *, today: date) -> dict[str, Any]:
    """`GET accounts/{id}/final-bill` — the closing bill, settled.

    ⚠ **`bill` IS `None` FOR EVERY ACCOUNT THAT IS NOT LEAVING**, and the screen
    is absent rather than empty (`BR-CWP-093`). A settlement panel over an
    account that has not moved out would be a page telling a customer their
    service is ending.

    ⚠ **THE LAST CHANCE TO QUERY A READING IS ON THIS SCREEN AND IT CLOSES**
    (`US-CWP-037` TC-9). Once the settlement has a path the account is closing,
    and a correction becomes a much slower business — so the route is withdrawn
    and `query_reading_closed_reason` says why, rather than the control simply
    vanishing.
    """
    from apps.portal.seams import billing_seam, metering_seam

    bill = billing_seam.final_bill_for([account.pk], today=today)
    if bill is None:
        return {"bill": None, "closing_reading": None}

    #: The move-out day IS the closing bill's `period_end` — `BR-CUS-056`, and
    #: `prepare_final_bill` sets it there in as many words: *"the OUTGOING
    #: account pays the move day, so `period_end` IS `moved_out_on`"*. Reading
    #: it off the bill rather than off the account is what stops the two
    #: disagreeing the day somebody re-dates a closure.
    moved_out_on = (
        date.fromisoformat(bill["period_end"]) if bill.get("period_end") else None
    )
    readings = metering_seam.readings_for_account(principal.tenant_id, account.pk, limit=12)
    closing = billing_seam.closing_reading_for(readings, moved_out_on=moved_out_on)

    settled = bool(bill.get("settled"))
    return {
        "bill": bill,
        "closing_reading": closing,
        #: ⚠ **THE ROUTE, AND THE REASON IT IS GONE.** Never a control that is
        #: simply absent: a customer who read *query this reading* yesterday and
        #: cannot find it today is owed the sentence, not the silence.
        "query_reading_open": not settled,
        "query_reading_closed_reason": None if not settled else "settled_correction_is_slower",
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 · `CWP-066` — WHERE YOUR LEVEL PAY STANDS (US-CWP-055)
# ═══════════════════════════════════════════════════════════════════════════


def level_pay_standing(account: Any) -> dict[str, Any]:
    """`GET accounts/{id}/level-pay/standing` — what it is really costing.

    ⚠ **`CWP-044` IS THE JOINING SCREEN AND THIS IS THE STANDING ONE, AND THE
    DIFFERENCE IS WHICH QUESTION IS BEING ASKED.** `US-CWP-055` §1: *"an
    enrolled customer has no screen at all today — not their level, not the
    variance building up, not the settle-up month. `CWP-044` is the JOINING
    screen; this is the one that was missing."* So this read carries no
    trailing average and no *what you would pay*: those belong to the offer,
    and repeating them here would be a second arithmetic over one fact.

    ⚠ **A CUSTOMER NOT ON LEVEL PAY GETS `standing: None` AND IS ROUTED**
    (TC-5). An empty standing screen for somebody who never joined would draw a
    variance of `$0.00`, which reads as *you are exactly level* rather than
    *this does not apply to you*.

    ⚠ **THE OVERRIDE'S REASON IS NOT IN THE BODY** (TC-4). `BR-CWP-052`'s
    posture, applied one column further along: the surest guard against a
    utility's private note about a customer reaching that customer's screen is
    that the code building the body never selects it.
    """
    from apps.portal.seams import billing_seam

    standing = billing_seam.level_pay_standing(account.pk)
    if standing is None:
        return {
            "standing": None,
            "months": [],
            #: ⚠ **THE SERVER SAYS WHERE TO SEND THEM, NOT THE SCREEN**
            #: (hard-won law 2's other half). `CWP-044` is registered at
            #: `/level-pay`; a front end that hardcoded the path would be a
            #: second map of which screens exist.
            "join_at": ERRAND_ROUTE_LEVEL_PAY,
        }
    return {
        "standing": standing,
        "months": billing_seam.level_pay_months(account.pk),
        "join_at": None,
    }


#: Where `CWP-044` is served, for the route above. Kept beside `ERRAND_ROUTE`'s
#: reasoning: one map of which screens exist, on the server.
ERRAND_ROUTE_LEVEL_PAY = "/level-pay"

# ═══════════════════════════════════════════════════════════════════════════
# CWP-025 · HOW WE CONTACT YOU (US-CWP-028, the PREFERENCES half)
#
# ⚠ **THE GRID IS HONEST ABOUT A STORE THAT IS NARROWER THAN THE DRAWING, AND
# THAT IS THE WHOLE DESIGN DECISION IN THIS SECTION (`DEF-CWP-3860`,
# `OQ-CWP-1660`).** `08-screen-layouts.md` draws `PreferenceGrid` as WHAT WE
# SEND × POST / EMAIL / TEXT / IN THE PORTAL, with an On/Off cell per event per
# channel. **This product holds no per-event customer preference at all.** What
# it holds is `accounts.paperless` (adds email), `accounts.sms_reminders` (adds
# text) and the PRINT FLOOR underneath both — three facts, not forty-eight.
#
# `US-CWP-028` §5 points the per-event cell at the *"notification rule
# catalogue"*, which is `notification_rules`: **one row per event per TENANT**,
# by unique constraint. A customer saving there would change what every other
# customer of that utility receives.
#
# **SO THE GRID DRAWS THE ROWS AND SAYS PLAINLY THAT THE ANSWER IS ONE ANSWER**
# — `applies_to_every_document: true` — rather than drawing forty-eight
# switches, forty-six of which would move the same two columns. A control that
# looks per-row and is not is hard-won law 2 with better manners.
# ═══════════════════════════════════════════════════════════════════════════

#: The four columns `CWP-025` draws, in the wireframe's order.
PREFERENCE_CHANNELS: tuple[str, ...] = ("post", "email", "text", "portal")

#: What a cell can be. WORDS the catalogue turns into a sentence (B14 rule 35).
CELL_ALWAYS = "always"
CELL_ON = "on"
CELL_OFF = "off"
CELL_NONE = "none"


def contact_preferences(principal: Any, *, today: date) -> dict[str, Any]:
    """`CWP-025` — the grid, the consent and the language, in one read.

    ⚠ **POST IS `always` AND IT IS READ FROM `notifications`, NEVER RESTATED
    HERE.** `seams.notifications_seam.print_floor_kinds()` reads
    `CHANNEL_FLOOR_BY_SOURCE`, the single statement of `BR-NOT-024` (PO
    2026-08-30: *"don't switch of print for any document it is awayls on"*). A
    tuple copied into the portal would go stale the next time the PO widens it,
    and the screen would then offer an off switch over a queue that prints
    anyway — which is the exact failure `US-CWP-028` §2 calls out: *"the screen
    must show it honestly rather than offering an off switch that quietly does
    nothing."*

    ⚠ **AND IF THE FLOOR CANNOT BE READ, THE GRID IS NOT DRAWN.** An empty
    tuple from that seam means *nobody could look*, not *no floor*, and a grid
    rendered on that answer would tell a customer a bill can be taken off
    paper. `floor_readable: false` is what the screen states instead.

    ⚠ **`in the portal` IS `always` FOR EVERY ROW AND HAS NO SWITCH**, which is
    a fact rather than a policy: `CWP-031` lists what was sent for every account
    this login holds, and there is no mechanism by which a customer could hide a
    document from their own documents screen.
    """
    from apps.portal.seams import notifications_seam

    floor = notifications_seam.print_floor_kinds()
    election = customers_seam.delivery_election(principal.tenant_id, list(principal.account_ids))
    email_on = bool(election.get("email_on"))
    text_on = bool(election.get("text_on"))

    rows = [
        {
            "kind": kind,
            "post": CELL_ALWAYS if kind in floor else CELL_NONE,
            "email": CELL_ON if email_on else CELL_OFF,
            "text": CELL_ON if text_on else CELL_OFF,
            "portal": CELL_ALWAYS,
        }
        for kind in floor
    ]
    return {
        "as_of": today.isoformat(),
        "channels": list(PREFERENCE_CHANNELS),
        #: ⚠ FALSE means the floor could not be read and the screen says so
        #: rather than drawing a grid it cannot stand behind.
        "floor_readable": bool(floor),
        "rows": rows,
        "email_on": email_on,
        "text_on": text_on,
        #: ⚠ **THE ONE SENTENCE THAT MAKES THE GRID HONEST** — see the section
        #: banner. The screen renders it as a line, not as a footnote.
        "applies_to_every_document": True,
        #: `election_varies` is TRUE when this login's accounts do not already
        #: agree, the same posture `contact_details` takes: silently showing one
        #: of four would tell a customer their choice is set where it is not.
        "election_varies": bool(election.get("varies")),
        "account_count": len(list(principal.account_ids)),
        "locales": list(PORTAL_LOCALES),
        "locale": account_language(principal),
        "paperless": paperless_consent(principal),
    }


def paperless_consent(principal: Any) -> dict[str, Any] | None:
    """The recorded consent and the date it was agreed, or `None`.

    `BR-CWP-087`, verbatim: *"Paperless is a **recorded consent** — a timestamp,
    the wording version, and a way to withdraw — not a toggle."*

    ⚠ **AN ABSENT CONSENT AND A WITHDRAWN ONE ARE DIFFERENT FACTS AND BOTH ARE
    SERVED** (`US-CWP-014` TC-2). `None` is *nobody ever asked* — every existing
    customer, because the one screen that takes this consent is the connection
    form and they connected before it existed. A row with `withdrawn_on` set is
    *they agreed and then changed their mind*, which the screen must be able to
    say; deleting the row would make the two indistinguishable for ever.

    ⚠ **THE ROW IS FOUND BY ACCOUNT, AND MOST LOGINS WILL HAVE NONE.** The
    consent hangs off the SERVICE REQUEST at `CWP-009` because the applicant has
    no account yet; `account_id` is stamped later if one is opened. Until that
    stamping exists, a customer who applied online sees `None` here — an honest
    absence rather than an invented consent, which is what a back-fill would be.
    """
    row = (
        models.PortalConsent.objects.filter(
            tenant_id=principal.tenant_id,
            account_id__in=[str(one) for one in principal.account_ids],
            kind=models.PortalConsent.KIND_PAPERLESS,
        )
        .order_by("-agreed_on")
        .first()
    )
    if row is None:
        return None
    return {
        "agreed_on": row.agreed_on.date().isoformat() if row.agreed_on else None,
        "wording_version": row.wording_version,
        "withdrawn_on": row.withdrawn_on.date().isoformat() if row.withdrawn_on else None,
        "taken_on_screen": row.taken_on_screen,
    }
