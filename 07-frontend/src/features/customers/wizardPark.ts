// ── Trace ──────────────────────────────────────────────
// Change:   CR-035 step 6 part 3/4 — **the port, and resume.** `wizardParkPort()`
//           in `moveShared.tsx` returns THIS, which is *"the whole switch"* its
//           own docstring named: the panel, the nine reasons, the note and the
//           submit path were built and wired months before the store existed.
// Rules:    BR-SHL-048 (PO 2026-08-26, verbatim: *"Option A - Unitl move in
//           executed, no records updates."*) — (a) NO foreign key, (b) a draft
//           is RE-VALIDATED at execution and never trusted from the park,
//           (c) a parked wizard holds nothing · BR-SHL-047 (every wizard parks)
//           · BR-SHL-046 (ONE declared step list drives the bar, the STEP
//           column and where a resume lands) · BR-SHL-025 (a control that
//           cannot act is DISABLED WITH ITS REASON) · BR-SHL-011 (URL state) ·
//           B19 §12.2 (`Save & exit` and `Park` are TWO controls)
// Tests:    wizardPark.dom.test.tsx (rendered output, not props)
// Impacts:  moveShared.tsx (`wizardParkPort`) · all five wizards · WaitingOnTab
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · RESUME PUTS THE TYPING BACK. IT DOES NOT PUT THE ANSWERS BACK.
// ══════════════════════════════════════════════════════════════════════════
// BR-SHL-048 (b), in the ruling's own words: *"Everything in it was true on
// 26 August. On 2 September the unit may be taken, the plan may have a new
// version, the deposit rule may have changed. The wizard resumes with what was
// typed and re-runs every check before it commits."*
//
// So this hook does exactly ONE thing to a wizard: it calls `onHydrate` with
// the values the clerk typed, once, and moves `?step=` to where they stopped.
// It carries **no verdict** — no "already valid", no cached lookup, no
// pre-approved step, no skipping of a picker. Every wizard's own queries fire
// again from the ids in the draft, and every `validate()` on every step runs
// again on the way forward, because the wizard cannot tell a hydrated field
// from one typed a second ago. That indistinguishability IS the guarantee: a
// resume that took a shortcut would need a flag saying so, and there is none to
// find.
//
// ⚠ **WHICH IS ALSO WHY `reached` IS NOT RESTORED.** `WizardNavState` carries
// `reached` — the furthest step Continue has unlocked (BR-SHL-018) — and it
// would be easy, and wrong, to set it to the parked step so the clerk could
// jump straight to Review. That would let a seven-day-old draft reach the
// commit button without step 2's check ever running on today's data. The
// wizard lands ON the parked step and walks forward from there through the same
// gates it did the first time.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · THE STEP IS AN INDEX INTO THE FLOW'S OWN LIST — NEVER A NUMBER
// ══════════════════════════════════════════════════════════════════════════
// BR-SHL-046 (PO 2026-08-24, *"6 steps"*): *"the list's progress bar and the
// wizard's step bar must be driven by ONE declared step list. Two literals that
// happen to agree today is exactly the state this defect was found in, and it
// recurs the day a seventh step appears."*
//
// So `useWizardPark` takes the caller's **declared list** — `MOVE_IN_STEPS`,
// `MOVE_OUT_STEPS`, `TRANSFER_STEPS`, `DISCONNECT_STEPS`, `NEW_CONNECT_STEPS` —
// and clamps through `stepFromParam`, the same function `?step=` already goes
// through. A conditional step (move-out's `shortfall`) is still one of the six,
// so a draft parked at step 5 lands on step 5 whether or not step 4 was drawn.
// Nothing here counts steps and nothing here hard-codes a length.
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { WizardCommitOutcome, WizardParkEntry } from "@/components/WizardFrame";
import type { Translator } from "@/features/tenancy/settingsShared";

