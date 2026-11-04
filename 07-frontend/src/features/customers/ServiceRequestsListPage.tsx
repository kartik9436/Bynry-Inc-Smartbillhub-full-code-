// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W4 task 4.11 — **S83, the Requests list (REQ-01)**.
//           Design: B19 §12.1 (04-docs/02-decisions/19-cr031-service-request-
//           capture.md), from the PO's own screenshots of 2026-08-24, and
//           B18 §5.3.1/§5.3.2. Screens: S83 (B18's proposal — A1 allocates no
//           id and decision **D1** is unruled, so nothing is minted here)
// Rules:    BR-CUS-093 (numbered AT CREATION — a draft row carries its number;
//           a pre-ruling row carries NULL forever and gaps are NORMAL) ·
//           BR-CUS-091 (`DISCONNECT` is a lawful request TYPE — the list was
//           right and the decision panel's refusal is withdrawn) ·
//           BR-SHL-011 (the URL grammar) · B14 rule 20 (ONE table type) ·
//           B14 rule 21 (Tailwind utilities; no stylesheet class) ·
//           BR-SHL-010 (an undeclared capability is not rendered)
// Tests:    07-frontend/src/features/customers/ServiceRequestsListPage.test.tsx
//           (TC-REQ-12 · TC-REQ-13 · TC-REQ-14)
// Impacts:  06-backend `GET /api/{tenant}/service-requests` (live) ·
//           App.tsx + routing/screenIds.ts (the route)
// AMENDED:  2026-08-25 by lane F-REQ — **DEF-664, the Accounts → Requests tab.**
//           The screen gains an EMBEDDED MODE (`urlState={false}`) so the tab
//           can mount the real list instead of a panel saying it "is still to
//           come". PO, from production on v2.46.0: *"When I click on service
//           request nothing is shoing, but I ahve created one request - it
//           shows up on another scren"*. DEF-664's stated blocker — the two
//           screens fighting over one query string — is solved by the embedded
//           copy owning NO query string at all, so **no URL grammar is decided
//           and BR-SHL-011 is untouched**. See `urlState` for the whole rule.
// ───────────────────────────────────────────────────────
//
// ✅ **THE `AGE` ACCENT IS DRAWN — BR-CUS-106 (PO ruling 2026-08-25, closing
// decision D4).** This block said *"the AGE accent is NOT drawn, and that is
// the whole of TC-REQ-14"* until that ruling. B19 §12.1 measured the drawing
// and could not derive the threshold — `15d` and `11d` render in the accent,
// `5d` and below do not, so it was bounded to **6–11 days** and no further —
// B18 *proposed* 7 without authority to confirm it, and picking 7 here would
// have been resolving an open decision by choosing a value. **The PO chose 7,
// one week, and the boundary is INCLUSIVE.**
//
// ⛔ **THE THRESHOLD IS STILL NOT IN THIS FILE.** `list_row` now SERVES
// `age_is_accented`, and `AgeCell` renders that flag; it does not compare
// `age_days` to anything. **TC-REQ-14 was REPLACED, not deleted** — it proved a
// 15-day row and a 2-day row were styled identically while D4 was open, and it
// now asserts the real rule, boundary included.
//
// ⚠ **WHAT ELSE B19 §12.1 DRAWS AND THIS DOES NOT, EACH WITH ITS REASON:**
//
//   * **The eight-tab strip** (`Accounts · Requests⁴² · New Connect⁷ · …`).
//     `AccountsListPage.tsx` renders it and is another lane's file in this
//     shared tree today. ✅ **AMENDED 2026-08-25 (DEF-664) — the tab's body is
//     no longer owed FROM THIS SIDE.** This component now takes `urlState` and
//     renders as an embedded list when it is `false`; the Accounts page mounts
//     it. The sentence below claiming the tab "still shows its arrives-with
//     note" was true when written and is superseded by that mount — hard-won
//     law 1: a comment describing a screen is not the screen.
//   * **The superscript tab counts.** `PageHeaderTab` has no count slot and
//     `components/PageHeader.tsx` is not this lane's file.
//   * **`Export`.** `POST /exports` registers no `service_requests` resource,
//     so BR-SHL-010 keeps the capability unrendered. Not drawn disabled either:
//     BR-SHL-025 is for a control this ROLE cannot use, not one the product
//     does not have. ⚠ **TRACKED AS DEF-1005 SINCE 2026-08-27** — this was one
//     of only two of the eight export-less lists that said so at all, and a
//     stated absence with no id behind it outlives its reason and nothing
//     notices (DEF-445).
//   * **The five segments render as a filter CHIP, not r10's radio `seg`
//     control.** B14 rule 12 fixes the toolbar's grammar and the shared
//     `TableConfig` has no segment capability; adding one changes every list in
//     the product. The behaviour B18 asks for is intact — the choice rides in
//     the URL as `f.segment=` and a reload restores it (BR-SHL-011).
//   * **The pager footnote is the shared one** (`1–8 of 42`), not B19's
//     *"Showing 1–8 of 42 (filtered from 118)"*. The wording belongs to
//     `ListPager` and to every list in the product, and the server sends one
//     `count` — a "(filtered from 118)" would need an unfiltered total the
//     envelope does not carry. **TC-REQ-13 asserts the served count, and the
//     parenthetical is REPORTED as needing a second server figure.**
import { useQuery } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { PageHeader } from "@/components/PageHeader";
import { RowActions, RowActionLink } from "@/components/RowActions";
import { EyeIcon } from "@/components/icons";
import { RequestEditRowAction } from "./serviceRequestEditDoor";
import {
  defaultRequestState,
  parseTableParams,
  serializeTableParams,
} from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { DASHBOARD_ROUTE } from "./customersShared";
import { listServiceRequests, SERVICE_REQUEST_SEGMENTS } from "./serviceRequestEndpoints";
import type {
  ServiceRequestRow,
  ServiceRequestSegment,
} from "./serviceRequestEndpoints";
import {
  DateOrNotSupplied,
  RequestNumber,
  RequestStatePill,
  SERVICE_REQUEST_NEW_ROUTE,
  SERVICE_REQUESTS_ROUTE,
  TextOrNotSupplied,
  serviceRequestPath,
} from "./serviceRequestShared";

