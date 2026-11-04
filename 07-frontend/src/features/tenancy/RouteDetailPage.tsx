// ── Trace ──────────────────────────────────────────────
// Change:  CR-029 RC-W3-T3 (PO 2026-08-23) — **SET-06D, a NEW screen**: the
//          route detail the upgraded prototype added and this product has never
//          had. Five tabs, a Facts rail, and `walk_order`'s FIRST WRITER.
// Design:  04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §3, §4
// Story:   US-MET-006 (EP-MET-02 §Stories)  Screens: SET-06D
// Rules:   D3 (*"Confirmed"* — build the sequence surface) · D6 (**NO reader
//          row on the rail**) · D10 (a route serves a service SET) ·
//          D11 (*"Per premises"* — the sequence grain) · D12 (**NO Balance
//          column** on Accounts) · BR-MET-033 (membership drives the counts) ·
//          BR-MET-075 (meters on route = available − excluded) · BR-MET-076
//          (the Draft pill) · BR-MET-078 (NO money) · BR-AUD-010 (a per-entity
//          Audit tab RENDERS the entity's rows and links to S61) ·
//          BR-SHL-011 (the open tab is URL state) · BR-SHL-020 (the A18 states)
// B14:     rule 1 (the header's ← names where it EXITS to) · 2 (one page
//          header) · 6 (danger tier) · 15 (icon row actions) · 18 (80%) ·
//          20 (one table type) · 21 (Tailwind, NO stylesheet class)
// Tests:   RoutesCyclesDetail.test.tsx
// ───────────────────────────────────────────────────────
/**
 * SET-06D — what a route IS, on one screen.
 *
 * ⚠ **THREE THINGS ON THIS SCREEN CONTRADICT THE DRAWING IT WAS BUILT FROM,
 * AND EACH IS A PO RULING** (B17 §3):
 *
 *   · **D6 — there is no reader anywhere.** The screenshot puts an inline
 *     reader edit on this rail. The PO ruled *"not required"*, so reader
 *     assignment is out of CR-029 entirely: `routes.assigned_to` keeps its
 *     value, no control writes it, and no row renders it. The fixture in the
 *     suite carries a reader name precisely so "the column is empty" cannot be
 *     mistaken for "the rule is honoured".
 *
 *   · **D11 — the walking order is PER PREMISES.** The screenshot numbers
 *     1408 Elm's three units 0142/0143/0144 and Cedar Ct's three units all
 *     0145. B17 §3 records that the second reading is the right one: *"a
 *     three-unit building is ONE stop at one sequence number, not three"*. A
 *     reader climbs those steps once.
 *
 *   · **D12 — the Accounts tab is status only.** The screenshot draws a
 *     Balance column ($142.30, $88.10…). Routes and cycles are GROUPING ONLY
 *     (BR-MET-078, hardened by this CR), so no money reaches this file.
 *
 * ⚠ **AMENDED 2026-08-23 (RC-W3c) — THE FOUR THINGS THIS SCREEN "COULD NOT
 * FINISH" ARE FINISHED, AND THE OLD PARAGRAPH IS DELETED RATHER THAN LEFT.**
 * It said RC-W1 had landed `route_premises_orders`, `route_meter_exclusions.
 * reason` and `read_windows` as TABLES with *"no endpoint for any of them"*, so
 * the reorder 404'd, exclusions had no reason and Read history was a stated
 * absence. RC-W3b mounted all of it. Every one of those sentences was false the
 * moment that lane landed, and a screen that goes on apologising for a shipped
 * feature is how a feature stays invisible (hard-won law 1, hard-won law 2).
 *
 * What is REAL on this screen now:
 *   · **the walking order SAVES** — `PUT /routes/{id}/premises-order`, the
 *     first writer `walk_order` has ever had (B17 §5 gap G5, closed);
 *   · **the saved walk is READ BACK** — `route_detail.premises_order`, so a
 *     reorder survives a refresh and a later route edit;
 *   · **an exclusion explains itself in place** — the two words ride on the
 *     meter row;
 *   · **Read history is a table of closed windows**, and **the Accounts tab
 *     lists real accounts** — status only, no money (D12).
 *
 * ⚠ **B14 RULE 21** — Tailwind utilities throughout; this file adds no class to
 * any stylesheet and borrows none from `met-*` or `settings-*`.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  deactivateRoute,
  deleteRoute,
  getRouteAccounts,
  getRouteDetail,
  getRouteMeterPicker,
  getRouteReadWindows,
  saveRoutePremisesOrder,
} from "@/api/endpoints";
import type {
  RouteAccountsPayload,
  RoutePickerMeter,
  RouteReadWindowRow,
} from "@/api/endpoints";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { CustomFieldsView } from "@/components/CustomFields";
import { DateCell, formatDate } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { AuditTab } from "@/features/metering/PremisesDetailPage";
import { premisesDetailPath, unitDetailPath, useRegional } from "@/features/metering/meteringShared";
import { InlineLinkTo } from "@/components/Surfaces";
import { assetDetailPath } from "@/features/assets/assetsShared";
import { accountDetailPath } from "@/features/customers/customersShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  ChipList,
  FactsRail,
  RC_DESC,
  RC_MUTED,
  ROUTES_CYCLES_PATH,
  StatedAbsence,
  cycleDetailPath,
  pluralKey,
  reorderStops,
  routeWizardPath,
  stopsFromServedOrder,
  walkOrderPayload,
} from "./routesCyclesShared";
import type { RouteStop } from "./routesCyclesShared";
import { lifecycleTone } from "./SettingsRoutesCyclesTab";
import { RouteReadFormatPanel } from "@/features/metering/ReadFormatPointer";
import {
  RefusalNotice,
  SettingsDenied,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "./settingsShared";
import type { Refusal, Translator } from "./settingsShared";

// ── Pure pieces ────────────────────────────────────────────────────────────

/** B17 §4 — the FIVE tabs, in the prototype's own order. Never a sixth. */
export const ROUTE_DETAIL_TABS = ["premises", "units", "assets", "accounts", "audit"] as const;
export type RouteDetailTab = (typeof ROUTE_DETAIL_TABS)[number];

