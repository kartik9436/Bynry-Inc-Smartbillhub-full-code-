// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-024 (the dispatch columns, the third axis) · US-WRK-026
//           (six filters and no seventh) · US-WRK-027 (bulk Assign ·
//           Reschedule · Change priority) · US-WRK-011 (the Area filter is
//           tenancy's own list) · US-WRK-004 (the list itself, wave A) ·
//           US-WRK-001 (an order with no connection is in the list)
//           Screens: Work-007 — TEMPLATE W2 as of CR-070 wave G
// Rules:    BR-WRK-006 (four anchors) · BR-WRK-018 (priority carries a
//           promise; sort by rank then due) · BR-WRK-022 (areas are
//           tenancy.Area) · BR-WRK-023 (the third axis) · BR-WRK-024 (RAISED
//           BY) · BR-WRK-026 (exactly six filters) · BR-WRK-027 (one row per
//           order) · B14 rule 2 (one page header) · rule 15 (icons for row
//           actions — none until Work-008 exists) · rule 19 (this list's own
//           search prompt) · rule 20 (one table type) · rule 21 (Tailwind;
//           on route-b-migrated.txt) · rule 31 (no id is a visible value) ·
//           rule 32 (one sentence per section) · rule 33 (a fact ≤ 6 words)
// Tests:    src/features/work/OrdersPage.test.tsx
// Impacts:  src/features/work/workEndpoints.ts · dispatchModals.tsx ·
//           src/api/queryClient.ts (`queryKeys.workOrders`)
// ───────────────────────────────────────────────────────
//
// ⚠ **WAVE G GREW THIS SCREEN FROM TEMPLATE W1 TO W2, AND WAVE A WROTE THE
// RELEASE CONDITION ITSELF.** The wave A header said: *"Every one of them reads
// a column that does not exist until wave G's migration … this wave draws
// template W1 and wave G grows it into W2."* Those columns exist now
// (`metering/0050`), so the KPI strip, the five filter chips, PRIORITY,
// TECHNICIAN, DUE, STATUS, RAISED BY and the bulk row all land here.
//
// ⚠ **STATE, OUTCOME AND CONNECTION ARE STILL SERVED AND ARE NOW OFF BY
// DEFAULT.** `Work-007` draws ten columns and none of those three is among
// them, and the drawing also puts a **Columns ▾** control at the right of the
// card — which is exactly what that control is for. Nothing was deleted: the
// server still sends all thirteen, `defaultVisible: false` is the only
// difference, and a dispatcher who wants the connection number ticks it back on
// and the choice is remembered (`BR-SHL-013`, keyed by `screenId`).
//
// ⚠ **BOTH HOLDS ARE RELEASED AS OF CR-070 WAVE H (2026-09-05), AND THE
// MECHANISM THAT MADE THAT HAPPEN IS WORTH MORE THAN EITHER BUTTON.**
//
// This paragraph used to read *"no row action and no `+ New work order`, and
// both are holds with a test"*, and beside it `ORDERS_HELD_CONTROLS` declared
// each refusal AS DATA with the ADDRESS that would release it. Wave H mounted
// `/:tenant/work/orders/new` and `/:tenant/work/orders/:orderNo`, and
// `OrdersPage.test.tsx` went red naming both controls — which is exactly what
// it was written to do.
//
// That is hard-won law 2's mirror clause running once, end to end: *when you
// write a hold, write the test that fires when the hold expires, in the same
// commit.* `DEF-CWP-3925` is what it costs when nobody does — the customer
// portal's front page had two working doors out of eight, five of them still
// refusing over screens that had shipped days earlier, with `tsc`, 391 test
// cases and every gate green over the top of it. No gate can see a stale
// refusal; only a test that fails when the destination arrives can.
//
// `ORDERS_HELD_CONTROLS` stays, now empty, with the same assertion pointed at
// it: an empty list is the honest statement that this screen refuses nothing,
// and the next lane that adds a hold inherits the machinery rather than
// re-inventing it.
import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { getLookupEntries } from "@/api/endpoints";
import { Button, ButtonLink } from "@/components/Button";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { KPIStrip } from "@/components/KPIStrip";
import { PageHeader } from "@/components/PageHeader";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { defaultRequestState } from "@/components/tableTypes";
import { seedQueryFromUrl } from "@/routing/seedQueryFromUrl";
import type {
  TableConfig,
  TableFilterConfig,
  TableRequestState,
} from "@/components/tableTypes";
import { Dash, accountDetailPath } from "@/features/customers/customersShared";
import { InlineLinkTo } from "@/components/Surfaces";
import { RowActionLink, RowActions } from "@/components/RowActions";
import { EyeIcon, PencilIcon } from "@/components/icons";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTenantPath } from "@/routing/tenantPath";
import { useRegional } from "@/features/metering/meteringShared";
// CR-070 wave H — ONE function each says where the detail and the wizard open,
// so the list and those screens cannot disagree about an address (law 5).
import { workOrderDetailPath } from "./OrderDetailPage";
import { dueText } from "./orderPage/orderFormat";
import type { Regional } from "./orderPage/orderFormat";
import { newOrderWizardPath } from "./NewOrderWizard";
import { ConnectionCell } from "./buildViews";
import { jobTypeFilterOptions } from "./raise/raiseModel";

