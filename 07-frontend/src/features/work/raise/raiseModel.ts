// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 3, lane RAISE — the decisions the raise makes,
//           pulled out of the DOM so they can be checked exhaustively (the
//           `popoverAnchor.ts` precedent: jsdom does no layout and no gate
//           reads rendered output).
// Rulings:  19 (one job per unit ticked) · 20 (an asset type chosen means the
//           asset must be chosen) · 24 (no Area — the job takes its
//           building's) · 25 (assign at raise, or leave it blank).
// Tests:    src/features/work/raise/raiseModel.test.ts
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";

import { SEARCH_DEBOUNCE_MS } from "@/components/searchDebounce";

import type { RaiseOptionType } from "../workEndpoints";

/** Where the raise was opened from — ruling 35: from an account or an asset
 *  the form arrives filled. */
export type RaiseOrigin =
  | { kind: "work"; premisesId?: string }
  | { kind: "account"; accountId: string }
  | { kind: "asset"; assetId: string };

/** A unit ticked on step 1, with the words the Confirm table draws for it. */
export interface ChosenUnit {
  id: string;
  label: string;
}

/** An asset ticked on step 1. `unitKey` groups the "Choose one" rule. */
export interface ChosenAsset {
  id: string;
  assetNo: string;
  unitKey: string;
  unitLabel: string;
  where: string | null;
  lastRead: string | null;
}

/**
 * **JOB TYPE AS A TWO-LEVEL PICKER (`DEF-WRK-9582`, P2.3).** A heading and its
 * sub-types are one flat list today, so *Outage report* sits beside
 * *Electrical Line* with nothing to tell the two apart. `WorkOrderType.parent`
 * is exactly two deep (`lookups.py` refuses a grandparent), so a heading with
 * sub-types becomes an `<optgroup>` and its sub-types the options; a heading
 * with no sub-types is an ordinary option.
 *
 * ⚠ A heading that HAS sub-types is not itself pickable — the sub-type is the
 * job. A heading with none is the job.
 */
export function jobTypeChoices(types: readonly RaiseOptionType[]): {
  options: { value: string; label: string }[];
  groups: { label: string; options: { value: string; label: string }[] }[];
} {
  const parents = new Set(types.map((row) => row.parent_name).filter((n): n is string => n !== null));
  const options = types
    .filter((row) => row.parent_name === null && !parents.has(row.name))
    .map((row) => ({ value: row.id, label: row.name }));
  const groups: { label: string; options: { value: string; label: string }[] }[] = [];
  for (const parent of parents) {
    groups.push({
      label: parent,
      options: types
        .filter((row) => row.parent_name === parent)
        .map((row) => ({ value: row.id, label: row.name })),
    });
  }
  return { options, groups };
}

/**
 * `DEF-WRK-9582` — the SAME two levels for a FILTER, where (unlike the raise)
 * a heading is a real choice: the server's `type=` matches a heading AND every
 * sub-type under it (`dispatch._apply_filters`). Each heading is followed by
 * its sub-types; a type with no sub-types stands alone as a flat option.
 * Headings and the types under them keep the catalogue's own order by name.
 */
export function jobTypeFilterOptions(
  types: readonly { id: string; name: string; parent_name?: string | null }[],
): { options: { value: string; label: string }[]; levels: Record<string, 1 | 2> } {
  const byName = (a: { name: string }, b: { name: string }) => a.name.localeCompare(b.name);
  const children = new Map<string, { id: string; name: string }[]>();
  for (const row of types) {
    if (row.parent_name) children.set(row.parent_name, [...(children.get(row.parent_name) ?? []), row]);
  }
  const out: { value: string; label: string }[] = [];
  const levels: Record<string, 1 | 2> = {};
  for (const row of [...types].filter((r) => !r.parent_name).sort(byName)) {
    const subs = (children.get(row.name) ?? []).sort(byName);
    out.push({ value: row.id, label: row.name });
    if (subs.length > 0) levels[row.id] = 1;
    for (const sub of subs) {
      out.push({ value: sub.id, label: sub.name });
      levels[sub.id] = 2;
    }
  }
  // A sub-type whose heading is not on the list (retired) is still a choice.
  const heads = new Set(types.filter((r) => !r.parent_name).map((r) => r.name));
  for (const row of types.filter((r) => r.parent_name && !heads.has(r.parent_name)).sort(byName)) {
    out.push({ value: row.id, label: row.name });
  }
  return { options: out, levels };
}

/**
 * **RULING 20 — WHICH TICKED UNITS STILL NEED THEIR ASSET CHOSEN.** A unit
 * with two meters of the chosen type has no single answer, so the clerk ticks
 * the one the job is for; a unit with none of its assets ticked is named.
 * Units are reported in the order the clerk ticked them.
 */
export function unitsMissingAnAsset(
  units: readonly ChosenUnit[],
  seen: readonly { unitKey: string }[],
  chosen: readonly ChosenAsset[],
): ChosenUnit[] {
  const hasAssets = new Set(seen.map((row) => row.unitKey));
  const covered = new Set(chosen.flatMap((row) => [row.unitKey, row.unitLabel]));
  return units.filter(
    (unit) =>
      (hasAssets.has(unit.id) || hasAssets.has(unit.label)) &&
      !covered.has(unit.id) &&
      !covered.has(unit.label),
  );
}

/** Units on which more than one asset of the type stands and none is ticked —
 *  each of their rows wears *Choose one* (image 15). */
export function chooseOneUnits(
  seen: readonly { unitKey: string; id: string }[],
  chosen: readonly ChosenAsset[],
): Set<string> {
  const counts = new Map<string, number>();
  for (const row of seen) counts.set(row.unitKey, (counts.get(row.unitKey) ?? 0) + 1);
  const covered = new Set(chosen.map((row) => row.unitKey));
  return new Set([...counts].filter(([key, n]) => n > 1 && !covered.has(key)).map(([key]) => key));
}

/** One job per unit, or per asset once an asset type is chosen (rulings 19, 20). */
export function jobCount(assetTypeChosen: boolean, units: number, assets: number): number {
  return assetTypeChosen ? assets : units;
}

/** The due date the priority promises, as `YYYY-MM-DD` — what the date picker
 *  opens on (image 16: *From the priority — 72 h*). */
export function dueFromPriority(slaHours: number, now: Date): string {
  const due = new Date(now.getTime() + slaHours * 3_600_000);
  const month = String(due.getMonth() + 1).padStart(2, "0");
  const day = String(due.getDate()).padStart(2, "0");
  return `${due.getFullYear()}-${month}-${day}`;
}

/** The assignee the write carries — `technician_id` for a person, `crew_id`
 *  for a crew or a contractor (a contractor is a crew row, `BR-WRK-028`). */
export function assigneeFor(
  candidate: { kind: string; id: string } | null,
): { technician_id: string } | { crew_id: string } | null {
  if (candidate === null) return null;
  return candidate.kind === "technician" || candidate.kind === "person"
    ? { technician_id: candidate.id }
    : { crew_id: candidate.id };
}

/** A fresh key per Confirm visit, so a double press returns the first answer. */
export function newIdempotencyKey(): string {
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** IS-3 — a typed search reaches the server 300 ms after the last keystroke,
 *  never on each one. */
export function useDebouncedTerm(value: string, ms: number = SEARCH_DEBOUNCE_MS): string {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}
