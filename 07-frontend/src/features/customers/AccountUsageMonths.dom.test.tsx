// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-10162 (no previous/current reading, no check result) ·
//          DEF-CUS-5146 (Read on / Source stated absent)
// Ruling:  decision log 2026-10-15 — USAGE TAB "MONTH BY MONTH" (PO: "go ahead")
// Rules:   BR-MET-106 (an unread month is ABSENT, never 0) · hard rule 3 (one
//          unit per figure — one row per service) · hard-won law 2 (service
//          names from the payload, never typed out)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, ASKED FIRST** (law 7 habit 2):
//   * *"the page contains 1,444,517"* passes if the figure lands in the wrong
//     column — so every cell is read BY ITS COLUMN in its own row;
//   * a `t()` on both sides proves only that the code agrees with itself — so
//     the worked row's words are asserted as LITERALS (`DEF-CUS-4622`);
//   * a bare harness with no `/:tenant/...` route builds `//…` addresses — so
//     the tab is mounted under the real account path (hard-won law 2).
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import i18n from "@/i18n";

import { AccountUsageTab } from "./AccountUsageTab";
import type { UsagePayload, UsagePoint, UsageReading, UsageSeries } from "./AccountUsageTab";

const TENANT = "brazosbend";
const ACCOUNT = "3f1a9c2e-0000-7000-8000-0000000000aa";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function reading(over: Partial<UsageReading> = {}): UsageReading {
  return {
    read_count: 1,
    read_on: "2026-09-28",
    source: "manual",
    read_method: "walk_by",
    read_method_origin: "recorded",
    previous_reading: "1240310.000000",
    previous_reading_display: "1240310",
    current_reading: "1444517.000000",
    current_reading_display: "1444517",
    reading_unit: "gal",
    readings_absent_reason: null,
    check: "high",
    status: "high",
    ...over,
  };
}

function point(month: string, quantity: string | null, over: Partial<UsagePoint> = {}): UsagePoint {
  const absent = quantity === null;
  return {
    month,
    quantity,
    quantity_display: quantity,
    unit: absent ? null : "gal",
    absent,
    read_count: absent ? 0 : 1,
    estimated_read_count: 0,
    estimated: false,
    computed_at: absent ? null : "2026-10-01T00:00:00Z",
    reading: absent ? null : reading(),
    ...over,
  };
}

const NONE = { value: null, display: null, unit: null, absent_reason: "no_months_with_reads" };

function series(code: string, name: string, points: UsagePoint[], unit = "gal"): UsageSeries {
  return {
    service: { id: `svc-${code}`, code, name },
    unit,
    unit_absence: null,
    points,
    months_present: points.filter((p) => !p.absent).length,
    months_absent: points.filter((p) => p.absent).length,
    metrics: { avg_per_month: NONE, peak: NONE, low: NONE, yoy: NONE },
  };
}

function payload(all: UsageSeries[]): UsagePayload {
  return {
    account_id: ACCOUNT,
    window: { months: 24, from: "2026-06", to: "2026-09", options: [12, 24] },
    services: all.map((s) => s.service),
    series: all,
    water_avg: { ...NONE, service_code: "water" },
    rule_ref: "BR-MET-106",
  };
}

/** The PO's account shape: one water meter, four months. */
const WATER = series("water", "Water", [
  point("2026-06", null),
  point("2026-07", "238356.000000", {
    read_count: 2,
    reading: reading({
      read_count: 2,
      read_on: "2026-07-31",
      source: "ami",
      read_method: "ami",
      previous_reading: "800000.000000",
      current_reading: "1038356.000000",
      check: "low",
      status: "low",
    }),
  }),
  point("2026-08", "9000.000000", {
    estimated: true,
    estimated_read_count: 1,
    reading: reading({
      read_on: "2026-08-30",
      source: "estimated",
      read_method: null,
      read_method_origin: "not_stated",
      previous_reading: null,
      previous_reading_display: null,
      current_reading: null,
      current_reading_display: null,
      check: "estimated",
      status: "estimated",
    }),
  }),
  point("2026-09", "204207.000000"),
]);

