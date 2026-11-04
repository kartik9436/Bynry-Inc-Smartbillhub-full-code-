# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-011 (config-driven validation flag engine) · US-MET-008
#           (the same rules run over STAGED rows) · US-MET-009 (duplicate-vs-
#           committed) · US-MET-017 (TOU sum-sanity on a channel group) ·
#           US-AST-011 (BR-AST-029 — an export record is lawful ONLY on a
#           net-metering asset; on any other it is a hard row error)
#           Screens: S25, S28 (steps 3–4), S29, S64 (the config surface)
# Rules:    BR-MET-020 (thresholds are tenant CONFIG — no value is EVER
#           hardcoded; missing config fails SAFE, never falls back) ·
#           BR-MET-021 (flag vocabulary, one primary status) · BR-MET-052
#           (completed VEE catalog: negative usage = hard error never auto-
#           fixed · retired meter = error · vacant unit = warning · TOU
#           Σwindows≈total ±1% · duplicate key (meter,date,channel)) ·
#           BR-MET-061 (TOU sum-sanity severity = WARNING) · BR-MET-025
#           (master/sub mismatch beyond the configured loss tolerance) ·
#           BR-MET-019 (consumption = (current − prior) × multiplier,
#           NUMERIC(18,6), explicit unit, unrounded) · BR-MET-016
#           (duplicate-vs-committed) · BR-MET-057 (cycle read-window) ·
#           OQ-009 closure + GT-14 (rollover) · OQ-002 closure (seeded
#           thresholds) · OQ-004 closure (unit must match or a factor exists —
#           never a silent conversion)
# Tests:    06-backend/tests/test_us_met_011_validation.py (rule-by-rule, incl.
#           the GT-14 rollover fixture and the two-tenant config proof)
# Impacts:  apps/metering/services.py (assembles the context, stores outcomes) ·
#           apps/metering/estimation.py (shares the trailing-actuals helper) ·
#           apps/metering/quantities.py (the published GT-4/GT-14 seam calls
#           `classify_register_delta` — ONE wrap implementation, not two) ·
#           S31.2 billing exceptions consume the stored outcomes read-only
# ───────────────────────────────────────────────────────
"""The read validation engine — pure functions over an assembled context.

Nothing here touches the ORM, the tenant context or the clock: `services.py`
gathers the row's world into a `ReadContext` and this module decides. That is
what makes BR-MET-020's promise testable — the same fixture run through two
tenants' configs must flag differently, and a test can prove it without a
database.

**Three laws this module refuses to break.**

1. *No threshold is ever hardcoded* (BR-MET-020). Every number comes from the
   tenant's config — since CR-038 A1 (PO 2026-08-26) resolved PER SERVICE:
   the (tenant, service) `read_validation_service_settings` row first, the
   legacy tenant-wide `read_validation_settings` row for electric/water only
   (the two services OQ-002 ratified figures for), and where BOTH are absent
   the engine does NOT substitute the seeded defaults — the rules that need a
   threshold report `not_evaluated` with reason `validation_config_missing`
   (US-MET-011/TC-9). A skipped rule is visible; a guessed one is not.

2. *Nothing is ever auto-fixed* (BR-MET-052). A register wrap is classified
   `rollover` and its consumption IS computed (OQ-009 closure, GT-14) — but it
   is flagged for review, never passed silently. Any other negative usage is a
   HARD ERROR with no repair path in this module at all: the resolutions are
   human dispositions (US-MET-008) or a supersede (US-MET-016).

3. *A rule that cannot be evaluated says so* (CLAUDE.md law 1). There is no
   `pass` outcome for a rule whose inputs are missing. It returns severity
   `not_evaluated` with a machine-readable reason, so "0 errors" never quietly
   means "0 rules ran". `UNRATIFIED_RULES` below is the honest list of rules
   this engine will NOT evaluate because their thresholds are not signed
   anywhere — see the constant's own comment.

Outcomes are self-describing (BR-MET-022): every one carries the rule, the
severity, the thresholds USED and the computed comparison, so S25/S29/S31.2
render the explanation from storage without re-deriving anything (BR-MET-056).
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from collections.abc import Iterable
from typing import Any

from apps.metering import register_units

# CR-054 W1 task 7: the row key's GRAMMAR, not the parser's tenant world.
# `read_import` is pure — no ORM, no tenant context, no clock — exactly as this
# module is, so importing it keeps the rule pure. The alternative was a second
# spelling of the key's grammar here, and two spellings of one grammar is how a
# writer and a reader start disagreeing about what a key means (hard-won law 5).
from apps.metering import read_import
from apps.metering.models import CHANNEL_EXPORT, CHANNEL_GENERATION

#: `asset_types.category` for a behind-the-meter DEVICE (BR-AST-004's tab key,
#: `apps.assets.services.TAB_BTM`). Spelled here rather than imported so this
#: module keeps its promise of touching no other module — it is a VALUE, and a
#: divergence is one grep from both sides.
CATEGORY_BEHIND_THE_METER = "behind_the_meter"

# ── severities ─────────────────────────────────────────────────────────────
OK = "ok"
WARNING = "warning"
ERROR = "error"
NOT_EVALUATED = "not_evaluated"
# ── BR-MET-136 (PO 2026-08-26, CR-038) — THE TENANT SWITCHED THIS RULE OFF ──
#: **`disabled` is a SEPARATE severity from `not_evaluated`, deliberately, and
#: the difference is the whole reason the flag exists.**
#:
#: `not_evaluated` says *we could not judge this* — no threshold is configured,
#: there is no prior read, the history is too short. It is a GAP, and the batch
#: summary's `unevaluated_rules` exists so a clerk can go and CLOSE it.
#: `disabled` says *we were told not to judge this* — the utility looked at the
#: check, decided it does not fit their business, and switched it off. Nothing
#: is broken and there is nothing to chase.
#:
#: Collapsing the two would put a deliberate policy into the chase list beside
#: real gaps, and a chase list full of things nobody needs to chase is a chase
#: list nobody reads — the exact failure `not_evaluated` was invented to
#: prevent. To a clerk looking at one read, "the high-usage check could not run
#: — no figures for gas" and "the high-usage check is off — your utility turned
#: it off" are different facts leading to different actions, so they are
#: different severities.
#:
#: What it is NOT: a verdict. It never outranks `ok`, never becomes the read's
#: primary status, and never blocks a post. It is a STATEMENT ON THE READ, per
#: BR-MET-136's trailing clause — because a rule that silently produces no
#: outcome is indistinguishable from a rule that passed.
DISABLED = "disabled"

# The worst ACTIONABLE severity present becomes the row's severity, and the
# first ERROR (else the first WARNING) becomes the read's ONE primary status
# (BR-MET-021 "exactly one primary status plus the full rule-outcome detail").
# NOT_EVALUATED ranks BELOW ok deliberately: it is a reporting axis, not a
# verdict. Letting it outrank ok would make an unevaluable rule silently block
# a clean row from posting — a rule that could not run must be VISIBLE (it is,
# in the row's outcomes and in the batch's `unevaluated_rules`), not decisive.
# `disabled` ranks BELOW `not_evaluated` for the same reason `not_evaluated`
# ranks below `ok`, only more so: a check the tenant switched off must never
# decide anything about a row it was told not to look at.
_SEVERITY_RANK = {DISABLED: -2, NOT_EVALUATED: -1, OK: 0, WARNING: 1, ERROR: 2}

# ── rule names (BR-MET-021 vocabulary + the BR-MET-052 catalog additions) ───
RULE_UNKNOWN_METER = "unknown_meter"
RULE_RETIRED_METER = "retired_meter"
RULE_UNIT_MISSING = "unit_missing"
RULE_NEGATIVE_USAGE = "negative_usage"
RULE_ROLLOVER = "rollover"
RULE_DUPLICATE = "duplicate"
RULE_ZERO = "zero"
RULE_HIGH = "high"
RULE_LOW = "low"
RULE_DAYS_THRESHOLD = "days_threshold"
RULE_OUT_OF_WINDOW = "out_of_window"
RULE_VACANT_UNIT = "vacant_unit"
RULE_TOU_SUM_SANITY = "tou_sum_sanity"
RULE_MISMATCH = "mismatch"
RULE_FACTOR = "factor_flag"
# BR-AST-029 (US-AST-011 TC-4): an EXPORT record is only lawful on an asset
# whose `net_metering` flag is on. On any other asset it is rejected outright —
# never silently stored as if it were consumption, which would put grid export
# into a customer's billed usage.
RULE_EXPORT_NOT_NET = "export_not_net"
# ── CR-038 W6 (BR-MET-124/135, PO 2026-08-26) — DEVICE READINGS ────────────
#: **The `generation` register belongs to a DEVICE, and only to a device.**
#:
#: BR-MET-135, verbatim: *"The channel vocabulary gains `generation` — a
#: device's produced quantity (the driving case: a solar inverter's 612 kWh in
#: a month), distinct from `export` (a net METER's grid-push register on
#: different equipment) and never summed with consumption."*
#:
#: Two unlawful pairings, one rule, both HARD ERRORS with no auto-fix — exactly
#: the posture `RULE_EXPORT_NOT_NET` takes for its mirror image, and for the
#: same reason: the wrong quantity in the wrong register is a number that reads
#: as a customer's usage:
#:
#:   1. `generation` on a METER — the file means `export` (a net meter's
#:      grid-push) or it means the wrong asset. Guessing which would put a
#:      site's production into a meter's registers.
#:   2. a DEVICE's reading on a CONSUMPTION register (`total`, a TOU window,
#:      `demand`) — a PV inverter's 612 kWh landing in `total` is generation
#:      being billed as usage, the precise thing BR-MET-135 forbids.
#:
#: ⚠ **ENG ADDITION TO THE CATALOG — REPORTED.** No PO ruling names a rule for
#: this pairing. What the PO ruled is that the two registers are DIFFERENT
#: THINGS ON DIFFERENT EQUIPMENT and are never summed; this enforces exactly
#: that sentence and invents no threshold. It is flagged here rather than
#: buried so a reviewer can rule it down to a warning if they disagree.
RULE_GENERATION_CHANNEL = "generation_channel"
# BR-MET-049 (US-MET-018, CR-038 W1) — verbatim: "**Plan-driven read-set
# completeness**: the unit's plan determines the required read set per meter
# (TOU → per-window records; demand → +demand record); completeness is tracked
# and enforced as a VEE validation before billing". This is the IMPORT-TIME
# half: the registers a meter actually received in the batch vs the set its
# unit's plan expects, shortfall named channel by channel. A GROUP rule like
# `tou_sum_sanity` — evaluated once per (meter, read date), stored on every row
# of the group. Severity on a shortfall is WARNING, deliberately: a person may
# accept with a reason (BR-MET-015), because what billing does with an
# incomplete meter is Open 2 and unruled — a hard error here would invent that
# ruling at a call site.
RULE_PLAN_REGISTERS = "plan_registers"
# BR-MET-122 (CR-038 W2), verbatim: "**A METER IN THE FILE THAT IS NOT IN THE
# TAGGED CYCLE IS A WARNING A CLERK ACCEPTS WITH A REASON** (PO 2026-08-26,
# CR-038 · closes the Blueprint's Open 1). PO verbatim: 'Open 1 - (a) flag as
# warning, clerk accepts with a reason'. The cycle-membership rule (W2) imports
# the row, flags it by name ('M-4021 belongs to CY-002, file tagged CY-001'),
# and BR-MET-015's disposition discipline applies … Never a silent import
# (today's behavior), never a hard refusal." Membership is the BR-MET-033 stamp
# (`service_points.cycle_id` — the cycle→routes→service-point chain
# `apps.metering.completeness._expected_meters` walks); the service layer
# resolves it onto the ReadContext and this rule only judges.
RULE_CYCLE_MEMBERSHIP = "cycle_membership"
# CR-038 W2 aspect 4 (2026-08-26): "a service-coherence rule (row's service vs
# the meter's real service)". The row's STATED service is its BR-MET-014
# effective tag (row column, else the batch tag); the meter's REAL service is
# its service point's (`services._service_of_asset`). A row that states
# nothing inherits (BR-MET-014) and NEVER flags.
#
# **A STATEMENT THAT DISAGREES WITH THE METER IS A WARNING NAMING BOTH VALUES**
# — CR-054 task 10's own worked case, *"a water meter in a batch tagged
# Electric"*, comes out as `row says electric, meter M-7301 is water`, and it
# comes out that way whether the statement is the ROW's column or the BATCH's
# tag, because BR-MET-014 makes the batch tag the row's effective service.
#
# ⚠ **THIS BLOCK SAID THE RULE COULD ONLY REPORT, AND THAT WAS SUPERSEDED FOUR
# DAYS BEFORE ANYONE READ IT (`DEF-2670`).** Its retired sentence, kept because
# a struck sentence is evidence and a deleted one is not:
#
#   ~~"A stated value that is not an enabled service code cannot be judged —
#   the row's service column has never been validated anywhere (files in the
#   wild carry 'E'), and minting an alias table here would be the snapping
#   `read_import` explicitly forbids — so it reports `not_evaluated` with the
#   value named, never a manufactured warning."~~
#
# **BR-MET-137 (PO 2026-08-26, closing DEF-792, verbatim: *"yes accept them"*)
# ruled the shorthand IN**, so `E` on an electric meter is agreement and `W` on
# it warns; `resolve_stated_service` is the resolver and the four branches of
# `_service_coherence_outcome` are where each clause lands. What survives of
# the struck sentence is its LAST clause only, and it survives unchanged: a
# token that resolves to nothing at all is still `not_evaluated` with the value
# verbatim (clause 3), and an ambiguous letter names both candidates rather
# than picking one (clause 2). CR-054 task 10 was written from the struck text
# and describes work that was already done — see `DEF-2670` for what that cost.
RULE_SERVICE_COHERENCE = "service_coherence"
# CR-054 W1 task 7 (2026-08-30) — THE ROW KEY ROUND TRIP. The generated reading
# sheet stamps each row with the meter and register it was GENERATED FOR
# (`read_import.build_row_key`). A clerk who finds a different meter at the
# stop legitimately types a different meter number over the pre-filled one — a
# meter REPLACEMENT is common and lawful — so the row is imported and FLAGGED
# BY NAME, never silently accepted and never refused: *"row 412 was M-4021, now
# M-4099 — was the meter replaced?"* (CR-054 task 7, verbatim).
#
# The severity and the posture are BR-MET-122's, deliberately: this is the same
# class of fact (the file says one thing, the registry says another, and the
# clerk is the one who can tell which is right), and BR-MET-122's ruling —
# *"flag as warning, clerk accepts with a reason"* — is the nearest signed
# statement in the corpus. Choosing ERROR would refuse a legitimate replacement;
# choosing OK would be the silent import CR-054 was raised to remove. No
# threshold is invented (BR-MET-020): the comparison is two strings.
#
# Membership is nothing to do with it, and this rule NEVER looks at a cycle:
# `RULE_CYCLE_MEMBERSHIP` asks whether the meter belongs to the tagged cycle;
# this asks whether the row is still about the meter it was written for.
RULE_ROW_KEY = "row_key"
# ── BR-MET-1160 (PO 2026-09-02) — THE UNIT THE READ IS PRICED AGAINST ───────
#: **`RULE_UNIT_MISSING`'s SIBLING: the read HAS a unit, and it is not the unit
#: the tariff prices in.**
#:
#: PO ruling 2026-09-02, verbatim: *"refula at the time of billing - it will be
#: too late to act , we have to ensure wehn we upload reading at that time it is
#: check and corrected"* — said on being told the ENGINE already refuses the
#: pair at bill time (`rating.pricing.stages.normalize._gate_uom`,
#: `BR-RAT-038`) and the rate wizard already warns at save
#: (`rating.selectors.uom_gate`, `DEF-3108`). Neither of those is where a
#: person can act: **a bill run refused at 2am has nobody at the screen**, on a
#: reading accepted hours earlier. At UPLOAD a clerk is standing at the import
#: screen with the batch in front of them and the mismatch is a correction they
#: can make on the row that caused it.
#:
#: THE MONEY, so the rule is not read as tidiness. `SERVICE_DEFAULT_UOMS["gas"]`
#: plants a register reading **therm**; the billing workbook signs **Gas flat
#: $1.15/ccf**. One therm of pipeline gas is about `0.9643 ccf`, so a `42`-unit
#: read priced per ccf bills **$48.30** where the honest figure is about
#: **$46.58** — roughly **4% over, `$1.72` a month on one meter**, on a bill
#: that foots and that nothing objected to.
#:
#: WHAT IT COMPARES, AND WHY THOSE TWO STRINGS. Left: the REGISTER's own unit
#: (`register_units.register_unit`, `BR-MET-143`) — the unit this quantity was
#: measured in, which is CLAUDE.md hard rule 3's subject. Right: the RATE
#: SCHEDULE's `uom`, resolved through the unit's plan
#: (`completeness.PlanRegisterResolver.pricing_unit_for_asset`) — the same
#: string `_gate_uom` will refuse the bill against. **Not
#: `tenant_services.billed_uom`**, which is NULL on every tenant ever
#: provisioned and is why the save-time gate was blind for as long as it
#: existed (`DEF-3108`).
#:
#: THE VERDICT IS `BR-MET-143`'s AND IS NOT RE-DECIDED HERE. The rule calls
#: `register_units.reconciliation` — the ONE implementation of
#: scale-versus-dimension, the same one rating reaches through its own seam —
#: and reads the severity off its `kind`:
#:
#:   · `dimension`  → **ERROR**. `therm` is ENERGY and `ccf` is VOLUME: no
#:     multiplier and no `conversion_factor` reconciles them, because the
#:     conversion needs a heating value, which is a physical fact about the gas
#:     and not a column on a table. Nothing a clerk types on the import screen
#:     can make this bill; the fix is a different unit on the meter or on the
#:     schedule, so the row is refused and both are named.
#:   · `scale`      → **WARNING**, and this severity is RATIFIED ELSEWHERE
#:     rather than chosen here: `US-RAT-005 TC-7` is signed *"warn now, rating
#:     blocked later"* for two units of the same kind, and reversing a signed
#:     test case is a finance/PO re-sign (HUMAN-GUIDE §6), never a lane's
#:     change in passing. `kgal` against `ccf` is that case.
#:   · `unknown_dimension` → **WARNING**. This repo has not been told what one
#:     of the units measures. Escalating to ERROR would be refusing a row on
#:     *"we do not know"* — stricter than the ratified same-dimension case with
#:     strictly less knowledge — and a wrong-remedy refusal is worse than a
#:     long one.
#:   · `match`      → OK.
#:
#: ⚠ **NOTHING IS AUTO-FIXED AND NO THRESHOLD IS INVENTED** (`BR-MET-052`,
#: `BR-MET-020`): the comparison is two strings and a declared dimension map,
#: and every outcome carries its resolutions (`BR-MET-022`) naming a screen a
#: clerk can actually reach — the meter's UoM, or the rate schedule's.
#:
#: ⚠ **ENG PLACEMENT NOTE — THIS IS A JUDGMENT RULE BECAUSE THE PO's LIST SAYS
#: SO, AND THE GAP IS RAISED RATHER THAN CLOSED (`OQ-1330`).** `BR-MET-136`
#: defines the integrity set BY NAME (seven rules) and everything else by
#: subtraction, so a tenant CAN switch this off. It fails safe if they do — the
#: engine still refuses the bill by name — but a check on a money path that a
#: setting can silence deserves the PO's word rather than this file's, which is
#: exactly the posture `RULE_GENERATION_CHANNEL` takes for `OQ-417`.
RULE_UNIT_MISMATCH = "unit_mismatch"

# Rules whose THRESHOLD is not ratified anywhere in the corpus. They are named
# in BR-MET-021's vocabulary and in US-MET-011's TCs, but neither B2 r5 #15
# (the approved `read_validation_settings` column set) nor US-MET-011 §5's
# field map defines the number they would compare against — TC-5 says only
# "the suspicion basis". BR-MET-020 forbids inventing one, and no OQ id exists
# to stub against, so the engine emits `not_evaluated` and the batch reports
# it. Raised to the PO in the lane report; a threshold column + a seeded value
# closes it.
UNRATIFIED_RULES: tuple[str, ...] = (RULE_FACTOR,)

# ── CR-038 A1: the INTEGRITY rules S64 shows LOCKED ─────────────────────────
# The PO's working assumption (flagged for confirmation in the CR): thresholds
# are editable, every rule always RUNS, and there is NO per-service kill
# switch — a utility cannot turn off "the meter must exist" or "a reading
# cannot go backwards". These rules take no threshold from config at all, so
# there is nothing on S64 for them BUT the statement that they run; the screen
# reads this tuple through the API so the engine and the page cannot disagree
# about which rules are beyond editing.
INTEGRITY_RULES: tuple[str, ...] = (
    RULE_UNKNOWN_METER,
    RULE_RETIRED_METER,
    RULE_UNIT_MISSING,
    RULE_NEGATIVE_USAGE,
    RULE_ROLLOVER,
    RULE_DUPLICATE,
    RULE_EXPORT_NOT_NET,
)

# ── BR-MET-136 · the SWITCHABLE half: the JUDGMENT rules ────────────────────
#: Every rule name this engine can emit, in catalog order. Written out rather
#: than scraped from the module namespace so that adding a rule constant is a
#: DELIBERATE act with respect to BR-MET-136: a new rule lands in exactly one
#: of the two lists below, and a reviewer can see which.
ALL_RULES: tuple[str, ...] = (
    # integrity (locked — INTEGRITY_RULES below is the same seven)
    RULE_UNKNOWN_METER,
    RULE_RETIRED_METER,
    RULE_UNIT_MISSING,
    RULE_NEGATIVE_USAGE,
    RULE_ROLLOVER,
    RULE_DUPLICATE,
    RULE_EXPORT_NOT_NET,
    # judgment (switchable per (tenant, service) — BR-MET-136 clause 1)
    RULE_ZERO,
    RULE_HIGH,
    RULE_LOW,
    RULE_DAYS_THRESHOLD,
    RULE_OUT_OF_WINDOW,
    RULE_VACANT_UNIT,
    RULE_TOU_SUM_SANITY,
    RULE_MISMATCH,
    RULE_FACTOR,
    RULE_GENERATION_CHANNEL,
    RULE_PLAN_REGISTERS,
    RULE_CYCLE_MEMBERSHIP,
    RULE_SERVICE_COHERENCE,
    RULE_ROW_KEY,
    RULE_UNIT_MISMATCH,
)

#: BR-MET-136 clause 1, verbatim: *"A judgment rule carries an ENABLED flag per
#: (tenant, service) — so a utility CAN retire a check that does not fit their
#: business."* The ruling defines the judgment set by SUBTRACTION — it names
#: the seven integrity rules and everything else is a judgment rule — so this
#: is derived, never hand-listed, and the two sets cannot drift apart.
#:
#: ⚠ **`generation_channel` IS IN THIS LIST BECAUSE THE RULING PUT IT HERE, AND
#: AN OPEN QUESTION IS OWED (OQ-417).** It is a HARD ERROR with no threshold —
#: a PV inverter's figure landing in a consumption register — and it is the
#: exact mirror image of `export_not_net`, which the PO locked BY NAME. The PO
#: named seven rules; a signature covers only what was shown, and
#: `generation_channel` was ruled 2026-08-26 in BR-MET-135 by a different
#: sitting that never mentioned switches. Choosing to lock it here would be
#: this engine amending the PO's list on its own authority, so it does not:
#: the ruling is followed literally and the gap is raised, not closed.
JUDGMENT_RULES: tuple[str, ...] = tuple(r for r in ALL_RULES if r not in INTEGRITY_RULES)

# Reasons a rule reports instead of a verdict.
REASON_NO_CONFIG = "validation_config_missing"  # US-MET-011/TC-9 fail-safe
REASON_NO_PRIOR = "no_prior_read"
REASON_NO_HISTORY = "no_trailing_history"
REASON_NO_THRESHOLD = "threshold_not_ratified"
REASON_NO_FLOOR = "absolute_floor_unavailable_for_unit"  # OQ-004: never convert silently
REASON_SEAM_UNWIRED = "occupancy_seam_unwired"
REASON_NO_CYCLE_WINDOW = "cycle_window_not_set"
REASON_INCOMPLETE_GROUP = "channel_group_incomplete"
# BR-MET-049: the expected register set could not be RESOLVED — no plan on the
# unit, rating unwired, no version in force, a window whose channel was never
# stated (BR-RAT-067), … The caller passes the SPECIFIC reason (the
# `apps.metering.completeness` absence vocabulary); this is only the fallback
# when it somehow passes none, so the gap is never silent.
REASON_PLAN_SET_UNRESOLVED = "plan_register_set_unresolved"
# BR-MET-122: a batch with no cycle tag SKIPS the membership rule with this
# stated reason — a cycle-less batch has no membership expectation to judge
# (the same posture `batch_cycle_coverage` takes for coverage).
REASON_NO_CYCLE_TAG = "batch_not_tagged_with_cycle"
# CR-054 W1 task 7: the cell was there and this grammar could not read it. A
# STATED absence, never a manufactured warning — the same posture
# `_parse_demand_reset` takes for a reset spelling nobody recognises, and the
# same reason: a failure to KNOW is not a finding.
REASON_ROW_KEY_UNREADABLE = "row_key_unrecognised"
# Service coherence: the meter's real service could not be resolved (no
# service point / no service on it) — no coherence claim can be judged.
REASON_METER_SERVICE_UNRESOLVED = "meter_service_unresolved"
# Service coherence: the row states a value that resolves to nothing at all in
# this tenant's ENABLED set — not a full code, and not a single letter any
# enabled code starts with (BR-MET-137 clause 3, unchanged by that ruling).
# `zebra`, not `E`. The rule reports the gap with the value verbatim rather
# than inventing an alias or manufacturing a warning.
REASON_STATED_SERVICE_UNRECOGNIZED = "stated_service_not_an_enabled_service"
# Service coherence, BR-MET-137 (PO 2026-08-26, closes DEF-792): the row states
# a SINGLE LETTER and the tenant's enabled set makes it mean two things — `S`
# where both sewer and solar are sold, `T` where both trash and thermal are.
# The rule does NOT pick one. A silently-chosen service prices the wrong charge,
# so both candidates are named and the file is asked to state the full code.
REASON_SERVICE_SHORTHAND_AMBIGUOUS = "service_shorthand_ambiguous"
# ── CR-038 W6 (BR-MET-125 / DEF-791) — the master-vs-subs group rule ────────
#: At least one sub-meter had no usable figure for the period, so Σ subs is
#: SHORT. Reported instead of a gap, because a smaller Σ reads exactly like a
#: larger unaccounted loss and the two are opposite facts.
REASON_SUBMETER_SET_INCOMPLETE = "submeter_sum_incomplete"
#: The master has no sub-meters at all — nothing to reconcile against. A master
#: whose subs were removed must not report a 100% gap.
REASON_NO_SUBMETERS = "asset_has_no_submeters"
#: The read is a DEVICE's (BR-MET-124/135), so a meter rule that has no meaning
#: on it is SKIPPED AND REPORTED — never faked, and never silently absent.
REASON_DEVICE_READ = "device_read_meter_rule_not_applicable"
# ── BR-MET-1160 · the two ways the unit-mismatch rule cannot judge ──────────
#: The unit that PRICES this meter could not be resolved. The caller passes the
#: SPECIFIC reason (`completeness`'s pricing-unit absence vocabulary — rating
#: unwired, no plan on the unit, the plan naming no schedule for this service,
#: no version in force on the read's date, the schedule stating no unit); this
#: is only the fallback when it somehow passes none, so the gap is never
#: silent. **It is never read as "the units agree"** — that is the DEF-075
#: lesson, and here it would be a silent 4%.
REASON_PRICING_UNIT_UNRESOLVED = "pricing_unit_unresolved"
#: A MAXIMUM register (`register_units.MAXIMUM_REGISTERS` — demand today) is
#: deliberately NOT gated against the energy schedule's unit, and this reports
#: that rather than leaving the rule silently absent.
#:
#: The reason is `rating.pricing.stages.normalize._peak_demand`'s own, verbatim:
#: *"the demand read is in kW and the energy beside it is in kWh, so gating it
#: against the ENERGY's unit would refuse every demand bill there is"*. The
#: demand register is priced by `rate_schedules.demand_rate_per_kw` and by
#: nothing this rule can see, so hard rule 3's gate on a peak is *"has a unit"*
#: (`unit_missing`, which does run) and not *"matches"*.
REASON_MAXIMUM_REGISTER = "maximum_register_not_priced_by_schedule_uom"

# OQ-002 closure: the absolute floor is expressed per UoM. These are the two
# units the ratified config carries a column for — a read in any other unit
# reports REASON_NO_FLOOR rather than being converted or compared bare.
_FLOOR_COLUMN_BY_UNIT = {"kwh": "high_abs_kwh", "kgal": "high_abs_kgal"}


@dataclass(frozen=True)
class Outcome:
    """One rule's verdict, self-describing per BR-MET-022/056."""

    rule: str
    severity: str
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "severity": self.severity, "detail": self.detail}


