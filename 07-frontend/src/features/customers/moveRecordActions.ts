// ── Trace ──────────────────────────────────────────────
// Change:   WHAT A CLERK CAN DO TO A MOVE-OUT RECORD, BY STATE — the PO's
//           ratified grid of 2026-09-20 (decision log §7, *"this si correct"*),
//           as ONE pure function so the table-driven test's rows ARE the grid
//           rather than a second copy of it.
// Rules:    B14 rule 4 (button grammar: `+ Noun` creates · `Verb →` navigates ·
//           `Verb ✓` commits) · rule 6 (the danger tier — `Discard draft` here;
//           write-off left this screen 2026-10-12, PO *"MOVE-OUT DOES NOT
//           WRITE OFF"*) · rule 11 (a money
//           commit shows what it will do) · rule 33 (the copy budget) ·
//           `BR-SHL-025` (a control this state cannot honour is DISABLED WITH
//           ITS REASON — and the ONE exception the PO ratified is below) ·
//           hard-won law 2's mirror (no live control over a dead destination)
// Screens:  the MOVE RECORD, `/moves/{ref}`
// Tests:    moveRecordActions.test.ts (the grid) ·
//           MoveRecordPage.actionGrid.dom.test.tsx (the grid, MOUNTED)
// Blueprint: `05-prototype/02 Accounts Menu Blueprint.pdf` **p117 lower frame →
//           p118 upper** (the record) and **p118 lower → p119 top** (the
//           commit dialog). ⚠ **NOT p074**, which this screen cited twelve
//           times and which draws the move-in WIZARD — `DEF-CUS-6000`, and the
//           measurement is
//           `04-docs/05-modules/03-customers/conformance/move-out-record-against-its-blueprint.md`.
// ───────────────────────────────────────────────────────
//
// ⚠ **THE GRID IS DATA AND NOT JSX, AND THAT IS THE POINT RATHER THAN A
// PREFERENCE.** The proof this build owes is *"a table-driven test whose rows
// ARE the action grid"*. If the grid lived inside the component, that test
// would have to mount the page to ask which controls exist — and a mount is
// exactly where this repo's checks have gone wrong before: `ourBlockedReasons`
// in `MoveOutWizard.tsx` records a case that rendered NOTHING and passed for
// the wrong reason. **A pure function cannot be defeated by a mount.** The DOM
// test still exists, because a pure grid says nothing about what is on screen —
// the two answer different questions and both are owed.
//
// ⚠ **`Open the request →` IS ABSENT WHERE THERE IS NO REQUEST, NOT DISABLED,
// AND THAT IS A RATIFIED EXCEPTION TO `BR-SHL-025`.** PO, 2026-09-20 §7:
// *"`Open the request →` appears ONLY where the move-out came from a service
// request — where it did not, it is ABSENT rather than greyed, which is a
// different thing from `BR-SHL-025`'s disabled-with-reason."* The reasoning is
// the one the Approve dialog's ruling gives from the other side: a greyed
// control says *you cannot do this HERE, YET*, and a move-out raised at the
// counter has no request to open and never will. There is nothing to wait for,
// so there is nothing to grey.
//
// ⚠⚠ **AND TODAY IT IS ABSENT ON EVERY MOVE-OUT IN THE PRODUCT — MEASURED, NOT
// ASSUMED (`DEF-CUS-6001`).** `move_records.request_id` exists and is indexed;
// the move-out wizard never writes it, and `move_record_reads.py` contains the
// string `request` **zero times**, so no door is served. The scenario suite has
// said so since before this lane started: `E3 · raised from a SERVICE REQUEST —
// and the wizard never sends the link`, RED in both columns. **This is written
// here rather than left to be inferred, because a control that is correctly
// absent on 100% of records is indistinguishable from one nobody built** — and
// the day `E3` goes green, `requestRef` starts arriving and this needs no
// change at all.

/** The four tiers the kit publishes that this screen uses. `ghost-danger` is a
 *  ROW action's colouring and is deliberately not here — rule 6's danger tier
 *  is for a destructive COMMIT, which is what `Write it off` and
 *  `Discard draft` are. */
export type MoveActionTier = "primary" | "secondary" | "ghost" | "danger";

/**
 * B14 rule 4's three grammars, named so the test can assert the MARKER rather
 * than the sentence — a label is translated eleven times and an arrow is not.
 *
 * `navigate` → `Verb →` · `commit` → `Verb ✓` · `create` → `+ Noun`.
 */
export type MoveActionGrammar = "navigate" | "commit" | "create";

