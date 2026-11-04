// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W3 (B18 §5.2.2) tasks 3.4 · 3.5 · 3.6 · 3.7 · 3.9 · 3.10 ·
//           3.11 — the ACC-01 tab bodies: the Overview's recent-bills panel,
//           usage-trend frame and `→ Update method`; the Payments tab's
//           deposit row; the Adjustments and Documents frames; the Meters tab
//           re-specified against the POST-CR-028 asset model with its nested
//           read log; the Notes tab as CARDS; and the Audit tab's portal actor.
//           Screens: S21 (the account detail).
// Story:    US-CUS-009 (Overview panels) · US-CUS-010 (Payments · Adjustments) ·
//           US-CUS-011 (Meters · Documents · Notes · Audit) ·
//           US-BIL-025 (the invoice list this panel reads, scoped by account) ·
//           US-AST-005 (the asset read log this tab nests).
// Rules:    BR-CUS-023 (the deposit is a LOOKUP from the plan deposit schedule,
//           unbuilt) · BR-CUS-028 (portal data is NOT fabricated in v1) ·
//           BR-CUS-034 (other modules are read through their own service
//           functions — customers keeps no copy of a billing, payments or
//           assets row) · BR-CUS-035 (notes are one of the two tabs customers
//           owns outright) · BR-AST-029 (the two typed read records) ·
//           BR-AST-012 (multiplier/unit are billing-affecting, forward only) ·
//           BR-SHL-023 (one money path) · BR-SHL-025 (a forbidden control is
//           disabled WITH its reason) · BR-SHL-034 (one date formatter) ·
//           B14 rule 20 (one table type) · B14 rule 21 (Tailwind utilities —
//           this file adds NO class to any stylesheet and is registered in
//           `styles/route-b-migrated.txt`).
// ───────────────────────────────────────────────────────
// ⚠ **THE REFERENCE IS r10's OWN MARKUP, NOT B18's PROSE.** B18 §5.2 cites
// `[shot: ACC-01 detail ×10]` and those screenshots are not in this repo
// (DEF-631 / B18 D5) — but `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html`
// DRAWS this screen, every tab of it, and that markup is what the tables below
// are measured against:
//
//   Meters       Meter # · Service · Type · Install date · Multiplier ·
//                Last read (right) · Last read date · Status
//   Read log     "Meter M-4021 · Read log" — Date · Read · Usage · Source · Notes
//   Adjustments  Date · Adjustment # · Reason · Applied to · Amount · Approved by
//   Documents    Document · Type · Date · Uploaded by · Size
//   Recent bills Bill # · Cycle · Usage · Amount · Status, + "All bills →"
//   Notes        CARDS: title, `date · author` right-aligned, body
//
// **Two of those six have no endpoint at all** and are built as FRAMES: the
// headings r10 draws, and one spanning cell that states the absence. An empty
// `<tbody>` would assert "this account was never adjusted", which is a claim
// about a customer nobody made.
//
// **Four of them are REAL now**, and three of those four were stated absences
// in this screen yesterday:
//   · recent bills — `GET /invoices?f.account_id=` is served (DEF-474 said so);
//   · the meter rows — `GET /assets/{id}` carries the post-CR-028 columns;
//   · the read log  — `GET /assets/{id}/reads` was served by CR-028 AST-W2
//     (DEF-475, closed), and the sentence that said otherwise is deleted.
// Hard-won law 1: the string changes with the fact, in the same commit.
import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAsset, getAssetReads, getInvoices } from "@/api/endpoints";
import type {
  AccountMeterRef,
  AccountNote,
  AssetDetail,
  AssetReadRow,
  InvoiceRow,
} from "@/api/endpoints";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { StatusPill } from "@/components/StatusPill";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import { billDetailPath, billStatusLabel, billStatusTone } from "@/features/billing/billingShared";
import { Fact, FactList, GuardedButton } from "@/features/metering/meteringShared";
import { serviceBadge } from "@/features/rating/ratingShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  ReadOutRow,
  SegmentButton,
  USAGE_ALL,
  accountUsageKey,
  getAccountUsage,
  readOuts,
  usageViewState,
} from "./AccountUsageTab";
import type { UsagePoint, UsageSeries } from "./AccountUsageTab";
import { Dash } from "./customersShared";

/** The muted 65% text r10 uses for every secondary line on this screen. */
const MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

/** r10's panel head: a title on the left, a `see →` word on the right. */
const PANEL_HEAD = "mb-2 flex items-baseline justify-between gap-3";

/** r10's `.see` — the accent word that leads somewhere. */
const SEE_LINK =
  "cursor-pointer border-0 bg-transparent p-0 font-body text-base text-accent " +
  "underline-offset-2 hover:underline";

/** How many bills r10's Overview panel draws. */
export const RECENT_BILLS = 4;

/**
 * r10's two usage windows, and the Overview OPENS ON TWELVE — r10 heads this
 * panel *"Usage trend · last 12 months"* while the Usage TAB draws 24. The
 * clerk can still switch it; this decides only where it starts.
 */
const USAGE_MONTHS = [12, 24] as const;

// ── The meters this account's unit carries, as the ASSETS module holds them ──