function mount(body: UsagePayload) {
  const client = createApiClient({
    tenant: TENANT,
    fetchImpl: async () =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TENANT}/accounts/${ACCOUNT}?tab=usage`]}>
        <Routes>
          <Route
            path="/:tenant/accounts/:accountId"
            element={<AccountUsageTab accountId={ACCOUNT} client={client} t={t} />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Each body row as `{column header: cell text}`. */
async function rows(): Promise<Array<Record<string, string>>> {
  const group = await screen.findByText("Month by month");
  const table = group.closest("section")?.querySelector("table");
  if (!table) throw new Error("no Month by month table");
  const heads = [...table.querySelectorAll("thead th")].map((th) => th.textContent ?? "");
  return [...table.querySelectorAll("tbody tr")].map((tr) => {
    const cells = [...tr.querySelectorAll("td")];
    return Object.fromEntries(heads.map((h, i) => [h, cells[i]?.textContent ?? ""]));
  });
}

afterEach(() => cleanup());

describe("DEF-CUS-10162 · Usage tab, Month by month", () => {
  it("draws the PO's seven columns, in the ruled order, for one service", async () => {
    mount(payload([WATER]));
    const group = await screen.findByText("Month by month");
    const table = group.closest("section")?.querySelector("table") as HTMLTableElement;
    const heads = [...table.querySelectorAll("thead th")].map((th) => th.textContent);
    expect(heads).toEqual([
      "Month",
      "Usage",
      "Previous reading",
      "Current reading",
      "Read on",
      "Source",
      "Check",
    ]);
  });

  it("the worked row: Sep 2026 · 204,207 gal · 1,240,310 · 1,444,517 · 09/28/2026 · Manual (Walk-by) · High", async () => {
    mount(payload([WATER]));
    const [sep] = await rows();
    expect(sep).toEqual({
      Month: "Sep 2026",
      Usage: "204,207 gal",
      "Previous reading": "1,240,310",
      "Current reading": "1,444,517",
      "Read on": "09/28/2026",
      Source: "Manual entry (Walk-by)",
      Check: "High",
    });
    // High is the DANGER tone (PO step 3) — the kit's danger class.
    const chip = within(document.querySelector('tr[data-usage-month="2026-09"]') as HTMLElement)
      .getByText("High");
    expect(chip).toHaveClass("pill", "past");
  });

  it("several readings: the latest date and source, a '2 readings' note, Low as warning", async () => {
    mount(payload([WATER]));
    const july = (await rows())[2];
    expect(july).toEqual({
      Month: "Jul 2026",
      Usage: "238,356 gal",
      "Previous reading": "800,000",
      "Current reading": "1,038,356",
      "Read on": "07/31/20262 readings",
      Source: "AMI (AMI)",
      Check: "Low",
    });
    const chip = within(document.querySelector('tr[data-usage-month="2026-07"]') as HTMLElement)
      .getByText("Low");
    expect(chip).toHaveClass("bg-warning-100");
  });

  it("an estimated month leaves the readings empty and says Estimated", async () => {
    mount(payload([WATER]));
    const august = (await rows())[1];
    expect(august).toEqual({
      Month: "Aug 2026",
      Usage: "9,000 gal",
      "Previous reading": "",
      "Current reading": "",
      "Read on": "08/30/2026",
      Source: "Estimated",
      Check: "Estimated",
    });
  });

  it("a month with no reading says 'No reading' and every other cell is empty", async () => {
    mount(payload([WATER]));
    const june = (await rows())[3];
    expect(june).toEqual({
      Month: "Jun 2026",
      Usage: "No reading",
      "Previous reading": "",
      "Current reading": "",
      "Read on": "",
      Source: "",
      Check: "",
    });
    // NEGATIVE: the retired stated absence is gone from the whole tab (the
    // row above already proves the unread month is not a zero, BR-MET-106).
    expect(document.body.textContent).not.toContain("Not recorded");
  });

  it("any other flag reads 'Flagged' as a warning, and its hover names the rule", async () => {
    const flagged = series("water", "Water", [
      point("2026-09", "4000.000000", {
        reading: reading({ check: "flagged", status: "days_threshold" }),
      }),
    ]);
    mount(payload([flagged]));
    const [sep] = await rows();
    expect(sep.Check).toBe("Flagged");
    const chip = within(document.querySelector('tr[data-usage-month="2026-09"]') as HTMLElement)
      .getByText("Flagged");
    expect(chip).toHaveClass("bg-warning-100");
    expect(chip).toHaveAttribute("title", "Read interval");
  });

  it("two services: one row per service per month, the Service column from the payload", async () => {
    const electric = series(
      "electric",
      "Electric",
      [
        point("2026-09", "842.000000", {
          unit: "kWh",
          reading: reading({
            read_on: "2026-09-05",
            previous_reading: "5000.000000",
            current_reading: "5842.000000",
            reading_unit: "kWh",
            source: "import",
            read_method: "drive_by",
            check: "ok",
            status: "ok",
          }),
        }),
      ],
      "kWh",
    );
    const water = series("water", "Water", [point("2026-09", null)]);
    mount(payload([electric, water]));
    const all = await rows();
    expect(all).toEqual([
      {
        Month: "Sep 2026",
        Service: "Electric",
        Usage: "842 kWh",
        "Previous reading": "5,000",
        "Current reading": "5,842",
        "Read on": "09/05/2026",
        Source: "File import (Drive-by)",
        Check: "OK",
      },
      {
        Month: "Sep 2026",
        Service: "Water",
        Usage: "No reading",
        "Previous reading": "",
        "Current reading": "",
        "Read on": "",
        Source: "",
        Check: "",
      },
    ]);
    const ok = within(document.querySelector('tr[data-usage-service="electric"]') as HTMLElement)
      .getByText("OK");
    expect(ok).toHaveClass("bg-success-100");
  });
});
