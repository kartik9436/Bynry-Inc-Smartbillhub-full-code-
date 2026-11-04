// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-003 (EP-RBS-01) — CR-075 wave D task D2. Screens: RBS-001.
// Rules:   B14 rule 31 (no database id is ever the visible value of a field) ·
//          B14 rule 32 (one sentence per section; no rule id or internal code
//          in clerk-facing copy) · B14 rule 33 (a FACT is at most six words;
//          RATIONALE is zero words on screen) · A12 (a status tone is status
//          MEANING, never decoration) · NFR-3 / NFR-5 (the totals are the
//          server's own `count`, never `rows.length`)
// Defects: DEF-RBS-4304 (two of the strip's four tiles have no total anywhere) ·
//          DEF-RBS-4327 (the run list serves no verdict) · DEF-RBS-4289 (there
//          is no Draft run status, and the frame draws one)
// Tests:   src/features/runbooks/home/runbooksHomeModel.test.ts
// Impacts: src/features/runbooks/home/RunbooksHome.tsx ·
//          src/features/runbooks/home/homeHoldExpiry.test.tsx (reads
//          HELD_DESTINATIONS as data)
// ───────────────────────────────────────────────────────
/**
 * Everything `RBS-001` decides that does not need a DOM.
 *
 * Kept out of the component so a test can assert a RULE — a tone, a word count,
 * a null that must stay a dash — rather than an impression of a rendered page.
 */
import type { RunRow } from "./homeEndpoints";
import { RUN_STATUS } from "./homeEndpoints";

/** A12 §Semantic tokens — the tones `StatusPill` accepts. */
export type Tone = "success" | "warning" | "danger" | "info" | "neutral" | "muted";

// ══════════════════════════════════════════════════════════════════════════
// THE KPI STRIP — FOUR TILES, AND ONLY TWO OF THEM HAVE A SOURCE
// ══════════════════════════════════════════════════════════════════════════
/**
 * One tile. `value === null` means **this product does not count this yet** and
 * the tile draws a dash with a four-word line saying so.
 *
 * ⚠ **A NULL HERE IS NOT A ZERO AND THE TWO MUST NEVER COLLAPSE.** A confident
 * `0` under *Block billing* reads as *nothing is stopping the bill run*, which
 * is the most dangerous sentence this screen could print. `RulesPage` made the
 * same distinction for the same reason (`DEF-WRK-4096`): a zero we cannot stand
 * behind is drawn as a dash, which in this product means *there is no such
 * thing here* rather than *none*.
 */
export interface HomeKpi {
  id: "blockBilling" | "waitingForYou" | "runningNow" | "ranCleanToday";
  labelKey: string;
  value: number | null;
}

/**
 * The four tiles `RBS-001.1` region 2 draws, in the frame's own order.
 *
 * ⚠ **TWO OF THE FOUR HAVE NO TOTAL ANYWHERE AND THAT IS `DEF-RBS-4304`,
 * FILED BEFORE THIS FUNCTION WAS WRITTEN.**
 *
 *   *Waiting for you* and *Running now* are the envelope `count` of
 *   `GET /runbooks/runs` filtered to `awaiting_approval` and to `running`.
 *   Both are true tenant totals computed in SQL, not page lengths.
 *
 *   *Block billing* is a count of open work items that stop a bill run. The
 *   only work-item figure the module serves is `open_items` PER RUNBOOK on the
 *   current page of `GET /runbooks` — a page total, and summing one on the
 *   client is exactly the aggregation `NFR-3` exists to refuse.
 *
 *   *Ran clean today* needs *done today AND found nothing*. `status=done` is
 *   equally true of the run that found three blockers, so the nearest servable
 *   figure is a different fact wearing the same label — the shape nobody
 *   re-checks.
 *
 * The tiles stay on screen because the task that ordered this screen says so:
 * make the absence visible rather than inventing a number or quietly dropping a
 * tile.
 */
export function homeKpis(totals: { awaitingApproval: number; running: number }): HomeKpi[] {
  return [
    { id: "blockBilling", labelKey: "runbooks.home.kpi.blockBilling", value: null },
    {
      id: "waitingForYou",
      labelKey: "runbooks.home.kpi.waitingForYou",
      value: totals.awaitingApproval,
    },
    { id: "runningNow", labelKey: "runbooks.home.kpi.runningNow", value: totals.running },
    { id: "ranCleanToday", labelKey: "runbooks.home.kpi.ranCleanToday", value: null },
  ];
}

