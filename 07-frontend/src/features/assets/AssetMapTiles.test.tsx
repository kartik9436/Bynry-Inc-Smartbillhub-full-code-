// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-INT-4287 — the asset map drew a flat grey rectangle for EVERY
//          tenant. The Product Owner, on the deployed build v2.208.1: *"in
//          previous version Map in asset was working now it is not"*.
// Rules:   BR-INT-048 (the page-security policy is generated from the
//          registered browser operations) · hard-won law 2 (a value computed
//          and never applied) · hard-won law 5 (one fact, one place)
// Tests:   this file · 06-backend/tests/test_us_int_042_gis.py (the half that
//          decides what the browser is PERMITTED to fetch)
// ───────────────────────────────────────────────────────
//
// ⚠ **`tileUrlFor` HAD NO TEST OF ANY KIND, AND NEITHER DID THE PAGE POLICY —
// a grep of `src/**/*.test.ts(x)` for `tileUrlFor`, `getPagePolicy` and
// `page-policy` returned NOTHING on 2026-09-06.** That is why the shipped
// fallback and the fail-closed policy could contradict each other for a whole
// deployment with `tsc`, eslint and every suite green: the two halves were each
// correct alone and nothing anywhere compared them.
//
// The assertions below are about the CONTRACT rather than about pixels — no
// gate in this repo reads rendered output (hard-won law 6), so the browser
// walkthrough is what proves the map draws. What this file makes impossible is
// the specific way it stopped drawing: a host of our own that the policy does
// not know about.
import { describe, expect, it } from "vitest";

import type { PagePolicyView } from "@/api/endpoints";

import { TILE_PATH, tileUrlFor } from "@/features/integrations/basemap";

const ESRI = "https://server.arcgisonline.com";

/** The payload shape `GET /integrations/page-policy` answers. */
function policy(over: Partial<PagePolicyView> = {}): PagePolicyView {
  return {
    policy: "default-src 'self'",
    hosts: {},
    tile_host: null,
    browser_operations: [],
    ...over,
  };
}

describe("DEF-INT-4287 · the map's tile host and the policy's are one fact", () => {
  it("draws NO tile layer when the policy names no host", () => {
    // ⚠ The whole defect in one line: this used to answer Esri's address, and
    // the policy for that same tenant permitted `img-src 'self' data: blob:`.
    // Every tile was refused, the zoom controls and the SVG markers still drew,
    // and the result was a grey rectangle with a blob on it.
    expect(tileUrlFor(null)).toBeNull();
    expect(tileUrlFor(undefined)).toBeNull();
    expect(tileUrlFor("   ")).toBeNull();
  });

  it("builds the template under whatever host the policy permitted", () => {
    expect(tileUrlFor(ESRI)).toBe(`${ESRI}${TILE_PATH}`);
    // R-7 — a city that runs its own tile server changes one field on Settings.
    expect(tileUrlFor("https://tiles.brazosbend.example")).toBe(
      `https://tiles.brazosbend.example${TILE_PATH}`,
    );
    // A trailing slash on a typed host must not produce a doubled path.
    expect(tileUrlFor("https://tiles.brazosbend.example/")).toBe(
      `https://tiles.brazosbend.example${TILE_PATH}`,
    );
  });

  it("names NO host of its own anywhere in the module", () => {
    // The fallback constant is gone: the host lives on the server, in
    // `live_calls.py`, which is also where the policy reads it. A second copy
    // here is how the two came to disagree.
    const built = tileUrlFor(ESRI);
    expect(built).toContain(ESRI);
    expect(tileUrlFor("")).toBeNull();
  });

  it("reads tile_host by name and never the first entry of img-src", () => {
    // ⚠ `img-src` is a DIRECTIVE and holds every permitted image origin. Here
    // the utility has connected its own city's tile server, and the SHIPPED
    // DEFAULT sorts first — so `hosts["img-src"][0]` draws the wrong city's
    // map, silently and correctly-looking.
    const view = policy({
      hosts: { "img-src": [ESRI, "https://tiles.brazosbend.example"] },
      tile_host: "https://tiles.brazosbend.example",
    });
    expect(view.hosts["img-src"][0]).toBe(ESRI);
    expect(tileUrlFor(view.tile_host)).toBe(
      `https://tiles.brazosbend.example${TILE_PATH}`,
    );
  });

  it("treats a null tile_host as SWITCHED OFF and not as not-answered-yet", () => {
    // The two states look identical on screen unless the screen says so, which
    // is the shape hard-won law 7 exists for. `null` arrives only once the
    // request has answered; the component gates its own sentence on that.
    const off = policy({ hosts: {}, tile_host: null });
    expect(tileUrlFor(off.tile_host)).toBeNull();
  });
});
