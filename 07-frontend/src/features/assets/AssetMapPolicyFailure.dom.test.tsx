// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-AST-5201 — a crashed page-policy call and a switched-off basemap
//          drew the same grey square and printed the same sentence
// Rules:   B14 rule 32 (one short sentence, only in the state it describes) ·
//          CLAUDE.md hard-won law 1 (a comment claiming a guarantee is not the
//          guarantee) · law 7 (a check that does not check)
// Tests:   this file
// Impacts: 07-frontend/src/features/assets/AssetMapTab.tsx — basemapState
// ───────────────────────────────────────────────────────
//
// **WHY THIS FILE EXISTS.** `AssetMapTiles.test.tsx` covers `tileUrlFor` and
// every other `AssetMapTab` test supplies a page policy that RESOLVES. So the
// branch that chooses the WORDS was covered by nothing, and the screen reported
// a server error to a clerk as *"Background map is switched off."* — a choice
// their own utility had supposedly made.
//
// The Product Owner met it on the deployed build on 2026-09-13: opening
// `GET /integrations/page-policy` for their tenant returned **Server Error
// (500)** while the asset map drew markers on bare grey. On this branch that
// endpoint answers 200 unauthenticated, 200 authenticated and 404 for an unknown
// tenant, so the crash is that deployment's — the misreporting was ours.
//
// ⚠ **THE FILE ALREADY WARNED ABOUT THIS IN A COMMENT** three lines above the
// render: *"A tenant who switched the map service off and a product whose tiles
// are being refused draw the identical grey square."* Warning about two states
// is not separating them — hard-won law 1.
//
// ⚠ **WHY THIS TESTS A PURE FUNCTION AND NOT THE RENDER.** `AssetMapTab` cannot
// be mounted under jsdom: Leaflet needs a real DOM and throws on `_removePath`
// during cleanup. That is precisely why the fault survived — the only reachable
// half was the half that did not decide the words. `basemapState` is now that
// decision, in a form a test can hold.
import { describe, expect, it } from "vitest";

import { basemapState } from "@/features/integrations/basemap";

const HOST = "https://server.arcgisonline.com";

describe("DEF-AST-5201 · a failed policy read is not a switched-off basemap", () => {
  it("a FAILED policy read is 'unavailable', never 'off'", () => {
    const state = basemapState({ host: undefined, answered: true, failed: true });
    expect(state.kind).toBe("unavailable");
    // The half that was the defect: it must not read as the utility's choice.
    expect(state.kind).not.toBe("off");
  });

  it("a policy that ANSWERED with no host is 'off' — the utility's own choice", () => {
    expect(basemapState({ host: null, answered: true, failed: false }).kind).toBe("off");
    expect(basemapState({ host: "", answered: true, failed: false }).kind).toBe("off");
    expect(basemapState({ host: "   ", answered: true, failed: false }).kind).toBe("off");
  });

  it("a permitted host draws, and carries the template the layer needs", () => {
    const state = basemapState({ host: HOST, answered: true, failed: false });
    expect(state.kind).toBe("drawing");
    if (state.kind === "drawing") {
      expect(state.tileUrl.startsWith(HOST)).toBe(true);
      expect(state.tileUrl).toContain("{z}");
    }
  });

  it("NOT YET is not OFF — the first render must not flash the sentence", () => {
    expect(basemapState({ host: undefined, answered: false, failed: false }).kind).toBe("pending");
  });

  it("a failure outranks an unanswered read, so a 500 never reads as pending", () => {
    // `isError` and `data === undefined` are both true on a rejected query, and
    // the order of these two tests is the difference between saying something
    // true and saying nothing at all.
    expect(basemapState({ host: undefined, answered: false, failed: true }).kind).toBe("unavailable");
  });
});