/** BR-SHL-011's fallback law: an unknown `?tab=` falls back, never errors. */
export function routeTabFrom(raw: string | null | undefined): RouteDetailTab {
  return ROUTE_DETAIL_TABS.includes(raw as RouteDetailTab) ? (raw as RouteDetailTab) : "premises";
}

export const routeDetailQueryKey = (routeId: string) => ["routes", "detail", routeId] as const;
export const routeMetersQueryKey = (routeId: string) => ["routes", "meters", routeId] as const;
export const routeReadWindowsQueryKey = (routeId: string) =>
  ["routes", "read-windows", routeId] as const;
export const routeAccountsQueryKey = (routeId: string) => ["routes", "accounts", routeId] as const;

/** Meters grouped by the premises they sit on — the Premises tab's per-stop
 *  count and the "no meter · verify" flag both read this. */
export function metersByPremises(
  meters: readonly RoutePickerMeter[],
): Map<string, RoutePickerMeter[]> {
  const byPremises = new Map<string, RoutePickerMeter[]>();
  for (const meter of meters) {
    const list = byPremises.get(meter.premises_id);
    if (list === undefined) {
      byPremises.set(meter.premises_id, [meter]);
    } else {
      list.push(meter);
    }
  }
  return byPremises;
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface RouteDetailPageProps {
  client?: ApiClient;
  readOnly?: boolean;
}

export function RouteDetailPage(props: RouteDetailPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const params = useParams();
  const routeId = params.routeId ?? "";
  const [search, setSearch] = useSearchParams();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const queryClient = useQueryClient();

  const tab = routeTabFrom(search.get("tab"));
  const readOnly = props.readOnly ?? false;
  const readOnlyTitle = readOnly ? t("settings.readOnlyReason") : undefined;

  const [order, setOrder] = useState<RouteStop[] | null>(null);
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [action, setAction] = useState<"deactivate" | "delete" | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const routeQuery = useQuery({
    queryKey: routeDetailQueryKey(routeId),
    queryFn: () => getRouteDetail(routeId, client),
    enabled: routeId !== "",
  });

  // ⚠ **NOTHING IS SENT BUT THE ROUTE ID (`CR-131-BRC07` step 5).** This built
  // one `unit_id` parameter per member — 52 characters each, 37,994 of them on
  // a 726-unit route against a 4–8 KB limit, so the request never arrived. The
  // route knows its own premises; asking it is one id.
  const metersQuery = useQuery({
    queryKey: routeMetersQueryKey(routeId),
    queryFn: () => getRouteMeterPicker({ routeId, per: "all" }, client),
    enabled: routeId !== "",
  });

  // B17 §4 — SET-06D's Read history. Fetched only on the tab that draws it: a
  // route that has been walked for a year has a real page of rows behind it.
  const readWindowsQuery = useQuery({
    queryKey: routeReadWindowsQueryKey(routeId),
    queryFn: () => getRouteReadWindows(routeId, client),
    enabled: routeId !== "" && tab === "audit",
  });

  const accountsQuery = useQuery({
    queryKey: routeAccountsQueryKey(routeId),
    queryFn: () => getRouteAccounts(routeId, client),
    enabled: routeId !== "" && tab === "accounts",
  });

  const orderMutation = useMutation({
    mutationFn: (stops: readonly RouteStop[]) =>
      saveRoutePremisesOrder(routeId, walkOrderPayload(stops), client),
    onSuccess: () => {
      // ⚠ INVALIDATE, THEN DROP THE LOCAL EDIT — in that order. The detail
      // read carries `premises_order`, so the saved walk comes back from the
      // server and the screen stops holding a private copy of it.
      void queryClient.invalidateQueries({ queryKey: routeDetailQueryKey(routeId) });
      setOrder(null);
      setRefusal(null);
      fireToast(t("settings.routes.detail.orderSaved"));
    },
    onError: (error: unknown) => {
      // ⚠ **THE 404 BRANCH IS GONE (RC-W3c).** It rendered *"the walking order
      // can't be saved yet — nothing stores it on the server"*, which stopped
      // being true when RC-W3b mounted the route. Keeping it would have left a
      // false sentence one 404 away from a user, so the refusal is now the
      // SERVER's own in every case — omitted stop, duplicate stop, duplicate
      // position, a premises that is not on this route — rendered through the
      // one envelope reader every settings screen uses.
      setRefusal(refusalOf(error, translate));
    },
  });

  const lifecycleMutation = useMutation({
    mutationFn: (kind: "deactivate" | "delete") =>
      kind === "deactivate"
        ? deactivateRoute(routeId, client).then(() => undefined)
        : deleteRoute(routeId, client),
    onSuccess: (_result, kind) => {
      setAction(null);
      setRefusal(null);
      fireToast(
        t(kind === "deactivate" ? "settings.routes.deactivated" : "settings.routes.deleted", {
          code: routeQuery.data?.code ?? "",
        }),
      );
      if (kind === "delete") {
        navigate(tenantPath(ROUTES_CYCLES_PATH));
      } else {
        void queryClient.invalidateQueries({ queryKey: routeDetailQueryKey(routeId) });
      }
    },
    onError: (error: unknown) => {
      setAction(null);
      setRefusal(refusalOf(error, translate));
    },
  });

  // CR-161-BRC10 W4 — the tenant's own date format for a date answer. Called
  // before the early returns below (rules of hooks).
  const regional = useRegional({});
  if (routeQuery.isPending) {
    return <LoadingSkeleton variant="table" />; // A18 §3
  }
  const route = routeQuery.data;
  if (route === undefined) {
    if (isPermissionDenied(routeQuery.error)) {
      return <SettingsDenied helper={t("settings.denied.tab")} />;
    }
    return (
      <FailedWithRetry
        title={t("settings.routes.failedTitle")}
        reason={apiErrorText(routeQuery.error, translate)}
        onRetry={() => void routeQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(ROUTES_CYCLES_PATH))}
      />
    );
  }

  // ⚠ **THE SERVER'S OWN WALK, READ BACK (D11).** `route_detail.premises_order`
  // is the ruled per-premises list; before RC-W3b nothing served it and the
  // screen inferred an order from the superseded per-unit column, so a saved
  // walk could not be seen again. `stopsFromServedOrder` falls back to that
  // inference only for a route nobody has sequenced.
  const storedStops = stopsFromServedOrder(route.premises_order, route.membership);
  const stops = order ?? storedStops;
  const meters = metersQuery.data?.meters ?? [];
  const byPremises = metersByPremises(meters);
  const dirty = order !== null;

  function moveStop(from: number, to: number): void {
    setOrder(reorderStops(stops, from, to));
  }

  // ── The Facts rail (B17 §4) ──────────────────────────────────────────────
  // ⚠ NO READER ROW (D6). The rows below are the ruled seven and nothing else.
  const facts = [
    { label: t("settings.routes.detail.fact.routeNo"), value: route.code },
    {
      label: t("settings.routes.detail.fact.readType"),
      value:
        route.route_type === null
          ? t("settings.unwiredCount")
          : t(`settings.routes.type.${route.route_type}`),
    },
    {
      label: t("settings.routes.detail.fact.services"),
      value: (
        <ChipList
          items={route.services}
          empty={<span className={RC_MUTED}>{t("settings.routes.wizard.serviceAll")}</span>}
        />
      ),
    },
    {
      label: t("settings.routes.detail.fact.area"),
      value: route.area_name ?? route.area_code ?? t("settings.unwiredCount"),
    },
    {
      label: t("settings.routes.detail.fact.members"),
      value: t("settings.routes.membersCell", { premises: route.premises, units: route.units }),
    },
    {
      // BR-MET-075 — both halves, always. An exclusion is never invisible.
      label: t("settings.routes.detail.fact.meters"),
      value: t("settings.routes.detail.metersOnRoute", {
        meters: route.meters,
        excluded: route.meters_excluded,
      }),
    },
    {
      label: t("settings.routes.detail.fact.cycle"),
      value:
        route.cycle_id === null || route.cycle_code === null ? (
          <span className={RC_MUTED}>{t("settings.routes.wizard.noCycle")}</span>
        ) : (
          <a className="text-accent underline" href={tenantPath(cycleDetailPath(route.cycle_id))}>
            {route.cycle_code}
          </a>
        ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        backTo={{ to: tenantPath(ROUTES_CYCLES_PATH), label: t("settings.tab.routesCycles") }}
        kicker={t("settings.routes.wizard.headKicker")}
        title={route.name === null ? route.code : `${route.code} · ${route.name}`}
        status={
          <StatusPill tone={lifecycleTone(route.status)}>
            {t(`settings.routes.status.${route.status}`)}
          </StatusPill>
        }
        secondaryActions={
          <>
            <Button
              variant="secondary"
              disabled={readOnly}
              title={readOnlyTitle}
              onClick={() => navigate(tenantPath(routeWizardPath(route.id)))}
            >
              {t("settings.routes.detail.edit")}
            </Button>
            <Button
              variant="secondary"
              disabled={readOnly || route.status !== "active"}
              title={readOnlyTitle}
              onClick={() => setAction("deactivate")}
            >
              {t("settings.reference.deactivate")}
            </Button>
            {/* B14 rule 6 — a destructive commit is the DANGER tier, never the
                standard primary. */}
            <Button
              variant="danger"
              disabled={readOnly}
              title={readOnlyTitle}
              onClick={() => setAction("delete")}
            >
              {t("settings.reference.delete")}
            </Button>
          </>
        }
        tabs={ROUTE_DETAIL_TABS.map((id) => ({
          id,
          label: t(`settings.routes.detail.tab.${id}`),
        }))}
        activeTabId={tab}
        tabsLabel={t("settings.routes.detail.tabsLabel")}
        onTabSelect={(next) => {
          const params2 = new URLSearchParams(search);
          params2.set("tab", next.id);
          setSearch(params2, { replace: true });
        }}
      />

      <RefusalNotice refusal={refusal} />

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        <div className="min-w-0 flex-1">
          {tab === "premises" && (
            <PremisesTab
              stops={stops}
              byPremises={byPremises}
              dirty={dirty}
              saving={orderMutation.isPending}
              readOnly={readOnly}
              readOnlyTitle={readOnlyTitle}
              t={translate}
              onMove={moveStop}
              onDragStart={setDragFrom}
              dragFrom={dragFrom}
              onReset={() => setOrder(null)}
              onSave={() => orderMutation.mutate(stops)}
            />
          )}
          {tab === "units" && <UnitsTab route={route} t={translate} />}
          {tab === "assets" && <AssetsTab meters={meters} t={translate} />}
          {tab === "accounts" && (
            <AccountsTab
              payload={accountsQuery.data ?? null}
              loading={accountsQuery.isPending}
              t={translate}
            />
          )}
          {tab === "audit" && (
            <div className="flex flex-col gap-4">
              {/* B17 §4 — Read history, SERVED (`GET /routes/{id}/read-windows`). */}
              <ReadHistory
                windows={readWindowsQuery.data ?? []}
                loading={readWindowsQuery.isPending}
                t={translate}
              />
              {/* BR-AUD-010 — the change log RENDERS here, route-scoped, and
                  links to S61. It is the CR-23/CR-028 pattern and deliberately
                  NOT a jump: a reader who clicks Audit to read the history was
                  being navigated off the screen instead. One audit surface —
                  the rows come from the same `GET /audit-log` with the same
                  `f.entity_type`/`f.entity_id` the link carries, so masking and
                  retention cannot diverge per module. */}
              <AuditTab entityType="route" entityId={route.id} t={translate} regional={{}} />
            </div>
          )}
        </div>
        <FactsRail title={t("settings.routes.detail.factsTitle")} facts={facts} />
      </div>
      {/* CR-192-BRC10 (MQ-033 task 11) — the route's own read format, and what
          each of its services resolves to (route → cycle → service). */}
      <RouteReadFormatPanel
        routeId={route.id}
        service={route.services.length === 1 ? (route.services[0] ?? null) : route.service_code}
        readOnly={readOnly}
        client={client}
      />
      {/* CR-161-BRC10 W4 — the utility's OWN route fields, read-only
          (`ROUTE_PAGE`). Nothing at all when none is placed here. */}
      <CustomFieldsView
        entity="routes"
        screen="ROUTE_PAGE"
        values={route.custom_data ?? {}}
        formatDate={(iso) => formatDate(iso, regional.timeZone, regional.dateFormat)}
        client={client}
      />

      {action !== null && (
        <ConfirmDialog
          // B14 rule 6 (DEF-718): BOTH actions this dialog serves — deactivate and delete — are destructive.
          confirmVariant="danger"
          title={t(
            action === "deactivate"
              ? "settings.routes.deactivateTitle"
              : "settings.routes.deleteTitle",
            { code: route.code },
          )}
          consequence={t(
            action === "deactivate"
              ? "settings.routes.deactivateBody"
              : "settings.routes.deleteBody",
            { code: route.code, members: route.members },
          )}
          confirmLabel={t(
            action === "deactivate"
              ? "settings.routes.deactivateAction"
              : "settings.routes.deleteAction",
            { code: route.code },
          )}
          working={lifecycleMutation.isPending}
          onConfirm={() => lifecycleMutation.mutate(action)}
          onCancel={() => setAction(null)}
        />
      )}
    </div>
  );
}

// ── Premises · the walking order (D3 + D11) ────────────────────────────────

/**
 * ⚠ **THIS IS `walk_order`'S FIRST WRITER SINCE THE COLUMN WAS CREATED.** B17
 * §5 G5, verbatim: *"`walk_order` exists with a uniqueness constraint and NO
 * WRITER; no screen shows it, no route sheet consumes it."* Both halves close
 * here — the list shows it and the sheet below prints it.
 *
 * ⚠ **DRAG IS NOT THE ONLY WAY TO MOVE A STOP, AND THAT IS DELIBERATE.** A
 * drag handle is invisible to a keyboard and to a screen reader, which is the
 * same failure B14's note on rule 15 describes for an unnamed icon: it renders
 * beautifully, passes every text assertion, and one class of user cannot use
 * it. So every stop carries real ↑/↓ buttons named with the STOP's own address,
 * and the drag affordance rides on top of them.
 */
function PremisesTab(props: {
  stops: readonly RouteStop[];
  byPremises: Map<string, RoutePickerMeter[]>;
  dirty: boolean;
  saving: boolean;
  readOnly: boolean;
  readOnlyTitle: string | undefined;
  t: Translator;
  dragFrom: number | null;
  onMove: (from: number, to: number) => void;
  onDragStart: (index: number | null) => void;
  onReset: () => void;
  onSave: () => void;
}) {
  const { t } = props;
  const stopName = (stop: RouteStop): string => stop.premise_no ?? stop.premises_id;

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className={RC_DESC}>{t("settings.routes.detail.walkOrderLede")}</p>
        <div className="flex gap-2">
          {props.dirty && (
            <Button variant="secondary" size="sm" onClick={props.onReset}>
              {t("settings.routes.detail.resetOrder")}
            </Button>
          )}
          <Button
            variant="primary"
            size="sm"
            disabled={props.readOnly || !props.dirty || props.saving}
            title={props.readOnlyTitle}
            onClick={props.onSave}
          >
            {t("settings.routes.detail.saveOrder")}
          </Button>
          {/* B14 rule 4 — `🖨` is a ROW action's glyph; an ordinary button says
              the word (PO 2026-08-20: *"this only for table actions ; not for
              buttons"*). The sheet is the SAME list in the SAME order, printed
              through the browser: no second ordering exists to drift. */}
          <Button variant="secondary" size="sm" onClick={() => window.print()}>
            {t("settings.routes.detail.printSheet")}
          </Button>
        </div>
      </div>

      {/* B17 §4's hint, where the members render. */}
      <p className={RC_DESC}>{t("settings.routes.detail.membersHint")}</p>

      <ol className="m-0 flex list-none flex-col gap-1 p-0 print:hidden">
        {props.stops.map((stop, index) => {
          const stopMeters = props.byPremises.get(stop.premises_id) ?? [];
          return (
            <li
              key={stop.premises_id}
              data-rc="stop"
              draggable="true"
              onDragStart={() => props.onDragStart(index)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                if (props.dragFrom !== null) {
                  props.onMove(props.dragFrom, index);
                }
                props.onDragStart(null);
              }}
              className="flex items-center gap-3 border border-divider p-2 text-base"
            >
              {/* D11 — the sequence is the STOP's position. One building, one
                  number, however many units are inside it. */}
              <span className="w-10 shrink-0 text-right font-heading font-semibold tabular-nums">
                {index + 1}
              </span>
              <span className="min-w-0 flex-1">
                {stopName(stop)}
                <span className={`ml-2 text-sm ${RC_MUTED}`}>
                  {t(pluralKey("settings.routes.detail.unitsOnStop", stop.units), {
                    count: stop.units,
                  })}
                </span>
                {stopMeters.length === 0 && (
                  // r10's CHECK callout, in place: a premises with no active
                  // meter STAYS on the route and is verified in the field.
                  <span className="ml-2 border border-warning-700 px-1.5 py-0.5 text-xs font-bold tracking-tag">
                    {t("settings.routes.detail.noMeterVerify")}
                  </span>
                )}
              </span>
              <span className="flex shrink-0 gap-1">
                <button
                  type="button"
                  className="inline-flex h-6 w-6 cursor-pointer items-center justify-center border border-divider bg-transparent text-btn-sm disabled:cursor-not-allowed disabled:opacity-40"
                  aria-label={t("settings.routes.detail.moveUp", { stop: stopName(stop) })}
                  title={t("settings.routes.detail.moveUp", { stop: stopName(stop) })}
                  disabled={props.readOnly || index === 0}
                  onClick={() => props.onMove(index, index - 1)}
                >
                  <span aria-hidden="true">↑</span>
                </button>
                <button
                  type="button"
                  className="inline-flex h-6 w-6 cursor-pointer items-center justify-center border border-divider bg-transparent text-btn-sm disabled:cursor-not-allowed disabled:opacity-40"
                  aria-label={t("settings.routes.detail.moveDown", { stop: stopName(stop) })}
                  title={t("settings.routes.detail.moveDown", { stop: stopName(stop) })}
                  disabled={props.readOnly || index === props.stops.length - 1}
                  onClick={() => props.onMove(index, index + 1)}
                >
                  <span aria-hidden="true">↓</span>
                </button>
              </span>
            </li>
          );
        })}
      </ol>

      {props.stops.length === 0 && (
        <StatedAbsence
          title={t("settings.routes.detail.noMembersTitle")}
          body={t("settings.routes.detail.noMembersBody")}
        />
      )}

      {/* THE ROUTE SHEET — the same array, in the same order, printed. Hidden
          on screen and visible on paper through Tailwind's `print:` variants,
          so no stylesheet gains a `@media print` block (B14 rule 21). */}
      <section className="hidden print:block" data-rc="route-sheet">
        <PlainTable>
          <thead>
            <tr>
              <th>{t("settings.routes.detail.sheet.stop")}</th>
              <th>{t("settings.routes.detail.sheet.premises")}</th>
              <th>{t("settings.routes.detail.sheet.units")}</th>
              <th>{t("settings.routes.detail.sheet.meters")}</th>
            </tr>
          </thead>
          <tbody>
            {props.stops.map((stop, index) => (
              <tr key={stop.premises_id} data-rc="sheet-stop">
                <td>{index + 1}</td>
                <td>{stopName(stop)}</td>
                <td>{stop.units}</td>
                <td>{(props.byPremises.get(stop.premises_id) ?? []).length}</td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </section>
    </section>
  );
}

// ── Units ──────────────────────────────────────────────────────────────────

function UnitsTab(props: {
  route: {
    membership: { unit_id: string; unit_label: string; premises_id: string; premise_no: string | null }[];
  };
  t: Translator;
}) {
  const { t } = props;
  // Record links (PO 2026-10-19) — every record on the route's tabs opens.
  const tenantPath = useTenantPath();
  if (props.route.membership.length === 0) {
    return (
      <StatedAbsence
        title={t("settings.routes.detail.noMembersTitle")}
        body={t("settings.routes.detail.noMembersBody")}
      />
    );
  }
  return (
    <div className="overflow-x-auto">
      <PlainTable>
        <thead>
          <tr>
            <th>{t("settings.routes.wizard.col.premise")}</th>
            <th>{t("settings.routes.detail.col.unit")}</th>
          </tr>
        </thead>
        <tbody>
          {props.route.membership.map((member) => (
            <tr key={member.unit_id}>
              <td>
                {member.premise_no === null ? (
                  t("settings.unwiredCount")
                ) : (
                  <InlineLinkTo to={tenantPath(premisesDetailPath(member.premises_id))}>{member.premise_no}</InlineLinkTo>
                )}
              </td>
              <td>
                <InlineLinkTo to={tenantPath(unitDetailPath(member.unit_id))}>{member.unit_label}</InlineLinkTo>
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </div>
  );
}

// ── Assets · exclusions explain themselves IN PLACE ────────────────────────

function AssetsTab(props: { meters: readonly RoutePickerMeter[]; t: Translator }) {
  const { t } = props;
  const tenantPath = useTenantPath();
  if (props.meters.length === 0) {
    return (
      <StatedAbsence
        title={t("settings.routes.wizard.metersEmptyTitle")}
        body={t("settings.routes.wizard.metersEmptyBody")}
      />
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-x-auto">
        <PlainTable>
          <thead>
            <tr>
              <th>{t("settings.routes.wizard.col.meter")}</th>
              <th>{t("settings.routes.wizard.col.premise")}</th>
              <th>{t("settings.routes.detail.col.unit")}</th>
              <th>{t("settings.routes.wizard.col.service")}</th>
              <th>{t("settings.routes.detail.col.onRoute")}</th>
              {/* B17 §6 — *"two words, shown in place"*. SERVED now. */}
              <th>{t("settings.routes.detail.col.why")}</th>
            </tr>
          </thead>
          <tbody>
            {props.meters.map((meter) => (
              <tr key={meter.id} data-rc="route-meter">
                <td>
                  {/* DEF-SHL-6348: words, never the id (B14 rule 31) — the id
                      rides only in the link's address. */}
                  <InlineLinkTo to={tenantPath(assetDetailPath(meter.id))}>
                    {meter.asset_no ?? t("metering.bulkEstimate.unknownMeter")}
                  </InlineLinkTo>
                </td>
                <td>
                  <InlineLinkTo to={tenantPath(premisesDetailPath(meter.premises_id))}>{meter.address_line}</InlineLinkTo>
                </td>
                <td>
                  <InlineLinkTo to={tenantPath(unitDetailPath(meter.unit_id))}>{meter.unit_label}</InlineLinkTo>
                </td>
                <td>{meter.service_code ?? t("settings.unwiredCount")}</td>
                <td>
                  {meter.excluded ? (
                    <span className={RC_MUTED}>{t("settings.routes.detail.excluded")}</span>
                  ) : (
                    t("settings.routes.detail.included")
                  )}
                </td>
                {/* ⚠ AN EXCLUSION EXPLAINS ITSELF WHERE IT SITS — and a NULL
                    reason stays blank rather than being filled in. Every
                    exclusion made before the column exists has none, and a
                    plausible reason invented here is worse than the blank: the
                    next staff member would re-tick the meter on the strength of
                    it. An INCLUDED meter has nothing to explain. */}
                <td>
                  {!meter.excluded ? (
                    ""
                  ) : meter.exclusion_reason === null ? (
                    <span className={RC_MUTED}>{t("settings.routes.detail.noReason")}</span>
                  ) : (
                    meter.exclusion_reason
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </div>
    </div>
  );
}

// ── Accounts · D12, status only ────────────────────────────────────────────

/**
 * ⚠ **D12 — *"not required"*: NO BALANCE COLUMN, EVER.** The screenshot draws
 * one ($142.30, $88.10…). Routes and cycles are grouping only (BR-MET-078,
 * hardened by this CR), so no money reaches this tab — and the payload behind
 * it carries no amount field at all, which is where the guarantee actually
 * lives. What a staff member needs here is who to warn, not what they owe.
 *
 * ⚠ **UNITS WITH NO ACCOUNT ARE COUNTED, NOT DROPPED.** On a route where half
 * the units are empty, "12 accounts" beside 30 units reads as eighteen missing
 * customers unless the screen says otherwise.
 */
function AccountsTab(props: {
  payload: RouteAccountsPayload | null;
  loading: boolean;
  t: Translator;
}): ReactNode {
  const { t } = props;
  const tenantPath = useTenantPath();
  if (props.loading) {
    return <LoadingSkeleton variant="table" />;
  }
  const rows = props.payload?.accounts ?? [];
  return (
    <section className="flex flex-col gap-3">
      <p className={RC_DESC}>{t("settings.routes.detail.accountsLede")}</p>
      {props.payload !== null && (
        <p className="m-0 text-base">
          {t("settings.routes.detail.accountsSummary", {
            accounts: props.payload.total,
            units: props.payload.units,
            without: props.payload.units_without_account,
          })}
        </p>
      )}
      {rows.length === 0 ? (
        <StatedAbsence
          title={t("settings.routes.detail.noAccountsTitle")}
          body={t("settings.routes.detail.noAccountsBody")}
        />
      ) : (
        <div className="overflow-x-auto">
          <PlainTable>
            <thead>
              <tr>
                <th>{t("settings.routes.detail.col.account")}</th>
                <th>{t("settings.routes.detail.col.customer")}</th>
                <th>{t("settings.routes.wizard.col.premise")}</th>
                <th>{t("settings.routes.detail.col.unit")}</th>
                <th>{t("settings.routes.col.status")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.account_id} data-rc="route-account">
                  <td>
                    {row.account_no === null ? (
                      t("settings.unwiredCount")
                    ) : (
                      <InlineLinkTo to={tenantPath(accountDetailPath(row.account_id))}>{row.account_no}</InlineLinkTo>
                    )}
                  </td>
                  <td>{row.customer_name ?? t("settings.unwiredCount")}</td>
                  <td>
                    {row.premise_no === null ? (
                      t("settings.unwiredCount")
                    ) : (
                      <InlineLinkTo to={tenantPath(premisesDetailPath(row.premises_id))}>{row.premise_no}</InlineLinkTo>
                    )}
                  </td>
                  <td>
                    <InlineLinkTo to={tenantPath(unitDetailPath(row.unit_id))}>{row.unit_label}</InlineLinkTo>
                  </td>
                  <td>
                    {row.status === null ? (
                      <span className={RC_MUTED}>{t("settings.unwiredCount")}</span>
                    ) : (
                      // The account's own status word, served. Not translated
                      // through a key set this screen does not own — the
                      // customers module names them and inventing a second
                      // vocabulary here is how two screens disagree.
                      row.status
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      )}
    </section>
  );
}

// ── Read history · B17 §4, SERVED ──────────────────────────────────────────

/**
 * SET-06D's **Read history** — one row per reading window closed on this route.
 *
 * ⚠ **THERE IS NO READER COLUMN, AND IT IS NOW A RULING RATHER THAN A
 * REPORTED TENSION — OQ-343, CLOSED 2026-08-23.** RC-W3c built the column
 * absent and said out loud that B17 §4 (*"Window · Read on · Reader ·
 * Collected · Expected · Result"*) and D6 (*"not required"*) disagreed, rather
 * than resolving it by call site. The PO ruled, verbatim: ***"B: no reader
 * anywhere, correct the screenshot and drop the stored name"***.
 *
 * So this table's five columns are the whole of it — **Window · Read on ·
 * Collected · Expected · Result** — and the PO's own SET-06D.audit screenshot
 * (*"Aug 2026 · Aug 3 · M. Chen · 196 · 196 · Complete"*) is **CORRECTED, NOT
 * FOLLOWED**. The change-log line the same screenshot draws, *"Reader changed ·
 * D. Ortiz → M. Chen"*, goes with it. `read_windows.reader` is dropped by
 * migration and `RouteReadWindowRow` no longer names it, so there is nothing
 * left here to render even by accident. The suite asserts the absence — and
 * `RoutesCyclesRulings.test.tsx` asserts it against the source of every file
 * under `src/`, because the next lane reads the screenshot before it reads
 * this comment.
 *
 * ⚠ **SCOPE, so nobody over-reaches on the strength of the sentence above:**
 * `routes.assigned_to` and the ops tab's existing read-only reader display are
 * NOT touched. They predate CR-029, D6 explicitly preserved them, and the PO
 * was never asked about them.
 *
 * A window with no `result` is still OPEN — it is not "Incomplete", and saying
 * so with the same word would report a route as failing when it is mid-walk.
 */
function ReadHistory(props: {
  windows: readonly RouteReadWindowRow[];
  loading: boolean;
  t: Translator;
}) {
  const { t } = props;
  const { timeZone, dateFormat } = useRegional({});
  if (props.loading) {
    return <LoadingSkeleton variant="table" />;
  }
  if (props.windows.length === 0) {
    return (
      <StatedAbsence
        title={t("settings.routes.detail.noReadHistoryTitle")}
        body={t("settings.routes.detail.noReadHistoryBody")}
      />
    );
  }
  return (
    <section className="flex flex-col gap-2">
      <p className="m-0 font-heading text-btn-sm font-semibold uppercase tracking-wider text-neutral-600">
        {t("settings.routes.detail.readHistory")}
      </p>
      <div className="overflow-x-auto">
        <PlainTable>
          <thead>
            <tr>
              <th>{t("settings.routes.detail.col.readWindow")}</th>
              <th>{t("settings.routes.detail.col.readOn")}</th>
              <th>{t("settings.routes.detail.col.collected")}</th>
              <th>{t("settings.routes.detail.col.expected")}</th>
              <th>{t("settings.routes.detail.col.result")}</th>
            </tr>
          </thead>
          <tbody>
            {props.windows.map((window) => (
              <tr key={window.id} data-rc="read-window">
                <td>
                  <DateCell
                    value={window.period_start}
                    timeZone={timeZone}
                    dateFormat={dateFormat}
                  />
                  {" – "}
                  <DateCell value={window.period_end} timeZone={timeZone} dateFormat={dateFormat} />
                </td>
                <td>
                  {window.read_on === null ? (
                    <span className={RC_MUTED}>{t("settings.unwiredCount")}</span>
                  ) : (
                    <DateCell value={window.read_on} timeZone={timeZone} dateFormat={dateFormat} />
                  )}
                </td>
                {/* ⚠ NULL IS NOT ZERO. A window whose counts were never stated
                    renders the dash — "0 of 196 collected" would report a walk
                    that nobody did as a walk that found nothing. */}
                <td className="tabular-nums">
                  {window.collected === null ? t("settings.unwiredCount") : window.collected}
                </td>
                <td className="tabular-nums">
                  {window.expected === null ? t("settings.unwiredCount") : window.expected}
                </td>
                <td>{readResultLabel(window.result, t)}</td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </div>
    </section>
  );
}

/** `Complete` · `Incomplete` · still open. A word outside the server's own set
 *  renders as the dash rather than through a default key — a third result is a
 *  fact about the data, and `frequencyKey` argues the posture in full. */
export function readResultLabel(result: string | null, t: Translator): string {
  if (result === null) {
    return t("settings.routes.detail.readResult.open");
  }
  if (result === "Complete") {
    return t("settings.routes.detail.readResult.complete");
  }
  if (result === "Incomplete") {
    return t("settings.routes.detail.readResult.incomplete");
  }
  return t("settings.unwiredCount");
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-029 RC-W3-T3 (B17 §7) — SET-06D, a new screen
// generated: 2026-08-23 by the RC-W3 frontend lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest (RoutesCyclesDetail.test.tsx)
// [CR-029 RC-W3c 2026-08-23] AMENDED — **FIVE OF THE SIX ABSENCES BELOW ARE GONE, AND THEY CLOSED IN ANOTHER LANE'S COMMIT.** RC-W3b mounted `PUT /routes/{id}/premises-order` (the walking order SAVES — B17 §5 gap G5 closed end to end), `GET /routes/{id}/read-windows` (Read history is a table of closed windows), `GET /routes/{id}/accounts` (real accounts, status only) and put `exclusion_reason` on every meter row and `premises_order` on the route payload (the saved walk is READ BACK, so a reorder survives a refresh and a later route edit). `orderRouteAbsent` is deleted: it told a user the order *"can't be saved yet"* on a route that saves it.
// [CR-029 RC-W6b 2026-08-23] ⚠ **OQ-343 IS RULED AND THE SCREENSHOT IS CORRECTED, NOT FOLLOWED — recorded here the way B17 §3 records its four, because a divergence from the PO's own drawing that lives only in a chat log gets "fixed" back by the next lane.** PO verbatim: ***"B: no reader anywhere, correct the screenshot and drop the stored name"***. TWO things in the SET-06D.audit screenshot are therefore WRONG ON PURPOSE: (1) the Read-history **Reader** column — the drawing shows *"Aug 2026 · Aug 3 · M. Chen · 196 · 196 · Complete"* and *"May 2026 · D. Ortiz · 191/196 · 5 skipped"*; the table renders **Window · Read on · Collected · Expected · Result** and nothing else. (2) the change-log line ***"Reader changed · D. Ortiz → M. Chen"***; no such row is rendered, and no audit event on this screen names a reader. The stored name goes too — `read_windows.reader` is dropped by migration (that column is metering's; this lane REPORTED it rather than editing another lane's app) and `RouteReadWindowRow` no longer types `reader_id`/`reader_name`, so a served key is inert here. ⚠ SCOPE: `routes.assigned_to` and the ops tab's read-only reader display are UNTOUCHED — D6 preserved them and the PO was not asked.
// exceptions: E3 the ACCOUNT STATUS renders the served word rather than a translated key: the customers module names that vocabulary and a second one here is how two screens disagree · E3 D12 forbids the Balance column the screenshot drew, and no money field exists on the payload either · E3 a null `collected`/`expected` on a read window renders the dash, never `0` · E3 NO browser walkthrough has happened for this screen (hard-won law 6)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
