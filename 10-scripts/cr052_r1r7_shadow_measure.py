#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: THE PER-STEP DISAGREEMENT COUNT for the R1–R7 pricing cutover —
#            one whole prepared bill run, on real seeded rows, under enforced
#            row-level security, reported per step as
#            agree / disagree / could-not-evaluate.
# Change:   CR-052 task 20 (step 4 of the recorded R1–R7 cutover). The decision
#           log's own next action, written when step 3 landed: *"Run the shadow
#           across a **real run** rather than one account, and count the
#           disagreements per step."* Until this script existed that count did
#           not, so task 20's *"put the seven measured disagreement classes to
#           the PO"* named a measurement nobody could produce.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — the pass runs inside
#           `core.tenancy.tenant_context` and under a role RLS applies to) ·
#           BR-BIL-039 (the preview and the real run are the SAME code, so the
#           shadow is measured off `prepare_run`'s own output) · BR-RAT-007 ·
#           BR-RAT-087 (the server formats money; nothing here re-rounds one)
# Tests:    06-backend/tests/test_cr052_task20_shadow_measure.py — the RED
#           proofs (§ "A MEASUREMENT THAT CANNOT FAIL") asserted as cases.
# Impacts:  12-governance/02-decision-log.md (the published table) ·
#           12-governance/11-change-requests.md CR-052 task 20
# ───────────────────────────────────────────────────────
"""How much do the live path and the ruled R1–R7 chain disagree, PER STEP?

⚠ **THIS SCRIPT MEASURES AND PUBLISHES. IT CHANGES NOTHING ABOUT PRICING.**
It switches no step, it touches `resolution_switch.SERVED_BY_CHAIN_DEFAULT`
(empty) not at all, it reconciles no disagreement and it adds no narrowing to
`gather.py`. Every ruling on what to DO about a class is step 4 and is the
Product Owner's. A lane that makes a disagreement go away here has destroyed
the evidence the shadow exists to produce.

**IT WRITES NOTHING.** `runs.prepare_run` states *"Writes nothing"* in its own
docstring and `shadow_report.report_for_prepared` is a read over its output;
the whole pass is additionally wrapped in a transaction that is rolled back, so
the assertion is structural and not a promise.

── THE ONE THING THIS SCRIPT EXISTS TO GET RIGHT ────────────────────────────

**A STEP THE SHADOW CANNOT EVALUATE IS NOT A STEP THAT AGREES.** Conflating the
two is the single easiest way to produce a comfortable, false answer: seven of
the eight steps would report "0 disagreements" and six of those zeroes would
mean *nothing was ever asked*. So every step carries THREE numbers and a
reason, never two:

    agree                 the comparison RAN at this step and matched
    disagree              the comparison ran and differed, OR the chain
                          REFUSED at this step where the live path priced
    could not evaluate    the comparison did not run at this step — and the
                          REASON is carried, per account, never summarised away

── WHAT THE SHADOW CAN AND CANNOT SAY, READ OFF THE CODE RATHER THAN ASSUMED ─

Two 🔒 human-owned modules do the work and this script re-derives their
coverage from them at runtime rather than restating it:

* `resolution_shadow.compare()` emits a `Divergence` at **R1** (the plan
  version), **R2** (the schedule version in force), **R3b** (the billable
  quantity), **R4** (the base AMOUNT, with `base_source` naming which object
  supplied the chain's), **R5** (the jurisdiction factor on the money), **R6**
  (the granted discount set) and **R7** (the tax rules that attach).
  ⚠ **FOUR OF THOSE ARRIVED ON 2026-08-31 (`DEF-2798`)** — before that this
  function compared three things and their zeroes meant *nobody asked*.
  ⚠ **AND R3 LEFT THE LIST ON 2026-09-01 (`DEF-2878`)** — see below.
* `resolution.refusal_steps()` publishes every typed refusal the chain can
  raise → the step it refuses at. That is R1, R2, R3, R3b, R4, R5 and R6.
  **R7 raises nothing at all and never will** — a failed applicability condition
  means NO LINE rather than an error (`DEF-273`) — so R7 is refusable at no
  point and its comparison is the ONLY thing that can ever evaluate it.
* **R3 AND R4 ARE TOLD APART SINCE 2026-08-31 (`DEF-2823`).** The base used to
  be ONE fused `R3/R4` figure, so a joint agreement satisfied *"its own class is
  at zero"* for neither half and both read `47 could not evaluate` on a run
  where the base agreed on all 47 accounts. `BR-RAT-088` says where the seam is
  — *"R3's refusal semantics are unchanged … but the base itself now resolves
  through R4"* — so R3 is compared on the SIZE and R4 on the AMOUNT.
  ⚠ **AND R3's COMPARISON WAS NOT "PARTLY" CIRCULAR — IT WAS A CHECK THAT COULD
  NOT FAIL, AND IT IS RETIRED (`DEF-2878`, 2026-09-01).** This paragraph used to
  say the comparison was *partly* circular and independent on a master account,
  and the PO's cutover ruling took R3's hold on exactly that reading — *"run the
  comparison over a wider population"*. **A wider population could never have
  released it.** Both sides are ONE call to
  `metering.selectors.connection_size_for`: `gather._connection_size_for`
  resolves it, `resolution_shadow.adapt` resolves the SAME seam,
  `resolution.resolve_served_size` ends `return meter.connection_size`, and
  `compare()` then tested the first against the last. Every extra account added
  one more agreement of X with X.
  **Measured with `--sabotage R3-seam`:** the shared seam patched for the whole
  pass to answer `'W-2'` where it should answer `'W-58'` — the wrong tier ladder
  on every account, in BOTH implementations — left the table reading
  **R3 47 agree / 0 disagree / 0 cannot evaluate, unmoved**, `by_step` empty.
  So `compare()` now asserts the size as an INVARIANT (`DEF-2839`'s posture for
  R1's plan id) and R3 is reported as **cannot evaluate**, never as agreement.
  **R3's one independent piece of evidence is its REFUSAL** — `SizeNotServed`
  for a size absent from the schedule's own axis, which is the SCHEDULE's fact
  against the CONNECTION's and is enumerable with no population at all
  (`06-backend/tests/test_def2878_r3_refusal_is_independent.py`).

The consequence is stated here so no reader has to infer it: **a zero in the
"disagree" column is only evidence of agreement where the "agree" column is
non-zero.** Everywhere else it is the absence of a measurement.

── THE ROLE'S POSTURE IS PART OF THE FIGURE ─────────────────────────────────

Every figure this repo published on 2026-08-30 was measured on a login that
bypassed tenant separation and it changed the answer by a quarter. So this
script REFUSES to print a table until it has re-read `pg_roles` at runtime and
found `rolsuper = false, rolbypassrls = false` on the role it is connected as,
and until a query with NO tenant context has come back with zero rows. Both
assertions are `tests/isolation_helpers.py`'s, kept in that file's words. The
posture is printed beside the figures, because a figure without it is not a
figure.

    DJANGO_SETTINGS_MODULE=config.settings.local \
    DATABASE_URL=postgres://…/sbh_r1r7shadow?sslmode=disable \
    JOBS_EAGER=false \
    python3 10-scripts/cr052_r1r7_shadow_measure.py

    --json PATH     also write the whole body, unedited, as JSON
    --sabotage STEP prove the harness can FAIL — see below
    --cycle CODE    measure one cycle rather than every cycle with accounts
    --what-if MODE  open R3's gate inside the rolled-back transaction and report
                    what is behind it — `size-rows` or `size-rows+base`. **NOT
                    the measurement**, and every line of that run says so.

── A MEASUREMENT THAT CANNOT FAIL (`--sabotage`) ────────────────────────────

A sibling lane's first draft of a very similar harness printed *"no slowdown"*
because it measured a machine that had gone quiet, and this repo recorded six
checks in one day that could not distinguish pass from fail. So this script
carries its own mutation switch and the report quotes the result:

    --sabotage R1     rewrite ONE ready account's live `rate_plan_id`.
    --sabotage R3     rewrite one account's live CONNECTION SIZE to one the
                      schedule does not price — DEF-1810's own failure, a
                      3-inch connection resolving the 5/8 rate. ⚠ Since
                      `DEF-2878` this moves the account to `shadow_comparison_
                      raised`, NOT the R3 column: R3 is an invariant now.
    --sabotage R4     add $4.00 to one account's live BASE CHARGE — DEF-154's
                      exact shape, which the frozen golden suite cannot see
                      because B5 hands the base to the engine directly.
    --sabotage R3b    a THOUSANDFOLD error on one account's live billable
                      quantity — the meter multiplier's whole effect, on the
                      field the live path actually carries it in.
    --sabotage R5     add 1 to one account's live jurisdiction factor: on an
                      $8.00 base that is the difference between $8.00 and
                      $16.00.
    --sabotage R6     add a granted discount the catalogue does not offer.
    --sabotage R7     remove one tax rule the live path attached — a customer
                      not charged a tax an authority is owed.

    Each of the five MUST move its own step's column, and each is quoted in the
    decision log with the figures it moved.

    --sabotage R3b-tariff-mult
                      THE PREVIOUS LANE'S MUTATION, KEPT: a thousandfold error
                      on `TariffConfig.multiplier`. ⚠ It must still NOT move
                      anything, and that is now the CORRECT result rather than
                      the defect. That field is a trip-wire the pricing engine
                      REFUSES by name when it is not 1 (PO ruling 2026-08-11 —
                      metering applies the meter multiplier, the engine never
                      does), `gather` sets none, and nothing prices from it. It
                      is kept so the old proof can be re-run and read correctly.

    --sabotage estate-unsized
                      ⚠ **THE RED PROOF FOR THE ONLY CHECK HERE THAT LOOKS
                      OUTSIDE THE RUN (`DEF-2965`).**
                      `metering.selectors.connection_size_for` — the seam R3
                      itself resolves — is patched for the whole pass to answer
                      `None` for every WATER connection, as though nobody had
                      ever recorded a size. Every utility billing water MUST
                      read NOT MET and MUST name the billable accounts affected;
                      a verdict of MET means the estate scan is not reading
                      configuration. **The LIVE demonstration is the more
                      important half:** on `sbh_r3rel` this report read water
                      `MET` while twelve of that utility's water meters carried
                      no size at all, because the run's population is the
                      accounts already in a cycle and the failing case sits one
                      join outside it.

    --sabotage service-coverage
                      ⚠ **`DEF-2965`'s OWN SHAPE, REPRODUCED ON DEMAND.**
                      `resolution_shadow.adapt` is patched for the whole pass to
                      drop every WATER meter from the facts the shadow reads, so
                      the run stops examining a service the tenant still BILLS.
                      The report MUST name it as BILLED AND NOT EXAMINED and
                      MUST NOT read MET. This is the exact hole that let three
                      utilities read `MET` while no electric account had ever
                      been measured: the report named what it FOUND and never
                      what it LOOKED AT.

    --sabotage R3-seam
                      ⚠ **THE MUTATION THAT PROVES R3's COMPARISON IS CIRCULAR
                      (`DEF-2878`), AND IT MUST NOT MOVE THE R3 COLUMN.** Every
                      other mutation here breaks ONE side. This one breaks the
                      SHARED SOURCE: `metering.selectors.connection_size_for` is
                      patched BEFORE `prepare_run` opens, to a size that IS on
                      the schedule's axis, so both paths read it and the chain
                      resolves rather than refusing. The customer is then priced
                      on the wrong tier ladder by BOTH implementations and
                      `compare()` sees two equal strings. ⚠ **Whether that costs
                      money depends on the tenant's ladder and is NOT claimed
                      here:** on the seeded fixture every water size carries the
                      same base, so the amount is `$8.00` before and after. The
                      finding is about the comparison, not the fixture — R3
                      cannot see a wrong size on a flat ladder OR on a stepped
                      one, because it is not looking at two answers.
                      **On 2026-09-01, BEFORE the fix: `--sabotage R3` moved the
                      column (46/1) and this one did not (47/0). The difference
                      between them is the whole finding** — the first proves the
                      comparison EXPRESSION can fire, the second proves its two
                      INPUTS are one value. ⚠ **AFTER the fix neither moves it**,
                      because R3 is an invariant and is not counted at all, so
                      this switch is now a REGRESSION guard: if the R3 row ever
                      moves under it again, the circular comparison is back.

Both mutate a frozen dataclass in memory through `dataclasses.replace`, after
`prepare_run` has returned and before the shadow reads it. No row is written,
no pricing code is touched, and the database is identical afterwards.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
# A broker would time a queue and seed a sample utility per fixture; neither is
# wanted here (CLAUDE.md law 14's own mitigation).
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection, transaction  # noqa: E402

# `config.settings.local` sets DEBUG=True and Django then keeps every statement
# and its parameters in `connection.queries`. This is `cr051_run_benchmark.py`'s
# recorded reasoning, and it applies for the same reason.
settings.DEBUG = False

from apps.billing import runs, shadow_report  # noqa: E402
from apps.billing import resolution_shadow as shadow  # noqa: E402
from apps.billing import resolution_switch  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.rating import resolution  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.tenancy import selectors as tenancy_selectors  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

# ══════════════════════════════════════════════════════════════════════════
# The eight steps, and what the shadow can say about each
# ══════════════════════════════════════════════════════════════════════════

#: §A2's order. R3b sits between R3 and R4 because the chain runs it there, and
#: the order is the content of §A2 rather than decoration.
STEPS = ("R1", "R2", "R3", "R3b", "R4", "R5", "R6", "R7")

#: ⚠ **THE FUSED BASE ROW IS GONE (`DEF-2823`, 2026-08-31).** `compare()` used
#: to emit ONE `R3/R4` divergence for the per-service base charge, because
#: `ServiceResolution` carried one `base_charge` and `base_source` merely named
#: which object supplied it. A joint agreement satisfies *"its own class is at
#: zero"* for NEITHER half, so R3 and R4 both read `47 could not evaluate` on a
#: run where the base agreed on all 47 accounts.
#:
#: `BR-RAT-088` says where the seam is — *"R3's refusal semantics are unchanged
#: … but the base itself now resolves through R4"* — so **R3 is compared on the
#: connection SIZE and R4 on the AMOUNT**, each against the live path's own
#: answer to that same question. The constant survives as an assertion: if this
#: key ever comes back, the coverage check below FAILS rather than silently
#: reporting two steps as unevaluated again.
#:
#: ⚠ **AND THE SIZE HALF DID NOT SURVIVE ITS OWN SCRUTINY (`DEF-2878`,
#: 2026-09-01).** Separating R3 from R4 was right and R4's comparison is real —
#: two independent narrowings over one table. R3's was not: *"the live path's
#: own answer to that same question"* was the live path repeating the seam's
#: answer, and the chain repeating it back. R3 is an INVARIANT now and only its
#: REFUSAL is evidence.
FUSED_BASE = "R3/R4"

AGREE = "agree"
DISAGREE = "disagree"
CANNOT = "cannot_evaluate"

#: What a step's `cannot evaluate` means when `compare()` RAN and simply put no
#: figure beside the live path's at that step. The default is the old sentence;
#: R3 has its own because *"nothing is implemented"* would be wrong and
#: comforting — something WAS implemented, it compared a value with itself, and
#: a reader needs to know which of those two facts they are looking at.
UNCOMPARED_DEFAULT = "no_comparison_is_implemented_for_this_step"
UNCOMPARED_REASON = {
    "R3": (
        "DEF-2878:both_paths_read_metering.connection_size_for_so_the_comparison"
        "_was_one_value_compared_with_itself;compare()_now_asserts_it_as_an"
        "_invariant_and_R3's_evidence_is_its_REFUSAL_only"
    ),
}


def comparator_coverage() -> dict[str, set[str]]:
    """Which steps the shadow can COMPARE at and which it can REFUSE at.

    Re-derived from the two modules at runtime rather than restated, because a
    hand-written second copy of this map is exactly `DEF-2341` — a refusal class
    added to the chain came back `None` from a copied dict and its account
    silently vanished from the count.

    `compare()`'s coverage cannot be derived from a published function (there is
    none), so it is read from the `Divergence` step strings the function can
    construct — asserted against the source text below **in BOTH directions**, so
    that a step added to `compare()` and not added here fails loudly instead of
    being reported as *cannot evaluate* for ever, AND a step listed here that
    `compare()` no longer emits fails instead of being reported as *agree* on
    every account for ever.

    ⚠ **THE SCAN IS A REGEX AND THAT IS A FIX, NOT A TIDY-UP (`DEF-2798`).** It
    used to split the source on two literal strings — `'Divergence("'` and
    `'Divergence(\\n' + 20 spaces + '"'` — so it could only see a call whose step
    string sat at ONE indentation. The four comparisons added on 2026-08-31 put
    two of them at bill level, sixteen spaces in, and the old scan found neither:
    it would have reported `unexpected = {}` and been silently blind to exactly
    the steps it exists to notice. A check that cannot fail is worse than no
    check (`DEF-182`), and an indentation-sensitive one is a check that stops
    being able to fail the first time somebody reformats.
    """
    refusable = set(resolution.refusal_steps().values())
    #: Every step `compare()` puts a figure beside the live path's at. R3b, R5,
    #: R6 and R7 joined on 2026-08-31 (`DEF-2798`); before that they were the
    #: four steps whose zero meant *nobody asked*.
    #:
    #: ⚠ **R3 LEFT THIS SET ON 2026-09-01 (`DEF-2878`) AND THAT IS A CORRECTION,
    #: NOT A LOSS OF COVERAGE.** Both sides of R3's comparison were one call to
    #: `metering.connection_size_for` — `compare()`'s own block now traces the
    #: four hops — so its `47 agree` was 47 restatements of one value and a
    #: WIDER POPULATION could only ever add more of them. `compare()` asserts it
    #: as an invariant instead, exactly as `DEF-2839` did for R1's plan id, so
    #: the regex scan below no longer sees an `R3` divergence and this set must
    #: not claim one. **R3 is still REFUSABLE** (`SizeNotServed`), and a chain
    #: refusal at R3 is still counted as an R3 disagreement — that half was
    #: never circular and it is the half that can release the step.
    compared = {"R1", "R2", "R3b", "R4", "R5", "R6", "R7"}

    source = Path(shadow.__file__).read_text(encoding="utf-8")
    body = source.split("def compare(", 1)[1].split("\ndef ", 1)[0]
    seen = set(re.findall(r'Divergence\(\s*"([^"]+)"', body))
    if FUSED_BASE in seen:
        raise AssertionError(
            f"resolution_shadow.compare() emits a fused {FUSED_BASE!r} divergence again. "
            "DEF-2823 separated them because a joint agreement is evidence for NEITHER "
            "half, and the cutover's own rule is that a step switches only when its own "
            "class is at zero. Compare the connection SIZE at R3 and the AMOUNT at R4."
        )
    unexpected = seen - compared
    if unexpected:
        raise AssertionError(
            f"resolution_shadow.compare() now emits divergences at {sorted(unexpected)}, "
            "which this harness would report as 'cannot evaluate'. Add them to "
            "`compared` above — a coverage map that silently under-reports is the "
            "comfortable lie this whole script exists to refuse."
        )
    missing = compared - seen
    if missing:
        raise AssertionError(
            f"this harness claims resolution_shadow.compare() compares {sorted(missing)} "
            "and its source emits no divergence at those steps, so every account would "
            "be counted as AGREEING at a step nothing was ever compared at — the exact "
            "failure DEF-2798 was filed for, in the opposite direction."
        )
    return {"compared": compared, "refusable": refusable}


def _verdicts_for(outcome_row: dict, coverage: dict[str, set[str]]) -> dict[str, tuple[str, str]]:
    """One account -> {step: (verdict, reason)} for all eight steps.

    THE THREE CASES, and each one is a ruling about what the evidence supports:

    **(1) `not_attempted`.** The adapter could not assemble the chain's inputs,
    or the account's row could not be read back, or the comparison raised. The
    chain was never run, so NO step was evaluated — all eight are
    `cannot_evaluate` carrying the blocked reason verbatim.

    **(2) `chain_refused`.** The chain refused at one named step. That step
    DISAGREES, and it is the highest-value row in the exercise: the ruled path
    refuses where the live path produced a number — a bill that would have gone
    out on a guess. **Every OTHER step is `cannot_evaluate`**, because
    `shadow_account` returns on the refusal and `compare()` is never called: not
    one figure was put beside another on this account.

    **(3) `agreed` / `disagreed`.** `compare()` ran. A step it covers agrees
    unless a divergence names it; a step it does not cover is `cannot_evaluate`
    — never `agree`. That last clause is the whole point of the column.
    """
    status = outcome_row["status"]
    verdicts: dict[str, tuple[str, str]] = {}

    if status == shadow.STATUS_NOT_ATTEMPTED:
        reason = outcome_row.get("blocked_reason") or "not_attempted"
        return {step: (CANNOT, f"not_attempted:{reason}") for step in STEPS}

    if status == shadow.STATUS_CHAIN_REFUSED:
        refused_at = outcome_row.get("refusal_step")
        for step in STEPS:
            if step == refused_at:
                verdicts[step] = (DISAGREE, f"chain_refused:{outcome_row.get('refusal_type')}")
            else:
                verdicts[step] = (
                    CANNOT,
                    f"chain_refused_at_{refused_at or 'an_unmapped_class'}"
                    "_so_compare_never_ran",
                )
        return verdicts

    # compare() ran.
    differed = {row["step"] for row in outcome_row.get("divergences", ())}
    for step in STEPS:
        if step in coverage["compared"]:
            verdicts[step] = (
                (DISAGREE, "figures_differ") if step in differed else (AGREE, "figures_match")
            )
        else:
            verdicts[step] = (CANNOT, UNCOMPARED_REASON.get(step, UNCOMPARED_DEFAULT))
    return verdicts


def switchability() -> dict[str, tuple[bool, str]]:
    """Per step: **can this deployment switch it on at all**, and if not, why.

    ⚠ **THIS COLUMN EXISTS BECAUSE ITS ABSENCE REACHED THE PRODUCT OWNER
    (`DEF-2838`, 2026-08-31).** The step-4 cutover options were put to them for
    all eight steps. The PO ruled R1, R2, R4 and R7 switchable — and
    `resolution_switch.FORKED` could serve only R3, R4 and R5, so **not one of
    the four could be switched and the first wave was zero steps, not three.**

    **The reason nothing caught it is worth stating, because it is a shape and
    not an oversight.** This harness answers *do the two paths AGREE at this
    step*. Whether a step CAN BE SWITCHED is a different question about a
    different module, and the table never asked it — so a step with no seam sat
    in the agreement table looking exactly like a step ready to go. A ruling made
    from an incomplete table is not a ruling that needs re-taking; it is a table
    that needs fixing, and this is the fix.

    **DERIVED AT RUNTIME FROM `resolution_switch.FORKED` AND `JOINT`, NEVER
    RESTATED.** `comparator_coverage()` above re-derives the comparator's own
    coverage for exactly this reason and records what a hand-written copy costs
    (`DEF-2341`): a copied map cannot see a change made after it was written, so
    it would go on printing *switchable* for a step whose fork was removed.

    The JOINT clause is carried too, because `BR-BIL-873` makes R3 and R4 one
    decision — a step that is forked but may not move ALONE is not switchable on
    its own, and saying otherwise is how R4 came to be offered without R3.
    """
    forked = set(resolution_switch.FORKED)
    partners: dict[str, set[str]] = {}
    for pair in resolution_switch.JOINT:
        for step in pair:
            partners.setdefault(step, set()).update(set(pair) - {step})

    answers: dict[str, tuple[bool, str]] = {}
    for step in STEPS:
        if step not in forked:
            answers[step] = (
                False,
                "no fork in this build — steps_served_by_chain() refuses the name",
            )
            continue
        welded = sorted(partners.get(step, set()))
        if welded:
            answers[step] = (
                True,
                "only together with " + ", ".join(welded) + " (BR-BIL-873)",
            )
        else:
            answers[step] = (True, "")
    return answers


def per_step_table(body: dict, coverage: dict[str, set[str]]) -> list[dict]:
    """The deliverable: EIGHT rows, four columns and a reason breakdown.

    ⚠ **THE NINTH `R3/R4` ROW IS GONE (`DEF-2823`).** It existed because the
    base was one fused figure and the joint agreement had to be reported
    somewhere it was true. R3 and R4 now each carry their own comparison, so
    reporting a fused row as well would double-count 47 accounts and, worse,
    would let a reader take the joint figure as evidence for either half — the
    exact reading the cutover's *"only when its own class is at zero"* rule
    forbids.
    """
    switchable = switchability()
    rows = {
        step: {
            "step": step,
            AGREE: 0,
            DISAGREE: 0,
            CANNOT: 0,
            "reasons": Counter(),
            "can_compare": step in coverage["compared"],
            "can_refuse": step in coverage["refusable"],
            # DEF-2838 — "is anything switched ON" was already printed; "what
            # COULD be" was not, and those are different questions.
            "switchable": switchable[step][0],
            "switchable_note": switchable[step][1],
        }
        for step in STEPS
    }
    for outcome_row in body["accounts_detail"]:
        verdicts = _verdicts_for(outcome_row, coverage)
        for step, (verdict, reason) in verdicts.items():
            rows[step][verdict] += 1
            rows[step]["reasons"][reason] += 1
    for row in rows.values():
        row["reasons"] = dict(sorted(row["reasons"].items(), key=lambda kv: -kv[1]))
    return [rows[step] for step in STEPS]


# ══════════════════════════════════════════════════════════════════════════
# THE SUPPLEMENTARY R1/R2 PROBE — and why it is separate from the table above
# ══════════════════════════════════════════════════════════════════════════
#
# `resolve()` runs R1 → R2 → R3 → R3b → R4 → R5 → R6 → R7 **in that order and
# once**, and `shadow_account` returns on the first refusal. So when the chain
# refuses at R3 — which on this database it does on every account — `compare()`
# is never called and R1 and R2 report `cannot evaluate` even though the chain
# RAN them and did not refuse.
#
# That is the correct verdict for the shadow's own table: no figure was put
# beside another, so there is no agreement evidence. But the evidence is
# obtainable, and leaving it unobtained would answer *"we know nothing about
# seven of eight steps"* where two of them can be measured today.
#
# So this probe calls the chain's OWN published R1 and R2 — `resolve_plan` and
# `resolve_schedule`, the same two functions `resolve()` calls — on the SAME
# adapted inputs, and applies `compare()`'s comparison expressions VERBATIM:
#
#     R1   str(data.rate_plan_id) != str(plan.plan_id)
#     R2   str(config.version_id) != str(schedule.version_id)
#
# plus `compare()`'s two asymmetric cases (a service the chain resolved and the
# live path did not, and the reverse). It prices nothing, writes nothing and
# resolves no step past R2.
#
# ⚠ **IT IS REPORTED IN ITS OWN COLUMN AND NEVER FOLDED INTO THE SHADOW'S.**
# The shadow's table is what the 🔒 human-owned modules say; this is what a
# second, narrower read of the same rows says. Presenting them as one number
# would let this script's arithmetic be mistaken for the chain's.


def probe_r1_r2(prepared, rows: dict) -> dict:
    """R1 and R2 agreement, on accounts whose chain refuses further down."""
    resolution_module, catalogue_module = shadow._rating()
    base = shadow._refusal_base() or ()
    counts = {
        step: {AGREE: 0, DISAGREE: 0, CANNOT: 0, "reasons": Counter(), "examples": []}
        for step in ("R1", "R2")
    }

    for data in prepared.ready:
        account = rows.get(str(data.account_id))
        if account is None:
            for step in ("R1", "R2"):
                counts[step][CANNOT] += 1
                counts[step]["reasons"]["account_row_could_not_be_read_back"] += 1
            continue
        inputs = shadow.adapt(data, account=account)
        if inputs.blocked_reason is not None:
            for step in ("R1", "R2"):
                counts[step][CANNOT] += 1
                counts[step]["reasons"][f"adapter_blocked:{inputs.blocked_reason}"] += 1
            continue
        catalogue = catalogue_module.build_catalogue(
            plan_id=inputs.plan_id,
            service_date=prepared.service_date,
            # R7's narrowing facts, REQUIRED since `DEF-2824`. This probe only
            # reads R1 and R2 off the catalogue, but a catalogue built without
            # them is the wrong catalogue and must not be constructible.
            account=inputs.account,
            premises=inputs.premises,
            unmetered_services=inputs.unmetered_services,
        )
        # ── R1 ──────────────────────────────────────────────────────────
        try:
            plan = resolution_module.resolve_plan(
                catalogue, inputs.account, prepared.service_date
            )
        except base as refusal:  # type: ignore[misc]
            counts["R1"][DISAGREE] += 1
            counts["R1"]["reasons"][f"chain_refused:{type(refusal).__name__}"] += 1
            if len(counts["R1"]["examples"]) < 3:
                counts["R1"]["examples"].append(f"{data.account_no}: {refusal}")
            counts["R2"][CANNOT] += 1
            counts["R2"]["reasons"]["R1_refused_so_R2_was_never_reached"] += 1
            continue
        # ⚠ **THIS EXPRESSION IS `compare()`'s AND MUST NOT DRIFT FROM IT**
        # (`DEF-2839`). It used to read `data.rate_plan_id != plan.plan_id`,
        # which is a CHECK THAT CANNOT FAIL: the catalogue is built as
        # `build_catalogue(plan_id=inputs.plan_id, …)` where `inputs.plan_id` IS
        # `data.rate_plan_id`, and `plan_version_facts` stamps it back onto the
        # row it yields. Both sides were one value by construction, so R1's
        # `47 agree` was 47 restatements of a single id and this probe's
        # `figures_differ` counter was unreachable — 94 account evaluations
        # across a clean run and a `--sabotage R1` run produced it NOT ONCE.
        # The comparable half is the VERSION, which never reaches the chain.
        if str(data.rate_plan_id) != str(plan.plan_id):
            # Not a divergence: the shadow's own plumbing is broken and no
            # figure in this run means anything. `compare()` raises on it.
            counts["R1"][CANNOT] += 1
            counts["R1"]["reasons"]["adapter_handed_the_chain_a_different_plan"] += 1
            counts["R2"][CANNOT] += 1
            counts["R2"]["reasons"]["R1_plumbing_broken_so_R2_was_never_reached"] += 1
            continue
        if str(data.rate_plan_version) != str(getattr(plan, "version", None)):
            counts["R1"][DISAGREE] += 1
            counts["R1"]["reasons"]["figures_differ"] += 1
            if len(counts["R1"]["examples"]) < 3:
                counts["R1"]["examples"].append(
                    f"{data.account_no}: live plan version {data.rate_plan_version}, "
                    f"ruled plan version {getattr(plan, 'version', None)}"
                )
        else:
            counts["R1"][AGREE] += 1
            counts["R1"]["reasons"]["figures_match"] += 1

        # ── R2 ──────────────────────────────────────────────────────────
        live_by_service = {config.service: config for config in data.tariffs}
        seen: set[str] = set()
        service_verdicts: list[str] = []
        for service in plan.services:
            seen.add(service)
            try:
                schedule = resolution_module.resolve_schedule(
                    catalogue, plan, service, prepared.service_date
                )
            except base as refusal:  # type: ignore[misc]
                service_verdicts.append(DISAGREE)
                counts["R2"]["reasons"][f"chain_refused:{type(refusal).__name__}"] += 1
                if len(counts["R2"]["examples"]) < 3:
                    counts["R2"]["examples"].append(f"{data.account_no}: {refusal}")
                continue
            config = live_by_service.get(service)
            if config is None:
                service_verdicts.append(DISAGREE)
                counts["R2"]["reasons"]["the_live_path_resolved_no_tariff_for_this_service"] += 1
                if len(counts["R2"]["examples"]) < 3:
                    counts["R2"]["examples"].append(
                        f"{data.account_no}: {service} — live resolved no tariff, "
                        f"ruled resolved version {schedule.version_id}"
                    )
            elif str(config.version_id) != str(schedule.version_id):
                service_verdicts.append(DISAGREE)
                counts["R2"]["reasons"]["figures_differ"] += 1
                if len(counts["R2"]["examples"]) < 3:
                    counts["R2"]["examples"].append(
                        f"{data.account_no}: {service} — live version {config.version_id}, "
                        f"ruled version {schedule.version_id}"
                    )
            else:
                service_verdicts.append(AGREE)
        for service in live_by_service:
            if service not in seen:
                service_verdicts.append(DISAGREE)
                counts["R2"]["reasons"][
                    "the_ruled_path_resolved_no_schedule_for_a_service_the_live_path_priced"
                ] += 1
                if len(counts["R2"]["examples"]) < 3:
                    counts["R2"]["examples"].append(
                        f"{data.account_no}: {service} — the ruled path resolved no schedule "
                        "for a service the live path priced"
                    )
        # The account is the unit of the count, as it is everywhere else: one
        # account disagreeing on one of five services is a disagreeing account.
        if not service_verdicts:
            counts["R2"][CANNOT] += 1
            counts["R2"]["reasons"]["the_plan_covers_no_services"] += 1
        elif DISAGREE in service_verdicts:
            counts["R2"][DISAGREE] += 1
        else:
            counts["R2"][AGREE] += 1
            counts["R2"]["reasons"]["figures_match"] += 1

    for row in counts.values():
        row["reasons"] = dict(sorted(row["reasons"].items(), key=lambda kv: -kv[1]))
    return counts


def _service_has_a_base_charge_code(service_code: str) -> bool:
    """Does this tenant declare an `is_base` charge code for this service?

    `BR-RAT-088` (PO 2026-08-20) makes the charge code the ONE source of a
    service's base amount, so a service without one has **no base at all** —
    R4 refuses the account by name rather than billing `$0.00` for it, and
    `BR-BIL-872` gives that refusal no fallback. This is therefore a precondition
    for switching R3 + R4 on a utility, exactly as much as the size axis is.

    Read straight off `charges`, with no repair: a soft-deleted code does not
    count, and the CLASS scoping (`BR-RAT-108`) is not applied because R4 does
    that narrowing itself — a service with a code scoped to the wrong class
    fails at R4 with its own sentence, which is a different finding from having
    no code at all and must not be reported as this one.
    """
    from apps.rating import models as rating_models

    return rating_models.Charge.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        deleted_at__isnull=True,
        is_base=True,
        service__code=service_code,
    ).exists()


#: `--sabotage estate-unsized` un-records the connection size of this service's
#: meters. Water, because it is the service every measured utility bills — a
#: sabotage on a service a utility does not carry proves nothing.
ESTATE_SABOTAGE_SERVICE = "water"

#: `--sabotage service-coverage` removes this service from the RUN's population
#: while leaving it enabled on the tenant. Water for the same reason.
COVERAGE_GAP_SERVICE = "water"


def what_the_estate_holds(prepared_unit_ids: set[str]) -> dict:
    """**The question the prepared run cannot answer: does this UTILITY hold a
    billable account whose connection size is not recorded?**

    ⚠ **THIS IS THE THIRD TIME THIS REPO HAS SHIPPED A MEASUREMENT WHOSE
    POPULATION COULD NOT CONTAIN THE FAILING CASE, AND IT IS THE ONE THAT
    MATTERS MOST (`DEF-2965`).** `DEF-2878` was R3's comparison comparing one
    value with itself; `DEF-2923` was a base-code check over three utilities
    that all had base codes; this is the same shape once more, and its
    sharpest form. Measured on `sbh_r3rel`, tenant `brazosbend`:

        service   | meters | with a size | without
        electric  |      8 |           0 |       8
        water     |     61 |          49 |      12

    **The electric half is the obvious one and it is not the important one.**
    Water was reported `MET` while twelve of its meters carried no size. The
    report was not lying: it measures the accounts a PREPARED RUN contains, and
    that population holds only accounts already in a cycle, whose meters already
    have sizes. **So the blindness was never "electric was not enabled in the
    population" — it is that the population is drawn from the RUN, and the
    failing case sits one join outside it.** Naming the services examined
    catches the electric half and does nothing for those twelve water meters,
    because water *was* examined.

    So this asks the ESTATE. For every service point this utility holds that a
    live service agreement attaches to an account, it asks the ENGINE'S OWN
    SEAM — `metering.selectors.connection_size_for`, the function R3 itself
    resolves — whether a size comes back. It needs no prepared run at all,
    which is also why it can be asked for a utility that has no cycle yet.

    ⚠ **IT ASKS THE SEAM RATHER THAN RE-JOINING THE TABLES IN SQL, AND THAT IS A
    JUDGMENT WITH A REASON.** A second implementation of *"does this connection
    have a size"* would be free to disagree with R3 — the seam answers `None`
    for two meters that disagree about the size, and counts only meters
    CURRENTLY assigned, and a hand-written join that missed either rule would
    report a clean estate over accounts R3 refuses. **This is a CENSUS and not a
    comparison, so asking one source twice is not `DEF-2878`'s tautology**:
    there is no second answer here for the first to agree with. What the seam
    buys is that this report cannot come to a different verdict from the step it
    is clearing — the same reason `what_the_run_carries` calls
    `resolve_served_size` instead of reimplementing it.

    ⚠ **IT REPORTS ACCOUNTS, NOT ONLY METERS.** Eight accounts is the number a
    person acts on; twenty meters is trivia until it is joined to who stops
    being billed.

    **A recorded size missing on a BANDED service is configuration the utility
    has not finished, not a defect in the engine.** The PO ruled on 2026-08-28
    that we charge on the size the account actually has, and you cannot charge
    on a size you do not have. The only thing this check settles is whether they
    find out on the preflight or on billing day.
    """
    from apps.customers import models as customers_models
    from apps.metering import selectors as metering_selectors

    tenant_id = core_tenancy.current_tenant_id()
    points = list(
        metering_models.ServicePoint.objects.select_related("service")
        .filter(tenant_id=tenant_id, deleted_at__isnull=True)
        .values_list("id", "unit_id", "service__code")
    )
    live_agreements = list(
        customers_models.ServiceAgreement.objects.filter(
            tenant_id=tenant_id, ended_on__isnull=True
        ).values_list("service_point_id", "account_id")
    )
    accounts_by_point: dict[str, set[str]] = {}
    for point_id, account_id in live_agreements:
        accounts_by_point.setdefault(str(point_id), set()).add(str(account_id))

    by_service: dict[str, dict] = {}
    for point_id, unit_id, service_code in points:
        attached = accounts_by_point.get(str(point_id)) or set()
        row = by_service.setdefault(
            service_code,
            {"points": 0, "points_unsized": 0, "accounts": set(), "accounts_unsized": set()},
        )
        row["points"] += 1
        row["accounts"].update(attached)
        # The engine's own seam. `None` means "this connection's size is
        # unresolved" — no meter, no recorded size, or two meters disagreeing —
        # and R3 refuses on exactly that answer.
        if metering_selectors.connection_size_for(unit_id, service_code) is None:
            row["points_unsized"] += 1
            row["accounts_unsized"].update(attached)

    banded = _banded_services()
    out = {}
    for service_code, row in sorted(by_service.items()):
        out[service_code] = {
            "connections": row["points"],
            "connections_with_no_size": row["points_unsized"],
            "billable_accounts": len(row["accounts"]),
            # ⚠ ONLY the accounts a live agreement attaches. A service point
            # nobody is billed for cannot stop a bill, and counting it would
            # inflate the number a person is being asked to act on.
            "billable_accounts_with_no_size": len(row["accounts_unsized"]),
            "banded": service_code in banded,
            #: How many of this service's connections the PREPARED RUN reached.
            #: The gap between this and `connections` is the report's blind
            #: spot, stated rather than left to be inferred.
            "connections_the_run_examined": sum(
                1 for _pid, unit_id, code in points
                if code == service_code and str(unit_id) in prepared_unit_ids
            ),
        }
    return out


def _banded_services() -> set[str]:
    """Which services have ratified connection-size bands at all.

    An unsized meter only stops a bill where the service HAS bands: sewer is
    ruled to have none (it is a share of the water usage charge), and thermal
    steam and battery are `OQ-560`/`OQ-561` — *"nobody has said"*, which is a
    third answer again. `apps.tenancy.service_size_classes` keeps the three
    apart and this collapses them for one purpose only: deciding whether a
    missing size is a finding. Where it is not banded, it is not.
    """
    from apps.tenancy import service_size_classes

    banded = set()
    for code in service_size_classes.RATIFIED_SERVICE_SIZE_CLASSES:
        try:
            if service_size_classes.size_classes_for_service(code):
                banded.add(code)
        except Exception:  # noqa: BLE001 — an unruled service is not "banded"
            continue
    return banded


def what_the_run_carries(prepared, rows: dict) -> dict:
    """The (service · size) pairs R3 is asked about, **and whether anything
    prices each one.**

    ⚠ **THIS IS R3's RELEASE CONDITION AS EXECUTABLE WORK, and it replaces a
    report that could only ever list (`DEF-2878`, PO ruling 2026-09-01).** The
    comparison this harness was built around asked the same seam the same
    question twice and reported the echo as agreement, so `47 of 47 agree` was
    never evidence and no wider population could have made it so. What IS
    independent at R3 is the REFUSAL: the size is the CONNECTION's fact and the
    axis is the CONFIGURATION's, so neither side hands the other its answer.

    So the question this function answers is the one that decides a switch:
    **on this utility, does every (service · size) pair its accounts actually
    carry have something pricing it?** Where the answer is yes, R3 resolves and
    the ruled path bills what the live path bills. Where it is no, R3 REFUSES
    the account (`BR-BIL-872` — no fallback) while the live path prices it
    today on the every-size ladder. That difference is real money, and it is
    the only thing switching R3 can cost.

    ⚠ **THE AXIS IS THE CHARGE CODE's FROM 2026-09-01 (`BR-RAT-1010`)** — PO
    verbatim, *"rate schedule will not provdie the size, charge code will
    provide"*. The `source` column below says which object answered for each
    pair, because a missing size is cured on the charge-code screen or on the
    rate schedule depending on that answer, and a report that names the wrong
    one sends a person to a screen where the fix is not.

    **It asks the chain, it does not re-implement it.** `resolve_served_size`
    is called — the same function R3 calls — so this report cannot come to a
    different verdict from the step it is clearing.
    """
    resolution_module, catalogue_module = shadow._rating()
    base = shadow._refusal_base() or ()

    pairs: Counter = Counter()
    services: Counter = Counter()
    unmetered: Counter = Counter()
    #: pair -> {"priced": bool, "source": str, "detail": str}
    verdicts: dict[str, dict] = {}
    unknown = 0
    for data in prepared.ready:
        account = rows.get(str(data.account_id))
        if account is None:
            continue
        inputs = shadow.adapt(data, account=account)
        if inputs.blocked_reason is not None:
            continue
        catalogue = None
        plan = None
        try:
            catalogue = catalogue_module.build_catalogue(
                plan_id=inputs.plan_id,
                service_date=prepared.service_date,
                account=inputs.account,
                premises=inputs.premises,
                unmetered_services=inputs.unmetered_services,
            )
            plan = resolution_module.resolve_plan(
                catalogue, inputs.account, prepared.service_date
            )
        except Exception:  # noqa: BLE001 — an unresolvable plan is R1's finding, not R3's
            catalogue = None
        for meter in inputs.meters:
            key = f"{meter.service} · {meter.connection_size}"
            pairs[(meter.service, meter.connection_size)] += 1
            services[meter.service] += 1
            if key in verdicts:
                continue
            if catalogue is None or plan is None:
                unknown += 1
                verdicts[key] = {
                    "priced": None,
                    "source": "",
                    "detail": "the plan could not be resolved, so R3 was never reached",
                }
                continue
            try:
                schedule = resolution_module.resolve_schedule(
                    catalogue, plan, meter.service, prepared.service_date
                )
            except base as refusal:  # type: ignore[misc]
                unknown += 1
                verdicts[key] = {
                    "priced": None,
                    "source": "",
                    "detail": f"no schedule resolved ({type(refusal).__name__}), so R3 "
                    "was never reached — an R2 finding, not an R3 one",
                }
                continue
            source = getattr(schedule, "size_axis_source", "schedule")
            try:
                resolution_module.resolve_served_size(schedule, meter)
            except base as refusal:  # type: ignore[misc]
                verdicts[key] = {"priced": False, "source": source, "detail": str(refusal)}
            else:
                verdicts[key] = {
                    "priced": True,
                    "source": source,
                    "detail": (
                        "priced by the service's base charge code"
                        if source == "charge_code"
                        else f"priced by rate schedule version {schedule.version_id}"
                    ),
                }
        for service in inputs.unmetered_services:
            unmetered[service] += 1

    # ── AND THE OTHER HALF OF "CAN THIS UTILITY BE SWITCHED" (`DEF-2923`) ──
    # ⚠ **THE REPORT ABOVE WAS BLIND TO THIS AND SAID `MET` ANYWAY.** It asks
    # whether the SIZE is priced and stops there, so it read `0 unpriced · MET`
    # on three utilities while a fourth — any tenant that has declared no
    # `is_base` charge code — would have had every account of that service
    # REFUSED the moment the pair was switched on. `BR-RAT-088` makes the charge
    # code the ONLY source of a base amount, and `_guard_base_charge_code`
    # deliberately does not fire for a tenant with no base code ANYWHERE, which
    # was right while nothing was switched on and is exactly the hole once
    # something is.
    #
    # The three utilities measured on 2026-09-01 all carry seeded base codes
    # (`DEF-455`), so the population could not contain the failing case: **`163
    # unchanged · 0 refused` was true and incomplete.** A preflight that can only
    # report on well-configured tenants is not a preflight, so it asks here.
    # ⚠ **ASKED OF EVERY SERVICE THE TENANT BILLS, NOT ONLY OF THE ONES THIS RUN
    # SAW (`DEF-2965`).** The block below already names an enabled service the
    # pass never examined; this asks the OTHER question about that same service
    # — has the utility declared its base charge code — because R4 refuses every
    # account of a service that has none and the answer does not depend on any
    # account reaching the adapter. Measured with `--sabotage no-base-code` on
    # `sbh_r3rel`: `brazosbend` now names ELECTRIC, the service it bills and
    # this pass never sees, where before it named only water.
    try:
        billed = sorted(tenancy_selectors.enabled_service_codes())
    except Exception:  # noqa: BLE001 — reported as unknown, never guessed
        billed = []
    base_codes = {}
    for service in dict.fromkeys([*billed, *services, *unmetered]):
        try:
            base_codes[service] = _service_has_a_base_charge_code(service)
        except Exception as exc:  # noqa: BLE001 — reported, never guessed
            base_codes[service] = None
            verdicts.setdefault(f"{service} · base charge code", {})
    # ── AND THE THIRD PRECONDITION, WHICH IS *WHICH SERVICES DID I EVEN LOOK
    # AT* (`DEF-2965`, 2026-09-01) ──────────────────────────────────────────
    # ⚠ **THIS REPORT PRINTED `MET` OVER A SERVICE IT HAD NEVER SEEN, AND THAT
    # IS HOW THE ELECTRIC CASE ESCAPED.** Everything above is derived from the
    # accounts that actually reached the adapter, so a service the tenant BILLS
    # but whose accounts never got that far contributes no pair, no verdict and
    # no complaint — it simply is not in the answer. On 2026-09-01 the three
    # measured utilities billed only water, sewer and trash, so `0 unpriced ·
    # MET` was true of water and silent about **electric**, where a meter with
    # no recorded `size_class` is refused by R3 by name and every electric bill
    # stops. `DEF-2878`'s shape for the third time: a measurement whose
    # population cannot contain the failing case.
    #
    # So the report now states the tenant's OWN enabled services beside the ones
    # it measured, and the verdict below refuses to say a bare `MET` while any
    # enabled service is missing from that set. **A silence is not a pass** —
    # this file already says so for a utility that carried no pair at all, and
    # this is the same sentence one level finer.
    try:
        enabled = sorted(tenancy_selectors.enabled_service_codes())
    except Exception:  # noqa: BLE001 — reported as unknown, never guessed
        enabled = None
    return {
        "enabled_services": enabled,
        "services_measured": sorted(services),
        "base_charge_codes": base_codes,
        "services_with_no_base_code": sorted(k for k, v in base_codes.items() if v is False),
        "service_size_pairs": {f"{s} · {size}": n for (s, size), n in sorted(pairs.items())},
        "metered_services": dict(services),
        "unmetered_services": dict(unmetered),
        "distinct_pairs": len(pairs),
        "verdicts": verdicts,
        "unpriced": sorted(k for k, v in verdicts.items() if v["priced"] is False),
        "undetermined": sorted(k for k, v in verdicts.items() if v["priced"] is None),
    }


def money_at_stake(prepared, body: dict) -> dict:
    """What the LIVE path was about to charge on the accounts the chain refuses.

    ⚠ **THIS IS NOT A BILL TOTAL AND MUST NOT BE READ AS ONE.** The decision log
    of 2026-08-28 rejected composing one, in terms: *"Rejected: composing a total
    from them, which would invent the figure the run has not worked out."* Phase
    1 computes no money at all. What is summed here is exactly one thing and it
    is named on every line: the **per-service BASE CHARGE rows the live path
    resolved**, on the accounts where the chain produced no number. It is the
    size of the class in money, not the size of anybody's bill.

    ⚠ **AND NO DIFFERENCE IS COMPUTED**, because the ruled path produced no
    figure to subtract. The absence IS the finding.
    """
    refused = {
        row["account_no"]
        for row in body["accounts_detail"]
        if row["status"] == shadow.STATUS_CHAIN_REFUSED
    }
    rows = 0
    total = 0
    by_service: Counter = Counter()
    for data in prepared.ready:
        if data.account_no not in refused:
            continue
        for config in data.tariffs:
            if config.base_charge is None:
                continue
            rows += 1
            total += config.base_charge
            by_service[config.service] += config.base_charge
    return {
        "accounts": len(refused),
        "base_rows": rows,
        "base_total": total,
        "by_service": {k: v for k, v in sorted(by_service.items(), key=lambda kv: -kv[1])},
    }


# ══════════════════════════════════════════════════════════════════════════
# The posture — asserted before a figure is printed, never after
# ══════════════════════════════════════════════════════════════════════════


def assert_rls_is_really_enforced() -> dict:
    """FAIL (never skip) if this connection could bypass tenant separation.

    Both assertions are `tests/isolation_helpers.py`'s, in that file's own
    terms: *"Superusers BYPASS row-level security, unconditionally, FORCE or
    not … A green suite that proves nothing is worse than a red one."*
    """
    if connection.vendor != "postgresql":
        raise SystemExit(
            "REFUSING TO MEASURE: this is not PostgreSQL. RLS, FORCE ROW LEVEL "
            "SECURITY and the deny-by-default policy do not exist on sqlite, so "
            "every figure would be measured on a database that cannot enforce "
            "the thing the figure is supposed to have been measured under."
        )
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_user, current_database()")
        role, database = cursor.fetchone()
        cursor.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
        rolsuper, rolbypassrls = cursor.fetchone()
    if rolsuper:
        raise SystemExit(
            f"REFUSING TO MEASURE: {role!r} is a SUPERUSER and bypasses RLS "
            "unconditionally. Every figure would be measured on a login that "
            "cannot see tenant separation — which is the defect that changed "
            "yesterday's performance answer by a quarter."
        )
    if rolbypassrls:
        raise SystemExit(
            f"REFUSING TO MEASURE: {role!r} carries BYPASSRLS. Same reason."
        )

    # Deny-by-default, proved rather than assumed: with no `app.tenant_id` the
    # policy predicate is NULL, which is not TRUE, which denies (DEF-639).
    core_tenancy.clear_current_tenant()
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM accounts")
        visible = cursor.fetchone()[0]
    if visible != 0:
        raise SystemExit(
            f"REFUSING TO MEASURE: {visible} account row(s) are visible with NO "
            "tenant context. Deny-by-default (CLAUDE.md hard rule 1) is not in "
            "force on this database, so nothing measured here would be measured "
            "under tenant separation."
        )

    # And the tables the run reads must really carry FORCEd RLS.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = ANY(%s)",
            [["accounts", "units", "meter_reads", "plan_versions", "tariff_versions"]],
        )
        tables = {name: (rls, force) for name, rls, force in cursor.fetchall()}
    unguarded = [name for name, (rls, force) in tables.items() if not (rls and force)]
    if unguarded:
        raise SystemExit(
            f"REFUSING TO MEASURE: {unguarded} do not carry ENABLE + FORCE ROW "
            "LEVEL SECURITY, so the pass would not run under the thing it claims."
        )
    return {
        "role": role,
        "database": database,
        "rolsuper": bool(rolsuper),
        "rolbypassrls": bool(rolbypassrls),
        "rows_visible_with_no_tenant_context": visible,
        "rls_enabled_and_forced": sorted(tables),
    }


# ══════════════════════════════════════════════════════════════════════════
# The run
# ══════════════════════════════════════════════════════════════════════════


def _sabotage(prepared, step: str):
    """Break ONE account on purpose so the harness can be watched counting it.

    Returns `(prepared, sentence)`. The mutation is on the frozen dataclass in
    memory, AFTER `prepare_run` has returned and BEFORE the shadow reads it — no
    row is written and no pricing code is touched.
    """
    ready = list(prepared.ready)
    if not ready:
        raise SystemExit("nothing to sabotage: the run prepared no ready accounts")

    if step == "R1":
        victim = ready[0]
        broken = "00000000-0000-0000-0000-0000deadbeef"
        ready[0] = replace(victim, rate_plan_id=broken)
        sentence = (
            f"R1 sabotage — account {victim.account_no}'s LIVE plan id was rewritten in "
            f"memory from {victim.rate_plan_id} to {broken}. ⚠ THIS MOVES THE ROW "
            "THROUGH THE REFUSAL PATH, NOT THROUGH THE COMPARISON: the adapter hands "
            "the broken id to the catalogue, which finds no published plan, and the "
            "chain refuses at R1 with NoPlanInForce. It is kept because it is the "
            "mutation `DEF-2839` was found with — it LOOKED like a working proof of "
            "R1's comparison for as long as nobody asked which column it moved. Use "
            "`--sabotage R1-version` for the figure difference."
        )
    elif step == "R1-version":
        # `DEF-2839` — THE MUTATION THAT ACTUALLY EXERCISES R1's COMPARISON.
        # The plan id is an INPUT (the adapter hands it to `build_catalogue`),
        # so breaking it can only ever produce a refusal. The VERSION never
        # reaches the chain, which is what makes it the comparable half: the
        # chain re-reads `rate_plans.version` for itself. Breaking the LIVE
        # version therefore moves R1's `figures_differ` counter — the counter
        # that stood at ZERO across 94 account evaluations before this existed.
        victim = ready[0]
        was = victim.rate_plan_version
        ready[0] = replace(victim, rate_plan_version=(was or 0) + 41)
        sentence = (
            f"R1-version sabotage — account {victim.account_no}'s LIVE plan version was "
            f"rewritten in memory from {was!r} to {(was or 0) + 41!r}. The chain re-reads "
            "the version for itself, so this MUST move that account out of R1's agree "
            "column and into its disagree column as `figures_differ` — a FIGURE "
            "difference and not a refusal."
        )
    elif step == "R3b":
        # ⚠ THE THOUSANDFOLD MULTIPLIER ERROR, ON THE FIELD THE LIVE PATH
        # ACTUALLY CARRIES IT IN. This switch used to multiply
        # `TariffConfig.multiplier` and nothing moved — which was read as proof
        # that R3b was uncompared, and it WAS uncompared. But that field is a
        # TRIP-WIRE the pricing engine REFUSES BY NAME when it is not 1 (PO
        # ruling 2026-08-11 — metering applies the meter multiplier and the
        # engine never does), so `gather` sets none and nothing prices from it:
        # mutating it would still move nothing today, for a SECOND reason that
        # has nothing to do with coverage. The live path carries the
        # multiplier's whole effect inside the CONSUMPTION — metering's stored
        # `(current − prior) × multiplier` — so that is where a multiplier error
        # lives and that is what is broken here. `--sabotage R3b-tariff-mult`
        # keeps the old mutation so the previous proof can still be re-run.
        victim = None
        for index, data in enumerate(ready):
            for position, reading in enumerate(data.readings):
                if reading.consumption is not None:
                    victim = (index, data, position, reading)
                    break
            if victim is not None:
                break
        if victim is None:
            raise SystemExit("nothing to sabotage: no ready account carries a consumption")
        index, data, position, reading = victim
        readings = list(data.readings)
        was = reading.consumption
        readings[position] = replace(
            reading, consumption=replace(was, amount=was.amount * 1000)
        )
        ready[index] = replace(data, readings=tuple(readings))
        sentence = (
            f"R3b sabotage — account {data.account_no}'s LIVE billable quantity for "
            f"{reading.service_code} was rewritten in memory from {was.amount} to "
            f"{was.amount * 1000} {was.unit}, the thousandfold meter-multiplier error on "
            "the figure that decides which tier a customer's usage lands in, applied to "
            "the field the live path actually carries it in (metering's stored "
            "post-multiplier consumption). R3b IS a step compare() covers since "
            "DEF-2798, so the table MUST move: this account leaves R3b's agree column "
            "and enters its disagree column."
        )
    elif step == "R2":
        # ⚠ **R2 HAD NO MUTATION AT ALL UNTIL 2026-08-31**, so its `47 agree`
        # was an unproved zero of exactly the kind this harness exists to
        # refuse — the same shape as `DEF-2839` at R1 and `DEF-2798` at the four
        # steps that were compared by nothing. R2 was examined for R1's
        # circularity at the same time and does NOT have it: `ChainInputs`
        # carries `plan_id` and nothing about a schedule, so the chain
        # re-derives the version from the plan's binding and the service date
        # (`_schedule_versions_for_plan`) while the live path carries
        # `TariffConfig.version_id` off `gather`. Two derivations of one answer.
        # This mutation is what turns that reading from an argument into a
        # measurement.
        victim = None
        for index, data in enumerate(ready):
            if data.tariffs:
                victim = (index, data)
                break
        if victim is None:
            raise SystemExit("nothing to sabotage: no ready account carries a tariff")
        index, data = victim
        tariffs = list(data.tariffs)
        was_version = tariffs[0].version_id
        broken = "00000000-0000-0000-0000-00000000d2f0"
        tariffs[0] = replace(tariffs[0], version_id=broken)
        ready[index] = replace(data, tariffs=tuple(tariffs))
        sentence = (
            f"R2 sabotage — account {data.account_no}'s LIVE rate-schedule VERSION for "
            f"{tariffs[0].service} was rewritten in memory from {was_version} to "
            f"{broken}: the live path pricing this period on one filing while the chain "
            "resolves another, which is the whole content of R2. The chain never "
            "receives a version id, so it re-derives its own and the two must differ: "
            "this account MUST leave R2's agree column and enter its disagree column as "
            "a FIGURE difference, not a refusal."
        )
    elif step == "R3b-tariff-mult":
        victim = None
        for index, data in enumerate(ready):
            if data.tariffs:
                victim = (index, data)
                break
        if victim is None:
            raise SystemExit("nothing to sabotage: no ready account carries a tariff")
        index, data = victim
        tariffs = list(data.tariffs)
        was_mult = tariffs[0].multiplier
        tariffs[0] = replace(tariffs[0], multiplier=was_mult * 1000)
        ready[index] = replace(data, tariffs=tuple(tariffs))
        sentence = (
            f"R3b-tariff-mult sabotage (THE PREVIOUS LANE'S MUTATION, KEPT) — account "
            f"{data.account_no}'s `TariffConfig.multiplier` for {tariffs[0].service} was "
            f"rewritten in memory from {was_mult} to {was_mult * 1000}. ⚠ THE TABLE MUST "
            "**NOT** MOVE, AND THAT IS NOW THE CORRECT RESULT RATHER THAN THE DEFECT. "
            "That field is a trip-wire the pricing engine refuses by name when it is not "
            "1; `gather` sets none and nothing prices from it, so an error there is not "
            "an error in anything a customer is billed. Comparing it against the chain's "
            "real meter multiplier would report a disagreement on every meter that is "
            "not x1. Use `--sabotage R3b` for the real multiplier error."
        )
    elif step == "R3":
        # `DEF-2823` — R3 is the CONNECTION SIZE, and this is the mutation that
        # proves the new comparison can distinguish pass from fail. Rewriting
        # the live size to one the schedule does not price is precisely the
        # $8.00/$8.00 pair `DEF-1810` was: a 3-inch connection billed at the
        # 5/8 rate, on a document that looks entirely ordinary.
        victim = None
        for index, data in enumerate(ready):
            if data.tariffs:
                victim = (index, data)
                break
        if victim is None:
            raise SystemExit("nothing to sabotage: no ready account carries a tariff")
        index, data = victim
        tariffs = list(data.tariffs)
        was_size = tariffs[0].size_class
        tariffs[0] = replace(tariffs[0], size_class="SABOTAGE-3-INCH")
        ready[index] = replace(data, tariffs=tuple(tariffs))
        sentence = (
            f"R3 sabotage — account {data.account_no}'s LIVE connection size for "
            f"{tariffs[0].service} was rewritten in memory from {was_size!r} to "
            "'SABOTAGE-3-INCH'. ⚠ SINCE `DEF-2878` THIS NO LONGER MOVES THE R3 ROW AND "
            "MUST NOT: R3's two sides were one seam call, so `compare()` asserts the "
            "size as an INVARIANT rather than comparing it, and breaking ONE side is "
            "now proof that the adapter mapped a different connection. The account "
            "moves to `shadow_comparison_raised` under COULD NOT ASK AT ALL, carrying "
            "the invariant's own sentence — which is what this mutation now proves. "
            "Use `--sabotage R3-seam` to see the circularity itself, and the R3 "
            "REFUSAL (a size absent from the schedule's axis) for the evidence that "
            "can actually release the step."
        )
    elif step == "R4":
        # `DEF-2823` — R4 is the base AMOUNT. This is DEF-154's exact shape:
        # the arithmetic over the base is right and the SOURCING is wrong.
        victim = None
        for index, data in enumerate(ready):
            if data.tariffs and data.tariffs[0].base_charge is not None:
                victim = (index, data)
                break
        if victim is None:
            raise SystemExit("nothing to sabotage: no ready account carries a base charge")
        index, data = victim
        tariffs = list(data.tariffs)
        was_base = tariffs[0].base_charge
        broken_base = Decimal(str(was_base)) + Decimal("4.00")
        tariffs[0] = replace(tariffs[0], base_charge=broken_base)
        ready[index] = replace(data, tariffs=tuple(tariffs))
        sentence = (
            f"R4 sabotage — account {data.account_no}'s LIVE base charge for "
            f"{tariffs[0].service} was rewritten in memory from {was_base} to "
            f"{broken_base}. That is DEF-154's exact shape — the arithmetic over the "
            "base is right and the SOURCING is wrong, which the frozen golden suite "
            "cannot see because B5 hands the base to the engine directly. R4 IS a step "
            "compare() covers since DEF-2823, so the table MUST move."
        )
    elif step == "R5":
        victim = None
        for index, data in enumerate(ready):
            if data.tariffs:
                victim = (index, data)
                break
        if victim is None:
            raise SystemExit("nothing to sabotage: no ready account carries a tariff")
        index, data = victim
        tariffs = list(data.tariffs)
        was_factor = tariffs[0].jurisdiction_factor
        broken_factor = was_factor + 1
        tariffs[0] = replace(tariffs[0], jurisdiction_factor=broken_factor)
        ready[index] = replace(data, tariffs=tuple(tariffs))
        sentence = (
            f"R5 sabotage — account {data.account_no}'s LIVE jurisdiction factor for "
            f"{tariffs[0].service} was rewritten in memory from {was_factor} to "
            f"{broken_factor}. That factor scales the base AND the usage (BR-RAT-102), "
            "so on an $8.00 base it is the difference between $8.00 and $16.00. R5 IS a "
            "step compare() covers since DEF-2798, so the table MUST move."
        )
    elif step == "R6":
        victim = ready[0]
        seam = sys.modules["apps.billing.rating_seam"]
        invented = seam.DiscountRule(
            code="SABOTAGE-DISCOUNT",
            name="A discount the catalogue does not offer",
            discount_type="fixed_amount",
            value=Decimal("1.00"),
            currency=victim.currency,
            applies_to="whole_bill",
        )
        ready[0] = replace(victim, discounts=(*victim.discounts, invented))
        sentence = (
            f"R6 sabotage — a granted discount `SABOTAGE-DISCOUNT` was added to account "
            f"{victim.account_no}'s LIVE discount set in memory. The catalogue does not "
            "offer it, so the chain drops it (BR-RAT-110 — the plan makes a discount "
            "available, the enrolment grants it) and the two sets differ. R6 IS a step "
            "compare() covers since DEF-2798, so the table MUST move. ⚠ This is the ONE "
            "direction R6 can find: `adapt` takes the chain's enrolments FROM this same "
            "live set, so the chain can drop a code and can never add one."
        )
    elif step == "R7":
        victim = None
        for index, data in enumerate(ready):
            if data.taxes:
                victim = (index, data)
                break
        if victim is None:
            raise SystemExit("nothing to sabotage: no ready account carries a tax rule")
        index, data = victim
        taxes = list(data.taxes)
        dropped = taxes.pop(0)
        ready[index] = replace(data, taxes=tuple(taxes))
        sentence = (
            f"R7 sabotage — the tax rule {dropped.code!r} was removed from account "
            f"{data.account_no}'s LIVE tax set in memory, which is a customer not being "
            "charged a tax an authority is owed. R7 publishes NO refusal class and never "
            "will (a failed condition means no line, not an error — DEF-273), so this "
            "comparison is the only thing that can ever evaluate it. R7 IS a step "
            "compare() covers since DEF-2798, so the table MUST move."
        )
    else:  # pragma: no cover - argparse constrains this
        raise SystemExit(f"unknown sabotage step {step!r}")

    return replace(prepared, ready=tuple(ready)), sentence


def apply_what_if(what_if: str, prepared, rows: dict) -> list[str]:
    """Open R3's gate IN A ROLLED-BACK TRANSACTION and see what is behind it.

    ⚠ **THIS IS A WHAT-IF AND IT IS NEVER THE MEASUREMENT.** It writes rows the
    tenant has not written, inside the transaction the whole script throws away,
    to answer ONE question the headline table cannot: *R3 refuses every account,
    so is R3 the only wall or is there another behind it?* Without an answer,
    "R3b..R7 could not be evaluated" is true and useless — nobody can tell
    whether those steps are one data fix away or five.

    **It proposes no price.** The only figure it writes is `base_charge`, and it
    writes the LIVE path's own resolved base for that service — a figure this
    tenant already bills — precisely so that no number here is invented. It does
    not decide it is correct; R4's charge code overrides it anyway
    (`base_source="charge_code"`), which is why the value cannot affect the
    comparison and only its NON-NULLNESS matters.

    Two stages, because R3 refuses on two separate grounds and the second is
    invisible until the first is cleared:

        size-rows       give every (service · size) the run carries a row on the
                        schedule version. `rate_size_rows` has 0 rows today.
        size-rows+base  and give the version a base charge.
                        `tariff_versions.base_charge` is NULL on all 9 versions.
    """
    from apps.rating import models as rating_models

    notes: list[str] = []
    tenant_id = core_tenancy.current_tenant_id()

    # Which (service, size) pairs and which live base per service.
    needed: dict[str, set[str]] = {}
    live_base: dict[str, object] = {}
    for data in prepared.ready:
        account = rows.get(str(data.account_id))
        if account is None:
            continue
        inputs = shadow.adapt(data, account=account)
        if inputs.blocked_reason is not None:
            continue
        for meter in inputs.meters:
            needed.setdefault(meter.service, set()).add(meter.connection_size)
        for config in data.tariffs:
            if config.base_charge is not None:
                live_base.setdefault(config.service, config.base_charge)

    written = 0
    versions_touched = 0
    for version in rating_models.TariffVersion.objects.filter(
        tenant_id=tenant_id
    ).select_related("tariff", "tariff__service"):
        service = version.tariff.service.code
        if service not in needed:
            continue
        for size in sorted(needed[service]):
            rating_models.RateSizeRow.objects.get_or_create(
                tenant_id=tenant_id,
                tariff_version=version,
                size_class=size,
                defaults={"minimum_bill": None, "currency": "USD"},
            )
            written += 1
        if what_if == "size-rows+base" and version.base_charge is None:
            base = live_base.get(service)
            if base is not None:
                version.base_charge = base
                version.save(update_fields=["base_charge"])
                versions_touched += 1
    notes.append(
        f"WHAT-IF `{what_if}` — {written} `rate_size_rows` row(s) written across the "
        f"tenant's schedule versions for the sizes the run's meters actually are"
        + (
            f", and `base_charge` set on {versions_touched} version(s) from the LIVE "
            "path's own resolved base (no price is proposed here)"
            if what_if == "size-rows+base"
            else ""
        )
        + ". Rolled back with everything else; the database is unchanged."
    )
    return notes


def _tenants_to_measure(selector: str | None) -> list:
    """WHICH UTILITIES THE COMPARISON RUNS OVER.

    ⚠ **THIS FUNCTION IS THE RELEASE CONDITION OF A PO RULING, not a
    convenience.** The 2026-08-31 cutover ruling holds R3, R3b, R5 and R6 and
    states in its own words what lifts the hold: *"run the comparison over more
    than one seeded utility, and over a period containing a demand meter. That
    is the same instrument, pointed at a wider population — not new
    machinery."*

    Until this argument existed the instrument could not be pointed anywhere:
    `measure()` took `Tenant.objects.order_by("created_at").first()` and had no
    way to reach a second. So *"R4 waits because R3 is held"* was never the
    whole truth — the evidence the ruling asked for had not been gathered, and
    reporting that as the PO's hold put our unfinished work on their decision
    (decision log, 2026-08-31).

    The default is unchanged — the first tenant by `created_at` — so every
    figure already published from this script still reproduces.
    """
    ordered = list(tenancy_models.Tenant.objects.order_by("created_at"))
    if not ordered:
        raise SystemExit("no tenant on this database — nothing to measure")
    if selector in (None, ""):
        return ordered[:1]
    if selector == "all":
        return ordered
    wanted = [part.strip() for part in selector.split(",") if part.strip()]
    chosen = []
    for name in wanted:
        match = next(
            (t for t in ordered if t.subdomain == name or t.name == name), None
        )
        if match is None:
            known = ", ".join(sorted(t.subdomain for t in ordered))
            raise SystemExit(f"no tenant {name!r} on this database — known: {known}")
        chosen.append(match)
    return chosen


#: The size `--sabotage R3-seam` substitutes, and the one it substitutes for.
#: Both are on the seeded water ladder (`rate_size_rows` carries W-58, W-34,
#: W-1, W-112, W-2, W-3, W-4, W-5, W-6), so the chain RESOLVES the wrong size
#: instead of refusing it — which is the point: a refusal would move the column
#: through `chain_refused` and prove nothing about the comparison.
SEAM_SABOTAGE_FROM = "W-58"
SEAM_SABOTAGE_TO = "W-2"


#: The size `--sabotage R3-coverage` un-prices. It is the one every seeded
#: utility's water accounts carry, so dropping it must flip every water row.
COVERAGE_SABOTAGE_SIZE = "W-58"


@contextmanager
def _seam_sabotage():
    """Break the ONE source both paths read R3's size from, for the whole pass.

    ⚠ **THIS IS THE ONLY MUTATION IN THIS FILE THAT MUST NOT MOVE ITS OWN
    COLUMN, AND IT IS INSTALLED BEFORE `prepare_run` FOR THAT REASON.** Every
    other `--sabotage` here rewrites a frozen dataclass AFTER the run has been
    prepared, so it breaks the live side only and the two sides then differ. The
    finding `DEF-2878` records is that R3 has no two sides:

        gather._connection_size_for   -> metering.connection_size_for
        resolution_shadow.adapt       -> metering.connection_size_for  (same)
        adapt puts that value on MeterFacts.connection_size
        rating.resolution.resolve_served_size ends `return meter.connection_size`
        compare() then tests the first against the last

    Both call sites resolve the seam by NAME at call time
    (`gather._resolve` / `resolution_shadow._seam`, each an `import_module` +
    `getattr`), so patching the attribute here reaches both — which is itself
    the evidence that there is one source and not two.

    Nothing is written. The patch is removed on the way out, and the whole pass
    is inside the transaction the script rolls back regardless.
    """
    from apps.metering import selectors as metering_selectors

    original = metering_selectors.connection_size_for

    def wrong_but_served(unit_id, service_code, *args, **kwargs):
        answer = original(unit_id, service_code, *args, **kwargs)
        return SEAM_SABOTAGE_TO if answer == SEAM_SABOTAGE_FROM else answer

    metering_selectors.connection_size_for = wrong_but_served
    try:
        yield (
            f"R3-seam sabotage — `metering.connection_size_for` was patched for the "
            f"WHOLE pass to answer {SEAM_SABOTAGE_TO!r} wherever it would have answered "
            f"{SEAM_SABOTAGE_FROM!r}. That is a 2-inch ladder pricing a 5/8-inch "
            "connection on EVERY account, in BOTH implementations at once (the seeded "
            "water ladder is flat, so the AMOUNT is $8.00 either way — the wrongness is "
            "the ladder, not the fixture's price). "
            "⚠ THE R3 ROW MUST NOT MOVE, AND SINCE THE FIX IT CANNOT — READ THIS "
            "RESULT WITH ITS DATE. On 2026-09-01, BEFORE `DEF-2878` was fixed, this "
            "mutation left the row reading `47 agree · 0 disagree · 0 cannot evaluate` "
            "and `by_step {}`, which is the whole finding: the one source both paths "
            "read had been made to lie, and the column called it agreement. AFTER the "
            "fix the row reads `0 agree · 0 disagree · N cannot evaluate` on every run, "
            "clean or sabotaged, because R3 is an invariant and is no longer counted. "
            "**So this switch is now a REGRESSION guard, not a demonstration**: if it "
            "ever moves the R3 row again, somebody has put the circular comparison "
            "back. The live demonstration is the recorded pair in the decision log."
        )
    finally:
        metering_selectors.connection_size_for = original


def _clear_every_base_charge_code() -> int:
    """Make THIS TENANT look like a utility that never declared a base charge.

    ⚠ **IT IS CALLED INSIDE THE TENANT CONTEXT, AND THE FIRST VERSION WAS NOT —
    WHICH MADE IT A SABOTAGE THAT SABOTAGED NOTHING.** Written as a whole-pass
    context manager like `_coverage_sabotage`, it ran before any tenant was
    selected, so `Charge.objects.filter(is_base=True)` was RLS-filtered to zero
    rows. It reported *"cleared 0 charge code(s)"*, the verdict stayed `MET`, and
    for one reading that looked like the new check being wrong. **The check was
    fine; the proof was empty** — which is the same class of fault the check
    itself exists to close, arriving in the tool built to test it.

    Returns the number cleared so the banner can state it: a sabotage that
    reports `0` has proved nothing and must be read as a failed proof, never as
    a passing run.
    """
    from apps.rating import models as rating_models

    return rating_models.Charge.objects.filter(is_base=True).update(is_base=False)


@contextmanager
def _coverage_sabotage():
    """Un-price ONE size for the whole pass, so the coverage verdict must flip.

    ⚠ **THIS EXISTS BECAUSE A VERDICT THAT CANNOT SAY `NOT MET` IS NOT A
    VERDICT.** `what_the_run_carries` reads R3's release condition off live
    configuration, and on this database every pair is priced — so a clean run
    can only ever print `MET`, and hard-won law 7 says prove a new guard RED
    before trusting it green. This is that proof, kept as a switch rather than
    written down once, because the next person to change the report needs to be
    able to re-run it.

    It patches `resolution_catalogue.configured_sizes_for` to drop
    `COVERAGE_SABOTAGE_SIZE` from whatever the tenant actually configured.
    Nothing is written and the whole pass is inside the rolled-back
    transaction; the patch is removed on the way out.
    """
    from apps.rating import resolution_catalogue as _catalogue

    original = _catalogue.configured_sizes_for

    def missing_one_size(version_id, service_code, *args, **kwargs):
        answer = original(version_id, service_code, *args, **kwargs)
        return tuple(size for size in answer if size != COVERAGE_SABOTAGE_SIZE)

    _catalogue.configured_sizes_for = missing_one_size
    try:
        yield (
            f"R3-coverage sabotage — `configured_sizes_for` was patched for the WHOLE "
            f"pass to drop {COVERAGE_SABOTAGE_SIZE!r} from every axis it answers, as "
            "though no utility had ever priced that connection size. Every account "
            "carrying it must read NOT PRICED and every utility carrying it must read "
            "NOT MET. If the verdict still reads MET, the report is not reading "
            "configuration and R3's release must not be taken from it."
        )
    finally:
        _catalogue.configured_sizes_for = original


@contextmanager
def _estate_unsized_sabotage():
    """Un-record ONE service's connection sizes, so the ESTATE line must flip.

    ⚠ **THIS IS THE RED PROOF FOR THE ONLY CHECK HERE THAT LOOKS OUTSIDE THE
    RUN (`DEF-2965`), AND LAW 7 SAYS PROVE IT RED BEFORE TRUSTING IT GREEN.**
    `what_the_estate_holds` reads live configuration, and on a well-configured
    utility it can only ever report zero — which is exactly the shape this repo
    has now shipped three times (`DEF-2878`, `DEF-2923`, `DEF-2965`): a check
    that cannot say the failing word.

    It patches `metering.selectors.connection_size_for` — the ENGINE'S OWN seam,
    which is what the estate scan asks — to answer `None` for every connection
    of `ESTATE_SABOTAGE_SERVICE`, as though nobody had ever recorded a size for
    them. **Every billable account of that service must be reported by name and
    the utility MUST read NOT MET.** A verdict of `MET` means the estate scan is
    not reading configuration and no switch decision may be taken from it.

    ⚠ **IT MOVES THE RUN'S OWN COLUMNS TOO, AND THAT IS NOT A FLAW — IT IS THE
    DIFFERENCE BETWEEN THE TWO CHECKS MADE VISIBLE.** The real defect is the
    reverse case, where the estate holds an unsized meter on an account the run
    never contained: the run reports `MET` and the estate reports the accounts.
    That case cannot be manufactured by patching a seam (it is a property of
    which accounts are in a cycle) and it was measured live instead — on
    `sbh_r3rel`, `brazosbend` read water `MET` while twelve of its water meters
    carried no size. The sabotage proves the SENTENCE can be printed; the live
    measurement proves it is printed for the case that matters.

    Nothing is written; the patch is removed on the way out and the whole pass
    is inside the transaction this script rolls back regardless.
    """
    from apps.metering import selectors as metering_selectors

    original = metering_selectors.connection_size_for

    def unrecorded(unit_id, service_code, *args, **kwargs):
        if service_code == ESTATE_SABOTAGE_SERVICE:
            return None
        return original(unit_id, service_code, *args, **kwargs)

    metering_selectors.connection_size_for = unrecorded
    try:
        yield (
            f"estate-unsized sabotage — `metering.connection_size_for` was patched for "
            f"the WHOLE pass to answer None for every {ESTATE_SABOTAGE_SERVICE!r} "
            "connection, as though no utility had ever recorded one. EVERY utility "
            f"billing {ESTATE_SABOTAGE_SERVICE!r} MUST read NOT MET and MUST name the "
            "billable accounts affected. A verdict of MET means the estate scan is not "
            "reading configuration and R3 + R4 must not be switched on the strength of "
            "this report. ⚠ A count of 0 accounts means the sabotage touched nothing "
            "and has proved NOTHING — read it as a failed proof, not a passing run."
        )
    finally:
        metering_selectors.connection_size_for = original


@contextmanager
def _coverage_gap_sabotage():
    """Take ONE service out of the RUN's population while leaving it BILLED.

    ⚠ **THIS IS `DEF-2965`'s ACTUAL SHAPE, REPRODUCED ON DEMAND.** On 2026-09-01
    the three measured utilities billed water, sewer and trash and the report
    read `MET` — while `brazosbend` also has ELECTRIC enabled and not one
    electric account was in any prepared run. The report had no way to say so,
    because it named what it FOUND and never what it LOOKED AT.

    It patches `resolution_shadow.adapt` to drop every meter of
    `COVERAGE_GAP_SERVICE` from the facts the shadow reads, so that service
    vanishes from the run's population and stays on `tenant_services`. **The
    report MUST then name it as billed-but-not-examined and MUST NOT read MET.**
    If the verdict still reads MET, the report is still describing its findings
    as though they were its coverage.

    Nothing is written: `adapt` returns a frozen dataclass and this rebuilds it
    with `dataclasses.replace`, after `prepare_run` and before the shadow reads.
    """
    original = shadow.adapt

    def without_one_service(data, *args, **kwargs):
        inputs = original(data, *args, **kwargs)
        meters = tuple(
            meter for meter in inputs.meters if meter.service != COVERAGE_GAP_SERVICE
        )
        unmetered = tuple(
            code for code in inputs.unmetered_services if code != COVERAGE_GAP_SERVICE
        )
        return replace(inputs, meters=meters, unmetered_services=unmetered)

    shadow.adapt = without_one_service
    try:
        yield (
            f"service-coverage sabotage — `resolution_shadow.adapt` was patched for the "
            f"WHOLE pass to drop every {COVERAGE_GAP_SERVICE!r} meter from the facts the "
            "shadow reads, so the run examines a service the tenant still BILLS. Every "
            f"utility with {COVERAGE_GAP_SERVICE!r} enabled MUST name it as BILLED AND "
            "NOT EXAMINED and MUST read NOT MET. This is DEF-2965's own shape: the "
            "report read MET over three utilities while never having looked at an "
            "electric account. A verdict of MET here means it still cannot tell "
            "'nothing wrong' from 'nothing looked at'."
        )
    finally:
        shadow.adapt = original


def measure(
    *,
    cycle_code: str | None,
    sabotage: str | None,
    what_if: str | None = None,
    tenants: str | None = None,
) -> dict:
    chosen_tenants = _tenants_to_measure(tenants)
    # ── TWO SABOTAGES ARE WHOLE-PASS PATCHES AND MUST SPAN TENANTS ────────
    # The guard below is about a ROW mutation, whose meaning is "this row's
    # step moved and no other". `R3-seam` and `R3-coverage` patch a shared
    # function for the entire pass instead, so they apply to every account of
    # every utility by construction — and `R3-coverage` in particular proves a
    # PER-UTILITY verdict, which cannot be read on one utility at a time.
    WHOLE_PASS_SABOTAGES = {
        "R3-seam", "R3-coverage", "no-base-code",
        # Both are whole-pass by nature: a per-utility verdict cannot be read
        # one utility at a time, and a coverage gap is a statement about the
        # POPULATION rather than about a row.
        "estate-unsized", "service-coverage",
    }
    if sabotage and sabotage not in WHOLE_PASS_SABOTAGES and len(chosen_tenants) > 1:
        # A sabotage rewrites ONE row and its whole meaning is "this row's step
        # moved and no other". Spread over several tenants the row it moved is
        # no longer identifiable from the table, so the mutation would prove
        # nothing while looking like it had.
        raise SystemExit(
            "--sabotage measures one mutated row against its own run; it cannot be "
            "read across several tenants. Name one tenant, or drop --sabotage."
        )

    posture = assert_rls_is_really_enforced()

    result: dict = {
        "posture": posture,
        "tenant": ", ".join(t.name for t in chosen_tenants),
        "tenants": [{"name": t.name, "subdomain": t.subdomain} for t in chosen_tenants],
        "sabotage": None,
    }

    bodies = []
    # `R3-seam` is not a row mutation and must not reach `_sabotage`: it patches
    # the shared seam around the whole pass, BEFORE `prepare_run` opens, so both
    # implementations read the broken answer.
    seam_sabotage = sabotage == "R3-seam"
    coverage_sabotage = sabotage == "R3-coverage"
    no_base_sabotage = sabotage == "no-base-code"
    estate_sabotage = sabotage == "estate-unsized"
    gap_sabotage = sabotage == "service-coverage"
    row_sabotage = (
        None
        if (
            seam_sabotage
            or coverage_sabotage
            or no_base_sabotage
            or estate_sabotage
            or gap_sabotage
        )
        else sabotage
    )
    with ExitStack() as stack:
        if seam_sabotage:
            result["sabotage"] = stack.enter_context(_seam_sabotage())
        if coverage_sabotage:
            result["sabotage"] = stack.enter_context(_coverage_sabotage())
        if estate_sabotage:
            result["sabotage"] = stack.enter_context(_estate_unsized_sabotage())
        if gap_sabotage:
            result["sabotage"] = stack.enter_context(_coverage_gap_sabotage())
        for tenant in chosen_tenants:
            _measure_one_tenant(
                tenant,
                cycle_code=cycle_code,
                sabotage=row_sabotage,
                no_base_sabotage=no_base_sabotage,
                what_if=what_if,
                result=result,
                bodies=bodies,
            )

    merged = _merge(bodies)
    coverage = comparator_coverage()
    merged["per_step"] = per_step_table(merged, coverage)
    merged["coverage"] = {
        "compared": sorted(coverage["compared"]),
        "refusable": sorted(coverage["refusable"]),
        "refusal_classes": resolution.refusal_steps(),
    }
    merged["served_by_chain_default"] = resolution_switch.SERVED_BY_CHAIN_DEFAULT
    result["body"] = merged
    return result


def _measure_one_tenant(
    tenant, *, cycle_code, sabotage, what_if, result, bodies, no_base_sabotage=False
) -> None:
    """One utility's cycles, appended to `bodies`. Was the body of `measure()`."""
    with core_tenancy.tenant_context(tenant.id):
        if no_base_sabotage:
            cleared = _clear_every_base_charge_code()
            # Accumulated across tenants: assigning here named only the LAST
            # utility while every one of them had been cleared, which reads as a
            # narrower sabotage than the one that ran.
            touched = result.setdefault("_sabotage_tenants", [])
            touched.append(f"{tenant.subdomain} ({cleared})")
            result["sabotage"] = (
                f"no-base-code sabotage — `is_base` cleared on {', '.join(touched)} "
                "charge code(s) per utility, so every service reads as one no utility has "
                "declared a base charge for. That utility MUST read NOT MET and MUST "
                "name the service; a verdict of MET means this check is not reading "
                "configuration and no switch decision may be taken from it. ⚠ A count "
                "of 0 means the sabotage touched nothing and has proved NOTHING — read "
                "it as a failed proof, not as a passing run. Rolled back with "
                "everything else; the database is unchanged."
            )
        # ── A PRECONDITION, STATED, BECAUSE ITS ABSENCE READS AS A FINDING ──
        # `rate_size_rows` is R3's whole input. With zero rows every account
        # refuses at R3 and the table reports `disagreed 47 · chain_refused 47`
        # — which looks exactly like a pricing disagreement and is not one; it
        # is a tenant that has never been given the size axis (DEF-2799). The
        # figures published from this script on 2026-08-31 were taken after
        # `10-scripts/def2799_apply_size_axis.py` had been run, and a container
        # restart reverted that write, so the same command produced 47
        # refusals an hour later. Say it here rather than let the next reader
        # conclude the chain broke.
        from apps.rating import models as _rating_models

        size_rows = _rating_models.RateSizeRow.objects.count()
        result.setdefault("preconditions", []).append(
            {
                "tenant": tenant.subdomain,
                "rate_size_rows": size_rows,
                "note": (
                    "R3 has no size axis to read on this tenant; every account will "
                    "refuse at R3. Run `10-scripts/def2799_apply_size_axis.py --tenant "
                    f"{tenant.subdomain}` first — this is NOT a pricing disagreement"
                )
                if size_rows == 0
                else "",
            }
        )
        cycles = list(metering_models.Cycle.objects.order_by("code"))
        if cycle_code:
            cycles = [c for c in cycles if c.code == cycle_code]
            if not cycles:
                raise SystemExit(f"no cycle {cycle_code!r} on this tenant")

        # THE WHOLE RUN. The population is every account every cycle scopes,
        # because "a whole prepared bill run" on this tenant is what the count
        # has to be over — one cycle would be one plan's worth of evidence.
        chosen = None
        best = -1
        per_cycle = []
        for cycle in cycles:
            unit_ids = runs._resolve("metering", "units_in_cycle")(cycle.id)
            per_cycle.append({"cycle": cycle.code, "units": len(unit_ids)})
            if len(unit_ids) > best:
                best, chosen = len(unit_ids), cycle
        result.setdefault("cycles", []).extend(per_cycle)

        # ⚠ NO `bodies = []` HERE. This was `measure()`'s local until the
        # per-tenant split; left in place it re-binds the parameter and every
        # tenant's bodies are dropped on return — which reads as
        # "no cycle produced a prepared run", not as a bug.
        for cycle in cycles:
            period_start, period_end, service_date = _period_for(cycle)
            prepared = runs.prepare_run(
                cycle_id=cycle.id,
                period_start=period_start,
                period_end=period_end,
                service_date=service_date,
            )
            if not prepared.ready and not prepared.blocked:
                continue
            sentence = None
            if sabotage and cycle is chosen:
                prepared, sentence = _sabotage(prepared, sabotage)
                result["sabotage"] = sentence
            if what_if and cycle is chosen:
                result.setdefault("what_if", []).extend(
                    apply_what_if(what_if, prepared, shadow_report._accounts_by_id(prepared))
                )
                # The catalogue is rebuilt per account inside the shadow, so the
                # rows just written are picked up; the pass cache that
                # `prepare_run` opened has already closed.
            body = shadow_report.report_for_prepared(prepared)
            body["_tenant"] = tenant.subdomain
            body["_cycle"] = f"{tenant.subdomain}/{cycle.code}"
            body["_period"] = [str(period_start), str(period_end), str(service_date)]
            body["_blocked_before_the_shadow"] = len(prepared.blocked)
            body["_blocked_reasons"] = dict(
                Counter(problem.reason for problem in prepared.blocked)
            )
            account_rows = shadow_report._accounts_by_id(prepared)
            body["_probe"] = probe_r1_r2(prepared, account_rows)
            body["_money"] = money_at_stake(prepared, body)
            body["_carries"] = what_the_run_carries(prepared, account_rows)
            # ⚠ **THE ESTATE, NOT THE RUN — AND IT IS A DIFFERENT BLIND SPOT
            # FROM THE ONE ABOVE (`DEF-2965`).** `services_measured` catches a
            # service the utility BILLS that this pass never examined. It does
            # nothing for a service that WAS examined and still hides the
            # failing case: every figure this body carries comes from the
            # accounts a prepared run contains, and that population holds only
            # accounts already in a cycle whose meters already have sizes. On
            # `sbh_r3rel` water was examined on all three utilities, read
            # `PRICED`, and two of them held 21 billable water accounts each
            # whose connection has no recorded size. This asks the whole
            # utility, and it needs no prepared run at all.
            body["_estate"] = what_the_estate_holds(
                # The units the RUN reached, read off the ACCOUNT rows —
                # `AccountBillingData` carries no unit id (the account derives
                # its plan through the unit; the id lives on the account row).
                {
                    str(row.unit_id)
                    for row in account_rows.values()
                    if getattr(row, "unit_id", None)
                }
            )
            bodies.append(body)


