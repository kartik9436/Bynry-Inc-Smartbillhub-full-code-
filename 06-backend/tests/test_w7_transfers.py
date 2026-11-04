# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-004 (move-in) · US-CUS-005 (move-out) — a transfer is the
#           THIRD path beside them.   Screens: S89 (not built; task 7.4)
# Change:   CR-030 W7 tasks 7.1 (table + RLS, five steps, one commit for both
#           halves) · 7.2 (the exclusion contract) · 7.3 (the deposit carries
#           without a refund-and-recollect; arrears follow)
# Rules:    BR-CUS-015 · BR-CUS-017 · BR-CUS-023 · BR-CUS-024 · BR-CUS-025 ·
#           BR-CUS-030 · BR-CUS-054 · BR-CUS-057 · BR-CUS-081 · BR-CUS-082 ·
#           BR-CUS-089 · BR-CUS-097 · BR-MET-036 · CLAUDE.md rules 1, 2, 4, 5, 7
# Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.7.2 · §5.7.3 ·
#           §5.7.4 · §5.7.5 (TC-TRF-1..6) · §5.7.6 · §9
# Tests:    this file
# ───────────────────────────────────────────────────────
"""W7 · transfers — WHAT SURVIVED THE 2026-09-01 REVERSAL, AND WHERE THE REST WENT.

⛔ **READ THIS FIRST. TWENTY-SIX CASES LEFT THIS FILE ON 2026-09-01 AND THEY
WERE NOT DELETED FOR BEING WRONG — THE BEHAVIOUR THEY PINNED WAS REVERSED BY A
PO RULING.** Verbatim: *"dont create new account - we reassing that account -
bascailly I have sold my property - so account get transfer to new person or
business; if I move to new location then it is new Service request and we follow
the process"* (`BR-CUS-1030`, `CR-058` tasks 14–18).

W7 built a transfer as *"the same customer, a new address"*: `move_out` on one
account and `create_account` at a new unit, in one commit. **A transfer is now
the opposite job** — *a property being SOLD* — and the same account is
reassigned to a new customer: same number, same unit, same unbroken ledger.

**WHERE THE REMOVED CASES WENT:** every one of them is replaced, case for case,
in `tests/test_cr058_w4_transfer_reassigns.py`, which asserts the NEGATIVE of
what they asserted — the account is not closed, no second account exists, the
number and the unit are unchanged, no journal line is written. TC-TRF-3's
deposit, TC-TRF-9's arrear and TC-TRF-10's unreadable interest moved with them,
because ⚖️ **the debt now follows the property** (PO, the same day: *"money
follow property - new owner boutght everything property + debt also"*) and the
account it sits on does not move.

**WHAT STAYS HERE, AND WHY EACH IS STILL TRUE:**

  * **The exclusion contract (task 7.2).** *"A transfer appears only here"* is a
    COUNTING contract between tabs and is untouched by what a transfer DOES. Its
    static half still goes red on somebody else's commit, which is what B18 asks
    for.
  * **The table, the model and the RLS policy (TC-TRF-11b · 12 · 13 · 13a).**
    `transfers` is unchanged by the reversal: no column added, none removed, and
    `DEF-639`'s `NULLIF` form is still the form.
  * **Step 1's occupancy refusal.** Only an occupant may sell, for the same
    reason only an occupant could move: a draft never took the unit and a closed
    account has already left it.

⚠ **NOTHING HERE ASSERTS WHAT A TRANSFER DOES ANY MORE.** That is deliberate:
one file owns that contract now, and two would eventually disagree about it.

⚠ **AND THERE IS NO `_wire_interest` HELPER IN THIS FILE — `DEF-2589`, which
the register locates HERE and which was fixed somewhere else.**
`test_def2030_2031_wizard_doors.py:80` imported one from this module; nothing of
that name has ever been defined here, so the import raised at COLLECTION and
pytest answered `Interrupted: 1 error during collection` — which stops the
WHOLE marker selection. `pytest -m golden` and `pytest -m isolation` both ran
ZERO tests and G4 led with the harness's own *"33 PASS, 0 FAIL"*, so a dead
release gate read as a golden-figure problem. Running the same suites BY PATH
collects fine, which is why it survived a lane that ran them that way. The
import now points at `tests/test_w7_worklists`, and the note at that call site
is the one to read: the helper in `test_w5_eligibility_and_deposit_carry.py`
patches a DIFFERENT seam, so re-pointing at the nearest same-named function
would have gone green having proved nothing.

**EVERY FIGURE IN THE FIXTURES BELOW IS STILL SOMEBODY ELSE'S** — ❄️ WE-7 /
GT-23's frozen pair, $150.00 principal + $3.50 interest = **$153.50**, is B18
§5.7.6's own `deposit carried $153.50`. Nothing here invents a figure.
"""

