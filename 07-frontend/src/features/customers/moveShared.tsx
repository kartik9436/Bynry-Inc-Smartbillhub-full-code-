// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W5 tasks 5.1 (park & resume on every wizard) and 5.7 (the
//           move-out impact screen). B18 §4.2 · §5.6.5 · B19 §15.7 · §15.10.
// Rules:    BR-SHL-025 (a control that cannot act is DISABLED WITH ITS REASON) ·
//           BR-CUS-030 (what a close writes, and its dunning clause) ·
//           BR-CUS-082 (SUPERSEDES that clause when a balance survives the
//           close — the debt is chased on and the ladder RESTARTS at tier 1) ·
//           BR-CUS-081 (a deposit that more than covers is settled and the
//           difference refunded) · BR-MET-105 (base charges on an empty unit
//           accrue to the owner / landlord) · BR-MET-036 (the unit flips to
//           Vacant by DERIVATION, never by a control) · BR-CUS-029 / BR-MET-044
//           (the plan lives once on the unit and survives the move-out) ·
//           B14 rule 21 (new UI is Tailwind utilities and adds NO stylesheet
//           class — this file is registered in styles/route-b-migrated.txt)
// ───────────────────────────────────────────────────────
//
// THE PIECES MOVE-IN AND MOVE-OUT SHARE, AND WHY THEY ARE HERE RATHER THAN IN
// EITHER SCREEN.
//
// Two of them are shared for the ordinary reason (both wizards park, both
// wizards state an absence the same way). The third is here for a specific one:
//
// ⚠ **THE MONEY LANDING IS A DERIVATION, AND THREE PANELS THAT LOOK LIKE COPY
// ARE ACTUALLY ITS OUTPUT.** B19 §15.10 captured the move-out impact screen in
// ONE scenario (`Refusal · excess`) and three of its panels are drawn as flat
// sentences: `Dunning · Stops on close`, the badge `All stopped`, and
// `Payment plan · 4 of 9 paid → Closed · nothing outstanding`. Every one of
// them is FALSE under a different landing:
//
//   · `Stops on close` is BR-CUS-030's clause, and BR-CUS-082 superseded it on
//     2026-08-24 for the closed-with-balance case — under `Short by` the debt
//     is chased ON and the ladder restarts at TIER 1. A screen that prints
//     "Stops on close" there tells a clerk the opposite of the signed rule.
//   · `nothing outstanding` on the payment plan is true only AFTER the
//     acceleration is billed — B19 §15.6 advisory 1, and case 3's own bill line
//     `Payment plan · remaining accelerated $132.15`.
//   · The six outgoing messages default from the outcome; drawn as captured
//     they would post a `Shortfall demand letter` to a customer owed $13.12.
//
// So each is a PURE FUNCTION of the landing below, unit-tested across all five
// values, and never a literal at a call site. B19 §15.12 item 6 states the same
// requirement in one line: *"steps 5 and 6 are scenario-driven too"*.
//
// ✅ **THE LANDING IS SERVED — `GET /accounts/{id}/close-impact` HAS BEEN
// MOUNTED SINCE 2026-08-25** (`apps/customers/api.py` → `settlement_for`), and
// `closeImpactPort()` below reads it since DEF-669 closed on 2026-08-27. This
// paragraph said *"NOT MOUNTED — no view, no serializer, no test anywhere in
// 06-backend"* for two days after all three existed.
//
// ⚠ **WHAT IS STILL ABSENT IS SIX OF TASK 5.7's IMPACT FIELDS, NOT THE
// LANDING.** They belong to other modules and nothing serves them; each arrives
// `null` and each panel states its own absence. Nothing falls back to the
// captured scenario and no figure is derived here (CLAUDE.md #2 — a rendered
// amount would be invented money).
import type { ReactNode } from "react";

import { api } from "@/api/client";
import { refusalSentence } from "@/api/refusalSentence";
import type { ApiClient } from "@/api/client";
import type { AccountDetail, AccountRow, AccountUnitPlan } from "@/api/endpoints";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { SelectField } from "@/components/FormModal";
import { MoneyCell, formatMoney } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import type { Translator } from "@/features/tenancy/settingsShared";

import { AccountFinder } from "./accountFinder";
import type { AccountSearchState } from "./accountFinder";
import { wizardParkStorePort } from "./wizardPark";
import type { WizardParkPort } from "./wizardPark";

// ══════════════════════════════════════════════════════════════════════════
// PART 1 · PARK — the port, LIVE since CR-035 (PO 2026-08-26)
// ══════════════════════════════════════════════════════════════════════════

/**
 * ✅ **THE SWITCH IS THROWN — CR-035, PO 2026-08-26.** This returned `null`
 * from the day the park panel was built until the store landed, and the
 * docstring that stood here named the condition exactly: *"Returning a port
 * here is the whole switch — the panel, the nine reasons, the note and the
 * submit path are built and wired above it, and nothing else changes when W5's
 * backend half lands."* It is kept, superseded, because it is the record of a
 * feature that sat one function away from existing for two days.
 *
 * **What it said, and what is now false about it:** *"`waiting_on`, `park_note`,
 * `parked_at` and `parked_by` are columns on `customers.ServiceRequest` and on
 * NOTHING ELSE … A move-in in progress is not a row; it is component state over
 * an account that has not been created."* That was MEASURED and true on
 * 2026-08-24. CR-035 built the store the sentence said was missing —
 * `wizard_parks`, five flows, `POST/GET/PATCH/DELETE /wizard-parks`.
 *
 * ⚠ **AND A MOVE-IN IN PROGRESS IS STILL NOT A ROW ABOUT A MOVE-IN.** The
 * store holds a saved FORM, not a job: BR-SHL-048 (PO verbatim, *"Option A -
 * Unitl move in executed, no records updates."*) is that a parked wizard
 * changes nothing until it is executed. Unit 12 reads **Vacant** the whole
 * time it is parked; the draft carries **no foreign key** to it; and the only
 * place the parked work appears is the clerk's own "Waiting on" list.
 *
 * `parkStoreBlockedReason` below reads this function and disappears on exactly
 * this condition, which is why it is one function and not a boolean at five
 * call sites — five disabled buttons became live with this `return`.
 */
export type { WizardParkPort };

export function wizardParkPort(client?: ApiClient): WizardParkPort | null {
  return wizardParkStorePort(client);
}

/** BR-SHL-025 — the sentence the control carries while it cannot act. Null
 *  the moment a port exists, which is what makes this one function rather than
 *  a boolean at two call sites. */
/**
 * Why Park is offered and blocked, and where the explanation belongs (DEF-731).
 *
 * ✅ **IT NOW RETURNS `null` ON EVERY WIZARD (CR-035, 2026-08-26)** — not
 * because this function changed, but because `wizardParkPort()` above stopped
 * returning `null`. That is the whole reason this was written as ONE function
 * reading the port rather than a boolean at five call sites: five `Park`
 * buttons went live on one `return`, and no call site was touched to do it.
 *
 * **The superseded reasoning, kept because it is the shape of the fix:** *"a
 * service request can be parked because it is ALREADY A SAVED ROW …  A move-in,
 * move-out or transfer in progress is not a row anywhere: there is no `move_ins`
 * table, no `move_outs` table and no wizard store."* True until CR-035 built
 * `wizard_parks` — which is a store for the FORM, not the missing job table.
 * BR-SHL-048 keeps it that way: a parked move-in is still not a move-in.
 *
 * ⚠ **THE SENTENCE BELOW IS NOT DEAD AND MUST NOT BE DELETED.** It is what a
 * clerk reads if the port ever goes null again — a build with the store
 * disabled, a flow added before its backend half lands. BR-SHL-025 asks for the
 * control DISABLED CARRYING ITS REASON, and deleting the reason would leave a
 * future gap rendering a silently inert button instead. The key it uses has no
 * catalogue row and is called with its `defaultValue`, so it needs no
 * translation while it is unreachable.
 */
export function parkStoreBlockedReason(t: Translator): string | null {
  if (wizardParkPort() !== null) {
    return null;
  }
  // ⛔ DEF-731 — the sentence below used to explain WHY the store is missing, in
  // the codebase's terms ("already a saved row", "becomes a record only when it
  // commits"). That reasoning is now in this function's docstring, where a
  // docstring is for. What a clerk reads is what a clerk can act on.
  // ⚠ **A NEW KEY, DELIBERATELY, AND THIS IS THE BUG THAT NEARLY SHIPPED.**
  // `customers.move.park.noStore` is ALREADY IN ALL ELEVEN CATALOGUES carrying
  // the old engineering sentence, and a catalogue entry BEATS a `defaultValue`.
  // Rewriting the default under the old key would have left the clerk reading
  // the exact sentence DEF-731 was filed about, with a green suite and a
  // convincing diff — the same shape as hard-won law 1 (a comment claiming a
  // guarantee is not the guarantee). The retired key is REPORTED for the locale
  // lane to remove; nothing here edits a catalogue.
  return t("customers.move.park.notAvailable", {
    defaultValue:
      "Parking is not available here yet — there is nowhere to keep what you are waiting on until the move is finished. Use Save & exit instead: the step you are on is kept in the address bar, so this reopens where you left off.",
  });
}

/**
 * ✅ **DEF-649 IS RULED AND MOVE-OUT PARKS TOO — `BR-SHL-047` (PO 2026-08-24,
 * verbatim: *"Park it"*).**
 *
 * The design objection is settled: the move-out wizard gets `Save & exit` and
 * `Park — waiting on` with the nine reasons, the note and the remind-on date,
 * exactly as move-in and the service request do. **There is no longer a
 * move-out-specific reason to refuse a park**, so this file no longer carries
 * one — both flows now block on the same thing, and it is the store.
 *
 * ⚠ **AND THE ARGUMENT AGAINST IT SURVIVES THE RULING, WHICH IS WHY THIS
 * COMMENT DOES.** A half-closed account STILL HOLDS ITS UNIT, so a parked
 * move-out blocks the next occupant for as long as it sits. The rule row says
 * the PO settled that parking is OFFERED and did **not** settle what stops one
 * sitting forever — that half is OPEN. So the visible AGE is built (see
 * `parkAgeDays` on the frame) and **no limit is invented**: a wizard that refused to park
 * after N days would be a rule nobody made.
 */

// ══════════════════════════════════════════════════════════════════════════
// PART 1b · ONE DECLARED STEP LIST — BR-SHL-046
// ══════════════════════════════════════════════════════════════════════════
//
// **PO 2026-08-24, closing DEF-648: *"6 steps"*.** The move-out wizard's own
// header was right and `MVO-01`'s four-segment `STEP` column was the defect.
//
// ⚠ **THE DURABLE HALF IS THE MECHANISM.** The rule's own words: *"the list's
// progress bar and the wizard's step bar must be driven by ONE declared step
// list. Two literals that happen to agree today is exactly the state this
// defect was found in, and it recurs the day a seventh step appears."*
//
// So the step list for each flow is declared ONCE, here, and both surfaces read
// it. The wizard reads it below; **the Move-outs tab needs one line** —
// `MOVE_OUT_STEPS.length` for its segment count and `stepLabel` for its
// tooltip — instead of the literal `4`. That file belongs to another lane and
// is not edited here; the import is the whole change.

export interface FlowStepDef {
  id: string;
  /** Catalogue key, LITERAL so G18 can see it. */
  labelKey: string;
  /** English, so a screen reads correctly before the catalogue merge. */
  en: string;
  /**
   * ⊕ **THE STEP'S OWN PAGE-HEAD TITLE — `DEF-CUS-6542`, 2026-09-24.**
   *
   * A wizard's `<h1>` is a FUNCTION OF THE CURRENT STEP, never a constant. A
   * constant is right on exactly one step and wrong on every other, and nobody
   * opens the other four beside the drawing — the transfer printed *"Find the
   * account, and who is selling"* over its buyer step, its date step, its
   * money step and its review for as long as the wizard existed, while the
   * line directly underneath correctly read `Step 2 of 5 · The buyer`.
   *
   * ⚠ **IT IS NOT `labelKey`, AND THE STRINGS ARE WHY.** The rail label and the
   * head title are DIFFERENT STRINGS on three of the transfer's five steps —
   * the rail reads *What they take on* where the head reads *The money* — so
   * deriving one from the other would silently rename three screens.
   *
   * ⚠ **THIS SENTENCE READ *"four of five"* AND NAMED THE DRAWN TITLES UNTIL
   * 2026-09-24 (lane TRF-CAP).** The PO ruled the five transfer heads shortened
   * to B14 rule 33's three-word cap — *"Shorten all five to the cap"* — and at
   * the shorter lengths steps 2 and 5 land on the words their rail already had.
   * **Two of five now MATCH by arithmetic and three still differ**, which is
   * why the field survives the shortening rather than collapsing into `en`.
   *
   * **OPTIONAL, deliberately.** A flow whose drawn titles have not been read
   * off its blueprint declares none and its host keeps the head it has;
   * inventing titles for a wizard nobody has measured is the guess rule 41
   * refuses. `TRANSFER_STEPS` is the first list to carry them.
   */
  titleKey?: string;
  /** English for the title — same job as `en`, correct before a catalogue merge. */
  titleEn?: string;
  /**
   * ⚠ **NO MOVE-OUT STEP IS CONDITIONAL ANY MORE — PO ruling 2026-09-24.**
   *
   * This field's docstring used to read: *"BR-SHL-046: a step that can be
   * SKIPPED is still one of the count. Step 4 renders `Shortfall · skipped`,
   * greyed, and does not leave the bar."* **That is SUPERSEDED for the
   * move-out.** The shortfall is no longer a step that can be skipped — it is
   * ABSORBED into step 3, where it is a section that appears only when the
   * subtraction lands `short`. There is nothing left to grey out, because
   * there is no longer a segment standing for it.
   *
   * The field itself stays, because BR-SHL-046's mechanism is unchanged and
   * another flow may still declare a skippable step. What changed is that this
   * flow no longer has one.
   */
  conditional?: boolean;
}

/**
 * **FOUR, PO ruling 2026-09-24, verbatim: *"i okay with these steps"*.**
 *
 * ⚠ **THIS LIST WAS SIX UNTIL TODAY, AND THE SUPERSESSION IS NAMED RATHER THAN
 * ASSUMED.** `BR-SHL-046` (PO 2026-08-24, verbatim *"6 steps"*) closed
 * `DEF-648` by ruling the count SIX. The PO has now ruled the shape FOUR, so
 * **the NUMBER in BR-SHL-046 is superseded and its MECHANISM is not**: both
 * bars are still driven by this one declared list, which is the durable half
 * the rule itself names. The server's `MOVE_OUT_STEP_COUNT` moves to 4 in the
 * same commit and `tests/test_def_648_step_count_parity.py` pins the new
 * figure — two literals in two languages that happen to agree is exactly the
 * state DEF-648 was found in.
 *
 * ⚠ **THE TWO MERGES, so a later lane does not "restore" a step:**
 * * old **3 + 4 → `settlement`**. They are ONE subtraction; *Short by* is its
 *   bottom line rather than a separate fact, which is why drawing it on its
 *   own step repeated the same figures three times.
 * * old **5 + 6 → `review`**. Old step 5 had **no input anywhere on it** —
 *   every panel was read-only, so it was a review page one click before the
 *   review page. Nothing is removed but the step.
 *
 * ⚠ **THE NUMBERS ARE INDEXES AND THIS FLOW SHRANK, SO A STORED STEP IS
 * REMAPPED AND NEVER CLAMPED** — see `moveOutStoredStep` directly below. A
 * clamp is right by luck on five of the six cases and lands old-4 one step TOO
 * FAR, on the confirm.
 */
export const MOVE_OUT_STEPS: readonly FlowStepDef[] = [
  { id: "account", labelKey: "customers.moveOut.step.account", en: "Find account" },
  { id: "date", labelKey: "customers.moveOut.step.date", en: "Date & reads" },
  // ⚠ **`Bill & deposit`, PO ruling 2026-09-24 — the drawn title of the merged
  // step (`03-bill-and-deposit.png`).** It was *Final bill & deposit* under
  // the six-step shape (PO 2026-09-20, option A), and the reason that ruling
  // gave still holds: a clerk hunting for the bill must read the word *bill*.
  // What changed is only the word *Final*, which the drawing drops now that
  // the shortfall sits on the same step.
  { id: "settlement", labelKey: "customers.moveOut.step.settlement", en: "Bill & deposit" },
  { id: "review", labelKey: "customers.moveOut.step.review", en: "Review & close" },
] as const;

