// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-003 (EP-WRK-01) — one worklist of every order the field has
//           finished and nobody has accepted, across every connection and
//           every anchor. Screen: Work-009 (`wireframes/Work-009.png`),
//           template W1 per `08-screen-layouts.md` §13.2.
// Rules:    BR-WRK-007 (the queue is `accepted_by IS NULL AND state =
//           completed` — no new table) · BR-MET-110 (a person accepts; only
//           then does a service go live) · BR-WRK-006 (an order with no
//           connection is here and its CONNECTION cell is a dash) · BR-WRK-005
//           (the screen id is recorded, none moves) · B14 rule 2 (one page
//           header) · rule 16 (the shared pager footer) · rule 17 (an empty
//           state says what is missing) · rule 20 (one table type) · rule 21
//           (Tailwind only — this file is on route-b-migrated.txt from its
//           first commit) · rule 31 (no database id is a visible value) ·
//           rule 32 (a description budget; no internal code in clerk copy) ·
//           rule 36 (the pack gives LAYOUT, r10 gives STYLE, the kit is how
//           you comply — see the note below)
// Tests:    src/features/work/AwaitingApprovalPage.test.tsx
// Impacts:  src/App.tsx (one route) · src/features/work/WorkShell.tsx (the
//           tab) · src/routing/screenIds.ts · 10-scripts/gates/
//           g29_allocated_badges.txt · src/features/work/workEndpoints.ts
// ───────────────────────────────────────────────────────
//
// ⚠ B14 RULE 36 (PO 2026-09-04): **EVERY VISIBLE PIECE OF THIS SCREEN COMES
// FROM THE SHARED KIT, AND NONE OF IT IS DRAWN HERE.** `wireframes/Work-009.png`
// says WHAT is on the screen and where; `05-prototype/r10-2026-08-16/UI-RULES.md`
// says what it LOOKS like; the kit is the only place those two meet. So:
// `PageHeader` (rule 2), `DataTable` — which brings r10 rule 16's *Showing
// 1–50 of N · Rows per page · pager* footer with it, so this screen neither
// writes one nor needs to — `StatusPill` for OUTCOME, `DateCell` for COMPLETED,
// `Dash` for an absent value, `RowActions`/`RowActionLink` with a glyph from
// `icons.tsx` for the eye (rule 15), and `Note` for both sentences. There is no
// raw `<button>`, no hand-rolled chip and no bespoke class: the breaches rule 36
// was ratified on were every one of them a screen inventing something the kit
// already had.
//
// ⚠ THE NOTE BAR IS REWRITTEN, AND THE DRAWING SAYS SO ITSELF.
// `wireframes/Work-009.png` ends with *"Every order here has field data and no
// `accepted_by`. Accepting one activates its service and tells the customer."*
// `accepted_by` is a COLUMN NAME on a clerk's screen, which B14 rule 32
// forbids, and `08-screen-layouts.md` records the deviation in its own
// "where the drawing loses" table: **write *nobody has accepted them***. The
// sentence below is that, and it loses nothing a clerk needed.
//
// ⚠ WHAT IS DELIBERATELY NOT HERE. No search box and no sort control: the
// drawing carries neither, and the server fixes the order (oldest first).
//
// ⚠ **CR-168 ROUND 2 (lane ORDERS-LIST) — THE QUEUE ACCEPTS, AND THE EYE OPENS
// THE ORDER (images 21, 22, 23).** This paragraph read *"No bulk 'accept all'
// either — BR-MET-110 is that a person reviews what the field sent"*. The PO
// has since drawn the acceptance ON this queue (ruling 13's drawings, task
// P1.36: *"a supervisor cannot accept from the queue they are sent to"*) and a
// SELECT column with *Accept selected…* (P3.7). The review half of BR-MET-110
// survives as the dialog: every accept, one or many, is asked first and names
// its consequence — the service goes live, the customer is told — and each
// order is accepted by its OWN request (`POST /work-orders/{id}/accept`, the
// one acceptance every door uses), so a refusal on one is that order's answer
// and never the batch's. The eye opened the build's home — the premises' or the
// account's build tab — and was DISABLED on a job with no build; it now opens
// `/work/orders/{id}` on every row (`DEF-WRK-9575`, P1.5), which also released
// the second held control (P1.7) beside the empty state's *Open work orders*.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { CommitIcon, EyeIcon } from "@/components/icons";
import { RowAction, RowActionLink, RowActions } from "@/components/RowActions";
import { PageHeader } from "@/components/PageHeader";
import { StatusPill } from "@/components/StatusPill";
import { Note } from "@/components/TextBits";
import { DateCell } from "@/components/DateCell";
import { useToast } from "@/components/Toast";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";
import { acceptWorkOrder } from "@/features/customers/newConnectEndpoints";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { ConnectionCell } from "./buildViews";

