// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Defect:   DEF-CWP-3994 — the tenant's date format and time zone reached the
//           staff app and not the portal.
// Rules:    IS-8 · BR-SHL-023 · hard-won law 3 (defaults fail closed) ·
//           hard-won law 2 (built is not wired)
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **WHY EVERY CASE HERE MOUNTS A REAL FRAME AND CHANGES THE SERVED VALUE.**
// `DEF-SHL-3964` was green everywhere and shipped broken. The provider existed,
// the context existed, 160 call sites were correctly de-prop-drilled, and every
// test passed — because each one SUPPLIED the context it then asserted was
// read. That proves a component consumes a context; it cannot prove the running
// app ever puts one there, and the running app did not: the portal is the
// provider's SIBLING in the route tree.
//
// So no case below wraps anything in `TenantRegionalProvider` by hand. Each
// renders `PortalShell` or `GuestFrame` — the components the real app renders —
// hands them a front payload, and asserts on what comes out. The format is then
// CHANGED and the same date re-read, because a single read cannot tell a served
// setting from a hardcoded string, and a hardcoded string was the whole defect.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { useTenantRegional } from "@/components/TenantRegional";

import type { PortalFront } from "../api/guestClient";
import { GuestFrame } from "../shell/GuestFrame";
import { PortalShell } from "../shell/PortalShell";
import { usePortalDate } from "./regional";

afterEach(cleanup);

const FRONT = (
  timezone: string | null,
  dateFormat: string | null,
  isLive = true,
): PortalFront => ({
  tenant: {
    slug: "pine-hill",
    name: "Pine Hill Water",
    brand_primary_hex: null,
    brand_accent_hex: null,
  },
  is_live: isLive,
  regional: { timezone, date_format: dateFormat, language: null },
  // `PORTAL_LOCALES` — the two the portal OFFERS (`BR-CWP-106`).
  locales: ["en", "es"],
  cards: [],
  links: { help: false, visit: false },
  services: [],
  strapline: null,
  office_hours_text: null,
  emergency_phone: null,
});

/** A child that renders one date through the hook every screen uses. */
function ShowsADate(props: { value?: string; withTime?: boolean }) {
  const asDate = usePortalDate();
  return <span data-probe="">{asDate(props.value ?? "2026-08-25", props.withTime)}</span>;
}

/** A child that reports whether a context was published AT ALL. */
function ReportsTheContext() {
  const regional = useTenantRegional();
  return <span data-context="">{regional === null ? "none" : regional.dateFormat}</span>;
}

function inShell(front: PortalFront, child: React.ReactNode) {
  // ⚠ **AND INSIDE A `QueryClientProvider`** — the shell's *Sign out*
  // (`DEF-CWP-4359`) clears the cache when it leaves.
  return render(
    <QueryClientProvider client={new QueryClient()}>
    <MemoryRouter initialEntries={["/pine-hill/portal/bills"]}>
      <Routes>
        <Route
          path="/:tenant/portal/bills"
          element={
            <PortalShell
              front={front}
              displayName="A Customer"
              accounts={[]}
              currentAccountId={null}
              onAccountChange={() => undefined}
            >
              {child}
            </PortalShell>
          }
        />
      </Routes>
    </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("the tenant's date format reaches the portal (DEF-CWP-3994)", () => {
  it("the SIGNED-IN frame publishes it — nothing here supplies a context", () => {
    // This is the assertion the original defect would have failed. The frame is
    // the real one; if it did not wrap its children, this reads "none".
    inShell(FRONT("America/Chicago", "DD-MMM-YY"), <ReportsTheContext />);
    expect(screen.getByText("DD-MMM-YY")).toBeInTheDocument();
  });

  it("the GUEST frame publishes it too — a receipt carries a date as well", () => {
    render(
      <MemoryRouter initialEntries={["/pine-hill/portal/pay"]}>
        <Routes>
          <Route
            path="/:tenant/portal/pay"
            element={
              <GuestFrame front={FRONT("Europe/Berlin", "DD.MM.YYYY")}>
                <ReportsTheContext />
              </GuestFrame>
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("DD.MM.YYYY")).toBeInTheDocument();
  });

  it("a date renders in the tenant's own format, not as an ISO string", () => {
    inShell(FRONT("America/Chicago", "DD-MMM-YY"), <ShowsADate />);
    const shown = document.querySelector("[data-probe]")?.textContent;
    expect(shown).toBe("25-Aug-26");
    expect(shown).not.toBe("2026-08-25");
  });

  it("CHANGING THE SETTING CHANGES THE DATE — the PO's own sentence", () => {
    // *"date and time format is set in the settings … but date shown everywhere
    // in the product does not change with that format change."* One payload,
    // then another, and the same date reads differently. A hardcoded format
    // passes the case above and fails this one, which is why both exist.
    const first = inShell(FRONT("America/Chicago", "DD-MMM-YY"), <ShowsADate />);
    expect(document.querySelector("[data-probe]")?.textContent).toBe("25-Aug-26");
    first.unmount();

    inShell(FRONT("America/Chicago", "DD/MM/YYYY"), <ShowsADate />);
    expect(document.querySelector("[data-probe]")?.textContent).toBe("25/08/2026");
  });

  it("the TIME ZONE moves an instant, which is the other half of IS-8", () => {
    // A payment taken at 01:30 UTC is the previous evening in Chicago. This is
    // the half that made a 7pm payment show as the next day.
    inShell(
      FRONT("America/Chicago", "YYYY-MM-DD"),
      <ShowsADate value="2026-08-26T01:30:00Z" withTime />,
    );
    expect(document.querySelector("[data-probe]")?.textContent).toBe("2026-08-25 20:30");
  });

  it("an UNSET format publishes nothing and states no format of its own", () => {
    // hard-won law 3. The wrong answer here is the defect: a plausible default
    // renders every date confidently and wrongly, with nothing to notice.
    inShell(FRONT(null, null), <ReportsTheContext />);
    expect(screen.getByText("none")).toBeInTheDocument();
  });

  it("a format this build cannot draw is treated as unset, never as itself", () => {
    // `tenant_settings.date_format` is a bare TEXT column, so the server can
    // hold a string that is not one of the seven. The shared mapper is what
    // decides that, and reusing it is why the portal cannot disagree with the
    // staff app about which formats are drawable.
    inShell(FRONT("America/Chicago", "SWAHILI/LONG"), <ReportsTheContext />);
    expect(screen.getByText("none")).toBeInTheDocument();
  });

  it("with nothing published, the server's own string is handed back unchanged", () => {
    // Declining to state a format is honest. Inventing MM/DD/YYYY for a utility
    // in Berlin is what shipped a five-hour error to a Texas customer.
    inShell(FRONT(null, null), <ShowsADate />);
    expect(document.querySelector("[data-probe]")?.textContent).toBe("2026-08-25");
  });
});
