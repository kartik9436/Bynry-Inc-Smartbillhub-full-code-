// ── Trace ────────────────────────────────────────────────────────────────
// Change:   CR-068 §9 · §11d — the portal's own screen register
// Rules:    every portal route has a CWP row and every row a route (G82's
//           rule, asserted here in the language the routes are written in)
// ─────────────────────────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import { PORTAL_ROUTES } from "./portalRoutes";
import { PORTAL_SCREENS, resolvePortalScreen } from "./screenIds";

describe("the portal's screen register is the portal's own route table", () => {
  it("covers every portal route, with nothing extra", () => {
    expect(PORTAL_SCREENS.map((row) => row.path)).toEqual(PORTAL_ROUTES.map((route) => route.path));
  });

  it("carries only CWP ids, each once, zero-padded to three as CR-068 §9 spells them", () => {
    const ids = PORTAL_SCREENS.map((row) => row.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) expect(id).toMatch(/^CWP-\d{3}$/);
  });

  it("resolves the front page from the bare portal root and from a trailing slash", () => {
    expect(resolvePortalScreen("/")?.id).toBe("CWP-001");
    expect(resolvePortalScreen("")?.id).toBe("CWP-001");
    expect(resolvePortalScreen("/nowhere")).toBeNull();
  });
});
