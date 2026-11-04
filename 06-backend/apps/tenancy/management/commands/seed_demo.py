# ── Trace ──────────────────────────────────────────────
# Story:    DevOps-prep lane (R1 demo bootability) — 09-infra/01-deployment-
#           architecture.md §5 step 4 (post-migrate seed) + §13 item 6.
#           Replaces the 10-scripts/03-seed_demo.py stub as the standard
#           demo/staging post-migrate step. NEVER prod (§5 step 4, §11 step 3).
#           W1 extension: US-RAT-002/005/006/007/008/009 (Plans & Rates) ·
#           US-MET-001/002/003/006 (Premises, Units, Routes & Cycles) ·
#           US-AST-002 (Assets) — all through those modules' own services.
# Rules:    BR-TEN-001 (atomic — an owner-less tenant must not exist) ·
#           BR-TEN-010 (subdomain replay = idempotent) · BR-TEN-012/013
#           (reference seed only via owning-module services/seams) ·
#           BR-RAT-024/025/030/031/035/036 (services ⊆ enabled · plan-as-bundle ·
#           publish · one-service-one-model schedules · charge identity · tax
#           forms) · BR-MET-002/003/009/010/033/034 (unit labels · services ⊆
#           enabled · cycle windows · route→cycle · membership · premises types) ·
#           BR-AST-009/010/011/033/043/044 (measuring assets declare service +
#           explicit UoM · net metering · assign-on-create · duplicate asset # ·
#           read methods · meter types) ·
#           CLAUDE.md rule 7 via BE-03 (config/money writes audit — no
#           registered sink means no seeding, refused loudly)
# Tests:    06-backend/tests/test_seed_demo.py (fixture-figure provenance on
#           sqlite; the live double-run + idempotency case is Postgres-gated) ·
#           the service paths it calls are covered by tests/test_us_ten_*.py,
#           test_us_rat_*.py, test_us_met_*.py, test_us_ast_*.py ·
#           `--check` is the sqlite-safe smoke (no DB writes, exit 0)
# Impacts:  demo/staging environments only. Writes go through THE REAL
#           SERVICES exclusively (apps.tenancy / apps.rating / apps.metering /
#           apps.assets services + documented seams) — with no exception since
#           2026-08-10: the platform SubscriptionPlan catalog is seeded by
#           apps/tenancy/migrations/0005_seed_subscription_plans.py and this
#           command only CHECKS for it (see _ensure_plans).
# ───────────────────────────────────────────────────────
"""seed_demo — provision the Brazos Bend demo fixture tenant and fill its W1
screens through the real service layers.

Scope: W0 (tenant + subscription + settings + owner user + UoM lookups +
number series + enabled services) **plus W1** — charge codes, taxes, rate
schedules and published plans (Plans & Rates, S9–S13), premises, units, routes
and billing cycles (S14–S16, S26–S27), and meters/assets on those units (S49).
Reads, customers, bills and payments still grow with their own lanes
(09-infra §13 item 6) — nothing here fakes them.

Honesty contract (prime directive): this command NEVER bypasses a service or
invents data.

* Every write goes through the owning module's service function under
  `app.tenant_id` context. No raw INSERT, no ORM shortcut, no RLS bypass.
* **No money value in this file was invented.** Each one is quoted from one of
  two ratified sources, cited inline at its constant:
    [F] `apps/tenancy/fixtures/lookup_defaults.json` — the W0 platform fixture
        (version 2026.08, US-TEN-002 §4 signed test data): charge codes and
        tax jurisdictions.
    [W] `04-docs/05-modules/07-billing/08-worked-examples.md` — the PO-verified
        billing workbook: §1 (the Brazos Bend fixture utility's plans, rates,
        bases and taxes) and the WE-n worked examples.
  Where a figure exists in NEITHER, the object is OMITTED and named in the
  closing summary — never filled with a plausible-looking guess.
* Non-money structure (TOU window times, seasons, addresses, dates) comes from
  the signed story §4 test data cited at each constant.
* Idempotent throughout (BR-TEN-010 posture): every object is looked up by its
  natural key through the owning module's SELECTOR before its create service is
  called, so a replay writes nothing and changes no count.

Postgres-only for actual seeding: tenant context is a Postgres GUC
(`set_config('app.tenant_id', …)`, core/tenancy.py) — sqlite cannot run it,
so on sqlite the command refuses before touching tenant tables. `--check`
performs no writes and is safe everywhere (including sqlite test settings).
"""

import os
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from django.conf import settings as django_settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection

from apps.rating.constants import PRICE_HISTORY_EPOCH
from apps.tenancy import models, seams, selectors, services
from core import audit as core_audit
from core import tenancy as core_tenancy
from core.pagination import ListParams
from core.permissions import SYSTEM_ADMIN

# US-TEN-001 §4 signed test data (tests/test_us_ten_helpers.brazosbend_payload).
# The owner password may be overridden via SEED_DEMO_OWNER_PASSWORD (.env.example);
# hashing/policy is identity's job (seam contract) — this is pass-through only.
BRAZOS_BEND = {
    "name": "Brazos Bend Utilities",
    "subdomain": "brazosbend",
    "state": "Texas",
    "services": ["electric", "water"],
    "currency": "USD",
    "plan": "growth",
    "load_defaults": True,
    "owner": {
        "full_name": "Dana Whitfield",
        "email": "dana@brazosbendutilities.com",
        "password": "S3cure!passw0rd",  # demo fixture credential — never prod
        "phone": "+1 (281) 555-0164",
    },
}

# US-TEN-005 §4 signed test data (tests/test_us_ten_005_006_settings.COMPANY_FULL).
COMPANY_PROFILE = {
    "legal_name": "Brazos Bend Utility District No. 1",
    "dba_name": "Brazos Bend Utilities",
    "ein": "74-3182640",
    "state_utility_id": "TX CCN 13148 / PUCT 10238",
    "mailing_address": "9410 FM 1093 Rd, Katy, TX 77494",
    "support_phone": "+1 (281) 555-0164",
    "support_email": "help@brazosbendutilities.com",
    "website": "brazosbendutilities.com",
    "brand_primary_hex": "#1B5E9E",
    "brand_accent_hex": "#201E1D",
    "remit_to_address": "PO Box 2210, Katy, TX 77492",
    "remit_payable_to": "Brazos Bend Utilities",
    "service_hours": "Mon-Fri 8-5 CT",
}

# US-TEN-006 §4 signed test data (tests/test_us_ten_005_006_settings.REGIONAL_TX).
REGIONAL_SETTINGS = {
    "country": "United States",
    "state": "Texas",
    "timezone": "America/Chicago",
    "language": "en-US",
    "first_day_of_week": "sunday",
    "currency": "USD",
    "number_format": "1,234.56",
    "date_format": "MM/DD/YYYY",
    "time_format": "12-hour",
    "fy_start_month": 10,
    "fy_start_day": 1,
    "accounting_method": "accrual",
    "close_cadence": "monthly",
    "close_day": "3rd business day",
    "lock_closed_periods": True,
}

# The demo tenant's signed plan (US-TEN-001 §4 test data · S112 pre-selected).
# Kept here as the value this command REQUIRES to be in the catalog; the catalog
# itself — all three ratified SKUs — is seeded by tenancy migration 0005, which
# cites A10/A13/A1/B2 per row. (The earlier note here that starter/scale had no
# signed values is withdrawn: the A13 addendum of 2026-08-07 prices all three.)
GROWTH_PLAN = {
    "code": "growth",
    "name": "Growth",
    "price_month": "5000",
    "currency": "USD",
    "min_accounts": 300,
    "max_accounts": 1000,
}

# ══════════════════════════════════════════════════════════════════════════
# W1 fixture — every money value below carries its ratified source, [F] or [W]
# (see the module docstring). Nothing here is invented; omissions are listed
# in OMITTED_FOR_LACK_OF_A_RATIFIED_FIGURE and printed by the closing summary.
# ══════════════════════════════════════════════════════════════════════════

# ── Charge codes (S12) ──────────────────────────────────────────────────────
# [F] lookup_defaults.json `charge_codes`, verbatim. Two representation notes,
# neither of them a new number:
#   · `charges.percent` stores a FRACTION (models.Charge comment; US-RAT-008
#     TC-3 asserts 1.5 % → "0.015"), so the fixture's "1.5" is written 0.015.
#   · TAMPER is $250.00 by PO RULING of 2026-08-10, and the ruling made it a
#     PLATFORM default rather than one fixture utility's number — so [F] now
#     carries it and this file quotes [F] like every other code. Two ratified
#     sources had disagreed (EP-RAT-03 §4 "New: TAMPER $250.00" vs the billing
#     workbook's §1 / WE-11 "$500.00"); the PO chose $250.00. The workbook's
#     $500.00 is not a second default — it is the WE-11 worked example and stays
#     there. The earlier note here that "[F] carries the code with no amount, so
#     the [W] figure fills it" is WITHDRAWN.
# DEPO-R ("Deposit refund") is DELIBERATELY ABSENT — a RULING, not a gap:
# BR-RAT-020/023 (CONFIRMED) move deposits to `plan_deposit_rules` per consumer
# category and explicitly supersede the prototype's single DEPO-R checkbox, so a
# platform-wide DEPO-R amount would encode a model the PO already replaced
# (apps.rating.services.CHARGE_CODES_NOT_SEEDED holds that reason in prose).
# `charge_type` per code is CONFIRMED and now also lives in [F], so a tenant
# provisioned through signup gets the same classification this demo does.
# `taxable_default` stays False for every row — B4.2 / WE-1 / WE-6 / WE-11:
# fees are never in the tax base. `waivable` on LATE is WE-15(f)'s manual
# first-time waiver, a behaviour flag, not a money value.
from core.sample_fixture import (  # [W] §1 — one figure, one home
    COMMERCIAL_WATER_BASE,
    ELECTRIC_BASE,
    INDUSTRIAL_ELECTRIC_BASE,
    WATER_BASE,
)

CHARGE_CODES: tuple[dict[str, Any], ...] = (
    {
        "code": "LATE",
        "name": "Late payment fee",
        "charge_type": "penalty",
        "amount_rule": "percent_with_minimum",
        "percent": "0.015",  # [F] 1.5 %, stored as a fraction
        "min_amount": "5",  # [F]
        "waivable": True,  # [W] WE-15(f)
    },
    {
        # BR-RAT-088 / §A3 — THE BASE CHARGE CODE, and the first one this seed
        # has ever carried. Until CR-013 P1b the base lived only on
        # `tariff_versions.base_charge`, so the demo tenant had no base charge
        # code for ANY service and the cutover had nothing to cut over TO.
        #
        # ⚠ THE SEED MAY AUTHOR THIS; A MIGRATION MAY NOT. A data migration
        # inherits a tenant's own charge codes and would have to GUESS which one
        # is the base — by name (`BASE-<service>`), which is the hard-coded
        # vocabulary B12 §No hard-coded values forbids and which fails silently
        # for a tenant that names theirs anything else. The seed is different:
        # it does not guess, it DECLARES, because it is the author of this data.
        #
        # The figure is not new — [W] §1 "Base/mo … Water $8", the same
        # `fixture.WATER_BASE` the water schedule has always priced with. One
        # fact, now in the object §A3 ruled owns it.
        "code": "BASE-W",
        "name": "Water base service — residential",
        "charge_type": "recurring",
        "service": "water",
        "amount_rule": "flat",
        "amount": WATER_BASE,  # [W] §1 — the schedule's own figure, unmoved
        "is_base": True,
        # ⚠ **SCOPED BY CLASS SINCE `DEF-2823` (2026-08-31), AND THE SCOPE IS
        # WHAT MAKES THE FIXTURE EXPRESSIBLE.** `RATE_PLANS` states TWO water
        # bases — Residential Standard `$8` and Small Commercial `$15` — and
        # with `BR-RAT-088` making the CHARGE CODE the source, one unscoped
        # `BASE-W` at `$8` would be the base of both, and the `$15` on the
        # plan would be a figure nothing reads. `BR-RAT-108` separates one
        # service's two amounts by CLASS and never by name, which is the
        # mechanism `apps/rating/sample_data.BASE_CHARGE_CODES` already uses
        # for this very pair on this very tenant.
        "applies_to_customer_classes": ["residential"],
    },
    {
        # The commercial half of the same service. Its figure is NOT new: it is
        # `[W] §1`'s *"Small Commercial water base $15"*, the figure
        # `RATE_PLANS` has always carried on `COM-SM`'s `plan_services
        # .base_charge` — MOVED to the object BR-RAT-088 rules owns it, not
        # invented and not duplicated.
        "code": "BASE-W-COM",
        "name": "Water base service — commercial",
        "charge_type": "recurring",
        "service": "water",
        "amount_rule": "flat",
        "amount": COMMERCIAL_WATER_BASE,
        "is_base": True,
        "applies_to_customer_classes": ["commercial"],
    },
    {
        # ⚠ **THE ELECTRIC HALF, AND WITHOUT IT NOTHING SEEDS AT ALL
        # (`DEF-528`, critical).** `BR-RAT-088`'s guard is SELF-ACTIVATING per
        # tenant: it returns early while no `is_base` charge exists, and once
        # ONE does it refuses every schedule whose service has no base code. So
        # declaring `BASE-W` alone did not add half a feature — it armed a
        # refusal that killed `seed_demo` at the first electric schedule, before
        # premises, units, accounts, reads, bills or payments were seeded. A
        # fresh deployment could not be seeded at all.
        #
        # **The rule that follows: a base charge code is seeded for EVERY
        # service this seed prices, or for none.** `RATE_SCHEDULES` prices
        # electric and water; there are two codes here for that reason and a
        # third arrives the day a third service is priced.
        #
        # The figure is not new — [W] §1 *"Base/mo … Electric $12"*, the same
        # `fixture.ELECTRIC_BASE` that `RATE_PLANS` already carries on
        # Residential Standard's `plan_services.base_charge`.
        "code": "BASE-E",
        "name": "Electric base service — residential",
        "charge_type": "recurring",
        "service": "electric",
        "amount_rule": "flat",
        "amount": ELECTRIC_BASE,  # [W] §1 — the plan's own figure, unmoved
        "is_base": True,
        # Scoped for the same reason `BASE-W` is (`DEF-2823`): `RATE_PLANS`
        # states TWO electric bases — Residential Standard `$12` and Industrial
        # `$180` — and one unscoped code cannot be both.
        "applies_to_customer_classes": ["residential"],
    },
    {
        # ⚠ **THE INDUSTRIAL ELECTRIC BASE, AND IT IS THE FIGURE THE FIXTURE
        # ALREADY DISAGREED WITH ITSELF ABOUT (`DEF-2823`, measured).** Before
        # today `IND` stated `$180` on `plan_services.base_charge` while the
        # only `is_base` electric code stated `$12` — a **$168** gap that
        # nothing read, because the live path took the plan's figure and the
        # ruled chain had no production caller. The moment `BR-RAT-088` reached
        # the code the two became one question, and the answer is the fixture's
        # own: `[W] §1 "Industrial electric base $180"`, moved here rather than
        # reconciled by picking whichever figure a query reached first.
        #
        # **No bill moves.** Measured on 2026-08-31: 0 accounts are on `IND`,
        # and all 47 that exist are water on `SCW-RES`/`SCW-COM`.
        "code": "BASE-E-IND",
        "name": "Electric base service — industrial",
        "charge_type": "recurring",
        "service": "electric",
        "amount_rule": "flat",
        "amount": INDUSTRIAL_ELECTRIC_BASE,
        "is_base": True,
        "applies_to_customer_classes": ["industrial"],
    },
    {
        "code": "CONN",
        "name": "Connection fee",
        "charge_type": "one_time",
        "amount_rule": "flat",
        "amount": "45",  # [F]
    },
    {
        "code": "DISC",
        "name": "Disconnect fee",
        "charge_type": "one_time",
        "amount_rule": "flat",
        "amount": "45",  # [F]
    },
    # ⊕ **ADDED 2026-09-21 — PO ruling, verbatim: *"reconnection fee is $75 -
    # fix the code and seed"* (`OQ-CUS-12518`).** This seed named `CONN`,
    # `DISC`, `NSF` and `TAMPER` and **no reconnection code at all**, so a cut
    # on a demo tenant refused even once the spelling was right: `commit_cut`
    # reads the tenant's own `RECON` row and there was none to read.
    # **$75.00 is `BR-CUS-104`'s signed figure** (PO 2026-08-25, $8,240.00
    # arrears + $75.00 = $8,315.00) and matches `lookup_defaults.json`, so a
    # demo utility and a newly provisioned one now price a reconnection alike.
    {
        "code": "RECON",
        "name": "Reconnection fee",
        "charge_type": "one_time",
        "amount_rule": "flat",
        "amount": "75",  # [F]
    },
    {
        "code": "NSF",
        "name": "Returned payment (NSF) fee",
        "charge_type": "penalty",
        "amount_rule": "flat",
        "amount": "30",  # [F]
        # DEF-PAY-10698 — DECLARED the NSF fee, so a bounce on a plan listing
        # it charges it (PO 2026-10-30); never read off the code string.
        "is_nsf_fee": True,
    },
    {
        "code": "TAMPER",
        "name": "Tamper fee",
        "charge_type": "penalty",
        "amount_rule": "flat",
        "amount": "250",  # [F] — PO ruling 2026-08-10 (EP-RAT-03 §4 over [W] $500)
    },
)

# ── Taxes & jurisdictions (S13) ─────────────────────────────────────────────
# [F] lookup_defaults.json `tax_jurisdictions.TX`. `taxes.rate` is a FRACTION
# (models.Tax comment; US-RAT-009 TC-1 asserts 6.25 % → "0.062500"), so the
# fixture's percent points are written as fractions — a representation change,
# not a new number. TX-STATE's 6.25 % is the same figure the workbook's §1 tax
# table opens with. `level` is set only where the fixture NAMES it ("Texas
# State"); "Local" gets none rather than a guessed county/city split.
TAX_RULES: tuple[dict[str, Any], ...] = (
    {
        "name": "Texas State",
        "jurisdiction": {"name": "Texas State", "level": "state"},
        "kind": "percent",
        "rate": "0.0625",  # [F] 6.25 %
    },
    {
        "name": "Local",
        "jurisdiction": {"name": "Local"},
        "kind": "percent",
        "rate": "0.02",  # [F] 2.00 %
    },
)

