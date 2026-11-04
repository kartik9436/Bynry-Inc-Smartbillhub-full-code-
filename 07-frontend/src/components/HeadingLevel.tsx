// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CWP-10563 — portal card and section headings chose their element
//           by LOOK, so the outline jumped h1 → h3 under a page title and a
//           card could not know where it sat (WCAG 1.3.1, 2.4.6; tester F-20).
// Rules:    decision log 2026-10-23, "Portal accessibility, Group D": one h1 per
//           page, no skipped levels, visual size unchanged.
// Tests:    src/components/HeadingLevel.test.tsx ·
//           src/portal/routing/portalOutline.dom.test.tsx
// ───────────────────────────────────────────────────────
import { createContext, createElement, useContext } from "react";
import type { HTMLAttributes, ReactNode } from "react";

/**
 * The level the NEXT section heading takes, where an outline is being kept.
 *
 * ⚠ **`null` MEANS "NOBODY IS KEEPING AN OUTLINE HERE", AND THAT IS THE STAFF
 * APP TODAY.** Every kit component that reads this falls back to the element it
 * always rendered when the value is `null`, so a staff screen renders byte for
 * byte what it did before this file existed. The portal sets `2` at its root
 * (`PortalApp`) — the page head is the h1 — and each section that draws a
 * heading hands `level + 1` to what it contains.
 *
 * ⚠ **THE LEVEL IS STRUCTURE AND THE SIZE IS A CLASS, AND THEY NEVER MEET.**
 * Each component keeps its own size utility (`text-lead`, `text-h5`,
 * `text-md`), and `global.css` sets only `font-size` per tag — which every one
 * of those classes overrides — so moving an `h3` to an `h2` moves the outline
 * and not a pixel.
 */
const HeadingLevelContext = createContext<number | null>(null);

/** Six is the deepest HTML heading; deeper nesting stays at h6 rather than inventing h7. */
function clamp(level: number): number {
  return Math.min(6, Math.max(1, Math.round(level)));
}

/** Start (or restart) an outline below this point: the next section heading is `level`. */
export function HeadingLevelProvider(props: { level: number; children: ReactNode }) {
  return (
    <HeadingLevelContext.Provider value={clamp(props.level)}>{props.children}</HeadingLevelContext.Provider>
  );
}

/** The level a section heading drawn here should take, or `null` outside any outline. */
export function useSectionHeadingLevel(): number | null {
  return useContext(HeadingLevelContext);
}

/**
 * The heading a section draws, and the level its CONTENTS' headings take.
 *
 * `fallback` is the element the component rendered before outlines existed —
 * used verbatim when no outline is being kept, which is what keeps the staff
 * app unchanged. `inner` is `null` in that case, so `SectionScope` adds no
 * provider and the tree is exactly what it was.
 */
export function useSectionHeading(fallback: number): {
  tag: `h${1 | 2 | 3 | 4 | 5 | 6}`;
  level: number;
  inner: number | null;
} {
  const outline = useSectionHeadingLevel();
  const level = outline ?? clamp(fallback);
  return {
    tag: `h${level}` as `h${1 | 2 | 3 | 4 | 5 | 6}`,
    level,
    inner: outline === null ? null : clamp(level + 1),
  };
}

/**
 * Wraps a section's contents so a heading inside it sits one level down.
 * A stable component (never one built during render, which would remount the
 * contents on every render and lose their state).
 */
export function SectionScope(props: { inner: number | null; children: ReactNode }) {
  if (props.inner === null) return <>{props.children}</>;
  return <HeadingLevelContext.Provider value={props.inner}>{props.children}</HeadingLevelContext.Provider>;
}

/** A heading element at a computed level, with whatever attributes the caller gives it. */
export function SectionHeadingTag(
  props: { tag: `h${1 | 2 | 3 | 4 | 5 | 6}`; children: ReactNode } & HTMLAttributes<HTMLHeadingElement>,
) {
  const { tag, children, ...rest } = props;
  return createElement(tag, rest, children);
}
