// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-170-BRC10 — forgot password (PO 2026-10-05, decision log
//          *"FORGOT PASSWORD"*, three rows: the flow, the ruled words, the go)
// Rules:   BR-IDN-023 as amended 2026-10-05 (its own page; NO contact) ·
//          BR-IDN-022 as amended 2026-10-05 (after the forced change the
//          session ends and the user signs in again) · BR-IDN-021 (no email)
// ───────────────────────────────────────────────────────
/**
 * ⚠ **EVERY CASE HERE RENDERS THE APP'S OWN ROUTE TABLE (`APP_ROUTES`) AT A REAL
 * ADDRESS UNDER `/:tenant`** — never a component mounted bare. That is hard-won
 * law 2's fixture clause: a page mounted outside its `/:tenant` route has an
 * undefined tenant, builds `//signin` for its links, and a `toContain` reads
 * that as a perfectly good string. Here every link is asserted by its FULL
 * address, tenant segment included, and every destination by the screen it
 * opens (`data-page`).
 *
 * The transport is the app's real default client built by the app's real
 * factory, with only `fetch` replaced by a stand-in server (`vi.mock` below).
 * It answers the three calls these screens make and RECORDS them, so the
 * sign-out is asserted as a request the server received rather than as a
 * function that was called.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation, useRoutes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { APP_ROUTES } from "@/App";
import { ToastProvider } from "@/components/Toast";
import { signInAfterPasswordChange } from "@/features/identity/ChangePasswordPage";
import {
  FIELD_APP_SIGN_IN,
  FORGOT_PASSWORD_ROUTE,
  forgotPasswordPath,
} from "@/features/identity/SignInPage";
import i18n from "@/i18n";

const server = vi.hoisted(() => {
  const calls: string[] = [];
  const json = (status: number, body: unknown) =>
    new Response(status === 204 ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();
    const path = url.replace(/^https?:\/\/[^/]+/, "").split("?")[0];
    calls.push(`${method} ${path}`);
    if (method === "POST" && path.endsWith("/me/password")) return json(204, null);
    if (method === "DELETE" && path.endsWith("/auth/session")) return json(204, null);
    if (path.endsWith("/auth/sign-in-options")) {
      return json(200, { data: { keep_signed_in_offered: false } });
    }
    return json(404, { code: "not_found", message_key: "errors.not_found" });
  }) as typeof fetch;
  return { calls, fetchImpl };
});

// The app's real default client, built by the app's real factory — only its
// transport is the stand-in above. Every screen that imports `api` gets it.
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  // The tenant is named because a MemoryRouter does not move `window.location`,
  // which is where the real client reads it from; the server asserts it below.
  return {
    ...actual,
    api: actual.createApiClient({ fetchImpl: server.fetchImpl, tenant: "brazosbend" }),
  };
});

const TENANT = "brazosbend";

function RoutedApp() {
  return useRoutes(APP_ROUTES as never);
}

/** Where the router is, so an assertion can read the address it settled on. */
function WhereAmI() {
  const { pathname, search } = useLocation();
  return <output data-testid="where">{`${pathname}${search}`}</output>;
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

beforeEach(async () => {
  server.calls.length = 0;
  await i18n.changeLanguage("en");
});
afterEach(cleanup);

describe("CR-170-BRC10 · the forgot-password page", () => {
  it("renders signed out at /{tenant}/forgot-password, in the PO's ruled words", () => {
    renderAt(`/${TENANT}/forgot-password`);
    expect(page("forgot-password")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Forgot your password?" })).toBeInTheDocument();
    expect(
      screen.getByText("Ask your System Admin. They give you a temporary password. Sign in with it."),
    ).toBeInTheDocument();
    // Public: no shell furniture, and it asked the server for nothing.
    expect(document.querySelector('nav, [role="navigation"]')).toBeNull();
    expect(server.calls).toEqual([]);
  });

  it("shows NO contact — no name, no phone, no email, no utility's name (PO: \"dont show any contact\")", () => {
    renderAt(`/${TENANT}/forgot-password`);
    const card = page("forgot-password") as HTMLElement;
    const text = card.textContent ?? "";
    expect(text).not.toMatch(/@/); // no email address
    expect(text).not.toMatch(/\d{3}[\s.-]?\d{3,4}/); // no phone number
    expect(text).not.toMatch(/administrator|contact/i); // the retired notice's words
    expect(text.toLowerCase()).not.toContain(TENANT); // no utility named, this one or any other
    expect(card.querySelector('a[href^="mailto:"], a[href^="tel:"]')).toBeNull();
  });

  it("Back to sign in returns to THIS tenant's sign-in page", () => {
    renderAt(`/${TENANT}/forgot-password`);
    const back = screen.getByRole("link", { name: "Back to sign in" });
    expect(back).toHaveAttribute("href", `/${TENANT}/signin`);
    fireEvent.click(back);
    expect(where()).toBe(`/${TENANT}/signin`);
    expect(page("signin")).not.toBeNull();
  });

  it("from the field app, Back returns to the field app's own door", () => {
    expect(forgotPasswordPath("mobile")).toBe(
      `${FORGOT_PASSWORD_ROUTE}?next=${encodeURIComponent(FIELD_APP_SIGN_IN)}`,
    );
    renderAt(`/${TENANT}${forgotPasswordPath("mobile")}`);
    expect(screen.getByRole("link", { name: "Back to sign in" })).toHaveAttribute(
      "href",
      `/${TENANT}/work/mobile/signin`,
    );
  });

  it("refuses a ?next= that would leave the tenant and goes to the ordinary sign-in", () => {
    renderAt(`/${TENANT}/forgot-password?next=%2F%2Fevil.example`);
    expect(screen.getByRole("link", { name: "Back to sign in" })).toHaveAttribute(
      "href",
      `/${TENANT}/signin`,
    );
  });
});

describe("CR-170-BRC10 · the sign-in card's Forgot password?", () => {
  it("is a link to the forgot-password page, and the inline notice is gone", () => {
    renderAt(`/${TENANT}/signin`);
    const forgot = screen.getByRole("link", { name: "Forgot password?" });
    expect(forgot).toHaveAttribute("href", `/${TENANT}/forgot-password`);
    fireEvent.click(forgot);
    expect(where()).toBe(`/${TENANT}/forgot-password`);
    expect(page("forgot-password")).not.toBeNull();
    expect(document.body.textContent).not.toMatch(/Contact your administrator/);
  });
});

describe("CR-170-BRC10 · after a forced password change", () => {
  async function completeForcedChange(entry: string) {
    renderAt(entry);
    fireEvent.change(document.getElementById("change-password-new") as HTMLInputElement, {
      target: { value: "Harbor2026tide" },
    });
    fireEvent.change(document.getElementById("change-password-confirm") as HTMLInputElement, {
      target: { value: "Harbor2026tide" },
    });
    await act(async () => {
      fireEvent.submit(document.querySelector("form") as HTMLFormElement);
    });
    await screen.findByText("Password changed. Sign in again.");
  }

  it("ends the session through the existing sign-out and lands on sign-in with the note", async () => {
    await completeForcedChange(`/${TENANT}/change-password`);
    expect(server.calls).toContain(`POST /api/${TENANT}/me/password`);
    expect(server.calls).toContain(`DELETE /api/${TENANT}/auth/session`);
    expect(
      server.calls.indexOf(`DELETE /api/${TENANT}/auth/session`),
    ).toBeGreaterThan(server.calls.indexOf(`POST /api/${TENANT}/me/password`));
    expect(page("signin")).not.toBeNull();
    expect(page("change-password")).toBeNull();
    // Consumed: the flag is stripped from the address once it has been read.
    expect(where()).toBe(`/${TENANT}/signin`);
  });

  it("a field technician goes back to the field app's sign-in, with the note", async () => {
    expect(signInAfterPasswordChange("/work/mobile")).toBe(`${FIELD_APP_SIGN_IN}?changed=1`);
    expect(signInAfterPasswordChange("/dashboard")).toBe("/signin?changed=1");
  });

  it("the note shows only on that arrival — never on an ordinary visit to sign-in", () => {
    renderAt(`/${TENANT}/signin`);
    expect(page("signin")).not.toBeNull();
    expect(screen.queryByText("Password changed. Sign in again.")).toBeNull();
  });
});
