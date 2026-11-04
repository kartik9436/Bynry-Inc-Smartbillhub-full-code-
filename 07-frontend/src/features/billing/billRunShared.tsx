// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-001 (S31 step 1 — cycle, period, scope, the idempotent run) ·
//           US-BIL-002 (S31.2 step 2 — "Check what we found") · US-BIL-003
//           (S31.3 step 3 — the case tables, bulk, the missing-service choice) ·
//           US-BIL-004 (step 4 — the background batch, the BREAKS, the totals) ·
//           US-BIL-005 (steps 5/6 — the live summary, the five-fact gate, release)
//           Screens: S31 · S31.2 · S31.3
// Rules:    BR-BIL-050 (five phases over FOUR wizard steps over seven stages —
//           three axes, none renumbering another) · BR-BIL-051 (calculate and
//           release are BACKGROUND batches) · BR-BIL-053 (breaks BEFORE the
//           totals, naming the failing stage, retry-now or mark-for-later) ·
//           BR-BIL-054 (the over-guardrail draft is a post-calculation
//           exception, never a pre-block) · BR-BIL-055 (a partial run issues the
//           clean and holds the rest) · BR-BIL-056 (the summary's four figures;
//           the SCREEN recalculates live — PO 2026-08-11 option B) · BR-BIL-057
//           (the category axes are PROPOSED, not ruled) · BR-BIL-058 (the gate
//           is FIVE separately-recorded facts) · BR-BIL-059 (each confirmation
//           against its coverage; a missing email never blocks) · BR-BIL-060
//           (bulk everywhere — N rows, one bulk_action_id) · BR-BIL-061
//           (base-only billing is a recorded staff opt-in, no default) ·
//           BR-BIL-062 (a first bill with no prior read is not a missing read) ·
//           BR-BIL-003 (a first-time waiver is manual — bulk may not launder it) ·
//           BR-BIL-005 (one run per tenant+cycle+period) · BR-BIL-024 (due date =
//           bill date + the cycle's due-days) · BR-BIL-025 (templates come from
//           the consumer category — there is no per-run template pick) ·
//           BR-BIL-037/040 (the seven stages; a failure NAMES its stage) ·
//           BR-SHL-010 (an undeclared capability is not rendered) · BR-SHL-011
//           (URL grammar) · BR-SHL-023 (one money path) · BR-SHL-025 (a control
//           that cannot be used renders disabled WITH its reason)
// ───────────────────────────────────────────────────────
// The pure half of S31. Everything here is provable without a browser and
// without a network, which is the point: the run's LAWS — which phase a step is
// in, whether a bulk action is allowed, whether the gate may release, what a
// due date is — must be assertable by a test rather than described in a comment
// (hard-won law 1).
//
// FIVE REFUSALS THIS MODULE MAKES BY CONSTRUCTION:
//
//   1. **It never decides whether a break may be retried.** `NOT_RETRYABLE_HERE`
//      lives in `06-backend/apps/billing/runs.py` and is the authority; the
//      server sends `retryable` per row. A client copy of that set would drift
//      the day a reason moved, and the failure mode is a button that always
//      fails — which BR-BIL-053's own reasoning calls worse than no button.
//   2. **It never sums money or counts.** No helper here adds an amount, and
//      the bulk confirm shows the SERVER's Σ for the case. A page of rows is not
//      the selection, and a client that totals money is a client that decides
//      what the money is (CLAUDE.md rule 2).
//   3. **It never lists the dispositions a case offers.** Those come with the
//      row, because BR-BIL-015's three choices and BR-BIL-003's manual-only
//      waiver are server-enforced rules. What this module DOES own is the one
//      asymmetry the PO made deliberate: bulk APPLY is allowed, bulk WAIVE is
//      refused, and it is refused HERE as well so the button never appears.
//   4. **It never derives a phase from a step number.** The map is data
//      (`PHASE_OF_STEP`) and a test asserts seven stages ≠ four steps ≠ five
//      phases, because the epic itself once wrote "the five S31 wizard steps"
//      when the wizard had six (BR-BIL-050, US-BIL-029 TC-11). ⚠ **THE WIZARD
//      HAS FOUR SINCE 2026-09-14** — PO, *"we have 4 step only now in bill
//      run"* (`DEF-BIL-5247`) — and the map being data is why that merge
//      changed no phase: see `BILL_RUN_STEPS` below.
//   5. **It never reads a clock.** The only date arithmetic here is
//      `dueDateFrom`, which adds the cycle's due-days to a date the user typed.
//      "Today" is the tenant's (BR-TEN-043) and no default here reaches for it.
import type { ReactNode } from "react";

import { refusalSentence } from "@/api/refusalSentence";
import { isApiError } from "@/api/client";
import { DECISION_CASES } from "@/api/endpoints";
import type {
  BillRunBreak,
  BillRunExceptionRow,
  BillRunHistoryRow,
  BillRunPricingShadow,
  BillRunReleaseBody,
  CycleRow,
  PricingShadowAccount,
} from "@/api/endpoints";
import { PlainTable } from "@/components/Surfaces";
import { StatusPill } from "@/components/StatusPill";
import { Dash } from "@/features/metering/meteringShared";
import { Kicker } from "@/components/TextBits";
import type { Translator } from "@/features/tenancy/settingsShared";


// ── Routes and URL state (BR-SHL-011 · A9) ─────────────────────────────────
// TENANT-RELATIVE like every route constant since path tenancy (PO 2026-08-10):
// the screen that navigates puts it through `tenantPath()`.

/**
 * S31. It is the `run` TAB of the prototype's Billing page (line 2888), so the
 * path is the tab's own — `billing/run` is all-static and React Router ranks it
 * above `billing/:tab`, which means the existing tab strip lands here with
 * nothing in `BillsListPage` edited.
 */
export const BILL_RUN_ROUTE = "/billing/run";

/** The wizard step, as URL state, so a half-done run is linkable (A9). */
export const STEP_PARAM = "step";
/**
 * The run this wizard is showing. BR-BIL-050 makes a run RESUMABLE from S30 at
 * whatever phase its status names, and a wizard whose run lives only in React
 * state is a wizard the browser owns — which is the thing that ruling forbids
 * (US-BIL-001 TC-7).
 */
export const RUN_PARAM = "run";
/**
 * ONE RUN'S ADDRESS, for a screen that holds a run id and is not the wizard —
 * `/billing/run?run=<id>`, tenant-relative like every route constant here.
 *
 * ⚠ **WRITTEN FOR `DEF-2716`, AND THE REASON IT DID NOT EXIST IS THE DEFECT.**
 * The bill detail's *Where this bill came from* panel printed `bill_run_id` as
 * a bare uuid under a comment that was true when it was written: *"EP-BIL-01's
 * run screens do not exist, so the id is SHOWN rather than linked — a link onto
 * a placeholder is 'built is not wired' wearing a different hat"*. `CR-051`
 * built those screens. Nothing re-read the sentence, which is hard-won law 1,
 * and `B14` rule 31 then made the fallback a rule breach as well as a stale
 * comment: *"no Databse ID on screen - that is a rule"* (PO, 2026-08-30).
 *
 * Composed here rather than at the call site so the route and its parameter
 * have ONE definition — they are both two lines up.
 */
export function billRunPath(runId: string): string {
  return `${BILL_RUN_ROUTE}?${RUN_PARAM}=${encodeURIComponent(runId)}`;
}
/**
 * Which findings tab and which case table are open. URL state for the same
 * reason the step is: a clerk who finds three accounts with no plan sends
 * someone the link to that tab, not a description of where to click
 * (BR-SHL-011's shareable-list grammar, applied inside a wizard).
 */
export const FOUND_PARAM = "found";
/**
 * ⛔ **`CASE_PARAM` ("case") IS DELETED — CR-051 task 17, 2026-08-31.** Step 3
 * no longer has fifteen case tabs to name: it has THREE families and a case
 * FILTER inside the open one, so the URL carries `?family=` and `?kind=`
 * (`billRunStep23.FAMILY_PARAM` / `CASE_FILTER_PARAM`). A constant left behind
 * would be a param name nothing reads and the next lane would wire a link to
 * it — dead UI with a URL, which is hard-won law 2 with an address.
 */
/**
 * CR-051 task 12 — the BACKGROUND job the clerk left running.
 *
 * ⚠ **THIS IS A POINTER, NOT A SECOND COPY OF SERVER STATE.** The 202 answers a
 * job id and nothing else on the run row records it, so without this the
 * progress readout would die with the tab and the PO's *"the clerk may close
 * the tab"* would be true of the WORK and false of the SCREEN. It is in the URL
 * for the same reason `RUN_PARAM` is (BR-BIL-050): a poll that lives only in
 * React state is a poll the browser owns.
 *
 * Losing it costs nothing that matters — the pass finishes in the worker and
 * the breaks and drafts are there on re-open. What is lost is the running
 * count, and that is what this param is for.
 */
export const JOB_PARAM = "job";
/**
 * CR-051 task 7 — `all` includes the breaks a later pass resolved.
 *
 * OUTSTANDING is the default because that is the WORK LIST (BR-BIL-053's own
 * word). The history is the supervisor's question — *"what did this run
 * struggle with?"* — and it is URL state so it is a link they can send, exactly
 * like every other filter on this wizard (BR-SHL-011).
 */
export const BREAKS_PARAM = "breaks";

// ── The three axes (BR-BIL-050) ────────────────────────────────────────────
// Seven stages · FOUR wizard steps · five phases. None renumbers another, and a
// test asserts all three counts because prose already got it wrong once.

/**
 * The SEVEN pipeline stages (BR-BIL-037), in their one fixed order. Mirrored
 * from `06-backend/apps/billing/runs.py STAGE_BY_REASON`, whose values are the
 * names a break carries — so a break row prints the same word the stage does
 * rather than a paraphrase that drifts.
 */
