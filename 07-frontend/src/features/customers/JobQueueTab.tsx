// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 step 2 wave G — **the Complaints and Services TABLES**
//           on the accounts register. PO ruling 2026-09-12: *"in the main tab
//           list, add complaints and services. These two tabs. build their ad
//           form and detail view. and tables."*
// Design:   `05-prototype/02 Accounts Menu Blueprint.pdf` screen 18 page 40
//           (*Complaints · the table*, `/:tenant/accounts?tab=complaints`) and
//           screen 19 page 47 (*Services · the table*,
//           `/:tenant/accounts?tab=services`), read as IMAGES.
// Rules:    BR-WRK-006 · BR-WRK-018 · BR-WRK-026 (six filters; NOT moved) ·
//           BR-SHL-010 (an undeclared capability is not rendered) ·
//           BR-SHL-011 (this list owns NO query string — `DEF-664`) ·
//           BR-SHL-025 · B14 rules 15, 19, 20, 21, 31, 32
// Tests:    src/features/customers/JobIntake.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **ONE COMPONENT, TWO TABS.** The only thing that differs between the
// Complaints queue and the Services queue is which `work_order_types` HEADING
// it stands on and which words it uses — so both are one `JobIntakeSpec`
// argument rather than two files. PO standing instruction, 2026-09-12: *"Do all
// changes bsed on actual code - also dont create duplcate code"*.
//
// ⚠ **THIS IS `GET /work-orders` WITH ITS TYPE PINNED — NOT A NEW READ.** The
// route already exists, already pages, already searches and already filters by
// type; a `GET /complaints` beside it would be a second queryset, a second
// pager and a second place for `BR-WRK-018`'s promise to be read differently.
// `jobIntakeShared.tsx` §1 records the whole judgment and its evidence.
//
// ⚠ **THE ROUTE'S WINDOW IS `OPEN`, AND THE DRAWN `Resolved` CHIP CANNOT BE
// SERVED.** `dispatch._open_queryset` is `state ∈ planned · in_progress ·
// blocked` — wave A's window, shared with the Orders tab so the two cannot
// disagree about what *open* means. The blueprint draws segment chips *Open ·
// Past due · Urgent · Resolved · All*, and two of those are outside that
// window. Rather than offer a chip that would silently return nothing, this tab
// draws the DISPATCH-STATUS and PRIORITY filters the route does answer, and the
// two unservable segments are REPORTED as owed. `BR-SHL-010`: a capability that
// is not declared is not rendered.
//
// ⚠ **NO KPI STRIP AND NO `CUSTOMER` COLUMN** — both are absences with reasons,
// argued in `jobQueueTableConfig`'s own docstring rather than repeated here.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getLookupEntries } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { EyeIcon } from "@/components/icons";
import { FilterBar, offerableFilters } from "@/components/FilterBar";
import { RowActionLink, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { Note } from "@/components/TextBits";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableRequestState } from "@/components/tableTypes";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { workOrderDetailPath } from "@/features/work/OrderDetailPage";
import { listWorkOrders } from "@/features/work/workEndpoints";
import type { WorkOrderDispatchRow } from "@/features/work/workEndpoints";
import { useTenantPath } from "@/routing/tenantPath";

import { Dash, accountDetailPath } from "./customersShared";
import { InlineLinkTo } from "@/components/Surfaces";
import {
  jobQueueQueryKey,
  jobQueueTableConfig,
  useJobKinds,
} from "./jobIntakeShared";
import type { JobIntakeSpec } from "./jobIntakeShared";

export interface JobQueueTabProps extends RegionalProps {
  spec: JobIntakeSpec;
  client?: ApiClient; // test seam — screens never build their own transport
  /** The tab's primary lives in the register's header, so the empty state's CTA
   *  is the SECOND way in and carries the ghost tier (B14 rule 4). Absent
   *  draws no button rather than wiring a no-op (`DEF-MET-4764`). */
  onNew?: () => void;
  newReason?: string | null;
}