import re
from decimal import Decimal
from pathlib import Path

import pytest

from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.customers import transfers
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests import identity_fixtures
from tests.isolation_helpers import (
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_actions,
    audit_rows,  # noqa: F401 — autouse BE-03 capture sink
    brazos,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

D = Decimal

# ── ❄️ WE-7 / GT-23, frozen: $150.00 held at the tenant's rate = $3.50 ──────
DEPOSIT_HELD = D("150.00")
DEPOSIT_INTEREST = D("3.50")
CARRIED = D("153.50")  # B18 §5.7.6 row 1: `deposit carried $153.50`
ARREAR = D("542.10")  # B18 §5.7.6 row 4: `arrear follows $542.10`, Jenna Park

TRANSFER_TABLES = ("transfers",)
MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "apps"
    / "customers"
    / "migrations"
    / "0021_cr030_w7_transfers.py"
)


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURE PLUMBING — real rows through real services (DEF-658: never the ORM,
# except for the two MONEY columns every service door deliberately refuses)
# ═══════════════════════════════════════════════════════════════════════════
def _plan(tenant, name="Residential Standard", service_code="electric"):
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _unit(actor, tenant, *, label="Unit A", service_code="electric"):
    """⚠ `service_code` is a parameter because the two fixture tenants do not
    enable the same services: Brazos Bend has Electric + Water, the isolation
    tenant `lonestar` has WATER ONLY. A hard-coded `electric` refuses on
    `metering.service_not_enabled` for lonestar, which is the tenant every
    isolation case needs."""
    premises = make_premises(actor, services_available=[service_code])
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan(tenant, service_code=service_code).id)}
    )
    metering_services.ensure_service_point(unit["id"], service_code)
    return unit


def _occupant(actor, unit, *, name="Iversen, Britt", opened_at="2026-07-01"):
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": opened_at,
            "contact": {"full_name": name},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
        },
    )


def _mover(
    actor,
    tenant,
    *,
    deposit=DEPOSIT_HELD,
    arrear=D("0"),
    name="Iversen, Britt",
    service_code="electric",
    label="18 Marten Row",
):
    """B18 §5.7.6 row 1 — the account a transfer starts FROM, with a customer
    entity linked (BR-CUS-054) because a transfer is *the same customer* at a
    new address and the customer is READ, never matched.

    ⚠ `deposit_on_file` and `balance` are written through the ORM and NOT
    through a service door, and that is the point rather than a shortcut:
    `services.REFUSED_FIELDS` refuses both on every client-facing path
    (BR-CUS-023 — the deposit is a lookup; BR-CUS-015 — the balance is the
    ledger's cache). A fixture that could set them through a door would mean the
    product had one.
    """
    unit = _unit(actor, tenant, label=label, service_code=service_code)
    account = _occupant(actor, unit, name=name)
    customers_models.Account.objects.filter(id=account["id"]).update(
        deposit_on_file=deposit, balance=arrear
    )
    # ⚠ **AN IDENTIFIER, NOT A NAME — `BR-CUS-1023` (PO 2026-09-01).** A name
    # alone no longer mints a Customer #, so a fixture that passed only a name
    # would produce an account with NO customer and every case below would fail
    # on `from_account_has_no_customer` rather than on its own subject. A phone
    # is the weakest identifier the rule accepts, which is why it is the one
    # used here.
    customer = customers_services.link_customer(
        account_id=account["id"],
        display_name=name,
        kind="person",
        identity={"phone": "+1-555-0101"},
        actor=actor,
    )
    return customer, customers_models.Account.objects.get(id=account["id"]), unit


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE FIVE STEPS (task 7.1)
# ═══════════════════════════════════════════════════════════════════════════
def test_step_1_refuses_an_account_that_does_not_occupy_a_unit(brazos, marcus):
    """BR-CUS-018 / BR-MET-036: a draft never took a unit and a closed account
    has already left one. Transferring either would schedule the closing of a
    tenancy that never happened."""
    with tenant_ctx(brazos):
        _customer, account, _u = _mover(marcus, brazos)
        customers_services.move_out(marcus, account.id, {"moved_out_on": "2026-08-01"})
        with pytest.raises(errors.BizError) as caught:
            transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
    assert caught.value.params["reason"] == transfers.REFUSAL_NOT_AN_OCCUPANT


