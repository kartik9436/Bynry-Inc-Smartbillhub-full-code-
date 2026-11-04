// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-004 (the Rate schedules list: structure preview + usage counts) ·
//           US-RAT-010 (the "Change scheduled — effective <date>" note)
//           Screens: S9 (Rate schedules tab) → S11
// Change:   DEF-441 — the CARD GRID becomes r10's NINE-COLUMN TABLE.
// Rules:    BR-RAT-019 (the six tariff models) · BR-RAT-024 (service vocabulary) ·
//           BR-RAT-025 (D1: a model is not service-tied) · BR-RAT-031 (one service, one
//           model; the status pill is DERIVED and there is NO approval-pending state;
//           a draft is a version with no effective date) · BR-RAT-032/033 (the previewed
//           tier/window rows are the STORED rows, verbatim) · BR-RAT-038 (the UoM gate is
//           stated, never silently converted) · BR-SHL-010 (only declared capabilities
//           render) · BR-SHL-011 (URL grammar) · BR-SHL-012 (the six A18 states) ·
//           BR-SHL-023 (ONE date-formatting path — the tenant's regional format) ·
//           BR-SHL-032 (a confirm names the action) · BR-SHL-034 (the shared formatter) ·
//           B14 rule 15 (row actions are ICONS) · B14 rule 3 (ONE table type)
// ═══════════════════════════════════════════════════════════════════════════
// DEF-441 — WHY THIS IS A TABLE, AND WHY IT WAS A CARD GRID FOR SO LONG
// ═══════════════════════════════════════════════════════════════════════════
// The Product Owner put our screen beside r10's on 2026-08-21: *"rate schedule
// is in table format in Proto - you ahve done card format"*.
//
// r10 is THE reference (PO ruling 2026-08-16) and its own markup, line 764 of
// `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html`, is a `<table class="table
// lt">` with NINE headers:
//
//     Schedule · Svc · Structure · Sizes · Seasons · Plans · Accounts ·
//     Effective · Status
//
// ⚠ **THE CARD GRID WAS NOT A MISTAKE ANYONE MADE AT THE KEYBOARD — IT WAS
// WRITTEN DOWN AS RATIFIED.** `04-docs/05-modules/06-rating/09-screen-inventory.md`
// §18 row 4 read *"stays a CARD GRID (EP-RAT-02, IS-5 N/A — ratified)"*, and
// EP-RAT-02's capability row said "not an IS-2 table" with the column chooser
// N/A. The lane that built this read those, saw them contradict its own build
// packet ("the shared DataTable on every list"), and did the correct thing with
// the wrong input: it followed the ratified document and REPORTED the
// divergence. The document was false. It is corrected in the same commit as
// this file, because leaving it would rebuild the card grid on the next pass.
//
// **What the card grid could not show, and now does:** Sizes, Seasons and
// Effective had no cell at all, and Plans/Accounts were a prose sentence in a
// card footer (*"Used by 1 plans · applied to 2 accounts"*) — unsortable,
// unscannable and unexportable. All five are served by
// `selectors.schedule_card`, four of them added for this fix.
//
// **Sortable on all nine (PO, 2026-08-21).** That required the SERVER: six of
// the nine sort over values derived per card, and before this fix
// `schedule_list` mapped any unknown sort key silently back to `name` — a
// `Plans ▲` header would have re-sorted by schedule name and looked like it
// worked. `SCHEDULE_SORTS` and `_SCHEDULE_DERIVED_SORTS` are that half.
//
// ⚠ **ONE STAMPED DIVERGENCE FROM r10: THE DATE FORMAT.** r10's Effective
// column reads `Jan 1, 2026`. That is `MMM D, YYYY`, and it is NOT one of the
// seven regional formats BR-SHL-023 ratified (the PO chose those twice, most
// recently *"we also need DD-MMM-YY"*). Hard-coding r10's form here would
// override the tenant's own Settings → Regional choice on this ONE screen — a
// de-DE tenant who set `DD.MM.YYYY` would get an English month name in a table
// and their own format everywhere else. So this renders through the shared
// `DateCell`, which is the ratified path, and the gap is FILED rather than
// decided here (DEF-459: add `MMM D, YYYY` as an eighth regional format, or
// rule that r10's drawing is simply the US default). *File it, don't follow
// it.*
//
// ⚠ **A TENTH COLUMN r10 DOES NOT DRAW: Actions.** r10 makes the whole row
// clickable and offers no per-row control, but our schedules can be ARCHIVED
// (US-RAT-004 TC-4, IS-1 deactivate-first) and that capability has to live
// somewhere. The Plans tab already carries the same extra column for the same
// reason, so this follows the house pattern rather than inventing a second one:
// B14 rule 15 icons, from the one icon module, with accessible names (G37).
//
// Every price in the structure preview is a decimal STRING rendered as text.
// This file performs no arithmetic of any kind.
// ═══════════════════════════════════════════════════════════════════════════
// CR-018 PHASE 1 — this component was the Route B spike, and it stays Route B.
// Styles live in the markup; the file is listed in `route-b-migrated.txt`, so
// `routeBUtilities.test.ts` (not G31) proves every class it names either
// compiles through the real Tailwind compiler or is declared in a stylesheet.
//
// ⚠ THE INTERPOLATED CLASS NAME IS GONE. `svc-${card.service}` was the app's
// one runtime-assembled class name and the reason `.svc-*` had to stay declared
// in `PlansRates.css`. The Svc column uses the shared `ServiceTags` (DEF-439's
// coloured letter badge), which reads its colour from a `--color-service-*`
// TOKEN in a style attribute — a token is invisible to Tailwind's scanner in
// exactly the way a class name is not, so there is nothing left to interpolate.
// `routeBUtilities.test.ts` was updated in this commit to assert the ABSENCE
// instead; the now-unreferenced `.rating-tag.svc-*` rules are dead CSS awaiting
// CR-018 Phase 2 (DEF-460).
//
// ⚠ NO ARBITRARY TYPE VALUES. `text-sm` is 12px and `text-[12px]` is refused by
// `10-scripts/gates/g34_type_scale_escape.py` — bracket notation is the one way
// an off-scale size can still reach the product.
// ═══════════════════════════════════════════════════════════════════════════
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  TARIFF_MODELS,
  archiveRateSchedule,
  duplicateRateSchedule,
  getRateSchedules,
  getTenantServices,
} from "@/api/endpoints";
import type { ScheduleCard, VersionStructure } from "@/api/endpoints";
import { sizesPricedText } from "@/api/rateScheduleReads";
import type { ScheduleListRow } from "@/api/rateScheduleReads";
import { getSchedulesBaseToChoose } from "@/api/baseCodeEndpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { CopyIcon, PencilIcon, PowerIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { FailedWithRetry, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
// The ONE quantity formatter (US-SHL-013). r10's Accounts column reads `1,098`
// with `font-feature-settings:tnum`; a count printed with `String(n)` reads
// `1098`. This is the shared separator law already written once — a second
// `toLocaleString` here would be the drift DEF-364 is about, one column over.
import { formatQuantity } from "@/components/UnitCell";
import { ListExportButton } from "@/features/exports/ListExportButton";
import {
  RefusalNotice,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  activatedServiceOptions,
  DASHBOARD_ROUTE,
  enumLabel,
  GuardedButton,
  PLANS_RATES_ROUTE,
  RatingStatusPill,
  scheduleStatusTone,
  useNarrowList,
} from "./ratingShared";
import type { RatingTabRender, Translator } from "./ratingShared";

