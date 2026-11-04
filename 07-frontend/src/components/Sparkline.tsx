// ── Trace ──────────────────────────────────────────────
// Story:    US-RBS-016 (EP-RBS-01) — CR-075 wave C task C1a. The `Records`
//           block's SPARKLINE CELL, the fourth cell renderer beside
//           `StatusPill`, `MoneyCell` and `UnitCell`.
//           Screens: RBS-006-R5, column *Twelve months* (runbook 5, the only
//           runbook that uses it)
// Rules:    B14 rule 36 · B14 rule 21 + its per-file clause · B14 rule 20 (one
//           table type — a cell must not change the row height) · CLAUDE.md
//           hard rule 3 (a quantity carries an explicit unit, never assumed)
// Tests:    src/components/Sparkline.test.tsx
// Impacts:  04-docs/05-modules/17-runbooks/09-component-inventory.md Part 1
//           row 4 (*"The sparkline cell and the grid mode are not [built]"*) ·
//           07-frontend/src/styles/route-b-migrated.txt
// ───────────────────────────────────────────────────────
//
// **TWELVE MONTHS OF A METER, IN A TABLE CELL.** `RBS-006-R5` draws five rows
// and each carries a line: flat, a spike with a dot on it, a fall to zero, a
// rollover, and a DASHED line where the twelve months are estimated rather than
// read. The pattern is named in words in the column beside it — *▬ Flat ·
// 5 months*, *▲ Spike · Jul* — so the line is the evidence and never the only
// statement. That ordering is deliberate and worth keeping: a picture no
// screen reader can read is not an answer.
//
// ⚠ **INLINE SVG, NO LIBRARY.** `Chart` (FE-20) is unbuilt, and a charting
// library here would ship axes, a legend and a tooltip into a 26px table cell.
// Twelve points and a polyline need none of them.
//
// ⚠ **THE DASHED LINE IS THE RULED EXCEPTION TO RULE 36, LIKE THE dashed
// `ref:setting` BOX.** Part 4 §4's test: a dashed border means *this is not
// yours to edit here* — and here it means *these figures were not read, they
// were estimated*, which is the same family of meaning and is exactly what
// `RBS-006-R5`'s bottom row says in words beside it (*≈ Estimated · 6 of 12*).
// Nothing else in this component is dashed and nothing is monospaced.
//
// ⚠ **HARD RULE 3 REACHES A PICTURE TOO.** A sparkline has no axis, so the unit
// cannot be inferred from anything on screen — which makes an unlabelled one
// strictly worse than an unlabelled number. `label` is REQUIRED and the caller
// composes it with its unit (*Twelve months of water use, in gallons*), so
// "assume gallons" is unexpressible rather than merely discouraged.

/** How the series was obtained. It changes the LINE, not the shape. */
export type SparklineSource = "read" | "estimated";

export interface SparklineProps {
  /** Twelve or so points, oldest first. Numbers, not decimal strings: these are
   *  QUANTITIES being compared against each other for shape, never money and
   *  never a figure a reader reads off. A money series belongs in a column
   *  through `MoneyCell`. */
  points: readonly number[];
  /** What the line is, WITH its unit — hard rule 3. Already translated. It is
   *  the accessible name and the tooltip, so it is what a reader who cannot see
   *  the line gets instead. */
  label: string;
  source?: SparklineSource;
  /** Which point to mark, by index — the spike, the month it went flat. A dot
   *  on `RBS-006-R5`'s line. Omit for no dot. */
  markAt?: number;
}

// 180 × 26 keeps the cell at B14 rule 20's row height: the table body is
// 13.5px with padding, so a taller cell would re-size every row in the table
// and break the one-table-type rule from inside a single column.
const WIDTH = 180;
const HEIGHT = 26;
const PADDING = 3;

/**
 * The sparkline cell. `RBS-006-R5` column 4.
 *
 * `role="img"` with the label as its accessible name: a screen reader says the
 * sentence and skips the geometry.
 */
export function Sparkline(props: SparklineProps) {
  const source = props.source ?? "read";
  const usable = props.points.filter((n) => Number.isFinite(n));
  // A series of one point, or none, has no shape to draw. It renders as the
  // label alone rather than as an empty box or a misleading flat line — a flat
  // line is a FINDING on this screen (*▬ Flat · 5 months*) and drawing one for
  // "no data" would report a pattern the meter never had.
  if (usable.length < 2) {
    return (
      <span className="text-xs text-neutral-600" data-sparkline="" data-sparkline-empty="">
        {props.label}
      </span>
    );
  }
  const low = Math.min(...usable);
  const high = Math.max(...usable);
  // A genuinely flat series has zero span; dividing by it would put every point
  // at NaN and draw nothing at all. It draws down the middle instead, which is
  // the honest picture of a meter that has not moved.
  const span = high - low === 0 ? 1 : high - low;
  const step = usable.length === 1 ? 0 : (WIDTH - PADDING * 2) / (usable.length - 1);
  const at = (value: number, index: number): [number, number] => [
    PADDING + step * index,
    HEIGHT - PADDING - ((value - low) / span) * (HEIGHT - PADDING * 2),
  ];
  const path = usable.map((value, i) => at(value, i).join(",")).join(" ");
  const mark =
    props.markAt !== undefined && props.markAt >= 0 && props.markAt < usable.length
      ? at(usable[props.markAt], props.markAt)
      : null;
  return (
    <svg
      className="block h-[26px] w-[180px]"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label={props.label}
      data-sparkline=""
      data-sparkline-source={source}
      data-sparkline-points={usable.length}
    >
      <title>{props.label}</title>
      <polyline
        points={path}
        fill="none"
        // The stroke is a token, read through `currentColor`'s neighbour rather
        // than hard-coded: `stroke-neutral-700` compiles here (asked of the real
        // compiler, DEF-SHL-4281) and a hex would drift from the palette.
        className="stroke-neutral-700"
        strokeWidth={1.5}
        strokeDasharray={source === "estimated" ? "4 3" : undefined}
        data-sparkline-line=""
      />
      {mark !== null && (
        <circle
          cx={mark[0]}
          cy={mark[1]}
          r={3}
          className="fill-accent"
          data-sparkline-mark=""
        />
      )}
    </svg>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-016 · CR-075 wave C task C1a · 09-component-inventory.md Part 1 row 4 · frame RBS-006-R5
// generated: 2026-09-06 by the CR-075 wave C build lane
// checklist: A=n/a B=n/a C✔ D=n/a E✔(the Records block's cell renderers) F✔ G✔ H=n/a
// gates: vitest src/components/Sparkline.test.tsx · runbookKitClasses · routeBUtilities · G31 · tsc
// exceptions: the dashed stroke for an estimated series, which B14 rule 36 permits by Part 4 §4's test and which the column beside it states in words
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