// ══════════════════════════════════════════════════════════════════════════
// STATUS AND KIND — WORDS AND TONES, NEVER THE STORED CODE
// ══════════════════════════════════════════════════════════════════════════
/**
 * A run's status → its tone. **Status MEANING, never decoration** (A12).
 *
 * `running` and `queued` are `neutral` — nothing is wrong and nothing is owed.
 * `awaiting_approval` is `warning` because a person is being waited on.
 * `failed` is `danger`; `stopped` is `muted`, which in this kit means *this is
 * over*; `done` is `success`.
 *
 * ⚠ **`done` IS NOT A VERDICT.** A done run that found three blockers is done.
 * The frame draws *3 blockers* here and that sentence lives in the frozen
 * report, not on the list row — `DEF-RBS-4327`. This function answers what the
 * run DID, and the screen does not pretend otherwise.
 */
export function statusTone(status: string): Tone {
  switch (status) {
    case RUN_STATUS.done:
      return "success";
    case RUN_STATUS.failed:
      return "danger";
    case RUN_STATUS.awaitingApproval:
      return "warning";
    case RUN_STATUS.stopped:
      return "muted";
    case RUN_STATUS.approved:
    case RUN_STATUS.acting:
      return "info";
    default:
      return "neutral";
  }
}

/** The catalogue key for a status word. An unknown status falls back to itself
 *  through `defaultValue` at the call site — never to a guessed word. */
export function statusKey(status: string): string {
  return `runbooks.home.status.${status}`;
}

/** `check` → info, `action` → danger. `RBS-002`'s own pairing, kept identical
 *  so one word does not carry two colours across two screens. */
export function kindTone(kind: string): Tone {
  return kind === "action" ? "danger" : "info";
}

export function kindKey(kind: string): string {
  return `runbooks.home.kind.${kind}`;
}

// ══════════════════════════════════════════════════════════════════════════
// HOW LONG IT TOOK
// ══════════════════════════════════════════════════════════════════════════
/**
 * `took_seconds` → the frame's own spelling: `12s`, `2s`, `1m 04s`, `4m 02s`.
 *
 * `null` when the run has not finished — the caller draws a dash. A run in
 * flight has no duration, and printing the seconds so far would be a number
 * that changes meaning between two reads of the same page.
 *
 * ⚠ **NO LOCALE ENTRY, DELIBERATELY.** `12s` and `1m 04s` are the same in every
 * catalogue this product ships, and a key per unit would be eleven translations
 * of a letter. A duration that ever needs words is a duration that has stopped
 * being a cell (B14 rule 32).
 */
export function formatTook(seconds: number | null): string | null {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) {
    return null;
  }
  const whole = Math.round(seconds);
  if (whole < 60) {
    return `${whole}s`;
  }
  const minutes = Math.floor(whole / 60);
  const rest = whole % 60;
  return `${minutes}m ${String(rest).padStart(2, "0")}s`;
}

// ══════════════════════════════════════════════════════════════════════════
// THE PAGE HEAD'S THREE DOORS — ONE OPEN, TWO HELD, ALL THREE AS DATA
// ══════════════════════════════════════════════════════════════════════════
/**
 * One of `RBS-001.1` region 1's three `Verb →` actions (B14 rule 4).
 *
 * ⚠ **THE WHOLE REASON THIS IS DATA AND NOT THREE `disabled` ATTRIBUTES:** a
 * hold is a rule with a CLOCK in it. `DEF-CWP-3925` is what happens when nobody
 * winds it — the customer portal's front page had **two working doors out of
 * eight**, five cards and the sign-in bar still refusing over screens that had
 * shipped days earlier, with `tsc`, 42 test files, 391 cases and every gate
 * green over it. `homeHoldExpiry.test.tsx` reads THESE lists and fails in both
 * directions: when a held screen appears, and when an open door stops working.
 *
 * `screen` is the id the destination stamps on its own root
 * (`data-screen="…"`, the convention `RunbookSetup.tsx` and 72 portal files
 * follow). `path` is the address — and the expiry test does not trust it alone,
 * because law 7 records a hold-expiry test that asserted a screen was
 * registered at an address while the router mounted it elsewhere, with every
 * check green.
 */
export interface HeadDestination {
  id: "templates" | "history" | "workList";
  /** The screen id the destination carries, or will carry. */
  screen: string;
  /** Tenant-relative address. */
  path: string;
  /** The button's label, in the clerk's own words. */
  labelKey: string;
}

/** @deprecated name kept while nothing else imports it — see `HeadDestination`. */
export type HeldDestination = HeadDestination;