/**
 * `GET /accounts/{id}` serves three fields per meter — `{id, asset_no,
 * qualifier}` — because `account_detail_dict` maps exactly those three off
 * `assets.selectors.assets_on_unit`. r10's Meters table draws EIGHT columns,
 * and the other five (service, type, install date, multiplier, status) live on
 * the asset itself.
 *
 * ⚠ **SO THE ROW IS READ FROM THE ASSETS MODULE, NOT COPIED INTO CUSTOMERS.**
 * BR-CUS-034 forbids a customers-side read model of another module's row, and
 * this is the same posture the Bills tab takes with billing's S30 list and the
 * Payments tab with payments' S33: one implementation of what a meter IS, read
 * through the owning module's own endpoint. It costs one request per meter —
 * two on the demo account — and every one is cached by asset id, so the header
 * chips and this table share a single answer.
 *
 * The reads come from the SAME asset's `GET /assets/{id}/reads`, newest first
 * (CR-028 AST-W2 T4). That list is both the nested read log AND where the
 * `Last read` / `Last read date` columns come from: `asset_dict` serves
 * `last_read` for SUB-METERS only (DEF-592 scoped it there), so a top-level
 * meter has no last-read field at all, and taking the head of the read list is
 * reading a served answer rather than deriving one.
 */
export interface AccountMeterView {
  meter: AccountMeterRef;
  asset: AssetDetail | null;
  assetFailed: boolean;
  reads: readonly AssetReadRow[] | null;
  readsFailed: boolean;
  loading: boolean;
}

export const accountMeterAssetKey = (assetId: string) =>
  ["accounts", "meter-asset", assetId] as const;
export const accountMeterReadsKey = (assetId: string) =>
  ["accounts", "meter-reads", assetId] as const;

/**
 * One view per meter on the unit, in the order the account payload lists them.
 *
 * A meter the account carries with NO id (an older payload shape) is kept in
 * the list and simply has no asset: the number still renders, the five
 * registry columns state their absence, and the meter is never dropped —
 * dropping it would under-report what is on the customer's unit.
 */
export function useAccountMeterViews(
  meters: readonly AccountMeterRef[],
  client?: ApiClient,
): AccountMeterView[] {
  const resolved = client ?? api;
  const withIds = meters.filter((meter) => meter.id !== null);
  const assetQueries = useQueries({
    queries: withIds.map((meter) => ({
      queryKey: accountMeterAssetKey(meter.id as string),
      queryFn: () => getAsset(meter.id as string, resolved),
      retry: false,
    })),
  });
  const readQueries = useQueries({
    queries: withIds.map((meter) => ({
      queryKey: accountMeterReadsKey(meter.id as string),
      queryFn: () => getAssetReads(meter.id as string, resolved),
      retry: false,
    })),
  });
  return meters.map((meter) => {
    const index = meter.id === null ? -1 : withIds.findIndex((row) => row.id === meter.id);
    const assetQuery = index === -1 ? undefined : assetQueries[index];
    const readsQuery = index === -1 ? undefined : readQueries[index];
    return {
      meter,
      asset: assetQuery?.data ?? null,
      assetFailed: assetQuery?.isError === true,
      // `AST-B-19` — the account's Meters tab shows a meter's RECENT reads, so
      // it takes the page's rows. This screen is the reason the break reached
      // beyond Assets: the same wrapper feeds an account's tab, and it was
      // handing this view the envelope object.
      reads: readsQuery?.data?.rows ?? null,
      readsFailed: readsQuery?.isError === true,
      loading: assetQuery?.isPending === true || readsQuery?.isPending === true,
    };
  });
}

/** The chips the header draws: the meter number beside the service the ASSET
 *  says it measures. A meter whose asset has not answered contributes nothing,
 *  so the chip degrades to the bare service rather than to a guessed pairing. */
export function meterChipsFrom(
  views: readonly AccountMeterView[],
): { assetNo: string | null; service: string | null }[] {
  return views.map((view) => ({
    assetNo: view.meter.asset_no ?? view.asset?.asset_no ?? null,
    service: view.asset?.service ?? null,
  }));
}

/** The newest read on a meter — the head of a NEWEST-FIRST served list. */
export function latestRead(view: AccountMeterView): AssetReadRow | null {
  return view.reads !== null && view.reads.length > 0 ? view.reads[0] : null;
}

// ⚠ **`AccountMetersTab` LEFT THIS FILE ON 2026-09-13 (B14 rule 41) AND IS NOW
//    `./AccountMetersTab.tsx`.** It drew EIGHT columns in an in-panel table
//    with no toolbar, no search, no filter and no pagination footer, and then
//    drew ONE READ LOG PER METER stacked down the page. `ACC-T07` draws ten
//    columns, the shared table's toolbar and footer, and the read log as a ROW
//    ACTION — and the blueprint says why: *"It is a row action rather than a
//    table per meter, because a unit with six meters would otherwise push the
//    list itself off the screen."*
//
//    Two of the ten were SERVED and composed away: `BR-AST-044` makes meter
//    type and read method separate classifications, and this table joined them
//    into one cell with the manufacturer, so neither could be scanned down and
//    neither could be filtered. The blueprint's own worked example is why that
//    matters — `W-4417` is an AMR meter still being read on foot.
//
//    `useAccountMeterViews`, `meterChipsFrom`, `latestRead` and
//    `MeterServiceCell` STAY HERE: the header's chips and the Overview's own
//    meters group read them, so they are the shared half and the new file
//    imports them rather than copying them.

