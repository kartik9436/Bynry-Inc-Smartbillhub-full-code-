// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W7 — `TRF-02.1`…`TRF-02.5` (B18 §5.7.7) and `DSC-02.1`…
//           `DSC-02.5` (B18 §5.8.7), both captured from the drawing 2026-08-25.
//           This file holds what BOTH wizards need: the two step lists, the two
//           routes, and the vocabularies — every one of them lifted from
//           `apps/customers/disconnects.py` rather than typed out of the
//           drawing, so a screen cannot offer a value the service refuses.
// Rules:    BR-SHL-046 (ONE declared step list per flow — DEF-648) ·
//           BR-SHL-025 (a control that cannot act is DISABLED WITH ITS REASON) ·
//           BR-CUS-103 · BR-CUS-104 · BR-CUS-105 (the three PO rulings of
//           2026-08-25 that make `DSC-02.4`'s drawn consequences panel WRONG —
//           see §3 below) · B14 rule 21 (this file declares no stylesheet class)
// Questions: OQ-374 · OQ-382 · OQ-383 · OQ-384 · OQ-385 — all OPEN, all touching
//           these two screens, each named at the control it disables.
// Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.7.7 · §5.8.7
// Tests:    TransferWizard.test.tsx · DisconnectWizard.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · WHY THE VOCABULARIES ARE COPIED FROM PYTHON AND NOT FROM THE DRAWING
// ══════════════════════════════════════════════════════════════════════════
// `disconnects.schedule_cut` refuses a reason outside `CUT_REASONS`, a
// treatment outside `SERVICE_TREATMENTS` and a deposit disposition outside
// `DEPOSIT_DISPOSITIONS` — each with a sentence saying that a sixth value is
// *"a new ground for taking away somebody's supply, and it needs a ruling
// rather than a string"*. So a picker built from the drawing's prose would
// produce values the only door in the product rejects. Each list below names
// the Python constant it mirrors.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · THE RESTRICTOR IS DRAWN AS THE DEFAULT FOR WATER AND IS REFUSED BY NAME
// ══════════════════════════════════════════════════════════════════════════
// `DSC-02.1` draws three treatments per service and captions the drawn case
// *"Cutting electric and sewer · restricting water rather than cutting it …
// which many jurisdictions require for water"*. `assert_treatments_expressible`
// raises on `restrictor`: the schema holds cut and not-cut, and a restricted
// service is neither. **OQ-385** is the actual blocker and it is a MONEY
// question — *"what is a restricted service charged?"* — so the option renders
// DISABLED carrying that sentence rather than being deleted (a deleted option
// tells a clerk the product has an opinion; a disabled one tells them the
// truth).
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · ⛔ `DSC-02.4`'s CONSEQUENCES PANEL IS STALE AND THE RULES ARE NOT
// ══════════════════════════════════════════════════════════════════════════
// The drawing's `Will` column, captured the same morning these rules were
// signed, says two things that the PO reversed the same day:
//
//   · *"Keep charging base and standing charges — a disconnected account still
//     accrues"* → **BR-CUS-103 REVERSES IT.** PO 2026-08-25, closing OQ-380,
//     answering *"does base keep running after a cut?"* — **"no"**. Base stops
//     AT THE CUT. `A-11488`, cut 2026-08-18 owing $612.75, still owes $612.75 a
//     month later.
//   · The reconnection fee dated *"When service is restored"* in the fee table
//     and *"Add … to the balance"* in the Will column → **BR-CUS-104 SETTLES IT
//     AT THE CUT.** PO verbatim: *"does reconnection need $8,315.00 - this is
//     correct"* — `A-11340` owes $8,240.00, the fee is its tenant's `CC-RECON`
//     figure, and the amount to clear for reconnection is the sum of the two.
//   · **BR-CUS-105** is the property the two produce together: from the cut
//     date on, nothing the passage of time does changes what a cut customer
//     owes.
//
// **So the screen is drawn from the RULES, and the superseded drawn sentence is
// kept beside its supersession rather than deleted** — the same posture
// `disconnects.CUT_WILL` takes in Python, and for the same reason: a reader
// holding r10 next to this product has to be able to find the sentence and be
// told it no longer binds.
//
// ⚠ **AND NO FIGURE IN THIS FILE IS A MONEY LITERAL.** `$75.00` is Brazos
// Bend's configured `CC-RECON` amount, not the product's (BR-BIL-007), and
// `$8,315.00` is one account's arithmetic. Both appear here ONLY inside quoted
// rule text describing a worked example, never as a value any screen renders.
import type { ReactNode } from "react";

import { Note } from "@/components/TextBits";

import type { FlowStepDef } from "./moveShared";
import type { Translator } from "./newConnectShared";

export type { Translator };

// ══════════════════════════════════════════════════════════════════════════
// 4 · THE TWO ROUTES, DECLARED ONCE
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **TOP-LEVEL AND STATIC, NOT ACCOUNT-SCOPED.** Move-in and move-out hang off
// `:accountId` because their endpoints do (`POST /accounts/{id}/move-out`), and
// neither of these does: `transfers.start_transfer` takes `from_account_id` in
// its PAYLOAD, because `TRF-02.1` is *"Search the account they are leaving"* —
// finding the account is step 1 of the flow, not a prerequisite of reaching it.
// `DSC-02.1` is the same shape (*"Customer, account #, address, or meter #…"*).
//
// ⚠ **`new` IS A STATIC SEGMENT AND IS DECLARED FIRST IN `App.tsx`.** Neither
// path has a sibling `:id` route today, so the ordering buys nothing YET — and
// it is written down because the day a transfer detail screen lands, a route
// added after this one would make `/transfers/new` a transfer whose id is the
// word "new". That is the trap `apps/customers/api.py` carries a comment about
// on `accounts/master`, and DEF-520 is the premises runner learning it the hard
// way.

