// ── Trace ──────────────────────────────────────────────
// Story:    US-IDN-001 (EP-IDN-01 §Stories)  Screens: S3
// Rules:    BR-IDN-001 (the tenant resolves first — from the URL's tenant segment since PO 2026-08-10) ·
//           BR-IDN-002 (ONE generic failure) ·
//           BR-IDN-025 (5 fails → 15-min lock) · BR-IDN-022 (forced change) · BR-IDN-023 (contact your administrator) ·
//           BR-IDN-026 (keep-signed-in off by default) · BR-SHL-017 (the kit's PasswordField, E1 closed)
// ───────────────────────────────────────────────────────
// TC tests for S3. Same conventions as the shell packets: no DOM library in
// package.json, so markup asserts on react-dom/server static output (wrapped in
// a MemoryRouter — the page navigates) and the behavior laws run through the
// exported pure pieces. A stub fetch stands in for the network. Anything
// needing a live browser (typing, clicking, cookies, real navigation) is an
// honest it.todo and becomes a Playwright journey.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";

import { createApiClient } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { signIn } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";

import {
  DASHBOARD_ROUTE,
  FORCED_PASSWORD_CHANGE_ROUTE,
  LOCKED_KEY,
  SignInPage,
  lockedMinutes,
  routeAfterSignIn,
  signInFailureLine,
  signInFailureKind,
} from "./SignInPage";

// §4 test data — Silver Creek Water, whose sign-in lives at `/silvercreek/signin`
// (PO 2026-08-10: the tenant is the URL's first PATH segment, not a subdomain).
const TENANT = "silvercreek";
const SIGNIN_PATH = `/${TENANT}/signin`;

const ALEX = {
  id: "0191d3c0-0000-7000-8000-000000000001",
  full_name: "Alex Reed",
  email: "alex@silvercreek.example",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

interface RecordedCall {
  url: string;
  init: RequestInit;
}

/** Records every request; no network, no mock framework. */
function recordingClient(
  body: unknown,
  status = 200,
): { client: ApiClient; calls: RecordedCall[] } {
  const calls: RecordedCall[] = [];
  const client = createApiClient({
    // The tenant is normally read off the browser's URL; a test states it, so
    // the URL these calls go to is visible in the assertions below.
    tenant: TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), init: init ?? {} });
      return new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    },
    sleep: () => Promise.resolve(),
  });
  return { client, calls };
}

function jsonClient(body: unknown, status = 200): ApiClient {
  return recordingClient(body, status).client;
}

/** Rendered AT the tenant's own sign-in URL — the tenant comes from the route. */
/**
 * ⚠ **THE PROVIDER IS NOT DECORATION — `DEF-IDN-5653` PUT A `useQueryClient`
 * INSIDE THIS PAGE.** Sign-in now writes its own answer into `queryKeys.me`,
 * because `POST /auth/session` returns exactly the payload `GET /me` serves and
 * it is the ONLY moment the app can learn it for a user who owes a forced
 * password change — every later `/me` is refused 403 by `_FORCED_CHANGE_EXEMPT`.
 * Mounting this page without a QueryClient therefore throws, and every case
 * below goes through this one wrapper so a case added later cannot forget it.
 */
function SignInHarness(props: { children: ReactNode; offers?: { tenant: string } }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (props.offers !== undefined) {
    // CR-145-BRC08 F3: the tick box is drawn only once the public read has
    // answered `keep_signed_in_offered: true`. A static render is the FIRST
    // paint, before any request can land, so a case that needs the box seeds
    // that answer into the cache under the key the page itself reads.
    client.setQueryData(queryKeys.signInOptions(props.offers.tenant), {
      keep_signed_in_offered: true,
    });
  }
  return <QueryClientProvider client={client}>{props.children}</QueryClientProvider>;
}

function renderSignIn(path = SIGNIN_PATH, offersKeepSignedIn = false): string {
  const tenant = path.split("/")[1] ?? "";
  return renderToStaticMarkup(
    <SignInHarness offers={offersKeepSignedIn ? { tenant } : undefined}>
      <MemoryRouter initialEntries={[path]}>
        <SignInPage client={jsonClient({ user: ALEX }, 201)} />
      </MemoryRouter>
    </SignInHarness>,
  );
}

