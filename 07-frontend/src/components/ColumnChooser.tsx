// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-INT-5498 — Settings → Connectors shipped two of UI-RULES 12's
//          four toolbar parts. The `▦ Columns` control existed ONLY inside
//          `DataTable`, welded to a `TableConfig<Row>` and a `<table>`, so the
//          connector CARD GRID could not reach it.
// Rules:   UI-RULES 12 (one toolbar in four parts — search · filter chips ·
//          `+ Filter ▾` · `▦ Columns`) · UI-RULES 14 (the ▦ opens show · hide ·
//          reorder · reset) · B14 rule 15 (the icon vocabulary has ONE owner) ·
//          B14 rule 21 (Tailwind utilities, no stylesheet class) ·
//          B14 rule 36 (where the kit lacks the piece a drawing needs, ADD IT
//          TO THE KIT rather than hand-rolling it in the screen).
// Impacts: components/DataTable.tsx (which now renders this instead of owning
//          it — 27 live lists) · features/integrations/IntegrationsTab.tsx.
// ───────────────────────────────────────────────────────
//
// THE `▦` PANEL — show, hide, reorder, reset. ONE of them, for the whole
// product.
//
// ⚠ **THIS IS A MOVE, NOT A SECOND IMPLEMENTATION, AND THAT DISTINCTION IS THE
// WHOLE REASON THE FILE EXISTS.** The Integration Blueprint asks this screen for
// a `▦ Columns` control and says in as many words why it must be the kit's:
// *"Naming it ▦ Columns keeps the kit's own control rather than minting a second
// one — B14 rule 36."* The alternative — copying 90 lines of JSX into the
// connector grid — is the exact shape this repository files most often: four
// screens, four chips, four radii. `DataTable` had already learned it once
// (`DEF-3722`, r10's `.fchip` as a private constant the next screen could not
// reach, now `components/Chip.tsx`).
//
// **Every byte of markup below came out of `DataTable.tsx` unchanged**, down to
// the `w-[21rem]` and the two `h-6 w-6` arrow squares, so no list in the product
// moves a pixel. `DataTableColumnPrefs.dom.test.tsx` and
// `DataTableColumnAnchor.dom.test.tsx` are the proof and neither was touched.
//
// ⚠ **THE DECISIONS STAYED WITH THE CALLER, AND THAT IS WHY THIS TAKES
// CALLBACKS RATHER THAN ARRAYS.** `DataTable`'s toggle is not "add or remove a
// key": `toggleColumnVisible` re-inserts a re-shown column at its CONFIG
// position, and BR-SHL-013's identity column cannot be hidden at all. Computing
// the next array in here would have quietly dropped both rules. So this
// component owns the drawing and the disclosure, and the caller owns what a
// press MEANS — which is also what lets a card grid reorder FACTS through the
// same control that reorders a table's COLUMNS.
//
// ⚠ **THE COPY IS `table.columns.*` FOR BOTH CALLERS, DELIBERATELY.** A card is
// a row on its side, so the blueprint keeps the kit's own word rather than
// minting a second vocabulary for the same control; a screen that wanted its own
// heading would be re-opening B14 rule 36 one level down.
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { panelAlignClass, resolvePanelAnchor } from "./popoverAnchor";
import type { PanelAnchor } from "./popoverAnchor";

import { Button } from "@/components/Button";
import { ColumnsIcon } from "@/components/icons";

/**
 * One line of the panel. `label` is PRE-TRANSLATED by the screen — the same
 * split `TableColumnConfig` already makes, because the framework never holds a
 * screen's own words.
 */
export interface ColumnChooserItem {
  key: string;
  label: string;
  /** BR-SHL-013's identity column: the box renders disabled and never hides. */
  locked?: boolean;
}

/** The panel's own width in px, and the number `resolvePanelAnchor` is given. */
const COLUMN_PANEL_WIDTH_PX = 336;