@dataclass
class ReadContext:
    """Everything one staged/committed read needs to be judged, assembled by
    the service layer. Every field is explicit — nothing is inferred here."""

    value: Decimal | None = None  # the current register reading
    read_at: datetime | None = None
    channel: str = "total"
    unit: str | None = None  # the asset's EXPLICIT UoM (CLAUDE.md rule 3)
    multiplier: Decimal | None = None
    register_digits: int | None = None  # rollover span = 10 ** digits (B4/GT-14)
    asset_known: bool = True
    asset_retired_on: date | None = None  # non-None ⇒ retired (BR-MET-052)
    prior_value: Decimal | None = None
    prior_read_at: datetime | None = None
    # Trailing ACTUAL consumptions (estimates excluded — BR-MET-026 discipline
    # applies to the flag basis too: an estimate must not move the average it
    # is compared against). Newest first; each is (consumption, day_count).
    trailing_actuals: list[tuple[Decimal, int]] = field(default_factory=list)
    # Duplicate inputs (BR-MET-016/052).
    duplicate_of_read_id: str | None = None  # a committed head at the same key AND value
    # BR-MET-1189 (PO 2026-10-04): a committed head at the same key with a
    # DIFFERENT value — a second reading of that register that day, KEPT.
    same_day_sibling_read_id: str | None = None
    duplicate_of_row_no: int | None = None  # an earlier row in the SAME batch
    same_cycle_unchanged_read_id: str | None = None  # BR-MET-016 second clause
    # Occupancy (BR-MET-052 vacant_unit). None = the customers seam could not
    # answer — reported, never read as "vacant".
    unit_occupied: bool | None = None
    # Cycle read-window (BR-MET-057) — both ends or the rule cannot run.
    cycle_window_start: date | None = None
    cycle_window_end: date | None = None
    # Unit conversion for the absolute floor (OQ-004 closure): the tenant's
    # configured factor from the register unit to the billed unit, or None.
    #
    # ⚠ `billed_unit` IS THE DECLARED COLUMN (`tenant_services.billed_uom`) AND
    # IS NULL ON EVERY TENANT THIS PRODUCT HAS EVER PROVISIONED — nothing seeds
    # it (`DEF-3108`). That is harmless for the absolute floor, which fails safe
    # and reports `REASON_NO_FLOOR`; it would be fatal for BR-MET-1160, which is
    # why that rule compares against `pricing_unit` below and never against
    # this. Do not "improve" this field into an effective unit: the high rule's
    # floor would silently start firing where it correctly reports a gap today.
    billed_unit: str | None = None
    conversion_factor: Decimal | None = None
    # ── BR-MET-1160 (PO 2026-09-02): the unit the TARIFF prices in ───────────
    #: The rate schedule's own `uom` for this meter's service on this read's
    #: date, resolved by the caller through the unit's plan
    #: (`completeness.PlanRegisterResolver.pricing_unit_for_asset`). It is the
    #: SAME STRING `rating.pricing.stages.normalize._gate_uom` will refuse the
    #: bill against, so a read this rule passes is a read the run will price.
    pricing_unit: str | None = None
    #: WHY `pricing_unit` is None, in `completeness`'s absence vocabulary. The
    #: engine never queries; the caller resolves it. `None` here with a `None`
    #: unit means the caller passed no reason at all, and the rule still
    #: reports rather than falling through to "the units agree".
    pricing_unit_absent_reason: str | None = None
    #: The plan the pricing unit came from, for the self-describing detail
    #: (BR-MET-022/056) — a clerk asking "priced against what?" gets an answer.
    pricing_plan_id: str | None = None
    # BR-AST-010/029: is this asset a net meter? None = not asked (the caller
    # did not resolve an asset), which is why the rule below tests `is False`
    # and not falsiness — "we do not know" must never read as "not a net meter".
    asset_net_metering: bool | None = None
    # ── CR-038 W6 (BR-MET-124/135) — IS THIS A DEVICE? ─────────────────────
    #: `asset_types.category` (BR-AST-004's tab key): `meters` · `sub_meters` ·
    #: `behind_the_meter`. A DEVICE is `behind_the_meter` — a PV inverter, a
    #: battery, a generator — and that is the ONE fact separating it from a
    #: meter. It is a CATEGORY and not a type CODE deliberately: a tenant may
    #: add its own device types (BR-TEN-036) and every one of them lands on the
    #: BTM tab, so a category test covers types nobody has invented yet where a
    #: `code == "pv"` test would silently treat them as meters.
    #:
    #: None = the caller did not resolve an asset's type. Every rule below
    #: tests `is_device is True` explicitly, never falsiness: "we do not know"
    #: must not read as "this is a meter" and quietly re-enable sixteen meter
    #: rules on an inverter.
    asset_category: str | None = None
    # Master/sub reconciliation (BR-MET-025), when this read is a master's.
    submeter_consumption_sum: Decimal | None = None
    loss_tolerance_pct: Decimal | None = None
    # CR-038 A1: WHICH service's thresholds judge this read. The asset's own
    # service (services._service_of_asset); None when the asset carries no
    # service point. `resolve_config` and the service-coherence rule read it.
    service_code: str | None = None
    # ── CR-038 W2 (2026-08-26) — mixed-cycle facts, resolved by the caller ──
    # The meter's number, for the NAMED messages BR-MET-122 asks for
    # ("M-4021 belongs to CY-002, file tagged CY-001").
    meter_no: str | None = None
    # The batch's cycle tag (None = the batch was not tagged with a cycle —
    # the membership rule skips with a stated reason).
    batch_cycle_id: str | None = None
    batch_cycle_code: str | None = None
    # The meter's OWN cycle, via the BR-MET-033 membership stamp
    # (`service_points.cycle_id`). None = the meter is in NO cycle.
    meter_cycle_id: str | None = None
    meter_cycle_code: str | None = None
    # The row's STATED service — its BR-MET-014 effective tag (the row column,
    # else the batch tag). None = nothing stated anywhere: the read inherits
    # the meter's service and the coherence rule never flags.
    stated_service: str | None = None
    # The tenant's enabled service codes (BR-MET-003's outer bound), so the
    # coherence rule can tell a real disagreement from an unvalidated value.
    # The engine never queries — the caller resolves this once per batch.
    enabled_services: tuple[str, ...] | None = None
    # ── CR-054 W1 task 7 (2026-08-30) — the row key, resolved by the caller ──
    #: The key the generated reading sheet stamped on this row, VERBATIM.
    #: None = the file carried none (a hand-built file, the blank template, the
    #: manual grid) and there is nothing to judge.
    row_key: str | None = None
    #: The row's number in the file, for the NAMED message CR-054 task 7 asks
    #: for (*"row 412 was M-4021, now M-4099"*). The engine holds no file, so
    #: the caller passes it — the same way `meter_no` arrives for BR-MET-122.
    row_no: int | None = None

    @property
    def is_device(self) -> bool | None:
        """True for a behind-the-meter DEVICE, False for a meter, None when the
        caller could not resolve the asset's type (never read as either)."""
        if self.asset_category is None:
            return None
        return self.asset_category == CATEGORY_BEHIND_THE_METER


