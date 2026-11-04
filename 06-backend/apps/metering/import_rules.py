# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (CR-023 P4 stage 3 — the recorded import supersedes the
#           stateless preview of US-MET-004 §5; design B15 §7A)
#           Screens: WFL-01.premises.3 (Validate), PRM-04
# Rules:    BR-MET-1030 (CR-058 W3 — the owner's identity columns; the three
#           new premises rules below flag a row that earns no owner account,
#           and all three are WARNING + FLAG_ONLY because CR-055's ruling
#           that no premises row is rejected on owner grounds stands) ·
#           BR-MET-090 (a rule is a DECLARED ROW, three tiers, severity and
#           action as TWO columns, and a run stores the rules AS THEY WERE) ·
#           BR-MET-091 (a rule the product cannot evaluate is DECLARED and
#           marked unavailable, never omitted) · BR-MET-003 (services ⊆ the
#           tenant's enabled services) · BR-MET-034 (premises types are a
#           Reference-data lookup) · BR-MET-071 (premises tag to an area) ·
#           BR-MET-085 (a premises import loads premises and nothing else)
#           BR-CUS-017 (one live account per unit, ever — asked here BEFORE the
#           write instead of only underneath it) · BR-CUS-022 (an account being
#           activated states the date its service started) · BR-CUS-018 (a new
#           account starts as a DRAFT, which is why neither of those two rules
#           fires on a row that is not going live)
#           BR-AST-047 (a sub-meter's allocation share) · BR-AST-007/027 (a
#           device's test interval is a number of MONTHS) — the two assets
#           ranges `assets.services._validate_asset` refuses under the write
# Change:   CR-047 — `ACC.UNIT_NOT_OCCUPIED` + `ACC.START_DATE_REQUIRED`, the two
#           refusals that used to escape stage 4's row loop (DEF-2519, critical)
#           · and the ASSETS half: `AST.ALLOC_SHARE_IN_RANGE` +
#           `AST.TEST_INTERVAL_POSITIVE`. ⚠ **THE CR PROPOSED FOUR OTHER ASSETS
#           RULES AND NONE OF THE FOUR WAS WRITTEN** — the number already on
#           file, the legacy reference already used, the missing install date on
#           an assigned row, and the unresolved lookup are each already carried
#           by a rule this catalogue has, or made unreachable by the loader
#           itself, and each redundancy is PINNED by a case in
#           `tests/test_cr047_assets_rules.py` so the next lane reading the CR
#           does not rebuild them.
# Tests:    06-backend/tests/test_cr023_import_stages.py ·
#           06-backend/tests/test_cr047_per_record_load.py (CR-047 accounts) ·
#           06-backend/tests/test_cr047_assets_rules.py (CR-047 assets)
# Impacts:  apps/metering/import_runs.py (stage 3 calls this) · PRM-04's
#           RULES THAT RAN table · endpoint 12/13 (GET/PATCH /import-rules),
#           which are NOT built here
# ───────────────────────────────────────────────────────
"""The import validation rule set — declared rows, three tiers, one evaluator
each.

**A RULE IS A DECLARED ROW, NOT AN `if` STATEMENT** (BR-MET-090). That is the
whole design brief and it is what makes the set changeable without breaking
anything already loaded: a run reads the rules AS THEY ARE, copies them onto
`import_rule_results`, and from then on OWNS its own copy. A month later the
utility can raise *premise type* from warning to error and July's receipt still
says what actually happened in July.

WHY THIS IS NOT `ReadValidationSettings`
----------------------------------------
Meter reads answer the same question — *how does this utility want its inbound
data checked* — as a WIDE ROW OF NAMED COLUMNS (`high_pct 200`, `low_pct 25`,
`days_flag_min 25`, `tou_sum_tolerance_pct 1`). That is correct for reads and
cannot work here. Reads have a **fixed, finance-signed** rule set, so adding a
rule is a deliberate act with a migration behind it. Imports have an **open**
one: tier 3 is a utility writing a rule we never shipped — *"No premise outside
our three ZIP codes"* — and a column set cannot express a rule nobody has
thought of yet. Both shapes should exist and the difference is written down
here rather than discovered (B15 §4.3A).

THE THREE TIERS, AND WHY THE TOP ONE CANNOT BE CONFIGURED
---------------------------------------------------------
**TIER 1 · STRUCTURAL.** The database or a hard rule refuses the row. Severity
is FIXED at `error` and the action at `reject_row`; there is no off switch and
none is offered, because switching one off would write a row Postgres or
CLAUDE.md rule 1 refuses anyway — the operator would be told the load succeeded
and it would not have. These rules are declared HERE, in code, and never appear
in `import_rules`: a table row a tenant can edit is by construction not
structural.

**TIER 2 · PLATFORM.** Shipped for every tenant with a default severity and a
default action, both re-configurable (BR-MET-090). An `ImportRule` row carrying
the same `code` is the tenant's override.

**TIER 3 · TENANT.** The utility's own rules, rows in `import_rules` with a
`rule_kind` this module has an evaluator for.

⚠ **TIER 1 IS EVALUATED FIRST AND STOPS THE ROW.** B15 §4.3A: *"Tier 1 failures
stop before tier 2 is asked."* A row rejected structurally is not then measured
against the platform rules, so a premises with no address does not also appear
in the *"already on file at this address"* count — it has no address to compare.

WHAT THIS MODULE DOES NOT DO
----------------------------
It does not WRITE. Stage 3 evaluates and records.

⚠ **AND NOTHING ELSE PERFORMS THE `default_to` / `skip_on_load` ACTIONS EITHER
— MEASURED 2026-08-26, CR-036 (g).** This paragraph said those actions "are
performed at stage 4, which is P5 and unbuilt", and it has outlived its truth
in one half and never been true in the other. **Stage 4 IS built and DOES
commit** (`import_runs.load`, mounted, CR-023/CR-026) — so the first half is
stale. But `SKIP_ON_LOAD` is *assigned* here at `PRM.ADDRESS_ON_FILE` and is
**read nowhere in this repo**: `grep -rn SKIP_ON_LOAD --include=*.py` returns
this module's definition and that one use, and nothing in `import_runs.py`.
A hit row is written `outcome="flagged"`, `_loadable_rows` forwards it, and the
write mode decides its fate exactly as if the rule carried `flag_only`.

**Measured, on the PO's own shape** (three premises re-run in `upsert`, second
file carrying `water` alone): `PRM.ADDRESS_ON_FILE` hits 3/3 with
`action="skip_on_load"`; every row outcome is `flagged`, not `skipped`; the dry
run says `will_create 0 · will_update 3`; the receipt says `created 0 ·
updated 3 · skipped 0`; and the row goes from `['water','sewer','trash']` to
`['water']`. Pinned by `tests/test_cr036_import_services.py`.

**The consequence, both ways round.** The good half: CR-036 (iii)'s advice —
*re-run the same file in `Insert & update`* — IS reachable for all 9,881 rows,
because the skip that would have defeated it does not fire. The bad half was a
defect: **the stage-3 table printed "Skip on load"** (`en.json`
`workflow.rules.action.skip_on_load`, `ImportWorkflowPage.tsx`) **on 9,881 rows
for an action no code performs**, so an operator planned a migration around a
promise the loader ignores.

✅ **CLOSED 2026-08-26 (DEF-750), and closed on the SCREEN'S side.**
`PRM.ADDRESS_ON_FILE` now declares `FLAG_ONLY` — the action the loader actually
performs — and its per-row hint no longer says the row *"will be skipped"*.
**Not one row behaves differently**; what changed is that the product stopped
claiming something about them. The reasoning is on the rule itself: under
`upsert` a skip would defeat the mode the operator was told to use, and under
`insert` whether to skip is a PRODUCT ruling nobody has made. Rebuilding the
action later is a two-line change here plus the loader branch — and it must be
mode-aware (CR-036 (g)).

⚠ **`DEFAULT_TO` IS STILL DECLARED BY TWO ASSETS RULES AND IS STILL PERFORMED
BY NOTHING IN THE LOADER** (`AST.MULTIPLIER_POSITIVE_INT`,
`AST.NEXT_TEST_DERIVABLE`). Their stated effects LOOK delivered by other means —
`Asset.multiplier` defaults to 1 in the model, and `next_test` is derived at
read time by `assets.selectors.next_test_date` — but **that was not measured**,
and a comment claiming a guarantee is not the guarantee (hard-won law 1). It is
reported rather than asserted: `test_def750__no_rule_declares_an_action_THE_
LOADER_DOES_NOT_PERFORM` names only what has been measured.

That severity/action separation is the reason BR-MET-090 insists severity and
action are two columns: r10's *"Premise type exists in the lookup table ·
**Warning** · 2 · **Default to Residential**"* is a warning that PERFORMS A WRITE the operator
never asked for, and a rule set that cannot say *"warn me but change nothing"*
cannot express the safe option at all.

⚠ **RULE SENTENCES ARE PROSE, NOT `message_key`s, AND THAT IS A DELIBERATE
EXCEPTION.** Tier-3 sentences are authored by the tenant and have no key and
never can — the ratified `custom_field.label` posture (B2 r17.5 #1, PO
2026-08-10). Platform sentences are held here in English beside them so one
screen renders one kind of thing. **The honest consequence, stated rather than
implied (hard-won law 1): the RULES THAT RAN table does not localise today.**
It is not a defect in this lane's sense — no key was dropped — but a lane
building a non-English deployment will find it, and it should find it written
down.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.metering import models, seams

# ── the vocabulary (mirrors models.IMPORT_RULE_* so a caller needs one import) ─
ERROR = "error"
WARNING = "warning"
PASS = "pass"
OFF = "off"

REJECT_ROW = "reject_row"
SKIP_ON_LOAD = "skip_on_load"
DEFAULT_TO = "default_to"
FLAG_ONLY = "flag_only"

TIER_STRUCTURAL = 1
TIER_PLATFORM = 2
TIER_TENANT = 3


@dataclass(frozen=True)
class RuleHit:
    """One row this rule fired on, with the sentence the operator reads.

    `problem` and `fix_hint` are r10's own two columns on the reject list —
    row `88`, key `P-11902`, *"Address falls outside the territory boundary"*
    → *"Confirm and load anyway"*. A hit with no sentence is a number with no
    explanation, which is the shape DEF-322 ruled against.
    """

    row_no: int
    problem: str
    fix_hint: str | None = None


@dataclass
class DeclaredRule:
    """A rule as it will be COPIED onto the run (BR-MET-090).

    Every field here is written to `import_rule_results`, because the run's
    receipt must go on saying what it said even after the configuration moves
    underneath it.
    """

    code: str
    target: str
    tier: int
    sentence: str
    severity: str
    action: str
    action_value: str | None = None
    rule_kind: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    available: bool = True
    unavailable_reason: str | None = None

    @property
    def blocks(self) -> bool:
        """Does a hit on this rule STOP the load? *"Errors block the load.
        Warnings don't — but you should look at them."*"""
        return self.available and self.severity == ERROR


# ═══════════════════════════════════════════════════════════════════════════
# THE PLATFORM CATALOG — premises
# ═══════════════════════════════════════════════════════════════════════════
#
# r10's stage 3 draws FOUR rules. All four are here, in its own order, plus the
# structural ones its screen never had to name because a prototype has no
# database to refuse anything.

PREMISES_RULES: tuple[DeclaredRule, ...] = (
    # ── TIER 1 · STRUCTURAL ────────────────────────────────────────────────
    DeclaredRule(
        code="PRM.ADDRESS_REQUIRED",
        target="premises",
        tier=TIER_STRUCTURAL,
        # B15 §4.2A #3: address_line is the ONLY non-null business column on
        # `premises`. A row without one cannot be created at all.
        sentence="Every premises needs a street address.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="address_required",
    ),
    DeclaredRule(
        code="PRM.PREMISE_NO_UNIQUE",
        target="premises",
        tier=TIER_STRUCTURAL,
        # `uq_premises_tenant_premise_no`. The database refuses the second one,
        # and a repeat INSIDE one file is the same collision arriving early —
        # unless stage 2's "keep the latest row when a key appears twice" has
        # already dropped the earlier one, in which case there is nothing here
        # to find (B15 §4.2A #1).
        sentence="A premise ID can only be used once.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="premise_no_unique",
    ),
    DeclaredRule(
        code="PRM.PREMISE_NO_ON_FILE",
        target="premises",
        tier=TIER_PLATFORM,
        # ⚠ Split OUT of PREMISE_NO_UNIQUE (`DEF-543`): stage 3 cannot know the
        # write mode, so an on-file match is not an error — it is the exact row
        # `Insert & update` exists for. The in-file duplicate stays the ERROR.
        # ⛔ **AMENDED 2026-08-27 — CR-046 C2, THE MEANING CHANGED WITH THE
        # COLUMN.** It read *"This premise ID is already on file — the write
        # mode decides what happens to it"*, which was true while a file could
        # bring its own premise number. Under the ruling it cannot: a value
        # here is only ever a QUOTE of a number WE issued, so a match is the
        # EXPECTED case rather than a coincidence.
        #
        # ⚠ **AND THE MODE IS NOW KNOWN (`CR-042` moved the choice to step 1,
        # wave B carried it into `World`), so the sentence no longer declines
        # to say which outcome applies** — `_for_write_mode` appends the tail
        # for the run's own mode and `insert` makes this an ERROR that rejects.
        # `DEF-543`'s obstacle was real and has been removed by a different
        # change; the two were simply never read together.
        sentence="This row names a premises already on file.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="premise_no_on_file",
    ),
    DeclaredRule(
        code="PRM.PREMISE_NO_NOT_ON_FILE",
        target="premises",
        tier=TIER_PLATFORM,
        # ⛔ **NEW 2026-08-27 — CR-046 C2, `AST.NUMBER_NOT_ON_FILE`'s twin, and
        # it is the OPPOSITE PREDICATE to the rule above rather than a variant
        # of it.** A premise ID that is NOT on file is one the operator
        # INVENTED, which is exactly what the ruling forbids — and it is wrong
        # in BOTH write modes (in Insert there is nothing to name; in Insert &
        # update it names nothing), so unlike the rule above it needs no
        # knowledge of the mode and can block at stage 3, where the operator can
        # still fix the file by clearing a cell.
        #
        # ⚠ **THE FIX HINT NAMES THE OTHER COLUMN, AND THAT IS NOT PADDING.**
        # An operator whose file has a `PREMISE_ID` column of their old
        # system's ids has somewhere for it to go (`external_ref`, BR-MET-403);
        # told only *"leave it blank"* they would delete data with no other
        # home — the very loss `external_ref` exists to prevent.
        sentence=(
            "A premise ID is issued by your numbering settings — leave this "
            "column blank for a new one."
        ),
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="premise_no_not_on_file",
    ),
    DeclaredRule(
        code="PRM.EXTERNAL_REF_UNIQUE",
        target="premises",
        tier=TIER_STRUCTURAL,
        # CR-046 C5 / BR-MET-403 — `uq_premises_tenant_external_ref_ci`
        # arriving early. ⚠ **IN-FILE ONLY**, the mirror of
        # `PRM.PREMISE_NO_UNIQUE`'s reason: a reference matching one ON FILE is
        # the MATCH KEY doing its job (`_key_of`), not a collision. Two rows of
        # the SAME file claiming one reference IS a collision, and catching it
        # here keeps the database's refusal from aborting a 428-row commit over
        # one duplicated cell.
        sentence="A row's external reference can only be used once in a file.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="external_ref_unique",
    ),
    DeclaredRule(
        code="PRM.SERVICES_ENABLED",
        target="premises",
        tier=TIER_STRUCTURAL,
        # BR-MET-003. B15 §4.2A #9 is explicit that r10's "Split on comma" is
        # NOT enough: a utility that does not sell sewer must have `S` refused,
        # not stored, because a premises listing a service the utility cannot
        # bill is a premises that can never bill correctly.
        sentence="A premises can only offer services this utility sells.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="services_enabled",
    ),
    DeclaredRule(
        code="PRM.REFERENCES_ON_FILE",
        target="premises",
        tier=TIER_STRUCTURAL,
        # B15 §4.3A tier 1: *"Every FK resolves — premises_type, area. A
        # dangling id is a row that reads as broken on every screen."* Only
        # `area` can dangle here: the premises-type path never writes an id it
        # did not look up (see PRM.TYPE_IN_LOOKUP below), so it lands NULL and
        # flags instead.
        # ⛔ OQ-328 — whether an unknown area should instead be CREATED or
        # LEFT NULL is unruled. Rejecting is the boundary, not a chosen answer:
        # it is the only option that neither authors reference data from a
        # spreadsheet nor discards a value the operator supplied.
        sentence="Every area a row names has to be on file already.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="references_on_file",
    ),
    DeclaredRule(
        code="PRM.VALUES_PARSE",
        target="premises",
        tier=TIER_STRUCTURAL,
        # The column's own type refuses it — a status outside the four the
        # column holds, a jurisdiction cell reading "maybe". ⚠ THE ONE THAT
        # MATTERS MOST IS `inside_city_limits`: a BLANK cell is NULL and never
        # an error, because NULL is a real third state (BR-RAT-101); a cell
        # with words in it nobody can read IS an error, because guessing which
        # way it meant is a silent pricing decision.
        sentence="Every value has to be the kind of value its column holds.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="values_parse",
    ),
    # ── TIER 2 · PLATFORM ──────────────────────────────────────────────────
    #
    # ⚠ **`PRM.ADDRESS_IN_TERRITORY` STOOD HERE AND IS GONE BY RULING, NOT BY
    # OMISSION (`BR-MET-097`, PO 2026-08-21).** It was r10's only
    # error-severity platform rule — *"Address must be inside the service
    # territory"* — declared here `available=False` with its reason, which is
    # the shape BR-MET-091 exists for. The PO ruled away the RULE, not the
    # implementation: *"We dont have to check; accept what utility user give
    # right now; theya re giving it from their GIS system hence it is assumed
    # it is correct; any upgrade we can think later"*.
    #
    # **`available=False` and ABSENT say different things to an operator.** The
    # first reads *"we would check this and cannot"* and invites a utility to
    # ask when it will be switched on. The ruling is that we do not check an
    # address at all, because the customer's GIS is the system of record for
    # their own addresses and re-deciding them here means arguing with it. So
    # the row is removed and this comment is the record — NOT a `severity=OFF`
    # entry, which would still be offering it.
    #
    # **The consequence is ruled rather than discovered: a premises import has
    # NO error-severity PLATFORM rule.** Only the five STRUCTURAL rules above
    # can reject a premises row. `blocking_rules` reports `platform: 0` BY
    # DESIGN — BR-MET-091 serves that number so no screen recomputes it — and
    # stage 3's *"Errors block the load"* stays true, because a structural
    # error is a real error. What it stops implying is that we checked the
    # address.
    #
    # **The upgrade stays cheap precisely because nothing was rejected on this
    # basis:** a territory list or a paid geocoder can be added later without
    # revisiting one row that is already loaded.
    DeclaredRule(
        code="PRM.ADDRESS_ON_FILE",
        target="premises",
        tier=TIER_PLATFORM,
        sentence="No premises is already on file at this address.",
        severity=WARNING,
        # ⛔ **WAS `SKIP_ON_LOAD`, AND THAT WAS `DEF-750` (high).** The screen
        # printed **"Skip on load"** in the ACTION column on 9,881 rows for an
        # action **no code performs** — measured, not inferred: `SKIP_ON_LOAD`
        # was assigned exactly here and read NOWHERE, and the loader never
        # branches on a rule's action at all. An operator planned a migration
        # around a promise the product does not keep.
        #
        # **It is DECLARED as what happens, rather than BUILT, and the reasoning
        # is the mode.** Under `upsert` — the mode CR-036 (iii) tells this very
        # operator to re-run in — *"already on file"* is the EXPECTED state of
        # every row, so a skip would defeat the mode entirely and strand all
        # 9,881 premises a second time. Under `insert` a skip is arguable and it
        # is a PRODUCT decision, not an engineering one: it silently does not
        # load rows the operator handed us, which is the mirror image of the
        # write nobody asked for that `PRM.TYPE_IN_LOOKUP` refuses two entries
        # below. Nobody has ruled it. **So the false half is removed today and
        # the question goes to the PO** — should a second premises at an address
        # already on file be skipped under `insert`? — rather than being
        # answered by whichever lane happened to be holding the file.
        #
        # ⚠ **AND IF IT IS EVER BUILT, IT MUST BE BUILT AS MODE-DEPENDENT**
        # (CR-036 amendment 2 (g)). The mode is chosen at stage 1 now, but the
        # run does not carry it until the load, so stage 3 cannot yet judge
        # against it — that is (g)'s remaining work, not this rule's.
        action=FLAG_ONLY,
        rule_kind="address_on_file",
    ),
    DeclaredRule(
        code="PRM.TYPE_IN_LOOKUP",
        target="premises",
        tier=TIER_PLATFORM,
        sentence="The premise type is one of the types on file.",
        severity=WARNING,
        # ⚠ r10's action here is `Default to Residential` and it is NOT
        # shipped, for two separate reasons and either would be enough.
        # (1) BR-MET-090: it is a WARNING THAT PERFORMS A WRITE nobody asked
        #     for — two premises silently become Residential and PRICE as
        #     Residential. Defensible as a policy, indefensible as a default.
        # (2) There is no such type. BR-MET-034 seeds five and not one is
        #     called Residential: Apartment complex · Commercial building ·
        #     Single-family · Mixed-use · Mobile-home park. Shipping r10's
        #     value verbatim would set a foreign key to a code no tenant has —
        #     accepted on screen, resolving to nothing, DEF-388's shape.
        # ⛔ OQ-329 holds the question. A utility may configure `default_to`
        # with one of ITS OWN codes the moment the rule-config endpoint lands.
        action=FLAG_ONLY,
        rule_kind="type_in_lookup",
    ),
    DeclaredRule(
        code="PRM.EXPECTED_UNITS_INTEGER",
        target="premises",
        tier=TIER_PLATFORM,
        sentence="The expected unit count is a whole number above zero.",
        severity=PASS,
        action=FLAG_ONLY,
        rule_kind="expected_units_integer",
        # ⚠ BR-MET-091 again, from the other direction: the rule is fine and
        # there is nothing to run it ON. `premises` has no expected-units
        # column, so BR-MET-088 forbids offering `UNIT_CNT` as a mapping
        # target, so no run can carry the value this rule would check.
        # ⛔ OQ-330 — transient check or stored expectation.
        available=False,
        unavailable_reason=(
            "A premises does not record how many units to expect, so the unit "
            "count in the file is not read and nothing was checked against it."
        ),
    ),
)