// ── Routes into S11 ────────────────────────────────────────────────────────

export const NEW_SCHEDULE_ROUTE = `${PLANS_RATES_ROUTE}/rates/new`;

/**
 * RAT-02, the schedule DETAIL. This used to be the RAT-03 wizard's own route
 * and it is the detail now (CR-013 P3 / screen inventory §18 row 5): a card's
 * NAME opens the record, and the record's own `Edit rates` opens the wizard,
 * which is what r10 draws and what CR-013 part 1 describes.
 */
export function scheduleRoute(tariffId: string): string {
  return `${PLANS_RATES_ROUTE}/rates/${tariffId}`;
}

/** RAT-03 in edit mode — one segment below the detail. */
export function scheduleEditRoute(tariffId: string): string {
  return `${PLANS_RATES_ROUTE}/rates/${tariffId}/edit`;
}

// ── Pure pieces ────────────────────────────────────────────────────────────

/**
 * CR-157-BRC10 wave B — THE LIST AS THE 2026-10-01 DRAWING DRAWS IT
 * (`05-prototype/rate-schedules-2026-10-01/images/01-list-all.png`, read as an
 * IMAGE, B14 rule 42):
 *
 *   Schedule ▲ · Service · Structure · Customer class · Base code · Sizes ·
 *   Effective · Plans · Accounts · Status · Actions
 *
 * ⚠ **`Seasons` LEFT THE TABLE AND `Svc` BECAME `Service`** — the drawing has
 * no Seasons column and prints the service as a WORD; the season labels are on
 * the Rates tab, where they are a table rather than a cell. The structure cell
 * is the method's name alone (*Tiered*, *Time-of-use*), as drawn.
 *
 * **The seven DEF-441 sorts stay sortable** — the server still knows them —
 * and the three new columns are NOT sortable: each is a derived figure the
 * server would have to sort in Python over the whole tenant (`NFR-3`), and a
 * header arrow over a sort that did not happen is the failure `SCHEDULE_SORTS`
 * was written to prevent.
 *
 * `cells` is optional so the pure config stays provable without a router.
 */
