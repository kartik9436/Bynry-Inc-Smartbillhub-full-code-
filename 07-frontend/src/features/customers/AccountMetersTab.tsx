// ── Trace ──────────────────────────────────────────────
// Change:   B14 rule 41 (PO 2026-09-13) — the product UI matches the blueprint
//           EXACTLY. `ACC-T07` and `ACC-T07R`, the Meters tab of
//           `04-docs/05-modules/03-customers/blueprint/02-account-detail.md`.
// Story:    US-CUS-011 · screen S21, tab `?tab=meters`.
// Rules:    BR-CUS-034 (customers keeps no copy of another module's row — the
//           meter is read through ASSETS' own endpoint) · BR-AST-031 (the
//           tenant's own lifecycle NAME) · BR-AST-044 (meter type and read
//           method are SEPARATE classifications) · BR-MET-051 (a demand row is
//           not an energy row) · BR-SHL-010 (an undeclared capability is not
//           rendered) · BR-SHL-011 (the drawer is addressable) · BR-SHL-034
//           (one date formatter) · B14 rule 15 (row actions are icons) ·
//           rule 16 (the pagination footer) · rule 19 (the search prompt names
//           what it matches) · rule 20 (one table type) · rule 21 (Tailwind
//           utilities; this file adds NO class to a stylesheet and IS
//           registered in `styles/route-b-migrated.txt`) · rule 31 (no database
//           id on screen) · rule 33 (on-screen text is capped by what it is
//           for) · rule 36 (compose the kit) · rule 41 (the drawing is scope).
// ───────────────────────────────────────────────────────
//
// ── THE DRAWING, QUOTED RATHER THAN LINKED ─────────────────────────────────
// `ACC-T07`:
//
//   toolbar  `All` `Electric` `Water` `Installed` `Removed` · `Filter ▾` ·
//            `⚲ Search by meter number or serial` · `Sort: Meter # ▼` ·
//            `Columns ▾` · `⇩ Export`
//   columns  `METER #` · `SERVICE` · `METER TYPE` · `READ METHOD` ·
//            `INSTALLED` · `MULTIPLIER` · `LAST READ` · `READ ON` · `STATUS` ·
//            `ACTIONS`
//   actions  `☰ Read log` and `…`
//   footer   `1–3 of 3 · Rows per page 50 100 200 ‹ ›`
//
// `ACC-T07R` — the Read log, opened over the tab at
// `?tab=meters&meter=e-4417&view=reads`:
//
//   head     `Read log — E-4417` over
//            `Electric · AMR meter read walk-by · 142 Bakers Row · Suite 1`
//   group    `THE METER` — Meter · Service · Meter type · Read method ·
//            Installed · Multiplier · Status · `Reads held 24, newest first`
//   table    `DATE ▼` · `CHANNEL` · `READING` · `USAGE` · `EXPORT` ·
//            `HOW IT WAS COLLECTED` · `STATUS`
//   footer   `1–7 of 24 · Rows per page 50 100 200 ‹ ›` and
//            `Read from the meter's own record` · `Export the log` · `Close`
//
// ── WHAT THIS REPLACED, AND WHY EACH DIFFERENCE IS A DIFFERENCE ────────────
//
// The tab drew EIGHT columns in an in-panel table with no toolbar, no search,
// no filters and no pagination footer, and then drew **one read log per meter,
// stacked down the page**. The blueprint says in terms why that is wrong:
// *"It is a row action rather than a table per meter, because a unit with six
// meters would otherwise push the list itself off the screen."*
//
//   1 · **`METER TYPE` AND `READ METHOD` WERE ONE CELL.** `BR-AST-044` makes
//       them separate classifications and the blueprint spells out why they
//       must be read apart: *"meter type is what the meter IS, read method is
//       how the reading is COLLECTED — W-2288 was a walk-by meter read by
//       walking to it, while W-4417 is an AMR meter still being read on foot
//       because the collector has not been fitted."* Both were served all
//       along (`meter_type_name`, `read_method_name`); the cell composed them
//       into one string with the manufacturer, so neither could be scanned
//       down and neither could be filtered.
//   2 · **THE READ LOG IS A ROW ACTION** and is addressable — `?meter=…`, so a
//       clerk can send somebody the log they are looking at (`BR-SHL-011`).
//   3 · **`ACTIONS` IS A DRAWN COLUMN** and was not there at all.
//
// ⚠ **THE SERVICE AGREEMENTS PANEL IS NO LONGER ON THIS TAB, AND THE BLUEPRINT
// SAYS WHERE IT WENT:** *"The meters belong to the unit, not to the account …
// The services this account holds are a separate fact and live in the Service
// group on Overview."* Overview draws that group (`acc02-overview.json`, slug
// `service`), so the fact is not lost — it stopped being said twice.
//
// ⚠ **THE DRAWN `Export` IS NOT BUILT AND THAT IS `BR-SHL-010`.**
// `POST /exports` resolves only the resources a module REGISTERS, and nothing
// registers a meter list or a read log. A download button here would be a
// control wired to a 404 (hard-won law 2), and an undeclared capability is not
// rendered — the same sentence `AccountDocumentsTab` and `DisconnectsTab`
// already make about their own toolbars.
import type { ReactNode } from "react";
import { useMemo, useState } from "react";

