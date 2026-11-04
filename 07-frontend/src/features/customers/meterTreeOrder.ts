// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-9765 — the move-in details view listed a behind-the-meter
//           device above the sub-meter under the main meter, where image 24
//           (and step 1, image 30) put the sub-meter first.
// ───────────────────────────────────────────────────────
/**
 * **What is READ before what is not** — a sub-meter (owed an opening read)
 * before a device behind the meter; within each, the server's order.
 *
 * ONE helper for the meter tree, used by step 1 (`StepUnit.meterLines`) and the
 * details view (`UnitReadsTab.meterTree`). Step 1 had this sort inline and the
 * details view's copy of the same tree did not, which is how the two drew one
 * unit's meters in two orders.
 */
export function readFirst<T extends { needs_opening_read?: boolean | null }>(children: readonly T[]): T[] {
  return [...children].sort((a, b) => Number(!a.needs_opening_read) - Number(!b.needs_opening_read));
}
