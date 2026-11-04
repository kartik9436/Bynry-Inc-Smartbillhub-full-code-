# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-001 (EP-CUS-01 — the S17 status pill + TC-5, the second
#           active account on a unit) · US-CUS-002 (S17 search/filters read
#           path) · US-CUS-003 (EP-CUS-02 — the S18 New Account write path:
#           account + contact + address + service agreements, BR-CUS-017's
#           enforcement and BR-CUS-020's vacant-unit rule) · US-CUS-004
#           (EP-CUS-02 — the S19 Move-In write path: the next occupant takes
#           the unit through the SAME BR-CUS-017 guard, with BR-CUS-056's
#           boundary day) · US-CUS-005 (EP-CUS-02 — the S20 Move-Out write
#           path: `closed_at`, the terminal status, the service agreements'
#           `ended_on`, and the BR-CUS-031 final-bill handoff RECORD) ·
#           US-CUS-006 (ONLY the BR-CUS-058 half: `credit_tier` is COMPUTED
#           and has NO input path — the BR-CUS-029 snapshot table itself is
#           NOT built here) ·
#           US-TEN-002 (seed standard reference data from platform fixtures)
#           Screens: S17 · S18 · S19 · S20 · S21 · S8 (Settings → Reference
#           data) · S111
# Journeys: J2 step 4 (account active / snapshot / deposit — two of the three
#           still unwritable, and SAID SO) · T4-06 (Active → Closed: the
#           final-bill chain) · T5-15 step 5 (the RECOVERY door — move-out
#           frees the unit, move-in takes it)
#           AMENDED 2026-08-15 (tenant custom-fields lane): US-SHL-015 (EP-SHL-07 — `custom_data` joins CREATE_FIELDS/PATCH_FIELDS and is
#           validated by TENANCY, the registry owner, never by a copy here)
# Rules:    BR-CUS-055 (account statuses — the five seeded, tenant-extensible
#           values and their behaviour classes; PO OQ-058(b), class seed
#           OQ-064 CLOSED) · BR-CUS-016 (stored status comes from the lookup) ·
#           BR-CUS-012 (the confirmed account attribute set) · BR-CUS-017 (at
#           most ONE active account per unit — enforced HERE and nowhere else
#           by PO ruling, OQ-092 CLOSED option (a)) · BR-CUS-018 (a draft account is `pending`, never billed,
#           and does not block the unit) · BR-CUS-020 (unit pickers offer
#           vacant/reserved units only) · BR-CUS-021 (initial/final reads
#           commit through the METERING service — not from here) ·
#           BR-CUS-022 (billing starts at the service start date) ·
#           BR-CUS-023 (deposit amount is a
#           LOOKUP, never hand-entered) · BR-CUS-024 (deposit carry-forward at
#           move-in rides the customer entity) · BR-CUS-025 (deposit applies to
#           the final bill FIRST) · BR-CUS-029 (the account plan snapshot) ·
#           BR-CUS-030 (move-out: final reads, `closed_at`, terminal status,
#           dunning stop) · BR-CUS-031 (the final-bill HANDOFF contract to
#           billing) · BR-CUS-045 (contact PII columns) · BR-CUS-054 (the
#           first-class customer entity) · BR-CUS-056 (same-day move: the
#           OUTGOING account pays the move day; the incoming one starts the
#           next day) · BR-CUS-057 (deposit interest) · BR-CUS-058
#           (credit tier is COMPUTED — no edit path) · BR-CUS-059 (autopay is
#           capture-only in v1) · BR-CUS-064 (preferred language) ·
#           BR-BIL-004 (issued invoices are immutable — a move-out may not be
#           backdated behind one) · BR-MET-036 (occupancy DERIVES from the
#           active account — this is what a move-out frees) ·
#           BR-MET-040 (a plan is REQUIRED at activation — and since CR-047 it
#           is checked AT ACTIVATION and not at import-creation; see
#           `_require_plan_on_unit`) ·
#           BR-MET-044 (the unit KEEPS its plan after a move-out) ·
#           BR-TEN-012/013/016/
#           031/036 (reference-data seeding law) · BR-TEN-026 (the live
#           active-account count the service-disable guard reads) ·
#           BR-TEN-035 (account numbers come from the tenant series) ·
#           BR-TEN-043 (event-time law) · BR-TEN-065 (the sample-data job needs
#           `Pending activation` to exist) · BR-SHL-025 (the server enforces
#           every mutating call independently)
# Tests:    06-backend/tests/test_us_cus_003_account_write.py ·
#           06-backend/tests/test_us_cus_003_account_race.py (the BR-CUS-017
#           concurrency proof, live Postgres) ·
#           06-backend/tests/test_us_cus_004_005_move_in_out.py ·
#           06-backend/tests/test_us_cus_004_move_in_race.py (the same race,
#           proved for the move-in path, live Postgres) ·
#           06-backend/tests/test_us_cus_schema_and_seed.py ·
#           06-backend/tests/test_reference_data_completeness.py ·
#           06-backend/tests/test_cr047_import_inheritance.py (CR-047 /
#           `DEF-2518` — the import door inherits the unit's services whatever
#           the row's status, and BR-MET-040 moves to ACTIVATION) ·
#           06-backend/tests/test_cr048_b6_b10.py (CR-048 B10 — the two move
#           messages, their idempotency key, and the savepoint that keeps a
#           notification failure off the move)
# Change:   CR-048 wave B task B10 (2026-08-30) — *"a customer moving in is
#           told NOTHING"*. `move_in` and `move_out` each queue ONE message at
#           the point the job completes, through
#           `apps/customers/notifications_seam.py` (resolved by name — B1), in
#           the flow's OWN transaction and inside the seam's OWN savepoint
#           (hard-won law 14). Keyed on the MOVE RECORD, never the account: the
#           account-keyed version silently dedupes the move-out letter into the
#           welcome written months earlier. The outcome rides `move_message` on
#           both wizard responses ·
#           CR-047 (2026-08-29) — `DEF-2518`. PO verbatim: *"if account is
#           created then we need to inherit details form units - otherwise
#           upadling it later will be big tasks"*. `_make_occupying` is split
#           into `_occupancy_guards` (a) + `_inherit_service_links` (b); the
#           import door always gets (b) and gets (a) only for a billing status.
#           `create_from_import` returns `services_linked` for the S68 receipt.
# Impacts:  apps/customers/api.py (the /accounts endpoints) ·
#           apps/customers/selectors.py · apps/customers/lookups.py (used_by
#           counts stop being 0 the moment an account exists) · apps/metering/
#           seams.py resolves `active_account_for_unit` /
#           `account_reference_count` / `unpaid_balance_exists` here BY NAME —
#           defining them is what turns BR-MET-036 occupancy on ·
#           apps/tenancy/seams.py resolves `active_account_count` here
#           (BR-TEN-026 service-disable guard)
# ───────────────────────────────────────────────────────
"""customers service layer — the ONLY write path into this module's tables
(LAW 0: api thin → services sole writer → selectors read).

TWO SLICES LIVE HERE, in order:

1. **Reference data** (slice 1) — `seed_reference_list` implements the tenancy
   seeding seam documented in apps/tenancy/seams.py for the two lists tenancy's
   LOOKUP_LISTS registry routes to this module. It landed because
   `account_statuses` was the last thing standing between the repo and
   BR-TEN-065: the sample-data job must create its sample account `Pending
   activation`, and until this module owned a table there was nowhere for that
   row to live.
2. **The account write path** (slice 2) — create / read-back /
   update / activate, plus the cross-module seams metering and tenancy resolve
   here BY NAME. Plan changes, payment plans and the import
   wizard are still NOT here; each is an explicit stub at the bottom of
   this file naming the rule that owns it, because those boundaries became
   REACHABLE from a live write path in that slice and a silent gap is worse
   than a loud one.
3. **Move-in / move-out** (slice 3, this one) — `move_out` and `move_in`, which
   were two of those stubs. See the section below; the short version is that
   slice 2 could OCCUPY a unit and could never FREE one, so a unit taken by
   mistake stayed taken and T5-15 step 5's ratified recovery door — move the
   occupant out, move the next one in — did not exist.

MOVE-OUT / MOVE-IN — what slice 3 does and, precisely, what it does not
──────────────────────────────────────────────────────────────────────
`move_out` performs the parts of BR-CUS-030 that have somewhere to be written:
`accounts.closed_at` = the move-out date, the status → the tenant's TERMINAL
status (BR-CUS-055), every open `service_agreements.ended_on` = the same date,
and an `account.closed` audit row. That is enough to make BR-MET-036's derived
occupancy answer "vacant" again — the terminal class does not occupy — so the
unit returns to the pickers and the next move-in can take it. `BR-MET-044` needs
nothing done: the unit's plan is metering's column and this path never touches
it, which is exactly "the unit KEEPS its last plan as the next-tenant prefill".

Everything else BR-CUS-030/031 names has NO home in this repository, and each is
REPORTED in the response rather than implied:

  · **the final bill** — billing owns `invoices` (W3) and has no tables at all;
    the PO holds that lane. A move-out that claimed to settle a final bill would
    be a lie, so it does not claim one (BR-CUS-031, BR-BIL-004).
  · **the handoff RECORD** — BR-CUS-031's contract is assembled and returned
    (and lands in the audit row), but there is NO table, queue or outbox for it
    in B2 or any addendum, so it is not PERSISTED anywhere a bill run could read
    it. `final_bill_handoff.persisted` is False and says which rule is missing.
  · **final reads** — BR-CUS-021 commits reads through the METERING service, and
    metering's only commit path is the S28 batch wizard whose idempotency
    fingerprint is scoped to (period, cycle, route, service, source). Minting a
    single-meter batch inside it could collide with the month's real import, so
    `final_reads` is a REFUSED input naming BR-CUS-021 and the handoff says the
    reads are absent.
  · **deposit settlement + interest** — BR-CUS-025's apply-first needs the final
    bill; the refund leg is payments' `refunds` (no tables); BR-CUS-057's
    accrual engine is US-CUS-023 and is not built. No figure is computed here.
  · **the close reason** — ✅ **BUILT 2026-09-20** (PO ruling of that date,
    option A). `reason` is an ACCEPTED field on this door and on no other, and
    lands in `accounts.close_reason` in the close's own transaction. It read
    *"PROPOSED-SCHEMA, not built. REFUSED with its rule rather than dropped"*
    until that day.
  · **dunning stop / close-out documents** — collections and notifications have
    no tables. Warned by name.

`move_in` is the S19 chain (11b §S19: `POST /accounts/{id}/move-in`, where {id}
is the OUTGOING account): it creates the NEXT account on that account's unit.
It creates nothing that `create_account` cannot, and deliberately so — what it
adds is the two rules that only exist at a turnover boundary:

  · it goes through **the same `_make_occupying` guard** — advisory lock on the
    (tenant, unit) scope FIRST, then the BR-CUS-017 check — because it is
    another path that makes an account occupy a unit, and a second door into
    the same room needs the same lock, not a copy of it.
  · **BR-CUS-056** (CONFIRMED — PO OQ-060 a): the outgoing account pays the move
    day, so an incoming start on or before it is REFUSED. That check lives in
    `_make_occupying` too, not in `move_in`, because the rule is about the
    UNIT's boundary day and every occupying path must honour it — activation of
    an old draft included.

The S19 STANDALONE entry (S17 → Move-in on a unit with no predecessor) has no
path in 11b §S19 — the only row there is `POST /accounts/{id}/move-in`. It is
served today by `POST /accounts` with an occupying status, which takes the same
guard and now the same BR-CUS-056 rule. No second endpoint is invented for it;
REPORTED instead. Same for `POST /accounts/{id}/move-out/preview` (11b §S20):
the preview is B4.3 final-bill math over invoices that do not exist, and a route
answering 501 is a promise (api.py's stated posture).

BR-CUS-017 — "at most ONE active account per unit" — IS THE POINT OF SLICE 2
────────────────────────────────────────────────────────────────────────────
OQ-092 recorded that this rule has NO DATABASE HALF and cannot get one as
written: the PROPOSED partial unique index `accounts(tenant_id, unit_id) WHERE
status='active'` assumed `status` was B2 §2's ENUM, and r5 #20 / BR-CUS-055
made it a PROTECTed FK to `account_statuses` — a PostgreSQL partial-index
predicate may name only its own table's columns, so it cannot read
`behavior_class` through the FK.

**The PO CLOSED it on 2026-08-10, option (a): service-layer enforcement only.**
Verbatim from the registry — "the check runs inside the create/update
transaction with row locking so two concurrent requests cannot both win, and a
test proves the race is closed. No denormalised column is added — it could
drift from the status FK and would be a second source of truth for the same
fact." So THIS FILE is the whole enforcement BY RULING, not by omission: it is
the only thing standing between a unit and two active accounts on it, i.e.
between one meter and two bills for one flow of consumption. The absence of the
DB constraint stays pinned by
`test_us_cus_001_tc5__one_active_account_per_unit_has_no_database_half`
(tests/test_w2_models.py), which the same ruling requires.

Enforcement here is therefore TWO mechanisms, not one:

  · **Mutual exclusion** — `pg_advisory_xact_lock(<BR-CUS-017 namespace>,
    <hash of tenant+unit>)`, taken INSIDE the write transaction and BEFORE the
    check, by every path that can make an account occupy a unit. Row locking
    alone cannot close this race: two concurrent creates on a VACANT unit both
    see zero rows, and `SELECT … FOR UPDATE` cannot lock rows that do not
    exist. The advisory lock is on the (tenant, unit) SCOPE, so the second
    transaction blocks until the first commits and then sees its row.
  · **The check** — after the lock, `occupying_accounts_for_unit()` is re-read
    `FOR UPDATE`; a hit refuses with 409 BIZ-STATE naming the existing account
    (T5-15 step 3: "the IS-7 failed state names the existing active account").

Advisory locks are a PostgreSQL feature. On the sqlite test tier the lock is a
documented no-op and only the check survives — which is exactly why the
concurrency proof (tests/test_us_cus_003_account_race.py) carries the
`isolation` marker and runs on the live cluster. A green sqlite run proves
nothing about it, and this comment is not the guarantee: that test is.

Money law: this module computes NO money. `balance` is a ledger-owned cache and
`deposit_on_file` is a BR-CUS-023 LOOKUP from the plan's deposit schedule
(US-CUS-007's slice); both are REFUSED as input fields here rather than given a
hand-entry path, so no figure in this file is ever chosen by anyone.

Two lists, two very different seeding stories — stated once so neither is
mistaken for the other:

  · `account_statuses` is a TENANT table. Rows are written per tenant, under
    the caller's `app.tenant_id`, by this seam. A replay writes nothing.
  · `account_types` is a PLATFORM table (r5 #12 [D5]: "platform-seeded"; r5's
    closing line excludes it from RLS). Its four rows are created by migration
    0002 BEFORE any tenant exists — the same posture tenancy 0001 takes for
    the service catalog and tenancy 0005 for the subscription SKUs. This seam
    still routes the list, because tenancy's registry declares it and
    `test_reference_data_completeness` requires every declared list to have a
    route; what it does is INSERT-MISSING only, so a backfill can restore a
    platform row someone deleted, and a normal run creates nothing and
    returns 0. It never writes a tenant-specific row, because there is no
    tenant column to write one into.

Nothing in the seeding half touches money either. The account tables carry
NUMERIC(18,6) + CHAR(3) columns (DB-3) but no figure is seeded, computed or
defaulted anywhere here.
"""

import hashlib
import logging
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from django.db import connection, transaction
from django.utils import timezone

from apps.customers import (
    account_import,
    deposit,
    identity_match,
    models,
    move_fees,
    move_in_preferences,
    moves,
    notifications_seam,
    seams,
)
from core import audit as core_audit
from core import errors
from core import numbering as core_numbering
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

logger = logging.getLogger("smartbillhub.customers")

# ── BR-CUS-055 (CONFIRMED — PO OQ-058 option b; class seed OQ-064 CLOSED) ────
# The five seeded statuses with their behaviour classes, verbatim from the rule
# register (04-docs/05-modules/03-customers/02-business-rules.md, BR-CUS-055).
# Billing keys off the CLASS, never the tenant's label — a tenant may rename
# "Vacation hold/Suspended" and nothing downstream moves.
#
# NOT derived from B2 §2's `account_status` ENUM, from A5 §Account (which A5
# itself marks UNKNOWN) or from the S8 prototype card: all three predate the
# 2026-08-08 ruling and name three DIFFERENT sets.
CLASS_NON_BILLABLE = "non_billable"
CLASS_BILLABLE = "billable"
CLASS_BILLABLE_BASE_ONLY = "billable_base_only"
CLASS_TERMINAL = "terminal"
BEHAVIOR_CLASSES: tuple[str, ...] = (
    CLASS_NON_BILLABLE,
    CLASS_BILLABLE,
    CLASS_BILLABLE_BASE_ONLY,
    CLASS_TERMINAL,
)

# ── BR-CUS-017 / BR-MET-036: which statuses OCCUPY a unit ───────────────────
# DERIVED from two CONFIRMED statements, not chosen:
#   · BR-CUS-018 — a draft/pending account "never derives occupancy and does
#     not block the unit for other move-ins"  ⇒ non_billable does NOT occupy.
#   · BR-MET-036 — the unit flips to Vacant when the active account is CLOSED
#     ⇒ terminal does NOT occupy.
# What is left is exactly the billable pair, which is also the right shape for
# a tenant-added status (US-CUS-020 TC-3 "Legal hold"): the boundary keys off
# the CLASS, never the tenant's label, the same way billing does.
# RESIDUE, REPORTED not resolved: a tenant could add a NON-draft status in the
# non_billable class, and this reading would leave its unit pickable. Nothing
# signed says whether that is right. OQ-092's closure ruled the ENFORCEMENT
# (service-layer, locked); it did not rule this class boundary — REPORTED in
# the lane report as a new question rather than decided here.
# ⚠ **AND IT IS NO LONGER HYPOTHETICAL — BR-CUS-107 SEEDS ONE (2026-08-25).**
# `disconnected` is a PLATFORM-seeded, NON-draft, `non_billable` status, so the
# residue above now names a row this product ships.
# ✅ **AND FOR THAT ROW IT IS RESOLVED — BR-CUS-110 (PO 2026-08-26, closing
# OQ-386), verbatim: *"B Yes, a cut ends occupancy and the debt follows the
# person"*.** This note read, until 2026-08-30, that two CONFIRMED rules said a
# cut account still occupies and that this class-derived reading was therefore
# wrong. **The PO ruled the other way**, against the recommendation that was
# given: the tuple below is CORRECT AS WRITTEN, a cut customer's unit reading
# vacant and pickable is INTENDED, and the fallout — `move_out` refusing them
# `not_an_occupant` — was DEF-724 and is FIXED by `close_out.py`
# (BR-CUS-430/431). The residue above still stands for a status a TENANT adds;
# it no longer stands for this one.
# ⛔ **WHAT STILL STOPS `disconnects.commit_cut` ASSIGNING THE ROW IS MONEY, AND
# IT IS `OQ-1170`:** `selectors.accounts_for_bill_run` scopes a bill run on this
# very tuple, so the moment the status is written the account leaves the run and
# the days it consumed BEFORE the cut are billed by nobody — while BR-CUS-103
# says base is billed right up to the cut. See
# `disconnects.DISCONNECTED_STATUS_ASSIGNED` (was `..._NOT_ASSIGNED` until the
# PO's ruling of 2026-08-30 closed OQ-1170), corrected the same day
# (`DEF-2640`: the blocker had been attributed to billing's
# `CLASSES_THAT_BILL`, which the account never reaches).
OCCUPYING_BEHAVIOR_CLASSES: tuple[str, ...] = (CLASS_BILLABLE, CLASS_BILLABLE_BASE_ONLY)

#: The BR-CUS-018 draft status a new account starts in unless the caller names
#: another one. Seeded by SEED_ACCOUNT_STATUSES above.
PENDING_STATUS_CODE = "pending_activation"

SEED_ACCOUNT_STATUSES: tuple[tuple[str, str, str], ...] = (
    ("pending_activation", "Pending activation", CLASS_NON_BILLABLE),
    ("active", "Active", CLASS_BILLABLE),
    # "Marked disconnect" is BILLABLE, not base-only: the account is still
    # consuming until the cut (OQ-064 closure — PO delegated, PM ruled).
    ("marked_disconnect", "Marked disconnect", CLASS_BILLABLE),
    ("vacation_hold", "Vacation hold/Suspended", CLASS_BILLABLE_BASE_ONLY),
    ("closed", "Closed", CLASS_TERMINAL),
    # ── THE SIXTH, BR-CUS-107 (PO ruling 2026-08-25, closing DEF-701) ───────
    # *"A CUT ACCOUNT GETS A SIXTH STATUS, `Disconnected`, IN CLASS
    # `non_billable`."* BR-CUS-055 seeded five and none of them means "the
    # service is off": a cut account read `Marked disconnect / billable`, which
    # is the rung BEFORE the cut and says *consuming until cut* about a
    # customer who has stopped consuming (DEF-701, measured on `A-11340`).
    #
    # The other three classes were each RULED OUT with a reason, so none of
    # them is available to a later lane that thinks it knows better:
    # `billable` bills a service that no longer runs; `billable_base_only` was
    # eliminated by the PO's own answer the same day (BR-CUS-103 — base stops
    # at the cut, so there is no base to bill); `terminal` is what `Closed`
    # means, and a cut account is not closed — it holds a debt, it can pay, and
    # it comes back. Worked: `A-11488`, cut 2026-08-18 owing **$612.75**, reads
    # `Disconnected / non-billable`, nothing accrues, the $612.75 stays owed,
    # and `mark_reconnecting` can still take it back.
    #
    # ⛔ **THE ROW IS SEEDED AND NOTHING ASSIGNS IT YET, AND THAT IS REPORTED
    # RATHER THAN QUIETLY DONE.** `disconnects.commit_cut` does NOT write it —
    # see `disconnects.DISCONNECTED_STATUS_ASSIGNED` for the two measured
    # consequences that must be closed first. Both fall out of the CLASS and
    # neither is a reason to pick a different one (BR-CUS-107's own clause):
    #   1. **OCCUPANCY — RULED, AND THE CODE IS RIGHT (BR-CUS-110, PO
    #      2026-08-26, closing OQ-386).** This entry said until 2026-08-30 that
    #      an account on this row stops occupying its unit and that *"that is
    #      wrong"*. The PO ruled the opposite — *"B Yes, a cut ends occupancy
    #      and the debt follows the person"* — so the unit reading VACANT and
    #      pickable is INTENDED. The one real consequence, `move_out` refusing
    #      the cut customer `not_an_occupant` and leaving them no terminal
    #      path, was DEF-724 and is FIXED (`close_out.py`, BR-CUS-430/431).
    #      Nothing is owed on this half.
    #   2. **THE ACCOUNT LEAVES THE BILL RUN — AND IT LEAVES IT HERE, NOT IN
    #      BILLING (corrected 2026-08-30, `DEF-2640`).** This entry blamed
    #      `apps/billing/stages/resolve_subscription.CLASSES_THAT_BILL` and a
    #      `BillingRuleError` on the run's exception list. **The account never
    #      reaches stage 1**: `billing.runs.prepare_run` asks
    #      `selectors.accounts_for_bill_run`, which filters on
    #      `OCCUPYING_BEHAVIOR_CLASSES` just below, so we drop it ourselves and
    #      silently. The COST is unchanged and is why the row is still not
    #      assigned: the usage and base consumed BEFORE the cut are billed by
    #      nobody, while BR-CUS-103 says base is billed right up to the cut —
    #      it stops base by subtracting the dark days from `service_days`
    #      (`disconnects.service_off_windows`), which only runs on an account
    #      the run SELECTED. Two signed rules meet and one must give: `OQ-1170`,
    #      which also asks what status a RESTORED account comes back on, since
    #      `restore_service` writes no account column either.
    ("disconnected", "Disconnected", CLASS_NON_BILLABLE),
)

# ── the consumer categories a NEW TENANT starts with ────────────────────────
# ⚠ **TENANT ROWS SINCE THE PO RULING OF 2026-09-17 — *"utility can get their
# own account types"* — WHICH SUPERSEDES `BR-CUS-094`'s PLATFORM POSTURE.** B2
# r5 #12 [D5] said "account_types (platform-seeded: residential/commercial/
# industrial/government)" and this tuple carried exactly those four; the seven
# `BR-CUS-094` ratified lived only in `models.AccountType.SEVEN_CATEGORIES` and
# in migration 0019, which is the drift `0019`'s own docstring reported and
# could not fix from its lane ("TWO COPIES OF THE OLD FOUR ARE STILL OUT
# THERE"). The two copies are ONE now: this tuple IS the seven plus the legacy
# code, mirrored from the model and pinned equal by
# `tests/test_reference_data_completeness.py`.
#
# ⚠ **THIS IS THE SEED, NOT THE VOCABULARY.** A tenant's list starts here and
# grows; nothing may read this tuple as the set of lawful values.
#
# `government` is seeded `legacy=True`: unselectable on new records, valid
# everywhere it already is (`BR-CUS-094` — *"no row is re-labelled by guess"*).
SEED_ACCOUNT_TYPES: tuple[tuple[str, str], ...] = tuple(models.AccountType.SEVEN_CATEGORIES) + (
    ("government", "Government"),
)

# ── BR-CUS-067 — the CR-010 sub-type tree (PO 2026-08-17, verbatim "add
# them"; decision log "Part-10 confirmations" 10.0). (code, name, parent
# account_type code). TENANT rows, deliberately unlike their PLATFORM parents:
# the PO's item-1 ruling puts Hospital/Church-shaped vocabulary here and the
# rows are the tenant's to rename, extend and deactivate. All 12 seed
# `is_system` (BR-TEN-036: deactivatable, never deletable). DISCRETIONARY,
# not structural: no schema column requires a sub-type to exist
# (`accounts.account_subtype_id` is NULL by r5 #19), so the S111 toggle
# governs the list like any other sample-content vocabulary (BR-TEN-067).
SEED_ACCOUNT_SUBTYPES: tuple[tuple[str, str, str], ...] = (
    ("single_family", "Single-family", "residential"),
    ("multi_family", "Multi-family", "residential"),
    ("senior_low_income", "Senior/Low-income", "residential"),
    ("small_commercial", "Small commercial", "commercial"),
    ("large_commercial", "Large commercial", "commercial"),
    # The PO's own item-1 amendment: *"where you will add Hospital, Church
    # etc"* — placed under Commercial as these two, shown back on screen.
    ("institutional_non_profit", "Institutional & non-profit", "commercial"),
    ("healthcare", "Healthcare", "commercial"),
    ("light_industrial", "Light industrial", "industrial"),
    ("heavy_industrial", "Heavy industrial", "industrial"),
    ("municipal_buildings", "Municipal buildings", "government"),
    ("schools", "Schools", "government"),
    ("parks_facilities", "Parks & facilities", "government"),
    # ⚠ **THE THIRTEENTH — PO ruling 2026-09-07, verbatim: *"please add
    # Governtment in it"*.** Twelve become thirteen.
    #
    # **IT IS NOT A DUPLICATE OF THE ACCOUNT *TYPE* OF THE SAME NAME, AND THAT
    # IS WORTH WRITING DOWN BECAUSE IT LOOKS LIKE ONE.** `government` is one of
    # the four PLATFORM account types (B2 r5 #12) and this is a SUBTYPE under
    # it — the tenant-editable level beneath the type (BR-CUS-067). The three
    # rows above it are specific kinds of public body; this is the general one,
    # for the government customer that is none of them. A utility billing a
    # federal depot differently from a city hall needs somewhere to put it, and
    # before this the only choices were three that name the wrong thing.
    #
    # APPENDED LAST, NOT SORTED IN — this tuple's ORDER is the order the S8 card
    # prints, and inserting it among its siblings would move rows on a screen a
    # tenant already knows. The same rule `DEFAULT_MAPPING_TEMPLATES` and
    # `core.numbering.SERIES_CATALOG` follow.
    ("government", "Government", "government"),
)

OWNED_REFERENCE_LISTS: tuple[str, ...] = (
    "account_statuses",
    "account_types",
    # CR-010 (2026-08-17): the two-level sub-type tree becomes a seeded,
    # tenant-extensible reference list with its own S8 card.
    "account_subtypes",
)


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _fixture_rows(
    entries: list[dict[str, Any]], list_code: str, keys: tuple[str, ...]
) -> list[tuple[str, ...]]:
    """Validate a fixture list into (key, …) tuples, or refuse loudly.

    A fixture entry missing its code or name is a PLATFORM DATA defect, not a
    tenant problem: it would seed a nameless reference row that renders blank
    on the S8 card forever. It raises rather than being skipped."""
    rows: list[tuple[str, ...]] = []
    for entry in entries:
        values = tuple(str(entry.get(key, "") or "").strip() for key in keys)
        if not all(values):
            raise errors.SysError(
                errors.SYS_INTERNAL,
                message_key="customers.reference_fixture_invalid",
                params={"list": list_code},
            )
        rows.append(values)
    return rows


def ensure_account_statuses() -> int:
    """Idempotent seed of the BR-CUS-055 statuses for the CURRENT tenant.

    Called by the seam when the fixture carries no list (the assets posture:
    an empty fixture falls back to the owning module's own RATIFIED set) and
    available to any later write path that needs a status to exist —
    migration 0001 creates the table EMPTY for tenants provisioned before it.

    Returns the number of rows CREATED, so a replay returns 0."""
    tenant_id = _tenant_id()
    created = 0
    for code, name, behavior_class in SEED_ACCOUNT_STATUSES:
        _, was_created = models.AccountStatus.objects.get_or_create(
            tenant_id=tenant_id,
            code=code,
            defaults={
                "name": name,
                "behavior_class": behavior_class,
                "is_system": True,
                "active": True,
            },
        )
        created += int(was_created)
    return created


def ensure_account_subtypes() -> int:
    """Idempotent seed of the BR-CUS-067 sub-type tree for the CURRENT tenant.

    Same posture as `ensure_account_statuses`: the platform fixture carries no
    `account_subtypes` entries on purpose — SEED_ACCOUNT_SUBTYPES is the single
    ratified source (the DEF-026 premises_types precedent: two copies of one
    law is a drift waiting for a pin test).

    Each row resolves its parent by the type code **of this tenant's own list**.
    ⚠ A missing parent used to be a platform-data defect (customers.0003 seeded
    the types before any tenant existed); since the PO ruling of 2026-09-17 the
    types are tenant rows, so this seeds them FIRST rather than raising at a
    tenant whose provisioning simply ran the lists in fixture order.

    Returns the number of rows CREATED, so a replay returns 0."""
    tenant_id = _tenant_id()
    ensure_account_types()
    created = 0
    for code, name, parent_code in SEED_ACCOUNT_SUBTYPES:
        # ⚠ TENANT-SCOPED SINCE THE PO RULING OF 2026-09-17: the parent is this
        # tenant's own type row, never "whichever tenant's row came back first".
        # sqlite has no RLS, so the explicit filter is what makes the test suite
        # test the same thing production does.
        parent = models.AccountType.objects.filter(
            tenant_id=tenant_id, code__iexact=parent_code
        ).first()
        if parent is None:
            raise errors.SysError(
                errors.SYS_INTERNAL,
                message_key="customers.reference_fixture_invalid",
                params={"list": "account_subtypes", "parent": parent_code},
            )
        # BR-TEN-012 by natural key: an existing code is LEFT ALONE, even if
        # the tenant re-parented or renamed it — a fixture never overwrites a
        # tenant edit.
        if models.AccountSubtype.objects.filter(tenant_id=tenant_id, code__iexact=code).exists():
            continue
        models.AccountSubtype.objects.create(
            tenant_id=tenant_id,
            account_type=parent,
            code=code,
            name=name,
            is_system=True,
            active=True,
        )
        created += 1
    return created


def ensure_account_types() -> int:
    """Idempotent seed of the consumer categories for the CURRENT tenant.

    ⚠ **PER TENANT SINCE THE PO RULING OF 2026-09-17** (*"utility can get their
    own account types"*). It used to be a platform insert-missing that read no
    tenant context at all, because the table had no `tenant_id`; it now has the
    same posture as its two siblings `ensure_account_statuses` and
    `ensure_account_subtypes`, and a brand-new tenant's first eight rows come
    from HERE rather than from a migration.

    `BR-TEN-012` by natural key: an existing code is LEFT ALONE, even if the
    tenant renamed it — a fixture never overwrites a tenant edit. So a replay
    returns 0 and a tenant that deleted a row it was allowed to delete gets it
    back on the next seed, which is what "insert-missing" has always meant here.

    `sort_order` is the PICKER's order (see `models.AccountType`): the ruled
    seven at 10..70 and the legacy code behind them at 900.

    Returns the number of rows CREATED, so a replay returns 0."""
    tenant_id = _tenant_id()
    created = 0
    for code, name in SEED_ACCOUNT_TYPES:
        _, was_created = models.AccountType.objects.get_or_create(
            tenant_id=tenant_id,
            code=code,
            defaults={
                "name": name,
                "is_system": True,
                "active": True,
                "legacy": code in models.AccountType.LEGACY_CODES,
                "sort_order": seeded_sort_order(code),
            },
        )
        created += int(was_created)
    return created


def seeded_sort_order(code: str) -> int:
    """`BR-CUS-094`'s ruled order for a seeded code, and the legacy slot for
    anything else. Mirrors `customers.0054`'s own `_sort_order_for` — a
    migration is frozen history and cannot import this."""
    codes = [row[0] for row in models.AccountType.SEVEN_CATEGORIES]
    if code in codes:
        return (codes.index(code) + 1) * models.AccountType.SORT_ORDER_STEP
    return models.AccountType.LEGACY_SORT_ORDER


def next_account_type_sort_order(tenant_id: Any) -> int:
    """Where a row the TENANT adds goes: after everything already in the list.

    The seeded seven occupy 10..70 and the legacy code sits at 900, so a first
    tenant-added row lands at 910 — behind the drawn order, in the order the
    tenant created them. This is the answer to the one question the ruling
    opens and it is a stored fact rather than a computed guess, so a later
    reordering screen has something to write to."""
    highest = (
        models.AccountType.objects.filter(tenant_id=tenant_id)
        .order_by("-sort_order")
        .values_list("sort_order", flat=True)
        .first()
    )
    base = highest if highest is not None else 0
    return int(base) + models.AccountType.SORT_ORDER_STEP


def reference_seed_omissions(list_code: str, entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    """OPTIONAL seam (apps/tenancy/seams.py): the entries this module will NOT
    create, and why. Read-only, side-effect free, safe from a `--check` path.

    ⚠ **EMPTY SINCE THE PO RULING OF 2026-09-17, AND THE ENTRY THAT WAS HERE IS
    THE REASON THIS FUNCTION EXISTS AT ALL.** `account_types` was the one
    interesting case: it explained that a per-tenant seed run creating 0 rows
    meant *"already present platform-wide"* and never *"empty"*. That sentence
    is now FALSE — the rows are the tenant's own, a fresh tenant's run creates
    eight, and a run that creates 0 means exactly what it means for every other
    list: this tenant already has them. Leaving the note would have been a
    comment claiming a guarantee that had stopped being true (hard-won law 1).

    The function is KEPT rather than deleted: the seam is declared in
    `apps/tenancy/seams.py` and the next list that needs to explain a 0 writes
    its reason here."""
    return []


def seed_reference_list(list_code: str, entries: list[dict[str, Any]], fixture_version: str) -> int:
    """The tenancy reference-data seeding seam (contract in apps/tenancy/seams.py).

    Customers owns three S8 lists (BR-TEN-031): `account_statuses` (BR-CUS-055,
    tenant-scoped), `account_types` (r5 #12 [D5], platform) and
    `account_subtypes` (BR-CUS-067, tenant-scoped two-level tree — CR-010,
    PO 2026-08-17). Writes land in
    THIS module's tables through THIS module's service layer under the
    caller's `app.tenant_id` context — never a cross-module write (BR-TEN-013).

    Per-list idempotent by natural key (BR-TEN-012): matched on `code`
    case-insensitively. An existing row is LEFT ALONE — a tenant-renamed
    status is never overwritten by a fixture, so a replay writes nothing.

    An EMPTY fixture list falls back to this module's own ratified constants,
    the same posture apps/assets takes for its four catalogs: the platform
    fixture and the rule-cited constant are two copies of one law, pinned
    equal by tests/test_reference_data_completeness.py.

    The one audit row for this write is tenancy's `reference.seeded`
    (BR-TEN-016), written by the caller in the same transaction with the list,
    the fixture version and the count.
    """
    if list_code not in OWNED_REFERENCE_LISTS:
        raise KeyError(f"customers owns no reference list {list_code!r} (BR-TEN-031)")

    if list_code == "account_types":
        # ⚠ TENANT ROWS since the PO ruling of 2026-09-17 (*"utility can get
        # their own account types"*). This branch used to write platform rows
        # with no tenant column at all.
        if not entries:
            return ensure_account_types()
        tenant_id = _tenant_id()
        created = 0
        for code, name in _fixture_rows(entries, list_code, ("code", "name")):
            if models.AccountType.objects.filter(tenant_id=tenant_id, code__iexact=code).exists():
                continue  # BR-TEN-012: an existing row is never overwritten
            models.AccountType.objects.create(
                tenant_id=tenant_id,
                code=code,
                name=name,
                is_system=True,
                legacy=code in models.AccountType.LEGACY_CODES,
                sort_order=seeded_sort_order(code),
            )
            created += 1
        return created

    if list_code == "account_subtypes":
        # BR-CUS-067 (CR-010): tenant rows under the platform tree. The
        # fixture deliberately carries no entries — SEED_ACCOUNT_SUBTYPES is
        # the single ratified source — but the entry path exists so a future
        # fixture bump CAN carry the list without a code change here.
        if not entries:
            return ensure_account_subtypes()
        tenant_id = _tenant_id()
        created = 0
        ensure_account_types()  # the parents are this tenant's own rows now
        for code, name, parent_code in _fixture_rows(
            entries, list_code, ("code", "name", "account_type")
        ):
            parent = models.AccountType.objects.filter(
                tenant_id=tenant_id, code__iexact=parent_code
            ).first()
            if parent is None:
                # A sub-type whose parent type this tenant does not have is a
                # fixture defect — refused, never seeded as an orphan.
                raise errors.SysError(
                    errors.SYS_INTERNAL,
                    message_key="customers.reference_fixture_invalid",
                    params={"list": list_code, "parent": parent_code},
                )
            if models.AccountSubtype.objects.filter(
                tenant_id=tenant_id, code__iexact=code
            ).exists():
                continue  # BR-TEN-012: an existing row is never overwritten
            models.AccountSubtype.objects.create(
                tenant_id=tenant_id,
                account_type=parent,
                code=code,
                name=name,
                is_system=True,
            )
            created += 1
        return created

    if not entries:
        return ensure_account_statuses()
    tenant_id = _tenant_id()
    created = 0
    for code, name, behavior_class in _fixture_rows(
        entries, list_code, ("code", "name", "behavior_class")
    ):
        if behavior_class not in BEHAVIOR_CLASSES:
            # BR-CUS-055 names four classes. A fixture that invents a fifth is
            # refused rather than stored: billing keys off this value, and a
            # class nothing understands is a silent non-billing account.
            raise errors.SysError(
                errors.SYS_INTERNAL,
                message_key="customers.reference_fixture_invalid",
                params={"list": list_code, "behavior_class": behavior_class},
            )
        if models.AccountStatus.objects.filter(tenant_id=tenant_id, code__iexact=code).exists():
            continue
        models.AccountStatus.objects.create(
            tenant_id=tenant_id,
            code=code,
            name=name,
            behavior_class=behavior_class,
            is_system=True,
        )
        created += 1
    return created


# ════════════════════════════════════════════════════════════════════════════
# SLICE 2 — the account write path (US-CUS-003 · S18)
# ════════════════════════════════════════════════════════════════════════════

#: BR-TEN-035: the tenant number series `accounts.account_no` is allocated from.
#: Seeded at provisioning (apps/tenancy SERIES_DEFAULTS "AC-{YYYY}-{00000}"), so
#: unlike metering's premises/unit series this one exists — a missing row is a
#: real fault here, not a documented gap, and it aborts the create.
ACCOUNT_SERIES = core_numbering.ACCOUNT
#: BR-TEN-035 — CR-030 W0. The `customer` series, the catalogue's twenty-fourth.
CUSTOMER_SERIES = core_numbering.CUSTOMER

#: `pg_advisory_xact_lock` classid for BR-CUS-017. A stable int4 derived from
#: the rule id so the namespace is self-describing in `pg_locks` and cannot
#: collide with another rule's lock by accident.
UNIT_ACCOUNT_LOCK_NAMESPACE = int.from_bytes(
    hashlib.blake2b(b"BR-CUS-017", digest_size=4).digest(), "big", signed=True
)

#: Fields a client may set at CREATE. Everything outside this set is refused
#: with a reason (see `_reject_unknown`) rather than silently dropped — a
#: dropped field is a preference the user believes they saved.
CREATE_FIELDS: frozenset[str] = frozenset(
    {
        "unit_id",
        "account_type",
        "account_subtype",
        "status",
        "opened_at",
        "autopay",
        "tax_exempt",
        "tax_exempt_ref",
        "tax_exempt_expires",
        # ── CR-122-BRC06 · a discount CLAIM (PO 2026-09-19) ─────────────────
        # Three of the six seeded discounts need a PERSON to apply — senior,
        # CAP/low-income and veteran — and a move-in had nowhere to say so.
        # ⚠ **RECORDED, NEVER ACTED ON.** No pricing path reads these: a claim
        # is not a grant (`proof_before_first_reduction` defaults true, and
        # `eligibility_rule` has no evaluator), and it never gates service
        # (B18 §5.3.4, *"never blocks service — only the discount"*). Declared
        # here rather than on the move-in alone so S18 and S19 cannot drift,
        # exactly as `deposit` below is. See `models.Account`.
        "eligibility_claimed",
        "eligibility_note",
        "preferred_language",
        # BR-CUS-028's capture set, BUILT 2026-08-31 (CR-052 task 14, migration
        # `customers 0034`). BR-BIL-036 makes print the FLOOR and these two the
        # channels elected ON TOP, so neither can switch a bill's print row off
        # — see the columns' own docstring. Both default False: not electing is
        # the safe answer and the one every account in the product carries.
        "paperless",
        "sms_reminders",
        "contact",
        "addresses",
        # EP-TEN-09 / US-SHL-015: the tenant's OWN fields on this account.
        # Validated by tenancy (the registry owner), never by a copy here.
        "custom_data",
        # `DEF-CUS-9170` (CR-161-BRC10 W3) — the utility's own SERVICE
        # AGREEMENT fields, typed once on the unit step and written on every
        # agreement this call opens. Not an account column: read only by
        # `_validate_service_custom_data`, never by the account write.
        "service_custom_data",
        # ── CR-094-BRC01 wave H — THE DEPOSIT, ON BOTH COUNTER DOORS ────────
        # PO ruling 2026-09-12: *"(a) It is one concept — money held against an
        # account — and building it four times would give four behaviours."*
        # It is declared HERE rather than twice, so `MOVE_IN_FIELDS` — which is
        # `CREATE_FIELDS` minus `unit_id` — gains it in the same line and S18
        # and S19 cannot drift apart. `apps/customers/deposit.py` owns the
        # vocabulary, the validation and the handover; this entry is only the
        # permission to send it. POPPED before the account write, exactly as
        # `initial_reads` is: no key that is not an account column reaches it.
        "deposit",
        # ── CR-056 W3 tasks 15 and 16 — WHO this account belongs to ─────────
        # Until 2026-08-31 an account opened at the counter had NO way to say
        # whose it was: `link_customer` ran only inside an import, so S18 left
        # the CUSTOMER # column blank on every account it created (CR-056 §4).
        # The block is `{customer_id?, display_name?, kind?, external_ref?,
        # identity?}` and every key in it is optional — an account may still be
        # opened with no customer at all, exactly as every account created
        # before the entity existed has none.
        "customer",
    }
)

#: Fields a client may PATCH. `unit_id` is absent on purpose: an account
#: belongs to exactly ONE unit (BR-CUS-017) and re-homing it is the move-out →
#: move-in pair (US-CUS-004/005), never an edit.
PATCH_FIELDS: frozenset[str] = frozenset(
    {
        "account_subtype",
        "status",
        "opened_at",
        "autopay",
        "tax_exempt",
        "tax_exempt_ref",
        "tax_exempt_expires",
        "preferred_language",
        # See CREATE_FIELDS — a preference a customer can state at sign-up is
        # one they can change afterwards, and BR-CUS-028's whole subject is a
        # preference (a customer who goes paperless in March cannot be told to
        # close the account and open a new one).
        "paperless",
        "sms_reminders",
        "custom_data",
        # `DEF-CUS-9820` — PO ruling 2026-10-06 D4 (a), verbatim: *"Yes: add an
        # editable "PO on bills" field to the account's Billing preferences.
        # Bills drafted after the change print the new PO; bills already
        # issued keep the old one"*. A school's PO expires each year; the
        # column was written only by the move-in (CR-171 P1.01). Issued bills
        # keep theirs because a bill prints what was STAMPED at assembly
        # (BR-BIL-030, hard rule 4) — nothing here touches an invoice.
        "po_number",
    }
)

#: `accounts.po_number`'s length — the move-in's own bound
#: (`move_in_people`, `_text(raw.get("po_number"), 60)`), so one column does not
#: acquire two limits. The move-in trims to it; an EDIT refuses past it, by name,
#: because a clerk correcting a PO must not have the end of it dropped silently.
PO_NUMBER_MAX = 60

#: Refused inputs, each with the rule that says why. Answering "unknown field"
#: for these would hide a real answer: the field EXISTS, and something other
#: than this request is entitled to write it.
REFUSED_FIELDS: dict[str, tuple[str, str]] = {
    # column exists, but the value is derived/owned elsewhere
    "kind": (
        "BR-CUS-068",
        "regular is the only kind this path writes; a MASTER account is created "
        "through POST /accounts/master (create_master_account), never by naming "
        "the kind on an ordinary create or edit",
    ),
    # ⚠ **`DEF-CUS-5127`'s SECOND NAME, AND THE ONE WITH NO RULE BEHIND IT.**
    # `account_type` is a real column — `BR-CUS-012` names it first in the
    # account attribute set — and a PATCH naming it answered *"unknown field"*,
    # telling a clerk correcting a miscategorised account that the field does
    # not exist. It now answers by name.
    #
    # ⚠ **THE REASON SAYS WHAT IS TRUE AND NOT WHAT WOULD SOUND FINISHED.** No
    # rule in this repository states that the consumer category is create-only
    # or how it may be changed, and inventing one to make this entry read like
    # its neighbours would be hard-won law 1 in its purest form — a refusal
    # citing a guarantee nobody signed. `OQ-CUS-12356` carries the question; the
    # refusal stands meanwhile because the door has no validated path for it,
    # not because a rule closed it.
    "account_type": (
        "BR-CUS-012 · OQ-CUS-12356",
        "the platform consumer category is set when the account is opened. No rule states "
        "how it may be changed afterwards and no door validates such a change — the "
        "sub-type tree hangs off it (BR-CUS-067) and nothing re-checks the pair. "
        "OQ-CUS-12356 is open; until it is ruled the category is corrected by opening the "
        "account against the right one",
    ),
    "account_no": ("BR-TEN-035", "allocated from the tenant number series"),
    "balance": ("BR-CUS-015", "cached AR figure — the ledger is the source of truth"),
    "credit_tier": ("BR-CUS-058", "COMPUTED from payment history — there is no input path"),
    "currency": ("BR-TEN-021", "one tenant, one currency — taken from the tenant"),
    "deposit_on_file": ("BR-CUS-023", "a LOOKUP from the plan deposit schedule (US-CUS-007)"),
    "deposit_received_on": ("BR-CUS-050", "written by the deposit path (US-CUS-007/023)"),
    # `DEF-CUS-9521` (PO 2026-10-04, *"(c) Let the clerk pick the size on the
    # Deposit step."*) — the size a clerk picked because no meter was fitted.
    # Written ONLY by `deposit.take()` inside the creating transaction, and read
    # back by the first bill, so an edit must never move it.
    "deposit_size_class": (
        "BR-RAT-020",
        "picked on the Deposit step when no meter is fitted (DEF-CUS-9521); the first bill reads it",
    ),
    "deposit_size_picked_at": ("BR-RAT-020", "stamped by the Deposit step with the size pick"),
    "deposit_size_picked_by": ("BR-RAT-020", "the person who picked the size on the Deposit step"),
    "bad_address": ("BR-PAY-018", "set by returned-mail handling, not by an edit"),
    "nsf_count": ("BR-PAY-013", "counted by payments, not entered"),
    "closed_at": ("BR-CUS-030", "closing an account is the Move-Out flow (US-CUS-005)"),
    # ⚠ **THIS REASON SAID "never" UNTIL 2026-09-13 AND IT WAS NO LONGER TRUE.**
    # `BR-CUS-1047` (PO ruling 2026-09-12, option (a) on `OQ-CUS-1769`) NARROWS
    # `BR-CUS-017`: an account MAY be re-pointed at another unit as a
    # CORRECTION. So a refusal that tells a clerk the unit can never change is
    # now the stale-reason failure hard-won law 1 names, and `paperless` and
    # `sms_reminders` left this map for exactly that (see below). It stays
    # refused HERE — an edit is still the wrong door — and now it SAYS WHICH
    # DOOR IS RIGHT, which is the whole difference between a refusal and a dead
    # end.
    "unit_id": (
        "BR-CUS-017 · BR-CUS-1047",
        "an account belongs to exactly ONE unit, and an edit is not how it moves. A "
        "customer who MOVED leaves by move-out and arrives by move-in (US-CUS-004/005) — "
        "the bills, meters and reads belong to the unit and must not follow a person. A "
        "record that named the WRONG unit is corrected at "
        "POST /accounts/{id}/correct-unit (BR-CUS-1047): a reason from a fixed list, a "
        "supervisor's approval, effective today, issued bills untouched",
    ),
    # ⚠ **`unit` AS WELL AS `unit_id`, AND THE SPELLING IS THE WHOLE DEFECT
    # (`DEF-CUS-5127`).** `_reject_unknown` matches PAYLOAD KEYS, and the
    # `accounts` relation's Django field name is `unit` while its payload key is
    # `unit_id`. A caller sending `unit` — which is what the model, the admin
    # and `Account._meta.concrete_fields` all call it — was told the field DOES
    # NOT EXIST, on a real column, and then read a promise in this map's own
    # docstring that it would be told why. Both spellings now answer the same.
    "unit": (
        "BR-CUS-017 · BR-CUS-1047",
        "same column as `unit_id` under its Django field name — send neither. A move is "
        "move-out → move-in; a wrong unit is POST /accounts/{id}/correct-unit",
    ),
    # ⚠ `paperless` and `sms_reminders` LEFT THIS MAP ON 2026-08-31 (CR-052 task
    # 14). They read "PROPOSED-SCHEMA column, not built" and are now built
    # (migration `customers 0034`) and WRITABLE — both are in CREATE_FIELDS and
    # PATCH_FIELDS above. A refusal whose reason has expired is hard-won law 1
    # in its second form, so the entries are removed rather than reworded.
    # `template_override_id` takes their place here for the opposite reason: the
    # column exists and this door is not the one entitled to write it.
    "template_override_id": (
        "BR-BIL-025",
        "the column exists (migration 0034) and no door assigns a bill template to "
        "an account yet — the template catalogue is billing's surface (S8 Templates) "
        "and assigning one per account belongs there, not on an account edit. Until "
        "that lands the chain resolves category default → fallback, which is what "
        "every tenant with one template already gets (DEF-2701)",
    ),
    # story-§5 PROPOSED-SCHEMA columns that slice 1 deliberately did not build
    "budget_billing": ("BR-CUS-028", "PROPOSED-SCHEMA column, not built (US-CUS-003 §5)"),
    "statement_language": ("BR-CUS-028", "PROPOSED-SCHEMA column, not built (US-CUS-003 §5)"),
    "portal_enabled": ("BR-CUS-012", "PROPOSED-SCHEMA column, not built (US-CUS-006 §5)"),
    "autopay_method_id": ("BR-CUS-059", "PROPOSED-SCHEMA column, not built (US-CUS-006 §5)"),
    "deposit_election": ("BR-CUS-023", "PROPOSED-SCHEMA column, not built (US-CUS-007 §5)"),
    "deposit_waive_reason_id": ("BR-CUS-023", "PROPOSED-SCHEMA column, not built"),
    # ⚠ **BOTH ENTRIES CHANGED THEIR REASON ON 2026-09-20 AND NEITHER LEFT THIS
    # LIST** (PO ruling of that date, option A — the column is BUILT, migration
    # `customers/0058`). This is `final_reads`' shape exactly: the field is
    # accepted on the ONE door that owns the act and stays refused on every
    # other, with the TRUE reason rather than a stale one (hard-won law 1 — a
    # stale reason is a stale claim).
    #   · `reason` is in MOVE_OUT_FIELDS, so `_reject_unknown` passes it THERE
    #     and this entry guards `POST /accounts`, the import, and every PATCH.
    #   · `close_reason` — the COLUMN's own name — is refused everywhere with no
    #     exception at all. Why a tenancy ended is settled by the act that ends
    #     it; letting an edit door set it would make the reason correctable
    #     while the close it explains is immutable (hard rule 4), which is
    #     `OQ-CUS-12513` and is OPEN.
    "close_reason": (
        "BR-CUS-030",
        "the move-out is the only act that may say why a tenancy ended — send `reason` to "
        "POST /accounts/{id}/move-out; correcting one afterwards is OQ-CUS-12513 and is open",
    ),
    "reason": (
        "BR-CUS-030",
        "the close reason is collected on the MOVE-OUT flow only, where it lands in "
        "`accounts.close_reason` — no other door ends a tenancy, so none may say why one ended",
    ),
    "bill_delivery_day": ("BR-CUS-060", "DROPPED — cycles decide bill dates"),
    # S19/S20 wizard fields whose destination is another module or an unbuilt
    # table. Each names the rule that owns it — a move-out that accepted a
    # refund method it can never execute would be the worst kind of success.
    "bill_from": ("BR-CUS-022", "the move-in/next-cycle option set is PROPOSED and has no column"),
    # ⚠ AMENDED 2026-08-26 (CR-038 W9): the MOVE-OUT door now ACCEPTS
    # `final_reads` (it is in MOVE_OUT_FIELDS, so `_reject_unknown` passes it
    # there) and routes them through metering's event door — BR-CUS-021
    # honoured, not bypassed. This entry now guards every OTHER door, where
    # the field stays refused with the true reason.
    "final_reads": (
        "BR-CUS-021",
        "final reads are captured on the MOVE-OUT flow only, committed via the "
        "metering event door (BR-MET-128) — no other door accepts them",
    ),
    "deposit_disposition": ("BR-CUS-025", "apply-first needs the final bill (billing W3)"),
    "refund_method": ("BR-CUS-025", "refunds execute through payments `refunds` — no tables"),
    "deposit_interest_accrued": ("BR-CUS-057", "accrual engine is US-CUS-023 §7, not built"),
    "carry_deposit_from": ("BR-CUS-024", "carry-forward rides `customer_accounts` (BR-CUS-054)"),
    # whole tables that do not exist
    "plan": ("BR-CUS-029", "the account plan snapshot has no table (account_plan_assignments)"),
    "rate_plan_id": ("BR-CUS-029", "the account plan snapshot has no table"),
    "plan_version": ("BR-CUS-029", "the account plan snapshot has no table"),
    # CORRECTED 2026-08-11 (US-CUS-019 lane): these two used to read "the
    # first-class customer entity has no table". It HAS one now (B2 r9 #1,
    # migration 0005) — but `POST /accounts` still has no linking path, because
    # S18 step 1's advisory duplicate check + "Use existing customer" is
    # US-CUS-003 TC-5 and was not built here. The refusal stands; the REASON
    # is now the true one (hard-won law 1 — a stale reason is a stale claim).
    "customer": ("BR-CUS-054", "linking a customer at create is US-CUS-003 step 1, not built"),
    "customer_id": ("BR-CUS-054", "linking a customer at create is US-CUS-003 step 1, not built"),
    "capacity_units": ("BR-CUS-029", "`account_capacities` has no DDL in any signed document"),
    # ⚠ AMENDED 2026-08-26 (CR-038 W9): the MOVE-IN door now ACCEPTS
    # `initial_reads` (it is in MOVE_IN_FIELDS) and routes them through
    # metering's event door — BR-CUS-021's unbuilt half, built. This entry now
    # guards every OTHER door (plain create included: an S18 create is not a
    # lifecycle event and BR-MET-128 names no context for it).
    "initial_reads": (
        "BR-CUS-021",
        "initial reads are captured on the MOVE-IN flow only, committed via the "
        "metering event door (BR-MET-128) — no other door accepts them",
    ),
}

#: BR-CUS-068 — the accounts.kind vocabulary. `regular` is every account this
#: module wrote before 2026-08-22; `master` is the owner/manager's account over
#: the premises' common-area units (PO ruling 2026-08-22, OQ-314 second half).
ACCOUNT_KIND_REGULAR = "regular"
ACCOUNT_KIND_MASTER = "master"

#: BR-CUS-068 — the POST /accounts/master payload. `unit_id` and `status` are
#: ABSENT on purpose: the master account's anchor unit is DERIVED (the premises'
#: first common-area unit, deterministic) and the account is created ACTIVE and
#: attached in one call — an unattached master is exactly the half-built state
#: the ruling closed. `unit_ids` is the OPTIONAL explicit attachment list; when
#: absent, every common-area unit of the premises is attached.
MASTER_CREATE_FIELDS: frozenset[str] = frozenset(
    {
        "premises_id",
        "unit_ids",
        "account_type",
        "account_subtype",
        "opened_at",
        "contact",
        "addresses",
        "custom_data",
        # ── CR-056 W3 task 17 — the Master Account door links its customer ──
        # CR-056 §4 measured the state this closes, verbatim: *"**Every Master
        # Account in the product has a blank customer column**."* Under the
        # 2026-08-31 ruling a Master Account IS the owner's account at an
        # address, so the one thing it must be able to say is WHOSE it is.
        "customer",
        # ── `DEF-CUS-8020` — THE FOUR BILLING PREFERENCES ────────────────────
        #
        # ⛔ **THE OMISSION WAS NEVER A RULING, AND THAT IS WHY THEY ARE ADDED
        # RATHER THAN REFUSED.** A boundary in this module is written DOWN: a
        # field this door deliberately will not take gets a `REFUSED_FIELDS`
        # entry with its rule id and a sentence saying why (`kind`,
        # `account_no`, `balance`, `credit_tier`, `deposit_on_file` …), so the
        # caller learns WHY rather than being told the field does not exist.
        # **All four of these are in neither set** — they fell through to the
        # generic *"unknown field"*, which is the answer this module gives for
        # a field that does not exist at all. Three further facts, each checked
        # rather than assumed: the columns exist on `models.Account`
        # (`0011_cr014_group3`), the ordinary door has permitted all four since
        # the module was built (`CREATE_FIELDS`, above), and no rule anywhere
        # in `04-docs` states that a master account may not be on autopay or
        # hold a tax exemption. The set was written in `CR-056` as the minimal
        # derived-anchor payload and has GROWN as callers needed real fields —
        # `customer` joined it in W3 task 17 for exactly this reason.
        #
        # ⚠ **AND THE SCREEN ASKS FOR THEM ON AN APPROVED DRAWING.**
        # `step4-charges.png` draws a *Billing preferences* panel — Autopay,
        # Tax exempt, Certificate number, Exemption expires — and
        # `CR-150-BRC09` §2 lists *billing preferences* as step 4's content.
        # Under B14 rules 41/42 the drawing decides what the screen CONTAINS,
        # so the opposite fix (stop asking) would have needed a PO ruling to
        # reverse an approved drawing. Nothing needed reversing.
        #
        # ⚠⚠ **PERMITTING THEM IS ONLY HALF THE FIX — SEE `create_master_account`,
        # WHICH NOW WRITES THEM.** `DEF-1661` is the recorded cost of doing only
        # this half: five columns declared lawful in an allow list, accepted by
        # `_reject_unknown`, written by nothing, and 1,213 migrated accounts
        # imported $0.00 of deposits with every test green. A field in this set
        # that no `objects.create()` reads is a preference the user believes
        # they saved.
        "autopay",
        "tax_exempt",
        "tax_exempt_ref",
        "tax_exempt_expires",
        # ⊕ `CR-164-BRC10` / `DEF-CUS-9195` — New Connection step 1's
        # *Communication* panel: the owner's language and the two ticks.
        # Typed, shown and dropped at the commit until now (`DEF-CUS-7863`).
        "preferred_language",
        "paperless",
        "sms_reminders",
    }
)

#: US-CUS-004 §5 — the S19 Move-In payload. `unit_id` is ABSENT on purpose: the
#: chained move-in takes the unit from the OUTGOING account named in the URL
#: (11b §S19), so a unit in the body would be a second, disagreeing source of
#: truth for which room the new tenant is entering. `opened_at` IS the wizard's
#: "Move-in date" (US-CUS-004 §5 maps it to `accounts.opened_at` +
#: `service_agreements.started_on`).
#: ⚠ `initial_reads` joined 2026-08-26 (CR-038 W9 task 3): BR-CUS-021's
#: capture, routed through `seams.commit_event_reads` (event `move_in`) —
#: never written here. Every other door still refuses the field by rule id.
#: ⚠ `service_request_id` joined 2026-09-15 (`CR-094-BRC01`): the application
#: this move-in fulfils, POPPED before the account write and handed to
#: `moves.record_move`. `BR-CUS-080`'s child half — see `moves.MoveRecord
#: .request_id` for why it is written HERE and not at approval.
#: ⚠ `wizard_park_id` joined 2026-09-19 (`CR-122-BRC06`): the DRAFT this
#: move-in was keyed into. POPPED before the account write, and it does exactly
#: two things — the finished record adopts the draft's `MVI-` reference instead
#: of allocating a second one, and the draft row is deleted in the same
#: transaction. It is a client-named id and never a client-named NUMBER: the
#: reference is read off the row the server looks up, tenant-scoped, so a
#: caller cannot dictate what a move-in is filed under.
#: ⚠ `services` joined 2026-09-25 (`BR-CUS-1101`, PO ruling of that date):
#: **which of the unit's services this account takes** — a list of service
#: codes, OPTIONAL, and absent means every service point on the unit, which is
#: what this door did before the field existed. POPPED before the account write
#: for `initial_reads`' reason (`accounts` has no such column) and validated
#: against the unit's own points by `_clean_service_choice`. **No column was
#: added anywhere**: taking a subset is writing fewer `service_agreements` rows.
MOVE_IN_FIELDS: frozenset[str] = frozenset(CREATE_FIELDS - {"unit_id"}) | {
    "initial_reads",
    "field_visit",
    "service_request_id",
    "wizard_park_id",
    "services",
    # CR-171-BRC10 P1.10/P1.11 (lane MVI-IDN) — the people who share the
    # account, the company's own facts and where the bill goes. POPPED before
    # the account write and validated by `move_in_people.pop`.
    "co_owners",
    "company",
    "po_number",
    "bills_go_to",
    # CR-171-BRC10 P2.25 (lane MVI-WIZ-CUST) — the wizard's own uploads, staged
    # before the account exists; POPPED and proved by `move_in_people.pop`.
    "documents",
    # ── CR-171-BRC10 P1.12 / P1.13 (lane MVI-MONEY) — the Fees table and Pay
    # now / Add to bill. On the MOVE-IN only, not `CREATE_FIELDS`: the lines
    # hang off the move RECORD, which only a move-in writes. `move_fees.py`
    # owns the vocabulary; both are POPPED before the account write.
    "fees",
    "payment",
    # CR-171-BRC10 P1.15 — *Autopay from*, discounts to claim, the exemption
    # with its certificate. `move_in_preferences.py` owns all three.
    "autopay_instrument_id",
    "discount_claims",
    "tax_exemption",
    # CR-171-BRC10 P1.20 (lane MVI-FLOW) — the Messaging table's ADDED rows.
    # POPPED before the account write and validated by `move_in_complete.pop`.
    "extra_messages",
    # CR-190-BRC10 — Step 4's per-move-in answer for the two defaults (untick,
    # or another channel). POPPED and validated by `move_in_complete.pop_defaults`.
    "default_messages",
    # CR-181-BRC10 (lane REOPEN) — reopen the returning customer's closed
    # account on THIS unit, and the clerk's choice about what it still owes.
    # POPPED and checked by `move_in_reopen.pop` / `.check`.
    "reopen_account_id",
    "reopen_balance",
}

#: US-CUS-005 §5 — the S20 Move-Out payload. `moved_out_on` is the wizard's
#: "Move-out date"; it lands in `accounts.closed_at` + every open
#: `service_agreements.ended_on`. `closed_at` itself stays a REFUSED field
#: everywhere else, and REFUSED_FIELDS points here (BR-CUS-030).
#: ⚠ `final_reads` joined 2026-08-26 (CR-038 W9 task 4): BR-CUS-021's capture,
#: routed through `seams.commit_event_reads` (event `move_out`).
#: ⚠ `field_visit` joined 2026-09-05 (CR-070 wave P, `US-WRK-039`,
#: `BR-WRK-055`): `{"template_ids": [...]}` — the jobs a clerk ticked on
#: **step 2**, *Date & final reads*. Not step 4: `MOVE_OUT_STEPS[3]` is
#: conditional and renders greyed and *skipped* whenever the account settles,
#: so a control placed there is invisible on the ordinary move-out
#: (`DEF-WRK-3725`).
#: ⚠ `service_request_id` joined 2026-09-15 (`CR-094-BRC01`), for `MOVE_IN_FIELDS`'
#: reason and through the same door.
#: ⚠ `reason` joined 2026-09-20 (PO ruling of that date, option A — decision log
#: *"TEN MOVE-OUT RULINGS IN ONE SITTING"* item 3): **why this tenancy ended**,
#: one of `models.CLOSE_REASONS`, landing in `accounts.close_reason` in the
#: close's own transaction. It had been a REFUSED field since the wizard was
#: built — five options drawn on screen and none stored, which the blueprint's
#: p110 calls *"worse than not asking"*. `close_reason` (the COLUMN's name) is
#: still refused on every door including this one: one spelling in, so a caller
#: cannot set the same fact two ways.
#: ⚠ `wizard_park_id` joined 2026-09-20 (PO ruling of that date, option A —
#: item 9), for `MOVE_IN_FIELDS`' reason and through the same door: the finished
#: record ADOPTS the draft's `MVO-` reference instead of allocating a second,
#: and the draft row is deleted in the same transaction.
MOVE_OUT_FIELDS: frozenset[str] = frozenset(
    {
        "moved_out_on",
        "status",
        "final_reads",
        "field_visit",
        "service_request_id",
        "reason",
        "wizard_park_id",
        # CR-185-BRC10 (coordinator ruling 2026-10-14, *"POST AT COMMIT"*) —
        # the shortfall disposition the clerk chose on step 3. Only
        # `transfer` acts here: the residue then moves to the owner INSIDE
        # this commit, after the final bill is drafted, for what is owed then.
        "shortfall_path",
    }
)

#: CR-030 W1 — the BULK IMPORT's account vocabulary (BR-CUS-046). `CREATE_FIELDS`
#: plus the four a MIGRATION is entitled to and a hand-typed account is not.
#:
#: ⚠ Named `IMPORT_ACCOUNT_FIELDS` and not `IMPORT_FIELDS`, because that name is
#: TAKEN — by the legacy three-step modal's request vocabulary
#: (`{content, filename, cutover_date, skip_errors}`, line ~2210), which CR-030
#: W1 deprecates. Two same-named field sets on one module, one about a REQUEST
#: and one about a ROW, is the kind of collision that reads fine in a diff.
#:
#: ⚠ **THIS WIDENS WHAT A PATH MAY WRITE, ON MONEY FIELDS, AND EACH ENTRY EARNS
#: ITS PLACE SEPARATELY.** The mechanism is the one `move_in` already uses
#: (`_open_account(allowed=…)`) and the reason is the same: a cutover has facts
#: a create does not. It is NOT a hole in `REFUSED_FIELDS` — every other door
#: still refuses all four.
#:
#:   * `deposit_on_file` + `deposit_received_on` — **US-CUS-023 is literally
#:     titled** *"Deposits-on-file import with ORIGINAL receipt dates + interest
#:     accrual start"*. BR-CUS-023 refuses them elsewhere because a deposit is a
#:     LOOKUP from the plan schedule; a migrated deposit was taken years ago
#:     under someone else's schedule, and importing it without its original date
#:     starts interest at cutover and quietly under-pays the customers who have
#:     been with the utility longest (BR-CUS-050/057).
#:   * `closed_at` — a migration brings CLOSED accounts across, and the Accounts
#:     KPI strip counts them (*"CLOSED THIS YEAR 64"*). BR-CUS-030 refuses it
#:     elsewhere because closing a LIVE account is the Move-Out flow rather than
#:     a status flip — which says nothing about an account the old system closed
#:     before we existed.
#:   * `bad_address` — set by returned-mail handling here (BR-PAY-018), and
#:     already true of some rows the day they arrive. Losing it means posting a
#:     first bill to an address the previous utility already knew was dead.
#:
#: ⚠ NOT widened, each still refused for the reason it always had: `balance`
#: (a cache — the opening position arrives as BUCKETS and posts through the
#: ledger), `credit_tier` (computed), `kind` (master accounts have their own
#: door), `nsf_count`, and `currency` (one tenant, one currency — the loader
#: passes the TENANT's, never the file's).
#:   * `external_ref` — **CR-046 C4/C5 · BR-CUS-172.** The utility's OWN
#:     account id. Refused on every other door because an account created by
#:     the S18 wizard has no legacy reference to declare; a migration has one
#:     for every row, and under the 2026-08-27 ruling it is also the MATCH KEY
#:     that stops a corrected re-run duplicating the whole book.
IMPORT_ACCOUNT_FIELDS: frozenset[str] = CREATE_FIELDS | frozenset(
    {"deposit_on_file", "deposit_received_on", "closed_at", "bad_address", "external_ref"}
)

#: ⛔ **CR-046 C4 — WHAT A RE-IMPORT MAY CHANGE ON AN ACCOUNT THAT IS ALREADY
#: ON FILE, AND WHAT IT MAY NEVER TOUCH.**
#:
#: `BR-AST-034`'s posture (*"a re-imported row updates SPEC fields"*) applied to
#: an account, and the exclusions are the whole of the rule:
#:
#:   * **The four `ob_*` buckets and the deposit are ABSENT.** They became
#:     journal entries through the ledger at the first load (GT-16 ❄️), and
#:     hard rule 4 makes a journal entry immutable — a correction is a NEW
#:     entry, never an edited one. A re-import that restated an opening balance
#:     would be a second, unbalanced claim about money already posted.
#:   * **`unit_id` is ABSENT.** An account belongs to exactly ONE unit
#:     (BR-CUS-017) and re-homing it is the move-out → move-in pair, never an
#:     edit — the same reason it is absent from `PATCH_FIELDS`.
#:   * **`account_no` is ABSENT.** It is the key we matched ON; letting a
#:     re-run rewrite it would make the next re-run match nothing.
#:   * **`status` IS present**, because a migration's second cut legitimately
#:     corrects an account the old system had already closed — and it goes
#:     through `_apply_status_change` like every other status move, so nothing
#:     about the transition's own rules is bypassed.
IMPORT_UPDATE_FIELDS: frozenset[str] = frozenset(
    {
        "account_subtype",
        "status",
        "opened_at",
        "closed_at",
        "autopay",
        "tax_exempt",
        "tax_exempt_ref",
        "tax_exempt_expires",
        "bad_address",
        "preferred_language",
        "external_ref",
        "custom_data",
    }
)

CONTACT_FIELDS: frozenset[str] = frozenset(
    # `custom_data` — `DEF-CUS-9168` (CR-161-BRC10 W3): the utility's own
    # contact fields, validated by tenancy through `seams.validate_custom_data`.
    {"full_name", "email", "phone", "dob", "gov_id_last4", "is_primary", "custom_data"}
    # CR-171-BRC10 P1.11 (lane MVI-IDN) — a company's contact person, image 40
    # (`customers/0080`).
    | {"job_title", "contact_by"}
)
#: ⚠ **`line2` JOINED ON 2026-09-23 (`DEF-CUS-6408`), AND `country` DID NOT.**
#: Both have been real columns since `customers 0039` (`DEF-2847`) and this door
#: could set neither — `DEF-CUS-5942` carried that gap honestly. The capture
#: wizard now takes a billing address as a US address, *"full address line,
#: unit, city, zip"* (PO report 2026-09-23), and the UNIT is line 2: an account
#: opened from that request would otherwise lose `Suite 200` at the one door that
#: writes where the bill goes, or have it glued onto line 1, which is assembling
#: an address out of parts `BR-NOT-029` clause (a) forbids. `country` stays out
#: for the reason `mailing_address_for_account` gives: nothing a clerk types
#: supplies it, and the utility's own country is not the customer's.
ADDRESS_FIELDS: frozenset[str] = frozenset(
    # `custom_data` — `DEF-CUS-9169` (CR-161-BRC10 W3): the utility's own
    # mailing-address fields, validated by tenancy, never by a copy here.
    {"kind", "line1", "line2", "city", "state", "postal_code", "custom_data"}
)
#: ── ONE HOME FOR AN ADDRESS — `BR-MET-1161`, PO ruling 2026-09-04 ─────────
#: PO verbatim: *"we are having addresses at one place now - Premises and Units
#: -> then they flow to {Meters, Sub meter, assets} + { accounts} -> from there
#: it flows to Routes and Cycles … so they will also draw addresses from same
#: place that we we can maintain the integrtiy"*.
#:
#: ⚠ **B2 §2 DECLARES TWO VALUES HERE AND THIS ACCEPTS ONE.** The supersession
#: is deliberate and is written out in the decision log of that date rather
#: than edited into B2 in passing. `service` is retired: where the METER is
#: lives on `premises`, and an account reaches it by walking
#: `account → unit → premises`. A second, editable copy on the account is a
#: second answer to *where is this*, and the map, the route sheet, the envelope
#: and the crew's phone would eventually disagree.
#:
#: ⚠ **NOTHING WAS MIGRATED BECAUSE THERE WAS NOTHING TO MIGRATE.** At the time
#: of the ruling: **0** rows of `kind='service'` against 51 `mailing`, and no
#: code path in the product read one — the only hits for the string were this
#: tuple, the validator below, and `selectors.py`'s docstring explaining why the
#: mailing read refuses to fall back to it. This closes a door onto a room
#: nobody had entered; it repairs no data.
#:
#: `mailing` STAYS, and that is the rule's own exception 1: where the BILL goes
#: is a different fact from where the meter is, for every landlord, every
#: managing agent and everyone who has moved.
ADDRESS_KINDS: tuple[str, ...] = ("mailing",)  # B2 §2 SUPERSEDED at its second value

#: Retired values, kept BY NAME so the refusal can say what happened. A value
#: that merely vanished from the tuple above would be refused as an "unknown
#: lookup", which tells a clerk holding a real service address nothing about
#: where to put it.
ADDRESS_KINDS_RETIRED: tuple[str, ...] = ("service",)

_MAX_TEXT = 500


# ── shared plumbing (same shape as apps/metering/services.py) ───────────────
def _audit(
    actor: Any,
    action: str,
    entity_id: Any,
    *,
    entity_type: str = "account",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """CLAUDE.md rule 7 — an account is a money-adjacent surface, so every
    write here lands its who/when/before→after row through BE-03."""
    core_audit.write_row(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
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


def _payload_dict(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="customers.payload_not_object")
    return payload


def _text(value: Any, limit: int = _MAX_TEXT) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned[:limit] if cleaned else None


def _date(value: Any, field: str, fe: list[dict[str, Any]]) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        fe.append(_field_error(field, errors.VAL_FORMAT, "customers.account.date_invalid"))
        return None


def _as_date(value: Any) -> date | None:
    """A date a SEAM handed us — already a `date` in practice, coerced from ISO
    text so a second caller cannot produce a different reading of one day.

    Unlike `_date` above this takes no `field_errors` list: it reads an argument
    a sibling module resolved and passed, not a cell a human typed, so a
    malformed value is a wiring fault and raises rather than landing under a
    form input that does not exist. `None` stays `None` — absence is a state the
    caller decides about (see `_inheritance_started_on`), never one this
    function fills in.

    ⚠ **NO CLOCK. BR-TEN-043** — nothing here may become `date.today()`.
    """
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def _decimal_or_none(value: Any, field: str, fe: list[dict[str, Any]]) -> Any:
    """`DEF-1661` — a money cell off an import row, or a NAMED refusal.

    ⚠ **HARD RULE 2 — `Decimal(str(value))`, NEVER `float`.** The cell arrives
    as text off a CSV and a float round-trip is how `150.00` becomes
    `149.999999999999997`; the column is `NUMERIC(18,6)` and B4.4 rounds only
    at finalisation, so nothing here quantises either.

    ⚠ **A NEGATIVE DEPOSIT IS REFUSED, not stored.** A deposit is money the
    utility HOLDS; a negative one is a typo that would show as a credit the
    customer never gave. The four `ob_*` buckets take a negative on purpose
    (BR-CUS-061, an opening credit) and they do not come through here.

    ⚠ **Blank is `None`, not `0`.** `deposit_on_file` defaults to 0 on the
    column, and *"no deposit column in the file"* and *"a deposit of zero"* are
    the same fact for money — but writing `None` lets the model default stand
    rather than this function asserting a figure it was not given.
    """
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError, ArithmeticError):
        fe.append(_field_error(field, errors.VAL_FORMAT, "customers.account.amount_invalid"))
        return None
    if amount < 0:
        fe.append(
            _field_error(
                field,
                errors.VAL_RANGE,
                "customers.account.amount_negative",
                br_ref="BR-CUS-023",
                value=str(amount),
            )
        )
        return None
    return amount


def _reject_unknown(payload: dict[str, Any], allowed: frozenset[str]) -> None:
    """Every key is either allowed, refused-with-a-reason, or unknown.

    A field that names a real column or a real rule gets that rule back, so the
    caller learns WHY rather than being told the field does not exist."""
    fe: list[dict[str, Any]] = []
    for field in payload:
        if field in allowed:
            continue
        if field in REFUSED_FIELDS:
            br_ref, reason = REFUSED_FIELDS[field]
            fe.append(
                _field_error(
                    field,
                    errors.VAL_FORMAT,
                    "customers.account.field_not_writable",
                    br_ref=br_ref,
                    reason=reason,
                )
            )
        else:
            fe.append(_field_error(field, errors.VAL_FORMAT, "customers.account.unknown_field"))
    _refuse_fields(fe)


# ── lookups the account row points at ───────────────────────────────────────
def _resolve_status(value: Any, fe: list[dict[str, Any]], *, field: str = "status") -> Any:
    """BR-CUS-016/055: the stored status comes from the tenant's own
    `account_statuses` list, by code or id. An inactive row is refused — a
    deactivated status is one the tenant has retired from use."""
    tenant_id = _tenant_id()
    qs = models.AccountStatus.objects.filter(tenant_id=tenant_id, active=True)
    row = qs.filter(code__iexact=str(value)).first()
    if row is None:
        try:
            row = qs.filter(pk=UUID(str(value))).first()
        except (ValueError, AttributeError, TypeError):
            row = None
    if row is None:
        fe.append(
            _field_error(
                field,
                errors.VAL_UNKNOWN_LOOKUP,
                "customers.account.status_unknown",
                value=str(value),
            )
        )
    return row


def _resolve_account_type(
    value: Any, fe: list[dict[str, Any]], *, allow_legacy: bool = False
) -> Any:
    """BR-CUS-012 + r5 #12 [D5]: the PLATFORM consumer category.

    ⛔ **`legacy` IS REFUSED HERE BY DEFAULT — DEF-736.** BR-CUS-094 (PO
    2026-08-24) retires `government` with the clause *"it stops being
    selectable on any form"*, and until this fix that clause was enforced on
    ONE door: `service_request_service.set_customer_category`'s
    `customers.serviceRequest.categoryIsLegacy`. `POST /accounts` and
    `POST /accounts/{id}/move-in` both resolve the category HERE, and this
    function filtered on `active=True` and never read `legacy` — so an API
    client (and the S18/S19 screens until DEF-684 closed their pickers) wrote a
    retired code onto a brand-new account and nothing objected.

    ⚠ **`allow_legacy=True` IS NOT A BACK DOOR — IT IS THE CUTOVER IMPORT, AND
    IT IS REQUIRED.** `apps/customers/account_import.py` creates account rows
    for customers who LAWFULLY carry `government`: BR-CUS-094 is explicit that
    every existing record keeps its code and keeps billing, and re-pointing is
    *"a human act per record"* through US-CUS-020's value-mapping step. A
    blanket refusal here would fail the very migration BR-CUS-094 was written
    to make painless — which is why DEF-736's own row says, in capitals, DO NOT
    close this by refusing every legacy code. The exemption is passed
    explicitly by `_commit_import_row` and by nothing else, so a new writer has
    to ASK for it rather than inherit it.

    `legacy` is a THIRD axis (see `models.AccountType`): `active=False` retires
    a code from every surface, `legacy=True` keeps it working everywhere it
    already works and only closes the picker. So the row is still RESOLVED —
    the refusal is a field error about choosing it, not a claim that the code
    does not exist.
    """
    # ⚠ TENANT-SCOPED SINCE THE PO RULING OF 2026-09-17. Before it, a code was
    # a platform-wide fact and an unscoped read was defensible; now two tenants
    # may lawfully hold one code for different things, so an unscoped read could
    # resolve an account onto ANOTHER utility's row. Under RLS the policy scopes
    # it too — this filter is what makes the sqlite test suite test the same
    # thing production does (CLAUDE.md law 14's other half).
    qs = models.AccountType.objects.filter(tenant_id=_tenant_id(), active=True)
    row = qs.filter(code__iexact=str(value)).first()
    if row is None:
        try:
            row = qs.filter(pk=UUID(str(value))).first()
        except (ValueError, AttributeError, TypeError):
            row = None
    if row is None:
        fe.append(
            _field_error(
                "account_type",
                errors.VAL_UNKNOWN_LOOKUP,
                "customers.account.type_unknown",
                value=str(value),
            )
        )
        return row
    if getattr(row, "legacy", False) and not allow_legacy:
        fe.append(
            _field_error(
                "account_type",
                errors.VAL_UNKNOWN_LOOKUP,
                "customers.account.type_is_legacy",
                value=str(row.code),
            )
        )
        return None
    return row


def _resolve_account_subtype(value: Any, fe: list[dict[str, Any]]) -> Any:
    if value in (None, ""):
        return None
    qs = models.AccountSubtype.objects.filter(tenant_id=_tenant_id(), active=True)
    row = qs.filter(code__iexact=str(value)).first()
    if row is None:
        try:
            row = qs.filter(pk=UUID(str(value))).first()
        except (ValueError, AttributeError, TypeError):
            row = None
    if row is None:
        fe.append(
            _field_error(
                "account_subtype",
                errors.VAL_UNKNOWN_LOOKUP,
                "customers.account.subtype_unknown",
                value=str(value),
            )
        )
    return row


def is_occupying(status: models.AccountStatus) -> bool:
    """BR-CUS-017/BR-MET-036 — see OCCUPYING_BEHAVIOR_CLASSES."""
    return status.behavior_class in OCCUPYING_BEHAVIOR_CLASSES


# ── BR-CUS-017: mutual exclusion on the (tenant, unit) scope ────────────────
def unit_lock_key(tenant_id: Any, unit_id: Any) -> int:
    """The int4 `pg_advisory_xact_lock` key for one (tenant, unit) scope.

    Stable across processes on purpose — `hash()` is salted per interpreter and
    two web workers must agree on the key or the lock guards nothing. A digest
    collision makes two different units share one lock: they serialize
    needlessly, which is slow and still CORRECT; there is no collision that
    lets two accounts through.
    """
    digest = hashlib.blake2b(f"{tenant_id}:{unit_id}".encode(), digest_size=4).digest()
    return int.from_bytes(digest, "big", signed=True)


def lock_unit_scope(unit_id: Any) -> bool:
    """Serialize every occupancy decision for one unit. Returns True when a
    real lock was taken.

    MUST be called inside `transaction.atomic()`: the lock is transaction-
    scoped, so it releases exactly when the deciding transaction ends — commit
    or rollback, no leak, no unlock call to forget.

    On a backend without advisory locks (the sqlite test tier) this is a
    documented no-op and BR-CUS-017 degrades to the check alone, which a
    concurrent writer can still race. PostgreSQL 16 is the deployment target
    (CLAUDE.md) and the concurrency proof runs there.
    """
    # ⚠ `CR-056` W1 / `BR-CUS-1012` — an account that names NO unit has no unit
    # scope to serialize. `unit_lock_key(tenant, None)` would hash the string
    # "None" and hand every unit-less account in the tenant THE SAME lock, so two
    # unrelated addresses would serialize against each other for no reason.
    if unit_id in (None, ""):
        return False
    if connection.vendor != "postgresql":
        return False
    if not transaction.get_connection().in_atomic_block:  # pragma: no cover - guarded by callers
        raise errors.SysError(
            errors.SYS_INTERNAL, message_key="customers.account.lock_outside_transaction"
        )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s, %s)",
            [UNIT_ACCOUNT_LOCK_NAMESPACE, unit_lock_key(_tenant_id(), unit_id)],
        )
    return True


def _refuse_if_unit_occupied(unit_id: Any, *, exclude_id: Any = None) -> None:
    """BR-CUS-017. Call ONLY after `lock_unit_scope()` — before the lock this
    read is a check-then-act race, which is the whole defect T5-15 step 4
    describes.

    The refusal NAMES the existing account, because that is what the IS-7
    failed state has to render (T5-15 step 3).
    """
    from apps.customers import selectors

    # `CR-056` W1 / `BR-CUS-1012` — nothing occupies "no unit". The read below
    # already answers empty for a NULL id; this says so at the door too, because
    # a caller reading only this function must not conclude that a unit-less
    # account was checked and passed.
    if unit_id in (None, ""):
        return
    qs = selectors.occupying_accounts_for_unit(unit_id, lock=True)
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    existing = qs.order_by("created_at", "id").first()
    if existing is None:
        return
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-CUS-017",
        message_key="customers.account.unit_already_occupied",
        params={
            "unit_id": str(unit_id),
            "account_id": str(existing.id),
            "account_no": existing.account_no,
            "status": existing.status.code,
        },
    )


# ── BR-CUS-020: which units the create path will accept ─────────────────────
def _eligible_unit(unit_id: Any, fe: list[dict[str, Any]]) -> Any:
    """BR-CUS-020 (CONFIRMED): "unit pickers offer only vacant or reserved
    units; occupied units never appear" — and a forged submit is refused here,
    because a picker that hides a row is a UI convenience, never enforcement.

    "Reserved" has NO representation in the schema: US-MET-002 §5 forbids a
    stored unit status and metering derives exactly {vacant, occupied} plus
    `inactive` for a soft-deleted unit (BR-MET-036). So "vacant or reserved"
    reduces, on the data that exists, to NOT OCCUPIED — which is the same
    predicate BR-CUS-017 enforces, checked again under the lock by the caller.
    A DEACTIVATED unit is refused too: it is neither vacant nor reserved, and
    BR-MET-047 blocks deactivation precisely while an account lives on it.
    REPORTED: if `reserved` ever becomes a real unit state, this is where it
    lands.
    """
    if unit_id in (None, ""):
        fe.append(_field_error("unit_id", errors.VAL_REQUIRED, "customers.account.unit_required"))
        return None
    unit = seams.unit_row(unit_id)  # 404-never-403 for a cross-tenant id (HR-1)
    if getattr(unit, "deleted_at", None) is not None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-020",
            message_key="customers.account.unit_not_eligible",
            params={"unit_id": str(unit_id), "reason": "deactivated"},
        )
    return unit


#: **BR-MET-040 IS NARROWED FOR A COMMON AREA, AND THIS CONSTANT IS THE
#: NARROWING — PO ruling 2026-09-21, verbatim: *"common area dont need rate plan
#: as of now; make this optional"*.**
#:
#: ⚠ **THE PO'S WORDS *"AS OF NOW"* ARE THEIRS AND ARE KEPT, AND THIS CONSTANT
#: IS WHAT KEEPS THEM.** The ruling is a deliberate, DATED position, not a
#: permanent property of common areas, so it is written as a condition that can
#: be READ and CHANGED rather than as a deletion of the rule. Setting this back
#: to `True` restores `BR-MET-040` over common areas in ONE line in ONE place,
#: and `test_br_met_040_common_area.py` asserts both sides of it.
#:
#: ⛔ **IT NARROWS NOTHING ELSE. THE RULE GOES ON HOLDING FOR A DWELLING**, on
#: every path it held before — `activate_account`, `update_account`'s status
#: change into a billing class, S18 `create_account` and S19 `move_in` with an
#: occupying status. The only unit this constant can reach is one carrying
#: `units.is_common_area = True`.
#:
#: ⚠ **WHAT MAKES IT SAFE RATHER THAN RECKLESS IS VERIFIED, NOT ASSUMED** (the
#: same guarantee `require_plan=False` has rested on since `CR-047`):
#: `apps/billing/gather.gather_account` raises `GATHER_NO_PLAN` for ANY unit
#: with no `rate_plan_id`, `runs.STAGE_BY_REASON` files it on the
#: `resolve-subscription` exception tab and `runs.NOT_RETRYABLE_HERE` marks it
#: not-retryable. **An unplanned unit can EXIST and can never be BILLED.**
#: `test_br_met_040_common_area.py::test_the_bill_run_still_refuses_an_unplanned_unit`
#: holds that, because if it ever stops being true this ruling needs re-putting.
COMMON_AREA_REQUIRES_A_PLAN = False


def _unit_is_a_common_area(unit: Any) -> bool:
    """`units.is_common_area` — `BR-MET-101`'s *a common area IS a unit with a
    flag*, read through whatever row object the caller was handed.

    ⚠ **A ROW THAT CANNOT ANSWER IS TREATED AS A DWELLING**, which is the
    fail-closed direction: the plan requirement then still fires. This function
    is reached from three modules' seams and the cost of guessing *common area*
    on an unreadable row is a dwelling going out unpriced."""
    return bool(getattr(unit, "is_common_area", False))


def _require_plan_on_unit(unit: Any) -> None:
    """BR-MET-040 (CONFIRMED — PO PU-10): "Plan is REQUIRED at account
    activation; a unit without a plan blocks with a message."

    ⚠ **NARROWED 2026-09-21 AND NOT REVERSED — SEE
    `COMMON_AREA_REQUIRES_A_PLAN` ABOVE.** PO, verbatim: *"common area dont need
    rate plan as of now; make this optional"*. The rule goes on holding for a
    DWELLING and stops holding for a COMMON AREA. Before that ruling this check
    was the first of the three refusals that made every New Connect build
    impossible: a build WITH a common area was refused here at
    `create_master_account`'s per-unit guard (*"This unit has no rate plan
    yet."*), and a build WITHOUT one was refused for lacking an anchor — a
    pincer that took eight builds out of eight in a browser.

    The unit's plan is metering's `units.rate_plan_id` and the account DERIVES
    from it — PO ruling 2026-08-11: *"from unit you will derive the plan, you
    will also need to maintain attributes that are important at account
    level."* So there is deliberately no second live plan record on the
    account to disagree with the unit; the account's own columns carry what is
    genuinely account-level (deposit, credit tier, tax exemption + certificate
    + expiry, autopay, preferred language, NSF count, bad address), and a
    reprint years later resolves its prices from the bill's own locked-at-issue
    snapshot rather than from today's assignment.

    A plan field in the payload is still refused rather than accepted and
    dropped: changing the plan is the unit's write path (S23 / S16), and
    accepting it here would give a caller a second door to a fact with one
    owner.

    ⛔ **WHERE THIS FIRES, AND WHERE IT DELIBERATELY NO LONGER DOES — CR-047
    task 11, `DEF-2518`.** Read the rule's own words again: *"at account
    **ACTIVATION**"*. It used to run on every path through `_make_occupying`,
    including the S68 bulk import, which is CREATION — so a migration could not
    load a single account until every unit already had a plan, and *"load the
    estate on day one, assign plans on day two"* was impossible. Since CR-047
    `create_from_import` passes `require_plan=False` and **nothing else does**:

      · `activate_account` (S21's Activate) — still refused here, by name;
      · `update_account`'s status change into a billing class
        (`_apply_status_change`) — the same;
      · S18 `create_account` and S19 `move_in` with an occupying status — the
        same, unchanged by this CR;
      · `create_from_import` — EXEMPT, and its account is a draft or a migrated
        live account that was already active in the utility's old system.

    ⚠ **AND A MIGRATED-ACTIVE ACCOUNT THEREFORE NEVER MEETS THIS CHECK AT ALL**,
    because it is created occupying and is never *activated*. That is stated
    rather than hidden, and it is safe for one reason that was VERIFIED and not
    assumed (hard-won law 1): **the bill run refuses it.**
    `apps/billing/gather.gather_account` raises `GatherProblem(GATHER_NO_PLAN)`
    for any unit with no `rate_plan_id`, `runs.STAGE_BY_REASON` files it on the
    `resolve-subscription` exception tab, and `runs.NOT_RETRYABLE_HERE` marks it
    as needing an edit somewhere else. So an unplanned account can be LOADED and
    can never be BILLED — which is exactly the shape the ruling asks for, since
    the plan is a REFERENCE (BR-CUS-029) and the day it lands on the unit every
    account under it has it, with nothing to backfill.
    """
    if _unit_is_a_common_area(unit) and not COMMON_AREA_REQUIRES_A_PLAN:
        # PO 2026-09-21 — *"common area dont need rate plan as of now; make this
        # optional"*. The requirement does not FIRE on a corridor, a car park or
        # an irrigation point; it is not deleted, and the constant above is the
        # one place that decides. A dwelling falls through to the refusal below
        # exactly as it always has.
        return
    if getattr(unit, "rate_plan_id", None) is None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-MET-040",
            message_key="customers.account.plan_required_at_activation",
            params={"unit_id": str(unit.id)},
        )


def _allocate_account_no() -> str:
    """BR-TEN-035. Unlike metering's premises/unit series, the `account` series
    IS seeded at provisioning, so a missing row is a real fault: the account
    number is NOT NULL and an account without one cannot exist. Fail loudly
    rather than invent a number (CLAUDE.md — guesses become silent errors)."""
    try:
        return core_numbering.next_number(ACCOUNT_SERIES, seams.tenant_today())
    except core_numbering.NumberingError as exc:
        logger.error("account number series unusable: %s", exc)
        raise errors.SysError(
            errors.SYS_INTERNAL,
            message_key="customers.account.numbering_unavailable",
            params={"series": ACCOUNT_SERIES},
        ) from exc


def _allocate_customer_no() -> str:
    """BR-TEN-035 — CR-030 W0. The same posture as `_allocate_account_no`: the
    `customer` series IS seeded at provisioning (`SERIES_DEFAULTS` derives from
    the catalogue), so a missing row is a real fault and not a shrug.

    ⚠ ONE DIFFERENCE FROM THE ACCOUNT NUMBER, AND IT IS DELIBERATE.
    `accounts.account_no` is NOT NULL, so an account with no number cannot
    exist and failing loudly is the only option. `customers.customer_no` is
    NULLABLE while the 0014 backfill runs (see the model), and it would be easy
    to read that as licence to swallow the error and leave a NULL behind. It is
    not: a customer created from here on ALWAYS gets a number, because a NULL
    written after the backfill has nothing to fill it later and would be
    invisible until somebody tried to quote it down a phone. Same raise, same
    reason."""
    try:
        return core_numbering.next_number(CUSTOMER_SERIES, seams.tenant_today())
    except core_numbering.NumberingError as exc:
        logger.error("customer number series unusable: %s", exc)
        raise errors.SysError(
            errors.SYS_INTERNAL,
            message_key="customers.customer.numbering_unavailable",
            params={"series": CUSTOMER_SERIES},
        ) from exc


def _tenant_currency() -> str:
    """CLAUDE.md rule 2's CHAR(3) partner. One tenant = one currency, so the
    account inherits it; `currency` is a REFUSED input field."""
    code = seams.tenant_currency()
    if not code or len(code) != 3:
        raise errors.SysError(
            errors.SYS_INTERNAL, message_key="customers.account.tenant_currency_missing"
        )
    return code


# ── validation ──────────────────────────────────────────────────────────────
#: The four columns `step4-charges.png` draws as *Billing preferences*.
#: Named ONCE so the two doors that take them cannot drift.
BILLING_PREFERENCE_FIELDS: tuple[str, ...] = (
    "autopay",
    "tax_exempt",
    "tax_exempt_ref",
    "tax_exempt_expires",
)


def _billing_preferences(payload: dict[str, Any], fe: list[dict[str, Any]]) -> dict[str, Any]:
    """**Autopay and the tax exemption, cleaned once for every door that takes
    them** — `DEF-CUS-8020`.

    ⚠ **IT IS A FUNCTION RATHER THAN FOUR LINES IN TWO PLACES BECAUSE THE TWO
    PLACES ARE TWO DOORS ONTO ONE TABLE.** `_validate_account` (the ordinary
    account) and `create_master_account` (the owner's account at an address)
    both write `accounts.autopay` and `accounts.tax_exempt*`. A second copy of
    the cleaning is how one door starts accepting a certificate number the
    other truncates, or storing `"yes"` where the other stores `True` — the
    same reasoning `_validate_customer_block` is shared for, one table over.

    ⚠ **ABSENT IS NOT `False`.** A key the caller did not send is left out of
    the returned dict entirely, so the column default applies. Writing `False`
    for an absent `autopay` would be this function answering a question the
    caller was never asked — and every pre-existing caller of the master door
    (the seeder, the tests, an approval) sends none of the four.

    BR-CUS-059: autopay is CAPTURE-ONLY in v1 — stored and displayed, never
    drafted against. 120 is `tax_exempt_ref`'s column bound.
    """
    out: dict[str, Any] = {}
    if "autopay" in payload:
        out["autopay"] = _bool(payload.get("autopay"))
    if "tax_exempt" in payload:
        out["tax_exempt"] = _bool(payload.get("tax_exempt"))
    if "tax_exempt_ref" in payload:
        out["tax_exempt_ref"] = _text(payload.get("tax_exempt_ref"), 120)
    if "tax_exempt_expires" in payload:
        out["tax_exempt_expires"] = _date(
            payload.get("tax_exempt_expires"), "tax_exempt_expires", fe
        )
    return out


def _validate_account(
    payload: dict[str, Any],
    *,
    partial: bool,
    allowed: frozenset[str] | None = None,
    unit_id: Any = None,
    allow_legacy_type: bool = False,
    custom_data_screen: str | None = None,
    customer_fields_screen: str | None = None,
) -> dict[str, Any]:
    """`allowed` and `unit_id` exist for the move-in path (US-CUS-004): its
    vocabulary is MOVE_IN_FIELDS and its unit comes from the OUTGOING account,
    never from the body. Everything else about the validation is identical, on
    purpose — a move-in that validated differently from a create would be a
    second set of rules for one table."""
    _reject_unknown(payload, allowed or (PATCH_FIELDS if partial else CREATE_FIELDS))
    fe: list[dict[str, Any]] = []
    out: dict[str, Any] = {}

    if not partial:
        out["unit"] = _eligible_unit(payload.get("unit_id") if unit_id is None else unit_id, fe)
        out["account_type"] = _resolve_account_type(
            payload.get("account_type"), fe, allow_legacy=allow_legacy_type
        )

    if "status" in payload:
        out["status"] = _resolve_status(payload.get("status"), fe)
    elif not partial:
        # BR-CUS-018: a new account is a DRAFT until something activates it.
        out["status"] = _resolve_status(PENDING_STATUS_CODE, fe)

    if "account_subtype" in payload:
        out["account_subtype"] = _resolve_account_subtype(payload.get("account_subtype"), fe)
    if "opened_at" in payload:
        out["opened_at"] = _date(payload.get("opened_at"), "opened_at", fe)
    out.update(_billing_preferences(payload, fe))
    # BR-CUS-028 / BR-BIL-036 (CR-052 task 14). Cleaned exactly like `autopay`
    # beside it: a boolean the customer states, stored and read, never derived.
    # They ADD a delivery channel and can never remove the print floor — the
    # floor lives in `apps/notifications` where no writer can forget it.
    if "paperless" in payload:
        out["paperless"] = _bool(payload.get("paperless"))
    if "sms_reminders" in payload:
        out["sms_reminders"] = _bool(payload.get("sms_reminders"))
    # CR-122-BRC06 — the claim. Cleaned exactly like the pair above it and read
    # by nothing else; 2000 is `service_request_service`'s own note bound,
    # reused so one idea does not acquire two limits.
    if "eligibility_claimed" in payload:
        out["eligibility_claimed"] = _bool(payload.get("eligibility_claimed"))
    if "eligibility_note" in payload:
        out["eligibility_note"] = _text(payload.get("eligibility_note"), 2000)
    if "preferred_language" in payload:
        out["preferred_language"] = _clean_language(payload.get("preferred_language"), fe)
    # `DEF-CUS-9820` — PO on bills (Billing preferences). Trimmed; blank clears
    # it (stored NULL, never ""); longer than the move-in allows is refused.
    if "po_number" in payload:
        po = _text(payload.get("po_number"), 10_000)
        if po is not None and len(po) > PO_NUMBER_MAX:
            fe.append(
                _field_error(
                    "po_number", errors.VAL_RANGE, "customers.lookups.too_long",
                    max=PO_NUMBER_MAX,
                )
            )
        else:
            out["po_number"] = po
    # ── ⛔ `DEF-1661` — FIVE COLUMNS THIS PATH DECLARED LAWFUL AND THEN DROPPED
    # ON THE FLOOR. FOUND BY CR-046 C4's *"check before adding anything"*.
    #
    # `IMPORT_ACCOUNT_FIELDS` has widened the vocabulary for `deposit_on_file`,
    # `deposit_received_on`, `closed_at` and `bad_address` since CR-030 W1,
    # with three paragraphs of comment each explaining why the import may write
    # them — and this function, the ONLY thing that turns a payload key into a
    # column value, had a branch for none of them. `_reject_unknown` accepted
    # them (they are in `allowed`), nothing validated them, nothing wrote them.
    # Hard-won law 2's exact shape: declared, argued for, wired to nothing,
    # every test green.
    #
    # **The measured cost is money.** US-CUS-023 is titled *"Deposits-on-file
    # import with ORIGINAL receipt dates + interest accrual start"*; a
    # migration of 1,213 accounts carrying $150.00 deposits imported
    # **$0.00 of deposits and no dates at all**, so every migrated customer's
    # deposit interest (BR-CUS-050/057) started at cutover — or never started,
    # there being no deposit. `bad_address` was lost the same way, so the first
    # bill run posts to addresses the previous utility already knew were dead.
    #
    # ⚠ **THESE ARE NOT WIDENINGS.** Every one is already in
    # `IMPORT_ACCOUNT_FIELDS` and therefore already refused on every other
    # door by `REFUSED_FIELDS`; a key absent from `allowed` never reaches here.
    if "closed_at" in payload:
        out["closed_at"] = _date(payload.get("closed_at"), "closed_at", fe)
    if "bad_address" in payload:
        out["bad_address"] = _bool(payload.get("bad_address"))
    if "deposit_on_file" in payload:
        out["deposit_on_file"] = _decimal_or_none(
            payload.get("deposit_on_file"), "deposit_on_file", fe
        )
    if "deposit_received_on" in payload:
        out["deposit_received_on"] = _date(
            payload.get("deposit_received_on"), "deposit_received_on", fe
        )
    # CR-046 C4/C5 · BR-CUS-172 — the utility's own account id.
    if "external_ref" in payload:
        out["external_ref"] = _text(payload.get("external_ref"), 200)
    # ── CR-056 W3 task 15 — WHO the account belongs to ─────────────────────
    # ⛔ **CARRIED THROUGH `out`, NOT WRITTEN TO THE `accounts` ROW.**
    # `_open_account` builds `Account.objects.create(...)` from named keys and
    # this is not one of them — the link lives in `customer_accounts`. It rides
    # here so a door cannot declare the field lawful and then drop it on the
    # floor, which is exactly `DEF-1661` twenty lines above.
    if "customer" in payload:
        # ⊕ `DEF-CUS-9228` — a door that DRAWS the owner's customer fields on
        # its own slot (New Connection Step 1) names it, exactly as the master
        # door does; every other caller passes none and binds as before.
        out["customer"] = _validate_customer_block(
            payload.get("customer"),
            fe,
            custom_data_screen=customer_fields_screen or custom_data_screen,
        )
    # EP-TEN-09 / US-SHL-015. Refuse this module's own errors FIRST, then hand
    # the blob to tenancy: its refusal is keyed `custom_data.<key>` and raises
    # straight out, so a screen never gets a half-validated form back.
    _refuse_fields(fe)
    if "custom_data" in payload:
        # `DEF-TEN-9157` — a required custom field blocks the save ONLY when it
        # is placed Input on THIS door's screen (`custom_data_screen`: S18 for
        # New account, None for an import or a move-in, which draw none).
        out["custom_data"] = seams.validate_custom_data(
            "accounts", payload.get("custom_data"), screen=custom_data_screen
        )

    _refuse_fields(fe)
    return out


#: What a door may say about the customer, and nothing else. Anything outside
#: this set is REFUSED by name rather than ignored — a clerk who types an
#: identifier into a key the server drops is `DEF-632`'s shape, and this is a
#: block where the dropped key would be somebody's Social Security number.
CUSTOMER_BLOCK_FIELDS: frozenset[str] = frozenset(
    # `custom_data` — CR-161-BRC10 W4, the utility's own customer fields as
    # typed on the New Account wizard's customer step (`S18`).
    {"customer_id", "display_name", "kind", "external_ref", "identity", "custom_data"}
)

#: The identity evidence a door may present, **PER KIND** — CR-056 W2b,
#: `BR-CUS-1022`, PO 2026-09-01. `name` is not accepted in either list because
#: the customer's own `display_name` is the name that gets matched, and two
#: names in one payload is two answers to one question.
#:
#: ⚠ **A FIELD BELONGING TO THE OTHER KIND IS REFUSED BY NAME, NOT IGNORED.**
#: The PO's ruling names different evidence for each kind and the decision log
#: gives the reason the two lists may not simply be unioned: *"asking for both
#: and leaving one blank turns a rule into a habit, and the blank field
#: eventually gets filled with something."* A dropped key is worse still — a
#: clerk believes a Tax ID was stored when it was not, which is `DEF-632`'s
#: exact shape one level up.
IDENTITY_BLOCK_FIELDS_BY_KIND: dict[str, frozenset[str]] = {
    identity_match.KIND_PERSON: frozenset({"date_of_birth", "ssn", "driving_licence", "phone"}),
    identity_match.KIND_COMPANY: frozenset({"tax_id", "phone"}),
}

#: The union, used ONLY to tell *"a field belonging to the other kind"* from
#: *"a field this product has never heard of"* — the first is a capture rule and
#: the second is a typo, and a clerk needs to be told which.
IDENTITY_BLOCK_FIELDS: frozenset[str] = frozenset(
    IDENTITY_BLOCK_FIELDS_BY_KIND[identity_match.KIND_PERSON]
    | IDENTITY_BLOCK_FIELDS_BY_KIND[identity_match.KIND_COMPANY]
)

#: `OQ-1241` — whether a company gets a date-of-birth equivalent is OPEN, so the
#: key is RECOGNISED here and stubbed in `identity_match.from_payload` rather
#: than refused as unknown. Refusing it as a typo would hide a real question.
IDENTITY_OPEN_QUESTION_FIELDS: frozenset[str] = frozenset({"incorporation_date"})


def _validate_customer_block(
    value: Any, fe: list[dict[str, Any]], *, custom_data_screen: str | None = None
) -> dict[str, Any] | None:
    """The `customer` block on an account-opening payload (CR-056 W3 · W2b).

    Every key is optional. Two things are NOT:

      * **An unknown key is refused.** This block carries government
        identifiers, and a typo'd key that is silently dropped means a clerk
        believes an SSN was stored when it was not — `DEF-632`'s exact shape,
        one level up.
      * **IDENTITY WITHOUT A KIND IS REFUSED (CR-056 W2b, `BR-CUS-1022`).** A
        person is asked for a Social Security number, a driving licence or a
        phone; a company for its Tax ID. Which test a match is judged against
        depends on the answer, so evidence presented against an unstated kind
        cannot be assessed at all — and defaulting it to `person` would file a
        business's Tax ID nowhere and judge it by a date of birth it has not
        got.

    ⚠ **THE REFUSAL IS SCOPED TO THE IDENTITY, NOT TO THE ACCOUNT.** A door
    naming a customer and NO identity still opens the account with the kind it
    stated or the `person` default — see `link_customer`. The PO ruled on
    2026-09-01 that a duplicate identifier *refuses to LINK and never refuses to
    SAVE*, and refusing to open an account over a missing dropdown would be the
    same one-way door in a different coat.
    """
    if value in (None, "", {}):
        return None
    if not isinstance(value, dict):
        fe.append(_field_error("customer", errors.VAL_FORMAT, "customers.account.unknown_field"))
        return None
    unknown = sorted(set(value) - CUSTOMER_BLOCK_FIELDS)
    if unknown:
        fe.append(
            _field_error(
                f"customer.{unknown[0]}",
                errors.VAL_FORMAT,
                "customers.account.unknown_field",
                field_name=unknown[0],
            )
        )
        return None
    kind = _validate_customer_kind(value.get("kind"), fe)
    out: dict[str, Any] = {
        "customer_id": value.get("customer_id"),
        "display_name": _text(value.get("display_name"), 200),
        "kind": kind,
        "external_ref": _text(value.get("external_ref"), 120),
    }
    if "custom_data" in value:
        # CR-161-BRC10 W4 — tenancy's ONE validator, through this module's seam.
        # The door names its screen (`S18` for New Account; `None` for a door
        # that draws no customer fields), so a required customer field binds
        # only where it is typed in (BR-TEN-052 as amended).
        out["custom_data"] = seams.validate_custom_data(
            "customers", value.get("custom_data"), screen=custom_data_screen
        )
    identity = value.get("identity")
    if identity in (None, "", {}):
        out["identity"] = None
        return out
    if not isinstance(identity, dict):
        fe.append(
            _field_error("customer.identity", errors.VAL_FORMAT, "customers.account.unknown_field")
        )
        return None
    presented = {key for key, cell in identity.items() if cell not in (None, "")}
    unknown_identity = sorted(set(identity) - IDENTITY_BLOCK_FIELDS - IDENTITY_OPEN_QUESTION_FIELDS)
    if unknown_identity:
        fe.append(
            _field_error(
                f"customer.identity.{unknown_identity[0]}",
                errors.VAL_FORMAT,
                "customers.account.unknown_field",
                field_name=unknown_identity[0],
            )
        )
        return None
    if presented and kind is None:
        # CR-056 W2b — the identity cannot be judged without knowing WHOSE it is.
        fe.append(
            _field_error(
                "customer.kind",
                errors.VAL_REQUIRED,
                "customers.customer.kind_required_for_identity",
                field_name=sorted(presented)[0],
            )
        )
        return None
    if kind is not None:
        # CAPTURE FOLLOWS THE KIND. Refused BY NAME, so a clerk is told a
        # business is not asked for a driving licence rather than watching the
        # value vanish.
        borrowed = sorted(presented - IDENTITY_BLOCK_FIELDS_BY_KIND[kind])
        if borrowed:
            fe.append(
                _field_error(
                    f"customer.identity.{borrowed[0]}",
                    errors.VAL_FORMAT,
                    "customers.customer.identity_not_asked_of_kind",
                    field_name=borrowed[0],
                    kind=kind,
                )
            )
            return None
    if identity.get("date_of_birth") not in (None, ""):
        # Parsed HERE so a malformed date is a field error on the form rather
        # than an identity that silently never matches anything.
        _date(identity.get("date_of_birth"), "customer.identity.date_of_birth", fe)
    out["identity"] = dict(identity)
    return out


def _validate_customer_kind(value: Any, fe: list[dict[str, Any]]) -> str | None:
    """`person` or `company` — B2 r9 #1's own two words — or `None` for unstated.

    ⚠ **A SOLE TRADER RAISES RATHER THAN BEING FOLDED INTO EITHER (`OQ-1242`).**
    `identity_match.normalise_kind` is where that happens, and it is deliberate:
    they trade as a business and are a natural person, so the two readings ask
    for different evidence, and choosing one here would resolve an open question
    by writing a value into a customer's row.
    """
    kind = identity_match.normalise_kind(_text(value, 40))
    if kind is None or kind in identity_match.KINDS:
        return kind
    fe.append(
        _field_error(
            "customer.kind",
            errors.VAL_UNKNOWN_LOOKUP,
            "customers.customer.kind_unknown",
            value=str(value),
        )
    )
    return None


def _clean_language(value: Any, fe: list[dict[str, Any]]) -> str | None:
    """BR-CUS-064 (CONFIRMED): the account carries a preferred language.

    The value set is BR-TEN-042's seeded language list, which tenancy owns — so
    it is read through the seam and NOT copied here. While that seam is
    unwired the value is accepted as free text rather than validated against a
    vocabulary this module invented."""
    code = _text(value, 12)
    if code is None:
        return None
    allowed = seams.tenant_languages()
    if allowed and code not in allowed:
        fe.append(
            _field_error(
                "preferred_language",
                errors.VAL_UNKNOWN_LOOKUP,
                "customers.account.language_unknown",
                value=code,
                allowed=list(allowed),
            )
        )
        return None
    return code


def _validate_contact(
    payload: Any,
    *,
    custom_data_screen: str | None = None,
    existing_custom: Any = None,
) -> dict[str, Any] | None:
    """BR-CUS-045: every column is PII, and `gov_id_last4` stores the LAST FOUR
    only — a longer value is truncated to its last four rather than stored, so
    a full government id cannot enter the database through this path.

    ⚠ **`custom_data` — `DEF-CUS-9168` (CR-161-BRC10 W3).** The utility's own
    contact fields, checked by tenancy (`seams.validate_custom_data`) and never
    by a copy here. `custom_data_screen` is the form this door IS: `"S21"` for
    the contact edit on Account detail, `None` for every door that draws no
    contact field (the wizards' contact block, a sale's co-applicant). A door
    that names a screen is checked EVERY time, sent or not, because a required
    field typed in there must hold an answer — the stored one (`existing_custom`)
    counts. A door that names none is checked only when it sends a blob, and
    nothing is required of it (PO Rules table 2026-10-02: *"A required field
    never blocks a screen that doesn't show it"*).
    """
    if payload in (None, {}):
        return None
    data = _payload_dict(payload)
    fe: list[dict[str, Any]] = []
    unknown = set(data) - CONTACT_FIELDS
    for field in sorted(unknown):
        fe.append(
            _field_error(f"contact.{field}", errors.VAL_FORMAT, "customers.account.unknown_field")
        )
    full_name = _text(data.get("full_name"), 200)
    if not full_name:
        fe.append(
            _field_error(
                "contact.full_name", errors.VAL_REQUIRED, "customers.contact.name_required"
            )
        )
    email = _text(data.get("email"), 254)
    if email and ("@" not in email or email.startswith("@") or email.endswith("@")):
        fe.append(
            _field_error("contact.email", errors.VAL_FORMAT, "customers.contact.email_format")
        )
    dob = _date(data.get("dob"), "contact.dob", fe)
    # CR-171-BRC10 P1.11 — `contacts.contact_by`, one list with the co-owners'.
    contact_by = _text(data.get("contact_by"), 20)
    if contact_by is not None and contact_by not in models.CONTACT_BY:
        fe.append(
            _field_error(
                "contact.contact_by", errors.VAL_UNKNOWN_LOOKUP, "customers.moveIn.people.choiceUnknown"
            )
        )
    _refuse_fields(fe)
    gov_id = _text(data.get("gov_id_last4"), 64)
    out = {
        "full_name": full_name,
        "email": email,
        "phone": _text(data.get("phone"), 40),
        "dob": dob,
        "gov_id_last4": gov_id[-4:] if gov_id else None,
        "is_primary": _bool(data.get("is_primary")) if "is_primary" in data else True,
    }
    # CR-171-BRC10 P1.11 — written only when sent, so a door that never asks
    # leaves an edited contact's stored values alone.
    if "job_title" in data:
        out["job_title"] = _text(data.get("job_title"), 120)
    if "contact_by" in data:
        out["contact_by"] = contact_by
    if custom_data_screen is not None or "custom_data" in data:
        out["custom_data"] = seams.validate_custom_data(
            "contacts",
            data.get("custom_data"),
            screen=custom_data_screen,
            existing=existing_custom,
        )
    return out


def _validate_addresses(
    payload: Any,
    *,
    custom_data_screen: str | None = None,
    existing_custom: Any = None,
) -> list[dict[str, Any]]:
    if payload in (None, []):
        return []
    if not isinstance(payload, (list, tuple)):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="customers.account.addresses_not_a_list"
        )
    fe: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for index, entry in enumerate(payload):
        data = _payload_dict(entry)
        for field in sorted(set(data) - ADDRESS_FIELDS):
            fe.append(
                _field_error(
                    f"addresses[{index}].{field}",
                    errors.VAL_FORMAT,
                    "customers.account.unknown_field",
                )
            )
        line1 = _text(data.get("line1"))
        if not line1:
            fe.append(
                _field_error(
                    f"addresses[{index}].line1",
                    errors.VAL_REQUIRED,
                    "customers.address.line1_required",
                )
            )
        kind = (_text(data.get("kind"), 20) or "mailing").lower()
        if kind in ADDRESS_KINDS_RETIRED:
            # `BR-MET-1161` — named separately from "unknown" on purpose: the
            # caller has a real service address in hand and needs to be told
            # where it lives, not that we have never heard of the word.
            fe.append(
                _field_error(
                    f"addresses[{index}].kind",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "customers.address.kind_service_retired",
                )
            )
        elif kind not in ADDRESS_KINDS:
            fe.append(
                _field_error(
                    f"addresses[{index}].kind",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "customers.address.kind_unknown",
                    allowed=list(ADDRESS_KINDS),
                )
            )
        rows.append(
            {
                "kind": kind,
                "line1": line1,
                # `DEF-CUS-6408` — the unit line, kept as its own column and
                # never folded into line 1 (`BR-NOT-029` clause (a)).
                "line2": _text(data.get("line2"), 200),
                "city": _text(data.get("city"), 120),
                "state": _text(data.get("state"), 120),
                "postal_code": _text(data.get("postal_code"), 40),
            }
        )
    _refuse_fields(fe)
    # `DEF-CUS-9169` (CR-161-BRC10 W3) — the utility's own MAILING-address
    # fields. `custom_data_screen` is the form this door is: `"S18"` for the
    # New Account wizard's mailing block, `"S21"` for the mailing edit on
    # Account detail, `None` for a door that draws none (New Connection, an
    # import). A named screen is checked for every row it sends, so a required
    # field placed Input there needs an answer; `existing_custom` is the stored
    # row's blob on an edit, and its answers count and survive.
    for index, entry in enumerate(payload):
        data = _payload_dict(entry)
        if custom_data_screen is None and "custom_data" not in data:
            continue
        rows[index]["custom_data"] = seams.validate_custom_data(
            "addresses",
            data.get("custom_data"),
            screen=custom_data_screen,
            existing=existing_custom,
        )
    return rows


# ── service agreements (US-CUS-003 §5: one row per active service) ──────────
def _unit_service_offer(unit_id: Any) -> list[str]:
    """The service codes a unit has a point for, de-duplicated, in the points'
    own order.

    **THE OFFER A MOVE-IN MAY CHOOSE FROM (`BR-CUS-1101`).** It is the same
    walk `_open_service_agreements` makes, reduced to codes, so the list a
    clerk is shown and the list the writer honours cannot disagree — the
    screen's own offer comes from metering's `metered_services`, which is this
    same de-duplication one module over.

    De-duplicated because `service_points` carries no unique key on
    (unit, service): a sub-metered unit may hold two water points, and a clerk
    is offered *water* once.
    """
    offer: list[str] = []
    for point in seams.service_points_for(unit_id):
        code = point.get("service")
        if code and code not in offer:
            offer.append(code)
    return offer


def _clean_service_choice(unit_id: Any, raw: Any) -> list[str] | None:
    """⛔ **`BR-CUS-1101` — WHICH OF THE UNIT'S SERVICES THIS ACCOUNT
    TAKES, VALIDATED AT THE DOOR (PO ruling 2026-09-25).**

    `None` (the field absent) is *all of them*, which is what every move-in did
    before this existed and is what `MOVE_IN_FIELDS`' entry documents. A list
    is the clerk's ticks.

    Three refusals, and each is a different thing going wrong:

      * **not a list** — a caller sent something this field cannot be;
      * **an EMPTY list** — refused, and for `final_reads`' reason rather
        than out of tidiness: a screen that sent a `services` key sent one
        because a clerk ticked boxes, and `[]` is a payload that lost them
        between the screen and the door. *Take nothing* is not a move-in;
      * **a code the unit has no point for** — refused **by name**, with
        the unit's own offer beside it. A clerk cannot buy a connection that
        does not exist, and a code silently dropped here would open an account
        the clerk believes has gas and which has no gas agreement, no gas
        route, no gas plan and no gas meter — hard-won law 2's mirror on a
        money path.

    Returned in the UNIT's order rather than the caller's, so two clerks who
    tick the same three services in different orders produce the same audit
    payload.
    """
    if raw is None:
        return None
    if not isinstance(raw, list):
        _refuse_fields(
            [
                _field_error(
                    "services",
                    errors.VAL_FORMAT,
                    "customers.move_in.services_not_a_list",
                )
            ]
        )
    offer = _unit_service_offer(unit_id)
    if not raw:
        _refuse_fields(
            [
                _field_error(
                    "services",
                    errors.VAL_REQUIRED,
                    "customers.move_in.services_required",
                    allowed=offer,
                )
            ]
        )
    wanted: list[str] = []
    unknown: list[str] = []
    for value in raw:
        code = (_text(value, 40) or "").strip().lower()
        if code == "" or code not in offer:
            if code not in unknown:
                unknown.append(code)
        elif code not in wanted:
            wanted.append(code)
    if unknown:
        _refuse_fields(
            [
                _field_error(
                    "services",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "customers.move_in.service_not_at_unit",
                    services=unknown,
                    allowed=offer,
                )
            ]
        )
    return [code for code in offer if code in wanted]


def _validate_service_custom_data(
    data: dict[str, Any],
    *,
    status: Any,
    screen: str | None,
    inherit_services: bool = False,
) -> dict[str, Any] | None:
    """`DEF-CUS-9170` (CR-161-BRC10 W3) — the SERVICE-AGREEMENT answers an
    account-opening door was handed, checked by tenancy and returned for
    `_write_service_custom_data` to put on every agreement the door opens.

    ⚠ **AGREEMENTS ARE OPENED, NEVER TYPED.** The server makes one per service
    point on the unit (`_open_service_agreements`), so the clerk types the
    answers ONCE, on the New Account unit step that lists the services, and
    every agreement the call opens carries them. `None` means *nothing was
    sent and nothing is required here* — the account opens exactly as before.

    ⛔ **A DRAFT OPENS NO AGREEMENT, SO IT CANNOT KEEP AN ANSWER.** A
    non-occupying account (the wizard's *Save as draft*) writes no
    `service_agreements` row until it is activated, and nothing else could
    hold the values until then. Saving them silently into nothing is
    `DEF-CUS-9159`'s exact shape, so a NON-EMPTY blob on a draft is refused by
    name, and the wizard says so before the press. On a draft nothing is
    required either: no agreement is being typed in.
    """
    sent = "service_custom_data" in data
    raw = data.get("service_custom_data")
    opens_agreements = is_occupying(status) or inherit_services
    if not opens_agreements:
        if sent and isinstance(raw, dict) and any(
            value not in (None, "", []) for value in raw.values()
        ):
            _refuse_fields(
                [
                    _field_error(
                        "service_custom_data",
                        errors.VAL_FORMAT,
                        "customers.account.service_fields_on_draft",
                    )
                ]
            )
        return None
    if screen is None and not sent:
        return None
    return seams.validate_custom_data("service_agreements", raw, screen=screen)


def _write_service_custom_data(agreements: list[Any], values: dict[str, Any] | None) -> None:
    """Put one validated blob on each agreement a door just OPENED. A
    `filter().update()` on the call's own fresh rows, inside the caller's
    transaction — nothing else holds them yet."""
    if not values or not agreements:
        return
    models.ServiceAgreement.objects.filter(pk__in=[row.pk for row in agreements]).update(
        custom_data=values
    )


def _open_service_agreements(
    account: models.Account,
    started_on: date,
    *,
    chosen_services: list[str] | None = None,
) -> list[Any]:
    """The account↔service_point rows the account takes at the unit.

    The services are metering's — read through its selector, never its ORM
    (B1). `tariff_id` is NOT written: r16 #3 supersedes that column with the
    BR-CUS-029 plan assignment, and neither the superseded column nor its
    replacement exists (see the models docstring).

    ⚠ **`chosen_services` IS `BR-CUS-1101` AND IT IS THE WHOLE OF IT
    (PO ruling 2026-09-25).** Their own scenario: a premises offers six
    services, the unit has six service points, five of them carry a meter or an
    asset, **and the account takes only three**. Until this keyword existed
    that last step was impossible — this loop walked EVERY point on the unit
    and opened one agreement per point, unconditionally, so an account could
    only ever take all six.

    ⛔ **NO COLUMN WAS ADDED AND NONE MAY BE.** Taking a subset is CREATING
    FEWER ROWS, not marking rows as unwanted: `service_agreements` already
    carries everything this needs. The PO was shown and accepted the cost —
    **an absent agreement cannot be told apart from a deliberate untick**, so
    nothing in the product may claim to know which of the two a missing row is.

    `None` is *every point*, and it is the default, so every existing caller —
    `POST /accounts` (S18), the S68 bulk import, `unit_correction`,
    `activate_account` — is byte-for-byte what it was. Only a door that names
    the subset in writing gets the new behaviour (the `CR-047` keyword
    discipline one function up).

    The value is a list of SERVICE CODES, never service point ids. Two reasons,
    and the second is the load-bearing one: a clerk chooses a *service* and a
    code is what a refusal can name out loud (`customers.move_in.service_not_at
    _unit`), and `service_points` carries **no unique key on (unit, service)**
    — a sub-metered unit may hold two water points — so a code takes every
    point on that service and cannot half-connect one. The door validates the
    list against the unit's own points before this is reached
    (`_clean_service_choice`); this function filters and never refuses, because
    a code that reached here unvalidated would be silently dropped otherwise.
    """
    created = []
    existing = set(
        models.ServiceAgreement.objects.filter(
            tenant_id=account.tenant_id, account=account, ended_on__isnull=True
        ).values_list("service_point_id", flat=True)
    )
    for point in seams.service_points_for(account.unit_id):
        if chosen_services is not None and point.get("service") not in chosen_services:
            continue
        point_id = point["id"]
        if UUID(str(point_id)) in {UUID(str(pk)) for pk in existing}:
            continue
        created.append(
            models.ServiceAgreement.objects.create(
                tenant_id=account.tenant_id,
                account=account,
                service_point_id=point_id,
                started_on=started_on,
            )
        )
    return created


def _refuse_if_start_lands_on_the_prior_move_day(account: models.Account) -> None:
    """BR-CUS-056 (CONFIRMED — PO OQ-060 option (a)): "the OUTGOING account pays
    the move day (billed through the move-day reading); the incoming account
    starts the NEXT day from the same reading — no gap, no double-bill."

    So an incoming start ON or BEFORE the previous occupant's `closed_at` is
    refused: those days are already the outgoing account's, and billing them
    twice is the exact defect the ruling exists to prevent (US-CUS-004 TC-6 —
    "the backdated chained start blocks").

    This lives in `_make_occupying` rather than in `move_in` because the rule is
    about the UNIT's boundary day, not about which wizard the caller used: a
    forged create and an old draft's activation reach the same day the same way.

    Silent when there is nothing to compare — a unit with no prior tenancy, or a
    predecessor closed WITHOUT a date (slice 2 had no way to write one). A
    missing start date is BR-CUS-022's refusal below, not this one's.
    """
    from apps.customers import selectors

    if account.opened_at is None:
        return
    prior = selectors.last_closed_account_for_unit(account.unit_id, exclude_id=account.pk)
    if prior is None or prior.closed_at is None or account.opened_at > prior.closed_at:
        return
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-CUS-056",
        message_key="customers.account.start_on_prior_move_day",
        params={
            "unit_id": str(account.unit_id),
            "opened_at": account.opened_at.isoformat(),
            "prior_account_no": prior.account_no,
            "prior_closed_at": prior.closed_at.isoformat(),
            "earliest_start": (prior.closed_at + timedelta(days=1)).isoformat(),
        },
    )


def _occupancy_guards(account: models.Account, unit: Any, *, require_plan: bool = True) -> None:
    """⛔ **(a) — THE OCCUPANCY HALF. Everything that must be true before an
    account may HOLD a unit, and nothing else.**

    ⚠ **THIS WAS THE FIRST HALF OF `_make_occupying`, AND SPLITTING IT IS
    `DEF-2518` (CR-047, PO ruling 2026-08-29).** That function bundled two
    different things behind one `if is_occupying(status)`: these guards, which
    really are about occupying, and `_open_service_agreements`, which is the
    account's INHERITANCE of its unit — the only writer of `service_agreements`
    on the create path. Because the two rode together, an imported row whose
    Status cell was EMPTY became a `pending_activation` account with NO service
    agreements: no service, no route, no cycle, no plan and no meter, counted on
    the receipt under *"created"* beside the good ones. PO verbatim: *"if
    account is created then we need to inherit details form units - otherwise
    upadling it later will be big tasks"*.

    **These four stay tied to a billing status and MUST NOT become
    unconditional**, because BR-CUS-018 is explicit that a draft *"never derives
    occupancy and does not block the unit for other move-ins"*. Making them
    unconditional would refuse the second imported row on a unit the migration
    also brought a live account for.

    Order matters and is the enforcement: LOCK the (tenant, unit) scope first,
    then check BR-CUS-017 under it, then the boundary day (BR-CUS-056), then the
    completeness rules. A check before the lock is exactly the race T5-15 step 4
    describes — and the boundary-day read is a unit-scope fact too, so it sits
    under the same lock rather than beside it.

    ⚠ **`require_plan` IS CR-047 TASK 11 AND IT IS A NARROW EXEMPTION.**
    BR-MET-040's own text is *"Plan is REQUIRED at account **activation**; a
    unit without a plan blocks with a message."* The import door is not
    activation — it is CREATION — and a migration must be able to load accounts
    on day one and assign plans on day two. Only `create_from_import` passes
    False; S18 `create_account`, S19 `move_in`, `activate_account` and
    `update_account`'s status change all keep the default True, so ACTIVATION
    still blocks exactly as the rule says. See `_require_plan_on_unit` for where
    an unplanned account is stopped from BILLING.
    """
    lock_unit_scope(account.unit_id)
    _refuse_if_unit_occupied(account.unit_id, exclude_id=account.pk)
    _refuse_if_start_lands_on_the_prior_move_day(account)
    if require_plan:
        _require_plan_on_unit(unit)
    if account.opened_at is None:
        # US-CUS-003 §5 maps the wizard's "Service start date" to
        # accounts.opened_at + service_agreements.started_on, and BR-CUS-022
        # starts the first bill from it. An occupying account without one could
        # never be billed, so it is required here rather than defaulted.
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-CUS-022",
            message_key="customers.account.start_date_required",
            params={"field": "opened_at"},
        )


def _inheritance_started_on(
    account: models.Account, changeover_on: date | None, *, terminal: bool = False
) -> date:
    """⛔ **WHAT `started_on` A NON-OCCUPYING ACCOUNT'S AGREEMENT GETS
    (CR-047 task 10). NO CLOCK IS READ HERE, EVER (BR-TEN-043).**

    Three candidates and they are RANKED, not blended:

      1. **the row's own `opened_at`** — the file said when service started, so
         that IS the date, exactly as it is for an occupying account;
      2. **its `closed_at`, and only for a TERMINAL row** — a migration brings
         closed accounts across (`IMPORT_ACCOUNT_FIELDS` accepts `closed_at`
         for exactly that reason) and an agreement that STARTS after it ENDS is
         not a fact about anything. Taking the close date makes it a same-day
         row: the account held these services, and it does not now;
      3. **the RUN's cutover/changeover date** — the only other date in play on
         this path. `apps/metering/import_runs.py` resolves it once per run and
         hands it over as `payload["cutover_on"]`; it is the date the opening
         buckets are struck at and the date the opening journal entries carry
         (BR-CUS-049), so an agreement dated the same day says the account began
         being ours on the day its books did. Anything else invents a fact.

    **`timezone.now()` / `date.today()` is NOT a third candidate and that is
    BR-TEN-043**, quoted by `import_runs._accounts_cutover`: *"the caller names
    the business event's date and this kernel never reads a clock on their
    behalf. Falling back to today would date a utility's migrated books on the
    day somebody happened to run the import rather than the day the balances
    were struck."* The same sentence governs this date for the same reason — a
    `started_on` of "whenever the import was run" would put proration and the
    first bill on a day nobody chose.

    So with neither, this REFUSES (hard-won law 3: defaults fail closed). That
    state is not reachable from S68 today — the runner falls back to a
    PROVISIONAL changeover date (today − 90 days) rather than passing None, and
    holds the money until it is confirmed — so this guards a future fourth
    caller rather than a live path. The refusal reuses the sentence the operator
    already sees when a run has no changeover date; G32 requires a raised
    `message_key` to resolve to a customer sentence and the catalogues are not
    this module's file.
    """
    if account.opened_at is not None:
        return account.opened_at
    if terminal and account.closed_at is not None:
        return account.closed_at
    if changeover_on is not None:
        return changeover_on
    raise errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref="BR-TEN-043 · BR-CUS-022 · BR-CUS-049",
        message_key="customers.import.cutover_required",
        params={"account_no": account.account_no, "field": "cutover_on"},
    )


def _inherit_service_links(
    account: models.Account, *, started_on: date, chosen_services: list[str] | None = None
) -> list[Any]:
    """⛔ **(b) — THE INHERITANCE HALF, which is what CR-047 makes
    unconditional for the import door.**

    ⚠ **NOTHING IS COPIED. EVERY ONE OF THESE ROWS IS A FOREIGN KEY**, and that
    is the whole design (BR-CUS-029, PO ruling 2026-08-11: *"from unit you will
    derive the plan, you will also need to maintain attributes that are
    important at account level"*). The chain is
    `accounts` → `service_agreements(service_point_id)` →
    `service_points(unit_id, service_id, route_id, cycle_id)` →
    `units(rate_plan_id)` and `assets(service_point_id)`, so the service, the
    route, the cycle, the plan and the meter are all REACHED, never stored on
    the account. Which is why the missing agreement row was so expensive: it is
    the FIRST link, and without it the entire chain is unreachable from the
    account even though every row it points at already exists.

    It is also why this is safe to write for a DRAFT. The rows are a reference,
    not a claim on the unit: `selectors.accounts_for_bill_run` scopes a run on
    `OCCUPYING_BEHAVIOR_CLASSES`, so a non-billable account's agreements are
    read by no bill run until its status changes, and `service_agreements`
    carries no unique key on (tenant, service_point) — only
    `ix_sa_tenant_service_point` — so a draft holding a link to a point a live
    account also holds is refused by nothing and means nothing.

    ⚠ **`chosen_services` IS `BR-CUS-1101`'s SUBSET, PASSED STRAIGHT
    THROUGH.** `None` is every point and is the default, so the import door and
    every other caller are unchanged. See `_open_service_agreements`.
    """
    return _open_service_agreements(account, started_on, chosen_services=chosen_services)


def _make_occupying(
    account: models.Account,
    unit: Any,
    *,
    warnings: list[dict[str, Any]],
    require_plan: bool = True,
    chosen_services: list[str] | None = None,
) -> list[Any]:
    """(a) then (b): the guards, then the inheritance they used to hide.

    Returns the agreements CREATED by this call, so a caller can report the
    count without a second derivation (CR-047's `services_linked`)."""
    _occupancy_guards(account, unit, require_plan=require_plan)
    created = _inherit_service_links(
        account, started_on=account.opened_at, chosen_services=chosen_services
    )
    # J2 step 4's handoff is "account active, plan version snapshot saved,
    # deposit rule applied". Two of those three have nowhere to be written in
    # this slice, and the response SAYS SO rather than implying they happened
    # (the metering `history_recorded: false` precedent).
    warnings.append({"code": "plan_snapshot_not_recorded", "br_ref": "BR-CUS-029", "j2_step": 4})
    warnings.append({"code": "deposit_not_applied", "br_ref": "BR-CUS-023", "j2_step": 4})
    return created


# ── the write path ──────────────────────────────────────────────────────────
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def create_account(
    actor: Any,
    payload: Any,
    *,
    require_identity: bool = True,
    require_deposit_answer: bool = True,
) -> dict[str, Any]:
    """POST /accounts (11b §2.6 · US-CUS-003 S18).

    Default status is BR-CUS-018's draft (`pending_activation`): it is never
    billed, derives no occupancy and does not block the unit. A caller MAY name
    an occupying status instead — that is the wizard's "Create account ✓" and
    also T5-15 step 3's adversarial probe, and both take the same BR-CUS-017
    road through `_make_occupying`.

    ONE transaction; audited (CLAUDE.md rule 7).

    ⛔ **`require_deposit_answer` — `OQ-CUS-12620` (a), PO 2026-09-23: *"we
    ahve to take depsoite if plans asked … "No" only when the plan asks
    none."*** It DEFAULTS ON, the `require_identity` shape below: a request
    with no `deposit` block is read as *No* (`deposit.NO_ANSWER`) and refused
    when the unit's plan asks a deposit of the account's category, so a
    hand-built `POST /accounts` cannot skip it by leaving the block off. No
    caller passes it off today; an in-process creator that has no deposit
    question to ask (a sample loader on a plan that asks one) has to say so in
    writing rather than inherit a hole.

    ⛔ **`require_identity` — `BR-CUS-1024`, PO 2026-09-01: *"Without identifier
    we cannot create Customer ID or master account ot regular account"*.** It
    DEFAULTS ON, so `POST /accounts` — the door a clerk presses — is gated
    without any caller having to ask for it, and an in-process creator that
    cannot identify its party has to say so in writing rather than inheriting a
    hole.

    **ONE CALLER PASSES IT OFF TODAY AND IT IS NOT THE COUNTER: the tenant
    SAMPLE SEED** (`customers.sample_data`). Its 48 seeded accounts carry a
    name, an email and a phone and **state no customer kind**, so the rule
    refuses every one of them and the demo tenant cannot be planted at all — no
    accounts, and therefore no bills, no payments, no payment plan and no
    refund. Choosing a kind for 48 fictional people to get past it would be the
    invented value the ruling forbids by name, so the consequence is REPORTED
    rather than shipped and the exemption is written at that call site.

    ⚠ **THE BULK IMPORT WAS THE OTHER ONE AND IT IS NO LONGER A QUESTION.** It
    reached the same wall for the same reason, two lanes flagged it
    independently, and **the PO ruled on 2026-09-01: the import gets the same
    identity columns the premises spreadsheet gained hours earlier, and the rule
    is NOT relaxed for it** (decision log, *THE BULK ACCOUNTS IMPORT GETS
    IDENTITY COLUMNS TOO*). A row with a name and one identifier loads and its
    customer is matched-or-created; a name alone loads nothing and is counted on
    the receipt. **That work is the import lane's** — the columns do not exist
    yet — so `create_from_import` and `_commit_import_row` still call
    `_open_account` without the keyword and inherit its fail-closed default. The
    exemption is theirs to remove when the columns land, not a hole this lane
    left open.

    **THE EXEMPTION DOES NOT WIDEN THE RULE AND IS VISIBLE IN A GREP** — which
    is the whole reason it is a keyword and not a setting.
    """
    # ── CR-094-BRC01 wave H ─────────────────────────────────────────────────
    # COPIED before the pop, for law 11's reason in miniature: this function
    # never mutates its caller's dict. `deposit` is in CREATE_FIELDS so the
    # vocabulary accepts it, and popped here so the account write below never
    # sees a key that is not an account column — the shape `move_in` already
    # uses for `initial_reads` and `field_visit`.
    #
    # VALIDATED BEFORE THE TRANSACTION OPENS, deliberately: a refused figure or
    # a missing tender writes nothing at all, and the clerk fixes it with every
    # other field still on screen.
    data = dict(_payload_dict(payload))
    deposit_instruction = deposit.clean(data.pop("deposit", None))
    if deposit_instruction is None and require_deposit_answer:
        # ⚠ **NO BLOCK IS *No*, SPELLED OUT (`OQ-CUS-12620` (a), 2026-09-23)** —
        # see `deposit.NO_ANSWER`. The HTTP door passes nothing, so it is gated
        # without asking; see this function's keyword for who passes it off.
        deposit_instruction = deposit.NO_ANSWER
    return _open_account(
        actor,
        data,
        audit_action="account.created",
        deposit_instruction=deposit_instruction,
        # `BR-CUS-1024` — this is the `+ New account` button on the Accounts
        # tab, confirmed as this door by the PO on 2026-09-01 and confirmed
        # again the same day WITH the customer: *"So here if customer ID is not
        # present, we have to create it if not matching customer ID not
        # available, - rest is correct"*.
        #
        # ⛔ **DEFAULTS ON, SO THE HTTP DOOR IS GATED WITHOUT ASKING** — the API
        # view passes nothing. The two in-process callers that pass it OFF each
        # say why at their own call site; see the docstring above.
        require_identity=require_identity,
    )


def _open_account(
    actor: Any,
    data: dict[str, Any],
    *,
    audit_action: str,
    allowed: frozenset[str] | None = None,
    unit_id: Any = None,
    require_occupying: bool = False,
    warnings: list[dict[str, Any]] | None = None,
    account_no: str | None = None,
    allow_legacy_type: bool = False,
    inherit_services: bool = False,
    inherit_started_on: date | None = None,
    require_plan: bool = True,
    agreements_out: list[Any] | None = None,
    require_identity: bool = False,
    deposit_instruction: Any = None,
    chosen_services: list[str] | None = None,
    customer_fields_screen: str | None = None,
    billing_only: bool = False,
    reopen: Any = None,
) -> dict[str, Any]:
    """The one code path that brings an account row into existence.

    ⊕ **`reopen` — `CR-181-BRC10` (PO 2026-10-13, *"Reopen, for the same unit
    only"*). FAILS CLOSED** like every keyword below: only `_move_in` passes
    it, with a `move_in_reopen.ReopenPlan` whose guards have already run.
    Instead of INSERTing a new row, the returning customer's closed account is
    locked and made the move-in's account (`move_in_reopen.reopen_row`); every
    step after that — `_make_occupying` (BR-CUS-017 under the unit lock), the
    service agreements, the customer link, the deposit and the snapshot audit
    — runs exactly as for a new account, on the same number.

    ⊕ **`billing_only` — `CR-164-BRC10` wave 4 (PO 2026-10-03: *"an owner who
    lives there holds it; a landlord or builder doesn't"*). FAILS CLOSED** like
    every keyword below: only `create_build_owner_account` passes it. The unit
    is still VALIDATED (it is how the account's premises, plan and category are
    known), but the row is written with the premises and NO unit, and nothing
    occupancy-shaped runs — no `_make_occupying`, no service agreement — so the
    account pays what it is billed by name and holds no home.

    ⚠ **`chosen_services` IS `BR-CUS-1101` (PO ruling 2026-09-25) AND IT
    FAILS CLOSED LIKE THE FOUR CR-047 KEYWORDS BELOW.** `None` means *every
    service point on the unit*, which is what this door has always done, so S18,
    the S68 import and `activate_account` are untouched. Only `_move_in` passes
    a list today, and it passes one the clerk ticked and this module validated
    against the unit's own points. See `_open_service_agreements`.

    `allow_legacy_type` is DEF-736's cutover exemption and ONLY the S68 bulk
    import passes it — see `_resolve_account_type`. It is a keyword with a
    fail-closed default so a fourth door has to ask for it in writing.

    `create_account` (S18), `move_in` (S19) and the S68 bulk import
    (US-CUS-019) are the three doors into it. They differ in vocabulary, in
    where the unit comes from and in what the audit row is called — NOT in the
    guard, which is the point: BR-CUS-017 is enforced in exactly one place
    (`_make_occupying`) and a second creator that reimplemented it would be a
    second, drifting copy of the only thing standing between one meter and two
    bills. That is why the bulk importer calls THIS rather than
    `Account.objects.create` in a loop: a validated rule must apply to row
    1,199 exactly as it applies to a hand-typed account.

    `account_no` is an ARGUMENT, never a payload field. BR-CUS-046 gives the
    import template an account-# column with an "auto-option", so a migrating
    utility can keep the numbers its customers already quote — but
    `account_no` stays in REFUSED_FIELDS for every client-facing path
    (BR-TEN-035: allocated from the tenant series). Passing it as a keyword is
    what makes the exception a traceable call site instead of a hole in the
    vocabulary. None = allocate, exactly as before.

    ⛔ **THE FOUR CR-047 KEYWORDS — `DEF-2518`, PO ruling 2026-08-29. ALL FOUR
    FAIL CLOSED, so only the door that asks in writing gets the new behaviour
    and S18/S19 are byte-for-byte what they were.**

      * `inherit_services` — write the unit's `service_agreements` even when the
        status does NOT occupy. This is the ruling: *"if account is created then
        we need to inherit details form units - otherwise upadling it later will
        be big tasks"*. Only `create_from_import` passes True.
      * `inherit_started_on` — the RUN's cutover/changeover date, used as
        `started_on` when the row carried no `opened_at`. Ranked BELOW the row's
        own date and never blended with it; see `_inheritance_started_on`, which
        reads no clock (BR-TEN-043).
      * `require_plan` — False lets a migration load an account onto a unit
        whose plan is not assigned yet. BR-MET-040 fires at ACTIVATION, which
        is the word the rule uses; see `_occupancy_guards`.
      * `agreements_out` — an out-parameter, filled with the agreements this
        call CREATED. It exists so `create_from_import` can report
        `services_linked` without a second derivation of the same number, and
        WITHOUT widening this function's return dict, which is the S18 and S19
        response body.

    ⛔ **AND A FIFTH KEYWORD — `require_identity`, `BR-CUS-1024`, PO 2026-09-01:
    *"Without identifier we cannot create Customer ID or master account ot
    regular account"*.** With it on, a payload naming a party and no identifier
    is refused BEFORE the transaction opens, so nothing is written and the clerk
    fixes the field with everything still on screen.

    **THE TWO COUNTER DOORS PASS IT; THE BULK IMPORT DOES NOT, AND THAT IS
    WRITTEN DOWN RATHER THAN LEFT AS A DEFAULT.** `create_account` (S18) and
    `move_in` (S19) are the doors a clerk presses and both turn it on. The
    import carries a name and a legacy reference and **no identity at all** — its
    own code calls the reference a reconciliation key — so the ruling read
    literally refuses every account row of every migration file. **That is
    migration-blocking, it is with the PO, and it must not be shipped by a
    default nobody chose** (decision log 2026-09-01). Its call sites leave this
    False and this paragraph is their reason.
    """
    from apps.customers import selectors

    cleaned = _validate_account(
        data,
        partial=False,
        allowed=allowed,
        unit_id=unit_id,
        allow_legacy_type=allow_legacy_type,
        # The New Account wizard is S18; the move-in door (`allowed` set) draws
        # no custom fields, so nothing is required of it (`DEF-TEN-9157`).
        custom_data_screen="S18" if allowed is None else None,
        customer_fields_screen=customer_fields_screen,
    )
    contact = _validate_contact(data.get("contact"))
    # `DEF-CUS-9169` — the New Account wizard's mailing block is the `S18`
    # slot for `addresses`; move-in and the import draw no address field.
    addresses = _validate_addresses(
        data.get("addresses"), custom_data_screen="S18" if allowed is None else None
    )
    service_custom = _validate_service_custom_data(
        data, status=cleaned["status"], screen="S18" if allowed is None else None,
        inherit_services=inherit_services,
    )
    warnings = [] if warnings is None else warnings

    if require_identity:
        # `BR-CUS-1024` — BEFORE `transaction.atomic()`, deliberately: a refusal
        # raised inside it would roll back a half-written account, and the whole
        # reason `link_customer` skips instead of raising is that it runs in
        # there. Refuse first, write nothing.
        #
        # ⚠ **THE NAME FALLS BACK TO THE CONTACT'S, AND THAT CLOSES THE ONLY
        # WAY THROUGH.** Both wizards ask for a name on step 1 and put it in the
        # contact; a payload that named a party there and sent no `customer`
        # block would otherwise open an account for somebody nobody can
        # identify, by omission rather than by right. The PO's *"no name ->
        # unchanged"* row is about presenting NO party at all, not about
        # presenting one in the other field.
        refuse_account_without_identity(
            cleaned.get("customer"),
            fallback_name=(contact or {}).get("full_name"),
        )

    with transaction.atomic():
        unit = cleaned["unit"]
        status = cleaned["status"]
        if require_occupying and not is_occupying(status):
            # A move-in whose account does not hold the unit is not a move-in:
            # the wizard's exit is "unit derives Occupied" (US-CUS-004 §1). The
            # DRAFT road stays open — it is `POST /accounts` (BR-CUS-018).
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-055",
                message_key="customers.account.status_does_not_occupy",
                params={"status": status.code, "behavior_class": status.behavior_class},
            )
        if reopen is not None:
            from apps.customers import move_in_reopen

            account = move_in_reopen.reopen_row(actor, reopen, cleaned)
        else:
            account = models.Account.objects.create(
                tenant_id=_tenant_id(),
                # ⊕ `CR-164-BRC10` wave 4 — a billing-only account names no unit.
                unit_id=None if billing_only else unit.id,
                billing_only=billing_only,
                # `CR-056` W1 — the ADDRESS, written from the unit at creation so the
                # column means the same thing on every row. ⚠ **THE MIGRATION 0036
                # BACKFILL FILLED IT FOR EVERY EXISTING ACCOUNT, ordinary ones
                # included**, so leaving it NULL here would make `f.premises_id=`
                # answer *the accounts opened before September* — a filter that is
                # right about history and wrong about today, which is worse than one
                # that is simply absent. `getattr` because the seam row is metering's
                # and this module does not own its shape.
                premises_id=getattr(unit, "premises_id", None),
                account_no=account_no or _allocate_account_no(),
                status=status,
                account_type=cleaned["account_type"],
                account_subtype=cleaned.get("account_subtype"),
                currency=_tenant_currency(),
                opened_at=cleaned.get("opened_at"),
                autopay=cleaned.get("autopay", False),
                # CR-052 task 14 — the election. `False` is the column's own default
                # and the fail-closed answer: a door that does not offer these keys
                # elects nothing, and the bill queues its print row alone.
                paperless=cleaned.get("paperless", False),
                sms_reminders=cleaned.get("sms_reminders", False),
                tax_exempt=cleaned.get("tax_exempt", False),
                tax_exempt_ref=cleaned.get("tax_exempt_ref"),
                tax_exempt_expires=cleaned.get("tax_exempt_expires"),
                # CR-122-BRC06 — the column's own default for every door that does
                # not offer the question, which is the honest answer for an account
                # nobody ever asked.
                eligibility_claimed=cleaned.get("eligibility_claimed", False),
                eligibility_note=cleaned.get("eligibility_note"),
                preferred_language=cleaned.get("preferred_language"),
                custom_data=cleaned.get("custom_data") or {},
                # ── `DEF-1661` — the five the import path declared and never wrote.
                # ⚠ **EACH FALLS BACK TO THE COLUMN'S OWN DEFAULT, NOT TO A VALUE
                # THIS LINE INVENTS**: a door that does not offer these keys (S18,
                # move-in) passes nothing, `cleaned` holds nothing, and the account
                # is created exactly as it was before this change. Only the import
                # path can put anything here, because only its `allowed` set
                # contains them.
                closed_at=cleaned.get("closed_at"),
                bad_address=cleaned.get("bad_address", False),
                deposit_on_file=(
                    cleaned["deposit_on_file"]
                    if cleaned.get("deposit_on_file") is not None
                    else Decimal("0")
                ),
                deposit_received_on=cleaned.get("deposit_received_on"),
                external_ref=cleaned.get("external_ref"),
            )
        if reopen is not None:
            # A reopened account already holds its contact and mailing rows;
            # what the clerk typed fills only what is EMPTY there (CR-181).
            from apps.customers import move_in_reopen

            contact, addresses = move_in_reopen.merge_people(account, contact, addresses)
        if contact is not None:
            models.Contact.objects.create(tenant_id=account.tenant_id, account=account, **contact)
        for address in addresses:
            models.Address.objects.create(tenant_id=account.tenant_id, account=account, **address)
        # ⛔ **CR-047 / `DEF-2518` — THE INHERITANCE IS NO LONGER INSIDE THE
        # OCCUPANCY BRANCH.** An occupying account takes the guards AND the
        # links, exactly as before; a non-occupying one takes ONLY the links,
        # and only through a door that asked for them. The `elif` is deliberate:
        # `_make_occupying` already wrote them, and running both would call
        # `_open_service_agreements` twice (harmless — it skips points already
        # linked — but it would report the count as zero the second time).
        created_links: list[Any] = []
        if billing_only:
            # ⊕ `CR-164-BRC10` wave 4 — holds no home: no occupancy guard and
            # no service agreement, so no cycle run can bill it for the home.
            pass
        elif is_occupying(status):
            created_links = _make_occupying(
                account,
                unit,
                warnings=warnings,
                require_plan=require_plan,
                chosen_services=chosen_services,
            )
        elif inherit_services:
            # ⚠ **A MIGRATED *CLOSED* ACCOUNT INHERITS ITS SERVICES CLOSED, AND
            # THAT IS NOT AN EXCEPTION TO THE RULING — IT IS THE RULING TOLD THE
            # TRUTH.** B2 §2 declares `ended_on` as *"NULL = still in force"*,
            # so writing an OPEN agreement for an account the old system had
            # already closed would state, in the database, that a finished
            # tenancy is current — and `selectors.service_codes_for` reads
            # exactly that column to badge S17's service chips. The links are
            # still written, because that is what the PO asked for and what
            # makes a final-bill reprint resolvable; they are simply dated
            # closed, through the same `_end_service_agreements` a real
            # move-out uses (BR-CUS-030). A terminal row with NO `closed_at`
            # keeps its agreements open: there is no date to close them with
            # and inventing one is BR-TEN-043's exact prohibition.
            terminal = status.behavior_class == CLASS_TERMINAL
            created_links = _inherit_service_links(
                account,
                started_on=_inheritance_started_on(account, inherit_started_on, terminal=terminal),
                chosen_services=chosen_services,
            )
            if terminal and account.closed_at is not None and created_links:
                # `max` rather than the raw close date: when the file's own two
                # dates contradict each other (a `closed_at` BEFORE its
                # `opened_at`) neither is ours to correct, and a same-day
                # agreement is the only reading that is not simply false.
                opened = min(row.started_on for row in created_links)
                _end_service_agreements(account, max(account.closed_at, opened))
        # `DEF-CUS-9170` — the answers typed on the unit step, on every
        # agreement this call opened. An occupying account whose unit has no
        # service point opens none, so an answer would land nowhere: refused
        # inside the transaction, which rolls the whole account back with it.
        if service_custom and not created_links:
            _refuse_fields(
                [
                    _field_error(
                        "service_custom_data",
                        errors.VAL_FORMAT,
                        "customers.account.service_fields_on_draft",
                    )
                ]
            )
        _write_service_custom_data(created_links, service_custom)
        if agreements_out is not None:
            agreements_out.extend(created_links)
        # ── CR-056 W3 task 15 — the door writes the customer link ───────────
        # INSIDE the same transaction as the account, deliberately: an account
        # that exists with its customer link half-written is the state CR-056
        # §4 describes on every Master Account in the product, and a rollback
        # that left one behind would be a new way to reach it.
        # ── `CR-058` task 3 — THE ONE RESOLVER, and the doors share it ─────
        customer_link = resolve_customer_for_account(
            actor=actor,
            account_id=account.id,
            block=cleaned.get("customer"),
        )
        account.refresh_from_db()
        # ⚠ **ONE SNAPSHOT, TWO CONSUMERS — `DEF-2480`, and it is half of
        # `DEF-2487`'s repair. THIS USED TO BE BUILT TWICE, ON CONSECUTIVE
        # LINES.** `DEF-2487` is the accounts import commit being SIGKILLed by
        # the 60-second gunicorn timeout at 1,048 rows, and this line is why a
        # row cost what it cost; the other half of that fix is the per-target
        # async bar in `apps/metering/import_runs.py`, which is where the id is
        # cited ten times. `account_detail_dict` is the whole S18
        # detail payload — contacts, addresses, service agreements, meters
        # through the assets seam, the unit and premises labels, the customer
        # number, the last invoice date and the ledger's AR position — and it
        # MEASURES AT 26 QUERIES on live PostgreSQL. Nothing mutates `account`
        # between the audit row and the return, so the second build was pure
        # waste. Measured on the accounts import LOAD, live PostgreSQL, at 45
        # rows: **107.6 queries and 128 ms per row before, 83.6 and 95 after** —
        # 24 queries a row, and 1,048 accounts fell from 128.1 s to 94.6 s.
        #
        # ⛔ **THE AUDIT ROW IS NOT WEAKENED AND MUST NOT BE.** Hard rule 7 makes
        # account creation a money action that writes `audit_log`, and the
        # after-blob is byte-identical to what it always was — the same complete
        # snapshot, built once instead of twice. `core.audit.write_row` calls
        # `jsonable(after)`, which converts eagerly into its own structure, so
        # sharing this dict with the return value cannot let a caller reach back
        # into the recorded row.
        # ── CR-094-BRC01 wave H · THE DEPOSIT, INSIDE THIS TRANSACTION ──────
        # The blueprint's own review panel states the order and the scope:
        # *"the account, then the reads, then the payment. One transaction."*
        # So a payment that cannot be recorded rolls the ACCOUNT back and the
        # clerk fixes the field with everything still on screen (`BR-SHL-019`),
        # which is the posture a refused opening reading already takes.
        #
        # ⚠ **BEFORE THE SNAPSHOT, DELIBERATELY.** `record_deposit_movement`
        # writes `accounts.deposit_on_file` under a lock inside this block, so
        # the snapshot below — the S18/S19 response body AND hard rule 7's
        # audit blob — must be built after it or the confirmation screen would
        # report a register of 0.00 over money it had just taken.
        #
        # ⚠ **FAIL-CLOSED KEYWORD, so only a door that asks in writing gets
        # it.** The S68 bulk import calls this function too and passes nothing:
        # a migrated deposit is `DEF-1713`'s path and is not this one.
        deposit_taken = deposit.take(actor, account, deposit_instruction, warnings=warnings)
        if deposit_instruction is not None:
            # ⚠ **`deposit_not_applied` IS FALSE ON A DOOR THAT JUST APPLIED
            # IT (2026-09-23, `DEF-CUS-6369`).** `_make_occupying` adds it to
            # every occupying account, and its sentence says the plan lookup
            # *"is not built"*. On S18/S19 the lookup has just run — the plan's
            # figure was taken, waived, or the plan asked none — so the
            # confirmation must not tell the clerk otherwise. Removed only
            # where `take()` ran; every other door keeps it.
            warnings[:] = [w for w in warnings if w.get("code") != "deposit_not_applied"]
        if deposit_taken is not None:
            account.refresh_from_db()
        snapshot = selectors.account_detail_dict(account)
        if deposit_taken is not None:
            snapshot = {**snapshot, "deposit": deposit_taken}
        _audit(actor, audit_action, account.id, after=snapshot)
    warnings.extend(_customer_not_created_warning(customer_link))
    return {**snapshot, **_customer_match_payload(customer_link), "warnings": warnings}


#: What a door reports back about the customer it just linked — and about the
#: one it REFUSED to link. `customer_match` is absent when no identity was
#: presented, because a key that is always there and usually null reads as a
#: feature that is always failing.
#:
#: ⚠ **`customer_not_created` IS THE SAME POSTURE FOR `BR-CUS-1023`** (PO
#: 2026-09-01): present ONLY where a door opened an account and minted no
#: Customer number, carrying the one thing that was missing. It is not an error
#: — the account is in the response beside it — and a screen that renders it as
#: one is saying the opposite of the ruling.
def _customer_match_payload(link: dict[str, Any] | None) -> dict[str, Any]:
    if not link:
        return {}
    out: dict[str, Any] = {
        # ⚠ **`CR-058` tasks 7 and 8 — THE ONE KEY A SCREEN READS.** Every door
        # already returned enough for a screen to WORK OUT what happened by
        # testing four other keys in the right order; none of them did, and
        # every account opened at the counter said only *"None"* where its
        # customer number should be. The outcome is stated in a word.
        "customer_outcome": link.get("outcome"),
        # `BR-CUS-1024` — TRUE when a name and a government identifier agreed
        # with a customer already on file. It is what earns the clerk *"this
        # looks like a customer you already have"* rather than silence.
        "customer_reused": bool(link.get("reused")),
    }
    match = link.get("match")
    if match is not None:
        out["customer_match"] = match
    not_created = link.get("not_created")
    if not_created is not None:
        out["customer_not_created"] = not_created
    return out


def _customer_not_created_warning(link: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The same fact as a WARNING row, for the doors that publish a warnings list.

    Two surfaces because there are two readers: `customer_not_created` is the
    structured answer a screen renders in its own words, and this is the entry
    that rides the door's existing `warnings` list so an operator reading the
    import summary or the master-account response sees it beside everything else
    that did not happen. Neither is a failure and neither refuses anything.
    """
    not_created = (link or {}).get("not_created")
    if not not_created:
        return []
    return [
        {
            "code": not_created["code"],
            "br_ref": "BR-CUS-1023",
            "message_key": not_created["message_key"],
            "missing": not_created["missing"],
            "kind": not_created["kind"],
        }
    ]


#: ⚠ **`_link_customer_from_payload` WAS HERE AND IS RETIRED (`CR-058` task 3).**
#: It translated a door's `customer` block into the one link write, and both
#: doors then re-assembled the answer around it in their own words. Its job and
#: its reasoning move WHOLE into `resolve_customer_for_account` below, which is
#: the single function `CR-058` asks every account-opening door to call — *"no
#: door may repeat this logic; a second copy is how two doors start disagreeing
#: about who a customer is"*. It is deleted rather than left as a second entry
#: point: a helper that still works is a helper a fifth door will find.

# ═══════════════════════════════════════════════════════════════════════════
# `CR-058` TASK 3 — **ONE FUNCTION, EVERY ACCOUNT-OPENING DOOR**
# ═══════════════════════════════════════════════════════════════════════════
#: The three words a door reports back, and the ONLY three. `CR-058` tasks 7 and
#: 8 ask both wizards to show the clerk *which of the three things happened*, so
#: the answer is a WORD the server states rather than a shape a screen infers
#: from which keys happen to be present.
OUTCOME_LINKED = "linked"
OUTCOME_CREATED = "created"
OUTCOME_NONE = "none"


def refuse_account_without_identity(
    block: Any,
    *,
    fallback_name: str | None = None,
    br_ref: str = "BR-CUS-1024",
) -> None:
    """`BR-CUS-1024` — **no identifier, no account.** Raises, or returns None.

    **PO verbatim, 2026-09-01:** *"Without identifier we cannot create Customer
    ID or master account ot regular account"*.

    ⛔ **THIS REVERSES A CLAUSE SIGNED THE SAME MORNING, AND THE SUPERSESSION IS
    QUOTED RATHER THAN ASSUMED.** `BR-CUS-1023` said: *"An account may still be
    opened. This rule is about the CUSTOMER #, not about service: a person
    standing at the counter who will not give an identifier still gets their
    water."* **That paragraph is SUPERSEDED** (decision log 2026-09-01). The
    identifier is now a condition on the ACCOUNT, not on the number alone.

    **THE THREE ROWS, and the third one is why this function can return quietly:**

        name + at least one identifier  ->  nothing raised; the door proceeds
        name alone                      ->  RAISED — no customer, no account
        no name                         ->  unchanged; nothing raised

    ⚠ **THE `no name` ROW IS THE PO'S OWN AND IS NOT A LOOPHOLE THIS FUNCTION
    INVENTED.** It is the row that keeps every in-process creator working — a
    transfer, a seed, a service request that opens an account for a party named
    elsewhere — and it cannot be reached from either wizard, because step 1 of
    both refuses to advance without a name. A door that presents NO party at all
    is not a door that failed to identify one.

    ⚠ **IT IS CALLED BEFORE THE TRANSACTION OPENS, NEVER INSIDE IT.** The whole
    reason `link_customer` skips rather than raising is that it runs inside the
    door's own `transaction.atomic()`, where an exception rolls a half-written
    account back. This runs FIRST, so a refused request writes nothing at all
    and the clerk fixes the field with everything still on screen.

    ⚠ **AND IT NAMES WHAT IS MISSING IN THE CLERK'S OWN WORDS.** No rule id and
    no internal code reaches the message (B14 rule 32 clause 4); the rule id
    rides in `br_ref`, which is where a payload's machinery belongs. The wording
    follows the KIND, because the TEST does — telling a business it needs a
    driving licence sends somebody to find a document that does not exist.
    """
    data = block if isinstance(block, dict) else {}
    name = _text(data.get("display_name"), 200) or _text(fallback_name, 200)
    if not name:
        # The PO's third row. Nothing was presented, so nothing failed to
        # identify itself.
        return
    evidence = identity_match.from_payload(
        data.get("identity"), kind=identity_match.normalise_kind(data.get("kind"))
    )
    if not evidence.name:
        evidence = replace(evidence, name=name)
    # A clerk who names an existing customer outright, or hands over a legacy
    # reference that RESOLVES, is pointing at a row that ALREADY EXISTS — the
    # rule is about opening an account for a party nobody can identify, and
    # those parties are identified. Same carve-out `BR-CUS-1023` makes for
    # linking, for the same reason.
    #
    # ⚠ **"THAT RESOLVES" IS NOW CHECKED, AND UNTIL 2026-09-01 IT WAS ONLY
    # CLAIMED (hard-won law 1: a comment claiming a guarantee is not the
    # guarantee).** The test was `if <a reference was sent>`, so ANY string in
    # `external_ref` — including one this tenant has never seen — walked an
    # account past the rule. It was found by putting the tenant seed THROUGH the
    # rule instead of around it: every seeded row carries a `customer_key`, so
    # all 48 would have taken this exit and the "the seed proves the rule end to
    # end" claim would have been hollow. A reference that resolves to nothing is
    # not an identification; it is a value nobody has checked.
    if data.get("customer_id") not in (None, ""):
        return
    ref = _text(data.get("external_ref"), 120)
    if (
        ref
        and models.Customer.objects.filter(
            tenant_id=_tenant_id(), external_ref__iexact=ref
        ).exists()
    ):
        return
    shortfall = identity_match.creation_minimum(evidence)
    if shortfall is None:
        return
    payload = identity_match.not_created_payload(shortfall)
    raise errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=br_ref,
        message_key=ACCOUNT_IDENTITY_MESSAGE_KEY[(shortfall["missing"], shortfall["kind"])],
        params={
            "missing": shortfall["missing"],
            "kind": shortfall["kind"] or "",
            "accepts": list(shortfall["accepts"]),
            # The same code the not-created payload uses, so a screen that
            # already knows how to read one outcome can read the other.
            "code": payload["code"],
        },
    )


#: The clerk's sentence when the ACCOUNT is refused, keyed per kind exactly as
#: `identity_match.NOT_CREATED_MESSAGE_KEY` is.
#:
#: ⚠ **THESE ARE NEW KEYS RATHER THAN A REUSE OF THE NOT-CREATED ONES, AND THE
#: DIFFERENCE IS THE WHOLE RULING.** Those sentences open *"No customer number
#: yet: …"*, which was true and complete while the account opened regardless.
#: It is now an understatement of what just happened, and a clerk reading it
#: would look for the account that was not created. Both sets stay: the old ones
#: still serve the doors that are NOT gated.
ACCOUNT_IDENTITY_MESSAGE_KEY: dict[tuple[str, str | None], str] = {
    (identity_match.MISSING_NAME, None): "customers.account.identity_name_required",
    (identity_match.MISSING_NAME, identity_match.KIND_PERSON): (
        "customers.account.identity_name_required"
    ),
    (identity_match.MISSING_NAME, identity_match.KIND_COMPANY): (
        "customers.account.identity_name_required"
    ),
    (identity_match.MISSING_KIND, None): "customers.account.identity_kind_required",
    (identity_match.MISSING_IDENTIFIER, identity_match.KIND_PERSON): (
        "customers.account.identity_required_person"
    ),
    (identity_match.MISSING_IDENTIFIER, identity_match.KIND_COMPANY): (
        "customers.account.identity_required_company"
    ),
}


def resolve_customer_for_account(
    *,
    actor: Any,
    account_id: Any,
    block: Any,
    fallback_name: str | None = None,
) -> dict[str, Any] | None:
    """`CR-058` task 3 — **the ONE act every account-opening door performs.**

    **PO verbatim (2026-09-01, the ruling that governs all the others):**
    *"During regular and master account creation process - we check whether we
    ahve mathicng customer ID, if yes, we use it if no we create it, given we
    have identify atleast 1"*.

        a matching customer is found            ->  USE IT. Never a second #.
        no match, and an identifier is present  ->  CREATE one.
        no match, and NO identifier             ->  refused at the door, before
                                                    this is ever reached.

    **FOUR DOORS CALL IT AND NONE OF THEM REPEATS ITS LOGIC** — `POST /accounts`
    (S18), `POST /accounts/{id}/move-in` (S19), `POST /accounts/master`, and
    through that last one New Connect and the premises-owner door, both of which
    reach it through the customers seam. A second copy is how two doors start
    disagreeing about who a customer is, which is not hypothetical here:
    `DEF-2587` is one landlord holding three customer numbers.

    ⚠ **IT DELEGATES AND DOES NOT DUPLICATE.** `link_customer` remains the ONE
    writer of `customer_accounts` (LAW 0), `identity_match` remains the only
    place a match is judged, and this function adds exactly one thing neither of
    them had: **it names the OUTCOME in a word.**

    **WHY THAT WORD IS THE POINT.** The server has always known whether it
    linked or created; it recorded the fact in `audit_log` and dropped it from
    the response, so no screen could tell a clerk which of the three things had
    happened. `CR-058` tasks 7 and 8 ask for exactly that sentence at the
    counter. `outcome` is `linked` · `created` · `none`, and a screen reads one
    key instead of inferring from which of four others happen to be present.

    ⚠ **A REUSE IS A LINK, NOT A CREATE.** `BR-CUS-1024`'s name-plus-government-
    identifier agreement returns `linked` with `reused: True` beside it, because
    what the clerk needs to hear is *"this looks like a customer you already
    have"* — the same sentence a `strong` match earns, on a different test.

    Returns `None` only when no party was named at all, which is a real state
    and not a gap: an account may lawfully be opened before anybody knows whose
    it is, and every account created before the `BR-CUS-054` entity existed has
    no link.
    """
    data = dict(block) if isinstance(block, dict) else {}
    if fallback_name and not _text(data.get("display_name"), 200):
        # ⚠ **THE MASTER DOOR'S OWN FALLBACK, LIFTED HERE SO IT IS NOT A SECOND
        # COPY OF THE RULE.** A premises' `owner_manager` is FREE TEXT: it may
        # name a person or a limited company and nothing in it says which. So
        # where the door supplies no name of its own the block carries THAT one,
        # states no kind, and under `BR-CUS-1024` that is now a refusal at the
        # door rather than an account with nobody identifiable behind it.
        #
        # ⚠ **IT FILLS A MISSING NAME RATHER THAN ONLY AN EMPTY BLOCK**, so a
        # caller that knows the KIND and the IDENTIFIER but reads the name off
        # the premises — the tenant seed's estate owner is exactly this — does
        # not have to carry a second copy of a name the address already holds.
        # A name the caller DID state always wins; this never overwrites one.
        data = {**data, "display_name": fallback_name}
    if not data:
        return None

    link = link_customer(
        account_id=account_id,
        external_ref=data.get("external_ref"),
        display_name=data.get("display_name"),
        kind=data.get("kind"),
        identity=data.get("identity"),
        customer_id=data.get("customer_id"),
        actor=actor,
        custom_data=data.get("custom_data"),
    )
    if link is None:
        return None

    if link.get("not_created"):
        outcome = OUTCOME_NONE
    elif link.get("created"):
        outcome = OUTCOME_CREATED
    else:
        outcome = OUTCOME_LINKED
    return {**link, "outcome": outcome}


# ── BR-CUS-068: the master account over a premises' common areas ────────────
def _master_attachment_units(premises_id: Any, data: dict[str, Any]) -> list[Any]:
    """The unit MODEL rows the master account will cover, validated.

    Default = every active common-area unit of the premises, in the seam's
    deterministic (label, id) order — the first is the ANCHOR the master row's
    `unit_id` points at (accounts.unit_id holds exactly one unit, BR-CUS-017,
    so the REST of the coverage rides `service_agreements`; decision log
    2026-08-22). An explicit `unit_ids` list narrows the set and every entry
    is checked: BR-CUS-068 — the master path attaches ONLY common-area units,
    refusing anything else BY NAME.
    """
    common = seams.common_area_units_for_premises(premises_id)
    if not common:
        # ⚠ **THIS REFUSAL IS GONE — `CR-056` W1 TASK 9, AND ITS STATED REASON IS
        # WHAT THE RULING REMOVED.** It refused a premises with nothing shared
        # because a master had to ANCHOR on a common-area unit and there was none
        # to anchor on. `BR-CUS-1010` moves the account onto the ADDRESS, so a
        # premises with no shared space is the ordinary case rather than the
        # impossible one: the PO ruled on 2026-08-31 that *every address gets its
        # owner a Master Account, whether or not anything is shared*.
        #
        # A caller that NAMED units still gets its named-unit refusal below; this
        # only stops the empty default from being an error. The account then
        # covers nothing, bills nothing and produces no document — which is the
        # same ruling's *no lines, no document*, and is `CR-056` W4's to build,
        # not this lane's. Nothing here decides anything about a bill.
        requested = data.get("unit_ids")
        if requested in (None, []):
            return []
    common_ids = {row["id"] for row in common}
    requested = data.get("unit_ids")
    if requested in (None, []):
        ordered_ids = [row["id"] for row in common]
    else:
        if not isinstance(requested, (list, tuple)):
            raise errors.ValidationError(
                errors.VAL_FORMAT, message_key="customers.payload_not_object"
            )
        ordered_ids = []
        for unit_id in requested:
            unit_id = str(unit_id)
            if unit_id not in common_ids:
                # The refusal NAMES the unit: either it is not a common area,
                # or it belongs to another premises / is deactivated — the seam
                # answers only this premises' ACTIVE common areas, and a
                # cross-tenant id 404s inside unit_row below before this list
                # could ever hold it.
                unit_label = None
                try:
                    row = seams.unit_row(unit_id)
                    unit_label = getattr(row, "label", None)
                except errors.NotFoundError:
                    pass
                raise errors.BizError(
                    errors.BIZ_STATE,
                    br_ref="BR-CUS-068",
                    params={
                        "unit_id": unit_id,
                        "label": unit_label,
                        "premises_id": str(premises_id),
                        "reason": "not_a_common_area_of_this_premises",
                    },
                )
            if unit_id not in ordered_ids:
                ordered_ids.append(unit_id)
        # Keep the seam's deterministic order regardless of payload order, so
        # the anchor does not depend on how a client happened to sort a list.
        ordered_ids.sort(key=lambda uid: [row["id"] for row in common].index(uid))
    return [seams.unit_row(unit_id) for unit_id in ordered_ids]


def _open_master_service_agreements(
    account: models.Account, unit_rows: list[Any], started_on: date
) -> dict[str, list[Any]]:
    """One SA row per active service point on EVERY covered common-area unit —
    the same rows `_open_service_agreements` writes for an ordinary account's
    single unit, which is what BR-CUS-068's "the SAME account–unit linkage
    every account uses" buys: the billing linkage with no new table."""
    created: list[Any] = []
    unbillable: list[Any] = []
    for unit in unit_rows:
        points = seams.service_points_for(unit.id)
        if not points:
            unbillable.append(unit)
            continue
        for point in points:
            created.append(
                models.ServiceAgreement.objects.create(
                    tenant_id=account.tenant_id,
                    account=account,
                    service_point_id=point["id"],
                    started_on=started_on,
                )
            )
    return {"created": created, "unbillable": unbillable}


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def create_master_account(
    actor: Any,
    payload: Any,
    *,
    require_identity: bool = True,
    customer_fields_screen: str | None = None,
) -> dict[str, Any]:
    """POST /accounts/master — the ROLE-GUARDED door. The door itself is
    `_create_master_account` below, and its docstring is the one to read.

    ⚠ **TWO DOORS SINCE 2026-10-02 (`DEF-CUS-9132`), AND THE SPLIT IS ABOUT ONE
    CALL.** `DEF-CUS-9078` put `_record_request_customer` inside the door, and
    that helper writes through `service_request_service.link_customer`, which is
    `@require_role`-guarded. The premises import's background jobs reach the door
    through `import_writer.create_master_account_from_import` with `_JobActor` —
    an id and NO role, by design — so a guarded call in the door's body is a
    call that can only ever REFUSE a job. Nothing refused at runtime, because the
    import never names a request and the helper returns first; but that is the
    argue-the-branch posture G140 exists to forbid (`DEF-1108`, `DEF-2515` and
    `DEF-AST-8102` were each one edit away from it), so the call is kept OFF the
    job's path instead.

    **Recording the request's customer is a REQUEST-PATH act** — a clerk at
    `POST /accounts/master`, or New Connect carrying a build to ACTIVE — and both
    reach THIS function, which has already checked the same role set
    `link_customer` checks (`SYSTEM_ADMIN`, `BILLING_CLERK`). So it happens here,
    after the door, and under ONE outer transaction so a refused link still rolls
    the account back with it, exactly as it did when the call sat inside the
    door's own `atomic` block. No permission check moved or widened: this door's
    guard is unchanged and `link_customer` keeps its own.
    """
    request_id = _payload_dict(payload).get("service_request_id")
    with transaction.atomic():
        result = _create_master_account(
            actor,
            payload,
            require_identity=require_identity,
            customer_fields_screen=customer_fields_screen,
        )
        _record_request_customer(actor, request_id, result["id"])
        # `DEF-CUS-9211` — the request's own fields reach the account it opened.
        _carry_request_custom_answers(actor, request_id, result["id"])
    return result


#: The fields New Connection's owner block may carry to the owner's REGULAR
#: account (`create_build_owner_account`) — the master door's own payload, so
#: one caller (`metering.connections.create_owner_account`) assembles one dict
#: for both doors. `premises_id` and `unit_ids` are the master door's anchor
#: and are dropped here: a regular account anchors on its ONE unit.
BUILD_OWNER_DROPPED_FIELDS: frozenset[str] = frozenset({"premises_id", "unit_ids"})


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def create_build_owner_account(
    actor: Any,
    payload: Any,
    *,
    unit_id: Any,
    customer_fields_screen: str | None = None,
    lives_there: bool = True,
) -> dict[str, Any]:
    """**`DEF-CUS-9228` — a single-family New Connection opens the OWNER's own
    REGULAR account, and the build's charges are billed to it.**

    ⊕ **`lives_there` — `CR-164-BRC10` wave 4, PO ruling 2026-10-03, verbatim:
    *"C By owner type: an owner who lives there holds it; a landlord or builder
    doesn't"*.** Shown: *Maria owns 14 Oak St; if she is a landlord, her tenant
    (Then *"B"*, then *"i dont know yet"* — the owner-occupier half is `OQ-CUS-12785`, OPEN.)
    Jose cannot move in until her account is moved out.* With `lives_there`
    False the account is opened BILLING ONLY (`_open_account(billing_only=True)`):
    the premises and no unit, no occupancy guard, no service agreement. It is
    billed the build's charges by name and holds nothing, so 14 Oak St stays
    Vacant and Jose's Move-in needs nobody moved out. The caller decides which
    (`metering.connections.owner_lives_there`); this door never reads a type.

    PO ruling 2026-10-02 (decision log, *"SEVEN PO ANSWERS IN ONE MESSAGE"*,
    item 1), verbatim: *"A. The owner asked for the work, so the owner pays.
    With B, the bill could land on a tenant who moves in later, or never go
    out at all."* Shown: *Maria, single-family at 14 Oak St, $90 connection
    fee + $30 inspection = $120*, billed to Maria's own account at Create.

    **WHY A REGULAR ACCOUNT ON THE ONE HOME, AND NOT A MASTER.** `BR-CUS-1114`
    (amended by `CR-162-BRC10` Q1) gives a single-family type no master
    account, and that rule is unchanged — `_refuse_master_on_single_unit_premises`
    still refuses one. The schema's `ck_accounts_regular_has_unit` binds a
    regular account to a unit, and a single-family build has exactly one home,
    so that is where it anchors.

    **ONE DOOR, NOT A SECOND CREATOR.** It is `_open_account` — the door S18,
    S19 and the import already share — so `BR-CUS-017`'s occupancy guards,
    `BR-MET-040`'s plan requirement, `BR-CUS-1024`'s identity rule and the
    customer resolver apply exactly as they do at the counter.

    **CREATED ACTIVE, THEN HELD PENDING BY THE CALLER — THE MASTER ACCOUNT'S
    OWN LIFECYCLE** (`hold_new_master_pending`'s docstring has the measurement):
    billing's door refuses a `non_billable` account, and the Create act posts
    the build's charges and any payment taken inside the same transaction, so
    the account must be billable for that one act. The commit then holds it in
    `pending_activation` and the build's first approval makes it Active
    (`activate_pending_master_account`, which now takes this account too).

    **MOVE-IN IS UNTOUCHED.** No move-in job is closed and no move record is
    written: an occupant still opens their own account by Move-in. While the
    build is pending this account occupies nothing (`BR-CUS-018`), so a Move-in
    before approval goes through as it always did.

    Audited (hard rule 7) as `account.created_for_build_owner`.

    HUMAN-REVIEW-PENDING — 🔒 money path (WHO a build's issued charges and the
    payment taken at Create are billed to). AI-authored 2026-10-02 under the PO
    ruling of 2026-08-09; row in `12-governance/09-human-review-ledger.md`
    (`DEF-CUS-9228`). No price, rate or rounding moved: the charges are raised
    by the same billing door the master account's are."""
    data = dict(_payload_dict(payload))
    request_id = data.pop("service_request_id", None)
    for key in BUILD_OWNER_DROPPED_FIELDS:
        data.pop(key, None)
    data = _carry_request_decisions(data, request_id)
    data["unit_id"] = str(unit_id)
    data["status"] = "active"
    with transaction.atomic():
        result = _open_account(
            actor,
            data,
            audit_action="account.created_for_build_owner",
            require_identity=True,
            customer_fields_screen=customer_fields_screen,
            billing_only=not lives_there,
        )
        _record_request_customer(actor, request_id, result["id"])
        # `DEF-CUS-9211` — the request's own fields reach the account it opened.
        _carry_request_custom_answers(actor, request_id, result["id"])
    return result


def _create_master_account(
    actor: Any,
    payload: Any,
    *,
    require_identity: bool = True,
    customer_fields_screen: str | None = None,
) -> dict[str, Any]:
    """POST /accounts/master — ONE ordinary `accounts` row, `kind='master'`,
    payer = the premises' owner/manager.

    ⚠ **THE ACCOUNT HANGS OFF THE ADDRESS FROM 2026-09-01 (`CR-056` W1,
    `BR-CUS-1010`).** `BR-CUS-068` (PO 2026-08-22, `OQ-314`'s second half) said
    *attached to the premises' COMMON-AREA UNITS*, and that clause is superseded
    at its own sentence: the row now writes `premises_id` and leaves `unit_id`
    NULL, and the common areas are reached through `service_agreements` like any
    other covered unit. **A shared space is something this account is CHARGED
    FOR, not the thing it hangs off.** Everything else about `BR-CUS-068` — an
    ordinary row, `kind='master'`, no new table, coverage through the same
    account–unit linkage — is unchanged and still CONFIRMED.

    **WHAT THE MONEY DOES: NOTHING.** `covered_unit_ids` used to answer *anchor
    + the SA units* and now answers *the SA units*, in the same (label, id)
    order, so `1408 Elm Street` still bills `$41.20` of hallway plus `$28.40` of
    irrigation = **`$69.60` on one owner document**
    (`tests/test_br_cus_068_master_bill.py` tc1). Accounts created before
    migration 0036 keep the anchor they were created with and bill exactly what
    they billed before it (`CR-056` task 6).

    **AND A PREMISES WITH NOTHING SHARED IS NO LONGER REFUSED** (`CR-056` task
    9). The old refusal's stated reason was that a master needed a common area to
    anchor on; there is no anchor now, and the PO ruled on 2026-08-31 that *every
    address gets its owner a Master Account, whether or not anything is shared*.
    Such an account covers nothing and therefore bills nothing — *no lines, no
    document* is the same ruling's general rule and is `CR-056` W4's to build.

    Created ACTIVE and attached in one call, deliberately — no draft stage:
    an unattached master account is exactly the half-built state the ruling
    closed, and the BR-CUS-018 draft default is the S18 wizard's rule, not
    this path's (decision log 2026-08-22). ONE transaction; audited (rule 7).

    The guard set per covered unit is BR-CUS-017's family, enforced under the
    same per-unit advisory locks the ordinary path takes: an occupying account
    on the unit refuses by name, a second MASTER already covering the unit
    (through its open service agreements) refuses by name, and a common area
    with no plan refuses per BR-MET-040 — its BR-MET-101 figures ($41.20 +
    $28.40 = $69.60) price from the unit's plan like every other bill.

    ⚠ **AND ONE GUARD THAT IS ABOUT THE ADDRESS RATHER THAN A UNIT**
    (`BR-CUS-1011`, `_refuse_if_premises_has_master`): a premises that already
    has an active Master Account refuses. It is not a duplicate of the covered-
    unit guard — that one structurally cannot fire on a premises with no common
    area, which is now a premises this door accepts.

    ⛔ **AND SINCE 2026-09-01, A GUARD ABOUT THE PARTY (`BR-CUS-1024`).** PO
    verbatim: *"Without identifier we cannot create Customer ID or master
    account ot regular account"*, said in answer to the question *whether a
    master account is created when the owner has a name and no identifier*. So
    this door refuses an owner it cannot identify, before it writes anything.

    **`require_identity` DEFAULTS TO ON HERE AND ONLY HERE**, because this is the
    door the PO's question was actually about. Every other creator in the product
    takes the keyword fail-closed and has to ask for the new behaviour in
    writing; this one has to ask to be EXCUSED from it, which is the right way
    round for the door a ruling names.

    ⚠ **AND IT REACHES TWO MORE DOORS BY INHERITANCE, WHICH IS RULING 2 OF THE
    SAME DAY.** New Connect (`metering.connections.create_owner_account`) and the
    premises-owner door (`metering.premises_owners`) both create their master
    account by resolving THIS function through the customers seam, so both are
    under the rule without a second copy of it — and both now pass the customer
    block through instead of a contact alone. PO on New Connect: *"we have to
    create it if not matching customer ID not available, - rest is correct"*.
    """
    from apps.customers import selectors

    data = dict(_payload_dict(payload))
    # `DEF-CUS-9036` — the approved request this master account fulfils. POPPED
    # for `move_in`'s reason (`accounts` has no such column); the request's own
    # linked customer and class are carried exactly as a move-in carries them.
    master_request_id = data.pop("service_request_id", None)
    _reject_unknown(data, MASTER_CREATE_FIELDS)
    data = _carry_request_decisions(data, master_request_id)
    if master_request_id and not data.get("account_type"):
        # The owner's build account's own default (`create_owner_account`),
        # reached only when neither the caller nor the request named a class.
        data["account_type"] = "commercial"
    fe: list[dict[str, Any]] = []

    premises_id = data.get("premises_id")
    if premises_id in (None, ""):
        fe.append(
            _field_error("premises_id", errors.VAL_REQUIRED, "customers.account.unknown_field")
        )
        _refuse_fields(fe)
    premises = seams.premises_ref(premises_id)  # 404-never-403 cross-tenant (HR-1)

    account_type = _resolve_account_type(data.get("account_type"), fe)
    account_subtype = (
        _resolve_account_subtype(data.get("account_subtype"), fe)
        if "account_subtype" in data
        else None
    )
    opened_at = _date(data.get("opened_at"), "opened_at", fe)
    _refuse_fields(fe)
    if opened_at is None:
        # Same posture as BR-CUS-022 on the ordinary path: the SAs need a
        # started_on and an attached account without one could never be billed.
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-CUS-022",
            message_key="customers.account.start_date_required",
            params={"field": "opened_at"},
        )

    contact = _validate_contact(data.get("contact"))
    if contact is None:
        # PO 2026-08-22: "payer = the premises' owner/manager". The premises'
        # own owner_manager is the default payer; a premises without one and a
        # payload without a contact leaves nobody to bill, which is refused
        # rather than guessed.
        owner = (premises.get("owner_manager") or "").strip()
        if not owner:
            _refuse_fields(
                [
                    _field_error(
                        "contact.full_name",
                        errors.VAL_REQUIRED,
                        "customers.contact.name_required",
                        reason="premises_has_no_owner_manager",
                        premises_id=str(premises_id),
                    )
                ]
            )
        contact = {
            "full_name": owner[:200],
            "email": None,
            "phone": None,
            "dob": None,
            "gov_id_last4": None,
            "is_primary": True,
        }
    addresses = _validate_addresses(data.get("addresses"))
    # CR-056 W3 task 17 — the SAME validator the ordinary door uses, so an
    # unknown key inside `customer` is refused identically on both. A second
    # copy of this validation is how one door starts accepting an identifier
    # the other refuses.
    customer_fe: list[dict[str, Any]] = []
    # ⊕ `CR-164-BRC10` wave 2 — a door that DRAWS the owner's customer fields
    # names its slot (`NEW_CONNECTION_OWNER` from New Connection Step 1), so a
    # required customer field binds there and nowhere else (BR-TEN-052 as
    # amended). Every other caller passes none, exactly as before.
    data["customer"] = _validate_customer_block(
        data.get("customer"), customer_fe, custom_data_screen=customer_fields_screen
    )
    _refuse_fields(customer_fe)
    if "custom_data" in data:
        # The master doors open an account from New Connection / New account —
        # the S18 slot (`DEF-TEN-9157`).
        custom_data = seams.validate_custom_data("accounts", data.get("custom_data"), screen="S18")
    else:
        custom_data = {}

    # ── `DEF-CUS-8020` — THE OTHER HALF OF WIDENING THE ALLOW LIST ──────────
    # `MASTER_CREATE_FIELDS` now PERMITS the four billing preferences; this is
    # what WRITES them. Doing only the first half is `DEF-1661` exactly — a
    # field declared lawful, accepted by `_reject_unknown`, cleaned by nobody
    # and written by nothing, with every test green — and it would have turned
    # a visible 422 into four boxes silently discarded, which is the worse of
    # the two failures because nothing tells the clerk.
    #
    # Cleaned by the SAME function the ordinary door uses, and the field errors
    # join `fe` so a bad `tax_exempt_expires` refuses here exactly as it
    # refuses there. Absent keys are absent, never `False` — see the helper.
    billing_preferences = _billing_preferences(data, fe)
    # ⊕ `CR-164-BRC10` — the same three the ordinary door cleans
    # (`_validate_account`), cleaned the same way; absent stays absent so the
    # column default applies, exactly as `_billing_preferences` treats its four.
    communication_preferences: dict[str, Any] = {}
    if "preferred_language" in data:
        communication_preferences["preferred_language"] = _clean_language(
            data.get("preferred_language"), fe
        )
    for flag in ("paperless", "sms_reminders"):
        if flag in data:
            communication_preferences[flag] = _bool(data.get(flag))
    _refuse_fields(fe)

    if require_identity:
        # `BR-CUS-1024` — before the transaction, so a refused request writes
        # nothing at all. The fallback name is the one this door would otherwise
        # have minted a customer from: the payload's contact, or failing that
        # the premises' own free-text `owner_manager`. **A free-text owner name
        # is a NAME and not an identity**, which is precisely the case the PO
        # was asked about and precisely the one they closed.
        refuse_account_without_identity(
            data.get("customer"),
            fallback_name=(contact or {}).get("full_name"),
        )

    warnings: list[dict[str, Any]] = []
    with transaction.atomic():
        unit_rows = _master_attachment_units(premises_id, data)
        # Deterministic lock order across ALL covered units (BR-CUS-017's own
        # locking discipline, extended to a multi-unit decision), then every
        # check runs under the locks.
        for unit in sorted(unit_rows, key=lambda row: str(row.id)):
            lock_unit_scope(unit.id)
        for unit in unit_rows:
            _refuse_if_unit_occupied(unit.id)
            _refuse_if_master_covered(unit)
            _require_plan_on_unit(unit)
        _refuse_if_premises_has_master(premises_id)
        # `BR-CUS-1114` (PO 2026-10-02) — after `BR-CUS-1011`, so an address
        # that already HAS an owner account still answers with that account
        # (`ensure_master_account_for_premises` reads that refusal as *already
        # there*); only a NEW master on a one-unit address is refused here.
        _refuse_master_on_single_unit_premises(premises_id)
        account = models.Account.objects.create(
            tenant_id=_tenant_id(),
            # ── `CR-056` W1 · `BR-CUS-1010` — THE ACCOUNT HANGS OFF THE ADDRESS.
            # It used to be `unit_id=unit_rows[0].id`, the premises' first common
            # area, and the rest of the coverage rode `service_agreements`. Now
            # ALL of the coverage rides them — the first common area included —
            # so a shared space is something this account is CHARGED FOR rather
            # than the thing it hangs off. **Nothing about what it bills moves:**
            # `covered_unit_ids` answers the anchor plus the SA units and now
            # answers the SA units alone, in the same (label, id) order, so
            # `1408 Elm Street` is still $41.20 + $28.40 = $69.60 on one
            # document. Accounts created before migration 0036 keep the anchor
            # they were created with (`CR-056` task 6).
            unit_id=None,
            premises_id=premises_id,
            account_no=_allocate_account_no(),
            status=_default_active_status(),
            account_type=account_type,
            account_subtype=account_subtype,
            kind=ACCOUNT_KIND_MASTER,
            currency=_tenant_currency(),
            opened_at=opened_at,
            custom_data=custom_data,
            # `DEF-CUS-8020`. Splatted rather than named four times so an absent
            # key takes the COLUMN's default instead of this door choosing one.
            **billing_preferences,
            **communication_preferences,
        )
        models.Contact.objects.create(tenant_id=account.tenant_id, account=account, **contact)
        for address in addresses:
            models.Address.objects.create(tenant_id=account.tenant_id, account=account, **address)
        agreements = _open_master_service_agreements(account, unit_rows, opened_at)
        for unit in agreements["unbillable"]:
            # Same honesty pattern as the J2 warnings: an attached common area
            # with no service points produces no SA and therefore no bill line;
            # said out loud rather than silently succeeding.
            warnings.append(
                {
                    "code": "unit_has_no_service_points",
                    "br_ref": "BR-CUS-068",
                    "unit_id": str(unit.id),
                    "label": unit.label,
                }
            )
        # ── CR-056 W3 task 17 — the Master Account door links its customer ──
        # CR-056 §4, measured: *"Every Master Account in the product has a
        # blank customer column."* Under the 2026-08-31 ruling a Master Account
        # IS the owner's account at an address, so the party it belongs to is
        # not decoration — it is the point of the row.
        #
        # ⚠ **THE FALLBACK IS THE PREMISES' OWN OWNER NAME, AND IT IS A NAME
        # AND NOT AN IDENTITY.** `contact["full_name"]` above already defaults
        # to `premises.owner_manager` when the payload names no contact; the
        # same string becomes the customer's `display_name` here so a master
        # account is never created with nobody on it. It presents NO identity
        # evidence, so it can never earn a `strong` tier and can never carry a
        # deposit — which is right: a free-text owner name is what CR-056 exists
        # to stop treating as a person.
        # ⚠ **CR-056 W2b's BESPOKE FALLBACK IS GONE FROM HERE AND LIVES IN THE
        # RESOLVER (`CR-058` task 3).** It used to build `{"display_name":
        # contact["full_name"]}` inline, which was a second copy of a rule the
        # ordinary door also has — and a second copy is how two doors start
        # disagreeing about who a customer is. The behaviour is unchanged: a
        # premises' `owner_manager` is free text, it may name a person or a
        # limited company, nothing in it says which, so the block carries a NAME
        # and states no kind.
        customer_link = resolve_customer_for_account(
            actor=actor,
            account_id=account.id,
            block=data.get("customer"),
            fallback_name=contact.get("full_name"),
        )
        account.refresh_from_db()
        # `DEF-2480` — one 26-query snapshot, two consumers. Same shape and same
        # reasoning as `_open_account` above: nothing mutates `account` between
        # these two lines, and the audit blob is unchanged.
        snapshot = selectors.account_detail_dict(account)
        _audit(
            actor,
            "account.master_created",
            account.id,
            after=snapshot,
        )
        jobs_closed = _fulfil_request_with_master(actor, master_request_id, account)
        # `DEF-CUS-9132` — the request's customer is recorded by the guarded
        # `create_master_account` AFTER this returns, inside its own outer
        # transaction, so the role-guarded `link_customer` is off every job's
        # path (G140). Do not move it back in here.
    # `BR-CUS-1023` — the premises' free-text owner name is a NAME and not an
    # identity, so this door most often mints nothing and says so out loud.
    warnings.extend(_customer_not_created_warning(customer_link))
    return {
        **snapshot,
        **_customer_match_payload(customer_link),
        "warnings": warnings,
        "move_in_jobs_closed": jobs_closed,
    }


def _fulfil_request_with_master(actor: Any, request_id: Any, account: Any) -> int:
    """`DEF-CUS-9036` — **an approved request can be fulfilled by a MASTER
    account, and its pending move-in job then leaves the queue.**

    PO ruling 2026-10-01: a portal request is carried to an active customer and
    *"you will ahve to create regular or master customer"*. For a build that is
    New Connect's owner account (`metering.connections.create_owner_account`).
    For a premises ALREADY on file — an owner or a property manager applying
    for a whole multi-unit building — the request is approved as a move-in
    (*"Opens an account on a unit that already has service"*) and the account
    is the owner's master. Until this function the master door took no request
    at all, so the job it raised waited on the Move-ins tab for ever.

    INSIDE the caller's transaction: a refused master rolls the job's close
    back with it. Writes no move record — no unit was occupied, which is the
    whole difference from `moves.record_move` — and says which door closed the
    job (`CLOSED_BY_MASTER_ACCOUNT`) instead. Audited against the REQUEST.
    """
    if not request_id:
        return 0
    from apps.customers import move_in_jobs

    closed = move_in_jobs.complete_for_request(
        request_id, reason=move_in_jobs.CLOSED_BY_MASTER_ACCOUNT
    )
    _audit(
        actor,
        "service_request.fulfilled_by_master_account",
        request_id,
        entity_type="service_request",
        after={
            "account_id": str(account.id),
            "account_no": account.account_no,
            "move_in_jobs_closed": closed,
        },
    )
    return closed


def _record_request_customer(actor: Any, request_id: Any, account_id: Any) -> None:
    """`DEF-CUS-9078` — **the customer a door opened for a request is recorded
    ON the request, so the next door for the same request reaches the same
    customer.**

    A new connection carried to ACTIVE passes two doors for one applicant: the
    build opens the owner's master account (`create_master_account`) and the
    move-in opens the occupant's regular one. Each resolves its customer on its
    own, and a PERSON carries no government identifier for `BR-CUS-1024` to
    reuse by — so the 21-walk of 2026-10-02 showed one applicant as two
    customer numbers. `_carry_request_decisions` already hands a request's
    LINKED customer to every door; this writes the link the first door made.

    **Only where the request names nobody** — a clerk's own link is never
    overwritten. Tier `strong`: the customer was created FOR this applicant at
    this door, so it is them by construction rather than by a likeness test.
    Written through `service_request_service.link_customer`, so the request's
    trail and `audit_log` say so exactly as a clerk's link does (rule 7).
    INSIDE the caller's transaction: a refused door rolls the link back too.
    """
    if not request_id:
        return
    request = (
        models.ServiceRequest.objects.filter(tenant_id=_tenant_id(), pk=request_id)
        .only("id", "matched_customer_id")
        .first()
    )
    if request is None or request.matched_customer_id:
        return
    holder = (
        models.CustomerAccount.objects.filter(tenant_id=_tenant_id(), account_id=account_id)
        .values_list("customer_id", flat=True)
        .first()
    )
    if holder is None:
        return
    from apps.customers import service_request_service

    service_request_service.link_customer(
        actor,
        request.id,
        customer_id=holder,
        tier="strong",
        basis="created_for_this_request",
    )


def _carry_request_custom_answers(actor: Any, request_id: Any, account_id: Any) -> None:
    """`DEF-CUS-9211` — **the utility's own fields typed on a service request
    reach the account a door has just opened FOR that request**, its holder,
    and the premises it sits on.

    Approval copies only onto records that exist then (`CR-161-BRC10` W6), and
    a first-time applicant's customer and account do not. Called right after
    `_record_request_customer`, so the request names this account's holder when
    it names nobody else; `request_custom_fields.carry_into_created` copies only
    when the holder IS the request's customer, keeps any answer already on the
    target, and writes one audit row. INSIDE the caller's transaction.
    """
    if not request_id:
        return
    from apps.customers import request_custom_fields

    request_custom_fields.carry_into_created(actor, request_id, account_id=account_id)


def _refuse_if_master_covered(unit: Any) -> None:
    """BR-CUS-068's own double-coverage guard: a common-area unit already
    covered by an active master account (through an OPEN service agreement on
    one of its service points) refuses by name — the same shape as
    BR-CUS-017's one-active-account-per-unit, applied to the SA linkage the
    master path attaches through."""
    from apps.customers import selectors

    existing = selectors.master_account_covering_unit(unit.id)
    if existing is None:
        return
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-CUS-068",
        message_key="customers.account.unit_already_occupied",
        params={
            "unit_id": str(unit.id),
            "label": unit.label,
            "account_id": str(existing.id),
            "account_no": existing.account_no,
            "status": existing.status.code,
        },
    )


def _refuse_if_premises_has_master(premises_id: Any) -> None:
    """`BR-CUS-1011` — ONE OWNER ACCOUNT PER ADDRESS.

    Once a Master Account IS the owner's account at an address (`BR-CUS-1010`),
    two of them at one address are two owners of one building, and every read
    that asks *who owns this premises* — `master_account_for`,
    `sub_accounts_for_master`, `owner_master_account_for_premises` — would have
    to pick one. `BR-CUS-171` already records what that felt like when the owner
    was derived geometrically: two masters over one premises made the derivation
    answer `None` rather than name a winner.

    ⚠ **A LANE JUDGMENT, RECORDED RATHER THAN ASKED** (decision log 2026-09-01).
    It follows from `BR-CUS-1010`; it moves no frozen figure, collides with no
    signed rule, and needs no fact only the PO holds — law 13 leaves it to us.

    ⚠ **SERVICE-LAYER ONLY, LIKE `BR-CUS-017` BEFORE IT** (`OQ-092`, option (a):
    *"the check runs inside the create/update transaction with row locking"*),
    and here for a second reason: premises carrying TWO masters already exist in
    this product, and a database constraint would refuse to migrate them. This
    binds new creations and rewrites no history.

    ⚠ **IT ASKS ABOUT THE ADDRESS, NOT ABOUT A UNIT**, so it catches the case
    `_refuse_if_master_covered` structurally cannot: a premises with no common
    area at all, where there is no covered unit for that guard to find.
    """
    from apps.customers import selectors

    if premises_id in (None, ""):
        return
    # ⚠ **ONE QUERY, NOT TWO (`DEF-MET-6302`).** This filter used to be written
    # out here; `selectors.master_account_at_premises` now holds it, so the guard
    # that REFUSES and the seeder that ASKS cannot come to disagree about who
    # owns a building — which is precisely the history `BR-CUS-171` records.
    existing = selectors.master_account_at_premises(premises_id)
    if existing is None:
        return
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-CUS-1011",
        message_key="customers.account.premises_already_has_master",
        params={
            "premises_id": str(premises_id),
            "account_id": str(existing.id),
            "account_no": existing.account_no,
            "status": existing.status.code,
        },
    )


#: `BR-CUS-1114` — the fewest live units a premises must hold before it may have
#: a master account. PO 2026-10-02: *"we have to raise master account on multi
#: pairtment building where we can have multiple units. single family hime,
#: single unit, we should not do master account"*.
MASTER_ACCOUNT_MIN_UNITS = 2


def dwelling_units_at_premises(premises_id: Any) -> int | None:
    """`BR-CUS-1114` — live units at a premises that are NOT common areas, or
    `None` when metering is unwired. Read through the two seams that already
    exist; no metering table is queried from here (B2 §2)."""
    total = seams.units_at_premises_count(premises_id)
    if total is None:
        return None
    return max(0, total - len(seams.common_area_units_for_premises(premises_id)))


def master_account_allowed_at_premises(premises_id: Any) -> dict[str, Any]:
    """`BR-CUS-1114` as amended by `CR-162-BRC10` (Q1) — MAY this address have
    an owner's master account, and on what grounds?

    PO ruling 2026-10-02 (decision log, *"NEW CONNECTION — THE PO'S
    SCREEN-BY-SCREEN REVIEW BECOMES ONE PROGRAMME"*), Q1: *"THE MASTER ACCOUNT
    IS DECIDED BY PREMISES TYPE, NOT BY HOW MANY UNITS ARE ENTERED: apartment
    complex, commercial building, mixed-use and any type able to hold several
    units get a master account … even with one unit entered … a single-family
    home gets none."*

    ⚠ **REFRAMED BY THE PO THE SAME DAY, AND THE REFRAMING IS THE RULE:**
    *"when we say premises type has account type - master or regular attached …
    then when you create account dont you want to use this field when you are
    creating accounts"*. So the answer is a SETTING on the utility's own
    premises-type row — *Account type: Master account / Regular account*
    (`metering.premises_types.account_kind`) — and never a list of names in
    code.

    Answers `{"allowed": bool, "basis": "type" | "units", ...}`:

      * the premises TYPE decides wherever its row is answered;
      * a utility's own type from before the setting existed, not yet answered,
        or a premises with no type, falls back to the rule as first built on
        2.442.0 — two or more homes at the address — so such an address behaves
        exactly as it did yesterday (decision log 2026-10-02, `CR-162-BRC10`
        judgment (a)).

    Read by the guard below AND served to the screens that open or hide the
    master form, so a button and the server cannot disagree."""
    kind = seams.premises_account_kind(premises_id)
    if kind is not None:
        return {"allowed": kind == ACCOUNT_KIND_MASTER, "basis": "type", "units": None}
    count = dwelling_units_at_premises(premises_id)
    return {
        "allowed": count is not None and count >= MASTER_ACCOUNT_MIN_UNITS,
        "basis": "units",
        "units": count,
    }


def _refuse_master_on_single_unit_premises(premises_id: Any) -> None:
    """`BR-CUS-1114` — A MASTER ACCOUNT ONLY WHERE THE PREMISES TYPE SAYS
    *MASTER ACCOUNT* (amended 2026-10-02 by `CR-162-BRC10`, Q1).

    ⛔ **THE FIRST BUILD OF THIS RULE (2.442.0) COUNTED THE UNITS ENTERED, AND
    THE PO CORRECTED IT THE SAME DAY.** Haustin Towers — an apartment building
    with one unit typed in — got no master account. Q1: the master account is
    decided by PREMISES TYPE; an apartment complex gets one *"even with one
    unit entered"*, a single-family home never does. The decision is
    `master_account_allowed_at_premises`, above; this only refuses.

    **WHY HERE, ONCE.** Every master door ends at `create_master_account`: the
    property's master form (`POST /accounts/master`), the portal approval's
    *Owner's master account* (the same form, with `service_request_id`), New
    Connect's owner step (`metering.connections.create_owner_account`) and the
    premises-owner / import door (`metering.premises_owners`). One guard here
    reaches all of them; a copy per door is a copy that drifts.

    **TWO SENTENCES, BECAUSE THEY ARE TWO DIFFERENT FACTS.** A premises whose
    type takes a REGULAR account is refused for what it IS (*"Single-family
    homes have no master account. Open a regular account at Move-in."*,
    `customers.account.master_not_for_single_family`); an address of an
    unanswered type is refused for how many homes it HAS, with the sentence
    2.442.0 already shipped (`customers.account.master_needs_two_units`).

    **WHAT IT DOES NOT DO (`BR-CUS-1114` (e)):** it never touches an existing
    master account — those are counted and reported, not changed. It refuses
    only a NEW one, and `BR-CUS-1011` runs first so an address that already has
    one still answers with it.

    ⚠ `None` from the unit-count seam means metering is unwired, which is a
    broken deployment rather than an answer; it is refused rather than read as
    *enough units*, because the safe failure is no new money object.
    """
    decision = master_account_allowed_at_premises(premises_id)
    if decision["allowed"]:
        return
    if decision["basis"] == "type":
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-1114",
            message_key="customers.account.master_not_for_single_family",
            params={"premises_id": str(premises_id)},
        )
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-CUS-1114",
        message_key="customers.account.master_needs_two_units",
        params={
            "premises_id": str(premises_id),
            "units": decision["units"],
            "minimum": MASTER_ACCOUNT_MIN_UNITS,
        },
    )


def hold_new_master_pending(actor: Any, account_id: Any) -> dict[str, Any]:
    """`CR-162-BRC10` (items 2 and 34) — a New Connection's owner master
    account is held PENDING until the build is approved.

    PO 2026-10-02: the premises *"is not yet active - it will be activated at
    the time of approval of new conenct request"*, and Q1: the master account
    and the owner customer are *"created PENDING at Create, ACTIVE on
    approval"*.

    ⚠ **WHY A HOLD AFTER CREATION AND NOT A PENDING CREATION — measured, not
    preferred.** The same press posts the build's one-time charges to this
    account and may take a payment against them (`BR-MET-1187`, PO 2026-09-28:
    *"we create entries in books … at creation once submitted"*). Billing's
    single door refuses a `non_billable` account by BR-CUS-055's own class
    rule (`billing.single._unit_less_scope`), so a master born pending made
    every New Connection with an owner refuse on *"the books entry cannot be
    written"* (`test_def_cus_8020_8021_the_create_button.py`, measured red).
    So the account opens ACTIVE exactly as `BR-CUS-068` made it, takes the
    build's charges inside the commit's one transaction, and THEN is held in
    the seeded `pending_activation` status (`BR-CUS-018`'s draft, class
    `non_billable`) — no cycle run bills it, and the build's first activation
    moves it back to `active` (`activate_pending_master_account`). No money
    rule moved: the one-time invoice is the one the commit always wrote.

    Only a MASTER account, only from `active`, and only the New Connection
    commit calls it (through metering's seam). Audited (hard rule 7)."""
    from apps.customers import selectors

    with transaction.atomic():
        account = selectors.account_or_404(account_id, lock=True)
        # ⊕ `DEF-CUS-9228` — and the owner's REGULAR account a single-family
        # build opens (`create_build_owner_account`), the same lifecycle. A
        # pending regular account occupies nothing (`BR-CUS-018`).
        if account.kind not in (ACCOUNT_KIND_MASTER, ACCOUNT_KIND_REGULAR):
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-1010",
                message_key="customers.account.not_a_master_account",
                params={"account_no": account.account_no},
            )
        code = account.status.code.lower()
        if code == PENDING_STATUS_CODE:
            return {"id": str(account.id), "status": account.status.code, "already_pending": True}
        before = {"status": account.status.code}
        account.status = _seeded_status(
            PENDING_STATUS_CODE, "customers.account.pending_status_missing"
        )
        account.save(update_fields=["status", "updated_at"])
        _audit(
            actor,
            "account.held_pending",
            account.id,
            before=before,
            after={"status": account.status.code, "br_ref": "CR-162-BRC10"},
        )
    return {"id": str(account.id), "status": account.status.code, "already_pending": False}


def activate_pending_master_account(actor: Any, account_id: Any) -> dict[str, Any]:
    """`CR-162-BRC10` (item 6) — a New Connection's owner master account
    becomes ACTIVE when the build is first approved.

    Called by metering's activation (`metering.connection_activation`) through
    the seam, inside that activation's transaction. **Idempotent:** an account
    already active answers `already_active` and writes nothing — a second
    activation of the same build must not write a second audit row.

    ⚠ **NOT `activate_account`, AND THE DIFFERENCE IS THE POINT.** That door is
    the S18 draft's resume: it makes the account its UNIT's occupant
    (`_make_occupying`). A master account occupies no unit (`BR-CUS-1010`:
    `unit_id` is NULL), so routing it there would either fail on the unit read
    or invent an occupancy. This flips the status, from `pending_activation`
    only, and writes one audit row (hard rule 7)."""
    from apps.customers import selectors

    with transaction.atomic():
        account = selectors.account_or_404(account_id, lock=True)
        if account.kind not in (ACCOUNT_KIND_MASTER, ACCOUNT_KIND_REGULAR):
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-1010",
                message_key="customers.account.not_a_master_account",
                params={"account_no": account.account_no},
            )
        code = account.status.code.lower()
        if code != PENDING_STATUS_CODE:
            return {
                "id": str(account.id),
                "account_no": account.account_no,
                "status": account.status.code,
                "already_active": True,
            }
        before = {"status": account.status.code}
        active = _default_active_status()
        if account.kind == ACCOUNT_KIND_REGULAR and account.billing_only:
            # ⊕ `CR-164-BRC10` wave 4 — a BILLING-ONLY owner's account (not an
            # owner-occupier; OQ-CUS-12785 for those) holds no home: Active
            # for its charges, the home left Vacant for Move-in.
            account.status = active
            account.save(update_fields=["status", "updated_at"])
        elif account.kind == ACCOUNT_KIND_REGULAR:
            # ⊕ `DEF-CUS-9228` — the single-family owner's account HOLDS its
            # home once Active, so it takes the occupancy door every other
            # activation takes (`_make_occupying`: the unit lock, BR-CUS-017,
            # the plan, the service agreements it does not already hold).
            #
            # ⚠ **AN OCCUPANT WHO MOVED IN WHILE THE BUILD WAS PENDING KEEPS
            # THE HOME** — Move-in is unchanged (PO ruling 2026-10-02, item 1).
            # Asked under the lock BEFORE any write, never caught after one
            # (hard-won law 14): this account stays Pending, its charges stay
            # owed on it, and the activation reports it rather than refusing
            # the whole approval.
            lock_unit_scope(account.unit_id)
            other = (
                selectors.occupying_accounts_for_unit(account.unit_id, lock=True)
                .exclude(pk=account.pk)
                .order_by("created_at", "id")
                .first()
            )
            if other is not None:
                _audit(
                    actor,
                    "account.left_pending_unit_occupied",
                    account.id,
                    before=before,
                    after={
                        "status": account.status.code,
                        "occupied_by": other.account_no,
                        "br_ref": "BR-CUS-017",
                    },
                )
                return {
                    "id": str(account.id),
                    "account_no": account.account_no,
                    "status": account.status.code,
                    "already_active": False,
                    "left_pending": True,
                    "occupied_by": other.account_no,
                }
            account.status = active
            account.save(update_fields=["status", "updated_at"])
            _make_occupying(account, seams.unit_row(account.unit_id), warnings=[])
        else:
            account.status = active
            account.save(update_fields=["status", "updated_at"])
        _audit(
            actor,
            "account.activated",
            account.id,
            before=before,
            after={"status": account.status.code, "br_ref": "CR-162-BRC10"},
        )
    return {
        "id": str(account.id),
        "account_no": account.account_no,
        "status": account.status.code,
        "already_active": False,
    }


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def update_account(actor: Any, account_id: Any, changes: Any) -> dict[str, Any]:
    """PATCH /accounts/{id}. Attribute edits only — the unit an account belongs
    to is not editable (BR-CUS-017), closing it is the move-out flow
    (BR-CUS-030), and every system-derived or unbuilt column refuses with its
    own rule id (REFUSED_FIELDS)."""
    from apps.customers import attribute_history, selectors

    data = _payload_dict(changes)
    # `DEF-CUS-9158` — Account detail (S21) edits the tenant's own fields. The
    # blob is taken OUT before the attribute validation and checked against the
    # stored row inside the lock, because an edit names only what changed: the
    # answers typed on other screens must survive it, and a required field
    # placed Input here is answered if the row already holds a value.
    has_custom = "custom_data" in data
    custom_submitted = data.pop("custom_data", None)
    cleaned = _validate_account(data, partial=True)
    warnings: list[dict[str, Any]] = []

    with transaction.atomic():
        account = selectors.account_or_404(account_id, lock=True)
        before = selectors.account_detail_dict(account)
        if has_custom:
            cleaned["custom_data"] = seams.validate_custom_data(
                "accounts",
                custom_submitted,
                screen="S21",
                existing=dict(account.custom_data or {}),
            )
        new_status = cleaned.pop("status", None)
        if new_status is not None and new_status.pk != account.status_id:
            _apply_status_change(account, new_status, warnings=warnings)
        fields: list[str] = []
        for field, value in cleaned.items():
            if field in ("unit", "account_type"):  # create-only, never patched
                continue
            if getattr(account, field, None) != value:
                setattr(account, field, value)
                fields.append(field)
        if new_status is not None:
            account.status = new_status
            fields.append("status")
        if fields:
            account.save(update_fields=[*dict.fromkeys(fields), "updated_at"])
            # ── CR-142-BRC07 `P0.18` · AS-WAS (the brief's §7.2.4, option b) ──
            #
            # ⚠ **THIS LINE IS THE WHOLE DIFFERENCE BETWEEN A REPORT THAT CAN
            # ANSWER *"revenue by class for July"* AND ONE THAT CANNOT.** The
            # three columns it shadows overwrite in place; the only other trace
            # is `audit_log`, which is pruned on a schedule with NO exemptions
            # (PO 2026-09-23), so without this the answer is unrecoverable
            # rather than merely unbuilt.
            #
            # INSIDE the same `transaction.atomic()` as the save, deliberately:
            # a history row for a save that rolled back is a period that never
            # happened, and a save with no history row is the defect.
            #
            # It writes NOTHING when none of the three moved — `record` returns
            # None — so an edit to the mailing address does not split July in
            # two.
            attribute_history.record(account, on=timezone.localdate(), actor=actor)
            _audit(
                actor,
                "account.updated",
                account.id,
                before=before,
                after=selectors.account_detail_dict(account),
            )
            # ⚖️ `DEF-RAT-9833` (PO ruling 4, 2026-10-06, reading (b)) — Autopay
            # or Paperless switched ON here puts the matching discount in place
            # for the next bill now, inside this transaction; OFF waits for the
            # night's sync, as before.
            if any(field in ("autopay", "paperless") and getattr(account, field) for field in fields):
                from apps.customers import discounts as customer_discounts

                customer_discounts.settings_switched_on(actor, account.id, source="account_edit")
    return {**selectors.account_detail_dict(account), "warnings": warnings}


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def update_account_contact(actor: Any, account_id: Any, changes: Any) -> dict[str, Any]:
    """`PATCH /accounts/{id}/contact` — correct the account's primary contact.

    ⚠ **THE DOOR THE PRODUCT DID NOT HAVE, AND THE ONE IT DID WAS A DIFFERENT
    TABLE (PO 2026-09-13).** The Product Owner drove the live account screen and
    reported *"I cannot edit Customer details"*, and the Overview's CUSTOMER
    group renders `contacts` — `BR-CUS-045`'s PII columns, keyed to the ACCOUNT.
    `PATCH /customers/{id}` (`BR-CUS-1054`, built the same day) writes the
    `customers` row, which is a different table reached through
    `customer_accounts` and is mounted on the customer's own screen; wiring the
    account's pencil to it would have moved a name the CUSTOMER group does not
    show. Two tables, two doors.

    **Only `contacts.create` existed** — the new-account and move-in wizards —
    and `portal_self_service._write_contact` takes email and phone from the
    CUSTOMER, so there was no staff door at all. A misspelt name on an account
    could not be corrected anywhere in the product.

    ⚠ **THE PRIMARY CONTACT, AND NOT AN ARBITRARY ONE.** The screen shows
    `primaryContact(detail.contacts)` — one row — so this writes the one the
    screen shows. An account with several contacts is a shape no screen in this
    product edits yet; a `contact_id` in the path would be a control nothing
    calls (hard-won law 2).

    ⚠ **`gov_id_last4` IS ACCEPTED AND TRUNCATED, NEVER WIDENED.**
    `_validate_contact` keeps only the last four, so a full government id cannot
    enter the database through this path either — the same guarantee the create
    path already gives, reused rather than restated.

    Audited whole-row before→after (`BR-AUD-003`), which is what makes a PII
    edit reviewable rather than silent.
    """
    from apps.customers import customer_edit, portal_seam, selectors

    data = _payload_dict(changes)
    # ⊕ PO 2026-10-22 (`OQ-CUS-12350` closed, `DEF-CWP-10400`) — the clerk's
    # *"Also use this as the portal sign-in email"* tick box. Not a contact
    # column, so it is taken out before the column check.
    move_login = data.pop(customer_edit.SIGN_IN_FLAG, None) is True
    _reject_unknown(data, CONTACT_FIELDS)
    with transaction.atomic():
        account = selectors.account_or_404(account_id, lock=True)
        contact = (
            models.Contact.objects.filter(
                tenant_id=account.tenant_id, account=account, deleted_at__isnull=True
            )
            .order_by("-is_primary", "created_at", "id")
            .first()
        )
        if contact is None:
            # An account with no contact row at all. This is a CORRECTION path,
            # not a creation one: minting a contact here would let a PATCH
            # create a person, which the wizards own.
            raise errors.deny_as_not_found("BR-CUS-045")
        # The validator requires `full_name`, so a partial body is completed
        # from the row before it is checked — this is a PATCH, not a PUT.
        merged = {
            "full_name": contact.full_name,
            "email": contact.email,
            "phone": contact.phone,
            "dob": contact.dob.isoformat() if contact.dob else None,
            "gov_id_last4": contact.gov_id_last4,
            **data,
        }
        # `DEF-CUS-9168` — this IS the contact edit on Account detail (slot
        # `S21` for `contacts`). Only the keys that changed travel; tenancy
        # merges them into the stored answers, so an answer typed elsewhere is
        # never wiped, and a required field placed Input here is answered when
        # the row already holds a value.
        cleaned = (
            _validate_contact(
                merged,
                custom_data_screen="S21",
                existing_custom=dict(contact.custom_data or {}),
            )
            or {}
        )
        cleaned.pop("is_primary", None)  # which row is primary is not edited here
        before = selectors.account_detail_dict(account)
        fields = [f for f, v in cleaned.items() if getattr(contact, f, None) != v]
        for field in fields:
            setattr(contact, field, cleaned[field])
        if fields:
            contact.save(update_fields=[*fields, "updated_at"])
            _audit(
                actor,
                "account.contact.updated",
                account.id,
                before=before,
                after=selectors.account_detail_dict(account),
            )
        sign_in_moved = False
        if move_login:
            # Offered only when exactly ONE holder of this account has a login
            # (decision log 2026-10-22, lane SIGNIN-EMAIL item 2): with two,
            # nothing says whose login the primary contact is. Refused by name,
            # inside the transaction, so the contact write goes back with it.
            holders = portal_seam.login_customers_for_account(account)
            if len(holders) > 1:
                raise errors.ValidationError(
                    errors.VAL_FORMAT,
                    message_key="customers.account.edit.signInJoint",
                    field_errors=[
                        {
                            "field": customer_edit.SIGN_IN_FLAG,
                            "code": errors.VAL_FORMAT,
                            "message_key": "customers.account.edit.signInJoint",
                            "params": {},
                        }
                    ],
                )
            sign_in_moved = customer_edit.move_sign_in(
                actor,
                account.tenant_id,
                holders[0] if holders else None,
                contact.email,
            )
    return {**selectors.account_detail_dict(account), "portal_sign_in_moved": sign_in_moved}


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def update_account_mailing_address(actor: Any, account_id: Any, changes: Any) -> dict[str, Any]:
    """`PATCH /accounts/{id}/mailing-address` — where the BILL goes.

    ⚠ **HARD RULE 8's FIRST NAMED EXCEPTION, AND IT HAD NO WRITE DOOR** (PO
    2026-09-13: *"I cannot edit … Mailing address"*). An address lives on
    `premises` and every other entity walks to it — except `customers.addresses`
    `kind='mailing'`, which is *"where the BILL goes, which for a landlord is
    another building"*. That is a genuinely separate fact, and the only writer
    it had was account creation. A customer who moved their post could not be
    followed without creating a new account.

    ⚠ **`kind` IS NOT ACCEPTED FROM THE CALLER AT ALL.** `kind='service'` is
    RETIRED by `BR-MET-1161` and a write asking for it is refused by name; this
    route writes `mailing` and only `mailing`, so the retired value cannot
    arrive through it even as a typo. `G85` fails a fourth home.

    **An empty `line1` DELETES the row**, which is the correct model rather than
    a second endpoint: no mailing row means *the bill goes to the service
    address*, which `B2 §2` and the screen both already say in those words. A
    soft delete, so the audit trail still reaches the row.
    """
    from apps.customers import selectors

    data = _payload_dict(changes)
    _reject_unknown(data, ADDRESS_FIELDS - {"kind"})
    with transaction.atomic():
        account = selectors.account_or_404(account_id, lock=True)
        before = selectors.account_detail_dict(account)
        row = (
            models.Address.objects.filter(
                tenant_id=account.tenant_id,
                account=account,
                kind="mailing",
                deleted_at__isnull=True,
            )
            .order_by("created_at", "id")
            .first()
        )
        line1 = _text(data.get("line1")) if "line1" in data else (row.line1 if row else None)
        if not line1:
            if row is not None:
                row.deleted_at = timezone.now()
                row.save(update_fields=["deleted_at", "updated_at"])
                _audit(
                    actor,
                    "account.mailing_address.removed",
                    account.id,
                    before=before,
                    after=selectors.account_detail_dict(account),
                )
            return selectors.account_detail_dict(account)
        merged = {
            "kind": "mailing",
            "line1": line1,
            "line2": (row.line2 if row else None),
            "city": (row.city if row else None),
            "state": (row.state if row else None),
            "postal_code": (row.postal_code if row else None),
            **{k: v for k, v in data.items() if k != "kind"},
        }
        # `DEF-CUS-9169` — this IS the mailing edit on Account detail (slot
        # `S21` for `addresses`): changed answers merge into the stored row's,
        # and a required field placed Input here counts a stored answer.
        cleaned = _validate_addresses(
            [merged],
            custom_data_screen="S21",
            existing_custom=dict(row.custom_data or {}) if row is not None else {},
        )[0]
        if row is None:
            models.Address.objects.create(
                tenant_id=account.tenant_id, account=account, **cleaned
            )
            fields = ["line1"]
        else:
            fields = [f for f, v in cleaned.items() if getattr(row, f, None) != v]
            for field in fields:
                setattr(row, field, cleaned[field])
            if fields:
                row.save(update_fields=[*fields, "updated_at"])
        if fields:
            _audit(
                actor,
                "account.mailing_address.updated",
                account.id,
                before=before,
                after=selectors.account_detail_dict(account),
            )
    return selectors.account_detail_dict(account)


#: The three facts a co-applicant carries — PO 2026-09-23, *"(name, email,
#: phone)"*. Nothing else is accepted, and an unknown key is refused by name.
CO_APPLICANT_FIELDS: frozenset[str] = frozenset({"full_name", "email", "phone", "dob"})
#: ⊕ `dob` — DEF-CUS-10253 (image `08-edit.png`, PO 2026-10-18: the account
#: page's co-applicant dialog uses the shared fields, a date of birth among
#: them). `contacts.dob` has existed since the table did; this widens the door.


def _co_applicant_rows(account: Any) -> list[Any]:
    """The account's live NON-primary contacts, oldest first."""
    return list(
        models.Contact.objects.filter(
            tenant_id=account.tenant_id,
            account=account,
            deleted_at__isnull=True,
            is_primary=False,
        ).order_by("created_at", "id")
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def set_account_co_applicant(
    actor: Any, account_id: Any, person: dict[str, Any] | None
) -> dict[str, Any] | None:
    """**THE ACCOUNT'S SECOND PERSON — REPLACED WHOLE, OR REMOVED.**

    PO ruling 2026-09-23 (transfer question T4, closing `OQ-CUS-12514`),
    verbatim: *"a) Store a second person on the account (name, email, phone),
    shown on the account page"*.

    ⚠ **A SECOND `contacts` ROW, `is_primary = false`, AND NO NEW COLUMN.**
    `contacts` has never been unique on the account (`ix_contacts_tenant_account`
    is a plain index), so the shape was always legal; what was missing was a
    writer and a screen. `BR-CUS-045`'s PII posture applies unchanged.

    ⚠ **REPLACE, NOT APPEND.** A sale calls this with the BUYER's co-applicant
    (or `None`), so the seller's second person leaves with the seller — the
    same reach-ends-at-the-sale reasoning as T3. Extra rows beyond one are
    soft-deleted, so an account never shows two co-applicants.

    `None`, or a person with no name, REMOVES. Returns the stored contact or
    `None`. Audited before→after (hard rule 7's posture for PII).
    """
    from apps.customers import selectors

    with transaction.atomic():
        account = selectors.account_or_404(account_id, lock=True)
        rows = _co_applicant_rows(account)
        name = _text((person or {}).get("full_name"), 200)
        if not name:
            if not rows:
                return None
            before = selectors.account_detail_dict(account)
            now = timezone.now()
            for row in rows:
                row.deleted_at = now
                row.save(update_fields=["deleted_at", "updated_at"])
            _audit(
                actor,
                "account.co_applicant.removed",
                account.id,
                before=before,
                after=selectors.account_detail_dict(account),
            )
            return None
        cleaned = _validate_contact(
            {
                "full_name": name,
                "email": (person or {}).get("email"),
                "phone": (person or {}).get("phone"),
                "dob": (person or {}).get("dob"),
                "is_primary": False,
            }
        ) or {}
        before = selectors.account_detail_dict(account)
        if rows:
            row = rows[0]
            row.full_name = cleaned["full_name"]
            row.email = cleaned["email"]
            row.phone = cleaned["phone"]
            row.dob = cleaned.get("dob")
            row.save(update_fields=["full_name", "email", "phone", "dob", "updated_at"])
            now = timezone.now()
            for extra in rows[1:]:
                extra.deleted_at = now
                extra.save(update_fields=["deleted_at", "updated_at"])
        else:
            row = models.Contact.objects.create(
                tenant_id=account.tenant_id,
                account=account,
                full_name=cleaned["full_name"],
                email=cleaned["email"],
                phone=cleaned["phone"],
                dob=cleaned.get("dob"),
                is_primary=False,
            )
        _audit(
            actor,
            "account.co_applicant.set",
            account.id,
            before=before,
            after=selectors.account_detail_dict(account),
        )
        return selectors.contact_dict(row)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def update_account_co_applicant(actor: Any, account_id: Any, changes: Any) -> dict[str, Any]:
    """`PATCH /accounts/{id}/co-applicant` — the account page's pencil.

    An absent key keeps what is stored; `full_name: ""` removes the person.
    Answers the whole account, as the other account-group doors do, so the page
    re-renders from one payload.
    """
    from apps.customers import selectors

    data = _payload_dict(changes)
    _reject_unknown(data, CO_APPLICANT_FIELDS)
    account = selectors.account_or_404(account_id)
    rows = _co_applicant_rows(account)
    current = rows[0] if rows else None
    merged = {
        "full_name": current.full_name if current else "",
        "email": current.email if current else None,
        "phone": current.phone if current else None,
        "dob": current.dob.isoformat() if current and current.dob else None,
        **data,
    }
    set_account_co_applicant(actor, account_id, merged)
    return selectors.account_detail_dict(selectors.account_or_404(account_id))


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def activate_account(actor: Any, account_id: Any, payload: Any = None) -> dict[str, Any]:
    """POST /accounts/{id}/activate (11b §2.6) — the resume half of the S18
    draft flow (BR-CUS-018): the pending account becomes the unit's occupant.

    `{"opened_at": "…"}` may accompany the call when the draft was saved before
    the service start date was known; nothing else is accepted here."""
    from apps.customers import selectors

    data = _payload_dict(payload or {})
    _reject_unknown(data, frozenset({"opened_at", "status"}))
    fe: list[dict[str, Any]] = []
    opened_at = _date(data.get("opened_at"), "opened_at", fe) if "opened_at" in data else None
    status = _resolve_status(data["status"], fe) if "status" in data else None
    _refuse_fields(fe)
    warnings: list[dict[str, Any]] = []

    with transaction.atomic():
        account = selectors.account_or_404(account_id, lock=True)
        before = selectors.account_detail_dict(account)
        if status is None:
            status = _default_active_status()
        if not is_occupying(status):
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-055",
                message_key="customers.account.status_does_not_activate",
                params={"status": status.code, "behavior_class": status.behavior_class},
            )
        # ⛔ DEF-721 — ACTIVATION HAS A LAWFUL STARTING POINT, AND THIS NEVER
        # READ IT. `activate_account` was written when `pending_activation` was
        # the ONLY non-billable status, so "activate" had exactly one place it
        # could start from and checking looked redundant. BR-CUS-107 added a
        # second member of that class — `disconnected` — and the omission
        # became reachable: nothing on the server refused activating an account
        # whose service is CUT and whose debt is unpaid, which walks straight
        # around the reconnect flow BR-PAY-036 and B18 §5.8.4 require.
        # `disconnects.mark_reconnecting` exists precisely so restoration is an
        # explicit audited act AFTER the money arrives, and a display guard on
        # S21 is not the fix — the endpoint still accepted the call.
        #
        # THE RULE IS NAMED, NOT INFERRED FROM A CLASS. `pending_activation` is
        # BR-CUS-018's draft and it is the only status this door opens from:
        #  · `active` / `marked_disconnect` are already occupying — activating
        #    one is a no-op that would rewrite `opened_at`;
        #  · `vacation_hold` comes back through its own resume, not this door
        #    (and BR-CUS-055 owns that vocabulary);
        #  · `closed` is terminal — reopening is a move-in, BR-CUS-030;
        #  · `disconnected` is the one this defect is about — BR-CUS-107 /
        #    B18 §5.8.4: it comes back through `mark_reconnecting`.
        # A tenant-added non-billable draft-alike is NOT silently admitted:
        # widening this set is a BR-CUS-055 ruling, not a lane's pick.
        if account.status.code.lower() != PENDING_STATUS_CODE:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-018 · BR-CUS-107 · BR-PAY-036",
                message_key="customers.account.activate_wrong_starting_status",
                params={
                    "status": account.status.code,
                    "behavior_class": account.status.behavior_class,
                    "expected": PENDING_STATUS_CODE,
                },
            )
        fields = ["status"]
        if opened_at is not None:
            account.opened_at = opened_at
            fields.append("opened_at")
        account.status = status
        _make_occupying(account, seams.unit_row(account.unit_id), warnings=warnings)
        account.save(update_fields=[*fields, "updated_at"])
        # `DEF-2480` — one 26-query snapshot, two consumers. Built AFTER the
        # save, so it carries the activated status exactly as the second build
        # did; the audit blob is unchanged.
        snapshot = selectors.account_detail_dict(account)
        _audit(
            actor,
            "account.activated",
            account.id,
            before=before,
            after=snapshot,
        )
    return {**snapshot, "warnings": warnings}


def _default_active_status() -> models.AccountStatus:
    """The seeded `active` row (BR-CUS-055). Absent only if a tenant deleted a
    seeded status, which BR-TEN-036 forbids — so this refuses rather than
    picking whichever billable row happens to sort first."""
    return _seeded_status("active", "customers.account.active_status_missing")


def _default_closed_status() -> models.AccountStatus:
    """The seeded `closed` row — the TERMINAL status BR-CUS-055 names, and the
    one a move-out lands on unless the caller names another terminal status of
    its own (BR-CUS-055 is tenant-extensible: "Legal hold", "Written off" …).

    Chosen by CODE, not by behaviour class, for the same reason
    `_default_active_status` is: a tenant may add a second terminal status, and
    silently picking whichever one sorted first would decide for them."""
    return _seeded_status("closed", "customers.account.closed_status_missing")


def _seeded_status(code: str, message_key: str) -> models.AccountStatus:
    row = models.AccountStatus.objects.filter(
        tenant_id=_tenant_id(), code__iexact=code, active=True
    ).first()
    if row is None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-CUS-055",
            message_key=message_key,
            params={"code": code},
        )
    return row


def _apply_status_change(
    account: models.Account, status: models.AccountStatus, *, warnings: list[dict[str, Any]]
) -> None:
    """Every stored-status transition, in one place (BR-CUS-016/017/030)."""
    if status.behavior_class == CLASS_TERMINAL:
        # BR-CUS-030: closing an account sets closed_at, ends the service
        # agreements, stops dunning and hands billing the BR-CUS-031 final-bill
        # contract. A bare status flip would LOOK like a close while doing none
        # of it — no `closed_at`, agreements still open, no handoff — so the
        # transition stays refused HERE and points at `move_out()`, which is now
        # a real flow rather than the stub this message used to name.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-030",
            message_key="customers.account.close_is_the_move_out_flow",
            params={"status": status.code, "story": "US-CUS-005"},
        )
    if is_occupying(status) and not is_occupying(account.status):
        _make_occupying(account, seams.unit_row(account.unit_id), warnings=warnings)


# ════════════════════════════════════════════════════════════════════════════
# SLICE 3 — move-out (US-CUS-005 · S20) and move-in (US-CUS-004 · S19)
# ════════════════════════════════════════════════════════════════════════════

#: BR-CUS-030/031 + BR-CUS-025/057: everything a real move-out would also do,
#: each naming the rule that owns it and the reason it cannot happen here. This
#: list rides the response of EVERY move-out; it is not conditional, because
#: none of these is conditional — no invoice, refund, dunning row or outbound
#: document can exist anywhere in this repository today.
MOVE_OUT_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    # ⚠ **THE CODE IS STILL TRUE; THE REASON WAS NOT (`DEF-CUS-6465`,
    # 2026-09-24).** It read *"billing owns `invoices` (W3) and has no tables"*,
    # which was exact when it was written and false long before it was read
    # again — `invoices` has had a table, and rows, for weeks. A move-out still
    # does not RAISE a final bill: it PRICES the closing window and hands the
    # figure over (blueprint p112, PO ruling 10 of 2026-09-20), and billing
    # raises it on its own run. **Renaming the code to fix a sentence would move
    # a wire contract**, so the code stays and the sentence says what is true.
    #
    # ⚠ **AND "BILLING RAISES IT ON ITS OWN RUN" WAS FALSE TOO (`DEF-CUS-10093`,
    # 2026-10-12).** No run bills a closed account (stage 1 refuses the terminal
    # class) and Billing → One-time → Final refuses it by name
    # (`final_bill.FINAL_ACCOUNT_ALREADY_CLOSED`), so after this flow writes the
    # close NOTHING in the product can raise the final bill. The sentence told a
    # clerk to wait for a bill that cannot come; it now says only what happened.
    # ⚠ **RULED 2026-10-13 (PO, option B): Complete DRAFTS the final bill before
    # the close** (`_draft_final_bill`), so this row now rides ONLY a move-out
    # that drafted none — every day up to the move day already on an issued bill
    # (`FINAL_BILL_DRAFT_SUPERSEDES`). A refused draft refuses the move-out.
    {
        "code": "final_bill_not_issued",
        "br_ref": "BR-CUS-031",
        "detail": "this flow prices the closing window and raises no invoice; once the "
        "account is closed, billing refuses a final bill for it "
        "(account_already_closed_for_billing)",
    },
    {
        "code": "final_bill_handoff_not_persisted",
        "br_ref": "BR-CUS-031",
        "detail": "the handoff contract has no table, queue or outbox in B2 or any addendum; "
        "it rides this response and the audit row only",
    },
    {
        "code": "final_reads_not_committed",
        "br_ref": "BR-CUS-021",
        # ⚠ AMENDED 2026-08-26 (CR-038 W9 task 4): the flow CAN commit them
        # now — `final_reads` in the payload routes through the metering event
        # door (BR-MET-128) — so this entry rides ONLY a move-out that
        # captured none. `move_out` filters it out when reads were committed.
        "detail": "no final reads were captured on this move-out; readings commit through "
        "the metering event door (BR-MET-128) when the wizard captures them, and none were",
    },
    # ⚠ **HALF OF THIS WAS TRUE AND HALF WAS NOT (`DEF-CUS-6465`).** *"Apply-first
    # needs the final bill"* is still exactly right. *"The refund leg is payments
    # `refunds`, which has no tables"* is false: `refunds` and `payments` both
    # exist. The surviving clause is the whole reason, so the sentence is the
    # true half and nothing else.
    {
        "code": "deposit_not_settled",
        "br_ref": "BR-CUS-025",
        "detail": "applying the deposit needs the final bill, and this flow does not raise one",
    },
    # ⚠ **THIS ENTRY IS NOW CONDITIONAL, AND THAT IS THE REAL FIX
    # (`DEF-CUS-6465`).** It said *"the accrual engine is US-CUS-023 §7 and is
    # not built"*. The accrual landed on 2026-09-03 (`CR-059` CS-20) and
    # `selectors.deposit_interest_accrued` answers, so on every account where
    # interest WAS worked out this row told the clerk it was not.
    #
    # **It takes `final_reads_not_committed`'s shape**, which is the only other
    # conditional row here: an UNCONDITIONAL entry is a claim about the PRODUCT,
    # a conditional one is a claim about THIS move-out. `move_out` filters it out
    # when the accrual answered.
    {
        "code": "deposit_interest_not_accrued",
        "br_ref": "BR-CUS-057",
        "detail": "no deposit interest could be worked out for this account",
    },
    # ⚠ **`close_reason_not_recorded` WAS HERE UNTIL 2026-09-20 AND IS GONE
    # BECAUSE IT STOPPED BEING TRUE** (PO ruling of that date, option A —
    # migration `customers/0058`). It read *"`accounts.close_reason` is
    # PROPOSED-SCHEMA and not built"*, which was exact for six weeks and became
    # a false claim on every response the moment the column landed. Hard-won
    # law 1: a stale warning is a stale claim, and this list is the one place a
    # caller learns what a move-out did NOT do — a lie here is worse than a
    # silence. The reason is now on the response, on the account and on the
    # move record; an account closed with no reason given carries NULL and no
    # warning, because *nobody chose one* is not a gap in the product.
    {
        "code": "dunning_not_stopped",
        "br_ref": "BR-CUS-030",
        "detail": "collections has no tables — there is no dunning state to stop",
    },
    {
        "code": "closeout_documents_not_queued",
        "br_ref": "BR-CUS-030",
        "detail": "the final statement + deposit-disposition letter queue through "
        "notifications, which has no tables",
    },
)

#: BR-CUS-024/054/021: what a real S19 move-in adds over a plain create, and
#: cannot here. `plan_snapshot_not_recorded` + `deposit_not_applied` are NOT in
#: this list — `_make_occupying` already appends them for every occupying path.
#: ⚠ **THERE IS NO `move_in_visit_not_raised` ENTRY HERE, AND THE ABSENCE IS
#: DELIBERATE (CR-070 wave P, 2026-09-05).** The wave plan expected one to be
#: added and then removed in the same wave; it was never added, because it would
#: have been false the day it was written. Every row in this tuple is
#: UNCONDITIONAL — a thing this product cannot do at all — and the turn-on visit
#: is a thing it CAN do and does. What rides a move-in that could not raise one
#: is `work_orders_not_raised`, appended to `warnings` by the door itself, on
#: exactly the move-ins where it is true. A permanent row saying *no visit is
#: ever booked* would be hard-won law 1's failure in a data structure: a claim
#: that outlived the thing it described.
MOVE_IN_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "customer_not_linked",
        "br_ref": "BR-CUS-054",
        # ⚠ **THE REASON THIS CARRIED EXPIRED ON 2026-08-11 AND THE ENTRY RODE
        # ON FOR FORTY DAYS (`DEF-CUS-5912`).** It read *"the first-class
        # `customers` entity has no table, so a RETURNING customer cannot be
        # recognised — this move-in writes a fresh contact row"*. `customers`
        # and `customer_accounts` were both built that day (`US-CUS-019`), so
        # every clause of it was false, and it was served over move-ins that
        # had just **recognised a returning customer and linked them**. That is
        # hard-won law 1's second form — a stated reason that outlived the
        # thing it described — and `services.REFUSED_FIELDS` was corrected for
        # exactly this on the same day while this tuple was not.
        #
        # ⚠ **AND IT IS NOW FILTERED, NOT JUST REWORDED.** `move_in` drops it
        # whenever the commit linked OR created a customer, which on a
        # committed move-in is always: `require_identity=True` means
        # `BR-CUS-1024` refuses an account whose customer identifies nobody
        # (`R3`), so `none` never reaches a commit. The entry is KEPT rather
        # than deleted because it is the true thing to say if a door ever does
        # open an account without one — and `customer_not_created`
        # (`BR-CUS-1023`) is the separate, live fact for a customer number that
        # could not be minted.
        "detail": "no `customers` record was linked to this account, so nothing ties it to "
        "the person's other tenancies",
    },
    {
        "code": "deposit_carry_forward_unavailable",
        "br_ref": "BR-CUS-024",
        # `DEF-CUS-9702` (CR-171 P1.21, lane MVI-FLOW) — the FACT stands (no
        # move-in door carries a deposit yet); the reason *"with no customer
        # entity"* expired on 2026-08-11 when `customer_accounts` was built.
        "detail": "no deposit was carried forward from an earlier account",
    },
    {
        "code": "initial_reads_not_committed",
        "br_ref": "BR-CUS-021",
        # ⚠ AMENDED 2026-08-26 (CR-038 W9 task 3): the flow CAN commit them
        # now — `initial_reads` in the payload routes through the metering
        # event door (BR-MET-128) — so this entry rides ONLY a move-in that
        # captured none. `move_in` filters it out when reads were committed.
        "detail": "no opening reads were captured on this move-in; readings commit through "
        "the metering event door (BR-MET-128) when the wizard captures them, and none were",
    },
)


def _end_service_agreements(account: models.Account, ended_on: date) -> list[Any]:
    """BR-CUS-030 / US-CUS-005 §5: the move-out date lands in `accounts.closed_at`
    AND in every open `service_agreements.ended_on`.

    Writing `ended_on` is the documented CLOSE of an agreement, not an edit of
    history: B2 §2 declares the column as "NULL = still in force". The rows
    themselves are never deleted and their `started_on` is never touched, so the
    unit's occupancy history stays sequential and readable (T4-06 step 5)."""
    closed: list[Any] = []
    rows = models.ServiceAgreement.objects.filter(
        tenant_id=account.tenant_id, account=account, ended_on__isnull=True
    ).order_by("started_on", "id")
    for row in rows:
        row.ended_on = ended_on
        row.save(update_fields=["ended_on", "updated_at"])
        closed.append(row)
    return closed


def _final_bill_handoff(
    account: models.Account,
    moved_out_on: date,
    detail: dict[str, Any],
    *,
    final_reads: dict[str, Any] | None = None,
    final_read_state: str | None = None,
) -> dict[str, Any]:
    """BR-CUS-031 (CONFIRMED) — "{account, move-out date, committed final reads,
    plan snapshot per service date, prior balance, deposit disposition, refund
    method}; billing prorates per B4.3 (through the move day, BR-CUS-056) and
    issues the immutable final invoice — customers never writes invoices."

    Assembled from what EXISTS. Four of the seven elements have no source in
    this repository, and each carries its rule id instead of a plausible value —
    a handoff whose `final_reads: []` meant "none were taken" and whose
    `deposit_disposition: null` meant "nothing to settle" would read as complete
    to the bill run that eventually consumes it.

    NOT PERSISTED, and the record says so: `persisted: False`. There is no
    handoff table, queue or outbox anywhere in B2 or its addenda, so this
    contract lives in the API response and in the `account.closed` audit row.
    No money is computed here: `prior_balance` and `deposit_on_file` are the
    stored NUMERIC(18,6) columns, serialized by the read layer.
    """
    return {
        "account_id": str(account.id),
        "account_no": account.account_no,
        "unit_id": str(account.unit_id),
        "moved_out_on": moved_out_on.isoformat(),
        # BR-CUS-056: the OUTGOING account pays the move day, so the final bill
        # runs THROUGH it — stated explicitly so billing never has to guess
        # whether the boundary is inclusive.
        "bill_through": moved_out_on.isoformat(),
        "bill_through_br_ref": "BR-CUS-056",
        "currency": detail["currency"],
        "prior_balance": detail["balance"],
        "deposit_on_file": detail["deposit_on_file"],
        "deposit_received_on": detail["deposit_received_on"],
        # ⚠ AMENDED 2026-08-26 (CR-038 W9 task 4): BR-CUS-031's "committed
        # final reads" element is SERVED when the metering read seam answered
        # at close — the unit's committed heads per meter/register plus the
        # how-obtained flag (`taken`/`due`/`estimated`, accounts.
        # final_read_state). `None` + the rule id stays the honest shape for a
        # deployment whose seam did not resolve — never an empty list, which
        # would read as "none were taken" (this docstring's own warning).
        "final_reads": final_reads,
        "final_read_state": final_read_state,
        "final_reads_unavailable": None if final_reads is not None else "BR-CUS-021",
        # ⚠ **DEF-2419 SERVED THE UNIT'S PLAN ON THE ACCOUNT DETAIL. IT IS
        # DELIBERATELY NOT SERVED HERE, AND THIS COMMENT EXISTS SO THE NEXT LANE
        # DOES NOT "FINISH THE JOB" BY ADDING IT.**
        #
        # `account_detail_dict` gained `unit_plan` on 2026-09-01 — the plan the
        # unit stands on TODAY, read through `accounts.unit_id`. That is a
        # SCREEN read: a clerk looking at an account can see which plan it is
        # billed on, and a wrong-by-a-day answer costs a second glance.
        #
        # BR-CUS-031 asks this handoff for something different in kind: the
        # **"plan snapshot per service date"**, a HISTORICAL fact that prices an
        # immutable final invoice. Today's plan is not that fact, and dropping
        # it in under any key would be the "plausible-looking value" this
        # function's own docstring refuses — on a money path, where the cost is
        # a customer billed on the wrong rates rather than a second glance.
        # Billing already resolves the unit's plan itself in `billing/gather.py`
        # when it needs one; a second path to the same fact through here would
        # be a copy that drifts.
        "plan_snapshot": None,
        "plan_snapshot_unavailable": "BR-CUS-029",
        "deposit_interest_accrued": None,
        "deposit_interest_unavailable": "BR-CUS-057",
        "deposit_disposition": None,
        "deposit_disposition_unavailable": "BR-CUS-025",
        "refund_method": None,
        "refund_method_unavailable": "BR-CUS-025",
        "persisted": False,
        "persistence_unavailable": "BR-CUS-031",
    }


def _check_move_out_against_issued_bills(
    account: models.Account, moved_out_on: date, warnings: list[dict[str, Any]]
) -> None:
    """US-CUS-005 TC-6 (negative): "move-out date before the last issued bill's
    period end → blocked; issued bills are untouched (BR-BIL-004); corrections
    route via J6, not move-out backdating."

    ⚠ **THIS DOCSTRING DESCRIBED AN UNWIRED SEAM UNTIL 2026-09-24
    (`DEF-CUS-6465`).** It read *"billing owns the invoices and has no tables, so
    the seam is unwired"* — true when written, and `DEF-035` wired
    `last_issued_invoice_period_end` on 2026-08-11. A None from it now means THIS
    ACCOUNT has no issued bill, which is a fact about the account.

    The not-checked outcome is still recorded on a None, because a seam that goes
    missing again must fail visibly rather than silently permitting what this
    check exists to refuse — silence would read as "the check passed"."""
    period_end = seams.last_issued_invoice_period_end(account.id)
    if period_end is None:
        warnings.append(
            {
                "code": "move_out_date_not_checked_against_issued_bills",
                "br_ref": "BR-BIL-004",
                # ⚠ **THE REASON CHANGED UNDER THIS SENTENCE (`DEF-CUS-6465`).**
                # It blamed a missing `invoices` table; the seam has been WIRED
                # since `DEF-035`, so a None here means THIS ACCOUNT has no
                # issued bill — a fact about the account, not about billing.
                "detail": "this account has no issued bill, so there is no period end to "
                "check the move-out date against",
            }
        )
        return
    if moved_out_on < period_end:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-BIL-004",
            message_key="customers.account.move_out_behind_issued_bill",
            params={
                "moved_out_on": moved_out_on.isoformat(),
                "issued_through": period_end.isoformat(),
            },
        )


# ══════════════════════════════════════════════════════════════════════════
# CR-038 W9 — EVENT READS through the metering door (BR-CUS-021 · BR-MET-128)
# ══════════════════════════════════════════════════════════════════════════
def _adopt_wizard_draft(actor: Any, wizard_park_id: Any, *, flow: str) -> str | None:
    """Take the draft's reference for the finished record, and delete the draft.

    `CR-122-BRC06`. A draft (`tenancy.WizardPark`) is allocated its flow's
    number — `MVI-{YY}-{0000}` for a move-in, `MVO-{YY}-{0000}` for a move-out
    — from the SAME series the finished record draws from, the moment the
    wizard writes the row. The tab draws a REFERENCE column over an OPEN
    counter and a clerk chasing an unfinished job has to be able to quote
    something. This is where that number stops being a draft's and becomes the
    record's.

    ⚠ **IT WAS `_adopt_move_in_draft` UNTIL 2026-09-20 AND THE `flow` ARGUMENT
    IS THE WHOLE CHANGE** (PO ruling of that date, option A, item 9 — *"a
    parked move-out is allocated a reference"*). The caller names the flow it
    is committing, and a draft of any OTHER flow is ignored exactly as a
    missing one is: a move-out may not consume a move-in's number, which is
    the check the old hardcoded `!= "move_in"` was really making.

    ⚠ **CALL IT INSIDE THE COMMIT'S OWN TRANSACTION.** The delete and the
    `move_records` insert must stand or fall together: a reference live on two
    rows at once would break `uq_wizard_parks_tenant_reference_ci`'s whole
    point, and a draft deleted by a commit that then failed would destroy the
    very typing this change exists to protect.

    ⚠ **EVERY FAILURE HERE RETURNS None AND COMMITS THE MOVE ANYWAY.** No
    draft, a draft of another flow, a draft another tenant owns, a draft
    already gone — none of them is a reason to refuse a household service.
    `record_move` then allocates a fresh number exactly as it did before this
    change, which is the behaviour every caller that sends no draft still gets.
    The posture is `moves._allocate_move_no`'s, in its own words: *"The move is
    the regulated act; its reference is not."*

    ⚠ **THE TENANT SCOPE IS THE QUERY'S, NOT THE CALLER'S.** `wizard_park_id`
    arrives in a client payload. `wizard_parks.park_row` reads through the
    tenant-scoped manager under RLS FORCE (CLAUDE.md rule 1), so a park id from
    another tenant resolves to nothing and this returns None — a caller can
    name a draft, never a number.
    """
    if not wizard_park_id:
        return None
    try:
        from apps.tenancy import wizard_parks as tenancy_parks

        row = tenancy_parks.park_row(wizard_park_id, lock=True)
        if row.flow != flow:
            return None
        reference = row.reference or None
        # Rule 4 does not reach here and the distinction matters: a draft is a
        # FORM, not a financial record, and BR-SHL-048 says so — *"a parked
        # wizard holds nothing"*. Discarding one is free and is what finishing
        # the job means.
        row.delete()
        return reference
    except Exception:  # noqa: BLE001 - see the docstring: never refuse the move
        return None


def _refuse_bad_read_dates(rows: list[dict[str, Any]], *, field: str, unit_id: Any) -> None:
    """**A read date a clerk CHOSE is bounded — PO ruling 2026-10-17.**

    Decision log *"WHERE A USER ENTERS A METER READING"*: Move-in step 1's read
    date is REQUIRED (`DEF-CUS-10165`), Mark as cut takes a closing reading with
    its date (`DEF-CUS-10166`) and Enter opening read takes a date
    (`DEF-CUS-10167`). A reading cannot have been taken TOMORROW, and a
    reading dated before the meter's last committed reading would slot a
    figure in BEHIND history the bills were already priced from — so both are
    refused here, by row, with everything still on the clerk's screen. The
    screen holds the same two bounds (`MeterReadingEntry.readDateProblem`);
    this is the half that holds when a caller is not that screen.

    · Only rows that CARRY a `read_at` are checked. A row with none takes the
      flow's own event date (`default_read_at`), which is what every caller
      written before this rule sent — backward compatible by construction.
    · *Today* is the TENANT's (`seams.tenant_today`, BR-TEN-020/043), never a
      server clock.
    · *Before the last reading* compares calendar days: the same day as the
      last reading is lawful (two readings in a day happen). The last reading
      is metering's per-meter `latest_read_at` for the unit
      (`seams.latest_read_dates_for_units`). Where that read is UNWIRED or the
      flow has no unit, the lower bound cannot be answered and is not
      invented — the future-date check still runs.
    """
    explicit = [(i, row) for i, row in enumerate(rows, start=1) if row.get("read_at")]
    if not explicit:
        return
    fe: list[dict[str, Any]] = []
    today = seams.tenant_today()
    latest: dict[str, str] = {}
    if unit_id not in (None, "", "None"):
        sweep = seams.latest_read_dates_for_units([unit_id])
        if sweep is not None:
            for bucket in sweep.values():
                for meter in bucket.get("meters") or ():
                    if meter.get("asset_no") and meter.get("latest_read_at"):
                        latest[str(meter["asset_no"])] = str(meter["latest_read_at"])[:10]
    for index, row in explicit:
        raw = str(row.get("read_at"))[:10]
        try:
            day = date.fromisoformat(raw)
        except ValueError:
            fe.append(
                _field_error(
                    f"{field}[{index}].read_at",
                    errors.VAL_FORMAT,
                    "customers.event_reads.read_at_invalid",
                    value=str(row.get("read_at")),
                )
            )
            continue
        if day > today:
            fe.append(
                _field_error(
                    f"{field}[{index}].read_at",
                    errors.VAL_RANGE,
                    "customers.event_reads.read_at_future",
                    br_ref="BR-CUS-021",
                    read_at=raw,
                    today=today.isoformat(),
                    meter_no=str(row.get("meter_no") or ""),
                )
            )
            continue
        last = latest.get(str(row.get("meter_no") or ""))
        if last is not None and raw < last:
            fe.append(
                _field_error(
                    f"{field}[{index}].read_at",
                    errors.VAL_RANGE,
                    "customers.event_reads.read_at_before_last",
                    br_ref="BR-CUS-021",
                    read_at=raw,
                    last_read_at=last,
                    meter_no=str(row.get("meter_no") or ""),
                )
            )
    _refuse_fields(fe)


def _commit_event_reads(
    actor: Any,
    *,
    event: str,
    reads: Any,
    default_read_at: date | None,
    context: dict[str, Any],
    bounded_dates: bool = False,
    field: str | None = None,
) -> dict[str, Any]:
    """The wizards' captured reads → `seams.commit_event_reads`, one call.

    BR-CUS-021: reads commit *"via the metering service (append-only
    BR-MET-017)"* — customers never writes `meter_reads` (B1/B8); this
    normalises the wizard payload and hands it through the ONE seam.

    · Each row is `{meter_no, value | estimate, channel?, read_at?}`; a row
      with no `read_at` takes `default_read_at` — the flow's OWN event date
      (move-in `opened_at`, move-out/transfer the move day, disconnect
      `cut_on`), never a wall clock (BR-TEN-043).
    · A non-list / empty / junk `reads` payload is REFUSED, not skimmed: a
      wizard that sent readings must learn what happened to every one.
    · **An UNWIRED seam REFUSES the payload** (`event_read_door_unwired`).
      Dropping keyed readings on the floor because a deployment lacks the door
      is DEF-075's shape on a write: the caller typed facts and the system
      would silently agree while recording nothing.
    · BR-MET-129 rides the door: WARNED rows post flagged; ERRORS raise with
      named rows, and because every caller wraps this in its own transaction,
      a refused read refuses the whole wizard commit (BR-SHL-019 — one
      transactional commit) with everything still on the clerk's screen.
    """
    if not isinstance(reads, list) or not reads:
        _refuse_fields(
            [
                _field_error(
                    "initial_reads" if event == "move_in" else "final_reads",
                    errors.VAL_FORMAT,
                    "customers.event_reads.rows_required",
                )
            ]
        )
    rows: list[dict[str, Any]] = [dict(raw) if isinstance(raw, dict) else {} for raw in reads]
    if bounded_dates:
        # PO 2026-10-17 — a date the clerk chose is bounded by today and the
        # meter's last reading, BEFORE the default fills the rest.
        _refuse_bad_read_dates(
            rows,
            field=field or ("initial_reads" if event == "move_in" else "final_reads"),
            unit_id=context.get("unit_id"),
        )
    for row in rows:
        if not row.get("read_at") and default_read_at is not None:
            row["read_at"] = default_read_at.isoformat()
    answer = seams.commit_event_reads(actor, {"event": event, "reads": rows, "context": context})
    if answer is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-021",
            message_key="customers.event_reads.door_unwired",
            params={
                "code": "event_read_door_unwired",
                "detail": (
                    "this deployment's metering publishes no "
                    "`services.commit_event_reads`, so the readings keyed on this "
                    "wizard cannot be committed — refused rather than dropped"
                ),
            },
        )
    return answer


def _final_read_state(answer: dict[str, Any] | None, moved_out_on: date) -> str | None:
    """CR-038 W9 task 4 — HOW the settlement's final read was obtained.

    Derived ONCE, at close, from the metering read seam, and stored on the
    account row beside `closed_at` (`models.FINAL_READ_STATES`):

        taken     ≡ every meter currently on the unit has a committed lineage
                    head at/after the move-out date, none of them an estimate
        estimated ≡ covered the same way, but ≥1 covering head IS an estimate
                    — B18 §5.6.2's amber cell, the state TC-MVO-7 proved had
                    no store until `accounts.final_read_state`
        due       ≡ any meter has no committed head at/after the date

    `None` — stored as NULL — is three honest absences, never a verdict: the
    seam did not resolve (a deployment fact), or the unit holds no meters
    (nothing can ever be read there; `unit_has_no_meters` is the cell's own
    absence), or the close predates the column. The move worklists render each
    with its reason (`move_reads.unit_reads_cell`).

    The covering definition is `move_reads._meters_due`'s, restated on the
    WRITE side deliberately: this runs at close inside `move_out`'s
    transaction, the list derives at read time, and both compare a per-meter
    `latest_read_at` (ISO, lexically ordered) against the row's own event date
    (BR-TEN-043 — never a clock). `answer` is ONE `seams.reads_for_unit`
    sweep, made by the caller and shared with the handoff — never a second
    opinion fetched here.
    """
    if answer is None or not answer["meters"]:
        return None
    threshold = moved_out_on.isoformat()
    covering: list[dict[str, Any]] = []
    for meter in answer["meters"]:
        latest = meter["latest_read_at"]
        if not (latest and latest >= threshold):
            return "due"
        covering.extend(
            register
            for register in meter["registers"]
            if register["read_at"] and register["read_at"] >= threshold
        )
    if any(register["estimated"] for register in covering):
        return "estimated"
    return "taken"


def _clean_close_reason(raw: Any, fe: list[dict[str, Any]]) -> str | None:
    """WHY THIS TENANCY ENDED — one of `models.CLOSE_REASONS`, or nothing.

    PO ruling 2026-09-20, option A (decision log *"TEN MOVE-OUT RULINGS IN ONE
    SITTING"* item 3). `BR-CUS-030`.

    ⚠ **OMITTED IS LAWFUL AND IS NOT THE SAME AS WRONG.** A move-out sent with
    no `reason` closes the account and leaves `close_reason` NULL — that is the
    behaviour every caller written before today already has, and refusing it
    would break the import, the two existing endpoints' tests and every
    scenario in `move_out_scenarios.sh` on a field the PO asked us to START
    collecting rather than to START demanding. **Whether the wizard should
    REQUIRE it is a screen decision and the screen makes it** (the select is
    marked required there); the door stays open so a job can still be closed
    by a caller that has no clerk in front of it.

    ⚠ **AN UNKNOWN CODE IS REFUSED BY NAME AND NEVER COERCED TO `other`.**
    Silently mapping a typo onto a real bucket is how a count becomes a lie:
    `other` would grow by every client bug, and nobody reading the report could
    tell. The refusal names the five so a developer reading the envelope learns
    the vocabulary without going to look it up.

    ⚠ **EMPTY STRING IS TREATED AS OMITTED, DELIBERATELY.** An HTML select that
    has not been touched posts `""`, and refusing that would make *"I have not
    chosen yet"* an error the clerk cannot clear by choosing nothing. It is the
    same reading `_clean_waiting_on` takes of an empty reason one module over.
    """
    if raw is None:
        return None
    value = str(raw).strip()
    if value == "":
        return None
    if value not in models.CLOSE_REASONS:
        fe.append(
            _field_error(
                "reason",
                errors.VAL_UNKNOWN_LOOKUP,
                "customers.account.close_reason_unknown",
                br_ref="BR-CUS-030",
                value=value,
                allowed=list(models.CLOSE_REASONS),
            )
        )
        return None
    return value


def _field_visit(election: Any) -> dict[str, Any]:
    """The whole field-visit answer a flow sent — `DEF-CUS-6363`.

    `{"template_ids": [...], "orders": [...], "none": bool}`. `template_ids` is
    the published-template tick the panel has offered since CR-070 wave P;
    `orders` are the rows a clerk ADDED (job type, priority, due, assignee,
    note — `apps.work.from_flows.clean_order_rows`); `none` is the *No visit
    needed* tick. The rows are validated HERE, before any transaction opens, so
    a row with no job type is refused by name with everything still on screen.
    """
    if not election:
        return {"template_ids": [], "orders": [], "none": False}
    if isinstance(election, dict):
        ids = election.get("template_ids") or []
        rows = election.get("orders") or []
        none = bool(election.get("none"))
    else:
        ids, rows, none = election, [], False
    if none and (ids or rows):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.fromFlows.noneWithOrders",
            params={"field": "field_visit.none"},
        )
    return {
        "template_ids": [str(one).strip() for one in ids if str(one).strip()],
        "orders": seams.clean_flow_order_rows(rows),
        "none": none,
    }


def _field_visit_templates(election: Any) -> list[str]:
    """The templates a clerk ticked on the field-work panel, or nothing.

    `{"template_ids": ["…", "…"]}` — a dict rather than a bare list because the
    panel will grow a *why* and a *when* and a payload key that is a list has
    nowhere to put them. **An empty election is a complete answer** and the
    normal one: most move-outs need nobody to attend.
    """
    if not election:
        return []
    if isinstance(election, dict):
        ids = election.get("template_ids") or []
    else:
        ids = election
    return [str(one).strip() for one in ids if str(one).strip()]


def _raise_flow_work(
    actor: Any, *, flow_kind: str, flow_id: Any, template_ids: Any, orders: Any = ()
) -> dict[str, Any]:
    """Ask Work for the jobs, and **never let the answer fail the flow**.

    `BR-WRK-055` and judgment 7, in one function so every door in this module
    keeps the posture identically rather than three times approximately. The
    catch is deliberately BROAD, and that is not laziness: an unpublished seam,
    a template deactivated between the panel drawing and the button being
    pressed, a flow with no anchor and a database that refuses the row all mean
    the same thing to the person at the counter — *the visit was not booked* —
    and every one of them must leave the move completed. A narrower catch turns
    the last case into a customer who cannot close their account.

    ⚠ **IT RETURNS THE SENTENCE RATHER THAN SWALLOWING.** One code, one
    catalogue key, in the shape `MOVE_OUT_UNAVAILABLE`'s rows already take.
    """
    work_orders: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if template_ids:
        try:
            raised = seams.raise_flow_work_orders(
                actor, flow_kind=flow_kind, flow_id=flow_id, template_ids=template_ids
            )
            work_orders.extend(raised.get("raised", []))
        except Exception as exc:  # noqa: BLE001 - see the docstring: every failure is one fact
            _log_not_raised(flow_kind, flow_id, len(template_ids), exc)
            warnings.append(seams.flow_work_not_raised(str(exc) or None))
    # `DEF-CUS-6363` — the rows a clerk ADDED. Same posture, same sentence when
    # the raise fails, and a per-order warning when only the assignee did not
    # stick (the order itself was raised and is in the dispatcher's queue).
    if orders:
        try:
            raised = seams.raise_flow_order_rows(
                actor, flow_kind=flow_kind, flow_id=flow_id, rows=list(orders)
            )
            work_orders.extend(raised.get("raised", []))
            warnings.extend(raised.get("warnings", []))
        except Exception as exc:  # noqa: BLE001 - see the docstring: every failure is one fact
            _log_not_raised(flow_kind, flow_id, len(list(orders)), exc)
            warnings.append(seams.flow_work_not_raised(str(exc) or None))
    return {"work_orders": work_orders, "warnings": warnings}


def _log_not_raised(flow_kind: str, flow_id: Any, asked: int, exc: BaseException) -> None:
    """`DEF-WRK-9784` — a raise that failed is LOGGED as well as warned.

    The warning is the clerk's; this line is support's. Until 2026-10-06 the
    catch kept only `str(exc)` on the response, so a move-in that booked none
    of the visits a clerk asked for left no trace on the server at all — M6's
    two visits were found only by a person reading the done screen. The
    message key travels when the failure is one of ours, so the log names the
    refusal (`work.order.template_wrong_service`) rather than a bare class.
    """
    logger.warning(
        "flow work orders not raised: flow=%s id=%s asked=%d refusal=%s detail=%s",
        flow_kind,
        flow_id,
        asked,
        getattr(exc, "message_key", None) or type(exc).__name__,
        str(exc) or None,
    )


def _reads_committed(event_reads: dict[str, Any] | None) -> int:
    """How many readings THIS job committed — the `move_records` count.

    `DEF-CUS-5933`: metering's event door answers a KEYED reading in `posted`
    (counted by `posted_reads`) and an ESTIMATED one in a separate `estimates`
    list, where `estimated: True` means the estimate WAS persisted as a
    `meter_reads` row (`metering.services.estimate_missing_read`) and
    `estimated: False` is a refusal-as-data that wrote nothing. Reading
    `posted_reads` alone filed an estimated final read under nought while
    `accounts.final_read_state` read `estimated` off that very row — one
    commit, two answers about one reading. Both kinds are counted here; a
    refused estimate is not, because no row exists for it.
    """
    answered = event_reads or {}
    keyed = int(answered.get("posted_reads") or 0)
    estimated = sum(1 for row in (answered.get("estimates") or ()) if row.get("estimated") is True)
    return keyed + estimated


#: `DEF-CUS-10093` — the two `MOVE_OUT_UNAVAILABLE` rows a drafted final bill
#: makes false. Each still rides a move-out that drafted none.
FINAL_BILL_DRAFT_SUPERSEDES = ("final_bill_not_issued", "deposit_not_settled")


def _draft_final_bill(actor: Any, account: Any, moved_out_on: date) -> dict[str, Any]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-CUS-10093` — billing drafts the final bill, or the move-out stops.

    PO ruling 2026-10-13, option B: *"If the draft cannot be created, the
    move-out does not complete, and the refusal is shown."* Billing's answer
    is `drafted`, `nothing_to_bill` (every day up to the move day is on an
    issued bill — BR-BIL-004, nothing is billed twice) or `refused` with the
    engine's own reason. A refusal is raised as ONE catalogue sentence with the
    engine's own key carried as `cause_key`, so the wizard says what failed and
    why. Customers writes no invoice (BR-CUS-037): the seam is the only door.
    """
    answer = seams.draft_move_out_final_bill(
        actor, account_id=account.id, moved_out_on=moved_out_on
    )
    if answer.get("outcome") == "refused":
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-BIL-013 · DEF-CUS-10093",
            message_key="customers.move_out.final_bill_not_drafted",
            params={
                **dict(answer.get("params") or {}),
                "reason": answer.get("reason"),
                "cause_key": answer.get("message_key"),
                "detail": answer.get("detail"),
            },
        )
    return dict(answer)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def move_out(actor: Any, account_id: Any, payload: Any = None) -> dict[str, Any]:
    """POST /accounts/{id}/move-out (11b §S20 · US-CUS-005 · BR-CUS-030).

    The occupant leaves: `closed_at` = the move-out date, status → the terminal
    status, every open service agreement ends on the same date, one
    `account.closed` audit row. BR-MET-036 then DERIVES the unit back to vacant
    — the terminal class does not occupy — which is the whole point: before this
    flow existed, the only way to free a unit was a direct status write, and
    `_apply_status_change` refuses those.

    What it does NOT do is in MOVE_OUT_UNAVAILABLE, verbatim, on every response.
    The BR-CUS-031 handoff it CAN assemble is returned as `final_bill_handoff`
    and is not persisted anywhere (see `_final_bill_handoff`).

    NO advisory scope lock here, deliberately, and this is the asymmetry worth
    stating: the BR-CUS-017 lock exists because a create/move-in decides about
    rows that do NOT yet exist, which `SELECT … FOR UPDATE` cannot lock. A
    move-out decides about ONE existing row, so `account_or_404(lock=True)` is
    the whole mutual exclusion — a second move-out waits on the row, then reads
    the terminal status and is refused as "not an occupant". A move-in racing
    the same unit blocks on that same row lock inside its own occupancy check
    (`occupying_accounts_for_unit(lock=True)`), so the turnover is serialized
    from both directions without a second lock to keep in step with the first.

    ONE transaction; audited (CLAUDE.md rule 7).
    """
    from apps.customers import selectors

    data = _payload_dict(payload or {})
    _reject_unknown(data, MOVE_OUT_FIELDS)
    fe: list[dict[str, Any]] = []
    if data.get("moved_out_on") in (None, ""):
        fe.append(
            _field_error(
                "moved_out_on", errors.VAL_REQUIRED, "customers.account.move_out_date_required"
            )
        )
    moved_out_on = _date(data.get("moved_out_on"), "moved_out_on", fe)
    status = _resolve_status(data["status"], fe) if "status" in data else None
    # ── WHY THIS TENANCY ENDED (PO ruling 2026-09-20 item 3, option A) ──────
    # Validated HERE, with the other fields, so a bad code refuses before the
    # transaction opens and the clerk keeps everything else they keyed.
    close_reason = _clean_close_reason(data.get("reason"), fe)
    shortfall_path = data.get("shortfall_path")
    if shortfall_path not in (None, "", "transfer", "collect", "payment_plan"):
        fe.append(
            _field_error(
                "shortfall_path", errors.VAL_FORMAT, "customers.move_out.shortfall_path_unknown"
            )
        )
    _refuse_fields(fe)
    # CR-038 W9 task 4 — the wizard's captured final reads. Lifted out here;
    # no account write below reads the payload again, so the readings travel
    # ONLY through the metering event door (BR-CUS-021).
    final_reads_payload = data.get("final_reads")
    # CR-070 wave P — the field visit the clerk elected on STEP 2. Lifted out
    # here for `final_reads`' reason: no account write below reads the payload
    # again, so the election travels only to Work and never near an account row.
    #
    # ⚠ **`_field_visit` AND NOT `_field_visit_templates` SINCE 2026-09-24 —
    # `DEF-CUS-6487`.** The narrow parser returns `template_ids` alone, so the
    # ROWS a clerk adds in the approved field-visit table and the *No visit
    # needed* answer were parsed out of the payload and thrown away. The PO
    # approved `FieldVisitOrders` for this flow that day (*"this si correct -
    # use it"*), and that component emits `{none, orders}` — so mounting it
    # over this parser would have given a clerk seven columns and an *Add work
    # order* button over a door that raised nothing, while the move-out
    # reported success. **Hard-won law 2's mirror, and worse than a dead prop:
    # a dead prop renders nothing and is visible; this one accepts input, the
    # flow succeeds, and no crew is ever sent.**
    #
    # **THE CHANGE IS ADDITIVE, WHICH IS WHY IT IS SAFE ON THIS DOOR.**
    # `_field_visit` parses `{"template_ids": [...]}` exactly as the narrow one
    # did, so every existing caller is unaffected (asserted by
    # `test_the_template_tick_still_raises_its_job`); it adds the two parts the
    # move-in and the transfer have read since `DEF-CUS-6363` in `2.351.0`.
    # That defect taught two of the three doors and did not re-read this one —
    # **a door that ignores a key nobody sends is indistinguishable from a door
    # that handles it**, which is why no test could have caught it before the
    # component arrived.
    field_visit = _field_visit(data.get("field_visit"))
    # PO ruling 2026-09-20 item 9 — the draft this move-out was keyed into.
    # Lifted out here for `final_reads`' reason; resolved below, inside the
    # transaction, so the draft's `MVO-` number becomes the record's.
    wizard_park_id = data.get("wizard_park_id")
    warnings: list[dict[str, Any]] = []
    event_reads: dict[str, Any] | None = None

    with transaction.atomic():
        account = selectors.account_or_404(account_id, lock=True)
        before = selectors.account_detail_dict(account)
        if status is None:
            status = _default_closed_status()
        if status.behavior_class != CLASS_TERMINAL:
            # A move-out that left the account occupying its unit would free
            # nothing — BR-MET-036 derives occupancy from the behaviour CLASS.
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-055",
                message_key="customers.account.status_does_not_close",
                params={"status": status.code, "behavior_class": status.behavior_class},
            )
        if not is_occupying(account.status):
            # Only an OCCUPANT can move out. A `pending_activation` draft never
            # took the unit (BR-CUS-018) and an already-terminal account has
            # left it (BR-MET-036) — closing either would write a `closed_at`
            # for a tenancy that never happened or happened twice.
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-030",
                message_key="customers.account.not_an_occupant",
                params={
                    "account_no": account.account_no,
                    "status": account.status.code,
                    "behavior_class": account.status.behavior_class,
                },
            )
        if account.opened_at is not None and moved_out_on < account.opened_at:
            # US-CUS-005 §5: the move-out date is "≥ opened_at". A tenancy
            # cannot end before it started, and the proration BR-CUS-022 asks
            # billing for would be negative days.
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-030",
                message_key="customers.account.move_out_before_start",
                params={
                    "moved_out_on": moved_out_on.isoformat(),
                    "opened_at": account.opened_at.isoformat(),
                },
            )
        # ── B19 §15.8 · A PARENT WITH OPEN CHILDREN IS WARNED, NOT REFUSED ──
        # `BR-CUS-1082`, **REVERSED BY PO RULING 2026-09-20 closing
        # `OQ-CUS-12515` on option (b), verbatim: *"option B - give a warning
        # and allow it; if owner has sold the property to new owner then we are
        # transfering all libalities and ownership to new owner"*.**
        #
        # ⚠ **THE REASON IS A FACT ABOUT THE PRODUCT RATHER THAN A JUDGMENT
        # ABOUT RISK, AND IT IS WHY THE ARGUMENT THAT STOOD HERE DOES NOT
        # SURVIVE.** This block used to RAISE, and reasoned from asymmetry:
        # refusing wrongly costs a support call, permitting wrongly writes a
        # NUMBERED move record that hard rule 4 forbids deleting. That
        # reasoning was sound, and the PO answered it with something the lane
        # did not have. **A landlord leaving is not a landlord abandoning their
        # tenants.** Where the property has been SOLD the act is a TRANSFER,
        # which moves the account, its liabilities and its ownership to the new
        # owner with the tenants untouched beneath it. So the case the refusal
        # protected against **already has its own flow**, and blocking the
        # move-out blocked only the legitimate remainder — an owner leaving for
        # some other reason entirely. A product that refuses a lawful act to
        # prevent a mistake the adjacent flow already prevents is not failing
        # closed; it is failing shut.
        #
        # ⚠ **ONE DEFINITION OF AN OPEN CHILD, AND IT SURVIVED THE REVERSAL
        # UNCHANGED.** `selectors.sub_accounts_for_master` is what
        # `settlement_for` counts for `open_sub_accounts`, so the number the
        # screen shows and the number this warns on cannot disagree. A
        # predicate rewritten here would be `DEF-CUS-5901`'s defect class — two
        # definitions of one word — and it would be that whether the answer
        # refuses or warns.
        #
        # ⚠ **THE READ STAYS WHERE THE RAISE WAS**, above `_commit_event_reads`
        # and before any write. It no longer HAS to be there to be correct —
        # closing a master does not close its children, so the count reads the
        # same either side of the commit — but moving it would be a change
        # nobody asked for on a money path, and reading the estate before the
        # flow touches it is the honest order.
        #
        # ⚠ **`[]` FOR EVERY ORDINARY ACCOUNT**, which is the common path and
        # the half a warning can still get wrong: the selector returns early on
        # `kind != master` and issues no query, so a tenant's move-out is
        # unchanged and its warnings list gains nothing. A warning that fired on
        # every account would pass a test of the master case exactly as a
        # correct one does — `tc2` and `tc3` are what separate them.
        open_children = selectors.sub_accounts_for_master(account)
        if open_children:
            warnings.append(
                {
                    "code": "master_closed_over_open_sub_accounts",
                    "br_ref": "BR-CUS-1082",
                    # ⚠ **THE SAME CATALOGUE KEY STEP 1 DRAWS**, in the shape
                    # every other warning on this response already takes
                    # (`MOVE_OUT_UNAVAILABLE`, `seams.flow_work_not_raised`).
                    # One pair of words in all eleven catalogues, so the strip
                    # the clerk read before the commit and the row they read
                    # after it cannot drift into two spellings of one fact.
                    "message_key": "customers.account.has_open_sub_accounts",
                    "account_no": account.account_no,
                    # The name the checker and the screen both key on, and the
                    # count the catalogue sentence interpolates. `count` is
                    # i18next's own plural selector, so one child reads "1
                    # sub-account is still open" and two read "2 sub-accounts
                    # are still open" without a second sentence in the code.
                    "open_sub_accounts": len(open_children),
                    "count": len(open_children),
                }
            )
        _check_move_out_against_issued_bills(account, moved_out_on, warnings)
        # ── DEF-CUS-10190 · WHAT THE LEAVING SETTLES (PO ruling 2026-10-17) ──
        # A live temporary stop ends and its open shut-off and turn-on jobs are called off; an open
        # disconnect case short of the cut closes as *customer left*. Inside
        # this transaction, so a refused reading below rolls both back. The
        # debt and any payment plan stay on this account — nothing here moves
        # money. See `move_in_units.settle_holds_at_move_out`.
        from apps.customers import move_in_units

        settled = move_in_units.settle_holds_at_move_out(actor, account, moved_out_on)

        # ── CR-038 W9 task 4: the FINAL READS, before the close ─────────────
        # Posted FIRST so the flag derivation and the handoff below read the
        # committed heads this very commit produced. Errors from the door
        # refuse the WHOLE move-out (one transaction, BR-SHL-019) with the
        # failing rows named; warnings post flagged (BR-MET-129).
        if final_reads_payload is not None:
            event_reads = _commit_event_reads(
                actor,
                event="move_out",
                reads=final_reads_payload,
                default_read_at=moved_out_on,
                context={
                    "account_id": str(account.id),
                    "account_no": account.account_no,
                    "unit_id": str(account.unit_id),
                    "flow": "move_out",
                },
            )

        # ── DEF-CUS-10093 · THE FINAL BILL IS DRAFTED HERE, BEFORE THE CLOSE ──
        # PO ruling 2026-10-13, option B, verbatim: *"Go with this - I recommend
        # B: nothing can be forgotten, readings are typed once, and the clerk
        # still reviews the bill before it goes out."* AFTER the reads, so the
        # draft prices the very dials step 3 priced (committed now, keyed then);
        # BEFORE `closed_at`, because billing refuses a closed account
        # (`final_bill.FINAL_ACCOUNT_ALREADY_CLOSED`). A refusal raises here and
        # this transaction rolls back the reads with it: the move-out does not
        # complete and the clerk keeps everything on screen. Drafted, never
        # issued — the clerk sends it from Billing.
        final_bill_draft = _draft_final_bill(actor, account, moved_out_on)

        # ── CR-185-BRC10 · BALANCE TO OWNER, RECORDED AT COMMIT ──────────────
        # 🔒 HUMAN-REVIEW-PENDING. Coordinator rulings 2026-10-14 (closing the
        # walk's `DEF-CUS-10152`): only money IN THE BOOKS moves. So the
        # tie-back is RECORDED here, inside this transaction — pending, with
        # the preview, when a final bill was drafted (it posts when that bill
        # is issued, from billing's issue path); posted here only when there
        # was nothing left to bill. A commit refused anywhere in this block
        # rolls the record back with everything else, so a refused move-out
        # moves no money and promises none. Step 3 only RECORDS the choice.
        balance_to_owner = None
        if shortfall_path == "transfer":
            from apps.customers import move_out_settlement

            balance_to_owner = move_out_settlement.record_balance_to_owner_at_commit(
                actor,
                account,
                final_bill_draft=final_bill_draft,
                moved_out_on=moved_out_on,
            )

        # HOW the settlement's final read was obtained — derived ONCE, stored
        # beside `closed_at` (models.FINAL_READ_STATES; NULL = seam unresolved
        # or a meterless unit — the read side states each absence). ONE seam
        # sweep serves both the flag and the handoff.
        seam_answer = seams.reads_for_unit(account.unit_id)
        read_state = _final_read_state(seam_answer, moved_out_on)
        handoff = _final_bill_handoff(
            account,
            moved_out_on,
            before,
            final_reads=seam_answer,
            final_read_state=read_state,
        )

        account.closed_at = moved_out_on
        account.status = status
        account.final_read_state = read_state
        # ⚠ **WHY THIS TENANCY ENDED, AND IT IS WRITTEN ONLY WHEN THE CLERK
        # ANSWERED** (PO ruling 2026-09-20 item 3). An omitted `reason` leaves
        # the column at NULL rather than writing `other`: NULL means *nobody
        # was asked* and `other` means *asked, and none of the four fitted* —
        # two different facts, and a report that folded them together would
        # over-count `other` by every close made before this column existed.
        # `_clean_close_reason` has already refused anything outside
        # `models.CLOSE_REASONS`, so this is a validated code or None.
        if close_reason is not None:
            account.close_reason = close_reason
        account.save(
            update_fields=[
                "closed_at",
                "status",
                "final_read_state",
                # ⚠ NAMED UNCONDITIONALLY, which is safe and is the point: when
                # `close_reason` was not set above, the field still holds what
                # the row already had, so writing it is a no-op. A conditional
                # `update_fields` list is two code paths through one save.
                "close_reason",
                "updated_at",
            ]
        )
        _end_service_agreements(account, moved_out_on)
        account.refresh_from_db()
        after = selectors.account_detail_dict(account)
        # The handoff rides the audit row because that is the only append-only
        # store it CAN reach today — stated, not implied (see the docstring).
        _audit(
            actor,
            "account.closed",
            account.id,
            before=before,
            after={**after, "final_bill_handoff": handoff, "final_bill": final_bill_draft},
        )
        # ── CR-039 wave D tasks 17–19: THE MOVE-OUT LEAVES A RECORD ──────────
        # PO ruling 2026-08-27, verbatim and in full: *"you cna keep them as
        # records for audit perpuses"*. BR-CUS-150/151: the record is of the
        # JOB, so nothing written above is copied into it — not the status, not
        # `closed_at`, not the readings. What it adds is the provenance this
        # function has held in local variables and thrown away since it was
        # written: who did it, at what moment, on what effective date, and how
        # many readings the job took.
        #
        # ⚠ **INSIDE THIS TRANSACTION, AFTER THE AUDIT ROW.** After, because a
        # refused reading or a refused status must roll the record back with
        # everything else — there must never be a record of a move-out that did
        # not happen (BR-SHL-019, one commit). Inside, because BR-TEN-035
        # requires the number to be allocated in the issuing transaction.
        # PO ruling 2026-09-20 item 9 — the draft's number becomes the record's
        # number, and the draft stops existing. Both inside this transaction,
        # so a refused reading rolls BOTH back: a clerk whose commit failed
        # still has their draft, with the same reference, where they left it.
        # See `_adopt_wizard_draft`; `move_in` above does exactly this.
        draft_reference = _adopt_wizard_draft(actor, wizard_park_id, flow=moves.KIND_MOVE_OUT)
        move_record = moves.record_move(
            kind=moves.KIND_MOVE_OUT,
            account_id=account.id,
            effective_on=moved_out_on,
            actor=actor,
            # PO ruling 2026-09-20 item 9 — see `_adopt_wizard_draft`. None
            # where no draft was sent, and `record_move` then allocates from
            # the same `move_out` series exactly as it always has.
            reserved_move_no=draft_reference,
            # A count, never a copy — `meter_reads` owns the readings
            # (BR-CUS-021). `0` where the wizard captured none, which is a real
            # answer and not an absence.
            reads_committed=_reads_committed(event_reads),
            # BR-TEN-057 — the tag rides the OWNING row, and this record's
            # owner is the account it closes: a demo estate's move-out is
            # sample data and BR-TEN-061 deletes on one predicate.
            is_sample=bool(account.is_sample),
            # CR-094-BRC01 — the application this move-out fulfils, where there
            # was one (`BR-CUS-080`). Read from the payload and never near an
            # account column, exactly as `final_reads` is.
            service_request_id=data.get("service_request_id"),
        )
        # ── CR-048 wave B task B10: THE OCCUPANT IS TOLD ─────────────────────
        # The teardown's finding, verbatim: *"the module that owns moving in has
        # no notification events at all"* — and the way out was just as silent.
        # `email_move_out_final` has been seeded on every tenant since
        # 2026-08-16 and nothing has ever sent it.
        #
        # ⚠ **INSIDE THIS TRANSACTION, AFTER THE MOVE RECORD, AND INSIDE ITS OWN
        # SAVEPOINT** — three separate decisions:
        #   · INSIDE, so a refused reading or a refused status rolls the message
        #     back with everything else; there must never be a letter about a
        #     move-out that did not happen (BR-SHL-019, one commit).
        #   · AFTER the record, because the message is KEYED on the record's id
        #     (rule 6 — see `notifications_seam`'s docstring for the
        #     account-keyed version of this and why it loses the letter).
        #   · IN ITS OWN SAVEPOINT, which the seam opens — hard-won law 14: on
        #     PostgreSQL a caught exception still aborts the transaction, so a
        #     `try` alone would lose this whole move-out at COMMIT.
        move_message = notifications_seam.queue_move_out_final(
            move_record_id=move_record["move_record_id"],
            account_id=account.id,
            effective_on=moved_out_on,
            # DEF-NOT-10536 (PO 2026-10-22) — the email carries the closing
            # reads this commit just wrote (the sweep above, each with its
            # unit) and the final bill drafted above, with its PDF.
            closing_reads=seam_answer,
            final_bill=final_bill_draft,
            actor=actor,
        )
    # `final_reads_not_committed` rides ONLY a flow that really committed none
    # — with reads captured above, the old warning would be false (hard-won
    # law 1: a stale claim is a stale claim in either direction).
    #
    # ⚠ **AND `deposit_interest_not_accrued` JOINED IT ON 2026-09-24
    # (`DEF-CUS-6465`).** The accrual landed on 2026-09-03 (`CR-059` CS-20) and
    # `selectors.deposit_interest_accrued` answers, so an UNCONDITIONAL row told
    # every clerk that no interest was worked out — including on the accounts
    # where it had been. An unconditional entry is a claim about the PRODUCT; a
    # conditional one is a claim about THIS move-out, and this is the second.
    #
    # ⚠ **THE READ IS WRAPPED, AND NOT OUT OF TIDINESS.** This runs AFTER the
    # transaction has committed the close, so an accrual that raises must not
    # take the move-out down with it — `BR-WRK-055`'s posture applied to a read:
    # the customer's account is closed either way, and a figure we could not work
    # out is reported as exactly that.
    # Imported HERE rather than at module scope, the way `_make_occupying` does
    # it one screen up: `selectors` imports this module back, and a top-level
    # import is a cycle.
    from apps.customers import selectors as customers_selectors

    try:
        accrued = customers_selectors.deposit_interest_accrued(account.id, moved_out_on)
    except Exception:  # noqa: BLE001 — a failed read is "no figure", never a failed move-out
        accrued = None
    # `DEF-CUS-10093` — with a final bill DRAFTED, "No final bill was raised"
    # and "settling the deposit needs the final bill" are both false: the bill
    # exists and its issue applies the deposit. They ride only a move-out that
    # drafted none (every day already on an issued bill).
    drafted = final_bill_draft.get("outcome") == "drafted"
    warnings.extend(
        dict(entry)
        for entry in MOVE_OUT_UNAVAILABLE
        if not (entry["code"] == "final_reads_not_committed" and event_reads is not None)
        and not (entry["code"] == "deposit_interest_not_accrued" and accrued is not None)
        and not (entry["code"] in FINAL_BILL_DRAFT_SUPERSEDES and drafted)
    )
    # ── CR-070 wave P · the final read somebody has to go and take ─────────
    #
    # ⚠ **AFTER THE COMMIT, DELIBERATELY, AND THAT IS `BR-WRK-055` IN CODE.**
    # *"the move-out does not wait for the visit and the visit does not close the
    # account"*. The account is closed and settled the moment the block above
    # commits; the job is raised against the move record that commit created. A
    # raise that fails, refuses or cannot reach Work at all therefore cannot
    # touch a single thing the customer came in to have done — it comes back as
    # `work_orders_not_raised` and the clerk raises it from the dispatcher.
    visit = _raise_flow_work(
        actor,
        flow_kind="move_out",
        flow_id=move_record["move_record_id"],
        template_ids=field_visit["template_ids"],
        # `DEF-CUS-6487` — the ROWS a clerk added in the field-visit table.
        # `_raise_flow_work` has accepted `orders=` since `DEF-CUS-6363`; the
        # move-out simply never passed them, because it never had any to pass.
        orders=field_visit["orders"],
    )
    warnings.extend(visit["warnings"])
    result = {**after, "final_bill_handoff": handoff, "warnings": warnings, **move_record}
    # `DEF-CUS-10093` — the draft, named, so the completion screen can link it.
    result["final_bill"] = final_bill_draft
    # CR-185-BRC10 — what the commit moved to the owner, or None when the clerk
    # did not tie the shortfall back. The completion screen reads THIS.
    result["balance_to_owner"] = balance_to_owner
    result["work_orders"] = visit["work_orders"]
    # DEF-CUS-10190 — what leaving ended on the way (hold, restart job, case).
    result["settled"] = settled
    # `DEF-CUS-6487`, carrying `DEF-CUS-6363`'s rule to the third door: *No visit
    # needed* is an ANSWER and it is kept. A clerk who said nobody has to attend
    # is a different fact from a clerk who was never asked, and the PO kept the
    # control on this screen on 2026-09-24 for exactly that reason
    # (*"(a) Keep 'No visit needed'"*). Named on the response so the wizard can
    # say what was decided rather than infer it from an empty list.
    result["field_visit_declined"] = field_visit["none"]
    if event_reads is not None:
        result["event_reads"] = event_reads
    # Named on the response so the wizard can SAY what happened to the letter —
    # queued, already queued, or stopped by this utility's own switch. A message
    # whose outcome only existed inside a transaction is an outcome nobody can
    # see again (hard-won law 2 applied to a result rather than to a prop).
    result["move_message"] = [dict(row) for row in move_message]
    return result


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def move_in(actor: Any, from_account_id: Any, payload: Any = None) -> dict[str, Any]:
    """POST /accounts/{id}/move-in (11b §S19 · US-CUS-004) — the next occupant
    takes the unit the account named in the URL is leaving (T5-15 step 5's
    ratified recovery door).

    A NEW account with its own number: US-CUS-004 §1 and T4-06 step 5 are both
    explicit that reopening does not exist — "a returning customer is a NEW
    account". Nothing about the outgoing account is edited here.

    THE GUARD IS NOT COPIED. This path reaches the unit through the same
    `_make_occupying` as `create_account`: advisory lock on the (tenant, unit)
    scope FIRST, then the BR-CUS-017 check, then BR-CUS-056's boundary day. Two
    simultaneous move-ins to one unit therefore cannot both win, for exactly the
    reason two simultaneous creates cannot (tests/test_us_cus_004_move_in_race.py).

    Defaults to the tenant's `active` status because the wizard's exit is "unit
    derives Occupied"; a non-occupying status is refused rather than quietly
    producing a draft that frees nothing.
    """
    from apps.customers import selectors

    def resolve() -> tuple[Any, Any]:
        outgoing = selectors.account_or_404(from_account_id)
        return outgoing.unit_id, outgoing

    return _move_in(actor, payload, resolve)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def move_in_to_unit(actor: Any, unit_id: Any, payload: Any = None) -> dict[str, Any]:
    """`POST /units/{unit_id}/move-in` — the move-in that names the UNIT, for a
    unit nobody has lived in (`DEF-CUS-6353`, decided 2026-09-23 under the PO's
    move-in approval ruling of the same day, `OQ-CUS-12616`).

    ⚠ **WHY A SECOND DOOR EXISTS AT ALL.** `move_in` above takes the OUTGOING
    account in its path, so a vacant unit that has never had an account had no
    move-in road: the wizard offered it (the unit list reads `occupancy=vacant`,
    and a never-occupied unit is vacant) and then refused it in 26 words,
    pointing the clerk at New account. An approved move-in request for such a
    unit now lands the clerk on this wizard, so the refusal became a dead end on
    the ruled flow. Decision log 2026-09-23, *"NO APPLICATION FEE IS EVER
    CARRIED…"* §3: *"the move-in wizard serves a first-occupant unit … the server
    opens the account under the SAME guards `POST /accounts` already takes"*.

    ⚠ **THE GUARD IS NOT COPIED, EXACTLY AS FOR `move_in`.** Both doors run the
    one `_move_in` body, which reaches the unit through `_open_account` →
    `_make_occupying`: the advisory lock on the (tenant, unit) scope, then
    `BR-CUS-017` (one active account per unit), then `BR-CUS-056` (no start on
    or before the last tenancy's move day), then the plan and the start date.
    A first occupant simply has no move day for `BR-CUS-056` to compare with.

    ⚠ **THE PREDECESSOR IS DERIVED HERE, NEVER TRUSTED FROM THE CLIENT.** Where
    the unit DOES have a finished tenancy it is found by the same
    `selectors.last_closed_account_for_unit` the boundary rule reads, and it is
    recorded as the move record's `from_account` exactly as the account-scoped
    door records it — so the two doors cannot write two different histories of
    one unit. Where it has none, `from_account` is NULL, which is the true
    answer: nobody left.
    """
    from apps.customers import selectors

    def resolve() -> tuple[Any, Any]:
        return unit_id, selectors.last_closed_account_for_unit(unit_id)

    return _move_in(actor, payload, resolve)


def _carry_request_decisions(
    data: dict[str, Any], request_id: Any, *, carry_people: bool = False
) -> dict[str, Any]:
    """`DEF-CUS-9035` — **the request's linked customer and class reach the
    account its move-in opens.**

    PO ruling 2026-10-01: a portal move-in is carried to an ACTIVE customer and
    *"you will ahve to create or link customer ID"*. The clerk links a customer
    on the request's Decision tab (`service_request_service.link_customer`) and
    picks its class at capture step 2 (`set_customer_category`) — and until
    that day neither reached the account: the move-in wizard copied the
    applicant's name, email, phone and date of birth and NEVER the link, so a
    clerk who had linked `C-00042` opened the account on a SECOND customer
    number unless a government identifier happened to match (`BR-CUS-1024`'s
    reuse test), and a person applying for a landlord's company never matches.

    **Two rules, each only where the payload says nothing:**
      * no `customer.customer_id` and the request names a matched customer →
        that customer, by id. `BR-CUS-1024`'s identity check is satisfied by the
        id exactly as it is for the wizard's own *existing customer* pick;
      * no `account_type` and the request carries a class → that class.

    A payload that DOES say — the clerk changed their mind in the wizard — wins,
    so the request is a default and never a lock. *"Searched, no prior
    customer"* (`matched_customer` NULL) adds nothing and the door mints or
    reuses by identity exactly as it always has.
    """
    if not request_id:
        return data
    request = (
        models.ServiceRequest.objects.filter(tenant_id=_tenant_id(), pk=request_id)
        .select_related("account_type")
        .first()
    )
    if request is None:
        return data
    carried = dict(data)
    block = carried.get("customer")
    if request.matched_customer_id and (
        not isinstance(block, dict) or block.get("customer_id") in (None, "")
    ):
        carried["customer"] = {
            **(block if isinstance(block, dict) else {}),
            "customer_id": str(request.matched_customer_id),
        }
    elif not request.matched_customer_id and not isinstance(block, dict) and request.applicant_name:
        # No link and no block at all — the shape the property's master-account
        # form sends, which has a payer box and no identity fields. The
        # APPLICANT is who the request is for, so they are the party: their
        # name, their kind, and for a person the phone the application already
        # holds (`BR-CUS-1023` accepts a phone to mint a person's number). A
        # company carries no identifier here — its Tax ID is not on the request
        # (`OQ-CWP-1560`) — so `BR-CUS-1024` refuses it by name and the clerk
        # links or identifies it, which is the rule working.
        kind = "company" if request.applicant_kind in ("business", "company") else "person"
        applicant: dict[str, Any] = {"display_name": request.applicant_name, "kind": kind}
        if kind == "person" and request.applicant_phone:
            applicant["identity"] = {"phone": request.applicant_phone}
        carried["customer"] = applicant
    _carry_application_tax_id(carried, request)
    # ⊕ Lane CF-1 (2026-10-18) — *"from an approved request: every field
    # arrives filled in"* and *"DATA COLECTED IS NOT LOST"*. The two encrypted
    # identifiers and the date of birth a request holds identify the NEW
    # person customer, and its government ID and *Contact by* reach the
    # contact — each only where the payload is silent. The screen cannot send
    # an SSN or a licence it was only ever shown the last four of, so the
    # server carries them, exactly as `_carry_application_tax_id` does.
    #
    # ⚠ **ON THE MOVE-IN ONLY (`carry_people`), NOT ON A BUILD'S OWNER —
    # `DEF-CUS-10266`.** Carried onto New Connect's owner too, the owner's own
    # last four began to appear in the owner account's read, and the PO-signed
    # S9 case (`test_def_cus_9830 … [with_ssn]`) forbids any of those four
    # digits there; the signed test stands unchanged. A build's owner is
    # identified by what the clerk types on step 1 (the request's numbers show
    # there as masks), as it was before lane CF-1.
    if carry_people:
        _carry_request_identity(carried, request)
    _carry_request_contact_facts(carried, request)
    if carry_people:
        _carry_request_co_applicants(carried, request)
    # ⊕ **`DEF-CUS-9053` — THE APPLICANT'S EMAIL AND PHONE REACH THE CONTACT,
    # where the payload names none.** The property's master form sends a payer
    # NAME and nothing else, so a master account opened for a portal request
    # held no way to reach anyone — and the portal's *Set up your login* then
    # answered *"We hold no contact"* to the very customer who applied online
    # with both. Only an EMPTY field is filled: a contact the clerk typed wins.
    contact = carried.get("contact")
    if isinstance(contact, dict):
        filled = dict(contact)
        if not str(filled.get("email") or "").strip() and request.applicant_email:
            filled["email"] = request.applicant_email
        if not str(filled.get("phone") or "").strip() and request.applicant_phone:
            filled["phone"] = request.applicant_phone
        carried["contact"] = filled
    if not carried.get("account_type") and request.account_type_id:
        carried["account_type"] = request.account_type.code
    _carry_application_mailing_address(carried, request)
    return carried


def _carry_application_mailing_address(carried: dict[str, Any], request: Any) -> None:
    """`DEF-CWP-9163` — **the mailing address the applicant typed online becomes
    the new account's ONE `kind='mailing'` row**, where the payload names none.

    PO 2026-10-02: *"Mailing Address is not captured as part of the
    applicant/customer information."* It is stored once, on the portal draft,
    and read through `portal_seam.application_mailing_address` — the shape
    `_carry_application_tax_id` set. **Hard rule 8's first named exception**:
    *where the BILL goes*, which for a landlord is another building, so it is a
    `customers.addresses` row on the ACCOUNT and never a premises address; and
    it is written here, by the customers module's own account-opening door,
    never by the portal (`BR-CWP-026`: a public form may never change an
    account).

    **Only where the payload is silent**, as every other default here: a clerk
    who typed a mailing address in the wizard is obeyed.
    """
    if "addresses" in carried:
        # The clerk said something about where the bill goes — even an empty
        # list is an answer (both wizards OMIT the key when they have none).
        return
    from apps.customers import portal_seam

    address = portal_seam.application_mailing_address(request)
    if address:
        carried["addresses"] = [
            {"kind": "mailing", **{k: v for k, v in address.items() if v}}
        ]


def _carry_application_tax_id(carried: dict[str, Any], request: Any) -> None:
    """`DEF-CWP-9045` — **the Tax ID a business typed online identifies the
    NEW company customer its request opens**, where the payload names none.

    `OQ-CWP-1560` closed (b): the number is stored ONCE, on the portal draft,
    and read from there (`portal_seam.application_tax_id`). Until 2026-10-02
    nothing read it, so `BR-CUS-1024` refused every new company opened from a
    portal request through a door with no identity fields — the property's
    master form above all, which sends a payer name and nothing else.

    **Only where the payload is silent, as every other default here:** a block
    naming a `customer_id` (a link) is left alone, a block of another kind is
    left alone, and a Tax ID the clerk typed wins over the application's.
    """
    block = carried.get("customer")
    if not isinstance(block, dict) or block.get("customer_id") not in (None, ""):
        return
    if block.get("kind") != "company":
        return
    identity = block.get("identity") if isinstance(block.get("identity"), dict) else {}
    if str(identity.get("tax_id") or "").strip():
        return
    from apps.customers import portal_seam

    # Lane CF-1 (`DEF-CUS-10223`) — a staff request now keeps the Tax ID a
    # clerk typed; it wins over a portal draft's.
    number = getattr(request, "tax_id", None) or portal_seam.application_tax_id(request)
    if number:
        carried["customer"] = {**block, "identity": {**identity, "tax_id": number}}


def _carry_request_identity(carried: dict[str, Any], request: Any) -> None:
    """Lane CF-1 — a PERSON applicant's SSN, driver's licence and date of birth,
    as the request holds them, identify the NEW customer its move-in opens.

    Only for a block that names no `customer_id` (a link is the identity) and
    states the person kind, and only for an identifier the block does not
    already carry — a value the clerk typed wins. The values are read
    decrypted here, server side, and never travel to the screen (BR-CUS-092).
    """
    block = carried.get("customer")
    if not isinstance(block, dict) or block.get("customer_id") not in (None, ""):
        return
    if block.get("kind") not in (None, "person"):
        return
    identity = dict(block.get("identity") or {}) if isinstance(block.get("identity"), dict) else {}
    filled = dict(identity)
    for key, value in (
        ("ssn", request.ssn),
        ("driving_licence", request.drivers_licence),
        ("date_of_birth", request.date_of_birth.isoformat() if request.date_of_birth else None),
    ):
        if value and not str(filled.get(key) or "").strip():
            filled[key] = value
    if filled != identity:
        carried["customer"] = {**block, "identity": filled}


def _carry_request_contact_facts(carried: dict[str, Any], request: Any) -> None:
    """Lane CF-1 — the request's government ID (last four) and *Contact by*
    reach the account's contact, where the contact names none."""
    contact = carried.get("contact")
    if not isinstance(contact, dict):
        return
    filled = dict(contact)
    if not str(filled.get("gov_id_last4") or "").strip() and request.gov_id_last4:
        filled["gov_id_last4"] = request.gov_id_last4
    if not str(filled.get("contact_by") or "").strip() and request.contact_by:
        filled["contact_by"] = request.contact_by
    carried["contact"] = filled


def carry_request_co_owner_numbers(
    co_owners: Any, request_id: Any, *, customer_kind: str | None = None
) -> Any:
    """Lane CF-1 — New Connection's door to `_carry_request_co_applicants`.

    `metering.connections.create_owner_account` takes the owner block's
    `co_owners` off BEFORE the account door runs (move-in's own writer files
    them afterwards), so the carry inside `_carry_request_decisions` never sees
    them. This applies the SAME rule to that list — a card the clerk kept, by
    name, gets the request's SSN and licence where it sent none; nothing is
    added — and returns it. A list the rule cannot read is returned unchanged.
    """
    if not request_id or not isinstance(co_owners, list) or not co_owners:
        return co_owners
    request = models.ServiceRequest.objects.filter(tenant_id=_tenant_id(), pk=request_id).first()
    if request is None:
        return co_owners
    carried: dict[str, Any] = {"co_owners": list(co_owners)}
    if customer_kind:
        carried["customer"] = {"kind": customer_kind}
    _carry_request_co_applicants(carried, request)
    return carried["co_owners"]


def _carry_request_co_applicants(carried: dict[str, Any], request: Any) -> None:
    """Lane CF-1 — the request's co-applicant cards reach the move-in's
    co-owners WHOLE.

    The move-in screen opens with the request's cards filled in (name,
    relationship, phone, email, date of birth, responsible for bills) and
    sends what the clerk kept — but it was only ever shown the SSN and the
    licence as a last four, so it cannot send them. Here, a card the clerk
    kept (same name) gets those two from the request, where the card sent
    none. **Nothing is added that the clerk did not keep**: a card removed on
    screen, or *Has co-owners* unticked, is an answer and is obeyed. A
    COMPANY holder's people are owners and officers, so nothing is carried
    onto one.
    """
    from apps.customers import service_request_service

    block = carried.get("customer")
    if isinstance(block, dict) and block.get("kind") == "company":
        return
    rows = carried.get("co_owners")
    if not isinstance(rows, list) or not rows:
        return
    cards = service_request_service.co_applicant_rows(request, decrypt=True)
    if not cards:
        return
    by_name = {str(card["full_name"]).strip().lower(): card for card in cards}
    merged = []
    for row in rows:
        if isinstance(row, dict):
            card = by_name.get(str(row.get("full_name") or "").strip().lower())
            if card is not None:
                row = dict(row)
                for key in ("ssn", "driving_licence"):
                    if not str(row.get(key) or "").strip() and card.get(key):
                        row[key] = card[key]
        merged.append(row)
    carried["co_owners"] = merged


def _move_in(actor: Any, payload: Any, resolve: Any) -> dict[str, Any]:
    """The one move-in body both doors run. `resolve()` answers
    `(unit_id, outgoing account or None)` and is called AFTER the payload has
    been validated, which is the order `move_in` always had: a refused field is
    named before a missing account is looked for."""
    data = dict(_payload_dict(payload or {}))  # copied — the pop below must not mutate the caller's
    _reject_unknown(data, MOVE_IN_FIELDS)
    if "status" not in data:
        data = {**data, "status": _default_active_status().code}
    # CR-038 W9 task 3 — the wizard's captured opening reads. POPPED so the
    # account write below never sees a reads key; they travel ONLY through the
    # metering event door (BR-CUS-021's own clause), AFTER the account exists.
    initial_reads_payload = data.pop("initial_reads", None)
    # CR-070 wave P — the turn-on the clerk elected on step 3, *Start date &
    # reads*. POPPED for `initial_reads`' reason: the account write below must
    # never see a key that is not an account column.
    field_visit = _field_visit(data.pop("field_visit", None))
    # CR-122-BRC06 — the draft the clerk keyed this into. POPPED for
    # `initial_reads`' reason; resolved below, inside the transaction.
    wizard_park_id = data.pop("wizard_park_id", None)
    # CR-094-BRC01 wave H — the deposit the clerk took on step 5. POPPED for
    # `initial_reads`' reason and VALIDATED here, before the transaction opens:
    # a refused figure writes nothing and the clerk keeps every other field.
    # ⚠ **NO BLOCK IS *No*, SPELLED OUT (`OQ-CUS-12620` (a), 2026-09-23).** A
    # move-in is a door that asks the deposit question, so a request that
    # leaves the block off meets the plan's check exactly as a clerk's *No*
    # does — it cannot skip a deposit the plan asks for by saying nothing.
    deposit_instruction = deposit.clean(data.pop("deposit", None)) or deposit.NO_ANSWER
    # CR-171-BRC10 P1.12 / P1.13 — the Fees table and the money taken for it.
    # POPPED and VALIDATED here, before the transaction opens, for the deposit's
    # reason: a refused row writes nothing and the clerk keeps every field. The
    # PRICES are checked inside, once the account names its category.
    fee_rows = move_fees.clean_fees(data.pop("fees", None))
    payment_instruction = move_fees.clean_payment(data.pop("payment", None))
    move_fees.refuse_deposit_taken_twice(payment_instruction, deposit_instruction)
    # CR-171-BRC10 P1.15 — POPPED for the same reason. With a certificate the
    # account's three BLANKET exemption columns are dropped from the write
    # (DEF-CUS-9724, PO 2026-10-05: an exemption removes only its own tax).
    billing_extras = move_in_preferences.clean(data)
    data = move_in_preferences.merge_account_values(data, billing_extras)
    # CR-094-BRC01 — the application this move-in fulfils. POPPED for
    # `initial_reads`' reason: `accounts` has no such column and the fact
    # belongs on the move RECORD (`BR-CUS-080`).
    move_request_id = data.pop("service_request_id", None)
    # `DEF-CUS-9035` — what the clerk already decided ON THE REQUEST: the
    # customer they linked and the class they picked. Applied only where this
    # payload is silent on each, so a clerk who changes either in the wizard
    # is obeyed. See `_carry_request_decisions`.
    data = _carry_request_decisions(data, move_request_id, carry_people=True)
    # `BR-CUS-1101` — which of the unit's services this account takes (PO
    # ruling 2026-09-25). POPPED for `initial_reads`' reason: `accounts` has no
    # such column and never will, because the subset IS the agreement rows.
    # VALIDATED below rather than here: the offer is the UNIT's, and the unit is
    # not known until `resolve()` has run.
    services_choice_raw = data.pop("services", None)
    # CR-171-BRC10 P1.10/P1.11 (lane MVI-IDN) — co-owners, company facts, PO and
    # bill routing. POPPED and VALIDATED here, before the transaction.
    from apps.customers import move_in_people

    people_block = move_in_people.pop(data)
    # CR-171-BRC10 P1.20 (lane MVI-FLOW) — the extra messages, validated here.
    from apps.customers import move_in_complete

    extra_rows = move_in_complete.pop(data)
    # CR-190-BRC10 — the two defaults, untick or re-channel, validated here.
    default_choices = move_in_complete.pop_defaults(data)
    # CR-181-BRC10 (lane REOPEN) — *Reopen AC-…* and the balance choice.
    # POPPED for `initial_reads`' reason; checked below once the unit is known.
    from apps.customers import move_in_reopen

    reopen_request = move_in_reopen.pop(data)
    unit_id, outgoing = resolve()
    # DEF-CUS-10190 (PO ruling 2026-10-17) — a unit SHOWN but not selectable
    # (a move-out in progress, an account pending activation, a removed unit)
    # is refused here, before anything is written. An occupied unit is still
    # BR-CUS-017's refusal inside `_make_occupying`.
    from apps.customers import move_in_units

    move_in_units.refuse_if_blocked(unit_id)
    # Every reopen guard BEFORE the transaction: same unit, this customer's
    # account, closed within the tenant's years, unit empty, and — under *pay
    # first* — nothing still owed. A refusal writes nothing.
    reopen_plan = move_in_reopen.check(
        reopen_request,
        unit_id=unit_id,
        customer_block=data.get("customer"),
        opened_at=data.get("opened_at"),
    )
    # Before the transaction opens, like the deposit above: a refused service
    # writes nothing and the clerk keeps every other field.
    chosen_services = _clean_service_choice(unit_id, services_choice_raw)
    # `DEF-WRK-9784` — a visit row's meter and template, checked against the
    # unit now: a template of another service is refused by name here rather
    # than completing the move-in with no work order and a warning.
    seams.check_flow_order_rows_on_unit(field_visit["orders"], unit_id)
    # `initial_reads_not_committed` rides ONLY a move-in that really commits
    # none — with a capture below the old warning would be false.
    warnings: list[dict[str, Any]] = [
        dict(entry)
        for entry in MOVE_IN_UNAVAILABLE
        if not (
            entry["code"] == "initial_reads_not_committed" and initial_reads_payload is not None
        )
    ]

    # ONE transactional commit (BR-SHL-019): a refused reading — BR-MET-129
    # errors refuse with named rows — rolls the new account back too, so the
    # clerk fixes the value with everything still on screen and commits ONCE.
    with transaction.atomic():
        result = _open_account(
            actor,
            data,
            audit_action="account.moved_in",
            allowed=MOVE_IN_FIELDS,
            unit_id=unit_id,
            require_occupying=True,
            warnings=warnings,
            # `BR-CUS-1024` — S19 is a counter door. PO 2026-09-01 on move-in:
            # *"You either create new Customer ID or you link existing customer
            # ID here"*, under the same no-identifier-no-account ruling.
            require_identity=True,
            # CR-094-BRC01 wave H — S19 step 5. The SAME capability S18 step 4
            # calls, by the same keyword: PO 2026-09-12, *"It is one concept"*.
            deposit_instruction=deposit_instruction,
            # `BR-CUS-1101` — the clerk's ticks, already checked against the
            # unit's points. `None` is every point (the default this door had).
            chosen_services=chosen_services,
            # CR-181-BRC10 — the returning customer's own account, reopened.
            reopen=reopen_plan,
        )
        # ── the stale absence, dropped the moment it stops being true ───────
        # `DEF-CUS-5912`. `MOVE_IN_UNAVAILABLE` is built BEFORE the commit, so
        # `customer_not_linked` rode every move-in including the ones that
        # recognised a returning customer and linked them to `C-00001`. The
        # outcome is only knowable HERE, which is why the filter is here and
        # not beside the tuple.
        #
        # ⚠ **THE LESSON IS THE ONE `DEF-CUS-5912` NAMES: a warning list
        # filtered for ONE member reads as conditional and is not.**
        # `initial_reads_not_committed` was filtered above and made the whole
        # tuple look like it was being checked; the other two passed straight
        # through. Nothing asserted the ABSENCE of a warning, only the presence
        # of the ones expected, so no test could see it.
        if result.get("customer_outcome") in (OUTCOME_LINKED, OUTCOME_CREATED):
            warnings[:] = [w for w in warnings if w.get("code") != "customer_not_linked"]
        # `DEF-CUS-9702` (CR-171 P1.21, lane MVI-FLOW) — one more that is false
        # here: `plan_snapshot_not_recorded` (the plan lives on the unit). The
        # carry-forward absence STAYS — it is true — and only its sentence was
        # corrected (see `MOVE_IN_UNAVAILABLE`).
        move_in_complete.drop_stale_absences(
            warnings, customer_outcome=result.get("customer_outcome")
        )
        if initial_reads_payload is not None:
            # Opening reads, dated the new occupant's own start by default
            # (BR-CUS-056: the incoming account starts *"the next day from the
            # same reading"* — the wizard passes per-row dates where they
            # differ). Committed AFTER `_open_account` so the unit is already
            # occupied and the vacant-unit warning does not fire on the very
            # move-in that ends the vacancy.
            opened = data.get("opened_at")
            result["event_reads"] = _commit_event_reads(
                actor,
                event="move_in",
                reads=initial_reads_payload,
                default_read_at=date.fromisoformat(str(opened)) if opened else None,
                # DEF-CUS-10165 — step 1's per-meter read date, bounded.
                bounded_dates=True,
                context={
                    "account_id": result["id"],
                    "account_no": result.get("account_no"),
                    "unit_id": str(unit_id),
                    "flow": "move_in",
                },
            )
        # ── CR-039 wave D tasks 17–19: THE MOVE-IN LEAVES A RECORD ──────────
        # PO ruling 2026-08-27: *"you cna keep them as records for audit
        # perpuses"*. Same posture as `move_out` above — the JOB, not its
        # effects — with one column this flow can fill and that one cannot:
        #
        # ⚠ **`from_account` IS THE LINK THIS FUNCTION HAS BEEN RETURNING AND
        # STORING NOWHERE.** The two lines below this block put
        # `moved_in_after_account_id` in the RESPONSE, and nothing has ever
        # written it down: reopen the page tomorrow and the chain from the
        # outgoing tenancy to the incoming one is gone. That is exactly the
        # class of fact BR-CUS-151 says this record is for.
        #
        # ⚠ **INSIDE `_open_account`'s TRANSACTION AND AFTER THE READS.** A
        # refused reading rolls the new account back (BR-SHL-019), and it must
        # roll this back with it — a record of a move-in whose account does not
        # exist would be worse than no record at all. The FK would refuse it
        # anyway; the ordering is what makes that never come up.
        # ⚠ **`opened_at` CANNOT BE NULL HERE, AND IT IS NOT AN ASSUMPTION.**
        # `move_in` passes `require_occupying=True`, and `_make_occupying`
        # REFUSES an occupying account with no start date by name
        # (`BR-CUS-022` / `customers.account.start_date_required`) before this
        # line is reached. It is read back off the WRITTEN account rather than
        # off the payload, so the record states the date the account actually
        # holds and the number's `{YY}` matches the tenancy's own start.
        opened_at_raw = result["opened_at"]
        # CR-122-BRC06 — the draft's number becomes the record's number, and
        # the draft stops existing. Both inside this transaction, so a refused
        # reading rolls BOTH back: a clerk whose commit failed still has their
        # draft, with the same reference, exactly where they left it.
        draft_reference = _adopt_wizard_draft(actor, wizard_park_id, flow=moves.KIND_MOVE_IN)
        move_record = moves.record_move(
            kind=moves.KIND_MOVE_IN,
            account_id=result["id"],
            effective_on=date.fromisoformat(str(opened_at_raw)),
            actor=actor,
            # `DEF-CUS-6353` — NULL for a first occupant: nobody left.
            from_account_id=outgoing.id if outgoing is not None else None,
            reads_committed=_reads_committed(result.get("event_reads")),
            # BR-TEN-057 — the tag rides the owning row. A first occupant has
            # no outgoing row to inherit one from, and the account this door
            # has just opened is never a sample row.
            is_sample=bool(outgoing.is_sample) if outgoing is not None else False,
            service_request_id=move_request_id,
            # CR-122-BRC06 — see `_adopt_wizard_draft`.
            reserved_move_no=draft_reference,
        )
        if reopen_plan is not None:
            # CR-181-BRC10 — the reopen and the clerk's balance choice, on the
            # move-in, inside its transaction (audited by `record`).
            result["reopened"] = move_in_reopen.record(
                actor, reopen_plan, move_record_id=move_record["move_record_id"]
            )
        _record_request_customer(actor, move_request_id, result["id"])
        # `DEF-CUS-9211` — the request's own fields reach the account it opened.
        _carry_request_custom_answers(actor, move_request_id, result["id"])
        # CR-171-BRC10 P1.10/P1.11/P1.26 (lane MVI-IDN) — inside the commit.
        result["people"] = move_in_people.write_at_complete(
            actor,
            account_id=result["id"],
            block=people_block,
            service_request_id=move_request_id,
        )
        # CR-171-BRC10 P1.20 (lane MVI-FLOW) — the Messaging table's added rows,
        # inside the commit and after the co-owners a row may name.
        extra_written = move_in_complete.write(
            move_record_id=move_record["move_record_id"],
            account_id=result["id"],
            rows=extra_rows,
        )
        result.update(move_record)
        # ── CR-171-BRC10 P1.12 / P1.13 · THE FEES AND THE MONEY 🔒 ───────────
        # Inside this transaction and after the record exists, because the
        # lines hang off it: a refused fee or payment rolls back the account,
        # the reads and the record with it (BR-SHL-019). `None` from each when
        # the wizard sent no block — the old wizard's move-in is unchanged.
        if fee_rows is not None or payment_instruction is not None or not billing_extras.empty:
            opened = models.Account.objects.select_related("account_type").get(pk=result["id"])
            # DEF-CUS-9780 — the move-in's *Assistance evidence*, already filed
            # on the account above (`write_at_complete`), rides to the claims.
            from apps.customers import move_in_documents

            extras_answer = move_in_preferences.apply(
                actor,
                opened,
                billing_extras,
                on_day=date.fromisoformat(str(result["opened_at"])) if result.get("opened_at") else None,
                evidence_cards=(
                    move_in_documents.evidence_cards(
                        account=opened,
                        rows=people_block.documents,
                        service_request_id=move_request_id,
                    )
                    if billing_extras.discount_claims
                    else None
                ),
            )
            if extras_answer is not None:
                result["billing_extras"] = extras_answer
            fee_answer = move_fees.record(
                actor,
                move_record_id=move_record["move_record_id"],
                account=opened,
                fees=fee_rows,
                deposit_result=result.get("deposit"),
                services=chosen_services,
                is_sample=bool(outgoing.is_sample) if outgoing is not None else False,
            )
            if fee_answer is not None:
                result["fees"] = fee_answer
            paid = move_fees.take_payment(
                actor,
                account=opened,
                instruction=payment_instruction,
                fees=fee_answer,
                deposit_result=result.get("deposit"),
                warnings=result.setdefault("warnings", []),
            )
            if paid is not None:
                result["payment"] = paid
        # ⚖️ `DEF-RAT-9833` (PO ruling 4, 2026-10-06, reading (b)) — Autopay or
        # Paperless set ON at move-in puts the matching discount in place for
        # the first bill now, not tonight. Idempotent beside a claim of the same
        # discount above (the claim's enrolment is already open).
        _opened_flags = (
            models.Account.objects.filter(pk=result["id"]).values("autopay", "paperless").first() or {}
        )
        if _opened_flags.get("autopay") or _opened_flags.get("paperless"):
            from apps.customers import discounts as customer_discounts

            customer_discounts.settings_switched_on(actor, result["id"], source="move_in")
        # ── CR-048 wave B task B10: THE NEW OCCUPANT IS WELCOMED ─────────────
        # *"A customer moving in is told NOTHING."* — the teardown's own
        # sentence, and this is the line that stops it being true.
        # Keyed on the MOVE RECORD (rule 6), inside this transaction so a
        # refused reading rolls it back too, and inside the seam's own SAVEPOINT
        # so a queue failure cannot take the new account with it on PostgreSQL
        # (hard-won law 14). `opened_at` is read back off the WRITTEN account,
        # exactly as the record's own `effective_on` is.
        # ⊕ CR-190-BRC10 — Step 4 may untick a default or pick another of its
        # allowed channels for THIS move-in (PO 2026-10-22, *"allow untick and
        # channel change per move-in"*). An untick queues nothing at all and is
        # AUDITED; the outcome row says so, so the completed screen can too.
        welcome_send, welcome_channels = move_in_complete.default_outcome(
            "move_in_welcome", default_choices.get("move_in_welcome")
        )
        agreement_send, agreement_channels = move_in_complete.default_outcome(
            "service_agreement", default_choices.get("service_agreement")
        )
        move_in_complete.audit_default_choices(
            actor,
            account_id=result["id"],
            move_record_id=move_record["move_record_id"],
            choices=default_choices,
        )
        result["move_message"] = (
            [
                dict(row)
                for row in notifications_seam.queue_move_in_welcome(
                    move_record_id=move_record["move_record_id"],
                    account_id=result["id"],
                    effective_on=date.fromisoformat(str(opened_at_raw)),
                    channels=welcome_channels,
                    actor=actor,
                )
            ]
            if welcome_send
            else [{"code": move_in_complete.UNTICKED, "br_ref": "CR-190-BRC10"}]
        )
        # `DEF-CUS-9743` — CR-171 P1.20's SECOND default, the service
        # agreement: listed on Review as always sent and, until this, queued by
        # nothing. Same savepoint discipline, its own outcome key so the
        # welcome's rows keep their meaning for every older reader.
        result["service_agreement_message"] = (
            [
                dict(row)
                for row in notifications_seam.queue_move_in_service_agreement(
                    move_record_id=move_record["move_record_id"],
                    account_id=result["id"],
                    effective_on=date.fromisoformat(str(opened_at_raw)),
                    channels=agreement_channels,
                    actor=actor,
                )
            ]
            if agreement_send
            else [{"code": move_in_complete.UNTICKED, "br_ref": "CR-190-BRC10"}]
        )
    # Named in the response because the chain is the thing the caller asked for:
    # this is S20's "Complete & start move-in →" landing on its new account.
    # `DEF-CUS-6353` — both None for a first occupant, which is the answer and
    # not an absence: there was no tenancy before this one.
    result["moved_in_after_account_id"] = str(outgoing.id) if outgoing is not None else None
    # DEF-CUS-10190 — the tenancy this follows ended at a CUT: the new occupant
    # needs the service back on. AFTER the commit (`BR-WRK-055`): a job that
    # cannot be raised never undoes the move-in, and is reported.
    result["reconnect"] = move_in_units.reconnect_after_cut(
        actor,
        new_account_id=result["id"],
        outgoing=outgoing,
        opened_at=date.fromisoformat(str(result["opened_at"])),
    )
    result["moved_in_after_account_no"] = outgoing.account_no if outgoing is not None else None
    # ── CR-070 wave P · the turn-on somebody has to go and do ──────────────
    #
    # AFTER the commit, for `move_out`'s reason and `BR-WRK-055`'s: the new
    # occupant has an account, a plan and their opening reads whether or not a
    # crew could be booked, and a field module that could refuse a move-in would
    # leave a household with no supply and no record of why.
    visit = _raise_flow_work(
        actor,
        flow_kind="move_in",
        flow_id=result["move_record_id"],
        template_ids=field_visit["template_ids"],
        orders=field_visit["orders"],
    )
    result["work_orders"] = visit["work_orders"]
    # `DEF-CUS-6363` — *No visit needed* is an ANSWER and it is kept: the
    # clerk said nobody has to attend, which is a different fact from a clerk
    # who was never asked. Named on the response, beside the orders.
    result["field_visit_declined"] = field_visit["none"]
    if visit["warnings"]:
        result["warnings"] = [*result.get("warnings", []), *visit["warnings"]]
    # CR-171-BRC10 P1.20 / P1.21 (lane MVI-FLOW) — AFTER the commit, like the
    # visit: the extra messages are queued (or say why not), then image 48's
    # *What happened* is composed from everything this response reports.
    result["extra_messages"] = move_in_complete.queue(
        actor,
        account_id=result["id"],
        on_date=date.fromisoformat(str(result["opened_at"])),
        written=extra_written,
    )
    result["request_no"] = _request_no(move_request_id)
    result["what_happened"] = move_in_complete.what_happened(result)
    return result


def _request_no(request_id: Any) -> str | None:
    """The `SR-` number the move-in came from, for image 48's *From request*."""
    if not request_id:
        return None
    return (
        models.ServiceRequest.objects.filter(tenant_id=_tenant_id(), pk=request_id)
        .values_list("request_no", flat=True)
        .first()
    )


# ══════════════════════════════════════════════════════════════════════════
# US-CUS-019 — the S68 brownfield account import (slice 4)
#
# HUMAN-OWNED (idempotency keys 🔒). HUMAN-REVIEW-PENDING — AI-authored
# 2026-08-11 under the PO ruling of 2026-08-09. Row in
# 12-governance/09-human-review-ledger.md.
#
# BR-CUS-051 is the whole design brief and it is one sentence: *"import
# mechanics = the standard"*. So this is deliberately the S52/S28 shape —
# stage (writing nothing) → per-row errors with reasons → skip-errors ON →
# "N created · N failed" ALWAYS → 10,000-row cap — and the only thing new is
# what an ACCOUNT row means that an asset row does not:
#
#   · it can OCCUPY a unit, so every created row goes through `_open_account`
#     and takes BR-CUS-017's advisory lock (see the docstring there);
#   · it belongs to a CUSTOMER (BR-CUS-054), so rows sharing a `customer_ref`
#     converge on ONE `customers` row and N `customer_accounts` links;
#   · it is MONEY-BEARING, so there is no re-upload "spec update" path the way
#     BR-AST-034 gives assets one — a row whose account # already exists is a
#     ROW ERROR, and post-cutover corrections go through the normal flows (J6).
# ══════════════════════════════════════════════════════════════════════════

#: Payload vocabulary of `POST /accounts/imports`. Narrow on purpose: an
#: import option a caller believes they set and that nothing reads is the
#: BR-CUS-051 "silent partial" in a different costume.
IMPORT_FIELDS: frozenset[str] = frozenset({"content", "filename", "cutover_date", "skip_errors"})

#: BR-CUS-046 template columns whose DB target belongs to ANOTHER story. They
#: are parsed, validated and STAGED — never silently dropped, never faked —
#: and the commit reports how many rows carried each. The assets importer set
#: this precedent with its `opening_read` column (deferred to the W2 reads
#: lane, logged per row, reported).
DEFERRED_COLUMNS: dict[str, tuple[str, str]] = {
    "deposit_amount": ("US-CUS-023", "BR-CUS-050"),
    "deposit_received_on": ("US-CUS-023", "BR-CUS-050"),
    "ob_current": ("US-CUS-021", "BR-CUS-048"),
    "ob_31_60": ("US-CUS-021", "BR-CUS-048"),
    "ob_61_90": ("US-CUS-021", "BR-CUS-048"),
    "ob_90_plus": ("US-CUS-021", "BR-CUS-048"),
}


# ═══════════════════════════════════════════════════════════════════════════
# CR-058 W7 · BR-CUS-1043 · DEF-2592 — THIS DOOR IS CLOSED
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **THERE ARE TWO ACCOUNTS-IMPORT DOORS AND THIS IS THE ONE WITH NO SCREEN.**
# `DEF-611` replaced the three-step wizard with the five-stage ETL runner
# (`CR-030` W1) and deleted the screen; **these endpoints stayed mounted and
# working**, and nothing in the frontend has called them since. A script or an
# integration pointed at them still worked this morning.
#
# ⚠ **AND IT SERVED RULES THE PO HAS SINCE REVERSED, WHICH IS WHY IT COULD NOT
# BE LEFT.** Two of them, both measurable:
#   1. **It allocates an account number for a blank cell.** PO 2026-08-27,
#      verbatim: *"we use utility provdied account number here - we dont create
#      our own number - since it will create lot of change management for
#      utility ; if row dont have account number reject it"*. The live runner
#      rejects the row; this door numbered it from the series.
#   2. **It requires no customer name**, and after `BR-CUS-1041` it would have
#      been the ONE door in the product that creates accounts with no identity
#      at all — so the ruling would govern the counter and the live migration
#      and not the door a script uses.
#
# ⚠ **REFUSED, NOT DELETED, AND THE DIFFERENCE IS FOR THE CALLER.** A 404 tells
# an integration nothing about what happened or where to go; this answers with a
# sentence naming the live import. `GET /accounts/imports/{id}` is deliberately
# untouched — reading a batch somebody staged last week is not a write, and the
# rows are real.
#
# ⚠ **THE ROLLBACK IS THIS FUNCTION.** `_refuse_retired_account_import()` is one
# call at the top of each of the two write doors; removing them restores the old
# behaviour exactly, and this change migrates, drops and rewrites no data.
def _refuse_retired_account_import() -> None:
    # ⚠ **THE REASON LIVES HERE BECAUSE IT NO LONGER FITS IN THE SENTENCE.**
    # The clerk-facing copy read *"…Accounts › Imports, which checks every row
    # before it writes any of them"* until 2026-09-03. B14 rule 33 caps a refusal
    # sentence at six words (PO ruling 2026-08-30), so the trailing clause — the
    # RATIONALE — was dropped and the INSTRUCTION kept, which is the order G33
    # prints on every failure. Do not put it back: **the new door validates the
    # whole batch before it writes a single row, and this one did not.** That is
    # why the old door is refused rather than left working, and it is the answer
    # to "why can't I use the old upload" if anyone asks.
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-CUS-1043",
        message_key="customers.import.retired_use_import_runs",
    )


def refuse_retired_account_import() -> None:
    """The same refusal, reachable from the API layer.

    ⚠ **A NAMED FUNCTION RATHER THAN THE PRIVATE ONE**, because the template
    view is not a service call and reaching for `services._refuse_…` from
    `api.py` would be the module's own guard being used around itself. One
    sentence, one `br_ref`, one door.
    """
    _refuse_retired_account_import()


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def stage_account_import(actor: Any, payload: Any) -> dict[str, Any]:
    """`POST /accounts/imports` (11b §S68) — parse the published template into
    `account_import_batches` / `account_import_rows` and validate EVERY row.

    BR-CUS-051: NOTHING touches `accounts`, `contacts`, `addresses` or
    `customers` until an explicit commit. A staged batch that is never
    committed stays as evidence of what someone tried to load.

    ⛔ **CLOSED 2026-09-01 — `BR-CUS-1043` / `DEF-2592`.** See the block above
    this function. The body below is kept and unreachable ON PURPOSE: it is what
    the door did, it is the rollback, and deleting it would make the reversal
    unreviewable.
    """
    _refuse_retired_account_import()
    from apps.customers import selectors

    data = _payload_dict(payload)
    _reject_unknown(data, IMPORT_FIELDS)
    content = data.get("content")
    if content in (None, ""):
        _refuse_fields(
            [_field_error("content", errors.VAL_REQUIRED, "customers.import.file_required")]
        )
    fe: list[dict[str, Any]] = []
    cutover_date = (
        _date(data.get("cutover_date"), "cutover_date", fe) if data.get("cutover_date") else None
    )
    _refuse_fields(fe)

    parsed = _parse_import_file(str(content))
    ensure_account_statuses()

    with transaction.atomic():
        batch = models.AccountImportBatch.objects.create(
            tenant_id=_tenant_id(),
            filename=_text(data.get("filename"), 260) or "accounts.csv",
            uploaded_by_id=getattr(actor, "id", None),
            cutover_date=cutover_date,
            # 🔒 CLAUDE.md rule 6 / DB-12 — computed SERVER-SIDE, both halves.
            file_hash=parsed.file_hash,
            tag_fingerprint=account_import.tag_fingerprint(cutover_date=cutover_date),
            row_count=len(parsed.rows),
            skip_errors=_bool(data.get("skip_errors", True)),  # BR-CUS-051: ON
        )
        claimed_numbers: set[str] = set()
        claimed_units: set[str] = set()
        valid = 0
        for parsed_row in parsed.rows:
            resolved, row_errors = _validate_import_row(parsed_row, claimed_numbers, claimed_units)
            if not row_errors:
                valid += 1
            models.AccountImportRow.objects.create(
                tenant_id=batch.tenant_id,
                batch=batch,
                row_no=parsed_row.row_no,
                raw={"source": parsed_row.raw, "resolved": resolved},
                errors=row_errors or None,
            )
        batch.valid_count = valid
        batch.save(update_fields=["valid_count"])
        _audit(
            actor,
            "account.import_staged",
            batch.id,
            entity_type="account_import_batch",
            after={"file": batch.filename, "rows": batch.row_count, "valid": valid},
        )
    return selectors.account_import_batch(batch.id)


def _parse_import_file(content: str) -> Any:
    """`account_import.parse` refusals → the BE-02 catalog exceptions
    BR-CUS-051 requires. The row cap is BIZ-CAP and is refused AT UPLOAD, so
    nothing is staged for an 11,600-row file (US-CUS-019 TC-6)."""
    try:
        return account_import.parse(content)
    except ValueError as exc:
        reason = str(exc)
        if reason == account_import.ERR_ROW_CAP:
            raise errors.BizError(
                errors.BIZ_CAP,
                br_ref="BR-CUS-051",
                message_key="customers.import.row_cap_exceeded",
                params={"max_rows": account_import.ROW_CAP},
            ) from exc
        if reason == account_import.ERR_TOO_LARGE:
            raise errors.BizError(
                errors.BIZ_CAP,
                br_ref="BR-CUS-051",
                message_key="customers.import.file_too_large",
                params={"max_bytes": account_import.BYTE_CAP},
            ) from exc
        if reason.startswith(account_import.ERR_UNMAPPED_COLUMN):
            _, _, missing = reason.partition(":")
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="customers.import.required_column_missing",
                params={"columns": missing.split(",")},
            ) from exc
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="customers.import.header_required"
        ) from exc


def _validate_import_row(
    parsed_row: Any, claimed_numbers: set[str], claimed_units: set[str]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Per-row, independent validation against THIS tenant's data.

    Every resolution here is tenant-scoped by construction — the querysets run
    under `app.tenant_id` and the unit reference goes through metering's own
    selector (B1), so US-CUS-019 TC-8's cross-tenant file finds nothing rather
    than finding the other tenant's rows.
    """
    values = dict(parsed_row.values)
    row_errors: list[dict[str, Any]] = list(parsed_row.errors)
    resolved: dict[str, Any] = {}

    def fail(column: str, code: str, **params: Any) -> None:
        row_errors.append({"column": column, "code": code, **params})

    # ── the unit (BR-CUS-047 — it must ALREADY exist) ───────────────────────
    unit_ref = values.get("unit_ref")
    unit_id = seams.unit_id_for_reference(unit_ref) if unit_ref else None
    if unit_ref and unit_id is None:
        fail("unit_ref", "unit_not_found", value=unit_ref, br_ref="BR-CUS-047")
    resolved["unit_id"] = unit_id

    # ── the account # (BR-CUS-051 derivation — money-bearing, so no update) ─
    account_no = values.get("account_no")
    if account_no:
        key = account_no.strip().lower()
        if key in claimed_numbers:
            fail("account_no", "account_no_duplicate_in_file", value=account_no)
        elif (
            models.Account.objects.filter(tenant_id=_tenant_id(), account_no__iexact=account_no)
            .only("id")
            .exists()
        ):
            fail("account_no", "account_no_exists", value=account_no, br_ref="BR-CUS-051")
        else:
            claimed_numbers.add(key)
            resolved["account_no"] = account_no
    # blank → BR-TEN-035 allocation at commit; the allocation is REPORTED.

    # ── category / sub-type / status (BR-CUS-052: unmapped values ERROR) ────
    category = values.get("category")
    if not category:
        fail("category", "category_required", br_ref="BR-CUS-046")
    else:
        # Tenant-scoped since the PO ruling of 2026-09-17 — an import maps a
        # legacy value onto THIS utility's vocabulary and no other's.
        type_qs = models.AccountType.objects.filter(tenant_id=_tenant_id(), active=True)
        row = type_qs.filter(code__iexact=category).first()
        if row is None:
            row = type_qs.filter(name__iexact=category).first()
        if row is None:
            # BR-CUS-052: an unmapped legacy value holds its row in error. The
            # step that WOULD map it is US-CUS-020, named here so the operator
            # learns what is missing rather than what is broken.
            fail("category", "unmapped_value", value=category, story_ref="US-CUS-020")
        else:
            resolved["account_type"] = row.code

    subtype = values.get("subtype")
    if subtype:
        row = models.AccountSubtype.objects.filter(
            tenant_id=_tenant_id(), active=True, code__iexact=subtype
        ).first()
        if row is None:
            fail("subtype", "unmapped_value", value=subtype, story_ref="US-CUS-020")
        else:
            resolved["account_subtype"] = row.code

    status_code = values.get("status")
    status_row = None
    if not status_code:
        fail("status", "status_required", br_ref="BR-CUS-055")
    else:
        status_row = models.AccountStatus.objects.filter(
            tenant_id=_tenant_id(), active=True, code__iexact=status_code
        ).first()
        if status_row is None:
            status_row = models.AccountStatus.objects.filter(
                tenant_id=_tenant_id(), active=True, name__iexact=status_code
            ).first()
        if status_row is None:
            fail("status", "unmapped_value", value=status_code, story_ref="US-CUS-020")
        else:
            resolved["status"] = status_row.code

    # ── plan override: the column is SIGNED, its target was SUPERSEDED ──────
    if values.get("plan_override"):
        # BR-CUS-046/AC-1 puts a plan-override column in the template; on
        # 2026-08-11 the PO superseded BR-CUS-029, so there is no account-side
        # plan record to write and the only remaining home is metering's
        # `units.rate_plan_id` — a CROSS-MODULE WRITE (B1/DB-16), forbidden.
        # Refused loudly rather than ignored: silently putting the account on
        # the unit's plan would bill it at a price nobody chose.
        fail(
            "plan_override",
            "plan_override_has_no_target",
            value=values.get("plan_override"),
            oq_ref="OQ-166",
        )

    # ── the customer (BR-CUS-054) ───────────────────────────────────────────
    customer_ref = values.get("customer_ref")
    customer_name = values.get("customer_name")
    if customer_ref:
        existing = models.Customer.objects.filter(
            tenant_id=_tenant_id(), external_ref__iexact=customer_ref
        ).first()
        if existing is None and not customer_name:
            fail("customer_name", "customer_name_required", br_ref="BR-CUS-054")
        resolved["customer_ref"] = customer_ref
    if customer_name:
        resolved["customer_name"] = customer_name
    if values.get("customer_kind"):
        resolved["customer_kind"] = values["customer_kind"]

    # ── occupancy: the same two rules the S18 wizard takes ──────────────────
    occupying = status_row is not None and is_occupying(status_row)
    if occupying and values.get("since") is None:
        # BR-CUS-022: billing starts at the service start date, so an occupying
        # account without one could never be billed.
        fail("since", "since_required", br_ref="BR-CUS-022")
    resolved["occupying"] = occupying

    # ── plain attributes ────────────────────────────────────────────────────
    for target in ("tax_exempt", "autopay"):
        if values.get(target) is not None:
            resolved[target] = bool(values[target])
    if values.get("since") is not None:
        resolved["opened_at"] = values["since"].isoformat()
    for target in ("email", "phone", "mailing_address"):
        if values.get(target):
            resolved[target] = values[target]

    # ── BR-CUS-017, in-file — LAST, and only for a row that will be committed ─
    # Two rows cannot both be the live occupant of one unit. This runs after
    # every other check and only when the row is otherwise clean, because a row
    # that is going to FAIL reserves nothing: if row 412 errors on its account
    # number, the unit it named is still free for row 900. Getting that order
    # wrong turns one bad cell into a cascade of unrelated refusals.
    #
    # The service guard (`_make_occupying`, under the advisory lock) is the
    # enforcement; catching it at STAGE is what makes the preview honest.
    if occupying and unit_id is not None and not row_errors:
        if str(unit_id) in claimed_units:
            fail("unit_ref", "unit_already_claimed_in_file", value=unit_ref, br_ref="BR-CUS-017")
        elif _occupying_account_exists(unit_id):
            fail("unit_ref", "unit_occupied", value=unit_ref, br_ref="BR-CUS-017")
        else:
            claimed_units.add(str(unit_id))

    # ── carried, not written (each names the story that owns it) ────────────
    deferred: dict[str, Any] = {}
    for column in DEFERRED_COLUMNS:
        value = values.get(column)
        if value not in (None, ""):
            deferred[column] = value.isoformat() if hasattr(value, "isoformat") else value
    if deferred:
        resolved["deferred"] = deferred
    return resolved, row_errors


def _occupying_account_exists(unit_id: Any) -> bool:
    return (
        models.Account.objects.filter(
            tenant_id=_tenant_id(),
            unit_id=unit_id,
            status__behavior_class__in=OCCUPYING_BEHAVIOR_CLASSES,
        )
        .only("id")
        .exists()
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def commit_account_import(actor: Any, batch_id: Any, payload: Any = None) -> dict[str, Any]:
    """`POST /accounts/imports/{id}/commit` (11b §S68).

    BR-CUS-051: skip-errors ON writes the valid rows only; OFF is
    all-or-nothing. The **"N created · N failed" summary is ALWAYS returned**,
    with the error report beside it — a partial success is the normal outcome
    of a cutover and it has to be legible, never silent.

    ⛔ **CLOSED 2026-09-01 — `BR-CUS-1043` / `DEF-2592`.** This is the door that
    actually wrote accounts under the reversed rules: a blank number cell was
    allocated from the series (PO 2026-08-27 reversed that) and no customer name
    was required (`BR-CUS-1041` now requires a name AND an identifier). Kept and
    unreachable, as the staging half is.
    """
    _refuse_retired_account_import()
    from apps.customers import selectors

    data = _payload_dict(payload or {})
    with transaction.atomic():
        batch = (
            models.AccountImportBatch.objects.filter(tenant_id=_tenant_id(), pk=batch_id)
            .select_for_update()
            .first()
        )
        if batch is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        _refuse_replayed_import(batch)

        skip_errors = _bool(data.get("skip_errors", batch.skip_errors))
        rows = list(
            models.AccountImportRow.objects.filter(tenant_id=batch.tenant_id, batch=batch).order_by(
                "row_no"
            )
        )
        error_rows = [row for row in rows if row.errors]
        if error_rows and not skip_errors:
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-CUS-051",
                message_key="customers.import.rows_must_be_fixed",
                params={"errors": len(error_rows)},
            )

        created = 0
        failed: list[dict[str, Any]] = []
        allocations: list[dict[str, Any]] = []
        #: `BR-CUS-1023` — rows whose ACCOUNT loaded and whose CUSTOMER was not
        #: minted. Same shape as `allocations` (a per-row fact the wizard
        #: lists), deliberately: it is not an error and must never be counted
        #: as one, or a clean cutover reads as a failed one.
        unidentified: list[dict[str, Any]] = []
        deferred_counts: dict[str, int] = {}
        for row in rows:
            if row.errors:
                # NEVER a silent skip: the row leaves this loop named.
                failed.append({"row_no": row.row_no, "reasons": row.errors})
                continue
            resolved = dict((row.raw or {}).get("resolved") or {})
            try:
                account = _commit_import_row(actor, resolved)
            except (errors.ApiError, errors.NotFoundError) as exc:
                failed.append(
                    {
                        "row_no": row.row_no,
                        "reasons": [
                            {
                                "code": _import_failure_code(exc),
                                "br_ref": getattr(exc, "br_ref", None),
                            }
                        ],
                    }
                )
                continue
            row.account_id = account["id"]
            update_fields = ["account"]
            # ── `BR-CUS-1023` — FLAG THE ROW, don't just count it ───────────
            # The ruling says the row is *"flagged for a human to identify"*,
            # and a count that lives only in this response is gone the moment
            # the wizard is closed. `raw` is this table's own JSON column
            # (`{"source": …, "resolved": …}`) so the flag is DURABLE and needs
            # no migration — the same posture `deferred` already takes for
            # columns the template publishes and this story does not write.
            not_created = account.get("customer_not_created")
            if not_created:
                row.raw = {**(row.raw or {}), "customer_not_identified": not_created}
                update_fields.append("raw")
                unidentified.append(
                    {
                        "row_no": row.row_no,
                        "account_no": account["account_no"],
                        "customer_name": resolved.get("customer_name"),
                        "missing": not_created["missing"],
                        "message_key": not_created["message_key"],
                    }
                )
            row.save(update_fields=update_fields)
            created += 1
            if not resolved.get("account_no"):
                allocations.append({"row_no": row.row_no, "account_no": account["account_no"]})
            for column in resolved.get("deferred") or {}:
                deferred_counts[column] = deferred_counts.get(column, 0) + 1

        from django.utils import timezone

        batch.committed_at = timezone.now()
        batch.save(update_fields=["committed_at"])
        _audit(
            actor,
            "account.bulk_imported",
            batch.id,
            entity_type="account_import_batch",
            after={
                "file": batch.filename,
                "batch_id": str(batch.id),
                "created": created,
                "failed": len(failed),
            },
        )
    return {
        **selectors.account_import_batch(batch.id),
        # BR-CUS-051: ALWAYS shown, success or partial, with the error report.
        "summary": {
            "created": created,
            "failed": len(failed),
            # `BR-CUS-1023` — a SUBSET of `created`, never an addend. These
            # rows succeeded; what they lack is a customer number.
            "unidentified": len(unidentified),
        },
        "allocations": allocations,
        "unidentified": unidentified,
        "errors": failed,
        # Columns the template publishes and this story does not write. Named,
        # counted and returned — the assets `opening_read` precedent.
        "deferred": [
            {
                "column": column,
                "rows": count,
                "story_ref": DEFERRED_COLUMNS[column][0],
                "br_ref": DEFERRED_COLUMNS[column][1],
            }
            for column, count in sorted(deferred_counts.items())
        ],
    }


def _refuse_replayed_import(batch: models.AccountImportBatch) -> None:
    """🔒 CLAUDE.md rule 6 / B2 DB-12 "file+tags imports".

    TWO refusals, because they are two different mistakes:

      · the SAME BATCH committed twice — a double-click, a retried request;
      · the SAME FILE staged again and committed — the operator who was not
        sure the first run finished and uploaded `bbu-accounts-cutover.csv`
        a second time. This is the one that costs 1,240 duplicate accounts,
        and the account-# uniqueness would not have caught it: the 96 rows
        whose number came from the SERIES would get 96 fresh numbers.

    The application check runs FIRST so the operator is told WHICH batch
    already did the work. The partial UNIQUE index on
    (tenant, file_hash, tag_fingerprint) WHERE committed_at IS NOT NULL is the
    backstop underneath. Both exist deliberately — and DEF-058 is why the test
    for this observes the SERVICE path and not only the outcome: a database
    unique that silently substitutes for a deleted application guard means
    nothing goes red when the guard disappears.
    """
    if batch.committed_at is not None:
        raise errors.BizError(
            errors.BIZ_IDEMPOTENT,
            br_ref="BR-CUS-051",
            message_key="customers.import.already_committed",
            params={"batch_id": str(batch.id)},
        )
    if not batch.file_hash:
        return
    prior = (
        models.AccountImportBatch.objects.filter(
            tenant_id=batch.tenant_id,
            file_hash=batch.file_hash,
            tag_fingerprint=batch.tag_fingerprint,
            committed_at__isnull=False,
        )
        .exclude(pk=batch.pk)
        .order_by("committed_at")
        .first()
    )
    if prior is not None:
        raise errors.BizError(
            errors.BIZ_IDEMPOTENT,
            br_ref="BR-CUS-051",
            message_key="customers.import.file_already_imported",
            params={
                "batch_id": str(prior.id),
                "filename": prior.filename,
                "committed_at": prior.committed_at.isoformat(),
            },
        )


def _import_failure_code(exc: Exception) -> str:
    """A refusal from the shared write path, rendered as a ROW reason.

    BR-CUS-017's occupancy refusal is the one worth naming precisely: it is the
    difference between "row 412 failed" and "row 412 names a unit that already
    has a live account".
    """
    key = str(getattr(exc, "message_key", "") or "")
    if "unit_occupied" in key or "already_active" in key:
        return "unit_occupied"
    if "plan_required" in key:
        return "unit_has_no_plan"
    if "start_date_required" in key:
        return "since_required"
    if "start_on_prior_move_day" in key:
        return "since_on_prior_move_day"
    if "unit_not_eligible" in key:
        return "unit_not_eligible"
    return key.rsplit(".", 1)[-1] or "refused"


def _commit_import_row(actor: Any, resolved: dict[str, Any]) -> dict[str, Any]:
    """One staged row → one account, its contact, its address and its customer
    link — through `_open_account`, the module's ONE creator.

    `_open_account` is the UNGUARDED shared body on purpose: the role was
    checked once at the batch entry point (`commit_account_import` is
    @require_role'd) and re-running it per row would multiply one refusal into
    N. Validation, the BR-CUS-017 lock and the per-row audit still run exactly
    as they do for a single hand-typed account — that is the whole point of
    coming through here rather than around it.
    """
    payload: dict[str, Any] = {
        "unit_id": resolved.get("unit_id"),
        "account_type": resolved.get("account_type"),
        "status": resolved.get("status"),
    }
    for field in ("account_subtype", "opened_at", "autopay", "tax_exempt"):
        if resolved.get(field) is not None:
            payload[field] = resolved[field]
    if resolved.get("customer_name"):
        contact: dict[str, Any] = {"full_name": resolved["customer_name"]}
        for field in ("email", "phone"):
            if resolved.get(field):
                contact[field] = resolved[field]
        payload["contact"] = contact
    mailing = resolved.get("mailing_address")
    if mailing and mailing.lower() not in ("same-as-service", "same as service"):
        payload["addresses"] = [{"kind": "mailing", "line1": mailing}]

    account = _open_account(
        actor,
        payload,
        audit_action="account.created",
        account_no=resolved.get("account_no"),
        # DEF-736 — the CUTOVER exemption, and the only place it is passed.
        # BR-CUS-094: every existing record keeps its `government` code and
        # keeps billing; re-pointing is a human act per record (US-CUS-020's
        # value-mapping step). Refusing a legacy category HERE would fail the
        # first upload of every utility the rule was written to make painless.
        allow_legacy_type=True,
    )
    # ⚠ **`BR-CUS-1023` — THIS DOOR NOW CREATES NO CUSTOMER, AND THAT IS THE
    # RULING RATHER THAN A REGRESSION (PO 2026-09-01).** A staged row carries a
    # name and a legacy reference and **no identity at all** — `customer_ref` is
    # a reconciliation key and its own comment above says so — so under the
    # minimum there is nothing here to mint a number with.
    #
    # **THE ACCOUNT LOADS, NO Customer # IS CREATED, AND THE ROW IS FLAGGED FOR
    # A HUMAN TO IDENTIFY.** That answer was already ruled three times before
    # today (*"Load the address, create nobody, flag it"*; *"the account appears
    # when the owner is identified"*; *"a name in a cell is not a person"*) and
    # is NOT put back to the PO (law 13). The import never invents a party.
    #
    # ⚠ **THE COST IS STATED RATHER THAN DISCOVERED:** an import that used to
    # produce a numbered customer per row now produces accounts whose customer
    # is blank until somebody identifies them. A mapping that DOES carry an
    # identifier still mints one — the rule is about evidence, not about doors.
    _row_customer = link_customer(
        account_id=account["id"],
        external_ref=resolved.get("customer_ref"),
        display_name=resolved.get("customer_name"),
        kind=resolved.get("customer_kind"),
    )
    # One key, the same name every other door uses for the same fact.
    account["customer_not_created"] = (_row_customer or {}).get("not_created")
    if resolved.get("deferred"):
        # Never silently dropped (BR-CUS-046 publishes these columns) and never
        # faked (their rules are US-CUS-021/023). Logged per row; counted and
        # returned to the wizard by the caller.
        logger.info(
            "account %s imported with columns deferred to US-CUS-021/023: %s",
            account["account_no"],
            ",".join(sorted(resolved["deferred"])),
        )
    return account


# ── seams other modules resolve HERE by name ────────────────────────────────
def active_account_for_unit(unit_id: Any) -> dict[str, Any] | None:
    """BR-MET-036: the derived-occupancy input metering asks customers for.

    Defining this function is what turns unit occupancy ON across the product
    (apps/metering/seams.py resolves it by name) — "built is not wired" cuts
    both ways, and this is the wire."""
    from apps.customers import selectors

    return selectors.active_account_for_unit(unit_id)


def account_reference_count(unit_id: Any) -> int:
    """BR-MET-037/047 delete + deactivation guard: accounts EVER attached to
    the unit, whatever their status — a closed account is still history that a
    unit delete would orphan."""
    from apps.customers import selectors

    return selectors.account_queryset().filter(unit_id=unit_id).count()


#: DEF-138 — the three answers `unpaid_balance_state` can give, so metering can
#: NAME which one it got instead of inferring it from a bare `True`.
BALANCE_CLEAR = "clear"
BALANCE_OUTSTANDING = "unpaid_balance"
BALANCE_UNREADABLE = "balance_unreadable"


def unpaid_balance_state(unit_id: Any) -> dict[str, Any]:
    """BR-MET-047's money half, from THE LEDGER, and **fail-closed** — DEF-138.

    ⛔ **WHAT THIS REPLACED, AND WHY IT NEVER ONCE REFUSED.** This read used to
    be `account_queryset().filter(unit_id=unit_id, balance__gt=0).exists()` —
    the CACHED `accounts.balance` column, which **nothing in this product
    writes**. So it answered `False` for every unit in the estate, including one
    whose account held an issued, unpaid **108.88**, and the BR-MET-047 refusal
    metering builds on it has never fired against a real debt. Its tests passed
    throughout because they monkeypatch the seam: the guard was written,
    correct and tested, and had never been asked about real money. Same cause as
    DEF-127 and the same shape as DEF-035.

    ⚠ **AND THE FIX IS NOT ONLY "READ THE LEDGER" — IT IS THAT AN UNREADABLE
    BOOK MUST REFUSE.** `ArPositions.amount_for` returns `None`, never
    `Decimal("0")`, when the books could not be asked (a partial deployment, no
    AR designation, DEF-081's mixed book). A guard that cannot check must not
    pass: permitting a deactivation on an unanswered question is exactly the
    old bug wearing a new source. So the three states are DISTINCT and the
    middle one BLOCKS:

      · `clear`            — the books answered, and nothing is owed here.
      · `unpaid_balance`   — the books answered, and money is outstanding.
      · `balance_unreadable` — the books could not be asked. **Blocks**, and
        carries the ledger's own `unavailable` reasons so the screen can say
        which deployment fact is missing rather than showing a figure.

    ⚠ **A UNIT THAT HAS NEVER HELD AN ACCOUNT IS `clear`, EVEN UNREADABLE.**
    Nothing can be owed on a unit no account was ever attached to, so an
    unreadable ledger is not a reason to refuse there — that would block the
    ordinary tidy-up of a mis-typed unit on every tree where the ledger seam is
    unwired, which is every tree today. The fail-closed answer is for units
    that COULD owe.
    """
    from apps.customers import selectors

    account_ids = [
        str(pk)
        for pk in selectors.account_queryset().filter(unit_id=unit_id).values_list("id", flat=True)
    ]
    if not account_ids:
        return {"state": BALANCE_CLEAR, "amount": None, "currency": None, "unavailable": ()}

    positions = seams.ar_positions(account_ids=account_ids)
    if not positions.available:
        return {
            "state": BALANCE_UNREADABLE,
            "amount": None,
            "currency": positions.currency,
            "unavailable": positions.unavailable,
        }

    total = Decimal("0")
    for account_id in account_ids:
        amount = positions.amount_for(account_id)
        if amount is None:
            # Belt and braces: `available` is True, so this cannot happen today.
            # If it ever does, it is an unanswered question and it BLOCKS.
            return {
                "state": BALANCE_UNREADABLE,
                "amount": None,
                "currency": positions.currency,
                "unavailable": positions.unavailable,
            }
        total += Decimal(str(amount))
    if total > 0:
        return {
            "state": BALANCE_OUTSTANDING,
            # CLAUDE.md rule 2 — a decimal STRING at 4dp with its CHAR(3),
            # never a float and never a display-rounded number.
            "amount": str(total.quantize(Decimal("0.0001"))),
            "currency": positions.currency,
            "unavailable": (),
        }
    return {
        "state": BALANCE_CLEAR,
        "amount": None,
        "currency": positions.currency,
        "unavailable": (),
    }


def unpaid_balance_exists(unit_id: Any) -> bool:
    """BR-MET-047: metering refuses to deactivate a unit with money outstanding.

    The BOOLEAN half of `unpaid_balance_state` above, kept because
    `apps/metering/seams.py` resolves THIS NAME and a rename would silently
    unwire the guard (a seam is a contract, hard-won law 2). **`True` now means
    "do not deactivate"**, which covers both money outstanding and books that
    could not be asked — the reason is in `unpaid_balance_state`, which metering
    reads when it wants to name the blocker.
    """
    return unpaid_balance_state(unit_id)["state"] != BALANCE_CLEAR


def active_account_count(service_code: str) -> int:
    """BR-TEN-026: the live count tenancy's service-disable guard reads.

    Slice 1 could not wire this — the service behind an agreement lives on
    metering's `service_points` and customers had no read seam. It has one now
    (apps/customers/seams.py), so the count is real: accounts that OCCUPY a
    unit and hold an open agreement for that service.

    ⛔ **THREE QUERIES, WHATEVER THE ESTATE — DEF-1549.** This used to call
    `seams.service_point_ref(point_id)` inside the loop, and that seam costs
    **two** round trips per point (the point row, then the platform-catalog
    probe for its code). The `service_by_point` dict memoised within ONE call
    and nothing carried across calls, so:

      * `tenancy.selectors.services_overview()` calls this **once per active
        service** — ~10 today — and each call re-walked every open agreement's
        points from scratch: `~10 × 2P` queries to draw one S8 screen; and
      * `assets._create_asset_inner` reached that screen read **once per import
        row**, which is how a twenty-row meter file became a gunicorn
        `WORKER TIMEOUT` for the Product Owner.

    The N+1 is real in its own right and would have bitten the next caller, so
    it is fixed here at the source rather than only routed around: the points
    are now resolved in ONE batched seam call (`service_codes_for_points`,
    two queries) after the agreements are read.

    ⚠ **BR-TEN-029 still holds — this is COUNTED LIVE, never cached.** The
    change is how many round trips one live count costs, not when it is taken;
    the disable guard still reads a figure computed at the moment it asks.

    ⚠ **`str()` ON BOTH SIDES OF THE MATCH IS LOAD-BEARING.** `values_list`
    hands back `UUID`s and the batched map is keyed by `str`; comparing the two
    shapes directly matches nothing, and the failure would be a silent **zero**
    — a count that lets a service be disabled underneath live accounts, which
    is precisely what BR-TEN-026 exists to prevent."""
    return active_account_counts().get(service_code, 0)


def active_account_counts() -> dict[str, int]:
    """`active_account_count` for EVERY service in one pass — `DEF-TEN-8731`.

    ⛔ **`services_overview()` USED TO ASK THE SINGULAR ONCE PER SERVICE**, and
    each ask re-read every open agreement and re-resolved every service point
    behind them: eleven passes over the whole estate to draw one table. At
    10,015 accounts that was 13.6–14.0 s of `GET /settings/services` in the
    browser; at 40,000 gunicorn killed it at 60 s, and the bulk run page asks
    it on every open. Now it is ONE grouped statement — each agreement's
    point's service correlated through metering's lazy queryset
    (`seams.service_points_queryset`), counted per service in PostgreSQL — the
    same set the singular counted, keyed by code. Where metering publishes no
    queryset it falls back to one batched read and a group-by in Python. The singular above is this dict's lookup,
    so the screen's column and the disable guard cannot disagree.

    `{code: count}` — a service nobody holds an open agreement for is ABSENT,
    and the caller's `.get(code, 0)` is the honest zero (BR-TEN-026). Still
    COUNTED LIVE (BR-TEN-029): nothing is cached across calls.
    """
    agreements = models.ServiceAgreement.objects.filter(
        tenant_id=_tenant_id(),
        ended_on__isnull=True,
        account__status__behavior_class__in=OCCUPYING_BEHAVIOR_CLASSES,
    )
    points = seams.service_points_queryset()
    if points is not None:
        # ONE statement: each agreement's point's service correlated as a
        # subquery, grouped in PostgreSQL, eleven rows back. Measured at 40,008
        # accounts (160,032 agreements) this replaced reading every agreement
        # and every point into Python — 3.5 s on its own.
        from django.db.models import Count, OuterRef, Subquery

        grouped = (
            agreements.annotate(
                _service_id=Subquery(
                    points.filter(pk=OuterRef("service_point_id")).values("service_id")[:1]
                )
            )
            .values("_service_id")
            .annotate(accounts=Count("account_id", distinct=True))
            .order_by()
        )
        # ⚠ The subquery's value comes back in the backend's own spelling (a
        # 32-hex string on SQLite, a UUID on PostgreSQL) — normalised through
        # `UUID` on both sides, or every key misses and the count is a silent
        # ZERO (the shape `str()` guards in the singular's docstring above).
        from uuid import UUID

        counts = {
            str(UUID(str(row["_service_id"]))): row["accounts"]
            for row in grouped
            if row["_service_id"] is not None
        }
        codes = {
            str(UUID(str(pk))): code for pk, code in seams.service_codes_by_ids(counts).items()
        }
        return {codes[key]: n for key, n in counts.items() if key in codes}
    rows = list(agreements.values_list("account_id", "service_point_id"))
    service_by_point = seams.service_codes_for_points({point_id for _, point_id in rows})
    accounts_by_service: dict[str, set[Any]] = {}
    for account_id, point_id in rows:
        code = service_by_point.get(str(point_id))
        if code is not None:
            accounts_by_service.setdefault(code, set()).add(account_id)
    return {code: len(accounts) for code, accounts in accounts_by_service.items()}


# ── BR-PAY-013's counting half — the seam payments could not write (DEF-069) ─
#
# `accounts` is CUSTOMERS' table and payments may not write another module's
# table (B1 / DB-16). BR-PAY-013 is CONFIRMED and says a bounce increments
# `accounts.nsf_count` and that at the tenant's N the account goes cash-only and
# off autopay. Customers published NO function for either, so every bounce left
# the count at 0 and the threshold could never be reached — for as long as the
# bounce path has existed. Nothing was red, because no test asserted a count
# that no code was ever going to write (DEF-069).
#
# ONE CALL DOES BOTH, and that is not tidiness: the count and the threshold
# decide the flag TOGETHER, so a caller holding two functions could increment
# and then fail to evaluate, and the account would sit at its second bounce with
# no flag and nothing saying why (DEF-070's own prevention column asks for
# exactly this shape).


@dataclass(frozen=True)
class NsfOutcome:
    """What one bounce did to the account — and what it could not do.

    `problems` carries the same discipline as `apps/payments/reversal
    .REVERSE_UNAVAILABLE`: a caller must never have to infer an absence. The one
    absence this can still report is a THRESHOLD it could not read, and it
    reports it rather than assuming the shipped default of 2.
    """

    account_id: str
    nsf_count: int
    threshold: int | None
    cash_only_no_autopay: bool
    flag_tripped_now: bool
    problems: tuple[dict[str, Any], ...] = ()


def record_nsf(account_id: Any, *, actor: Any = None) -> NsfOutcome:
    """BR-PAY-013's `nsf_count++` and its privilege flag, in one transaction.

    **PUBLISHED FOR PAYMENTS.** `apps/payments/reversal.py` resolves it BY NAME
    — the seam idiom that module already uses for `account_queryset` — and the
    resolve-by-name call site is what makes this reachable without payments ever
    importing a customers model (B1 / DB-16 / gate G6).

    ════════════════════════════════════════════════════════════════════════
    THE COUNT AND THE FLAG ARE ONE DECISION
    ════════════════════════════════════════════════════════════════════════
    Worked on J12's own account, at the tenant default **N = 2**:

      * **first bounce** → `nsf_count` 0 → **1**, no flag (J12 step 2/3: *"no
        flag yet (N=2)"*);
      * **second bounce** → `nsf_count` 1 → **2**, **flag TRIPS** (J12 step 4);
      * with the tenant's N changed to **3**, the second bounce trips nothing
        and a **third** is required — US-PAY-009 TC-3 verbatim, *"config, not
        constant"*.

    The comparison is `>=`, not `==`: an account that somehow passes the
    threshold without this path seeing the exact value must still be flagged,
    and an `==` would let it through forever.

    ════════════════════════════════════════════════════════════════════════
    WHAT IT DELIBERATELY DOES NOT DO
    ════════════════════════════════════════════════════════════════════════
      * **It never lowers the count and never clears the flag.** J12 step 6:
        *"the cash-only flag REMAINS — no rule auto-clears it; lifting it is an
        explicit staff config action, audited"*. That LIFT has no story and no
        endpoint yet and is **REPORTED, not invented here** — a clearing path
        written on nobody's rule is a way for a privilege sanction to disappear.
      * **It never touches `accounts.autopay`.** That column is the customer's
        own ELECTION (BR-CUS-059); the flag is the ENFORCEMENT, and
        `apps.payments.autopay.is_enrolled` reads the flag. Flipping the
        election would destroy it with nothing to restore on a lift.
      * **It never guesses the threshold.** An unreadable setting produces
        `threshold=None`, `nsf_privilege_threshold_unavailable` on `problems`,
        and NO FLAG — the count still increments, because the count is a fact
        and the flag is a judgement that needs a number nobody could read.
      * **It never reads a clock.** The trip's who/when is `audit_log`'s
        (hard rule 7), written here inside the same transaction.

    Idempotency is the CALLER's (hard rule 6): the bounce that calls this is
    guarded by `uq_payments_reverses` and the webhook key, so a replayed bounce
    never reaches this function and the count cannot be double-incremented by
    one returned cheque.
    """
    with transaction.atomic():
        account = (
            models.Account.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), pk=account_id)
            .first()
        )
        if account is None:
            raise errors.NotFoundError()

        before = {
            "nsf_count": account.nsf_count,
            "cash_only_no_autopay": account.cash_only_no_autopay,
        }
        account.nsf_count = (account.nsf_count or 0) + 1

        problems: list[dict[str, Any]] = []
        threshold = seams.nsf_privilege_threshold()
        tripped = False
        if threshold is None:
            problems.append(
                {
                    "code": "nsf_privilege_threshold_unavailable",
                    "br_ref": "BR-PAY-013",
                    "detail": "the tenant's `nsf_privilege_n` (B2 r14 #5, S70 collections) "
                    "could not be read, so the cash-only / no-autopay flag was NOT decided. "
                    "The bounce is counted — that is a fact — but the flag is a judgement "
                    "against a number, and the shipped default of 2 is NOT substituted here: "
                    "it lives once, in the tenant's own settings, and a copy of it in this "
                    "file would be free to drift from the figure on their screen.",
                }
            )
        elif account.nsf_count >= threshold and not account.cash_only_no_autopay:
            account.cash_only_no_autopay = True
            tripped = True

        account.save(update_fields=["nsf_count", "cash_only_no_autopay", "updated_at"])
        _audit(
            actor,
            "account.nsf_recorded",
            account.pk,
            before=before,
            after={
                "nsf_count": account.nsf_count,
                "cash_only_no_autopay": account.cash_only_no_autopay,
                "nsf_privilege_n": threshold,
                "flag_tripped": tripped,
                "job": None if actor is not None else "payments.reverse",
            },
        )

    return NsfOutcome(
        account_id=str(account.pk),
        nsf_count=account.nsf_count,
        threshold=threshold,
        cash_only_no_autopay=account.cash_only_no_autopay,
        flag_tripped_now=tripped,
        problems=tuple(problems),
    )


class DepositRegisterError(Exception):
    """The deposit register refusing a movement it cannot make truthfully.

    A plain exception and NOT an `errors.BizError`: neither case it raises is
    something a clerk typed. Both mean a caller asked for a movement that would
    leave the register disagreeing with the books — which is a fault in the
    calling path, reported with both figures, rather than a message to translate
    into thirteen languages.
    """


@dataclass(frozen=True)
class DepositMovement:
    """What one cleared deposit — or one bounced one — did to the register.

    `held_before` / `held_after` are both carried so a caller, an audit reader
    and a test all see the movement rather than only its result: a register that
    ends at 150.00 could have started at 0.00 or at 150.00, and only one of
    those means the money arrived.
    """

    account_id: str
    account_ref: str | None
    moved: Decimal
    held_before: Decimal
    held_after: Decimal
    received_on: Any = None
    problems: tuple[dict[str, Any], ...] = ()


#: ⚠ **THIS IS NOT A HOLE IN `REFUSED_FIELDS`, AND THE DISTINCTION IS THE WHOLE
#: OF BR-CUS-670.** `deposit_on_file` stays REFUSED on every door a person types
#: into (`create_account`, `update_account`), for the reason BR-CUS-023 gives:
#: how much deposit an account SHOULD hold is a LOOKUP from the plan's deposit
#: schedule and is nobody's free text. What this function writes is a different
#: fact — how much the utility ACTUALLY HOLDS — and it is derived from a money
#: event that has already reached the books, exactly as `record_nsf` derives
#: `nsf_count` from a bounce that has already been reversed. Neither is an input.
DEPOSIT_MOVEMENT_ACTIONS = ("deposit.received", "deposit.released")


def record_deposit_movement(
    account_id: Any,
    amount: Any,
    *,
    actor: Any = None,
    received_on: Any = None,
    released: bool = False,
) -> DepositMovement:
    """BR-CUS-670 — the customer deposit REGISTER, moved by a cleared deposit.

    HUMAN-OWNED · HUMAN-REVIEW-PENDING (🔒 the deposit register that S36 ties
    out against the 2300 liability). Row in
    `12-governance/09-human-review-ledger.md`.

    **PUBLISHED FOR PAYMENTS**, and resolved BY NAME there — the `record_nsf`
    shape, and for the same reason: `accounts` is CUSTOMERS' table and payments
    may not write another module's (B1 / DB-16). Payments posts the ledger leg
    and then asks customers to move the register; neither module does both.

    ════════════════════════════════════════════════════════════════════════
    THE DEFECT THIS CLOSES — DEF-177, OPEN SINCE 2026-08-16
    ════════════════════════════════════════════════════════════════════════
    `apps/payments/ledger_seam.post_payment_cleared` has credited the 2300
    deposit-liability account on every cleared deposit for a fortnight, and
    **nothing has ever written `accounts.deposit_on_file`**. So the first
    utility to take a $150.00 deposit got *books $150.00 / register $0.00* on
    the S36 tie-out, and BR-LED-007 blocks a release on it — correctly, because
    the register really was not being kept.

    ⚠ **THE MOVEMENT IS THE MONEY THAT CLEARED, NOT THE PLAN'S FIGURE.** A
    deposit-purpose payment of $150.00 moves the register by $150.00 even if the
    plan schedule says $300.00; the register states what is HELD, and the
    difference between held and required is a collections question, not a
    bookkeeping one. That is what keeps this side of the tie-out equal to the
    side payments posts: **both are written from the SAME cleared amount.**

    ⚠ **`released=True` IS THE BOUNCE, AND IT EXISTS SO THE TIE-OUT CANNOT
    DRIFT BACK.** When a deposit payment is reversed, `posting.reverse_entry`
    mirrors the entry and the 2300 liability falls; a register that did not fall
    with it would re-open DEF-177 from the other side, one bounced cheque at a
    time. The release is a SUBTRACTION on the register and never a negative
    balance: a utility cannot hold less than none of a customer's money, so a
    release larger than what is held is REFUSED by name rather than clamped.

    ⚠ **IT DOES NOT DECIDE WHETHER A DEPOSIT WAS DUE (BR-CUS-023 / US-CUS-007).**
    The plan-schedule lookup is still unbuilt and is still that story's; this
    records money that arrived. The two questions are not the same one and
    answering the second here would have been inventing the first.
    """
    moved = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    if moved <= Decimal("0"):
        # BR-CUS-670: the register moves by the amount that CLEARED, and the
        # DIRECTION is stated by `released=` rather than inferred from a sign —
        # so a zero or negative movement is a caller fault, not a customer's money.
        raise DepositRegisterError(
            f"a deposit movement of {moved} was asked for on account {account_id}, and a "
            "movement must be greater than zero. A release is asked for with `released=True` "
            "and a positive figure, so the direction is never inferred from a sign."
        )
    with transaction.atomic():
        account = (
            models.Account.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), pk=account_id)
            .first()
        )
        if account is None:
            raise errors.NotFoundError()
        before = Decimal(account.deposit_on_file or Decimal("0"))
        after = before - moved if released else before + moved
        if after < Decimal("0"):
            # Refused, never clamped. Clamping would leave the register at 0.00
            # while the ledger reversal took the full amount out of 2300 —
            # a drift created by the very code written to prevent one.
            # BR-CUS-670 / BR-CUS-025 — a utility cannot hold less than none of a
            # customer's deposit, and clamping to zero is what would CREATE the drift.
            raise DepositRegisterError(
                f"account {account.account_no or account_id} holds {before} of this "
                f"customer's money and a release of {moved} was asked for, which would leave "
                f"{after}. Refused rather than reduced to zero: the reversing entry takes the "
                "FULL amount out of the deposit-liability account, so a register stopped at "
                "zero would differ from the books by exactly the excess."
            )
        fields = ["deposit_on_file"]
        account.deposit_on_file = after
        # BR-CUS-050 — the ORIGINAL receipt date, stamped only when the account
        # has none. A second deposit on an account that already holds one must
        # not restart BR-CUS-057's interest clock and quietly under-pay the
        # customer who has been with the utility longest.
        if not released and received_on is not None and account.deposit_received_on is None:
            account.deposit_received_on = received_on
            fields.append("deposit_received_on")
        account.save(update_fields=[*fields, "updated_at"])
        _audit(
            actor,
            "deposit.released" if released else "deposit.received",
            account.pk,
            before={"deposit_on_file": str(before)},
            after={
                "deposit_on_file": str(after),
                "moved": str(moved),
                "deposit_received_on": (
                    account.deposit_received_on.isoformat() if account.deposit_received_on else None
                ),
                "job": None if actor is not None else "payments.record",
            },
        )
    return DepositMovement(
        account_id=str(account.pk),
        account_ref=account.account_no,
        moved=moved,
        held_before=before,
        held_after=after,
        received_on=account.deposit_received_on,
    )


def cash_only_no_autopay(account_id: Any) -> bool | None:
    """Is this account under the BR-PAY-013 privilege sanction?

    **None means the account is not this tenant's or does not exist**, and it is
    never collapsed into False: *"they may use autopay"* and *"we could not find
    them"* are different answers, and only the first one is safe to act on. The
    autopay path refuses on a None rather than recording an intent.
    """
    row = (
        models.Account.objects.filter(tenant_id=_tenant_id(), pk=account_id)
        .values("cash_only_no_autopay")
        .first()
    )
    return None if row is None else bool(row["cash_only_no_autopay"])


# ── boundaries this slice does NOT cross (prime directive) ──────────────────
# Each of these is reachable from the write path above, has a CONFIRMED rule,
# and has nowhere to store its result. They are stubs rather than omissions so
# that a caller gets the rule id instead of a plausible-looking success.
def record_plan_snapshot(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    """BR-CUS-029 / BR-CUS-014 sc.1 — the append-only `account_plan_assignments`
    row every activation owes J2 step 4. The table has no DDL in B2 or any
    addendum ("Exact DDL of all addenda = Eng-Lead 🔒 at migration authoring"),
    so writing one would mean inventing schema."""
    raise NotImplementedError("BR-CUS-029")


# ── CR-030 W1 · the accounts import target's seam implementers ──────────────
# metering's runner stages, maps and validates; every `accounts` row is written
# HERE, because customers owns the table (B1/B2 §2). G20 asserts each documented
# seam has an implementer, and these are the three `apps/metering/seams.py`
# documents: `create_from_import`, `post_opening_batch_from_import`,
# `rollback_from_import`.


def create_from_import(*, actor: Any = None, payload: dict[str, Any]) -> dict[str, Any]:
    """One import row → one account, its customer link, and its opening position.

    HUMAN-OWNED · HUMAN-REVIEW-PENDING (money rounding 🔒 — the cached balance).

    ⚠ **IT GOES THROUGH `_open_account`, NOT `Account.objects.create`.** That
    function's own docstring names this caller as one of its three doors and
    says why: BR-CUS-017 (one live account per unit, ever) is enforced in
    exactly ONE place, and a bulk creator that reimplemented the guard would be
    a second, drifting copy of the only thing standing between one meter and two
    bills. A validated rule must apply to row 1,199 exactly as to a hand-typed
    account.

    ⚠ **`accounts.balance` IS WRITTEN HERE AND ONLY HERE ON THIS PATH.** It is a
    CACHE (B2) and no ordinary path writes it — but US-CUS-021 makes it *"Σ
    bucket amounts exactly"* at cutover, and until US-CUS-022's journal entries
    post there is nothing else for a screen to read. It is set from the SAME
    position object the buckets were written from, never re-derived: two
    derivations of one number is how they come to disagree.

    ⛔ **THE ACCOUNT INHERITS ITS UNIT WHATEVER ITS STATUS — `DEF-2518`, PO
    ruling 2026-08-29, verbatim: *"if account is created then we need to inherit
    details form units - otherwise upadling it later will be big tasks"*.**

    Until CR-047 the only writer of `service_agreements` on this path sat inside
    `_make_occupying`, behind `if is_occupying(status)`. The Status column is
    OPTIONAL in the published template and its rule only warns on an UNKNOWN
    value, never an absent one — so an empty Status cell produced a
    `pending_activation` account with **no service agreements at all**: no
    service, no route, no cycle, no plan and no meter, and the receipt counted
    it under *"created"* beside the good ones. The four keywords below are the
    fix; the guards that really are about occupying stay behind the status
    check, because BR-CUS-018 says a draft must not block the unit.

    ⚠ **`require_plan=False` IS TASK 11 AND IT DOES NOT LET AN ACCOUNT BILL
    UNPLANNED.** BR-MET-040 says *"at account **activation**"*; this door is
    creation. An account whose unit has no plan is stopped in two later places
    that were checked rather than assumed (law 1): `activate_account` and
    `update_account`'s status change both still run `_require_plan_on_unit`, and
    the bill run itself refuses at `apps/billing/gather.gather_account` with
    `GATHER_NO_PLAN` → a `resolve-subscription` exception row that
    `runs.NOT_RETRYABLE_HERE` marks as needing an edit elsewhere.

    ⚠ **`services_linked` IS A COUNT OF ROWS THIS CALL CREATED**, collected as
    `_open_account` writes them rather than re-counted afterwards — the same
    posture as the `deposit` read-back below, for the same reason.
    """
    from apps.customers import import_writer

    mapped = dict(payload.get("mapped") or {})
    unit_id = payload.get("unit_id")
    account_no = payload.get("account_no") or None
    currency = payload.get("currency") or _tenant_currency()
    # ONE normalisation of the run's changeover date, used by both consumers —
    # the opening buckets and the inherited agreements. `import_runs` hands over
    # a `date`; a str is accepted so a second caller cannot silently produce two
    # different readings of one day.
    as_of = _as_date(payload.get("cutover_on"))

    links: list[Any] = []
    account = _open_account(
        actor,
        payload.get("account") or {},
        audit_action="account.created_by_import",
        allowed=IMPORT_ACCOUNT_FIELDS,
        unit_id=unit_id,
        account_no=account_no,
        inherit_services=True,
        inherit_started_on=as_of,
        require_plan=False,
        agreements_out=links,
    )

    # BR-CUS-054 — one `customer_ref` = ONE customer row, so the landlord with
    # fourteen units is one customer with one number and not fourteen. A row
    # with neither ref nor name links nothing and returns None, which is lawful:
    # every account created before the customers table has no link either.
    # ⚠ **`customer_ref` HERE, `external_ref` ON THE ACCOUNT — TWO COLUMNS, TWO
    # FACTS, AND CONFLATING THEM WAS `DEF-1660`.** This one is the PERSON's
    # legacy id and reaches `customers.external_ref` (BR-CUS-054); the row's
    # `external_ref` is the ACCOUNT's and rode in through
    # `_account_payload_from` → `IMPORT_ACCOUNT_FIELDS` → `_open_account`
    # (BR-CUS-172). A landlord with fourteen units has ONE of the first and
    # FOURTEEN of the second.
    # ⚠ **CR-056 W2b — THE KIND IS PASSED, NOT LEFT TO THE COLUMN DEFAULT.** A
    # mapping that carries `customer_kind` states it; one that does not leaves it
    # unstated, and `link_customer` records `kind_defaulted` on the audit row
    # rather than letting `person` arrive invisibly. **This path presents NO
    # identity evidence** — `customer_ref` is the LEGACY system's id, a
    # reconciliation key — so an unstated kind is lawful here and refuses
    # nothing: a spreadsheet column may not earn a tier under either kind's test.
    # ⛔ **CR-058 W7 · BR-CUS-1041 — THE ROW'S IDENTITY EVIDENCE, RESOLVED HERE
    # AND NOWHERE ELSE.** PO ruling 2026-09-01: *"Without identifier we cannot
    # create Customer ID or master account ot regular account"*. The runner
    # assembles a `customer` block from the operator's own cells
    # (`import_runs.account_customer_block`) and hands it over; **this door does
    # the one act** — match first, create on no match, create nothing with no
    # identifier — exactly as the master-account door does for the premises
    # import. A matcher on the metering side would be the second copy `CR-058`
    # exists to prevent.
    #
    # ⚠ **THE BLOCK IS OPTIONAL AND ITS ABSENCE IS THE OLD BEHAVIOUR.** A caller
    # that sends none falls back to the row's own `customer_ref` /
    # `customer_name` / `customer_kind`, which is what every run staged before
    # today carries — so a re-load of an older run resolves exactly as it did.
    block = dict(payload.get("customer") or {})
    customer = link_customer(
        account_id=account["id"],
        # ⚠ **`customer_ref` HERE IS STILL THE LEGACY KEY AND STILL NOT
        # EVIDENCE.** It reaches `customers.external_ref` and may LINK; it can
        # never satisfy the creation minimum, because it identifies a row in
        # somebody else's database and not a person.
        external_ref=block.get("external_ref") or mapped.get("customer_ref"),
        display_name=block.get("display_name") or mapped.get("customer_name"),
        kind=block.get("kind") or mapped.get("customer_kind"),
        identity=block.get("identity") or None,
        customer_no=block.get("customer_no") or mapped.get("customer_no"),
    )

    position = import_writer.write_opening_buckets(
        account_id=account["id"],
        account_ref=account.get("account_no"),
        mapped=mapped,
        as_of=as_of,
        currency=currency,
        import_run_id=payload.get("import_run_id"),
    )
    if not position["empty"]:
        # The cache, from the position just written. `update()` rather than a
        # model save so no other field can be touched by accident.
        models.Account.objects.filter(pk=account["id"]).update(balance=position["total"])

    # ⚠ **THE MIGRATED DEPOSIT IS REPORTED BACK, BECAUSE IT HAS A LEDGER SIDE
    # AND USED NOT TO (DEF-1713).** `deposit_on_file` rode in through
    # `IMPORT_ACCOUNT_FIELDS` (US-CUS-023) and this function posted NOTHING for
    # it, so the seeded estate carried a register of $750.00 against a 2300
    # deposit-liability GL of $0.00 — the exact mirror of DEF-177. It is read
    # back from the ROW rather than from the payload, so what the caller hands
    # the ledger is what the database actually holds: two derivations of one
    # number is how they come to disagree.
    held = (
        models.Account.objects.filter(pk=account["id"])
        .values("deposit_on_file", "deposit_received_on")
        .first()
    ) or {}
    deposit = Decimal(held.get("deposit_on_file") or 0)

    return {
        "id": account["id"],
        "account_no": account.get("account_no"),
        "customer_no": (customer or {}).get("customer_no"),
        # ⛔ **CR-058 W7 — the receipt's *matched* / *created* split, and the
        # flag that tells the runner to walk the `customer` series past a number
        # the file itself quoted (`DEF-2593` / `DEF-577`).**
        "customer_created": bool((customer or {}).get("created")),
        "customer_no_from_file": bool((customer or {}).get("customer_no_from_file")),
        # `BR-CUS-1023` — WHY it is None, where it is None. A blank customer
        # number with no sentence beside it is the state CR-056 §4 measured and
        # this ruling deliberately re-creates; the difference is that it now
        # says so (hard-won law 2).
        "customer_not_created": (customer or {}).get("not_created"),
        "opening_total": str(position["total"]),
        "opening_empty": position["empty"],
        "deposit_on_file": str(deposit),
        "deposit_received_on": held.get("deposit_received_on"),
        # ⛔ **CR-047's CROSS-LANE CONTRACT — how many `service_agreements` rows
        # THIS call created for THIS account.** `apps/metering/import_runs.py`
        # accumulates it into the run's counters and the S68 receipt renders it,
        # so a migrating utility can see that 1,247 accounts brought 2,494
        # service links across and not zero. An `int`, always present, `0` when
        # the unit had no service points at all — which is itself a real answer
        # and one worth showing on the receipt.
        "services_linked": len(links),
    }


#: ⛔ The open question this module refuses to guess at. Named as a constant so
#: no call site decides it by accident and so a grep for the id finds the code
#: waiting on it (the `import_writer.OQ_OPENING_CREDIT` posture).
OQ_ROLLBACK_OPENING = "OQ-352"


def update_from_import(
    actor: Any = None, *, account_no: Any = None, changes: dict[str, Any] | None = None
) -> dict[str, Any]:
    """⛔ **CR-046 C4 — *Insert & update*'s existing-row half for accounts.**

    ⛔⛔ **THIS FUNCTION CARRIES NO `@require_role`, AND THAT IS DELIBERATE.
    DO NOT ADD ONE BACK (`DEF-2515`, critical, PO-reported).**

    It had one — `@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")`,
    copied from the hand-typed doors — and it took a real utility's **9,000-account
    migration** down with an auth error. PO verbatim, 2026-08-29: *"When we tried
    to upload accounts yesterday with 9000 accounts - it gave us Auth error and
    then 500"*.

    **THE MECHANISM, AND WHY IT CANNOT BE FIXED ANY OTHER WAY.**
    `import_runs.ASYNC_ROW_BAR` is 5,000. Above it the load stage is DEFERRED,
    and the worker carries `import_runs._JobActor` — `__slots__ = ("id",)`, an id
    and **no role**, by design and correctly so:

        "Role was checked at enqueue; the worker carries the actor id in the
         record, never a role, so it can grant nothing."

    `core.permissions.require_role` reads `getattr(actor, "role", None)`, gets
    `None`, and raises `AuthError` AUTH-002 — its own docstring already says
    *"job callers get the same exception and their runner records it."* So a role
    gate here is **not defence in depth; it is a check that can only ever produce
    a FALSE REFUSAL**, because the worker is architecturally incapable of
    satisfying it.

    **THE ROLE IS STILL ENFORCED, IN THE ONE PLACE THAT CAN ENFORCE IT.**
    `@require_role` sits on `import_runs.transform` / `validate` / `load` — the
    REQUEST that enqueues the stage — plus `BR-MET-098`'s approver check in the
    API layer. `BR-SHL-025` is satisfied by the door, not by this line.
    `test_def2515_worker_has_no_role.py::TC-2` asserts that door is still shut,
    so the deletion is provably a narrowing of nothing.

    ⚠ **THE ASYMMETRY IS THE EVIDENCE, AND IT WAS SITTING IN THIS FILE ALL
    ALONG.** `create_from_import` above has NEVER carried a decorator — the same
    loader calls it, from the same worker, for the same reason. Only the UPDATER
    got one, and nobody re-asked whether a worker could satisfy it. Measured when
    this was filed: of **220** role-guarded functions in the backend, exactly ONE
    was reachable from the import load path, and it was this one.

    ⚠ **AND IT IS `DEF-1108` REPEATING.** That defect moved the approver check
    out of the worker and left the rule in as many words: *"rebuilding a role in
    the worker would be a second, weaker place for that decision to live."* This
    decorator was added afterwards, by a lane with no reason to think about
    workers, and the sentence did not reach it. `TC-3` now walks the whole seam
    surface, so the next one fails on its own commit rather than in somebody's
    migration.

    ⚠ **WHY IT HID FOR SO LONG:** every import test in this repository uses a
    handful of rows, so the entire deferred path — the one a real migration
    ALWAYS takes — was never executed end to end. At or below 5,000 rows the load
    runs on the request, which carries a real role, and everything passes.


    PO verbatim, of the shape now applied to all four uploads: *"if yes - ( in
    case of insert - reject it | in case of Insert & Update = update the
    details)"*.

    ⚠ **IT DOES NOT TOUCH THE BOOKS, AND THAT IS HARD RULE 4 RATHER THAN A
    SCOPE CHOICE.** The four `ob_*` buckets became journal entries through the
    ledger at the first load (GT-16 ❄️, *"Σ of all opening JEs = Σ of all
    imported buckets (1,213 accounts → $184,320.55)"*). A journal entry cannot
    be updated or deleted; a correction is a NEW entry. So a corrected re-run
    updates an account's DETAILS and leaves its opening position exactly where
    it is — and the operator who genuinely needs to move an opening figure does
    it through an adjustment, which is a visible act with its own audit row
    rather than a silent side effect of re-uploading a spreadsheet.
    **`IMPORT_UPDATE_FIELDS` is where that exclusion is enforced**, and its
    docstring carries the rest of the reasoning.

    ⚠ **IT REUSES `update_account`'s VALIDATOR AND ITS STATUS MACHINE.** A bulk
    updater with its own rules is the second, drifting copy `_open_account`'s
    docstring warns about — a validated rule must apply to row 1,199 exactly as
    it applies to a hand-edited account.

    Addressed by `account_no` because that is what the runner's match key
    resolved to; an unknown one RAISES rather than creating, because the
    caller has already decided this row is an update.
    """
    from apps.customers import selectors

    data = _payload_dict(changes or {})
    _reject_unknown(data, IMPORT_UPDATE_FIELDS)
    cleaned = _validate_account(data, partial=True, allowed=IMPORT_UPDATE_FIELDS)
    warnings: list[dict[str, Any]] = []
    with transaction.atomic():
        account = (
            models.Account.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), account_no=account_no)
            .first()
        )
        if account is None:
            # Unreachable through the runner (the key matched a moment ago);
            # asserted anyway, because a guarantee that is not checked is a
            # comment (hard-won law 1).
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-090",
                message_key="customers.account.not_found",
                params={"account_no": str(account_no)},
            )
        before = selectors.account_detail_dict(account)
        new_status = cleaned.pop("status", None)
        if new_status is not None and new_status.pk != account.status_id:
            _apply_status_change(account, new_status, warnings=warnings)
        fields: list[str] = []
        for field, value in cleaned.items():
            if field in ("unit", "account_type"):  # create-only, never re-imported
                continue
            if field == "custom_data":
                # `DEF-MET-9239` — the file's own-field columns are ADDED to
                # the answers already held (a clerk's, an earlier file's),
                # never a replacement of them: the assets and premises imports'
                # rule. A blank cell never reaches here, so nothing is cleared.
                value = {**(account.custom_data or {}), **(value or {})}
            if getattr(account, field, None) != value:
                setattr(account, field, value)
                fields.append(field)
        if new_status is not None:
            account.status = new_status
            fields.append("status")
        if fields:
            account.save(update_fields=[*dict.fromkeys(fields), "updated_at"])
        _audit(
            actor,
            "account.updated_by_import",
            account.id,
            before=before,
            after=selectors.account_detail_dict(account),
        )
    return {
        "id": str(account.id),
        "account_no": account.account_no,
        "changed": [*dict.fromkeys(fields)],
        "warnings": warnings,
    }


def rollback_from_import(actor: Any, account_id: Any, *, run_no: str | None = None) -> str:
    """Reverse ONE account an import run created — B18 §5.9.4's rollback, and
    the law underneath its *"30 days · unbilled accounts only"* callout.

    Returns the outcome the runner counts on its receipt:

      * ``"reversed"`` — the account is CLOSED as of the tenant's today and its
        opening buckets are removed. Closed, never deleted: BR-CUS-030 makes
        closing an account a flow rather than a status flip, an `audit_log` row
        already names its creation (rule 7), and a corrected re-import must be
        able to address the unit again.
      * ``"kept_billed"`` — an invoice has been ISSUED against it, so the
        account is KEPT exactly as it stands and reported by name. **This is
        hard rule 4, not a policy:** there is no lawful way to delete an issued
        invoice, so there is no lawful way to un-create the account it was
        issued to. The 30-day window in the UI is a courtesy; THIS is the rule,
        and it holds on day one as firmly as on day thirty.
      * ``"missing"`` — the recorded id no longer resolves; reported, never
        invented around.

    ⛔ **AND ONE THING IT WILL NOT DO — OQ-352.** An account whose OPENING
    BALANCES were posted (it carries `AccountOpeningBucket` rows, and those
    rows exist only where `apps.ledger.opening_balances` wrote a balanced
    opening entry against them) is NOT reversed here, because deleting the
    buckets while hard rule 4 keeps the journal entry alive leaves the books
    asserting receivables — GT-16's **267.30** on `A-12103` — for an account
    that no longer trades, and breaks BR-LED-007's tie-out with nothing in the
    product reporting it. **No signed document states the reversing entry or
    its date** (BR-CUS-049's *"corrections via J6 only"* is the BILL-correction
    journey), so this refuses by name rather than choosing. The importer
    refuses the whole run earlier and for the same reason; this is the
    BOUNDARY guard, so a future caller cannot reach the delete below by
    another door.

    ⚠ **THE BILLED CHECK READS BILLING THROUGH ITS OWN SEAM, and a `None` from
    that seam is NOT "no bill" (DEF-075's whole lesson).** `last_issued_invoice_date`
    resolves `apps.billing.selectors`; if billing cannot answer at all, this
    refuses to reverse and reports `kept_billed` — the safe direction, because
    keeping an account that could have been reversed costs a support call and
    reversing one that carries an issued bill corrupts the books.
    """
    account = models.Account.objects.filter(pk=account_id).first()
    if account is None:
        return "missing"

    if models.AccountOpeningBucket.objects.filter(account_id=account.id).exists():
        # ⛔ OQ-352 — see the ⛔ block above. Checked BEFORE the billed read so
        # the answer cannot depend on which module is reachable.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref=OQ_ROLLBACK_OPENING,
            message_key="metering.import.rollback_opening_unruled",
            params={"oq": OQ_ROLLBACK_OPENING},
        )

    billed = seams.last_issued_invoice_date(account.id)
    if billed is not None:
        return "kept_billed"
    if not seams.billing_can_answer():
        # Cannot prove it is unbilled ⇒ treat it as billed. See the ⚠ above.
        return "kept_billed"

    with transaction.atomic():
        models.AccountOpeningBucket.objects.filter(account_id=account.id).delete()
        account.closed_at = seams.tenant_today()
        account.save(update_fields=["closed_at", "updated_at"])
        _audit(
            actor,
            "account.reversed_by_import",
            account.id,
            # `_audit` carries who/when/before→after; the RUN is the "why", and
            # it goes in `after` rather than inventing a parameter the writer
            # does not have (BE-03's shape is shared by every module).
            after={"run_no": run_no, "closed_at": str(account.closed_at)},
        )
    return "reversed"


def confirm_opening_changeover(**kwargs: Any) -> dict[str, Any] | None:
    """The seam implementer for `metering.seams.confirm_opening_changeover` —
    CR-046 C4 / the PO's changeover ruling of 2026-08-27. Re-dates a HELD
    opening batch to the operator's real date and posts it, once.

    Re-exported here for the same two reasons the three below are: `resolve`
    looks a name up on THIS module, and G20 asserts every documented seam has
    an implementer."""
    from apps.customers import import_writer

    return import_writer.confirm_opening_changeover(**kwargs)


def post_opening_batch_from_import(**kwargs: Any) -> dict[str, Any] | None:
    """US-CUS-022 — the BR-CUS-049 handoff, once per run.

    A pass-through to `import_writer`, which owns the contract composition. It
    exists as a named service function because that is what the seam resolves
    (`resolve("customers", "post_opening_batch_from_import")`) and because the
    boundary is worth being able to point at: customers asks, **the ledger
    writes the journal lines** (hard rule 5).
    """
    from apps.customers import import_writer

    return import_writer.post_opening_batch_from_import(**kwargs)


def link_customer(
    *,
    account_id: Any,
    external_ref: str | None = None,
    display_name: str | None = None,
    kind: str | None = None,
    identity: Any = None,
    customer_id: Any = None,
    customer_no: Any = None,
    actor: Any = None,
    custom_data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """BR-CUS-054 — the first-class `customers` entity and its
    `customer_accounts` link.

    **This was a `NotImplementedError("BR-CUS-054")` stub until 2026-08-11**,
    and the reason it gave was true: B2 §2 carried no column list. It carried
    one all along in r9 #1 — *"`customers` (kind person|company, display_name,
    external_ref UNIQUE per tenant) + `customer_accounts` N:M link"* — and
    migration 0005 builds exactly that. The stub is retired rather than left
    beside a live table (a stub whose gap has closed is a lie with a rule id
    on it).

    THE MATCHING RULE, stated because it is the landlord case (US-CUS-019
    TC-2): one distinct `external_ref` = ONE `customers` row. A ref that
    matches an existing tenant customer LINKS to it and does not duplicate; a
    ref that matches nothing creates one. Tenant-scoped by construction —
    US-CUS-019 TC-8's cross-tenant file finds nothing to link to.

    A row with NO customer_ref and NO name links nothing and returns None: an
    account can exist without a customer entity (every account created before
    this table did), and inventing a customer named after nobody would put junk
    in the master list the S17 search reads.

    What this deliberately does NOT do: re-home `contacts` onto the customer
    row (r9 #1 calls that an Eng-Lead disposition).

    ══════════════════════════════════════════════════════════════════════
    CR-056 W3 — THIS RAN ONLY INSIDE AN IMPORT, AND NOW EVERY DOOR CALLS IT
    ══════════════════════════════════════════════════════════════════════
    CR-056 §4, verbatim: *"Exactly one function writes a customer-to-account
    link and it runs only inside an import. **Every Master Account in the
    product has a blank customer column**, and an account opened at the counter
    shows a dash where its number should be."* That was measured, not guessed —
    the only two callers were `_commit_import_row` and `create_from_import`.

    Three things joined the signature, and each closes one half of that:

      * **`identity`** — an `identity_match.IdentityEvidence` or the payload
        block it is built from. Where it is present the RETURNING CUSTOMER is
        recognised instead of a second one being created (task 13).
      * **`customer_id`** — the clerk's own answer. *"This is that person"*,
        chosen from the advisory candidates, which is `BR-CUS-019`'s ADVISORY
        posture (*staff decides; matches resolve by LINKING*) built rather than
        described.
      * **`customer_no`** — OUR number, quoted by the operator's own file
        (`CR-058` W7 / `DEF-2593`). A number already on file LINKS to that
        customer; a free one is used INSTEAD of allocating, so a utility keeps
        the numbers it migrated with. ⚠ **It is a KEY and never evidence:** it
        contributes nothing to `BR-CUS-1023`'s minimum, because it names a ROW
        and does not identify a PERSON — the same line `external_ref` sits on.
      * **`actor`** — because `BR-CUS-089` stores the tier WITH ITS CONFIRMER
        and the confirmer is a person. An unattended call records no tier at
        all, which refuses the deposit carry-forward, which is the safe
        direction.

    ⚠ **WHAT A `strong` MATCH DOES AND DOES NOT DO.** It links the account to
    the customer already on file and records `match_tier='strong'` with the
    basis and the confirmer, which is what lets `discounts.carry_forward_offer`
    carry a returning customer's deposit (WE-7/GT-23 ❄️: **$150.00** principal +
    **$3.50** interest = **$153.50**). It moves no money here — this function
    posts nothing and touches no `deposit_on_file`.

    ⚠ **AND A WEAK MATCH REFUSES BY NAME RATHER THAN LINKING.** Where somebody
    on file looks related but the three signed criteria do not all agree, the
    new account is opened under **its own** customer number, the candidates ride
    back on `match.candidates` for a human to look at, and NOTHING is merged.
    Both rules get what they ask for: `BR-CUS-019` is advisory so nothing is
    blocked, and `BR-CUS-089` moves money only on `strong` so nothing is joined
    on a guess. `identity_match.WEAK_MATCH_REFUSAL` is the sentence a screen
    shows.

    ⚠ **THE IMPORT PATH IS UNCHANGED AND MUST STAY THAT WAY.** It passes no
    `identity` and no `actor`, so it matches on `external_ref` exactly as it
    did — the LEGACY system's id, a reconciliation key, not identity evidence.
    A spreadsheet column may not earn a `strong` tier; the tier stays NULL and
    the carry-forward keeps refusing.

    ══════════════════════════════════════════════════════════════════════
    CR-056 W2b — `kind` STOPS BEING DECORATION AND STARTS DECIDING THINGS
    ══════════════════════════════════════════════════════════════════════
    **PO ruling 2026-09-01, verbatim:** *"Customer can be person or company - in
    case of person , if we have SSN, or DL or Phone number, we create the
    Customer ID and attached these to custoemr ID ; if it is Company then we ask
    for Tax ID"*. `kind` was already a parameter and already a column, and until
    today NOTHING read it: it fell through to `"person"` inside the create and
    no rule cared. Now it selects which identifier is captured and which test a
    match is judged on (`BR-CUS-1022`).

    **THE JUDGMENT THIS LANE MADE, and it is recorded in the decision log of
    2026-09-01 rather than only here — REFUSE THE IDENTITY, NEVER THE ACCOUNT:**

      * **Identity presented with NO kind → REFUSED by name.** A government
        identifier filed under a party nobody has classified is the money
        hazard: it is stored where the matcher for the other kind never looks,
        and a guess of `person` would judge a business by a date of birth it
        does not have.
      * **No identity presented → the account opens, and the kind falls back to
        `person`** — the bulk import matching on a legacy reference, the
        master-account door carrying a premises owner's name. **The fallback is
        WRITTEN here and recorded in the audit row rather than arriving
        invisibly from the model's column default**, which is the half of
        *"a silent default is wrong"* that could actually be fixed without
        breaking every spreadsheet a utility already holds.

    **WHY THE SPLIT AND NOT A BLANKET REFUSAL:** the PO's OTHER ruling of the
    same day. *A duplicate identifier refuses to LINK and never refuses to
    SAVE* — a clerk who mistypes a digit must still be able to open the account.
    Refusing to open one over a missing dropdown is the same one-way door in a
    different coat.

    ══════════════════════════════════════════════════════════════════════
    CR-056 W6 — A NAME ALONE NO LONGER CREATES A NUMBER (`BR-CUS-1023`)
    ══════════════════════════════════════════════════════════════════════
    **PO ruling 2026-09-01, verbatim:** *"Customer ID - minimum name and one ID
    - minimum - please make this rule and apply"*.

    | kind | enough to CREATE a Customer # |
    |---|---|
    | **person** | a name **AND** (SSN **or** driving licence **or** phone) |
    | **company** | a name **AND** its Tax ID |

    ⚠ **THE MINIMUM GATES THE `create` BRANCH AND NOTHING ELSE.** A clerk's
    named `customer_id`, a matching `external_ref` and a `strong` identity match
    all reach a row that already exists, and none of them consults it. The rule
    is about MINTING a number, not about recognising one.

    ⚠ **IT SKIPS; IT NEVER RAISES.** Every caller is inside the door's own
    transaction, so an exception would roll the ACCOUNT back and fuse the two
    outcomes the ruling separates. A door that presents less than the minimum
    gets its account, its contact and its address, and a `not_created` block
    naming the one thing that was missing. See the comment at the create.

    ⛔ **SUPERSEDED AT ONE CLAUSE THE SAME DAY — PO 2026-09-01, verbatim:
    *"Without identifier we cannot create Customer ID or master account ot
    regular account"*.** The paragraph above about the account still opening is
    REVERSED: the identifier now gates **the account** and not the Customer #
    alone, so a name alone creates NOTHING at all. **The minimum below is
    unchanged and is the predicate that ruling needs** — only its consequence
    moved, from *no number* to *no row*. **The account-level refusal is NOT
    BUILT HERE**: it belongs to the lane that recorded the ruling, and it
    carries a migration-blocking half that lane's own record says must reach the
    PO first (the bulk import could then create no accounts at all). Decision
    log 2026-09-01, *AND NO IDENTIFIER MEANS NO ACCOUNT EITHER*.

    ⚠ **WHAT IS ENOUGH TO CREATE IS NOT WHAT IS ENOUGH TO MATCH.** A **phone
    alone CREATES** (the PO named it) and a **phone alone is a WEAK match that
    carries no deposit** (`BR-CUS-089`). Both are true at once and a lane that
    reconciles them either refuses a customer the PO said to create or moves
    **$150.00** on a telephone number. `CREATE_IDENTIFIER_FIELDS` and
    `tier_for` are deliberately two tables for that reason.
    """
    ref = _text(external_ref, 120)
    name = _text(display_name, 200)
    stated_kind = identity_match.normalise_kind(kind)
    evidence = (
        identity
        if isinstance(identity, identity_match.IdentityEvidence)
        else identity_match.from_payload(identity, kind=stated_kind)
    )
    if not evidence.name:
        evidence = replace(evidence, name=name)
    if evidence.kind is None and stated_kind is not None:
        evidence = replace(evidence, kind=stated_kind)
    # CR-056 W2b — the second lock, for in-process callers that build an
    # `IdentityEvidence` by hand and never pass through the door's validator.
    # `identifiers()` already returns nothing for an unstated kind, so this
    # refuses LOUDLY instead of behaving like an empty evidence set.
    if stated_kind is None and evidence.identifiers():
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.customer.kind_required_for_identity",
            params={"field_name": sorted(evidence.identifiers())[0]},
        )
    tenant_id = _tenant_id()

    # ⛔ **CR-058 W7 / `DEF-2593` — THE OPERATOR'S OWN CUSTOMER NUMBER.**
    # The accounts template has published a `Customer #` column since CR-030
    # W0, auto-mapped it, reported it `Matched` at stage 2 and then dropped it:
    # a utility migrating with its own customer numbers lost every one and
    # could not reconcile against their old system (`BR-CUS-1042`).
    quoted_no = _text(customer_no, 120)

    # ── the clerk's explicit answer wins over everything (BR-CUS-019) ──────
    named_customer = None
    if customer_id not in (None, ""):
        named_customer = models.Customer.objects.filter(tenant_id=tenant_id, id=customer_id).first()
        if named_customer is None:
            # 404-never-403: from outside the tenant an id that exists
            # elsewhere and an id that does not exist are the same fact (HR-1).
            raise errors.deny_as_not_found("BR-TEN-003")

    verdict: dict[str, Any] | None = None
    if named_customer is None and evidence.has_any():
        verdict = identity_match.recognise(evidence)

    if (
        not ref
        and not name
        and not quoted_no
        and named_customer is None
        and not (verdict and verdict["matched"])
    ):
        return None

    customer = named_customer
    if customer is None and quoted_no:
        # ⛔ **OUR NUMBER IS AN EXACT KEY AND IS TRIED BEFORE THE MATCHER.**
        # An operator writing `C-00417` in a cell is naming a specific customer
        # — the strongest statement available short of a clerk clicking one —
        # and `_key_of` takes the same view of `account_no` for the same reason.
        # Case-insensitive, because `C-00417` and `c-00417` are one customer in
        # any legacy export (`uq_customers_tenant_customer_no_ci`).
        # ⚠ **A number that resolves to NOBODY is not an error and is not
        # discarded**: it is FREE, and it is used at the create below. That is
        # the whole of `DEF-2593` — the utility keeps the numbers it migrated
        # with instead of being renumbered by us.
        customer = models.Customer.objects.filter(
            tenant_id=tenant_id, customer_no__iexact=quoted_no
        ).first()
    if customer is None and verdict is not None and verdict["matched"]:
        customer = models.Customer.objects.filter(
            tenant_id=tenant_id, id=verdict["matched"]
        ).first()
    if customer is None and ref:
        customer = models.Customer.objects.filter(
            tenant_id=tenant_id, external_ref__iexact=ref
        ).first()
    # ══════════════════════════════════════════════════════════════════════
    # `BR-CUS-1024` — MATCH FIRST. AN EXACT NAME + GOVERNMENT ID REUSES THE
    # NUMBER ALREADY ON FILE INSTEAD OF MINTING A SECOND ONE.
    # ══════════════════════════════════════════════════════════════════════
    # PO 2026-09-01 (`CR-058` ruling 0), verbatim: *"During regular and master
    # account creation process - we check whether we ahve mathicng customer ID,
    # if yes, we use it if no we create it, given we have identify atleast 1"*.
    #
    # ⚠ **THIS IS A THIRD TEST AND NOT A LOOSENING OF `BR-CUS-089`.** The branch
    # above already linked on a `strong` verdict, which is the MONEY test and
    # needs a date of birth for a person. This one asks a different question —
    # *does this number already exist* — and its answer changes only how many
    # rows there are. `tier` below is still taken from `verdict` alone, so a
    # reused row records NO tier and NO confirmer and
    # `discounts.carry_forward_offer` still refuses: **$0.00** moves.
    #
    # ⚠ **MEASURED, `DEF-2587`.** Without this branch a landlord giving a name
    # and a Social Security number at three buildings — an identifier, which is
    # exactly what the ruling asks for — was written as `C-00001`, `C-00002` and
    # `C-00003`: three customers over one Social Security number. The matcher had
    # FOUND the earlier row each time and reported *matched on name and Social
    # Security number*; nothing read that answer.
    reused = False
    if customer is None:
        reuse = identity_match.reuse_candidate(evidence)
        if reuse["customer"] is not None:
            customer = reuse["customer"]
            reused = True
    if customer is None:
        # ══════════════════════════════════════════════════════════════════
        # `BR-CUS-1023` — THE MINIMUM TO **MINT** A NUMBER, AND IT IS A SKIP
        # ══════════════════════════════════════════════════════════════════
        # PO 2026-09-01, verbatim: *"Customer ID - minimum name and one ID -
        # minimum - please make this rule and apply"*. A name alone no longer
        # creates a Customer #.
        #
        # ⛔ **IT IS STILL A SKIP AND NOT A RAISE — but the REASON printed here
        # until 2026-09-01 is SUPERSEDED, and it is quoted rather than deleted
        # so nobody restores it.** It read: *"fusing the two outcomes the PO
        # separated in as many words: An account may still be opened. This rule
        # is about the CUSTOMER #, not about service: a person standing at the
        # counter who will not give an identifier still gets their water."*
        # **PO verbatim, later the same day:** *"Without identifier we cannot
        # create Customer ID or master account ot regular account"*. The two
        # outcomes are now deliberately FUSED at the doors a clerk presses
        # (`BR-CUS-1024`).
        #
        # **The skip survives the reversal for a different and still-true
        # reason: WHERE the refusal lives.** Every caller of this function runs
        # inside the door's own `transaction.atomic()`, so an exception HERE
        # would roll an account back mid-write. The gated doors therefore refuse
        # BEFORE they open the transaction (`refuse_account_without_identity`),
        # and by the time this line is reached the caller is one that is NOT
        # gated — the bulk import (whose identity columns the PO ruled for on
        # 2026-09-01 and whose lane owes them) and the tenant sample seed. A
        # later lane that "tidies" this into a `BizError` will take a utility's
        # cutover down before those columns exist, and every test that only
        # asserts a refusal will still pass.
        #
        # ⚠ **IT GATES CREATION ONLY.** Every branch above — the clerk's named
        # customer, a matching `external_ref`, a `strong` identity match — has
        # already found a row, and none of them reaches here. Applying the
        # minimum to a LINK would refuse to recognise exactly the customers the
        # rule exists to protect.
        #
        # ⚠ **AND NOTHING IS INVENTED TO GET PAST IT.** No placeholder phone, no
        # zero Tax ID, no account number reused as an identifier: *"a filled
        # column that means nothing is worse than an empty one, because the
        # matcher will read it."*
        #
        # The old `display_name_required` refusal lived here and is FOLDED IN
        # rather than deleted: a ref with no name is one of the three things
        # this can be missing, its sentence is unchanged and still shown, and it
        # now skips the number instead of failing the whole import row.
        shortfall = identity_match.creation_minimum(evidence)
        if shortfall is not None:
            not_created = identity_match.not_created_payload(shortfall)
            # CLAUDE.md rule 7 — the decision NOT to mint a number gates a
            # deposit carry-forward exactly as a weak match does, and a refusal
            # that leaves no trace is a customer nobody can account for. The
            # blob names the account, never an identifier (BR-CUS-092(c)) — and
            # there is no `customer.id` to key on, so the ACCOUNT is the entity.
            core_audit.write_row(
                action="customer.not_created",
                entity_type="account",
                entity_id=account_id,
                actor_user_id=_actor_id(actor),
                before=None,
                after={
                    "display_name": name,
                    "external_ref": ref,
                    "kind": shortfall["kind"],
                    **not_created,
                },
            )
            return {
                "id": None,
                "customer_no": None,
                # Nothing was created and nothing was reused. Both keys are
                # present on EVERY return of this function so a caller never has
                # to ask whether the shape it got is the short one.
                "created": False,
                "reused": False,
                "kind": shortfall["kind"],
                # Nothing was created, so nothing fell back to `person`. A
                # `True` here would say a default was taken when no row exists.
                "kind_defaulted": False,
                "display_name": name,
                "external_ref": ref,
                "match": None,
                # ⚠ **hard-won law 2 — the door RETURNS this or the clerk never
                # learns it.** A skip nobody can see is the blank customer
                # column CR-056 §4 was written to close, wearing a rule id.
                "not_created": not_created,
            }
        customer = models.Customer.objects.create(
            tenant_id=tenant_id,  # noqa: E501 — see `created` in the return
            # CR-030 W0 — allocated INSIDE the create, so a customer never
            # exists unnumbered even for the width of a transaction. ⚠ CR-056
            # W3 task 16 gives this line four more callers (the S18 wizard, the
            # master-account door, the S19 move-in and the service-request
            # path) and it stays exactly where it is: the number is allocated
            # INSIDE the create, so no door can produce an unnumbered customer.
            # ⛔ **CR-058 W7 / `DEF-2593` — THE FILE'S OWN NUMBER WHERE IT GAVE
            # ONE, THE SERIES WHERE IT DID NOT.** `BR-TEN-035`'s principle, the
            # same one that made the account number come off the file: the side
            # that owns the identifier issues it, and a customer number is on
            # every letter the utility has already sent. The allocation stays
            # INSIDE the create either way, so no door can produce an unnumbered
            # customer.
            customer_no=(quoted_no or _allocate_customer_no()),
            # ⚠ **CR-056 W2b — THE KIND IS WRITTEN HERE, NEVER INHERITED FROM
            # THE COLUMN DEFAULT.** `models.Customer.kind` still declares
            # `default="person"` for the rows that predate this ruling, and a
            # door that reached the create without stating one used to pick it
            # up invisibly. It is stated explicitly now and `kind_defaulted`
            # below records that nobody said so, which is the difference
            # between a default and a silent default.
            kind=(stated_kind or identity_match.KIND_PERSON),
            display_name=name,
            external_ref=ref,
            # CR-161-BRC10 W4 — the answers the New Account wizard collected,
            # ALREADY validated by `_validate_customer_block`.
            custom_data=dict(custom_data or {}),
        )
        created = True
        kind_defaulted = stated_kind is None
    else:
        created = False
        kind_defaulted = False

    # ── the presented identity lands on the customer (task 11 · task 13) ────
    # FILLS EMPTY COLUMNS ONLY. Correcting an identifier already on file is a
    # different act with a different audit story — somebody is asserting the
    # stored value is wrong — and it is not a side effect of opening an
    # account. `apply_evidence` writes each ciphertext and its blind index
    # together, so a value the matcher cannot see can never be stored.
    filled = identity_match.apply_evidence(customer, evidence)
    if filled:
        customer.save(update_fields=[*_identity_columns(filled), "updated_at"])
    if custom_data and not created:
        # CR-161-BRC10 W4 — a RETURNING customer: what the clerk typed on the
        # wizard lands on the customer already on file. Only answered keys move
        # (a blank on a fresh form means "not asked", never "clear it"), the
        # same fill-don't-wipe posture `apply_evidence` takes one line up.
        merged = {**dict(customer.custom_data or {}), **{
            key: value for key, value in custom_data.items() if value not in (None, "", [])
        }}
        if merged != dict(customer.custom_data or {}):
            customer.custom_data = merged
            customer.save(update_fields=["custom_data", "updated_at"])

    tier = None
    basis = None
    if verdict is not None and verdict["matched"] and str(customer.id) == verdict["matched"]:
        # BR-CUS-089 — the tier and its confirmer are STORED. The confirmer is
        # the human at the door; an unattended call records no tier, which
        # refuses the deposit carry-forward rather than defaulting it.
        tier = verdict["tier"]
        basis = verdict["basis"]

    link, _ = models.CustomerAccount.objects.get_or_create(
        tenant_id=tenant_id, customer=customer, account_id=account_id
    )
    actor_id = _actor_id(actor)
    if tier is not None and link.match_tier is None:
        link.match_tier = tier
        link.match_basis = basis
        link.match_confirmed_by_id = actor_id
        link.match_confirmed_at = timezone.now()
        link.save(
            update_fields=[
                "match_tier",
                "match_basis",
                "match_confirmed_by",
                "match_confirmed_at",
            ]
        )

    match: dict[str, Any] | None = None
    if verdict is not None:
        match = {
            "tier": tier,
            "basis": basis,
            "refusal": verdict["refusal"],
            "candidates": verdict["candidates"],
            "recognised": bool(tier),
        }
        match["reused"] = reused
        if verdict["refusal"] == identity_match.REFUSAL_NOT_STRONG and not reused:
            # CR-056 W2b — the wording follows the kind, because the TEST does.
            # Telling a clerk a business failed a date-of-birth test would send
            # them to find a fact that does not exist.
            #
            # ⚠ **AND IT IS WITHHELD ON A REUSE, BECAUSE THE SENTENCE WOULD BE
            # FALSE (`BR-CUS-1024`).** Both wordings end *"The new account has
            # been opened under its own customer number and nothing has been
            # merged"* — which is exactly what did NOT happen when the name and
            # a government identifier agreed and the existing number was reused.
            # The tier is still weak and no deposit still moves; what changed is
            # that there is no second number to apologise for.
            match["unavailable"] = [identity_match.weak_match_refusal(customer.kind)]
        # CLAUDE.md rule 7 — a recognition decision GATES a deposit, so both
        # the recognition and the refusal write `audit_log`. A refusal is the
        # decision that a returning customer's money stayed where it was; a
        # refusal that left no trace is a figure nobody can reconcile. The blob
        # carries `customer_no` and last-four projections only, never a full
        # identifier (BR-CUS-092(c)).
        core_audit.write_row(
            action=("customer.identity_recognised" if tier else "customer.identity_not_recognised"),
            entity_type="customer",
            entity_id=customer.id,
            actor_user_id=actor_id,
            before=None,
            after={
                "account_id": str(account_id),
                "customer_no": customer.customer_no,
                "created": created,
                # CR-056 W2b — WHICH TEST WAS APPLIED, and whether anybody said
                # so. A `weak` verdict is unreadable a month later without it.
                "kind": customer.kind,
                "kind_defaulted": kind_defaulted,
                "identity_filled": filled,
                **match,
            },
        )

    return {
        "id": str(customer.id),
        # ⚠ **`created` LEFT THIS FUNCTION ONLY AS AN AUDIT BLOB UNTIL
        # 2026-09-01, AND THAT IS WHY NO SCREEN COULD SAY WHAT HAPPENED.** The
        # server knew whether it had linked or created and never told anybody:
        # `CR-058` tasks 7 and 8 ask both wizards to show the clerk which of the
        # three things happened, and neither could, because the one fact that
        # separates *linked* from *created* was written to `audit_log` and
        # dropped from the response. Hard-won law 2 in its purest form — a fact
        # no caller can read is a fact that does not exist for the user.
        "created": created,
        # `BR-CUS-1024` — TRUE when an exact name + government-identifier
        # agreement reused a number already on file rather than minting one. It
        # is a LINK, so `created` is False beside it; it is reported separately
        # because a clerk is owed *"this looks like a customer you already
        # have"* rather than silence.
        "reused": reused,
        # CR-030 W0. Returned, not merely stored: hard-won law 2 — a column no
        # caller can read is a column that does not exist for the user.
        "customer_no": customer.customer_no,
        # ⛔ **CR-058 W7 — MATCHED OR CREATED, SAID OUT LOUD.** The import
        # receipt has to tell a utility how many people this file JOINED to
        # customers it already held and how many it brought in new; one figure
        # covering both cannot tell a re-run from a first load. It was already
        # computed here and thrown away.
        "created": created,
        # ⛔ **AND WHETHER THE NUMBER CAME OFF THE FILE**, which is what the
        # caller needs to walk the `customer` series past it (`DEF-577`'s
        # arithmetic, on the second series `DEF-2593` opened).
        "customer_no_from_file": bool(created and quoted_no),
        "kind": customer.kind,
        # CR-056 W2b — TRUE when this door created the row and nobody stated a
        # kind. A screen can say *"opened as a person"* instead of implying
        # somebody chose it.
        "kind_defaulted": kind_defaulted,
        "display_name": customer.display_name,
        "external_ref": customer.external_ref,
        "match": match,
    }


#: `apply_evidence` answers in FACT names; `save(update_fields=…)` needs COLUMN
#: names, and the two differ for every encrypted identifier because each writes
#: a ciphertext AND its blind-index twin. Getting this wrong writes the token
#: and drops the value, or the other way round — either of which is a customer
#: the matcher can see and nobody can read, or one nobody can find.
def _actor_id(actor: Any) -> Any:
    """The acting person's id, or None for an unattended call.

    `BR-CUS-089` stores the identity-match tier WITH ITS CONFIRMER, and the
    confirmer is a human. `None` here is therefore not a tidy default — it is
    the honest statement that nobody looked, and it is why an unattended call
    that reached a `strong` verdict still records no confirmer.
    """
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _identity_columns(filled: list[str]) -> list[str]:
    columns: list[str] = []
    for fact in filled:
        columns.append(fact)
        twin = identity_match.BIDX_COLUMN.get(fact)
        if twin:
            columns.append(twin)
    return columns


# `move_in` (BR-CUS-024) and `move_out` (BR-CUS-030) WERE stubs here. They are
# implemented above in slice 3 — the parts of their rules that have somewhere to
# be written — and every part that does not is a named entry in
# MOVE_IN_UNAVAILABLE / MOVE_OUT_UNAVAILABLE rather than a stub the write path
# never calls.


# ═══════════════════════════════════════════════════════════════════════════
# S22 — ADD NOTE (US-CUS-015 · BR-CUS-035)
#
# The one S22 modal that writes a customers table. Everything else on that rail
# hands off (BR-CUS-037), and three of the seven have nowhere to hand off TO —
# see ACTION_UNAVAILABLE below.
# ═══════════════════════════════════════════════════════════════════════════
NOTE_FIELDS = frozenset({"title", "body", "pinned", "customer_visible"})


def _note_or_404(account: models.Account, note_id: Any) -> models.AccountNote:
    """The note, inside this tenant AND on this account.

    Both halves matter. RLS already scopes the tenant; the ACCOUNT check is what
    stops `/accounts/A/notes/<a note of account B>` editing a stranger's row
    under a URL that looks legitimate — HR-1's "absent, never forbidden".
    """
    if not isinstance(note_id, (str, UUID)) or str(note_id).strip() == "":
        raise errors.NotFoundError()
    row = models.AccountNote.objects.filter(
        tenant_id=_tenant_id(), account=account, pk=str(note_id)
    ).first()
    if row is None:
        raise errors.NotFoundError()
    return row


def _clean_note(payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
    """US-CUS-011 TC-7: title OR body is required — a note with neither is not
    a note, it is a timestamp.

    Checked here rather than in the database because the refusal has to say
    WHICH field to fill, and a CHECK constraint can only say the row is wrong.
    """
    _reject_unknown(payload, NOTE_FIELDS)
    cleaned: dict[str, Any] = {}
    if "title" in payload or not partial:
        cleaned["title"] = _text(payload.get("title"), 200)
    if "body" in payload or not partial:
        cleaned["body"] = _text(payload.get("body"), 4000)
    if "pinned" in payload:
        cleaned["pinned"] = _bool(payload.get("pinned"))
    if "customer_visible" in payload:
        # BR-CUS-035: STORED and INERT. Nothing reads it in v1 — the portal is
        # out of scope — and nothing may treat it as a permission.
        cleaned["customer_visible"] = _bool(payload.get("customer_visible"))
    if not partial and not (cleaned.get("title") or cleaned.get("body")):
        _refuse_fields(
            [
                _field_error("title", errors.VAL_REQUIRED, "customers.note.title_or_body_required"),
                _field_error("body", errors.VAL_REQUIRED, "customers.note.title_or_body_required"),
            ]
        )
    return cleaned


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-IDN-009")
def create_account_note(actor: Any, account_id: Any, payload: Any) -> dict[str, Any]:
    """US-CUS-015 TC-4 / US-CUS-011 TC-3 — write one `account_notes` row.

    Audited as `note.created` (BR-CUS-035 "IS-1 audited"). A note is not a money
    action, so hard rule 7 does not compel this row; IS-1 does, and the reason is
    the same one the rule gives everywhere else — a note is evidence in a
    dispute, and evidence with no author and no timestamp is not evidence.
    """
    from apps.customers import selectors as customers_selectors

    data = _payload_dict(payload)
    cleaned = _clean_note(data, partial=False)
    account = customers_selectors.account_or_404(account_id)
    with transaction.atomic():
        note = models.AccountNote.objects.create(
            tenant_id=_tenant_id(),
            account=account,
            author_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            title=cleaned.get("title"),
            body=cleaned.get("body"),
            pinned=bool(cleaned.get("pinned", False)),
            customer_visible=bool(cleaned.get("customer_visible", False)),
        )
        row = customers_selectors.note_dict(note)
        _audit(actor, "note.created", note.id, entity_type="account_note", after=row)
    return row


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-IDN-009")
def update_account_note(actor: Any, account_id: Any, note_id: Any, payload: Any) -> dict[str, Any]:
    """Pin, unpin or correct a note — audited with the whole row before→after
    (BR-AUD-003), which is what makes an edit reviewable rather than silent."""
    from apps.customers import selectors as customers_selectors

    data = _payload_dict(payload)
    cleaned = _clean_note(data, partial=True)
    account = customers_selectors.account_or_404(account_id)
    with transaction.atomic():
        note = _note_or_404(account, note_id)
        before = customers_selectors.note_dict(note)
        for field_name, value in cleaned.items():
            setattr(note, field_name, value)
        if not (note.title or note.body):
            _refuse_fields(
                [
                    _field_error(
                        "title", errors.VAL_REQUIRED, "customers.note.title_or_body_required"
                    )
                ]
            )
        note.save(update_fields=[*cleaned.keys(), "updated_at"])
        after = customers_selectors.note_dict(note)
        _audit(
            actor, "note.updated", note.id, entity_type="account_note", before=before, after=after
        )
    return after


# ═══════════════════════════════════════════════════════════════════════════
# THE S22 ACTIONS THIS DEPLOYMENT CANNOT HONOUR — named, with their reasons
#
# BR-CUS-037 makes every one of these an ENTRY POINT into another module's
# service. Four of those services do not exist, and three of the rules behind
# them are unruled. Each is a dict rather than a sentence because the SCREEN
# renders the reason on the disabled control (BR-SHL-025) and a screen cannot
# group on prose.
# ═══════════════════════════════════════════════════════════════════════════
ACTION_UNAVAILABLE: dict[str, dict[str, Any]] = {
    "adjust": {
        "code": "adjustment_write_path_absent",
        "br_ref": "BR-CUS-037",
        "oq_ref": None,
        "detail": (
            "An adjustment is a NEW row on billing's `adjustments` table and billing publishes "
            "no writer for it — `apps.billing.services` exports the late fee and nothing else. "
            "The approval gate (BR-CUS-038) and the GL coding have nowhere to land either."
        ),
    },
    # ══════════════════════════════════════════════════════════════════════
    # ⚠ THREE ENTRIES LEFT THIS MAP ON 2026-09-07 (`DEF-CUS-4631`) BECAUSE THE
    # ACTIONS ARE NOT UNAVAILABLE — `issue_credit`, `print_bill` and
    # `disconnect_notice`.
    # ══════════════════════════════════════════════════════════════════════
    # The PO read S21 and asked why the icons were dead: *"in account - view we
    # have all those icons - can you activate them now"*, then *"activate all of
    # them"*. Each of the three was refusing on work that had since been
    # finished, and each refused for a DIFFERENT wrong reason, which is why they
    # were never fixed together:
    #
    #   · `issue_credit` said the goodwill DEBIT account *"has not been
    #     decided"*. `OQ-105`/`OQ-168` closed 2026-08-12 — *"a separate write-off
    #     account"* — and `corrections.credit_only_gl_accounts` has resolved it
    #     BY DESIGNATION ever since, with `execute_credit_only` posting the pair.
    #     Restated once already on 2026-09-02 to the shape *"a credit note needs
    #     a bill"*, which is TRUE and is not a reason to disable a control: it is
    #     a reason to send the clerk to the bill. S21's `$` glyph now opens the
    #     bill-correction workflow on this account's latest issued bill.
    #   · `print_bill` said *"`GET /invoices/{id}/document` is not mounted, so
    #     nothing can reach it"* and named `OQ-169` as open. The route has been
    #     mounted in `config/urls.py` via `apps.billing.documents_api`, and
    #     `OQ-103`/`OQ-169` both closed 2026-08-12: a later reprint renders THE
    #     CORRECTED instance. Two false clauses in one sentence.
    #   · `disconnect_notice` named `OQ-133`/`OQ-136`/`OQ-137` as open — all
    #     three closed 2026-08-12 — plus two structural gaps that have since been
    #     built: `payments.collections_models.NoticeHistory` IS the
    #     `notice_history` table, and `disconnects.medical_hold_for` IS the
    #     medical-hold read. The whole disconnect ladder is mounted at
    #     `/accounts/{id}/disconnect-case` and its `advance` / `notices` children.
    #
    # ⚠ **THE LESSON IS THE ONE `corrections.py` ALREADY WROTE DOWN AND NOBODY
    # ACTED ON.** On 2026-09-02 it recorded, in as many words, that the expired
    # goodwill sentence *"was quoted in two other places in this product"* — this
    # map and the `customers.account.action.issueCreditBlocked` catalogue string
    # — and both quotes stayed. Writing down where a lie is copied does not
    # remove the copies.
    "send_statement": {
        "code": "statement_renderer_absent",
        "br_ref": "BR-CUS-040",
        "oq_ref": None,
        "detail": (
            "A statement is a dated RANGE LEDGER with the 'nothing is due' disclaimer — a "
            "different document from a bill (A19 rule 1). `apps/billing/documents.py` renders "
            "invoices only, and the B2 r2 account-ledger derived view it would read does not "
            "exist."
        ),
    },
}


def send_disconnect_notice(_actor: Any, _account_id: Any, _payload: Any = None) -> dict[str, Any]:
    """US-CUS-015's disconnect half. **SUPERSEDED — it is not blocked any more.**

    ⚠ **RE-CITED 2026-09-07 (`DEF-CUS-4631`), AND THE OLD CITATION IS THE POINT.**
    This raised `NotImplementedError("OQ-133 / OQ-136 / OQ-137 — …")` and its
    docstring said three blockers were structural — *"no `notice_history`, no
    medical-hold column, no tenant charge-code read for the reconnect fee"* — and
    three were unruled. **Every one of those six statements is now false:**

      · `OQ-133`, `OQ-136` and `OQ-137` all closed on **2026-08-12** (the ladder
        restarts after a bounce; a partial payment pauses it only above a
        tenant-set percentage; the $25.00 floor applies to the whole ladder).
      · `notice_history` IS a table — `payments.collections_models.NoticeHistory`,
        `db_table = "notice_history"`, recording every send AND every skip.
      · the medical hold IS readable — `customers.disconnects.medical_hold_for`,
        published on the runbooks seam and read by `payments.ladder`.
      · the reconnect fee IS read from the tenant's own charge code —
        `disconnects.reconnection_terms`, which answers `None` WITH a reason when
        `CC-RECON` is not configured rather than inventing a number (DEF-700).

    **So there is nothing left for this function to wait for, and it is not the
    path either.** Sending a disconnect notice happens through the mounted
    disconnect-case routes — `POST /accounts/{id}/disconnect-case`, its
    `advance` and `notices` children, and `/disconnects/schedule` — which is
    what `DSC-02`, the five-step wizard, has driven since 2026-08-25. The
    generation itself is `payments.notices.send_disconnect_notices`, queue-first
    per `BR-NOT-005`, and it is payments' to own (r12 #7): a customers-side
    singular sender would be a SECOND door onto a ladder this module does not
    own, which is the prime directive's exact prohibition and the reason
    `apps/notifications/api.py` declined to mint one either.

    It still raises, because it still does nothing — but it no longer claims to
    be waiting on decisions that were made, and it names the door that works.
    Kept rather than deleted so a caller that finds this name is told WHERE to
    go instead of meeting an `AttributeError`.
    """
    raise NotImplementedError(
        "send_disconnect_notice is superseded and writes nothing. A disconnect notice is "
        "a rung on the collection ladder, which payments owns: use POST "
        "/accounts/{id}/disconnect-case and its advance/notices children (the DSC-02 "
        "wizard's own path), or payments.notices.send_disconnect_notices for the bulk "
        "send. Nothing here is blocked on an open question."
    )


# ═══════════════════════════════════════════════════════════════════════════
# S23 — CHANGE PLAN (US-CUS-016 steps 1–2 · US-CUS-017 step 3)
# ═══════════════════════════════════════════════════════════════════════════
#: US-CUS-016 §7's deposit line, and why it is not produced.
#:
#: TWO CONFIRMED RULES DISAGREE ABOUT ONE CUSTOMER-FACING FIGURE.
#:   BR-CUS-042 (CONFIRMED, OQ-011 closure): differential = new category amount
#:     − old category amount; positive billed, negative credited. US-CUS-016 §7
#:     works it as −$50.00 and its net impact as −$68.50.
#:   BR-CUS-062 (CONFIRMED, PO CL-5 option (b), 2026-08-08, "closes the last B4
#:     deposit placeholder"): **no recompute in v1** — the deposit set at move-in
#:     stands until final-bill settlement; the category differential is v1.1.
#: BR-CUS-062 is the later ruling and is corroborated twice independently —
#: 11b §2.6's S23 row reads "deposit NO recompute v1 (BR-CUS-062)", and
#: `apps/rating/proration.py`'s own docstring says the differential is "NOT here
#: and is not missing" for the same reason. That is strong evidence and it is
#: still not a ruling this module may make: choosing between two CONFIRMED rules
#: on a figure a customer is quoted is precisely what the prime directive
#: forbids. So the line is REFUSED BY NAME, the net impact says it excluded it,
#: and OQ-179 carries the question.
DEPOSIT_DIFFERENTIAL_UNAVAILABLE: dict[str, Any] = {
    "code": "deposit_differential_rules_conflict",
    "br_refs": ["BR-CUS-042", "BR-CUS-062"],
    "oq_ref": "OQ-179",
    "detail": (
        "BR-CUS-042 says compute the category differential on a plan change; BR-CUS-062 says "
        "there is no deposit recompute in v1. Both are CONFIRMED. No differential is stated "
        "and none is registered."
    ),
}

#: B4.3 prorates base AND usage. The base half is a stored charge the engine can
#: scale; the usage half needs a FORECAST of consumption for a period that has
#: not happened, and nothing in this repo forecasts consumption for a preview
#: (metering estimates a period that HAS happened, which is a different thing).
USAGE_PREVIEW_UNAVAILABLE: dict[str, Any] = {
    "code": "usage_forecast_absent",
    "br_ref": "BR-RAT-004",
    "oq_ref": "OQ-180",
    "detail": (
        "B4.3 prorates usage as well as base. Pricing usage for a period that has not "
        "happened needs a forecast, and no rule says what it should be — an average, the "
        "same month last year, or nothing at all. US-CUS-016 TC-3's 'day-split usage' has no "
        "input."
    ),
}

#: The unit's billing period could not be located, so a mid-cycle split cannot
#: be LOCATED either — not "cannot be computed".
#:
#: ✅ **THE READ EXISTS SINCE 2026-08-31 (`DEF-2708`).** `apps.metering
#: .selectors.billing_period_for_unit` is published and this constant no longer
#: reports an unwritten seam: it reports a cycle that cannot ANSWER. The four
#: causes are a unit on no cycle, a pre-CR-029 cycle carrying no frequency or no
#: first run, a date before the cycle's first run, and a unit billing on two
#: cycles at once. **The machine code is deliberately unchanged** — every
#: catalogue, every screen and `tests/test_us_cus_012_017_account_actions.py`
#: assert on it, and a refusal code is a contract with the front end (G32),
#: not prose. What changed is what it MEANS, so the detail says so.
PERIOD_UNAVAILABLE: dict[str, Any] = {
    "code": "billing_period_unpublished",
    "br_ref": "BR-MET-009",
    "oq_ref": None,
    "detail": (
        "The unit's billing period is derived by metering from the cycle's own schedule — "
        "`apps.metering.selectors.billing_period_for_unit(unit_id)`, a metering read customers "
        "may not make itself (B1) — and this unit's cycle cannot answer it: the unit is on no "
        "cycle, or on two, or its cycle carries no frequency and no first run (every cycle "
        "provisioned before CR-029). No prorated figure is stated, because assuming a 30-day "
        "month would invent money from a calendar nobody configured."
    ),
}

EFFECTIVE_IMMEDIATELY = "immediately"
EFFECTIVE_NEXT_CYCLE = "next_cycle"
EFFECTIVE_CUSTOM = "custom"

#: A19's plan-change confirmation email ("Your rate plan has changed — effective
#: Sep 1"), by CODE. There is no `notification_templates` table (EP-NOT-02), so
#: this is a handle the dispatcher will resolve, not a pinned version.
#:
#: ⚠⚠ **THIS READ `"plan_change"` FROM W6 UNTIL 2026-08-30 AND THAT CODE IS
#: DECLARED BY NOTHING.** Not `catalogs.LISTINGS`, not `seed_templates.SEEDABLE`,
#: not `CATALOGS` — so every plan-change email this product has ever queued was
#: pinned to wording that does not exist and would have rendered as nothing
#: anybody wrote. It is DEF-2511's fault in a third module, found by CR-048 wave
#: B task B11 while adopting the class the letter should always have named:
#: `email_plan_change`, seeded on every tenant since 2026-08-16 and counted by
#: B9 as wording with no rule.
#:
#: **A TEMPLATE CODE IS NOT A DOCUMENT TYPE**, and the two vocabularies look
#: alike, which is exactly why this survived. The old value is quoted rather
#: than deleted so a reader diffing an old queue row against a new one can see
#: what changed underneath it.
PLAN_CHANGE_TEMPLATE_CODE = "email_plan_change"


def _q6(value: Any) -> str:
    """A NUMERIC(18,6) figure as its wire string (CLAUDE.md rule 2)."""
    return str(Decimal(str(value)).quantize(Decimal("0.000001")))


def _plan_base_by_service(plan: dict[str, Any]) -> dict[str, Decimal]:
    """`{service_code: base_charge}` from rating's own plan bundle.

    Read verbatim. Nothing here derives, defaults or scales a base charge — a
    plan with no `plan_services` row for a service has no base charge for it,
    which is a different statement from zero and is left absent.
    """
    out: dict[str, Decimal] = {}
    for row in plan.get("services") or []:
        if isinstance(row, dict) and row.get("base_charge") is not None:
            out[str(row["service"])] = Decimal(str(row["base_charge"]))
    return out


def _account_and_unit_plan(account_id: Any) -> tuple[models.Account, Any, dict[str, Any]]:
    """The account, its unit, and the plan the unit holds.

    BR-CUS-029 as SUPERSEDED by the PO on 2026-08-11 — *"from unit you will
    derive the plan"*. There is no account-side plan record to read and none is
    invented: the unit is the single place a plan lives, and this is the
    derivation the ruling describes.
    """
    from apps.customers import selectors as customers_selectors

    account = customers_selectors.account_or_404(account_id)
    unit = seams.unit_row(account.unit_id)
    current = seams.plan_ref(getattr(unit, "rate_plan_id", None))
    if current is None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-MET-040",
            message_key="customers.plan_change.no_current_plan",
            params={"account_id": str(account.pk)},
        )
    return account, unit, current


def plan_change_options(account_id: Any) -> dict[str, Any]:
    """S23 step 1 — the plans this account may move to, and why each is offered.

    BR-CUS-041 + BR-RAT-030: PUBLISHED plans whose services are a SUBSET of the
    unit's services. A plan covering a service the unit does not take cannot be
    billed on that unit, so it is not offered at all; a plan covering FEWER
    services is offered WITH the loss named (`drops_services`), because
    US-CUS-016 TC-6 requires an explicit acknowledgment and silence is what a
    customer would discover on their next bill.

    `requires_eligibility` carries the plan's own eligibility flags. ADVISORY —
    BR-RAT-043 (OQ-055 closure) makes eligibility advisory-with-audit in v1, so
    nothing here gates on it and the wizard logs the proof checkbox instead.
    """
    account, unit, current = _account_and_unit_plan(account_id)
    unit_services = {row["service"] for row in seams.service_points_for(account.unit_id)}
    current_detail = seams.plan_detail(current["id"]) or {}
    offered: list[dict[str, Any]] = []
    for row in seams.assignable_plans():
        services = {str(code) for code in (row.get("services") or [])}
        # CR-013 part 5 (PLN-04): *"ineligible plans listed with the failing
        # rule, not filtered out"* — the same principle the CR states for the
        # plan wizard's step 2, and for the same reason: *"an absent option
        # teaches the operator the product cannot do it."* Until 2026-08-21 both
        # conditions below were a `continue`, so a clerk looking for the water
        # plan they had just published simply did not see it and had nothing to
        # read. The row is emitted either way now, carrying the CODE of the rule
        # that refuses it; the sentence stays the screen's (one translated
        # string per catalogue), exactly as `drops_services` already works.
        #
        # ⚠ AN `ineligible_reason` IS NOT A WARNING — IT IS A REFUSAL, and the
        # screen must render the row UNSELECTABLE. Nothing about what may be
        # assigned has changed here; only what a clerk can see and understand.
        # Whether the second reason should become acknowledgeable (the way
        # `drops_services` is) is the PO's, and is OQ-302.
        ineligible_reason: str | None = None
        if not services:
            # A published plan with no service lines. Assigning it bills nothing
            # at all, which is worse than the mismatch below and is why it is
            # named separately rather than folded into one "not eligible".
            ineligible_reason = "no_services"
        elif not services.issubset(unit_services):
            # BR-CUS-041, and the docstring's own sentence: a plan covering a
            # service the unit does not take cannot be billed on that unit.
            ineligible_reason = "covers_unavailable_services"
        offered.append(
            {
                "id": row["id"],
                "code": row["code"],
                "name": row["name"],
                "version": row.get("version"),
                "services": sorted(services),
                "base_charges": row.get("base_charges"),
                "is_current": str(row["id"]) == str(current["id"]),
                # US-CUS-016 TC-6 / TC-1's per-row note, as DATA. The sentence a
                # clerk reads is the screen's (one translated string per
                # catalogue), never a sentence assembled on the server.
                "drops_services": sorted(unit_services - services),
                "requires_eligibility": sorted((row.get("eligibility") or {}).keys()),
                #: `None` = assignable. A CODE (never a sentence) = refused, and
                #: this is the rule that refuses it.
                "ineligible_reason": ineligible_reason,
                #: The services this plan prices that the unit does not take —
                #: what `covers_unavailable_services` is ABOUT, so the screen can
                #: name them instead of saying "some service".
                "missing_services": sorted(services - unit_services),
            }
        )
    return {
        "account_id": str(account.pk),
        "unit_id": str(account.unit_id),
        "unit_services": sorted(unit_services),
        "current_plan": {
            "id": current["id"],
            "code": current["code"],
            "name": current["name"],
            "version": current.get("version"),
            "base_charges": current_detail.get("base_charges"),
        },
        "plans": offered,
    }


def _effective_date(payload: dict[str, Any], account: models.Account) -> tuple[date, str]:
    """The effective date and WHICH of BR-CUS-041's three options produced it.

    `effective_on` is an explicit calendar date (the Custom option, and the one
    the wizard sends once it has resolved Immediately or Next-cycle to a day).
    `effective` names an option instead:

      · `immediately`  → the tenant's today (BR-TEN-043: the event date is asked
        for explicitly; `tenant_today()` is the tenancy read, not a wall clock).
      · `next_cycle`   → the day after the current period ends — which needs the
        period, so it REFUSES when metering cannot answer, rather than guessing
        a month boundary.
    """
    raw = payload.get("effective_on")
    if raw:
        fe: list[dict[str, Any]] = []
        parsed = _date(raw, "effective_on", fe)
        _refuse_fields(fe)
        return parsed, EFFECTIVE_CUSTOM
    option = str(payload.get("effective") or EFFECTIVE_NEXT_CYCLE)
    if option == EFFECTIVE_IMMEDIATELY:
        return seams.tenant_today(), EFFECTIVE_IMMEDIATELY
    if option == EFFECTIVE_NEXT_CYCLE:
        period = _period_for(account)
        if period is None:
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref=PERIOD_UNAVAILABLE["br_ref"],
                message_key="customers.plan_change.period_unavailable",
                params={"detail": PERIOD_UNAVAILABLE["detail"]},
            )
        return period[1] + timedelta(days=1), EFFECTIVE_NEXT_CYCLE
    _refuse_fields(
        [
            _field_error(
                "effective", errors.VAL_UNKNOWN_LOOKUP, "customers.plan_change.bad_effective"
            )
        ]
    )
    raise AssertionError("unreachable — _refuse_fields always raises")  # pragma: no cover


def _period_for(account: models.Account, *, as_of: date | None = None) -> tuple[date, date] | None:
    """The unit's billing period as `(start, end)`, or None.

    `as_of` names WHICH period (BR-TEN-043 — the event date is an argument).
    The proration split passes the EFFECTIVE date, because the period a
    mid-cycle change splits is the one that change falls in; the "next cycle
    start" resolver passes nothing, because *"next"* is relative to today.
    """
    window = seams.billing_period_for_unit(account.unit_id, as_of=as_of)
    if not window:
        return None
    try:
        return (
            date.fromisoformat(str(window["start"])),
            date.fromisoformat(str(window["end"])),
        )
    except (KeyError, TypeError, ValueError):
        return None


class _Period:
    """The two day-counts the rating engine reads off a period, and nothing else.

    A carrier, deliberately — `apps.rating.engine.prorate_base_charge` asks for
    `.service_days` and `.cycle_days` and this answers. Counting calendar days
    between two dates is not proration; the RATIO and the multiplication are the
    engine's, and this class performs neither.
    """

    __slots__ = ("service_days", "cycle_days")

    def __init__(self, service_days: int, cycle_days: int) -> None:
        self.service_days = service_days
        self.cycle_days = cycle_days


def _guard_effective_date(account: models.Account, effective: date) -> None:
    """US-CUS-016 TC-4 — an issued bill is never re-priced (BR-BIL-004).

    The earliest allowed date is the day after the last ISSUED bill's period
    end. The refusal points at the correction path (J6) rather than clamping the
    date silently: a wizard that moved a clerk's date without saying so would
    change what a customer is charged and report success.
    """
    billed_through = seams.last_issued_invoice_period_end(account.pk)
    if not billed_through:
        return
    try:
        boundary = date.fromisoformat(str(billed_through))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return
    if effective <= boundary:
        raise errors.BizError(
            errors.BIZ_WINDOW,
            br_ref="BR-BIL-004",
            message_key="customers.plan_change.behind_issued_bill",
            params={
                "billed_through": boundary.isoformat(),
                "effective_on": effective.isoformat(),
                "earliest": (boundary + timedelta(days=1)).isoformat(),
            },
        )


def _target_plan(payload: dict[str, Any]) -> dict[str, Any]:
    """The plan being moved TO — PUBLISHED only (BR-RAT-030, US-CUS-016 TC-5).

    An unknown id and an unpublished one answer the same refusal, which is
    rating's own posture: separating them would tell a caller which ids exist.
    """
    plan_id = payload.get("rate_plan_id") or payload.get("plan_id")
    if not plan_id:
        _refuse_fields(
            [
                _field_error(
                    "rate_plan_id", errors.VAL_REQUIRED, "customers.plan_change.plan_required"
                )
            ]
        )
    plan = seams.plan_ref(plan_id)
    if plan is None:
        _refuse_fields(
            [
                _field_error(
                    "rate_plan_id",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "customers.plan_change.plan_unknown_or_unpublished",
                    rate_plan_id=str(plan_id),
                )
            ]
        )
    return plan


def preview_plan_change(account_id: Any, payload: Any) -> dict[str, Any]:
    """S23 step 2 — the proration preview. WRITES NOTHING, COMPUTES NO PRORATION.

    US-CUS-016 §1 is explicit on both counts: *"Preview math comes from the
    rating engine via service function (US-RAT-012) — this story computes
    nothing itself and WRITES NOTHING."* This function honours that literally:

      · the BASE COMPARISON is a subtraction of two of the tenant's own stored
        base charges (30.50 → 12.00 = −18.50, US-CUS-016 §7's first figure).
        Two stored amounts subtracted is not proration and no rule assigns it
        elsewhere;
      · every PRORATED figure comes from `seams.prorate_base_charge`, which is
        `apps.rating.engine.prorate_base_charge` — B4.3, finance-signed, GT-3.
        There is no day-ratio multiplication anywhere in this module, and
        `test_us_cus_016_tc3__the_prorated_base_comes_from_the_rating_engine`
        replaces the engine with a sentinel to prove it;
      · the DEPOSIT differential is not stated at all (OQ-179, above);
      · the USAGE half is not stated at all (OQ-180, above);
      · when metering cannot answer where the cycle starts, no prorated figure
        is stated either — `proration` is null with its reason beside it.

    `net_impact` therefore always carries `excludes[]`. A net that quietly
    summed a shorter list would be the most dangerous number on the screen: it
    would look like the whole answer.
    """
    data = _payload_dict(payload)
    account, _unit, current = _account_and_unit_plan(account_id)
    target = _target_plan(data)
    effective, option = _effective_date(data, account)
    _guard_effective_date(account, effective)

    current_detail = seams.plan_detail(current["id"]) or {}
    target_detail = seams.plan_detail(target["id"]) or {}
    current_bases = _plan_base_by_service(current_detail)
    target_bases = _plan_base_by_service(target_detail)
    current_total = sum(current_bases.values(), Decimal("0"))
    target_total = sum(target_bases.values(), Decimal("0"))

    # ⚠ THE PERIOD THE CHANGE FALLS IN, not the one today falls in (`DEF-2708`
    # · BR-TEN-043). A change effective next month splits NEXT month's period,
    # and those two months are different lengths more often than not.
    period = _period_for(account, as_of=effective)
    proration: dict[str, Any] | None = None
    proration_unavailable: dict[str, Any] | None = dict(PERIOD_UNAVAILABLE)
    if period is not None:
        start, end = period
        cycle_days = (end - start).days + 1
        old_days = max((effective - start).days, 0)
        new_days = max(cycle_days - old_days, 0)
        old_line = seams.prorate_base_charge(
            base_charge=current_total, period=_Period(old_days, cycle_days)
        )
        new_line = seams.prorate_base_charge(
            base_charge=target_total, period=_Period(new_days, cycle_days)
        )
        if old_line is None or new_line is None:
            # The engine is the ONLY source of a prorated figure. Unwired means
            # no figure — never a fallback multiplication here.
            proration_unavailable = {
                "code": "rating_engine_unwired",
                "br_ref": "BR-RAT-004",
                "oq_ref": None,
                "detail": (
                    "`apps.rating.engine.prorate_base_charge` did not resolve, so no prorated "
                    "amount was produced. B4.3 lives in that one function and this module "
                    "never substitutes arithmetic of its own."
                ),
            }
        else:
            proration_unavailable = None
            proration = {
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "cycle_days": cycle_days,
                "current_plan_line": {
                    "plan": current["code"],
                    "service_days": old_days,
                    "amount": str(old_line),
                },
                "new_plan_line": {
                    "plan": target["code"],
                    "service_days": new_days,
                    "amount": str(new_line),
                },
                "computed_by": "apps.rating.engine.prorate_base_charge",
            }

    excludes = ["deposit_differential", "usage"]
    if proration is None:
        excludes.append("proration")
    return {
        "account_id": str(account.pk),
        "currency": account.currency,
        "effective_on": effective.isoformat(),
        "effective_option": option,
        "current_plan": {"id": current["id"], "code": current["code"], "name": current["name"]},
        "new_plan": {
            "id": target["id"],
            "code": target["code"],
            "name": target["name"],
            "version": target.get("version"),
        },
        "base": {
            "current_total": _q6(current_total),
            "new_total": _q6(target_total),
            "delta": _q6(target_total - current_total),
            "per_service": [
                {
                    "service": code,
                    "current": _q6(current_bases[code]) if code in current_bases else None,
                    "new": _q6(target_bases[code]) if code in target_bases else None,
                }
                for code in sorted(set(current_bases) | set(target_bases))
            ],
        },
        "proration": proration,
        "proration_unavailable": proration_unavailable,
        "deposit_differential": None,
        "deposit_differential_unavailable": dict(DEPOSIT_DIFFERENTIAL_UNAVAILABLE),
        "usage_unavailable": dict(USAGE_PREVIEW_UNAVAILABLE),
        # US-CUS-016 §5 "Net impact next bill = Σ preview lines". The Σ is over
        # the lines that EXIST — and it says which ones it never saw.
        "net_impact": {
            "amount": _q6(target_total - current_total),
            "basis": "base_charges_only",
            "excludes": excludes,
        },
        "writes": [],  # §1: "this story … WRITES NOTHING", asserted in TC-1
    }


def _plan_change_agreement_answers(
    account: models.Account, data: dict[str, Any]
) -> list[tuple[Any, dict[str, Any]]]:
    """`DEF-CUS-9170` — the merged SERVICE-AGREEMENT answers Change plan (slot
    `S23`) will write, one per OPEN agreement, computed before any write.

    The clerk types ONE set of answers for the account's services; each open
    agreement keeps its own stored answers and takes the changed ones on top
    (`existing=`), so a key the clerk did not touch is never wiped. A required
    field placed Input on Change plan is checked against each agreement's
    stored answer, every time — the form drew it, so it must hold one.

    An account with no open agreement has nothing to put an answer on: a
    non-empty blob is refused by name rather than dropped.
    """
    agreements = list(
        models.ServiceAgreement.objects.filter(
            tenant_id=account.tenant_id, account=account, ended_on__isnull=True
        ).order_by("started_on", "id")
    )
    raw = data.get("service_custom_data")
    if not agreements:
        if isinstance(raw, dict) and any(v not in (None, "", []) for v in raw.values()):
            _refuse_fields(
                [
                    _field_error(
                        "service_custom_data",
                        errors.VAL_FORMAT,
                        "customers.account.service_fields_on_draft",
                    )
                ]
            )
        return []
    return [
        (
            row,
            seams.validate_custom_data(
                "service_agreements",
                raw,
                screen="S23",
                existing=dict(row.custom_data or {}),
            ),
        )
        for row in agreements
    ]


def _write_plan_change_agreement_answers(
    actor: Any, account: models.Account, answers: list[tuple[Any, dict[str, Any]]]
) -> None:
    """Write only the agreements whose answers MOVED, audited before→after."""
    changed = [(row, merged) for row, merged in answers if merged != (row.custom_data or {})]
    if not changed:
        return
    before = {str(row.pk): dict(row.custom_data or {}) for row, _ in changed}
    for row, merged in changed:
        row.custom_data = merged
        row.save(update_fields=["custom_data", "updated_at"])
    _audit(
        actor,
        "service_agreement.custom_data.updated",
        account.pk,
        before=before,
        after={str(row.pk): merged for row, merged in changed},
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-IDN-009")
def change_plan(actor: Any, account_id: Any, payload: Any) -> dict[str, Any]:
    """S23 step 3 (US-CUS-017) — confirm the change, notify, audit.

    ONE transaction, and what lands in it:

      (a) the unit's plan moves and the append-only `unit_plan_assignments` row
          is written with source `change_plan`, the actor and the reason —
          through metering's OWN `assign_unit_plan`, the reviewed cross-module
          write path (B2 §2). Customers writes neither table.
      (b) DROPPED 2026-08-11 by PO ruling. There is no account-side plan record:
          *"from unit you will derive the plan"* (BR-CUS-029, SUPERSEDED). The
          version snapshot BR-CUS-013 asks for rides on the unit's history row.
      (c) the deposit-differential instruction is NOT registered — two CONFIRMED
          rules disagree (OQ-179). It is reported in `problems[]`.
      (d) the A19 plan-change email is queued through notifications when the
          clerk elects it (BR-NOT-005: written to the queue, never sent inline).
      (e) `audit_log` `plan.changed` carries from→to, the dates and the actor.

    A plan change moves no balance, so hard rule 7 does not compel (e) on its
    own reading. It is written anyway and the reading is stated rather than
    implied: this decides what the customer will be charged from a date, which
    is a decision ABOUT money, and `record_unit_plan_assignment` takes the same
    posture for its own backdating row.

    IDEMPOTENCY (TC-5): the same plan from the same date twice is ONE change.
    That guard is rating's, on the history row's natural key, and it is reached
    rather than re-implemented — two guards would be two answers.
    """
    data = _payload_dict(payload)
    account, _unit, current = _account_and_unit_plan(account_id)
    target = _target_plan(data)
    effective, option = _effective_date(data, account)
    _guard_effective_date(account, effective)
    reason = _text(data.get("reason"), 500)
    notify = _bool(data.get("notify"))
    eligibility_proof = _bool(data.get("eligibility_proof_logged"))
    # `DEF-CUS-9170` (CR-161-BRC10 W3) — Change plan is the `S23` input slot
    # for SERVICE AGREEMENT fields. Checked BEFORE anything is written, so a
    # refusal leaves the plan where it was.
    agreement_answers = _plan_change_agreement_answers(account, data)

    problems: list[dict[str, Any]] = [
        {
            "code": "deposit_differential_not_registered",
            "br_ref": "BR-CUS-042",
            "oq_ref": DEPOSIT_DIFFERENTIAL_UNAVAILABLE["oq_ref"],
            "detail": DEPOSIT_DIFFERENTIAL_UNAVAILABLE["detail"],
        }
    ]

    with transaction.atomic():
        assignment = seams.assign_unit_plan(
            actor,
            str(account.unit_id),
            {
                "plan_id": target["id"],
                "effective_from": effective.isoformat(),
                "source": "change_plan",
                "reason": reason,
            },
        )
        if assignment is None:
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-CUS-014",
                message_key="customers.plan_change.assignment_unavailable",
                params={"unit_id": str(account.unit_id)},
            )
        history = assignment.get("history") or {}
        recorded = {
            "unit_id": str(account.unit_id),
            "rate_plan_id": str(target["id"]),
            "plan_code": target["code"],
            "plan_version": history.get("plan_version") or target.get("version"),
            "assigned_from": effective.isoformat(),
            "source": "change_plan",
            "reason": reason,
        }
        _audit(
            actor,
            "plan.changed",
            account.pk,
            before={"rate_plan_id": current["id"], "plan_code": current["code"]},
            after={
                **recorded,
                "effective_option": option,
                # BR-RAT-043: eligibility is advisory-with-audit in v1 — the
                # checkbox is EVIDENCE on the trail, never a gate (TC-3).
                "eligibility_proof_logged": eligibility_proof,
            },
        )
        _write_plan_change_agreement_answers(actor, account, agreement_answers)

    notification = (
        _queue_plan_change_email(actor, account, current, target, effective, assignment)
        if notify
        else None
    )
    if notify and notification is None:
        problems.append(
            {
                "code": "notification_not_queued",
                "br_ref": "BR-NOT-005",
                "oq_ref": None,
                "detail": (
                    "The plan-change email was elected and no queue row exists — "
                    "`apps.notifications.services.queue_document` did not resolve. The plan "
                    "change itself stands; the customer has NOT been told."
                ),
            }
        )
    return {
        "account_id": str(account.pk),
        "assignment": recorded,
        "notification": notification,
        "problems": problems,
    }


def _queue_plan_change_email(
    actor: Any,
    account: models.Account,
    current: dict[str, Any],
    target: dict[str, Any],
    effective: date,
    assignment: dict[str, Any],
) -> dict[str, Any] | None:
    """US-CUS-017 (d) — the A19 plan-change confirmation, WRITTEN to the queue.

    Outside the transaction that moves the plan, deliberately: a queue write
    that failed must not roll back a plan change the clerk was told about, and
    BR-NOT-005 already makes the queue the durable record.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  REWRITTEN 2026-08-30 · CR-048 wave B task B11. IT HAD FOUR FAULTS.  ║
    ╚══════════════════════════════════════════════════════════════════════╝
    This function existed and ran and wrote a row, and every one of those rows
    was wrong in a way nothing reported — which is why it is worth listing them
    rather than quietly replacing the body:

      1 · **THE TEMPLATE CODE WAS NOT A TEMPLATE CLASS.** It pinned
          `plan_change`, declared by no catalogue anywhere (DEF-2511). The
          seeded wording is `email_plan_change`.
      2 · **IT KEYED ON THE ACCOUNT** — `source_id=str(account.pk)` — so a
          customer's SECOND rate change found the first letter's row and
          returned `created=False`. No error, no gap, and a customer told once
          and never again (DEF-2512).
      3 · **IT RODE `source_type="plan"`, WHICH IS THE PAYMENT-PLAN KIND.** The
          two senses of "plan" are different things in this product, and once
          BR-NOT-024 landed on 2026-08-29 the payment-plan PRINT FLOOR began
          putting this rate-plan email on paper.
      4 · **IT PASSED NO `event_key`**, so switching *Rate plan changed* off on
          Settings → Notifications did nothing whatsoever — CR-048's own
          headline, in this module.

    All four are closed by handing the write to `notifications_seam`, which
    names the `rate_plan_changed` event, pins `email_plan_change`, rides the
    `account` source kind and keys on the **`unit_plan_assignments` row** — so
    the letter inherits `change_plan`'s own TC-5 idempotency (*"the same plan
    from the same date twice is ONE change"*) rather than keeping a second
    opinion about it.

    The seam raises nothing and runs inside its own savepoint (hard-won law 14),
    so this call cannot reach the committed change by either route.

    ⚠ **THE LANGUAGE IS THE UTILITY'S, NOT THE ACCOUNT'S — AMENDED 2026-09-23
    (`OQ-CUS-12619`, `DEF-NOT-6354`).** This paragraph read *"THE LANGUAGE
    STILL TRAVELS FROM HERE … this is the one caller that holds it"* and passed
    `account.preferred_language`. The PO then ruled, verbatim, *"(a) Portal
    only; emails in English."*: a message takes the utility's default language
    and the account's preference drives the customer portal alone
    (`BR-NOT-006` amended). So the language is read from Settings → Regional
    through `seams.tenant_default_language`, the same read every other
    customer message in this module uses.
    """
    from apps.customers import notifications_seam

    # ⚠ **THE ID IS NESTED, AND READING IT OFF THE TOP LEVEL SILENTLY RETURNS
    # NOTHING.** `metering._apply_unit_plan` answers `{unit_id, rate_plan_id,
    # plan_name, …, "history": {…}}` and the append-only
    # `unit_plan_assignments` row's own id lives on the INNER dict — the same
    # place this function's caller already reads `plan_version` from. Taking
    # `assignment["id"]` returns None, this function returns None, and
    # `change_plan` reports `notification_not_queued`: a letter that silently
    # stops being sent, which is the failure mode this whole wave is about.
    assignment_id = (assignment.get("history") or {}).get("id")
    if assignment_id is None:  # pragma: no cover - _apply_unit_plan raises without one
        return None
    outcome = notifications_seam.queue_rate_plan_change(
        assignment_id=assignment_id,
        account_id=account.pk,
        effective_on=effective,
        # The plan's NAME, which is what a customer would recognise. Its CODE is
        # an internal handle and stays in the response's from/to pair below.
        plan_name=str(target.get("name") or target["code"]),
        # CR-190-BRC10 — the two plans, so the email can state their charges.
        from_plan_id=current.get("id"),
        to_plan_id=target.get("id"),
        customer_class=(
            getattr(getattr(account, "account_type", None), "code", None) or None
        ),
        actor=actor,
        language=seams.tenant_default_language(),
    )
    return {
        "effective_on": effective.isoformat(),
        "from_plan": current["code"],
        "to_plan": target["code"],
        # The seam's own outcome rows — queued, already queued, suppressed by
        # this utility's switch, refused, or broken. `channels` and `created`
        # kept their old shape would have been a second copy of what the rows
        # already say, free to disagree with them.
        "outcome": [dict(row) for row in outcome],
    }


# ══════════════════════════════════════════════════════════════════════════
# US-TEN-019 SAMPLE DATA — the seams `apps/tenancy/seams.py` documents
# ══════════════════════════════════════════════════════════════════════════
# Thin forwarders on purpose. The seam contract names
# `apps.customers.services.seed_sample_records`, G20 harvests that exact path, and
# the implementation is large enough to deserve its own file — so the published
# NAME lives here and the CODE lives in `sample_data.py`. The import is inside
# each function because `sample_data` imports this module (it drives the same
# services a clerk's click uses), and a module-level import would be a cycle.
#
# DEF-153: every one of these was DOCUMENTED and UNIMPLEMENTED until
# 2026-08-16, which is why the Sample data panel loaded nothing and a brand-new
# tenant was empty.


def seed_sample_records(actor: Any) -> int:
    """BR-TEN-056/057 — this module's block of the sample set. See sample_data."""
    from apps.customers import sample_data

    return sample_data.seed_sample_records(actor)


def seed_sample_payment_plans(actor: Any) -> int:
    """CR-010 Part-10.4 amendment 3 (PO 2026-08-17) — the live, mid-schedule
    payment plan, driven through the S24 wizard's own path. See sample_data."""
    from apps.customers import sample_data

    return sample_data.seed_sample_payment_plans(actor)


def seed_sample_move_out(actor: Any) -> int:
    """DEF-CUS-4631 — the ONE seeded tenancy that ends, driven through
    `move_out` above rather than written as a row. Until 2026-09-07 no seeded
    tenant had ever held an account in the TERMINAL state the flow exists to
    reach. See sample_data."""
    from apps.customers import sample_data

    return sample_data.seed_sample_move_out(actor)


def seed_sample_wizard_parks(actor: Any) -> int:
    """CR-035 step 6 row 6 (PO 2026-08-26) — ONE parked move-in, so the
    `Waiting on` tab is not empty on a demo. It writes one row of the
    tenancy-hosted `wizard_parks` through that module's own `park()` service and
    changes nothing else (BR-SHL-048). See sample_data."""
    from apps.customers import sample_data

    return sample_data.seed_sample_wizard_parks(actor)


def seed_sample_owner_accounts(actor: Any) -> int:
    """DEF-MET-6302 (PO 2026-09-23, *"attach master accounts to the sample
    data"*) — the owner's account at each seeded address whose owner is not its
    occupier, and the `premises.master_account_id` declaration that fills the
    Premises list's Owner column. See sample_owner_accounts."""
    from apps.customers import sample_owner_accounts

    return sample_owner_accounts.seed_sample_owner_accounts(actor)


def seed_sample_owner_accounts_note() -> str | None:
    """BR-TEN-060 — the named line the Sample data panel shows beside the block:
    how many addresses were passed over, and under which clause of the rule.

    ⚠ **IT CARRIES A NUMBER FOR EVERY REASON**, because a declared blind spot
    with no number beside it is indistinguishable from an empty one (hard-won
    law 7's fifth shape). `None` where there is nothing to say."""
    from apps.customers import sample_owner_accounts

    return sample_owner_accounts.owner_account_note()


def remove_sample_records() -> dict[str, Any]:
    """BR-TEN-061/066 — remove what is free, report the rest BY NAME."""
    from apps.customers import sample_data

    return sample_data.remove_sample_records()


def sample_record_count() -> int:
    """How many sample rows this module holds right now, read live."""
    from apps.customers import sample_data

    return sample_data.sample_record_count()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-005@bbed56d (slice 3 — EP-CUS-02 move-out lead story; co-packets US-CUS-004@bbed56d · US-CUS-003@bbed56d · EP-CUS-01@a2e1d59 · customers 02-business-rules@f125a9c) · slice 1 half generated from US-CUS-001@a2e1d59
# generated: 2026-08-11 by story-coder (W2 customers slice 1 = reference-data seam · slice 2 = the account write path · slice 3 = move-out + move-in) · AMENDED 2026-08-15 by story-coder (tenant custom-fields lane)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests -m "not golden and not isolation"✔ · pytest tests -m isolation✔ (sqlite tier) + live-Postgres isolation run✔ · run_gates 14-PASS/0-FAIL/1-SKIP✔ · seed_demo --check exits 0✔
# exceptions: `account_types` is seeded by MIGRATION (platform table) and this seam is insert-missing only — the per-tenant run normally returns 0, which reference_seed_omissions() explains rather than letting an operator read it as "empty" · BR-CUS-017 has NO DATABASE HALF and is not getting one — PO ruling 2026-08-10 option (a), service-layer enforcement inside the transaction with locking; this file is the whole enforcement, and on a backend without advisory locks (sqlite) only the check survives, so the concurrency proof runs on live Postgres · move-in is a SECOND door onto a unit and REUSES `_make_occupying` rather than carrying a copy of the guard; the ordering is asserted on the move-in path in tests/test_us_cus_004_005_move_in_out.py and the cross-session effect in tests/test_us_cus_004_move_in_race.py · the OCCUPYING class set is DERIVED from BR-CUS-018 + BR-MET-036 (a tenant-added non-draft `non_billable` status would not occupy — the ruling settled the MECHANISM, not this class boundary, so the residue is REPORTED as a new question) · `account_plan_assignments` (BR-CUS-029) and the `customers`/`customer_accounts` entity (BR-CUS-054) remain NotImplementedError stubs naming their rules; every payload field that would need one is REFUSED with its rule id · move-out performs ONLY the BR-CUS-030 parts with somewhere to be written (`closed_at`, terminal status, `service_agreements.ended_on`, audit) — the final bill, the deposit settlement + BR-CUS-057 interest, the dunning stop and the close-out documents each have NO table anywhere and are reported by rule id in MOVE_OUT_UNAVAILABLE — ⚠ **the close reason WAS in that list until 2026-09-20 and is now WRITTEN** (`accounts.close_reason`, migration 0058, PO ruling option A): `reason` is accepted on this door alone, `close_reason_not_recorded` is gone from MOVE_OUT_UNAVAILABLE because it had become a false claim, and an account closed with no reason given holds NULL, which means *nobody was asked* and never *no reason* · the BR-CUS-031 handoff is ASSEMBLED and RETURNED but NOT PERSISTED — no handoff table, queue or outbox exists in B2 or any addendum, so `final_bill_handoff.persisted` is False and the record rides the response and the audit row only · US-CUS-005 TC-6's issued-bill guard is WRITTEN but its seam is unwired (billing owns `invoices`), so every move-out warns that the check could not run; the refusal itself is proved by driving the seam in a test · move-in commits NO reads: BR-CUS-021 routes them through metering's S28 batch path, whose idempotency fingerprint is scoped to (period, cycle, route, service, source), and minting a single-meter batch inside it could collide with the month's real import — `final_reads`/`initial_reads` are REFUSED inputs · the STANDALONE S19 entry has no path in 11b §S19 and none is invented: `POST /accounts` with an occupying status is it, and it now takes the same BR-CUS-056 boundary rule · J2 step 4's handoff stays INCOMPLETE by construction: every occupying path returns `plan_snapshot_not_recorded` + `deposit_not_applied` rather than implying either happened · deposit amounts, balances, interest and credit tiers are refused as inputs and never computed — no money is calculated, seeded or defaulted anywhere in this file · `active_account_count(service_code)` IS wired (slice 1 reported it as blocked on a customers→metering read seam; apps/customers/seams.py is that seam)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
