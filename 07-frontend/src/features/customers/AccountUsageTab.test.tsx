// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W3 task 3.8 — the ACC-01 Usage tab.
// Story:    US-CUS-011.  Screens: S21 (Usage tab).
// Rules:    BR-MET-106 (an unread month is ABSENT, never `0`; estimates are
//           counted and MARKED; the figure carries its unit) · CLAUDE.md hard
//           rule 3 (kWh and kgal are never added together) · BR-SHL-010 (an
//           undeclared capability is not rendered — `Compare to neighbors →`)
// ───────────────────────────────────────────────────────
// The assertions that matter most here are the NEGATIVE ones:
//   * an unread month must NOT produce a bar and must NOT print `0`;
//   * `Compare to neighbors` must NOT appear anywhere in the markup;
//   * kWh and kgal must NOT be summed into one figure.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";

import {
  AccountUsageTab,
  accountUsageKey,
  axisLabels,
  axisTop,
  getAccountUsage,
  labelStep,
  monthOnMonth,
  usageViewState,
} from "./AccountUsageTab";
import type { UsageMetric, UsagePayload, UsagePoint, UsageSeries } from "./AccountUsageTab";

const TEST_TENANT = "brazosbend";
const ACCOUNT = "11111111-2222-3333-4444-555555555555";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function metric(display: string | null, over: Partial<UsageMetric> = {}): UsageMetric {
  return {
    value: display,
    display,
    unit: "kWh",
    absent_reason: display === null ? "no_months_with_reads" : null,
    ...over,
  };
}

function point(month: string, over: Partial<UsagePoint> = {}): UsagePoint {
  return {
    month,
    quantity: "628.000000",
    quantity_display: "628",
    unit: "kWh",
    absent: false,
    read_count: 1,
    estimated_read_count: 0,
    estimated: false,
    computed_at: "2026-08-24T10:00:00Z",
    ...over,
  };
}

const ABSENT: Partial<UsagePoint> = {
  quantity: null,
  quantity_display: null,
  unit: null,
  absent: true,
  read_count: 0,
  computed_at: null,
};

/** r10's own strip: 628 avg · 842 peak Jul 2026 · 412 low Feb 2026 · 3.42 kgal. */
function electric(over: Partial<UsageSeries> = {}): UsageSeries {
  return {
    service: { id: "svc-e", code: "electric", name: "Electric" },
    unit: "kWh",
    unit_absence: null,
    points: [
      point("2026-05", { quantity: "598.000000", quantity_display: "598" }),
      point("2026-06", ABSENT), // NEVER READ
      point("2026-07", { quantity: "842.000000", quantity_display: "842" }),
      point("2026-08", {
        quantity: "628.000000",
        quantity_display: "628",
        estimated: true,
        estimated_read_count: 1,
      }),
    ],
    months_present: 3,
    months_absent: 1,
    metrics: {
      avg_per_month: metric("628"),
      peak: metric("842", { month: "2026-07" }),
      low: metric("412", { month: "2026-02" }),
      yoy: metric("+8.28", { unit: null }),
    },
    ...over,
  };
}

function water(): UsageSeries {
  return {
    service: { id: "svc-w", code: "water", name: "Water" },
    unit: "kgal",
    unit_absence: null,
    points: [point("2026-07", { quantity: "3.420000", quantity_display: "3.42", unit: "kgal" })],
    months_present: 1,
    months_absent: 0,
    metrics: {
      avg_per_month: metric("3.42", { unit: "kgal" }),
      peak: metric("3.42", { unit: "kgal", month: "2026-07" }),
      low: metric("3.42", { unit: "kgal", month: "2026-07" }),
      yoy: metric(null, { unit: null, absent_reason: "no_prior_reads" }),
    },
  };
}

function payload(over: Partial<UsagePayload> = {}): UsagePayload {
  const series = over.series ?? [electric(), water()];
  return {
    account_id: ACCOUNT,
    window: { months: 24, from: "2024-09", to: "2026-08", options: [12, 24] },
    services: series.map((s) => s.service),
    series,
    water_avg: metric("3.42", { unit: "kgal", service_code: "water" }),
    rule_ref: "BR-MET-106",
    ...over,
  };
}