import { workOrderDetailPath } from "./OrderDetailPage";
import { workOrderOutcomeTone } from "./OrdersPage";
import { WORK_ORDERS_ROUTE, useWorkTabs } from "./WorkShell";
import { listAwaitingApproval } from "./workEndpoints";
import type { AwaitingApprovalRow } from "./workEndpoints";
import { WhereCell } from "./WhereCell";

/** `Work-009`'s route, tenant-relative like every route constant.
 *
 *  ⚠ DECLARED IN `WorkShell.tsx` AND RE-EXPORTED HERE. The strip needs every
 *  Work address to build its tabs and this screen needs the strip, so one of
 *  the two directions had to go — and an import cycle does not fail loudly, it
 *  hands the other module `undefined` (see that file's note). */
export { WORK_AWAITING_APPROVAL_ROUTE } from "./WorkShell";

/** The badge. r10 draws `WRK-01`..`WRK-18` for the module and NONE for this
 *  screen (`01-overview.md` §6 reads *—*), so `WRK-20` is MINTED by this lane
 *  in `g29_allocated_badges.txt`'s own shape, the way `WRK-19` was minted for
 *  the templates page on 2026-09-03. It is not a claim on A1's register: A1's
 *  reserved S61–S90 band is exhausted and inventing an `S` id would be worse
 *  than reporting the absence. */
export const AWAITING_APPROVAL_SCREEN = "WRK-20";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/**
 * WAITING, in words. `US-WRK-003` §5: *"in words, never a raw timestamp"*.
 *
 * The server sends whole days and this turns them into the drawing's phrase —
 * *6 days*, *1 day*. Exported so the test can ask the question without a DOM.
 */
export function waitingLabel(days: number | null, t: Translate): string {
  if (days === null) {
    return "";
  }
  return t("work.approvals.waiting.days", {
    defaultValue: "{{count}} days",
    count: days,
  });
}

/**
 * The table's declaration — `Work-009`'s seven columns in the drawing's order:
 * ORDER · CONNECTION · PREMISE · SERVICE · OUTCOME · COMPLETED · WAITING.
 * Exported so a test reads the capability row without rendering.
 */