/** `TRF-02` — the five-step transfer wizard. */
export const TRANSFER_WIZARD_ROUTE = "/transfers/new";

/** `DSC-02` — the five-step disconnect wizard. */
export const DISCONNECT_WIZARD_ROUTE = "/disconnects/new";

/**
 * The query parameter that opens `DSC-02` with step 1's account ALREADY CHOSEN.
 *
 * ⚠ **IT IS A PREFILL AND NOT A LOCK.** Step 1 stays editable: a clerk who
 * arrives from the wrong account must be able to correct it without going back
 * to a list, and the wizard's validation is unchanged — the account is still
 * required, still fetched, and the restricted-service refusal still fires.
 * Nothing about the flow depends on how the clerk got here.
 *
 * Added 2026-09-07 for the S21 icon rail's ⚡ glyph (`DEF-CUS-4631`): the rail
 * is the screen a clerk is actually standing on when they decide to disconnect,
 * and sending them to a wizard that asks them to type the account they are
 * already looking at is how a control that is "live" still fails a person.
 */
export const DISCONNECT_ACCOUNT_PARAM = "account";

/** `DSC-02` opened on ONE account. An empty id gives the plain route, so a
 *  caller with nothing to prefill cannot compose a dangling `?account=`. */
export function disconnectWizardPathFor(accountId: string): string {
  const id = accountId.trim();
  return id === ""
    ? DISCONNECT_WIZARD_ROUTE
    : `${DISCONNECT_WIZARD_ROUTE}?${DISCONNECT_ACCOUNT_PARAM}=${encodeURIComponent(id)}`;
}

/**
 * Where both wizards' `← ` link and their `Save & exit` go. Neither list has a
 * standalone route — both are embedded tabs of the Accounts page (DEF-664) — so
 * the exit is the tab's own address and NOT a fabricated `/transfers`.
 *
 * ⚠ **THEY WERE WRITTEN AS A SECOND PATH SEGMENT AND THAT IS AN ACCOUNT ID
 * (`DEF-CUS-5948`, 2026-09-20).** The accounts router carries
 * `accounts/:accountId`, so `/accounts/transfers` is read as *the account whose
 * id is the word "transfers"* — and every exit from the transfer wizard landed
 * a clerk on **"Accounts · Failed · This account could not be opened. We could
 * not find that."** Walked in Chromium on `brazosbend`: the `← Transfers` head
 * link, `Save & exit` on all five steps, and `TransferDone`'s *Back to
 * transfers* after a committed sale, all three.
 *
 * ⚠ **THE FINDING EXISTED AND HAD NEVER BEEN FILED**, which is why it survived:
 * `moveShared.tsx`'s own `MOVE_INS_TAB_PATH` note names these two constants by
 * name — *"they are written the path way and hit exactly that; they are another
 * lane's file and are REPORTED, not edited here"* — and no register row was
 * ever written, so nothing counted it. That is CLAUDE.md hard rule 4's last
 * paragraph exactly: a finding recorded only in the file you happen to be in is
 * a finding nobody can count. `PARKED_HOME_PATHS` in `wizardPark.ts` has always
 * held the query form, which is why PARKING out of this wizard worked and
 * leaving it did not.
 */
export const TRANSFERS_TAB_PATH = "/accounts?tab=transfers";
export const DISCONNECTS_TAB_PATH = "/accounts?tab=disconnects";

// ══════════════════════════════════════════════════════════════════════════
// 5 · THE TWO STEP LISTS — BR-SHL-046, one declaration each
// ══════════════════════════════════════════════════════════════════════════

