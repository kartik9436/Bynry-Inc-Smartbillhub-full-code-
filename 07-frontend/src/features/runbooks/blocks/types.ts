// ── Trace ──────────────────────────────────────────────
// Story:    US-RBS-016 (EP-RBS-01) — CR-075 wave C task C1b.
//           Screens: RBS-006 (the result renderer) · RBS-004 (the setup renderer)
// Rules:    `BR-RBS-021` (a thirteenth block needs THREE runbooks that cannot be
//           drawn without it) · `BR-RBS-020` (the report is composed at close and
//           FROZEN) · B14 rule 36 · B14 rule 31 (no database id is ever the
//           visible value of a field) · CLAUDE.md hard rule 2 (money 2, percent
//           2) · hard rule 3 (a quantity carries its unit)
// Tests:    src/features/runbooks/blocks/blocks.test.tsx
// Impacts:  06-backend/apps/runbooks/contract.py (`BLOCK_TYPES`, the one place
//           the twelve names are minted) ·
//           04-docs/05-modules/17-runbooks/09-component-inventory.md Part 1
// ───────────────────────────────────────────────────────
//
// **THE TWELVE SHAPES. THE BACKEND DELIBERATELY DOES NOT DECLARE THEM.**
// `contract.py`'s `Block` says so in its own docstring: *"`payload` is whatever
// that block draws and is deliberately untyped here: the twelve shapes are the
// renderer's (wave C), and typing them in the backend would mean two
// declarations of one thing that can disagree. What is typed is the NAME."*
// This file is the other half of that decision — the names are mirrored from
// `BLOCK_TYPES` and a test asserts the two lists agree, so neither can drift.
//
// ⚠ **THIS IS WHY THIRTY-FOUR RUNBOOKS NEED NO NEW SCREEN.** `RB-020`: adding
// runbook 23 is one Python module and no frontend code, because its report is a
// composition of these twelve and nothing else. That claim only survives while
// the list is CLOSED — `BR-RBS-021`, *"a thirteenth block needs THREE runbooks
// that cannot be drawn without it"*, and the moment it grows per request the
// renderer becomes a UI language and every future runbook becomes a support
// question about it.
//
// ⚠ **EVERY VALUE CARRIES ITS KIND, AND THAT IS THE POINT.** A report row is
// not a bag of strings: each cell says what it IS, so the renderer picks
// `MoneyCell` for money, `PercentCell` for a percentage and `UnitCell` for a
// quantity without any screen deciding. `09-component-inventory.md` names the
// failure this avoids: *"A screen that formats both with one helper is wrong in
// one of the two directions on every row."*
import type { PercentBasis, PercentDirection } from "@/components/PercentCell";
import type { SparklineSource } from "@/components/Sparkline";
import type { StatusTone } from "@/components/StatusPill";
import type { VerdictTone } from "@/components/VerdictBand";
import type { ChainCellState } from "@/components/Chain";
import type { OutcomeTone } from "@/components/OutcomeCard";
import type { RecordGridState } from "@/components/RecordGrid";

/** The twelve, in `contract.py`'s own order. `blocks.test.tsx` asserts this
 *  list and `BLOCK_TYPES` agree name for name — two declarations of one thing
 *  that CAN disagree are kept from disagreeing by a test, because there is no
 *  way to share a tuple across Python and TypeScript. */
export const BLOCK_TYPES = [
  "verdict",
  "kpis",
  "chain",
  "records",
  "breakdown",
  "reconciled",
  "ranked",
  "sentence",
  "facts",
  "action",
  "row_decisions",
  "downloads",
] as const;

export type BlockName = (typeof BLOCK_TYPES)[number];

/* ── the cell vocabulary ──────────────────────────────────────────────────
 * Eight kinds, and each exists because a screen would otherwise format it by
 * hand. `text` is the default and carries no meaning beyond "words".
 * ────────────────────────────────────────────────────────────────────────── */

