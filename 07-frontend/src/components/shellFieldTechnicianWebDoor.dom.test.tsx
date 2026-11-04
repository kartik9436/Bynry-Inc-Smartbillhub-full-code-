// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-IDN-9748 (2026-10-05, customer on sandbox) — a Field
//          Technician signed in to the STAFF web app and the shell's boot read
//          (`GET /shell/display`, office roles only) answered 403, which drew
//          "We couldn't load your regional settings." with a Retry that could
//          never succeed.
// Rules:   BR-WRK-043 / OQ-WRK-1494 (PO 2026-09-04: "Field technicians will
//          not logn to web app; they will login to mobile app only") · B14
//          rule 33 as excepted by the PO for this one message (2026-10-06,
//          DEF-IDN-9777: two sentences + "Open the field app") · law 6 (assert
//          the ROUTED result, through the real routes).
// ───────────────────────────────────────────────────────
// WHAT WOULD MAKE THIS PASS WRONGLY: a shell that drew the field-app sentence
// for EVERY failure — so a 500 keeps the Retry, and a 403 that means "change
// your temporary password first" is not read as the wrong door.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { APP_ROUTES } from "@/App";
import { ApiError } from "@/api/client";
import type { SessionUser } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

const TENANT = "entranosa-water-association";
const FAILED = "We couldn't load your regional settings.";
// DEF-IDN-9777 — the PO's two sentences, verbatim (2026-10-06).
const WRONG_DOOR = "Field Technicians do not have access to the staff portal.";
const WRONG_DOOR_NEXT = "Please sign in on the Field Technician mobile app instead.";
const OPEN = "Open the field app";

const boot = vi.hoisted(() => ({ status: 403, key: "errors.auth.permission_denied", signedOut: 0 }));
vi.mock("@/api/endpoints", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/endpoints")>()),
  getShellDisplay: async () => {
    throw new ApiError(boot.status, { code: null, message_key: boot.key });
  },
  signOut: async () => {
    boot.signedOut += 1;
  },
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

function openWith(status: number, key = "errors.auth.permission_denied") {
  boot.status = status;
  boot.key = key;
  boot.signedOut = 0;
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
  return router;
}

describe("DEF-IDN-9748 — a field technician at the staff web app's door", () => {
  it("a 403 on the boot read shows the PO's two sentences as a centred notice, and no Retry", async () => {
    openWith(403);
    const heading = await screen.findByRole("heading", { name: WRONG_DOOR });
    expect(screen.getByText(WRONG_DOOR_NEXT)).toBeInTheDocument();
    // A proper notice, not a bare line: the shared signed-out card.
    expect(heading.closest("[data-page='field-app-only']")).not.toBeNull();
    expect(screen.getAllByRole("link", { name: OPEN })).toHaveLength(1);
    expect(document.body.textContent).not.toContain(FAILED);
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });

  it("its one action signs the web session out and lands on the field app's sign-in", async () => {
    const router = openWith(403);
    const go = await screen.findByRole("link", { name: OPEN });
    expect(go).toHaveAttribute("href", `/${TENANT}/work/mobile/signin`);
    expect(go).toHaveAttribute("data-variant", "primary");
    fireEvent.click(go);
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/${TENANT}/work/mobile/signin`),
    );
    expect(boot.signedOut).toBe(1);
  });

  it("a 403 asking for a password change is NOT read as the wrong door", async () => {
    openWith(403, "errors.auth.password_change_required");
    await waitFor(() => expect(document.body.textContent).toContain(FAILED));
    expect(document.body.textContent).not.toContain(WRONG_DOOR);
  });

  it("a 500 keeps the Retry", async () => {
    openWith(500, "errors.unexpected");
    await waitFor(() => expect(document.body.textContent).toContain(FAILED));
    expect(document.body.textContent).not.toContain(WRONG_DOOR);
  });
});
