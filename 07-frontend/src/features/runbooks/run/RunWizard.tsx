// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-001 (EP-RBS-01) · CR-075 wave C task C4.
//          Screens: RBS-005.1 Scope · RBS-005.2 Checking · RBS-005.6 Done ·
//          RBS-005.8 a check itself failed.
// Rules:   `RBR-01` (every step listed before the first one starts; a step that
//          did not run carries the reason) · `BR-RBS-002` (a Check is
//          CONSTRUCTED with no ports, so this path offers no action that
//          writes) · `BR-RBS-009` (scope pinned once) · `BR-RBS-011` (a failure
//          names its fix route) · `BR-RBS-042` (declared INPUTS, never arranged
//          steps) · B14 rules 1, 2, 3, 4, 5, 11, 16, 20, 21, 31, 32, 33, 36.
// Tests:   RunWizard.test.tsx · runWizardModel.test.ts ·
//          runWizardClasses.test.ts
//          Walkthrough: 10-scripts/render-checks/rbs-c-run-wizard.mjs
// Defects: DEF-RBS-4286 (no per-step outcome is recorded anywhere) ·
//          DEF-RBS-4289 (Save as draft has no draft to save) ·
//          DEF-CWP-3925 (a live screen behind a dead control).
// ───────────────────────────────────────────────────────
//
// WHAT THIS SCREEN IS, AND THE ONE SENTENCE THAT GOVERNS IT
// ══════════════════════════════════════════════════════════════════════════
// `RBS-005` is the run wizard. This file is its **Check path** — four steps,
// *Scope · Checking · Review · Done* (`04-flows.md` §4) — of which it draws
// three and the failure state of the second. **Review's body is `RBS-006`**,
// the result renderer (task `C2`), handed in as `review`; the reasoning is in
// `runWizardModel.ts` and it is why `C4` depends on `C2` and on nothing else.
//
// The sentence that governs the whole thing is `RBR-01`:
//
//     every step listed before the first one starts, with a reason on any that
//     did not run
//
// ⚠ **A BLANK STEP IS THE DEFECT.** Not a missing step — a step that is drawn
// and says nothing. Everything below is arranged so a row cannot come out
// empty: `progressRows` gives every row either the run's own sentence or one of
// ours, and this component renders whichever it was handed.
//
// ══════════════════════════════════════════════════════════════════════════
// THE SHEETS DRAW THE COLLECTIONS LADDER, WHICH IS AN ACTION. THIS IS A CHECK.
// ══════════════════════════════════════════════════════════════════════════
// Every `RBS-005` frame is drawn on runbook 8, the ladder — six rail steps, a
// `Stop`, *398 queued*, *Notices cannot be unsent*. **A Check sends nothing and
// CAN send nothing**: `BR-RBS-002` says the write capability is ABSENT, not
// refused. So four pieces of the sheets are not carried across literally, and
// every one is stamped in `08-screen-layouts.md` rather than changed silently:
//
//   1. `RBS-005.1`'s subtitle *"Nothing is sent until you approve."* promises a
//      send after an approval. On the Check path there is no approval and no
//      send, ever. It reads **"This check changes nothing."**
//   2. `RBS-005.2`'s *"Nothing has been sent."* becomes **"Nothing has
//      changed."** — same posture, true of a Check.
//   3. `RBS-005.2`'s right-hand bar label *"About 25 seconds left"* is a TIME
//      ESTIMATE this product cannot make: a Check runs synchronously, there is
//      no job record and nothing measures a rate. It carries the percentage
//      instead — a real figure from the same numerator, and the *"step and
//      percentage in words, never a spinner"* `08-screen-layouts.md` already
//      rules for a run in flight.
//   4. `RBS-005.1`'s two consequence lines ARE kept verbatim — *"This step
//      sends nothing."* and *"You will see everything first."* — because both
//      are already true of a Check.
//
// The rail is four cells rather than six, which is `04-flows.md`'s own ruling
// and not a reading of the frames.
//
// ══════════════════════════════════════════════════════════════════════════
// EVERY CONTROL IS A REAL DOOR OR A REQUIRED PROP — THERE ARE NO HOLDS HERE
// ══════════════════════════════════════════════════════════════════════════
// `DEF-CWP-3925`: the mirror of dead UI is a live screen behind a dead control,
// and the mechanism is *a rule with a clock in it* — a hold true the day it is
// written and rotten the day the screen it pointed at lands.
//
// **So this file writes no holds.** Its three navigations are real `<Link>`s to
// real addresses, which resolve today to the honest not-built-yet screen and to
// the real screen the day wave D and phase 1c land them, with no second act
// required of anybody. Its six actions are REQUIRED props, so `tsc` refuses a
// caller that forgets one; a wizard that defaulted them to a no-op would be
// exactly the dead button this paragraph is about.
// ⚠ **AMENDED 2026-10-13, WHEN THE WIZARD GOT ITS ADDRESS (`OQ-WRK-12792` →
// A).** Three of the six — `onSaveDraft`, `onStop`, `onTellSupport` — may now
// be answered `null`, which draws no button: the routed page
// (`RunWizardPage.tsx`) has no draft, no stop route and no support
// destination, and `null` is that decision stated rather than a no-op
// wearing a button. They are still required, so the decision is still the
// caller's to make out loud.
//
// ⚠ `onSaveDraft` IS REQUIRED AND THE PRODUCT HAS NOTHING TO SAVE
// (`DEF-RBS-4289`): `RUN_STATUSES` holds no `draft`, the status machine starts
// at `queued`, and none of the ten run endpoints saves a run without starting
// it. Making it required puts the decision on the route rather than shipping a
// button that quietly does nothing here.
//
// ⚠ `onTellSupport` IS REQUIRED FOR A DIFFERENT REASON, RECORDED IN THE
// DECISION LOG RATHER THAN LEFT AS A GAP. This product has no in-app support
// destination — `support_phone` and `support_email` in company settings are the
// TENANT'S own contact for THEIR customers, and `/signin-help` is a public
// pre-authentication landing. Inventing one here would be a comment claiming a
// guarantee (hard-won law 1).
//
// ══════════════════════════════════════════════════════════════════════════
// B14 RULE 21 IS PER FILE, AND THIS FILE IS COVERED BY A DIRECTORY ENTRY
// ══════════════════════════════════════════════════════════════════════════
// `07-frontend/src/styles/route-b-migrated.txt` carries `features/runbooks/` as
// a DIRECTORY entry (wave A task A2), and both readers expand a trailing `/` to
// the `.ts`/`.tsx` beneath it — so a file born here is covered on the day it is
// born and no line is added. Every class below was asked of the real Tailwind
// compiler before it was written (92 candidates, 0 misses), and
// `runWizardClasses.test.ts` re-asks them on every run: `routeBUtilities.test.ts`'s
// `kit_constant` grammar cannot see a type-annotated constant, and all three
// tone maps here are that shape (`DEF-SHL-4281`).
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  CHECK_STEPS,
  progressRows,
  railCells,
  scopeStartKey,
  stepsFinished,
} from "./runWizardModel";
import type {
  ProgressRow,
  ProgressState,
  RailState,
  RunPhase,
  StepCatalogueEntry,
  StepOutcome,
} from "./runWizardModel";