# ── Rate schedules (S11) ────────────────────────────────────────────────────
# One service, one model (BR-RAT-031). `effective_from` present + a complete
# structure ⇒ the first version is written ACTIVE (create_rate_schedule).
SCHEDULE_EFFECTIVE_FROM = "2026-08-01"  # the packet's fixture window (no money)

# US-RAT-006 TC-1 "Option B" signed configuration (mirrored verbatim in
# tests/test_us_rat_helpers.tou_structure): the ONLY TOU config in the signed
# corpus that states its WINDOW TIMES as well as its prices. Its summer prices
# are the workbook's own Residential Standard summer on/off figures
# ([W] §1: "summer on $0.22 … off $0.09").
# ⚠ AMENDED 2026-08-16 (pricing-engines lane). The note here used to say the
# three-window on/mid/off variants "state prices but NO window boundaries, so
# they are NOT built here". That is true of the Small Commercial TOU and it is
# NOT true of the residential MID window: **US-RAT-006 TC-3 states its
# boundaries in as many words** — *"Mid-peak 11:00-14:00 … accepted (<=3
# windows); coverage check passes (off-peak reshapes to 20:00-11:00)"* — and
# [W] §1 states its PRICE for this very plan (*"summer on $0.22 / mid $0.14 /
# off $0.09"*). Two cited sources, one for the hours and one for the money,
# neither invented: TC-3's own illustrative price ($0.15) belongs to the wizard
# story's example and is NOT this tenant's, whose summer on/off figures are
# already the workbook's.
#
# The consequence is worth stating: with the mid window built, the demo tenant's
# electric schedule is the REFERENCE BILL's schedule, so a bill run over it
# reproduces B5 GT-17's own **$88.60** of electric usage (120 x 0.22 + 200 x
# 0.14 + 380 x 0.09) rather than a partial version of it. The Small Commercial
# TOU stays omitted — its window boundaries are stated nowhere.
_TOU_SEASONS = (
    {"label": "Summer", "start_month": 6, "start_day": 1, "end_month": 9, "end_day": 30},
    {"label": "Winter", "start_month": 10, "start_day": 1, "end_month": 5, "end_day": 31},
)
_TOU_WINDOWS = (
    {
        "label": "On-peak",
        "season": "Summer",
        "day_type": "weekday",
        "start_time": "14:00",
        "end_time": "20:00",
        "unit_price": "0.22",  # [W] §1 summer on-peak
        # BR-RAT-067 (PO 2026-08-16, OQ-236): the utility SAYS which register.
        # For the demo tenant the seed is the utility, so it states them here
        # rather than leaving the engine to rank prices — the workbook names
        # these three windows on/mid/off and metering's registers carry the
        # same three names (B2 r8 / BR-MET-059).
        "channel": "tou_on",
    },
    {
        # US-RAT-006 TC-3 boundaries; [W] §1 Residential Standard summer mid.
        "label": "Mid-peak",
        "season": "Summer",
        "day_type": "weekday",
        "start_time": "11:00",
        "end_time": "14:00",
        "unit_price": "0.14",  # [W] §1 summer mid-peak
        "channel": "tou_mid",
    },
    {
        "label": "Off-peak",
        "season": "Summer",
        "day_type": "weekday",
        # TC-3: adding the mid window RESHAPES off-peak to 20:00-11:00, so the
        # 24 hours still belong to exactly one window each (BR-RAT-033).
        "start_time": "20:00",
        "end_time": "11:00",
        "unit_price": "0.09",  # [W] §1 summer off-peak
        "channel": "tou_off",
    },
    {
        "label": "All day",
        "season": "Winter",
        "day_type": "weekday",
        "start_time": "00:00",
        "end_time": "00:00",
        "unit_price": "0.13",  # US-RAT-006 TC-1 winter all-day
        # ONE window covering the whole winter day, so the meter reports it on
        # ONE register. `tou_off` is the STATED choice and the reason is written
        # down rather than inferred: BR-RAT-033 is the only signed sentence that
        # names a window by price ("the off-peak (lowest-price) window of its
        # season"), and an all-day window is its season's lowest-price window.
        # A tenant who wires their meter differently changes it on S11.
        "channel": "tou_off",
    },
)

# ── DEF-2799 · THE SIZE AXIS AND THE VERSION BASE ───────────────────────────
# Both facts are seeded together or neither is — see the long note above
# `apps.rating.sample_data.sample_size_rows`, which this seeder shares. In
# short: with `rate_size_rows` empty the ruled R1–R7 chain refuses every meter
# at R3 (*"connection size … has no row"*), and with the rows written but
# `tariff_versions.base_charge` NULL it refuses them again with the other
# sentence (*"…with a BLANK base charge"*). `version_base` below is the SAME
# figure the plan states for that service. ⚠ **THAT USED TO MATTER BECAUSE
# `gather._base_charge_for` WOULD HAVE REFUSED A DISAGREEMENT, AND IT STOPPED
# MATTERING ON 2026-09-28 (`DEF-BIL-7170`)** — the plan's and the schedule's
# figures are both retired and neither is read, so there is nothing left to
# disagree with. The seeder keeps writing one figure in both places because
# both are still SHOWN; it is
# injected in `_seed_schedules` and cross-checked against `RATE_PLANS` there,
# so the two literals cannot drift apart unnoticed.
RATE_SCHEDULES: tuple[dict[str, Any], ...] = (
    {
        "name": "Residential Electric — TOU",
        "base_code": "BASE-E",  # DEF-RAT-9842 — RES-STD electric, $12.00
        "service": "electric",
        "model": "time_of_use",
        "uom": "kWh",
        "effective_from": SCHEDULE_EFFECTIVE_FROM,
        "structure": {
            "seasons": [dict(season) for season in _TOU_SEASONS],
            "windows": [dict(window) for window in _TOU_WINDOWS],
        },
    },
    {
        # [W] §1 Residential Standard: "Water tiers (0–5 kgal $4.00 /
        # 5–15 $6.50 / 15+ $8.00)"; the same tier set prices WE-1/6/9/10.
        "name": "Residential Water — Inclining tiers",
        "base_code": "BASE-W",  # DEF-RAT-9842 — RES-STD water, $8.00
        "service": "water",
        "model": "tiered",
        "uom": "kgal",
        # ⚠ **[W] WE-3's MINIMUM BILL LIVES HERE SINCE 2026-09-10** — PO ruling,
        # *"set it in rates and use it in plans - thats it - this is rule"*. It
        # was `RATE_PLANS["RES-STD"]` water's `minimum_amount`, and moving it is
        # what stops `WE-3` under-billing by **$5.40** a month: a `0.4 kgal`
        # residential water bill prices `$9.60` usage + `$8.00` base = `$17.60`
        # and the floor tops it to nothing at all if this figure is absent,
        # because `BR-RAT-028` mode (A) has no other home now. Migrations
        # `rating/0030` (move) + `0031` (remove).
        "minimum_bill": "15.00",
        "effective_from": SCHEDULE_EFFECTIVE_FROM,
        "structure": {
            "tiers": [
                {"from_qty": "0", "to_qty": "5", "unit_price": "4.00"},
                {"from_qty": "5", "to_qty": "15", "unit_price": "6.50"},
                {"from_qty": "15", "to_qty": None, "unit_price": "8.00"},
            ]
        },
    },
    {
        # [W] §1 Small Commercial: "Water flat $5.20/kgal" (priced in WE-4).
        "name": "Small Commercial Water — Flat",
        "base_code": "BASE-W-COM",  # DEF-RAT-9842 — COM-SM water, $15.00
        "service": "water",
        "model": "flat",
        "uom": "kgal",
        "effective_from": SCHEDULE_EFFECTIVE_FROM,
        "structure": {"unit_price": "5.20"},
    },
    {
        # [W] §1 Industrial: "Electric energy $0.085/kWh + demand $11.00/kW"
        # (priced in WE-5). Both figures the demand model requires are ratified.
        "name": "Industrial Electric — Energy + demand",
        "base_code": "BASE-E-IND",  # DEF-RAT-9842 — IND electric, $180.00
        "service": "electric",
        "model": "demand",
        "uom": "kWh",
        "effective_from": SCHEDULE_EFFECTIVE_FROM,
        "structure": {
            "demand": {
                "energy_rate_per_kwh": "0.085",
                "demand_rate_per_kw": "11.00",
            }
        },
    },
)

# ── Plans (S10) ─────────────────────────────────────────────────────────────
# Plan-as-bundle (BR-RAT-025): one row per ticked service with its own base
# charge ([W] §1 "Base/mo" column) and its schedule.
# ⚠ **THE PER-SERVICE MINIMUM IS THE SCHEDULE'S SINCE 2026-09-10** — PO ruling,
# *"set it in rates and use it in plans - thats it - this is rule"*. It is
# authored in `RATE_SCHEDULES` above (`minimum_bill`) and a plan SHOWS it;
# `plan_services.minimum_amount` is gone (`rating/0030`+`0031`). The base is
# still stated here AND on its `is_base` charge code, which `BR-RAT-088` makes
# the source — `_assert_base_codes_state_the_plans_bases` asserts they agree.
# `penalty_rule` is deliberately absent: [W] §1's "late fee 1.5 % min $5.00,
# grace 5 days" are TENANT settings, and D6 says an untouched panel writes no
# row so the plan falls back to them.
# `deposit_rules` are ABSENT: [W] §1 states the amounts ($150 / $400 / $1,200)
# but a rule row needs an `account_type_id`, and account types are a W2
# customers table that does not exist yet — see the omissions list.
RATE_PLANS: tuple[dict[str, Any], ...] = (
    {
        "name": "Residential Standard",
        "code": "RES-STD",
        "description": "Residential electric (TOU) + water (inclining tiers).",
        "services": [
            {"service": "electric", "base_charge": "12", "schedule": "Residential Electric — TOU"},
            {
                "service": "water",
                "base_charge": "8",  # [W] §1 Residential Standard water base
                # WE-3's `$15.00` minimum MOVED to the schedule above on
                # 2026-09-10 (PO ruling). A plan states no floor of its own any
                # more; it shows the schedule's.
                "schedule": "Residential Water — Inclining tiers",
            },
        ],
        "charges": ("LATE", "NSF", "CONN"),
    },
    {
        # Water-only on purpose: [W] §1's Small Commercial electric is a TOU +
        # demand bundle whose WINDOW TIMES are not stated anywhere, so its
        # electric half is omitted rather than invented (omissions list).
        "name": "Small Commercial",
        "code": "COM-SM",
        "description": "Small commercial water on the flat $5.20/kgal schedule.",
        "services": [
            {
                "service": "water",
                "base_charge": "15",  # [W] §1 Small Commercial water base
                "schedule": "Small Commercial Water — Flat",
            },
        ],
        "charges": ("LATE", "NSF", "DISC"),
    },
    {
        "name": "Industrial",
        "code": "IND",
        "description": "Industrial electric: energy + demand, meter multiplier applies.",
        "services": [
            {
                "service": "electric",
                "base_charge": "180",  # [W] §1 Industrial electric base
                "schedule": "Industrial Electric — Energy + demand",
            },
        ],
        "charges": ("LATE", "NSF", "TAMPER"),
    },
)

# ── Premises & units (S14/S15/S16) ──────────────────────────────────────────
# EP-MET-01 §4 signed test data (addresses, owner/manager, statuses, unit
# labels and unit IDs). No money anywhere in this block.
# `premises_type` maps each §4 label onto one of the FIVE SEEDED types
# (BR-MET-034 SEED_PREMISES_TYPES) — §4's "Duplex / Multi-tenant / Warehouse"
# are that tenant's own extended entries and this seed adds no lookup rows.
#
# ⚠ **`area_code` ADDED BY CR-029 RC-W0-T1, AND IT IS WHAT MAKES THE ROUTE
# WIZARD REVIEWABLE AT ALL.** The SET-06.2 area chips filter premises by tag,
# and DEF-220 is the record of what an untagged fixture does to them: the
# filter took the picker from *"9 premises match"* to *"0 premises match"*
# every time, because `premises.area_id` had never held a value on any tenant.
# The four codes are the seeded areas (`lookup_defaults.json` — NORTH · DTWN ·
# EAST · IND); the districts below are this fixture's own geography, chosen so
# that every area holds at least one premises and two of them hold more than
# one, which is the minimum shape a filter and BR-MET-083's cascade can be
# judged on. A tenant that does not HOLD one of these areas (the S111 toggle,
# or a deletion the lookup laws allow) is tagged with what it has and reported
# — `_available_area_codes` below, the same "None is a real answer" posture
# `apps/metering/sample_data.py::_area_code_for` records.
PREMISES: tuple[dict[str, Any], ...] = (
    {
        "address_line": "1408 Bluestem Ln",
        "area_code": "NORTH",
        "city": "Katy",
        "state": "TX",
        "postal_code": "77494",
        "premises_type": "single_family",
        "owner_manager": "Whitfield Rentals LLC",
        "services_available": ["electric", "water"],
        "status": "active",
        "units": (
            {
                "label": "Unit A",
                "unit_no": "U-00101-A",
                "unit_type": "residential",
                "plan": "RES-STD",
            },
            {
                "label": "Unit B",
                "unit_no": "U-00101-B",
                "unit_type": "residential",
                "plan": "RES-STD",
            },
        ),
    },
    {
        "address_line": "2201 Cane Island Pkwy",
        "area_code": "NORTH",
        "city": "Katy",
        "state": "TX",
        "postal_code": "77494",
        "premises_type": "single_family",
        "owner_manager": "Chen, David",
        "services_available": ["electric", "water"],
        "status": "active",
        "units": (
            {
                "label": "Unit 1",
                "unit_no": "U-00102",
                "unit_type": "residential",
                "plan": "RES-STD",
            },
        ),
    },
    {
        "address_line": "500 Mason Rd Plaza",
        "area_code": "DTWN",
        "city": "Katy",
        "state": "TX",
        "postal_code": "77450",
        "premises_type": "commercial_building",
        "owner_manager": "Mason Rd Holdings",
        "services_available": ["electric", "water"],
        "status": "active",
        "units": (
            {
                "label": "Master",
                "unit_no": "U-00214-M",
                "unit_type": "commercial_master",
                "plan": "COM-SM",
            },
            {
                "label": "Suite 200",
                "unit_no": "U-00214-200",
                "unit_type": "commercial",
                "plan": "COM-SM",
            },
        ),
    },
    {
        "address_line": "2200 Riverbend Ct",
        "area_code": "EAST",
        "city": "Katy",
        "state": "TX",
        "postal_code": "77494",
        "premises_type": "apartment_complex",
        "owner_manager": "Riverbend Apts LP",
        "services_available": ["electric", "water"],
        "status": "active",
        "units": (
            {
                "label": "Apt 101",
                "unit_no": "U-00318-101",
                "unit_type": "residential_submetered",
                "plan": "RES-STD",
            },
            {
                "label": "Apt 102",
                "unit_no": "U-00318-102",
                "unit_type": "residential_submetered",
                "plan": "RES-STD",
            },
            {
                "label": "Apt 103",
                "unit_no": "U-00318-103",
                "unit_type": "residential_submetered",
                "plan": "RES-STD",
            },
        ),
    },
    {
        "address_line": "3450 Pin Oak Dr",
        "area_code": "EAST",
        "city": "Katy",
        "state": "TX",
        "postal_code": "77494",
        "premises_type": "single_family",
        "owner_manager": "Rodriguez, M.",
        "services_available": ["electric", "water"],
        "status": "pending",
        "units": (
            {
                "label": "Unit 1",
                "unit_no": "U-00350",
                "unit_type": "residential",
                "plan": "RES-STD",
            },
        ),
    },
    {
        "address_line": "77 Gulf Fwy Industrial",
        "area_code": "IND",
        "city": "Katy",
        "state": "TX",
        "postal_code": "77494",
        "premises_type": "commercial_building",
        "owner_manager": "Northwind Mfg.",
        "services_available": ["electric", "water"],
        "status": "active",
        "units": (
            {
                "label": "Bldg 1",
                "unit_no": "U-00420",
                "unit_type": "commercial",
                "plan": "IND",
            },
        ),
    },
)

