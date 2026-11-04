// ── Trace ──────────────────────────────────────────────
// Change:   B14 rule 41 (PO 2026-09-13) — `ACC-T07` and `ACC-T07R`'s FRONTEND
//           cases.
// Rules:    BR-AST-044 (meter type and read method are SEPARATE) ·
//           BR-AST-031 (the tenant's own lifecycle name) · BR-MET-051 (a
//           demand row is not an energy row) · BR-SHL-011 (the read log is
//           addressable) · B14 rule 15 (row actions are icons) · rule 16 (the
//           pagination footer) · rule 31 (no database id on screen).
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY CASE HERE IS PRESENCE AND ORDER, AND THAT IS THE CEILING.** jsdom
// computes no layout, so none of this can say the screen LOOKS like the
// drawing; `10-scripts/render-checks/acc02-tab-conformance.mjs` is the
// instrument for that and a person reading its screenshot is the check behind
// it (hard-won law 6). What these cases hold is the part a source reader CAN
// own: the drawn columns exist, in the drawn order, and each cell states an
// absence rather than going blank.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { AssetDetail, AssetReadRow } from "@/api/endpoints";

import {
  AccountMetersTab,
  MeterReadLogPanel,
  compareMeters,
  isInstalled,
  meterFilterOptions,
  meterMatches,
  meterMatchesFilter,
  metersTableConfig,
} from "./AccountMetersTab";
import type { AccountMeterView } from "./accountDetailTabs";

const TEST_TENANT = "brazosbend";
const ACCOUNT = "3f1a9c2e-0000-7000-8000-000000000001";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function asset(overrides: Partial<AssetDetail> = {}): AssetDetail {
  return {
    id: "0198f3c2-0000-7000-8000-00000000aaaa",
    asset_no: "E-4417",
    serial_no: "SN-88120",
    type: "meter",
    type_name: "Meter",
    tab: "meters",
    status: "installed",
    status_name: "Installed",
    behavior_class: "in_service",
    // ⚠ **THE TWO THAT WERE ONE CELL.** `BR-AST-044` classification 2 is what
    // the meter IS; classification 3 is how the reading is COLLECTED. The
    // blueprint's own example is an AMR meter still read on foot.
    meter_type: "amr",
    meter_type_name: "AMR",
    read_method: "walk_by",
    read_method_name: "Walk-by",
    multiplier: "1.000000",
    size_class: null,
    unit: "kWh",
    net_metering: false,
    manufacturer: "Itron",
    model: "OpenWay CENTRON",
    install_date: "2024-09-10",
    parent_asset_no: null,
    service_point_id: null,
    assigned_unit_id: null,
    assigned_to: null,
    assigned_address: "142 Bakers Row · Suite 1",
    assigned: true,
    test_due: false,
    retire_date: null,
    retire_reason: null,
    replaced_by: null,
    actions: [],
    service: "electric",
    ...overrides,
  } as unknown as AssetDetail;
}

function read(overrides: Partial<AssetReadRow> = {}): AssetReadRow {
  return {
    read_id: "0198f3c2-0000-7000-8000-00000000bbbb",
    date: "2026-08-18T00:00:00Z",
    channel: "total",
    read_type: "actual",
    reading: "61480.000000",
    consumption: "5510.000000",
    unit: "kWh",
    export: null,
    export_unit: null,
    export_read_id: null,
    source: "walk_by",
    status: "ok",
    ...overrides,
  } as unknown as AssetReadRow;
}

function view(overrides: Partial<AccountMeterView> = {}): AccountMeterView {
  return {
    meter: { id: "0198f3c2-0000-7000-8000-00000000aaaa", asset_no: "E-4417", qualifier: null },
    asset: asset(),
    assetFailed: false,
    reads: [read()],
    readsFailed: false,
    loading: false,
    ...overrides,
  } as AccountMeterView;
}

const CONFIG = metersTableConfig(t, [view()], {
  meterNo: () => <span />,
  installed: () => <span />,
  readOn: () => <span />,
  actions: () => <span />,
});

