// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-RAT-5826 — `Review & activate` showed NO prices for four of the
//           seven structures: it mapped `draft.tiers`, which only `flat` and
//           `tiered` fill, so a time-of-use schedule built over 47 acts
//           reviewed as `0 kWh and above · — · —`.
//           DEF-RAT-5830 — a missing season price refused with an unplaced
//           "This is required." on a box carrying no required mark, because the
//           server's field path bound to no control.
//           DEF-RAT-5832 — the demand editor explained a ratchet it offered no
//           control for.
// Rules:    hard rule 2 (money 4 / percentages 6, both DISPLAY 2) · PO ruling
//           2026-08-27, *"A rate is not money and not a quantity - 4 decimal
//           places"* · B14 rule 32 (a screen's description budget) · rule 33
//           (rationale is ZERO words on screen) · BR-RAT-1017 (a season owns
//           its windows) · BR-RAT-022 (a capacity unit is tenant text)
// Note:     ⚠ **EVERY CASE HERE WAS SHOWN RED AGAINST THE PRE-FIX CODE** —
//           hard-won law 7 — and the CONTROL case in each describe proves the
//           fixture can tell a working screen from a broken one first.
// ───────────────────────────────────────────────────────
import { cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { VersionRow } from "@/api/endpoints";
import i18n from "@/i18n";

import {
  emptyScheduleDraft,
  rateIn,
  reviewRateRows,
} from "./RateScheduleWizard";
import type { ScheduleDraft } from "./RateScheduleWizard";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string =>
  i18n.t(key, params ?? {}) as string;

/**
 * **THE WHOLE COMPOSED TABLE AS ONE STRING, AND THAT IS THE POINT.**
 *
 * *A price appears* passes on a screen that shows one season's prices twice
 * over, on a stale figure, or on the right figure against the wrong label. So
 * every assertion below reads the whole list — label AND figure, in order —
 * against a fixture whose two seasons deliberately carry DIFFERENT ladders.
 */
const composed = (draft: ScheduleDraft, inForce: VersionRow | null = null): string =>
  reviewRateRows(draft, inForce, t)
    .map((row) => `${row.label} = ${row.after}`)
    .join(" · ");

// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-RAT-5826 — the review prices every structure, not two of seven", () => {
  it("CONTROL: the two structures that always worked still read the same", () => {
    const flat = { ...emptyScheduleDraft(), model: "flat", uom: "kWh" };
    flat.tiers = [{ from_qty: "0", to_qty: "", unit_price: "0.1150" }];
    expect(composed(flat)).toBe("0 kWh and above = 0.115");
  });

  it("CONTROL: the empty seeded ladder is what every other structure used to show", () => {
    // ⚠ THIS IS THE DEFECT, PRESERVED AS A FACT. `emptyScheduleDraft` seeds ONE
    // blank tier, and the old block mapped it whatever the model was — so this
    // single row is exactly what a clerk saw after building a time-of-use
    // schedule with four priced windows.
    const bare = { ...emptyScheduleDraft(), model: "time_of_use", uom: "kWh" };
    expect(bare.tiers).toHaveLength(1);
    expect(bare.tiers[0].unit_price).toBe("");
  });

  it("TIME-OF-USE: every window, named by its SEASON and its hours", () => {
    const draft: ScheduleDraft = {
      ...emptyScheduleDraft(),
      model: "time_of_use",
      uom: "kWh",
      seasons: [
        { key: "s0", label: "Summer", start_month: "6", start_day: "1", end_month: "9", end_day: "30", unit_price: "" },
        { key: "s1", label: "Winter", start_month: "10", start_day: "1", end_month: "5", end_day: "31", unit_price: "" },
      ],
      windows: [
        { label: "Off-peak", season_key: "s0", day_type: "weekday", start_time: "00:00", end_time: "16:00", unit_price: "0.0900", channel: "tou_off" },
        { label: "On-peak", season_key: "s0", day_type: "weekday", start_time: "16:00", end_time: "00:00", unit_price: "0.2400", channel: "tou_on" },
        { label: "Off-peak", season_key: "s1", day_type: "weekday", start_time: "00:00", end_time: "16:00", unit_price: "0.0800", channel: "tou_off" },
        { label: "On-peak", season_key: "s1", day_type: "weekday", start_time: "16:00", end_time: "00:00", unit_price: "0.1900", channel: "tou_on" },
      ],
    };
    // Four windows, four DIFFERENT prices, each against the season that owns
    // it — so a table that repeated one season's ladder cannot pass.
    expect(composed(draft)).toBe(
      "Summer · Off-peak, 00:00 to 16:00 = 0.09 · " +
        "Summer · On-peak, 16:00 to 00:00 = 0.24 · " +
        "Winter · Off-peak, 00:00 to 16:00 = 0.08 · " +
        "Winter · On-peak, 16:00 to 00:00 = 0.19",
    );
  });

  it("TIME-OF-USE: a window whose season was removed is still reviewed", () => {
    const draft: ScheduleDraft = {
      ...emptyScheduleDraft(),
      model: "time_of_use",
      uom: "kWh",
      seasons: [],
      windows: [
        { label: "On-peak", season_key: "s9", day_type: "weekday", start_time: "16:00", end_time: "00:00", unit_price: "0.2400", channel: "tou_on" },
      ],
    };
    // It still POSTS, so it is still shown — losing it here would be a review
    // page that omits part of what will be stored.
    expect(composed(draft)).toBe(
      `${t("rating.rate.review.unnamed")} · On-peak, 16:00 to 00:00 = 0.24`,
    );
  });

  it("SEASONAL: one row per season, each with its own price", () => {
    const draft: ScheduleDraft = {
      ...emptyScheduleDraft(),
      model: "seasonal",
      uom: "kgal",
      seasons: [
        { key: "s0", label: "Summer", start_month: "6", start_day: "1", end_month: "9", end_day: "30", unit_price: "6.5000" },
        { key: "s1", label: "Winter", start_month: "10", start_day: "1", end_month: "5", end_day: "31", unit_price: "4.2000" },
      ],
    };
    expect(composed(draft)).toBe("Summer = 6.50 · Winter = 4.20");
    // …and the two figures are not the same one printed twice.
    const rows = reviewRateRows(draft, null, t);
    expect(rows[0].after).not.toBe(rows[1].after);
  });

  it("DEMAND: the energy rate AND the demand rate, each on its own row", () => {
    const draft: ScheduleDraft = {
      ...emptyScheduleDraft(),
      model: "demand",
      uom: "kW",
      demand: {
        ...emptyScheduleDraft().demand,
        energy_rate_per_kwh: "0.0850",
        demand_rate_per_kw: "14.5000",
        peak_window_label: "15-min monthly",
      },
    };
    expect(composed(draft)).toBe(
      `${t("rating.demand.energyLabel")} = 0.085 · ${t("rating.demand.demandLabel")} = 14.50`,
    );
  });

  it("DEMAND: the two options are reviewed only when the version states them", () => {
    const base = {
      ...emptyScheduleDraft(),
      model: "demand",
      uom: "kW",
      demand: {
        ...emptyScheduleDraft().demand,
        energy_rate_per_kwh: "0.0850",
        demand_rate_per_kw: "14.5000",
      },
    };
    expect(reviewRateRows(base, null, t)).toHaveLength(2);
    const withBoth: ScheduleDraft = {
      ...base,
      demand: {
        ...base.demand,
        ratchet_enabled: true,
        ratchet_pct: "80.00",
        pf_penalty_enabled: true,
        pf_penalty_rate_per_kw: "2.5000",
      },
    };
    expect(composed(withBoth)).toBe(
      `${t("rating.demand.energyLabel")} = 0.085 · ` +
        `${t("rating.demand.demandLabel")} = 14.50 · ` +
        `${t("rating.demand.pfRateLabel")} = 2.50 · ` +
        `${t("rating.demand.ratchetPctLabel")} = 80.00`,
    );
  });

  it("CAPACITY: the tenant's own unit word labels the rate", () => {
    const draft: ScheduleDraft = {
      ...emptyScheduleDraft(),
      model: "capacity",
      uom: "kW",
      capacity: { unit_label: "panel", rate_per_unit: "12.0000" },
    };
    expect(composed(draft)).toBe("panel = 12.00");
  });

  it("PERCENT OF SERVICE: the BASIS, the percentage and the rate", () => {
    const draft: ScheduleDraft = {
      ...emptyScheduleDraft(),
      model: "percent_of_service",
      percent: "85.50",
      basis_service: "water",
      tiers: [{ from_qty: "0", to_qty: "", unit_price: "5.0000" }],
    };
    // ⚠ **THIS ASSERTED ONE ROW UNTIL `CR-130-BRC07`, AND ONE ROW IS NOT
    // ENOUGH TO REVIEW THIS STRUCTURE.** `85.50%` means two entirely different
    // bills depending on which number it is taken of, so a comparison showing
    // the percentage moving and NOT the basis moving hides the change that
    // matters most. The basis comes first for that reason.
    //
    // ⚠ The percentage is still NOT `rateIn`'s four places: hard rule 2 gives
    // a percentage its own display, and padding it to `85.5000` would state a
    // precision nobody typed. The RATE beside it is money and does get four.
    expect(composed(draft)).toBe(
      `${t("rating.percentOfService.basisKindLabel")} = ${t("rating.percentOfService.basisKind.usage")} · ` +
        `${t("rating.percentOfService.percentLabel")} = 85.50 · ` +
        `${t("rating.rate.flat.priceLabel")} = 5.00`,
    );
  });

  it("PERCENT OF SERVICE: the charge basis reviews NO rate, because it has none", () => {
    // `CR-130-BRC07` §3 — a percentage of MONEY needs no price per unit and the
    // server refuses one by name. A review row reading "—" would send a clerk
    // looking for a field that is deliberately absent.
    const draft: ScheduleDraft = {
      ...emptyScheduleDraft(),
      model: "percent_of_service",
      percent: "80",
      basis_service: "water",
      percent_basis: "charge",
      tiers: [{ from_qty: "0", to_qty: "", unit_price: "5.0000" }],
    };
    expect(composed(draft)).toBe(
      `${t("rating.percentOfService.basisKindLabel")} = ${t("rating.percentOfService.basisKind.charge")} · ` +
        `${t("rating.percentOfService.percentLabel")} = 80`,
    );
  });

  it("the IN FORCE column reads the stored version, matched by NAME", () => {
    const draft: ScheduleDraft = {
      ...emptyScheduleDraft(),
      model: "seasonal",
      uom: "kgal",
      seasons: [
        { key: "s0", label: "Summer", start_month: "6", start_day: "1", end_month: "9", end_day: "30", unit_price: "6.5000" },
        { key: "s1", label: "Winter", start_month: "10", start_day: "1", end_month: "5", end_day: "31", unit_price: "4.2000" },
      ],
    };
    // The stored rows are in the OPPOSITE order on purpose: matched by index a
    // clerk would be shown last year's winter price against this year's summer.
    const inForce = {
      structure: {
        tiers: [
          { seq: 1, season: "Winter", size_class: null, from_qty: "0", to_qty: null, unit_price: "3.900000" },
          { seq: 2, season: "Summer", size_class: null, from_qty: "0", to_qty: null, unit_price: "6.100000" },
        ],
      },
    } as unknown as VersionRow;
    const rows = reviewRateRows(draft, inForce, t);
    expect(rows.map((row) => `${row.label}: ${row.before} → ${row.after}`)).toEqual([
      "Summer: 6.10 → 6.50",
      "Winter: 3.90 → 4.20",
    ]);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
describe("a unit price shows up to FOUR decimal places, at least two (PO 2026-10-02, narrowing 2026-08-27)", () => {
  it("pads what a clerk typed and trims what a storage column padded", () => {
    expect(rateIn("3.200000")).toBe("3.20"); // the six-place stored value
    expect(rateIn("0.09")).toBe("0.09"); // what a clerk actually types
    expect(rateIn("0.1150")).toBe("0.115");
    expect(rateIn("0.042500")).toBe("0.0425"); // PO 2026-10-02: never 0.04
    expect(rateIn("14.5")).toBe("14.50");
  });

  it("never rounds — a figure it cannot show at four places is shown whole", () => {
    expect(rateIn("0.14205")).toBe("0.14205");
    expect(rateIn("12")).toBe("12"); // no decimal point: handed back untouched
  });

  it("an absent figure is an em-dash, never a zero", () => {
    expect(rateIn("")).toBe("—");
    expect(rateIn(null)).toBe("—");
    expect(rateIn(undefined)).toBe("—");
  });
});