export type MoveActionId =
  | "resume"
  | "discardDraft"
  | "openAccount"
  | "openCustomer"
  | "openRequest"
  | "tieBack"
  | "collect"
  | "paymentPlan";

/** The three dispositions `move_out_settlement.SHORTFALL_PATHS` publishes. ⚠ The
 *  VALUES are the server's; a list typed out by hand here is how an eleventh
 *  service failed to appear on the sign-up screen, silently. `write_off` left
 *  the set on 2026-10-12 (PO, *"we will not write off at the time of move
 *  out"*): the balance stays outstanding and is chased (BR-CUS-082), and
 *  Finance or a System Admin writes it off later in Payments. */
export type ShortfallPath = "collect" | "payment_plan" | "transfer";

export interface MoveAction {
  id: MoveActionId;
  tier: MoveActionTier;
  grammar: MoveActionGrammar;
  /** The disposition this commits, where it commits one. `null` for a door. */
  path: ShortfallPath | null;
}

/**
 * Where the shortfall stands — the grid's SECOND axis.
 *
 * ⚠ **`decided` CANNOT BE READ BACK FROM THE SERVER, AND THIS LANE DID NOT
 * INVENT A WAY (`OQ-CUS-12516`).** `shortfall_decision` returns
 * `persisted: false` with its own reason — *"no `final_settlements` table
 * exists in B2 or any addendum, so this decision rides the audit row and the
 * response"* — and `settlement_for` recomputes the landing from the BALANCE,
 * which only a TRANSFER moves (since 2026-10-14, `OQ-1250` → a). So a record
 * that was collected or put on a plan an hour ago reads `short` again on the
 * next page load.
 *
 * **What is built, and why it is not a pretence:** the page holds the outcome
 * for as long as the clerk is looking at the answer it just got — which is the
 * ratified row's behaviour, *"the outcome stated as a FACT — not four live
 * buttons"* — and a reload honestly returns to `undecided`. Defaulting to
 * `decided` would be the product claiming a settlement it cannot produce, and
 * hiding the four buttons after a reload would strand a clerk who was
 * interrupted. **The limit is filed rather than papered over.**
 */
export type ShortfallStanding = "none" | "undecided" | "decided";

export interface MoveRecordActionInput {
  /** `move_record_reads.STATE_IN_FLIGHT` / `STATE_COMPLETED` — the server's
   *  own two values, never a third invented here. */
  /** ⚠ **THREE SINCE `BR-CUS-1090`.** `approved` is an approved move-in nobody
   *  has started — it has no draft to resume and no account to open, so it has
   *  an arm of its own rather than borrowing either. */
  state: "in_flight" | "completed" | "approved";
  shortfall: ShortfallStanding;
  /** `doors.account` resolved. ⚠ **FALSE ON EVERY IN-FLIGHT MOVE**, because an
   *  account is what completing one PRODUCES — the server says so by name,
   *  `NO_ACCOUNT_UNTIL_IT_COMPLETES`. The ratified grid lists
   *  `Open the account →` on the in-flight row; it is emitted only when the
   *  door is really there, so the row renders two controls rather than a third
   *  that opens nothing. Hard-won law 2's mirror, and the audit records it. */
  hasAccount: boolean;
  /** `doors.customer` resolved. */
  hasCustomer: boolean;
  /** The service request this move-out was raised from, or `null`. See the
   *  header note: today this is `null` on every record. */
  requestRef: string | null;
  /** A parked draft's handle — `Discard draft` has nothing to discard without
   *  it, so the control is emitted only when it is present. */
  parkId: string | null;
}

/**
 * THE RATIFIED GRID, and nothing else may decide which controls a move-out
 * record carries.
 *
 * | State | Shortfall | Actions and tier |
 * |---|---|---|
 * | Approved³ | n/a | `Open the request →` secondary, and **nothing else** |
 * | In flight | n/a | `Resume →` primary · `Discard draft` danger · `Open the account →` ghost¹ |
 * | Completed | settled or refunded | `Open the account →` secondary · `Open the customer →` ghost · `Open the request →` ghost² |
 * | Completed | short, undecided | the three above **plus** `Tie the shortfall back ✓` primary · `Follow the customer ✓` secondary · `+ Payment plan` secondary ⁴ |
 * | Completed | short, decided | the three doors, and the outcome stated as a FACT |
 *
 * ¹ never emitted — no in-flight move has an account (see `hasAccount`).
 * ² emitted only where the move-out came from a request (see the header).
 * ³ `BR-CUS-1090`, added 2026-09-22 for a move-in that is approved and not
 *   started. **Neither ratified row above changed.** Its three absences are
 *   argued at the branch itself, not here.
 * ⁴ the ratified row also carried `Write it off ✓` danger. **Removed
 *   2026-10-12** — PO, *"we will not write off at the time of move out; these
 *   charges remain outstanding on the account and followup is done as per
 *   outstanding rules"* (decision log, *"MOVE-OUT DOES NOT WRITE OFF"*). The
 *   server refuses `write_off` by name, so the control would be a live button
 *   over a refusing door (hard-won law 2's mirror).
 *
 * **One danger control in the whole screen:** `Discard draft` on an in-flight
 * record. `Tie the shortfall back` MOVES money and destroys none, so it is
 * primary — the PO's own reasoning, ratified.
 */