describe("US-IDN-001 — sign in with email and password (S3)", () => {
  it("US-IDN-001 TC-1: correct credentials at the tenant's PATH create a session and land on the Dashboard", async () => {
    const { client, calls } = recordingClient({ user: ALEX }, 201);
    const user = await signIn(
      { email: ALEX.email, password: "Canyon2026rapids", keep_signed_in: false },
      client,
    );
    expect(user.role_name).toBe("System Admin");
    expect(routeAfterSignIn(user)).toBe(DASHBOARD_ROUTE);

    // BR-IDN-001/BR-TEN-003: the tenant rides in the request PATH (PO
    // 2026-08-10) — the body still carries credentials only, never a tenant id,
    // so nothing the user types can name a tenant.
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("/api/silvercreek/auth/session");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({
      email: ALEX.email,
      password: "Canyon2026rapids",
      keep_signed_in: false,
    });
    expect(calls[0].init.credentials).toBe("include"); // the httpOnly session cookie
  });

  it("US-IDN-001 TC-2/TC-3/TC-4: wrong password, unknown email and a deactivated membership are ONE message (BR-IDN-002)", () => {
    // All three are the identical server envelope (errors.auth.sign_in_failed),
    // and only the server's LOCKED refusal can change the line.
    const t = i18n.t.bind(i18n);
    const generic = new ApiError(401, { code: "AUTH-001", message_key: "errors.auth.sign_in_failed" });
    expect(signInFailureLine(generic, t)).toBe("That email or password is incorrect.");
    expect(signInFailureLine(new Error("network"), t)).toBe("That email or password is incorrect.");
    // …and it is a FORM-level message: never marked on a field, which would
    // say which input the server disliked.
    const html = renderSignIn();
    expect(html).not.toContain("aria-invalid");
  });

  it("DEF-IDN-10620 (TC-8): a locked login says the UTILITY'S minutes, from the server — never a browser-side 5 or 15", () => {
    const t = i18n.t.bind(i18n);
    const locked = (minutes: unknown) =>
      new ApiError(401, { code: "AUTH-001", message_key: LOCKED_KEY, params: { minutes } });
    expect(LOCKED_KEY).toBe("auth.sign_in.locked");
    expect(lockedMinutes(locked(5))).toBe(5);
    expect(signInFailureLine(locked(5), t)).toBe("Too many wrong attempts. Try again in 5 minutes.");
    expect(signInFailureLine(locked(45), t)).toBe("Too many wrong attempts. Try again in 45 minutes.");
    // A locked key with no usable number is not believed — the generic line.
    expect(lockedMinutes(locked("soon"))).toBeNull();
    expect(signInFailureLine(locked(undefined), t)).toBe("That email or password is incorrect.");
    // Only a 401 can carry it.
    expect(lockedMinutes(new ApiError(403, { code: null, message_key: LOCKED_KEY, params: { minutes: 5 } }))).toBeNull();
  });

  it("BR-IDN-022: a session flagged must_change_password routes to the forced-change screen, not the app", () => {
    expect(routeAfterSignIn({ ...ALEX, must_change_password: true })).toBe(
      FORCED_PASSWORD_CHANGE_ROUTE,
    );
    expect(routeAfterSignIn(ALEX)).toBe(DASHBOARD_ROUTE);
  });

  it("BR-IDN-023: the only forgotten-password path is the static 'contact your administrator' notice", () => {
    const html = renderSignIn();
    expect(html).toContain("Forgot password?");
    // v1 has no reset endpoint (BR-IDN-021): no email field, no submit target
    // for a reset, nothing that could post a request.
    expect(html).not.toContain("reset");
  });

  it("BR-IDN-026 / BR-IDN-001: keep-me-signed-in is OFF by default and the tenant is shown, not chosen", () => {
    // CR-145-BRC08 F3 made the box's PRESENCE the utility's; its DEFAULT is
    // still unticked. Absent on first paint (fail closed — nobody has said it
    // is offered yet)…
    expect(renderSignIn()).not.toContain('id="signin-keep"');
    // …and, once the utility has said it is offered, drawn UNTICKED.
    const html = renderSignIn(SIGNIN_PATH, true);
    expect(html).toContain('id="signin-keep"');
    expect(html).not.toMatch(/<input[^>]*id="signin-keep"[^>]*checked/);
    expect(html).not.toMatch(/<input[^>]*checked[^>]*id="signin-keep"/);
    // The tenant named on the card is the one in the URL — read, never typed.
    expect(html).toContain("Signing in to silvercreek");
    // No tenant picker exists — the PATH decides (BR-IDN-001, PO 2026-08-10).
    expect(html).not.toContain("tenant-select");
    // A different path is a different utility, from the same component.
    expect(renderSignIn("/lonestar/signin")).toContain("Signing in to lonestar");
    // …and a URL with no tenant names none rather than inventing one.
    expect(renderSignIn("/signin-help")).not.toContain("Signing in to");
  });

  it("BR-IDN-001 (PO 2026-08-10): the tenant comes from the ROUTE — the browser host is never consulted", () => {
    // The prop that used to carry `window.location.host` is gone; what the page
    // takes now is the tenant itself, and its default is the route's segment.
    const html = renderToStaticMarkup(
      <SignInHarness>
        <MemoryRouter initialEntries={["/brazosbend/signin"]}>
          <SignInPage client={jsonClient({ user: ALEX }, 201)} />
        </MemoryRouter>
      </SignInHarness>,
    );
    expect(html).toContain("Signing in to brazosbend");
    expect(html).not.toContain("smartbillhub.app"); // no host form survives
    expect(html).not.toContain("://");
  });

  it("BR-SHL-017: the form ships the field kit with a real password input and a working submit", () => {
    const html = renderSignIn();
    expect(html).toContain('id="signin-email"');
    expect(html).toContain('id="signin-password" type="password"');
    expect(html).toContain('type="submit"');
  });

  it("BR-SHL-017 (E1 closed): the password control is the KIT's PasswordField — this page no longer defines its own", () => {
    const html = renderSignIn();
    // Asserted through the control's accessible name and role, not its markup:
    // the kit ships a real toggle button called "Show password", so its
    // presence here proves S3 is composing PasswordField rather than the local
    // <input type="password"> block it used to carry.
    expect(html).toContain('aria-label="Show password"');
    expect(html).toContain('aria-controls="signin-password"');
    // …and that button must never submit the sign-in form.
    // ⚠ CLASS NAME -> `data-variant` (CR-018 Phase 4a, 2026-08-20). Route B
    // deletes the name; `buttonKit` stamps `data-variant`/`data-size` on every
    // kit button precisely so a check has something stable to read.
    expect(html).toMatch(/<button [^>]*data-variant="ghost"[^>]*class="[^"]*password-toggle"/);
    // The kit's field wrapper, not a hand-rolled one.
    expect(html).toContain('class="password-field"');
  });

  it.todo(
    "US-IDN-001 TC-5 (v2-deferred, BR-IDN-028): 2FA challenge after correct credentials — no 2FA ships in v1",
  );
  it.todo(
    "US-IDN-001 TC-6 (v2-deferred, BR-IDN-028): forced 2FA enrollment under a tenant policy — no such policy exists in v1",
  );
  it.todo(
    "US-IDN-001 TC-7 (isolation): a Blue Mesa member signing in at silvercreek is denied — server/RLS scope, proven by the backend isolation suite (G5)",
  );
  it.todo(
    "browser scope → Playwright journey: typing credentials, clicking Sign in, the httpOnly cookie landing, and the real redirect to the Dashboard",
  );
});

