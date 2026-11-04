// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CWP-10545 (portal a11y F-09, brand half)
// Rules:    decision log 2026-10-23 — Group A ruling 3(a); inventory
//           08-qa/a11y-portal-2026-10/group-a-inventory.md §6.2 (1)
// ───────────────────────────────────────────────────────
/**
 * The sign-in wall a signed-out visitor meets on every account page is drawn
 * inside `[data-portal]` but OUTSIDE both frames, so it never received the
 * corrected ink or the utility's colour. The root now carries both.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { queryKeys } from "@/api/queryClient";

import { PortalApp, usePortalRootStyle } from "./PortalApp";

function Probe() {
  return createElement("div", { "data-probe": "", style: usePortalRootStyle() });
}

function render(node: React.ReactElement, hex?: string | null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (hex !== undefined) client.setQueryData(queryKeys.portalFront, { tenant: { brand_primary_hex: hex }, regional: { language: "en" } });
  return renderToStaticMarkup(createElement(QueryClientProvider, { client }, node));
}

describe("Group A 3(a) · the portal root writes the ink the sign-in wall uses", () => {
  it("before the front page is known: our accent's inks (black at rest)", () => {
    const html = render(createElement(Probe));
    expect(html).toContain("--color-on-accent:#000000");
    expect(html).toContain("--color-on-accent-600:#FFFFFF");
    expect(html).not.toContain("--color-accent:");
  });

  it("with the utility's colour: that colour and ITS ink", () => {
    const html = render(createElement(Probe), "#1D3557");
    expect(html).toContain("--color-accent:#1D3557");
    expect(html).toContain("--color-on-accent:#FFFFFF");
  });

  it("the [data-portal] root itself carries it, so a frameless state inherits it", () => {
    const html = render(
      createElement(MemoryRouter, { initialEntries: ["/brazosbend/portal/bills"] }, createElement(PortalApp)),
      "#EC3013",
    );
    const root = /<div data-portal=""[^>]*>/.exec(html)?.[0] ?? "";
    expect(root).toContain("--color-accent:#EC3013");
    expect(root).toContain("--color-on-accent:#000000");
  });
});