def _period_for(cycle) -> tuple[date, date, date]:
    """The last CLOSED calendar month, on every cycle, so the run is comparable.

    Not derived from a clock inside the pass: `prepare_run` takes the service
    date explicitly (BR-RAT-007 — a June run re-executed in 2031 must reach
    June's tariff versions), and this function is the caller that supplies it.
    July 2026 is the month the seeded reads cover on this database.
    """
    return date(2026, 7, 1), date(2026, 7, 31), date(2026, 7, 1)


def _merge(bodies: list[dict]) -> dict:
    """One body over every cycle. Counts add; class rows fold on `class_id`."""
    if not bodies:
        raise SystemExit("no cycle produced a prepared run — nothing was measured")
    merged: dict = {
        "accounts": 0,
        "attempted": 0,
        "agreed": 0,
        "disagreed": 0,
        "chain_refused": 0,
        "not_attempted": 0,
        "blocked_before_the_shadow": 0,
        "by_step": Counter(),
        "blocked_by_reason": Counter(),
        "accounts_detail": [],
        "classes": [],
        "cycles_measured": [],
    }
    classes: dict[str, dict] = {}
    for body in bodies:
        merged["cycles_measured"].append(
            {"cycle": body["_cycle"], "period": body["_period"], "accounts": body["accounts"]}
        )
        for key in ("accounts", "attempted", "agreed", "disagreed", "chain_refused", "not_attempted"):
            merged[key] += body[key]
        merged["blocked_before_the_shadow"] += body["_blocked_before_the_shadow"]
        merged["by_step"].update(body["by_step"])
        merged["blocked_by_reason"].update(body["blocked_by_reason"])
        merged["accounts_detail"].extend(body["accounts_detail"])
        merged.setdefault("blocked_reasons", Counter()).update(body["_blocked_reasons"])
        probe = merged.setdefault(
            "probe",
            {
                step: {AGREE: 0, DISAGREE: 0, CANNOT: 0, "reasons": Counter(), "examples": []}
                for step in ("R1", "R2")
            },
        )
        for step, row in body["_probe"].items():
            for key in (AGREE, DISAGREE, CANNOT):
                probe[step][key] += row[key]
            probe[step]["reasons"].update(row["reasons"])
            probe[step]["examples"].extend(row["examples"][: 3 - len(probe[step]["examples"])])
        money = merged.setdefault(
            "money", {"accounts": 0, "base_rows": 0, "base_total": 0, "by_service": Counter()}
        )
        money["accounts"] += body["_money"]["accounts"]
        money["base_rows"] += body["_money"]["base_rows"]
        money["base_total"] += body["_money"]["base_total"]
        money["by_service"].update(body["_money"]["by_service"])
        carries = merged.setdefault(
            "carries",
            {"service_size_pairs": Counter(), "metered_services": Counter(),
             "unmetered_services": Counter(), "verdicts": {}, "by_tenant": {}},
        )
        carries["service_size_pairs"].update(body["_carries"]["service_size_pairs"])
        carries["metered_services"].update(body["_carries"]["metered_services"])
        carries["unmetered_services"].update(body["_carries"]["unmetered_services"])
        # ⚠ **THE VERDICT IS KEYED PER TENANT AND NEVER MERGED ACROSS THEM.**
        # A pair priced on one utility and unpriced on another is exactly the
        # finding this report exists to surface, and a dict keyed by pair alone
        # would let the second utility's answer overwrite the first's — the
        # aggregation silently reporting one utility's configuration as
        # everybody's. `by_tenant` is what the release verdict is read off.
        for pair, verdict in body["_carries"].get("verdicts", {}).items():
            carries["verdicts"].setdefault(pair, {})[body["_tenant"]] = verdict
        # ⚠ **ACCUMULATED, NEVER ASSIGNED — ONE BODY IS ONE CYCLE, NOT ONE
        # UTILITY.** `_measure_one_tenant` appends a body per billing cycle, so
        # a plain assignment here keeps only the LAST cycle's answer. Measured
        # on this database the first time it was written that way: `brazosbend`
        # read `0 pair(s) -> NOT MET` while the table two lines above listed its
        # `water · W-58` as PRICED, because its final cycle carried no ready
        # account. A verdict that contradicts its own evidence is worse than no
        # verdict, and R3's release is read off exactly this line.
        held = carries["by_tenant"].setdefault(
            body["_tenant"],
            {"pairs": set(), "unpriced": set(), "undetermined": set(),
             "counts": Counter(), "no_base_code": set(),
             "enabled_services": set(), "services_measured": set()},
        )
        held["pairs"].update(body["_carries"].get("verdicts", {}))
        held["unpriced"].update(body["_carries"].get("unpriced", []))
        held["undetermined"].update(body["_carries"].get("undetermined", []))
        held["counts"].update(body["_carries"]["service_size_pairs"])
        held.setdefault("no_base_code", set()).update(
            body["_carries"].get("services_with_no_base_code", [])
        )
        # `DEF-2965` — what this utility BILLS against what this pass LOOKED AT.
        # Accumulated per tenant for the same reason the pairs are (one body is
        # one CYCLE, not one utility): a service billed on a cycle that carried
        # no ready account is still a service this verdict has not examined.
        held.setdefault("enabled_services", set()).update(
            body["_carries"].get("enabled_services") or []
        )
        held.setdefault("services_measured", set()).update(
            body["_carries"].get("services_measured") or []
        )
        # `DEF-2965` — the ESTATE is a fact about the UTILITY, not about a
        # cycle, so the counts are taken by MAXIMUM rather than overwritten: a
        # cycle that somehow saw fewer connections must not be able to SHRINK
        # the finding, which is the mistake the `by_tenant` block one field up
        # already carries a warning about.
        estate = held.setdefault("estate", {})
        for service_code, est in (body.get("_estate") or {}).items():
            kept = estate.setdefault(service_code, dict(est))
            for key in (
                "connections",
                "connections_with_no_size",
                "billable_accounts",
                "billable_accounts_with_no_size",
                "connections_the_run_examined",
            ):
                kept[key] = max(kept.get(key, 0), est.get(key, 0))
            kept["banded"] = est.get("banded", kept.get("banded", False))
        for row in body["classes"]:
            held = classes.get(row["class_id"])
            if held is None:
                classes[row["class_id"]] = dict(row)
            else:
                held["accounts"] += row["accounts"]
                held["occurrences"] += row["occurrences"]
                for service in row["services"]:
                    if service not in held["services"]:
                        held["services"].append(service)
        for row in body["blocked_classes"]:
            merged.setdefault("blocked_classes", {})
            key = row["reason"]
            held = merged["blocked_classes"].get(key)
            if held is None:
                merged["blocked_classes"][key] = dict(row)
            else:
                held["accounts"] += row["accounts"]
    merged["by_step"] = dict(merged["by_step"])
    merged["blocked_by_reason"] = dict(merged["blocked_by_reason"])
    merged["blocked_reasons"] = dict(merged.get("blocked_reasons", Counter()))
    for row in merged.get("probe", {}).values():
        row["reasons"] = dict(sorted(row["reasons"].items(), key=lambda kv: -kv[1]))
    if "money" in merged:
        merged["money"]["by_service"] = {
            k: v for k, v in sorted(merged["money"]["by_service"].items(), key=lambda kv: -kv[1])
        }
    if "carries" in merged:
        carries = merged["carries"]
        carries["distinct_pairs"] = len(carries["service_size_pairs"])
        for key in ("service_size_pairs", "metered_services", "unmetered_services"):
            carries[key] = dict(sorted(carries[key].items()))
        for row in carries.get("by_tenant", {}).values():
            row["counts"] = dict(sorted(row["counts"].items()))
            for key in ("pairs", "unpriced", "undetermined", "no_base_code",
                        "enabled_services", "services_measured"):
                row[key] = sorted(row.get(key) or [])
            # Derived ONCE here rather than at three print sites. The BANDED
            # gate is the whole of it: sewer is ruled to have no size class, so
            # every sewer connection has no recorded size and none of them stops
            # a bill — reporting it would send a person looking for a size the
            # product will never hold.
            row["unsized_services"] = sorted(
                code
                for code, est in (row.get("estate") or {}).items()
                if est.get("banded") and est.get("billable_accounts_with_no_size", 0)
            )
    merged["classes"] = sorted(
        classes.values(), key=lambda row: (-row["accounts"], row["class_id"])
    )
    merged["blocked_classes"] = sorted(
        merged.get("blocked_classes", {}).values(), key=lambda row: (-row["accounts"], row["reason"])
    )
    return merged