# ── Billing cycles & routes (S26/S27) ───────────────────────────────────────
# EP-MET-02 §4 (US-MET-005/006) signed test data, REBUILT BY CR-029 RC-W0-T1
# (B17 §7). `due_days` 20 is that §4's own "+20 days" — a date-math input, not
# money (the workbook's §1 "due-days 21" is the tenant-level default; the cycle
# rows carry the metering §4 value).
#
# WHAT CHANGED, AND WHY EACH PART OF IT IS A RULING RATHER THAN A PREFERENCE
# --------------------------------------------------------------------------
# 1. **The codes are `CY-001…` / `RT-001…`** — D5, PO verbatim: *"Rt-001 is
#    good"*. The old `08-A` / `Route 1` grammar is history for these rows.
# 2. **Every cycle carries the three ruled fields about time** — start day ·
#    frequency · days to complete (B17 §2, from the PO's pre-CR ruling) — and
#    NOT the legacy `window_start`/`window_end`/`bill_date` DATES, which D2
#    supersedes and RC-W5 drops. `create_cycle` keeps the legacy day pair in
#    step by itself (`_sync_cycle_schedule`), so nothing loses a window.
# 3. **`bill_day` and `due_days` STAY, as the cycle's DEFAULTS** — D9, PO
#    verbatim: *"when we configure Cycle we are provideing default values;
#    mostly it wil remain as it is but user can over ride them during
#    billing"*. They are date math, never money (BR-MET-078).
# 4. **EVERY ROUTE CARRIES A SERVICE AND AN AREA.** B17 §5 gap G7: *"seeded
#    routes carry no service/area"*, so the SET-06.2 area chips filtered a
#    tenant in which no route had ever held an area — the filter and the whole
#    cascade were unexercised on the only data a reviewer ever opens. D7 closes
#    it: *"Yes - please do it"*. A route with a NULL service is the LEGACY
#    all-services route and DEF-227 is the record of what one does to a
#    service point that already belongs to a route drawn for its own service.
#    There are now none in this fixture.
#
# ⚠ **ONE SERVICE PER ROUTE HERE, NOT A SERVICE SET (D10), AND THAT IS A
# BOUNDARY AND NOT A DISAGREEMENT.** D10 rules *"yes it will be multi
# service"* — RT-001 is "Water + Electric" — and the column behind it lands
# with RC-W1's task W1-T4, which has not shipped. Seeding the SET is the
# remaining half of W0-T1. Until then each service gets its own route, which
# is lawful today (BR-MET-074: a unit is on ≤1 route PER SERVICE, and a house
# read for water on Tuesday and electric by AMI is the case that rule exists
# for) and re-reads cleanly as a set when the column arrives: RT-001 + RT-002
# are one North stop with two crews.
#
# ⚠ **NO WALK ORDERS AND NO METER EXCLUSION ARE SEEDED YET** — both are the
# other half of W0-T1 and both need W1-T4: D11 puts the sequence grain at PER
# PREMISES (*"Per premises"* — one stop, many meters) and today's `walk_order`
# is a per-UNIT column, and `route_meter_exclusions` has no `reason` column to
# carry the two-word reason the SET-06D Assets tab renders in place. Seeding a
# per-unit walk order now would seed the reading D11 superseded.
#
# ⚠ **WHICH FREQUENCIES ARE SEEDED, AND WHY THE OTHER THREE ARE NOT.** Monthly
# · Bimonthly · Quarterly · Semiannual · Annual all anchor on a DAY OF MONTH
# (B17 §2), which is exactly what `cycles.start_day` holds and what
# `create_cycle` validates (1–31). Daily is n/a by that same table, and
# **Weekly and Fortnightly anchor on a WEEKDAY for which no column exists** —
# `start_day` would take an integer 1–31 that no rule gives a weekday meaning.
# Seeding one would invent that meaning, so they wait for the field.
CYCLES: tuple[dict[str, Any], ...] = (
    {
        "code": "CY-001",
        "name": "Residential monthly",
        "frequency": "Monthly",
        "start_day": 1,
        "days_to_complete": 3,  # read 1–3 · the D1 worked figure's own shape
        "bill_day": 5,
        "due_days": 20,
        "first_run_date": "2026-09-01",
    },
    {
        "code": "CY-002",
        "name": "Commercial monthly",
        "frequency": "Monthly",
        "start_day": 12,
        "days_to_complete": 5,  # read 12–16
        "bill_day": 19,
        "due_days": 20,
        "first_run_date": "2026-09-12",
    },
    {
        "code": "CY-003",
        "name": "Irrigation quarterly",
        "frequency": "Quarterly",
        "start_day": 15,
        "days_to_complete": 5,  # read 15–19
        "bill_day": 22,
        "due_days": 20,
        "first_run_date": "2026-09-15",
    },
    {
        "code": "CY-004",
        "name": "Industrial bimonthly",
        "frequency": "Bimonthly",
        "start_day": 20,
        "days_to_complete": 4,  # read 20–23
        "bill_day": 26,
        "due_days": 20,
        "first_run_date": "2026-09-20",
    },
    {
        "code": "CY-005",
        "name": "Backflow semiannual",
        "frequency": "Semiannual",
        "start_day": 10,
        "days_to_complete": 2,  # read 10–11
        "bill_day": 15,
        "due_days": 20,
        "first_run_date": "2026-10-10",
    },
    # A cycle with NO routes on it, deliberately: the SET-05 cycles landing
    # states its own coverage (*"42 accounts sit on no cycle — they are never
    # read and never billed until one is assigned"*) and SET-07D's Coverage tab
    # is a whole tab about the gap. Neither can be reviewed against a fixture in
    # which every cycle is full.
    {
        "code": "CY-006",
        "name": "Fire-line annual",
        "frequency": "Annual",
        "start_day": 5,
        "days_to_complete": 1,  # read on the 5th
        "bill_day": 8,
        "due_days": 20,
        "first_run_date": "2026-11-05",
    },
)

ROUTES: tuple[dict[str, Any], ...] = (
    {
        "code": "RT-001",
        "name": "Katy North — water + electric",
        "route_type": "walk",
        # D10, PO verbatim: *"yes it will be multi service"*, and the upgraded
        # prototype draws RT-001 as exactly this. `service_codes` is the SET;
        # the FIRST member becomes the transitional head `routes.service_id`
        # that BR-MET-074's uniques key on, so it is ordered deliberately.
        "service_codes": ("water", "electric"),
        "area_code": "NORTH",
        "cycle": "CY-001",
        "premises": ("1408 Bluestem Ln", "2201 Cane Island Pkwy"),
    },
    {
        "code": "RT-002",
        "name": "Downtown plaza — electric",
        "route_type": "ami",
        "feeder_ref": "F-02",
        "service_codes": ("electric",),
        "area_code": "DTWN",
        "cycle": "CY-002",
        "premises": ("500 Mason Rd Plaza",),
        # THE FIXTURE'S ONE METER EXCLUSION, and it is a real one rather than a
        # decoration: M-7200 is the building's MASTER electric meter and the
        # Suite 200 sub-meter (M-7204) hangs off it. A crew walking the tenant
        # route does not read the master — BR-MET-075, and the reason is the
        # two words SET-06D's Assets tab renders in place beside the row.
        # ⚠ APPLIED AFTER THE ASSETS ARE SEEDED (`_apply_route_exclusions`),
        # because an exclusion names an asset id and the assets do not exist
        # when the routes are created.
        "exclusions": {"M-7200": "master metered"},
    },
    {
        "code": "RT-003",
        "name": "Riverbend — electric drive-by",
        "route_type": "drive",
        "service_codes": ("electric",),
        "area_code": "EAST",
        "cycle": "CY-001",
        "premises": ("2200 Riverbend Ct", "3450 Pin Oak Dr"),
    },
    {
        "code": "RT-004",
        "name": "Riverbend — irrigation walk",
        "route_type": "walk",
        "service_codes": ("water",),
        "area_code": "EAST",
        "cycle": "CY-003",
        # The SAME two premises as RT-003, for the OTHER service. BR-MET-074's
        # own case — one address, two crews — kept beside RT-001's service SET
        # so the fixture holds both shapes a reviewer has to be able to tell
        # apart: one route that reads two services, and two routes that split
        # them.
        "premises": ("2200 Riverbend Ct", "3450 Pin Oak Dr"),
    },
    {
        "code": "RT-005",
        "name": "Gulf Fwy industrial — electric",
        "route_type": "ami",
        "feeder_ref": "F-03",
        "service_codes": ("electric",),
        "area_code": "IND",
        "cycle": "CY-004",
        "premises": ("77 Gulf Fwy Industrial",),
    },
    {
        "code": "RT-006",
        "name": "Gulf Fwy industrial — water walk",
        "route_type": "walk",
        "service_codes": ("water",),
        "area_code": "IND",
        "cycle": "CY-005",
        "premises": ("77 Gulf Fwy Industrial",),
    },
)

# ── Assets (S49/S51) ────────────────────────────────────────────────────────
# EP-MET-01 §4 meter numbers (the ones tied to these very units) + EP-AST-01 §4
# for the inventory spare M-5099 and the BF-3301 backflow. Each measuring asset
# declares its service AND an explicit UoM (BR-AST-009 / CLAUDE.md rule 3) and
# carries all three classifications: asset type · meter type (BR-AST-044) ·
# read method (BR-AST-043). Non-measuring assets leave `meter_type` and
# `read_method` NULL — the service refuses a meter type there (BR-AST-044 as
# amended), which is exactly the shape BF-3301 and BAT-0904 prove.
# `unit` here is a (premises address, unit label) pair, not a UoM; the UoM is
# the `uom` key. No money in this block — multipliers are counts (M-7210's ×10
# is EP-MET-01 §4's own).
ASSET_INSTALL_DATE = "2025-01-06"  # one seed install date; assign-on-create needs one
ASSETS: tuple[dict[str, Any], ...] = (
    {
        "asset_no": "M-7001",
        "type": "meter",
        "service": "electric",
        "uom": "kWh",
        "meter_type": "ami",
        "read_method": "ami",
        "multiplier": "1",
        "on": ("1408 Bluestem Ln", "Unit A"),
    },
    {
        "asset_no": "W-7001",
        "type": "meter",
        "service": "water",
        "uom": "kgal",
        "meter_type": "ami",
        "read_method": "ami",
        "multiplier": "1",
        "on": ("1408 Bluestem Ln", "Unit A"),
    },
    {
        "asset_no": "M-7200",
        "type": "meter",
        "service": "electric",
        "uom": "kWh",
        "meter_type": "master",
        "read_method": "ami",
        "multiplier": "1",
        "on": ("500 Mason Rd Plaza", "Master"),
    },
    {
        "asset_no": "M-7204",
        "type": "sub_meter",
        "service": "electric",
        "uom": "kWh",
        "meter_type": "sub_meter",
        "read_method": "walk_by",
        "multiplier": "1",
        "parent_asset_no": "M-7200",
        "on": ("500 Mason Rd Plaza", "Suite 200"),
    },
    {
        "asset_no": "M-7301",
        "type": "meter",
        "service": "electric",
        "uom": "kWh",
        "meter_type": "ami",
        "read_method": "ami",
        "multiplier": "1",
        "on": ("2200 Riverbend Ct", "Apt 101"),
    },
    {
        # ── CR-054 W0 task 1 — THE NET METER, AND THE FLAG IS A RULE ────────
        # `net_metering` is OPTIONAL on type `meter` and unavailable on a
        # non-measuring type — BR-AST-010, enforced in
        # `assets.services._validate_asset` (`NET_METERING_OPTIONAL`). So
        # setting it here invents no rule; WHICH meter carries it is this
        # fixture's own choice and is recorded in the decision log.
        # The consequence is the one BR-AST-029 states: a net meter's cycle is a
        # consumption record PLUS an export record, so the plan-driven required
        # set for this meter is its plan's four TOU registers + `export`, and
        # `DEMO_CYCLE_READS` below seeds all five. A residential solar household
        # on a time-of-use tariff is the ordinary shape of that customer.
        "asset_no": "M-7302",
        "type": "meter",
        "service": "electric",
        "uom": "kWh",
        "meter_type": "ami",
        "read_method": "ami",
        "multiplier": "1",
        "net_metering": True,
        "on": ("2200 Riverbend Ct", "Apt 102"),
    },
    {
        # ── CR-054 W0 task 1 — THE TIME-OF-USE METER ────────────────────────
        # EP-MET-03 §4 signed test data names it and gives it its registers:
        # *"TOU M-7450 (E, kWh — deltas tou_on 210 / tou_mid 118 / tou_off 96 /
        # total 430 → sum-sanity 1.40%)"*. Without a meter on a TOU plan reading
        # all four registers, `validation.tou_sum_sanity` can only ever answer
        # `not_evaluated: incomplete_group` on this tenant, and
        # `plan_register_completeness` has no complete meter to contrast the
        # short one against.
        # ⚠ The UNIT is this fixture's pairing, not §4's: §4 lists no meter for
        # U-00102, and it is the one ACTIVE residential unit in the fixture with
        # no electric meter on it. Recorded in the decision log.
        "asset_no": "M-7450",
        "type": "meter",
        "service": "electric",
        "uom": "kWh",
        "meter_type": "ami",
        "read_method": "ami",
        "multiplier": "1",
        "on": ("2201 Cane Island Pkwy", "Unit 1"),
    },
    {
        "asset_no": "M-7210",
        "type": "meter",
        "service": "electric",
        "uom": "kWh",
        "meter_type": "amr",
        "read_method": "amr",
        "multiplier": "10",  # EP-MET-01 §4: "M-7210, ×10 multiplier"
        "on": ("77 Gulf Fwy Industrial", "Bldg 1"),
    },
    {
        # US-AST-001 §4: "M-5099 meter · E · AMI · ×1 · Inventory" — the
        # BR-AST-011 leave-in-inventory path (no unit, status inventory).
        "asset_no": "M-5099",
        "type": "meter",
        "service": "electric",
        "uom": "kWh",
        "meter_type": "ami",
        "read_method": "ami",
        "multiplier": "1",
        "on": None,
    },
    {
        # EP-AST-01 §4 backflow preventer: NON-measuring, so no service, no
        # UoM, and meter_type/read_method stay NULL by law (BR-AST-009/044).
        "asset_no": "BF-3301",
        "type": "backflow",
        "last_test_date": "2025-06-02",
        "test_interval_months": 12,
        "on": ("500 Mason Rd Plaza", "Suite 200"),
    },
    {
        # EP-AST-01 §4 "BAT-0904 battery · Inventory" — non-measuring spare.
        "asset_no": "BAT-0904",
        "type": "battery",
        "on": None,
    },
)

# ── WHAT THIS UTILITY MEASURES AND WHAT IT DOES NOT (BR-RAT-081 · DEF-2310) ──
#
# ⚠ **THIS BLOCK EXISTS BECAUSE THE RULED `$45.00` WAS UNREACHABLE ON EVERY
# SHIPPED TENANT.** `BR-RAT-081` (PO 2026-08-20, verbatim: *"yes we have to say
# service is meter or unmetered"*) and `BR-RAT-090` (option A, closing OQ-283 —
# **3 carts × `$15.00` = `$45.00`; take one away and the next bill is
# `$30.00`**) were both signed, `DEF-495` gave the column a reader and
# `DEF-1813` built the whole bill path behind it — and no tenant anywhere
# declared a single service unmetered, because nothing could write the column.
# Every figure that work produced was reachable only by editing a database row
# by hand. This is the fixture's half of closing that.
#
# **NOTHING HERE IS INVENTED.** `trash` is unmetered by the PO's own example
# (CR-019: *"in trash you ahve trash cans … 1 trash can $15 - for example if you
# ahve 3 you multiple by 3"*), and `cart` is the platform's own seeded unit,
# scoped to trash in `fixtures/lookup_defaults.json`.
#
# ⚠ **IT DECLARES; IT DOES NOT ENABLE, AND THAT IS A BOUNDARY AND NOT AN
# OVERSIGHT.** Brazos Bend signs up for `electric + water`, so its trash row is
# present-but-off (New mandate 4, PO 2026-08-17) and `unmetered_service_codes()`
# — which filters `enabled=True` — still returns nothing for it. Switching a
# seeded tenant's service ON is `DEF-1250`/`DEF-2490`'s work, in
# `apps/rating/sample_data.py`, and doing it from here would collide with a lane
# running today. What this guarantees is that the declaration is ALREADY TRUE
# the moment that lane switches trash on: no second migration of anybody's
# database, no hand-edited row.
SERVICE_MEASUREMENT: tuple[dict[str, Any], ...] = (
    {
        "service": "trash",
        # BR-TEN-1180 — the whole point of the block. It was `metered: False`
        # until the PO's ruling of 2026-09-02 gave the column three values
        # (`DEF-2409`); `capacity` is what the false side of that boolean always
        # MEANT here — *"in trash you ahve trash cans … 1 trash can $15 - for
        # example if you ahve 3 you multiple by 3"* is a COUNT, which is
        # `BR-RAT-090` and is the `capacity` basis by name.
        "billing_basis": "capacity",
        # r6.4 / BR-RAT-038 as the tenant holds it. `rating.sample_data
        # ._trash_uom()` asks `seams.billed_uom("trash")` for exactly this and
        # has fallen back to a constant every time it has ever been called
        # (DEF-497 fixed the READ; there was nothing to read). No conversion
        # factor is stated and none is owed: an unmetered service has no
        # register, so there are not two units to reconcile (BR-MET-710 — the
        # count crosses the billing seam unitless).
        "billed_uom": "cart",
    },
)