export function scheduleTableConfig(
  t: Translator,
  serviceOptions: { value: string; label: string }[],
  cells?: {
    name: (row: ScheduleListRow) => JSX.Element;
    service: (row: ScheduleListRow) => JSX.Element;
    structure: (row: ScheduleListRow) => JSX.Element;
    customerClass: (row: ScheduleListRow) => JSX.Element;
    baseCode: (row: ScheduleListRow) => JSX.Element;
    sizes: (row: ScheduleListRow) => JSX.Element;
    effective: (row: ScheduleListRow) => JSX.Element;
    plans: (row: ScheduleListRow) => JSX.Element;
    accounts: (row: ScheduleListRow) => JSX.Element;
    status: (row: ScheduleListRow) => JSX.Element;
    actions: (row: ScheduleListRow) => JSX.Element;
  },
  /** `DEF-RAT-9112` — below 1440, Sizes and Plans start behind the Columns
   *  picker so the list fits the 1280 laptop's 960px; the full set stays one
   *  click away. Decision log 2026-10-02. */
  narrow = false,
): TableConfig<ScheduleListRow> {
  const hideWhenNarrow = narrow ? { defaultVisible: false } : {};
  return {
    screenId: "S9.rates",
    columns: [
      {
        key: "name",
        label: t("rating.rates.col.schedule"),
        sortable: true,
        identity: true,
        cell: cells?.name,
      },
      { key: "service", label: t("rating.rs.col.service"), sortable: true, cell: cells?.service },
      {
        key: "structure",
        label: t("rating.rates.col.structure"),
        sortable: true,
        cell: cells?.structure,
      },
      { key: "customerClass", label: t("rating.rs.col.customerClass"), cell: cells?.customerClass },
      { key: "baseCode", label: t("rating.rs.col.baseCode"), cell: cells?.baseCode },
      { key: "sizes", label: t("rating.rates.col.sizes"), cell: cells?.sizes, ...hideWhenNarrow },
      {
        key: "effective",
        label: t("rating.rates.col.effective"),
        sortable: true,
        cell: cells?.effective,
      },
      {
        key: "plans",
        label: t("rating.rates.col.plans"),
        sortable: true,
        numeric: true,
        cell: cells?.plans,
        ...hideWhenNarrow,
      },
      {
        key: "accounts",
        label: t("rating.rates.col.accounts"),
        sortable: true,
        numeric: true,
        cell: cells?.accounts,
      },
      { key: "status", label: t("rating.col.status"), sortable: true, cell: cells?.status },
      { key: "actions", label: t("rating.col.actions"), cell: cells?.actions },
    ],
    getRowId: (row) => row.id,
    searchFields: ["name"], // the matrix's only search field
    searchPlaceholder: "rating.rates.searchPlaceholder",
    filters: [
      // A group inside `+ Filter`, like every other list's (DEF-RAT-9103, PO
      // 2026-10-02: *"all these should be part of filter - and sepearte button
      // should not be given"*) — wave B's row of service chips is gone. Several
      // services at once since OQ-306 closed (PO 2026-10-02, *"Allow several
      // services at once."*) — the shared FilterBar does it for `service`.
      { name: "service", label: t("rating.filter.service"), options: serviceOptions },
      {
        name: "structure",
        label: t("rating.rates.filter.structure"),
        options: TARIFF_MODELS.map((model) => ({
          value: model,
          label: t(`rating.model.${model}`),
        })),
      },
      {
        name: "status",
        label: t("rating.rates.filter.status"),
        options: SCHEDULE_STATUSES.map((status) => ({
          value: status,
          label: t(`rating.schedule.status.${status}`),
        })),
      },
    ],
    defaultSort: { sort: "name", dir: "asc" },
  };
}

/** BR-RAT-031: DERIVED, and deliberately three-valued — no approval state. */
export const SCHEDULE_STATUSES = ["active", "draft", "archived"] as const;