export type ReportValue =
  /** Words the server already chose, in the reader's language. */
  | { kind: "text"; text: string }
  /** A status. The tone is the server's; `StatusPill` never knows a domain
   *  status, so a new status never needs a new pill. */
  | { kind: "pill"; label: string; tone: StatusTone }
  /** Money — 4 stored, 2 shown, currency riding WITH the amount (hard rule 2). */
  | { kind: "money"; amount: string; currency: string }
  /** A quantity — hard rule 3, the unit is not optional here either. */
  | { kind: "unit"; quantity: string; unit: string }
  /** A tariff RATE — 6 stored, **4** shown at most, 2 at least (`OQ-620` as narrowed 2026-10-02). Deliberately
   *  its own kind and not `money`: `$0.0025 / kWh` prints `$0.00` if rounded to
   *  two, beside a real charge. */
  | { kind: "rate"; rate: string; currency: string }
  /** A percentage — 6 stored, 2 shown, and the CONVENTION is required because
   *  the product stores both fractions and percent points. */
  | { kind: "percent"; value: string; basis: PercentBasis; direction?: PercentDirection; signed?: boolean }
  /** A date or an instant. The tenant's zone and format arrive from the shell,
   *  not from the payload — one formatting path (`BR-SHL-023`). */
  | { kind: "date"; value: string; withTime?: boolean }
  /** Twelve months in a cell. The label carries the unit (hard rule 3). */
  | { kind: "sparkline"; points: number[]; label: string; source?: SparklineSource; markAt?: number }
  /** A fix route — *Set a tax region →*. `RBS-006-R1`'s last column, and the
   *  reason `TC-RBS-14` can scan for a failure reason with no way to act on it. */
  | { kind: "link"; label: string; to: string };

/** One declared column of a tabular block. `label` is the header a reader sees
 *  and arrives pre-translated, exactly as `TableColumnConfig` requires. */
export interface ReportColumn {
  key: string;
  label: string;
  numeric?: boolean;
  sortable?: boolean;
}

/** One row. `id` is React's key and is NEVER rendered — B14 rule 31. */
export interface ReportRow {
  id: string;
  cells: Record<string, ReportValue>;
  /** Facts the row CARRIES and no block DRAWS.
   *
   *  ⚠ **THIS IS NOT A HIDDEN COLUMN AND IT MUST NOT BECOME ONE.** A renderer
   *  walks `columns`, so nothing here can reach a screen by accident — which is
   *  the point: `decided_by_rule` names the rule a finding came from, and B14
   *  rule 32 forbids a rule id in clerk-facing copy, while `TC-RBS-14` and the
   *  findings CSV both need it. Dropping it to keep the row tidy would lose the
   *  trace from the only artefact that is frozen (`BR-RBS-020`).
   *
   *  Added with `DEF-RBS-4284`, when the engine moved to these shapes: the flat
   *  rows it used to emit carried `service` and `decided_by_rule`, and a
   *  five-column row would have silently dropped both. */
  meta?: Record<string, string | null>;
}

/* ── the twelve payloads ───────────────────────────────────────────────── */

/** 1 · Verdict — one bold word, a count line, a detail line. */
export interface VerdictPayload {
  word: string;
  tone: VerdictTone;
  count: string;
  detail?: string;
}

/** 2 · KPIs — tiles: value, label, tone. A money tile carries its basis, which
 *  `KpiTile` already makes required, so no unlabeled money number ships. */
export interface KpisPayload {
  tiles: {
    id: string;
    label: string;
    value: ReportValue;
    detail?: string;
    /** The date basis for a MONEY tile, labelled beside the figure
     *  (`BR-REP-001`: no unlabelled money number anywhere).
     *
     *  ⚠ **THIS TRAVELS IN THE PAYLOAD BECAUSE `KpisBlock` USED TO HARDCODE
     *  `"posting"` FOR EVERY MONEY TILE — `DEF-RBS-4350`.** So the test bill,
     *  which prices an account and writes nothing at all, drew its total under
     *  **Posting date**, two inches above its own sentence saying *"Nothing was
     *  written and no bill number was used"*. Both halves were correct
     *  decisions on their own — the block needed a basis, and `BR-REP-001`
     *  makes one required — and neither had anything to check against, because
     *  no runbook drew a money tile until wave F.
     *
     *  Ignored on a tile that is not money. Absent on a money tile it still
     *  falls back to `"posting"`, and that fallback is a KNOWN GAP rather than
     *  a default anybody chose: `test_us_rbs_015_conformance.py` asserts that
     *  every money tile in every shipped runbook declares one, so the fallback
     *  is unreachable for anything on the branch and a new runbook that omits
     *  it goes red naming itself. */
    basis?: import("@/components/MoneyCell").MoneyBasis;
  }[];
}