# ── consumption (BR-MET-019 + the OQ-009 rollover closure) ──────────────────

# The OQ-009 closure / GT-14 span check, written the way the ruling writes it:
# "> 50% of the register span". This is the RULE's own fraction, not a tenant
# threshold — BR-MET-020 governs the numbers a tenant configures, and this is
# not one of them; it is the definition of a wrap. It is named so the single
# comparison below reads like the ruling and so a test can drive that
# comparison RED by moving it.
ROLLOVER_SPAN_FRACTION = Decimal("0.5")

# `RegisterDelta.kind` when the register simply advanced. The wrap and the
# bad-read kinds reuse the rule names above (RULE_ROLLOVER / RULE_NEGATIVE_USAGE)
# so a caller never has to translate between two vocabularies.
DELTA_NORMAL = "normal"


@dataclass(frozen=True)
class RegisterDelta:
    """How one (prior, current) register pair resolves, plus the working.

    `kind` is `DELTA_NORMAL`, `RULE_ROLLOVER` or `RULE_NEGATIVE_USAGE`.
    `consumption` is None for the last of those and ONLY for that one: a value
    the engine cannot compute honestly is never invented (BR-MET-052 — nothing
    is auto-fixed, by law). No unit travels on this type; it is register
    arithmetic, and the unit is attached by the caller that knows the asset
    (CLAUDE.md rule 3 — see apps/metering/quantities.py).
    """

    kind: str
    consumption: Decimal | None
    prior: Decimal
    current: Decimal
    multiplier: Decimal
    register_digits: int | None = None
    span: Decimal | None = None
    drop: Decimal | None = None
    wrapped_delta: Decimal | None = None


def register_span(register_digits: int) -> Decimal:
    """BR-AST-015: an N-digit register rolls over at 10**N.

    The span is an ASSET fact. It is a parameter here — never a default —
    because a wrap computed against an assumed span is precisely the silent
    fix the rollover rule exists to prevent.
    """
    return Decimal(10) ** int(register_digits)


def classify_register_delta(
    *,
    prior: Decimal,
    current: Decimal,
    multiplier: Decimal,
    register_digits: int | None = None,
) -> RegisterDelta:
    """BR-MET-019 + the OQ-009 rollover closure as PURE register arithmetic.

    The ONE implementation of the wrap rule in this codebase. `compute_consumption`
    below dresses it in the flag vocabulary for the read engine; the published
    metering seam (`apps/metering/quantities.py`) dresses it in a unit for the
    B5 golden fixtures. Neither re-derives it.

      * `current >= prior`  -> `(current − prior) × multiplier`, unrounded
        NUMERIC(18,6) (B4.4 puts rounding at invoice-line finalization, never
        here — and nothing in this module produces money at all).
      * `current < prior` AND a KNOWN span AND `(prior − current) >` 50% of that
        span -> the register wrapped: `((span − prior) + current) × multiplier`
        (GT-4 / GT-14: `(100,000 − 99,800) + 240 = 440`).
      * anything else negative -> `RULE_NEGATIVE_USAGE` with NO consumption.
        That includes an unknown span: with no `register_digits` there is no
        span, so no wrap can be claimed, and guessing a 5-, 6- or 9-digit
        register would be inventing the asset fact the rule turns on.

    The `× multiplier` on the wrap branch follows BR-MET-019's general form
    (register delta × multiplier). GT-14's fixture is ×1 and so does not
    discriminate; recorded as an Eng reading, unchanged from the read lane.
    """
    delta = current - prior
    digits = int(register_digits) if register_digits else None
    if delta >= 0:
        return RegisterDelta(
            kind=DELTA_NORMAL,
            consumption=delta * multiplier,
            prior=prior,
            current=current,
            multiplier=multiplier,
            register_digits=digits,
        )

    drop = prior - current
    if digits:
        span = register_span(digits)
        if drop > span * ROLLOVER_SPAN_FRACTION:  # >50% of span ⇒ a wrap, not a bad read
            wrapped = (span - prior) + current
            return RegisterDelta(
                kind=RULE_ROLLOVER,
                consumption=wrapped * multiplier,
                prior=prior,
                current=current,
                multiplier=multiplier,
                register_digits=digits,
                span=span,
                drop=drop,
                wrapped_delta=wrapped,
            )

    return RegisterDelta(
        kind=RULE_NEGATIVE_USAGE,
        consumption=None,
        prior=prior,
        current=current,
        multiplier=multiplier,
        register_digits=digits,
        drop=drop,
    )


