#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: E2E stack fixture — the ONE bill the browser journey reads.
#            Story:  US-BIL-005 (issue) · US-BIL-029 (stage 6 assemble) ·
#                    US-BIL-025/026 (the two reads S30 renders)
#            Screens: S30 (All bills) · S30 detail
# Rules:    BR-BIL-063 (the number is allocated at DRAFT creation) ·
#           BR-BIL-058 (nothing issues without a recorded release) ·
#           BR-BIL-010 (every line's GL account is stamped AT ISSUE) ·
#           BR-BIL-024 (the due date derives at issue) · BR-TEN-043 (event
#           time is a PARAMETER, never a clock read) · CLAUDE.md rule 1
#           (every write inside `tenant_context`) · rule 2 (decimal money)
# Golden:   GT-1 — B5 ❄️ FROZEN, finance-signed 2026-08-08. The inputs are
#           IMPORTED from tests/test_us_bil_029_assemble.py, never retyped:
#           one copy of a signed figure, in the module that already owns it.
# Tests:    07-frontend/e2e/W3-money-render.spec.ts asserts what a browser
#           RENDERS for the bill this script writes.
# Impacts:  08-qa/01-e2e/stack/boot_stack.sh (calls this) · nothing in
#           06-backend/apps/** (this file only CALLS those services)
# ───────────────────────────────────────────────────────
"""Seed the ONE issued bill the browser money journey reads — through the real engine.

WHY THIS FILE EXISTS. `manage.py seed_demo` provisions Brazos Bend and fills its
W1 world (services, plans, rate schedules, premises, units, meters) and stops
there, deliberately: *"meter reads, customers/accounts, bills, payments and
finance: their lanes have not landed — nothing here fakes them."* So a freshly
seeded stack has **no account and no bill**, and `GET /invoices` answers
`{"count": 0}`. A browser journey that asserts a rendered money figure needs one
bill in the database, and needs it to have arrived the way a real bill arrives.

WHAT "THROUGH THE REAL ENGINE" MEANS HERE, precisely — because the difference is
the whole value of the exercise:

  * the LINES and the TOTAL are computed by `apps.rating`'s priced pass, reached
    through billing's stage 1 → stage 2 → `rating_seam.price_period` → stage 6,
    which is the same chain `apps/billing/runs.py` drives. **No total is typed
    into this file.** If the engine mis-prices GT-1, this script writes the
    wrong number and the browser assertion goes RED with the mismatch quoted —
    which is the point.
  * the bill is ISSUED by `apps.billing.issue.issue_invoice`, so it passes the
    release gate (BR-BIL-058), allocates its number (BR-BIL-063), derives its
    due date (BR-BIL-024), stamps every line's GL account from the ledger
    (BR-BIL-010) and posts its balanced journal entry.

WHAT IS SEEDED BY HAND, and why each is not a money figure:
  * the ACCOUNT (`E2E-10001`) — customers' full activation path needs a plan
    assignment, deposit rules and an account-type→deposit map that no ratified
    figure exists for yet (seed_demo's own omissions list says so). The account
    row carries no money.
  * the CYCLE and the BILL RUN — a run needs a cycle window and a due-days
    term; both come from the tenant's own seeded billing cycle where one exists.
  * the RELEASE record — the four phase-4 confirmations a human ticks on S31
    step 4. Its `total_amount` is the run's own summary figure, not the bill's.

WHAT THIS FILE IS **NOT**, since 2026-08-15 (DEF-108 + DEF-110). It seeds ONE
account and ONE bill and nothing else, and that is the whole world a journey
found when it arrived: units 10 · units with a plan **0** ·
unit_plan_assignments **0** · accounts **1** · meter_reads **0**, and one journal
entry dated **30 June**, so a JULY trial balance answered `0 rows, 0.000000 =
0.000000` at every step of the month-close journey — which would have closed an
empty month, exported zero rows, and PASSED. The per-journey cohorts live in
`seed_journey_fixture.py` next to this file, driven from each journey's own
Fixture paragraph, and `boot_stack.sh` runs it after this one. **Add a journey's
world THERE, not here** — this file's one bill is read by name by
`W3-money-render.spec.ts` and must keep being the same bill.

IDEMPOTENT. A second run finds the account and the issued bill and writes
nothing — the stack can be re-booted without minting a second bill and moving
the number the journey reads.

Run (from 06-backend, with DJANGO_SETTINGS_MODULE and DATABASE_URL set):

    python3 ../08-qa/01-e2e/stack/seed_e2e_fixture.py

or through `08-qa/01-e2e/stack/boot_stack.sh`, which sets both.

NEVER PRODUCTION. It refuses under `config.settings.production` for the same
reason `seed_demo` does: it mints fixture rows against a fixture tenant.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import transaction  # noqa: E402

from core import tenancy as core_tenancy  # noqa: E402

# The fixture tenant `seed_demo` provisions (its BRAZOS_BEND payload).
TENANT_SUBDOMAIN = os.environ.get("E2E_TENANT", "brazosbend")

# The account this fixture bills. `E2E-` prefixed so it can never be confused
# with a number the real `BL-`/`A-` series allocated.
E2E_ACCOUNT_NO = "E2E-10001"

# BR-TEN-043: every business moment below is a PARAMETER, never a clock read —
# so a re-boot on a different day writes the identical bill.
ISSUED_AT = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)
# BR-BIL-026's pin. `invoices.template_id` is a uuid column and the template
# TABLES do not exist yet (B2 r10 #4), so issue takes the pin as a parameter —
# see `issue.issue_invoice`'s docstring. A FIXED uuid, so a re-boot pins the
# same version rather than a fresh one, and one that is obviously a fixture.
TEMPLATE_ID = "e2e00000-0000-4000-8000-000000000001"
TEMPLATE_VERSION = 1
RUN_KEY = "e2e|gt1|2026-06"


def _fail(message: str) -> None:
    sys.stderr.write(f"seed_e2e_fixture: {message}\n")
    raise SystemExit(2)


def _refuse_in_production() -> None:
    """Same posture as `seed_demo`'s guard: a fixture seeder never runs in prod.

    Two independent tests, because either alone has a hole: the settings MODULE
    can be renamed, and `DEBUG` can be true on a settings module named
    `production`. Failing closed on both is the cheap answer (hard-won law 3 —
    the unsafe option must be the one you type, and there is no way to type one
    here at all).
    """
    module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
    if module.endswith("production") or not settings.DEBUG:
        _fail(
            "refusing to run: this mints fixture rows (an account, a bill run, a "
            f"release record and an ISSUED bill) against a fixture tenant, and "
            f"DJANGO_SETTINGS_MODULE={module!r} with DEBUG={settings.DEBUG} is not a "
            "development stack. Same rule as `manage.py seed_demo`."
        )


def _tenant():
    from apps.tenancy import models as tenancy_models

    tenant = tenancy_models.Tenant.objects.filter(subdomain=TENANT_SUBDOMAIN).first()
    if tenant is None:
        _fail(
            f"no tenant `{TENANT_SUBDOMAIN}` — run `manage.py seed_demo` first "
            "(boot_stack.sh does it in order)"
        )
    return tenant


def _owner(tenant):
    """The seeded owner (Dana). Used as the release-gate confirmer and audit actor."""
    from apps.identity import models as identity_models

    user = identity_models.User.objects.filter(tenant=tenant).order_by("created_at").first()
    if user is None:
        _fail("the tenant has no user — seed_demo provisions the owner; re-run it")
    return user


def _account(tenant):
    """An account on a seeded unit. Created once; found on every later run."""
    from apps.customers import models as customer_models
    from apps.metering import models as metering_models

    existing = customer_models.Account.objects.filter(
        tenant=tenant, account_no=E2E_ACCOUNT_NO
    ).first()
    if existing is not None:
        return existing, False

    unit = metering_models.Unit.objects.order_by("unit_no").first()
    if unit is None:
        _fail("the tenant has no units — seed_demo seeds six premises and ten units")
    status = customer_models.AccountStatus.objects.filter(tenant=tenant, code="active").first()
    account_type = customer_models.AccountType.objects.filter(code="residential").first()
    if status is None or account_type is None:
        _fail("account statuses / types missing — seed_demo seeds both")
    account = customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit.id,
        status=status,
        account_type=account_type,
        account_no=E2E_ACCOUNT_NO,
    )
    return account, True


def _cycle(tenant):
    """The tenant's own June cycle if it seeded one; otherwise the fixture window.

    `due_days` is what BR-BIL-024 derives the due date from at issue — a run
    against a cycle with no terms refuses, which is the correct refusal and not
    something to work around here.
    """
    from datetime import date

    from apps.metering import models as metering_models

    cycle = metering_models.Cycle.objects.filter(tenant=tenant, due_days__isnull=False).first()
    if cycle is not None:
        return cycle
    cycle, _ = metering_models.Cycle.objects.get_or_create(
        tenant=tenant,
        code="E2E-06",
        defaults={
            "window_start": date(2026, 6, 1),
            "window_end": date(2026, 6, 30),
            "bill_date": date(2026, 7, 1),
            "due_days": 21,
        },
    )
    return cycle


def _tax_rules(tenant, user):
    """The tenant's OWN seeded taxes, each pointed at its authority's account.

    THE FIGURES ARE NOT INVENTED AND THIS IS THE NICEST FACT IN THE FIXTURE.
    `seed_demo` seeds Brazos Bend with exactly two taxes from [F]
    `lookup_defaults.json`: **Texas State 6.25 %** and **Local 2.00 %**. GT-1's
    frozen input is *"tax 8.25 % on (usage+base)"*, and under B4.4's per-line
    half-up rounding the tenant's own pair reproduces GT-1's signed tax to the
    cent on GT-1's own $100.58 base:

        100.58 × 0.0625 = 6.28625 → 6.29
        100.58 × 0.0200 = 2.01160 → 2.01
                                    ─────
                                     8.30   ← GT-1's frozen tax, B5 line 12

    So the browser reads a bill taxed by the fixture utility's real, ratified
    tax configuration, and the number finance signed is the number that lands.
    (`tests/test_br_bil_069_tax_authority_gl.py` documents the one-cent case
    where a three-way split does NOT agree with the single-rate narration —
    OQ-148. This two-way split does; nothing here rounds anything itself.)

    WHAT THIS FUNCTION HAS TO WRITE, and why it is a human's action replayed:
    BR-BIL-069 (PO ruling 2026-08-11, OQ-116) makes every tax line resolve its
    liability account through `taxes.liability_gl_account_id`, and `seed_demo`
    leaves that column NULL — its own summary says GL mappings *"stay NULL
    rather than pointing at a made-up id"*. `apps/ledger/chart.py` carries no
    2200 row by design, because seeding one would invent a tax authority no
    tenant created (BR-TEN-037). So a real tenant's accountant mints one
    account per authority on S13 and points each tax at it, and that is exactly
    the three steps below — the same three
    `tests/test_br_bil_069_tax_authority_gl.a_tax_authority` takes. The
    2200-suffix scheme is TYPED, as a human types it, because nothing generates
    one. OQ-147 was CLOSED 2026-08-12 — `apps.ledger.services` now generates the
    2200-nn code — so these hand-typed codes are legacy and can be dropped.
    """
    from apps.ledger import models as ledger_models
    from apps.ledger import services as ledger_services
    from apps.rating import models as rating_models

    from apps.billing import rating_seam

    taxes = list(rating_models.Tax.objects.filter(tenant=tenant).order_by("-rate"))
    if not taxes:
        _fail("the tenant has no taxes — seed_demo seeds Texas State + Local; re-run it")

    rules = []
    for index, tax in enumerate(taxes, start=1):
        if tax.liability_gl_account_id is None:
            code = f"2200-{index:02d}"
            account = ledger_models.LedgerAccount.objects.filter(tenant=tenant, code=code).first()
            if account is None:
                account = ledger_services.create_tax_authority_account(
                    code=code,
                    name=f"Tax payable — {tax.jurisdiction.name}",
                    actor=user,
                )
            tax.liability_gl_account_id = account.id
            tax.save(update_fields=["liability_gl_account_id"])
            print(f"  tax authority ........ {tax.jurisdiction.name} → {code}")
        rules.append(
            rating_seam.TaxRule(
                code=tax.jurisdiction.name, rate=tax.rate, tax_id=str(tax.id)
            )
        )
    return tuple(rules)


def _run(tenant, cycle):
    from apps.billing import models as billing_models

    from tests.test_us_bil_029_assemble import PERIOD_END, PERIOD_START

    run = billing_models.BillRun.objects.filter(tenant=tenant, idempotency_key=RUN_KEY).first()
    if run is not None:
        return run
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        idempotency_key=RUN_KEY,
    )


def _release(tenant, run, user):
    """S31 step 4's four confirmations, recorded. BR-BIL-058: no release, no issue."""
    from apps.billing import models as billing_models

    existing = billing_models.BillRunRelease.objects.filter(tenant=tenant, bill_run=run).first()
    if existing is not None:
        return existing
    return billing_models.BillRunRelease.objects.create(
        tenant=tenant,
        bill_run=run,
        summary={"source": "08-qa/01-e2e/stack/seed_e2e_fixture.py"},
        account_count=1,
        bill_count=1,
        # The run's own summary figure, not the bill's — the bill's total is
        # whatever the engine prices, and this file never states it.
        total_amount=Decimal("0.000000"),
        currency="USD",
        compliance_confirmed=True,
        email_mandate_confirmed=True,
        sms_mandate_confirmed=True,
        autopay_mandate_confirmed=True,
        confirmed_by=user,
        confirmed_at=ISSUED_AT,
    )