import { BulkModal } from "./dispatchModals";
import { useWorkTabs } from "./WorkShell";
import { WhereCell } from "./WhereCell";
import {
  WORK_ORDER_DISPATCH_STATES,
  bulkWorkOrders,
  getWorkKpis,
  listCrews,
  listWorkAreas,
  listWorkOrders,
} from "./workEndpoints";
import type {
  BulkAct,
  BulkOutcome,
  WorkOrderDispatchRow,
  WorkOrderDispatchState,
  WorkOrderOutcome,
  WorkOrderState,
} from "./workEndpoints";

/** r10's own badge for the dispatcher — `01-overview.md` §6, Work-007 ↔ WRK-01. */
export const WORK_ORDERS_SCREEN = "WRK-01";

/**
 * ⚠ **EVERY REFUSAL THIS SCREEN DRAWS, AS DATA A TEST CAN READ.**
 *
 * A hold is a rule with a CLOCK in it: true the day it is written, false the
 * day the thing it waits for arrives — and landing a screen and releasing the
 * control that pointed at it are two acts, of which only the first feels like
 * the work. `DEF-CWP-3925` is what that cost on the customer portal: eight
 * doors on the front page, two of them working, five refusing over screens
 * shipped days earlier, with `tsc`, 391 test cases and every gate green.
 *
 * `G103` owns this question for the portal and reads `portal/routing/holds.ts`;
 * no gate reads a STAFF hold. So this list is the staff equivalent and
 * `OrdersPage.test.tsx` walks it: **the day `releasedBy` appears in the screen
 * registry, the suite goes red and names the control.**
 */
export const ORDERS_HELD_CONTROLS = [
  // ⚠ **EMPTY SINCE CR-070 WAVE H, AND EMPTY IS A STATEMENT.** Wave G declared
  // two entries here — the empty state's `+ New work order` and the row's 👁 —
  // each naming the address that would release it. Wave H landed both
  // addresses, so both controls are live above and both entries are gone.
  //
  // The list is KEPT rather than deleted because it is the machinery, not the
  // data: `OrdersPage.test.tsx` still walks it, so a lane that adds the next
  // hold gets the expiry test for free instead of writing one from scratch —
  // and writing one from scratch is precisely what nobody does (`DEF-CWP-3925`).
] as const;

/** The state's tone — metering's five tokens, the kit's six tones. */
export function workOrderStateTone(state: WorkOrderState): StatusTone {
  switch (state) {
    case "in_progress":
      return "info";
    case "blocked":
      return "warning";
    case "completed":
      return "success";
    case "cancelled":
      return "muted";
    default:
      return "neutral";
  }
}

/** The outcome's tone — five tokens; null renders a dash, never a pill. */
export function workOrderOutcomeTone(outcome: WorkOrderOutcome): StatusTone {
  switch (outcome) {
    case "passed":
      return "success";
    case "failed":
      return "danger";
    case "partially_done":
      return "warning";
    case "cancelled":
      return "muted";
    default:
      return "info";
  }
}

/**
 * `BR-WRK-023`'s third axis, in the drawing's own colours: *On site* teal, *En
 * route* teal, *Queued* grey, *Scheduled* green.
 *
 * ⚠ **THIS IS A SEPARATE FUNCTION FROM `workOrderStateTone` ABOVE ON PURPOSE.**
 * The two axes share two of their words — `cancelled` and `complete`/`completed`
 * — and mean different things by them: a `state` of cancelled says the job was
 * called off, a `dispatch_state` of cancelled says it was taken off the run. One
 * shared mapping would make that ambiguity invisible in the code as well as on
 * the screen.
 */
export function dispatchStateTone(state: WorkOrderDispatchState): StatusTone {
  switch (state) {
    case "en_route":
    case "on_site":
      return "info";
    case "scheduled":
      return "success";
    case "complete":
      return "muted";
    case "on_hold":
      return "warning";
    case "cancelled":
      return "muted";
    default:
      return "neutral";
  }
}

type Translate = (key: string, params?: Record<string, unknown>) => string;

/**
 * The table's declaration — `Work-007`'s TEN at template W2, in the drawing's
 * order, plus the three wave A columns the **Columns ▾** chooser keeps on offer.
 *
 * Exported so the test can count the capability row without a DOM.
 */
