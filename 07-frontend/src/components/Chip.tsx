// ── Trace ──────────────────────────────────────────────
// Change:   B14 rule 36 (PO 2026-09-04, *"style guide na dtailwind component
//           remain same - thi sis not in line with style guide - also toolkit
//           is not align"*) — the chip becomes a KIT component instead of a
//           private constant, because a private constant is a chip nobody
//           else can use.
// Defect:   DEF-3722 — the kit had no chip, so the Integrations grid drew its
//           category filter out of raw `<button>` pills with their own radius,
//           their own padding and their own two colours, while `FilterBar`
//           three directories away already drew r10's chip correctly.
// Rules:    r10 rule 12 (the toolbar's filter chips: `All` plus removable
//           applied-filter chips) · B14 rule 21 (Tailwind utilities, no
//           stylesheet class added; this file is on route-b-migrated.txt from
//           its first commit) · rule 5 (a chip is not a third button size — it
//           is a different control, and it is drawn once, here)
// Tests:    src/components/Chip.test.tsx
// Impacts:  components/FilterBar.tsx (now renders these instead of its own
//           private CHIP string) · features/integrations/IntegrationsTab.tsx
// ───────────────────────────────────────────────────────
//
// ONE CHIP, THREE SHAPES, AND WHY IT IS THREE EXPORTS AND NOT ONE COMPONENT
// ────────────────────────────────────────────────────────────────────────
// r10 draws a chip in exactly two situations and they behave differently:
//
//   [All]  [Svc: Water ×]  [Status: Active ×]      ← the filter bar
//   [All]  [Email]  [Payments]  [Accounting]       ← a chip set that CHOOSES
//
// The first is a static label with a REMOVE control inside it; the second is a
// pressable control whose selected state inverts. A single component taking
// both `onRemove` and `onClick` would take neither properly — `RowActions` and
// `Surfaces` each reached the same shape from the same direction, and the
// reason is the same: the element differs. A removable chip is a `<span>` with
// a `<button>` inside it (the ✕ is the control, and it needs its own
// accessible name); a choosing chip IS the button.
//
// ⚠ THE INVERTED STATE IS `border-text bg-text text-bg` AND IT IS NOT A COLOUR
// DECISION MADE HERE. It is transcribed from `FilterBar`'s `All` chip, which
// transcribed it from r10's `.fchip.active` — ink on paper, the same pair the
// product's own inverted controls use. Writing it a second time with different
// tokens is precisely how four screens acquired four chips.
//
// ⚠ AND THE TOKENS ARE THE THEME'S. `src/styles/tailwind.css` sets
// `--color-*: initial`, which DELETES Tailwind's stock palette — so
// `border-slate-300` and `bg-white` compile to NOTHING while `tsc`, eslint and
// every `toContain` assertion pass, because the class IS in the DOM
// (DEF-974 · DEF-INT-3630). `divider`, `text` and `bg` are declared;
// `src/styles/routeBUtilities.test.ts` compiles every class in this file
// through the real Tailwind and is the only check that knows the difference.
import type { HTMLAttributes, ReactNode } from "react";

/**
 * r10 `.fchip`: inline-flex, 6px gap, 4px/12px padding, 12px heading type at
 * weight 600, one divider-coloured hairline.
 *
 * ⚠ IT IS A CONSTANT AND NOT A PROP. Every caller gets the same chip; the only
 * thing a caller varies is whether it is SELECTED, which is the line below.
 */
const CHIP =
  "inline-flex items-center gap-1.5 border px-3 py-1 font-heading text-btn-sm font-semibold";

/** Selected inverts to ink-on-paper; at rest it is a hairline (r10 `.fchip.active`). */
const RESTING = "border-divider bg-transparent";
const SELECTED = "border-text bg-text text-bg";