#: Every month the fixture writes a read into — FIXED dates (BR-TEN-043: a
#: re-boot on a different day writes the identical reads), September 2024 to
#: November 2026.
READ_MONTHS: tuple[tuple[int, int], ...] = tuple(
    [(2024, month) for month in range(9, 13)]
    + [(2025, month) for month in range(1, 13)]
    + [(2026, month) for month in range(1, 12)]
)


def _ensure_read_partitions() -> list[str]:
    """Make sure `meter_reads` has a guarded partition for every month in
    `READ_MONTHS` before the first read is written (`DEF-INF-9033`).

    ⚠ **THE PARTITIONS FOLLOW THE SEED, NOT THE OTHER WAY ROUND.** The bootstrap
    window slides with the calendar and these dates do not, so a fixed window
    that fits today stops fitting some month later. Created through
    `core.partitioning`, the one place that creates a partition WITH its tenant
    policy — never by hand.
    """
    from core import partitioning

    first = date(*READ_MONTHS[0], 1)
    last = date(*READ_MONTHS[-1], 1)
    return partitioning.ensure_partitions_cover("meter_reads", first, last)


def _water_reads(tenant, account):
    """One committed WATER read per month, so a real bill run has usage to bill.

    ⚠ **WHY WATER AND NOT ELECTRIC, AND WHY ANY READS AT ALL** (DEF-116, the
    browser proof). Until this existed the seeded stack held **zero meter
    reads**, so a bill run driven through S31 broke every account at
    measure-consumption and no bill could be produced by clicking — the engine
    was fine and the world was empty (DEF-108's shape).

    ⚠ **THE PARAGRAPH THAT USED TO SIT HERE IS NOW FALSE, AND IT IS QUOTED
    RATHER THAN DELETED** (hard-won law 1 — a comment claiming a state of the
    product is a claim). It read: *"ELECTRIC IS LEFT WITHOUT READS ON PURPOSE …
    the demo plan Residential Standard prices electric on a time_of_use tariff
    and the rating engine registers flat and tiered only, so an electric line is
    refused — correctly … The missing TOU and demand tariff models are a real
    gap and are the rating lane's."* That gap was closed on **2026-08-16**:
    `apps/rating/pricing/models/tou.py` is registered and prices GT-17's own
    120/200/380 kWh split at $0.22/$0.14/$0.09 to **$88.60**.

    So **electric now gets reads too**, and they are TOU reads — one register per
    window (`channel` = tou_on | tou_mid | tou_off, B2 r8 / BR-MET-059), which is
    what BR-RAT-021's *"reads arrive pre-split per window"* means in the
    database. A `total` register is written beside them, because a TOU meter has
    one and because the seam's main consumption is deliberately taken from a
    register that measures the period's total (DEF-150).

    The fixture is therefore honest in the opposite direction from before: the
    demo tenant's own plan is a time-of-use plan, and a bill run over it now
    produces a priced electric bill rather than a missing-read exception. Water
    still bills on its tiered tariff, so the ONE bill carries both shapes.

    IDEMPOTENT: a read that is already there is left alone. `meter_reads` is
    append-only at the DATABASE (a committed row cannot be deleted, only
    superseded — BR-MET-053/054), so a second boot must not try.

    Every value is a PARAMETER, never a clock read (BR-TEN-043): the same boot
    on a different day writes the identical reads.
    """
    from apps.assets import models as asset_models
    from apps.metering import models as metering_models
    from apps.metering import services as metering_services  # DEF-288: the collection-route stamp

    from apps.customers import models as customer_models

    # EVERY unit that carries an account, not just the fixture's own: a bill run
    # is over a CYCLE, and one account with usage in a cycle of five is a run
    # that mostly breaks. `account` is accepted so each read carries the
    # customer it belongs to where one exists.
    accounts_by_unit = {
        str(row.unit_id): row for row in customer_models.Account.objects.all()
    }
    assignments = list(asset_models.AssetAssignment.objects.filter(to_date__isnull=True))
    waters: list[tuple[object, object]] = []
    for assignment in assignments:
        if str(assignment.unit_id) not in accounts_by_unit:
            continue
        asset = asset_models.Asset.objects.filter(pk=assignment.asset_id).first()
        if asset is not None and (asset.unit or "").lower() in ("kgal", "gal", "ccf"):
            waters.append((asset, accounts_by_unit[str(assignment.unit_id)]))
    electrics: list[tuple[object, object]] = []
    for assignment in assignments:
        if str(assignment.unit_id) not in accounts_by_unit:
            continue
        asset = asset_models.Asset.objects.filter(pk=assignment.asset_id).first()
        if asset is not None and (asset.unit or "").lower() in ("kwh",):
            electrics.append((asset, accounts_by_unit[str(assignment.unit_id)]))

    if not waters and not electrics:
        print("reads .................. SKIPPED — no water or electric meter on any account")
        return 0

    # ⚠ **DEF-INF-9033.** This comment called the window *"the partitioned
    # months this schema actually carries"* — true of a database migrated in
    # August or September 2026 and false from October 1, because
    # `metering/0003` partitions relative to the day it RUNS (24 months back).
    # The seed now asks for the months it writes instead of assuming them.
    months = list(READ_MONTHS)
    _ensure_read_partitions()
    written = 0
    for water, holder in waters:
        value = Decimal("1000")
        for year, month in months:
            read_date = date(year, month, 1)
            read_at = datetime(year, month, 1, tzinfo=timezone.utc)
            prior, value = value, value + Decimal("12")
            if metering_models.MeterRead.objects.filter(
                tenant=tenant, asset_id=water.id, read_at=read_at, channel="total"
            ).exists():
                continue
            metering_models.MeterRead.objects.create(
                tenant=tenant,
                asset_id=water.id,
                account=holder,
            # DEF-288 — STAMP THE COLLECTION ROUTE, exactly as the product
            # does at `commit_read_batch`. This seeder writes `meter_reads`
            # DIRECTLY, so it bypasses the one place BR-MET-079's stamp is
            # applied; without this line the read exists with no record of
            # where it was collected, and the delete guard cannot see it.
            # MEASURED on the live e2e stack before the fix: 1,674 reads,
            # 189 stamped — every one of those 189 arrived through an import
            # batch, and the other 1,485 came from here.
            route_id=metering_services.collection_route_id(water),

                read_at=read_at,
                channel="total",
                period_start=read_date - timedelta(days=30),
                period_end=read_date,
                prior_value=prior,
                current_value=value,
                multiplier=Decimal("1"),
                consumption=value - prior,
                # CLAUDE.md rule 3 — the unit is the ASSET's own, never inferred.
                unit=water.unit,
                source="manual",
                status="ok",
                lifecycle="committed",
                days_since_prior=30,
            )
            written += 1
    print(
        f"water reads ............ {written} written across {len(waters)} water meter(s) "
        f"({len(waters) * len(months) - written} already there)"
    )
    written += _tou_electric_reads(tenant, electrics, months, metering_models)
    return written