// ── The cells DEF-441 added, as PURE functions ─────────────────────────────
// Provable without a DOM, and the only place each rule is written.

/**
 * r10's Structure cell: `Tiered · 3 blocks`, `TOU · 2 periods`,
 * `Demand + energy`, `Flat · by line size`.
 *
 * The MODEL comes from the enum catalog; the qualifier after it is a count of
 * STORED ROWS the server already sent (`block_count` / `window_count`), never a
 * re-derivation on the client. A model with neither count renders as the model
 * alone — which is what r10 draws for Demand, and is the honest answer for a
 * schedule with no structure entered yet.
 */
export function structureText(t: Translator, card: ScheduleCard): string {
  const model = enumLabel(t, "rating.model", card.structure);
  if (card.window_count > 0) {
    return t("rating.rates.structure.periods", { model, n: card.window_count });
  }
  if (card.block_count > 0) {
    return t("rating.rates.structure.blocks", { model, n: card.block_count });
  }
  return model;
}

/**
 * r10's Sizes cell: `5 sizes`, `1 size`.
 *
 * ⚠ ZERO IS NOT "NO SIZES" AND MUST NOT RENDER AS AN EM-DASH. DEF-360: an empty
 * size axis means *"one row prices every connection size"* — which is what
 * every version written before the size axis existed says, and is a real,
 * correct, common state. An em-dash there would read as "this schedule prices
 * nothing", which is the opposite of the truth.
 */
export function sizesText(t: Translator, card: ScheduleCard): string {
  if (card.size_count === 0) {
    return t("rating.rates.sizes.all");
  }
  if (card.size_count === 1) {
    return t("rating.rates.sizes.one");
  }
  return t("rating.rates.sizes.many", { n: card.size_count });
}

/**
 * r10's Seasons cell, which it draws BOTH ways on the same table: `Summer /
 * Winter` on the seasonal water row and `2 seasons` on the TOU row.
 *
 * The rule chosen here — NAMES up to two, a COUNT beyond that — is this lane's
 * judgment where r10 gave two forms and no rule, and it is recorded in
 * `12-governance/02-decision-log.md` with its worked figure. Null is `—`,
 * exactly as r10 draws for a schedule with no seasons.
 */
export function seasonsText(t: Translator, card: ScheduleCard): string | null {
  if (card.season_labels.length === 0) {
    return null; // the caller renders r10's em-dash
  }
  if (card.season_labels.length <= 2) {
    return card.season_labels.join(" / ");
  }
  return t("rating.rates.seasons.many", { n: card.season_labels.length });
}

/**
 * r10's Plans and Accounts cells. A ZERO renders as an em-dash — r10's own
 * choice on both its `Fire line standby` row (no plans) and its draft row (no
 * accounts) — because `0` in a column of counts reads as a measured zero when
 * what it means is "none yet". Anything else goes through the ONE shared
 * quantity formatter, so 1098 reaches the screen as r10's `1,098`.
 */
export function countText(value: number): string | null {
  return value === 0 ? null : formatQuantity(String(value));
}

/**
 * Which stored rows a card previews, given the model. Returns the KIND only —
 * the renderer below reads the actual rows — so the mapping stays provable
 * without a DOM and cannot drift from BR-RAT-019's model set.
 */
export type PreviewKind = "tiers" | "windows" | "capacity" | "demand" | "percent" | "none";

export function previewKind(structure: VersionStructure | undefined): PreviewKind {
  if (structure === undefined) {
    return "none";
  }
  if (structure.capacity !== undefined) {
    return "capacity";
  }
  if (structure.demand !== undefined) {
    return "demand";
  }
  if (structure.windows !== undefined && structure.windows.length > 0) {
    return "windows";
  }
  if (structure.tiers !== undefined && structure.tiers.length > 0) {
    return "tiers";
  }
  if (structure.percent !== undefined && structure.percent !== null) {
    return "percent";
  }
  return "none";
}

/**
 * The version a card previews: the one in force, else the schedule's saved
 * DRAFT (BR-RAT-031 — that preview IS the resume view). Returns null when the
 * schedule is identity-only.
 */
export function previewVersion(card: ScheduleCard) {
  return card.current_version ?? card.draft_version;
}

