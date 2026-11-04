// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-018 · US-RBS-003 — CR-075 wave D tasks D3 and D4.
// Screens: RBS-002 · RBS-003 · and any later screen that draws a category.
// Rules:   B14 rule 31 (no database id is ever the visible value of a field —
//          and a raw enum code is that rule's spirit) · B14 rule 35 (a
//          catalogue is written in its own language) · `BR-RBS-025` (the
//          sixteen are a closed list; a seventeenth needs three runbooks that
//          fit nowhere else) · `RB-020` (adding runbook 23 needs no frontend
//          code).
// Tests:   TemplateLibrary.dom.test.tsx (every served category resolves to a
//          word, and an unknown one falls back rather than blanking).
// ───────────────────────────────────────────────────────
// THE SIXTEEN CATEGORY WORDS — AND WHY PUTTING THEM HERE DOES NOT BREAK
// `RB-020`.
//
// `models.CATEGORIES` is a CLOSED list of sixteen and the API serves the CODE:
// `onboarding_cutover`, `data_sync`, `plans_rates`. A screen drawing that code
// is drawing an internal identifier at a person, which is what B14 rule 31 was
// ratified against (*"no Databse ID on screen - that is a rule"*).
//
// ⚠ **THIS IS A VOCABULARY, NOT A PER-RUNBOOK FACT, AND THE DIFFERENCE IS THE
// WHOLE ARGUMENT.** `RB-020`'s claim is that **adding runbook 23 needs one
// Python module and no frontend code** — and it still does: runbook 23 picks one
// of the sixteen words that are already here. What WOULD break the claim is a
// map keyed by RUNBOOK — a per-template sentence, a per-template port label —
// and that is exactly what this module does not hold and why `DEF-RBS-4309` was
// filed instead of a lookup table. A seventeenth category is a deliberate act
// requiring three runbooks that fit nowhere else (`BR-RBS-025`), so it is the
// rare event that legitimately touches both sides.
//
// ⚠ **AND THE WORDS BELONG IN THE CATALOGUES RATHER THAN IN PYTHON.**
// `apps/runbooks/api.py::runbook_detail` rules the direction for this module in
// its own docstring: serving a rendered view model *"would put screen copy in
// Python and out of the eleven locale catalogues, which is B14's line and not a
// style preference."* Sixteen keys, eleven languages, each written in its own
// language rather than translated from English (B14 rule 35).

/** The i18n key for one category code. Kept as a function so the string is
 *  built in ONE place — a second `runbooks.category.${code}` written inline at a
 *  call site is the kind of duplication that survives a rename in one file and
 *  not the other. */
export function categoryKey(code: string): string {
  return `runbooks.category.${code}`;
}

/**
 * The word for a category code, in the reader's language.
 *
 * ⚠ **AN UNKNOWN CODE FALLS BACK TO THE CODE ITSELF RATHER THAN TO A BLANK.**
 * `i18next` returns the KEY when a key is missing, so a seventeenth category
 * shipped before its word would draw `runbooks.category.something` across a
 * chip — an internal string, which is the rule this file exists to keep. The
 * fallback returns the raw code instead: still not a word, and visibly a gap
 * rather than a broken key path. Both are wrong and the second one is legible,
 * which is what a fallback is for.
 */
export function categoryLabel(
  translate: (key: string) => string,
  code: string,
): string {
  const key = categoryKey(code);
  const word = translate(key);
  return word === key ? code : word;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-018 (CR-075 wave D task D3) · B14 rules 31 and 35 · BR-RBS-025 · RB-020
// generated: 2026-09-06 by the CR-075 wave D D3/D4 build lane
// checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=n/a
// gates: tsc --noEmit (the LOCAL compiler) · vitest · G15 (catalogue parity — the sixteen keys land in all eleven through i18n_fanin.py)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