import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { EyeIcon } from "@/components/icons";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions } from "@/components/RowActions";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { StatusPill } from "@/components/StatusPill";
import { UnitCell, formatQuantity } from "@/components/UnitCell";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
/**
 * ⚠ **`isPeakChannel` IS METERING'S, NOT THIS SCREEN'S.** `BR-MET-051` — a
 * DEMAND channel records a maximum rather than a quantity consumed, so its
 * "usage" is a delta between two maxima that nothing bills, and kW is not kWh.
 * The first draft of this file re-derived the predicate with its own regex,
 * which is exactly the second definition that drifts; four screens already
 * import this one.
 */
import { assetDetailPath } from "@/features/assets/assetsShared";
import { isPeakChannel } from "@/features/metering/demandShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { Dash } from "./customersShared";
import { MeterServiceCell, latestRead } from "./accountDetailTabs";
import type { AccountMeterView } from "./accountDetailTabs";

/** The screen id `TableConfig` keys its column preference on. */
const METERS_TABLE_SCREEN = "S21.meters";

const MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

/** A meter is HELD while its lifecycle stage is one the tenant marks live. */
export function isInstalled(view: AccountMeterView): boolean {
  return view.asset?.behavior_class === "in_service";
}

/**
 * `ACC-T07`'s search: *"Search by meter number or serial"*.
 *
 * ⚠ **CLIENT-SIDE, AND THERE IS NO SERVER TO ASK.** The rows are one
 * `GET /assets/{id}` per meter — `account_detail_dict` serves `{id, asset_no,
 * qualifier}` and the registry facts live on the asset — so there is no list
 * endpoint carrying a `q`. A unit holds a handful of meters, which is the same
 * reasoning `workOrderMatches` records one module over.
 */
export function meterMatches(view: AccountMeterView, q: string): boolean {
  const needle = q.trim().toLowerCase();
  if (needle === "") {
    return true;
  }
  return [view.meter.asset_no, view.asset?.asset_no ?? null, view.asset?.serial_no ?? null]
    .filter((part): part is string => typeof part === "string" && part !== "")
    .some((part) => part.toLowerCase().includes(needle));
}

/**
 * `ACC-T07`'s five chips — `All` `Electric` `Water` `Installed` `Removed`.
 *
 * ⚠ **THE SERVICE HALF IS DERIVED FROM THE ROWS AND IS NEVER TYPED OUT.** The
 * drawing names Electric and Water because its unit carries two meters;
 * hard-won law 2 is the service list typed by hand in two places, so an
 * eleventh service never appears on screen and fails silently. A unit with a
 * gas meter gets a Gas chip without this file changing.
 *
 * `All` is the no-filter state the shared bar already gives, so it is not an
 * option here — declaring it would be a second way to say the same thing.
 */
