// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 §F — lane FIELD-2: automatic location (BR-WRK-061).
// ───────────────────────────────────────────────────────
import { afterEach, describe, expect, it, vi } from "vitest";

const written: unknown[] = [];
vi.mock("./offlineStore", () => ({
  readFix: vi.fn(async () => null),
  writeFix: vi.fn(async (_o: string, fix: unknown) => void written.push(fix)),
}));

import { bestFix, better, fixFromPosition, resetLocationForTests, startFix } from "./location";

function position(accuracy: number, at: number): GeolocationPosition {
  return {
    coords: { latitude: 29.56011234, longitude: -95.80721234, accuracy, altitude: null, altitudeAccuracy: null, heading: null, speed: null },
    timestamp: at,
  } as unknown as GeolocationPosition;
}

afterEach(() => {
  resetLocationForTests();
  written.length = 0;
});

describe("BR-WRK-061 — the best fix is kept, never traded for a worse one", () => {
  it("a smaller radius wins; a worse later fix does not replace a better one", () => {
    const a = fixFromPosition(position(30, 1000));
    const b = fixFromPosition(position(8, 2000));
    const c = fixFromPosition(position(300, 3000));
    expect(better(null, a)).toBe(true);
    expect(better(a, b)).toBe(true);
    expect(better(b, c)).toBe(false);
  });

  it("the wire's four fields, rounded as the server stores them", () => {
    expect(fixFromPosition(position(8.04, Date.parse("2026-10-04T15:00:00Z")))).toEqual({
      lat: 29.560112,
      lng: -95.807212,
      accuracy_m: 8,
      fix_at: "2026-10-04T15:00:00.000Z",
    });
  });

  it("acquisition starts at job start and keeps the best fix it is given", async () => {
    let push: ((p: GeolocationPosition) => void) | null = null;
    const watch = vi.fn((ok: (p: GeolocationPosition) => void) => {
      push = ok;
      return 7;
    });
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { watchPosition: watch, clearWatch: vi.fn() },
    });
    startFix("o1");
    startFix("o1"); // the same job twice is one watch
    expect(watch).toHaveBeenCalledTimes(1);
    push!(position(300, 1000));
    push!(position(8, 2000));
    push!(position(120, 3000));
    expect((await bestFix("o1"))?.accuracy_m).toBe(8);
    expect(written).toHaveLength(2); // 300 m, then 8 m — the 120 m fix was not better
  });

  it("no geolocation at all is no fix, never an error", async () => {
    Object.defineProperty(navigator, "geolocation", { configurable: true, value: undefined });
    startFix("o2");
    expect(await bestFix("o2")).toBeNull();
  });
});
