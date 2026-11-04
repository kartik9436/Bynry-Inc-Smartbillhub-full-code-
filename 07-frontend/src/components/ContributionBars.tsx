// ── Trace ──────────────────────────────────────────────
// Story:    US-RBS-016 (EP-RBS-01) — CR-075 wave C task C1a, block 7 (Ranked)
//           of the twelve. Screens: RBS-006-R4 (six rows) · RBS-006-R16
// Rules:    B14 rule 36 (the pack gives layout, r10 gives the visual style, and
//           **nothing dashed, monospaced or labelled like a diagram** ships to
//           a utility user — see the mono note below) · B14 rule 21 + its
//           per-file clause · B14 rule 32 · CLAUDE.md hard rule 2 (money
//           displays 2) · hard rule 3 (a quantity carries its unit)
// Tests:    src/components/ContributionBars.test.tsx
// Impacts:  04-docs/05-modules/17-runbooks/09-component-inventory.md Part 5 §3 ·
//           07-frontend/src/styles/route-b-migrated.txt
// ───────────────────────────────────────────────────────
//
// **WHAT CAUSED IT · LARGEST FIRST.** `RBS-006-R4` draws six rows: a label with
// a quieter second line under it, a thin bar, and the figure right-aligned —
// *More water used · 7,240 gal vs 5,250 gal · 4 more days · +$46.40*.
//
// ⚠ **THIS IS NOT A CHART AND MUST NOT BECOME ONE.** `09-component-inventory.md`
// Part 5 §3 says so: `Chart` (FE-20) is unbuilt and is *"the wrong instrument
// anyway — this is a row list with a bar, not a chart."* It has no axes, no
// legend and no scale a reader is meant to read off; the BAR is a comparison
// between the rows and the VALUE is the fact. Reaching for a charting library
// here would add an axis nobody asked for and a tooltip that hides the number.
//
// ⚠ **THE BAR IS PROPORTIONAL AND THE COMPONENT DOES THE ARITHMETIC, ONCE.**
// Every sheet draws the rows largest first with the widest bar on the top row,
// so the proportion is against the LARGEST ROW rather than against the total —
// a share-of-total reading would draw the top bar at 46% and look like a bug.
// The caller hands in a `weight` (a non-negative number) and this decides the
// width, so twelve screens cannot each pick their own denominator.
//
// ⚠ **THE VALUE IS MONOSPACED AND THAT IS DELIBERATE UNDER RULE 36.** The
// build sheets specify *"value mono 12.5px right"*, and rule 36 bans monospace
// as an ANNOTATION style. `09-component-inventory.md` Part 4 §4 settles it:
// monospace here means *a machine produced this exact value*, in a column that
// must align digit under digit — and it names `RBS-006-R4`'s `+$46.40` as
// PASSING for exactly that reason, while `RBS-004-R8`'s panel subtitle FAILS.
// So the tabular figures keep the mono; nothing else in this component has it.
import type { ReactNode } from "react";

export interface ContributionRow {
  /** Stable key. Never rendered — B14 rule 31. */
  id: string;
  /** *More water used* · *Reached tier 2*. Already translated. */
  label: string;
  /** The quieter second line: *7,240 gal vs 5,250 gal · 4 more days*. A
   *  quantity in it carries its unit (hard rule 3) — the caller composes it
   *  through `UnitCell`, which makes the unit compile-required. */
  detail?: ReactNode;
  /** How long the bar is, relative to the largest row. Non-negative. A row that
   *  contributed nothing gets `0` and draws an empty track, which is what
   *  `RBS-006-R4`'s *Rate change · None between the two bills · $0.00* is: a
   *  cause that was CHECKED and found not guilty, which is worth a row. */
  weight: number;
  /** The figure, already formatted — `+$46.40` through `MoneyCell`'s
   *  `formatMoney`, `+4.7%` through `PercentCell`'s `formatPercent`. This
   *  component never formats a number: BR-SHL-023 keeps one formatting path,
   *  and a second one here is how a screen shows `$46.4` beside a real charge. */
  value: ReactNode;
}

export interface ContributionBarsProps {
  rows: readonly ContributionRow[];
  /** What the list is, for a screen reader: *What caused it, largest first.* */
  label: string;
}

/**
 * The Ranked block. `RBS-006-R4` region 4, `RBS-006-R16` region 5.
 *
 * Rows are drawn in the order given. Sorting is the runbook's job, not this
 * component's — `RBS-006-R16` ranks by contribution and `RBS-006-R4` ranks by
 * money, and a component that re-sorted would silently disagree with whichever
 * one it was not written for.
 */
export function ContributionBars(props: ContributionBarsProps) {
  // Against the LARGEST row, not the total — see the header. A list whose rows
  // are all zero (nothing moved, which is a real and reportable outcome) would
  // divide by zero, so the denominator floors at 1 and every bar draws empty.
  const largest = props.rows.reduce((max, row) => (row.weight > max ? row.weight : max), 0);
  const denominator = largest > 0 ? largest : 1;
  return (
    <ol className="m-0 flex list-none flex-col gap-3 p-0" aria-label={props.label} data-bars="">
      {props.rows.map((row) => {
        const filled = Math.max(0, Math.min(100, (row.weight / denominator) * 100));
        return (
          <li
            key={row.id}
            className="flex flex-wrap items-center gap-3"
            data-bar-row=""
            data-bar-weight={row.weight}
          >
            <span className="min-w-[200px] flex-1">
              <span className="block text-md text-neutral-900">{row.label}</span>
              {row.detail !== undefined && (
                <span className="block text-sm text-neutral-600">{row.detail}</span>
              )}
            </span>
            <span
              className="h-[8px] w-[180px] shrink-0 bg-neutral-300"
              // The track is the comparison; the fill is this row's share of the
              // largest. `aria-hidden` because the figure beside it says the same
              // thing in words, and a screen reader reading a bar twice is noise.
              aria-hidden="true"
              data-bar-track=""
            >
              <span
                className="block h-full bg-neutral-700"
                style={{ width: `${filled}%` }}
                data-bar-fill=""
              />
            </span>
            <span
              className="w-[110px] shrink-0 text-right font-mono text-sm text-neutral-900 tabular-nums"
              data-bar-value=""
            >
              {row.value}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-016 · CR-075 wave C task C1a · 09-component-inventory.md Part 5 §3 · frames RBS-006-R4, RBS-006-R16
// generated: 2026-09-06 by the CR-075 wave C build lane
// checklist: A=n/a B=n/a C✔ D=n/a E✔(the Ranked block composes it) F✔ G✔ H=n/a
// gates: vitest src/components/ContributionBars.test.tsx · runbookKitClasses · routeBUtilities · G31 · tsc
// exceptions: the mono value, which Part 4 §4 rules PASSING under B14 rule 36 (a machine produced this exact value, in a column that must align)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
