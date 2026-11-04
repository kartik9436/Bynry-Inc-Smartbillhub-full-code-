// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 1 · P1.3 — screen 1·1's Standard · Custom strip
//          (05-prototype/09 Reports Build Brief.pdf p20 callout ④, read as an
//          IMAGE per B14 rule 42).
// Rules:   B14 rule 43 (a piece of UI is built as a COMPONENT; standalone code
//          inside a page is not reuse) · rule 36 (where the kit lacks a piece a
//          screen needs, ADD IT TO THE KIT as an opt-in, so nothing existing
//          moves) · rule 21 (Tailwind utilities; NO class added to a
//          stylesheet) · rule 44 (the drawing says what is on the screen; our
//          spacing and token scale say how it is built, and they win) · rule 5
//          (two button sizes only) · rule 33 (a LABEL is three words)
// Tests:   src/components/SubTabs.test.tsx
// ───────────────────────────────────────────────────────
//
// A SECOND-LEVEL TAB STRIP, IN THE KIT, WHERE THERE WAS ONLY A STYLESHEET.
//
// ── WHY THIS IS A NEW FILE AND NOT A REUSE ──────────────────────────────────
//
// The product already draws this shape in three places — Settings → Company,
// Users & roles, and Configure — and every one of them is `<div
// className="settings-tabs" role="tablist">` over `SettingsPage.css`. That is
// B14 rule 43's subject exactly: three copies of one piece of UI, importable by
// nothing, and a fourth screen wanting the shape has only two ways in, both
// wrong. It can add `settings-tabs` to a Reports page — a Settings class on a
// Reports screen, which couples them for ever — or it can hand-roll a fourth
// copy, which is what `DEF-3722`'s chip did three directories from a chip that
// already existed.
//
// So the strip becomes a component. **`SettingsPage` is NOT migrated** — rule
// 36's own clause, *added as an opt-in so nothing existing moves*: the three
// shipped strips keep their stylesheet until a Settings lane touches them for
// its own reasons, and nothing on 27 screens moves to serve one new one.
//
// ── WHAT IS TRANSCRIBED AND WHAT IS TAKEN FROM OUR SCALE ────────────────────
//
// Transcribed from `SettingsPage.css` `.settings-tabs`, so the fourth strip
// looks like the three shipped ones: a 2px divider rule under the row, the
// active tab in accent with a 2px accent rule sitting ON that divider
// (`-mb-0.5`), inactive text at 65% of the ink, `font-heading` 600 at
// `--text-btn`, which is B14 rule 5's default tier.
//
// ⚠ **ONE MEASUREMENT IS OURS AND NOT THE STYLESHEET'S.** `.settings-tabs
// button` pads `var(--space-3) 18px`. **18px is not on the scale** — it sits
// between `--space-4` (16px) and `--space-5` (20px) — and B14 rule 44 says the
// scale wins and there is nothing to escalate, because rule 37 already makes a
// drawn figure an illustration and the drawing never spoke to it. So the
// horizontal padding is `px-4`, 16px, the nearer of the two. The vertical is
// `py-3`, which IS `--space-3` exactly. This is a 2px-per-side difference from
// the three shipped Settings strips and it is deliberate; it is recorded in
// 12-governance/02-decision-log.md, 2026-09-26, rather than left to be found.
//
// ⚠ **THE COUNT IS PART OF THE LABEL AND NOT A BADGE.** The drawing writes
// `Standard · 45` and `Custom · 0` as one run of text, and callout ④ is why
// that matters: *"Custom reads 0 on day one and that is the point — an empty
// sub-tab is how a clerk learns they can author a report."* A count that
// disappears when it is zero would delete the one thing the strip is for, so
// `count: 0` RENDERS and only `count: undefined` draws nothing.
import type { ReactNode } from "react";

export interface SubTab {
  id: string;
  label: string;
  /** Rendered as ` · N`. **Zero renders; absent does not.** See above. */
  count?: number;
}

/**
 * The strip. `onSelect` is given the tab's id; the caller owns where that goes
 * — a URL segment, a query parameter or local state — because a strip that
 * navigated would be a strip that only works on screens shaped like Settings.
 */
export function SubTabs(props: {
  tabs: readonly SubTab[];
  activeId: string;
  onSelect: (id: string) => void;
  /** The accessible name of the strip. B14 rule 33: three words. */
  label: string;
  /** A name for the strip in tests and browser walkthroughs. */
  "data-sub-tabs"?: string;
}): ReactNode {
  // ⚠ A ONE-TAB STRIP IS FURNITURE — p20 callout ③, ruled by the PO on
  // 2026-09-26 (12-governance/02-decision-log.md, 76be101a3): *"The strip is
  // not drawn until the second tab exists."* It is enforced HERE rather than
  // remembered by each caller, because the caller that forgets is the one that
  // draws a strip a clerk cannot use.
  if (props.tabs.length < 2) {
    return null;
  }
  return (
    <div
      className="mb-6 flex flex-wrap border-b-2 border-b-divider"
      role="tablist"
      aria-label={props.label}
      data-sub-tabs={props["data-sub-tabs"] ?? ""}
    >
      {props.tabs.map((tab) => {
        const selected = tab.id === props.activeId;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={selected}
            data-sub-tab={tab.id}
            className={[
              "-mb-0.5 cursor-pointer border-0 border-b-2 bg-transparent px-4 py-3",
              "font-heading text-btn font-semibold",
              selected
                ? "border-b-accent text-accent-text"
                : "border-b-transparent text-[color-mix(in_srgb,var(--color-text)_65%,transparent)] hover:text-text",
            ].join(" ")}
            onClick={() => props.onSelect(tab.id)}
          >
            {tab.count === undefined ? tab.label : `${tab.label} · ${tab.count}`}
          </button>
        );
      })}
    </div>
  );
}

export default SubTabs;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 Phase 1 · P1.3 (05-prototype/09 Reports Build Brief.pdf p20 callout ④, read as an IMAGE)
// screens: S44
// generated: 2026-09-26 by lane REP-P1
// gates: RED PROVED FIRST — SubTabs.test.tsx could not resolve ./SubTabs before this file existed, and the one-tab case returned a rendered strip until the length guard was written
// exceptions: (1) `px-4` where `.settings-tabs` pads 18px — B14 rule 44, 18px is off the scale · (2) the three shipped Settings strips are NOT migrated to this component (rule 36: added as an opt-in, nothing existing moves)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
