// ── Trace ──────────────────────────────────────────────
// Change:   CR-101-BRC03 — Billing §03, `16 Scope` (blueprint p046 · p048).
//           "Is billing continuous?" is the clerk's real question and nothing
//           in this product answered it.
// Rules:    Blueprint p048 — *"A gap is days nobody billed. An overlap is days
//           billed twice. Both are silent, both are money, and neither is
//           visible anywhere in this product today."* · B14 rule 37 — a figure
//           drawn in a wireframe is an ILLUSTRATION, so no drawn date is
//           asserted here and no fixture is seeded from one
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import type { BillRunHistoryRow } from "@/api/endpoints";

import { periodContinuity } from "./billRunShared";

const CYCLE = "cycle-a";
const OTHER = "cycle-b";

function run(over: Partial<BillRunHistoryRow> = {}): BillRunHistoryRow {
  return {
    id: "run-1",
    run_no: "RUN-0001",
    cycle_id: CYCLE,
    period_start: "2026-01-01",
    period_end: "2026-01-31",
    issued_at: null,
    accounts: 0,
    bills_issued: 0,
    held: 0,
    status: "draft",
    bill_type: "cycle",
    created_at: null,
    ...over,
  };
}

describe("CR-101-BRC03 — is this period continuous with the last one?", () => {
  it("says nothing at all when there is no previous run to compare against", () => {
    // ⚠ **THE CASE THAT MATTERS MOST, AND IT IS THE ONE THAT RENDERS NOTHING.**
    // "We could not look" and "there is no gap" are different facts, and only
    // one of them is safe to read as good news. A green band over a utility's
    // first ever run would be an absence of evidence drawn as evidence of
    // absence — the chip-stuck-at-zero shape.
    expect(periodContinuity("2026-02-01", CYCLE, []).state).toBe("unknown");
    expect(periodContinuity("", CYCLE, [run()]).state).toBe("unknown");
    expect(periodContinuity("2026-02-01", "", [run()]).state).toBe("unknown");
    // A run on ANOTHER cycle answers nothing about this one.
    expect(periodContinuity("2026-02-01", CYCLE, [run({ cycle_id: OTHER })]).state).toBe("unknown");
    // A run with no period recorded cannot be compared against either.
    expect(periodContinuity("2026-02-01", CYCLE, [run({ period_end: null })]).state).toBe("unknown");
  });

  it("continuous: this period starts the day after the last one ended", () => {
    const verdict = periodContinuity("2026-02-01", CYCLE, [run()]);
    expect(verdict.state).toBe("continuous");
  });

  it("gap: days nobody billed, counted and named", () => {
    // Last run ended 31 Jan; this one starts 4 Feb. 1–3 Feb were never billed.
    const verdict = periodContinuity("2026-02-04", CYCLE, [run()]);
    expect(verdict).toEqual({ state: "gap", days: 3, from: "2026-02-01", to: "2026-02-03" });
  });

  it("overlap: days that would be billed twice, counted and named", () => {
    // Last run ended 31 Jan; this one starts 29 Jan. 29–31 Jan are covered
    // twice — three days, INCLUSIVE of both ends, because each of those days
    // carries two bills.
    const verdict = periodContinuity("2026-01-29", CYCLE, [run()]);
    expect(verdict).toEqual({ state: "overlap", days: 3, from: "2026-01-29", to: "2026-01-31" });
  });

  it("a one-day gap and a one-day overlap are each counted as one", () => {
    // The off-by-one either side of `continuous`, which is where this kind of
    // arithmetic goes wrong and where it is least visible.
    expect(periodContinuity("2026-02-02", CYCLE, [run()])).toMatchObject({ state: "gap", days: 1 });
    expect(periodContinuity("2026-01-31", CYCLE, [run()])).toMatchObject({
      state: "overlap",
      days: 1,
    });
  });

  it("compares against the run that ENDED LATEST, not the first row it meets", () => {
    const runs = [
      run({ id: "old", period_start: "2025-11-01", period_end: "2025-11-30" }),
      run({ id: "recent", period_start: "2026-01-01", period_end: "2026-01-31" }),
    ];
    expect(periodContinuity("2026-02-01", CYCLE, runs).state).toBe("continuous");
    // …and the order the server happens to send them in must not change it.
    expect(periodContinuity("2026-02-01", CYCLE, [...runs].reverse()).state).toBe("continuous");
  });

  it("⚠ ignores the run you are re-opening, so a walk back is not an overlap", () => {
    // **THE FALSE ALARM THIS GUARDS, AND IT IS THE MOST ORDINARY THING A CLERK
    // DOES ON THIS SCREEN.** `GET /billing/runs` returns the run currently
    // being edited alongside the finished ones. Comparing a period with ITSELF
    // reports the whole period billed twice — a red danger band, on every
    // re-entry, for ever. "Previous" therefore means a run that STARTS
    // strictly before this one, never merely a different row.
    const mine = run({ id: "mine", period_start: "2026-02-01", period_end: "2026-02-28" });
    const last = run({ id: "last", period_start: "2026-01-01", period_end: "2026-01-31" });
    expect(periodContinuity("2026-02-01", CYCLE, [mine, last]).state).toBe("continuous");
  });

  it("counts across a month boundary and a leap day rather than by month length", () => {
    // 2028 is a leap year: Feb has 29 days. A count that assumed 28 would be
    // one day short here and nowhere else, which is the kind of arithmetic
    // that ships.
    const feb = run({ period_start: "2028-02-01", period_end: "2028-02-29" });
    expect(periodContinuity("2028-03-01", CYCLE, [feb]).state).toBe("continuous");
    expect(periodContinuity("2028-03-02", CYCLE, [feb])).toMatchObject({ state: "gap", days: 1 });
  });
});
