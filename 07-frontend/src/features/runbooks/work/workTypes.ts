// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-006 (EP-RBS-03) — CR-075 wave H task H3.
// Rules:   `07-endpoints.md` row 17 (`GET · PATCH /work-items[/{id}]`) ·
//          B14 rule 31 (no database id is ever the visible value of a field).
// ───────────────────────────────────────────────────────
//
// **THE WIRE SHAPE `GET /work-items` SERVES, WRITTEN ONCE.**
//
// ⚠ **`fingerprint` IS NOT HERE AND MUST NEVER BE.** `US-RBS-006` §5 says it in
// its own words: *never rendered*. The backend's `work_item_row` does not serve
// it either, and a type that declared it would invite a column somebody could
// draw. Two declarations, one absence.

/** One row of `RBS-007`, exactly as `selectors.work_item_row` serves it. */
export interface WorkItemRow {
  /** Never drawn. It is the key and the address of a `PATCH`. */
  id: string;
  source_kind: "finding" | "exception" | "human_task";
  /** The runbook's NAME, or `null` for a human task, which has no run. */
  from: string | null;
  run_id: string | null;
  runbook_key: string | null;
  title: string;
  /** *240 accounts*, *Water* — a count and a noun, never an id. */
  subject_ref: string | null;
  weight: number;
  /** The pill's machine name; the screen colours it and translates it. */
  weight_pill: string;
  /** Tenant-RELATIVE, resolved by the screen (`DEF-RBS-4329`). */
  fix_route: string | null;
  owner: string | null;
  owner_id: string | null;
  due_on: string | null;
  status: "open" | "resolved";
  /** The FIRST sighting. The age a clerk reads comes from this and from
   *  nothing else — `updated_at` is the last sighting and is not served. */
  created_at: string;
  resolved_at: string | null;
}

/** The three chips `RBS-007` region 2 draws. `all` is the ABSENCE of a filter
 *  and is never sent to the server. */
export type WorkChip = "all" | "blocks_billing" | "cutover";

/** The counts the list route serves beside its page — over the WHOLE list. */
export interface WorkCounts {
  all: number;
  blocks_billing: number;
  findings: number;
  exceptions: number;
  human_tasks: number;
}