import { Button, ButtonAnchor, ButtonLink } from "@/components/Button";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { PageHeader } from "@/components/PageHeader";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import { useTenantPath } from "@/routing/tenantPath";

/* ── the view model ─────────────────────────────────────────────────────── */

/**
 * One row of `RBS-005.1`'s key–value table — a declared INPUT and its value.
 *
 * ⚠ **INPUTS, NOT FILTERS, AND NOT STEPS (`BR-RBS-042`, PO 2026-09-06).** *"you
 * cannot change the logic those are finate steps ; you can change the input to
 * logic"*. The sheet draws the ladder's three — *Accounts included · Services ·
 * As at* — and those are that runbook's own parameters, so this table is DATA
 * and never a list this file types out. There is no filter builder, for
 * anybody.
 *
 * ⚠ **`all` ARRIVES AS THE WORD AND IS RENDERED AS THE WORD.** It is a rule
 * resolved at run start, never a list expanded at configure time; a screen that
 * printed the expansion would make a service added later look like one dropped.
 */
export interface RunInputRow {
  id: string;
  label: string;
  value: string;
}

/** One record that came back needing a person — `RBS-005.6` region 4. */
export interface RunNeedsYouRow {
  id: string;
  /**
   * What the finding is ABOUT, in words — an account's name, a plan's name,
   * *Every account*. Never an id (B14 rule 31), and never a key.
   */
  subject: string;
  outcome: { label: string; tone: StatusTone };
  detail: string;
  /**
   * `BR-RBS-011`: a failure NAMES its fix route, and a failure with no route is
   * a defect in the runbook rather than a fact about the account. So it is not
   * optional here either, and `TC-RBS-14` scans for the absence.
   */
  fix: { label: string; to: string };
}