export const PIPELINE_STAGES = [
  "resolve-subscription",
  "measure-consumption",
  "price-usage",
  "apply-charges",
  "compute-tax",
  "assemble-document",
  "post-to-ledger",
] as const;
export type PipelineStage = (typeof PIPELINE_STAGES)[number];

/** The FIVE phases the PO described on 2026-08-11, in order (BR-BIL-050). */
export const RUN_PHASES = ["prepare", "calculate", "breaks", "summary", "release"] as const;
export type RunPhase = (typeof RUN_PHASES)[number];

export interface BillRunStep {
  id: string;
  /** The blueprint's own rail word, through the catalog. */
  labelKey: string;
  /** Which of the five phases this step belongs to (epic §Phase map). */
  phase: RunPhase;
}

/**
 * The FOUR wizard steps — the blueprint's rail, in its order and its words:
 * **Scope · Check · Sign off · Send**.
 *
 * ⚠ **THIS ARRAY HELD SIX UNTIL 2026-09-14 AND THE DOCSTRING SAID WHY: *"the
 * prototype's stepper, in its order and its words"*.** That was correct until
 * `B14` rule 41 (2026-09-13) made the BLUEPRINT the specification rather than
 * the r10 prototype. **PO ruling 2026-09-14, verbatim: *"we have 4 step only
 * now in bill run"*** (`DEF-BIL-5247`), said after comparing our screenshot
 * with `04 Billing, As Built.pdf`. The document states the mapping itself, so
 * it is quoted here rather than re-derived:
 *
 * | Blueprint step | The six it replaces |
 * |---|---|
 * | 1 **Scope** | `cycle` — *"Pick the cycle"*, KEEP, WIDENED (p28) |
 * | 2 **Check** | `found` + `customers` + `totals` — MERGE INTO ONE (p28) |
 * | 3 **Sign off** | `confirm` — KEEP, TRIMMED (p29) |
 * | 4 **Send** | `send` — KEEP, ONE DOOR ADDED (p29) |
 *
 * And the rail's words are the document's, p35: *"The wizard rail now reads
 * Scope · Check · Sign off · Send … Review was the wrong word for the step:
 * reviewing is what a clerk does ON it, and what the product does TO GET THERE
 * is a check."*
 *
 * **THE PHASE COLUMN DID NOT MOVE AND THAT IS THE CHECK ON THIS EDIT.** The six
 * steps carried `prepare · prepare · prepare · breaks · summary · release` —
 * four distinct phases, because `calculate` was never a step's phase (it is the
 * transition INTO the merged step; the clerk is not held at a screen for it,
 * BR-BIL-051). The four carry `prepare · breaks · summary · release`: the same
 * four words, in the same order, one step each. Merging three `prepare`/`breaks`
 * steps into one could not have been done without changing a phase if the map
 * had ever been arithmetic over a step number, which is why it is data
 * (BR-BIL-050, refusal 4 at the head of this file).
 */
export const BILL_RUN_STEPS: readonly BillRunStep[] = [
  { id: "scope", labelKey: "billing.run.step.scope", phase: "prepare" },
  { id: "check", labelKey: "billing.run.step.check", phase: "breaks" },
  { id: "signoff", labelKey: "billing.run.step.signoff", phase: "summary" },
  { id: "send", labelKey: "billing.run.step.send", phase: "release" },
];

export const BILL_RUN_STEP_COUNT = BILL_RUN_STEPS.length;

/**
 * The rail position of a step, 1-based — **derived from the array, never
 * typed.**
 *
 * ⚠ **IT EXISTS BECAUSE THREE SCREENS PRINTED THEIR OWN STEP NUMBER AS A
 * TRANSLATED STRING.** `billing.run.step1.kicker` was the literal `"Step 1"`,
 * `step5.kicker` was `"Step 5"` and `step6.kicker` was `"Step 6 · almost
 * done"` — in eleven catalogues each. A rail that moved from six words to four
 * therefore left two screens announcing a step number that no longer existed,
 * in every language at once, with `tsc`, every suite and every gate green:
 * there is nothing in a catalogue string for a check to compare against the
 * rail. The number now comes from the same array the rail is drawn from, so
 * the two cannot disagree.
 *
 * `null` for an id that is not on the rail, and the caller draws no kicker —
 * an invented number would be the defect this function exists to remove.
 */
export function stepNumberOf(id: string): number | null {
  const at = BILL_RUN_STEPS.findIndex((one) => one.id === id);
  return at === -1 ? null : at + 1;
}

/** The phase a step sits in — DATA, never arithmetic over a step number. */
export function phaseOfStep(stepNumber: number): RunPhase | null {
  return BILL_RUN_STEPS[stepNumber - 1]?.phase ?? null;
}

/** BR-SHL-011's spirit: an out-of-range `?step=` clamps; it never errors. */
export function runStepFromParam(raw: string | null): number {
  const parsed = Number(raw ?? "1");
  if (!Number.isInteger(parsed)) {
    return 1;
  }
  return Math.min(Math.max(1, parsed), BILL_RUN_STEP_COUNT);
}

// ── Step 1: what the clerk chooses, and what is derived (US-BIL-001) ───────

export interface RunScopeForm {
  cycleId: string;
  periodStart: string; // "YYYY-MM-DD"
  periodEnd: string;
  billDate: string;
  /**
   * CR-029 D9 — the run's due-days OVERRIDE, **as typed**.
   *
   * ⚠ **A STRING, AND THAT IS THE WHOLE DESIGN.** `number | null` cannot tell
   * *"the clerk typed 0"* from *"the clerk typed nothing"*, and those are two
   * different instructions to the server: 0 means **due on the bill date** (a
   * lawful arrangement — BR-MET-009 requires only `due_days ≥ 0`) while empty
   * means *use the cycle's default*. Collapsing them would hand every customer
   * in the run the cycle's terms while the clerk watched their own zero vanish.
   */
  dueDays: string;
  /** BR-BIL-021/US-BIL-001 §5: recorded even when it is every service. */
  services: string[];
}

export function emptyRunScopeForm(): RunScopeForm {
  return {
    cycleId: "",
    periodStart: "",
    periodEnd: "",
    billDate: "",
    dueDays: "",
    services: [],
  };
}

export type RunPeriodProblem = "required" | "ends_before_start";

/** US-BIL-001 TC-5: `period_end < period_start` is refused before a round trip. */
export function periodProblem(start: string, end: string): RunPeriodProblem | null {
  if (start === "" || end === "") {
    return "required";
  }
  return end < start ? "ends_before_start" : null;
}

/**
 * CR-029 D9 — what a due-days entry may be, refused before the network.
 *
 * ⚠ **EMPTY IS FINE AND `0` IS FINE, AND THEY ARE NOT THE SAME ANSWER.** Empty
 * means the run takes the cycle's default; `0` means due on the bill date. The
 * only refusal is a value that is not a whole number of days, or a negative one
 * — every bill in a run with negative due-days would be overdue the day it was
 * sent, which is why `issue.derive_due_date` refuses it server-side too.
 *
 * The same three rejects the server rejects (`api._optional_due_days`): a
 * fraction, a word, a negative. Stated in both places on purpose — the client
 * refusal is a courtesy and the server's is the rule.
 */
export function dueDaysProblem(raw: string): "range" | null {
  const text = raw.trim();
  if (text === "") {
    return null;
  }
  return /^\d+$/.test(text) ? null : "range";
}

/**
 * The due-days the form is carrying, as the API's own value — `undefined` when
 * nobody typed one, so the key is OMITTED from the body and the cycle's default
 * governs. **Never `null` for a typed `0`.**
 */
export function dueDaysValue(raw: string): number | undefined {
  const text = raw.trim();
  if (text === "" || dueDaysProblem(text) !== null) {
    return undefined;
  }
  return Number(text);
}

/**
 * CR-029 D9 — **picking a cycle OFFERS its defaults; it never forces them.**
 *
 * PO, verbatim 2026-08-23: *"when we configure Cycle we are provideing default
 * values; mostly it wil remain as it is but user can over ride them during
 * billing"*. So this fills a field the clerk has left ALONE and touches nothing
 * they have typed — including a typed `"0"`, which a truthiness test would
 * quietly replace with the cycle's own number.
 *
 * ⚠ **THE PERIOD COMES FROM THE SERVER'S `next_period` AND FROM NOWHERE ELSE.**
 * The three schedule fields (start day · frequency · days to complete) are on
 * the payload and it would be one line to turn them into a window here — and on
 * a cycle anchored to the 29th, 30th or 31st that line would be this product
 * answering **OQ-339** by call site, which the whole period engine exists to
 * refuse. A cycle the engine declined to propose for prefills NOTHING, and the
 * clerk types the period, which is exactly what the wizard did before.
 *
 * Worked, and it is the figure the ruling was confirmed on: cycle 06-A bills
 * **1 Jul** with **21** due-days → due **22 Jul**. A clerk who types **14** on
 * the run gets **15 Jul**, and the cycle still says 21 for the next run.
 */
export function prefillFromCycle(form: RunScopeForm, cycle: CycleRow | null): RunScopeForm {
  if (cycle === null) {
    return form;
  }
  const offered = { ...form };
  if (offered.periodStart === "" && cycle.next_period !== null) {
    offered.periodStart = cycle.next_period.period_start;
  }
  if (offered.periodEnd === "" && cycle.next_period !== null) {
    offered.periodEnd = cycle.next_period.period_end;
  }
  if (offered.billDate === "" && cycle.bill_date !== null) {
    offered.billDate = cycle.bill_date;
  }
  // ⚠ `!== ""`, NOT a truthiness test — see `RunScopeForm.dueDays`.
  if (offered.dueDays === "" && cycle.due_days !== null) {
    offered.dueDays = String(cycle.due_days);
  }
  return offered;
}