# ── The multi-register cycle reads (CR-054 W0 task 1) ───────────────────────
#
# ⚠ **WHY THIS BLOCK EXISTS, MEASURED BEFORE IT WAS WRITTEN.** On a freshly
# seeded demo tenant, `select channel, count(*) from meter_reads group by 1`
# returned exactly one row — **`total | 199`**. Every reading this product had
# ever seeded carried NO channel, and `read_import.parse_row` defaults an absent
# one to `total` (*"BR-MET-059: absent ⇒ the flat meter's one channel"*). So the
# demo utility could not demonstrate a single one of the register rules the
# engine already computes:
#
#   * `validation.plan_register_completeness` — the shortfall warning that names
#     what is missing (*"expects total/tou_on/tou_mid/tou_off, file has total
#     only"*) — had nothing short to fire on, because no demo unit carried a
#     plan at all and the resolver answered `no_plan` for every meter;
#   * `validation.tou_sum_sanity` — Σ windows ≈ total within the tenant's
#     tolerance — could only ever answer `not_evaluated: incomplete_group`;
#   * the DEMAND path — a peak in kW that is a MAXIMUM and never a delta, the
#     quantity half of DEF-797 (**$154.00 against a correct $4,532.00**) — had
#     no `demand` register anywhere on the tenant;
#   * `export` on a net meter (BR-AST-029) was known-absent and recorded as such
#     in `apps/metering/selectors.py`'s CR-028 debt-sweep note.
#
# **NOTHING HERE IS A REGISTER VALUE INVENTED TO MAKE A RULE FIRE.** Every
# figure is either quoted from signed §4 test data (cited at the row), derived
# from one by arithmetic that is shown, or an opening BASELINE — the number a
# dial happened to be standing at, which prices nothing and is authored, exactly
# as `core/sample_fixture` authors its own (*"THIS IS FIXTURE AUTHORSHIP, NOT
# SIGNED LAW, AND IT PRICES NOTHING"*). **No threshold, rate or rule is stated
# here**: the 1 % TOU tolerance is the tenant's own seeded
# `tou_sum_tolerance_pct` (BR-MET-052 / RATIFIED_SERVICE_SEED), read from
# config, and this fixture never writes it.
#
# **NO MONEY MOVES ON ANY OF THESE READS.** seed_demo creates no account and no
# bill run, so nothing prices them; they are quantities with their explicit
# units (CLAUDE.md rule 3).
#
# ⚠ **THE DATES ARE CONSTRAINED BY THE PLAN, NOT CHOSEN FOR LOOKS.** Plans and
# rate schedules are effective from `SCHEDULE_EFFECTIVE_FROM` (2026-08-01), and
# `PlanRegisterResolver` asks rating for the plan version AS OF THE READ DATE —
# so a read dated before that resolves `no_version` and the completeness rule
# reports `not_evaluated`. The AUGUST read of each pair is therefore the one
# that carries the verdict; the JULY read is the prior register the product
# derives consumption from (BR-MET-019), and its own completeness verdict is a
# truthful `not_evaluated` for want of a plan version.
#
# Read dates sit INSIDE their cycle's derived window (BR-MET-057) so
# `out_of_window` reports `ok` rather than a warning on every row: *Residential
# monthly* reads on days 1–3, *Industrial bimonthly* on days 20–23. The cycle is
# named by its NAME and not its `CY-###` code — see `_seed_multi_register_reads`
# for the measured reason.
DEMO_CYCLE_READS: tuple[dict[str, Any], ...] = (
    {
        # ── The residential electric round, prior cycle ─────────────────────
        "period_month": "2026-07-01",
        "cycle": "Residential monthly",
        "service": "electric",
        "read_method": "ami",
        "source_detail": "ami_itron",
        "file_name": "demo-2026-07-cy001-electric.csv",
        "rows": (
            # M-7450 · the TOU meter's opening registers. BASELINE figures —
            # what the four dials read; the DELTAS in the August batch are the
            # signed half.
            {
                "meter_id": "M-7450",
                "read_date": "2026-07-01",
                "channel": "tou_on",
                "reading": "4110",
            },
            {
                "meter_id": "M-7450",
                "read_date": "2026-07-01",
                "channel": "tou_mid",
                "reading": "2240",
            },
            {
                "meter_id": "M-7450",
                "read_date": "2026-07-01",
                "channel": "tou_off",
                "reading": "1860",
            },
            {
                "meter_id": "M-7450",
                "read_date": "2026-07-01",
                "channel": "total",
                "reading": "8210",
            },
            # M-7301 · THE DELIBERATELY SHORT METER. Its unit is on RES-STD,
            # whose electric schedule is time-of-use, so its required set is
            # four registers — and the file carries one, every cycle, exactly as
            # a crew that read the dial and not the windows would hand in.
            {
                "meter_id": "M-7301",
                "read_date": "2026-07-01",
                "channel": "total",
                "reading": "8410",
            },
            # M-7302 · the NET meter (BR-AST-010 flag above): four TOU registers
            # plus the grid-push register BR-AST-029 requires.
            {
                "meter_id": "M-7302",
                "read_date": "2026-07-01",
                "channel": "tou_on",
                "reading": "3050",
            },
            {
                "meter_id": "M-7302",
                "read_date": "2026-07-01",
                "channel": "tou_mid",
                "reading": "1620",
            },
            {
                "meter_id": "M-7302",
                "read_date": "2026-07-01",
                "channel": "tou_off",
                "reading": "1410",
            },
            {
                "meter_id": "M-7302",
                "read_date": "2026-07-01",
                "channel": "total",
                "reading": "6080",
            },
            {
                "meter_id": "M-7302",
                "read_date": "2026-07-01",
                "channel": "export",
                "reading": "940",
            },
        ),
    },
    {
        # ── The residential electric round, the cycle read that is JUDGED ────
        "period_month": "2026-08-01",
        "cycle": "Residential monthly",
        "service": "electric",
        "read_method": "ami",
        "source_detail": "ami_itron",
        "file_name": "demo-2026-08-cy001-electric.csv",
        "rows": (
            # ⚖️ **THE THREE WINDOW DELTAS ARE EP-MET-03 §4's OWN**, verbatim:
            # *"TOU M-7450 (E, kWh — deltas tou_on 210 / tou_mid 118 / tou_off
            # 96 / total 430 → sum-sanity 1.40%)"*. 4110+210 · 2240+118 ·
            # 1860+96.
            {
                "meter_id": "M-7450",
                "read_date": "2026-08-01",
                "channel": "tou_on",
                "reading": "4320",
            },
            {
                "meter_id": "M-7450",
                "read_date": "2026-08-01",
                "channel": "tou_mid",
                "reading": "2358",
            },
            {
                "meter_id": "M-7450",
                "read_date": "2026-08-01",
                "channel": "tou_off",
                "reading": "1956",
            },
            # ⚠ **THE TOTAL IS 424, WHICH IS 210+118+96 — §4's OWN THREE WINDOWS
            # ADDED UP — AND NOT §4's 430, AND THE DIFFERENCE IS THE WHOLE
            # POINT.** §4's pair (430 against a window sum of 424) is a 1.40 %
            # deviation and therefore a BREACH of the tenant's seeded 1 %
            # `tou_sum_tolerance_pct`: it is §4's FLAGGED case, and it is what
            # `validation.tou_sum_sanity` exists to catch. A demo whose only TOU
            # meter is permanently flagged teaches a clerk to dismiss the flag,
            # so the fixture seeds the HEALTHY case — the same three signed
            # window deltas with a total that agrees, deviation 0.000000 % —
            # and the flagged case is one number away (8634 → 8640) for anyone
            # who wants to see the warning fire. Recorded in the decision log.
            {
                "meter_id": "M-7450",
                "read_date": "2026-08-01",
                "channel": "total",
                "reading": "8634",
            },
            # 8410 + 682. A plain running total on a four-register plan.
            {
                "meter_id": "M-7301",
                "read_date": "2026-08-01",
                "channel": "total",
                "reading": "9092",
            },
            # 192 + 104 + 88 = 384, the total's own delta. Baseline authorship,
            # summing exactly, for the same reason M-7450's does.
            {
                "meter_id": "M-7302",
                "read_date": "2026-08-01",
                "channel": "tou_on",
                "reading": "3242",
            },
            {
                "meter_id": "M-7302",
                "read_date": "2026-08-01",
                "channel": "tou_mid",
                "reading": "1724",
            },
            {
                "meter_id": "M-7302",
                "read_date": "2026-08-01",
                "channel": "tou_off",
                "reading": "1498",
            },
            {
                "meter_id": "M-7302",
                "read_date": "2026-08-01",
                "channel": "total",
                "reading": "6464",
            },
            {
                "meter_id": "M-7302",
                "read_date": "2026-08-01",
                "channel": "export",
                "reading": "1062",
            },
        ),
    },
    {
        # ── The industrial round, prior cycle ────────────────────────────────
        "period_month": "2026-07-01",
        "cycle": "Industrial bimonthly",
        "service": "electric",
        "read_method": "amr",
        "source_detail": "drive_by",
        "file_name": "demo-2026-07-cy004-electric.csv",
        "rows": (
            {
                "meter_id": "M-7210",
                "read_date": "2026-07-20",
                "channel": "total",
                "reading": "44000",
            },
            # ⚖️ **A DEMAND REGISTER IS A MAXIMUM, NOT A COUNTER** — BR-MET-051
            # (*"Demand: manual demand-register value at cycle read + reset
            # noted"*), and `register_units.billable_quantity` bills its VALUE.
            # The register is read on the SECONDARY side of the CT, so what the
            # dial says is the peak divided by the meter's own ×10 factor
            # (EP-MET-01 §4: *"M-7210, ×10 multiplier"*): 39.8 × 10 = 398 kW.
            # 398 → 412 kW is DEF-797's own measured pair on this very schedule.
            {
                "meter_id": "M-7210",
                "read_date": "2026-07-20",
                "channel": "demand",
                "reading": "39.8",
            },
        ),
    },
    {
        # ── The industrial round, the cycle read that is JUDGED ──────────────
        "period_month": "2026-08-01",
        "cycle": "Industrial bimonthly",
        "service": "electric",
        "read_method": "amr",
        "source_detail": "drive_by",
        "file_name": "demo-2026-08-cy004-electric.csv",
        "rows": (
            # 44000 + 2754. EP-MET-03 §4: *"M-7210 (E, ×10 factor, raw 2,754 →
            # computed 27,540 kWh, factor warning)"* — the raw delta is the
            # signed figure and the product applies the ×10 itself (BR-MET-019).
            {
                "meter_id": "M-7210",
                "read_date": "2026-08-20",
                "channel": "total",
                "reading": "46754",
            },
            # 41.2 × 10 = **412 kW**, which is DEF-797's correct peak — the one
            # that prices at 412 × $11.00 = $4,532.00 on the Industrial schedule
            # and that the defect billed as 14 kWh. Nothing here prices it; the
            # point is that the committed read carries 412 in **kW**
            # (`register_units.register_unit`) and not a difference of two peaks.
            # `demand_reset` is BR-MET-051's *"reset noted"* — the 7th published
            # template column, which nothing on this tenant has ever set. It is
            # lawful ONLY on a demand row (`demand_reset_not_demand_channel`).
            {
                "meter_id": "M-7210",
                "read_date": "2026-08-20",
                "channel": "demand",
                "reading": "41.2",
                "demand_reset": "true",
            },
        ),
    },
)

# Printed verbatim by the closing summary. Each line names an object this seed
# did NOT create and the reason — the prime directive's "report the gap, never
# choose a value" applied to a demo fixture.
OMITTED_FOR_LACK_OF_A_RATIFIED_FIGURE: tuple[str, ...] = (
    "charge code DEPO-R — NOT a missing figure: BR-RAT-020/023 (CONFIRMED, PO "
    "Q&A R1 D6 + R3) move deposits to `plan_deposit_rules` as a fixed $ per "
    "consumer category, PLAN-level, and explicitly SUPERSEDE the prototype's "
    "single DEPO-R checkbox — so a platform-wide DEPO-R amount would encode a "
    "model the PO already replaced. The fixture ships the code and its "
    "`charge_type` (refundable) and no amount, deliberately.",
    "Small Commercial electric (TOU on $0.19 / mid $0.12 / off $0.075 + demand "
    "$9.50/kW) and the Residential mid-peak $0.14 — the workbook states the "
    "PRICES but no window boundaries anywhere, and a TOU version cannot be "
    "stored without them (BR-RAT-033 coverage). Plan COM-SM is water-only.",
    "plan deposit rules ($150 residential / $400 commercial / $1,200 industrial, "
    "workbook §1) — plan_deposit_rules needs an account_type_id and account "
    "types are a W2 customers table that does not exist yet.",
    "sewer / trash / gas / broadband rate schedules (workbook §1 prices them) — "
    "those services are not enabled for this tenant, and BR-RAT-024 forbids a "
    "schedule on a service the tenant has not enabled.",
    "trash is DECLARED unmetered and billed per cart (BR-RAT-081 / BR-RAT-090) "
    "and is deliberately NOT enabled: switching a seeded tenant's service on "
    "after the fixture has run is DEF-1250 / DEF-2490's work in "
    "apps/rating/sample_data.py. The declaration is stored and inert until then "
    "— unmetered_service_codes() reads enabled services only — so the ruled "
    "3 x $15.00 = $45.00 walks the moment trash is switched on, with nobody "
    "editing a database row.",
    "GL account mappings on charges, plan services and taxes — ledger_accounts "
    "is a W5 table; the columns stay NULL rather than pointing at a made-up id.",
)