/** B18 §5.7.7's five, and they are ALSO `transfers.STEPS` — the service layer
 *  declares the identical five, in the identical order, and its `step` column
 *  is the number this rail shows. Two literals that happen to agree is the
 *  state DEF-648 was found in, so the agreement is asserted by a test rather
 *  than trusted. */
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **THE TRANSFER RAIL IS THE SALE'S RAIL — `DEF-CUS-5075`, 2026-09-12.**
// ══════════════════════════════════════════════════════════════════════════
// It read `Leaving · Final reads · Arriving · Money · Review & confirm` — the
// five steps of the job the PO REPLACED on 2026-09-01, verbatim: *"dont create
// new account - we reassing that account - bascailly I have sold my property -
// so account get transfer to new person or business; if I move to new location
// then it is new Service request"*.
//
// **The server was rewritten that day and the screen was not.** So the wizard
// asked which unit the customer was moving to and on what two dates, and the
// door asked who was BUYING and on what one date: five of the six keys the
// screen sent were ignored, three of the four the server read were never sent,
// and posting it answered `422 VAL-001 customers.transfer.buyer_required` —
// failing at the SECOND of five staged writes, naming a field that appeared on
// none of the five screens. **No property could be sold in this product.**
//
// These five are the blueprint's own drawing at p113–p118, read as images.
//
// ⚠ **FOUR OF THESE KEYS ARE NOT YET IN THE ELEVEN CATALOGUES, AND `G27` IS RED
// ON THEM BY MY HAND. IT IS A HANDOVER, NOT A HOLE, AND HERE IS THE ONE
// COMMAND THAT CLOSES IT:**
//
//     python3 10-scripts/i18n_fanin.py \
//       04-docs/05-modules/03-customers/conformance/CR-094-lane4-i18n-handover.json
//
// All four render correct English today — the rail reads *Find the account · The
// buyer · Date of sale · What they take on · Review & confirm*, verified in
// Chromium at 1280 and 1440 — because every call site is
// `t(labelKey, { defaultValue: en })`. **`G27` cannot see that**, and says so in
// its own docstring: a key handed to the shared kit as CONFIG never appears
// inside a `t(...)` in the file that writes it, so the gate treats it as a raw
// key on screen (`DEF-WRK-3957`, where `work.templates.search` really did
// render literally). Here it is wrong about the symptom and right about the
// gap.
//
// ⚠ **AND IT WAS NOT FIXED HERE ON PURPOSE.** `i18n_fanin.py` rewrites all
// eleven catalogues, and at the time of writing another lane held eight
// uncommitted keys in every one of them — so running it would have published a
// sibling's in-flight work through my commit, which is law 11 mechanism five.
// Widening `g27_translation_keys_baseline.txt` was the other way to a green
// gate and is forbidden outright: it converts a true finding into a permanently
// invisible one. So the translations are written, native-reviewed **OWED**, and
// waiting in the handover file above.
//
// ⊕ **EACH STEP NOW CARRIES ITS OWN PAGE-HEAD TITLE — `DEF-CUS-6542`,
// 2026-09-24.** The wizard's `<h1>` was ONE constant key for all five steps, so
// a clerk standing on the buyer step was told to *"Find the account, and who is
// selling"*. **A screenshot of step 1 — which is what every walkthrough and
// every review had looked at — showed nothing wrong**, which is how it survived
// eight walked screens and four step-2 lanes.
//
// ⚠ **THE TITLES CAME OFF THE DRAWING, AND THEY ARE NOT THE RAIL LABELS.** Read
// off `05-prototype/02 Accounts Menu Blueprint.pdf` (the 281-page edition) **AS
// IMAGES at scale 2** (B14 rule 42) — PDF pages **127, 128, 129, 130 and 131**,
// one per step, plus **p131's review sections**, which name three of the steps
// again in two words each. **THE WORDS HAVE SINCE BEEN SHORTENED BY PO RULING —
// see the block below** — but the field is still not derivable from `en`: three
// of the five titles differ from the rail label sitting beside them.
//
// ⚠ **THE FIVE TITLES ARE SHORTENED TO B14 RULE 33's CAP — PO RULING
// 2026-09-24, VERBATIM: *"4 · The five transfer headings - b  Shorten all five
// to the cap"*.** This block said the opposite for one day, and the reversal is
// written out rather than quietly applied.
//
// **What it replaced:** the five were built exactly as drawn — 7 · 4 · 4 · 5 · 7
// words — on the precedent the PO set the same morning for the move-out's four
// shortfall path names (*"b) Leave as drawn"*). The question was put to them a
// second time FOR THESE FIVE, and they ruled the other way.
//
//     step | as drawn                             | w | ruled            | w
//     -----|--------------------------------------|---|------------------|---
//       1  | Find the account, and who is selling | 7 | Account & seller | 3
//       2  | Who is buying it                     | 4 | The buyer        | 2
//       3  | The date of sale                     | 4 | The date         | 2
//       4  | What the buyer takes on              | 5 | The money        | 2
//       5  | Review — one account, one new owner  | 7 | Review & confirm | 3
//
// ⚠ **STEP 5's DRAWN COUNT IS SEVEN AND THIS MORNING'S RECORD SAYS SIX.** Words
// are whitespace-separated tokens here and in both checks, so the em dash is one
// — which is the STRICTER count and is why `Account & seller` and `Review &
// confirm` are AT the cap rather than under it. The figure put to the PO was
// *"four to seven words"*, which is right on either count.
// ⚠ **THE TWO RULINGS STAND SIDE BY SIDE — THIS IS NOT A GENERAL REVERSAL.** The
// move-out's four labels are still *"Leave as drawn"*, and a lane running a copy
// audit over ACC-06 step 4 must NOT shorten them. Each ruling covers the strings
// it was shown and nothing else; the decision log of 2026-09-24 records both, in
// that order, with the PO's own words on each.
//
// ⚠ **THREE OF THE FIVE ARE NOT INVENTED — THEY ARE THE DRAWING'S OWN SHORT
// NAMES FOR THE SAME CONTENT.** p131 heads the review's own sections *The
// buyer*, *The date* and *The money*, each carrying a `↖ Step N` flag back to
// the step it summarises. So the shortening reaches for the blueprint's
// vocabulary before it reaches for ours, which is as close to rule 41 as a
// ruling to shorten can get. Step 1 keeps BOTH halves the drawn title made a
// point of — the account, and who is selling — in three words; step 5 takes the
// drawn step strip's own name for step 5.
//
// ⚠ **TWO OF THE FIVE NOW EQUAL THEIR RAIL LABEL, AND THAT IS REPORTED RATHER
// THAN DISGUISED.** *The buyer* (step 2) and *Review & confirm* (step 5) are the
// shortest true name for their step and the rail already had it; forcing a
// difference would be inventing a second name for one thing. Steps 1, 3 and 4
// still differ from their rail labels, so `titleKey` stays a field of its own
// and is NOT derivable from `labelKey`.
export const TRANSFER_STEPS: readonly FlowStepDef[] = [
  {
    id: "account",
    labelKey: "customers.transfer.step.account",
    en: "Find the account",
    titleKey: "customers.transfer.stepTitle.account",
    //: drawn *"Find the account, and who is selling"* (p127, 7 words).
    titleEn: "Account & seller",
  },
  {
    id: "buyer",
    labelKey: "customers.transfer.step.buyer",
    en: "The buyer",
    titleKey: "customers.transfer.stepTitle.buyer",
    //: drawn *"Who is buying it"* (p128, 4 words); p131's own section heading.
    titleEn: "The buyer",
  },
  {
    id: "saleDate",
    labelKey: "customers.transfer.step.saleDate",
    en: "Date of sale",
    titleKey: "customers.transfer.stepTitle.saleDate",
    //: drawn *"The date of sale"* (p129, 4 words); p131's own section heading.
    titleEn: "The date",
  },
  {
    id: "takeOn",
    labelKey: "customers.transfer.step.takeOn",
    en: "What they take on",
    titleKey: "customers.transfer.stepTitle.takeOn",
    //: drawn *"What the buyer takes on"* (p130, 5 words); p131's own section
    //: heading over the same balance-and-deposit block.
    titleEn: "The money",
  },
  {
    id: "review",
    labelKey: "customers.transfer.step.review",
    en: "Review & confirm",
    titleKey: "customers.transfer.stepTitle.review",
    //: drawn *"Review — one account, one new owner"* (p131, 6 words). The tail
    //: is the FACT the step exists to show and it is rendered in full below; a
    //: heading is a NAME, so this takes the step strip's own words for step 5.
    titleEn: "Review & confirm",
  },
] as const;