export function JobQueueTab(props: JobQueueTabProps) {
  const { t } = useTranslation();
  const translate = (key: string, params?: Record<string, unknown>): string => t(key, params);
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props);
  const { spec } = props;

  // The heading whose kinds this queue holds, resolved from its CODE through
  // the utility's own catalogue. Never hard-coded: a tenant may rename the row
  // and `BR-TEN-030` freezes only the code.
  const { heading, failed: kindsFailed } = useJobKinds(spec, client);

  // The PRIORITY chip's options. The utility's own list, read once and shared
  // with the dispatcher's cache key so two screens cannot hold two copies.
  const prioritiesQuery = useQuery({
    queryKey: queryKeys.workLookup("work_priorities"),
    queryFn: () => getLookupEntries("work_priorities", { per: 200 }, client),
  });

  const config = useMemo(
    () =>
      jobQueueTableConfig(
        translate,
        spec,
        {
          // B14 rule 31 — the REFERENCE a clerk reads out loud, never the uuid.
          // A job with no number is a real state (`_allocate_unused_number`
          // warns rather than refuses), so the dash is an absence and not a
          // blank.
          //
          // Record links (PO 2026-10-19): the reference opens the job — the
          // work order's own page, the eye's destination — and the account
          // number opens the account.
          ref: (row) =>
            row.order_no !== null ? (
              <InlineLinkTo to={tenantPath(workOrderDetailPath("", row.id).slice(1))}>{row.order_no}</InlineLinkTo>
            ) : (
              <Dash />
            ),
          account: (row) =>
            row.account !== null ? (
              <InlineLinkTo to={tenantPath(accountDetailPath(row.account.id))}>{row.account.account_no}</InlineLinkTo>
            ) : (
              <Dash />
            ),
          // ⚠ **THE ADDRESS IS THE SERVER'S ONE STRING AND IS NOT RE-JOINED
          // HERE.** `_premise_of` walks the anchor to the premises and sends
          // `address` already assembled; hard rule 8 puts the address on the
          // PREMISES and every other entity derives it by walking. The drawing
          // prints a unit beside it (`1408 Elm · Unit E`) and this row carries
          // no unit label — REPORTED, and not guessed from the premise number.
          address: (row) =>
            row.premise !== null ? <span>{row.premise.address}</span> : <Dash />,
          // The KIND, which is the job's own words — *Billing Issues*, *Odour
          // complaint*. `_dispatch_row` sends the catalogue NAME where a type
          // resolved and the typed string otherwise, so nothing is mapped here.
          about: (row) => <span>{row.type}</span>,
          service: (row) => (row.service !== null ? <span>{row.service}</span> : <Dash />),
          // `BR-WRK-018` — the name and the hours, as the utility set them.
          // Null until a utility seeds priorities, and then it is a dash rather
          // than an invented rank.
          priority: (row) =>
            row.priority !== null ? <span>{row.priority.name}</span> : <Dash />,
          logged: (row) =>
            row.raised_at !== null ? (
              <DateCell value={row.raised_at} timeZone={timeZone} dateFormat={dateFormat} />
            ) : (
              <Dash />
            ),
          // ⚠ **THE PROMISE, NOT A PROMISE THIS PLATFORM MAKES.** Page 40, in
          // the drawing's own words: *"Respond by is not a promise this
          // platform makes. It is the moment a job was logged plus the hours
          // this utility set for that priority."* The figure is the server's
          // stamped `due_at`; nothing here adds hours to anything.
          respondBy: (row) =>
            row.due_at !== null ? (
              <DateCell value={row.due_at} timeZone={timeZone} dateFormat={dateFormat} />
            ) : (
              <Dash />
            ),
          state: (row) => (
            <StatusPill tone={jobStateTone(row)}>
              {translate(`work.orders.dispatch.${row.dispatch_state}`)}
            </StatusPill>
          ),
          // B14 rule 15 — an ICON with an accessible name, and a real `<Link>`
          // so ⌘-click opens the record in a second tab.
          //
          // ⚠ **THE DETAIL VIEW IS THE WORK ORDER'S OWN PAGE AND NOTHING NEW IS
          // BUILT FOR IT.** The blueprint draws the complaint and the service
          // detail at `/brazosbend/work/wo/…` — that screen exists, is routed
          // and is tested — so a second detail would be `CR-070` wave O's
          // duplicate destination one level down: PO, *"you cannot have two
          // differnt screen - this is an integration problem"*.
          actions: (row) => (
            <RowActions>
              <RowActionLink
                label={translate("customers.jobIntake.action.open", {
                  ref: row.order_no ?? "",
                })}
                icon={<EyeIcon />}
                to={tenantPath(workOrderDetailPath("", row.id).slice(1))}
              />
            </RowActions>
          ),
        },
        { priorities: prioritiesQuery.data?.results ?? [] },
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, spec, timeZone, dateFormat, prioritiesQuery.data],
  );

  // `DEF-664` — the table state is THIS COMPONENT'S. The query string belongs
  // to the Accounts page this tab sits inside, and is neither read nor written
  // here.
  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));

  const headingId = heading?.id ?? null;
  const listQuery = useQuery({
    queryKey: jobQueueQueryKey(spec.kind, headingId, state),
    // ⚠ **NOT ASKED UNTIL THE HEADING IS KNOWN.** A request with no `type`
    // would return the WHOLE dispatcher queue under a complaints heading —
    // every meter exchange and every reading on the utility, presented as
    // complaints. An unresolved heading renders the note below instead.
    enabled: headingId !== null,
    queryFn: () =>
      listWorkOrders(
        {
          q: state.q,
          page: state.page,
          per: state.per,
          type: headingId ?? undefined,
          status: state.filters.status,
          priority: state.filters.priority,
        },
        client,
      ),
  });

  return (
    <div data-embedded="" data-job-queue={spec.kind}>
      {(kindsFailed || (heading === null && !listQuery.isPending)) && (
        <Note>{t("customers.jobIntake.kindsUnavailable")}</Note>
      )}
      <DataTable<WorkOrderDispatchRow>
        config={config}
        filterBarSlot={
          <FilterBar
            filters={offerableFilters(config.filters ?? [])}
            state={state}
            onStateChange={setState}
          />
        }
        state={state}
        onStateChange={setState}
        rows={listQuery.data?.results ?? []}
        totalRows={listQuery.data?.count ?? null}
        loading={listQuery.isPending && headingId !== null}
        error={
          listQuery.isError
            ? {
                reason: t("work.orders.loadFailed"),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        empty={{
          title: t(spec.emptyTitleKey),
          helper: t(spec.emptyHelperKey),
          ...(props.onNew === undefined
            ? {}
            : {
                ctaLabel: t(spec.newActionKey),
                ctaReason: props.newReason ?? null,
                ctaVariant: "secondary" as const,
                onCta: props.onNew,
              }),
        }}
      />
    </div>
  );
}

/**
 * The STATE pill's tone, and it is the SCREEN's judgment because no rule ranks
 * the dispatch axis.
 *
 * `BR-WRK-023`'s seven dispatch states say where the technician is; what a
 * clerk on this queue is scanning for is whether the PROMISE has gone. So the
 * accent goes on a job whose `due_at` is in the past and nothing else — page
 * 40 draws exactly one row in the accent and it is the one reading `Past due`.
 */
export function jobStateTone(row: WorkOrderDispatchRow): StatusTone {
  if (row.dispatch_state === "complete") {
    return "success";
  }
  if (row.dispatch_state === "cancelled") {
    return "muted";
  }
  if (row.due_at !== null && Date.parse(row.due_at) < Date.now()) {
    return "warning";
  }
  return "neutral";
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-094-BRC01 step 2 wave G · blueprint screens 18 (p39–45) and 19
//         (p46–54) · PO rulings of 2026-09-12 quoted in the header ·
//         `GET /work-orders` (`apps/work/dispatch.dispatch_page`) ·
//         BR-WRK-006 · BR-WRK-018 · BR-WRK-026 · BR-WRK-058
// generated: 2026-09-12 by CR-094-BRC01 wave G
// checklist: A✔(the one backend change is `DEF-WRK-5106`, the parent-aware type
//         filter) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: E3 **no `CUSTOMER` column** — `_dispatch_row` serves the account
//         as `{id, account_no}` and no customer name; a dash in every cell
//         would assert *"this job has no customer"* on every row (`DEF-127`'s
//         rule). REPORTED · E3 **no KPI strip** — the drawn four tiles are
//         figures over the whole queue and A11's envelope carries no aggregate;
//         computing one from `results` would put a number on screen that
//         changes as a clerk pages. REPORTED · E3 **the drawn `Resolved` and
//         `All` segments are not offered** — `GET /work-orders` serves the OPEN
//         window only, and a chip that returned nothing is worse than a chip
//         that is absent (`BR-SHL-010`) · E3 **no sortable column** — the route
//         fixes the order at priority rank then due time and takes no `sort`
//         param, so a sort control would offer an ordering the request cannot
//         ask for