export function workOrdersTableConfig(
  t: Translate,
  cells: {
    select: (row: WorkOrderDispatchRow) => React.ReactNode;
    /** `DEF-WRK-9689` — the *Select all* box in the select column's head. */
    selectHeader?: () => React.ReactNode;
    actions: (row: WorkOrderDispatchRow) => React.ReactNode;
    premise: (row: WorkOrderDispatchRow) => React.ReactNode;
    priority: (row: WorkOrderDispatchRow) => React.ReactNode;
    technician: (row: WorkOrderDispatchRow) => React.ReactNode;
    due: (row: WorkOrderDispatchRow) => React.ReactNode;
    status: (row: WorkOrderDispatchRow) => React.ReactNode;
    raisedBy: (row: WorkOrderDispatchRow) => React.ReactNode;
    state: (row: WorkOrderDispatchRow) => React.ReactNode;
    outcome: (row: WorkOrderDispatchRow) => React.ReactNode;
    connection: (row: WorkOrderDispatchRow) => React.ReactNode;
  },
  filters: TableFilterConfig[],
): TableConfig<WorkOrderDispatchRow> {
  return {
    screenId: WORK_ORDERS_SCREEN,
    getRowId: (row) => row.id,
    // B14 rule 19 — what the search MATCHES, as a key. The drawing's box reads
    // *Search WO #, premise…*; the server also matches the type and the
    // CONNECTION number, and a box that names fewer fields than it searches is
    // the smaller of the two sins rule 19 is about.
    searchFields: ["order_no", "type", "premise", "connection_no"],
    searchPlaceholder: "work.orders.search",
    filters,
    // ⚠ NO SORTABLE COLUMN, AND THE SORT IS NOT ARBITRARY. `BR-WRK-018` fixes it
    // — priority rank, then due time — and the footer says so in words a clerk
    // reads. This seeds `defaultRequestState`; the server ignores `sort`/`dir`.
    defaultSort: { sort: "priority", dir: "asc" },
    columns: [
      // The bulk checkbox. DataTable has no built-in selection, so it is a cell
      // in THIS config — the shape `AssetRegistryPage` already uses, and the
      // reason B14 rule 20's one table type is not put at risk by a second one.
      { key: "select", label: t("work.orders.col.select"), cell: cells.select, header: cells.selectHeader },
      {
        key: "order_no",
        label: t("work.orders.col.order"),
        identity: true,
        // `DEF-WRK-9698` — an id never wraps: `WO-` / `0016` on two lines made
        // every row two lines tall and the number unreadable at a glance.
        cell: (row) => (
          <span data-order-no="" className="whitespace-nowrap tabular-nums">
            {row.order_no ?? ""}
          </span>
        ),
      },
      { key: "type", label: t("work.orders.col.type"), cell: (row) => <span>{row.type}</span> },
      { key: "premise", label: t("work.orders.col.premise"), cell: cells.premise },
      {
        key: "service",
        label: t("work.orders.col.service"),
        cell: (row) =>
          row.service === null ? (
            <Dash />
          ) : (
            <span data-service={row.service}>{t(`work.orders.service.${row.service}`)}</span>
          ),
      },
      { key: "priority", label: t("work.orders.col.priority"), cell: cells.priority },
      { key: "technician", label: t("work.orders.col.technician"), cell: cells.technician },
      { key: "due", label: t("work.orders.col.due"), cell: cells.due },
      { key: "dispatch_state", label: t("work.orders.col.status"), cell: cells.status },
      { key: "source", label: t("work.orders.col.raisedBy"), cell: cells.raisedBy },
      // ── still served, off by default, on offer in Columns ▾ ────────────────
      // `Work-007` draws ten and none of these is among them. They are NOT
      // deleted: the row still carries them, a dispatcher ticks one back on and
      // the choice is remembered (BR-SHL-013, keyed by screenId).
      {
        key: "state",
        label: t("work.orders.col.state"),
        cell: cells.state,
        defaultVisible: false,
      },
      {
        key: "outcome",
        label: t("work.orders.col.outcome"),
        cell: cells.outcome,
        defaultVisible: false,
      },
      {
        key: "connection",
        label: t("work.orders.col.connection"),
        cell: cells.connection,
        defaultVisible: false,
      },
      // ── CR-070 wave H · the 👁 wave G held ─────────────────────────────
      // B14 rule 15 — an ICON with an accessible name, never a text link. It
      // was not drawn at all until now, and drawing a GREYED eye over nothing
      // would have been the mirror failure: a dead control with a sentence
      // explaining itself.
      { key: "actions", label: t("work.orders.col.actions"), cell: cells.actions },
    ],
  };
}

export interface OrdersPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

