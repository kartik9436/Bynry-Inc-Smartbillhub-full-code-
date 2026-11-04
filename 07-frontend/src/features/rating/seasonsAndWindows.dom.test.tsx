// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-RAT-5736 — the TOU editor drew seasons and windows as two
//           unrelated panels, and every window carried its own Season dropdown.
//           DEF-RAT-5733 — a season boundary was four bare numeric boxes, so
//           31 April and month 13 typed in and were refused only at activation.
//           DEF-RAT-5734 — step 2 pre-listed every size class with a control on
//           each, and each row repeated its own column header as a label.
// Question: OQ-RAT-12410 — how the seasonal and time-of-use editors should be
//           DRAWN. Blocked until the PO delegated the drawing, 2026-09-18:
//           *"please design it - as per ui rules we have - fix these alos"*,
//           and then approved it: *"this is good - Wave 4 — the seasonal /
//           time-of-use editor"*.
// Rules:    B14 rule 33 (on-screen text is capped by what it is for) · rule 32
//           clause 3 (a row never repeats what its own control offers) · rule 8
//           and BR-SHL-033 (a long list is searchable; the DIVERGENCE for a
//           month/day pair is in `SeasonsAndWindows`' own docstring) ·
//           BR-RAT-033/034 (seasons cover the year; a window is per season ×
//           day type) · BR-RAT-067 (a window names its register)
// Note:     EVERY case below was shown RED against the two-panel editor before
//           the fix — hard-won law 7 — and the CONTROL case at the top of each
//           describe proves this fixture can tell a working screen from a
//           broken one before any red is trusted.
// ───────────────────────────────────────────────────────
import { cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import {
  emptyScheduleDraft,
  nextSeasonKey,
  seasonDayOfYear,
  structurePayload,
} from "./RateScheduleWizard";
import type { ScheduleDraft } from "./RateScheduleWizard";
import wizardSource from "./RateScheduleWizard.tsx?raw";

// Without this each `render` leaves its markup in the document and the NEXT
// query reads the PREVIOUS screen — a fixture that measures the render before
// the one under test cannot go red for the right reason.
afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string =>
  i18n.t(key, params ?? {}) as string;

const SUMMER = {
  key: "s0",
  label: "Summer",
  start_month: "4",
  start_day: "1",
  end_month: "9",
  end_day: "30",
  unit_price: "",
};
const WINTER = {
  key: "s1",
  label: "Winter",
  start_month: "10",
  start_day: "1",
  end_month: "3",
  end_day: "31",
  unit_price: "",
};

function touDraft(over: Partial<ScheduleDraft> = {}): ScheduleDraft {
  return {
    ...emptyScheduleDraft(),
    model: "time_of_use",
    seasons: [SUMMER, WINTER],
    windows: [
      {
        label: "Peak",
        season_key: "s0",
        day_type: "weekday",
        start_time: "14:00",
        end_time: "19:00",
        unit_price: "0.2400",
        channel: "tou_on",
      },
      {
        label: "Night",
        season_key: "s1",
        day_type: "weekday",
        start_time: "19:00",
        end_time: "14:00",
        unit_price: "0.0900",
        channel: "tou_off",
      },
    ],
    ...over,
  };
}

// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-RAT-5736 — ONE panel, and a window lives INSIDE its season", () => {

  it("THE CONTRACT IS UNCHANGED: the payload still posts the season's LABEL", () => {
    const structure = structurePayload(touDraft()) as {
      windows: Record<string, unknown>[];
    };
    expect(structure.windows[0].season).toBe("Summer");
    expect(structure.windows[1].season).toBe("Winter");
    // And a renamed season carries its windows with it, which is what the key
    // is FOR — by label this was `rating.tou.unknown_season` at activation.
    const renamed = touDraft({
      seasons: [{ ...SUMMER, label: "Peak season" }, WINTER],
    });
    expect(
      (structurePayload(renamed) as { windows: Record<string, unknown>[] }).windows[0].season,
    ).toBe("Peak season");
  });

  it("`nextSeasonKey` never reissues a key a season is already using", () => {
    expect(nextSeasonKey([])).toBe("s0");
    expect(nextSeasonKey([SUMMER, WINTER])).toBe("s2");
    // A gap left by a removal is reused, which is safe BECAUSE the windows
    // that pointed at it were removed with it.
    expect(nextSeasonKey([WINTER])).toBe("s0");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-RAT-5733 — a month by NAME, a day the month can hold", () => {

  it("`seasonDayOfYear` refuses what the boxes used to accept", () => {
    expect(seasonDayOfYear("13", "1")).toBeNull();
    expect(seasonDayOfYear("4", "31")).toBeNull();
    expect(seasonDayOfYear("2", "29")).toBeNull();
    expect(seasonDayOfYear("1", "1")).toBe(1);
    expect(seasonDayOfYear("12", "31")).toBe(365);
  });

});

// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-RAT-5735 — B14 rule 33 on the strings this wave touched", () => {
  const words = (key: string): number[] =>
    t(key)
      .split(/(?<=[.!?])\s+/)
      .map((sentence) => sentence.trim().split(/\s+/).filter(Boolean).length);

  it("every sentence of the reworded copy is six words or fewer", () => {
    for (const key of [
      "rating.season.hint",
      "rating.tou.optionBNote",
      "rating.tou.holidayNote",
      "rating.tou.orphanNote",
      "rating.tou.noWindows",
      "rating.rate.sizes.legacyBase",
      "rating.rate.sizes.noSizeClasses",
      "rating.rate.sizes.noBaseCode",
      "rating.rate.uomNoneForService",
      "rating.rate.baseNotEditableHere",
      "rating.rate.tiers.pureTiers",
      "rating.rate.sizes.tierOverrideOnStructure",
      "rating.rate.sub",
      "rating.rate.sizes.oneBaseEverySize",
      "rating.rate.sizes.fallbackNote",
      "rating.rate.tiers.hint",
      "rating.rate.basics.hint",
      "rating.rate.sizes.upliftGap",
      "rating.rate.sizes.blankIsNoFloor",
      "rating.rate.sizeTiers.noSizes",
      "rating.rate.sizeTiers.hint",
      "rating.rate.sizes.allPriced",
      "rating.rate.sizes.emptyTable",
    ]) {
      for (const count of words(key)) {
        expect({ key, count }).toEqual({ key, count: Math.min(count, 6) });
      }
    }
  });

  it("A CONSEQUENCE IS SHORTENED, NEVER REMOVED — rule 33 protects these by name", () => {
    // Money: a bill for an unserved size is REFUSED, and must never read $0.00.
    expect(t("rating.rate.sizes.baseNotServed", { code: "BASE-W" })).toContain("$0.00");
    expect(t("rating.rate.sizes.baseSizeNotServed", { code: "BASE-W" })).toContain("$0.00");
    // Activation is refused without a base code.
    expect(t("rating.rate.sizes.noBaseCode").toLowerCase()).toContain("refused");
    // ⚠ "A seasonal schedule saves and does not bill" WAS asserted here until
    // 2026-10-01. It stopped being a consequence and became false: a seasonal
    // schedule BILLS (`DEF-RAT-8832`, `OQ-234` closed 2026-09-07), and the
    // notice and its two keys are retired. See the hold-expiry case below.
    // A blank minimum is not zero.
    expect(t("rating.rate.sizes.blankIsNoFloor").toLowerCase()).toContain("not zero");
    // ⚠ AMENDED 2026-10-01 (`DEF-RAT-8739`): *"This stores from the effective
    // date. Already-billed amounts never change."* and the *Not read by billing
    // yet* band below were classed here as consequences rule 33 protects. The
    // PO asked for both to go (*"step 5 too much text"*), so they are retired,
    // and the PO's word outranks this lane's classification. Recorded in the
    // decision log of 2026-10-01 with the risk it leaves (`DEF-RAT-8737`).
    // The holiday calendar's location — dropped by the first cut of this
    // sweep, caught by an existing test, and restored as a second sentence.
    expect(t("rating.tou.holidayNote").toLowerCase()).toContain("calendar");
  });

  it("RATIONALE IS ZERO WORDS ON SCREEN — the base-only paragraph is gone", () => {
    // The reason a clerk ACTS on still rides on the disabled option itself.
    expect(t("rating.rate.baseOnlyDisabled", { model: "Base only" })).toContain("Base only");
    // The 29-word explanation of WHY it is listed is retired from all eleven.
    expect(i18n.t("rating.rate.baseOnlyGap")).toBe("rating.rate.baseOnlyGap");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-RAT-8832 — the 'seasonal cannot be billed' hold has EXPIRED", () => {
  // Hard-won law 2's mirror: a live feature behind a refusal. The notice was
  // true while `seasonal` had no pricing engine (OQ-234). The PO closed OQ-234
  // on 2026-09-07 ("please split  swithch it on") and the engine was built on
  // 2026-10-01, so the notice and both of its keys are gone. Re-adding either
  // tells a clerk the opposite of what the bill run now does; this goes red.
  it("neither notice key exists in the catalogue the screen reads", () => {
    expect(i18n.t("rating.seasonal.notBillableTitle")).toBe("rating.seasonal.notBillableTitle");
    expect(i18n.t("rating.seasonal.notBillableBody")).toBe("rating.seasonal.notBillableBody");
  });

  it("the wizard no longer renders a not-billable notice for Seasonal", () => {
    expect(wizardSource).not.toContain("rating.seasonal.notBillable");
  });
});