/**
 * BR-BIL-024 — due date = bill date + the cycle's due-days. **Display only**,
 * and only at this step: the stored `invoices.due_date` is derived by the server
 * AT ISSUE and is never typed by anyone (US-BIL-001 §5, "never user-typed"), so
 * this function exists to SHOW the consequence of a bill date, not to send one.
 *
 * `dueDays` null ⇒ null. The cycle's due-days is tenant configuration
 * (BR-BIL-021) and a cycle that has not been given one cannot produce a due
 * date; a default of 21 here would be exactly the hardcoded constant that rule
 * forbids, printed as though the tenant had chosen it.
 *
 * ⚠ **CR-029 D9 — THE CALLER NOW PASSES THE RUN'S OWN DUE-DAYS WHEN ONE WAS
 * TYPED, AND THE CYCLE'S ONLY OTHERWISE.** That precedence is the server's
 * (`runs.effective_due_days`) and this function does not own it — it adds days
 * to a date and nothing more. `0` is a real argument here: 2026-07-01 + 0 =
 * **2026-07-01**, due on the bill date, which is why the guard below tests
 * `Number.isInteger` and never truthiness.
 *
 * UTC arithmetic on a calendar date, never a local `Date` — a date-only value
 * shifted through a browser timezone is how "Aug 22" becomes "Aug 21" for half
 * the world. No clock is read: the input is a date the user typed.
 * Worked (US-BIL-001 TC-1): 2026-08-01 + 21 = **2026-08-22**.
 */
export function dueDateFrom(billDate: string, dueDays: number | null): string | null {
  if (billDate === "" || dueDays === null || !Number.isInteger(dueDays)) {
    return null;
  }
  const parsed = Date.parse(`${billDate}T00:00:00Z`);
  if (Number.isNaN(parsed)) {
    return null;
  }
  return new Date(parsed + dueDays * 86_400_000).toISOString().slice(0, 10);
}

// ── Is this period continuous with the last one? (blueprint p046 · p048) ───

/**
 * What sits between this run's period and the previous run's, on the same
 * cycle. `unknown` when there is nothing to compare against.
 */
export type PeriodContinuity =
  | { state: "unknown" }
  | { state: "continuous"; previousEnd: string }
  | { state: "gap"; days: number; from: string; to: string }
  | { state: "overlap"; days: number; from: string; to: string };

/** One day, in the milliseconds `Date.parse` counts. */
const ONE_DAY = 86_400_000;

function dayValue(iso: string): number | null {
  if (iso === "") {
    return null;
  }
  const parsed = Date.parse(`${iso}T00:00:00Z`);
  return Number.isNaN(parsed) ? null : parsed;
}

function isoOf(value: number): string {
  return new Date(value).toISOString().slice(0, 10);
}

/**
 * **THE QUESTION A CLERK CANNOT ANSWER TODAY, AND IT IS MONEY BOTH WAYS.**
 *
 * The blueprint puts it plainly (p048): *"The clerk's question is not 'what is
 * this period?' — the cycle answers that. It is **'is billing continuous?'**,
 * and nothing can answer that except the previous period sitting next to this
 * one. **A gap is days nobody billed. An overlap is days billed twice.** Both
 * are silent, both are money, and neither is visible anywhere in this product
 * today."*
 *
 * Three states, and they are not equal in weight:
 *
 * * **continuous** — this period starts the day after the last one ended;
 * * **gap** — days between the two that no run covered. Not a refusal: a
 *   mid-cycle change can make a gap legitimate. It is STATED, and stated
 *   BEFORE the run starts rather than found afterwards;
 * * **overlap** — days this run would bill that a previous run already billed.
 *   Customer-visible, and a correction then undoes it one bill at a time.
 *
 * ⚠ **"PREVIOUS" MEANS STRICTLY EARLIER, NOT MERELY OTHER.** The comparison
 * takes the newest run on this cycle whose period STARTS before ours. Without
 * that, re-opening the run you are already working on compares a period with
 * itself and reports a full-period overlap — a false alarm on the most ordinary
 * thing a clerk does on this screen.
 *
 * ⚠ **IT COSTS NO NEW READ.** `GET /billing/runs` is already fetched by this
 * step for the past-runs panel, and it already carries `period_start`,
 * `period_end` and `cycle_id` — one query, two facts, which is what the
 * blueprint says of it.
 *
 * ⚠ **EVERY DATE HERE IS DERIVED, NEVER DRAWN.** The blueprint illustrates this
 * band with *"2 days were never billed: 30–31 Aug"*; B14 rule 37 says a figure
 * drawn in a wireframe is an illustration and never a fact to build to, so no
 * test may assert that pair and no fixture may be seeded from it.
 */
export function periodContinuity(
  periodStart: string,
  cycleId: string,
  pastRuns: readonly BillRunHistoryRow[],
): PeriodContinuity {
  const start = dayValue(periodStart);
  if (start === null || cycleId === "") {
    return { state: "unknown" };
  }
  let previousEnd: number | null = null;
  for (const run of pastRuns) {
    if (run.cycle_id !== cycleId || run.period_start === null || run.period_end === null) {
      continue;
    }
    const runStart = dayValue(run.period_start);
    const runEnd = dayValue(run.period_end);
    if (runStart === null || runEnd === null || runStart >= start) {
      continue;
    }
    if (previousEnd === null || runEnd > previousEnd) {
      previousEnd = runEnd;
    }
  }
  if (previousEnd === null) {
    return { state: "unknown" };
  }
  const expected = previousEnd + ONE_DAY;
  if (start === expected) {
    return { state: "continuous", previousEnd: isoOf(previousEnd) };
  }
  if (start > expected) {
    return {
      state: "gap",
      days: Math.round((start - expected) / ONE_DAY),
      from: isoOf(expected),
      to: isoOf(start - ONE_DAY),
    };
  }
  return {
    state: "overlap",
    days: Math.round((previousEnd - start) / ONE_DAY) + 1,
    from: periodStart,
    to: isoOf(previousEnd),
  };
}

// ── The API's own state, DERIVED (the `listRouteAbsent` precedent) ─────────

/**
 * True when this API serves no bill runs at all.
 *
 * `POST /billing/runs` is a COLLECTION-create route: there is no id in the path
 * for a server to fail to find, so a 404 from it is never "that run is missing"
 * — it can only mean "no such resource". Same reading as `listRouteAbsent` on
 * `GET /invoices`, and the same consequence: the sentence the wizard renders
 * about it stops being reachable the day the route is registered, with nothing
 * here edited. Deliberately NOT a build flag (hard-won law 1).
 */
export function runRouteAbsent(error: unknown): boolean {
  return isApiError(error) && error.status === 404;
}

/**
 * BR-BIL-005: an identical (tenant, cycle, period) is refused with who, when
 * and a link to the original. The refusal is the SERVER's — 409 with the
 * envelope's own `message_key` and params — so this only recognises it. A
 * client that re-implemented the message would be re-implementing the rule.
 */
export function runIsDuplicate(error: unknown): boolean {
  return isApiError(error) && error.status === 409;
}

/**
 * The ORIGINAL run a 409 points at — BR-BIL-005's third fact, the LINK.
 *
 * ⚠ **THE LINK WAS THE HALF NOBODY BUILT, AND IT LEFT THE CLERK STUCK FOREVER
 * (DEF-178).** `runs.DuplicateRun`'s own docstring says the rule "names three
 * things the refusal must show — *who ran the original, when, and a link* — and
 * only the caller knows how to render a link". This screen was that caller and
 * it rendered none: `createRun` failed, `startRun` returned, and the run id the
 * server had just handed over was dropped on the floor. Because the refusal is
 * PERMANENT — that tenant+cycle+period can never be created again, by design —
 * the wizard became a dead end with no way forward and no way to the run that
 * already existed. The refusal that protects the clerk from double-billing was
 * indistinguishable from the product being broken.
 *
 * Returns null when the envelope named no run, rather than inventing one: an
 * "open it" control that opens nothing is worse than no control (hard-won
 * law 2).
 */
export interface DuplicateRunRef {
  runId: string;
  ranAt: string | null;
}

export function duplicateRunRef(error: unknown): DuplicateRunRef | null {
  if (!runIsDuplicate(error) || !isApiError(error)) {
    return null;
  }
  const runId = error.params.run_id;
  if (typeof runId !== "string" || runId === "") {
    return null;
  }
  const ranAt = error.params.ran_at;
  return { runId, ranAt: typeof ranAt === "string" && ranAt !== "" ? ranAt : null };
}

// `scopeRefusalText` deliberately lives in `BillRunWizard.tsx` beside
// `scopeProblems` and the `ScopeProblem` union it reads, NOT here. Pulling it
// down would make this file import a type from its own importer — the exact
// cycle DEF-175 blanked a whole screen with, invisible to tsc, eslint and
// vitest and visible only in the bundled SPA. The arrows point one way.

// ── Step 2: the six findings tabs (US-BIL-002, prototype line 2937) ────────

export interface FindingTab {
  id: string;
  labelKey: string;
}

export const FINDING_TABS: readonly FindingTab[] = [
  { id: "consumers", labelKey: "billing.run.found.tab.consumers" },
  { id: "plans", labelKey: "billing.run.found.tab.plans" },
  { id: "reads", labelKey: "billing.run.found.tab.reads" },
  { id: "balances", labelKey: "billing.run.found.tab.balances" },
  { id: "credits", labelKey: "billing.run.found.tab.credits" },
  { id: "overcharges", labelKey: "billing.run.found.tab.overcharges" },
];

