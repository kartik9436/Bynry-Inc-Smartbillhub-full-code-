// ── Trace ──────────────────────────────────────────────
// Change:   CR-038 · ADDITION 2026-08-26 — W5 task 8, the METER half.
// Story:    US-AST-005.  Screens: S50 (Reads tab).
// Rules:    BR-MET-106 (an unread month is ABSENT, never `0`; estimates are
//           counted and MARKED) · BR-MET-135 / BR-AST-029 / BR-RAT-014 (a
//           register that is not consumption is never added to usage) ·
//           CLAUDE.md hard rule 3 (an explicit unit, always)
// Defects:  DEF-798 (684 + 14 = 698 kWh where the truth is 684 kWh)
// ───────────────────────────────────────────────────────
// **THE ASSERTIONS THAT MATTER MOST ARE THE NEGATIVE ONES**, and the first is
// DEF-798's own number: with a 684 kWh energy register and a 14 kW demand
// register on ONE meter, the string `698` must appear nowhere in the markup.
// A screen that blended them would look perfectly reasonable and be wrong by
// exactly the amount the defect measured.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";

import {
  AssetUsageStrip,
  assetUsageKey,
  getAssetUsage,
  usageStripState,
} from "./AssetUsageStrip";
import type {
  AssetUsageMetric,
  AssetUsagePayload,
  AssetUsagePoint,
  AssetUsageSeries,
} from "./AssetUsageStrip";

const TEST_TENANT = "brazosbend";
const ASSET = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function metric(display: string | null, over: Partial<AssetUsageMetric> = {}): AssetUsageMetric {
  return {
    value: display,
    display,
    unit: "kWh",
    absent_reason: display === null ? "no_months_with_reads" : null,
    ...over,
  };
}

function point(month: string, over: Partial<AssetUsagePoint> = {}): AssetUsagePoint {
  return {
    month,
    quantity: "684.000000",
    quantity_display: "684",
    unit: "kWh",
    absent: false,
    read_count: 1,
    estimated_read_count: 0,
    estimated: false,
    ...over,
  };
}

const ABSENT: Partial<AssetUsagePoint> = {
  quantity: null,
  quantity_display: null,
  unit: null,
  absent: true,
  read_count: 0,
};

/** The ENERGY register — what the customer actually used. */
function energy(over: Partial<AssetUsageSeries> = {}): AssetUsageSeries {
  return {
    channel: "total",
    is_consumption: true,
    unit: "kWh",
    unit_absence: null,
    points: [
      point("2026-05", { quantity: "598.000000", quantity_display: "598" }),
      point("2026-06", ABSENT), // NEVER READ
      point("2026-07"), // 684 kWh — DEF-798's own figure
    ],
    months_present: 2,
    months_absent: 1,
    metrics: {
      avg_per_month: metric("641"),
      peak: metric("684", { month: "2026-07" }),
      low: metric("598", { month: "2026-05" }),
      yoy: metric(null, { unit: null, absent_reason: "no_prior_reads" }),
    },
    ...over,
  };
}

/** The DEMAND register on the SAME meter — 14, and it is kW, not kWh. */
function demand(): AssetUsageSeries {
  return {
    channel: "demand",
    is_consumption: false,
    unit: "kWh", // ⚠ the ASSET's UoM, exactly as the product stamps it — see below
    unit_absence: null,
    points: [point("2026-07", { quantity: "14.000000", quantity_display: "14" })],
    months_present: 1,
    months_absent: 0,
    metrics: {
      avg_per_month: metric("14"),
      peak: metric("14", { month: "2026-07" }),
      low: metric("14", { month: "2026-07" }),
      yoy: metric(null, { unit: null, absent_reason: "no_prior_reads" }),
    },
  };
}

function payload(over: Partial<AssetUsagePayload> = {}): AssetUsagePayload {
  return {
    asset_id: ASSET,
    asset_no: "M-4412",
    window: { months: 12, from: "2025-08", to: "2026-07", options: [12, 24] },
    series: [energy(), demand()],
    rule_ref: "BR-MET-106",
    source: "computed_from_reads",
    stored_source_absent: { reason: "monthly_usage_has_no_asset_grain", tracks: "OQ-421" },
    ...over,
  };
}