/**
 * **A STORED STEP, IN THE FOUR-STEP SHAPE — the explicit old→new map.**
 *
 * ⚠ **THIS EXISTS BECAUSE A CLAMP FAILS IN THE UNSAFE DIRECTION HERE, AND ONLY
 * ON ONE ROW OF SIX.** `clampToSteps` holds a stored step inside `[1, 4]`,
 * which is right by luck for five of the six numbers a move-out draft can
 * carry — and lands the sixth one step TOO FAR:
 *
 * | parked at | should open at | a clamp gives | |
 * |---|---|---|---|
 * | 1 · Find account | 1 | 1 | right |
 * | 2 · Date & reads | 2 | 2 | right |
 * | 3 · Final bill & deposit | 3 · Bill & deposit | 3 | right |
 * | **4 · The shortfall** | **3 · Bill & deposit** | **4 · Review & close** | ⛔ **WRONG** |
 * | 5 · What happens next | 4 · Review & close | 4 | right |
 * | 6 · Review & close | 4 · Review & close | 4 | right |
 *
 * **Old 4 is the money step and new 4 is the confirm**, so a clamp walks a
 * clerk past the step where the shortfall is settled and drops them on *Close
 * the account*. Landing a clerk EARLY on a flow that GREW is the safe
 * direction — that is what `MOVE_IN_STEPS`' own comment relies on — but this
 * flow SHRANK, and the one bad case fails forward.
 *
 * ⚠ **THE CLAMP IS NOT REMOVED AND MUST NOT BE.** It still guards a stored
 * step that is out of range for some other reason — a corrupted row, a hand-
 * edited `?step=`, a flow that gains a step later. This map runs FIRST and the
 * clamp runs after it; a number this map does not know is handed through
 * untouched and the clamp still catches it.
 *
 * ⚠ **TODAY'S EXPOSURE IS ZERO AND THAT IS A REASON TO MOVE NOW, NOT A REASON
 * TO SKIP THE MAP.** Measured on the seeded tenant 2026-09-24: one parked
 * draft, a `move_in` at step 1, and no parked move-outs at all. The map costs
 * nothing today and is the difference between a safe and an unsafe landing the
 * first day somebody parks on the shortfall.
 */
export const MOVE_OUT_STORED_STEP: Readonly<Record<number, number>> = {
  1: 1,
  2: 2,
  3: 3,
  4: 3,
  5: 4,
  6: 4,
};

/** A step stored under the SIX-step shape, read in the four-step one. */
export function moveOutStoredStep(stored: number): number {
  if (!Number.isInteger(stored)) {
    return stored;
  }
  return MOVE_OUT_STORED_STEP[stored] ?? stored;
}

/**
 * ⚠ **SEVEN since 2026-09-25 — `BR-CUS-1101` added the Services step at
 * position 2. This block said SIX and is amended rather than left to rot; the
 * step list itself is below and is the only thing to count.**
 *
 * **SIX since 2026-09-12 — PO ruling, `CR-094-BRC01` step 2 wave H.** Verbatim:
 * *"on the plans and deposit step, change the plans and deposit step to account
 * preferences … and add one more step of deposit into the move in stepper"*.
 *
 * ⚠ **TWO CHANGES IN ONE RULING AND BOTH ARE HERE, because the rail is DERIVED
 * from this list (`BR-SHL-046`, PO 2026-08-24: *"the list's progress bar and
 * the wizard's step bar must be driven by ONE declared step list"*).** The
 * Move-ins tab's STEP column reads the same array, so a step added in the
 * wizard and not here would paint `4 of 5` over a six-step flow.
 *
 * ⚠ **`plan` BECAME `preferences` AND THE ID MOVED WITH THE LABEL.** The step
 * never chose a plan — the plan lives once on the unit and the account derives
 * it (PO 2026-08-11) — so an id saying `plan` named the one thing the step
 * cannot do. What it collects is preferences, and since this wave that includes
 * **paperless billing**: PO, *"Make it as account preferences in that user can
 * also select paperless billing. that should also be available."*
 *
 * ⚠ **THE NUMBERS ARE INDEXES, so inserting `deposit` at position 5 moves
 * `review` from 5 to 6** — and a parked draft or a Move-ins row reopens this
 * wizard AT a number. A draft parked on the old step 5 (`review`) now opens on
 * `deposit`, which is one step short of where it was rather than past the end:
 * the clamp in `stepFromParam` keeps every stale number in range, and landing
 * a clerk one step early on a flow that grew is the safe direction.
 */
/**
 * **WHY A TENANCY ENDED — the five the move-out screen offers** (PO ruling
 * 2026-09-20, option A; decision log *"TEN MOVE-OUT RULINGS IN ONE SITTING"*
 * item 3). `BR-CUS-030`.
 *
 * ⚠ **DECLARED ONCE, HERE, FOR THE REASON THE SERVICE LIST EXISTS TO TEACH.**
 * `CLAUDE.md`'s hard-won law 2 records what a hand-typed list costs: the
 * eleven services are typed out in two places, so an eleventh service *"does
 * NOT appear on screen on its own and it fails SILENTLY — the row exists, the
 * API serves it, `tsc` and every test pass, and the sign-up screen simply
 * never offers it."* A reason list typed inside `MoveOutWizard` would fail the
 * identical way: the server would accept a sixth code that no clerk could ever
 * choose.
 *
 * ⚠ **THESE ARE THE SERVER'S CODES, CHARACTER FOR CHARACTER** —
 * `customers.models.CLOSE_REASONS`. They are stored values, so they are never
 * translated and never renamed; what a clerk reads is
 * `customers.moveOut.reason.<code>` in each of the eleven catalogues, which is
 * B14 rule 35's *"a catalogue is written in its own language"*.
 *
 * ⚠ **THE ORDER IS THE BLUEPRINT'S** and `other` is deliberately last, because
 * a list whose escape hatch sits in the middle gets picked by accident.
 */
export const CLOSE_REASONS = [
  "lease_ended",
  "owner_sold",
  "downgrade_or_hardship",
  "deceased",
  "other",
] as const;

export type CloseReason = (typeof CLOSE_REASONS)[number];

export const MOVE_IN_STEPS: readonly FlowStepDef[] = [
  // ⚠ **FOUR since 2026-10-05 — `CR-171-BRC10` (images 30–47, PO v2/v4:
  // *"can you arrange this information in logical way"*).** The seven-step
  // list (Find unit · Which services · Customer · Start date & reads ·
  // Account preferences · Deposit · Review) folded into four: the services,
  // the date, the reads and the field visit joined the UNIT, and the
  // preferences and the deposit became BILLING. `BR-SHL-046` stands — this is
  // still the ONE list the rail, the step line and the Move-ins STEP column
  // read; only its content changed (CR §2 S5).
  //
  // ⚠ **THE FLOW SHRANK, SO OLD NUMBERS NEED A MAP AND HAVE ONE** — a draft
  // parked at old step 5 is not "step 5 clamped to 4": it is Billing.
  // `MOVE_IN_SEVEN_STEP_TO_FOUR` below is that map, wired as the move-in's
  // `storedStep` on both surfaces (the list and the resume), and the server
  // holds the same one (`move_reads.MOVE_IN_SEVEN_STEP_TO_FOUR`).
  { id: "unit", labelKey: "customers.moveIn.step.unit", en: "Unit" },
  { id: "customer", labelKey: "customers.moveIn.step.customer", en: "Customer" },
  { id: "billing", labelKey: "customers.moveIn.step.billing", en: "Billing" },
  { id: "review", labelKey: "customers.moveIn.step.review", en: "Review" },
] as const;

/**
 * **A MOVE-IN DRAFT PARKED UNDER THE SEVEN-STEP WIZARD, READ IN THE FOUR-STEP
 * ONE — `CR-171-BRC10` P1.03, the CR's own map (§4).** Old 1–2 (Find unit ·
 * Which services) → 1 · Unit; 3 (Customer) → 2 · Customer; 4 (Start date &
 * reads) → **1 · Unit**, because the date, the reads and the visit live on the
 * Unit step now (images 30–32); 5–6 (Preferences · Deposit) → 3 · Billing;
 * 7 (Review) → 4 · Review. Every value is kept — the four-step form reads the
 * seven-step keys — so only the STEP moves.
 *
 * ⚠ **THE SERVER HOLDS THE SAME MAP** (`move_reads.MOVE_IN_SEVEN_STEP_TO_FOUR`)
 * for the list's STEP cell, and `tests/test_cr171_p1_04_move_ins_list.py`
 * holds the two equal.
 *
 * ⚠ **NOT IDEMPOTENT, SO IT IS APPLIED ONLY TO A SEVEN-STEP DRAFT.** A
 * four-step draft at 2 · Customer would map to 1 · Unit. A draft says which
 * shape wrote it: `values.step_shape === "four"` (the four-step form must
 * write it), or a `subject_ref.service_request_id` (the request's Edit door,
 * which only ever wrote four steps). Anything else is seven-step.
 *
 * ⚠ **WIRED 2026-10-05 (P2.15, lane WIZ)** — in the same commit that made
 * `MOVE_IN_STEPS` four: the wizard's resume and `parkedDrafts`' STEP cell both
 * pass it as `storedStep`, and the four-step form writes `step_shape: "four"`
 * on every park. `moveInStoredStep.test.ts` holds the wiring.
 */
export const MOVE_IN_SEVEN_STEP_TO_FOUR: Readonly<Record<number, number>> = {
  1: 1,
  2: 1,
  3: 2,
  4: 1,
  5: 3,
  6: 3,
  7: 4,
};

/** The key the four-step form writes into a draft's `values`. */
export const MOVE_IN_STEP_SHAPE_KEY = "step_shape";
export const MOVE_IN_STEP_SHAPE_FOUR = "four";

/** Was this draft written by the four-step form? See the map above. */
export function moveInDraftIsFourStep(row?: {
  subject_ref?: unknown;
  values?: unknown;
}): boolean {
  const values = (row?.values ?? {}) as Record<string, unknown>;
  const subject = (row?.subject_ref ?? {}) as Record<string, unknown>;
  if (values[MOVE_IN_STEP_SHAPE_KEY] === MOVE_IN_STEP_SHAPE_FOUR) {
    return true;
  }
  return typeof subject.service_request_id === "string" && subject.service_request_id !== "";
}

/** A stored move-in step, in the four-step shape. The clamp still runs after. */
export function moveInStoredStep(
  stored: number,
  row?: { subject_ref?: unknown; values?: unknown },
): number {
  if (!Number.isInteger(stored) || moveInDraftIsFourStep(row)) {
    return stored;
  }
  return MOVE_IN_SEVEN_STEP_TO_FOUR[stored] ?? stored;
}

/** `2 of 6` — the list's STEP column and the wizard's own line, from ONE list. */
export function flowProgress(
  steps: readonly FlowStepDef[],
  step: number,
): { step: number; of: number } {
  const of = steps.length;
  const clamped = Math.max(1, Math.min(Math.trunc(step), of));
  return { step: clamped, of };
}

/**
 * BR-SHL-011's spirit: an out-of-range `?step=` clamps, it never errors.
 *
 * ⚠ **`storedStep` IS THE FLOW'S OLD→NEW MAP AND IT RUNS BEFORE THE CLAMP
 * (`CR-150-BRC09`, 2026-09-28).** A clamp answers *is this number in range*,
 * which stops being the right question the moment a flow MERGES two steps: a
 * New Connect `?step=6` was *Charges* under the eight-step shape, and it is in
 * range for a five-step list, so the clamp hands it through untouched — onto
 * **Review**, one step past the money. The parameter is OPTIONAL and the
 * default is exactly the old behaviour, because a flow that has not changed
 * shape has nothing to map.
 *
 * ⚠ **THIS IS THE SAME OPTION `useWizardPark` ALREADY TAKES, ON THE OTHER
 * DOOR.** A stored step reaches a wizard two ways — out of `wizard_parks` on a
 * resume, and out of the address bar on a bookmark — and a map applied to one
 * of them is a wizard that lands a clerk in two different places depending on
 * how they arrived.
 */
export function stepFromParam(
  raw: string | null,
  steps: readonly FlowStepDef[],
  storedStep?: (stored: number) => number,
): number {
  const parsed = Number(raw ?? "1");
  if (!Number.isInteger(parsed)) {
    return 1;
  }
  const mapped = storedStep?.(parsed) ?? parsed;
  return Math.min(Math.max(1, mapped), steps.length);
}

// ══════════════════════════════════════════════════════════════════════════
// PART 2 · THE MONEY LANDING — one derivation, and the panels that follow it
// ══════════════════════════════════════════════════════════════════════════

/**
 * B19 §15.9's five, and §15.12 item 1 names them as the one derived outcome the
 * whole of steps 3, 5 and 6 read from. **A clerk never chooses one** — B19
 * §15.1 is explicit that the prototype's `Scenario` switch is a reviewer's
 * device and must not be built; the balance and the deposit decide it.
 */
export const MONEY_LANDINGS = [
  "settled",
  "refund_due",
  "short",
  "refused_other_debt",
  "refused_excess",
] as const;

export type MoneyLanding = (typeof MONEY_LANDINGS)[number];

/**
 * What `GET /accounts/{id}/close-impact` must answer. Written here as the
 * CONTRACT rather than as a guess at a payload: every field is something B18
 * §5.6.5 or B19 §15.10 states on the screen and no field is something the
 * screen does not print.
 */
export interface CloseImpact {
  landing: MoneyLanding;
  /** §15.10 `Units occupied after this 1 of 3`.
   *  ✅ **SERVED since CR-056 W6** — counted from the premises, common areas
   *  excluded, with the leaving account already taken off the occupied side. */
  units_occupied_after: { occupied: number; total: number } | null;
  /** §15.10 · §15.5 — who the empty unit's standing charge is addressed to.
   *  ✅ **SERVED since CR-056 W6.** The owner ACCOUNT's own contact where one
   *  resolves; the premises' free-text owner otherwise, which is DEF-650's
   *  *"a charge cannot be sent to a name"* stated rather than implied. */
  owner_on_record: string | null;
  /** ✅ **SERVED since CR-056 W6, AND `null` IS STILL NOT `true`** — DEF-669.
   *  It was typed `boolean` and the panel defaulted an unread value to `true`,
   *  which ASSERTS the owner is free text on every premises in the product. A
   *  third state costs one character and stops the screen making a claim
   *  nobody measured. */
  owner_is_free_text: boolean | null;
  /** §15.10 `Common-area account MA-1408 · unaffected`.
   *  ✅ **SERVED since CR-056 W6.** Under that CR it is the owner's account at
   *  the ADDRESS whether or not the address has a common area; the field keeps
   *  its name so no reader has to be migrated. */
  common_area_account_no: string | null;
  /** CR-056 W6 / BR-CUS-1040 — the account this unit falls to the moment the
   *  tenant leaves, and the FAULT when there is none. PO 2026-08-31: *"no
   *  lines because nothing falls to it"* and *"no lines although the premises
   *  HAS an unoccupied unit"* are different facts and only one is good news. */
  unit_falls_to: {
    available: boolean;
    account_id: string | null;
    account_no: string | null;
    br_ref: string;
    reason: string | null;
  } | null;
  /** The plan's OWN configured standing charge per service, read verbatim and
   *  never summed. A DECIMAL STRING with its CHAR(3), never a number
   *  (CLAUDE.md #2). ✅ **SERVED since CR-056 W6.** */
  vacant_base_charges:
    { service: string; name: string; stored: string; display: string; currency: string }[] | null;
  /** §15.10's four dispositions carry a monthly price each; BR-MET-105's own
   *  worked figure is $30.50/month. A DECIMAL STRING with its CHAR(3), never a
   *  number (CLAUDE.md #2).
   *  ⛔ **STILL NOT SERVED, ON PURPOSE.** One total is a PRICE and pricing is
   *  the rating engine's; nothing publishes a per-unit standing charge outside
   *  a bill run, so `vacant_base_charges` above carries the plan's own figures
   *  instead of an arithmetic this screen would have invented. */
  vacant_base_charge: { amount: string; currency: string } | null;
  /** `BR-CUS-1082` — a parent with open children is WARNED when it is moved
   *  out, never refused (PO ruling 2026-09-20, `OQ-CUS-12515` option (b)).
   *  This read said *"cannot be moved out"*, after `B19 §15.8`, whose item 1
   *  that ruling superseded. The FIELD is unchanged: it is the count, and it
   *  is the one `selectors.sub_accounts_for_master` answers. */
  open_sub_accounts: number;
  /** §15.6 advisory 1 — `4 of 9 instalments paid`, which the label needs. */
  payment_plan: { paid: number; of: number } | null;
  /**
   * ⚠ **B19 §15.9's SUBTRACTION, ADDED 2026-09-19 — and it was being thrown
   * away.** `settlement_for` has served `everything_outstanding`,
   * `what_is_applied` and `verdict` since 2026-08-25 and this port mapped
   * exactly two of their fields; steps 3, 5 and 6 then drew stated absences
   * over money the server had already sent. `null` when the read has not
   * answered; every field inside it independently null when a TERM could not
   * be read, which is the state every account is in until a final bill is
   * stated.
   */
  money: SettlementMoney | null;
  /**
   * ⚠ **READ HERE AND NOWHERE ELSE, FROM 2026-09-19.** `MoveOutWizard` used to
   * fetch this same route a SECOND time with its own fetcher, which is how
   * `DEF-CUS-5072` lost a leading slash on one caller and not the other —
   * *"nothing in this repository compares two callers of one route"*. Worse
   * after today: the second fetcher stated no `final_bill`, so step 4 read a
   * DIFFERENT settlement from step 3 on the same screen. One caller, one
   * settlement.
   */
  shortfall_paths: ShortfallPathOption[];
  /** BR-CUS-081's CLOSED set of refund methods, as the server publishes it.
   *  Read, never typed out here — the eleventh-service lesson. */
  refund_methods: readonly string[];
  /** The settlement's own `gaps[]` — why there is no landing. Never a word on
   *  screen (B14 rule 33); it rides on `data-` so support can still find it. */
  gaps: readonly string[];
  /**
   * ⚠ **THE SERVER'S OWN ANSWER TO *IS STEP 4 LIVE*, AND THE REASON IT IS READ
   * RATHER THAN DERIVED — `DEF-CUS-5920`.** The step derived it as `landing
   * !== null && landing !== "short"`, which is FALSE under a null landing — so
   * on every account in the product the four shortfall radios rendered ENABLED
   * over a `POST` that refuses `no_shortfall` every single time. The server
   * computes `step_4_live = landing in STEP_4_LIVE_IN`, which is False when
   * there is no landing, and that is the only figure that can be right.
   */
  step_4_live: boolean | null;
}

