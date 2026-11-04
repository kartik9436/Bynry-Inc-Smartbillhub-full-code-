// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-003 (EP-RBS-01) — CR-075 wave D task D2, the reads RBS-001
//          makes. Screens: RBS-001 (`S147`).
// Rules:   `07-endpoints.md` row 8 — `GET /runbooks/runs`, *"history across
//          runbooks, filterable by runbook, category, outcome and date"* ·
//          `BR-SHL-011` (the `q` / `page` / `per` / `f.<name>` grammar) ·
//          `NFR-3` (every list pages server-side, `per` clamped
//          50/100/200/500/1000) · `NFR-5` (no cap anywhere) · B14 rule 31
//          (an id is linked with, never drawn)
// Defects: DEF-RBS-4305 (the outcome filter takes ONE status, so neither of
//          this screen's two tables is a single query) · DEF-WRK-4119 /
//          DEF-AST-4120 (three screens drew empty tables over rows the server
//          had returned, because each described the reply by hand)
// Tests:   src/features/runbooks/home/homeEndpoints.test.ts (the served shape,
//          against a reply RECORDED from the running server — never invented)
// Impacts: src/features/runbooks/home/RunbooksHomePage.tsx
// ───────────────────────────────────────────────────────
/**
 * The three reads `RBS-001` makes, and why there are three rather than one.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * NOTHING HERE DESCRIBES THE LIST ENVELOPE, AND THAT IS THE POINT
 * ══════════════════════════════════════════════════════════════════════════
 * Every call goes through `readListPage`, which is the ONE description of
 * `{count, next, previous, results}` in this repository and asserts it at
 * runtime. Three shipped Work screens drew empty tables over rows the API had
 * returned because each had transcribed the SELECTOR's dict — `rows`/`total` —
 * which is a perfect description of the layer below the boundary and a complete
 * fiction about the wire. A screen here never sees either name.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHY THREE READS — `DEF-RBS-4305`, FILED BEFORE THIS FILE WAS WRITTEN
 * ══════════════════════════════════════════════════════════════════════════
 * `GET /runbooks/runs` filters `f.outcome` to **one** status: `runs_page`
 * writes `if outcome in RUN_OUTCOMES`, and `RUN_OUTCOMES` is the eight bare
 * words, so a comma list or a repeated param falls outside the vocabulary and
 * the list comes back **unfiltered, with a 200**. The screen draws two sets the
 * filter cannot express — *needs a person* is queued · running ·
 * awaiting_approval · approved · acting, and *finished* is done · failed ·
 * stopped.
 *
 * So each read asks for exactly one thing it can actually ask for:
 *
 *   `awaitingApproval` → the **Needs you** table, and the *Waiting for you*
 *                        tile is its `total`. One paged list, one footer.
 *   `running`          → the **in-flight banner** (`RBS-001.3`), and the
 *                        *Running now* tile is its `total`. The banner names
 *                        the newest; the tile carries the true count, so a
 *                        second run in flight is never hidden without a number.
 *   `history`          → **Finished recently**: the unfiltered history, newest
 *                        first, server-paged, with the footer `RBS-001.1`
 *                        draws. Today only `running`, `done` and `failed` are
 *                        ever written (`services.open_run` opens at `running`,
 *                        `close_run` lands on `done` or `failed`), so this is
 *                        the finished runs plus a run that is executing at the
 *                        instant of the read. When wave L starts writing
 *                        `awaiting_approval` and `stopped` it becomes
 *                        `f.outcome=done,failed,stopped` — the one line that
 *                        changes here when `DEF-RBS-4305` is fixed.
 *
 * ⚠ **NONE OF THE THREE SORTS OR SLICES ON THE CLIENT.** `runs_page` orders on
 * `(-started_at, -created_at, -id)` and slices in SQL. Four endpoints in this
 * product already page in Python behind a comment naming the old 3,000-account
 * ceiling — correct at the bottom tier and 13× short of the top of the one we
 * sell to (`DEF-PAY-4221`). This screen does not join them: `per` travels, the
 * server clamps it, and the totals in the strip are the server's own `count`
 * rather than `rows.length`.
 */