export interface RunWizardProps {
  /** The runbook's display name — *Can we bill?*. The kicker and the exit. */
  runbookName: string;
  /** Where `←` exits to: the runbook's own detail screen (`RBS-004`). */
  runbookTo: string;
  phase: RunPhase;

  /** `RBS-005.1` region 3: the declared inputs, in the runbook's own order. */
  inputs: readonly RunInputRow[];
  /**
   * How many subjects the pinned scope resolved to (`BR-RBS-009`).
   *
   * ⚠ **`null` IS *NOT COUNTED*, AND IT IS WHAT THE ROUTED PAGE PASSES TODAY
   * (`DEF-WRK-10123`).** `resolve(params)`'s live count is wave `L`'s and no
   * route serves it, so the *Matches* row is not drawn at all — a FACT row
   * with no fact is worse than none, the Scope tab's own ruling — and the
   * start button says what it does instead of quoting a number it does not
   * have. A guessed count here would be the one thing this screen may not do.
   */
  matches: number | null;
  /**
   * What the scope matched, in words the runbook chose — *1,004 accounts*,
   * *This utility*. A string rather than a number and a noun, because runbook 1
   * resolves to ONE tenant subject and *"1 This utility"* is not a sentence.
   * `null` exactly when `matches` is.
   */
  matchesValue: string | null;
  /**
   * `true` when this run will ACT — an Action runbook started for real. It
   * moves the scope step's subtitle, its consequence box and the start
   * button's tier, because *"This check changes nothing"* over a live run is
   * the one sentence on this screen that would be false. Absent is a Check (or
   * a dry run), which is every frame the sheets draw.
   */
  live?: boolean;
  /**
   * The run's own choices, drawn under the inputs table and ABOVE the
   * consequence box (B14 rule 11) — *How to run* for an Action, and the
   * runbook's one-off text inputs. The pop-up this wizard replaced asked
   * exactly these (`OQ-WRK-12792`, PO 2026-10-13), and a wizard that dropped
   * them would take *Run for real* away from the one runbook that has it.
   */
  scopeControls?: ReactNode;

  /** The steps the DEFINITION declares, drawn before the first one starts. */
  steps: readonly StepCatalogueEntry[];
  /**
   * What the RUN recorded, keyed by step. **Nothing serves this today**
   * (`DEF-RBS-4286`) — an empty map is the honest state, and every row then
   * says *waiting* or *Never reached* rather than going blank.
   */
  outcomes: Readonly<Record<string, StepOutcome>>;

  /** `RBS-005.6` region 3, already toned by the caller. */
  doneTiles: readonly KpiTile[];
  /** `RBS-005.6`'s subtitle — the run's own headline sentence. */
  doneHeadline: string;
  /** `RBS-005.6` region 4. Empty is a legitimate — and good — outcome. */
  needsYou: readonly RunNeedsYouRow[];
  /**
   * The first column's heading — *Account*, *Affects*, *Meter*.
   *
   * ⚠ **THE SHEET SAYS `Account` AND THAT IS THE LADDER'S WORD, NOT EVERY
   * RUNBOOK'S — FOUND BY LOOKING AT THE RENDERED SCREEN, WHICH IS THE ONLY
   * INSTRUMENT THAT COULD.** `RBS-005.6` is drawn on runbook 8, where every row
   * IS an account. Runbook 1 declares `subject_type = tenant` and its findings
   * are about a tax region, a rate ladder and an account chain, so a column
   * headed *Account* over the row *No rate above 20,000 gallons* is simply
   * false. The engine already has the general word — `configuration_check.py`'s
   * records block declares its third column **Affects** — so the heading is the
   * caller's, from the runbook, exactly as `BR-RBS-042` has every other thing
   * on this screen come from the runbook's own declaration.
   *
   * Required rather than defaulted to *Account*: a default is how the ladder's
   * word would quietly appear over a Check's findings, which is the thing this
   * prop exists to stop.
   */
  needsYouSubjectLabel: string;
  /** The result files the run declared. Drawn `↓ {label}`, B14 rule 4. */
  downloads: readonly { id: string; label: string; href: string }[];
  // ⚠ **NO `workListTo` PROP — REMOVED 2026-10-02 (`DEF-RBS-9136`).** *Open
  // work list →* goes to ONE screen, `RBS-007` at `/{tenant}/runbooks/work`,
  // whatever runbook ran, so the address is this screen's to build and
  // `DoneStep` builds it the way it already built *Back to runbooks*. It was a
  // required prop that no screen passed (this wizard was not mounted on a route
  // yet), and its only supplier — the test — handed it `/runbooks/work-list`,
  // which the real router opens as `RBS-004`: the setup screen for a runbook
  // keyed `work-list`.