async function renderStrip(body: AssetUsagePayload | "unreadable"): Promise<string> {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      body === "unreadable"
        ? new Response(JSON.stringify({ detail: "boom" }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          })
        : new Response(JSON.stringify(body), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  try {
    await queryClient.prefetchQuery({
      queryKey: assetUsageKey(ASSET, 12),
      queryFn: () => getAssetUsage(ASSET, 12, client),
    });
  } catch {
    // An unreadable payload is one of the cases under test.
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <AssetUsageStrip assetId={ASSET} client={client} t={t} />
    </QueryClientProvider>,
  );
}

describe("CR-038 W5 T8 — S50 trailing-12-month strip (BR-MET-106 · DEF-798)", () => {
  it("DEF-798: a demand peak-delta is drawn SEPARATELY and never blended into usage", async () => {
    const html = await renderStrip(payload());

    // ⚠ **THE FIRST TWO ASSERTIONS OF THIS CASE CHANGED SHAPE ON 2026-09-12
    // (`DEF-MET-4970`), AND THE OLD ONES ARE WRITTEN OUT HERE RATHER THAN
    // DELETED.** They were:
    //
    //     expect(html).toContain(chartTitle({ channel: "total", … }));
    //     expect(html).toContain(chartTitle({ channel: "demand", … }));
    //
    // …i.e. *both registers draw a full chart panel, at the same time*. That
    // is what put the read log 2.6 screens below the fold on a five-register
    // meter, so the layout moved: every register is a `Disclosure` row, the
    // first open and the rest closed.
    //
    // **What DEF-798 actually asserts is untouched, and one half of it got
    // stronger.** The law is *a register that is not consumption is never
    // added to usage, and is drawn and labelled rather than hidden*. Both
    // registers are still NAMED on arrival, each still carries its OWN unit
    // (hard rule 3), the demand row still says *not consumption* — and it now
    // says it with the row CLOSED, which the old layout never had to prove.
    // `698` is still unprintable by any route, and there is still no
    // "meter total" tile and no code path that could build one.
    expect(html).toContain("Total register");
    expect(html).toContain("Demand");
    expect(html).toContain("kWh");

    // ⚠ THE NEGATIVE ASSERTION THIS WHOLE FILE EXISTS FOR. 684 + 14 = 698 is
    // the number DEF-798 measured on the account tab. It must not be printable
    // from this screen by any route.
    expect(html).not.toContain("698");
    expect(html).toContain("684");
    expect(html).toContain("14");

    // And the demand register SAYS it is not usage, so no reader adds it by eye.
    expect(html).toContain(t("assets.usage.notConsumption"));
    expect(html).toContain('data-consumption="false"');
  });

  it("BR-MET-106: an unread month draws NO bar and is never printed as 0", async () => {
    const html = await renderStrip(payload());
    expect(html).toContain('data-month="2026-06" data-absent="true"');
    expect(html).toContain(t("assets.usage.absentMonths", { absent: 1, total: 3 }));
    // "zero usage and no read are different claims about a customer."
    expect(html).not.toContain('data-month="2026-06" data-absent="false"');
  });

  it("BR-MET-106: a month including an estimate is MARKED, not silently equal", async () => {
    const estimated = energy({
      points: [point("2026-07", { estimated: true, estimated_read_count: 1 })],
      months_present: 1,
      months_absent: 0,
    });
    const html = await renderStrip(payload({ series: [estimated] }));
    expect(html).toContain('data-estimated="true"');
    expect(html).toContain(t("assets.usage.estimatedMonths", { months: 1 }));
  });

  it("hard-won law 1: the screen SAYS these figures are computed, not the stored row", async () => {
    const html = await renderStrip(payload());
    // Asserted as a FRAGMENT, not the whole string: React escapes the
    // apostrophe in "meter's" to `&#x27;`, so a whole-sentence toContain over
    // the catalogue value can never match rendered markup.
    expect(html).toContain("Figures are calculated from this meter");
    // The question that would close the gap travels with the claim.
    expect(html).toContain('data-tracks="OQ-421"');
  });

  it("a meter with no readings says so plainly — not an ArrivesWith, nothing is missing", async () => {
    const html = await renderStrip(payload({ series: [] }));
    expect(html).toContain(t("assets.usage.empty"));
    expect(html).not.toContain(t("assets.usage.notConsumption"));
  });

  it("a broken endpoint draws NEITHER the empty state nor a chart", async () => {
    // ⚠ **THE FAILURE FRAME CANNOT BE REACHED THROUGH `renderToStaticMarkup`,
    // AND `AccountUsageTab` RECORDS THE SAME MEASUREMENT ONE FOLDER OVER.**
    // On react-query 5 in this repo a query whose cached state is `error`
    // reports `pending / fetching` to a SERVER render — the server snapshot
    // ignores a cached error and starts the query optimistically. So this tier
    // renders the LOADING frame for a broken endpoint.
    //
    // What CAN be asserted here is the thing that would actually hurt a user:
    // a failed read must never be dressed as "this meter has no readings", and
    // it must never draw a chart over data it does not have. The FRAME CHOICE
    // itself is proved by the pure `usageStripState` test below, which is why
    // that function was pulled out of the component at all.
    const html = await renderStrip("unreadable");
    expect(html).not.toContain(t("assets.usage.empty"));
    expect(html).not.toContain('data-absent="false"');
  });

  // ══════════════════════════════════════════════════════════════════════
  // CR-092-BRC01 lane 2 — `DEF-MET-4969` (the words) and `DEF-MET-4970`
  // (the height). Both proved RED against `ce623f444` first.
  // ══════════════════════════════════════════════════════════════════════

  it("DEF-MET-4969: a register is named in WORDS — the served code never reaches a clerk", async () => {
    const html = await renderStrip(payload());
    expect(html).toContain("Total register");
    expect(html).toContain("Demand");
    // ⚠ The codes. `total` is a substring of nothing else here and `demand`
    // appears only as the code, so both are safe negatives.
    expect(html).not.toContain(">total<");
    expect(html).not.toContain("total ·");
    expect(html).not.toContain("demand ·");
    expect(html).not.toContain("demand register,");
  });

  it("DEF-MET-4970: two registers draw ONE open panel, and the second still states its figure", async () => {
    const html = await renderStrip(payload());

    // The first register is OPEN: its chart, its axis and its tiles are drawn.
    // Its name and unit are on the row header, not repeated as a chart title —
    // the same fact twice on one screen is what `AST-R-09` forbids.
    expect(html).toContain('aria-expanded="true"');
    expect(html).toContain("Total register");
    expect(html).toContain('data-month="2026-07"');
    expect(html).toContain(t("assets.usage.axis", { from: "2026-05", to: "2026-07" }));
    expect(html).toContain(t("assets.usage.kpi.avg"));

    // ⚠ **THE SECOND IS COLLAPSED AND ITS NUMBER IS STILL ON SCREEN.** That is
    // `Disclosure`'s own law — *"collapsing never hides a number"* — and it is
    // what keeps `DEF-798` true through this change: the demand register is
    // still NAMED, still carries its own unit, still says it is not usage, and
    // 684 + 14 is still unprintable.
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain("Demand");
    expect(html).toContain("14"); // its average, on the closed row
    expect(html).toContain(t("assets.usage.notConsumption"));
    expect(html).toContain('data-consumption="false"');
    expect(html).not.toContain("698");

    // …and the collapsed register's CHART is genuinely not rendered, so the
    // read log below is not pushed down by it. `2026-07` is the demand
    // register's only month and the energy one's last, so the count is what
    // decides: one chart's worth of bars, not two.
    expect(html.split('data-month="2026-07"').length - 1).toBe(1);
  });

  it("DEF-MET-4970: ONE register draws the plain panel — no toggle over a list of one", async () => {
    const html = await renderStrip(payload({ series: [energy()] }));
    expect(html).toContain(
      t("assets.usage.chartTitle", { channel: "Total register", months: 12, unit: "kWh" }),
    );
    expect(html).not.toContain("aria-expanded");
  });

  it("usageStripState checks isError BEFORE isPending, so a retrying failure is not 'loading'", () => {
    // A query that has errored and is retrying is BOTH errored and fetching.
    expect(usageStripState({ isPending: true, isError: true, data: undefined })).toBe("failed");
    expect(usageStripState({ isPending: true, isError: false, data: undefined })).toBe("loading");
    expect(usageStripState({ isPending: false, isError: false, data: {} })).toBe("ready");
  });
});