export function findingTabFrom(raw: string | null): string {
  return FINDING_TABS.some((tab) => tab.id === raw) ? (raw as string) : FINDING_TABS[0].id;
}

/**
 * Which findings tab owns which STAGE — BR-BIL-040's *"surfaced in the tab that
 * owns that stage's inputs (Plans ← stage 1, Reads ← stage 2, …)"*, and nothing
 * more than that.
 *
 * **This replaced a reason→tab table on 2026-08-11 and the deletion is the
 * point.** That table listed fourteen reason CODES — every `GATHER_*`, `RUN_*`
 * and `CALC_*` constant in `06-backend/apps/billing/` — and re-derived what the
 * server had already computed in `runs.STAGE_BY_REASON`, because
 * `runs.AccountProblem` carried no stage where `runs.Break` did. It was
 * REPORTED, the backend put `stage` on the problem, and what is left here is
 * the only half that was ever this screen's: which of ITS OWN TABS shows a
 * given stage. A new reason code now lands on the right tab with nothing here
 * edited — which is exactly what the duplicate could never do.
 *
 * `price-usage` maps to Plans because its inputs are the tariff VERSIONS, which
 * is where a clerk goes to fix "no version in force at the service date".
 *
 * A NULL stage is a real answer and lands on Consumers: the run's own shape
 * (`cycle_has_no_service_points`, `unit_has_no_billable_account`) and the
 * base-only opt-in (BR-BIL-061) are not stage failures, and US-BIL-002 §1 puts
 * the base-only cohort on Consumers by name. An UNKNOWN stage lands there too
 * rather than being dropped — a finding nobody mapped is still a finding, and a
 * screen that silently discards one has reintroduced the silent skip the whole
 * model forbids (billing model §2).
 */
export const FINDING_TAB_BY_STAGE: Readonly<Record<string, string>> = {
  "resolve-subscription": "plans",
  "measure-consumption": "reads",
  "price-usage": "plans",
};

export function findingTabForStage(stage: string | null): string {
  return (stage === null ? undefined : FINDING_TAB_BY_STAGE[stage]) ?? "consumers";
}

/**
 * The findings tabs `prepare_run` returns NOTHING for. Balances (prior
 * balances + late-fee candidates, BR-BIL-001/002/008) and Credits (unallocated
 * credits in allocation order, BR-PAY-010) are both in US-BIL-002's scope and
 * neither is in `PreparedRun` — it carries `ready`, `blocked` and `decisions`
 * and no money at all. Named as a set so the screen renders the same honest
 * panel for each and one line deletes them when the server answers.
 *
 * ⚠ **`overcharges` LEFT THIS SET ON 2026-08-31 (CR-051 tasks 15 and 18), AND
 * THE REASON IS THAT THE TAB NAME MEANT TWO THINGS.** The list read
 * `["balances", "credits", "overcharges"]` on the belief that the tab was
 * BR-BIL-029's guardrail preview, which really is unserved. It is not: r10 line
 * 4256 draws late fees and service charges under that heading — *charges to
 * ADD* — and CR-053's own note says so in one line: *"the Over charges tab
 * holds charges to ADD, not the overcharge guardrail. Two concepts share one
 * name and the screen inherits the confusion."* Those rows ARE served, on
 * `GET /billing/runs/{id}/exceptions` as the `late_fee` and `extra_charge`
 * cases, and the tab now draws them. The guardrail preview is still unserved
 * and still says so — on STEP 4, under *Unusually large bills*, where
 * BR-BIL-029 actually lives.
 */
export const FINDING_TABS_UNSERVED: readonly string[] = ["balances", "credits"];

/** BR-CUS-055's class, as the run reports it. The cohort BR-BIL-061 is about. */
export const BASE_ONLY_CLASS = "billable_base_only";

/**
 * The blocked findings, grouped by REASON CODE with their count — the shape
 * S31.2 renders (`PreparedRun.blocked_by_reason` on the server side). The code
 * is the grouping key because it is stable; the human sentence lives on each
 * row underneath it (US-BIL-002 §1, `runs.AccountProblem`'s own docstring).
 *
 * Insertion-ordered, so the screen shows reasons in the order the run met them
 * rather than in an alphabetical order nobody chose.
 */
export function groupByReason<T extends { reason: string }>(
  problems: readonly T[],
): { reason: string; rows: T[] }[] {
  const groups: { reason: string; rows: T[] }[] = [];
  for (const problem of problems) {
    const existing = groups.find((group) => group.reason === problem.reason);
    if (existing === undefined) {
      groups.push({ reason: problem.reason, rows: [problem] });
    } else {
      existing.rows.push(problem);
    }
  }
  return groups;
}

// ── Step 3: the case tables and the bulk law (US-BIL-003 · BR-BIL-060) ─────

export interface CaseTab {
  /** A `DECISION_CASES` value where one exists — the server's own vocabulary. */
  id: string;
  labelKey: string;
}

/**
 * The case kinds a run can raise — and **only** the ones it can raise.
 *
 * ⚠ **THIS LIST HELD FIFTEEN UNTIL `CR-101-BRC03` AND THE ENGINE EMITS NINE
 * (`DEF-2596`).** The six removed were `overcharge`, `no_usage`, `owes`,
 * `past_due`, `late_fee` and `extra_charge`. Each was a filter a clerk could
 * pick and that could never have a row behind it — and an empty table is the
 * one answer that cannot distinguish *"none this run"* from *"this can never
 * happen"*, on the screen where a clerk decides what a utility charges.
 *
 * **The rule is the blueprint's own, §03 p041, ruled 2026-09-11:** *"A case
 * kind the engine did not raise **gets no chip**… The as-built screen declares
 * fifteen."*
 *
 * Measured at `v2.261.4`, both sides, rather than carried forward:
 *
 * | where | how many |
 * |---|---|
 * | `runs.py` `AccountProblem(reason="…")` | **2** — `missing_read`, `base_only_billing` |
 * | `read_analysis.READ_ANALYSIS_CASES` | **7** |
 * | **emitted, total** | **9** |
 * | declared here, before | 15 |
 *
 * Four of the six (`overcharge`, `no_usage`, `late_fee`, `extra_charge`) ARE
 * real `DECISION_CASES` values — the server would have recorded a decision on
 * one — and no code path creates a row carrying them. The other two (`owes`,
 * `past_due`) were never in `DECISION_CASES` at all, so even a row that
 * somehow appeared could not have stored a reply.
 *
 * ⚠ **REMOVING A KIND FROM THIS LIST WOULD SILENTLY DROP ITS ROWS**, because
 * `familyRows` keeps only rows whose case a family claims — which is the
 * `DEF-2381` shape (an account vanishing from a run with nothing said). It is
 * refused rather than accepted: `casesWithNoChip()` below reports any served
 * row whose kind this list does not hold, and the screen SAYS SO. So if the
 * engine ever starts raising `late_fee` — `17.20 Waiver` is drawn against
 * exactly that day — the rows are named on screen rather than disappearing.
 *
 * **`G124` is what stops this drifting again.** It reads the Python emitters
 * and this constant independently and fails when a kind is declared here that
 * no engine path can raise. Nothing compared the two lists before it: they
 * live in two languages, and `tsc` type-checks a list of strings.
 */
export const CASE_TABS: readonly CaseTab[] = [
  // ── CR-038 W8 (2026-08-26): the read-analysis cases, in the prototype's own
  // BIL-02.2 order (Estimated · High · Low · Days threshold · Meter factor)
  // plus the two the CR adds (Replacements · True-up). The old `estimated`
  // placeholder tab — a prototype label with no `DECISION_CASES` value — is
  // SUPERSEDED by `estimated_read`, which records for real; the reported gap
  // it named is closed rather than kept alongside its fix.
  { id: "estimated_read", labelKey: "billing.run.case.estimated" },
  { id: "high_usage", labelKey: "billing.run.case.high" },
  { id: "low_usage", labelKey: "billing.run.case.low" },
  { id: "days_threshold", labelKey: "billing.run.case.days" },
  { id: "meter_factor", labelKey: "billing.run.case.factor" },
  { id: "replacement", labelKey: "billing.run.case.replacement" },
  { id: "true_up", labelKey: "billing.run.case.trueUp" },
  { id: "missing_read", labelKey: "billing.run.case.missingRead" },
  { id: "base_only_billing", labelKey: "billing.run.case.baseOnly" },
  // BR-BIL-301 (PO 2026-09-25, option (b)) — the accounts billing $0.00 for a
  // service the plan sells them and the property is not connected for. Drawn
  // as a tab rather than left to `casesWithNoChip`, because the whole second
  // half of the ruling is that a clerk can WORK THROUGH these; a kind with no
  // chip belongs to no family and is filtered out of every table.
  { id: "service_not_connected", labelKey: "billing.run.case.notConnected" },
];

/**
 * The kinds among the SERVED rows that this screen draws no chip for.
 *
 * ⚠ **THE MIRROR OF `CASE_TABS`, AND THE REASON TRIMMING IT IS SAFE.** Every
 * filter, family and chip is derived from `CASE_TABS`, so a row whose kind is
 * not in it belongs to no family and would be filtered out of every table —
 * present in the payload, absent from the screen, and counted in no total. An
 * account falling silently out of a run is `DEF-2381`, which the blueprint
 * calls the most important thing on this screen.
 *
 * So the answer to *"the engine raised something we do not draw"* is to SAY
 * SO, never to drop it. Reads the rows, never a declaration — a list checked
 * against itself would move with whatever it was meant to catch.
 */
