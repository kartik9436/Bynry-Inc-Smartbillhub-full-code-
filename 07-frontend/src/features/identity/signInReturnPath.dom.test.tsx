// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-6378 (2026-09-23) — after Session expired → Sign in, the
//          person lands back on the page they were on, and ONLY a page inside
//          this tenant.
// Rules:   BR-IDN-022 (a forced password change still comes first) ·
//          BR-TEN-003 (the tenant is the URL's, never the parameter's)
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { SessionUser } from "@/api/endpoints";
import { SignInPage } from "@/features/identity/SignInPage";

afterEach(cleanup);

const TENANT = "brazosbend";

const DANA: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@brazosbend.example",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

/** A server that accepts the password and answers with `user`. */
function acceptingServer(user: SessionUser) {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: (async () =>
      new Response(JSON.stringify({ user }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      })) as typeof fetch,
  });
}

/** Where the browser is, rendered so the assertion reads the router's own answer. */
function WhereAmI() {
  const { pathname, search } = useLocation();
  return <p data-testid="landed">{`${pathname}${search}`}</p>;
}

async function signInAt(entry: string, user: SessionUser = DANA): Promise<string> {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/:tenant/signin" element={<SignInPage client={acceptingServer(user)} />} />
          <Route path="*" element={<WhereAmI />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  fireEvent.change(document.getElementById("signin-email") as HTMLInputElement, {
    target: { value: user.email },
  });
  fireEvent.change(document.getElementById("signin-password") as HTMLInputElement, {
    target: { value: "S3cure!passw0rd" },
  });
  fireEvent.submit(document.querySelector("form") as HTMLFormElement);
  return (await screen.findByTestId("landed")).textContent ?? "";
}

describe("DEF-SHL-6378 — signing in again lands where the session ended", () => {
  it("(c) returns to the page named in ?next=, filters and all", async () => {
    expect(await signInAt(`/${TENANT}/signin?next=%2Fpayments%3Fq%3Dsmith`)).toBe(
      `/${TENANT}/payments?q=smith`,
    );
  });

  it("with no ?next= it lands on the Dashboard, exactly as before", async () => {
    expect(await signInAt(`/${TENANT}/signin`)).toBe(`/${TENANT}/dashboard`);
  });

  it("(d) refuses an off-site ?next= and lands on this tenant's Dashboard", async () => {
    expect(await signInAt(`/${TENANT}/signin?next=https%3A%2F%2Fevil.example%2Fphish`)).toBe(
      `/${TENANT}/dashboard`,
    );
  });

  it("(d) refuses a protocol-relative ?next=", async () => {
    expect(await signInAt(`/${TENANT}/signin?next=%2F%2Fevil.example`)).toBe(`/${TENANT}/dashboard`);
  });

  it("(d) refuses a ?next= that climbs into another utility", async () => {
    expect(await signInAt(`/${TENANT}/signin?next=%2F..%2Fother-utility%2Fpayments`)).toBe(
      `/${TENANT}/dashboard`,
    );
  });

  it("BR-IDN-022 — a password that must be changed is changed first, whatever ?next= says", async () => {
    expect(
      await signInAt(`/${TENANT}/signin?next=%2Fpayments`, { ...DANA, must_change_password: true }),
    ).toBe(`/${TENANT}/change-password`);
  });
});
