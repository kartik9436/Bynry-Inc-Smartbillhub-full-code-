/**
 * How many side-by-side columns the pane a component sits in can hold (R121,
 * R122): `fitColumns()` against the pane's MEASURED usable width, never the
 * window's. A screen that laid itself out two-up because the WINDOW was a
 * tablet (the readings grid, the job's own split, before-and-after, the walk
 * and the read entry) now asks this instead, so in a 464 content pane it stays
 * one column and in T4's 764 it goes two — the 260 rule holds by arithmetic.
 *
 * On a phone it is always one: the phone's layouts are the phone boards'.
 */
import { useFormFactor } from './FormFactor';
import { fitColumns } from './geometry';
import { usePaneWidth } from './TabletFrame';
import { space } from '../tokens';

/** The gap a grid of cards leaves between columns (the kit's card gap). */
export const COLUMN_GAP = space[3];

export function usePaneColumns(wanted: number, gap: number = COLUMN_GAP): number {
  const form = useFormFactor();
  const pane = usePaneWidth();
  if (!form.tablet) return 1;
  return fitColumns(pane.usable, gap, wanted);
}

/** Two columns of at least 260 fit here. */
export function useSideBySide(): boolean {
  return usePaneColumns(2) >= 2;
}

/** Split a list into rows of `n` — a grid without a grid component. */
export function rowsOf<T>(items: readonly T[], n: number): T[][] {
  const out: T[][] = [];
  const size = Math.max(1, n);
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}