/** B18 §5.8.7's five, named in the frame's own step strip: *"1 Account & reason
 *  · 2 Protections · 3 Notice & date · 4 Fees & consequences · 5 Review"*. */
/**
 * ⚠ **FOUR, AND IT WAS FIVE UNTIL 2026-09-25 — THE DISCONNECT WIZARD REBUILD.**
 *
 * It read *"1 Account & reason · 2 Protections · 3 Notice & date · 4 Fees &
 * consequences · 5 Review"*, which is B18 §5.8.7's five and blueprint
 * p136–p141's five. **It is now `Choose · Check · Schedule · Confirm` — four
 * words, each naming an ACT.**
 *
 * ⚠ **THE ARGUMENT IS THE BILLING BLUEPRINT'S AND IT IS BORROWED ON PURPOSE.**
 * p35: *"Four words, each naming an act"*. `billRunShared.tsx` was built to
 * r10's SIX-step stepper — its own docstring says so, *"the prototype's stepper,
 * in its order and its words"* — while the Billing blueprint draws four and
 * carries a whole carry-over map for converting the six into the four. **A
 * lane obeying the pointer built the wrong shape and passed every check.** This
 * stepper is NOT inherited from the prototype; it is the four the rebuild's own
 * drawings carry (`Step1Choose.png` … `Step4Confirm.png`).
 *
 * **WHAT MOVED, so nothing is lost by subtraction:**
 *
 * | was | is |
 * |---|---|
 * | 1 Account & reason | **1 Choose** — the account, the reason and the services |
 * | 2 Protections | **2 Check** — and the ladder check is HERE ONLY (item 3.2) |
 * | 3 Notice & date | **3 Schedule** — the notice, the date and who goes |
 * | 4 Fees & consequences | **4 Confirm** — with 5 |
 * | 5 Review | **4 Confirm** — the old 4 and 5 were the same screen twice |
 *
 * ⚠ **`parkedDrafts.tsx` READS THIS ARRAY FOR ITS STEP COUNT**, so a draft
 * parked on the old step 5 resumes clamped to step 4 by `clampToSteps` rather
 * than opening on a step that no longer exists. That is the existing clamp
 * doing its job and needs no change; it is named here because it is the one
 * consequence of this edit that reaches data already written.
 */
export const DISCONNECT_STEPS: readonly FlowStepDef[] = [
  { id: "choose", labelKey: "customers.disconnect.step.choose", en: "Choose" },
  { id: "check", labelKey: "customers.disconnect.step.check", en: "Check" },
  { id: "schedule", labelKey: "customers.disconnect.step.schedule", en: "Schedule" },
  { id: "confirm", labelKey: "customers.disconnect.step.confirm", en: "Confirm" },
] as const;

// ══════════════════════════════════════════════════════════════════════════
// 6 · THE DISCONNECT VOCABULARIES — `disconnects.py`'s constants, mirrored
// ══════════════════════════════════════════════════════════════════════════

/** `disconnects.CUT_REASONS`, with `DSC-02.1`'s own plain sentence on each card.
 *
 *  ⚠ **TWO OF THESE FIVE COULD NEVER COMMIT UNTIL `DEF-CUS-6023` (2026-09-20).**
 *  This list sent `tampering` and `abandoned`; `disconnects.CUT_REASONS` and the
 *  `ck_disconnect_case_cut_reason` CHECK constraint hold `tampering_or_theft`
 *  and `premises_abandoned`. **Two strings — and two of the five reasons on a
 *  screen that takes away somebody's supply were refused on the reason alone**,
 *  which is the FIRST check `schedule_cut` runs, before the ladder, the proof or
 *  the date. It survived because the front end asserted its OWN copy back to
 *  itself, and a mirror is green for any five strings.
 *  **`cutReasonVocabulary.test.ts` now reads `disconnects.py` and compares**, so
 *  a sixth reason on the server goes RED here rather than silently never being
 *  offered — hard-won law 2 in its usual costume.
 *
 *  ⛔ **FOUR OF THE FIVE HAVE NO LAWFUL PATH TO A CUT — OQ-382, OPEN, AND IT IS
 *  A DIFFERENT THING FROM THE SPELLING ABOVE.**
 *  `schedule_cut` requires tier 3 of the dunning ladder plus certified proof of
 *  service, which is right for non-payment and impossible for the other four: a
 *  meter found tampered with on a Monday will never reach tier 3. The question
 *  is not the vocabulary, it is **the authority** — which of the four may bypass
 *  the ladder and what each needs instead. Until it is ruled, the four cards
 *  render SELECTABLE-BUT-WARNED rather than hidden: hiding them would tell a
 *  clerk this product has no concept of a safety cut, and choosing one silently
 *  would promise a schedule the service refuses.
 *
 *  ⚠ **SO `reachable` DID NOT GO STALE WHEN THE SPELLING WAS FIXED.** The two
 *  holds are independent: the spelling was refused by `cut_reason_unknown`, the
 *  authority is refused by the tier-3 precondition, and `schedule_cut` branches
 *  on the reason exactly once — to reject an unknown one. **The day OQ-382 is
 *  ruled this flag IS stale**, and that is the mirror of hard-won law 2 (a live
 *  path behind a dead control), so the test that fires on that day is written
 *  beside this one in `cutReasonVocabulary.test.ts`: it reads OQ-382's status
 *  in the register and goes red the moment it stops saying OPEN. */