/**
 * **THE DOOR THAT OPENS.** `RBS-002`, the template library, landed the same day
 * as this screen (`CR-075` wave D task `D3`) at `runbooks/templates`, and this
 * button was released in the commit that first met it.
 *
 * ⚠ **THIS LIST WAS EMPTY AND `templates` WAS IN `HELD_DESTINATIONS` FOR THE
 * FIRST DRAFT OF THIS FILE.** The hold-expiry test went red on the merge — it
 * found `data-screen="RBS-002"` in `features/runbooks/library/` and named this
 * button — which is precisely what a hold-expiry test is for and precisely what
 * did NOT happen on the customer portal's front page.
 *
 * ⚠ **AND THE ORDER MATTERS: A STATIC SEGMENT BEATS `:key`.** `App.tsx` mounts
 * `runbooks/:key` for `RBS-004`, and React Router v6 ranks by specificity, so
 * the DECLARED `runbooks/templates` wins wherever it sits in the array. Before
 * it was declared, this address opened the setup screen for *the runbook whose
 * key is templates* — `integrations/subprocessors` exactly, which shipped and
 * answered 405 under a comment asserting the collision away.
 */
export const OPEN_DESTINATIONS: readonly HeadDestination[] = [
  {
    id: "templates",
    screen: "RBS-002",
    path: "/runbooks/templates",
    labelKey: "runbooks.home.action.templates",
  },
  // ⚠ **RELEASED 2026-09-07, IN THE COMMIT THAT LANDED THE SCREEN IT WAS
  // HOLDING** (`CR-075` wave I task `I6`). `RBS-008` is declared, routed at
  // `/{tenant}/runbooks/runs` and tested. Hard-won law 2's mirror is that
  // landing a screen and releasing the control that points at it are TWO acts
  // and only the first feels like the work — which cost the customer portal six
  // of its eight front-page doors with `tsc`, 391 cases and every gate green
  // (`DEF-CWP-3925`). `homeHoldExpiry.test.tsx` is the clock that fired here,
  // and its assertions were TURNED AROUND rather than deleted.
  {
    id: "history",
    screen: "RBS-008",
    path: "/runbooks/runs",
    labelKey: "runbooks.home.action.history",
  },
  // ⚠ **RELEASED 2026-10-02, TWENTY-FIVE DAYS LATE.** `RBS-007` landed on
  // 2026-09-07 in `df1ade52e` (`CR-075` waves G and H) — declared in
  // `features/runbooks/work/WorkList.tsx` and routed at `runbooks/work` — and
  // this button stayed a disabled *Work list →* over a working screen. The
  // hold-expiry test went red that morning, naming this entry, and was not
  // read: law 7's *proved red, then never read*, on top of law 2's mirror.
  {
    id: "workList",
    screen: "RBS-007",
    path: "/runbooks/work",
    labelKey: "runbooks.home.action.workList",
  },
];

/**
 * **NONE HELD TODAY.** A head action whose screen is not built goes here and
 * draws as a disabled button carrying its reason (`BR-SHL-025`), never hidden;
 * `homeHoldExpiry.test.tsx` is the clock on every entry.
 *
 * ⚠ **THIS LIST HELD TWO UNTIL 2026-09-07 AND ONE UNTIL 2026-10-02.** *History →*
 * left it the day `RBS-008` landed. *Work list →* should have left it the same
 * day `RBS-007` did (2026-09-07, `df1ade52e`) and left it twenty-five days late.
 */
export const HELD_DESTINATIONS: readonly HeadDestination[] = [];

/**
 * The three, in the frame's own order — Templates → · History → · Work list →.
 *
 * The screen renders THIS, so a released hold changes which tier a button draws
 * in and never its position: a clerk who learned where *History →* sits does
 * not have to learn again the week it starts working.
 */
export const HEAD_DESTINATIONS: readonly HeadDestination[] = [
  ...OPEN_DESTINATIONS,
  ...HELD_DESTINATIONS,
];

/** Is this head action live today? Read by the screen and by its expiry test. */
export function isOpen(id: HeadDestination["id"]): boolean {
  return OPEN_DESTINATIONS.some((open) => open.id === id);
}

/**
 * The address of one run's result — `RBS-006`, which IS built and IS routed.
 *
 * Built here where the tenant slug is known rather than handed to a renderer as
 * a key for it to guess at. A component mounted without its route pattern gets
 * `undefined` from `useParams()` and produces `//host/…`, a protocol-relative
 * URL to another host that reads as a perfectly good string to `toContain`
 * (`DEF-CWP-3925`) — which is why the DOM tests mount under the real pattern.
 */
export function runResultPath(tenant: string, row: RunRow): string {
  return `/${tenant}/runbooks/${encodeURIComponent(row.runbook_key)}/runs/${encodeURIComponent(row.id)}`;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-003 (EP-RBS-01; CR-075 wave D task D2)
// generated: 2026-09-06 by the CR-075 wave D task D2 build lane
// checklist: A✔ B✔ C✔ D=n/a(no endpoint) E✔ F✔ G✔ H=n/a(no 🔒 path)
// gates: tsc✔ (the LOCAL compiler) · vitest (runbooksHomeModel.test.ts, homeHoldExpiry.test.tsx)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