#: The reference bill's own window split — B5 GT-17 (= WE-1): *"TOU 120/200/380
#: kWh"* at the Residential Standard summer prices $0.22 / $0.14 / $0.09, which
#: `10-scripts/03-golden-verify.py` recomputes to **$88.60**.
#:
#: ⚠ AMENDED 2026-08-16. This note used to say the channel *"follows BR-RAT-064's
#: price rank: dearest window = `tou_on`"*. **BR-RAT-064 is SUPERSEDED** — the
#: PO ruled *"make the rate wizard say which register is which"* (OQ-236 CLOSED
#: → BR-RAT-067), so the pairing below is now the one the SEEDED TARIFF STATES
#: (`seed_demo._TOU_WINDOWS`: On-peak → `tou_on`, Mid-peak → `tou_mid`, Off-peak
#: → `tou_off`) and rating no longer derives anything from the prices. The three
#: quantities are unchanged and so is the 88.60 they produce; what changed is
#: that these register names are read from the tariff rather than inferred, so a
#: fixture that disagreed with the tariff would now REFUSE by name instead of
#: quietly re-ranking itself into agreement.
TOU_SPLIT: tuple[tuple[str, str], ...] = (
    ("tou_on", "120"),
    ("tou_mid", "200"),
    ("tou_off", "380"),
)