export function casesWithNoChip(rows: readonly BillRunExceptionRow[]): string[] {
  const drawn = new Set(CASE_TABS.map((tab) => tab.id));
  return [...new Set(rows.map((row) => row.case))].filter((one) => !drawn.has(one)).sort();
}

/**
 * The STORED figures each read-analysis case table draws as columns, in order
 * (CR-038 W8). Keys are the server's `facts` members — `read_analysis.py` owns
 * the vocabulary and this maps each key to its column header — and a fact the
 * server did not send renders a dash, never a zero. Cases absent here (the
 * classic six) render no facts columns at all.
 */
export const CASE_FACT_COLUMNS: Readonly<
  Record<string, readonly { key: string; labelKey: string }[]>
> = {
  estimated_read: [
    { key: "meter", labelKey: "billing.run.factcol.meter" },
    { key: "estimation_method", labelKey: "billing.run.factcol.method" },
    { key: "consecutive_estimate_no", labelKey: "billing.run.factcol.consecutive" },
  ],
  high_usage: [
    { key: "meter", labelKey: "billing.run.factcol.meter" },
    { key: "this_period", labelKey: "billing.run.factcol.thisPeriod" },
    { key: "trailing_average", labelKey: "billing.run.factcol.average" },
    { key: "ratio_pct", labelKey: "billing.run.factcol.ratio" },
    { key: "threshold_pct", labelKey: "billing.run.factcol.threshold" },
  ],
  low_usage: [
    { key: "meter", labelKey: "billing.run.factcol.meter" },
    { key: "this_period", labelKey: "billing.run.factcol.thisPeriod" },
    { key: "trailing_average", labelKey: "billing.run.factcol.average" },
    { key: "ratio_pct", labelKey: "billing.run.factcol.ratio" },
    { key: "threshold_pct", labelKey: "billing.run.factcol.threshold" },
  ],
  days_threshold: [
    { key: "meter", labelKey: "billing.run.factcol.meter" },
    { key: "days", labelKey: "billing.run.factcol.days" },
    { key: "expected_days", labelKey: "billing.run.factcol.expectedDays" },
    { key: "judged_by", labelKey: "billing.run.factcol.judgedBy" },
  ],
  meter_factor: [
    { key: "meter", labelKey: "billing.run.factcol.meter" },
    { key: "multiplier", labelKey: "billing.run.factcol.factor" },
    { key: "current_value", labelKey: "billing.run.factcol.rawRead" },
    { key: "computed", labelKey: "billing.run.factcol.computed" },
  ],
  replacement: [
    { key: "old_meter", labelKey: "billing.run.factcol.oldMeter" },
    { key: "old_final_quantity", labelKey: "billing.run.factcol.oldFinal" },
    { key: "new_meter", labelKey: "billing.run.factcol.newMeter" },
    { key: "new_start_quantity", labelKey: "billing.run.factcol.newStart" },
    { key: "segments_total", labelKey: "billing.run.factcol.segmentsTotal" },
  ],
  true_up: [
    { key: "meter", labelKey: "billing.run.factcol.meter" },
    { key: "register_delta", labelKey: "billing.run.factcol.actualSpan" },
    { key: "estimated_total", labelKey: "billing.run.factcol.estimatedBilled" },
    { key: "trued_quantity", labelKey: "billing.run.factcol.truedQuantity" },
  ],
};

/**
 * The fact columns whose VALUE is a code rather than a figure — B14 rule 32
 * clause 4, `DEF-2882`.
 *
 * ⚠ **A FACT CELL RENDERED `String(value)` AND MOST FACTS ARE NUMBERS, WHICH IS
 * WHY THIS WENT UNNOTICED.** Meter numbers, day counts, ratios and quantities
 * all render correctly that way, so the cell looked right on every column but
 * two — and on those two a billing clerk read **`trailing_3_avg`** under
 * *Method* and **`cycle_span`** under *Judged against*. Both are the metering
 * engine's own identifiers, served (correctly) so the screen can group and
 * explain them; printing them is the screen declining to do the explaining.
 *
 * Only these two keys are listed, deliberately. Every other fact is a figure or
 * a human reference (`meter` is `asset_no`, never an id — B14 rule 31), and
 * translating a number would be worse than leaving it alone. A value with no
 * catalogue entry still renders as itself: an unmapped code is at least a fact
 * a clerk can quote to support, and inventing a sentence for a code we have
 * never seen would be this file guessing at the engine's meaning.
 */
export const CODED_FACT_KEYS: readonly string[] = ["estimation_method", "judged_by"];

/** The words for a coded fact value, or the value itself when we have none. */
export function factValueText(
  t: Translator,
  key: string,
  value: string | number,
): string {
  if (!CODED_FACT_KEYS.includes(key)) {
    return String(value);
  }
  return t(`billing.run.factvalue.${String(value)}`, { defaultValue: String(value) });
}

/** Case ids that name no `DECISION_CASES` value — a choice cannot be recorded. */
export const CASES_WITHOUT_A_RECORD: readonly string[] = CASE_TABS.filter(
  (tab) => !(DECISION_CASES as readonly string[]).includes(tab.id),
).map((tab) => tab.id);

/**
 * ⛔ **`caseTabFrom` IS DELETED — CR-051 task 17, 2026-08-31.** It narrowed a
 * URL value to one of fifteen case tabs and there are no longer fifteen case
 * tabs. `billRunStep23.familyFrom` narrows the FAMILY and the wizard checks the
 * case filter against `familyCases(open family)`, which is the same guarantee
 * one level up: a `?kind=` naming a case that is not in the open family is not
 * honoured as a filter for it.
 */

/**
 * **The one asymmetry the PO made deliberate (BR-BIL-060 + BR-BIL-003).**
 *
 * Bulk APPLY of a late fee is allowed — *"if there are 500 or 1000 or 5000
 * bills to be generated and 1000 bills has late fees, it is impossible for user
 * to do this manually account by account"*. Bulk WAIVE is not, because a
 * first-time waiver is a per-case staff decision that carries a reason
 * (BR-BIL-003), and a bulk control that waived a thousand fees would launder a
 * manual-only rule through a convenience.
 *
 * Returns the catalog key for WHY it is refused, or null when the bulk action
 * is allowed. The server refuses regardless (US-BIL-003 TC-10) — this only
 * means the clerk is told which and why instead of finding out after a click.
 */
export function bulkRefusalKey(caseId: string, choice: string): string | null {
  if (caseId === "late_fee" && choice.startsWith("waive")) {
    return "billing.run.bulk.waiveRefused";
  }
  return null;
}

/** A selection, as a pure value — the wizard holds it and this reasons about it. */
export function toggleSelected(selected: readonly string[], id: string): string[] {
  return selected.includes(id)
    ? selected.filter((value) => value !== id)
    : [...selected, id];
}

export function toggleAll(selected: readonly string[], ids: readonly string[]): string[] {
  return ids.every((id) => selected.includes(id)) ? [] : [...ids];
}

/**
 * BR-BIL-060: the confirm dialog shows the SELECTION COUNT and, where money is
 * involved, the SELECTION TOTAL — before the click.
 *
 * The total is the SERVER's Σ for the case and it is returned as-is, never
 * re-added across the selected rows. Two reasons, and both are load-bearing:
 * money is NUMERIC(18,6) and a browser that adds decimal strings has just
 * become a money path (CLAUDE.md rule 2, BR-SHL-023); and a selection is not a
 * page — the clerk may have selected 1,000 rows of which 25 are loaded, so a
 * sum over what happens to be in memory would be confidently wrong.
 *
 * `total` null ⇒ the dialog shows the count and says the total is not served.
 * A missing Σ never becomes a computed one.
 */
export interface BulkSelectionSummary {
  count: number;
  total: { amount: string; currency: string } | null;
}

export function bulkSelectionSummary(
  selected: readonly string[],
  servedTotal: { amount: string; currency: string } | undefined,
  wholeCaseSelected: boolean,
): BulkSelectionSummary {
  return {
    count: selected.length,
    // The served Σ answers "the whole case". It is honest for a select-all and
    // dishonest for anything narrower, so a partial selection reports no total
    // rather than a total for rows the clerk did not choose.
    total: wholeCaseSelected && servedTotal !== undefined ? servedTotal : null,
  };
}

// ── Step 4: the breaks (BR-BIL-053) and the guardrail exception (BR-BIL-054) ──

/**
 * ⛔ **`retryRefusalKey` LIVED HERE AND IS DELETED (CR-051 task 7, 2026-08-30).**
 * Its contract was *"a key, or NULL when the retry is allowed"*, and the null
 * branch became a lie the day DEF-2557 was filed: `runs.retry_account` is built
 * and tested and reachable from **no route**, so there is no shape of this
 * product in which a retry control may act. A function that answers "allowed"
 * would have handed a screen a live button over a missing endpoint — hard-won
 * law 2, the exact defect this repository keeps paying for.
 *
 * Its replacement is `billRunResume.breakRetryReason`, which returns a SENTENCE
 * on every branch and therefore cannot enable anything. The server's own
 * `retryable` still decides FIRST — `NOT_RETRYABLE_HERE` is the backend's
 * authority and a row it refuses would still refuse once the route lands.
 */

/** BR-BIL-053: the phase-3 grouping — a clerk fixes all the missing reads at once. */
export function breaksByStage(
  breaks: readonly BillRunBreak[],
): { stage: string; rows: BillRunBreak[] }[] {
  const groups: { stage: string; rows: BillRunBreak[] }[] = [];
  for (const brk of breaks) {
    const existing = groups.find((group) => group.stage === brk.stage);
    if (existing === undefined) {
      groups.push({ stage: brk.stage, rows: [brk] });
    } else {
      existing.rows.push(brk);
    }
  }
  return groups;
}