# ═══════════════════════════════════════════════════════════════════════════
# 2 · ONE COMMIT FOR BOTH HALVES (task 7.1's heart)
# ═══════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE EXCLUSION CONTRACT (task 7.2) — B18 §5.7.3's counting contract
# ═══════════════════════════════════════════════════════════════════════════
def test_tc_trf_1c_no_move_list_builder_exists_that_bypasses_the_contract(brazos):
    """**THE STATIC HALF, AND IT IS THE ONE THAT WILL GO RED ON SOMEBODY ELSE'S
    COMMIT.**

    Measured 2026-08-25: neither the Move-ins nor the Move-outs list exists.
    `AccountsListPage.tsx` renders both tabs as `<ArrivesWith>` and there is no
    `move_in_list` / `move_out_list` of any name in `apps/customers/`. So there
    is nothing to filter today, and B18 §5.7.3 still demands the exclusion be
    ASSERTED — *"because nothing else will catch it"*.

    This case therefore asserts the contract at the only point it can be
    asserted: the moment a move list appears in this app, the file that defines
    it must call one of `EXCLUSION_CONTRACT`'s three published entry points. A
    lane that builds `GET /move-outs` and forgets meets this as a failure with
    its own filename in the message.
    """
    app_dir = Path(__file__).resolve().parents[1] / "apps" / "customers"
    definition = re.compile(
        r"^def\s+(move_?ins?_list|move_?outs?_list|list_move_?ins?|list_move_?outs?"
        r"|move_?in_rows|move_?out_rows)\b",
        re.MULTILINE,
    )
    offenders = []
    for path in sorted(app_dir.glob("*.py")):
        if path.name == "transfers.py":
            continue
        text = path.read_text(encoding="utf-8")
        if definition.search(text) and not any(
            name in text for name in transfers.EXCLUSION_CONTRACT
        ):
            offenders.append(path.name)
    assert offenders == [], (
        "a move-in / move-out list builder exists and does not apply the B18 §5.7.3 exclusion "
        f"contract: {offenders}. Call one of {transfers.EXCLUSION_CONTRACT}."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE MONEY (task 7.3) — carries, does not round-trip; arrears follow
# ═══════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════
# 5 · TENANT SCOPING AND RLS (CLAUDE.md hard rule 1)
# ═══════════════════════════════════════════════════════════════════════════
def test_tc_trf_12_the_model_and_the_live_table_agree_column_for_column(brazos):
    """⚠ **THE GUARD THAT PAYS FOR `managed = False`.**

    The table is created by raw DDL in migration 0021 and the model lives in
    `transfers.py`, so Django's own schema editor is not keeping the two in
    step. This does: every model field has a column and every column has a
    model field. A lane that adds one without the other meets it here.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        columns = {
            row.name for row in connection.introspection.get_table_description(cursor, "transfers")
        }
    declared = {field.column for field in transfers.Transfer._meta.fields}
    assert declared - columns == set(), f"model fields with no column: {declared - columns}"
    assert columns - declared == set(), f"columns with no model field: {columns - declared}"


def test_tc_trf_13a_the_migration_writes_the_nullif_form_not_the_bare_cast(brazos):
    """DEF-639, statically — this half runs on every vendor.

    The bare `current_setting('app.tenant_id')::uuid` ERRORS on an unset or
    empty GUC rather than denying, and it is evaluated during deferred FK
    validation at a migration's exit — which is why a fresh database could not
    be built at all (OQ-354). G41 ratchets the old form repo-wide; this asserts
    the new table was born in the new one.
    """
    text = MIGRATION.read_text(encoding="utf-8")
    assert "NULLIF(current_setting('app.tenant_id', true), '')::uuid" in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert re.search(r"current_setting\('app\.tenant_id'\)::uuid", text) is None
    # OQ-354: a migration that clears tenant context must leave the nil
    # sentinel, never `''`. This one clears none — asserted so a later edit
    # that adds a `set_config` has to come back and read this line.
    assert "set_config" not in text


@requires_postgres
def test_tc_trf_13_the_rls_policy_is_the_nullif_form(rls, brazos):  # noqa: F811
    """The live half — the policy as PostgreSQL actually stored it."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT qual, with_check, polname FROM pg_policies "
            "JOIN pg_policy ON polname = policyname WHERE tablename = 'transfers'"
        )
        rows = cursor.fetchall()
    assert rows, "no RLS policy on transfers"
    for qual, with_check, name in rows:
        assert "NULLIF" in (qual or ""), f"{name} uses the bare cast"
        assert "NULLIF" in (with_check or ""), f"{name} uses the bare cast on WITH CHECK"


