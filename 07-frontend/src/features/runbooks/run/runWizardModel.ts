// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-001 (EP-RBS-01) · CR-075 wave C task C4.
//          Screens: RBS-005.1 Scope · RBS-005.2 Checking · RBS-005.6 Done ·
//          RBS-005.8 a check itself failed.
// Rules:   `RBR-01` (every step listed before the first one starts; a step that
//          did not run carries the reason) · `BR-RBS-002` (a Check is
//          CONSTRUCTED with no ports) · `BR-RBS-009` (scope resolved once and
//          pinned) · `BR-RBS-042` (a runbook is one fixed process with declared
//          INPUTS; nobody arranges steps) · B14 rule 3 (the numbered rail).
// Tests:   runWizardModel.test.ts · RunWizard.test.tsx
// Defects: DEF-RBS-4286 (a run records no per-step outcome anywhere — this file
//          is what makes that absence legible instead of blank).
// ───────────────────────────────────────────────────────
//
// THE FOUR-STEP CHECK PATH, AND WHERE THE NUMBER COMES FROM
// ══════════════════════════════════════════════════════════════════════════
// `04-flows.md` §4, verbatim: *"A Check's wizard is four steps, not six — it
// skips **Gate** and **Act** entirely… On screen that is the step rail of
// `RBS-005`: *Scope · Checking · Review · Approve · Applying · Done* for an
// Action, and the same rail without Approve and Applying for a Check."*
//
// So the four are **Scope · Checking · Review · Done**, and they are declared
// here once rather than typed into each screen. A Check has no Approve because
// there is nothing to approve: `BR-RBS-002` says a Check is CONSTRUCTED without
// action ports, so the capability to send is absent rather than withheld.
//
// ⚠ **REVIEW'S BODY IS NOT THIS FILE'S AND MUST NOT BECOME IT.** Step 3 draws
// the run's frozen report, which is `RBS-006` — the result renderer, task `C2`.
// That is why `C4` `depends_on` `C2` and on nothing else in the plan. The
// wizard takes it as a required slot (`RunWizardProps.review`); writing a
// second report renderer here would be the two-implementations mistake
// `TC-RBS-14` and `DEF-RBS-4284` are both about.
//
// ══════════════════════════════════════════════════════════════════════════
// THE PROGRESS LIST IS THE HONESTY ARGUMENT, AND IT HAS A HOLE UNDER IT
// ══════════════════════════════════════════════════════════════════════════
// `RBR-01` — one of the four rules `02-business-rules.md` records as having no
// `BR-RBS-` home — is this screen's whole reason to exist:
//
//     every step listed before the first one starts, with a reason on any that
//     did not run
//
// ⚠ **THE ENGINE SERVES THE FIRST HALF AND NOT THE SECOND (`DEF-RBS-4286`).**
// A runbook's DEFINITION carries `steps[]` with `key`, `label`, `mode` and
// `writes`, so the catalogue is real and can be drawn before anything runs. A
// RUN carries `status`, `counts` and `report` and **no per-step outcome at
// all**: `RunResult.step_runs` is an execution COUNT held in memory and never
// persisted, and `07-endpoints.md` row 9 specifies header, counts, status and
// approver. So *which step is running, which failed with what sentence, and
// which were never reached* has no field.
//
// **This file is written so that the hole shows rather than hides.** Hand it an
// empty `outcomes` map and every step reads *waiting* while the run is in
// flight and **Never reached** once it has stopped — never *done*, never blank.
// A list that says Done because a row is missing is worse than the single line
// it replaces, because it is confidently wrong.
//
// ⚠ **THE SHAPE IS BORROWED, DELIBERATELY, FROM `provisioningStepStates` IN
// `features/tenancy/SignupWizard.tsx`.** `08-screen-layouts.md` says so in as
// many words — *"the batch-progress pattern is not invented here — it copies
// what the product already does when it seeds a new utility"* — and that
// function is the one the PO asked for by name in `CR-064`. Its `DEF-3500`
// clause is the one worth copying: a step the run never REACHED says so on its
// own line, because that was the third case the PO's sentence covers and the
// only one that carried no words at all.

/** The four steps of a Check's rail, in order (`04-flows.md` §4). */
export const CHECK_STEPS = ["scope", "checking", "review", "done"] as const;