#: ── THE UNITS CATALOG (`BR-MET-096`) ──────────────────────────────────────
#: ⚠ **THIS SET WAS BLOCKED AND IS NOT ANY MORE.** The note that stood here
#: said units waited on *"a units row whose premise exists but whose plan does
#: not"* being unruled. `BR-MET-100` (PO 2026-08-21) ruled it: the row LOADS,
#: without a plan, FLAGGED — the PO overruled the recommendation to reject it.
#: So the plan rule below is a **WARNING**, and the premise rule is the ERROR.
#:
#: Four of r10's own units rules, and the one it draws that we do not run:
#:   * *Parent premise must already exist* — **Error · reject row.** r10's own
#:     stage 3 shows it hitting once, on row 119, `U-11902-B`.
#:   * *Unit label unique within its premise* — **Warning · flag.** ⚠ r10 says
#:     *"suffix and continue"*; we FLAG instead, because silently renaming a
#:     customer's unit `12` to `12-2` invents an identifier the utility never
#:     chose and will never find again. `BR-MET-089`'s posture — carry the
#:     problem, do not coerce the value — applies to labels as much as to cells.
#:   * *Plan must be on file* — **Warning · flag** (`BR-MET-100`).
#:   * *Unit type exists in the lookup table* — Warning, and r10 shows 0 hits.
#:   * *Meter ID not already linked to another unit* — **NOT DECLARED AT ALL.**
#:     A units import creates no meter (PO 2026-08-21: *"we will not add meter
#:     or asset here when we are uploading units"*), so no METER_E/METER_W
#:     column is offered and there is nothing for the rule to read. Declaring it
#:     `available=False` would imply a check we intend to run one day on a
#:     column that will never be part of this import.
# ── DEF-1088 · BR-MET-402 — the OWNER column resolves to a PARTY ───────────
#
# ⛔⛔ **CR-055 (2026-08-31) — THE NEAR RULE NO LONGER REJECTS. ALL THREE OWNER
# RULES ARE `WARNING` + `FLAG_ONLY` NOW, AND THE PREMISES UPLOAD THEREFORE
# CANNOT REJECT A ROW ON OWNER GROUNDS AT ALL.**
#
# PO ruling 2026-08-31, recorded in `12-governance/02-decision-log.md`: *"an
# uploaded owner name that matches no owner exactly but resembles two or more
# existing owners now LOADS THE PREMISES WITH NO OWNER, flagged to fill in
# later, exactly as a blank owner column already does. The row is not
# rejected."* Two options were declined in the same sentence: keep rejecting
# (*"a big migration can stall on spelling"*) and pick the closest match
# automatically (*"the owner carries the master account, so a wrong pick
# eventually sends somebody else's bill to the wrong party"*).
#
# ⚠ **DECISION 3 IS NOT REVERSED, AND READING IT THAT WAY IS THE ONE MISTAKE
# THIS BLOCK EXISTS TO STOP.** *"Offer the match, clerk decides"* says the
# import may not PICK — and it still does not pick: `_resolve_owner_ref`
# resolves an EXACT name only, so a near name writes NO `owner_id`, ever. What
# CR-055 changed is the CONSEQUENCE of refusing to pick. The row used to be
# thrown away; now it lands ownerless on the same worklist a blank column
# lands on. A lane that "finishes the job" by resolving the first candidate
# has built the option the PO explicitly declined.
#
# ⚠ **THE CREATE SCREEN IS UNTOUCHED.** `BR-MET-401` still refuses a premises
# with no owner there, because a clerk filling in a form knows the answer or
# can find it. This is the import, which is *"thousands of rows and half the
# owner answers are in a filing cabinet"*.
#
# ⚠ **WHAT IT COSTS, AND THE RECEIPT IS THE WHOLE MITIGATION.** No owner means
# no master account, so the address has NOBODY TO CHARGE — it holds units, it
# holds meters, it can be read, and it cannot be BILLED until somebody fills
# the owner in. `premises_with_no_owner` counts these rows and CR-055 task 2
# splits that count in two (`premises_owner_blank` vs
# `premises_owner_ambiguous`), because a blank needs RESEARCH and an ambiguity
# needs a DECISION between two named parties the file already knows.
#
#   · a NEAR match is a **WARNING** that loads ownerless (CR-055). It still
#     resolves nothing — merging two similar names bills the wrong landlord,
#     and creating a second party beside the first is the *"twelve unrelated
#     strings"* the typed record exists to stop — but refusing to choose no
#     longer costs the operator the address;
#
#   · an UNKNOWN name is a **WARNING** that loads, because a utility's FIRST
#     upload has no typed owners at all, so an error here would refuse every
#     row of every first import — the PO raised exactly that themselves
#     (*"we will need to careful what we do when we upload presmies in the
#     system first time"*). The row loads, the operator's string is kept as
#     BR-MET-151 provenance, and the address appears on the PRM-04 matching
#     list where a PERSON supplies the category the import may not invent
#     (BR-MET-151 clause 3: *Whitfield Rentals LLC* is not evidence of a
#     landlord). It is counted on the receipt, so it is not silent.
#
# ⚠ **A TENANT CAN STILL RAISE THIS ROW BACK TO `ERROR`, AND THAT IS TIER 2
# WORKING AS DESIGNED** (`resolve()` applies an `ImportRule` override). CR-055
# is a change to what the PRODUCT ships, not a new tier-1 floor; a utility that
# deliberately configures owner ambiguity as a blocker has made a choice and
# `import_rules` records it on the run.
PREMISES_RULES = PREMISES_RULES + (
    DeclaredRule(
        code="PRM.OWNER_NEAR_MATCH",
        target="premises",
        tier=TIER_PLATFORM,
        # CR-055 — the sentence had to change with the behaviour: it said
        # *"pick which party it is"* to an operator whose row had already been
        # thrown out. Two short sentences beat one long one (B14 copy rule).
        sentence="This owner matches two parties. The address loads with no owner.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="owner_near_match",
    ),
    DeclaredRule(
        code="PRM.OWNER_NOT_ON_FILE",
        target="premises",
        tier=TIER_PLATFORM,
        # ⚠ **THE SIGNED WALKTHROUGH SAYS THIS SENTENCE SHOULD READ *"No owner
        # record by this name — a master account is created for them"*, AND IT
        # DOES NOT SAY THAT YET, ON PURPOSE (hard-won law 1: a sentence
        # claiming a guarantee is not the guarantee).**
        # `OQ-790` is CLOSED and the ruling is *"call master account creation
        # logic … and generate account number using Setting -> numbering"*.
        # Three things block a literal build and none of them is a drawing:
        #   1. `accounts.unit_id` is **NOT NULL** and a brand-new premises has
        #      no units, so there is nothing lawful to anchor a master on;
        #      `create_master_account` refuses with `no_common_area_units`.
        #   2. `premises_owners.category_id` is NOT NULL, `BR-MET-151` clause 3
        #      forbids reading a category off a name, and the premises template
        #      offers no category column — which is exactly why `BR-MET-402`
        #      clause 5 (**CONFIRMED**) says *"THE IMPORT NEVER CREATES A
        #      PARTY"*. Building the opposite supersedes a signed rule.
        #   3. `accounts.account_type` is NOT NULL and the premises row states
        #      no account type.
        # Reported rather than half-built: the sentence keeps describing what
        # the code does, and the divergence from the page is on the record.
        #
        # ⛔ **CORRECTED 2026-09-01 — `CR-058` W3. TWO OF THOSE THREE OBSTACLES
        # ARE GONE AND THE SENTENCE IS STILL RIGHT, WHICH IS WHY THE PARAGRAPH
        # HAD TO BE AMENDED RATHER THAN LEFT (hard-won law 1: a comment
        # claiming a guarantee is not the guarantee, and a comment claiming an
        # IMPOSSIBILITY that has since become possible is worse — it stops the
        # next lane looking).**
        #   1. GONE. `accounts.unit_id` is NULLABLE and `accounts.premises_id`
        #      exists (`CR-056` W1, `BR-CUS-1010`), so a master account hangs
        #      off the ADDRESS and a premises with no units anchors nothing.
        #   3. GONE. The premises template now offers `owner_account_type`
        #      (`BR-MET-1030`), so the row can state it — and a row that does
        #      NOT state it creates nothing and says so
        #      (`PRM.OWNER_ACCOUNT_TYPE_MISSING`), rather than defaulting.
        #   2. **NARROWED 2026-09-19 — AND THIS RULE'S SENTENCE MOVED WITH
        #      IT.** It used to read *"STANDS — the template still offers no
        #      category column, so `BR-MET-402` clause 5's THE IMPORT NEVER
        #      CREATES A PARTY is untouched"*. The PO ruled *"Yes add owner
        #      category column in csv template"*, so the template DOES offer
        #      one and a row that STATES a category now creates and links the
        #      party. `premises_owners.category_id` is still NOT NULL and
        #      `BR-MET-151` clause 3 still forbids reading a category OFF A
        #      NAME — being TOLD one was never the same act. So clause 5 is
        #      narrowed, not reversed: **no party from a name alone.**
        # **The address can now get an OWNER ACCOUNT without a typed party**
        # (`BR-MET-1030`: the account hangs off the address; the party record
        # is a separate fact). So a row reaching this rule may still end with a
        # master account — through `PRM.OWNER_AWAITING_IDENTITY`'s sibling
        # path — and it still ends with no `premises_owners` row, which is
        # exactly what this sentence tells the operator.
        # ⚠ **THE SENTENCE NO LONGER PROMISES WAITING.** With a category stated
        # the row gets its owner record in this very run, so *"waits for
        # matching"* would be false on exactly the rows the 2026-09-19 ruling
        # fixed. It states the fact — nobody is on file by that name — and
        # leaves the consequence to `PRM.OWNER_CATEGORY_MISSING`, which fires
        # only when there really is nothing coming.
        sentence="No owner record by this name yet.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="owner_not_on_file",
    ),
    DeclaredRule(
        code="PRM.OWNER_COLUMN_EMPTY",
        target="premises",
        tier=TIER_PLATFORM,
        # ⛔ **NEW 2026-08-27 — the fourth answer, and it NARROWS `BR-MET-401`
        # to the create screen rather than reversing it.** PO verbatim: *"what
        # if owner column is empty - in such case we create the premises and
        # keep owner name empty - we cna edit and updaste it later"*.
        #
        # ⚠ **IT IS A DIFFERENT ROW FROM `PRM.OWNER_NOT_ON_FILE` AND THE
        # DIFFERENCE IS THE WHOLE POINT.** *"nobody is called that"* and *"the
        # column names nobody"* lead to opposite next actions — one wants a
        # party typed, the other wants an owner FOUND — and one sentence for
        # both is how the empty case went unnoticed until the PO read the
        # picture. `resolve_owner_name` answers `"empty"` for exactly this.
        #
        # ⚠ **WHAT IT COSTS, ON THE SCREEN RATHER THAN IN A DOCSTRING:** no
        # owner means no master account, so that address has NOBODY TO CHARGE.
        # It is a real premises — units, meters, readings — and it cannot be
        # billed until somebody fills the owner in. The run's receipt counts
        # these rows (`premises_with_no_owner`) so they can never be silently
        # indistinguishable from complete ones.
        sentence=(
            "The Owner column is empty — the address loads with no owner, and "
            "cannot be billed until someone fills it in."
        ),
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="owner_column_empty",
    ),    # ═══════════════════════════════════════════════════════════════════
    # CR-058 W3 · BR-MET-1030 — THREE REASONS AN OWNER GETS NO ACCOUNT
    # ═══════════════════════════════════════════════════════════════════
    #
    # ⛔ **PO RULING 2026-09-01:** *"If owner name is given and one identify
    # given - DL, SSN, Phone or Tax ID - then you create master account and
    # Customer ID - otherwise dont create anything"*.
    #
    # ⚠ **ALL THREE ARE `WARNING` + `FLAG_ONLY`, AND THAT IS THE RULING RATHER
    # THAN LENIENCY.** *"Otherwise dont create anything"* says what is NOT
    # created; it does not say the address is rejected. The 2026-08-27 ruling
    # that an ownerless premises LOADS is untouched, and an error here would
    # refuse every row of the first upload a utility ever sends.
    #
    # ⚠ **THREE RULES AND NOT ONE, BECAUSE THE NEXT ACTION IS DIFFERENT EACH
    # TIME** — `DEF-771` clause 3 and `CR-055`'s own split, applied before the
    # complaint arrives. *Find an identifier* is a filing-cabinet job; *choose a
    # category* is a thirty-second decision; *say whether this is a person or a
    # company* is a dropdown. One merged sentence would tell an operator that N
    # rows need attention and nothing about what kind.
    DeclaredRule(
        code="PRM.OWNER_AWAITING_IDENTITY",
        target="premises",
        tier=TIER_PLATFORM,
        sentence=(
            "This owner has a name and no identifier, so no owner account is "
            "created for the address."
        ),
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="owner_awaiting_identity",
    ),
    DeclaredRule(
        code="PRM.OWNER_ACCOUNT_TYPE_MISSING",
        target="premises",
        tier=TIER_PLATFORM,
        # ⚠ **NOTHING MAY GUESS WHAT A CUSTOMER IS CHARGED AS.** The account
        # type is the consumer category the bill is priced and reported by;
        # defaulting it to `residential` for a builder's site is a money
        # decision taken by a shrug. So a row that HAS the identity and lacks
        # this creates nothing either, and is told which cell is missing.
        sentence=(
            "This owner can be identified but the row says nothing about how "
            "their account is charged, so no owner account is created."
        ),
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="owner_account_type_missing",
    ),
    DeclaredRule(
        code="PRM.OWNER_CATEGORY_MISSING",
        target="premises",
        tier=TIER_PLATFORM,
        # ⛔ **NEW 2026-09-19 — PO RULING: *"Yes add owner category column in
        # csv template"*. THE FOURTH REASON, AND IT IS THE ONLY ONE THAT DOES
        # NOT COST THE ROW ITS ACCOUNT.**
        # The other three say *no owner account is created*. This one says the
        # opposite: the account IS created, and the OWNER RECORD is not. Until
        # today that outcome was unavoidable and silent — every row of a first
        # migration produced an account attached to a building with nobody
        # named on it, and the receipt reported the account and not the gap.
        #
        # ⚠ **`WARNING` + `FLAG_ONLY`, LIKE ITS THREE SIBLINGS, AND HERE IT
        # MATTERS MOST.** A utility that has not set its categories up yet must
        # still be able to load its addresses; an error would refuse the first
        # upload it ever sends, which is `DEF-1088`'s lesson in as many words.
        #
        # ⚠ **IT FIRES ONLY WHERE STATING A CATEGORY WOULD CHANGE THE OUTCOME**
        # — the row earns an account AND the owner is not already on file. A
        # name already on file needs no category: the party exists and the
        # import links to it, which is the branch that always worked.
        sentence=(
            "This owner gets an account but no owner record — the row does not "
            "say what kind of owner they are."
        ),
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="owner_category_missing",
    ),
    DeclaredRule(
        code="PRM.OWNER_CATEGORY_IN_LOOKUP",
        target="premises",
        tier=TIER_PLATFORM,
        # ⛔ **`DEF-618`'s RULE, ON THE COLUMN PO 2026-09-19 ADDED.** Every
        # `KIND_LOOKUP` column owes one of these: the value-map step resolves
        # what it can and says NOTHING about what it could not, so an
        # unrecognised value reaches stage 4 as a silent `None`.
        #
        # ⚠ **WITHOUT IT THE OPERATOR IS TOLD THE OPPOSITE OF WHAT THEY DID.**
        # `PRM.OWNER_CATEGORY_MISSING` beside this one says *"the row does not
        # say what kind of owner they are"* — true of a blank cell and false of
        # a typo, and the two are indistinguishable once the lookup has answered
        # `None`. This fires on the raw text being present and unresolved, so
        # only one of the two can ever hit a row.
        #
        # ⚠ **WARNING + FLAG_ONLY**, like `PRM.TYPE_IN_LOOKUP` and unlike
        # `ACC.TYPE_IN_LOOKUP`: the address and its owner account still load,
        # and only the owner RECORD is not created. Rejecting the row would
        # throw away an address over a spelling.
        sentence="The owner category is one of the categories on file.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="owner_category_in_lookup",
    ),
    DeclaredRule(
        code="PRM.OWNER_IDENTITY_MISMATCH",
        target="premises",
        tier=TIER_PLATFORM,
        # ⚠ **`BR-CUS-1022` — WHICH IDENTIFIER COUNTS DEPENDS ON THE KIND.** A
        # person is known by a Social Security number, a driving licence or a
        # phone; a company by its Tax ID. An identifier presented under an
        # unstated kind cannot be judged at all, and one belonging to the OTHER
        # kind is filed where that kind's matcher will never look. Both are
        # caught on the operator's own file rather than by the writer refusing
        # on row 9,881 — the reason `account_lookup_indexes` exists.
        sentence=(
            "This owner's identifier does not match the kind of party stated, "
            "so no owner account is created."
        ),
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="owner_identity_mismatch",
    ),
)


UNITS_RULES: tuple[DeclaredRule, ...] = (
    DeclaredRule(
        code="UNT.LABEL_REQUIRED",
        target="units",
        tier=TIER_STRUCTURAL,
        sentence="Every unit has a label.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="required_field",
        params={"field": "label", "noun": "unit label"},
    ),
    DeclaredRule(
        code="UNT.VALUES_PARSE",
        target="units",
        tier=TIER_STRUCTURAL,
        sentence="Every value has to be the kind of value its column holds.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="values_parse",
    ),
    DeclaredRule(
        code="UNT.PARENT_PREMISE_ON_FILE",
        target="units",
        tier=TIER_STRUCTURAL,
        sentence="Parent premise must already exist.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="parent_premise_on_file",
    ),
    # ⛔ **RAISED FROM WARNING TO ERROR ON 2026-08-27, AND SPLIT IN TWO — PO
    # ruling, verbatim: *"premsies and unit name - not just unit name that
    # combination is unique"*.**
    #
    # It was flag-only while `(premises, label)` was merely a sensible
    # convention. It is the unit's IDENTITY now (`uq_units_tenant_premises_
    # label`, and the PO's own words), so a second `Apt 3B` at one address is
    # **two rows claiming to be the same unit**, not a warning.
    #
    # ⚠ **BUT ONLY THE IN-FILE HALF CAN BE AN ERROR, AND THIS IS DEF-543's
    # LESSON RATHER THAN A HEDGE.** This evaluator used to fire on BOTH a
    # duplicate inside the file and a match against a unit already on file, and
    # raising THAT to an error would reject every legitimate *Insert & update*
    # row — the exact rows the mode exists for. So the on-file half moves to
    # `UNT.PAIR_ON_FILE` below, where the run's own write mode decides.
    DeclaredRule(
        code="UNT.LABEL_UNIQUE_IN_PREMISE",
        target="units",
        tier=TIER_STRUCTURAL,
        sentence="One premises cannot hold two units with the same label.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="unit_label_unique",
    ),
    DeclaredRule(
        code="UNT.PAIR_ON_FILE",
        target="units",
        tier=TIER_PLATFORM,
        # ⛔ **THE IDENTITY MATCH, AND IT IS THE ROW *Insert & update* EXISTS
        # FOR.** Same mechanism as every other target's *number already on
        # file* rule (`NUMBER_ON_FILE_KINDS`), keyed on the PAIR because the
        # pair is what identifies a unit.
        #
        # ⚠ **THE PREMISES IS HALF THE KEY AND LEAVING IT OUT IS A SILENT
        # OVERWRITE.** Matching on the label alone would find a DIFFERENT
        # BUILDING'S flat and update it — a row that loads clean, reports
        # `updated`, and has quietly rewritten someone else's unit. It is the
        # failure that never looks like a failure, which is why it has a test
        # of its own (`test_cr046_c3__same_label_two_premises_*`).
        sentence="This row names a unit already on file.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="unit_pair_on_file",
    ),
    # ── CR-046 C3 · THE UNIT NUMBER, AND THE IDENTITY QUESTION IT ASKED ─────
    #
    # ⛔ **CR-046 C3 SAYS TO CONFIRM FIRST *"whether a unit's identity is its
    # number or its label within a premises"* AND TO BUILD TO WHICHEVER THE
    # DATABASE MAKES UNIQUE. IT MAKES BOTH UNIQUE AND ONLY ONE OF THEM
    # MANDATORY, WHICH IS THE ANSWER.**
    #
    #   `uq_units_tenant_premises_label`  (tenant, premises, label) — `label`
    #       is NOT NULL and `premises` is NOT NULL, so EVERY unit has this key.
    #   `uq_units_tenant_unit_no`         (tenant, unit_no) — `unit_no` is
    #       NULLABLE and Postgres does not collide NULLs, so N units may carry
    #       no number at all and still be lawful.
    #
    # **A column that can be absent cannot be an identity.** So the unit's
    # identity is its LABEL WITHIN ITS PREMISES, and `unit_no` is the strongest
    # STATEMENT an operator can make when they do quote one. That is why
    # `_key_of` tries the number first and falls back to the composite, and why
    # these two rules are about a QUOTED number rather than about identity.
    # Decision log 2026-08-27, "THE UNIT'S IDENTITY IS ITS LABEL WITHIN ITS
    # PREMISES".
    DeclaredRule(
        code="UNT.NUMBER_UNIQUE",
        target="units",
        tier=TIER_STRUCTURAL,
        # `uq_units_tenant_unit_no` arriving early. IN-FILE only — the on-file
        # half is the mode-dependent rule below.
        sentence="A unit number can only be used once.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="unit_no_unique",
    ),
    DeclaredRule(
        code="UNT.NUMBER_ON_FILE",
        target="units",
        tier=TIER_PLATFORM,
        # The C1 shape, one noun along: the head states the FACT, and
        # `_for_write_mode` appends what the run's own mode will do about it.
        sentence="This row names a unit already on file.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="unit_no_on_file",
    ),
    DeclaredRule(
        code="UNT.NUMBER_NOT_ON_FILE",
        target="units",
        tier=TIER_PLATFORM,
        # The opposite predicate — an invented number, wrong in both modes.
        sentence=(
            "A unit number is issued by your numbering settings — leave this "
            "column blank for a new one."
        ),
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="unit_no_not_on_file",
    ),
    DeclaredRule(
        code="UNT.EXTERNAL_REF_UNIQUE",
        target="units",
        tier=TIER_STRUCTURAL,
        # CR-046 C5 / BR-MET-404 — `uq_units_tenant_external_ref_ci` arriving
        # early. In-file only, for `PRM.EXTERNAL_REF_UNIQUE`'s stated reason.
        sentence="A row's external reference can only be used once in a file.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="external_ref_unique",
    ),
    DeclaredRule(
        code="UNT.PLAN_ON_FILE",
        target="units",
        tier=TIER_PLATFORM,
        # ⚠ The sentence says what HAPPENS, because BR-MET-100's whole risk is
        # that an unplanned unit looks finished. An operator reading "plan not
        # found" would assume the row failed; it did not.
        sentence="Plan must already exist — a unit naming an unknown plan loads with no plan and is flagged.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="plan_on_file",
    ),
    DeclaredRule(
        code="UNT.TYPE_IN_LOOKUP",
        target="units",
        tier=TIER_PLATFORM,
        sentence="Unit type exists in the lookup table.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="unit_type_in_lookup",
    ),
)

#: ── THE THREE ASSETS CATALOGS (CR-028 AST-W3 · B16 §4.7b · BR-AST-045) ─────
#:
#: Rule sentences and severities are B16 §4.7b's table ("errors block,
#: warnings flag"), with three DOCUMENTED judgments:
#:
#:   * **Blank unit is NOT a rule at all** (BR-AST-045, PO verbatim: *"If they
#:     dont provide unit, its okay, we will still accept them"*) — a blank
#:     `UNIT_REF` loads to inventory, so no evaluator fires on it.
#:   * **A number already ON FILE is a WARNING, not the error** — DEF-543's
#:     lesson applied on day one: stage 3 cannot know the write mode, and the
#:     on-file match is precisely the row `Insert & update` exists for. The
#:     in-file duplicate stays the ERROR (the later row would silently win).
#:     ⚠ **AND SINCE 2026-08-27 A NUMBER **NOT** ON FILE IS ALSO AN ERROR**
#:     (`AST.NUMBER_NOT_ON_FILE`). The PO ruled that a meter's number is issued
#:     by the tenant's numbering settings and never taken from a file, so an
#:     unrecognised number is an invented one — wrong in BOTH write modes,
#:     which is what lets it block where the on-file case still cannot.
#:   * **An unknown DEVICE TYPE is an ERROR, diverging from r10's "W → Other"
#:     on purpose.** `assets.type` is a non-null FK and BR-AST-004 seeds no
#:     "Other" — r10's action would set a foreign key to a code no tenant has,
#:     which is exactly the `Default to Residential` shape OQ-329 already
#:     refused to ship (see PRM.TYPE_IN_LOOKUP above). A row whose type cannot
#:     resolve cannot be created at all, so the severity is structural.


def _assets_common(target: str, noun: str) -> tuple[DeclaredRule, ...]:
    """The rules every assets target shares. Built per target because a
    DeclaredRule carries its target and a run copies it verbatim
    (BR-MET-090)."""
    return (
        DeclaredRule(
            code="AST.VALUES_PARSE",
            target=target,
            tier=TIER_STRUCTURAL,
            sentence="Every value has to be the kind of value its column holds.",
            severity=ERROR,
            action=REJECT_ROW,
            rule_kind="values_parse",
        ),
        DeclaredRule(
            code="AST.NUMBER_UNIQUE",
            target=target,
            tier=TIER_STRUCTURAL,
            # `uq_assets_tenant_no` (BR-AST-008/033: duplicate asset # is a
            # HARD BLOCK). In-file only — the on-file half is the warning below.
            sentence=f"A {noun} number can only be used once.",
            severity=ERROR,
            action=REJECT_ROW,
            rule_kind="asset_no_unique",
        ),
        DeclaredRule(
            code="AST.NUMBER_ON_FILE",
            target=target,
            tier=TIER_PLATFORM,
            # ⛔ **AMENDED 2026-08-27 — THE SENTENCE CHANGED MEANING WITH THE
            # COLUMN.** It read *"This {noun} number is already on file — the
            # write mode decides what happens to it"*, which was true while a
            # file could bring its own number. Under the PO ruling it cannot:
            # a value here is only ever a quote of a number WE issued, so a
            # match is the EXPECTED case rather than a coincidence, and the
            # thing worth saying is what each mode will then do with it.
            #
            # ⚠ **IT IS STILL A WARNING, AND STILL FOR `DEF-543`'S REASON:
            # STAGE 3 CANNOT KNOW THE WRITE MODE.** The ruling says a value in
            # Insert mode is an error — and the mode is chosen at stage 1,
            # changeable at stage 4, and NOT an input to any rule here. So the
            # mode-dependent half is refused where the mode is actually known
            # (`_insert_mode_on_file_sentences`, per row, at the rehearsal and
            # the commit) and this rule carries the mode-INDEPENDENT half.
            # ⛔ **THE SUBJECT IS THE ROW, NOT THE NUMBER (CR-046 F2).** The PO
            # asked *"Does this row name a meter already on file?"*, and since
            # BR-AST-049 a row can name one two ways — by quoting our number,
            # or by carrying the `external_ref` it was loaded with. A sentence
            # about "this number" would be silent about the second, which is
            # the one a first migration's correction re-run actually uses.
            #
            # ⚠ THE HEAD OF THIS SENTENCE IS PARSED BY `_for_write_mode`, which
            # replaces everything after the first `.` with a per-mode tail.
            # Keep the first sentence a complete statement of the CONDITION.
            sentence=(
                f"This row names a {noun} already on file. The write mode "
                "decides what happens to it."
            ),
            severity=WARNING,
            action=FLAG_ONLY,
            rule_kind="asset_no_on_file",
        ),
        DeclaredRule(
            code="AST.NUMBER_NOT_ON_FILE",
            target=target,
            tier=TIER_PLATFORM,
            # ⛔ **NEW 2026-08-27 — THE HALF `AST.NUMBER_ON_FILE` COULD NOT
            # CARRY, BECAUSE IT IS THE OPPOSITE PREDICATE.**
            #
            # PO verbatim: *"here we should not allow usse to fill in Asset ID
            # - we have number system set in the settings, we shoudl call that
            # function and get unique number and assign it"*. A number that is
            # NOT on file is the shape of that objection exactly: the operator
            # has invented one. It is wrong in BOTH write modes — in Insert
            # there is nothing to name, in Insert & update it names nothing —
            # so unlike the rule above it needs no knowledge of the mode and
            # can be a hard ERROR at stage 3, where the operator can still fix
            # the file by clearing a cell.
            #
            # ⚠ **THIS IS WHY THE OLD RULE WAS AMENDED AND NOT REPLACED.** One
            # rule cannot say both "already on file" and "not on file"; the two
            # sentences are about different rows and only one of them blocks.
            sentence=(
                f"A {noun} number is issued by your numbering settings — leave "
                "this column blank for a new one."
            ),
            severity=ERROR,
            action=REJECT_ROW,
            rule_kind="asset_no_not_on_file",
        ),
        DeclaredRule(
            code="AST.EXTERNAL_REF_UNIQUE",
            target=target,
            tier=TIER_STRUCTURAL,
            # BR-AST-049 — `uq_assets_tenant_external_ref_ci` arriving early.
            # ⚠ **IN-FILE ONLY, and the reason is the mirror of
            # `AST.NUMBER_UNIQUE`'s:** a reference that matches one ON FILE is
            # the MATCH KEY doing its job (`_key_of`), not a collision. Two
            # rows of the SAME file claiming one reference is a collision, and
            # catching it here is what keeps the database's refusal from
            # aborting a 1,847-row commit over one bad pair.
            sentence="A row's external reference can only be used once in a file.",
            severity=ERROR,
            action=REJECT_ROW,
            rule_kind="external_ref_unique",
        ),
    )


def _assets_meter_rules(target: str, noun: str) -> tuple[DeclaredRule, ...]:
    """The rules the meters and sub-meters targets share on top of the common
    set — service law, unit tagging, multiplier, certification, lookups."""
    return (
        DeclaredRule(
            code="AST.SERVICE_ENABLED",
            target=target,
            tier=TIER_STRUCTURAL,
            # BR-AST-009 + BR-MET-003: a measuring asset DECLARES its service,
            # and only a service this utility sells.
            sentence=f"Every {noun} names a service this utility sells.",
            severity=ERROR,
            action=REJECT_ROW,
            rule_kind="asset_service_enabled",
        ),
        DeclaredRule(
            code="AST.SERVICE_AT_PREMISES",
            target=target,
            tier=TIER_STRUCTURAL,
            # BR-MET-119 (PO 2026-08-26, CR-036): PREMISES → UNITS → METERS. The
            # rule above is the OUTER bound — *"does this utility sell it"* —
            # and this is the INNER one: *"does THIS ADDRESS have it"*. TIER 1
            # because the loader refuses the row whatever this table says
            # (`services.ensure_service_point`), and a switchable rule would
            # tell an operator the load succeeded when it did not.
            sentence=f"Every {noun} names a service its unit's address offers.",
            severity=ERROR,
            action=REJECT_ROW,
            rule_kind="asset_service_at_premises",
        ),
        DeclaredRule(
            code="AST.SERVICE_HAS_UNIT",
            target=target,
            tier=TIER_STRUCTURAL,
            # ⛔ **`DEF-935` — THE PO'S OWN SYMPTOM: A CLEAN REHEARSAL AND A
            # COMMIT THAT DIES.** `CLAUDE.md` rule 3 and BR-AST-009 require an
            # EXPLICIT unit on a measuring asset and there is correctly no
            # assume-kWh branch anywhere, so `_check_measuring_requirements`
            # refuses the row at LOAD time when the tenant declares no unit for
            # the service it names. Nothing asked the question one stage
            # earlier, so the operator read *"Will create 20 · Rows rejected
            # 0"*, pressed Commit, and the single transaction refused on row 1.
            #
            # ⚠ TIER 1, for the reason `AST.SERVICE_AT_PREMISES` gives verbatim
            # one rule up: the loader refuses the row whatever this table says,
            # and a switchable rule would tell an operator the load succeeded
            # when it did not.
            #
            # This is DEF-618 / DEF-619's class on a third input, and the
            # difference is where it is caught, never whether: the refusal is
            # RIGHT — a reading with no unit is the one thing this product may
            # never store (hard rule 3).
            sentence=(
                f"The service a {noun} measures has a unit on file — a service "
                "with no unit cannot carry a reading."
            ),
            severity=ERROR,
            action=REJECT_ROW,
            rule_kind="asset_service_has_unit",
        ),
        DeclaredRule(
            code="AST.UNIT_ON_FILE",
            target=target,
            tier=TIER_STRUCTURAL,
            # BR-AST-045's other half: a NAMED unit must exist. Blank is
            # accepted (inventory) and never reaches this rule.
            sentence="A named unit must already be on file — blank loads to inventory.",
            severity=ERROR,
            action=REJECT_ROW,
            rule_kind="unit_ref_on_file",
        ),
        DeclaredRule(
            code="AST.UNIT_BLANK_TO_INVENTORY",
            target=target,
            tier=TIER_PLATFORM,
            # ⛔ **`DEF-1079` — A LAWFUL VALUE WITH A MATERIAL CONSEQUENCE MUST
            # REACH THE SUMMARY, NOT ONLY A SIDE PANEL.** The Product Owner
            # loaded twenty meters with `unit_ref` blank on every row. The KPI
            # strip read **"NO REMARKS AT ALL — 20"** while the panel directly
            # below read *"Unit — mapped from `unit_ref`, and blank in all 20
            # rows. Nothing will be written to it."* **Both were true**, and
            # the summary won, because `counts.clean` counts rows with no RULE
            # HIT and a blank unit fired no rule PRECISELY BECAUSE IT IS
            # LAWFUL. So the single most consequential fact about that load —
            # twenty meters that cannot take a reading or be billed until
            # somebody assigns them — was reported only in grey.
            #
            # ⚠ **A WARNING, AND IT MUST STAY A WARNING.** BR-AST-045 is the
            # PO's own ruling and a blank unit loading to inventory is
            # CORRECT; nothing here may stop the row (BR-MET-129). What was
            # wrong was never the rule, it was the silence.
            #
            # ⚠ **AND IT FIRES ON THE OPPOSITE CONDITION TO THE RULE ABOVE.**
            # `AST.UNIT_ON_FILE`'s sentence — *"blank loads to inventory"* —
            # reads as reassurance and fires only when a unit IS named and is
            # missing, so on the PO's file it reported zero hits and said
            # nothing about the twenty rows it was describing.
            sentence=(
                f"This {noun} names no unit, so it loads into inventory — it "
                "cannot take a reading or be billed until it is assigned."
            ),
            severity=WARNING,
            action=FLAG_ONLY,
            rule_kind="unit_ref_blank_to_inventory",
        ),
        DeclaredRule(
            code="AST.MULTIPLIER_POSITIVE_INT",
            target=target,
            tier=TIER_PLATFORM,
            # B16 §4.7b verbatim: "multiplier positive int (W→default ×1)".
            # The sentence says what HAPPENS (BR-MET-100's copy discipline).
            sentence=(
                "The multiplier is a whole number above zero — anything else "
                "loads at ×1 and is flagged."
            ),
            severity=WARNING,
            action=DEFAULT_TO,
            action_value="1",
            rule_kind="multiplier_positive_int",
        ),
        DeclaredRule(
            code="AST.CERT_DUE_FUTURE",
            target=target,
            tier=TIER_PLATFORM,
            # B16 §4.7b: "cert date future (W→flag test due)" — a CERT_DUE
            # already in the past flags the meter as test-due on arrival.
            sentence="The certification-due date is in the future — a past one flags the meter test-due.",
            severity=WARNING,
            action=FLAG_ONLY,
            rule_kind="cert_due_future",
        ),
        DeclaredRule(
            code="AST.METER_TYPE_IN_LOOKUP",
            target=target,
            tier=TIER_PLATFORM,
            sentence="The meter type is one of the types on file.",
            severity=WARNING,
            action=FLAG_ONLY,
            rule_kind="meter_type_in_lookup",
        ),
        DeclaredRule(
            code="AST.READ_METHOD_IN_LOOKUP",
            target=target,
            tier=TIER_PLATFORM,
            sentence="The read method is one of the methods on file.",
            severity=WARNING,
            action=FLAG_ONLY,
            rule_kind="read_method_in_lookup",
        ),
    )