def compute_consumption(ctx: ReadContext) -> tuple[Decimal | None, Outcome | None]:
    """`(current − prior) × multiplier` in NUMERIC(18,6), UNROUNDED (B4.4 —
    rounding happens only at invoice-line finalization, and never here).

    Returns `(consumption, outcome)` where `outcome` is the rollover warning or
    the negative-usage hard error when either applies, else None.

    Rollover (OQ-009 CLOSED, PO R7 — GT-14): `current < prior` AND
    `(prior − current) > 50% of the register span` ⇒ the register wrapped, so
    consumption = `((10**digits − prior) + current) × multiplier`, FLAGGED for
    review. Anything else negative is the BR-MET-052 hard error — this function
    returns no consumption for it, because a value the engine cannot compute
    honestly must not be invented (there is no auto-fix, by law).

    The arithmetic itself lives in `classify_register_delta` above and is NOT
    repeated here — this function is the flag-engine's dressing of that one
    result (BR-MET-021's vocabulary, BR-MET-022/056's self-describing detail).
    """
    # ── CR-038 W6 (BR-MET-124/135): A DEVICE'S FIGURE IS NOT A REGISTER ────
    # The PO's driving case is *"a solar inverter's monthly generation, e.g.
    # 612 kWh"* — a PERIOD QUANTITY, already the answer. There is nothing to
    # subtract a prior from, and doing it anyway is the defect this branch
    # exists to prevent: last month's 612 taken off this month's 640 would
    # store 28 kWh of generation for a month that produced 640, and every check
    # in this file would pass over it.
    #
    # ⚠ **THE MULTIPLIER IS NOT APPLIED, AND THAT IS REPORTED.** `multiplier`
    # is a REGISTER factor (a CT ratio) and it scales a delta; a device's
    # produced quantity is what the inverter says it produced. Scaling it by a
    # column meant for register arithmetic would change a number no ruling
    # covers. It defaults to 1 so nothing moves today — named rather than left
    # to be discovered when a tenant sets it to 40.
    if ctx.is_device is True:
        return ctx.value, None

    # ── BR-MET-143 / DEF-797: A MAXIMUM REGISTER IS NOT A RUNNING TOTAL ─────
    # ⛔ **THIS IS THE DEFECT'S QUANTITY HALF, AND IT WAS CUSTOMER-FACING
    # MONEY.** BR-MET-051, verbatim: *"Demand: manual demand-register VALUE at
    # cycle read"*. Until 2026-08-27 this function ran `(current − prior) ×
    # multiplier` on EVERY channel, so a demand register — a maximum, not a
    # counter — reported the DIFFERENCE BETWEEN TWO PEAKS. Measured on the
    # Industrial schedule: peaks 398 → 412 committed `consumption=14.000000`
    # and the bill line read *"electric demand · peak 14.000000 kWh ·
    # $154.00"* against a correct **412 kW × $11.00 = $4,532.00** — one
    # commercial account under-billed by **$4,378.00 in a single month**, with
    # the wrong unit printed on an issued document.
    #
    # The arithmetic itself is `register_units.billable_quantity`, which owns
    # BOTH branches so a future maximum register (peak kVA, max flow) joins the
    # rule in one place instead of growing a second `if channel == …` here.
    #
    # **No rollover and no negative-usage verdict can apply.** Both are
    # statements about a COUNTER: a peak that falls from 412 to 90 is a quiet
    # month, not a wrap and not a hard error, and BR-MET-051's *"reset noted"*
    # is the fact that already records a demand reset. Returning a verdict here
    # would train a clerk to dismiss the flag that matters.
    if register_units.is_maximum_register(ctx.channel):
        return (
            register_units.billable_quantity(
                channel=ctx.channel,
                value=ctx.value,
                multiplier=ctx.multiplier,
                delta_consumption=None,
            ),
            None,
        )

    if ctx.value is None or ctx.prior_value is None or ctx.multiplier is None:
        return None, None

    resolved = classify_register_delta(
        prior=ctx.prior_value,
        current=ctx.value,
        multiplier=ctx.multiplier,
        register_digits=ctx.register_digits,
    )

    if resolved.kind == DELTA_NORMAL:
        return resolved.consumption, None

    if resolved.kind == RULE_ROLLOVER:
        return resolved.consumption, Outcome(
            RULE_ROLLOVER,
            WARNING,
            {
                "prior": str(resolved.prior),
                "current": str(resolved.current),
                "register_digits": resolved.register_digits,
                "register_span": str(resolved.span),
                "wrapped_delta": str(resolved.wrapped_delta),
                "multiplier": str(resolved.multiplier),
                "consumption": str(resolved.consumption),
                "unit": ctx.unit,
                # B14 rule 31 — the provenance MOVES to this comment rather than
                # being deleted: `OQ-009`'s closure and `GT-14` are what set
                # the half-span test this string describes.
                "basis": "the drop exceeds half the register span",
            },
        )

    return None, Outcome(
        RULE_NEGATIVE_USAGE,
        ERROR,
        {
            "prior": str(resolved.prior),
            "current": str(resolved.current),
            "drop": str(resolved.drop),
            "register_digits": resolved.register_digits,
            "auto_fix": False,  # BR-MET-052: never, by law
            "resolutions": ["investigate", "override", "reject"],
        },
    )


# ── config access (BR-MET-020: config or nothing) ───────────────────────────

# CR-038 A1: the two services whose figures the legacy tenant-wide row was
# actually RATIFIED for (OQ-002's floors are 50 kWh and 1 kgal — electric's
# and water's units). Where no per-service row exists, ONLY these two fall
# back to that row, so their behavior is byte-identical to before this
# amendment; every other service without a row keeps the TC-9 fail-safe.
LEGACY_FALLBACK_SERVICES: tuple[str, ...] = ("electric", "water")


@dataclass(frozen=True)
class ConfigSet:
    """The tenant's WHOLE validation config, assembled by the service layer
    (CR-038 A1): the legacy tenant-wide row plus the per-service rows keyed by
    service code. Pure data — the ORM never enters this module.

    `resolve_config` turns it into the ONE config object a read is judged by.
    Callers that still pass a bare tenant row (older tests, single-tenant
    paths) are untouched: `resolve_config` passes anything that is not a
    ConfigSet straight through."""

    tenant_row: Any = None
    service_rows: dict[str, Any] = field(default_factory=dict)

    @property
    def any_config(self) -> bool:
        """Whether ANY validation config exists for this tenant — the honest
        input to the batch summary's `validation_config_present`, which a bare
        `config is not None` would answer wrongly on an empty ConfigSet."""
        return self.tenant_row is not None or bool(self.service_rows)


def resolve_config(config: Any, service_code: str | None) -> Any:
    """The config object THIS read's thresholds come from (CR-038 A1).

    Resolution order, per the PO's ruling ("we will ahev to set these rules in
    settings and take it from there"):

      1. the (tenant, service) row, when one exists for the read's service;
      2. else the legacy tenant-wide row — for ELECTRIC and WATER only, so
         existing behavior is unchanged where no per-service row exists;
      3. else None — the threshold rules report `validation_config_missing`
         and are SKIPPED, exactly the US-MET-011 TC-9 fail-safe (a read on a
         service with no ratified figures is never judged by another
         service's numbers).

    A read whose service is UNKNOWN (no service point on the asset) resolves
    to None on a ConfigSet: no service's thresholds can honestly claim it.
    That narrows the old behavior (the tenant row used to judge every read
    regardless of service) and it narrows it VISIBLY — every skipped rule is
    reported per row and in the batch's `unevaluated_rules`.

    Anything that is not a ConfigSet passes through unchanged, so callers
    holding a bare tenant row (or None) behave exactly as before."""
    if not isinstance(config, ConfigSet):
        return config
    if service_code:
        row = config.service_rows.get(service_code)
        if row is not None:
            return row
        if service_code in LEGACY_FALLBACK_SERVICES:
            return config.tenant_row
    return None


# ── BR-MET-136 · the ENABLED switch, resolved and applied ───────────────────

#: The reason a `disabled` outcome carries. One value, so a screen, a report or
#: a grep can find every rule a tenant switched off without parsing prose.
REASON_TENANT_DISABLED = "disabled_by_tenant_setting"

#: The settings column the switch map lives in. Named here because THIS module
#: defines the vocabulary the map is keyed by; `models.ReadValidationServiceSettings`
#: declares the column and its docstring argues the shape.
SWITCH_FIELD = "rule_enabled"


def rule_switches(config: Any) -> dict[str, bool]:
    """The (tenant, service) ENABLED map for the config THIS read resolved to.

    BR-MET-136 clause 2, verbatim: *"The default is ALL ENABLED, for every
    service, at provisioning and on backfill."* Three absences all mean all
    enabled, and each of them is a real state in this codebase:

      * `config is None`      — no figures for this service at all (the
        BR-MET-020 fail-safe); no row exists, so no switch was ever set.
      * the LEGACY tenant-wide row — it has no `rule_enabled` column and never
        will; electric/water on fallback run every rule, unchanged.
      * `rule_enabled == {}`  — the column's own default, which is what every
        existing row acquires on backfill and every new row on provisioning.

    **A key that is absent means ENABLED.** That is the whole reason the column
    is a map of the CHOICES a tenant made rather than a full row of flags: the
    default costs no migration, no seed and no backfill pass, so there is no
    window in which an existing tenant can silently acquire a disabled rule.

    BR-MET-136 clause 4 is enforced HERE as well as at the API: an integrity
    rule is forced back to True whatever the stored map says. The API refuses
    the attempt by name, but a row written by a shell, a fixture or a future
    migration would slip past that door — and "the meter must exist" must not
    be switchable off by any path at all.
    """
    raw = getattr(config, SWITCH_FIELD, None) if config is not None else None
    switches = {rule: True for rule in ALL_RULES}
    if isinstance(raw, dict):
        for rule, enabled in raw.items():
            if rule in JUDGMENT_RULES:
                switches[rule] = bool(enabled)
    return switches


def switch_outcome(outcome: Outcome, switches: dict[str, bool]) -> Outcome:
    """One rule's verdict, or the STATEMENT that the tenant switched it off.

    BR-MET-136's trailing clause, verbatim: *"a disabled rule must state on the
    read that it was disabled rather than vanish."* A rule that silently
    produces no outcome is indistinguishable from a rule that passed, and the
    whole point of the flag is that somebody CHOSE — so the outcome is
    REPLACED, never dropped.

    ⚠ **The rule still RAN to get here, and that is deliberate.** BR-MET-136
    clause 3 is *"an enabled rule ALWAYS runs — no silent skipping, no
    per-batch bypass"*, and the cheapest way to guarantee it is to leave the
    engine with no skip branch at all: every rule is computed exactly as it was
    before, and this ONE function is the only place in the codebase where a
    computed verdict can be replaced. A branch that skips the computation would
    be a second place an enabled rule could fail to run, and the two would
    drift. The wasted arithmetic is a few Decimal comparisons per row; the
    alternative is a bypass path nobody can grep for.
    """
    if switches.get(outcome.rule, True):
        return outcome
    return Outcome(
        outcome.rule,
        DISABLED,
        {"reason": REASON_TENANT_DISABLED, "rule_ref": "BR-MET-136"},
    )


def apply_rule_switches(outcomes: list[Outcome], switches: dict[str, bool]) -> list[Outcome]:
    """`switch_outcome` over a row's whole outcome list. Length-preserving by
    construction — the count of outcomes on a read never changes because a
    tenant turned a check off, only what one of them SAYS."""
    return [switch_outcome(o, switches) for o in outcomes]


def switch_group_outcome(outcome: Outcome, config: Any, service_code: str | None) -> Outcome:
    """`switch_outcome` for a GROUP rule, which resolves its own config.

    The three group rules — `tou_sum_sanity`, `plan_register_completeness` and
    the master/sub `mismatch` — are computed OUTSIDE `evaluate_row`, once per
    (meter, date) group, so they cannot ride its switch pass. They take this
    door instead, and it is the only other one: two doors, both named
    `switch_*`, and `grep -n "switch_.*outcome" apps/metering/` finds every
    place in the product where a rule's verdict can be replaced.
    """
    return switch_outcome(outcome, rule_switches(resolve_config(config, service_code)))


def disabled_rules(outcomes: list[Outcome]) -> list[dict[str, Any]]:
    """Every rule the tenant switched OFF, for the batch summary — the exact
    mirror of `unevaluated()` and deliberately a SEPARATE list from it (see
    `DISABLED`'s own comment: a gap and a choice are different facts)."""
    return [
        {"rule": o.rule, "reason": o.detail.get("reason")}
        for o in outcomes
        if o.severity == DISABLED
    ]


def _threshold(config: Any, name: str) -> Decimal | int | None:
    if config is None:
        return None
    return getattr(config, name, None)


def _no_config(rule: str) -> Outcome:
    return Outcome(rule, NOT_EVALUATED, {"reason": REASON_NO_CONFIG})


def _trailing_average(ctx: ReadContext) -> Decimal | None:
    """Mean consumption of the trailing ACTUAL reads (OQ-002 closure basis:
    trailing-12-month average, trailing-3 when history is short — the service
    layer decides which window it hands over; this is the arithmetic half)."""
    if not ctx.trailing_actuals:
        return None
    total = sum((c for c, _days in ctx.trailing_actuals), Decimal("0"))
    return total / Decimal(len(ctx.trailing_actuals))


def _absolute_floor(ctx: ReadContext, config: Any) -> tuple[Decimal, str] | None:
    """The OQ-002 absolute floor for THIS read's unit, or None when the tenant
    has not made one available.

    OQ-004 CLOSED is the governing rule for the awkward case (a water register
    stores raw gallons while the floor is per kgal): the register unit must
    MATCH the billed unit or a conversion factor must be configured — on a
    mismatch with no factor the system blocks rather than converting silently.
    So: an exact unit match uses its column; a configured factor converts; and
    anything else returns None, which makes the high rule report
    `absolute_floor_unavailable_for_unit` instead of flagging on ratio alone.
    """
    if config is None or not ctx.unit:
        return None
    unit = ctx.unit.strip().lower()
    # CR-038 A1 — a per-service row carries ONE unit-aware floor
    # (high_abs_value in high_abs_unit, the service's own unit) instead of the
    # legacy per-unit column pair. Shape, not type, decides: the legacy tenant
    # row has no `high_abs_unit` attribute, so it falls through unchanged.
    abs_unit = getattr(config, "high_abs_unit", None)
    if abs_unit is not None:
        floor = _threshold(config, "high_abs_value")
        if floor is None:
            return None
        abs_unit = str(abs_unit).strip().lower()
        if unit == abs_unit:
            return (Decimal(floor), unit)
        # Register unit ≠ the floor's unit: convert ONLY with the tenant's
        # configured factor, and only when it targets the floor's own unit
        # (OQ-004: never a silent conversion).
        billed = (ctx.billed_unit or "").strip().lower()
        if billed != abs_unit or ctx.conversion_factor in (None, 0):
            return None
        return (Decimal(floor) / Decimal(ctx.conversion_factor), unit)
    column = _FLOOR_COLUMN_BY_UNIT.get(unit)
    if column is not None:
        floor = _threshold(config, column)
        return (Decimal(floor), unit) if floor is not None else None
    # Register unit ≠ a floor unit: convert ONLY with the tenant's factor.
    billed = (ctx.billed_unit or "").strip().lower()
    column = _FLOOR_COLUMN_BY_UNIT.get(billed)
    if column is None or ctx.conversion_factor in (None, 0):
        return None
    floor = _threshold(config, column)
    if floor is None:
        return None
    # The floor is expressed in the BILLED unit; express it in the register's.
    return (Decimal(floor) / Decimal(ctx.conversion_factor), unit)


# ── the per-row rules ───────────────────────────────────────────────────────


def _identity_outcomes(ctx: ReadContext) -> list[Outcome]:
    """Errors that make the read unpostable regardless of any threshold."""
    outcomes: list[Outcome] = []
    if not ctx.asset_known:
        # US-MET-008/TC-8: "not in inventory" — never auto-create a meter.
        outcomes.append(
            Outcome(RULE_UNKNOWN_METER, ERROR, {"resolutions": ["fix_meter_id", "reject"]})
        )
        return outcomes
    if ctx.asset_retired_on is not None:
        outcomes.append(
            Outcome(
                RULE_RETIRED_METER,
                ERROR,
                {
                    "retired_on": ctx.asset_retired_on.isoformat(),
                    "resolutions": ["fix_meter_id", "reject"],
                },
            )
        )
    if not ctx.unit:
        # CLAUDE.md rule 3 has no "assume kWh" branch. A measuring asset with
        # no UoM cannot produce a storable consumption, so the row errors here
        # rather than posting a bare number. Eng addition to the catalog —
        # REPORTED (it enforces a hard rule, it does not invent a threshold).
        #
        # ⚠ CR-038 W6: THIS IS THE RULE A DEVICE READ MEETS FIRST. BR-AST-009
        # requires a UoM only on MEASURING types (meter · net_meter ·
        # sub_meter), so a PV inverter lawfully carries none — and a generation
        # figure with no unit is exactly as unusable as any other bare
        # quantity. The row is refused with the DEVICE's own resolution named,
        # because "set the meter's UoM" sends a clerk to the wrong screen.
        outcomes.append(
            Outcome(
                RULE_UNIT_MISSING,
                ERROR,
                {
                    "resolutions": (
                        ["set_device_uom", "reject"]
                        if ctx.is_device is True
                        else ["set_asset_uom", "reject"]
                    ),
                    "asset_category": ctx.asset_category,
                },
            )
        )
    return outcomes