/**
 * Renders the real component with the payload PREFETCHED under its own query
 * key. `renderToStaticMarkup` never resolves a promise, so a query not already
 * in the cache renders the loading state — which is one of the cases below.
 */
async function renderTab(
  body: UsagePayload | "unreadable" | "nothing-prefetched",
): Promise<string> {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      body === "unreadable" || body === "nothing-prefetched"
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
  if (body !== "nothing-prefetched") {
    try {
      await queryClient.prefetchQuery({
        queryKey: accountUsageKey(ACCOUNT, 24),
        queryFn: () => getAccountUsage(ACCOUNT, 24, client),
      });
    } catch {
      // An unreadable payload is one of the cases under test.
    }
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <AccountUsageTab accountId={ACCOUNT} client={client} t={t} />
    </QueryClientProvider>,
  );
}

describe("CR-030 W3 T3.8 — S21 Usage tab (BR-MET-106)", () => {
  it("draws ACC-T06's chart header, the picker vocabulary and the four drawn read-outs", async () => {
    const html = await renderTab(payload());
    // ⚠ **AMENDED 2026-09-13 (B14 rule 41).** The header was r10's
    // `Electric usage · 24 months (kWh)`. `ACC-T06` heads the chart
    // `Electric · Sep 2025 — Aug 2026` — the service and the WINDOW ITSELF,
    // because the window is the fact a reader needs to place the bars and
    // `24 months` makes them work it out. The unit moved to its own line
    // against the value axis, where the drawing puts it (`kWh a month`), so
    // hard rule 3 is still satisfied on screen.
    expect(html).toContain(
      t("customers.account.usage.chartRange", {
        service: "Electric",
        from: "May 2026",
        to: "Aug 2026",
      }),
    );
    expect(html).toContain(t("customers.account.usage.axisUnit", { unit: "kWh" }));
    // ⚠ THE PICKER'S OPTIONS ARE THE ACCOUNT'S OWN SERVICES, plus `All` —
    // read from the payload, never a list typed in the component (law 2).
    expect(html).toContain(">Electric</option>");
    expect(html).toContain('<option value="water">Water</option>');
    expect(html).toContain(t("customers.account.usage.segment.all"));
    // …and it OPENS on the first service, so the tab draws ONE trend
    // (PO 2026-09-07). The second chart is an option, not a scroll.
    expect(html).not.toContain(">Water · ");
    // ⚠ **FOUR READ-OUTS, AND EACH HAS ITS OWN SECOND LINE** (`ACC-T06`:
    // `Highest · 6,820 kWh · Dec 25`). They used to fold the month INTO the
    // value — *"842 kWh in 2026-07"* — which is a sentence where the drawing
    // has a figure and its context, and which printed `2026-07` at a clerk.
    expect(html).toContain(t("customers.account.usage.kpi.avg"));
    expect(html).toContain("628 kWh");
    expect(html).toContain(t("customers.account.usage.kpi.perMonth"));
    expect(html).toContain(t("customers.account.usage.kpi.peak"));
    expect(html).toContain("842 kWh");
    expect(html).toContain("Jul 2026");
    expect(html).toContain(t("customers.account.usage.kpi.low"));
    expect(html).toContain("412 kWh");
    expect(html).toContain("Feb 2026");
    expect(html).not.toContain("2026-07<");
    // ⚠ **THE FOURTH IS *THIS MONTH AGAINST LAST*, NOT THE SERVED `yoy`.**
    // `ACC-T06` compares the two newest months and prints both operands under
    // the percentage. `metrics.yoy` compares this YEAR with the prior year and
    // is still served; it is simply not what this read-out is.
    expect(html).toContain(t("customers.account.usage.kpi.monthOnMonth"));
    expect(html).not.toContain(t("customers.account.usage.kpi.yoy"));
    // ⚠ **AND THE FIFTH FIGURE IS NOT HERE, BECAUSE IT IS ABOUT WATER**
    // (`DEF-CUS-4626`). It read *"Average water month · 15 kgal"* beside four
    // electric figures on the PO's own screen. It is `payload.water_avg`, a
    // top-level field outside every series, so it could never follow the
    // picker — it is shown only when its own service is.
    expect(html).not.toContain(t("customers.account.usage.kpi.waterAvg"));
    // ⚠ **SCOPED TO THE READ-OUT ROW, AND IT HAD TO BE NARROWED ON 2026-09-13.**
    // This read `not.toContain("3.42 kgal")` over the WHOLE render, which was
    // true only while the tab drew nothing but a chart. `ACC-T06`'s
    // `Month by month` table lists every service, so water's own figures are
    // now on the page legitimately — in a column headed `Water`, which is not
    // the same claim as an unlabelled water average beside four electric ones.
    // A whole-document assertion for a thing that belongs in one region is how
    // a true check becomes a false one (law 7).
    const readouts = html.slice(html.indexOf('data-testid="usage-readouts"'));
    expect(readouts.slice(0, readouts.indexOf("</div></div>"))).not.toContain("3.42 kgal");
    // ⚠ **AND THE BASIS LINE IS GONE FROM THIS TAB.** It read *"Across the
    // last 12 months"* under the row because the chart title said only
    // `24 months`; the title names the window itself now, so the line restated
    // it — one sentence per section (B14 rule 32). The prop stays for the
    // Overview's own trend group, which composes this row under a table.
    expect(html).not.toContain(t("customers.account.usage.kpi.basis.last12Plain"));
  });

  it("ACC-T06: the value axis is drawn, rounded UP to a round number", () => {
    // ⚠ **DRAWN AND NEVER BUILT.** `ACC-T06` rules the chart `0 · 2,000 ·
    // 4,000 · 6,000 · 8,000` over a peak of 6,820 — five labels, and a top
    // that is the next round step ABOVE the tallest bar rather than the bar
    // itself. A scale whose top IS the tallest bar leaves the reader no
    // headroom to judge it by.
    expect(axisTop(6820)).toBe(8000);
    expect(axisLabels(axisTop(6820))).toEqual([8000, 6000, 4000, 2000, 0]);
    // The drawing's own figures are the check; these are the neighbours.
    expect(axisTop(842)).toBe(1000);
    expect(axisTop(0)).toBe(0);
    // An axis with no bars states one label rather than dividing by zero.
    expect(axisLabels(0)).toEqual([0]);
  });

  it("ACC-T06: 24 months are labelled every second bar, 12 every bar", () => {
    // ⚠ **MEASURED IN A BROWSER, NOT REASONED ABOUT (hard-won law 6).** One
    // slot is one bar wide, and at 24 months `Oct 2024` does not fit one —
    // the first build of this axis rendered `Oct 2… Dec … Feb 2…` across the
    // whole row. Thinning keeps every drawn label INTACT and drops some;
    // truncating keeps all of them and makes none legible.
    expect(labelStep(12)).toBe(1);
    expect(labelStep(24)).toBe(2);
    expect(labelStep(36)).toBe(3);
    expect(labelStep(0)).toBe(1);
  });

  it("ACC-T06: Vs last month is the two newest months, and refuses rather than inventing", () => {
    const series = electric();
    const change = monthOnMonth(series);
    // The newest two PRESENT months of the fixture, and both operands travel
    // with the percentage so the arithmetic is checkable on the row.
    expect(change).not.toBeNull();
    expect(change?.now).toBe("628");
    expect(change?.before).toBe("842");
    expect(change?.percent).toBe("-25.42%");
    // ⚠ **A SERIES WITH ONE PRESENT MONTH ANSWERS NOTHING, NEVER 0%.** A
    // percentage against nothing is the invented number this screen is
    // written against.
    const single = { ...series, points: series.points.slice(0, 1) };
    expect(monthOnMonth(single)).toBeNull();
    expect(monthOnMonth(undefined)).toBeNull();
  });

  it("ACC-T06: Month by month lists a row per service per month", async () => {
    const html = await renderTab(payload());
    expect(html).toContain(t("customers.account.usage.months.title"));
    // A row per SERVICE per month, the service read off the payload (law 2).
    // Every cell is asserted in `AccountUsageMonths.dom.test.tsx` (PO
    // 2026-10-15); this static tier keeps the negative cases.
    expect(html).toContain('data-usage-month="2026-07"');
    expect(html).toContain(t("customers.account.usage.col.readOn"));
    expect(html).toContain(t("customers.account.usage.col.source"));
    expect(html).toContain(t("customers.account.usage.col.check"));
    expect(html).not.toContain("Not recorded");
    // `BR-MET-106` — an unread month is ABSENT in the table too, never a zero.
    expect(html).toContain(t("customers.account.usage.notRead"));
    expect(html).not.toContain(">0 kWh<");
  });

  it("PO 2026-09-07: the read-outs are body text, not KPI tiles", async () => {
    // ⚠ **THE COMPONENT IS THE ASSERTION.** PO verbatim: *"I dont think KPi
    // component is the right component for this"* — these figures describe
    // the chart above them and change with the picker, so they must not be
    // drawn at `--text-metric` (26px, twice body). `KPIStrip` renders
    // `.kpi-grid`; this row must not.
    const html = await renderTab(payload());
    expect(html).toContain('data-testid="usage-readouts"');
    expect(html).not.toContain("kpi-grid");
    // NEGATIVE: no other screen changed — the shared component and its token
    // are untouched, which is the whole reason this was solved here.
  });

  it("an account with ONE service is not asked to choose", async () => {
    const html = await renderTab(payload({ series: [electric()] }));
    expect(html).not.toContain('id="usage-service"');
    expect(html).toContain(
      t("customers.account.usage.chartRange", {
        service: "Electric",
        from: "May 2026",
        to: "Aug 2026",
      }),
    );
  });

  it("BR-MET-106: an unread month draws NO bar and is stated, never rendered as 0", async () => {
    const html = await renderTab(payload({ series: [electric()] }));
    // The absent slot exists and says what it is…
    expect(html).toContain('data-month="2026-06"');
    expect(html).toContain('data-absent="true"');
    expect(html).toContain(t("customers.account.usage.absentMonth", { month: "2026-06" }));
    // …and the chart says how many months are missing.
    // ⚠ THE NAME IS `months`. This assertion passed for weeks with `absent`
    // and `total` — names no catalogue interpolates — because BOTH sides of
    // the comparison go through the same call, so it rendered the raw
    // `{{months}} month(s) have no reading` and matched it against itself
    // (`DEF-CUS-4622`). A `t()` on both sides of a `toContain` can only ever
    // prove the code agrees with itself, which is why the literal is here too.
    expect(html).toContain(t("customers.account.usage.absentMonths", { months: 1 }));
    expect(html).toContain("1 month(s) have no reading");
    // NEGATIVE: the absent month must carry no height and no zero figure.
    const june = html.slice(html.indexOf('data-month="2026-06"'));
    const slot = june.slice(0, june.indexOf("</div>"));
    expect(slot).not.toContain("height");
    expect(slot).not.toContain(">0<");
  });

  it("BR-MET-106: a month that includes an estimate is MARKED, on the bar and under the chart", async () => {
    const html = await renderTab(payload({ series: [electric()] }));
    expect(html).toContain('data-estimated="true"');
    expect(html).toContain(
      t("customers.account.usage.barTitleEstimated", {
        month: "2026-08",
        value: "628",
        unit: "kWh",
      }),
    );
    expect(html).toContain(t("customers.account.usage.estimatedMonths", { months: 1 }));
  });

  it("hard rule 3: two services are two units and two charts, never one total", async () => {
    // The picker offers each service separately BECAUSE kWh and kgal do not
    // add; `All` draws them side by side and still sums nothing.
    const html = await renderTab(payload());
    expect(html).toContain(">Electric</option>");
    expect(html).toContain('<option value="water">Water</option>');
    // NEGATIVE: nothing anywhere sums 842 kWh and 3.42 kgal.
    expect(html).not.toContain("845.42");
    expect(html).not.toContain("Total usage");
  });

  it("DEF-CUS-4621/4514/4515: no placeholder and no raw key ever reaches the screen", async () => {
    // ⚠ **THE ONE ASSERTION THAT WOULD HAVE CAUGHT ALL THREE COPY DEFECTS,
    // and it works because it compares the markup against nothing the code
    // itself produced.** Every other assertion here renders `t(key, args)` on
    // both sides of a `toContain`, so a call whose argument names match no
    // placeholder — and a computed key with no catalogue entry — satisfy it
    // perfectly: both sides are equally wrong. The Product Owner found all
    // three by opening the screen, which is hard-won law 6 for the fourth
    // time on this file.
    for (const body of [
      payload(),
      payload({ series: [electric()] }),
      payload({
        series: [
          electric({
            metrics: {
              avg_per_month: metric(null, { unit: null }),
              peak: metric(null, { unit: null }),
              low: metric(null, { unit: null }),
              yoy: metric(null, { unit: null, absent_reason: "no_prior_reads" }),
            },
          }),
        ],
        water_avg: metric(null, {
          unit: null,
          absent_reason: "no_water_months",
          service_code: "electric",
        }),
      }),
    ]) {
      const html = await renderTab(body);
      expect(html).not.toContain("{{");
      // The chart's accessible name is one of the three, and the only one a
      // screenshot cannot show: it is read aloud, never drawn.
      expect(html).toContain('aria-label="Monthly Electric usage in kWh"');
      expect(html).not.toContain("customers.account.usage.");
    }
  });

  it("BR-SHL-010: `Compare to neighbors` is not drawn and not stubbed (B18 D3)", async () => {
    const html = await renderTab(payload());
    expect(html.toLowerCase()).not.toContain("neighbor");
    expect(html.toLowerCase()).not.toContain("neighbour");
  });

  it("an account with no calculated month says so plainly — no chart, no zeroes", async () => {
    const html = await renderTab(payload({ series: [], services: [] }));
    expect(html).toContain(t("customers.account.usage.empty"));
    expect(html).not.toContain('data-absent="false"');
    // …and no KPI strip, because there is nothing to average.
    expect(html).not.toContain(t("customers.account.usage.kpi.avg"));
  });

  it("a metric with no figure prints its REASON, never 0", async () => {
    // A WATER-only account, so all five figures — the fifth included — are
    // about the service on screen and every absence reaches the markup.
    const series: UsageSeries = {
      ...water(),
      metrics: {
        avg_per_month: metric(null, { unit: null }),
        peak: metric(null, { unit: null }),
        low: metric(null, { unit: null }),
        yoy: metric(null, { unit: null, absent_reason: "no_prior_reads" }),
      },
    };
    const html = await renderTab(
      payload({
        series: [series],
        water_avg: metric(null, {
          unit: null,
          absent_reason: "no_water_months",
          service_code: "water",
        }),
      }),
    );
    expect(html).toContain(t("customers.account.usage.absent.no_months_with_reads"));
    expect(html).toContain(t("customers.account.usage.absent.no_prior_reads"));
    expect(html).toContain(t("customers.account.usage.absent.no_water_months"));
    expect(html).not.toContain("0 kWh");
  });

  it("OQ-358: a series whose months disagree about the unit says so and carries the id", async () => {
    const series = electric({
      unit: null,
      unit_absence: { reason: "mixed_units_across_months", tracks: "OQ-358" },
    });
    const html = await renderTab(payload({ series: [series] }));
    expect(html).toContain(t("customers.account.usage.mixedUnits"));
    expect(html).toContain('data-tracks="OQ-358"');
  });

  it("states that it is loading rather than drawing an empty chart", async () => {
    expect(await renderTab("nothing-prefetched")).toContain(t("customers.account.usage.loading"));
  });

  it("chooses the FAILURE frame over the loading one, which SSR alone cannot show", () => {
    // ⚠ Measured on react-query 5 in this repo: a query cached as
    // `status: "error"` reports `pending / fetching` to `renderToStaticMarkup`,
    // because the server snapshot ignores a cached error. So the failure frame
    // is unreachable from this (node-tier) suite through a render, and the
    // decision is asserted where it lives instead.
    expect(usageViewState({ isPending: true, isError: false, data: undefined })).toBe("loading");
    expect(usageViewState({ isPending: false, isError: true, data: undefined })).toBe("failed");
    // errored AND retrying: still a failure, never "still waiting".
    expect(usageViewState({ isPending: true, isError: true, data: undefined })).toBe("failed");
    // settled with no body at all is a failure too, not an empty chart.
    expect(usageViewState({ isPending: false, isError: false, data: undefined })).toBe("failed");
    expect(usageViewState({ isPending: false, isError: false, data: payload() })).toBe("ready");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-011@a1fbf3f (the S21 operational tabs; BR-MET-106 snapshot 2026-08-24)
// generated: 2026-08-24 by the CR-030 W3 task 3.8 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest✔
// exceptions: E3 the fixtures are FOUR months rather than r10's 24 — the absence, the estimate mark and the two units are what these cases are about, and 24 identical bars would hide them
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
