// ── Trace ──────────────────────────────────────────────
// Change:  CR-054 task 20 — the MODAL half. The wave of 2026-08-30 measured and
//          cut `metering.upload.*` (860 words → 425) and said so in its own
//          record; the two modals the task names by figure — *"Dispute 259 to
//          about 90; Correct 64 to about 25"* — were never touched, and
//          `metering.read.override.*` still measured EXACTLY the 64 words the CR
//          published as its starting figure. That is how this lane knew.
// Rules:   B14 rule 32 (ratified PO 2026-08-31) — a screen has a DESCRIPTION
//          BUDGET: one sentence per section · a stated absence is a `<details>`
//          closed by default · a row never repeats what its own control offers ·
//          no rule id or internal code in clerk-facing copy.
//          BR-MET-133 (PO 2026-08-26) — the four facts a billed dispute must
//          state. BR-SHL-041 (eleven catalogues).
// ───────────────────────────────────────────────────────
// ⚠ **WHY A WORD BUDGET IS A TEST AND NOT A NOTE.** B14's own status table says
// rule 32's clauses 1, 3 and 4 are UNENFORCED, "because no gate in this repo
// reads rendered output". A word count does not need rendered output: the copy
// is data, in `en.json`, and prose grows one helpful sentence at a time. Every
// sentence that pushed these two modals to 259 and 64 words was added by someone
// being helpful. So the ceiling is asserted, and it may fall and never rise —
// the same posture G31 and G43 take.
//
// ⚠ **AND THE BUDGET DOES NOT OVERRIDE A SIGNED RULE.** `billedBillStands`
// carries four facts the PO signed on 2026-08-26 (`BR-MET-133`) and CR-054's own
// wording for this task is *"keep every consequence statement, cut every
// explanation of what is not happening"*. So the cut here took the explanations
// — *"not a change to that bill"*, *"clearing does not open one"*, *"the reading
// has no field for it"*, *"Nothing is edited"*, *"Nothing here changes the
// reading itself"* — and every consequence stayed. That sentence is TWO
// sentences rather than rule 32 clause 1's one, deliberately and recorded: one
// sentence carrying five signed facts is a worse sentence for a clerk than two.
//
// RED PROOF, MEASURED (hard-won law 7), on the untouched tree at `bef4c12a`:
//   npx vitest run src/features/metering/CR054Task20ModalCopy.test.ts
//   × the Dispute modal fits its budget → expected 127 to be ≤ 95
//   × the Correct modal fits its budget → expected 64 to be ≤ 40
//   × the disputed-reading banner fits its budget → expected 91 to be ≤ 68
//   × the Clear-dispute modal fits its budget → expected 78 to be ≤ 63
//   × a required field's help does not restate "Required" → expected 'Required. The System Admin…' not to match /^required[.,]/i
//   × no help text explains what is NOT happening → expected 'Stored in the audit trail, not on the reading — the reading has no field for it.' not to contain 'has no field'
//   6 failed | 3 passed
import { describe, expect, it } from "vitest";
import en from "../../i18n/locales/en.json";

const catalogue = en as Record<string, string>;

/** Words as a person counts them: a placeholder is the one word it stands in
 *  for, and punctuation is not a word. Deliberately the same rule CR-054's own
 *  measurement used, so the figures in the register and the figures here mean
 *  the same thing. */
