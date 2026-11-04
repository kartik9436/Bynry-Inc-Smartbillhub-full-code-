// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-003 · US-RBS-018 (EP-RBS-01) — CR-075 wave D task D4.
// Screens: RBS-003.1 all · RBS-003.2 filtered to Actions · RBS-003.3 empty
//          (`S149`), at `/{tenant}/runbooks/mine`.
// Rules:   `NFR-3` (universal server pagination) · `NFR-5` (no caps) · B14
//          rule 2 (page head) · rule 4 (one primary) · rule 12 (toolbar) ·
//          rule 15 (row actions are icons, max 2 + …) · rule 16 (pager) · rule
//          17 (an empty list says what is missing and the action that fills
//          it) · rule 20 (one table type) · rule 31 (no database id on
//          screen) · rule 32 · rule 33.
// Tests:   MyRunbooks.dom.test.tsx ·
//          10-scripts/render-checks/rbs-d-the-library.mjs
// Defects: DEF-RBS-4310 (the Scheduled and Paused chips have no server count
//          and no server filter) · DEF-RBS-4291 (`started_at` is never
//          stamped) · DEF-CWP-3925 (mount under the real path pattern).
// ───────────────────────────────────────────────────────
// THE LIST THAT MAKES THE MODULE WORTH OPENING DAILY.
//
// `08-screen-layouts.md`: ***Open items* is the column that makes this screen
// worth opening daily** — it is the count of work items a runbook's last run
// left on `RBS-007`, and it is why the list is a list and not a settings page.
//
// ══════════════════════════════════════════════════════════════════════════
// AND IT IS THE DOOR `RBS-004` HAS BEEN WAITING FOR
// ══════════════════════════════════════════════════════════════════════════
// The wave C lane shipped the setup screen at `/{tenant}/runbooks/{key}` and
// wrote in the decision log that **nothing in the product pointed at it**: *"the
// door is `RBS-003` (My runbooks, task `D4`); until it lands a person reaches
// this screen only by typing the address."* That is hard-won law 2's FRONT half
// — a screen with no door — and this file closes it. Every runbook name in the
// table is a real `<Link>` to that address, and `MyRunbooks.dom.test.tsx`
// asserts the href **by address**, never by *there is a link*: `DEF-CWP-3925`'s
// broken `//portal/…` addresses were perfectly good STRINGS.
//
// ══════════════════════════════════════════════════════════════════════════
// THREE THINGS THE SHEET DRAWS AND THIS SCREEN DOES NOT — EACH STAMPED
// ══════════════════════════════════════════════════════════════════════════
//   * **The `Scheduled` and `Paused` chips.** `GET /runbooks` filters on `kind`
//     and `category` and on nothing else, and serves no count for either state
//     (`DEF-RBS-4310`). A chip with no server filter is furniture, and one
//     counted from the current page is `NFR-3` in the shape `DEF-PAY-4221`
//     records four times over.
//   * **The two sortable columns.** `parse_list_params` is called with
//     `allowed_sorts=()`, so the catalogue orders by name and ignores any `sort`
//     it is sent. A sort control that silently does nothing is law 7's
//     *structurally incapable of failing* wearing a chevron, so no column
//     declares `sortable` until the server sorts.
//   * **The `▶` row action.** Starting a run is `POST /runbooks/{key}/runs`,
//     task `L`. The setup screen carries `Run ▶` with an honest sentence
//     because that screen is where a person decides to run something; an
//     icon-only `▶` in a table row that answers with a toast is a worse trade.
//
// ⚠ **AND ONE THE SHEET DRAWS THAT IS SERVED AND IS EMPTY TODAY.** `Last run`
// reads *Not started yet* on every row, because `services.open_run` never stamps
// `started_at` (`DEF-RBS-4291`, filed by the wave that wrote the endpoint). The
// cell says that in words rather than drawing a blank, which is the difference
// between a screen with no data and a screen that looks broken.
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ButtonLink } from "@/components/Button";
import { ChipRow, ChipToggle } from "@/components/Chip";
import { DataTable } from "@/components/DataTable";
import { CopyIcon, EyeIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { RowAction, RowActionLink, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { tenantPathFrom, useTenant } from "@/routing/tenantPath";

import { categoryLabel } from "./libraryLabels";
import type { CatalogueRow } from "./libraryTypes";

export interface MyRunbooksProps {
  rows: readonly CatalogueRow[];
  /** The server's total. `null` until the first response, which is what
   *  `DataTable` expects and what stops *"of 0"* flashing before a load. */
  total: number | null;
  loading: boolean;
  error?: { reason?: string; onRetry: () => void } | null;
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
  /** The kind chip row — `All · Checks · Actions`, the three the server filters
   *  on. Held here rather than in `TableConfig.filters` because the sheet draws
   *  them as CHIPS on the toolbar's first row, which is rule 12's own grammar. */
  kind: string;
  onKind: (kind: string) => void;
  /** **Templates →** — the page head's navigation action. */
  templatesTo: string;
  /**
   * What `RBS-003.3`'s **Browse templates →** does.
   *
   * ⚠ **A REQUIRED PROP RATHER THAN AN OPTIONAL ONE** (law 2 / `G13`): an
   * optional handler nothing passes renders a button that does nothing, every
   * test passes, and the empty state — the one screen state a new tenant is
   * guaranteed to see — becomes a dead end. `EmptyList` takes a callback rather
   * than a link, so the navigation happens in the page and the renderer stays
   * pure.
   */
  onBrowseTemplates: () => void;
  /**
   * **Clone** — `POST /runbooks/{key}/clone` (`07-endpoints.md` row 6, whose
   * own Screens column says `RBS-003.1`).
   *
   * ⚠ **RELEASED IN THE WAVE THAT COULD RELEASE IT, WHICH IS THE HALF THAT GETS
   * FORGOTTEN** (`DEF-RBS-4311`). The route landed on 2026-09-06 with wave `E1`
   * and this row action did not exist, so `US-RBS-038` — *"Clone on Dunning
   * makes Commercial accounts with its own schedule, cap and dry run; both rows
   * appear on My runbooks"* — had a working endpoint and no door. That is
   * hard-won law 2's mirror, which cost the customer portal six of its eight
   * front-page doors with every check green.
   *
   * ⚠ **REQUIRED, NOT OPTIONAL** (law 2's front half, and `G13`'s whole
   * question): a caller that forgets it does not compile.
   */
  onClone: (row: CatalogueRow) => void;
}

const KIND_ORDER = ["all", "check", "action"] as const;

/** The result pill's tone, by run status. `models.RUN_STATUSES`.
 *
 *  ⚠ **A COMPLETE MAP AND NOT A LOOKUP WITH A DEFAULT**, so a ninth status
 *  added to the model makes this file stop compiling rather than quietly drawing
 *  every new outcome in neutral grey — which is the shape a *Failed* run would
 *  hide in. */
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

export function MyRunbooks(props: MyRunbooksProps) {
  const { t } = useTranslation();
  const tenant = useTenant();
  // Destructured OUT of `props` so the memo below depends on the handler and
  // not on the whole props object — the rule's own preferred fix, and the one
  // that stops the table config being rebuilt on every unrelated prop change.
  const { onClone } = props;

  const config = useMemo<TableConfig<CatalogueRow>>(
    () => ({
      // Keys `table.RBS-003.columns` (`BR-SHL-013`) so a person's column choice
      // survives a remount. It is this screen's own id and shares with nothing.
      screenId: "RBS-003",
      // ⚠ **`key`, NOT AN ID.** B14 rule 31 bans a database id as a visible
      // value, and `getRowId` feeds React's key and the column preference —
      // neither of which is drawn — but using the slug here means the UUID never
      // enters this component at all. A field that does not exist cannot be
      // rendered by accident.
      getRowId: (row) => row.key,
      searchFields: ["name", "key"],
      // B14 rule 19: this list's OWN prompt, as a KEY so the other ten languages
      // can reach it.
      searchPlaceholder: "runbooks.mine.search",
      defaultSort: { sort: "name", dir: "asc" },
      columns: [
        {
          key: "name",
          label: t("runbooks.mine.col.runbook"),
          // ⚠ NOT `sortable` — see the header. The server ignores `sort`.
          cell: (row) => (
            <Link
              to={tenantPathFrom(tenant, `runbooks/${row.key}`)}
              data-runbook={row.key}
              className="text-neutral-900"
            >
              {row.name}
            </Link>
          ),
        },
        {
          key: "kind",
          label: t("runbooks.mine.col.kind"),
          cell: (row) => (
            <StatusPill tone={row.kind === "check" ? "info" : "danger"}>
              {t(`runbooks.library.kind.${row.kind}`)}
            </StatusPill>
          ),
        },
        {
          key: "category",
          label: t("runbooks.mine.col.category"),
          cell: (row) => categoryLabel(t, row.category),
        },
        {
          key: "schedule",
          label: t("runbooks.mine.col.schedule"),
          // *Paused* wins over the trigger, because a paused runbook does not
          // run whatever its trigger says — which is the fact a clerk scanning
          // this column is looking for.
          cell: (row) =>
            row.enabled
              ? t(`runbooks.mine.trigger.${row.trigger_kind}`)
              : t("runbooks.mine.trigger.paused"),
        },
        {
          key: "last_run",
          label: t("runbooks.mine.col.lastRun"),
          cell: (row) => lastRunWhen(t, row),
        },
        {
          key: "result",
          label: t("runbooks.mine.col.result"),
          cell: (row) =>
            row.last_run === null ? (
              // rule 33: a FACT in ≤ 6 words. Not a dash — a dash reads as data
              // that failed to load.
              <span className="text-neutral-600">{t("runbooks.mine.neverRun")}</span>
            ) : (
              <StatusPill tone={RESULT_TONE[row.last_run.status] ?? "neutral"}>
                {t(`runbooks.mine.result.${row.last_run.status}`)}
              </StatusPill>
            ),
        },
        {
          key: "open_items",
          label: t("runbooks.mine.col.openItems"),
          numeric: true,
          cell: (row) => row.open_items,
        },
        {
          key: "actions",
          label: t("runbooks.mine.col.actions"),
          cell: (row) => (
            <RowActions>
              {/* ⚠ **DISABLED WITH ITS REASON RATHER THAN HIDDEN**
                  (`BR-SHL-025`): a runbook that has never run has nothing to
                  view, and a person learns that instead of hunting for a
                  control somebody removed. */}
              <RowActionLink
                label={t("runbooks.mine.action.viewLastRun")}
                icon={<EyeIcon />}
                reason={row.last_run === null ? t("runbooks.mine.neverRun") : null}
                to={
                  row.last_run === null
                    ? ""
                    : tenantPathFrom(tenant, `runbooks/${row.key}/runs/${row.last_run.id}`)
                }
              />
              {/* **Clone** — `RB-040`, and the sheet's row-action cell allows
                  two icons before the overflow (rule 15). A COMMAND rather than
                  a link: it writes before anything navigates, so a middle-click
                  that opened it in a second tab would be a second copy. */}
              <RowAction
                label={t("runbooks.mine.action.clone")}
                icon={<CopyIcon />}
                hint={t("runbooks.mine.action.cloneHint")}
                onClick={() => onClone(row)}
              />
            </RowActions>
          ),
        },
      ],
    }),
    // `onClone` joins the list because the Clone cell closes over it — a memo
    // that omitted it would freeze the first handler the table ever saw.
    [t, tenant, onClone],
  );

  return (
    <main data-screen="RBS-003">
      <PageHeader
        backTo={{ to: tenantPathFrom(tenant, "runbooks"), label: t("runbooks.mine.back") }}
        title={t("runbooks.mine.title")}
        rollup={t("runbooks.mine.subtitle")}
        // ⚠ **ONE PRIMARY (B14 rule 4).** The sheet draws `↓ Export` and
        // `Templates →`; **Export is not built** — no export job exists for this
        // list — so it is absent rather than drawn dead, and `Templates →` is
        // the screen's one action. It NAVIGATES, so it is a link and rule 4's
        // `Verb →` grammar is what names it.
        primaryAction={
          <ButtonLink variant="primary" to={props.templatesTo} data-templates="">
            {t("runbooks.mine.templates")}
          </ButtonLink>
        }
      />

      <DataTable
        config={config}
        state={props.state}
        onStateChange={props.onStateChange}
        rows={props.rows}
        totalRows={props.total}
        loading={props.loading}
        error={props.error ?? null}
        // ── `RBS-003.3` · rule 17: what is missing and the action that fills it
        empty={{
          title: t("runbooks.mine.empty.title"),
          helper: t("runbooks.mine.empty.helper"),
          ctaLabel: t("runbooks.mine.empty.cta"),
          // rule 4 again: the page head already carries `Templates →`, so this
          // one is the SECONDARY tier and the screen keeps one primary. Work >
          // Parts shipped two primaries and the PO reported it.
          ctaVariant: "secondary",
          onCta: props.onBrowseTemplates,
        }}
        filterBarSlot={
          // ── `RBS-003.2` · the chips, and the `×` that undoes one ───────────
          // *A filter is visible and undoable* — the sheet draws the selected
          // chip with its `×`, and pressing the selected chip again clears it,
          // which is the same gesture without a second control.
          <ChipRow aria-label={t("runbooks.mine.kindChipsLabel")} data-chips="kind">
            {KIND_ORDER.map((kind) => (
              <ChipToggle
                key={kind}
                selected={kind === "all" ? props.kind === "" : props.kind === kind}
                // Pressing the SELECTED chip clears it — the same gesture the
                // sheet's `×` performs, without a second control to hit. The
                // test found this: the first draft re-sent the chip's own value
                // and the filter could be turned on and never off.
                onClick={() =>
                  props.onKind(kind === "all" || props.kind === kind ? "" : kind)
                }
                data-kind={kind}
              >
                {t(`runbooks.library.chip.${kind}`)}
                {kind !== "all" && props.kind === kind && (
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

/**
 * The *Last run* cell.
 *
 * ⚠ **IT READS `started_at` AND `started_at` IS NEVER WRITTEN**
 * (`DEF-RBS-4291`, filed by the lane that built this endpoint: *"services.
 * open_run creates the run with status=running and never sets started_at"*). So
 * every row says *Not started yet* today. **That is the honest answer and not a
 * placeholder** — the column is drawn from the field the field map declares for
 * it, and the day the writer stamps it the cell fills in with no change here.
 * Drawing `finished_at` instead would make the column true-looking and wrong: a
 * run that failed at open has a finish and no start.
 */
function lastRunWhen(translate: (key: string) => string, row: CatalogueRow): string {
  if (row.last_run === null) {
    return translate("runbooks.mine.neverRun");
  }
  if (row.last_run.started_at === null) {
    return translate("runbooks.mine.notStarted");
  }
  return row.last_run.started_at;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-003 · US-RBS-018 (EP-RBS-01; CR-075 wave D task D4) · wireframes/RBS-003.1–.3 (sheets + frames) · 08-screen-layouts.md §RBS-003 · NFR-3 · B14 rules 2/4/12/15/16/17/20/31/32/33
// generated: 2026-09-06 by the CR-075 wave D D3/D4 build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a(no 🔒 path)
// gates: tsc --noEmit (the LOCAL compiler, never npx) · vitest · routeBUtilities · G13 (every handler prop is required and passed)
// exceptions: the Scheduled/Paused chips, the two sortable columns, the ▶ row action and ↓ Export are ABSENT rather than drawn dead — each stamped in 08-screen-layouts.md, the first under DEF-RBS-4310
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