/**
 * The service square + its name, from the ONE badge map the product shares.
 *
 * ⚠ **EXPORTED SINCE 2026-09-03 (`DEF-3483`), AND THE EXPORT IS THE FIX.** The
 * Product Owner, on this same screen: *"Services on this account - I will show
 * name of the service inform of similar to this - E Electric"* — pointing at
 * the Meters table BELOW, which is this cell, and asking the panel above it to
 * read the same way. "Services on this account" drew the bare coloured square
 * through `meteringShared.ServiceTags`, so an account selling six services was
 * six coloured letters — W E S T St F — and a clerk had to know that `St` is
 * storm water and `So` is solar to read its own service list.
 *
 * It is EXPORTED rather than copied, and the reason is the one written over the
 * badge map itself: six of the eleven services cannot be told apart from their
 * name (Sewer, Solar and Storm water all start with `S`), so a second table of
 * letters anywhere is `DEF-348`'s icon split with letters instead of pencils.
 * One cell, one map, two panels.
 *
 * It lives HERE, in a file `route-b-migrated.txt` lists, because the utilities
 * below only compile for a file on that list (DEF-974) — `AccountDetailPage.tsx`
 * is NOT on it, so the same markup written there would render as nothing at all
 * while `tsc`, eslint and every `toContain` assertion passed.
 */
export function MeterServiceCell(props: { code: string; t: Translator }) {
  const badge = serviceBadge(props.code);
  const name = props.t(`rating.service.${props.code}`, { defaultValue: props.code });
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        aria-hidden="true"
        className="inline-flex h-5 w-5 shrink-0 items-center justify-center font-heading text-xs font-extrabold leading-none text-bg"
        style={{ background: `var(${badge.token})` }}
      >
        {badge.letter}
      </span>
      <span>{name}</span>
    </span>
  );
}

// ⚠ **`MeterTypeCell` AND `MeterReadLog` LEFT THIS FILE WITH THEIR ONLY CALLER
//    ON 2026-09-13.** `MeterTypeCell` composed `BR-AST-044`'s three separate
//    classifications into one string (`AMI · Itron OpenWay CENTRON`); `ACC-T07`
//    draws METER TYPE and READ METHOD as two columns, so the composition is
//    what had to go. `MeterReadLog` was a panel drawn once PER METER under the
//    table; `ACC-T07R` makes it a row action with its own address
//    (`?meter=…&view=reads`), a `THE METER` group and seven columns including
//    CHANNEL and EXPORT, which this one did not draw at all. Both now live in
//    `./AccountMetersTab.tsx` in their drawn shape.

// ── 3.4 · Overview — recent bills, the usage-trend frame, the payment method ─

export const accountRecentBillsKey = (accountId: string) =>
  ["accounts", "recent-bills", accountId] as const;

/**
 * r10's `Recent bills` panel — billing's OWN list, scoped by `f.account_id`.
 *
 * ⚠ **THIS PANEL SAID FOR THREE DAYS THAT THE ENDPOINT DID NOT EXIST, AND THE
 * SAME FILE'S BILLS TAB WAS READING IT** (DEF-474, still open on the usage
 * half). `GET /invoices` is mounted, takes `f.account_id` and orders by issue
 * date descending server-side. Nothing here is a customers read model
 * (BR-CUS-034): it is one request to billing, and the row renders through
 * billing's own status vocabulary.
 *
 * `per` asks for the page size the server allows and the panel takes the first
 * four — `clamp_page_size` rounds 4 UP to nothing and DOWN to 50, so asking
 * for four would silently fetch fifty anyway; slicing here says so out loud.
 */
