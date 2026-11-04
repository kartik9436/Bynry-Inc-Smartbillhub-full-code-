# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-002 (S31.2 "Check what we found" — the pre-commit stage, the
#           one place every input is shown before anything commits)
#           Screens: S31.2
# Defects:  DEF-438 (the R1–R7 chain has no production caller) · DEF-1810 ·
#           DEF-1811 (the shadow could not be run on a single real account —
#           the reason the screen half was withheld) · DEF-1812 · DEF-1813
#           (CLOSED 2026-08-28; the last missing fact, which is what makes this
#           panel readable at all)
# Rules:    BR-BIL-039 (the preview and the real run are the SAME code, which is
#           why a disagreement belongs on the preview) · BR-SHL-020 (a refusal
#           reads as a sentence, not a code) · BR-RAT-087 (money carries the
#           server's own display companion; the client never formats money) ·
#           CLAUDE.md rule 1 (tenant scoping) · B1 (no cross-module import)
# Tests:    06-backend/tests/test_step3_shadow_panel.py
# Impacts:  apps/billing/resolution_shadow.py (this is its FIRST production
#           caller, and the decision log names this screen as the only lawful
#           one) · apps/billing/api.run_pricing_shadow · apps/billing/runs.py
#           (READ ONLY — nothing here is called from the run, so a fault in this
#           file cannot break a bill)
# ───────────────────────────────────────────────────────
"""STEP 3 OF THE CUTOVER: put the disagreements on the pre-commit screen.

HUMAN-REVIEW-PENDING — this file reads the output of rating math and decides
what an operator is told about it. It computes no money and writes nothing, but
it stands next to a CLAUDE.md sensitive path, so it is AI-authored under the PO
ruling of 2026-08-09 with a row in `12-governance/09-human-review-ledger.md`.

⚠ CORRECTED 2026-08-31 — THE PARAGRAPH BELOW IS HISTORY, NOT THE CURRENT STATE.
A glob in 10-scripts/gates/human_owned.txt DOES match this file now: the PO
ruled on 2026-08-31, having been shown all 62 unguarded files in five groups,
that groups one to four go on the watched list — "56 files" in their own words
— and this file is one of them. G7 checks it from that commit. The paragraph is
kept because WHY it went unguarded is worth knowing (DEF-2790: the check
written to catch exactly this looked for the wrong marker for three days), and
nothing below it should be read as describing today.

⚠ **NO GLOB IN `10-scripts/gates/human_owned.txt` MATCHES THIS FILE, AND A LANE
MAY NOT ADD ITSELF** — editing that list is a process event and the PO's call
(`metering_seam.py`, `payments_seam.py` and `posting_seam.py` all took this
posture before it). The line is RAISED in the review ledger instead. This file
does NOT declare `HUMAN-OWNED`, deliberately: G53 fails a file that claims to be
guarded while no glob reaches it, and claiming a guarantee nothing enforces is
hard-won law 1.

WHAT THIS IS
------------
Step 3 of the six-step cutover recorded in `12-governance/02-decision-log.md`,
2026-08-27, *"HOW R1–R7 GETS WIRED INTO BILLING — run both, compare, rule, then
switch. Never swap and hope."* Steps 1 and 2 (the adapter and the shadow run)
are `resolution_shadow.py`. This is the half that shows the result to a person:

    | 3 | **Surface** the disagreements on the pre-commit screen, by step and by
        account | nothing |

**"nothing" is that table's own entry under "what changes on a bill", and it is
a property this file must keep.** It prices nothing, it writes nothing, and it
is called from no code path a bill ever travels — `runs.prepare_run` and
`runs.calculate_account` do not import this module. A fault here shows an
operator an empty panel; it cannot stop or alter a bill run. That separation is
deliberate: putting the shadow inside `prepare_run` would have made a bug in an
unruled comparison able to break a real run.

WHY IT IS BUILT NOW, WHEN THE LAST LANE DELIBERATELY DID NOT BUILD IT
---------------------------------------------------------------------
The recorded judgment (decision log, 2026-08-27 §4) was: *"A count that is
always zero means the chain is not running, and nothing else would say so.
Today that count is always zero AND the chain is not running. Shipping the
S31.2 panel now would ship the exact reading the decision log says to
distrust."* **That reason has expired.** `DEF-1813` closed on 2026-08-28 —
the fourth and last of the four missing facts — and the shadow now attempts a
real account and comes back with a real refusal on it.

⚠ THE THREE RULES THIS PANEL OBEYS, AND EVERY ONE OF THEM IS A RULING
----------------------------------------------------------------------
1. **`attempted` IS SHOWN BESIDE `disagreed`, ALWAYS.** *"READ THE THIRD AND
   FOURTH NUMBERS TOGETHER OR THEY LIE. '0 disagreed' is also what perfect
   agreement looks like."* This body cannot be rendered without `attempted`:
   the two counts are siblings in one dict and the screen prints them in one
   sentence.
2. **IT MAY NOT MAKE A DISAGREEMENT GO AWAY.** *"A lane that makes the
   disagreements go away has destroyed the evidence this job exists to produce,
   and has done it inside the one system where a wrong answer is irreversible."*
   So every divergence carries BOTH figures verbatim and this file chooses
   neither, computes no difference between them, and has no fallback, no
   default and no rounding that could bring two numbers together.
3. **"COULD NOT ASK" IS ITS OWN STATE.** An account the adapter could not
   assemble inputs for is a missing FACT, not agreement. `not_attempted` and
   `blocked_by_reason` are served on every response, so an operator can tell
   three things apart: the two paths agreed, the two paths differed, nobody
   could ask.

⚠ IT RUNS OVER THE WHOLE RUN, NOT ONE ACCOUNT, AND THAT IS THE POINT
--------------------------------------------------------------------
**A disagreement CLASS cannot be ruled from a single account.** Nobody can
decide *"the two engines mean different things by a plan in force"* from one
row; that ruling is step 4 and it needs to know whether the class touches one
account or four hundred. So `report_for_prepared` walks EVERY ready account in
the run and reports each class with the number of accounts it touches, one
worked example, and both of that example's figures.

⚠ **AND `attempted` MATTERS MORE AT SCALE, NOT LESS.** *"1,200 accounts · 0
disagreed"* reads as triumph and may be *"0 attempted"*. The two counts are
siblings in one dict here for exactly that reason, at every scale.

**WHAT THIS COSTS, MEASURED RATHER THAN CLAIMED.** `resolve()` is pure and
`gather_account` has already loaded the facts, so the comparison itself is CPU
and no I/O. The ADAPTER is not free: `resolution_shadow.adapt` resolves the
connection size, the multiplier and the unit row through metering's seams, and
those are per account. **That is reported, not hidden** — see the trailer's
exception (6). It cannot slow a bill run, because no bill path imports this
module; it makes THIS panel slower on a large run and nothing else.

WHY A SEPARATE ENDPOINT AND NOT A MEMBER OF `findings_dict`
------------------------------------------------------------
Two reasons, and the first is the load-bearing one.

* **`findings_dict` is the screen that decides whether a bill run proceeds.**
  `compare()` raises rather than reporting parity when it compared nothing, by
  design — *"an empty comparison is a failure, not a pass"* — so folding the
  shadow into the findings body would let an unruled comparison 500 the stage a
  clerk cannot bill without. The shadow is advisory; the findings are not.
* The panel is read by someone reviewing the CUTOVER, not by every clerk on
  every run. A second request is the honest shape for that.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from apps.billing import resolution_shadow, runs

__all__ = [
    "CLASS_FIGURES_DIFFER",
    "MONEY_STEPS",
    "SHADOW_ROW_UNAVAILABLE",
    "SHADOW_RAISED",
    "classes_from",
    "live_summary",
    "report_for_prepared",
]

#: Divergence steps whose two figures are MONEY. Keyed off the step rather than
#: sniffed off the value's type, so a `Decimal` that is not money (a count, a
#: version ordinal) never acquires a currency-shaped display string it has not
#: earned. R1 and R2 disagree about IDENTIFIERS; **R4** disagrees about a base
#: charge, which is money and carries BR-RAT-087's display companion.
#:
#: ⚠ **`R3` IS DELIBERATELY NOT IN THIS SET, AND THAT IS `DEF-2823`.** Until
#: 2026-08-31 the base was one fused `R3/R4` figure. R3 now disagrees about a
#: CONNECTION SIZE — `W-58` against `2-inch` — which is a size-class code and
#: not money; formatting it as currency would misstate what the two paths
#: differed on. The old fused key stays in the set so a panel rendered from a
#: stored earlier run still formats its money, and nothing emits it any more.
MONEY_STEPS = frozenset({"R4", "R3/R4"})

#: What a divergence with no `note` of its own is called. The chain's refusals
#: name themselves; a bare figure difference does not, so it is given ONE name
#: rather than a hundred — a class is *"R4 water: the two paths resolved
#: different base charges"*, and the ACCOUNT COUNT beside it is what makes it
#: rulable. It is never given a name that implies which figure is right.
CLASS_FIGURES_DIFFER = "the two paths resolved different figures"

#: The account was in the run's ready set and its row could not be re-resolved,
#: so the chain was not run on it. Reported as a REASON under `not_attempted`,
#: never folded into agreement — the same distinction `resolution_shadow`'s own
#: `MISSING_*` constants draw.
SHADOW_ROW_UNAVAILABLE = "shadow_account_row_unavailable"

#: The shadow raised where it should have REPORTED. `compare()` does this
#: deliberately when it compared nothing (*"an empty comparison is a failure,
#: not a pass"*), and it is exactly the finding that must reach a person rather
#: than a log. It is `not_attempted` and not `agreed`, for the same reason
#: every other blocked state is: nothing was compared.
SHADOW_RAISED = "shadow_comparison_raised"


def _text(value: Any) -> str | None:
    """One side of a divergence, VERBATIM, as a string.

    Never a boolean, never a summary. *"Billing and rating disagree"* is not
    actionable; *"R2 water: live resolved version 7, the chain resolved version
    9"* is (`resolution_shadow.Divergence`'s own docstring). `None` stays
    `None`, because "the live path resolved nothing here" is a fact and the
    string `"None"` is not.
    """
    return None if value is None else str(value)


def _display(step: str, value: Any) -> str | None:
    """BR-RAT-087's DISPLAY companion for a money figure — the SERVER's, always.

    *"If the client may not format, the server must."* The stored figure travels
    beside it untouched, so the panel prints the pair the server sent and does
    no money arithmetic of its own.

    ⚠ **THIS ROUNDS FOR DISPLAY AND NOTHING ELSE, AND IT MAY NOT BE USED TO
    MAKE TWO FIGURES MATCH.** `$8.0000` and `$8.0049` both display `8.00`, so a
    panel that compared the DISPLAY strings would report agreement on a
    disagreement — which is the one thing this whole exercise forbids. The
    comparison already happened in `resolution_shadow.compare()`, on the stored
    values; this is a label.
    """
    if value is None or step not in MONEY_STEPS:
        return None
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError, ArithmeticError):
        # A step declared money whose value will not parse is a finding of its
        # own. It is left WITHOUT a display string rather than shown as 0.00,
        # which would be a money claim about a value nobody could read.
        return None


def live_summary(data: Any) -> str | None:
    """WHAT THE PATH THAT BILLS TODAY RESOLVED, in one readable line.

    ⚠ **THIS EXISTS FOR THE REFUSAL ROWS, WHICH ARE THE HIGHEST-VALUE ROWS IN
    THE EXERCISE.** *"A disagreement where the chain REFUSES and the live path
    produced a number is the highest-value row in the report, not an
    inconvenience"* — *"a bill that would have gone out on a guess."* A refusal
    has no chain figure to put beside a live one, so without this the class row
    would say *"the new rules will not price it"* and say nothing at all about
    what today's billing was about to do.

    ⚠ **IT IS NOT A BILL TOTAL AND MUST NEVER BE READ AS ONE.** Phase 1 computes
    no money (`selectors.exceptions_dict`: *"phase 1 computes no money at
    all"*), so what is in hand is the PLAN and, per service, the tariff version
    and its base charge. Those are named as what they are. Composing a total
    from them would be inventing the very figure the run has not worked out yet.

    Composed on the SERVER because the money in it is money (BR-RAT-087 — the
    client never formats money).
    """
    plan = data.rate_plan_name or data.rate_plan_id
    if plan is None:
        return None
    version = data.rate_plan_version
    head = f"{plan} (v{version})" if version is not None else str(plan)
    parts: list[str] = []
    for config in data.tariffs:
        base = _display("R4", config.base_charge)
        if base is None:
            parts.append(f"{config.service} on version {config.version_id}")
        else:
            parts.append(f"{config.service} base {base} on version {config.version_id}")
    return head if not parts else f"{head} — " + "; ".join(parts)


def _divergence_dict(divergence: Any) -> dict[str, Any]:
    """One row of the panel: a step, a service, and BOTH figures.

    `sentence` is `Divergence.sentence()` — one line a clerk can act on
    (BR-SHL-020). It is served rather than composed on the client because the
    two figures are the finding and a client that re-assembled them could
    silently drop one.
    """
    step = divergence.step
    return {
        "step": step,
        "service": divergence.service or None,
        "live": _text(divergence.live),
        "chain": _text(divergence.chain),
        "live_display": _display(step, divergence.live),
        "chain_display": _display(step, divergence.chain),
        "is_money": step in MONEY_STEPS,
        "note": divergence.note or None,
        "sentence": divergence.sentence(),
    }


def _outcome_dict(outcome: Any, summary: str | None) -> dict[str, Any]:
    """One ACCOUNT's whole result — the by-account grouping, in full.

    `refusal_sentence` is the chain's OWN message, unedited and whole. Rendering
    the exception CLASS NAME instead is named in the decision log as *"the lazy
    way to make the first test pass"*, so both are served and the screen shows
    the sentence: `refusal_type` is there for a reader who wants to grep the
    code, never as the thing on screen.
    """
    return {
        "account_id": outcome.account_id,
        "account_no": outcome.account_no,
        "status": outcome.status,
        "refusal_step": outcome.refusal_step,
        "refusal_type": outcome.refusal_type,
        "refusal_sentence": outcome.refusal_sentence,
        # ── `DEF-RAT-7991`, 2026-09-29 ──────────────────────────────────────
        # `refusal_sentence` is the ENGINEER's, uuids and all, and the bill-run
        # screen printed it raw. These two are what a clerk may read: the
        # catalogue key in their own language, and its id-free English mirror.
        # Null where the chain states none, and the screen shows nothing then
        # rather than falling back to the sentence above (B14 rule 31).
        "refusal_message_key": outcome.refusal_message_key,
        "refusal_clerk_detail": outcome.refusal_clerk_detail,
        "refusal_message_params": outcome.refusal_message_params or None,
        "blocked_reason": outcome.blocked_reason,
        "blocked_detail": outcome.blocked_detail,
        #: What the path that bills TODAY resolved for this account. Present on
        #: every row, and it is the only thing on a REFUSAL row that says what
        #: was about to happen if nobody looked.
        "live_summary": summary,
        "divergences": [_divergence_dict(row) for row in outcome.divergences],
    }


def _steps_from(outcomes: tuple[Any, ...]) -> list[dict[str, Any]]:
    """The by-STEP grouping — the chain's nine typed refusals as a vocabulary.

    *"`R3 — this size is not priced` is a sentence a utility can act on in a
    minute; the live path's equivalent silence is found in an audit."* So the
    panel leads with the step, and each step carries the accounts it was found
    on, in the order the run walked them.

    A step appears here ONLY if something was found at it. An empty list is the
    honest rendering of "nothing was found", and it is read beside `attempted`
    — which is what stops it being mistaken for "everything agreed".
    """
    steps: dict[str, dict[str, Any]] = {}

    def _bucket(step: str) -> dict[str, Any]:
        return steps.setdefault(
            step, {"step": step, "accounts": [], "count": 0, "refusals": 0, "divergences": 0}
        )

    for outcome in outcomes:
        seen: set[str] = set()
        for divergence in outcome.divergences:
            bucket = _bucket(divergence.step)
            bucket["count"] += 1
            bucket["divergences"] += 1
            if outcome.account_no not in seen:
                bucket["accounts"].append(outcome.account_no)
                seen.add(outcome.account_no)
        if outcome.refusal_step:
            bucket = _bucket(outcome.refusal_step)
            bucket["count"] += 1
            bucket["refusals"] += 1
            if outcome.account_no not in seen:
                bucket["accounts"].append(outcome.account_no)
                seen.add(outcome.account_no)
    return [steps[key] for key in sorted(steps)]


def classes_from(
    outcomes: tuple[Any, ...], summaries: dict[str, str | None] | None = None
) -> list[dict[str, Any]]:
    """THE LIST STEP 4 IS RULED FROM — one row per CLASS, with its account count.

    ⚠ **THIS IS THE DELIVERABLE OF THE WHOLE STEP.** *"Rule each class of
    disagreement — PO's call, not a lane's."* A ruling needs three things and
    this row carries all three: **what** the two paths disagreed about, **both
    figures** for a worked example, and **how many accounts** it touches. One
    account disagreeing at R1 and four hundred disagreeing at R1 are the same
    class and a completely different decision.

    A CLASS is `(step, the thing that differed)`:

    * a chain REFUSAL is classed by its typed name — `R1 · NoPlanInForce` — the
      vocabulary the chain already publishes and the one the decision log calls
      its *signature*;
    * a figure DIVERGENCE is classed by its own `note` where it has one (*"the
      live path resolved no tariff for this service"*), and otherwise by the one
      neutral name `CLASS_FIGURES_DIFFER`. Neutral on purpose: naming it *"the
      chain is wrong"* would be this file taking step 4's decision.

    **The example is the FIRST occurrence in run order and carries both figures
    unchanged.** No average, no range, no "and 399 others differ by about" —
    every one of those would be arithmetic over two answers where the product
    does not yet know which is right.

    Services are listed rather than folded away: *"R2 water"* and *"R2 gas"* are
    the same shape and can be very different findings.
    """
    rows: dict[tuple[str, str], dict[str, Any]] = {}

    def _row(step: str, label: str, kind: str, refusal_type: str | None) -> dict[str, Any]:
        return rows.setdefault(
            (step, label),
            {
                "class_id": f"{step} · {label}",
                "kind": kind,
                "step": step,
                "what": label,
                "refusal_type": refusal_type,
                "services": [],
                "accounts": 0,
                "occurrences": 0,
                "example_account_no": None,
                "example_sentence": None,
                "example_service": None,
                "example_live": None,
                "example_chain": None,
                "example_live_display": None,
                "example_chain_display": None,
                "example_live_summary": None,
                "is_money": False,
                "_seen_accounts": set(),
            },
        )

    def _touch(row: dict[str, Any], account_no: str, service: str | None) -> None:
        row["occurrences"] += 1
        if account_no not in row["_seen_accounts"]:
            row["_seen_accounts"].add(account_no)
            row["accounts"] += 1
        if service and service not in row["services"]:
            row["services"].append(service)

    known = summaries or {}
    for outcome in outcomes:
        for divergence in outcome.divergences:
            label = divergence.note or CLASS_FIGURES_DIFFER
            row = _row(divergence.step, label, "divergence", None)
            _touch(row, outcome.account_no, divergence.service or None)
            if row["example_account_no"] is None:
                served = _divergence_dict(divergence)
                row["example_account_no"] = outcome.account_no
                row["example_live_summary"] = known.get(outcome.account_id)
                row["example_sentence"] = served["sentence"]
                row["example_service"] = served["service"]
                row["example_live"] = served["live"]
                row["example_chain"] = served["chain"]
                row["example_live_display"] = served["live_display"]
                row["example_chain_display"] = served["chain_display"]
                row["is_money"] = served["is_money"]
        if outcome.refusal_step:
            row = _row(
                outcome.refusal_step,
                outcome.refusal_type or "refused",
                "refusal",
                outcome.refusal_type,
            )
            _touch(row, outcome.account_no, None)
            if row["example_account_no"] is None:
                row["example_account_no"] = outcome.account_no
                # ⚠ WHAT TODAY'S BILLING RESOLVED, BESIDE THE REFUSAL. Without
                # it this row says the new rules will not price the account and
                # says nothing about the bill that was about to go out on the
                # old ones — which is the half a person acts on.
                row["example_live_summary"] = known.get(outcome.account_id)
                # ⚠ THE CHAIN'S OWN SENTENCE, WHOLE. Rendering the exception
                # class name here instead is named in the decision log as "the
                # lazy way to make the first test pass".
                row["example_sentence"] = outcome.refusal_sentence
                # A refusal has no pair of figures: the ruled path produced no
                # number at all, and that ABSENCE is the finding. `live` is left
                # null rather than filled with the live figure dressed up as a
                # comparison — the live amount for a refused account is on that
                # account's own row, where it is not mistaken for a match.
    ordered = sorted(rows.values(), key=lambda row: (-row["accounts"], row["class_id"]))
    for row in ordered:
        row.pop("_seen_accounts", None)
    return ordered


def _blocked_classes(outcomes: tuple[Any, ...]) -> list[dict[str, Any]]:
    """The COULD-NOT-ASK classes, counted the same way and read the same way.

    ⚠ **AN ACCOUNT NOBODY COULD ASK ABOUT IS NOT AN ACCOUNT THAT AGREED**, and
    at run scale that is the difference between *"nothing to rule"* and *"we
    measured nothing"*. Each reason carries its account count and one example
    sentence, so a reader can see what a person would have to go and do.
    """
    rows: dict[str, dict[str, Any]] = {}
    for outcome in outcomes:
        if not outcome.blocked_reason:
            continue
        row = rows.setdefault(
            outcome.blocked_reason,
            {
                "reason": outcome.blocked_reason,
                "accounts": 0,
                "example_account_no": None,
                "example_detail": None,
            },
        )
        row["accounts"] += 1
        if row["example_account_no"] is None:
            row["example_account_no"] = outcome.account_no
            row["example_detail"] = outcome.blocked_detail
    return sorted(rows.values(), key=lambda row: (-row["accounts"], row["reason"]))


def _accounts_by_id(prepared: Any) -> dict[str, Any]:
    """The Account rows for this run's ready set, re-resolved through the seam.

    Billing may not import another module's models (B1 / gate G6), so the rows
    come back through `customers.accounts_for_bill_run` — the SAME seam
    `prepare_run` used to build the set in the first place, asked for the same
    anchor units. `prepared.coverage` already holds those anchors (anchor
    first, DEF-572), so this costs one query for the run and no per-account
    lookup.

    An empty map is a legitimate answer and the caller reports it by name; it
    is never treated as "these accounts agreed".
    """
    accounts_for = runs._resolve("customers", "accounts_for_bill_run")
    if accounts_for is None:
        return {}
    anchors = [units[0] for units in prepared.coverage.values() if units]
    if not anchors:
        return {}
    return {str(account.id): account for account in accounts_for(anchors)}


def report_for_prepared(prepared: Any) -> dict[str, Any]:
    """The S31.2 pricing-shadow panel, whole.

    `prepared` is `runs.PreparedRun` — the run's own phase-1 pass, the object
    the findings screen is already drawn from. Taking it as an argument rather
    than re-preparing is what makes the panel and the findings describe the same
    instant: a second prepare pass could differ from the first for no reason but
    the clock.

    THE BODY, and every member of it is a ruling:

    * `attempted` · `agreed` · `disagreed` · `chain_refused` · `not_attempted` ·
      `accounts` — `resolution_shadow.summarise()` verbatim, unedited. The
      screen may not show `disagreed` without `attempted`.
    * `by_step` — the summary's own count per step, and `steps` beside it, the
      same grouping with the account numbers attached.
    * `classes` — **the list step 4 is ruled from**: one row per class of
      disagreement, with the number of ACCOUNTS it touches and one worked
      example carrying both figures. Ordered by account count, biggest first,
      because that is the order the rulings are worth making in.
    * `blocked_by_reason` — why an account could not be asked, per reason — and
      `blocked_classes` beside it, the same counts with an example sentence.
    * `accounts_detail` — one row per account, with every divergence's two
      figures.
    """
    outcomes: list[Any] = []
    summaries: dict[str, str | None] = {}
    rows = _accounts_by_id(prepared)
    for data in prepared.ready:
        summaries[str(data.account_id)] = live_summary(data)
        account = rows.get(str(data.account_id))
        if account is None:
            outcomes.append(
                resolution_shadow.ShadowOutcome(
                    account_id=data.account_id,
                    account_no=data.account_no,
                    status=resolution_shadow.STATUS_NOT_ATTEMPTED,
                    blocked_reason=SHADOW_ROW_UNAVAILABLE,
                    blocked_detail=(
                        "this account was in the run's ready set and its record could "
                        "not be read back, so the ruled path was not run on it. That is "
                        "a fact nobody has, not an agreement between the two paths."
                    ),
                )
            )
            continue
        try:
            outcomes.append(
                resolution_shadow.shadow_account(
                    data, account=account, service_date=prepared.service_date
                )
            )
        except Exception as raised:  # noqa: BLE001 — see below
            # ⚠ **THIS IS NOT SWALLOWING A DISAGREEMENT AND THE DISTINCTION IS
            # THE WHOLE POINT.** `shadow_account` REPORTS the chain's own typed
            # refusals; anything that escapes it is the comparison failing to
            # happen — `compare()` raises on purpose when it compared nothing,
            # because *"a parity checker that compares nothing returns no
            # divergences and reads as green"*. Recording it as `not_attempted`
            # with its own sentence puts it in front of a person under "could
            # not ask", which is what it is. Letting it propagate would blank
            # the panel for every OTHER account in the run, including the ones
            # that did disagree.
            outcomes.append(
                resolution_shadow.ShadowOutcome(
                    account_id=data.account_id,
                    account_no=data.account_no,
                    status=resolution_shadow.STATUS_NOT_ATTEMPTED,
                    blocked_reason=SHADOW_RAISED,
                    blocked_detail=f"{type(raised).__name__}: {raised}",
                )
            )

    frozen = tuple(outcomes)
    body = dict(resolution_shadow.summarise(frozen))
    body["steps"] = _steps_from(frozen)
    body["classes"] = classes_from(frozen, summaries)
    body["blocked_classes"] = _blocked_classes(frozen)
    body["accounts_detail"] = [
        _outcome_dict(outcome, summaries.get(str(outcome.account_id))) for outcome in frozen
    ]
    return body


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-002 (S31.2 "Check what we found") · decision log 2026-08-27
#         *"HOW R1–R7 GETS WIRED INTO BILLING — run both, compare, rule, then
#         switch"* step 3, and *"R1–R7 STEP 3, DELIVERED"* §4, the recorded
#         judgment this file discharges · decision log 2026-08-28 `DEF-1813`
#         (the fact that made the judgment expire) · BR-BIL-039 · BR-SHL-020 ·
#         BR-RAT-087
# generated: 2026-08-28 by the R1–R7 step-3 screen lane (claude)
# checklist: A✔ B✔ C✔ D✔ E✔ (the S31.2 panel in
#         features/billing/billRunShared.tsx, mounted by BillRunWizard.tsx —
#         i18n keys only, in all ELEVEN catalogues; no money is formatted here)
#         F✔ G✔ H=deferred(PO 2026-08-09)
# gates: golden-verify 33 PASS / 0 FAIL before and after — NO ❄️ B4/B5 figure is
#         asserted, moved or read here · run_gates unchanged by this file ·
#         tests/test_step3_shadow_panel.py
# exceptions: (1) **NOTHING HERE PRICES ANYTHING AND NOTHING CALLS IT FROM A
#         BILL PATH.** Steps 1–4 of the recorded cutover all read "nothing" in
#         the "what changes on a bill" column, and the separation is structural
#         rather than promised: `runs.py` does not import this module, so a
#         fault here cannot reach `prepare_run`, `calculate_account` or issue.
#         (2) **NO DIFFERENCE IS COMPUTED BETWEEN THE TWO FIGURES.** Both are
#         served verbatim and the panel prints both. Subtracting them would be
#         this file deciding which one is right, which is step 4 and is the
#         PO's.
#         (3) **AN ESCAPED EXCEPTION IS `not_attempted`, NOT `agreed`.** See the
#         comment at the catch — `compare()` raises deliberately when it
#         compared nothing, and that finding must reach a person.
#         (4) `_display` rounds for DISPLAY only (BR-RAT-087) and the stored
#         figure is served beside it untouched. The comparison is made on the
#         stored values inside `resolution_shadow.compare()`, never on these
#         strings — two figures that display alike are still a disagreement.
#         (5) NO GLOB in `10-scripts/gates/human_owned.txt` matches this file
#         and a lane may not add itself. RAISED in the review ledger.
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING — row in
#         12-governance/09-human-review-ledger.md.
# ──────────────────────────────────────────────────────────