  /** Step 3's body — `RBS-006`, task `C2`. Required: see the file header. */
  review: ReactNode;

  onStart: () => void;
  /**
   * ⚠ **`null` DRAWS NO BUTTON, AND THAT IS THE ROUTE'S DECISION, MADE ON
   * PURPOSE.** These three are not optional — `tsc` still refuses a caller
   * that forgets one — but each may be answered `null`: *"this product has no
   * such action"*. `onSaveDraft` has no draft to save (`DEF-RBS-4289`),
   * `onStop` has no route that stops a run (the home's hold-expiry test pins
   * that address), and `onTellSupport` has no in-app support destination. A
   * button wired to a no-op is `DEF-CWP-3925`'s dead control; a button that is
   * not drawn is a fact.
   */
  onSaveDraft: (() => void) | null;
  onCancel: () => void;
  onStop: (() => void) | null;
  onRetry: () => void;
  onTellSupport: (() => void) | null;
  onStepSelect: (step: (typeof CHECK_STEPS)[number]) => void;
}

/* ── tone maps ──────────────────────────────────────────────────────────── */

/**
 * The rail's numbered circle. `RBS-005.1`'s SIZE column: *"numbered circles
 * 19px · done = ink fill, current = accent fill on accent-100"*.
 */
const RAIL_BADGE: Record<RailState, string> = {
  done: "bg-text text-bg",
  current: "bg-accent text-bg",
  todo: "bg-surface text-text",
};

/**
 * The progress marker. `RBS-005.2`'s own words: *"marker 18px: done
 * success-500, current accent, skipped n300, failed danger-500, waiting
 * n500"* — five states, five tokens, transcribed rather than chosen.
 */
const MARK_TONE: Record<ProgressState, string> = {
  done: "bg-success-500 text-bg",
  current: "bg-accent text-bg",
  skipped: "bg-neutral-300 text-text",
  failed: "bg-danger-500 text-bg",
  waiting: "bg-neutral-500 text-bg",
};

/** A step still to come is greyed; one that ran is not. */
const ROW_TONE: Record<ProgressState, string> = {
  done: "text-text",
  current: "text-text",
  skipped: "text-neutral-700",
  failed: "text-text",
  waiting: "text-neutral-600",
};

const TITLE_KEY: Record<RunPhase, string> = {
  scoping: "runbooks.run.scope.title",
  checking: "runbooks.run.checking.title",
  checkFailed: "runbooks.run.checking.title",
  review: "runbooks.run.review.title",
  done: "runbooks.run.done.title",
};

const SUBTITLE_KEY: Record<RunPhase, string> = {
  scoping: "runbooks.run.scope.subtitle",
  checking: "runbooks.run.checking.subtitle",
  checkFailed: "runbooks.run.checking.failedSubtitle",
  review: "runbooks.run.review.subtitle",
  // `done` never reads this: its subtitle is the run's own headline.
  done: "runbooks.run.done.title",
};

/** The two subtitles that would be false over a run that ACTS. */
const LIVE_SUBTITLE_KEY: Partial<Record<RunPhase, string>> = {
  scoping: "runbooks.run.scope.subtitleLive",
  checking: "runbooks.run.checking.subtitleLive",
};