import type { FlowStepDef } from "./moveShared";
import {
  createWizardPark,
  discardWizardPark,
  getWizardPark,
  patchWizardPark,
} from "./wizardParkEndpoints";
import type {
  WizardParkBody,
  WizardParkFlow,
  WizardParkPatch,
  WizardParkRow,
  WizardParkSubjectRef,
} from "./wizardParkEndpoints";

/** `?parked=<id>` — the resume handle, URL state exactly like `?step=` and
 *  `?park=1` (BR-SHL-011 / A9). A parked draft therefore has a LINK, which is
 *  what the "Waiting on" list's Resume action navigates to and what a remind-on
 *  notification will need the day one is sent. */
export const PARKED_PARAM = "parked";

/**
 * Where a parked draft LIVES — **the tab for its own kind of work, one per
 * flow.**
 *
 * ⚠ **THIS REPLACED A SINGLE `WAITING_ON_TAB_PATH = "/accounts?tab=waiting-on"`
 * ON 2026-08-26 (CR-035 · AMENDMENT 1).** PO, verbatim: *"We dont need seperate
 * tab for this - this will be directly on each request Request, Connect, Move IN
 * move Out, Trasnfr, Disconnect - seperate queue not reequired"*. The ninth tab
 * is gone; a parked move-in is on **Move-ins**, a parked disconnect is on
 * **Disconnects**, and so on. The map is here, beside `PARKED_PARAM`, for the
 * reason the one string was: a park, a discard and a resume must not drift into
 * three destinations — and now there are five destinations, so a single place
 * naming them matters more rather than less.
 *
 * ⚠ **THE TAB IDS ARE WRITTEN OUT RATHER THAN IMPORTED FROM
 * `AccountsListPage`, DELIBERATELY.** That module imports every one of the six
 * tab bodies, each of which imports its wizard; importing it from
 * `wizardPark.ts` — which all five wizards import — closes a cycle. The five
 * strings are asserted against `ACCOUNTS_TAB_IDS` in
 * `parkedDrafts.dom.test.tsx` instead, so a renamed tab fails a test rather
 * than silently navigating a clerk to the Accounts list.
 */
export const PARKED_HOME_PATHS: Record<WizardParkFlow, string> = {
  move_in: "/accounts?tab=move-ins",
  move_out: "/accounts?tab=move-outs",
  transfer: "/accounts?tab=transfers",
  disconnect: "/accounts?tab=disconnects",
  new_connect: "/accounts?tab=new-connects",
};

/** The tab a just-parked draft of this flow will be sitting on. */
export function parkedHomePath(flow: WizardParkFlow): string {
  return PARKED_HOME_PATHS[flow];
}

// ══════════════════════════════════════════════════════════════════════════
// THE PORT
// ══════════════════════════════════════════════════════════════════════════

/**
 * What a wizard knows about the thing it is parking, beyond the nine reasons.
 *
 * ⚠ **`subjectRef` IS AN OBJECT OF COPIED VALUES AND NOT A FOREIGN KEY
 * (BR-SHL-048 (a)).** It holds the unit or account id the clerk had chosen,
 * carried so the wizard can look it up AGAIN on resume — not so anything can
 * join to it. The ruling is explicit: *"deleting a unit cannot be blocked by a
 * forgotten draft, and no report, ageing bucket or occupancy query can reach a
 * parked draft by joining to it."* The service says the same from its side:
 * *"it resolves nothing."*
 *
 * ⚠ **AND IT IS AN OBJECT ON THE WIRE, WHICH THIS LANE GOT WRONG FIRST TIME.**
 * Typed as a bare string it would have 422'd every park with `VAL-002` while
 * every button, panel and test kept working — see `WizardParkSubjectRef`.
 *
 * `subjectLabel` is the words a clerk recognises — "Unit 12, 500 Main St". It
 * is COPIED TOO, and deliberately: the list must read correctly a week later
 * even if the premise was renamed, because the row is a record of what the
 * clerk was doing and not a live view of anything.
 */
export interface WizardParkContext {
  flow: WizardParkFlow;
  subjectLabel: string;
  subjectRef: WizardParkSubjectRef;
  /** What was typed. Each wizard owns the shape and its own narrowing. */
  values: Record<string, unknown>;
}