def _upload_fix_rules(
    target: str, noun: str, *, sized: bool, submeter: bool = False, device: bool = False
) -> tuple[DeclaredRule, ...]:
    """⛔ **PLAN U4 / U5 — THE ROW CHECKS THE PO CONFIRMED ON 2026-09-30**
    (`04-docs/05-modules/05-assets/12-asset-upload-fix-plan.md`; PO: *"these
    are all correct + all these tasks are good"*). Every one TIER 1 and an
    ERROR — see the block comment above the evaluators for why: *"all problems
    at once"* needs every rule to see every row."""

    def rule(code: str, kind: str, sentence: str) -> DeclaredRule:
        return DeclaredRule(
            code=code,
            target=target,
            tier=TIER_STRUCTURAL,
            sentence=sentence,
            severity=ERROR,
            action=REJECT_ROW,
            rule_kind=kind,
        )

    rules = [
        rule(
            "AST.UOM_FOR_SERVICE",
            "uom_for_service",
            f"A {noun}'s unit of measure is one its service allows — blank takes "
            "the service's own unit.",
        )
    ]
    if sized:
        rules.append(
            rule(
                "AST.SIZE_FOR_SERVICE",
                "size_for_service",
                f"A {noun}'s size comes from its own service's list.",
            )
        )
    if not device:
        rules.append(
            rule(
                "AST.REGISTER_DIGITS_IN_RANGE",
                "register_digits_in_range",
                "Register digits are 4 to 10 — blank means 9.",
            )
        )
    if submeter:
        rules.extend(
            [
                rule(
                    "AST.ALLOCATION_RULE_IN_LIST",
                    "allocation_rule_in_list",
                    "The allocation rule is rubs, sqft, equal or absorb — blank is "
                    "metered, not allocated.",
                ),
                rule(
                    "AST.LOSS_TOLERANCE_IN_RANGE",
                    "loss_tolerance_in_range",
                    "A loss tolerance is 0 to 100%.",
                ),
            ]
        )
    if submeter or device:
        rules.append(
            rule(
                "AST.PARENT_SAME_SERVICE",
                "parent_same_service",
                f"A {noun}'s parent meter measures the same service.",
            )
        )
    return tuple(rules)


ASSETS_METERS_RULES: tuple[DeclaredRule, ...] = (
    *_assets_common("assets_meters", "meter"),
    *_assets_meter_rules("assets_meters", "meter"),
    DeclaredRule(
        code="AST.UNIT_SERVICE_FREE",
        target="assets_meters",
        tier=TIER_PLATFORM,
        # r10 WFL-01.meters.3 row 588 verbatim shape: "Unit U-10688-A already
        # has an active electric meter" → "Load into inventory instead". An
        # ERROR-severity platform rule: no DB constraint enforces it, but a
        # second active meter on one unit+service is a bill nobody can price
        # unambiguously (B16 §4.7a — the rule that keeps billing unambiguous).
        # ⚠ METERS ONLY — a sub-meter coexists with the unit's own meter by
        # design (the seeded registry is exactly that shape), so the
        # sub-meters catalog deliberately does not carry this rule.
        sentence="The unit has no other active meter for this service.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="unit_service_free",
    ),
    DeclaredRule(
        code="AST.SIZE_CLASS_IN_LOOKUP",
        target="assets_meters",
        tier=TIER_STRUCTURAL,
        # ⛔ **BR-MET-530 — PO ruling 2026-08-28, *"Please do both"*.** TIER 1
        # and ERROR for the reason the evaluator states at length: an unknown
        # size that merely flags loads a meter that then bills off the
        # every-size ladder, silently. TIER 1 rather than TIER 3 because a
        # tenant switching this rule OFF would be switching on exactly the
        # silent mispricing DEF-514/DEF-1900 were filed for — the same posture
        # `AST.SERVICE_AT_PREMISES` states one rule up.
        #
        # ⚠ **METERS ONLY.** The sub-meters catalogue deliberately does not
        # carry it, because the sub-meters TEMPLATE deliberately does not carry
        # the column (ruling judgment 4 — that boundary is `DEF-1901`'s to
        # widen, not this lane's).
        #
        # The sentence says what is TRUE of a good row (BR-MET-100's copy
        # discipline), and the blank case is stated in it because blank is the
        # lawful, common answer on a first migration.
        sentence=(
            "The connection size is one of the sizes on file \u2014 blank is fine "
            "and means no size is recorded."
        ),
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="size_class_in_lookup",
    ),
    *_upload_fix_rules("assets_meters", "meter", sized=True),
)

ASSETS_SUBMETERS_RULES: tuple[DeclaredRule, ...] = (
    *_assets_common("assets_submeters", "sub-meter"),
    *_assets_meter_rules("assets_submeters", "sub-meter"),
    DeclaredRule(
        code="AST.PARENT_ON_FILE",
        target="assets_submeters",
        tier=TIER_STRUCTURAL,
        # BR-AST-003 (a sub-meter REQUIRES a meter/net-meter parent) + B16
        # §4.7b ("parent exists & active (E)").
        sentence="The parent master meter must already be on file and active.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="parent_meter_on_file",
    ),
    DeclaredRule(
        code="AST.ALLOC_WITHIN_MASTER",
        target="assets_submeters",
        tier=TIER_PLATFORM,
        # B16 §4.7b "sub total ≤ master (W→review)", computed WHERE COMPUTABLE:
        # the in-file allocation shares under one master may not exceed 100%.
        sentence="Allocation shares under one master total at most 100% — a larger total is flagged for review.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="alloc_within_master",
    ),
    DeclaredRule(
        code="AST.ALLOC_SHARE_IN_RANGE",
        target="assets_submeters",
        tier=TIER_STRUCTURAL,
        # ⛔⛔ **CR-047 — ONE OF THE TWO ASSETS REFUSALS THE REHEARSAL COULD NOT
        # SEE, AND IT IS NOT THE RULE DIRECTLY ABOVE IT.**
        #
        # `AST.ALLOC_WITHIN_MASTER` measures the in-file TOTAL under one master
        # and WARNS, which is right: two rows of 60% total 120%, and the writer
        # accepts both, because 60 is a lawful share of a master. What it
        # cannot see is ONE ROW claiming more than the whole master —
        # `assets.services._validate_asset` refuses `allocation_share_pct > 100`
        # by name (`assets.allocation_share_range`), from under the write.
        #
        # So until this rule the rehearsal said *"flagged — will load"* on a row
        # the commit was certain to refuse, which is `DEF-2519`'s exact shape on
        # the sub-meters target: before CR-047's savepoint that refusal escaped
        # `_load_assets_rows`' loop and took the whole run with it.
        #
        # ⚠ TIER 1, for the reason `AST.SERVICE_AT_PREMISES` gives verbatim: the
        # loader refuses the row whatever this table says, and a switchable rule
        # would tell an operator the load succeeded when it did not.
        #
        # ⚠ **`100` EXACTLY IS LAWFUL** — the writer's predicate is `> 100`, and
        # a single sub-meter carrying its master's whole load is an ordinary
        # arrangement. The rule quotes the predicate rather than approximating
        # it, because a rehearsal that is stricter than the write rejects rows
        # the product would have accepted.
        sentence="A sub-meter's share of its master is at most 100%.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="alloc_share_in_range",
    ),
    DeclaredRule(
        code="AST.UNIT_PREMISES_MATCHES_MASTER",
        target="assets_submeters",
        tier=TIER_PLATFORM,
        # B16 §4.7b "unit same premises as master" — a WARNING: a sub hung off
        # a master across the street is unusual, not impossible.
        sentence="The sub-meter's unit sits on the same premises as its master.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="sub_unit_premises_matches_master",
    ),
    *_upload_fix_rules("assets_submeters", "sub-meter", sized=False, submeter=True),
)

ASSETS_DEVICES_RULES: tuple[DeclaredRule, ...] = (
    *_assets_common("assets_devices", "device"),
    DeclaredRule(
        code="AST.DEVICE_TYPE_ON_FILE",
        target="assets_devices",
        tier=TIER_STRUCTURAL,
        # ⚠ ERROR where r10 says "W → Other" — see the block comment above.
        sentence="Every device names a behind-the-meter type on this tenant's list.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="device_type_on_file",
    ),
    DeclaredRule(
        code="AST.PREMISES_ON_FILE",
        target="assets_devices",
        tier=TIER_STRUCTURAL,
        # B16 §4.7b "premises exists (E)" — CR-023's precedent applied:
        # "Load the premise first". Blank premises AND blank unit → inventory
        # (BR-AST-045), so neither blank reaches this rule.
        sentence="A named premises must already be on file — blank loads to inventory.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="device_premises_on_file",
    ),
    DeclaredRule(
        code="AST.UNIT_ON_FILE",
        target="assets_devices",
        tier=TIER_STRUCTURAL,
        sentence="A named unit must already be on file — blank loads to inventory.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="unit_ref_on_file",
    ),
    DeclaredRule(
        code="AST.UNIT_BLANK_TO_INVENTORY",
        target="assets_devices",
        tier=TIER_PLATFORM,
        # DEF-1079 on the third target. ⚠ **A DEVICE HAS TWO WAYS TO BE
        # SEATED** (BR-AST-045): its own unit, or the one unit of a named
        # premises. So this fires only when BOTH are blank — the evaluator
        # skips a row naming a premises, and a device that names one is going
        # into service, not into inventory.
        sentence=(
            "This device names neither a unit nor a premises, so it loads "
            "into inventory — it cannot take a reading until it is assigned."
        ),
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="unit_ref_blank_to_inventory",
    ),
    DeclaredRule(
        code="AST.NEXT_TEST_DERIVABLE",
        target="assets_devices",
        tier=TIER_PLATFORM,
        # B16 §4.7b: "next-test present when frequency set (W→derive from
        # install date)" — the one assets action that WRITES a defaulted value,
        # and the sentence says so (BR-MET-090's two-column discipline).
        sentence=(
            "A device with a test frequency states its next test — a missing "
            "one is derived from the install date and flagged."
        ),
        severity=WARNING,
        action=DEFAULT_TO,
        action_value="install_date + frequency",
        rule_kind="next_test_derivable",
    ),
    DeclaredRule(
        code="AST.TEST_INTERVAL_POSITIVE",
        target="assets_devices",
        tier=TIER_STRUCTURAL,
        # ⛔⛔ **CR-047 — THE SECOND ASSETS REFUSAL THE REHEARSAL COULD NOT SEE.**
        #
        # `0` is how a clerk spells *"never"* in a spreadsheet column headed
        # *Test frequency (months)*. It is a whole number, so stage 2 parses it
        # without complaint and `AST.VALUES_PARSE` says nothing; then
        # `assets.services._validate_asset` refuses `months < 1` by name
        # (`assets.test_interval_range`) from under the write. A negative reaches
        # the same refusal, because `KIND_INTEGER` accepts a leading sign.
        #
        # ⚠ **A BLANK CELL IS THE LAWFUL WAY TO SAY THE SAME THING AND MUST NOT
        # FIRE.** `_create_asset_inner` fills an absent interval from
        # `SEED_TEST_INTERVAL_MONTHS` for the device's own type (a backflow
        # preventer gets 12), so a file with no frequency column at all loads
        # every row. A rule that demanded a value would reject rows the loader
        # writes without complaint — the trap `ACC.UNIT_NOT_OCCUPIED` documents
        # one catalogue down.
        #
        # ⚠ TIER 1, for `AST.SERVICE_AT_PREMISES`' stated reason: the writer
        # refuses the row whatever this table says.
        #
        # ⚠ **IT IS THE OTHER HALF OF THE RULE ABOVE, NOT A DUPLICATE OF IT.**
        # `AST.NEXT_TEST_DERIVABLE` asks whether a device WITH a frequency
        # states its next test and derives one when it does not; this asks
        # whether the frequency is a length of time at all. On a row carrying
        # `0` the rule above would happily derive `install date + 0 months`.
        sentence=(
            "A test frequency is a number of months above zero — leave it "
            "blank for the usual interval for this kind of device."
        ),
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="test_interval_positive",
    ),
    # ⛔ **PLAN U2/U4/U5 — THE DEVICES SHEET'S SERVICE, SIZE AND PARENT (PO
    # ruling 2026-09-30).** A device is counted on the bill through its SERVICE
    # POINT (`billable_asset_count`), so the service is REQUIRED and must be one
    # the utility sells and the device's unit has. The two lookup rules reuse
    # the meters' evaluators — one resolver per question (DEF-544).
    DeclaredRule(
        code="AST.SERVICE_ENABLED",
        target="assets_devices",
        tier=TIER_STRUCTURAL,
        sentence="Every device names a service this utility sells.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="asset_service_enabled",
    ),
    DeclaredRule(
        code="AST.DEVICE_SERVICE_ON_UNIT",
        target="assets_devices",
        tier=TIER_STRUCTURAL,
        # TIER 1 for `AST.SERVICE_AT_PREMISES`' reason: the loader refuses the
        # row whatever this table says (`ensure_service_point`).
        sentence="A device's unit has the device's service.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="device_service_on_unit",
    ),
    DeclaredRule(
        code="AST.SIZE_CLASS_IN_LOOKUP",
        target="assets_devices",
        tier=TIER_STRUCTURAL,
        sentence="The size is one of the sizes on file — blank is fine and means no size is recorded.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="size_class_in_lookup",
    ),
    DeclaredRule(
        code="AST.PARENT_ON_FILE",
        target="assets_devices",
        tier=TIER_STRUCTURAL,
        sentence="A named parent meter must already be on file and active — blank is fine.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="device_parent_on_file",
    ),
    *_upload_fix_rules("assets_devices", "device", sized=True, device=True),
)


#: target → its platform catalog. ⚠ **ONE LOOKUP** — `BR-MET-096` rules one
#: workflow for every target, so a new target is a line here and never a
#: branch in extract, transform or validate. CR-028 exercises the ruling as
#: written: the three assets targets are three entries.
# ═══════════════════════════════════════════════════════════════════════════
# THE ACCOUNTS CATALOG (CR-030 W1 — EP-CUS-07)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THIS TUPLE'S ABSENCE WAS A MONEY BUG, AND IT IS WHY IT EXISTS.** With no
# entry in `PLATFORM_CATALOG` a target gets NO rules — so stage 2's parse
# problems were carried on the row, `values_parse` was never evaluated, and a
# negative opening balance came through as **clean, with the value silently
# dropped to NULL**: the account loaded, its buckets were short, and its cached
# balance was wrong by the amount nobody saw. Found by CR-030 W1's own OQ-065
# case, which expected a refusal and got a successful load.
ACCOUNTS_RULES: tuple[DeclaredRule, ...] = (
    # ── CR-046 C4 — THE ACCOUNT'S OWN IDENTIFIER ────────────────────────────
    # The accounts target had NO rule about `account_no` at all: the column was
    # offered, whatever the file said was written, and a blank fell through to
    # the series. Under the PO ruling of 2026-08-27 the series is the ONLY
    # path, which needs the same three-piece shape every other target now has.
    DeclaredRule(
        code="ACC.NUMBER_UNIQUE",
        target="accounts",
        tier=TIER_STRUCTURAL,
        # `ux_accounts_no` arriving early — in-file only.
        sentence="An account number can only be used once.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="account_no_unique",
    ),
    DeclaredRule(
        code="ACC.NUMBER_ON_FILE",
        target="accounts",
        tier=TIER_PLATFORM,
        # ⚠ **UNCHANGED BY THE REVERSAL, AND WORTH SAYING WHY.** Where the
        # number comes FROM moved; what a number ALREADY ON FILE means did
        # not. It is still the match key and the write mode still decides —
        # *Insert new only* rejects, *Insert & update* updates the details.
        # ⚠ **AND AN UPDATE NEVER CHANGES IT** (`IMPORT_UPDATE_FIELDS` omits
        # `account_no`): it is the key we matched on, and a re-run that
        # rewrote it would make the NEXT re-run match nothing.
        sentence="This row names an account already on file.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="account_no_on_file",
    ),
    DeclaredRule(
        code="ACC.NUMBER_REQUIRED",
        target="accounts",
        tier=TIER_STRUCTURAL,
        # ⛔⛔ **THIS ROW REPLACED `ACC.NUMBER_NOT_ON_FILE`, WHICH SAID THE
        # OPPOSITE AND LIVED FOR ELEVEN HOURS (PO ruling 2026-08-27).**
        #
        # It read *"An account number is issued by your numbering settings —
        # leave this column blank for a new one"*. The PO reversed that for
        # this target alone: *"we use utility provdied account number here - we
        # dont create our own number - since it will create lot of change
        # management for utility ; if row dont have account number reject it"*.
        #
        # ⚠ **THE OLD SENTENCE IS QUOTED RATHER THAN DELETED**, because the
        # other three targets DO say exactly that and a lane harmonising the
        # four would rebuild what the reversal removed. The principle under
        # both rulings is one principle — **the side that owns the identifier
        # issues it** — and a customer owns their account number.
        #
        # STRUCTURAL, not platform: a row with no account number cannot be
        # created at all, and there is nothing to fall back to.
        sentence="Every account needs the number your utility already uses for it.",
        severity=ERROR,
        action=REJECT_ROW,
        # ⚠ **ITS OWN KIND, NOT THE GENERIC `required_field`.** That evaluator's
        # fix hint reads *"Your utility requires … on every premises"* — it is
        # tier 3's shipped kind for a TENANT'S own rule about premises, and on
        # this row it would answer a question about an account by naming a
        # premises. The sentence is the whole point of this rule.
        rule_kind="account_no_required",
    ),
    # ═══════════════════════════════════════════════════════════════════
    # CR-058 W7 · BR-CUS-1041 — TWO REASONS A ROW CREATES NOTHING
    # ═══════════════════════════════════════════════════════════════════
    #
    # ⛔ **PO RULING 2026-09-01:** *"Without identifier we cannot create Customer
    # ID or master account ot regular account"*.
    #
    # ⚠ **ERROR + REJECT_ROW, WHERE THE PREMISES TWINS ARE WARNINGS, AND THE
    # DIFFERENCE IS NOT SEVERITY TASTE.** On the premises import the ADDRESS
    # still loads and only the owner's account is skipped, so a flag is the
    # honest answer. Here **nothing loads at all** — no account, no customer —
    # and a warning would let the rehearsal print *"will create 1,213"* over
    # rows the commit refuses. That is `DEF-965`'s complaint and `DEF-544`'s
    # law: a load that resolves against a different world than stage 3 showed is
    # a defect in its own right.
    #
    # ⚠ **TWO RULES AND NOT ONE, because the next action is different each
    # time** — `DEF-771` clause 3. *Find an identifier* is a filing-cabinet job;
    # *say whether this is a person or a company* is a dropdown. One merged
    # sentence would tell an operator that N rows need attention and nothing
    # about what kind.
    #
    # ⚠ **NEITHER FIRES ON A ROW WHOSE ACCOUNT IS ALREADY ON FILE.** An
    # *Insert & update* re-run creates no account and no customer, so requiring
    # identity there would refuse the corrected re-run of a file that loaded
    # lawfully yesterday. The rule is about MINTING, exactly as `BR-CUS-1023` is.
    DeclaredRule(
        code="ACC.CUSTOMER_IDENTITY_REQUIRED",
        target="accounts",
        tier=TIER_PLATFORM,
        sentence=(
            "Every new account says who its customer is — a name and one way "
            "to identify them."
        ),
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="account_customer_identity_required",
    ),
    DeclaredRule(
        code="ACC.CUSTOMER_IDENTITY_MISMATCH",
        target="accounts",
        tier=TIER_PLATFORM,
        # ⚠ **`BR-CUS-1022` — WHICH IDENTIFIER COUNTS DEPENDS ON THE KIND.** A
        # person is known by a Social Security number, a driving licence or a
        # phone; a company by its Tax ID. An identifier under an unstated kind
        # cannot be judged at all, and one belonging to the OTHER kind is filed
        # where that kind's matcher will never look.
        sentence=(
            "A customer's identifier matches the kind of customer the row says "
            "they are."
        ),
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="account_customer_identity_mismatch",
    ),
    DeclaredRule(
        code="ACC.EXTERNAL_REF_UNIQUE",
        target="accounts",
        tier=TIER_STRUCTURAL,
        # CR-046 C5 / BR-CUS-172 — `uq_accounts_tenant_external_ref_ci`
        # arriving early. In-file only, same reason as the other three.
        sentence="A row's external reference can only be used once in a file.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="external_ref_unique",
    ),
    # ── TIER 1 · STRUCTURAL ────────────────────────────────────────────────
    # ⚠ NO `ACC.UNIT_MAPPED` RULE, AND THAT IS DELIBERATE. `unit_ref` is
    # `required=True` in the column map, and stage 2 already REFUSES a file that
    # leaves a required column unmapped — the premises precedent, whose own
    # docstring gives the reason: a file with no such column cannot produce a
    # single loadable row, so walking it to stage 3 to reject all 431 rows one
    # at a time tells the operator the wrong thing about what is wrong.
    DeclaredRule(
        code="ACC.VALUES_PARSE",
        target="accounts",
        tier=TIER_STRUCTURAL,
        # ⚠ AMENDED 2026-08-24 (DEF-620) — THIS COMMENT DESCRIBED A REFUSAL
        # THAT NO LONGER HAPPENS AND SHOULD NEVER HAVE. It read: *"a NEGATIVE
        # [bucket] is not a typo: it is a legacy CREDIT balance, and OQ-065 asks
        # what we do with those. Stage 2 refuses it."* OQ-065 CLOSED on
        # 2026-08-08 → BR-CUS-061: credits import as a carried ACCOUNT CREDIT
        # and the aging buckets stay debit-only. A negative `ob_*` cell now
        # travels; `customers.import_writer.opening_position` splits it.
        #
        # What this rule still does, and why it must stay ERROR/reject_row: it
        # turns a cell that CANNOT be read as money at all — `abc`, a stray
        # currency symbol — into a rejected row with a row number, instead of a
        # value that quietly becomes NULL. That is DEF-614, and it cost a
        # silent money bug before this rule existed.
        sentence="Every value has to be the kind of value its column holds.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="values_parse",
    ),
    # ── TIER 2 · PLATFORM ──────────────────────────────────────────────────
    DeclaredRule(
        code="ACC.UNIT_ON_FILE",
        target="accounts",
        tier=TIER_PLATFORM,
        # BR-CUS-047 — the migration order is Premises → Units + Plans →
        # Assets → ACCOUNTS → opening reads. An account import creates no unit:
        # auto-creating one would invent the premise half of a utility's estate
        # from a billing spreadsheet.
        sentence="The unit this account names is already on file.",
        severity=ERROR,
        action=REJECT_ROW,
        # The evaluator the assets targets already use for the same question —
        # one resolver, so an accounts row and a meter row agree about what
        # "on file" means (DEF-544's lesson).
        rule_kind="unit_ref_on_file",
    ),
    # ⛔ DEF-618 — the four `KIND_LOOKUP` columns, each declaring what a miss
    # MEANS. Without these the value-map step resolves what it can and says
    # nothing about what it could not, and an unmapped type reached stage 4.
    DeclaredRule(
        code="ACC.TYPE_IN_LOOKUP",
        target="accounts",
        tier=TIER_PLATFORM,
        sentence="The account type is one of the types on file.",
        # ⚠ ERROR, where the assets equivalents are WARNING. The difference is
        # not severity taste: `account_type` is required and the account
        # cannot be opened without it, so a flagged row would be a row the
        # load is guaranteed to fail on.
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="account_type_in_lookup",
    ),
    DeclaredRule(
        code="ACC.STATUS_IN_LOOKUP",
        target="accounts",
        tier=TIER_PLATFORM,
        sentence="The account status is one of the statuses on file.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="status_in_lookup",
    ),
    DeclaredRule(
        code="ACC.SUBTYPE_IN_LOOKUP",
        target="accounts",
        tier=TIER_PLATFORM,
        sentence="The account sub-type is one of the sub-types on file.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="account_subtype_in_lookup",
    ),
    DeclaredRule(
        code="ACC.LANGUAGE_IN_LOOKUP",
        target="accounts",
        tier=TIER_PLATFORM,
        sentence="The preferred language is one of the languages on file.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="preferred_language_in_lookup",
    ),
    # ⛔⛔ **CR-047 · DEF-2519 — THE TWO REFUSALS THE REHEARSAL COULD NOT SEE.**
    #
    # `BR-CUS-051` promises *"staged → per-row errors → skip-errors ON → 'N
    # created · N failed' summary"*, and stage 3 delivered the first half for
    # everything it could check BEFORE the write. These two are checked INSIDE
    # `customers._make_occupying`, so the only place they surfaced was a
    # refusal escaping the row loop — a 1,213-row migration where row 63 names
    # an occupied unit left ZERO accounts on file.
    #
    # ⚠ **THEY ARE THE SAME TWO REFUSALS, MOVED EARLIER — NOT A SECOND COPY OF
    # THE RULE.** The writer still enforces both (that is `_make_occupying`'s
    # job and hard rule 4's protection), and CR-047's per-row savepoint is what
    # catches the ones stage 3 cannot see: a row whose unit is taken by a
    # SIBLING ROW OF THE SAME FILE, or by an account somebody opened between
    # the rehearsal and the commit. What these rules buy is the STAGE at which
    # an operator learns — beside every other rejection, with the row number,
    # before they click Load — which is exactly what `account_lookup_indexes`'
    # own docstring argues for the four lookup columns.
    DeclaredRule(
        code="ACC.UNIT_NOT_OCCUPIED",
        target="accounts",
        tier=TIER_PLATFORM,
        # BR-CUS-017 — one live account per unit, ever. The sentence states
        # what has to be TRUE (the house style of every rule above: *"The unit
        # this account names is already on file"*), never what went wrong; the
        # hit's own `problem` says that, and names the account in the way.
        sentence="The unit this account names is free.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="unit_not_occupied",
    ),
    DeclaredRule(
        code="ACC.START_DATE_REQUIRED",
        target="accounts",
        tier=TIER_STRUCTURAL,
        # BR-CUS-022 — the first bill starts from `opened_at`, so an account
        # being ACTIVATED without one could never be billed.
        #
        # ⚠ **STRUCTURAL, LIKE `ACC.NUMBER_REQUIRED` AND FOR ITS REASON.** A
        # tenant switching this off would not load those rows; it would move
        # their refusal from a rehearsal into the writer, which is the whole
        # defect. There is nothing to fall back to — a defaulted start date is
        # a date nobody chose, on the column the first bill is computed from.
        sentence="An account you are activating has the date its service started.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="start_date_required",
    ),
    DeclaredRule(
        code="ACC.OPENED_NOT_FUTURE",
        target="accounts",
        tier=TIER_STRUCTURAL,
        # PO 2026-10-17 (`DEF-CUS-10180`, decision log *"ACCOUNT AGE ON THE
        # ACCOUNTS LIST"* rule 7): *"Imported account → the Opened date carried
        # from the old system (optional import column; future/unreadable refused
        # per row)"*. An unreadable date is `ACC.VALUES_PARSE`'s row already;
        # this is the other half. A future Opened date is an age below zero on
        # the Accounts list and a first bill counted from a day not yet come.
        #
        # STRUCTURAL for `ACC.START_DATE_REQUIRED`'s reason: there is nothing
        # to fall back to, and a tenant switching it off would only move the
        # refusal somewhere a clerk cannot see it.
        sentence="An Opened date is not in the future.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="opened_not_in_future",
    ),
)


# ═══════════════════════════════════════════════════════════════════════════
# THE PLATFORM CATALOG — parts (CR-077)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **A TARGET WITH NO RULE SET IS NOT NEUTRAL — IT IS A REHEARSAL THAT
# PROMISES MORE THAN IT DELIVERS.** `resolve()` answers `()` for a target the
# catalogue does not name, so stage 3 would find nothing wrong with any file and
# every genuinely bad row would be discovered at the WRITE, landing in
# `rejected_at_write`. The loaders' own comment says what that means: *"a run
# where this is not zero is a run whose rehearsal did not see everything"*. So
# the register's five refusals are declared here, judged before anything is
# written, and the writer stays the backstop rather than the first line.
#
# ⚠ **EVERY ONE OF THEM IS `work.services._clean_part`'s, ASKED RATHER THAN
# RESTATED.** The uniqueness of a part number is `uq_parts_tenant_part_no_ci`;
# the category list is the tenant's own, read through the seam. Nothing here
# invents a constraint work does not have — that is how a rehearsal and a
# commit come apart.