/** 3 · Chain — ordered steps; a red cell NAMES the blocker and a never-reached
 *  cell says so rather than sitting blank (`RB-036`, `BR-RBS-027`). */
export interface ChainPayload {
  label: string;
  cells: { id: string; position: number; label: string; state: ChainCellState; note?: string }[];
}

/** 4 · Records — the per-record table, and **its grid display mode**.
 *
 *  ⚠ `display` is what makes the coverage grid need no new screen: it is the
 *  SAME block, drawn as cells. `10-execution-plan.md` C1a — *"phase 2's coverage
 *  grid IS that grid mode"*. */
export interface RecordsPayload {
  display?: "table" | "grid";
  columns: ReportColumn[];
  rows: ReportRow[];
  total: number;
  /** Grid mode only: which column holds the cell's label, which holds its
   *  state, and where a cell opens. */
  grid?: {
    labelKey: string;
    stateByRowId: Record<string, RecordGridState>;
    linkKey: string;
    reasonKey?: string;
  };
  /** B14 rule 17 — what is missing and what fills it. */
  empty: { title: string; helper: string };
  /** Chips: *All 9* · *Blockers 3* · *Warnings 6* (`RBS-006-R1` region 4). */
  chips?: { id: string; label: string; count: number }[];
}

/** 5 · Breakdown — group-by with counts: by class, tier, source, channel, type. */
export interface BreakdownPayload {
  heading: string;
  columns: ReportColumn[];
  rows: ReportRow[];
}

/** 6 · Reconciled — ours · theirs · difference, with a ties mark.
 *
 *  ⚠ The two column headings are **Recorded** and **In the books** — B14 rule 34,
 *  *the one pair of words for held here and in the books, in all eleven
 *  catalogues* (`CR-060` C11). They arrive pre-translated in `columns`. */
export interface ReconciledPayload {
  heading: string;
  columns: ReportColumn[];
  rows: ReportRow[];
  /** Which rows tie. A tie is a MARK, not an absence — `RBS-006-R9` draws a
   *  `Ties` pill rather than an empty difference cell. */
  tiesLabel: string;
}

/** 7 · Ranked — label, thin bar, value. Largest first; the ORDER is the
 *  runbook's and this renderer never re-sorts. */
export interface RankedPayload {
  heading: string;
  rows: { id: string; label: string; detail?: string; weight: number; value: ReportValue }[];
}

/** 8 · Sentence — one card: a stop, a find, *read this aloud*, what the
 *  customer receives. */
export interface SentencePayload {
  tone: OutcomeTone;
  label?: string;
  text: string;
}

/** 9 · Facts — label · value list. */
export interface FactsPayload {
  heading?: string;
  rows: { id: string; label: string; value: ReportValue }[];
}

/** 10 · Action — ONE button with a tier and an enabling condition.
 *
 *  ⚠ `enabled: false` REQUIRES `reason`. B14 draws a control a user may not use
 *  as disabled WITH its reason, never hidden — and `RBS-006-R9`'s own caption is
 *  the case: *"Close period stays disabled until this list is empty. It says
 *  why: 3 items open."* A disabled button with no reason is the shape hard-won
 *  law 2's 2026-09-05 mirror is about. */
export type ActionPayload =
  | { label: string; tier: "primary" | "secondary" | "danger"; enabled: true }
  | { label: string; tier: "primary" | "secondary" | "danger"; enabled: false; reason: string };