/* ── the screen ─────────────────────────────────────────────────────────── */

export function RunWizard(props: RunWizardProps) {
  const { t } = useTranslation();
  const path = useTenantPath();
  const rows = progressRows(props.steps, props.outcomes, props.phase);

  // B14 rule 1: a `←` names where the page EXITS to, and inside a stepper
  // `← Back` means only the previous step. This is the EXIT, so it is a real
  // link to the runbook's own screen — the kit's `backTo`, not a kicker with an
  // arrow drawn into the string, because an arrow a clerk cannot press is
  // `DEF-CWP-3925`'s dead control wearing the right glyph.
  //
  // ⚠ `RBS-005.6` DROPS THE `←` AND KEEPS THE WORDS, which `08-screen-layouts.md`
  // rules is rule 1 read correctly rather than an inconsistency: once the run is
  // over there is no exit backwards, and the way on is the button row.
  const exiting = props.phase !== "done";
  const liveKey = props.live === true ? LIVE_SUBTITLE_KEY[props.phase] : undefined;
  const subtitle =
    props.phase === "done"
      ? props.doneHeadline
      : t(liveKey ?? SUBTITLE_KEY[props.phase]);

  return (
    <div data-screen="RBS-005" data-run-phase={props.phase} className="flex min-w-0 flex-col">
      <PageHeader
        kicker={exiting ? undefined : props.runbookName}
        backTo={exiting ? { to: props.runbookTo, label: props.runbookName } : undefined}
        title={t(TITLE_KEY[props.phase])}
        rollup={<span className="text-base text-neutral-700">{subtitle}</span>}
        secondaryActions={
          <HeadActions phase={props.phase} downloads={props.downloads} onStop={props.onStop} />
        }
      />

      <Rail phase={props.phase} onSelect={props.onStepSelect} />

      {props.phase === "scoping" && <ScopeStep {...props} />}
      {(props.phase === "checking" || props.phase === "checkFailed") && (
        <CheckingStep
          rows={rows}
          finished={stepsFinished(rows)}
          total={props.steps.length}
          failed={props.phase === "checkFailed"}
          onRetry={props.onRetry}
          onTellSupport={props.onTellSupport}
        />
      )}
      {props.phase === "review" && props.review}
      {props.phase === "done" && (
        <DoneStep {...props} runbooksTo={path("/runbooks")} workListTo={path("/runbooks/work")} />
      )}
    </div>
  );
}

/**
 * The page head's right-hand actions.
 *
 * ⚠ **`Stop` IS THE DANGER TIER AND IT IS NOT A COMMIT** — `08-screen-layouts.md`
 * says why the ladder draws it that way: *"the in-flight banner's Stop is the
 * danger tier so nobody is afraid to press Run"*. B14 rule 5's two sizes: `sm`,
 * which is the sheet's 12px.
 */
function HeadActions(props: {
  phase: RunPhase;
  downloads: RunWizardProps["downloads"];
  onStop: (() => void) | null;
}) {
  const { t } = useTranslation();
  if (props.phase === "checking") {
    if (props.onStop === null) return null;
    return (
      <Button variant="danger" size="sm" data-run-action="stop" onClick={props.onStop}>
        {t("runbooks.run.checking.stop")}
      </Button>
    );
  }
  if (props.phase !== "done") return null;
  return (
    <>
      {props.downloads.map((file) => (
        // `ButtonAnchor` and not `ButtonLink`: a result file LEAVES the SPA, the
        // same reasoning the kit records for the bill PDF. B14 rule 4: `↓` is
        // the download glyph.
        <ButtonAnchor
          key={file.id}
          variant="secondary"
          size="sm"
          href={file.href}
          data-run-download={file.id}
        >
          ↓ {file.label}
        </ButtonAnchor>
      ))}
    </>
  );
}

