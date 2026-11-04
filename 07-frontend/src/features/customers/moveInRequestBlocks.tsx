// ── Trace ──────────────────────────────────────────────
// Change:  `CR-122-BRC06` — *"at this stage Customer - you also need to allow
//          to submit document - similar to what we did in new reeust. even
//          drawing dont show it right now"* and *"here if ove is coming from
//          service request these details will be filled in"* (PO, 2026-09-19),
//          plus the step 4 discount claim ruled in the same session and the
//          step 5 clearing-date warning.
// Rules:   B14 rule 32 (a screen has a description budget — one sentence per
//          section, a stated absence CLOSED by default, no rule id or internal
//          code in clerk-facing copy) · B14 rule 33 (a LABEL ≤ 3 words · a FACT
//          ≤ 6 words · a CONSEQUENCE ≤ 6 words per sentence, at most two ·
//          RATIONALE is ZERO WORDS ON SCREEN) · B14 rule 21 (new UI is Tailwind
//          utilities and adds NO stylesheet class) · B14 rule 31 (no database
//          id is ever the visible value of a field) · B18 §5.3.4 (a discount
//          claim never blocks service) · `DEF-CUS-5872` (a `storage_ref` is not
//          a file).
// Screens: S19 move-in — step 2 (Customer), step 4 (Account preferences),
//          step 5 (Deposit).
// Tests:   moveInRequestBlocks.dom.test.tsx (rendered output, not props)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THESE FOUR LIVE IN THEIR OWN FILE
// ══════════════════════════════════════════════════════════════════════════
// `MoveInWizard.tsx` is NOT on `src/styles/route-b-migrated.txt`, so `G31`
// owns it and demands that every class it names be declared by a stylesheet.
// B14 rule 21 says the opposite of what that leaves room for: new UI is
// written in Tailwind utilities and adds NO class to a stylesheet. The two are
// only reconcilable by putting new UI in a file the ledger lists — which is
// the precedent `RateScheduleDetail.tsx` set, and the note beside it on the
// ledger says so in as many words.
//
// ⚠ **AND THE OLD WARNING ABOUT THIS WAS WRONG, WHICH IS WORTH KNOWING HERE.**
// Several docstrings in this folder still say a utility in an unlisted file
// "renders as nothing at all". It does not — `tailwind.css` declares
// `@source "../"` and the compiler scans the whole of `src/`. The real cost of
// an unlisted file is a RED GATE at merge, and the fix is to list the file,
// never to reach for a stylesheet class (`DEF-GOV-5102`).
//
// ══════════════════════════════════════════════════════════════════════════
// THE COPY RULE THAT SHAPED EVERY STRING BELOW
// ══════════════════════════════════════════════════════════════════════════
// PO ruling 2026-09-19, verbatim: *"please ensure enven if drawing sshow too
// much content ons creen - dont apply that we have to use our rules to show
// content on screen"*. The blueprint's frames carry long explanatory
// paragraphs — most of it is the DOCUMENT talking to its reader, not copy for
// a clerk. So the SHAPE here is the drawing's and the WORDS are B14 rules 32
// and 33's. Every sentence the drawing carries and this file does not is
// listed in the conformance record with its reason.

import { Note } from "@/components/TextBits";
import type { Translator } from "@/features/tenancy/settingsShared";


// ══════════════════════════════════════════════════════════════════════════
// 1 · STEP 2 — THE DETAILS CAME FROM A REQUEST
// ══════════════════════════════════════════════════════════════════════════

/**
 * One line saying where the answers below came from.
 *
 * ⚠ **IT NAMES THE REQUEST BY ITS REFERENCE, NOT ITS ID** (B14 rule 31 — no
 * database id is ever the visible value of a field). The id is in the address
 * bar because that is URL state; what a clerk reads is `SR-26-0006`.
 *
 * ⚠ **AND THE FIELDS STAY EDITABLE, WHICH IS THE POINT OF SAYING THIS AT ALL.**
 * A prefilled box that a clerk cannot correct is worse than an empty one: the
 * applicant may have moved, married or mistyped since they applied. This line
 * exists so a clerk knows the values were not typed by them and are theirs to
 * change — six words, per rule 33.
 */
export function RequestPrefillNote(props: { requestNo: string | null; t: Translator }) {
  if (props.requestNo === null || props.requestNo === "") {
    return null;
  }
  return (
    <Note>
      {props.t("customers.moveIn.fromRequest.filled", {
        defaultValue: "Filled from request {{ref}}.",
        ref: props.requestNo,
      })}
    </Note>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// 2 · STEP 4 — A DISCOUNT CLAIM
// ══════════════════════════════════════════════════════════════════════════

export interface DiscountClaimForm {
  /** The codes the clerk ticked. */
  codes: string[];
  /** Anything the clerk wants to add — free text, optional. */
  note: string;
}

export function emptyDiscountClaim(): DiscountClaimForm {
  return { codes: [], note: "" };
}

// ══════════════════════════════════════════════════════════════════════════
// 3 · STEP 5 — THE CLEARING-DATE TRAP IS **NOT HERE**, AND THAT IS A FINDING
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE WARNING WAS ALREADY BUILT, ALREADY WIRED AND ALREADY ON SCREEN.**
// `depositCapability.DepositStep` renders an `Advisory` under the clearing
// date whose tone goes `blocked` the moment the field is blank — landed
// 2026-09-13 in `cd73c1963`. The record this lane was given said *"our step is
// silent"*; it was wrong, and a component was read for a missing control
// instead of the screen being looked at.
//
// So there is no component here. What this lane changed is the SENTENCE, in
// `en.json`, and only because the old one stopped one step short of the thing
// that actually bites: it said the register moves when the payment clears, and
// never that **the new account reads `$0.00`** in the meantime. Rule 33's
// consequence budget is two sentences of six words and both versions fit it —
// the new one spends its twelve words on the consequence rather than on the
// mechanism.
//
// ⚠ **A SECOND WARNING WOULD HAVE BEEN WORSE THAN NONE.** Two strips under one
// date field saying nearly the same thing in different words is how a screen
// teaches a clerk to stop reading strips.
