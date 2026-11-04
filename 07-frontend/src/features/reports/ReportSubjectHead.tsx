// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-REP-7052 — no statement names what it is about. `Subject.head_from`
//          has been published by the server since `P2.14` and is rendered
//          NOWHERE; the shipped account statement has never named its account
//          either.
// Screens: 2·1 Report viewer — the page-head roll-up, beside the window, the
//          basis and the grain.
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT — this is why the head is
//          not four lines inside a 1,800-line page) · rule 33 (a FACT ≤ 6
//          words; RATIONALE is ZERO words on screen) · rule 31 (no database id
//          is ever the visible value of a field) · rule 44 (our tokens and our
//          kit win over the drawing) · rule 21 (Tailwind utilities; this file
//          is listed in route-b-migrated.txt) · CLAUDE.md hard rule 8 (a unit
//          refines a premises by LABEL and has no address of its own).
// Tests:   07-frontend/src/features/reports/reportSubjectHead.dom.test.tsx
// Impacts: ReportViewerPage.tsx (renders it inside the existing roll-up) ·
//          apps/reports/subject_head.py (composes what this draws)
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  IT RENDERS WHAT IT IS HANDED AND KNOWS NOTHING ABOUT ACCOUNTS           ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// The brief draws it twice — p69's `100244 · Ruiz, Marisol` and p71's
// `1408 Elm Street · Unit 3` — and p71 states it in prose: *"The head reads
// 1408 Elm Street · Unit 3 — the premises address and the unit label."*
//
// ⚠ **THERE IS NO LIST OF SUBJECTS IN THIS FILE AND THERE MUST NEVER BE ONE.**
// The server composes the parts from the SUBJECT's own `head_from`; this joins
// them. A subject added on the server therefore appears in the head with no
// change here at all — which is the point, because lane REP-SUBJ-2 is building
// the customer and premises subjects while this is written, and a hand-typed
// map here would be the seventh of the six `P0.7` deleted (CLAUDE.md: *never
// hand-type a list*).
//
// ⚠ **NOTHING HERE IS TRANSLATED, AND THAT IS NOT AN OVERSIGHT.** Every part is
// the NAME of a record — an account number, a person, an address, a unit label
// — and a name is the same in eleven languages. B14 rule 35 governs a
// CATALOGUE; it does not ask us to translate `AC-2026-00032`. There is no
// label either: a word like *Account* in front of the number would be three
// more words on a line the Product Owner has already asked twice to shorten
// (`DEF-REP-7011` — four stacked lines above the first row, and they wanted
// two).
//
// ⚠ **B14 RULE 31 — THE ID IS NOT HERE AND CANNOT BE.** The server publishes
// VALUES only; the `subject_id` that selected the record travels in the URL,
// which is navigation and is what the unit statement already does. A test
// asserts the id is absent from `textContent`.
import type { ReactNode } from "react";

import type { ReportResponse } from "@/api/reportsEndpoints";

/** The parts, in the server's order, with the empty ones dropped.
 *
 *  Exported and pure so *"the head never renders a stray separator"* is a
 *  property with a test rather than something somebody looked at once. */
export function subjectHeadParts(head: ReportResponse["head"]): string[] {
  const parts: string[] = [];
  for (const field of head?.fields ?? []) {
    const value = (field?.value ?? "").trim();
    if (value !== "") {
      parts.push(value);
    }
  }
  return parts;
}

/**
 * *"AC-2026-00032 · Hugo Faulkner"* — which record this page of money is about.
 *
 * ⚠ **IT DRAWS ROLL-UP ITEMS AND NOT A LINE OF ITS OWN** (`DEF-REP-7011`, and
 * `ReportGrainLine`'s `inline` carries the same reasoning). The window, the
 * basis and the grain are already one line under the title; a head on its own
 * line would be the third, over a screen whose Product Owner counted four and
 * asked for two. The separator is `.fin-rollup-item`'s own `::before`.
 *
 * ⚠ **THE PARTS ARE ONE ITEM, NOT SEVERAL.** `1408 Elm Street` and `Apt 3B`
 * are two halves of ONE fact — hard rule 8's *the building's address plus the
 * unit's label* — and splitting them across roll-up items would let the window
 * appear between them the day the order changed.
 */
export function ReportSubjectHead(props: { head: ReportResponse["head"] }): ReactNode {
  const parts = subjectHeadParts(props.head);
  if (parts.length === 0) {
    // ⚠ **NOTHING, NEVER A DASH.** A report about no particular record, or one
    // opened before a record has been named, has no head — and a placeholder
    // would be this screen inventing a value for a question the server said it
    // could not answer.
    return null;
  }
  return (
    <span
      className="fin-rollup-item font-medium text-text"
      data-report-head={props.head?.subject ?? ""}
    >
      {parts.join(" · ")}
    </span>
  );
}