/** The screen id `TableConfig` keys its column preference on. B18 proposes S83
 *  and A1 allocates nothing (D1) — the STRING is a preference key, not a claim
 *  that A1 declares the id, and `routing/screenIds.ts` carries the real
 *  finding on the route row. */
export const REQUESTS_TABLE_SCREEN = "S83";

export const REQUEST_SEGMENT_FILTER = "segment";

/** REQ-01's own search prompt (B14 rule 19, DEF-510): it names WHAT the server
 *  really matches — `list_queryset` ORs request no, applicant name, address,
 *  phone and email, and nothing else. */
const SEARCH_PLACEHOLDER = "customers.serviceRequest.list.searchPlaceholder";

export function requestsTableConfig(
  t: (key: string, params?: Record<string, unknown>) => string,
  cells: {
    request: (row: ServiceRequestRow) => JSX.Element;
    type: (row: ServiceRequestRow) => JSX.Element;
    received: (row: ServiceRequestRow) => JSX.Element;
    channel: (row: ServiceRequestRow) => JSX.Element;
    age: (row: ServiceRequestRow) => JSX.Element;
    waitingOn: (row: ServiceRequestRow) => JSX.Element;
    state: (row: ServiceRequestRow) => JSX.Element;
    actions: (row: ServiceRequestRow) => JSX.Element;
  },
): TableConfig<ServiceRequestRow> {
  return {
    screenId: REQUESTS_TABLE_SCREEN,
    getRowId: (row) => row.id,
    searchFields: ["request_no", "applicant", "address", "phone", "email"],
    searchPlaceholder: SEARCH_PLACEHOLDER,
    filters: [
      {
        name: REQUEST_SEGMENT_FILTER,
        label: t("customers.serviceRequest.list.segment"),
        options: SERVICE_REQUEST_SEGMENTS.map((segment) => ({
          value: segment,
          label: t(`customers.serviceRequest.segment.${segment}`),
        })),
      },
    ],
    // ⚠ **`received_at` ASCENDING, AND IT IS THE SERVER'S ORDER.**
    // B19 §12.1's own footnote: *"Sorted by age, oldest first — the oldest
    // thing waiting is the thing to look at."* `list_queryset` orders by
    // `received_at, id` and accepts no `sort` param, so NO column is declared
    // sortable: a sort control would offer an ordering the request cannot ask
    // for. Reported rather than faked.
    // ── `BR-CUS-1046` (PO 2026-09-10, EXTENDED 2026-09-12) ──────────────────
    // *"It should always sort it by the creation order. The new newly created
    // entries should always show on the top."* The name is the SERVER's sort
    // name; `created` orders `created_at DESC, id DESC`.
    //
    // ⚠ **`created` IS NOT A COLUMN ON THIS TABLE, AND THAT IS DELIBERATE.**
    // Neither the blueprint nor B18 draws a Created column here, and the skill's
    // §2.5 is explicit that an absence is a decision: *say so, do not add it*.
    // So no header carries the glyph while the list is on its default, and the
    // sentence under the pager is what states the ordering — which is the
    // mechanism this screen already used for exactly that job.
    // ⚠ **THIS TAB OPENED ON `received_at` ASCENDING** — B18 §5.2.2's *"the oldest
    // thing waiting is the thing to look at"*. `RECEIVED` is sortable now, so that
    // ordering is one click that survives a refresh (`BR-CUS-1046` clause 2).
    defaultSort: { sort: "created", dir: "desc" },
    columns: [
      {
        key: "request_no",
        // `BR-CUS-1046` — SORTABLE, and the key IS the server's sort name.
        sortable: true,
        label: t("customers.serviceRequest.col.request"),
        identity: true,
        cell: cells.request,
      },
      { key: "type", label: t("customers.serviceRequest.col.type"), cell: cells.type },
      {
        key: "applicant",
        // `BR-CUS-1046` — SORTABLE, and the key IS the server's sort name.
        sortable: true,
        label: t("customers.serviceRequest.col.applicant"),
        cell: (row) => <TextOrNotSupplied value={row.applicant} t={t} />,
      },
      {
        key: "address",
        label: t("customers.serviceRequest.col.address"),
        cell: (row) => (
          <span>
            <TextOrNotSupplied value={row.address} t={t} />
            {row.address_unit !== null && row.address_unit !== "" && (
              <span className="text-neutral-700"> · {row.address_unit}</span>
            )}
          </span>
        ),
      },
      {
        key: "received_at",
        // `BR-CUS-1046` — SORTABLE, and the key IS the server's sort name.
        sortable: true,
        label: t("customers.serviceRequest.col.received"),
        cell: cells.received,
      },
      // ⚠ **ADDED 2026-09-04 (CR-068 wave B, `BR-CWP-076`).** Where the work
      // came from was on the detail header and nowhere a clerk scanning the
      // worklist could see it, and the portal is the first thing that ever
      // wrote the column. *Channel* is a heading `r10` draws, so `G14`'s
      // baseline does not move.
      {
        key: "channel",
        label: t("customers.serviceRequest.col.channel"),
        cell: cells.channel,
      },
      {
        key: "age_days",
        label: t("customers.serviceRequest.col.age"),
        numeric: true,
        cell: cells.age,
      },
      {
        key: "waiting_on",
        label: t("customers.serviceRequest.col.waitingOn"),
        cell: cells.waitingOn,
      },
      {
        key: "state",
        label: t("customers.serviceRequest.col.state"),
        // `BR-CUS-1046` — SORTABLE, and the key IS the server's sort name.
        sortable: true,
        cell: cells.state,
      },
      { key: "actions", label: t("customers.serviceRequest.col.actions"), cell: cells.actions },
    ],
  };
}