/** What the caller STATES, because the settlement will not invent either.
 *  `finalBill` is the preview's `total` (the CHARGES); `asOf` is the day
 *  BR-CUS-057's interest accrues to, which is the move-out day. */
export interface CloseImpactTerms {
  finalBill?: string | null;
  asOf?: string | null;
}

export interface CloseImpactPort {
  read: (accountId: string, terms?: CloseImpactTerms) => Promise<CloseImpact>;
}

/**
 * ✅ **MOUNTED, AND WIRED HERE SINCE 2026-08-27 — DEF-669.**
 *
 * ⛔ **WHAT THIS SAID BEFORE, AND WHY IT WAS THE DEFECT.** This function
 * returned `null` under a docstring reading *"NOT MOUNTED … a grep of the whole
 * repository for either path returns nothing"*. Both sentences were TRUE when
 * written and both became FALSE the moment `GET /accounts/{id}/close-impact`
 * and `POST /accounts/{id}/settle-shortfall` landed — on 2026-08-25, in
 * `apps/customers/api.py`. The move-out wizard therefore told a clerk the
 * feature was unbuilt **on the commit that built it**, which is hard-won law 1
 * exactly: a string describing an absence must change with the fact it
 * describes, and nothing in this repository makes that check systematic. The
 * backend lane that mounts a route has no reason to grep the frontend for prose
 * about it.
 *
 * ⚠ **AND THE SECOND HALF OF DEF-669 IS WHY THIS MAPS RATHER THAN CASTS.** The
 * two sides disagree about what a `CloseImpact` IS, in BOTH directions:
 * `settlement_for` serves `landing`, `open_sub_accounts` and the whole of B19
 * §15.9's MONEY, and **none** of task 5.7's other six impact fields — premises
 * occupancy, the BR-MET-105a owner whose column does not exist, the master
 * account, the vacant base charge and payment-plan progress are each owned by
 * another module. So the payload is a SUPERSET on the money side and a SUBSET
 * on the impact side. **Casting the response to `CloseImpact` would leave those
 * six `undefined`, and `undefined` renders as `0 of 0` and as "not free text"**
 * — a screen quietly stating measurements nobody took. They are mapped to an
 * explicit `null` instead, which every panel already renders as a stated
 * absence. Nothing is invented to close the difference; the six need owners and
 * that is DEF-669's open half, tracked on its row.
 */
export function closeImpactPort(client: ApiClient = api): CloseImpactPort {
  return {
    read: async (accountId: string, terms: CloseImpactTerms = {}): Promise<CloseImpact> => {
      // ⚠ **THE LEADING SLASH IS LOAD-BEARING — `DEF-CUS-4010`, 2026-09-05.**
      // Without it `apiPath` concatenates tenant and path with nothing between
      // them and the request goes to `/api/brazosbendaccounts/<id>/close-impact`
      // — a 404 on EVERY move-out, on the *What happens next* step, in
      // production. It was invisible because the port's own failure path
      // renders the absence honestly, so a 404 and *"this figure is not
      // available"* look identical on screen; every unit test stubs the port
      // and never builds the URL. Found by clicking through a move-out on a
      // real build (hard-won law 6), which is the only thing that could.
      // ⚠ **THE STATED TERMS ARE WHAT UNBLOCK THE WHOLE CHAIN.** Without
      // `?final_bill=` the settlement reports `final_bill_not_stated`, no
      // landing and fourteen null totals — which is what every account in this
      // product answered until 2026-09-19, because no caller ever stated one.
      const query = new URLSearchParams();
      if ((terms.finalBill ?? "") !== "") {
        query.set("final_bill", String(terms.finalBill));
      }
      if ((terms.asOf ?? "") !== "") {
        query.set("as_of", String(terms.asOf));
      }
      const suffix = query.toString() === "" ? "" : `?${query.toString()}`;
      const answer = await client.get<Record<string, unknown>>(
        `/accounts/${accountId}/close-impact${suffix}`,
      );
      const served = answer.data ?? {};
      return {
        landing: (served.landing ?? null) as MoneyLanding,
        // ── SERVED (BR-CUS-171, PO 2026-08-27 closing OQ-531) ──────────────
        open_sub_accounts: Number(served.open_sub_accounts ?? 0),
        // ── SERVED SINCE CR-056 W6 (BR-CUS-1040) — four of DEF-669's six ────
        // `move_out_settlement.close_impact_for` answers these now: the unit
        // falls to the owner's account on the day the tenant leaves, and the
        // PO ruled on 2026-08-31 that the screen must SAY so before the clerk
        // commits. `?? null` on every one of them, never `?? 0` and never
        // `?? false` — an unread value must stay the third state DEF-669's own
        // correction created, or the panel resumes stating measurements
        // nobody took.
        units_occupied_after:
          (served.units_occupied_after as CloseImpact["units_occupied_after"]) ?? null,
        owner_on_record: (served.owner_on_record as string | null) ?? null,
        owner_is_free_text: (served.owner_is_free_text as boolean | null) ?? null,
        common_area_account_no: (served.common_area_account_no as string | null) ?? null,
        unit_falls_to: (served.unit_falls_to as CloseImpact["unit_falls_to"]) ?? null,
        vacant_base_charges:
          (served.vacant_base_charges as CloseImpact["vacant_base_charges"]) ?? null,
        // ── STILL NOT SERVED, each with the reason it is not ────────────────
        // A single "what the empty unit costs" figure is a PRICE and pricing is
        // the rating engine's alone; nothing publishes a per-unit standing
        // charge outside a bill run. The plan's own configured per-service
        // figures arrive above instead — read verbatim, never summed.
        vacant_base_charge: null,
        payment_plan: null, // payments — instalment progress
        // ── SERVED SINCE 2026-08-25 AND MAPPED SINCE 2026-09-19 ────────────
        money: settlementMoneyOf(served),
        shortfall_paths: Array.isArray(served.shortfall_paths)
          ? (served.shortfall_paths as ShortfallPathOption[])
          : [],
        refund_methods: Array.isArray(served.refund_methods)
          ? (served.refund_methods as string[])
          : [],
        gaps: Array.isArray(served.gaps) ? (served.gaps as string[]) : [],
        step_4_live: typeof served.step_4_live === "boolean" ? served.step_4_live : null,
      };
    },
  };
}

/** The landing, or null when nothing has told us. **Never a default** — the
 *  captured scenario is one of five and picking it would be picking a value. */
export function landingOf(impact: CloseImpact | null): MoneyLanding | null {
  return impact === null ? null : impact.landing;
}

// ── The three sentences that must not be constants ────────────────────────

export interface DerivedSentence {
  /** The catalogue key. */
  key: string;
  /** English, so the screen reads correctly before the catalogue merge. */
  text: string;
  /** The rule this sentence obeys — rendered as `data-br-ref`, never as prose
   *  on a customer's screen (DEF-332). */
  ruleRef: string;
}

/**
 * `Collections & notices` · `Dunning`.
 *
 * BR-CUS-030 stops dunning at close. **BR-CUS-082 (PO, 2026-08-24) supersedes
 * that for the closed-with-balance case**: the balance is still chased and the
 * ladder RESTARTS at tier 1 rather than resuming the tier it had reached — and
 * a closed account cannot be escalated to disconnection, because there is
 * nothing left to disconnect.
 *
 * So `short` is the case the captured screenshot could not show, and it is the
 * one that would have shipped wrong.
 */
export function dunningOnClose(landing: MoneyLanding | null): DerivedSentence {
  if (landing === "short") {
    return {
      key: "customers.moveOut.impact.dunning.chasedOn",
      text: "Chased on after the close, and the reminder ladder starts again at tier 1. A closed account cannot be escalated to disconnection, so this is a collections sequence and not a service one.",
      ruleRef: "BR-CUS-082",
    };
  }
  if (landing === null) {
    return {
      key: "customers.moveOut.impact.dunning.unknown",
      text: "Either stops at the close or carries on, and which one depends on whether a balance survives it. Nothing has told this screen how the money lands, so it does not say.",
      ruleRef: "BR-CUS-030",
    };
  }
  return {
    key: "customers.moveOut.impact.dunning.stops",
    text: "Stops at the close — nothing is owed once this settles.",
    ruleRef: "BR-CUS-030",
  };
}

/**
 * `Payments` · `Payment plan · 4 of 9 paid`.
 *
 * B19 §15.6 advisory 1: closing ACCELERATES the remaining instalments onto the
 * final bill. `Closed · nothing outstanding` is true only once that has been
 * billed — which is what case 3's own bill line (`Payment plan · remaining
 * accelerated $132.15`) shows. B19 records it as *"unverified across variants —
 * do not build the label as a constant"*.
 */
export function paymentPlanOnClose(
  landing: MoneyLanding | null,
  plan: { paid: number; of: number } | null,
): DerivedSentence | null {
  if (plan === null) {
    return null; // no plan on this account — the row is absent, not empty
  }
  if (landing === "short") {
    return {
      key: "customers.moveOut.impact.plan.accelerated",
      text: "Closed. The instalments still unpaid are accelerated onto the final bill, and what the deposit does not cover is part of the shortfall.",
      ruleRef: "BR-CUS-082",
    };
  }
  if (landing === null) {
    return {
      key: "customers.moveOut.impact.plan.unknown",
      text: "Closes with the account. Whether anything is left outstanding depends on the accelerated instalments meeting the final bill, and how the money lands is not known here.",
      ruleRef: "BR-CUS-030",
    };
  }
  return {
    key: "customers.moveOut.impact.plan.settled",
    text: "Closed, with nothing outstanding — the accelerated instalments are met by this settlement.",
    ruleRef: "BR-CUS-030",
  };
}

/** B19 §15.11's six messages. `on` is the DEFAULT the outcome sets; every one
 *  stays individually togglable once something can record the choice. */
export interface OutgoingMessage {
  id: string;
  label: string;
  channel: string;
  on: boolean;
}

/**
 * ⚠ **THE CAPTURED SELECTION IS INTERNALLY INCONSISTENT AND B19 SAYS SO.** The
 * screenshot is `Refusal · excess` — money owed BACK — and it draws `Deposit
 * refund notice` UNTICKED beside `Shortfall demand letter` TICKED, whose own
 * description reads *"Only when a balance remains after the deposit"*. Drawn as
 * captured it posts a demand letter to a customer owed $13.12.
 *
 * So the two money-dependent ones are computed and the four constants are not:
 * the final bill, the closure confirmation, the owner notice and the SMS go out
 * whatever the landing.
 */
export function outgoingMessageDefaults(landing: MoneyLanding | null): OutgoingMessage[] {
  const refundLeaves = landing === "refund_due";
  const balanceRemains = landing === "short";
  return [
    { id: "final_bill", label: "Final bill", channel: "PDF + email", on: true },
    { id: "closed_confirmation", label: "Account closed confirmation", channel: "Email", on: true },
    { id: "refund_notice", label: "Deposit refund notice", channel: "Email", on: refundLeaves },
    {
      id: "shortfall_letter",
      label: "Shortfall demand letter",
      channel: "Post",
      on: balanceRemains,
    },
    { id: "owner_notice", label: "Notice to the owner", channel: "Email", on: true },
    { id: "move_out_sms", label: "Move-out SMS", channel: "SMS", on: true },
  ];
}

// ── The unit's four dispositions ──────────────────────────────────────────

export interface VacancyDisposition {
  id: string;
  label: string;
  description: string;
  /** BR-SHL-025 — null means it could be recorded; a sentence is why it could
   *  not be. Two of the four post to FREE TEXT and cannot bill anyone. */
  blockedReason: string | null;
  /** The one the unit reaches by DERIVATION if nothing else is decided. */
  isDerivedDefault: boolean;
}

/**
 * B19 §15.10's `★ Unit · the decision`, and **it is the one place on this
 * screen where DEF-650 bites twice.** BR-MET-105 sends the empty unit's base
 * charges to *"the owner / landlord"*; §15.5 records that the owner is FREE
 * TEXT on the premise record. A charge cannot be sent to a name.
 *
 * So the four are not equally buildable, and that is drawn rather than hidden:
 * choices ① and ② post to a real master account or to nobody, and ③ and ④ post
 * to `Ridge Property LLC`, which is a string. Per BR-SHL-025 the two that
 * cannot act carry their reason instead of being dropped.
 */
export function vacancyDispositions(args: {
  commonAreaAccountNo: string | null;
  ownerOnRecord: string | null;
  /** ⛔ DEF-669 — `null` means NOBODY HAS TOLD US, and it is not `true`. The
   *  BR-MET-105a owner column does not exist, so the close-impact read serves
   *  no answer here; typing this `boolean` made the caller default an unread
   *  value to `true` and the screen then asserted "free text" about every
   *  premises in the product. An unmeasured fact states nothing. */
  ownerIsFreeText: boolean | null;
}): VacancyDisposition[] {
  const owner = args.ownerOnRecord ?? "the owner on the premise record";
  const freeText = args.ownerIsFreeText === true
    ? `${owner} is free text on the premise record, not an account, so nothing can be billed or transferred to them until they exist as one (DEF-650).`
    : null;
  const master = args.commonAreaAccountNo;
  return [
    {
      id: "vacant_base_only",
      label: "Vacant · base charges only",
      description:
        master === null
          ? "Service stays live with no occupant. The base charges need a master account to bill to and this premise has none on record."
          : `Service stays live with no occupant. Base charges bill to the master account ${master} so the connection is kept ready.`,
      blockedReason:
        master === null
          ? "There is no common-area account on this premise for the base charges to bill to."
          : null,
      isDerivedDefault: true,
    },
    {
      id: "vacant_service_off",
      label: "Vacant · service off, no billing",
      description:
        "Service is disconnected at the unit. Nothing bills to anyone, and a reconnect fee applies to the next occupant.",
      blockedReason: null,
      isDerivedDefault: false,
    },
    {
      id: "landlord_billed",
      label: "Landlord-billed · between tenants",
      description: `${owner} carries base charges and any usage while the unit is empty — cleaning, showings, works.`,
      blockedReason: freeText,
      isDerivedDefault: false,
    },
    {
      id: "occupied_owner_billed",
      label: "Occupied · owner-billed",
      description:
        "The owner occupies or holds the unit themselves. It never enters a vacant state.",
      blockedReason: freeText,
      isDerivedDefault: false,
    },
  ];
}

