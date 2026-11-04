# ── Trace ──────────────────────────────────────────────
# Defect:   **DEF-2310** — `tenant_services.metered` had a READER and no WRITER,
#           so BR-RAT-081's declaration could not be made from any screen or API
#           and BR-RAT-090's per-cart billing was unreachable on every shipped
#           tenant. `grep metered=False` across `apps/` found one TEST HELPER
#           and nothing else.
#           **DEF-2311** — `tenant_services.billed_uom` / `conversion_factor`,
#           read by metering, assets and rating through
#           `tenancy.selectors.service_billed_uoms()`, written by nothing at
#           all, so every tenant's answer was `None`.
# Rules:    **BR-RAT-081** (a service is DECLARED metered or unmetered — PO
#           2026-08-20, verbatim *"yes we have to say service is meter or
#           unmetered"*) · **BR-RAT-090** (an unmetered service's quantity is a
#           COUNT of its assets on the unit; ratified 3 carts × $15.00 = $45.00,
#           remove one and the next bill is $30.00) · **BR-RAT-038** (the
#           register→billed UoM gate: match, or state a conversion factor — no
#           silent conversion) · **BR-MET-710** (the count crosses the billing
#           seam UNITLESS and takes the tariff's own unit) · **BR-TEN-810**
#           (NEW — the declaration is forward-only: nothing already issued
#           moves) · BR-TEN-016 (one audit row per settings write) ·
#           CLAUDE.md hard rule 1 (tenant scoping), rule 2 (no float on a stored
#           figure), rule 4 (financial immutability), rule 7 (audit)
# Related:  DEF-495 (gave the column its first reader) · DEF-1813 (built the
#           whole bill path behind it, and filed both of these on its way past)
#           · DEF-515 (the same shape one column over, in rating)
# ───────────────────────────────────────────────────────
"""⚠ **AMENDED 2026-09-02 — `BR-TEN-1180` (`DEF-2409`) GAVE THIS DECLARATION A THIRD
VALUE, AND EVERY CASE BELOW STILL ASSERTS WHAT IT WAS WRITTEN TO ASSERT.**

`DEF-2310` is the defect that gave `BR-RAT-081`'s declaration a WRITER. The PO's ruling of
2026-09-02 changed the declaration's VOCABULARY and not its writer: the field is
`billing_basis`, it carries `metered` · `share` · `capacity`, and **`capacity` is exactly
what `metered=False` meant here** — trash priced by a COUNT of the unit's carts
(`BR-RAT-090`; 3 × `$15.00` = `$45.00`, unchanged and still asserted below).

The word *unmetered* survives all through this file and is still the right word for the
CONCEPT — `unmetered_service_codes()` keeps its name. What could not survive is the
BOOLEAN, because sewer reads no register AND is not priced by a count, so neither of its
two values was true for sewer.

DEF-2310 / DEF-2311 — a utility can now SAY what kind of service it sells.

**WHAT A UTILITY CAN DO THAT IT COULD NOT.** A refuse utility opens Settings →
Services, declares trash **unmetered** and billed per **cart**, and its next
bill for a property with three carts is **$45.00** — `3 × $15.00`, priced off
the carts standing on the unit. Before this commit that declaration could be
made by exactly one thing in the world: somebody typing an UPDATE against
`tenant_services`. Every figure DEF-1813 produced was reachable only that way.

**THE END-TO-END CASE IS `tc7` AND IT IS THE POINT OF THE FILE.** It declares
through `services.update_tenant_service` — the same call the S8 screen makes —
and touches the column through nothing else. If the writer is removed, `tc7`
cannot reach $45.00 at all.

**RED PROOF (r11 step 2d), MEASURED.** The whole file was run against an
untouched copy of the tree at this lane's starting commit `8febad7`: **10 of 11
FAILED**, most with
`core.errors.ValidationError: VAL-002 (settings.unknown_field)` from
`apps/tenancy/services.py:545` — the product refusing the very fields this work
adds — and `tc11` with
`ImportError: cannot import name 'SERVICE_MEASUREMENT'`.

⚠ **THE ELEVENTH PASSED THERE, AND FIXING THAT IS THE MOST USEFUL THING IN THIS
DOCSTRING.** `tc7` asserted only `pytest.raises(ValidationError)`, and the old
tree DID raise one — `settings.unknown_field`, because the field did not exist.
So a case written to prove *a float is refused* passed green against a product
that could not store a conversion factor at all. It now asserts the message key
per input, and goes red with the other ten.

The line to break to make `tc1` fail is the `"billing_basis"` branch of
`update_tenant_service`; the line to break to make `tc6` fail is the
`row.metered and …` guard in `_apply_service_uom` — dropping it refuses the
trash declaration BR-RAT-081 exists for, which is exactly the trap DEF-1813
recorded from the other side.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.assets import services as asset_services
from apps.billing import models as billing_models
from apps.billing import runs
from apps.customers import models as customer_models
from apps.customers import services as customer_services
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from apps.tenancy import api as tenancy_api
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from core import errors

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)
from tests.test_br_cus_068_master_bill import _by_service, _cycle
from tests.test_us_ten_helpers import FakeUser, api_call

pytestmark = pytest.mark.django_db

#: BR-RAT-090 / OQ-303, closed 2026-08-21. PO verbatim: *"they are bill 1 trash
#: can $15 - for example if you have 3 you multiple by 3"*.
PER_CART = Decimal("15.000000")
THREE_CARTS = Decimal("45.00")

AUG_START, AUG_END = date(2026, 8, 1), date(2026, 8, 31)
INSTALL = date(2026, 1, 5)


def _declare(actor, code, changes):
    """THE WHOLE POINT: the declaration goes through the product's own writer.

    Deliberately NOT `TenantService.objects.update(billing_basis=…)` — that is the
    shape `tests/test_def_161_designed_absence_bills.py` had to use ("written on
    tenant_services directly because no screen writes it yet") and it is the
    defect this file closes. A test that reaches past the product to arrange its
    fixture cannot fail on a missing write path.
    """
    return tenancy_services.update_tenant_service(actor, code, changes)


def _trash_plan(tenant):
    """One plan, TRASH only, $15.00 per cart, no base — so the bill total IS the
    cart line and a wrong count cannot hide inside a right-looking total."""
    plan = make_plan(tenant, name="Refuse only", services=("trash",))
    from apps.rating import selectors as rating_selectors

    for row in rating_selectors.plan_rate_schedules(plan.id):
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=row["tariff"],
            model="tiered",
            base_charge=Decimal("0"),
            uom="cart",  # CLAUDE.md rule 3 — the unit the PRICE is quoted per
            currency="USD",
            effective_from=date(2025, 1, 1),
            effective_to=None,
        )
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=version,
            seq=1,
            from_qty=Decimal("0"),
            to_qty=None,
            unit_price=PER_CART,
        )
    return plan


def _cart(actor, unit_id, number):
    """A non-measuring `container_cart` on the unit's trash service point."""
    return asset_services.create_asset(
        actor,
        {
            "type": "container_cart",
            "asset_no": f"D2310-CART-{number:04d}",
            "service": "trash",
            "unit_id": str(unit_id),
            "install_date": INSTALL.isoformat(),
        },
    )


def _world(actor, tenant, *, cycle_code, carts):
    """A unit taking TRASH ONLY with `carts` carts on it — and trash declared
    unmetered and billed per cart THROUGH THE SETTINGS SERVICE."""
    from apps.metering import premises_owners

    _declare(actor, "trash", {"enabled": True})
    _declare(actor, "trash", {"billing_basis": "capacity", "billed_uom": "cart"})
    cycle = _cycle(tenant, cycle_code)
    plan = _trash_plan(tenant)
    owner = premises_owners.create_premises_owner(
        actor, {"name": f"Cartway Refuse {cycle_code}", "category": "landlord"}
    )
    premises = make_premises(
        actor,
        address_line=f"8 Declaration Row {cycle_code}",
        services_available=["trash"],
        owner_id=owner["id"],
    )
    unit = make_unit(actor, premises["id"], label="Unit 1", services=["trash"])
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    for n in range(carts):
        _cart(actor, unit["id"], n + 1)
    created = customer_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": AUG_START.isoformat(),
            "contact": {"full_name": "Rosa Ibarra"},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block("Rosa Ibarra", account_type="residential"),
            "addresses": [
                {"kind": "mailing", "line1": "8 Declaration Row", "city": "Katy", "state": "TX"}
            ],
        },
    )
    customer_services.activate_account(actor, created["id"])
    return cycle, unit, customer_models.Account.objects.get(pk=created["id"])