/**
 * BR-BIL-054's three required actions on an over-guardrail draft: release it
 * knowingly, exclude it, or send it back for a read check. Named here as the
 * epic names them; the CHOICE VALUES a row actually accepts still come with the
 * row from the server (`BillRunExceptionRow.choices`), because the vocabulary
 * `bill_run_decisions.choice` stores is the server's.
 */
export const OVERCHARGE_ACTION_KEYS = [
  "billing.run.overcharge.release",
  "billing.run.overcharge.exclude",
  "billing.run.overcharge.readCheck",
] as const;

// ── Step 5: the summary (BR-BIL-056/057) and the gate (BR-BIL-058/059) ────

/**
 * BR-BIL-057 — the category axes, **PROPOSED and NOT RULED**. The PO said *"and
 * various categories"* and enumerated none, so this is the derived seed the rule
 * carries and the screen labels it as an open decision rather than a menu.
 * A run built before that ruling "implements the axes it can derive and stubs
 * the axis SET as the open decision it is".
 */
export const SUMMARY_AXES = [
  "service",
  "consumer_category",
  "bill_type",
  "status_class",
  "delivery_channel",
  "exception_state",
] as const;

/**
 * BR-BIL-058 — the release gate is FIVE separate facts, each shown separately
 * and each RECORDED separately, because *"a release that went out without the
 * compliance check is a different event from one that did, and only separate
 * facts can say which happened"*.
 *
 * `coverageKey` is the sentence each is shown AGAINST (BR-BIL-059): how many
 * accounts hold that mandate and how many do not. The final confirm has no
 * coverage — it attests the whole run, not a mandate — which is why the field
 * is nullable rather than a fifth invented count.
 */
export interface GateFact {
  id: string;
  labelKey: string;
  coverageKey: string | null;
  /**
   * The mandate whose coverage this confirmation is shown against, as the
   * SERVER names it on the phase-4 summary (DEF-2854).
   *
   * ⚠ **IT IS A FIELD RATHER THAN A PREFIX MATCH ON `id`.** `email_mandate`
   * happens to start with `email` today and matching on that would be a
   * coincidence doing load-bearing work: rename either side and the coverage
   * silently stops resolving, which renders "not counted" beside a tick that
   * says the clerk has seen the number. Compliance and the final confirm carry
   * NULL because neither is a mandate — compliance attests a checklist and the
   * final confirm attests the whole run, so neither has a coverage to count,
   * and a fifth invented figure is exactly what BR-BIL-059 is guarding.
   */
  mandate: string | null;
}

export const GATE_FACTS: readonly GateFact[] = [
  {
    id: "compliance",
    labelKey: "billing.run.gate.compliance",
    coverageKey: "billing.run.gate.complianceCoverage",
    mandate: null,
  },
  {
    id: "email_mandate",
    labelKey: "billing.run.gate.email",
    coverageKey: "billing.run.gate.emailCoverage",
    mandate: "email",
  },
  {
    id: "sms_mandate",
    labelKey: "billing.run.gate.sms",
    coverageKey: "billing.run.gate.smsCoverage",
    mandate: "sms",
  },
  {
    id: "autopay_mandate",
    labelKey: "billing.run.gate.autopay",
    coverageKey: "billing.run.gate.autopayCoverage",
    mandate: "autopay",
  },
  { id: "final", labelKey: "billing.run.gate.final", coverageKey: null, mandate: null },
];

export type GateState = Record<string, boolean>;

export function emptyGateState(): GateState {
  return Object.fromEntries(GATE_FACTS.map((fact) => [fact.id, false]));
}

/**
 * BR-BIL-058: release is REFUSED while any of the five is untaken, and the
 * refusal NAMES the one that is missing (US-BIL-005 TC-10).
 *
 * BR-BIL-059 is the other half and it is enforced by ABSENCE here: nothing in
 * this function looks at coverage. An account with no email address, no SMS
 * opt-in and no autopay mandate still bills and never blocks the release —
 * print is the primary channel and the floor (BR-BIL-036). The confirmations
 * attest that the operator SAW the coverage, not that everyone is covered.
 */
export function untakenGateFacts(state: GateState): GateFact[] {
  return GATE_FACTS.filter((fact) => state[fact.id] !== true);
}

/**
 * The gate state as the five booleans `POST /billing/runs/{id}/release` records
 * (BR-BIL-058) — every one of them stated, always.
 *
 * IT DOES NOT SEND ONLY THE TICKED ONES, and that is the point of the rule: an
 * untaken confirmation is a FACT the record has to carry, not an absence. The
 * server reads a missing key as *not confirmed* and refuses naming it, so the
 * two agree either way — but a body that omitted them would make "Priya did not
 * tick compliance" and "this client version does not know about compliance"
 * the same wire shape, and only one of those is a thing a clerk did.
 *
 * `!== false` is deliberately not used: anything that is not literally `true`
 * is not a confirmation, because this is the record of a human saying go before
 * money leaves.
 */
export function releaseConfirmations(state: GateState): BillRunReleaseBody["confirmations"] {
  return {
    compliance: state.compliance === true,
    email_mandate: state.email_mandate === true,
    sms_mandate: state.sms_mandate === true,
    autopay_mandate: state.autopay_mandate === true,
    final: state.final === true,
  };
}

export function gateBlockedReason(state: GateState, t: Translator): string | null {
  const untaken = untakenGateFacts(state);
  if (untaken.length === 0) {
    return null;
  }
  return t("billing.run.gate.blocked", {
    count: untaken.length,
    first: t(untaken[0].labelKey),
  });
}

// ── Small components the steps share ───────────────────────────────────────

/**
 * The rule and story references behind each `RunGap`, as CONSTANTS rather than
 * catalogue entries (CR-016, 2026-08-19).
 *
 * **Why they left the i18n catalogue.** These eleven strings used to live in all
 * ELEVEN locale files as `billing.run.*.gapRule`, and they were translated —
 * eleven copies of "Rule BR-BIL-015 · column bill_run_decisions.case", one per
 * language. A translation catalogue is for text a human reads, and a rule id is
 * not that: it is the same in every language, no translator can improve it, and
 * G15 was keeping eleven copies of it in parity for nothing. Now that `RunGap`
 * puts the reference on `data-rule-ref` instead of on screen, it is metadata,
 * so it lives with the code that uses it.
 *
 * They stay because the original argument for showing them was right — a reader
 * should be able to check that the screen is waiting for the RIGHT thing rather
 * than taking its sentence on trust. Only the audience changed: support and
 * engineers read the DOM attribute; the billing clerk reads the sentence.
 */
export const RUN_GAP_RULES = {
  step1: "Rules BR-BIL-024 · BR-BIL-025",
  step2: "Story US-BIL-002 · GET /billing/runs/{id}/findings",
  step3: "Story US-BIL-003 · GET /billing/runs/{id}/exceptions",
  step4Batch: "Rules BR-BIL-051 · BR-BIL-052 · open item TD-17",
  foundUnserved: "Story US-BIL-002 · rules BR-BIL-001 · BR-PAY-010 · BR-BIL-029",
  caseNoRecord: "Rule BR-BIL-015 · column bill_run_decisions.case",
  analysisGap:
    "CR-038 W8 · rules BR-MET-121 · BR-MET-022/056 — a metering seam the read analysis could not reach",
  // ⚠ THIS READ "returned by the calculation, not stored" UNTIL 2026-08-30, and
  // it was true until billing migration 0026 gave the breaks a table. The rule
  // reference now names the route that serves them (hard-won law 1: a stale
  // absence-claim misleads exactly as much as a stale guarantee).
  breaks: "Rules BR-BIL-053 · BR-BIL-055 — GET /billing/runs/{id}/breaks, stored in bill_run_breaks",
  overcharge: "Rules BR-BIL-029 · BR-BIL-054",
  powers: "Rule BR-BIL-023 — the draft actions are contracted and unbuilt",
  send: "Rule BR-BIL-016 · queued, not dispatched — e-mail activation is a later release",
  pricingShadow:
    "Story US-BIL-002 · GET /billing/runs/{id}/pricing-shadow — step 3 of the R1–R7 cutover",
} as const;

/**
 * A panel naming a surface the wizard cannot serve, and WHY.
 *
 * ⚠ **`ruleRef` NO LONGER RENDERS AS TEXT (CR-016, 2026-08-19).** This component
 * used to print it as a third paragraph, so a billing clerk read lines like
 * *"Rule BR-BIL-015 · column bill_run_decisions.case"* and *"Story US-BIL-002 ·
 * GET /billing/runs/{id}/findings"* — a database column name and an HTTP route,
 * on the screen of a utility with one or two staff. The Product Owner
 * photographed exactly this: *"you should follow screen that is given - you are
 * adding your own content and details on screen/Ui - too much problem"*.
 *
 * The original reason for printing it was sound — *"so a reader can go and check
 * that the screen is waiting for the right thing rather than taking the sentence
 * on trust"* — and it survives, because the reference is still on the element as
 * `data-rule-ref`. Support and any engineer can read it off the DOM in one
 * click; the clerk reading the panel cannot. The honest sentence in `message`,
 * which is the half that tells a user what they can and cannot do, is untouched.
 */
/**
 * ⚖️ **CLOSED BY DEFAULT — PO ruling 2026-08-31, said four times while working
 * the deployed product: *"too much content"*, *"descriptions are not following
 * rules"*, *"too much desciptions"*, *"too much content - desctiption is too
 * much for clark to read"*.**
 *
 * This panel is how this repo obeys hard-won law 1 on a screen: a thing the
 * product cannot do yet is SAID, never left to look like good news. That rule
 * is right and is not being weakened here — **what was missing was a budget.**
 * Every gap earned a titled panel with a paragraph in it, they accumulated per
 * screen, and step 5 of the bill run ended up with nine explanatory paragraphs
 * and two of these panels around five checkboxes and four figures.
 *
 * A clerk running bills is not reading; they are working down a screen. So the
 * SENTENCE stays, in full, and stops occupying the work surface: the title is
 * a one-line summary they can open. Nothing is deleted, nothing is hidden from
 * anyone who wants it, and the screen is a screen again.
 *
 * ⚠ **THE TITLE MUST STILL SAY THERE IS A GAP** — it is the only thing visible
 * when closed. A title that reads as decoration puts us back where law 1
 * started, with an absence that looks like nothing at all.
 */