class Command(BaseCommand):
    help = (
        "Seed the Brazos Bend demo fixture tenant through the real provisioning, "
        "rating, metering and assets services (demo/staging post-migrate step — "
        "NEVER prod). Idempotent: a replay leaves every count unchanged "
        "(BR-TEN-010 posture). Use --check for a write-free readiness report. "
        "The R1 gate's additional blank tenant is provisioned at release time via "
        "the real signup flow (S110–S114), not seeded here."
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        #: CR-029 RC-W0-T1 — area codes the fixture names that this tenant does
        #: not hold. Per-INSTANCE, never a class attribute: Django builds one
        #: Command per run, and a shared mutable would carry one tenant's gap
        #: into the next run's report.
        self._area_gaps: set[str] = set()

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--check",
            action="store_true",
            help="Report seeding readiness (DB vendor, required lanes/seams, fixture "
            "files) without writing anything. Always exits 0.",
        )
        parser.add_argument(
            "--tenant",
            metavar="SUBDOMAIN",
            default=None,
            help="Seed/BACKFILL REFERENCE DATA ONLY into a tenant that already exists, "
            "named by its subdomain. Provisions nothing, creates no owner, writes no "
            "demo records and touches no money. This is the path for an operator who "
            "signed up before a reference list existed — without it, a live tenant "
            "could never be filled. Idempotent: a replay writes nothing.",
        )
        parser.add_argument(
            "--allow-empty-reference-lists",
            action="store_true",
            help="Do not exit non-zero when a reference list is EMPTY with no recorded "
            "reason. Escape hatch for a deliberately partial environment — naming it on "
            "the command line is the point (DEF-016: the unsafe option is the one you type).",
        )

    # ── pre-flight probes (honest, read-only) ───────────────────────────────
    def _probe(self) -> dict[str, Any]:
        # Read-only peek at the BE-03 sink registration; the write path itself
        # enforces rule 7 (write_row raises AuditWriteError when unregistered).
        audit_sink = getattr(core_audit, "_sink", None) is not None
        return {
            "settings_module": getattr(django_settings, "SETTINGS_MODULE", None) or "?",
            "db_vendor": connection.vendor,
            "postgres": connection.vendor == "postgresql",
            # Resolved at call time (seam pattern): the moment the identity lane
            # lands provision_owner/owner_email_for, these flip to wired.
            "identity_provision_owner": seams.resolve("identity", "provision_owner") is not None,
            "identity_owner_email_for": seams.resolve("identity", "owner_email_for") is not None,
            "audit_sink": audit_sink,
            "lookup_fixture": services.FIXTURE_PATH.exists(),
        }

    def _blockers(self, probe: dict[str, Any]) -> list[str]:
        blockers: list[str] = []
        if not probe["postgres"]:
            blockers.append(
                f"database vendor is '{probe['db_vendor']}' — tenant context is a "
                "Postgres GUC (core/tenancy.py set_config); seeding is Postgres-only. "
                "Point DATABASE_URL at the compose postgres:16 service."
            )
        if not (probe["identity_provision_owner"] and probe["identity_owner_email_for"]):
            blockers.append(
                "identity seam not wired (apps.identity.services.provision_owner / "
                "owner_email_for — contract in apps/tenancy/seams.py). Provisioning "
                "refuses without it: an owner-less tenant must not exist (BR-TEN-001). "
                "Owner-user step honestly NOT skippable — the whole tenant waits."
            )
        if not probe["audit_sink"]:
            blockers.append(
                "no BE-03 audit sink registered (apps.audit store lane not landed — "
                "core/audit.py) — every provisioning/settings write must land its "
                "audit row (CLAUDE.md rule 7), so seeding would fail mid-flight. "
                "Refused up front instead."
            )
        if not probe["lookup_fixture"]:
            blockers.append(f"lookup fixture missing: {services.FIXTURE_PATH}")
        return blockers

    def _report(self, probe: dict[str, Any], blockers: list[str]) -> None:
        yes = self.style.SUCCESS("wired")
        no = self.style.WARNING("NOT wired")
        self.stdout.write(f"settings module .......... {probe['settings_module']}")
        self.stdout.write(f"database vendor .......... {probe['db_vendor']}")
        self.stdout.write(
            f"identity provision_owner . {yes if probe['identity_provision_owner'] else no}"
        )
        self.stdout.write(f"BE-03 audit sink ......... {yes if probe['audit_sink'] else no}")
        self.stdout.write(
            f"lookup fixture ........... {'present' if probe['lookup_fixture'] else 'MISSING'}"
        )
        try:
            has_growth = models.SubscriptionPlan.objects.filter(code="growth").exists()
            self.stdout.write(f"plan catalog (growth) .... {'present' if has_growth else 'absent'}")
        except DatabaseError as exc:  # e.g. tables not migrated / sqlite :memory:
            self.stdout.write(
                f"plan catalog (growth) .... unavailable ({type(exc).__name__} — run migrate)"
            )
        # DEF-026: the guard is per PATH, so the report says which paths this
        # host allows rather than leaving the operator to discover it by
        # running the wrong one.
        if self._under_production_settings(probe):
            self.stdout.write(
                self.style.WARNING(
                    "production settings ...... demo-fixture seeding REFUSED here "
                    "(it mints a tenant with a published owner password); "
                    "`--tenant <subdomain>` reference-data backfill RUNS here "
                    "(BR-TEN-064 · DEF-026)"
                )
            )
        for blocker in blockers:
            self.stdout.write(self.style.WARNING(f"BLOCKER: {blocker}"))

    # ── platform catalog bootstrap ──────────────────────────────────────────
    def _ensure_plans(self) -> None:
        """REPORT the platform SKU catalog; do not build it.

        AMENDED 2026-08-10 (deploy-blocker lane, 09-infra/02 §10.3). This used
        to be the ONLY writer of `subscription_plans` anywhere in the repo — and
        it creates one plan and refuses to run under production settings, so a
        real deployment started with an empty catalog and every signup failed
        with `signup.plan_unknown`. That is not a demo-fixture problem, so it is
        no longer solved here: `apps/tenancy/migrations/0005_seed_subscription_plans.py`
        seeds all three ratified SKUs at migrate time, before any tenant exists.
        The earlier note that "starter/scale have no signed values" is withdrawn
        — they are ratified in A10, A13 (2026-08-07 addendum), A1 §S112 and the
        B2 column comment; the migration cites all four.

        What is left here is a check. A demo seed that silently created its own
        catalog would hide exactly the failure this command is meant to surface."""
        present = sorted(models.SubscriptionPlan.objects.values_list("code", flat=True))
        if GROWTH_PLAN["code"] in present:
            self.stdout.write(f"plan catalog: {', '.join(present)} (seeded by tenancy 0005)")
            return
        raise CommandError(
            "subscription_plans has no 'growth' row — the demo tenant's signed plan "
            f"(present: {', '.join(present) or 'none'}). Run `manage.py migrate` first: "
            "the catalog is seeded by apps/tenancy/migrations/0005_seed_subscription_plans.py."
        )

    # ── W1 seeding, module by module, all through the real services ─────────
    def _declare_service_measurement(self, actor: Any) -> int:
        """BR-RAT-081 + r6.4: say which services this utility does not meter.

        Through `services.update_tenant_service` — the same audited call the S8
        screen makes — so the fixture cannot reach a column the product cannot.
        That is the whole shape of `DEF-2310`: a fixture that wrote the row
        directly would have hidden the missing writer for another eight days.

        Idempotent (BR-TEN-010 posture): the declaration is compared against
        what `service_row` already answers and an unchanged service is not
        written at all — so a replay writes no row and no audit entry.

        **Runs BEFORE the schedules**, because `_trash_uom()` reads the declared
        billed unit when it builds one.
        """
        written = 0
        for entry in SERVICE_MEASUREMENT:
            code = str(entry["service"])
            changes = {key: value for key, value in entry.items() if key != "service"}
            if not models.TenantService.objects.filter(
                tenant_id=core_tenancy.current_tenant_id(), service__code=code
            ).exists():
                # A tenant provisioned before New mandate 4 carries a row only
                # for the services it chose at signup. Say which and why rather
                # than crash a seed over it (DEF-016's posture), and never
                # create the row here — `_apply_service_toggle` owns that door.
                self.stdout.write(
                    self.style.WARNING(
                        f"  SKIPPED measurement declaration for '{code}': this tenant has no "
                        "tenant_services row for it (provisioned before New mandate 4)."
                    )
                )
                continue
            current = selectors.service_row(code)
            if all(current.get(key) == value for key, value in changes.items()):
                continue
            services.update_tenant_service(actor, code, changes)
            written += 1
        return written

    def _seed_charges(self, actor: Any) -> int:
        """S12 charge codes via apps.rating.services.create_charge — and, since
        DEF-016 wired rating's PROVISIONING seam, create-or-COMPLETE.

        Provisioning now seeds LATE/CONN/DISC/NSF from the same [F] fixture, so
        by the time this runs those four already exist carrying their fixture
        money. What the platform seed cannot carry is what the fixture does not
        state: `charge_type` (the S12 four-card classification) and LATE's
        [W] WE-15(f) `waivable` flag. Rather than skip the row and lose them —
        or overwrite a value the tenant may have set — this fills ONLY fields
        that are still empty, through rating's own audited `update_charge`.

        Idempotent (BR-TEN-010 posture): the second run finds nothing empty, so
        it calls nothing and writes nothing. Money fields are compared, never
        recomputed; no figure here is new (see the CHARGE_CODES block).
        """
        from apps.rating import selectors as rating_selectors
        from apps.rating import services as rating_services

        existing = {row["code"]: row for row in rating_selectors.charge_list(ListParams(per=1000))}
        created = 0
        for entry in CHARGE_CODES:
            row = existing.get(entry["code"])
            if row is None:
                rating_services.create_charge(
                    actor, {**entry, "effective_from": PRICE_HISTORY_EPOCH.isoformat()}
                )
                created += 1
                continue
            # Fill-the-blanks only: a field the row already answers is left
            # alone (BR-TEN-012 — a seeded row a tenant may have touched is
            # never overwritten by a fixture).
            fill = {
                field: value
                for field, value in entry.items()
                if field not in ("code", "name") and not row.get(field)
            }
            if "amount_rule" in fill:
                # rating's own validator requires the rule's figures alongside
                # it (flat⇒amount, percent⇒percent, +minimum⇒min_amount), so a
                # rule never travels without them.
                fill.update(
                    {
                        field: entry[field]
                        for field in ("amount", "percent", "min_amount")
                        if field in entry
                    }
                )
            # ── DEF-TEN-5343 · A NULL AMOUNT BESIDE A PER-SIZE TABLE IS NOT A BLANK ──
            # Since DEF-6440 (2.219.7) provisioning prices a base code PER SIZE
            # and omits the scalar ON PURPOSE: CR-013 part 2 gives a code ONE
            # basis, and rating's `_validate_charge` refuses a scalar beside a
            # table (`rating.charges.amount_and_size_table`). The table IS the
            # amount, and its smallest size reproduces this fixture's figure
            # exactly, so there is nothing here to complete. Reading that NULL
            # as a blank sent the scalar anyway and killed every fresh seed at
            # this step from 2026-09-07 to 2026-09-15 — before taxes, plans,
            # premises, cycles, assets or reads existed.
            if row.get("size_amounts"):
                fill.pop("amount", None)
            if fill:
                # CR-156-BRC10 — a filled price is the fixture's, and it has
                # always applied: dated from the epoch like every seeded row.
                fill["effective_from"] = PRICE_HISTORY_EPOCH.isoformat()
                rating_services.update_charge(actor, row["id"], fill)
        return created

    def _seed_taxes(self, actor: Any) -> int:
        """S13 taxes + their tenant jurisdictions via create_tax (BR-TEN-037:
        jurisdictions are tenant-entered).

        The jurisdiction is looked up by NAME through rating's own selector
        BEFORE the inline dict is used: `create_tax` creates a new jurisdiction
        for every inline payload it is given, so once provisioning seeds the
        `tax_jurisdictions` list (DEF-016) an inline dict here would mint a
        SECOND 'Texas State'. Natural-key lookup first is the same BR-TEN-010
        posture the rest of this command already follows.

        ⚠ **THE SKIP IS ON THE SET, NOT ON THE NAME — DEF-247, 2026-08-18, and
        this is DEF-166 arriving a second time through the mirror ordering.**
        It used to read `if entry["name"] in existing: continue`, which is the
        exact shape DEF-166 fixed in `rating.sample_data.seed_sample_taxes` on
        2026-08-16. That fix corrected ONE of the two functions carrying the
        bug. If the sample taxes seed FIRST, this tenant holds `State water tax`
        (6.25%) and `City utility tax` (2%); neither name matches `Texas State`
        or `Local`, so this loop created both **beside** them — four percent
        rules on two jurisdictions, and every bill taxed at **16.5% where the
        tenant's own rates say 8.25%**.

        Measured on a booted stack before the fix: GT-1's $100.58 base priced
        tax **16.60** against its frozen **8.30**, and the E2E fixture refused
        to seed rather than boot a bill the money journey must fail on.

        A NAME CHECK CANNOT EXPRESS THE RULE. The rule is BR-TEN-012's — a
        tenant that has priced its own taxes is not given more by a fixture —
        and that is a statement about the SET, not about matching spellings.
        Two seeders naming the same rate differently is not an edge case; it is
        the normal case, because neither one knows the other's vocabulary.
        """
        from apps.rating import selectors as rating_selectors
        from apps.rating import services as rating_services

        existing = {row["name"] for row in rating_selectors.tax_list(ListParams(per=1000))}
        if existing:
            return 0  # DEF-247: any tax rule at all means this command adds none
        jurisdictions = {row["name"]: row["id"] for row in rating_selectors.jurisdiction_list()}
        created = 0
        for entry in TAX_RULES:
            if entry["name"] in existing:
                continue
            payload = {k: v for k, v in entry.items() if k != "jurisdiction"}
            known = jurisdictions.get(entry["jurisdiction"]["name"])
            payload["jurisdiction"] = known if known else dict(entry["jurisdiction"])
            result = rating_services.create_tax(actor, payload)
            if not known:
                jurisdictions[entry["jurisdiction"]["name"]] = result["jurisdiction"]["id"]
            created += 1
        return created

    @staticmethod
    def _assert_base_codes_state_the_plans_bases() -> None:
        """`DEF-2823` — every base this fixture's PLANS state must also be
        stated by an `is_base` CHARGE CODE, at the same figure.

        ⚠ **THIS REPLACES `_version_base_by_schedule`, WHICH WROTE THE RETIRED
        COLUMN.** That helper derived `tariff_versions.base_charge` from
        `RATE_PLANS` so R3 would stop refusing (`DEF-2799`, the same morning).
        It worked and it was the wrong shape: `BR-RAT-088` retired that column
        and `RateScheduleWizard` removed its control, so **a real utility
        cannot write it at all** and the fixture was configured in a way no
        customer could copy. The base now lives on the charge code, which is
        where the ruling puts it and what the wizard can actually write.

        **WHY A CHECK AND NOT A DERIVATION.** The old helper DERIVED the second
        figure so the two could not drift. A charge code cannot be derived —
        it carries a class scope (`BR-RAT-108`) and, one day, a per-size table,
        and deriving those from a plan row would invent narrowing nobody typed.
        So the two figures are BOTH authored and this asserts they agree, which
        is the same guarantee reached the other way round.

        **AND THE FAILURE IT CATCHES IS A REAL ONE, NOT A HYPOTHETICAL.** Until
        2026-08-31 this fixture stated `$180.00` for `IND` electric on the plan
        and `$12.00` on the only `is_base` electric code — a **`$168.00`** gap
        that nothing could see, because the live path read the plan and the
        ruled chain has no production caller. With `gather` reading the code,
        that pair now REFUSES the bill by name; this stops the SEED instead, at
        the point where it is one edit to fix.

        Pure: it reads two module constants and asks the database nothing, so
        it cannot be defeated by seeding order.
        """
        by_service_class: dict[tuple[str, str | None], set[str]] = {}
        for code in CHARGE_CODES:
            if not code.get("is_base"):
                continue
            classes = code.get("applies_to_customer_classes") or [None]
            for klass in classes:
                key = (str(code["service"]), klass)
                by_service_class.setdefault(key, set()).add(str(code["amount"]))
        for plan in RATE_PLANS:
            for service in plan["services"]:
                base = service.get("base_charge")
                if base is None:
                    continue
                service_code = str(service["service"])
                stated = {
                    amount
                    for (svc, _klass), amounts in by_service_class.items()
                    if svc == service_code
                    for amount in amounts
                }
                if not stated:
                    raise CommandError(
                        f"plan {plan['code']!r} states a base charge of {base} for "
                        f"{service_code!r} and NO charge code in CHARGE_CODES declares "
                        f"itself the base for that service. BR-RAT-088 makes the charge "
                        "code the one source, so this base would reach no bill at all — "
                        "every line individually correct and the total short by the base."
                    )
                if Decimal(str(base)) not in {Decimal(amount) for amount in stated}:
                    raise CommandError(
                        f"plan {plan['code']!r} states a base charge of {base} for "
                        f"{service_code!r} and no `is_base` charge code states that "
                        f"figure — the codes say {', '.join(sorted(stated))}. "
                        "BR-RAT-088 makes the charge code the source and the plan the "
                        "DISPLAY. Since DEF-BIL-7170 (PO 2026-09-28) the bill is produced "
                        "from the charge code and the plan's figure is not read at all, so "
                        "this disagreement no longer stops a bill — it puts a number on "
                        "the plan's screen that no customer is ever charged. Move the "
                        "plan's figure onto the "
                        "charge code, scoped by customer class where one service carries "
                        "two amounts (BR-RAT-108)."
                    )

    def _seed_schedules(self, actor: Any) -> tuple[int, dict[str, str]]:
        """S11 rate schedules via create_rate_schedule. Each carries
        `effective_from` + a complete structure, so its first version is
        written ACTIVE and it is pickable by the plan builder (BR-RAT-031)."""
        from apps.rating import selectors as rating_selectors
        from apps.rating import services as rating_services
        from apps.rating.sample_data import sample_size_rows

        index = {
            card["name"]: card["id"]
            for card in rating_selectors.schedule_list(ListParams(per=1000))
        }
        self._assert_base_codes_state_the_plans_bases()
        code_ids = {
            row["code"]: row["id"] for row in rating_selectors.charge_list(ListParams(per=1000))
        }
        created = 0
        for entry in RATE_SCHEDULES:
            if entry["name"] in index:
                continue
            payload = dict(entry)
            # ── DEF-2799 · WHICH SIZES THIS SCHEDULE SERVES (BR-RAT-120) ────
            # `size_rows` is R3's whole input since `DEF-2823`: R3 asks *does
            # this schedule serve this size* and R4 states the amount.
            #
            # ⚠ **AND `base_charge` IS DELIBERATELY NOT WRITTEN, WHICH REVERSES
            # THIS MORNING'S PATCH (`DEF-2823`, 2026-08-31).** The DEF-2799
            # lane wrote `tariff_versions.base_charge` here so R3's blank-base
            # refusal would stop firing. It worked and it was exactly the wrong
            # shape: `BR-RAT-088` RETIRED that column and
            # `RateScheduleWizard.tsx` removed its control in the same ruling
            # (*"CARRIED, NEVER EDITED … no control, no editing, no loss"*), so
            # **a real utility cannot write that field at all** and the fixture
            # was configured in a way no customer could copy. The base now
            # lives where the ruling puts it — on the `is_base` CHARGE CODE
            # (`CHARGE_CODES` above) — and R3 resolves from the size axis
            # alone. Neither fact can move a bill: see the note above
            # RATE_SCHEDULES and `tests/test_def2799_seeded_size_axis.py`.
            payload["size_rows"] = sample_size_rows(entry["service"])
            # ── DEF-RAT-8737 · THE MINIMUM IS THE SIZE'S (PO 2026-10-01) ────
            # *"A · Minimum per size - this is correct"*. The version carries
            # no minimum any more (the API refuses one by name) and billing
            # reads the size row's, so WE-3's `$15.00` is authored once in
            # `RATE_SCHEDULES` and written onto EVERY size the schedule serves
            # — which bills exactly what the version figure billed before.
            minimum = payload.pop("minimum_bill", None)
            if minimum is not None:
                payload["size_rows"] = [
                    {**row, "minimum_bill": minimum} for row in payload["size_rows"]
                ]
            # ── DEF-RAT-9842 · THE SCHEDULE NAMES ITS BASE CODE ─────────────
            # PO ruling 2026-10-06: a schedule naming no base code bills a
            # `$0.00` base. Each of these four is bound by ONE plan of ONE
            # class, so it names that class's code — the code the retired pool
            # picked — and every demo bill keeps its figure.
            base_code = payload.pop("base_code")
            payload["base_charge_code"] = str(code_ids[base_code])
            result = rating_services.create_rate_schedule(actor, payload)
            index[entry["name"]] = result["id"]
            created += 1
        return created, index

    def _seed_plans(self, actor: Any, schedules: dict[str, str]) -> tuple[int, int]:
        """S10 plan bundles via create_plan + publish_plan. A plan lands as a
        DRAFT and is published explicitly (BR-RAT-030); publishing enforces D2
        completeness (every ticked service needs its schedule)."""
        from apps.rating import selectors as rating_selectors
        from apps.rating import services as rating_services

        existing = {row["code"]: row for row in rating_selectors.plan_list(ListParams(per=1000))}
        jurisdictions = [row["id"] for row in rating_selectors.jurisdiction_list()]
        created = published = 0
        for entry in RATE_PLANS:
            row = existing.get(entry["code"])
            if row is None:
                payload: dict[str, Any] = {
                    "name": entry["name"],
                    "code": entry["code"],
                    "description": entry["description"],
                    "services": [
                        {
                            k: v
                            for k, v in {
                                "service": service["service"],
                                "base_charge": service["base_charge"],
                                "tariff": schedules.get(service["schedule"]),
                            }.items()
                            if v is not None
                        }
                        for service in entry["services"]
                    ],
                    # D7 attachments: no amount_override — the charge code's own
                    # ratified amount applies. taxable stays False (B4.2: fees
                    # are never in the tax base).
                    "charge_rules": [
                        {"charge": code, "recurrence": "event", "taxable": False}
                        for code in entry["charges"]
                    ],
                    # D8: rate_override NULL = the jurisdiction's own rate.
                    "tax_rules": [{"jurisdiction": jid} for jid in jurisdictions],
                    # ── BR-RAT-890 (DEF-494) · A PLAN STATES WHEN IT STARTS ──
                    # PO ruling 2026-08-28: `publish_plan` refuses an undated
                    # plan, so without this line `_seed_plans` could no longer
                    # publish anything and the demo tenant would come up with
                    # three unassignable drafts.
                    # SCHEDULE_EFFECTIVE_FROM, the SAME date this fixture's
                    # rate-schedule versions carry: a plan that starts before
                    # its own prices do would be in force with nothing to
                    # price, and one that starts after them leaves a gap where
                    # the ruled path refuses. It is also exactly what
                    # `rating/0024` computes for a tenant seeded before today.
                    "effective_from": SCHEDULE_EFFECTIVE_FROM,
                }
                row = rating_services.create_plan(actor, payload)
                created += 1
            if row["status"] == "draft":
                # BR-RAT-890 (DEF-494): a replay over a tenant that already
                # holds this plan as an UNDATED draft — created before the
                # ruling, or left half-set up. `publish_plan` refuses it, so
                # without this the seed aborts on that tenant and never
                # recovers. A draft needs no BR-RAT-037 reason.
                if not row.get("effective_from"):
                    rating_services.update_plan(
                        actor, row["id"], {"effective_from": SCHEDULE_EFFECTIVE_FROM}
                    )
                rating_services.publish_plan(actor, row["id"])
                published += 1
        return created, published

    def _available_area_codes(self) -> set[str]:
        """The area codes this tenant actually holds, upper-cased for matching.

        CR-029 RC-W0-T1. Read through tenancy's own ORM (this IS the tenancy
        module). A seeded area can legitimately be absent — BR-TEN-036 protects
        a seeded row from DELETION, not from a tenant that never received it
        because the S111 toggle was off — so a missing area drops the tag and is
        REPORTED rather than raising. Refusing the whole premises block over a
        district would turn a cosmetic gap into "the demo utility is empty".
        """
        from apps.tenancy import models as tenancy_models

        return {
            str(code).upper()
            for code in tenancy_models.Area.objects.filter(
                tenant_id=core_tenancy.current_tenant_id()
            ).values_list("code", flat=True)
        }

    def _with_area(self, payload: dict[str, Any], available: set[str]) -> dict[str, Any]:
        """`payload` minus an `area_code` this tenant does not hold."""
        code = payload.get("area_code")
        if code is None or str(code).upper() in available:
            return payload
        self._area_gaps.add(str(code))
        return {k: v for k, v in payload.items() if k != "area_code"}

    def _seed_premises_and_units(self, actor: Any) -> tuple[int, int, dict[str, Any]]:
        """S16 guided add via create_premises (which creates its units in the
        SAME transaction through the wizard's `units` step).

        CR-029 RC-W0-T1 added the `area_code` tag (see the PREMISES block). A
        premises that ALREADY EXISTS and carries no area is backfilled through
        `update_premises` — the seed's create-or-COMPLETE posture, the same one
        `_seed_charges` takes — because a tenant seeded before this change would
        otherwise keep an untagged fixture and the SET-06.2 area filter would
        still return zero rows there. The backfill runs BR-MET-083's cascade,
        which is the ruled behaviour of tagging a premises and is exactly what
        W0-T1 exists to make exercisable.
        """
        from apps.metering import selectors as metering_selectors
        from apps.metering import services as metering_services

        by_address = {row.address_line: row for row in metering_selectors.premises_list()}
        available_areas = self._available_area_codes()
        premises_created = units_created = 0
        index: dict[str, Any] = {"premises": {}, "units": {}}

        for entry in PREMISES:
            address = entry["address_line"]
            row = by_address.get(address)
            # `plan` is NOT part of the create payload and is stripped here on
            # purpose (CR-054 W0 task 1). A plan assignment is a DATED event with
            # its own append-only history row (`assign_unit_plan` →
            # BR-CUS-013/BR-MET-041), so it is applied afterwards by
            # `_assign_unit_plans`, which can also repair a unit created before
            # the plans existed — the create path cannot.
            unit_payloads = [
                {
                    **{k: v for k, v in unit.items() if k != "plan"},
                    "services": list(entry["services_available"]),
                }
                for unit in entry["units"]
            ]
            if row is None:
                payload = {k: v for k, v in entry.items() if k != "units"}
                payload = self._with_area(payload, available_areas)
                payload["units"] = unit_payloads
                # BR-MET-401 / DEF-650 — the owner is REQUIRED at creation (PO
                # 2026-08-27). Resolved through metering's own sample helper, so
                # this command and `sample_data` cannot disagree about which
                # party a demo address belongs to — the second copy of a rule is
                # how two seeders come to seed two different estates.
                from apps.metering import sample_data as metering_sample_data

                payload["owner_id"] = metering_sample_data._sample_owner_id(
                    actor, payload.get("owner_manager")
                )
                result = metering_services.create_premises(actor, payload)
                premises_created += 1
                units_created += len(result["units"])
                index["premises"][address] = result["id"]
                for unit in result["units"]:
                    index["units"][(address, unit["label"])] = unit["id"]
                continue

            index["premises"][address] = str(row.id)
            area_code = entry.get("area_code")
            if row.area_id is None and area_code and str(area_code).upper() in available_areas:
                metering_services.update_premises(actor, str(row.id), {"area_code": area_code})
            known = {
                unit.label: unit
                for unit in metering_selectors.units_list(filters={"premises_id": str(row.id)})
            }
            for unit_payload in unit_payloads:
                unit = known.get(unit_payload["label"])
                if unit is not None:
                    index["units"][(address, unit.label)] = str(unit.id)
                    continue
                result = metering_services.create_unit(
                    actor, {**unit_payload, "premises_id": str(row.id)}
                )
                units_created += 1
                index["units"][(address, unit_payload["label"])] = result["id"]
        return premises_created, units_created, index

    def _seed_cycles_and_routes(self, actor: Any, index: dict[str, Any]) -> tuple[int, int]:
        """S27 cycles then S26 routes — a route names its cycle (BR-MET-010),
        and its membership stamps route/cycle onto the units' service points
        (BR-MET-033).

        CR-029 RC-W0-T1: each route now sends its own `service_code` and
        `area_code` (D7, closing B17 §5's *"seeded routes carry no
        service/area"*), and each cycle sends the three ruled schedule fields
        (B17 §2) instead of the legacy calendar dates D2 supersedes.
        """
        from apps.metering import selectors as metering_selectors
        from apps.metering import services as metering_services

        available_areas = self._available_area_codes()
        # ⚠ **IDEMPOTENT ON THE NAME, NOT ON THE CODE — CR-029 RC-W5-T1.**
        #
        # These constants carry a CODE, and until W5-T1 that code was reliably
        # free: the sample-records plant (`apps/metering/sample_data.py`, which
        # provisioning runs BEFORE this command) minted `SCW-M` / `SCW-R1`, a
        # second naming grammar that D5 replaced. Now that the plant allocates
        # from the same `CY-`/`RT-` series this fixture names, it takes `CY-001`
        # and `RT-001` first — and a skip keyed on the CODE silently DROPPED the
        # colliding definition. Measured on a fresh seed: the demo tenant lost
        # *"Residential monthly"* and *"Katy North — water + electric"*
        # altogether, six cycles became five, and nothing said so.
        #
        # So the key is the NAME — what the fixture is actually FOR — and the
        # code is a preference: taken by the plant, this asks the series for the
        # next one. Every definition lands, every code stays inside D5's
        # grammar, and a replay still writes nothing.
        by_code = {row["code"]: row["id"] for row in metering_selectors.cycles_list()}
        by_name = {(row.get("name") or ""): row["id"] for row in metering_selectors.cycles_list()}
        cycles: dict[str, Any] = {}
        cycles_created = 0
        for entry in CYCLES:
            existing = by_name.get(entry["name"])
            if existing is not None:
                cycles[entry["code"]] = existing
                continue
            payload = dict(entry)
            if payload["code"] in by_code:
                # Somebody else holds this code. Drop it and let the series
                # allocate — `create_cycle` does exactly that for the wizard's
                # untouched pre-fill (BR-MET-077).
                payload.pop("code")
            result = metering_services.create_cycle(actor, payload)
            cycles[entry["code"]] = result["id"]
            by_code[result["code"]] = result["id"]
            cycles_created += 1

        route_codes = {row["code"] for row in metering_selectors.routes_list()}
        route_names = {(row.get("name") or "") for row in metering_selectors.routes_list()}
        routes_created = 0
        for entry in ROUTES:
            if entry.get("name") in route_names:
                continue
            payload = {
                k: v for k, v in entry.items() if k not in ("cycle", "premises", "exclusions")
            }
            if payload.get("code") in route_codes:
                # Taken — by the sample plant, or by an EARLIER entry in this
                # very loop that had its own code popped and was allocated this
                # one. The set is updated below for exactly that reason: a
                # snapshot taken before the loop cannot see the codes the loop
                # itself consumes, and the first fresh seed after W5-T1 died on
                # `metering.route.code_duplicate` proving it.
                payload.pop("code")
            payload["service_codes"] = list(entry["service_codes"])
            payload = self._with_area(payload, available_areas)
            payload["cycle_id"] = cycles[entry["cycle"]]
            payload["premises_ids"] = [
                index["premises"][address]
                for address in entry["premises"]
                if address in index["premises"]
            ]
            created = metering_services.create_route(actor, payload)
            route_codes.add(created["code"])
            route_names.add(entry.get("name") or "")
            routes_created += 1
        return cycles_created, routes_created

    def _seed_assets(self, actor: Any, index: dict[str, Any]) -> int:
        """S51 add-asset via apps.assets.services.create_asset. With `unit_id`
        the service creates the service point through the metering seam and
        opens the first assignment (BR-AST-011 assign-on-create); without one
        the asset lands in inventory.

        ⚠ **CREATE-or-COMPLETE for `net_metering`, hard-won law 4 in its data
        form.** Adding `net_metering: True` to the ASSETS table above reaches no
        tenant that already carries M-7302, and a fixture edit that only lands
        on brand-new tenants is a fixture edit that does not land. So an asset
        this table declares net-metered and the database does not is corrected
        through `update_asset` — BR-AST-012's spec-field edit, audited
        before/after — rather than left for the next reader to discover as a
        demo whose export register is expected by nothing.
        """
        from apps.assets import selectors as asset_selectors
        from apps.assets import services as asset_services

        existing = {
            asset.asset_no: asset for asset in asset_selectors.asset_list(filters={"status": "all"})
        }
        created = 0
        for entry in ASSETS:
            row = existing.get(entry["asset_no"])
            if row is not None:
                if entry.get("net_metering") and not row.net_metering:
                    asset_services.update_asset(actor, str(row.id), {"net_metering": True})
                continue
            payload = {k: v for k, v in entry.items() if k not in ("on", "uom") and v is not None}
            if entry.get("uom"):
                # CLAUDE.md rule 3 — the asset's own explicit UoM column.
                payload["unit"] = entry["uom"]
            placement = entry.get("on")
            if placement is not None:
                payload["unit_id"] = index["units"][placement]
                payload["install_date"] = ASSET_INSTALL_DATE
            asset_services.create_asset(actor, payload)
            created += 1
        return created

    def _assign_unit_plans(self, actor: Any, index: dict[str, Any]) -> int:
        """Put every seeded unit on the plan its `PREMISES` entry names.

        ⚠ **THE DEMO TENANT HAD NO UNIT ON ANY PLAN AT ALL** — measured
        2026-08-30, `select count(*) from units where rate_plan_id is null`
        counted all ten of this fixture's own units — and two separate things
        were broken by it, neither loudly:

          1. `create_account` REFUSES to activate an account on a planless unit
             (BR-CUS-014 / BR-MET-040, *"the account derives its plan from the
             unit"*), so nothing could ever be connected at a demo address;
          2. `completeness.PlanRegisterResolver` answers
             `REGISTERS_ABSENT_NO_PLAN` for every meter on a planless unit, so
             `plan_register_completeness` reports `not_evaluated` — the rule is
             computed, stored and says nothing, on every reading, for ever.

        Which plan a unit is on is FIXTURE AUTHORSHIP and is declared per unit
        in `PREMISES` rather than derived from `unit_type` here, because the
        Industrial premises' unit is a `commercial` type on the `IND` plan and a
        derivation would have to special-case it — a rule nobody wrote, buried
        in a seeder. It is recorded in the decision log.

        Idempotent (BR-TEN-010): a unit that already carries a plan is left
        exactly as it is, including one an operator moved by hand.
        `effective_from` is `SCHEDULE_EFFECTIVE_FROM` — the same date the plans
        and their rate schedules start, because a unit on a plan before that
        plan has prices is a unit nothing can bill.
        """
        from apps.metering import selectors as metering_selectors
        from apps.metering import services as metering_services
        from apps.rating import selectors as rating_selectors

        plans = {row["code"]: row["id"] for row in rating_selectors.plan_list(ListParams(per=1000))}
        live = {str(unit.id): unit for unit in metering_selectors.units_list()}
        assigned = 0
        for entry in PREMISES:
            address = entry["address_line"]
            for unit in entry["units"]:
                code = unit.get("plan")
                unit_id = index["units"].get((address, unit["label"]))
                if not code or unit_id is None or code not in plans:
                    continue
                row = live.get(str(unit_id))
                if row is None or row.rate_plan_id is not None:
                    continue
                metering_services.assign_unit_plan(
                    actor,
                    str(unit_id),
                    {
                        "plan_id": plans[code],
                        "effective_from": SCHEDULE_EFFECTIVE_FROM,
                        "source": "new_connection",
                        "reason": "demo fixture (seed_demo) — the plan this unit's cohort is on",
                    },
                )
                assigned += 1
        return assigned

    def _seed_multi_register_reads(self, actor: Any) -> int:
        """CR-054 W0 task 1 — the TOU, demand, short and net-metered readings,
        through the S28 pipeline a clerk drives by hand and through nothing else.

        `stage_read_batch` → `validate_read_batch` → `set_row_disposition` →
        `commit_read_batch`. **Nothing here writes a `meter_reads` row**, for the
        reason `apps/metering/sample_data.py` already states about its own reads:
        the validation engine is what decides whether a reading is plausible, and
        a fixture that inserted around it would seed reads no clerk could have
        entered — and, worse here, would seed a `demand` row whose consumption
        never went through `register_units.billable_quantity` at all.

        Idempotent (BR-TEN-063), keyed on (asset, read date, channel) — the same
        triple B2 r8's own uniqueness is keyed on — and NOT on the meter: a
        per-meter guard cannot tell *"already seeded"* from *"three of five rows
        landed and two were refused"*, so a partial run could never be completed
        by running the seed again, which is what a replay is for.

        An ERROR row is NOT dispositioned here. BR-MET-015 resolves an error by a
        human's override, reject, field visit or skip, and every one of those is
        a judgment about a real meter; a fixture that auto-overrode its own
        errors would post readings the product had just refused. It raises with
        the reason instead — the `apps/metering/sample_data.py::_post_batch`
        posture, quoted rather than reinvented.
        """
        from apps.metering import selectors as metering_selectors
        from apps.metering import services as metering_services
        from apps.assets import selectors as asset_selectors

        assets = {
            asset.asset_no: asset for asset in asset_selectors.asset_list(filters={"status": "all"})
        }
        # ⚠ **BY NAME, NEVER BY CODE — the RC-W5-T1 trap, and it bit this lane
        # before the comment was written.** `create_cycle` allocates `CY-###`
        # from the number series when the preferred code is taken, and the
        # sample-records plant runs BEFORE this command and takes `CY-001`. On
        # the measured tenant *"Residential monthly"* is `CY-002` and
        # *"Industrial bimonthly"* is `CY-005`; a batch tagged by the constant's
        # `CY-001` was therefore tagged with the SILVER CREEK cycle, and the
        # product said so correctly and twice — `out_of_window` warning
        # (*read 2026-08-01, window 2026-08-14 … 2026-08-14*) and
        # `cycle_membership` warning (*"M-7301 belongs to CY-002, file tagged
        # CY-001"*, BR-MET-122) — on all 24 rows.
        cycles = {(row.get("name") or ""): row["id"] for row in metering_selectors.cycles_list()}
        posted = 0
        for spec in DEMO_CYCLE_READS:
            rows = [row for row in spec["rows"] if self._read_is_absent(row, assets)]
            if not rows:
                continue
            payload: dict[str, Any] = {
                "source_kind": "manual",
                "source_detail": spec["source_detail"],
                # BR-MET-123 — the read METHOD, the tag that travels onto every
                # reading. Each batch names the method its own meters carry.
                "read_method": spec["read_method"],
                "period_month": spec["period_month"],
                "service": spec["service"],
                "file_name": spec["file_name"],
                "rows": [dict(row) for row in rows],
            }
            cycle_id = cycles.get(spec["cycle"])
            if cycle_id is not None:
                # BR-MET-057: the cycle is what gives `out_of_window` a window
                # to judge against. Omitted rather than invented if the cycle is
                # missing — the batch is still lawful, the rule reports itself.
                payload["cycle_id"] = cycle_id
            batch = metering_services.stage_read_batch(actor, payload)
            batch_id = batch["id"]
            metering_services.validate_read_batch(actor, batch_id)
            staged = self._validated_read_rows(batch_id, staged=len(rows), where=spec["file_name"])
            for row in staged:
                if row.get("severity") == "warning" and not row.get("disposition"):
                    # BR-MET-129 (PO 2026-08-26) posts a warned reading WITHOUT
                    # a disposition; the explicit accept stays as PROVENANCE, so
                    # "the seed accepted this flagged read, and why" is a fact an
                    # operator can read off the row.
                    metering_services.set_row_disposition(
                        actor,
                        batch_id,
                        row["row_no"],
                        {
                            "disposition": "accept",
                            "reason": "demo fixture — accepted by seed_demo (CR-054 W0 task 1)",
                        },
                    )
            blocking = [
                row
                for row in self._validated_read_rows(
                    batch_id, staged=len(rows), where=spec["file_name"]
                )
                if row.get("severity") == "error" and not row.get("disposition")
            ]
            if blocking:
                raise CommandError(
                    f"{spec['file_name']} will not post: {len(blocking)} of {len(rows)} row(s) "
                    "failed validation, and BR-MET-015 resolves an error only by a human's "
                    "override, reject, field visit or skip — never by a fixture. First: "
                    + "; ".join(
                        f"row {row.get('row_no')} "
                        f"{row.get('message') or row.get('code') or ''}".strip()
                        for row in blocking[:3]
                    )
                    + ". Usually this means the meters these reads name were never seeded — "
                    "check the assets block above."
                )
            # DEF-MET-8106 — inline: the seed reads these readings back next.
            result = metering_services.commit_read_batch(
                actor, batch_id, {"certified": True}, defer=False
            )
            posted += int(result.get("posted_reads") or 0)
        return posted

    def _read_is_absent(self, row: dict[str, Any], assets: dict[str, Any]) -> bool:
        """True when this exact (meter, date, register) is NOT already committed.

        Read through metering's own published selector rather than its ORM
        (B1 — a module owns its tables), and over lineage HEADS, which is what
        `typed_reads_for_asset` answers.
        """
        from apps.metering import selectors as metering_selectors

        asset = assets.get(row["meter_id"])
        if asset is None:
            # The meter does not exist here — stage the row anyway and let
            # `unknown_meter` say so by name. A seeder that silently dropped it
            # would post a batch that is short and reports success.
            return True
        read_on = row["read_date"]
        return not any(
            head.get("channel") == row["channel"] and str(head.get("read_at") or "")[:10] == read_on
            for head in metering_selectors.typed_reads_for_asset(
                asset.id, period_start=read_on, period_end=read_on
            )
        )

    def _validated_read_rows(self, batch_id: Any, *, staged: int, where: str) -> list[Any]:
        """The batch's rows AFTER validation — from the BATCH, never from
        `validate_read_batch`'s return value.

        ⛔ **DEF-659, and it needs no ruling to land.** `validate_read_batch`
        answers `selectors.read_batch_dict` — id, status, counts, compliance —
        and has never carried a `rows` key, so a consumer reading
        `report.get("rows", [])` iterates an empty list for ever: nothing is
        dispositioned, no blocking row can be found, and the batch still reports
        `posted`. `.get(key, default)` over a same-module contract cannot fail.
        So this reads the published selector and **asserts the count against
        what was staged**, which is the check that survives a future reshaping.
        """
        from apps.metering import selectors as metering_selectors
        from apps.metering import services as metering_services

        # `services._batch_row` + `selectors.read_batch_rows` is EXACTLY the
        # pair `apps/metering/api.py::read_batch_detail` uses to answer the S28
        # review screen — the same door, so this seed sees what a clerk sees.
        # Reaching for the ORM here instead would put a `read_import_batches`
        # query in apps/tenancy, which B1 forbids.
        rows = metering_selectors.read_batch_rows(metering_services._batch_row(batch_id))
        if len(rows) != staged:
            raise CommandError(
                f"{where} staged {staged} row(s) and metering reports {len(rows)} back — the "
                "seed will not disposition, judge or post rows it cannot see. This is the shape "
                "of DEF-659: a consumer reading an empty list where the rows are, "
                "dispositioning nothing, and letting the batch report `posted` over reads that "
                "never landed."
            )
        return rows

    def _apply_route_exclusions(self, actor: Any) -> int:
        """CR-029 RC-W0-T1 — BR-MET-075's meter exclusions, with their reasons.

        **A SEPARATE STEP, AND IT HAS TO BE.** An exclusion names an ASSET, and
        the assets do not exist when the routes are created — the seed's order
        is premises → cycles+routes → assets, because a route's membership is
        premises-shaped and an asset needs the unit to hang off. So the
        exclusion is applied afterwards, through `update_route`, which is the
        same door the SET-06.3 wizard step uses.

        `exclusion_reasons` carries the two words SET-06D's Assets tab renders
        in place (*"MTR-W2262 excluded · premise demolished"*, B17 §6). The
        exclusion is a ROW, never a change to the asset: the master meter keeps
        its premises, its unit, its service point and everything it bills — the
        one thing that changes is which crew sheet it appears on.
        """
        from apps.assets import selectors as asset_selectors
        from apps.metering import selectors as metering_selectors
        from apps.metering import services as metering_services

        by_asset_no = {
            asset.asset_no: str(asset.id)
            for asset in asset_selectors.asset_list(filters={"status": "all"})
        }
        routes = {row["code"]: row for row in metering_selectors.routes_list()}
        applied = 0
        for entry in ROUTES:
            wanted = entry.get("exclusions")
            route = routes.get(entry["code"])
            if not wanted or route is None:
                continue
            asset_ids = [by_asset_no[no] for no in wanted if no in by_asset_no]
            if not asset_ids:
                continue
            reasons = {by_asset_no[no]: reason for no, reason in wanted.items() if no in by_asset_no}
            # `DEF-TEN-8820` — create-or-skip, like every other step: a replay
            # over a route that already holds exactly these exclusions writes
            # nothing and counts nothing (BR-TEN-010), or the closing line says
            # "this run created: 1 meter exclusions" over a tenant it left as
            # it found it.
            if metering_selectors.route_exclusion_reasons(route["id"]) == reasons:
                continue
            metering_services.update_route(
                actor,
                route["id"],
                {"excluded_asset_ids": asset_ids, "exclusion_reasons": reasons},
            )
            applied += len(asset_ids)
        return applied

    # ── live counts (read through each module's selectors) ──────────────────
    def _live_counts(self) -> list[tuple[str, Any]]:
        from apps.assets import selectors as asset_selectors
        from apps.metering import selectors as metering_selectors
        from apps.rating import selectors as rating_selectors

        params = ListParams(per=1000)
        plans = rating_selectors.plan_list(params)
        assets = asset_selectors.asset_list(filters={"status": "all"})
        return [
            ("UoMs", models.Uom.objects.filter(tenant_id=core_tenancy.current_tenant_id()).count()),
            (
                "number series",
                models.NumberSeries.objects.filter(
                    tenant_id=core_tenancy.current_tenant_id()
                ).count(),
            ),
            (
                "enabled services",
                models.TenantService.objects.filter(
                    tenant_id=core_tenancy.current_tenant_id(), enabled=True
                ).count(),
            ),
            ("charge codes", len(rating_selectors.charge_list(params))),
            ("tax jurisdictions", len(rating_selectors.jurisdiction_list())),
            ("taxes", len(rating_selectors.tax_list(params))),
            ("rate schedules", len(rating_selectors.schedule_list(params))),
            ("rate plans", len(plans)),
            ("  of which published", sum(1 for plan in plans if plan["status"] == "published")),
            ("premises", metering_selectors.premises_list().count()),
            ("units", len(metering_selectors.units_list())),
            (
                "  of which on a rate plan",
                sum(1 for u in metering_selectors.units_list() if u.rate_plan_id is not None),
            ),
            ("routes", len(metering_selectors.routes_list())),
            ("billing cycles", len(metering_selectors.cycles_list())),
            ("assets", len(assets)),
            ("  of which meters/sub-meters", sum(1 for a in assets if a.meter_type_id is not None)),
            # CR-054 W0 task 1 — PER REGISTER, because "199 meter reads" is the
            # number that hid the whole finding: every one of them was `total`
            # and nothing on the summary said so.
            ("committed reads", metering_selectors.read_list().count()),
            *[
                (
                    f"  of which {channel}",
                    metering_selectors.read_list(filters={"channel": channel}).count(),
                )
                for channel in ("total", "tou_on", "tou_mid", "tou_off", "demand", "export")
            ],
        ]

    # ── DEF-016: the reference-data honesty report ──────────────────────────
    def _reference_data_report(self, state_code: str | None) -> list[str]:
        """Print 'these reference lists are EMPTY, and why'; return the
        UNEXPLAINED ones. Must be called INSIDE a tenant context.

        This is the surface DEF-016 was missing. The old code wrote one
        WARNING line into a run summary and moved on, so a list nobody could
        seed looked exactly like a list nobody needed. Now every declared list
        is named with its live count, an unseedable one must carry a written
        reason, and one that carries neither rows nor a reason is UNEXPLAINED —
        which the caller turns into a non-zero exit."""
        report = services.reference_data_report()
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("── reference data · every declared list ──"))
        for row in report["lists"]:
            label = f"{row['list']} ({row['owner']})"
            dots = "." * max(1, 40 - len(label))
            if row["state"] == "uncounted":
                count: Any = f"{row['seed_run_count']} at seed time"
            else:
                count = "unwired" if row["count"] is None else row["count"]
            line = f"{label} {dots} {count}"
            if row["state"] == "seeded":
                self.stdout.write(line)
            elif row["state"] == "UNEXPLAINED":
                self.stdout.write(self.style.ERROR(f"{line}   ← UNEXPLAINED"))
            elif row["state"] == "uncounted":
                # Seeded, but nothing here can count it live — say exactly that.
                # Printing "EMPTY" would be false and printing a number would be
                # a claim this process cannot check.
                self.stdout.write(self.style.WARNING(f"{line}   ← SEEDED · NO S8 CARD"))
            else:
                self.stdout.write(self.style.WARNING(f"{line}   ← EMPTY"))
        if report["empty"] or report["unexplained"] or report["uncounted"]:
            self.stdout.write("")
            self.stdout.write("reference lists that are EMPTY or not countable here, and why:")
            for row in report["lists"]:
                if row["reason"]:
                    self.stdout.write(f"  · {row['list']}: {row['reason']}")
        for note in services.reference_seed_omissions(state_code):
            self.stdout.write(
                f"  · {note['list']} entry {note['entry']!r} not created: {note['reason']}"
            )
        return list(report["unexplained"])

    def _refuse_unexplained(self, unexplained: list[str], *, allowed: bool) -> None:
        if not unexplained:
            return
        if allowed:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(unexplained)} UNEXPLAINED empty reference list(s) tolerated because "
                    "--allow-empty-reference-lists was named on the command line."
                )
            )
            return
        raise CommandError(
            "UNEXPLAINED empty reference list(s): "
            + ", ".join(unexplained)
            + ". Either wire the owning module's seed_reference_list seam (BR-TEN-013) or "
            "record the reason in apps.tenancy.services.UNSEEDABLE_REFERENCE_LISTS. This is "
            "DEF-016: a reference list may be legitimately unseedable, but it may never be "
            "quietly empty. Re-run with --allow-empty-reference-lists to proceed anyway."
        )

    # ── the production guard, PER PATH (DEF-026 · BR-TEN-064) ───────────────
    @staticmethod
    def _under_production_settings(probe: dict[str, Any]) -> bool:
        return str(probe["settings_module"]).endswith("production")

    def _refuse_demo_fixture_in_production(self, probe: dict[str, Any]) -> None:
        """DEF-026. This refusal belongs to the DEMO-FIXTURE PATH ONLY.

        It used to sit at the top of `handle()`, before `options["tenant"]` was
        ever read — so `--tenant <subdomain>`, the reference-data BACKFILL for a
        tenant that ALREADY EXISTS, could not run under production settings.
        Production is the only place real tenants exist, so a live tenant that
        signed up before a reference list existed was UNFILLABLE: the one path
        written for it refused wherever it was needed. That is DEF-026.

        BR-TEN-064 (CONFIRMED, PO 2026-08-10) rules the guard PER PATH and the
        three paths are asserted separately (EP-TEN-03 TC-12):

          · demo fixture (no flags) — REFUSES here. It mints a whole tenant with
            a PUBLISHED owner password (BRAZOS_BEND["owner"]["password"], echoed
            by the closing summary), which is exactly what must never exist on a
            production database. Unchanged, and deliberately so.
          · `--tenant <subdomain>` — RUNS. It creates no tenant, no user, no
            credential and no subscription; it copies the platform reference
            fixture into a tenant somebody else already provisioned, and it
            touches no money. The same reasoning BR-TEN-064 applies to the
            sample-data job applies here: a guard that fires where the work is
            needed means the ruling never executes.
          · `--check` — write-free everywhere, exits 0 everywhere. A report is
            safe to read on any host; refusing to REPORT was never the point.
        """
        if self._under_production_settings(probe):
            raise CommandError(
                "seed_demo refuses under production settings — the demo-fixture path "
                "mints a tenant with a PUBLISHED owner password and fixtures never "
                "reach prod (09-infra §5 step 4 · BR-TEN-064). The reference-data "
                "backfill is NOT refused: `manage.py seed_demo --tenant <subdomain>` "
                "runs here and fills a tenant that already exists (DEF-026)."
            )

    # ── handle ──────────────────────────────────────────────────────────────
    def handle(self, *args: Any, **options: Any) -> None:
        probe = self._probe()
        blockers = self._blockers(probe)

        if options["check"]:
            # No production guard: --check writes nothing on any path and on any
            # host (BR-TEN-064). It is a report, and the operator who most needs
            # to read it is the one standing in front of the production box.
            self._report(probe, blockers)
            self.stdout.write(
                self.style.SUCCESS("ready to seed")
                if not blockers
                else self.style.WARNING(f"not ready — {len(blockers)} blocker(s) above")
            )
            return  # --check always exits 0: it is a report, not a gate

        if options["tenant"]:
            # Reference-data BACKFILL for an existing tenant. NO production
            # refusal (DEF-026 / BR-TEN-064) — this path is FOR production. The
            # Postgres guard is part of `blockers` and is checked first, so
            # sqlite refuses here exactly as it does for the demo path — before
            # a tenant table is read, let alone written.
            self._backfill_existing_tenant(
                probe,
                blockers,
                str(options["tenant"]),
                allow_empty=bool(options["allow_empty_reference_lists"]),
            )
            return

        # ── from here down: the DEMO FIXTURE path, and only it ──────────────
        self._refuse_demo_fixture_in_production(probe)
        self._ensure_plans()

        if blockers:
            self._report(probe, blockers)
            raise CommandError(
                "seeding blocked — nothing tenant-scoped was written (BR-TEN-001 "
                "atomicity). Fix the blocker(s) above and re-run; the command is "
                "idempotent (BR-TEN-010)."
            )

        payload = {**BRAZOS_BEND, "owner": dict(BRAZOS_BEND["owner"])}
        env_password = os.environ.get("SEED_DEMO_OWNER_PASSWORD")
        if env_password:
            payload["owner"]["password"] = env_password

        result = services.provision_tenant(payload)
        if result["created"]:
            self.stdout.write(self.style.SUCCESS(f"provisioned tenant '{result['subdomain']}'"))
            self.stdout.write(
                f"  owner user ............ {result['owner_user_id']} (via identity seam)"
            )
            self.stdout.write(f"  trial ends ............ {result['trial_ends_at']}")
            seed = result["reference_seed"]
            self.stdout.write(
                f"  reference seed ........ version={seed['version']} seeded={seed['seeded']}"
            )
            for list_code, reason in seed["skipped_reasons"].items():
                # BR-TEN-013 skip-until-wired, said out loud and per list. The
                # old single line said only WHICH lists skipped, into a summary
                # nobody read — that is DEF-016.
                self.stdout.write(self.style.WARNING(f"  SKIPPED {list_code}: {reason}"))
        else:
            self.stdout.write(
                f"tenant '{result['subdomain']}' already provisioned — replay left it "
                "unchanged (BR-TEN-010)"
            )

        tenant_id = result["id"]
        actor = self._demo_actor(result, payload)

        # S8 settings through the real tab-save services, acting as the demo
        # operator (System Admin). Idempotent: unchanged fields write nothing.
        with core_tenancy.tenant_context(tenant_id):
            services.save_company_profile(actor, COMPANY_PROFILE)
            services.save_regional_settings(actor, REGIONAL_SETTINGS)
            self.stdout.write(
                "company profile + regional/fiscal settings saved (US-TEN-005/006 §4 data)"
            )

            made: dict[str, int] = {}
            # BEFORE the schedules: `_trash_uom()` reads the declared billed
            # unit when one is being built (DEF-2310 / DEF-2311).
            made["service declarations"] = self._declare_service_measurement(actor)
            made["charge codes"] = self._seed_charges(actor)
            made["taxes"] = self._seed_taxes(actor)
            made["rate schedules"], schedules = self._seed_schedules(actor)
            made["rate plans"], made["plans published"] = self._seed_plans(actor, schedules)
            (
                made["premises"],
                made["units"],
                index,
            ) = self._seed_premises_and_units(actor)
            made["billing cycles"], made["routes"] = self._seed_cycles_and_routes(actor, index)
            made["assets"] = self._seed_assets(actor, index)
            # CR-029 RC-W0-T1 — after the assets, because an exclusion names one.
            made["meter exclusions"] = self._apply_route_exclusions(actor)
            # CR-054 W0 task 1 — the plans FIRST: a reading's plan-driven
            # required register set is resolved from the unit's plan, so a read
            # posted before the plan exists is judged against `no_plan`.
            made["unit plans"] = self._assign_unit_plans(actor, index)
            made["meter reads"] = self._seed_multi_register_reads(actor)

            counts = self._live_counts()
            unexplained = self._reference_data_report(
                selectors.us_state_code(str(REGIONAL_SETTINGS["state"]))
            )

        self._closing_summary(payload, result, made, counts)
        self._refuse_unexplained(unexplained, allowed=bool(options["allow_empty_reference_lists"]))

    # ── reference-data backfill for a tenant that ALREADY EXISTS (--tenant) ──
    def _backfill_existing_tenant(
        self, probe: dict[str, Any], blockers: list[str], subdomain: str, *, allow_empty: bool
    ) -> None:
        """`--tenant <subdomain>`: fill this tenant's REFERENCE DATA and nothing
        else. No tenant row, no owner, no subscription, no demo records, no
        money — an operator who signed up before a list existed had no way to
        get it, and this is that way.

        The identity/audit blockers still apply (an audit row must be writable —
        CLAUDE.md rule 7), and so does the Postgres guard: tenant context is a
        Postgres GUC, so sqlite refuses before a tenant table is touched."""
        if blockers:
            self._report(probe, blockers)
            raise CommandError(
                "backfill blocked — nothing tenant-scoped was read or written. Fix the "
                "blocker(s) above and re-run; the command is idempotent (BR-TEN-010)."
            )
        tenant = models.Tenant.objects.filter(subdomain=subdomain.strip().lower()).first()
        if tenant is None:
            known = sorted(models.Tenant.objects.values_list("subdomain", flat=True))
            raise CommandError(
                f"no tenant with subdomain '{subdomain}' (present: {', '.join(known) or 'none'}). "
                "--tenant fills an EXISTING tenant; it never provisions one — signup does "
                "that (S110–S114)."
            )
        actor = self._backfill_actor(tenant)
        with core_tenancy.tenant_context(tenant.id):
            summary = services.seed_reference_data_for_tenant(tenant, actor)
            self.stdout.write(
                self.style.SUCCESS(f"reference-data backfill · tenant '{tenant.subdomain}'")
            )
            self.stdout.write(f"  fixture version ....... {summary['version']}")
            if summary["seeded"]:
                self.stdout.write(
                    "  seeded ................ "
                    + ", ".join(f"{count} {name}" for name, count in summary["seeded"].items())
                )
            else:
                self.stdout.write(
                    "  seeded ................ nothing — every list already carried its "
                    "seed-run row for this fixture version (idempotent replay, BR-TEN-010)"
                )
            for list_code, reason in summary["skipped_reasons"].items():
                self.stdout.write(self.style.WARNING(f"  SKIPPED {list_code}: {reason}"))
            # DEF-123 — THE REPAIR PATH FOR A TENANT PROVISIONED BEFORE THE
            # BILL-TEMPLATE SEED EXISTED. Provisioning seeds it from 2026-08-16;
            # a tenant created before that line has no template and therefore
            # cannot issue a single bill (BR-BIL-026 makes the pin non-optional).
            # A change to provisioning never reaches a tenant that already
            # exists, which is hard-won law 4 in its data form, so the operator
            # needs a door and this is it. Idempotent: insert-missing.
            template_seed = seams.seed_bill_templates(actor, on_date=selectors.tenant_today())
            if template_seed is None:
                self.stdout.write(
                    self.style.WARNING(
                        "  SKIPPED bill template: apps.billing.services.seed_bill_templates "
                        "is not wired — this tenant cannot issue a bill (DEF-123)."
                    )
                )
            else:
                self.stdout.write(f"  bill template ......... {template_seed['reason']}")
            # DEF-163 — THE SAME REPAIR DOOR, FOR THE NOTICE TEMPLATES.
            # Provisioning seeds them from 2026-08-16; a tenant created before
            # that line cannot send a dunning letter or a disconnection notice
            # at all, because `template_service.resolve` refuses without a
            # published body and generation refuses with it. Idempotent:
            # insert-missing, so a body a tenant edited is never overwritten.
            #
            # BOTH HALVES ARE PRINTED. `seeded` is what landed; `absent` is
            # every class the platform has NO body for, each with its reason —
            # and an operator who reads only the first half would walk away
            # believing this utility can send a disconnection notice.
            notice_seed = seams.seed_notice_templates(actor, on_date=selectors.tenant_today())
            if notice_seed is None:
                self.stdout.write(
                    self.style.WARNING(
                        "  SKIPPED notice templates: apps.notifications.services."
                        "seed_notice_templates is not wired — this tenant cannot send a "
                        "notice (DEF-163)."
                    )
                )
            else:
                self.stdout.write(f"  notice templates ...... {notice_seed['reason']}")
                for row in notice_seed["absent"]:
                    self.stdout.write(
                        self.style.WARNING(f"  NO BODY {row['code']}: {row['reason']}")
                    )
            # DEF-251 — THE REPAIR DOOR FOR THE READ-VALIDATION SETTINGS ROW.
            # Provisioning seeds it from 2026-08-18; every tenant created
            # before that line has none, and none of them will ever get one
            # from provisioning (hard-won law 4 in its data form). What that
            # tenant experiences is not an error: every threshold read-check
            # reports `not_evaluated: validation config missing` and the
            # single-read correction path does not say even that.
            # Idempotent — a tenant that has tuned its thresholds keeps them.
            read_validation = seams.seed_read_validation_settings(actor)
            if read_validation is None:
                self.stdout.write(
                    self.style.WARNING(
                        "  SKIPPED read validation: apps.metering.services."
                        "seed_read_validation_settings is not wired — this tenant's "
                        "threshold read-checks will report not_evaluated (DEF-251)."
                    )
                )
            else:
                self.stdout.write(
                    "  read validation ....... "
                    + (
                        "row created with the ratified defaults"
                        if read_validation["created"]
                        else "already present — not overwritten"
                    )
                )
            # DEF-258 — THE REPAIR DOOR FOR THE NOTIFICATION ROWS.
            # Provisioning writes the dispatch-settings row from 2026-08-17 and
            # the SET-12 rule matrix from 2026-08-19; a tenant created before
            # either line has neither, and hard-won law 4 says a change to
            # provisioning never reaches a host that already exists. The rows
            # DO materialise on first read, so this door is not the difference
            # between working and broken — it is the difference between "this
            # utility has never configured its notifications" and "nobody has
            # opened the screen", which are the same zero rows and different
            # facts. Idempotent: a tenant that tuned its matrix keeps it.
            notification_seed = seams.seed_notification_settings(actor)
            if notification_seed is None:
                self.stdout.write(
                    self.style.WARNING(
                        "  SKIPPED notifications: apps.notifications.services."
                        "seed_notification_settings is not wired — this tenant's "
                        "dispatch row and rule matrix appear on first read instead "
                        "of now (DEF-258)."
                    )
                )
            else:
                made_rules = int(notification_seed.get("rules_created", 0))
                made_channels = int(notification_seed.get("channels_created", 0))
                self.stdout.write(
                    "  notification rules .... "
                    + (
                        f"{made_rules} rule(s) + {made_channels} channel row(s) created"
                        if made_rules or made_channels
                        else "already present — not overwritten"
                    )
                )
            # DEF-253 — THE HOLIDAY CALENDAR RENEWAL.
            # Provisioning seeds the sign-up year and the next and NOTHING
            # renews it, so on the first 1 January after that horizon every
            # business-day grace calculation goes back to skipping weekends
            # alone: a bill due Thu 24 Dec charges its late fee on Mon 4 Jan,
            # a day early and ON New Year's Day, silently, for every customer
            # of that tenant (DEF-042, returning).
            #
            # ⚠ AN EMPTY CALENDAR IS LEFT ALONE. A tenant outside the US
            # deletes every seeded date, which BR-TEN-039 entitles them to do,
            # and empty is indistinguishable from new in the data — so the
            # top-up EXTENDS and never seeds from nothing. That refusal lives
            # in `ensure_us_holidays_through`; this door cannot override it.
            holidays_added = services.top_up_holiday_calendar(tenant)
            if holidays_added:
                self.stdout.write(f"  holiday calendar ...... {holidays_added} date(s) added")
            elif not models.HolidayCalendar.objects.filter(tenant=tenant).exists():
                self.stdout.write(
                    "  holiday calendar ...... EMPTY, and left empty on purpose — this "
                    "tenant removed the seeded dates (BR-TEN-039) and business-day "
                    "grace will skip weekends only"
                )
            else:
                self.stdout.write("  holiday calendar ...... already covers this year and next")
            state_code = selectors.us_state_code(tenant.state) if tenant.state else None
            unexplained = self._reference_data_report(state_code)
        self._refuse_unexplained(unexplained, allowed=allow_empty)

    def _backfill_actor(self, tenant: Any) -> Any:
        """A System Admin actor whose id is the tenant's REAL owner user, so the
        BR-TEN-016 audit rows name a person and not a synthetic uuid. Both seams
        are optional here: an unresolvable owner yields actor_user_id NULL — a
        system action — rather than a foreign-key violation or an invented id."""
        owner_user_id = None
        email = None
        try:
            email = seams.owner_email_for(tenant.id)
        except seams.SeamNotWired:
            email = None
        if email:
            from apps.identity import selectors as identity_selectors

            owner = identity_selectors.user_by_email(tenant.id, email)
            owner_user_id = str(owner.id) if owner is not None else None
        if owner_user_id is None:
            self.stdout.write(
                self.style.WARNING(
                    "  owner user not resolvable through the identity seam — the audit "
                    "rows for this backfill carry no actor (system action), stated rather "
                    "than filled with an invented id."
                )
            )
        return SimpleNamespace(id=owner_user_id, pk=owner_user_id, role=SYSTEM_ADMIN)

    def _demo_actor(self, result: dict[str, Any], payload: dict[str, Any]) -> Any:
        """The demo operator: a System Admin whose id is the tenant's REAL owner
        user. `provision_tenant` returns owner_user_id only on the CREATE path
        (a BR-TEN-010 replay returns None), and several W1 tables hold FKs into
        `users` (asset_assignments.actor_user_id, rate_change_log.actor_id) — a
        synthetic uuid would be a foreign-key violation, so the replay path
        re-reads the owner through identity's selector (read layer, LAW 0)."""
        owner_user_id = result.get("owner_user_id")
        if owner_user_id is None:
            from apps.identity import selectors as identity_selectors

            owner = identity_selectors.user_by_email(result["id"], payload["owner"]["email"])
            owner_user_id = str(owner.id) if owner is not None else None
        return SimpleNamespace(id=owner_user_id, pk=owner_user_id, role=SYSTEM_ADMIN)

    def _closing_summary(
        self,
        payload: dict[str, Any],
        result: dict[str, Any],
        made: dict[str, int],
        counts: list[tuple[str, Any]],
    ) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("── Brazos Bend demo tenant · what is in it now ──"))
        for label, value in counts:
            dots = "." * max(1, 32 - len(label))
            self.stdout.write(f"{label} {dots} {value}")

        # CR-029 RC-W0-T1 — an area the fixture names and the tenant does not
        # hold. Never silent: an untagged premises is a route wizard whose area
        # chips return zero rows (DEF-220), and the whole point of the tag is
        # that somebody can see it is there.
        if self._area_gaps:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "area tags SKIPPED — this tenant does not hold: "
                    + ", ".join(sorted(self._area_gaps))
                    + " (the SET-06.2 area filter and BR-MET-083's cascade are "
                    "unexercised for those districts)"
                )
            )

        written = sum(made.values())
        self.stdout.write("")
        if written:
            self.stdout.write(
                "this run created: "
                + ", ".join(f"{count} {label}" for label, count in made.items() if count)
            )
        else:
            self.stdout.write(
                "this run created nothing — every object was already present "
                "(idempotent replay, BR-TEN-010 posture)"
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("── walkthrough credentials ──"))
        # PO ruling 2026-08-10: tenancy is PATH-based, so the walkthrough opens
        # /{tenant}/signin on the one origin — no per-tenant hostname exists.
        self.stdout.write(f"tenant (URL path segment) ....... /{result['subdomain']}")
        self.stdout.write(f"sign-in ......................... /{result['subdomain']}/signin")
        self.stdout.write(f"owner email ..................... {payload['owner']['email']}")
        self.stdout.write(f"owner password .................. {payload['owner']['password']}")
        self.stdout.write(
            "                                  (demo fixture credential — override with "
            "SEED_DEMO_OWNER_PASSWORD; NEVER prod)"
        )

        self.stdout.write("")
        self.stdout.write("not seeded, and why (no value was invented to fill these):")
        for note in OMITTED_FOR_LACK_OF_A_RATIFIED_FIGURE:
            self.stdout.write(f"  · {note}")
        self.stdout.write(
            "  · premise numbers (S14 'Premise ID') are blank: EP-TEN-08 defines no "
            "`premises` series and BE-06's KNOWN_SERIES carries none, so provisioning "
            "seeds no row and create_premises accepts no override — the metering "
            "service reports `numbering_series_missing` rather than faking a number. "
            "Unit IDs come from EP-MET-01 §4 because create_unit DOES accept unit_no."
        )
        self.stdout.write(
            "  · customers/accounts, bills, payments and finance: their lanes have not "
            "landed (09-infra §13 item 6) — nothing here fakes them."
        )
        self.stdout.write(
            "  · a full cycle of readings for every meter: CR-054 W0 task 1 seeds the "
            "REGISTER SHAPES the validation engine had nothing to judge — a time-of-use "
            "meter with its four registers, a demand meter with its peak in kW and its "
            "noted reset, one meter deliberately SHORT of its plan's set so the "
            "completeness warning has something to fire on, and a net meter's export "
            "record. It is a demonstration set, not a cycle: the other meters on this "
            "tenant still carry no reading, which is what makes the S25 Missing chip and "
            "the chase list have something to show."
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-001@a1d4f6b (EP-TEN-03 provisioning + 09-infra r1 §13 item 6); W1 extension co-packet US-RAT-002/US-MET-003/US-AST-002 (Plans & Rates · Premises/Units · Assets)
# generated: 2026-08-09 by story-coder v1 (deploy-prep lane; trailer completed by Eng-Lead after the lane hit the session limit) · EXTENDED 2026-08-10 by story-coder (W1 demo-content lane) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10) · AMENDED 2026-08-10 by story-coder (deploy-blocker lane — 09-infra/02 §10.3) · AMENDED 2026-08-10 by story-coder (DEF-016/017 reference-data lane — --tenant backfill, the loud EMPTY-lists report and its non-zero exit) · AMENDED 2026-08-10 by story-coder (DEF-026 backend-fix lane — production guard split PER PATH, TAMPER $250 PO ruling, DEF-017's seventh list `premises_types`, BR-TEN-067 structural-catalogue exemption) · AMENDED 2026-08-18 by story-coder (CR-010 silent-seed-gaps lane — DEF-251/DEF-253: the --tenant repair door now seeds the read-validation row and tops up the holiday calendar, and PRINTS which of the three calendar states it found)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — management command) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: loads under Django✔ · refuses non-Postgres + unregistered-sink up front (BR-TEN-001 no half tenant)✔ · run_gates✔ · trace_lint✔ · live seed run against PostgreSQL 16 executed TWICE — identical counts on the replay (idempotent)✔ · sqlite suite green (tests/test_seed_demo.py; the live double-run case is Postgres-gated via tests.isolation_helpers.requires_postgres) · [path-tenancy lane 2026-08-10] ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · [deploy-blocker lane 2026-08-10] ruff✔ black✔ · re-run live against PostgreSQL 16 after the change: prints `plan catalog: growth, scale, starter (seeded by tenancy 0005)` and `this run created nothing` (idempotent replay, counts unchanged) · suite `pytest tests -m "not golden and not isolation"` 868 passed / 9 skipped (818 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · [DEF-016/017 reference-data lane 2026-08-10] ruff✔(--select E4,E7,E9,F on apps/ — the bar the baseline passes; the repo-wide `ruff check .` default-rule run has 194 pre-existing findings under the newer ruff 0.15.8 in this container, none in this lane's files) black✔(--target-version py312 on this lane's files; 8 apps/ files are pre-existing reformat candidates under black 26.3.1, none of them this lane's) · suite `pytest tests -m "not golden and not isolation"` 895 passed / 9 skipped (875 was the baseline in this tree when the lane started) · `-m isolation` 14 passed / 30 skipped (unchanged) · run_gates 13-PASS/0-FAIL/1-SKIP✔ · no migration in this lane (no schema change) · RED-then-GREEN proved for both defects: removing rating's seam turns the DEF-016 guard red naming ['charge_codes','tax_jurisdictions']; removing the six SEED_LIST_OWNERS rows turns the DEF-017 guards red naming all six · [DEF-026 backend-fix lane 2026-08-10] ruff check .✔(All checks passed) black --check on this lane's 6 files✔ (the repo-wide run reports 9 reformat candidates, ALL of them the concurrent metering W2-reads lane's files — none of this lane's) · suite `pytest tests -m "not golden and not isolation"` 975 passed / 10 skipped / 4 FAILED — every failure belongs to the concurrent metering+customers W2 lane (test_be11_openapi snapshot · test_be_list_export routes/cycles · test_us_met_005_006 ×2, where `collected` flipped from None to 0 when that lane wired seams.collected_read_count) and each was PROVED pre-existing by re-running it with every file of THIS lane reverted to HEAD: identical 4 failures. The baseline when this lane started was 923 passed / 9 skipped / 0 failed · `-m isolation` sqlite 14 passed / 39 skipped; live Postgres (config.settings.local + DATABASE_URL) 40 passed / 12 skipped / 1 failed (test_us_cus_003_account_race — customers lane) · run_gates 10-PASS/4-FAIL/1-SKIP: G1, G3, G7 and G8 name ONLY apps/metering/** and apps/customers/** files from the concurrent lane (14-PASS/0-FAIL/1-SKIP at lane start) · `manage.py seed_demo --check` exit 0 under config.settings.local AND under config.settings.production · no migration in this lane (no schema change) · LIVE PROOF on PostgreSQL 16 with DJANGO_SETTINGS_MODULE=config.settings.production: `seed_demo --tenant lonestarridge` RAN and seeded 5 premises_types into a tenant that could never have been filled before; the replay wrote nothing (BR-TEN-010); `seed_demo` with no flags still refused; `--check` still exit 0 and now names which paths the host allows · RED-then-GREEN proved for all three guarded changes — (1) DEF-026: with the refusal restored to the top of handle(), the --tenant and --check cases fail with 'refuses under production settings' on sqlite AND the live-Postgres backfill case fails the same way, while the demo-fixture case stays green, which IS the split; (2) DEF-017 seventh list: removing the two `premises_types` registrations turns 6 tests red naming it; (3) BR-TEN-067: restoring the `if data["load_defaults"]` gate turns US-TEN-002 TC-2 red with seeded_lists == set()
# exceptions: E3 — W1 content is seeded only where a RATIFIED figure exists; five objects are deliberately NOT created (OMITTED_FOR_LACK_OF_A_RATIFIED_FIGURE, printed by the command itself) · premise_no stays NULL because no `premises` number series is defined anywhere (EP-TEN-08 / BE-06 KNOWN_SERIES) — reported, not worked around · reads/customers/bills/payments still await their lanes · [path-tenancy lane 2026-08-10] the walkthrough now prints the tenant as a URL PATH segment and the /{tenant}/signin route; row counts are unchanged (63 audit rows) because the owner session provisioning opens is created either way — only its id now reaches an HTTP cookie, which a CLI run has none of · [deploy-blocker lane 2026-08-10] _ensure_plans() NO LONGER WRITES. It was the only writer of `subscription_plans` in the repo, it created one plan, and it refuses to run under production settings — so a real deployment started with an empty catalog and every signup failed (09-infra/02 §10.3). The catalog is now seeded by apps/tenancy/migrations/0005_seed_subscription_plans.py before any tenant exists; this command CHECKS for it and raises CommandError naming the migration if it is missing, because a demo seed that quietly built its own catalog is exactly what hid the blocker · the earlier note here that "starter/scale have no signed values" is WITHDRAWN — A10, the A13 addendum of 2026-08-07, A1 §S112 and B2's column comment all price all three, and the migration cites them per row · [DEF-016/017 lane 2026-08-10] `--tenant <subdomain>` seeds/backfills REFERENCE DATA ONLY into an EXISTING tenant — it provisions nothing, creates no owner and writes no sample records; the production guard and the Postgres guard are unchanged and --check stays write-free and exit 0 · the run now prints every declared reference list with its live count and an explicit 'EMPTY, and why' block, and EXITS NON-ZERO when a list is empty with no recorded reason (--allow-empty-reference-lists is the named escape hatch — the unsafe option is the one you type) · _seed_charges became create-or-COMPLETE because provisioning now seeds the same [F] figures first: it fills only fields still empty, so the demo keeps its cited charge_type/waivable and a replay still writes nothing · _seed_taxes resolves the jurisdiction by NAME before using the inline dict, because create_tax mints a new jurisdiction for every inline payload and would otherwise have created a second 'Texas State' · OUT OF SCOPE and deliberately NOT built here (BR-TEN-056 clauses 1-3, another lane): the is_sample tag, sample RECORDS, the background provisioning job and the Settings 'Remove sample data' action — services.seed_reference_data_for_tenant() and services.reference_data_report() are the seams they will use · [DEF-026 lane 2026-08-10] the production refusal is now PER PATH (BR-TEN-064, EP-TEN-03 TC-12): the demo-fixture path still refuses because it mints a tenant with a PUBLISHED owner password; `--tenant <subdomain>` RUNS in production because it creates no tenant, user, credential or subscription and production is the only host where real tenants exist; `--check` is write-free and exit 0 everywhere and now NAMES which paths the host allows · TAMPER is $250.00 quoted from [F] (PO ruling 2026-08-10 — EP-RAT-03 §4 over the billing workbook's $500.00, and made a PLATFORM default); the workbook's $500.00 is neither deleted nor a second default — it is the WE-11 worked example, and tests/test_seed_demo.py keeps both facts side by side so the divergence reads as a ruling and not as drift · DEPO-R stays uncreated for a RULING, not a missing figure (BR-RAT-020/023 supersede the prototype's single DEPO-R checkbox), and its note now says so · REPORTED, NOT FIXED HERE: a fixture edit does NOT reach a tenant that already carries a `reference_seed_runs` row for version 2026.08, so EXISTING tenants receive neither TAMPER nor the new `charge_type` values — that needs a fixture VERSION BUMP, a PO/versioning decision outside this lane · REPORTED, NOT FIXED HERE: `premises_types` now seeds and reports, but its S8 Reference-data card still cannot render — that needs apps.metering to call register_lookup_handler AND to author the list's CRUD services (it has none), and apps/metering/** is another lane's territory in this session, so it was deliberately not edited
# AMENDED: 2026-08-30 by the CR-054 W0 task 1 lane (multi-register demo readings)
#   — `DEMO_CYCLE_READS` + `_seed_multi_register_reads` + `_assign_unit_plans`, and
#   M-7450 / M-7302's `net_metering` in ASSETS. MEASURED FINDING: the demo utility
#   held 199 readings and every one was `total`, so `plan_register_completeness`,
#   `tou_sum_sanity`, the demand path and `export` had nothing to judge; all ten of
#   this fixture's units also carried NO rate plan, so the resolver answered
#   `no_plan` for every meter and `create_account` (BR-CUS-014) would have refused
#   every address. 24 readings now post through stage -> validate -> disposition ->
#   commit, never an INSERT. Eng disposition REPORTED, three of them: (1) which plan
#   each unit is on is FIXTURE AUTHORSHIP, declared per unit because the Industrial
#   unit is a `commercial` type on `IND` and a derivation would need a rule nobody
#   wrote; (2) the seeded TOU total is 424 — EP-MET-03 §4's own three window deltas
#   summed — and NOT §4's 430, whose 1.40% is the FLAGGED case, so the demo shows
#   the healthy state and the breach is one number away; (3) all 24 readings carry a
#   truthful `vacant_unit` warning because this command seeds no accounts. Each is
#   written up in 12-governance/02-decision-log.md, 2026-08-30.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