export function awaitingApprovalTableConfig(
  t: Translate,
  cells: {
    select: (row: AwaitingApprovalRow) => React.ReactNode;
    order: (row: AwaitingApprovalRow) => React.ReactNode;
    connection: (row: AwaitingApprovalRow) => React.ReactNode;
    premise: (row: AwaitingApprovalRow) => React.ReactNode;
    outcome: (row: AwaitingApprovalRow) => React.ReactNode;
    completed: (row: AwaitingApprovalRow) => React.ReactNode;
    open: (row: AwaitingApprovalRow) => React.ReactNode;
  },
): TableConfig<AwaitingApprovalRow> {
  return {
    screenId: AWAITING_APPROVAL_SCREEN,
    getRowId: (row) => row.id,
    // ⚠ NO SEARCH, AND THE WAY TO SAY THAT IS TO SAY NOTHING. `searchFields`
    // is absent, not `[]`: `DataTable` renders the box on
    // `config.searchFields !== undefined`, so an empty array draws a live
    // search box over a server that declares no `q` — a control that reads
    // every keystroke and can never change a row. `tableTypes.ts:244` states
    // the idiom in its own words — *"absent = no search box"* — and G43 reads
    // it the same way: a list that declares `searchFields` must declare
    // `searchPlaceholder`, and this one declares neither because it has no box
    // to label (`BR-SHL-010`: a capability absent here is not a gap).
    // ⚠ NO SORT. Oldest first is the server's, fixed: a supervisor works this
    // list from the top and any other order is a different screen.
    defaultSort: { sort: "completed_at", dir: "asc" },
    columns: [
      // CR-168 P3.7 — image 21's SELECT column, the same cell shape the Orders
      // list uses (DataTable has no built-in selection; B14 rule 20's one
      // table type is kept by putting the box in the config).
      { key: "select", label: t("work.approvals.col.select"), cell: cells.select },
      { key: "order_no", label: t("work.approvals.col.order"), identity: true, cell: cells.order },
      { key: "connection", label: t("work.approvals.col.connection"), cell: cells.connection },
      { key: "premise", label: t("work.approvals.col.premise"), cell: cells.premise },
      {
        key: "service",
        label: t("work.approvals.col.service"),
        cell: (row) =>
          row.service === null ? (
            <Dash />
          ) : (
            <span data-service={row.service}>{t(`work.orders.service.${row.service}`)}</span>
          ),
      },
      { key: "outcome", label: t("work.approvals.col.outcome"), cell: cells.outcome },
      { key: "completed_at", label: t("work.approvals.col.completed"), cell: cells.completed },
      {
        key: "waiting_days",
        label: t("work.approvals.col.waiting"),
        cell: (row) => (
          <span className="tabular-nums">{waitingLabel(row.waiting_days, t)}</span>
        ),
      },
      // The ACTIONS cell — B14 rule 15, one icon from the shared vocabulary
      // (`EyeIcon` is "view" everywhere in this product), never a text link.
      {
        key: "actions",
        label: t("work.approvals.col.actions"),
        cell: cells.open,
      },
    ],
  };
}

export interface AwaitingApprovalPageProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

/** What is being asked: one row's ✓ or the ticked rows' *Accept selected…*. */
type Asking = { rows: AwaitingApprovalRow[] } | null;