export function RunGap(props: { title: string; message: string; ruleRef: string }) {
  return (
    <details className="my-3 border border-dashed border-[color-mix(in_srgb,var(--color-text)_30%,transparent)] bg-[color-mix(in_srgb,var(--color-text)_3%,transparent)] p-3" data-brun="gap" data-rule-ref={props.ruleRef}>
      {/* CR-018 Route B: `.brun-gap h3` and `.brun-gap p` were descendant
          rules. They are written ON the elements rather than as `[&_h3]:` /
          `[&_p]:` variants on purpose — a descendant variant is (0,1,1) and
          would out-specify anything a child ever needs to override, which is
          exactly why the deleted `.brun-gap-rule` had to carry `!important`. */}
      <summary className="m-0 cursor-pointer font-heading text-md">{props.title}</summary>
      <p className="m-0 mt-1 max-w-measure text-base text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]" role="note">
        {props.message}
      </p>
    </details>
  );
}

/** A section head inside a step — the prototype's `.kicker` above a block. */
/**
 * `required` marks the GROUP the way `FieldLabel` marks a single field
 * (BR-SHL-017 — a required input is visibly marked, accent asterisk until
 * design ratifies a convention).
 *
 * ⚠ **AN UNMARKED REQUIRED GROUP IS HOW DEF-178 LOOKED TO A CLERK.** Step 1's
 * service picker is required — `scopeProblems` refuses a run scoped to no
 * service, because such a run bills nobody — yet it rendered with no marker, no
 * ticked default, and a hint ("a service left unticked is a choice this run
 * records") that reads as *optional*. Every field carrying a `*` was filled,
 * the button was enabled, and the run would not start. A group whose absence
 * blocks the primary action is a required field and says so.
 */