import { readListPage } from "@/api/paginated";
import type { ApiClient } from "@/api/client";
import type { PagedRows } from "@/api/paginated";

/** `GET /runbooks/runs`, the list path — written once. */
const RUNS_PATH = "/runbooks/runs";

/**
 * One row of `GET /runbooks/runs`, exactly as `selectors._run_row` builds it.
 *
 * ⚠ **`id` IS HERE TO BE LINKED WITH AND IS NEVER DRAWN** (B14 rule 31). A run
 * has no natural key and `/runbooks/{key}/runs/{id}` is its address; what a
 * clerk reads is `runbook_name`, which the selector always populates, so there
 * is no branch in which an id becomes the visible value.
 *
 * ⚠ **`counts` IS THE RUNBOOK AUTHOR'S OWN VOCABULARY AND IS NOT RENDERED**
 * (`DEF-RBS-4327`). Its keys come from `RecordOutcome.outcome`, chosen per
 * definition in Python, plus the engine's `failed` and `skipped` — so drawing
 * them would print an untranslated internal word into a cell, which is B14
 * rule 31 and rule 35 at once. The type carries the field because the server
 * sends it; nothing below reads it.
 */
export interface RunRow {
  id: string;
  runbook_key: string;
  runbook_name: string;
  kind: string;
  category: string;
  version: number;
  mode: string;
  trigger: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  took_seconds: number | null;
  counts: Record<string, number>;
  records: number;
  by: { trigger: string; person: string | null };
}

/** The statuses this screen names, as data — read by the model and its tests. */
export const RUN_STATUS = {
  queued: "queued",
  running: "running",
  awaitingApproval: "awaiting_approval",
  approved: "approved",
  acting: "acting",
  done: "done",
  failed: "failed",
  stopped: "stopped",
} as const;

/**
 * The **Needs you** page — the runs waiting for a person to approve them.
 *
 * ⚠ **IT IS EMPTY ON EVERY TENANT TODAY AND THAT IS A FACT ABOUT THE PRODUCT,
 * NOT ABOUT THIS CALL.** Nothing writes `awaiting_approval` until wave L binds
 * the acting half; `services.open_run` opens a run at `running` and
 * `close_run` lands it on `done` or `failed`. The section therefore renders its
 * own empty state rather than being hidden, because a section that disappears
 * cannot be distinguished from one that was never built.
 */
export function listRunsAwaitingApproval(
  query: { page: number; per: number },
  client?: ApiClient,
): Promise<PagedRows<RunRow>> {
  return readListPage<RunRow>(
    RUNS_PATH,
    { "f.outcome": RUN_STATUS.awaitingApproval, page: query.page, per: query.per },
    client,
  );
}

/**
 * The runs in flight — `RBS-001.3`'s banner, and the *Running now* tile.
 *
 * `per` is the smallest the server will clamp to (50) because the banner draws
 * ONE run; the tile reads `total`, which is the whole tenant's count and not
 * this page's length.
 */
export function listRunsInFlight(
  client?: ApiClient,
  per = 50,
): Promise<PagedRows<RunRow>> {
  return readListPage<RunRow>(
    RUNS_PATH,
    { "f.outcome": RUN_STATUS.running, page: 1, per },
    client,
  );
}

/**
 * **Finished recently** — the history, newest first, server-paged.
 *
 * Unfiltered on purpose; see this file's header and `DEF-RBS-4305`. The one
 * line that changes when that defect is fixed is the query below.
 */
export function listRunHistory(
  query: { page: number; per: number },
  client?: ApiClient,
): Promise<PagedRows<RunRow>> {
  return readListPage<RunRow>(RUNS_PATH, { page: query.page, per: query.per }, client);
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-003 (EP-RBS-01; CR-075 wave D task D2; 07-endpoints.md row 8 quoted verbatim)
// generated: 2026-09-06 by the CR-075 wave D task D2 build lane
// checklist: A✔ B✔ C✔ D✔ E=n/a(no screen in this file) F✔ G✔ H=n/a(no 🔒 path)
// gates: tsc✔ (the LOCAL compiler) · vitest (homeEndpoints.test.ts) · G114 (one envelope description — this file adds none)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