def _bill(tenant, cycle, tag):
    prepared = runs.prepare_run(
        cycle_id=cycle.id, period_start=AUG_START, period_end=AUG_END, service_date=AUG_END
    )
    assert prepared.ready, "the fixture produced no billable account — the test would be vacuous"
    run = billing_models.BillRun.objects.create(
        tenant=tenant, cycle=cycle, period_start=AUG_START, period_end=AUG_END, idempotency_key=tag
    )
    return runs.calculate_account(prepared.ready[0], bill_run=run, service_date=AUG_END)


# ══════════════════════════════════════════════════════════════════════════
# (1) THE DECLARATION EXISTS — BR-RAT-081 has a writer
# ══════════════════════════════════════════════════════════════════════════
def test_def_2310_tc1__a_service_can_be_declared_unmetered(brazos, dana):
    """The reader `DEF-495` added now has something to read that a person put
    there. Before this call `unmetered_service_codes()` could only ever be empty
    on a tenant nobody had edited by hand.

    ⚠ **AMENDED 2026-09-02 (`BR-TEN-1180`) — THE OPENING ASSERTION WAS INVERTED
    AND THAT IS THE FIX, NOT A REGRESSION.** This case used to assert
    `unmetered_service_codes() == ()` immediately after ENABLING trash, because
    every service on every tenant was seeded METERED — which is exactly
    `DEF-2409`'s first fault (`_enable_signup_services` created all ten rows
    without naming the column, so all ten took the model default). Provisioning
    now names the basis from `SERVICE_DEFAULT_UOMS`, so **enabling trash IS
    already a declaration**, and the honest assertion is that the seed is right.
    The round trip it was written to prove is untouched below.
    """
    with tenant_ctx(brazos):
        tenancy_services.update_tenant_service(dana, "trash", {"enabled": True})
        # THE SEED, not the absence of one — DEF-2409's first fault, fixed.
        assert tenancy_selectors.unmetered_service_codes() == ("trash",)
        assert tenancy_selectors.service_row("trash")["billing_basis"] == "capacity"

        # A tenant that disagrees can still say so, and be believed.
        saved = tenancy_services.update_tenant_service(dana, "trash", {"billing_basis": "metered"})
        assert saved["billing_basis"] == "metered"
        assert tenancy_selectors.unmetered_service_codes() == ()

        # And back again — a declaration a tenant cannot reverse is a trap.
        saved = tenancy_services.update_tenant_service(dana, "trash", {"billing_basis": "capacity"})
        assert saved["billing_basis"] == "capacity"
        assert tenancy_selectors.unmetered_service_codes() == ("trash",)