export const CUT_REASONS = [
  {
    code: "non_payment",
    en: "Non-payment",
    sub: "the ladder has run and they have not paid",
    reachable: true,
  },
  {
    code: "unsafe_installation",
    en: "Unsafe installation",
    sub: "a hazard found on site",
    reachable: false,
  },
  {
    // `disconnects.CUT_REASON_TAMPERING`. **Not `tampering`** — DEF-CUS-6023.
    code: "tampering_or_theft",
    en: "Tampering or theft",
    sub: "the meter has been interfered with",
    reachable: false,
  },
  {
    // `disconnects.CUT_REASON_ABANDONED`. **Not `abandoned`** — DEF-CUS-6023.
    code: "premises_abandoned",
    en: "Premises abandoned",
    sub: "nobody is there and nobody is paying",
    reachable: false,
  },
  {
    code: "customer_asked",
    en: "The customer asked",
    sub: "they want service ended",
    reachable: false,
  },
] as const;

export type CutReason = (typeof CUT_REASONS)[number]["code"];

/** `disconnects.SERVICE_TREATMENTS` — `TREATMENT_FULL` · `TREATMENT_RESTRICTOR`
 *  · `TREATMENT_LEAVE`. The middle one is `expressible: false`; see §2. */
export const SERVICE_TREATMENTS = [
  { code: "full_disconnection", en: "Full disconnection", expressible: true },
  { code: "restrictor", en: "Restrictor / limiter", expressible: false },
  { code: "leave_connected", en: "Leave connected", expressible: true },
] as const;

export type ServiceTreatment = (typeof SERVICE_TREATMENTS)[number]["code"];

export const TREATMENT_FULL: ServiceTreatment = "full_disconnection";
export const TREATMENT_RESTRICTOR: ServiceTreatment = "restrictor";
export const TREATMENT_LEAVE: ServiceTreatment = "leave_connected";

/** `disconnects.DEPOSIT_DISPOSITIONS`. `DSC-02.4` draws ● **Hold it** selected,
 *  and it is also the option that moves no money — which is why `commit_cut`
 *  records it as the default rather than leaving the question open on a cut
 *  account. */
export const DEPOSIT_DISPOSITIONS = [
  { code: "held", en: "Hold it" },
  { code: "applied_against_arrear", en: "Apply it against the arrear" },
] as const;

export type DepositDisposition = (typeof DEPOSIT_DISPOSITIONS)[number]["code"];

export const DEPOSIT_HELD: DepositDisposition = "held";

/** `disconnects.SERVICE_CHANNELS` — `DSC-02.3`'s `HOW IT GOES OUT`, and every
 *  one of them is a claim this release cannot make.
 *
 *  ⛔ **DEF-692.** B18 §5.8.2's own warning: *"there is no email, SMS or print
 *  adapter in this release"*, and `disconnects.DELIVERY_UNAVAILABLE` writes
 *  `delivery_state` NULL for exactly that reason — *"a fabricated delivery
 *  state is what a utility shows a regulator when a customer says they were
 *  never told"*. Certified mail is drawn **Required** and **locked** at tier 3
 *  because it is the legal proof; BR-CUS-100 splits the SEND from the PROOF, so
 *  the proof is a record a person enters and no channel here sends anything. */
/** ⚠ **SIX NOW, AND IT WAS FOUR — `DEF-CUS-5172`, FIXED BY `CR-125-BRC07`.**
 *  Blueprint p138 draws SIX ways a notice goes out and this list held four:
 *  `posted` and `in_app` were both missing. The server has held `posted` in
 *  `disconnects.SERVICE_CHANNELS` and in its own
 *  `ck_disconnect_notice_service_channel` check constraint since W7 — so
 *  recording a notice as having gone out by POST was a thing this product could
 *  store and could not say. CLAUDE.md law 12 in its usual costume: the row
 *  exists, the server accepts it, `tsc` and every test pass, and the option
 *  never appears. `NoticeAndDateStep.tsx` carried a local five-element
 *  `PROOF_CHANNELS` to work around it; that copy is deleted by this commit.
 *
 *  ⚠ **`in_app` IS A SEND AND IS NOT A PROOF, AND THAT SPLIT IS THE WHOLE
 *  REASON `provable` EXISTS.** BR-CUS-100: *"IN-APP DOES NOT SATISFY CERTIFIED
 *  MAIL … proof of service is a legal artefact produced outside this product"*,
 *  and `disconnects.record_proof_of_service` refuses it BY NAME with
 *  `in_app_is_a_send_not_a_proof`. So it is offered where the drawing offers it
 *  — *How the next one goes out* — and never in *Served by*. Reading one list
 *  for both is how a screen offers a clerk an option the server will refuse.
 *
 *  ⛔ **DEF-692.** B18 §5.8.2's own warning: *"there is no email, SMS or print
 *  adapter in this release"*, and `disconnects.DELIVERY_UNAVAILABLE` writes
 *  `delivery_state` NULL for exactly that reason — *"a fabricated delivery
 *  state is what a utility shows a regulator when a customer says they were
 *  never told"*. `delivers` marks the ONE that does: the portal, which is a
 *  page a customer opens rather than a message this product sends. */