/** Work-007 at wave G: five tiles, six filters, ten columns and three bulk acts. */
export function OrdersPage(props: OrdersPageProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const toast = useToast();
  const queryClient = useQueryClient();
  const translate: Translate = (key, params) => t(key, params);
  // `DEF-WRK-9701` — the tenant's zone and format, the same pair the order
  // page reads, so Due is one string on both screens.
  const regional: Regional = useRegional({});
  // CR-070 wave H — the row's 👁 and the empty state's CTA both navigate now.
  const navigate = useNavigate();
  const tenantPath = useTenantPath();

  /** ONE function says where *New work order* opens, so the permanent action
   *  row and the empty state's CTA cannot drift apart (hard-won law 5). */
  const newOrderPath = tenantPath(newOrderWizardPath("").slice(1));
  const openNewOrder = () => navigate(newOrderPath);

  const [selected, setSelected] = useState<string[]>([]);
  /** True once *Choose all N* has gathered every order the filter matches. */
  const [allMatching, setAllMatching] = useState(false);
  const [gathering, setGathering] = useState(false);
  /** The ids of the page in hand, read by the head box at render time (the
   *  table config is memoised; the page is not one of its inputs). */
  const pageIds = useRef<string[]>([]);
  const [pending, setPending] = useState<BulkAct | null>(null);

  // ── the five filter chips' options ──────────────────────────────────────
  // Four come from the utility's own lists and one is this product's own
  // vocabulary. `US-WRK-011`'s whole content is that the Area chip reads
  // `tenancy.Area` through Work's seam and Work keeps no copy of it.
  const areasQuery = useQuery({
    queryKey: queryKeys.workAreas(),
    queryFn: () => listWorkAreas(client),
  });
  const typesQuery = useQuery({
    queryKey: queryKeys.workLookup("work_order_types"),
    queryFn: () => getLookupEntries("work_order_types", { per: 200 }, client),
  });
  const prioritiesQuery = useQuery({
    queryKey: queryKeys.workLookup("work_priorities"),
    queryFn: () => getLookupEntries("work_priorities", { per: 200 }, client),
  });
  const crewsQuery = useQuery({
    queryKey: queryKeys.workCrews("", 1, 200),
    // The TECHNICIAN chip's options — people, crews and contractors in one
    // list, because BR-WRK-029 makes one test decide for all three and a chip
    // that offered only people would hide every job a contractor holds.
    queryFn: () => listCrews({ per: 200 }, client),
  });

  const filters: TableFilterConfig[] = useMemo(
    () => [
      {
        name: "type",
        label: t("work.orders.filter.type"),
        // `DEF-WRK-9582` (P2.3) — job type › sub-type as TWO levels, the
        // heading bold and its sub-types indented under it (BR-WRK-058), as the
        // raise draws them. Choosing a heading matches every sub-type under it.
        ...jobTypeFilterOptions(typesQuery.data?.results ?? []),
      },
      {
        name: "status",
        label: t("work.orders.filter.status"),
        options: WORK_ORDER_DISPATCH_STATES.map((state) => ({
          value: state,
          label: t(`work.orders.dispatch.${state}`),
        })),
      },
      {
        name: "priority",
        label: t("work.orders.filter.priority"),
        options: (prioritiesQuery.data?.results ?? []).map((row) => ({
          value: row.id,
          label: row.name,
        })),
      },
      {
        name: "technician",
        label: t("work.orders.filter.technician"),
        // *Unassigned* is a real answer to *which technician* and is what the
        // first KPI tile counts, so it is the first option rather than a
        // seventh filter of its own.
        options: [
          { value: "none", label: t("work.orders.unassigned") },
          ...(crewsQuery.data?.results ?? []).map((row) => ({
            value: row.id,
            label: row.name,
          })),
        ],
      },
      {
        name: "area",
        label: t("work.orders.filter.area"),
        options: (areasQuery.data ?? []).map((row) => ({ value: row.id, label: row.name })),
      },
    ],
    [t, typesQuery.data, prioritiesQuery.data, crewsQuery.data, areasQuery.data],
  );

  const config = useMemo(
    () =>
      workOrdersTableConfig(
        translate,
        {
          // ── CR-070 wave H · the row action wave G held ─────────────────
          // B14 rule 15's 👁, pointing at `Work-008`. `RowActionLink` draws a
          // real `<Link>`, so ⌘-click opens the order in a second tab and the
          // address bar tells a dispatcher where they are.
          actions: (row) => (
            <RowActions>
              <RowActionLink
                label={translate("work.orders.action.open", {
                  order: row.order_no ?? "",
                })}
                icon={<EyeIcon />}
                to={tenantPath(workOrderDetailPath("", row.id).slice(1))}
              />
              {/* ── CR-070 wave I · the ✎, pointing at `Work-021` ──────────
                  B14 rule 15's vocabulary is 👁 · ✓ · ✎, and this is the third.
                  It lands in the SAME COMMIT as the screen it opens: landing a
                  screen and landing the door that reaches it are one act, and
                  treating them as two is what shipped the customer portal with
                  two working doors out of eight (`DEF-CWP-3925`).

                  ⚠ It is a SECOND door beside wave H's 👁, not a replacement:
                  reading an order and changing one are different intentions,
                  and the drawing gives each its own glyph. */}
              <RowActionLink
                label={translate("work.orders.action.edit", {
                  order: row.order_no ?? "",
                })}
                icon={<PencilIcon />}
                to={tenantPath(`/work/orders/${row.id}/edit`)}
              />
            </RowActions>
          ),
          // `DEF-WRK-9689` (beta #29, P3.6) — the head box ticks the PAGE in
          // hand; the bar then offers every order the filter matches.
          selectHeader: () => {
            const ids = pageIds.current;
            const all = ids.length > 0 && ids.every((id) => selected.includes(id));
            return (
              <input
                type="checkbox"
                aria-label={translate("work.orders.selectAll")}
                data-select-all=""
                checked={all}
                disabled={ids.length === 0}
                onChange={(event) => {
                  const ticked = event.target.checked;
                  setAllMatching(false);
                  setSelected((current) =>
                    ticked
                      ? [...current, ...ids.filter((id) => !current.includes(id))]
                      : current.filter((id) => !ids.includes(id)),
                  );
                }}
              />
            );
          },
          select: (row) => (
            <input
              type="checkbox"
              aria-label={translate("work.orders.selectRow", { order: row.order_no ?? "" })}
              checked={selected.includes(row.id)}
              // ⚠ **THE FUNCTIONAL UPDATER, BECAUSE THIS CONFIG IS MEMOISED.**
              // The alternative reads `selected` out of the closure the
              // `useMemo` captured, which is correct only for as long as
              // `selected` stays in that memo's dependency list — and a lane
              // trimming those deps to stop the table re-rendering would turn a
              // performance tweak into *ticking three rows assigns one*, with
              // `tsc` and every static assertion green. This form cannot be
              // broken that way.
              // (Recorded honestly: the *1 order ticked* failure this was first
              // written for turned out to be the fixture clicking a node a
              // settling query had already replaced — see the test. The updater
              // is right on its own merits, not because it fixed that.)
              onChange={(event) =>
                setSelected((current) =>
                  event.target.checked
                    ? [...current, row.id]
                    : current.filter((id) => id !== row.id),
                )
              }
            />
          ),
          // PREMISE — the address, and the account number beside it when the
          // order stands on an account (Work-007: `903 Birch Ln · A-10222`).
          // `DEF-WRK-9671` — a job on no premises reads its meter's stored-at
          // note, else a dash (`WhereCell`).
          premise: (row) => (
            <WhereCell
              premise={row.premise}
              storedAt={row.stored_at}
              suffix={
                row.account !== null && (
                  // Record links (PO 2026-10-19): the number opens the account.
                  <span className="tabular-nums text-neutral-700">
                    {" · "}
                    <InlineLinkTo to={tenantPath(accountDetailPath(row.account.id))}>{row.account.account_no}</InlineLinkTo>
                  </span>
                )
              }
            />
          ),
          // PRIORITY — the pill takes the TENANT's own colour token, which is
          // one of the four `PRIORITY_COLOURS` and a subset of the kit's six
          // tones. A utility that renames Urgent still gets its own word and its
          // own colour, and this screen invents neither (B14 rule 31: the NAME
          // is the visible value).
          priority: (row) =>
            row.priority === null ? (
              <Dash />
            ) : (
              <StatusPill tone={row.priority.colour}>{row.priority.name}</StatusPill>
            ),
          // TECHNICIAN — a name, or a RED pill reading *Unassigned*. Never a
          // blank cell: a blank reads as a bug, a red pill reads as the thing a
          // dispatcher is on this screen to fix.
          technician: (row) =>
            row.technician === null ? (
              <StatusPill tone="danger">{translate("work.orders.unassigned")}</StatusPill>
            ) : (
              <span className="flex flex-col">
                <span>{row.technician.name}</span>
                {/* P4.1 — has the person given the job taken it? A fact of
                    one or two words under the name (B14 rule 33). */}
                {row.technician_acceptance ? (
                  <span
                    className={
                      row.technician_acceptance.state === "declined"
                        ? "text-sm text-danger-700"
                        : "text-sm text-neutral-600"
                    }
                    data-acceptance={row.technician_acceptance.state}
                  >
                    {translate(`work.orders.acceptance.${row.technician_acceptance.state}`)}
                  </span>
                ) : null}
              </span>
            ),
          due: (row) =>
            row.due_at === null ? <Dash /> : <DueCell due={row.due_at} t={translate} regional={regional} />,
          status: (row) => (
            <StatusPill tone={dispatchStateTone(row.dispatch_state)}>
              {translate(`work.orders.dispatch.${row.dispatch_state}`)}
            </StatusPill>
          ),
          // RAISED BY — `BR-WRK-024`. A dash on an order raised before any door
          // stamped a reason; never a guess (the server's own posture).
          raisedBy: (row) =>
            row.source === null ? (
              <Dash />
            ) : (
              <span title={row.source_ref ?? undefined}>
                {translate(`work.orders.source.${row.source}`)}
              </span>
            ),
          state: (row) => (
            <StatusPill tone={workOrderStateTone(row.state)}>
              {translate(`work.orders.state.${row.state}`)}
            </StatusPill>
          ),
          outcome: (row) =>
            row.outcome === null ? (
              <Dash />
            ) : (
              <StatusPill tone={workOrderOutcomeTone(row.outcome)}>
                {translate(`work.orders.outcome.${row.outcome}`)}
              </StatusPill>
            ),
          // CONNECTION — the shared cell, so this queue, the approval queue and
          // the dispatcher cannot disagree about where a build lives.
          connection: (row) => <ConnectionCell connection={row.connection} />,
        },
        filters,
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, selected, filters, regional.timeZone, regional.dateFormat],
  );

  // ── DEF-WRK-4094 · CR-073 ────────────────────────────────────────────
  // Universal search's per-group "View all" opens this list as
  // `?q=<term>` (BR-SHL-011's grammar). This screen held its table state
  // locally and never read the query string, so that link promised a
  // filtered list and delivered the whole register — with `tsc` green, the
  // route resolving and the screen rendering perfectly.
  // Seeded ONCE, at mount, and only `q`: this screen does not WRITE the URL
  // back, so reading a page or a sort it will never write would restore, on
  // reload, a state the user had since left. See seedQueryFromUrl's docstring.
  const [searchParams] = useSearchParams();
  const [state, setState] = useState<TableRequestState>(() =>
    seedQueryFromUrl(defaultRequestState(config), searchParams),
  );

  const listQuery = useQuery({
    queryKey: queryKeys.workOrders(state.q, state.page, state.per, state.filters),
    queryFn: () =>
      listWorkOrders(
        {
          q: state.q,
          page: state.page,
          per: state.per,
          type: state.filters.type,
          status: state.filters.status,
          priority: state.filters.priority,
          technician: state.filters.technician,
          area: state.filters.area,
        },
        client,
      ),
  });

  pageIds.current = (listQuery.data?.results ?? []).map((row) => row.id);
  const matchingTotal = listQuery.data?.count ?? 0;
  const pageAllChosen =
    pageIds.current.length > 0 && pageIds.current.every((id) => selected.includes(id));

  /**
   * *Choose all N* — every order the CURRENT search and filters match, read
   * page by page from the server (NFR-3: no unpaginated read; NFR-5: no cap).
   * The bulk write is per order anyway (`BR-WRK-027`), so it takes the ids.
   */
  async function chooseAllMatching() {
    setGathering(true);
    try {
      const per = 500;
      const ids: string[] = [];
      for (let page = 1; ; page += 1) {
        const chunk = await listWorkOrders(
          {
            q: state.q,
            page,
            per,
            type: state.filters.type,
            status: state.filters.status,
            priority: state.filters.priority,
            technician: state.filters.technician,
            area: state.filters.area,
          },
          client,
        );
        ids.push(...chunk.results.map((row) => row.id));
        if (chunk.results.length < per || ids.length >= chunk.count) break;
      }
      setSelected(ids);
      setAllMatching(true);
    } catch (error) {
      toast(t("work.orders.bulk.chooseAllFailed"));
      if (!isApiError(error)) throw error;
    } finally {
      setGathering(false);
    }
  }

  const kpisQuery = useQuery({ queryKey: queryKeys.workKpis(), queryFn: () => getWorkKpis(client) });
  const kpis = kpisQuery.data;

  const strip = useWorkTabs(t("work.orders.sentence"));

  async function runBulk(body: Record<string, unknown>): Promise<FormSubmitOutcome> {
    // ⚠ **P1.1 · `DEF-WRK-9570` — A REFUSED BATCH IS ANSWERED, NOT THROWN.**
    // `FormModal` awaits this inside a try/finally with no catch, so a refusal
    // that escaped here was an unhandled rejection: the dialog stayed open and
    // said nothing, and a dispatcher had no way to tell a refusal from a hang.
    // The server's sentence now renders in the dialog, through the catalogue.
    let outcome: BulkOutcome;
    try {
      outcome = await bulkWorkOrders({ act: pending as BulkAct, ids: selected, ...body }, client);
    } catch (error) {
      return isApiError(error)
        ? { ok: false, error: formErrorEnvelope(error) }
        : { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
    // `BR-WRK-027` — the answer is PER ORDER, so the message is too. A batch
    // where seven of eight succeeded says both numbers; saying only "done"
    // would hide a refusal the dispatcher has to act on.
    toast(
      outcome.failed === 0
        ? t("work.orders.bulk.done", { count: outcome.done })
        : t("work.orders.bulk.partial", { done: outcome.done, failed: outcome.failed }),
    );
    setSelected([]);
    setAllMatching(false);
    setPending(null);
    await queryClient.invalidateQueries({ queryKey: ["work"] });
    return { ok: true } as const;
  }

  return (
    <div data-work-orders="" data-screen={WORK_ORDERS_SCREEN}>
      <PageHeader
        // ⚠ **P2.1 · `DEF-WRK-9562` · `DEF-WRK-4105` — THE CREATE IS THE PAGE'S
        // PRIMARY ACT, TOP RIGHT, ACCENT** (image 01; ruling 16, B14 rule 2).
        // It lived in a row under the pager, outlined, from `DEF-WRK-4121`
        // until CR-168 — a fix for a missing button that put it where the
        // empty state's CTA had been. `TemplatesPage` already did it right, so
        // this is that shape: a `ButtonLink` (it navigates, so ⌘-click opens a
        // second tab) in the kit's header slot.
        secondaryActions={
          <ButtonLink variant="primary" data-new-order="" to={newOrderPath}>
            {t("work.orders.empty.cta")}
          </ButtonLink>
        }
        kicker={t("work.orders.kicker")}
        title={t("work.orders.title")}
        {...strip}
      />

      {/* ⚠ FIVE TILES, AND THE STAFF STRIP HAS CARRIED FOUR — a COUNT, not a
          new component (`08-screen-layouts.md` Work-007's own deviation note).
          The kit's grid is `auto-fit` over a 240px minimum for money; these
          are counts, so `tiles="count"` takes 224px and five sit on one row at
          1440 (image 01, `DEF-WRK-9680`) and still wrap on a narrow screen. */}
      <KPIStrip
        // `DEF-WRK-9680` — five COUNTS fit one row at 1440 (image 01).
        tiles="count"
        loading={kpisQuery.isPending}
        kpis={[
          {
            id: "unassigned",
            label: t("work.orders.kpi.unassigned"),
            value: kpis?.unassigned.count ?? 0,
            detail: t("work.orders.kpi.unassignedSub"),
          },
          {
            id: "due_today",
            label: t("work.orders.kpi.dueToday"),
            value: kpis?.due_today.count ?? 0,
            // ⚠ i18next's PLURAL MACHINERY, not a count glued to a string. A
            // sentence built here with `+ " urgent"` is a plural nobody can
            // translate, and six of the eleven languages do not form it the way
            // English does.
            detail: t("work.orders.kpi.dueTodaySub", { count: kpis?.due_today.urgent ?? 0 }),
          },
          {
            id: "in_field",
            label: t("work.orders.kpi.inField"),
            value: kpis?.in_field.count ?? 0,
            detail: t("work.orders.kpi.inFieldSub"),
          },
          {
            id: "awaiting",
            label: t("work.orders.kpi.awaiting"),
            value: kpis?.awaiting_approval.count ?? 0,
            detail: t("work.orders.kpi.awaitingSub"),
          },
          {
            id: "overdue",
            label: t("work.orders.kpi.overdue"),
            value: kpis?.overdue.count ?? 0,
            // The worst one, NAMED — the tile points at something a person can
            // act on rather than at a number. Nothing overdue says so instead.
            detail:
              kpis?.overdue.worst == null
                ? t("work.orders.kpi.overdueNone")
                : t("work.orders.kpi.overdueSub", {
                    order: kpis.overdue.worst.order_no ?? "",
                    count: kpis.overdue.worst.days,
                  }),
          },
        ]}
      />

      {/* `Work-007`'s ActionRow — the bulk half, drawn only when something is
          ticked, because an empty bulk bar is furniture over a capability
          nobody has invoked. **`+ New work order` is NOT in here**: it is the
          one control on this screen that does not act on a selection, so it
          is the page header's primary act (image 01, CR-168 P2.1). */}
      {selected.length > 0 && (
        <div
          className="mb-3 flex flex-wrap items-center gap-3 border border-l-[3px] border-divider border-l-accent-500 bg-surface px-3 py-2 text-base"
          role="status"
          data-bulk-bar=""
        >
          <span>{t("work.orders.bulk.selected", { count: selected.length })}</span>
          {/* `DEF-WRK-9689` (P3.6) — the page is chosen and more match: offer
              them all. Once gathered, say so; the count is the server's. */}
          {allMatching && selected.length === matchingTotal ? (
            <span data-all-matching="">{t("work.orders.bulk.allChosen", { n: matchingTotal })}</span>
          ) : pageAllChosen && matchingTotal > pageIds.current.length ? (
            <Button variant="ghost" disabled={gathering} onClick={() => void chooseAllMatching()} data-choose-all="">
              {t("work.orders.bulk.chooseAll", { n: matchingTotal })}
            </Button>
          ) : null}
          <Button variant="secondary" onClick={() => setPending("assign")}>
            {t("work.orders.bulk.assign")}
          </Button>
          <Button variant="secondary" onClick={() => setPending("reschedule")}>
            {t("work.orders.bulk.reschedule")}
          </Button>
          <Button variant="secondary" onClick={() => setPending("priority")}>
            {t("work.orders.bulk.priority")}
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              setSelected([]);
              setAllMatching(false);
            }}
          >
            {t("work.orders.bulk.clear")}
          </Button>
        </div>
      )}

      <DataTable<WorkOrderDispatchRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={listQuery.data?.results ?? []}
        totalRows={listQuery.data?.count ?? null}
        loading={listQuery.isPending}
        filterBarSlot={
          <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
        }
        error={
          listQuery.isError
            ? { reason: t("work.orders.loadFailed"), onRetry: () => void listQuery.refetch() }
            : null
        }
        empty={{
          title: t("work.orders.empty.title"),
          helper: t("work.orders.empty.helper"),
          ctaLabel: t("work.orders.empty.cta"),
          // CR-070 wave H — it opens the wizard. `ctaReason` is gone because
          // there is no longer a reason: a disabled control with a stale
          // sentence is worse than no control (hard-won law 2's mirror).
          onCta: () => openNewOrder(),
        }}
      />

      {/* `Work-007`'s footer sentence. The list's own pager states 1–8 of 10;
          this states what the utility has, which is the other fact — and the
          denominator comes from the KPI read, never from the page. */}
      {kpis !== undefined && (
        <p className="text-sm text-neutral-700" data-orders-footer="">
          {t("work.orders.footer", {
            shown: listQuery.data?.results.length ?? 0,
            count: kpis.open_total,
          })}
        </p>
      )}

      {pending !== null && (
        <BulkModal
          act={pending}
          ids={selected}
          held={selected.filter((id) => (listQuery.data?.results ?? []).some((row) => row.id === id && row.technician !== null)).length}
          client={client}
          priorities={(prioritiesQuery.data?.results ?? []).map((row) => ({
            value: row.id,
            label: row.name,
          }))}
          onSubmit={runBulk}
          onClose={() => setPending(null)}
        />
      )}
    </div>
  );
}