def test_def_2310_tc2__the_declaration_is_audited_under_its_own_action(brazos, dana, audit_rows):
    """Hard rule 7 + BR-TEN-016. Its OWN action name, not the UoM one: a change
    of measurement basis moves money on every subsequent bill, and burying it
    inside `settings.service_uom.updated` would make it unfindable beside the
    bills it explains.

    ⚠ **AMENDED 2026-09-02 (`BR-TEN-1180`): THE CHANGE IT DRIVES IS NOW
    `metered → capacity`, BECAUSE TRASH IS SEEDED `capacity`.** It used to declare
    trash capacity on a row seeded metered. Provisioning names the basis now, so
    that write is a no-op and `_apply_service_billing_basis` returns early
    without an audit row — which is this case's OWN second clause ("a replay is
    not an event") firing on its first. Driving it the other way round proves the
    same rule against a row that actually moves.
    """
    with tenant_ctx(brazos):
        tenancy_services.update_tenant_service(dana, "trash", {"enabled": True})
        audit_rows.clear()
        tenancy_services.update_tenant_service(dana, "trash", {"billing_basis": "metered"})

        written = [r for r in audit_rows if r["action"] == "settings.service_metering.updated"]
        assert len(written) == 1
        assert written[0]["before"]["billing_basis"] == "capacity"
        assert written[0]["after"]["billing_basis"] == "metered"
        assert written[0]["after"]["service"] == "trash"
        assert written[0]["entity_type"] == "tenant_service"

        # An UNCHANGED declaration writes nothing — a replay is not an event.
        audit_rows.clear()
        tenancy_services.update_tenant_service(dana, "trash", {"billing_basis": "metered"})
        assert [r for r in audit_rows if r["action"] == "settings.service_metering.updated"] == []