export function ColumnChooser(props: {
  /** Menu order: the visible ones in display order, then the hidden ones. */
  items: ColumnChooserItem[];
  visible: string[];
  onToggle: (key: string) => void;
  onMoveUp: (key: string) => void;
  onMoveDown: (key: string) => void;
  onReset: () => void;
}) {
  const { t } = useTranslation();
  const { items, visible } = props;
  const [anchor, setAnchor] = useState<PanelAnchor>({ align: "right", shiftPx: 0 });

  return (
    <details
      className="relative"
      // ⚠ MEASURED FROM THE SUMMARY, NOT THE PANEL. The panel's own width is
      //    the fixed `w-[21rem]` below — a constant, and the only honest source
      //    while the panel is still display:none on the frame the toggle fires.
      //    Reading the panel's rect here returns zeros, which
      //    `resolvePanelAnchor` treats as "do not move".
      onToggle={(event) => {
        if (!event.currentTarget.open) {
          return;
        }
        const summary = event.currentTarget.querySelector("summary");
        const rect = summary?.getBoundingClientRect();
        if (rect === undefined) {
          return;
        }
        setAnchor(
          resolvePanelAnchor({
            anchorLeft: rect.left,
            anchorRight: rect.right,
            panelWidth: COLUMN_PANEL_WIDTH_PX,
            viewportWidth: document.documentElement.clientWidth,
          }),
        );
      }}
    >
      {/* r10 draws a COLUMNS glyph with the tooltip "Choose columns · ↑↓ to
          reorder", not IS-5's interim ⋮ menu. The drawing supersedes the
          interim spec (OQ-013).

          ⚠ THE GLYPH IS IMPORTED, NOT DECLARED HERE (DEF-462). It was an
          inline `<svg>` — *"inline so it needs no icon dependency"* — and
          that is precisely what B14 rule 15 forbids and G37 refuses: the
          icon vocabulary has ONE owner, `components/icons.tsx`, because
          DEF-348 found the same pencil four times under two names. B14 rule 21
          still holds for the LAYOUT: Tailwind utilities, no stylesheet class. */}
      <summary
        aria-label={t("table.columns.open")}
        title={t("table.columns.title")}
        className="inline-flex h-8 w-8 cursor-pointer list-none items-center justify-center rounded-md border border-divider [&::-webkit-details-marker]:hidden"
      >
        <ColumnsIcon />
      </summary>
      {/* B14 rule 21 · matched to r10's drawing (PO screenshots 2026-08-20).
          Tailwind utilities throughout — the bespoke .table-columns-* rules
          this replaced are deleted from DataTable.css, so the CSS surface
          SHRINKS rather than growing beside a new implementation. */}
      {/* ⚠ WIDTH IS THE WHOLE FIX (DEF-440, PO 2026-08-21: *"its square, 1
          column in 1 row and arrows; in your UI it is disturbed"*). At
          `--size-menu-min` (260px) the header wrapped to two lines and every
          row wrapped the LABEL under its own checkbox, so a one-line row
          became three. r10 draws each row as `[x] Label ......... [up][dn]`,
          once, on one line. This is a fixed width rather than a min-width
          because the panel must not resize as labels change — a menu that
          reflows while the pointer is inside it moves the row being
          clicked. */}
      {/* ⚠ `right-0` IS NO LONGER UNCONDITIONAL (DEF-1085). `panelAlignClass`
          returns one of two STATIC tokens — never a built string — because
          this file is on `src/styles/route-b-migrated.txt` and its classes
          are answered by the Tailwind compiler, which reads source text and
          would compile `${side}-0` to nothing at all (DEF-974). */}
      <div
        className={`absolute ${panelAlignClass(anchor.align)} top-[calc(100%+var(--space-1))] z-40 flex w-[21rem] flex-col gap-2 border border-divider bg-surface p-3 shadow-md`}
        style={
          anchor.shiftPx === 0
            ? undefined
            : { transform: `translateX(${String(anchor.shiftPx)}px)` }
        }
      >
        <p className="m-0 whitespace-nowrap font-heading text-btn-sm font-semibold uppercase tracking-wider text-neutral-600">
          {t("table.columns.title")}
        </p>
        {items.map((col) => {
          const isVisible = visible.includes(col.key);
          const position = visible.indexOf(col.key);
          return (
            <div key={col.key} className="flex items-center justify-between gap-2 text-base">
              <label
                // `min-w-0` + `truncate` is what keeps a long label on ONE
                // line beside its box instead of pushing itself underneath:
                // without it the flex item refuses to shrink below its
                // content and wraps. A label too long for the panel ellipses
                // and keeps its full text in the title attribute.
                className="flex min-w-0 flex-1 cursor-pointer items-center gap-2"
                title={col.locked === true ? t("table.columns.identityLocked") : col.label}
              >
                <input
                  type="checkbox"
                  className="shrink-0"
                  checked={isVisible}
                  // BR-SHL-013: the identity column's hide control renders
                  // disabled — it stays visible always.
                  disabled={col.locked === true}
                  onChange={() => props.onToggle(col.key)}
                />
                <span className="truncate">{col.label}</span>
              </label>
              {/* Both arrows, always rendered when the column is visible, and
                  DISABLED at the ends rather than absent — a control that
                  vanishes at the boundary makes the row jump under the
                  pointer mid-reorder. B14 rule 21: Tailwind utilities. */}
              {isVisible && (
                // ⚠ r10 draws these as BORDERED SQUARES, not bare glyphs
                // (DEF-440). `shrink-0` so they keep their square against a
                // long label rather than being squeezed into rectangles —
                // the "its square" half of the PO's sentence.
                <span className="ml-auto inline-flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    className="inline-flex h-6 w-6 cursor-pointer items-center justify-center border border-divider bg-transparent text-btn-sm text-neutral-700 hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-40"
                    aria-label={t("table.columns.moveUp", { label: col.label })}
                    disabled={position <= 0}
                    onClick={() => props.onMoveUp(col.key)}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    className="inline-flex h-6 w-6 cursor-pointer items-center justify-center border border-divider bg-transparent text-btn-sm text-neutral-700 hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-40"
                    aria-label={t("table.columns.moveDown", { label: col.label })}
                    disabled={position < 0 || position >= visible.length - 1}
                    onClick={() => props.onMoveDown(col.key)}
                  >
                    ↓
                  </button>
                </span>
              )}
            </div>
          );
        })}
        {/* r10 draws this full-width across the foot of the panel. */}
        <Button
          variant="secondary"
          className="mt-1 w-full justify-center"
          onClick={() => props.onReset()}
        >
          {t("table.columns.reset")}
        </Button>
      </div>
    </details>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-INT-5498 (CR-110-BRC04) — the connector toolbar's missing two parts
// generated: 2026-09-16 by the CR-110 maintenance lane, as a MOVE out of DataTable.tsx
// checklist: A=n/a B✔ C✔ D=n/a E✔(rendered by DataTable and by IntegrationsTab) F✔ G✔ H=n/a
// gates: tsc · eslint · vitest (DataTable's two existing column dom suites are the move's proof) · G31 (both callers and this file are on route-b-migrated.txt) · G37 (the glyph is imported from components/icons.tsx)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
