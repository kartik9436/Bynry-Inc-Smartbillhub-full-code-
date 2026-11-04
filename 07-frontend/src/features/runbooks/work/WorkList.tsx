// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-006 (EP-RBS-03) — CR-075 wave H task H3.
// Screens: RBS-007.1 populated · RBS-007.2 all clear (`S153`), at
//          `/{tenant}/runbooks/work`, against
//          `wireframes/RBS-007.1___RBS-007.2.md`.
// Rules:   `NFR-3` (universal server pagination — nothing here slices an
//          array) · `NFR-5` (no caps) · B14 rule 2 (page head) · rule 4 (one
//          primary) · rule 12 (the toolbar's order) · rule 15 (row actions are
//          icons, max 2 + …) · rule 16 (the pagination footer) · rule 17 (an
//          empty list says what is missing and the action that fills it) ·
//          rule 20 (ONE table type) · rule 21 + its PER-FILE migration clause
//          (`features/runbooks/` is a directory entry in
//          `styles/route-b-migrated.txt`, so a file born here is Tailwind) ·
//          rule 31 (no database id is ever the visible value) · rule 32 (a
//          description budget) · rule 33 (a refusal caps at five or six words)
//          · `BR-RBS-011` (a failure names its fix route) · `BR-RBS-017`.
// Tests:   WorkList.dom.test.tsx
// Defects: DEF-CWP-3925 (mount under the REAL path pattern — a component
//          mounted bare gets `undefined` for `:tenant` and builds every
//          address as `//host/…`, which reads as a perfectly good string).
// ───────────────────────────────────────────────────────
//
// **THE SCREEN THE WHOLE MODULE IS FOR, IN ONE SENTENCE FROM `US-RBS-006`:**
// *"I open one screen each morning instead of remembering which of eleven
// runbooks found something."*
//
// ══════════════════════════════════════════════════════════════════════════
// AGE IS THE COLUMN THAT CARRIES THE ARGUMENT
// ══════════════════════════════════════════════════════════════════════════
// *"Thirty daily sweeps over one missing read are ONE item, THIRTY DAYS OLD"* —
// and the age is `created_at`, the FIRST sighting, never the last. A row that
// showed `updated_at` would read *Today* every morning and this screen would
// lose the only number that says a thing has been ignored. The engine
// guarantees the row (`engine/work_items.py` upserts and never re-creates);
// this file draws what that guarantee produces.
//
// ⚠ **AND THE AGE IS DAYS, NOT HOURS AND MINUTES.** The sheet's sample values
// include *3 hours*; anything under a day reads **Today** here instead, because
// eleven languages' plural rules for an hour count is a translation surface
// this screen does not need — the fact it exists to carry is *how many days*.
// The divergence is stamped in `08-screen-layouts.md`; the sheet's own
// acceptance line says sample values are illustrative.
//
// ══════════════════════════════════════════════════════════════════════════
// TWO THINGS THE SHEET DRAWS AND THIS SCREEN DOES NOT, EACH STAMPED
// ══════════════════════════════════════════════════════════════════════════
//   * **`↓ Export`.** `EP-RBS-03`'s capability matrix promises CSV and
//     `07-endpoints.md` row 17 serves none — there is no work-list export route
//     at all. A button over a route that does not exist is hard-won law 2's
//     2026-09-05 mirror (the customer portal had two working doors out of
//     eight), so it is ABSENT rather than drawn dead.
//   * **The `Mine` and `Cutover` chips.** `GET /work-items` filters on
//     `f.source`, `f.status` and `f.owner`. *Cutover* is `f.source=human_task`
//     and IS built; ***Mine* needs the signed-in user's id**, which this screen
//     does not hold — `useTenantRegional` publishes the tenant's display
//     settings and not the viewer's identity. A chip that filtered to somebody
//     else's work would be worse than no chip, so it is absent and the row
//     carries three rather than four. That is `DEF-RBS-4310`'s shape and the
//     same answer that defect got.
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ChipRow, ChipToggle } from "@/components/Chip";
import { DataTable } from "@/components/DataTable";
import { CommitIcon, RollBackIcon, WrenchIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { RowAction, RowActionLink, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";

import type { WorkChip, WorkItemRow } from "./workTypes";

/** The three chips, in the sheet's order. *All* is the absence of a filter, so
 *  it is not a value the server ever receives. */
export const CHIP_ORDER: readonly WorkChip[] = ["all", "blocks_billing", "cutover"];

/** `weight_pill` → the tone `StatusPill` draws. The SERVER names the pill and
 *  this map only colours it, so a fifth weight band added on the far side
 *  arrives with a neutral tone rather than crashing a cell. */
const PILL_TONE: Record<string, StatusTone> = {
  blocks_billing: "danger",
  before_go_live: "warning",
  human_task: "info",
  routine: "neutral",
};

export interface WorkListProps {
  rows: readonly WorkItemRow[];
  /** `null` until the first response — the pager says nothing rather than
   *  saying *of 0* over a list that has not loaded. */
  total: number | null;
  loading: boolean;
  error: { reason: string; onRetry: () => void } | null;
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
  /** Which chip is pressed. `"all"` is the absence of a server filter. */
  chip: WorkChip;
  onChip: (next: WorkChip) => void;
  /** *All 14 · Blocks billing 3 · Cutover 6* — the SERVER's counts over the
   *  whole list, never over the page. */
  counts: { all: number; blocks_billing: number; human_tasks: number } | null;
  /** Resolve and reopen. Required, and required because an optional callback
   *  nothing passes is dead UI — hard-won law 2, four defects in one day. */
  onResolve: (row: WorkItemRow) => void;
  onReopen: (row: WorkItemRow) => void;
  /** Where *Run a check ▶* goes when there is nothing waiting. */
  runbooksTo: string;
  onRunACheck: () => void;
  /** Tenant-relative route → the real URL. The screen knows the tenant; a
   *  runbook emits `meter-reads` and never `/{tenant}/meter-reads`. */
  toHref: (path: string) => string;
  /** Today, as the caller reads it — never `new Date()` in here. A clock read
   *  inside a pure renderer makes the same row draw differently in a test and
   *  in a browser (`BR-TEN-043`'s spirit, gate `G6`). */
  today: Date;
}

export function WorkList(props: WorkListProps) {
  const { t } = useTranslation();
  const { onResolve, onReopen, toHref, today } = props;

  const config = useMemo<TableConfig<WorkItemRow>>(
    () => ({
      // Keys `table.RBS-007.columns` (`BR-SHL-013`) so a person's column choice
      // survives a remount. Its own id; it shares with nothing.
      screenId: "RBS-007",
      // ⚠ The id feeds React's key and the saved column set — neither is drawn
      // (B14 rule 31). What a reader sees is `title`.
      getRowId: (row) => row.id,
      searchFields: ["title", "subject_ref"],
      searchPlaceholder: "work.search",
      // The server orders by weight then age; naming its own order here is what
      // stops the table asking for one the server ignores.
      defaultSort: { sort: "weight", dir: "desc" },
      columns: [
        {
          key: "title",
          label: t("work.col.what"),
          cell: (row) => (
            <span data-work-title="">
              {row.title}
              {row.subject_ref !== null && (
                <span className="ms-2 text-neutral-600">{row.subject_ref}</span>
              )}
            </span>
          ),
        },
        {
          key: "from",
          label: t("work.col.from"),
          // ⚠ **THE RUNBOOK'S NAME, AND IT IS A DOOR.** *"Each carries where it
          // came from — the run that raised it"*, so the cell opens that run's
          // frozen result. A human task has no run and draws its words plain
          // rather than a link to nowhere.
          cell: (row) =>
            row.run_id === null || row.runbook_key === null || row.from === null ? (
              <span className="text-neutral-600">{t("work.from.person")}</span>
            ) : (
              <Link
                to={toHref(`runbooks/${row.runbook_key}/runs/${row.run_id}`)}
                data-work-run={row.run_id}
                className="text-neutral-900"
              >
                {row.from}
              </Link>
            ),
        },
        {
          key: "weight",
          label: t("work.col.weight"),
          cell: (row) => (
            <StatusPill tone={PILL_TONE[row.weight_pill] ?? "neutral"}>
              {t(`work.pill.${row.weight_pill}`)}
            </StatusPill>
          ),
        },
        {
          key: "owner",
          label: t("work.col.owner"),
          cell: (row) =>
            row.owner ?? <span className="text-neutral-600">{t("work.unassigned")}</span>,
        },
        {
          key: "age",
          label: t("work.col.age"),
          numeric: true,
          cell: (row) => <span data-work-age="">{ageWords(t, row.created_at, today)}</span>,
        },
        {
          key: "actions",
          label: t("work.col.actions"),
          cell: (row) => (
            <RowActions>
              {/* ⚠ **`BR-RBS-011` MADE VISIBLE: a finding a clerk cannot act on
                  is a finding we should not have shown them.** Every row the
                  engine raises carries a fix route; a human task may not, and
                  the control is then DISABLED WITH ITS REASON rather than
                  hidden (`BR-SHL-025`). */}
              <RowActionLink
                label={t("work.action.openFix")}
                icon={<WrenchIcon />}
                reason={row.fix_route === null ? t("work.noFixRoute") : null}
                to={row.fix_route === null ? "" : toHref(row.fix_route)}
              />
              {row.status === "open" ? (
                <RowAction
                  label={t("work.action.resolve")}
                  icon={<CommitIcon />}
                  hint={t("work.action.resolveHint")}
                  onClick={() => onResolve(row)}
                />
              ) : (
                <RowAction
                  label={t("work.action.reopen")}
                  icon={<RollBackIcon />}
                  hint={t("work.action.reopenHint")}
                  onClick={() => onReopen(row)}
                />
              )}
            </RowActions>
          ),
        },
      ],
    }),
    [t, toHref, onResolve, onReopen, today],
  );

  return (
    <main data-screen="RBS-007">
      <PageHeader
        backTo={{ to: props.runbooksTo, label: t("work.back") }}
        title={t("work.title")}
        rollup={t("work.subtitle")}
      />

      <DataTable
        config={config}
        state={props.state}
        onStateChange={props.onStateChange}
        rows={[...props.rows]}
        totalRows={props.total}
        loading={props.loading}
        error={props.error ?? null}
        // ── `RBS-007.2` · rule 17: what is missing and the action that fills it
        empty={{
          title: t("work.empty.title"),
          helper: t("work.empty.helper"),
          ctaLabel: t("work.empty.cta"),
          ctaVariant: "secondary",
          onCta: props.onRunACheck,
        }}
        filterBarSlot={
          <ChipRow aria-label={t("work.chipsLabel")} data-chips="work">
            {CHIP_ORDER.map((chip) => (
              <ChipToggle
                key={chip}
                selected={props.chip === chip}
                // Pressing the selected chip clears it — the same gesture the
                // sheet's `×` performs, without a second control to hit.
                onClick={() => props.onChip(props.chip === chip ? "all" : chip)}
                data-chip={chip}
              >
                {`${t(`work.chip.${chip}`)} ${chipCount(props.counts, chip)}`}
              </ChipToggle>
            ))}
          </ChipRow>
        }
      />
    </main>
  );
}

/** The number beside a chip, or an em dash before the first response.
 *
 *  ⚠ **THE SERVER'S COUNT OVER THE WHOLE LIST, NEVER THE PAGE'S.** A chip that
 *  counted `rows.length` would read *All 50* over 900 items — `NFR-3` broken
 *  one layer up, and the shape `DEF-RBS-4310` is about. */
function chipCount(
  counts: { all: number; blocks_billing: number; human_tasks: number } | null,
  chip: WorkChip,
): string {
  if (counts === null) {
    return "—";
  }
  if (chip === "blocks_billing") {
    return String(counts.blocks_billing);
  }
  if (chip === "cutover") {
    return String(counts.human_tasks);
  }
  return String(counts.all);
}

/**
 * *2 days* · *30 days* · *Today* — the age a clerk reads, from the FIRST
 * sighting.
 *
 * ⚠ **`today` IS AN ARGUMENT AND NOT A CLOCK READ.** Gate `G6` and
 * `BR-TEN-043`'s spirit: a value computed from `new Date()` inside a pure
 * renderer draws differently in a test and in a browser, and the one number
 * this screen exists to show would be the one that could not be asserted.
 */
export function ageWords(
  translate: (key: string, options?: Record<string, unknown>) => string,
  createdAt: string,
  today: Date,
): string {
  const born = new Date(createdAt);
  if (Number.isNaN(born.getTime())) {
    // A timestamp that will not parse is not a zero — saying *Today* over it
    // would be a guess with a friendly face.
    return "—";
  }
  const days = Math.floor((today.getTime() - born.getTime()) / 86_400_000);
  return days < 1 ? translate("work.age.today") : translate("work.age.days", { count: days });
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-006 (EP-RBS-03; CR-075 wave H task H3) · wireframes/RBS-007.1___RBS-007.2 (sheet + frame) · NFR-3 · B14 rules 2/4/12/15/16/17/20/21/31/32/33
// generated: 2026-09-07 by the CR-075 wave H build lane
// checklist: A✔ B✔ C✔ D✔(GET · PATCH /work-items[/{id}], 07-endpoints.md row 17) E✔ F✔ G✔ H=n/a(no 🔒 path)
// gates: tsc --noEmit (the LOCAL compiler, never npx) · vitest WorkList.dom.test.tsx · G13 (every handler prop is required and passed) · G31 (rule 21) · routeBUtilities
// exceptions: `↓ Export` is ABSENT rather than drawn dead — 07-endpoints.md row 17 serves no CSV route · the `Mine` chip is ABSENT — the filter exists (`f.owner`) and this screen does not hold the viewer's id · the Age column is DAYS and reads `Today` under one day, where the sheet's samples include `3 hours`. All three stamped in 08-screen-layouts.md
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