export function moveRecordActions(input: MoveRecordActionInput): MoveAction[] {
  const out: MoveAction[] = [];

  // ── APPROVED — `BR-CUS-1090`, PO ruling 2026-09-22 ───────────────────────
  //
  // ⚠ **A THIRD ARM, AND NEITHER RATIFIED ARM ABOVE MOVES BY ONE BYTE.** The
  // grid in this docstring was ratified on 2026-09-20 for the two states that
  // existed then. An approved move-in nobody has started is a third, and the
  // honest way to serve it is its own branch — folding it into `in_flight`
  // would have let `Resume →` and `Discard draft` onto a row with no draft to
  // resume and nothing to discard, which is a live-looking control that opens
  // nothing (hard-won law 2's mirror).
  //
  // **ONE DOOR, AND THE TWO ABSENCES ARE STATED RATHER THAN LEFT TO BE READ
  // OFF THE CODE:**
  //   · **no `Resume →`** — `move_in_jobs` §3 files the door from a job into
  //     the move-in wizard rather than faking one; there is no draft here and
  //     no `parkId` is served for this state;
  //   · **no `Discard draft`** — no door in this product cancels a move-in job
  //     (`move_in_jobs` §3 again: *"a state nobody can write is a slot nothing
  //     fills"*);
  //   · **no `Open the account →`** — approving opens no account, which the
  //     Approve drawing says on all five outcomes.
  //
  // What is left is the walk back to the application, which is the thing the
  // ruling moved OFF the Move-ins tab's `Reference` column and had to put
  // somewhere. `requestRef` has been this grid's condition since it was
  // written, held at `null` by both call sites with a note saying *"the day it
  // starts arriving, this needs no change at all"* — which was true of the
  // CONDITION and not of the branching, and this is that discovered.
  if (input.state === "approved") {
    if (input.requestRef !== null) {
      out.push({ id: "openRequest", tier: "secondary", grammar: "navigate", path: null });
    }
    return out;
  }

  if (input.state === "in_flight") {
    // The PO's fourth capability of 2026-09-19 — *"We will need this action on
    // details page - 4 · Close or complete it"*. It NAVIGATES back into the
    // wizard at the parked step; it writes nothing, so it is `Verb →`.
    out.push({ id: "resume", tier: "primary", grammar: "navigate", path: null });
    if (input.parkId !== null) {
      out.push({ id: "discardDraft", tier: "danger", grammar: "commit", path: null });
    }
    if (input.hasAccount) {
      out.push({ id: "openAccount", tier: "ghost", grammar: "navigate", path: null });
    }
    return out;
  }

  // ── COMPLETED ────────────────────────────────────────────────────────────
  // The three doors come FIRST and are present in every completed arm. They
  // are the record's reason for existing; the three options belong to one
  // situation and leave when it is settled.
  if (input.hasAccount) {
    out.push({ id: "openAccount", tier: "secondary", grammar: "navigate", path: null });
  }
  if (input.hasCustomer) {
    out.push({ id: "openCustomer", tier: "ghost", grammar: "navigate", path: null });
  }
  if (input.requestRef !== null) {
    out.push({ id: "openRequest", tier: "ghost", grammar: "navigate", path: null });
  }

  if (input.shortfall !== "undecided") {
    // `none` — settled or refunded, nothing to place.
    // `decided` — *"the outcome stated as a FACT — not four live buttons"*.
    return out;
  }

  // ── money is short and nobody has said whose it is ───────────────────────
  out.push({ id: "tieBack", tier: "primary", grammar: "commit", path: "transfer" });
  out.push({ id: "collect", tier: "secondary", grammar: "commit", path: "collect" });
  // ⚠ `+ Payment plan` is rule 4's CREATOR grammar and the PO's own spelling.
  // It opens S24's payment-plan wizard at `/accounts/:id/payment-plan` rather
  // than posting `path: "payment_plan"` blind: a plan a clerk never wrote terms
  // for is a disposition with no agreement behind it, and S24 is where the
  // terms are taken. The disposition is still named here so the grid stays one
  // list of three.
  out.push({ id: "paymentPlan", tier: "secondary", grammar: "create", path: "payment_plan" });
  // ⚠ NO `Write it off ✓` — PO 2026-10-12, *"MOVE-OUT DOES NOT WRITE OFF"*.
  return out;
}

