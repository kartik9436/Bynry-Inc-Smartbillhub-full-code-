// ── Trace ──────────────────────────────────────────────
// Change:  CR-076 addendum — the PO compared the running SET-10 against the
//          design and asked for the preview to be a DOCUMENT, not a text blob.
// Screens: SET-10 (Settings → Configure → Templates → one template)
// Rules:   B14 rule 31 (no database id is ever a visible value) · BR-SHL-020 /
//          BR-SHL-025 (an absent fact is NAMED, never faked) · hard-won law 1
//          (a comment claiming a guarantee is not the guarantee)
// ───────────────────────────────────────────────────────
//
// HOW A RENDERED BODY IS SET ON PAPER.
//
// ══════════════════════════════════════════════════════════════════════════
//  WHAT THE SERVER ACTUALLY SENDS, AND WHY THAT DECIDES EVERYTHING HERE
// ══════════════════════════════════════════════════════════════════════════
// `POST …/preview` returns `body` as ONE STRING. There is no line-item array,
// no letterhead object, no totals block and no document tree — `rendering.render`
// substitutes merge fields into the wording a person typed and hands back text.
// That is not an oversight to route around: a template IS wording, and
// `template_preview.py` says in its own docstring that the preview must be the
// real renderer rather than a second one, *"because two renderers that can
// disagree WILL"*.
//
// So the design's document — a masthead, an accent rule, right-aligned amounts,
// a total — cannot be assembled from fields the server does not send. What this
// module does instead is SET the text the server did send: it reads the shape
// the AUTHOR gave their own wording (blank lines, capitals, a value at the end
// of a short line) and gives each shape its typography.
//
// ══════════════════════════════════════════════════════════════════════════
//  THE ONE RULE THAT KEEPS THIS HONEST: NOTHING IS RECOGNISED BY PATTERN
// ══════════════════════════════════════════════════════════════════════════
// A line is a label-and-value row **only when it ends with a string the server
// told us is a sample value** — `merge_field_rows[].sample_value`, resolved by
// the renderer's own formatter. It is NEVER recognised by a money regex, a
// currency symbol or a trailing-number heuristic.
//
// That distinction is the whole safety of this module, and it is the same one
// `designerKind` states one file over: *"reading a drawing decision out of a
// human sentence is how a screen starts changing behaviour when somebody edits
// a label"*. A `$` test would right-align a sentence the moment a utility wrote
// a price into their prose. This cannot: the strings it matches are the exact
// strings the renderer just substituted, so a line only aligns because a merge
// field genuinely ends it.
//
// ⚠ **AND WHEN THE SERVER SENDS NO SAMPLES, NOTHING ALIGNS.** A class with no
// merge-field catalogue (`catalog_unavailable`) yields an empty sample set, so
// every line comes back as plain text and the page is simply a well-set page.
// The degradation is the honest one — no invented structure — and it is the
// common case on the classes that have no palette at all.
//
// ══════════════════════════════════════════════════════════════════════════
//  WHAT IT DELIBERATELY DOES NOT DO — READ THIS BEFORE "IMPROVING" IT
// ══════════════════════════════════════════════════════════════════════════
// **A LINE HOLDING TWO SAMPLE VALUES IS LEFT AS PROSE.** The seeded bill body's
// most important line is `Total due {total_due} by {due_date}`, which renders as
// *"Total due $123.45 by 31/01/2026"*. The design draws a total as a
// right-aligned figure; splitting this one would put *"Total due $123.45 by"* in
// the label column and the DATE in the money column, which states something
// false about which number is the amount. So it stays a sentence, and the
// design's bold total line is a KNOWN DEPARTURE recorded in the walkthrough
// rather than a guess made here.
//
// **A LABEL IS AT MOST FOUR WORDS.** `Amount outstanding`, `Previous balance`,
// `What we are doing` are labels; *"Report a leak, an outage or an emergency —"*
// is prose that happens to end in a phone number. Four is measured against the
// twenty-eight seeded bodies rather than chosen: it admits every label/value
// line they contain and admits no sentence.
//
// **THE MASTHEAD IS THE BODY'S OWN FIRST LINE, NOT THE UTILITY'S NAME.** Several
// seeded bodies open with `{utility_name}` alone on a line and that is what the
// design's letterhead is. An email opens `Hi {first_name},` instead — a greeting,
// and setting a greeting as a letterhead would be worse than setting nothing —
// so a first line ending in a comma is never a masthead.

