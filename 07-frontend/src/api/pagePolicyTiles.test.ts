// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-INT-7430 — the page's baked-in Content-Security-Policy named no
//          basemap tile host, so the Work map and the Assets map were refused
//          every tile on every build. Option (a), decision log 2026-10-04
//          ("THE WORK MAP SHOWS AN ESRI STREET MAP" — the Esri egress is an
//          ACCEPTED exposure): the baked policy allows the DEFAULT Esri tile
//          origin and nothing broader.
// Rules:   hard-won law 5 (the host has one home on the server —
//          `live_calls.ESRI_TILE_HOST` — so this test checks the front end's
//          copy against it) · law 7 (the test drives the REAL Vite plugin
//          (`deployConfig.pagePolicyPlugin`, which `vite.config.ts`
//          registers) — the code that writes the tag into `dist/index.html`).
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-expect-error — a plain .mjs build-config module with no .d.ts by design.
import { pagePolicyPlugin } from "../../scripts/deployConfig.mjs";

// Node's fs, reached the way `src/components/buttonKit.test.ts` does: `tsc`
// carries no @types/node for `src/`, so a bare `node:fs` import fails it.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: URL, enc: string): string;
};

const ESRI = "https://server.arcgisonline.com";

/** The policy exactly as the build writes it into index.html, for an API origin. */
async function bakedPolicy(apiBase: string): Promise<string> {
  const plugin = pagePolicyPlugin(apiBase) as {
    name: string;
    transformIndexHtml(html: string): Promise<string>;
  };
  expect(plugin.name).toBe("smartbillhub-page-policy");
  const html = await plugin.transformIndexHtml('<head>\n    <meta charset="UTF-8" />\n</head>');
  const content = html.match(/http-equiv="Content-Security-Policy" content="([^"]+)"/);
  expect(content, "the built document carries a CSP meta tag").not.toBeNull();
  return content![1];
}

const directive = (policy: string, name: string) =>
  policy.split("; ").find((one) => one.startsWith(`${name} `)) ?? "";

describe("DEF-INT-7430 — the baked policy lets the default basemap tiles in", () => {
  it("the front end's tile origin is the server's ESRI_TILE_HOST, not a second opinion", () => {
    const liveCalls = nodeFs.readFileSync(
      new URL("../../../06-backend/apps/integrations/live_calls.py", import.meta.url),
      "utf8",
    );
    expect(liveCalls).toMatch(new RegExp(`^ESRI_TILE_HOST = "${ESRI.replace(/[./]/g, "\\$&")}"$`, "m"));
  });

  for (const [mode, api] of [
    ["wolocal", ""],
    ["production", "https://api-smart360.bynry.com"],
  ] as const) {
    it(`img-src names the Esri tile origin (${mode} build)`, async () => {
      const policy = await bakedPolicy(api);
      expect(directive(policy, "img-src").split(" ")).toContain(ESRI);
    });

    it(`adds no wildcard, no bare scheme and no other host (${mode} build)`, async () => {
      const policy = await bakedPolicy(api);
      expect(policy).not.toContain("*");
      const img = directive(policy, "img-src").split(" ").slice(1);
      expect(img).not.toContain("https:");
      expect(img).not.toContain("http:");
      const expected = ["'self'", "data:", "blob:", ...(api ? [api] : []), ESRI];
      expect([...img].sort()).toEqual([...expected].sort());
      // The tile origin widens img-src ONLY.
      for (const other of ["default-src", "connect-src", "frame-src", "object-src", "script-src"]) {
        expect(directive(policy, other)).not.toContain("arcgisonline");
      }
    });
  }
});