def _tou_electric_reads(tenant, electrics, months, metering_models) -> int:
    """One register per TOU window per month, plus the meter's own total.

    ⚠ THE `metering_services` IMPORT BELOW IS LOAD-BEARING AND WAS MISSING UNTIL
    2026-08-24 (DEF-641). DEF-288's collection-route stamp was applied in TWO
    places in this file; `_water_reads` imports the module at its own top and
    this function did not, so line 530 named a global that has never existed.
    It is a `NameError` the moment a TOU electric read is seeded — which is
    every run of this seeder — and it went unseen for weeks because CI lints
    with `working-directory: 06-backend`, so NO linter has ever read `08-qa/`.
    Pointed at this file, `ruff` names it instantly as F821.

    WHY FOUR ROWS AND NOT ONE. A time-of-use meter holds a register per window
    and BR-RAT-021 says the reads arrive PRE-SPLIT; `meter_reads` is keyed on
    (asset, read_at, channel) exactly so it can carry them (B2 r8 /
    BR-MET-059). The `total` row is written as well because a real TOU meter has
    one and because `billing_reads_for_unit` takes the service's main
    consumption from a register that measures the period's total — the two
    questions are different and DEF-150 is what happens when one row answers
    both.

    The quantities are B5 GT-17's, so the electric line on the seeded stack is
    the reference bill's own **$88.60** and a person can check it against a
    frozen document rather than against this file.
    """
    from apps.metering import services as metering_services  # DEF-288/DEF-641

    if not electrics:
        print("electric TOU reads ..... SKIPPED — no electric meter on any account's unit")
        return 0
    total_qty = sum(Decimal(qty) for _, qty in TOU_SPLIT)
    written = 0
    for meter, holder in electrics:
        base = {channel: Decimal("1000") for channel, _ in TOU_SPLIT}
        base["total"] = Decimal("1000")
        for year, month in months:
            read_date = date(year, month, 1)
            read_at = datetime(year, month, 1, tzinfo=timezone.utc)
            for channel, qty in (*TOU_SPLIT, ("total", str(total_qty))):
                step = Decimal(qty)
                prior, base[channel] = base[channel], base[channel] + step
                if metering_models.MeterRead.objects.filter(
                    tenant=tenant, asset_id=meter.id, read_at=read_at, channel=channel
                ).exists():
                    continue
                metering_models.MeterRead.objects.create(
                    tenant=tenant,
                    asset_id=meter.id,
                    account=holder,
                    # DEF-288 — STAMP THE COLLECTION ROUTE, exactly as the product
                    # does at `commit_read_batch`. This seeder writes `meter_reads`
                    # DIRECTLY, so it bypasses the one place BR-MET-079's stamp is
                    # applied; without this line the read exists with no record of
                    # where it was collected, and the delete guard cannot see it.
                    # MEASURED on the live e2e stack before the fix: 1,674 reads,
                    # 189 stamped — every one of those 189 arrived through an import
                    # batch, and the other 1,485 came from here.
                    route_id=metering_services.collection_route_id(meter),

                    read_at=read_at,
                    channel=channel,
                    period_start=read_date - timedelta(days=30),
                    period_end=read_date,
                    prior_value=prior,
                    current_value=base[channel],
                    multiplier=Decimal("1"),
                    consumption=step,
                    # CLAUDE.md rule 3 — the unit is the ASSET's own, per row.
                    unit=meter.unit,
                    source="manual",
                    status="ok",
                    lifecycle="committed",
                    days_since_prior=30,
                )
                written += 1
    print(
        f"electric TOU reads ..... {written} written across {len(electrics)} electric meter(s) "
        f"(4 registers each: tou_on 120 / tou_mid 200 / tou_off 380 / total {total_qty} kWh — "
        "B5 GT-17's own split)"
    )
    return written