export function RunSection(props: {
  kicker: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <section className="my-4" data-brun="section">
      <Kicker>
        {props.kicker}
        {props.required === true && (
          <span className="field-required" aria-hidden="true">
            *
          </span>
        )}
      </Kicker>
      {props.hint !== undefined && <p className="m-0 mb-3 max-w-measure text-base text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">{props.hint}</p>}
      {props.children}
    </section>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-001@990725e (sha1[:7] of the three sources this packet was authored from, concatenated in order: 04-docs/05-modules/07-billing/06-epics/EP-BIL-01-bill-run.md — the §Phase map + US-BIL-001..005 — · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-050..063 · 08-qa/01-e2e/journeys/J24-five-phase-bill-run.md; so a later change to any of them makes this stamp findable as stale in one grep. Co-packets: US-BIL-002/003/004/005, same three sources)
// generated: 2026-08-11 by story-coder (W3 billing FRONTEND lane — S31, the screen the run engine landed without)
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — every /billing/runs path is contracted in 11b §2.8 and unserved; 06-backend is another lane's) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report
// [run-API lane 2026-08-11] AMENDED: `FINDING_TAB_BY_REASON` DELETED — fourteen reason codes that duplicated `runs.STAGE_BY_REASON`, replaced by `FINDING_TAB_BY_STAGE` (three entries) now that `runs.AccountProblem` carries the stage the server computed. The duplicate was REPORTED by this file when it was written; the backend closed it the same day. Consequence worth naming: two reasons move tab — `account_has_no_unit` and `tenant_currency_unresolved` go Consumers → Plans, because the server says stage 1 and BR-BIL-040 puts a stage-1 finding where the Plans inputs live. The previous placement was hand-made here and disagreed with the pipeline.
// [CR-029 RC-W3c 2026-08-23] AMENDED for **D9**: `RunScopeForm` gains `dueDays` (a STRING — see its own docstring: `number | null` cannot tell a typed `0` from an untouched field, and `0` means due on the bill date), plus `dueDaysProblem`, `dueDaysValue` and `prefillFromCycle`. The module's stated refusal *"it never reads a clock"* is UNCHANGED — `prefillFromCycle` copies dates the SERVER computed and derives none.
// exceptions: E3 nothing here decides whether a break may be retried — `NOT_RETRYABLE_HERE` is the backend's and travels per row · E3 nothing here sums money or counts; a partial selection reports NO total rather than a computed one · E3 `CASES_WITHOUT_A_RECORD` names the three prototype categories that map to no `DECISION_CASES` value instead of minting a case · E3 `prefillFromCycle` reads `cycle.next_period` and NEVER derives a window from `start_day`+`days_to_complete`: that derivation on a month-end cycle is OQ-339, and a cycle the period engine declined to propose for prefills nothing
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────


// ── The pricing comparison (S31.2 · step 3 of the R1–R7 cutover) ───────────
//
// The decision log, 2026-08-27: *"The run already has a stage that shows every
// input before anything commits, and BR-BIL-039 makes the preview and the real
// run the same code. That is where a disagreement belongs."* This is that
// panel, and every rule below is a ruling rather than a preference.

/**
 * The status of ONE account, as a pill a person can read.
 *
 * ⚠ **THERE ARE THREE OUTCOMES AND NOT TWO, AND THE THIRD IS THE EASY ONE TO
 * LOSE.** Agreed · Disagreed · **Could not be checked.** An account the adapter
 * could not assemble inputs for is a missing FACT, not agreement, so it never
 * renders in the same tone as agreement and never disappears into a total.
 */
export const SHADOW_STATUS_TONE: Readonly<Record<string, "success" | "warning" | "danger">> = {
  agreed: "success",
  disagreed: "danger",
  chain_refused: "danger",
  not_attempted: "warning",
};

/**
 * The refusal on one shadow row, IN THE CLERK'S WORDS — `DEF-RAT-7991`.
 *
 * `row.refusal_sentence` is the rating chain's own message and nine of its
 * raise sites interpolate a database uuid into it; it was rendered raw on this
 * screen. `refusalSentence` prefers the server's clerk key, falls back to a
 * uuid-free sentence, and refuses one that is not (B14 rule 31).
 */
function refusalOnRow(row: PricingShadowAccount, t: Translator): string | null {
  return refusalSentence(
    {
      message_key: row.refusal_message_key ?? null,
      message_params: row.refusal_message_params ?? null,
      detail: row.refusal_clerk_detail ?? row.refusal_sentence ?? null,
    },
    t,
  );
}

export function shadowStatusTone(status: string): "success" | "warning" | "danger" {
  return SHADOW_STATUS_TONE[status] ?? "warning";
}

/**
 * status -> the words on screen, as QUOTED LITERALS.
 *
 * Written as a map rather than as a template key for the reason DEF-049 records:
 * a key nothing names in code reads as dead to G18 and is translated eleven
 * times for nothing. It is also G44's rule — a dynamically built key cannot be
 * checked against the catalogue by anything.
 */
export const SHADOW_STATUS_KEYS: Readonly<Record<string, string>> = {
  agreed: "billing.run.shadow.status.agreed",
  disagreed: "billing.run.shadow.status.disagreed",
  chain_refused: "billing.run.shadow.status.chainRefused",
  not_attempted: "billing.run.shadow.status.notAttempted",
};

/**
 * blocked reason -> the words on screen. Same rule as the statuses above.
 *
 * ⚠ **A REASON WITH NO ENTRY RENDERS THE SERVER'S OWN CODE, NOT A BLANK.** The
 * server is the authority on why an account could not be checked, and a new
 * reason arriving before this map knows about it must still say something true.
 */
export const SHADOW_REASON_KEYS: Readonly<Record<string, string>> = {
  connection_size_unresolved: "billing.run.shadow.reason.connectionSize",
  meter_multiplier_not_published_to_billing: "billing.run.shadow.reason.multiplier",
  unmetered_asset_count_not_published_to_billing: "billing.run.shadow.reason.assetCount",
  account_has_no_plan: "billing.run.shadow.reason.noPlan",
  shadow_account_row_unavailable: "billing.run.shadow.reason.rowUnavailable",
  shadow_comparison_raised: "billing.run.shadow.reason.comparisonRaised",
};

export function shadowStatusLabel(status: string, t: Translator): string {
  const key = SHADOW_STATUS_KEYS[status];
  return key === undefined ? status : t(key);
}

export function shadowReasonLabel(reason: string, t: Translator): string {
  const key = SHADOW_REASON_KEYS[reason];
  return key === undefined ? reason : t(key);
}

/**
 * TRUE only when this body really is a pricing comparison.
 *
 * ⚠ **A PANEL THAT CANNOT READ ITS BODY RENDERS NOTHING — IT DOES NOT RENDER
 * ZEROS (`DEF-2402`).** A server that predates this endpoint answers the
 * generic empty-list envelope, and the first version of this component read
 * `accounts_detail.filter(...)` straight off it and threw — taking down the
 * WHOLE of "Check what we found", which is the stage a clerk cannot bill
 * without. That is precisely the failure the separate endpoint exists to
 * prevent, arriving through the rendering instead of the request.
 *
 * ⚠ **AND THE DEFAULT MUST NOT BE ZERO.** Coercing the missing counts to 0
 * would print *"We worked out 0 of 0 customers both ways. 0 came out
 * differently."* over a server that never answered — the exact reading the
 * decision log says to distrust, manufactured by the client. Absent is absent.
 */
export function isPricingShadow(body: unknown): body is BillRunPricingShadow {
  if (body === null || typeof body !== "object") return false;
  const row = body as Record<string, unknown>;
  return (
    typeof row.accounts === "number" &&
    typeof row.attempted === "number" &&
    typeof row.disagreed === "number" &&
    typeof row.not_attempted === "number"
  );
}

/**
 * Accounts worth listing one by one: everything that is not plain agreement.
 *
 * An agreed account has nothing for a person to do, and printing 1,200 of them
 * would bury the ones that do. The COUNT of them is still on screen in the
 * sentence above the table, so nothing is hidden — only un-listed.
 */
export function shadowAccountsToList(
  shadow: BillRunPricingShadow,
): PricingShadowAccount[] {
  return (shadow.accounts_detail ?? []).filter((row) => row.status !== "agreed");
}

/**
 * TRUE when the panel's headline number would read as good news and is not.
 *
 * ⚠ **THIS IS THE WHOLE REASON THE COMPONENT EXISTS IN THIS SHAPE.** The
 * decision log: *"READ THE THIRD AND FOURTH NUMBERS TOGETHER OR THEY LIE. '0
 * disagreed' is also what perfect agreement looks like… a count that is always
 * zero means the chain is not running, and nothing else would say so."* So when
 * nothing was attempted, the screen says so in its own sentence instead of
 * printing a zero that reads as a clean bill of health.
 */
export function shadowMeasuredNothing(shadow: BillRunPricingShadow): boolean {
  return shadow.attempted === 0;
}

/**
 * One side of a disagreement, as it is printed.
 *
 * The SERVER's display string when it sent one (BR-RAT-087 — the client never
 * formats money), the stored figure otherwise, and a named absence when the
 * ruled path produced no figure at all. A refusal has no pair of numbers: that
 * ABSENCE is the finding, and printing 0.00 there would state something false.
 */
export function shadowFigure(
  value: string | null,
  display: string | null,
): string | null {
  if (display !== null) {
    return display;
  }
  return value;
}

/** The comparison panel S31.2 draws before anything commits. */
export function PricingShadowPanel(props: {
  t: Translator;
  shadow: BillRunPricingShadow;
  /** Record links (PO 2026-10-19): where an account number opens (new tab). */
  accountHref?: (accountId: string) => string;
}) {
  const { t, shadow } = props;
  // DEF-2402 — an unreadable body is an ABSENCE, never a row of zeros.
  if (!isPricingShadow(shadow)) return null;
  const listed = shadowAccountsToList(shadow);
  const classes = shadow.classes ?? [];
  const blocked = shadow.blocked_classes ?? [];
  return (
    <RunSection
      kicker={t("billing.run.shadow.kicker")}
      hint={t("billing.run.shadow.hint")}
    >
      {/* ⚠ ONE SENTENCE, FOUR NUMBERS, AND THEY CANNOT BE SEPARATED. The
          attempted count is inside the same string as the disagreement count,
          so no future edit can leave one on screen without the other. */}
      <p className="m-0 mb-2 max-w-measure text-base" data-brun="shadow-counts">
        {t("billing.run.shadow.counts", {
          attempted: shadow.attempted,
          accounts: shadow.accounts,
          disagreed: shadow.disagreed,
          notAttempted: shadow.not_attempted,
        })}
      </p>
      {shadowMeasuredNothing(shadow) && (
        <p
          className="m-0 mb-2 max-w-measure text-base text-warning-700"
          data-brun="shadow-nothing"
          role="note"
        >
          {t("billing.run.shadow.measuredNothing")}
        </p>
      )}

      {classes.length === 0 ? (
        <p className="m-0 mb-2 max-w-measure text-base" data-brun="shadow-none">
          {t("billing.run.shadow.noneFound")}
        </p>
      ) : (
        <>
          <h3 className="m-0 mb-1 font-heading text-md">
            {t("billing.run.shadow.classesHeading")}
          </h3>
          <div className="overflow-x-auto">
            <PlainTable>
              <thead>
                <tr>
                  <th>{t("billing.run.shadow.col.what")}</th>
                  <th>{t("billing.run.shadow.col.step")}</th>
                  <th>{t("billing.run.shadow.col.accounts")}</th>
                  <th>{t("billing.run.shadow.col.live")}</th>
                  <th>{t("billing.run.shadow.col.ruled")}</th>
                </tr>
              </thead>
              <tbody>
                {classes.map((row) => (
                  <tr key={row.class_id} data-brun="shadow-class">
                    <td>
                      <span className="block">{row.what}</span>
                      {row.example_sentence !== null && (
                        <span className="block text-xs text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                          {t("billing.run.shadow.example", {
                            account: row.example_account_no ?? "",
                            sentence: row.example_sentence,
                          })}
                        </span>
                      )}
                    </td>
                    <td>
                      {row.step}
                      {row.services.length > 0 && (
                        <span className="block text-xs text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                          {row.services
                            .map((code) =>
                              t(`rating.service.${code}`, { defaultValue: code }),
                            )
                            .join(", ")}
                        </span>
                      )}
                    </td>
                    <td data-brun="shadow-class-accounts">{row.accounts}</td>
                    {/* ⚠ BOTH FIGURES, SIDE BY SIDE, AND NEITHER CHOSEN. No
                        difference is computed and no preference is shown: which
                        one is right is the Product Owner's ruling and not this
                        screen's. */}
                    {/* ⚠ THE TWO CELLS CARRY `data-brun` MARKERS SO A TEST CAN
                        ASSERT ON THEM AND NOT ON THE PAGE. A page-wide search
                        for "18.50" also matches the example SENTENCE two cells
                        to the left, so a panel that had dropped this column
                        entirely would still pass one — which is the caution the
                        decision log records verbatim: "assert against the
                        row's own element, never text that also appears in the
                        page's furniture." It was written for a column heading;
                        it applies just as exactly to a sibling cell. */}
                    <td data-brun="shadow-live">
                      {shadowFigure(row.example_live, row.example_live_display) ??
                        row.example_live_summary ?? <Dash>{t("billing.run.shadow.noFigure")}</Dash>}
                    </td>
                    <td data-brun="shadow-ruled">
                      {shadowFigure(row.example_chain, row.example_chain_display) ?? (
                        <Dash>{t("billing.run.shadow.noFigure")}</Dash>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
          </div>
        </>
      )}

      {/* ⚠ COULD-NOT-ASK IS ITS OWN TABLE, NEVER A ROW IN THE ONE ABOVE. An
          account nobody could check has not agreed with anything. */}
      {blocked.length > 0 && (
        <>
          <h3 className="m-0 mb-1 mt-3 font-heading text-md">
            {t("billing.run.shadow.blockedHeading")}
          </h3>
          <div className="overflow-x-auto">
            <PlainTable>
              <thead>
                <tr>
                  <th>{t("billing.run.shadow.col.reason")}</th>
                  <th>{t("billing.run.shadow.col.accounts")}</th>
                  <th>{t("billing.run.shadow.col.detail")}</th>
                </tr>
              </thead>
              <tbody>
                {blocked.map((row) => (
                  <tr key={row.reason} data-brun="shadow-blocked">
                    <td>
                      {shadowReasonLabel(row.reason, t)}
                    </td>
                    <td>{row.accounts}</td>
                    <td>{row.example_detail ?? <Dash>{t("billing.run.shadow.noDetail")}</Dash>}</td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
          </div>
        </>
      )}

      {listed.length > 0 && (
        <>
          <h3 className="m-0 mb-1 mt-3 font-heading text-md">
            {t("billing.run.shadow.accountsHeading")}
          </h3>
          <div className="overflow-x-auto">
            <PlainTable>
              <thead>
                <tr>
                  <th>{t("billing.run.shadow.col.account")}</th>
                  <th>{t("billing.run.shadow.col.outcome")}</th>
                  <th>{t("billing.run.shadow.col.what")}</th>
                </tr>
              </thead>
              <tbody>
                {listed.map((row) => (
                  <tr key={row.account_id} data-brun="shadow-account">
                    <td>
                      {props.accountHref !== undefined && row.account_id ? (
                        <a href={props.accountHref(row.account_id)} target="_blank" rel="noreferrer" className="text-accent-700 underline">
                          {row.account_no}
                        </a>
                      ) : (
                        row.account_no
                      )}
                    </td>
                    <td>
                      <StatusPill tone={shadowStatusTone(row.status)}>
                        {shadowStatusLabel(row.status, t)}
                      </StatusPill>
                    </td>
                    <td>
                      {/* The chain's own refusal, IN THE CLERK'S WORDS.
                          ⚠ `row.refusal_sentence` printed RAW here until
                          `DEF-RAT-7991` (2026-09-29) and carried up to four
                          database uuids onto this screen — B14 rule 31. The
                          sentence is still SHOWN (rendering the exception
                          class name instead is named in the decision log as
                          "the lazy way to make the first test pass"); it is
                          the server's clerk sentence that is shown now, and
                          `refusalSentence` refuses a uuid-bearing fallback. */}
                      {refusalOnRow(row, t) !== null && (
                        <span className="block">{refusalOnRow(row, t)}</span>
                      )}
                      {row.blocked_detail !== null && (
                        <span className="block">{row.blocked_detail}</span>
                      )}
                      {row.status === "chain_refused" && row.live_summary !== null && (
                        <span className="block text-xs text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                          {t("billing.run.shadow.liveResolved", { summary: row.live_summary })}
                        </span>
                      )}
                      {row.divergences.map((one) => (
                        <span className="block" key={`${one.step}-${one.service ?? ""}`}>
                          {one.sentence}
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
          </div>
        </>
      )}
    </RunSection>
  );
}