/**
 * DUE, as a dispatcher reads it — *Today 15:30*, *Tomorrow*, *2 days late*.
 *
 * ⚠ **AND IT IS LATE-AWARE, BECAUSE THAT IS THE COLUMN'S JOB.** A due date is
 * the only cell on this screen whose meaning depends on the clock, and an
 * overdue job rendered as a plain date is a job nobody notices. Six words at
 * most (B14 rule 33's FACT cap) and the full timestamp on `title`.
 */
function DueCell(props: { due: string; t: Translate; regional: Regional }) {
  const due = new Date(props.due);
  const days = Math.floor((Date.now() - due.getTime()) / 86_400_000);
  if (days >= 1) {
    return (
      <span className="text-danger-700" title={props.due}>
        {props.t("work.orders.due.late", { count: days })}
      </span>
    );
  }
  // ⚠ `DEF-WRK-9701` — NOT `toLocaleDateString()`, which reads the BROWSER's
  // locale and zone: `10/8/2026` here beside `10/09/2026` on the order page.
  // `dueText` is the order page's own formatter (IS-8, the tenant's pair).
  return <span title={props.due}>{dueText(props.due, props.regional)}</span>;
}

export default OrdersPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-024/026/027/011@wave-G · US-WRK-004 · US-WRK-001 (EP-WRK-01, EP-WRK-05) · 08-screen-layouts.md Work-007 · 09-component-inventory.md W2 · wireframes/Work-007.png
// generated: 2026-09-05 by the CR-070 wave G build lane (grown from the wave A W1 screen)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST — with `defaultVisible: false` removed from the three wave A columns, OrdersPage.test.tsx fails "the drawing's ten are the default set"; with ORDERS_HELD_CONTROLS' releasedBy pointed at a registered path, it fails "a hold names a screen that has not landed". tsc · eslint · vitest · G31 (route-b-migrated.txt)
// exceptions: E4 the drawing's five NAMED chips — *Type · all · Status · all · Priority · all · Technician · all · Area · all*, standing on the toolbar with their value in them — render as B14 rule 12's `[All] [chip ×] [+ Filter ▾]`. All five dimensions are declared and a sixth beside them; only the CONTROL differs, and it differs because `DEF-442` is the PO's own instruction that put this shape there (*"it is panel and when you select somethibg it shows selection on screen"*). Building the drawing's version back would re-open a closed defect and grow a Work-only toolbar (rule 36) · E4 SVC spells the service out where the drawing draws one letter — a letter is a code, the tenant names its own services (`BR-MET-109`), and Solar/Sewer/Storm water share an initial; `Work-009` spells it out too, so the pack disagrees with itself · E4 no `OPEN ORDERS` caption above the table — decided once for the module in `08-screen-layouts.md`: the product has 41 `DataTable` call sites and none draws a section caption · E4 no download control; CR-045 owns it · GET /work-orders/map is not built (07-endpoints.md row 68, WM-23's own screen)
// ⚠ THIS LINE STILL SAID *no row action and no + New work order until Work-008 and the wizard exist* AFTER WAVE H LANDED BOTH (2026-09-05, the recurrence noted in `DEF-WRK-4046`). Wave H did the hard half correctly — `App.tsx` registered the two addresses, `ORDERS_HELD_CONTROLS` was removed, the row actions and the empty-state CTA went live, and `OrdersPage.test.tsx` is green on all seventeen — and left the footer describing the screen it used to be. Third file the same day, which is why the defect names the MECHANISM rather than the strings: a lane corrects the prose it is reading and not the footer it is not.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
