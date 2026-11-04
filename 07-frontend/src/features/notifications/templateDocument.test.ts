// ── Trace ──────────────────────────────────────────────
// Change:  CR-076 addendum — SET-10's preview is a DOCUMENT, not a text blob.
// Screens: SET-10
// Rules:   BR-SHL-020 (an absent fact is named, never faked) · hard-won law 7
//          (prove a guard RED, and ask what would make it pass WRONGLY)
// ───────────────────────────────────────────────────────
//
// WHAT SETS A LINE APART, AND WHAT MUST NOT.
//
// `documentBlocks` is the only piece of SET-10 that reads the rendered body and
// decides how to draw it, so it is the only piece that can get a document
// WRONG in a way nobody notices — a right-aligned figure states *this number is
// the amount*, and a sentence set as a label states something false about the
// author's own prose.
//
// ⚠ **HALF OF THIS FILE IS THE NEGATIVE HALF, DELIBERATELY (law 7, habit 2).**
// The question *what would make this pass wrongly* has a concrete answer here:
// a rule that looked for a currency symbol, a trailing number or a colon would
// pass every positive case below and would then right-align a utility's prose
// the first time somebody wrote a price into a sentence. The cases named "is
// NOT" are what separate this implementation from that one, and they are the
// ones to keep if the file is ever trimmed.
//
// RED-PROVED BEFORE TRUSTED GREEN, in the harness that runs it (`vitest run`,
// not a hand-rolled entry point — DEF-GOV-3733):
//   · `readsAsLabel`'s four-word cap was raised to twenty and
//     "prose ending in a sample value is left alone" failed on
//     "We received your payment of" being treated as a label;
//   · the `label.includes(sample)` guard was deleted and "a line carrying TWO
//     sample values stays prose" failed, splitting `Total due $123.45 by
//     31/01/2026` into a label ending in the amount and a DATE in the money
//     column — the exact false statement the guard exists to prevent;
//   · the masthead's comma test was deleted and "a greeting is not a
//     letterhead" failed on `Hi Sample first name,`;
//   · the masthead's *and a document follows it* clause was deleted and SEVEN
//     cases failed at once.
//
// ⚠ **THAT FOURTH CLAUSE WAS NOT PLANNED — THESE CASES FOUND IT, WHICH IS THE
// ARGUMENT FOR WRITING THEM FIRST.** The first draft made a masthead of any
// short first line whose successor was blank OR ABSENT, so a body that is ONE
// LINE — a short notice, a bill insert's single sentence — was set entirely as
// an 18px letterhead with an accent rule under it and no document beneath. It
// went red here before it went anywhere near a browser, and the fix is in
// `templateDocument.ts` with the reason beside it.
import { describe, expect, it } from "vitest";

import { documentBlocks, documentSamples } from "./templateDocument";

/** The samples a seeded body actually renders with — money, a date and a name,
 *  exactly as `template_preview.sample_context` types them. */
const SAMPLES = ["$123.45", "31/01/2026", "Sample work type", "SAMPLE-ACCOUNT"];

function kinds(body: string, samples = SAMPLES) {
  return documentBlocks(body, samples).map((block) => block.kind);
}

describe("the values a document is set against are the SERVER's", () => {
  it("takes every sample the server resolved, and drops the ones it refused to", () => {
    // The five BR-TEN-017 identity tokens carry `sample_value: null` and a
    // sentence saying where they come from. That sentence is an ABSENCE and
    // must never align a line as though it were a value.
    expect(
      documentSamples([
        { sample_value: "$123.45" },
        { sample_value: null },
        { sample_value: "$123.45" },
        { sample_value: "  " },
      ]),
    ).toEqual(["$123.45"]);
  });

  it("with NO samples in hand, nothing is set apart at all", () => {
    // A class whose merge-field catalogue nobody has written serves no samples.
    // The honest degradation is a well-set page of prose — never a guess.
    const body = "Previous balance $123.45\nTotal due $123.45 by 31/01/2026";
    expect(kinds(body, [])).toEqual(["text", "text"]);
  });
});

describe("a label and its value", () => {
  it("splits a short line whose END is a value the server resolved", () => {
    const [block] = documentBlocks("Previous balance $123.45", SAMPLES);
    expect(block.kind).toBe("pair");
    expect(block.text).toBe("Previous balance");
    expect(block.value).toBe("$123.45");
  });

  it("works for a date and a name, not only for money", () => {
    // The rule is *the server said this string is a sample*, so it is not a
    // money rule and does not become one.
    expect(documentBlocks("Date 31/01/2026", SAMPLES)[0]).toMatchObject({
      kind: "pair",
      text: "Date",
      value: "31/01/2026",
    });
    expect(documentBlocks("What we are doing Sample work type", SAMPLES)[0]).toMatchObject({
      kind: "pair",
      text: "What we are doing",
    });
  });

  it("is NOT prose that happens to end in a sample value", () => {
    // Four words is the cap, measured against the twenty-eight seeded bodies:
    // it admits every label/value line they contain and admits no sentence.
    expect(kinds("We received your payment of $123.45")).toEqual(["text"]);
    expect(kinds("Report a leak, an outage or an emergency $123.45")).toEqual(["text"]);
  });

  it("is NOT a line that closes a sentence before the value", () => {
    expect(kinds("Your new balance is now. $123.45")).toEqual(["text"]);
  });

  it("is NOT a line carrying TWO sample values — the seeded bill's total line", () => {
    // `Total due {total_due} by {due_date}`. Splitting it puts the amount in
    // the LABEL and the DATE in the money column, which states that the date is
    // the figure. It stays a sentence, and that is a stated departure from the
    // design's bold total rather than a guess made here.
    expect(kinds("Total due $123.45 by 31/01/2026")).toEqual(["text"]);
  });

  it("is NOT a one-character coincidence at the end of a line", () => {
    // A short "value" matches the end of almost any line and would align
    // punctuation. Two characters is the floor.
    expect(kinds("Everything is fine.", ["."])).toEqual(["text"]);
  });
});