export function meterFilterOptions(
  views: readonly AccountMeterView[],
  t: Translator,
): { value: string; label: string }[] {
  const services = new Map<string, string>();
  for (const view of views) {
    const code = view.asset?.service;
    if (code != null && code !== "") {
      services.set(code, t(`rating.service.${code}`, { defaultValue: code }));
    }
  }
  return [
    ...[...services].map(([value, label]) => ({ value, label })),
    { value: "installed", label: t("customers.account.meters.filter.installed") },
    { value: "removed", label: t("customers.account.meters.filter.removed") },
  ];
}

export function meterMatchesFilter(view: AccountMeterView, value: string): boolean {
  if (value === "") {
    return true;
  }
  if (value === "installed") {
    return isInstalled(view);
  }
  if (value === "removed") {
    return !isInstalled(view);
  }
  return view.asset?.service === value;
}

/**
 * `ACC-T07`'s `Sort: Meter # ▼` — the only sort it offers, and the default.
 *
 * ⚠ **A METER NUMBER IS NOT A NUMBER**: `M-4021` beside `M-999` sorts wrongly
 * under a plain string compare, which is what a person reads as a broken list.
 * `numeric: true` on the collator is what makes `M-999` come before `M-4021`.
 */
export function compareMeters(a: AccountMeterView, b: AccountMeterView): number {
  const no = (view: AccountMeterView) => view.meter.asset_no ?? view.asset?.asset_no ?? "";
  return no(a).localeCompare(no(b), undefined, { numeric: true, sensitivity: "base" });
}

export function metersTableConfig(
  t: Translator,
  views: readonly AccountMeterView[],
  cells: {
    meterNo: (view: AccountMeterView) => JSX.Element;
    installed: (view: AccountMeterView) => JSX.Element;
    readOn: (view: AccountMeterView) => JSX.Element;
    actions: (view: AccountMeterView) => JSX.Element;
  },
): TableConfig<AccountMeterView> {
  /** The registry did not answer for this meter — every column but the number
   *  comes off the asset, so one dash with one reason serves them all. */
  const absent = (
    <span title={t("customers.account.meters.registryAbsentWhy")}>
      <Dash />
    </span>
  );
  return {
    screenId: METERS_TABLE_SCREEN,
    getRowId: (view) => view.meter.id ?? view.meter.asset_no ?? "",
    searchFields: ["meterNo"],
    searchPlaceholder: "customers.account.meters.search",
    filters: [
      {
        name: "kind",
        label: t("customers.account.meters.filter.label"),
        options: meterFilterOptions(views, t),
      },
    ],
    defaultSort: { sort: "meterNo", dir: "asc" },
    columns: [
      {
        key: "meterNo",
        label: t("customers.account.meters.col.meterNo"),
        identity: true,
        cell: cells.meterNo,
      },
      {
        key: "service",
        label: t("customers.account.meters.col.service"),
        cell: (view) =>
          view.asset?.service != null && view.asset.service !== "" ? (
            <MeterServiceCell code={view.asset.service} t={t} />
          ) : (
            absent
          ),
      },
      {
        // ⚠ **`BR-AST-044` CLASSIFICATION 2 — WHAT THE METER *IS*.** It was
        // composed into one cell with the read method and the manufacturer,
        // so a clerk could not tell an AMR meter from a walk-by one at a
        // glance and could not filter on either.
        key: "meterType",
        label: t("customers.account.meters.col.meterType"),
        cell: (view) =>
          view.asset === null ? (
            absent
          ) : (
            <span>{view.asset.meter_type_name ?? view.asset.type_name}</span>
          ),
      },
      {
        // ⚠ **CLASSIFICATION 3 — HOW THE READING IS *COLLECTED*.** The
        // blueprint's own worked example: `W-4417` is an AMR meter still read
        // on foot because the collector has not been fitted. Two columns that
        // look alike and are not.
        key: "readMethod",
        label: t("customers.account.meters.col.readMethod"),
        cell: (view) =>
          view.asset?.read_method_name == null ? absent : <span>{view.asset.read_method_name}</span>,
      },
      {
        key: "installed",
        label: t("customers.account.meters.col.installed"),
        cell: cells.installed,
      },
      {
        // `BR-AST-012` — a billing-affecting figure, a decimal STRING, never
        // parsed into a float (CLAUDE.md hard rule 2). `formatQuantity` strips
        // the storage artefact (`1.000000` → `1`) and no significant digit.
        key: "multiplier",
        label: t("customers.account.meters.col.multiplier"),
        numeric: true,
        cell: (view) =>
          view.asset?.multiplier == null ? (
            absent
          ) : (
            <span className="tabular-nums">×{formatQuantity(view.asset.multiplier)}</span>
          ),
      },
      {
        // `CR-038 W4` / `BR-MET-051` — the newest record on a demand meter is
        // the DEMAND register, so it is MARKED rather than printed under a
        // heading that reads as the energy one.
        key: "lastRead",
        label: t("customers.account.meters.col.lastRead"),
        numeric: true,
        cell: (view) => {
          const read = latestRead(view);
          if (read?.reading == null) {
            return (
              <span title={t("customers.account.meters.noReadsWhy")}>
                <Dash />
              </span>
            );
          }
          return (
            <span className="tabular-nums" data-peak={isPeakChannel(read.channel) ? "" : undefined}>
              {formatQuantity(read.reading)}
              {isPeakChannel(read.channel) && (
                <span className={`ml-1 text-sm ${MUTED}`}>
                  {t("customers.account.meters.peakMark")}
                </span>
              )}
            </span>
          );
        },
      },
      {
        key: "readOn",
        label: t("customers.account.meters.col.readOn"),
        cell: cells.readOn,
      },
      {
        key: "status",
        label: t("customers.account.meters.col.status"),
        cell: (view) =>
          view.asset === null ? (
            absent
          ) : (
            // `BR-AST-031` — the TENANT's own lifecycle stage name, toned off
            // its behaviour class. Never a label this screen invented.
            <StatusPill tone={isInstalled(view) ? "success" : "neutral"}>
              {view.asset.status_name}
            </StatusPill>
          ),
      },
      {
        key: "actions",
        label: t("customers.account.meters.col.actions"),
        cell: cells.actions,
      },
    ],
  };
}