# ══════════════════════════════════════════════════════════════════════════
# Printing
# ══════════════════════════════════════════════════════════════════════════


def _money(amount) -> str:
    """CLAUDE.md hard rule 2 — money DISPLAYS at 2 decimals.

    ⚠ **AND IT REFUSES TO ROUND SILENTLY.** B4's rounding rules are ❄️ FROZEN
    and this script has no business applying one: every figure it sums is a
    stored base charge that is already exact at 2dp, so trimming the container's
    trailing zeros loses nothing. If a sum ever is NOT exact at 2dp, both forms
    are printed and the fact is named, rather than a rounding decision being
    taken here where no rule authorises one.
    """
    from decimal import Decimal

    value = Decimal(str(amount))
    two = value.quantize(Decimal("0.01"))
    if two == value:
        return f"${two}"
    return f"${value} (NOT exact at 2 decimals — displayed unrounded; no B4 rule is applied here)"


def render(result: dict) -> str:
    body = result["body"]
    posture = result["posture"]
    out: list[str] = []
    add = out.append

    add("═" * 78)
    add("R1–R7 PRICING SHADOW — PER-STEP DISAGREEMENT COUNT OVER A WHOLE BILL RUN")
    add("CR-052 task 20 · step 4 of the recorded cutover · MEASURES ONLY, RULES NOTHING")
    add("═" * 78)
    add("")
    add("THE ROLE'S POSTURE, because a figure without it is not a figure:")
    add(f"  database              {posture['database']}")
    add(f"  connected as          {posture['role']}")
    add(f"  rolsuper              {posture['rolsuper']}   (RLS is NOT bypassed)")
    add(f"  rolbypassrls          {posture['rolbypassrls']}   (RLS is NOT bypassed)")
    add(
        f"  no-tenant-context     {posture['rows_visible_with_no_tenant_context']} account rows visible"
        "  (deny-by-default in force)"
    )
    add(f"  ENABLE+FORCE RLS on   {', '.join(posture['rls_enabled_and_forced'])}")
    add("")
    for pre in result.get("preconditions", []):
        if pre["note"]:
            add(f"⚠ PRECONDITION NOT MET — {pre['tenant']}: {pre['note']}")
    if any(pre["note"] for pre in result.get("preconditions", [])):
        add("")
    count = len(result.get("tenants", [])) or 1
    add(
        f"POPULATION — {count} utility(ies): "
        + ", ".join(t["subdomain"] for t in result.get("tenants", []))
    )
    for row in body["cycles_measured"]:
        add(f"  {row['cycle']}  {row['period'][0]} → {row['period'][1]}  ·  {row['accounts']} accounts shadowed")
    add(f"  TOTAL {body['accounts']} accounts entered the shadow; "
        f"{body['blocked_before_the_shadow']} more were blocked by the run BEFORE it "
        "(they never reach the ready set and are not in any column below)")
    # ⚠ **DERIVED, NEVER ASSERTED (PO ruling 2026-09-01, `CR-057`).** This line
    # used to end with a hardcoded "— empty, so NO rule prices any real bill
    # through the chain today". The day the pair was switched on that sentence
    # became FALSE, and it would have gone on printing under a report whose
    # whole job is to say what is live. A report that states a constant it did
    # not read is the same class of fault as a check that cannot fail.
    _served = sorted(resolution_switch.steps_served_by_chain())
    add(f"  resolution_switch.SERVED_BY_CHAIN_DEFAULT = {body['served_by_chain_default']!r} "
        f"· settings.BILLING_RESOLUTION_STEPS = {settings.BILLING_RESOLUTION_STEPS!r}")
    add("  SERVED BY THE CHAIN RIGHT NOW: "
        + (", ".join(_served) + " — these rules PRICE REAL BILLS on this deployment"
           if _served else
           "nothing — no rule of the chain prices any real bill here"))
    add("")
    add("WHOLE-RUN TOTALS (the shadow's own summary, unedited)")
    add(f"  accounts {body['accounts']} · attempted {body['attempted']} · agreed {body['agreed']} "
        f"· disagreed {body['disagreed']} · chain_refused {body['chain_refused']} "
        f"· not_attempted {body['not_attempted']}")
    add("")
    add("PER STEP — and a step that CANNOT BE EVALUATED is not a step that agrees")
    add("")
    add(f"  {'step':<7}{'agree':>7}{'disagree':>10}{'cannot':>9}   {'compare?':<9}{'refuse?':<8}{'switch?':<9} why the cannot-evaluate column reads as it does")
    add("  " + "─" * 83)
    for row in body["per_step"]:
        top = next(iter(row["reasons"]), "")
        # DEF-2838 — `switch?` is derived from `resolution_switch.FORKED`/`JOINT`
        # at runtime. A step reading NO cannot be offered for switching at all,
        # however clean its agreement columns look.
        add(
            f"  {row['step']:<7}{row[AGREE]:>7}{row[DISAGREE]:>10}{row[CANNOT]:>9}   "
            f"{'yes' if row['can_compare'] else 'NO':<9}{'yes' if row['can_refuse'] else 'NO':<8}"
            f"{'yes' if row.get('switchable') else 'NO':<9} {top}"
        )
    add("")
    add("  switch? — CAN this build serve the step from the ruled path (DEF-2838).")
    add("  It is NOT the agreement columns and it is not `SERVED_BY_CHAIN_DEFAULT`:")
    add("  a step reading NO has no seam, so naming it refuses however clean its")
    add("  agreement looks. Derived from resolution_switch.FORKED/JOINT at runtime.")
    for row in body["per_step"]:
        if row.get("switchable_note"):
            add(f"      {row['step']:<5} {row['switchable_note']}")
        elif not row.get("switchable"):
            add(f"      {row['step']:<5} NOT SWITCHABLE — no fork in this build")
    add("")
    add("  by_step (the shadow's own count of divergences + refusals): "
        f"{body['by_step'] or '{}'}")
    add("")
    add("SUPPLEMENTARY — R1 AND R2 PROBED DIRECTLY, because the chain RAN them")
    add("  The chain refuses further down, so `compare()` is never called and the table")
    add("  above must read `cannot evaluate` at R1 and R2. The evidence is obtainable")
    add("  anyway: these two rows call the chain's own `resolve_plan` and")
    add("  `resolve_schedule` and apply `compare()`'s comparison expressions verbatim.")
    add("  Reported separately and never folded into the table above.")
    add("")
    add(f"  {'step':<7}{'agree':>7}{'disagree':>10}{'cannot':>9}   reasons")
    add("  " + "─" * 74)
    for step in ("R1", "R2"):
        row = body["probe"][step]
        add(
            f"  {step:<7}{row[AGREE]:>7}{row[DISAGREE]:>10}{row[CANNOT]:>9}   "
            + "; ".join(f"{k}={v}" for k, v in row["reasons"].items())
        )
        for example in row["examples"]:
            add(f"          e.g. {example}")
    add("")
    money = body.get("money", {})
    if money.get("accounts"):
        add("THE SIZE OF THE REFUSAL CLASS IN MONEY")
        add("  ⚠ NOT a bill total and never to be read as one. Phase 1 computes no money.")
        add("  This is exactly one thing: the per-service BASE CHARGE rows the LIVE path")
        add("  resolved, on the accounts where the ruled path produced no number at all.")
        add("  No difference is computed — the ruled path produced nothing to subtract.")
        add("")
        add(f"  {money['accounts']} account(s) refused · {money['base_rows']} base-charge row(s) "
            f"the live path resolved · {_money(money['base_total'])} in those rows for this period")
        for service, amount in money["by_service"].items():
            add(f"    {service:<14} {_money(amount)}")
        add("")
    carries = body.get("carries", {})
    if carries:
        add("R3's RELEASE CONDITION — does every (service · size) these accounts carry")
        add("have something pricing it?")
        add(f"  {carries['distinct_pairs']} distinct pair(s). A pair with nothing pricing it means R3")
        add("  REFUSES the account (BR-BIL-872, no fallback) where the live path bills it today")
        add("  on the every-size ladder. That difference is the only thing switching R3 can cost.")
        add("  The axis is the CHARGE CODE's where the service declares a base code, and the rate")
        add("  schedule's otherwise (BR-RAT-1010, PO 2026-09-01) — the `priced by` column says")
        add("  which, because it is the screen a person has to open to cure a refusal.")
        verdicts = carries.get("verdicts") or {}
        by_tenant_counts = {
            name: row.get("counts", {}) for name, row in (carries.get("by_tenant") or {}).items()
        }
        for pair, total in sorted(carries["service_size_pairs"].items()):
            per_tenant = verdicts.get(pair) or {}
            if not per_tenant:
                add(f"    {pair:<24} on {total} account(s) in all   — not evaluated")
                continue
            for tenant_name, verdict in sorted(per_tenant.items()):
                mark = (
                    "PRICED    " if verdict["priced"] is True
                    else "NOT PRICED" if verdict["priced"] is False
                    else "UNDECIDED "
                )
                # ⚠ **THIS COUNT IS THIS UTILITY's, NOT THE RUN's.**
                # `service_size_pairs` is summed across every utility measured,
                # so printing it beside one utility's name reads as that
                # utility carrying all of them — `water · W-58 on 163
                # account(s)` against three utilities of 47, 58 and 58.
                mine = by_tenant_counts.get(tenant_name, {}).get(pair, 0)
                add(f"    {pair:<24} {tenant_name:<16} {mine:>4} account(s)   {mark}")
                add(f"      {verdict['detail']}")
        if carries.get("unmetered_services"):
            add(f"  unmetered services on these accounts: {carries['unmetered_services']}")
        add("")
        by_tenant = carries.get("by_tenant") or {}
        no_base = sorted({s for t in by_tenant.values() for s in (t.get("no_base_code") or [])})
        unpriced = sorted({p for t in by_tenant.values() for p in t["unpriced"]})
        undecided = sorted({p for t in by_tenant.values() for p in t["undetermined"]})
        measured_nothing = sorted(name for name, row in by_tenant.items() if not row["pairs"])
        # `DEF-2965` — services a utility BILLS that this pass never examined.
        unseen_any = sorted({
            s
            for row in by_tenant.values()
            for s in (set(row.get("enabled_services") or [])
                      - set(row.get("services_measured") or []))
        })
        add("  WHAT THE UTILITY HOLDS — the ESTATE, not this run (DEF-2965)")
        add("  The block above names a service this pass never EXAMINED. This is the")
        add("  other blind spot: a service that WAS examined and still hides the failing")
        add("  case. Every figure in this report is drawn from the accounts a prepared")
        add("  run contains, and that population holds only accounts already in a cycle")
        add("  whose meters already have sizes — so it cannot contain the connection")
        add("  nobody recorded a size for. This asks the whole utility and needs no run,")
        add("  which is also why it can be asked of a utility that has no cycle yet.")
        add("  `metering.connection_size_for` is the ENGINE'S OWN seam, so this cannot")
        add("  come to a different answer from the step it is clearing.")
        for tenant_name, row in sorted(by_tenant.items()):
            estate = row.get("estate") or {}
            if not estate:
                add(f"    {tenant_name:<28} no service point on this utility")
                continue
            for service_code, est in sorted(estate.items()):
                # ⚠ **AN UNBANDED SERVICE PRINTS A DASH, NOT A COUNT.** Sewer is
                # RULED to have no size class — it is a share of the water usage
                # charge and reads no register — so every one of its connections
                # has no recorded size and NONE of them is a finding. Printing
                # `61 with NO recorded size` beside it is a true number that
                # reads as an alarm, and a reader who acts on it goes looking
                # for a size the product will never hold.
                if not est.get("banded"):
                    add(
                        f"    {tenant_name:<28} {service_code:<12} "
                        f"{est['connections']:>4} connection(s) ·        — no size "
                        "bands, so a size is neither recorded nor needed"
                    )
                    continue
                add(
                    f"    {tenant_name:<28} {service_code:<12} "
                    f"{est['connections']:>4} connection(s) · "
                    f"{est['connections_with_no_size']:>4} with NO recorded size · "
                    f"{est['billable_accounts_with_no_size']:>4} of "
                    f"{est['billable_accounts']} billable account(s) affected"
                    f"   [this run examined {est['connections_the_run_examined']}]"
                )
        add("")
        unsized_any = sorted({
            s for row in by_tenant.values() for s in (row.get("unsized_services") or [])
        })
        accounts_at_risk_all = sum(
            est.get("billable_accounts_with_no_size", 0)
            for row in by_tenant.values()
            for code, est in (row.get("estate") or {}).items()
            if code in (row.get("unsized_services") or [])
        )
        add("  THE VERDICT, PER UTILITY")
        for tenant_name, row in sorted(by_tenant.items()):
            # ⚠ **TWO PRECONDITIONS, NOT ONE (`DEF-2923`).** A size nothing
            # prices refuses at R3; a SERVICE with no `is_base` charge code
            # refuses at R4. Both stop the same bill and only the first was
            # asked, which is why this verdict once read MET over a population
            # that could not contain the second case.
            missing = row.get("no_base_code") or []
            # ⚠ **WHAT THIS PASS NEVER LOOKED AT (`DEF-2965`).** A service the
            # utility bills whose accounts never reached the adapter produces no
            # pair and therefore no complaint, so a bare `MET` used to be
            # printed over it. It is named here instead.
            unseen = sorted(
                set(row.get("enabled_services") or []) - set(row.get("services_measured") or [])
            )
            # ⚠ **THE ESTATE IS THE FOURTH PRECONDITION AND IT IS A HARD `NOT
            # MET` (`DEF-2965`).** The three above are read off the accounts
            # this pass contained; this one is read off the utility. A billable
            # account whose connection has no recorded size, on a BANDED
            # service, is refused BY NAME at R3 on billing day with no fallback
            # (`BR-BIL-872`) — that is not a silence about something unmeasured,
            # it is a measured refusal, so it outranks the `SILENT on` wording.
            unsized = row.get("unsized_services") or []
            at_risk = sum(
                est.get("billable_accounts_with_no_size", 0)
                for code, est in (row.get("estate") or {}).items()
                if code in unsized
            )
            state = (
                "NOT MET — nothing to measure" if not row["pairs"]
                else "NOT MET"
                if (row["unpriced"] or row["undetermined"] or missing or unsized)
                # **NOT a bare MET while a billed service was never examined.**
                # It is not a failure — nothing was found wrong — but it is not
                # a clearance either, and the two must not read the same.
                else f"MET for what was measured · SILENT on {', '.join(unseen)}" if unseen
                else "MET"
            )
            add(f"    {tenant_name:<28} {len(row['pairs'])} pair(s) · "
                f"{len(row['unpriced'])} unpriced · "
                f"{len(row['undetermined'])} undecided · "
                f"{len(missing)} service(s) with no base charge code · "
                f"{at_risk} account(s) with no recorded size  ->  {state}")
            seen = sorted(row.get("services_measured") or [])
            add(f"      services examined: {', '.join(seen) if seen else 'none'}"
                + (f"  ·  ENABLED BUT NOT EXAMINED: {', '.join(unseen)}" if unseen else ""))
            for service in missing:
                add(f"      no `is_base` charge code for {service!r} — R4 refuses every "
                    "account of it (BR-RAT-088). Declare one under Charge codes.")
            for service in unseen:
                add(f"      {service!r} is enabled on this utility and NO account of it "
                    "reached this pass, so R3 and R4 are UNTESTED for it here. If it is "
                    "banded, a meter with no recorded connection size is refused by name "
                    "and that bill stops (BR-RAT-120).")
            for service in unsized:
                est = row["estate"][service]
                add(f"      {est['billable_accounts_with_no_size']} billable account(s) on "
                    f"{service!r} have a connection with NO recorded size "
                    f"({est['connections_with_no_size']} of {est['connections']} "
                    "connections). R3 refuses each of them on billing day, by name, and a "
                    "size may not be guessed. This is CONFIGURATION THE UTILITY HAS NOT "
                    "FINISHED, not a fault in the engine: record the size on the meter "
                    "(Assets, or the size column on the meter upload).")
        # ⚠ **ONE CHAIN, NOT TWO.** Written as a separate `if`, the base-code
        # block printed its "must NOT be switched on" paragraph and the
        # all-clear paragraph in the same run, four lines apart — a report that
        # contradicts itself is worse than one that says nothing, because a
        # reader takes whichever half they scrolled to.
        if unsized_any:
            # ⚠ **FIRST IN THE CHAIN BECAUSE IT IS THE ONE NO PREPARED RUN CAN
            # SEE.** Everything below it is a finding about the accounts this
            # pass contained; this is a finding about the accounts it could not
            # contain, and it is the one that reads MET while bills stop.
            add(f"  {accounts_at_risk_all} BILLABLE ACCOUNT(S) HAVE A CONNECTION WITH NO "
                f"RECORDED SIZE, on: {', '.join(unsized_any)}")
            add("  R3 + R4 must NOT be switched on here: R3 refuses each of those accounts")
            add("  on billing day, by name, and a size may not be guessed (BR-BIL-872 gives")
            add("  a switched rule no fallback). This is CONFIGURATION THE UTILITY HAS NOT")
            add("  FINISHED rather than a fault in the engine — the PO ruled on 2026-08-28")
            add("  that we charge on the size the account actually has, and you cannot")
            add("  charge on a size you do not have. Record the size on each meter (Assets,")
            add("  or the size column on the meter upload), then re-run this.")
        elif no_base:
            add(f"  {len(no_base)} service(s) with NO BASE CHARGE CODE: {', '.join(no_base)}")
            add("  R3 + R4 must NOT be switched on here: R4 refuses every account of those")
            add("  services by name (BR-RAT-088 — the charge code owns the base amount, and")
            add("  BR-BIL-872 gives a switched rule no fallback). Declare a base charge code")
            add("  for each under Charge codes and mark it as the base, then re-run this.")
        elif unpriced:
            add(f"  {len(unpriced)} pair(s) NOTHING PRICES: {', '.join(unpriced)}")
            add("  R3 is NOT released. Each of these is a size to price on the base charge code")
            add("  (or on the rate schedule where the service declares no base code).")
        elif undecided:
            add(f"  {len(undecided)} pair(s) could not be decided at R3 — an R1 or R2 finding, not")
            add("  an R3 one, and R3's condition cannot be read while they stand.")
        elif measured_nothing:
            add(f"  {len(measured_nothing)} utility/utilities carried NO (service · size) pair at "
                f"all: {', '.join(measured_nothing)}.")
            add("  Nothing was priced wrongly there — nothing was measured there. R3's condition")
            add("  is silent on a utility whose accounts never reached the adapter, and a silence")
            add("  is not a pass.")
        elif by_tenant:
            add("  ZERO pairs with nothing pricing them, every service this utility BILLS")
            add("  has a base charge code, and no billable account holds a connection with")
            add("  no recorded size — on every utility measured. The last of those three")
            add("  was not asked before 2026-09-01 (DEF-2965) and is the only one that")
            add("  looks outside this run's own population.")
            if unseen_any:
                # ⚠ **THE CLAUSE THAT WOULD HAVE CAUGHT THE ELECTRIC CASE
                # (`DEF-2965`).** Without it this paragraph reads as a clearance
                # for the whole deployment when it is a clearance for the
                # services that happened to have accounts in this pass.
                add("")
                add(f"  ⚠ BUT {len(unseen_any)} BILLED SERVICE(S) WERE NEVER EXAMINED: "
                    f"{', '.join(unseen_any)}.")
                add("  Not one account of them reached this pass, so R3 and R4 are UNTESTED")
                add("  for them here and NOTHING BELOW SPEAKS FOR THEM. A banded service whose")
                add("  meters carry no recorded connection size is refused BY NAME and those")
                add("  bills stop (BR-RAT-120) — which is exactly the case this report could")
                add("  not see on 2026-09-01, when three utilities billing only water, sewer")
                add("  and trash returned MET and said nothing about electric.")
                add("  Give them accounts on a cycle and re-run before trusting this verdict.")
                add("")
            add("  R3's release condition is MET on this database. R3 requires R4 with it")
            add("  (BR-BIL-873, one base charge from the pair), and THE PAIR IS ALREADY ON:")
            add("  the PO ruled it in on 2026-09-01 and the shipped default serves 'R3,R4'.")
            add("  So this verdict is no longer a release gate — it is the PER-UTILITY check")
            add("  that this deployment's utilities are configured for a switch already")
            add("  thrown. A utility that fails it is one whose bills will REFUSE.")
            add("  Rollback, one line, no release: SBH_BILLING_RESOLUTION_STEPS= (empty).")
        add("")
    if body.get("blocked_reasons"):
        add("FOR COMPLETENESS — accounts the RUN blocked before the shadow saw them")
        for reason, count in sorted(body["blocked_reasons"].items(), key=lambda kv: -kv[1]):
            add(f"  {reason}  ·  {count}")
        add("")
    add("THE CLASSES — one row per disagreement class, biggest first")
    if not body["classes"]:
        add("  none. Read this beside the agree column above, not as good news.")
    for row in body["classes"]:
        add("")
        add(f"  {row['class_id']}  ·  {row['accounts']} account(s)  ·  {row['occurrences']} occurrence(s)"
            + (f"  ·  services {', '.join(row['services'])}" if row["services"] else ""))
        add(f"    example account   {row['example_account_no']}")
        if row.get("example_live_display") or row.get("example_chain_display"):
            add(f"    live path says    {row.get('example_live_display') or row.get('example_live')}")
            add(f"    ruled path says   {row.get('example_chain_display') or row.get('example_chain')}")
        if row.get("example_sentence"):
            add(f"    the sentence      {row['example_sentence']}")
        if row.get("example_live_summary"):
            add(f"    what billing was  {row['example_live_summary']}")
            add("    about to use")
    add("")
    add("COULD NOT ASK AT ALL — per reason")
    if not body["blocked_classes"]:
        add("  none")
    for row in body["blocked_classes"]:
        add(f"  {row['reason']}  ·  {row['accounts']} account(s)  ·  e.g. {row['example_account_no']}")
        if row.get("example_detail"):
            add(f"    {row['example_detail']}")
    for note in result.get("what_if", []):
        add("")
        add("⚠ WHAT-IF IN FORCE — THIS RUN IS NOT THE MEASUREMENT:")
        add(f"  {note}")
    if result.get("sabotage"):
        add("")
        add("SABOTAGE IN FORCE — this run is a RED PROOF, not a measurement:")
        add(f"  {result['sabotage']}")
    add("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Per-step R1–R7 shadow disagreement count")
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument(
        "--sabotage",
        choices=(
            "R1",
            "R1-version",
            "R2",
            "R3",
            "R3-seam",
            "R3-coverage",
            "no-base-code",
            "estate-unsized",
            "service-coverage",
            "R3b",
            "R3b-tariff-mult",
            "R4",
            "R5",
            "R6",
            "R7",
        ),
        default=None,
    )
    parser.add_argument("--cycle", default=None)
    parser.add_argument(
        "--tenant",
        default=None,
        help=(
            "which utility/utilities to measure: a subdomain, a comma-separated list, "
            "or 'all'. Default is the first tenant by created_at, unchanged. Widening "
            "past one utility is the release condition the PO's 2026-08-31 cutover "
            "ruling states for the held steps R3, R3b, R5 and R6."
        ),
    )
    parser.add_argument(
        "--list-tenants",
        action="store_true",
        help="print the utilities on this database and exit",
    )
    parser.add_argument(
        "--what-if",
        dest="what_if",
        choices=("size-rows", "size-rows+base"),
        default=None,
        help="open R3's gate in the rolled-back transaction and report what is behind it",
    )
    args = parser.parse_args()

    if args.list_tenants:
        for tenant in tenancy_models.Tenant.objects.order_by("created_at"):
            print(f"{tenant.subdomain:24} {tenant.name}")
        return 0

    # Structural, not promised: nothing in this pass writes, and the
    # transaction proves it rather than a docstring claiming it.
    try:
        with transaction.atomic():
            result = measure(
                cycle_code=args.cycle,
                sabotage=args.sabotage,
                what_if=args.what_if,
                tenants=args.tenant,
            )
            raise _Done(result)
    except _Done as done:
        result = done.result

    print(render(result))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        print(f"(whole body written to {args.json})")
    return 0


