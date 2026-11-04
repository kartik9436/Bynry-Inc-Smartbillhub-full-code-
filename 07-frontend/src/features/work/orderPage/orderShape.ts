// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 2, lane ORDER-PAGE — P1.29, the order page's
//           two shapes (rulings 15 and 17, PO 2026-09-24).
// ───────────────────────────────────────────────────────
//
// ⚠ **THE SHAPE IS THE SERVER'S (`shape`, §7.3), AND THE FALLBACK IS ONLY FOR
// THE HOURS BEFORE THE SERVER SENDS IT.** Ruling 15 reads *"if the order is
// comleted then only user can view details in checklist and can view the
// customer signature and photos"* — so the one fact that decides is whether the
// field has completed the job, which is `state = completed`. The fallback reads
// exactly that and nothing else; it never looks at the dispatch status, which
// is a different axis and on the demo still reads *Scheduled* on finished jobs
// (`DEF-WRK-9526`).
import type { getWorkOrder } from "../workEndpoints";
import type { OrderPageFields } from "./orderPageEndpoints";

export type OrderRow = Awaited<ReturnType<typeof getWorkOrder>> & OrderPageFields;

export type OrderShape = "open" | "completed";

export function orderShape(row: Pick<OrderRow, "shape" | "state">): OrderShape {
  if (row.shape === "open" || row.shape === "completed") return row.shape;
  return row.state === "completed" ? "completed" : "open";
}

/** A job the office has already accepted — nothing on the page can act on it
 *  any more (`BR-MET-110`: the office only accepts, and only once). */
export function isAccepted(row: Pick<OrderRow, "accepted">): boolean {
  return row.accepted !== null && row.accepted !== undefined && row.accepted.at !== null;
}

/** A job that has stopped — cancelled — offers no action at all. */
export function isStopped(row: Pick<OrderRow, "state" | "dispatch_state">): boolean {
  return row.state === "cancelled" || row.dispatch_state === "cancelled";
}

function nameOf(by: string | { name: string } | null | undefined): string | null {
  if (by === null || by === undefined) return null;
  return typeof by === "string" ? by : by.name;
}

/** Image 04's *Closed by — D. Ortiz · 25 Sep, 11:50 AM*: who closed the job in
 *  the field, and when. Read from `closed` (§7.3); before the server sends it,
 *  the holder and `completed_at` are the same two facts. */
export function closedBy(row: OrderRow): { name: string | null; at: string | null } {
  if (row.closed) return { name: nameOf(row.closed.by), at: row.closed.at };
  return { name: row.technician?.name ?? null, at: row.completed_at ?? null };
}