/**
 * S21's **Meters** tab — the meters on this account's unit.
 *
 * ⚠ **THE METERS BELONG TO THE UNIT, NOT TO THE ACCOUNT**, which is why a
 * meter removed before this tenancy began is still listed: the blueprint says
 * so in terms — *"they stay when the occupant leaves, which is why a meter
 * removed in November 2025 is still listed here under a tenancy that began in
 * 2024."*
 */
export function AccountMetersTab(props: {
  views: readonly AccountMeterView[];
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** The meter whose read log is open, from `?meter=` — so a clerk can send
   *  somebody the log they are looking at (`BR-SHL-011`). */
  openMeterId: string | null;
  onOpenMeter: (id: string | null) => void;
}) {
  const { t } = props;
  const tenantPath = useTenantPath();

  const config = useMemo(
    () =>
      metersTableConfig(t, props.views, {
        meterNo: (view) => (
          // B14 rule 31 — the visible value is the meter NUMBER. A meter the
          // account payload carried with no id has no asset page to open, so
          // it renders as text rather than as a link to nowhere.
          <span data-meter-row={view.meter.asset_no ?? view.meter.id ?? ""}>
            {view.meter.id === null ? (
              (view.meter.asset_no ?? <Dash />)
            ) : (
              <InlineLinkTo to={tenantPath(assetDetailPath(view.meter.id))}>
                <b>{view.meter.asset_no ?? view.asset?.asset_no ?? ""}</b>
              </InlineLinkTo>
            )}
          </span>
        ),
        installed: (view) =>
          view.asset?.install_date == null ? (
            <span title={t("customers.account.meters.registryAbsentWhy")}>
              <Dash />
            </span>
          ) : (
            <DateCell
              value={view.asset.install_date}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
            />
          ),
        readOn: (view) => {
          const read = latestRead(view);
          return read?.date == null ? (
            <span title={t("customers.account.meters.noReadsWhy")}>
              <Dash />
            </span>
          ) : (
            <DateCell
              value={read.date}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
              withTime
            />
          );
        },
        // B14 rule 15 — a row action is an ICON with a tooltip, never a text
        // link, and at most two before a `…`. `ACC-T07` draws `☰ Read log`
        // and a `…`; the second is the asset's own page, which is the only
        // other thing a person can do to a meter from here.
        actions: (view) => (
          <RowActions>
            <RowAction
              icon={<EyeIcon />}
              label={t("customers.account.meters.readLog")}
              reason={
                view.meter.id === null ? t("customers.account.meters.readLogNoAsset") : null
              }
              onClick={() => props.onOpenMeter(view.meter.id)}
            />
          </RowActions>
        ),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, props.views, props.timeZone, props.dateFormat, tenantPath],
  );

  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));

  const matched = props.views
    .filter((view) => meterMatchesFilter(view, state.filters.kind ?? ""))
    .filter((view) => meterMatches(view, state.q));
  const sorted = [...matched].sort(compareMeters);
  const from = (state.page - 1) * state.per;
  const page = sorted.slice(from, from + state.per);

  const open =
    props.openMeterId === null
      ? null
      : (props.views.find((view) => view.meter.id === props.openMeterId) ?? null);

  return (
    /* `data-account-overview` and the `data-overview-group` hook are what the
       BROWSER census selects on — jsdom computes no layout, so no vitest case
       in this repo can say the screen LOOKS like the drawing. One column on
       this tab, because the drawing gives it one. */
    <div data-account-overview="">
      <div className="flex min-w-0 flex-col">
        <Panel
          as="section"
          tone="group"
          data-overview-group="meters"
          data-screen={METERS_TABLE_SCREEN}
          title={t("customers.account.panel.meters")}
        >
          <DataTable<AccountMeterView>
            config={config}
            state={state}
            onStateChange={setState}
            rows={page}
            totalRows={matched.length}
            loading={props.views.some((view) => view.loading)}
            filterBarSlot={
              <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
            }
            empty={{
              title: t("customers.account.meters.emptyTitle"),
              helper: t("customers.account.metersEmpty"),
            }}
          />
        </Panel>

        {open !== null && (
          <MeterReadLogPanel
            view={open}
            t={t}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            onClose={() => props.onOpenMeter(null)}
          />
        )}
      </div>
    </div>
  );
}

