# ── Trace ──────────────────────────────────────────────
# Defects: DEF-2889 (R2's own narrowing drops a rate schedule version ONE DAY
#          early — R2 may not be switched on until it is closed) · DEF-2890 (the
#          mirror: R3 + R4 without R2 can stamp the chain's base onto the live
#          path's ladder) ·
#          DEF-438 (the R1–R7 chain has no production caller — this file is the
#          door that lets one rule at a time walk through it) · DEF-2550 (the
#          shadow's trailer says it must have no caller "yet"; it now has an
#          INERT one) · DEF-2551 (the shadow and this file each build the
#          catalogue and call `resolve`; only the ADAPTER is shared) · DEF-2552
#          (a switched rule is resolved at gather and `with_readings` rewrites
#          the readings afterwards without re-resolving)
# Rules:   BR-BIL-870 (a rule is served by the chain only when the deployment
#          names it; the default names none) · BR-BIL-871 (ONE fork, at the end
#          of the one impure pass; the chain runs at most once per account) ·
#          BR-BIL-872 (a switched rule whose chain refuses REFUSES THE ACCOUNT —
#          there is no fallback to the old implementation) · BR-BIL-873 (R3 and
#          R4 switch TOGETHER, because `resolve()` produces one base charge from
#          both) · BR-BIL-874 (a named step with no fork is a REFUSAL, never a
#          silent no-op) · BR-BIL-055 (a break refuses the account, never the
#          run) · BR-BIL-039 (the preview and the real run are the same code)
# Tests:   06-backend/tests/test_br_bil_870_resolution_switch.py
# Impacts: apps/billing/gather.py (the ONE call site, AND `version_fields_from`
#          — R2's fork reuses the live path's own version->TariffConfig mapping
#          rather than copying it) · apps/billing/contracts.py
#          (`AccountBillingData.resolution_steps` — what priced this account) ·
#          apps/billing/resolution_shadow.py (its `adapt` is REUSED, never
#          re-written) · apps/rating/resolution.py · apps/rating/selectors.py
#          (`pricing_inputs_for_version_id`, R2's read) · apps/billing/seam_batch
#          .py (that read is memoised for the pass) · config/settings/base.py
# ───────────────────────────────────────────────────────
"""STEP 5's MECHANISM: let ONE ruled rule at a time price a real bill.

HUMAN-OWNED 🔒 · HUMAN-REVIEW-PENDING — this file decides WHICH implementation
prices a customer's base charge, which makes it rating math, a CLAUDE.md
sensitive path, AI-authored under the PO ruling of 2026-08-09 ("AI will do it;
we will review it later as human"). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a recorded human
sign-off. It implements signed law and never invents it.

⚠ CORRECTED 2026-08-31 — THE PARAGRAPH BELOW IS HISTORY, NOT THE CURRENT STATE.
A glob in 10-scripts/gates/human_owned.txt DOES match this file now: the PO
ruled on 2026-08-31, having been shown all 62 unguarded files in five groups,
that groups one to four go on the watched list — "56 files" in their own words
— and this file is one of them. G7 checks it from that commit. The paragraph is
kept because WHY it went unguarded is worth knowing (DEF-2790: the check
written to catch exactly this looked for the wrong marker for three days), and
nothing below it should be read as describing today.

⚠ NO GLOB IN `10-scripts/gates/human_owned.txt` MATCHES THIS FILE, AND A LANE
MAY NOT ADD ONE — that list is a process event and the PO's call (the file's own
header says so, and `issue.py`, `decisions.py` and `read_analysis.py` each record
an escape caused by a lane correctly declining). The name is on
`10-scripts/gates/g53_unguarded_baseline.txt` so G53 states the gap instead of
hiding it, and the review-ledger row asks the PO for the glob in plain words.

WHAT THIS IS, IN ONE SENTENCE
-----------------------------
**Step 5** of the six-step cutover recorded in `12-governance/02-decision-log.md`,
2026-08-27, *"HOW R1–R7 GETS WIRED INTO BILLING — run both, compare, rule, then
switch. Never swap and hope."* Step 5 reads:

    "Switch one STEP at a time (R1, then R2, …), each only when its class is at
     zero. Move that step's DB half out of `gather` as it goes live."

Before this file there was **no seam a single rule could cross**. The bill run's
own database-backed narrowing served every rule and the chain served none, so
the only move available was swapping all seven at once — which the recorded
method forbids by name: *"switching all seven at once makes every disagreement
arrive in one diff with no way to attribute it."* This file is the missing seam.

⚠ R3 AND R4 ARE SWITCHED ON — CORRECTED 2026-09-01, AND THE PARAGRAPH BELOW IS
HISTORY
-----------------------------------------------------------------------------
**This section said "NOTHING IS SWITCHED ON, AND THAT IS THE POINT" and that
stopped being true the hour `CR-057` shipped.** `SERVED_BY_CHAIN_DEFAULT` is
`"R3,R4"` and `config/settings/base.py` ships the same pair, so **the chain
prices the base charge of every account on every deployment that has not
deliberately rolled it back.** The PO ruled the pair in on 2026-09-01 (*"Can you
wire them in now - R3 and R4"*). It is corrected here rather than left, because
a docstring describing a state the product has left is hard-won law 1 — and this
one told a reader that `apply()` is inert, which is the single most misleading
thing this file could say about itself.

What the ORIGINAL paragraph was right about, and still is: switching a rule is
step 5 PROPER, the method gates it (*"each only when its class is at zero"*),
and R1, R2, R5 and R7 are forkable and deliberately still OFF. Each needs its
own measurement and its own ruling, and `test_br_bil_870_resolution_switch.py`
asserts the served set is EXACTLY `{R3, R4}` so a widening goes red.

**So a full bill run before and after `CR-057` is NOT guaranteed to produce
identical figures** — it was measured instead: 3 utilities, 163 accounts, 163
unchanged, 0 moved, 0 refused (`10-scripts/cr057_r3r4_switch_dry_run.py`, and
the honest limit of that measurement is recorded beside
`SERVED_BY_CHAIN_DEFAULT`). With the setting rolled back to empty, `apply()`
does still return its argument unchanged — the same object, not a copy.

⚠ AND IT MAY NOT MAKE A DISAGREEMENT GO AWAY
--------------------------------------------
The decision log: *"A lane that makes the disagreements go away has destroyed
the evidence this job exists to produce, and has done it inside the one system
where a wrong answer is irreversible (hard rule 4)."* So there is **no fallback
in this file**. A rule served by the chain is served by the chain: if the chain
refuses, or if the adapter cannot assemble its facts, the ACCOUNT is refused by
name and lands on the run's exception screen. Quietly re-serving that account
from the old implementation would produce a bill that nobody could attribute to
either path, which is the one outcome worse than a refusal.

THE THREE DESIGN DECISIONS, AND WHAT WAS REJECTED
=================================================

1 · WHAT CARRIES THE CHOICE — a DEPLOYMENT setting, not a tenant row
---------------------------------------------------------------------
`settings.BILLING_RESOLUTION_STEPS`, sourced from the `SBH_BILLING_RESOLUTION_
STEPS` environment variable. A space- or comma-separated list of step names,
empty by default.

**Why not a tenant setting.** It was the obvious shape — the repo has a settings
module, a screen and an audit trail for tenant configuration — and it is wrong
here for three reasons. (a) Which implementation prices a bill is not a utility's
preference; it is our cutover, ruled centrally by the PO when a disagreement
class reaches zero. Storing it per tenant would invite two tenants to be priced
by two different narrowings with nobody having decided that. (b) A tenant row is
editable by any staff user who can reach Settings, and this decides money. (c) A
tenant setting is a PRODUCT FEATURE: it implies the choice is supported and
permanent, when step 6 deletes the loser. This control is scaffolding and its
carrier should look like scaffolding.

**Why not a bare code constant.** Reversibility. If a switched rule produces a
wrong figure on a live run, the fix must not wait for a build. An environment
variable is off at the next restart.

**What the environment variable costs, stated rather than hidden** — hard-won law
4: *"a template change never reaches a host that already has a `.env`."* The
code cannot then say which rules were live on the run that produced a given
bill. The mitigation is `AccountBillingData.resolution_steps`: the active set is
STAMPED on every account the run gathers, so the answer travels with the data
the clerk approved rather than living only in a host's environment.

**Fails closed** (hard-won law 3: *"the unsafe option must be the one you
type"*). Absent, blank, or unset ⇒ every rule served by its existing
implementation. There is no value that means "all".

2 · WHERE THE FORK LIVES — ONE place, at the end of `gather_account`
---------------------------------------------------------------------
Exactly one call site: the last line of `apps/billing/gather.py`'s
`gather_account`. Not one fork per stage.

**Why.** Two forks for one decision is how two implementations come to disagree,
which is the defect this whole cutover exists to close — and `gather.py`'s own
header already says it about the preview: *"two implementations that agree until
they don't is the classic way a preview lies."* One site also means the chain
runs **at most once per account**: `resolution.resolve()` returns the whole
narrowing in one object, so serving three rules from it costs the same as
serving one.

**Why the END of gather and not the middle.** The adapter's input is
`AccountBillingData` — the live path's own finished output. Running the chain
there guarantees both sides are looking at the same account at the same instant
(the shadow's own reasoning: *"a shadow that re-read the database could differ
from the live path for no reason but the clock"*), and it means a switched rule
is a SUBSTITUTION onto a fully-gathered account rather than a second gather.

**It is NOT a boundary move under BR-BIL-038.** That rule defines one as *"a
change to this tuple or to the signature of a stage entry point"*;
`pipeline.SEQUENCE` is untouched, no stage entry point's signature changes, and
`gather_account` is not a stage.

3 · WHAT HAPPENS WHEN THE CHAIN REFUSES — the account, by name, on screen
---------------------------------------------------------------------------
The chain has ten typed refusals and each names its step and the missing fact.
When a rule is switched on and the chain refuses, this raises `RuledPathRefused`
and `gather` turns it into a reason-coded `GatherProblem`
(`ruled_path_refused`), which `runs.prepare_run` already records per account
(BR-BIL-055: *a break never blocks the run*). **One named row on the S31.2
exception tab, and the other 499 accounts still draft.**

The chain's OWN sentence is carried whole and unedited — *"R3: connection size
'3-inch' has no row on the rate schedule version …"* — because that sentence is
the product of the whole exercise (BR-SHL-020: a refusal reads as a sentence,
never a code) and rendering the exception class name instead is called out in
the decision log as *"the lazy way to make the first test pass"*.

**The adapter being BLOCKED is treated the same way**, deliberately. A missing
connection size is not an error the chain raised, but it has the identical
consequence: the rule the deployment asked the chain to serve has no answer.
Both carry `ruled_path_refused` with the reason in the sentence, because the
clerk's next action is the same in both cases — somebody must go and supply the
fact — and two codes would split one queue in two.

WHICH RULES HAVE A FORK TODAY, AND WHY NOT ALL EIGHT
====================================================
`FORKED` names the steps whose answer this file can substitute onto a gathered
account. That is **six of eight**:

    R1        ->  AccountBillingData.rate_plan_version  (the chain's plan VERSION)
    R2        ->  TariffConfig's whole PRICE SHAPE, rebuilt from the chain's
                                     rate schedule version (the one step that
                                     needed a database read — see its section)
    R3 + R4   ->  TariffConfig.base_charge         (the chain's per-service base)
    R5        ->  TariffConfig.jurisdiction_factor (the chain's money_factor)
    R7        ->  AccountBillingData.taxes         (the chain's ATTACHED taxes)

⚠ **R1's FORK IS ITS VERSION AND NOT ITS PLAN, AND THE DIFFERENCE IS THE WHOLE
REASON IT CAN BE SWITCHED AT ALL (CR-052 task 21, 2026-08-31).** This paragraph
used to list R1 among the steps with nothing to substitute, on the grounds that
*"the chain is HANDED gather's plan id today, so substituting it would
substitute nothing"*. That is true of the plan ID and false of the plan
VERSION, and `DEF-2839` is what separated them: `resolution_shadow.adapt` hands
`plan_id` to `build_catalogue`, which stamps it back onto the row it yields —
one value compared with itself — while **the version never reaches the chain,
so the chain re-reads it.** One half of R1's answer is an echo and the other
half is an independent resolution of `BR-RAT-007` (*the version in force at the
service date*), and only the second half is switchable.

So R1's fork substitutes `rate_plan_version` and nothing else, and the plan id
is asserted as an INVARIANT rather than substituted: if the two paths ever name
different plans the shadow is comparing two different accounts and every other
figure in the run is meaningless, which is a louder failure than a divergence.

**WHAT SWITCHING R1 CHANGES ON A BILL: the version RECORDED, never an amount.**
`rate_plan_version` reaches `stages/assemble_document.py`'s payload and nothing
prices from it. That is the honest scope of R1 and it is stated here so nobody
reads "R1 is live" as "the chain is choosing prices".

The other two need their DB half moved out of `gather` first, which is the
second half of step 5 (*"Move that step's DB half out of `gather` as it goes
live"*) and is a slice per rule:

    R3b  the billable quantity — lives on the reading, not on the tariff; stage
                              2 measures it.
    R6   the discounts       — the two paths carry different shapes.

R2's SECTION BELOW is what that list used to say about R2, resolved rather than
restated: *"substituting the id alone would stamp the chain's version on prices
read from the live one"* is still exactly right, and the fork does not do it.

⚠ **R7 WAS ON THAT LIST UNTIL 2026-08-31 AND THE REASON GIVEN — *"likewise, the
two paths carry different shapes"* — DID NOT SURVIVE READING BOTH SHAPES
(CR-052 task 22).** They differ in one field each way and neither difference is
structural:

* The chain's `TaxRule` carries `services`, `customer_classes`,
  `inside_city_only` and `outside_city_only`. Three of those four are
  APPLICABILITY and `resolve_taxes` has already applied them — `resolved.taxes`
  is the narrowed answer, not the candidate list — so they need no home on the
  billing side. The fourth, `services`, DOES have one:
  `rating_seam.TaxRule.applies_to_services`, added for r10's *"City Franchise
  Fee 1.5% · Electric only"* precisely so a franchise fee stops taxing the water.
* The billing rule carries `discount_treatment` (`BR-RAT-106` / `DEF-502`) and
  **the chain has no such field.** It is statutory, per tax, and decides whether
  an authority levies on the subtotal before or after a discount.

So the fork substitutes the chain's four money-and-identity fields and CARRIES
`discount_treatment` ACROSS from the live rule it matches — by `tax_id` first
(*"whose debt it is"*, an identity that does not move) and by `code` only as a
fallback. **A chain tax with no live counterpart REFUSES the account** rather
than defaulting: `None` answers `before`, which is a real levy order, and
choosing it for an authority nobody matched would be this file inventing a
statutory fact on a money path.

R2's FORK — THE VERSION IS REBUILT INTO PRICES, NEVER STAMPED ONTO THEM
=======================================================================
**Added 2026-08-31, CR-052 task 22. The decision log entry of the same date —
*"R2's FORK IS BUILT INSIDE `resolution_switch`, NOT INSIDE `gather`"* — carries
the choice and what was rejected; this is what it does.**

R2 decides *plan version -> exactly one RATE SCHEDULE VERSION per service*, and
what the chain hands back is `ServiceResolution.schedule_version_id`: **an ID,
with no rates and no tiers on it.** Substituting that id onto a `TariffConfig`
whose prices `gather` read from a DIFFERENT version would stamp one version's
number onto another version's money — **a lie on the bill, and the worst kind,
because every figure would still be internally consistent.** So the fork does
not substitute the id. It REBUILDS the tariff's price shape from the version the
chain named, through `gather.version_fields_from` — the SAME mapping the live
path uses, extracted rather than copied, because a second copy of a money
projection drifts on the first rate shape that gains a column (`DEF-434`).

**THE READ, AND WHY IT IS NOT ONE PER SERVICE PER ACCOUNT.**

  * **The equal case issues no read at all.** `TariffConfig.version_id` already
    records which version priced this line (`DEF-276`). When the chain's answer
    equals it, the rebuild is provably the same projection of the same version
    at the same date and the same size, so nothing is substituted and the step
    is stamped. That is **47 of 47** accounts of the seeded utility today
    (*R2 47 agree / 0 disagree*, measured 2026-08-31).
  * **The unequal case asks rating**, through `selectors.pricing_inputs_for_
    version_id` — a six-line id lookup in front of `pricing_inputs_for_version`,
    which is the product's ONE projection of a stored version onto the engine's
    inputs. It is on `seam_batch.BATCHABLE` beside `pricing_inputs` itself, so
    it collapses on the same argument that one collapses on: a small utility has
    a handful of plans, and the accounts on one plan name one version between
    them (measured on the live path's copy of this read: **2,937 calls -> 6**).

**THE FACT THE CHAIN'S VERSION CANNOT SUPPLY, AND IT REFUSES BY NAME: THE BASE
CHARGE.** Same shape as R7's `discount_treatment` refusal, one field along.
`TariffConfig.base_charge` is not a field of the rate schedule version — it is
`gather._base_charge_for`'s answer. ⚠ **THAT ANSWER WAS TAKEN OVER THREE STORED
FIGURES UNTIL 2026-09-28 — the charge code's amount, the plan's figure and the
version's own `base_charge` column — AND IT IS TAKEN OVER ONE NOW**
(`DEF-BIL-7170`; PO: *"we will never take default value from plan $8.0 - that
is retired"*). The charge code owns it and the other two are read by nothing.
What does NOT travel on a `TariffConfig` is the narrowing the charge code was
resolved through — the customer class, the connection size and the schedule's
own binding — so this module still cannot re-take that decision, and `gather`
says why in its own words at the place it reads them: *"a second place that
re-derives any of them is a second narrowing that can disagree with this one."*

⚠ **THE PARAGRAPH THAT STOOD HERE DESCRIBED A WORLD THAT ENDED ON 2026-09-28
(`DEF-BIL-7170`).** It read: *"The version's column is the one input of the
three that MOVES when R2 moves the version, and it is live in two branches — the
value itself where no charge code is declared and the plan states none, and a
TRIPWIRE where one is."* The PO retired both of the other two sources — *"we
will never take default value from plan $8.0 - that is retired"* — so
`gather._base_charge_for` takes ONE input, the charge code's amount, and the
version's own column is read by nothing. **What the version still moves is the
BINDING**, `tariff_versions.base_charge_code` (`BR-RAT-1025`), and the branch
below still compares the retired COLUMN: that is `DEF-BIL-7310`, filed and left
standing because it fails closed on a configuration no deployment runs. So:

    same version                      -> the base cannot have moved; no rebuild
    different, R3 + R4 ALSO served    -> the chain supplies `base_charge`
                                         outright; nothing is mixed
    different, R3 + R4 NOT served     -> the two versions' own `base_charge`
                                         columns are compared. EQUAL, the base is
                                         unaffected either way and the rebuild
                                         stands. DIFFERENT, the ACCOUNT REFUSES
                                         by name.

`None` is not defaulted to a figure and a figure is not carried silently: a
ladder from one version beside a base from another is the same internally
consistent lie, one field down.

**THE SIZE GATE IS CARRIED ACROSS, with `gather`'s own sentence** (`DEF-484`). If
the chain's version prices some connection sizes differently and this
connection's size could not be resolved, the rebuild REFUSES rather than pricing
the every-size ladder — *"that answer is right for a size the schedule does not
name and wrong for one it does, and the two are indistinguishable on the
document."*

⚠ **AND R2 MUST NOT BE SWITCHED ON UNTIL `DEF-2889` IS CLOSED, WHICH IS A CHAIN
DEFECT THIS FORK FOUND AND DID NOT FIX.** The two narrowings disagree by exactly
one day and the CHAIN is the one that is wrong:
`rating.selectors.in_force_version` matches `effective_to >= service_date`, while
`resolution.ScheduleVersion.in_force_on` matches `effective_to > service_date` —
and `rating.services` closes a superseded version with `previous.effective_to =
new_from - timedelta(days=1)`, so `effective_to` is the LAST DAY the version
prices. On a service date equal to it the chain finds the old version out of
force and the new one not yet started and **refuses the account**, where the live
path bills it. `BR-BIL-872` makes that refusal final, so switching R2 today would
stop one day's bills per schedule change for a boundary the chain reads wrongly.

⚠ **THE MIRROR CASE IS FILED AND NOT FIXED HERE — `DEF-2890`.** R3 + R4 switched
WITHOUT R2 can stamp a base charge resolved from the CHAIN's version onto a tier
ladder read from the LIVE one, whenever `base_source` is `schedule` rather than
`charge_code`. It is the same coupling running the other way; it predates this
commit, no deployment names a step so it has never run on a bill, and closing it
is either a `JOINT` entry pairing R3/R4 with R2 or the same version comparison in
the other direction. **A lane must not widen `JOINT` casually** — this file
already refuses `R4` without `R3` *"rather than silently widening to both,
because widening would switch a rule nobody asked for"*.

**A step named in the setting that has no fork REFUSES at once** (BR-BIL-874).
It must not be accepted and ignored: a switch that silently does nothing is a
comment claiming a guarantee (hard-won law 1), and it would read as *"R2 has
been live for a week and nothing broke"* when R2 never ran.

⚠ **AND R3b HAS A SECOND OBSTACLE THAT IS NOT ABOUT THE DATABASE — `DEF-2552`.**
A switched-on rule is resolved HERE, at gather, and `gather.with_readings` swaps
new readings onto the already-gathered account afterwards when a clerk replaces
a missing read with an estimate on S31.3. It does not re-resolve. That cannot
bite on either rule with a fork today — neither the base charge nor the money
factor depends on a reading — but a reading-derived step given a fork would be
answered from the readings the clerk REPLACED. Whoever forks R3b owns that, and
the fix must not become a SECOND fork point (BR-BIL-871): the single fork moves,
it does not multiply.

⚠ **EVERY BILL PATH GOES THROUGH THIS ONE LINE, VERIFIED RATHER THAN ASSUMED.**
`AccountBillingData` is constructed in exactly ONE place in the product —
`gather.py`'s `gather_account` — and `runs.prepare_run`, `single
.calculate_single_bill` and `midperiod` all call it. So "one fork" is a fact
about the tree and not an intention.

**R3 AND R4 SWITCH TOGETHER** (BR-BIL-873). `resolve()` produces ONE
`base_charge` per service from both steps — R4's charge code where the tenant
declares one, the schedule's retired scalar where it does not, with
`base_source` recording which — so there is no seam between them to switch on
its own. Naming one without the other is refused rather than silently widened.

⚠ **AND THE SHADOW NO LONGER FUSES THEM, WHICH IS NOT THE SAME QUESTION
(`DEF-2823`, 2026-08-31).** This paragraph used to end *"the shadow's own
comparison labels this divergence `R3/R4` for exactly this reason"*, and that
half is now false: `resolution_shadow.compare()` compares the connection SIZE
at **R3** and the base AMOUNT at **R4**, separately, because a fused agreement
is evidence for NEITHER half and the cutover's own rule is that a step switches
only when its own class is at zero. **`BR-BIL-873` is unchanged** — SWITCHING
them apart is still refused, because one figure still comes out of `resolve()`.
Measuring them apart and switching them apart are two different acts, and only
the first happened.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date
from decimal import Decimal
from importlib import import_module
from inspect import signature
from typing import Any

from django.conf import settings

from apps.billing import bill_warnings, resolution_shadow
from apps.billing.contracts import AccountBillingData

logger = logging.getLogger(__name__)

__all__ = [
    "STEPS",
    "FORKED",
    "JOINT",
    "SETTING",
    "SERVED_BY_CHAIN_DEFAULT",
    "SwitchMisconfigured",
    "RuledPathRefused",
    "steps_served_by_chain",
    "apply",
]

#: The chain's own steps, in the design's §A2 order. This is the vocabulary a
#: deployment types; it is NOT a list of what is switchable — see `FORKED`.
STEPS: tuple[str, ...] = ("R1", "R2", "R3", "R3b", "R4", "R5", "R6", "R7")

#: The steps this file can serve from the chain today. See the docstring for
#: why the other two need their database half moved first.
FORKED: frozenset[str] = frozenset({"R1", "R2", "R3", "R4", "R5", "R7"})

#: Steps that may only be switched TOGETHER, because the chain produces one
#: answer from all of them (BR-BIL-873).
JOINT: tuple[frozenset[str], ...] = (frozenset({"R3", "R4"}),)

#: The Django setting, fed from `SBH_BILLING_RESOLUTION_STEPS` in
#: `config/settings/base.py`.
SETTING = "BILLING_RESOLUTION_STEPS"

#: ⚠ **THIS CONSTANT DECIDES NOTHING — `config/settings/base.py` DOES
#: (`DEF-2922`, 2026-09-01).** It is reached only as
#: `getattr(settings, SETTING, SERVED_BY_CHAIN_DEFAULT)` and
#: `BILLING_RESOLUTION_STEPS` is ALWAYS defined there, so this fallback is
#: unreachable on every deployment and always has been. **Changing this line
#: alone switches nothing on, and changing the setting alone leaves this file
#: contradicting itself** — hard-won law 2 (*built is not wired*) hiding in the
#: one file whose whole job is the switch. It was found by moving it and
#: watching `steps_served_by_chain()` still answer `frozenset()`. The two
#: literals are pinned EQUAL by `test_br_bil_870_resolution_switch.py`, and it
#: asserts the SET as well — because asserting a constant that decides nothing
#: is a check that cannot fail (`DEF-182`).
#:
#: ⚠ **R3 AND R4 ARE ON. THE PRODUCT OWNER RULED THE PAIR IN ON 2026-09-01 AND
#: THE SHIPPED DEFAULT NOW SERVES IT (`CR-057`).** PO verbatim: *"Can you wire
#: them in now - R3 and R4"* and, after being told the first flip broke things,
#: *"can you fix this probelm and again try to siwthicing - R3 and R4"*.
#:
#: **WHAT THE FIRST FLIP BROKE, AND HOW IT WAS CLOSED RATHER THAN WORKED AROUND
#: — `DEF-2923`.** Flipping this made SEVEN cases of the switch suite fail, and
#: not one was a fixture problem: **a tenant that had declared no `is_base`
#: charge code for a service had every account of that service REFUSED**, by
#: name, with *"Declare a base charge code for 'water' under Charge codes"*.
#: That is `BR-RAT-088` behaving exactly as signed — the charge code is the only
#: source of a base amount — reaching a live default for the first time.
#: **The first answer was to serve the ruling per deployment instead. The PO
#: sent that back, and they were right: the state is the defect, not the
#: default.** So the hole is closed at its cause —
#: `rating.services._guard_base_charge_code` now consults
#: `steps_served_by_chain()` and refuses to ACTIVATE A SCHEDULE for a tenant
#: with no base code while R4 is served. **The refusal moved from billing day to
#: a settings screen**, where the sentence names the fix and nobody's bill has
#: stopped.
#:
#: ⚠ **WHAT WAS NOT DONE, DELIBERATELY: A FALLBACK.** `BR-BIL-872` gives a
#: switched rule none, and re-serving a refused account from the old
#: implementation produces a bill nobody can attribute to either path.
#:
#: **WHAT A DEPLOYMENT SHOULD RUN BEFORE TRUSTING THIS, per utility:**
#:
#:   `cr052_r1r7_shadow_measure.py --tenant <sub>`   does R3 REFUSE anybody?
#:       measured 2026-09-01: 3 utilities · 163 accounts · 2 distinct
#:       (service · size) pairs · **0 with nothing pricing them**, and every
#:       service carrying a declared base charge code.
#:   `cr057_r3r4_switch_dry_run.py --tenant <sub>`   and is the FIGURE the same?
#:       the pair switched on inside a rolled-back transaction:
#:       **163 accounts · 163 unchanged · 0 moved · 0 refused.**
#:
#: Both were proved able to print the failing verdict (`--sabotage`), because a
#: check that has only ever printed one answer is not a check (law 7).
#:
#: ⚠ **AND THE HONEST LIMIT: three utilities on one database sharing one seeded
#: ladder is not a product-wide answer.** Both preflights take `--tenant`
#: because both must be RUN on a utility before that utility is trusted. What
#: protects the utilities nobody measured is not the measurement — it is the
#: activation gate above, which fires for every tenant.
#:
#: **WHAT IS ON IS THE PAIR AND NOTHING ELSE.** `BR-BIL-873` binds R3 and R4 (the
#: chain produces ONE base charge from the two) and `JOINT` refuses either alone.
#: R1, R2, R5 and R7 are forkable and deliberately absent: each needs its own
#: measurement and its own ruling, and the default test asserts the served set is
#: EXACTLY `{R3, R4}` so a widening goes red.
#:
#: **ROLLBACK — one line, no release, and it is TESTED rather than promised:**
#: set `SBH_BILLING_RESOLUTION_STEPS=` (empty) and restart. The setting is
#: re-read on every call and never cached at import, and
#: `test_br_rat_120_size_refusal.py::test_TC6b` prices a real bill through the
#: rolled-back path to prove it still works.
SERVED_BY_CHAIN_DEFAULT: str = "R3,R4"

_BY_LOWER = {step.lower(): step for step in STEPS}


class SwitchMisconfigured(Exception):
    """The deployment named something this file cannot honour.

    Raised rather than ignored, on purpose. A step name that is accepted and
    does nothing would be reported to a PO as *"R2 has been live for a week"*
    when R2 never ran once — the exact shape of hard-won law 1.
    """


class RuledPathRefused(Exception):
    """A switched-on rule has no answer for this account, so the account stops.

    `sentence` is the chain's own message where the chain refused, and the
    adapter's own message where the adapter could not assemble the facts. It is
    carried WHOLE: it names the step and the missing fact, which is what makes
    ⚠ **AND `sentence` IS THE ENGINEER'S HALF — `DEF-RAT-7991`, 2026-09-29.**
    Nine of the chain's raise sites interpolate a database uuid into it, and
    `one_time.py` puts it into a **200-response body** where `BR-SHL-020 r2`'s
    stripper cannot see it. So a clerk on the One-time bill screen read four
    uuids at once. The three fields below carry rating's own CLERK sentence —
    the catalogue key, its facts, and the id-free English mirror — straight
    through to the serialiser, unexamined and never composed here. Empty on a
    refusal that states none, which is every one the ADAPTER raises.
    """

    def __init__(
        self,
        step: str | None,
        sentence: str,
        *,
        service: str = "",
        message_key: str | None = None,
        clerk_detail: str | None = None,
        message_params: dict[str, object] | None = None,
        reason: str | None = None,
    ) -> None:
        self.step = step
        self.sentence = sentence
        self.service = service
        #: The gather's reason code when it is NOT `ruled_path_refused` — set
        #: only for a refusal the Check puts to a clerk as a decision
        #: (`runs.METER_HAS_NO_MULTIPLIER`, changes row 44). None otherwise.
        self.reason = reason
        self.message_key = message_key
        self.clerk_detail = clerk_detail
        self.message_params: dict[str, object] = dict(message_params or {})
        super().__init__(sentence)


def steps_served_by_chain() -> frozenset[str]:
    """Which rules this deployment has asked the ruled path to serve.

    Empty on every deployment that has not typed one, which is all of them.
    Validated on EVERY read rather than once at import: settings are overridden
    per test and per management command, and a set validated once would be a
    set nobody re-checked after it changed.
    """
    raw = getattr(settings, SETTING, SERVED_BY_CHAIN_DEFAULT)
    if raw is None:
        raw = ""
    if isinstance(raw, str):
        typed = [part for part in raw.replace(",", " ").split() if part]
    else:
        typed = [str(part).strip() for part in raw if str(part).strip()]
    if not typed:
        return frozenset()

    chosen: set[str] = set()
    for name in typed:
        canonical = _BY_LOWER.get(name.lower())
        if canonical is None:
            raise SwitchMisconfigured(
                f"{SETTING} names {name!r}, which is not a step of the R1–R7 chain. "
                f"The steps are {', '.join(STEPS)}. Nothing is switched and no bill "
                "is priced until this is corrected — a name nobody recognises must "
                "not read as 'off'."
            )
        chosen.add(canonical)

    unforked = sorted(step for step in chosen if step not in FORKED)
    if unforked:
        raise SwitchMisconfigured(
            f"{SETTING} names {', '.join(unforked)}, and this build has no fork for "
            f"{'them' if len(unforked) > 1 else 'it'}. Only "
            f"{', '.join(sorted(FORKED))} can be served by the ruled path today; the "
            "rest need their database half moved out of the bill run first (step 5 of "
            "the cutover). Accepting the name and doing nothing would report a rule as "
            "live for a week when it never ran once."
        )

    for pair in JOINT:
        overlap = chosen & pair
        if overlap and overlap != pair:
            raise SwitchMisconfigured(
                f"{SETTING} names {', '.join(sorted(overlap))} without "
                f"{', '.join(sorted(pair - overlap))}. BR-BIL-873: the chain produces "
                "ONE base charge from R3 and R4 together — R4's charge code where the "
                "tenant declares one and R3's size row where it does not — so there is "
                "no seam between them to switch on its own. Name both or neither."
            )
    return frozenset(chosen)


def apply(
    data: AccountBillingData, *, account: Any, service_date: date
) -> AccountBillingData:
    """THE fork. One call site, one chain run, one substitution per switched rule.

    Returns `data` ITSELF — not a copy — when nothing is switched on. ⚠ That
    used to read *"which is every deployment today"* and it stopped being true
    with `CR-057`: the shipped default is **R3,R4**, so on an ordinary
    deployment this function DOES substitute the base charge and the early
    return below is reached only after a rollback
    (`SBH_BILLING_RESOLUTION_STEPS=`). The identity is still the guarantee that
    a ROLLED-BACK deployment moves no figure, and a test asserts it by object
    identity rather
    than by comparing fields.

    Raises `RuledPathRefused` when a switched-on rule has no answer for this
    account. `gather` maps that onto a reason-coded `GatherProblem`; there is no
    fallback here and there must never be one.
    """
    served = steps_served_by_chain()
    if not served:
        return data
    tariffs = tuple(getattr(data, "tariffs", ()) or ())
    if tariffs and all(getattr(config, "covers_unit_id", None) for config in tariffs):
        # 🔒 `DEF-CUS-9050` (PO 2026-10-02) — an owner's bill made ONLY of empty
        # homes' base charges (a master with no common area). `_substituted`
        # leaves every such tariff exactly as `gather` priced it (DEF-BIL-8724),
        # so there is nothing for the chain to substitute — and asking it would
        # resolve the plan's services against an EMPTY home and refuse for a
        # meter nobody reads (R3). Returned unchanged, by identity.
        return data

    resolved = _resolve_for(data, account=account, service_date=service_date)
    return _substituted(data, resolved, served, service_date=service_date)


# ══════════════════════════════════════════════════════════════════════════
# Running the chain — through the SHADOW's adapter, never a second one
# ══════════════════════════════════════════════════════════════════════════


def _resolve_for(data: AccountBillingData, *, account: Any, service_date: date) -> Any:
    """`AccountBillingData` -> a `Resolution`, or a named refusal.

    ⚠ **THE ADAPTER IS `resolution_shadow.adapt`, REUSED VERBATIM.** It is the
    dangerous half of this mapping — it is where a register difference must not
    become a stored consumption and where a missing multiplier must not become
    1 — and a second copy of it is the two-implementations defect this cutover
    exists to close, committed inside the cutover itself.

    ⚠ **WHAT IS NOT SHARED IS THE INVOCATION** (`DEF-2551`): the catalogue build
    and the `resolve()` call below are a second copy of six lines the shadow also
    holds. The durable fix is for `resolution_shadow` to publish one
    `resolve_for()` that both callers use; that file has an owner and this lane
    does not write it, so the duplication is FILED rather than left unsaid.
    """
    # ── changes row 44 (PO 2026-09-30) · NO MULTIPLIER IS A CLERK'S DECISION ──
    # *"no multiplier → Hold (default) / Bill with multiplier 1"*. Inside a
    # Check pass the refusal becomes that decision (`runs.METER_HAS_NO_
    # MULTIPLIER`, its own tag) and a recorded ×1 is honoured; outside one —
    # single, first, one-time, back-bill, where nobody can answer — a meter with
    # no register difference this period needs no factor (nothing is scaled),
    # and one WITH a difference is refused exactly as before.
    from apps.billing import runs

    in_check = runs.in_check_pass()
    account_id = getattr(account, "id", None)

    def multiplier_one(service: str) -> bool:
        # Asked only where the factor is missing and the usage is billed, so a
        # True here IS the ×1 being applied — noted, so the Check keeps the
        # answered decision on the account (`runs.note_multiplier_one`).
        chosen = (
            runs.clerk_answer(account_id, service, runs.METER_HAS_NO_MULTIPLIER)
            == runs.ANSWER_MULTIPLIER_ONE
        )
        if chosen:
            runs.note_multiplier_one(service)
        return chosen

    inputs = resolution_shadow.adapt(
        data,
        account=account,
        unread_factor=(
            resolution_shadow.UNREAD_FACTOR_REFUSE
            if in_check
            else resolution_shadow.UNREAD_FACTOR_NOT_NEEDED
        ),
        multiplier_one=multiplier_one,
    )
    if (
        in_check
        and inputs.blocked_reason == resolution_shadow.MISSING_MULTIPLIER
        and inputs.blocked_service
    ):
        raise RuledPathRefused(
            None,
            f"service {inputs.blocked_service!r}: the meter states no multiplier — it has "
            "never been read, or its read stored none — and a missing factor is never 1 "
            "(BR-MET-056). A clerk decides: Hold, or Bill with multiplier 1.",
            service=inputs.blocked_service,
            reason=runs.METER_HAS_NO_MULTIPLIER,
            message_params={"service_code": inputs.blocked_service},
        )
    if (
        inputs.blocked_reason == resolution_shadow.MISSING_ASSET_COUNT
        and inputs.blocked_service
    ):
        # `DEF-BIL-8851` — NOBODY COUNTED, BY ITS OWN NAME (BR-RAT-090: *"'no
        # carts recorded' and 'zero carts' are different facts and only one of
        # them is billable"*). The live path's stage already stops this as
        # `CALC_ASSET_COUNT_UNAVAILABLE`, with its own Check tag (Assets,
        # blocks) and its own one-time sentence; the ruled path now says the
        # same thing instead of a generic *"ruled path refused"*, so a clerk is
        # sent to count the carts and never to the Reads tab.
        raise RuledPathRefused(
            None,
            f"service {inputs.blocked_service!r}: nobody has counted what stands on "
            "this connection, so there is no quantity to bill. A count of zero would "
            "be a different fact (BR-RAT-090).",
            service=inputs.blocked_service,
            reason=runs.CALC_ASSET_COUNT_UNAVAILABLE,
            message_params={"service_code": inputs.blocked_service},
        )
    if inputs.blocked_reason is not None:
        raise RuledPathRefused(
            None,
            f"the ruled path could not price this account: {inputs.blocked_detail or inputs.blocked_reason}",
            # `DEF-BIL-8218` — WHICH fact is missing, and on which service, as
            # stable codes (never prose): the bulk run's Check offers the fix
            # for a missing connection size on the row. `service` is left
            # unset on purpose, so the gather's per-service retry and every
            # refusal a clerk already sees are unchanged.
            message_params={
                "blocked": inputs.blocked_reason,
                **({"service_code": inputs.blocked_service} if inputs.blocked_service else {}),
            },
        )

    resolution = import_module("apps.rating.resolution")
    catalogue_module = import_module("apps.rating.resolution_catalogue")
    # `account` / `premises` are R7's narrowing facts and are REQUIRED
    # (`DEF-2824`): `plan_tax_rules` fails closed on every restriction a tax
    # states, so a catalogue built without them carries only the UNRESTRICTED
    # taxes — and this is the file that can put that answer on a real bill.
    catalogue = catalogue_module.build_catalogue(
        plan_id=inputs.plan_id,
        service_date=service_date,
        account=inputs.account,
        premises=inputs.premises,
        unmetered_services=inputs.unmetered_services,
    )
    # ── 2026-09-30 · THE CHAIN RESOLVES THE SERVICES THIS BILL PRICES ─────
    # PO rulings of that date: no asset = not in service; not in service
    # prints no line. The chain walks `plan.services` and REFUSES a metered
    # service with no meter (R3, `SizeNotServed`), so a plan service the live
    # path has ruled out would stop the whole bill on the ruled path while the
    # live path prices it. The narrowing is to `data.tariffs` — the live
    # path's own decision, taken once in `gather` — and it can only REMOVE a
    # service from the chain's domain, never add one, so every service the
    # chain answers for is still compared (`_substituted` still refuses a
    # service the chain did not resolve). `billed` empty narrows nothing.
    billed = {getattr(config, "service", "") for config in data.tariffs}
    # ── 2026-10-01 · A SERVICE WHOSE BASE GATHER FOUND BY SIZE IS NOT ASKED ──
    # PO: *"based rates should be search based on sizes dueing billing; if rate
    # is not found then you assum it zero and calculate instead of refusing the
    # bill"*. `_substituted` already leaves these services' tariffs exactly as
    # `gather` built them; but the chain was still RESOLVED over them, and R4
    # resolves ONE amount per service at ONE size — so a per-size base code
    # (`BASE-T` CART-96 $3.00) refused the whole account (`charge_code_amount`:
    # *"states no amount for connection size …"*) before the exclusion could
    # apply. Measured: 2 × CART-96 with a per-size BASE-T was `ruled_path_
    # refused`, never $36.00. So the chain is not asked about them at all.
    # ⚠ NOT when R7 is served: the chain's taxes are resolved over the plan's
    # services, and dropping one would drop its tax. That combination keeps
    # yesterday's behaviour, refusal included — stated, not hidden.
    keep = billed
    if "R7" not in steps_served_by_chain():
        keep = billed - _priced_outside_chain(data)
    if billed:
        catalogue = replace(
            catalogue,
            plan_versions=tuple(
                replace(plan, services=tuple(s for s in plan.services if s in keep))
                for plan in catalogue.plan_versions
            ),
        )
    # Only the chain's OWN refusals are caught. An `AttributeError` inside
    # `resolve()` is a bug in the chain and must not reach a clerk dressed as a
    # configuration problem — the distinction `rating_seam._refusal_types` draws.
    base = getattr(resolution, "ResolutionError", None)
    if not (isinstance(base, type) and issubclass(base, BaseException)):
        base = ()  # pragma: no cover - defensive
    try:
        return resolution.resolve(
            catalogue=catalogue,
            account=inputs.account,
            premises=inputs.premises,
            meters=inputs.meters,
            quantities=inputs.quantities,
            asset_counts=inputs.asset_counts,
            service_date=service_date,
        )
    except base as refusal:  # type: ignore[misc]
        # `refusal_steps()` is rating's own map, published for exactly this
        # (DEF-2341 records what a hand-written copy costs: it cannot see a
        # refusal class added after it was written).
        steps = resolution.refusal_steps()
        # `clerk_refusal` is rating's OWN published reader (`DEF-RAT-7991`),
        # for the reason `refusal_steps()` is one line up: a hand-written copy
        # here cannot see a field added there (DEF-2341).
        clerk = resolution.clerk_refusal(refusal) or {}
        raise RuledPathRefused(
            steps.get(type(refusal).__name__),
            str(refusal),
            message_key=clerk.get("message_key"),
            clerk_detail=clerk.get("detail"),
            message_params=clerk.get("message_params"),
        ) from refusal


# ══════════════════════════════════════════════════════════════════════════
# The substitution — per rule, per service, and never partial
# ══════════════════════════════════════════════════════════════════════════


def _priced_outside_chain(data: AccountBillingData) -> set[str]:
    """The services whose base `gather` found BY SIZE, which the chain — one
    answer per service at one size — cannot express: a counted service billed
    one config per size (`per_size_line`, trash and fire) and a summing
    capacity service whose base is `Σ base(size) × count` (`pricing_trace`'s
    `base_by_size`, PO 2026-10-01). Read off the flags gather SET, never
    inferred from sizes (a master account's two connections must still reach
    the refusal in `_substituted`)."""
    outside = {
        str(getattr(config, "service", ""))
        for config in data.tariffs
        if getattr(config, "per_size_line", False)
    }
    outside |= {
        str(service)
        for service, entry in (getattr(data, "pricing_trace", None) or {}).items()
        if (entry or {}).get("base_by_size")
    }
    return outside


def _substituted(
    data: AccountBillingData,
    resolved: Any,
    served: frozenset[str],
    *,
    service_date: date,
) -> AccountBillingData:
    """Put the chain's answers where the live ones were, for switched rules only.

    ⚠ **A SERVICE THE CHAIN DID NOT RESOLVE REFUSES.** Leaving that one tariff
    on the live answer while its neighbours moved is a silent per-service
    fallback, and it would produce a bill priced by two narrowings at once —
    the disagreement reconciled away invisibly, one line at a time.
    """
    # ⚠ **A MASTER ACCOUNT IS NO LONGER REFUSED HERE — `DEF-BIL-8470`,
    # 2026-09-30.** This block refused every master bill (BR-CUS-068) on the
    # premise that *"the adapter can only look a connection size up against
    # the ANCHOR's unit"*. That premise is withdrawn: `resolution_shadow.adapt`
    # now resolves each service against the covered unit that SERVES it, by the
    # live path's own `gather._coverage_facts`, so each service the chain
    # answers is ONE connection — the one the live path prices. Two covered
    # units on one service (OQ-334) or on two plans (OQ-335) still refuse, in
    # `gather`, by name, before this point. On 1408 Elm the one bill now prices
    # the hallway's $41.20 and the irrigation's $28.40: **$69.60**.

    # ── CR-063 · A SERVICE BILLED ONE LINE PER SIZE IS OUTSIDE THIS CHAIN ──
    # Decision log 2026-09-02: a capacity service priced by a COUNT — trash and
    # fire — carries ONE BILL LINE PER SIZE, so one connection legitimately
    # produces two tariffs for one service. That is a different fact from the
    # master account below and it must not be refused as one: a fire property
    # has ONE fire connection with, say, a 6" line and two 2" lines on it, and
    # refusing it would stop a bill the live path prices correctly. (This read
    # "a 6-inch line and two hydrants" until the PO withdrew the private hydrant
    # from fire's size list on 2026-09-03 — the SHAPE this comment describes,
    # two tariffs on one connection, is exactly as it was.)
    #
    # **The chain has no vocabulary for it** — `resolved.service(code)` is one
    # answer per SERVICE, and applying that answer to both configs would stamp
    # one size and one base onto two lines. So the service is EXCLUDED from
    # substitution and its tariffs stand exactly as `gather` built them.
    #
    # ⚠ **THIS IS A NAMED EXCLUSION AND NOT THE SILENT PER-SERVICE FALLBACK
    # THIS FUNCTION'S DOCSTRING FORBIDS.** That warning is about a service the
    # chain FAILED to resolve — a disagreement, which must be reported rather
    # than reconciled away. This is a service whose SHAPE the chain cannot
    # express, known before it is asked, deterministic, and logged below with
    # the account it applied to. Nothing is reconciled because nothing was
    # compared.
    #
    # ⚠ **THE TEST IS THE FLAG `gather` SET, NEVER A COMPARISON OF SIZES.** A
    # master account covering a 5/8" unit and a 2" unit also carries two tariffs
    # with two distinct sizes, and reading that as a per-size split would apply
    # this exclusion to exactly the case the refusal below exists for.
    # ── 2026-09-30 · A SERVICE BILLED ONE LINE SET PER METER IS OUTSIDE IT TOO ──
    # PO: *"both meter should be build in metered case also - as a speearte
    # line"*. Two in-service meters on one metered point are two tariffs for
    # one service, each naming its meter (`asset_id`), and the chain — one
    # answer per SERVICE — cannot say which meter a base belongs to, exactly as
    # it cannot for a size. Excluded BY THE FLAG `gather` SET (the meter id),
    # never by counting tariffs, so a master account's two connections still
    # reach the refusal below. Measured on PostgreSQL 16 before this clause:
    # 5 of 75 seeded accounts carry two water meters and every one REFUSED on
    # *"more than one tariff for water"* — bills that priced the day before.
    per_size = {
        getattr(config, "service", "")
        for config in data.tariffs
        if getattr(config, "per_size_line", False) or getattr(config, "asset_id", None)
    }
    # ── 2026-10-01 · A SUMMING CAPACITY SERVICE WHOSE BASE WAS FOUND BY SIZE ──
    # PO: *"based rates should be search based on sizes dueing billing"*. Its
    # base is `Σ base(size) × count` (`gather._size_base`), and the chain's one
    # answer per service would overwrite it with a single size's figure. Same
    # named exclusion as above, by the FLAG `gather` recorded, never inferred.
    per_size |= _priced_outside_chain(data)
    # ── `DEF-BIL-8724` (2026-10-01) · AN EMPTY UNIT'S BASE ON AN OWNER'S BILL ──
    # BR-CUS-170 puts the base charge of every unit nobody occupies on the
    # owner's bill, priced from THAT UNIT's own plan (DEF-990), as its own
    # base-only tariff. The chain resolves the OWNER's plan, one answer per
    # service, so it has no answer for a base that belongs to another unit on
    # another plan — and counting it as a second electric tariff refused the
    # owner's whole bill: 1408 Elm's $69.60 + $12.00 = **$81.60** issued as
    # nothing. Excluded PER TARIFF by the flag `gather` set (never by counting
    # tariffs, and never the whole service — the hallway's electric beside it
    # is still the chain's), and logged below with the account.
    services = [
        getattr(config, "service", "")
        for config in data.tariffs
        if getattr(config, "service", "") not in per_size
        and not getattr(config, "covers_unit_id", None)
    ]
    duplicates = sorted({name for name in services if services.count(name) > 1})
    if duplicates:
        # A master account carries one tariff per covered unit and several can
        # share a service code (BR-CUS-068). The chain resolves ONE answer per
        # SERVICE, so it cannot say which of two water connections a base
        # charge belongs to. Refused rather than applied to both.
        raise RuledPathRefused(
            None,
            "the ruled path resolves one answer per service and this bill carries "
            f"more than one tariff for {', '.join(duplicates)} (a master account "
            "covers several units, BR-CUS-068). It cannot say which connection an "
            "answer belongs to, so it prices none of them.",
            service=duplicates[0],
        )

    serve_base = {"R3", "R4"} <= served
    serve_factor = "R5" in served
    serve_plan_version = "R1" in served
    serve_schedule = "R2" in served
    serve_taxes = "R7" in served

    # ── R1 · THE PLAN ID IS AN INVARIANT, NOT AN ANSWER (DEF-2839) ────────
    # The chain is handed this id and stamps it back, so the two sides are one
    # value by construction. It is checked rather than substituted, and a
    # difference is not a divergence to report — it means this run compared two
    # different accounts and no figure in it means anything.
    # Read ONLY when R1 is served: a caller that has not switched R1 on must not
    # be made to carry a plan on its resolution object at all.
    chain_plan_id = (
        str(getattr(getattr(resolved, "plan", None), "plan_id", "") or "")
        if serve_plan_version
        else ""
    )
    live_plan_id = str(getattr(data, "rate_plan_id", "") or "") if serve_plan_version else ""
    if serve_plan_version and chain_plan_id and live_plan_id != chain_plan_id:
        raise RuledPathRefused(
            "R1",
            f"the ruled path resolved plan {chain_plan_id!r} and the bill run gathered "
            f"plan {live_plan_id!r} for the same account. That is not a pricing "
            "disagreement — the two paths are looking at different accounts, so no "
            "figure produced for this account can be trusted.",
        )

    # PO ruling 2026-09-30 — which services bill a `$0.00` base because nobody
    # defined and bound one. Starts from what `gather` found and is RESTATED
    # per service from the chain's own answer below whenever R3 + R4 serve the
    # base, so the warning always describes the figure the bill actually uses.
    live_warnings = getattr(data, "warnings", ()) or ()
    base_not_set = set(bill_warnings.base_not_set_services(live_warnings))

    tariffs = []
    for config in data.tariffs:
        service = getattr(config, "service", "")
        if service in per_size:
            # CR-063 — see the note above `duplicates`. The live answer stands,
            # deliberately and by name.
            logger.info(
                "ruled path skipped %s for account %s: billed one line per size",
                service,
                data.account_no,
            )
            tariffs.append(config)
            continue
        if getattr(config, "covers_unit_id", None):
            # DEF-BIL-8724 — see the note above `services`. Priced by `gather`
            # from the empty unit's own plan; the live answer stands, by name.
            logger.info(
                "ruled path skipped %s for account %s: the base of empty unit %s",
                service,
                data.account_no,
                config.covers_unit_id,
            )
            tariffs.append(config)
            continue
        try:
            answer = resolved.service(service)
        except KeyError:
            raise RuledPathRefused(
                None,
                f"the ruled path resolved no schedule for {service!r}, which the bill "
                "run priced. The two paths disagree about which services this account "
                "takes, and that disagreement is the finding — it is reported, never "
                "reconciled by keeping one service on the old path.",
                service=service,
            ) from None
        changes: dict[str, Any] = {}
        if serve_schedule:
            # ── R2 · THE VERSION IS REBUILT INTO PRICES, NEVER STAMPED ─────
            # `_schedule_from_chain` returns `{}` when the chain named the
            # version the bill run already priced from, which is the only case
            # any real tenant produces today. See this module's R2 section.
            changes.update(
                _schedule_from_chain(
                    config,
                    answer,
                    service_date=service_date,
                    serve_base=serve_base,
                )
            )
        if serve_base:
            # ── DEF-2890 · THE MIRROR OF R2's OWN GATE, AND IT WAS MISSING ────
            # `_schedule_from_chain` refuses when R2 moves the version and the
            # base would be left behind (*"the prices would come from one
            # version while the base came from another"*). **The same bill can
            # be assembled the other way round**: switch R3 + R4 WITHOUT R2 and
            # the chain states the base while `gather` has already built every
            # tier, minimum and unit price from the version the LIVE path
            # resolved. If the two paths named different versions, this stamps
            # one version's base onto another version's ladder — the identical
            # unauditable bill, arrived at from the opposite side.
            #
            # It has never run on a real bill (no deployment names a step) and
            # the seeded utility has one version per schedule, so the two paths
            # cannot name different versions there — which is exactly why
            # nothing found it.
            #
            # The check is asked ONLY when R2 is off: with R2 on,
            # `_schedule_from_chain` has already rebuilt the ladder FROM the
            # chain's version, so there is nothing left to disagree with. A
            # `JOINT` entry welding R3/R4 to R2 was the alternative and is
            # rejected: it would force a rule nobody asked for to be switched on,
            # which is the widening `steps_served_by_chain` refuses by name.
            if not serve_schedule:
                chain_version_id = str(getattr(answer, "schedule_version_id", "") or "")
                live_version_id = str(getattr(config, "version_id", "") or "")
                if chain_version_id and live_version_id and chain_version_id != live_version_id:
                    raise RuledPathRefused(
                        "R4",
                        f"service {service}: the ruled path states the base charge from "
                        f"rate schedule version {chain_version_id} and the bill run "
                        f"priced every other figure on this service — the tier ladder, "
                        f"the minimum, the unit price — from version {live_version_id}. "
                        "The base would come from one version and the prices from "
                        "another, which is not a disagreement to report, it is a bill "
                        "nobody could audit. Switch the rate-schedule rule on as well so "
                        "one version states all of it, or make the two paths resolve the "
                        "same version.",
                        service=service,
                    )
            # ── PO ruling 2026-09-30 · ONLY A CHARGE CODE STATES A BASE ──────
            # *"if user did not define and bind base charges in rate schedule
            # - then as a default you take 0"*. The chain answers `not_set`
            # (with `0`) for exactly that — and it ALSO still answers
            # `schedule`, the RETIRED `tariff_versions.base_charge` column
            # (`BR-RAT-088`), for a tenant with no base code. Taking that figure
            # here would put the retired column back on a bill the live path
            # bills at `$0.00` with a warning under the same ruling, and
            # 2026-09-28's *"we will never take default value from plan $8.0 -
            # that is retired"* is the same fact one object over. So anything
            # but a charge code's answer bills `$0.00` and warns.
            source = getattr(answer, "base_source", None)
            if source in ("charge_code", "named_charge_code"):
                changes["base_charge"] = answer.base_charge
                base_not_set.discard(service)
            else:
                changes["base_charge"] = Decimal("0.0000")
                base_not_set.add(service)
        if serve_factor:
            changes["jurisdiction_factor"] = answer.money_factor
        tariffs.append(replace(config, **changes) if changes else config)

    stamped = tuple(step for step in STEPS if step in served)
    changed: dict[str, Any] = {"tariffs": tuple(tariffs), "resolution_steps": stamped}
    if serve_base and hasattr(data, "warnings"):
        # Restated in tariff order, so the warnings read in the bill's order.
        ordered = [
            getattr(config, "service", "")
            for config in tariffs
            if getattr(config, "service", "") in base_not_set
        ]
        changed["warnings"] = bill_warnings.with_base_not_set(live_warnings, ordered)
    if serve_taxes:
        changed["taxes"] = _taxes_from_chain(resolved, data)
    if serve_plan_version:
        # BR-RAT-007 — the version in force AT the service date, resolved by the
        # chain rather than by gather. It is recorded on the bill and prices
        # nothing; see the R1 note in this module's docstring.
        changed["rate_plan_version"] = getattr(
            getattr(resolved, "plan", None), "version", None
        )
    logger.info(
        "ruled path served %s for account %s", ", ".join(stamped), data.account_no
    )
    return replace(data, **changed)


def _rating_selector(name: str) -> Any:
    """A rating selector, resolved through BILLING'S ONE seam resolver.

    ⚠ **`gather._resolve` AND NOT `import_module`, DELIBERATELY.** That function
    is *"the ONE place a seam name becomes a callable"* and it is where
    `seam_batch.wrap` memoises a read for the length of one prepare pass. Its own
    comment says why it is wired there: *"a seam reached around this would be a
    seam nobody batched, and there would be no way to tell which"* (hard-won law
    2). R2's read is on that list by name, so reaching around it here would turn
    one read per plan into one read per service per account — which is the exact
    cost the fork was designed not to have.

    Imported late because `gather` imports THIS module at its top. The fork's
    call site is the last line of `gather_account`, so by the time anything here
    runs the module is fully imported and this is a dictionary lookup.
    """
    return import_module("apps.billing.gather")._resolve("rating", name)


def _decimal_or_none(value: Any) -> Decimal | None:
    """A stored money column as a `Decimal`, or `None` when nothing is stated.

    ⚠ **`None` AND `Decimal("0")` ARE DIFFERENT FACTS HERE AND MUST STAY THAT
    WAY.** `CR-013` part 1 makes a blank base mean *this size is not served* and
    `DEF-277` makes the bill refuse on it, while a stored `0.00` bills `$0.00`
    (PO 2026-08-19, *"print $0.00"*). So this never answers zero for an absence,
    and the comparison it feeds never reads one as the other.
    """
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError):  # pragma: no cover - defensive
        return None


def _schedule_from_chain(
    config: Any, answer: Any, *, service_date: date, serve_base: bool
) -> dict[str, Any]:
    """R2's fork — the chain's RATE SCHEDULE VERSION, rebuilt into prices.

    Returns the `TariffConfig` fields to replace, `{}` when there is nothing to
    replace, and raises `RuledPathRefused` when the rebuild cannot be made
    honestly. Read this module's R2 section for the whole argument; this
    docstring states what the code does, in order.

    ⚠ **THE ID IS NEVER SUBSTITUTED ON ITS OWN.** That is the entire reason R2
    could not ride the existing fork point: the chain hands back a version id
    and no prices, `gather` has already built every tariff from the LIVE path's
    version by the time this runs, and stamping one version's number onto
    another version's money is a lie every figure on the page agrees with.

    ⚠ **AND THE MAPPING IS `gather.version_fields_from`, REUSED, NOT COPIED.**
    It is the live path's own projection of rating's `pricing_inputs` dict onto
    the version half of `TariffConfig`, extracted for this caller in the same
    commit. A second copy is `DEF-434`'s defect one layer up — it would drift on
    the first rate shape that gained a column, silently, because both copies
    would still build a well-formed tariff.
    """
    service = getattr(config, "service", "")
    chain_version_id = str(getattr(answer, "schedule_version_id", "") or "")
    if not chain_version_id:
        raise RuledPathRefused(
            "R2",
            f"the ruled path resolved no rate schedule version for {service!r}, which "
            "the bill run priced. R2's whole answer is which version prices a service, "
            "so there is nothing to price this one from and no version is put in its "
            "place.",
            service=service,
        )

    live_version_id = str(getattr(config, "version_id", "") or "")
    if chain_version_id == live_version_id:
        # ── THE EQUAL CASE IS A PROVABLE NO-OP AND ISSUES NO READ ──────────
        # Same version, same service date, same connection size — so rebuilding
        # would re-derive byte for byte what is already on this tariff. This is
        # every account of every tenant measured so far (R2: 47 agree / 0
        # disagree, 2026-08-31), which is why R2 costs the run nothing until the
        # day the two paths genuinely disagree.
        return {}

    seam = _rating_selector("pricing_inputs_for_version_id")
    if seam is None:
        raise RuledPathRefused(
            "R2",
            f"the ruled path resolved rate schedule version {chain_version_id} for "
            f"{service!r} and rating publishes no way to read a named version's prices "
            "on this deployment, so the bill cannot be priced from it. Nothing is "
            "guessed and the live path's version is not kept — a rule the deployment "
            "asked the ruled path to serve has no answer.",
            service=service,
        )

    size_class = getattr(config, "size_class", None)
    # 🔒 BR-RAT-034 (built 2026-10-01) — the SAME served span `gather` counted
    # season days over, so the swapped-in version is split over the same days
    # against ITS OWN season calendar. Passed only to a rating that names the
    # two keywords; without them the version prices on one season, as before.
    span = getattr(config, "season_span", None)
    span_kwargs: dict[str, Any] = {}
    if span is not None:
        try:
            names = signature(seam).parameters
        except (TypeError, ValueError):  # pragma: no cover — unintrospectable callable
            names = {}
        if "period_start" in names and "period_end" in names:
            span_kwargs = {"period_start": span[0], "period_end": span[1]}
    chain_inputs = seam(chain_version_id, service_date, size_class, **span_kwargs)
    if chain_inputs is None:
        # BR-RAT-031 is the rule behind the second half of this sentence — a
        # version with no effective date is the resumable DRAFT, it has never
        # been in force, and no read path may treat it as either. The rule id
        # stays in this comment and out of the sentence (G28 / CR-016).
        raise RuledPathRefused(
            "R2",
            f"the ruled path resolved rate schedule version {chain_version_id} for "
            f"{service!r} and this utility has no priced version by that name — it is "
            "unknown, or it is a saved draft, which has never been in force and may "
            "never price anything. The bill refuses rather than falling back to the "
            "version the run resolved.",
            service=service,
        )

    # ── DEF-484's GATE, CARRIED ACROSS WITH ITS OWN SENTENCE ───────────────
    # The live path refuses when the version in force NAMES sizes and no size
    # could be resolved. The chain's version may name different ones, so the
    # gate is asked again HERE against the version actually being priced from —
    # not assumed to have been asked about a different version.
    sized_groups = tuple(chain_inputs.get("size_groups") or ())
    if sized_groups and not size_class:
        raise RuledPathRefused(
            "R2",
            f"service {service}: the rate schedule version the ruled path resolved "
            f"prices {', '.join(sized_groups)} differently from every other size, and "
            "this connection's size could not be resolved. The bill refuses rather "
            "than being priced on the every-size ladder, because that answer is right "
            "for a size the schedule does not name and wrong for one it does, and the "
            "two are indistinguishable on the document.",
            service=service,
        )

    # ── THE BASE CHARGE — THE ONE FACT THIS MODULE MAY NOT RE-DECIDE ───────
    # `TariffConfig.base_charge` is `gather._base_charge_for`'s answer, and from
    # 2026-09-28 (`DEF-BIL-7170`) that is the CHARGE CODE's amount and nothing
    # else — this comment named three figures, the plan's and this version's
    # among them, and both are retired and unread. The decision still cannot be
    # re-taken here, for the reason `gather` gives: *"a second place that
    # re-derives any of them is a second narrowing that can disagree with this
    # one."*
    #
    # When R3 and R4 are served too, the chain supplies the base outright and
    # there is nothing mixed. Otherwise the two versions' own columns must
    # AGREE, because that column WAS both the fallback value and BR-RAT-088's
    # migration-artefact tripwire — moving the version moved the one input of
    # the three that this fork can move.
    #
    # ⚠ **THAT REASON EXPIRED ON 2026-09-28 AND THE CHECK IS LEFT STANDING,
    # DELIBERATELY AND WITH A ROW AGAINST IT — `DEF-BIL-7310`.** PO: *"we will
    # never take default value from plan $8.0 - that is retired"*. The base now
    # comes from the CHARGE CODE alone, so `tariff_versions.base_charge` is
    # neither a fallback nor a tripwire and comparing it guards nothing. **What
    # the version CAN still move is the BINDING** —
    # `tariff_versions.base_charge_code` (`BR-RAT-1025`) — and that is the
    # column this comparison should be reading.
    #
    # It is not changed here for two reasons, both of them law 7's: this branch
    # runs only where R2 is served WITHOUT R3 and R4, which is no deployment
    # (`SERVED_BY_CHAIN_DEFAULT` is `R3,R4`), so the fix could not be proved on
    # a real configuration; and a guard that REFUSES fails closed, which is the
    # safe direction to leave it while it is wrong. **Changing it silently, on
    # a 🔒 money path, on the strength of an argument nobody can run, is how
    # the defect this ruling fixed was shipped in the first place.**
    if not serve_base:
        live_inputs = seam(live_version_id, service_date, size_class) if live_version_id else None
        if live_inputs is None:
            raise RuledPathRefused(
                "R2",
                f"service {service}: the ruled path would price this from rate schedule "
                f"version {chain_version_id} and the bill run's own version cannot be "
                "read back, so it cannot be shown that the base charge on this bill "
                "does not belong to the version being replaced. The base is statutory "
                "to the customer and it is not carried across on a guess.",
                service=service,
            )
        chain_column = _decimal_or_none(chain_inputs.get("base_charge"))
        live_column = _decimal_or_none(live_inputs.get("base_charge"))
        if chain_column != live_column:
            raise RuledPathRefused(
                "R2",
                f"service {service}: the ruled path prices this from a different rate "
                "schedule version than the bill run did, and the two versions state "
                f"different base charges of their own ({live_column} on the run's "
                f"version, {chain_column} on the ruled path's). The base charge on this "
                "bill was decided from three figures — the charge code's, the plan's "
                "and the version's — and two of them do not reach this point, so the "
                "prices would come from one version while the base came from another. "
                "That is not a disagreement to report, it is a bill nobody could "
                "audit. Switch R3 and R4 on with R2 so the ruled path states the base "
                "too, or make the two versions agree.",
                service=service,
            )

    # ── HARD RULE 3 · CONSUMPTION ALWAYS WITH AN EXPLICIT UNIT ─────────────
    # `billed_unit` is what every priced line on this service is measured in. A
    # version that states none would relabel the bill to nothing at all, and
    # assuming the live version's unit while pricing from the chain's ladder is
    # the same mixing this function refuses one field up.
    if not (chain_inputs.get("billed_unit") or ""):
        raise RuledPathRefused(
            "R2",
            f"service {service}: the rate schedule version the ruled path resolved "
            "states no unit of measure, so nothing on this service could be priced "
            "with the unit named. Consumption is never billed in an assumed unit.",
            service=service,
        )

    gather = import_module("apps.billing.gather")
    return dict(gather.version_fields_from(chain_inputs))


def _taxes_from_chain(resolved: Any, data: AccountBillingData) -> tuple[Any, ...]:
    """R7's fork — the chain's ATTACHED taxes, in the shape billing prices from.

    ⚠ **`discount_treatment` IS CARRIED ACROSS, NEVER DEFAULTED.** It is
    `BR-RAT-106` / `DEF-502`: statutory, stated per tax, deciding whether an
    authority levies on the subtotal BEFORE or AFTER a discount. The chain has
    no such field, so it is taken from the live rule this one matches — by
    `tax_id`, *"whose debt it is"*, an identity a rename does not move, and by
    `code` only as a fallback. `None` answers `before`, which is a real levy
    order and not an absence, so a chain tax matching no live rule REFUSES the
    account instead of being given one.

    Nothing here recomputes a tax. `resolve_taxes` has already applied R7's four
    applicability conditions, so this maps a decided answer and adds no rule.
    """
    seam = import_module("apps.billing.rating_seam")
    by_id = {str(rule.tax_id): rule for rule in data.taxes if rule.tax_id}
    by_code = {str(rule.code): rule for rule in data.taxes if rule.code}

    mapped: list[Any] = []
    for rule in getattr(resolved, "taxes", ()) or ():
        tax_id = getattr(rule, "tax_id", None)
        live = by_id.get(str(tax_id)) if tax_id else None
        if live is None:
            live = by_code.get(str(getattr(rule, "code", "")))
        if live is None:
            raise RuledPathRefused(
                "R7",
                f"the ruled path attached tax {getattr(rule, 'code', '?')!r} "
                f"(tax_id {tax_id!r}) and the bill run attached no rule matching it, so "
                "there is no `discount_treatment` to carry across. That figure is "
                "statutory and per authority (BR-RAT-106): it decides whether this tax "
                "levies before or after a discount, and defaulting it would be this "
                "product inventing a levy order on a money path.",
            )
        mapped.append(
            seam.TaxRule(
                code=getattr(rule, "code", ""),
                # DEF-RAT-9307 — the line's wording, taken from the live rule
                # like `discount_treatment` below, so the ruled path and the
                # bill run print the same words for the same tax.
                bill_label=getattr(live, "bill_label", None),
                rate=getattr(rule, "rate", None),
                tax_id=str(tax_id) if tax_id else None,
                flat_amount=getattr(rule, "flat_amount", None),
                discount_treatment=live.discount_treatment,
                applies_to_services=tuple(getattr(rule, "services", ()) or ()),
            )
        )
    return tuple(mapped)


# ── Lifecycle ─────────────────────────────────────────────
# packet: decision log 2026-08-27 *"HOW R1–R7 GETS WIRED INTO BILLING — run both,
#         compare, rule, then switch. Never swap and hope"* step 5 · step 1 of
#         12-governance/19-execution-sequence.md · DEF-438 · BR-BIL-038 (checked
#         and NOT triggered — `pipeline.SEQUENCE` and every stage signature are
#         untouched) · BR-BIL-055 · BR-BIL-039 · BR-SHL-020 · hard-won laws 1, 2
#         and 3
# generated: 2026-08-28 by the per-step switch lane (claude) · AMENDED 2026-08-31
#         by the CR-052 task 22 R2-fork lane (claude): `_schedule_from_chain`
#         REBUILDS the tariff from the rate schedule version the chain resolved,
#         through `gather.version_fields_from` (the live path's own mapping,
#         EXTRACTED not copied) and rating's `pricing_inputs_for_version_id`
#         (a by-id lookup in front of the projection `DEF-434` already made the
#         product's only one). The choice between rebuilding HERE and moving the
#         chain into `gather` is the decision log, 2026-08-31, *"R2's FORK IS
#         BUILT INSIDE `resolution_switch`, NOT INSIDE `gather`"* — a judgment
#         recorded rather than a question put to the PO (law 13)
# checklist: A✔ (backend) B=NOT BUILT ON PURPOSE — there is no screen for this
#         and there must not be one: the choice is a deployment's, not a
#         utility's (design decision 1), and drawing it would make a temporary
#         cutover control look like a product feature. The one thing a clerk
#         DOES see is the refusal row, which reaches the existing S31.2
#         exception tab through `gather`'s reason code and has its copy in all
#         eleven locales. C✔ (tests + data) D✔ (proved, both directions)
# gates: golden-verify 33 PASS / 0 FAIL before and after — no ❄️ B4/B5 figure is
#         asserted or moved here, and none can be while the setting is empty ·
#         G61 frozen-figures PASS (130 signed money figures) before and after ·
#         G28 unchanged at 546 raise sites both sides · run_gates unchanged ·
#         tests/test_br_bil_870_resolution_switch.py, and R2's seven cases were
#         proved RED in a detached worktree at the pre-fork commit first
# exceptions: (1) **NOTHING IS SWITCHED ON.** `SERVED_BY_CHAIN_DEFAULT` is empty
#         and `apply` returns its argument unchanged, so every bill this product
#         issues is priced by exactly the code that priced it yesterday.
#         Switching a rule is step 5 proper and needs its disagreement class
#         ruled at zero (step 4, not started).
#         (2) **SIX OF EIGHT STEPS HAVE A FORK** (R1, R2, R3, R4, R5, R7).
#         `R3b` and `R6` need their database half moved out of `gather` first.
#         Naming one of them REFUSES rather than being ignored.
#         (2b) **R2 MUST NOT BE SWITCHED ON UNTIL `DEF-2889` IS CLOSED** — the
#         chain drops a rate schedule version one day EARLY (`in_force_on` uses
#         `effective_to > service_date` where the live path uses `>=`, and
#         `rating.services` writes `effective_to = new_from - 1 day`), so on the
#         last day of a version the chain refuses an account the live path bills.
#         `DEF-2890` is the mirror, on R3 + R4 without R2, and is also open.
#         (3) **A SWITCHED RULE IS RESOLVED AT GATHER AND `with_readings` DOES
#         NOT RE-RESOLVE** (`DEF-2552`). Harmless for every forked rule — none of
#         the base charge, the money factor, the plan version, the tax set or the
#         schedule VERSION depends on a reading — and a real constraint on whoever
#         forks R3b.
#         (4) **THE OLD IMPLEMENTATION IS UNTOUCHED AND STILL SERVES EVERYTHING.**
#         Deleting it is step 6 and happens after a full billing cycle on the
#         chain.
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING 🔒 — rating math / money, a
#         CLAUDE.md sensitive path; row in 12-governance/09-human-review-ledger.md
#         which also asks the PO for the `human_owned.txt` glob this file has no
#         match in. Not RATIFIED without a recorded human sign-off.
# ──────────────────────────────────────────────────────────