def test_def_2310_tc3__the_screen_can_see_it(brazos, dana):
    """`built is not wired` (hard-won law 2): the value the write path stores
    must reach the read the screen renders, for a service that is OFF as well as
    one that is on."""
    with tenant_ctx(brazos):
        tenancy_services.update_tenant_service(dana, "trash", {"billing_basis": "capacity"})
        rows = {row["service"]: row for row in tenancy_selectors.services_overview()}

        assert rows["trash"]["billing_basis"] == "capacity"
        assert rows["trash"]["enabled"] is False  # declared without being sold
        # Every other service still answers the column's safe default.
        assert rows["water"]["billing_basis"] == "metered"
        assert set(rows["trash"]) >= {"billing_basis", "billed_uom", "conversion_factor"}


# ══════════════════════════════════════════════════════════════════════════
# (2) DEF-2311 — the billed unit, written for the first time
# ══════════════════════════════════════════════════════════════════════════
def test_def_2311_tc4__the_billed_unit_and_its_factor_are_writable(brazos, dana):
    """`service_billed_uoms()` is consumed by metering, assets and rating and
    answered `None` for every tenant in the product because nothing wrote it."""
    with tenant_ctx(brazos):
        assert tenancy_selectors.service_billed_uoms()["water"] == {
            "billed_uom": None,
            "conversion_factor": None,
        }

        tenancy_services.update_tenant_service(
            dana, "water", {"billed_uom": "ccf", "conversion_factor": "0.748052"}
        )

        declared = tenancy_selectors.service_billed_uoms()["water"]
        assert declared["billed_uom"] == "ccf"
        # NUMERIC(18,6) — six decimals, and never a float (hard rule 2).
        assert declared["conversion_factor"] == Decimal("0.748052")

        # `null` CLEARS it, and that has to work or a unit could be switched on
        # and never off again (DEF-515's shape).
        tenancy_services.update_tenant_service(
            dana, "water", {"billed_uom": None, "conversion_factor": None}
        )
        assert tenancy_selectors.service_billed_uoms()["water"] == {
            "billed_uom": None,
            "conversion_factor": None,
        }