/** One line of the rendered document, with the typography it has earned.
 *
 *  `rule` is the accent line under a letterhead. It is a BLOCK rather than
 *  something the component draws beside the masthead, because a letterhead is
 *  often two lines — a name and an address — and the rule belongs under the
 *  whole block rather than under its first line. Emitting it here keeps that
 *  decision in the one place that knows where the block ends. */
export type DocBlockKind = "masthead" | "rule" | "heading" | "pair" | "text" | "blank";

export interface DocBlock {
  readonly kind: DocBlockKind;
  /** The whole line, or — for a `pair` — the label half. */
  readonly text: string;
  /** A `pair`'s right-hand value. Absent on every other kind. */
  readonly value?: string;
}

/** The longest sample value this line ENDS with, or null.
 *
 *  Longest wins so that a value which is a suffix of another cannot win over
 *  it — `123.45` inside `$123.45` would otherwise leave a stray currency symbol
 *  at the end of the label.
 */
function trailingSample(line: string, samples: readonly string[]): string | null {
  let best: string | null = null;
  for (const sample of samples) {
    // A one-character "value" is noise: it matches the end of almost any line
    // and would align punctuation.
    if (sample.length < 2) continue;
    if (!line.endsWith(sample)) continue;
    if (best === null || sample.length > best.length) best = sample;
  }
  return best;
}

/** Whether a label is a LABEL rather than the tail of a sentence. */
function readsAsLabel(label: string, samples: readonly string[]): boolean {
  if (label === "") return false;
  // A label does not close a sentence. `Your new balance is` would, and is prose.
  if (/[.!?;]$/.test(label)) return false;
  // Four words, measured against the seeded bodies — see the header.
  if (label.split(/\s+/).length > 4) return false;
  // A label carrying its own merge value is not a label: splitting
  // `Total due $123.45 by` would call a DATE the amount.
  return samples.every((sample) => sample.length < 2 || !label.includes(sample));
}

/**
 * A rendered body, as the blocks a page is set from.
 *
 * `samples` are `merge_field_rows[].sample_value` — the exact strings the
 * renderer substituted. Pass an empty array and every line comes back `text`,
 * which is the correct answer for a class whose palette nobody has defined.
 */
export function documentBlocks(body: string, samples: readonly string[]): DocBlock[] {
  const lines = body.split("\n");
  const blocks: DocBlock[] = [];
  // Where the letterhead ends — an EXCLUSIVE index, 0 when there is none.
  const mastheadEnd = mastheadExtent(lines);
  // The masthead is the FIRST block of the document and only ever that: a
  // capitalised name halfway down a letter is a heading, not a letterhead.
  let firstInkSeen = false;

  for (let index = 0; index < lines.length; index += 1) {
    const raw = lines[index];
    const line = raw.trimEnd();
    if (line.trim() === "") {
      blocks.push({ kind: "blank", text: "" });
      continue;
    }
    const isFirstInk = !firstInkSeen;
    firstInkSeen = true;

    // ── the letterhead ────────────────────────────────────────────────────
    // `mastheadExtent` decides where it ends; this only draws it. The FIRST
    // line is the name and takes the letterhead weight; anything else in the
    // block is the address under it, set as ordinary document text; the accent
    // rule closes the block.
    if (index < mastheadEnd) {
      blocks.push({ kind: isFirstInk ? "masthead" : "text", text: line });
      if (index === mastheadEnd - 1) {
        blocks.push({ kind: "rule", text: "" });
      }
      continue;
    }

    // ── a heading the author wrote in capitals ────────────────────────────
    // `WE CALLED TODAY AND COULD NOT FINISH`, `HOW TO REACH US`. This reads the
    // author's OWN emphasis rather than guessing at meaning: a line a person
    // typed in capitals is a line they meant to stand out.
    if (/[A-Z]/.test(line) && line === line.toUpperCase() && line.length <= 60) {
      blocks.push({ kind: "heading", text: line });
      continue;
    }

    // ── a label and the value a merge field put at the end of it ──────────
    const value = trailingSample(line, samples);
    if (value !== null) {
      const label = line.slice(0, line.length - value.length).trimEnd();
      if (readsAsLabel(label, samples)) {
        blocks.push({ kind: "pair", text: label, value });
        continue;
      }
    }

    blocks.push({ kind: "text", text: line });
  }

  return blocks;
}