def _unit_mismatch_outcome(ctx: ReadContext) -> Outcome | None:
    """**BR-MET-1160 — the read's unit against the unit the tariff prices in.**

    `RULE_UNIT_MISSING`'s sibling, and it runs one step later: that rule refuses
    a read with NO unit, this one refuses a read whose unit is not the unit the
    bill will be priced in. See `RULE_UNIT_MISMATCH` for the ruling, the money
    and why each severity is what it is.

    Returns None only where there is nothing to say at all: no unit on the read
    (hard rule 3 already refused the row upstream, and a second complaint about
    the same absence would send the clerk to the same screen twice).
    """
    if not ctx.unit:
        # `unit_missing` has already refused this row by name.
        return None
    if register_units.is_maximum_register(ctx.channel):
        # A peak is priced per kW by `demand_rate_per_kw`, not by the
        # schedule's energy `uom` — see REASON_MAXIMUM_REGISTER.
        return Outcome(
            RULE_UNIT_MISMATCH,
            NOT_EVALUATED,
            {"reason": REASON_MAXIMUM_REGISTER, "channel": ctx.channel, "read_uom": ctx.unit},
        )
    if not ctx.pricing_unit:
        return Outcome(
            RULE_UNIT_MISMATCH,
            NOT_EVALUATED,
            {
                "reason": ctx.pricing_unit_absent_reason or REASON_PRICING_UNIT_UNRESOLVED,
                "read_uom": ctx.unit,
            },
        )
    # BR-MET-143's ONE implementation decides scale versus dimension. This rule
    # reads the verdict; it never re-derives it (two answers to that question is
    # how a meter gets planted at x1 on a pair no factor can reconcile).
    verdict = register_units.reconciliation(ctx.unit, ctx.pricing_unit)
    detail: dict[str, Any] = {
        "read_uom": ctx.unit,
        "pricing_uom": ctx.pricing_unit,
        "channel": ctx.channel,
        "meter": ctx.meter_no,
        "reconciliation": verdict.as_dict(),
        # The tenant's DECLARED conversion, so the outcome says what is on file
        # rather than only what is wrong. ⚠ Declaring one does NOT clear this
        # flag: nothing in `apps/billing/` or `apps/rating/pricing/` converts,
        # so the engine still refuses the bill (`DEF-3107`, filed and open).
        "conversion_factor": (
            None if ctx.conversion_factor is None else str(ctx.conversion_factor)
        ),
    }
    if ctx.pricing_plan_id:
        detail["plan_id"] = ctx.pricing_plan_id
    if verdict.matches:
        return Outcome(RULE_UNIT_MISMATCH, OK, detail)
    # Both resolutions are named because we cannot know WHICH side is wrong: a
    # gas utility that meters in therm and prices per ccf has one typo, and it
    # is either on the meter or on the rate schedule. Guessing would send a
    # clerk to the wrong screen — the failure `RULE_UNIT_MISSING`'s own comment
    # records as worse than a long refusal.
    detail["resolutions"] = [
        "fix_schedule_uom",
        "set_device_uom" if ctx.is_device is True else "set_asset_uom",
        "reject",
    ]
    detail["summary"] = (
        f"reading is in {ctx.unit}, the rate schedule prices per {ctx.pricing_unit}"
    )
    if verdict.kind == register_units.DIMENSION:
        # Different KINDS of quantity: no multiplier and no conversion factor
        # reconciles them, so there is no number a clerk can type that makes
        # this bill. It is refused rather than warned.
        return Outcome(RULE_UNIT_MISMATCH, ERROR, detail)
    # SCALE — US-RAT-005 TC-7 is signed "warn now, rating blocked later", and a
    # signed test case moves by re-sign (HUMAN-GUIDE §6), never here.
    # UNKNOWN_DIMENSION — we have not been told what one unit measures, and a
    # refusal on "we do not know" would be stricter with less knowledge.
    return Outcome(RULE_UNIT_MISMATCH, WARNING, detail)


#: The meter rules that have NO MEANING on a device's generation figure. Each
#: is SKIPPED AND REPORTED — BR-MET-124, verbatim: *"the sixteen meter rules
#: that do not apply are skipped and reported, never faked"*.
#:
#: Why each one, because a list with no reasons is a list nobody can correct:
#:
#:   · `zero` / `high` / `low` — every threshold behind them (`zero_scope`,
#:     `high_pct` + the absolute floor, `low_pct`) is a CONSUMPTION figure the
#:     PO ratified for consumption (OQ-002: 50 kWh, 1 kgal). NO figure has ever
#:     been signed for how much a solar month may vary from the last three, and
#:     judging generation by a consumption threshold is precisely the faking
#:     BR-MET-124 forbids. When the PO signs generation bounds, they arrive as
#:     config (BR-MET-020) and these three come off this list.
#:   · `vacant_unit` — the rule exists to catch usage at an address nobody
#:     lives at (BR-MET-129: *"there can be fraud also by people"*). A roof
#:     generates whether or not the flat below it is let; flagging it would
#:     train a clerk to dismiss the flag that matters.
#:   · `negative_usage` / `rollover` — both are REGISTER arithmetic, and a
#:     device has no register in the meter sense: the figure is the period's
#:     production as the inverter reports it, not a counter to subtract from.
#:     There is no span to wrap and no delta to go negative.
#:
#: NOT on this list, deliberately, and each also a reason: `unknown_meter`,
#: `retired_meter` and `unit_missing` are identity and hard rule 3 — they bind
#: any asset. `duplicate` keys on (asset, date, channel), which is as true of an
#: inverter as of a meter. `days_threshold`, `out_of_window` and
#: `cycle_membership` are about COLLECTION CADENCE, not about what the quantity
#: means, and a device read collected off-cycle is worth the same warning.
DEVICE_SKIPPED_RULES: tuple[str, ...] = (
    RULE_ZERO,
    RULE_HIGH,
    RULE_LOW,
    RULE_VACANT_UNIT,
    RULE_NEGATIVE_USAGE,
    RULE_ROLLOVER,
)


def _device_skips() -> list[Outcome]:
    """One reported skip per meter rule that a generation figure cannot be
    judged by. Reported EVERY time, so "0 warnings" on a device read never
    quietly means "we judged it and it was fine"."""
    return [
        Outcome(rule, NOT_EVALUATED, {"reason": REASON_DEVICE_READ, "rule_ref": "BR-MET-124"})
        for rule in DEVICE_SKIPPED_RULES
    ]


def _generation_channel_outcome(ctx: ReadContext) -> Outcome | None:
    """**BR-MET-135: the `generation` register is a DEVICE's, and only a
    device's.** See `RULE_GENERATION_CHANNEL` for the rule's full statement and
    for the Eng-addition flag.

    Silent when the caller could not resolve the asset's category — `is_device`
    is None there, and refusing a row on "we do not know" would block every
    read the moment a type row went missing.
    """
    is_device = ctx.is_device
    if is_device is None:
        return None
    if ctx.channel == CHANNEL_GENERATION and not is_device:
        return Outcome(
            RULE_GENERATION_CHANNEL,
            ERROR,
            {
                "reason": "generation_on_a_meter",
                "channel": ctx.channel,
                "asset_category": ctx.asset_category,
                "meter": ctx.meter_no,
                # `export` is named because it is what a net meter's file
                # usually MEANT — but the row is refused rather than snapped to
                # it, because guessing which of two registers a file meant is
                # how a site's production becomes a customer's usage.
                "resolutions": ["use_export_channel", "fix_meter_id", "reject"],
            },
        )
    if is_device and ctx.channel != CHANNEL_GENERATION:
        return Outcome(
            RULE_GENERATION_CHANNEL,
            ERROR,
            {
                "reason": "device_reading_on_a_consumption_register",
                "channel": ctx.channel,
                "asset_category": ctx.asset_category,
                "meter": ctx.meter_no,
                "resolutions": ["use_generation_channel", "fix_meter_id", "reject"],
            },
        )
    return Outcome(RULE_GENERATION_CHANNEL, OK, {"channel": ctx.channel, "device": is_device})


def _export_outcome(ctx: ReadContext) -> Outcome | None:
    """BR-AST-029: export records belong to net-metering assets and no others.

    An EXPORT register is not consumption (CLAUDE.md rule 3 — the quantity means
    a different thing), so a row claiming one on a plain meter is a hard error
    with no auto-fix: the clerk fixes the file or the asset, and the wizard's
    per-row error pattern excludes the row.
    """
    if ctx.channel != CHANNEL_EXPORT:
        return None
    if ctx.asset_net_metering is False:
        return Outcome(
            RULE_EXPORT_NOT_NET,
            ERROR,
            {
                "reason": "asset_is_not_net_metering",
                "channel": ctx.channel,
                "resolutions": ["fix_meter_id", "enable_net_metering", "reject"],
            },
        )
    return None


def _duplicate_outcome(ctx: ReadContext) -> Outcome | None:
    """BR-MET-016/052 — key (meter, date, channel). The same date on a
    DIFFERENT channel is never a duplicate (US-MET-009/TC-8)."""
    if ctx.duplicate_of_row_no is not None:
        return Outcome(
            RULE_DUPLICATE,
            ERROR,
            {
                "scope": "intra_batch",
                "key": ["asset", "read_at", "channel"],
                "channel": ctx.channel,
                "first_row_no": ctx.duplicate_of_row_no,
                "resolutions": ["keep_one", "reject"],
            },
        )
    if ctx.duplicate_of_read_id is not None:
        # The SAME reading again — same meter, date, register AND value. Not a
        # second reading: it is already in the register, so storing it would
        # add a row and no fact (a re-uploaded file, a wizard re-submitted
        # after a timeout). BR-MET-016 stands for it; the event door answers
        # it as `already_recorded` rather than a refusal (BR-MET-1189 (4)).
        return Outcome(
            RULE_DUPLICATE,
            ERROR,
            {
                "scope": "committed",
                "key": ["asset", "read_at", "channel"],
                "channel": ctx.channel,
                "existing_read_id": ctx.duplicate_of_read_id,
                "same_value": True,
                "resolutions": ["reject", "replace_existing"],
            },
        )
    if ctx.same_day_sibling_read_id is not None:
        # ⚠ **SUPERSEDED FOR THE SAME-DAY PAIR — BR-MET-1189 (PO 2026-10-04,
        # DEF-WRK-9642).** PO verbatim: *"take the reading records in register
        # and use date and highest consumption reading if it is apprved and
        # validated"*. A DIFFERENT value on the same register and date was an
        # ERROR with `reject` / `replace_existing`, which refused every field
        # job closed on a day its meter was already read (WO-0043, E-5000:
        # 3,400 kWh by the office, 3,412 kWh by the technician, Accept refused
        # forever). It is now KEPT: the outcome stays on the row as a FACT
        # (severity OK — it sets no status and blocks nothing) and
        # `counted_reading` decides which of the two counts. A clerk who wants
        # the old reading CORRECTED still has the `override` disposition and
        # the `insert & update` write mode — both supersede, as before.
        return Outcome(
            RULE_DUPLICATE,
            OK,
            {
                "scope": "same_day_second_reading",
                "key": ["asset", "read_at", "channel"],
                "channel": ctx.channel,
                "existing_read_id": ctx.same_day_sibling_read_id,
                "kept": True,
                "br_ref": "BR-MET-1189",
            },
        )
    if ctx.same_cycle_unchanged_read_id is not None:
        return Outcome(
            RULE_DUPLICATE,
            ERROR,
            {
                "scope": "same_cycle_unchanged_value",  # BR-MET-016 second clause
                "channel": ctx.channel,
                "existing_read_id": ctx.same_cycle_unchanged_read_id,
                "resolutions": ["reject", "replace_existing"],
            },
        )
    return None


def _zero_outcome(ctx: ReadContext, consumption: Decimal | None, config: Any) -> Outcome | None:
    """BR-MET-021 zero + the configured scope (US-MET-011 §5 `zero_scope`)."""
    if consumption is None or consumption != 0:
        return None
    if config is None:
        return _no_config(RULE_ZERO)
    scope = (getattr(config, "zero_scope", None) or "").strip()
    if scope == "off":
        return None
    if scope == "active_non_vacant":
        if ctx.unit_occupied is None:
            return Outcome(
                RULE_ZERO, NOT_EVALUATED, {"reason": REASON_SEAM_UNWIRED, "scope": scope}
            )
        if not ctx.unit_occupied:
            return None  # a vacant unit's zero is the vacant_unit warning's business
    return Outcome(RULE_ZERO, WARNING, {"consumption": "0", "unit": ctx.unit, "zero_scope": scope})


