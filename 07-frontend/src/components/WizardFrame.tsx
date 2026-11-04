// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-010 (EP-SHL-03 §Stories)  Screens: S10, S18, S23, S28, S31, S38, S110–S114 (every guided flow)
// Rules:    BR-SHL-018 (rail semantics) · BR-SHL-019 (commit semantics)
// ───────────────────────────────────────────────────────
// FE-06 WizardFrame (B13 §1): the shared wizard frame — numbered clickable
// step rail (.br-steps), Back/Continue action row, final ✓ confirm with the
// A18 §3 working state, single-flight transactional commit, A18 §4 failure
// with entered state preserved. The frame owns navigation/validation
// ORCHESTRATION only; each consuming wizard declares its steps, per-step
// validation (rendering its own US-SHL-009 inline errors), and commit handler
// — its actual fields/writes belong to the consuming module (EP-SHL-03 scope).
// Wizard data lives in the CONSUMER's state above this frame, so values are
// retained when jumping back and returning forward (BR-SHL-018). The step
// number is URL state (`?step=`, A9): pass `nav`/`onNavChange` and serialize
// in the consumer, restoring through clampStepToReached — same controlled
// pattern as DataTable's request state.
import { useRef, useState, useSyncExternalStore } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { FailedWithRetry, WorkingButton } from "./StateFrame";
import type { CommitTier } from "./StateFrame";

import { Button } from "@/components/Button";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DatePickerField, SelectField, TextField } from "@/components/FormModal";
import { useLeaveGuard } from "@/components/LeaveGuard";
import type { LeaveDraft } from "@/components/LeaveGuard";

const noop = () => undefined;

// ── Rail navigation state (pure, testable without a browser) ───────────────

export interface WizardNavState {
  step: number; // 1-based current step
  reached: number; // highest step ever validated into — the forward fence
}

export function initialWizardNav(): WizardNavState {
  return { step: 1, reached: 1 };
}

// BR-SHL-018: a URL-restored `?step=` clamps to the highest validated step —
// a pasted deep link can never skip past unvisited steps (US-SHL-010 §5).
export function clampStepToReached(
  requested: number,
  nav: WizardNavState,
  stepCount: number,
): WizardNavState {
  const sane = Number.isFinite(requested) ? Math.trunc(requested) : 1;
  const step = Math.max(1, Math.min(sane, stepCount, nav.reached));
  return step === nav.step ? nav : { ...nav, step };
}

// BR-SHL-018: completed steps are clickable to jump BACK; forward clicks are a
// no-op (blocked transitions return the SAME object, so callers can ===).
export function jumpBackTo(nav: WizardNavState, target: number): WizardNavState {
  if (target >= 1 && target < nav.step) {
    return { ...nav, step: target };
  }
  return nav;
}

export function backOne(nav: WizardNavState): WizardNavState {
  return jumpBackTo(nav, nav.step - 1);
}

// BR-SHL-018: forward movement only via Continue AFTER the current step
// validates — an invalid step stays put (US-SHL-010 TC-3).
export function continueFrom(
  nav: WizardNavState,
  stepCount: number,
  valid: boolean,
): WizardNavState {
  if (!valid || nav.step >= stepCount) {
    return nav;
  }
  const step = nav.step + 1;
  return { step, reached: Math.max(nav.reached, step) };
}

// ── Commit controller (framework-free, like the Toast queue) ───────────────
// BR-SHL-019: ONE transactional commit call, single-flight, failure kept as
// state so the frame can render A18 §4 with everything the user entered still
// on screen. Plain object + listeners so its laws are testable without a
// browser (B8 LAW 0: boring and explicit).

export interface WizardCommitPartial {
  imported: number;
  needReview: number;
  failed: number;
}

export type WizardCommitOutcome =
  | { ok: true }
  // reason is PLAIN LANGUAGE (BR-SHL-020) — the consumer maps its error
  // envelope/message_key to copy before it gets here.
  | { ok: false; reason: string; partial?: WizardCommitPartial; refusedOnStep?: number };

export interface WizardCommitFailure {
  reason: string;
  partial?: WizardCommitPartial;
}

export interface WizardCommitState {
  working: boolean;
  failure: WizardCommitFailure | null;
}

export interface WizardCommitController {
  // Returns null when a commit is already in flight (the duplicate click is
  // ignored — BR-SHL-019 single-flight, US-SHL-010 TC-5).
  run: (commit: () => Promise<WizardCommitOutcome>) => Promise<WizardCommitOutcome | null>;
  dismissFailure: () => void;
  getState: () => WizardCommitState;
  subscribe: (listener: () => void) => () => void;
}