describe("DEF-533 — the door that leads nowhere", () => {
  // ⚠ THE PO'S LOCKOUT, as a pure rule (this suite is a static render and
  // cannot submit; the click-through half lives in the jsdom suite, DEF-523).
  // DEF-532 dropped the tenant from the URL; signing out then landed on
  // `/premises/signin` — a door for a utility named "premises". The server
  // 404s the whole path, so no password can ever work, and the flattened
  // "check your email and password" message was a lie that kept the PO
  // retrying credentials.
  it("a 404 is the tenant not existing, never a credentials failure", () => {
    const notFound = new ApiError(404, { code: null, message_key: "errors.not-found" });
    expect(signInFailureKind(notFound)).toBe("unknown-tenant");
  });
  it("every other failure stays flattened (BR-IDN-004's one message)", () => {
    expect(
      signInFailureKind(new ApiError(401, { code: "AUTH-001", message_key: "errors.auth-001" })),
    ).toBe("credentials");
    expect(
      signInFailureKind(new ApiError(429, { code: null, message_key: "errors.throttled" })),
    ).toBe("credentials");
    expect(signInFailureKind(new Error("network"))).toBe("credentials");
  });
  it("the unknown-utility copy exists and points at help", () => {
    const html = renderSignIn("/premises/signin");
    // the STATE is unreachable in a static render (it needs a failed submit),
    // but the door itself must render — and the copy keys must exist so the
    // state never prints a raw key (the DEF-533 screenshot's second defect).
    expect(html).toContain("signin-email");
    expect(i18n.t("identity.signIn.unknownTenant", { tenant: "premises" })).toContain("premises");
    expect(i18n.t("identity.signIn.unknownTenantHelp").length).toBeGreaterThan(4);
  });
});



// ── Lifecycle ─────────────────────────────────────────────
// packet: US-IDN-001@402b6db (story+rules snapshot hash — EP-IDN-01)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ tsc✔ eslint✔ vitest 239/239✔ (4 todo this file's suite — browser/journey/v2-deferred scope) · run_gates 9 PASS · 2 FAIL · 1 SKIP — BOTH FAILs are 06-backend-owned and in flight from the two backend lanes (G5 isolation collection errors, G10 backend stories still missing test_us_*_tc* files); reproduced IDENTICALLY with 07-frontend stashed, so nothing in this packet caused them · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