export const SERVICE_CHANNELS = [
  { code: "certified_mail", en: "Certified mail", required: true, provable: true, delivers: false },
  { code: "posted", en: "Posted", required: false, provable: true, delivers: false },
  { code: "email", en: "Email", required: false, provable: true, delivers: false },
  { code: "text_message", en: "Text message", required: false, provable: true, delivers: false },
  { code: "door_hanger", en: "Door hanger", required: false, provable: true, delivers: false },
  { code: "in_app", en: "In the portal", required: false, provable: false, delivers: true },
] as const;

/** The five a PROOF may name — `SERVICE_CHANNELS` minus the portal. Derived
 *  rather than typed, so a seventh channel cannot land in one list and not the
 *  other. */
export const PROOF_CHANNELS = SERVICE_CHANNELS.filter((row) => row.provable);

/**
 * `DSC-02.2`'s TEN checks, in the drawn order, each flagged with whether
 * `disconnects.protection_check` can actually answer it.
 *
 * ⛔ **TEN ARE DRAWN, THREE ARE BUILT, AND ONE MORE IS SERVED AS ABSENT.**
 * `protection_check` answers medical, payment-plan and weather-moratorium, and
 * serves `dispute` as `outcome: "unavailable"` — *"nothing in this repository
 * stores a disputed AMOUNT … a green clearance derived from a table that does
 * not exist would authorise a cut"*. The remaining six are **DEF-691** /
 * BR-CUS-101, and each missing one is a household that can be cut when it
 * should not be.
 *
 * ⚠ **SO THE SCREEN NEVER PRINTS `All clear`.** The drawn chip is a summary of
 * ten findings and this product holds three; a green chip over seven unasked
 * questions is the single most dangerous sentence either of these wizards could
 * render. The step shows what was checked and what was not, separately.
 */
export const PROTECTION_CHECKS = [
  { code: "medical", en: "Medical equipment on site", answered: true },
  { code: "moratorium", en: "Weather moratorium", answered: true },
  { code: "life_support", en: "Life support registration", answered: false },
  { code: "age_disability", en: "Age or disability protection", answered: false },
  { code: "payment_plan", en: "Active payment plan", answered: true },
  { code: "dispute", en: "Open dispute", answered: false },
  { code: "assistance", en: "Assistance application pending", answered: false },
  { code: "partial_payment", en: "Recent partial payment", answered: false },
  { code: "notice_served", en: "Notice period served", answered: false },
  { code: "landlord_billed", en: "Landlord-billed premises", answered: false },
] as const;

/** The three `protection_check` really answers, so a screen counts rather than
 *  hard-coding `3` beside a list of ten. */
export function answeredProtections(): readonly string[] {
  return PROTECTION_CHECKS.filter((row) => row.answered).map((row) => row.code);
}

export function unansweredProtections(): readonly string[] {
  return PROTECTION_CHECKS.filter((row) => !row.answered).map((row) => row.code);
}

// ══════════════════════════════════════════════════════════════════════════
// 7 · THE CUT'S CONSEQUENCES — BR-CUS-103/104/105, NOT `DSC-02.4`'s DRAWING
// ══════════════════════════════════════════════════════════════════════════

/** What a cut WILL do. Item 2 is the one the PO reversed; the drawn sentence
 *  travels with it as `superseded` so the screen can show both (see §3). */
export interface CutConsequence {
  code: string;
  en: string;
  /** The drawn sentence this replaces, when it replaces one. */
  supersededDrawn?: string;
  ruleRef: string;
}

export const CUT_WILL: readonly CutConsequence[] = [
  {
    code: "cut_chosen_services",
    en: "Cut the services chosen at step 1 on the scheduled date, leaving the account open.",
    ruleRef: "DSC-02.4",
  },
  {
    code: "base_stops",
    en: "Stop the base and standing charges at the cut. A customer with no service pays nothing for it, so the balance does not grow while the supply is off.",
    supersededDrawn:
      "Keep charging base and standing charges — a disconnected account still accrues",
    ruleRef: "BR-CUS-103",
  },
  {
    code: "fee_at_cut",
    en: "Add the reconnection fee to the balance at the cut, not at restoration. The arrears and the fee together are what must be cleared before service is restored.",
    ruleRef: "BR-CUS-104",
  },
  {
    code: "balance_static",
    en: "Leave the balance unchanged from the cut date onward. It moves only when they pay, when a correction is posted, or when service is restored.",
    ruleRef: "BR-CUS-105",
  },
  {
    code: "blocks_new_service",
    en: "Move the account into the disconnected state, which blocks new service elsewhere until it is settled.",
    ruleRef: "DSC-02.4 · OQ-384",
  },
] as const;

/** What a cut will NOT do — `DSC-02.4`'s second column, chipped *"Worth being
 *  clear about"*. ⚠ Its second drawn row (*"Stop the balance growing"*) is
 *  GONE: under BR-CUS-103 a cut is now exactly the thing that stops base
 *  growing, so keeping it would make the screen contradict itself one column
 *  over. The write-off half survives because nothing about a cut forgives a
 *  debt. */
export const CUT_WILL_NOT: readonly CutConsequence[] = [
  {
    code: "not_close",
    en: "Close the account or settle the deposit — that is a move-out, not a disconnect.",
    ruleRef: "DSC-02.4",
  },
  {
    code: "not_write_off",
    en: "Write off any of what is owed. The debt stands; only its growth stops.",
    supersededDrawn: "Stop the balance growing, or write any of it off",
    ruleRef: "BR-CUS-103",
  },
  {
    code: "not_remove_meter",
    en: "Remove the meter, unless meter removal was chosen as the field work.",
    ruleRef: "DSC-02.4",
  },
] as const;

// ══════════════════════════════════════════════════════════════════════════
// 8 · SHARED RENDERING
// ══════════════════════════════════════════════════════════════════════════