/** `Work-009` — the queue the field fills and the office empties by accepting. */
export function AwaitingApprovalPage(props: AwaitingApprovalPageProps) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const client = props.client ?? api;
  const translate: Translate = (key, params) => t(key, params);
  const { timeZone, dateFormat } = useRegional(props);

  const [state, setState] = useState<TableRequestState>(() =>
    defaultRequestState(awaitingApprovalTableConfig(translate, EMPTY_CELLS)),
  );
  const [selected, setSelected] = useState<string[]>([]);
  const [asking, setAsking] = useState<Asking>(null);
  const [working, setWorking] = useState(false);

  const listQuery = useQuery({
    queryKey: queryKeys.workAwaitingApproval(state.page, state.per),
    queryFn: () => listAwaitingApproval({ page: state.page, per: state.per }, client),
  });
  const rows = useMemo(() => listQuery.data?.results ?? [], [listQuery.data]);

  /**
   * **P1.36 / P3.7 — ACCEPT, ONE REQUEST PER ORDER.** Each order goes through
   * the one acceptance every door uses (`BR-MET-110` step two: data accepted,
   * service activated, customer told), in turn, so a refusal is THAT order's
   * answer and the rest still land (`BR-WRK-027`'s per-order shape). The server
   * writes each acceptance in its own transaction — nothing here batches them.
   */
  async function accept(chosen: AwaitingApprovalRow[]) {
    setWorking(true);
    let done = 0;
    let firstRefusal: unknown = null;
    for (const row of chosen) {
      try {
        await acceptWorkOrder(row.id, client);
        done += 1;
      } catch (error) {
        firstRefusal ??= error;
      }
    }
    setWorking(false);
    setAsking(null);
    setSelected([]);
    const failed = chosen.length - done;
    if (chosen.length === 1 && failed === 0) {
      const only = chosen[0];
      toast(
        only.connection === null
          ? t("work.approvals.acceptedOne", { order: only.order_no ?? "" })
          : t("work.approvals.acceptedLive", { order: only.order_no ?? "" }),
      );
    } else if (failed === 0) {
      toast(t("work.approvals.acceptedMany", { count: done }));
    } else if (chosen.length === 1) {
      toast(refusalText(translate, firstRefusal));
    } else {
      toast(t("work.approvals.acceptedSome", { done, failed }));
    }
    await queryClient.invalidateQueries({ queryKey: ["work"] });
  }

  const config = awaitingApprovalTableConfig(translate, {
    select: (row) => (
      <input
        type="checkbox"
        aria-label={t("work.orders.selectRow", { order: row.order_no ?? "" })}
        checked={selected.includes(row.id)}
        onChange={(event) =>
          setSelected((current) =>
            event.target.checked ? [...current, row.id] : current.filter((id) => id !== row.id),
          )
        }
      />
    ),
    // Image 21's ORDER cell is the number alone; the job's name is in the
    // accept dialog, where the decision is made.
    order: (row) => <span className="tabular-nums">{row.order_no ?? ""}</span>,
    connection: (row) => <ConnectionCell connection={row.connection} />,
    premise: (row) => <WhereCell premise={row.premise} storedAt={row.stored_at} />,
    outcome: (row) =>
      row.outcome === null ? (
        <Dash />
      ) : (
        <StatusPill tone={workOrderOutcomeTone(row.outcome)}>
          {translate(`work.orders.outcome.${row.outcome}`)}
        </StatusPill>
      ),
    completed: (row) =>
      row.completed_at === null ? (
        <Dash />
      ) : (
        <DateCell value={row.completed_at} timeZone={timeZone} dateFormat={dateFormat} />
      ),
    // B14 rule 15 — 👁 then ✓, icons with accessible names. The eye opens the
    // ORDER on every row (`DEF-WRK-9575`): an order always exists, so there is
    // no row whose eye has nowhere to go.
    open: (row) => (
      <RowActions>
        <RowActionLink
          label={t("work.approvals.open")}
          icon={<EyeIcon />}
          to={tenantPath(workOrderDetailPath("", row.id).slice(1))}
        />
        <RowAction
          label={t("work.approvals.accept", { order: row.order_no ?? "" })}
          icon={<CommitIcon />}
          onClick={() => setAsking({ rows: [row] })}
        />
      </RowActions>
    ),
  });

  const strip = useWorkTabs(t("work.approvals.sentence"));

  const total = listQuery.data?.count ?? null;
  const oldest = listQuery.data?.oldest_waiting ?? null;
  const ticked = rows.filter((row) => selected.includes(row.id));

  /** The dialog's words. One order names itself; several are counted. */
  function question(chosen: AwaitingApprovalRow[]): { title: string; body: string } {
    if (chosen.length === 1) {
      const row = chosen[0];
      const where = [
        row.premise?.address ?? row.stored_at ?? null,
        row.service === null ? null : t(`work.orders.service.${row.service}`),
        // `DEF-WRK-9679` — image 22's *closed by D. Ortiz*: whose work is
        // being accepted. Absent, never guessed, when no close was recorded.
        row.closed_by?.name ? t("work.approvals.closedBy", { name: row.closed_by.name }) : null,
      ]
        .filter((part): part is string => part !== null)
        .join(" · ");
      const consequence =
        row.connection === null
          ? t("work.approvals.acceptConsequenceNoBuild")
          : t("work.approvals.acceptConsequence");
      return {
        title: t("work.approvals.acceptTitle", { order: row.order_no ?? "" }),
        body: `${consequence}\n\n${row.type}\n${where}`,
      };
    }
    return {
      title: t("work.approvals.acceptTitleMany", { count: chosen.length }),
      body: t("work.approvals.acceptConsequenceMany"),
    };
  }
  const asked = asking === null ? null : question(asking.rows);

  return (
    <div data-work-approvals="" data-screen={AWAITING_APPROVAL_SCREEN}>
      <PageHeader
        kicker={t("work.approvals.kicker")}
        title={t("work.approvals.title")}
        // Image 22 — *Accept selected… (1)* top right, present only while
        // something is ticked (ruling 16; an action over nothing is furniture).
        secondaryActions={
          ticked.length > 0 ? (
            <Button
              variant="primary"
              data-accept-selected=""
              onClick={() => setAsking({ rows: ticked })}
            >
              {t("work.approvals.acceptSelected", { count: ticked.length })}
            </Button>
          ) : undefined
        }
        {...strip}
      />

      <DataTable<AwaitingApprovalRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={total}
        loading={listQuery.isPending}
        error={
          listQuery.isError
            ? { reason: t("work.approvals.loadFailed"), onRetry: () => void listQuery.refetch() }
            : null
        }
        empty={{
          title: t("work.approvals.empty.title"),
          helper: t("work.approvals.empty.helper"),
          ctaLabel: t("work.approvals.empty.cta"),
          // P1.7 — released: the Orders list shipped in CR-070 wave H.
          onCta: () => navigate(tenantPath(WORK_ORDERS_ROUTE)),
        }}
      />

      {/* `Work-009`'s CountFooter — *"3 orders · oldest waiting 6 days"*. The
          second figure is about the WHOLE queue and comes from the server. The
          day phrase is interpolated already formatted (two plurals, one key). */}
      {total !== null && total > 0 && (
        <Note className="tabular-nums" data-approvals-footer="">
          {t("work.approvals.footer", {
            count: total,
            waiting: waitingLabel(oldest, translate),
          })}
        </Note>
      )}

      <Note data-approvals-note="">{t("work.approvals.note")}</Note>

      {asking !== null && asked !== null ? (
        <ConfirmDialog
          title={asked.title}
          consequence={asked.body}
          confirmLabel={t("work.approvals.acceptConfirm")}
          cancelLabel={t("work.approvals.keepWaiting")}
          working={working}
          onConfirm={() => void accept(asking.rows)}
          onCancel={() => setAsking(null)}
        />
      ) : null}
    </div>
  );
}