/**
 * WHERE THE LETTERHEAD ENDS — an exclusive line index, or 0 for no letterhead.
 *
 * A letterhead is the document's FIRST BLOCK, at most two lines, each of them
 * short, none of them closing a sentence, with a document below it.
 *
 * ⚠ **TWO LINES AND NOT ONE, BECAUSE THE BROWSER SAID SO.** The first version
 * asked for a single line, and on the real seeded disconnection notice the
 * letterhead is `{utility_name}` followed immediately by `{utility_address}` —
 * a name and a street address, which is what a letterhead IS. No masthead was
 * recognised, so no accent rule was drawn, and the page opened with two lines of
 * ordinary body text where the design has a heading and a rule. Every DOM
 * assertion passed over it; only the rendered page showed it (hard-won law 6).
 *
 * ⚠ **AND EVERY LINE IS TESTED, NOT ONLY THE FIRST.** A body opening `Dear
 * customer` / `Your account is overdue.` is two short lines followed by a blank,
 * and setting THAT as a letterhead would put a sentence in a masthead. A line
 * that closes a sentence ends the candidate; so does a comma, which is what
 * makes `Hi {first_name},` a greeting rather than a name.
 */
function mastheadExtent(lines: readonly string[]): number {
  let start = 0;
  while (start < lines.length && lines[start].trim() === "") start += 1;
  if (start >= lines.length) return 0;

  let end = start;
  while (end < lines.length && lines[end].trim() !== "") {
    const line = lines[end].trimEnd();
    // Short, and not the tail of a sentence — on EVERY line of the block.
    if (line.length > 48 || /[,:;.!?]$/.test(line)) return 0;
    end += 1;
    if (end - start > 2) return 0;
  }
  // A letterhead is only a letterhead because a document follows it. Without
  // this a one-line body was set entirely as an 18px heading with a rule under
  // it and nothing beneath.
  if (!lines.slice(end).some((rest) => rest.trim() !== "")) return 0;
  return end;
}

/** The sample strings a document is set against — the server's, never guessed.
 *
 *  ⚠ **`sample_value` AND NOT `sample_unavailable`.** The five BR-TEN-017
 *  identity tokens have no sample on purpose (they are stamped from Settings →
 *  Company at render), so the renderer prints its named absence for them. That
 *  absence is not a value and must never align a line as though it were one.
 */
export function documentSamples(
  rows: readonly { sample_value: string | null }[],
): string[] {
  const seen = new Set<string>();
  for (const row of rows) {
    if (row.sample_value !== null && row.sample_value.trim() !== "") {
      seen.add(row.sample_value);
    }
  }
  return [...seen];
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-076 addendum (the PO's two SET-10 screenshots, transcribed into the
//         lane brief) · 04-docs/02-decisions/14-ui-conventions.md B14 rules
//         21/31/32/36 · apps/notifications/template_preview.py (what is served)
// generated: 2026-09-07 by the SET-10 designer lane
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