/**
 * CR-039 wave D tasks 15/16 — **the reference cell, shared by S89 and S90.**
 *
 * The CR's own finding 5: *"Transfer and disconnect have tables and no number …
 * A clerk cannot quote a reference; nothing on a bill can point at the job that
 * caused a change."* **A number a clerk cannot SEE is not a number**, so both
 * worklists gained a leading column and both draw it through this one function.
 *
 * ⚠ **AMENDED 2026-08-27 — THIS PARAGRAPH SAID "IT DRAWS AN ABSENCE ON EVERY
 * ROW TODAY" AND BOTH QUESTIONS HAVE SINCE CLOSED. It now draws a NUMBER on
 * every row of a re-seeded tenant, and NOT ONE LINE OF THIS FILE CHANGED**,
 * which is what rule 1 below was written to buy. The original reasoning, kept
 * because it is why the cell has this shape: `OQ-426` (transfer) and `OQ-427`
 * (disconnect) were open, B18 draws no number for either flow, so no series was
 * minted and the writers reported `numbering_series_missing` rather than
 * inventing a prefix. `TRF-26-0001` (PO-named) and `DSC-26-0001` (the build's
 * delegated choice) are what the two columns print now.
 *
 * ⚠ **THE ABSENCE BRANCH IS NOT DEAD CODE AND MUST NOT BE TIDIED AWAY.** A host
 * provisioned before the rulings holds no series row until somebody runs
 * `manage.py seed_demo --tenant <subdomain>` (`_seed_number_series` is
 * `get_or_create`), so both reasons are still reachable — and S90's second
 * absence, `no_case_opened`, never depended on a question at all.
 *
 * Three rules, and each is the same one a neighbouring cell on these screens
 * already obeys:
 *
 *   1. **The number renders when the server sent one** — its own string,
 *      never assembled here. The day either question closes, this cell starts
 *      printing `TRF-26-0001`-shaped text with no change to this file.
 *   2. **When it is absent, the REASON renders** — the server's sentence, as a
 *      `role="note"`, so a clerk reads *"a number series for transfers has not
 *      been set up"* rather than a dash they must interpret.
 *   3. **The open question is a `data-` attribute, never part of the
 *      sentence** (DEF-332 — `OQ-426` means nothing to a billing clerk).
 *
 * ⛔ **AND IT MUST NEVER PRINT A BARE `—`.** A dash on a reference column reads
 * as *"this record has no reference"*, which is a statement about the record.
 * The truth is a statement about the tenant's SETUP, and the two look identical
 * once rendered — DEF-127's *"looks exactly like a settled account"*, one
 * column over.
 *
 * B14 rule 21: Tailwind utilities only; this adds no stylesheet class.
 */