function renderTab(views: AccountMeterView[], openMeterId: string | null = null): string {
  return renderToStaticMarkup(
    // ⚠ **MOUNTED UNDER THE REAL PATH PATTERN.** A bare `MemoryRouter` with no
    // `/:tenant/...` route leaves `useParams().tenant` undefined, so the asset
    // links come out `//assets/…` — a protocol-relative address to another
    // host that reads as a perfectly good string to `toContain`.
    <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts/${ACCOUNT}?tab=meters`]}>
      <AccountMetersTab
        views={views}
        t={t}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        openMeterId={openMeterId}
        onOpenMeter={() => undefined}
      />
    </MemoryRouter>,
  );
}

describe("ACC-T07 · the Meters tab", () => {
  it("draws the TEN drawn columns, in the drawn order", () => {
    // ⚠ **IT DREW EIGHT, AND TWO OF THE MISSING ONES WERE SERVED ALL ALONG.**
    // `meter_type_name` and `read_method_name` were composed into one cell
    // with the manufacturer, so neither could be scanned down or filtered, and
    // `ACTIONS` was not there at all.
    expect(CONFIG.columns.map((column) => column.key)).toEqual([
      "meterNo",
      "service",
      "meterType",
      "readMethod",
      "installed",
      "multiplier",
      "lastRead",
      "readOn",
      "status",
      "actions",
    ]);
    expect(CONFIG.columns.map((column) => column.label)).toEqual([
      t("customers.account.meters.col.meterNo"),
      t("customers.account.meters.col.service"),
      t("customers.account.meters.col.meterType"),
      t("customers.account.meters.col.readMethod"),
      t("customers.account.meters.col.installed"),
      t("customers.account.meters.col.multiplier"),
      t("customers.account.meters.col.lastRead"),
      t("customers.account.meters.col.readOn"),
      t("customers.account.meters.col.status"),
      t("customers.account.meters.col.actions"),
    ]);
  });

  it("BR-AST-044 — METER TYPE and READ METHOD are two cells and say two different things", () => {
    const html = renderTab([view()]);
    // The blueprint's worked example, in one row: an AMR meter read on foot.
    expect(html).toContain(">AMR<");
    expect(html).toContain(">Walk-by<");
    // …and the manufacturer is NOT folded into either of them, which is what
    // made the old single cell unscannable.
    expect(html).not.toContain("AMR · Itron");
  });

  it("the filter chips are DERIVED from the rows, never a typed list of services", () => {
    // Hard-won law 2: the service list typed by hand in two places is why an
    // eleventh service never appeared on screen and failed silently.
    const options = meterFilterOptions(
      [view(), view({ asset: asset({ service: "water", asset_no: "W-4417" }) })],
      t,
    );
    expect(options.map((option) => option.value)).toEqual([
      "electric",
      "water",
      "installed",
      "removed",
    ]);
    // A unit with a gas meter gets a Gas chip without this file changing.
    const gas = meterFilterOptions([view({ asset: asset({ service: "gas" }) })], t);
    expect(gas.map((option) => option.value)).toEqual(["gas", "installed", "removed"]);
  });

  it("`Installed` and `Removed` read the tenant's BEHAVIOUR CLASS, not a status word", () => {
    // `BR-AST-031` — the lifecycle stage is REFERENCE DATA a tenant names, so
    // nothing here may match on the word `Installed`. The behaviour class is
    // the stable half.
    const removed = view({ asset: asset({ status_name: "Taken out", behavior_class: "terminal" }) });
    expect(isInstalled(view())).toBe(true);
    expect(isInstalled(removed)).toBe(false);
    expect(meterMatchesFilter(view(), "installed")).toBe(true);
    expect(meterMatchesFilter(removed, "installed")).toBe(false);
    expect(meterMatchesFilter(removed, "removed")).toBe(true);
    expect(meterMatchesFilter(removed, "electric")).toBe(true);
    // `All` is the no-filter state the shared bar gives, so "" matches all.
    expect(meterMatchesFilter(removed, "")).toBe(true);
  });

  it("the search matches the meter NUMBER and the SERIAL, as the drawing says", () => {
    expect(meterMatches(view(), "4417")).toBe(true);
    expect(meterMatches(view(), "sn-88")).toBe(true);
    expect(meterMatches(view(), "W-2288")).toBe(false);
    expect(meterMatches(view(), "")).toBe(true);
  });

  it("`Sort: Meter # ▼` is numeric-aware, so M-999 comes before M-4021", () => {
    // ⚠ **A METER NUMBER IS NOT A NUMBER.** Under a plain string compare
    // `M-4021` sorts before `M-999`, which a person reads as a broken list.
    const sorted = [
      view({ meter: { id: "a", asset_no: "M-4021", qualifier: null } }),
      view({ meter: { id: "b", asset_no: "M-999", qualifier: null } }),
    ].sort(compareMeters);
    expect(sorted.map((one) => one.meter.asset_no)).toEqual(["M-999", "M-4021"]);
  });

  it("B14 rule 16 — the toolbar and the pagination footer are the shared table's", () => {
    const html = renderTab([view()]);
    expect(html).toContain(t("customers.account.meters.search"));
    expect(html).toContain("table-pager");
    // B14 rule 15 — a row action is an ICON with a tooltip, never a text link.
    expect(html).toContain(`aria-label="${t("customers.account.meters.readLog")}"`);
  });

  it("B14 rule 31 — the meter NUMBER is the visible value and the uuid is not", () => {
    const html = renderTab([view()]);
    expect(html).toContain("E-4417");
    expect(html).not.toContain(">0198f3c2-0000-7000-8000-00000000aaaa<");
    // The asset link is built under the real tenant, not `//assets/…`.
    expect(html).toContain(`/${TEST_TENANT}/assets/0198f3c2-0000-7000-8000-00000000aaaa`);
  });

  it("a meter whose registry did not answer STATES it rather than drawing blanks", () => {
    const html = renderTab([view({ asset: null, assetFailed: true, reads: null })]);
    expect(html).toContain("E-4417");
    expect(html).toContain(t("customers.account.meters.registryAbsentWhy"));
    expect(html).toContain(t("customers.account.meters.noReadsWhy"));
  });

  it("the census hook is on the drawn section, because no vitest case can see layout", () => {
    const html = renderTab([view()]);
    expect(html).toContain("data-account-overview");
    expect(html).toContain('data-overview-group="meters"');
  });
});

