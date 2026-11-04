// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-LED-10071 (J3) · DEF-LED-10072 (P2 · P4)
// Ruling:   decision log 2026-10-12 "FINANCE: JOURNAL SEARCH AND THE PERIOD
//           CONTROLS", CONFIRMED
// ───────────────────────────────────────────────────────
// Every quick choice, counted from a stated business date. **What would make
// these pass wrongly:** a window computed from the browser's clock — so every
// case names `today` explicitly and none of them could pass on another day.
import { describe, expect, it } from "vitest";

import { choiceFor, periodRefusal, periodWindow } from "./periodWindow";

const TODAY = "2026-10-12";
const OCTOBER = { start: "2026-10-01", end: "2026-10-31" };

describe("periodWindow — each quick choice from the business date", () => {
  it("Last 30 days is thirty days ending today, both ends included", () => {
    expect(periodWindow("last_30", TODAY)).toEqual({ from: "2026-09-13", to: TODAY });
  });

  it("Last 60 days", () => {
    expect(periodWindow("last_60", TODAY)).toEqual({ from: "2026-08-14", to: TODAY });
  });

  it("Last 90 days", () => {
    expect(periodWindow("last_90", TODAY)).toEqual({ from: "2026-07-15", to: TODAY });
  });

  it("This month is the finance month, ending today while it is still running (P4)", () => {
    expect(periodWindow("this_month", TODAY, OCTOBER)).toEqual({ from: "2026-10-01", to: TODAY });
    // An open month already over keeps its own end.
    expect(periodWindow("this_month", TODAY, { start: "2026-09-01", end: "2026-09-30" })).toEqual({
      from: "2026-09-01",
      to: "2026-09-30",
    });
  });

  it("Last month is the month before, whole", () => {
    expect(periodWindow("last_month", TODAY, OCTOBER)).toEqual({
      from: "2026-09-01",
      to: "2026-09-30",
    });
    expect(periodWindow("last_month", "2026-03-10", { start: "2026-03-01", end: "2026-03-31" })).toEqual(
      { from: "2026-02-01", to: "2026-02-28" },
    );
  });

  it("Custom has no window of its own", () => {
    expect(periodWindow("custom", TODAY)).toBeNull();
  });

  it("crosses a year boundary without a zone", () => {
    expect(periodWindow("last_30", "2026-01-10")).toEqual({ from: "2025-12-12", to: "2026-01-10" });
    expect(periodWindow("last_month", "2026-01-10", { start: "2026-01-01", end: "2026-01-31" })).toEqual(
      { from: "2025-12-01", to: "2025-12-31" },
    );
  });
});

describe("periodRefusal — P4", () => {
  it("refuses To before From", () => {
    expect(periodRefusal("2026-10-05", "2026-10-01", TODAY)).toBe("toBeforeFrom");
  });

  it("refuses a period that ends after today", () => {
    expect(periodRefusal("2026-10-01", "2026-10-13", TODAY)).toBe("endsAfterToday");
  });

  it("accepts a window ending today, and calls a half-typed one incomplete", () => {
    expect(periodRefusal("2026-10-01", TODAY, TODAY)).toBeNull();
    expect(periodRefusal("2026-10-01", "", TODAY)).toBe("incomplete");
    expect(periodRefusal("2026-02-31", TODAY, TODAY)).toBe("incomplete");
  });
});

describe("choiceFor — a typed window that IS a quick choice reads as one", () => {
  it("names the matching choice, and Custom otherwise", () => {
    const all = ["this_month", "last_month", "last_30", "custom"] as const;
    expect(choiceFor("2026-09-13", TODAY, TODAY, all, OCTOBER)).toBe("last_30");
    expect(choiceFor("2026-10-01", TODAY, TODAY, all, OCTOBER)).toBe("this_month");
    expect(choiceFor("2026-10-02", TODAY, TODAY, all, OCTOBER)).toBe("custom");
  });
});