export interface WizardParkPort {
  /**
   * Park it. `existingId` is the draft being re-parked after a resume — a
   * PATCH rather than a second row, so a clerk who resumes and parks again on
   * Thursday has ONE thing waiting and not two.
   */
  park: (
    entry: WizardParkEntry,
    context: WizardParkContext,
    existingId?: string | null,
  ) => Promise<WizardParkRow>;
  read: (id: string) => Promise<WizardParkRow>;
  discard: (id: string) => Promise<void>;
}

function createBodyOf(entry: WizardParkEntry, context: WizardParkContext): WizardParkBody {
  const body: WizardParkBody = {
    flow: context.flow,
    subject_label: context.subjectLabel,
    subject_ref: context.subjectRef,
    step: entry.step,
    values: context.values,
    waiting_on: entry.reason,
  };
  // The note and the reminder are BOTH optional (`WizardParkEntry` says so, and
  // the service request's own park makes the reminder optional). An empty
  // string is not "no reminder" — it is a blank date, and `_clean_remind_on`
  // would have to parse one. Omit the field instead.
  if (entry.note !== "") {
    body.park_note = entry.note;
  }
  if (entry.remindOn !== "") {
    body.remind_on = entry.remindOn;
  }
  return body;
}

/**
 * Re-parking an already-parked draft — **FIVE FIELDS, and the omissions are the
 * point.** `update_park` reads `step`, `values`, `waiting_on`, `park_note` and
 * `remind_on` and nothing else: *"a draft that changed which flow it was, or
 * which unit it named, would be a different draft wearing the same id, and the
 * 'Waiting on' list would silently rewrite its own history."*
 *
 * ⚠ **AN EMPTY NOTE IS SENT AS `null` HERE AND OMITTED ON THE CREATE, AND THAT
 * ASYMMETRY IS RIGHT.** On a PATCH *"an absent key is left alone; an explicit
 * `null` clears"* — so omitting a cleared note would leave last week's note on a
 * draft the clerk just emptied. On a create there is nothing to clear.
 */
function patchBodyOf(entry: WizardParkEntry, context: WizardParkContext): WizardParkPatch {
  return {
    step: entry.step,
    values: context.values,
    waiting_on: entry.reason,
    park_note: entry.note === "" ? null : entry.note,
    remind_on: entry.remindOn === "" ? null : entry.remindOn,
  };
}

/**
 * The real store, wired. This is what `wizardParkPort()` hands back.
 *
 * ⚠ **IT IS A FUNCTION OF A CLIENT AND NOT A MODULE-LEVEL SINGLETON**, for the
 * reason every screen in this product takes a `client` prop: a test that could
 * not substitute the transport would have to be run against a real server, and
 * a component that built its own would ignore the tenant the router is on.
 */
export function wizardParkStorePort(client: ApiClient = api): WizardParkPort {
  return {
    park: (entry, context, existingId = null) =>
      existingId === null || existingId === ""
        ? createWizardPark(createBodyOf(entry, context), client)
        : patchWizardPark(existingId, patchBodyOf(entry, context), client),
    read: (id) => getWizardPark(id, client),
    discard: (id) => discardWizardPark(id, client),
  };
}

// ══════════════════════════════════════════════════════════════════════════
// THE HOOK — one call per wizard, and it wires BOTH halves
// ══════════════════════════════════════════════════════════════════════════