def test_def_2311_tc5__a_metered_mismatch_with_no_factor_refuses_and_writes_nothing(brazos, dana):
    """BR-RAT-038 — *"mismatch with no factor → clear user message + rating
    blocked … no silent conversion"* — enforced where the sentence is typed
    rather than three weeks later inside a bill run."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as raised:
            tenancy_services.update_tenant_service(dana, "water", {"billed_uom": "ccf"})

        assert raised.value.message_key == "settings.services.factor_required"
        assert raised.value.code == errors.VAL_UOM_MISMATCH
        # NOTHING was stored — a refusal that half-wrote would be worse than none.
        assert tenancy_selectors.service_billed_uoms()["water"]["billed_uom"] is None


def test_def_2311_tc6__an_unmetered_service_needs_no_factor(brazos, dana):
    """⚠ **THE CASE DEF-1813 HIT FROM THE OTHER SIDE AND RECORDED.** Trash is
    billed per `cart`; no number converts a period into a cart, and none is owed
    — a capacity service has no register, so BR-RAT-038 has nothing to reconcile
    (BR-MET-710: the count crosses the seam unitless). Demanding a factor here
    would make the ONE declaration BR-RAT-081 exists for impossible to type.

    ⚠ **AMENDED 2026-09-02 (`BR-TEN-1180` / `DEF-3230`): TRASH'S SEEDED PRIMARY
    UNIT IS `cart`, NOT `month`.** This case used to assert `month`, and that
    cell is precisely what the PO corrected — *"Trash - it is capacity based and
    Cart sizes will decide price X how many Cart"*. `month` made the quantity a
    PERIOD when it is a COUNT, so there was nothing to multiply. **The rule this
    case guards is untouched and is arguably better demonstrated now:** primary
    `cart` and billed `cart` still need no conversion factor, and the branch
    below still proves the guard is not simply absent."""
    with tenant_ctx(brazos):
        tenancy_services.update_tenant_service(dana, "trash", {"enabled": True})
        assert tenancy_selectors.service_row("trash")["primary_uom"] == "cart"

        tenancy_services.update_tenant_service(
            dana, "trash", {"billing_basis": "capacity", "billed_uom": "cart"}
        )

        assert tenancy_selectors.service_billed_uoms()["trash"]["billed_uom"] == "cart"

        # …and the guard is not simply absent: declare it METERED with a billed
        # unit that DIFFERS from the primary, and the pair is refused.
        #
        # ⚠ **THE PAIR HAD TO CHANGE WITH THE SEED (`DEF-3230`).** This branch
        # used to send `billed_uom: "cart"` against a primary of `month`, which
        # was a mismatch while trash was seeded `month`. Trash's primary is
        # `cart` now, so that pair MATCHES and no factor is owed — the assertion
        # would have gone green for the wrong reason, which is worse than red.
        # `pickup` is the catalogue's other trash-scoped unit, so the mismatch is
        # real and stays inside the service.
        with pytest.raises(errors.ValidationError) as raised:
            tenancy_services.update_tenant_service(
                dana, "trash", {"billing_basis": "metered", "billed_uom": "pickup"}
            )
        assert raised.value.message_key == "settings.services.factor_required"


def test_def_2311_tc7__a_factor_is_a_positive_decimal_and_never_a_float(brazos, dana):
    """Hard rule 2 keeps binary floating point off every path a stored figure
    travels; zero and negative are not conversions at all."""
    with tenant_ctx(brazos):
        for bad, key in (
            (0.748052, "settings.services.factor_format"),
            ("nope", "settings.services.factor_format"),
            ("0", "settings.services.factor_positive"),
            ("-1", "settings.services.factor_positive"),
        ):
            with pytest.raises(errors.ValidationError) as raised:
                tenancy_services.update_tenant_service(
                    dana, "water", {"billed_uom": "ccf", "conversion_factor": bad}
                )
            # ⚠ THE MESSAGE KEY, NEVER MERELY "something refused". On the tree
            # before this lane every one of these four raised
            # `settings.unknown_field` — the field did not exist — so a bare
            # `pytest.raises(ValidationError)` PASSED against a product that
            # could not store a conversion factor at all. A check whose output
            # cannot tell pass from fail is worse than no check.
            assert raised.value.message_key == key
        assert tenancy_selectors.service_billed_uoms()["water"]["conversion_factor"] is None


# ══════════════════════════════════════════════════════════════════════════
# (3) ⚠ THE DELIVERABLE — $45.00 reached WITHOUT touching the database
# ══════════════════════════════════════════════════════════════════════════
def test_def_2310_tc8__three_carts_bill_forty_five_dollars_declared_through_the_service(
    brazos, dana
):
    """**3 × `$15.00` = `$45.00`, and the ONLY thing that made trash unmetered
    is `update_tenant_service` — the call the S8 screen makes.**

    DEF-1813 proved this arithmetic with the column set by a test helper. This
    proves the same figure with the column set by the product, which is the
    whole of DEF-2310: without it, the ruled walkthrough exists only for
    somebody with a database client.
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account = _world(dana, brazos, cycle_code="D2310-1", carts=3)

        invoice = _bill(brazos, cycle, "def-2310-tc8")

        assert _by_service(invoice)["trash"] == THREE_CARTS
        assert invoice.total == THREE_CARTS
        usage = [line for line in invoice.lines.all() if line.kind == "usage"]
        assert len(usage) == 1
        # CLAUDE.md rule 3 — three CARTS, never three of nothing.
        assert (usage[0].quantity, usage[0].unit) == (Decimal("3.000000"), "cart")


# ══════════════════════════════════════════════════════════════════════════
# (4) BR-TEN-810 — forward-only, and it says how many accounts it moves
# ══════════════════════════════════════════════════════════════════════════
def test_br_ten_810_tc9__changing_the_declaration_leaves_issued_bills_alone(brazos, dana):
    """**Nothing already issued moves** — CLAUDE.md hard rule 4. The change is
    about where the NEXT bill's quantity comes from, and the count of accounts
    taking the service travels back so the consequence is named rather than
    discovered."""
    with tenant_ctx(brazos):
        cycle, _unit, _account = _world(dana, brazos, cycle_code="D2310-2", carts=3)
        invoice = _bill(brazos, cycle, "def-2310-tc9")
        assert invoice.total == THREE_CARTS
        issued_total, issued_lines = invoice.total, invoice.lines.count()

        saved = tenancy_services.update_tenant_service(dana, "trash", {"billing_basis": "metered"})

        invoice.refresh_from_db()
        assert (invoice.total, invoice.lines.count()) == (issued_total, issued_lines)
        # …and the warning NAMES what the next bill run will do differently.
        assert saved["warnings"]["accounts_on_next_bill"] == 1


