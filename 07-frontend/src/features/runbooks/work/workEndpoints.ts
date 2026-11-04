// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-006 (EP-RBS-03) — CR-075 wave H task H3.
// Screens: RBS-007 (`S153`).
// Rules:   `07-endpoints.md` row 17 (`GET · PATCH /work-items[/{id}]`) ·
//          `NFR-3` (universal server pagination) · `BR-SHL-011` (the
//          `f.<name>` filter grammar).
// Defects: DEF-WRK-4119 · DEF-AST-4120 (three shipped screens drew empty
//          tables over rows the server HAD returned, because each described
//          the reply by hand).
// ───────────────────────────────────────────────────────
// THE TWO CALLS `RBS-007` MAKES, AND NEITHER DESCRIBES THE ENVELOPE.
//
// It lives in the feature rather than in `src/api/` for the reason
// `libraryEndpoints.ts` gives in its own header and applies here unchanged:
// several lanes are editing that folder this hour, and law 11 mechanism two is
// two lanes appending to one file where the second to commit silently reverts
// the first with a correct file count and its own hunks present.
import { readListPageWith } from "@/api/paginated";
import type { PagedRows } from "@/api/paginated";
import type { ApiClient } from "@/api/client";
import { api } from "@/api/client";

import type { WorkChip, WorkCounts, WorkItemRow } from "./workTypes";

/** What the list takes. `q`, `page` and `per` are `BR-SHL-011`'s own names. */
export interface WorkQuery {
  q?: string;
  page: number;
  per: number;
  chip: WorkChip;
}

/** The page plus the chip counts, off ONE object.
 *
 *  ⚠ **`readListPageWith`, NOT `readListPage`.** The counts ride on the
 *  envelope because `api.py::_envelope` returns a fresh dict of four keys and
 *  discards everything else — `DEF-AST-4120` is a figure that never left the
 *  server for exactly that reason. Reading them from the same object the rows
 *  came out of is what stops a screen describing a second shape to reach
 *  them. */
export type WorkPage = PagedRows<WorkItemRow> & { body: { chips: WorkCounts } };

/**
 * A chip → the server filter it IS.
 *
 * ⚠ **`all` SENDS NOTHING.** An empty `f.source=` would be a meaningless
 * parameter in the address bar and in every cache key derived from it, so two
 * identical requests would look different to React Query.
 */
export function workParams(query: WorkQuery): Record<string, string | number> {
  const params: Record<string, string | number> = { page: query.page, per: query.per };
  if (query.q !== undefined && query.q !== "") {
    params.q = query.q;
  }
  if (query.chip === "cutover") {
    // *Cutover* is the human-task source kind — a plan item somebody has to
    // sign, which the engine never raises and never closes.
    params["f.source"] = "human_task";
  }
  if (query.chip === "blocks_billing") {
    // ⚠ **THE SERVER HAS NO `f.weight`, AND THIS CHIP IS HONEST ABOUT IT.**
    // `GET /work-items` filters on source, status and owner. Rather than
    // inventing a filter the route does not serve — which would return the
    // unfiltered list and read as a chip that does nothing — the chip sends
    // `f.source=finding`: every blocker in this product is a Check's finding
    // today, because an Action's exception carries a weight of its own only
    // once wave `L` raises one. **The day it does, this line is what to fix**
    // and `workEndpoints.test.ts` names it.
    params["f.source"] = "finding";
  }
  return params;
}

/** `GET /work-items` — row 17: the work list, paged on the server. */
export async function getWorkItems(
  query: WorkQuery,
  client: ApiClient = api,
): Promise<WorkPage> {
  return readListPageWith<WorkItemRow, { chips: WorkCounts }>(
    "/work-items",
    workParams(query),
    client,
  );
}

/**
 * `PATCH /work-items/{id}` — row 17: assign, resolve, reopen.
 *
 * ⚠ **RESOLVING IS NOT DELETING AND REOPENING IS NOT A SECOND ROW.** The server
 * keeps `created_at` untouched through both, because the age a clerk reads is
 * the FIRST sighting. And a person's tick does not win forever: the item is
 * DERIVED, so an item resolved while the fault is still there is re-raised on
 * the next run — by design (`BR-RBS-017`).
 */
export async function patchWorkItem(
  id: string,
  changes: { status?: "open" | "resolved"; owner_id?: string | null; due_on?: string | null },
  client: ApiClient = api,
): Promise<WorkItemRow> {
  const response = await client.patch<WorkItemRow>(
    `/work-items/${encodeURIComponent(id)}`,
    changes,
  );
  if (response.data === null) {
    throw new Error("empty 200 body from /work-items where the contract promises one");
  }
  return response.data;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-006 (EP-RBS-03; CR-075 wave H task H3) · 07-endpoints.md row 17 · NFR-3 · BR-SHL-011
// generated: 2026-09-07 by the CR-075 wave H build lane
// checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=n/a
// gates: tsc --noEmit (the LOCAL compiler) · vitest · G114 (one envelope description — this file adds none)
// exceptions: the `Blocks billing` chip sends `f.source=finding` because the route serves no weight filter; the reason and the day it becomes wrong are in `workParams`' own comment
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