export type CheckStep = (typeof CHECK_STEPS)[number];

/**
 * Where the run is. Not the same vocabulary as `runbook_runs.status`, and the
 * difference is the point: `status` is what the SERVER recorded, `RunPhase` is
 * what the SCREEN is showing. A stopped run and a failed run are two statuses
 * and one screen.
 */
export type RunPhase =
  /** Nothing has been started; the clerk is looking at the scope (`RBS-005.1`). */
  | "scoping"
  /** In flight (`RBS-005.2`). */
  | "checking"
  /** A step itself failed and the run stopped there (`RBS-005.8`). */
  | "checkFailed"
  /** The findings are ready to read — step 3, drawn by `RBS-006`. */
  | "review"
  /** The run is over (`RBS-005.6`). */
  | "done";

/** B14 rule 3's three rail states. `done` is a tick, `current` the accent fill. */
export type RailState = "done" | "current" | "todo";

export interface RailCell {
  id: CheckStep;
  /** 1-based, and it is what the circle prints for a step not yet done. */
  position: number;
  state: RailState;
  /**
   * B14 rule 3: *"clickable when complete"*. A rail cell is navigation only
   * where the clerk has already been — never forward, which would let someone
   * skip Checking and read a report that does not exist yet.
   */
  clickable: boolean;
}

/** Which rail step a phase is standing on. */
const PHASE_STEP: Record<RunPhase, CheckStep> = {
  scoping: "scope",
  checking: "checking",
  checkFailed: "checking",
  review: "review",
  done: "done",
};

export function currentStep(phase: RunPhase): CheckStep {
  return PHASE_STEP[phase];
}

/**
 * The rail, computed from the phase and from nothing else.
 *
 * ⚠ **A FAILED CHECK LEAVES *Checking* CURRENT RATHER THAN MARKING IT DONE**,
 * which is what `RBS-005.8`'s frame draws — *✓ Scope → 2 Checking → 3 Review*,
 * with Checking carrying the accent fill. A tick on a step that broke would be
 * the same lie as a Done row with no record behind it.
 */
export function railCells(phase: RunPhase): RailCell[] {
  const at = CHECK_STEPS.indexOf(currentStep(phase));
  return CHECK_STEPS.map((id, index) => ({
    id,
    position: index + 1,
    state: index < at ? "done" : index === at ? "current" : "todo",
    clickable: index < at,
  }));
}

/* ── the progress list ──────────────────────────────────────────────────── */

/**
 * The five marker states `RBS-005.2` and `RBS-005.8` name in their own SIZE ·
 * STATE · RULE column: *"marker 18px: done success-500, current accent, skipped
 * n300, failed danger-500, waiting n500"*. Five words, five states, and the
 * component's tone map is keyed on exactly these so a sixth cannot appear
 * without a token for it.
 */
export type ProgressState = "done" | "current" | "failed" | "skipped" | "waiting";

/** One step as the runbook DECLARES it — the catalogue half of `RBR-01`. */
export interface StepCatalogueEntry {
  key: string;
  /** The clerk-facing words the definition carries. Never the key (B14 rule 31). */
  label: string;
}

/**
 * One step as the RUN reports it.
 *
 * ⚠ **NOTHING SERVES THIS TODAY (`DEF-RBS-4286`).** It is declared because the
 * screen cannot be honest without the shape, and because a caller that HAS the
 * data — a fixture, a walkthrough, or the endpoint the defect asks for — can
 * pass it with no change here. What is not done is inventing a source for it.
 */
export interface StepOutcome {
  state: "done" | "failed" | "skipped";
  /**
   * The run's OWN sentence about this step, verbatim and untranslated — the
   * `SignupWizard` posture, where `reason` is a promise that the bytes are the
   * server's. A step that finished cleanly carries none.
   */
  reason?: string;
  /** The right-hand mono figure: *1,004 · 2s*, *31 removed · 1s*, *stopped*. */
  detail?: string;
}