/** 11 · Row decisions — accept / keep on a records row, each mapping to a port
 *  or an engine act.
 *
 *  ⚠ **TEXT BUTTONS, AND THAT IS A RULED DIVERGENCE FROM B14 RULE 15.**
 *  `09-component-inventory.md` Part 4 §3: rule 15 says row actions are icons,
 *  never text links — and *Accept theirs →* / *Keep ours* are not any of rule
 *  15's nine verbs, so an icon could not carry WHICH of two values is being
 *  kept. The precedent is Integrations, whose `MappingRow` and `DecisionCard`
 *  both ship text buttons. **A DECISION is not a row action**: a Records table
 *  may carry ONE decision column of text buttons where the choice is between
 *  named values. */
export interface RowDecisionsPayload {
  heading: string;
  columns: ReportColumn[];
  rows: ReportRow[];
  /** The choices, in the order drawn. Two on `RBS-006-R20`. */
  choices: { id: string; label: string }[];
}

/** 12 · Downloads — the two result files. */
export interface DownloadsPayload {
  files: { id: string; label: string; format: "csv" | "pdf" }[];
}

/** One block of a frozen report. The union is discriminated by `block`, so
 *  `tsc` refuses a payload that does not match its name and the renderer's
 *  switch is exhaustive without a default arm. */
export type ReportBlock =
  | { block: "verdict"; payload: VerdictPayload }
  | { block: "kpis"; payload: KpisPayload }
  | { block: "chain"; payload: ChainPayload }
  | { block: "records"; payload: RecordsPayload }
  | { block: "breakdown"; payload: BreakdownPayload }
  | { block: "reconciled"; payload: ReconciledPayload }
  | { block: "ranked"; payload: RankedPayload }
  | { block: "sentence"; payload: SentencePayload }
  | { block: "facts"; payload: FactsPayload }
  | { block: "action"; payload: ActionPayload }
  | { block: "row_decisions"; payload: RowDecisionsPayload }
  | { block: "downloads"; payload: DownloadsPayload };

/** What every block component is handed besides its own payload.
 *
 *  ⚠ THE FORMATTING CONTEXT IS PASSED, NEVER LOOKED UP PER BLOCK. `DateCell`
 *  makes the tenant's zone and format REQUIRED (IS-8), and `DEF-SHL-3964` is
 *  what happens when that travels as an optional prop nobody sets: every date in
 *  the product fell through to `MM/DD/YYYY` and `UTC` for weeks, with no crash
 *  and nothing to notice. One context, handed down once by the renderer. */
export interface BlockContext {
  timeZone: string;
  dateFormat: import("@/components/DateCell").RegionalDateFormat;
  locale?: string;
  /** Tenant-relative fix route → the real URL. `tenantPath.ts`'s own rule:
   *  *"Every internal link and redirect in the app goes through this — screens
   *  never write `/${tenant}/…` themselves."*
   *
   *  ⚠ **REQUIRED, AND IT IS REQUIRED BECAUSE IT WAS MISSING — `DEF-RBS-4329`.**
   *  Every runbook emits its fix routes TENANT-RELATIVE, exactly as
   *  `tenancy.selectors.CHECKLIST_TARGETS` does (`settings/services`,
   *  `payments/record`). `ReportValueCell` handed that string straight to
   *  `<Link to>`, and React Router resolves a relative `to` against the CURRENT
   *  route — so from `/:tenant/runbooks/:key/runs/:runId` it produced
   *  `/brazosbend/runbooks/cash-application/runs/<id>/payments/record` and every
   *  Fix link on every runbook landed on *"This screen is not built yet."*
   *  `BR-RBS-011` says a failure NAMES ITS FIX ROUTE, and one that opens onto
   *  "not built yet" has not.
   *
   *  It is PASSED rather than looked up with `useTenantPath()` inside the cell,
   *  for the reason `GlobalSearchResults` gives for the same prop: the component
   *  then needs no router context of its own to be unit-tested. And it is
   *  REQUIRED rather than optional because `DEF-SHL-3964` is what this same
   *  context costs when a formatting fact travels as an optional prop nobody
   *  sets — hard-won law 2, one field up. */
  toHref: (path: string) => string;
}