// ── S20 step 4 · WHERE A SHORTFALL GOES, AND THE CLERK'S ACT ───────────────
//
// 🔒 MONEY PATH · HUMAN-REVIEW-PENDING — the control below is what moves
// $175.20 of a departed tenant's debt onto a landlord's account. Ledger row:
// 12-governance/09-human-review-ledger.md.
//
// **BR-CUS-097 AS QUALIFIED 2026-08-27 (PO, closing OQ-531's fifth part),
// verbatim:** *"if U1 leave and dont pay $500 then $500 Debt is shifted to
// Owner A, **if clark tied back to A during move out process**"*.
//
// The rule as written on 2026-08-24 reads as AUTOMATIC — *"the residue moves to
// the master account the sub-account hangs off"* — and it is NOT. An automatic
// transfer would move a departing tenant's debt onto a landlord who never
// agreed to it, silently, on every move-out in the product. **The clerk's
// action is the consent**, which is why this is a control a person operates and
// never a consequence the screen states.

/** One transfer target, RESOLVED by the server. Never an input on this screen:
 *  BR-CUS-097 — *"a transfer cannot be built against an ambiguous target"*. */
export interface ShortfallPathTarget {
  target: string;
  available: boolean;
  br_ref: string;
  account_id: string | null;
  account_no: string | null;
  reason: string | null;
}

/** One of `shortfall_path_options()`'s rows (three since 2026-10-12), as the server serves it. */
export interface ShortfallPathOption {
  path: string;
  enabled: boolean;
  br_ref: string;
  reason: string | null;
  targets?: ShortfallPathTarget[];
}

/** The choice as the clerk reads it: what it does, whether it can be done, and
 *  — for the transfer — WHOSE letters it redirects. */
export interface ShortfallChoice {
  path: string;
  label: string;
  description: string;
  blockedReason: string | null;
  /** BR-CUS-082 + OQ-366: what the reminder ladder does if this is chosen. */
  consequence: string;
  /** The resolved master, for the transfer path only. Never an input. */
  targetAccountNo: string | null;
}

/**
 * The paths as choices — PURE, provable without a browser (B13 §1).
 *
 * ⚠ **THE `consequence` FIELD IS WHY THIS IS A FUNCTION AND NOT FOUR
 * LITERALS.** Until 2026-08-27 nobody could say who the reminder ladder chased
 * after a transfer: `BR-CUS-082` restarted it at tier 1, `BR-CUS-097` moved the
 * money, and neither said whose door — this file's own `dunningOnClose` says so
 * in its docstring. `OQ-366`'s closure settles it, and settles it ONLY for a
 * residue a clerk actually tied back. So two of these three paths chase the
 * closed account and one chases the landlord, and which is which is a fact
 * about the CHOICE — it cannot be a constant on the panel.
 */
export function shortfallChoices(options: ShortfallPathOption[]): ShortfallChoice[] {
  const COPY: Record<string, { label: string; description: string }> = {
    collect: {
      label: "Pursue it",
      description: "The balance stays on this account and collections continue against it.",
    },
    payment_plan: {
      label: "Put it on a payment plan",
      description: "The balance stays on this account, in instalments the customer agrees to.",
    },
    transfer: {
      label: "Tie it back to the master account",
      description: "The balance moves to the owner of this premises.",
    },
  };
  return options.map((option) => {
    const copy = COPY[option.path] ?? { label: option.path, description: "" };
    const target = (option.targets ?? []).find((row) => row.available) ?? null;
    const isTransfer = option.path === "transfer";
    return {
      path: option.path,
      label: copy.label,
      description:
        isTransfer && target?.account_no
          ? `${copy.description} On this premises that is ${target.account_no}.`
          : copy.description,
      blockedReason: option.enabled ? null : option.reason,
      consequence: isTransfer
        ? // OQ-366, closed 2026-08-27, stated BEFORE the click — it is the half
          // of the decision a clerk would otherwise meet in a letter.
          "The reminder ladder then follows the master account, restarting at tier 1 — this account is closed by then, so there is nobody on the tenant side left to chase."
        : "The reminder ladder restarts at tier 1 against this closed account. Nothing moves to the owner.",
      targetAccountNo: isTransfer ? (target?.account_no ?? null) : null,
    };
  });
}

/**
 * What each shortfall path would ask for, and who may take it.
 *
 * ⚠ **EXPORTED 2026-09-24 BECAUSE THE DRAWING MERGED TWO TABLES INTO ONE.**
 * `03-bill-and-deposit.png` draws ONE table — *(pick) · Path · Who can · What
 * it needs* — where the six-step shape drew the chooser and *What each one
 * would ask for* as two separate panels. `moveOutTables.ShortfallPaths` reads
 * this, so the two columns are one vocabulary rather than a second copy free
 * to drift from this one.
 *
 * ⚠ **IT SURVIVED A DELETION THAT TOOK ITS NEIGHBOURS.** `EachPathAsks`, which
 * used to be the only reader, is gone with the step it drew; this stayed
 * because what each path NEEDS is a FACT a clerk acts on, not the rationale
 * the rest of that panel carried.
 */
export const PATH_ASKS: Record<
  string,
  // `supervisor` left with write-off (2026-10-12): every remaining path is any clerk's.
  { fields: { key: string; en: string } }
> = {
  collect: {
    fields: { key: "customers.moveOut.pathAsk.collect", en: "A forwarding address" },
  },
  payment_plan: {
    fields: {
      key: "customers.moveOut.pathAsk.paymentPlan",
      en: "Instalments · first payment date · amount each · the customer's agreement",
    },
  },
  transfer: {
    fields: {
      key: "customers.moveOut.pathAsk.transfer",
      en: "The target — the master account or the premises owner — and a reason",
    },
  },
  // ⚠ NO `write_off` — PO 2026-10-12, *"we will not write off at the time of
  // move out"*. Finance or a System Admin writes it off later in Payments.
};

// ══════════════════════════════════════════════════════════════════════════
// PART 3 · THE RENDERERS — Tailwind utilities only (B14 rule 21)
// ══════════════════════════════════════════════════════════════════════════

/**
 * One tagged advisory — B19 draws six tags on this flow (`CHECK`, `BLOCKED`,
 * `FREE TEXT`, `EXPLICIT`, `DEDUCTION ENDS`, `REVERTS`) and each is a rule
 * rather than a note. `blocked` takes B14's danger tier; the rest are neutral,
 * because an advisory that shouts is one nobody reads twice.
 */
export function Advisory(props: {
  tag: string;
  children: ReactNode;
  tone?: "note" | "blocked";
  tracks?: string;
}) {
  const blocked = props.tone === "blocked";
  return (
    <p
      role={blocked ? "alert" : "note"}
      data-advisory={props.tracks ?? props.tag}
      className={
        blocked
          ? "mt-2 flex max-w-prose flex-wrap items-baseline gap-2 border-l-2 border-danger-500 pl-3 text-sm text-danger-700"
          : "mt-2 flex max-w-prose flex-wrap items-baseline gap-2 border-l-2 border-divider pl-3 text-sm text-neutral-700"
      }
    >
      <span className="font-heading text-xs font-semibold uppercase tracking-wide">
        {props.tag}
      </span>
      <span>{props.children}</span>
    </p>
  );
}

/** A label / value line inside a panel body. */
export function ImpactRow(props: { label: ReactNode; children: ReactNode; ruleRef?: string }) {
  return (
    <div
      className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b border-divider py-2 last:border-b-0"
      {...(props.ruleRef === undefined ? {} : { "data-br-ref": props.ruleRef })}
    >
      <span className="text-xs uppercase tracking-wide text-neutral-700">{props.label}</span>
      <span className="min-w-0 max-w-prose text-sm text-text">{props.children}</span>
    </div>
  );
}

/**
 * A value that is an ABSENCE. The `tracks` id rides on `data-` and never
 * appears in the sentence a clerk reads (DEF-332, PO 2026-08-19: our internal
 * ids do not belong on a customer's screen).
 */
export function Absent(props: { children: ReactNode; tracks: string }) {
  return (
    <span role="note" className="max-w-prose text-sm text-neutral-700" data-tracks={props.tracks}>
      {props.children}
    </span>
  );
}

/** The bordered list a set of `ImpactRow`s belongs in. */
export function ImpactList(props: { children: ReactNode }) {
  return <div className="mt-2 flex flex-col">{props.children}</div>;
}

// ══════════════════════════════════════════════════════════════════════════
// PART 4 · THE IMPACT SCREEN — B18 §5.6.5 · B19 §15.10
// ══════════════════════════════════════════════════════════════════════════
//
// The PO asked for *"screen to show all the impact on premises and unit,
// assets, plans & rates, Deposites, payments - or anything that is important"*
// (B18 §5.6.5). B19 §15.10 then captured it panel by panel with its copy.
//
// ⚠ **THE TWO DOCUMENTS DISAGREE ON THE PANEL SET AND NEITHER IS WRONG.** B18
// row 5.7 says *"seven panels"* and lists Unit · Assets · Plan & rates ·
// Deposit · Payments · Open items · Sub-accounts. B19 §15.10's screenshot draws
// SIX under the heading *"Six things change"* — Premises · ★ Unit · Assets ·
// Plans, rates & discounts · Payments · Collections & notices. The union is
// NINE and every one of them is a consequence a clerk has to know about before
// committing, so the union is what renders; the discrepancy is reported rather
// than resolved by dropping two panels.
//
// ⚠ **THE MONEY IS SERVED; SIX OF THE IMPACT FACTS ARE NOT, AND IT SAYS SO PER
// PANEL RATHER THAN ONCE (DEF-669).** `GET /accounts/{id}/close-impact` IS
// mounted and answers the landing and B19 §15.9's money. Premises occupancy,
// the owner, the master account, the vacant base charge and payment-plan
// progress are each another module's and arrive `null`. The panels still
// render, because the SHAPE of the consequence is knowable from
// the rules even when the number is not — `the plan stays with the unit` is
// BR-MET-044 and needs no endpoint — and because a clerk meeting an empty
// screen learns nothing about what closing an account does.

// ══════════════════════════════════════════════════════════════════════════
// PART 5 · STEPS 3, 4 AND 5, BUILT TO THEIR DRAWING (blueprint p112–p115)
// ══════════════════════════════════════════════════════════════════════════
//
// **PO ruling 2026-09-19, step by step, against a mapped table of all six
// steps** — *"we need to do it"* (step 3) · *"this is correct"* (step 4's
// drawing) · *"we should build this"* (step 5) · *"Can you build this using
// the drawing and match the screena nd process"*. And the standing instruction
// of the same day: *"when you build the product screens for detials view they
// should exactly match with drawing in the blueprint document"*.
//
// ⚠ **BUILT FROM THE IMAGES, NOT FROM A TEXT DUMP** (B14 rule 42): p110–p115
// of `05-prototype/02 Accounts Menu Blueprint.pdf` were rendered and READ. The
// extractor loses which of two columns a block is in, what is a TABLE and what
// is a list of facts, and where one screen ends and the next begins — all
// three of which this part depends on. Each drawn screen SPANS two PDF pages:
// step 3 is the bottom of p112 plus the top of p113, and so on.
//
// ⚠ **RULE 37 — EVERY FIGURE DRAWN IS AN ILLUSTRATION.** `$71.40`, `634 kWh`,
// `$186.40`, `$153.50` give the SHAPE and are no tenant's numbers. Not one of
// them appears below. Every figure on these screens comes off a served payload
// or renders as a stated absence.
//
// ⚠ **AND THE MARGIN PROSE IS THE DOCUMENT EXPLAINING ITSELF, NOT SCREEN
// COPY.** The red boxes, the dashed panels and the grey paragraphs under the
// drawn tables are the blueprint's own commentary. B14 rule 33 puts RATIONALE
// at ZERO words on screen, so none of it is transcribed; it is here, in the
// code, which is where rule 33 says it belongs.

/** One money figure as `move_out_settlement._pair` serves it: the 4dp STORED
 *  string and the 2dp DISPLAY string, or two nulls when the term could not be
 *  read. Never a number and never a zero standing in for an absence. */
export interface MoneyAmount {
  stored: string | null;
  display: string | null;
}

const NO_AMOUNT: MoneyAmount = { stored: null, display: null };

function amountOf(raw: unknown): MoneyAmount {
  if (raw === null || typeof raw !== "object") {
    return NO_AMOUNT;
  }
  const pair = raw as { stored?: unknown; display?: unknown };
  return {
    stored: typeof pair.stored === "string" ? pair.stored : null,
    display: typeof pair.display === "string" ? pair.display : null,
  };
}

/**
 * B19 §15.9's ONE subtraction, as `GET /accounts/{id}/close-impact` serves it.
 *
 * Every field is a `MoneyAmount` because **every one of them can be absent**:
 * the settlement fails CLOSED on a term it cannot read, so `landing` comes
 * back null, `gaps` names the reason and every total is `{stored: null,
 * display: null}`. That is the state this product is in TODAY on every account
 * until a final-bill figure is stated, and it is the state these screens are
 * built to render honestly rather than the happy one the drawing shows.
 */
export interface SettlementMoney {
  currency: string | null;
  priorBalance: MoneyAmount;
  finalBill: MoneyAmount;
  exportCredit: MoneyAmount;
  finalBillNet: MoneyAmount;
  outstanding: MoneyAmount;
  depositHeld: MoneyAmount;
  depositInterest: MoneyAmount;
  unappliedCredit: MoneyAmount;
  applied: MoneyAmount;
  net: MoneyAmount;
  shortfall: MoneyAmount;
  excess: MoneyAmount;
  settledFromDeposit: MoneyAmount;
  refundAmount: MoneyAmount;
}

/**
 * The served settlement, mapped. Reads NOTHING it was not sent — an absent
 * block gives fourteen absent figures rather than fourteen zeros.
 *
 * ⚠⚠ **AND THE VERDICT IS DROPPED WHERE THERE IS NO LANDING, WHICH IS NOT
 * TIDINESS — IT WAS `$0.00` ON A REAL SCREEN (`DEF-CUS-5926`, found by walking
 * a booted stack in a browser and by nothing else).** `MoveOutSettlement`
 * fails closed on the LANDING and the TOTALS — `landing: null`, `outstanding:
 * null` — and its docstring says so: *"every gap here fails CLOSED … rather
 * than a landing derived from a term quietly read as zero"*. But
 * `shortfall`, `excess`, `settled_amount` and `refund_amount` are typed
 * `-> Decimal` and **return `ZERO` when `net` is None**, so the payload
 * carries `verdict.shortfall = "0.0000"` under a gap. The screen then printed
 * **`Short by $0.00`** — the claim that this customer owes nothing — three
 * rows under its own sentence *"The subtraction has not run yet"*, and again
 * on step 4, step 5 and step 6's recap.
 *
 * **A zero the arithmetic never reached is not a measurement**, and on a final
 * settlement it is the most consequential claim the screen can make. The four
 * verdict figures are therefore readable ONLY when the server states a
 * landing; the two terms the ACCOUNT answers for — the prior balance and the
 * deposit held — are real reads and survive.
 */
export function settlementMoneyOf(served: Record<string, unknown>): SettlementMoney {
  const outstanding = (served.everything_outstanding ?? {}) as Record<string, unknown>;
  const applied = (served.what_is_applied ?? {}) as Record<string, unknown>;
  const verdictServed = (served.verdict ?? {}) as Record<string, unknown>;
  // No landing ⇒ no verdict. `complete` is the server's own word for it and is
  // read where it is sent; the landing is the fallback, because both are false
  // under exactly the same gaps.
  const decided =
    served.complete === true ||
    (typeof served.landing === "string" && served.landing !== "");
  const verdict: Record<string, unknown> = decided ? verdictServed : {};
  return {
    currency: typeof served.currency === "string" ? served.currency : null,
    priorBalance: amountOf(outstanding.prior_balance),
    finalBill: amountOf(outstanding.final_bill),
    exportCredit: amountOf(outstanding.export_credit),
    finalBillNet: amountOf(outstanding.final_bill_net),
    outstanding: amountOf(outstanding.total),
    depositHeld: amountOf(applied.deposit_held),
    depositInterest: amountOf(applied.deposit_interest),
    unappliedCredit: amountOf(applied.unapplied_credit),
    applied: amountOf(applied.total),
    net: amountOf(verdict.net),
    shortfall: amountOf(verdict.shortfall),
    excess: amountOf(verdict.excess),
    settledFromDeposit: amountOf(verdict.settled_from_deposit),
    refundAmount: amountOf(verdict.refund_amount),
  };
}