def _high_low_outcomes(ctx: ReadContext, consumption: Decimal | None, config: Any) -> list[Outcome]:
    """BR-MET-020 high/low against the tenant's ratio thresholds.

    High needs BOTH conditions (OQ-002 closure): ratio above `high_pct` AND the
    delta above the absolute floor for the read's unit. Low is ratio-only, with
    usage > 0 (a zero read is the zero rule's, not low's)."""
    if consumption is None:
        return []
    if config is None:
        return [_no_config(RULE_HIGH), _no_config(RULE_LOW)]
    average = _trailing_average(ctx)
    if average is None or average == 0:
        return [
            Outcome(RULE_HIGH, NOT_EVALUATED, {"reason": REASON_NO_HISTORY}),
            Outcome(RULE_LOW, NOT_EVALUATED, {"reason": REASON_NO_HISTORY}),
        ]

    ratio_pct = (consumption / average) * Decimal(100)
    base = {
        "consumption": str(consumption),
        "unit": ctx.unit,
        "trailing_average": str(average),
        "trailing_reads": len(ctx.trailing_actuals),
        "ratio_pct": str(ratio_pct),
    }
    outcomes: list[Outcome] = []

    high_pct = _threshold(config, "high_pct")
    floor = _absolute_floor(ctx, config)
    if high_pct is None:
        outcomes.append(Outcome(RULE_HIGH, NOT_EVALUATED, {"reason": REASON_NO_CONFIG}))
    elif ratio_pct <= Decimal(high_pct):
        outcomes.append(Outcome(RULE_HIGH, OK, {**base, "threshold_pct": str(high_pct)}))
    elif floor is None:
        # Ratio breached but the AND-half cannot be evaluated: OQ-004 forbids a
        # silent conversion, so the rule reports rather than half-firing.
        outcomes.append(
            Outcome(
                RULE_HIGH,
                NOT_EVALUATED,
                {**base, "threshold_pct": str(high_pct), "reason": REASON_NO_FLOOR},
            )
        )
    else:
        floor_value, floor_unit = floor
        delta = consumption - average
        detail = {
            **base,
            "threshold_pct": str(high_pct),
            "absolute_floor": str(floor_value),
            "absolute_floor_unit": floor_unit,
            "delta_over_average": str(delta),
        }
        outcomes.append(Outcome(RULE_HIGH, WARNING if delta > floor_value else OK, detail))

    low_pct = _threshold(config, "low_pct")
    if low_pct is None:
        outcomes.append(Outcome(RULE_LOW, NOT_EVALUATED, {"reason": REASON_NO_CONFIG}))
    else:
        breached = consumption > 0 and ratio_pct < Decimal(low_pct)
        outcomes.append(
            Outcome(RULE_LOW, WARNING if breached else OK, {**base, "threshold_pct": str(low_pct)})
        )
    return outcomes


def _days_outcome(ctx: ReadContext, config: Any) -> Outcome:
    """BR-MET-020 read-interval bounds (seeded 25–35 flag / 20–45 hard).

    ⚖️ **THE IMPORT-TIME VERDICT IS WARNING AT MOST — BR-MET-121 (PO
    2026-08-26, CR-038), and since that ruling it is LAW, not merely this
    function's implementation.** BR-MET-121 verbatim: *"I will keep on
    colelcting reading and load it in application for given utility. when you
    run bill cycle you pull the reading and at that time we have to decide
    whether it is for 90 days or whrther it for 30 days or 15 days ; and if
    there is an issue with reading days we flag it ; reading is reading we
    store it as it comes"*. **(1)** An interval-days problem NEVER refuses a
    reading at import: both tiers below return WARNING (the 20–45 "hard" tier
    keeps its distinct `hard: True` detail so a screen can say "outside the
    hard bound", but it does not ERROR and it does not block commit —
    BR-MET-129 posts warned rows). **(2)** The AUTHORITATIVE days judgment
    happens when the BILL RUN pulls the readings (the W8 Days tab) — not here.
    The bounds stay tenant/service CONFIG for flagging (BR-MET-020,
    unchanged). Measured 2026-08-26 by the CR-038 W2 lane: this function has
    returned WARNING for both tiers since it was written (2026-08-11) — the
    ruling ratifies the behavior; the test that pins it now cites the law so
    drift to ERROR goes RED (`test_cr038_w2_mixed_cycle.py`).
    """
    if config is None:
        return _no_config(RULE_DAYS_THRESHOLD)
    if ctx.read_at is None or ctx.prior_read_at is None:
        return Outcome(RULE_DAYS_THRESHOLD, NOT_EVALUATED, {"reason": REASON_NO_PRIOR})
    days = (ctx.read_at.date() - ctx.prior_read_at.date()).days
    flag_min = _threshold(config, "days_flag_min")
    flag_max = _threshold(config, "days_flag_max")
    hard_min = _threshold(config, "days_hard_min")
    hard_max = _threshold(config, "days_hard_max")
    if None in (flag_min, flag_max, hard_min, hard_max):
        return Outcome(RULE_DAYS_THRESHOLD, NOT_EVALUATED, {"reason": REASON_NO_CONFIG})
    detail = {
        "days": days,
        "flag_bounds": [flag_min, flag_max],
        "hard_bounds": [hard_min, hard_max],
    }
    outside_hard = days < int(hard_min) or days > int(hard_max)  # type: ignore[arg-type]
    outside_flag = days < int(flag_min) or days > int(flag_max)  # type: ignore[arg-type]
    if outside_hard:
        return Outcome(RULE_DAYS_THRESHOLD, WARNING, {**detail, "hard": True})
    if outside_flag:
        return Outcome(RULE_DAYS_THRESHOLD, WARNING, {**detail, "hard": False})
    return Outcome(RULE_DAYS_THRESHOLD, OK, detail)


def _window_outcome(ctx: ReadContext) -> Outcome:
    """BR-MET-057: the cycle read-window is what a read is expected inside.
    No threshold involved — the window is the cycle's own configuration."""
    if ctx.read_at is None:
        return Outcome(RULE_OUT_OF_WINDOW, NOT_EVALUATED, {"reason": REASON_NO_PRIOR})
    if ctx.cycle_window_start is None or ctx.cycle_window_end is None:
        return Outcome(RULE_OUT_OF_WINDOW, NOT_EVALUATED, {"reason": REASON_NO_CYCLE_WINDOW})
    read_day = ctx.read_at.date()
    detail = {
        "read_date": read_day.isoformat(),
        "window_start": ctx.cycle_window_start.isoformat(),
        "window_end": ctx.cycle_window_end.isoformat(),
    }
    outside = read_day < ctx.cycle_window_start or read_day > ctx.cycle_window_end
    return Outcome(RULE_OUT_OF_WINDOW, WARNING if outside else OK, detail)


def _vacant_outcome(ctx: ReadContext) -> Outcome:
    """BR-MET-052: a read on a vacant unit is a WARNING (postable only via an
    explicit accept-with-reason, BR-MET-015). Occupancy is DERIVED from the
    active account (BR-MET-036) — when the customers seam cannot answer, this
    reports rather than declaring every unit vacant."""
    if ctx.unit_occupied is None:
        return Outcome(RULE_VACANT_UNIT, NOT_EVALUATED, {"reason": REASON_SEAM_UNWIRED})
    if ctx.unit_occupied:
        return Outcome(RULE_VACANT_UNIT, OK, {"occupied": True})
    return Outcome(
        RULE_VACANT_UNIT,
        WARNING,
        # ⚠ **THE RULE ID LEFT THIS STRING ON 2026-09-14 (`DEF-MET-5204`).**
        # It reached a clerk VERBATIM on 2 of 2 readings opened in a browser,
        # because the reading detail printed this bag as a `<dl>` with the raw
        # key as each label. B14 rule 31 names `BR-…` by family and says where
        # the provenance goes instead: *"it MOVES to the code comment beside
        # the string."* The rule is **BR-MET-036** — occupancy is DERIVED from
        # the active account. The screen states the fact from its own
        # catalogue now, in eleven languages, so every row ALREADY COMMITTED
        # reads correctly too — which a copy edit here could never have done.
        {"occupied": False, "basis": "no active account on the unit"},
    )


def _cycle_membership_outcome(ctx: ReadContext) -> Outcome:
    """BR-MET-122 (PO 2026-08-26, CR-038 · closes the Blueprint's Open 1),
    verbatim: *"**A METER IN THE FILE THAT IS NOT IN THE TAGGED CYCLE IS A
    WARNING A CLERK ACCEPTS WITH A REASON.** PO verbatim: 'Open 1 - (a) flag
    as warning, clerk accepts with a reason'. The cycle-membership rule (W2)
    imports the row, flags it by name ('M-4021 belongs to CY-002, file tagged
    CY-001'), and BR-MET-015's disposition discipline applies — accepted with
    a recorded reason or it does not post. Never a silent import (today's
    behavior), never a hard refusal."*

    Membership is the meter's `service_points.cycle_id` stamp (BR-MET-033 —
    the same cycle→routes→service-point chain `completeness._expected_meters`
    walks), resolved by the service layer onto the context; this rule is pure.

    * batch not tagged with a cycle → `not_evaluated` with the stated reason
      (no membership expectation exists to judge);
    * meter in the tagged cycle → `ok`, both cycles recorded;
    * meter in NO cycle → WARNING that says exactly that;
    * meter in a DIFFERENT cycle → WARNING, both cycles NAMED.

    ⚠ At the POST gate, BR-MET-129 (ruled the same day, later) means this
    warning — like every warning — no longer HOLDS the reading out: it posts
    carrying the flag, and the clerk's accept-with-reason stays the recorded
    disposition when one is given. The severity here is exactly what
    BR-MET-122 says: WARNING, never ERROR, never a silent pass.
    """
    if ctx.batch_cycle_id is None:
        return Outcome(RULE_CYCLE_MEMBERSHIP, NOT_EVALUATED, {"reason": REASON_NO_CYCLE_TAG})
    meter = ctx.meter_no or "meter"
    file_cycle = ctx.batch_cycle_code or str(ctx.batch_cycle_id)
    detail: dict[str, Any] = {
        "meter": ctx.meter_no,
        "file_cycle": file_cycle,
        "file_cycle_id": str(ctx.batch_cycle_id),
        # Rule 31 again. The ids are **BR-MET-122** (this warning) and
        # **BR-MET-033** (the cycle→routes→service-point chain it reads).
        "basis": "the meter's own cycle stamp",
    }
    if ctx.meter_cycle_id is not None and str(ctx.meter_cycle_id) == str(ctx.batch_cycle_id):
        return Outcome(
            RULE_CYCLE_MEMBERSHIP,
            OK,
            {**detail, "meter_cycle": ctx.meter_cycle_code or str(ctx.meter_cycle_id)},
        )
    if ctx.meter_cycle_id is None:
        return Outcome(
            RULE_CYCLE_MEMBERSHIP,
            WARNING,
            {
                **detail,
                "meter_cycle": None,
                "summary": f"{meter} belongs to no cycle, file tagged {file_cycle}",
                "resolutions": ["accept_with_flag", "fix_meter_id", "reject"],
            },
        )
    meter_cycle = ctx.meter_cycle_code or str(ctx.meter_cycle_id)
    return Outcome(
        RULE_CYCLE_MEMBERSHIP,
        WARNING,
        {
            **detail,
            "meter_cycle": meter_cycle,
            "meter_cycle_id": str(ctx.meter_cycle_id),
            "summary": f"{meter} belongs to {meter_cycle}, file tagged {file_cycle}",
            "resolutions": ["accept_with_flag", "fix_meter_id", "reject"],
        },
    )


def _row_key_outcome(ctx: ReadContext) -> Outcome | None:
    """**CR-054 W1 task 7 — is this row still about the meter it was written
    for?** Pure: this function judges and does nothing else.

    The shape is `_cycle_membership_outcome`'s above, deliberately and exactly:
    the SERVICE LAYER resolves the two facts onto the context (the key the file
    carried, the meter the row actually names) and the rule compares them. It
    reads no database, knows no cycle, and takes no threshold — BR-MET-020 has
    nothing to govern here, because the comparison is two strings.

    CR-054 task 7, verbatim: *"The row `key` column must survive the round trip
    so that a row whose meter no longer matches its key is caught. On upload
    that is a WARNING with both values named — 'row 412 was M-4021, now M-4099
    — was the meter replaced?' — never a silent import and never a hard
    refusal. A swapped meter is legitimate and common."*

    Four postures, each STATED rather than defaulted:

      * **no key** → `None`, and the caller appends nothing. A hand-built file,
        the blank published template and the manual grid carry no key; there is
        no expectation to judge, and emitting `not_evaluated` on every row of
        every hand-built file would be noise in the one report a clerk reads.
      * **a key this grammar cannot read** → `not_evaluated`, with the cell
        shown back verbatim. A failure to KNOW is not a finding.
      * **the key's meter is the row's meter** → `ok`, both values recorded.
      * **they differ** → WARNING, both NAMED, with BR-MET-015's disposition
        vocabulary — the same three resolutions BR-MET-122 offers, because it
        is the same kind of disagreement and the clerk is the one who can
        settle it.

    ⚠ **THE REGISTER HALF IS REPORTED AND NOT JUDGED, ON PURPOSE.** The key
    also carries the register the row was generated for, and a clerk can move a
    value onto the wrong register row as easily as onto the wrong meter. CR-054
    task 7 rules the METER case and says nothing about the register, so the
    channel is carried in the detail where a screen can show it and the
    severity is decided by the meter comparison alone. Inventing a second
    verdict here would be this engine ruling on a case nobody put to it — the
    posture `generation_channel`'s own note takes three rules above.
    """
    if ctx.row_key is None:
        return None
    parsed = read_import.parse_row_key(ctx.row_key)
    if parsed is None:
        return Outcome(
            RULE_ROW_KEY,
            NOT_EVALUATED,
            {"reason": REASON_ROW_KEY_UNREADABLE, "row_key": ctx.row_key},
        )
    keyed_cycle, keyed_channel, keyed_meter = parsed
    detail: dict[str, Any] = {
        "row_no": ctx.row_no,
        "row_key": ctx.row_key,
        "keyed_cycle": keyed_cycle,
        "keyed_meter": keyed_meter,
        # Reported, never judged — see the docstring.
        "keyed_channel": keyed_channel or None,
        "channel": ctx.channel,
        "meter": ctx.meter_no,
        # Rule 31. The id is **CR-054** task 7.
        "basis": "the generated reading sheet's row key",
    }
    if ctx.meter_no is not None and str(ctx.meter_no) == keyed_meter:
        return Outcome(RULE_ROW_KEY, OK, detail)
    row_label = f"row {ctx.row_no}" if ctx.row_no is not None else "this row"
    return Outcome(
        RULE_ROW_KEY,
        WARNING,
        {
            **detail,
            "summary": (
                f"{row_label} was {keyed_meter}, now {ctx.meter_no or 'blank'} "
                "— was the meter replaced?"
            ),
            "resolutions": ["accept_with_flag", "fix_meter_id", "reject"],
        },
    )


