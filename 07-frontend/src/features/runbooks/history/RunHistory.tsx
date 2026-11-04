// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-007 (EP-RBS-03) — CR-075 wave I task I6.
// Screens: RBS-008 Run history (`S154`, figure 28), one state, at
//          `/{tenant}/runbooks/runs`. Sheet:
//          04-docs/05-modules/17-runbooks/wireframes/RBS-008.md
// Rules:   BR-RBS-016 (a missed firing shows as **Failed**, naming the time) ·
//          BR-SHL-023 / IS-8 (every instant renders in the TENANT's zone and
//          format, published by the shell) · `NFR-3` · B14 rule 2 (page head) ·
//          rule 12 (toolbar) · rule 15 (row actions) · rule 16 (pager) ·
//          rule 17 (an empty list says what is missing) · rule 20 (one table
//          type) · rule 31 (no database id on screen) · rule 32 · rule 33.
// Defects: DEF-SHL-4283 (nine components read GET /settings/regional, which is
//          Admin-only — this one does not) · DEF-CWP-3925 (mount under the real
//          path pattern) · DEF-RBS-4291 (`started_at`).
// Tests:   07-frontend/src/features/runbooks/history/RunHistory.dom.test.tsx
// ───────────────────────────────────────────────────────
// THE SCREEN THAT MAKES *NOBODY OPENED THE PRODUCT* CHECKABLE.
//
// `EP-RBS-03`'s exit test is a demonstration: at 06:00 tenant local the sweep
// runs while the utility is asleep. **This is the only screen on which a person
// can afterwards see whether it did.** Every other runbooks screen answers
// *what does this runbook do* or *what did THIS run find*; this one answers
// *did it run at all, and when, and what happened the time before*.
//
// ══════════════════════════════════════════════════════════════════════════
// THE COLUMN THAT CARRIES THE WHOLE WAVE: **Outcome**
// ══════════════════════════════════════════════════════════════════════════
// `BR-RBS-016` — *a missed firing RAISES; it does not silently catch up. It
// appears in run history as **Failed**, not as an absence.* An absence is
// invisible to every check this repository has, and *"the sweep did not run for
// nine days"* is otherwise discovered by a bill run failing. So the scheduler
// writes a real `failed` run whose report is one sentence naming the missed
// time, and this table is where that sentence becomes findable: the row reads
// **Failed**, its *Started* cell holds the time the run SHOULD have started,
// and opening it shows the sentence.
//
// ⚠ **WHICH IS WHY `Started` IS DRAWN FROM `started_at` AND NOT FROM
// `created_at`.** On a missed firing those two are hours or days apart, and
// only the first is the fact a clerk needs.
//
// ══════════════════════════════════════════════════════════════════════════
// *By* DISTINGUISHES A PERSON FROM **Schedule**, AND TODAY IT CAN ONLY EVER SAY
// ONE OF THEM
// ══════════════════════════════════════════════════════════════════════════
// The sheet: ***By* distinguishes a person from *Schedule*** — *the audit-actor
// question made visible*. `runbook_runs` carries `approved_by` and `stopped_by`
// and **no `started_by`** (`DEF-RBS-4292`), so the server sends `by.person` as
// `null` on every row and this column draws the TRIGGER, which is a fact.
// Filling it from `approved_by` would put the approver's name in a *started by*
// column, which is the kind of near-right answer nobody ever re-checks.
//
// ══════════════════════════════════════════════════════════════════════════
// THREE THINGS THE SHEET DRAWS THAT ARE ABSENT, EACH STAMPED
// ══════════════════════════════════════════════════════════════════════════
//   * **`↓ Export`.** No export job exists for this list — `GET /runbooks/runs`
//     serves JSON and nothing else. Absent rather than drawn dead, exactly as
//     `RBS-003` decided for the same button.
//   * **`Started [sortable]`.** `runs_list` calls `parse_list_params` with
//     `allowed_sorts=()`, so the server orders by `-started_at, -created_at,
//     -id` and IGNORES any `sort` it is sent. A sort control that silently does
//     nothing is hard-won law 7's *structurally incapable of failing* wearing a
//     chevron. The order it draws IS the sortable order the sheet asks for; the
//     control is what is missing, and it arrives when the server sorts.
//   * **`+ Filter ▾`.** The server DOES filter on `f.runbook`, `f.category`,
//     `f.from` and `f.to`, so unlike the two above this is a real gap and not a
//     refusal — it is a `TableConfig.filters` declaration and a `FilterBar`,
//     sized for this wave and not taken. ⚠ It is NOT closed by adding chips:
//     `DEF-1700` is four screens that put a dimension into a chip row the
//     `+ Filter` panel already offered from the same option source, and the
//     Product Owner deleted all four (*"first raw of tookkit is more than
//     suficient"*). The five chips here are outcome and kind, which the panel
//     does not offer, so they are row one's own set.
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ChipRow, ChipToggle } from "@/components/Chip";
import { DataTable } from "@/components/DataTable";
import { formatDate } from "@/components/DateCell";
import { EyeIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { RowActionLink, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useRegional } from "@/features/metering/meteringShared";
import { tenantPathFrom, useTenant } from "@/routing/tenantPath";

import { formatTook } from "../home/runbooksHomeModel";
import type { RunRow } from "../home/homeEndpoints";
import { HISTORY_CHIPS } from "./historyEndpoints";
import type { HistoryChipId } from "./historyEndpoints";

export interface RunHistoryProps {
  rows: readonly RunRow[];
  /** The server's total. `null` until the first response, so the pager says
   *  nothing rather than *"of 0"* over a list that has not loaded. */
  total: number | null;
  loading: boolean;
  error?: { reason?: string; onRetry: () => void } | null;
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
  /** The chip row — `All · Checks · Actions · Failed · Stopped`. Held by the
   *  page and sent BACK to the server; nothing here slices a page. */
  chip: HistoryChipId;
  onChip: (chip: HistoryChipId) => void;
  /**
   * What `RBS-008`'s empty state does — go and look at the runbooks.
   *
   * ⚠ **REQUIRED, NOT OPTIONAL** (hard-won law 2, and `G13`'s whole question).
   * An optional handler nothing passes renders a button that does nothing,
   * every test passes, and the empty state — the one state a brand-new tenant
   * is guaranteed to see — becomes a dead end.
   */
  onBrowseRunbooks: () => void;
}

/** The result pill's tone, by run status — `models.RUN_STATUSES`.
 *
 *  ⚠ **A COMPLETE MAP AND NOT A LOOKUP WITH A DEFAULT.** A ninth status added
 *  to the model must make this file stop compiling rather than quietly drawing
 *  every new outcome in neutral grey, which is exactly the shade a **Failed**
 *  run would hide in — and a hidden Failed is `BR-RBS-016` defeated at the last
 *  step, after the scheduler went to the trouble of raising it. */
const RESULT_TONE: Record<string, StatusTone> = {
  queued: "neutral",
  running: "neutral",
  awaiting_approval: "warning",
  approved: "info",
  acting: "info",
  done: "success",
  failed: "danger",
  stopped: "warning",
};

/**
 * A chip's word, taken from the vocabulary that already owns it.
 *
 * ⚠ **B14 RULE 34 — ONE PAIR OF WORDS PER IDEA, EVERYWHERE, IN ALL ELEVEN
 * CATALOGUES.** *Checks* and *Actions* are the library's own chips and *Failed*
 * and *Stopped* are the words `RBS-003` already draws for those two run
 * outcomes. Minting `runbooks.history.chip.failed` would put a SECOND
 * translation of *Failed* into eleven files, and the two would diverge the
 * first time either was reworded — which is the drift rule 34 exists to stop.
 */
function chipLabelKey(id: HistoryChipId): string {
  if (id === "all" || id === "check" || id === "action") {
    return `runbooks.library.chip.${id}`;
  }
  return `runbooks.mine.result.${id}`;
}

export function RunHistory(props: RunHistoryProps) {
  const { t } = useTranslation();
  const tenant = useTenant();
  // ⚠ **THE SHELL'S PUBLICATION, NEVER `GET /settings/regional`** — that
  // endpoint is Admin-only and a Billing Clerk meets a refusal on it
  // (`DEF-SHL-4283`). `useRegional` reads the publication from
  // `GET /shell/display`, which every signed-in role may read, and the shell
  // draws no screen until it has answered — so there is no fallback to name.
  // DEF-SHL-3964: `useRegional` and no hand-written fallback (DEF-SHL-9122).
  const { timeZone, dateFormat } = useRegional({});

  const config = useMemo<TableConfig<RunRow>>(
    () => ({
      // Keys `table.RBS-008.columns` (`BR-SHL-013`) so a person's column choice
      // survives a remount. This screen's own id; it shares with nothing.
      screenId: "RBS-008",
      // ⚠ **THE ID IS USED HERE AND DRAWN NOWHERE** (B14 rule 31). A run has no
      // natural key and `/runbooks/{key}/runs/{id}` is its address; `getRowId`
      // feeds React's key and the column preference, neither of which is
      // rendered. What a clerk reads is `runbook_name`.
      getRowId: (row) => row.id,
      searchFields: ["runbook_name"],
      searchPlaceholder: "runbooks.history.search",
      defaultSort: { sort: "started_at", dir: "desc" },
      columns: [
        {
          key: "started",
          label: t("runbooks.history.col.started"),
          // ⚠ NOT `sortable` — see the header. The server ignores `sort`.
          cell: (row) =>
            row.started_at === null ? (
              // rule 33: a fact in five words. Not a dash — a dash reads as
              // data that failed to load.
              <span className="text-neutral-600">{t("runbooks.mine.notStarted")}</span>
            ) : (
              formatDate(row.started_at, timeZone, dateFormat, true)
            ),
        },
        {
          key: "runbook",
          label: t("runbooks.mine.col.runbook"),
          cell: (row) => (
            <Link
              to={tenantPathFrom(tenant, `runbooks/${row.runbook_key}`)}
              data-runbook={row.runbook_key}
              className="text-neutral-900"
            >
              {row.runbook_name}
            </Link>
          ),
        },
        {
          key: "by",
          label: t("runbooks.history.col.by"),
          // The audit-actor question made visible. `by.person` is `null` on
          // every row until `started_by` exists (`DEF-RBS-4292`); the TRIGGER
          // is a fact and is what this cell says meanwhile.
          cell: (row) => row.by.person ?? t(`runbooks.mine.trigger.${row.by.trigger}`),
        },
        {
          key: "outcome",
          label: t("runbooks.history.col.outcome"),
          cell: (row) => (
            <StatusPill tone={RESULT_TONE[row.status] ?? "neutral"}>
              {t(`runbooks.mine.result.${row.status}`)}
            </StatusPill>
          ),
        },
        {
          key: "acted",
          label: t("runbooks.history.col.acted"),
          numeric: true,
          // `records` is the plan's own row count. `counts` is NOT drawn: its
          // keys are the runbook author's Python vocabulary, so rendering them
          // prints an untranslated internal word into a cell (`DEF-RBS-4327`,
          // B14 rules 31 and 35 at once).
          cell: (row) => row.records,
        },
        {
          key: "took",
          label: t("runbooks.history.col.took"),
          numeric: true,
          cell: (row) =>
            formatTook(row.took_seconds) ?? (
              <span className="text-neutral-600">{t("runbooks.history.stillGoing")}</span>
            ),
        },
        {
          key: "actions",
          label: t("runbooks.mine.col.actions"),
          cell: (row) => (
            <RowActions>
              {/* rule 15: icons with tooltips, at most two before the overflow.
                  A run always has a result to open — even a MISSED firing,
                  whose result is the one sentence naming the time it should
                  have run. */}
              <RowActionLink
                label={t("runbooks.history.action.open")}
                icon={<EyeIcon />}
                to={tenantPathFrom(
                  tenant,
                  `runbooks/${row.runbook_key}/runs/${row.id}`,
                )}
              />
            </RowActions>
          ),
        },
      ],
    }),
    [t, tenant, timeZone, dateFormat],
  );

  return (
    <main data-screen="RBS-008">
      <PageHeader
        backTo={{ to: tenantPathFrom(tenant, "runbooks"), label: t("runbooks.mine.back") }}
        title={t("runbooks.history.title")}
        rollup={t("runbooks.history.subtitle")}
      />

      <DataTable
        config={config}
        state={props.state}
        onStateChange={props.onStateChange}
        rows={props.rows}
        totalRows={props.total}
        loading={props.loading}
        error={props.error ?? null}
        // ── rule 17: what is missing, and the action that fills it ──────────
        empty={{
          title: t("runbooks.history.empty.title"),
          helper: t("runbooks.history.empty.helper"),
          ctaLabel: t("runbooks.history.empty.cta"),
          ctaVariant: "secondary",
          onCta: props.onBrowseRunbooks,
        }}
        filterBarSlot={
          <ChipRow aria-label={t("runbooks.history.chipsLabel")} data-chips="outcome">
            {HISTORY_CHIPS.map((chip) => (
              <ChipToggle
                key={chip.id}
                selected={props.chip === chip.id}
                // Pressing the SELECTED chip clears it back to All — the same
                // gesture the sheet's `×` performs, without a second control.
                onClick={() =>
                  props.onChip(chip.id === "all" || props.chip === chip.id ? "all" : chip.id)
                }
                data-chip={chip.id}
              >
                {t(chipLabelKey(chip.id))}
                {chip.id !== "all" && props.chip === chip.id && (
                  <span aria-hidden="true" className="ms-1">
                    ×
                  </span>
                )}
              </ChipToggle>
            ))}
          </ChipRow>
        }
      />
    </main>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-007 (EP-RBS-03; CR-075 wave I task I6) · wireframes/RBS-008.md (4 regions, verbatim) · 08-screen-layouts.md §RBS-008 · NFR-3 · B14 rules 2/12/15/16/17/20/31/32/33 · BR-SHL-023
// generated: 2026-09-07 by the CR-075 wave I build lane
// checklist: A✔ B✔ C✔ D✔(GET /runbooks/runs, 07-endpoints.md row 8) E✔ F✔ G✔ H=n/a(no 🔒 path)
// gates: ./node_modules/.bin/tsc --noEmit (the LOCAL compiler, never npx) · vitest RunHistory.dom.test.tsx · G13 (every handler prop is required and passed)
// exceptions: `↓ Export` and the sortable `Started` header are ABSENT rather than drawn dead — no export job exists for this list and `runs_list` passes `allowed_sorts=()`; both stamped in the header above
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