# ══════════════════════════════════════════════════════════════════════════
# (5) CLAUDE.md hard rule 1 — one tenant's declaration is its own
# ══════════════════════════════════════════════════════════════════════════
def test_def_2310_tc10__the_declaration_does_not_cross_a_tenant(brazos, dana, lonestar, erin):
    """A settings write is tenant-scoped like every other. Asserted rather than
    assumed, because `unmetered_service_codes()` decides whether a bill run
    demands a meter read."""
    with tenant_ctx(brazos):
        tenancy_services.update_tenant_service(dana, "water", {"billing_basis": "capacity"})
        assert tenancy_selectors.unmetered_service_codes() == ("water",)

    with tenant_ctx(lonestar):
        assert tenancy_selectors.unmetered_service_codes() == ()
        assert tenancy_selectors.service_row("water")["billing_basis"] == "metered"

    with tenant_ctx(brazos):
        assert tenancy_selectors.service_row("water")["billing_basis"] == "capacity"


def test_def_2310_tc11__the_seed_declares_trash_through_the_same_service(brazos, dana):
    """The demo fixture's block, applied to a provisioned tenant: it declares
    and it does NOT enable, so `unmetered_service_codes()` — which reads enabled
    services only — is still empty, and the declaration is already true the
    moment somebody switches trash on. That boundary is the whole reason this
    lane did not edit `apps/rating/sample_data.py` (DEF-1250 / DEF-2490)."""
    from apps.tenancy.management.commands.seed_demo import SERVICE_MEASUREMENT

    with tenant_ctx(brazos):
        for entry in SERVICE_MEASUREMENT:
            code = str(entry["service"])
            tenancy_services.update_tenant_service(
                dana, code, {k: v for k, v in entry.items() if k != "service"}
            )
            row = tenancy_selectors.service_row(code)
            assert row["billing_basis"] == "capacity"
            assert row["billed_uom"] == "cart"
            assert row["enabled"] is False

        assert tenancy_selectors.unmetered_service_codes() == ()

        tenancy_services.update_tenant_service(dana, "trash", {"enabled": True})
        assert tenancy_selectors.unmetered_service_codes() == ("trash",)


# ══════════════════════════════════════════════════════════════════════════
# (6) ⚠ THROUGH THE ENDPOINT THE SCREEN ACTUALLY CALLS
# ══════════════════════════════════════════════════════════════════════════
def test_def_2310_tc12__the_declaration_travels_the_whole_http_path(brazos, dana):
    """**`PUT /settings/services/trash`, the exact request the S8 modal sends.**

    `tc1`–`tc11` call the service; this calls the ROUTE, because the layer in
    between is where `DEF-2310` actually lived — `update_tenant_service` refused
    `billing_basis` as an unknown field, so the screen could have been built and the
    request would still have bounced. The response is what the screen re-renders
    from, so the three values are asserted ON IT and not read back separately.

    The clerk denial is asserted in the same case: BR-TEN-025's closed catalog
    and `SystemAdminOnly` are what stop a billing clerk changing how a service
    is measured, and a new field on an existing endpoint inherits that or it
    does not — reading the code is not the same as running it.
    """
    with tenant_ctx(brazos):
        tenancy_services.update_tenant_service(dana, "trash", {"enabled": True})

    saved = api_call(
        tenancy_api.service_update,
        "put",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
        data={"billing_basis": "capacity", "billed_uom": "cart"},
        service="trash",
    )
    assert saved.status_code == 200
    assert saved.data["billing_basis"] == "capacity"
    assert saved.data["billed_uom"] == "cart"
    assert saved.data["conversion_factor"] is None

    # The GET the screen loads from agrees with the PUT's own answer — a write
    # whose response cannot be re-read is a screen nobody can trust.
    listed = api_call(
        tenancy_api.services_settings,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
    )
    trash = next(row for row in listed.data if row["service"] == "trash")
    assert (trash["billing_basis"], trash["billed_uom"]) == ("capacity", "cart")

    # …and a billing clerk cannot change how a service is measured.
    denied = api_call(
        tenancy_api.service_update,
        "put",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        data={"billing_basis": "metered"},
        service="trash",
    )
    assert denied.status_code == 403
    with tenant_ctx(brazos):
        assert tenancy_selectors.service_row("trash")["billing_basis"] == "capacity"


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2310 + DEF-2311 (12-governance/10-defect-log.csv) · BR-RAT-081 · BR-RAT-038 · BR-TEN-810
# generated: 2026-08-28 by the service-declaration lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: tc9's `accounts_on_next_bill == 1` reads the customers seam, so it is a real count and not a null — on a deployment where that lane is unwired the key is None and the screen shows no sentence, which is the same discipline the BR-TEN-026 counts keep
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
