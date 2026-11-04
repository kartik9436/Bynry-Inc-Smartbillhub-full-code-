// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-001 (EP-CWP-01) — the front page's building blocks.
//           Screens: CWP-001 (and every guest hub after it)
// Rules:    B14 rule 36 (PO 2026-09-04: the captured pack gives the LAYOUT,
//           05-prototype/r10-2026-08-16/UI-RULES.md gives the LOOK, and the
//           SHARED KIT is how you comply: every piece below either IS a staff
//           component or wraps one) · r10 rule 4 (button grammar) · rule 5
//           (two sizes) · rule 6 (danger is for destructive commits and
//           nothing else — nothing here is danger) · rule 9 (never a wall of
//           checkboxes) · rule 10 · rule 11 · rule 18 ·
//           09-component-inventory.md §0 (tokens) · §2 `PageHead` · §3
//           `InfoBar` · §4 `ErrandCard` — including its DISABLED state, PO
//           ruling 2026-09-05: all six errand cards are shown, disabled where
//           unavailable, *"for completess"* · §5 `Button` HELD (CR-068 R3,
//           BR-CWP-056: a control that may not be used yet is disabled WITH
//           its reason beneath it — never hidden, never live-but-inert) ·
//           B14 rule 21 (Tailwind utilities; this folder is on
//           route-b-migrated.txt) · rule 5 (two button sizes — the staff kit's)
//           · rule 32 (one sentence per section) · rule 33 (a held reason is
//           five or six words)
// Tests:    src/portal/guest/FrontPage.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ EVERY CLASS BELOW WAS ASKED OF THE COMPILER BEFORE IT WAS WRITTEN. This
// theme clears Tailwind's stock palette, sizes and radii (`src/styles/
// tailwind.css` `--color-*: initial` …), so `bg-white`, `text-lg` and every
// `slate` shade compile to NOTHING while `tsc` and every `toContain` pass —
// DEF-974's trap, and the inventory's own token table names two of them. The
// portal writes the theme's names instead: `bg-[white]` (an arbitrary value
// the compiler honours), `text-neutral-*`, `text-lead`, `text-lead`. The
// walkthrough asserts computed style so the next lane cannot lose this quietly.