/**
 * The AGE cell.
 *
 * ✅ **THE ACCENT IS DRAWN — BR-CUS-106 (PO ruling 2026-08-25, closing decision
 * D4).** This comment said *"NO ACCENT, DELIBERATELY — decision D4"* until that
 * ruling, and the refusal was right while it stood: B19 §12.1's drawing bounds
 * the threshold only to *6–11 days*, B18 *proposed* 7 without authority, and
 * drawing an accent would have meant this file picking the number. The PO chose
 * **7 — one week — inclusive**.
 *
 * ⛔ **THIS COMPONENT STILL DOES NOT KNOW WHERE THE LINE IS, AND MUST NOT.**
 * It renders `row.age_is_accented`, which the server computes once
 * (`apps/customers/service_request.age_is_accented`). Re-deriving `age_days >=
 * 7` here would put the rule in two places, and the second copy is the one that
 * drifts. `AgeCell(row({age_days: 15, age_is_accented: false}))` renders PLAIN,
 * and that case is asserted — it is what proves the threshold is not here.
 *
 * `data-age-days` stays for the same reason it arrived: so a test reads the
 * value, not the sentence a translation may change.
 *
 * ── `CR-150-BRC09`, 2026-09-28 — TWO CHANGES, BOTH SO THIS STAYS ONE CELL ──
 *
 * ⚠ **(1) IT TAKES THE PAIR IT READS, NOT `ServiceRequestRow`.** The New
 * connects list draws the same AGING column off the same rule and the same
 * server flag, and B14 rule 43 says a piece of UI is a COMPONENT rather than
 * code copied into a second page. The prop was narrowed to one row type by
 * accident rather than by decision — this cell has only ever touched
 * `age_days` and `age_is_accented` — so it now declares exactly those and
 * BOTH rows satisfy it. **Copying it would have been a second threshold with
 * extra steps**, which is the thing the paragraph above exists to prevent.
 * Its home is really the shared kit beside `MoneyCell` and `DateCell`;
 * that move is its own sweep and is REPORTED rather than done in passing.
 *
 * ⚠ **(2) `null` IS NOT `false`, AND THIS CELL COLLAPSED THEM UNTIL TODAY.**
 * `seams.age_is_accented` returns `None` when **customers publishes no
 * threshold at all** — *nobody could be asked* — and the old
 * `age_is_accented === true` drew that identically to a genuine *not old*
 * row. That is `DEF-075`'s substitution, on the column a clerk chases work
 * from, and the server's own docstring names it: *"a missing implementer
 * answering 'not old' … `False` renders identically to a real plain row. The
 * caller states the absence instead."* Three renderings now, and the
 * difference costs **zero words** (B14 rule 33 — the reason a figure is not
 * accented is RATIONALE): accented reads in the accent, known-plain reads in
 * the body colour, and unknown reads muted, with `data-age-accented` carrying
 * `true` / `false` / `unknown` so a test reads the fact rather than a colour.
 * It is unreachable on the Requests list, where the threshold is resolved
 * in-module, and reachable on New connects, which asks through a seam.
 */
