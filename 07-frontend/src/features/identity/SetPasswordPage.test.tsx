// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-188-BRC10 — staff invitation / reset emails carry a one-time
//          sign-in link (PO 2026-10-22)
// Rules:   BR-IDN-022 as amended 2026-10-05 (after the change the person signs
//          in again) · BR-IDN-002 (one refusal for every dead link)
// ───────────────────────────────────────────────────────
/**
 * Rendered through the app's OWN route table at a real `/:tenant` address
 * (hard-won law 2's fixture clause), with only `fetch` replaced by a stand-in
 * server that records what it was asked.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation, useRoutes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { APP_ROUTES } from "@/App";
import { ToastProvider } from "@/components/Toast";
import { SET_PASSWORD_ROUTE, SET_PASSWORD_TOKEN_PARAM } from "@/features/identity/SignInPage";
import i18n from "@/i18n";

const server = vi.hoisted(() => {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const state = { live: true };
  const json = (status: number, body: unknown) =>
    new Response(status === 204 ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  const dead = () =>
    json(409, {
      code: "BIZ-STATE",
      message_key: "errors.identity.password_link_not_accepted",
      br_ref: "BR-IDN-002",
    });
  const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();
    const path = url.replace(/^https?:\/\/[^/]+/, "").split("?")[0];
    const body = init?.body ? JSON.parse(String(init.body)) : null;
    calls.push({ method, path, body });
    if (path.endsWith("/auth/password-link/check")) {
      if (!state.live) return dead();
      return json(200, {
        email: "sam@brazosbend.example",
        purpose: "invite",
        utility_name: "Brazos Bend Water",
        expires_at: "2026-10-29T12:00:00Z",
        password_policy: { min_length: 8, require_mixed: true, require_symbol: false },
      });
    }
    if (path.endsWith("/auth/password-link/complete")) {
      if (!state.live) return dead();
      state.live = false;
      return json(204, null);
    }
    if (path.endsWith("/auth/sign-in-options")) {
      return json(200, { data: { keep_signed_in_offered: false } });
    }
    return json(404, { code: "not_found", message_key: "errors.not_found" });
  }) as typeof fetch;
  return { calls, state, fetchImpl };
});

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    api: actual.createApiClient({ fetchImpl: server.fetchImpl, tenant: "brazosbend" }),
  };
});

const TENANT = "brazosbend";

function RoutedApp() {
  return useRoutes(APP_ROUTES as never);
}
function WhereAmI() {
  const { pathname, search, hash } = useLocation();
  return <output data-testid="where">{`${pathname}${search}${hash}`}</output>;
}
function renderAt(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <RoutedApp />
          <WhereAmI />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}
const where = () => screen.getByTestId("where").textContent;
const page = (handle: string) => document.querySelector(`[data-page="${handle}"]`);
// The token travels in the FRAGMENT (decision log 2026-10-22, MERGE-ACCESS)…
const linkAddress = (token: string) =>
  `/${TENANT}${SET_PASSWORD_ROUTE}#${SET_PASSWORD_TOKEN_PARAM}=${token}`;
// …and a link emailed before that change carried it in the query.
const legacyLinkAddress = (token: string) =>
  `/${TENANT}${SET_PASSWORD_ROUTE}?${SET_PASSWORD_TOKEN_PARAM}=${token}`;

beforeEach(async () => {
  server.calls.length = 0;
  server.state.live = true;
  await i18n.changeLanguage("en");
});
afterEach(cleanup);

describe("CR-188-BRC10 · the set-password page an emailed link opens", () => {
  it("the address the server builds is the address the app mounts", () => {
    // `apps/identity/password_links.SET_PASSWORD_SEGMENT = "set-password"`,
    // `TOKEN_PARAM = "token"` — the two halves of one link.
    expect(SET_PASSWORD_ROUTE).toBe("/set-password");
    expect(SET_PASSWORD_TOKEN_PARAM).toBe("token");
  });

  it("checks the link, then sets the password and lands on sign-in with the one-time flag", async () => {
    renderAt(linkAddress("tok-123"));
    // The loading card carries the same heading, so wait for the CHECKED card.
    expect(await screen.findByText("For sam@brazosbend.example")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Set your password" })).toBeInTheDocument();
    expect(page("set-password")).not.toBeNull();
    expect(server.calls[0]).toMatchObject({
      method: "POST",
      path: `/api/${TENANT}/auth/password-link/check`,
      body: { token: "tok-123" },
    });
    fireEvent.change(screen.getByLabelText(/New password/), {
      target: { value: "Willow2026brook" },
    });
    fireEvent.change(screen.getByLabelText(/Confirm/), { target: { value: "Willow2026brook" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Set password" }));
    });
    const complete = server.calls.find((c) => c.path.endsWith("/auth/password-link/complete"));
    expect(complete?.body).toEqual({
      token: "tok-123",
      new_password: "Willow2026brook",
      confirm_password: "Willow2026brook",
    });
    expect(await screen.findByTestId("where")).toBeInTheDocument();
    expect(where()).toBe(`/${TENANT}/signin`);
    expect(page("signin")).not.toBeNull();
    expect(screen.getByText("Password changed. Sign in again.")).toBeInTheDocument();
  });

  it("reads the token from the fragment once and takes it off the address bar", async () => {
    renderAt(linkAddress("tok-123"));
    expect(await screen.findByText("For sam@brazosbend.example")).toBeInTheDocument();
    expect(where()).toBe(`/${TENANT}${SET_PASSWORD_ROUTE}`);
    // Still the set-password form after the replace, not the dead-link card.
    expect(screen.getByLabelText(/New password/)).toBeInTheDocument();
  });

  it("still opens a link emailed with ?token=, and strips that too", async () => {
    renderAt(legacyLinkAddress("tok-old"));
    expect(await screen.findByText("For sam@brazosbend.example")).toBeInTheDocument();
    expect(server.calls[0]).toMatchObject({ body: { token: "tok-old" } });
    expect(where()).toBe(`/${TENANT}${SET_PASSWORD_ROUTE}`);
  });

  it("a dead link says so before anyone types, with one way back", async () => {
    server.state.live = false;
    renderAt(linkAddress("used-token"));
    expect(await screen.findByRole("heading", { name: "Link not valid" })).toBeInTheDocument();
    expect(screen.getByText("Ask your admin to resend it.")).toBeInTheDocument();
    expect(screen.queryByLabelText(/New password/)).toBeNull();
    expect(screen.getByRole("link", { name: "Back to sign in" })).toHaveAttribute(
      "href",
      `/${TENANT}/signin`,
    );
  });

  it("no token at all asks the server nothing", () => {
    renderAt(`/${TENANT}${SET_PASSWORD_ROUTE}`);
    expect(screen.getByRole("heading", { name: "Link not valid" })).toBeInTheDocument();
    expect(server.calls.filter((c) => c.path.includes("password-link"))).toEqual([]);
  });
});