@requires_postgres
def test_tc_trf_11b_the_transfers_table_is_rls_scoped(
    rls, brazos, lonestar, marcus, erin
):  # noqa: F811
    """⚠ **THE ONLY ASSERTION IN THIS FILE THAT PROVES RLS.**

    A plain ORM query under `tenant_ctx` runs as the app's role, a SUPERUSER in
    dev and CI, and superusers bypass row-level security unconditionally — FORCE
    or not (DEF-101). So this runs inside `SET ROLE sbh_rls_probe` (NOLOGIN
    NOSUPERUSER NOBYPASSRLS).

    `transfers` names a customer, both of their account numbers and the address
    they are moving to. A cross-tenant READ is a competitor's move list; a
    cross-tenant WRITE would point somebody else's transfer at a unit in this
    tenant's estate.
    """
    with tenant_ctx(brazos):
        _customer, account, _u = _mover(marcus, brazos)
        transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
    with tenant_ctx(lonestar):
        _c2, other, _u2 = _mover(erin, lonestar, service_code="water", label="Far away")
        transfers.start_transfer(erin, {"from_account_id": str(other.id)})

    for table in TRANSFER_TABLES:
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)
    assert_no_foreign_rows_anywhere(rls, brazos, TRANSFER_TABLES)
    assert_no_foreign_rows_anywhere(rls, lonestar, TRANSFER_TABLES)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-004@HEAD · US-CUS-005@HEAD
#         (04-docs/02-decisions/18-cr030-onboarding-design.md §5.7 · W7 tasks
#          7.1/7.2/7.3 · 04-docs/05-modules/03-customers/02-business-rules.md
#          BR-CUS-015/017/023/024/025/030/054/057/081/082/089/097)
# generated: 2026-08-25 by the CR-030 W7 transfers lane (S2)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — measured, not claimed.
# exceptions: (1) `TC-TRF-1` IS ASSERTED IN TWO HALVES AND THE SECOND IS STATIC.
#         Neither the Move-ins nor the Move-outs list exists (measured), so the
#         behavioural half asserts the published predicate and the static half
#         asserts that no list builder has appeared that bypasses it. Stated
#         rather than smoothed: a case that could only ever pass is worse than
#         no case (CLAUDE.md law 11, twice over).
#         (2) `TC-TRF-3`'s SIGNED HALF IS ASSERTED AND ITS UNSIGNED HALF IS NOT.
#         *"The deposit is not refunded and re-collected"* is proved as an
#         absence of events. *"Both carried"* — the position actually moving to
#         the new account — has no signed mechanics and no open question; the
#         gap is asserted instead, and the question is written out in
#         `transfers.py` §3 for whoever mints the OQ row.
#         (3) TWO FIXTURE COLUMNS ARE WRITTEN THROUGH THE ORM. `deposit_on_file`
#         and `balance` are in `services.REFUSED_FIELDS` on every client-facing
#         path (BR-CUS-023 / BR-CUS-015). A fixture that could set them through
#         a door would mean the product had one. Same device as
#         `test_w5_eligibility_and_deposit_carry.py::_returning_customer`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