PARTS_RULES: tuple[DeclaredRule, ...] = (
    # ── TIER 1 · STRUCTURAL ────────────────────────────────────────────────
    DeclaredRule(
        code="PRT.PART_NO_REQUIRED",
        target="parts",
        tier=TIER_STRUCTURAL,
        # ⚠ **AND WE DO NOT INVENT ONE, WHICH IS THE OPPOSITE OF PREMISES,
        # UNITS AND METERS.** Those three take their number from the tenant's
        # own series; there is no `part` series in `core.numbering` and
        # `Work-025` has never issued one, so a part number is the utility's
        # and a blank cell has no answer. The sentence has to say so, or an
        # operator who has just loaded meters will wait for a number that is
        # never coming.
        sentence="Every part needs a part number.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="part_no_required",
    ),
    # ⚠ **CR-168 ruling 32 (PO 2026-09-24): *"add name to the part add
    # form"* — the part has a NAME; it was the same field called Description.**
    # Both rules also carry their OWN fix sentence (`DEF-WRK-9588`): the
    # generic `required_field` hint is tier 3's premises sentence and told a
    # parts row *"Your utility requires unit on every premises."* (image 42).
    DeclaredRule(
        code="PRT.NAME_REQUIRED",
        target="parts",
        tier=TIER_STRUCTURAL,
        sentence="Every part needs a name.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="required_field",
        params={"field": "name", "label": "name", "fix_hint": "Add the part's name."},
    ),
    DeclaredRule(
        code="PRT.UNIT_REQUIRED",
        target="parts",
        tier=TIER_STRUCTURAL,
        sentence="Every part is counted in something — each, metre, box.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="required_field",
        params={
            "field": "unit_of_measure",
            "label": "unit",
            "fix_hint": "Add how it is counted — each, ft, roll.",
        },
    ),
    DeclaredRule(
        code="PRT.VALUES_PARSE",
        target="parts",
        tier=TIER_STRUCTURAL,
        sentence="Every value has to be the kind of value its column holds.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="values_parse",
    ),
    DeclaredRule(
        code="PRT.PART_NO_UNIQUE",
        target="parts",
        tier=TIER_STRUCTURAL,
        # The IN-FILE half. `uq_parts_tenant_part_no_ci` arriving early — two
        # rows of one file claiming the same part number are two rows claiming
        # to be the same part, whatever the write mode is.
        sentence="One part number cannot appear twice in the same file.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="part_no_unique",
    ),
    # ── TIER 2 · PLATFORM ──────────────────────────────────────────────────
    DeclaredRule(
        code="PRT.NUMBER_ON_FILE",
        target="parts",
        tier=TIER_PLATFORM,
        # ⛔ **THE SEVERITY IS THE RUN'S WRITE MODE'S** — `_for_write_mode`
        # rewrites this one rule from the mode chosen at stage 1, exactly as it
        # does for every other target's *already on file* rule. In *Insert new
        # only* it REJECTS; in *Insert & update* it is the row the mode exists
        # for. One code, because a receipt, a tenant override and a rule table
        # all address it by code.
        sentence="This row names a part already on file.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="part_no_on_file",
    ),
    DeclaredRule(
        code="PRT.CATEGORY_IN_LOOKUP",
        target="parts",
        tier=TIER_PLATFORM,
        # ⚠ **A BLANK CATEGORY IS LAWFUL AND IS NOT A HIT.** `_clean_part`
        # writes `category = None` for an empty cell and the register shows the
        # part as uncategorised, so firing on a blank would reject rows the load
        # would have written.
        sentence="A category has to be one already on your parts register.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="category_in_lookup",
    ),
)


# ═══════════════════════════════════════════════════════════════════════════
# THE PAYMENTS CATALOG (`P1.1` — a lockbox or store file)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **THIS TUPLE'S ABSENCE WOULD BE A MONEY BUG AND THE ACCOUNTS TARGET
# ALREADY PROVED IT.** `PLATFORM_CATALOG.get(target, ())` gives a target with
# no entry **NO RULES AT ALL** — so stage 2's parse problems ride on the row,
# `values_parse` is never evaluated, and the rehearsal shows a clean file. On
# the accounts target that silently dropped a negative opening balance; here it
# would show an operator four hundred green rows and then reject most of them
# at the write, after they had pressed commit on a morning's takings.
#
# ⚠ **THE LAST TWO RULES ARE WHERE `P1.12` LIVES**, and the pair is the point:
# `PAY.ACCOUNT_ON_FILE` REJECTS a row naming an account we do not have, and
# `PAY.NAME_ONLY_MATCH` HOLDS a row we could only guess at (it FLAGGED until
# `DEF-PAY-10756`, and so counted in *will create* for a row the writer
# refuses). Neither posts
# money. The difference between them is what a person can do next — one is a
# wrong number to correct, the other is a judgement to make — and collapsing
# them into one severity would either reject money a clerk could have placed or
# post money on the strength of a name.
PAYMENTS_RULES: tuple[DeclaredRule, ...] = (
    # ── TIER 1 · STRUCTURAL ────────────────────────────────────────────────
    DeclaredRule(
        code="PAY.AMOUNT_REQUIRED",
        target="payments",
        tier=TIER_STRUCTURAL,
        sentence="Every payment needs an amount.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="required_field",
        # `DEF-PAY-10758` (L3-03) — the shared default fix sentence is the
        # premises one (*"Your utility requires amount on every premises"*),
        # which on a payments file is false and reads as nonsense.
        params={
            "field": "amount",
            "label": "amount",
            "fix_hint": "Add the amount paid. Or take the row out.",
        },
    ),
    DeclaredRule(
        code="PAY.VALUES_PARSE",
        target="payments",
        tier=TIER_STRUCTURAL,
        sentence="Every value has to be the kind of value its column holds.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="values_parse",
    ),
    DeclaredRule(
        code="PAY.PAYER_NAMED",
        target="payments",
        tier=TIER_STRUCTURAL,
        # ⚠ **THE WHOLE ROW, NOT ONE COLUMN** — which is why this is not
        # `required_field`. A row naming an account is fine with no payer, and
        # a row naming a payer is workable with no account. A row naming
        # NEITHER is money with nowhere to go.
        sentence="Every payment names an account or a payer.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="payment_row_identified",
    ),
    # ── TIER 2 · PLATFORM ──────────────────────────────────────────────────
    DeclaredRule(
        code="PAY.ACCOUNT_ON_FILE",
        target="payments",
        tier=TIER_PLATFORM,
        # ⚠ **NOT A WARNING.** The writer refuses this row, so flagging it
        # would let an operator press commit expecting it to load — the shape
        # `DEF-544` names: a rehearsal that judges against a different world
        # than the write.
        sentence="An account number has to be one you already have.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="payment_account_on_file",
    ),
    DeclaredRule(
        code="PAY.NAME_ONLY_MATCH",
        target="payments",
        tier=TIER_PLATFORM,
        # ⛔ **`P1.12` / CS-2 RULE 2, AS A RULE AN OPERATOR CAN SEE.** *A
        # name-and-amount guess never commits on its own.* A name is not an
        # identifier; posting to the wrong customer breaks two accounts
        # silently and can only be undone by a reversal on one and a new
        # payment on the other.
        sentence="A payer's name is a suggestion, never a match.",
        # ⛔ **HELD, NOT FLAGGED — `DEF-PAY-10756` (L2-08, PO 2026-10-30 "Rest
        # we will fix").** As a WARNING the row counted in the dry run's *will
        # create* and was then refused by the writer, so the tester's file read
        # *"will create 5"* and loaded 4 with one row explained nowhere. The
        # writer's refusal is the rule; the rehearsal now says the same thing.
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="payment_name_only_match",
    ),
    # ── `DEF-PAY-10757` (L2-09, PO 2026-10-30: *"closed account held,
    # disconnect warned, future-dated payment row refused"*) ────────────────
    DeclaredRule(
        code="PAY.ACCOUNT_NOT_CLOSED",
        target="payments",
        tier=TIER_PLATFORM,
        sentence="A closed account takes no payment.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="payment_account_not_closed",
    ),
    DeclaredRule(
        code="PAY.ACCOUNT_IN_DISCONNECT",
        target="payments",
        tier=TIER_PLATFORM,
        sentence="An account in a disconnect is checked.",
        severity=WARNING,
        action=FLAG_ONLY,
        rule_kind="payment_account_in_disconnect",
    ),
    DeclaredRule(
        code="PAY.DATE_NOT_FUTURE",
        target="payments",
        tier=TIER_STRUCTURAL,
        sentence="A payment is never dated ahead.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="payment_date_not_future",
    ),
    # ── `DEF-PAY-10697` (lockbox audit LBX-08, PO 2026-10-30 *"LBX-08 need
    # fix"*: an in-file duplicate cheque is flagged and HELD) ───────────────
    # ⚠ **THE CHEQUE IS ACCOUNT · AMOUNT · REFERENCE, NEVER THE REFERENCE
    # ALONE** — two customers can both send cheque 1042. Both rules HOLD the
    # row (an error, the row is not written): one cheque posted twice is real
    # money credited twice, undone only by a reversal.
    DeclaredRule(
        code="PAY.CHEQUE_ONCE_IN_FILE",
        target="payments",
        tier=TIER_PLATFORM,
        sentence="A payment reference appears once.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="payment_cheque_once_in_file",
    ),
    DeclaredRule(
        code="PAY.CHEQUE_NOT_ALREADY_RECORDED",
        target="payments",
        tier=TIER_PLATFORM,
        sentence="A recorded payment is not recorded again.",
        severity=ERROR,
        action=REJECT_ROW,
        rule_kind="payment_cheque_not_already_recorded",
    ),
)


PLATFORM_CATALOG: dict[str, tuple[DeclaredRule, ...]] = {
    "accounts": ACCOUNTS_RULES,
    "premises": PREMISES_RULES,
    "units": UNITS_RULES,
    "assets_meters": ASSETS_METERS_RULES,
    "assets_submeters": ASSETS_SUBMETERS_RULES,
    "assets_devices": ASSETS_DEVICES_RULES,
    "parts": PARTS_RULES,
    "payments": PAYMENTS_RULES,
}


# ═══════════════════════════════════════════════════════════════════════════
# RESOLUTION — catalog + this tenant's own rows
# ═══════════════════════════════════════════════════════════════════════════


#: ⛔ **CR-046 C1 — `AST.NUMBER_ON_FILE` PER WRITE MODE (PO 2026-08-27).**
#:
#: PO verbatim: *"Does this row name a meter already on file? if yes - ( in
#: case of insert - reject it | in case of Insert & Update = update the
#: details)"*.
#:
#: The rule keeps ONE CODE — a tenant override, a rule table and a receipt all
#: address it by code, and splitting it in two would make the same fact
#: addressable two ways depending on a mode the reader cannot see. What varies
#: is the severity, the action and the sentence.
#:
#: ⚠ **THE GENERIC SENTENCE RETIRES.** *"…the write mode decides what happens
#: to it"* was honest while nothing here knew the mode; now that it does, a
#: sentence that declines to say which outcome applies is simply withholding
#: the answer.
_NUMBER_ON_FILE_BY_MODE: dict[str, tuple[str, str, str]] = {
    # mode → (severity, action, sentence tail after "This row names a {noun}
    #         already on file"), `{noun}` filled by the caller.
    "insert": (
        ERROR,
        REJECT_ROW,
        "and Insert new only writes new records — this row is rejected.",
    ),
    "upsert": (
        WARNING,
        FLAG_ONLY,
        "and Insert & update will update its details.",
    ),
}


#: ⛔ **CR-046 C2/C3/C4 — THE *ON FILE* RULE KIND ON ALL FOUR TARGETS.**
#: Wave C1 built this mechanism for `asset_no_on_file` alone. The PO widened
#: the ruling to premises, units and accounts in the same change request, and
#: the mode-dependent half is identical on every one of them — so this is a
#: MEMBERSHIP TEST rather than four copies of `_for_write_mode`.
#:
#: ⚠ **A KIND ADDED HERE MUST DECLARE A SENTENCE `_for_write_mode` CAN SPLIT**
#: — the head is everything before the first `.` or ` — `, and the per-mode
#: tail is appended to it. A declaration whose first sentence already states an
#: outcome would read as two contradictory outcomes in one line.
NUMBER_ON_FILE_KINDS: frozenset[str] = frozenset(
    {
        "asset_no_on_file",
        "premise_no_on_file",
        "unit_no_on_file",
        # ⛔ **THE UNITS TARGET HAS TWO ENTRIES HERE AND ONLY ONE OF THEM IS A
        # NUMBER.** The PO ruled the unit's identity is `premises + label`
        # (2026-08-27), so the row a run is ABOUT can be named two ways — by
        # quoting the number we issued, or by the pair. Both are *"this row
        # names a record already on file"*, so both take the mode-dependent
        # outcome; a pair match that stayed a warning under `insert` would let
        # the loader reject a row the rehearsal called clean.
        "unit_pair_on_file",
        "account_no_on_file",
        # CR-077 — the parts target's identity match. Same reasoning as every
        # other entry: the mode chosen at stage 1 decides whether a row naming
        # a part already on file is the row *Insert & update* exists for or a
        # row *Insert new only* rejects.
        "part_no_on_file",
    }
)


def _for_write_mode(catalog: tuple[DeclaredRule, ...], write_mode: Any) -> tuple[DeclaredRule, ...]:
    """Re-declare the target's *number already on file* rule for the run's
    mode. Everything else is returned untouched, and an unknown or absent mode
    returns the catalog exactly as declared — see `World.write_mode` for why
    that has to be safe."""
    variant = _NUMBER_ON_FILE_BY_MODE.get(str(write_mode or "").strip())
    if variant is None:
        return catalog
    severity, action, tail = variant
    out: list[DeclaredRule] = []
    for rule in catalog:
        if rule.rule_kind not in NUMBER_ON_FILE_KINDS:
            out.append(rule)
            continue
        # The noun is recoverable from the rule the target declared, so the
        # per-mode sentence does not have to know the target's vocabulary.
        head = rule.sentence.split(" — ", 1)[0].split(".", 1)[0]
        out.append(
            DeclaredRule(
                code=rule.code,
                target=rule.target,
                tier=rule.tier,
                sentence=f"{head} {tail}",
                severity=severity,
                action=action,
                rule_kind=rule.rule_kind,
            )
        )
    return tuple(out)


def resolve(target: str, tenant_id: Any, write_mode: Any = None) -> list[DeclaredRule]:
    """The rule set AS IT IS NOW, for this tenant, in evaluation order.

    ⚠ **`write_mode` IS THE RUN'S OWN, AND IT CHANGES ONE RULE'S SEVERITY**
    (CR-046 wave B/C1). See `_for_write_mode` above. Absent → the catalog as
    declared, which is the pre-CR-046 behaviour and the only safe default.

    Tier 1 first (they stop the row), then tier 2, then tier 3. A tenant row
    whose `code` matches a PLATFORM rule is an override of its severity and
    action; a tenant row whose code matches nothing is one of their own.

    ⚠ **A TIER-1 CODE IS NEVER OVERRIDDEN.** If a row ever appears in
    `import_rules` carrying a structural code — through a future config
    endpoint, a fixture or a hand-written INSERT — it is IGNORED here rather
    than applied, because the alternative is a screen reporting that a rule the
    database enforces has been switched off.
    """
    catalog = _for_write_mode(PLATFORM_CATALOG.get(target, ()), write_mode)
    structural_codes = {rule.code for rule in catalog if rule.tier == TIER_STRUCTURAL}
    overrides: dict[str, models.ImportRule] = {}
    tenant_rules: list[models.ImportRule] = []
    rows = models.ImportRule.objects.filter(tenant_id=tenant_id, target=target, active=True)
    for row in rows:
        if row.code in structural_codes:
            continue  # tier 1 is not configurable — see the docstring
        if any(row.code == rule.code for rule in catalog):
            overrides[row.code] = row
        else:
            tenant_rules.append(row)

    resolved: list[DeclaredRule] = []
    for rule in catalog:
        override = overrides.get(rule.code)
        if override is None:
            resolved.append(rule)
            continue
        resolved.append(
            DeclaredRule(
                code=rule.code,
                target=rule.target,
                tier=rule.tier,
                sentence=override.sentence or rule.sentence,
                severity=override.severity or rule.severity,
                action=override.action or rule.action,
                action_value=override.action_value,
                rule_kind=rule.rule_kind,
                params=override.params or {},
                available=rule.available,
                unavailable_reason=rule.unavailable_reason,
            )
        )
    for row in tenant_rules:
        resolved.append(_tenant_rule(row))
    resolved.sort(key=lambda rule: (rule.tier, rule.code))
    return resolved


def _tenant_rule(row: models.ImportRule) -> DeclaredRule:
    """One tier-3 row, and BR-MET-091 applied to the tenant's own half.

    A utility can only express a rule this module has an EVALUATOR for. One it
    does not is reported `available: false` with that reason — never dropped,
    because a rule the utility authored and cannot see on the receipt is a rule
    they believe is protecting them.
    """
    kind = (row.rule_kind or "").strip()
    known = kind in EVALUATORS
    return DeclaredRule(
        code=row.code,
        target=row.target,
        tier=TIER_TENANT,
        sentence=row.sentence or row.code,
        severity=row.severity or WARNING,
        action=row.action or FLAG_ONLY,
        action_value=row.action_value,
        rule_kind=kind,
        params=row.params or {},
        available=known,
        unavailable_reason=(
            None
            if known
            else (
                "This rule asks for a check this product cannot make yet, so "
                "nothing on this run was measured against it."
            )
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE EVALUATORS
# ═══════════════════════════════════════════════════════════════════════════
#
# Each takes the mapped rows and the WORLD they are judged against, and returns
# the rows it fired on. None of them writes anything, and none of them may:
# stage 3's whole promise is that it is a rehearsal (B15 §4, TC-1).


@dataclass
class World:
    """What stage 3 needs to know about the tenant, read ONCE for the run.

    Read once rather than per row because DEF-324 measured the cost of the
    other shape: `enabled_service_codes()` on the hot path of every premises
    write spent 47 of 118 profiled seconds answering one question 304 times.
    A 431-row migration would ask each of these questions 431 times.
    """

    enabled_services: set[str]
    premises_type_codes: set[str]
    area_names: set[str]
    existing_premise_nos: set[str]
    existing_addresses: set[str]
    #: ── the units target's half (`BR-MET-096`) ────────────────────────────
    #: ⚠ **`DEF-771` — WAS `plan_codes: set[str]`, AND THE SHAPE WAS THE
    #: DEFECT.** A set of codes can answer only *"is this token a code we
    #: publish"*, so a file whose `Plan` column held plan NAMES — the column is
    #: LABELLED *Plan* and accepts `plan`, `rate plan`, `tariff` — mapped clean
    #: and loaded 9,881 units unplanned. This is `rating.assignable_plan_index`
    #: whole: lowered token (CODE **or** NAME) → `{plan_id, outcome, plan,
    #: collisions, matched_on}`, where only a `published` outcome carries an id
    #: (`BR-RAT-030`) and the other three say WHY. Read once for the same
    #: reason as the rest.
    plan_index: dict[str, Any] = field(default_factory=dict)
    #: `(premise_no lowered, unit label lowered)` already on file, so a label
    #: clashing with a unit the utility already has is caught as well as one
    #: clashing inside the file itself.
    existing_unit_keys: set[tuple[str, str]] = field(default_factory=set)
    #: Unit TYPE codes the tenant's reference list holds, lowered.
    unit_type_codes: set[str] = field(default_factory=set)
    #: ── CR-046 C3/C4 — the two remaining identifier indexes ───────────────
    #: `unit_no` already on file, LOWERED. Empty is a real state (a tenant
    #: whose units were all created before the `unit` series was seeded carry
    #: NULL), and it makes every quoted number an invented one — which is the
    #: correct answer, not a gap.
    existing_unit_nos: set[str] = field(default_factory=set)
    #: `account_no` already on file, LOWERED. ⚠ **READ THROUGH THE SEAM**
    #: (`seams.accounts_import_index`): `accounts` is customers' table and
    #: this module may not query it (B1/B2 §2). It is the SAME index the
    #: accounts loader matches with, so stage 3 and stage 4 cannot disagree
    #: about what is on file (`DEF-544`'s law).
    existing_account_nos: set[str] = field(default_factory=set)
    #: ⛔ **THE PAYMENTS TARGET'S WORLD (`P1.1`) — THE ACCOUNT INDEX AS
    #: PAYMENTS KEYS IT, READ THROUGH `seams.payments_import_index`.**
    #: `existing_account_nos` above cannot do this job: it is a SET of numbers,
    #: and the payments ladder needs the ENTRY — the id to post against and the
    #: legacy reference a payer name can equal. `DEF-771`'s lesson exactly
    #: (*"a set of codes can answer only is this token a code we publish"*),
    #: met before it cost anything this time.
    #:
    #: ⚠ **`None` AND `{}` ARE DIFFERENT AND THE RULES READ THE DIFFERENCE.**
    #: `None` is *payments cannot answer* and the rules report nothing rather
    #: than blessing four hundred rows; `{}` is a utility with no accounts,
    #: where every row correctly reports an account not on file.
    payments_account_index: dict[str, Any] | None = None
    #: `DEF-PAY-10697` (LBX-08) — payments' own read of which of a file's
    #: cheques it ALREADY has (`seams.payments_posted_cheques`), handed in as a
    #: CALLABLE so it is asked once, about this file's cheques only, and never
    #: about the tenant's whole payment history. `None` = payments cannot
    #: answer, and `PAY.CHEQUE_NOT_ALREADY_RECORDED` then reports nothing.
    payments_posted_cheques: Callable[..., Any] | None = None
    #: ⛔ **THE RUN'S WRITE MODE — CR-046 wave B, and it is a REVERSAL OF
    #: `DEF-543`'S STATED OBSTACLE.**
    #:
    #: `DEF-543` reasoned that an on-file match must WARN rather than block
    #: because *"stage 3 cannot know the write mode"*. That was true and is not
    #: any more: **`CR-042` moved the write-mode choice from stage 4 to stage
    #: 1**, and stage 3 runs after stage 1. The two changes were never read
    #: together, so the constraint outlived the thing that caused it.
    #:
    #: ⚠ **`None` IS A REAL VALUE AND MUST STAY SAFE.** A run extracted before
    #: this landed, or by a client that does not send the mode, has none — and
    #: an absent mode must never be spelled the same way as `insert`, because
    #: `insert` is the value that REJECTS rows. When it is None the on-file
    #: rule keeps its pre-CR-046 warning and the hard outcome still lands at
    #: the dry run and the load, where the mode is always known.
    write_mode: str | None = None
    #: ── the assets targets' half (CR-028 AST-W3 · BR-MET-096's posture:
    #: one world for every target, read unconditionally) ─────────────────────
    #: Today in the TENANT's calendar (BR-TEN-020) — the cert-due rule's clock.
    today: Any = None
    #: Lowered asset number → {id, asset_no, behavior_class, type_code,
    #: unit_id} — the assets registry, read once through the seam.
    asset_index: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Lowered unit reference (unit_no · "premise · label" · tenant-unique
    #: label) → unit id. THE SAME index the load resolves with — a stage 3
    #: that judged against a different resolver than stage 4 loads with is
    #: DEF-544's shape.
    unit_ref_index: dict[str, str] = field(default_factory=dict)
    #: (unit id, service code) → the active meter's number already seated
    #: there — r10's "already has an active electric meter" world.
    unit_service_taken: dict[tuple[str, str], str] = field(default_factory=dict)
    #: unit id → its premises id, for the sub-meter same-premises warning.
    unit_premises: dict[str, str] = field(default_factory=dict)
    #: Lowered premise_no → that premises' unit ids, for the devices target
    #: (premises exists · premises-level attach resolves to its ONE unit).
    premises_units: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: ── BR-MET-119 (CR-036 · DEF-772) — THE THIRD LINK OF THE CHAIN ───────
    #: premises id → `{"ref": what a clerk CALLS this address, "services": what
    #: it OFFERS}`. `services` is `None` when nobody has been asked, which is a
    #: DIFFERENT state from `[]` (DEF-756/762) and gets a different sentence.
    #: Read once for the same reason as everything above it (DEF-324).
    premises_offer: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: ── `DEF-935` — THE FOURTH LINK, AND IT IS THE ONE THAT KILLED A COMMIT ─
    #: service code → the unit THIS TENANT reads it in, `None` when they have
    #: declared none. `tenancy.selectors.service_default_uoms` states the case
    #: itself: *"Four of the ten catalog services — sewer, solar, thermal/heat,
    #: battery — have no design-stated default, so a tenant that enables one
    #: carries a NULL."* A meter for one of those passes every rule in this
    #: catalogue and is then refused INSIDE the load (`assets.uom_required`),
    #: which takes the whole all-or-nothing transaction with it. Read once,
    #: like everything above.
    service_units: dict[str, Any] = field(default_factory=dict)
    #: ── PLAN U4 (PO ruling 2026-09-30) — WHICH SERVICE A SIZE AND A UNIT OF
    #: MEASURE BELONG TO ─────────────────────────────────────────────────────
    #: size code → its service code (`None` = untagged, lawful everywhere), and
    #: UoM code → its service code (`None` = all services). Read ONCE through
    #: `seams.asset_upload_scopes` (DEF-324), so `AST.SIZE_FOR_SERVICE` and
    #: `AST.UOM_FOR_SERVICE` judge the rule `service_scope_filter` states.
    size_service: dict[str, Any] = field(default_factory=dict)
    uom_service: dict[str, Any] = field(default_factory=dict)
    #: ── DEF-1088 · BR-MET-402 — THE TENANT'S TYPED OWNERS, READ ONCE ───────
    #: Two indexes over the same rows because the two questions are different
    #: and only one of them may resolve:
    #:   · `owner_exact`  lowered NAME → owner id. This is the DATABASE's own
    #:     `uq_premises_owners_tenant_name_ci` key, so a hit is a fact and the
    #:     load REUSES the party — the PO's *"it can be existing master account
    #:     also"*.
    #:   · `owner_near`   normalised name → [{id, name}]. A hit here is a
    #:     QUESTION, not an answer: PO decision 3 is *"offer the match, clerk
    #:     decides"*, so the import may not pick one and rejects the row with
    #:     the candidate named.
    #: Read once, for DEF-324's measured reason like everything above.
    owner_exact: dict[str, str] = field(default_factory=dict)
    owner_near: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    #: ── CR-077 · the parts target's half — read unconditionally, like every
    #: other target's, because `BR-MET-096` forbids a world that depends on the
    #: target and DEF-935 is what an index that is silently empty costs. ─────
    #: Lowered `part_no` already on file. ⚠ **READ THROUGH THE SEAM** — `parts`
    #: is work's table and this module may not query it (`BR-WRK-002`, `G78`).
    #: It is the SAME index the parts loader matches with, so stage 3 and stage
    #: 4 cannot disagree about what is on file (`DEF-544`'s law).
    existing_part_nos: set[str] = field(default_factory=set)
    #: Lowered category NAME **and** CODE → the category's own name. Both,
    #: because `work.services._clean_part` resolves both ways, and a stage 3
    #: that knew only one of them would reject rows the load would have written
    #: — the exact mirror of the defect a rehearsal exists to prevent.
    part_categories: dict[str, str] = field(default_factory=dict)
    #: ── CR-047 · BR-CUS-017 + BR-CUS-022 — THE TWO FACTS STAGE 3 NEEDED AND
    #: DID NOT HAVE, AND THEIR ABSENCE WAS `DEF-2519` (critical) ─────────────
    #: Both are read ONCE for the run, through the customers seam (B1/B2 §2),
    #: for DEF-324's measured reason like everything above.
    #:
    #: `occupied_unit_ids` — the unit ids that already hold a LIVE account,
    #: STRINGS, as `resolve_unit_ref` answers. It is
    #: `seams.accounts_for_units`, which keys off the behaviour CLASS
    #: (`OCCUPYING_BEHAVIOR_CLASSES`) and is the SAME reading
    #: `_refuse_if_unit_occupied` takes under the lock — so the rehearsal and
    #: the writer cannot disagree about what "occupied" means (DEF-544's law).
    occupied_unit_ids: frozenset[str] = frozenset()
    #: `occupying_status_codes` — which status codes TAKE a unit, LOWERED.
    #: ⚠ **`None` IS A REAL VALUE AND IT MEANS "NOBODY WAS ASKED".** Both rules
    #: below return no hits on it rather than guessing, because the alternative
    #: is a fabricated answer in the one direction that costs a migration: a
    #: `frozenset()` would say *no status occupies a unit* and silence them,
    #: an "everything occupies" reading would reject every draft row a utility
    #: legitimately loads onto a unit that is already live. See
    #: `seams.occupying_account_status_codes` for what its fallback can and
    #: cannot see.
    occupying_status_codes: frozenset[str] | None = None


def _rows_with(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return [row for row in rows if key in (row.get("problems") or {})]


def _hits_from_problem_key(rows: list[dict[str, Any]], key: str) -> list[RuleHit]:
    """Rows the TRANSFORM stage already found a problem on, under `key`.

    Stage 2 parses; stage 3 judges. A cell that would not parse is discovered
    while mapping and CARRIED — verbatim, with the original value — rather than
    coerced, which is `read_import.py`'s ratified posture: *"nothing here
    coerces a value to make it fit"*.
    """
    hits = []
    for row in rows:
        problem = (row.get("problems") or {}).get(key)
        if problem:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=problem.get("problem", ""),
                    fix_hint=problem.get("fix_hint"),
                )
            )
    return hits


def _eval_address_required(rows, world, rule) -> list[RuleHit]:
    hits = []
    for row in rows:
        if not (row.get("mapped") or {}).get("address_line"):
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem="This row has no street address.",
                    fix_hint="Add the address in the file, or skip empty rows at the mapping step.",
                )
            )
    return hits