def resolve_stated_service(stated: str, enabled: Iterable[str]) -> tuple[str | None, list[str]]:
    """**BR-MET-137 — the utility's own shorthand for a service it SELLS.**

    PO 2026-08-26, asked with DEF-792's measured case in hand (a row's stated
    service is validated nowhere and every fixture in the corpus carries `"E"`):
    *"yes accept them"*.  `E` -> electric, `W` -> water, `G` -> gas, and the same
    first-letter shorthand for whatever else the tenant has enabled.

    Returns `(resolved_code, candidates)`:

    * `("electric", ["electric"])` — resolved, either because the row stated the
      FULL code or because one enabled service starts with that letter.
    * `(None, ["sewer", "solar"])` — **AMBIGUOUS, and deliberately unresolved.**
      Two enabled services share the letter, so the caller reports the ambiguity
      with both named.  Guessing here would price the wrong charge on somebody's
      bill, and the fix costs the file one character.
    * `(None, [])` — the token means nothing in this tenant's enabled set.

    ⚠ **RESOLVED AGAINST THE ENABLED SET, NEVER A HARDCODED TEN-ROW TABLE.**
    BR-MET-003's posture is that a tenant may only state a service it SELLS, so
    a letter is read against what this tenant sells and not against the
    platform's catalogue.  The consequence is deliberate and worth stating: `S`
    resolves cleanly to sewer for a tenant without solar, and is refused as
    ambiguous for the tenant next door who has both.  The same file is correct
    in one tenant and unanswerable in the other, because the vocabulary belongs
    to the tenant.

    ⚠ **IT ADDS A SHORTHAND; IT REPLACES NOTHING.**  A full service code is
    valid input everywhere it was before, which is why the exact match is tried
    first and a one-character SERVICE CODE (were one ever enabled) would win
    over the shorthand reading of the same letter.
    """
    token = str(stated or "").strip().lower()
    if not token:
        return None, []
    codes = [str(code).strip().lower() for code in (enabled or ()) if str(code).strip()]
    if token in codes:
        return token, [token]
    if len(token) != 1:
        return None, []
    candidates = sorted({code for code in codes if code.startswith(token)})
    if len(candidates) == 1:
        return candidates[0], candidates
    return None, candidates


def _service_coherence_outcome(ctx: ReadContext) -> Outcome | None:
    """CR-038 W2 aspect 4 (2026-08-26): *"a service-coherence rule (row's
    service vs the meter's real service)"* — a WARNING with BOTH values named
    when they disagree.

    The row's STATED service is its BR-MET-014 effective tag — BR-MET-014
    verbatim: *"Batch tags (month/cycle/route/service/source) inherit to every
    row unless a row-level column overrides; effective tags recorded on batch
    + rows"* — so a batch tag counts as a statement too. A row that states
    NOTHING (no row column, no batch tag) inherits the meter's own service at
    post and NEVER flags: this function returns None, the rule simply does not
    apply.

    A stated value that is not an enabled service code is a GAP, not a
    warning: nothing in the product has ever validated the row's service
    column (files in the wild carry "E"), `read_import` keeps values verbatim
    by law ("never snapped to a valid value"), and minting an alias table here
    would invent vocabulary nobody signed. The rule reports `not_evaluated`
    with the value named so the batch summary shows the gap honestly.
    """
    if ctx.stated_service is None or not str(ctx.stated_service).strip():
        return None  # nothing stated — inherits (BR-MET-014), never flags
    stated_raw = str(ctx.stated_service).strip()
    stated = stated_raw.lower()
    if ctx.service_code is None:
        return Outcome(
            RULE_SERVICE_COHERENCE,
            NOT_EVALUATED,
            {"reason": REASON_METER_SERVICE_UNRESOLVED, "stated_service": stated_raw},
        )
    real = str(ctx.service_code).strip().lower()
    detail: dict[str, Any] = {
        "stated_service": stated_raw,
        "meter_service": ctx.service_code,
        "meter": ctx.meter_no,
    }
    # BR-MET-137: resolve the STATEMENT before judging it, so `E` on a meter
    # that is electric is agreement rather than an unrecognised token. The full
    # code still wins — `resolve_stated_service` tries the exact match first.
    resolved, candidates = resolve_stated_service(stated, ctx.enabled_services or ())
    if resolved is None and len(candidates) > 1:
        # ⚠ AMBIGUOUS AND NOT GUESSED (BR-MET-137 clause 2). `S` where the
        # tenant sells both sewer and solar. Naming one would price the wrong
        # charge; naming both tells the operator the one character to add.
        return Outcome(
            RULE_SERVICE_COHERENCE,
            NOT_EVALUATED,
            {
                **detail,
                "reason": REASON_SERVICE_SHORTHAND_AMBIGUOUS,
                "candidates": candidates,
                "summary": (
                    f"{stated_raw!r} could mean "
                    + " or ".join(candidates)
                    + " — state the full code"
                ),
            },
        )
    if resolved is None:
        # Clause 3, the W2 posture unchanged: an unrecognised token reports the
        # gap with the value verbatim. It is NOT snapped to anything.
        return Outcome(
            RULE_SERVICE_COHERENCE,
            NOT_EVALUATED,
            {**detail, "reason": REASON_STATED_SERVICE_UNRECOGNIZED},
        )
    if resolved == real:
        # The resolved code, not the raw token, is what agrees with the meter —
        # which is the whole of BR-MET-137: `E` on an electric meter is now a
        # match instead of an unanswerable cell.
        return Outcome(RULE_SERVICE_COHERENCE, OK, {**detail, "resolved_service": resolved})
    meter = ctx.meter_no or "meter"
    return Outcome(
        RULE_SERVICE_COHERENCE,
        WARNING,
        {
            **detail,
            "resolved_service": resolved,
            "summary": f"row says {stated_raw}, meter {meter} is {ctx.service_code}",
            "resolutions": ["accept_with_flag", "fix_meter_id", "reject"],
        },
    )


def submeter_mismatch(
    *,
    master_consumption: Decimal | None,
    submeter_sum: Decimal | None,
    unit: str | None,
    tolerance_pct: Decimal | None = None,
    config: Any = None,
    service_code: str | None = None,
    expected_submeters: int | None = None,
    resolved_submeters: int | None = None,
    unresolved: list[dict[str, Any]] | None = None,
) -> Outcome:
    """**BR-MET-025 / BR-MET-125 — the master-vs-sub-meters gap, as a GROUP
    rule.** ALWAYS returns an outcome; it never returns None.

    Shaped exactly like `tou_sum_sanity` and `plan_register_completeness`: it is
    evaluated once per (master meter, read date, register) over facts the caller
    resolved, because the inputs live on OTHER assets' reads and a per-row
    context cannot see them. That is the whole of DEF-791 — see
    `_mismatch_outcome` below, which is now a thin adapter onto this body so the
    rule has ONE implementation and not two.

    **The worked figure, from the PO packet that signed BR-MET-125:** master
    12,400 kWh − Σ subs 11,940 = **460 kWh (3.71%)** against a **3%** tolerance
    → a WARNING, and 460 kWh unaccounted for.

    Four refusals, each of which would otherwise manufacture a number:

    * **No tolerance** → `not_evaluated` / `validation_config_missing`.
      BR-MET-020: the figure is the master's own `assets.loss_tolerance_pct`,
      else the (tenant, service) `mismatch_pct`, else the tenant-wide
      `mismatch_default_pct`. There is no 3% constant in this file.
    * **No master consumption**, or a zero one → `not_evaluated`. A percentage
      of zero is not a large gap, it is a division by zero.
    * **An INCOMPLETE Σ subs** → `not_evaluated` / `submeter_sum_incomplete`,
      with every unresolved sub-meter NAMED. This is the important one: a sub
      that was not read, or that reads in a different unit, would otherwise
      silently shrink the sum and invent an unaccounted gap out of a missing
      reading. `resolved_submeters < expected_submeters` is a skip, never a
      smaller Σ.
    * **No sub-meters at all** → `not_evaluated` / `asset_has_no_submeters`.
      The caller normally does not even ask, but a master that LOST its subs
      must not report a 100% gap.

    `unit` travels on every branch (CLAUDE.md hard rule 3): 460 means nothing
    without kWh, and the stored row and the report both read it from here.
    """
    detail: dict[str, Any] = {
        "unit": unit,
        "master_consumption": None if master_consumption is None else str(master_consumption),
        "submeter_sum": None if submeter_sum is None else str(submeter_sum),
        "expected_submeters": expected_submeters,
        "resolved_submeters": resolved_submeters,
        "unresolved_submeters": list(unresolved or []),
    }
    if service_code is not None:
        detail["service"] = service_code

    if expected_submeters == 0:
        return Outcome(RULE_MISMATCH, NOT_EVALUATED, {**detail, "reason": REASON_NO_SUBMETERS})
    if (
        expected_submeters is not None
        and resolved_submeters is not None
        and resolved_submeters < expected_submeters
    ):
        return Outcome(
            RULE_MISMATCH, NOT_EVALUATED, {**detail, "reason": REASON_SUBMETER_SET_INCOMPLETE}
        )
    if submeter_sum is None or master_consumption is None:
        return Outcome(
            RULE_MISMATCH, NOT_EVALUATED, {**detail, "reason": REASON_SUBMETER_SET_INCOMPLETE}
        )

    tolerance = tolerance_pct
    if tolerance is None:
        tolerance = _threshold(resolve_config(config, service_code), "mismatch_default_pct")
    if tolerance is None:
        return Outcome(RULE_MISMATCH, NOT_EVALUATED, {**detail, "reason": REASON_NO_CONFIG})
    if master_consumption == 0:
        return Outcome(RULE_MISMATCH, NOT_EVALUATED, {**detail, "reason": REASON_NO_HISTORY})

    gap = abs(master_consumption - submeter_sum)
    gap_pct = (gap / master_consumption) * Decimal(100)
    within = gap_pct <= Decimal(tolerance)
    return Outcome(
        RULE_MISMATCH,
        OK if within else WARNING,
        {
            **detail,
            "gap": str(gap),
            "gap_pct": str(gap_pct),
            "tolerance_pct": str(tolerance),
            "within_tolerance": within,
        },
    )


def _mismatch_outcome(ctx: ReadContext, consumption: Decimal | None, config: Any) -> Outcome | None:
    """BR-MET-025 on the PER-ROW path — a thin adapter onto `submeter_mismatch`.

    ⚠ **THIS RETURNS None ON EVERY PRODUCTION ROW, AND THAT IS NOW HONEST
    (DEF-791).** `ReadContext.submeter_consumption_sum` is never populated by
    `services._build_context`, because a row's context is assembled from ONE
    asset's world and Σ subs is a fact about OTHER assets' reads. Until
    2026-08-26 that hole was covered by a comment on the hardcoded `None`
    reading *"BR-MET-025 runs on the committed group, below"* — and there was
    no group loop below, or anywhere. The rule, its config column and its unit
    tests all existed and no live input ever reached it.

    The group loop now exists (`services.validate_read_batch` →
    `submeter_reconciliation.evaluate_batch`), so this adapter stays for the
    US-MET-011/TC-6 unit test, which drives the rule by handing it a context
    directly. It delegates rather than duplicating: a rule with two bodies is
    a rule that will disagree with itself.
    """
    if ctx.submeter_consumption_sum is None or consumption is None:
        return None
    return submeter_mismatch(
        master_consumption=consumption,
        submeter_sum=ctx.submeter_consumption_sum,
        unit=ctx.unit,
        tolerance_pct=ctx.loss_tolerance_pct,
        config=config,
        service_code=ctx.service_code,
    )


def _unratified_outcomes() -> list[Outcome]:
    """Rules named by BR-MET-021 whose threshold nobody has signed. They are
    reported EVERY time so their absence is visible in the batch summary rather
    than passing as a silent green."""
    return [
        Outcome(rule, NOT_EVALUATED, {"reason": REASON_NO_THRESHOLD, "rule_ref": "BR-MET-020"})
        for rule in UNRATIFIED_RULES
    ]


