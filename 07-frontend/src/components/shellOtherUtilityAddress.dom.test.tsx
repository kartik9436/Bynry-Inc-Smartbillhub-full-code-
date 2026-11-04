// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-9241 (2026-10-03, New Connection end-to-end walk stage 14b)
//          — signed in to one utility, opening ANOTHER utility's address drew
//          "We couldn't load your regional settings." with a Retry that could
//          never succeed: every tenant-scoped route answers 404 to a
//          non-member (HR-1), the shell's boot read among them.
// Rules:   HR-1 (a non-member learns nothing a 404 does not say) · BR-SHL-009
//          (a tenant's own sign-in page is `/{tenant}/signin`) · law 6
//          (assert the ROUTED result, through the real routes).
// ───────────────────────────────────────────────────────
// WHAT WOULD MAKE THIS PASS WRONGLY: a shell that sent EVERY failure to the
// sign-in page — so the second case keeps a 500 on the Retry screen. And a
// stub the client never calls: the default client captures `fetch` when it is
// created, so the boot read is mocked at its endpoint instead.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { APP_ROUTES } from "@/App";
import { ApiError } from "@/api/client";
import type { SessionUser } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

const TENANT = "lakeside";

const display = vi.hoisted(() => ({ status: 404 }));
vi.mock("@/api/endpoints", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/endpoints")>()),
  getShellDisplay: async () => {
    throw new ApiError(display.status, { code: null, message_key: "errors.not-found" });
  },
}));

const OTHER_UTILITYS_CLERK: SessionUser = {
  id: "u9",
  full_name: "Dana Whitfield",
  email: "dana@brazosbend.example",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

afterEach(cleanup);

function openWith(displayStatus: number) {
  display.status = displayStatus;
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, OTHER_UTILITYS_CLERK);
  const router = createMemoryRouter(APP_ROUTES, { initialEntries: [`/${TENANT}/dashboard`] });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return router;
}

describe("DEF-SHL-9241 — another utility's address while signed in elsewhere", () => {
  it("a 404 on the shell's boot read goes to THIS utility's sign-in, not a dead Retry", async () => {
    const router = openWith(404);
    await waitFor(() => expect(router.state.location.pathname).toBe(`/${TENANT}/signin`));
    expect(document.body.textContent).not.toContain("We couldn't load your regional settings.");
  });

  it("any other failure keeps the Retry — only the non-member answer moves the page", async () => {
    const router = openWith(500);
    await waitFor(() =>
      expect(document.body.textContent).toContain("We couldn't load your regional settings."),
    );
    expect(router.state.location.pathname).toBe(`/${TENANT}/dashboard`);
  });
});