export function createWizardCommitController(unexpectedReason: string): WizardCommitController {
  let state: WizardCommitState = { working: false, failure: null };
  const listeners = new Set<() => void>();

  function setState(next: WizardCommitState): void {
    state = next;
    for (const listener of listeners) {
      listener();
    }
  }

  return {
    run: async (commit) => {
      if (state.working) {
        return null; // BR-SHL-019: exactly one commit request in flight
      }
      setState({ working: true, failure: null });
      let outcome: WizardCommitOutcome;
      try {
        outcome = await commit();
      } catch {
        // A thrown commit (network drop) still fails in plain language —
        // never a silent hang or a raw error (BR-SHL-020).
        outcome = { ok: false, reason: unexpectedReason };
      }
      // ⛔ **A REFUSAL THE CONSUMER HAS ROUTED TO A STEP DOES NOT TAKE THE
      // FOOTER — `DEF-MET-6110`/`DEF-MET-6111`, PO ruling 2026-09-21: *"you
      // ahve to show the error at step you mentioned"*.**
      //
      // `FailedWithRetry` below REPLACES the whole action row, which is right
      // for a commit that failed on the review step and wrong for a rule the
      // clerk can fix four steps back: it leaves them on the owning step with
      // no `Continue` and no `Back`, so correcting one field costs a `Cancel`
      // first. A consumer that names `refusedOnStep` has already put the clerk
      // on that step and renders the sentence there, beside the control — so
      // the frame keeps the ordinary footer and they simply walk forward.
      //
      // ⚠ **ADDITIVE, AND EVERY OTHER WIZARD IS UNTOUCHED.** The field is
      // optional and no other consumer sets it, so all of them still take the
      // failure card exactly as before.
      const routed = !outcome.ok && outcome.refusedOnStep !== undefined;
      setState({
        working: false,
        failure:
          outcome.ok || routed ? null : { reason: outcome.reason, partial: outcome.partial },
      });
      return outcome;
    },
    dismissFailure: () => setState({ working: false, failure: null }),
    getState: () => state,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

// ── Park & resume (CR-030 W5 task 5.1) ─────────────────────────────────────
//
// PO, verbatim (B18 §4.2): *"many times it is not necessary that workflos will
// complete in 1 go - utility user will have field dependecies or oprational
// depedancies - in those cases how do you handle it - we might have to process
// from step 1 to 2 and stap there and save that much work completed"*, and the
// ruling on how: *"We will keep wizard only that way it is easy for utility
// user to undratdn"*.
//
// **So park is FOLDED INTO THE WIZARD MODEL, not layered over it as a case
// object — which is why it lives here and not in a feature.** It is written
// once on the frame, so the eleventh wizard to mount this component gets the
// two controls, the nine reasons and the step fact without asking.
//
// ⚠ **AND THE FRAME DOES NOT DECIDE WHETHER A FLOW MAY PARK.** Each consumer
// passes `parkBlockedReason`: null lets the control act, a sentence renders it
// DISABLED carrying that sentence (BR-SHL-025 — there is no boolean, so a
// consumer cannot disable it without saying why).
//
// ✅ **BR-SHL-047 (PO 2026-08-24, closing DEF-649, verbatim *"Park it"*): EVERY
// wizard parks, move-out included** — the same nine reasons, note and remind-on
// date the service request already has. So no flow refuses a park by design any
// more; what a flow may still say is that it has nowhere to RECORD one, which is
// a fact about that flow's storage and not about this frame.

/**
 * B18 §4.2's NINE, verbatim and in its order. A CLOSED vocabulary: the
 * `WAITING ON` column on the Move-ins / Move-outs / Requests tabs holds one of
 * these in plain words, so a tenth typed by a clerk would be a column value
 * nothing can filter, count or age.
 */
export const WIZARD_PARK_REASONS = [
  "customer",
  "documents",
  "deposit",
  "payment",
  "inspection",
  "permit",
  "materials",
  "site_access",
  "third_party",
] as const;

export type WizardParkReason = (typeof WIZARD_PARK_REASONS)[number];

/**
 * The nine in the catalogue, written as LITERAL keys rather than assembled
 * from the code above. A template key (`wizard.park.reason.${code}`) renders
 * perfectly and is invisible to G18, which reads literal dotted strings — so
 * all nine would report as dead catalogue entries the day they are translated.
 */
export const WIZARD_PARK_REASON_COPY: { code: WizardParkReason; key: string; en: string }[] = [
  { code: "customer", key: "wizard.park.reason.customer", en: "waiting on the customer" },
  { code: "documents", key: "wizard.park.reason.documents", en: "waiting on documents" },
  { code: "deposit", key: "wizard.park.reason.deposit", en: "waiting on a deposit" },
  { code: "payment", key: "wizard.park.reason.payment", en: "waiting on a payment" },
  { code: "inspection", key: "wizard.park.reason.inspection", en: "waiting on inspection" },
  { code: "permit", key: "wizard.park.reason.permit", en: "waiting on a permit" },
  { code: "materials", key: "wizard.park.reason.materials", en: "waiting on materials" },
  { code: "site_access", key: "wizard.park.reason.siteAccess", en: "waiting on site access" },
  { code: "third_party", key: "wizard.park.reason.thirdParty", en: "waiting on a third party" },
];

export function isWizardParkReason(value: string): value is WizardParkReason {
  return (WIZARD_PARK_REASONS as readonly string[]).includes(value);
}

/** What a park records. B18 §4.2 asks for *"a reason from a fixed list and an
 *  optional note"*; the STEP is here because *"the row reopens the wizard at
 *  its furthest incomplete step"* and something has to carry which one. */
export interface WizardParkEntry {
  reason: WizardParkReason;
  note: string;
  /** BR-SHL-047 names it beside the nine and the note. Empty is legal — the
   *  service request's own park makes the reminder optional and this matches
   *  it rather than inventing a stricter form for the same act. */
  remindOn: string;
  step: number;
}

export interface WizardExit {
  /**
   * B19 §12.2: `Save & exit` leaves quietly and writes nothing of its own.
   *
   * ⚠ **`null` MEANS THIS WIZARD HAS NO SEPARATE `Save & exit`, AND PARK IS THE
   * ONLY WAY OUT — `CR-125-BRC07`, PO ruling 2026-09-21** (*"we need to keep
   * only park, complete - two action only"*, confirmed *"this si correct"*).
   * The disconnect wizard passes `null`; every other wizard passes its function
   * and is byte-identical to before.
   *
   * ⚠ **IT IS `| null` AND NOT OPTIONAL, DELIBERATELY.** Optional would mean a
   * wizard that FORGOT this key silently loses its way out — hard-won law 2's
   * dead-UI shape, arrived at by omission. Required-but-nullable makes every
   * caller state which of the two it is, so the day a sixth wizard lands the
   * compiler asks the question rather than picking an answer.
   */
  onSaveAndExit: (() => void) | null;
  /** BR-SHL-025 — null lets Park act; a sentence disables it CARRYING that
   *  sentence. Not a boolean, deliberately. */
  parkBlockedReason: string | null;
  /** URL state, exactly like `?step=` (A9): a half-filled park survives a
   *  reload, and a consumer that serialises it gets a linkable one. */
  parkOpen: boolean;
  onParkOpenChange: (open: boolean) => void;
  onPark: (entry: WizardParkEntry) => Promise<WizardCommitOutcome>;
  /** The tenant's format — the remind-on field is a date and BR-SHL-033 says a
   *  date uses the date control, which needs one. */
  dateFormat: RegionalDateFormat;
  /**
   * When this flow is ALREADY parked, the instant it was parked at.
   *
   * ⚠ **BR-SHL-047 LEFT ONE HALF OPEN AND THIS IS IT.** The PO settled that a
   * move-out may park; they did not settle what stops a parked one sitting
   * forever, **and a parked move-out still holds its unit**. So the AGE is
   * built and rendered, and no limit is invented — a wizard that refused to
   * park after N days would be enforcing a rule nobody made.
   */
  parkedAt: string | null;
}

// ⚠ FOUR `max-w-prose` LANDED HERE AFTER CR-041 CLEANED THIS FILE, directly
// under the comment above saying not to (merge, 2026-08-27). G43's rule-18
// ratchet caught them: 54 live against a baseline of 50, and the whole delta
// was this one const. `max-w-prose` is a real Tailwind utility and the WRONG
// cap — 65ch — where B14 rule 18 ratifies 80%, which is what `max-w-measure`
// is. The baseline stays at 50 rather than being raised to absorb them:
// a ratchet that moves to fit whatever arrived is not a ratchet.
const EXIT = {
  group: "mr-auto flex flex-wrap items-center gap-2",
  panel: "mt-6 border border-divider bg-surface p-4",
  title: "font-heading text-base font-semibold text-text",
  note: "mt-1 max-w-measure text-sm text-neutral-700",
  fields: "mt-3 flex flex-col gap-3",
  panelActions: "mt-4 flex flex-wrap justify-end gap-2",
  failure: "mt-2 max-w-measure text-sm text-danger-500",
  blocked: "max-w-measure text-sm text-neutral-700",
  age: "max-w-measure text-sm font-semibold text-accent-text",
} as const;

/**
 * How long a parked flow has been sitting, in whole days.
 *
 * ⚠ **BR-SHL-047 SETTLED THAT A MOVE-OUT MAY PARK AND LEFT THE COST OPEN:** a
 * parked move-out STILL HOLDS ITS UNIT, so the next occupant cannot be moved in
 * behind it, and nothing was ruled about what stops one sitting forever. The
 * rule row asks for the visible AGE and explicitly not for a limit — so this
 * counts days and refuses nothing.
 *
 * Whole days off the UTC instants: a local getter meeting a date-only string is
 * exactly how an off-by-one day is born.
 */
export function parkAgeDays(parkedAt: string | null, now: Date): number | null {
  if (parkedAt === null || parkedAt === "") {
    return null;
  }
  const parked = Date.parse(parkedAt);
  if (Number.isNaN(parked)) {
    return null;
  }
  const days = Math.floor((now.getTime() - parked) / 86_400_000);
  return days < 0 ? 0 : days;
}

/**
 * The two controls — **BUTTONS ONLY (DEF-1083).**
 *
 * This used to render the park AGE and the park REFUSAL inline beside the
 * buttons, the refusal wrapped in a `flex-col` span so it sat under its own
 * control. Both are prose, both are taller than a button, and both were flex
 * items in the footer's one row — so the row stopped being a row. What renders
 * where is now split: the buttons are here, the sentences are `WizardExitNote`
 * below, on the frame's declared `exitNote` line.
 */
function WizardExitControls(props: { exit: WizardExit; working: boolean }) {
  const { t } = useTranslation();
  const blocked = props.exit.parkBlockedReason;
  return (
    <div className={EXIT.group} data-wizard="exit">
      {/* ⚠ **ABSENT WHEN `onSaveAndExit` IS `null` — `CR-125-BRC07`.** The
          disconnect wizard keeps two actions, Park and Complete, and
          `Save & exit` MERGED INTO PARK: they were two names for one act. This
          is the only place that decision renders, so a wizard that wants both
          still gets both and nothing else in this file changed. */}
      {props.exit.onSaveAndExit !== null && (
        <Button variant="secondary" disabled={props.working} onClick={props.exit.onSaveAndExit}>
          {t("wizard.exit.saveAndExit", { defaultValue: "Save & exit" })}
        </Button>
      )}
      {blocked === null ? (
        <Button
          variant="secondary"
          disabled={props.working}
          onClick={() => props.exit.onParkOpenChange(true)}
        >
          {t("wizard.exit.park", { defaultValue: "Park" })}
        </Button>
      ) : (
        // BR-SHL-025: disabled, and the reason is READABLE — a `title` is a
        // mouse, and a keyboard or touch user would get nothing from one. The
        // reason renders on the note line below; `aria-describedby` is what ties
        // the two together now that they are no longer siblings.
        <Button variant="secondary" disabled title={blocked} aria-describedby={EXIT_NOTE_ID}>
          {t("wizard.exit.park", { defaultValue: "Park" })}
        </Button>
      )}
    </div>
  );
}

/** The id the disabled Park points at, so the split does not cost a screen
 *  reader the reason the sighted user can see. */
const EXIT_NOTE_ID = "wizard-exit-note";

/**
 * The footer's prose, on its own line beneath the buttons (DEF-1083).
 *
 * Two sentences can appear, and they answer different questions, so both are
 * kept and neither is merged:
 *
 *  · the park AGE — how long a parked flow has been sitting. It is drawn WITH
 *    the control rather than only on the list, because the person who can end
 *    the wait is the one looking at this.
 *
 *    ⛔ **A NEW KEY, AND THE OLD ONE IS RETIRED (CR-035).** ✅ RETIREMENT DONE —
 *    verified 2026-08-26 across all eleven catalogues: `wizard.park.age` is
 *    defined in NONE of them and has no call site anywhere in `src/`. The old
 *    default read *"Parked {{days}} days — the unit is still held"* and became
 *    FALSE on 2026-08-26: BR-SHL-048 (c) settles BR-SHL-047's open half the
 *    other way — *"Under this ruling it holds nothing, because nothing is
 *    written — so no parked wizard can ever block anything."* A catalogue entry
 *    BEATS a `defaultValue`, so rewriting the default under the old key would
 *    have left every clerk reading the superseded claim with a green suite.
 *    ⚠ AND THE REPLACEMENT SAYS THE COST, NOT JUST THE CORRECTION: the ruling
 *    accepts in writing that *"a parked move-out is invisible, so that account
 *    KEEPS BILLING"*, so the age is the whole of the mitigation and a sentence
 *    that only said "nothing is held" would read as reassurance.
 *
 *  · the park REFUSAL — why the control beside it is disabled (BR-SHL-025).
 */
function WizardExitNote(props: { exit: WizardExit }) {
  const { t } = useTranslation();
  const blocked = props.exit.parkBlockedReason;
  const age = parkAgeDays(props.exit.parkedAt, new Date());
  if (age === null && blocked === null) {
    return null;
  }
  return (
    <p className={WIZ.exitNote} id={EXIT_NOTE_ID} data-wizard="exit-note" role="note">
      {age !== null && (
        <span className="font-semibold text-accent-text" data-wizard="park-age">
          {t("wizard.park.ageDraft", {
            days: age,
            defaultValue: "Waiting {{days}} days — nothing is held or changed until you finish this",
          })}
        </span>
      )}
      {age !== null && blocked !== null && " · "}
      {blocked !== null && <span data-wizard="park-blocked">{blocked}</span>}
    </p>
  );
}

/**
 * The park panel. INLINE rather than a modal, and that is a decision: its
 * openness is the consumer's URL state, so a clerk who reloads mid-park still
 * has the form — and a modal would have hidden the step content the reason is
 * being written about.
 */
function WizardParkPanel(props: { exit: WizardExit; step: number; stepCount: number }) {
  const { t } = useTranslation();
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [remindOn, setRemindOn] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  async function submit(): Promise<void> {
    if (!isWizardParkReason(reason)) {
      setProblem(
        t("wizard.park.reasonRequired", {
          defaultValue: "Choose what this is waiting on before parking it.",
        }),
      );
      return;
    }
    setWorking(true);
    const outcome = await props.exit.onPark({
      reason,
      note: note.trim(),
      remindOn,
      step: props.step,
    });
    setWorking(false);
    if (outcome.ok) {
      setProblem(null);
      props.exit.onParkOpenChange(false);
      return;
    }
    setProblem(outcome.reason);
  }

  return (
    <div className={EXIT.panel} data-wizard="park">
      <h3 className={EXIT.title}>
        {t("wizard.park.title", { defaultValue: "Park this — what are you waiting for?" })}
      </h3>
      {/* ⛔ **A NEW KEY, AND `wizard.park.parkedAt` IS NOW RETIRED (CR-035).**
          ✅ **Verified 2026-08-26: it is defined in none of the eleven
          catalogues and called from nowhere in `src/`.** It used to end *"…and
          everything already entered stays on the record"* — and under
          BR-SHL-048 **there is no record**: a parked wizard is a saved FORM, the
          unit stays Vacant and no account exists. Telling a clerk their typing
          is "on the record" is telling them a move-in has begun.

          ⚠ THE STEP IS BR-SHL-046's INDEX, PASSED IN, NOT COUNTED HERE. The
          consumer hands over `stepCount` from its own declared step list, so a
          skipped step is still one of the six and a resume lands where the
          clerk stopped. */}
      <p className={EXIT.note}>
        {t("wizard.park.draftStep", {
          step: props.step,
          of: props.stepCount,
          defaultValue:
            "Parked at step {{step}} of {{of}}. Reopening this from your Waiting on list brings you back to this step with everything you have typed. Nothing is created or changed until you finish the wizard.",
        })}
      </p>
      <div className={EXIT.fields}>
        <SelectField
          id="wizard_park_reason"
          label={t("wizard.park.reason", { defaultValue: "Waiting on" })}
          required
          value={reason}
          onChange={setReason}
          placeholder={t("wizard.park.reasonPlaceholder", {
            defaultValue: "Choose what this is waiting on",
          })}
          options={WIZARD_PARK_REASON_COPY.map((row) => ({
            value: row.code,
            label: t(row.key, { defaultValue: row.en }),
          }))}
          {...(problem === null ? {} : { error: problem })}
        />
        <TextField
          id="wizard_park_note"
          label={t("wizard.park.note", { defaultValue: "Note (optional)" })}
          help={t("wizard.park.noteHelp", {
            defaultValue: "What the next person needs to know before they pick this up.",
          })}
          value={note}
          onChange={setNote}
        />
        {/* BR-SHL-047 names the remind-on date beside the reason and the note.
            BR-SHL-033: a date uses the date control, in the tenant's format. */}
        <DatePickerField
          id="wizard_park_remind_on"
          label={t("wizard.park.remindOn", { defaultValue: "Remind me on (optional)" })}
          value={remindOn}
          dateFormat={props.exit.dateFormat}
          onChange={setRemindOn}
        />
      </div>
      <div className={EXIT.panelActions}>
        <Button variant="secondary" onClick={() => props.exit.onParkOpenChange(false)}>
          {t("wizard.park.cancel", { defaultValue: "Keep working" })}
        </Button>
        <WorkingButton working={working} onClick={() => void submit()}>
          {t("wizard.park.submit", { defaultValue: "Park it" })}
        </WorkingButton>
      </div>
    </div>
  );
}

// ── The component ──────────────────────────────────────────────────────────

/**
 * ── CR-018 ROUTE B · THE FRAME IN TAILWIND (PO, 2026-08-21) ────────────────
 *
 * PO verbatim, twice this session: *"do everything using tailwind and not
 * custom CSS"*, then *"We need this as part of Tailwind - can we do it?"* about
 * this component by name. `WizardFrame.css` is DELETED and every rule it held
 * is a utility below.
 *
 * ⚠ **THE SEMANTIC CLASS NAMES BECAME `data-` ATTRIBUTES, AND THAT IS THE ONE
 * REAL DECISION HERE.** `wizard-frame`, `br-steps`, `br-step`, `.n`,
 * `wizard-step-content`, `wizard-actions` and `wizard-blocked` were doing two
 * different jobs at once: styling, and being the handle eight test files reach
 * for. Route B's own rule refuses a class token that "renders NOTHING — no
 * stylesheet declares them and Tailwind generates no rule for them", so a bare
 * `wizard-frame` left on the element after its stylesheet went would fail the
 * check by construction. Keeping a stylesheet alive just to declare names
 * nothing styles would be worse: a rule that exists to satisfy a gate.
 *
 * So the handle is now an ATTRIBUTE, which is what it always was in spirit —
 * `data-wizard="frame"`, `data-wizard-step` with `data-state`. Tests assert on
 * the attribute; the utilities carry the pixels. Nothing on screen moves: every
 * value below is the one the stylesheet held, ported one for one.
 *
 * ⚠ **THE BREAKPOINT IS `max-lg:`, NOT `lg:`.** Our scale is DESKTOP-FIRST and
 * Tailwind's own is min-width, which is exactly why `--breakpoint-*` is cleared
 * and re-declared: `--breakpoint-lg: 1024px`, so `max-lg:` IS the ported
 * `@media (max-width: 1024px)` rule (A12, US-SHL-010 TC-7) and `lg:` would
 * silently mean the opposite viewport.
 */
const WIZ = {
  frame: "flex min-w-0 flex-col gap-4",
  rail:
    "mb-6 flex border-y-2 border-divider " +
    // A12 · below 1024px the rail SCROLLS — never wraps, never overflows.
    "max-lg:flex-nowrap max-lg:overflow-x-auto",
  step:
    // ⚠ **`min-w-0` IS WHAT STOPS A LONG RAIL CLIPPING — `DEF-CUS-5198`.** A
    // flex item's `min-width` is `auto`, so a cell REFUSES to shrink below its
    // own label and the row overflows instead of wrapping. Measured in a
    // browser on 2026-09-16: the new-connect rail's content was **1236px inside
    // a 992px box at 1280** with nine cells, so 244px of *Review & confirm*
    // hung outside it; merging owner and scope took it to 1113px and it still
    // hung 121px out. `min-w-0` lets the cell shrink and the LABEL wrap, which
    // is what the blueprint draws — p086 sets *Plans & work orders* on three
    // lines and splits *Communication*.
    //
    // ⚠ **IT CANNOT MOVE A RAIL THAT ALREADY FITS**, and that was measured too
    // rather than argued: at 1280 and 1440, move-in (6), move-out (6),
    // transfer (5) and disconnect (5) all report `scrollWidth === clientWidth`,
    // so there is no shrink pressure on them and nothing to shrink.
    "flex min-w-0 flex-1 cursor-pointer items-center gap-3 border-0 border-r border-divider " +
    "bg-transparent px-5 py-4 text-left font-heading text-base font-semibold " +
    "last:border-r-0 " +
    // BR-SHL-018: an upcoming step is not BROKEN, it is just not navigation —
    // so it keeps full opacity and loses only the pointer.
    "disabled:cursor-default disabled:opacity-100 " +
    "max-lg:flex-none max-lg:whitespace-nowrap",
  // ⚠ **THESE FOUR ARE MUTUALLY EXCLUSIVE AND THAT IS THE FIX — `DEF-SHL-6756`.**
  //
  // They used to LAYER: the cell always carried `text-text` and gained
  // `text-accent` when active, and the badge always carried `bg-surface` and
  // gained `bg-accent`. Two utilities of equal specificity on one element, so
  // **the CASCADE decides, not the order they are written in** — and in the
  // built stylesheet `.bg-surface` sits after `.bg-accent` and `.text-text`
  // after `.text-accent`, so the conditional class lost every time.
  //
  // **Measured in Chromium at 1440 on 2026-09-25**: the ACTIVE step's badge was
  // `rgb(234,233,233)` behind text of `rgb(243,242,242)` — the number was
  // near-white on near-white — and the active cell's colour was identical to
  // the other three. **The active step was invisible on every one of the 23
  // wizards that use this frame.**
  //
  // ⚠ **NOTHING IN THIS REPOSITORY COULD SEE IT.** Every class was present in
  // the DOM and every one compiled to a real rule, so `tsc`, the suites, `G31`
  // and `routeBUtilities` all passed — and so does
  // `className.toContain("text-accent")`, which is a check that does not check.
  // Only `getComputedStyle` in a browser can answer this (hard-won law 6).
  stepRest: "text-text",
  stepActive: "text-accent-text",
  badge: "flex h-[26px] w-[26px] flex-none items-center justify-center text-sm",
  badgeRest: "bg-surface",
  badgeActive: "bg-accent text-on-accent",
  badgeDone: "bg-text text-bg",
  content: "mb-6",
  // 04-docs/README §Interactions and US-SHL-010 say "right-aligned action row";
  // the prototype styles it space-between. The signed story text wins, as it
  // did in the stylesheet this replaces.
  actions: "mt-8 flex flex-wrap items-center justify-end gap-2",
  // The footer's LEFT-hand cluster — `Cancel`, then `Save & exit`/`Park` where
  // a flow has them. `mr-auto` absorbs the free space in the `justify-end` row
  // above, which is the same device `EXIT.group` has used since CR-030, so the
  // two ends of the row are *leave* on the left and *advance* on the right.
  leftGroup: "mr-auto flex flex-wrap items-center gap-2",
  // DEF-178 — right aligned so the refusal sits UNDER the button that refused
  // it, not across the page away from the control the user just pressed.
  blocked: "mt-2 text-right text-base text-danger-500",
  // ⚠ **THE FOOTER'S PROSE LINE (DEF-1083).** A disabled control's reason and a
  //    parked flow's age are both PROSE, and both used to render INSIDE the
  //    button row — as a flex item taller than the buttons beside it. On Run
  //    bills step 2 that meant `Save & exit`, a disabled `Park` and a
  //    two-sentence paragraph sharing one line, with `Back` and `Continue`
  //    pushed to the far right of a row that no longer read as a row. The PO's
  //    words were *"UI is broken at Park"*.
  //
  //    **The rule, and it is the same one `PageHeader` now follows one frame
  //    over (DEF-966): an action row holds ACTIONS.** A status, a reason, an
  //    age — anything a person cannot press — gets a declared line of its own.
  //    Both defects were a correct thing with nowhere to put it, so both are
  //    answered by giving it somewhere rather than by shortening it.
  //
  //    LEFT-aligned, unlike `blocked` above, and the difference is deliberate:
  //    `blocked` explains the PRIMARY, which sits at the right-hand end, while
  //    this explains the exit group, which `mr-auto` holds at the left. Each
  //    sits under the control it is about (DEF-178's own argument).
  exitNote: "mt-2 max-w-measure text-left text-sm text-neutral-700",
} as const;

/**
 * What a step answers when Continue is pressed — **and the string is the whole
 * point (DEF-936).**
 *
 * `true` advances. `false` blocks and the frame prints its generic sentence,
 * which is exactly right when the unmet condition IS a field: the step has
 * already marked it, and *"fill in what's marked above"* points at the mark.
 *
 * ⛔ **A STRING BLOCKS AND SAYS WHY, AND UNTIL 2026-08-27 THERE WAS NO WAY TO.**
 * Step 1 of the bill run refused Continue on `runId !== ""` — a condition no
 * field on the screen carries — so a clerk who had filled in every input was
 * told to *"fill in what's marked above"* with **nothing marked above**. The
 * PO's words: *"all inputs are provided continue button dont work"*. The step
 * knew the reason and had no channel to say it; the frame had a channel and no
 * way to know. This union is that channel, and the generic sentence becomes the
 * FALLBACK it should always have been (DEF-936 prevention (b), verbatim: *"a
 * step whose validate can fail for a reason no field carries must be able to
 * supply its own sentence, or the frame will keep telling people to look at
 * fields that are already correct"*).
 *
 * ⚠ **AND A PROMISE IS ALLOWED, WHICH IS THE OTHER HALF.** DEF-936's own
 * closing question is *"if pressing Continue is what a clerk expects to advance
 * the step, Continue should be what starts the run"* — and starting a run is a
 * network call. A step may therefore do the work its own Continue implies and
 * answer when it is done. The frame single-flights the press and renders the
 * A18 §3 working state while it is out, so a second press is not a second run.
 *
 * ⚠ **THIS IS NOT A SECOND COMMIT AND MUST NOT BECOME ONE (BR-SHL-019).** The
 * ONE transactional commit is still the final ✓ and nothing here touches it. A
 * step that writes on Continue is writing its own step's row — a prepared run,
 * a staged batch — which is precisely what the flow was already doing from a
 * button of its own; what changes is WHICH button, not how many writes.
 */
export type WizardStepVerdict = boolean | string;

export interface WizardStep {
  id: string;
  label: string; // consumer catalog copy on the rail
  content: ReactNode; // built from the consumer's state — that's what retains values
  /**
   * ⚠ **THE STEP'S OWN FORWARD LABEL — OPT-IN, ADDED 2026-09-14 UNDER B14
   * RULE 36 (`CR-101-BRC03`, the Fix a bill journey).**
   *
   * Absent is `wizard.continue`, which is what every one of the fifteen
   * wizards mounting this frame renders today and goes on rendering — so
   * nothing existing moves, which is the condition rule 36 attaches to
   * widening the kit (*"ADD IT TO THE KIT as an opt-in, so nothing existing
   * moves"*).
   *
   * **Why it is needed rather than nice.** The Fix a bill blueprint draws a
   * different forward label on each of its first three steps — *Continue →*,
   * *See what it changes →*, *Send for approval →* — and the third is not
   * decoration: it is the act that RECORDS THE APPROVAL SIGNATURE, which is a
   * different thing from moving to the next page. A frame that says
   * *"Continue"* there tells a clerk they are turning a page when they are
   * signing. That is CONTENT (what the button does), not construction, so
   * rule 38 does not send it to the UI rules — the drawing decides it.
   *
   * It is a `ReactNode` and not a string for the same reason `commitLabel` is:
   * the label is the consumer's catalogue copy, interpolated with the
   * consumer's own figures (*Send 6 for approval*), and the frame never
   * translates it.
   */
  continueLabel?: ReactNode;
  /**
   * ⚠ **A SECOND, QUIET LINE UNDER THE STEP'S NAME — OPT-IN, ADDED 2026-10-12
   * FOR FIX A BILL (`CR-180-BRC10`, `05-prototype/fix-a-bill-2026-10-12/01`).**
   * The drawing's rail reads *Bills / Which bills · Fix / What was wrong ·
   * Check / What it does · Send / Approve and issue*. Absent on every other
   * wizard, and absent renders the label exactly as before, so nothing that
   * does not ask moves (B14 rule 36's opt-in condition).
   */
  hint?: string;
  /**
   * ⚠ **THE STEP'S FORWARD BUTTON CAN BE REFUSED BEFORE IT IS PRESSED — OPT-IN,
   * ADDED 2026-09-30 FOR THE BULK BILL RUN (`bulkRun/BulkRunPage.tsx`).**
   *
   * The drawing shows `Start checking` DISABLED while any Scope refusal stands
   * and `Sign off` disabled until all five confirmations are ticked
   * (`05-prototype/bulk-bill-run-2026-09-30/05`, `31`). `commitDisabled` does
   * this for the final step's commit and nothing did it for a Continue, so the
   * only alternative was a live button that refuses on press — hard-won law 2's
   * mirror. The reason is the screen's to draw beside it (BR-SHL-025).
   *
   * Absent on every existing wizard, so nothing that does not ask moves
   * (B14 rule 36's opt-in condition). OR-ed with the working state, never
   * substituted for it.
   */
  continueDisabled?: boolean;
  /**
   * ⚠ **THE ACTION ROW IS ABSENT WHILE THE STEP'S BODY IS A PROGRESS PANEL OR A
   * STOP — OPT-IN, ADDED 2026-10-01 FOR THE BULK BILL RUN (`DEF-BIL-8678`).**
   * The bulk-run drawing shows no footer under *Checking accounts*, *Meter
   * Reads isn't answering*, *Calculating bills* or *Sending*
   * (`05-prototype/bulk-bill-run-2026-09-30/09`, `10`, `24`, `34`). With the
   * row on screen the clerk was offered *Price 0 accounts* while the Check ran
   * and an ENABLED *Price 4 accounts* under *No account was checked*. Absent on
   * every other wizard, so nothing that does not ask moves (B14 rule 36).
   */
  actionsHidden?: boolean;
  // false blocks Continue and the frame speaks generically; a STRING blocks and
  // is what the frame says instead; a Promise of either lets the step do the
  // work its Continue implies. The step still renders its own US-SHL-009 inline
  // errors — this is the floor beneath them, never a replacement.
  validate?: () => WizardStepVerdict | Promise<WizardStepVerdict>;
}

export interface WizardFrameProps {
  steps: WizardStep[];
  nav?: WizardNavState; // controlled — the consumer mirrors `?step=` (A9)
  onNavChange?: (next: WizardNavState) => void;
  /**
   * **WHETHER THE RAIL IS NAVIGATION AT ALL** — the disconnect wizard rebuild
   * of 2026-09-25, item 3.16.
   *
   * ⚠ **ABSENT MEANS `true`, WHICH IS BYTE-FOR-BYTE WHAT EVERY WIZARD RENDERS
   * TODAY.** Twenty-three flows use this frame and none of them asked for this;
   * a silent flip would change the accessibility tree of all of them on one
   * screen's authority. Same shape and same reasoning as `commitVariant` above
   * and as `EditableTable`'s `reorderable` one kit level down (B14 rule 36:
   * extend the kit, never copy it into a screen).
   *
   * ⚠ **WHY A FLOW WOULD PASS `false`.** `BR-SHL-018` lets a clerk jump BACK to
   * a completed step and nowhere else, so on a controlled rail whose `reached`
   * never runs ahead of `step` — which is what the disconnect wizard has always
   * done — **every cell is a `<button>` and every cell is `disabled`.** A row
   * of four disabled buttons is four controls that do nothing: a screen reader
   * announces four buttons, a keyboard tabs through four buttons, and not one
   * of them ever acts. That is hard-won law 2's mirror at its cheapest to fix —
   * the drawing draws flat segments, so they are drawn as flat segments.
   *
   * `false` renders each cell as a `<span>` inside the same `<nav>`, keeping
   * `aria-current="step"` and every `data-` hook, so a walkthrough that finds
   * the rail by `data-wizard-step` finds it unchanged. **Back and Continue are
   * then the only navigation, which is what the flow is declaring.**
   */
  railNavigable?: boolean;
  commitLabel: ReactNode; // the flow's ✓ copy, e.g. "Create utility & go live ✓" (A13)
  /**
   * B14 rule 6 — THE FLOW DECLARES WHETHER ITS COMMIT IS DESTRUCTIVE (DEF-712).
   *
   * Rule 6: *"Destructive commits (disconnect, retire, reverse, write-off) use
   * the danger button — outlined accent, filled on hover — never the standard
   * primary."* Absent means `primary`, which is what every wizard rendered
   * before this prop existed and what every non-destructive wizard still
   * renders, so nothing moves on a screen that does not ask.
   *
   * ⚠ **THE FRAME CANNOT DECIDE THIS AND MUST NOT TRY.** Whether cutting a
   * household's water is destructive is a fact about the FLOW, not about the
   * frame, and there is nothing in `steps`/`commitLabel` a heuristic could read
   * that would not be guessing — a label match on "disconnect" would style
   * whatever a translator wrote and miss `retire`/`reverse`/`write-off`
   * entirely. So the consumer declares it, in one word, and rule 6 becomes
   * ASKABLE of rendered output for the first time.
   *
   * ⚠ **AND IT IS A PROP RATHER THAN A SECOND BUTTON.** The W7 lane that hit
   * this refused to draw its own danger commit beside the frame's, because that
   * loses the single-flight guard (BR-SHL-019), the A18 §3 working state and
   * the A18 §4 failure-with-entered-state-preserved. Threading the tier keeps
   * all three; a parallel button keeps none.
   */
  commitVariant?: CommitTier;
  /**
   * The commit is refused BEFORE it is pressed — the server would not accept
   * it, the rule it needs is not built, a precondition is not met.
   *
   * ⚠ **OPTIONAL, AND ABSENT MEANS EXACTLY WHAT IT MEANT BEFORE.** It reaches
   * `WorkingButton.disabled`, which is OR-ed with `working` and never
   * substituted for it, so no caller can re-enable a button mid-commit.
   *
   * ⚠ **THE REASON IS THE SCREEN'S TO DRAW, NOT THIS FRAME'S** — `BR-SHL-025`
   * wants a refused control's reason as VISIBLE TEXT beside it, and B14 is
   * explicit that a row of controls holds only things a person can PRESS, so
   * the sentence belongs under the action row rather than in it. This prop
   * only stops the press.
   */
  commitDisabled?: boolean;
  commitFailedTitle: string; // bold what-failed line for A18 §4 (plain language)
  onCommit: () => Promise<WizardCommitOutcome>; // ONE transactional call (BR-SHL-019)
  onCommitted: () => void; // consumer fires the flow's toast + routes to its declared exit
  onDownloadErrorReport?: () => void; // wired where the operation produces a report (A18 §4)
  onViewFailingRows?: () => void; // partial-success link target (A18 §4)
  controller?: WizardCommitController; // test seam, like ToastProvider's queue prop
  // CR-030 W5 task 5.1 — park & resume. Absent on a flow that has not been
  // widened yet; every widened flow passes one and gets both controls.
  exit?: WizardExit;
  /**
   * ⚠ **ONE MORE BUTTON IN THE ACTION ROW, AND IT IS NEVER THE COMMIT**
   * (CR-070 wave E, `US-WRK-016`).
   *
   * `Work-014` draws the template builder's footer as *← Back · Continue → ·
   * **Save draft*** — and *Save draft* is not a commit, not an exit and not a
   * park. It writes the flow's own draft rows and leaves the person exactly
   * where they are, which none of the three slots this frame already had can
   * express: `exit` LEAVES, `onCommit` is the ONE transactional call
   * (`BR-SHL-019`), and there was no third.
   *
   * ⚠ **A PROP RATHER THAN A SECOND BUTTON ROW, FOR `DEF-712`'s REASON.** A
   * flow that drew its own button beside the frame's would put it on a
   * different line at a different size, and B14 rule 5's *"how many button
   * sizes does this screen render"* would answer differently on this screen
   * than on the eighteen others. Threading it keeps one row, one alignment and
   * one tier vocabulary.
   *
   * Absent on every existing flow, so nothing that does not ask for it moves.
   * It renders BEFORE `← Back`, which is where the drawing puts it, and it is
   * the flow's job to disable it while a commit is in flight if that matters
   * to the flow — the frame does not know what the button does.
   */
  secondaryActions?: ReactNode;
  /**
   * ⚠ **THREE OPT-INS FOR THE BULK BILL RUN'S DRAWING — ADDED 2026-10-01
   * (`DEF-BIL-8679`, `DEF-BIL-8688`).** The bulk-run drawing puts `Back` at
   * the LEFT of the footer, the reason a primary is refused (or what it costs)
   * on the SAME row just before it, and a tick in place of a completed step's
   * number (`05-prototype/bulk-bill-run-2026-09-30/05`, `11`, `31`, `35`).
   * **Absent on every other wizard, so no other screen moves** (B14 rule 36's
   * opt-in condition): a product-wide change to the footer or the rail is a
   * decision for every wizard's own drawing, not this one's.
   */
  backAtStart?: boolean;
  actionNote?: ReactNode;
  /**
   * ⚠ **A SECOND BUTTON BESIDE THE FINAL COMMIT, ON THE RIGHT — OPT-IN, ADDED
   * 2026-10-03 FOR THE NEW PLAN FORM (`CR-167-BRC10`, images 20–21).** The
   * drawing ends Review *Back* on the left and *Save as draft* · *Publish plan*
   * together on the right (PO ruling 10). `secondaryActions` renders BEFORE
   * *Back*, which with `backAtStart` is the left-hand end, so it cannot draw
   * this. Rendered on the final step only, immediately before the commit.
   * Absent on every other wizard, so nothing that does not ask moves (B14
   * rule 36's opt-in condition).
   */
  commitCompanion?: ReactNode;
  doneMark?: "number" | "tick";
  /**
   * ⚠ **`Cancel` LIVES IN THE FOOTER, AND IT IS THE FRAME'S — PO RULING
   * 2026-09-19.**
   *
   * The Product Owner, looking at the Add units screen: ***"cancel button
   * should be bottom not on top"***, and then, on the shape being put back to
   * them in words — *"Footer: the wizard actions, with `Cancel`, and `← Back`
   * meaning previous step only"* — ***"this is correct"***.
   *
   * ⚠ **WHY IT IS A PROP ON THIS FRAME RATHER THAN A BUTTON IN FIVE SCREENS.**
   * Five wizards each drew their own `Cancel` in their own PAGE HEAD, and they
   * had drifted already: three rendered `ghost`, one `secondary`, and each
   * carried its own paragraph explaining the position. B14 rule 36 is explicit
   * about that shape — *"Where the kit lacks a piece, ADD IT TO THE KIT — one
   * component, one visual decision, every screen — rather than hand-rolling it
   * in the screen, which is how four screens acquire four different chips."*
   * Rule 38 then says the same thing for this exact control: a drawing telling
   * you *"that the footer puts Cancel on the left … is not layout, it is FORM
   * CONSTRUCTION, and B14 plus the component kit already settle it."*
   *
   * ⚠ **AND THE DIVERGENCE THOSE FIVE SCREENS RECORDED RESTED ON A FALSE
   * PREMISE.** Each said, in its own words, that `WizardFrame` *"owns the
   * footer row and right-aligns it for ten wizards, so Cancel sits in the
   * header"*. The row is `justify-end`, but `WizardExitControls` has sat at its
   * LEFT since `CR-030` by carrying `mr-auto` — so a left-hand slot was always
   * available and nobody looked. That is hard-won law 1: a comment claiming a
   * constraint is not the constraint.
   *
   * ⚠ **IT DOES NOT MEAN *previous step*, AND THE FRAME KEEPS THEM APART
   * (B14 rule 1).** `← Back` steps back inside the wizard; this LEAVES it. The
   * two never share a label, so the consumer passes the word its own catalogue
   * holds for leaving and the frame goes on rendering `wizard.back` for the
   * step-back.
   *
   * Absent on all 23 other wizards, and the branch below is written so that a
   * frame with no `cancel` renders byte-identical markup to the one it always
   * did — nothing that does not ask for this moves.
   */
  cancel?: WizardCancel;
  /**
   * ⚠ **THE FLOW HAS FINISHED — OPT-IN, ADDED 2026-09-30 FOR THE ONE-TIME
   * BILL'S *Sent* STATE (`05-prototype/one-time-bill-2026-09-30/1440-08-Interim-4-sent.png`).**
   *
   * The drawing shows every rail cell done and none of them a door once the
   * bill has gone, and the footer gone with it: there is nothing to go back
   * to and nothing left to commit. Without this a finished flow could only
   * leave its last step `active`, which says *"you are still sending"*, or
   * unmount the frame and hand-draw a second rail, which B14 rule 36 forbids.
   *
   * `true` marks every cell done, makes none of them navigable, and renders
   * no action row. The current step's `content` still renders — the flow
   * puts its outcome there. **Absent on every existing wizard, so nothing that
   * does not ask moves** (rule 36's opt-in condition).
   */
  complete?: boolean;
  /**
   * ⚠ **`DEF-SHL-10001` — THE LEAVE-PAGE POPUP'S DRAFT, AND ONLY SIX FLOWS
   * PASS ONE** (PO 2026-10-07: *"\"Save as draft\" only on the 6 that can
   * keep a draft"*): Move-in, New connection, Transfer, Move-out, Disconnect
   * and Service request capture. Each writes the store its own Park or save
   * already writes — never a second one. Absent everywhere else, and there the
   * popup says the work will not be saved.
   */
  saveDraft?: LeaveDraft | null;
}

/** The footer's exit, `BR-SHL-019`-safe: it is disabled while the ONE
 *  transactional commit is in flight, exactly as `Save & exit` and `Park` are,
 *  so a clerk cannot navigate out from under a write that has already begun. */
export interface WizardCancel {
  /** The flow's own word for LEAVING — never `wizard.back`, which is the
   *  step-back one frame down (B14 rule 1: the two never share a label). */
  label: string;
  onCancel: () => void;
}

/** The rail cell's words: the label alone — byte-for-byte as before — or,
 *  where a flow passes a `hint`, the label over its quiet second line. */
function StepLabel(props: { step: WizardStep }) {
  if (props.step.hint === undefined) return <>{props.step.label}</>;
  return (
    <span className="flex min-w-0 flex-col">
      <span data-step-label="">{props.step.label}</span>
      <span className="font-body text-sm font-normal text-neutral-700">{props.step.hint}</span>
    </span>
  );
}

export function WizardFrame(props: WizardFrameProps) {
  const { t } = useTranslation();

  const [internalNav, setInternalNav] = useState<WizardNavState>(initialWizardNav);
  const nav = props.nav ?? internalNav;
  function handleNav(next: WizardNavState): void {
    if (next === nav) {
      return; // blocked transition (forward jump / invalid step) — nothing moves
    }
    setBlocked(false); // the refusal belongs to the step that raised it
    setBlockedReason(null);
    setInternalNav(next);
    props.onNavChange?.(next);
  }

  const ownController = useRef<WizardCommitController | null>(null);
  if (ownController.current === null) {
    ownController.current = createWizardCommitController(t("wizard.failed.reason"));
  }
  const controller = props.controller ?? ownController.current;
  const commitState = useSyncExternalStore(
    controller.subscribe,
    controller.getState,
    controller.getState,
  );

  // ══════════════════════════════════════════════════════════════════════
  // **THE LEAVE-PAGE GUARD — `DEF-SHL-10001`, PO ruling 2026-10-07.** Every
  // wizard in the product mounts this frame, so one guard here covers them
  // all. It arms when the clerk TOUCHES the screen (types, ticks, picks — see
  // `touch` on the root below) or steps it forward, and never for a screen
  // only opened or resumed. Every exit this frame owns runs `deliberately`, so
  // Complete, Park, Save & exit, Cancel and the footer never ask.
  // ══════════════════════════════════════════════════════════════════════
  const [advanced, setAdvanced] = useState(false);
  const guard = useLeaveGuard({ dirty: advanced, draft: props.saveDraft ?? null });
  const ownExit = props.exit;
  const exit: WizardExit | undefined =
    ownExit === undefined
      ? undefined
      : {
          ...ownExit,
          onSaveAndExit:
            ownExit.onSaveAndExit === null
              ? null
              : () => guard.deliberately(() => ownExit.onSaveAndExit?.()),
          onPark: async (entry) => {
            const outcome = await guard.deliberately(() => ownExit.onPark(entry));
            if (outcome.ok) guard.release();
            return outcome;
          },
        };

  async function handleCommit(): Promise<void> {
    const outcome = await guard.deliberately(() => controller.run(props.onCommit));
    if (outcome !== null && outcome.ok) {
      guard.release();
      // BR-SHL-019: success fires the flow's toast and routes to the declared
      // exit — both are the consumer's, done in onCommitted.
      props.onCommitted();
    }
  }

  /**
   * ⚠ **A BLOCKED CONTINUE USED TO CHANGE NOTHING ON SCREEN — DEF-178.**
   *
   * `WizardStep.validate`'s comment has always read *"false blocks Continue;
   * the step renders its own US-SHL-009 inline errors"*. That was a COMMENT,
   * not a guarantee (hard-won law 1), and nothing ever enforced its second
   * half. Measured in Chromium across the ten wizards that mount this frame:
   * pressing Continue on `/accounts/new` and on `/reads/upload` issued no
   * request, changed no URL and changed **not one character of the DOM**. The
   * step blocked exactly as designed and told the user nothing whatsoever.
   *
   * That is the DEF-178 shape — an enabled button that does nothing — and
   * fixing it per-wizard would fix it ten times and miss the eleventh. So the
   * FRAME answers: a refused press always renders a line at the button that
   * refused it. A step that also draws its own inline errors still does, and
   * should; this is the floor beneath them, not a replacement.
   */
  const [blocked, setBlocked] = useState(false);
  /**
   * ⛔ **DEF-936 — THE STEP'S OWN SENTENCE, WHEN IT HAS ONE.** Null means the
   * step blocked without saying why, which is the field case the generic
   * sentence describes correctly. A string is rendered INSTEAD of it, in the
   * same place, at the same button.
   */
  const [blockedReason, setBlockedReason] = useState<string | null>(null);
  /** A18 §3 for a step that does work on Continue: one press at a time. */
  const [continuing, setContinuing] = useState(false);

  async function handleContinue(): Promise<void> {
    if (continuing) {
      return; // single-flight: a second press is never a second write
    }
    const current = props.steps[nav.step - 1];
    const answer = current?.validate?.() ?? true;
    let verdict: WizardStepVerdict;
    if (answer instanceof Promise) {
      setContinuing(true);
      try {
        verdict = await answer;
      } catch {
        // A step that THREW told the clerk nothing, which is the DEF-178 shape
        // this whole path exists to prevent. Block, and let the generic
        // sentence speak rather than inventing a diagnosis the frame cannot
        // make — the step's own failure rendering is where the detail lives.
        verdict = false;
      } finally {
        setContinuing(false);
      }
    } else {
      verdict = answer;
    }
    const valid = verdict === true;
    if (valid && nav.step < props.steps.length) setAdvanced(true);
    setBlocked(!valid);
    setBlockedReason(typeof verdict === "string" ? verdict : null);
    handleNav(continueFrom(nav, props.steps.length, valid));
  }

  const currentStep = props.steps[nav.step - 1];
  const isFinalStep = nav.step === props.steps.length;
  const failure = commitState.failure;

  return (
    <div className={WIZ.frame} data-wizard="frame" {...guard.touch}>
      {guard.element}
      <nav className={WIZ.rail} data-wizard="rail" aria-label={t("wizard.rail")}>
        {props.steps.map((step, index) => {
          const number = index + 1;
          const complete = props.complete === true;
          const done = complete || number < nav.step; // BR-SHL-018: only completed steps navigate (back)
          const active = !complete && number === nav.step;
          const badgeTone = active ? WIZ.badgeActive : done ? WIZ.badgeDone : WIZ.badgeRest;
          const cellTone = active ? WIZ.stepActive : WIZ.stepRest;
          const badge = (
            <span className={`${WIZ.badge} ${badgeTone}`} aria-hidden="true">
              {done && props.doneMark === "tick" ? "✓" : number}
            </span>
          );
          // See `railNavigable` — a flow that declares its rail is not
          // navigation gets flat segments rather than a row of controls that
          // never act. Every hook and `aria-current` survive.
          if (props.railNavigable === false) {
            return (
              <span
                key={step.id}
                // ⚠ **`stepActive` IS HERE BECAUSE THE FIRST DRAFT DROPPED IT.**
                // Rendering the cell as a `<span>` lost the accent on the step a
                // clerk is standing on, so the rail showed step 1 emphasised on
                // every screen. Nothing could see it — `tsc`, the suites and the
                // gates were all green — and the browser shot beside the drawing
                // is what found it (hard-won law 6).
                className={`${WIZ.step} cursor-default ${cellTone}`}
                data-wizard-step={number}
                data-state={active ? "active" : done ? "done" : "upcoming"}
                aria-current={active ? "step" : undefined}
              >
                {badge}
                <StepLabel step={step} />
              </span>
            );
          }
          return (
            <button
              key={step.id}
              type="button"
              className={`${WIZ.step} ${cellTone}`}
              data-wizard-step={number}
              data-state={active ? "active" : done ? "done" : "upcoming"}
              disabled={!done || complete}
              aria-current={active ? "step" : undefined}
              onClick={() => handleNav(jumpBackTo(nav, number))}
            >
              {badge}
              <StepLabel step={step} />
            </button>
          );
        })}
      </nav>

      {/* Step content derives from the consumer's state, so jumping back and
          returning forward re-shows everything entered (BR-SHL-018, TC-1). */}
      <div className={WIZ.content} data-wizard="content">
        {currentStep?.content}
      </div>

      {props.complete === true || currentStep?.actionsHidden === true ? null : failure !== null ? (
        // BR-SHL-019 / A18 §4: the failed card replaces only the action row —
        // the step content above keeps every entered value on screen (TC-6).
        <FailedWithRetry
          title={props.commitFailedTitle}
          reason={failure.reason}
          onRetry={() => void handleCommit()} // Retry re-submits the same commit
          onDownloadReport={props.onDownloadErrorReport ?? noop}
          onCancel={() => controller.dismissFailure()}
          partial={
            failure.partial === undefined
              ? undefined
              : { ...failure.partial, onViewFailing: props.onViewFailingRows ?? noop }
          }
        />
      ) : (
        // Right-aligned action row per 04-docs/README §Interactions (the
        // prototype styles it space-between — reported, not resolved here).
        // B18 §4.2 puts Park *"beside the footer primary"*, so the exit group
        // rides the same row and `mr-auto` keeps Back/Continue where they were.
        <div
          className={WIZ.actions}
          data-wizard="actions"
          // Anything the footer itself does — a flow's own secondary action
          // that leaves, say — is the clerk's deliberate act, not an escape.
          onClickCapture={() => guard.deliberately(() => undefined)}
        >
          {/* ⚠ **THE LEFT-HAND CLUSTER, AND THE BRANCH IS DELIBERATE.** A frame
              with no `cancel` renders exactly what it always rendered — the
              exit group alone, carrying its own `mr-auto` — so all 23 wizards
              that do not ask for a Cancel produce byte-identical markup. Only
              a frame that DOES ask gets the wrapper, which holds the two
              left-hand controls in one `mr-auto` group; giving both their own
              would split the free space between them and put neither at the
              left. PO ruling 2026-09-19. */}
          {props.cancel !== undefined ? (
            <div className={WIZ.leftGroup} data-wizard="left">
              <Button
                variant="secondary"
                // BR-SHL-019: no leaving out from under a commit in flight,
                // the same guard `Save & exit` and `Park` already carry.
                disabled={commitState.working}
                onClick={() => guard.deliberately(() => props.cancel?.onCancel())}
                data-wizard-cancel=""
              >
                {props.cancel.label}
              </Button>
              {props.exit !== undefined && (
                <WizardExitControls exit={exit as WizardExit} working={commitState.working} />
              )}
            </div>
          ) : (
            props.exit !== undefined && (
              <WizardExitControls exit={exit as WizardExit} working={commitState.working} />
            )
          )}
          {/* CR-070 wave E — the flow's own non-commit button (*Save draft* on
              `Work-014`). Before `← Back`, which is where the drawing puts it. */}
          {props.secondaryActions}
          {nav.step > 1 && (
            <Button
              variant="secondary"
              disabled={commitState.working}
              onClick={() => handleNav(backOne(nav))}
              className={props.backAtStart === true ? "mr-auto" : undefined}
            >
              {t("wizard.back")}
            </Button>
          )}
          {props.actionNote}
          {isFinalStep && props.commitCompanion}
          {isFinalStep ? (
            // BR-SHL-019: the ✓ confirm — disabled + "Working…" while the ONE
            // transactional call is in flight (WorkingButton, A18 §3).
            // B14 rule 6: the flow's own tier — danger where the commit is
            // destructive, primary everywhere else (DEF-712).
            <WorkingButton
              working={commitState.working}
              variant={props.commitVariant}
              // ⚠ **THE COMMIT CAN BE REFUSED BEFORE IT IS PRESSED, AND UNTIL
              // 2026-09-25 THIS FRAME HAD NO WAY TO SAY SO** — `WorkingButton`
              // has taken a `disabled` since `CR-069` wave E and this was the
              // one caller that never threaded it. So a wizard whose server
              // WILL refuse rendered a live primary button over a dead act:
              // hard-won law 2's mirror, the shape that put two working doors
              // out of eight on the portal's front page. Found by looking at
              // `S148` in a browser, not by a gate.
              //
              // ⚠ **OPTIONAL, AND ABSENT MEANS EXACTLY WHAT IT MEANT BEFORE**
              // (B14 rule 36's own mechanism — *add it to the kit as an opt-in
              // so nothing existing moves*). All fifteen wizards mounting this
              // frame pass nothing and render byte for byte as they did.
              disabled={props.commitDisabled === true}
              onClick={() => void handleCommit()}
            >
              {props.commitLabel}
            </WorkingButton>
          ) : (
            // DEF-936: Continue may now do the work its label promises, so it
            // carries the A18 §3 working state exactly as the commit does.
            // `working=false` renders the identical primary Button it always
            // was, so no wizard that validates synchronously moves.
            <WorkingButton
              working={continuing}
              disabled={currentStep?.continueDisabled === true}
              onClick={() => void guard.deliberately(() => handleContinue())}
            >
              {/* The STEP's own forward label where it declares one, and the
                  frame's generic word where it does not — see WizardStep. */}
              {currentStep?.continueLabel ?? t("wizard.continue")}
            </WorkingButton>
          )}
        </div>
      )}
      {/* ⚠ **THE FOOTER'S PROSE, ON ITS OWN LINE (DEF-1083).** It used to render
          INSIDE the action row above, as a flex item taller than the buttons
          beside it — so on Run bills step 2 `Save & exit`, a disabled `Park` and
          a two-sentence paragraph shared one line and `Back`/`Continue` were
          pushed to the far right of a row that no longer read as a row. The
          Product Owner's words were *"UI is broken at Park"*.

          It renders only where the failure frame is not showing, because that
          frame replaces the whole footer. */}
      {failure === null && exit !== undefined && <WizardExitNote exit={exit} />}

      {/* Park is the consumer's to allow: the panel exists only where the flow
          said it may (`parkBlockedReason === null`) and the clerk opened it. */}
      {props.exit !== undefined &&
        props.exit.parkOpen &&
        props.exit.parkBlockedReason === null && (
          <WizardParkPanel
            exit={exit as WizardExit}
            step={nav.step}
            stepCount={props.steps.length}
          />
        )}

      {/* DEF-178: the press ANSWERS, at the button that refused it. */}
      {blocked && !isFinalStep && (
        <p className={WIZ.blocked} data-wizard="blocked" role="alert">
          {/* DEF-936: the step's own sentence wins. The generic one is the
              FALLBACK — true whenever the unmet condition is a marked field,
              and a lie whenever it is not. */}
          {blockedReason ?? t("wizard.blocked")}
        </p>
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-010@b9eb83e (story+rules snapshot hash) · AMENDED 2026-08-24 for CR-030 W5 task 5.1 (BR-SHL-046 · BR-SHL-047)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-08-24 by the CR-030 W5 FRONTEND lane (N2 — park & resume, once, on the frame) · AMENDED 2026-08-25 by lane DANGERTIER (DEF-712 — an OPTIONAL `commitVariant`, so a flow can DECLARE its commit destructive and B14 rule 6's danger tier can reach a wizard commit at all; absent = `primary`, so eighteen wizard commits are unchanged. NOT a second button: single-flight, the A18 §3 working state and A18 §4 failure-with-entered-state-preserved are each re-asserted WITH the tier set)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 54/54✔ (7 todo this packet — browser/journey/consumer scope) · [DANGERTIER 2026-08-25] tsc✔ eslint 0✔ vitest 2624 passed / 1 skipped / 198 todo across 150 files✔ · G13✔ G31✔ G37✔ G40✔ · every rule-6 case proved RED first in a scratchpad copy (dropped pass-through, unconditional danger, and the three property mutations)
// exceptions: E3 the park PANEL is inline and its openness is the CONSUMER's URL
//   state (`?park=1`), not modal state: a clerk who reloads mid-park keeps the
//   form, and a modal would hide the step the reason is being written about ·
//   E3 `parkBlockedReason` is a SENTENCE and not a boolean, so a consumer
//   cannot disable park without saying why (BR-SHL-025); both W5 consumers pass
//   one today and the reason is the missing STORE, not BR-SHL-047 · E4 the nine
//   reasons carry LITERAL catalogue keys (`WIZARD_PARK_REASON_COPY`) rather
//   than a template key, because a template key is invisible to G18 and all
//   nine would read as dead catalogue entries the day they are translated
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
