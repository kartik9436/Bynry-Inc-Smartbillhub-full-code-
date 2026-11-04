// ── Trace ──────────────────────────────────────────────
// Story:    US-AST-011 (BR-AST-029's two records) · US-AST-012 (TC-1: the S29
//           drawer shows each record's type and links its pair)
//           Screens: S29
// Rules:    BR-AST-029 · BR-AST-010 (only net assets carry export records) ·
//           BR-AST-025 (quantity + unit everywhere, NEVER money) ·
//           CLAUDE.md rule 3 (a quantity carries its unit)
// ───────────────────────────────────────────────────────
/**
 * The panel that closes the `metering` surface-debt line, tested against the
 * sentence that named it: *"no screen shows the two channels AS A PAIR, which
 * is the whole point of the story."*
 *
 * Three of these five assert an ABSENCE — no netted figure, no money, no zero
 * on a flat meter — because on this story the things the screen must NOT say
 * are the rules with signatures on them (BR-AST-025, BR-AST-010, OQ-001).
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { NetMeterPair as NetMeterPairPayload } from "@/api/endpoints";

import { NetMeterPair, hasNetPair, pairAbsenceKey } from "./NetMeterPair";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** EP-AST-05 §4: M-4021's Aug cycle — 684 kWh delivered, 120 kWh exported. */
function pair(over: Partial<NetMeterPairPayload> = {}): NetMeterPairPayload {
  return {
    is_net_meter: true,
    read_at: "2026-08-03T00:00:00Z",
    consumption: {
      read_id: "r-import",
      channel: "total",
      read_type: "consumption",
      consumption: "684.000000",
      unit: "kWh",
      usage_display: "684 kWh",
      current_value: "42864.000000",
      current_value_display: "42864 kWh",
      status: "ok",
      lifecycle: "committed",
    },
    export: {
      read_id: "r-export",
      channel: "export",
      read_type: "export",
      consumption: "120.000000",
      unit: "kWh",
      usage_display: "120 kWh",
      current_value: "120.000000",
      current_value_display: "120 kWh",
      status: "ok",
      lifecycle: "committed",
    },
    absent_reason: null,
    ...over,
  };
}

describe("S29 — the net-metering pair (US-AST-011 / US-AST-012)", () => {
  it("US-AST-012 TC-1: both channels render TOGETHER, each with its own unit", () => {
    const html = renderToStaticMarkup(<NetMeterPair pair={pair()} />);
    expect(html).toContain(t("metering.read.netPair.title"));
    // Rule 3 — the SERVER's composed figure, unit included, on both sides.
    expect(html).toContain("684 kWh");
    expect(html).toContain("120 kWh");
    expect(html).toContain(t("metering.read.netPair.imported"));
    expect(html).toContain(t("metering.read.netPair.exported"));
  });

  it("BR-AST-025 / OQ-001: the two figures are NEVER netted and no money appears", () => {
    const html = renderToStaticMarkup(<NetMeterPair pair={pair()} />);
    // 684 − 120 = 564. That subtraction IS the net-metering credit math; it
    // lives in rating (EP-RAT-06) and is gated by OQ-001, and v1 bills solar as
    // a capacity charge. If this number ever appears here, this screen has
    // started doing another module's arithmetic.
    expect(html).not.toContain("564");
    expect(html).not.toContain("$");
    expect(html).not.toContain("USD");
    // …and the screen SAYS no credit is computed, rather than leaving a reader
    // to assume one is coming.
    expect(html).toContain(t("metering.read.netPair.noCreditYet"));
  });

  it("BR-AST-010: a flat meter renders NOTHING — never 'Export: 0'", () => {
    const flat = pair({
      is_net_meter: false,
      consumption: null,
      export: null,
      absent_reason: "asset_is_not_net_metering",
    });
    expect(hasNetPair(flat)).toBe(false);
    expect(renderToStaticMarkup(<NetMeterPair pair={flat} />)).toBe("");
  });

  it("BR-AST-029: a net cycle with no export reading says so — it does not print 0", () => {
    const gap = pair({ export: null, absent_reason: "no_export_record" });
    expect(pairAbsenceKey(gap)).toBe("metering.read.netPair.noExport");
    const html = renderToStaticMarkup(<NetMeterPair pair={gap} />);
    expect(html).toContain(t("metering.read.netPair.noExport"));
    // An em-dash, not a zero: "exported nothing" and "was not read" are
    // different facts and a 0 would state a third one that is true of neither.
    expect(html).toContain("—");
    expect(html).not.toContain(">0<");
  });

  it("an absence code the server adds later renders its own sentence, not a wrong one", () => {
    expect(pairAbsenceKey(pair({ absent_reason: "no_consumption_record" }))).toBe(
      "metering.read.netPair.noConsumption",
    );
    expect(pairAbsenceKey(pair())).toBeNull();
  });
});