export interface WizardParkBinding {
  /** `WizardExit.onPark`, ready to pass through. */
  onPark: (entry: WizardParkEntry) => Promise<WizardCommitOutcome>;
  /** `WizardExit.parkedAt` — set only while a parked draft is open, so the age
   *  rides beside the control the person who can end the wait is looking at. */
  parkedAt: string | null;
  /** The draft being resumed, `null` on a fresh wizard. */
  parkedId: string | null;
  /**
   * TRUE while the draft is being read.
   *
   * ⚠ **A WIZARD MUST NOT DECIDE ANYTHING IN THIS WINDOW.** For one render the
   * URL says a draft is open and the form is still empty; a step that read
   * "no unit chosen" and offered to create one would be answering a question
   * whose data had not arrived. Every consumer holds its first step's refusal
   * until this goes false.
   */
  resuming: boolean;
  /** Why the draft could not be read, in words, or null. */
  resumeProblem: string | null;
  /**
   * ⚠ **`DEF-SHL-10001` — THE LEAVE-PAGE POPUP'S *Save as draft*.** Writes the
   * SAME `wizard_parks` row `Park` and the autosave write, as a DRAFT
   * (`waiting_on: ""`) — PATCHing the row this wizard already has, or creating
   * it. It never navigates: the popup carries on the navigation it stopped.
   */
  saveDraft: () => Promise<WizardCommitOutcome>;
  /** `DEF-CUS-10002` — the last autosave write failed and nothing since has
   *  succeeded. The consumer says so in one short line; it is no longer
   *  silent (PO ruling 2026-10-07). */
  autosaveFailed: boolean;
}

export interface UseWizardParkArgs {
  /** The flow's own declared step list (BR-SHL-046). NEVER a step count. */
  steps: readonly FlowStepDef[];
  /** The step the clerk is on right now — what a park records. */
  step: number;
  /** `?park=1` — the consumer's own URL state for the panel. Read (never
   *  written) here, so the post-park navigation can wait for the panel's own
   *  close to land first; see the effect below for what happens without it. */
  parkOpen: boolean;
  /** Rebuilt every render, so a park always carries the LATEST typing. */
  context: WizardParkContext;
  t: Translator;
  client?: ApiClient;
  /**
   * Put the typed values back in the form. Called ONCE per draft.
   *
   * ⚠ It receives the whole row rather than `row.values` alone, because a
   * wizard may want `subject_ref` — the unit or account it was about — and
   * pulling that out of `values` as well would be the same fact in two places.
   */
  onHydrate: (row: WizardParkRow) => void;
  /** Where to go once the park lands. Every wizard sends the clerk to the
   *  "Waiting on" list, because that is the one surface their parked work now
   *  appears on (BR-SHL-048) and a clerk who cannot see where it went has no
   *  way to learn that it went anywhere. */
  onParked: () => void;
  /**
   * `CR-122-BRC06` — **keep a DRAFT of this wizard without being asked.**
   *
   * ⚠ **THIS IS NOT A SECOND STORE AND MUST NEVER BECOME ONE.** It writes the
   * same `wizard_parks` row `Park` writes, through the same port, under
   * `BR-SHL-048` — *"Option A - Unitl move in executed, no records updates"*.
   * What it changes is WHEN: a draft is written the moment the wizard opens,
   * and re-written as the clerk types, so a closed tab costs nothing.
   *
   * ⚠ **AND IT WRITES NO `waiting_on`, WHICH IS THE WHOLE DISTINCTION.** B19
   * §12.2's two controls stay two — `Park` still asks *what are you waiting
   * for?* and records a reason, a note and a reminder; an autosaved draft
   * answers none of those questions because nobody asked the clerk one. The
   * server reads an empty reason as `is_draft`.
   *
   * ⚠ **IT NEVER TOUCHES A ROW THAT HAS BEEN PARKED.** Resume a parked draft,
   * carry on typing, and the autosave updates `step` and `values` only — the
   * reason a clerk chose, their note and their reminder are left exactly as
   * they set them. A patch that sent the whole entry would quietly demote a
   * park back to a draft on the first keystroke.
   */
  autosave?: boolean;

