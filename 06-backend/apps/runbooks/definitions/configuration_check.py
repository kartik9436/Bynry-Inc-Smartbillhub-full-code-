# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-001 (EP-RBS-01) — CR-075 wave C task C5: runbook 1,
#           *Can we bill?* — ten steps, one verdict per enabled service, rolled
#           up to a tenant verdict.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no ports) · BR-RBS-010
#           (every record states the rule that decided it, in words a clerk can
#           read) · BR-RBS-011 (a failure names its fix route; one without a
#           route is a defect in the runbook) · BR-RBS-019 (the declared unit of
#           work) · BR-RBS-020 (the report is composed at close and frozen) ·
#           BR-RBS-021 (twelve blocks) · BR-RBS-023 (a step declares its mode) ·
#           BR-RBS-024 (one category from the fixed sixteen) · BR-RBS-039 (every
#           foreign read through a seam this module owns) ·
#           01-overview.md §8.1 (the per-service rollup) · B14 rules 31 and 32
# Tests:    06-backend/tests/test_us_rbs_001_configuration_check.py
#           (TC-RBS-14, TC-RBS-16, the blockers fixture, the rollup)
# Impacts:  apps/runbooks/definitions/__init__.py (the one line that registers
#           it) · apps/runbooks/seams/*.py (the reads it makes)
# ───────────────────────────────────────────────────────
"""Runbook 1 — **Can we bill?**

Ten read steps over a tenant's configuration graph, producing **one verdict per
enabled service and a tenant verdict that is the worst of them**
(`01-overview.md` §8.1). It is the first runbook this product ships and the one
runbooks 2 and 3 call through `requires`.

⚠ **IT IS A CHECK, SO IT DECLARES NO PORTS AT ALL** (`BR-RBS-002`). Not an
empty allow-list it is trusted not to use — none. `RunbookDefinition` refuses a
Check that declares one at CONSTRUCTION, which is the import
`AppConfig.ready()` performs, so a lane that adds a writer here stops the
process from starting rather than discovering it on a Tuesday. Findings become
work items when the run closes and **the engine writes those** (`BR-RBS-022`);
that is the whole reason a two-person utility can press **Run ▶** on a thousand
accounts.

WHAT EACH STEP IS ALLOWED TO CONCLUDE
--------------------------------------
Every finding carries a **weight** and a **fix route**, and neither is optional:

* `BLOCKER` — billing cannot proceed. It reddens its service, and any blocker
  anywhere makes the tenant verdict **No-go**.
* `WARNING` — billing proceeds and something is wrong. Warnings alone make the
  verdict **Warn**, never **No-go**.

⚠ **A FINDING WITH NO FIX ROUTE CANNOT BE CONSTRUCTED** (`BR-RBS-011`,
`TC-RBS-14`). `Finding.__post_init__` refuses one, and a static scan over this
package refuses one in a branch no fixture reaches — because the runtime half
can only ever see the branches a test happens to walk, and the branch that
matters is the one nobody has hit yet.

THE THREE PLACES THIS RUNBOOK DIVERGES FROM ITS OWN CARD, EACH STAMPED
-----------------------------------------------------------------------
`RB-101` is the card and it is the source. Where this file departs from it, the
reason is written here rather than left for a reader to spot:

1. **Six report blocks, not the card's four.** The card lists *KPIs · Chain ·
   Records · Downloads*. `01-overview.md` §8.1 decided the per-service rollup
   AFTER that card was written and says in its own words how it is drawn — *the
   `Verdict` block draws the tenant verdict; the per-service verdicts are a
   `Breakdown` block* — both already among the twelve, so `BR-RBS-021` is
   untouched and no thirteenth block is minted.
2. **All ten steps are `set` mode**, where the card's summary line reads *set ·
   per record*. `14-step-library.md` §7 enumerates all ten of this runbook's
   steps individually and marks every one `read · set`; the subject is the
   TENANT and `resolve()` returns exactly one subject, so a per-record step
   would run once and mean the same thing with an extra savepoint. The
   enumeration is the finer statement and it wins.
3. **`Usage to cover` offers one choice, not the card's *Highest seen, 12
   months*.** That value needs a maximum over twelve months of consumption per
   service, and **`metering` publishes no such read** — it is `S-14` in
   `13-selector-inventory.md`, ABSENT, owned by `metering`, first needed here.
   Step 5 therefore checks a fact the ladder itself states — `BR-RAT-032` makes
   the last tier's `to_qty` NULL, so a ladder whose top block carries a NUMBER
   stops somewhere and usage above it cannot be priced at all — and **says in
   its own output which comparison it did not make**. A dropdown offering a
   value the code cannot honour would be worse than a dropdown of one.

WHY THIS RUNBOOK DECLARES NO TENANT-DATA INPUT, AND WHY *ALL* IS SAFE HERE
---------------------------------------------------------------------------
`BR-RBS-042` (PO ruling 2026-09-06, CONFIRMED) makes a runbook **one fixed
process with declared inputs**, each carrying a **domain resolved per tenant**,
from which a tenant picks one value, several, or ***all*** — and **clause 1
says *all* is stored as the word and resolved at RUN START, never expanded at
configure time**, because a utility that picks *all services* with two and later
adds a third must get **three** on the next run.

Runbook 1's card settles the first half: its scope panel is headed **Scope
decided for you** and every row is a value rather than a control — *Covers:
whole utility · Services: the ones you sell · As at: today*. **So it declares no
input drawn from tenant data at all**, and its two `enum` parameters carry
domains that are the runbook's own fixed vocabulary rather than the tenant's.

The second half is satisfied **structurally rather than by a setting**, which is
worth stating because it is easy to read this file and conclude the rule does not
apply. The service list is *all*, permanently — and it is read by
`tenancy_seam.enabled_services()` **when the run starts**, once, and never stored
on the definition. A tenant that enables Trash tomorrow gets a third service
verdict on its next run with nothing to reconfigure, which is clause 1's own
worked example. `test_us_rbs_001_a_service_enabled_after_a_run_appears_in_the_next_one`
is the test `BR-RBS-042` records as owed, discharged for this runbook.

⚠ **WHAT WOULD MAKE THIS RUNBOOK PASS WRONGLY, ANSWERED IN WRITING** (hard-won
law 7's second habit). A Check that cannot read something must not report it
clean — that is `G32`'s shape, which reported `0 unresolved` truthfully over 21
live refusals. So every step here returns a `checked` mapping beside its
findings, saying **how many things it looked at**, and the report's KPI strip
draws the checked counts next to the found ones. An estate with no premises and
an estate whose premises are all correct produce different numbers, and a reader
can tell them apart. Where a step genuinely cannot answer a half of its card
question, it names that half in `checked` rather than staying silent — steps 2,
5 and 9 each do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_SET,
    Finding as WorkItemFinding,
    PARAM_ENUM,
    PARAM_TOGGLE,
    Block,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import (
    billing_seam,
    customers_seam,
    ledger_seam,
    metering_seam,
    notifications_seam,
    payments_seam,
    rating_seam,
    tenancy_seam,
)

# ── the two weights, and the three verdicts they roll up to ───────────────

BLOCKER = "blocker"
WARNING = "warning"

#: The one basis that is MEASURED. `share` (sewer — a percentage of another
#: service's money, `BR-RAT-015`) and `capacity` (trash and fire — the size
#: class picks the price and the COUNT multiplies it) are priced without a
#: reading, so neither has a unit and neither takes a meter. Named here rather
#: than imported: `apps.tenancy.models.BILLING_BASIS_METERED` is another
#: module's constant and importing it is what `G115` refuses (`BR-RBS-039`) —
#: the VALUE crosses the seam, never the name.
BASIS_METERED = "metered"

VERDICT_GO = "go"
VERDICT_WARN = "warn"
VERDICT_NO_GO = "no_go"

#: Worst-wins, and the order is the whole rollup rule (`01-overview.md` §8.1).
_VERDICT_RANK = {VERDICT_GO: 0, VERDICT_WARN: 1, VERDICT_NO_GO: 2}
_WEIGHT_VERDICT = {WARNING: VERDICT_WARN, BLOCKER: VERDICT_NO_GO}

# ── the fix routes ────────────────────────────────────────────────────────
#
# ⚠ **EVERY ONE IS A PATH THIS PRODUCT ACTUALLY MOUNTS, VERIFIED AGAINST
# `07-frontend/src/App.tsx` ON 2026-09-06.** A fix route that resolves to
# nothing is a dead button over a live finding — hard-won law 2's mirror, the
# shape that left the customer portal with two working doors out of eight — and
# nothing in the backend suite can see it, because a string is a string.
#
# They are TENANT-RELATIVE, exactly like `tenancy.selectors.CHECKLIST_TARGETS`,
# which is this product's existing convention for a deep link the server
# supplies: the shell prefixes `/:tenant/`. Reusing that shape rather than
# inventing a second one means one answer to *what does a server-side link look
# like* instead of two that can drift.

FIX_SERVICES = "settings/services"
FIX_NUMBER_SERIES = "settings/number-series"
FIX_REFERENCE_DATA = "settings/reference-data"
FIX_TEMPLATES = "settings/templates"
FIX_PLANS_RATES = "plans-rates"
FIX_ACCOUNTS = "accounts"
FIX_UNITS = "premises/units"
FIX_ASSETS = "assets"
FIX_READS = "reads"
FIX_CYCLES = "reads/cycles"
FIX_FINANCE = "finance"


@dataclass(frozen=True)
class Finding:
    """One thing wrong, in words a clerk can read, with the screen that fixes it.

    ⚠ **`fix_route` IS REQUIRED AND IS CHECKED TWICE** (`BR-RBS-011`,
    `TC-RBS-14`). Once here, at construction, so a finding built in a branch a
    test walks cannot escape without one; and once statically, over this whole
    package, so a finding built in a branch **no test walks** cannot either. The
    second check is the one that matters: a fixture exercises the faults somebody
    thought of.

    ⚠ **`decided_by_rule` IS A SENTENCE AND NEVER A RULE ID.** `BR-RBS-010` asks
    for *the rule that decided it, in words a clerk can read*, and B14 rule 32
    keeps rule ids and internal codes out of clerk-facing copy altogether. The
    id belongs in this file's docstrings, where an engineer reads it.

    ⚠ **NO FIELD HERE CARRIES A DATABASE ID** (B14 rule 31). `affects` is a
    count and a noun — *"240 accounts"* — because that is what a clerk can act
    on; an id would be a value they can neither read nor use.
    """

    step: str
    reason: str
    affects: str
    weight: str
    fix_route: str
    fix_label: str
    decided_by_rule: str
    #: `None` for a finding about the tenant rather than about one service —
    #: the reference data, the account chain, the read window. §8.1's three
    #: tenant-wide steps produce exactly these.
    service: str | None = None

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("a finding with no reason says nothing to anybody")
        if not self.fix_route.strip():
            raise ValueError(
                f"finding {self.reason!r} names no fix route. BR-RBS-011: a failure names its "
                "fix route, and a failure with no route is a defect in the runbook — a clerk "
                "reads what is wrong and has nowhere to go."
            )
        if not self.fix_label.strip():
            raise ValueError(f"finding {self.reason!r} has a route and no words on the button")
        if self.weight not in (BLOCKER, WARNING):
            raise ValueError(f"finding {self.reason!r} carries weight {self.weight!r}")

    def as_row(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "service": self.service,
            "finding": self.reason,
            "affects": self.affects,
            "weight": self.weight,
            "fix_route": self.fix_route,
            "fix_label": self.fix_label,
            "decided_by_rule": self.decided_by_rule,
        }


@dataclass
class _StepResult:
    """What every step returns — findings, and what it actually looked at.

    `checked` is not decoration. A step that reports no findings over an empty
    estate and a step that reports none over a correct one are the same sentence
    with very different meanings, and a check whose output cannot tell a reader
    which is which is worse than no check at all (hard-won law 7).
    """

    findings: list[Finding] = field(default_factory=list)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "findings": [finding.as_row() for finding in self.findings],
            "checked": dict(self.checked),
        }


# ── the ten steps ─────────────────────────────────────────────────────────
#
# Each is `run(ctx, subjects)` because all ten are `set` mode: they run ONCE
# over the pinned set, which for this runbook is the single tenant subject.
# `ctx.set_results` carries what an earlier step computed, so the enabled
# service list is read once by step 1 and used by the six later steps that are
# per-service — one answer to *which services does this tenant sell*, not seven.

STEP_SERVICES = "services_and_units"
STEP_REFERENCE = "reference_data"
STEP_TAX = "tax"
STEP_PLANS = "plans_in_force"
STEP_RATES = "rate_coverage"
STEP_CHAIN = "account_chain"
STEP_METERS = "meters"
STEP_READS = "reads_and_windows"
STEP_DOCUMENTS = "documents"
STEP_BOOKS = "books"

#: §8.1, written out so two implementations cannot disagree: *"Steps 1, 3, 4, 5,
#: 7, 9 and 10 are per-service; steps 2, 6 and 8 are tenant-wide (reference
#: data; the account → unit → premise → address chain; the read window)."*
PER_SERVICE_STEPS = (
    STEP_SERVICES,
    STEP_TAX,
    STEP_PLANS,
    STEP_RATES,
    STEP_METERS,
    STEP_DOCUMENTS,
    STEP_BOOKS,
)
TENANT_WIDE_STEPS = (STEP_REFERENCE, STEP_CHAIN, STEP_READS)

#: The chain block draws one cell per step, in this order, and a clerk reads the
#: words rather than the keys.
STEP_LABELS = {
    STEP_SERVICES: "Services and units",
    STEP_REFERENCE: "Reference data",
    STEP_TAX: "Tax",
    STEP_PLANS: "Plans in force",
    STEP_RATES: "Rate coverage",
    STEP_CHAIN: "Account chain",
    STEP_METERS: "Meters",
    STEP_READS: "Reads and windows",
    STEP_DOCUMENTS: "Documents",
    STEP_BOOKS: "Books",
}


def _enabled_services(ctx) -> tuple[str, ...]:
    """The services step 1 found, read back by every per-service step after it.

    Read once and reused rather than re-read seven times: `tenancy` is asked
    which services this tenant sells exactly once per run, so a service enabled
    mid-run cannot appear in one step's answer and be missing from another's.
    That is `BR-RBS-009`'s pinning applied one level down, to a fact the scope
    itself is derived from.
    """
    result = ctx.set_results.get(STEP_SERVICES) or {}
    checked = result.get("checked") or {}
    return tuple(checked.get("services") or ())


def step_services_and_units(ctx, subjects) -> dict[str, Any]:
    """1 · Every enabled service has a unit and a basis.

    ⚠ **THE BASIS DECIDES WHETHER A UNIT IS EVEN MEANINGFUL, AND THERE ARE
    THREE OF THEM** (`BR-TEN-1180`, 2026-09-02). Only a `metered` service is
    measured. A `share` service is a percentage of another service's money
    (`BR-RAT-015` — sewer, drawn as an em-dash in both unit columns on r10) and
    a `capacity` service is COUNTED rather than measured (trash and fire, where
    the size class picks the price and the count multiplies it). Neither has a
    unit, by design.

    ⚠ **THIS STEP HAS PRODUCED A FALSE BLOCKER TWICE IN ITS OWN BUILD AND BOTH
    ARE WORTH THE PARAGRAPH.** The first read a NULL BILLING unit as a gap and
    reddened both services of every freshly provisioned tenant; the second asked
    the retired two-state question *is it metered* and reddened **sewer at every
    utility that sells it**. Neither was caught by a test — both were caught by
    running the runbook and reading its output (hard-won law 6). A Check that
    reddens a correct utility is worse than no Check: the first thing it teaches
    is that its findings can be ignored.
    """
    result = _StepResult()
    rows = tenancy_seam.service_basis()
    result.checked = {
        "services": [str(row["service"]) for row in rows],
        "count": len(rows),
        "bases": sorted({str(row.get("billing_basis")) for row in rows}),
    }
    for row in rows:
        code = str(row["service"])
        basis = row.get("billing_basis")
        if basis != BASIS_METERED:
            # A share or a capacity service is priced without a reading. There
            # is nothing here to be missing, so there is nothing to report.
            continue
        if not row.get("primary_uom"):
            result.findings.append(
                Finding(
                    step=STEP_SERVICES,
                    service=code,
                    reason="This service is read off a meter and says nothing about its unit.",
                    affects="Every meter on this service",
                    weight=BLOCKER,
                    fix_route=FIX_SERVICES,
                    fix_label="Set a unit",
                    decided_by_rule=(
                        "A service read off a meter must say what it is measured in before "
                        "a reading means anything."
                    ),
                )
            )
        elif _needs_a_conversion(row):
            result.findings.append(
                Finding(
                    step=STEP_SERVICES,
                    service=code,
                    reason=(
                        f"This service is read in {row.get('primary_uom')} and billed in "
                        f"{row.get('billed_uom')}, with nothing saying how to convert."
                    ),
                    affects="Every bill line on this service",
                    weight=BLOCKER,
                    fix_route=FIX_SERVICES,
                    fix_label="Set a conversion",
                    decided_by_rule=(
                        "Where the reading unit and the billing unit differ, the conversion "
                        "has to be written down — it is never guessed."
                    ),
                )
            )
    return result.as_dict()


def _needs_a_conversion(row) -> bool:
    """The two units DIFFER and no factor is on file — `OQ-004`, *no silent conversion*.

    ⚠ **A NULL BILLING UNIT IS NOT THIS FAULT AND IS NOT ANY FAULT.**
    `tenancy.selectors.service_billed_uoms` states it, and `service_row` repeats
    it so the two cannot contradict each other: NULL means *the register's own
    unit is what is billed*. The first draft of this step read a NULL as a gap
    and reported a blocker on **both services of a freshly provisioned
    tenant** — every utility, on its first day, told that billing was stopped by
    something that was configured correctly.
    """
    billed = row.get("billed_uom")
    if not billed:
        return False
    if billed == row.get("primary_uom"):
        return False
    return not row.get("conversion_factor")


def step_reference_data(ctx, subjects) -> dict[str, Any]:
    """2 · Number series, holidays and account types are present. **Tenant-wide.**

    ⚠ **THIS STEP CHECKED TWO OF THE CARD'S THREE THINGS UNTIL 2026-09-17 AND
    NOW CHECKS ALL THREE.** It used to say, in `checked` rather than in a
    silence: *"platform data — no tenant-scoped read exists, and nothing here
    can differ per tenant"*. That was true — `account_types` was a PLATFORM
    table, seeded by migration `0003` and identical for every utility — and the
    PO reversed it (*"utility can get their own account types"*,
    `BR-CUS-1079`). The rows are the utility's now, so **there IS something a
    tenant can get wrong**: switch every category off, or leave only legacy
    ones, and no account can be created at all. A declared blind spot that has
    stopped being blind is worse than one that never was, because it goes on
    reading like a considered exclusion.
    """
    result = _StepResult()
    series = tenancy_seam.number_series()
    holidays = tenancy_seam.holiday_calendar()
    types = customers_seam.account_type_counts()
    result.checked = {
        "number_series": len(series),
        "holidays": len(holidays),
        "account_types": types,
    }
    if not types["selectable"]:
        result.findings.append(
            Finding(
                step=STEP_REFERENCE,
                reason=(
                    "No customer category can be picked, so no account can be created."
                    if types["total"]
                    else "There are no customer categories, so no account can be created."
                ),
                affects="Every new account",
                weight=BLOCKER,
                fix_route=FIX_REFERENCE_DATA,
                fix_label="Add a customer category",
                decided_by_rule=(
                    "Every account carries a customer category, so at least one has to "
                    "be switched on for a clerk to open one."
                ),
            )
        )
    if not series:
        result.findings.append(
            Finding(
                step=STEP_REFERENCE,
                reason="No number series exists, so nothing can be numbered.",
                affects="Every bill, account and receipt",
                weight=BLOCKER,
                fix_route=FIX_NUMBER_SERIES,
                fix_label="Add a number series",
                decided_by_rule="A bill takes its number from a series, and no series means no bill.",
            )
        )
    if not holidays:
        result.findings.append(
            Finding(
                step=STEP_REFERENCE,
                reason="No holidays are entered, so dates can land on days you are shut.",
                affects="Due dates and read windows",
                weight=WARNING,
                fix_route=FIX_REFERENCE_DATA,
                fix_label="Add your holidays",
                decided_by_rule="Due dates move off a holiday only when the calendar knows about it.",
            )
        )
    return result.as_dict()


def step_tax(ctx, subjects) -> dict[str, Any]:
    """3 · A tax region on every service point.

    ⚠ **TWO DIFFERENT FAULTS AND THIS STEP KEEPS THEM APART.** No authority at
    all is a **blocker**: nothing can attach, so every bill goes out untaxed and
    the product says nothing. An authority with **no price** is a **warning**,
    because a rate-less scaffold is a correct state — a utility that genuinely
    charges no tax reads the same notice and does nothing — and inventing a rate
    charges real customers real money (decision log 2026-08-28).
    """
    result = _StepResult()
    regions = rating_seam.tax_regions()
    census = metering_seam.census()
    services = _enabled_services(ctx)
    result.checked = {
        "authorities": regions.get("jurisdictions", 0),
        "priced": regions.get("priced", 0),
        "premises": census.get("premises", 0),
        "units": census.get("units", 0),
    }
    affects = f"{census.get('units', 0)} units across {census.get('premises', 0)} premises"
    if not regions.get("jurisdictions"):
        for code in services:
            result.findings.append(
                Finding(
                    step=STEP_TAX,
                    service=code,
                    reason="No tax region is set, so nothing on this service can be taxed.",
                    affects=affects,
                    weight=BLOCKER,
                    fix_route=FIX_PLANS_RATES,
                    fix_label="Set a tax region",
                    decided_by_rule="Tax attaches to a property through a region, and there is none.",
                )
            )
    elif not regions.get("priced"):
        for code in services:
            result.findings.append(
                Finding(
                    step=STEP_TAX,
                    service=code,
                    reason="A tax region exists and carries no rate, so bills go out untaxed.",
                    affects=affects,
                    weight=WARNING,
                    fix_route=FIX_PLANS_RATES,
                    fix_label="Price the tax",
                    decided_by_rule="A region with no rate charges nothing, which may be right for you.",
                )
            )
    return result.as_dict()


def step_plans_in_force(ctx, subjects) -> dict[str, Any]:
    """4 · Every plan has a version covering today.

    A plan whose tariff has no version in force on the run date prices nothing:
    `BR-RAT-007` resolves the version by the SERVICE date and refuses a draft,
    so the gap is silent until a bill run meets it.
    """
    result = _StepResult()
    coverage = rating_seam.plan_coverage(_as_at(ctx))
    result.checked = {"plan_services": len(coverage)}
    for row in coverage:
        if row.get("has_version_in_force"):
            continue
        result.findings.append(
            Finding(
                step=STEP_PLANS,
                service=str(row.get("service_code")),
                reason=f"{row.get('plan_name')} has no rate version covering today.",
                affects="Every account on this plan",
                weight=BLOCKER,
                fix_route=FIX_PLANS_RATES,
                fix_label="Activate a version",
                decided_by_rule="A plan prices from the version in force on the service date.",
            )
        )
    return result.as_dict()


def step_rate_coverage(ctx, subjects) -> dict[str, Any]:
    """5 · Blocks cover zero to the highest usage seen.

    ⚠ **WHAT THIS CHECKS AND WHAT IT CANNOT, STATED IN ITS OWN OUTPUT.**
    `BR-RAT-032` makes the last tier of a ladder unbounded — a flat tariff is a
    single `0 → ∞` row — so a top block carrying a NUMBER is a ladder that stops,
    and usage above it can be priced by nobody. That is a fact about the ladder
    and it is what this step reports.

    The comparison the card asks for — *the highest usage seen in twelve months*
    — needs a maximum over consumption per service, and **`metering` publishes
    no such read**: it is `S-14` in `13-selector-inventory.md`, ABSENT, owned by
    `metering`, and this is the wave that first needs it. `checked` says so on
    every run rather than leaving a reader to assume the comparison was made.
    """
    result = _StepResult()
    coverage = rating_seam.plan_coverage(_as_at(ctx))
    result.checked = {
        "ladders": len(coverage),
        "usage_comparison": (
            "not made — nothing reads the highest usage seen, so a ladder that stops above "
            "today's highest reading still reads as bounded"
        ),
    }
    for row in coverage:
        if not row.get("has_version_in_force"):
            continue  # step 4 already reported it; one fault, one finding.
        if row.get("tier_count") and row.get("top_block_to") is not None:
            unit = row.get("unit") or "units"
            result.findings.append(
                Finding(
                    step=STEP_RATES,
                    service=str(row.get("service_code")),
                    reason=(
                        f"{row.get('plan_name')} has no block above "
                        f"{_quantity(row.get('top_block_to'))} {unit}."
                    ),
                    affects="Any account using more than that",
                    weight=BLOCKER,
                    fix_route=FIX_PLANS_RATES,
                    fix_label="Add a block",
                    decided_by_rule="The last block runs to no limit, or usage above it prices at nothing.",
                )
            )
    return result.as_dict()


def step_account_chain(ctx, subjects) -> dict[str, Any]:
    """6 · Account → unit → premise → address, unbroken. **Tenant-wide.**

    ⚠ **A MASTER ACCOUNT NAMES NO UNIT AND THAT IS LAWFUL** (`BR-CUS-1010`): it
    is the owner's account at an ADDRESS, so it hangs off the premises. A check
    that read *no unit* as *broken* would report every master account in the
    product as a blocker. What is broken is an account that reaches **no
    premises at all** — through its unit or directly — because an address is
    stored on `premises` and nowhere else (hard rule 8, `BR-MET-1161`), so an
    account that cannot walk there has no address, and nobody can bill it or
    post to it.
    """
    result = _StepResult()
    anchors = customers_seam.account_anchors()
    resolved = metering_seam.resolve_anchors(
        [a["unit_id"] for a in anchors if a["unit_id"]],
        [a["premises_id"] for a in anchors if a["premises_id"]],
    )
    units = resolved["units"]
    premises = resolved["premises"]
    broken: list[str] = []
    for anchor in anchors:
        unit = units.get(anchor["unit_id"]) if anchor["unit_id"] else None
        if unit is not None and unit.get("premises_id"):
            continue
        if anchor["premises_id"] and anchor["premises_id"] in premises:
            continue
        broken.append(str(anchor["account_no"]))
    result.checked = {"accounts": len(anchors), "broken": len(broken)}
    if broken:
        result.findings.append(
            Finding(
                step=STEP_CHAIN,
                reason=f"{len(broken)} accounts do not reach a property.",
                affects=f"{len(broken)} accounts",
                weight=BLOCKER,
                fix_route=FIX_ACCOUNTS,
                fix_label="Match units",
                decided_by_rule="An account is billed at an address, and the address lives on the property.",
            )
        )
    return result.as_dict()


def step_meters(ctx, subjects) -> dict[str, Any]:
    """7 · Every metered unit has a meter, a multiplier and a unit.

    ⚠ **THE MULTIPLIER IS ASKED ONLY WHERE A READ EXISTS**, because `metering`
    answers *the multiplier this connection's reads were computed with* — so on
    a meter with no read the answer is `None` for a reason that is step 8's, not
    this step's. Asking it anyway would report every unread meter twice, under
    two different fixes, and a clerk would fix neither.
    """
    result = _StepResult()
    graph = metering_seam.service_point_graph()
    metered = {
        str(row["service"])
        for row in tenancy_seam.service_basis()
        if row.get("billing_basis") == BASIS_METERED
    }
    missing_meter: dict[str, int] = {}
    missing_multiplier: dict[str, int] = {}
    points_checked = 0
    for unit in graph:
        assets_by_service: dict[str, list[dict[str, Any]]] = {}
        for asset in unit["assets"]:
            assets_by_service.setdefault(str(asset.get("service")), []).append(asset)
        for point in unit["points"]:
            service = str(point.get("service"))
            if service not in metered:
                # A share or capacity service takes no meter at all, so a
                # service point without one is the correct shape rather than a
                # gap (`BR-TEN-1180`: three bases, not a boolean).
                continue
            points_checked += 1
            meters = assets_by_service.get(service) or []
            if not meters:
                missing_meter[service] = missing_meter.get(service, 0) + 1
                continue
            if not any(meter.get("last_read") for meter in meters):
                continue  # step 8's finding, not this one's.
            if metering_seam.multiplier_for(unit["unit_id"], service) is None:
                missing_multiplier[service] = missing_multiplier.get(service, 0) + 1
    result.checked = {"service_points": points_checked, "units": len(graph)}
    for service, count in sorted(missing_meter.items()):
        result.findings.append(
            Finding(
                step=STEP_METERS,
                service=service,
                reason=f"{count} places take this service and have no meter.",
                affects=f"{count} service points",
                weight=BLOCKER,
                fix_route=FIX_ASSETS,
                fix_label="Add a meter",
                decided_by_rule="A metered service is billed off a meter, and there is none here.",
            )
        )
    for service, count in sorted(missing_multiplier.items()):
        result.findings.append(
            Finding(
                step=STEP_METERS,
                service=service,
                reason=f"{count} meters are read without a multiplier.",
                affects=f"{count} meters",
                weight=WARNING,
                fix_route=FIX_ASSETS,
                fix_label="Set a multiplier",
                decided_by_rule="A read is turned into usage by the meter's multiplier.",
            )
        )
    return result.as_dict()


def step_reads_and_windows(ctx, subjects) -> dict[str, Any]:
    """8 · One read per meter, and the read window closes before bill day.
    **Tenant-wide.**

    The window comes from the tenant's own cycle — `start_day` plus
    `days_to_complete` IS the read window (B17 §2) — so the comparison is
    against what the utility configured and never against a number this module
    chose.
    """
    result = _StepResult()
    graph = metering_seam.service_point_graph()
    cycles = metering_seam.cycles()
    unread = 0
    meters = 0
    for unit in graph:
        for asset in unit["assets"]:
            if not asset.get("service"):
                continue
            meters += 1
            if not asset.get("last_read"):
                unread += 1
    late_windows = [
        cycle
        for cycle in cycles
        if _closes_after_bill_day(cycle.get("start_day"), cycle.get("days_to_complete"), cycle.get("bill_day"))
    ]
    result.checked = {"meters": meters, "unread": unread, "cycles": len(cycles)}
    if unread:
        result.findings.append(
            Finding(
                step=STEP_READS,
                reason=f"{unread} meters have never been read.",
                affects=f"{unread} meters",
                weight=BLOCKER,
                fix_route=FIX_READS,
                fix_label="Import history",
                decided_by_rule="Usage is the difference between two readings, and there is not one yet.",
            )
        )
    for cycle in late_windows:
        result.findings.append(
            Finding(
                step=STEP_READS,
                reason=f"The {cycle.get('name')} reading window closes after its bill day.",
                affects="Every account on this cycle",
                weight=WARNING,
                fix_route=FIX_CYCLES,
                fix_label="Move the window",
                decided_by_rule="Reading has to finish before the bills go out, or they go out estimated.",
            )
        )
    return result.as_dict()


def step_documents(ctx, subjects) -> dict[str, Any]:
    """9 · A bill template and a notice template exist for every service.

    ⚠ **THIS PRODUCT HOLDS TEMPLATES PER TENANT, NOT PER SERVICE**, so the
    card's *"No Spanish bill template · Water · Sewer"* cannot be answered as
    written: `bill_templates` is chosen by consumer category and language, and a
    notice template by its code. What can be answered — and what stops a bill —
    is whether the tenant has a PUBLISHED bill layout at all, and whether any
    notice template is published. The finding is attached to every enabled
    service because a missing layout stops all of them, and `checked` states
    that no per-service or per-language comparison was made.
    """
    result = _StepResult()
    services = _enabled_services(ctx)
    has_bill = billing_seam.has_published_bill_template()
    notices = notifications_seam.published_notice_templates()
    result.checked = {
        "published_bill_template": has_bill,
        "published_notice_templates": notices,
        "per_language": "not checked — a template's language set is not read here",
    }
    if not has_bill:
        for code in services:
            result.findings.append(
                Finding(
                    step=STEP_DOCUMENTS,
                    service=code,
                    reason="No published bill layout, so a bill has nothing to print on.",
                    affects="Every bill",
                    weight=BLOCKER,
                    fix_route=FIX_TEMPLATES,
                    fix_label="Publish a layout",
                    decided_by_rule="A bill is printed on a published layout, and a draft is not one.",
                )
            )
    if not notices:
        result.findings.append(
            Finding(
                step=STEP_DOCUMENTS,
                reason="No published notice template, so reminders have no wording.",
                affects="Every reminder and notice",
                weight=WARNING,
                fix_route=FIX_TEMPLATES,
                fix_label="Add a template",
                decided_by_rule="A notice is sent from a published template.",
            )
        )
    return result.as_dict()


def step_books(ctx, subjects) -> dict[str, Any]:
    """10 · Every charge code and tender maps to an account.

    A revenue line with no account is refused at issue, BY NAME — so the refusal
    arrives on bill day, in front of a clerk who cannot fix it in the minute they
    have. That is precisely the class of fault this runbook exists to move
    forward in time.
    """
    result = _StepResult()
    services = _enabled_services(ctx)
    tenders = payments_seam.active_tenders()
    unmapped = ledger_seam.unmapped_designations()
    without_revenue = [code for code in services if ledger_seam.revenue_account_for(code) is None]
    result.checked = {
        "services": len(services),
        "tenders": len(tenders),
        "unmapped_designations": len(unmapped),
    }
    for code in without_revenue:
        result.findings.append(
            Finding(
                step=STEP_BOOKS,
                service=code,
                reason="This service has no revenue account, so its bill lines cannot post.",
                affects="Every bill line on this service",
                weight=BLOCKER,
                fix_route=FIX_FINANCE,
                fix_label="Map an account",
                decided_by_rule="Every line posted to the books names the account it lands in.",
            )
        )
    if not tenders:
        result.findings.append(
            Finding(
                step=STEP_BOOKS,
                reason="No live way to take a payment, so nothing can be receipted.",
                affects="Every payment",
                weight=BLOCKER,
                fix_route=FIX_REFERENCE_DATA,
                fix_label="Add a tender",
                decided_by_rule="A payment is recorded against a tender, and every one is retired.",
            )
        )
    if unmapped:
        result.findings.append(
            Finding(
                step=STEP_BOOKS,
                reason=f"{len(unmapped)} places in the books have no account behind them.",
                affects=f"{len(unmapped)} of the eleven",
                weight=WARNING,
                fix_route=FIX_FINANCE,
                fix_label="Finish the mapping",
                decided_by_rule="Each kind of posting names its own account before it is used.",
            )
        )
    return result.as_dict()


# ── the small helpers the steps share ─────────────────────────────────────


def _as_at(ctx):
    """The date this run prices against — *As at: Today* on the setup card.

    Through the seam, like every other foreign read: `G115` refused the direct
    import by file and line, and it was right to (see `tenancy_seam.today`).
    """
    return tenancy_seam.today()


def _quantity(value) -> str:
    """A quantity, at most two decimals, trailing zeros TRIMMED (`BR-MET-144`).

    ⚠ **THE VALUE ARRIVES AS A SIX-PLACE STRING AND THAT IS THE WHOLE REASON
    THIS FUNCTION EXISTS.** `rating.selectors.version_structure` serves every
    tier bound through `_money`, which is STORAGE precision — so a block that
    stops at twenty thousand gallons arrives as `"20000.000000"`. Printed
    straight into a sentence it reads *"no block above 20000.000000 gal"*,
    which is `DEF-1121` word for word: a water tier read `0.000000 – 5.000000`
    on a live screen because three screens interpolated the same strings.

    A block bound is a QUANTITY, not money — at most 2dp with zeros TRIMMED
    (`BR-MET-144`), never money's 2dp with zeros KEPT (`BR-SHL-250`).
    """
    from decimal import Decimal, InvalidOperation

    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError):
        return str(value)
    text = f"{number:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def _closes_after_bill_day(start_day, days_to_complete, bill_day) -> bool:
    """Does the reading window still be open when the bills go out?

    All three are day-of-month numbers on the tenant's cycle. A window that runs
    past the bill day is a WARNING rather than a blocker: the bills still go out,
    they go out estimated, and a utility that has chosen to estimate is not
    misconfigured.
    """
    if start_day is None or days_to_complete is None or bill_day is None:
        return False
    return int(start_day) + int(days_to_complete) > int(bill_day)


# ── the rollup — one verdict per service, worst-wins ──────────────────────


def _verdict_from(weights) -> str:
    verdict = VERDICT_GO
    for weight in weights:
        candidate = _WEIGHT_VERDICT.get(weight, VERDICT_GO)
        if _VERDICT_RANK[candidate] > _VERDICT_RANK[verdict]:
            verdict = candidate
    return verdict


def _all_findings(set_results) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in STEP_LABELS:
        rows.extend((set_results.get(key) or {}).get("findings") or [])
    return rows


def rollup(set_results) -> dict[str, Any]:
    """`01-overview.md` §8.1, implemented once so two readers cannot disagree.

    **A service's verdict is the worst outcome among its own steps. The tenant
    verdict is the worst among the enabled services' verdicts and the
    tenant-wide steps.** Blocker anywhere → **No-go**. Warnings only → **Warn**.
    Nothing found → **Go**.

    ⚠ **A SERVICE WITH NOTHING WRONG IS STILL LISTED, AS `Go`.** That is the
    point of the whole decision: a two-service utility that fixes water watches
    Sewer stay red while Water goes green, and a screen that only listed the
    faulty services would show movement as a row disappearing — which reads like
    a bug rather than like progress.
    """
    services = tuple((set_results.get(STEP_SERVICES) or {}).get("checked", {}).get("services") or ())
    findings = _all_findings(set_results)
    per_service = {
        code: _verdict_from(
            row["weight"] for row in findings if row.get("service") == code
        )
        for code in services
    }
    tenant_wide = _verdict_from(row["weight"] for row in findings if row.get("service") is None)
    worst = tenant_wide
    for verdict in per_service.values():
        if _VERDICT_RANK[verdict] > _VERDICT_RANK[worst]:
            worst = verdict
    return {"tenant": worst, "services": per_service, "tenant_wide": tenant_wide}


def _headline(blockers: int) -> str:
    """The run header a clerk reads. Four words at most (B14 rule 33's spirit).

    No rule id and no internal code (B14 rule 32): *"3 things stop billing"* is
    the whole sentence, and the detail is one table below it.
    """
    if blockers == 0:
        return "Nothing stops billing"
    if blockers == 1:
        return "1 thing stops billing"
    return f"{blockers} things stop billing"


# ── what this run leaves on somebody's desk — CR-075 wave H, US-RBS-006 ───
#
# ⚠ **THE RUNBOOK RETURNS FINDINGS; THE ENGINE WRITES `work_items`**
# (`BR-RBS-022`). Runbook 1 is the first Check to declare this, and `J-RBS-1`'s
# last step is what it exists for: fix the tax region, re-run, and the item
# **closes itself** because this run no longer raises its fingerprint.

#: `Finding.weight` is an integer because `work_items.weight` is one, and a
#: screen turns it back into a word (B14 rule 32 — no internal code in clerk
#: copy). Two values because this runbook has two: **billing cannot proceed**
#: and **billing proceeds and something is wrong**.
WORK_ITEM_WEIGHT: dict[str, int] = {BLOCKER: 100, WARNING: 50}


def findings(view) -> list[WorkItemFinding]:
    """Every blocker and warning this run found, as work items.

    ⚠ **`kind` IS THE QUESTION THAT WAS ASKED, NOT THE ANSWER THAT CAME BACK** —
    the step and the service, never the sentence. `BR-RBS-017` makes the
    fingerprint what stops thirty daily sweeps becoming thirty rows, and a
    reworded `finding` string would otherwise mint a second item and reset the
    age a clerk reads to today. Step 3 on Water is one question whichever of its
    two answers comes back, and only one of them can be true at a time.

    ⚠ **A TENANT-WIDE FINDING CARRIES `-` FOR ITS SERVICE AND THAT IS A VALUE.**
    §8.1's three tenant-wide steps produce findings with `service = None`; the
    dash keeps them in one namespace with the per-service ones rather than
    letting *the reference data* and *water's reference data* collide.

    ⚠ **`subject_ref` IS `affects` — A COUNT AND A NOUN, NEVER AN ID.** *"240
    accounts"* is what a clerk can act on (B14 rule 31), and it is the same
    string the Records table already draws.
    """
    return [
        WorkItemFinding(
            kind=f"{row['step']}:{row.get('service') or '-'}",
            title=row["finding"],
            fix_route=row["fix_route"],
            weight=WORK_ITEM_WEIGHT.get(row["weight"], 0),
            subject_ref=row.get("affects") or "",
            # The subject of this whole runbook is the TENANT (`resolve()`
            # returns exactly one), so the fingerprint's subject part is the
            # word rather than an id — which the fingerprint already carries as
            # its first field.
            subject_type="tenant",
        )
        for row in _all_findings(view.set_results)
    ]


# ── the report — six of the twelve blocks, composed at close ──────────────
#
# ⚠ **EVERY PAYLOAD HERE IS THE RENDERER'S SHAPE, AND IT WAS NOT UNTIL
# `DEF-RBS-4284` (2026-09-06).** This function shipped with `C5` emitting six
# payloads of its own invention — `{"verdict", "headline"}`, `{"grouped_by"}`,
# `{"items"}`, bare string columns, and chain states `blocker`/`warning`/`clear`
# — while `C1b` built the eleven block components against
# `07-frontend/src/features/runbooks/blocks/types.ts`. **Not one of the six
# matched, and the chain's two state vocabularies had no value in common.**
#
# **BOTH SIDES WERE GREEN AND NEITHER WAS WRONG ON ITS OWN TERMS.** The only
# thing checked was the twelve NAMES: `blocks.test.tsx` reads `contract.py`'s
# `BLOCK_TYPES` and asserts the list matches name for name. Its own comment
# predicts this failure one level down — *"a report the backend accepts draws
# nothing on screen — and nothing else would say"* — and that is exactly what
# happened, because a name check over an unchecked payload is a declared blind
# spot with no number attached (hard-won law 7's fifth shape).
#
# **THE DIRECTION WAS ALREADY RULED AND IS NOT THIS LANE'S CHOICE.**
# `contract.py`'s `Block` docstring: *"`payload` is whatever that block draws
# and is deliberately untyped here: the twelve shapes are the renderer's (wave
# C) … What is typed is the NAME."* So the ENGINE moves to the renderer, never
# the other way. Nothing is migrated: no runbooks route is mounted yet, so no
# stored report exists to be re-shaped, and `BR-RBS-020`'s freeze is untouched.


def _verdict_word(verdict: str) -> str:
    """The clerk-facing word for a verdict.

    B14 rule 32 — no internal code in clerk-facing copy — so `no_go` never
    reaches a screen. `VerdictBand` draws this in a tone chip.
    """
    return {VERDICT_GO: "Go", VERDICT_WARN: "Warn", VERDICT_NO_GO: "No-go"}[verdict]


#: `VerdictTone` in `07-frontend/src/components/VerdictBand.tsx`. Three values,
#: and they are the shared kit's, not this module's.
_VERDICT_TONE = {VERDICT_GO: "success", VERDICT_WARN: "warning", VERDICT_NO_GO: "danger"}

#: `StatusTone` in `07-frontend/src/components/StatusPill.tsx`.
_WEIGHT_PILL = {
    BLOCKER: ("Blocks billing", "danger"),
    WARNING: ("Warning", "warning"),
}


def _chain_state(step_result) -> str:
    """One chain cell as `ChainCellState` — `ok` | `bad` | `notReached` | `pending`.

    ⚠ **A WARNING DOES NOT REDDEN THE CELL, AND THAT IS READ OFF THE FRAME
    RATHER THAN DECIDED HERE.** `wireframes/RBS-006-R1.png` draws cells 3, 5 and
    6 red — Tax, Rate coverage, Account chain, the three BLOCKERS — and draws 7,
    8 and 9 green, which are Meters, Reads and Documents: the three steps
    carrying this fixture's six WARNINGS. So a blocker is `bad` and everything
    else is `ok`. The warnings are not lost — the KPI strip counts them and the
    findings table lists them, both on the same screen.

    `notReached` is in the vocabulary and this runbook never emits it: a Check
    runs every step whatever the earlier ones found — stopping at the first would
    tell a clerk one thing to fix and hide the two behind it, and a utility would
    then run this three times instead of once. That is why a clerk gets all three
    blockers from one run.
    """
    weights = {row["weight"] for row in (step_result.get("findings") or [])}
    return "bad" if BLOCKER in weights else "ok"


def _chain_note(key: str, step_result) -> str | None:
    """What a chain cell says under its label.

    Two different jobs, and both are required by something. **A red cell NAMES
    the blocker** — `wireframes/RBS-006-R1.md` region 3, *"a red cell names the
    blocker"*, and `BR-RBS-027`. **A green cell says what it LOOKED AT**, which
    is where `checked` becomes visible to a reader: a step that found nothing
    over an empty estate and one that found nothing over a correct estate are
    the same sentence with very different meanings, and hard-won law 7 says a
    check whose output cannot tell a reader which is which is worse than none.
    """
    findings = step_result.get("findings") or []
    blockers = [row for row in findings if row["weight"] == BLOCKER]
    if blockers:
        return blockers[0]["finding"]
    checked = step_result.get("checked") or {}
    counts = [
        f"{value:,} {name.replace('_', ' ')}"
        for name, value in sorted(checked.items())
        if isinstance(value, int)
    ]
    return " · ".join(counts) if counts else None


def _finding_row(index: int, row: dict[str, Any]) -> dict[str, Any]:
    """One findings row as a `ReportRow`.

    Every cell carries its KIND, which is what lets twelve blocks draw
    thirty-four runbooks: the renderer picks `StatusPill` for a pill and a
    router link for a link without this module deciding anything about
    presentation. `id` is React's key and is NEVER drawn (B14 rule 31), so it is
    the row's position rather than any database id.
    """
    label, tone = _WEIGHT_PILL[row["weight"]]
    return {
        "id": f"f{index}",
        "cells": {
            "step": {"kind": "text", "text": STEP_LABELS[row["step"]]},
            "finding": {"kind": "text", "text": row["finding"]},
            "affects": {"kind": "text", "text": row["affects"]},
            "weight": {"kind": "pill", "label": label, "tone": tone},
            "fix": {"kind": "link", "label": row["fix_label"], "to": row["fix_route"]},
        },
        # ⚠ CARRIED, NEVER DRAWN — the renderer walks `columns`, so nothing here
        # can reach a screen. `decided_by_rule` MUST NOT: B14 rule 32 forbids a
        # rule id in clerk-facing copy. It is here because the findings CSV and
        # `TC-RBS-14` both read it, and the report is the only frozen artefact.
        "meta": {"service": row["service"], "decided_by_rule": row["decided_by_rule"]},
    }


def report(view) -> list[Block]:
    """Composed from records and counts at CLOSE, then frozen (`BR-RBS-020`).

    Six blocks, all from the twelve: `Verdict` · `KPIs` · `Chain` · `Breakdown`
    · `Records` · `Downloads`. The card names four; §8.1's rollup added the
    first and the fourth when it decided the per-service verdict, and it chose
    them precisely because both were already in the vocabulary — a thirteenth
    block needs three runbooks that cannot be drawn without it (`BR-RBS-021`).

    ⚠ **THE KPI STRIP IS THREE TILES AND THE BUILD SHEET DRAWS FOUR.** The
    fourth is *12s · Took*, and a duration is not a fact about the REPORT: the
    report is frozen at close and the elapsed time lives on the run row
    (`runbook_runs.started_at` / `finished_at`). The screen composes it from the
    run it is already holding. Stamped in `08-screen-layouts.md`, per the rule
    that where a sheet and a rule disagree the RULE wins and the divergence is
    written down.
    """
    set_results = dict(view.set_results)
    findings = _all_findings(set_results)
    verdicts = rollup(set_results)
    blockers = sum(1 for row in findings if row["weight"] == BLOCKER)
    warnings = sum(1 for row in findings if row["weight"] == WARNING)
    clear_steps = [
        key
        for key in STEP_LABELS
        if not ((set_results.get(key) or {}).get("findings") or [])
    ]
    return [
        Block(
            block="verdict",
            payload={
                "word": _verdict_word(verdicts["tenant"]),
                "tone": _VERDICT_TONE[verdicts["tenant"]],
                "count": _headline(blockers),
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "blockers",
                        "label": "Blockers",
                        "value": {"kind": "text", "text": str(blockers)},
                    },
                    {
                        "id": "warnings",
                        "label": "Warnings",
                        "value": {"kind": "text", "text": str(warnings)},
                    },
                    {
                        "id": "steps_clear",
                        "label": "Steps clear",
                        "value": {
                            "kind": "text",
                            "text": f"{len(clear_steps)} of {len(STEP_LABELS)}",
                        },
                    },
                ]
            },
        ),
        Block(
            block="chain",
            payload={
                "label": f"Ten steps, {blockers} stopped billing.",
                "cells": [
                    {
                        "id": key,
                        "position": index,
                        "label": STEP_LABELS[key],
                        "state": _chain_state(set_results.get(key) or {}),
                        "note": _chain_note(key, set_results.get(key) or {}),
                    }
                    for index, key in enumerate(STEP_LABELS, start=1)
                ],
            },
        ),
        Block(
            block="breakdown",
            payload={
                "heading": "By service",
                "columns": [
                    {"key": "service", "label": "Service"},
                    {"key": "verdict", "label": "Verdict"},
                ],
                "rows": [
                    {
                        "id": code,
                        "cells": {
                            "service": {"kind": "text", "text": code},
                            "verdict": {
                                "kind": "pill",
                                "label": _verdict_word(verdict),
                                "tone": _VERDICT_TONE[verdict],
                            },
                        },
                    }
                    for code, verdict in sorted(verdicts["services"].items())
                ],
            },
        ),
        Block(
            block="records",
            payload={
                "columns": [
                    {"key": "step", "label": "Step"},
                    {"key": "finding", "label": "Finding"},
                    {"key": "affects", "label": "Affects"},
                    {"key": "weight", "label": "Weight"},
                    {"key": "fix", "label": "Fix"},
                ],
                "rows": [_finding_row(index, row) for index, row in enumerate(findings, start=1)],
                "total": len(findings),
                "chips": [
                    {"id": "all", "label": "All", "count": len(findings)},
                    {"id": "blockers", "label": "Blockers", "count": blockers},
                    {"id": "warnings", "label": "Warnings", "count": warnings},
                ],
                # B14 rule 17's shape, and the words a clerk WANTS to see: a
                # Check that finds nothing is a good outcome rather than a gap,
                # which is why `RecordsPayload.empty` carries no call to action.
                "empty": {
                    "title": "Nothing stops billing.",
                    "helper": "Every step ran and found nothing to fix.",
                },
                # ⚠ CARRIED, NOT DRAWN — and it is REACHABLE, which is the whole
                # point. `checked` is what each step actually looked at, and it
                # reaches a reader through the chain cells' notes above
                # (`_chain_note`). It stays in the payload because a downstream
                # reader — the findings CSV, `TC-RBS-14`'s static scan — reads
                # it here, and because a step's evidence outliving its own cell
                # is what tells an empty estate from a correct one.
                "checked": {
                    key: (set_results.get(key) or {}).get("checked", {}) for key in STEP_LABELS
                },
            },
        ),
        Block(
            block="downloads",
            payload={"files": [{"id": "findings", "label": "Findings", "format": "csv"}]},
        ),
    ]


def resolve(ctx):
    """The pinned set: **one subject, the tenant** (`BR-RBS-019`).

    *Scope decided for you* — the card's own heading. There is nothing to pick:
    the runbook reads the tenant's enabled services and checks everything behind
    them, which is why `RBS-004`'s scope rows are values rather than controls.
    """
    tenant_id = ctx.tenant_id
    if tenant_id is None:
        from core import tenancy as core_tenancy

        tenant_id = core_tenancy.current_tenant_id()
    return [SubjectRef(subject_type="tenant", subject_id=str(tenant_id), label="This utility")]


def _step(key: str, run) -> Step:
    """One step, `set` mode, labelled from the one table the chain also reads.

    ⚠ **`mode` IS PASSED EXPLICITLY ON EVERY STEP AND THIS HELPER DOES NOT MAKE
    IT A DEFAULT.** `Step.mode` has no default on purpose (`BR-RBS-023`) — a
    default would decide it silently for every step a lane forgets — and a
    helper that supplied one would put the default back one layer up. It is
    written here once, for ten steps that genuinely all run once over the
    pinned set, and a step that needs the other mode is built with `Step(...)`
    directly rather than by widening this.
    """
    return Step(key=key, label=STEP_LABELS[key], mode=MODE_SET, run=run)


RUNBOOK = RunbookDefinition(
    key="configuration_check",
    name="Can we bill?",
    kind=models.KIND_CHECK,
    category="platform",
    subject_type="tenant",
    unit_of_work="config graph",
    triggers=(models.TRIGGER_MANUAL,),
    tags=("Plans & Rates", "Service points"),
    parameters=(
        Parameter(
            name="report",
            type=PARAM_ENUM,
            label="Report",
            required=True,
            default="blockers_and_warnings",
            choices=("blockers_and_warnings", "blockers_only"),
        ),
        Parameter(
            name="usage_to_cover",
            type=PARAM_ENUM,
            label="Usage to cover",
            required=True,
            default="ladder_is_unbounded",
            # ⚠ ONE CHOICE, AND THE CARD OFFERS *Highest seen, 12 months*. See
            # the module docstring, divergence 3: that value needs `S-14`, a
            # metering read that does not exist. A dropdown offering a value the
            # code cannot honour is worse than a dropdown of one.
            choices=("ladder_is_unbounded",),
        ),
        Parameter(
            name="include_held_accounts",
            type=PARAM_TOGGLE,
            label="Include held accounts",
            default=False,
        ),
        Parameter(
            name="raise_work_items",
            type=PARAM_TOGGLE,
            label="Raise work items",
            default=True,
        ),
    ),
    resolve=resolve,
    report=report,
    findings=findings,
    steps=(
        _step(STEP_SERVICES, step_services_and_units),
        _step(STEP_REFERENCE, step_reference_data),
        _step(STEP_TAX, step_tax),
        _step(STEP_PLANS, step_plans_in_force),
        _step(STEP_RATES, step_rate_coverage),
        _step(STEP_CHAIN, step_account_chain),
        _step(STEP_METERS, step_meters),
        _step(STEP_READS, step_reads_and_windows),
        _step(STEP_DOCUMENTS, step_documents),
        _step(STEP_BOOKS, step_books),
    ),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-001 (EP-RBS-01; CR-075 wave C task C5)
# generated: 2026-09-06 by the CR-075 wave C backend lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — the routes are wave D) E=n/a(no screen — the renderers are C1–C4, a sibling lane) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_001_configuration_check.py · pytest tests/test_us_rbs_015_conformance.py · G115 (the import census)
# exceptions: step 5 makes no highest-usage comparison (S-14, ABSENT, owned by metering) and says so in its own output; step 2 does not read account types (platform data, no tenant-scoped read); step 9 makes no per-service or per-language template comparison
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
