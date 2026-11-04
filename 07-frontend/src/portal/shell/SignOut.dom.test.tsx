// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-020 (EP-CWP-05) — getting in, and getting back out.
//           Screens: CWP-022 and every signed-in screen after it
// Defect:   DEF-CWP-4359 — a customer who signed in to the portal could not
//           sign out. `POST portal/auth/sign-out` was served and
//           `portalClient.signOut()` was exported, and NOTHING under
//           `src/portal/` imported it, so a session ended only when the
//           cookie expired. On a library or service-counter machine the next
//           person got the previous customer's bills, address and payment
//           history. Reported by the Product Owner on the running product,
//           2026-09-07: *"we dont have sign out in Customer portal"*.
//           ⚠ Filed first against the number 4357; `DEF-PAY-4357` had already
//           taken it on the remote (`1ff13a82`) while the portal row sat
//           unpushed in a tree two commits behind — law 11's `DEF-1787`
//           mechanism. Renumbered against the pushed world.
// Rules:    BR-CWP-104 (the session ends on the SERVER, and the customer
//           lands on THIS utility's own portal front door) · BR-CWP-004 (the
//           staff sign-in page is a different credential store, which is why
//           it is not the destination) · B14 rule 36 (the kit is how you
//           comply — `NavActionWord`)
// Cases:    the control CALLS the route · it lands on `CWP-015` BY ADDRESS ·
//           the address is the one the screen register holds · it leaves even
//           when the server refuses · nothing the customer was reading
//           survives on the machine
//
// ⚠ **THIS FILE IS THE CHECK THAT FIRES IF THE CONTROL EVER DISAPPEARS
// AGAIN**, and it asserts the two things a `toContain("Sign out")` cannot:
// WHAT IT CALLS and WHERE IT LANDS. A button that exists and posts nothing is
// the defect wearing a label.
//
// ⚠ **MOUNTED UNDER THE REAL `/:tenant/portal` PATH PATTERN** (`DEF-CWP-3925`).
// `usePortalPath` reads the tenant off `useParams`; a shell mounted bare in a
// `MemoryRouter` builds every address as `//portal/…` — a protocol-relative
// URL to another host, which reads as a perfectly good string to `toContain`.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalAccount } from "../api/portalClient";
import type { PortalFront } from "../api/guestClient";
import { PORTAL_SCREENS } from "../routing/screenIds";

// A plain recorder rather than a bare `vi.fn()` so the behaviour can be
// swapped per case — the shape `MyDetails.dom.test.tsx` already uses here.
let signOutCalls = 0;
let signOutBehaviour: () => Promise<{ ok: boolean }> = async () => {
  signOutCalls += 1;
  return { ok: true };
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, signOut: () => signOutBehaviour() };
});

const { PortalShell, SIGN_OUT_SCREEN_ID, signOutRoute } = await import("./PortalShell");

const FRONT: PortalFront = {
  tenant: {
    slug: "pine-hill",
    name: "Pine Hill Water & Power",
    brand_primary_hex: "#EC3013",
    brand_accent_hex: null,
  },
  is_live: true,
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

const ACCOUNT: PortalAccount = {
  id: "acc-1",
  account_no: "ACC-10432-A",
  label: "1408 Elm St · A",
  permissions: ["see", "download", "pay"],
  source: "holder",
  is_master: false,
};

/** Where the router actually is, printed so a case can read it. */
function WhereAmI() {
  const { pathname } = useLocation();
  return <output data-where="">{pathname}</output>;
}

function mount(client: QueryClient) {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/pine-hill/portal/home"]}>
        <WhereAmI />
        <Routes>
          {/* The signed-out surface is a REAL route here, so a landing can be
              asserted by address instead of by intent. */}
          <Route path="/pine-hill/portal/sign-in" element={<p>front door</p>} />
          <Route
            path="/:tenant/portal/*"
            element={
              <PortalShell
                front={FRONT}
                displayName="Maria Alvarez"
                accounts={[ACCOUNT]}
                currentAccountId={ACCOUNT.id}
                onAccountChange={() => undefined}
              >
                <p>body</p>
              </PortalShell>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function signOutControl() {
  const control = document.querySelector('[data-action="sign_out"]');
  if (!(control instanceof HTMLButtonElement)) {
    throw new Error("no sign-out control in the portal shell — DEF-CWP-4359");
  }
  return control;
}

afterEach(() => {
  cleanup();
  signOutCalls = 0;
  signOutBehaviour = async () => {
    signOutCalls += 1;
    return { ok: true };
  };
});

describe("DEF-CWP-4359 · the customer portal has a way out", () => {
  it("the shell offers a sign-out that CALLS the route — not a button that only navigates", async () => {
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    mount(client);
    await userEvent.click(signOutControl());
    // The session ends on the SERVER. A handler that only cleared the browser
    // would leave a live session behind on a shared machine, which is the
    // whole of this defect.
    await waitFor(() => expect(signOutCalls).toBe(1));
  });

  it("lands on this utility's own portal front door, BY ADDRESS", async () => {
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    mount(client);
    await userEvent.click(signOutControl());
    await waitFor(() =>
      expect(screen.getByText("/pine-hill/portal/sign-in")).toBeInTheDocument(),
    );
    // …and the tenant is still in it. `DEF-037` is the staff app landing on
    // the bare public host and dropping the tenant on every sign-out.
    const where = document.querySelector("[data-where]")?.textContent ?? "";
    expect(where.startsWith("/pine-hill/portal/")).toBe(true);
    expect(where.startsWith("//")).toBe(false);
  });

  it("that address is the one the screen register holds for CWP-015", () => {
    // The destination is read from the register rather than typed, so the day
    // the front door moves the control follows it. This case is what stops
    // `signOutRoute()`'s fallback shipping unnoticed.
    const row = PORTAL_SCREENS.find((screen) => screen.id === SIGN_OUT_SCREEN_ID);
    expect(row).toBeDefined();
    expect(row?.path).toBe("/sign-in");
    expect(signOutRoute()).toBe("/sign-in");
  });

  it("leaves even when the server refuses — the customer asked to go", async () => {
    signOutBehaviour = async () => {
      signOutCalls += 1;
      throw new Error("network");
    };
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    mount(client);
    await userEvent.click(signOutControl());
    await waitFor(() =>
      expect(screen.getByText("/pine-hill/portal/sign-in")).toBeInTheDocument(),
    );
    expect(signOutCalls).toBe(1);
  });

  it("nothing the customer was reading is left in the machine", async () => {
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    client.setQueryData(["portal", "session"], { customer: { display_name: "Maria Alvarez" } });
    mount(client);
    await userEvent.click(signOutControl());
    await waitFor(() => expect(client.getQueryData(["portal", "session"])).toBeUndefined());
  });
});