def _eval_premise_no_unique(rows, world, rule) -> list[RuleHit]:
    """IN-FILE duplicates ONLY — the DB half moved to its own WARNING rule.

    ⚠ **THIS EVALUATOR USED TO REJECT EVERY ROW WHOSE ID WAS ALREADY ON FILE,
    WHICH MADE `Insert & update` A MODE THAT COULD NEVER UPDATE (`DEF-543`).**
    Stage 3 runs before the write mode is chosen, so a row matching an existing
    premises is not an error — it is precisely the row `upsert` exists for and
    the row `insert` skips. What IS an error whatever the mode is the same id
    twice in one file: the second row would silently win. The on-file case is
    now `PRM.PREMISE_NO_ON_FILE`, a WARNING that tells the operator what each
    mode will do with it.
    """
    hits = []
    seen: dict[str, int] = {}
    for row in rows:
        premise_no = (row.get("mapped") or {}).get("premise_no")
        if not premise_no:
            continue  # blank is legitimate — the series allocates one
        if premise_no in seen:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"Premise ID {premise_no} appears twice in this file.",
                    fix_hint=f"Row {seen[premise_no]} uses it as well. Keep one.",
                )
            )
        else:
            seen[premise_no] = row["row_no"]
    return hits


def _eval_premise_no_on_file(rows, world, rule) -> list[RuleHit]:
    """The on-file match. **SEVERITY IS THE RUN'S, NOT THIS FUNCTION'S** —
    `_for_write_mode` swaps it to ERROR/reject under *Insert new only*.

    ⛔ **THE FIX HINT SAID *"Insert new only will skip it unchanged"* UNTIL
    2026-08-27 AND THAT SENTENCE IS NOW FALSE (`CR-046` F2).** The PO chose the
    word: *"in case of insert - reject it"*. A skip reads as *"nothing needed
    doing"* — benign, no action — and a reject reads as *"this row did not
    load"*. Only one of them is true, and the difference is entirely in what
    the operator does next.

    ⚠ **AND THE HINT NAMES WHERE A NUMBER COMES FROM.** Under the same ruling
    the ONLY reason to fill this column in is to update a record already on
    file; an operator told merely *"this one exists"* would try a different
    number, which is the one thing the column no longer accepts.

    ⚠ *`replace` used to be the third case here and is WITHDRAWN* (CR-042 /
    OQ-580), refused by name at both entry points — so it is not described.
    """
    hits = []
    known = {str(value).strip().lower() for value in world.existing_premise_nos}
    for row in rows:
        premise_no = (row.get("mapped") or {}).get("premise_no")
        if premise_no and str(premise_no).strip().lower() in known:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"Premise ID {premise_no} is already on file.",
                    fix_hint=(
                        "Insert & update will update that premises; Insert new "
                        "only will REJECT this row, because a new premise ID "
                        "comes from Settings › Numbering › Premises. Leave the "
                        "column blank for a new address."
                    ),
                )
            )
    return hits


def _eval_premise_no_not_on_file(rows, world, rule) -> list[RuleHit]:
    """⛔ **CR-046 C2 — A PREMISE ID THIS SYSTEM NEVER ISSUED.**

    Blank passes and is the NORMAL case: the tenant's `premises` series
    allocates (BR-MET-403). A value that resolves passes too — it names a row,
    and `PRM.PREMISE_NO_ON_FILE` above judges it for the write mode. What is
    left is a number the operator INVENTED, which is precisely what the ruling
    of 2026-08-27 forbids.
    """
    hits = []
    known = {str(value).strip().lower() for value in world.existing_premise_nos}
    for row in rows:
        number = str((row.get("mapped") or {}).get("premise_no") or "").strip()
        if number and number.lower() not in known:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{number} is not a premise ID this utility has issued.",
                    fix_hint=(
                        "Clear this cell — the ID is allocated from Settings → "
                        "Numbering when the row is written. If this is your OLD "
                        "system's id, map that column to External reference."
                    ),
                )
            )
    return hits


def _eval_unit_no_unique(rows, world, rule) -> list[RuleHit]:
    """IN-FILE duplicates of a QUOTED unit number (`uq_units_tenant_unit_no`
    arriving early). A blank is skipped and is the normal case."""
    return _quoted_number_duplicates(rows, "unit_no")


def _eval_account_no_unique(rows, world, rule) -> list[RuleHit]:
    """IN-FILE duplicates of a QUOTED account number (`ux_accounts_no` arriving
    early). A blank is skipped and is the normal case."""
    return _quoted_number_duplicates(rows, "account_no")


def _quoted_number_duplicates(rows, field_name: str) -> list[RuleHit]:
    """The in-file half of every identifier rule, stated once.

    ⚠ **BLANK IS SKIPPED, AND SINCE 2026-08-27 THAT IS THE MAJORITY OF ROWS.**
    A file of 428 new premises carries 428 blank identifier cells; treating
    them as 427 duplicates of each other would reject the whole file. Only a
    QUOTED number can collide, because only a quoted number names anything.
    """
    hits: list[RuleHit] = []
    seen: dict[str, int] = {}
    for row in rows:
        number = str((row.get("mapped") or {}).get(field_name) or "").strip()
        if not number:
            continue
        key = number.lower()
        if key in seen:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{number} appears twice in this file.",
                    fix_hint=f"Row {seen[key]} uses it as well. Keep one.",
                )
            )
        else:
            seen[key] = row["row_no"]
    return hits


def _eval_unit_no_on_file(rows, world, rule) -> list[RuleHit]:
    """A quoted unit number that DOES resolve. **SEVERITY IS THE RUN'S, NOT
    THIS FUNCTION'S** — `_for_write_mode` swaps it to ERROR/reject under
    *Insert new only*, exactly as it does for the meters target."""
    return _quoted_number_on_file(
        rows, "unit_no", world.existing_unit_nos, noun="unit", on_file=True
    )


def _eval_unit_no_not_on_file(rows, world, rule) -> list[RuleHit]:
    """A quoted unit number that resolves to NOTHING — an invented one."""
    return _quoted_number_on_file(
        rows, "unit_no", world.existing_unit_nos, noun="unit", on_file=False
    )


def _eval_account_no_on_file(rows, world, rule) -> list[RuleHit]:
    """A quoted account number that DOES resolve. Severity is the run's."""
    return _quoted_number_on_file(
        rows, "account_no", world.existing_account_nos, noun="account", on_file=True
    )


def _eval_account_no_required(rows, world, rule) -> list[RuleHit]:
    """⛔ **A ROW WITH NO ACCOUNT NUMBER IS REJECTED — and this function
    REPLACED `_eval_account_no_not_on_file`, which said the opposite** (PO
    ruling 2026-08-27: *"if row dont have account number reject it"*).

    ⚠ **THE SENTENCE HAS TO EXPLAIN WHY WE WILL NOT INVENT ONE**, because the
    other three uploads DO invent one and an operator who has just loaded
    premises and units will reasonably expect this one to as well. The answer
    is that an account number is theirs, not ours.

    ⚠ **IT ALSO CLOSES A MEASURED DEFECT.** `BR-CUS-051`/`OQ-165`'s own worked
    case on `bbu-accounts-cutover.csv`: the 1,144 rows carrying explicit
    numbers all errored as duplicates *(working as intended)* while the **96
    blank-number rows quietly created 96 new accounts on units that already had
    one.* Those 96 rows are exactly what this rejects.
    """
    return [
        RuleHit(
            row_no=row["row_no"],
            problem="This row has no account number.",
            fix_hint=(
                "The account number is YOURS — the one already on the "
                "customer's bills and in your old system. SMART360 Next does "
                "not issue one here, because renumbering an account means "
                "writing to every customer."
            ),
        )
        for row in rows
        if not str((row.get("mapped") or {}).get("account_no") or "").strip()
    ]


# ═══════════════════════════════════════════════════════════════════════════
# CR-058 W7 · BR-CUS-1041 — the two evaluators, over ONE verdict
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **NEITHER DECIDES ANYTHING.** Both read `import_runs.account_identity_
# verdict`, which is the same function stage 4 asks before it creates and the
# same one the receipt counts — so what an operator is shown at stage 3 and what
# happens at stage 4 cannot disagree. `_owner_verdict_of` is its twin, one
# target along, and the reasoning there is this reasoning.


def _account_identity_verdict_of(row: dict[str, Any]) -> dict[str, Any]:
    """This row's identity verdict, from the SAME mapped cells stage 4 reads.

    ⚠ Imported inside the function: `import_runs` imports THIS module at top
    level, so the reverse edge has to be lazy or neither imports.
    """
    from apps.metering.import_runs import account_identity_verdict

    return account_identity_verdict(row.get("mapped") or {})


def _account_row_is_on_file(row: dict[str, Any], world) -> bool:
    """⛔ **THE EXEMPTION, AND IT IS THE WHOLE REASON A CORRECTED RE-RUN STILL
    WORKS.** A row whose account number is already on file goes down the UPDATE
    branch, which creates no account and no customer — so `BR-CUS-1041` has
    nothing to govern there, and applying it would refuse the re-upload of a
    file that loaded lawfully yesterday.

    ⚠ **IT READS THE SAME `world.existing_account_nos` `ACC.NUMBER_ON_FILE`
    READS**, so the two rules cannot disagree about what *on file* means
    (`DEF-544`).
    """
    number = str((row.get("mapped") or {}).get("account_no") or "").strip()
    if not number:
        return False
    on_file = getattr(world, "existing_account_nos", None) or ()
    return number.casefold() in {str(value).casefold() for value in on_file}


def _eval_account_customer_identity_required(rows, world, rule) -> list[RuleHit]:
    """A name and no identifier — the PO's *"otherwise dont create anything"*,
    and a blank name cell, which is the same gap one step earlier."""
    from apps.metering.import_runs import (
        ACCOUNT_IDENTITY_AWAITING,
        ACCOUNT_IDENTITY_NO_NAME,
    )

    hits: list[RuleHit] = []
    for row in rows:
        if _account_row_is_on_file(row, world):
            continue
        verdict = _account_identity_verdict_of(row)
        if verdict["verdict"] == ACCOUNT_IDENTITY_NO_NAME:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem="This row does not say who the account is for.",
                    fix_hint=(
                        "Fill in the customer name, and one way to identify "
                        "them — a Social Security number, a driving licence or "
                        "a phone for a person, or a Tax ID for a company."
                    ),
                )
            )
        elif verdict["verdict"] == ACCOUNT_IDENTITY_AWAITING:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"'{verdict['name']}' has a name and no way to identify them.",
                    fix_hint=(
                        "Add one of a Social Security number, a driving licence "
                        "or a phone for a person, or a Tax ID for a company, "
                        "and upload again. Nothing is created for this row "
                        "until then."
                    ),
                )
            )
    return hits


def _eval_account_customer_identity_mismatch(rows, world, rule) -> list[RuleHit]:
    """The kind is unstated, or the identifier belongs to the other kind."""
    from apps.metering.import_runs import ACCOUNT_IDENTITY_MISMATCH

    hits: list[RuleHit] = []
    for row in rows:
        if _account_row_is_on_file(row, world):
            continue
        verdict = _account_identity_verdict_of(row)
        if verdict["verdict"] != ACCOUNT_IDENTITY_MISMATCH:
            continue
        name = verdict["name"]
        if verdict.get("reason") == "kind_not_stated":
            problem = f"'{name}' has an identifier and the row does not say who it belongs to."
            fix_hint = (
                "Fill in whether this customer is a person or a company. A "
                "person is known by a Social Security number, a driving licence "
                "or a phone; a company by its Tax ID, and the two are never "
                "interchangeable."
            )
        else:
            problem = f"'{name}' is a {verdict['kind']}, and this identifier belongs to the other kind."
            fix_hint = (
                "A person is identified by a Social Security number, a driving "
                "licence or a phone. A company is identified by its Tax ID. "
                "Move the value into the right column, or correct the kind."
            )
        hits.append(RuleHit(row_no=row["row_no"], problem=problem, fix_hint=fix_hint))
    return hits


# ═══════════════════════════════════════════════════════════════════════════
# CR-047 · DEF-2519 — the two refusals that used to escape the row loop
# ═══════════════════════════════════════════════════════════════════════════
def _activating(row: dict[str, Any], world: World) -> bool:
    """Would THIS row take its unit? — the predicate both rules below share.

    ⚠ **A BLANK STATUS IS A DRAFT AND IS NOT AN ACTIVATION.** `BR-CUS-018`
    starts a new account in `pending_activation` unless the caller names
    another status, and a draft never reaches `_make_occupying`: it does not
    occupy the unit, it is not billed, and it needs no start date. So a rule
    that fired on every row would REJECT rows the loader writes without
    complaint — which is why the status is read rather than assumed.

    `False` when nobody could be asked (`occupying_status_codes is None`), so
    both rules go quiet rather than inventing an answer in either direction.
    """
    codes = world.occupying_status_codes
    if not codes:
        return False
    return str((row.get("mapped") or {}).get("status") or "").strip().lower() in codes


def _eval_unit_not_occupied(rows, world, rule) -> list[RuleHit]:
    """⛔ **BR-CUS-017 — one live account per unit, ever — ASKED BEFORE THE
    WRITE INSTEAD OF UNDERNEATH IT (`DEF-2519`, critical).**

    `customers._refuse_if_unit_occupied` raises `BIZ-STATE` from inside
    `_make_occupying`, and until CR-047 that refusal escaped
    `_load_accounts_rows`' loop and took the whole `transaction.atomic()` with
    it: on the measured 1,213-row cutover, one row naming an occupied unit left
    **zero** accounts on file. The savepoint in stage 4 is what makes that one
    row instead of the file; this is what makes it one row the operator sees
    **before** they click Load, beside every other rejection, with its number.

    ⚠ **IT DOES NOT REPLACE THE WRITER'S GUARD AND MUST NOT BE READ AS DOING
    SO.** Two rows of the SAME FILE naming one free unit both pass here — the
    world is read once, before the run writes anything — and so does a unit
    somebody moves into between the rehearsal and the commit. Both are caught
    by `_make_occupying` under its advisory lock, which is the only place a
    check-then-act race can be closed (that function's own docstring says so).
    A stage-3 copy of the lock would be a second, drifting enforcement of the
    one thing standing between one meter and two bills.

    The sentence NAMES the account already there, because that is what the
    operator needs in order to decide which of the two is right — the
    `_refuse_if_unit_occupied` refusal carries the same fact for the same
    reason (IS-7's failed state, T5-15 step 3).
    """
    if world.occupying_status_codes is None or not world.occupied_unit_ids:
        return []
    hits: list[RuleHit] = []
    for row in rows:
        if not _activating(row, world):
            continue
        ref = str((row.get("mapped") or {}).get("unit_ref") or "").strip()
        unit_id = resolve_unit_ref(ref, world.unit_ref_index)
        # A reference that resolves to nothing is `ACC.UNIT_ON_FILE`'s row, not
        # this one — one problem per row, and that rule states it better.
        if unit_id is None or unit_id not in world.occupied_unit_ids:
            continue
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=f"Unit {ref} already has a live account on it.",
                fix_hint=(
                    "Close the account that is there before this one starts, or "
                    "point this row at the unit its customer actually lives in. "
                    "One unit carries one live account at a time — two would "
                    "bill the same meter twice."
                ),
            )
        )
    return hits


def _eval_start_date_required(rows, world, rule) -> list[RuleHit]:
    """⛔ **BR-CUS-022 — an account you are ACTIVATING needs the date its
    service started (`DEF-2519`, the second escaping refusal).**

    `customers._make_occupying` raises `BIZ-COMPLETENESS` on a blank
    `opened_at`, with its own reason: the first bill starts from that date, so
    *"an occupying account without one could never be billed"*. It is required
    there rather than defaulted, and it is required here rather than defaulted
    for the same reason — a date nobody chose is the column a customer's first
    bill is computed from.

    ⚠ **IT ONLY FIRES ON A ROW BEING ACTIVATED.** A cutover file legitimately
    carries drafts and closed accounts, and neither needs a start date; a rule
    that demanded one from every row would reject the rows a migration is
    allowed to bring in unfinished.

    ⚠ **AN UNREADABLE DATE IS NOT THIS RULE'S ROW.** Stage 2 carries a cell it
    could not parse as a problem rather than coercing it, and
    `ACC.VALUES_PARSE` states that far better than "you left it blank" would.
    So a row whose date failed to parse is skipped here and rejected there.
    """
    hits: list[RuleHit] = []
    for row in rows:
        if not _activating(row, world):
            continue
        mapped = row.get("mapped") or {}
        if str(mapped.get("opened_at") or "").strip():
            continue
        if "opened_at" in (row.get("problems") or {}):
            continue  # ACC.VALUES_PARSE owns this row — see the docstring
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem="This account is going live and the file gives no date its service started.",
                fix_hint=(
                    "Fill in the day this customer's service began. It is the day "
                    "the first bill is counted from, so it cannot be guessed — if "
                    "the account is not live yet, set its status to pending "
                    "activation instead and the date can wait."
                ),
            )
        )
    return hits


def _eval_opened_not_in_future(rows, world, rule) -> list[RuleHit]:
    """PO 2026-10-17 — a row whose Opened date is after the tenant's own today
    is refused, one row at a time (`DEF-CUS-10180`). Blank is fine: the column
    is optional, and `ACC.START_DATE_REQUIRED` owns the one case that needs it.
    An unreadable cell is `ACC.VALUES_PARSE`'s and is skipped here, the posture
    `_eval_start_date_required` takes. The mapped value is the ISO date stage 2
    parsed, so a string comparison against today's ISO date is a date one.

    The words are B14 rule 33's: a FACT ≤ 6 words, an INSTRUCTION ≤ 6 per
    sentence."""
    if world.today is None:
        return []
    today_iso = str(world.today)
    hits: list[RuleHit] = []
    for row in rows:
        if "opened_at" in (row.get("problems") or {}):
            continue  # ACC.VALUES_PARSE owns this row
        opened = str((row.get("mapped") or {}).get("opened_at") or "").strip()
        if opened and opened[:10] > today_iso:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"Opened date {opened[:10]} is in the future.",
                    fix_hint="Use the day it opened. Leave blank if unknown.",
                )
            )
    return hits


def _quoted_number_on_file(
    rows, field_name: str, known: set[str], *, noun: str, on_file: bool
) -> list[RuleHit]:
    """The two opposite predicates, stated once because they differ only in a
    `not` and in the sentence they carry.

    ⚠ **A BLANK CELL FIRES NEITHER**, and that is the whole point of the
    2026-08-27 ruling: blank is how a NEW record is spelled, so it is neither
    a match nor an invention.
    """
    hits: list[RuleHit] = []
    lowered = {str(value).strip().lower() for value in known}
    for row in rows:
        number = str((row.get("mapped") or {}).get(field_name) or "").strip()
        if not number:
            continue
        present = number.lower() in lowered
        if present != on_file:
            continue
        if on_file:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{number} is already on file.",
                    fix_hint=(
                        f"Insert & update will update that {noun}; Insert new "
                        "only will reject this row, because a new number comes "
                        "from your numbering settings."
                    ),
                )
            )
        else:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{number} is not a {noun} number this utility has issued.",
                    fix_hint=(
                        "Clear this cell — the number is allocated from "
                        "Settings → Numbering when the row is written. If this "
                        "is your OLD system's number, map that column to "
                        "External reference."
                    ),
                )
            )
    return hits


def _eval_services_enabled(rows, world, rule) -> list[RuleHit]:
    hits = []
    for row in rows:
        services = (row.get("mapped") or {}).get("services_available") or []
        unknown = [code for code in services if code not in world.enabled_services]
        if unknown:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"This utility does not sell {', '.join(unknown)}.",
                    fix_hint="Remove it from the row, or turn the service on in Settings first.",
                )
            )
    return hits


def _eval_references_on_file(rows, world, rule) -> list[RuleHit]:
    hits = []
    for row in rows:
        area = (row.get("mapped") or {}).get("area_name")
        if area and area.strip().lower() not in world.area_names:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"There is no area called {area}.",
                    fix_hint="Add the area in Settings first, or leave the column unmapped.",
                )
            )
    return hits


def _eval_values_parse(rows, world, rule) -> list[RuleHit]:
    return _hits_from_problem_key(rows, "parse")


def _eval_address_on_file(rows, world, rule) -> list[RuleHit]:
    """r10's own second rule, and it is a WARNING on purpose.

    Two premises at one address is unusual and not impossible — a duplex split
    after a migration, a re-numbered street — so it is flagged rather than
    refused.

    ⛔ **THIS DOCSTRING USED TO END *"and the action is `skip_on_load` so the
    operator's own file never silently creates a second row at an address they
    already have"*, AND THAT WAS NEVER TRUE (DEF-750).** Nothing performed the
    skip; the second row was created, silently, exactly as described. The rule
    now declares `FLAG_ONLY`, which is what it does — see the declaration for
    why the skip is not simply built instead.
    """
    hits = []
    seen: dict[str, int] = {}
    for row in rows:
        address = ((row.get("mapped") or {}).get("address_line") or "").strip().lower()
        if not address:
            continue
        if address in world.existing_addresses:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem="A premises is already on file at this address.",
                    # ⛔ **THE SECOND COPY OF DEF-750'S PROMISE, one level down
                    # and in the words the operator reads beside their own
                    # row.** It said *"It will be skipped unless you say to
                    # load it anyway."* — of a row nothing skips, and of a
                    # choice no screen offers. It says what happens now, and
                    # the consequence the operator can act on.
                    fix_hint=(
                        "This row still loads. In Insert & update it updates the "
                        "premises already at this address; in Insert new only it "
                        "adds a second one — check which you meant."
                    ),
                )
            )
        elif address in seen:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem="This address appears twice in this file.",
                    fix_hint=f"Row {seen[address]} has it as well.",
                )
            )
        else:
            seen[address] = row["row_no"]
    return hits


def _eval_type_in_lookup(rows, world, rule) -> list[RuleHit]:
    hits = []
    for row in rows:
        raw_type = (row.get("mapped") or {}).get("premises_type_raw")
        code = (row.get("mapped") or {}).get("premises_type")
        if raw_type and not code:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{raw_type} is not one of the premise types on file.",
                    # The fix names what WILL happen, because `flag_only` means
                    # the type is simply not set — see PRM.TYPE_IN_LOOKUP.
                    fix_hint="This premises will load with no type set. Add the type in Settings, or set it afterwards.",
                )
            )
    return hits


# ── the units evaluators (`BR-MET-096` · `BR-MET-100`) ─────────────────────


def _eval_parent_premise_on_file(rows, world, rule) -> list[RuleHit]:
    """r10's only error-severity units rule, and the one it shows hitting.

    ⚠ **THE PREMISE REFERENCE IS THE CUSTOMER'S OWN TEXT**, carried by stage 2
    under `premises_ref` and never resolved to an id there — so this compares
    text to `premise_no`, which is what the operator typed in their file and
    what they will recognise in the reject list.
    """
    hits = []
    # ⚠ **HOISTED, AND THAT IS THE WHOLE OF CR-036 (e)'s UNITS HALF.** This
    # case-folded set used to be rebuilt INSIDE the loop — once per row — so
    # the rule cost rows x premises-already-on-file: 9,881 units against 9,957
    # premises measured **12.9s** for a check that does nothing but a hash
    # lookup, and 50,000 against 50,000 would be five and a half minutes.
    # Built once, the same 9,881 x 9,957 case is **0.006s**. Same comparison,
    # same hits, same sentences — only the loop invariant moved.
    known_premise_nos = {value.lower() for value in world.existing_premise_nos}
    for row in rows:
        ref = (row.get("mapped") or {}).get("premises_ref")
        token = str(ref).strip() if ref else ""
        if not token:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem="This row names no parent premise.",
                    fix_hint="Map a column to Parent premise, or add the premise ID to the row.",
                )
            )
            continue
        if token.lower() not in known_premise_nos:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"Parent premise {token} was not loaded.",
                    fix_hint="Load the premise first, then re-run just the rejects.",
                )
            )
    return hits


def _unit_pair(mapped: dict[str, Any]) -> tuple[str, str] | None:
    """⛔ **THE UNIT'S IDENTITY, IN ONE PLACE — PO ruling 2026-08-27:
    *"premsies and unit name - not just unit name that combination is
    unique"*.**

    Both halves, lowered, or `None` when the label is missing
    (`UNT.LABEL_REQUIRED` owns that case). Written once because three callers
    need it and a second spelling of an identity key is how one of them comes
    to match a different building's flat.
    """
    premise = str(mapped.get("premises_ref") or "").strip().lower()
    label = str(mapped.get("label") or "").strip().lower()
    return (premise, label) if label else None


def _eval_unit_label_unique(rows, world, rule) -> list[RuleHit]:
    """⛔ **IN-FILE ONLY SINCE 2026-08-27, AND AN ERROR RATHER THAN A FLAG.**

    Two rows of one file naming `(premises, label)` twice are two rows claiming
    to be the SAME UNIT, and the database says so
    (`uq_units_tenant_premises_label`). Whichever mode the run is in, one of
    them is wrong — so unlike the on-file case this needs no knowledge of the
    write mode and can block at stage 3, where the operator can still fix the
    file.

    ⚠ **THE ON-FILE HALF USED TO BE HERE AND HAS MOVED TO `UNT.PAIR_ON_FILE`.**
    Leaving it would have made every legitimate *Insert & update* row an error
    the moment this rule's severity was raised — DEF-543's lesson, arriving
    from the other direction.

    ⚠ **WE REFUSE WHERE r10 SUFFIXES.** r10's action column reads *"suffix and
    continue"*, which would rename a customer's unit `12` to `12-2` — an
    identifier the utility never chose, cannot search for and will not
    recognise on a bill (`BR-MET-089`: carry the problem, never coerce the
    value). The divergence is deliberate and is stamped in `B15 §9`.
    """
    hits = []
    seen: dict[tuple[str, str], int] = {}
    for row in rows:
        key = _unit_pair(row.get("mapped") or {})
        if key is None:
            continue
        premise, label = key
        if key in seen:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=(
                        f"Unit {label} appears twice for premise "
                        f"{premise or '(none)'} in this file."
                    ),
                    fix_hint=(
                        f"Row {seen[key]} names the same unit. A premises and a "
                        "unit label together identify ONE unit, so keep one row "
                        "or give the other a different label."
                    ),
                )
            )
        else:
            seen[key] = row["row_no"]
    return hits


def _eval_unit_pair_on_file(rows, world, rule) -> list[RuleHit]:
    """The identity match against what is ALREADY on file. **SEVERITY IS THE
    RUN'S, NOT THIS FUNCTION'S** — `_for_write_mode` swaps it to ERROR/reject
    under *Insert new only* and leaves it a flag under *Insert & update*.

    ⚠ **THE PREMISES IS HALF THE KEY.** `world.existing_unit_keys` is built as
    `(premise_no, label)` pairs for exactly this reason: a `world` keyed on
    labels alone would report `Apt 3B` at 12 Sample Street as already on file
    because a different building has an `Apt 3B` — and in *Insert & update* the
    loader would then overwrite that other building's flat. Two premises, one
    label, one row is the case, and it has its own test.
    """
    hits = []
    for row in rows:
        key = _unit_pair(row.get("mapped") or {})
        if key is None or key not in world.existing_unit_keys:
            continue
        premise, label = key
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=f"Unit {label} at premise {premise or '(none)'} is already on file.",
                fix_hint=(
                    "Insert & update will update that unit; Insert new only "
                    "will reject this row."
                ),
            )
        )
    return hits


#: `BR-MET-100`'s accepted cost, in the operator's words, appended to every
#: unresolved-plan hint. ONE string because it is one ruling: whichever of the
#: four reasons applies, the row LOADS and the unit cannot bill.
PLAN_COST_SENTENCE = (
    "This unit will be created WITHOUT a plan and flagged. "
    "It cannot be billed until a plan is set."
)


def resolve_plan_ref(ref: Any, index: dict[str, Any]) -> dict[str, Any] | None:
    """One `Plan` cell → what it resolved to, against `World.plan_index`.

    ⚠ **THE ONE RESOLVER STAGE 3, THE DRY RUN AND THE LOAD ALL USE**, which is
    `DEF-544`'s rule restated: a rehearsal judged by a different resolver than
    the commit writes with is worse than no rehearsal. `resolve_unit_ref` above
    exists for the same reason.

    `None` for a row naming NO plan — that is not a row naming a wrong one
    (`BR-MET-098`: an absent plan loads unplanned without a hit). Otherwise a
    verdict whose `plan_id` is set only when exactly one PUBLISHED plan answers
    to the token (`BR-RAT-030`).
    """
    token = str(ref).strip() if ref else ""
    if not token:
        return None
    entry = index.get(token.lower())
    if entry is None:
        return {
            "asked_for": token,
            "plan_id": None,
            "outcome": "unknown",
            "matched_on": "",
            "plan": "",
            "collisions": [],
        }
    return {"asked_for": token, **entry}


