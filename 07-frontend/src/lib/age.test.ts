// DEF-MET-10164 — the one age arithmetic and its words.
// Proved RED before green: with `addMonths` clamping removed (plain day carry),
// `2026-01-31 → 2026-02-28` read `28 days` and the leap-day case read
// `11 mos`; with `formatAge` ignoring the plural (`_other` only) `1 yr` read
// `1 yrs`.
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";
import { ageBetween, dayInZone, formatAge } from "@/lib/age";

const t = i18n.getFixedT("en");
const words = (start: string, end: string, tz = "America/Chicago") => {
  const age = ageBetween(start, end, tz);
  return age === null ? null : formatAge(age, t);
};

describe("ageBetween", () => {
  it("the PO's worked figure: 03/14/1996 on 10/17/2026 is 30 yrs 7 mos", () => {
    expect(ageBetween("1996-03-14", "2026-10-17", "America/Chicago")).toEqual({
      years: 30,
      months: 7,
      days: 3,
    });
    expect(words("1996-03-14", "2026-10-17")).toBe("30 yrs 7 mos");
  });

  it("a unit added in 2015 to a 1996 building is 11 yrs (its own date)", () => {
    expect(words("2015-06-01", "2026-10-17")).toBe("11 yrs 4 mos");
  });

  it("same day is 0 days", () => {
    expect(words("2026-10-17", "2026-10-17")).toBe("0 days");
  });

  it("under a month is days only, under a year months only", () => {
    expect(words("2026-10-05", "2026-10-17")).toBe("12 days");
    expect(words("2026-06-17", "2026-10-17")).toBe("4 mos");
    expect(words("2026-06-18", "2026-10-17")).toBe("3 mos");
  });

  it("singulars", () => {
    expect(words("2025-10-17", "2026-10-17")).toBe("1 yr");
    expect(words("2025-09-17", "2026-10-17")).toBe("1 yr 1 mo");
    expect(words("2026-09-17", "2026-10-17")).toBe("1 mo");
    expect(words("2026-10-16", "2026-10-17")).toBe("1 day");
  });

  it("whole years print no 0 mos", () => {
    expect(words("2021-10-17", "2026-10-17")).toBe("5 yrs");
  });

  it("month ends: the anniversary clamps to the last day of a shorter month", () => {
    expect(words("2026-01-31", "2026-02-28")).toBe("1 mo");
    expect(words("2026-01-31", "2026-02-27")).toBe("27 days");
    expect(words("2026-01-31", "2026-03-30")).toBe("1 mo"); // days drop under months
    expect(ageBetween("2026-01-31", "2026-03-30", "UTC")).toEqual({ years: 0, months: 1, days: 30 });
    expect(words("2026-03-31", "2026-04-30")).toBe("1 mo");
  });

  it("leap day: 29 Feb 2024 is 1 yr on 28 Feb 2025, and 4 yrs on 29 Feb 2028", () => {
    expect(words("2024-02-29", "2025-02-28")).toBe("1 yr");
    expect(words("2024-02-29", "2025-02-27")).toBe("11 mos");
    expect(words("2024-02-29", "2028-02-29")).toBe("4 yrs");
    expect(words("2023-02-28", "2024-02-29")).toBe("1 yr");
  });

  it("a start after the end is no age at all (null), never a negative", () => {
    expect(ageBetween("2026-10-18", "2026-10-17", "UTC")).toBeNull();
    expect(ageBetween(null, "2026-10-17", "UTC")).toBeNull();
    expect(ageBetween("not a date", "2026-10-17", "UTC")).toBeNull();
  });

  it("an instant is read as a day in the TENANT's zone, not UTC", () => {
    // 03:00 UTC on 15 March is still 14 March in Chicago.
    expect(dayInZone("1996-03-15T03:00:00+00:00", "America/Chicago")).toBe("1996-03-14");
    expect(dayInZone("1996-03-15T03:00:00+00:00", "UTC")).toBe("1996-03-15");
    // and a calendar date is used exactly as written
    expect(dayInZone("1996-03-14", "Asia/Tokyo")).toBe("1996-03-14");
  });

  it("end null means today in the tenant's zone", () => {
    const age = ageBetween("2000-01-01", null, "UTC");
    expect(age).not.toBeNull();
    expect(age!.years).toBeGreaterThanOrEqual(26);
  });
});

describe("formatAge in another catalogue", () => {
  it("Japanese joins with no space", () => {
    const ja = i18n.getFixedT("ja-JP");
    expect(formatAge({ years: 30, months: 7, days: 3 }, ja)).toBe("30年7か月");
  });
});