/**
 * B14 rule 3 — the numbered rail, clickable when complete.
 *
 * ⚠ **IT IS DRAWN HERE RATHER THAN THROUGH `WizardFrame` (FE-06), AND THAT IS A
 * STATED DIVERGENCE FROM THE SHEET'S COMPONENT COLUMN.** `WizardFrame` is a
 * COMMIT frame: it owns a Back/Continue footer, a single-flight transactional
 * `onCommit` and the A18 §3 working state, and its rail is not separable from
 * them. **A Check run has no commit at all** — `BR-RBS-002` gives it no writer
 * — so mounting that frame would draw a Continue and a final ✓ over a flow that
 * has neither, which is `DEF-712`'s shape running backwards. What IS carried
 * across is the frame's own geometry, value for value from its `WIZ` constant:
 * the `border-y-2` rail, `flex-1` cells with a `border-r` divider,
 * `last:border-r-0`, the disabled-but-full-opacity upcoming step (`BR-SHL-018`:
 * an upcoming step is not BROKEN, it is just not navigation), and `max-lg:`
 * scrolling rather than wrapping (A12).
 */
function Rail(props: { phase: RunPhase; onSelect: (step: (typeof CHECK_STEPS)[number]) => void }) {
  const { t } = useTranslation();
  return (
    <nav
      data-wizard="rail"
      data-run-rail=""
      aria-label={t("runbooks.run.rail.label")}
      className="mb-6 flex border-y-2 border-divider max-lg:flex-nowrap max-lg:overflow-x-auto"
    >
      {railCells(props.phase).map((cell) => (
        <button
          key={cell.id}
          type="button"
          data-run-step={cell.id}
          data-state={cell.state}
          disabled={!cell.clickable}
          aria-current={cell.state === "current" ? "step" : undefined}
          onClick={() => props.onSelect(cell.id)}
          className={
            "flex flex-1 items-center gap-3 border-0 border-r border-divider bg-transparent " +
            "px-5 py-4 text-left font-heading text-base font-semibold last:border-r-0 " +
            "disabled:cursor-default disabled:opacity-100 max-lg:flex-none max-lg:whitespace-nowrap " +
            (cell.state === "current" ? "text-accent" : "text-text")
          }
        >
          <span
            className={
              "flex h-[26px] w-[26px] shrink-0 items-center justify-center text-sm " +
              RAIL_BADGE[cell.state]
            }
          >
            {cell.state === "done" ? "✓" : cell.position}
          </span>
          {t(`runbooks.run.rail.${cell.id}`)}
        </button>
      ))}
    </nav>
  );
}

/** `RBS-005.1` — regions 3, 4 and 5. Region 1 is the page head, 2 is the rail. */
function ScopeStep(props: RunWizardProps) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-4">
      {/* Region 3 · the declared inputs, then what the scope matched. A wizard
          summary table, which B14 rule 16 exempts from the pagination footer BY
          NAME — so no pager here is the rule, not an omission. */}
      <div data-run-scope="inputs">
        <PlainTable>
          <tbody>
            {props.inputs.map((row) => (
              <tr key={row.id} data-run-input={row.id}>
                <th scope="row" className="font-semibold">
                  {row.label}
                </th>
                <td className="text-right">{row.value}</td>
              </tr>
            ))}
            {props.matches !== null && props.matchesValue !== null && (
              <tr data-run-input="matches">
                <th scope="row" className="font-semibold">
                  {t("runbooks.run.scope.matches")}
                </th>
                <td className="text-right font-semibold tabular-nums">{props.matchesValue}</td>
              </tr>
            )}
          </tbody>
        </PlainTable>
      </div>

      {/* Region 4 · B14 rule 11 — the consequence box sits directly ABOVE the
          commit and never after it. Each line is inside rule 33's six words. */}
      {props.scopeControls !== undefined && props.scopeControls !== null && (
        <div data-run-scope="controls" className="flex flex-col gap-3">
          {props.scopeControls}
        </div>
      )}

      <ConsequenceBox
        heading={t("runbooks.run.scope.consequence.heading")}
        bullets={
          props.live === true
            ? [t("runbooks.run.scope.consequence.live"), t("runbooks.run.scope.consequence.liveFinal")]
            : [t("runbooks.run.scope.consequence.sends"), t("runbooks.run.scope.consequence.first")]
        }
      />

      {/* Region 5 · at most one primary; Cancel is ghost. Nothing here is the
          danger tier, because nothing here commits: `BR-RBS-002`. */}
      <div className="flex flex-wrap items-center gap-2">
        {/* B14 rule 6: a run that ACTS is a destructive commit, so it takes the
            danger tier; a Check stays primary because nothing here commits. */}
        <Button
          variant={props.live === true ? "danger" : "primary"}
          data-run-action="start"
          onClick={props.onStart}
        >
          {/* ⚠ `n`, NEVER `count`. `count` is i18next's own plural selector, so
              passing it makes the lookup go to `…start_one` / `…start_other`
              first — keys no catalogue holds. The fallback happens to work
              today and would break the moment a translator added a plural
              form, which is a silent copy change nothing here could see. */}
          {props.matches === null
            ? t(props.live === true ? "runbooks.run.scope.startLive" : "runbooks.run.scope.startOne")
            : t(scopeStartKey(props.matches), { n: props.matches.toLocaleString() })}
        </Button>
        {props.onSaveDraft !== null && (
          <Button variant="secondary" data-run-action="draft" onClick={props.onSaveDraft}>
            {t("runbooks.run.scope.draft")}
          </Button>
        )}
        <Button variant="ghost" data-run-action="cancel" onClick={props.onCancel}>
          {t("runbooks.run.scope.cancel")}
        </Button>
      </div>
    </div>
  );
}