def plan_ref_problem(resolved: dict[str, Any]) -> tuple[str, str]:
    """(problem, fix_hint) for a `Plan` cell that did not resolve.

    ⚠ **FOUR SENTENCES, BECAUSE THEY ARE FOUR DIFFERENT ACTS** (`DEF-771`).
    The index is published-only ON PURPOSE (`BR-RAT-030`) and the operator
    could not tell *"no such plan"* from *"that plan exists and is a draft"* —
    the first is a spelling fix or a new plan, the second is one click on
    Publish, the third is choosing a different plan, and the fourth is a name
    collision only a human can break. All four keep `BR-MET-100`'s outcome:
    the row LOADS, unplanned and flagged. **Refusing here means refusing to
    CHOOSE, never refusing the row** — the PO ruled option B and clause 3 of
    `DEF-771` says so again.
    """
    asked = resolved["asked_for"]
    outcome = resolved["outcome"]
    if outcome == "ambiguous":
        both = " and ".join(resolved["collisions"])
        return (
            f"Plan {asked} matches more than one published plan — {both}. "
            "This import will not choose between them.",
            "Rename one of them, or put the plan's CODE in this column instead — "
            f"a code is unique and a name is not. {PLAN_COST_SENTENCE}",
        )
    if outcome == "draft":
        return (
            f"Plan {asked} is a DRAFT — {resolved['plan']}. A draft has no prices a "
            "bill could be produced from, so it cannot be assigned.",
            f"Publish it under Plans & Rates and run this file again. {PLAN_COST_SENTENCE}",
        )
    if outcome == "archived":
        return (
            f"Plan {asked} is ARCHIVED — {resolved['plan']}. An archived plan is "
            "withdrawn, so it cannot be assigned.",
            "Use a published plan in this column, or re-publish this one under "
            f"Plans & Rates. {PLAN_COST_SENTENCE}",
        )
    return (
        f"Plan {asked} is not on file — no plan of this utility has that code or that name.",
        f"Check the spelling, or add the plan under Plans & Rates. {PLAN_COST_SENTENCE}",
    )


def _eval_plan_on_file(rows, world, rule) -> list[RuleHit]:
    """`BR-MET-100` — a WARNING, and the sentence says what happens.

    ⚠ **THE PO OVERRULED THE RECOMMENDATION HERE, SO THE RISK IS CARRIED IN
    THE COPY RATHER THAN ARGUED AGAIN.** Option A rejected the row and named
    the plan; the PO ruled option B — load it, flag it. The cost the PO
    accepted is that *a unit with no plan does not fail, it simply never
    appears on a bill*. A hit that said only "plan not found" would let an
    operator assume the row failed. It did not, and the fix hint says so.

    ⚠ **AND THE SENTENCE NOW SAYS *WHICH* PROBLEM IT IS (`DEF-771`).** It read
    "Plan X is not on file." for all four cases, including the two where the
    plan IS on file — a draft and an archived one — which is the half of the
    fix the defect calls *"half the value"*. `plan_ref_problem` owns the words;
    this evaluator owns only which rows get them.
    """
    hits = []
    for row in rows:
        ref = (row.get("mapped") or {}).get("rate_plan_ref")
        resolved = resolve_plan_ref(ref, world.plan_index)
        if resolved is None or resolved["plan_id"] is not None:
            continue
        problem, fix_hint = plan_ref_problem(resolved)
        hits.append(RuleHit(row_no=row["row_no"], problem=problem, fix_hint=fix_hint))
    return hits


def _eval_unit_type_in_lookup(rows, world, rule) -> list[RuleHit]:
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        raw = mapped.get("unit_type_raw")
        if raw and mapped.get("unit_type") is None:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{raw} is not a unit type on this tenant's list.",
                    fix_hint="Add it under Settings → Reference data, or use an existing type.",
                )
            )
    return hits


# ── the assets evaluators (CR-028 AST-W3 · B16 §4.7b · BR-AST-045) ─────────


def resolve_unit_ref(ref: Any, index: dict[str, str]) -> str | None:
    """One unit reference → a unit id, against the world's `unit_ref_index`.

    ⚠ **PURE, AND SHARED WITH THE LOAD.** Stage 3 judges a reference with this
    function and stage 4 resolves it with the SAME one (`import_runs` calls
    back in here) — two resolvers is how a rehearsal and a commit start
    disagreeing (DEF-544). Accepts the unit number, a "premise · label" pair
    in either spacing, or a tenant-unique bare label.
    """
    token = str(ref or "").strip().lower()
    if not token:
        return None
    direct = index.get(token)
    if direct is not None:
        return direct
    if "·" in token:
        left, _, right = token.partition("·")
        return index.get(f"{left.strip()} · {right.strip()}")
    return None


def _eval_asset_no_unique(rows, world, rule) -> list[RuleHit]:
    """IN-FILE duplicates only (`uq_assets_tenant_no` arriving early) — the
    on-file match is `AST.NUMBER_ON_FILE`'s warning, because stage 3 cannot
    know the write mode (DEF-543's lesson, applied on day one here).

    ⚠ **A BLANK NUMBER IS NOT MERELY LEGITIMATE — SINCE 2026-08-27 IT IS THE
    NORMAL CASE AND THE ONLY ONE A NEW ROW MAY HAVE.** The tenant's asset
    series allocates it (BR-AST-026), and the PO ruled that path the only one.
    A value here is a quote of a number we already issued, so two rows quoting
    the SAME one still cannot both be honoured — which is what this rule is
    now about."""
    hits = []
    seen: dict[str, int] = {}
    for row in rows:
        number = str((row.get("mapped") or {}).get("asset_no") or "").strip()
        if not number:
            continue
        key = number.lower()
        if key in seen:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{number} appears twice in this file.",
                    fix_hint=f"Row {seen[key]} uses it as well. Keep one.",
                )
            )
        else:
            seen[key] = row["row_no"]
    return hits


def _eval_asset_no_on_file(rows, world, rule) -> list[RuleHit]:
    """⛔ **"DOES THIS ROW NAME A METER ALREADY ON FILE?" — the PO's own first
    question (2026-08-27), and its answer decides the row's fate.**

    **TWO WAYS A ROW CAN NAME ONE, and both count (BR-AST-049):** by quoting
    the number we issued (`asset_no`), or by carrying the `external_ref` it was
    loaded with. Only the first existed when this rule was written; the second
    is the one a first migration's correction re-run actually uses, because
    such a file has never held a SMARTBillHub number.

    **SEVERITY IS THE RUN'S, NOT THIS FUNCTION'S** — `_for_write_mode` swaps it
    at declaration time (ERROR under `insert`, informational under `upsert`).
    `DEF-543`'s *"stage 3 does not know the write mode"* stopped being true
    when CR-042 moved the choice to stage 1.

    ⚠ **THE FIX HINT IS MODE-AWARE AND SAYS THE OUTCOME, NOT THE OPTIONS.** An
    operator reading a rejected row needs to know what to do, and *"the write
    mode decides"* tells them only that somebody else knows.
    """
    hits = []
    insert_only = str(getattr(world, "write_mode", "") or "").strip() == "insert"
    for row in rows:
        mapped = row.get("mapped") or {}
        number = str(mapped.get("asset_no") or "").strip()
        legacy = str(mapped.get("external_ref") or "").strip()
        if number and number.lower() in world.asset_index:
            named, how = number, "quotes"
        elif legacy and f"ext:{legacy.lower()}" in world.asset_index:
            named = str(world.asset_index[f"ext:{legacy.lower()}"]["asset_no"])
            how = "external"
        else:
            continue
        if insert_only and how == "quotes":
            fix = (
                "Insert new only writes new records. Choose Insert & update to "
                "update it, or clear this cell — a new record's number is "
                "issued from Settings › Numbering when the row is written."
            )
        elif insert_only:
            fix = (
                "Insert new only writes new records. Choose Insert & update to "
                "update it, or remove this row from the file."
            )
        else:
            fix = "Insert & update will update its spec fields."
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=(
                    f"{named} is already on file."
                    if how == "quotes"
                    else f"{named} already carries this external reference."
                ),
                fix_hint=fix,
            )
        )
    return hits


def _eval_external_ref_unique(rows, world, rule) -> list[RuleHit]:
    """BR-AST-049 in-file duplicates. See the declaration for why on-file
    matches are deliberately NOT hits."""
    hits = []
    seen: dict[str, int] = {}
    for row in rows:
        value = str((row.get("mapped") or {}).get("external_ref") or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{value} appears twice in this file.",
                    fix_hint=(
                        f"Row {seen[key]} carries it as well, and an external "
                        "reference identifies one record. Keep one."
                    ),
                )
            )
        else:
            seen[key] = row["row_no"]
    return hits


def _eval_asset_no_not_on_file(rows, world, rule) -> list[RuleHit]:
    """⛔ **A NUMBER THIS SYSTEM NEVER ISSUED — the PO ruling of 2026-08-27 made
    checkable.**

    Blank passes and is the NORMAL case: the tenant's series allocates
    (BR-AST-026). A value that resolves passes too — it names a row, and
    `AST.NUMBER_ON_FILE` above flags it for the write mode. What is left is a
    number the operator INVENTED, which is precisely what the ruling forbids.

    ⚠ **THE FIX HINT NAMES THE OTHER TWO COLUMNS, and that is not padding.**
    An operator whose file has a `METER_NO` column of their old system's
    numbers has somewhere for it to go (`external_ref`, BR-AST-049) and so
    does the manufacturer's serial (`serial_no`); told only *"leave it blank"*
    they would delete data they have no other home for, which is the very loss
    the ruling's own consequence paragraph exists to prevent.
    """
    hits = []
    for row in rows:
        number = str((row.get("mapped") or {}).get("asset_no") or "").strip()
        if number and number.lower() not in world.asset_index:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{number} is not a number this utility has issued.",
                    fix_hint=(
                        "Clear this cell — the number is allocated from "
                        "Settings → Numbering when the row is written. If this "
                        "is your OLD system's number, map that column to "
                        "External reference; if it is the manufacturer's, map "
                        "it to Serial number."
                    ),
                )
            )
    return hits


def _eval_asset_service_enabled(rows, world, rule) -> list[RuleHit]:
    """BR-AST-009 + BR-MET-003 for the measuring targets: the service is
    REQUIRED and must be one the utility sells. The raw text is what the
    operator typed; the resolved code is what stage 2's lookup found."""
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        raw = str(mapped.get("service_raw") or "").strip()
        if mapped.get("service"):
            continue
        if raw:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"This utility does not sell {raw}.",
                    fix_hint="Fix the service in the row, or turn it on in Settings first.",
                )
            )
        else:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem="This row names no service.",
                    # Noun-free since 2026-09-30: the devices sheet asks too.
                    fix_hint="Every asset has one service — add it to the row.",
                )
            )
    return hits


def _eval_asset_service_has_unit(rows, world, rule) -> list[RuleHit]:
    """`DEF-935` — the STAGE 3 half of the refusal `_check_measuring_
    requirements` performs at stage 4 (`assets.uom_required`).

    ⚠ **THE SENTENCE NAMES THE SERVICE AND THE SETTINGS SCREEN, NOT THE FIELD.**
    The refusal the load raises renders as *"Choose the unit this asset reads
    in."* — which points at a field the assets import does not offer as a
    column at all, so an operator holding the file cannot act on it. What they
    can act on is the service's unit in Settings, which is where the NULL is.

    A row whose service did not resolve is left alone: `AST.SERVICE_ENABLED`
    owns it, and two rules reporting the same row twice is the noise
    `BR-MET-091` exists to avoid.
    """
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        service = str(mapped.get("service") or "").strip()
        if not service:
            continue  # AST.SERVICE_ENABLED owns the unresolved-service row
        if world.service_units.get(service):
            continue
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=f"No unit is on file for {service}, so this meter cannot be read.",
                fix_hint=(
                    f"Set the unit {service} is measured in under Settings → Services, "
                    "then re-run just the rejects."
                ),
            )
        )
    return hits


def _eval_asset_service_at_premises(rows, world, rule) -> list[RuleHit]:
    """BR-MET-119 for the measuring targets — the STAGE 3 half of the refusal
    `services.ensure_service_point` performs at stage 4.

    ⚠ **IT IS HERE SO AN OPERATOR SEES IT BEFORE LOADING, NOT AS A WALL AT
    COMMIT.** Every premises built through the product before 2026-08-26 holds
    `NULL` (DEF-756), so the first asset upload after this ships can reject
    wholesale — which is the ruling working as intended and is exactly why the
    verdict has to arrive at the rehearsal, with the sentence that says what to
    do, rather than as a row count at the end.

    The sentence names all three things BR-MET-119's third clause requires: the
    service asked for, what the address DOES offer (or plainly that it has
    never been asked), and where to change it — the PREMISES, which is the only
    place there is, because a unit has no list of its own (CR-037 withdrawn).
    """
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        service = str(mapped.get("service") or "").strip()
        ref = str(mapped.get("unit_ref") or "").strip()
        if not service:
            continue  # AST.SERVICE_ENABLED owns the unresolved-service row
        if not ref:
            continue  # blank unit → inventory (BR-AST-045); no address to ask
        unit_id = resolve_unit_ref(ref, world.unit_ref_index)
        if unit_id is None:
            continue  # AST.UNIT_ON_FILE owns the missing-unit case
        offer = world.premises_offer.get(str(world.unit_premises.get(str(unit_id)) or ""))
        if offer is None:
            # The unit's premises is not in THIS tenant's index. Say nothing
            # rather than guess: the load's own tenant-scoped read refuses it.
            continue
        label = offer["ref"]
        offered = offer["services"]
        if offered is None:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"Nobody has said which services {label} offers.",
                    fix_hint=f"Add {service} on the premises first, then load again.",
                )
            )
        elif service not in offered:
            listed = ", ".join(str(code) for code in offered) or "nothing"
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{label} offers {listed}, not {service}.",
                    fix_hint=f"Add {service} on the premises first, then load again.",
                )
            )
    return hits


def _eval_unit_ref_on_file(rows, world, rule) -> list[RuleHit]:
    """BR-AST-045's judged half: a NAMED unit must exist; blank never reaches
    here (it loads to inventory — the PO's own sentence)."""
    hits = []
    for row in rows:
        ref = (row.get("mapped") or {}).get("unit_ref")
        token = str(ref or "").strip()
        if not token:
            continue
        if resolve_unit_ref(token, world.unit_ref_index) is None:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"Unit {token} was not loaded.",
                    fix_hint=(
                        "Load the premise/unit first, or clear the unit cell "
                        "to load into inventory instead."
                    ),
                )
            )
    return hits


def _eval_unit_ref_blank_to_inventory(rows, world, rule) -> list[RuleHit]:
    """DEF-1079 — the MIRROR of `_eval_unit_ref_on_file`: a row that names NO
    unit is lawful (BR-AST-045) and is reported, so it stops being counted as
    a row with nothing to say about it.

    The problem sentence is written for the operator, not for us: it names the
    consequence they will meet next week — a meter that cannot take a reading
    — rather than restating the rule. The fix hint offers BOTH lawful answers,
    because loading to inventory really is one of them.
    """
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        if str(mapped.get("unit_ref") or "").strip():
            continue
        # ⚠ A DEVICE MAY SEAT ON A PREMISES INSTEAD (BR-AST-045's third case,
        # the devices target). A row naming a premises is NOT going to
        # inventory, so it is not this rule's row.
        #
        # ⛔ **THE KEY IS `premises_ref`, NOT `premises` (DEF-1106).** This read
        # `mapped.get("premises")` from the day it was written, and stage 2
        # carries a `KIND_PREMISE_REF` cell under `premises_ref` — the name
        # `_unit_seat_for` and `_eval_premises_on_file` both use. So the guard
        # never fired: measured on the CR-028 devices fixture, **7 of 10 rows**
        # were told *"No unit named — this loads into inventory"* while the
        # very next stage seated every one of them on the premises they named.
        # The rule's own comment describes the behaviour it did not have, which
        # is hard-won law 1 exactly.
        if str(mapped.get("premises_ref") or "").strip():
            continue
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem="No unit named — this loads into inventory.",
                fix_hint=(
                    "Name the unit to put it in service, or leave it blank "
                    "and assign it later from the meter's own page."
                ),
            )
        )
    return hits


def _eval_unit_service_free(rows, world, rule) -> list[RuleHit]:
    """r10 row 588, made a rule: one ACTIVE meter per unit per service — the
    check that keeps billing unambiguous (B16 §4.7a). Counts what is on file
    AND what this same file already tagged, so the second of two in-file rows
    aimed at one seat is caught before the commit could race itself."""
    hits = []
    taken_in_file: dict[tuple[str, str], int] = {}
    for row in rows:
        mapped = row.get("mapped") or {}
        ref = str(mapped.get("unit_ref") or "").strip()
        service = mapped.get("service")
        if not ref or not service:
            continue
        unit_id = resolve_unit_ref(ref, world.unit_ref_index)
        if unit_id is None:
            continue  # AST.UNIT_ON_FILE owns the missing-unit case
        seat = (unit_id, str(service))
        holder = world.unit_service_taken.get(seat)
        own_number = str(mapped.get("asset_no") or "").strip().lower()
        if not own_number:
            # ⛔ **THE ROW'S OWN METER, FOUND BY THE UTILITY'S OWN REFERENCE
            # (BR-AST-049, PO ruling 2026-08-27).** Since the ruling a normal
            # row carries NO number, so the comparison below would read `""`
            # against `M-00001` on every row of a corrected re-run and reject
            # the whole file with *"this unit already has an active water
            # meter"* — the exact pile of rejects the ruling's addendum warns
            # about, arriving through this rule instead of the match key.
            # `external_ref` is unique per tenant, so resolving through it
            # names one row and no other.
            legacy = str(mapped.get("external_ref") or "").strip().lower()
            match = world.asset_index.get(f"ext:{legacy}") if legacy else None
            if match is not None:
                own_number = str(match.get("asset_no") or "").strip().lower()
        if holder is not None and own_number and holder.strip().lower() == own_number:
            # ⚠ THE SEAT'S HOLDER IS THIS ROW'S OWN METER — a re-import of a
            # file whose meters are already seated (the Insert & update
            # correction pass) is an UPDATE of the holder, not a second meter
            # on the seat. r10's reject is about a DIFFERENT meter.
            continue
        if holder is not None:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"Unit {ref} already has an active {service} meter ({holder}).",
                    fix_hint=(
                        "Load into inventory instead — clear the unit cell — "
                        "or retire the meter it replaces first."
                    ),
                )
            )
            continue
        if seat in taken_in_file:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=(
                        f"Unit {ref} is already given an active {service} meter "
                        f"by row {taken_in_file[seat]} of this file."
                    ),
                    fix_hint="Keep one of the two rows, or clear this row's unit cell.",
                )
            )
            continue
        taken_in_file[seat] = row["row_no"]
    return hits


def _eval_multiplier_positive_int(rows, world, rule) -> list[RuleHit]:
    """B16 §4.7b: positive int, W → default ×1. The load performs the default
    (`import_runs.multiplier_or_default` — the same predicate, shared so the
    warning and the write cannot disagree)."""
    hits = []
    for row in rows:
        raw = (row.get("mapped") or {}).get("multiplier")
        token = str(raw or "").strip()
        if not token:
            continue
        if token.isdigit() and int(token) > 0:
            continue
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=f"{token} is not a whole number above zero.",
                fix_hint="This row will load at ×1 and stay flagged until corrected.",
            )
        )
    return hits


def _eval_cert_due_future(rows, world, rule) -> list[RuleHit]:
    """A CERT_DUE already behind the tenant's own today: the meter arrives
    test-due, which is a fact to flag, never a reason to refuse the device."""
    if world.today is None:
        return []
    today_iso = str(world.today)
    hits = []
    for row in rows:
        due = (row.get("mapped") or {}).get("certification_due")
        if due and str(due) < today_iso:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"The certification-due date {due} is already past.",
                    fix_hint="The row loads and the asset is flagged test-due.",
                )
            )
    return hits


def _eval_meter_type_in_lookup(rows, world, rule) -> list[RuleHit]:
    return _lookup_misses(rows, "meter_type", "meter type")


def _eval_read_method_in_lookup(rows, world, rule) -> list[RuleHit]:
    return _lookup_misses(rows, "read_method", "read method")


def _eval_account_type_in_lookup(rows, world, rule) -> list[RuleHit]:
    """⛔ DEF-618 — the one lookup miss that is an ERROR, not a flag.

    `_lookup_misses` below tells the operator the row *"will load with the
    field unset"*, and for a meter type or a read method that is true and
    harmless. `account_type` is neither. It is `required=True` in the column
    map, and it is what a plan, a deposit rule and a tax treatment all key off,
    so `customers._validate_account` REFUSES a row without one.

    Before this rule existed that refusal happened **inside stage 4** — the one
    stage that writes. A single unrecognised type in a 1,247-row migration
    raised `VAL-005` out of the load, and the operator saw a failed run rather
    than one rejected row with a row number beside every other rejection. Same
    family as DEF-614: accounts carries four `KIND_LOOKUP` columns and shipped
    with no rule declaring what a miss means for any of them.
    """
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        raw = mapped.get("account_type_raw")
        if raw and mapped.get("account_type") is None:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{raw} is not an account type on this tenant's list.",
                    fix_hint=(
                        "Map it to one of your account types on the previous "
                        "step, or add it under Settings \u2192 Reference data. "
                        "An account cannot be opened without a type."
                    ),
                )
            )
    return hits


def _eval_status_in_lookup(rows, world, rule) -> list[RuleHit]:
    return _lookup_misses(rows, "status", "status")


def _eval_account_subtype_in_lookup(rows, world, rule) -> list[RuleHit]:
    return _lookup_misses(rows, "account_subtype", "account sub-type")


def _eval_preferred_language_in_lookup(rows, world, rule) -> list[RuleHit]:
    return _lookup_misses(rows, "preferred_language", "language")


def _eval_size_class_in_lookup(rows, world, rule) -> list[RuleHit]:
    """⛔ **BR-MET-530 — THE SECOND LOOKUP MISS THAT IS AN ERROR** (the first is
    `AST.ACCOUNT_TYPE_IN_LOOKUP`, and it is worth reading the reason beside it).

    PO ruling 2026-08-28, judgment 3, verbatim in the decision log: an UNKNOWN
    code is **refused at stage 3 (validate), not silently dropped at stage 4
    (load)** — *"because a silently-blank size is what produced the every-size
    ladder in the first place"*.

    ⚠ **THE TWO OUTCOMES DIFFER BY A BILL, NOT BY A FIELD.** `_lookup_misses`
    below tells the operator the row *"will load with the field unset"*, which
    is true and harmless for a meter type. For a connection size it is neither:
    an unset size makes `rating.selectors.pricing_inputs` fall back to the
    NULL "every size" tier group, so the meter bills — quietly, at the wrong
    rung. On r10's own water figures a connection re-read from `W-2` to nothing
    moves the ladder from `3.45 / 5.10 / 7.70` back to `3.20 / 4.80 / 7.20`,
    and nobody is told. A rejected row, with its row number and the sizes on
    file named, is the outcome an operator can act on.

    ⚠ **A BLANK CELL IS NOT A MISS AND NEVER REACHES THIS RULE** (ruling
    judgment 2 — blank stays lawful on both doors, per BR-AST-500). `raw` is
    falsy for an empty cell, exactly as it is for every other lookup, so the
    1,847-meter load this ruling exists to serve is untouched.
    """
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        raw = mapped.get("size_class_raw")
        if raw and mapped.get("size_class") is None:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{raw} is not a connection size on this tenant's list.",
                    fix_hint=(
                        "Map it to one of your sizes on the previous step, or "
                        "add it under Settings \u2192 Reference data. Leave the "
                        "cell EMPTY if you do not know this meter's size — a "
                        "blank size loads; a size we cannot price does not."
                    ),
                )
            )
    return hits


def _lookup_misses(rows, field_name: str, label: str) -> list[RuleHit]:
    """Raw text present, resolved code absent — the `PRM.TYPE_IN_LOOKUP`
    shape: the row loads with the field unset, and the hit says so."""
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        raw = mapped.get(f"{field_name}_raw")
        if raw and mapped.get(field_name) is None:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{raw} is not a {label} on this tenant's list.",
                    fix_hint=(
                        f"This row will load with no {label} set. Add it under "
                        "Settings → Reference data, or use an existing one."
                    ),
                )
            )
    return hits


def resolve_parent_ref(ref: Any, index: dict[str, Any]) -> dict[str, Any] | None:
    """⛔ **ONE `Parent / master meter` CELL → THE MASTER IT NAMES, THREE WAYS.**

    **WHY THIS EXISTS AT ALL, AND IT IS DAMAGE THE NUMBERING RULING DID.**
    Until 2026-08-27 a file supplied its own meter numbers, so a sub-meter file
    could name its master by the number it had always used. Under the PO ruling
    a master's number is **issued by us at import** — so on a first migration
    the utility loads its masters, we give each a number it has never seen, its
    sub-meter file names those masters by its OLD system's identifiers, and
    **every sub-meter row rejects for a master that loaded a minute earlier**.
    The only way through would be: load masters, export the receipt, transcribe
    our numbers into the sub file, re-upload. That is not a migration path.

    **THE ORDER, and it follows `resolve_unit_ref`'s precedent on this same
    import** (*"the unit's NUMBER, or the premises and the unit together, or
    just the unit label"*):

      1. the master's **meter number** — masters already on file before the run;
      2. the master's **serial number** — what is stamped on the device;
      3. the utility's **external reference** — its old system's number.

    **The last two are what a first migration actually holds.**

    ⚠ **AMBIGUITY IS A VERDICT, NEVER A PICK.** `BR-AST-033` makes a duplicate
    serial WARN-BUT-ALLOW, so two masters may carry one legitimately. Taking
    the first would hang a sub-meter off the wrong device and surface months
    later as a wrong bill — so a serial claimed twice comes back as
    `{"ambiguous": [...]}` and the caller refuses by name. `external_ref` is
    `UNIQUE (tenant, …)` and has no such case; the meter number is
    `UNIQUE (tenant, asset_no)`.

    ⚠ **THE SAME RESOLVER STAGE 3 AND THE LOAD BOTH USE** — `DEF-544`'s rule:
    a rehearsal judged by a different resolver than the commit writes with is
    worse than no rehearsal.

    `None` for a token that names nothing.
    """
    token = str(ref or "").strip().lower()
    if not token:
        return None
    for key in (token, f"serial:{token}", f"ext:{token}"):
        entry = index.get(key)
        if entry is None:
            continue
        if entry.get("ambiguous"):
            return {"ambiguous": list(entry.get("ambiguous_asset_nos") or ())}
        return entry
    return None


def _eval_parent_meter_on_file(rows, world, rule) -> list[RuleHit]:
    """BR-AST-003 + B16 §4.7b: the master must exist, be a meter, and be
    ACTIVE. A blank parent is an error here (a sub-meter REQUIRES one) —
    unlike a blank unit, which BR-AST-045 accepts."""
    hits = []
    for row in rows:
        token = str((row.get("mapped") or {}).get("parent_asset_no") or "").strip()
        if not token:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem="This row names no parent master meter.",
                    fix_hint="A sub-meter hangs off a master — add its meter number.",
                )
            )
            continue
        parent = resolve_parent_ref(token, world.asset_index)
        if parent is None:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"Parent meter {token} was not loaded.",
                    fix_hint=(
                        "Load the master first, then re-run just the rejects. "
                        "This cell takes the master's meter number, its serial "
                        "number, or the external reference your old system "
                        "used — whichever your file has."
                    ),
                )
            )
            continue
        if parent.get("ambiguous"):
            # ⚠ WHICH ONE. Never the first (BR-AST-033 — see resolve_parent_ref).
            names = ", ".join(parent["ambiguous"])
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=(
                        f"Serial {token} is carried by more than one meter "
                        f"({names}), so it does not say which master this "
                        "sub-meter hangs off."
                    ),
                    fix_hint=(
                        "Name the master by its meter number or by its "
                        "external reference — both are unique — or correct "
                        "the duplicated serial first."
                    ),
                )
            )
            continue
        if parent["type_code"] not in ("meter", "net_meter"):
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{token} is not a meter, so it cannot parent a sub-meter.",
                    fix_hint="Name the master meter the sub hangs off.",
                )
            )
            continue
        if parent["behavior_class"] != "in_service":
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"Parent meter {token} is not active.",
                    fix_hint="A sub-meter needs an ACTIVE master — assign or replace it first.",
                )
            )
    return hits