export interface ProgressRow {
  key: string;
  position: number;
  label: string;
  state: ProgressState;
  /** The server's own sentence, verbatim. Null when it said nothing. */
  reason: string | null;
  /**
   * OURS, as a locale key, for a step the RUN said nothing about.
   *
   * ⚠ **A SECOND FIELD RATHER THAN A DEFAULT FOR `reason`, AND FOR THE REASON
   * `SignupWizard` GIVES:** `reason` is the server's bytes and folding one of
   * our messages into it would quietly make that promise false, leaving the
   * next reader no way to tell which kind of sentence they were holding.
   */
  reasonKey: string | null;
  /** The mono figure at the right, or null — never an empty string. */
  detail: string | null;
}

/** What a step says when the run stopped and nothing recorded it. */
export const STEP_NEVER_REACHED_KEY = "runbooks.run.checking.neverReached";
/** What a step says while the run is still coming to it. */
export const STEP_WAITING_KEY = "runbooks.run.checking.waiting";

/**
 * THE ONE DECISION THE PROGRESS LIST MAKES, lifted out of the component so
 * every state is provable without a browser.
 *
 * Read it top to bottom, because the ORDER is the honesty:
 *
 *   1. **The catalogue is the list, always.** Every declared step is a row from
 *      the first frame, before anything has run — `RBR-01`, and the reason a
 *      count that grows is not a list.
 *   2. **What the run recorded wins.** A step with an outcome reports that
 *      outcome and that sentence, and nothing here overrides it.
 *   3. **A step with no record is never `done`.** A list that says Done because
 *      a row is missing is confidently wrong, which is worse than silent.
 *   4. **Exactly one step is `current`**, and only while the run is in flight:
 *      the first step with no record. No timer, no guess, no percentage
 *      invented from a clock.
 *   5. **Once the run has stopped, an unrecorded step says *Never reached***
 *      rather than sitting blank. A blank step is the defect this screen exists
 *      to prevent.
 *   6. **Before it starts, every step is `waiting`** — not "not started", which
 *      would claim we know something we have not been told.
 */
export function progressRows(
  catalogue: readonly StepCatalogueEntry[],
  outcomes: Readonly<Record<string, StepOutcome>>,
  phase: RunPhase,
): ProgressRow[] {
  const stopped = phase === "checkFailed" || phase === "review" || phase === "done";
  let currentTaken = false;
  return catalogue.map((entry, index) => {
    const base = { key: entry.key, position: index + 1, label: entry.label };
    const recorded = outcomes[entry.key];
    if (recorded !== undefined) {
      return {
        ...base,
        state: recorded.state,
        // A step that FINISHED carries its sentence as a FACT on the detail
        // line; only a step that did not finish puts one on the reason line,
        // which is the half the PO asked to see.
        reason: recorded.state === "done" ? null : (recorded.reason ?? null),
        reasonKey: null,
        detail: recorded.detail ?? null,
      };
    }
    if (phase === "scoping") {
      return { ...base, state: "waiting" as const, reason: null, reasonKey: STEP_WAITING_KEY, detail: null };
    }
    if (!stopped && !currentTaken) {
      currentTaken = true;
      return { ...base, state: "current" as const, reason: null, reasonKey: null, detail: null };
    }
    return {
      ...base,
      state: "waiting" as const,
      reason: null,
      reasonKey: stopped ? STEP_NEVER_REACHED_KEY : STEP_WAITING_KEY,
      detail: null,
    };
  });
}

/** How many steps of the catalogue actually finished — the bar's numerator. */
export function stepsFinished(rows: readonly ProgressRow[]): number {
  return rows.filter((row) => row.state === "done" || row.state === "skipped").length;
}

/**
 * The scope button's label key and its interpolation.
 *
 * ⚠ **THE SHEET'S `Check these 1,004 →` IS THE COLLECTIONS LADDER'S, AND IT
 * READS AS A BUG ON A ONE-SUBJECT CHECK.** Runbook 1 (*Can we bill?*) declares
 * `subject_type = "tenant"` and resolves to a single subject — *This utility* —
 * so the sheet's copy taken literally renders **Check these 1 →**. A count of
 * one carries no information, so the label says what is about to happen
 * instead. Above one, the sheet's own words, with the number the sheet's own
 * number.
 */
export function scopeStartKey(matches: number): string {
  return matches === 1 ? "runbooks.run.scope.startOne" : "runbooks.run.scope.start";
}