/** US-RAT-004 TC-4 (IS-1): archiving is blocked while any plan references it. */
export function scheduleCanArchive(card: ScheduleCard): boolean {
  return card.status !== "archived";
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface RateSchedulesTabProps {
  readOnly: boolean;
  client?: ApiClient;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** US-SHL-020 addendum r2 — see PlansTab for why navigation tabs use it too. */
  render: RatingTabRender;
}

export function RateSchedulesTab(props: RateSchedulesTabProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [pendingArchive, setPendingArchive] = useState<ScheduleListRow | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const narrow = useNarrowList(); // DEF-RAT-9112
  // DEF-RAT-9797 — how many live schedules still name no base code.
  const baseToChooseQuery = useQuery({
    queryKey: ["rate-schedules", "base-to-choose"],
    queryFn: () => getSchedulesBaseToChoose(client),
    retry: false,
  });
  const baseToChoose = baseToChooseQuery.data?.count ?? 0;
  const config = scheduleTableConfig(
    translate,
    // DEF-RAT-5691 — the tenant's OWN services, never the platform catalogue
    // (BR-RAT-024, PO ruling 2026-09-17).
    activatedServiceOptions(servicesQuery.data),
    {
      // r10: the schedule name is ACCENT-COLOURED AND BOLD, and it is the door
      // into the record. `.rating-link` is the shared accent link this feature
      // already uses for the same job on the Plans tab.
      name: (row) => (
        <button
          type="button"
          className="rating-link font-heading font-semibold"
          onClick={() => navigate(tenantPath(scheduleRoute(row.id)))}
        >
          {row.name}
        </button>
      ),
      // DEF-439's coloured letter badge, from `ratingShared`. NOT a badge
      // written here: the letters cannot be derived from the names (Sewer,
      // Solar and Storm water all start with S) and one map is the only way
      // two screens can agree.
      // CR-157-BRC10 B — the service as a WORD (`01-list-all.png`).
      service: (row) => <span>{row.service_name}</span>,
      structure: (row) => <span>{enumLabel(translate, "rating.model", row.structure)}</span>,
      customerClass: (row) => (
        <span>{row.customer_class_name ?? t("rating.rs.everyClass")}</span>
      ),
      // DEF-RAT-9110: a code is one token — `BASE-W` never breaks at its hyphen.
      baseCode: (row) => (
        <span className="flex flex-col">
          <span className="whitespace-nowrap">
            <EmDashOr text={row.base_code ?? null} />
          </span>
          {/* DEF-RAT-9797 — a schedule names exactly one base code. */}
          {row.base_code_to_choose === true && (
            <span className="text-sm text-warning-700" data-base-to-choose="">
              {t("rating.rs.baseToChoose")}
            </span>
          )}
        </span>
      ),
      sizes: (row) => (
        <EmDashOr text={sizesPricedText(translate, row.sizes_priced, row.sizes_total)} />
      ),
      plans: (row) => <EmDashOr text={countText(row.used_by_plans)} />,
      accounts: (row) => <EmDashOr text={countText(row.applied_to_accounts)} />,
      effective: (row) => (
        <EffectiveCell card={row} timeZone={props.timeZone} dateFormat={props.dateFormat} />
      ),
      status: (row) => <ScheduleStatusCell card={row} />,
      actions: (row) => (
        <ScheduleRowActions
          card={row}
          readOnly={props.readOnly}
          onEdit={() => navigate(tenantPath(scheduleEditRoute(row.id)))}
          onDuplicate={() => {
            setRefusal(null);
            duplicate.mutate(row);
          }}
          onArchive={() => {
            setRefusal(null);
            setPendingArchive(row);
          }}
        />
      ),
    },
    narrow,
  );
  const state = parseTableParams(searchParams, config);

  const listQuery = useQuery({
    queryKey: queryKeys.rateSchedules(serializeTableParams(state, config).toString()),
    queryFn: () =>
      getRateSchedules(
        {
          q: state.q,
          filters: state.filters,
          sort: state.sort,
          dir: state.dir,
          page: state.page,
          per: state.per,
        },
        client,
      ),
  });

  // CR-157-BRC10 B — the row's middle icon (`01-list-all.png`). The same call
  // the detail's `Duplicate` makes: a NEW schedule carrying a DRAFT copy, and
  // success opens it, as the detail does.
  const duplicate = useMutation({
    mutationFn: (card: ScheduleListRow) => duplicateRateSchedule(card.id, {}, client),
    onSuccess: (copy) => {
      fireToast(t("rating.rateDetail.toast.duplicated", { name: copy.name }));
      void queryClient.invalidateQueries({ queryKey: ["rate-schedules"] });
      navigate(tenantPath(scheduleEditRoute(copy.id)));
    },
    onError: (error: unknown) => setRefusal(refusalOf(error, translate)),
  });

  const archive = useMutation({
    mutationFn: (card: ScheduleListRow) => archiveRateSchedule(card.id, client),
    onSuccess: (_saved, card) => {
      setPendingArchive(null);
      setRefusal(null);
      fireToast(t("rating.rates.toast.archive", { name: card.name }));
      void queryClient.invalidateQueries({ queryKey: ["rate-schedules"] });
    },
    onError: (error: unknown) => {
      // "referenced by N plans — detach first" arrives with its own count.
      setPendingArchive(null);
      setRefusal(refusalOf(error, translate));
    },
  });

  function setState(next: TableRequestState): void {
    setSearchParams(serializeTableParams(next, config), { replace: true });
  }

  // The primary action this tab owns, built once: it goes up to the shared
  // page head, top-right beside History (B14 rule 2; DEF-RAT-9101, PO
  // 2026-10-02). DEF-RAT-8824 had moved it to a bar under the table, where a
  // long list put it off-screen.
  const newSchedule = (
    <GuardedButton
      readOnly={props.readOnly}
      readOnlyReason={t("rating.readOnlyReason")}
      variant="primary"
      onClick={() => navigate(tenantPath(NEW_SCHEDULE_ROUTE))}
    >
      {t("rating.rates.new")}
    </GuardedButton>
  );

  // Both failures keep the header and strip — see ChargeCodesTab for why.
  if (listQuery.data === undefined && listQuery.isError) {
    if (isPermissionDenied(listQuery.error)) {
      return (
        <>
          {props.render({
            body: (
              <PermissionDenied
                helper={t("rating.denied")}
                onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
              />
            ),
          })}
        </>
      );
    }
    // US-RAT-004 TC-5: A18 §4 — Retry re-issues the IDENTICAL query.
    return (
      <>
        {props.render({
          body: (
            <FailedWithRetry
              title={t("rating.rates.failedTitle")}
              reason={apiErrorText(listQuery.error, translate)}
              onRetry={() => void listQuery.refetch()}
              onDownloadReport={() => undefined}
              onCancel={() => void listQuery.refetch()}
            />
          ),
        })}
      </>
    );
  }

  return (
    <>
      {props.render({
        action: newSchedule,
        body: (
          <div className="rating-tab">
            <RefusalNotice refusal={refusal} />
            {baseToChoose > 0 && (
              <p role="status" className="m-0 mb-4 bg-warning-100 px-4 py-3 text-base text-warning-700" data-base-to-choose-notice="">
                {t("rating.rs.baseToChooseNotice", { count: baseToChoose })}
              </p>
            )}

            {/* B14 rule 3 — the ONE table type. The search box, the filter row,
                the IS-5 column chooser (r10's column glyph at the right of that
                row), the pager and all six A18 states come from here; the card
                grid hand-rolled four of them and simply did without the rest. */}
            <DataTable<ScheduleListRow>
              config={config}
              state={state}
              onStateChange={setState}
              rows={listQuery.data?.results ?? []}
              totalRows={listQuery.data?.count ?? null}
              loading={listQuery.isPending}
              filterBarSlot={
                <FilterBar
                  filters={config.filters ?? []}
                  state={state}
                  onStateChange={setState}
                />
              }
              downloadSlot={
                // DEF-441. EP-RAT-02's matrix said "tabular export ships with
                // EP-RAT-04's history view" — which was a consequence of calling
                // this surface a card grid, and a card grid is the only list in
                // the product with no Download. `apps/rating/exports.py`
                // registers the resource; the server writes the BR-SHL-016 audit
                // row, because a copy of a tenant's pricing is exactly that kind
                // of event.
                <ListExportButton resource="rate-schedules" state={state} client={client} />
              }
              empty={{
                title: t("rating.rates.emptyTitle"),
                helper: t("rating.rates.emptyHelper"),
                ctaLabel: t("rating.rates.new"),
                onCta: () => !props.readOnly && navigate(tenantPath(NEW_SCHEDULE_ROUTE)),
              }}
            />

            {pendingArchive !== null && (
              <ConfirmDialog
                // B14 rule 6 (DEF-718): archive a rate schedule.
                confirmVariant="danger"
                title={t("rating.rates.confirm.archive.title", { name: pendingArchive.name })}
                consequence={t("rating.rates.confirm.archive.body", {
                  name: pendingArchive.name,
                  plans: pendingArchive.used_by_plans,
                })}
                confirmLabel={t("rating.rates.confirm.archive.verb")}
                working={archive.isPending}
                onConfirm={() => archive.mutate(pendingArchive)}
                onCancel={() => setPendingArchive(null)}
              />
            )}
          </div>
        ),
      })}
    </>
  );
}

// ── The cells ──────────────────────────────────────────────────────────────

/** r10's em-dash, decided in ONE place. A cell with nothing to say says so; it
 *  is never left blank, which reads as a rendering failure. */
function EmDashOr(props: { text: string | null }) {
  if (props.text === null) {
    return <span className="rating-empty">—</span>;
  }
  return <span>{props.text}</span>;
}

/**
 * r10's Effective column, plus the two dated notes the card footer used to
 * carry — because the column is where a date belongs, and dropping the notes
 * would drop US-RAT-004 TC-3 and BR-RAT-031's draft rule off the screen
 * entirely.
 *
 * ⚠ THE FORMAT IS THE TENANT'S, NOT r10's. r10 draws `Jan 1, 2026`; this
 * renders through the shared `DateCell`, which applies the tenant's Settings →
 * Regional format (BR-SHL-023's ONE formatting path, seven formats the PO chose
 * twice). Hard-coding r10's `MMM D, YYYY` would give one screen a format the
 * tenant never picked, while every other date in the product obeyed them.
 * DEF-459 files the divergence for the PO to rule on.
 */
function EffectiveCell(props: {
  card: ScheduleCard;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const { card } = props;
  return (
    <div className="flex flex-col gap-1">
      {card.effective_from === null ? (
        <span className="rating-empty">—</span>
      ) : (
        <DateCell
          value={card.effective_from}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
      )}
      {card.scheduled_change !== null && (
        // US-RAT-004 TC-3: a future-effective version. NOT "pending approval" —
        // that state was removed (BR-RAT-031 as-modified); it is simply dated.
        <span className={NOTE_CLASS} role="note">
          {t("rating.rates.scheduledChange")}{" "}
          <DateCell
            value={card.scheduled_change}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
        </span>
      )}
      {card.current_version === null && card.draft_version !== null && (
        // BR-RAT-031: a saved draft is resumable and is excluded from every
        // plan-builder picker until it is activated. The Status pill says
        // "Draft"; this says what Draft COSTS, which is the part a user acts on.
        <span className={NOTE_CLASS} role="note">
          {t("rating.rates.draftNote")}
        </span>
      )}
    </div>
  );
}

/**
 * The row's own actions — B14 rule 15: ICONS with accessible names, from the
 * one icon module (G37 refuses anything else inside `<RowActions>`).
 *
 * ⚠ THE NAME AND THE PENCIL GO TO DIFFERENT PLACES, ON PURPOSE. The schedule
 * NAME opens the record (RAT-02); the pencil opens the wizard (RAT-03) — the
 * same two-door arrangement the Plans tab uses, and the reason neither is a
 * dead control (hard-won law 2).
 */
function ScheduleRowActions(props: {
  card: ScheduleListRow;
  readOnly: boolean;
  onEdit: () => void;
  onDuplicate: () => void;
  onArchive: () => void;
}) {
  const { t } = useTranslation();
  const reason = props.readOnly ? t("rating.readOnlyReason") : null;
  return (
    // CR-157-BRC10 B — Edit · Duplicate · Retire, the three icons drawn on
    // every row of `01-list-all.png`, in that order (B14 rule 15: icons with
    // accessible names; the danger action is the power glyph, as drawn).
    <RowActions>
      <RowAction
        label={t("rating.rates.action.edit")}
        icon={<PencilIcon />}
        reason={reason}
        onClick={props.onEdit}
      />
      <RowAction
        label={t("rating.rateDetail.action.duplicate")}
        icon={<CopyIcon />}
        reason={reason}
        onClick={props.onDuplicate}
      />
      {scheduleCanArchive(props.card) && (
        <RowAction
          label={t("rating.rateDetail.action.retire")}
          icon={<PowerIcon />}
          reason={reason}
          onClick={props.onArchive}
        />
      )}
    </RowActions>
  );
}

/**
 * CR-157-BRC10 B — `IN FORCE` with `SCHEDULED` under it when a later version
 * is filed (`01-list-all.png`, Water — Residential). The words are the
 * drawing's; the value is still `schedule_state`'s derivation (BR-RAT-031),
 * so a draft reads *Draft* and a retired schedule *Archived*.
 */
function ScheduleStatusCell(props: { card: ScheduleListRow }) {
  const { t } = useTranslation();
  const { card } = props;
  return (
    // DEF-RAT-9110: `whitespace-nowrap` — *In force* is one pill on one line.
    <span className="inline-flex flex-col items-start gap-1 whitespace-nowrap">
      {card.status === "active" ? (
        <StatusPill tone="success">{t("rating.rs.status.inForce")}</StatusPill>
      ) : (
        <RatingStatusPill
          tone={scheduleStatusTone(card.status)}
          stem="rating.schedule.status"
          value={card.status}
        />
      )}
      {card.scheduled_change !== null && (
        <StatusPill tone="warning">{t("rating.rs.status.scheduled")}</StatusPill>
      )}
    </span>
  );
}

/**
 * The dated-note strip — CR-018 Phase 1, kept verbatim through DEF-441 because
 * the notes changed CELL, not style.
 *
 * ⚠ IT IS `text-sm`, NOT `text-[12px]` (CR-018 Phase 2b, G34). Both compile to
 * 12px — `--text-sm` IS 12px — but bracket notation is the one way an off-scale
 * size can still reach the product now that the `--text-*` namespace is
 * cleared, so `10-scripts/gates/g34_type_scale_escape.py` refuses it.
 *
 * ⚠ IT MUST STAY A WHOLE STRING LITERAL. Tailwind v4 generates only what its
 * scanner can SEE in source text, so a constant is fine and a template literal
 * that BUILDS a class name is not — 55 of Phase 0's 76 checks first came back
 * `rgba(0, 0, 0, 0)` for exactly that reason (tailwind-specimen/README.md).
 */
const NOTE_CLASS = "m-0 text-sm px-2 py-1 border-l-[3px] border-l-accent-500 bg-surface";

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RAT-004@0b56fac (story+rules snapshot hash — EP-RAT-02; co-story US-RAT-010@f69a661)
// generated: 2026-08-09 by story-coder v1 (W1 Plans & Rates frontend lane — S9 Rate schedules tab) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-21 by the DEF-441 lane (the CARD GRID becomes r10 line 764's NINE-COLUMN TABLE — PO: *"rate schedule is in table format in Proto - you ahve done card format"*)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: [DEF-441 lane 2026-08-21] tsc✔ eslint --max-warnings 0✔ vitest 1820 passed / 187 todo across 108 files✔ (1819+187 was the pre-lane baseline; this lane adds 14 new cases in RateSchedulesTable.test.tsx, all 14 PROVED RED against the card grid at HEAD first) · pytest tests/test_us_rat_schedules.py 40 passed / 1 pre-existing FAIL (DEF-458, not this lane) · pytest tests/test_be_list_export.py 49 passed✔ · g31✔ g34✔ g13✔ g30 defect-register✔ g35 version-lockstep✔ (2.29.56) · g37✔ (was RED on DataTable.tsx before this lane fixed DEF-462) · run_gates 24 PASS / 14 FAIL — every one of the 14 pre-existing and citing files this lane did not touch · trace_lint✔ (227 stories, 459 BR refs, 60 OQs) run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ (399+111 baseline unchanged and green; this packet adds 88 passing + 19 todo across 5 files — every todo is browser-interaction, server/RLS-isolation or unbuilt-neighbour-module scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: ⚠ E2/E3/E4 ARE ALL CLOSED BY DEF-441 (2026-08-21) AND EVERY ONE OF THEM WAS A CONSEQUENCE OF THE SAME FALSE DOCUMENT. E2 said the ratified capability matrix "wins" over the build packet's shared DataTable — the matrix said card grid and r10 line 764 draws `<table class="table lt">` with nine headers, so the matrix was wrong and the divergence it told this lane to report was the defect. E3 said the matrix declares no export ("tabular export ships with EP-RAT-04's history view") — that followed from the card grid, and `apps/rating/exports.py` now registers `rate-schedules`. E4 said the pager is local because DataTable's pager is bound to its <table> — there is a <table> now, and DataTable's own pager renders. · NEW E5: a TENTH column r10 does not draw. r10 makes the whole row clickable and offers no per-row control; a schedule can be ARCHIVED (US-RAT-004 TC-4, IS-1) and the Plans tab already carries the same extra column, so this follows the house pattern rather than dropping the capability. · NEW E6: r10's Effective column reads `Jan 1, 2026` = `MMM D, YYYY`, which is NOT one of BR-SHL-023's seven ratified regional formats; this renders through the shared DateCell (the tenant's own choice) and the gap is FILED as DEF-459 rather than hard-coded here. · NEW E7: r10 right-aligns Accounts and leaves Plans left; both are `numeric` here, because two count columns that do not line up is what the flag exists to prevent — the one place this table does not copy r10 cell for cell.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