/**
 * ⚠ EVERY CLASS STRING BELOW IS A WHOLE LITERAL AND NONE IS BUILT BY GLUING A
 * LITERAL TO AN INTERPOLATION, AND THAT IS NOT A STYLE PREFERENCE.
 * Tailwind's scanner reads source TEXT: it cannot see a class it would have to
 * evaluate, so `gap-2${maybe}` is read as the token `gap-2$` and `gap-2` is
 * never emitted. The class is still in the DOM, so tsc, eslint and every
 * `toContain` pass — CR-018 Phase 0 lost 55 of 76 swatches to exactly this.
 * `src/styles/routeBUtilities.test.ts` refused this file's first draft by name
 * for two such joins, which is the check doing its job one commit before a
 * screenshot would have.
 */
export function chipClasses(selected: boolean, extra?: string): string {
  const base = `${CHIP} ${selected ? SELECTED : RESTING}`;
  return extra === undefined || extra === "" ? base : `${base} ${extra}`;
}

/** Join what a caller handed in without ever putting a literal beside a `${`. */
function withExtra(base: string, extra?: string): string {
  return extra === undefined || extra === "" ? base : `${base} ${extra}`;
}

/**
 * A chip that CHOOSES — one of a set, exactly one selected at a time.
 *
 * `aria-pressed` and not `role="radio"`: a radio group demands roving focus
 * management and arrow-key navigation, and r10's chip row is a row of ordinary
 * buttons a person tabs through. `aria-pressed` says the same thing about the
 * one fact that matters — this one is on — without claiming a keyboard
 * contract this control does not implement.
 */
export function ChipToggle({
  selected,
  className,
  children,
  ...rest
}: {
  selected: boolean;
  children: ReactNode;
} & Omit<HTMLAttributes<HTMLButtonElement>, "children">) {
  return (
    <button
      type="button"
      data-chip={selected ? "selected" : "resting"}
      aria-pressed={selected}
      className={chipClasses(selected, withExtra("cursor-pointer", className))}
      {...rest}
    >
      {children}
    </button>
  );
}

/**
 * A chip that STATES something and can be taken off — the applied-filter chip.
 *
 * The ✕ is a real button with its own accessible name. r10 makes the whole
 * chip clickable with a bare `×` glyph, which names nothing to a screen
 * reader; `FilterBar` had already diverged on exactly this point and the
 * divergence travels with the component rather than being re-decided.
 */
export function Chip({
  onRemove,
  removeLabel,
  className,
  children,
  ...rest
}: {
  /** Absent = the chip is not removable and renders no ✕. */
  onRemove?: () => void;
  /** The ✕'s accessible name. Required whenever `onRemove` is given. */
  removeLabel?: string;
  children: ReactNode;
} & Omit<HTMLAttributes<HTMLSpanElement>, "children">) {
  return (
    <span
      data-chip="resting"
      className={chipClasses(false, className)}
      {...rest}
    >
      {children}
      {onRemove !== undefined && (
        <button
          type="button"
          className="cursor-pointer border-none bg-transparent p-0 text-btn-sm opacity-60 hover:opacity-100"
          aria-label={removeLabel}
          onClick={onRemove}
        >
          ×
        </button>
      )}
    </span>
  );
}

/** r10 `.fbar` — flex, 8px gap, wraps. One literal, so the scanner sees it. */
const CHIP_ROW = "flex flex-wrap items-center gap-2";

/**
 * The row the chips sit in.
 *
 * ⚠ IT EXISTS SO THE GAP IS DECIDED ONCE. The Integrations grid wrote `gap-2`
 * and the filter bar wrote `gap-2`, and that they agreed was luck: nothing
 * compared them, and the next screen would have written `gap-3`.
 */
export function ChipRow({
  className,
  children,
  ...rest
}: { children: ReactNode } & HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-chip-row=""
      className={withExtra(CHIP_ROW, className)}
      {...rest}
    >
      {children}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: B14 rule 36 (PO 2026-09-04) · DEF-3722 · r10 UI-RULES rule 12
// generated: 2026-09-04 by the style-conformance lane
// checklist: A=n/a(a control) B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: tsc · eslint · vitest src/components/Chip.test.tsx · routeBUtilities.test.ts (every utility here compiles against the real theme) · G86 (this file is the kit, so it is exempt by path — the gate reads features/ and portal/)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