/** The cell set the STATE seed uses. The state only needs the column KEYS, so
 *  it is built from a config whose cells render nothing — cheaper than building
 *  the real one twice, and it cannot drift because the columns come from the
 *  same function. */
const EMPTY_CELLS = {
  select: () => null,
  order: () => null,
  connection: () => null,
  premise: () => null,
  outcome: () => null,
  completed: () => null,
  open: () => null,
};

export default AwaitingApprovalPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-003@ab786097 (EP-WRK-01) · 08-screen-layouts.md Work-009 · 09-component-inventory.md W1 · wireframes/Work-009.png
// generated: 2026-09-04 by the CR-070 wave B build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST — with the CONNECTION cell's null branch returning "" instead of <Dash/>, AwaitingApprovalPage.test.tsx fails "a row with no connection draws a dash"; quoted in the lane report. tsc · vitest · routeBUtilities.test.ts (every utility here is a declared token) · the cr070-b walkthrough reads a COLOUR from computed style
// exceptions: no search, no sort — stated in the header with the reason · [CR-168 round 2, lane ORDERS-LIST, 2026-10-04] bulk accept and the per-row ✓ ARE here now (P1.36, P3.7, images 21–23), each asked first; the eye opens the order on every row (DEF-WRK-9575) · E4 ⚠ **THIS IS THE ONE DRAWING IN THE PACK THAT AGREES WITH THE PRODUCT ABOUT SECTION CAPTIONS** — `Work-009` draws no caps caption above its table, where the other five draw one, and no list screen in the product draws one either (41 `DataTable` call sites, zero captions). Recorded because the module-wide decision in `08-screen-layouts.md` rests partly on it: the pack is not unanimous · E4 SERVICE is spelled out here and abbreviated to one letter on `Work-007`, which is the pack contradicting itself; both screens spell it out
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