/**
 * `RBS-005.2` and `RBS-005.8` — one component, because they are one screen in
 * two states, and splitting them is how a state stops being tested.
 */
function CheckingStep(props: {
  rows: readonly ProgressRow[];
  finished: number;
  total: number;
  failed: boolean;
  onRetry: () => void;
  onTellSupport: (() => void) | null;
}) {
  const { t } = useTranslation();
  // The bar is the honest fraction of STEPS, not a clock — `SignupWizard`'s own
  // rule for the same pattern: no timer, no guess, no invented percentage.
  const pct = props.total === 0 ? 0 : Math.round((props.finished / props.total) * 100);
  return (
    <div className="flex flex-col gap-2">
      {/* Regions 3 and 4 · the bar and its labels. Hidden once the run has
          stopped: a frozen bar under a failed run reads as a run still going. */}
      {!props.failed && (
        <>
          <div
            data-run-bar=""
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={t("runbooks.run.checking.progressLabel")}
            className="h-[5px] w-full bg-neutral-300"
          >
            <div data-run-bar-fill="" className="h-[5px] bg-accent" style={{ width: `${pct}%` }} />
          </div>
          <div className="flex items-baseline justify-between text-sm text-neutral-600">
            <span data-run-bar-label="left">
              {t("runbooks.run.checking.of", { done: props.finished, total: props.total })}
            </span>
            <span data-run-bar-label="right">
              {t("runbooks.run.checking.percent", { pct })}
            </span>
          </div>
        </>
      )}

      {/* Region 5 · THE PROGRESS LIST. Every declared step is here from the
          first frame (`RBR-01`), and not one row can come out empty. */}
      <ol data-run-progress="" className="m-0 grid list-none gap-0 p-0">
        {props.rows.map((row) => (
          <li
            key={row.key}
            data-run-progress-step={row.key}
            data-state={row.state}
            className={
              "flex items-start gap-3 border-b border-divider px-2 py-2 text-table " +
              ROW_TONE[row.state]
            }
          >
            <span
              data-run-progress-mark=""
              className={
                "mt-1 flex h-[18px] w-[18px] shrink-0 items-center justify-center " +
                "text-xs leading-none " +
                MARK_TONE[row.state]
              }
            >
              {row.state === "done" ? "✓" : row.state === "failed" ? "!" : row.position}
            </span>
            <span className="flex min-w-0 flex-1 flex-col gap-1">
              <span>{row.label}</span>
              {/* THE REASON LINE. The run's own bytes when it has any, ours as a
                  catalogue key when it has none — and one of the two is always
                  present on a step that did not finish, which is the half of
                  `RBR-01` that `DEF-RBS-4286` says nothing serves yet. */}
              {(row.reason !== null || row.reasonKey !== null) && (
                <span data-run-progress-why="" className="text-sm text-neutral-600">
                  {row.reason ?? t(row.reasonKey ?? "")}
                </span>
              )}
            </span>
            <span
              data-run-progress-detail=""
              className="shrink-0 font-mono text-xs text-neutral-600"
            >
              {row.detail ?? "—"}
            </span>
          </li>
        ))}
      </ol>

      {/* `RBS-005.8` region 3 · two buttons, at most one primary, both small. */}
      {props.failed && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Button variant="primary" size="sm" data-run-action="retry" onClick={props.onRetry}>
            {t("runbooks.run.checking.retry")}
          </Button>
          {props.onTellSupport !== null && (
            <Button
              variant="secondary"
              size="sm"
              data-run-action="tell-support"
              onClick={props.onTellSupport}
            >
              {t("runbooks.run.checking.tellSupport")}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

/** `RBS-005.6` — regions 3, 4 and 5. */
function DoneStep(props: RunWizardProps & { runbooksTo: string; workListTo: string }) {
  const { t } = useTranslation();
  // ⚠ `[&>.kpi-grid]:mb-0` — THE ONE PLACE IN THE PRODUCT THAT OPTS OUT OF THE
  // STRIP'S OWN BOTTOM MARGIN, and it opts out because this container is FLEX.
  // `KPIStrip.css` gives `.kpi-grid` `margin-bottom: var(--space-4)` so the
  // strip stops welding itself to whatever follows it (DEF-3481's shape, one
  // element down). In a BLOCK container that margin COLLAPSES against the next
  // element's own; in a flex container margins do not collapse, they stack on
  // the `gap` — so here it would read 16px of gap plus 16px of margin plus the
  // next block's own `py-4`. The strip keeps this container's rhythm and the
  // rest of the product gets the gap.
  return (
    <div className="flex flex-col gap-4 [&>.kpi-grid]:mb-0">
      {/* Region 3 · the kit's strip. The tone colours the VALUE only, which the
          caller does by handing a toned node — the strip has no tone prop, and
          adding one is a change to a shared component this lane does not own. */}
      <KPIStrip kpis={props.doneTiles} />

      {/* Region 4 · what needs a person, each row carrying its fix route
          (`BR-RBS-011`). A wizard summary table, so rule 16 exempts it from the
          pager — and it is the run's own short list rather than a page of one. */}
      {props.needsYou.length === 0 ? (
        <div data-run-needs-you="empty" className="flex flex-col gap-1 py-4">
          <span className="font-heading text-base font-semibold">
            {t("runbooks.run.done.allClear")}
          </span>
          <span className="text-sm text-neutral-600">{t("runbooks.run.done.allClearWhy")}</span>
        </div>
      ) : (
        <div data-run-needs-you="rows">
          <PlainTable>
            <thead>
              <tr>
                <th scope="col">{props.needsYouSubjectLabel}</th>
                <th scope="col">{t("runbooks.run.done.col.outcome")}</th>
                <th scope="col">{t("runbooks.run.done.col.detail")}</th>
                <th scope="col">{t("runbooks.run.done.col.fix")}</th>
              </tr>
            </thead>
            <tbody>
              {props.needsYou.map((row) => (
                <tr key={row.id} data-run-needs-you-row={row.id}>
                  <th scope="row" className="font-semibold">
                    {row.subject}
                  </th>
                  <td>
                    <StatusPill tone={row.outcome.tone}>{row.outcome.label}</StatusPill>
                  </td>
                  <td>{row.detail}</td>
                  <td>
                    {/* A REAL door, and the reason `BR-RBS-011` exists: a
                        failure with no route to a fix is a defect in the
                        runbook, not a fact about the account. */}
                    <Link
                      data-run-fix={row.id}
                      to={row.fix.to}
                      className="text-accent-700 no-underline hover:underline"
                    >
                      {row.fix.label} →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      )}

      {/* Region 5 · both are NAVIGATIONS, so both are links: middle-click and
          "open in a new tab" keep working, and neither can rot into a dead
          control the day its screen lands (`DEF-CWP-3925`). */}
      <div className="flex flex-wrap items-center gap-2">
        <ButtonLink variant="primary" data-run-action="work-list" to={props.workListTo}>
          {t("runbooks.run.done.openWorkList")}
        </ButtonLink>
        <ButtonLink variant="secondary" data-run-action="runbooks" to={props.runbooksTo}>
          {t("runbooks.run.done.backToRunbooks")}
        </ButtonLink>
      </div>
    </div>
  );
}