export function RecentBillsPanel(props: {
  accountId: string;
  client?: ApiClient;
  t: Translator;
  onSeeAll: () => void;
  /** `ACC-S15` — this group's edit control, built by the page and passed in.
   *  It is REFUSED on this panel (hard rule 4: an issued bill is credited, not
   *  changed) and is drawn anyway, because a group with nothing to edit still
   *  carries its control WITH its reason rather than going blank. */
  pencil?: ReactNode;
}) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const query = useQuery({
    queryKey: accountRecentBillsKey(props.accountId),
    queryFn: () =>
      getInvoices(
        {
          filters: { account_id: props.accountId },
          sort: "issue_date",
          dir: "desc",
          per: DEFAULT_PAGE_SIZE,
        },
        props.client ?? api,
      ),
    retry: false,
    enabled: props.accountId !== "",
  });
  const rows: InvoiceRow[] = (query.data?.results ?? []).slice(0, RECENT_BILLS);
  return (
    /* ⚠ **HEADED `HISTORY`, IN THE `group` TONE, WITH `All bills →` ON THE
       HEADING ROW (B14 rule 41, 2026-09-13).** The blueprint draws this as one
       of the Overview's eleven named groups; it shipped as a plain bordered
       `Recent bills` card. **Only the frame moved** — the query, the rows, the
       columns and the `All bills →` control are the ones this panel already
       had, so no second bills reader exists. `Panel`'s own `trailing` slot
       carries the control, which is what keeps the accent rule one unbroken
       line under both (see `GROUP_HEAD` in `components/Panel.tsx`). */
    <Panel
      as="section"
      tone="group"
      data-overview-group="history"
      title={t("customers.account.panel.history")}
      trailing={
        <div className="flex items-center gap-3">
          <button type="button" className={SEE_LINK} onClick={props.onSeeAll}>
            {t("customers.account.recentBills.all")}
          </button>
          {props.pencil}
        </div>
      }
    >
      {query.isPending ? (
        <p className={`m-0 text-base ${MUTED}`}>{t("customers.account.recentBills.loading")}</p>
      ) : query.data === undefined ? (
        <p className={`m-0 text-base ${MUTED}`}>{t("customers.account.recentBills.failed")}</p>
      ) : rows.length === 0 ? (
        /* The blueprint draws the absence as a heading and a sentence, not as
           one muted line. `recentBills.empty` is the heading's own words and is
           reused rather than restated. */
        <>
          <p className="m-0 mb-1 font-heading text-md font-bold uppercase">
            {t("customers.account.recentBills.empty")}
          </p>
          <p className={`m-0 mb-3 text-sm ${MUTED}`}>
            {t("customers.account.recentBills.emptyWhy")}
          </p>
        </>
      ) : (
        <div className="overflow-x-auto">
          <PlainTable>
            <thead>
              <tr>
                <th>{t("customers.account.recentBills.col.billNo")}</th>
                <th>{t("customers.account.recentBills.col.cycle")}</th>
                <th>{t("customers.account.recentBills.col.usage")}</th>
                <th>{t("customers.account.recentBills.col.amount")}</th>
                <th>{t("customers.account.recentBills.col.status")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    {/* ⛔ DEF-3158 — this read `row.invoice_no ?? row.id.slice(0, 8)`
                        until 2026-09-02, so a bill whose number had not been
                        minted showed eight characters of its database id as the
                        link text. B14 rule 31 forbids it outright ("no Databse
                        ID on screen - that is a rule", PO 2026-08-31), and a
                        TRUNCATION is the same breach as a full uuid: it is still
                        the database's value and a person still cannot use it.
                        The rule's own answer where no human-facing number
                        exists: say so in words, and let the internal value ride
                        on `title` as evidence. The link still works — it always
                        navigated by `row.id`, which is a HREF and not a visible
                        value. */}
                    <InlineLinkTo to={tenantPath(billDetailPath(row.id))}>
                      {row.invoice_no ?? (
                        <span title={row.id}>{t("customers.account.recentBills.noBillNo")}</span>
                      )}
                    </InlineLinkTo>
                  </td>
                  <td>{row.cycle_label ?? <Dash />}</td>
                  <td>
                    {/* r10 prints `684 kWh · 3.72 kgal` here. A bill ROW carries
                        its money totals and no quantity at all — the usage is
                        on the bill's LINES — so this states the absence rather
                        than opening every bill on an overview panel. */}
                    <span title={t("customers.account.recentBills.usageAbsentWhy")}>
                      <Dash />
                    </span>
                  </td>
                  <td className="tabular-nums">
                    <MoneyCell amount={row.total} currency={row.currency} />
                  </td>
                  <td>
                    <StatusPill tone={billStatusTone(row.status, row.past_due)}>
                      {billStatusLabel(row, t)}
                    </StatusPill>
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      )}
    </Panel>
  );
}

/**
 * r10's `Usage trend · last 12 months` — twelve bars and a `Details →`.
 *
 * ⚠ **THIS PANEL SAID *"no endpoint publishes that for a meter, an account or
 * a service"* UNTIL 2026-09-03, AND ONE HAD BEEN PUBLISHED SINCE CR-030 W3
 * TASK 3.8 (`DEF-3487`, hard-won law 1 for the third time on this screen).**
 * The Product Owner: *"we did 2 month bills, which means 2 months detaisl are
 * available - why theya re not displayed - Usage trend ... if it is multi
 * service, then you ahve to provdie drop down for each service that is
 * metered"*. They are right on both counts, and the second one was already
 * built: `GET /accounts/{id}/usage` serves a per-service monthly series, and
 * `AccountUsageTab` — mounted one tab along, on the SAME screen — draws it with
 * a segment control listing the account's own services and a chart per service
 * in that service's own unit.
 *
 * **SO THIS PANEL WAS THE ONLY THING SAYING THE FEATURE DID NOT EXIST**, while
 * the tab beside it drew it. Its sentence had rotted twice: the FIRST version
 * blamed a reads filter CR-028 shipped (`DEF-475`, closed) and the second
 * blamed a missing monthly series that task 3.8 then landed. Both were true
 * when written and neither was re-read, which is exactly the shape law 1
 * describes and G38 says no source-reading check can catch.
 *
 * **WHAT IT DRAWS NOW.** The real component, over a TWELVE-month window
 * because r10's overview panel is *"last 12 months"* and the tab's own default
 * of 24 is the tab's. Everything else is the tab's: the service selector the
 * PO asked for, one chart per service, each titled with its own unit, an
 * absent month drawn as no bar rather than a zero (BR-MET-106 — *"zero usage
 * and no read are different claims about a customer"*), and estimates marked.
 *
 * **The panel keeps its heading and its `Details →`, and it is NOT a `Panel`
 * any more.** `UsageChart` draws its own panel per service, so wrapping them
 * in one would nest a card inside a card; the heading row and the link sit
 * above them instead. B14 rule 32 is satisfied by subtraction — the section
 * now carries a chart and NO sentence at all, where it used to carry
 * thirty-nine words explaining why there was nothing to see.
 *
 * ⚠ **`customers.account.arrives.usageTrend` IS RETIRED FROM ALL ELEVEN
 * CATALOGUES IN THE SAME COMMIT**, rather than left behind for a future lane to
 * find and believe. A false sentence that no longer renders is still a false
 * sentence a grep will return.
 */