class _Done(Exception):
    """Carries the figures out of the transaction that is thrown away."""

    def __init__(self, result: dict) -> None:
        super().__init__("done")
        self.result = result


if __name__ == "__main__":
    raise SystemExit(main())


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-052 task 20 · DEF-438 (the chain has no production caller) ·
#         decision log 2026-08-27 *"HOW R1–R7 GETS WIRED INTO BILLING — run
#         both, compare, rule, then switch"* step 4 · decision log 2026-08-28
#         *"R1–R7 STEP 3, DELIVERED"*, whose recorded next action is the
#         measurement this script performs
# generated: 2026-08-31 by the CR-052 task-20 measurement lane (claude)
# gates: golden-verify 33 PASS / 0 FAIL before and after — no ❄️ B4/B5 figure is
#         read, asserted or moved here; this script computes no money and
#         formats none (BR-RAT-087)
# exceptions: (1) **IT SWITCHES NOTHING.** `SERVED_BY_CHAIN_DEFAULT` is read and
#         printed and never written. No `ShadowOutcome` prices anything, no
#         disagreement is reconciled and no narrowing enters `gather.py`.
#         (2) **IT WRITES NO ROW.** `prepare_run` writes nothing by its own
#         contract and the whole pass is additionally rolled back.
#         (3) **A STEP IT CANNOT EVALUATE IS NEVER COUNTED AS AGREEMENT**, which
#         is the one property the table's third column exists to hold.
# ──────────────────────────────────────────────────────────