/** Rule 4's marker for a grammar — appended by the renderer, asserted by the
 *  test. Kept here so one file owns the grammar and its glyph. */
export function grammarMarker(grammar: MoveActionGrammar): { before: string; after: string } {
  if (grammar === "navigate") return { before: "", after: " →" };
  if (grammar === "commit") return { before: "", after: " ✓" };
  return { before: "+ ", after: "" };
}

/**
 * THE CATALOGUE KEY FOR EACH ACTION'S LABEL — and this map is how **ONE ACT
 * GETS ONE NAME** (PO 2026-09-20 §7, finding (a)).
 *
 * ⚠ **THE HEADER CONTROL AND THE OPTIONS ROW READ THE SAME KEY, SO THEY CANNOT
 * DRIFT.** The finding was that one act had four spellings — the header's
 * *"Tie the shortfall back"*, the options row's *"Tie back to the master"*, the
 * dialog footer's *"Tie it back to A-10001"* and the catalogue's *"Tie to
 * master"*. The PO ruled that one verb must win and **did not say which**, so
 * under hard-won law 13 that is ours to decide and write down rather than ask.
 *
 * **B14 rule 33 decides it: a LABEL caps at THREE WORDS.** *"Tie the shortfall
 * back"* is four and *"Tie back to the master"* is five; `path.transfer` —
 * *"Tie to master"* — is three, and it is **already written idiomatically in
 * all eleven catalogues** (`Auf Hauptkonto`, `Pasar a la matriz`, `親契約へ付替`),
 * which rule 35 asks for and which a fresh English-shaped translation would
 * have thrown away.
 *
 * ⚠ **AND THE FIX IS STRUCTURAL RATHER THAN A SWEEP.** Pointing both surfaces
 * at one key means a future rename moves BOTH in one edit. A sweep that
 * rewrote four strings to match would leave four strings that can drift again
 * tomorrow — which is exactly how this defect was born. B14 rule 34 applies
 * the same discipline to *Recorded* / *In the books* by policing the words;
 * here the words cannot disagree because there is only one of them.
 *
 * The three money options therefore reuse `path.*` and the two existing doors
 * reuse `door.*`. Only `discardDraft` and `openRequest` are new strings, and
 * `resume` reuses the one the parked-drafts panel already publishes.
 */
export function moveActionLabelKey(id: MoveActionId): string {
  switch (id) {
    case "resume":
      return "customers.waitingOn.action.resume";
    case "openAccount":
      return "customers.moveRecord.door.account";
    case "openCustomer":
      return "customers.moveRecord.door.customer";
    // ⚠ ONE KEY, TWO SURFACES — the options table and the header control.
    case "tieBack":
      return "customers.moveRecord.path.transfer";
    case "collect":
      return "customers.moveRecord.path.collect";
    case "paymentPlan":
      return "customers.moveRecord.path.payment_plan";
    default:
      return `customers.moveRecord.action.${id}`;
  }
}

// ══════════════════════════════════════════════════════════════════════════
// CR-171-BRC10 P2.04 — THE MOVE-IN DETAILS VIEW'S BUTTONS, BY STATUS
// ══════════════════════════════════════════════════════════════════════════
/**
 * The eight statuses `GET /moves/{ref}` serves on a move-in (`status`, the
 * list's ONE function — CR-171 §9.LIST). Read from the server, never derived.
 */
export const MOVE_IN_STATUSES = [
  "to_approve",
  "waiting_on_customer",
  "declined",
  "not_started",
  "draft",
  "waiting_on_a_read",
  "completed",
  "cancelled",
] as const;
export type MoveInStatus = (typeof MOVE_IN_STATUSES)[number];

export function isMoveInStatus(value: unknown): value is MoveInStatus {
  return typeof value === "string" && (MOVE_IN_STATUSES as readonly string[]).includes(value);
}