// ── The final-bill preview — `GET /accounts/{id}/final-bill-preview` ────────
//
// **THE KEYSTONE THE 2026-09-19 RULING NAMES.** Steps 3, 4 and 5 were one
// blocked chain: the settlement takes a final-bill figure the CALLER states,
// no caller ever stated one, so the landing was null on every account and step
// 4's radios rendered live over a POST that refused every time.
//
// ⚠ **IT PRICES AND POSTS NOTHING.** The Billing blueprint settles it on p112
// in its own dashed panel — *"NO BILL IS ISSUED BY THIS SCREEN"* — which is
// what makes it safe to run inside a wizard a clerk may abandon.
//
// ⚠ **THE DRAWN TABLE IS ASSEMBLED FROM BOTH CALLS.** The priced rows come
// from here; the *Unbanked export credit* row and *Final bill, net* come from
// `close-impact`'s `everything_outstanding`, because BR-MET-107's credit is
// METERING's fact applied by the SETTLEMENT. Neither half computes the
// other's figure — subtracting the credit here would double-count it.

export interface FinalBillLine {
  description: string | null;
  amount: string | null;
  quantity: string | null;
  unit: string | null;
  estimated: boolean;
  /**
   * ⚠ **THE DRAWN TABLE'S FIRST COLUMN, AND THE PORT WAS THROWING IT AWAY.**
   * `03-bill-and-deposit.png` draws *Service · Line · Period · Quantity ·
   * Amount*, so *Water · Base charge* is two columns and not one string. The
   * server has served `service` on every priced line since `one_time._line_body`
   * was written — *"`charge_id`, `tax_id`, `service` and `tariff_version_id` are
   * the line's IDENTITY"* — and this port read four of the row's ten keys.
   *
   * ⚠ **IT IS A SERVICE CODE AND IT IS NOT THE VISIBLE VALUE OF A FIELD
   * (B14 rule 31).** What the column renders is the code's own catalogue name,
   * the way every other service badge in the product reads it.
   */
  service: string | null;
  /** `34 kgal @ $2.4500` is quantity, unit and THIS — the engine's own rate,
   *  already beside the line on a printed bill. A flat rule states null. */
  unitPrice: string | null;
  /** `kind='tax'` is summarised in the table's Tax row, never drawn as a line —
   *  the drawn rows sum to the Subtotal and the tax is added once beneath. */
  kind: string | null;
}

export interface FinalBillPreview {
  priced: boolean;
  lines: readonly FinalBillLine[];
  total: string | null;
  /**
   * ⚠ **THE DRAWN *Subtotal* AND *Tax* ROWS, AND THIS PORT READ NEITHER.**
   * `final_bill.preview_final_bill` has served `subtotal` and `tax_total`
   * beside `total` since it was written — *"the same four keys `one_time.
   * preview` and the drafted bill return"* — and the wizard read one of the
   * four. The drawn table's three closing rows are these plus `total`, and
   * they are the ENGINE's own figures: nothing here adds a line to reach a
   * subtotal or applies a rate to reach a tax. **Summing the drawn rows to
   * check them is what the drawing is for; computing them is billing's
   * (BR-CUS-037 — customers may not price a bill).**
   */
  subtotal: string | null;
  taxTotal: string | null;
  currency: string | null;
  periodStart: string | null;
  periodEnd: string | null;
  /**
   * **`DEF-CUS-5931` — this figure was priced from reads NOBODY HAS COMMITTED**,
   * the ones the clerk keyed on step 2 (PO 2026-09-20, *"option b is correct"*).
   * It is a different claim from a figure priced off a committed read, so the
   * screen states it; the reads themselves still commit with the close.
   */
  fromUncommittedReads: boolean;
  /** The server's own refusal code. `data-` only; never a word on screen. */
  unavailable: string | null;
  /**
   * ⚠ **THE ENGINE'S OWN SENTENCE, AND THE HALF THAT WAS BEING THROWN AWAY
   * (`DEF-CUS-6464`).** `priced_unavailable` carries `{reason, detail}` and this
   * port kept only the `reason` — a code, which B14 rule 32 forbids showing a
   * clerk, so there was nothing left that could be rendered at all.
   *
   * The `detail` is the ACTIONABLE half: *"base charge code BASE-E prices per
   * connection size and states no amount for size None — price that size on the
   * charge code, or record the connection's size"*. It names the thing a clerk
   * can go and fix. It is the server's own words, quoted verbatim rather than
   * paraphrased into a catalogue key, exactly as `oneTimeConfirmShared.ts` does
   * one flow over — a paraphrase here would be a second copy of an engine
   * message free to drift from the engine.
   */
  unavailableDetail: string | null;
  /** ⚠ `unavailableDetail` IS THE ENGINE'S OWN SENTENCE and nine of the rating
   *  chain's raise sites put a database uuid in it (`DEF-RAT-7991`, B14 rule
   *  31). These two are the server's CLERK sentence, and `refusalSentence` is
   *  what chooses between them at the two places this preview is rendered. */
  unavailableKey?: string | null;
  unavailableParams?: Record<string, unknown> | null;
  /** `DEF-BIL-10052` — every value the draft is missing, when
   *  `unavailable === "values_missing"`: the service, its meter numbers, and
   *  `reading` or `estimate_no_history`. */
  missing?: readonly FinalBillMissingValue[];
}

export interface FinalBillMissingValue {
  service: string;
  meters: readonly string[];
  what: "reading" | "estimate_no_history" | string;
}

export interface FinalBillPreviewPort {
  read: (
    accountId: string,
    movedOutOn: string,
    keyedReads?: readonly Record<string, unknown>[],
  ) => Promise<FinalBillPreview>;
}

/**
 * What a clerk reads when the closing period cannot be priced — `DEF-RAT-7991`.
 *
 * `unavailableDetail` is the engine's own sentence and it is still what shows
 * where the server states no clerk key and the sentence names no uuid
 * (`DEF-CUS-6464`: it is the ACTIONABLE half). `refusalSentence` is the one
 * reader that decides, and both render sites of this preview call it.
 */
export function finalBillRefusal(
  preview: {
    unavailableKey?: string | null;
    unavailableParams?: Record<string, unknown> | null;
    unavailableDetail?: string | null;
  } | null,
  t: Translator,
): string | null {
  if (preview === null) {
    return null;
  }
  return refusalSentence(
    {
      message_key: preview.unavailableKey ?? null,
      message_params: preview.unavailableParams ?? null,
      detail: preview.unavailableDetail ?? null,
    },
    t,
  );
}

export function finalBillPreviewPort(client: ApiClient = api): FinalBillPreviewPort {
  return {
    read: async (
      accountId: string,
      movedOutOn: string,
      keyedReads: readonly Record<string, unknown>[] = [],
    ): Promise<FinalBillPreview> => {
      // ⚠ **THE LEADING SLASH IS LOAD-BEARING — `DEF-CUS-4010` and
      // `DEF-CUS-5072`, twice on this very screen.** Without it `apiPath`
      // welds the tenant segment and `accounts` into one word and the request
      // 404s on every tenant. `apiPathLiteral.guard.test.ts` refuses it now.
      const path =
        `/accounts/${accountId}/final-bill-preview` +
        `?moved_out_on=${encodeURIComponent(movedOutOn)}`;
      // ⚠ **A `POST` THAT WRITES NOTHING, AND ONLY WHEN THERE IS SOMETHING TO
      // SEND (`DEF-CUS-5931`).** The keyed capture is eleven registers wide on
      // a campus and does not belong in a query string; the door answers the
      // identical payload either way, and `priced_from_uncommitted_reads` is
      // what says which reads it priced. With nothing keyed this is the GET it
      // has always been — byte for byte the same request.
      const answer =
        keyedReads.length === 0
          ? await client.get<Record<string, unknown>>(path)
          : await client.post<Record<string, unknown>>(path, { final_reads: keyedReads });
      const served = answer.data ?? {};
      const rows = Array.isArray(served.lines) ? (served.lines as Record<string, unknown>[]) : [];
      const gap = (served.priced_unavailable ?? null) as
        | {
            reason?: unknown;
            detail?: unknown;
            message_key?: unknown;
            message_params?: unknown;
            missing?: unknown;
          }
        | null;
      return {
        priced: served.priced === true,
        lines: rows.map((row) => ({
          description: typeof row.description === "string" ? row.description : null,
          amount: typeof row.amount === "string" ? row.amount : null,
          quantity: typeof row.quantity === "string" ? row.quantity : null,
          unit: typeof row.unit === "string" ? row.unit : null,
          estimated: row.estimated === true,
          service: typeof row.service === "string" ? row.service : null,
          unitPrice: typeof row.unit_price === "string" ? row.unit_price : null,
          kind: typeof row.kind === "string" ? row.kind : null,
        })),
        total: typeof served.total === "string" ? served.total : null,
        subtotal: typeof served.subtotal === "string" ? served.subtotal : null,
        taxTotal: typeof served.tax_total === "string" ? served.tax_total : null,
        currency: typeof served.currency === "string" ? served.currency : null,
        periodStart: typeof served.period_start === "string" ? served.period_start : null,
        periodEnd: typeof served.period_end === "string" ? served.period_end : null,
        fromUncommittedReads: served.priced_from_uncommitted_reads === true,
        unavailable: typeof gap?.reason === "string" ? gap.reason : null,
        unavailableDetail: typeof gap?.detail === "string" ? gap.detail : null,
        unavailableKey: typeof gap?.message_key === "string" ? gap.message_key : null,
        missing: Array.isArray(gap?.missing)
          ? (gap.missing as Record<string, unknown>[]).map((row) => ({
              service: typeof row.service === "string" ? row.service : "",
              meters: Array.isArray(row.meters)
                ? (row.meters as unknown[]).filter((m): m is string => typeof m === "string")
                : [],
              what: typeof row.what === "string" ? row.what : "reading",
            }))
          : [],
        unavailableParams:
          gap?.message_params !== null && typeof gap?.message_params === "object"
            ? (gap.message_params as Record<string, unknown>)
            : null,
      };
    },
  };
}

/**
 * The plan the unit stands on, as the drawing writes it: `code · name · v1`.
 *
 * **PO 2026-09-19 on step 1, verbatim: *"you should have plan name also in
 * this - all other correct"*.** Pure so it can be proved without a mount, and
 * it states the absence rather than composing a line out of nulls — three
 * different real absences arrive here as the same null (the account names no
 * unit, the unit stands on no plan, the plan is no longer published).
 */
export function unitPlanLine(plan: AccountUnitPlan | null | undefined): string | null {
  if (plan === null || plan === undefined) {
    return null;
  }
  const parts = [plan.code, plan.name].filter((part): part is string => (part ?? "") !== "");
  if (plan.version !== null) {
    parts.push(`v${plan.version}`);
  }
  return parts.length === 0 ? null : parts.join(" · ");
}

/**
 * BR-CUS-056 — the OUTGOING account pays the move day, so the unit is free and
 * the next tenancy starts THE DAY AFTER. Calendar arithmetic on an ISO date
 * with no clock and no timezone in it (gate G6 keeps a clock off a money
 * path); `""` in, `""` out, so an undated wizard states an absence instead.
 */
export function dayAfter(isoDate: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(isoDate)) {
    return "";
  }
  const at = new Date(`${isoDate}T00:00:00Z`);
  if (Number.isNaN(at.getTime())) {
    return "";
  }
  at.setUTCDate(at.getUTCDate() + 1);
  return at.toISOString().slice(0, 10);
}

// ── The drawn matrices ──────────────────────────────────────────────────────
//
// p112–p115 draw SIX small column-headed tables inside these three steps — the
// final bill, the five landings, what the other three ask for, what each
// shortfall path asks for, what the chosen path will do, what we will send and
// what the close does not do. **One component, seven callers**: the skill's
// own §2.3, and the alternative is seven copies drifting apart on a header
// weight. Not `DataTable` — that is the LIST table with its toolbar, its
// pagination and its column chooser, and none of these is a list.

export interface MatrixColumn {
  key: string;
  label: string;
  /** Money and counts sit right, as B14 has it. Text sits left. */
  numeric?: boolean;
}

export interface MatrixRow {
  key: string;
  /** A cell is a NODE, because half of these are a figure or a stated absence
   *  rather than a string — typing it `string` is how a row that should have
   *  said *not served* comes to say nothing at all. */
  cells: Record<string, ReactNode>;
  strong?: boolean;
}

