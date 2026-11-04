// ── Trace ────────────────────────────────────────────────────────────────
// Defect:   DEF-CWP-3987 (layout audit `D12`) — every signed-in screen that
//           has a rail shows a WHITE main column beside a GREY rail, because
//           the portal's `Card` writes `bg-[white]` and the shared `Panel`
//           writes `bg-surface`, which is the STAFF app's token (`#eae9e9`).
//           `09-component-inventory.md` §0 row *Surface* says the portal's
//           surface is `bg-[white]`, for "cards, panels" — both.
// Rules:    09-component-inventory.md §0 (Surface → `bg-[white]`, cards AND
//           panels) · B14 rule 36 (compose the kit; do not fork a component
//           to recolour it) · DEF-CWP-3736's mechanism, one token over: the
//           portal moves a VARIABLE on its own frame rather than rewriting
//           the utilities the shared kit already writes
// Cases:    the two frames declare the override · the shared Panel still
//           reads the token (so the override is what colours it)
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **THIS IS A TOKEN TEST, AND IT IS DELIBERATELY IN TWO HALVES.** Asserting
// only that the frame writes `--color-surface` would keep passing on the day
// somebody "fixes" `Panel` to `bg-[white]` and the staff app goes white with
// it; asserting only that `Panel` writes `bg-surface` would keep passing on
// the day the override is dropped and the rail goes grey again. The pair is
// the claim: *the portal's panels are white BECAUSE the portal moves the
// token* — and either half going missing is the defect returning.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { Panel } from "@/components/Panel";
import type { PortalFront } from "../api/guestClient";
import type { PortalAccount } from "../api/portalClient";
import { GuestFrame, PORTAL_SURFACE, portalFrameStyle } from "./GuestFrame";
import { PortalShell } from "./PortalShell";

function front(hex: string | null = "#EC3013"): PortalFront {
  return {
    tenant: { slug: "pine-hill", name: "Pine Hill Water & Power", brand_primary_hex: hex, brand_accent_hex: null },
    is_live: true,
    // `DEF-CWP-3994` — the tenant's Regional settings ride on the front
    // payload, and the type makes them REQUIRED so a fixture cannot
    // quietly omit them and hide the wire being absent.
    regional: { timezone: "America/Chicago", date_format: "DD-MMM-YY", language: null },
    // `PORTAL_LOCALES` — the two the portal OFFERS (`BR-CWP-106`).
    locales: ["en", "es"],
    cards: [],
    links: { help: false, visit: false },
    services: [],
    strapline: null,
    office_hours_text: null,
    emergency_phone: null,
  };
}

const ACCOUNT: PortalAccount = {
  id: "a1",
  account_no: "ACC-a1",
  label: "1408 Elm St · A",
  permissions: ["see", "download", "pay"],
  source: "holder",
  is_master: false,
};

/** ⚠ Under the REAL `/:tenant/portal` pattern — a bare `MemoryRouter` leaves
 *  `useParams().tenant` undefined and every address comes out `//portal/…`,
 *  which `toContain` accepts (hard-won law 2's fixture clause). */
function under(node: React.ReactNode): string {
  // ⚠ **AND INSIDE A `QueryClientProvider`** — the shell's *Sign out*
  // (`DEF-CWP-4359`) clears the cache when it leaves, so the frame now reads a
  // query client the way every screen inside it already does.
  return renderToStaticMarkup(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/pine-hill/portal/home"]}>
        <Routes>
          <Route path="/:tenant/portal/*" element={node} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("the portal's surface token (DEF-CWP-3987)", () => {
  it("is white on the signed-in frame, beside the accent it already overrides", () => {
    const html = under(
      <PortalShell
        front={front()}
        displayName="Maria Alvarez"
        accounts={[ACCOUNT]}
        currentAccountId="a1"
        onAccountChange={() => {}}
      >
        <p>body</p>
      </PortalShell>,
    );
    expect(html).toContain(`--color-surface:${PORTAL_SURFACE}`);
  });

  it("is white on the guest frame too, so the two halves cannot drift apart", () => {
    const html = under(
      <GuestFrame front={front()}>
        <p>body</p>
      </GuestFrame>,
    );
    expect(html).toContain(`--color-surface:${PORTAL_SURFACE}`);
  });

  it("is written even by a utility that has chosen no colour of its own", () => {
    // The surface is OURS, not the tenant's: `brandStyle` writes nothing when
    // there is no hex, and a rail that went grey only for unbranded utilities
    // would be the same defect with a smaller blast radius.
    expect(portalFrameStyle(front(null).tenant)).toMatchObject({
      "--color-surface": PORTAL_SURFACE,
    });
    expect(portalFrameStyle(front(null).tenant)).not.toHaveProperty("--color-accent");
  });

  it("still reaches the shared Panel through the token, not through a fork", () => {
    // If this half fails, `Panel` stopped reading the variable and the
    // override above is decorating nothing — see the note at the top.
    const html = renderToStaticMarkup(<Panel title="Your service">x</Panel>);
    expect(html).toContain("bg-surface");
  });
});