  /**
   * ⚠ **THE OLD→NEW MAP, APPLIED BEFORE THE CLAMP, FOR A FLOW WHOSE STEP LIST
   * HAS CHANGED SHAPE.** A stored step is an INDEX into the list as it stood
   * when the draft was parked. `clampToSteps` below only holds a number in
   * RANGE — right by luck whenever a flow GREW, and wrong on a merged step
   * whenever a flow SHRANK. The move-out went six steps to four on 2026-09-24
   * and passes `moveOutStoredStep`; a flow that has not changed shape passes
   * nothing, because its stored number is already its own index.
   *
   * **The clamp still runs afterwards and is not replaced** — a number this
   * map does not know is handed through untouched and clamped exactly as before.
   *
   * ⚠ **THE ROW RIDES ALONG (`CR-171-BRC10` P1.03).** The move-in's
   * seven→four map is not idempotent, so it must know which shape WROTE the
   * draft (`moveShared.moveInDraftIsFourStep`) — a fact on the row, not on the
   * number. A map that does not need it ignores the second argument.
   */
  storedStep?: (stored: number, row?: WizardParkRow) => number;
}

export function useWizardPark(args: UseWizardParkArgs): WizardParkBinding {
  const { t } = args;
  const client = args.client ?? api;
  const [searchParams, setSearchParams] = useSearchParams();
  const rawParkedId = searchParams.get(PARKED_PARAM);
  const parkedId = rawParkedId === null || rawParkedId === "" ? null : rawParkedId;

  const port = wizardParkStorePort(client);

  const draftQuery = useQuery({
    queryKey: ["wizard-park", parkedId],
    queryFn: () => port.read(parkedId ?? ""),
    enabled: parkedId !== null,
    retry: false,
    // A draft is read ONCE per resume and then belongs to the form. Refetching
    // it behind a clerk who is typing would overwrite their work with a
    // week-old copy of itself.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  // The applied-guard is a ref and not state, deliberately: hydrating is a side
  // effect on somebody else's state, and a second render must not repeat it.
  // Keyed by the draft's OWN id so navigating from one parked draft to another
  // inside the same mounted wizard hydrates the second one.
  const hydrated = useRef<string | null>(null);
  const row = draftQuery.data ?? null;

  useEffect(() => {
    if (row === null || hydrated.current === row.id) {
      return;
    }
    hydrated.current = row.id;
    args.onHydrate(row);
    // BR-SHL-046 §2 — the parked step is an index into the flow's declared
    // list, clamped exactly as `?step=` is. A draft parked at a step that no
    // longer exists lands on the last one rather than erroring (BR-SHL-011's
    // fallback law).
    //
    // ⚠ **THE FLOW'S OWN MAP RUNS FIRST, AND THE CLAMP STILL RUNS AFTER IT.**
    // A clamp answers *is this number in range*, which is not the same
    // question as *which step is this number now* once a flow has merged two
    // of its steps. The move-out's old step 4 is in range for a four-step
    // list, so the clamp passes it through — onto *Review & close*, one step
    // PAST the money step it belongs on. `storedStep` is where that is
    // decided; the clamp keeps guarding everything it always guarded.
    const landing = clampToSteps(args.storedStep?.(row.step, row) ?? row.step, args.steps);
    const next = new URLSearchParams(searchParams);
    next.set("step", String(landing));
    setSearchParams(next, { replace: true });
    // The effect depends on the ROW, not on the caller's freshly-built closures
    // — `onHydrate`, `context` and `steps` are new objects every render, and
    // listing them would re-run this on every keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [row]);

  // ⚠ **THE NAVIGATION WAITS FOR THE PANEL TO CLOSE, AND THAT WAS MEASURED
  // RATHER THAN PREFERRED (it cost an afternoon).** The frame's park panel does
  // one more thing after `onPark` resolves: it closes itself, which is
  // `onParkOpenChange(false)` — an imperative `setSearchParams(...,
  // {replace: true})` on the WIZARD's own URL. Navigating from inside `onPark`,
  // or from an effect that fires in the same flush, puts that replace LAST:
  // observed in jsdom, the location went `…/transfers/new?park=1` →
  // (navigate) → `…/transfers/new`. **The park had succeeded, the row was
  // written, and the screen did not move** — a clerk would press Park, see
  // nothing happen, and press it again. No response-level assertion can see it,
  // because every response was a 201.
  //
  // So the effect waits for `parkOpen` to go false, which is the panel's own
  // close having already committed. `parkOpen` is the consumer's URL state and
  // is passed in for exactly this ordering.
  const [parked, setParked] = useState(false);
  useEffect(() => {
    if (!parked || args.parkOpen) {
      return;
    }
    setParked(false);
    args.onParked();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parked, args.parkOpen]);

  // ══════════════════════════════════════════════════════════════════════
  // CR-122-BRC06 · THE DRAFT — written on open, re-written as they type
  // ══════════════════════════════════════════════════════════════════════
  //
  // ⚠ **THE CREATE IS GUARDED BY A REF, NOT BY STATE.** Two renders before the
  // first response lands would otherwise create two drafts and burn two
  // references, and the second would orphan the first on the Move-ins tab with
  // nothing to tell them apart. A ref is written synchronously, so the second
  // render sees it.
  const creating = useRef(false);
  const [autosaveFailed, setAutosaveFailed] = useState(false);
  const [draftId, setDraftId] = useState<string | null>(null);
  // What was last SENT, serialised. The autosave compares against it so a
  // re-render that changed nothing does not write a row — this effect runs on
  // every keystroke and most keystrokes change one field of one object.
  const lastSaved = useRef<string | null>(null);
  const activeId = parkedId ?? draftId;

  // ⚠ **HOISTED OUT OF THE DEPENDENCY ARRAY, AND NOT FOR TIDINESS.** These two
  // were written inline as `JSON.stringify(...)` in the array below, which
  // `react-hooks/exhaustive-deps` refuses BY NAME — *"a complex expression in
  // the dependency array … extract it to a separate variable so it can be
  // statically checked"* — and which left `G98 lint-clean` red from the commit
  // that introduced them. The rule is not being pedantic: an expression the
  // linter cannot read statically is one it cannot check for a MISSING
  // dependency either, so the array silently stops being verified at exactly
  // the point this hook is most dangerous — it writes the clerk's draft.
  //
  // The VALUE is unchanged: still the serialised form, so the effect follows
  // what the clerk typed rather than the caller's freshly-built closures
  // (`context` is a new object every render and listing it would loop).
  const valuesKey = JSON.stringify(args.context.values);
  const subjectRefKey = JSON.stringify(args.context.subjectRef);

  useEffect(() => {
    if (args.autosave !== true) {
      return;
    }
    // ⛔ **NOT WHILE A RESUME IS IN FLIGHT.** For one render `?parked=` names a
    // draft and the form is still empty; autosaving THAT would write the empty
    // form over the very draft being read. `resuming` is the same window every
    // other consumer of this hook holds its refusals for.
    if (parkedId !== null && draftQuery.isPending) {
      return;
    }
    const snapshot = JSON.stringify({
      step: args.step,
      values: args.context.values,
      subject_label: args.context.subjectLabel,
      subject_ref: args.context.subjectRef,
    });
    if (lastSaved.current === snapshot) {
      return;
    }

    if (activeId === null) {
      if (creating.current) {
        return;
      }
      creating.current = true;
      lastSaved.current = snapshot;
      void createWizardPark(
        {
          flow: args.context.flow,
          subject_label: args.context.subjectLabel,
          subject_ref: args.context.subjectRef,
          step: args.step,
          values: args.context.values,
          // The draft state, said in the one place that says it.
          waiting_on: "",
        },
        client,
      )
        .then((row) => {
          setDraftId(row.id);
          // ⚠ **MARK IT HYDRATED BEFORE THE URL NAMES IT, OR THE WIZARD READS
          // ITS OWN EMPTY DRAFT BACK OVER THE FORM.** Setting `?parked=` below
          // makes `draftQuery` fetch this row, and the hydrate effect above
          // would then call `onHydrate` with the values as they were at the
          // instant of creation — which on a wizard opened from a service
          // request is BEFORE the prefill has run. Measured, not feared: it
          // wiped the applicant's name, email and phone every time.
          //
          // A draft this wizard created from its own state has nothing to tell
          // it. Only a draft that arrived in the URL from somewhere else — the
          // Move-ins tab, a bookmark, a reopened tab — is a resume.
          hydrated.current = row.id;
          setAutosaveFailed(false);
          // ⚠ **THE HANDLE GOES IN THE URL, `replace`, EXACTLY AS A RESUME
          // DOES.** That is what makes `Save & exit` work without a save
          // button: the address in the bar already names the draft, so the
          // clerk's own back-button, bookmark or reopened tab lands on it.
          const next = new URLSearchParams(window.location.search);
          next.set(PARKED_PARAM, row.id);
          setSearchParams(next, { replace: true });
        })
        .catch(() => {
          // ⚠ **NO LONGER SILENT — `DEF-CUS-10002`, PO ruling 2026-10-07.**
          // This read *"SILENT, AND THAT IS ARGUED … a red banner over a form
          // they are typing into would be this product interrupting them"*.
          // A clerk who then leaves trusting the draft loses the work, which
          // is the report the PO relayed. So the failure is surfaced as ONE
          // short line (never a banner), and the next change still retries.
          creating.current = false;
          lastSaved.current = null;
          setAutosaveFailed(true);
        });
      return;
    }

    lastSaved.current = snapshot;
    void patchWizardPark(
      activeId,
      {
        // ⛔ `step`, `values` and the subject ONLY. No `waiting_on`, no note,
        // no reminder — see `autosave`'s docstring for why sending the whole
        // entry would demote a parked draft on the first keystroke. The server
        // leaves an absent key alone, which is what makes this safe.
        step: args.step,
        values: args.context.values,
        subject_label: args.context.subjectLabel,
        subject_ref: args.context.subjectRef,
      } as WizardParkPatch,
      client,
    ).then(
      () => setAutosaveFailed(false),
      () => {
        lastSaved.current = null;
        setAutosaveFailed(true);
      },
    );
    // The effect follows the VALUES, not the caller's freshly-built closures:
    // `context` is a new object every render and listing it would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    args.autosave,
    args.step,
    activeId,
    parkedId,
    draftQuery.isPending,
    valuesKey,
    args.context.subjectLabel,
    subjectRefKey,
  ]);

  async function onPark(entry: WizardParkEntry): Promise<WizardCommitOutcome> {
    try {
      // ⚠ `activeId`, NOT `parkedId` (`CR-122-BRC06`). A clerk who types and
      // then presses Park already HAS a row — the autosaved draft — and
      // passing only the resume handle would create a SECOND one, leaving the
      // draft behind on the tab holding the same typing under a different
      // reference. This is the line that turns a draft into a park.
      await port.park(entry, args.context, activeId);
    } catch {
      // BR-SHL-020 — plain language, and it says what the clerk still has:
      // the form is untouched and the work is not lost.
      return {
        ok: false,
        reason: t("wizard.park.failed", {
          defaultValue:
            "This could not be parked, so nothing was saved. Everything you have typed is still on the screen — try again, or use Save & exit and come back to the address in the bar.",
        }),
      };
    }
    setParked(true);
    return { ok: true };
  }

  async function saveDraft(): Promise<WizardCommitOutcome> {
    try {
      if (activeId === null) {
        const row = await createWizardPark(
          {
            flow: args.context.flow,
            subject_label: args.context.subjectLabel,
            subject_ref: args.context.subjectRef,
            step: args.step,
            values: args.context.values,
            waiting_on: "",
          },
          client,
        );
        setDraftId(row.id);
      } else {
        // The autosave's own body: no `waiting_on`, so a draft that was
        // PARKED keeps its reason (see the autosave's comment above).
        await patchWizardPark(
          activeId,
          {
            step: args.step,
            values: args.context.values,
            subject_label: args.context.subjectLabel,
            subject_ref: args.context.subjectRef,
          } as WizardParkPatch,
          client,
        );
      }
    } catch {
      return { ok: false, reason: t("leaveGuard.saveFailed") };
    }
    return { ok: true };
  }

  return {
    onPark,
    saveDraft,
    autosaveFailed,
    parkedAt: row?.parked_at ?? null,
    parkedId,
    resuming: parkedId !== null && draftQuery.isPending,
    resumeProblem:
      parkedId !== null && draftQuery.isError
        ? t("customers.waitingOn.resumeFailed", {
            defaultValue:
              "That parked draft could not be read, so nothing has been filled in below. It is still on the Waiting on list — open it again from there.",
          })
        : null,
  };
}

// ══════════════════════════════════════════════════════════════════════════
// 3 · READING A DRAFT BACK — TWO HELPERS, AND BOTH OF THEM DISTRUST IT
// ══════════════════════════════════════════════════════════════════════════
//
// A parked draft is JSON that left this app days ago. It may have been written
// by an older build with different fields, by a newer one with more, or (in the
// case a schema cannot rule out) by hand. BR-SHL-048 (b) makes the posture
// obvious even before that: *"a draft is RE-VALIDATED at execution, never
// trusted from the park."*
//
// So neither helper below ever widens a form. They read the EMPTY form as the
// shape of truth and copy across only what matches it — a field the draft does
// not carry keeps its empty value, and a field of the wrong type is dropped
// rather than coerced. A wizard therefore cannot be handed a `unitId` that is a
// number, or an `autopay` that is the string `"false"` (which is truthy, and is
// the shape of a very quiet money defect).

/** A parked list of codes — service codes, mostly. Anything in it that is not
 *  a string is DROPPED rather than stringified: a `null` in a service list
 *  renders as an unnamed tick box, and a number renders as a service this
 *  tenant does not sell. */
export function parkedStringList(parked: unknown): string[] {
  return Array.isArray(parked) ? parked.filter((item): item is string => typeof item === "string") : [];
}

/** One parked scalar, as a string. Anything else reads as "not filled in". */
export function parkedString(values: Record<string, unknown>, key: string): string {
  const value = values[key];
  return typeof value === "string" ? value : "";
}

/**
 * A parked sub-form, merged onto the empty one.
 *
 * The `typeof` comparison against the EMPTY form's own value is the whole
 * check: it is what refuses `autopay: "yes"` and `unit_id: 42` without needing
 * a schema per wizard. `null` is refused outright — it is the JSON shape that
 * passes `typeof === "object"` and then breaks every consumer that spreads it.
 */
export function hydrateForm<T extends object>(empty: T, parked: unknown): T {
  if (parked === null || typeof parked !== "object" || Array.isArray(parked)) {
    return empty;
  }
  const source = parked as Record<string, unknown>;
  const out = { ...empty };
  for (const key of Object.keys(empty)) {
    const value = source[key];
    if (value === undefined || value === null) {
      continue;
    }
    if (typeof value === typeof (empty as Record<string, unknown>)[key]) {
      (out as Record<string, unknown>)[key] = value;
    }
  }
  return out;
}

/** The same clamp `stepFromParam` applies, on a number rather than a string.
 *  Written here rather than imported so this file takes no runtime dependency
 *  on `moveShared` — which imports THIS file for the port, and a cycle between
 *  the two would be a real one rather than a type-only one. */
export function clampToSteps(step: number, steps: readonly FlowStepDef[]): number {
  if (!Number.isInteger(step)) {
    return 1;
  }
  return Math.min(Math.max(1, step), steps.length);
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-035 · BR-SHL-048 (02-decision-log.md 2026-08-26) · BR-SHL-047 ·
//         BR-SHL-046 · BR-SHL-025 · BR-SHL-018 · B19 §12.2 · B18 §4.2
// generated: 2026-08-26 by lane PARKUI
// checklist: A=n/a(backend half is lane PARKSVC) B✔ C✔ D✔ E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// exceptions: E3 `reached` is NOT restored on resume — see §1; a clerk walks
//         forward through the same gates rather than jumping to Review · E3 no
//         optimistic update and no cache seeding on park: the row the list
//         shows is the SERVER's, because `age_days` and `parked_at` are its
//         figures and a browser clock must not author either
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