export function UsageTrendPanel(props: {
  accountId: string;
  client?: ApiClient;
  t: Translator;
  onDetails: () => void;
  /** `ACC-S15` — see `RecentBillsPanel`. Refused here because the figure is
   *  MEASURED: the read is what gets corrected, on the meter. */
  pencil?: ReactNode;
}) {
  const { t } = props;
  const [months, setMonths] = useState<number>(USAGE_MONTHS[0]);
  const query = useQuery({
    queryKey: accountUsageKey(props.accountId, months),
    queryFn: () => getAccountUsage(props.accountId, months, props.client ?? api),
    retry: false,
    enabled: props.accountId !== "",
  });
  const state = usageViewState(query);
  const payload = query.data;
  return (
    <Panel
      as="section"
      tone="group"
      data-overview-group="usage-trend"
      title={t("customers.account.panel.usageTrend")}
      trailing={
        <div className="flex items-center gap-3">
          <button type="button" className={SEE_LINK} onClick={props.onDetails}>
            {t("customers.account.usageTrend.details")}
          </button>
          {props.pencil}
        </div>
      }
    >
      {/* r10's window control, and it is the Usage tab's own component rather
          than a second one — the two surfaces must not disagree about which
          window is selected (B14 rule 36). */}
      <div
        className="mb-3 flex gap-1"
        role="group"
        aria-label={t("customers.account.usage.windowLabel")}
      >
        {USAGE_MONTHS.map((option) => (
          <SegmentButton
            key={option}
            label={t("customers.account.usage.window", { months: option })}
            active={months === option}
            onClick={() => setMonths(option)}
          />
        ))}
      </div>
      {state !== "ready" || payload === undefined ? (
        <p className={`m-0 text-base ${MUTED}`}>
          {t(`customers.account.usage.${state === "failed" ? "failed" : "loading"}`)}
        </p>
      ) : payload.series.length === 0 ? (
        <p className={`m-0 text-base ${MUTED}`}>{t("customers.account.usage.empty")}</p>
      ) : (
        <>
          <UsageTrendTable series={payload.series} t={t} />
          <ReadOutRow
            items={readOuts(payload.series, payload, USAGE_ALL, t)}
            basis={
              payload.series.length > 1 && payload.series[0] !== undefined
                ? t("customers.account.usage.kpi.basis.last12", {
                    service: payload.series[0].service.name,
                  })
                : t("customers.account.usage.kpi.basis.last12Plain")
            }
          />
        </>
      )}
    </Panel>
  );
}

/**
 * The Overview's usage trend AS A TABLE — `MONTH` and one column per service,
 * newest month first.
 *
 * ⚠ **IT REPLACED A BAR CHART ON THE PRODUCT OWNER'S OWN INSTRUCTION, 2026-09-13**,
 * read off the running screen: *"we just need table and not graphs here"*. The
 * blueprint draws this group the same way — `MONTH · ELECTRIC · WATER`, six
 * rows, newest first — so the drawing and the ruling agree and the bars were
 * the divergence. The Usage TAB keeps its charts; only this group changes.
 *
 * **ONE COLUMN PER SERVICE AND NO PICKER, DELIBERATELY.** The chart needed a
 * picker because it could draw one series legibly at a time; a table holds them
 * side by side, which is what the drawing draws and what a clerk on the phone
 * actually reads.
 *
 * ⚠ **AN ABSENT MONTH IS A DASH AND NEVER A ZERO** (`BR-MET-106` — *"zero usage
 * and no read are different claims about a customer"*), and the unit rides on
 * every cell because hard rule 3 says consumption is never shown without one.
 * An ESTIMATED month is marked, as it is under the chart.
 */
