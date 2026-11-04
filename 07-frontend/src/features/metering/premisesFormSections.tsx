// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave B `B8` — *"05 Edit a property PRM-02 and create property
//          screen should match - please update - it will help user to have
//          simialr experience"* (PO 2026-09-08, verbatim).
//          RE-CUT 2026-09-10 by the conformance pass against the DRAWN frame:
//          `04-docs/05-modules/04-metering/conformance/CR-089-p008-add-property-details.md`
//          and `CR-089-p036-edit-a-property.md`, PO ruling of the same day —
//          *"(a) The frame wins, correct the sentences"*.
// Rules:   B14 rule 21 (new UI adds NO class to a stylesheet) · B14 rule 32 (a
//          screen has a description budget: one sentence per section)
// Screens: S16 the guided add (`AddPremisesWizard`) · PRM-01/PRM-02 the edit
//          form (`PremisesListPage`)
// ───────────────────────────────────────────────────────
// THE HEADINGS, DECLARED ONCE, SO THE TWO FORMS CANNOT DISAGREE.
//
// ⚠ **THEY DID DISAGREE, AND NOT BY A LITTLE.** Before this file the create
// form asked for the parcel and the two coordinates FOURTH — right under the
// postal code — and the edit form asked for them LAST, under the owner. Same
// eight facts, two orders, and a clerk who learned one screen had to re-find
// every field on the other. Neither form had a heading of any kind: the create
// step was eighteen labelled boxes under one `<h3>Premise details</h3>`.
//
// ⚠ **FOUR, NOT SIX — AND THE SIX WERE NEVER DRAWN (2026-09-10).** This array
// held six headings, written in STATEMENT form (*Where it is*, *Parcel and map
// point*, *Utility services*), and they came from a commitment SENTENCE rather
// than from the blueprint's frame, which nothing in the container could open at
// the time. The frame draws **four question-headings** on both screens, and the
// blueprint contradicts itself in exactly this place: its teal block says *five
// question-headings*, `PUJ-18` says *"the same six headings"*, and its own
// `COGNITIVE LOAD` row says **"Fifteen fields in four named groups"**. The PO
// ruled the frame wins. So:
//
//   1 · `Where is it?`                 — the address AND the map confirmation
//   2 · `What kind of property is it?` — type, city limits AND utility services
//   3 · `Who looks after it?`          — owner, managed by, area, sub-area
//   4 · `Reading and billing`          — read route + billing cycle, `optional`
//
// The three ids the six-group form used — `map`, `belongs`, `services` — are
// RETIRED as of 2026-09-10: their controls now sit inside the four above
// (parcel and point under `where`, services under `kind`, area under `owner`),
// which is where the frame draws them. The transitional `RETIRED_SECTION_LABELS`
// map that kept them resolving while the edit form still rendered six is DELETED,
// and `PremisesFormSections.test.tsx` now asserts both forms render exactly the
// declared four, in order.
//
// ⚠ **THE HEADINGS ARE QUESTIONS AND THAT IS THE DELIVERABLE, NOT A TONE.**
// The frame's own words: *"A person filling a form is answering questions, and
// a heading that asks one is easier to answer than a heading that names a
// database table."*
//
// ⚠ **THE ORDER IS THE DELIVERABLE, WHICH IS WHY IT IS A LIST AND NOT A
// CONVENTION.** A comment asking two files to stay in step is a comment; an
// exported array both files map over is the thing itself. `PremisesFormSections
// .test.tsx` reads both source files and asserts what each renders — so the
// next lane that adds a field to one form and not the other gets a red test
// rather than a slow divergence (hard-won law 1).
//
// ⚠ **NO TAILWIND UTILITY IN THIS FILE, AND THAT IS NOT AN OVERSIGHT.** Neither
// consumer is listed in `src/styles/route-b-migrated.txt` — `AddPremisesWizard
// .tsx` and `PremisesListPage.tsx` are both Route A — and a utility emitted from
// an unlisted file is a class no stylesheet declares: it renders as NOTHING and
// `tsc`, eslint and every `toContain` assertion pass over it (CLAUDE.md B14 rule
// 21's migration clause, DEF-974). The heading is therefore an unclassed `<h4>`,
// which is what rule 21 is actually asking for: it adds no class to any
// stylesheet at all. The `optional` chip beside it is the KIT's `Chip`, whose
// classes are emitted from `components/Chip.tsx` — a file that IS on the list —
// so it costs this file nothing.
import type { ReactNode } from "react";

import { Chip } from "@/components/Chip";

import type { Translator } from "@/features/tenancy/settingsShared";

/**
 * The four, in the drawn order. Each `id` is what a test asserts on; each
 * `labelKey` is the question a clerk reads.
 *
 * ⚠ **FOUR, NOT FIVE — `What is inside it?` IS NOT HERE.** The units and the
 * common areas exist only while a property is being CREATED (`B5`), and the
 * edit form draws no such group at all (`CR-089-p036`, *"There is no `What is
 * inside it?` heading on the edit form"*). A heading the edit form could never
 * draw would break the very promise this file makes. The create form adds that
 * block itself, BELOW the four, and says so.
 */