describe("ACC-T07R · the read log, opened over the tab", () => {
  it("opens only for the meter `?meter=` names, and is not drawn otherwise", () => {
    expect(renderTab([view()])).not.toContain("data-meter-read-log");
    const open = renderTab([view()], "0198f3c2-0000-7000-8000-00000000aaaa");
    expect(open).toContain("data-meter-read-log");
    expect(open).toContain(t("customers.account.readLog.title", { meter: "E-4417" }));
  });

  it("draws `THE METER`'s seven facts and the reads-held line", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts/${ACCOUNT}?tab=meters`]}>
        <MeterReadLogPanel
          view={view({ reads: [read(), read({ read_id: "c2", date: "2026-07-17T00:00:00Z" })] })}
          t={t}
          timeZone="America/Chicago"
          dateFormat="MM/DD/YYYY"
          onClose={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(html).toContain(t("customers.account.readLog.theMeter"));
    for (const field of ["meter", "service", "meterType", "readMethod", "installed", "multiplier", "status"]) {
      expect(html).toContain(t(`customers.account.readLog.field.${field}`));
    }
    // The drawing's own line — *Reads held 24, newest first*.
    expect(html).toContain(t("customers.account.readLog.readsHeld", { count: 2 }));
  });

  it("draws `THE READS`' seven columns, CHANNEL and EXPORT included", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts/${ACCOUNT}?tab=meters`]}>
        <MeterReadLogPanel
          view={view()}
          t={t}
          timeZone="America/Chicago"
          dateFormat="MM/DD/YYYY"
          onClose={() => undefined}
        />
      </MemoryRouter>,
    );
    for (const column of ["date", "channel", "reading", "usage", "export", "collected", "status"]) {
      expect(html).toContain(t(`customers.account.readLog.col.${column}`));
    }
    // ⚠ **EXPORT IS A DASH AND NOT A ZERO**, and the blueprint says why: the
    // column fills where a meter exports, and a zero would read as *"it
    // exported nothing"* about a meter that only imports.
    expect(html).not.toContain(">0 kWh<");
    expect(html).toContain("—");
    // Reads are taken and corrected in Reads, never here — a FACT, six words.
    expect(html).toContain(t("customers.account.readLog.correctedIn"));
  });

  it("BR-MET-051 — a DEMAND row's usage is stated, not printed as a quantity", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts/${ACCOUNT}?tab=meters`]}>
        <MeterReadLogPanel
          // ⚠ **`demand` EXACTLY — the channel vocabulary is metering's.**
          // The first draft of this case wrote `peak_demand`, which
          // `isPeakChannel` does not match, so it asserted the peak branch
          // over a row that never took it: a case named after a claim it does
          // not make (law 7). `READ_CHANNEL_DEMAND` is the one value.
          view={view({ reads: [read({ channel: "demand", unit: "kW" })] })}
          t={t}
          timeZone="America/Chicago"
          dateFormat="MM/DD/YYYY"
          onClose={() => undefined}
        />
      </MemoryRouter>,
    );
    // On a demand channel `consumption` is a delta between two maxima that
    // nothing bills, so printing it under a heading that reads as energy is a
    // wrong number rather than a missing one. kW is not kWh.
    expect(html).toContain(t("customers.account.readLog.peakNoUsage"));
    expect(html).not.toContain("5,510 kW");
  });
});