export function RecordNumberCell(props: {
  /** The allocated number, or `null` while no series exists. */
  number: string | null;
  /** The server's reason, present exactly when `number` is null.
   *
   *  ⚠ `open_question` is OPTIONAL and that is not laziness. S90 serves TWO
   *  absences here: `OQ-427` (unnumbered case) carries one, and
   *  `no_case_opened` (a protection row that never entered the ladder) is a
   *  settled fact with no question behind it. A required `open_question` would
   *  force the second to invent one. */
  unavailable: { code: string; detail: string; open_question?: string; series?: string } | null;
  /** `transfer` / `disconnect` — for the `data-` hook a test reads. */
  kind: string;
}) {
  const { number, unavailable, kind } = props;
  if (number !== null) {
    return (
      <span className="tabular-nums" data-record-number={kind}>
        {number}
      </span>
    );
  }
  return (
    <span
      role="note"
      className="block max-w-measure text-sm text-neutral-700"
      data-record-number={kind}
      data-record-number-absent=""
      data-tracks={unavailable?.open_question ?? unavailable?.code}
    >
      {unavailable?.detail ?? ""}
    </span>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// 9 · A SERVER CODE IS NOT A WORD A CLERK READS — `DEF-CUS-6053`
// ══════════════════════════════════════════════════════════════════════════
//
// ⛔ **THE REVIEW SCREEN SHOWED `non_payment` AND `held` TO A CLERK.**
// `DisconnectReviewStep` rendered `t(\`…reason.${code}\`, { defaultValue: code })`
// — a fallback whose whole job is to render SOMETHING rather than fail, so a
// key nobody has written reaches the screen as the server's own enum. Step 1
// and step 4 got it right by accident, because they had the vocabulary row in
// hand and passed `row.en`; step 5 holds only the draft's code.
//
// ⚠ **THE FIX IS NOT A BIGGER `defaultValue`.** The filed row is explicit: *"a
// missing label is a defect, and rendering the code is how it stays
// invisible"*. So an unknown code renders a VISIBLE refusal, and the code goes
// into `data-unlabelled` where a walk can find it and a clerk cannot read it.
// **B14 rule 31's neighbourhood**: a lowercase enum is not a database id, which
// is exactly why a human reading that rule can pass over this — so the check
// lives here rather than in anybody's reading.
//
// B14 rule 43 — this is a COMPONENT rather than three lines repeated per row,
// because the next screen that renders a vocabulary value must not have to
// remember any of the above.

/** The shape every disconnect vocabulary in §6 shares: a server code and the
 *  English the drawing gives it. */
export interface VocabularyRow {
  readonly code: string;
  readonly en: string;
}

// ══════════════════════════════════════════════════════════════════════════
// 10 · THE CASE NUMBER ON THE LADDER PANEL — `DEF-CUS-6052`
// ══════════════════════════════════════════════════════════════════════════
//
// ⛔ **`Case reference` SHOWED THE WORD `service`.** Blueprint p136 draws the
// CASE NUMBER — `DSC-26-0001` — and `AccountAndReasonStep` bound the cell to
// `ladder.data.sequence`, which is `disconnects.SEQ_SERVICE` / `SEQ_COLLECTIONS`:
// BR-CUS-082's two-value vocabulary for *is this ladder one that can end in a
// cut*. Both sides are strings, so `tsc`, eslint and every unit test passed.
//
// ⚠ **THE HUMAN REFERENCE IS `case_no`**, which `disconnects.case_payload`
// already serves beside `case_no_unavailable`; it is being added to the LADDER
// payload by a sibling lane. The parameter below is written so this file
// compiles and behaves correctly BOTH BEFORE AND AFTER that push: `account_id`
// is required only so the type is not a weak one, and the absence of `case_no`
// is distinguished from a `null` case_no — *"the payload does not carry it"*
// and *"there is no case"* are two different sentences to put on a screen.

/** What the ladder payload can say about the case's human reference. FOUR
 *  answers, because a screen that collapses them tells a clerk something
 *  untrue: a number · *a case exists and has no number* · *no case is open* ·
 *  *this build does not serve it*. */
export interface LadderCaseNumber {
  /** `null` when no case number could be resolved for any reason. */
  value: string | null;
  /** `false` when the payload carries no `case_no` field AT ALL — an older
   *  build, which a screen must state rather than read as *no case*. */
  served: boolean;
  /** `true` when a case EXISTS and carries no number — `OQ-427`, served as
   *  `disconnects.CASE_NUMBER_UNAVAILABLE`. `disconnect_reads`'s own words:
   *  *"no case was ever opened"* and *"a real case, unnumbered"* are two
   *  different facts, and the server keeps them apart so a screen can. */
  unnumbered: boolean;
}

/**
 * `DSC-02.1`'s `Case reference`, from the ladder payload — **never `sequence`**.
 */
export function ladderCaseNumber(
  ladder:
    | {
        account_id: string;
        case_no?: string | null;
        case_no_unavailable?: { code?: string } | null;
      }
    | undefined,
): LadderCaseNumber {
  if (ladder === undefined || !("case_no" in ladder)) {
    return { value: null, served: false, unnumbered: false };
  }
  const value = ladder.case_no === undefined || ladder.case_no === "" ? null : ladder.case_no;
  return {
    value,
    served: true,
    // `case_no_unavailable` is served ONLY when a case exists, so its presence
    // beside a null number is the unnumbered case and nothing else.
    unnumbered: value === null && (ladder.case_no_unavailable ?? null) !== null,
  };
}

/** A step's headline sentence. Capped at B14 rule 18's measure (80%, the
 *  `--desc-measure` token behind `max-w-measure`). Same shape as the New
 *  Connect wizard's, restated rather than imported so two lanes are not editing
 *  one component. */
export function StepIntro(props: { title: string; children?: ReactNode }) {
  // ⊕ 2026-09-23 (`DEF-CUS-6385`) — the sentence is OPTIONAL: B14 rule 33 puts
  // rationale at zero words, so a step whose only sentence was rationale draws
  // its title alone rather than an empty note.
  return (
    <div className="mb-4">
      <h3 className="font-heading text-h5 m-0 mb-1">{props.title}</h3>
      {props.children === undefined ? null : (
        <Note className="max-w-measure">{props.children}</Note>
      )}
    </div>
  );
}

/** `Step N of 5 · <the flow's own promise>` — B18 draws a footer on every one
 *  of the ten steps and both promises are load-bearing:
 *
 *    · transfer:   *"both halves commit together at the end"* — the atomic
 *      commit `commit_transfer` already implements, written for a clerk.
 *    · disconnect: *"nothing is cut until the scheduled date"* — *"the whole
 *      design in eight words"*. The wizard SCHEDULES; `commit_cut` cuts.
 */
export function stepFooterSentence(
  flow: "transfer" | "disconnect",
  step: number,
  of: number,
  t: Translator,
): string {
  return flow === "transfer"
    ? t("customers.transfer.footer", {
        // ⚠ **THIS SAID *"both halves commit together at the end"* — the
        // replaced job, on every one of the five steps (`DEF-CUS-5075`).**
        // There are no halves: one account changes hands through five staged
        // writes in one transaction. The atomicity is still the point and is
        // still said; what is gone is the claim that two things are happening.
        defaultValue: "Step {{step}} of {{of}} · one account changes hands, all at once.",
        step,
        of,
      })
    : t("customers.disconnect.footer", {
        defaultValue: "Step {{step}} of {{of}} · nothing is cut until the scheduled date.",
        step,
        of,
      });
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: B18 §5.7.7 (`TRF-02.1`…`TRF-02.5`) · §5.8.7 (`DSC-02.1`…`DSC-02.5`) ·
//         BR-CUS-103 · BR-CUS-104 · BR-CUS-105 · BR-CUS-100 · BR-CUS-101 ·
//         BR-SHL-025 · BR-SHL-046 · BR-BIL-007 · OQ-374 · OQ-382 · OQ-383 ·
//         OQ-384 · OQ-385 · DEF-691 · DEF-692 · apps/customers/disconnects.py ·
//         apps/customers/transfers.py
// generated: 2026-08-25 by lane W7WIZ
// checklist: A=n/a(no backend half in this lane) B✔ C✔ D✔ E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// exceptions:
//   E3 the drawn `All clear` protections chip is NOT rendered anywhere — ten
//      checks are drawn, four are answerable and one of those four answers
//      "unavailable". A green summary over six unasked questions is the most
//      dangerous sentence on either screen.
//   E3 `DSC-02.4`'s `Will` column is rebuilt from BR-CUS-103/104/105 rather
//      than transcribed; the two superseded drawn sentences ride beside their
//      supersessions, the posture `disconnects.CUT_WILL` takes in Python.
//   E3 the restrictor treatment is present and DISABLED (OQ-385), not deleted.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
