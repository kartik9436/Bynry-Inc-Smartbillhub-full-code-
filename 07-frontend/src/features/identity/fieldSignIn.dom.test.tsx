// @vitest-environment jsdom
/**
 * DEF-WRK-9583 (critical) — a field technician can sign in, and the web form
 * names the wrong door instead of calling a right password wrong.
 *
 * The server half is `06-backend/tests/test_def_wrk_9583_field_sign_in.py`.
 * This half asserts what only the screen can get wrong:
 *
 *   · the field app's door posts `surface: "mobile"` and lands on the phone;
 *   · the web door posts `surface: "web"`;
 *   · a `BR-WRK-043` refusal renders its own sentence — never *"That email or
 *     password is incorrect."*, which sent a technician to reset a password
 *     that worked — and offers the field app's door;
 *   · a wrong password still renders the ONE generic line (`BR-IDN-002`);
 *   · an invited technician's forced change carries the phone as `?next=`.
 *
 * Mounted under the REAL path patterns (hard-won law 2: a bare mount makes
 * `useParams().tenant` undefined and every built address `//…`).
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { SessionUser } from "@/api/endpoints";
import {
  FIELD_APP_HOME,
  FORCED_PASSWORD_CHANGE_ROUTE,
  SignInPage,
  routeAfterSignIn,
} from "@/features/identity/SignInPage";

afterEach(cleanup);

const TENANT = "brazosbend";

const OSEI: SessionUser = {
  id: "u-tech",
  full_name: "T. Osei",
  email: "tosei@brazosbend.example",
  phone: null,
  role: "field_technician",
  role_name: "Field Technician",
  must_change_password: false,
};

type Answer = { status: number; body: unknown };

/** A server that records each body it is sent and answers `answer`. */
function server(answer: Answer, sent: unknown[]) {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: (async (_url: unknown, init?: RequestInit) => {
      if (init?.method !== "POST") {
        // `GET auth/sign-in-options` — not the sign-in; answered empty.
        return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
      }
      sent.push(JSON.parse(String(init.body ?? "{}")));
      return new Response(JSON.stringify(answer.body), {
        status: answer.status,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch,
  });
}

function refusal(status: number, messageKey: string, code: string): Answer {
  return {
    status,
    body: { code, message_key: messageKey, params: {}, field_errors: [], br_ref: null, trace_id: "t" },
  };
}

function WhereAmI() {
  const { pathname, search } = useLocation();
  return <p data-testid="landed">{`${pathname}${search}`}</p>;
}

function mount(entry: string, answer: Answer, sent: unknown[]) {
  const client = server(answer, sent);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/:tenant/signin" element={<SignInPage client={client} />} />
          <Route
            path="/:tenant/work/mobile/signin"
            element={<SignInPage client={client} surface="mobile" />}
          />
          <Route path="*" element={<WhereAmI />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  fireEvent.change(document.getElementById("signin-email") as HTMLInputElement, {
    target: { value: OSEI.email },
  });
  fireEvent.change(document.getElementById("signin-password") as HTMLInputElement, {
    target: { value: "Prairie2026grass" },
  });
  fireEvent.submit(document.querySelector("form") as HTMLFormElement);
}

describe("DEF-WRK-9583 · the field app's door", () => {
  it("(a) declares the mobile surface and lands on the phone", async () => {
    const sent: unknown[] = [];
    mount(`/${TENANT}/work/mobile/signin`, { status: 201, body: { user: OSEI } }, sent);
    expect((await screen.findByTestId("landed")).textContent).toBe(`/${TENANT}/work/mobile`);
    expect(sent).toEqual([expect.objectContaining({ surface: "mobile" })]);
  });

  it("(a) an invited technician changes the password first, then goes to the phone", () => {
    expect(routeAfterSignIn({ ...OSEI, must_change_password: true }, null, FIELD_APP_HOME)).toBe(
      `${FORCED_PASSWORD_CHANGE_ROUTE}?next=%2Fwork%2Fmobile`,
    );
  });

  it("(c) a web-only login on the phone hears the web app named", async () => {
    const sent: unknown[] = [];
    mount(
      `/${TENANT}/work/mobile/signin`,
      refusal(403, "identity.signIn.webAppOnly", "AUTH-002"),
      sent,
    );
    expect(await screen.findByText("Sign in on the web app.")).toBeInTheDocument();
    expect(screen.queryByText("That email or password is incorrect.")).toBeNull();
  });
});

describe("DEF-WRK-9583 · the web form", () => {
  it("declares the web surface", async () => {
    const sent: unknown[] = [];
    mount(`/${TENANT}/signin`, { status: 201, body: { user: { ...OSEI, role: "billing_clerk" } } }, sent);
    await screen.findByTestId("landed");
    expect(sent).toEqual([expect.objectContaining({ surface: "web" })]);
  });

  it("(b) names the field app — never 'email or password is incorrect' — and links its door", async () => {
    const sent: unknown[] = [];
    mount(`/${TENANT}/signin`, refusal(403, "identity.signIn.fieldAppOnly", "AUTH-002"), sent);
    // DEF-IDN-9777 — the PO's two sentences, verbatim (2026-10-06), in the alert.
    const first = await screen.findByText(
      "Field Technicians do not have access to the staff portal.",
    );
    const alert = first.closest("[role='alert']") as HTMLElement;
    expect(alert).not.toBeNull();
    expect(
      within(alert).getByText("Please sign in on the Field Technician mobile app instead."),
    ).toBeInTheDocument();
    expect(screen.queryByText("That email or password is incorrect.")).toBeNull();
    // One clear button, drawn by the kit as a primary button — not a bare link.
    const open = within(alert).getByRole("link", { name: "Open the field app" });
    expect(open).toHaveAttribute("href", `/${TENANT}/work/mobile/signin`);
    expect(open).toHaveAttribute("data-variant", "primary");
  });

  it("(d) a wrong password is still the one generic line", async () => {
    const sent: unknown[] = [];
    mount(`/${TENANT}/signin`, refusal(401, "errors.auth.sign_in_failed", "AUTH-001"), sent);
    expect(await screen.findByText("That email or password is incorrect.")).toBeInTheDocument();
    expect(
      screen.queryByText("Field Technicians do not have access to the staff portal."),
    ).toBeNull();
  });

  it("(d) any OTHER 403 key is flattened too — the named list never widens", async () => {
    const sent: unknown[] = [];
    mount(`/${TENANT}/signin`, refusal(403, "errors.auth.sign_in_failed", "AUTH-002"), sent);
    expect(await screen.findByText("That email or password is incorrect.")).toBeInTheDocument();
  });
});