/**
 * `ACC-T07R` — one meter's reads, over the tab it was opened from.
 *
 * ⚠ **IT OPENS OVER THE TAB RATHER THAN IN A MODAL, AND IT IS ADDRESSABLE.**
 * The drawing's own address is `?tab=meters&meter=e-4417&view=reads`, and B14
 * rule 30's non-rule (DECLINED 2026-08-30) plus the modal/screen test both say
 * the same thing about a surface that holds a table of its own and that
 * somebody would want to link to: it is not a modal. This is the shape
 * `WorkOrderPanel` already uses one module over for exactly the same job — a
 * record opened over the list it was opened from, driven by a query
 * parameter — so the product has one answer rather than two.
 *
 * ⚠ **`Export the log` IS NOT DRAWN AS A DISABLED BUTTON, IT IS NOT DRAWN.**
 * `POST /exports` registers no reads resource, and `BR-SHL-010` keeps an
 * undeclared capability unrendered — not `BR-SHL-025`'s disabled-with-a-reason,
 * which is the posture for a control this ROLE cannot use rather than one the
 * PRODUCT does not have.
 */
export function MeterReadLogPanel(props: {
  view: AccountMeterView;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
}) {
  const { t, view } = props;
  const tenantPath = useTenantPath();
  const number = view.meter.asset_no ?? view.asset?.asset_no ?? "";
  const reads = view.reads ?? [];

  /** `THE METER`'s rows, in the drawn order. A fact with no answer is a dash
   *  and never a blank — the asset registry may simply not have answered. */
  const facts: { label: string; value: ReactNode }[] = [
    { label: t("customers.account.readLog.field.meter"), value: number || <Dash /> },
    {
      label: t("customers.account.readLog.field.service"),
      value:
        view.asset?.service != null && view.asset.service !== "" ? (
          <MeterServiceCell code={view.asset.service} t={t} />
        ) : (
          <Dash />
        ),
    },
    {
      label: t("customers.account.readLog.field.meterType"),
      value: view.asset?.meter_type_name ?? view.asset?.type_name ?? <Dash />,
    },
    {
      label: t("customers.account.readLog.field.readMethod"),
      value: view.asset?.read_method_name ?? <Dash />,
    },
    {
      label: t("customers.account.readLog.field.installed"),
      value:
        view.asset?.install_date == null ? (
          <Dash />
        ) : (
          <DateCell
            value={view.asset.install_date}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
        ),
    },
    {
      label: t("customers.account.readLog.field.multiplier"),
      value:
        view.asset?.multiplier == null ? <Dash /> : `×${formatQuantity(view.asset.multiplier)}`,
    },
    {
      label: t("customers.account.readLog.field.status"),
      value: view.asset?.status_name ?? <Dash />,
    },
  ];

  return (
    <Panel as="section" accent data-meter-read-log={view.meter.id ?? number}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3>{t("customers.account.readLog.title", { meter: number })}</h3>
          {/* The drawing's subtitle: what this meter is, then where it stands.
              ⚠ **THE ADDRESS IS NOT COMPOSED HERE.** Hard rule 8 keeps an
              address on `premises` and every other entity walks to it; the
              asset's own served `assigned_address` is that walk's answer, and
              a blank one is simply not printed rather than assembled from
              parts this screen holds. */}
          <p className={`m-0 mt-1 text-sm ${MUTED}`} data-read-log-subtitle="">
            {[
              view.asset?.meter_type_name ?? view.asset?.type_name ?? null,
              view.asset?.read_method_name ?? null,
              view.asset?.assigned_address ?? null,
            ]
              .filter((part): part is string => typeof part === "string" && part !== "")
              .join(" · ")}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {view.meter.id !== null && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                window.location.assign(tenantPath(assetDetailPath(view.meter.id ?? "")));
              }}
            >
              {t("customers.account.readLog.openAsset")}
            </Button>
          )}
          <Button variant="secondary" size="sm" onClick={props.onClose}>
            {t("customers.account.readLog.close")}
          </Button>
        </div>
      </div>

      <h4 className="mb-2 mt-4 font-heading text-xs uppercase tracking-kicker text-accent">
        {t("customers.account.readLog.theMeter")}
      </h4>
      <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
        {facts.map((fact) => (
          <div key={fact.label} className="contents">
            <dt className={`m-0 text-sm ${MUTED}`}>{fact.label}</dt>
            <dd className="m-0 text-base">{fact.value}</dd>
          </div>
        ))}
      </dl>
      {/* The drawing's own line — *Reads held 24, newest first*. A FACT, five
          words (B14 rule 33), and it is the thing that tells a clerk the list
          below is not everything when it is paged. */}
      <p className={`m-0 mt-3 text-sm ${MUTED}`} data-reads-held="">
        {t("customers.account.readLog.readsHeld", { count: reads.length })}
      </p>

      <h4 className="mb-2 mt-4 font-heading text-xs uppercase tracking-kicker text-accent">
        {t("customers.account.readLog.theReads")}
      </h4>
      {view.readsFailed ? (
        <p className={`m-0 text-base ${MUTED}`}>{t("customers.account.readLog.failed")}</p>
      ) : view.reads === null ? (
        <p className={`m-0 text-base ${MUTED}`}>{t("customers.account.readLog.loading")}</p>
      ) : reads.length === 0 ? (
        <p className={`m-0 text-base ${MUTED}`}>{t("customers.account.readLog.empty")}</p>
      ) : (
        <div className="overflow-x-auto">
          <PlainTable>
            <thead>
              <tr>
                <th>{t("customers.account.readLog.col.date")}</th>
                <th>{t("customers.account.readLog.col.channel")}</th>
                <th>{t("customers.account.readLog.col.reading")}</th>
                <th>{t("customers.account.readLog.col.usage")}</th>
                <th>{t("customers.account.readLog.col.export")}</th>
                <th>{t("customers.account.readLog.col.collected")}</th>
                <th>{t("customers.account.readLog.col.status")}</th>
              </tr>
            </thead>
            <tbody>
              {reads.map((read, index) => (
                <tr key={read.read_id ?? `${read.date ?? "read"}-${index}`}>
                  <td>
                    {read.date === null ? (
                      <Dash />
                    ) : (
                      <DateCell
                        value={read.date}
                        timeZone={props.timeZone}
                        dateFormat={props.dateFormat}
                      />
                    )}
                  </td>
                  {/* ⚠ **A DRAWN COLUMN THAT WAS NOT BUILT.** `ACC-T07R` heads
                      it `CHANNEL` and its rows read `Total`; `BR-MET-051` is
                      why it matters — a demand row and an energy row sit in
                      one log together, and without this column a reader
                      cannot tell which they are looking at. */}
                  <td>
                    {read.channel === null ? (
                      <Dash />
                    ) : (
                      t(`metering.reads.channel.${read.channel}`, { defaultValue: read.channel })
                    )}
                  </td>
                  {/* `DEF-646` — the register value with the storage artefact
                      stripped and every significant digit kept. */}
                  <td className="tabular-nums">
                    {read.reading != null ? formatQuantity(read.reading) : <Dash />}
                  </td>
                  <td>
                    {/* CLAUDE.md hard rule 3 — a quantity NEVER travels without
                        its unit, so a figure whose unit did not arrive is a
                        dash. On a DEMAND channel `consumption` is a delta
                        between two maxima that nothing bills (`BR-MET-051`), so
                        the cell states that rather than printing it. */}
                    {isPeakChannel(read.channel) ? (
                      <span className={`text-sm ${MUTED}`}>
                        {t("customers.account.readLog.peakNoUsage")}
                      </span>
                    ) : read.consumption !== null && read.unit !== null ? (
                      <UnitCell quantity={read.consumption} unit={read.unit} />
                    ) : (
                      <Dash />
                    )}
                  </td>
                  {/* ⚠ **`EXPORT` IS A DASH AND NOT A ZERO, AND THE BLUEPRINT
                      SAYS WHY:** *"The column is the other half of a
                      net-metering pair and fills where a meter exports —
                      solar, chiefly. This one only imports, so every row is a
                      dash rather than a zero, which would read as 'it exported
                      nothing'."* */}
                  <td>
                    {read.export !== null && read.export_unit !== null ? (
                      <UnitCell quantity={read.export} unit={read.export_unit} />
                    ) : (
                      <Dash />
                    )}
                  </td>
                  <td>
                    {read.source === null ? (
                      <Dash />
                    ) : (
                      t(`metering.reads.source.${read.source}`, { defaultValue: read.source })
                    )}
                  </td>
                  <td>
                    {read.status === null ? (
                      <Dash />
                    ) : (
                      t(`metering.reads.status.${read.status}`, { defaultValue: read.status })
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      )}
      {/* `ACC-T07R`'s closing line, and it is a FACT rather than a rationale:
          reads are taken and corrected in Reads, never here. Six words. */}
      <p className={`m-0 mt-3 text-sm ${MUTED}`}>{t("customers.account.readLog.correctedIn")}</p>
    </Panel>
  );
}

export default AccountMetersTab;

// ── Lifecycle ─────────────────────────────────────────────
// generated: 2026-09-13 by the ACC-02 conformance lane (tabs Usage · Meters ·
//            Work · Adjustments)
// exceptions: E3 no `⇩ Export` on either table — `POST /exports` registers
//             neither a meter list nor a read log, and BR-SHL-010 keeps an
//             undeclared capability unrendered rather than wired to a 404 ·
//             E3 the read log opens OVER the tab as an addressable panel
//             rather than as a modal: it holds a table of its own and the
//             drawing gives it its own address, which is the modal/screen
//             test's answer and `WorkOrderPanel`'s existing shape
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