function UsageTrendTable(props: { series: readonly UsageSeries[]; t: Translator }) {
  const { series, t } = props;
  // The month axis is the UNION of every series' months, newest first — a
  // service fitted later has fewer points than its neighbour, and dropping the
  // months it does not cover would silently shorten the other's history.
  const months = [...new Set(series.flatMap((one) => one.points.map((point) => point.month)))]
    .sort()
    .reverse();
  const cell = (one: UsageSeries, month: string): UsagePoint | undefined =>
    one.points.find((point) => point.month === month);
  return (
    <div className="overflow-x-auto">
      <PlainTable>
        <thead>
          <tr>
            <th>{t("customers.account.usage.col.month")}</th>
            {series.map((one) => (
              <th key={one.service.id}>{one.service.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {months.map((month) => (
            <tr key={month}>
              <td>{month}</td>
              {series.map((one) => {
                const point = cell(one, month);
                return (
                  <td key={one.service.id} className="tabular-nums">
                    {point === undefined || point.absent || point.quantity_display === null ? (
                      <Dash />
                    ) : (
                      <>
                        {point.quantity_display}
                        {one.unit === null ? null : ` ${one.unit}`}
                        {point.estimated && (
                          <span className={`ml-1 text-sm ${MUTED}`}>
                            {t("customers.account.usage.estimatedMark")}
                          </span>
                        )}
                      </>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </div>
  );
}

export function PaymentMethodPanel(props: { t: Translator }) {
  const { t } = props;
  return (
    /* ⚠ **THREE FAULTS, ALL READ OFF THE RUNNING PRODUCT BY THE PRODUCT OWNER
       ON 2026-09-13, AND ALL THREE IN THIS ONE BLOCK.**
       They pasted it back: *"Payment method / Payment method / The stored
       payment method and its verification state belong to the payments module.
       Autopay is recorded on the account, and nothing collects on it in this
       version. / Update method"*.

         1 · **THE HEADING WAS PRINTED TWICE.** The `<h3>` said it, and then
             `ArrivesWith` — which renders its OWN `<h3>` from its `title` prop
             — said it again. Nothing could see that: both are real headings in
             the DOM, so `tsc`, every `toContain` and every gate pass over it,
             and only a person reading the screen finds it. Hard-won law 6.
         2 · **IT WAS A BORDERED CARD IN A COLUMN OF FLAT GROUPS.** Every other
             group on this tab is `tone="group"` — the accent rule under an
             uppercase heading the blueprint draws. This one still carried the
             old `plain` panel, so it read as a different KIND of thing.
         3 · **TWENTY-SEVEN WORDS OF RATIONALE, WHICH B14 RULE 33 FORBIDS
             OUTRIGHT** — *"RATIONALE — why the product works this way, why a
             control is absent — is ZERO WORDS ON SCREEN"*. The sentence was
             true; being true is not the test. What it said belongs here:
             **payments stores no method for an account in this version, and
             autopay is an enrolment recorded on the account that nothing
             collects on** (`apps/payments/models.py:623`, *"a promise
             recorded, never a charge"*). `customers.account.arrives.paymentMethod`
             is left in all eleven catalogues rather than deleted — nothing
             else renders it today, and retiring a key is a catalogue-wide
             sweep that belongs to the lane that owns it.

       ⚠ **THE CONTROL STAYS, DISABLED, WITH ITS REASON** (`BR-SHL-025` /
       B14 rule 25): a control a clerk cannot use is shown refusing, never
       hidden, so nobody hunts for a button somebody removed. Its reason is
       re-cut to rule 33's six-word cap. */
    <Panel
      as="section"
      tone="group"
      data-overview-group="payment-method"
      title={t("customers.account.panel.paymentMethod")}
      trailing={
        <GuardedButton
          label={t("customers.account.paymentMethod.update")}
          reason={t("customers.account.paymentMethod.updateBlocked")}
          size="row"
          onClick={() => undefined}
        />
      }
    >
      {/* The drawing's own first row — `On file`, answered. A FACT at rule 33's
          six-word cap, not an explanation of why it is empty. */}
      <FactList>
        <Fact label={t("customers.account.paymentMethod.onFile")}>
          <Dash>{t("customers.account.paymentMethod.noneOnFile")}</Dash>
        </Fact>
      </FactList>
    </Panel>
  );
}

// ── 3.6 / 3.7 · The two tabs with no endpoint — frames, never empty tables ──

// ⚠ **`FrameTable` LEFT THIS FILE ON 2026-09-13 WITH ITS LAST CALLER.** It drew
//    a table's real column HEADINGS over ONE spanning cell carrying a stated
//    absence — the honest shape for a tab whose endpoint did not exist, and
//    deliberately not an empty `<tbody>`, which asserts *"this account was
//    never adjusted"*. Both tabs that used it (Documents, then Adjustments) now
//    list real rows through `DataTable`, so the helper has no caller and is
//    deleted rather than kept warm: a component nothing mounts is dead UI that
//    passes every test in the suite (hard-won law 2).

// ⚠ **`AccountAdjustmentsTab` LEFT THIS FILE ON 2026-09-13 (B14 rule 41) AND IS
//    NOW `./AccountAdjustmentsTab.tsx`.** It was a `FrameTable` here — r10's six
//    column heads over one spanning cell stating that no endpoint listed an
//    adjustment. **That sentence was false by then**: `GET /payments` accepts
//    `f.account_id` AND `f.type`, pages in the database and serves four of the
//    six columns, and nothing had ever called it with `f.type=adjustment`. A
//    real list needs the toolbar, the pagination footer and an empty state,
//    which is `DataTable`, and `FrameTable` above is deliberately none of
//    those — so the frame is GONE rather than edited, exactly as
//    `AccountDocumentsTab`'s was the day before.
//
//    ⚠ **ITS RATIONALE SENTENCE WENT WITH IT, AND THAT IS B14 RULE 33.**
//    `customers.account.arrives.adjustmentsListing` — *"Adjustments show on the
//    Payments tab, marked Adjustment. This table needs two facts nothing keeps
//    yet — the reason and who approved it."* — is RATIONALE, which is ZERO
//    WORDS ON SCREEN. The two facts it named are still missing and each cell
//    now says so in two words; the WHY is in the new file's own header. The key
//    is left in the eleven catalogues rather than deleted, because removing a
//    key is a separate act with its own blast radius.

// ⚠ **`AccountDocumentsTab` LEFT THIS FILE ON 2026-09-12 (`CR-094-BRC01` wave I,
//    `ACC-S8`) AND IS NOW `./AccountDocumentsTab.tsx`.** It was a FRAME here —
//    r10's five column heads over one spanning cell stating that nothing could
//    hold a document — because `BR-CUS-036` had been CONFIRMED since
//    2026-08-08 and nobody had built the table it names. The table, the two
//    endpoints and the upload exist now, so the frame is gone rather than
//    edited: a real list needs the toolbar, the filter, the pagination footer
//    and an empty state, which is `DataTable`, and `FrameTable` above is
//    deliberately none of those.
//
//    ⚠ **AND ITS TWO STRINGS WENT WITH IT, IN THIS COMMIT** —
//    `customers.account.documents.uploadBlocked` (*"Nothing stores a document
//    yet: there is no upload endpoint and no table behind it."*) and
//    `customers.account.arrives.documents`. Both were TRUE when written and are
//    false now, and hard-won law 1 is exactly about the gap between those two
//    sentences: a string that outlives its fact is a comment claiming a
//    guarantee. `AccountAdjustmentsTab` above keeps its frame and its sentence,
//    because an account still cannot be adjusted.

// ── CR-059 CS-37 · P13 — the Credits tab ───────────────────────────────────

// ⚠ **`AccountCreditsTab`, `AccountPlanTab` AND `AccountDepositRowNote` LEFT
//    THIS FILE ON 2026-09-13 (B14 rule 41) AND ARE NOW `./AccountMoneyTabs.tsx`.**
//    The Credits and Payment-plan tabs are drawn as the blueprint's named
//    GROUPS now — ACC-T04 and ACC-T05 — with the column heads always shown
//    and the census hooks the browser check selects on. The deposit-row note
//    is not re-created anywhere: it was RATIONALE, and B14 rule 33 puts that
//    at zero words on screen (PO 2026-09-13). Its reasoning is in the new
//    file's header.
//
//    They MOVED rather than being copied — a component nothing mounts is dead
//    UI that passes every test in the suite (hard-won law 2), and two
//    implementations of one tab is how a screen comes to say two things.

// ── 3.11 · The Audit tab's portal actor ────────────────────────────────────

/**
 * r10's ACC-01 audit table distinguishes `System` from `Sarah Miller (portal)`
 * — a customer acting on their own account through a portal.
 *
 * `audit_log` records WHO acted (`actor`) and nothing about the CHANNEL:
 * `source` is contracted and served null (gap AUD-D2), and there is no portal
 * in this version at all, so no row could carry one. **BR-CUS-028 is the rule
 * and it is CONFIRMED — portal data is not fabricated in v1** — which makes
 * this a stated scope boundary rather than a defect, and it is rendered as one,
 * with the rule id on the element for support and out of the sentence
 * (DEF-332).
 *
 * ⚠ **THE SENTENCE CHANGED ON 2026-09-06 AND THE OLD ONE IS WORTH KNOWING
 * ABOUT (`DEF-CUS-4298`).** It read *"Every entry here was made by a member of
 * staff or by the system."* — true while `audit_log` had exactly two answers, a
 * user id or a NULL meaning *a system job* (BR-AUD-003). `US-AUD-010` added a
 * THIRD: an automation that names itself, which this very table now draws as
 * *"Returned payments, version 4"* (BR-AUD-019). The old sentence was then a
 * claim the screen beneath it contradicted.
 *
 * **Nothing caught it and nothing could have.** The test asserted the sentence
 * was PRESENT, which is not the same question as whether it is TRUE, and no
 * gate in this repository reads rendered output (hard-won law 6). It was found
 * by looking at a screenshot from the browser walkthrough. **The general form
 * is `DEF-CUS-3653`'s: when a value gains a new meaning, grep for the COPY that
 * describes it, not only for the code that reads it.**
 */
/**
 * ⚠ **AND IT HAPPENED AGAIN TO THE HOVER RATHER THAN THE VISIBLE LINE
 * (`DEF-CUS-4998`, 2026-09-12).** The paragraph above records `DEF-CUS-4298`
 * fixing the sentence a reader can SEE. The `title=` attribute below said, as
 * its third sentence, *"There is no customer portal in this version, so no
 * entry can come from a customer"* — and that was false twice over: the portal
 * ships, and `apps/portal/credentials.py` writes `portal_credential.create`
 * with `actor: "portal:self-enrolment"`, so an entry CAN come from a customer
 * and does.
 *
 * It now reads **"Who acted is recorded. The channel is not."** — the two
 * clauses that are true, and nothing in place of the one that was not. The
 * automation clause was dropped rather than reworded: the VISIBLE line this
 * hover hangs off already names the three kinds of actor, and saying it twice
 * is B14 rule 32's description budget.
 *
 * **A hover is the worst place for a false sentence and the reason is
 * mechanical:** every screenshot of this tab shows the visible line and none
 * of them shows this one, so the fix for `DEF-CUS-4298` could not have found
 * it. It was found by grepping the CATALOGUE for the claim rather than the
 * screen for the words.
 */
export function AccountAuditPortalNote(props: { t: Translator }) {
  return (
    <p
      className={`m-0 text-base ${MUTED}`}
      role="note"
      data-rule-ref="BR-CUS-028"
      title={props.t("customers.account.audit.portalActorWhy")}
    >
      {props.t("customers.account.audit.portalActor")}
    </p>
  );
}

// ── 3.10 · Notes as CARDS ──────────────────────────────────────────────────

/**
 * r10 draws each note as a PANEL: the title as the panel heading, `date ·
 * author` right-aligned on the same line, and the body beneath. A pinned note
 * takes the accent top-rule r10 gives the first card.
 *
 * ⚠ **THIS SHIPPED AS A BOTTOM-BORDERED LIST**, which reads as table rows —
 * B18 §5.2.2 calls it *"a real conformance drift"*, and TC-ACD-6 is written
 * against it. The card is the same data in r10's own container; nothing about
 * what a note IS changed.
 */
export function AccountNoteCards(props: {
  notes: readonly AccountNote[];
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** The pin/unpin control for one note, rendered inside its card. */
  renderAction?: (note: AccountNote) => ReactNode;
}) {
  const { t } = props;
  return (
    <div className="flex flex-col gap-3" data-note-cards="">
      {props.notes.map((note) => (
        <Panel
          key={note.id}
          as="section"
          accent={note.pinned}
          className="mb-0"
          data-note-card=""
          data-pinned={note.pinned ? "true" : undefined}
        >
          <div className={PANEL_HEAD}>
            <h3>{note.title ?? <Dash />}</h3>
            <span className={`font-heading text-xs font-semibold ${MUTED}`}>
              {note.created_at !== null && (
                <DateCell
                  value={note.created_at}
                  timeZone={props.timeZone}
                  dateFormat={props.dateFormat}
                />
              )}
              {/* A note with no author is a SYSTEM note (r10's "Autopay
                  enrollment confirmed · System") — the absence is the fact. */}
              <span aria-hidden="true"> · </span>
              {note.author_name ?? t("customers.account.note.systemAuthor")}
            </span>
          </div>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            {note.pinned && (
              <StatusPill tone="warning">{t("customers.account.note.pinnedPill")}</StatusPill>
            )}
            {note.customer_visible && (
              <StatusPill tone="neutral">
                {t("customers.account.note.customerVisiblePill")}
              </StatusPill>
            )}
          </div>
          {note.body !== null && note.body !== "" && (
            <p className="m-0 text-base leading-body">{note.body}</p>
          )}
          {props.renderAction !== undefined && (
            <div className="mt-2 flex justify-end">{props.renderAction(note)}</div>
          )}
        </Panel>
      ))}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-008@6825515 (sha1[:7] of the three sources this lane was authored from, concatenated in order: 04-docs/05-modules/03-customers/06-epics/EP-CUS-03-account-detail.md · 04-docs/05-modules/03-customers/02-business-rules.md · 04-docs/02-decisions/18-cr030-onboarding-design.md §5.2 — the CR-030 W3 packet)
// co-packet: CR-030/B18@2026-08-23 §5.2.2 (S21 · ACC-01) · US-CUS-009/010/011 · US-BIL-025 · US-AST-005 · BR-CUS-023/028/034/035 · W3 tasks 3.4–3.11
// generated: 2026-08-24 by the CR-030 W3 frontend lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest (AccountDetailPage.test.tsx TC-ACD-2/3/5/6/7 + the meters and recent-bills cases) · g31 (registered in styles/route-b-migrated.txt — routeBUtilities.test.ts and the real Tailwind compiler own every utility here) · g37 (no row-action cell — nothing here is a row action) · g38 (every NEW stated absence cites an OPEN row: the usage-trend frame DEF-474, the deposit row DEF-177; the two frame tables carry the sentences this screen already shipped, unmodified and still uncited, because adding an id to an old note LOWERS G38's untracked count and its baseline lives in 10-scripts/, outside this lane — REPORTED) · g14 (every new `.col.` heading is a string r10's own ACC-01 markup draws: Meter # · Service · Type · Install date · Multiplier · Last read · Last read date · Status · Date · Read · Usage · Source · Notes · Adjustment # · Reason · Applied to · Amount · Approved by · Document · Uploaded by · Size · Bill # · Cycle — so the ratchet does not move)
// exceptions: E3 the Meters table reads each meter's registry row through `GET /assets/{id}` (one request per meter, cached by asset id and shared with the header chips): `GET /accounts/{id}` serves only `{id, asset_no, qualifier}` per meter, and BR-CUS-034 forbids a customers-side copy of an assets row · E3 `Last read` / `Last read date` come from the HEAD of `GET /assets/{id}/reads` (served newest-first) because `asset_dict.last_read` is served for SUB-METERS only (DEF-592's scope) — a served answer read, never a derived one · E3 the read log draws one panel PER METER where r10 nests one for the first meter only; with a single meter it is r10 exactly, and choosing one of two would be this screen deciding which meter the clerk meant · E3 r10's read-log `Export` control is NOT drawn: `POST /exports` registers no reads resource (BR-SHL-010 — an undeclared capability is not rendered) · E3 the read log's NOTES column carries the read's STATUS when it is not `ok`: r10's `Partial cycle` is a per-read note the schema has no column for · E3 the Recent bills USAGE cell is a stated absence — an invoice ROW carries money totals and no quantity (the usage is on its lines) · E3 `+ New adjustment` and `+ Upload document` render as SECONDARIES, not r10's primaries: the page header holds the one primary (BR-SHL-044), and both are disabled with their reason because neither has an endpoint · E3 the Adjustments and Documents tabs draw r10's HEADINGS over one spanning absence cell rather than an empty tbody, which would assert "never adjusted" / "nothing filed" · E3 the deposit row r10 draws in the Payments tab is NOT fabricated — DEF-177 (open) is named, and B18 itself calls the shape a modelling claim to confirm · E3 the Audit tab's portal actor is a stated scope boundary carrying BR-CUS-028, not a defect: there is no portal in this version and `audit_log` records no channel (gap AUD-D2)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