describe("the letterhead and the author's own emphasis", () => {
  it("sets the body's first standalone line as the masthead, with a rule under it", () => {
    // Several seeded bodies open with `{utility_name}` alone on a line, which
    // is exactly what the design's letterhead is.
    const blocks = documentBlocks("Riverbend Water\n\nWE CALLED TODAY", SAMPLES);
    expect(blocks[0]).toMatchObject({ kind: "masthead", text: "Riverbend Water" });
    expect(blocks[1].kind).toBe("rule");
  });

  it("a NAME AND AN ADDRESS is one letterhead, with the rule under both", () => {
    // The seeded disconnection notice opens `{utility_name}` then
    // `{utility_address}` with no blank between them — which is what a
    // letterhead IS, and what the first version of this refused to recognise:
    // no masthead was found, so no accent rule was drawn, and the page opened
    // with two lines of body text where the design has a heading and a rule.
    const blocks = documentBlocks(
      "Riverbend Water\n9410 FM 1093 Rd Katy TX\n\nSample Customer",
      SAMPLES,
    );
    expect(blocks.map((b) => b.kind).slice(0, 3)).toEqual(["masthead", "text", "rule"]);
    expect(blocks[1].text).toBe("9410 FM 1093 Rd Katy TX");
  });

  it("…but THREE lines is a paragraph, not a letterhead", () => {
    expect(kinds("Riverbend Water\nOne\nTwo\n\nBody")[0]).toBe("text");
  });

  it("a sentence anywhere in the block ends the letterhead", () => {
    // `Dear customer` / `Your account is overdue.` is two short lines followed
    // by a blank. Setting that as a letterhead puts a sentence in a masthead,
    // so every line of the candidate is tested and not only the first.
    expect(kinds("Dear customer\nYour account is overdue.\n\nPay now")[0]).toBe("text");
  });

  it("a GREETING is not a letterhead", () => {
    // `Hi {first_name},` opens every seeded email. Setting it as a masthead
    // would be worse than setting nothing, and the comma is what says it runs
    // on into the letter.
    expect(kinds("Hi Sample first name,\n\nYour bill is ready.")[0]).toBe("text");
  });

  it("a line that runs straight on is not a letterhead either", () => {
    expect(kinds("Riverbend Water\nsends you this letter.")[0]).toBe("text");
  });

  it("gives a line the author wrote in CAPITALS its own weight", () => {
    // Reading the author's own emphasis, not guessing at meaning.
    // Index 2 is the RULE that closes the letterhead, so the heading is 3.
    expect(documentBlocks("Hello there\n\nHOW TO REACH US\n\nCall us.", SAMPLES)[3]).toMatchObject({
      kind: "heading",
      text: "HOW TO REACH US",
    });
  });

  it("does not call ordinary prose a heading because it has no lower-case letters in it", () => {
    // A line of digits and punctuation has no letters at all; treating it as
    // emphasis would set a phone number as a section head.
    expect(kinds("555 010 2200")).toEqual(["text"]);
  });
});

describe("the author's own shape survives", () => {
  it("keeps a blank line as space rather than collapsing it", () => {
    expect(kinds("One\n\nTwo")).toEqual(["masthead", "rule", "blank", "text"]);
  });

  it("returns one block per line, plus the letterhead's rule, so nothing is dropped", () => {
    const body = "Riverbend Water\n\nHOW TO REACH US\n\nAmount $123.45\nThanks for reading.";
    // ⚠ **`+ 1` IS THE RULE AND IT IS THE ONLY BLOCK THAT IS NOT A LINE.**
    // Saying so here is what keeps this case a "nothing is dropped" check
    // rather than a number somebody adjusts until it passes.
    expect(documentBlocks(body, SAMPLES)).toHaveLength(body.split("\n").length + 1);
  });

  it("is not an empty loop", () => {
    // DEF-057's shape: every expectation above is over an array, and an
    // implementation returning [] would satisfy several of them vacuously.
    expect(documentBlocks("Amount $123.45", SAMPLES).length).toBeGreaterThan(0);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-076 addendum (the PO's SET-10 screenshots) · templateDocument.ts's
//         own module header, which states what it will and will not recognise
// generated: 2026-09-07 by the SET-10 designer lane
// gates: vitest — RED-PROVED first, three separate breaks, each named in the
//         header above with the case it failed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
