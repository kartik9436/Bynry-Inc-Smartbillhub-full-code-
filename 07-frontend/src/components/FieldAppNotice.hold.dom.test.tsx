// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-187-BRC10 T-55 — the HOLD on repointing "Open the field app" at
//          the app stores until the native field app ships (decision log
//          2026-10-21, twelve conflicts, #9).
// Rules:   hard-won law 2 — "WHEN YOU WRITE A HOLD, WRITE THE TEST THAT FIRES
//          WHEN THE HOLD EXPIRES, in the same commit — assert the destination
//          by ADDRESS" · law 6 (through the real routes, never mounted bare).
// ───────────────────────────────────────────────────────
// WHAT THIS HOLDS: today the button goes to the WEB field app's sign-in, and
// both store addresses are empty. The day somebody writes a store address into
// `fieldAppStores.ts`, the first test goes red and names the rest of the job —
// so a URL can never be filled in while the button still points at the web app.
//
// WHAT WOULD MAKE THIS PASS WRONGLY: asserting the component's `href` PROP in a
// bare mount. The shell builds the address with the tenant, so this mounts the
// real routes at a real tenant and reads the rendered link.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { APP_ROUTES } from "@/App";
import { ApiError } from "@/api/client";
import type { SessionUser } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { FIELD_APP_STORE_URLS } from "@/features/identity/fieldAppStores";

const TENANT = "entranosa-water-association";
const OPEN = "Open the field app";

vi.mock("@/api/endpoints", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/endpoints")>()),
  getShellDisplay: async () => {
    throw new ApiError(403, { code: null, message_key: "errors.auth.permission_denied" });
  },
  signOut: async () => undefined,
}));

const TECHNICIAN: SessionUser = {
  id: "u7",
  full_name: "Tomas Field",
  email: "tomas@entranosa.example",
  phone: null,
  role: "field_technician",
  role_name: "Field technician",
  must_change_password: false,
};

afterEach(cleanup);

describe("T-55 HOLD — 'Open the field app' points at the web field app until the native app ships", () => {
  it("the store addresses are still empty (this goes red the day the native app ships)", () => {
    expect(
      FIELD_APP_STORE_URLS,
      "A STORE ADDRESS HAS BEEN SET — the T-55 hold has expired. Now: (1) point " +
        "FieldAppNotice's button (components/FieldAppNotice.tsx, used by SignInPage.tsx " +
        "and ShellWithSession.tsx) at FIELD_APP_STORE_URLS for the visitor's platform; " +
        "(2) decide the web field app's door per T-72 (retire, or keep as the fallback); " +
        "(3) change the expected destination in the test below and delete this assertion.",
    ).toEqual({ appStore: "", googlePlay: "" });
  });

  it("the routed button's destination is the web field app's sign-in, by address", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity } },
    });
    queryClient.setQueryData(queryKeys.me, TECHNICIAN);
    const router = createMemoryRouter(APP_ROUTES, { initialEntries: [`/${TENANT}/dashboard`] });
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </QueryClientProvider>,
    );
    const go = await screen.findByRole("link", { name: OPEN });
    expect(go).toHaveAttribute("href", `/${TENANT}/work/mobile/signin`);
    expect(go.getAttribute("href")).not.toMatch(/apps\.apple\.com|play\.google\.com/);
  });
});