def _eval_alloc_within_master(rows, world, rule) -> list[RuleHit]:
    """Sub total ≤ master, computed WHERE COMPUTABLE (the task's own words):
    the in-file allocation shares under one master may not exceed 100%. A row
    with no share is metered, not allocated (B16 §4.7b) and counts nothing."""
    from decimal import Decimal, InvalidOperation

    totals: dict[str, Decimal] = {}
    contributors: dict[str, list[int]] = {}
    display: dict[str, str] = {}  # the file's own casing, for the sentence
    for row in rows:
        mapped = row.get("mapped") or {}
        parent_text = str(mapped.get("parent_asset_no") or "").strip()
        parent = parent_text.lower()
        share = mapped.get("allocation_share_pct")
        if not parent or share in (None, ""):
            continue
        try:
            value = Decimal(str(share))
        except InvalidOperation:  # pragma: no cover — stage 2 carries the parse problem
            continue
        totals[parent] = totals.get(parent, Decimal("0")) + value
        contributors.setdefault(parent, []).append(row["row_no"])
        display.setdefault(parent, parent_text)
    hits = []
    for parent, total in totals.items():
        if total <= 100:
            continue
        for row_no in contributors[parent]:
            hits.append(
                RuleHit(
                    row_no=row_no,
                    problem=(
                        f"The allocation shares under {display[parent]} total {total}% — "
                        "more than the master measures."
                    ),
                    fix_hint="Review the shares so they total at most 100%.",
                )
            )
    return hits


def _eval_alloc_share_in_range(rows, world, rule) -> list[RuleHit]:
    """⛔ **ONE ROW'S OWN SHARE, WHERE THE RULE ABOVE MEASURES THE FILE'S TOTAL
    (CR-047).**

    `assets.services._validate_asset` refuses a share above 100 by name, so a
    row carrying one is certain to be refused at the commit. Asked here, it is
    one rejected row with its number and the operator's own figure in the
    sentence, before they press Load.

    ⚠ **A CELL THAT WOULD NOT PARSE IS NOT THIS RULE'S ROW.** Stage 2 carries
    an unreadable number as a problem rather than coercing it, and
    `AST.VALUES_PARSE` states that far better than a range sentence would —
    the posture `_eval_start_date_required` takes for `opened_at`. A NEGATIVE
    share is stage 2's row for the same reason: the decimal branch already
    carries *"… is negative"* on every non-accounts target.

    The sentence quotes the operator's OWN cell text, never a re-rendered
    Decimal: a file that says `150.00` should read back `150.00`.
    """
    from decimal import Decimal, InvalidOperation

    hits: list[RuleHit] = []
    for row in rows:
        raw = (row.get("mapped") or {}).get("allocation_share_pct")
        text = str(raw if raw is not None else "").strip()
        if not text:
            continue  # blank is "metered, not allocated" (B16 §4.7b)
        try:
            share = Decimal(text)
        except InvalidOperation:  # pragma: no cover — stage 2 carries the parse problem
            continue
        if share <= 100:
            continue
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=f"A share of {text}% is more than the whole master measures.",
                fix_hint=(
                    "A sub-meter's share is its part of the master, so it "
                    "cannot be more than 100%. Correct the share, or leave the "
                    "cell empty if this sub-meter is metered rather than "
                    "allocated."
                ),
            )
        )
    return hits


def _eval_test_interval_positive(rows, world, rule) -> list[RuleHit]:
    """⛔ **A DEVICE TESTED EVERY ZERO MONTHS (CR-047).**

    `_validate_asset` refuses `months < 1`; this asks the same question one
    stage earlier. Blank passes and is the normal case — the create path fills
    it from the seeded interval for the device's kind — so the only rows here
    are the ones a clerk typed a number into that is not a length of time.

    ⚠ **A CELL THAT WOULD NOT PARSE IS `AST.VALUES_PARSE`'S ROW**, exactly as
    for the share above.
    """
    hits: list[RuleHit] = []
    for row in rows:
        raw = (row.get("mapped") or {}).get("test_interval_months")
        text = str(raw if raw is not None else "").strip()
        if not text:
            continue
        try:
            months = int(text)
        except ValueError:  # pragma: no cover — stage 2 carries the parse problem
            continue
        if months >= 1:
            continue
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=f"A test frequency of {text} months is not a length of time.",
                fix_hint=(
                    "Give the number of months between tests — 12 for a yearly "
                    "backflow test. Leave the cell empty if this device is not "
                    "on a schedule of its own: it then takes the usual interval "
                    "for its kind."
                ),
            )
        )
    return hits


def _eval_sub_unit_premises_matches_master(rows, world, rule) -> list[RuleHit]:
    """A sub billing a unit on a DIFFERENT premises than its master is worth a
    look, not a refusal. Computed only when both seats are known — an unseated
    master or an inventory-bound sub states nothing to compare."""
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        parent = world.asset_index.get(str(mapped.get("parent_asset_no") or "").strip().lower())
        unit_id = resolve_unit_ref(mapped.get("unit_ref"), world.unit_ref_index)
        if parent is None or unit_id is None or not parent.get("unit_id"):
            continue
        master_premises = world.unit_premises.get(str(parent["unit_id"]))
        sub_premises = world.unit_premises.get(unit_id)
        if master_premises and sub_premises and master_premises != sub_premises:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=(
                        f"This sub-meter's unit is not on the same premises as "
                        f"its master {parent['asset_no']}."
                    ),
                    fix_hint="Check the unit — a sub usually serves the master's own building.",
                )
            )
    return hits


def _eval_device_type_on_file(rows, world, rule) -> list[RuleHit]:
    """The devices target's type gate — ERROR by the divergence documented on
    the catalog: `assets.type` is a non-null FK and no "Other" is seeded."""
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        if mapped.get("type"):
            continue
        raw = mapped.get("type_raw")
        if raw:
            problem = f"{raw} is not a behind-the-meter device type on this tenant's list."
            fix = "Add the type under Settings → Reference data, or use an existing one."
        else:
            problem = "This row names no device type."
            fix = "Every device declares its kind — backflow, PV, EV charger, comms, battery…"
        hits.append(RuleHit(row_no=row["row_no"], problem=problem, fix_hint=fix))
    return hits


def _eval_device_premises_on_file(rows, world, rule) -> list[RuleHit]:
    """The devices target's premises law: a named premises must exist, and a
    premises-level attach must resolve to ONE unit — assignments seat on units
    (`asset_assignments.unit_id`), so a multi-unit premises needs the unit
    named and a unit-less premises cannot seat anything yet. Blank premises
    AND blank unit is the BR-AST-045 inventory case and never reaches here."""
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        token = str(mapped.get("premises_ref") or "").strip()
        if not token:
            continue
        units = world.premises_units.get(token.lower())
        if units is None:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"Premises {token} was not loaded.",
                    fix_hint=(
                        "Load the premise first, or clear the cell to load "
                        "into inventory instead."
                    ),
                )
            )
            continue
        if str(mapped.get("unit_ref") or "").strip():
            continue  # the named unit decides the seat; AST.UNIT_ON_FILE judges it
        if len(units) == 0:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"Premises {token} has no unit yet, so nothing can hold the device.",
                    fix_hint=(
                        "Load the unit first, or clear the cell to load into " "inventory instead."
                    ),
                )
            )
        elif len(units) > 1:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"Premises {token} has {len(units)} units — name the one the device serves.",
                    fix_hint="Add the unit to the row, or clear the premises cell for inventory.",
                )
            )
    return hits


# ═══════════════════════════════════════════════════════════════════════════
# PLAN U4 / U5 — THE ASSET UPLOAD'S NEW ROW CHECKS (PO rulings 2026-09-30)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **EVERY ONE IS TIER 1 AND AN ERROR, AND THE REASON IS THE RULING, NOT
# TIDINESS.** Plan U4 reads *"Row checks, all problems at once"*: a TIER 2 rule
# skips a row an earlier error already blocked (`validate`'s candidate filter),
# so a row with three problems would show one. Tier 1 walks every row, and
# `validate` joins every error a row collects (`ALL_PROBLEMS_TARGETS`).

#: BR-AST-538's four ratified methods: the stored CODE, and the English words a
#: clerk sees for it. The upload takes either, case-insensitively.
ALLOCATION_RULE_WORDS: dict[str, str] = {
    "rubs": "share of the building's total",
    "sqft": "by floor area",
    "equal": "split equally",
    "absorb": "owner absorbs",
}
#: Plan U4: a register shows 4 to 10 digits.
REGISTER_DIGITS_RANGE: tuple[int, int] = (4, 10)


def allocation_rule_code(raw: Any) -> str | None:
    """The stored code for an allocation-rule cell, or None when it is not one
    of the four. ONE resolver for stage 3 AND the load (`DEF-544`)."""
    token = str(raw or "").strip().lower()
    if not token:
        return None
    if token in ALLOCATION_RULE_WORDS:
        return token
    for code, words in ALLOCATION_RULE_WORDS.items():
        if token == words:
            return code
    return None


def _service_word(code: Any) -> str:
    """`trash` → `Trash`, `storm_water` → `Storm water` — the service as a
    clerk reads it in a sentence (never the snake-case code)."""
    return str(code or "").replace("_", " ").strip().capitalize()


def _row_seat(mapped: dict[str, Any], world: World) -> tuple[str | None, str]:
    """(unit id, what the operator called it) for a device or meter row — the
    SAME resolution the load seats with (`_unit_seat_for`, DEF-544): the named
    unit, else a named premises' ONE unit."""
    ref = str(mapped.get("unit_ref") or "").strip()
    if ref:
        return resolve_unit_ref(ref, world.unit_ref_index), ref
    premises = str(mapped.get("premises_ref") or "").strip()
    if premises:
        units = world.premises_units.get(premises.lower()) or ()
        if len(units) == 1:
            return str(units[0]), premises
    return None, ref or premises


def _eval_device_service_on_unit(rows, world, rule) -> list[RuleHit]:
    """⛔ **PLAN U5 — A DEVICE ATTACHES TO ITS SERVICE'S SERVICE POINT ON THE
    UNIT, AND A UNIT WITHOUT THAT SERVICE REFUSES THE ROW BY NAME.**

    Billing counts a counted service's assets THROUGH the service point
    (`assets.selectors.billable_asset_count`): a cart that is not on the unit's
    trash point is not on the bill. The point is got-or-created by
    `metering.services.ensure_service_point`, which refuses a service the
    unit's premises does not offer (BR-MET-119) — so this is that refusal at
    stage 3, in the words the plan gives: *"Unit has no Trash service"*.

    A row with no seat is inventory (BR-AST-045) and has no unit to ask; a row
    whose service or unit did not resolve belongs to the rule that owns that.
    """
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        service = str(mapped.get("service") or "").strip()
        if not service:
            continue
        unit_id, label = _row_seat(mapped, world)
        if unit_id is None:
            continue
        offer = world.premises_offer.get(str(world.unit_premises.get(str(unit_id)) or ""))
        if offer is None:
            continue  # not this tenant's index — the load's own read refuses it
        offered = offer["services"]
        if offered is None or service not in offered:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"Unit {label} has no {_service_word(service)} service.",
                    fix_hint=(
                        f"Add {_service_word(service)} on the premises {offer['ref']} "
                        "first, then load again."
                    ),
                )
            )
    return hits


def _eval_size_for_service(rows, world, rule) -> list[RuleHit]:
    """⛔ **PLAN U4 — THE SIZE COMES FROM THE ROW'S OWN SERVICE'S LIST.**

    A size is lawful for a service when it is tagged to that service or to
    none (`tenancy.selectors.service_scope_filter`, CR-065) — the same rule the
    Settings picker offers by. `2" fire line` on a trash cart is a size the
    utility HAS and the wrong one for this row: it would price the cart off the
    fire ladder. An unknown size is `AST.SIZE_CLASS_IN_LOOKUP`'s row, and an
    unresolved service is `AST.SERVICE_ENABLED`'s.
    """
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        size = mapped.get("size_class")
        service = str(mapped.get("service") or "").strip()
        if not size or not service:
            continue
        tag = world.size_service.get(str(size))
        if tag and tag != service:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=(
                        f"{size} is a size for {_service_word(tag)}, not for "
                        f"{_service_word(service)}."
                    ),
                    fix_hint=(
                        f"Choose one of the {_service_word(service)} sizes on your "
                        "Reference data list, or leave the cell empty."
                    ),
                )
            )
    return hits


def _eval_uom_for_service(rows, world, rule) -> list[RuleHit]:
    """⛔ **PLAN U4 — THE UNIT OF MEASURE IS ONE THIS SERVICE ALLOWS.**

    Two refusals, one rule, because they are one question — *can this row
    carry this unit?*: a unit not on the tenant's list at all, and a unit
    scoped to ANOTHER service (`kWh` on a water meter). Blank never reaches
    here: it takes the service's default unit (PO 2026-09-30,
    `SERVICE_DEFAULT_UOMS`), which is hard rule 3 kept, never an assumed unit.
    """
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        raw = mapped.get("unit_raw")
        if not raw:
            continue
        unit = mapped.get("unit")
        if unit is None:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{raw} is not a unit of measure on this tenant's list.",
                    fix_hint=(
                        "Use one of your units under Settings → Reference data, "
                        "or leave the cell empty for the service's own unit."
                    ),
                )
            )
            continue
        service = str(mapped.get("service") or "").strip()
        tag = world.uom_service.get(str(unit))
        if service and tag and tag != service:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=(
                        f"{unit} is a unit for {_service_word(tag)}, not for "
                        f"{_service_word(service)}."
                    ),
                    fix_hint=(
                        f"Use a {_service_word(service)} unit, or leave the cell "
                        "empty for the service's own unit."
                    ),
                )
            )
    return hits


def _eval_allocation_rule_in_list(rows, world, rule) -> list[RuleHit]:
    """Plan U4 — BR-AST-538's four methods, CHOSEN, never typed: a fifth value
    would reach the reconciliation engine by typo. Blank is lawful (*metered,
    not allocated*)."""
    hits = []
    for row in rows:
        raw = str((row.get("mapped") or {}).get("allocation_rule") or "").strip()
        if raw and allocation_rule_code(raw) is None:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{raw} is not an allocation rule.",
                    fix_hint="Use rubs, sqft, equal or absorb — or leave it empty.",
                )
            )
    return hits


def _eval_register_digits_in_range(rows, world, rule) -> list[RuleHit]:
    """Plan U4 — a register shows 4 to 10 digits. Blank is 9 (BR-AST-015)."""
    low, high = REGISTER_DIGITS_RANGE
    hits = []
    for row in rows:
        value = (row.get("mapped") or {}).get("register_digits")
        if value is None or value == "":
            continue
        try:
            digits = int(value)
        except (TypeError, ValueError):
            continue  # AST.VALUES_PARSE owns a cell that is not a number
        if not low <= digits <= high:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{digits} register digits is outside {low} to {high}.",
                    fix_hint=f"Use {low} to {high}, or leave it empty for 9.",
                )
            )
    return hits


def _eval_loss_tolerance_in_range(rows, world, rule) -> list[RuleHit]:
    """Plan U4 — a loss tolerance is a percentage, 0 to 100. A negative never
    reaches here: stage 2 refuses a negative decimal as a parse problem."""
    hits = []
    for row in rows:
        value = (row.get("mapped") or {}).get("loss_tolerance_pct")
        if value in (None, ""):
            continue
        try:
            pct = Decimal(str(value))
        except (InvalidOperation, ValueError):
            continue
        if pct > 100:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"A loss tolerance of {value}% is above 100%.",
                    fix_hint="Use 0 to 100, or leave it empty.",
                )
            )
    return hits


def _eval_parent_same_service(rows, world, rule) -> list[RuleHit]:
    """⛔ **PLAN U4 — A PARENT MEASURES THE SAME SERVICE AS WHAT HANGS OFF IT.**

    A water sub-meter under an electric master is allocated from the wrong
    register; a trash cart linked to a water meter says nothing true. The
    parent's service is read through its service point (the same path
    `billable_asset_count` reads); a parent in inventory has none on file and
    is not judged — the rule refuses only what it can SEE is wrong. An
    unresolvable or ambiguous parent is `AST.PARENT_ON_FILE`'s row.
    """
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        token = str(mapped.get("parent_asset_no") or "").strip()
        service = str(mapped.get("service") or "").strip()
        if not token or not service:
            continue
        parent = resolve_parent_ref(token, world.asset_index)
        if parent is None or parent.get("ambiguous"):
            continue
        parent_service = parent.get("service_code")
        if parent_service and parent_service != service:
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=(
                        f"{token} measures {_service_word(parent_service)}, not "
                        f"{_service_word(service)}."
                    ),
                    fix_hint="Name a parent meter of the same service, or fix the service.",
                )
            )
    return hits


def _eval_device_parent_on_file(rows, world, rule) -> list[RuleHit]:
    """Plan U2/U4 — a DEVICE's parent is OPTIONAL (a cart sits behind no
    meter), so a blank cell passes; a named one must resolve exactly as a
    sub-meter's master does — ONE resolver, `resolve_parent_ref` (BR-AST-050
    (c), DEF-544) — and be a meter. `_eval_parent_meter_on_file` is reused on
    the rows that name one, with its words turned from sub-meter to device."""
    named = [
        row
        for row in rows
        if str((row.get("mapped") or {}).get("parent_asset_no") or "").strip()
    ]
    return [
        RuleHit(
            row_no=hit.row_no,
            problem=hit.problem.replace("a sub-meter", "a device").replace(
                "this sub-meter", "this device"
            ),
            fix_hint=(hit.fix_hint or "")
            .replace("A sub-meter needs", "A linked device needs")
            .replace("the sub hangs off", "the device sits behind"),
        )
        for hit in _eval_parent_meter_on_file(named, world, rule)
    ]


def _eval_next_test_derivable(rows, world, rule) -> list[RuleHit]:
    """TEST_FREQ without NEXT_TEST: derived from the install date at load
    (`DEFAULT_TO`), or flagged underivable when there is no install date to
    count from — stated, never guessed."""
    hits = []
    for row in rows:
        mapped = row.get("mapped") or {}
        if not mapped.get("test_interval_months") or mapped.get("certification_due"):
            continue
        if mapped.get("install_date"):
            problem = "This device has a test frequency but no next-test date."
            fix = "The next test will be derived from the install date and flagged."
        else:
            problem = (
                "This device has a test frequency but no next-test date and no "
                "install date to derive one from."
            )
            fix = "It loads with no test scheduled — set one from its detail page."
        hits.append(RuleHit(row_no=row["row_no"], problem=problem, fix_hint=fix))
    return hits


def _eval_unavailable(rows, world, rule) -> list[RuleHit]:
    """The evaluator for a rule that cannot run. It returns nothing and it is
    NOT the absence of an evaluator: BR-MET-091 wants the rule listed, with a
    reason and with `hits` honestly zero, rather than quietly missing."""
    return []


# ── the parts target (CR-077) ───────────────────────────────────────────────


def _eval_part_no_required(rows, world, rule) -> list[RuleHit]:
    """⛔ **A ROW WITH NO PART NUMBER IS REJECTED, AND THE SENTENCE HAS TO SAY
    WHY WE WILL NOT INVENT ONE.**

    Premises, units and meters all take their number from the tenant's own
    series, so an operator who has just loaded those three will reasonably
    expect this upload to do the same. It cannot: there is no `part` series in
    `core.numbering` and `Work-025` has never issued one, so a part number is
    the utility's own and a blank cell has no answer anywhere in the product.
    """
    return [
        RuleHit(
            row_no=row["row_no"],
            problem="This row has no part number.",
            fix_hint=(
                "A part number is yours, not ours — there is no numbering "
                "setting for parts, so nothing can fill this in. Put your own "
                "number in the file and upload it again."
            ),
        )
        for row in rows
        if not str((row.get("mapped") or {}).get("part_no") or "").strip()
    ]


def _eval_part_no_unique(rows, world, rule) -> list[RuleHit]:
    """IN-FILE duplicates of a part number (`uq_parts_tenant_part_no_ci`
    arriving early). Unlike every other target's version of this rule a blank
    is NOT the normal case — `PRT.PART_NO_REQUIRED` above rejects it — but the
    shared helper skips blanks anyway, so a file that is short of numbers gets
    one clear reason per row instead of two."""
    return _quoted_number_duplicates(rows, "part_no")


def _eval_part_no_on_file(rows, world, rule) -> list[RuleHit]:
    """A part number that DOES resolve. Severity is the run's write mode's
    (`NUMBER_ON_FILE_KINDS`), which is what makes *Insert & update* mean
    something on this target."""
    # CR-168 · `DEF-WRK-9588` (image 42) — a part number comes off the FILE,
    # never from numbering settings, so the shared sentence's *"because a new
    # number comes from your numbering settings"* is false here. The drawn fix.
    return [
        RuleHit(
            row_no=hit.row_no,
            problem=hit.problem,
            fix_hint="Import it as Insert & update. Or take the row out.",
        )
        for hit in _quoted_number_on_file(
            rows, "part_no", world.existing_part_nos, noun="part", on_file=True
        )
    ]


def _eval_category_in_lookup(rows, world, rule) -> list[RuleHit]:
    """A category cell naming something the tenant's register does not hold.

    ⚠ **A BLANK IS LAWFUL AND FIRES NOTHING.** `work.services._clean_part`
    writes `category = None` for an empty cell, so a hit on a blank would
    reject rows the load would have written — the exact mirror of the defect a
    rehearsal exists to prevent.

    ⚠ **AND THE MATCH IS NAME-THEN-CODE, BECAUSE THAT IS WHAT THE WRITER
    DOES.** `world.part_categories` is keyed on both, lowered, by work's own
    published index. A rule that knew only the name would reject a file written
    in codes and a file written in codes is exactly what an export from another
    system looks like.
    """
    known = world.part_categories or {}
    if not known:
        # ⚠ **NOTHING IS JUDGED WHEN THE INDEX IS EMPTY, AND THAT IS A CHOICE.**
        # An empty index is either *this tenant has added no categories* or
        # *work could not answer*, and this rule cannot tell them apart —
        # `DEF-075`. Rejecting every categorised row on an unanswerable read
        # would turn a wiring fault into a data-quality report; the writer
        # refuses the row by name either way, and `rejected_at_write` is where
        # that shows.
        return []
    hits: list[RuleHit] = []
    offered = ", ".join(sorted({name for name in known.values()}))
    for row in rows:
        # ⚠ **THE OPERATOR'S OWN CELL, NOT THE RESOLVED ONE (CR-168,
        # `DEF-WRK-9587`).** Once the parts target has a lookup index, stage 2
        # writes the resolved NAME into `category` and `None` for a cell it
        # cannot resolve — so reading `category` here would see an unknown
        # value as a blank and let the row load uncategorised, silently.
        # `category_raw` is what the file said.
        mapped = row.get("mapped") or {}
        value = str(mapped.get("category_raw") or mapped.get("category") or "").strip()
        if not value or value.lower() in known:
            continue
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=f"{value} is not one of your parts categories.",
                fix_hint=(
                    f"Use one of yours — {offered} — or leave the cell empty "
                    "and the part loads with no category. Categories are added "
                    "on Settings."
                ),
            )
        )
    return hits


def _eval_required_field(rows, world, rule) -> list[RuleHit]:
    """TIER 3's one shipped kind — *"every premise must carry an owner"*,
    *"the GIS ref is mandatory for us"*. Two of B15 §4.3A's three tier-3
    examples are exactly this shape; the third (*"no premise outside our three
    ZIP codes"*) needs a value list and has no evaluator, so a rule asking for
    it is reported unavailable by `_tenant_rule` rather than silently ignored.
    """
    target_field = str((rule.params or {}).get("field") or "").strip()
    if not target_field:
        return []
    label = str((rule.params or {}).get("label") or target_field)
    # A DECLARED rule may carry its own fix sentence (CR-168, `DEF-WRK-9588`);
    # the premises wording stays the default for tier 3's tenant rules.
    fix_hint = str((rule.params or {}).get("fix_hint") or "") or (
        f"Your utility requires {label} on every premises."
    )
    hits = []
    for row in rows:
        if not (row.get("mapped") or {}).get(target_field):
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"This row has no {label}.",
                    fix_hint=fix_hint,
                )
            )
    return hits


#: `rule_kind` → evaluator. A kind absent from this map is a rule this product
#: cannot make (BR-MET-091), which is a REASON on the receipt and never a
#: missing row.
def _owner_cell(row: dict[str, Any]) -> str:
    """The operator's own owner text for one row, trimmed. Empty when the file
    carries no `Owner` column at all — in which case neither owner rule fires,
    because a column nobody mapped is not a problem with the data."""
    return str((row.get("mapped") or {}).get("owner_ref") or "").strip()


def _eval_owner_near_match(rows, world, rule) -> list[RuleHit]:
    """BR-MET-402 — the name is CLOSE to two or more parties on file. It LOADS
    with no owner, flagged; nothing is picked.

    ⛔ **CR-055 (PO 2026-08-31) CHANGED THE CONSEQUENCE AND NOT THE JUDGMENT.**
    Until that day this rule was an `ERROR` and the row was thrown away.
    Decision 3 — *"Near match on the name - (b) offer the match, clerk
    decides"* — is unchanged and still binding: the import may not PICK, and it
    does not, because `_resolve_owner_ref` resolves EXACT names only. What
    moved is what refusing to pick costs the operator: the address now loads
    ownerless, on the same worklist a blank Owner column lands on, instead of
    stalling a migration over a spelling.

    ⚠ **THE CANDIDATE NAMES STAY IN THE SENTENCE, AND CR-055 MAKES THAT LOAD-
    BEARING.** The person settling this row has to choose between two named
    parties; naming them here — and again in the receipt's
    `premises_owner_ambiguous_names` — is what saves them re-running the search
    the import already ran.
    """
    from apps.metering.premises_owners import _normalise_owner_name

    hits: list[RuleHit] = []
    for row in rows:
        text = _owner_cell(row)
        if not text or text.lower() in world.owner_exact:
            continue
        candidates = world.owner_near.get(_normalise_owner_name(text)) or []
        if not candidates:
            continue
        names = ", ".join(sorted(str(item.get("name") or "") for item in candidates)[:3])
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=f"Owner '{text}' looks like {names}.",
                fix_hint=(
                    "The address loads with no owner. "
                    "Pick the party on Owner matching."
                ),
            )
        )
    return hits


def _eval_owner_not_on_file(rows, world, rule) -> list[RuleHit]:
    """BR-MET-402 — nobody by that name. FLAG and load.

    ⚠ **THIS DELIBERATELY DOES NOT REJECT, AND `DEF-1088` SAYS WHY IN AS MANY
    WORDS:** *"the ruling makes the owner MANDATORY, so this must ship BEFORE
    the mandatory field, or a utility's first upload refuses every row it
    carries."* On a first upload every row lands here.

    ⛔ **AMENDED 2026-09-19.** This paragraph read: *"The import cannot create
    the party itself: `premises_owners.category` is NOT NULL and BR-MET-151
    clause 3 forbids reading a category off a name, and `premises` has no
    category column to map one from. So the string is kept as provenance and a
    PERSON types the party."* **The last clause of the premise is gone** — the
    PO ruled a category column onto the template on 2026-09-19 — so the import
    CAN create the party when the row states one.

    What is unchanged: the NOT NULL column, `BR-MET-151` clause 3, and the
    outcome for a row that states nothing, which is still *keep the string as
    provenance and let a PERSON type the party*. This rule fires on the NAME
    being unknown and says only that; whether anything is coming for it is
    `PRM.OWNER_CATEGORY_MISSING`'s to say.
    """
    hits: list[RuleHit] = []
    for row in rows:
        text = _owner_cell(row)
        if not text or text.lower() in world.owner_exact:
            continue
        from apps.metering.premises_owners import _normalise_owner_name

        if world.owner_near.get(_normalise_owner_name(text)):
            continue  # the NEAR rule above owns this row
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=f"No owner record named '{text}' yet.",
                fix_hint=(
                    "The address loads and keeps the name. Type the party on "
                    "Premises \u2192 Owner matching, where the category is chosen."
                ),
            )
        )
    return hits


def _eval_owner_column_empty(rows, world, rule) -> list[RuleHit]:
    """PO ruling 2026-08-27 — the row LOADS and is FLAGGED, never rejected.

    ⚠ **A FLAG IS NOT A NUISANCE HERE, IT IS THE WHOLE MITIGATION.** The PO's
    reason for allowing the empty column is *"we cna edit and updaste it
    later"*, and "later" only happens if somebody can find the rows. This puts
    each one on the run's own review list; `unmatched_premises_qs()` is the
    standing worklist behind them and the receipt carries the count.
    """
    return [
        RuleHit(
            row_no=row["row_no"],
            problem="This row names no owner.",
            fix_hint=(
                "The address loads without one. It cannot be billed until an "
                "owner is set — do that on Premises → Owner matching, or add "
                "an Owner column and upload again with Insert & update."
            ),
        )
        for row in rows
        if not _owner_cell(row)
    ]


# ═══════════════════════════════════════════════════════════════════════════
# CR-058 W3 · BR-MET-1030 — the three evaluators, over ONE verdict
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **NONE OF THEM DECIDES ANYTHING.** All three read
# `import_runs.owner_account_verdict`, which is the same function stage 4 asks
# before it creates and the same one the receipt counts — so the warning an
# operator is shown at stage 3 and the act taken at stage 4 cannot disagree.
# That is `DEF-544`'s rule (*"a load that resolves against a different world
# than stage 3 showed is a defect in its own right, not a race"*) applied to a
# judgment rather than to an index.