def evaluate_row(ctx: ReadContext, config: Any) -> tuple[Decimal | None, list[Outcome]]:
    """Run the per-row catalog. Returns `(consumption, outcomes)`.

    `consumption` is None whenever it cannot be computed honestly — a missing
    prior, or the negative-usage hard error that BR-MET-052 forbids fixing.

    CR-038 A1: when handed a `ConfigSet`, the row is judged by the config
    `resolve_config` picks for ITS service — per-service row first, the legacy
    tenant row for electric/water only, else the TC-9 skip-and-report. A bare
    tenant row (or None) behaves exactly as before.

    CR-038 BR-MET-136: every outcome leaves this function through
    `apply_rule_switches`, which replaces a JUDGMENT rule the tenant switched
    off with a `disabled` STATEMENT (never a removal) and can never touch an
    integrity rule. There is exactly one such call per return path, on purpose
    — see `switch_outcome`'s own docstring for why the rules still run.
    """
    config = resolve_config(config, ctx.service_code)
    switches = rule_switches(config)
    outcomes = _identity_outcomes(ctx)
    if any(o.rule == RULE_UNKNOWN_METER for o in outcomes):
        # Nothing downstream can be judged without a meter: prior value,
        # multiplier, digits and occupancy all hang off it.
        duplicate = _duplicate_outcome(ctx)
        if duplicate is not None:
            outcomes.append(duplicate)
        # CR-054 W1 task 7. A row whose meter cannot be resolved is the case
        # where the key matters MOST: `unknown_meter` says "M-4099 is not a
        # meter" and the key is the only thing that can add "…and this row was
        # written for M-4021". Without it a clerk is told what is wrong and
        # nothing about how to get back.
        row_key = _row_key_outcome(ctx)
        if row_key is not None:
            outcomes.append(row_key)
        return None, apply_rule_switches(outcomes, switches)

    # BR-MET-1160 (PO 2026-09-02) — beside hard rule 3's other half. It is
    # evaluated BEFORE the consumption rules, and above the device branch so it
    # runs on both kinds of asset, because it is a fact about the MEASUREMENT
    # rather than about the number: whether this quantity can be priced at all.
    unit_mismatch = _unit_mismatch_outcome(ctx)

    consumption, consumption_outcome = compute_consumption(ctx)

    # ── CR-038 W6 (BR-MET-124/135): THE DEVICE PATH ────────────────────────
    # A device's figure runs the SAME pipeline — identity, hard rule 3,
    # duplicates, cadence — and the six meter rules that cannot mean anything
    # on a generation quantity are SKIPPED AND REPORTED rather than faked
    # (`DEVICE_SKIPPED_RULES` carries the reason for each one).
    if ctx.is_device is True:
        outcomes.append(_generation_channel_outcome(ctx))  # type: ignore[arg-type]
        # BR-MET-1160 runs on a DEVICE too, and deliberately: it is not on
        # `DEVICE_SKIPPED_RULES` because it is not a threshold judgment about
        # consumption — it is hard rule 3 applied to the other factor, and a
        # generation figure in the wrong unit is priced by the same engine and
        # refused by the same gate. Where the device's service has no plan or
        # no schedule the rule simply reports, exactly as it does for a meter.
        if unit_mismatch is not None:
            outcomes.append(unit_mismatch)
        duplicate = _duplicate_outcome(ctx)
        if duplicate is not None:
            outcomes.append(duplicate)
        outcomes.append(_days_outcome(ctx, config))
        outcomes.append(_window_outcome(ctx))
        outcomes.append(_cycle_membership_outcome(ctx))
        coherence = _service_coherence_outcome(ctx)
        if coherence is not None:
            outcomes.append(coherence)
        # CR-054 W1 task 7 — a device's row is generated onto the same sheet
        # and typed over by the same clerk.
        row_key = _row_key_outcome(ctx)
        if row_key is not None:
            outcomes.append(row_key)
        outcomes.extend(_device_skips())
        outcomes.extend(_unratified_outcomes())
        return consumption, apply_rule_switches(outcomes, switches)

    # BR-MET-1160 on the meter path — see the device branch above for the pair.
    if unit_mismatch is not None:
        outcomes.append(unit_mismatch)

    if consumption_outcome is not None:
        outcomes.append(consumption_outcome)
    elif ctx.prior_value is None:
        # A first read has no delta. That is not a defect — it is the meter's
        # first cycle — but the rules that need a prior say so explicitly.
        outcomes.append(Outcome(RULE_NEGATIVE_USAGE, OK, {"reason": REASON_NO_PRIOR}))

    duplicate = _duplicate_outcome(ctx)
    if duplicate is not None:
        outcomes.append(duplicate)

    export = _export_outcome(ctx)
    if export is not None:
        outcomes.append(export)

    # BR-MET-135's other half: a `generation` row on a METER is refused. On a
    # meter this only ever fires for that pairing (the rule returns OK for
    # every ordinary register), so it is appended for its ERROR, not for noise.
    generation = _generation_channel_outcome(ctx)
    if generation is not None and generation.severity == ERROR:
        outcomes.append(generation)

    zero = _zero_outcome(ctx, consumption, config)
    if zero is not None:
        outcomes.append(zero)
    outcomes.extend(_high_low_outcomes(ctx, consumption, config))
    outcomes.append(_days_outcome(ctx, config))
    outcomes.append(_window_outcome(ctx))
    outcomes.append(_vacant_outcome(ctx))
    # CR-038 W2 (2026-08-26): the mixed-cycle pair. Membership always reports
    # (skip-with-reason on an untagged batch — BR-MET-122); coherence only
    # when a service was actually stated (BR-MET-014 inheritance never flags).
    outcomes.append(_cycle_membership_outcome(ctx))
    coherence = _service_coherence_outcome(ctx)
    if coherence is not None:
        outcomes.append(coherence)
    # CR-054 W1 task 7 — the row key, judged beside the two facts it is most
    # like: the file says one thing, the registry says another, and the clerk
    # is the one who can tell which is right.
    row_key_outcome = _row_key_outcome(ctx)
    if row_key_outcome is not None:
        outcomes.append(row_key_outcome)
    mismatch = _mismatch_outcome(ctx, consumption, config)
    if mismatch is not None:
        outcomes.append(mismatch)
    outcomes.extend(_unratified_outcomes())
    return consumption, apply_rule_switches(outcomes, switches)


# ── group rule: TOU sum-sanity (BR-MET-052 + BR-MET-061) ────────────────────


def tou_sum_sanity(
    window_consumptions: dict[str, Decimal],
    total_consumption: Decimal | None,
    config: Any,
    service_code: str | None = None,
) -> Outcome:
    """Σ(tou_on + tou_mid + tou_off) ≈ total within the tenant's tolerance.

    BR-MET-052 confirms ±1%; BR-MET-020's config-over-constant rule means the
    number is READ from config (`tou_sum_tolerance_pct`, seeded 1.0), never
    written here. Since CR-038 A1 that config resolves per (tenant, service) —
    `service_code` is the group's meter's service, and a `ConfigSet` resolves
    exactly as `evaluate_row` does. BR-MET-061 CONFIRMS the severity is
    WARNING — postable only via an explicit accept + reason, never a silent
    pass. Evaluated ONLY when the full window set AND the total are present
    (US-MET-017/TC-6: a partial entry cannot be checked, and inventing the
    missing window would be exactly the guess this whole lane forbids).
    """
    from apps.metering.models import TOU_WINDOW_CHANNELS

    config = resolve_config(config, service_code)
    if config is None:
        return _no_config(RULE_TOU_SUM_SANITY)
    missing = [c for c in TOU_WINDOW_CHANNELS if window_consumptions.get(c) is None]
    if missing or total_consumption is None:
        return Outcome(
            RULE_TOU_SUM_SANITY,
            NOT_EVALUATED,
            {
                "reason": REASON_INCOMPLETE_GROUP,
                "missing_channels": missing + ([] if total_consumption is not None else ["total"]),
            },
        )
    tolerance = _threshold(config, "tou_sum_tolerance_pct")
    if tolerance is None:
        return Outcome(RULE_TOU_SUM_SANITY, NOT_EVALUATED, {"reason": REASON_NO_CONFIG})
    window_sum = sum((window_consumptions[c] for c in TOU_WINDOW_CHANNELS), Decimal("0"))
    if total_consumption == 0:
        return Outcome(RULE_TOU_SUM_SANITY, NOT_EVALUATED, {"reason": REASON_INCOMPLETE_GROUP})
    deviation_pct = (abs(total_consumption - window_sum) / total_consumption) * Decimal(100)
    detail = {
        "window_sum": str(window_sum),
        "total": str(total_consumption),
        "deviation_pct": str(deviation_pct),
        "tolerance_pct": str(tolerance),
        "windows": {c: str(window_consumptions[c]) for c in TOU_WINDOW_CHANNELS},
    }
    breached = deviation_pct > Decimal(tolerance)
    return Outcome(RULE_TOU_SUM_SANITY, WARNING if breached else OK, detail)


# ── group rule: plan-driven register completeness (BR-MET-049) ──────────────


def plan_register_completeness(
    received_channels: "set[str] | frozenset[str] | tuple[str, ...]",
    expected_channels: tuple[str, ...] | None,
    *,
    absent_reason: str | None = None,
    plan_detail: dict[str, Any] | None = None,
) -> Outcome:
    """The registers a meter RECEIVED in the batch vs the set its plan EXPECTS.

    BR-MET-049, verbatim: *"**Plan-driven read-set completeness**: the unit's
    plan determines the required read set per meter (TOU → per-window records;
    demand → +demand record); completeness is tracked and enforced as a VEE
    validation before billing"* (CONFIRMED — PO RD-2, "track it and use it for
    validations").

    PURE, like every rule here: the EXPECTED set arrives resolved (the
    `apps.metering.completeness` resolver derives it from the unit's plan
    through the rating seam — this module never touches the ORM), and the
    RECEIVED set is what the batch actually staged for this meter+date.

    Three outcomes and nothing else:

      * expected set UNRESOLVABLE (`expected_channels is None`) →
        `not_evaluated` carrying the caller's SPECIFIC reason — a unit with no
        plan contributes no required set (US-MET-018 TC-5), rating being
        unwired is "cannot answer" and never "expects nothing" (the DEF-075
        posture), and a TOU window with no stated channel is BR-RAT-067's
        refusal, never a rank or a guess.
      * a SHORTFALL → **WARNING**, with the missing registers NAMED — the
        detail carries `expected`, `received`, `missing` and a human `summary`
        ("expects tou_on/tou_mid/tou_off/total, file has total only"), so
        S28/S29 render the explanation from storage (BR-MET-022/056). WARNING
        and not ERROR, deliberately: a person may accept with a reason
        (BR-MET-015), because the billing consequence of posting an incomplete
        meter is **Open 2 and unruled** — a hard error here would close that
        question at a call site, which the prime directive forbids.
      * complete → `ok`, with the compared sets still recorded.

    Channels the file sent that the plan does NOT name ride along as
    `unexpected` — informational only, never a severity: the unlawful cases
    have their own rules (an export row on a plain meter is RULE_EXPORT_NOT_NET,
    a hard error) and this rule judges only the SHORTFALL.
    """
    received = {str(channel) for channel in received_channels}
    if expected_channels is None:
        return Outcome(
            RULE_PLAN_REGISTERS,
            NOT_EVALUATED,
            {"reason": absent_reason or REASON_PLAN_SET_UNRESOLVED, **(plan_detail or {})},
        )
    expected = list(expected_channels)
    missing = [channel for channel in expected if channel not in received]
    received_ordered = sorted(received)
    detail: dict[str, Any] = {
        "expected": expected,
        "received": received_ordered,
        "missing": missing,
        "unexpected": sorted(received - set(expected)),
        # Rule 31. The id is **BR-MET-049**.
        "basis": "the unit's plan sets the required read set per meter",
        **(plan_detail or {}),
    }
    if not missing:
        return Outcome(RULE_PLAN_REGISTERS, OK, detail)
    has = "/".join(received_ordered) + (" only" if received_ordered else "")
    detail["summary"] = (
        f"expects {'/'.join(expected)}, file has {has if received_ordered else 'no rows'}"
    )
    detail["resolutions"] = ["accept_with_flag", "estimate", "field_visit", "reject"]
    return Outcome(RULE_PLAN_REGISTERS, WARNING, detail)


# ── summarising ─────────────────────────────────────────────────────────────


def worst_severity(outcomes: list[Outcome]) -> str:
    """The row's severity = the worst outcome present (BR-MET-015 drives what
    that permits: errors must be resolved, warnings need an explicit accept)."""
    worst = OK
    for outcome in outcomes:
        if _SEVERITY_RANK[outcome.severity] > _SEVERITY_RANK[worst]:
            worst = outcome.severity
    return worst


def primary_status(outcomes: list[Outcome]) -> str:
    """BR-MET-021: a read carries EXACTLY ONE primary status plus the full
    outcome detail. The first error wins, else the first warning, else `ok` —
    `not_evaluated` is never a status, only a reported gap."""
    for severity in (ERROR, WARNING):
        for outcome in outcomes:
            if outcome.severity == severity:
                return outcome.rule
    return OK


def unevaluated(outcomes: list[Outcome]) -> list[dict[str, Any]]:
    """Every rule that did NOT run, with its reason — the honest half of a
    "0 errors" summary (CLAUDE.md law 1)."""
    return [
        {"rule": o.rule, "reason": o.detail.get("reason")}
        for o in outcomes
        if o.severity == NOT_EVALUATED
    ]


def as_json(outcomes: list[Outcome]) -> list[dict[str, Any]]:
    return [o.as_dict() for o in outcomes]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-011@64b3d87 (story+rules snapshot — EP-MET-04 lead story; staged-row half co-packet EP-MET-03@a4d93b5)
# generated: 2026-08-10 by the W2 reads lane · AMENDED 2026-08-26 by the CR-038 A1 S64 lane (per-(tenant, service) threshold resolution: ConfigSet + resolve_config — per-service row first, legacy tenant row for electric/water only, TC-9 skip-and-report otherwise; unit-aware floor shape high_abs_value/high_abs_unit; INTEGRITY_RULES published for S64's locked list; ReadContext.service_code)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — engine module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(N/A — not a 🔒 path: every threshold is READ from tenant config; no key, rounding rule or money figure is authored here)
# gates: see the lane report (ruff/black/pytest/run_gates/golden run over the whole slice) · AMENDED 2026-08-11 by the metering quantity-seam lane: ruff✔ black✔ · pytest tests -m golden → 9 passed / 2 xfailed✔ · pytest tests -m "not golden and not isolation" → 1096 passed / 10 skipped✔ · 10-scripts/03-golden-verify.py 33 PASS + GT-1..16 12 PASS✔ · run_gates 14 PASS / 0 FAIL / 1 SKIP✔
# exceptions: factor_flag NOT evaluated — no ratified threshold exists (BR-MET-020 forbids inventing one and no OQ id covers it); REPORTED to the PO · `unit_missing` is an Eng addition to the catalog enforcing CLAUDE.md rule 3, not a new threshold · rollover applies the multiplier to the wrapped delta per BR-MET-019's general form (GT-14's ×1 fixture does not discriminate) — REPORTED · [2026-08-11 quantity-seam lane] the wrap arithmetic was EXTRACTED verbatim into `classify_register_delta` so the published GT-4 seam and the flag engine share ONE implementation; `compute_consumption` now dresses that result and computes nothing itself. No threshold, figure or verdict moved — `span / 2` is now written `span * ROLLOVER_SPAN_FRACTION` (0.5), the same comparison in the ruling's own words, and the existing rule-by-rule tests pass unchanged.
# exceptions: [2026-08-26 CR-038 W2 lane] BR-MET-121/122 + the mixed-cycle pair —
#   `_days_outcome` docstring now carries BR-MET-121 verbatim (WARNING at most is
#   LAW; the function had returned WARNING for both tiers since 2026-08-11, so the
#   ruling ratifies rather than changes the verdict); RULE_CYCLE_MEMBERSHIP added
#   (BR-MET-122 — pure; membership facts resolved by services onto ReadContext);
#   RULE_SERVICE_COHERENCE added (row's BR-MET-014 effective service vs the
#   meter's real one; nothing-stated inherits and never flags; an unrecognized
#   stated value reports `not_evaluated` with the value named because the row's
#   service column is validated NOWHERE — an alias table would invent vocabulary).
#   Guards proved RED first — tests/test_cr038_w2_mixed_cycle.py quotes the runs.
# exceptions: [2026-08-26 CR-038 W1 lane] RULE_PLAN_REGISTERS added — BR-MET-049's import-time half (US-MET-018), a GROUP rule beside tou_sum_sanity, pure like everything here (the expected set arrives resolved from apps/metering/completeness through the rating seam; no ORM). Severity on a shortfall is WARNING, deliberately: the billing consequence of an incomplete meter is Open 2 and UNRULED, so a hard error would close an open question at a call site. Guard proved RED first — tests/test_us_met_018_plan_registers.py quotes the pre-change failure verbatim.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