/** Every button the move-in details view can draw (images 03–17). */
export type MoveInActionId =
  | "approve"
  | "askForMore"
  | "resendAsk"
  | "edit"
  | "decline"
  | "reopen"
  | "start"
  | "cancel"
  | "discardDraft"
  | "changeDate"
  | "enterOpeningRead"
  | "addWorkOrder"
  | "sendMessage"
  | "print";

/** The three places a button sits in the drawn head: one primary, one
 *  secondary to its left, and the rest behind `More ▾` (B14 rule 2). */
export interface MoveInActionSlots {
  primary: MoveInActionId | null;
  secondary: MoveInActionId | null;
  more: readonly MoveInActionId[];
  /** The ones in `more` drawn in the danger tier (B14 rule 6). */
  danger: ReadonlySet<MoveInActionId>;
}

const DANGER_MOVE_IN: ReadonlySet<MoveInActionId> = new Set(["decline", "cancel", "discardDraft"]);

/** A request's buttons are the SERVER's (`move_in_request.request_actions`,
 *  §9.REQ) — this only maps each served word onto its drawn slot. */
const REQUEST_ACTION: Record<string, MoveInActionId> = {
  approve: "approve",
  ask_for_more: "askForMore",
  resend_ask: "resendAsk",
  edit: "edit",
  decline: "decline",
  reopen: "reopen",
};

/**
 * **Which buttons, in which slot, for each status — images 03–17 as drawn.**
 *
 * | Status | Secondary | Primary | More ▾ |
 * |---|---|---|---|
 * | To approve (03/04) | Ask for more… | Approve ✓ | Edit · Decline… |
 * | Waiting on customer (05/06) | Resend the ask | Approve ✓ | Edit · Decline… |
 * | Declined (07/08) | — | — | Reopen |
 * | Not started (09/10) | — | Start | Edit · Cancel move-in… |
 * | Draft (11/12) | — | Edit | Discard draft… |
 * | Waiting on a read (13/14) | Change move-in date | Enter opening read | Add a work order · Send a message · Cancel move-in… |
 * | Completed (15/16) | — | — | Send a message · Print |
 * | Cancelled (17) | — | — | — |
 *
 * On a request the SET is the server's (`actions`), so a word the server stops
 * serving leaves the head too; the slots are the drawing's.
 */
export function moveInActionSlots(
  status: MoveInStatus,
  served: readonly string[] = [],
): MoveInActionSlots {
  const slots = (
    primary: MoveInActionId | null,
    secondary: MoveInActionId | null,
    more: readonly MoveInActionId[],
  ): MoveInActionSlots => ({
    primary,
    secondary,
    more,
    danger: new Set(more.filter((id) => DANGER_MOVE_IN.has(id))),
  });
  switch (status) {
    case "to_approve":
    case "waiting_on_customer":
    case "declined": {
      const ids = served
        .map((word) => REQUEST_ACTION[word])
        .filter((id): id is MoveInActionId => id !== undefined);
      const primary = ids.includes("approve") ? "approve" : null;
      const secondary = ids.find((id) => id === "askForMore" || id === "resendAsk") ?? null;
      return slots(
        primary,
        secondary,
        ids.filter((id) => id !== primary && id !== secondary),
      );
    }
    case "not_started":
      return slots("start", null, ["edit", "cancel"]);
    case "draft":
      return slots("edit", null, ["discardDraft"]);
    case "waiting_on_a_read":
      return slots("enterOpeningRead", "changeDate", ["addWorkOrder", "sendMessage", "cancel"]);
    case "completed":
      return slots(null, null, ["sendMessage", "print"]);
    case "cancelled":
      return slots(null, null, []);
  }
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: decision log 2026-09-20 §6 and §7 (the six tables and the action
//         grid, PO-ratified) + the conformance file
//         `04-docs/05-modules/03-customers/conformance/move-out-record-against-its-blueprint.md`
//         + blueprint p117–p119 rendered and read as images (B14 rule 42)
// generated: 2026-09-20, the move-out record rebuild lane
// exceptions: E1 the ratified grid's in-flight `Open the account →` is never
//             emitted, because no in-flight move HAS an account — the server
//             says so by name (`NO_ACCOUNT_UNTIL_IT_COMPLETES`) and a control
//             opening nothing is hard-won law 2's mirror · E2 the ratified
//             grid's `Completed · short, decided` arm has nothing to read it
//             from, because `shortfall_decision` persists nothing — held for
//             the session and filed as `OQ-CUS-12516`
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