function words(value: string): number {
  return value.replace(/\{\{[^}]*\}\}/g, "X").match(/[A-Za-z0-9’'%$/.-]+/g)?.length ?? 0;
}

function total(keys: readonly string[]): number {
  return keys.reduce((sum, key) => {
    const value = catalogue[key];
    expect(value, `${key} is missing from en.json`).toBeTypeOf("string");
    return sum + words(value);
  }, 0);
}

// Every string each surface actually renders, in render order. These lists are
// the contract: a new sentence added to a modal has to be added here too, and
// then it has to fit.
//
// ⚠ **THE ORDER OF THESE THREE LISTS IS THE DRAWN ORDER AS OF 2026-09-14** —
// the blueprint's entries 04, 05 and 06 put the CONSEQUENCE last, immediately
// above the footer (B14 rule 11), where two of the three modals had it first.
//
// ⚠ **AND THE KICKER IS COUNTED ONCE, BELOW, IN NONE OF THEM.** It sat in the
// DISPUTE list and in neither of the others, so the three totals measured
// different things. It is also the one string here whose job is not description
// — it NAMES the reading, and step-1 Q7 is why it grew from the list's word
// "Reads" to the reading's own meter and register. A budget that counts an
// identifier as prose pushes back against naming the register, which is the
// last thing this module needs.
const DISPUTE_MODAL = [
  "metering.read.dispute.modalTitle",
  "metering.read.dispute.figure",
  "metering.read.dispute.reason",
  "metering.read.dispute.reasonHelp",
  "metering.read.dispute.note",
  "metering.read.dispute.billedBillStands",
  "metering.read.dispute.submit",
] as const;

const CORRECT_MODAL = [
  "metering.read.override.title",
  "metering.read.override.value",
  "metering.read.override.valueHelp",
  "metering.read.override.reason",
  "metering.read.override.reasonHelp",
  "metering.read.override.note",
  "metering.read.override.submit",
] as const;

const CLEAR_MODAL = [
  "metering.read.dispute.clearTitle",
  "metering.read.dispute.resolution",
  "metering.read.dispute.resolutionHelp",
  "metering.read.dispute.clearOutcome",
  "metering.read.dispute.clearNote",
  "metering.read.dispute.clearSubmit",
] as const;

/** The one string all three dialogs share, and the only one that is a NAME. */
const MODAL_KICKER = "metering.read.kicker";

const DISPUTE_BANNER = [
  "metering.read.dispute.title",
  "metering.read.dispute.noReason",
  "metering.read.dispute.by",
  "metering.read.dispute.holdsRun",
  "metering.read.dispute.billedBillStands",
] as const;

/** The help under a field the form already marks required (B14 rule 10). */
const REQUIRED_FIELD_HELPS = [
  "metering.read.dispute.reasonHelp",
  "metering.read.override.reasonHelp",
  "metering.read.override.valueHelp",
] as const;

const ALL_TOUCHED = [
  ...new Set([
    ...DISPUTE_MODAL,
    ...CORRECT_MODAL,
    ...CLEAR_MODAL,
    ...DISPUTE_BANNER,
    MODAL_KICKER,
  ]),
];

describe("CR-054 task 20 · B14 rule 32 on the Dispute and Correct modals", () => {
  // ⚠ THE CEILING IS THE MEASURED RESULT, NOT THE CR'S TARGET, and it is a
  // RATCHET in G31's and G43's posture: it may FALL, it may never RISE. A
  // ceiling set at the target would leave headroom for exactly the growth this
  // exists to stop.
  //
  // ⚠ AND THE MODAL'S TOTAL IS NOT ITS DESCRIPTION BUDGET. Twelve of the
  // Correct modal's words are a title, two field labels and a button — chrome,
  // not description — so its DESCRIPTIONS went 52 → 28 against the CR's "about
  // 25", while the whole modal went 64 → 40. Both figures are in the report.
  //
  // ⚠ **ALL THREE CEILINGS FELL ON 2026-09-14 AND NONE OF THEM ROSE**, which is
  // the posture above being obeyed rather than restated — *"a fall that is not
  // banked is also a failure"*. The blueprint's own copy pass cut three helper
  // lines to B14 rule 33's caps (one eight-word consequence becomes two
  // sentences of two and four; two facts lose the half that explained what is
  // NOT happening), and the kicker left the DISPUTE list for its own case.
  // Measured after, with the same `words()` a person counts by: **83 · 38 · 59.**
  //
  // ⚠ **AND THEY FELL AGAIN THE SAME DAY, ON THE PO'S OWN RULING** — verbatim:
  // ***"reduce the content to 5 to 6 meaningful words"***, said of the three
  // drawn consequence sentences at 13, 19 and 18 words. Each is now two
  // sentences of at most six, which is B14 rule 33's *"two sentences of six
  // beat one sentence of twelve"* rather than a shorter single line:
  //
  //   Correct  "The new value becomes the current reading; this one stays in
  //            the history."  →  "New value becomes current. The old one stays
  //            in history."                                        13 →  10
  //   Dispute  "The reading is not changed, and the account leaves the next
  //            bill run until a System Admin clears it."
  //            →  "Account leaves the next bill run. Only a System Admin
  //            clears it."                                         19 →  12
  //   Clear    "The account returns to the next bill run and will be billed on
  //            this reading as it stands."
  //            →  "Account returns to the bill run. Billed on this reading."
  //                                                                18 →  10
  //
  // ⚠ **NOTHING A CLERK ACTS ON WAS CUT, AND THE TESTS BELOW ARE WHY.** Every
  // consequence still names WHO undoes it and WHAT survives — *System Admin*,
  // *history* — because the pair of assertions in "the consequence a clerk acts
  // on survives in every shortened sentence" refused two earlier drafts that
  // had dropped one or the other. Measured after: **76 · 35 · 40.**
  it("the Dispute modal fits its budget (CR-054 task 20: 259 → about 90)", () => {
    expect(total(DISPUTE_MODAL)).toBeLessThanOrEqual(76);
  });

  it("the Correct modal fits its budget (CR-054 task 20: 64 → about 25)", () => {
    expect(total(CORRECT_MODAL)).toBeLessThanOrEqual(35);
  });

  it("the Clear-dispute modal fits its budget", () => {
    expect(total(CLEAR_MODAL)).toBeLessThanOrEqual(40);
  });

  it("the disputed-reading banner fits its budget", () => {
    expect(total(DISPUTE_BANNER)).toBeLessThanOrEqual(68);
  });

  it("B14 rule 32 clause 3: a required field's help does not restate “Required”", () => {
    for (const key of REQUIRED_FIELD_HELPS) {
      // The asterisk on the label already says it (B14 rule 10), so the word is
      // the row repeating what its own control offers.
      expect(catalogue[key], key).not.toMatch(/^required[.,]/i);
      expect(catalogue[key], key).not.toMatch(/^obligator/i);
    }
    // The same clause, one step along: the field is LABELLED "Corrected
    // register value", so a help text that opens by naming the register reading
    // again is the row repeating its own control.
    expect(catalogue["metering.read.override.valueHelp"]).not.toMatch(/register reading/i);
  });

  it("B14 rule 32 clause 4: no rule id and no internal code reaches a clerk", () => {
    for (const key of ALL_TOUCHED) {
      expect(catalogue[key], key).not.toMatch(/\b(?:BR|US|EP|OQ|DEF|GT|IS|ADR)-[A-Z]{0,3}-?\d{3,5}\b/);
      // A stored enum token — `tou_on`, `no_read`, `minimum_adjustment` — is the
      // shape DEF-2881's four leaks took. A `{{placeholder}}` is not one.
      expect(catalogue[key].replace(/\{\{[^}]*\}\}/g, "X"), key).not.toMatch(
        /\b[a-z]+_[a-z]+\b/,
      );
    }
  });

  it("CR-054 task 20's own rule: no sentence explains what is NOT happening", () => {
    // Each of these fragments was on the screen before this pass and each
    // described an absence rather than a consequence. Named so they cannot
    // quietly come back.
    const retired = [
      "has no field",
      "does not open one",
      "Nothing is edited",
      "Nothing here changes the reading",
      "not a change to that bill",
      "is the kind that helps",
      "an auditor needs",
    ];
    for (const key of ALL_TOUCHED) {
      for (const fragment of retired) {
        expect(catalogue[key], `${key} still carries “${fragment}”`).not.toContain(fragment);
      }
    }
  });

  it("BR-MET-133 survives the cut — all four signed facts are still on the screen", () => {
    // The budget must never be met by deleting a fact the PO signed on
    // 2026-08-26. This duplicates ReadDetailPage.test.tsx deliberately: that
    // one guards the RULE, this one guards the rule AGAINST THIS BUDGET.
    const sentence = catalogue["metering.read.dispute.billedBillStands"];
    expect(sentence).toContain("stands");
    expect(sentence).toContain("disputed amount does not age");
    expect(sentence).toContain("no late fees");
    expect(sentence).toContain("rest of the bill ages as usual");
    expect(sentence).toContain("billed correction");
  });

  it("the consequence a clerk acts on survives in every shortened sentence", () => {
    expect(catalogue["metering.read.dispute.note"]).toContain("System Admin");
    expect(catalogue["metering.read.dispute.holdsRun"]).toContain("System Admin");
    // Hard rule 3 — a register value is never shown or asked for without its
    // unit, so the placeholder stays even under the budget.
    expect(catalogue["metering.read.override.valueHelp"]).toContain("{{unit}}");
    // The correction is an APPEND, and that is the fact a clerk needs before
    // typing over a register (BR-MET-024).
    expect(catalogue["metering.read.override.note"]).toContain("history");
  });

  it("step-1 Q7: the kicker on all three dialogs names the REGISTER, not the list", () => {
    // A dialog COVERS the page that names the register, so while one is open
    // its kicker is the only place the register appears — and a correction
    // filed on the wrong one is permanent (metering migration `0007` freezes
    // the channel). DEF-797 is what that costs: 412 kW billed as 14 kWh,
    // $154.00 against $4,532.00.
    //
    // RED PROOF, with `metering.reads.kicker` still wired on all three:
    //   × expected 'Reads' to contain '{{channel}}'
    const kicker = catalogue[MODAL_KICKER];
    expect(kicker).toContain("{{meter}}");
    expect(kicker).toContain("{{channel}}");
    // ⚠ And the list's own word is NOT it: `metering.reads.kicker` is "Reads" —
    // the screen you came from, never the row you are about to change for ever.
    expect(catalogue["metering.reads.kicker"]).not.toContain("{{channel}}");
  });
});
