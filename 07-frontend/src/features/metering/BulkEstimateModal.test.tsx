// ── Trace ──────────────────────────────────────────────
// Screen:   Meter Reads blueprint **entry 20**, the Still-to-read tab's bulk bar
//           (p045's dark bar, p047's control table row *Estimate these*).
// Rules:    BR-MET-026/027/058/062 · BR-MET-030 (a reason on every estimate) ·
//           BR-SHL-025 (a refusal is an ANSWER with its reason) · hard rule 3 ·
//           B14 rules 7, 11, 31, 33
// ───────────────────────────────────────────────────────
//
// **THREE THINGS ARE GUARDED HERE AND EVERY ONE OF THEM SHIPS SILENTLY.**
//
// 1. **A PARTIAL ANSWER IS NEVER RENDERED AS A SUCCESS.** `POST
//    /reads/bulk-estimate` answers 200 with `estimated` AND `refused`, because
//    one meter with no history must not cost the other thirty-nine theirs. A
//    screen reading only `estimated` would send a clerk to a bill run believing
//    forty gaps were filled when four were — `DEF-708`'s shape.
//
// 2. **A RECORD IS `(meter, register, date)`, NOT A METER.** A TOU meter short
//    of three windows is THREE targets. Getting this wrong estimates one
//    register and leaves two, which reads on screen as *done*.
//
// 3. **NO UUID REACHES THE SCREEN (B14 rule 31).** The refusal list is keyed and
//    hooked on the meter NUMBER; the asset id is the anchor and never the value.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ReadChaseRow } from "@/api/endpoints";

import { BulkEstimateOutcome, bulkEstimateSchema, bulkEstimateTargets } from "./BulkEstimateModal";
import type { BulkEstimateResult } from "./readCycleEndpoints";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** ⚠ A REAL uuid, because the assertion that matters is `not.toContain`. */
const TOU = "01a09e06-452a-7db4-8d5f-6b33e4f2e3da";
const FLAT = "01a09e06-4531-7c11-b0a2-9d5a1f7c4e88";

function row(over: Partial<ReadChaseRow> = {}): ReadChaseRow {
  return {
    unit_id: "u-1",
    unit: "2C",
    premises: "1408 Elm",
    meter: "MTR-0471",
    asset_id: TOU,
    route: "RT-001",
    service: "electric",
    missing_channels: ["tou_on", "tou_mid", "tou_off"],
    days_left: -9,
    ...over,
  };
}

describe("Estimate these — the targets a tick becomes", () => {
  it("expands ONE ticked meter into one target per register it still owes", () => {
    expect(bulkEstimateTargets([row()], [TOU], "2026-09-03")).toEqual([
      { asset_id: TOU, meter_no: "MTR-0471", channel: "tou_on", read_at: "2026-09-03" },
      { asset_id: TOU, meter_no: "MTR-0471", channel: "tou_mid", read_at: "2026-09-03" },
      { asset_id: TOU, meter_no: "MTR-0471", channel: "tou_off", read_at: "2026-09-03" },
    ]);
  });

  it("touches only the ticked meters, never the whole shortfall", () => {
    const rows = [row(), row({ asset_id: FLAT, meter: "MTR-0488", missing_channels: ["total"] })];
    const targets = bulkEstimateTargets(rows, [FLAT], "2026-09-03");
    expect(targets).toHaveLength(1);
    expect(targets[0].meter_no).toBe("MTR-0488");
  });

  it("a chase row with no asset id is not a target — the anchor is what the server keys on", () => {
    expect(bulkEstimateTargets([row({ asset_id: null })], [TOU], "2026-09-03")).toEqual([]);
  });
});

describe("BR-MET-030 — the schema asks for shape, never for arithmetic", () => {
  it("refuses an empty reason and a malformed date", () => {
    expect(bulkEstimateSchema.safeParse({ read_at: "2026-09-03", reason: "" }).success).toBe(false);
    expect(bulkEstimateSchema.safeParse({ read_at: "03/09/2026", reason: "ok" }).success).toBe(
      false,
    );
    expect(
      bulkEstimateSchema.safeParse({ read_at: "2026-09-03", reason: "Window closed" }).success,
    ).toBe(true);
  });
});

describe("BR-SHL-025 — a refusal is an ANSWER, and a partial answer is rendered as one", () => {
  function outcome(result: BulkEstimateResult): string {
    return renderToStaticMarkup(
      <BulkEstimateOutcome result={result} t={(key, params) => t(key, params)} />,
    );
  }

  it("renders BOTH halves when some were filled and some were refused", () => {
    const html = outcome({
      estimated: [{ meter: "MTR-0471", channel: "tou_on", read_at: "2026-09-03" }],
      refused: [
        {
          meter: "MTR-0501",
          channel: "total",
          read_at: "2026-09-03",
          reason: "BIZ_STATE",
          message_key: "metering.read.reason.no_history",
        },
      ],
    });
    expect(html).toContain(t("metering.bulkEstimate.madeTitle", { count: 1 }));
    expect(html).toContain(t("metering.bulkEstimate.refused", { count: 1 }));
    // the refused meter is NAMED — a count alone does not tell a clerk where to go
    expect(html).toContain("MTR-0501");
  });

  it("says NOTHING WAS ESTIMATED rather than a cheerful zero when every one was refused", () => {
    const html = outcome({
      estimated: [],
      refused: [{ meter: "MTR-0501", channel: "total", read_at: null }],
    });
    expect(html).toContain(t("metering.bulkEstimate.noneMadeTitle"));
    expect(html).not.toContain(t("metering.bulkEstimate.madeTitle", { count: 0 }));
  });

  it("B14 rule 31 — the asset uuid is nowhere in the rendered answer", () => {
    const html = outcome({
      estimated: [],
      refused: [{ meter: "MTR-0501", channel: "total", read_at: null }],
    });
    expect(html).not.toContain(TOU);
    expect(html).not.toContain(FLAT);
  });

  it("G18 — a message key this app does not hold falls back to a sentence, never to the key", () => {
    const html = outcome({
      estimated: [],
      refused: [
        {
          meter: "MTR-0501",
          channel: "total",
          read_at: null,
          message_key: "metering.read.reason.a_key_nobody_wrote",
        },
      ],
    });
    expect(html).toContain(t("metering.bulkEstimate.refusedGeneric"));
    expect(html).not.toContain("metering.read.reason.a_key_nobody_wrote");
  });
});
