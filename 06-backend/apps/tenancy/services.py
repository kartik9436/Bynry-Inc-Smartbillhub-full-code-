# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-020 (2026-08-15 — `seed_reference_data_for_tenant` gains the
#           `structural_only` narrowing the sweep passes unconditionally per OQ-088)
# Story:    US-TEN-001 / US-TEN-002 / US-TEN-004 (EP-TEN-03 provisioning + seeding +
#           failure paths, S110–S114) · US-TEN-003 (S62 checklist writes) ·
#           US-TEN-005 / US-TEN-006 (EP-TEN-05 company + regional/fiscal saves, S8) ·
#           US-TEN-007 / US-TEN-008 (EP-TEN-06 services & UoM, S8) ·
#           US-TEN-009 / US-TEN-010 / US-TEN-011 (EP-TEN-07 lookup framework, S8) ·
#           US-TEN-012 (EP-TEN-08 numbering + the BE-06 allocator sink, S8)
#           AMENDED 2026-08-09 (settings rule-page + reference-data + logo gap
#           lane): US-TEN-005 (logo write) · US-TEN-009/010/011 (the two hosted
#           reference lists) · US-MET-011 (S64 config write — TC-7/TC-8)
#           Screens += S64, S66, S69, S70, S71
#           AMENDED 2026-08-10 (list-export lane): US-SHL-008 (the generic
#           table-level export accept — cap, audit, enqueue; 11b §2.11)
#           Screens += every list that declares Download
#           AMENDED 2026-08-15 (tenant custom-fields lane): US-TEN-014/015/016/017 (EP-TEN-09 — the four custom-field writes: create,
#           edit, placement, deactivate/reactivate; NO delete at any layer, BR-TEN-050) + `validate_custom_data_for`, PUBLISHED for the owning modules (US-SHL-015)
# Rules:    BR-TEN-001 · BR-TEN-003 · BR-TEN-010 · BR-TEN-011 · BR-TEN-012 ·
#           BR-TEN-013 · BR-TEN-014 · BR-TEN-015 · BR-TEN-016 · BR-TEN-017 ·
#           BR-TEN-018 · BR-TEN-020 · BR-TEN-021 · BR-TEN-024 · BR-TEN-025 ·
#           BR-TEN-026 · BR-TEN-027 · BR-TEN-029 · BR-TEN-030 · BR-TEN-031 ·
#           BR-TEN-034 · BR-TEN-035 · BR-TEN-036 · BR-TEN-037 · BR-TEN-039 ·
#           BR-TEN-041 · BR-TEN-042 · BR-TEN-043 · BR-TEN-019 (logo) ·
#           BR-MET-020 · BR-MET-026 · BR-MET-027 (S64) · BR-BIL-001 ·
#           BR-BIL-013 · BR-BIL-014 · BR-BIL-017 · BR-BIL-018 · BR-BIL-021 ·
#           BR-BIL-029 · BR-PAY-010 · BR-PAY-013 · BR-PAY-016 · BR-PAY-017 ·
#           BR-PAY-018 · BR-PAY-019 · BR-REP-022 (the rule-page saves)
# Tests:    06-backend/tests/test_us_ten_001_004_provisioning.py ·
#           test_us_ten_002_seeding.py · test_us_ten_003_checklist.py ·
#           test_us_ten_005_006_settings.py · test_us_ten_007_008_services_uom.py ·
#           test_us_ten_009_011_lookups.py · test_us_ten_012_numbering.py ·
#           test_us_ten_settings_rule_pages.py (the five rule pages + logo)
# Impacts:  BE-01 resolver + BE-06 numbering sink registration (apps.py) · every
#           issuing module (number allocation) · S62 checklist · S8 Settings tabs ·
#           J1 (signup → provisioned tenant → checklist) · J5 step 3 (fiscal)
# ───────────────────────────────────────────────────────
"""tenancy service layer — the ONLY write path into this module's tables (LAW 0:
api thin → services sole writer → selectors read).

HUMAN-OWNED — added 2026-08-31 when the PO's ruling put this file on
10-scripts/gates/human_owned.txt ("groups one, two, three and four ... That is
56 files"). The guard list requires both markers; this file carried only
HUMAN-REVIEW-PENDING, which is exactly why G53 could not see it (DEF-2790).

Cross-module calls go through apps/tenancy/seams.py exclusively (BR-TEN-013/031)
— this module never imports another module's models. Every write here lands its
BR-TEN-016 audit row through core.audit (BE-03); every refusal is a catalog
exception (BE-02); all config writes are event-time forward (BR-TEN-043) —
nothing here re-renders or restates anything already issued (BR-TEN-017/020/027/035).

Eng dispositions recorded in the build report (not silently resolved):
- ⚠ ein: CLOSED 2026-08-24 (BR-CUS-092(b), settling DEF-632). This entry read
  *"ein stored as plain 9 digits for now — the OQ-016 ruling (app-layer
  encryption) needs a platform crypto kernel that no lane has authored yet"* for
  the life of the product, and it was the whole of the record: "for now" had no
  expiry, no owner and no test, so a CLOSED ruling (OQ-016, B2 §6) sat
  unimplemented and INVISIBLE until a screen promised a customer their SSN was
  *"stored encrypted"*. The kernel now exists — `core/crypto.py` — and this
  column is its SECOND caller, which BR-CUS-092(b) required precisely because
  *"a helper with one caller is exactly how the first one was skipped"*. Written
  and read through `models.Tenant.ein` (`EncryptedTextField`, AES-256-GCM);
  converted by `tenancy/migrations/0018_br_cus_092_ein_encrypted`. NOTHING IN
  THIS FILE CHANGED: `save_company_profile` still normalises to nine digits
  (BR-TEN-018) and `mask_ein` still masks them into the audit trail
  (BR-AUD-006) — the field encrypts underneath both. Guarded by
  tests/test_br_cus_092_ein_encryption.py. 🔒 HUMAN-REVIEW-PENDING on the
  encryptor itself.
- DEP-/RCT-/EXP- series (BR-TEN-041) have NO design-stated default format —
  their rows are NOT seeded at provisioning; their owning W5 lanes seed them.
- Owner password policy/hashing belongs to identity (seam contract) — this
  module only requires the field non-empty and passes it through.
"""

import json
import logging
import re
import time
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, NamedTuple
from uuid import UUID
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.tenancy import brand as brand_law
from apps.tenancy import exports
from apps.tenancy import logo as logo_law
from apps.tenancy import custom_fields
from apps.tenancy import models, platform_numbering, seams, selectors, settings_families, us_holidays
from core import audit as core_audit
from core import errors
from core import jobs as core_jobs
from core import numbering as core_numbering
from core import tenancy as core_tenancy
from core.dbfields import uuid7
from core.permissions import SYSTEM_ADMIN, require_role

logger = logging.getLogger("smartbillhub.tenancy")

TRIAL_DAYS = 14  # BR-TEN-014: trial_ends_at = provisioned_at + 14 days

# BR-TEN-011 subdomain grammar + reserved labels live in selectors.subdomain_problem
# (single source — the S110 live check and the S114 commit must answer identically).

# BR-TEN-042 (LC-5a/LC-6a): the seeded currency choices; ONE per tenant.
#
# ⚠ **UNTIL 2026-09-24 (`P0.6`) THIS TUPLE WAS THE ONLY PLACE IN THE PRODUCT
# THAT KNEW WHAT A CURRENCY IS.** 39 columns across the schema hold a bare
# `CharField(3)`; the lawful set lived here, the symbols lived in
# `apps/reports/dashboard_format.CURRENCY_SYMBOLS`, and nothing linked a single
# stored value to either. `tenancy.Currency` is the lookup `OQ-031` already
# ruled for (CLOSED → `BR-TEN-036`: *enums → lookup tables, seeded defaults*).
#
# **The five values do NOT move.** `tenancy/0050` seeds exactly these, so every
# refusal this drives answers today what it answered yesterday.
SEED_CURRENCIES = ("USD", "CAD", "MXN", "EUR", "GBP")


def active_currency_codes() -> tuple[str, ...]:
    """The currency codes a tenant may choose — read from the lookup table.

    ⚠ **A CALLABLE, NOT A MODULE-LEVEL QUERY, AND THAT IS NOT STYLE.** Reading
    the database at import time makes this module unimportable before its own
    migration has run — and `manage.py migrate` imports it. That is how a
    lookup table takes an application down on a fresh install.

    **Falls back to `SEED_CURRENCIES`** when the table cannot be read (an older
    schema, or the migration that creates it) or is empty. The fallback is the
    SAME FIVE VALUES, so both paths give the same answer and a caller cannot
    tell which it got. That is deliberate: this must never become a way for the
    product to start refusing a currency it accepted an hour ago.

    ⚠ **THE SAVEPOINT IS HARD-WON LAW 14 AND IS NOT OPTIONAL.** This function
    catches a database error and carries on — and **on PostgreSQL a failed
    statement aborts the entire transaction**. Without the nested `atomic()`,
    the `except` below would swallow the error and leave the connection
    unusable: every later query raises `InFailedSqlTransaction`, and a caller
    as important as `provision_tenant` would fail somewhere else entirely, with
    a message naming neither this function nor the missing table. The nested
    block is a SAVEPOINT, and it rolls back just the failed read.

    ⚠ **AND THE DEFAULT SUITE CANNOT SHOW THAT.** `config/settings/test.py`
    hardcodes in-memory SQLite, which has no aborted-transaction state — so the
    version WITHOUT the savepoint passes every test on every machine, green,
    and fails the first time a real host runs an older schema. Law 14 names
    this exact shape; do not "simplify" it away.
    """
    from django.db import transaction

    from apps.tenancy import models as tenancy_models  # local — avoids a cycle

    try:
        with transaction.atomic():  # the SAVEPOINT — see the docstring
            codes = tuple(
                tenancy_models.Currency.objects.filter(is_active=True)
                .order_by("sort", "code")
                .values_list("code", flat=True)
            )
    except Exception:  # noqa: BLE001 — table absent on an older schema
        return SEED_CURRENCIES
    return codes or SEED_CURRENCIES

# BR-TEN-042 (LC-2): seeded language set, data-driven. "en-US" accepted alongside
# "en" because the prototype/regional tab offers "English (US)" (PO veto invited).
#
# BR-SHL-041 (PO ruling 2026-08-10, picker mock-up) added the six new locales,
# and they are accepted here on 2026-08-11 with the catalogues that back them.
# The server tuple has to grow WITH the catalogues, not after them: this is the
# validated vocabulary for `tenant_settings.default_language`,
# `accounts.preferred_language` (through apps.customers.seams) and the S8
# Regional select, so a code the frontend offers and this tuple rejects is a 422
# on a control the user can see — and a code accepted here with no catalogue
# renders the app in English while claiming otherwise.
#
# The six new codes are REGION-QUALIFIED because BR-SHL-041 confirms them that
# way and they have no earlier spelling to preserve. The five originals keep
# theirs (`en`/`es`/`es-MX`/`de`/`hi`) until US-SHL-018 runs BR-SHL-042's data
# migration to `en-US`/`es-ES`/`es-419`/`de-DE`/`hi-IN` — that migration owns
# rewriting the stored values, and renaming them here first would make every
# stored value invalid between the two commits.
SEED_LANGUAGES = (
    "en",
    "en-US",
    "es",
    "es-MX",
    "de",
    "hi",
    "fr-FR",
    "id-ID",
    "it-IT",
    "ja-JP",
    "ko-KR",
    "pt-BR",
)
# US-TEN-006 §5: the offered pattern sets (prototype-extracted).
NUMBER_FORMATS = ("1,234.56", "1.234,56")
# PO ruling 2026-08-10 ("more date formats"): six, up from three. All numeric —
# a month-name format would need month names in each of the eleven BR-SHL-041
# locales, making a format choice depend on a translation catalog. The frontend
# mirrors this tuple in SettingsRegionalTab.DATE_FORMAT_OPTIONS; a value this
# tuple rejects must never be offered there.
# ── Default timezone per US state (PO 2026-08-10: "you have to give default
# time zones") ───────────────────────────────────────────────────────────────
# Provisioning left `tenant_settings.timezone` NULL, so a brand-new utility
# opened Settings → Regional to an empty field and every date on every screen
# rendered in UTC with the live preview reading "not set". The signup wizard
# already collects the state, which determines the zone for 37 of the 50.
#
# ⚠ THIRTEEN STATES SPAN TWO ZONES (AK FL ID IN KS KY MI ND NE OR SD TN TX).
# For those this is the zone of the larger share of the population, and it is a
# DEFAULT, not a determination — the field stays editable and a utility in
# east Tennessee or the Florida panhandle changes it in one click. That is the
# only honest way to prefill a value the state cannot decide: a sensible
# starting point that says what it is, never a silent claim to be correct.
# Values are constrained to the eight zones the S8 type-ahead offers (A1 §S8).
US_STATE_TIMEZONES: dict[str, str] = {
    "AL": "America/Chicago",
    "AK": "America/Anchorage",
    "AZ": "America/Phoenix",
    "AR": "America/Chicago",
    "CA": "America/Los_Angeles",
    "CO": "America/Denver",
    "CT": "America/New_York",
    "DE": "America/New_York",
    "DC": "America/New_York",
    "FL": "America/New_York",
    "GA": "America/New_York",
    "HI": "Pacific/Honolulu",
    "ID": "America/Denver",
    "IL": "America/Chicago",
    "IN": "America/New_York",
    "IA": "America/Chicago",
    "KS": "America/Chicago",
    "KY": "America/New_York",
    "LA": "America/Chicago",
    "ME": "America/New_York",
    "MD": "America/New_York",
    "MA": "America/New_York",
    "MI": "America/New_York",
    "MN": "America/Chicago",
    "MS": "America/Chicago",
    "MO": "America/Chicago",
    "MT": "America/Denver",
    "NE": "America/Chicago",
    "NV": "America/Los_Angeles",
    "NH": "America/New_York",
    "NJ": "America/New_York",
    "NM": "America/Denver",
    "NY": "America/New_York",
    "NC": "America/New_York",
    "ND": "America/Chicago",
    "OH": "America/New_York",
    "OK": "America/Chicago",
    "OR": "America/Los_Angeles",
    "PA": "America/New_York",
    "PR": "America/Puerto_Rico",
    "RI": "America/New_York",
    "SC": "America/New_York",
    "SD": "America/Chicago",
    "TN": "America/Chicago",
    "TX": "America/Chicago",
    "UT": "America/Denver",
    "VT": "America/New_York",
    "VA": "America/New_York",
    "WA": "America/Los_Angeles",
    "WV": "America/New_York",
    "WI": "America/Chicago",
    "WY": "America/Denver",
}

# The 13 above, named so a reader does not have to diff the map against an atlas.
SPLIT_ZONE_STATES = frozenset(
    {"AK", "FL", "ID", "IN", "KS", "KY", "MI", "ND", "NE", "OR", "SD", "TN", "TX"}
)


def default_timezone_for_state(state_code: str | None) -> str | None:
    """The prefill for a new tenant. None when the state is unknown — an unset
    zone the user must choose beats a wrong zone they never noticed."""
    if not state_code:
        return None
    return US_STATE_TIMEZONES.get(state_code.strip().upper())


DATE_FORMATS = (
    "MM/DD/YYYY",  # United States
    "DD/MM/YYYY",  # most of the world
    "YYYY-MM-DD",  # ISO 8601
    "DD.MM.YYYY",  # de-DE, continental Europe
    "DD-MM-YYYY",  # hi-IN, Dutch
    "YYYY/MM/DD",  # ja-JP, ko-KR
    "DD-MMM-YY",  # PO 2026-08-10 — the one month-NAME format (25-Aug-26).
    #
    # ⚠ **THIS COMMENT USED TO COVER BOTH DIRECTIONS IN ONE SENTENCE AND WAS
    # HALF FALSE (DEF-753).** It read: the name "is produced by Intl in the
    # app's current language … so it is already right in all eleven locales."
    # TRUE FOR DISPLAY. FALSE FOR IMPORT — and nobody checked the two separately
    # because one sentence appeared to answer both (hard-won law 1: a comment
    # claiming a guarantee is not the guarantee).
    #
    #   · WRITING (screens, bills): `components/DateCell.formatDate` asks `Intl`
    #     in the tenant's language, so a German tenant sees `25-Okt-26`.
    #   · READING (CSV import): `metering.import_runs._parse_date` uses `%b` in
    #     the C locale, which accepts ENGLISH abbreviations only. MEASURED:
    #     `25-Aug-26` parses; `25-Okt-26`, `25-Mär-26` and `25-mars-26` are all
    #     refused, as is `25-Sept-26`.
    #
    # The two do not meet — the app never imports a file it wrote (IS-11 keeps
    # every CSV export on ISO-8601) — so this is a documented asymmetry, not a
    # bug to paper over by guessing month names in eleven languages. The
    # importer's refusal and the S8 picker both say "English month names" out
    # loud instead.
    #
    # The 2-digit year is the PO's choice and is screen-only: IS-11 keeps CSV
    # exports on ISO-8601.
)
TIME_FORMATS = ("12-hour", "24-hour")
FIRST_DAYS_OF_WEEK = ("sunday", "monday")
ACCOUNTING_METHODS = ("accrual", "cash")
CLOSE_CADENCES = ("monthly", "quarterly")

# BR-TEN-035 / US-TEN-012 §4: prototype-stated default formats, seeded per tenant
# at provisioning (BE-06: "seeding the per-tenant series rows is provisioning's job").
#
# ⚠ THIS MAP IS NO LONGER TYPED OUT HERE — IT IS DERIVED, AND THAT IS THE POINT
# (CR-005, 2026-08-16). It held FIVE series while `core.numbering.KNOWN_SERIES`
# held nine, and the four in the gap were not a plan: a manual journal entry
# POSTED WITH NO NUMBER on every tenant in existence because `JOURNAL_ENTRY` was
# missing from this literal (BR-LED-021 (i), which names the one-line fix and
# says it *"belongs to the tenancy lane"* — this is that lane, and the fix is
# structural rather than one line so the next series cannot go missing the same
# way). The screen's ready-made options and the seeded default are now ONE
# source: option[0] of `SERIES_CATALOG`, so a tenant can never hold a format the
# dropdown does not offer.
SERIES_DEFAULTS: dict[str, str] = {
    series: options[0] for series, (_group, options) in core_numbering.SERIES_CATALOG.items()
}

# ── BR-TEN-1180 · WHAT THE PLATFORM SEEDS FOR EACH OF THE TEN SERVICES ──────
# One row per catalog service, in the seed order BR-RAT-024 fixes: HOW it is
# priced, and the units it is priced in. **RATIFIED CELL BY CELL BY THE PO ON
# 2026-09-02**, closing `DEF-2409` and `DEF-3230`.
#
# The PO's words, in the order they were said:
#   *"this is problem with every Utility services - why dont you se the correct
#   data in Seed data and fix it - show me on screen what youa re going to set in
#   table format first"*
#   *"Shall we consider Metered, % of service and Capacity based; Storm water -
#   it is capacity based not unmetered , capaicyt is decided based on sizes of
#   propoerty; Trash - it is capacity based and Cart sizes will decide price X
#   how many Cart; Solar - is also capacity based - 1 panel capacity X # of Solar
#   panels ; Broadband - It will be capacity based - ; Thermal/Heat - Metered;
#   Battery - capacity based - you ahve to udpaet it - show me final table"*
#   on solar's unit: *"that is correct - you have to decide the unit for Solar
#   panels - and then it behave like Trash only"*
#   on battery's `kW`: *"Im okay with it"*
#
# The signed table, which this map IS:
#
#   #   service        basis        primary   alt      changed from
#   1   electric       metered      kWh       kW       —
#   2   water          metered      kgal      ccf      —
#   3   gas            metered      ccf       therm    SWAPPED
#   4   sewer          share        —         —        was absent entirely
#   5   trash          capacity     cart      —        was `month`
#   6   storm_water    capacity     ERU       —        was `kgal`
#   7   solar          capacity     kW        —        was absent entirely
#   8   broadband      capacity     Mbps      —        was `month`
#   9   thermal_heat   metered      ton-hr    klb      —   ⚠ SUPERSEDED
#                                                       2026-09-07 — see below
#  10   battery        capacity     kW        —        was absent entirely
#
# Four metered · one share · five capacity. **THAT COUNT IS THE 2026-09-02 ONE
# AND IT HAS MOVED TWICE SINCE — fire made it six capacity (`CR-063`), and
# `CR-080` makes THERMAL the seventh. The live split is THREE metered · one
# share · SEVEN capacity, and `tests/test_br_ten_1180_billing_basis.py`
# `SIGNED_SHAPE` is the statement under test.**
#
# ── ROW 9 MOVED ON 2026-09-07 · `CR-080` · THERMAL IS CAPACITY-BASED ────────
# ⚠ **A SERVICE CHANGING SIDES IS A RE-SIGN, AND THIS ONE HAS THE RULING.**
# PO verbatim, 2026-09-07: *"connected tonnage - it is capacity not metering;
# i will ahve 100 tonne or 200 tonne etc"*, and in the same message *"it is
# capacity based - please make a note and figure out the impact - if you ahve
# to write a CR to ahndle this please write"*. Confirmed the same day in their
# eleven-service walk: *"Thermal — basis disputed - this si correct"*.
#
# ⚠ **AND IT IS A DEBT BEING CALLED IN RATHER THAN A NEW RULING.** The PO had
# already ruled on **2026-08-27**: *"(a) multiplier replaces bands for capacity
# services (solar, battery, thermal); bands stay for pipe/amp/CFH - this si
# corect"*. Thermal was named in that sentence and was the one service of the
# three never executed; `apps/tenancy/service_size_classes.py` recorded the
# omission in its own words — *"the debt solar just paid, thermal still owes"*.
# **So what row 9 reverses is a LANE judgment made because the ruling had not
# reached the code, not a PO decision.**
#
#   9   thermal_heat   capacity     ton       klb      metered → capacity,
#                                                      ton-hr → ton  (CR-080)
#
# ⚠ **THE UNIT AND THE BASIS MOVE TOGETHER, WHICH IS WHY THEY ARE ONE MAP** —
# see the paragraph below on `month`. `ton-hr` is an ENERGY (a ton of cooling
# delivered for an hour); a capacity service has no hours, so leaving it here
# would state `$X per ton-hour` against a quantity measured in connected tons.
# That is `DEF-497` exactly, one service over.
#
# ⚠ **`ton` IS THE REFRIGERATION TON — 12,000 BTU/hr — AND NOT THE METRIC
# TONNE.** The PO wrote *"tonne"*; the reading is recorded so they can correct
# it in one word. It is what the withdrawn size classes already said (*"Thermal
# chilled water ≤25 tons"*) and what a North American chilled-water utility
# measures — the City of Mesa's own rate book defines a Ton-Hour as 12,000 BTU
# and bills district cooling on a **Rated-Ton**.
#
# ⚠ **`klb` STAYS IN THE ALT SLOT AND `OQ-560` STAYS OPEN — DELIBERATE.** `klb`
# (thousand pounds of steam) is thermal's STEAM half, whose bands were put to
# the PO as a dimension with no boundaries and were never ruled;
# `steam_size_classes()` still raises `OQ-560`. Dropping `klb` here would make
# this map silent about steam, which reads like steam was settled. It also
# keeps the DERIVED scope below unchanged, so no catalogue entry is re-scoped
# by a side effect. `ton-hr` leaves this map and does **not** leave the
# catalogue: `lookup_defaults.json` STATES `"service": "thermal_heat"` on it,
# the fixture wins where it speaks, and `BR-TEN-071` deletes nothing — a
# utility that meters chilled-water energy still has the unit to pick.
#
# That is the whole platform default set, and it is now COMPLETE: this map named SEVEN services before today, and
# the rule it stated for the gap — *"a service absent from this map is one the
# DESIGN has not named units for, not one we forgot"* — is what turned three
# genuinely missing services into a documented decision (`DEF-3230`'s
# escape_reason). There is no gap left for that rule to protect.
#
# ── WHY GAS SWAPS, so nobody "tidies" it back ───────────────────────────────
# `apps/rating/sample_data.py` lines 64-65 and 344-345 sign gas at **$1.15 per
# ccf** while the seeded gas meter reads **therm**, with no conversion factor
# configured. That is the exact mismatch the bill-time unit gate refuses
# (`OQ-004`'s *"no silent conversion"*), and `DEF-2397` recorded it at the line
# the figure sits on rather than fixing it. Making `ccf` the primary makes the
# seed agree with the signed price; `therm` stays available as the ALT, so a
# utility that reads therms loses nothing.
#
# ── THE PATTERN UNDER trash / storm_water / solar / broadband / battery ─────
# The PO stated it as a count first — *"Cart sizes will decide price X how many
# Cart"* — so **the size class selects the RATE and the quantity is a COUNT of
# capacity units** (`BR-RAT-090`, option A, closing `OQ-283`). `month` was wrong
# for exactly that reason: it made the quantity a PERIOD rather than a count, so
# there was nothing to multiply.
#
# ⚠ **AND SOLAR IS THE ONE WHERE A COUNT IS NOT ENOUGH — `CR-062` statement (6)
# SUPERSEDES STATEMENT (4) OF THE SAME SESSION, AND THIS IS WHY SOLAR READS `kW`
# RATHER THAN `panel`.** Statement (4) approved `panel`, a count of panels
# exactly like carts. Statement (6) corrected it:
#
#   *"In solar youa re still not doing it correctly - For example We have 10
#   Types of Solar panel with various capaity 1 Kw, 2Kw 3Kw 4Kw so and SO forth ;
#   on given Unit we have installed 3 panels with 2Kw, 4Kw and 8 Kw , it means
#   the totla capacity will be 14 Kw ; rate will be for 1 Kw = 14 $ per KW then
#   bill should be 14 X 14 = 156 $"*
#
# **Panels come in different sizes and are installed together, so counting them
# loses the thing being sold.** Three panels of 2 kW, 4 kW and 8 kW are 14 kW —
# and a count would say "3", which prices a 14 kW array the same as three 1 kW
# ones. So the billable quantity is the SUM of the installed capacities and the
# unit is `kW`, the same unit battery carries and for the same reason.
#
# ⚠ **THE PO's ARITHMETIC IN THAT QUOTE IS OFF BY ONE PRODUCT AND THE CORRECTED
# FIGURE IS WHAT THE PRODUCT USES: 14 kW × `$14.00` = `$196.00`, not `$156`.**
# They were told so in the same session and did not dispute it (`CR-062` step 0).
# It is recorded rather than silently fixed, because a wrong figure copied into a
# fixture becomes a wrong figure asserted by a test, and then it is the product's
# own answer.
#
# **`panel` IS THEREFORE NOT ADDED TO THE CATALOGUE** (`CR-062` task B5). `kW`
# is already there, already unscoped, and now named by three services.
# `apps/tenancy/service_size_classes.py` already seeds size classes for most of
# these (trash CART-35/64/96 and DUMP-2/4/6/8, storm water SW-1ERU/2-5/6-20/20P,
# solar SOL-5/5-10/10-25/25P, battery none by the ruling that dissolved
# `OQ-561`) — the classes were already there and only the unit was wrong.
# ⚠ **THE SIZE CLASSES THEMSELVES ARE `CR-062` TASKS A1–A6 AND ARE NOT THIS
# LANE's** — the PO asked for ten solar panel types, six battery types and five
# storm-water sizes (*"for panels you will need various capacityes similarly the
# capacities we have created for Trash cart"*). This map states the UNIT each
# service is priced in; that file states the SIZES, and it is dispatched
# separately.
#
# ── BROADBAND'S UNIT IS A LANE JUDGMENT, RECORDED, NOT A QUESTION ───────────
# The PO said *"Broadband - It will be capacity based - "* and named no unit.
# `Mbps` is what was shown on the approved table and is already the fixture's
# broadband scope. The trade-off a later reader would otherwise rediscover: a
# per-Mbps rate (the BB-500 band × 500 Mbps) honours the capacity ruling exactly,
# while a utility that would rather charge a flat price per connection changes
# the unit on Settings → Services & UoM — **which is what a seeded DEFAULT is
# for.** Recorded in the decision log; not put back to the PO (law 13).
#
# ── SEWER IS THE ONE ROW WITH NO UNIT, AND THAT IS THE POINT ────────────────
# `share` means a percentage of another service's money (`BR-RAT-015` — sewer is
# a percentage of the water usage charge). It reads no register and counts no
# assets, so it has no quantity of its own and inventing a unit would be
# inventing one. r10 SET-03 draws sewer as an em-dash in both UoM columns, which
# is the design saying the same thing. `EDU` exists in the catalogue scoped to
# sewer and is deliberately NOT seeded here: it is a unit a utility that bills
# sewer by equivalent dwelling units may pick, never the default for a service
# the ruling calls a share.
#
# BLAST RADIUS: this map is read by `_default_uoms_for` when a service is turned
# ON for a tenant and by `_enable_signup_services` when a tenant is created, so
# it governs services enabled FROM NOW. A tenant that already enabled storm water
# keeps whatever its `tenant_services` row holds — **this is a default, never a
# backfill, and nothing rewrites a stored unit.** The one thing that DOES move
# every existing row is migration `tenancy 0030`, and it moves the BASIS only:
# a basis every tenant got wrong is not a preference anybody expressed.


class ServiceDefault(NamedTuple):
    """One row of the signed table above.

    ⚠ **THE FIELD ORDER IS LOAD-BEARING: `primary` and `alt` STAY AT INDEX 0 AND
    1.** This map has been read POSITIONALLY since it was written — `mapping[0]`
    and `mapping[1]` in `_default_uoms_for`, `SERVICE_DEFAULT_UOMS.get(code,
    (None,))[0]` in two test modules, and *"the second entry in
    SERVICE_DEFAULT_UOMS[gas]"* in a third. Putting `basis` first would leave
    every one of those reading a basis where a unit belongs, and a NamedTuple
    would let them do it in SILENCE — `("kWh", "kW")` and `("metered", "kWh")`
    are both perfectly good tuples. It goes last, where nothing indexes.
    """

    primary: str | None
    alt: str | None
    basis: str


SERVICE_DEFAULT_UOMS: dict[str, ServiceDefault] = {
    "electric": ServiceDefault("kWh", "kW", models.BILLING_BASIS_METERED),
    "water": ServiceDefault("kgal", "ccf", models.BILLING_BASIS_METERED),
    # SWAPPED 2026-09-02 — the seed now agrees with the signed $1.15 per ccf.
    "gas": ServiceDefault("ccf", "therm", models.BILLING_BASIS_METERED),
    # ── CR-081 · SEWER HAS A QUANTITY FROM 2026-09-08, IN WATER'S UNIT ──────
    # ⚠ **THIS ROW READ `ServiceDefault(None, None, share)` UNDER THE COMMENT
    # *"No unit, by the ruling: a share of another service's money has no
    # quantity."*** That comment was true and is now FALSE, and it is quoted
    # rather than deleted (hard-won law 1). The PO re-signed the volume basis on
    # 2026-09-08 (`CR-081`, HUMAN-GUIDE §6): sewer bills **90% of the water
    # VOLUME** at its own rate, so it has a quantity, and a quantity is never
    # carried without an explicit unit (hard rule 3).
    #
    # **THE UNIT IS WATER'S, WHICH IS WHY THIS ROW MIRRORS WATER'S EXACTLY.** A
    # utility metering water in `ccf` bills sewer in `ccf`. This map is a SEED —
    # it decides what a fresh tenant's sewer row is offered — and the authority
    # at bill time is the BASIS service's actual unit, which `engine.price_bill`
    # copies onto the line from the water tariff. The two cannot disagree on a
    # bill; if a tenant re-scopes water to `ccf` on Settings, the sewer LINE
    # follows water and this seed does not have to.
    #
    # **THE BASIS STAYS `share`.** Sewer still reads no register and still has
    # no meter — `CR-081` gives it a borrowed quantity, not a measured one — so
    # nothing here re-bases it onto metering or onto an asset count.
    #
    # ⚠ **CONSEQUENCE, STATED RATHER THAN LEFT TO BE REDISCOVERED: `kgal`
    # WIDENS from `water` back to All services**, because `_derive_uom_service_
    # scope` (below) NULLs any unit two services claim, and sewer now claims it.
    # That is the SAFE direction the derivation's own docstring names — a picker
    # offering more, never less — and it is required: a sewer schedule whose
    # `uom` is `kgal` must be constructible on a fresh tenant.
    "sewer": ServiceDefault("kgal", "ccf", models.BILLING_BASIS_SHARE),
    "trash": ServiceDefault("cart", None, models.BILLING_BASIS_CAPACITY),
    "storm_water": ServiceDefault("ERU", None, models.BILLING_BASIS_CAPACITY),
    # `kW`, not `panel` — PO statement (6) SUPERSEDES statement (4) (`CR-062`).
    "solar": ServiceDefault("kW", None, models.BILLING_BASIS_CAPACITY),
    "broadband": ServiceDefault("Mbps", None, models.BILLING_BASIS_CAPACITY),
    # ── CR-080 · THERMAL IS CAPACITY-BASED FROM 2026-09-07 ──────────────────
    # PO: *"connected tonnage - it is capacity not metering; i will ahve 100
    # tonne or 200 tonne etc"*. It read `ServiceDefault("ton-hr", "klb",
    # metered)` until that day. **The basis and the unit moved in ONE edit** —
    # the paragraph above the map says why they must — and `klb` stays in the
    # alt slot because it is STEAM's unit and `OQ-560` is still open.
    #
    # **It SUMS, like solar and battery, not COUNTS like trash and fire.** The
    # 2026-08-27 ruling is *"multiplier replaces bands for capacity services"*,
    # so a building with a 100-ton and a 25-ton connection is 125 tons, and
    # `service_size_classes.capacity_uom_for_service("thermal_heat")` answers
    # `"ton"` rather than `None`. That call is the mechanical test.
    "thermal_heat": ServiceDefault("ton", "klb", models.BILLING_BASIS_CAPACITY),
    "battery": ServiceDefault("kW", None, models.BILLING_BASIS_CAPACITY),
    # ── CR-063 · THE ELEVENTH SERVICE (PO 2026-09-02) ────────────────────────
    # *"We will need Fire as utility Service - Capacity based - this will behave
    # exactly like trash"*.
    #
    # ⚠ **`capacity` HERE MEANS TRASH'S ARITHMETIC AND NOT SOLAR'S, AND THE TWO
    # ARE THE SAME WORD FOR TWO DIFFERENT SUMS.** A `capacity` service either
    # COUNTS what is installed (trash: 3 carts x $15.00 = $45.00) or SUMS it
    # (solar: 2 + 4 + 8 kW = 14 kW x $14.00 = $196.00). *"Exactly like trash"*
    # settles it — **fire COUNTS** — and the mechanical test is
    # `service_size_classes.capacity_uom_for_service("fire")`, which answers
    # `None` exactly as trash's does. One 2" line bills $12.00; one 6" line and
    # two 2" lines bill $60.00 + 2 x $12.00 = $84.00.
    #
    # ⚠ **THE UNIT IS `connection` AND NOT `line`, AND THE ORIGINAL REASON WAS
    # THE HYDRANT — WHICH THE PO HAS SINCE REMOVED (2026-09-03).** The argument
    # was that a private hydrant is not a line and both were billed off this one
    # tick, so a unit named for one would be wrong for the other. `HYD` has left
    # fire's size list, so that argument no longer applies. **The unit does not
    # move anyway, for two independent reasons:** a fire line IS a service
    # connection, so `connection` was never wrong for it; and `BR-TEN-072`
    # forbids renaming a code already seeded, with `BR-TEN-071` making it
    # pointless for every tenant that already holds one. Recorded here rather
    # than quietly left, because a reader who checks WHY this says `connection`
    # would otherwise find a reason that no longer exists (hard-won law 1).
    "fire": ServiceDefault("connection", None, models.BILLING_BASIS_CAPACITY),
}


def _derive_uom_service_scope() -> dict[str, str | None]:
    """CR-004 task A3 / DEF-184 — the seeded scope, DERIVED from the map above.

    The PO's ruling gives each UoM entry ONE service or none (*"every entry can
    be scoped to one service or all"*), and `SERVICE_DEFAULT_UOMS` is the only
    ratified statement in the repo about which unit belongs to which service.
    So the scope is computed from it rather than typed a second time — a second
    hand-kept list is a second thing to drift, and the two would disagree the
    first time a service's default changed.

    **A UNIT NAMED BY MORE THAN ONE SERVICE STAYS NULL, AND THAT IS THE WHOLE
    RULE.** The map is not a partition: `ccf` is water's alt AND gas's primary,
    `kW` is electric's alt AND battery's primary. One nullable column cannot say
    "water or gas", and inventing a join table to say it would be resolving a
    question nobody asked. NULL already means "All services", so a shared unit
    lands there and every service is still offered it — which is the SAFE
    direction: the failure this closes is a picker offering TOO MUCH, never too
    little.

    ── **WHAT THE 2026-09-02 RULING MOVED, BECAUSE THE MAP UNDER THIS FUNCTION
    CHANGED** (`BR-TEN-1180`, `DEF-3230`) ──────────────────────────────────────
    With the ten-service map, the derivation now answers:

        kWh          → electric      (named by electric alone)
        kgal         → NULL, All services  (water AND sewer — `CR-081`,
                                      2026-09-08; it was `water` alone from the
                                      day storm water moved to ERU until then)
        therm        → gas           (gas alone — it is gas's ALT now, not its
                                      primary, and this function does not care
                                      which slot a claim comes from)
        cart         → trash
        ERU          → storm_water
        Mbps         → broadband
        klb          → thermal_heat  (steam's unit; DEF-2396)
        ton          → thermal_heat  (CR-080, 2026-09-07)
        ccf          → NULL, All services  (water's alt AND gas's primary)
        kW           → NULL, All services  (electric's ALT, battery's primary
                                      AND solar's primary — THREE services)
        month        → absent from the map entirely; no service names it now

    **TWO SCOPES ACTUALLY MOVE, and both are stated rather than left to be
    rediscovered:**

    * **`kW` WIDENS from `electric` to All services, and THREE services name it —
      say so rather than leaving it looking like a two-service coincidence.**
      Battery is priced per kW (PO: *"Battery - capacity based"*, and on the unit
      itself *"Im okay with it"*), and **solar joined them under `CR-062`
      statement (6)**, which reversed solar from a COUNT of panels to the SUM of
      their capacities: three panels of 2 kW, 4 kW and 8 kW are **14 kW**, and a
      count would say *"3"*. The scope would be NULL with only two claimants and
      is NULL with three; what changes is that a later reader cannot mistake it
      for an accident of two. This is the safe direction — a picker offering more
      — and it is the rule above doing exactly what it says.
    * **`kgal` NARROWED from All services to `water`** on 2026-09-02, and
      **WIDENED BACK on 2026-09-08 (`CR-081`)**, which is worth reading as one
      story rather than two edits. It was shared originally because storm water
      was seeded `kgal`, which is the very cell the PO corrected (*"Storm water -
      it is capacity based not unmetered"*); narrowing is the RISKY direction and
      was accepted deliberately, since the seed governs NEW rows only and no
      stored unit is rewritten. **Sewer now claims `kgal` and `ccf` too**, because
      `CR-081` gives sewer a quantity in the BASIS service's unit, so the shared
      unit lands back at NULL — the SAFE direction, and the one that lets a fresh
      tenant's sewer schedule actually state `kgal`.

    ── **WHERE THIS MAP AND `lookup_defaults.json` DISAGREE, AND WHO WINS** ────
    ⚠ **THE FIXTURE ONLY WINS WHERE IT SPEAKS.** `_seed_uoms` resolves a new row
    as `stated or SEEDED_UOM_SERVICE_SCOPE.get(code)` — so a fixture entry that
    CARRIES a `"service"` key overrides this function, and a fixture entry that
    carries none is decided HERE. That distinction is worth spelling out because
    it is the opposite of what "the fixture is authoritative" sounds like:

    * `cart`, `ERU`, `Mbps`, `ton-hr`, `ton` and `klb` each STATE their service
      in the
      fixture, and this function derives the same answer for every one it still
      names. **`ton-hr` is the exception since `CR-080` and it is a SAFE one:**
      thermal declares `ton` now, so this function makes no claim on `ton-hr`
      at all and the fixture's stated `thermal_heat` is unopposed. The two
      statements agree wherever both speak, so nothing can move whichever one
      is read.
      **`panel` is NOT among them and is not in the catalogue at all** — it was
      going to be, and `CR-062` statement (6) removed the need for it before it
      shipped (task B5).
    * `kWh`, `kW`, `kgal`, `ccf`, `therm` and `month` state NOTHING in the
      fixture. Their scope is whatever this function returns — which is why the
      two movements above are real movements and not cosmetic ones.

    A test asserts that no unit is scoped one way here and another way in the
    fixture, so the day somebody adds a `"service"` key to `kgal` the
    contradiction is a red test rather than a silent re-scope.

    So a water service is offered kgal and ccf and is REFUSED therm — DEF-184's
    exact symptom — while nothing legitimate is taken away.
    """
    claims: dict[str, set[str]] = {}
    for service_code, row in SERVICE_DEFAULT_UOMS.items():
        # ⚠ `row` is a `ServiceDefault`, so iterating it would sweep up `basis`
        # and scope a unit called "capacity" to five services. The two UNIT
        # slots are named explicitly for that reason.
        for unit in (row.primary, row.alt):
            if unit:
                claims.setdefault(unit.lower(), set()).add(service_code)
    return {unit: (next(iter(o)) if len(o) == 1 else None) for unit, o in claims.items()}


#: unit code (lowercased) → the service it is scoped to at seed time, or None
#: for "All services". Derived once at import; see `_derive_uom_service_scope`.
SEEDED_UOM_SERVICE_SCOPE: dict[str, str | None] = _derive_uom_service_scope()

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "lookup_defaults.json"

# Seed routing (BR-TEN-012/013/031): list_code → owning module (None = tenancy).
# DEF-017 (2026-08-10): the six lists below the rule were NEVER here, so nothing
# ever tried to seed them and no report ever said so. Owners are LOOKUP_LISTS'
# own owner strings — the registry and the seeder must not disagree about who
# owns a list, and `test_reference_data_completeness.py` asserts they do not.
SEED_LIST_OWNERS: tuple[tuple[str, str | None], ...] = (
    ("uoms", None),
    ("charge_codes", "rating"),
    ("tax_jurisdictions", "rating"),
    ("discount_program_owners", "rating"),  # CR-166-BRC10 · seeded from the drawing
    ("discount_exclusivity_groups", "rating"),  # CR-166-BRC10
    ("discount_eligibility", "rating"),  # CR-166-BRC10
    ("reason_codes", "billing"),
    ("payment_methods", "payments"),
    # ── DEF-017: the six that were in no fixture and no seeder ──────────────
    ("meter_types", "metering"),  # BR-AST-043 · routed metering → assets
    ("read_methods", "metering"),  # BR-AST-043 · routed metering → assets
    ("asset_types", "metering"),  # BR-AST-004/009/042 · routed metering → assets
    ("asset_statuses", "metering"),  # BR-AST-031 · routed metering → assets
    # DEF-017's SEVENTH list, added 2026-08-10. `premises_types` was in NEITHER
    # registry, although apps.metering.services.seed_reference_list has handled
    # the list code since it was written and says so in its own docstring. The
    # consequence: the only way a tenant ever got premises types was the
    # side effect of `ensure_reference_catalogs()` on a premises WRITE — so a
    # tenant that had not yet added a premises had none, the S16 wizard could
    # not resolve a type, and nothing anywhere reported it. No seed-run ledger
    # row, no audit row, no line in the reference-data report: the one list
    # whose absence was invisible. The fixture carries no `premises_types`
    # entries on purpose — metering's own BR-MET-034 SEED_PREMISES_TYPES is the
    # single ratified source, and its seeder falls back to it for an empty list.
    ("premises_types", "metering"),  # BR-MET-034 · metering-hosted table
    # W2 customers slice (2026-08-10): both routes are now LIVE — the module
    # owns its tables and authors seed_reference_list.
    ("account_statuses", "customers"),  # BR-CUS-055 · per-tenant lookup rows
    # ── CR-004 (2026-08-16): the six r10 SET-04 lists, tenancy-HOSTED and
    # owned elsewhere. Owner strings name the TRUE owner, not the host, which
    # is what test_reference_data_completeness asserts against LOOKUP_LISTS.
    ("areas", "metering"),
    # RENAMED 2026-08-27 by BR-TEN-170 (PO: *"it is utility service size class"*).
    # The list_code moves; the hosted TABLE is still `meter_size_classes` and that
    # split is stated in the rule and tracked as DEF-970 — a table rename is a B2
    # schema change with its own migration, RLS policy rewrite and review.
    ("service_size_classes", "metering"),
    ("occupancy_statuses", "metering"),
    ("device_types", "metering"),
    ("certification_types", "metering"),
    # CR-039 wave C task 12 (BR-TEN-150) — the five the PO ratified on
    # 2026-08-27, seeded from lookup_defaults.json like every other flat list.
    ("owner_categories", "metering"),
    ("import_mappings", "ledger"),
    # ⚠ PLATFORM rows until the PO ruling of 2026-09-17 ("utility can get their
    # own account types"). Now TENANT rows like every other list here: eight
    # seed per tenant (BR-CUS-094's seven + the `government` legacy code) and a
    # replay creates 0 because the seam is insert-missing by natural key.
    ("account_types", "customers"),
    # ── CR-010 (PO 2026-08-17, decision log "Part-10 confirmations" 10.0 +
    # A-section items 1/4): two new tenant-extensible lists, both seeded from
    # their owning module's ratified constants (the fixture deliberately
    # carries no entries — the DEF-026 premises_types posture).
    ("account_subtypes", "customers"),  # BR-CUS-067 · the two-level tree's tenant rows
    ("unit_types", "metering"),  # BR-MET-084 · UNIT_TYPES tuple → editable rows
    # ── CR-059 CS-18 (2026-09-01): reconciliation difference reasons ────────
    # The fixture deliberately carries NO entries — the DEF-026 `premises_types`
    # posture. `apps.payments.bankrec_models.SEED_DIFFERENCE_REASONS` is the
    # single ratified source and payments' own seeder falls back to it for an
    # empty list, so there is no second copy to drift.
    ("bank_rec_difference_reasons", "payments"),
    # ── CR-070 wave C (2026-09-04): the Work module's five lists ────────────
    # The fixture deliberately carries NO `work_*` entries — the DEF-026
    # `premises_types` posture. `apps.work.models.SEED_*` are the single
    # ratified source and `apps.work.services.seed_reference_list` falls back
    # to them for an empty list, so there is no second copy to drift.
    #
    # ⚠ **PRIORITIES BEFORE TYPES, AND THE ORDER IS LOAD-BEARING.** A seeded
    # job type names its default priority BY CODE (*Reconnect → Urgent*), so
    # the priorities must already be rows when the types are written or all
    # eight land with a NULL default and r10's own defaults quietly disappear.
    # `test_us_wrk_007_types.py` asserts the eight, so it would not stay
    # broken — but it would be a puzzling half-hour, which is what this
    # comment is for.
    ("work_priorities", "work"),
    ("work_order_types", "work"),
    ("work_skills", "work"),
    ("work_safety_kits", "work"),
    ("work_parts_categories", "work"),
    # `CR-168-BRC10` P0.4 (judgment J1) — why a job is held; a lookup, never a
    # CHECK list. `work/0028` seeds the tenants that already exist.
    ("work_hold_reasons", "work"),
)

# ── BR-TEN-067 (CONFIRMED, PO 2026-08-10, OQ-082) ───────────────────────────
# The S111 "Load standard charge codes & reference data" toggle governs SAMPLE
# CONTENT. It does not govern the STRUCTURAL CATALOGUES below, which are
# vocabulary the schema itself requires: an account cannot exist without a
# status, a premises cannot be created without a type (BR-MET-034), an asset
# cannot be classified without its type and lifecycle stage. Turning the toggle
# off used to leave a tenant that literally could not create its first record,
# with eleven empty dropdowns and no way to fill them from the UI.
#
# These ALWAYS seed, toggle or no toggle. ⚠ **`account_types` JOINED THEM ON
# 2026-09-17** (PO: *"utility can get their own account types"*). It was
# deliberately absent while r5 #12 [D5] made it a PLATFORM table with no
# tenant_id, seeded by migration customers.0003 before any tenant existed, so
# the toggle never governed it. Now the rows are the tenant's own and
# `accounts.account_type_id` is NOT NULL, which is the `owner_categories`
# argument exactly: a tenant whose toggle emptied this list could not create an
# account at all.
#
# Narrows US-TEN-002 TC-2 ("toggle off ⇒ all lists empty") — see
# tests/test_us_ten_002_seeding.py, amended with this rule cited.
STRUCTURAL_REFERENCE_LISTS: frozenset[str] = frozenset(
    {
        "meter_types",  # BR-AST-043
        "read_methods",  # BR-AST-043
        "asset_types",  # BR-AST-004/009/042
        "asset_statuses",  # BR-AST-031 lifecycle stages
        "account_statuses",  # BR-CUS-055 — an account cannot exist without one
        # PO ruling 2026-09-17 — `accounts.account_type_id` is NOT NULL, so an
        # account cannot exist without one of these either.
        "account_types",
        "premises_types",  # BR-MET-034 — create_premises cannot resolve a type
        # CR-004 (decision log 2026-08-16, PO-delegated): structural because a
        # unit that cannot be given an occupancy status has undefined BILLING
        # behaviour — tenant-billed / owner-billed / base-only / no-billing.
        "occupancy_statuses",
        # Structural by consistency with asset_types and meter_types above: a
        # device row needs a type to exist.
        "device_types",
        # CR-039 wave C task 12 (BR-TEN-150 clause 3). NOT by analogy:
        # `premises_owners.category_id` is NOT NULL, so a tenant whose toggle
        # emptied this list could not record a premises owner at all — which is
        # the exact state BR-TEN-067 was written to prevent.
        "owner_categories",
        # CR-166-BRC10: *Who qualifies* is REQUIRED on every discount and the
        # form offers only this list, so a utility whose toggle emptied it
        # could not create one. The other two discount lists ride with it so
        # the form never draws an empty dropdown beside a full one.
        "discount_program_owners",
        "discount_exclusivity_groups",
        "discount_eligibility",
    }
)

# ── DEF-016: the silent skip becomes a written-down, machine-checkable fact ──
# BR-TEN-013 skip-until-wired is LAW and is not broken here: an unwired owning
# module still legitimately skips its list. What changes is that the skip can no
# longer hide. A declared reference list that ends up EMPTY must appear in THIS
# register with a reason; an empty list that is NOT registered is reported as
# UNEXPLAINED by `reference_data_report()`, which makes `seed_demo` exit
# non-zero and fails `tests/test_reference_data_completeness.py`.
#
# That is precisely the DEF-016 condition: before rating authored
# `seed_reference_list`, `charge_codes` was empty and unregistered, so both the
# gate-style test and the command would have gone red instead of writing
# "honestly skipped" into a summary nobody reads (BR-TEN-056 clause 3).
#
# To add an entry here you have to state WHY in prose that a reviewer reads —
# which is the point. Removing an entry is what "the lane landed" looks like.
#
# EMPTY IS THE GOAL STATE, and 2026-08-10 is the day it was reached: the W2
# customers SCHEMA + SEAM slice landed `account_statuses` and `account_types`
# as real tables with a real `apps.customers.services.seed_reference_list`, so
# the last two entries came OUT. An empty register means every declared
# reference list is genuinely seeded — it does NOT mean the register is
# obsolete, and the next module that declares a list before it can seed one
# writes its reason here exactly as before.
#
# Consequences that were waiting on those two rows, now unblocked:
#   · BR-TEN-065 — the sample-data job can create its sample account
#     `Pending activation`, because that status row now exists.
#   · The two S8 Reference-data cards can render (apps/customers/lookups.py
#     registers their handlers), so `reference_data_report()` can COUNT them
#     instead of answering "unwired".
#
# ⚠ `account_types` WAS seeded by MIGRATION customers.0003 and not per tenant,
# because r5 #12 [D5] made it a PLATFORM table with no `tenant_id`. **The PO
# reversed that on 2026-09-17** — it seeds per tenant like every other list, a
# fresh tenant's run creates EIGHT, and a replay creates 0 meaning "this tenant
# already has them". `customers.reference_seed_omissions` used to explain the
# old 0 and is now empty, because the sentence it carried had become false.
UNSEEDABLE_REFERENCE_LISTS: dict[str, str] = {
    # DEF-203 (2026-08-28). NOT a gap waiting on a lane, and the first entry
    # here that is expected to be PERMANENT.
    "bank_accounts": (
        "'bank_accounts' is a tenant's OWN banking relationship — the name their "
        "staff recognise ('Chase Operating') and the last digits their bank "
        "statement prints. No platform fixture can carry one, because nobody but "
        "the utility knows what their accounts are called, and a seeded example "
        "would be a fake bank account sitting in a picker that imports real "
        "money. So this list is EMPTY on every freshly provisioned tenant BY "
        "DESIGN and stays empty until a System Admin adds one on Settings → "
        "Configure → Reference data → Bank accounts (BR-PAY-850). It is the one "
        "declared list that seeding will never fill; the entry is not waiting on "
        "an unwired seam and removing it would put the list back into DEF-016's "
        "UNEXPLAINED state."
    ),
    # EMPTY OTHERWISE — and the entry that stood here is worth its epitaph.
    # `import_mappings` was registered 2026-08-16 as "deliberately seeded with
    # nothing" (a mapping describes the tenant's own file layout, so a FIXTURE
    # cannot carry one — that half is still true and tenant maps are still
    # never fixture-seeded). BR-AST-048 (PO 2026-08-22, CR-028) superseded the
    # empty-list half: each assets import target now ships ONE system default
    # template GENERATED from the runner's own target contract — the same
    # source as the CR-025 sample CSV — so the known-good sample round-trips
    # with zero mapping work and nothing hand-written can drift. The entry
    # came out because the list genuinely seeds now, which is what removing an
    # entry looks like. The register itself stays, for the next module that
    # declares a list before it can seed one.
}

_EIN_RE = re.compile(r"^\d{2}-?\d{7}$")  # BR-TEN-018: NN-NNNNNNN, stored as 9 digits
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")  # BR-TEN-019
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ── shared plumbing ─────────────────────────────────────────────────────────
def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _tenant_row(*, locked: bool = False) -> models.Tenant:
    qs = models.Tenant.objects.all()
    if locked:
        qs = qs.select_for_update()
    row = qs.filter(pk=_tenant_id()).first()
    if row is None:
        raise errors.NotFoundError()
    return row


def _audit(
    actor: Any,
    action: str,
    entity_type: str,
    entity_id: Any,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """BR-TEN-016: one audit row per Settings/provisioning write, via BE-03."""
    actor_user_id = getattr(actor, "id", None) or getattr(actor, "pk", None)
    core_audit.write_row(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        before=before,
        after=after,
    )


def _field_error(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


def _refuse_fields(field_errors: list[dict[str, Any]]) -> None:
    if field_errors:
        raise errors.ValidationError(
            field_errors[0]["code"],
            message_key=field_errors[0]["message_key"],
            params=field_errors[0]["params"],
            field_errors=field_errors,
        )


def mask_ein(ein: str | None) -> str | None:
    """BR-AUD-006: PII enters the trail masked only."""
    if not ein:
        return ein
    return "**-***" + ein[-4:]


# ── signup validation (US-TEN-001 §5 field map) ─────────────────────────────
def _validate_signup(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="signup.payload_not_object")
    fe: list[dict[str, Any]] = []

    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        fe.append(_field_error("name", errors.VAL_REQUIRED, "signup.name_required"))
    elif len(name.strip()) > 120:
        fe.append(_field_error("name", errors.VAL_RANGE, "signup.name_too_long", max=120))

    subdomain = payload.get("subdomain")
    if not isinstance(subdomain, str) or not subdomain.strip():
        fe.append(_field_error("subdomain", errors.VAL_REQUIRED, "signup.subdomain_required"))
        subdomain = ""
    else:
        subdomain = subdomain.strip().lower()
        problem = selectors.subdomain_problem(subdomain)
        if problem is not None:
            code = errors.VAL_RANGE if problem == "length" else errors.VAL_FORMAT
            fe.append(_field_error("subdomain", code, "signup.subdomain_invalid", problem=problem))

    state = payload.get("state")
    state_code: str | None = None
    if state is not None:
        state_code = selectors.us_state_code(str(state))
        if state_code is None:
            fe.append(_field_error("state", errors.VAL_UNKNOWN_LOOKUP, "signup.state_unknown"))

    currency = payload.get("currency") or "USD"
    if str(currency).upper() not in active_currency_codes():
        fe.append(
            _field_error(
                "currency",
                errors.VAL_UNKNOWN_LOOKUP,
                "signup.currency_unknown",
                allowed=list(active_currency_codes()),
            )
        )
    currency = str(currency).upper()

    plan_code = payload.get("plan") or "growth"  # S112: Growth pre-selected
    plan = models.SubscriptionPlan.objects.filter(
        code=str(plan_code), deleted_at__isnull=True
    ).first()
    if plan is None:
        fe.append(_field_error("plan", errors.VAL_UNKNOWN_LOOKUP, "signup.plan_unknown"))

    services_billed = payload.get("services")
    service_codes: list[str] = []
    if not isinstance(services_billed, list) or not services_billed:
        fe.append(_field_error("services", errors.VAL_REQUIRED, "signup.services_required"))
    else:
        known = set(models.Service.objects.filter(active=True).values_list("code", flat=True))
        for code in services_billed:
            code_str = str(code)
            if code_str not in known:
                fe.append(
                    _field_error(
                        "services",
                        errors.VAL_UNKNOWN_LOOKUP,
                        "signup.service_unknown",
                        service=code_str,
                    )
                )
            elif code_str not in service_codes:
                service_codes.append(code_str)

    owner = payload.get("owner")
    owner_out: dict[str, Any] = {}
    if not isinstance(owner, dict):
        fe.append(_field_error("owner", errors.VAL_REQUIRED, "signup.owner_required"))
    else:
        email = owner.get("email")
        if not isinstance(email, str) or not _EMAIL_RE.match(email.strip()):
            fe.append(_field_error("owner.email", errors.VAL_FORMAT, "signup.owner_email_invalid"))
        full_name = owner.get("full_name")
        if not isinstance(full_name, str) or not full_name.strip():
            fe.append(
                _field_error("owner.full_name", errors.VAL_REQUIRED, "signup.owner_name_required")
            )
        password = owner.get("password")
        if not isinstance(password, str) or not password:
            fe.append(
                _field_error(
                    "owner.password", errors.VAL_REQUIRED, "signup.owner_password_required"
                )
            )
        owner_out = {
            "email": str(email).strip() if isinstance(email, str) else "",
            "full_name": str(full_name).strip() if isinstance(full_name, str) else "",
            "password": password if isinstance(password, str) else "",
            "phone": (str(owner.get("phone")).strip() or None) if owner.get("phone") else None,
        }

    _refuse_fields(fe)
    return {
        "name": str(name).strip(),
        "subdomain": subdomain,
        "state": str(state).strip() if state is not None else None,
        "state_code": state_code,
        "currency": currency,
        "tax_region": (
            (str(payload.get("tax_region")).strip() or None) if payload.get("tax_region") else None
        ),
        "plan": plan,
        "services": service_codes,
        "load_defaults": bool(payload.get("load_defaults", True)),
        "owner": owner_out,
    }


# ── provisioning (US-TEN-001/002/004 · flows §2/§3) ─────────────────────────
def _portal_website(subdomain: str) -> str | None:
    """A new utility's default website: its customer portal's address,
    `PUBLIC_APP_ORIGIN` + `/<slug>/portal` — the same address Settings › Portal
    shows and its QR code encodes (`portal.selectors.address_for`).

    ⚖️ PO ruling 2026-10-05 (decision log *"FIVE PO RULINGS IN ONE REPLY"* (5),
    `DEF-TEN-9720`), verbatim: *"(a) New utilities get their portal address
    (https://app.bynry.com/brazosbend/portal). Existing utilities keep what
    they have and can edit it."* Until then sign-up seeded
    `https://smartbillhub.com/<slug>`, a host this product does not serve,
    which seven customer messages print as *"View or pay at
    {utility_website}"*.

    ⚠ **FAILS CLOSED (law 3):** `core.public_origin` answers `None` for an
    unset or malformed setting, and the website is then left BLANK — a
    Company-tab checklist gap — rather than a guessed address on a letter.
    Only sign-up calls this; no stored value is ever rewritten (there is no
    data migration), and the field stays editable on Settings › Company.
    """
    from core import public_origin

    origin = public_origin.public_app_origin()
    if origin is None:
        return None
    return f"{origin}/{subdomain}/portal"


def provision_tenant(
    payload: Any, *, ip: str | None = None, user_agent: str | None = None
) -> dict[str, Any]:
    """S114 commit: ONE atomic transaction (BR-TEN-010) — tenant + owner (via the
    identity seam) + owner session + trial subscription + services + number
    series + optional reference seed. Idempotent on the subdomain natural key:
    a replay with the same subdomain + owner email returns the EXISTING tenant
    unchanged.

    `ip` / `user_agent` are recorded on the owner's session (the caller's, from
    the request); a CLI caller such as `manage.py seed_demo` passes neither.

    **A REPLAY NEVER GETS A SESSION** (`owner_session_id` is None on that path).
    BR-TEN-010 matches a replay on subdomain + owner email and checks NO
    password, so minting a session there would hand a live login to anyone who
    can guess a public slug and an owner address. Only the branch that actually
    created the owner — the one that verified the password the caller chose —
    may return one.
    """
    data = _validate_signup(payload)

    existing = models.Tenant.objects.filter(subdomain=data["subdomain"]).first()
    if existing is not None:
        return _replay_or_conflict(existing, data)

    attempted_id = uuid7()
    try:
        with transaction.atomic():
            try:
                # Nested savepoint so the commit-time UNIQUE race (US-TEN-004
                # TC-2) surfaces as a lawful 409, not a broken transaction.
                with transaction.atomic():
                    tenant = models.Tenant.objects.create(
                        id=attempted_id,
                        name=data["name"],
                        subdomain=data["subdomain"],
                        state=data["state"],
                        currency=data["currency"],
                        tax_region=data["tax_region"],
                        provisioned_at=timezone.now(),
                        # CR-010 10.3 (PO 2026-08-17: *"please provdie default
                        # where we can provide dont keep it null"*, then *"im
                        # okay with your suggestions"*). SEVEN fields seed from
                        # facts the signup already gave us or the platform
                        # already renders; the five that stay NULL — EIN,
                        # state utility id, both addresses, support phone,
                        # logo — stay because a fabricated tax id or remit-to
                        # address on a bill is a FALSE FACT, not a default
                        # (ruled on the same artifact row), and each is an S62
                        # checklist item. Every one is tenant-editable on
                        # Settings → Company.
                        legal_name=data["name"],
                        dba_name=data["name"],
                        support_email=data["owner"]["email"],
                        remit_payable_to=data["name"],
                        service_hours="Mon–Fri 8:00 AM–5:00 PM",
                        # The product's own placeholder brand — already what
                        # every screen renders when the hexes are unset, now
                        # stated so the Company tab shows the real values.
                        brand_primary_hex="#1B5E9E",
                        brand_accent_hex="#0F7A6B",
                        # ⚖️ DEF-TEN-9720 — the utility's PORTAL ADDRESS (PO
                        # 2026-10-05 (5)); blank when the environment names no
                        # public address. See `_portal_website`.
                        website=_portal_website(data["subdomain"]),
                    )
            except IntegrityError as exc:
                raise errors.BizError(
                    errors.BIZ_STATE,
                    br_ref="BR-TEN-011",
                    message_key="signup.subdomain_taken",
                    params={"subdomain": data["subdomain"]},
                ) from exc
            with core_tenancy.tenant_context(tenant.id):
                result = _provision_inside_context(tenant, data, ip=ip, user_agent=user_agent)
    except (errors.BizError, errors.ValidationError, errors.AuthError):
        raise  # lawful refusals: BE-02 answers; nothing was committed
    except Exception as exc:
        # BR-TEN-001/016: the transaction rolled back — nothing remains; the
        # failure leaves an ops trace with NO PII (US-TEN-004).
        _record_provision_failure(attempted_id, data["subdomain"], exc)
        raise
    # CR-010 new mandate 1 (PO 2026-08-17): a NEW tenant is PLANTED with the
    # sample set — same job/orchestrator as the S8 panel and load_sample_data,
    # never a second seeder — AFTER the transaction above has committed
    # (BR-TEN-063: the plant's failure never fails provisioning; C-15 rules
    # incompleteness SOFT: S62 flag + loud trail, tenant still opens). Gated
    # by the S111 load_defaults toggle — BR-TEN-067 narrows that toggle to
    # sample RECORDS, which is exactly what this plants.
    #
    # ⚠ CR-017 (PO 2026-08-19, *"otherwise they are left hi and dry"*): the
    # plant's JOB RECORD travels back in the response. It is the only thing on
    # this path that can honestly answer *"what is happening in the
    # background?"* — a real BE-07 record with a real status, real progress and
    # a real poll URL (`/api/jobs/{id}`), rather than a timer the screen makes
    # up. The screen S115 renders reads THIS, and reads it the same way in all
    # three of the deployment shapes the plant can be in (DEF-320):
    #   · JOBS_EAGER on  — the plant already ran inside this request, so the
    #     record comes back `succeeded` and the screen draws the completion.
    #   · JOBS_EAGER off with a runner — `queued`/`running`, and the screen
    #     narrates it as it goes.
    #   · JOBS_EAGER off with NO runner (DEF-320, the deployed build today) —
    #     `queued` forever, and the screen says the tenant is ready and the
    #     sample data has not landed, which is exactly C-15's soft posture.
    # `None` is a REAL answer, not a missing field: no sample plant was asked
    # for (the S111 toggle is off), or the job machinery itself refused.
    sample_plant: dict[str, Any] | None = None
    if data["load_defaults"]:
        from apps.tenancy import sample_data as tenancy_sample_data

        with core_tenancy.tenant_context(tenant.id):
            record = tenancy_sample_data.enqueue_provisioning_plant(
                owner_user_id=result.get("owner_user_id")
            )
            if record is not None:
                sample_plant = {
                    **core_jobs.accepted(record),
                    # The status AT RESPONSE TIME. Not authority — the poll URL
                    # is — but it saves the screen a round trip in the eager
                    # case, where the job is already finished before the caller
                    # can possibly ask.
                    "status": (selectors.job_poll(record["id"]) or record)["status"],
                    "total": len(tenancy_sample_data.SAMPLE_MODULES),
                    # ── CR-064 task A1 (PO 2026-09-02) ──────────────────────
                    # *"list down all 17 steps"*. The catalogue travels with
                    # the commit response so the screen can name every step
                    # BEFORE the first poll answers and before any block has
                    # finished — which is the half of the request `total: 17`
                    # could never satisfy, because a count is not a list.
                    # It is the tuple in source order and holds no outcome:
                    # what each step DID arrives on the poll (`steps`, from
                    # `job_poll`), and the two are keyed the same way so the
                    # screen joins them without a second catalogue.
                    "steps": tenancy_sample_data.step_catalogue(),
                }
    result["sample_plant"] = sample_plant
    return result


def _provision_inside_context(
    tenant: models.Tenant,
    data: dict[str, Any],
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    # Owner FIRST (BR-TEN-013 via the identity seam): if identity cannot create
    # the login, the whole tenant must not exist (BR-TEN-001).
    owner_user_id = seams.provision_owner(
        tenant_id=tenant.id,
        email=data["owner"]["email"],
        full_name=data["owner"]["full_name"],
        password=data["owner"]["password"],
        phone=data["owner"]["phone"],
    )
    # …and their session, in the SAME transaction (PO 2026-08-10, supersedes
    # BR-TEN-045). Optional seam: None means "no session issued", and the owner
    # signs in at /{subdomain}/signin exactly as the superseded rule described.
    owner_session_id = seams.start_owner_session(
        tenant_id=tenant.id, user_id=owner_user_id, ip=ip, user_agent=user_agent
    )
    trial_ends_at = tenant.provisioned_at + timedelta(days=TRIAL_DAYS)  # BR-TEN-014
    models.Subscription.objects.create(
        tenant=tenant, plan=data["plan"], status="trial", trial_ends_at=trial_ends_at
    )
    # ── CR-039 wave F task 25/27 (PO 2026-08-27) ────────────────────────────
    # *"when utility will do cofiguration, data migrton by themself then it is
    # self serve and we dont have to implment it - how you want to handle it,
    # youc anhave 0 month implmentaiton"*.
    #
    # ⚠ **THE ROW IS THE POINT, AND UNTIL NOW NOTHING WROTE IT.** The decision
    # log of 2026-08-27 chose a zero-month ORDER over the absence of one because
    # *"a row and no row are different things to a report"* — with the row,
    # *"how many customers are self-serve?"* is one query and the answer is a
    # fact. `tenancy 0021` landed the table and `order_no` as a column NO LINE
    # OF CODE HAD EVER WRITTEN, which is task 27's *"its own numbering"*
    # describing something that did not exist.
    #
    # Written HERE, beside the subscription, because it is the same kind of
    # fact about the same event: what this utility bought when it signed up.
    # Inside the provisioning transaction, so a tenant can never exist without
    # its commercial record — the same reason the subscription is here.
    implementation_order = platform_numbering.create_self_serve_order(
        tenant, on=tenant.provisioned_at.date()
    )
    # The zone is prefilled from the state collected at signup (PO 2026-08-10).
    # CR-010 ruling 7 (PO 2026-08-17: *"yes this is good"*) SUPERSEDES the old
    # posture here, which was "a default is only worth writing where the signup
    # already told us the answer" and left ELEVEN regional fields NULL — no
    # date format, no fiscal-year start, until a human opened the tab. The
    # US-first set below was put to the PO field by field with its values and
    # ratified; every one stays tenant-editable on Settings → Company →
    # Regional, and every spelling is drawn from this module's own validated
    # vocabularies (DATE_FORMATS[0], NUMBER_FORMATS[0], …) so the seed can
    # never write a value the save path would refuse.
    #
    # `accounting_method` is deliberately ABSENT: the PO removed that control
    # (CR-008 ruling 1 — it had zero readers), so seeding a value would revive
    # a claim the product does not honour. `close_day` "last day" is the
    # monthly-close convention the PO confirmed as "Monthly, last day".
    models.TenantSettings.objects.create(
        tenant=tenant,
        timezone=default_timezone_for_state(data["state_code"]),
        country="United States",
        language="en-US",
        date_format=DATE_FORMATS[0],  # MM/DD/YYYY
        number_format=NUMBER_FORMATS[0],  # 1,234.56
        time_format=TIME_FORMATS[0],  # 12-hour
        first_day_of_week=FIRST_DAYS_OF_WEEK[0],  # sunday
        fy_start_month=1,
        fy_start_day=1,
        close_cadence="monthly",
        close_day="last day",
        # CR-060 C7 / task T2 — SEEDED, never left unknown. The column carries
        # the same default (tenancy 0029), so this line changes no behaviour;
        # it is here because the seed is a RULE (BR-TEN-1050) and the eleven
        # regional fields above are seeded explicitly for the same reason. A
        # reader looking for what a new tenant starts as reads this list.
        organisation_type=models.ORGANISATION_TYPE_UTILITY,
    )

    actor_shim = type("Actor", (), {"id": owner_user_id})()
    # S111 toggle (BR-TEN-012: discretionary seeding only when on) — NARROWED by
    # BR-TEN-067 (CONFIRMED, PO 2026-08-10): the structural catalogues seed
    # either way, because they are the operator's real vocabulary and not sample
    # content. An account cannot exist without a status; a premises cannot be
    # created without a type. The toggle governs sample RECORDS.
    seed_summary = _seed_reference_data(
        tenant,
        data["state_code"],
        actor_shim,
        structural_only=not data["load_defaults"],
    )

    _seed_number_series(tenant)
    # THIS YEAR **AND NEXT** (DEF-042). One year runs out, silently, in January:
    # a bill due Thu 24 Dec 2026 with 5 business days' grace must charge on Tue
    # 5 Jan 2027, and that answer needs 1 Jan 2027 to be in the calendar. With
    # the sign-up year alone the fee landed Mon 4 Jan — a day early, ON a public
    # holiday. This is the ONLY caller allowed to seed a calendar from empty
    # (see `ensure_us_holidays_through`): here, empty means the tenant is new;
    # everywhere else it means the tenant deleted the dates on purpose.
    _this_year = selectors.tenant_today().year
    _seed_us_holidays(tenant, _this_year)
    _seed_us_holidays(tenant, _this_year + 1)
    # The chart of accounts, then the services (BR-BIL-010; PO rulings
    # 2026-08-11 closing OQ-106/OQ-115, REVERSED IN PART 2026-08-17 by CR-010
    # B-9 + New mandate 4 — see _enable_signup_services).
    #
    # THE ORDER IS LOAD-BEARING AGAIN, the way it originally was (amended
    # 2026-08-18): the seed plants the FULL 33-row chart (*"9 - A full ~40
    # accounts for every tenant, as you said"*), and `_enable_signup_services`
    # then creates a `tenant_services` row for ALL TEN catalog services —
    # signup's picks enabled, the rest present-but-off — pointing each at the
    # accounts the seed just planted (*"more is better ; less is contraint"*).
    # Seeding second would leave every pointer NULL on the way in; the ledger
    # function tolerates it (it mints on demand), but the order spares ten
    # pointless mint attempts and keeps the audit trail reading
    # `provisioning_seed` for what provisioning seeded.
    seams.seed_chart_of_accounts(actor_shim)
    # ── CR-040 task A2 · BR-PAY-150 (PO ruling 2026-08-27, closing OQ-490) ──
    # *"reconcilaition is a seperate problem - (a) Undeposited funds is the
    # answer for every tender - no chart change, nothing to re-sign, and the
    # demo's cash sits in one bucket by design"*.
    #
    # AFTER the chart, ALWAYS: the mapping points at a row `seed_chart_of_accounts`
    # has just planted, so running it before would find no account and write
    # nothing. Reference data (the seven tenders themselves) is seeded further
    # up, so both halves exist by the time this line runs and neither ordering
    # is a coincidence — see `_map_tender_clearing_accounts`.
    _map_tender_clearing_accounts(tenant, actor_shim)
    _enable_signup_services(tenant, data["services"], actor_shim)
    # ── THE SECOND REFERENCE PASS, AND IT HAS TO BE HERE ────────────────────
    # `_seed_reference_data` ran ~40 lines up, BEFORE any service was enabled,
    # because `_enable_signup_services` points each `tenant_services` row at
    # UoM rows that pass plants. `work_order_types` is the first list whose
    # ROWS depend on the tenant's services (PO 2026-09-07: a water-only utility
    # gets eighteen sub-types, a water-and-gas one gets twenty-two), so it is
    # topped up here, insert-missing, the moment the enablement rows exist.
    # Without this line every tenant would receive the common twenty-seven and
    # not one service row, silently and with every test green.
    seed_summary["service_scoped"] = _seed_service_scoped_reference_data(tenant, actor_shim)
    # ── CR-066 (PO ruling 2026-09-02) · closing DEF-2386 ────────────────────
    # *"Table 1 — the 28 charge codes - these are all correct - you can apply
    # them as part of Seed data"* — and the phrase that is the whole scope is
    # **"as part of Seed data"**. The fix is not 28 rows on one tenant; it is
    # that every tenant this product creates from here on receives charge codes
    # that already point at accounts.
    #
    # ⚠ **WITHOUT THESE TWO LINES A FRESH TENANT CANNOT ISSUE A BILL THAT
    # CARRIES A FEE.** `apps/billing/issue.py` resolves a USAGE or BASE line from
    # the SERVICE's designation and a FEE line from `charges.gl_account_id`, and
    # refuses the whole bill when that column is null. Measured on PostgreSQL 16
    # on 2026-09-02: a tenant provisioned from empty held **28 charge codes
    # pointing nowhere** while its sample estate issued 95 invoices, because
    # every line the estate writes is usage or base. Two of the seeded codes
    # (`PAPER`, `HYDRANT`) are `recurring` and `BR-RAT-117` puts a recurring code
    # on the ordinary bill of every tenant that configures one, so ONE unmapped
    # charge refuses a whole run.
    #
    # **THE ORDER IS LOAD-BEARING, TWICE OVER.** After `seed_chart_of_accounts`
    # because the mapping points at rows it plants; after
    # `_enable_signup_services` because a BASE charge code resolves through
    # `tenant_services.revenue_account`, which that call writes. Running either
    # way round earlier finds no account and writes nothing — safe, and still a
    # tenant that cannot bill.
    seams.rating_apply_default_gl_accounts(actor_shim)
    _map_reason_code_accounts(tenant, actor_shim)
    # The FALLBACK BILL TEMPLATE and its published version (DEF-123, 2026-08-16).
    #
    # WHY A NEW TENANT NEEDS THIS BEFORE IT NEEDS ANYTHING ELSE BILLING OWNS:
    # BR-BIL-026 pins a template version on every bill at issue and makes the pin
    # non-optional, so a tenant with no template cannot issue a bill AT ALL —
    # `templates_service.resolve_for` refuses with BR-BIL-025's own sentence. For
    # the day between `bill_templates` landing and this line, that was the state
    # of every tenant on every deployment: the lifecycle service was complete and
    # correct, its tests passed against rows the TESTS created, and nothing in
    # the product ever wrote one. Hard-won law 2 (*built is not wired*) applied
    # to DATA rather than to a component prop — which is exactly why G13 saw
    # nothing and why G25 now asks the question of every required row.
    #
    # Same shape as the chart of accounts above and for the same reasons: a
    # SEAM resolved by name (tenancy never touches billing's ORM — BR-TEN-013),
    # inside this transaction, insert-missing so a repair run repairs. The date
    # is the TENANT's today and is passed IN — billing reads no clock (BR-TEN-043).
    #
    # ⚠ THIS REACHES NEW TENANTS ONLY. A tenant provisioned before this line
    # existed still has no template, exactly as a host with an existing `.env`
    # never sees a template change (hard-won law 4). The repair for those is
    # `manage.py seed_demo --tenant <subdomain>`, which calls the same seam;
    # G25's data clause is what makes an un-repaired tenant loud instead of
    # silent.
    seams.seed_bill_templates(actor_shim, on_date=selectors.tenant_today())
    # THE NOTICE TEMPLATES (DEF-163, 2026-08-16) — the same hole, one module on.
    #
    # A bill template lets a tenant ISSUE; a notice template lets it CHASE. With
    # no published body `template_service.resolve` refuses by name, so
    # `notices.generate_reminder` and `generate_disconnect_notice` refuse and
    # NOTHING IS QUEUED — every dunning letter and every disconnection notice on
    # every deployment, for as long as the lifecycle service existed with no
    # seeder in front of it.
    #
    # ⚠ THIS PLANTS TWO CLASSES, NOT TWENTY, AND THE SHORTNESS IS THE RULE.
    # A body is what a customer reads, so only classes a signed spec writes in
    # full are planted: `dunning` and `receipt`, both quoted verbatim from A13.
    # The disconnect notice (OQ-243), the payment-plan agreement (OQ-244) and
    # the email/SMS/contract/plan-notice classes (OQ-206/OQ-207) are left ABSENT
    # WITH THEIR REASON, which `GET /notification-templates` serves per class and
    # the S8 Notifications tab draws. Inventing a 10-day regulated notice or a
    # 48-hour certified letter would put words in a utility's mouth that look
    # official the moment they are written.
    #
    # ⚠ NEW TENANTS ONLY — hard-won law 4 in its data form. A tenant provisioned
    # before this line has no notice template and never will from here; the
    # repair is `manage.py seed_demo --tenant <subdomain>`, which calls the same
    # seam, insert-missing.
    seams.seed_notice_templates(actor_shim, on_date=selectors.tenant_today())

    # CR-010 item 7 (PO 2026-08-17): the dispatch-settings row is WRITTEN here
    # rather than materialised on first read, so the S8 Notifications tab opens
    # populated and "which tenants have a notifications row" is answerable from
    # the database. Values are the model's own ratified column defaults (email
    # and SMS dispatch OFF — the unsafe option is the one you type); the
    # first-read get_or_create stays as the repair path for older tenants.
    #
    # ⚠ AND THE SET-12 RULE ROWS WITH IT — DEF-258, 2026-08-19. The PO's
    # sentence names two things: *"the NotificationSettings row is to be
    # WRITTEN at provisioning … and the SET-12 rule rows with it"*. Only the
    # first half landed a day earlier, and the live database said so plainly:
    # `notification_settings` carried this line's timestamp and
    # `notification_rules` carried one twenty hours later, written the moment a
    # lane opened the screen. Until then the honest answer to *"has this
    # utility configured its notifications?"* was zero rows — the same
    # ambiguity this line removed for the dispatch row.
    #
    # Nothing about SENDING changes: BR-NOT-005 and BR-NOT-013 stand, and the
    # larger half of DEF-258 (no queue writer reads these rows) stays open as a
    # wiring story.
    seams.seed_notification_settings(actor_shim)

    # CR-011 item 8 (PO 2026-08-18, *"you decide"*): the SECURITY-POLICY row,
    # for the same reason and in the same shape as the line above it.
    #
    # `identity.selectors.security_policy_values` has always served an UNSAVED
    # `SecurityPolicy(tenant_id=…)` when no row exists, so the effective policy
    # of a tenant that never opened the Security tab was a set of PYTHON CLASS
    # DEFAULTS. That is fine until the ratified figures move: BR-IDN-025's
    # minimum going 8 → 10 would tighten every un-opened tenant's password rule
    # on deploy, with no author, no before/after and no `audit_log` row, because
    # nothing was ever saved. It also made "which tenants have configured
    # security?" unanswerable — 0 rows meant "never looked".
    #
    # NOTHING CHANGES FOR ANY TENANT TODAY: the row is written at the model's
    # own column defaults, which are exactly what the read-side fallback
    # returns. Only the storage moves.
    #
    # ⚠ NEW TENANTS ONLY (hard-won law 4, data form). `seed_reference_data_for_
    # tenant` carries the same call for `manage.py seed_demo --tenant <sub>`,
    # which is the repair door for every tenant that already exists.
    seams.seed_security_policy(actor_shim)

    # DEF-251 (CR-010 item 11(b), failure-mode map §7.1): the METER-READ
    # VALIDATION row. `apps.metering.services.ensure_read_validation_settings`
    # has described itself as *"Provisioning entry point … Tenancy owns
    # provisioning, so it calls this"* since the day it was written, and this
    # line is the first time that sentence has been true — the only callers in
    # the whole repository were two test files, and the live database held
    # ZERO rows for the only tenant on the system.
    #
    # Nothing crashed, which is why it survived: every threshold rule the read
    # checker owns reports `not_evaluated: validation config missing` rather
    # than running, and the single-read correction path does not even say that
    # much. A brand-new utility's high-usage and zero-usage checks simply never
    # fired. **Any object whose absence fails SILENTLY is a defect by
    # definition** — the PO's own rule, and the reason this line exists.
    #
    # OPTIONAL seam, like the four above it: an unwired metering leaves the
    # tenant exactly as it was. ⚠ NEW TENANTS ONLY (hard-won law 4 in its data
    # form) — the repair for tenants provisioned before this line is
    # `manage.py seed_demo --tenant <subdomain>`, which calls the same seam.
    seams.seed_read_validation_settings(actor_shim)

    _audit(
        actor_shim,
        "tenant.provisioned",
        "tenant",
        tenant.id,
        after={
            "name": tenant.name,
            "subdomain": tenant.subdomain,
            "plan": data["plan"].code,
            "services": data["services"],
            "trial_ends_at": trial_ends_at.isoformat(),
            "load_defaults": data["load_defaults"],
            # CLAUDE.md hard rule 7 — every money action writes `audit_log`.
            # The implementation order carries a money column, and the action
            # that creates it IS this provisioning: it rides on this row rather
            # than adding a second one, because a signup is one event and two
            # rows would invite a reader to look for two causes.
            "implementation_order_no": implementation_order.order_no,
            "implementation_duration_months": implementation_order.duration_months,
            "implementation_price": str(implementation_order.price),
        },
    )
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "subdomain": tenant.subdomain,
        "created": True,
        "trial_ends_at": trial_ends_at.isoformat(),
        "owner_user_id": str(owner_user_id),
        # SERVER-SIDE ONLY: api.py turns this into the Set-Cookie header and
        # drops the key. A session id in a JSON body is a credential in the
        # SPA's memory, its logs and its error reports — the cookie is httpOnly
        # for exactly that reason.
        "owner_session_id": owner_session_id,
        "reference_seed": seed_summary,
    }


def _replay_or_conflict(existing: models.Tenant, data: dict[str, Any]) -> dict[str, Any]:
    """BR-TEN-010: same subdomain + same owner email = replay → the existing
    tenant, row counts untouched. Anything else = 409 (US-TEN-001 TC-3)."""
    with core_tenancy.tenant_context(existing.id):
        known_email = seams.owner_email_for(existing.id)
    if known_email is not None and known_email.strip().lower() == data["owner"]["email"].lower():
        subscription = (
            models.Subscription.objects.filter(tenant=existing).order_by("created_at").first()
        )
        return {
            "id": str(existing.id),
            "name": existing.name,
            "subdomain": existing.subdomain,
            "created": False,
            "trial_ends_at": (
                subscription.trial_ends_at.isoformat()
                if subscription and subscription.trial_ends_at
                else None
            ),
            "owner_user_id": None,
            # No password was checked on this path — see provision_tenant().
            "owner_session_id": None,
            "reference_seed": {
                "version": None,
                "seeded": {},
                "skipped": [],
                "skipped_reasons": {},
                "structural_only": False,  # a replay seeds nothing at all
            },
        }
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-TEN-011",
        message_key="signup.subdomain_taken",
        params={"subdomain": data["subdomain"]},
    )


def _record_provision_failure(tenant_id: UUID, subdomain: str, exc: Exception) -> None:
    """US-TEN-004 / BR-TEN-016: `tenant.provision_failed` ops trace, no PII.
    Best-effort by design — the failure answer must never be masked by a
    trail problem (same posture as BE-03 refusal_attempt)."""
    try:
        with core_tenancy.tenant_context(tenant_id):
            core_audit.write_row(
                action="tenant.provision_failed",
                entity_type="tenant",
                entity_id=tenant_id,
                actor_user_id=None,
                after={"subdomain": subdomain, "error": type(exc).__name__},
            )
    except Exception:  # pragma: no cover - defensive
        logger.exception("tenant.provision_failed trace could not be written")


def _load_seed_fixture() -> dict[str, Any]:
    """Versioned platform fixture (BR-TEN-012). Missing/corrupt → the WHOLE
    provisioning transaction rolls back (US-TEN-002 TC-4)."""
    try:
        with open(FIXTURE_PATH, encoding="utf-8") as fh:
            fixture = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise errors.SysError(
            errors.SYS_INTERNAL,
            message_key="signup.reference_fixture_invalid",
            params={"reason": type(exc).__name__},
        ) from exc
    if not isinstance(fixture, dict) or not isinstance(fixture.get("version"), str):
        raise errors.SysError(
            errors.SYS_INTERNAL,
            message_key="signup.reference_fixture_invalid",
            params={"reason": "missing version"},
        )
    return fixture


def _seed_reference_data(
    tenant: models.Tenant, state_code: str | None, actor: Any, *, structural_only: bool = False
) -> dict[str, Any]:
    """US-TEN-002: per-list idempotent copy of the versioned fixture. Lists owned
    by other modules route through their seam; a not-yet-wired owner is honestly
    SKIPPED (no seed-run row) and reported — never guessed (BR-TEN-013/031).

    DEF-016: `skipped` stays a plain list of codes (its existing contract), but
    the summary now also carries `skipped_reasons` — code → why, taken from
    UNSEEDABLE_REFERENCE_LISTS where the gap is a known one and marked
    UNEXPLAINED where it is not. `reference_data_report()` is the surface that
    turns that into a non-zero signal; nothing here decides to fail, because an
    unwired seam legitimately skips (BR-TEN-013) and provisioning must still
    commit a working tenant (BR-TEN-001).

    `structural_only` is BR-TEN-067 (CONFIRMED, PO 2026-08-10): the S111 toggle
    governs sample content, never the STRUCTURAL_REFERENCE_LISTS vocabulary the
    schema requires. Provisioning passes it when the toggle is OFF, so a tenant
    that declined the defaults still gets account statuses, premises types and
    the asset catalogs — and nothing else.

    ⚠ **`tax_jurisdictions` IS NOT LATCHED BY ITS SEED-RUN ROW, AND DEF-444 IS
    WHY.** Every other list here depends only on the fixture version, so "this
    tenant was seeded at V2.19.0.0" is a complete answer. This one also depends
    on `tenants.state` — a column the SIGN-UP FORM DOES NOT REQUIRE and the S8
    Regional tab can fill in afterwards. So a tenant that signed up without
    naming a state received the `ALL` scaffold (County · City · Special
    district, no rate, no authority), got a run row at the current version, and
    could then **never** receive Texas State, Local, the PUC, the City franchise
    fee or the TWDB surcharge — not from a re-run, not from a version bump
    (`reference_sweep` defers every discretionary list under OQ-088), not from
    the `--tenant` repair door, which read the run row and skipped. The live
    tenant reached plan wizard step 5 reading *"No tax jurisdictions exist yet"*
    and **no customer on any plan could be taxed.**

    ⚠ **AND SINCE CR-077 (2026-09-07) THAT PARAGRAPH IS ABOUT FIFTY-ONE MORE
    STATES.** The catalogue now holds a set for every code in
    `selectors.US_STATES` — the fifty states plus DC and Puerto Rico — so the
    same latch would strand an Iowa utility on County · City · Special district
    exactly as it stranded the Texas one, and the symptom would be the same
    sentence on the same screen. The exemption below is what carries them, and
    `tests/test_cr077_fifty_state_tax_jurisdictions.py` asserts it on IOWA
    rather than on the state it was originally fixed for, because a fix proved
    only on its own defect is a fix nobody has tested twice.

    The owning module's seeder is insert-missing by natural key (BR-TEN-012), so
    re-offering this one list costs one query on a replay and writes nothing. A
    second run row is NOT created and no audit row is written when nothing
    arrived — a replay is still silent, which is what BR-TEN-010 asks for.
    """
    fixture = _load_seed_fixture()
    version = fixture["version"]
    summary: dict[str, Any] = {
        "version": version,
        "seeded": {},
        "skipped": [],
        "skipped_reasons": {},
        "structural_only": structural_only,
    }
    for list_code, owner_module in SEED_LIST_OWNERS:
        if structural_only and list_code not in STRUCTURAL_REFERENCE_LISTS:
            continue  # BR-TEN-067: the toggle is off and this list is discretionary
        if list_code == "tax_jurisdictions":
            entries = tax_jurisdiction_entries(fixture, state_code)
            if not entries:
                # ⚠ THIS USED TO BE A BARE `continue` AND THAT SILENCE IS HALF
                # OF DEF-444. A tenant left with no jurisdictions is
                # indistinguishable from a tenant that legitimately levies no
                # tax, and only a human looking at plan wizard step 5 can tell
                # the two apart. Now it says which it is, in the summary
                # `reference_data_report()` already reads.
                summary["skipped"].append(list_code)
                summary["skipped_reasons"][list_code] = (
                    "DEF-444 — this tenant records no US state (`tenants.state` is empty), so "
                    "the platform catalogue has no per-state rows to apply and this fixture "
                    "version ships no `ALL` scaffold either. Record the state on Settings → "
                    "Company → Regional and the rows are delivered there."
                )
                continue
        elif list_code == "import_mappings":
            # BR-AST-048 (CR-028): the three system default templates are
            # GENERATED from the runner's own target contract — the same
            # source as the CR-025 sample CSV, so the two cannot drift. The
            # generator lives with the contract (metering) and is reached
            # seam-first; unwired ⇒ [] ⇒ the list seeds fixture-only (which is
            # nothing — tenant maps are never fixture-seeded, see the model).
            entries = list(fixture.get(list_code, [])) + _generated_import_mapping_entries()
        else:
            entries = fixture.get(list_code, [])
        already = models.ReferenceSeedRun.objects.filter(
            tenant=tenant, list_code=list_code, fixture_version=version
        ).exists()
        # US-TEN-002 TC-3: retry changes nothing — EXCEPT for the lists whose
        # entries depend on something other than the fixture version: the
        # per-state tax rows (DEF-444, the tenant's own `state` column) and —
        # since BR-AST-048 — the GENERATED mapping defaults, whose content
        # moves with the runner's target contract rather than the fixture. A
        # replay that finds nothing missing still creates nothing (the seeds
        # are insert-missing / refresh-system-only) and reports nothing.
        if already and list_code not in RERUN_REFERENCE_LISTS:
            continue
        if owner_module is None:
            count = _seed_uoms(tenant, entries)
        else:
            try:
                seeded = seams.seed_reference_list(owner_module, list_code, entries, version)
            except KeyError:
                # CR-004 (2026-08-16): the owning module HAS a seeder but does
                # not handle this list code — apps.metering raises
                # `KeyError("metering owns no reference list 'areas'")` for the
                # six lists this change declares. That is the module saying "not
                # mine yet", which is the SAME fact as having no seeder at all,
                # so it takes the same path: fall through to tenancy's hosted
                # table below.
                #
                # Caught HERE rather than fixed in apps/metering deliberately.
                # Metering is another lane's territory, its KeyError is a
                # correct statement about what it owns (BR-TEN-031), and
                # silencing it there would make the module claim lists it does
                # not validate. Seam FIRST is preserved exactly: the moment
                # metering authors these codes it returns a count, no exception
                # is raised, and this branch stops running.
                seeded = None
            if seeded is None:
                hosted = HOSTED_LOOKUP_HANDLERS.get(list_code)
                if hosted is None:  # owner lane not authored — skip-until-wired
                    summary["skipped"].append(list_code)
                    summary["skipped_reasons"][list_code] = UNSEEDABLE_REFERENCE_LISTS.get(
                        list_code,
                        f"UNEXPLAINED — apps.{owner_module}.services.seed_reference_list is not "
                        f"wired and {list_code!r} has no row in "
                        "apps.tenancy.services.UNSEEDABLE_REFERENCE_LISTS. This is the DEF-016 "
                        "shape: a list nobody can seed and nobody wrote down.",
                    )
                    continue
                # The owner's seeder is not authored, but tenancy HOSTS this
                # list's table (see the ReasonCode/PaymentMethod docstrings), so
                # the fixture lands here rather than nowhere — the card would
                # otherwise render empty forever. Seam FIRST, always: the moment
                # the owning lane authors seed_reference_list it wins, and this
                # fallback stops running (BR-TEN-013/031).
                count = hosted().seed(tenant, entries)
            else:
                count = int(seeded)
        if not already:
            models.ReferenceSeedRun.objects.create(
                tenant=tenant, list_code=list_code, fixture_version=version, seeded_count=count
            )
        elif count == 0:
            # A REPLAY OF THE PER-STATE LIST THAT FOUND NOTHING MISSING. No
            # second run row, no audit row, nothing in the summary — a re-run
            # that changes nothing must LOOK like it changed nothing
            # (BR-TEN-010), or the honest report becomes noise nobody reads.
            continue
        _audit(
            actor,
            "reference.seeded",
            "reference_list",
            None,
            after={"list": list_code, "fixture_version": version, "count": count},
        )
        summary["seeded"][list_code] = count
    return summary


#: Reference lists whose ENTRIES depend on which utility services this tenant
#: has switched ON — not merely which rows a picker later offers.
#:
#: ⚠ **THEY CANNOT BE SEEDED BY `_seed_reference_data` AND THAT IS AN ORDERING
#: FACT, NOT A PREFERENCE** (decision log 2026-09-07, *"the second reference
#: pass"*). `provision_tenant` runs the reference pass BEFORE
#: `_enable_signup_services`, because a `tenant_services` row points at the UoM
#: rows that pass plants — reversing the two would leave every unit pointer
#: NULL. So at reference time there is not one enabled service in the database,
#: and a seeder that filters on enablement sees an empty set and quietly seeds
#: the common rows only.
#:
#: **Nothing was broken by this before 2026-09-07**: `uoms` and
#: `service_size_classes` are service-SCOPED but seed every row for every
#: tenant and let the pickers filter, and both say so in their own docstrings.
#: `work_order_types` is the first list where the PO ruled that the ROWS
#: THEMSELVES differ — *"a water-only utility gets exactly the eighteen and
#: nothing else"* — so it is the first that needs a second pass.
SERVICE_ENABLEMENT_REFERENCE_LISTS: tuple[str, ...] = ("work_order_types",)


def _seed_service_scoped_reference_data(tenant: models.Tenant, actor: Any) -> dict[str, int]:
    """Re-offer the lists above, AFTER the tenant's services are enabled.

    Called twice and from nowhere else: by `provision_tenant`, immediately
    after `_enable_signup_services`, and by `_apply_service_toggle` the moment
    a clerk switches a service ON months later — because *"a utility that picks
    water and gas gets the eighteen plus the four gas ones"* has an obvious
    other half, and a utility that adds gas in March should not have to notice
    that its crews cannot raise a gas leak call-out.

    Every owning seeder here is insert-missing by natural key (`BR-TEN-012`),
    so this writes NOTHING on a replay, nothing for a service already seeded,
    and no `reference_seed_runs` row at all — the run row belongs to the
    reference pass and this is a top-up of it, not a second run of it. A pass
    that creates nothing is silent, which is what `BR-TEN-010` asks for.

    Returns list_code → rows created, for the caller's summary. An unwired
    owner returns None from the seam and is skipped exactly as it is upstream.
    """
    fixture_version = str(_load_seed_fixture().get("version") or "")
    owners = dict(SEED_LIST_OWNERS)
    added: dict[str, int] = {}
    for list_code in SERVICE_ENABLEMENT_REFERENCE_LISTS:
        owner_module = owners.get(list_code)
        if owner_module is None:
            continue
        try:
            seeded = seams.seed_reference_list(owner_module, list_code, [], fixture_version)
        except KeyError:  # the owner does not claim this list — same as unwired
            seeded = None
        if not seeded:
            continue
        added[list_code] = int(seeded)
        _audit(
            actor,
            "reference.seeded",
            "reference_list",
            None,
            after={
                "list": list_code,
                "fixture_version": fixture_version,
                "count": int(seeded),
                "pass": "service_enablement",
            },
        )
    return added


def seed_reference_data_for_tenant(
    tenant: models.Tenant, actor: Any, *, structural_only: bool = False
) -> dict[str, Any]:
    """Seed/BACKFILL the REFERENCE DATA of a tenant that ALREADY EXISTS.

    The operator problem this closes: every reference list was seeded exactly
    once, inside the provisioning transaction of a brand-new tenant. A tenant
    that signed up before a list existed — or before its owning module authored
    a seam — had no way to get it, ever. `manage.py seed_demo --tenant <sub>`
    is that way, and this is the service behind it.

    REFERENCE DATA ONLY. No tenant row, no owner user, no subscription, no
    sample records — this never provisions and never touches money.

    Idempotent (BR-TEN-010 posture): `_seed_reference_data` skips any list that
    already has a `reference_seed_runs` row for this fixture version, and each
    owning module's seeder looks the entry up by its natural key before every
    create, so a replay writes nothing and changes no count. It runs in ONE
    transaction, so a mid-flight failure leaves no half-seeded list.

    The caller supplies the tenant context; the state code for the per-state
    lists comes from the tenant's own saved regional settings, never from the
    command line — a caller cannot re-key a tenant's tax jurisdictions to
    another state by passing a flag.

    `structural_only` (added 2026-08-15 with US-TEN-020's sweep) narrows the run
    to STRUCTURAL_REFERENCE_LISTS, the same narrowing provisioning applies when
    the S111 toggle is off (BR-TEN-067). The SWEEP passes it unconditionally,
    because OQ-088 (CLOSED, PO 2026-08-10) rules that *until*
    `tenants.reference_defaults_opted_in` exists, a version bump may deliver the
    structural vocabulary and NOTHING discretionary — "a tenant that asked for no
    charge codes must not receive them because a bump happened". `--tenant`
    backfill keeps the default False: an operator naming one tenant on the
    command line has stated the intent the column would have recorded.
    """
    # `tenants.state` is where signup and the S8 Regional tab both keep it
    # (REGIONAL_TENANT_FIELDS); a tenant that never filled it gets no per-state
    # list, exactly as an unset state does at provisioning.
    state_code = selectors.us_state_code(tenant.state) if tenant.state else None
    with transaction.atomic():
        summary = _seed_reference_data(tenant, state_code, actor, structural_only=structural_only)
        # CR-005: number series ride the SAME repair door. They are not a
        # reference LIST (no fixture, no `reference_seed_runs` row, no owning
        # seam), which is exactly why a tenant provisioned before a series
        # existed had no way to ever get it — `apps/ledger/manual_je.py` says so
        # in its own docstring about the missing `JE-` row, and every tenant on
        # the host was in that state. `_seed_number_series` skips what is
        # already there, so a replay changes nothing and an admin's edited
        # format is never overwritten.
        summary["number_series_created"] = _seed_number_series(tenant)
        # CR-040 task A2 — THE REPAIR DOOR for a tenant that already exists.
        # Hard-won law 4 in its data form: a provisioning change reaches a
        # tenant on the day it is created and never afterwards, and EVERY
        # tenant ever provisioned before 2026-08-27 carries seven NULL tender
        # pointers (DEF-891). Idempotent — a tender that already names an
        # account is left exactly as the tenant set it.
        summary["tenders_mapped"] = _map_tender_clearing_accounts(tenant, actor)["mapped"]
        # CR-066 task A3 — THE REPAIR DOOR, and hard-won law 4 again: a
        # provisioning change reaches a tenant on the day it is created and
        # never afterwards, so EVERY tenant provisioned before 2026-09-02
        # carries charge codes that point nowhere and cannot issue a bill
        # carrying a fee (DEF-2386). ⚠ **THE CHART IS TOPPED UP FIRST**: the
        # nine accounts CR-066 adds do not exist on any older tenant, so mapping
        # before seeding would find no row and write nothing.
        # `seed_chart_of_accounts` is insert-missing (*"rule 1: the tenant's
        # chart is the tenant's"*), so it adds the nine and leaves every
        # renumbered, renamed or deactivated row exactly as the tenant has it.
        #
        # ⚠ **BR-TEN-012 — NOTHING A TENANT SET IS OVERWRITTEN.** Both sweeps
        # filter on a NULL pointer and have no other branch, which is what makes
        # this safe to run as often as anyone likes.
        seams.seed_chart_of_accounts(actor)
        gl_defaults = seams.rating_apply_default_gl_accounts(actor) or {}
        summary["charges_gl_mapped"] = int(gl_defaults.get("charges_mapped") or 0)
        summary["charges_gl_unmapped"] = list(gl_defaults.get("charges_unmapped") or [])
        summary["discounts_gl_mapped"] = int(gl_defaults.get("discounts_mapped") or 0)
        summary["reasons_gl_mapped"] = _map_reason_code_accounts(tenant, actor)["mapped"]
        # CR-011 item 8 — THE REPAIR DOOR for a tenant that already exists.
        # A provisioning change reaches a tenant on the day it is created and
        # never afterwards (hard-won law 4 in its data form), and the only
        # tenant on the live host predates this by a day. Ride the same door
        # the number series ride, for the same reason: idempotent
        # get_or_create, so a replay writes nothing and an admin's edited
        # policy is never overwritten.
        policy = seams.seed_security_policy(actor)
        summary["security_policy_created"] = bool(policy and policy.get("created"))
        # ── BR-WRK-058 · the service-enablement pass, on the repair door too ──
        # `_seed_reference_data` above cannot deliver a list whose ROWS depend
        # on which services this tenant sells: at provisioning it runs before
        # enablement, and here it skips any list that already has a run row for
        # the current fixture version. So an operator repairing a tenant with
        # `seed_demo --tenant <sub>` would get every other list topped up and
        # the work order sub-types not — which is the shape this door exists to
        # close, one list over. Insert-missing, so a replay writes nothing.
        summary["service_scoped"] = _seed_service_scoped_reference_data(tenant, actor)
        return summary


def _seed_run_counts() -> dict[str, int]:
    """list_code → rows the owning module's seeder REPORTED creating for the
    tenant in context, read from tenancy's OWN `reference_seed_runs` ledger.

    This is evidence, not a count: it says a seed ran and what it wrote at the
    time. `reference_data_report()` uses it only to tell "seeded, but this
    process cannot count it" apart from "empty" — never to replace a live count.
    """
    ledger: dict[str, int] = {}
    for list_code, seeded_count in models.ReferenceSeedRun.objects.filter(
        tenant_id=_tenant_id()
    ).values_list("list_code", "seeded_count"):
        ledger[list_code] = max(ledger.get(list_code, 0), int(seeded_count or 0))
    return ledger


def _fixture_entry_key(entry: dict[str, Any]) -> str:
    """The NATURAL KEY of one fixture row — `code`, or `name` when the list has
    no code (BR-TEN-161(a), DEF-960).

    ⚠ **THIS IS THE THIRD FACE OF ONE DEFECT AND THE REASON IT GETS A NAME.**
    `tax_jurisdictions` has no `code` anywhere in its chain: no column on the
    table (BR-TEN-037 — the row is tenant-entered and its identity IS the name),
    no `code` key on its fixture rows (`{"name": "County", "level": "county"}`),
    and its handler's `serialize` bridges the gap by publishing `code: row.name`.
    A reader that asks for `entry["code"]` sees an empty list and reports **a gap
    of zero for a list that has one** — which is DEF-902 with the sign flipped
    and silent, the worst of the three failure modes because nothing raises.

    So the fixture side resolves its key exactly the way `_held_codes` resolves
    the held side, and the two then compare like with like. Written as a named
    function rather than an inline `or` so the next reader meets the RULE and
    not a defensive-looking expression.
    """
    return str(entry.get("code") or entry.get("name") or "")


def reference_list_fixture_gap(list_code: str) -> dict[str, Any]:
    """BR-TEN-161 — *"the data is correct and your tenant does not have it"*,
    said by the PRODUCT instead of by a person (DEF-902).

    For ONE reference list, for the tenant in context, answers: which entries
    does the platform fixture ship that this tenant does not hold?

        {"list", "fixture_version", "seeded_version", "missing": [{code, name}],
         "held": int, "fixture_entries": int, "sweep_delivers": bool}

    ── THE DEFECT THIS EXISTS FOR, WITH ITS MEASURED FIGURES ────────────────
    PO, on the live app at v2.61.1: *"in this setting - unable to see sub
    areas"*. `lookup_defaults.json` at `V2.48.0.2` ships **seven** area rows
    with their `parent_code` wiring; Silver Creek Water shows **four**. The
    fixture, the two-level depth cap and the Add-entry dialog are all correct
    and shipped — the tenant was simply PROVISIONED BEFORE the fixture grew,
    and nothing re-offers a reference list to a tenant that already has one.
    **The PO had ratified those three names that same morning (OQ-432) and
    then could not see them**, which is hard-won law 4 in its data form: a
    template change never reaches a host that already has one.

    ── WHY THIS IS A READ AND NOT A FIX ────────────────────────────────────
    The sweep cannot close the gap and BR-TEN-160 records why: `areas` is
    SAMPLE content under BR-TEN-067, `sweep_tenant()` passes
    `structural_only=True` unconditionally under OQ-088's CLOSED ruling, and
    adding `areas` to `STRUCTURAL_REFERENCE_LISTS` to make it sweep would
    silently widen what a tenant that DECLINED the defaults receives at
    provisioning. Whether the sweep should re-offer a list a tenant
    demonstrably already holds is **OQ-550**, routed to the PO and not decided
    here. So this function makes the gap VISIBLE and delivers nothing.

    ── THE COMPARISON IS BY NATURAL KEY, NEVER BY COUNT (BR-TEN-161a) ──────
    Codes, case-insensitively, because BR-TEN-030 makes a code unique per
    tenant case-insensitively. A count-only check calls a tenant that deleted
    one seeded row and added two of its own *current*, and it is not.

    ⚠ **A ROW THE TENANT DELETED READS AS MISSING.** No column records that a
    tenant removed a seeded row, so `missing` states the fact that can be
    proved — *this entry is in the platform list and not in yours* — and
    never asserts why. Stated here because the screen must not claim more.

    ⚠ **`seeded_version` IS THE HIGHEST VERSION IN THE TENANT'S OWN LEDGER
    FOR THIS LIST**, not the fixture's, and `None` means this list was never
    seeded to this tenant at all — a different sentence from "behind".
    """
    from apps.tenancy.reference_sweep import _fixture_entries, _held_codes, version_key

    lookup_handler(list_code)  # unknown / unwired list → 404, never an empty gap
    fixture = _load_seed_fixture()
    # ⚠ **THE SWEEP'S OWN RESOLVER, NOT A SECOND READING OF THE FILE.** Exactly
    # one list is not a plain array under its own key: `tax_jurisdictions` is a
    # dict keyed by STATE whose rows are the tenant's own state plus the `ALL`
    # scaffold (CR-010's tax ruling, DEF-444), and a naive `fixture[list_code]`
    # would iterate its KEYS and report a gap of zero for a list that has one.
    # `_fixture_entries` is the resolver both provisioning-side sites already
    # share, and sharing it a third time is the point: a screen that answered
    # "nothing is missing" while the seeder disagreed would be DEF-902 with the
    # sign flipped.
    state_code = (
        models.Tenant.objects.filter(pk=_tenant_id()).values_list("state", flat=True).first()
    )
    entries = [
        entry
        for entry in _fixture_entries(fixture, list_code, state_code)
        if isinstance(entry, dict) and _fixture_entry_key(entry)
    ]
    # ⚠ **AND THE HELD SIDE IS THE SWEEP'S READER TOO — `row.code` IS A BUG THIS
    # LANE WROTE AND ITS OWN TEST CAUGHT.** The first cut read `row.code` off the
    # queryset and answered **HTTP 500 `AttributeError: 'TaxJurisdiction' object
    # has no attribute 'code'`** for one list: `tax_jurisdictions` has no `code`
    # COLUMN at all (BR-TEN-037 — the table is tenant-entered and its identity is
    # the NAME), and its handler's `serialize` is what publishes `code: row.name`.
    # `_held_codes` already reads every list through the OWNING module's
    # registered handler for exactly that reason (BR-TEN-029/031), so this reuses
    # it rather than re-deriving it — and the tenant's held count then agrees with
    # the sweep's plan by construction rather than by luck.
    held_keys = _held_codes(list_code) or set()
    missing = [
        {"code": _fixture_entry_key(entry), "name": str(entry.get("name") or "")}
        for entry in entries
        if _fixture_entry_key(entry).strip().lower() not in held_keys
    ]
    versions = list(
        models.ReferenceSeedRun.objects.filter(
            tenant_id=_tenant_id(), list_code=list_code
        ).values_list("fixture_version", flat=True)
    )
    seeded_version = max(versions, key=version_key) if versions else None
    return {
        "list": list_code,
        "fixture_version": fixture["version"],
        "seeded_version": seeded_version,
        "missing": missing,
        # DISTINCT codes, which is `_held_codes`' own grain and the sweep's: a
        # count taken any other way could disagree with the set the comparison
        # was actually made against.
        "held": len(held_keys),
        "fixture_entries": len(entries),
        # BR-TEN-160: will an automatic sweep ever deliver these by itself?
        # The screen needs the answer to say what to DO, and a screen that
        # guessed it would drift the first time the structural set moved.
        "sweep_delivers": list_code in STRUCTURAL_REFERENCE_LISTS,
    }


def reference_data_report() -> dict[str, Any]:
    """DEF-016's NAMED SURFACE: 'these reference lists are EMPTY, and why'.

    One row per list declared in LOOKUP_LISTS, for the tenant in context:

        {"list", "owner", "count", "seed_run_count", "state", "reason"}

    `state` is one of
      · "seeded"      — the list has rows.
      · "empty"       — the list has NO rows and UNSEEDABLE_REFERENCE_LISTS
                        records why. A legitimate BR-TEN-013 skip, WRITTEN DOWN.
      · "UNEXPLAINED" — the list has no rows and nobody wrote down a reason.
                        THIS is DEF-016: charge codes were exactly this for the
                        whole of W0/W1 and the only trace was one WARNING line
                        in a summary nobody reads (BR-TEN-056 clause 3).
      · "unwired"     — no owning module has registered a handler, so the list
                        cannot even be counted; it is registered or UNEXPLAINED
                        on the same rule as "empty".
      · "uncounted"   — no handler EITHER, but `reference_seed_runs` proves the
                        list was seeded and how many rows landed. Added
                        2026-08-10 with DEF-017's seventh list. Reporting
                        `premises_types` as "empty" would have been false (it
                        has five rows) and reporting it as "seeded" would have
                        been a claim this process cannot check — so it gets its
                        own state, its own reason, and the ledger figure that
                        backs it. It is NOT counted as empty or unexplained,
                        because the data is there; what is missing is the S8
                        card, which needs the owning module to register a
                        lookup handler (BR-TEN-031).

    `unexplained` is the machine-checkable signal: non-empty means a caller
    should FAIL. `seed_demo` exits non-zero on it and
    tests/test_reference_data_completeness.py asserts it is empty — so the next
    list added without a seeder cannot reach a live tenant unnoticed.

    Read-only: it counts through each owning module's registered handler
    (BR-TEN-029/031), writes nothing, and needs an active tenant context.
    """
    ledger = _seed_run_counts()
    rows: list[dict[str, Any]] = []
    for list_code, definition in LOOKUP_LISTS.items():
        handler = definition.handler
        count = handler.count() if handler is not None else None
        seed_run_count = ledger.get(list_code, 0)
        registered = UNSEEDABLE_REFERENCE_LISTS.get(list_code)
        if count:
            state, reason = "seeded", None
        elif count is None and seed_run_count:
            state = "uncounted"
            reason = (
                f"{list_code!r} IS seeded — `reference_seed_runs` records {seed_run_count} "
                f"row(s) written by apps.{definition.owner} for this tenant — but no module "
                "has registered a lookup handler for it, so this process cannot count it "
                "live and its S8 Reference-data card cannot render. That is a FRAMEWORK gap "
                f"owned by apps.{definition.owner} (register_lookup_handler + the list's own "
                "CRUD services, BR-TEN-031), not a gap in the data. Reported here rather "
                "than shown as empty, which would be false."
            )
        elif registered is not None:
            state, reason = ("empty" if count == 0 else "unwired"), registered
        else:
            state = "UNEXPLAINED"
            reason = (
                f"{list_code!r} is "
                + ("EMPTY" if count == 0 else "not served by any registered handler")
                + " and has no row in apps.tenancy.services.UNSEEDABLE_REFERENCE_LISTS. "
                "Either wire its owning module's seed_reference_list seam "
                "(BR-TEN-013) or write the reason down there — a reference list "
                "may not be quietly absent (DEF-016)."
            )
        rows.append(
            {
                "list": list_code,
                "owner": definition.owner,
                "count": count,
                "seed_run_count": seed_run_count,
                "state": state,
                "reason": reason,
            }
        )
    return {
        "lists": rows,
        "empty": [row["list"] for row in rows if row["state"] in ("empty", "unwired")],
        "uncounted": [row["list"] for row in rows if row["state"] == "uncounted"],
        "unexplained": [row["list"] for row in rows if row["state"] == "UNEXPLAINED"],
    }


def reference_seed_omissions(state_code: str | None = None) -> list[dict[str, str]]:
    """The per-ENTRY half of the report: fixture entries their owning module
    will NOT create, and why (optional seam, [] where an owner offers none).

    Read-only and tenant-independent — it asks each owner about the FIXTURE, so
    it answers the same before and after a seed and is safe to print from a
    `--check`-style path. `seed_demo` already reports its own omissions this
    way for DEPO-R and the TOU windows; this is the same discipline applied to
    the platform seed every real signup runs.
    """
    fixture = _load_seed_fixture()
    notes: list[dict[str, str]] = []
    for list_code, owner_module in SEED_LIST_OWNERS:
        if owner_module is None:
            continue
        if list_code == "tax_jurisdictions":
            entries = tax_jurisdiction_entries(fixture, state_code)
        else:
            entries = fixture.get(list_code, [])
        if not entries:
            continue
        for note in seams.reference_seed_omissions(owner_module, list_code, entries):
            notes.append({"list": list_code, **note})
    return notes


#: The ONE reference list whose entries depend on a TENANT COLUMN as well as on
#: the fixture version — `tenants.state`, which sign-up does not require and the
#: S8 Regional tab can fill in at any time afterwards. Named once, because
#: DEF-444 is what happens when three places each assume the fixture version is
#: the whole cache key.
TENANT_STATE_REFERENCE_LIST = "tax_jurisdictions"

#: The lists a REPLAY re-runs despite an existing seed-run row, because their
#: entries depend on something other than the fixture version: the per-state
#: tax rows (DEF-444) and BR-AST-048's generated mapping defaults. Both seeds
#: are insert-missing/refresh-only, so a replay that finds nothing missing
#: writes nothing and reports nothing.
RERUN_REFERENCE_LISTS: frozenset[str] = frozenset({TENANT_STATE_REFERENCE_LIST, "import_mappings"})


def _generated_import_mapping_entries() -> list[dict[str, Any]]:
    """BR-AST-048's three defaults, GENERATED by the module that owns the
    target contract (metering's runner) and reached seam-first — tenancy never
    states an import target's columns itself, so the default and the CR-025
    sample cannot drift apart. [] while unwired: the list then seeds nothing,
    exactly as before BR-AST-048."""
    fn = seams.resolve("metering", "default_import_mapping_entries")
    if fn is None:
        return []
    return list(fn())


def deliver_state_tax_jurisdictions(tenant: models.Tenant, actor: Any) -> dict[str, Any]:
    """Apply this tenant's OWN STATE's tax jurisdictions — DEF-444.

    ⚠ **THIS EXISTS BECAUSE SEEDING RAN ONCE, BEFORE THE STATE WAS KNOWN.**
    `tenants.state` is OPTIONAL at sign-up (`_validate_signup` accepts a null
    `state`, and the wizard's step-1 validity check does not require the field),
    so a utility can be provisioned with no state at all. Reference seeding runs
    inside that provisioning transaction, resolves `tax_jurisdiction_entries`
    against `None`, and hands the tenant the `ALL` scaffold: County · City ·
    Special district, with no authority and **no tax**. The operator then fills
    the state in on Settings → Company → Regional, and until this function
    existed **nothing anywhere applied the catalogue again** — the run row said
    "seeded at this version", the version sweep defers every discretionary list
    (OQ-088), and the `--tenant` repair door read the same run row and skipped.
    The tenant stayed untaxable for good.

    ⚠ **IT IS GATED ON THE TENANT'S OWN RECORDED OPT-IN, WHICH IS OQ-088'S RULE
    RATHER THAN A CONVENIENCE.** Until `tenants.reference_defaults_opted_in`
    exists, *"declined"* and *"did not exist yet"* are the same absence, and a
    tenant that asked for no reference data must not receive some because a
    field changed. A `reference_seed_runs` row for this list IS that recorded
    opt-in: it can only have been written by a run that already delivered the
    list to this tenant. No row ⇒ no delivery, and the reason is returned.

    ⚠ **IT INVENTS NOTHING AND OVERWRITES NOTHING.** The rows come from the
    platform catalogue, through the OWNING module's seeder (BR-TEN-013/031),
    which is insert-missing by name and — under DEF-273's set-skip — prices
    nothing for a tenant that already holds any `taxes` row. BR-TEN-058 is
    untouched: this is tenancy applying its own reference catalogue, which is
    the opposite of a sample run writing into one.
    """
    state_code = selectors.us_state_code(tenant.state) if tenant.state else None
    if state_code is None:
        return {"delivered": 0, "reason": "the tenant records no US state"}
    if not models.ReferenceSeedRun.objects.filter(
        tenant=tenant, list_code=TENANT_STATE_REFERENCE_LIST
    ).exists():
        return {
            "delivered": 0,
            "reason": (
                "this tenant holds no tax_jurisdictions seed-run row, so it never opted in to "
                "reference defaults for this list — OQ-088: 'declined' and 'did not exist yet' "
                "are the same absence until tenants.reference_defaults_opted_in exists"
            ),
        }
    fixture = _load_seed_fixture()
    version = fixture["version"]
    entries = tax_jurisdiction_entries(fixture, state_code)
    if not entries:
        return {"delivered": 0, "reason": f"the platform catalogue has no rows for {state_code}"}
    count = int(
        seams.seed_reference_list("rating", TENANT_STATE_REFERENCE_LIST, entries, version) or 0
    )
    if count:
        _audit(
            actor,
            "reference.seeded",
            "reference_list",
            None,
            after={
                "list": TENANT_STATE_REFERENCE_LIST,
                "fixture_version": version,
                "count": count,
                "state": state_code,
            },
        )
        logger.info(
            "tenancy: %s recorded state %s, so %d tax-jurisdiction row(s) from the platform "
            "catalogue were applied (DEF-444)",
            tenant.subdomain,
            state_code,
            count,
        )
    return {"delivered": count, "state": state_code}


def tax_jurisdiction_entries(fixture: dict[str, Any], state_code: str | None) -> list:
    """The tax-jurisdiction rows this tenant seeds: its OWN state's rows PLUS
    the `ALL` scaffold.

    ⚠ **THE PARENTHESIS HERE READ *"where the fixture carries a set — Texas
    today"* UNTIL 2026-09-07, AND IT IS NOW EVERY STATE (CR-077).** PO ruling,
    verbatim: *"Can you have Tax jurisdictions - for all states - atleast 1 -
    you seed based on customer selection - if they select Iowa you seed in Iowa,
    but you ahve to ahve a list for all 50 states"*. The fixture keys are the
    fifty states plus DC and Puerto Rico — `selectors.US_STATES` exactly, and a
    test pins the two lists to each other — so `keyed.get(state_code)` answers
    for every state a utility can select rather than for one.

    **The new sets carry NO RATE, and that is the ruling rather than an
    omission.** Each state names its revenue authority and its utility
    commission and states no `taxes` block, so nothing can be priced from them;
    the utility fills the figures in on S13. Texas is the exception and keeps
    the five worked rates the PO ruled on 2026-08-18 (DEF-254/DEF-273).

    The scaffold is CR-010's tax ruling (PO 2026-08-17, options *"a and B -
    default available"*): County · City · Special district rows with NO rate,
    for every state — the structure is visible on S13 without a single
    pre-filled figure, because a wrong tax rate charges real customers real
    money and the state rows are the only ones any corpus source prices.
    Before this, a non-Texas tenant seeded ZERO jurisdictions and the screen
    gave no hint of what the levels even are.
    """
    keyed = fixture.get("tax_jurisdictions", {})
    return list(keyed.get(state_code or "", [])) + list(keyed.get("ALL", []))


def _seed_uoms(tenant: models.Tenant, entries: list[dict[str, Any]]) -> int:
    """Insert-missing only (upsert by code, case-insensitive). Existing rows are
    never touched — the conservative reading of BR-TEN-012's 'tenant-touched
    rows are never overwritten' (no touch-tracking column exists to tell a
    pristine seeded row from an edited one; recorded in the build report).

    CR-004 / DEF-184: a NEW row is born carrying its utility-service scope from
    `SEEDED_UOM_SERVICE_SCOPE`, which is derived from `SERVICE_DEFAULT_UOMS` —
    the seed already thought in service→unit pairs, and this is the half that
    was missing. A unit no service names, and a unit more than one names, is
    left NULL = "All services". The insert-missing law is unchanged: an EXISTING
    row keeps whatever scope its tenant gave it, seed or staff, and re-running
    the seeder re-scopes nothing.

    The scope is written even for a service this tenant has not enabled — the
    map is the PLATFORM's statement about what a unit MEANS, not about what this
    tenant sells, and a water-only co-op that never enables gas simply never
    sees `therm` offered anywhere. (Staff-entered scopes are the other case and
    ARE gated on enablement — see `UomLookupHandler._resolve_service`.)
    """
    created = 0
    catalog = {row.code: row for row in models.Service.objects.all()}
    for entry in entries:
        code = str(entry.get("code", "")).strip()
        name = str(entry.get("name", "")).strip()
        if not code or not name:
            raise errors.SysError(
                errors.SYS_INTERNAL,
                message_key="signup.reference_fixture_invalid",
                params={"reason": "uom entry missing code/name"},
            )
        exists = models.Uom.objects.filter(tenant=tenant, code__iexact=code).exists()
        if not exists:
            # CR-010 10.2 (PO 2026-08-17): a fixture entry may STATE its scope
            # (`"service": "gas"`), and a stated scope wins over the derived
            # map — the same precedent charge_type set ("copied only when the
            # fixture STATES it"). An entry naming a service the catalog does
            # not hold fails LOUD: a typo scoping kVA to "electricity" must
            # not silently land as All-services.
            stated = str(entry.get("service") or "").strip() or None
            if stated is not None and stated not in catalog:
                raise errors.SysError(
                    errors.SYS_INTERNAL,
                    message_key="signup.reference_fixture_invalid",
                    params={"reason": f"uom {code!r} names unknown service {stated!r}"},
                )
            service_code = stated or SEEDED_UOM_SERVICE_SCOPE.get(code.lower())
            models.Uom.objects.create(
                tenant=tenant,
                code=code,
                name=name,
                service=catalog.get(service_code) if service_code else None,
                is_system=True,
                active=True,
            )
            created += 1
    return created


# ── CR-040 task A2 · the tender → clearing account mapping ──────────────────
# 🔒 HUMAN-REVIEW-PENDING — this decides WHICH GL ACCOUNT a customer's money
# lands in on receipt, which is the "ledger posting" / "money" sensitive path.
# Row in 12-governance/09-human-review-ledger.md.
#
# BR-PAY-150 (CONFIRMED 2026-08-27, PO ruling closing OQ-490, verbatim:
# *"reconcilaition is a seperate problem - (a) Undeposited funds is the answer
# for every tender - no chart change, nothing to re-sign, and the demo's cash
# sits in one bucket by design"*).
#
# ⚠ **THE BEHAVIOUR DOES NOT MOVE, AND THAT IS THE POINT.**
# `apps/payments/ledger_seam.tender_clearing_account_id` already answers None
# for an unmapped tender, and the receipt already debits the
# `undeposited_funds` designation in that case (OQ-143, PO 2026-08-11). So
# before this function every seeded payment landed in 1010, and after it every
# seeded payment lands in 1010. **What changes is that the value is STATED
# rather than ABSENT** — and a stated value is one a gate can hold (task A3),
# where an absence is indistinguishable from an omission nobody decided.
#
# ⚠ **THE COST IS THE PO'S OWN SENTENCE, ACCEPTED DELIBERATELY.** One cash
# bucket. Bank reconciliation has nothing to reconcile per tender until a
# separate piece of work gives the chart per-tender clearing accounts — which
# would be an addition to the ❄️ FROZEN signed chart (B5 line 74) and needs a
# finance re-sign through HUMAN-GUIDE §6, never an inline edit.
#
# ⚠ **THE REASON-CODE HALF IS NOT DONE HERE AND MUST NOT BE.** OQ-490 carried
# two halves and the PO ruled ONE — *"the answer for every TENDER"*. A
# signature covers only what was shown (PO 2026-08-11), so
# `reason_codes.default_gl_account_id` STAYS NULL and stays on the agenda: the
# right revenue account for a billing-error credit is the SERVICE's (4110
# Water, 4100 Electric...), a property of the bill being corrected rather than
# of the reason a clerk picked, and that column has no backend reader at all
# today. Seeding it would state something the money does not agree with.

#: The ledger's own word for the holding account an unbanked receipt sits in
#: (`apps/ledger/chart.UNDEPOSITED_FUNDS`, one of the eleven designations the
#: PO ruled on 2026-08-11 closing OQ-110). It is a STRING here and not an
#: import: tenancy may not import the ledger (B1 / BR-TEN-013), so a
#: designation crosses the seam as a name exactly as a service code does. The
#: seam RAISES on a designation the ledger does not know, so a typo here is a
#: loud failure at provisioning rather than a silent NULL.
UNDEPOSITED_FUNDS_DESIGNATION = "undeposited_funds"


def _map_tender_clearing_accounts(tenant: models.Tenant, actor: Any) -> dict[str, Any]:
    """Point every seeded tender at `undeposited_funds`. Idempotent.

    Returns `{"mapped": n, "already": n, "skipped_reason": str | None}`.

    **Only a row this seed planted is touched** (`is_system=True`) and only one
    that carries NO pointer. A tenant who chose an account on Settings →
    Accounting → GL mapping has made a decision, and a re-run that overwrote it
    would be provisioning quietly undoing a clerk — the BR-TEN-012
    insert-missing posture, one field along.

    **It writes nothing when the ledger cannot answer**, and says why rather
    than leaving the caller to infer it. Three ways that happens — the ledger
    module is unauthored, the chart holds no `undeposited_funds` row, or the
    tenant has no chart — and all three end the same way: the tenders stay
    NULL, which is the lawful pre-2026-08-27 state and not a broken one.
    """
    account_id = seams.ledger_account_id_for_designation(UNDEPOSITED_FUNDS_DESIGNATION)
    if account_id is None:
        return {
            "mapped": 0,
            "already": 0,
            "skipped_reason": (
                "no account carries the `undeposited_funds` designation for this tenant, so "
                "there is nothing to point the tenders at. The chart of accounts is seeded by "
                "apps.ledger.services.seed_chart_of_accounts inside this same transaction; if "
                "it did not run, fix that rather than mapping the tenders to a guess. Every "
                "tender stays NULL, which is the lawful fallback (the receipt debits "
                "Undeposited funds anyway) and NOT a broken tenant."
            ),
        }
    rows = list(
        models.PaymentMethod.objects.filter(
            tenant=tenant, is_system=True, clearing_gl_account_id__isnull=True
        )
    )
    mapped = 0
    for row in rows:
        row.clearing_gl_account_id = account_id
        row.save(update_fields=["clearing_gl_account_id", "updated_at"])
        mapped += 1
    already = (
        models.PaymentMethod.objects.filter(
            tenant=tenant, clearing_gl_account_id__isnull=False
        ).count()
        - mapped
    )
    if mapped:
        # CLAUDE.md hard rule 7 — every money action writes `audit_log`. WHICH
        # GL account receives a customer's cash is a money decision even when
        # the account chosen is the one the posting path already fell back to.
        _audit(
            actor,
            "reference.tender_gl_mapped",
            "payment_method",
            None,
            after={
                "designation": UNDEPOSITED_FUNDS_DESIGNATION,
                "clearing_gl_account_id": str(account_id),
                "tenders": mapped,
                # THE RULING, VERBATIM, LIVES HERE — not in the payload, because
                # S61 renders a payload value to a clerk (DEF-2377). BR-PAY-150,
                # PO 2026-08-27 closing OQ-490: Undeposited funds is the answer
                # for every tender.
                "br_ref": "BR-PAY-150",
                "decided": (
                    "every kind of payment is filed to Undeposited funds until the "
                    "bank confirms it"
                ),
            },
        )
    return {"mapped": mapped, "already": already, "skipped_reason": None}


def _map_reason_code_accounts(tenant: models.Tenant, actor: Any) -> dict[str, Any]:
    """Point each seeded adjustment reason at the account CR-066 table 2 names.

    Returns `{"mapped": n, "already": n, "skipped": [codes]}`.

    PO 2026-09-02, verbatim: *"Table 2 — the five adjustment reasons - these are
    all good - please apply these."* The table put to them, in full:
    `BILLERR` → 4700 Billing adjustment · `LEAK` → 4710 Leak adjustment ·
    `METERR` → 4720 Rate / meter correction · `GOODWILL` → 4730 Customer
    credit · `DISPUTE` → 4700 Billing adjustment.

    ⚠ **THIS UNBLOCKS NO BILL AND MUST NEVER BE REPORTED AS THOUGH IT DOES.**
    Nothing in the backend reads `reason_codes.default_gl_account_id`: an
    adjustment credit reverses whatever account the original bill credited. The
    PO was told exactly that in the message that carried the table and approved
    it anyway, because the mapping is correct to have. What was blocking bills
    was the CHARGE codes, one function up.

    ⚠ **IT SUPERSEDES A DECISION OF OUR OWN, WHICH IS WHY THE SUPERSESSION IS
    WRITTEN HERE RATHER THAN ASSUMED.** `CR-040` task A1 was closed *"not to be
    seeded"* in the decision log on 2026-08-27, on the reasoning that the signed
    chart held no general adjustments account to point at and that seeding one
    would add a row to ❄️ FROZEN B5 line 74. That reasoning was right and is now
    spent: the PO has ruled the four accounts into existence and named which
    reason goes where. The screen note that told a clerk the column was blank by
    decision moves with it.

    **Only a row this seed planted** (`is_system=True`) **and only one carrying
    NO pointer** — `BR-TEN-012`, the same insert-missing posture
    `_map_tender_clearing_accounts` takes directly above.
    """
    rows = list(
        models.ReasonCode.objects.filter(
            tenant=tenant, is_system=True, default_gl_account_id__isnull=True
        )
    )
    mapped = 0
    skipped: list[str] = []
    for row in rows:
        account_id = seams.ledger_default_gl_account_id_for_reason(row.code)
        if not account_id:
            # A reason the platform table does not name, or a chart with no such
            # row (an older tenant whose chart has not been topped up). Left
            # NULL, which is the state every reason code has been in since the
            # column existed — never a guessed account.
            skipped.append(row.code)
            continue
        row.default_gl_account_id = account_id
        row.save(update_fields=["default_gl_account_id", "updated_at"])
        mapped += 1
    already = (
        models.ReasonCode.objects.filter(
            tenant=tenant, default_gl_account_id__isnull=False
        ).count()
        - mapped
    )
    if mapped:
        # CLAUDE.md hard rule 7. It writes an audit row even though nothing
        # posts through the column yet, for the reason the tender mapper states:
        # WHICH account a utility's money is filed against is a money decision,
        # and the row is what a finance reviewer reads to see what the seed
        # decided and when.
        _audit(
            actor,
            "reference.reason_gl_mapped",
            "reason_code",
            None,
            after={
                "reasons": mapped,
                "skipped": sorted(skipped),
                # THE RULING, VERBATIM, LIVES HERE — not in the payload, because
                # S61 renders a payload value to a clerk (DEF-2377). CR-066, PO
                # 2026-09-02: *"Table 2 - the five adjustment reasons - these are
                # all good - please apply these."* Supersedes CR-040 task A1's
                # "not to be seeded" close of 2026-08-27. Nothing posts through
                # this column yet.
                "br_ref": "CR-066",
                "decided": (
                    "the five adjustment reasons were filed to the accounts the "
                    "utility approved; nothing posts through them yet"
                ),
            },
        )
    return {"mapped": mapped, "already": already, "skipped": sorted(skipped)}


def _seed_number_series(tenant: models.Tenant) -> int:
    """US-TEN-012 §5 / BE-06: one row per series in `core.numbering.SERIES_CATALOG`
    — TWENTY-TWO since CR-005, five before it — at its first ready-made format
    with the counter at 1 and no period restart.

    Idempotent by `get_or_create` on (tenant, series), which is what makes it
    safe to call on a tenant that already exists: a series already configured
    keeps ITS format and ITS counter, and only the missing rows are created.
    That is the repair door for every tenant provisioned before this change
    (`manage.py seed_demo --tenant <subdomain>` → `seed_reference_data_for_tenant`),
    and it is why the four series that had no row — journal entries, deposit
    batches, receipts, export batches — stop being a permanent gap for hosts
    that are already running. Returns the number of rows created so the caller
    can report it rather than claim it.
    """
    created = 0
    for series, format_string in SERIES_DEFAULTS.items():
        _row, was_created = models.NumberSeries.objects.get_or_create(
            tenant=tenant,
            series=series,
            defaults={
                "format": format_string,
                "next_number": 1,
                # G3: the correction case restarts yearly; every other
                # series is seeded never-restarting (`SERIES_DEFAULT_RESTART`).
                "restart_period": core_numbering.SERIES_DEFAULT_RESTART.get(
                    series, core_numbering.RESTART_NEVER
                ),
                "period_counted": "",
            },
        )
        created += 1 if was_created else 0
    return created


def _seed_us_holidays(tenant: models.Tenant, year: int) -> int:
    """Seed the US federal holidays for `year` (PO ruling 2026-08-11).

    Verbatim: *"for time being consider USA and Load US holiday for given year
    as a seed data"* — an interim default for a US-first launch, not a claim
    that the product is US-only. The tenant's calendar (S63 / BR-TEN-039) stays
    the authority: a tenant edits or deletes these, and a tenant outside the US
    replaces them. Nothing downstream knows a date came from a seed.

    ONE YEAR, and the year is an ARGUMENT (BR-TEN-043). **Callers should use
    `ensure_us_holidays_through` rather than this function** — a single year is
    what created DEF-042, and this stays single-year only because the year is
    genuinely the unit the US federal calendar is defined in.

    `get_or_create` per date, so a re-provision or a re-run never duplicates
    and never overwrites a label a tenant has already renamed. Returns the
    number of rows actually created, for the provisioning summary.
    """
    created = 0
    for holiday_date, label in us_holidays.us_federal_holidays(year):
        _row, made = models.HolidayCalendar.objects.get_or_create(
            tenant=tenant, holiday_date=holiday_date, defaults={"label": label}
        )
        created += int(made)
    return created


def holiday_coverage_year(tenant_id: Any) -> int | None:
    """The last year this tenant's calendar covers, or `None` if it is empty.

    `None` is NOT a defect and must not be treated as one: a tenant outside the
    US legitimately deletes every seeded date (BR-TEN-039 keeps the calendar the
    tenant's own). *Empty* means "this tenant observes no holidays"; *ending in
    2026* means "nobody renewed it". Only the second is DEF-042.
    """
    last = (
        models.HolidayCalendar.objects.filter(tenant_id=tenant_id)
        .order_by("-holiday_date")
        .values_list("holiday_date", flat=True)
        .first()
    )
    return last.year if last else None


def ensure_us_holidays_through(tenant: models.Tenant, through_year: int) -> int:
    """Top a tenant's calendar up so it covers every year through `through_year`.

    **DEF-042.** Provisioning used to seed the SIGN-UP YEAR only and nothing
    renewed it, so on 1 January every business-day grace calculation silently
    reverted to skipping weekends alone — no error, no log line, no failing
    test. The PO's own worked case is the proof: a bill due **Thu 24 Dec 2026**
    with 5 business days' grace must charge on **Tue 5 Jan 2027**. That answer
    needs **1 Jan 2027** to be in the calendar. With one year seeded the fee
    lands **Mon 4 Jan** — a day early, and *on a public holiday*, for every
    customer of that tenant.

    **WHY THIS SHAPE, out of the three the defect named.** A create-ahead job
    was the alternative, and it was rejected for a specific reason rather than a
    stylistic one: **this product has no scheduler wired.** The collections
    ladder's own endpoint records that it has no scheduled caller, so a renewal
    job would be a comment claiming a guarantee — hard-won law 1, in the one
    place where its failure is invisible until January. This function is instead
    IDEMPOTENT and cheap, so any caller that knows a horizon can simply assert
    it, and a scheduler can call it later without changing anything.

    The third option — computing US holidays inline in the grace clock — is
    rejected outright and stays rejected: it would hardcode one country into
    money math and silently override a tenant that edited its own calendar,
    which is the opposite of the PO's *"for time being"* framing.

    **WHY THIS IS NOT CALLED FROM THE READ PATH**, which is what "seed on first
    use" would most naturally mean: `selectors._close_by_date` is the function
    that walks the grace days, and it is a SELECTOR. A read that writes rows is
    a read that can fail on a replica, inside another module's transaction, or
    under a role with no INSERT — and it would write tenant rows from a call
    site that never expected to. Writes live here, in services. **So the gap
    this leaves is real and is stated rather than implied: a tenant whose
    calendar is not topped up by one of the callers below will still walk into
    an uncovered year.** `10-scripts/gates/g23_holiday_horizon.py` is what makes
    that loud instead of silent.

    **IT EXTENDS; IT NEVER RE-SEEDS.** An EMPTY calendar means the tenant
    deleted the seeded dates — a utility outside the US doing exactly what
    BR-TEN-039 entitles it to — and topping that up would silently re-impose US
    federal holidays on a tenant that removed them, every time anything called
    this. So an empty calendar returns 0 and is left alone. The initial seed is
    provisioning's job and happens once, when the calendar is empty *because the
    tenant is new* rather than because they emptied it. The two cases look
    identical in the data, which is precisely why only one caller may seed.

    Idempotent per date via `get_or_create`, so re-running never duplicates and
    never overwrites a label a tenant has renamed. Years already covered cost
    one query each and create nothing. Returns rows actually created.
    """
    covered = holiday_coverage_year(tenant.pk)
    if covered is None:
        return 0  # the tenant's own empty calendar — see above, never re-seed
    created = 0
    for year in range(covered + 1, through_year + 1):
        created += _seed_us_holidays(tenant, year)
    return created


def top_up_holiday_calendar(tenant: models.Tenant) -> int:
    """Assert the SAME horizon provisioning leaves: this year and next — DEF-253.

    **THE CALLER `ensure_us_holidays_through` NEVER HAD.** That function was
    written, was correct, was idempotent, and refused to re-seed an emptied
    calendar — and the only things that called it were tests and the gate that
    excludes its own definition. So a tenant's calendar ran to the end of the
    year after signup and stopped, and DEF-042's failure returns unchanged on
    the next 1 January: a bill due **Thu 24 Dec** with 5 business days' grace
    charges the late fee on **Mon 4 Jan** — a day early, and on New Year's Day
    — because 1 Jan is not in the calendar to be skipped. Its own docstring
    said so: *"the gap this leaves is real and is stated rather than implied."*
    Stating a gap is not closing one.

    **WHY A HORIZON OF `year + 1`, and not five years.** It is the horizon
    provisioning already writes and the horizon `g24_holiday_horizon.py`
    already checks, so there is exactly one number and three places agree on
    it. A longer horizon would look safer and would silently widen the set of
    dates a non-US tenant has to delete.

    **⚠ WHAT THIS MUST NOT DO, and the whole reason it delegates rather than
    seeding.** An EMPTY calendar is a tenant's deliberate act — BR-TEN-039
    makes the calendar theirs, and a utility outside the US deletes every
    seeded date. An empty calendar and a brand-new one are indistinguishable in
    the data, so re-seeding "empty" would re-impose US federal holidays on a
    tenant that removed them, every time the sweep ran. `ensure_us_holidays_
    through` already returns 0 for that case and this function adds nothing
    that could change it.

    The clock: `selectors.tenant_today()` is the tenant's own date (BR-TEN-043
    — the year is an argument, never a module-level clock), so a tenant in a
    zone that has already turned the year over gets that year's horizon.

    Returns rows actually created, so a caller can print "nothing to do" rather
    than claim work it did not do.
    """
    return ensure_us_holidays_through(tenant, selectors.tenant_today().year + 1)


def _enable_signup_services(
    tenant: models.Tenant, service_codes: list[str], actor: Any = None
) -> None:
    """ALL TEN catalog services get a row; signup picks which start ENABLED.

    ⚠ **REWRITTEN 2026-08-18 under the PO's New mandate 4 (2026-08-17),
    verbatim:** *"we will provdie full list for all services - they can always
    select what they want out of it; more is better ; less is contraint"* —
    ruled alongside CR-010 B-9's full-chart seed (*"9 - A full ~40 accounts for
    every tenant, as you said"*). Until then only the services CHOSEN at signup
    got a `tenant_services` row; now every active catalog service (BR-RAT-024's
    ten) gets one at provisioning — the chosen ones `enabled=True`, the rest
    **present-but-off** (`enabled=False`, `disabled_at` NULL because they were
    never on) — and EVERY row carries its default UoMs and its GL account
    pointers, so switching a service on later is one toggle on S8, not a
    configuration hunt.

    `ensure_service_revenue_accounts` answers each service's account ids — the
    same call `_apply_service_toggle` makes, so signup and the S8 toggle stay
    identical. Since B-9's full-chart seed it finds every account already
    seeded and mints nothing on a new tenant; it remains the top-up path for
    tenants provisioned under OQ-115's narrowing (2026-08-11 → 2026-08-17).

    What lands here is a DEFAULT. The tenant may re-point either account
    afterwards through `update_tenant_service`, and nothing re-seeds over it.

    A chosen code outside the active catalog is refused by name (BR-TEN-025:
    the catalog is closed). `_validate_signup` already refuses it at the door
    with `signup.service_unknown`; this second check exists because before the
    rewrite `Service.objects.get` would have raised on the same input, and a
    rewrite may not quietly turn a refusal into a silent skip.
    """
    chosen = set(service_codes)
    catalog = list(models.Service.objects.filter(active=True).order_by("sort", "code"))
    unknown = chosen - {service.code for service in catalog}
    if unknown:
        _refuse_fields(
            [
                _field_error(
                    "services", errors.VAL_UNKNOWN_LOOKUP, "signup.service_unknown", service=code
                )
                for code in sorted(unknown)
            ]
        )
    for service in catalog:
        primary, alt = _default_uoms_for(tenant, service.code)
        revenue_id, base_revenue_id = seams.ensure_service_revenue_accounts(service.code, actor)
        models.TenantService.objects.create(
            tenant=tenant,
            service=service,
            enabled=service.code in chosen,
            # ⚠ **NAMED, NOT INHERITED — this is `DEF-2409`'s first fault fixed
            # (`BR-TEN-1180`, 2026-09-02).** This call created all ten rows
            # naming tenant, service, enabled, both UoMs and the two revenue
            # accounts — and NOT the measurement column, so every service on
            # every tenant took the model default and **every service in the
            # product was declared metered**, Solar, Battery, Storm water and
            # Sewer included. The screen rendered that faithfully, which is why
            # the PO reported it as a display bug and it was not.
            #
            # It is `_default_basis_for` and not a literal because the basis and
            # the units must come from ONE map or they will disagree: a service
            # cannot be capacity-based and carry a period as its unit, which is
            # exactly what `trash` and `broadband` did with `month`.
            billing_basis=_default_basis_for(service.code),
            primary_uom=primary,
            alt_uom=alt,
            revenue_account_id=revenue_id,
            base_revenue_account_id=base_revenue_id,
        )


def _default_basis_for(service_code: str) -> str:
    """The ruled billing basis for a catalog service — `BR-TEN-1180`.

    **A service missing from `SERVICE_DEFAULT_UOMS` falls back to `metered`, and
    that fallback should now be unreachable.** The map names all ten catalog
    services since the PO's ruling of 2026-09-02, and `BR-TEN-025` makes the
    catalog CLOSED — so the only way here is a service added to the catalog and
    not to the map, which is the gap `DEF-3230` was filed about. `metered` is
    the safe landing (hard-won law 3): it is what every row held before today,
    so a service that slipped through prices exactly as it does now instead of
    being silently re-based onto an asset count that would bill `$0.00`.

    A test asserts the map covers every active catalog service by name, so that
    gap is a red test rather than a quiet default.
    """
    row = SERVICE_DEFAULT_UOMS.get(service_code)
    return row.basis if row is not None else models.BILLING_BASIS_METERED


def _default_uoms_for(
    tenant: models.Tenant, service_code: str
) -> tuple[models.Uom | None, models.Uom | None]:
    mapping = SERVICE_DEFAULT_UOMS.get(service_code)
    if mapping is None:
        return None, None

    def find(code: str | None) -> models.Uom | None:
        if code is None:
            return None
        return models.Uom.objects.filter(tenant=tenant, code__iexact=code, active=True).first()

    return find(mapping[0]), find(mapping[1])


# ── S62 checklist writes (US-TEN-003, BR-TEN-015/016) ───────────────────────
@require_role(SYSTEM_ADMIN)
def mark_checklist_item(actor: Any, item_code: str) -> dict[str, Any]:
    """Manual mark-done/dismiss for ADVISORY items only — computed items complete
    themselves from live data, never from a click (BR-TEN-015)."""
    kinds = dict(selectors.CHECKLIST_ITEMS)
    if item_code not in kinds:
        raise errors.NotFoundError()
    if kinds[item_code] != "advisory":
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-TEN-015",
            message_key="checklist.item_not_advisory",
            params={"item": item_code},
        )
    with transaction.atomic():
        tenant = _tenant_row(locked=True)
        state = dict(tenant.checklist_state or {})
        manual = dict(state.get("manual_done") or {})
        if item_code not in manual:
            before = {"checklist_state": tenant.checklist_state}
            manual[item_code] = {
                "by": str(getattr(actor, "id", None)),
                "at": timezone.now().isoformat(),
            }
            state["manual_done"] = manual
            tenant.checklist_state = state
            tenant.save(update_fields=["checklist_state", "updated_at"])
            _audit(
                actor,
                "checklist.item_marked_done",
                "tenant",
                tenant.id,
                before=before,
                after={"checklist_state": state},
            )
    return selectors.checklist()


# ── S8 Company profile (US-TEN-005) ─────────────────────────────────────────
_COMPANY_TEXT_LIMITS = {
    "legal_name": 200,
    "dba_name": 200,
    "state_utility_id": 40,  # US-TEN-005 §5: free text ≤40
    "mailing_address": 500,
    "support_phone": 40,
    "website": 200,
    "remit_to_address": 500,
    "remit_payable_to": 200,
    "service_hours": 60,  # §5: free text ≤60
}
#: CR-060 C7 / task T2 — the ONE company-profile field that does not live on
#: `tenants`. It is stored on `tenant_settings` (CR-060 §9's table) and it is
#: EDITED on Company → Profile beside legal name and DBA, because it is an
#: identity fact and that is where identity lives (C7's own placement ruling:
#: *"Not a finance tab, and not a signup wizard a tenant sees once and never
#: returns to"*). One tab, one atomic save, two rows written — which is why
#: `save_company_profile` writes both inside one transaction and audits once.
COMPANY_SETTINGS_FIELDS = frozenset({"organisation_type"})
COMPANY_FIELDS = (
    frozenset(_COMPANY_TEXT_LIMITS)
    | COMPANY_SETTINGS_FIELDS
    | {
        "ein",
        "support_email",
        "brand_primary_hex",
        "brand_accent_hex",
        "brand_logo_link_url",
    }
)

#: `CR-199-BRC10` S5 — the logo link's longest accepted address.
BRAND_LOGO_LINK_MAX = 500


def brand_logo_link_ok(value: str) -> bool:
    """`https://<host>…` with no space, no credentials and no quote or angle
    bracket — the only shape a customer email's logo may point at (PO ruling
    1A, 2026-10-29). Anything else is refused by name, never repaired."""
    from urllib.parse import urlsplit

    if len(value) > BRAND_LOGO_LINK_MAX or any(ch in value for ch in " \t\r\n\"'<>`\\"):
        return False
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return (
        parts.scheme == "https"
        and bool(parts.hostname)
        and parts.username is None
        and parts.password is None
    )


def _validate_company_changes(changes: Any) -> dict[str, Any]:
    if not isinstance(changes, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="settings.payload_not_object")
    fe: list[dict[str, Any]] = []
    out: dict[str, Any] = {}
    for field, raw in changes.items():
        if field not in COMPANY_FIELDS:
            fe.append(_field_error(field, errors.VAL_FORMAT, "settings.unknown_field"))
            continue
        value = raw.strip() if isinstance(raw, str) else raw
        if field == "organisation_type":
            # BR-TEN-1050 — three values and NO null. Every other field on this
            # tab clears to None; this one cannot, because the whole point of a
            # seeded default is that no tenant is ever in an unknown state. An
            # empty string here is therefore a REFUSAL and not a clear.
            if value in ("", None) or str(value) not in models.ORGANISATION_TYPES:
                fe.append(
                    _field_error(
                        "organisation_type",
                        errors.VAL_UNKNOWN_LOOKUP,
                        "settings.company.organisationTypeUnknown",
                        allowed=list(models.ORGANISATION_TYPES),
                    )
                )
            else:
                out[field] = str(value)
            continue
        if value in ("", None):
            out[field] = None
            continue
        if field == "ein":
            if not isinstance(value, str) or not _EIN_RE.match(value):
                # US-TEN-005 TC-4: "Enter as NN-NNNNNNN"
                fe.append(_field_error("ein", errors.VAL_FORMAT, "settings.company.ein_format"))
            else:
                out["ein"] = value.replace("-", "")  # BR-TEN-018: stored as 9 digits
        elif field == "support_email":
            if not isinstance(value, str) or not _EMAIL_RE.match(value):
                fe.append(
                    _field_error(
                        "support_email", errors.VAL_FORMAT, "settings.company.email_format"
                    )
                )
            else:
                out[field] = value
        elif field == "brand_logo_link_url":
            # CR-199-BRC10 S5 — https only; the message names the rule.
            if not isinstance(value, str) or not brand_logo_link_ok(value):
                fe.append(
                    _field_error(field, errors.VAL_FORMAT, "settings.company.logoLinkHttps")
                )
            else:
                out[field] = value
        elif field in ("brand_primary_hex", "brand_accent_hex"):
            if not isinstance(value, str) or not _HEX_COLOR_RE.match(value):
                # BR-TEN-019: valid #RRGGBB only
                fe.append(_field_error(field, errors.VAL_FORMAT, "settings.company.hex_format"))
            else:
                out[field] = value
        else:
            limit = _COMPANY_TEXT_LIMITS[field]
            if not isinstance(value, str):
                fe.append(_field_error(field, errors.VAL_FORMAT, "settings.company.text_expected"))
            elif len(value) > limit:
                fe.append(
                    _field_error(field, errors.VAL_RANGE, "settings.company.too_long", max=limit)
                )
            else:
                out[field] = value
    _refuse_fields(fe)
    return out


@require_role(SYSTEM_ADMIN)
def save_company_profile(actor: Any, changes: Any) -> dict[str, Any]:
    """Whole-tab atomic save with ONE audit row (BR-TEN-024/016). Values are
    stamped onto documents at issue time by the issuing modules — nothing here
    re-renders anything already issued (BR-TEN-017)."""
    cleaned = _validate_company_changes(changes)
    with transaction.atomic():
        tenant = _tenant_row(locked=True)
        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
        # Portal a11y Group A ruling 3(b), PO/QA 2026-10-23: a NEW brand colour
        # that reaches 4.5:1 with neither white nor the dark ink is refused by
        # name. An unchanged colour is never refused — ruling 3(a) corrects the
        # existing ones on screen, so re-saving the tab cannot be blocked by a
        # colour the utility chose before the rule. (Never fires with today's
        # inks: see `brand.brand_colour_refused`.)
        low_contrast = [
            _field_error(field, errors.VAL_RANGE, "settings.company.hex_contrast")
            for field in ("brand_primary_hex", "brand_accent_hex")
            if cleaned.get(field) is not None
            and cleaned[field] != getattr(tenant, field)
            and brand_law.brand_colour_refused(cleaned[field])
        ]
        # Group A decision 3, PO/QA 2026-10-23: a NEW primary colour too light
        # to read as text on white even after darkening (88%), or too light for
        # the focus ring (3:1 on white and on #f3f2f2), is refused and says
        # why. Worked: #F5C518 is refused. The PRIMARY only: the accent colour
        # is drawn nowhere (DEF-CWP-3737), so refusing it as text would refuse
        # a colour no one sees (decision log 2026-10-23, "how they are built" (3)).
        field = "brand_primary_hex"
        if (
            not any(fe["field"] == field for fe in low_contrast)
            and cleaned.get(field) is not None
            and cleaned[field] != getattr(tenant, field)
            and brand_law.brand_colour_too_light(cleaned[field])
        ):
            low_contrast.append(_field_error(field, errors.VAL_RANGE, "settings.company.hex_too_light"))
        _refuse_fields(low_contrast)
        for field, new_value in cleaned.items():
            if field in COMPANY_SETTINGS_FIELDS:
                continue  # written below — it lives on `tenant_settings`
            old_value = getattr(tenant, field)
            if old_value == new_value:
                continue
            if field == "ein":  # BR-AUD-006: masked into the trail
                before[field], after[field] = mask_ein(old_value), mask_ein(new_value)
            else:
                before[field], after[field] = old_value, new_value
            setattr(tenant, field, new_value)
        # CR-060 C7 / task T2 — the settings half of the SAME tab, inside the
        # SAME transaction and under the SAME audit row (BR-TEN-024: the whole
        # tab commits atomically with one audit row). It is a second ROW, not a
        # second module: `tenant_settings` is tenancy's own table, so this is
        # not the cross-module write BR-TEN-013 forbids.
        settings_changes = {
            field: value for field, value in cleaned.items() if field in COMPANY_SETTINGS_FIELDS
        }
        if settings_changes:
            settings_row = (
                models.TenantSettings.objects.select_for_update()
                .filter(tenant_id=tenant.id)
                .first()
            )
            if settings_row is None:
                settings_row = models.TenantSettings.objects.create(tenant_id=tenant.id)
            touched: list[str] = []
            for field, new_value in settings_changes.items():
                if getattr(settings_row, field) == new_value:
                    continue
                before[field], after[field] = getattr(settings_row, field), new_value
                setattr(settings_row, field, new_value)
                touched.append(field)
            if touched:
                settings_row.save(update_fields=[*touched, "updated_at"])
        if after:
            tenant_fields = [key for key in after if key not in COMPANY_SETTINGS_FIELDS]
            if tenant_fields:
                tenant.save(update_fields=[*tenant_fields, "updated_at"])
            _audit(
                actor,
                "settings.company_profile.updated",
                "tenant",
                tenant.id,
                before=before,
                after=after,
            )
    return selectors.company_profile()


# ── S8 Company → Brand: logo upload (US-TEN-005 TC-5 · BR-TEN-019) ──────────
#
# ⚠ **THE LOGO LIVES IN THE COMMON DOCUMENT STORE SINCE 2026-10-05
# (`CR-172-BRC10`).** PO, verbatim: *"The uploaded logo is stored in S3, the same
# way the product's other files are stored. The database holds only the
# reference"* and *"use common compotent to save logo - dont create seperate
# code"*. So there is NO logo storage code here: `_store_logo` calls
# `document_store.store()` — the call a bill, a receipt and a work-order
# photograph make — and the row keeps the stored document's id. Until then the
# sanitised bytes were written to `tenants.logo_bytes` because *"no
# document-storage kernel exists"*; that was a lane's choice and the kernel has
# existed since `CR-049`.


def _storage_unavailable(exc: Exception) -> errors.SysError:
    """The ONE refusal an upload makes when the store cannot take the file.

    503 with `settings.company.logo_storage_unavailable` — *"Logo storage is
    unavailable. Nothing was saved."* in all eleven
    catalogues. The row is untouched (the caller has written nothing yet), so
    the logo the utility had is the logo it still has.
    """
    logger.warning("logo upload refused: the document store is unavailable (%s)", exc)
    return errors.SysError(
        errors.SYS_PROVIDER,
        message_key="settings.company.logo_storage_unavailable",
        params={"reason": type(exc).__name__},
    )


def _storage_failures() -> tuple[type[BaseException], ...]:
    """Every exception that means *the store could not take it* — our own
    refusals, and the S3 client's, which the adapter passes through unchanged."""
    from apps.tenancy import document_storage

    failures: list[type[BaseException]] = [document_storage.DocumentStorageError]
    try:
        from botocore.exceptions import BotoCoreError, ClientError

        failures += [BotoCoreError, ClientError]
    except ImportError:  # pragma: no cover - boto3 is a declared dependency
        pass
    return tuple(failures)


def _store_logo(
    stored: bytes,
    content_type: str,
    *,
    source_id: Any,
    actor_user_id: Any = None,
    process: str | None = None,
) -> tuple[Any, Any]:
    """Put ONE logo into the common store: `(uploaded ref, print ref)`.

    A PNG is one stored document, and it is both. A JPG (`DEF-TEN-10618`) is
    two: the JPG the screens draw and its PNG copy for print. An SVG (only a
    logo stored before 2026-10-27, moved by `move_logos_to_store`) is TWO on the same
    `source_id` — the cleaned SVG the screens draw, and its PNG rendering
    (`logo.raster_png`, BR-TEN-019's *"rasterized for PDF/print"*) the printed
    documents draw. A document already stored for this source and type is
    REUSED rather than stored again — which is what lets an interrupted move
    (`move_logos_to_store`) be run twice.

    The display name is `logos/<yyyy>/<mm>/logo.<ext>` — the human name an
    export of this utility's files unpacks to.
    """
    from apps.tenancy import document_models, document_store

    # An SVG (legacy) or a JPG (`DEF-TEN-10618`) gets a PNG copy for print.
    raster = logo_law.print_png(stored, content_type)
    moment = timezone.now()

    def put(payload: bytes, media: str) -> Any:
        existing = document_store.for_source(
            source_type=document_models.SOURCE_TENANT_LOGO,
            source_id=source_id,
            content_type=media,
        )
        if existing.found:
            return existing.document
        ext = {logo_law.SVG_CONTENT_TYPE: "svg", logo_law.JPEG_CONTENT_TYPE: "jpg"}.get(media, "png")
        return document_store.store(
            kind=document_models.KIND_TENANT_LOGO,
            source_type=document_models.SOURCE_TENANT_LOGO,
            source_id=source_id,
            content_type=media,
            display_name=f"logos/{moment:%Y}/{moment:%m}/logo.{ext}",
            payload=payload,
            actor_user_id=actor_user_id,
            process=process,
        )

    uploaded = put(stored, content_type)
    printed = put(raster, logo_law.PNG_CONTENT_TYPE) if raster is not None else uploaded
    return uploaded, printed


@require_role(SYSTEM_ADMIN)
def save_company_logo(
    actor: Any, content: bytes, *, content_type: str | None, filename: str | None = None
) -> dict[str, Any]:
    """Store ONE sanitized logo for the tenant, with one audit row (BR-TEN-016).

    The allowlist, the 2 MB cap and the SVG sanitizer are apps/tenancy/logo.py;
    they run HERE too (not only in api.py) so a job or shell caller meets the
    same law — the API's 415/413 are the transport rendering of these refusals,
    which arrive as 422 VAL-002 for any non-HTTP caller.

    **BYTES FIRST, THEN THE ROW** (`CR-172-BRC10`): the file goes into the
    common document store and only when that has succeeded does the row learn
    the new reference. A store that cannot take it is refused with
    `settings.company.logo_storage_unavailable` (503) and NOTHING is saved.

    Replacing a logo is forward-only in the BR-TEN-017 sense: already-issued
    documents keep the logo stamped at their issue time — they name the stored
    document they were drawn with, and that document is write-once.
    """
    if logo_law.is_svg(content_type, filename):
        logo_law.refuse_svg()  # DEF-TEN-10618 — PNG or JPG only (PO 2026-10-27)
    resolved = logo_law.normalized_content_type(content_type, filename)
    if resolved is None:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="settings.company.logo_type_not_allowed",
            params={"allowed": sorted(logo_law.LOGO_CONTENT_TYPES), "declared": content_type},
            field_errors=[
                _field_error(
                    "file",
                    errors.VAL_FORMAT,
                    "settings.company.logo_type_not_allowed",
                    allowed=sorted(logo_law.LOGO_CONTENT_TYPES),
                    br="BR-TEN-019",
                )
            ],
        )
    stored, resolved_type, digest = logo_law.sanitized_logo(content, resolved)
    actor_user_id = getattr(actor, "id", None) or getattr(actor, "pk", None)
    try:
        uploaded, _printed = _store_logo(
            stored, resolved_type, source_id=uuid7(), actor_user_id=actor_user_id
        )
    except _storage_failures() as exc:
        raise _storage_unavailable(exc) from exc
    reference = str(uploaded.id)
    with transaction.atomic():
        tenant = _tenant_row(locked=True)
        before = {
            "logo_file_id": tenant.logo_file_id,
            "content_type": tenant.logo_content_type,
        }
        tenant.logo_file_id = reference
        tenant.logo_content_type = resolved_type
        tenant.logo_bytes = None
        tenant.save(update_fields=["logo_file_id", "logo_content_type", "logo_bytes", "updated_at"])
        after = {
            "logo_file_id": reference,
            "content_type": resolved_type,
            "size_bytes": len(stored),
            "content_hash": digest,
        }
        _audit(
            actor,
            "settings.company_logo.updated",
            "tenant",
            tenant.id,
            before=before,
            after=after,  # the REFERENCE only — bytes never enter the trail
        )
    return after


# ── Moving the logos that were stored on the row (CR-172-BRC10) ─────────────
def _legacy_logo_source(tenant: models.Tenant) -> UUID:
    """The `source_id` a moved logo is stored under — DERIVED, not minted.

    A function of the tenant and of the bytes' own `sha256:` reference, so a
    move that stored the copy and died before repointing the row finds that
    copy on the next run (`_store_logo` reuses it) instead of storing a second.
    """
    import uuid as uuid_module

    return uuid_module.uuid5(
        uuid_module.NAMESPACE_URL, f"smartbillhub:tenant-logo:{tenant.id}:{tenant.logo_file_id}"
    )


def _move_one_logo(tenant: models.Tenant, original: bytes, content_type: str) -> str:
    """One utility's move, inside the caller's tenant context and savepoint."""
    import hashlib

    from apps.tenancy import document_store

    uploaded, _printed = _store_logo(
        original,
        content_type,
        source_id=_legacy_logo_source(tenant),
        process="tenancy.move_logos_to_store",
    )
    copy = document_store.fetch(uploaded.id)
    if hashlib.sha256(copy).hexdigest() != hashlib.sha256(original).hexdigest():
        logger.warning("logo move: tenant %s copy did not match; left on the row", tenant.id)
        return "left"
    moved = models.Tenant.objects.filter(pk=tenant.pk, logo_file_id=tenant.logo_file_id).update(
        logo_file_id=str(uploaded.id), logo_bytes=None
    )
    if not moved:
        return "left"  # the row changed under us (a new upload) — nothing to move
    core_audit.write_row(
        action="settings.company_logo.moved_to_store",
        entity_type="tenant",
        entity_id=tenant.id,
        actor_user_id=None,
        before={"logo_file_id": tenant.logo_file_id},
        after={"logo_file_id": str(uploaded.id), "content_type": content_type},
    )
    return "moved"


#: The columns `tenancy/0061` (which calls the two functions below with the
#: live model) can rely on existing. Never widen this to a column a later
#: migration adds.
_LOGO_MOVE_COLUMNS = ("id", "logo_bytes", "logo_file_id", "logo_content_type")


def move_logos_to_store() -> dict[str, int]:
    """Copy every logo still held on its row into the common store — re-runnable.

    Called by `tenancy/0061` and by `manage.py move_logos_to_store`. For each
    utility whose row still holds bytes, under THAT utility's own tenant context
    (hard rule 1): store the bytes (and an SVG's PNG rendering), read them back
    through `document_store.fetch()`, and accept the copy ONLY if its sha256
    equals the row's bytes; then repoint `logo_file_id` and empty `logo_bytes`.

    ⚠ **A SAVEPOINT PER UTILITY — hard-won law 14.** One utility's failure must
    not abort the transaction the others are in, which on PostgreSQL it would.

    ⚠ **STORAGE DOWN LEAVES THE ROW EXACTLY AS IT WAS** — bytes and `sha256:`
    reference — and the logo goes on drawing from the row
    (`selectors.logo_bytes`' fallback). A copy that does not match is not
    accepted either. Both are counted as `left`, and running this again later
    finishes the job.

    Returns `{"moved", "already", "left"}`: moved now, moved before, still on the row.
    """
    from apps.tenancy import document_store

    report = {"moved": 0, "already": 0, "left": 0}
    # A store that cannot take it, and an old SVG the renderer refuses: both leave
    # the row as it was.
    failures = _storage_failures() + (document_store.DocumentStoreError, errors.ApiError)
    # ⚠ `.only(...)` — `tenancy/0061` calls this with the LIVE model, so a full
    # SELECT names every column the model has TODAY, and a column added by a
    # later migration (`0067`'s `brand_logo_link_url`) does not exist yet at
    # 0061 — every fresh database failed to migrate (DEF-TEN-10671). Only the
    # four columns 0061 already had are read.
    for tenant in models.Tenant.objects.only(*_LOGO_MOVE_COLUMNS).order_by("id"):
        if tenant.logo_bytes is None:
            if tenant.logo_file_id and not str(tenant.logo_file_id).startswith("sha256:"):
                report["already"] += 1
            continue
        original = bytes(tenant.logo_bytes)
        content_type = tenant.logo_content_type or ""
        # A stored SVG is still MOVED (`DEF-TEN-10618` keeps existing data); it
        # is refused only as a new upload.
        movable = (*logo_law.LOGO_CONTENT_TYPES, logo_law.SVG_CONTENT_TYPE)
        if content_type not in movable or not original:
            logger.warning("logo move: tenant %s holds a logo of type %r; left on the row", tenant.id, content_type)
            report["left"] += 1
            continue
        try:
            with core_tenancy.tenant_context(tenant.id), transaction.atomic():
                outcome = _move_one_logo(tenant, original, content_type)
        except failures as exc:
            logger.warning("logo move: tenant %s left on the row — store unavailable (%s)", tenant.id, exc)
            outcome = "left"
        report[outcome] += 1
    return report


def move_logos_back_to_rows() -> dict[str, int]:
    """THE ROLLBACK of `CR-172-BRC10`: put each stored logo's bytes back on its row.

    For a utility whose row names a stored logo and holds no bytes: fetch the
    logo from the store under its own tenant context (`fetch` verifies the
    hash), write the bytes back to `logo_bytes` and restore the `sha256:`
    reference the previous build reads. Then the previous build can be deployed
    on this schema. Nothing is deleted from the store. Returns
    `{"restored", "skipped"}`.
    """
    import hashlib

    from apps.tenancy import document_store

    report = {"restored": 0, "skipped": 0}
    rows = (
        models.Tenant.objects.filter(logo_bytes__isnull=True)
        .exclude(logo_file_id=None)
        .only(*_LOGO_MOVE_COLUMNS)  # the live model; see `move_logos_to_store`
    )
    for tenant in rows.order_by("id"):
        if str(tenant.logo_file_id).startswith("sha256:"):
            report["skipped"] += 1
            continue
        with core_tenancy.tenant_context(tenant.id), transaction.atomic():
            payload = document_store.fetch(tenant.logo_file_id)
            models.Tenant.objects.filter(pk=tenant.pk).update(
                logo_bytes=payload,
                logo_file_id="sha256:" + hashlib.sha256(payload).hexdigest(),
            )
        report["restored"] += 1
    return report


# ── S64/S66/S69/S70/S71 rule pages (11b §2.3 · BR-TEN-024/043) ──────────────
@require_role(SYSTEM_ADMIN)
def save_settings_family(actor: Any, slug: str, changes: Any) -> dict[str, Any]:
    """Whole-page atomic save with ONE audit row (BR-TEN-024/016) for any of
    the five rule pages; unknown page → 404.

    Event-time forward (BR-TEN-043): the new value governs events that happen
    AFTER the save. Nothing here re-evaluates a flagged read, re-prices a bill,
    re-times a collections ladder already walking, or re-levels a budget
    account — those all read config at their own event time, which is exactly
    why config is a document and not a hardcoded number (BR-MET-020).
    """
    family = settings_families.FAMILIES.get(slug)
    if family is None:
        raise errors.NotFoundError()
    with transaction.atomic():
        tenant_id = _tenant_id()
        row = models.TenantSettings.objects.select_for_update().filter(tenant_id=tenant_id).first()
        if row is None:
            row = models.TenantSettings.objects.create(tenant_id=tenant_id)
        columns_before = {p.column: getattr(row, p.column) for p in family.params if p.column}
        before = settings_families.merge(
            family, getattr(row, family.document_field), columns_before
        )
        after = settings_families.clean(family, changes, before)
        if after == before:
            return after  # no-op save writes nothing and audits nothing
        document, columns = settings_families.split(family, after)
        setattr(row, family.document_field, document)
        for column, value in columns.items():
            setattr(row, column, value)
        row.save(update_fields=[family.document_field, *columns, "updated_at"])
        changed = sorted(key for key in after if after[key] != before[key])
        _audit(
            actor,
            family.audit_action,
            "tenant_settings",
            row.id,
            before={"page": family.screen, **{key: before[key] for key in changed}},
            after={"page": family.screen, **{key: after[key] for key in changed}},
        )
    return after


# ── S8 Regional, formats & fiscal (US-TEN-006) ──────────────────────────────
REGIONAL_TENANT_FIELDS = frozenset({"currency", "state"})
REGIONAL_SETTINGS_FIELDS = frozenset(
    {
        "country",
        "timezone",
        "language",
        "first_day_of_week",
        "number_format",
        "date_format",
        "time_format",
        "fy_start_month",
        "fy_start_day",
        "accounting_method",
        "close_cadence",
        "close_day",
        "lock_closed_periods",
    }
)
_DAYS_IN_MONTH = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)  # Feb 29 allowed


def _validate_regional_changes(changes: Any) -> dict[str, Any]:
    if not isinstance(changes, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="settings.payload_not_object")
    fe: list[dict[str, Any]] = []
    out: dict[str, Any] = {}

    def choice(field: str, allowed: tuple[str, ...]) -> None:
        value = changes[field]
        if value is None:
            out[field] = None
        elif str(value) not in allowed:
            fe.append(
                _field_error(
                    field,
                    errors.VAL_UNKNOWN_LOOKUP,
                    "settings.regional.bad_choice",
                    allowed=list(allowed),
                )
            )
        else:
            out[field] = str(value)

    for field in changes:
        if field not in REGIONAL_TENANT_FIELDS | REGIONAL_SETTINGS_FIELDS:
            fe.append(_field_error(field, errors.VAL_FORMAT, "settings.unknown_field"))
    _refuse_fields(fe)

    if "currency" in changes:
        choice("currency", active_currency_codes())
    if "language" in changes:
        choice("language", SEED_LANGUAGES)
    if "first_day_of_week" in changes:
        choice("first_day_of_week", FIRST_DAYS_OF_WEEK)
    if "number_format" in changes:
        choice("number_format", NUMBER_FORMATS)
    if "date_format" in changes:
        choice("date_format", DATE_FORMATS)
    if "time_format" in changes:
        choice("time_format", TIME_FORMATS)
    if "accounting_method" in changes:
        choice("accounting_method", ACCOUNTING_METHODS)
    if "close_cadence" in changes:
        choice("close_cadence", CLOSE_CADENCES)
    if "timezone" in changes:
        tz_value = changes["timezone"]
        if tz_value is None:
            out["timezone"] = None
        else:
            try:
                ZoneInfo(str(tz_value))
                out["timezone"] = str(tz_value)
            except (KeyError, ValueError):
                fe.append(
                    _field_error("timezone", errors.VAL_FORMAT, "settings.regional.bad_timezone")
                )
    if "state" in changes:
        state_value = changes["state"]
        if state_value is None:
            out["state"] = None
        elif selectors.us_state_code(str(state_value)) is None:
            fe.append(
                _field_error("state", errors.VAL_UNKNOWN_LOOKUP, "settings.regional.state_unknown")
            )
        else:
            out["state"] = str(state_value).strip()
    if "country" in changes:
        country_value = changes["country"]
        out["country"] = str(country_value).strip() if country_value else None
    if "close_day" in changes:
        close_value = changes["close_day"]
        out["close_day"] = str(close_value).strip() if close_value else None
    if "lock_closed_periods" in changes:
        out["lock_closed_periods"] = bool(changes["lock_closed_periods"])

    month = changes.get("fy_start_month")
    day = changes.get("fy_start_day")
    if "fy_start_month" in changes and month is not None:
        try:
            month = int(month)
        except (TypeError, ValueError):
            month = 0
        if not 1 <= month <= 12:
            fe.append(
                _field_error("fy_start_month", errors.VAL_RANGE, "settings.regional.bad_month")
            )
        else:
            out["fy_start_month"] = month
    elif "fy_start_month" in changes:
        out["fy_start_month"] = None
    if "fy_start_day" in changes and day is not None:
        try:
            day = int(day)
        except (TypeError, ValueError):
            day = 0
        check_month = out.get("fy_start_month")
        max_day = _DAYS_IN_MONTH[check_month - 1] if isinstance(check_month, int) else 31
        if not 1 <= day <= max_day:
            # US-TEN-006 TC-5: invalid month/day combination (e.g. February 30)
            fe.append(_field_error("fy_start_day", errors.VAL_RANGE, "settings.regional.bad_day"))
        else:
            out["fy_start_day"] = day
    elif "fy_start_day" in changes:
        out["fy_start_day"] = None

    _refuse_fields(fe)
    return out


@require_role(SYSTEM_ADMIN)
def save_regional_settings(actor: Any, changes: Any) -> dict[str, Any]:
    """Display-time transforms only (BR-TEN-020): storage stays UTC + NUMERIC +
    CHAR(3). Currency is LOCKED once the first financial record exists →
    409 BIZ-LOCKED (BR-TEN-042; BR-TEN-021 pre-lock = forward-only)."""
    cleaned = _validate_regional_changes(changes)
    with transaction.atomic():
        tenant = _tenant_row(locked=True)
        settings_row, _ = models.TenantSettings.objects.get_or_create(tenant=tenant)
        if "currency" in cleaned and cleaned["currency"] != tenant.currency:
            if seams.financial_records_exist():
                raise errors.BizError(
                    errors.BIZ_LOCKED,
                    br_ref="BR-TEN-042",
                    message_key="settings.regional.currency_locked",
                    params={"currency": tenant.currency},
                )
        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
        tenant_fields: list[str] = []
        settings_fields: list[str] = []
        for field, new_value in cleaned.items():
            if field in REGIONAL_TENANT_FIELDS:
                target, fields_list = tenant, tenant_fields
            else:
                target, fields_list = settings_row, settings_fields
            old_value = getattr(target, field)
            if old_value == new_value:
                continue
            before[field], after[field] = old_value, new_value
            setattr(target, field, new_value)
            fields_list.append(field)
        if tenant_fields:
            tenant.save(update_fields=[*tenant_fields, "updated_at"])
        if settings_fields:
            settings_row.save(update_fields=[*settings_fields, "updated_at"])
        if after:
            _audit(
                actor,
                "settings.regional_fiscal.updated",
                "tenant_settings",
                settings_row.id,
                before=before,
                after=after,
            )
        # ⚠ DEF-444 — THE STATE IS NOT ONLY A DISPLAY SETTING. Every other field
        # on this tab changes how a figure is rendered; `state` decides which tax
        # jurisdictions the platform catalogue holds for this tenant, and that
        # catalogue is applied at provisioning, once, from a field sign-up does
        # not require. A tenant that named its state here got the setting saved
        # and nothing else, and could never be taxed. Applying it HERE is the fix
        # at the cause: the catalogue is applied where the state is recorded.
        #
        # In the same transaction as the save, so a tenant is never left having
        # recorded Texas with the delivery half-done. Idempotent by natural key,
        # so a person who opens this tab and saves it again writes nothing.
        if "state" in after:
            deliver_state_tax_jurisdictions(tenant, actor)
    return selectors.regional_settings()


# ── S8 Services & UoM (US-TEN-007/008) ──────────────────────────────────────
@require_role(SYSTEM_ADMIN)
def set_service_gl_accounts(
    actor: Any, service_code: str, changes: dict[str, Any]
) -> dict[str, Any]:
    """**THE SERVICE HALF OF ONE GL-MAPPING SAVE — `CR-060` C10, task T11.**

    C10's complaint, verbatim: *"Eleven GL columns are set across six screens;
    the one page that shows them all is READ-ONLY because half belongs to
    another module."* This is the half tenancy owns — `tenant_services.
    revenue_account_id` and `base_revenue_account_id` — published so the ledger
    can ASK for it rather than write it.

    ⚠ **IT IS A NARROW DOOR ON PURPOSE, AND THAT IS THE WHOLE POINT.**
    `update_tenant_service` above accepts enable/disable, both UoMs, the
    billing basis and the conversion factor as well as these two columns. A
    mapping screen calling THAT could disable a service by sending one
    unexpected key. This accepts **exactly two fields and refuses every other
    by name**, so the orchestrated save cannot reach anything a mapping page has
    no business changing. B1 is kept in the direction that matters: the ledger
    never touches this table, and this function never touches the ledger's.

    **IT OPENS NO TRANSACTION OF ITS OWN.** The caller wraps the whole save,
    because C10's proof is *"a partial failure writes NOTHING"* — a nested
    `atomic()` here would be a SAVEPOINT that could commit while the role half
    rolled back, which is the exact opposite of what was asked for. It is
    written to be called inside somebody else's atomic block and its docstring
    says so, because the next lane's instinct will be to "make it safe" by
    adding one.

    Returns what CHANGED, so the orchestrator can report the save honestly
    rather than claiming every field it was sent.
    """
    unknown = set(changes) - {"revenue_account_id", "base_revenue_account_id"}
    if unknown:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="settings.services.unknownGlField",
            field_errors=[
                {"field": name, "code": errors.VAL_UNKNOWN_LOOKUP} for name in sorted(unknown)
            ],
        )
    row = models.TenantService.objects.filter(
        tenant_id=_tenant_id(), service__code=service_code
    ).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-025")

    before = {
        "revenue_account_id": str(row.revenue_account_id) if row.revenue_account_id else None,
        "base_revenue_account_id": (
            str(row.base_revenue_account_id) if row.base_revenue_account_id else None
        ),
    }
    changed: list[str] = []
    for field in ("revenue_account_id", "base_revenue_account_id"):
        if field not in changes:
            continue
        # `None` CLEARS the pointer and an absent key LEAVES IT ALONE — the
        # `_UNSET` distinction `update_tenant_service` makes, expressed here as
        # key presence. A screen that sent every field every time would drop a
        # tenant's base-revenue pointer each time somebody re-pointed usage.
        raw = changes[field]
        value = None if raw in (None, "") else str(raw)
        if value != before[field]:
            setattr(row, field, value)
            changed.append(field)
    if changed:
        row.save(update_fields=[*changed, "updated_at"] if hasattr(row, "updated_at") else changed)
    return {"service_code": service_code, "changed": changed, "before": before}


# ⚠ `DEF-TEN-8814` — this guard sat on the line above this `def` until
# 2026-09-02, when `set_service_gl_accounts` was inserted between them and took
# it, leaving this function unguarded for a month (BR-SHL-025: the service
# guard IS the enforcement; US-TEN-007 TC-4 is the test that says so). A new
# function goes ABOVE a decorator, never between it and its `def`.
@require_role(SYSTEM_ADMIN)
def update_tenant_service(actor: Any, service_code: str, changes: Any) -> dict[str, Any]:
    """Enable/disable (guarded, soft — BR-TEN-026), per-service UoM edits
    (forward-only — BR-TEN-027) and the GL revenue accounts (BR-BIL-010).
    Service types are the closed platform catalog: tenants only toggle
    availability (BR-TEN-025).

    **THE GL OVERRIDE** (PO ruling 2026-08-11 closing OQ-115, verbatim: *"you
    create an account, but allow tenant user to override it"*). `revenue_account`
    and `base_revenue_account` each take the id of one of the tenant's own live
    ledger accounts, or `null` to clear the mapping. What the seed put there is
    a DEFAULT — a utility that keeps its water revenue in an account of its own
    numbering says so here, once, and every bill line, every roll-up and every
    trial balance follows, because `apps/ledger/selectors.py` resolves the
    stored pointer and never the chart's default. Nothing re-seeds over it: the
    ledger's seed only ever INSERTS accounts the tenant does not have, and it
    never writes this row at all.

    ── **THE MEASUREMENT DECLARATION** (BR-TEN-810 / BR-TEN-811, DEF-2310 +
    DEF-2311, 2026-08-28; the first of the three RENAMED 2026-09-02) ────────
    `billing_basis`, `billed_uom` and `conversion_factor` are the three columns
    a utility could not reach from anywhere in the product until DEF-2310.

    **`billing_basis`** is BR-TEN-1180 — PO 2026-09-02, verbatim: *"Shall we
    consider Metered, % of service and Capacity based"*. It **SUPERSEDES
    BR-RAT-081** (PO 2026-08-20, *"yes we have to say service is meter or
    unmetered"*), whose boolean column shipped that day; DEF-495 gave it a
    reader and DEF-1813 built the whole bill path behind it (3 carts × `$15.00`
    = `$45.00`), and `metered=False` was written NOWHERE outside a test helper
    — so a refuse utility could not tell the product it does not meter trash,
    and every figure that work produced was reachable only by editing a database
    row by hand. This is the writer.

    ⚠ **THE FIELD IS `billing_basis` AND `metered` IS NOT ACCEPTED — a clean
    cut, ruled the same day: *"we are in beta stage ... hence you can fix it; I
    will delete the DB and relaunch"*.** A payload still sending `metered` is
    refused by the unknown-field check below, by name, which is the loud failure
    hard-won law 1 asks for. `_apply_service_billing_basis` carries the whole
    reasoning, sewer included.

    **`billed_uom` + `conversion_factor`** are r6.4's register→billed gate as
    the TENANT holds it (BR-RAT-038). `selectors.service_billed_uoms()` is read
    by metering, assets and rating; nothing wrote it, so every tenant's answer
    was `None` and the gate had only its refusing half (DEF-2311).

    ⚠ **BOTH ARE ACCEPTED ON A PRESENT-BUT-OFF SERVICE, and that is deliberate**
    — the same posture `primary_uom`/`alt_uom` have always had here. Since New
    mandate 4 (PO 2026-08-17, *"we will provdie full list for all services -
    they can always select what they want out of it"*) every tenant carries a
    row for all ten catalog services, so a utility can say how it will bill
    trash before it switches trash on, which is the order a real utility works
    in. It cannot move a cent while the service is off: `unmetered_service_codes
    ()` and `service_billed_uoms()` both filter `enabled=True`.
    """
    if not isinstance(changes, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="settings.payload_not_object")
    unknown = set(changes) - {
        "enabled",
        "billing_basis",
        "primary_uom",
        "alt_uom",
        "billed_uom",
        "conversion_factor",
        "revenue_account",
        "base_revenue_account",
    }
    if unknown:
        _refuse_fields(
            [_field_error(f, errors.VAL_FORMAT, "settings.unknown_field") for f in sorted(unknown)]
        )
    service = models.Service.objects.filter(code=service_code, active=True).first()
    if service is None:
        raise errors.NotFoundError()  # BR-TEN-025: closed catalog

    warnings: dict[str, Any] = {}
    with transaction.atomic():
        tenant_id = _tenant_id()
        row = (
            models.TenantService.objects.select_for_update()
            .filter(tenant_id=tenant_id, service=service)
            .first()
        )
        if "enabled" in changes:
            row = _apply_service_toggle(actor, service, row, bool(changes["enabled"]))
        # BR-TEN-1180 BEFORE the units, because the units are read in the light
        # of it: a `capacity` service is priced from a COUNT and the count
        # carries the TARIFF's unit (BR-MET-710), so the warning
        # `_apply_service_uom` returns has to be computed after the declaration
        # it describes, never before.
        if "billing_basis" in changes:
            row, basis_warnings = _apply_service_billing_basis(actor, service, row, changes)
            warnings.update(basis_warnings)
        if UOM_FIELDS & set(changes):
            row, uom_warnings = _apply_service_uom(actor, service, row, changes)
            warnings.update(uom_warnings)
        # GL LAST, and the order is load-bearing: a payload that enables a
        # service AND names its accounts must end on the tenant's choice, not on
        # the default the toggle just seeded. Enable first, override second.
        if "revenue_account" in changes or "base_revenue_account" in changes:
            row = _apply_service_gl_accounts(actor, service, row, changes)
    return {**selectors.service_row(service_code), "warnings": warnings}


def _apply_service_toggle(
    actor: Any, service: models.Service, row: models.TenantService | None, enable: bool
) -> models.TenantService:
    tenant_id = _tenant_id()
    if enable:
        if row is None:
            # Since New mandate 4 (PO 2026-08-17) provisioning creates a row
            # for EVERY service in the platform catalogue, so on a tenant
            # provisioned after 2026-08-18
            # this branch never runs — it is the enablement path for tenants
            # provisioned before the mandate, and it must keep working for
            # exactly as long as one of them exists (hard-won law 4).
            tenant = models.Tenant.objects.get(pk=tenant_id)
            primary, alt = _default_uoms_for(tenant, service.code)
            # Same GL call as provisioning (BR-BIL-010). Without this line a
            # service switched on from S8 AFTER signup would carry a NULL
            # revenue account forever while a service chosen at signup carried
            # one — built, and not wired, for exactly one of the two paths.
            #
            # Since the PO's OQ-115 ruling this call MINTS as well as resolves,
            # and that is what makes the ruling implementable: a water-only
            # utility has no 4140 Gas revenue account, so the moment its clerk
            # switches Gas on from this screen is the moment 4140 has to come
            # into existence. It does, here, in the same transaction.
            revenue_id, base_revenue_id = seams.ensure_service_revenue_accounts(service.code, actor)
            row = models.TenantService.objects.create(
                tenant_id=tenant_id,
                service=service,
                enabled=True,
                # ⚠ **`DEF-3502` — THE SAME FAULT AS `DEF-2409`, ONE PATH OVER,
                # AND THE PARAGRAPH ABOVE IS THE WARNING THAT WAS NOT TAKEN.**
                # It says a column named by provisioning and not here is *"built,
                # and not wired, for exactly one of the two paths"* — and this
                # call then omitted `billing_basis` for a day after `BR-TEN-1180`
                # landed, so every service a clerk switched on from S8 after
                # signup took the model default and was declared **metered**
                # whatever it actually is. Fire, Trash, Solar, Battery, Storm
                # water and Sewer included; a fire line declared metered is
                # refused by the bill run for having no register, which is
                # `DEF-161` again.
                #
                # `_default_basis_for` and not a literal, for the reason the
                # provisioning call gives: the basis and the units must come
                # from ONE map or they will disagree.
                #
                # ⚠ THE DURABLE GUARD IS NOT THIS COMMENT. `test_def3502_
                # toggle_billing_basis.py` TC-2 reads both `create()` calls out
                # of this file and compares their keyword sets, so the NEXT
                # column added to one and not the other goes red instead of
                # quietly taking a model default. Do not delete it to "simplify"
                # a duplicated argument list — the duplication is the defect it
                # is watching.
                billing_basis=_default_basis_for(service.code),
                primary_uom=primary,
                alt_uom=alt,
                revenue_account_id=revenue_id,
                base_revenue_account_id=base_revenue_id,
            )
        elif not row.enabled:
            row.enabled, row.disabled_at = True, None
            row.save(update_fields=["enabled", "disabled_at", "updated_at"])
        _audit(
            actor,
            "settings.service.enabled",
            "tenant_service",
            row.id,
            after={"service": service.code},
        )
        # A service switched on months after signup gets the reference rows the
        # signup path would have given it — the same call, the same seeders,
        # insert-missing. Without it a utility that adds Gas in March has crews
        # that cannot raise a gas leak call-out and nothing anywhere saying so,
        # which is `DEF-3502`'s shape ("built, and not wired, for exactly one of
        # the two paths") on data instead of on a column.
        _seed_service_scoped_reference_data(
            models.Tenant.objects.get(pk=tenant_id), actor
        )
        return row
    # Disable path — guarded (BR-TEN-026): blocked while anything references it.
    schedules = seams.rate_schedule_count(service_code=service.code) or 0
    accounts = seams.active_account_count(service.code) or 0
    if schedules or accounts:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-TEN-026",
            message_key="settings.services.disable_blocked",
            params={
                "service": service.code,
                "rate_schedules": schedules,
                "active_accounts": accounts,
            },
        )
    if row is None or not row.enabled:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-TEN-026",
            message_key="settings.services.not_enabled",
            params={"service": service.code},
        )
    row.enabled, row.disabled_at = False, timezone.now()  # soft: history kept
    row.save(update_fields=["enabled", "disabled_at", "updated_at"])
    _audit(
        actor,
        "settings.service.disabled",
        "tenant_service",
        row.id,
        before={"service": service.code, "enabled": True},
        after={"service": service.code, "enabled": False},
    )
    return row


#: The four unit columns one S8 save writes together, named once so the
#: dispatcher, the refusal and the audit row cannot drift apart (DEF-2311).
#: `billed_uom` and `conversion_factor` joined the set on 2026-08-28; the two
#: before them have been here since US-TEN-008.
UOM_FIELDS: frozenset[str] = frozenset(
    {"primary_uom", "alt_uom", "billed_uom", "conversion_factor"}
)


def _service_conversion_factor(
    row: models.TenantService, changes: dict[str, Any], fe: list[dict[str, Any]]
) -> Decimal | None:
    """The r6.4 register→billed factor, as a Decimal or None. DEF-2311.

    NUMERIC(18,6) — six decimals, the same precision the column declares and
    the same the percentage half of CLAUDE.md rule 2 uses. `None`/`""` CLEARS
    the factor, which is a real thing a tenant does when the two units become
    the same one again; an OMITTED key leaves whatever is stored alone.

    A float is refused rather than coerced: hard rule 2 keeps binary floating
    point out of every stored figure, and a factor multiplies a consumption on
    its way to a price.
    """
    if "conversion_factor" not in changes:
        return row.conversion_factor
    raw = changes["conversion_factor"]
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
    if isinstance(raw, float):
        # ONE message key for both bad shapes, and the choice is deliberate: to
        # the person typing it, a JSON float and the word "nope" are the same
        # event — *that is not a factor we can store* — and a second sentence
        # explaining JSON number types is copy nobody can act on (G33's own
        # note: shorten by deleting RATIONALE, never INSTRUCTION). The REASON a
        # float is refused rather than coerced lives in this docstring, which is
        # what a docstring is for.
        fe.append(
            _field_error("conversion_factor", errors.VAL_FORMAT, "settings.services.factor_format")
        )
        return None
    try:
        value = Decimal(str(raw)).quantize(Decimal("0.000001"))
    except (InvalidOperation, ValueError):
        fe.append(
            _field_error("conversion_factor", errors.VAL_FORMAT, "settings.services.factor_format")
        )
        return None
    if value <= 0:
        # A zero factor prices every reading at nothing and a negative one
        # prices it backwards. Neither is a conversion.
        fe.append(
            _field_error("conversion_factor", errors.VAL_RANGE, "settings.services.factor_positive")
        )
        return None
    return value


def _apply_service_uom(
    actor: Any,
    service: models.Service,
    row: models.TenantService | None,
    changes: dict[str, Any],
) -> tuple[models.TenantService, dict[str, Any]]:
    """The service's four units — primary, alternate, BILLED and the factor.

    ⚠ **THE BILLED UNIT AND ITS FACTOR ARE NEW HERE (DEF-2311, 2026-08-28) AND
    THEY ARE ON THIS PATH RATHER THAN A SECOND ONE ON PURPOSE.** `billed_uom`
    and `conversion_factor` are read by metering, assets and rating through
    `selectors.service_billed_uoms()` and were written by NOTHING, so every
    tenant in the product answered `None` and r6.4's register→billed gate had
    only its refusing half. Two write paths for one service's units is how two
    screens come to disagree about what a tenant declared.

    **BR-RAT-038 IS ENFORCED AT THE DECLARATION, NOT ONLY AT RATING** — the rule
    reads *"read/register unit must match the billed unit or a per-service
    conversion factor must be defined; mismatch with no factor → clear user
    message + rating blocked for that read (no silent conversion)"*. Blocking a
    bill run three weeks later for a sentence somebody typed on this screen is
    the same refusal delivered at the worst possible moment, so a billed unit
    that differs from the primary and states no factor is refused HERE, in the
    field, by name. Nothing is ever converted silently at either end.

    ⚠ **AND ONLY FOR A METERED SERVICE — see the check itself for why.** An
    unmetered service has no register, so there are not two units to reconcile;
    demanding a `month → cart` factor would make the trash declaration BR-RAT-081
    exists for impossible to type.

    **A BILLED UNIT EQUAL TO THE PRIMARY IS STORED AS ITSELF, NOT AS NULL.**
    `None` means *the register's own unit is what is billed* (the selector's own
    docstring says so, and it is what every tenant alive answers today); a
    tenant that has deliberately said *kgal in and kgal out* has stated
    something, and flattening the two into one value would lose which.
    """
    if row is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-TEN-026",
            message_key="settings.services.not_enabled",
            params={"service": service.code},
        )
    fe: list[dict[str, Any]] = []
    primary_code = changes.get("primary_uom", row.primary_uom.code if row.primary_uom else None)
    alt_code = changes.get("alt_uom", row.alt_uom.code if row.alt_uom else None)
    billed_code = changes.get("billed_uom", row.billed_uom.code if row.billed_uom else None)
    factor = _service_conversion_factor(row, changes, fe)
    # ── BR-TEN-1181 (2026-09-02, DEF-3232) — WHICH BASES OWE A UNIT ──────────
    # `row.billing_basis` is the EFFECTIVE value: `update_service` applies the
    # basis before the units, so a payload that states both is judged against
    # what it just declared and not against what the row held a moment ago.
    share = row.billing_basis == models.BILLING_BASIS_SHARE
    if not primary_code and not share:
        # US-TEN-008 TC-5, narrowed to the two bases that HAVE a quantity. A
        # metered service's reading and a capacity service's count are both
        # measured in something (CLAUDE.md hard rule 3), and metering's own
        # validation errors `unit_missing` on a register with no unit.
        fe.append(
            _field_error("primary_uom", errors.VAL_REQUIRED, "settings.services.primary_required")
        )
    if share:
        # BR-TEN-1180 clause (2): a share is *"a percentage of another service's
        # money; no register, no count, and no unit of its own"*. So the four
        # unit fields are NULL for it, and a caller that SUPPLIES one is refused
        # by name rather than having its answer quietly dropped.
        #
        # ⚠ REFUSE WHAT WAS SUPPLIED, CLEAR WHAT WAS NOT. A tenant provisioned
        # before the ruling holds sewer as `share` WITH a stored `kgal` primary —
        # migration `tenancy 0031` moved the basis and deliberately moved no
        # unit — and this save is the repair path for that row. Refusing on a
        # stale value the caller never mentioned would be DEF-3232 again in a
        # different field: a refusal with nothing a clerk can do about it.
        for field, code in (
            ("primary_uom", primary_code),
            ("alt_uom", alt_code),
            ("billed_uom", billed_code),
            ("conversion_factor", factor),
        ):
            if field in changes and code not in (None, ""):
                fe.append(
                    _field_error(
                        field,
                        errors.VAL_FORMAT,
                        "settings.services.uom_not_for_share",
                        service=service.code,
                    )
                )
        primary_code = alt_code = billed_code = None
        factor = None
    if primary_code and alt_code and str(primary_code).lower() == str(alt_code).lower():
        fe.append(
            _field_error("alt_uom", errors.VAL_FORMAT, "settings.services.alt_equals_primary")
        )
    # BR-RAT-038, in the field the tenant is looking at — AND ONLY FOR A
    # METERED SERVICE. The rule's own words are *"read/register unit must match
    # the billed unit"*: no read, no register, nothing to reconcile. An
    # unmetered service is priced from a COUNT that crosses the billing seam
    # unitless and takes the TARIFF's unit (BR-MET-710 / BR-BIL-710), so
    # demanding a month→cart factor here would refuse the one declaration this
    # work exists to make possible — which is exactly the trap DEF-1813 hit
    # from the other side and recorded: *"it turned DEF-161's ruled base-only
    # outcome into a REFUSAL for any tenant that had declared a service
    # unmetered without declaring its billed unit"*.
    if (
        row.metered
        and primary_code
        and billed_code
        and str(primary_code).lower() != str(billed_code).lower()
        and factor is None
    ):
        fe.append(
            _field_error(
                "conversion_factor",
                errors.VAL_UOM_MISMATCH,
                "settings.services.factor_required",
                billed_uom=str(billed_code),
                primary_uom=str(primary_code),
            )
        )
    _refuse_fields(fe)

    def resolve_uom(field: str, code: str | None) -> models.Uom | None:
        if code is None:
            return None
        # BR-TEN-029 / US-TEN-008 TC-4: deactivated entries excluded from NEW picks.
        # DEF-184: …and so are units scoped to a DIFFERENT utility service. It
        # is LITERALLY the filter the picker reads — `selectors.uom_scope_filter`
        # is the one expression both call — because a screen that only draws the
        # right options is a screen, not a rule, and the API is what a second
        # client, a script or a replayed request reaches.
        uom = (
            models.Uom.objects.filter(tenant_id=_tenant_id(), code__iexact=str(code), active=True)
            .filter(selectors.uom_scope_filter(service.code))
            .first()
        )
        if uom is None:
            _refuse_fields(
                [
                    _field_error(
                        field,
                        errors.VAL_UNKNOWN_LOOKUP,
                        "settings.services.uom_unknown",
                        uom=str(code),
                    )
                ]
            )
        return uom

    # ⚠ `str(primary_code) if primary_code else None`, NOT `str(primary_code)`.
    # A share service reaches here with every unit cleared (BR-TEN-1181), and
    # `str(None)` is the four-character string "None" — which `resolve_uom`
    # would look up as a UoM code and refuse as unknown, turning a correct save
    # into a refusal naming a unit nobody typed.
    new_primary = resolve_uom("primary_uom", str(primary_code) if primary_code else None)
    new_alt = resolve_uom("alt_uom", str(alt_code) if alt_code else None)
    new_billed = resolve_uom("billed_uom", str(billed_code) if billed_code else None)
    before = {
        "primary_uom": row.primary_uom.code if row.primary_uom else None,
        "alt_uom": row.alt_uom.code if row.alt_uom else None,
        "billed_uom": row.billed_uom.code if row.billed_uom else None,
        "conversion_factor": (
            None if row.conversion_factor is None else str(row.conversion_factor)
        ),
    }
    warnings: dict[str, Any] = {}
    if row.primary_uom and new_primary and row.primary_uom.pk != new_primary.pk:
        # BR-TEN-027: forward-only; existing schedules in the old unit are NAMED,
        # never converted (count live via the rating seam; None while unwired).
        warnings["rate_schedules_in_old_unit"] = seams.rate_schedule_count(
            uom_code=row.primary_uom.code
        )
    row.primary_uom, row.alt_uom = new_primary, new_alt
    row.billed_uom, row.conversion_factor = new_billed, factor
    row.save(
        update_fields=[
            "primary_uom",
            "alt_uom",
            "billed_uom",
            "conversion_factor",
            "updated_at",
        ]
    )
    after = {
        "primary_uom": new_primary.code if new_primary else None,
        "alt_uom": new_alt.code if new_alt else None,
        "billed_uom": new_billed.code if new_billed else None,
        "conversion_factor": None if factor is None else str(factor),
    }
    if before != after:
        _audit(
            actor,
            "settings.service_uom.updated",
            "tenant_service",
            row.id,
            before=before,
            after=after,
        )
    return row, warnings


def _apply_service_billing_basis(
    actor: Any,
    service: models.Service,
    row: models.TenantService | None,
    changes: dict[str, Any],
) -> tuple[models.TenantService, dict[str, Any]]:
    """BR-TEN-1180 — the utility says HOW this service is priced. DEF-2310 · DEF-2409.

    ── **THE HISTORY, BECAUSE IT IS A SUPERSESSION AND NOT A REWRITE** ────────
    **BR-RAT-081, PO ruling 2026-08-20**, verbatim: *"yes we have to say service
    is meter or unmetered."* The boolean column shipped that day; `DEF-2310` made
    this the first thing in the product that wrote it. Until then `metered=False`
    appeared nowhere outside a test helper, so BR-RAT-090's per-cart billing —
    **3 carts × `$15.00` = `$45.00`, take one away and the next bill is
    `$30.00`** — was reachable only by editing a database row by hand.

    **BR-TEN-1180, PO ruling 2026-09-02**, verbatim: *"Shall we consider Metered,
    % of service and Capacity based"*. It SUPERSEDES the two-state declaration
    above at this sentence, and it does not reverse it: the question BR-RAT-081
    asked was right and the vocabulary was one value short.

    **`DEF-2409` is what the missing value cost, and sewer is the proof.** Sewer
    reads no register, so on the boolean it had to be `metered=False` — and the
    false side MEANS *priced from a COUNT of the unit's assets* (`BR-RAT-090`).
    A sewer connection has no assets, so the count is 0. Sewer is in fact a
    PERCENTAGE of the water usage charge (`BR-RAT-015`): **neither value of the
    boolean was true for it**, and flipping it to unmetered to make the screen
    honest would have told the engine to price sewer by counting carts.

    The three values, and what each means to the bill run — `metered` (a register
    is read), `share` (a percentage of another service's money, no quantity of
    its own) and `capacity` (a COUNT of capacity units on the unit) — are
    declared on `models.BILLING_BASES`, which carries the reasoning.

    ⚠ **THE WRITE PAYLOAD TAKES `billing_basis` AND NO LONGER TAKES `metered`.**
    A clean cut, by the PO's ruling of the same day: *"we are in beta stage - so
    no real utility is actually onboarded yet - so there is no real data yet -
    hence you can fix it; I will delete the DB and relaunch"*. A compatibility
    shim accepting `metered: false` would have to guess which of `share` and
    `capacity` the caller meant, and guessing between those two is the defect.

    ── **BR-TEN-810: THE DECLARATION IS FORWARD-ONLY, AND IT IS NEVER
    RETROACTIVE** ────────────────────────────────────────────────────────────
    *"What happens to history when a service changes from metered to unmetered
    after bills exist"* is a real question and it is answered from law already
    signed rather than invented here:

    * **Issued bills, their lines, the payments against them and the journal
      entries do not move.** CLAUDE.md hard rule 4 — no UPDATE or DELETE on an
      issued invoice; a correction is a NEW row. A declaration typed on a
      settings screen is not a correction to anything already billed.
    * **Reads already recorded do not move either, and they keep billing.**
      DEF-1813's ruling on DEF-161: *"a declared-unmetered service that
      nevertheless has a meter and a GOOD read still bills the read"*. The
      declaration says what an UNREAD point MEANS; it never suppresses a real
      measurement, so nothing a meter recorded is thrown away.
    * **It takes effect on the next bill that has not been priced yet, IN
      FULL** — BR-MET-710 observes the asset count at the SERVICE-PERIOD END
      DATE, so there is no half-metered period and none is invented. Worked:
      trash declared unmetered on 15 September, three carts on the unit, the
      1–30 September cycle not yet billed → September bills `3 × $15.00 =
      `$45.00` by the count seen on 30 September, and August's issued bill is
      untouched.

    **SO IT IS ALLOWED WHILE BILLS EXIST, AND IT WARNS.** The alternative — lock
    it once a bill is issued, the way BR-TEN-042 locks the currency — was
    rejected and the reason is stated so it is not re-litigated: a currency lock
    protects figures ALREADY STORED from being re-read in a different unit,
    while this changes only how the NEXT quantity is obtained. A utility that
    starts collecting carts in its third year must be able to say so. The count
    of accounts that take the service travels back as a warning, exactly as
    BR-TEN-027's forward-only UoM warning does, so the consequence is named
    before it is met.

    **AUDITED UNDER ITS OWN ACTION** (`settings.service_metering.updated`, hard
    rule 7): a change of measurement basis moves money on every subsequent bill
    for the service, and burying it inside the UoM action would make it
    unsearchable in the trail beside the bills it explains.

    ⚠ **THE ACTION NAME DOES NOT CHANGE, AND THAT IS DELIBERATE.** It is the
    same fact changing, and every row already written under
    `settings.service_metering.updated` — by this path and by
    `sample_data.declare_estate_metering`, which shares it on purpose — is part
    of one searchable history. Renaming it would split that history in two at an
    arbitrary date and leave a utility unable to answer *"when did we change how
    trash is priced?"* from one query. What DOES change is the payload: the
    `before` and `after` now carry `billing_basis` with its value, so a row says
    *capacity, not share* rather than merely *not metered* — which is the whole
    ambiguity `DEF-2409` was filed about, and the audit trail was carrying it
    too.
    """
    if row is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-TEN-026",
            message_key="settings.services.not_enabled",
            params={"service": service.code},
        )
    raw = changes["billing_basis"]
    # ⚠ `isinstance(raw, str)` FIRST, and the order matters: `True in
    # BILLING_BASES` is False so a stray boolean would be refused either way,
    # but an unhashable payload (a list, a dict) raises inside `in` rather than
    # refusing, and a 500 is not a validation message.
    if not isinstance(raw, str) or raw not in models.BILLING_BASES:
        _refuse_fields(
            [
                _field_error(
                    "billing_basis",
                    errors.VAL_FORMAT,
                    "settings.services.billing_basis_invalid",
                    allowed=", ".join(models.BILLING_BASES),
                )
            ]
        )
    basis = str(raw)
    if row.billing_basis == basis:
        return row, {}
    previous = row.billing_basis
    row.billing_basis = basis
    row.save(update_fields=["billing_basis", "updated_at"])
    _audit(
        actor,
        "settings.service_metering.updated",
        "tenant_service",
        row.id,
        # ⚠ **`before` IS THE VALUE THAT WAS THERE, READ FROM THE ROW.** The
        # boolean version computed it as `not metered`, which was exact for two
        # values and is a LIE for three — with `share` on file and `capacity`
        # being written, a negation cannot name what was replaced. Read it, do
        # not derive it.
        before={"service": service.code, "billing_basis": previous},
        after={"service": service.code, "billing_basis": basis},
    )
    # BR-TEN-810's named consequence. `None` while the customers lane is
    # unwired — and a null is NOT a zero, which is the same discipline the
    # BR-TEN-026 counts on this screen already keep.
    return row, {"accounts_on_next_bill": seams.active_account_count(service.code)}


#: The two GL columns a tenant may re-point, and the seam field name each one
#: writes. Named once so the refusal, the write and the audit row cannot drift.
SERVICE_GL_FIELDS: tuple[str, ...] = ("revenue_account", "base_revenue_account")


def _apply_service_gl_accounts(
    actor: Any,
    service: models.Service,
    row: models.TenantService | None,
    changes: dict[str, Any],
) -> models.TenantService:
    """The tenant's own GL mapping for a service (PO ruling 2026-08-11, OQ-115).

    Verbatim: *"you create an account, but allow tenant user to override it."*
    The seed points Water revenue at 4110; a utility that keeps water revenue in
    an account of its own numbering re-points it here, and from that moment
    every read resolves THEIR account — `apps/ledger/selectors.py` reads the
    stored pointer, never the chart's default, and the ledger's seed never
    writes this row at all, so no re-provision or repair run can take it back.

    `null` CLEARS a mapping, and that is a real thing a tenant may want (an
    account being retired, a chart being restructured) — so it is accepted
    rather than treated as "field omitted". The consequence is stated where a
    clerk will meet it: an unmapped service's lines cannot be stamped at issue
    and BR-BIL-010 refuses the whole bill, which is the correct refusal and not
    a silent one.

    **WHY THE LEDGER VALIDATES AND NOT THIS FUNCTION.** The FK on
    `tenant_services.revenue_account` guarantees the row exists; it does NOT
    guarantee the row is this tenant's, so without a check a crafted id could
    point one tenant's service at another tenant's account — a cross-tenant read
    of a chart, written into a money path. `seams.ledger_account_is_live` asks
    the module that owns the table (B1 / BR-TEN-013), which also answers False
    for an account the tenant has deactivated (IS-1): revenue must not be mapped
    onto a row their own trial balance treats as retired.
    """
    if row is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-TEN-026",
            message_key="settings.services.not_enabled",
            params={"service": service.code},
        )
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    fe: list[dict[str, Any]] = []
    updates: dict[str, Any] = {}
    for field in SERVICE_GL_FIELDS:
        if field not in changes:
            continue
        value = changes[field]
        new_id = None if value in (None, "") else str(value)
        if new_id is not None and not seams.ledger_account_is_live(new_id):
            fe.append(
                _field_error(
                    field,
                    errors.VAL_UNKNOWN_LOOKUP,
                    "settings.services.gl_account_unknown",
                    account=new_id,
                )
            )
            continue
        old_id = getattr(row, f"{field}_id")
        old_id = str(old_id) if old_id else None
        if old_id == new_id:
            continue
        before[field], after[field] = old_id, new_id
        updates[f"{field}_id"] = new_id
    _refuse_fields(fe)
    if not updates:
        return row
    for attribute, value in updates.items():
        setattr(row, attribute, value)
    row.save(update_fields=[*updates, "updated_at"])
    # BR-TEN-016 / CLAUDE.md rule 7: which bucket a service's revenue lands in
    # is a money decision, so the change carries who and before/after.
    _audit(
        actor,
        "settings.service_gl.updated",
        "tenant_service",
        row.id,
        before={"service": service.code, **before},
        after={"service": service.code, **after},
    )
    return row


# ── S8 Reference data — lookup framework (US-TEN-009/010/011) ───────────────
class LookupListDef:
    """One Reference-data list: tenancy renders/routes, the OWNER validates and
    writes (BR-TEN-031). handler=None until the owning lane registers one —
    such a list 404s (skip-until-wired), it is never guessed."""

    def __init__(self, code: str, owner: str, handler: Any = None) -> None:
        self.code = code
        self.owner = owner
        self.handler = handler


# BR-TEN-036 (OQ-031 closed): former closed enums become seeded, tenant-extensible
# lookup tables OWNED by their modules; BR-TEN-037 (OQ-032 closed): tax
# jurisdictions are tenant-entered. Owners register handlers in AppConfig.ready().
LOOKUP_LISTS: dict[str, LookupListDef] = {
    "uoms": LookupListDef("uoms", "tenancy"),
    # ── CR-004 (2026-08-16): the six r10 SET-04 lists. Tenancy HOSTS the
    # tables; the owner string names the module that owns content and
    # validation (BR-TEN-031), which is what the card header shows and what
    # test_reference_data_completeness checks against SEED_LIST_OWNERS.
    "areas": LookupListDef("areas", "metering"),
    "service_size_classes": LookupListDef("service_size_classes", "metering"),  # BR-TEN-170
    "occupancy_statuses": LookupListDef("occupancy_statuses", "metering"),
    "device_types": LookupListDef("device_types", "metering"),
    "certification_types": LookupListDef("certification_types", "metering"),
    # CR-039 wave C task 12 (BR-TEN-150). The owner string names the module that
    # owns content and validation, which is metering — a category MEANS
    # something about a premises owner, and BR-MET-150 is where that meaning is
    # written. Same owner string as the SEED_LIST_OWNERS route, which
    # tests/test_reference_data_completeness.py pins.
    "owner_categories": LookupListDef("owner_categories", "metering"),
    "import_mappings": LookupListDef("import_mappings", "ledger"),
    "charge_codes": LookupListDef("charge_codes", "rating"),
    "tax_jurisdictions": LookupListDef("tax_jurisdictions", "rating"),
    # CR-166-BRC10 (PO 2026-10-03): the three discount dropdowns — *"Program
    # owner - make this drop down"*, *"Exclusivity group - can you make this
    # drop down"*, *"Who qualifies * - drop down"* — editable per utility.
    # `apps/rating/discount_lists.py` owns content and validation and registers
    # the handlers from `RatingConfig.ready()`.
    "discount_program_owners": LookupListDef("discount_program_owners", "rating"),
    "discount_exclusivity_groups": LookupListDef("discount_exclusivity_groups", "rating"),
    "discount_eligibility": LookupListDef("discount_eligibility", "rating"),
    "reason_codes": LookupListDef("reason_codes", "billing"),
    "payment_methods": LookupListDef("payment_methods", "payments"),
    # DEF-203 (PO ruling 2026-08-28, *"capture bank account in configure. Keep
    # them in section which is logical"*): the tenant's OWN bank accounts. The
    # table is payments' (`bankrec_models.BankAccount`), so payments validates
    # and writes it and registers the handler from AppConfig.ready()
    # (BR-TEN-031). It is the one declared list that is never seeded — see its
    # UNSEEDABLE_REFERENCE_LISTS entry, which is a REASON, not a gap.
    "bank_accounts": LookupListDef("bank_accounts", "payments"),
    # CR-059 CS-18 (2026-09-01): the reconciliation DIFFERENCE reasons. The
    # reason on a bank-rec difference was free text, so nobody could report on
    # cause — how much of this quarter's difference was processor fees and how
    # much was error. The table is payments' own
    # (`bankrec_models.BankRecDifferenceReason`), so payments validates, writes
    # and SEEDS it (BR-TEN-031) and registers the handler from
    # AppConfig.ready(). Unlike `bank_accounts` this one IS seeded — from
    # payments' own ratified constant, not from the fixture (the
    # `premises_types` posture; see the SEED_LIST_OWNERS entry).
    "bank_rec_difference_reasons": LookupListDef("bank_rec_difference_reasons", "payments"),
    "meter_types": LookupListDef("meter_types", "metering"),
    # DEF-017's seventh list (2026-08-10). Declaring the key is what lets
    # `premises_types` be SEEDED and REPORTED like every other list; the S8 card
    # additionally needs apps.metering to register a handler here (and the CRUD
    # services behind it — metering has none today). Until that lands the list
    # is served by metering's own GET /premises/types endpoint exactly as
    # before, and `reference_data_report()` reports it as seeded-but-not-
    # countable rather than pretending either way. Same owner string as the
    # seeder route, which tests/test_reference_data_completeness.py pins.
    "premises_types": LookupListDef("premises_types", "metering"),
    # BR-AST-043 splits the meter catalogs in two: meter_types = what the meter
    # IS · read_methods = how the read is COLLECTED. apps/assets registered a
    # handler for both from the day the rule landed, but this registry declared
    # only the first, so the second logged a skip-until-wired warning at every
    # startup and its S8 card could never render. Same owner string as its twin.
    "read_methods": LookupListDef("read_methods", "metering"),
    "asset_types": LookupListDef("asset_types", "metering"),
    "asset_statuses": LookupListDef("asset_statuses", "metering"),
    "account_statuses": LookupListDef("account_statuses", "customers"),
    "account_types": LookupListDef("account_types", "customers"),
    # CR-010 (PO 2026-08-17): the sub-type tree's tenant-editable second level.
    # apps/customers/lookups.py registers the handler from AppConfig.ready().
    "account_subtypes": LookupListDef("account_subtypes", "customers"),
    # CR-010 A-4 (PO 2026-08-17: "this is correct"): the UNIT_TYPES tuple
    # becomes editable rows — apps/metering/lookups.py registers the handler.
    "unit_types": LookupListDef("unit_types", "metering"),
    # ── CR-070 wave C (2026-09-04): the Work module's five reference lists.
    # Four of these CARDS have been on the S8 grid since 2026-08-16 rendering
    # *"Field work is not part of this release yet…"*, because — in their own
    # config's words — *"no module in the map owns a work order, a crew, a
    # skill or a parts stock, so there is no table to host a row and no owner
    # to author a handler."* `apps.work` is the eleventh code module as of
    # 2026-09-03 and owns all five tables, so the sentence stops and the cards
    # edit real rows (`US-WRK-012`). `apps/work/lookups.py` registers the
    # handlers from `WorkConfig.ready()`.
    #
    # ⚠ `work_parts_categories` is the CARD's long-standing code and the table
    # is `part_categories`. The list code follows the card, not the table:
    # renaming it would move twenty-two catalogue entries to rename something
    # no user ever sees, on the wave whose job is to make the card work.
    "work_order_types": LookupListDef("work_order_types", "work"),
    "work_priorities": LookupListDef("work_priorities", "work"),
    "work_skills": LookupListDef("work_skills", "work"),
    "work_safety_kits": LookupListDef("work_safety_kits", "work"),
    "work_parts_categories": LookupListDef("work_parts_categories", "work"),
    "work_hold_reasons": LookupListDef("work_hold_reasons", "work"),
}


def register_lookup_handler(list_code: str, handler: Any) -> None:
    """Owner modules call this from AppConfig.ready(). Handler contract (duck-typed):
    search(q) → iterable · get(id) → obj|None · serialize(obj) → dict ·
    used_by(obj) → int · create(payload) → obj · update(obj, payload) → obj ·
    set_active(obj, active) · delete(obj). Content validation lives in the
    handler — the owning module's law (BR-TEN-031)."""
    if list_code not in LOOKUP_LISTS:
        raise KeyError(f"unknown reference-data list {list_code!r} (EP-TEN-07)")
    LOOKUP_LISTS[list_code].handler = handler


def lookup_handler(list_code: str) -> Any:
    definition = LOOKUP_LISTS.get(list_code)
    if definition is None or definition.handler is None:
        # Unknown list OR owner lane not landed yet: the resource does not exist
        # on this deployment — 404, never an invented behavior.
        raise errors.NotFoundError()
    return definition.handler


class UomLookupHandler:
    """The UoM list — tenancy-owned content (BR-TEN-031).

    THE ONLY HANDLER THAT OPTS IN to the CR-004 utility-service scope. The
    capability is per-list: `serialize` publishing a `service` key is what tells
    the generic list view to render r10's **Utility service** column, and the
    eleven handlers that do not publish it are untouched and render no column.
    Nine lists are CONFIRMED unscoped by the PO and eight are unruled — none of
    them may grow this field without a ruling of their own.
    """

    def _qs(self) -> Any:
        return models.Uom.objects.filter(tenant_id=_tenant_id()).select_related("service")

    def search(self, q: str | None) -> Any:
        qs = self._qs().order_by("code", "id")  # IS-2 stable secondary sort
        if q and len(q.strip()) >= 2:  # IS-3: server-side, min 2 chars
            term = q.strip()
            qs = qs.filter(Q(code__icontains=term) | Q(name__icontains=term))
        return qs

    def count(self) -> int:
        return self._qs().count()

    def get(self, entry_id: Any) -> models.Uom | None:
        return self._qs().filter(pk=entry_id).first()

    def used_by(self, row: models.Uom) -> int:
        """BR-TEN-029 live count: tenant_services refs (local) + meters.unit
        (metering seam; 0 while unwired — no meter tables exist yet)."""
        local = (
            models.TenantService.objects.filter(tenant_id=_tenant_id())
            .filter(Q(primary_uom=row) | Q(alt_uom=row) | Q(billed_uom=row))
            .count()
        )
        return local + seams.uom_used_by_count(row.code)

    def serialize(self, row: models.Uom) -> dict[str, Any]:
        return {
            "id": str(row.pk),
            "code": row.code,
            "name": row.name,
            # CR-004 task A3: the Utility-service column. `null` is not "unset"
            # — it is the VALUE "All services", and the screen renders it as
            # those words rather than as a blank cell.
            "service": (
                {"id": str(row.service_id), "code": row.service.code} if row.service_id else None
            ),
            "active": row.active,
            "is_system": row.is_system,
            "used_by": self.used_by(row),
        }

    def _check_duplicate(self, code: str, exclude_pk: Any = None) -> None:
        qs = self._qs().filter(code__iexact=code)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        existing = qs.first()
        if existing is not None:
            # US-TEN-010 TC-4: case-insensitive duplicate names the existing entry.
            _refuse_fields(
                [
                    _field_error(
                        "code",
                        errors.VAL_FORMAT,
                        "settings.lookups.duplicate_code",
                        existing=existing.code,
                    )
                ]
            )

    def _resolve_service(self, value: Any) -> models.Service | None:
        """CR-004 task A3 — resolve the scope, or refuse it (BR-TEN-026).

        ⚠ **THE LOGIC MOVED TO `_resolve_tenant_service` ON 2026-09-02 (CR-065)
        AND THIS METHOD IS NOW A DELEGATE.** A second list — `service_size_classes`
        — became scoped that day, and two copies of *"which service tokens does
        this tenant own"* is exactly the drift `GlPointerLookupMixin` was written
        to avoid on the GL pointer, one rule along. The method stays because its
        callers and its tests name it; the rule it states lives once.
        """
        return _resolve_tenant_service(value)

    def _validate(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        fe: list[dict[str, Any]] = []
        out: dict[str, Any] = {}
        unknown = set(payload) - {"code", "name", "service"}
        for field in sorted(unknown):
            fe.append(_field_error(field, errors.VAL_FORMAT, "settings.unknown_field"))
        for field in ("code", "name"):
            if field in payload:
                value = str(payload[field] or "").strip()
                if not value:
                    fe.append(_field_error(field, errors.VAL_REQUIRED, "settings.lookups.required"))
                elif len(value) > 60:
                    fe.append(
                        _field_error(field, errors.VAL_RANGE, "settings.lookups.too_long", max=60)
                    )
                else:
                    out[field] = value
            elif not partial:
                fe.append(_field_error(field, errors.VAL_REQUIRED, "settings.lookups.required"))
        _refuse_fields(fe)
        # OPT-IN, so an omitted `service` is not a cleared one: on create the
        # entry is born unscoped (All services), on update the stored scope
        # stands. Only an explicitly present key changes it.
        if "service" in payload:
            out["service"] = self._resolve_service(payload["service"])
        return out

    def create(self, payload: dict[str, Any]) -> models.Uom:
        cleaned = self._validate(payload, partial=False)
        self._check_duplicate(cleaned["code"])
        return models.Uom.objects.create(
            tenant_id=_tenant_id(),
            code=cleaned["code"],
            name=cleaned["name"],
            service=cleaned.get("service"),
            is_system=False,
            active=True,
        )

    def update(self, row: models.Uom, payload: dict[str, Any]) -> models.Uom:
        cleaned = self._validate(payload, partial=True)
        if "code" in cleaned and cleaned["code"].lower() != row.code.lower():
            self._check_duplicate(cleaned["code"], exclude_pk=row.pk)
        for field, value in cleaned.items():
            setattr(row, field, value)
        row.save(update_fields=[*cleaned.keys(), "updated_at"])
        return row

    def set_active(self, row: models.Uom, active: bool) -> models.Uom:
        row.active = active
        row.save(update_fields=["active", "updated_at"])
        return row

    def delete(self, row: models.Uom) -> None:
        row.delete()


def _resolve_tenant_service(value: Any) -> Any:
    """THE rule, once: resolve a service token against THIS tenant's ENABLED
    services, or refuse it (BR-TEN-026).

    `None` / `""` is a real value — **"All services"** for `uoms`, **"nobody has
    said"** for `service_size_classes` — never an omission, so it resolves to
    `None` and clears the tag.

    THE TENANT CHECK IS THE POINT. `services` is a shared PLATFORM catalog with
    no tenant column, so an id or code alone proves nothing about who may use
    it — the resolution goes through `tenant_services` with `enabled=True`,
    which is what makes "a service of THIS tenant" true rather than assumed. A
    water-only co-op naming `electric` gets the same refusal as a caller naming
    `unicorn`, and deliberately so: which services a utility sells is not
    something the error message should publish back to whoever asked.

    ⚠ **THE SEED DOES NOT COME THROUGH HERE, AND MUST NOT.** A platform fixture
    states what a size class IS — `FL-2` is fire's whether or not this tenant
    sells fire — so `ServiceScopeLookupMixin.seed` reads the catalogue directly.
    This function is the WRITE path, where a person is naming a service.
    """
    if value in (None, ""):
        return None
    if isinstance(value, dict):  # the serialized shape, echoed back by a UI
        value = value.get("id") or value.get("code")
    token = str(value).strip()
    match = Q(service__code__iexact=token)
    try:
        match = match | Q(service_id=UUID(token))
    except (ValueError, AttributeError, TypeError):
        pass  # not a uuid — a code is the only remaining reading
    row = (
        models.TenantService.objects.select_related("service")
        .filter(tenant_id=_tenant_id(), enabled=True)
        .filter(match)
        .first()
    )
    if row is None:
        _refuse_fields(
            [
                _field_error(
                    "service",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "settings.lookups.service_unknown",
                    service=token,
                )
            ]
        )
    return row.service  # type: ignore[union-attr]


class HostedFlatLookupHandler:
    """The BR-TEN-031 duck-typed handler for a FLAT (code · name) reference
    list whose table tenancy HOSTS — see the ReasonCode/PaymentMethod model
    docstrings for why hosting is not owning, and how a list is re-homed.

    Same contract and same shape as apps/assets/lookups._BaseHandler, kept
    deliberately parallel so the two read as one pattern: used_by is LIVE
    (BR-TEN-029) through the owning module's seam, a code freezes once used
    (BR-TEN-030 — enforced by update_lookup_entry against that count), a used
    row cannot be deleted (BR-TEN-034), and a SEEDED row is deactivatable but
    never deletable (BR-TEN-036), even at used_by 0.
    """

    model: Any = None
    list_code: str = ""
    used_by_seam: Any = None

    def _qs(self) -> Any:
        return self.model.objects.filter(tenant_id=_tenant_id())

    def search(self, q: str | None) -> Any:
        qs = self._qs().order_by("code", "id")  # IS-2 stable secondary sort
        if q and len(q.strip()) >= 2:  # IS-3 server-side, min 2 chars
            term = q.strip()
            qs = qs.filter(Q(code__icontains=term) | Q(name__icontains=term))
        return qs

    def count(self) -> int:
        return self._qs().count()

    def get(self, entry_id: Any) -> Any:
        return self._qs().filter(pk=entry_id).first()

    def used_by(self, row: Any) -> int:
        """0 while the owning module is unwired — BY CONSTRUCTION, not by
        guess: that module stores nothing yet, so nothing can reference the
        row (the same honest reading seams.uom_used_by_count documents).

        ⚠ DEF-187. That paragraph was TRUE AS A STATEMENT AND FALSE AS CODE for
        the whole of CR-004: `used_by_seam` defaults to None on the class above,
        this method called it unconditionally, and every one of the six new
        lists answered HTTP 500 `TypeError: 'NoneType' object is not callable`
        the moment a user opened it. The two pre-CR-004 handlers set a real
        seam, so they were unaffected and every test stayed green.

        The `is None` branch below is the sentence the docstring always claimed.
        It is written as an explicit branch rather than a zero-returning default
        on the class attribute, because a lambda sitting in `used_by_seam`
        cannot be told apart from a real seam by a reader or by a test — and
        "which lists have a live reference count" is exactly the fact this
        method exists to make legible."""
        if self.used_by_seam is None:
            return 0
        return int(self.used_by_seam(row.code))

    def serialize(self, row: Any) -> dict[str, Any]:
        return {
            "id": str(row.pk),
            "code": row.code,
            "name": row.name,
            "active": row.active,
            "is_system": row.is_system,
            "used_by": self.used_by(row),
        }

    def _check_duplicate(self, code: str, exclude_pk: Any = None) -> None:
        qs = self._qs().filter(code__iexact=code)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        existing = qs.first()
        if existing is not None:  # BR-TEN-030, US-TEN-010 TC-4
            _refuse_fields(
                [
                    _field_error(
                        "code",
                        errors.VAL_FORMAT,
                        "settings.lookups.duplicate_code",
                        existing=existing.code,
                    )
                ]
            )

    def _validate(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        fe: list[dict[str, Any]] = []
        out: dict[str, Any] = {}
        for field in sorted(set(payload) - {"code", "name"}):
            fe.append(_field_error(field, errors.VAL_FORMAT, "settings.unknown_field"))
        for field in ("code", "name"):
            if field in payload:
                value = str(payload[field] or "").strip()
                if not value:
                    fe.append(_field_error(field, errors.VAL_REQUIRED, "settings.lookups.required"))
                elif len(value) > 60:
                    fe.append(
                        _field_error(field, errors.VAL_RANGE, "settings.lookups.too_long", max=60)
                    )
                else:
                    out[field] = value
            elif not partial:
                fe.append(_field_error(field, errors.VAL_REQUIRED, "settings.lookups.required"))
        _refuse_fields(fe)
        return out

    def create(self, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=False)
        self._check_duplicate(cleaned["code"])
        return self.model.objects.create(
            tenant_id=_tenant_id(), is_system=False, active=True, **cleaned
        )

    def update(self, row: Any, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=True)
        if "code" in cleaned and cleaned["code"].lower() != row.code.lower():
            self._check_duplicate(cleaned["code"], exclude_pk=row.pk)
        for field, value in cleaned.items():
            setattr(row, field, value)
        row.save(update_fields=[*cleaned.keys(), "updated_at"])
        return row

    def set_active(self, row: Any, active: bool) -> Any:
        row.active = active
        row.save(update_fields=["active", "updated_at"])
        return row

    def delete(self, row: Any) -> None:
        if row.is_system:
            # BR-TEN-036 / flows §10: a seeded row is part of the vocabulary
            # every tenant shares — deactivate it, never delete it.
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-TEN-036",
                message_key="settings.lookups.system_row_not_deletable",
                params={"code": row.code},
            )
        row.delete()

    def seed(self, tenant: models.Tenant, entries: list[dict[str, Any]]) -> int:
        """Insert-missing only, is_system=True — the same conservative reading
        of BR-TEN-012 that _seed_uoms documents (no touch-tracking column
        exists, so an existing row is never overwritten)."""
        created = 0
        for entry in entries:
            code = str(entry.get("code", "")).strip()
            name = str(entry.get("name", "")).strip()
            if not code or not name:
                raise errors.SysError(
                    errors.SYS_INTERNAL,
                    message_key="signup.reference_fixture_invalid",
                    params={"reason": f"{self.list_code} entry missing code/name"},
                )
            if not self.model.objects.filter(tenant=tenant, code__iexact=code).exists():
                self.model.objects.create(
                    tenant=tenant, code=code, name=name, is_system=True, active=True
                )
                created += 1
        return created


class ServiceScopeLookupMixin:
    """ONE implementation of *"this flat list's rows name a utility service"*,
    shared by every list that carries the `BR-TEN-078` scope.

    ── WHY A MIXIN, AND WHY IT ARRIVED WITH THE SECOND LIST (CR-065) ─────────
    `uoms` was the only scoped list from CR-004 until 2026-09-02, so its scope
    lived inline on `UomLookupHandler` and had nothing to drift against. Then
    the Product Owner ruled that a size class names its service too, and the
    choice was to copy those five behaviours — publish the key, accept the
    field, refuse an unknown service, tag on seed, filter the picker — or to
    state them once. This is `GlPointerLookupMixin`'s own argument, one rule
    along: *"Copying them would put two statements of one rule in one file, and
    the second one is the one that drifts"* (hard-won law 1).

    ── WHAT `NULL` MEANS, AND WHY THAT IS PER LIST ──────────────────────────
    The MECHANISM is one thing and the MEANING is the owning rule's. On `uoms`
    a null scope is the VALUE *"All services"* (PO 2026-08-16). On
    `service_size_classes` it is *"nobody has said"* — a size class a tenant
    added that nobody has tagged. **Both behave identically and deliberately:
    an untagged row is offered EVERYWHERE.** `BR-TEN-071` forbids deleting a
    tenant's own row, so the alternative would be a row a tenant owns that no
    screen will show them.

    ── THE OFFER RULE LIVES IN THE SELECTOR, NOT HERE ───────────────────────
    `selectors.service_scope_filter` is the one expression — *scoped to THIS
    service, plus everything scoped to none* — because it is asked by a picker
    (what may I OFFER) and by a write (what may I ACCEPT), and a screen that
    draws the right options while the API accepts anything is the shape DEF-184
    already took once.

    ── WHAT SUBCLASSES SET ──────────────────────────────────────────────────
    Nothing. The field is `service` on every list that has it, because unlike a
    GL pointer — where a tender points at CASH and a reason at REVENUE, and one
    shared name would let a reader map one onto the other — there is exactly one
    thing this column can mean.
    """

    def _qs(self) -> Any:
        return super()._qs().select_related("service")  # type: ignore[misc]

    def serialize(self, row: Any) -> dict[str, Any]:
        """The scope, in the shape `UomLookupHandler` already publishes.

        ⚠ **PUBLISHING THIS KEY IS WHAT MAKES THE S8 COLUMN APPEAR**, and
        `referenceDataConfig.serviceScoped` is what makes the screen ASK for it —
        two halves, on purpose, because a list that publishes no `service` key is
        not scoped at all and ABSENT is a different fact from `null`.

        `{id, code}` and never a bare id: the id is what an edit sends back, the
        code is what a person recognises, and `B14` rule 31 forbids a database id
        ever being the value a field SHOWS.
        """
        return {
            **super().serialize(row),  # type: ignore[misc]
            "service": (
                {"id": str(row.service_id), "code": row.service.code} if row.service_id else None
            ),
        }

    def _validate(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        """code/name exactly as every other flat list, plus the service tag.

        The base class refuses every field it does not know by name, so the tag
        is lifted out BEFORE that check and put back after — which keeps one
        refusal path for unknown fields rather than two. (The same shape
        `GlPointerLookupMixin` uses for its account pointer.)

        OPT-IN, so an omitted `service` is not a cleared one: on create the row
        is born untagged, on update the stored tag stands. Only an explicitly
        present key changes it — and an explicit `null` CLEARS it, which is a
        real act a person performs on the form.
        """
        given = "service" in payload
        raw = payload.get("service")
        rest = {key: value for key, value in payload.items() if key != "service"}
        cleaned = super()._validate(rest, partial=partial)  # type: ignore[misc]
        if given:
            cleaned["service"] = _resolve_tenant_service(raw)
        return cleaned

    def create(self, payload: dict[str, Any]) -> Any:
        """The base `create` cannot take the tag, because `_validate` returns a
        `Service` INSTANCE and the base passes `**cleaned` straight to
        `objects.create` — which works, and would silently stop working the day
        the base grows a field allow-list. Named here instead."""
        cleaned = self._validate(payload, partial=False)
        self._check_duplicate(cleaned["code"])  # type: ignore[attr-defined]
        return self.model.objects.create(  # type: ignore[attr-defined]
            tenant_id=_tenant_id(),
            code=cleaned["code"],
            name=cleaned["name"],
            service=cleaned.get("service"),
            is_system=False,
            active=True,
        )

    def scope_filter(self, qs: Any, service_code: str) -> Any:
        """Narrow a list to one service — *this service, plus the untagged*.

        Used by `selectors.lookup_page` when a caller sends `f.service_code`, so
        a fire rate schedule can ASK for fire's sizes rather than fetching sixty
        and choosing. An unknown or misspelled code returns the untagged rows
        rather than raising, exactly as `uoms_for_service` does and for the same
        reason: this is a picker feed, and the screen that asks about a service
        it cannot name has a bigger problem than a short dropdown.
        """
        return qs.filter(selectors.service_scope_filter(service_code))

    def seed(self, tenant: models.Tenant, entries: list[dict[str, Any]]) -> int:
        """Insert-missing, `is_system=True`, WITH the fixture's `service_code`.

        ⚠ **THE SEED READS THE PLATFORM CATALOGUE DIRECTLY AND DOES NOT ASK
        WHETHER THIS TENANT HAS ENABLED THE SERVICE.** A fixture states what a
        size class IS — `FL-2` is fire's whether or not this utility sells fire
        — so a tenant with fire switched off still receives fire's six rows,
        correctly tagged, and simply never sees them on a picker because no
        picker asks about a service they do not sell. Routing this through
        `_resolve_tenant_service` would have refused half the fixture for every
        tenant that did not enable all eleven services at sign-up.

        ⚠ **AN ENTRY WITH NO `service_code` SEEDS UNTAGGED RATHER THAN
        REFUSING.** Every list this mixin serves shares one seeding path with
        the twelve that are not scoped, and a fixture that has not yet grown the
        key is a fixture, not an error.

        BR-TEN-071/BR-TEN-012: an EXISTING row is never touched, tag included.
        A tenant provisioned before CR-065 is filled in by `tenancy/0035`, once,
        and never by a re-run of this.
        """
        created = 0
        for entry in entries:
            code = str(entry.get("code", "")).strip()
            name = str(entry.get("name", "")).strip()
            if not code or not name:
                raise errors.SysError(
                    errors.SYS_INTERNAL,
                    message_key="signup.reference_fixture_invalid",
                    params={"reason": f"{self.list_code} entry missing code/name"},  # type: ignore[attr-defined]
                )
            if self.model.objects.filter(tenant=tenant, code__iexact=code).exists():  # type: ignore[attr-defined]
                continue
            service_code = str(entry.get("service_code", "") or "").strip()
            service = (
                models.Service.objects.filter(code=service_code).first() if service_code else None
            )
            self.model.objects.create(  # type: ignore[attr-defined]
                tenant=tenant,
                code=code,
                name=name,
                service=service,
                is_system=True,
                active=True,
                **self._seed_extra(code, service),
            )
            created += 1
        return created

    def _seed_extra(self, code: str, service: Any) -> dict[str, Any]:
        """Further columns a seeded row is born with — none on most lists.
        `ServiceSizeClassLookupHandler` gives a summing size its capacity."""
        return {}


class GlPointerLookupMixin:
    """ONE implementation of *"this flat list carries a pointer at a ledger
    account"*, shared by the two lists that do.

    ── WHY A MIXIN AND NOT A SECOND COPY (CR-008, 2026-08-17) ────────────────
    `reason_codes.default_gl_account_id` landed earlier the same day with this
    logic written inline. `payment_methods.clearing_gl_account_id` landed hours
    later needing the identical five branches — accept the field, accept `null`
    as a CLEAR, refuse a malformed uuid, ask the LEDGER for ownership+liveness,
    refuse all three failures with one message. Copying them would put two
    statements of one money rule in one file, and the second one is the one
    that drifts (hard-won law 1). So the reason-code handler now READS this
    class rather than owning the logic, and a change to how a GL pointer is
    validated changes both lists or neither.

    ── WHAT SUBCLASSES SET ───────────────────────────────────────────────────
    `GL_FIELD` — the column name, which is deliberately NOT the same on the two
    lists: an adjustment reason points at REVENUE (`default_gl_account_id`) and
    a tender points at CASH (`clearing_gl_account_id`), and one shared name
    would let a reader map a tender onto an income account with nothing
    objecting.

    ── THE CHECK IS THE LEDGER'S, ALWAYS ─────────────────────────────────────
    The table is the ledger's (B1), so `seams.ledger_account_is_live` answers,
    never a query from here. It answers OWNERSHIP as well as liveness — an FK
    would prove the row exists and never prove it is THIS tenant's, which in a
    money path is the whole question — and it REFUSES rather than answering
    True when the ledger publishes no such read, so an unwired ledger stores
    nothing instead of storing everything.
    """

    #: Set by each subclass. The one field beyond code/name the list accepts.
    GL_FIELD: str = ""

    def serialize(self, row: Any) -> dict[str, Any]:
        stored = getattr(row, self.GL_FIELD)
        return {
            **super().serialize(row),  # type: ignore[misc]
            self.GL_FIELD: (str(stored) if stored else None),
        }

    def _validate(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        """code/name exactly as every other flat list, plus the GL pointer.

        The base class refuses every field it does not know by name, so the
        pointer is lifted out BEFORE that check and put back after — which
        keeps one refusal path for unknown fields rather than two.
        """
        gl_given = self.GL_FIELD in payload
        raw = payload.get(self.GL_FIELD)
        rest = {key: value for key, value in payload.items() if key != self.GL_FIELD}
        cleaned = super()._validate(rest, partial=partial)  # type: ignore[misc]
        if not gl_given:
            return cleaned
        if raw is None or str(raw).strip() == "":
            cleaned[self.GL_FIELD] = None  # CLEARS the mapping — a real act
            return cleaned
        try:
            account_id = UUID(str(raw))
        except (AttributeError, TypeError, ValueError):
            _refuse_fields(
                [_field_error(self.GL_FIELD, errors.VAL_FORMAT, "settings.lookups.gl_not_a_uuid")]
            )
            raise  # pragma: no cover - _refuse_fields always raises
        if not seams.ledger_account_is_live(account_id):
            # Unknown, another tenant's, or deactivated (IS-1) — one refusal for
            # all three, because telling them apart would confirm the existence
            # of another tenant's account id (HR-1's reasoning, one layer down).
            _refuse_fields(
                [
                    _field_error(
                        self.GL_FIELD,
                        errors.VAL_UNKNOWN_LOOKUP,
                        "settings.lookups.gl_account_unknown",
                        account=str(account_id),
                    )
                ]
            )
        cleaned[self.GL_FIELD] = account_id
        return cleaned


class ReasonCodeLookupHandler(GlPointerLookupMixin, HostedFlatLookupHandler):
    """/lookups/reason_codes — correction / penalty-theft / assessed-read /
    write-off / reconcile-difference families (BR-BIL-014/019, BR-PAY-020 per
    the EP-TEN-07 settings-audit upgrade); content owner is billing.

    ── THE FIFTH MAPPING SECTION (CR-008 ruling 9, PO 2026-08-17) ────────────
    The PO was asked whether adjustment reasons should carry their own GL
    account and answered *"make it separate"*, so this list is the only flat
    lookup with a sixth field: `default_gl_account_id`, the column US-TEN-010
    §5 specified and that the model deliberately did not carry while no ledger
    table existed. A *billing error* credit and a *goodwill* credit are the
    same shape and different money, and a utility's auditor reads them apart.

    The account is validated by the LEDGER (`seams.ledger_account_is_live`),
    never here: the table is the ledger's (B1), and the check answers
    OWNERSHIP as well as liveness — an FK would prove the row exists and never
    prove it is THIS tenant's, which in a money path is the whole question.
    `null` CLEARS the mapping and is accepted, because retiring a mapping is a
    real thing a tenant does; an unmapped reason is not refused anywhere, and
    nothing about posting changes today.
    """

    model = models.ReasonCode
    list_code = "reason_codes"
    used_by_seam = staticmethod(seams.reason_code_used_by_count)
    #: The one field beyond code/name this list accepts (CR-008 ruling 9).
    #: Validated by `GlPointerLookupMixin`, which this handler shares with
    #: PaymentMethodLookupHandler so the two cannot drift on what a usable
    #: account is.
    GL_FIELD = "default_gl_account_id"


class PaymentMethodLookupHandler(GlPointerLookupMixin, HostedFlatLookupHandler):
    """/lookups/payment_methods — OQ-031 CLOSED turned B2's `payment_method_t`
    enum into this seeded, tenant-extensible list (BR-TEN-036); content owner
    is payments. Seeds are the W0 fixture's seven, `wire` (BR-PAY-026) and
    `money_order` (BR-TEN-041 upgrade) included.

    ── THE TENDER'S CASH/CLEARING ACCOUNT (CR-008, PO 2026-08-17) ────────────
    The PO was shown the gap in plain English — *"a utility taking card,
    cheque, cash and IVR has nowhere to say that card lands in a merchant
    clearing account and cheques in the bank"* — and ruled *"Im good with
    all"*. `clearing_gl_account_id` is that column, and this list is where it
    is written, from Settings → Accounting → GL mapping.

    ⚠ **IT IS THE CASH SIDE.** Every other GL pointer in the product is the
    REVENUE side (where a bill's money is earned); this one is where a
    customer's money is received. The names differ so a reader cannot map a
    tender onto an income account with nothing objecting.

    ⚠ **POSTING IS WIRED SINCE 2026-08-18 (CR-008 B-10; this paragraph said
    the opposite while OQ-264's second half was open).** The PO ruled it in
    (*"10 - A inside CR-008 now"*, 2026-08-17) and both legs moved in ONE
    change: the receipt debits this account when set, and reconciliation
    credits what each receipt actually debited, read from the entries. NULL
    still means undeposited funds — the pre-B-10 behaviour, unchanged. The
    screen's sentence is updated with the same slice.
    """

    model = models.PaymentMethod
    list_code = "payment_methods"
    used_by_seam = staticmethod(seams.payment_method_used_by_count)
    #: CR-008 second-set ruling 1 — see the class docstring for why the name
    #: differs from the reason-code list's.
    GL_FIELD = "clearing_gl_account_id"


# ── CR-004: the six r10 SET-04 lists tenancy now hosts ──────────────────────
# Each is the BR-TEN-036 flat shape, so each is three lines on top of
# HostedFlatLookupHandler. `used_by_seam` is left at the base default for all
# six: no owning module exposes a reference-count seam for them yet, so
# used_by is the LOCAL count and nothing is invented. That has one visible
# consequence, stated rather than hidden — BR-TEN-034's audit-lock cannot yet
# see a use that lives in another module's table, so a row may be deletable
# here that a wired seam would lock. The seams land with the owning lanes.


class AreaLookupHandler(HostedFlatLookupHandler):
    """/lookups/areas — the districts a premises is TAGGED with; owner metering.

    ⚠ **GEOGRAPHY ONLY, AND THAT IS A RULING — OQ-338, CLOSED 2026-08-23. PO
    verbatim: *"A: geography only - option a"*.** This line read *"districts
    and ROUTES premises group by"* until CR-029 RC-W6b, which is the r10
    confusion the ruling closed: in that prototype SET-04's list duplicated the
    routes registry byte for byte and one premises ended up on Route 3 and
    Route 1 at once. **An area says WHERE a premises is. A ROUTE says who reads
    it, and a route is created and edited in exactly ONE place — the routes
    registry (SET-05).** Nothing route-shaped belongs on this list: no route
    column, no route count, no route editing. `tests/test_cr029_rcw5_naming.py`
    pins all three, including that this handler REFUSES a route-shaped field
    rather than ignoring it.

    ⚠ **THE ONE HOSTED LIST THAT IS NOT FLAT (BR-MET-066b, PO ruling
    2026-08-16).** Every other list on this page is `code · name`; this one
    also takes a `parent_code`. *"user can define their own areas and we wil
    tag them to premises ; in CR06 you can use area and sub area for
    filtering."*

    **A row with no parent IS an area. A row with a parent IS a sub-area.**

    `parent_code`, not `parent_id`: this list is edited on a settings screen
    where a human types codes, and every other field on it is a code. The
    handler resolves it and refuses an unknown one by name.

    **DEPTH IS EXACTLY TWO AND IT IS ENFORCED HERE**, in the one place a
    parent is ever set — not by a database trigger, which would be a second
    statement of the same rule and the one that drifts (hard-won law 1). Two
    refusals implement it: a parent that itself has a parent (a grandchild),
    and a row pointed at itself.
    """

    model = models.Area
    list_code = "areas"

    def serialize(self, row: Any) -> dict[str, Any]:
        parent = row.parent if row.parent_id else None
        return {
            **super().serialize(row),
            "parent_id": str(row.parent_id) if row.parent_id else None,
            "parent_code": parent.code if parent else None,
            "parent_name": parent.name if parent else None,
            # The FILTER needs to know which rows are pickable as parents, and
            # a client computing it from `parent_id is None` would be a second
            # implementation of BR-MET-066b's depth rule.
            "is_sub_area": row.parent_id is not None,
            # ⚠ **r10's OWN CARD TEXT, EARNED BACK (CR-039 wave E task 22).**
            # SET-04 draws `North district · 3 sub-areas`, and the seed fixture
            # carried those counts as literal NAME TEXT until CR-010 A-section
            # stripped them — reference_sweep's V1.0.0.1 entry says why in one
            # sentence: *"the four area names cleaned of r10's '· N sub-areas'
            # counts, which claimed sub-areas no tenant has."* The counts were
            # removed because they were a CLAIM. Now that sub-areas are seeded
            # they are a FACT, so they come back as a COUNTED FIELD rather than
            # as words baked into a name — which is the whole difference.
            # Always an integer, 0 included: `—` and `0 sub-areas` are the same
            # fact and a screen that draws one of them is enough.
            "sub_area_count": row.sub_areas.count(),
            # CR-161-BRC10 W4 — the utility's own answers, read by the Areas
            # card's dialog (to pre-fill) and its list (the `AREA_LIST` column).
            "custom_data": dict(row.custom_data or {}),
        }

    def seed(self, tenant: models.Tenant, entries: list[dict[str, Any]]) -> int:
        """The fixture's areas AND their sub-areas — BR-MET-066b's second level.

        ⚠ **THIS OVERRIDE EXISTS BECAUSE THE BASE `seed` READS `code` AND `name`
        AND NOTHING ELSE.** `areas` is the one hosted list that is not flat, so
        a fixture entry carrying `parent_code` went through
        `HostedFlatLookupHandler.seed` with the key silently discarded: the row
        landed, top-level, and no error was raised anywhere. That is exactly the
        shape of hard-won law 2 — the column, the two refusals, the Parent
        picker, the `area_path` string and the premises tag were ALL built and
        the only thing that could put a value in `parent_id` was a human typing
        one on a settings screen. Every tenant provisioned to 2026-08-26 had
        four flat areas, which is what the PO was looking at when they asked
        *"Why you dont have sub areas below"*.

        **TWO PASSES, AND THE ORDER IS THE WHOLE MECHANISM.** A child's parent
        must exist before the child can point at it, and a fixture is a list
        with no guaranteed order. Pass 1 creates every parentless entry; pass 2
        creates the children and resolves each `parent_code` through
        `_resolve_parent`, which is the SAME function the settings screen goes
        through — so the depth cap, the self-reference refusal and the unknown-
        code refusal are stated once and apply to a fixture exactly as they
        apply to a person (hard-won law 1: no second statement of the rule).

        **INSERT-MISSING, like every other seeder here (BR-TEN-012).** A replay
        writes nothing. ⚠ An area that ALREADY EXISTS is not re-parented: a
        tenant who promoted a sub-area to a district, or re-hung it under
        another one, has made a decision, and a version bump re-delivering the
        fixture must not quietly undo it. The consequence is stated rather than
        hidden — a tenant seeded before this override keeps four flat areas and
        RECEIVES the three sub-areas as new rows, which is the right outcome
        and is what the repair door (`seed_demo --tenant`) delivers.
        """
        created = 0
        rows = [dict(entry) for entry in entries]
        for wants_parent in (False, True):
            for entry in rows:
                parent_code = str(entry.get("parent_code") or "").strip()
                if bool(parent_code) is not wants_parent:
                    continue
                code = str(entry.get("code", "")).strip()
                name = str(entry.get("name", "")).strip()
                if not code or not name:
                    raise errors.SysError(
                        errors.SYS_INTERNAL,
                        message_key="signup.reference_fixture_invalid",
                        params={"reason": f"{self.list_code} entry missing code/name"},
                    )
                if self.model.objects.filter(tenant=tenant, code__iexact=code).exists():
                    continue
                parent = self._resolve_parent(parent_code, tenant=tenant) if parent_code else None
                self.model.objects.create(
                    tenant=tenant,
                    code=code,
                    name=name,
                    parent=parent,
                    is_system=True,
                    active=True,
                )
                created += 1
        return created

    def _resolve_parent(self, value: Any, *, own_pk: Any = None, tenant: Any = None) -> Any:
        """BR-MET-066b: resolve `parent_code` and enforce the two-level cap.

        `tenant` is passed by `seed` and by nothing else. `_qs()` scopes itself
        to the tenant IN CONTEXT, which is right for every screen call and is
        an assumption a seeder must not make: `seed` is handed its tenant as an
        argument and is the one caller that can be sure which one it means.
        """
        if value in (None, ""):
            return None
        qs = self._qs() if tenant is None else self.model.objects.filter(tenant=tenant)
        parent = qs.filter(code__iexact=str(value).strip()).first()
        if parent is None:
            _refuse_fields(
                [
                    _field_error(
                        "parent_code",
                        errors.VAL_UNKNOWN_LOOKUP,
                        "settings.areas.parent_unknown",
                        picked=str(value),
                    )
                ]
            )
        if own_pk is not None and str(parent.pk) == str(own_pk):
            _refuse_fields(
                [_field_error("parent_code", errors.VAL_FORMAT, "settings.areas.parent_self")]
            )
        if parent.parent_id is not None:
            # A sub-area may not itself be a parent — r10 draws two levels and
            # the corpus describes no third.
            _refuse_fields(
                [
                    _field_error(
                        "parent_code",
                        errors.VAL_FORMAT,
                        "settings.areas.parent_is_sub_area",
                        picked=parent.code,
                        picked_parent=parent.parent.code,
                    )
                ]
            )
        return parent

    def _validate(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        # `parent_code` and `custom_data` are handled by create/update below;
        # hide them from the base validator, which refuses every field it does
        # not know.
        stripped = {k: v for k, v in payload.items() if k not in ("parent_code", "custom_data")}
        return super()._validate(stripped, partial=partial)

    #: CR-161-BRC10 W4 — the Areas card's add/edit dialog is the ONE screen
    #: that types an area's own fields (`custom_fields.SLOTS`, `AREA_FORM`).
    #: It always sends `custom_data` (`{}` when the utility has none), and no
    #: other door does — the seeder, the sweep and the import never name it —
    #: so the key's presence is what says the answers were typed there, and a
    #: required field binds only on this dialog (BR-TEN-052 as amended).
    CUSTOM_SCREEN = "AREA_FORM"

    def _custom(self, payload: dict[str, Any], existing: Any) -> dict[str, Any] | None:
        """The cleaned answers, or None when this door sent none. Validated by
        `custom_fields.validate_custom_data` — the ONE validator — BEFORE the
        row is written, so a refusal leaves nothing behind."""
        if "custom_data" not in payload:
            return None
        return validate_custom_data_for(
            "areas",
            payload.get("custom_data") or {},
            screen=self.CUSTOM_SCREEN,
            existing=existing,
        )

    def create(self, payload: dict[str, Any]) -> Any:
        custom = self._custom(payload, None)
        row = super().create(payload)
        if "parent_code" in payload:
            row.parent = self._resolve_parent(payload["parent_code"], own_pk=row.pk)
            row.save(update_fields=["parent", "updated_at"])
        if custom is not None:
            row.custom_data = custom
            row.save(update_fields=["custom_data", "updated_at"])
        return row

    def update(self, row: Any, payload: dict[str, Any]) -> Any:
        custom = self._custom(payload, dict(row.custom_data or {}))
        row = super().update(row, payload)
        if custom is not None and custom != dict(row.custom_data or {}):
            row.custom_data = custom
            row.save(update_fields=["custom_data", "updated_at"])
        if "parent_code" in payload:
            new_parent = self._resolve_parent(payload["parent_code"], own_pk=row.pk)
            if new_parent is None and row.sub_areas.exists():
                # Nothing to refuse — clearing a parent on a row that HAS
                # children is fine; it just promotes it back to top level.
                pass
            if new_parent is not None and row.sub_areas.exists():
                # …but giving a parent to a row that already has children
                # would create the third level the rule forbids, from the
                # other direction. `_resolve_parent` cannot see this one.
                _refuse_fields(
                    [
                        _field_error(
                            "parent_code",
                            errors.VAL_FORMAT,
                            "settings.areas.has_sub_areas",
                            count=row.sub_areas.count(),
                        )
                    ]
                )
            row.parent = new_parent
            row.save(update_fields=["parent", "updated_at"])
        return row

    def delete(self, row: Any) -> None:
        """An area with sub-areas refuses deletion NAMING THEM, rather than
        letting the PROTECT FK surface as a 500. Same shape as BR-TEN-034's
        used-row refusal: the user is told what is in the way."""
        children = row.sub_areas.count()
        if children:
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-MET-066b",
                message_key="settings.areas.delete_blocked_sub_areas",
                params={"code": row.code, "sub_areas": children},
            )
        super().delete(row)


class ServiceSizeClassLookupHandler(ServiceScopeLookupMixin, HostedFlatLookupHandler):
    """/lookups/service_size_classes — owner metering. Code, name and the utility
    SERVICE the size belongs to; the base charge r10 renders on this card is
    money and stays on a B4 screen.

    ⚠ **THIS DOCSTRING SAID *"Codes and names only"* UNTIL 2026-09-02 AND THAT
    SENTENCE WAS THE DEFECT (`DEF-2385`, `CR-065`).** It was accurate about the
    code and wrong about the world: `RATIFIED_SERVICE_SIZE_CLASSES` has been
    KEYED BY SERVICE since it was written — it knows `FL-2` is fire's and `E-CT`
    is electric's — and the seeding path read that map for its codes and names
    and threw the key away. So the Fire rate schedule offered *Electric
    CT-metered*, and the screens could not filter because there was nothing to
    filter on. Hard-won law 2 (*built is not wired*) on reference DATA.

    **PO ruling 2026-09-02, verbatim, with a screenshot of that screen:** *"This
    is where we are setting rates for fire  you should show only capacity for
    fire . in Setting a capacity needs to tags to utility services ."* It
    SUPERSEDES `BR-TEN-078` and `BR-TEN-170` for this one list — both had ruled
    it unscoped, twice — and the supersession is written into those rules and
    the decision log, dated. Every other list stays unscoped.

    **NULL means "nobody has said" and lists on every service** (`BR-TEN-071`:
    a tenant's own row is never deleted, so it must never become invisible).
    `OQ-1380` asks whether one size may belong to several services and is OPEN;
    a 2" pipe is a water size and a fire size, and the seed spells the two apart
    as `W-2` and `FL-2` so nothing waits on it.

    ⚠ **RENAMED FROM `meter_size_classes` ON 2026-08-27 — BR-TEN-170.** PO
    verbatim: *"it is utility service size class"*. Four of the five services
    BR-TEN-171 adds have no meter — storm water is sized by the PROPERTY,
    broadband by the TIER BOUGHT, solar by INVERTER CAPACITY, battery by ITS
    RATING — so the old name could not hold them without lying about what it
    was sizing.

    ⚠ **THE HOSTED TABLE IS STILL `meter_size_classes` AND `models.MeterSizeClass`
    IS STILL ITS MODEL (DEF-970).** `list_code` is the name a person meets — the
    API path, the S8 card, the seed-run ledger — and it is what the ruling
    renamed. The physical name is invisible to every user, and moving it is a B2
    schema change with a migration, four RLS policy renames and its own review.
    The split is deliberate and is written into BR-TEN-170 rather than left to be
    discovered.

    The CONTENT is `apps.tenancy.service_size_classes`, not this class: which
    services have bands, which have none BY RULING (sewer) and which have none
    BY ABSENCE OF ONE (thermal steam → OQ-560; battery was the second until the
    PO dissolved OQ-561). The fixture mirrors it — including, since CR-065, the
    SERVICE each row belongs to — and a test refuses drift."""

    model = models.MeterSizeClass  # DEF-970 — table name, not list name
    list_code = "service_size_classes"

    def serialize(self, row: Any) -> dict[str, Any]:
        """⊕ **`DEF-CUS-9840` — HOW MUCH ONE SIZE IS, for a service that SUMS.**

        New Connect step 3 reads *Solar · 3 panels · 21 kW* on a unit's service
        row (PO ruling (a), 2026-10-06). The 21 is the same sum the bill takes
        (`BR-RAT-090` through `service_size_classes.total_capacity`), so the
        screen must read the ratified ladder the bill reads — never a kW typed
        per size in a component. `capacity` is that ladder's figure for this
        row's code on its own service, as a string (a quantity, never money and
        never a float); `capacity_uom` its unit (hard rule 3).

        **Both `null` is a finished answer**: a COUNTED service (trash, fire), a
        banded one, a row with no service, or a tenant's own code the ladder
        does not hold — the screen then counts the pieces and sums nothing,
        which is exactly what the bill would refuse to sum either."""
        out = super().serialize(row)
        capacity: str | None = None
        uom: str | None = None
        service_code = row.service.code if row.service_id else None
        if service_code:
            from apps.tenancy import service_size_classes as ladder

            # ⊕ `DEF-RAT-10220` — the ROW's own capacity wins; the ladder
            # answers only for a row that carries none (the same order the
            # bill reads in, `metering.seams.total_installed_capacity`).
            own = (
                {row.code.strip().casefold(): row.capacity}
                if row.capacity is not None
                else None
            )
            try:
                uom = ladder.capacity_uom_for_service(service_code)
                if uom is not None:
                    capacity = str(ladder.capacity_of(service_code, row.code, own))
            except (KeyError, ladder.SizeClassNotRuled, ladder.NotACapacityService):
                capacity = None
            if capacity is None:
                uom = None
        return {**out, "capacity": capacity, "capacity_uom": uom}

    # ── DEF-RAT-10220 · a size of a SUMMING service carries its capacity ─────
    # PO 2026-10-17: *"enters its kW (e.g. 47.84), stored to 4 decimals"*, and
    # *"do not hard code anything … it should able to handle dyanmic
    # capacities"*. WHICH services ask is configuration —
    # `service_size_classes.capacity_uom_for_service` — never a name list:
    # solar and battery (kW), thermal (ton), broadband (Mbps), storm water
    # (ERU) all ask; trash, fire and every banded service never do.

    @staticmethod
    def _capacity_uom(service: Any) -> str | None:
        if service is None:
            return None
        from apps.tenancy import service_size_classes as ladder

        try:
            return ladder.capacity_uom_for_service(service.code)
        except (KeyError, ladder.SizeClassNotRuled):
            return None

    @staticmethod
    def _parse_capacity(raw: Any) -> Any:
        """`None` for blank; a 4-dp `Decimal` > 0; a field refusal otherwise.
        A string or int, never a float (hard rule 2's reasoning: this number
        is multiplied by a price)."""
        from decimal import Decimal, InvalidOperation

        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return None
        if isinstance(raw, (float, bool)):
            _refuse_fields(
                [_field_error("capacity", errors.VAL_FORMAT, "settings.sizeClasses.capacityInvalid")]
            )
        try:
            value = Decimal(str(raw).strip())
        except (InvalidOperation, ValueError):
            value = None
        if (
            value is None
            or not value.is_finite()
            or value <= 0
            or int(value.as_tuple().exponent) < -4
            or value >= Decimal("100000000000000")
        ):
            _refuse_fields(
                [_field_error("capacity", errors.VAL_RANGE, "settings.sizeClasses.capacityInvalid")]
            )
        assert value is not None
        return value.quantize(Decimal("0.0001"))

    def _validate(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        given = "capacity" in payload
        raw = payload.get("capacity")
        rest = {key: value for key, value in payload.items() if key != "capacity"}
        cleaned = super()._validate(rest, partial=partial)
        if given:
            cleaned["capacity"] = self._parse_capacity(raw)
        return cleaned

    def _settle_capacity(self, cleaned: dict[str, Any], service: Any, *, current: Any) -> None:
        """Make `cleaned["capacity"]` agree with the service's billing shape.
        A summing service REQUIRES a capacity (> 0); any other service carries
        none, and a capacity sent for one is refused rather than dropped."""
        uom = self._capacity_uom(service)
        if uom is None:
            if cleaned.get("capacity") is not None:
                _refuse_fields(
                    [
                        _field_error(
                            "capacity",
                            errors.VAL_FORMAT,
                            "settings.sizeClasses.capacityNotApplicable",
                        )
                    ]
                )
            if current is not None:
                cleaned["capacity"] = None
            return
        effective = cleaned["capacity"] if "capacity" in cleaned else current
        if effective is None:
            _refuse_fields(
                [
                    _field_error(
                        "capacity",
                        errors.VAL_REQUIRED,
                        "settings.sizeClasses.capacityRequired",
                        uom=uom,
                    )
                ]
            )

    def create(self, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=False)
        self._check_duplicate(cleaned["code"])
        self._settle_capacity(cleaned, cleaned.get("service"), current=None)
        return self.model.objects.create(
            tenant_id=_tenant_id(),
            code=cleaned["code"],
            name=cleaned["name"],
            service=cleaned.get("service"),
            capacity=cleaned.get("capacity"),
            is_system=False,
            active=True,
        )

    def update(self, row: Any, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=True)
        if "code" in cleaned and cleaned["code"].lower() != row.code.lower():
            self._check_duplicate(cleaned["code"], exclude_pk=row.pk)
        service = cleaned["service"] if "service" in cleaned else row.service
        self._settle_capacity(cleaned, service, current=row.capacity)
        for field, value in cleaned.items():
            setattr(row, field, value)
        row.save(update_fields=[*cleaned.keys(), "updated_at"])
        return row

    def _seed_extra(self, code: str, service: Any) -> dict[str, Any]:
        """A seeded size of a summing service is born with the ratified
        ladder's figure — the ladder is the SEED SOURCE, the row is what every
        reader asks (`tenancy/0064` back-fills tenants seeded before)."""
        if self._capacity_uom(service) is None:
            return {}
        from apps.tenancy import service_size_classes as ladder

        try:
            return {"capacity": ladder.capacity_of(service.code, code)}
        except (KeyError, ladder.SizeClassNotRuled, ladder.NotACapacityService):
            return {}


class OccupancyStatusLookupHandler(HostedFlatLookupHandler):
    """/lookups/occupancy_statuses — owner metering. STRUCTURAL: the values are
    billing behaviour, so the sample-data toggle never suppresses them."""

    model = models.OccupancyStatus
    list_code = "occupancy_statuses"


class DeviceTypeLookupHandler(HostedFlatLookupHandler):
    """/lookups/device_types — behind-the-meter devices; owner metering."""

    model = models.DeviceType
    list_code = "device_types"


class CertificationTypeLookupHandler(HostedFlatLookupHandler):
    """/lookups/certification_types — owner metering."""

    model = models.CertificationType
    list_code = "certification_types"


class PremisesOwnerCategoryLookupHandler(HostedFlatLookupHandler):
    """/lookups/owner_categories — WHAT KIND OF PARTY a premises owner is;
    owner metering (BR-TEN-150, BR-MET-150).

    Codes and names only, like every other flat list here. There is no contact
    column and no description column on the CATEGORY — the party's details live
    on `premises_owners`, and the PO's *"no richer text"* (2026-08-27) governs
    that table too.

    STRUCTURAL (see `STRUCTURAL_REFERENCE_LISTS`): `premises_owners.category_id`
    is NOT NULL, so a tenant whose S111 toggle emptied this list could not
    record an owner at all.
    """

    model = models.PremisesOwnerCategory
    list_code = "owner_categories"


class ImportMappingLookupHandler(HostedFlatLookupHandler):
    """/lookups/import_mappings — saved ETL column maps; owner ledger.

    BR-AST-048 (CR-028): the list now seeds ONE GENERATED system default per
    assets import target — see the model docstring. TENANT rows are still
    never fixture-seeded (a mapping describes the tenant's own file layout).

    ⚠ **A TEMPLATE'S `mapping` IS NEVER TENANT-EDITED THROUGH THIS SURFACE.**
    The base `_validate` accepts `code`/`name` only, so rename/deactivate work
    exactly as on every list, and the map content can only ever be written by
    the seed (system rows) or `save_import_mapping` (copy-on-write tenant
    rows) — which is BR-AST-048's "never mutated" made structural.
    """

    model = models.ImportMapping
    list_code = "import_mappings"

    def serialize(self, row: Any) -> dict[str, Any]:
        payload = super().serialize(row)
        payload["target"] = row.target
        # r10 SET-04 draws "Meter fleet v2 · 14 columns" — the COUNT, never
        # the map itself, which is a payload no list screen needs.
        payload["column_count"] = len(row.mapping or {})
        return payload

    def seed(self, tenant: models.Tenant, entries: list[dict[str, Any]]) -> int:
        """BR-AST-048's seed: insert-missing by code, and — for a SYSTEM row
        that already exists — refresh `target`/`mapping` to the regenerated
        contract ("when a target gains a column, the regenerated default picks
        it up"). The tenant's own `name` (renamable) and `active`
        (deactivatable) are never touched, and tenant rows never are at all.
        """
        created = 0
        for entry in entries:
            code = str(entry.get("code", "")).strip()
            name = str(entry.get("name", "")).strip()
            if not code or not name:
                raise errors.SysError(
                    errors.SYS_INTERNAL,
                    message_key="signup.reference_fixture_invalid",
                    params={"reason": f"{self.list_code} entry missing code/name"},
                )
            existing = self.model.objects.filter(tenant=tenant, code__iexact=code).first()
            if existing is None:
                self.model.objects.create(
                    tenant=tenant,
                    code=code,
                    name=name,
                    target=entry.get("target"),
                    mapping=entry.get("mapping"),
                    is_system=True,
                    active=True,
                )
                created += 1
            elif existing.is_system and (
                existing.mapping != entry.get("mapping") or existing.target != entry.get("target")
            ):
                existing.mapping = entry.get("mapping")
                existing.target = entry.get("target")
                existing.save(update_fields=["mapping", "target", "updated_at"])
        return created


def save_import_mapping(
    actor: Any, *, name: str, target: str, mapping: dict[str, Any]
) -> dict[str, Any]:
    """BR-AST-048's copy-on-write: "Save mapping as template" ALWAYS creates a
    NEW tenant row — never updates a system default, whatever name the tenant
    chose (two rows may share a NAME; the CODE is minted unique). Called by
    the runner through the metering→tenancy seam: `import_mappings` is
    tenancy's table and this is its one lawful tenant-map writer."""
    cleaned_name = str(name or "").strip()
    if not cleaned_name:
        raise errors.ValidationError(errors.VAL_REQUIRED, message_key="settings.lookups.required")
    if not isinstance(mapping, dict) or not mapping:
        raise errors.ValidationError(errors.VAL_REQUIRED, message_key="settings.lookups.required")
    base = re.sub(r"[^a-z0-9]+", "_", cleaned_name.lower()).strip("_") or "mapping"
    code = base
    suffix = 1
    while models.ImportMapping.objects.filter(tenant_id=_tenant_id(), code__iexact=code).exists():
        suffix += 1
        code = f"{base}_{suffix}"
    row = models.ImportMapping.objects.create(
        tenant_id=_tenant_id(),
        code=code,
        name=cleaned_name[:60],
        target=str(target or "") or None,
        mapping=mapping,
        is_system=False,
        active=True,
    )
    _audit(
        actor,
        "import_mapping.saved",
        "import_mapping",
        row.id,
        after={"name": row.name, "target": row.target, "columns": len(mapping)},
    )
    return {
        "id": str(row.id),
        "code": row.code,
        "name": row.name,
        "target": row.target,
        "is_system": False,
        "column_count": len(mapping),
    }


def touch_import_mapping(mapping_id: Any) -> None:
    """BR-AST-048's most-recently-used clock, moved by the runner when a run
    starts from (or is recognised as) a template. A tenancy-owned write on a
    tenancy-owned column; silently ignores an id that no longer resolves —
    a recognition is not an event worth failing an extract over."""
    from django.utils import timezone as dj_timezone

    models.ImportMapping.objects.filter(tenant_id=_tenant_id(), pk=mapping_id).update(
        last_used_at=dj_timezone.now()
    )


# list_code → the handler for a list whose table tenancy hosts. Used both for
# registration (apps.py) and for the provisioning seed fallback below.
HOSTED_LOOKUP_HANDLERS: dict[str, Any] = {
    "reason_codes": ReasonCodeLookupHandler,
    "payment_methods": PaymentMethodLookupHandler,
    "areas": AreaLookupHandler,
    "service_size_classes": ServiceSizeClassLookupHandler,  # BR-TEN-170
    "occupancy_statuses": OccupancyStatusLookupHandler,
    "device_types": DeviceTypeLookupHandler,
    "certification_types": CertificationTypeLookupHandler,
    # CR-039 wave C task 12 (PO 2026-08-27: *"category is okay, no richer
    # text"*). Tenancy hosts; metering owns the content (BR-TEN-031/150).
    "owner_categories": PremisesOwnerCategoryLookupHandler,
    "import_mappings": ImportMappingLookupHandler,
}


@require_role(SYSTEM_ADMIN)
def create_lookup_entry(actor: Any, list_code: str, payload: Any) -> dict[str, Any]:
    handler = lookup_handler(list_code)
    if not isinstance(payload, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="settings.payload_not_object")
    with transaction.atomic():
        row = handler.create(payload)  # owning-module validation (BR-TEN-031)
        serialized = handler.serialize(row)
        _audit(
            actor,
            "settings.lookup.created",
            "lookup_entry",
            serialized["id"],
            after={"list": list_code, **serialized},
        )
    return serialized


@require_role(SYSTEM_ADMIN)
def update_lookup_entry(actor: Any, list_code: str, entry_id: Any, payload: Any) -> dict[str, Any]:
    handler = lookup_handler(list_code)
    if not isinstance(payload, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="settings.payload_not_object")
    with transaction.atomic():
        row = handler.get(entry_id)
        if row is None:
            raise errors.NotFoundError()
        before = handler.serialize(row)
        new_code = str(payload.get("code") or "").strip()
        if new_code and new_code.lower() != before["code"].lower() and before["used_by"] > 0:
            # BR-TEN-030: code immutable once used; name/detail stay editable.
            raise errors.BizError(
                errors.BIZ_IMMUTABLE,
                br_ref="BR-TEN-030",
                message_key="settings.lookups.code_locked",
                params={"used_by": before["used_by"]},
            )
        row = handler.update(row, payload)
        after = handler.serialize(row)
        _audit(
            actor,
            "settings.lookup.updated",
            "lookup_entry",
            after["id"],
            before={"list": list_code, **before},
            after={"list": list_code, **after},
        )
    return after


@require_role(SYSTEM_ADMIN)
def set_lookup_entry_active(
    actor: Any, list_code: str, entry_id: Any, active: bool
) -> dict[str, Any]:
    """Deactivate always allowed; reactivation allowed at any time (BR-TEN-029)."""
    handler = lookup_handler(list_code)
    with transaction.atomic():
        row = handler.get(entry_id)
        if row is None:
            raise errors.NotFoundError()
        before = handler.serialize(row)
        row = handler.set_active(row, active)
        after = handler.serialize(row)
        action = "settings.lookup.reactivated" if active else "settings.lookup.deactivated"
        _audit(
            actor,
            action,
            "lookup_entry",
            after["id"],
            before={"list": list_code, **before},
            after={"list": list_code, **after},
        )
    return after


@require_role(SYSTEM_ADMIN)
def delete_lookup_entry(actor: Any, list_code: str, entry_id: Any) -> None:
    """Hard removal ONLY at Used-by = 0, recomputed at commit time — the 🔒
    audit-lock is server-enforced (BR-TEN-034, US-TEN-011 TC-4/TC-5)."""
    handler = lookup_handler(list_code)
    with transaction.atomic():
        row = handler.get(entry_id)
        if row is None:
            raise errors.NotFoundError()
        used = handler.used_by(row)  # fresh count INSIDE the transaction
        if used > 0:
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-TEN-034",
                message_key="settings.lookups.locked_referenced",
                params={"used_by": used},
            )
        before = handler.serialize(row)
        handler.delete(row)
        _audit(
            actor,
            "settings.lookup.deleted",
            "lookup_entry",
            before["id"],
            before={"list": list_code, **before},
        )


# ── S8 Custom fields (EP-TEN-09 — US-TEN-014/015/016/017) ───────────────────
#
# FOUR WRITES AND NO FIFTH. Create · edit · placement · activate/deactivate.
# **There is no delete at any layer** (BR-TEN-050, CONFIRMED PO 2026-08-10 —
# *"Deactivate only"*): no service, no route, no ORM call. US-TEN-017 TC-3 asks
# for a 405/no-route and gets it by there being nothing to route to. Dropping a
# tenant-defined field would destroy data nobody can reconstruct, and the
# platform has no way to know what it was worth.
#
# Every one of the four bumps `tenant_settings.custom_field_version` inside the
# SAME transaction (BR-TEN-053), so the cached registry a hundred screens read
# is superseded by a new key the instant the write commits.
def _bump_custom_field_version(tenant_id: Any) -> None:
    """BR-TEN-053's invalidation, and the reason it is a bump not a delete:
    a delete fan-out has to enumerate eight entity keys and get every one right,
    and the failure mode of missing one is a screen rendering last quarter's
    field set with no error anywhere. A monotonic version cannot be partially
    applied."""
    models.TenantSettings.objects.filter(tenant_id=tenant_id).update(
        custom_field_version=F("custom_field_version") + 1
    )


def _custom_field_or_404(field_id: Any) -> models.CustomField:
    row = models.CustomField.objects.filter(tenant_id=_tenant_id(), pk=field_id).first()
    if row is None:
        # Cross-tenant and genuinely-absent are indistinguishable by law (HR-1).
        raise errors.NotFoundError()
    return row


@require_role(SYSTEM_ADMIN)
def create_custom_field(actor: Any, payload: Any) -> dict[str, Any]:
    """US-TEN-015 — define a field. Writes a ROW; never runs DDL (BR-TEN-046).

    The cap (BR-TEN-051, CONFIRMED — *"10 are okay"*) is counted INSIDE the
    transaction and the refusal names the cap and the count, because a
    truncation the operator cannot see is the failure this rule exists to
    prevent. It is per tenant per entity: Brazos Bend holding 10 Accounts fields
    does not stop Lone Star Ridge adding its first (US-TEN-015 TC-9), and does
    not stop Brazos Bend adding a Premises field (§6 acceptance).
    """
    tenant_id = _tenant_id()
    changes = custom_fields.validate_definition(payload)
    entity = changes["entity"]
    with transaction.atomic():
        active = models.CustomField.objects.filter(
            tenant_id=tenant_id, entity=entity, is_active=True
        ).count()
        if active >= custom_fields.ACTIVE_CAP_PER_ENTITY:
            # US-TEN-015 TC-5: 422 BIZ-CAP, params {entity, active, cap}, and
            # NOTHING is written — the audit trail records no create.
            raise errors.BizError(
                errors.BIZ_CAP,
                br_ref="BR-TEN-051",
                message_key="settings.customFields.cap_reached",
                params={
                    "entity": entity,
                    "active": active,
                    "cap": custom_fields.ACTIVE_CAP_PER_ENTITY,
                },
            )
        if models.CustomField.objects.filter(
            tenant_id=tenant_id, entity=entity, key=changes["key"]
        ).exists():
            # US-TEN-015 TC-6. UNIQUE (tenant, entity, key) holds in the
            # database too; this is the readable half of the same law.
            _refuse_fields(
                [
                    _field_error(
                        "key",
                        errors.VAL_FORMAT,
                        "settings.customFields.duplicate_key",
                        key=changes["key"],
                    )
                ]
            )
        row = models.CustomField.objects.create(tenant_id=tenant_id, **changes)
        _bump_custom_field_version(tenant_id)
        after = selectors._custom_field_dict(row)
        _audit(actor, "custom_field.created", "custom_field", after["id"], after=after)
    return after


@require_role(SYSTEM_ADMIN)
def update_custom_field(actor: Any, field_id: Any, payload: Any) -> dict[str, Any]:
    """US-TEN-015 TC-3/TC-4 — the LABEL is editable; the KEY never is.

    BR-TEN-049: a stamped invoice snapshot and a pinned template version both
    reference the key forever, so a rename would silently break documents that
    have already been issued — hard rule 4 defeated without a single UPDATE on
    an invoice. `validate_definition` refuses `key` and `entity` by name; the
    row is UPDATED in place rather than recreated, so the field keeps its id and
    its stored values (TC-3: "the field is not recreated").
    """
    tenant_id = _tenant_id()
    with transaction.atomic():
        row = _custom_field_or_404(field_id)
        before = selectors._custom_field_dict(row)
        changes = custom_fields.validate_definition(payload, existing=row)
        for field, value in changes.items():
            setattr(row, field, value)
        row.save(update_fields=[*changes, "updated_at"] if changes else ["updated_at"])
        _bump_custom_field_version(tenant_id)
        after = selectors._custom_field_dict(row)
        _audit(
            actor, "custom_field.updated", "custom_field", after["id"], before=before, after=after
        )
    return after


@require_role(SYSTEM_ADMIN)
def save_custom_field_placement(actor: Any, field_id: Any, placement: Any) -> dict[str, Any]:
    """US-TEN-016 — where the field appears, and in which mode.

    THIS IS THE NO-CODE SURFACE: after this write the field renders on those
    screens with no deploy between defining it and seeing it. What keeps that
    safe is that the tenant chooses among slots the PLATFORM cleared
    (BR-TEN-052) — S31 Run Bills and the S12/S13 money screens are not in the
    allow-list at all, so a placement naming one is a 422 rather than a field on
    a bill run.

    `not_shown` is stored by OMISSION, which is what makes TC-3 true: the field
    disappears from that screen and **the stored values are untouched**, so
    placing it again brings every value back.
    """
    tenant_id = _tenant_id()
    with transaction.atomic():
        row = _custom_field_or_404(field_id)
        before = selectors._custom_field_dict(row)
        row.placement = custom_fields.validate_placement(
            row.entity, placement, existing=dict(row.placement or {})
        )
        row.save(update_fields=["placement", "updated_at"])
        _bump_custom_field_version(tenant_id)
        after = selectors._custom_field_dict(row)
        _audit(
            actor,
            "custom_field.placement_changed",
            "custom_field",
            after["id"],
            before=before,
            after=after,
        )
    return after


@require_role(SYSTEM_ADMIN)
def set_custom_field_active(actor: Any, field_id: Any, active: bool) -> dict[str, Any]:
    """US-TEN-017 — deactivate and reactivate. THE ONLY LIFECYCLE THAT EXISTS.

    Deactivating hides the field from every placement and excludes it from new
    invoice snapshots (`selectors.document_safe_custom_fields` filters
    `is_active`); the values stay in the owning rows and reappear verbatim on
    reactivation (TC-1/TC-2). It also frees cap headroom (TC-4).

    OQ-075 is CLOSED — **warn, do not block** (PO 2026-08-10). The deactivation
    proceeds unconditionally and the response carries the warning; see
    `custom_fields.template_reference_warning` for why the affected-template
    list is empty by construction in R2 and what has to change when US-NOT-016
    lands. The story text still asks for a stub of that question by name and is
    STALE — the registry is the live record and G8 fails a stub citing a closed
    question, so the ruling is implemented instead. REPORTED.
    """
    tenant_id = _tenant_id()
    with transaction.atomic():
        row = _custom_field_or_404(field_id)
        before = selectors._custom_field_dict(row)
        warning = custom_fields.template_reference_warning(row.key) if not active else None
        row.is_active = bool(active)
        row.save(update_fields=["is_active", "updated_at"])
        _bump_custom_field_version(tenant_id)
        after = selectors._custom_field_dict(row)
        _audit(
            actor,
            "custom_field.reactivated" if active else "custom_field.deactivated",
            "custom_field",
            after["id"],
            before=before,
            after=after,
        )
    if warning is not None:
        after = {**after, "template_warning": warning}
    return after


def validate_custom_data_for(
    entity: str,
    submitted: Any,
    *,
    require_input: bool = True,
    screen: str | None = None,
    existing: Any = None,
) -> dict:
    """PUBLISHED FOR THE OWNING MODULES (US-SHL-015) — the value half.

    A module that accepts `custom_data` on a write calls this ONE function
    before it persists: unknown keys are rejected, options are enforced, types
    are checked and required fields block save on INPUT placements only. It is
    published here rather than copied into four modules for the reason
    EP-SHL-07 gives for its component — eight entities and nine screens before a
    line is written, and four diverging copies otherwise.

    It is a READ plus pure validation and writes nothing, so it is safe for a
    caller to run inside its own transaction.

    ⚠ **`screen` IS THE DOOR'S FORM, AND A DOOR MUST NAME IT (`DEF-TEN-9157`,
    `CR-161-BRC10`).** Required binds only to fields placed Input on that
    screen; `None` is a door that is not a screen (an import), of which nothing
    is required. `existing` makes this an EDIT and returns the merged blob — see
    `custom_fields.validate_custom_data`.
    """
    definitions = selectors.custom_field_registry(entity)
    return custom_fields.validate_custom_data(
        definitions,
        submitted,
        require_input=require_input,
        screen=screen,
        existing=existing,
    )


# ── S8 Numbering (US-TEN-012 · BR-TEN-035) + the BE-06 allocator sink ───────
@require_role(SYSTEM_ADMIN)
def save_number_series(
    actor: Any,
    series: str,
    *,
    format_string: str | None = None,
    next_number: int | None = None,
    restart_period: str | None = None,
) -> dict[str, Any]:
    """Format changes apply to FUTURE numbers only — issued numbers are never
    renumbered (BR-TEN-035; there is deliberately no renumber API anywhere).
    Next-number edits are forward-only (≥ current)."""
    with transaction.atomic():
        row = _apply_series_edit(
            series,
            format_string=format_string,
            next_number=next_number,
            restart_period=restart_period,
        )
        if row is not None:
            _audit(
                actor,
                "settings.numbering.updated",
                "number_series",
                row["id"],
                before=row["before"],
                after=row["after"],
            )
    return selectors.number_series_row(series)


@require_role(SYSTEM_ADMIN)
def save_number_series_bulk(actor: Any, rows: Any) -> list[dict[str, Any]]:
    """CR-005 Save: *"persists all rows in one transaction, toast + audit log
    entry (who, when, old → new format per entity)"*.

    ONE transaction and ONE audit row, and both halves of that matter. The
    transaction is what makes a screen-wide Save honest — a table where row 9
    fails validation must not leave rows 1–8 saved, because the admin who
    changed nine formats together believes they took effect together, and the
    next number issued would prove them half right. The single audit row is what
    the CR asks for in its own words: the before/after map is keyed BY ENTITY,
    so one line of the audit trail answers *"what did numbering look like before
    this person touched it"* — which is the question asked after a number turns
    up looking wrong, and it cannot be answered by nine rows that have to be
    found first.

    Refusals are the per-series ones, unchanged: a malformed format (VAL-002
    naming the problem), a backward counter (VAL-004 naming the minimum), an
    unusable restart. The FIRST refusal aborts the whole save.
    """
    if not isinstance(rows, list):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="settings.numbering.bulk_payload_invalid"
        )
    before_map: dict[str, Any] = {}
    after_map: dict[str, Any] = {}
    with transaction.atomic():
        for entry in rows:
            if not isinstance(entry, dict) or not entry.get("series"):
                raise errors.ValidationError(
                    errors.VAL_FORMAT, message_key="settings.numbering.bulk_payload_invalid"
                )
            series = str(entry["series"])
            changed = _apply_series_edit(
                series,
                format_string=entry.get("format"),
                next_number=entry.get("next_number"),
                restart_period=entry.get("restart_period"),
            )
            if changed is not None:
                before_map[series] = changed["before"]
                after_map[series] = changed["after"]
        if before_map:
            # entity_id is None: this row is ABOUT the whole tab, not about one
            # series row, and pointing it at an arbitrary one of the nine would
            # be a worse lie than pointing it at nothing.
            _audit(
                actor,
                "settings.numbering.bulk_updated",
                "number_series",
                None,
                before=before_map,
                after=after_map,
            )
    return selectors.number_series_overview()


def _apply_series_edit(
    series: str,
    *,
    format_string: Any = None,
    next_number: Any = None,
    restart_period: Any = None,
) -> dict[str, Any] | None:
    """One series row, locked, validated and written — the shared body of the
    per-row save and the whole-tab save. Returns the before/after pair when
    something actually changed, else None (an unchanged row writes no audit row:
    a Save over nine untouched rows is not nine edits).

    CALL INSIDE A TRANSACTION. It takes a `SELECT … FOR UPDATE` and leaves the
    audit write to its caller, because the whole-tab save owes ONE audit row
    across every series and cannot have this function writing nine.
    """
    row = (
        models.NumberSeries.objects.select_for_update()
        .filter(tenant_id=_tenant_id(), series=series)
        .first()
    )
    if row is None:
        raise errors.NotFoundError()
    before = {
        "format": row.format,
        "next_number": row.next_number,
        "restart_period": row.restart_period,
    }
    fields: list[str] = []
    if format_string is not None and format_string != row.format:
        core_numbering.validate_format(format_string)  # US-TEN-012 TC-4
        row.format = format_string
        fields.append("format")
    if next_number is not None:
        try:
            proposed = int(next_number)
        except (TypeError, ValueError) as exc:
            raise errors.ValidationError(
                errors.VAL_FORMAT, message_key="settings.numbering.next_number_not_int"
            ) from exc
        core_numbering.ensure_forward_only(row.next_number, proposed)  # TC-5
        if proposed != row.next_number:
            row.next_number = proposed
            fields.append("next_number")
    if restart_period is not None and str(restart_period) != row.restart_period:
        row.restart_period = str(restart_period)
        fields.append("restart_period")
        # The counter's POSITION is only meaningful under the policy that was in
        # force when it was recorded. Switching policy therefore clears it, and
        # the next allocation writes the period it actually issues into — rather
        # than comparing "2026-08" against a series that now restarts yearly and
        # concluding, wrongly, that the year has rolled.
        row.period_counted = ""
        fields.append("period_counted")
    # ALWAYS validated together, even when only ONE of the two moved: a legal
    # format and a legal restart can be an illegal PAIR (yearly restart on
    # `AC-{00000}` re-mints AC-00001 every January — OQ-252), and whichever half
    # arrives second is the one that makes it true.
    if fields:
        core_numbering.validate_restart_period(row.format, row.restart_period)
        row.save(update_fields=[*fields, "updated_at"])
        return {
            "id": row.id,
            "before": before,
            "after": {
                "format": row.format,
                "next_number": row.next_number,
                "restart_period": row.restart_period,
            },
        }
    return None


def advance_number_series_to(actor: Any, series: str, minimum_next: int) -> int:
    """🔒 HUMAN-REVIEW-PENDING (numbering, DEF-577 — row in 12-governance/09-human-review-ledger.md).

    Move a series' counter FORWARD so it stands clear of numbers that already
    exist. Called by the modules that write their own numbers — the CR-023
    import (which writes the CUSTOMER'S numbers straight from their CSV) and
    the premises/unit creators when they find the counter standing behind the
    table.

    **This is the S63 act an admin performs by hand today**, and DEF-577 records
    exactly that workaround: on the demo database the `unit` series stood at
    **102** while units up to **U-00420** were already on file, so an operator
    had to open Settings → Numbering and type a bigger number before "Add unit"
    would work at all. Doing it in code changes nothing about the rule — it
    removes the requirement that a human notice.

    **FORWARD ONLY, and never past what was asked for.** BR-TEN-035: a number is
    never reused and next-number edits are forward-only, so a request that would
    move the counter BACKWARD is not honoured (and `ensure_forward_only` is
    called on the path that would move it, so the law refuses out loud rather
    than being re-implemented here). Gaps are explicitly fine — skipping from
    102 to 421 issues no number and loses none.

    Returns the counter's position afterwards. Call inside the caller's
    transaction: the row is locked for the same reason `allocate_series_number`
    locks it.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        # BR-TEN-003 — a counter is per tenant, so no context means no answer.
        raise core_numbering.NumberingError(f"no tenant context for series {series!r} catch-up")
    row = (
        models.NumberSeries.objects.select_for_update()
        .filter(tenant_id=tenant_id, series=series)
        .first()
    )
    if row is None:
        # Seeding the per-tenant series rows is provisioning's job
        # (US-TEN-012 / BE-06); this refuses rather than creating one.
        raise core_numbering.NumberingError(f"no {series!r} number series row for this tenant")
    if row.next_number >= minimum_next:
        # Already clear. Silence is correct: nothing moved, so nothing is
        # audited and no reader is told about a change that did not happen.
        return row.next_number
    core_numbering.ensure_forward_only(row.next_number, minimum_next)
    before = row.next_number
    row.next_number = minimum_next
    row.save(update_fields=["next_number", "updated_at"])
    _audit(
        actor,
        "settings.numbering.caught_up",
        "number_series",
        row.id,
        before={"series": series, "next_number": before},
        after={"series": series, "next_number": minimum_next},
    )
    logger.warning(
        "number series %r caught up %s -> %s: the counter stood behind numbers "
        "already in its own table (DEF-577)",
        series,
        before,
        minimum_next,
    )
    return minimum_next


def allocate_series_number(series: str, issue_date: date) -> tuple[str, int]:
    """The BE-06 series sink (registered in AppConfig.ready — apps.py):
    SELECT … FOR UPDATE the tenant's series row INSIDE the caller's issuing
    transaction, return (format, sequence), advance the counter by one.
    Gaps from rolled-back transactions are fine; a number is never reused
    (BR-TEN-035). Tenant comes from app.tenant_id context — never a parameter.

    CR-005 adds the PERIOD RESTART, and it happens here rather than on the
    settings screen for one reason: the restart is an event at ISSUE time, not
    at save time. A series that restarts every January restarts on the day
    January's first bill is written, whoever writes it and whether or not an
    admin has visited Settings that year.

    ⚠ **A BACKDATED NUMBER UNDER A RESTART POLICY IS REFUSED BY NAME, NOT
    MINTED** (OQ-252). BR-TEN-043 lets a caller number under a past date; a
    monthly-restarting series that issued `BL-2607-000050` in July and stands at
    12 in August would hand a July-dated bill `BL-2607-000012` — a number July
    already used, on a row hard rule 4 forbids anyone to correct. The counter
    therefore only ever rolls FORWARD into a later period, and a backward one
    aborts the issuing transaction with `numbering_restart_backdated` so a human
    decides. A utility that backdates across period boundaries turns restart off
    for that series; nothing else is safe and nothing here guesses.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise core_numbering.NumberingError(
            f"no tenant context for series {series!r} allocation (BR-TEN-003)"
        )
    row = (
        models.NumberSeries.objects.select_for_update()
        .filter(tenant_id=tenant_id, series=series)
        .first()
    )
    if row is None:
        raise core_numbering.NumberingError(
            f"no {series!r} number series row for this tenant — provisioning "
            f"seeds series rows (US-TEN-012/BE-06)"
        )
    fields = ["next_number", "updated_at"]
    if row.restart_period != core_numbering.RESTART_NEVER:
        key = core_numbering.period_key(row.restart_period, issue_date)
        if row.period_counted and key < row.period_counted:
            raise core_numbering.NumberingError(
                f"numbering_restart_backdated: {series!r} restarts {row.restart_period} and is "
                f"counting in {row.period_counted!r}; an issuance dated {issue_date.isoformat()} "
                f"falls in {key!r} and would re-mint a number that period already used "
                f"(BR-TEN-035 / OQ-252)"
            )
        if not row.period_counted:
            # FIRST allocation since the policy was chosen: ADOPT the period,
            # do NOT reset. An admin who sets the counter to 18,411 and switches
            # restart on has said what the next bill number is; resetting here
            # would throw that away on the very next bill and hand out numbers
            # the old series already used. The restart begins at the NEXT
            # boundary, which is what "restart each year" means.
            row.period_counted = key
            fields.append("period_counted")
        elif key != row.period_counted:
            row.next_number = 1  # the new period starts at one (CR-005)
            row.period_counted = key
            fields.append("period_counted")
    sequence = row.next_number
    row.next_number = sequence + 1
    row.save(update_fields=fields)
    return row.format, sequence


# ── S63 Holiday calendar (BR-TEN-039; r5 #3 — W0 table, endpoints per 11b §2.3) ──
@require_role(SYSTEM_ADMIN)
def create_holiday(actor: Any, payload: Any) -> dict[str, Any]:
    holiday_date, label = _validate_holiday(payload, partial=False)
    with transaction.atomic():
        if models.HolidayCalendar.objects.filter(
            tenant_id=_tenant_id(), holiday_date=holiday_date
        ).exists():
            _refuse_fields(
                [
                    _field_error(
                        "holiday_date", errors.VAL_FORMAT, "settings.holidays.duplicate_date"
                    )
                ]
            )
        row = models.HolidayCalendar.objects.create(
            tenant_id=_tenant_id(), holiday_date=holiday_date, label=label
        )
        _audit(
            actor,
            "settings.holiday.created",
            "holiday_calendar",
            row.id,
            after={"date": holiday_date.isoformat(), "label": label},
        )
    return {"id": str(row.id), "date": holiday_date.isoformat(), "label": label}


@require_role(SYSTEM_ADMIN)
def update_holiday(actor: Any, holiday_id: Any, payload: Any) -> dict[str, Any]:
    holiday_date, label = _validate_holiday(payload, partial=True)
    with transaction.atomic():
        row = models.HolidayCalendar.objects.filter(tenant_id=_tenant_id(), pk=holiday_id).first()
        if row is None:
            raise errors.NotFoundError()
        before = {"date": row.holiday_date.isoformat(), "label": row.label}
        if holiday_date is not None and holiday_date != row.holiday_date:
            if (
                models.HolidayCalendar.objects.filter(
                    tenant_id=_tenant_id(), holiday_date=holiday_date
                )
                .exclude(pk=row.pk)
                .exists()
            ):
                _refuse_fields(
                    [
                        _field_error(
                            "holiday_date", errors.VAL_FORMAT, "settings.holidays.duplicate_date"
                        )
                    ]
                )
            row.holiday_date = holiday_date
        if label is not None:
            row.label = label
        row.save(update_fields=["holiday_date", "label", "updated_at"])
        after = {"date": row.holiday_date.isoformat(), "label": row.label}
        _audit(
            actor,
            "settings.holiday.updated",
            "holiday_calendar",
            row.id,
            before=before,
            after=after,
        )
    return {"id": str(row.id), **after}


@require_role(SYSTEM_ADMIN)
def delete_holiday(actor: Any, holiday_id: Any) -> None:
    with transaction.atomic():
        row = models.HolidayCalendar.objects.filter(tenant_id=_tenant_id(), pk=holiday_id).first()
        if row is None:
            raise errors.NotFoundError()
        before = {"date": row.holiday_date.isoformat(), "label": row.label}
        row.delete()
        _audit(actor, "settings.holiday.deleted", "holiday_calendar", holiday_id, before=before)


def _validate_holiday(payload: Any, *, partial: bool) -> tuple[date | None, str | None]:
    if not isinstance(payload, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="settings.payload_not_object")
    fe: list[dict[str, Any]] = []
    holiday_date: date | None = None
    label: str | None = None
    raw_date = payload.get("date")
    if raw_date is None:
        if not partial:
            fe.append(_field_error("date", errors.VAL_REQUIRED, "settings.holidays.date_required"))
    else:
        try:
            holiday_date = date.fromisoformat(str(raw_date))
        except ValueError:
            fe.append(_field_error("date", errors.VAL_FORMAT, "settings.holidays.bad_date"))
    raw_label = payload.get("label")
    if raw_label is None:
        if not partial:
            fe.append(
                _field_error("label", errors.VAL_REQUIRED, "settings.holidays.label_required")
            )
    else:
        label = str(raw_label).strip()
        if not label:
            fe.append(
                _field_error("label", errors.VAL_REQUIRED, "settings.holidays.label_required")
            )
        elif len(label) > 80:
            fe.append(
                _field_error("label", errors.VAL_RANGE, "settings.holidays.label_too_long", max=80)
            )
    _refuse_fields(fe)
    return holiday_date, label


# ── BE-07 job store + transport (core/jobs.py contract; table hosted here) ──
# The kernel keeps no models: it persists through a registered store with three
# duck-typed methods, exactly as core.audit persists through a registered sink.
# tenancy hosts the `jobs` table (models.Job docstring records that disposition),
# so the adapter lives here and apps.py registers it at startup.

JOB_ACTIVE_STATUSES = sorted(core_jobs.ACTIVE_STATUSES)  # ('queued', 'running')


def _job_uuid(job_id: Any) -> UUID | None:
    """Job ids arrive as strings (the kernel mints them); anything that is not
    a uuid is simply absent — the caller answers 404, never a 500."""
    if isinstance(job_id, UUID):
        return job_id
    try:
        return UUID(str(job_id))
    except (AttributeError, TypeError, ValueError):
        return None


def job_record(job: models.Job) -> dict[str, Any]:
    """One `jobs` row as the BE-07 record dict (column-per-key, no extras)."""
    return {
        "id": str(job.id),
        "tenant_id": job.tenant_id,
        "kind": job.kind,
        "status": job.status,
        "progress": job.progress or models.job_progress_default(),
        "checkpoint": job.checkpoint,
        "result_link": job.result_link,
        "error": job.error,
        "scope_key": job.scope_key,
        "payload": job.payload or {},
    }


class JobStore:
    """The BE-07 store: save (upsert by id) · get · find_active.

    Tenant scoping: every method runs under the caller's app.tenant_id (RLS
    FORCE on `jobs`, B2 §3), which is why `get` carries no tenant filter — the
    kernel's own state transitions load a record by id alone, and RLS is what
    keeps that honest. The POLL endpoint does not use this class; it reads
    through selectors.job_poll(), which filters by tenant explicitly so the
    sqlite tier obeys the same law the G5 suite proves on Postgres.
    """

    def save(self, record: dict[str, Any]) -> None:
        models.Job.objects.update_or_create(
            id=_job_uuid(record["id"]),
            defaults={
                "tenant_id": record["tenant_id"],
                "kind": record["kind"],
                "status": record["status"],
                "progress": record["progress"],
                "checkpoint": record["checkpoint"],
                "result_link": record["result_link"],
                "error": record["error"],
                "scope_key": record["scope_key"],
                "payload": record["payload"],
            },
        )

    def get(self, job_id: Any) -> dict[str, Any] | None:
        target = _job_uuid(job_id)
        if target is None:
            return None
        job = models.Job.objects.filter(id=target).first()
        return job_record(job) if job is not None else None

    def seconds_idle(self, job_id: Any) -> float | None:
        """Seconds since this record was last written (`updated_at` moves on
        every save, and a running job saves as it records progress) — the
        heartbeat `core.jobs.redispatch` reads to tell a dead worker's job from
        a live one (DEF-BIL-8511). None when the row is not visible."""
        target = _job_uuid(job_id)
        if target is None:
            return None
        touched = models.Job.objects.filter(id=target).values_list("updated_at", flat=True).first()
        if touched is None:
            return None
        return max((timezone.now() - touched).total_seconds(), 0.0)

    def list_active(self, tenant_id: Any, kind: str) -> list[dict[str, Any]]:
        """Every queued or running job of `kind` for this tenant, oldest first —
        `core.jobs.active_records` (B28's per-utility cap on Check batches)."""
        return [
            job_record(job)
            for job in models.Job.objects.filter(
                tenant_id=tenant_id, kind=kind, status__in=JOB_ACTIVE_STATUSES
            ).order_by("created_at", "id")
        ]

    def find_active(self, tenant_id: Any, kind: str, scope_key: str) -> dict[str, Any] | None:
        """NFR-16 fold-in: the still-running job for this scope, or None. The
        partial unique index on (tenant, kind, scope_key) WHERE status active
        (models.Job) is the same law at the DB level, against races."""
        job = (
            models.Job.objects.filter(
                tenant_id=tenant_id,
                kind=kind,
                scope_key=scope_key,
                status__in=JOB_ACTIVE_STATUSES,
            )
            .order_by("created_at")
            .first()
        )
        return job_record(job) if job is not None else None


# ⚠ `record_job_artifact` — which wrote the artifact's DISK PATH onto the job's
# payload — is gone (PO 2026-10-02, exports move to S3, `DEF-MET-4954`). A
# finished export is recorded as a `job_artifacts` row by
# `apps/tenancy/export_store.publish`, called from `exports.finish_artifact`.


# ── US-SHL-008 — the generic table-level export (11b §2.11) ─────────────────
def request_list_export(
    *,
    actor: Any,
    resource_name: Any,
    q: str = "",
    sort: Any = None,
    direction: Any = None,
    filters: dict[str, str] | None = None,
    columns: Any = None,
) -> dict[str, Any]:
    """Accept one list export. **It is never refused for being large.**

    Order matters: resolve the resource (an unregistered one does NOT exist on
    this deployment — 404, never a guessed queryset), enqueue, then write the
    audit row for a money-bearing list.

    ════════════════════════════════════════════════════════════════════════
    THE CAP AND THE PRE-COUNT ARE BOTH DELETED — `P2.4` (`CR-142-BRC07`)
    ════════════════════════════════════════════════════════════════════════
    Until this commit the first thing this function did was
    `exports.selection_count(resource.select(params))`, and then it raised
    `BIZ-CAP` above `exports.EXPORT_ROW_CAP = 100_000`. **`NFR-5` forbids a
    hard cap anywhere**, and the number was already short of the product's own
    customers: Killeen at **57,066 accounts × 14 cycles is ~685,000 rows a
    year**, so a clerk asking for their own year of bills was told to narrow
    their filters.

    **This is a DELETION and not a rewrite, because the writer already
    streams.** `exports.write_csv` pulls from `row_stream`, which pulls from
    `selection_iter`, which is `.iterator(chunk_size=CHUNK)` — the file is
    written row by row and was never held in memory. The cap was guarding
    nothing the writer could not do.

    **THE PRE-COUNT GOES WITH IT, AND THAT IS THE HALF THAT COST TIME.**
    `selection_count` is a SQL `COUNT` for a QuerySet and falls through to
    `len()` on a Python list for the derived-filter selections — units, assets,
    routes, cycles and the four rating lists — which **builds the whole report,
    throws it away, and builds it again to write it.** The count existed to
    feed the cap and to seed the job's progress total; the cap is gone and
    `record_progress` already takes `total=None` (the progress bar counts up
    without a denominator, which is what a stream honestly has).

    ⚠ **NOTHING MAY REINSTATE IT, INCLUDING ON A SETTINGS SCREEN.** A tenant
    -configurable ceiling is still a ceiling.

    RBAC disposition, recorded rather than silently chosen: **A4 has no
    per-list "export" cell.** All nine list GETs are AnyTenantRole, and this
    endpoint grants no data the caller cannot already read — the same rows, the
    same RLS, a different container. So the gate is the LIST's own gate, and
    the narrowing question (should exporting need more than reading?) is
    flagged for the PO batch. The audit export took the same route from
    BR-AUD-009 for the same reason.

    Returns the BE-07 202 body: {job_id, status_url}.
    """
    resource = exports.export_resource(resource_name)
    if resource is None:
        # HR-1 / 11b G4: an unknown resource is ABSENT, not a hint.
        raise errors.NotFoundError()

    params = exports.params_from_payload(
        resource,
        {"q": q, "sort": sort, "dir": direction, "filters": filters or {}},
    )
    # P4.13 — the caller's ticked columns, RESOLVED HERE against the resource
    # so the payload holds names this list actually has. Resolving at accept
    # time rather than at run time means the audit row below records what the
    # file will carry, not what the client asked for; BR-SHL-011's fall-back
    # lives in `columns_for` and is applied once.
    # ⚠ **THE RESOURCE'S OWN PARAMETER CHECK, BEFORE THE JOB EXISTS
    # (DEF-TEN-9160).** The pre-count deleted above was, without saying so,
    # also the only thing that ran a selector's refusals at accept time; from
    # 2.357.0 a finance export with a malformed date was answered 202 and then
    # failed in the job. `validate` reads no rows, so the cost P2.4 removed
    # stays removed.
    if resource.validate is not None:
        resource.validate(params)
    chosen = exports.columns_for(resource, columns)
    column_names = [column.name for column in chosen]
    record = core_jobs.enqueue(
        exports.LIST_EXPORT_JOB,
        payload={
            "resource": resource.name,
            "q": params.q,
            "sort": params.sort,
            "dir": params.dir,
            "filters": dict(params.filters),
            "columns": column_names,
            "actor_user_id": str(getattr(actor, "id", None) or getattr(actor, "pk", "")) or None,
        },
    )
    if resource.money:
        # BR-SHL-016: money-table exports write `audit_log` — who, which list,
        # the filter state, the row count. A non-money list writes none, and
        # that silence is the rule's, not an omission.
        core_audit.money_action(
            actor,
            "list.exported",
            resource.name,
            None,  # an export covers a FILTERED SET, not one row
            after={
                "resource": resource.name,
                "q": params.q,
                "sort": params.sort,
                "dir": params.dir,
                "filters": dict(params.filters),
                # P4.13 — WHICH columns left the building. A money export whose
                # audit row named the filters but not the columns cannot answer
                # *what did we hand over*, which is the question the row is for.
                "columns": column_names,
                # ⚠ **NO `row_count`, AND ITS ABSENCE IS THE POINT (`P2.4`).**
                # The audit row is written at ACCEPT time, and at accept time
                # nothing has counted the selection — counting it was the
                # second build of the whole report. The number the row used to
                # carry is on the finished JOB, measured from what was actually
                # written rather than predicted before the file existed.
                "job_id": record["id"],
            },
        )
    return core_jobs.accepted(record)


def dispatch_job(record: dict[str, Any]) -> None:
    """The BE-07 transport, registered alongside the store (apps.py).

    Two paths, and the setting is read HERE at dispatch time so it is one grep
    away and overridable per test:

    * **JOBS_EAGER on** (local, dev, demo, and the test settings when a test
      turns it on): run the job in-process right now, so a 202 actually
      finishes on a box with no broker.
    * **JOBS_EAGER off** (production): hand the record to **Celery**, which is
      the PO's ruling of 2026-08-19 — *"We want Async job install redis and
      celery; Trigger after tenant creation"*.

    ⚠ **THE SECOND BRANCH USED TO DO NOTHING, AND THAT WAS DEF-320.** The
    comment here read *"do nothing — the record rests `queued` until a Celery
    worker calls core.jobs.run_pending(job_id)"*, and no Celery worker existed:
    `docker-compose.yml` said so in its own header. So on the deployed build
    every 202 was a promise nothing kept — four kinds of them. The sample-data
    plant meant every new tenant opened empty and silently; **the bulk rate
    change (DEF-326) meant staff changed prices, the product agreed, and the
    prices did not change.** A comment describing a worker is not a worker
    (hard-won law 1), and nothing in this repo read that comment.

    ⚠ **`apps.tenancy.tasks` is imported INSIDE the branch, not at module
    scope.** Importing it binds `config.celery`, which builds a Celery app; the
    web process on an eager deployment has no use for one and no broker to
    point it at, and an import error there would take down provisioning rather
    than one job. On the branch that actually needs a broker, an import failure
    is a real failure and is logged as one — with the record left `queued`,
    which is the honest state and is what a repair run reads.
    """
    if getattr(settings, "JOBS_EAGER", False):
        core_jobs.run_eager(record)
        return
    try:
        from apps.tenancy import tasks as tenancy_tasks
    except Exception:  # noqa: BLE001 — a queued record beats a 500 over saved work
        logger.exception(
            "BE-07: no Celery transport importable, so job %s (%s) stays QUEUED. "
            "Nothing is lost — the record is the truth (B12 r1) — but nothing "
            "will run it until a worker exists (DEF-320)",
            record.get("id"),
            record.get("kind"),
        )
        return
    tenancy_tasks.send(record)


#: How long a worker gets to answer the ping, in seconds. Short on purpose: this
#: runs inside the request that is about to promise a person something, and a
#: worker that cannot answer in a second is not one this import should be handed
#: to. A miss costs a refusal the person can act on; a long wait costs the
#: request it is trying to protect.
WORKER_PING_TIMEOUT_SECONDS = 1.0

#: How long a `ready` answer is trusted before asking again, in seconds. The
#: probe is asked once per deferred stage, not per row, so this is only about a
#: person clicking Commit twice — but a broker round-trip per click is still a
#: round-trip, and a worker does not vanish between two clicks. A NEGATIVE answer
#: is never cached: the fix for "no worker" is to start one, and the very next
#: thing that person does is try again.
WORKER_PING_CACHE_SECONDS = 5.0

#: queue name (or None, the broadcast question) → (when, the reason string).
#: ⚠ **KEYED BY QUEUE ON PURPOSE (CR-051 task 29).** A single shared entry would
#: let "the `celery` worker answered" stand in as the answer for the `billing`
#: queue for the next five seconds — the exact confusion the queue argument
#: exists to end, with a delay attached.
_worker_ping_cache: dict[str | None, tuple[float, str]] = {}


def job_dispatch_ready(queue: str | None = None) -> tuple[bool, str]:
    """Will a job enqueued right now actually be RUN? Registered as
    `core.jobs.set_dispatch_probe` (apps.py).

    ⚠ **`queue` ARRIVED WITH THE SECOND QUEUE, AND WITHOUT IT THIS FUNCTION
    WOULD NOW LIE (CR-051 task 29, PO ruling 2026-08-31).** `control.ping` is a
    BROADCAST: every worker on the broker answers it, whatever queues it
    consumes. That was a complete answer while this product had one queue. It
    stopped being one the moment billing got its own: the `celery` worker
    answers the ping happily while the `billing` queue has NO consumer —
    `celery-billing` stopped, or a compose file that lost its `-Q billing` — and
    a caller told *ready* on that evidence enqueues a bill run that rests
    `queued` for ever. That is exactly DEF-320, recreated by the change meant to
    prevent a different harm.

    So when a queue is NAMED, the question becomes *"is anybody consuming THAT
    queue"* and is asked with `inspect.active_queues()`, which reports each live
    worker's queue list. With no queue named the old broadcast question stands,
    because that IS the right question for a kind on the default queue.

    ⚠ **AND THE CACHE IS PER QUEUE.** One shared "a worker answered" cache would
    let a live `celery` worker's answer stand in for the billing queue for five
    seconds — the same lie, with a delay.

    ⛔ **THE FAILURE THIS PREVENTS IS A SILENT ONE.** `dispatch_job` above hands
    the record to Celery and `tasks.send` swallows a broker failure by design —
    *"the record stays queued and is picked up by the next worker that sees
    it"*. That is correct for work already recorded, and it means a deployment
    with no worker running accepts an import, shows the operator *queued*, and
    never writes a single account. DEF-2487 moved the accounts commit onto that
    path; without this probe the fix would have replaced a visible 500 with
    nothing at all.

    Three answers, and only the middle one costs anything:

    * **eager dispatch** — the body runs inside `enqueue`, so there is nothing
      to be ready. Answered without touching the network.
    * **broker dispatch** — ASK THE WORKERS. `app.control.ping` is a broadcast
      with a reply queue: an empty list means no process answered, which is
      exactly the question. Nothing else available to a web process can
      distinguish *"the broker is up and nobody is consuming"* from *"a worker
      is there"* — and that first state is the one that lost the accounts.
    * **anything raised** — treated as NOT ready by `core.jobs.dispatch_is_ready`
      (law 3: defaults fail closed).
    """
    if getattr(settings, "JOBS_EAGER", False):
        return True, "eager dispatch — the body runs in this process"
    if not getattr(settings, "JOBS_REQUIRE_LIVE_WORKER", True):
        return True, "JOBS_REQUIRE_LIVE_WORKER is off — the caller is its own worker"
    now = time.monotonic()
    cached = _worker_ping_cache.get(queue)
    if cached is not None and now - cached[0] < WORKER_PING_CACHE_SECONDS:
        return True, cached[1]
    from config.celery import app as celery_app

    if queue is None:
        replies = celery_app.control.ping(timeout=WORKER_PING_TIMEOUT_SECONDS) or []
        if not replies:
            return False, "no Celery worker answered the ping"
        names = ", ".join(sorted(name for reply in replies for name in reply))
        reason = f"{len(replies)} Celery worker(s) answered: {names}"
    else:
        # `active_queues()` and not `ping()`: the question is not "is a worker
        # alive" but "is a worker alive ON THIS QUEUE", and only this call can
        # tell them apart. A worker that has lost the broker answers neither.
        answered = (
            celery_app.control.inspect(timeout=WORKER_PING_TIMEOUT_SECONDS).active_queues()
            or {}
        )
        consumers = sorted(
            node
            for node, queues in answered.items()
            if any((one or {}).get("name") == queue for one in (queues or []))
        )
        if not consumers:
            return False, f"no Celery worker is consuming the {queue!r} queue"
        reason = f"{len(consumers)} Celery worker(s) consume {queue!r}: {', '.join(consumers)}"
    _worker_ping_cache[queue] = (now, reason)
    return True, reason


def job_active_on_worker(job_id: Any) -> bool | None:
    """Is a Celery worker EXECUTING this job right now? Registered as
    `core.jobs.set_liveness_probe` (apps.py) — DEF-BIL-8511.

    A worker killed mid-job writes nothing, so its record says `running` for
    ever; the broker hands the message back only after `visibility_timeout`
    (8,820 s here). Asking the workers is the one answer a web process can get
    in a second: `inspect().active()` lists every task each live worker is
    executing, with its arguments, and the job id is the first of them
    (`tasks.run_pending_job`).

    * **None — cannot tell**: eager dispatch (no worker exists to ask), the
      call raised, or NO worker answered at all. A silent broker is not proof
      the job stopped, and the caller then falls back to the heartbeat alone.
    * **True** — some worker lists it.
    * **False** — at least one worker answered and none lists it.
    """
    if getattr(settings, "JOBS_EAGER", False):
        return None
    try:
        from config.celery import app as celery_app

        answered = celery_app.control.inspect(timeout=WORKER_PING_TIMEOUT_SECONDS).active() or {}
    except Exception:  # noqa: BLE001 — unknown, never "stopped"
        logger.warning("BE-07: could not ask the workers whether job %s is active", job_id)
        return None
    if not answered:
        return None
    wanted = str(job_id)
    for tasks in answered.values():
        for task in tasks or []:
            if wanted in repr((task or {}).get("args")) or wanted in repr((task or {}).get("kwargs")):
                return True
    return False



# ═══════════════════════════════════════════════════════════════════════════
# THE SAMPLE SET'S CUSTOMER PORTAL — two blocks of SAMPLE_MODULES
# ═══════════════════════════════════════════════════════════════════════════
#
# PO ruling 2026-09-07, verbatim: *"before step 29 this - you ahve to set all
# the self service data in settings -> configure -> Customer portal -
# {overview, branding, Help & Answer, Tips  + service centers }"*.
#
# ⚠ **UNDER `tenancy` AND NOT UNDER `portal`, AND THAT IS G81 RATHER THAN A
# PREFERENCE.** `apps/portal/services.py` may hold only the portal's declared
# write points — *"One more `def` there is one more write, and it fails by
# name"* — and a seeding seam is not one of them. The bodies are in
# `apps/tenancy/portal_sample.py`, and every row is still written by the module
# that owns its table. The full reasoning is that file's docstring.


def seed_sample_portal_content(actor: Any) -> int:
    """BR-TEN-056/057 — the portal's overview, branding, answers, tips and
    counters. See `apps/tenancy/portal_sample.py`."""
    from apps.tenancy import portal_sample

    return portal_sample.seed_sample_portal_content(actor)


def seed_sample_portal_login(actor: Any) -> int:
    """BR-TEN-056/057 — one seeded customer who can actually sign in.
    See `apps/tenancy/portal_sample.py`."""
    from apps.tenancy import portal_sample

    return portal_sample.seed_sample_portal_login(actor)


def seed_sample_portal_login_note() -> str | None:
    """DEF-3224 — what the login block still has to say when it succeeded."""
    from apps.tenancy import portal_sample

    return portal_sample.seed_sample_portal_login_note()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-001@d5f8c32 (story+rules snapshot hash — EP-TEN-03 lead story; co-packets EP-TEN-05@0733260 · EP-TEN-06@53479d6 · EP-TEN-07@178c282 · EP-TEN-08@80cdedf · EP-MET-04@34f14b6)
# generated: 2026-08-09 by story-coder v1 (W0 tenancy provisioning + settings lane) · AMENDED 2026-08-09 by story-coder (settings rule-page + reference-data + logo gap lane) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10) · AMENDED 2026-08-10 by story-coder (DEF-016/DEF-017 reference-data lane — UNSEEDABLE_REFERENCE_LISTS register, reference_data_report(), seed_reference_data_for_tenant() backfill, six new SEED_LIST_OWNERS routes) · AMENDED 2026-08-10 by story-coder (W2 customers SCHEMA + SEAM slice — the last two UNSEEDABLE_REFERENCE_LISTS entries removed; the register is now empty) · AMENDED 2026-08-10 by story-coder (DEF-026 backend-fix lane — DEF-017's seventh reference list `premises_types`, BR-TEN-067 structural-catalogue exemption from the S111 toggle, and the report's new seeded-but-uncountable state) · AMENDED 2026-08-11 by story-coder (eleven-locale lane — SEED_LANGUAGES grows from six accepted codes to BR-SHL-041's twelve, landing WITH the six catalogues that back them) · AMENDED 2026-08-15 by story-coder (tenant custom-fields lane) · AMENDED 2026-08-18 by story-coder (CR-010 silent-seed-gaps lane — DEF-251 provisioning calls the read-validation seeder; DEF-253 `top_up_holiday_calendar`, the production caller `ensure_us_holidays_through` never had) · AMENDED 2026-08-19 by story-coder (CR-017 lane — `provision_tenant` returns `sample_plant`: the plant job's id, poll URL, status-at-response and block total, so the signup screen narrates a REAL job record instead of a timer) · AMENDED 2026-08-22 by the CR-028 AST-W3 lane (BR-AST-048 — ImportMapping handler serialize/seed for generated defaults, save_import_mapping copy-on-write + touch_import_mapping, RERUN_REFERENCE_LISTS, the import_mappings UNSEEDABLE entry removed (superseded))
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: [list-export lane 2026-08-10] ruff✔ black✔ py_compile✔ · pytest tests/test_be_list_export.py 49 passed✔ · suite `pytest tests -m "not golden and not isolation"` 762 passed / 7 skipped / 47 deselected (713 was the baseline when this lane started; the 49 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped · migrate from empty✔ makemigrations --check --dry-run clean✔ (no migration in this lane) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · frontend tsc✔ eslint✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 baseline) · ruff✔(E4/E7/E9/F select, same bar the baseline passes) black✔ pytest tests/test_us_ten_*: 86 passed / 2 skipped (logo lane · identity-seam skip-until-wired) / 2 isolation→G5✔ · suite 335 passed, 7 skipped, 20 deselected✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently) · [gap lane 2026-08-09 FINAL] ruff --select E4,E7,E9,F✔ black✔ · migrate from empty✔ makemigrations --check --dry-run✔ · suite `pytest tests -m "not golden and not isolation"` 682 passed / 7 skipped / 47 deselected (594 was the baseline when this lane started; 62 of the new tests are this lane's, the rest arrived from the concurrent audit-viewer / identity / rating lanes) · `-m isolation` 14 passed / 22 postgres-only skipped · [path-tenancy lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · no migration in this lane · [DEF-016/017 reference-data lane 2026-08-10] ruff✔(--select E4,E7,E9,F on apps/ — the bar the baseline passes; the repo-wide `ruff check .` default-rule run has 194 pre-existing findings under the newer ruff 0.15.8 in this container, none in this lane's files) black✔(--target-version py312 on this lane's files; 8 apps/ files are pre-existing reformat candidates under black 26.3.1, none of them this lane's) · suite `pytest tests -m "not golden and not isolation"` 895 passed / 9 skipped (875 was the baseline in this tree when the lane started) · `-m isolation` 14 passed / 30 skipped (unchanged) · run_gates 13-PASS/0-FAIL/1-SKIP✔ · no migration in this lane (no schema change) · RED-then-GREEN proved for both defects: removing rating's seam turns the DEF-016 guard red naming ['charge_codes','tax_jurisdictions']; removing the six SEED_LIST_OWNERS rows turns the DEF-017 guards red naming all six · [DEF-026 backend-fix lane 2026-08-10] ruff check .✔(All checks passed) black --check on this lane's 6 files✔ (the repo-wide run reports 9 reformat candidates, ALL of them the concurrent metering W2-reads lane's files — none of this lane's) · suite `pytest tests -m "not golden and not isolation"` 975 passed / 10 skipped / 4 FAILED — every failure belongs to the concurrent metering+customers W2 lane (test_be11_openapi snapshot · test_be_list_export routes/cycles · test_us_met_005_006 ×2, where `collected` flipped from None to 0 when that lane wired seams.collected_read_count) and each was PROVED pre-existing by re-running it with every file of THIS lane reverted to HEAD: identical 4 failures. The baseline when this lane started was 923 passed / 9 skipped / 0 failed · `-m isolation` sqlite 14 passed / 39 skipped; live Postgres (config.settings.local + DATABASE_URL) 40 passed / 12 skipped / 1 failed (test_us_cus_003_account_race — customers lane) · run_gates 10-PASS/4-FAIL/1-SKIP: G1, G3, G7 and G8 name ONLY apps/metering/** and apps/customers/** files from the concurrent lane (14-PASS/0-FAIL/1-SKIP at lane start) · `manage.py seed_demo --check` exit 0 under config.settings.local AND under config.settings.production · no migration in this lane (no schema change) · RED-then-GREEN proved twice: removing the two `premises_types` registrations turns 6 tests red naming it (3 in test_reference_data_completeness.py, 3 in test_us_ten_002_seeding.py); restoring the `if data["load_defaults"]` gate turns US-TEN-002 TC-2 red with seeded_lists == set() against the six structural lists · live Postgres proof: `seed_demo --tenant lonestarridge` under config.settings.production seeded 5 premises_types into a tenant that had none and could not have been given any · [eleven-locale lane 2026-08-11] pytest tests/test_us_ten_005_006_settings.py tests/test_us_cus_003_account_write.py 63 passed✔ (TC-6's `fr` refusal still refuses — the six new codes are region-qualified, so a bare `fr` is still outside the tuple) · run_gates G15 i18n-parity PASS (10 catalogues × 3087 keys, 30870 values translated or allowlisted); this lane touched ONE backend file and none of the concurrent r17 custom-fields lane's G1/G7/G8/G10 failures are its
# exceptions: identity/rating/billing/payments/metering/customers seams documented + skip-until-wired (seams.py) · ein plain-stored pending a platform crypto kernel (OQ-016 ruling needs one; masked in audit) [⚠ SUPERSEDED 2026-08-24 by BR-CUS-092(b)/DEF-632 — the kernel exists (core/crypto.py) and this column is its second caller; converted by tenancy/migrations/0018_br_cus_092_ein_encrypted. Kept rather than deleted because it is the historical record of how long a CLOSED ruling went unimplemented behind the words 'for now'] · DEP-/RCT-/EXP- series formats unstated → not seeded (reported) · E2-candidates: US-TEN-006 TC-4 warn-and-confirm vs BR-TEN-042 hard lock; TC-6 en-only vs BR-TEN-042 language set; flows §10 "is_system never deletable" vs US-TEN-011 TC-2 — reported, implemented per the BR register (STATUS AUTHORITY) · [gap lane 2026-08-09] logo upload BUILT (BR-TEN-019; rasterization still absent — see apps/tenancy/logo.py) · the reference-seed path now falls back to tenancy's HOSTED table when billing/payments have no seed_reference_list — seam still consulted FIRST, so the owning lane wins the moment it lands (BR-TEN-013/031) · UomLookupHandler.delete deliberately still allows deleting an unused SEEDED row (the pre-existing US-TEN-011 TC-2 reading); the two new hosted handlers follow apps/assets and refuse it (BR-TEN-036) — the divergence is REPORTED, not silently harmonized · [path-tenancy lane 2026-08-10] provision_tenant issues the owner's session inside the SAME transaction through an OPTIONAL seam (unwired ⇒ no session, tenant still live, owner signs in — the superseded BR-TEN-045 flow); the replay branch returns owner_session_id=None on purpose, because BR-TEN-010 matches on subdomain + owner email and checks NO password · [DEF-016/017 lane 2026-08-10] a reference list may still legitimately SKIP (BR-TEN-013 skip-until-wired) but may no longer be QUIETLY empty: an empty list must carry a written reason in UNSEEDABLE_REFERENCE_LISTS or reference_data_report() marks it UNEXPLAINED, which makes seed_demo exit non-zero and fails tests/test_reference_data_completeness.py · account_statuses is seeded by NOBODY and carries NO fixture values on purpose: B2's account_status ENUM, A5 §Account (marked UNKNOWN) and the S8 prototype card name three DIFFERENT sets, and the prime directive forbids choosing one — REPORTED to the PO, not resolved · account_types values ARE ratified (B2 'Tables to add' #12 [D5]) and sit in the fixture, but the customers module owns no tables and authors no seam, so the list waits on that lane · the S62 checklist half of BR-TEN-056 clause 3 is NOT built here (US-TEN-019's lane owns it); reference_data_report() is the seam it reads · [W2 customers slice 2026-08-10] UNSEEDABLE_REFERENCE_LISTS is now EMPTY — `account_statuses` and `account_types` both seed through apps.customers.services.seed_reference_list, which is what removing an entry looks like; the register itself stays, for the next module that declares a list before it can seed one · [DEF-026 lane 2026-08-10] `premises_types` is DEF-017's SEVENTH list: it was in NEITHER LOOKUP_LISTS nor SEED_LIST_OWNERS although apps.metering.services.seed_reference_list has handled the code since it was written, so the only way a tenant ever got premises types was the side effect of `ensure_reference_catalogs()` on a premises WRITE — no ledger row, no audit row, no line in any report, and a brand-new tenant whose S16 wizard could not resolve a type. Both registrations now exist; the fixture deliberately carries NO premises_types entries so metering's own BR-MET-034 SEED_PREMISES_TYPES stays the single ratified source (nothing to drift) · REPORTED, NOT FIXED HERE: the S8 card for that list still cannot render — it needs apps.metering to call register_lookup_handler AND to author the list's CRUD services, of which it has none, and apps/metering/** is another lane's territory in this session. Rather than show the list as EMPTY (false — it has five rows) or as seeded (a claim this process cannot check), reference_data_report() gained a fourth state, `uncounted`, backed by tenancy's OWN reference_seed_runs ledger and carrying the reason in prose; it counts as neither empty nor unexplained, so UNSEEDABLE_REFERENCE_LISTS stays empty and the DEF-016 guard is not weakened · BR-TEN-067 (CONFIRMED, PO 2026-08-10, OQ-082) NARROWS the S111 toggle: the six STRUCTURAL_REFERENCE_LISTS always seed because they are vocabulary the schema requires (an account cannot exist without a status; create_premises cannot resolve a type) — the toggle governs sample content. `account_types` is deliberately NOT in that set: r5 #12 [D5] makes it a PLATFORM table the toggle never governed · [OQ-115 lane 2026-08-11] `update_tenant_service` now accepts `revenue_account` / `base_revenue_account` (PO: *"allow tenant user to override it"*). It validates ONLY that the id is a LIVE account of this tenant's own chart, through `seams.ledger_account_is_live`; it does NOT require the account to be of type `revenue`. That restriction was never ruled and is not invented here — a tenant owns its chart and may have renumbered or re-typed anything (US-LED-005) — but the consequence is real and is stated rather than hidden: a tenant CAN map service revenue onto, say, their AR account and see it in the wrong place on the trial balance. REPORTED as a judgment call in 12-governance/02-decision-log.md 2026-08-11 and flagged for the finance reviewer in the human-review ledger row · a tenant provisioned BEFORE that ruling keeps all 22 seeded accounts; nothing here deletes or deactivates, so the six a water-only tenant does not sell go away only if its own staff remove them on S56
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
