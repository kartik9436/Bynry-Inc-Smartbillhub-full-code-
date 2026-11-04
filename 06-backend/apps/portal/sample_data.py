# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-001 · US-CWP-069 · US-CWP-070 §4 test data — Pine Hill Water
#           ⊕ 2026-09-04, CR-068 wave C: US-CWP-012 §4 (`31 Palm Ct` with
#           Water/Sewer/Trash and no Electric, `$185.00` to connect and a
#           `$150.00` deposit; `1408 Elm St · A` OCCUPIED for TC-3) ·
#           US-CWP-015 §4 (the six categories, and Oak Ridge's own three).
#           & Power (`pine-hill`, brand #EC3013 / #E15B47) and Oak Ridge
#           (`oak-ridge`), the second tenant every isolation test needs.
# Rules:    10-execution-plan.md *Fixture* (the portal fixture is seeded as its
#           OWN tenants, so the story figures land verbatim and NO Brazos Bend
#           figure moves — G4/G61 stay untouched) · BR-TEN-010 (provisioning
#           is idempotent on the slug + owner email, so a replay writes
#           nothing) · CLAUDE.md prime directive (every write goes through the
#           owning module's service; no raw INSERT, no RLS bypass)
# Tests:    06-backend/tests/test_us_cwp_helpers.py (the same payloads build
#           the test tenants) · 10-scripts/render-checks/cr068-a-switch-it-on.mjs
# Impacts:  management/commands/seed_portal_demo.py
# ───────────────────────────────────────────────────────
"""The portal's demo fixture — two utilities, provisioned through the real
sign-up service and branded through the real Company → Profile save.

WHY ITS OWN TENANTS. The stories are written against Pine Hill Water & Power
and the code's one seeded demo tenant is Brazos Bend, whose figures are
workbook-verified and guarded (G4, G61). Adding Pine Hill's colours to Brazos
Bend would move a guarded fixture for a screenshot; provisioning Pine Hill as
its own tenant moves nothing. Decision-log row 2026-09-03.

Wave A seeds what wave A's screens show: the two tenants, their brand, the
portal switched ON for Pine Hill with the five R8 switches, the strapline, the
four services as chips, the office hours and the emergency number. Oak Ridge
is live with its own strapline and colours and nothing of Pine Hill's
(US-CWP-001 TC-5).

Wave B adds the STREET the burst is on — `US-CWP-008` §4's four addresses, which
are what make the affected-area rule demonstrable: `1408 Elm St` with units A, B
and Common, `1412 Elm St`, and `22 Palm Ct` **outside** the area. Later waves
append their rows here — Maria Alvarez, her accounts and `BL-2608-0141` arrive
with wave E.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from apps.rating.constants import PRICE_HISTORY_EPOCH
from apps.customers import services as customers_services
from apps.customers import models as customers_models
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.rating import services as rating_services
from apps.portal import models
from apps.portal import settings_service
from apps.portal.seams import tenancy_seam
from apps.tenancy import models as tenancy_models
from apps.tenancy import published_content_sample
from apps.tenancy import services as tenancy_services
from core import numbering as core_numbering
from core.permissions import SYSTEM_ADMIN
from core.tenancy import tenant_context

#: US-CWP-001 §4 · US-CWP-069 §4 · US-CWP-070 §4. The owner is the System Admin
#: who turns the portal on; the password is a demo credential and never prod.
PINE_HILL: dict[str, Any] = {
    "signup": {
        "name": "Pine Hill Water & Power",
        "subdomain": "pine-hill",
        "state": "Texas",
        "services": ["water", "sewer", "trash", "electric"],
        "currency": "USD",
        "plan": "growth",
        "load_defaults": True,
        "owner": {
            "full_name": "Sarah Miller",
            "email": "sarah@pinehillwp.test",
            "password": "Pin3Hill!passw0rd",
            "phone": "+1 (512) 555-0148",
        },
    },
    "company": {
        "legal_name": "Pine Hill Water & Power",
        "dba_name": "Pine Hill Water & Power",
        "brand_primary_hex": "#EC3013",
        "brand_accent_hex": "#E15B47",
        "support_phone": "(512) 555-0148",
    },
    "settings": {
        "is_live": True,
        "quick_pay_enabled": True,
        "self_read_enabled": False,
        "plans_enabled": True,
        "requests_enabled": True,
        "outage_reporting_enabled": True,
    },
    "branding": {
        "strapline": "Your account, your bills and your meter readings — any time.",
        "front_page_services": ["water", "sewer", "trash", "electric"],
        "office_hours_text": "8am to 5pm, Monday to Friday",
        "emergency_phone": "(512) 555-0100",
    },
    # CR-068 wave D: eight answers (six published, one draft, one not shown),
    # six tips, three centres with the depot hidden, Thanksgiving on 26 Nov.
    "published_content": "pine_hill",
    #: US-CWP-015 §4 — Pine Hill runs the six the wireframe draws, so the
    #: seeded default IS its list and `quick_service_categories` stays empty.
    "quick_services": None,
    #: US-CWP-012 §4 — the priced addresses (wave C). Oak Ridge gets none,
    #: deliberately: TC-5 asks that `31 Palm Ct` on `/oak-ridge` answers with
    #: Oak Ridge's own premises *or a person will look at it*, and never Pine
    #: Hill's fees. An Oak Ridge premises at the same address would make the
    #: test pass for the wrong reason.
    "priced_addresses": True,
}

#: The second tenant, with nothing of Pine Hill's in it.
OAK_RIDGE: dict[str, Any] = {
    "signup": {
        "name": "Oak Ridge Water",
        "subdomain": "oak-ridge",
        "state": "Texas",
        "services": ["water"],
        "currency": "USD",
        "plan": "growth",
        "load_defaults": True,
        "owner": {
            "full_name": "Elena Ruiz",
            "email": "elena@oakridgewater.test",
            "password": "0akRidge!passw0rd",
            "phone": None,
        },
    },
    "company": {
        "legal_name": "Oak Ridge Water Supply Corporation",
        "dba_name": "Oak Ridge Water",
        "brand_primary_hex": "#0B6E4F",
        "brand_accent_hex": "#1F9D75",
        "support_phone": "(830) 555-0170",
    },
    "settings": {"is_live": True},
    "branding": {
        "strapline": "Clean water for the ridge, every day.",
        "front_page_services": ["water"],
        "office_hours_text": "9am to 4pm, Monday to Thursday",
        "emergency_phone": "(830) 555-0199",
    },
    # Its OWN one answer, one tip and one centre — enough for every isolation
    # case to have something to find on the wrong side.
    "published_content": "oak_ridge",
    "priced_addresses": False,
    #: ⚠ **OAK RIDGE'S LIST IS DIFFERENT ON PURPOSE — IT IS WHAT MAKES
    #: US-CWP-015 TC-6 AND TC-7 PROVABLE.** TC-7 asks that a RENAMED category
    #: shows its new label, so Oak Ridge calls a re-read *"Check my meter
    #: reading"*; TC-6 asks that a category only Oak Ridge configured is not
    #: offered on Pine Hill, so it carries `standpipe_permit`, which Pine Hill
    #: does not sell. A fixture where both utilities held the same list could
    #: not tell a tenant-configured list from a hardcoded one at all.
    "quick_services": [
        {"code": "re_read", "label": "Check my meter reading", "hint": "We will read it again", "needs_bill_number": False},
        {"code": "standpipe_permit", "label": "Standpipe permit", "hint": "For builders", "needs_bill_number": False},
        {"code": "other", "label": "Something else", "hint": None, "needs_bill_number": False},
    ],
}

FIXTURE_TENANTS: tuple[dict[str, Any], ...] = (PINE_HILL, OAK_RIDGE)

#: `US-CWP-008` §4 — the street the burst is on, and the address that is not.
#: The units on `1408 Elm St` are the reason the staff screen shows two figures
#: (two addresses, three units) rather than one.
PINE_HILL_PREMISES: tuple[dict[str, Any], ...] = (
    {
        "address_line": "1408 Elm St",
        "city": "Austin",
        "state": "TX",
        "postal_code": "78702",
        "units": ("A", "B", "Common"),
    },
    {
        "address_line": "1412 Elm St",
        "city": "Austin",
        "state": "TX",
        "postal_code": "78702",
        "units": (),
    },
    {
        "address_line": "22 Palm Ct",
        "city": "Austin",
        "state": "TX",
        "postal_code": "78702",
        "units": (),
    },
)

#: ⚠ **WHY THE COUNTER STARTS AT 412 AND IS NOT AN INVENTED NUMBER.**
#: Every portal document writes the reference a passer-by is handed as
#: `RP-26-0412` — `US-CWP-007` §4, `US-CWP-009`, `US-CWP-010` §4, the wireframes
#: and the wave-B demo script. A brand-new series counts from 1, so a fixture
#: that left it there would print `RP-26-0001` on every screenshot and quietly
#: make eight documents wrong. A real utility switching a portal on in September
#: has a counter part-way through its year, so the fixture sets one:
#: `next_number = 412` on Pine Hill's own `interruption_report` series, which is
#: exactly what an admin may do on Settings → Numbering (`BR-TEN-035`,
#: forward-only). **No Brazos Bend figure moves and no other series is touched.**
PINE_HILL_REPORT_COUNTER_STARTS_AT = 412

#: Who owns the fixture's street. `BR-MET-150` makes a premises name its owner
#: by POINTING at a `premises_owners` row, so the fixture needs one party rather
#: than four; it is invented for the demo and belongs to nobody real.
FIXTURE_OWNER_NAME = "Elm Street Holdings"


def _owner_actor(tenant_id: uuid.UUID, email: str) -> Any:
    """The provisioned owner as the B12 §6a actor, so every fixture write is
    audited under a real user id rather than a made-up one."""
    from apps.identity import models as identity_models

    user = identity_models.User.objects.filter(tenant_id=tenant_id, email__iexact=email).first()
    return SimpleNamespace(id=getattr(user, "id", None), role=SYSTEM_ADMIN)


def seed_tenant(spec: dict[str, Any]) -> dict[str, Any]:
    """Provision one fixture utility and switch its portal on. Idempotent: a
    replay re-saves the same values and provisioning writes nothing new."""
    result = tenancy_services.provision_tenant(spec["signup"])
    tenant_id = uuid.UUID(str(result["id"]))
    with tenant_context(tenant_id):
        actor = _owner_actor(tenant_id, spec["signup"]["owner"]["email"])
        tenancy_services.save_company_profile(actor, dict(spec["company"]))
        settings_service.save_settings(actor, tenant_id, dict(spec["settings"]))
        by_code = {row["code"]: row["id"] for row in tenancy_seam.enabled_services(tenant_id)}
        branding = dict(spec["branding"])
        codes = branding.pop("front_page_services")
        branding["front_page_service_ids"] = [by_code[code] for code in codes if code in by_code]
        settings_service.save_branding(actor, tenant_id, branding)
        # CR-068 wave D (2026-09-04): the help answers, tips and service
        # centres the demo clicks. ⚠ Seeded by TENANCY's own module, because
        # those six tables are tenancy's (03-field-map.md §2) and B2 §2 forbids
        # a cross-module write — this file calls it, it does not write them.
        quick = spec.get("quick_services")
        if quick is not None:
            settings_service.save_branding(
                actor, tenant_id, {"quick_service_categories": quick}
            )
        content = spec.get("published_content")
        if content == "pine_hill":
            published_content_sample.seed_published_content(tenant_id)
        elif content == "oak_ridge":
            published_content_sample.seed_oak_ridge_content(tenant_id)
    return {
        "id": str(tenant_id),
        "subdomain": spec["signup"]["subdomain"],
        #: ⚠ The caller needs it to build the actor for the sample-data plant,
        #: and looking it back up would be a second place that knows which
        #: signup spec a tenant came from.
        "owner_email": spec["signup"]["owner"]["email"],
    }


def _fixture_owner(actor: Any) -> str:
    """One typed premises owner for the fixture's street (`BR-MET-150`).

    ⚠ **THE CATEGORY IS PICKED BY THE FIXTURE AND NOT BY THE CODE, AND THAT IS
    THE RULE BEING OBEYED RATHER THAN WORKED AROUND.** `create_premises_owner`
    REFUSES a payload with no category on purpose — *"picking `landlord`
    because it is the commonest would be this code answering a question about a
    real party on the utility's behalf"*. A demo fixture is allowed to answer it
    for its own invented party, so it does, in one place, in the open.
    """
    from apps.metering import models as metering_models
    from apps.metering import premises_owners as owner_services
    from apps.tenancy import models as tenancy_models
    from core import tenancy as core_tenancy

    # ⚠ **BOTH QUERIES ARE TENANT-SCOPED, AND THEY WERE NOT (`DEF-CWP-3757`).** This
    # runs as a seeding role with `rolsuper=t`, so RLS is skipped for every
    # query the process makes — which is exactly the condition CLAUDE.md hard
    # rule 1 names ("no cross-tenant queryset") and the only condition under
    # which an unscoped filter here is visible. On an EMPTY database both of
    # these were right by accident, because one tenant existed. On a database
    # that already holds a sample utility — which is every proof-db template,
    # the whole point of which is to be realistic — the category query returned
    # ANOTHER TENANT'S row and handed its UUID to `create_premises_owner`, whose
    # validator IS scoped and correctly refused it:
    #
    #     core.errors.ValidationError: VAL-005 (metering.premises_owner.category_unknown)
    #
    # The refusal names the category and not the tenant, so it reads as a
    # missing lookup rather than as a leak. The owner query had the same shape
    # one line up: seeding the SECOND utility would find the FIRST one's owner
    # by name and return an id belonging to somebody else.
    tenant_id = core_tenancy.current_tenant_id()
    existing = metering_models.PremisesOwner.objects.filter(
        tenant_id=tenant_id, name=FIXTURE_OWNER_NAME
    ).first()
    if existing is not None:
        return str(existing.id)
    categories = tenancy_models.PremisesOwnerCategory.objects.filter(tenant_id=tenant_id)
    category = (
        categories.filter(code__iexact="landlord").first()
        or categories.order_by("code").first()
    )
    if category is None:  # a tenant with no owner categories cannot hold a typed owner
        raise RuntimeError("no premises-owner category is seeded on this tenant")
    return str(
        owner_services.create_premises_owner(
            actor, {"name": FIXTURE_OWNER_NAME, "category": str(category.id)}
        )["id"]
    )


def seed_street(actor: Any, specs: tuple[dict[str, Any], ...] = PINE_HILL_PREMISES) -> int:
    """The four addresses of `US-CWP-008` §4, through metering's own service.

    Idempotent on the address line: a replay finds the row and creates nothing,
    which is what lets `seed_portal_demo` be run twice on one database without
    a second Elm St.
    """
    from apps.metering import models as metering_models

    owner_id = _fixture_owner(actor)
    created = 0
    for spec in specs:
        existing = metering_models.Premises.objects.filter(
            address_line=spec["address_line"]
        ).first()
        if existing is None:
            result = metering_services.create_premises(
                actor,
                {
                    "address_line": spec["address_line"],
                    "city": spec["city"],
                    "state": spec["state"],
                    "postal_code": spec["postal_code"],
                    "owner_id": owner_id,
                },
            )
            premises_id = result["id"]
            created += 1
        else:
            premises_id = existing.id
        for label in spec["units"]:
            if not metering_models.Unit.objects.filter(
                premises_id=premises_id, label=label
            ).exists():
                metering_services.create_unit(actor, {"premises_id": str(premises_id), "label": label})
                created += 1
    return created


def start_report_counter(
    tenant: Any, actor: Any, at: int = PINE_HILL_REPORT_COUNTER_STARTS_AT
) -> None:
    """Put Pine Hill's `RP-` counter where the story figures expect it.

    ⚠ **IT SEEDS THE SERIES ROW FIRST, AND THAT IS A REAL BUG THIS FIXTURE MET
    RATHER THAN A PRECAUTION.** `interruption_report` is the thirtieth series
    and every tenant provisioned before it existed has NO ROW for it — the
    counter is not zero, it is absent — so `create_interruption` refuses with
    *"no report numbers are set up"* and the whole guest flow 500s on a tenant
    that was seeded yesterday. `tenancy.seed_reference_data_for_tenant` is the
    repair door that module publishes for exactly this (its docstring: *"a
    tenant that signed up before a list existed had no way to get it, ever"*),
    and it is idempotent, so calling it on a fresh tenant writes nothing.

    ⚠ **FORWARD ONLY** (`BR-TEN-035`): a counter already past `at` is LEFT
    ALONE. Winding one back would hand out a number this tenant has already
    issued, which is the one thing that rule forbids outright.
    """
    tenancy_services.seed_reference_data_for_tenant(tenant, actor, structural_only=True)
    row = tenancy_models.NumberSeries.objects.filter(
        series=core_numbering.INTERRUPTION_REPORT
    ).first()
    if row is not None and row.next_number < at:
        row.next_number = at
        row.save(update_fields=["next_number"])


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave C — the priced addresses behind CWP-008 (US-CWP-012 §4)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **EVERY FIGURE BELOW IS THE STORY'S OWN TEST DATA, QUOTED.** `US-CWP-012`
# §4: *"Premises `31 Palm Ct, Austin TX 78702`: Water available, connection
# `$185.00`, deposit `$150.00`; Sewer available, included, no deposit; Trash
# available, `$0.00`; Electric **not present**. Occupied premises `1408 Elm St ·
# A` for TC-3. Unknown `77 Nowhere Ln`."* Changing one of them changes what the
# wave demonstrates, so they are named here once and nowhere else.
#
# ⚠ **AND THE THREE PRESENTATIONS ARE THREE DIFFERENT SEEDED FACTS**, which is
# the point of the fixture rather than an accident of it:
#
#   Water     a one-time charge priced at $185.00  ->  `$185.00`
#   Sewer     NO one-time charge attached at all   ->  `Included`
#   Trash     a one-time charge priced at $0.00    ->  `$0.00`
#   Electric  no service point at the address      ->  `NOT HERE`, no fee
#
# `US-CWP-012` TC-4 is explicit that the fourth must not read `$0.00`, *"which
# means free"*. A fixture that gave trash no charge either could not tell the
# second row from the third and the test would pass over a real bug.

WATER_CONNECTION_FEE = Decimal("185.0000")
TRASH_CONNECTION_FEE = Decimal("0.0000")
RESIDENTIAL_DEPOSIT = Decimal("150.0000")

#: Used by `tests/test_us_cwp_012_availability.py` TC-6, which builds the
#: future-dated plan itself — see `seed_priced_addresses` for why the fixture
#: cannot.
FUTURE_WATER_CONNECTION_FEE = Decimal("220.0000")

PALM_CT = "31 Palm Ct"
ELM_ST = "1408 Elm St"

#: `US-CWP-012` TC-3's occupier and `US-CWP-013` TC-2's returning customer are
#: the same person, deliberately: recognising somebody who has held an account
#: here before is only demonstrable against somebody who has.
OCCUPIER_NAME = "Maria Alvarez"
OCCUPIER_PHONE = "(512) 555-0134"

#: What a unit of each service is priced at. Wave C quotes a CONNECTION FEE and
#: prices no consumption at all, so these are the smallest lawful numbers that
#: let a plan publish — NOT figures any story asserts, and named as such so
#: nobody reads them as the fixture's prices.
#: ⚠ **WATER IS PRICED IN `gal` AND NOT `kgal`, AND THAT IS A CORRECTION
#: (`DEF-CWP-4166`, CR-068 wave H).** `BR-MET-1160` validates a read's unit
#: against the unit the TARIFF prices in, and refuses the pair as
#: `unit_mismatch` — *"declaring a conversion does NOT clear this flag: nothing
#: in `apps/billing/` or `apps/rating/pricing/` converts, so the engine still
#: refuses the bill"* (`DEF-3107`, open). Wave H puts a real meter on
#: `1408 Elm St · A` reading **gallons**, because every figure `US-CWP-040` and
#: `US-CWP-041` assert is in gallons — `4,820 gal`, an axis labelled in gallons.
#: Against a `kgal` tariff the 31 August read committed with `status =
#: unit_mismatch`, which means the bill engine would refuse this account: a demo
#: tenant that cannot be billed.
#: Only the LAST read was flagged, which is what made it easy to miss — the plan
#: is effective from thirty days ago, so it is the only read inside its window.
#: The money is unchanged: `0.0035` per gallon is `3.50` per thousand.
_UNIT_PRICE = {"water": "0.0035", "sewer": "2.0000", "trash": "1.0000"}
_UOM = {"water": "gal", "sewer": "kgal", "trash": "each"}
_BASE_CHARGE = {"water": "12.0000", "sewer": "8.0000", "trash": "9.0000"}


def _base_charge_for(actor: Any, service_code: str) -> None:
    """The service's DECLARED base charge code (`BR-RAT-088`).

    ⚠ **WITHOUT IT NO SCHEDULE CAN ACTIVATE ON THIS DEPLOYMENT.**
    `_guard_base_charge_code` used to be self-activating per tenant — a utility
    with no `is_base` code anywhere was simply pricing the old way — and
    `DEF-2923` inverted it: with the ruled chain serving R4, the charge code is
    the ONLY source of a base amount, so the gate now fires for every tenant. A
    fixture that skipped this fails at `create_rate_schedule` with
    `rating.schedules.no_base_charge_code`, which reads like a broken fixture
    and is the product telling the truth.
    """
    #: ⚠ **ANY EXISTING BASE FOR THIS SERVICE, NOT JUST OUR OWN CODE — AND THAT
    #: IS `DEF-CWP-3927`, WHICH EMPTIED THE WHOLE DEMO.** The old guard asked
    #: only whether `BASE-{SERVICE}-PORTAL` existed, so on a tenant that also
    #: carries the standard sample data this fixture minted a SECOND base for
    #: water, sewer and trash. Neither is scoped to a customer class, so both
    #: claim every account, and `resolve-subscription` then refuses every bill
    #: by name: *"2 charge codes declare themselves the base and all of them
    #: apply to this account — BASE-S, BASE-SEWER-PORTAL"*. Measured on a clean
    #: database: Pine Hill **0 invoices** against Oak Ridge's 100, with 49 of
    #: 50 units blocked and nine further fixture blocks failing off that one
    #: root. The engine is right to refuse; this fixture was wrong to give it
    #: two answers.
    #: ⚠ `service__code`, NOT `service`. `Charge.service` is a FOREIGN KEY to
    #: `tenancy.Service`, so filtering it by the code string raises
    #: `ValidationError: "water" is not a valid UUID` — which is how the first
    #: draft of this fix broke the very step it was moved to protect. The
    #: service layer above resolves the code for a WRITE; a raw read has to do
    #: it itself.
    existing = rating_models.Charge.objects.filter(
        service__code=service_code, is_base=True, deleted_at__isnull=True
    ).first()
    if existing is not None:
        return
    code = f"BASE-{service_code.upper()}-PORTAL"
    rating_services.create_charge(
        actor,
        {
            "code": code,
            "name": f"{service_code.title()} base service",
            "charge_type": "recurring",
            "service": service_code,
            "amount_rule": "flat",
            "amount": _BASE_CHARGE.get(service_code, "10.0000"),
            "effective_from": PRICE_HISTORY_EPOCH.isoformat(),  # CR-156-BRC10 — a seeded price has always applied
            "is_base": True,
        },
    )


def _schedule_for(actor: Any, service_code: str, name: str, *, effective_from: date) -> str:
    """An ACTIVE rate schedule — one flat tier, and it has to be active.

    ⚠ **A DRAFT SCHEDULE IS REFUSED BY `create_plan` ITSELF**, with
    `rating.plans.draft_schedule`, and finding that out is worth writing down:
    the tempting fixture is a schedule with an identity and no version
    (`BR-RAT-031`'s save-draft shape), which `publish_plan`'s *"every ticked
    service needs its schedule"* would appear to satisfy. It does not — the plan
    wizard refuses to BIND a draft schedule at all, which is right: a plan
    pointing at prices nobody has finished entering is a plan that cannot bill.
    """
    existing = rating_models.Tariff.objects.filter(name=name, deleted_at__isnull=True).first()
    if existing is not None:  # a replay, or a run that stopped half-way
        return str(existing.id)
    _base_charge_for(actor, service_code)
    payload: dict[str, Any] = {
        "name": name,
        "service": service_code,
        "model": "flat",
        "uom": _UOM.get(service_code, "each"),
        "currency": "USD",
        "effective_from": effective_from.isoformat(),
        "structure": {"unit_price": _UNIT_PRICE.get(service_code, "1.0000")},
    }
    base_code = _residential_base_code_id(service_code)
    if base_code is not None:
        payload["base_charge_code"] = base_code
    result = rating_services.create_rate_schedule(actor, payload)
    return str(result["id"])


def _residential_base_code_id(service_code: str) -> str | None:
    """`DEF-RAT-9842` — the base code this portal schedule NAMES.

    PO ruling 2026-10-06: a schedule naming no base code bills a `$0.00` base.
    Every portal account is RESIDENTIAL (`account_type: "residential"` below),
    so the schedule names the one live `is_base` code for the service whose
    class scope admits a residential account — this fixture's own
    `BASE-<SERVICE>-PORTAL` on a tenant with nothing else, or the standard
    sample's `BASE-W` / `BASE-E` beside it (`DEF-CWP-3927`). That is the code
    the retired class-narrowed pool picked, so no portal bill moves. None when
    there is not exactly one: the rating guard then decides, by name.
    """
    candidates = [
        code
        for code in rating_models.Charge.objects.filter(
            service__code=service_code, is_base=True, deleted_at__isnull=True
        )
        if not code.applies_to_customer_classes
        or "residential" in code.applies_to_customer_classes
    ]
    return str(candidates[0].id) if len(candidates) == 1 else None


def _priced_plan(
    actor: Any, *, name: str, code: str, services: list[str], effective_from: date,
    fee_suffix: str, fees: dict[str, Decimal],
) -> str:
    """One published plan carrying the connection charges and the deposit.

    ⚠ **PUBLISHED, AND THAT MATTERS TO THE PUBLIC READ.** A draft plan prices
    nothing (`BR-RAT-030`), so quoting its fees on a public page would publish a
    price nobody had approved. `rating_seam.connection_fees` refuses a plan that
    is not published for exactly that reason.
    """
    existing = rating_models.RatePlan.objects.filter(code=code).first()
    if existing is not None:
        # A replay, or a run that stopped half-way. ⚠ **PUBLISH IT IF IT IS
        # STILL A DRAFT** rather than returning it as-is: a half-finished run
        # leaves a draft plan, and `metering.services._apply_unit_plan` refuses
        # to put a unit on one — with `metering.plan.tariff_unknown`, so as not
        # to leak which ids exist, which names the wrong problem on a replay.
        if existing.status == "draft":
            rating_services.publish_plan(actor, existing.id)
        return str(existing.id)
    payload = {
        "name": name,
        "code": code,
        "effective_from": effective_from.isoformat(),
        # ── `DEF-CWP-7001` / `DEF-BIL-7170` · THE PLAN STATES NO BASE ───────
        # ⚠ **THIS LOOP WROTE `"base_charge": "8.0000"` FOR EVERY SERVICE**,
        # while `_BASE_CHARGE` a few lines up declares water `12.0000`, sewer
        # `8.0000` and trash `9.0000` on the charge codes that actually price
        # them. So water was out by `$4.00` and trash by `$1.00`, and sewer
        # agreed only by coincidence — one retired column filled blindly, not
        # two opinions about trash.
        #
        # **The column is RETIRED** (PO 2026-09-28: *"we will never take
        # default value from plan $8.0 - that is retired"*), so the honest
        # fixture states nothing there and lets the charge code answer. A NULL
        # is a lawful plan service row — `rating.services` stopped requiring
        # the figure under `DEF-477` — and *"this plan states no base for
        # water"* is a different fact from *"water's base is zero"*, which is
        # a price.
        #
        # ⚠ **WRITING THE RIGHT NUMBER HERE WOULD HAVE BEEN THE WRONG FIX.**
        # Three services, two places, one figure each: the moment they can
        # disagree, something has to decide which wins, and deciding that is
        # exactly what the ruling took away. A fixture that states a base in
        # ONE place cannot drift.
        "services": [
            {
                "service": one,
                "currency": "USD",
                "tariff": _schedule_for(actor, one, f"{name} — {one}", effective_from=effective_from),
            }
            for one in services
        ],
    }
    plan = rating_services.create_plan(actor, payload)
    charge_rules = []
    for service_code, amount in fees.items():
        if service_code not in services:
            continue
        charge = rating_services.create_charge(
            actor,
            {
                # ⚠ Charge codes are capped at TWENTY characters
                # (`rating.services._validate_charge`), which is why the suffix
                # is `RES` and not the plan code — `CONN-WATER-PORTAL-RES` is
                # twenty-one and refused with `rating.too_long`.
                "code": f"CONN-{service_code.upper()}-{fee_suffix}",
                "name": f"Connection fee — {service_code}",
                "charge_type": "one_time",
                "service": service_code,
                "amount_rule": "flat",
                "amount": str(amount),
                "effective_from": PRICE_HISTORY_EPOCH.isoformat(),  # CR-156-BRC10 — a seeded price has always applied
            },
        )
        # ⚠ NO `amount_override`. PO 2026-08-19 ruling 1: *"no plan cannot
        # override prices"* — the validator refuses any POSITIVE value
        # (`rating.above_maximum`, maximum 0) because a positive override is a
        # plan repricing a charge, and `rating.resolution` does not consult the
        # column at all. The PRICE is the charge code's; the plan only binds it.
        charge_rules.append({"charge": charge["id"], "recurrence": "once"})
    residential = customers_models.AccountType.objects.filter(code="residential").first()
    rating_services.update_plan(
        actor,
        plan["id"],
        {
            "charge_rules": charge_rules,
            "deposit_rules": (
                [
                    {
                        "account_type_id": str(residential.id),
                        "amount": str(RESIDENTIAL_DEPOSIT),
                        "currency": "USD",
                    }
                ]
                if residential is not None
                else []
            ),
        },
    )
    rating_services.publish_plan(actor, plan["id"])
    return str(plan["id"])


def _put_on_plan(actor: Any, unit_id: Any, plan_id: str, services: list[str]) -> None:
    """The unit's services and its plan, through metering's own doors.

    ⚠ **THE PREMISES HAS TO DECLARE THE SERVICE FIRST, AND THE PRODUCT REFUSES
    OTHERWISE.** `BR-MET-119` (PO 2026-08-26, CR-036) is the chain **premises →
    units → meters**: *"a premises DECLARES what services are available at the
    address; a unit INHERITS that list and has none of its own"*, and PO
    verbatim, *"Refuse it ; if they want that servcie then they ahve to
    provision it on that unit or premise first"*. `seed_street` (wave B) creates
    `1408 Elm St` with **no** `services_available`, because a burst-main report
    needs an address and nothing else — so a wave-C fixture that went straight
    to `ensure_service_point` was refused, correctly, by the rule. The premises
    is updated through metering's own door first, which is what a utility would
    have done.
    """
    from apps.metering import models as metering_models

    premises = (
        metering_models.Unit.objects.filter(pk=unit_id)
        .select_related("premises")
        .first()
    )
    if premises is not None:
        declared = list(premises.premises.services_available or [])
        missing = [code for code in services if code not in declared]
        if missing:
            metering_services.update_premises(
                actor,
                premises.premises_id,
                {"services_available": declared + missing},
            )
    for code in services:
        metering_services.ensure_service_point(unit_id, code)
    unit = metering_models.Unit.objects.filter(pk=unit_id).only("rate_plan_id").first()
    if unit is not None and unit.rate_plan_id is None:
        metering_services.assign_unit_plan(actor, unit_id, {"tariff_id": plan_id})


def _occupy(actor: Any, unit_id: Any, *, name: str, phone: str) -> None:
    """One live account at an address — `US-CWP-012` TC-3's *somebody already
    has service here*.

    ⚠ **THE LONG WAY ROUND, THROUGH THE REAL DOORS**, because the short way is
    what hides defects (`DEF-658`'s own lesson) and because `BR-CUS-1024`
    refuses an account whose customer identifies nobody. The phone is in the
    `555-` range reserved for fiction, the shape `tests/identity_fixtures.py`
    already defines for the whole suite.

    ⚠ **AND ACTIVATION IS NOT OPTIONAL.** A `pending_activation` account is a
    draft: it derives no occupancy, so the address would still read as a NEW
    CONNECTION and TC-3 would pass over nothing.
    """
    if customers_models.Account.objects.filter(unit_id=unit_id).exists():
        return
    account = customers_services.create_account(
        actor,
        {
            "unit_id": str(unit_id),
            "account_type": "residential",
            "opened_at": "2026-01-05",
            "contact": {"full_name": name, "phone": phone},
            "customer": {"display_name": name, "kind": "person", "identity": {"phone": phone}},
            # ⚠ **THE PLAN ASKS A DEPOSIT, SO THE ACCOUNT MUST ANSWER IT
            # (`DEF-CWP-6424`).** Since `39d6ee638` (2.348.0, `OQ-CUS-12620`
            # (a)) *"No" only when the plan asks none* — and `_priced_plan`
            # prices a Residential deposit, so an account opened with no
            # deposit block is refused (`customers.deposit.planAsksDeposit`),
            # and every portal suite that seeds this street errored in setup.
            # `required` without `take_now` is the plan's figure ASSESSED and
            # left for the first bill: no money moves, so no balance, payment
            # or ledger figure these suites assert changes. The figure itself
            # is the plan's, filled in by the server, never typed here.
            "deposit": {"decision": "required"},
        },
    )
    customers_services.activate_account(actor, account["id"])


def seed_priced_addresses(actor: Any) -> dict[str, Any]:
    """`31 Palm Ct` priced, and `1408 Elm St · A` occupied.

    ⚠ **IDEMPOTENT PER STEP, NOT PER FIXTURE, AND THAT IS A CORRECTION.** The
    first draft guarded the whole thing with one *"does `31 Palm Ct` exist?"*
    check, and a run that stopped half-way then reported SUCCESS on the next
    replay while the occupied account was still missing. A fixture that says it
    seeded and did not is a walkthrough failing checks that read exactly like a
    broken screen — the trap `proof-db.sh`'s own header warns about in capital
    letters.

    ⚠ **TC-6 IS NOT SEEDED HERE, AND THE REASON IS THE PRODUCT REFUSING
    CORRECTLY.** That case needs a unit sitting on a plan whose window has not
    opened, and `metering.services._apply_unit_plan` will not create that state:
    it resolves through `seams.plan_ref`, which answers None for a plan that is
    not effective, and refuses with `metering.plan.tariff_unknown`. That refusal
    is the first line of defence and worth having, so the fixture does not reach
    around it with a raw `UPDATE` — the prime directive forbids that here, and
    `write_points.MODULE_WRITE_TABLES` says this file writes no model of its
    own. The case is proved where the state can be built honestly:
    `tests/test_us_cwp_012_availability.py` TC-6.
    """
    from apps.metering import models as metering_models

    today = date.today()
    plan_id = _priced_plan(
        actor,
        name="Portal Residential",
        code="PORTAL-RES",
        services=["water", "sewer", "trash"],
        effective_from=today - timedelta(days=30),
        fee_suffix="RES",
        # ⚠ SEWER IS ABSENT FROM THIS DICT AND THAT IS THE `Included` CELL. No
        # one-time charge is attached for sewer at all, so nothing extra is
        # payable to connect it — a different fact from trash's `$0.00`, a
        # charge the utility configured and priced at zero (US-CWP-012 TC-4).
        fees={"water": WATER_CONNECTION_FEE, "trash": TRASH_CONNECTION_FEE},
    )

    palm = metering_models.Premises.objects.filter(address_line=PALM_CT).first()
    if palm is None:
        palm_result = metering_services.create_premises(
            actor,
            {
                "address_line": PALM_CT,
                "city": "Austin",
                "state": "TX",
                "postal_code": "78702",
                "services_available": ["water", "sewer", "trash"],
                "owner_id": _fixture_owner(actor),
            },
        )
        palm_id = palm_result["id"]
    else:
        palm_id = palm.id
    palm_unit = metering_models.Unit.objects.filter(premises_id=palm_id).first()
    if palm_unit is None:
        created = metering_services.create_unit(
            actor,
            {
                "premises_id": str(palm_id),
                "label": "Unit A",
                "services": ["water", "sewer", "trash"],
                "plan": {"tariff_id": plan_id},
            },
        )
        palm_unit_id = created["id"]
    else:
        palm_unit_id = palm_unit.id
        _put_on_plan(actor, palm_unit_id, plan_id, ["water", "sewer", "trash"])

    # `1408 Elm St` already exists — wave B seeds the street the burst is on,
    # with no services and no plan. Wave C gives its Unit A water, a plan and an
    # occupant, which is what makes TC-3 read MOVE-IN rather than NEW CONNECTION.
    elm_unit = metering_models.Unit.objects.filter(
        premises__address_line=ELM_ST, label="A"
    ).first()
    if elm_unit is not None:
        # ⚠ **THREE SERVICES, NOT ONE, AND THE FIXTURE HAS ALWAYS SAID SO
        # (CR-068 wave H).** This read `["water"]` until 2026-09-06, while the
        # documents built on it named three: wave E's consequence panel is
        # specified to say *"Water/Sewer/Trash"* (`10-execution-plan.md` §348
        # demo script, step 4), and wave H's whole `BR-CWP-073` demonstration is
        # a metered service beside a `share` one and a `capacity` one — *"the
        # sewer panel: Billed on: Water used"*, *"trash: Billed on: Your 96 gal
        # cart"*. With water alone `CWP-033` draws one panel and the rule it
        # exists to prove cannot be seen at all.
        # The order matters: the services go on the unit BEFORE `_occupy` opens
        # the account, because `customers._open_service_agreements` derives the
        # account's services from the unit's service points AT OPENING. Adding
        # them afterwards leaves an account billed for one service on a unit
        # that has three.
        _put_on_plan(actor, elm_unit.id, plan_id, ["water", "sewer", "trash"])
        _occupy(actor, elm_unit.id, name=OCCUPIER_NAME, phone=OCCUPIER_PHONE)
    return {"palm_unit_id": str(palm_unit_id)}


#: ── CR-068 WAVE H · MARIA'S TWO YEARS, HER CORRECTED JUNE, AND HER KERB ─────
#: `US-CWP-040` §4 · `US-CWP-041` §4 · `US-CWP-043` §4, and every figure below is
#: one of theirs. Screens `CWP-033` (Usage), `CWP-034` (Every reading),
#: `CWP-037` (Meters and equipment).
#:
#: ⚠ **THE TWELVE ARE THE STORY'S OWN TWELVE, RE-ORDERED — AND THE RE-ORDERING
#: IS THE WHOLE REASON ONE SEED CAN SERVE BOTH SCREENS.** The two shipped test
#: fixtures describe DIFFERENT histories for the same meter:
#: `test_us_cwp_usage_helpers.twelve_months_of_water` puts 30 June 2026 at dial
#: `144,810`, and `test_us_cwp_041_readings.four_readings` puts that same date
#: at `144,600` estimated / `144,130` corrected. Both are green, because no test
#: builds both on one account — but a DEMO has only one meter, so a seed has to
#: pick, and picking either one makes the other screen wrong in front of a
#: customer.
#: This tuple is a PERMUTATION of `MONTHLY_GALLONS`, so the three figures
#: `US-CWP-040` §4 asserts are untouched by construction — total `48,120 gal`,
#: low `3,050`, high `4,820` — and the order is chosen so the closing dials fall
#: out as `four_readings`' own four: May `140,370`, June `144,130`, July
#: `148,220`, August `153,040`. Nothing was invented and nothing was reconciled
#: by hand; the multiset is the story's and the sequence is the only arrangement
#: of it that both stories can be true of.
USAGE_MONTHS_GALLONS: tuple[int, ...] = (
    4820, 4300, 3900, 3410, 3050, 3410, 4090, 4170, 4300, 3760, 4090, 4820,
)

#: ⚠ **TWENTY-FOUR MONTHS ARE SEEDED AND THE STORY ASKS FOR TWELVE, BECAUSE THE
#: KPI THE DEMO SCRIPT QUOTES CANNOT EXIST ON TWELVE.** The execution plan's
#: wave-H script reads *"`4,820 gal` this period, 18% above last August"*, and
#: `metering.monthly_usage_reads._metrics` measures the year-on-year change as
#: **the last twelve months against the twelve BEFORE them** — a total against a
#: total, not one August against another. `portal.selectors` says so in its own
#: comment and asks for the wider payload on purpose. So a twelve-month fixture
#: makes that tile answer `no_prior_reads`, honestly and uselessly, and the
#: person giving the demo is left explaining an absence.
#: These total **`40,778 gal`**, which is the total that makes the product's own
#: arithmetic print **`+18.00`** against this year's `48,120` — the figure is
#: DERIVED from the published read, never typed onto a screen.
#: Every month is strictly inside `3,050 … 4,820`, so switching the chart to 24
#: months still marks January 2026 as the low and the two `4,820` months as the
#: high, exactly as the twelve-month view does.
#:
#: ⚠ **ELEVEN AND NOT TWELVE, AND THE REASON IS A HARD FLOOR IN THE DATABASE
#: (`DEF-CWP-4167`).** `meter_reads` is RANGE-PARTITIONED on `read_at` and the
#: earliest partition this product creates is **`meter_reads_2024_09`**, so a
#: read dated before 1 September 2024 is refused by PostgreSQL itself. The
#: refusal is reported as `skipped_rows: [{reason: "database_refused"}]` with
#: `status: posted_nothing` — but `batch_status` still reads `posted`, and the
#: shared helper this seeder calls returns only `posted_reads`, so a seeder that
#: does not look at the skip list plants one fewer read than it planned and says
#: nothing. That is how the first draft of this fixture lost a month.
#: A month of usage needs a read at each END of it, so the oldest month this
#: fixture can state is **October 2024**: its opening baseline sits on 30
#: September 2024, the earliest date the database will accept.
#: `monthly_usage.yoy_change` sums *"over the months that are PRESENT — not
#: zero-filled"*, so eleven months totalling `40,778` compare correctly against
#: twelve, and `months_compared` travels with the answer saying `11` and `12`.
PRIOR_YEAR_GALLONS: tuple[int, ...] = (
    3803, 3570, 3375, 3297, 3336, 3511, 3706, 3880, 4016, 4113, 4171,
)

#: The dial a year before the twelve, and two years before them. `104,920` is
#: `153,040 − 48,120`, which is `test_us_cwp_usage_helpers`' own opening figure.
USAGE_OPENING_DIAL = 104920 - sum(PRIOR_YEAR_GALLONS)

#: `US-CWP-043` §4 — the three things at `1408 Elm St · A`, by SERIAL. B14 rule
#: 31: what a customer sees is what is stamped on the box, never a row id.
WATER_METER_SERIAL = "88-40219"
WATER_METER_ASSET_NO = "M-88402"
REFUSE_CART_SERIAL = "C-11840"
BACKFLOW_SERIAL = "BF-2210"

#: `US-CWP-041` §4 — the estimate, and the dial somebody finally walked out and
#: read. The correction is applied through `supersede_read`, the product's own
#: door, so the screen renders a shape the product can actually produce.
ESTIMATED_JUNE_DIAL = "144600"
CORRECTED_JUNE_DIAL = "144130"
JUNE_READ_ON = date(2026, 6, 30)
JUNE_CORRECTED_ON = date(2026, 7, 3)


#: The month the series starts in — October 2024, so it ends in August 2026 and
#: its opening baseline sits on 30 September 2024, the earliest date
#: `meter_reads`' partitions accept (see `PRIOR_YEAR_GALLONS`).
#: Held as a `(year, month)` pair because the arithmetic below is where this
#: fixture's one real bug lived: an earlier draft mixed a 0-based month into a
#: helper that wanted a 1-based one, shifted every read a month early, dropped
#: August 2026 off the end and landed the June correction on May's dial. The
#: seed reported a healthy-looking count while doing it.
USAGE_FIRST_MONTH = (2024, 10)


def _month_end(year: int, month: int) -> date:
    """The day the walk happens — the last of the month, however long it is.

    `month` is 1-based, the way a person says it. Passing the 0-based form is
    exactly the mistake described on `USAGE_FIRST_MONTH`.
    """
    return date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)


def _month_end_offset(offset: int) -> date:
    """The last day of the month `offset` months after `USAGE_FIRST_MONTH`.

    `offset = -1` is the month BEFORE the first, which is where the opening
    baseline read sits.
    """
    year, month = USAGE_FIRST_MONTH
    ordinal = year * 12 + (month - 1) + offset
    return _month_end(ordinal // 12, ordinal % 12 + 1)


def _usage_read_plan() -> list[dict[str, Any]]:
    """The opening baseline, then twenty-four monthly walks ending 31 Aug 2026.

    ⚠ **REGISTER VALUES, NEVER CONSUMPTIONS** — the product derives usage from
    consecutive dials (`BR-MET-106`), so a fixture that typed a gallons figure
    would be asserting its own arithmetic instead of the product's. The dial
    climbs by each month's gallons, which is what makes a reading and its
    used-since agree the way a real register does.

    ⚠ **TWENTY-FIVE READS FOR TWENTY-FOUR MONTHS, AND THE EXTRA ONE IS THE
    POINT.** A month's consumption is the difference between its own closing
    dial and the one before it, so the FIRST read of a lineage carries
    `consumption = NULL` — it is a baseline, not a month. Seed twenty-four reads
    and the oldest month is silently unusable, which costs the year-on-year
    comparison the month it needs at the far end.
    """
    plan: list[dict[str, Any]] = [
        {"read_on": _month_end_offset(-1), "register": str(USAGE_OPENING_DIAL)}
    ]
    dial = USAGE_OPENING_DIAL
    for offset, gallons in enumerate((*PRIOR_YEAR_GALLONS, *USAGE_MONTHS_GALLONS)):
        read_on = _month_end_offset(offset)
        dial += gallons
        register = str(dial)
        # ⚠ **JUNE 2026 IS POSTED AS THE ESTIMATE AND CORRECTED AFTERWARDS.**
        # Posting the corrected dial and then "correcting" it would leave the
        # screen with a correction that changed nothing — `US-CWP-041` TC-3 is
        # about a customer seeing the SIZE of what was put right.
        if read_on == JUNE_READ_ON:
            register = ESTIMATED_JUNE_DIAL
        plan.append({"read_on": read_on, "register": register})
    return plan


def seed_usage_and_equipment(actor: Any) -> dict[str, Any]:
    """`CWP-033`, `CWP-034` and `CWP-037` given something honest to draw.

    ⚠ **WITHOUT THIS THE THREE SCREENS OPEN EMPTY ON THE DEMO TENANT AND ARE
    RIGHT TO** (`10-execution-plan.md` wave H, the ⚠ note on `H4`). The sample
    plant reads the ESTATE's meters; Maria's account is the portal fixture's own
    and had no meter, no reading and no month against it, so a browser pointed
    at `/usage` drew nothing and a lane would reasonably have concluded the
    screen was broken.

    Everything is written through the OWNING module's own door — `create_asset`
    for the three assets, metering's stage → validate → commit pipeline for the
    reads, `supersede_read` for the correction — because
    `apps/portal/write_points.py` lets this file write only *"through the owning
    modules' services (never a raw write)"* and `G81` enforces it. The
    `is_sample` tag is written by each owning module for the same reason
    (`BR-TEN-057`), so what this plants, `BR-TEN-061` can remove.
    """
    from apps.assets import sample_data as assets_sample
    from apps.assets import services as asset_services
    from apps.metering import models as metering_models
    from apps.metering import sample_data as metering_sample

    unit = (
        metering_models.Unit.objects.filter(premises__address_line=ELM_ST, label="A")
        .select_related("premises")
        .first()
    )
    if unit is None:
        return {"seeded": False, "why": "1408 Elm St · A is not seeded on this tenant"}
    account = customers_models.Account.objects.filter(unit_id=unit.id).first()
    if account is None:
        return {"seeded": False, "why": "no account is open at 1408 Elm St · A"}

    #: `US-CWP-043` §4. Each through `create_asset`, which mints the service
    #: point when the unit has none — `BR-AST-028`'s premises-first creation.
    from apps.assets import models as asset_models

    existing = set(
        asset_models.Asset.objects.filter(
            tenant_id=unit.tenant_id,
            asset_no__in=[WATER_METER_ASSET_NO, REFUSE_CART_SERIAL, BACKFLOW_SERIAL],
        ).values_list("asset_no", flat=True)
    )
    equipment: list[dict[str, Any]] = [
        {
            "type": "meter",
            "asset_no": WATER_METER_ASSET_NO,
            "serial_no": WATER_METER_SERIAL,
            "service": "water",
            "unit": "gal",
            "read_method": "walk_by",
            "multiplier": "1",
            "unit_id": str(unit.id),
            "install_date": "2021-03-04",
            "location_note": "Front boundary box",
            "status": "active",
        },
        {
            #: ⚠ **A CART IS EQUIPMENT, AND IT HAS NO LAST READ** — `US-CWP-043`
            #: TC-2's whole point. `BR-MET-106`'s sister rule: an EMPTY cell is
            #: not a zero, because nobody reads a wheelie bin.
            "type": "container_cart",
            "asset_no": REFUSE_CART_SERIAL,
            "serial_no": REFUSE_CART_SERIAL,
            "service": "trash",
            "unit_id": str(unit.id),
            "install_date": "2024-01-15",
            "location_note": "Rear alley",
            "status": "active",
            "size_class": "CART-96",
        },
        {
            #: `US-CWP-043` TC-3 — the chip comes from the EXISTING maintenance
            #: cadence (`BR-AST-007`), never from a word typed on the row. Last
            #: tested 14 Nov 2025 on a twelve-month interval, so the next test is
            #: 14 Nov 2026 and the row reads TEST DUE NOV without being overdue.
            "type": "backflow",
            "asset_no": BACKFLOW_SERIAL,
            "serial_no": BACKFLOW_SERIAL,
            "service": "water",
            "unit_id": str(unit.id),
            "install_date": "2021-03-04",
            "location_note": "Front boundary box",
            "status": "active",
            "last_test_date": "2025-11-14",
            "test_interval_months": 12,
        },
    ]
    created = 0
    for payload in equipment:
        if payload["asset_no"] in existing:
            continue
        asset_services.create_asset(actor, payload)
        created += 1
    #: `BR-TEN-057` — assets writes its own tag, so `BR-TEN-061` can take these
    #: back out again.
    assets_sample.tag_sample_assets([row["asset_no"] for row in equipment])

    posted = metering_sample.seed_account_read_history(
        actor,
        asset_no=WATER_METER_ASSET_NO,
        service="water",
        read_method="walk_by",
        source_detail="walk_by",
        reads=_usage_read_plan(),
    )
    #: ⚠ **MARKED AS AN ESTIMATE BEFORE IT IS CORRECTED, AND THE ORDER IS THE
    #: WHOLE OF `US-CWP-041`'s CENTRAL CASE.** `portal_reads` finds a correction
    #: by looking through the superseded rows for an ESTIMATED one, so a row
    #: marked afterwards is a correction `CWP-034` will not draw. Run the other
    #: way round, the browser showed June as an ordinary walked reading with
    #: `estimated: false` and `correction: null` — the screen rendering
    #: perfectly and the story's whole point missing.
    metering_sample.mark_sample_read_estimated(
        asset_no=WATER_METER_ASSET_NO, read_on=JUNE_READ_ON
    )
    corrected = metering_sample.correct_sample_read(
        actor,
        asset_no=WATER_METER_ASSET_NO,
        read_on=JUNE_READ_ON,
        value=CORRECTED_JUNE_DIAL,
        reason="Meter read on 3 July",
        corrected_on=JUNE_CORRECTED_ON,
    )
    #: `BR-MET-106` — the months the reads support. `supersede_read` already
    #: restates on its way out, so this is belt and braces for the run where
    #: nothing needed correcting.
    metering_sample.restate_sample_months(actor, account.pk)
    return {
        "seeded": True,
        "account_no": account.account_no,
        "assets_created": created,
        "reads_posted": posted,
        "june_corrected": corrected is not None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE SAMPLE SET'S PORTAL — what EVERY provisioned utility gets
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **EVERYTHING ABOVE THIS LINE SEEDS TWO HAND-BUILT TENANTS AND NOTHING
# ELSE, WHICH IS WHY A PROVISIONED UTILITY'S PORTAL WAS EMPTY.** `seed_portal_
# demo` provisions Pine Hill and Oak Ridge and calls the seeders above; a
# tenant that signs up through the real path runs `SAMPLE_MODULES` and never
# reaches this file at all. Measured 2026-09-07: `portal_settings` 1 on
# `pine-hill` and **0 on `brazosbend` and on every provisioned tenant**, the
# same for help answers, tips and service centres. Built, and not wired —
# CLAUDE.md hard-won law 2.
#
# The two functions below are the sample set's own, reached through
# `apps/tenancy/portal_sample.py` (the block body) and NOT through the two
# fixture tenants. They write nothing this file did not already write: the
# switches and the branding through `settings_service`, the login through
# `credentials`. See `12-governance/02-decision-log.md`, 2026-09-07.

#: The strapline every seeded portal opens with. One sentence (B14 rule 32);
#: `STRAPLINE_MAX_CHARS` is 140 and this is well inside it. Deliberately says
#: nothing a particular utility would have to correct.
SAMPLE_STRAPLINE = "Your account, your bills and your meter readings — any time."

#: What the front page says the counter is open. A tenant that has typed its
#: own hours into Company → Profile keeps them; this is the fallback.
SAMPLE_OFFICE_HOURS = "8am to 5pm, Monday to Friday"

#: ⚠ **A FICTIONAL NUMBER ON PURPOSE, AND FROM THE RANGE THE REST OF THE
#: SAMPLE ESTATE ALREADY USES.** `555-01xx` is reserved for fiction, and every
#: seeded contact in this repository is a `(512) 555-01xx`. A real utility's
#: own support number is used instead when Company → Profile holds one, which
#: is the common case after sign-up.
SAMPLE_EMERGENCY_PHONE = "(512) 555-0100"

#: 🔒 THE SEEDED CUSTOMER'S PASSWORD, AND IT IS A DEMO CREDENTIAL.
#:
#: It is written here, in the open, for the same reason every fixture password
#: in `10-scripts/render-checks/` is: the account it opens is a SAMPLE account
#: (`is_sample = True`), on a sample estate, holding invented bills. It reaches
#: no real customer's records because `seed_sample_portal_login` will not enrol
#: an account that is not tagged sample — that refusal is the safety property,
#: not the secrecy of this string.
#:
#: Twelve characters is the product's own floor (`pw_min_length`), so a
#: shorter one would be refused by the policy the portal enforces.
SAMPLE_PORTAL_PASSWORD = "Sample-Portal-2026!"


def seed_sample_portal_settings(actor: Any) -> dict[str, Any]:
    """The portal's OVERVIEW and BRANDING for the tenant in context.

    PO ruling 2026-09-07, verbatim: *"before step 29 this - you ahve to set all
    the self service data in settings -> configure -> Customer portal -
    {overview, branding, Help & Answer, Tips  + service centers }"*. This is
    the first two of those five; the other three are tenancy's own tables and
    are seeded by `published_content_sample`.

    ⚠ **IT WRITES ONLY WHEN THERE IS NO ROW, AND THAT IS THE IDEMPOTENCY THAT
    MATTERS.** `save_settings` is an upsert, so a naive replay would overwrite
    a strapline the utility had since typed — the sample plant can be re-run
    per block from the Sample data panel, and `manage.py load_sample_data` can
    be run at any time. A tenant that has opened Settings → Configure →
    Customer portal once already owns that row, and this leaves it alone.

    ⚠ **`is_live` IS SET TO TRUE, WHICH IS THIS FILE OVERRIDING A DEFAULT THAT
    EXISTS FOR A GOOD REASON** (`models.PortalSettings.is_live` defaults False,
    *"law 3: off until switched on"*). The reasoning is in the decision log,
    2026-09-07, and the short form is the PO's own ordering: the configuration
    exists so that *"a customer who can sign into the portal"* has somewhere to
    sign in to, and a portal that is not live serves the holding page to
    everyone including the seeded customer. Turning it off is one switch on the
    Overview segment, and `BR-TEN-061` removal takes the row with it.
    """
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    #: ⚠ **IT REPORTS `settings: 1` EITHER WAY, AND `wrote` IS WHAT SAYS WHICH.**
    #: The Sample data panel's number is *what this tenant has*, which is how
    #: every other block's count reads; a replay that answered 0 would make the
    #: line drop from 18 to 17 on a run that changed nothing.
    if models.PortalSettings.objects.filter(tenant_id=tenant_id).exists():
        return {
            "settings": 1,
            "wrote": False,
            "why": "this tenant already has a portal settings row",
        }

    settings_service.save_settings(
        actor,
        tenant_id,
        {
            "is_live": True,
            "quick_pay_enabled": True,
            #: ⚠ OFF, and it is the one that is off in every fixture in this
            #: repository (`CR-068` R8). A utility that wants customer-supplied
            #: readings turns it on deliberately.
            "self_read_enabled": False,
            "plans_enabled": True,
            "requests_enabled": True,
            "outage_reporting_enabled": True,
        },
    )

    tenant = tenancy_models.Tenant.objects.filter(pk=tenant_id).first()
    branding: dict[str, Any] = {
        "strapline": SAMPLE_STRAPLINE,
        #: The tenant's OWN services, whichever it ticked at sign-up —
        #: `save_branding` refuses any id the tenant does not sell
        #: (`US-CWP-070` TC-5), so a hardcoded four could not work here even
        #: if it were honest.
        "front_page_service_ids": [
            str(row["id"]) for row in tenancy_seam.enabled_services(tenant_id)
        ],
        "office_hours_text": (getattr(tenant, "service_hours", None) or SAMPLE_OFFICE_HOURS),
        "emergency_phone": (getattr(tenant, "support_phone", None) or SAMPLE_EMERGENCY_PHONE),
    }
    settings_service.save_branding(actor, tenant_id, branding)
    return {
        "settings": 1,
        "wrote": True,
        "services_on_front": len(branding["front_page_service_ids"]),
    }


def seed_sample_portal_login(actor: Any) -> dict[str, Any]:
    """ONE seeded customer who can actually sign in — the PO's step 29.

    ⚠ **IT ENROLS A SAMPLE ACCOUNT OR IT ENROLS NOTHING.** The account must
    carry `is_sample = True` and be linked to a customer; a real customer's
    account is never given a password by a seeder, whatever else is on the
    tenant. That refusal is what makes a demo login safe to ship in the sample
    set at all, and it is why `SAMPLE_PORTAL_PASSWORD` can be written in the
    open two screens up.

    Idempotent by refusal, like every other portal seeder here: an address that
    already holds a credential is left exactly as it is, so a replay never
    resets a password somebody has since changed.
    """
    from apps.portal import credentials

    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    account, email = _sample_account_to_enrol(tenant_id)
    if account is None:
        return {
            "credentials": 0,
            "why": "no sample account with a customer and an email address is on file",
        }
    if credentials.credential_by_email(tenant_id, email) is not None:
        return {"credentials": 0, "email": email, "why": "already enrolled"}
    credentials.create_credential(
        tenant_id,
        account=account,
        email=email,
        password=SAMPLE_PORTAL_PASSWORD,
        otp_channel=models.CHANNEL_EMAIL,
    )
    return {"credentials": 1, "email": email, "account_no": account.account_no}


def _sample_account_to_enrol(tenant_id: Any) -> tuple[Any, str]:
    """The lowest-numbered SAMPLE account that a person could actually sign in
    to: linked to a customer (`create_credential` refuses anything else) and
    holding a primary contact with an email address.

    ⚠ **THE LINK IS THE PART THAT IS NOT OBVIOUS.** Measured on `brazosbend`,
    2026-09-07: 78 accounts, of which **21 have no `customer_accounts` row at
    all** — the workbook estate's `A-` series. Enrolling one of those raises
    *"this account is linked to no customer, so there is nobody to enrol"*,
    which reads like a broken seeder and is the rule working.
    """
    links = {
        row.account_id
        for row in customers_models.CustomerAccount.objects.filter(tenant_id=tenant_id).only(
            "account_id"
        )
    }
    for account in (
        customers_models.Account.objects.filter(tenant_id=tenant_id, is_sample=True)
        .order_by("account_no")
        .iterator()
    ):
        if account.pk not in links:
            continue
        contact = (
            customers_models.Contact.objects.filter(
                tenant_id=tenant_id, account_id=account.pk, is_primary=True
            )
            .exclude(email=None)
            .exclude(email="")
            .order_by("created_at")
            .first()
        )
        if contact is not None:
            return account, str(contact.email)
    return None, ""


def seed_portal_fixture(*, with_priced_addresses: bool = True) -> list[dict[str, Any]]:
    """Both tenants, and Pine Hill's street. Returns what was provisioned, for
    the command's summary.

    `with_priced_addresses=False` leaves wave C's priced street to the caller,
    to be seeded AFTER the sample-data plant — see the comment on the call
    below, and `DEF-CWP-3927` for what happens when it runs before.
    """
    seeded = [seed_tenant(spec) for spec in FIXTURE_TENANTS]
    pine = seeded[0]
    with tenant_context(uuid.UUID(pine["id"])):
        actor = _owner_actor(uuid.UUID(pine["id"]), PINE_HILL["signup"]["owner"]["email"])
        pine["premises_rows_created"] = seed_street(actor)
        start_report_counter(tenancy_models.Tenant.objects.get(pk=uuid.UUID(pine["id"])), actor)
        # CR-068 wave C: the prices `CWP-008` quotes, and the occupied unit that
        # makes `1408 Elm St` read as a MOVE-IN.
        #
        # ⚠ **DEFERRED WHEN THE CALLER IS ALSO GOING TO PLANT THE SAMPLE DATA
        # (`DEF-CWP-3927`).** This step mints a base charge code for each of
        # water, sewer and trash so its quote plan can publish, and the standard
        # plant mints its own — two bases per service, and every bill refused.
        # Running it AFTER lets `_base_charge_for` find the standard base and
        # reuse it, so exactly one base per service exists whichever order a
        # caller chooses. A caller that plants no sample data (the default) is
        # unchanged and gets its prices here, as before.
        if with_priced_addresses and PINE_HILL.get("priced_addresses"):
            seed_priced_addresses(actor)
    return seeded