def _owner_verdict_of(row: dict[str, Any]) -> dict[str, Any]:
    """This row's owner verdict, computed from the SAME mapped cells stage 4
    will read.

    ⚠ Imported inside the function: `import_runs` imports THIS module at
    top level, so the reverse edge has to be lazy or neither imports.
    """
    from apps.metering.import_runs import owner_account_verdict

    return owner_account_verdict(row.get("mapped") or {})


def _eval_owner_awaiting_identity(rows, world, rule) -> list[RuleHit]:
    """A name and no identifier — the PO's *"otherwise dont create anything"*."""
    from apps.metering.import_runs import OWNER_ACCOUNT_AWAITING_IDENTITY

    return [
        RuleHit(
            row_no=row["row_no"],
            problem=f"'{_owner_cell(row)}' has a name and no way to identify them.",
            fix_hint=(
                "The address loads. To give this owner an account, add one of "
                "a Social Security number, a driving licence or a phone for a "
                "person, or a Tax ID for a company, and upload again with "
                "Insert & update."
            ),
        )
        for row in rows
        if _owner_cell(row)
        and _owner_verdict_of(row)["verdict"] == OWNER_ACCOUNT_AWAITING_IDENTITY
    ]


def _eval_owner_account_type_missing(rows, world, rule) -> list[RuleHit]:
    """Identity is there; the consumer category is not, and nothing may guess
    it."""
    from apps.metering.import_runs import OWNER_ACCOUNT_NO_ACCOUNT_TYPE

    return [
        RuleHit(
            row_no=row["row_no"],
            problem=(
                f"'{_owner_cell(row)}' can be identified, but the row does not "
                "say what their account is charged as."
            ),
            fix_hint=(
                "Fill in Owner account type — the same list the Accounts "
                "upload uses — and upload again with Insert & update. It "
                "cannot be guessed: it is what the bill is priced by."
            ),
        )
        for row in rows
        if _owner_cell(row)
        and _owner_verdict_of(row)["verdict"] == OWNER_ACCOUNT_NO_ACCOUNT_TYPE
    ]


def _eval_owner_category_in_lookup(rows, world, rule) -> list[RuleHit]:
    """The operator named a category and it is not on the tenant's list —
    `PRM.TYPE_IN_LOOKUP`'s shape, on the column added 2026-09-19.

    ⚠ **THE FIX NAMES WHAT WILL HAPPEN**, because `FLAG_ONLY` means the
    address and its owner account still load and only the owner RECORD is not
    created. A sentence that only says *"this is wrong"* leaves the operator
    guessing what it cost them.
    """
    hits: list[RuleHit] = []
    for row in rows:
        mapped = row.get("mapped") or {}
        raw = str(mapped.get("owner_category_raw") or "").strip()
        if raw and not mapped.get("owner_category"):
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    problem=f"{raw} is not one of the owner categories on file.",
                    fix_hint=(
                        "The address and the owner's account still load, and no "
                        "owner record is created. Add the category on Settings, "
                        "or correct the spelling, and upload again with Insert "
                        "& update."
                    ),
                )
            )
    return hits


def _eval_owner_category_missing(rows, world, rule) -> list[RuleHit]:
    """The row earns an ACCOUNT and says nothing about what kind of owner this
    is, so the owner RECORD cannot be created — PO ruling 2026-09-19.

    ⚠ **SILENT ON A NAME ALREADY ON FILE.** The party exists, the import links
    to it, and the category is already recorded against it. Telling an operator
    to fill in a column that would change nothing is the noise `B14` rule 32 and
    `DEF-771` clause 3 are both about.

    ⚠ **AND SILENT ON A ROW THAT EARNS NO ACCOUNT.** Such a row already has a
    sibling rule saying what it is missing, and two warnings about one row lead
    to two different next actions — which is the exact fault the three-rule
    split exists to avoid.
    """
    from apps.metering.import_runs import OWNER_ACCOUNT_ELIGIBLE

    hits: list[RuleHit] = []
    for row in rows:
        name = _owner_cell(row)
        if not name or name.lower() in world.owner_exact:
            continue
        verdict = _owner_verdict_of(row)
        if verdict["verdict"] != OWNER_ACCOUNT_ELIGIBLE or verdict.get("category"):
            continue
        # ⚠ **AND NOT WHERE THEY TYPED SOMETHING WE DID NOT RECOGNISE** —
        # `PRM.OWNER_CATEGORY_IN_LOOKUP` owns that row and says something
        # different about it. Two warnings on one row lead to two different
        # next actions, which is the exact fault the owner rules' three-way
        # split exists to avoid.
        if verdict.get("category_raw"):
            continue
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=(
                    f"'{name}' gets an owner account, and no owner record is "
                    "created for them."
                ),
                fix_hint=(
                    "Fill in Owner category — the list on Settings, such as "
                    "Landlord or Property manager — and upload again with "
                    "Insert & update. Without it the address loads and someone "
                    "types the owner on the Owners screen later. It cannot be "
                    "guessed from a name."
                ),
            )
        )
    return hits


def _eval_owner_identity_mismatch(rows, world, rule) -> list[RuleHit]:
    """The kind is unstated, or the identifier belongs to the other kind."""
    from apps.metering.import_runs import OWNER_ACCOUNT_IDENTITY_MISMATCH

    hits: list[RuleHit] = []
    for row in rows:
        name = _owner_cell(row)
        if not name:
            continue
        verdict = _owner_verdict_of(row)
        if verdict["verdict"] != OWNER_ACCOUNT_IDENTITY_MISMATCH:
            continue
        if verdict.get("reason") == "kind_not_stated":
            problem = f"'{name}' has an identifier and does not say who it belongs to."
            fix_hint = (
                "Fill in Owner is a person or a company. A person is known by "
                "a Social Security number, a driving licence or a phone; a "
                "company by its Tax ID, and the two are never interchangeable."
            )
        else:
            problem = f"'{name}' is a {verdict['kind']}, and this identifier belongs to the other kind."
            fix_hint = (
                "A person is identified by a Social Security number, a driving "
                "licence or a phone. A company is identified by its Tax ID. "
                "Move the value into the right column, or correct the kind."
            )
        hits.append(RuleHit(row_no=row["row_no"], problem=problem, fix_hint=fix_hint))
    return hits


# ── the payments target (`P1.1` / `P1.12`) ─────────────────────────────────
#
# ⚠ **ALL THREE ASK PAYMENTS AND DECIDE NOTHING THEMSELVES.** What counts as a
# match is payments' answer, not a second one (`DEF-544`, and `BR-MET-096`'s
# whole posture: the runner stages and judges, the owning module rules on its
# own facts). A ladder re-implemented here would drift from the writer's within
# a release, and the operator would read one verdict in the rehearsal and meet
# another at the commit.


def _payment_verdict_of(row: dict[str, Any], world: World) -> dict[str, Any] | None:
    """This row's match verdict, from payments' own ladder, or `None`.

    `None` when payments cannot answer at all — and every caller below then
    reports NOTHING rather than reporting the row clean. An unwired matcher
    must never look like a file with no problems in it (hard-won law 7's
    *incapable of failing* shape, refused by construction).
    """
    if world.payments_account_index is None:
        return None
    mapped = row.get("mapped") or {}
    return seams.payments_match_account(
        account_ref=mapped.get("account_ref"),
        payer_name=mapped.get("payer_name"),
        index=world.payments_account_index,
    )


def _eval_payment_row_identified(rows, world, rule) -> list[RuleHit]:
    """A row naming neither an account nor a payer is money with nowhere to go."""
    hits: list[RuleHit] = []
    for row in rows:
        mapped = row.get("mapped") or {}
        named = str(mapped.get("account_ref") or "").strip() or str(
            mapped.get("payer_name") or ""
        ).strip()
        if named:
            continue
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem="This row names no account and no payer.",
                fix_hint=(
                    "There is nothing to match this money to. Add the account "
                    "number to the row and upload the file again."
                ),
            )
        )
    return hits


def _eval_payment_account_on_file(rows, world, rule) -> list[RuleHit]:
    """The file named an account; do we have it?

    ⚠ **A ROW THAT NAMES NO ACCOUNT IS NOT A HIT HERE.** It is either
    `PAY.PAYER_NAMED`'s (nothing at all) or `PAY.NAME_ONLY_MATCH`'s (a payer to
    judge). Firing on a blank would reject rows a person could have placed.
    """
    hits: list[RuleHit] = []
    for row in rows:
        mapped = row.get("mapped") or {}
        named = str(mapped.get("account_ref") or "").strip()
        if not named:
            continue
        verdict = _payment_verdict_of(row, world)
        if verdict is None or verdict.get("state") == "clean":
            continue
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=f"{named} is not an account you have.",
                fix_hint=(
                    "Check the number in the file. If the customer was never "
                    "migrated, load the account first and upload this again."
                ),
            )
        )
    return hits


def _eval_payment_name_only_match(rows, world, rule) -> list[RuleHit]:
    """⛔ **`P1.12` — THE SUGGESTION, SHOWN BEFORE THE COMMIT AND NEVER ACTED ON.**

    ⚠ HELD (an error) since `DEF-PAY-10756`: as a flag the dry run counted it
    as a payment to create, and the writer then refused it. The paragraph below
    is the history of why it was a flag.
    It FLAGGED rather than rejected, and the difference is what a person can do
    about it: a wrong account number is a file to correct, and a payer name
    that looks like one account is a judgement only a person can make. The row
    loads nothing either way — `create_payment_from_import` refuses it — so
    what this rule buys is the operator seeing it at the rehearsal instead of
    on the receipt.
    """
    hits: list[RuleHit] = []
    for row in rows:
        mapped = row.get("mapped") or {}
        if str(mapped.get("account_ref") or "").strip():
            continue
        verdict = _payment_verdict_of(row, world)
        if verdict is None or verdict.get("method") != "name_only":
            continue
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=f"{verdict.get('account_no')} is a guess from the payer's name.",
                fix_hint=(
                    "A name is not an account number. Put the account number "
                    "in the file and upload it again, or record this one "
                    "payment by hand."
                ),
            )
        )
    return hits


def _payment_accounts_by_id(world: World) -> dict[str, dict[str, Any]]:
    """The payments index re-keyed by account id — built ONCE per rule, so a
    400-row file against a 40,000-account index is two passes, never a product
    of the two (NFR-5's T5 ceiling)."""
    return {
        str(entry.get("id")): entry for entry in (world.payments_account_index or {}).values()
    }


def _payment_account_entry(
    row: dict[str, Any], world: World, by_id: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    """The index entry of the account this row CLEANLY matched, or None.

    Only a clean match is judged: a row that names no account we have is
    `PAY.ACCOUNT_ON_FILE`'s, and a name-only guess is `PAY.NAME_ONLY_MATCH`'s.
    """
    verdict = _payment_verdict_of(row, world)
    if verdict is None or verdict.get("state") != "clean":
        return None
    return by_id.get(str(verdict.get("account_id") or ""))


def _eval_payment_account_not_closed(rows, world, rule) -> list[RuleHit]:
    """`DEF-PAY-10757` (L2-09) — money for a CLOSED account is HELD.

    Closed is the status's behaviour class (`terminal`, BR-CUS-055), never its
    label, so a tenant that renames *Closed* keeps the rule. The tester's
    $66.00 for a closed account posted with no warning; it now waits for a
    person, who refunds it or moves it to the customer's new account."""
    hits: list[RuleHit] = []
    by_id = _payment_accounts_by_id(world)
    for row in rows:
        entry = _payment_account_entry(row, world, by_id)
        if entry is None or entry.get("behavior_class") != "terminal":
            continue
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=f"Account {entry.get('account_no')} is closed.",
                fix_hint="Take this row out. Record it by hand.",
            )
        )
    return hits


#: The seeded account-status CODES that mean the account is in a disconnect
#: (`lookup_defaults.json` → `account_statuses`): marked for shut-off, or shut
#: off. Codes, never names — a tenant may rename either.
DISCONNECT_STATUS_CODES = frozenset({"marked_disconnect", "disconnected"})


def _eval_payment_account_in_disconnect(rows, world, rule) -> list[RuleHit]:
    """`DEF-PAY-10757` (L2-09) — a payment for an account in a disconnect LOADS
    and is FLAGGED: the money is real and may be what stops the shut-off, so a
    person must look today rather than tomorrow (the tester's $942.34)."""
    hits: list[RuleHit] = []
    by_id = _payment_accounts_by_id(world)
    for row in rows:
        entry = _payment_account_entry(row, world, by_id)
        if entry is None or str(entry.get("status_code") or "") not in DISCONNECT_STATUS_CODES:
            continue
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=f"Account {entry.get('account_no')} is in a disconnect.",
                fix_hint="It loads. Check the shut-off today.",
            )
        )
    return hits


def _eval_payment_date_not_future(rows, world, rule) -> list[RuleHit]:
    """`DEF-PAY-10757` (L2-09) — a payment dated after today is REFUSED.

    Money cannot have arrived tomorrow. Compared with the tenant's business day
    (`world.today`, BR-TEN-043), never a clock. Silent when today is unknown."""
    if world.today is None:
        return []
    today_iso = str(world.today)
    hits: list[RuleHit] = []
    for row in rows:
        paid_on = str((row.get("mapped") or {}).get("paid_on") or "").strip()
        if not paid_on or paid_on[:10] <= today_iso:
            continue
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=f"The date paid, {paid_on[:10]}, is after today.",
                fix_hint="Correct the date. Then upload again.",
            )
        )
    return hits


def _payment_cheque_key(row: dict[str, Any], world: World) -> Any:
    """This row's cheque identity, through payments' ONE definition, or None.

    The account half is the account payments MATCHED (so `A-1` and its legacy
    reference are one account), falling back to what the file typed when no
    clean match exists — two identical unmatched rows are still one cheque.
    """
    mapped = row.get("mapped") or {}
    verdict = _payment_verdict_of(row, world)
    account = (
        verdict.get("account_id")
        if verdict is not None and verdict.get("state") == "clean"
        else None
    ) or (str(mapped.get("account_ref") or "").strip().lower() or None)
    return seams.payments_cheque_key(account, mapped.get("amount"), mapped.get("reference"))


def _eval_payment_cheque_once_in_file(rows, world, rule) -> list[RuleHit]:
    """`DEF-PAY-10697` (LBX-08) — the SAME cheque twice in one file is held.

    The first occurrence goes forward; every later one is held, naming the row
    it repeats. *Keep the latest row when a key appears twice*, when the
    operator ticks it, has already dropped the earlier copies at stage 2 on
    account + reference, so this fires only where nobody chose."""
    hits: list[RuleHit] = []
    first: dict[Any, int] = {}
    for row in rows:
        key = _payment_cheque_key(row, world)
        if key is None:
            continue
        if key in first:
            reference = str((row.get("mapped") or {}).get("reference") or "").strip()
            hits.append(
                RuleHit(
                    row_no=row["row_no"],
                    # `DEF-PAY-10760` (L2-02) — a store receipt (`HV-1029-0006`)
                    # is not a cheque; the reference column carries either.
                    problem=f"Reference {reference} is already in this file.",
                    fix_hint=f"Row {first[key]} has the same payment. Keep one.",
                )
            )
        else:
            first[key] = row["row_no"]
    return hits


def _eval_payment_cheque_not_already_recorded(rows, world, rule) -> list[RuleHit]:
    """`DEF-PAY-10697` (LBX-08) — a cheque this utility already recorded is held.

    Asks payments ONCE, about this file's matched cheques only. Silent when
    payments cannot answer (`None`), never a blanket pass dressed as a check."""
    lookup = world.payments_posted_cheques
    if lookup is None or world.payments_account_index is None:
        return []
    keyed: list[tuple[dict[str, Any], Any]] = []
    for row in rows:
        verdict = _payment_verdict_of(row, world)
        if verdict is None or verdict.get("state") != "clean":
            continue
        mapped = row.get("mapped") or {}
        key = seams.payments_cheque_key(
            verdict.get("account_id"), mapped.get("amount"), mapped.get("reference")
        )
        if key is not None:
            keyed.append((row, key))
    if not keyed:
        return []
    found = lookup([key for _row, key in keyed]) or {}
    hits: list[RuleHit] = []
    for row, key in keyed:
        if key not in found:
            continue
        reference = str((row.get("mapped") or {}).get("reference") or "").strip()
        hits.append(
            RuleHit(
                row_no=row["row_no"],
                problem=f"Reference {reference} is already recorded as {found[key]}.",
                fix_hint="Take this row out. It is paid already.",
            )
        )
    return hits


EVALUATORS: dict[str, Callable[..., list[RuleHit]]] = {
    # ── payments (`P1.1` / `P1.12`) ─────────────────────────────────────────
    "payment_cheque_once_in_file": _eval_payment_cheque_once_in_file,
    "payment_cheque_not_already_recorded": _eval_payment_cheque_not_already_recorded,
    # ⚠ Registered here or the three DeclaredRules above are rows nothing ever
    # evaluates — hard-won law 2 one layer below the UI, and on a money path.
    "payment_row_identified": _eval_payment_row_identified,
    "payment_account_on_file": _eval_payment_account_on_file,
    "payment_name_only_match": _eval_payment_name_only_match,
    "payment_account_not_closed": _eval_payment_account_not_closed,
    "payment_account_in_disconnect": _eval_payment_account_in_disconnect,
    "payment_date_not_future": _eval_payment_date_not_future,
    "owner_near_match": _eval_owner_near_match,
    "owner_not_on_file": _eval_owner_not_on_file,
    "owner_column_empty": _eval_owner_column_empty,
    # CR-058 W3 · BR-MET-1030 — the three reasons an owner gets no account.
    "owner_awaiting_identity": _eval_owner_awaiting_identity,
    "owner_account_type_missing": _eval_owner_account_type_missing,
    "owner_identity_mismatch": _eval_owner_identity_mismatch,
    # PO ruling 2026-09-19 — the fourth, and the only one that still gets an
    # account. ⚠ Registered here or the DeclaredRule above is a row nothing
    # ever evaluates, which is hard-won law 2 one layer below the UI.
    "owner_category_missing": _eval_owner_category_missing,
    "owner_category_in_lookup": _eval_owner_category_in_lookup,
    # ── the assets targets (CR-028 AST-W3) ──────────────────────────────────
    "asset_no_unique": _eval_asset_no_unique,
    "asset_no_on_file": _eval_asset_no_on_file,
    "asset_no_not_on_file": _eval_asset_no_not_on_file,
    "external_ref_unique": _eval_external_ref_unique,
    "asset_service_enabled": _eval_asset_service_enabled,
    "asset_service_has_unit": _eval_asset_service_has_unit,
    "asset_service_at_premises": _eval_asset_service_at_premises,
    "unit_ref_on_file": _eval_unit_ref_on_file,
    "unit_ref_blank_to_inventory": _eval_unit_ref_blank_to_inventory,
    "unit_service_free": _eval_unit_service_free,
    "multiplier_positive_int": _eval_multiplier_positive_int,
    "cert_due_future": _eval_cert_due_future,
    "meter_type_in_lookup": _eval_meter_type_in_lookup,
    "size_class_in_lookup": _eval_size_class_in_lookup,  # BR-MET-530
    # CR-030 W1 / DEF-618 — accounts' four lookups. The first is an ERROR
    # because the field is required; the other three flag and load unset,
    # which is the `_lookup_misses` posture the assets targets already use.
    # CR-058 W7 · BR-CUS-1041 — the two reasons a row creates nothing.
    "account_customer_identity_required": _eval_account_customer_identity_required,
    "account_customer_identity_mismatch": _eval_account_customer_identity_mismatch,
    "account_type_in_lookup": _eval_account_type_in_lookup,
    "status_in_lookup": _eval_status_in_lookup,
    "account_subtype_in_lookup": _eval_account_subtype_in_lookup,
    "preferred_language_in_lookup": _eval_preferred_language_in_lookup,
    "read_method_in_lookup": _eval_read_method_in_lookup,
    "parent_meter_on_file": _eval_parent_meter_on_file,
    "alloc_within_master": _eval_alloc_within_master,
    # ── CR-047 — the two ASSETS refusals that used to escape the row loop.
    # `alloc_within_master` above is the file's TOTAL and warns; this is one
    # row's own share and blocks, because the writer blocks it.
    "alloc_share_in_range": _eval_alloc_share_in_range,
    "test_interval_positive": _eval_test_interval_positive,
    "sub_unit_premises_matches_master": _eval_sub_unit_premises_matches_master,
    "device_type_on_file": _eval_device_type_on_file,
    "device_premises_on_file": _eval_device_premises_on_file,
    "next_test_derivable": _eval_next_test_derivable,
    # ── plan U4/U5 (PO rulings 2026-09-30). ⚠ Registered here or each
    # DeclaredRule is a row nothing ever evaluates (hard-won law 2).
    "device_service_on_unit": _eval_device_service_on_unit,
    "size_for_service": _eval_size_for_service,
    "uom_for_service": _eval_uom_for_service,
    "allocation_rule_in_list": _eval_allocation_rule_in_list,
    "register_digits_in_range": _eval_register_digits_in_range,
    "loss_tolerance_in_range": _eval_loss_tolerance_in_range,
    "parent_same_service": _eval_parent_same_service,
    "device_parent_on_file": _eval_device_parent_on_file,
    # ── premises + units (CR-023) ───────────────────────────────────────────
    "premise_no_on_file": _eval_premise_no_on_file,
    # ── CR-046 C2/C3/C4 — the identifier family, one entry per predicate ────
    "premise_no_not_on_file": _eval_premise_no_not_on_file,
    "unit_no_unique": _eval_unit_no_unique,
    "unit_no_on_file": _eval_unit_no_on_file,
    "unit_no_not_on_file": _eval_unit_no_not_on_file,
    "account_no_unique": _eval_account_no_unique,
    "account_no_on_file": _eval_account_no_on_file,
    "account_no_required": _eval_account_no_required,
    # ── CR-047 / DEF-2519 — the two refusals that used to escape the row loop
    "unit_not_occupied": _eval_unit_not_occupied,
    "start_date_required": _eval_start_date_required,
    # PO 2026-10-17 (`DEF-CUS-10180`) — the imported Opened date.
    "opened_not_in_future": _eval_opened_not_in_future,
    "parent_premise_on_file": _eval_parent_premise_on_file,
    "unit_label_unique": _eval_unit_label_unique,
    "unit_pair_on_file": _eval_unit_pair_on_file,
    "plan_on_file": _eval_plan_on_file,
    "unit_type_in_lookup": _eval_unit_type_in_lookup,
    "address_required": _eval_address_required,
    "premise_no_unique": _eval_premise_no_unique,
    "services_enabled": _eval_services_enabled,
    "references_on_file": _eval_references_on_file,
    "values_parse": _eval_values_parse,
    "address_on_file": _eval_address_on_file,
    "type_in_lookup": _eval_type_in_lookup,
    "expected_units_integer": _eval_unavailable,
    "required_field": _eval_required_field,
    # CR-077 — the parts target.
    "part_no_required": _eval_part_no_required,
    "part_no_unique": _eval_part_no_unique,
    "part_no_on_file": _eval_part_no_on_file,
    "category_in_lookup": _eval_category_in_lookup,
}


def evaluate(rule: DeclaredRule, rows: list[dict[str, Any]], world: World) -> list[RuleHit]:
    """Run ONE rule. An unavailable rule and an `off` rule both return nothing
    — and both are still LISTED, which is the entire point of BR-MET-091."""
    if not rule.available or rule.severity == OFF:
        return []
    evaluator = EVALUATORS.get(rule.rule_kind)
    if evaluator is None:  # pragma: no cover — _tenant_rule marks these unavailable
        return []
    if rule.rule_kind in DATES_ONLY_EXEMPT_KINDS and rule.target in DATES_ONLY_NUMBER_FIELD:
        rows = [row for row in rows if not is_dates_only_row(rule.target, row.get("mapped"))]
    return evaluator(rows, world, rule)


# ═══════════════════════════════════════════════════════════════════════════
# `DEF-MET-10164` — THE "DATES ONLY" ROW (PO ruling 2026-10-17, point 5)
# ═══════════════════════════════════════════════════════════════════════════
#
# PO, verbatim: *"Re-import corrects existing records' Created date only
# (matched on premise / unit number), each change audited old → new"*, and the
# deploy note beside it: *"utilities re-import number + old-system date to
# correct records already imported (every imported row today carries its
# import day)."*
#
# ⚠ **THAT FILE HAS TWO COLUMNS, AND THE ORDINARY RULES WOULD REJECT EVERY ROW
# OF IT.** A premises row needs a street address and a unit row needs a label
# and a parent premise — correctly, for a row that CREATES something. A row
# that carries only OUR number and a Created date creates nothing: it names a
# record already on file (`PRM.PREMISE_NO_NOT_ON_FILE` / `UNT.NUMBER_NOT_ON_FILE`
# still refuse a number we never issued) and asks to correct one date. So the
# three "what a new record needs" rules step aside for exactly that shape and
# for nothing wider; every other rule — parse, in-file uniqueness, the number
# being ours — still runs on it.
#
# ⚠ **THE SHAPE IS JUDGED PER ROW, FROM WHAT THE ROW CARRIES.** A row whose
# only non-empty values are the number and the Created date is a date
# correction whatever else the file maps; a row carrying an address as well is
# an ordinary upsert row and meets every rule as before. The loader reads the
# same predicate (`import_runs._load_locked`), so stage 3 and the write cannot
# disagree about which rows are corrections (`DEF-544`'s lesson).

#: target → the number column that names a record already on file.
DATES_ONLY_NUMBER_FIELD: dict[str, str] = {"premises": "premise_no", "units": "unit_no"}

#: The one field a dates-only row corrects.
DATES_ONLY_FIELD = "created_at"

#: The rules about what a NEW record needs, which a correction row does not.
DATES_ONLY_EXEMPT_KINDS: frozenset[str] = frozenset(
    {"address_required", "required_field", "parent_premise_on_file", "owner_column_empty"}
)


def is_dates_only_row(target: str, mapped: dict[str, Any] | None) -> bool:
    """True when this row carries only our record number and a Created date.

    A Created cell that failed to parse still makes the row a correction row —
    it is refused for its DATE (`*.VALUES_PARSE`), not for a missing address
    the operator never meant to send.
    """
    number_field = DATES_ONLY_NUMBER_FIELD.get(target)
    mapped = mapped or {}
    if number_field is None or not str(mapped.get(number_field) or "").strip():
        return False
    carried = {
        key
        for key, value in mapped.items()
        if not str(key).startswith("__") and key != number_field and value not in (None, "", [], {})
    }
    if carried - {DATES_ONLY_FIELD}:
        return False
    if DATES_ONLY_FIELD in carried:
        return True
    parse = (mapped.get("__parse_problems__") or {}).get("parse") or {}
    return parse.get("target") == DATES_ONLY_FIELD


def error_severity_rules(rules: list[DeclaredRule]) -> list[DeclaredRule]:
    """The rules that can actually BLOCK a load.

    Serving this is not decoration. Stage 3's own sub-line promises *"Errors
    block the load"*, and since `BR-MET-097` (PO 2026-08-21) ruled that we do
    not check an imported address at all, **no PLATFORM rule of error severity
    remains on a premises import** — the only errors left are the five
    structural ones, which no utility can configure and which the database
    would refuse anyway. An operator is entitled to know which of those two
    sentences applies to them. (This paragraph used to say *"with
    `PRM.ADDRESS_IN_TERRITORY` unavailable"*, which described a gap. It is not
    a gap now; it is a ruling, and the rule row is gone rather than greyed.)
    """
    return [rule for rule in rules if rule.blocks]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-004@8bf4be8 (CR-023 P4 stage 3 — design B15 §4.3A; BR-MET-090/091 CONFIRMED 2026-08-21)
# generated: 2026-08-21 by the CR-023 P3/P4 lane · AMENDED 2026-08-22 by the CR-028 AST-W3 lane (the three assets catalogs + fifteen evaluators, World's assets half, resolve_unit_ref shared with the load (DEF-544 posture)) · AMENDED 2026-08-29 by the CR-047 assets-rules lane (AST.ALLOC_SHARE_IN_RANGE + AST.TEST_INTERVAL_POSITIVE — the two `_validate_asset` RANGE refusals that reached the operator only from under the write; the four rules CR-047 proposed are each already carried and NONE was added, pinned in tests/test_cr047_assets_rules.py)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — PRM-04's RULES THAT RAN table and the runner are P6/WFL, another lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr023_import_stages.py · pytest tests/test_cr047_assets_rules.py (RED first: 'flagged'/'staged' == 'rejected') · golden 33/33 · run_gates no new failure (DEF-2516's pre-existing set unchanged)
# exceptions: platform rule SENTENCES are English prose rather than message_keys — the ratified custom_field.label exception (B2 r17.5 #1), because a tier-3 sentence is tenant prose with no key; the RULES THAT RAN table therefore does not localise, REPORTED · r10's `Default to Residential` action is deliberately NOT shipped (OQ-329) · `target=units` has no catalog here (B15 §17 P8) and stage 1 refuses it by name
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
