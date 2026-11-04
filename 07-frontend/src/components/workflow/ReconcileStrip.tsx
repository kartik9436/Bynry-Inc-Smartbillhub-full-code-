// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — the figure strip, ONE component and THREE uses
//           (design B15 §4.2 AFTER TRANSFORM · §4.3 KPI · §4.5 KPI)
// Rules:    B14 rule 21 (Tailwind) · B15 §9 note 6 (right-aligned numerics use
//           tabular numerals — r10 sets `font-feature-settings:tnum` on every
//           count it prints)
// Impacts:  components/workflow/WorkflowRunner.tsx composes this.
// ───────────────────────────────────────────────────────
import { Kicker } from "@/components/TextBits";

import type { ReconcileFigure } from "./contract";
import * as WF from "./workflowKit";

/**
 * A labelled figure strip — `Rows in 431 · Duplicates dropped 3 · Rows forward
 * 428` — reused as the Validate KPI strip and the Result KPI strip.
 *
 * ⚠ ONE COMPONENT, THREE USES, AND THAT IS THE WHOLE ARGUMENT FOR THIS KIT.
 * r10 draws these three blocks with three different pieces of inline CSS: the
 * transform reconcile as label/value rows in a tinted block, and the two KPI
 * strips as centred tiles — 4 across at stage 3, 3 across at stage 5. They are
 * the same thing said three ways: a set of counts, some of which are exceptions.
 * Written three times they drift; written once they cannot. `layout` says which
 * shape, and nothing else differs.
 *
 * ⚠ THE FLAGGED TILE IS A TINT, NOT A COLOURED NUMBER. r10 tints the whole
 * exception tile AND colours its figure, so `ERRORS 2` reads as an exception at
 * a glance and not only to a reader who knows the palette. Both are ported.
 *
 * ⚠ AND THE TILE FIGURE IS `text-metric` (26px) IN BOTH KPI USES, WHERE r10
 * DRAWS 24px AT STAGE 3 AND 26px AT STAGE 5. There is no 24px step in the ruled
 * type scale — `--text-h3` is 25 and `--text-metric-sm` is 22 — so honouring
 * r10 exactly would need an arbitrary value, which G34 refuses by name and
 * OQ-279 already carries six of. One tile component means one figure size; the
 * 2px is the cost and it is stated rather than absorbed.
 */
export interface ReconcileStripProps {
  /** The uppercase heading above the block ("After transform"), or `null` for
   *  the two KPI strips, which r10 draws with no caption. */
  caption: string | null;
  figures: readonly ReconcileFigure[];
  layout: "rows" | "tiles";
  /** Tiles across. Four is r10's strip and the default; five exists for the
   *  stage-3 KPI strip, whose fifth figure is `CR-036` (f)'s `Will load`.
   *  Ignored for `rows`. */
  tiles?: 4 | 5;
}

export function ReconcileStrip({ caption, figures, layout, tiles = 4 }: ReconcileStripProps) {
  if (layout === "rows") {
    return (
      <div className={WF.FIG_ROWS} data-workflow="reconcile" data-layout="rows">
        {caption !== null && (
          <Kicker as="div" className={WF.FIG_CAPTION}>
            {caption}
          </Kicker>
        )}
        {figures.map((figure) => (
          <div key={figure.id} className={WF.FIG_ROW} data-workflow-figure={figure.id}>
            <span>{figure.label}</span>
            <b className={WF.FIG_ROW_VALUE}>{figure.value}</b>
          </div>
        ))}
      </div>
    );
  }
  return (
    <div data-workflow="reconcile" data-layout="tiles">
      {caption !== null && (
        <Kicker as="div" className={WF.FIG_CAPTION}>
          {caption}
        </Kicker>
      )}
      <div className={tiles === 5 ? WF.FIG_TILES_5 : WF.FIG_TILES}>
        {figures.map((figure) => (
          <div
            key={figure.id}
            className={figure.flagged ? WF.FIG_TILE_FLAGGED : WF.FIG_TILE}
            data-workflow-figure={figure.id}
            data-flagged={figure.flagged ? "true" : "false"}
          >
            <Kicker as="div">{figure.label}</Kicker>
            <div className={figure.flagged ? WF.FIG_TILE_VALUE_FLAGGED : WF.FIG_TILE_VALUE}>
              {figure.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