import { createContext, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { Button, ButtonLink } from "@/components/Button";
import { SectionHeadingTag, SectionScope, useSectionHeading } from "@/components/HeadingLevel";
import { Panel } from "@/components/Panel";
import { SegmentedControl } from "@/components/SegmentedControl";
import { WorkingButton, type CommitTier } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { formatQuantity as formatQuantityNumber } from "@/components/UnitCell";

import { FieldWiringProvider, useAnnounce, useFieldWiring, useFormScope, useScopedField } from "./a11y";

/* ⚠ **`PageHead` USED TO BE DECLARED HERE — `DEF-CWP-3655`, B14 rule 36.** It
 * drew a kicker, an `<h1>` and one grey subtitle out of raw utilities, which is
 * `components/PageHeader.tsx` with different type sizes: the kit's header has
 * held exactly that skeleton (kicker · title · sub-line · right-aligned
 * actions) since B14 rule 2, and it is where `DEF-966` moved the status pill
 * out of the action row. The guest screens name it directly now —
 * `<PageHeader kicker={…} title={…} rollup={…} />` — and the subtitle rides in
 * `rollup`, which is that component's own word for the line under the title.
 */

/** Three cards a row on a wide screen, one on a phone. */
export function CardGrid3(props: { children: ReactNode }) {
  // ⚠ **MAX-WIDTH, LIKE THE WHOLE THEME (`DEF-CWP-4004`).** Three columns is
  // the base rule and the phone is the override — see `KpiRow` below, which
  // has been written this way since the week it was built.
  return <div className="grid grid-cols-3 gap-4 max-md:grid-cols-1">{props.children}</div>;
}

/**
 * A control that exists and may not be used yet — CR-068 R3 made a component.
 * The staff kit's disabled presentation PLUS a visible one-line reason, on the
 * button's `title` as well so a hover reads it. Never hidden, never
 * live-but-inert: a greyed button with a live route behind it is *built is not
 * wired* inverted (US-CWP-001 §1).
 */
export function HeldButton(props: { label: string; reason: string; size?: "default" | "sm" }) {
  // F-22 (`DEF-CWP-10551`): the sentence was always drawn; now the button
  // also POINTS at it, so a screen reader reads the reason with the button.
  const reasonId = `held-${useId()}`;
  // F-23 (`DEF-CWP-10566`): inside an errand card the name carries the card.
  const actionName = useErrandActionName(props.label);
  return (
    <div className="flex flex-col items-start gap-1" data-held="true">
      <Button
        variant="secondary"
        size={props.size ?? "sm"}
        disabled
        title={props.reason}
        aria-describedby={reasonId}
        aria-label={actionName}
      >
        {props.label}
      </Button>
      <span id={reasonId} className="text-base text-neutral-600">
        {props.reason}
      </span>
    </div>
  );
}

/**
 * Title · grey two-line description · `Start →` at the bottom. Always in a
 * CardGrid3.
 *
 * ⚠ **`unavailable` ARRIVED 2026-09-05 WITH THE PO RULING THAT REVERSED THE
 * FILTERING** — *"Yoi ahev these cards - may be disable them, but for
 * completess have them on screen"*. Before it, a card a tenant could not offer
 * never reached the browser at all, so an absence carried no explanation and
 * B14 rule 17 could not reach it: a card that is never drawn has no empty
 * state, empty or otherwise (`DEF-CWP-3953`).
 *
 * The disabled presentation is the KIT's single decision about what
 * *offered-and-not-usable* looks like (B14 rule 36) — the card recedes to the
 * page's own ground, its words drop to the muted step, and it is announced to
 * a screen reader as disabled. Its REASON is the caller's `action`, which is a
 * `HeldButton`: a fact gets its own declared line (r10 rule 32) and is never
 * squeezed into the row of things a person can press.
 *
 * `reasonCode` rides on a `data-` attribute for the tests and the walkthrough
 * and is NEVER rendered — it is an internal code, and rule 31 keeps those off
 * the glass.
 */
export function ErrandCard(props: {
  cardKey: string;
  title: string;
  description: string;
  action: ReactNode;
  unavailable?: boolean;
  reasonCode?: string;
}) {
  const off = props.unavailable === true;
  // `DEF-CWP-10563`: the level is the outline's (h2 under a page h1), the size
  // is `text-lead` whatever the level.
  const heading = useSectionHeading(2);
  return (
    <article
      className={
        off
          ? "flex flex-col gap-2 border border-neutral-200 bg-bg p-4"
          : "flex flex-col gap-2 border border-neutral-200 bg-[white] p-4"
      }
      data-errand={props.cardKey}
      data-unavailable={off ? (props.reasonCode ?? "true") : undefined}
      aria-disabled={off ? true : undefined}
    >
      <SectionHeadingTag
        tag={heading.tag}
        className={off ? "text-lead font-bold text-neutral-500" : "text-lead font-bold text-neutral-900"}
      >
        {props.title}
      </SectionHeadingTag>
      <p className={off ? "text-body leading-relaxed text-neutral-500" : "text-body leading-relaxed text-neutral-600"}>
        {props.description}
      </p>
      <ErrandCardContext.Provider value={props.title}>
        <SectionScope inner={heading.inner}>
          <div className="mt-auto pt-2">{props.action}</div>
        </SectionScope>
      </ErrandCardContext.Provider>
    </article>
  );
}

/**
 * The heading of the `ErrandCard` an action sits in, or `null` outside one.
 *
 * ⚠ **`DEF-CWP-10566` (tester F-23).** Every card's action reads `Start →`, so
 * the front page alone carried six links of one name to six places, and a
 * screen reader's list of links read *Start, Start, Start…*. PO/QA ruled
 * 2026-10-23 (*"Keep "Start →" on screen; a screen reader hears "Start: Pay a
 * bill""*): the visible words do not move and the NAME adds the card's own
 * heading. Through context, so the eight call sites pass nothing new and a new
 * card is named correctly with no line written for it.
 */
const ErrandCardContext = createContext<string | null>(null);

/** `"Start →"` inside the *Pay a bill* card → `"Start: Pay a bill"`; `undefined` outside a card. */
export function useErrandActionName(visible: string): string | undefined {
  const { t } = useTranslation();
  const card = useContext(ErrandCardContext);
  if (card === null) return undefined;
  return errandActionName(visible, card, (action, title) => t("portal.actionName", { label: action, value: title }));
}

/**
 * The accessible name of a card's action. The visible arrow is dropped — it is
 * a direction for the eye, and a screen reader would otherwise say *"right
 * arrow"* in the middle of the name.
 */
export function errandActionName(
  visible: string,
  card: string,
  format: (action: string, card: string) => string,
): string {
  const action = visible.replace(/\s*[→›»]+\s*$/u, "").trim();
  return format(action === "" ? visible : action, card);
}

/**
 * A repeated row control named for its own row — *"Open this document:
 * BL-2609-000651"* (`DEF-CWP-10566`; PO/QA 2026-10-23, Group E ruling 2:
 * *"Repeated row links get their row's subject"*). Without a subject (a letter
 * that minted no number) the plain words stand, which is what they were.
 */
export function rowActionName(
  action: string,
  subject: string | null | undefined,
  t: (key: string, options: Record<string, string>) => string,
): string {
  if (subject === null || subject === undefined || subject.trim() === "") return action;
  return errandActionName(action, subject, (a, s) => t("portal.actionName", { label: a, value: s }));
}

/**
 * Full-width single row: a brand `i`, one sentence with a bold clause, an
 * optional trailing control.
 *
 * ⚠ **`tail` AND `below` ARRIVED 2026-09-05 AND BOTH ARE THE DRAWING'S OWN
 * SHAPE, READ OFF THE IMAGE.** The pair `lead` + `bold` could only ever bold
 * the END of a sentence, and `CWP-034` bolds its SECOND WORD — *An **estimated**
 * reading is our best guess…* — so the screen was bolding the whole following
 * sentence instead and emphasising something other than the thing being
 * defined. `tail` is the remainder after the bold clause. **Each catalogue
 * writes all three parts and may put the emphasis where its own grammar puts
 * it** (B14 rule 35); a language that leads with the noun writes an empty
 * `lead`.
 *
 * `below` is a control on its own line UNDER the sentence, inside the same
 * box — which is where `CWP-037.png` draws *Report a problem*, not on the
 * right where `trailing` puts it. Both slots are optional and no existing
 * call site changes.
 */
export function InfoBar(props: {
  lead: string;
  bold: string;
  tail?: string;
  trailing?: ReactNode;
  below?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2 border border-neutral-200 bg-[white] px-4 py-3 text-body">
      <div className="flex items-start gap-3">
        <span className="shrink-0 font-bold text-accent-text" aria-hidden="true">
          i
        </span>
        <p className="min-w-0 flex-1 text-neutral-700">
          {props.lead} <span className="font-bold text-neutral-900">{props.bold}</span>
          {props.tail !== undefined ? ` ${props.tail}` : null}
        </p>
        {props.trailing !== undefined ? <div className="shrink-0">{props.trailing}</div> : null}
      </div>
      {/* The control sits under the sentence and indents past the `i`, so the
          notice reads as one block rather than as a sentence and a stray
          button. */}
      {props.below !== undefined ? <div className="pl-6">{props.below}</div> : null}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// CR-068 wave C — the pieces CWP-008 · CWP-047 · CWP-009 · CWP-010 are drawn
// from (09-component-inventory.md §6 `MiniTable` · §7 `ConsequenceBox` · §8
// `KVList` · §9 `Stepper` · §10 `StatusChip` · §11 `Panel` · §12 `FormField`)
// ═══════════════════════════════════════════════════════════════════════════
//
// ⚠ EVERY CLASS BELOW WAS ASKED OF THE COMPILER BEFORE IT WAS WRITTEN, for the
// reason the header of this file already gives: this theme clears Tailwind's
// stock palette and type scale, so `bg-white`, `text-lg` and every `slate`
// shade are class names that render as NOTHING while tsc and every `toContain`
// pass (DEF-974). The walkthrough reads computed style back out of a real
// engine so the next lane cannot lose this quietly.

/**
 * `TwoCol` — main and rail, drawn at ≈ 62/35 (`08-screen-layouts.md`).
 *
 * ⚠ **THERE WERE TWO OF THESE UNDER ONE NAME UNTIL 2026-09-05**
 * (`DEF-CWP-3984`, audit row D9) — this one and another in
 * `portal/components/content.tsx`, one directory apart, which is `TwoCol`'s
 * turn at the drift `DEF-CWP-3655` folded out of `Panel` and `Chip`. The
 * second author could not see the first because an import names a PATH, and
 * `tsc` cannot see it because each file imports its own.
 *
 * ⚠ **THE ONE REAL DIFFERENCE WAS THE MAIN COLUMN'S SPACING, AND THE OTHER
 * ONE WAS RIGHT.** They agreed on the grid; `content.tsx`'s gave the main
 * column `flex flex-col gap-4`, matching the rail, and this one did not — so a
 * screen passing several cards as `main` drew them FLUSH AGAINST EACH OTHER
 * beside a rail whose cards were spaced. That was live on `CWP-028` (the bill)
 * and `CWP-047` (tracking a request), and it is fixed by the fold rather than
 * by either screen. The other twenty-five callers pass a single element as
 * `main`, where `flex flex-col` changes nothing.
 *
 * ⚠ **NOW MAX-WIDTH, WHICH IS WHAT THE THEME MANDATES (`DEF-CWP-4004`).**
 * `tailwind.css` says it in capitals — *"authoring reads `max-lg:grid-cols-1`
 * — NEVER `lg:grid-cols-2`"* — and CLEARS Tailwind's min-width namespace so
 * the two scales cannot sit side by side under overlapping names. The old
 * `md:` form read correctly BY ACCIDENT (one column below 900px, two above),
 * which is why nothing ever went wrong and why a lane reading this component
 * for the house style found the opposite of the rule.
 *
 * ⚠ **THE `col-span` OVERRIDES ARE LOAD-BEARING AND ARE WHY THIS WAS NOT A
 * RENAME.** The base grid is now `grid-cols-12`, so each child carries its
 * span as the BASE rule. Below 900px the grid collapses to one column, and a
 * child still asking for `col-span-8` there would span into SEVEN IMPLICIT
 * COLUMNS — a silently broken phone layout that `tsc`, eslint and every
 * `toContain` assertion pass over. `max-md:col-span-1` on both children is
 * what makes the collapse real.
 */
export function TwoCol(props: { main: ReactNode; rail: ReactNode }) {
  return (
    // ⚠ **THE THREE MARKS ARE FOR CHECKS, AND THEY ARE WHY D9 WAS FINDABLE AT
    // ALL.** Audit row D14's finding is that nothing in this repo compares a
    // built screen with its drawing, and the reason is partly mechanical:
    // *does this screen have a rail* had no selector, so a test had to count
    // `nth-child` on a structure any later edit moves. `data-twocol-rail` is
    // one selector, it survives a re-order, and it is the same posture
    // `data-kpi-row`, `data-kvlist` and `data-chart` already take.
    <div className="grid grid-cols-12 gap-4 max-md:grid-cols-1" data-twocol="">
      <div className="flex flex-col gap-4 col-span-8 max-md:col-span-1" data-twocol-main="">
        {props.main}
      </div>
      <div className="flex flex-col gap-4 col-span-4 max-md:col-span-1" data-twocol-rail="">
        {props.rail}
      </div>
    </div>
  );
}

/** A bordered white card — the main column's container on every guest screen. */
export function Card(props: { children: ReactNode; testId?: string }) {
  return (
    <section
      className="flex flex-col gap-4 border border-neutral-200 bg-[white] p-4"
      data-testid={props.testId}
    >
      {props.children}
    </section>
  );
}

/* ⚠ **`Panel` USED TO BE DECLARED HERE AND IT IS THE KIT'S NOW — `DEF-CWP-3655`.**
 * It was a rail `<aside>` with its own border, its own small-caps heading and
 * an `info` tone that changed the FILL, while `portal/components/content.tsx`
 * exported another `Panel` whose `info` tone changed the BORDER, one directory
 * from `components/Panel.tsx` which had gained a `title` prop that very morning
 * under B14 rule 36. Three opinions, one name, and the second author could not
 * see the first because an import names a PATH.
 *
 * The kit's `Panel` now carries `as="aside"`, `tone` and `trailing`, so every
 * guest screen composes it: `<Panel as="aside" tone="info" title={…}>`. The one
 * visual decision the fold settles is that **a tone is a border, not a fill** —
 * see `PanelTone` in `components/Panel.tsx` for why.
 */

/** A section title inside a card — small caps, the wireframe's own device. */
export function SectionTitle(props: { children: ReactNode }) {
  return (
    <p className="text-xs font-bold uppercase tracking-wide text-neutral-900">{props.children}</p>
  );
}

/**
 * ⚠ **`info` ARRIVED 2026-09-04 WITH `DEF-CWP-3655`.** `content.tsx` exported a
 * SECOND chip with four tones — success, neutral, info, warning — under its own
 * markup, and its own comment said so: *"the staff kit's tones, its own
 * markup."* Folding it here rather than keeping two meant this union had to
 * hold everything the guest surface actually asks for. `StatusPill` already had
 * all six, with the contrast of each fill MEASURED rather than assumed
 * (`DEF-722`), so nothing new was drawn — a name was deleted.
 */
//
// ⚠ **`danger` ARRIVED 2026-09-04 WITH `CWP-023` (CR-068 wave F), AND IT IS
// B14 RULE 36 WORKING RATHER THAN THE RULE BEING BENT.** An overdue balance is
// the first thing the portal has had to say in the strongest tone, and the
// rule's own mechanism is *"where the kit lacks a piece, ADD IT TO THE KIT"* —
// so nothing was drawn here. `StatusTone` already carries all six and
// `danger` composes `.pill.past`, StateFrame.css's own rule, whose contrast
// was measured rather than assumed (`DEF-722`). Widening this union by one
// name is the whole change; a red span in `MyAccounts.tsx` would have been a
// fifth chip and a colour nobody had checked.
export type ChipTone = "success" | "neutral" | "warning" | "info" | "danger";

/**
 * A status word in a box — **the shared kit's `StatusPill`, wearing the
 * portal's data attribute and nothing else.**
 *
 * ⚠ **THIS USED TO BE ITS OWN SPAN WITH ITS OWN THREE TONES, AND B14 RULE 36
 * IS WHY IT IS NOT (PO 2026-09-04).** The rule's mechanism, verbatim: *"compose
 * the kit. Where the kit lacks a piece, ADD IT TO THE KIT — one component, one
 * visual decision, every screen — rather than hand-rolling it in the screen,
 * which is how four screens acquire four different chips."* The kit already
 * held this component, with its contrast ratios MEASURED against each fill
 * rather than assumed (`StatusPill`, DEF-722); a second one here would have
 * been a fifth chip and a colour nobody had checked.
 */
export function StatusChip(props: { tone: ChipTone; children: ReactNode; testKey?: string }) {
  return (
    // ⚠ **UPPERCASE AND LETTER-SPACED, AND THAT IS THE PORTAL'S DECISION RATHER
    // THAN THE PILL'S** (`DEF-CWP-4002`; `13-wireframe-delta.md` X3 — the
    // wireframe draws `IN SERVICE`, `CLEARED`, `DUE`, `BOUNCED`; the build
    // shipped `Cleared`). It is applied HERE, on the portal's wrapper, and not
    // on `.pill` in `StateFrame.css`, because that class is the staff app's
    // too and this is not a change anybody asked for over there.
    //
    // ⚠ **IN CSS, NEVER IN THE STRING.** Uppercasing the catalogue value would
    // shout it into eleven languages at once — and `ja-JP`, `ko-KR` and `hi`
    // have no letter case, so the "uppercase" spelling would be identical to
    // the ordinary one while the German and French ones lost their sentence
    // shape in the accessible name. `text-transform` leaves the WORD alone:
    // the screen reader still says *Due in 12 days*.
    //
    // The pair is the one `SectionTitle` already writes six lines up, so the
    // theme demonstrably emits both — and `src/styles/routeBUtilities.test.ts`
    // asks the real Tailwind compiler about every class in this directory, so
    // a utility that compiled to nothing would fail a merge-blocking test
    // rather than render as silence (DEF-974).
    <span className="uppercase tracking-wide" data-chip={props.testKey ?? props.tone}>
      <StatusPill tone={props.tone}>{props.children}</StatusPill>
    </span>
  );
}

export interface MiniTableColumn {
  key: string;
  /**
   * ⚠ **A `ReactNode` AND NOT A `string`, SINCE 2026-09-05 (`DEF-CWP-3977`).**
   * B14 rule 13 puts a `⇅` BUTTON inside a sortable heading — the same shape
   * the staff `DataTable` uses — and a `string` cannot carry one. Widened
   * rather than duplicated: the alternative was a second table with a second
   * header, which is the one thing the tables decision of that day exists to
   * avoid. Plain headings still pass a plain string and nothing moves.
   */
  label: ReactNode;
  align?: "left" | "right";
}

export interface MiniTableRow {
  key: string;
  muted?: boolean;
  cells: Record<string, ReactNode>;
}

/**
 * The four-row table on `CWP-008`. Not the staff `DataTable` — no toolbar, no
 * sort, no footer, four rows and four columns (B14 rule 4 is about the one
 * table TYPE staff screens use; this is a read-only mini table the inventory
 * lists separately).
 *
 * ⚠ **IT SCROLLS INSIDE ITSELF ON A NARROW SCREEN.** A table is the one thing
 * that reliably pushes a page sideways, and the walkthrough asserts the body
 * never does.
 */
export function MiniTable(props: {
  columns: MiniTableColumn[];
  rows: MiniTableRow[];
  caption: string;
}) {
  return (
    <div className="overflow-x-auto">
      {/* r10 rule 20: table type is ONE size everywhere — `--table-font-size`,
          13.5px, the same token the staff DataTable renders at. Not the
          15px body size the rest of this screen uses, and not an inline
          override. */}
      <table className="w-full border-collapse text-table" data-minitable="">
        <caption className="sr-only">{props.caption}</caption>
        <thead>
          <tr>
            {props.columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                // ⚠ **`px-3` IS LOAD-BEARING — THIS TABLE HAD VERTICAL PADDING
                //     ONLY, AND ON `border-collapse` A RIGHT-ALIGNED COLUMN THAT
                //     IS NOT LAST BUTTS STRAIGHT INTO ITS NEIGHBOUR
                //     (`DEF-CWP-3956`).** Bills read `AMOUNT   OWINGSTATUS`;
                //     Payments read `AMOUNTSTATUS`; Every reading collided in the
                //     BODY too — `800 kWhRead by a meter reader`. Measured, not
                //     inferred: `Expected` ended at x=996 and `Status` began at
                //     x=996. Twelve tables across eleven screens, all from here.
                //     `first:pl-0 last:pr-0` keeps the table lined up with the
                //     panel edge, which is why the fix is not a bare `px-3`.
                //     `PreferenceGrid` in this same file already carried `pr-3`,
                //     so this was one component that forgot, not a convention.
                className={`border-b border-neutral-300 px-3 pb-2 text-table-header font-bold uppercase tracking-table-header text-neutral-700 first:pl-0 last:pr-0 ${
                  column.align === "right" ? "text-right" : "text-left"
                }`}
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
              data-row={row.key}
              data-muted={row.muted ? "true" : undefined}
              className={row.muted ? "text-neutral-600" : "text-neutral-900"}
            >
              {props.columns.map((column) => (
                <td
                  key={column.key}
                  className={`border-b border-neutral-200 px-3 py-2 first:pl-0 last:pr-0 ${
                    column.align === "right" ? "text-right" : "text-left"
                  }`}
                  data-cell={column.key}
                >
                  {row.cells[column.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * B14 rule 11's consequence box — **the SHARED kit's, since 2026-09-05.**
 *
 * ⚠ **IT WAS DECLARED HERE AND IT IS NOT ANY MORE (B14 rule 36, `G86` clause
 * (c)).** `components/ConsequenceBox.tsx` now holds both shapes: this one — a
 * heading and its bullets, with the left brand rule — and the staff screens'
 * tone-title-sentence strip. The markup, the classes and the `data-consequence`
 * hook are byte-for-byte what this file rendered, so **nothing on any of the
 * seventeen portal screens that draw one moves a pixel**; what changed is that
 * there is one component under the name rather than two in two directories.
 *
 * Re-exported rather than deleted so every call site keeps its import.
 */
export { ConsequenceBox } from "@/components/ConsequenceBox";

/** Label on the left, value bold on the right — the review step's summary. */
export function KVList(props: { rows: { key: string; label: string; value: ReactNode }[] }) {
  return (
    <dl className="flex flex-col" data-kvlist="">
      {props.rows.map((row) => (
        <div
          key={row.key}
          className="flex items-baseline justify-between gap-4 border-b border-neutral-200 py-2"
          data-kv={row.key}
        >
          <dt className="text-body text-neutral-700">{row.label}</dt>
          <dd className="text-body font-bold text-neutral-900">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * `TotalRow` — the bottom line under a `KVList`, and the kit's, not a screen's.
 *
 * ⚠ **THIS WAS THE ONE PIECE `CWP-044` AND `CWP-063` GENUINELY LACKED, AND
 * B14 RULE 36 SAYS WHAT TO DO ABOUT THAT:** *"where the kit lacks a piece, ADD
 * IT TO THE KIT — one component, one visual decision, every screen — rather
 * than hand-rolling it in the screen, which is how four screens acquire four
 * different chips."* Two screens needed a heavier closing row on the same day;
 * writing it twice is how they would have ended up 1px and one type size
 * apart.
 *
 * `09-component-inventory.md` §4 already SPECIFIES it as a `KVList` variant
 * and this is that specification, declaration for declaration:
 *     border-t-2 border-neutral-900 · both sides bold · text-[17px]
 * which in this theme's names is `border-t-2 border-neutral-900` and
 * `text-lead`. ⚠ **`text-lead` IS 16px AND THE INVENTORY SAYS 17px, AND THAT
 * IS DELIBERATE RATHER THAN A MISS** — `tailwind.css` declares no 17px step,
 * `ErrandCard`'s title renders the inventory's own 17px heading at `text-lead`
 * already, and writing `text-[17px]` here would put a fifth type size in the
 * product to satisfy a number nobody would measure. Same step, same token, one
 * scale.
 *
 * ⚠ **IT IS A `<div>` AND NOT A `<dl>`, DELIBERATELY.** It sits INSIDE the
 * caller's own `KVList` markup pattern as its last row, so wrapping it in a
 * second definition list would nest one list inside another for a visual
 * effect. The caller renders `<KVList/>` then `<TotalRow/>`; a screen reader
 * gets the pairs and then the total, in that order.
 */
/**
 * ⚠ **`signed` ARRIVED 2026-09-04 WITH `CWP-030` (CR-068 wave H), AND IT IS
 * B14 RULE 36 WORKING RATHER THAN THE RULE BEING BENT.** *Why August cost
 * $3.74 more* is the first total this product has had to state a DIRECTION
 * for, and `08-screen-layouts.md` draws it as *positives in brand red*. A
 * second `TotalRow` in that screen would have been the `Panel` defect again
 * (`DEF-CWP-3655`), so this widens the one that exists by a single optional
 * prop. Omitted, every existing call site renders exactly what it did.
 *
 * ⚠ **THE SIGN ITSELF IS THE CALLER'S AND NOTHING HERE READS IT.** This prop
 * chooses a colour; it never inspects, strips or re-derives the figure, which
 * is why a bill that FELL cannot be painted as one that rose.
 */
export function TotalRow(props: {
  label: string;
  value: ReactNode;
  testKey?: string;
  signed?: "up" | "down" | "flat";
}) {
  return (
    <div
      className="flex items-baseline justify-between gap-4 border-t-2 border-neutral-900 py-2"
      data-total={props.testKey ?? ""}
      data-signed={props.signed}
    >
      <span className="text-lead font-bold text-neutral-900">{props.label}</span>
      <span
        className={`text-lead font-bold tabular-nums ${
          props.signed === "up" ? "text-accent-text" : "text-neutral-900"
        }`}
      >
        {props.value}
      </span>
    </div>
  );
}

/**
 * The four-step bar. A done step reads ✓, the current one its number, the rest
 * their numbers greyed — and **it is not a navigation control**: an applicant
 * moves with the buttons, so nothing here is clickable and nothing here lies
 * about being clickable.
 */
export function Stepper(props: { steps: string[]; current: number }) {
  // ⚠ Max-width (`DEF-CWP-4004`): four abreast is the base rule and two on a
  // phone is the override, which is the direction this theme mandates.
  return (
    // ⚠ **`mb-6` AND NOT `mb-4` — B14 rule 39's `rail margin-bottom 24`
    // (`CR-085`).** Measured at 16px on all nine wizard addresses at both
    // widths on 2026-09-11, against an anchor of 24: the bar that says WHERE
    // YOU ARE sat the same distance from the form as two fields sit from each
    // other, so it read as the first row of the form rather than as the frame
    // around it. `--space-6` is the scale's *"between sections, after a wizard
    // rail"* step and this is the second half of that clause.
    <ol className="mb-6 grid grid-cols-4 gap-2 max-md:grid-cols-2" data-stepper="">
      {props.steps.map((label, index) => {
        const step = index + 1;
        const done = step < props.current;
        const now = step === props.current;
        return (
          <li
            key={label}
            data-step={step}
            data-state={done ? "done" : now ? "current" : "todo"}
            // ⚠ **`py-4 px-5 gap-3` — B14 rule 39's `step 16×20 gap 12`
            // (`CR-085`).** This cell measured `p-2` — **8×8 with an 8px icon
            // gap, all three of them half the anchor** — which is the PO's own
            // sentence measured: *"the components are too much close."* The
            // side padding is `--space-5` (20px), the step the same amendment
            // added to the scale on the day rule 39 was ratified, and the icon
            // gap is `--space-3`, the scale's *"step icon gap"* step by name.
            className={`flex items-center gap-3 border py-4 px-5 text-body ${
              now ? "border-accent text-neutral-900" : "border-neutral-200 text-neutral-600"
            }`}
          >
            <span
              className={`inline-flex h-5 w-5 shrink-0 items-center justify-center border text-xs font-bold ${
                now ? "border-accent text-accent-text" : "border-field-border"
              }`}
              aria-hidden="true"
            >
              {done ? "✓" : step}
            </span>
            <span className="truncate">{label}</span>
          </li>
        );
      })}
    </ol>
  );
}

/** One labelled control. `required` draws the brand asterisk the forms use. */
export function FormField(props: {
  id: string;
  label: string;
  required?: boolean;
  helper?: string;
  error?: string | null;
  children: ReactNode;
}) {
  // ⚠ **THE FIELD WIRES ITS OWN BOX — F-03, `DEF-CWP-10548`.** `TextInput`
  // has supported `invalid` / `describedBy` / `required` since `DEF-CWP-9215`,
  // and six callers passed the first, about forty the second and none the
  // third: hard-won law 2. So this publishes them and the box reads them
  // (`a11y.tsx` `useFieldWiring`); a form that passes nothing is still fully
  // marked, and one that passes its own still wins.
  //
  // ⚠ **AND A REQUIRED FIELD LEFT EMPTY IS CAUGHT HERE, INSIDE A `FormScope`**
  // — *"Fill this in."*, linked from the error summary (judgments 3 and 4).
  // Outside a scope nothing changes.
  const error = useScopedField(props.id, props.label, props.required === true, props.error);
  const scope = useFormScope();
  const helperId = props.helper !== undefined ? `${props.id}-helper` : null;
  const wiring = {
    id: props.id,
    errorId: fieldErrorId(props.id),
    helperId,
    invalid: Boolean(error),
    required: props.required === true,
  };
  return (
    // ⚠ **TWO GAPS, NOT ONE — B14 rule 39's field anatomy (`CR-085`).**
    //
    // This was `flex flex-col gap-1`: **one** 4px gap serving label → input AND
    // input → helper, so those two distances *could not differ by design*. Rule
    // 39 ratifies **5px** and **6px** with the reason spelled out — *"DOM ORDER
    // ALONE IS NOT ENOUGH: the helper must READ as attached to the input above
    // it, never to the label below it, and a 3/3/9 rhythm destroys that even
    // with correct markup"* — so the three gaps are ratified as FIGURES and a
    // single container gap cannot express them whatever it is set to.
    //
    // ⚠ **5 AND 6 ARE OFF THE SEVEN-STEP SCALE ON PURPOSE AND MUST NOT BE
    // ROUNDED.** The rule's own amendment of 2026-09-11 says so by name: the
    // KPI gap was rounded 6 → 8 that day and the field anatomy was *"NOT
    // GENERALISED … deliberately"*, because rounding these would change the
    // **1 : 1 : 4** ratio the PO specified, and the ratio is the point of the
    // clause rather than the individual numbers.
    //
    // Written as Tailwind's own multiplier steps (`1.25` × 4px = 5, `1.5` × 4px
    // = 6) and not as `mb-[5px]` — an arbitrary value is a number nobody can
    // find or change in one place, which is what rule 39 exists to end.
    //
    // ⚠ **AND THE 4px ABOVE WAS NEVER WHAT RENDERED UNDER AN INPUT.**
    // `global.css` restored the browser's `p { margin-block: 1em }` for the
    // staff app, so the measured input → helper distance in the portal was
    // **17px**, and `1em` made it a different number at every font size. That
    // is turned off for the portal at its root (`[data-portal] p`), which is
    // what makes these two figures the ones that actually render.
    <div
      className="flex flex-col"
      data-field={props.id}
      onInput={scope === null ? undefined : () => scope.clear(props.id)}
    >
      <label htmlFor={props.id} className="mb-1.25 text-base font-semibold text-neutral-800">
        {props.label}
        {props.required ? (
          <span className="text-accent-text" aria-hidden="true">
            {" *"}
          </span>
        ) : null}
      </label>
      <FieldWiringProvider value={wiring}>{props.children}</FieldWiringProvider>
      {props.helper !== undefined ? (
        <p id={helperId ?? undefined} className="mt-1.5 text-base text-neutral-600">
          {props.helper}
        </p>
      ) : null}
      {/* ⚠ **TIED AND ANNOUNCED — `DEF-CWP-9215`.** The error carries an id a
          box can point at (`fieldErrorId`, passed as the input's
          `describedBy`) and sits in a polite live region that is ALWAYS in the
          tree, so a screen reader hears the sentence the moment it appears
          rather than only a sighted reader seeing it (accessibility questions
          3 and 7, `22-product-maintenance-process.md` §6). */}
      <p
        id={fieldErrorId(props.id)}
        aria-live="polite"
        className={error ? "mt-1.5 text-base font-semibold text-danger-700" : "sr-only"}
        data-field-error={error ? props.id : undefined}
      >
        {error ?? ""}
      </p>
    </div>
  );
}

/** The id of a `FormField`'s error line — what its box names in
 *  `aria-describedby` (`DEF-CWP-9215`). */
export function fieldErrorId(id: string): string {
  return `${id}-error`;
}

/** The one input shape every guest form uses.
 *
 * ⚠ `multiline` ADDED 2026-09-04 (CR-068 wave B): `CWP-006`'s *Anything else*
 * is a two-line box in the wireframe, and a screen that reached for a bare
 * `<textarea>` would be the second input shape in a kit whose whole point is
 * that there is one (B14 rule 36). Same border, same padding, same type size —
 * only the element and the row count differ.
 */
export function TextInput(props: {
  id: string;
  value: string;
  type?: string;
  multiline?: boolean;
  onChange: (value: string) => void;
  placeholder?: string;
  /** `DEF-CWP-9215` — the box is refused: `aria-invalid`, read aloud. */
  invalid?: boolean;
  /** The id of the line that explains it (`fieldErrorId`, a helper). */
  describedBy?: string;
  /** Read aloud as required; the visible asterisk is `FormField`'s. */
  required?: boolean;
  /** `numeric` — a ZIP code (`DEF-CWP-9817`): a phone shows digits. */
  inputMode?: "decimal" | "numeric";
  /** What the browser may fill it with (`address-line1`, `postal-code` …) —
   *  WCAG 1.3.5, *identify input purpose* (`DEF-CWP-9817`). */
  autoComplete?: string;
}) {
  const { t } = useTranslation();
  // ⚠ **EVERY PASSWORD FIELD IN THE PORTAL GETS A REVEAL, AND IT LIVES HERE
  // RATHER THAN ON EACH SCREEN — `DEF-CWP-4377`.** The Product Owner, signing
  // in to Silver Creek on the live product: *"im unable to see the password -
  // this is an issue with all login or change password screen on customer
  // portal"*. There were three fields and no way to check any of them: sign in,
  // and the two on Set up your login, where a customer types a password TWICE
  // and is told only afterwards whether the halves matched.
  //
  // Putting it on the three screens would have been three copies of one rule
  // and a fourth field later with none. `TextInput` is what every portal form
  // already composes, so the reveal arrives everywhere at once and cannot be
  // forgotten by the next screen.
  const [revealed, setRevealed] = useState(false);
  const isPassword = props.type === "password";
  const wired = useFieldWiring(props.id, props);

  const shared = {
    id: props.id,
    value: props.value,
    placeholder: props.placeholder,
    ...wired,
    inputMode: props.inputMode,
    autoComplete: props.autoComplete,
    // ⚠ **`py-1.5 px-2.5 min-h-9` — B14 rule 39's `.input 6×10 min-h 36`
    // (`CR-085`).** This was `px-3 py-2` and measured **8 × 12, 41px tall**
    // against a staff `.input` measured at **6 × 10, 36px** on the same day —
    // **two input shapes in one product** (`DEF-CWP-4923`), which is the exact
    // second-copy-free-to-drift failure rule 39 was ratified to end.
    //
    // ⚠ **IT WILL NOT MEASURE EXACTLY 36 AND THAT IS STATED RATHER THAN
    // HIDDEN.** The staff `.input` reaches 36 because it is `--text-md` (14px);
    // the portal runs on `--text-body` (15px) because a customer reads this on
    // a phone. 15 × 1.55 + 12 + 2 ≈ **37**. The rule ratifies the PADDING and
    // the MINIMUM, both of which are now exact; the extra pixel is the type
    // size and belongs to a type decision, not a spacing one.
    className:
      "w-full min-h-9 border border-field-border bg-[white] px-2.5 py-1.5 text-body text-neutral-900",
  };
  if (props.multiline === true) {
    return <textarea {...shared} rows={2} onChange={(event) => props.onChange(event.target.value)} />;
  }
  const field = (
    <input
      {...shared}
      type={isPassword && revealed ? "text" : (props.type ?? "text")}
      onChange={(event) => props.onChange(event.target.value)}
    />
  );
  if (!isPassword) {
    return field;
  }
  return (
    <div className="flex items-stretch gap-2" data-password-field={props.id}>
      {field}
      {/* ⚠ **`type="button"` IS LOAD-BEARING, NOT TIDINESS.** A <button> inside
          a <form> defaults to `type="submit"`, so without this the reveal would
          SUBMIT THE SIGN-IN FORM — a customer pressing "Show" to check a typo
          would instead send the half-typed password and be told it was wrong.
          The control meant to prevent a failed sign-in would have caused one. */}
      <button
        type="button"
        className="shrink-0 border border-field-border bg-[white] px-3 text-base font-semibold text-accent-text"
        aria-controls={props.id}
        aria-pressed={revealed}
        data-password-reveal={props.id}
        onClick={() => setRevealed((was) => !was)}
      >
        {revealed ? t("portal.form.hidePassword") : t("portal.form.showPassword")}
      </button>
    </div>
  );
}

/** One month on a money chart. */
export interface MoneyBar {
  /** `2026-08`, or whatever the screen keys its rows by. */
  key: string;
  /** The row's own label — a month name the SCREEN composed. */
  label: string | null;
  /** The numeric value, used for the bar WIDTH and for nothing else. */
  value: number | null;
  /** Already money-formatted by the caller. See the note below. */
  display: string | null;
  /** The second series, when a screen draws one. */
  compareValue?: number | null;
  compareDisplay?: string | null;
}

/**
 * `MoneyBars` — a month-by-month chart of MONEY, with an optional second
 * series and an optional reference line.
 *
 * ⚠ **IT IS A SEPARATE COMPONENT FROM `UsageBars` ON PURPOSE, AND THE REASON
 * IS HARD RULE 3.** `UsageBars` is a CONSUMPTION chart: its `unit` prop is not
 * optional and there is no path that drops it, because a quantity always
 * carries its unit. Money is not a quantity and has no unit — it has a
 * CURRENCY — so passing billed amounts through `UsageBars` would label a
 * currency as a unit on the axis. `DEF-CWP-3981` sized that correctly and
 * declined to do it.
 *
 * ⚠ **THE CALLER FORMATS THE MONEY AND THIS COMPONENT NEVER DOES.** `display`
 * arrives already composed. That is deliberate twice over: this kit file must
 * not import `formatMoney` (which lives in `signin/Enrol` and imports back out
 * of here — a cycle), and money rounding belongs in exactly one place per
 * CLAUDE.md hard rule 2. A chart that formatted its own figures would be a
 * second arithmetic beside the one the screen already used for the same
 * numbers directly above it.
 *
 * ⚠ **NO CHART LIBRARY AND NO CANVAS**, which is `BilledBars`'s own reasoning
 * carried over when this was lifted out of `plans/LevelPay.tsx` (B14 rule 36 —
 * a screen drawing its own chart is how a product ends up with four different
 * charts). A `<div>` per month with a width stays legible at every width, adds
 * no dependency, and — the reason that matters — puts every figure in the DOM
 * as TEXT, so the walkthrough and a screen reader read the same numbers a
 * sighted customer does.
 *
 * ⚠ **`null` IS NOT `0`.** A month with no figure draws NO bar and says
 * nothing, rather than a zero-width bar reading as *"you paid nothing"*.
 *
 * ⚠ **THE BAR SHRINKS AND THE FIGURE DOES NOT (`DEF-CWP-4678`, 2026-09-08).**
 * The bar carried `shrink-0` beside a percentage width, so the tallest bar took
 * the whole row and its money label — 54px plus the gap — was then added ON TOP
 * of it. The row could only overflow, and at 390px `CWP-044` measured **415px of
 * document inside a 390px window**. `flex-shrink` is the whole fix: a long
 * figure now takes its room from the bar, which is the thing that can afford it,
 * and short bars barely move because flex shrinks in proportion to base size.
 * The `min-w-0` on the label's row is what lets the shrink actually happen — a
 * flex item will not shrink below its content without it.
 *
 * ⚠ **AND IT WAS FOUND ONLY BECAUSE A FIXTURE FINALLY BUILT THE ORDINARY CASE.**
 * Every seeded account was enrolled (this screen returns early and draws no
 * chart) or had no bills at all (the chart draws its empty sentence). An account
 * with a real run of bills and no enrolment — the person actually deciding
 * whether to join — existed in no fixture until `CR-085`.
 */
export function MoneyBars(props: {
  bars: MoneyBar[];
  /** Names the first series in the legend. */
  seriesLabel: string;
  /** Names the second series. Absent draws one series and no legend pair. */
  compareLabel?: string;
  /** The line drawn across the bars — a level, a target, an average. */
  referenceValue?: number | null;
  /** The already-composed sentence for that line. Absent draws no line. */
  referenceLabel?: string | null;
  emptyLabel: string;
  testId?: string;
}) {
  if (props.bars.length === 0) {
    return (
      <p className="mt-2 text-body text-neutral-600" data-money-chart-empty="">
        {props.emptyLabel}
      </p>
    );
  }
  const every = props.bars.flatMap((bar) =>
    [bar.value, bar.compareValue].filter((one): one is number => typeof one === "number"),
  );
  const ceiling = Math.max(...every, props.referenceValue ?? 0, 1);
  const width = (value: number | null | undefined) =>
    typeof value === "number" ? `${Math.max(2, Math.round((value / ceiling) * 100))}%` : "0%";
  const hasCompare = props.compareLabel !== undefined;
  return (
    <div data-money-chart={props.testId ?? ""}>
      <ol className="mt-3 flex flex-col gap-2">
        {props.bars.map((bar) => (
          <li key={bar.key} className="flex flex-col gap-0.5" data-money-month={bar.key}>
            {bar.label === null ? null : (
              <span className="text-base text-neutral-600">{bar.label}</span>
            )}
            <span className="flex min-w-0 items-center gap-2">
              {/* The reference decides the ACCENT, so a month above the line
                  reads as the exception it is — `BilledBars`'s own rule. */}
              <span
                aria-hidden="true"
                className={`h-3 min-w-0 ${
                  typeof props.referenceValue === "number" &&
                  typeof bar.value === "number" &&
                  bar.value > props.referenceValue
                    ? "bg-accent"
                    : "bg-neutral-100"
                }`}
                style={{ width: width(bar.value) }}
              />
              <span
                className="shrink-0 text-base tabular-nums text-neutral-600"
                data-money-value={bar.key}
              >
                {bar.display ?? "—"}
              </span>
            </span>
            {hasCompare ? (
              <span className="flex min-w-0 items-center gap-2">
                <span
                  aria-hidden="true"
                  className="h-3 min-w-0 bg-field-border"
                  style={{ width: width(bar.compareValue) }}
                />
                <span
                  className="shrink-0 text-base tabular-nums text-neutral-600"
                  data-money-compare={bar.key}
                >
                  {bar.compareDisplay ?? "—"}
                </span>
              </span>
            ) : null}
          </li>
        ))}
      </ol>
      {/* ⚠ A SWATCH WITH NO WORD BESIDE IT EXPLAINS NOTHING — `UsageBars`'s
          own legend rule. Two series always get two words. */}
      {hasCompare ? (
        <p className="mt-2 text-base text-neutral-600" data-money-legend="">
          <span className="font-semibold text-neutral-900">{props.seriesLabel}</span>
          {" · "}
          {props.compareLabel}
        </p>
      ) : null}
      {props.referenceLabel ? (
        <p className="mt-1 text-base text-neutral-600" data-money-reference="">
          {props.referenceLabel}
        </p>
      ) : null}
    </div>
  );
}

/**
 * `DocumentPreview` — the issued page, framed and letter-shaped
 * (`09-component-inventory.md` §4: *"`border border-neutral-200 p-6 grid
 * place-items-center` → `aspect-[8.5/11] w-[62%] border`"*).
 *
 * ⚠ **IT EMBEDS THE KEPT FILE ITSELF, AND THAT DISTINCTION IS THE WHOLE
 * COMPONENT.** `BR-CWP-045` and `BR-NOT-027` forbid the portal from RENDERING
 * a bill — a preview built out of the figures would be a second document
 * beside the legal one, free to differ from it, and its figures being right
 * would not make it honest. This puts the frozen bytes on screen in the
 * browser's own viewer. There is no second document; there is one document,
 * and now the customer can look at it.
 *
 * ⚠ **`<object>`, NOT `<iframe>` OR `<embed>`** — it is the only one of the
 * three with a CHILD FALLBACK, so a browser with no PDF viewer (and jsdom,
 * where every test runs) shows the children instead of a silent grey
 * rectangle. A preview that fails to a blank box is worse than the download
 * link it replaced.
 *
 * ⚠ **THE `aspect` IS ON THE FRAME AND THE OBJECT FILLS IT.** A PDF viewer
 * reports no intrinsic size, so an unsized `<object>` collapses to roughly
 * 150px tall — letter-shaped is a decision this component has to make, not
 * one the document makes for it.
 */
export function DocumentPreview(props: {
  href: string;
  title: string;
  children: ReactNode;
}) {
  // `DEF-CWP-10570` (2.4.7): a keyboard user tabbing into the bill saw no
  // ring. ⚠ **NO CSS SELECTOR CAN DRAW IT.** Measured in Chromium: once Tab
  // enters the PDF viewer, `document.activeElement` is the `<object>` but
  // `:focus`, `:focus-visible` and `:focus-within` are all FALSE on it and on
  // its parent, and the object fires no focus event — focus is inside the
  // viewer's own document. What does fire is the WINDOW's `blur`, with the
  // object as the active element; the window's `focus` fires when focus comes
  // back. So the ring follows those two, and `:focus` covers the fallback
  // (no viewer). The ring is the product's: 2px of the brand colour, 2px out
  // — `#ec3013` reads 4.20 on white and 3.76 on `#f3f2f2`, and Company →
  // Profile refuses a colour under 3:1.
  const frame = useRef<HTMLObjectElement>(null);
  const [inside, setInside] = useState(false);
  useEffect(() => {
    const left = () => window.setTimeout(() => setInside(document.activeElement === frame.current), 0);
    const back = () => setInside(false);
    window.addEventListener("blur", left);
    window.addEventListener("focus", back);
    return () => {
      window.removeEventListener("blur", left);
      window.removeEventListener("focus", back);
    };
  }, []);
  return (
    <div className="grid place-items-center border border-neutral-200 p-6" data-document-preview="">
      <object
        ref={frame}
        data={props.href}
        type="application/pdf"
        aria-label={props.title}
        tabIndex={0}
        data-focus-inside={inside ? "" : undefined}
        className={
          "aspect-[8.5/11] w-[62%] border border-neutral-200 bg-[white] focus:outline-2 focus:outline-offset-2 focus:outline-accent" +
          (inside ? " outline-2 outline-offset-2 outline-accent" : "")
        }
      >
        {/* The fallback is not decoration: it is what a customer on a browser
            with no viewer actually gets, so it has to be the way OUT of here. */}
        {props.children}
      </object>
    </div>
  );
}

/**
 * `DialInput` — the wide, spaced-digit box (`09-component-inventory.md` §5:
 * *"`font-mono text-[22px] tracking-[0.35em] h-14`; **flagged** →
 * `border-[var(--brand)]` + a brand helper sentence"*).
 *
 * ⚠ **BOTH TYPE VALUES ARE WRITTEN AS RULED STEPS AND NEITHER PIXEL MOVES.**
 * The inventory is raw Tailwind because it was drawn before the scale was
 * ruled, and eslint refuses both of its spellings by name: `text-[22px]` is
 * `text-metric-sm` (`--text-metric-sm: 22px`, decision log 2026-08-19,
 * `OQ-275`/`276`/`278`) and `tracking-[0.35em]` is `tracking-dial`, a token
 * added to `tailwind.css` beside the five wide-tracking values already named
 * there — `G34` bans the bracket form outright. Where the inventory and the
 * ruled scale disagree the scale wins, and 22px and 0.35em are unchanged.
 *
 * Two screens want it and they want it for the same reason: a **six-digit
 * one-time code** (`CWP-017`) and **the number on a meter dial** (`CWP-035`)
 * are both figures a person is COPYING from somewhere else, digit by digit,
 * and a box that spaces the digits out is a box you can check your work in.
 * `CWP-017` rendered a plain `TextInput` until today, which is the same
 * control as *Last name*.
 *
 * ⚠ **`flagged` IS A BORDER AND A SENTENCE, NEVER A REFUSAL.** `CWP-035`'s
 * drawn state is *"That is 5,900 gallons in two days — about nineteen times
 * your usual…"*: the reading is ACCEPTED and the customer is told it looks
 * unusual before they send it. The prop is therefore presentational and the
 * screen owns the sentence — this component never composes one, because a
 * quantity's words belong to the catalogue (B14 rule 35) and its unit belongs
 * to whoever knows the unit (hard rule 3).
 *
 * ⚠ **THE ACCENT IS `border-accent`, NOT `border-[var(--brand)]`** as the
 * inventory's prose spells it — `--brand` is set NOWHERE in this product and
 * every rule that read it painted grey (`DEF-CWP-3736`).
 *
 * ⚠ **THE BORDER COLOUR IS FILLED EXACTLY ONCE, BY NAME, RATHER THAN
 * APPENDED** — the slot discipline `Panel.tsx` records for its own tones. Two
 * utilities that both set the same property are a coin toss decided at build
 * time, so the flagged and unflagged spellings are whole strings rather than a
 * base string with a colour added to it.
 *
 * ⚠ **AND THAT PARAGRAPH LIVES HERE RATHER THAN INSIDE THE className
 * EXPRESSION, WHERE IT WAS FIRST WRITTEN AND WHERE IT BROKE THE BUILD-TRUTH
 * TEST.** `routeBUtilities.test.ts` extracts class TOKENS from the markup and
 * asks the real Tailwind compiler about each one; a line comment inside a
 * className expression is inside the markup as far as that scanner is
 * concerned, so two ordinary English words in it were reported as classes
 * that render nothing. The test was right in the only way that matters: it
 * cannot tell a comment from a class, and neither can Tailwind's own
 * scanner, which is why a class name built by interpolation is already broken
 * for a second reason. Comments about classes go ABOVE the attribute, or
 * here.
 *
 * ⚠ **`font-mono` IS DELIBERATE HERE AND IS BANNED TWO SCREENS AWAY.**
 * `StartService.test.tsx` refuses `font-mono` on `CWP-011` under *"renders no
 * wireframe style"* — a monospaced face there is annotation, left over from a
 * drawing. Here it is the point: proportional digits in a spaced box do not
 * line up, and the inventory names the face. The ban is per screen, not a
 * theme rule; `--font-mono` is one of the few Tailwind families
 * `tailwind.css` deliberately keeps (*"the existing literal"*).
 */
export function DialInput(props: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  flagged?: boolean;
  inputMode?: "numeric" | "decimal";
  maxLength?: number;
  placeholder?: string;
  /**
   * ⚠ **ADDED 2026-10-17 FOR `CWP-035`'s DIAL FIGURE (`DEF-CWP-10175`), TO THE
   * KIT AND NOT TO THE SCREEN** (B14 rules 36 and 43). The box was built for
   * `CWP-017`'s six-digit code and carried no way to say it was refused or
   * which line explains it — `TextInput` gained exactly these for
   * `DEF-CWP-9215` (accessibility questions 3 and 7). All optional: the one
   * existing caller renders byte for byte as before.
   */
  invalid?: boolean;
  describedBy?: string;
  required?: boolean;
  /** The code box is a one-time code; a meter figure is not (`off`). */
  autoComplete?: string;
}) {
  const wired = useFieldWiring(props.id, props);
  return (
    <input
      id={props.id}
      value={props.value}
      placeholder={props.placeholder}
      inputMode={props.inputMode ?? "numeric"}
      maxLength={props.maxLength}
      autoComplete={props.autoComplete ?? "one-time-code"}
      {...wired}
      data-dial-input={props.flagged === true ? "flagged" : ""}
      className={
        "h-14 w-full bg-[white] px-3 font-mono text-metric-sm tracking-dial text-neutral-900 " +
        (props.flagged === true ? "border border-accent" : "border border-field-border")
      }
      onChange={(event) => props.onChange(event.target.value)}
    />
  );
}

/** Two controls side by side on a wide screen, stacked on a phone. */
export function TwoUp(props: { children: ReactNode }) {
  // ⚠ Max-width (`DEF-CWP-4004`) — see `TwoCol` above for why the direction
  // matters even where both forms happen to render the same thing.
  // ⚠ **`gap-5` — B14 rule 39's `field → field 20px` (`CR-085`).** This is the
  // kit's field container, so its gap IS the third figure of the field anatomy
  // (5 : 6 : 20, a ratio of ≈ 1 : 1 : 4). It measured 16 — the same step the
  // rule gives to *between blocks* — which made a field's own helper and the
  // next field's label nearly equidistant from the input between them, and
  // that is the failure the anatomy clause describes in words.
  return <div className="grid grid-cols-2 gap-5 max-md:grid-cols-1">{props.children}</div>;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * CR-068 wave B — the five pieces this kit did not already hold
 *
 * ⚠ **WAVE B ARRIVED WITH ELEVEN AND ADDED FIVE, AND THE DIFFERENCE IS B14
 * RULE 36 DOING ITS JOB.** This lane had drafted its own `TwoCol`, `TwoUp`,
 * `FormField`, `ConsequenceBox`, `KVList` and two rail panels before reading
 * this file at the tip — where waves C and D had already built every one of
 * them. Six duplicates were deleted rather than merged, because the rule's
 * mechanism is *"one component, one visual decision, every screen"* and two
 * consequence boxes in one file is exactly the four-different-chips failure
 * the PO named. What is below is what genuinely had no home.
 * ═══════════════════════════════════════════════════════════════════════════ */

/** `flex items-center gap-2 mt-4` — a row of controls with NO way back in it.
 *  A row that has a Back, a Cancel or a Change is a `WizardFooter` (below). */
export function ButtonRow(props: { children: ReactNode }) {
  return <div className="mt-4 flex items-center gap-2">{props.children}</div>;
}

/**
 * **A FORM'S FOOTER: THE WAY BACK ON THE LEFT, THE WAY FORWARD ON THE RIGHT —
 * every step, every portal form, from this one place (`DEF-CWP-9164`).**
 *
 * PO 2026-10-02, verbatim: *"continue and Back button mis placed at right side
 * continue button should display at left side back button should display"* —
 * ruled the same day as **Back on the LEFT, Continue / Send on the RIGHT**
 * (decision log, *"PORTAL START-SERVICE FORM — FIVE DEFECTS"*). Until then the
 * order was `09-component-inventory.md` §5's *"commit first"* and every screen
 * hand-placed its own two buttons, so there was no one place for it to be
 * right — or wrong. Now there is, and a screen that wants a Back passes it here
 * rather than writing a row.
 *
 * ⚠ **`back` IS WHATEVER GOES BACKWARDS** — a stepper's `← Back`, a *Change*,
 * a *Cancel*, an exit to the card list. **`forward` is the commit and anything
 * beside it**, with the commit LAST so it sits at the far right. With no
 * `back`, the forward group still sits on the right, so a step's commit is in
 * the same place whether or not that step has a way back.
 *
 * ⚠ **ON A NARROW PHONE THE TWO GROUPS WRAP, BACK FIRST** — the DOM order is
 * the reading and tab order (Back, then forward), which is also the order a
 * screen reader announces them in.
 */
export function WizardFooter(props: { back?: ReactNode; forward: ReactNode }) {
  return (
    <div className="mt-4 flex flex-wrap items-start justify-between gap-2" data-wizard-footer="">
      <div className="flex flex-wrap items-center gap-2" data-footer-side="back">
        {props.back ?? null}
      </div>
      <div className="ml-auto flex flex-wrap items-start gap-2" data-footer-side="forward">
        {props.forward}
      </div>
    </div>
  );
}

/**
 * A single-choice list — **r10 rule 9's other half.** Rule 9 forbids a wall of
 * checkboxes for a MULTIPLE-choice field; this is the SINGLE-choice control,
 * and it is radios because exactly one answer is possible.
 *
 * The hint after `·` is the wireframe's *"· We treat this as urgent"* — grey,
 * inline, never a second line.
 */
export function RadioList(props: {
  name: string;
  value: string | null;
  options: readonly { value: string; label: string; hint?: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <div role="radiogroup" aria-label={props.name} data-radiolist={props.name}>
      {props.options.map((option) => (
        <label
          key={option.value}
          className="flex cursor-pointer items-center gap-3 py-1.5 text-body"
          data-radio={option.value}
        >
          <input
            type="radio"
            name={props.name}
            value={option.value}
            checked={props.value === option.value}
            onChange={() => props.onChange(option.value)}
          />
          <span className="text-neutral-900">{option.label}</span>
          {option.hint !== undefined ? (
            <span className="text-neutral-600">· {option.hint}</span>
          ) : null}
        </label>
      ))}
    </div>
  );
}

/**
 * *What happens now* — a vertical list of steps with a square marker: done is
 * ink with a ✓, **current is the tenant's brand**, future is grey.
 *
 * ⚠ **IT IS NOT THE `Stepper`, AND THE DIFFERENCE IS NOT COSMETIC.** A stepper
 * is where an applicant IS in a form they are filling; this is where a JOB is
 * in a process nobody on this screen controls. One moves when you press a
 * button, the other when a crew arrives.
 *
 * ⚠ **AND IT IS NOT A WIREFRAME ANNOTATION.** B14 rule 36 breach (a) was
 * production UI drawn in a sketch style; this is a solid 1px square, the brand
 * colour on the current step, nothing dashed and nothing monospaced.
 */
export function ChecklistTimeline(props: {
  steps: readonly {
    label: string;
    detail?: string;
    /**
     * A second, grey line under the step — **what happened**, where the
     * `detail` beside the label is **when**.
     *
     * ⚠ **ADDED TO THE KIT AND NOT TO THE SCREEN** (B14 rule 36: *"where the
     * kit lacks a piece, ADD IT TO THE KIT"*). `08-screen-layouts.md` draws
     * `CWP-051`'s ladder as *"bold step · date, grey actor/detail"* and every
     * step in the drawing carries one; live drew the date and nothing else, so
     * the ladder said WHEN each step happened and never WHAT
     * (`DEF-CWP-4201` row 51.4). Optional, so the four other callers are
     * unchanged and no pixel of theirs moves.
     */
    note?: string;
    state: "done" | "current" | "future";
  }[];
}) {
  const box: Record<string, string> = {
    done: "border-neutral-800 text-neutral-800",
    current: "border-accent text-accent-text",
    future: "border-field-border text-field-border",
  };
  return (
    <ol className="m-0 list-none p-0" data-timeline="">
      {props.steps.map((step) => (
        <li key={step.label} className="flex gap-3 py-2" data-timeline-step={step.state}>
          <span
            aria-hidden="true"
            className={`mt-0.5 grid h-4 w-4 shrink-0 place-items-center border text-xs leading-none ${box[step.state]}`}
          >
            {step.state === "done" ? "✓" : ""}
          </span>
          <span className="min-w-0 flex-1 text-body">
            <span className="font-bold text-neutral-900">{step.label}</span>
            {step.detail !== undefined ? (
              <span className="ml-2 text-neutral-600">{step.detail}</span>
            ) : null}
            {step.note !== undefined && step.note !== "" ? (
              <span className="block text-base text-neutral-600" data-step-note="">
                {step.note}
              </span>
            ) : null}
          </span>
        </li>
      ))}
    </ol>
  );
}

/**
 * The photo box, **HELD** — `CR-068` §2b, a signed deferral (PO 2026-08-08,
 * `DF-4`: *consumer upload portal = v2*) awaiting a re-sign.
 *
 * ⚠ **THERE IS NO `<input type="file">` HERE, AND THAT IS THE POINT.** A
 * disabled file input is still a file input, and the guest edge refuses a file
 * anyway. What renders is the control's SHAPE with its reason inside it, in the
 * same six-word form every other held control uses (`BR-CWP-056`, rule 33).
 * Never hidden, never live-but-inert.
 */
export function PhotoPicker(props: { reason: string }) {
  return (
    <div
      className="flex h-11 items-center gap-2 border border-neutral-300 bg-neutral-100 px-3 text-body text-neutral-500"
      aria-disabled="true"
      data-photo-picker="held"
    >
      <span aria-hidden="true">{"\u{1F4F7}"}</span>
      <span>{props.reason}</span>
    </div>
  );
}

/**
 * The one commit control a guest form uses — **the `SaveBar` pattern, not a new
 * one.** `WorkingButton` is the staff kit's commit (single-flight, A18 §3
 * working state) and carries no `disabled`; a form with a field still empty
 * therefore renders the SAME tier disabled with its reason on `title`, exactly
 * as `settingsShared.SaveBar` does for a read-only Settings screen
 * (`BR-SHL-025`: disabled WITH the reason, never a vanished control).
 *
 * ⚠ **PRIMARY BY DEFAULT, BECAUSE MOST GUEST COMMITS ARE NOT DESTRUCTIVE.**
 * r10 rule 6 reserves the danger tier for a destructive commit — disconnect,
 * retire, reverse, write-off. Reporting a burst main and looking up a
 * reference are neither.
 *
 * ⚠ **AND `tier` EXISTS BECAUSE ONE OF THEM IS, AND COULD NOT SAY SO
 * (`CR-085` task (c), found by reading the DOM).** `08-screen-layouts.md`
 * `CWP-052` draws *Request this ✓* as **`Button(danger)`** and calls it *"second
 * danger-tier commit"*; `StopOrRestart.tsx`'s own docstring has said **"THE
 * COMMIT IS THE DANGER TIER AND IT IS EARNED"** since the day it was written —
 * and this component hard-coded primary, so asking a utility to turn a
 * household's water off committed through a button styled identically to
 * *Save*. Measured in a real browser 2026-09-08: `data-variant="primary"`.
 * That is hard-won law 1 exactly — a comment claiming a guarantee is not the
 * guarantee — and it is the same shape, and the same cure, as `DEF-712` one
 * layer down: `WorkingButton` gained an optional `variant` for precisely this
 * and this wrapper never passed it on.
 *
 * It is OPTIONAL and absent means `primary`, so every existing call site
 * renders exactly as before; only a screen that DECLARES its commit
 * destructive changes tier.
 */
/**
 * A commit that may not be pressed yet, WITH ITS REASON AS TEXT.
 *
 * ⚠ **F-22 (`DEF-CWP-10551`): THE REASON WAS ON `title=` AND NOWHERE ELSE** —
 * on `CommitButton` and on five hand-built buttons (Report, Track, Set up your
 * login, Ask for a plan, choose a new password). A tooltip needs a mouse and a
 * second of hover, and on a phone it does not exist. `DEF-CWP-4866` wrapped it
 * per screen (`HeldCommit`) and wrote *"the fix belongs in the kit"*; this is
 * that fix. The sentence is drawn under the button exactly as `HeldButton`
 * draws it, and the button points at it with `aria-describedby`. `title`
 * stays, for the mouse.
 */
export function DisabledCommit(props: {
  label: ReactNode;
  reason: string;
  tier?: CommitTier;
  /** Kept for the screens whose tests select the button by it. */
  testKey?: string;
}) {
  const reasonId = `commit-${useId()}`;
  const saying = props.reason !== "";
  return (
    <span className="inline-flex flex-col items-start gap-1" data-commit-held="">
      <Button
        variant={props.tier ?? "primary"}
        disabled
        title={saying ? props.reason : undefined}
        aria-describedby={saying ? reasonId : undefined}
        data-action={props.testKey}
      >
        {props.label}
      </Button>
      {saying ? (
        <span id={reasonId} className="text-base text-neutral-600" data-commit-reason="">
          {props.reason}
        </span>
      ) : null}
    </span>
  );
}

/**
 * The reason line for a hand-built control that is disabled SOMETIMES (F-22).
 * The control names it with `aria-describedby={id}` while it is drawn; it is
 * drawn only while there is a reason. Same words and classes as
 * `DisabledCommit`'s, so the two cannot look different.
 */
export function ButtonReason(props: { id: string; reason: string | null | undefined }) {
  if (!props.reason) return null;
  return (
    <span id={props.id} className="text-base text-neutral-600" data-commit-reason="">
      {props.reason}
    </span>
  );
}

export function CommitButton(props: {
  label: string;
  working: boolean;
  ready: boolean;
  reason: string;
  tier?: CommitTier;
  onClick: () => void;
}) {
  const tier = props.tier ?? "primary";
  if (!props.ready) {
    return <DisabledCommit label={props.label} reason={props.reason} tier={tier} />;
  }
  return (
    <WorkingButton working={props.working} variant={tier} onClick={props.onClick}>
      {props.label}
    </WorkingButton>
  );
}

/**
 * A path inside THIS utility's portal — `/pine-hill/portal/report`.
 *
 * ⚠ **THE TENANT IS READ OFF THE ADDRESS THE BROWSER IS ON, NEVER TYPED**
 * (`BR-CWP-005` · `BR-CWP-007`). A relative `<Link to="report">` would work
 * until the day a screen is rendered from a route that is not `/:tenant/portal`
 * — and then it would silently point somewhere else.
 */
export function usePortalPath(): (to: string) => string {
  const { tenant } = useParams();
  return (to: string) => `/${tenant ?? ""}/portal${to === "/" ? "" : to}`;
}

/** `Verb →` on an errand card whose screen EXISTS (r10 rule 4). Same tier and
 *  size as the held one beside it, so a live card and a held card differ only
 *  in whether they can be pressed — which is why `size` is here at all, taking
 *  the same two values `HeldButton` takes and the same default: the front
 *  page's sign-in bar draws its control at `default`, and a link that could
 *  only be `sm` would have made the live version a different shape from the
 *  held one it replaces. */
export function ErrandLink(props: {
  label: string;
  to: string;
  size?: "default" | "sm";
  /**
   * ⚠ **`primary` EXISTS FOR EXACTLY ONE CONTROL ON THE WHOLE GUEST SURFACE**
   * — *Pay a bill* on `CWP-001`. The wireframe's own note is the rule: *"One
   * filled button, and it is not 'Sign in' — most visits are a payment, and
   * most of those people have no account and do not want one."* Before this
   * prop the front page drew SIX identical outlined controls and a seventh in
   * the sign-in bar, so a stranger arriving with a paper bill met no visual
   * primary action at all.
   *
   * ⚠ **DEFAULT `secondary`, SO NO EXISTING CALL SITE MOVES A PIXEL** — and
   * the default is what keeps a live card and the `HeldButton` beside it the
   * same shape, which is the reason `size` is on this component at all.
   * Adding a second filled control anywhere on a guest screen breaks r10's
   * *exactly one primary per screen*; if you are reaching for this prop, check
   * first that nothing else on the screen already has it.
   */
  variant?: "primary" | "secondary";
}) {
  const path = usePortalPath();
  const actionName = useErrandActionName(props.label);
  return (
    <ButtonLink
      variant={props.variant ?? "secondary"}
      size={props.size ?? "sm"}
      to={path(props.to)}
      aria-label={actionName}
    >
      {props.label}
    </ButtonLink>
  );
}

/**
 * `WhereNext` — the row of doors at the foot of a panel.
 *
 * ⚠ **THIS EXISTS BECAUSE 26 OF THE PORTAL'S 50 SCREENS HAD NO DOOR INTO THEM**
 * (`DEF-CWP-3954`). Every one of them was shipped, routed, tested and answering
 * correctly at its own address; a customer simply could not get there. The
 * arithmetic that found it was a browser CRAWL — follow anchors only, never
 * type an address — and it stood at **twelve destinations** for a signed-in
 * customer. On the bills list the only control was a greyed *Pay* and the bill
 * numbers were bold text, so a person could see their bills and could not open
 * one.
 *
 * ⚠ **IT IS A KIT COMPONENT AND NOT A `<div>` EACH SCREEN DRAWS** (B14 rule
 * 36). Six screens needed the same block, and `Usage.tsx` had already
 * hand-rolled the first one — a wrapper with its own margin, its own gap and
 * its own mark. Six spellings of *here is where you can go from here* is the
 * four-different-chips failure the rule exists to stop, so the seventh is the
 * kit's and `Usage.tsx` now composes it too.
 *
 * ⚠ **EVERY DOOR CARRIES `data-door` WITH ITS ADDRESS.** A crawl reads
 * `href`, which is enough; a TEST that wants to say *this screen opens
 * `/pay-now`* needs a handle that does not depend on the tenant in the path,
 * and `G100` reads the SOURCE. Three readers, one fact.
 *
 * ⚠ **NO HEADING, AND THAT IS RULE 32 RATHER THAN AN OMISSION.** A door
 * names its own destination — `Your payment methods`, `Documents and
 * letters` — so a line of copy above it would say the same thing twice, and
 * the screen has a description budget. It is the rule under a horizontal
 * line inside the panel it belongs to, which is the shape `MyDetails.tsx`
 * already chose for the one door it had.
 *
 * ⚠ **EVERY LABEL BELOW IS A KEY THE ELEVEN CATALOGUES ALREADY HOLD** —
 * usually the destination screen's OWN title. Naming a door after the
 * screen it opens means a customer reads the same words on the button and
 * on the page, and it minted not one new string in eleven languages.
 *
 * ⚠ **A DOOR IS A LINK, NEVER A HELD BUTTON.** `HeldButton` is for a control
 * whose SCREEN does not exist yet (`CR-068` R3); the day it lands, the hold
 * stops being true and nothing in this repo asks (hard-won law 2's mirror,
 * `DEF-CWP-3925`). Anything in this list is a screen that answers today.
 */
export function WhereNext(props: {
  mark: string;
  doors: readonly { key: string; label: string; to: string }[];
}) {
  if (props.doors.length === 0) return null;
  return (
    <div
      className="mt-4 flex flex-wrap gap-2 border-t border-neutral-200 pt-3"
      data-where-next={props.mark}
    >
      {props.doors.map((door) => (
        <span key={door.key} className="inline-flex" data-door={door.to}>
          <ErrandLink label={door.label} to={door.to} />
        </span>
      ))}
    </div>
  );
}

/**
 * `NamedGaps` — the short grey list under a figure, saying what the figure does
 * NOT include. One line per gap, in the customer's own words.
 *
 * ⚠ **IT EXISTS BECAUSE THE TWO SCREENS THAT DREW THIS LIST WERE PRINTING THE
 * SERVER'S ENGINEERING PROSE STRAIGHT ONTO A CUSTOMER'S HOME PAGE
 * (`DEF-CWP-3926`).** Both wrote `t(key, { defaultValue: problem.detail })`,
 * no key existed for any code, and `detail` is a sentence addressed to a
 * developer. What a customer actually read on `CWP-022` was:
 *
 *     apps.billing.selectors.issued_invoices_for_account is not published, so
 *     no bill states its usage+base / taxes / tenant-defined / fees balances …
 *     (OQ-128, `minimum_adjustment` belongs to no named class) and the tenant's
 *     own definition of the fourth class in the ledger (BR-PAY-038, PO
 *     2026-08-11).
 *
 * **A fallback to the server's words is never right here**, however tempting:
 * `problems[]` is a diagnostic channel that grows a code whenever a module
 * finds a gap, so the fallback is a standing promise that the NEXT code
 * somebody adds — in any module, on any money path — appears on a customer's
 * screen in English, with its rule ids. B14 rules 31 and 32 forbid an internal
 * code in CLERK-facing copy; this is stricter, and `BR-CWP-021` says a visitor
 * sees no internals at all.
 *
 * **So a gap with no sentence renders NOTHING.** Not the key, not the detail,
 * not a placeholder: the figure above it is still honest, and the customer is
 * no worse off than before the code existed. Writing the sentence is what makes
 * a gap appear — which puts the work in the right place.
 */
export function NamedGaps(props: { problems: readonly { code: string }[]; mark: string }) {
  const { t } = useTranslation();
  //: ⚠ **DE-DUPLICATED BY CODE (`DEF-CWP-4132`).** `problems[]` arrives
  //: concatenated across the account set, so a landlord holding three accounts
  //: was handed the same code three times and read the identical sentence three
  //: times in a row under one figure — and React was handed three children with
  //: the same key. **A gap is a fact about the FIGURE, not about each account
  //: behind it**, so it is said ONCE however many accounts stand behind it.
  //: Every unit test passes one account, which is why nothing saw it: the
  //: component was correct for its own contract and so was the server, and the
  //: defect lived in the seam between them.
  const seen = new Set<string>();
  const lines = props.problems
    .map((problem) => ({ code: problem.code, text: t(`portal.problem.${problem.code}`, { defaultValue: "" }) }))
    .filter((one) => one.text !== "")
    .filter((one) => {
      if (seen.has(one.code)) return false;
      seen.add(one.code);
      return true;
    });
  if (lines.length === 0) {
    return null;
  }
  return (
    <ul className="mt-3 flex flex-col gap-1" {...{ [props.mark]: "" }}>
      {lines.map((one) => (
        <li key={one.code} className="text-base text-neutral-600">
          {one.text}
        </li>
      ))}
    </ul>
  );
}

/** A plain word in the guest frame's nav bar. */
export function NavLinkWord(props: { label: string; to: string; name: string }) {
  const path = usePortalPath();
  return (
    <Link
      to={path(props.to)}
      data-link={props.name}
      className="text-neutral-900 no-underline hover:underline"
    >
      {props.label}
    </Link>
  );
}

/**
 * The same word, on a `<button>` that ACTS instead of navigating —
 * `NavLinkWord`'s sibling, and a separate export for the reason
 * `components/Surfaces.tsx` splits `InlineLink` from `InlineLinkTo`: a
 * `<Link>` needs `to`, a `<button>` needs `onClick`, and one component taking
 * both takes neither properly.
 *
 * ⚠ **IT IS IN THE KIT AND NOT IN THE SHELL BECAUSE THE SHELL IS THE SECOND
 * PLACE THAT WOULD HAVE DRAWN IT** (B14 rule 36, and this file's own rule:
 * *if a screen needs something not here, add it here first*). The header's
 * live words — *Messages*, *Help* — are `NavLink`s wearing exactly this look;
 * a `<button>` drawn beside them with its own classes is how a five-item row
 * ends up with three visual treatments.
 *
 * ⚠ **THE PADDING AND THE BORDER ARE ZEROED ON PURPOSE.** A `<button>` in a
 * screen file that sets padding, a border AND a colour is a hand-rolled box,
 * which `G86` clause (b) refuses and `Button` already owns. This is a WORD,
 * so it draws no box — and `font-body text-body` are explicit because a
 * `<button>` does not inherit the row's type the way an `<a>` does.
 */
export function NavActionWord(props: {
  label: string;
  name: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      data-action={props.name}
      onClick={props.onClick}
      disabled={props.disabled === true}
      className="cursor-pointer border-none bg-transparent p-0 font-body text-body text-neutral-900 no-underline hover:underline"
    >
      {props.label}
    </button>
  );
}


/* ═══════════════════════════════════════════════════════════════════════════
 * CR-068 wave H — THE USAGE CHART, ADDED TO THE KIT (B14 rule 36)
 * ═══════════════════════════════════════════════════════════════════════════
 *
 * ⚠ **`Home.tsx` ASKED FOR THIS BY NAME AND ITS SENTENCE IS NOW SPENT.** It
 * said the twelve-month data came down with the page and *"what is missing is
 * a chart in the shared kit, and B14 rule 36's mechanism is where the kit
 * lacks a piece, ADD IT TO THE KIT rather than hand-roll one here — which is
 * how four screens end up with four different charts"*. `CWP-033` is the
 * second screen that needs it, so it is here rather than in the screen.
 *
 * ⚠ **ONE SERIES PER CHART, AND THAT IS HARD RULE 3 RATHER THAN A STYLE
 * CHOICE.** Gallons and therms share a month and nothing else, so there is no
 * multi-series form here to reach for and no categorical palette to validate —
 * a single series needs no legend and the TITLE names it. Two services are two
 * charts, side by side, exactly as the staff Usage tab draws them.
 *
 * ⚠ **AN ABSENT MONTH IS AN EMPTY SLOT, NEVER A ZERO BAR** (`BR-MET-106`).
 * *"Zero usage and no read are different claims about a customer"*, and a
 * zero-height bar is the claim we are forbidden to make.
 *
 * ⚠ **AN ESTIMATED MONTH IS MARKED BY TEXTURE AND NOT BY COLOUR ALONE.** It
 * keeps the same fill and gains a dashed outline plus its own word in the
 * tooltip, so a reader who cannot separate two hues still sees the mark.
 */

/**
 * `"2026-08"` -> the month name, short, in the reader's own language.
 *
 * ⚠ **`Intl`, NEVER A LIST OF TWELVE STRINGS IN ELEVEN CATALOGUES** (B14 rule
 * 35). `content.tsx` states the same reason for the clock and the weekday: a
 * catalogue holding *Jan Feb Mar* is a word-for-word translation of an English
 * list, and every one of the eleven would have to be maintained by hand.
 *
 * ⚠ **THE DAY IS 1 AND THAT MATTERS.** `new Date("2026-08")` parses as UTC
 * midnight and shifts a month backwards west of Greenwich; the parts are split
 * and handed to the local-time constructor instead, which is what
 * `dayMonthText` does one file over for the same reason.
 */
export function shortMonthText(month: string, language: string): string {
  const [year, index] = month.split("-").map((part) => Number(part));
  if (!year || !index) return month;
  return new Intl.DateTimeFormat(language, { month: "short" }).format(
    new Date(year, index - 1, 1),
  );
}

/**
 * `"2026-08"` or `"2026-08-02"` -> *Aug 2026* / *August 2026*, in the reader's
 * own language.
 *
 * ⚠ **`Intl`, NEVER A CATALOGUE STRING** — `shortMonthText` above states the
 * reason and this is the same argument one word longer: twelve month names in
 * eleven catalogues is a word-for-word translation of an English list (B14
 * rule 35), and the year's PLACE in the phrase differs by language, which is
 * exactly what `Intl` already knows and a `{{month}} {{year}}` template does
 * not.
 *
 * ⚠ **IT TAKES A DATE AND USES ONLY THE FIRST TWO PARTS**, so an issue date
 * (`2026-08-02`) and a usage month (`2026-08`) both answer *Aug 2026*. The day
 * is forced to 1 for `shortMonthText`'s reason: `new Date("2026-08")` parses as
 * UTC midnight and slides a month backwards west of Greenwich.
 *
 * ⚠ **AN UNPARSEABLE VALUE COMES BACK UNCHANGED, NEVER AS `Invalid Date`.**
 */
export function monthYearText(
  date: string | null | undefined,
  language: string,
  month: "short" | "long" = "short",
): string {
  if (date === null || date === undefined || date === "") return "";
  const [year, index] = date.split("-").map((part) => Number(part));
  if (!year || !index || index < 1 || index > 12) return date;
  return new Intl.DateTimeFormat(language, { month, year: "numeric" }).format(
    new Date(year, index - 1, 1),
  );
}

export interface UsageBar {
  /** `2026-08` — the month, as the server states it. */
  month: string;
  /** The stored figure, or `null` when the month is ABSENT (never `0`). */
  quantity: string | null;
  /** Two decimals, trailing zeros trimmed — composed by the server. */
  quantityDisplay: string | null;
  /** `BR-MET-106` — the month has no read at all. */
  absent: boolean;
  /** `BR-MET-106` — part of it was estimated, and the customer may know. */
  estimated: boolean;
}

/**
 * A twelve- or twenty-four-bar column chart for ONE service.
 *
 * `unit` is not optional and there is no path that drops it (hard rule 3): it
 * labels the axis, which is `US-CWP-040` TC-2's own requirement — *the axis
 * labelled in gallons*.
 *
 * `lowestLabel` / `highestLabel` are the already-composed sentences for the two
 * marked months; the caller writes them from its catalogue rather than this
 * component assembling English (B14 rule 35).
 */
export function UsageBars(props: {
  bars: UsageBar[];
  unit: string;
  caption: string;
  axisLabel: string;
  /** The legend's words (`CWP-033` 33.3). Absent draws no legend at all —
   *  a swatch with no word beside it explains nothing.
   *
   *  ⚠ **`lowestLabel` / `highestLabel` USED TO BE HERE AND ARE NOT ANY MORE
   *  (CR-085 group H).** The drawing puts the lowest and the highest month in
   *  the SUMMARY TILES above the chart, each with the month it happened in —
   *  *Lowest · Feb 412 kWh* — and the server has always served that month
   *  (`metrics.low.month`). A footnote under the axis repeating the same two
   *  figures without their months was the same fact written twice and worse
   *  the second time. */
  legendMeasured?: string | null;
  legendHighest?: string | null;
  /** `BR-MET-106` — the drawing's own state: *"Estimated months: marked on the
   *  chart with a legend, so the customer knows which bars are measured."* The
   *  bars have carried the dashed outline since the chart was written and
   *  nothing named it, which is hard-won law 1 in pixels. Drawn ONLY when a
   *  bar in this window is actually estimated: a legend entry for a mark that
   *  is not on the chart explains a distinction there is nothing to see. */
  legendEstimated?: string | null;
  emptyLabel: string;
  barTitle: (bar: UsageBar) => string;
  testId?: string;
}) {
  const { i18n } = useTranslation();
  const present = props.bars.filter((bar) => !bar.absent && bar.quantity !== null);
  if (present.length === 0) {
    // B14 rule 17 / BR-CWP-093 — a sentence that says what will fill it, never
    // an axis with nothing on it.
    return (
      <p className="mt-2 text-body text-neutral-600" data-chart-empty={props.testId ?? ""}>
        {props.emptyLabel}
      </p>
    );
  }
  const values = present.map((bar) => Number(bar.quantity));
  const peak = Math.max(...values);
  const lowest = Math.min(...values);

  return (
    <figure className="m-0" data-chart={props.testId ?? ""}>
      {/* The unit rides in the axis label because it is the WHOLE chart's
          unit — hard rule 3, on screen and not only in the payload. */}
      <div className="mb-1 text-base font-semibold text-neutral-700" data-chart-axis="">
        {props.axisLabel}
      </div>
      <div
        className="flex h-[180px] items-end gap-[2px] border-b border-neutral-300 py-2"
        role="img"
        aria-label={props.caption}
      >
        {props.bars.map((bar) => {
          if (bar.absent || bar.quantity === null) {
            return (
              <div
                key={bar.month}
                className="h-full flex-1 self-stretch"
                data-month={bar.month}
                data-absent="true"
                title={props.barTitle(bar)}
              />
            );
          }
          const value = Number(bar.quantity);
          // A 3% floor so a very small month reads as a mark rather than
          // disappearing into the axis and looking like an absence.
          const height = peak > 0 ? Math.max(3, (value / peak) * 100) : 3;
          const extreme =
            value === peak ? "highest" : value === lowest ? "lowest" : undefined;
          return (
            <div
              key={bar.month}
              // ⚠ **THE HIGHEST MONTH IS A DARKER TIER AND NOT ONLY A DATA
              // ATTRIBUTE.** `data-extreme` has marked it since this component
              // was written and nothing rendered the mark, so `CWP-033`'s
              // legend entry *Highest month* would have described a
              // distinction no reader could see — a comment claiming a
              // guarantee, in pixels (hard-won law 1). `bg-accent-700` is the
              // theme's own darkest accent step, the one `buttonKit` already
              // uses for `active:`.
              className={`flex-1 self-end rounded-t-[4px] ${
                value === peak ? "bg-accent-700" : "bg-accent"
              }`}
              data-month={bar.month}
              data-absent="false"
              data-estimated={bar.estimated ? "true" : "false"}
              data-extreme={extreme}
              title={props.barTitle(bar)}
              style={{
                height: `${height}%`,
                // The estimate is MARKED, and by texture rather than by hue
                // alone — a reader who cannot separate two colours still sees
                // the dashes.
                opacity: bar.estimated ? 0.6 : 1,
                outline: bar.estimated ? "1px dashed var(--color-accent)" : undefined,
                outlineOffset: bar.estimated ? "-1px" : undefined,
              }}
            />
          );
        })}
      </div>
      {/* ⚠ **MONTH NAMES UNDER THE BARS — `CWP-033` 33.2, and they were absent
          entirely.** The chart drew twelve bars a customer could not date.
          They are produced by `Intl` in the reader's own language rather than
          assembled from an English list (B14 rule 35, the reason
          `content.tsx`'s clock exists), and they sit in the SAME flex tracks
          as the bars so a label cannot drift off its column. */}
      <div className="mt-1 flex gap-[2px]" data-chart-months={props.testId ?? ""}>
        {props.bars.map((bar) => (
          <span
            key={bar.month}
            className="min-w-0 flex-1 truncate text-center text-base text-neutral-600"
            data-month-label={bar.month}
          >
            {shortMonthText(bar.month, i18n.language)}
          </span>
        ))}
      </div>
      <figcaption className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-base text-neutral-600">
        {props.legendMeasured ? (
          <span className="inline-flex items-center gap-1.5" data-chart-legend="measured">
            <span className="inline-block h-2.5 w-2.5 bg-accent" aria-hidden="true" />
            {props.legendMeasured}
          </span>
        ) : null}
        {props.legendHighest ? (
          <span className="inline-flex items-center gap-1.5" data-chart-legend="highest">
            <span className="inline-block h-2.5 w-2.5 bg-accent-700" aria-hidden="true" />
            {props.legendHighest}
          </span>
        ) : null}
        {props.legendEstimated && present.some((bar) => bar.estimated) ? (
          <span className="inline-flex items-center gap-1.5" data-chart-legend="estimated">
            <span
              className="inline-block h-2.5 w-2.5 border border-dashed border-accent opacity-60"
              aria-hidden="true"
            />
            {props.legendEstimated}
          </span>
        ) : null}
      </figcaption>
    </figure>
  );
}

/**
 * The segmented pair `CWP-033`'s head draws — *12 months* | *24 months*, and
 * the `On` / `Off` pairs `CWP-025` draws over its contact grid.
 *
 * ⚠ **IT DREW ITS LABEL NOWHERE AND ITS CHOSEN OPTION IN THE BRAND TIER, AND
 * BOTH ARE FIXED HERE (`DEF-CWP-3996`, `DEF-CWP-3997`; `14-layout-audit.md`
 * row D4).** `props.label` went to `aria-label` on the wrapper and nothing was
 * drawn, so `CWP-025` shipped **four bare `On`/`Off` buttons floating above a
 * table with nothing saying which pair was email and which was text** — the
 * fault the Product Owner reported. The chosen option rendered
 * `variant="primary"`, a solid brand fill, which B14 rule 6 reserves for
 * destructive commits: a red `Off` block reads as an error, not as a state.
 *
 * ⚠ **THE FIRST HALF IS THE ONE THAT WILL FOOL A CHECKER, WHICH IS WHY THE
 * TEST FOR IT IS WRITTEN AS IT IS.** An `aria-label` IS an accessible name, so
 * `getByRole("group", { name: … })` and every axe rule passed on the broken
 * control — a test asserting *this control is labelled* was green over a
 * control no sighted person could read. `SegmentedChoice.dom.test.tsx` asserts
 * a **visible text node** instead, and was proved red on the old component
 * (5 of its 6 cases) before this was written.
 *
 * ⚠ **AND IT IS THE KIT'S CONTROL NOW, NOT TWO BUTTONS (B14 rule 36).** Rule
 * 36's breach (c) names this exact shape — *"category chips and segmented
 * controls were hand-rolled as raw `<button>` elements while `Button`,
 * `buttonKit`, `FilterBar` and `SegmentedControl` all exist in the kit"*.
 * `components/SegmentedControl.tsx` is a joined strip with a measured
 * chosen-state fill and a real `radiogroup`; two `Button`s side by side were a
 * second segmented control with a colour nobody had checked. The old note here
 * explained why it was not the stylesheet's `.seg-opt` — true, and it was
 * never the choice between those two.
 *
 * `purpose="choice"` and not the default `view`: every one of the three uses
 * picks a VALUE (on/off, twelve months, owing only) rather than switching
 * which panel is shown, so the control is a radiogroup and each option
 * announces itself checked or not.
 */
export function SegmentedChoice(props: {
  label: string;
  options: { key: string; label: string }[];
  current: string;
  onChoose: (key: string) => void;
  testId?: string;
}) {
  // `useId` and not the testId: the testId is optional, and two controls with
  // the same one on a screen would point both labels at a single element.
  const labelId = `seg-${useId()}`;
  // F-04 (`DEF-CWP-10552`): the choice keeps focus (a radio) and the change is
  // said — *"Twelve months"* — because the page under it re-draws silently.
  const say = useAnnounce();
  return (
    <div className="flex flex-col gap-1">
      <span id={labelId} className="text-xs font-bold uppercase tracking-wide text-neutral-600">
        {props.label}
      </span>
      <SegmentedControl
        segments={props.options.map((option) => ({ id: option.key, label: option.label }))}
        active={props.current}
        onSelect={(key) => {
          props.onChoose(key);
          const chosen = props.options.find((option) => option.key === key);
          if (chosen !== undefined && key !== props.current) say.polite(chosen.label);
        }}
        label={props.label}
        labelledBy={labelId}
        purpose="choice"
        name={props.testId ?? ""}
      />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
 * CR-068 wave H — the one piece the kit still lacked.
 *
 * ⚠ **`TotalRow` IS NOT HERE, AND THAT IS THE INTERESTING HALF.** This lane
 * wrote one, and so did the wave-H lane building `CWP-032` and `CWP-044`, in
 * the same hour — two components, one name, both correct, exactly the shape
 * `DEF-CWP-3655` records for `Panel`. Theirs landed first, so this lane deleted
 * its own and **widened theirs by one optional prop** (`signed`) instead. That
 * is B14 rule 36's own mechanism: *"one component, one visual decision, every
 * screen"*, and it is the same move `ChipTone` records for `danger` — a union
 * widened by one name rather than a fifth chip nobody had checked.
 * ═══════════════════════════════════════════════════════════════════════════ */

/**
 * A quantity for a person — `2,000 gal`, `1 cart`, `4,820 gal`.
 *
 * The server already refuses to SERVE a quantity with no unit, so the `null`
 * below is the second of two guards on one rule — and the one that survives a
 * later lane rewriting the screen.
 *
 * ⚠ **THE NUMBER IS THE KIT'S NOW AND THIS FUNCTION ONLY ADDS THE UNIT**
 * (`DEF-CWP-4003`, B14 rule 36 · hard-won law 5). It used to group the digits
 * itself, in six lines, on a stated assumption — *"the number itself arrives
 * already rounded to `BR-MET-144`'s two places by the server, so nothing here
 * rounds anything"*. That is true of a bill line's `quantity` and **false of
 * `yoy.this_year_total`**, which the wire sends as the stored
 * `NUMERIC(18,6)`: `CWP-033`'s year card would have read `48,120.000000 gal`.
 *
 * `components/UnitCell.tsx` has held the ruled version the whole time —
 * `BR-MET-144`'s two places, half-up on the decimal STRING so a carry never
 * becomes a `Number`, trailing zeros stripped because `8.000000` and `8` are
 * the same number to the last bit (`DEF-646`, the Product Owner's own words:
 * *"meter reads are whole numbers - youa re shoiwing 4 decimal"*). Two
 * implementations of one rule under one NAME is how `TwoCol` and `Panel`
 * drifted; this deletes the second rather than teaching it to round.
 *
 * ⚠ **NO EXISTING CALLER MOVES A PIXEL**, and that is checked rather than
 * assumed: the one other consumer is `CWP-028`'s bill line, whose quantities
 * are already trimmed (`2000`, `4820`, `1`), and grouping-only input has no
 * trailing zeros and no third decimal for the new step to touch.
 *
 * ⚠ **IT RETURNS `null` WHEN THE UNIT IS MISSING, AND THAT IS CLAUDE.md HARD
 * RULE 3 HELD ON THE LAST STEP** — kept exactly. A bare `4,820` in a column
 * headed *Quantity* is read as whatever unit the reader assumes.
 */
/**
 * **The number on the dial**, grouped — `153,040`, not `153040`.
 *
 * ⚠ **WHY THIS IS NOT `formatQuantity`, AND WHY HARD RULE 3 IS NOT ENGAGED.**
 * Hard rule 3 says a CONSUMPTION always carries an explicit unit, and
 * `formatQuantity` enforces it by refusing to render a bare number. A dial
 * figure is not a consumption: it is the running index printed on the face of
 * the box, and the column beside it — *Used since* — is the consumption and
 * keeps its unit. Putting `gal` after a register reading would state that the
 * meter has measured 153,040 gallons since it was made, which is a different
 * and usually false claim.
 *
 * ⚠ **AND WHY IT GROUPS HERE RATHER THAN ON THE SERVER.** The wire value comes
 * from `apps/metering/quantity_display.quantity_text`, which returns a bare
 * string deliberately and is shared with the staff screens; grouping there
 * would change what a clerk sees and what a CSV export contains. Grouping is a
 * LOCALE decision and the locale is the browser's. `13-wireframe-delta.md` X2
 * names this exact figure as the one that matters most — it is the number a
 * customer checks against the box on their wall, and `6462` is materially
 * harder to check than `6,462`.
 *
 * `null` in, `null` out: an absent reading is absent, and the caller draws the
 * dash (`BR-MET-106` — an unread month is ABSENT, never a zero).
 */
export function formatDialFigure(value: string | null): string | null {
  if (value === null || value === "") return null;
  return formatQuantityNumber(String(value));
}

export function formatQuantity(quantity: string | null, unit: string | null): string | null {
  if (quantity === null || unit === null || unit === "") return null;
  return `${formatQuantityNumber(String(quantity))} ${unit}`;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * CR-068 wave G · `CWP-025` — three pieces the kit lacked, ADDED HERE rather
 * than hand-rolled in the screen (B14 rule 36, verbatim: *"where the kit lacks
 * a piece, ADD IT TO THE KIT rather than hand-rolling it in the screen, which
 * is how four screens acquire four different chips"*).
 * ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Two panels of equal width — `08-screen-layouts.md`'s **T4**.
 *
 * ⚠ **`TwoCol` IS 62/35 AND IS NOT THIS.** Three screens already write
 * `grid-cols-2 … max-md:grid-cols-1` by hand (`CWP-018`'s 50/50 among them), which
 * is the drift this component exists to stop: T4 is a named template in the
 * layout document and there should be one place that knows what it is.
 */
export function TwoEqual(props: { left: ReactNode; right: ReactNode }) {
  return (
    // ⚠ **`flex flex-col gap-4` ON BOTH COLUMNS, ADDED 2026-09-05
    // (`DEF-CWP-4016`) — THIS COMPONENT HAD `TwoCol`'s BUG AND NO CALLER HAD
    // TRIPPED IT YET.** `DEF-CWP-3984` fixed exactly this one component along:
    // a column with no spacing rule draws two `Card`s FLUSH AGAINST EACH
    // OTHER, and `Card` carries no margin of its own. `TwoEqual`'s only
    // caller (`CWP-025`) passes a single `Panel` each side, where this
    // changes nothing — so the bug was latent, and it would have gone live
    // the moment a screen with a two-card column moved here. `CWP-024`'s
    // right-hand column is exactly that screen, and it moves here in the same
    // commit.
    <div className="grid grid-cols-2 gap-4 max-md:grid-cols-1" data-two-equal="">
      <div className="flex flex-col gap-4" data-two-equal-left="">
        {props.left}
      </div>
      <div className="flex flex-col gap-4" data-two-equal-right="">
        {props.right}
      </div>
    </div>
  );
}

/**
 * The one dropdown shape the portal uses — `FormField.Select` in the layout
 * document's vocabulary.
 *
 * ⚠ **IT MATCHES `TextInput` DECLARATION FOR DECLARATION**, because a picker
 * that is a different height and a different border from the box above it is
 * the second input shape in a kit whose whole point is that there is one. The
 * staff app's two `<select>`s are inside `DataTable`'s pager and
 * `ChipMultiSelect`, both stylesheet-classed and neither reusable here (B14
 * rule 21 — `portal/` is on `route-b-migrated.txt` and adds no class).
 */
export function SelectInput(props: {
  id: string;
  value: string;
  /**
   * `lang` marks an option written in another language — a language's own
   * name, `Español` on an English page (`DEF-CWP-10561`, WCAG 3.1.2).
   */
  options: readonly { value: string; label: string; lang?: string }[];
  onChange: (value: string) => void;
  placeholder?: string;
  /**
   * The name, where no `<label for>` names the box — a chooser drawn inside a
   * line of text rather than under a field label (`DEF-CWP-10564`, Home's bill
   * month).
   */
  ariaLabel?: string;
  /** `DEF-CWP-9215` — see `TextInput`. */
  invalid?: boolean;
  describedBy?: string;
  required?: boolean;
  /** Leaving the box — a portal form saves on leave (`DEF-CWP-3705`). */
  onBlur?: () => void;
}) {
  const wired = useFieldWiring(props.id, props);
  return (
    <select
      id={props.id}
      data-select={props.id}
      aria-label={props.ariaLabel}
      {...wired}
      onBlur={props.onBlur}
      // ⚠ `bg-[white]` AND NOT `bg-white` — DEF-974, and this exact line was
      // caught by `src/styles/routeBUtilities.test.ts` before it shipped.
      // This theme CLEARS Tailwind's stock palette, so `bg-white` compiles
      // to nothing at all while tsc, eslint and every `toContain("bg-white")`
      // assertion pass — the class IS in the DOM and declares no rule. The
      // arbitrary-value form is what the rest of this kit already uses.
      className="border border-field-border bg-[white] px-3 py-2 text-body text-neutral-900"
      value={props.value}
      onChange={(event) => props.onChange(event.target.value)}
    >
      {/* ⚠ **THE EMPTY ROW IS EXPLICIT AND CARRIES ITS OWN WORDS** (wave R).
          A dropdown whose first row is a real value has already answered the
          question for the customer — on `CWP-054`'s *which bill* that would
          attach a query to a bill they never picked. Omit `placeholder` where a
          choice is genuinely pre-made, which is what `CWP-025` does. */}
      {props.placeholder !== undefined ? <option value="">{props.placeholder}</option> : null}
      {props.options.map((option) => (
        <option key={option.value} value={option.value} lang={option.lang}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

/** One cell of a `PreferenceGrid`: a fact, or a switch. */
export type PreferenceCell = "always" | "on" | "off" | "none";

/**
 * `CWP-025`'s grid — WHAT WE SEND × the channels, one row per document kind.
 *
 * ⚠ **AN `always` CELL RENDERS A CHIP AND NO CONTROL, AND THAT IS THE WHOLE
 * POINT OF THE COMPONENT** (`US-CWP-028` §2: *"the screen must show it honestly
 * rather than offering an off switch that quietly does nothing"*). Print is the
 * floor on every customer document (`BR-NOT-024`, PO 2026-08-30) — so the cell
 * is a STATEMENT, not a disabled toggle, because a greyed switch still reads as
 * *this could be turned off by somebody*.
 *
 * ⚠ **AND THE SWITCHABLE CELLS ARE DRIVEN FROM ONE VALUE PER COLUMN, NOT ONE
 * PER CELL.** This product holds no per-event customer preference
 * (`OQ-CWP-1660`); the caller passes a single `on`/`off` per switchable column
 * and the screen says so in a line above the table. A component that took a
 * per-cell callback would invite the next lane to wire forty-eight switches to
 * two columns — hard-won law 2 with better manners.
 */
export function PreferenceGrid(props: {
  caption: string;
  columns: { key: string; label: string }[];
  rows: { key: string; label: string; cells: Record<string, PreferenceCell> }[];
  alwaysLabel: string;
  onLabel: string;
  offLabel: string;
  noneLabel: string;
}) {
  function cell(state: PreferenceCell) {
    if (state === "always") {
      return <StatusChip tone="neutral">{props.alwaysLabel}</StatusChip>;
    }
    if (state === "none") {
      return (
        <span className="text-neutral-600" aria-label={props.noneLabel}>
          —
        </span>
      );
    }
    return (
      <span className="text-body text-neutral-800">
        {state === "on" ? props.onLabel : props.offLabel}
      </span>
    );
  }
  return (
    <div className="overflow-x-auto" data-preference-grid="">
      <table className="w-full border-collapse text-body">
        <caption className="sr-only">{props.caption}</caption>
        <thead>
          <tr className="border-b border-neutral-300">
            <th scope="col" className="py-2 pr-3 text-left text-xs font-bold uppercase tracking-wide text-neutral-700">
              {props.caption}
            </th>
            {props.columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className="py-2 pr-3 text-left text-xs font-bold uppercase tracking-wide text-neutral-700"
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => (
            <tr key={row.key} className="border-b border-neutral-200" data-preference-row={row.key}>
              <th scope="row" className="py-2 pr-3 text-left font-bold text-neutral-900">
                {row.label}
              </th>
              {props.columns.map((column) => (
                <td
                  key={column.key}
                  className="py-2 pr-3"
                  data-cell={`${row.key}.${column.key}`}
                  data-state={row.cells[column.key] ?? "none"}
                >
                  {cell(row.cells[column.key] ?? "none")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * `ProtectionCard` — one hold on the supply, with its own lifetime.
 *
 * ⚠ **THE PIECE `CWP-064` GENUINELY LACKED, AND B14 RULE 36 SAYS WHAT TO DO
 * ABOUT THAT:** *"where the kit lacks a piece, ADD IT TO THE KIT — one
 * component, one visual decision, every screen — rather than hand-rolling it in
 * the screen, which is how four screens acquire four different chips."*
 * `08-screen-layouts.md` draws THREE of these on one screen and `CWP-057`'s
 * rail wants the same shape for the hold it reports, so writing it inside a
 * screen would have been three or four of them a pixel and a type size apart.
 *
 * ⚠ **`ends` IS A `ReactNode` AND NOT A DATE, DELIBERATELY.** The three
 * lifetimes are three SHAPES: a certificate ends on a date, a payment-plan hold
 * ends on **no date at all** and says so in a sentence instead, and a
 * moratorium is a window with both ends. A `Date | null` prop here would push
 * every screen into inventing an em-dash for the middle one, which is precisely
 * the customer who believes a hold is permanent, stops paying, and is cut the
 * week it lapses (`BR-CWP-090`).
 *
 * ⚠ **`action` IS OPTIONAL BECAUSE ONE OF THE THREE HAS NO CONTROL.** Nobody
 * applies for a weather moratorium — the regulator sets the window — so the
 * card renders with no button rather than with a disabled one.
 */
export function ProtectionCard(props: {
  cardKey: string;
  title: string;
  chip: { tone: ChipTone; label: string };
  since?: string;
  endsLabel: string;
  ends: ReactNode;
  body: ReactNode;
  action?: ReactNode;
}) {
  return (
    <Panel as="section" title={props.title} data-protection={props.cardKey}>
      <div className="flex flex-wrap items-baseline gap-2">
        <StatusChip tone={props.chip.tone} testKey={`protection-${props.cardKey}`}>
          {props.chip.label}
        </StatusChip>
        {props.since !== undefined ? (
          <span className="text-base text-neutral-600" data-since={props.cardKey}>
            {props.since}
          </span>
        ) : null}
      </div>
      <KVList rows={[{ key: "ends", label: props.endsLabel, value: props.ends }]} />
      <p className="m-0 text-body leading-relaxed text-neutral-800" data-protection-body={props.cardKey}>
        {props.body}
      </p>
      {props.action !== undefined ? <div>{props.action}</div> : null}
    </Panel>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
 * `DEF-CWP-3965` — THE BALANCE STRIP, AND WHY IT IS IN THE KIT
 *
 * `CWP-022` opens with four tiles and `CWP-033` with three; `08-screen-layouts.md`
 * names a `KpiRow` on `CWP-066` as well. The portal kit had NONE of it, so the
 * home page drew its balance as a bordered card with a big number in it — which
 * is B14 rule 36's four-different-chips failure waiting to happen on three
 * screens at once. The rule's own mechanism says what to do: *"where the kit
 * lacks a piece, ADD IT TO THE KIT — one component, one visual decision, every
 * screen."*
 *
 * ⚠ **THE STAFF `KPIStrip` IS NOT WRAPPED, AND THAT IS A DECISION RATHER THAN
 * AN OVERSIGHT.** `StatusChip` wraps `StatusPill` because the shapes agreed.
 * These do not, in three ways, and each would have to be fought:
 *   · its MONEY tile REQUIRES a `BR-REP-001` date basis and prints it in the
 *     tile header — *as at posting date* is a reporting label a customer has
 *     no use for and would read as an error;
 *   · it has no `lead` variant, and the inventory names one for exactly two
 *     screens (the balance here, *you pay each month* on `CWP-066`);
 *   · it lays out `auto-fit minmax(180px,1fr)` from `KPIStrip.css`, where the
 *     portal's `KpiRow` is `grid-cols-{3|4}` in utilities — and `portal/` is on
 *     `route-b-migrated.txt` precisely so it adds no stylesheet class (rule 21).
 * ═══════════════════════════════════════════════════════════════════════════ */

/**
 * `KpiRow` — `09-component-inventory.md` §2: `grid grid-cols-{3|4} gap-4`.
 *
 * ⚠ **FOUR IS THE DEFAULT AND THREE IS A REAL VALUE**, because `CWP-033` and
 * `CWP-066` both draw three. Anything past the column count wraps onto a second
 * line rather than being dropped: a tile is a fact, and a screen that silently
 * stopped at four would hide a service a customer is billed for.
 *
 * ⚠ **`max-md:grid-cols-1` AND NOT `md:grid-cols-4`.** This theme's breakpoints
 * are MAX-width (`tailwind.css`: *"authoring reads `max-lg:grid-cols-1` — NEVER
 * `lg:grid-cols-2`"*), so the wide layout is the base rule and the phone is the
 * override.
 */
export function KpiRow(props: { columns?: 3 | 4; children: ReactNode }) {
  return (
    <div
      data-kpi-row=""
      className={`grid gap-4 max-md:grid-cols-1 ${
        props.columns === 3 ? "grid-cols-3" : "grid-cols-4"
      }`}
    >
      {props.children}
    </div>
  );
}

/**
 * `KpiTile` — kicker label · big figure · one grey sub-line.
 *
 * ⚠ **THE FIGURE IS `text-metric-lg` (32px) WHERE THE INVENTORY SAYS 34px, AND
 * THAT IS DELIBERATE — the same call `TotalRow` records one screen up.**
 * `tailwind.css` declares no 34px step and the metric tier is LOCKED at
 * 22 / 26 / 32 (`OQ-278` ruled, `OQ-279` re-ruled). Writing `text-[34px]` here
 * would put a fifth metric size in the product to satisfy a number nobody would
 * measure, and `G34` bans the literal. Same role, nearest ruled step, one scale.
 *
 * ⚠ **THE UNIT RIDES INSIDE THE FIGURE AND IS NEVER OPTIONAL WHERE THERE IS
 * ONE** (CLAUDE.md hard rule 3). `4,820` means nothing; `4,820 gal` is the whole
 * tile. It is a separate prop rather than part of `value` so the type sizes
 * cannot drift apart between screens.
 *
 * ⚠ **`lead` IS THE BRAND RULE DOWN THE LEFT EDGE, WRITTEN `border-l-accent`
 * AND NOT `border-l-[var(--brand)]`** (`DEF-CWP-3736`). The tenant's own colour
 * arrives as an override of `--color-accent` on the portal frame — `--brand` is
 * a variable this product sets nowhere and every rule that read it painted grey.
 */
export function KpiTile(props: {
  label: string;
  value: ReactNode;
  unit?: string | null;
  sub?: ReactNode;
  lead?: boolean;
  testKey: string;
}) {
  return (
    <div
      data-kpi={props.testKey}
      data-kpi-lead={props.lead ? "true" : undefined}
      className={`flex flex-col gap-1 border border-neutral-200 bg-[white] p-4 ${
        props.lead ? "border-l-4 border-l-accent" : ""
      }`}
    >
      <SectionTitle>{props.label}</SectionTitle>
      <p className="m-0 text-metric-lg font-bold tabular-nums text-neutral-900">
        <span data-kpi-value={props.testKey}>{props.value}</span>
        {props.unit ? (
          <span className="ml-1 text-body font-normal" data-kpi-unit={props.testKey}>
            {props.unit}
          </span>
        ) : null}
      </p>
      {/* B14 rule 32 — ONE sub-line, or none. A tile with two grey rows under
          the figure is the description budget spent on a number that is
          already legible. */}
      {props.sub !== undefined && props.sub !== null ? (
        <p className="m-0 text-base text-neutral-600" data-kpi-sub={props.testKey}>
          {props.sub}
        </p>
      ) : null}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
 * CR-085 group H — **WHICH SERVICE THE SCREEN IS ABOUT.**
 * ═══════════════════════════════════════════════════════════════════════════ */

/**
 * The wireframe's `ServicePicker` — one service at a time, on `s50` Usage and
 * on `s51` Readings.
 *
 * ⚠ **THE PRODUCT OWNER ASKED FOR THIS IN SO MANY WORDS** — *"on this screen
 * usage you will ahve to give drop down for utility services"* — and the
 * drawing says WHY: *"kWh, thousand gallons and therms cannot share an axis,
 * and a chart that mixes them is unreadable"* (CLAUDE.md hard rule 3, one
 * level up from a column). Ana's own account is the case: **800 kWh and 8
 * kgal**, drawn one under the other with no chooser, was two scales on one
 * page and a `MONTHLY AVERAGE` tile that named neither.
 *
 * ⚠ **A DROPDOWN ON A PHONE AND TABS ON A DESKTOP, WHICH IS ONE CONTROL AND
 * NOT TWO DECISIONS.** The drawing draws both — *"A picker on phone, tabs on
 * desktop"* — and `bills/Bills.tsx` already ships the same `md:hidden` /
 * `max-md:hidden` pair for its card list and its table. Both halves are real,
 * labelled controls pointed at ONE visible label (`DEF-CWP-3996`: an
 * `aria-label` is an accessible name, so a floating word beside a control
 * passes every checker and is still unreadable to a sighted person).
 *
 * ⚠ **`md` IS 900px IN THIS THEME AND BOTH FORMS COMPILE — CHECKED IN THE
 * BUILT CSS, NOT ASSUMED** (B14 rule 21's trap, `DEF-974`): `md:hidden` is
 * `@media (min-width:900px)` and `max-md:hidden` is `@media not all and
 * (min-width:900px)`. A misspelled utility emits nothing and every check
 * passes.
 *
 * ⚠ **ONE OPTION DRAWS NOTHING AT ALL** — the drawing's own state, verbatim:
 * *"One service only — No picker at all — a chooser with one option is
 * furniture."* `null`, not a disabled strip.
 *
 * ⚠ **THE LIST IS THE ACCOUNT'S OWN SERVICES AND NEVER A FIXED ONE.** The
 * drawing says so and CLAUDE.md's hard-won law 2 says what it costs: the front
 * end types the service list out by hand in two places, and the eleventh
 * service silently never appeared on screen.
 */
export function ServicePicker(props: {
  /** The visible kicker — *WHICH SERVICE*. Written by the catalogue. */
  label: string;
  /** The account's own services, in the order the server sent them. */
  services: readonly { code: string; name: string }[];
  current: string;
  onChoose: (code: string) => void;
  testId?: string;
}) {
  // `useId` runs before the early return: a hook may not sit behind a branch.
  const labelId = `svc-${useId()}`;
  if (props.services.length < 2) return null;
  return (
    <div className="flex flex-col gap-1" data-service-picker={props.testId ?? "service"}>
      <span id={labelId} className="text-xs font-bold uppercase tracking-wide text-neutral-600">
        {props.label}
      </span>
      {/* The phone's dropdown — the Product Owner's own word. `bg-[white]` and
          not `bg-white`: this theme clears the stock palette (`DEF-974`). */}
      <select
        aria-labelledby={labelId}
        data-service-select={props.testId ?? "service"}
        // ⚠ **`hidden … max-md:block`, NEVER `md:hidden`** — this theme is
        // DESKTOP-FIRST, every responsive rule is max-width, and `G107` keeps
        // the portal at zero min-width variants (`DEF-CWP-4004`). Both forms
        // compile, which is exactly why the drift is silent and why a gate is
        // the only thing that can see it.
        className="hidden border border-field-border bg-[white] px-3 py-2 text-body text-neutral-900 max-md:block"
        value={props.current}
        onChange={(event) => props.onChoose(event.target.value)}
      >
        {props.services.map((service) => (
          <option key={service.code} value={service.code}>
            {service.name}
          </option>
        ))}
      </select>
      {/* The desktop's tabs. `purpose="view"` and not `choice`: this switches
          WHICH panel is shown, which is a tablist and not a radiogroup —
          `SegmentedChoice` one screen up picks a VALUE and is right to differ. */}
      <SegmentedControl
        className="max-md:hidden"
        segments={props.services.map((service) => ({ id: service.code, label: service.name }))}
        active={props.current}
        onSelect={props.onChoose}
        label={props.label}
        labelledBy={labelId}
        purpose="view"
        name={props.testId ?? "service"}
      />
    </div>
  );
}