def main() -> int:
    _refuse_in_production()

    # Imported HERE, after django.setup(): these carry GT-1's frozen inputs and
    # the real stage-1→2→rating→stage-6 chain. Importing them rather than
    # copying them is deliberate — a second copy of a signed figure drifts.
    from apps.billing import issue as billing_issue
    from apps.billing import models as billing_models

    from tests.test_us_bil_029_assemble import GT1_TOTAL, assemble, billing_data

    tenant = _tenant()
    print(f"tenant ................. {TENANT_SUBDOMAIN} ({tenant.id})")

    with core_tenancy.tenant_context(tenant.id):
        user = _owner(tenant)
        account, created = _account(tenant)
        print(f"account ................ {account.account_no} ({'created' if created else 'found'})")
        # The usage a real bill run measures. Written on every boot,
        # BEFORE the early return below, because a stack that already has
        # its issued bill still needs reads for the NEXT run a clerk drives.
        _water_reads(tenant, account)

        existing = (
            billing_models.Invoice.objects.filter(
                tenant=tenant, account=account, status=billing_models.INVOICE_ISSUED
            )
            .order_by("created_at")
            .first()
        )
        if existing is not None:
            print(f"bill ................... {existing.invoice_no} (found — nothing written)")
            print(f"  total ................ {existing.total}")
            print(f"  status ............... {existing.status}")
            _report(existing)
            return 0

        cycle = _cycle(tenant)
        run = _run(tenant, cycle)
        _release(tenant, run, user)
        taxes = _tax_rules(tenant, user)

        # ── THE ENGINE RUNS HERE ────────────────────────────────────────────
        # stage 1 (resolve subscription) → stage 2 (measure consumption) →
        # rating's priced pass → stage 6 (assemble the draft). Every figure on
        # the draft is computed; none is supplied.
        #
        # `atomic` is REQUIRED, not tidiness: BR-BIL-063's number allocation
        # takes `SELECT … FOR UPDATE` on the tenant's series row, which Django
        # refuses outside a transaction. A management command gets one from
        # ATOMIC_REQUESTS/`@transaction.atomic`; a bare script has none.
        with transaction.atomic():
            draft = assemble(tenant, account, run, billing_data(account, taxes=taxes))
            print(f"draft .................. {draft.invoice_no} (stage 6, engine-priced)")

            bill = billing_issue.issue_invoice(
                draft,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
                actor=user,
            )
        stored = billing_models.Invoice.objects.get(pk=bill.pk)
        print(f"bill ................... {stored.invoice_no} (issued)")
        print(f"  subtotal ............. {stored.subtotal}")
        print(f"  tax .................. {stored.tax_total}")
        print(f"  total ................ {stored.total}")

        # A LOUD self-check, not an assertion of the contract: the browser spec
        # is what asserts the frozen figure, and it reads B5 rather than this
        # file. This line exists so a stack that seeded the WRONG bill says so
        # at boot instead of at the end of a Playwright run.
        if stored.total != GT1_TOTAL:
            _fail(
                f"the engine priced {stored.total}, GT-1 is {GT1_TOTAL} — the stack "
                "would boot a bill the money journey must fail on. Refusing to "
                "report success; investigate the rating engine, not this script."
            )
        _report(stored)
    return 0


def _report(bill) -> None:
    print("")
    print("── what the browser journey will read ──")
    print(f"  bill number .......... {bill.invoice_no}")
    print(f"  rendered total ....... {bill.total} {bill.currency}")
    print(f"  detail URL ........... /{TENANT_SUBDOMAIN}/billing/bills/{bill.id}")
    print(f"  list URL ............. /{TENANT_SUBDOMAIN}/billing")
    print("")


if __name__ == "__main__":
    raise SystemExit(main())

# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-057 / PO ruling 2026-08-11 ("we ahve to prove against human clicking")
# generated: 2026-08-11 by the E2E bring-up lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
# gates: run against a live Postgres + migrated + seed_demo'd database; output quoted in the lane report
# exceptions: the ACCOUNT is created with the customers MODEL rather than the
#   activation service — customers' activation path needs plan deposit rules
#   that no ratified figure exists for (seed_demo's own omissions list). The
#   account row carries no money, so nothing signed is invented here. REPORTED,
#   not worked around: when EP-CUS-07's onboarding lands, this should call it.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