export function MoveMatrix(props: {
  columns: readonly MatrixColumn[];
  rows: readonly MatrixRow[];
  tracks: string;
}) {
  return (
    <table className="mt-2 w-full text-sm" data-move-matrix={props.tracks}>
      <thead>
        <tr className="border-b border-neutral-300 text-left text-xs uppercase tracking-wide text-neutral-600">
          {props.columns.map((column) => (
            <th
              key={column.key}
              scope="col"
              className={
                column.numeric
                  ? "px-2 pb-1 text-right font-medium first:pl-0 last:pr-0"
                  : "px-2 pb-1 text-left font-medium first:pl-0 last:pr-0"
              }
            >
              {column.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {props.rows.map((row) => (
          <tr
            key={row.key}
            className={
              row.strong
                ? "border-b border-neutral-300 font-semibold last:border-0"
                : "border-b border-neutral-100 last:border-0"
            }
            data-move-row={row.key}
          >
            {props.columns.map((column) => (
              <td
                key={column.key}
                // ⚠ **THE COLUMN GAP IS LOAD-BEARING AND WAS MISSING — found in
                // a browser on ACC-06 step 4.** With no horizontal padding the
                // closing reading `1943` and the read date `09/30/2026` render
                // as `194309/30/2026`, and the two headers above them as
                // `CLOSING READINGREAD DATE`. A right-aligned number with the
                // next cell hard against it is unreadable at six columns; at
                // three it happens to look fine, which is why it survived.
                // B14 rule 44 — our spacing scale decides how a table is
                // built, and it is one step of it either side.
                className={
                  column.numeric
                    ? "px-2 py-2 text-right tabular-nums first:pl-0 last:pr-0"
                    : "px-2 py-2 text-left first:pl-0 last:pr-0"
                }
              >
                {row.cells[column.key] ?? null}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** A figure, or the stated absence in its place. **Never a zero** — on a final
 *  settlement `$0.00` is the claim that this customer owes nothing. */
export function Figure(props: {
  amount: MoneyAmount;
  currency: string | null;
  tracks: string;
  t: Translator;
  /** Drawn with a leading minus on the subtraction's applied side. */
  negated?: boolean;
  /** The sentence to show instead. Defaults to the shared one. */
  absent?: string;
}) {
  const { t } = props;
  if (props.amount.stored === null || props.currency === null) {
    return (
      <Absent tracks={props.tracks}>
        {props.absent ??
          t("customers.moveOut.money.notStated", { defaultValue: "Not worked out yet" })}
      </Absent>
    );
  }
  return (
    <span data-figure={props.tracks}>
      {props.negated ? "− " : null}
      <MoneyCell amount={props.amount.stored} currency={props.currency} />
    </span>
  );
}

/**
 * The drawn section heading inside a step.
 *
 * ⚠ **`aside` AND `action` ARE THE DRAWING'S OWN HEADING FURNITURE, NOT NEW
 * IDEAS** — `03-bill-and-deposit.png` draws *The money · Draft bill ·
 * DR-26-0418* and *The draft bill · DRAFT · DR-26-0418 · 01–30 Sep 2026* with
 * *Open the bill* on the right of the same line. They are declared here so
 * every section on both steps shares ONE heading, at one size and one weight
 * (B14 rule 44: the drawing says what is on the screen, our standard says how
 * it is built), rather than three screens each composing their own.
 *
 * ⚠ **`aside` IS A FACT, NEVER A SENTENCE.** B14 rule 33 caps a fact at six
 * words and puts rationale at zero, so a bill reference and its period belong
 * here and an explanation of what a draft is does not.
 */
export function StepSection(props: {
  title: string;
  children: ReactNode;
  tracks: string;
  aside?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="mt-6 first:mt-0" data-step-section={props.tracks}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className="font-heading text-base font-semibold text-text">{props.title}</h3>
          {props.aside === undefined ? null : (
            <span className="text-xs text-neutral-600" data-step-section-aside={props.tracks}>
              {props.aside}
            </span>
          )}
        </div>
        {props.action ?? null}
      </div>
      {props.children}
    </section>
  );
}

/** The drawing's two-column body. Staff app: 1280 and 1440 (PO 2026-09-10), so
 *  the split is `lg` and everything stacks below it rather than shrinking. */
export function StepColumns(props: { left: ReactNode; right: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
      <div>{props.left}</div>
      <div>{props.right}</div>
    </div>
  );
}

// ── STEP 3 · FINAL BILL & DEPOSIT (p112 + the top of p113) ─────────────────

/** One drawn option card. **Not a radio, and that is a reported divergence
 *  from the drawing** — see `DepositDisposition` below. */
function OptionCard(props: {
  label: string;
  chip?: string;
  note?: string;
  selected: boolean;
  tracks: string;
  children?: ReactNode;
}) {
  return (
    <li
      // NO CORNER RADIUS — `tailwind.css` re-declares every `--radius-*` as 0
      // ("the Modernist system is square"), so `rounded-md` would compile to a
      // rule that draws a square corner while telling the next reader the
      // design wanted a curve. `Disclosure.tsx` records the same finding.
      className={
        props.selected
          ? "border border-accent p-3"
          : "border border-dashed border-neutral-300 p-3"
      }
      data-deposit-option={props.tracks}
      data-selected={props.selected ? "yes" : "no"}
    >
      <p className="flex flex-wrap items-baseline gap-2">
        <span
          aria-hidden="true"
          className={
            props.selected
              ? "inline-block h-2.5 w-2.5 rounded-full bg-accent"
              : "inline-block h-2.5 w-2.5 rounded-full border border-neutral-400"
          }
        />
        <span className={props.selected ? "font-semibold text-text" : "font-semibold text-neutral-600"}>
          {props.label}
        </span>
        {props.chip === undefined ? null : (
          <span className="text-xs uppercase tracking-wide text-neutral-600">{props.chip}</span>
        )}
      </p>
      {props.note === undefined ? null : (
        <p className="mt-1 max-w-prose text-sm text-neutral-700">{props.note}</p>
      )}
      {props.children}
    </li>
  );
}

/**
 * *What to do with the deposit* — p112's second section.
 *
 * ⚠ **DRAWN AS FOUR RADIOS AND BUILT AS FOUR STATED OPTIONS, AND THE DRAWING
 * ITSELF IS WHY.** Its own caption reads *"Which of the four is available is
 * decided by the subtraction below, NOT BY THE CLERK"* — so the group is a
 * STATE and never a choice, and `POST /accounts/{id}/move-out` refuses
 * `deposit_disposition` outright (BR-CUS-025: `services.REFUSED_FIELDS`).
 * Four radios over an endpoint that refuses the field is hard-won law 2's
 * mirror — a live control that can never succeed — which is the defect this
 * same lane is fixing one step along. The four are drawn, named, and the three
 * unavailable ones each say WHY, which is the whole of what the drawing asks
 * for. **REPORTED as a divergence rather than taken quietly.**
 *
 * ⚠ **THE TWO FIELDS ARE FACTS FOR THE SAME REASON.** p112 draws *Amount to
 * apply* and *Applied on* as inputs. Nothing accepts either: the settlement
 * applies the WHOLE deposit (`derive(deposit_held=…)`) and has no partial-apply
 * parameter, and the date it accrues interest to is the move-out day the clerk
 * already stated at step 2. Editable boxes that post nowhere would be the same
 * defect one line down.
 */
export function DepositDisposition(props: {
  money: SettlementMoney | null;
  landing: MoneyLanding | null;
  movedOutOn: string;
  /**
   * ⚠ **THE ACCOUNT'S OWN `deposit_on_file`, AS A FALLBACK, AND IT IS NOT A
   * SECOND FIGURE.** `settlement_for` builds `deposit_held` from exactly this
   * column (`derive(deposit_held=account.deposit_on_file)`), so the two cannot
   * disagree — it is one number read one step earlier. Without it a clerk on a
   * deployment whose settlement has not answered sees no deposit at all on the
   * screen whose subject IS the deposit, which the step this replaced did show.
   * **The prior balance gets NO such fallback**: `detail.balance` is a cache
   * nothing writes (DEF-127) and the settlement reads the LEDGER, so those two
   * genuinely can differ and only one of them is the money.
   */
  depositOnFile: string | null;
  currency: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  t: Translator;
}) {
  const { t, landing, money } = props;
  const depositHeld: MoneyAmount =
    money !== null && money.depositHeld.stored !== null
      ? money.depositHeld
      : { stored: props.depositOnFile, display: props.depositOnFile };
  const depositCurrency = money?.currency ?? props.currency;
  const notYet = t("customers.moveOut.deposit.chipNotYet", { defaultValue: "Not settled yet" });
  // ══════════════════════════════════════════════════════════════════════
  // `DEF-CUS-10053` (PO 2026-10-11: *"show me all option dont drop it"*) —
  // ALL options stay drawn, and the one the account's OWN figures land on is
  // the one highlighted, with its amount. Before this, Refund and Hold were
  // `selected={false}` on every account and Refund's chip read *Account is
  // short* even on a `refund_due` landing — so a customer owed money back was
  // shown a disabled Refund. The landing is `move_out_settlement.derive`'s; the
  // clerk still chooses nothing (B19 §15.1).
  // ══════════════════════════════════════════════════════════════════════
  const amount = (value: MoneyAmount | undefined): string =>
    value?.stored ? formatMoney(value.stored, depositCurrency) : "";
  const refundChip =
    landing === null
      ? notYet
      : landing === "refund_due"
        ? t("customers.moveOut.deposit.refundAmount", { amount: amount(money?.refundAmount) })
        : landing === "settled"
          ? t("customers.moveOut.deposit.nothingLeft")
          : landing === "short"
            ? t("customers.moveOut.deposit.refundChip", { defaultValue: "Account is short" })
            : t("customers.moveOut.deposit.nothingLeft");
  const holdChip =
    landing === null
      ? notYet
      : landing === "refused_excess"
        ? t("customers.moveOut.deposit.holdAmount", { amount: amount(money?.excess) })
        : t("customers.moveOut.deposit.holdChip", { defaultValue: "No dispute" });
  const transferChip =
    landing === "refused_other_debt"
      ? t("customers.moveOut.deposit.otherDebtAmount", { amount: amount(money?.excess) })
      : t("customers.moveOut.deposit.transferChip", { defaultValue: "Different flow" });
  return (
    <StepSection
      tracks="deposit"
      // ⚠ **`The deposit`, THE DRAWING'S OWN HEADING (PO-ratified
      // `03-bill-and-deposit.png`, 2026-09-24).** It read *What to do with the
      // deposit* — SIX words where B14 rule 33 caps a LABEL at three, and the
      // drawing had already shortened it. The catalogue entry moves with this
      // default in all eleven languages, because a catalogue BEATS a
      // `defaultValue` and correcting the default alone ships the fix dead
      // (the `DEF-731` shape).
      title={t("customers.moveOut.deposit.title", {
        defaultValue: "The deposit",
      })}
    >
      {landing === null && (
        <p className="m-0 mt-2 text-sm text-neutral-700" data-deposit-pending="">
          {t("customers.moveOut.deposit.pending")}
        </p>
      )}
      <ul className="mt-2 flex flex-col gap-3">
        <OptionCard
          tracks="apply"
          selected
          label={t("customers.moveOut.deposit.apply", {
            defaultValue: "Apply it to the final bill",
          })}
          note={t("customers.moveOut.deposit.applyNote", {
            defaultValue: "Reduces what this customer owes.",
          })}
        >
          <ImpactList>
            <ImpactRow
              label={t("customers.moveOut.deposit.amountToApply", {
                defaultValue: "Amount to apply",
              })}
            >
              <span className="flex flex-col gap-0.5">
                <Figure
                  amount={depositHeld}
                  currency={depositCurrency}
                  tracks="deposit-held"
                  t={t}
                />
                <span className="text-xs text-neutral-600">
                  {t("customers.moveOut.deposit.amountHelp", {
                    defaultValue: "The whole deposit, always.",
                  })}
                </span>
              </span>
            </ImpactRow>
            <ImpactRow
              label={t("customers.moveOut.deposit.appliedOn", { defaultValue: "Applied on" })}
            >
              <span className="flex flex-col gap-0.5">
                {props.movedOutOn === "" ? (
                  <Absent tracks="applied-on">
                    {t("customers.moveOut.deposit.appliedOnAbsent", {
                      defaultValue: "Set the move-out date first.",
                    })}
                  </Absent>
                ) : (
                  <DateCell
                    value={props.movedOutOn}
                    timeZone={props.timeZone}
                    dateFormat={props.dateFormat}
                  />
                )}
                <span className="text-xs text-neutral-600">
                  {t("customers.moveOut.deposit.appliedOnHelp", {
                    defaultValue: "The move-out day.",
                  })}
                </span>
              </span>
            </ImpactRow>
          </ImpactList>
        </OptionCard>

        <OptionCard
          tracks="refund"
          selected={landing === "refund_due"}
          label={t("customers.moveOut.deposit.refund", { defaultValue: "Refund it" })}
          chip={refundChip}
          note={t("customers.moveOut.deposit.refundNote", {
            defaultValue: "Needs a credit balance.",
          })}
        />
        <OptionCard
          tracks="hold"
          selected={landing === "refused_excess"}
          label={t("customers.moveOut.deposit.hold", { defaultValue: "Hold it" })}
          chip={holdChip}
          note={t("customers.moveOut.deposit.holdNote", {
            defaultValue: "Needs an open dispute.",
          })}
        />
        <OptionCard
          tracks="transfer"
          selected={landing === "refused_other_debt"}
          label={t("customers.moveOut.deposit.transfer", {
            defaultValue: "Transfer it to another account",
          })}
          chip={transferChip}
          note={t("customers.moveOut.deposit.transferNote", {
            defaultValue: "Use the transfer flow instead.",
          })}
        />
      </ul>
    </StepSection>
  );
}

/**
 * **THE EMPTY UNIT'S MONTHLY CHARGE, AS ONE LINE — PO ruling 2026-09-24,
 * verbatim: *"(a) Keep, as one line in 'The unit'"*.**
 *
 * ⚠ **PURE, AND EXPORTED, SO THE ARITHMETIC CAN BE PROVED WITHOUT A BROWSER.**
 * It is the one figure on the review that this screen computes rather than
 * reads, so it is the one that needs a test of its own — and a sum written
 * inline inside a 600-line panel is a sum nobody can point a case at.
 *
 * ⚠ **IT ADDS PUBLISHED FIGURES AND PRICES NOTHING** (`BR-CUS-037`: customers
 * may not price a bill). `vacant_base_charges` carries the plan's OWN
 * configured standing charge per service, read verbatim off the server; this
 * adds them up. The per-unit standing charge itself is the rating engine's and
 * is deliberately not served at all, which is why `vacant_base_charge` beside
 * it is null and why nothing here reaches for it.
 *
 * ⚠ **MONEY IS TEXT ALL THE WAY THROUGH — CLAUDE.md hard rule 2.** The sum is
 * done in integer hundredths of the smallest unit off the STORED string and
 * handed back as a string; a `Number` here would be a float on a closing
 * figure. Stored to 4 decimals, displayed at 2 by `MoneyCell`, and **never
 * rounded here**.
 *
 * ⚠ **A SERVICE CHARGING NOTHING IS NOT NAMED.** On the PO's own worked case
 * six services carry a figure and three of them are `0`, so listing all six
 * would tell a clerk the unit is charged for things it is not.
 *
 * Returns null when the read did not answer — never a `$0.00`, which on a
 * closing screen is the claim that an empty unit costs nothing.
 */
export function vacantChargesLine(
  rows: CloseImpact["vacant_base_charges"],
): { total: string; currency: string; services: string[] } | null {
  if (rows === null || rows.length === 0) {
    return null;
  }
  const currency = rows[0].currency;
  let hundredths = 0n;
  const services: string[] = [];
  for (const row of rows) {
    // A decimal string at 4dp (rule 2). Parsed by its two halves so no float
    // ever touches it, and a row this cannot read is a row that must not be
    // silently counted as zero.
    const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(row.stored.trim());
    if (match === null || row.currency !== currency) {
      return null;
    }
    const fraction = (match[3] ?? "").padEnd(4, "0").slice(0, 4);
    const scaled = BigInt(match[2]) * 10000n + BigInt(fraction || "0");
    const signed = match[1] === "-" ? -scaled : scaled;
    hundredths += signed;
    if (signed !== 0n) {
      // ⚠ **THE SERVER'S OWN `name`, NOT A CATALOGUE LOOKUP OF THE CODE.**
      // `vacant_base_charges` carries the service's display name beside its
      // figure; reaching for `services.<code>` instead would be a second
      // vocabulary for one list, and B14 rule 31 keeps the CODE off the screen
      // either way. A row with no name falls back to its code rather than
      // rendering blank — a charge with no service named is worse than one
      // naming a code a clerk can quote at us.
      services.push(row.name === "" ? row.service : row.name);
    }
  }
  const negative = hundredths < 0n;
  const absolute = negative ? -hundredths : hundredths;
  const whole = absolute / 10000n;
  const fraction = (absolute % 10000n).toString().padStart(4, "0");
  return {
    total: `${negative ? "-" : ""}${whole}.${fraction}`,
    currency,
    services,
  };
}

export function CloseImpactPanels(props: {
  detail: AccountDetail;
  impact: CloseImpact | null;
  money: SettlementMoney | null;
  /**
   * ⚠ **`The money` IS HANDED IN, NOT BUILT HERE — B14 rule 43 and the
   * drawing's own instruction that it is ONE component mounted TWICE.**
   * `04-review-and-close.png` draws the identical table step 3 draws, and
   * `moveOutTables.TheMoney` is that table. It arrives as a NODE rather than
   * by import because `moveOutTables.tsx` imports this file — taking it the
   * other way round is an import cycle. The wizard mounts the one component on
   * both steps, which is the property that matters: two renderings of one
   * closing position is how a recap comes to disagree with the step it recaps.
   */
  moneyPanel: ReactNode;
  /** `The meters`, drawn on the review as a READ-ONLY table rather than the
   *  three fact rows this panel used to carry. Handed in for the same reason. */
  metersPanel: ReactNode;
  movedOutOn: string;
  /** What the clerk keyed on step 2, so *Final reads* is a fact and not a
   *  guess. `total` is the registers the unit offers. */
  reads: { taken: number; estimated: number; total: number };
  timeZone: string;
  dateFormat: RegionalDateFormat;
  t: Translator;
}) {
  const { detail, impact, money, t } = props;
  const landing = landingOf(impact);
  const currency = money?.currency ?? detail.currency;
  // ⚠ **A NEW KEY, AND THE OLD ONE IS WHY — hard-won law 1, caught in a
  // browser.** `customers.moveOut.impact.notServed` is in all ELEVEN
  // catalogues reading *"This arrives with the close-impact read, which is not
  // built yet."* The read was MOUNTED on 2026-08-25 (`DEF-669`), so the
  // sentence has been false for three weeks — and **a catalogue entry beats a
  // `defaultValue`**, so correcting the default alone would have shipped the
  // fix dead (the `DEF-731` shape). It is also 15 words where B14 rule 33
  // allows six. Retire the old key; this one states the fact.
  const notServed = t("customers.moveOut.impact.notStated", {
    defaultValue: "The close read does not answer this.",
  });
  const nextDay = dayAfter(props.movedOutOn);
  const vacantCharges = vacantChargesLine(impact?.vacant_base_charges ?? null);
  const dated = (iso: string): ReactNode =>
    iso === "" ? (
      <Absent tracks="moved-out-on">
        {t("customers.moveOut.impact.undated", { defaultValue: "Set the move-out date first." })}
      </Absent>
    ) : (
      <DateCell value={iso} timeZone={props.timeZone} dateFormat={props.dateFormat} />
    );

  // ── What we will send — DERIVED from the landing (B19 §15.11) ────────────
  const messageColumns: MatrixColumn[] = [
    { key: "message", label: t("customers.moveOut.messages.col", { defaultValue: "Message" }) },
    { key: "when", label: t("customers.moveOut.willDo.col.then", { defaultValue: "When" }) },
    {
      key: "state",
      label: t("customers.moveOut.messages.state", { defaultValue: "State" }),
      numeric: true,
    },
  ];
  const messageRows = outgoingMessageDefaults(landing).map((row) => ({
    key: row.id,
    cells: {
      message: row.label,
      when:
        row.id === "final_bill"
          ? t("customers.moveOut.messages.whenBilling", {
              defaultValue: "When billing raises it",
            })
          : t("customers.moveOut.messages.whenClose", { defaultValue: "On close" }),
      state: row.on
        ? t("customers.moveOut.messages.queued", { defaultValue: "Queued" })
        : t("customers.moveOut.messages.notQueued", { defaultValue: "Not queued here" }),
    },
  }));

  /* ⛔ **`notDoRows` IS DELETED WITH THE PANEL IT FED.** It built the six
     rows of *What this close does NOT do* plus a measured seventh, and the
     PO deleted that panel on 2026-09-24 (*"on last step - too much
     information"*). Leaving the computation behind would be dead code that
     reads as something the screen shows — the same class as a component
     nothing mounts, one layer down. `CLOSE_DOES_NOT` and
     `CLOSE_DOES_NOT_KEYS` go with it, and their catalogue keys are retired
     through `10-scripts/i18n_fanin.py` in the same commit. */

  return (
    <div data-close-impact="">
      <StepColumns
        left={
          <>
            {/* ── THE ACCOUNT ──────────────────────────────────────────── */}
            <StepSection
              tracks="account"
              title={t("customers.moveOut.impact.account.title", { defaultValue: "The account" })}
            >
              <ImpactList>
                <ImpactRow
                  label={t("customers.moveOut.impact.account.status", {
                    defaultValue: "Status becomes",
                  })}
                  ruleRef="BR-CUS-030"
                >
                  {props.movedOutOn === "" ? (
                    dated(props.movedOutOn)
                  ) : (
                    <span className="flex flex-wrap items-baseline gap-2">
                      <span>
                        {t("customers.moveOut.impact.account.closed", { defaultValue: "Closed" })}
                      </span>
                      {dated(props.movedOutOn)}
                    </span>
                  )}
                </ImpactRow>
                <ImpactRow
                  label={t("customers.moveOut.impact.account.balance", {
                    defaultValue: "Balance at close",
                  })}
                >
                  {landing === null ? (
                    <Absent tracks="landing">
                      {t("customers.moveOut.money.notStated", {
                        defaultValue: "Not worked out yet",
                      })}
                    </Absent>
                  ) : landing === "short" ? (
                    <span className="flex flex-wrap items-baseline gap-2">
                      <Figure
                        amount={money?.shortfall ?? NO_AMOUNT}
                        currency={currency}
                        tracks="balance-at-close"
                        t={t}
                      />
                      <span>
                        {t("customers.moveOut.impact.account.stillOwed", {
                          defaultValue: "still owed",
                        })}
                      </span>
                    </span>
                  ) : landing === "refund_due" ? (
                    <span className="flex flex-wrap items-baseline gap-2">
                      <Figure
                        amount={money?.refundAmount ?? NO_AMOUNT}
                        currency={currency}
                        tracks="balance-at-close"
                        t={t}
                      />
                      <span>
                        {t("customers.moveOut.impact.account.owedBack", {
                          defaultValue: "owed back",
                        })}
                      </span>
                    </span>
                  ) : (
                    t("customers.moveOut.impact.account.nothingOwed", {
                      defaultValue: "Nothing owed either way",
                    })
                  )}
                </ImpactRow>
                <ImpactRow
                  label={t("customers.moveOut.impact.account.agreements", {
                    defaultValue: "Service agreements",
                  })}
                  ruleRef="BR-CUS-030"
                >
                  {/* ⚠ Found in a browser: undated, this read *"2 end"*, which
                      is a sentence with its object missing. The count is known
                      either way, so the UNDATED case says when instead of
                      trailing off. */}
                  {props.movedOutOn === "" ? (
                    t("customers.moveOut.impact.account.agreementsOnClose", {
                      count: detail.services.length,
                      defaultValue: "{{count}} end on close",
                    })
                  ) : (
                    <span className="flex flex-wrap items-baseline gap-2">
                      <span>
                        {t("customers.moveOut.impact.account.agreementsEnd", {
                          count: detail.services.length,
                          defaultValue: "{{count}} end",
                        })}
                      </span>
                      {dated(props.movedOutOn)}
                    </span>
                  )}
                </ImpactRow>
                <ImpactRow
                  label={t("customers.moveOut.impact.payments.autopayLabel", {
                    defaultValue: "Autopay",
                  })}
                  ruleRef="BR-CUS-059"
                >
                  {detail.autopay
                    ? t("customers.moveOut.impact.account.autopayStops", {
                        defaultValue: "Stops on close",
                      })
                    : t("customers.moveOut.impact.account.autopayNone", {
                        defaultValue: "Not enrolled",
                      })}
                </ImpactRow>
                <ImpactRow
                  label={t("customers.moveOut.impact.account.paperless", {
                    defaultValue: "Paperless",
                  })}
                >
                  {/* ⚠ OPTIONAL IN THE CONTRACT — a bundle deployed against a
                      server that predates the column reads `undefined`, which
                      must degrade to the stated absence and never to "off". */}
                  {detail.paperless === undefined ? (
                    <Absent tracks="paperless">{notServed}</Absent>
                  ) : detail.paperless ? (
                    t("customers.moveOut.impact.account.paperlessKept", {
                      defaultValue: "Kept for the final bill",
                    })
                  ) : (
                    t("customers.moveOut.impact.account.paperlessOff", {
                      defaultValue: "Not enrolled",
                    })
                  )}
                </ImpactRow>
              </ImpactList>
            </StepSection>

            {/* ── THE UNIT ─────────────────────────────────────────────── */}
            <StepSection
              tracks="unit"
              title={t("customers.moveOut.impact.unit.heading", { defaultValue: "The unit" })}
            >
              <ImpactList>
                <ImpactRow
                  label={t("customers.moveOut.impact.unit.fallsToLabel", {
                    defaultValue: "Falls to",
                  })}
                  ruleRef="BR-MET-036"
                >
                  {/* ⚠ Found in a browser: an undated flow rendered *"Vacant,
                      from Set the move-out date first."* — a label welded to
                      an absence, which reads as neither. The absence stands on
                      its own or the fact does. */}
                  {nextDay === "" ? (
                    dated(nextDay)
                  ) : (
                    <span className="flex flex-wrap items-baseline gap-2">
                      <span>
                        {t("customers.moveOut.impact.unit.vacant", {
                          defaultValue: "Vacant, from",
                        })}
                      </span>
                      {dated(nextDay)}
                    </span>
                  )}
                </ImpactRow>
                <ImpactRow
                  label={t("customers.moveOut.impact.unit.standby", {
                    defaultValue: "Vacant standby",
                  })}
                >
                  {/* ⚠ **THREE STATES, AND THE PO RULED THAT TWO OF THEM ARE
                      DIFFERENT FACTS** (2026-08-31): *"no lines because nothing
                      falls to it"* and *"no lines although the premises HAS an
                      unoccupied unit"* — only one is good news. `null` is *the
                      read did not answer*; `available: false` is *this address
                      has no owner account*, which is a FAULT; `available: true`
                      names the account.
                      ⚠ **AND THE REVERSE EDGE RIDES WITH IT**, because the same
                      ruling asks for it in the same section — as TWO sentences
                      of six words rather than the one of thirty that stood on
                      the old panel (B14 rule 33: *two sentences of six beat one
                      sentence of twelve*). */}
                  {impact === null || impact.unit_falls_to === null ? (
                    <Absent tracks="vacant-charge">{notServed}</Absent>
                  ) : impact.unit_falls_to.available ? (
                    <span className="flex flex-col gap-0.5">
                      <span>
                        {t("customers.moveOut.impact.unit.standbyOn", {
                          account: impact.unit_falls_to.account_no ?? "",
                          defaultValue: "Billed to {{account}} while empty",
                        })}
                      </span>
                      <span>
                        {t("customers.moveOut.impact.unit.standbyEnds", {
                          defaultValue: "It stops when someone moves in",
                        })}
                      </span>
                    </span>
                  ) : (
                    t("customers.moveOut.impact.unit.standbyOff", {
                      defaultValue: "This address has no owner account",
                    })
                  )}
                </ImpactRow>
                <ImpactRow
                  label={t("customers.moveOut.field.plan", { defaultValue: "Plan" })}
                  ruleRef="BR-MET-044"
                >
                  {t("customers.moveOut.impact.unit.planStays", {
                    defaultValue: "Stays on the unit",
                  })}
                </ImpactRow>
                <ImpactRow
                  label={t("customers.moveOut.impact.unit.nextOccupant", {
                    defaultValue: "Next occupant can start",
                  })}
                  ruleRef="BR-CUS-056"
                >
                  {dated(nextDay)}
                </ImpactRow>
                {/* ⚠ **REAL MONEY, KEPT BY RULING WHEN THE PANEL AROUND IT
                    WENT.** The PO was shown that an empty unit is charged
                    every month and answered ***"(a) Keep, as one line in 'The
                    unit'"*** (2026-09-24). It used to be one row of the *Not
                    stated here* panel, which is deleted; this is that row, in
                    the place the ruling names.

                    ⚠ **THE TOTAL IS SUMMED FROM THE PLAN'S OWN PER-SERVICE
                    FIGURES AND IS NOT A PRICE THIS SCREEN INVENTED.**
                    `vacant_base_charges` carries each service's configured
                    standing charge verbatim, as a DECIMAL STRING with its
                    CHAR(3) (CLAUDE.md rule 2 — stored to 4, DISPLAYED at 2,
                    never a float). Adding published figures is arithmetic; the
                    per-unit standing charge itself is the rating engine's and
                    is deliberately not served, which is why `vacant_base_charge`
                    beside it is null.

                    ⚠ **ONLY THE SERVICES THAT ACTUALLY CHARGE ARE NAMED.** On
                    the PO's own worked case six services carry a figure and
                    three of them are zero, so naming all six would list a unit
                    as charged for things it is not. B14 rule 33 caps a fact at
                    six words; the total and the services that reach it are the
                    fact, and nothing here says why. */}
                <ImpactRow
                  label={t("customers.moveOut.impact.unit.vacantCharges", {
                    defaultValue: "Vacant charges",
                  })}
                  ruleRef="BR-MET-105"
                >
                  {vacantCharges === null ? (
                    <Absent tracks="vacant-charge">{notServed}</Absent>
                  ) : (
                    <span className="flex flex-wrap items-baseline gap-2">
                      <span className="font-semibold">
                        <MoneyCell
                          amount={vacantCharges.total}
                          currency={vacantCharges.currency}
                        />
                      </span>
                      <span>
                        {t("customers.moveOut.impact.unit.aMonth", { defaultValue: "a month" })}
                      </span>
                      {vacantCharges.services.length === 0 ? null : (
                        <span className="text-neutral-700">
                          {`· ${vacantCharges.services.join(", ")}`}
                        </span>
                      )}
                    </span>
                  )}
                </ImpactRow>
              </ImpactList>
            </StepSection>

            {/* ── THE METERS ───────────────────────────────────────────── */}
            {/* ⚠ **A TABLE, NOT THREE SENTENCES ABOUT ONE — the drawing's own
                shape (`04-review-and-close.png`).** This panel used to say
                *On the unit: W-5024, FS-1001, FS-1002, FS-1003* on one line,
                *They stay fitted — Yes, a move-out removes nothing* and
                *Final reads — 1 taken, 0 estimated*. The drawing replaces all
                three with the meters themselves, a row each, carrying the
                CLOSING READING a clerk keyed on step 2 — which is the fact
                they are confirming and the one none of those sentences
                carried. **`They stay fitted` goes with them** (sheet 2: *both
                rows go*): it is RATIONALE about what a move-out does not do,
                and B14 rule 33 puts that at zero words on screen. */}
            {props.metersPanel}
          </>
        }
        right={
          <>
            {/* ── THE MONEY ────────────────────────────────────────────── */}
            {props.moneyPanel}
            {/* The two CHOICES made on step 3, read back beneath the figures
                they were made against — `04-review-and-close.png` draws them
                as two rows under the table rather than as a panel of their
                own. A FACT each, at six words or fewer (B14 rule 33). */}
            <ImpactList>
              <ImpactRow
                label={t("customers.moveOut.impact.money.deposit", { defaultValue: "Deposit" })}
                ruleRef="BR-CUS-025"
              >
                {t("customers.moveOut.impact.money.applied", {
                  defaultValue: "Applied to the final bill",
                })}
              </ImpactRow>
              <ImpactRow
                label={t("customers.moveOut.subtraction.shortBy", { defaultValue: "Shortfall" })}
              >
                {landing === null ? (
                  <Absent tracks="shortfall">
                    {t("customers.moveOut.money.notStated", {
                      defaultValue: "Not worked out yet",
                    })}
                  </Absent>
                ) : (
                  t(`customers.moveOut.landingName.${landing}`, {
                    defaultValue: landing.replace(/_/g, " "),
                  })
                )}
              </ImpactRow>
            </ImpactList>

            {/* ── WHAT WE WILL SEND ────────────────────────────────────── */}
            <StepSection
              tracks="messages"
              title={t("customers.moveOut.messages.heading", {
                defaultValue: "What we will send",
              })}
            >
              <MoveMatrix columns={messageColumns} rows={messageRows} tracks="messages" />
            </StepSection>

            {/* ⛔ **`What this close does NOT do` AND `Not stated here` ARE
                BOTH DELETED — `DEF-CUS-6499`, PO 2026-09-24: *"on last step -
                too much information"*.** Between them they were six rows and
                six more, four of the second panel's reading *"The close read
                does not answer this."* Every row of both is RATIONALE — what
                the product does not do and why, what a read did not answer —
                which B14 rule 33 puts at ZERO WORDS ON SCREEN and says to
                REMOVE rather than shorten.

                ⚠ **ONE ROW OF THE SECOND PANEL SURVIVES, BY RULING, AND IT
                MOVED RATHER THAN DIED.** The vacant-charge position is REAL
                MONEY — the PO answered *"(a) Keep, as one line in 'The unit'"*
                when shown that an empty unit bills every month — so it is now
                a single line inside *The unit* above, naming the monthly total
                with the services behind it. Nothing explains why.

                Their keys are retired through `10-scripts/i18n_fanin.py` in
                this commit. */}
          </>
        }
      />
    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════════
// PART 4 · THE TWO STANDALONE ENTRY POINTS — PO ruling 2026-08-26
// ══════════════════════════════════════════════════════════════════════════
//
// PO 2026-08-26, verbatim, quoting this repository's own justification back at
// it and overruling it:
//
//   *"Move-in and move-out stay disabled, on purpose: both wizards are built,
//   but a move-in creates the next occupant of a particular account's unit and
//   no account is chosen in that header. The live control is on the account's
//   own page and the button says so. -Enable Move in /move out"*
//
// So the Accounts header's `Move-in` / `Move-out` stop being disabled. What
// they were missing was never the wizard — both have been built and routed
// since 2026-08-11 — it was an ENTRY POINT: a first step that chooses the thing
// the account-scoped URL used to carry.
//
// ⚠ **NEITHER WIZARD GROWS A NEW FIRST STEP.** `MOVE_OUT_STEPS[0]` is already
// `account` ("Find account") and `MOVE_IN_STEPS[0]` is already `unit` ("Unit").
// The two components below are what those steps DRAW when nothing arrived in
// the URL; every step after the first is byte-identical to the account-scoped
// flow, because it is the same code reading the same state.
//
// ⚠ **AND THEY CHOOSE DIFFERENT THINGS, WHICH IS THE PO'S OWN SENTENCE.** A
// move-out closes ONE NAMED ACCOUNT, so its picker is the shared
// `AccountFinder` (DEF-732), exactly as `TransferWizard` and `DisconnectWizard`
// use it. A move-in *"creates the next occupant of a particular account's
// unit"*, so its picker is the UNIT — and the outgoing account is DERIVED from
// it rather than asked for.

/** `MVI-01` — the standalone Move-in entry. Static segment, and it is declared
 *  before any `:id` sibling in `App.tsx` for the reason `/transfers/new`
 *  carries a comment about: the day a move-in DETAIL screen lands, a route
 *  added after this one would make `/move-ins/new` a move-in whose id is the
 *  word "new" (DEF-520, and `apps/customers/api.py` on `accounts/master`). */
export const MOVE_IN_WIZARD_ROUTE = "/move-ins/new";

/** `MVO-01` — the standalone Move-out entry. Same shape, same reason. */
export const MOVE_OUT_WIZARD_ROUTE = "/move-outs/new";

/**
 * Where each standalone wizard's `←` link and its `Save & exit` go.
 *
 * Neither list has a standalone route — both are TABS of the Accounts page
 * (`AccountsListPage`'s `?tab=` query param, `ACCOUNTS_TAB_PARAM`), so the exit
 * is the tab's own address and NOT a fabricated `/move-ins`.
 *
 * ⚠ Written as a QUERY STRING and not as `/accounts/move-ins`. The accounts
 * router carries `accounts/:accountId`, so a second path segment there is read
 * as an ACCOUNT ID and the page would try to load an account called
 * "move-ins". (`TRANSFERS_TAB_PATH` / `DISCONNECTS_TAB_PATH` in
 * `transferDisconnectShared.tsx` are written the path way and hit exactly that;
 * they are another lane's file and are REPORTED, not edited here.)
 */
export const MOVE_INS_TAB_PATH = "/accounts?tab=move-ins";
export const MOVE_OUTS_TAB_PATH = "/accounts?tab=move-outs";

/** BR-MET-036 / `services.CLASS_TERMINAL` — the class, never the label. The
 *  same string `customersShared.isClosedAccount` tests, stated once here so the
 *  filter below and that predicate cannot drift apart. */
export const TERMINAL_BEHAVIOR_CLASS = "terminal";

/**
 * THE UNIT'S MOST RECENT FINISHED TENANCY — the account a standalone move-in
 * follows.
 *
 * ⚠ **THIS IS NOT A NEW RULE AND NOT A NEW ENDPOINT.** It mirrors
 * `apps/customers/selectors.last_closed_account_for_unit` field for field: the
 * TERMINAL behaviour class (never the tenant's renamable label — BR-MET-036
 * keys occupancy off the class) AND a `closed_at` on it, ordered by `closed_at`
 * descending. A terminal account with no `closed_at` is SKIPPED rather than
 * treated as "closed on some unknown day", because BR-CUS-056's boundary is a
 * comparison against that date and there is nothing to compare against.
 *
 * The rows come from the PUBLISHED `GET /accounts?f.unit_id=` — `unit_id` is in
 * `ACCOUNT_FILTERS` and has been served since W2. No route is invented, exactly
 * as `accountFinder.tsx` invented none.
 *
 * ⚠ **ONE DIVERGENCE FROM THE SERVER, STATED RATHER THAN HIDDEN.** The server
 * breaks a `closed_at` tie with `-created_at, -id`; `AccountRow` carries no
 * `created_at`, so this breaks it with `id` alone. Two accounts closing on the
 * SAME DAY on the SAME UNIT is already a state BR-CUS-017 makes unusual, and
 * both would give the identical BR-CUS-056 boundary — but the resolved
 * predecessor is RENDERED by name, number and close date in the step below, so
 * a wrong tiebreak is visible to the clerk rather than silent. REPORTED.
 */
export function lastClosedAccountForUnit(rows: readonly AccountRow[]): AccountRow | null {
  const finished = rows.filter(
    (row) => row.status_behavior_class === TERMINAL_BEHAVIOR_CLASS && row.closed_at !== null,
  );
  const sorted = [...finished].sort((left, right) => {
    const closed = (right.closed_at ?? "").localeCompare(left.closed_at ?? "");
    return closed !== 0 ? closed : right.id.localeCompare(left.id);
  });
  return sorted[0] ?? null;
}

/**
 * What the standalone MOVE-OUT draws as step 1: the shared account finder, and
 * then whatever the chosen account turned out to be.
 *
 * The search itself is the wizard's (`useAccountSearch`), for the reason
 * `accountFinder.tsx` documents — this component is mounted in static-markup
 * tests that provide no `QueryClientProvider`, so a `useQuery` in here would
 * throw in every one of them.
 */
export function MoveOutAccountPick(props: {
  term: string;
  onTermChange: (term: string) => void;
  search: AccountSearchState;
  value: string;
  onChange: (accountId: string) => void;
  /** The chosen account, once it has been read back. Null while nothing is
   *  chosen, while it is loading, and when the read failed. */
  detail: AccountDetail | null;
  loading: boolean;
  failedReason: string | null;
  t: Translator;
}) {
  const { t } = props;
  return (
    <Panel data-move-pick="account">
      <h3 className="font-heading text-base font-semibold text-text">
        {t("customers.moveOut.find.title", {
          defaultValue: "Find the account that is moving out",
        })}
      </h3>
      {/* ⛔ **THE SECTION BLURB IS DELETED — `DEF-CUS-6481`, PO 2026-09-24:
          *"too much text reduce  this"*.** It was 27 words saying three things
          the screen already says: *"A move-out closes one named account"* is
          RATIONALE, which B14 rule 33 puts at ZERO words on screen; *"the same
          search the accounts list uses"* is rationale about our own
          implementation; and the list of what may be typed is what the
          CONTROL's own placeholder offers — which B14 rule 32 forbids
          repeating (*"a row never repeats what its own control offers"*). The
          heading above still names the act, which is rule 32's one sentence
          per section spent where it counts. */}
      <div className="mt-3">
        <AccountFinder
          idPrefix="mvo"
          label={t("customers.moveOut.find.label", { defaultValue: "Account" })}
          required
          term={props.term}
          onTermChange={props.onTermChange}
          search={props.search}
          value={props.value}
          onChange={props.onChange}
          t={t}
        />
      </div>

      {props.value !== "" && props.loading && (
        <Note className="mt-3" data-move-pick-state="loading">
          {t("customers.moveOut.find.reading", {
            defaultValue: "Reading that account…",
          })}
        </Note>
      )}

      {props.failedReason !== null && (
        // BR-SHL-020 — the PLATFORM failed, and it is a different sentence from
        // "no account matches", which the finder itself already states.
        <RefusalStrip className="mt-3" role="alert" data-move-pick-state="failed">
          {props.failedReason}
        </RefusalStrip>
      )}
    </Panel>
  );
}

/**
 * What the standalone MOVE-IN draws as step 1: the VACANT unit, and the
 * outgoing account derived from it.
 *
 * ⚠ **THE UNIT IS THE QUESTION AND THE ACCOUNT IS THE ANSWER — that ordering is
 * the PO's sentence, not a preference.** `POST /accounts/{id}/move-in` takes the
 * OUTGOING account in its path, so the wizard still needs one; what it does not
 * need is a clerk who knows which closed account used to hold the room. The
 * unit is what a clerk has in front of them, and `lastClosedAccountForUnit`
 * turns it into the id the endpoint wants, by the server's own rule.
 *
 * ⚠ **BR-CUS-020: ONLY VACANT UNITS ARE OFFERED, AND ONLY THE SERVER DECIDES.**
 * The options come from `GET /units?f.occupancy=vacant`, the same read
 * `NewAccountWizard`'s unit step uses. An occupied unit is not hidden by this
 * screen; it is never returned to it, and BR-CUS-017 refuses a forged one again.
 *
 * ⚠ **A VACANT UNIT WITH NO PREVIOUS TENANCY IS A FIRST OCCUPANT, AND IT MOVES
 * IN HERE (`DEF-CUS-6353`, decided 2026-09-23).** This step used to refuse it —
 * *"This unit has no finished tenancy to follow … Open it as a new account
 * instead"* — because the only move-in door was account-scoped. The list offered
 * the unit (a never-occupied unit IS vacant) and then refused it, and the PO's
 * move-in approval ruling of the same day sends an approved request for such a
 * unit straight here. `POST /units/{unit_id}/move-in` now takes it under the
 * same guards, so this says who the occupant follows — or that there is nobody
 * — and the flow continues. The refusal key was RETIRED, not reworded.
 */
export function MoveInUnitPick(props: {
  unitId: string;
  onUnitChange: (unitId: string) => void;
  options: readonly { value: string; label: string }[];
  unitsLoading: boolean;
  unitsFailed: boolean;
  /** The derived outgoing account, once the unit's accounts have been read. */
  predecessor: AccountRow | null;
  /** The unit's accounts have been READ (so a null predecessor means "this unit
   *  has no finished tenancy", not "not asked yet" — the DEF-732 distinction). */
  resolved: boolean;
  accountsFailedReason: string | null;
  t: Translator;
  /**
   * **WHAT STEP 1 DRAWS UNDER THE PICKER, INSIDE THE SAME PANEL** — image 30's
   * unit card and its four groups (`CR-171-BRC10` P2.18). With it, the card's
   * *History* group says who the occupant follows, so the two notes below
   * (the predecessor sentence, *First occupant of this unit.*) are not drawn
   * twice. Absent renders exactly what it rendered before.
   */
  children?: ReactNode;
  /**
   * **`DEF-CUS-10190` (PO 2026-10-17) — THE SEARCH ACROSS EVERY UNIT.** When
   * the wizard passes it, it REPLACES the vacant-only select, its help line
   * and its failure strip: *"user wants search all units irrespective of ther
   * tatus"*. The select survives only for a caller that passes nothing.
   */
  unitSearch?: ReactNode;
}) {
  const { t } = props;
  const chosen = props.unitId !== "";
  const card = props.children !== undefined && props.children !== null;
  const searching = props.unitSearch !== undefined && props.unitSearch !== null;
  return (
    <Panel data-move-pick="unit">
      {/* `CR-171-BRC10` P2.18 — image 30 heads this panel *Unit*. */}
      <h3 className="font-heading text-base font-semibold text-text">
        {t("customers.moveIn.find.panel", { defaultValue: "Unit" })}
      </h3>
      {/* ⚠ **NO HINT LINE (`DEF-CUS-6353`, B14 rule 33).** It read *"A move-in
          books the next occupant into a unit that has been left. Choose the
          unit; the account it follows is worked out from it."* — false for a
          first occupant, who follows nobody, and rationale either way. The key
          was retired rather than reworded. */}

      {searching ? <div className="mt-3">{props.unitSearch}</div> : null}
      {searching ? null : (
      <div className="mt-3">
        <SelectField
          id="mvi_unit"
          label={t("customers.moveIn.find.label", { defaultValue: "Vacant unit" })}
          required
          value={props.unitId}
          onChange={props.onUnitChange}
          options={[...props.options]}
          placeholder={
            props.unitsLoading
              ? t("customers.moveIn.find.loading", { defaultValue: "Reading the vacant units…" })
              : t("customers.moveIn.find.choose", { defaultValue: "Choose the unit" })
          }
          // CR-171-BRC10 §2 S9 (PO 2026-10-05, *"this is okay"*) — the fact
          // only; the reason it is so is rationale (B14 rule 33).
          help={t("customers.moveIn.find.help", { defaultValue: "Occupied units aren't listed." })}
        />
      </div>
      )}

      {!searching && props.unitsFailed && (
        <RefusalStrip className="mt-3" role="alert" data-move-pick-state="units-failed">
          {t("customers.moveIn.find.unitsFailed", {
            defaultValue: "The vacant units could not be read, so nothing is listed above.",
          })}
        </RefusalStrip>
      )}

      {props.accountsFailedReason !== null && (
        <RefusalStrip className="mt-3" role="alert" data-move-pick-state="failed">
          {props.accountsFailedReason}
        </RefusalStrip>
      )}

      {!card && chosen && props.resolved && props.predecessor !== null && (
        // ⚠ NAMED, not silent. The predecessor is DERIVED, so the clerk is shown
        // exactly which tenancy this move-in follows and on what date it ended —
        // the date BR-CUS-056 measures the earliest start against.
        <Note className="mt-3" data-move-pick-state="predecessor">
          {t("customers.moveIn.find.follows", {
            defaultValue:
              "This move-in follows {{account}}, whose tenancy of this unit ended on {{closed}}.",
            account:
              props.predecessor.account_no ??
              props.predecessor.name ??
              t("customers.account.noNumber"),
            closed: props.predecessor.closed_at ?? "",
          })}
        </Note>
      )}

      {!card && chosen && props.resolved && props.predecessor === null && (
        // `DEF-CUS-6353` — a FACT, not a refusal: nobody has lived here, and
        // the move-in carries on under the same checks (B14 rule 33, ≤ 6 words).
        <Note className="mt-3" data-move-pick-state="first-occupant">
          {t("customers.moveIn.find.firstOccupant", {
            defaultValue: "First occupant of this unit.",
          })}
        </Note>
      )}
      {props.children}
    </Panel>
  );
}

/**
 * What steps 2..N draw before step 1 has been answered.
 *
 * The rail keeps its full count either way (BR-SHL-046: the number is an INDEX,
 * and a step that drops out misaddresses every step after it), so the later
 * steps render this rather than disappearing — and each one's `validate` is
 * false, so `Continue` cannot walk past the unanswered first step.
 */
export function PickFirstNote(props: { children: ReactNode }) {
  return (
    <Panel data-move-pick="pending">
      <Note>{props.children}</Note>
    </Panel>
  );
}

/**
 * **THE SECTIONS OF ONE WIZARD STEP, STACKED AT 24px.**
 *
 * ⚠⚠ **WHY IT EXISTS — `DEF-CUS-6763`, reported by the PO on `v2.351.98`:**
 * *"spacing problem reason and table start"*. Inside a `Panel`, section-level
 * children are ordinary block elements, so the gap between two of them is
 * whatever the FIRST one's own bottom margin happens to be — and the gap
 * between the move-out's Reason select and the `Meters on this unit` heading
 * measured **0px** in Chromium at 1440, with the heading reading as a caption
 * on the field above it rather than as a new section. The pair below it
 * measured **20px**, from one child's hand-written `mb-5`. **Two neighbouring
 * gaps, two different numbers, neither of them the rule's.**
 *
 * ⚠ **THE NUMBER IS B14 RULE 39's, NOT A JUDGMENT.** That rule ratifies ONE
 * spacing scale and names the step for this job: **`--space-6`, 24px, between
 * SECTIONS** (16px is between blocks and 20px is field-to-field, which is what
 * `FieldStack` already renders INSIDE the field group). B14 rule 44 is why the
 * drawing does not get a say: *the drawing says what is on the screen and how
 * it is arranged; our UI standard says how it is built* — spacing, sizes, the
 * type scale — *and it wins every time*.
 *
 * ⚠ **THE READINGS TABLE'S OWN `mb-5` IS NEUTRALISED HERE RATHER THAN DELETED
 * FROM IT.** `MoveInReadingsTable` carries `mb-5` on its root with the comment
 * *"B14 rule 39's 20px before the next section"* — the right intent reaching
 * for the wrong step of the scale — and that component is mounted by the
 * MOVE-IN wizard too, which this defect did not report and which no lane has
 * walked today. Stripping the margin there would leave the move-in's own step
 * at 0px, which is the defect running backwards. **So the host that stacks
 * owns the rhythm**, and the shared component keeps rendering exactly what it
 * renders everywhere else. `DEF-CUS-6772` carries the move-in half.
 *
 * ⚠ **IT LIVES IN THIS FILE AND NOT IN THE WIZARD, DELIBERATELY** — the same
 * posture `moveShared.tsx` has recorded since `CR-030` W5. `MoveOutWizard.tsx`
 * is NOT on `styles/route-b-migrated.txt`, so `G31` owns it and a Tailwind
 * utility written there is a RED GATE at merge; every utility these two
 * wizards need lives in a file `routeBUtilities.test.ts` owns instead, and the
 * wizards stay at ratchet 0. Reaching for a stylesheet class is what B14 rule
 * 21 forbids.
 */
export function WizardSectionStack(props: { children: ReactNode }) {
  return (
    <div
      className="flex flex-col gap-6 [&_[data-move-in-readings]]:mb-0"
      data-wizard-sections=""
    >
      {props.children}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W5 tasks 5.1 + 5.7 (B18 §4.2 · §5.6.5) · B19 §15.7 · §15.10
// generated: 2026-08-24 by the CR-030 W5 FRONTEND lane (N2)
// amended: 2026-08-26 by lane SCREENVOICE — **DEF-731**. `parkStoreBlockedReason`
//         explained the missing store in the codebase's terms on screen. The
//         explanation is now this function's docstring and the copy is the
//         clerk's. ⚠ It asks for a NEW key, `customers.move.park.notAvailable`:
//         `customers.move.park.noStore` is in all ELEVEN catalogues holding the
//         reported sentence, and a catalogue beats a `defaultValue` — rewriting
//         the default alone would have shipped the fix dead. RETIRE the old key.
// amended: 2026-08-26 by lane MOVEENTRY — **PO ruling** *"-Enable Move in
//         /move out"*. PART 4 adds the two standalone entry points'
//         route constants, `lastClosedAccountForUnit` (the client-side mirror of
//         `selectors.last_closed_account_for_unit`) and the three components the
//         two wizards' first steps draw when nothing arrived in the URL. They
//         live HERE for the reason the impact screen does: every Tailwind
//         utility stays in a file `routeBUtilities.test.ts` owns, so
//         `MoveInWizard.tsx` and `MoveOutWizard.tsx` add no class and stay under
//         G31 at ratchet 0.
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: tsc✔ eslint✔ vitest✔ · G31 skips this file (Route B) and
//        routeBUtilities.test.ts owns it instead
// exceptions: E3 `wizardParkPort` and `closeImpactPort` return null — neither
//   endpoint exists, and both were grepped for rather than assumed · E3 no
//   money figure is rendered from a literal anywhere in this file
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
