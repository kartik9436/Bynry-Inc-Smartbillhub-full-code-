// ── Trace ──────────────────────────────────────────────
// Story:  US-RBS-007 (EP-RBS-03) — CR-075 wave I task I6.
// Screens: RBS-008 Run history at `/{tenant}/runbooks/runs`.
// Rules:  `07-endpoints.md` row 8 — `GET /runbooks/runs`, *"history across
//         runbooks, filterable by runbook, category, outcome and date"* ·
//         `NFR-3` (universal server pagination) · `BR-SHL-011` (the `f.<name>`
//         filter grammar; an unknown value falls back to unfiltered and a list
//         URL never 4xx's over its own params).
// Defects: DEF-RBS-4305 (the home's *Finished recently* is unfiltered — this
//         file is the screen that DOES filter, on the same endpoint).
// Tests:  07-frontend/src/features/runbooks/history/RunHistory.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * `GET /runbooks/runs` for `RBS-008` — the whole history, filtered by the SERVER.
 *
 * ⚠ **THE CHIP ROW IS A SERVER FILTER AND NOT A `.filter()` OVER ONE PAGE.**
 * `08-screen-layouts.md` draws *All · Checks · Actions · Failed · Stopped* and
 * a pager reading *Showing 1–6 of 214*. Those two facts cannot both be true of
 * a client-side filter: page one holds fifty rows and the count belongs to the
 * whole tenant. `CLAUDE.md`'s opening paragraph names four places in this
 * repository where exactly that shortcut was taken and is now a defect
 * (`DEF-PAY-4221`) — correct at three thousand accounts, thirteen times short
 * at forty thousand. Run history is the list most certain to get big: a
 * 40,000-account utility running twelve scheduled runbooks daily writes six
 * figures of rows inside a year.
 *
 * ⚠ **TWO CHIPS FILTER ON `kind` AND TWO ON `outcome`, AND THEY ARE DIFFERENT
 * SERVER PARAMS.** *Checks* and *Actions* are what the runbook IS; *Failed* and
 * *Stopped* are what one run DID. The screen draws them in one row because a
 * clerk thinks of them as one question — *show me the bad ones* — and this file
 * is where that single choice becomes the right two parameters.
 */
import type { ApiClient } from "@/api/client";
import type { PagedRows } from "@/api/paginated";
import { readListPage } from "@/api/paginated";
import type { RunRow } from "../home/homeEndpoints";

/** `GET /runbooks/runs`, the list path — written once. */
const RUNS_PATH = "/runbooks/runs";

/**
 * The five chips the sheet draws, as DATA.
 *
 * Each names the ONE server parameter it moves, so a chip cannot be added
 * without deciding which filter it is — the mistake `DEF-RBS-4310` records on
 * `RBS-003`, where two chips were drawn over a server that filters on neither.
 */
export const HISTORY_CHIPS = [
  { id: "all", param: null, value: null },
  { id: "check", param: "kind", value: "check" },
  { id: "action", param: "kind", value: "action" },
  { id: "failed", param: "outcome", value: "failed" },
  { id: "stopped", param: "outcome", value: "stopped" },
] as const;

export type HistoryChipId = (typeof HISTORY_CHIPS)[number]["id"];

export interface HistoryQuery {
  q: string;
  chip: HistoryChipId;
  page: number;
  per: number;
}

/** The chip → `f.<name>` translation, alone, so a test can read it. */
export function historyParams(query: HistoryQuery): Record<string, string | number> {
  const params: Record<string, string | number> = { page: query.page, per: query.per };
  if (query.q.trim() !== "") {
    params.q = query.q.trim();
  }
  const chip = HISTORY_CHIPS.find((one) => one.id === query.chip);
  if (chip !== undefined && chip.param !== null && chip.value !== null) {
    params[`f.${chip.param}`] = chip.value;
  }
  return params;
}

/**
 * Every run this utility has ever started, newest first.
 *
 * The order is the SERVER's — `-started_at, -created_at, -id`, three keys
 * because `started_at` is nullable and uuid7 is time-ordered only to the
 * millisecond. Nothing here re-sorts, and no column declares `sortable` until
 * `runs_page` is called with `allowed_sorts`.
 */
export function listRunHistoryPage(
  query: HistoryQuery,
  client?: ApiClient,
): Promise<PagedRows<RunRow>> {
  return readListPage<RunRow>(RUNS_PATH, historyParams(query), client);
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-007 (EP-RBS-03; CR-075 wave I task I6) · 07-endpoints.md row 8 · 08-screen-layouts.md RBS-008 · NFR-3
// generated: 2026-09-07 by the CR-075 wave I build lane
// checklist: A✔ B✔ C✔ D✔(GET /runbooks/runs, unchanged) E=n/a(no screen in this file) F✔ G✔ H=n/a
// gates: ./node_modules/.bin/tsc --noEmit (the LOCAL compiler, never npx) · vitest RunHistory.dom.test.tsx
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