export function AgeCell(props: {
  row: { age_days?: number | null; age_is_accented?: boolean | null };
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const days = props.row.age_days;
  if (days === null || days === undefined) {
    return (
      <span role="note" className="text-sm text-neutral-700" data-tracks="BR-CUS-093">
        {props.t("customers.serviceRequest.list.ageUnknown")}
      </span>
    );
  }
  // The same posture `DisconnectsTab` takes for its accented `CUT DATE`: the
  // accent is a FACT the server decides and the cell renders.
  const accent = props.row.age_is_accented;
  const known = accent === true || accent === false;
  return (
    <span
      className={
        accent === true
          ? "tabular-nums text-accent-700"
          : known
            ? "tabular-nums"
            : "tabular-nums text-neutral-600"
      }
      data-age-days={days}
      data-age-accented={known ? (accent === true ? "true" : "false") : "unknown"}
      data-tracks="BR-CUS-106"
    >
      {props.t("customers.serviceRequest.list.ageDays", { days })}
    </span>
  );
}

/**
 * The TYPE cell.
 *
 * ✅ **`DISCONNECT` RENDERS LIKE ANY OTHER TYPE — BR-CUS-091** (PO 2026-08-24,
 * *"Yes customer can request it"*). Two artefacts disagreed; the ruling says the
 * LIST was right.
 *
 * ⚠ **`NOT YET CLASSIFIED` IS A REAL STATE AND NOT AN EMPTY CELL.** *"The
 * application never asked what kind of job this is — that is decided here."*
 * A blank would read as data we lost.
 */
export function TypeCell(props: {
  row: ServiceRequestRow;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  if (props.row.type === null) {
    return (
      <span className="text-sm uppercase tracking-wide text-neutral-700">
        {props.t("customers.serviceRequest.type.notYetClassified")}
      </span>
    );
  }
  return (
    <span className="text-sm uppercase tracking-wide" data-request-type={props.row.type}>
      {props.t(`customers.serviceRequest.type.${props.row.type}`)}
    </span>
  );
}

/**
 * ⛔ **THE SEGMENT THIS SCREEN OPENS ON — `DEF-CUS-5011`.**
 *
 * B19 §12.1 draws the strip as `All · **Open** · Waiting on customer ·
 * Approved · Closed` with **Open** selected, so `open` is the drawing's
 * default and this is it, named once rather than written twice.
 */
export const DEFAULT_SEGMENT: ServiceRequestSegment = "open";

/** The same state with one segment applied. Pure, so the rule is testable. */
export function withSegment(
  state: TableRequestState,
  segment: ServiceRequestSegment,
): TableRequestState {
  return { ...state, filters: { ...state.filters, [REQUEST_SEGMENT_FILTER]: segment } };
}

/**
 * ⛔ **AN ABSENT SEGMENT IS `all`, AND IT USED TO BE `open` — `DEF-CUS-5011`.**
 *
 * Two defaults, each written correctly, that nothing ever compared: the shared
 * `FilterBar` lights its `All` chip when NO filter is applied, and this
 * function independently read *no filter* as `open`. So the screen showed
 * **`All`, `aria-pressed="true"`**, over a request for `?segment=open` — six of
 * eight requests on `brazosbend`, under a control saying nothing was filtered.
 * Measured in Chromium, 2026-09-12: chip `All`, footer `1–18 of 18`, and the
 * one network call `?segment=open&page=1&per=50&sort=created&dir=desc` over a
 * tenant holding 20.
 *
 * **`All` means all now**, which is what the chip has always said, and the
 * screen's own default arrives as an APPLIED filter instead — so the clerk
 * reads `Stage: Open` on a list of the open ones, and clearing it really does
 * show everything. The alternative — teaching the shared `FilterBar` that one
 * screen's "no filter" is not "all" — would change twenty-odd lists on one
 * screen's authority.
 */
export function segmentFromState(state: TableRequestState): ServiceRequestSegment {
  const raw = state.filters[REQUEST_SEGMENT_FILTER];
  return (SERVICE_REQUEST_SEGMENTS as readonly string[]).includes(raw ?? "")
    ? (raw as ServiceRequestSegment)
    : "all";
}

export function serviceRequestsQueryKey(
  tenantScope: string,
  state: TableRequestState,
): readonly unknown[] {
  return [
    "service-requests",
    tenantScope,
    segmentFromState(state),
    state.q,
    state.page,
    state.per,
    // ⚠ **`state.sort` AND `state.dir` ARE IN THE KEY FOR THE REASON
    // `state.filters` IS (`BR-CUS-1046`).** Without them react-query answers a
    // re-sorted request from the previously-sorted page already in cache: the
    // header's arrow flips, the rows do not move, and no request is ever made.
    // That is `state.filters`' own defect one column along.
    state.sort,
    state.dir,
  ];
}

export interface ServiceRequestsListPageProps extends RegionalProps {
  client?: ApiClient;
  /**
   * **DOES THIS COPY OWN THE QUERY STRING? — DEF-664's embedded mode.**
   *
   * `true` (the default) is the standalone screen at `/requests`: table state
   * is parsed from and written back to the URL under BR-SHL-011's grammar, so
   * a view is shareable and survives a reload. Nothing about that route
   * changes.
   *
   * `false` is the copy that sits INSIDE the Accounts → Requests tab. It reads
   * NOTHING from the query string and writes NOTHING to it: `page`, `per`,
   * `q`, `sort` and the segment live in this component's own state for as long
   * as the tab is mounted.
   *
   * ⚠ **BOTH HALVES MATTER, AND THE READ HALF IS THE ONE THAT IS EASY TO
   * FORGET.** DEF-664 records the write collision — `AccountsListPage` and this
   * screen both call `setParams(serializeTableParams(...), {replace: true})`,
   * so nested they would overwrite each other's `?page=`. But `parseTableParams`
   * is just as damaging in the other direction: an embedded copy reading the
   * OUTER page's `?page=3&q=smith` would open the Requests tab on page 3 of a
   * search the user typed into the accounts list. So embedded mode starts from
   * `defaultRequestState` and never looks at the URL again.
   *
   * ⚠ **THIS DECIDES NO URL GRAMMAR.** DEF-664's stated blocker was that
   * namespacing the parameters is BR-SHL-011's to settle, not a lane's. Nothing
   * here namespaces anything: the embedded copy simply has no parameters, and
   * the standalone copy keeps the exact grammar it already had.
   *
   * ⛔ **THE PRICE, STATED RATHER THAN HIDDEN:** inside the tab a page/search/
   * segment choice is NOT in the URL, so it does not survive a reload and
   * cannot be pasted to a colleague. That is the deliberate trade — the tab's
   * URL belongs to the page it sits in — and the standalone screen is where a
   * shareable request view lives.
   */
  urlState?: boolean;
}

export function ServiceRequestsListPage(props: ServiceRequestsListPageProps) {
  const { t } = useTranslation();
  const translate = (key: string, params?: Record<string, unknown>): string => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  const { timeZone, dateFormat } = useRegional(props);
  const ownsUrl = props.urlState !== false;
  const [params, setParams] = useSearchParams();

  const config = useMemo(
    () =>
      requestsTableConfig(translate, {
        request: (row) => (
          <RequestNumber
            requestNo={row.request_no}
            absence={row.number_absence}
            t={translate}
            // ⚠ **THE NUMBER IS THE DOOR — `DEF-CUS-6005`.** PO, from the live
            // product: *"in list view user cannot click on SR-26-0013 and open
            // it"*. The eye below stays; this is the second door onto the SAME
            // address, built from the SAME `serviceRequestPath` so the two
            // cannot drift.
            //
            // ⚠ **THE DRAWING SHOWS THIS CELL AS PLAIN TEXT, AND THE DIVERGENCE
            // IS STAMPED RATHER THAN SILENT** (B14 rule 41). p085 of the
            // Accounts blueprint draws `REQUEST #` unlinked beside a boxed,
            // clearly-labelled `↗ Open` button per row. Our product obeys B14
            // rule 15 — *"row actions are ICONS with tooltips, never text
            // links"* — so that labelled button is an unlabelled eye here, and
            // the drawing's plain-text number was safe only because the drawn
            // door was unmistakable. Ours is not. The affordance the drawing
            // relies on is restored on the element a clerk actually reaches
            // for.
            to={tenantPath(serviceRequestPath(row.id))}
          />
        ),
        type: (row) => <TypeCell row={row} t={translate} />,
        received: (row) => (
          <DateOrNotSupplied
            value={row.received_at}
            t={translate}
            timeZone={timeZone}
            dateFormat={dateFormat}
          />
        ),
        // ⚠ **A KNOWN CHANNEL IS TRANSLATED AND AN UNKNOWN ONE IS PRINTED AS
        // IT STANDS**, which is what free text against a service-side
        // vocabulary means: five values have words in eleven catalogues and a
        // sixth a tenant's data may carry does not, and inventing one would be
        // worse than showing the value. A row with no channel at all is an
        // em-dash: nothing recorded where it came from, which is true of every
        // request this product wrote before the portal existed.
        channel: (row) =>
          row.channel === null || row.channel === "" ? (
            <span aria-hidden="true">—</span>
          ) : (
            <span data-channel={row.channel}>
              {translate(`customers.serviceRequest.channel.${row.channel}`, {
                defaultValue: row.channel,
              })}
            </span>
          ),
        age: (row) => <AgeCell row={row} t={translate} />,
        // ⚠ A request that is waiting on NOTHING renders an em-dash and that is
        // correct here and only here: `waiting_on` null means *nobody parked
        // this*, which IS "none", not "we do not know". B19 §12.1 draws exactly
        // that on four of its eight rows.
        waitingOn: (row) =>
          row.waiting_on === null || row.waiting_on === "" ? (
            <span aria-hidden="true">—</span>
          ) : (
            <span>{translate(`customers.serviceRequest.waitingOn.${row.waiting_on}`, {
              defaultValue: row.waiting_on,
            })}</span>
          ),
        state: (row) => <RequestStatePill state={row.state} t={translate} />,
        actions: (row) => (
          <RowActions>
            <RowActionLink
              label={translate("customers.serviceRequest.action.open")}
              icon={<EyeIcon />}
              to={tenantPath(serviceRequestPath(row.id))}
            />
            {/* ✎ `Resume` on a draft, `Edit` while the request is still being
                worked, NOTHING once it is decided (`DEF-CUS-6427`, PO
                2026-09-23: *"there is no edit available on list view"*). Two
                glyphs is B14 rule 15's maximum. */}
            <RequestEditRowAction requestId={row.id} state={row.state} t={translate} />
          </RowActions>
        ),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, timeZone, dateFormat],
  );

  // The embedded copy's table state. Seeded from the config's declared
  // defaults — NOT from `params` — so the outer page's `?page=`/`?q=` can never
  // leak into this list (see `urlState` above). The hook is called
  // unconditionally, as hooks must be; only which value is READ depends on the
  // prop.
  // `DEF-CUS-5011` — seeded with the drawn default as an APPLIED filter, so the
  // chip reads `Stage: Open` rather than `All`. It is in the STORED state and
  // not wrapped around the read, because a wrapper cannot tell "the screen just
  // opened" from "the clerk pressed All", and would undo the clear.
  const [ownState, setOwnState] = useState<TableRequestState>(() =>
    withSegment(defaultRequestState(config), DEFAULT_SEGMENT),
  );

  /**
   * ⛔ **`DEF-CUS-5011`, THE STANDALONE COPY'S HALF — AND WHY IT IS A REF AND
   * NOT A URL WRITE.**
   *
   * A bare `/requests` carries no `f.segment`, and for this copy the URL *is*
   * the state — so "the screen just opened" and "the clerk pressed All" are
   * the same query string, and a wrapper that reads an absent segment as
   * `open` would silently undo the clear. Something has to remember which it
   * is, and there are only two places to put it.
   *
   * **Seeding the URL on mount was tried and abandoned.** It works, and it
   * breaks `DEF-664`'s own case — *"the standalone screen writes its table
   * state to the URL"* asserts the address starts EMPTY and gains parameters
   * only when a clerk does something. Rewriting the address on arrival makes
   * that false and turns every first paint into a navigation.
   *
   * So the fact lives here: the default is applied until the clerk changes
   * something, and after that the URL is the whole truth. The FIRST render
   * therefore asks for `open` — not `all` and then `open` a round trip later.
   *
   * ⛔ **THE PRICE, STATED RATHER THAN HIDDEN:** a cleared segment is not
   * shareable — paste the address after pressing `All` and it opens on `Open`
   * again, because a bare URL is the default. Nothing on screen lies while
   * that happens (the chip says `Show: Open` and the request says `open`),
   * which is the whole of this defect. It is the same class as
   * `DEF-CUS-5091` — table state that does not survive a reload on this
   * screen — and it belongs to that row's fix, not to this one.
   */
  const touched = useRef(false);
  const parsed = ownsUrl ? parseTableParams(params, config) : ownState;
  const state =
    !touched.current && parsed.filters[REQUEST_SEGMENT_FILTER] === undefined
      ? withSegment(parsed, DEFAULT_SEGMENT)
      : parsed;
  function onStateChange(next: TableRequestState): void {
    // `DEF-CUS-5011` — from here on an absent segment means the clerk cleared
    // it, so the default stops being applied and `All` means all.
    touched.current = true;
    if (!ownsUrl) {
      // ⛔ NOT `setParams`, and not "setParams with a namespace" either. The
      // embedded copy leaves the query string entirely to the page it sits
      // inside — that is the whole of DEF-664's fix.
      setOwnState(next);
      return;
    }
    setParams(serializeTableParams(next, config), { replace: true });
  }

  const listQuery = useQuery({
    queryKey: serviceRequestsQueryKey(SERVICE_REQUESTS_ROUTE, state),
    queryFn: () =>
      listServiceRequests(
        {
          segment: segmentFromState(state),
          q: state.q,
          page: state.page,
          per: state.per,
          // `BR-CUS-1046` — the clerk's chosen column reaches the `ORDER BY`.
          sort: state.sort,
          dir: state.dir,
        },
        client,
      ),
  });

  const kpis = listQuery.data?.kpis;
  const tiles: KpiTile[] = [
    {
      id: "open",
      label: t("customers.serviceRequest.kpi.open"),
      value: kpis?.open ?? 0,
      detail: t("customers.serviceRequest.kpi.openDetail"),
    },
    {
      id: "waiting",
      label: t("customers.serviceRequest.kpi.waiting"),
      value: kpis?.waiting_on_customer ?? 0,
      detail: t("customers.serviceRequest.kpi.waitingDetail"),
    },
    {
      id: "oldest",
      label: t("customers.serviceRequest.kpi.oldest"),
      // ⚠ NOT `?? 0`. A tenant with nothing parked has NO oldest waiting item,
      // and "0 days" is a different claim from "there is none" — the
      // `AwaitsCell` precedent one screen over.
      value:
        kpis?.oldest_waiting.days === null || kpis?.oldest_waiting.days === undefined
          ? t("customers.serviceRequest.kpi.oldestNone")
          : t("customers.serviceRequest.list.ageDays", { days: kpis.oldest_waiting.days }),
      detail:
        kpis?.oldest_waiting.request_no === null || kpis?.oldest_waiting.request_no === undefined
          ? undefined
          : `${kpis.oldest_waiting.request_no} · ${t(
              `customers.serviceRequest.waitingOn.${kpis.oldest_waiting.waiting_on ?? "unknown"}`,
              { defaultValue: kpis.oldest_waiting.waiting_on ?? "" },
            )}`,
    },
    {
      id: "approved",
      label: t("customers.serviceRequest.kpi.approvedNotStarted"),
      value: kpis?.approved_not_started ?? 0,
      detail: t("customers.serviceRequest.kpi.approvedNotStartedDetail"),
    },
    {
      id: "refused",
      label: t("customers.serviceRequest.kpi.refusedThisMonth"),
      value: kpis?.refused_this_month ?? 0,
      detail: t("customers.serviceRequest.kpi.refusedThisMonthDetail"),
    },
  ];

  return (
    <div data-embedded={ownsUrl ? undefined : ""}>
      {/* ⛔ **THE PAGE CHROME IS THE STANDALONE SCREEN'S, AND IT IS SUPPRESSED
          INSIDE THE TAB (DEF-664).** The `← Dashboard` back link, the
          `SERVICE REQUESTS` kicker, the `Requests.` H1 and the `+ New request`
          primary all belong to a screen that IS the page. In the Accounts →
          Requests tab the user is already under an `Accounts` H1 with its own
          tab strip and its own primary slot, so rendering this would give the
          tab TWO page headers, two H1s and a second primary — which breaks
          B14 rule 4 / BR-SHL-044's "exactly one primary" on that screen.
          What stays is everything that is about the LIST: the KPI strip, the
          toolbar, the table and the pager.

          ⛔ **THE SENTENCE THAT USED TO BE HERE IS DEF-729, AND IT IS THE
          MITIGATION THAT FAILED — NOT THE SUPPRESSION.** It read: *"The `+ New
          request` route is not lost to the embedded user — the empty state's
          CTA below still offers it, which is where a tab with no rows needs it
          most."* **That is true only while the list is EMPTY.** The PO's tab
          held one row (`SR-26-0001`), so the empty state never rendered and
          there was no way to raise a request at all. A fallback that fires only
          in the state where the feature is least needed is not a fallback, and
          every test passed over it because the standalone route has the button
          and the empty state has the CTA — nothing asserted the case that
          actually ships.

          ✅ The way in is now `AccountsListPage`'s ONE primary slot, which
          carries the ACTIVE tab's create action and relabels to `+ New request`
          here. That satisfies exactly-one-primary rather than fighting it, and
          it is what r10 draws. The empty state's CTA below stays as it is — it
          is a second door, no longer the only one — and
          `AccountsCreateEntry.test.tsx` asserts the missing case: a tab WITH
          ROWS offers a way to create one. */}
      {ownsUrl && (
        <PageHeader
          kicker={t("customers.serviceRequest.list.kicker")}
          title={t("customers.serviceRequest.list.title")}
          backTo={{
            to: tenantPath(DASHBOARD_ROUTE),
            label: t("customers.serviceRequest.list.back"),
          }}
          primaryAction={
            <Button
              variant="primary"
              onClick={() => navigate(tenantPath(SERVICE_REQUEST_NEW_ROUTE))}
            >
              {t("customers.serviceRequest.action.new")}
            </Button>
          }
        />
      )}

      <KPIStrip kpis={tiles} loading={listQuery.isLoading} />

      <DataTable<ServiceRequestRow>
        config={config}
        state={state}
        onStateChange={onStateChange}
        rows={listQuery.data?.results ?? []}
        totalRows={listQuery.data?.count ?? null}
        loading={listQuery.isLoading}
        error={
          listQuery.isError
            ? {
                reason: t("customers.serviceRequest.list.loadFailed"),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        // ⚠ **THE THIRD INSTANCE OF DEF-1701, AND IT WAS A STATED ABSENCE
        //    RATHER THAN AN UNKNOWN ONE.** This file's own lifecycle trailer
        //    read *"the segment FILTER is still not reachable from either copy:
        //    this screen passes no `filterBarSlot`, which predates this packet
        //    and is untouched by it"* — a comment naming a gap, which hard-won
        //    law 1 says is a note and never a plan. Meanwhile §63-67 of this
        //    file's header had already RULED the shape: *"the five segments
        //    render as a filter CHIP … the URL as `f.segment=` and a reload
        //    restores it (BR-SHL-011)"*. The decision was made, the config
        //    declared it, and the one line that renders it was never written.
        //
        //    Found by G45's sweep, not by the PO's screenshots — CR-045 wave D
        //    was sized at the two screens the PO could see.
        filterBarSlot={
          <FilterBar filters={config.filters ?? []} state={state} onStateChange={onStateChange} />
        }
        empty={{
          title: t("customers.serviceRequest.list.emptyTitle"),
          helper: t("customers.serviceRequest.list.emptyHelper"),
          ctaLabel: t("customers.serviceRequest.action.new"),
          onCta: () => navigate(tenantPath(SERVICE_REQUEST_NEW_ROUTE)),
        }}
      />

      {/* B19 §12.1's own footnote, which is a statement about the SORT and is
          true: the server orders by `received_at` ascending and accepts no
          other ordering. */}
      <p className="mt-2 text-sm text-neutral-700">
        {t("customers.serviceRequest.list.sortFootnote")}
      </p>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W4 task 4.11 · B19 §12.1 · B18 §5.3.1/§5.3.2
// generated: 2026-08-24 by the CR-031 W4 FRONTEND lane (M3)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: tsc✔ eslint✔ vitest✔ · G13✔ G31✔ G37✔ G40✔
// exceptions: ✅ the AGE accent exception is CLOSED — **BR-CUS-106** (PO
//   2026-08-25) ruled D4 at seven days inclusive; the accent is drawn from the
//   server's `age_is_accented` and the threshold is not in this file · E3 the eight-tab strip and
//   its superscript counts are NOT drawn — `AccountsListPage.tsx` and
//   `components/PageHeader.tsx` are other lanes' files; the Requests tab body
//   is one line and is OWED · E3 no `Export` control: `POST /exports`
//   registers no `service_requests` resource (BR-SHL-010) · E3 no column is
//   sortable: `list_queryset` accepts no `sort` param, so a sort control would
//   offer an ordering the request cannot ask for · E3 the pager prints the
//   shared `1–8 of 42`; B19's *"(filtered from 118)"* needs an unfiltered total
//   the envelope does not carry — REPORTED
// ── AMENDED 2026-08-25 · lane F-REQ · DEF-664 ─────────────
// packet: DEF-664 (12-governance/10-defect-log.csv) + its 2026-08-25 escalation
//   in 12-governance/11-change-requests.md — the PO reported it from production
//   on v2.46.0
// change: `urlState?: boolean` — an EMBEDDED MODE for the Accounts → Requests
//   tab. Embedded: table state in component state, the query string neither read
//   nor written, standalone page chrome suppressed. Standalone `/requests`:
//   byte-identical behaviour, shareable links unchanged.
// gates: tsc✔ eslint --max-warnings 0✔ vitest 16/16 in this file's suite✔
// proved RED first (hard-won law 7), twice:
//   (1) embedded copy made to call `setParams` →
//       `expected '?sort=received_at&dir=asc&page=2' to be
//        '?tab=requests&sort=account_no&dir=desc&page=3&per=100&q=smith'`
//       — which is DEF-664's collision reproduced exactly: the ACCOUNTS list's
//       own params destroyed by the nested requests list;
//   (2) `ownsUrl` forced false → the standalone cases went red
//       (`expected '' to contain 'page=2'` and no `<h1>` at all), proving the
//       embedded cases alone cannot protect `/requests`.
// exceptions: E3 no SORT case — `requestsTableConfig` declares no sortable
//   column (the server accepts no `sort`), so DataTable draws no sort control
//   and there is nothing to click; the pager and the rows-per-page select are
//   exercised instead · E3 the embedded copy's page/search/segment do NOT
//   survive a reload and cannot be pasted to a colleague — the tab's URL
//   belongs to the page it sits in, and `/requests` is where a shareable
//   request view lives · ✅ **E3 CLOSED 2026-08-27 (DEF-1701)** — this read
//   *"the segment FILTER is still not reachable from either copy: this screen
//   passes no `filterBarSlot`"*. It is passed now, in both copies; the segment
//   is a removable chip and a `+ Filter` group, exactly as §63-67 ruled
//   · **[TABCTA 2026-08-26 · DEF-729]** E2 **the embedded copy's claim that the
//   `+ New request` route was "not lost … the empty state's CTA below still
//   offers it" IS SUPERSEDED — the SUPPRESSION was right and the MITIGATION was
//   not.** It held only while the list was EMPTY, and the PO's tab had one row,
//   so there was no way in at all. The header stays suppressed (two H1s and two
//   primaries would break B14 rule 4 / BR-SHL-044); the way in is
//   `AccountsListPage`'s ONE primary slot, which now carries the ACTIVE tab's
//   create action. No code in this file changed — only the comment that was
//   false — and the missing assertion lives in `AccountsCreateEntry.test.tsx`:
//   a tab WITH ROWS offers a way to create one.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