export const PREMISES_FORM_SECTIONS = [
  // 1 · WHERE IS IT? — the address itself, and then what the lookup found.
  // `BR-MET-1161`: an address is stored on premises and nowhere else, so this
  // is the one place in the product it is typed. The parcel and the point ride
  // here too, as a CONFIRMATION rather than as four more boxes — the frame's
  // words: *"What the lookup found is a confirmation, not four more boxes. A
  // clerk reads them; they only edit them when the lookup is wrong."*
  { id: "where", labelKey: "metering.premises.section.where" },
  // 2 · WHAT KIND OF PROPERTY IS IT? — the type and which side of the city line
  // it sits on, both of which decide money (`BR-RAT-101`/`BR-RAT-102`), and
  // what the utility can sell here (`BR-MET-003`). The frame draws the services
  // control INSIDE this group rather than as a fifth heading of its own.
  { id: "kind", labelKey: "metering.premises.section.kind" },
  // 3 · WHO LOOKS AFTER IT? — the owner (optional since `B1`), who manages it,
  // and where it belongs operationally: area and sub-area, two controls over
  // one column (`BR-MET-071`).
  { id: "owner", labelKey: "metering.premises.section.owner" },
  // 4 · READING AND BILLING — the route and its cycle (`B6`). The only group
  // that carries the `optional` chip, because it is the one a clerk in a hurry
  // may skip whole.
  { id: "readingBilling", labelKey: "metering.premises.section.readingBilling" },
] as const;

export type PremisesFormSectionId = (typeof PREMISES_FORM_SECTIONS)[number]["id"];

function labelKeyFor(id: string): string {
  const section = PREMISES_FORM_SECTIONS.find((row) => row.id === id);
  // ⚠ NO FALLBACK, DELIBERATELY. `RETIRED_SECTION_LABELS` stood here while the
  // edit form still rendered six ids; that form is now re-cut onto these four
  // (CR-089 `PUJ-18`), so a miss means a caller invented an id. Returning ""
  // would render an empty <h4> that tsc, eslint and every toContain assertion
  // pass over — hard-won law 2. The equality test in
  // `PremisesFormSections.test.tsx` is what holds this now.
  return section?.labelKey ?? "";
}

/**
 * One heading and the controls under it.
 *
 * ⚠ **`hint` IS OPTIONAL AND IS CAPPED AT ONE SENTENCE BY B14 RULE 32** — *"a
 * screen has a description budget: one sentence per section"*, ratified after
 * the PO said *"too much content - desctiption is too much for clark to read"*
 * four times in twenty minutes.
 *
 * ⚠ **`optional` IS A CHIP ON THE HEADING, WHICH IS WHERE THE FRAME PUTS IT** —
 * *"the optional section says it is optional, on the heading, so a clerk in a
 * hurry knows what they may skip."* It is the kit's `Chip` rather than a word
 * in the heading string, so it cannot be mistaken for part of the question in
 * any of the eleven catalogues.
 */
export function PremisesFormSection(props: {
  id: PremisesFormSectionId | string;
  t: Translator;
  hint?: string;
  /** Draws the `optional` chip beside the question. */
  optional?: boolean;
  children: ReactNode;
}) {
  return (
    <section data-premises-section={props.id}>
      <h4>
        {props.t(labelKeyFor(props.id))}{" "}
        {props.optional === true ? <Chip>{props.t("metering.premises.section.optional")}</Chip> : null}
      </h4>
      {props.hint === undefined ? null : <p className="met-panel-hint">{props.hint}</p>}
      {props.children}
    </section>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-089 §6 wave B task B8 — 12-governance/change-requests/CR-089-premises-units-rejourneyed.md
// generated: 2026-09-09 by the CR-089 wave B lane
// amended:   2026-09-10 by the CR-089 P2/P3 conformance lane — six statement
//            headings become the four QUESTION headings the blueprint's frame
//            draws (PO ruling 2026-09-10, *"(a) The frame wins"*), plus the
//            `optional` chip the `READING AND BILLING` heading carries.
// checklist: A✔ B✔ C✔ D=n/a(no endpoint) E✔ F✔ G✔ H=n/a
// exceptions:
//   E3 the frame draws the four headings in SMALL UPPERCASE. This file is Route
//      A and B14 rule 21 forbids it a stylesheet class, so the heading is an
//      unclassed `<h4>` in sentence case and the case treatment is recorded as
//      a divergence in the conformance file rather than faked with a utility
//      that would render as nothing.
//   E3 CLOSED 2026-09-10 — the edit form is re-cut onto the four
//      (`CR-089-p036`), the transitional label map is deleted, and the equality
//      assertion it stood in for is restored.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
