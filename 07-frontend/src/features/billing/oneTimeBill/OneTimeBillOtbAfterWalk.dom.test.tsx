// @vitest-environment jsdom
/**
 * DEF-BIL-10067 — what the AFTER walk of 2026-10-12 still found on the one-time
 * bill (`05-prototype/otb-after-2026-10-12/README.md`, "Also seen"):
 *
 *   * (a) the Rates table's electric parts showed 373.33 + 133.33 + 293.33 =
 *     799.99 kWh against an 800 kWh read — the last part now takes the
 *     remainder on screen, as the engine does for the stored shares;
 *   * (b) the tag read "Split 09/15/2026" though electric is cut on 15 AND
 *     20 Sep — it names every cut;
 *   * the typed reading stays on the request after Continue posts it, so the
 *     preview and the draft are priced on it, and it is not posted twice.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render } from "@testing-library/react";
import i18n from "i18next";
import { afterEach, describe, expect, it } from "vitest";

import type { OneTimeBillRateRow } from "@/api/billingOpsEndpoints";

import { RatesTable } from "./ServicesStep";
import { footingShares, unpostedReadings } from "./oneTimeBillModel";
import type { OtbFormat } from "./oneTimeBillShared";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;
const fmt: OtbFormat = { t, currency: "USD", timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" };

const tiers = (a: string, b: string, c: string) => ({
  tiers: [
    { up_to: "500", unit: "kWh", price: a },
    { up_to: "1000", unit: "kWh", price: b },
    { up_to: null, unit: "kWh", price: c },
  ],
});

const electric: OneTimeBillRateRow = {
  service: "electric",
  asset_id: null,
  asset_label: "E-5012",
  rate_type: "tiered",
  usage_rate: tiers("0.1200", "0.1450", "0.1700"),
  base_charge: { amount: "12.0000", code: "BASE-E", set: true, per_asset: false, prorated: null },
  minimum: null,
  versions: [
    { label: "Electric", from: "2026-01-01" },
    { label: "Electric", from: "2026-09-15" },
    { label: "Electric", from: "2026-09-20" },
  ],
  amount: "111.1000",
  parts: [
    {
      period_start: "2026-09-01",
      period_end: "2026-09-14",
      days: 14,
      usage_rate: tiers("0.1100", "0.1350", "0.1600"),
      quantity: "373.333333",
      unit: "kWh",
      amount: "44.5700",
      version_label: "Electric",
      version_from: "2026-01-01",
    },
    {
      period_start: "2026-09-15",
      period_end: "2026-09-19",
      days: 5,
      usage_rate: tiers("0.1150", "0.1400", "0.1650"),
      quantity: "133.333333",
      unit: "kWh",
      amount: "16.5800",
      version_label: "Electric",
      version_from: "2026-09-15",
    },
    {
      period_start: "2026-09-20",
      period_end: "2026-09-30",
      days: 11,
      usage_rate: tiers("0.1200", "0.1450", "0.1700"),
      quantity: "293.333334",
      unit: "kWh",
      amount: "37.9500",
      version_label: "Electric",
      version_from: "2026-09-20",
    },
  ],
};

describe("(a) the shown parts add back to the read", () => {
  it("373.33 + 133.33 + 293.34 = 800, never 799.99", () => {
    render(<RatesTable rates={[electric]} plan={null} perPeriod={false} t={t} fmt={fmt} />);
    const parts = Array.from(document.querySelectorAll("[data-rate-part]"));
    expect(parts).toHaveLength(3);
    expect(parts[0]).toHaveTextContent("373.33 kWh");
    expect(parts[1]).toHaveTextContent("133.33 kWh");
    expect(parts[2]).toHaveTextContent("293.34 kWh");
  });

  it("footingShares: the last part takes the remainder, exactly", () => {
    expect(footingShares(["373.333333", "133.333333", "293.333334"])).toEqual([
      "373.33",
      "133.33",
      "293.34",
    ]);
    // Shares that already foot are unchanged: the PO's 0.79 + 0.91 = 1.70.
    expect(footingShares(["0.793333", "0.906667"])).toEqual(["0.79", "0.91"]);
    expect(footingShares(["5", null])).toEqual(["5", null]);
  });
});

describe("(b) the tag names every cut", () => {
  it("electric cut on 15 and 20 Sep reads both dates", () => {
    render(<RatesTable rates={[electric]} plan={null} perPeriod={false} t={t} fmt={fmt} />);
    const row = document.querySelector('[data-rate-row="electric"]');
    expect(row).toHaveTextContent("Split 09/15/2026, 09/20/2026");
  });
});

describe("the typed reading stays on the request after Continue", () => {
  const typed = [{ asset_id: "w-9011", read_at: "2026-09-29", value: "4.6", role: "current" as const }];
  it("a reading Continue already posted at that value is not posted again", () => {
    expect(unpostedReadings(typed, undefined)).toEqual(typed);
    expect(unpostedReadings(typed, { "w-9011|current|2026-09-29": "4.6" })).toEqual([]);
  });
  it("a changed value is posted", () => {
    expect(unpostedReadings(typed, { "w-9011|current|2026-09-29": "4.5" })).toEqual(typed);
  });
});
