// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-145-BRC08 task F3 — the sign-in screen hides "Keep me signed in"
//          when the utility has switched it off.
// Rules:   BR-IDN-026 as amended (PO 2026-09-28, "Im okay with these limit") —
//          whether the tick box is OFFERED is the utility's, default on ·
//          BR-IDN-001 (the tenant is the URL's) · B14 rule 33 (rationale is
//          ZERO words on screen — an absent control explains nothing)
// ───────────────────────────────────────────────────────
// ⚠ **THE ENDPOINT IS PUBLIC, AND THAT IS THE WHOLE REASON `B13` EXISTS.** A
// sign-in screen has no session, so it cannot read `GET /settings/security-
// policy`, where this fact also lives — that endpoint is System-Admin-only and
// would 401 on every visitor. A screen deciding its own controls from a 401 is
// a screen whose controls are decided by an error path.
//
// ⚠ **EVERY ASSERTION WAITS FOR THE ANSWER, NOT FOR A TICK.** The box is absent
// BEFORE the request is answered and absent AFTER a refusal, so a check that
// runs on the first tick passes for the wrong reason and would go on passing
// with the fix removed. The offered case is therefore proved with `findBy*` —
// which cannot resolve until the box exists — and the withheld case is proved
// only AFTER the same request has been observed to land, by waiting on
// something else the answer changes.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
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

/**
 * A utility that does or does not offer the tick box, plus a counter so a test
 * can wait on the PUBLIC READ HAVING BEEN ANSWERED rather than on a timer.
 */
function utility(offers: boolean | "refuses") {
  const optionsCalls = vi.fn();
  const signInBodies: unknown[] = [];
  const client = createApiClient({
    tenant: TENANT,
    fetchImpl: (async (input: unknown, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/auth/sign-in-options")) {
        optionsCalls();
        if (offers === "refuses") {
          return new Response(JSON.stringify({ error: { code: "SYS-001" } }), { status: 500 });
        }
        return new Response(JSON.stringify({ keep_signed_in_offered: offers }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      signInBodies.push(JSON.parse(String(init?.body ?? "{}")));
      return new Response(JSON.stringify({ user: DANA }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch,
  });
  return { client, optionsCalls, signInBodies };
}

function mountSignIn(client: ReturnType<typeof utility>["client"]): QueryClient {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // ⚠ MOUNTED UNDER THE REAL PATH PATTERN `/:tenant/signin`. A bare
  // `MemoryRouter` leaves `useParams().tenant` undefined, every address the
  // page builds comes out `//...` — a protocol-relative URL to another host —
  // and the query key this screen is cached under becomes the same for every
  // utility, which is precisely the bug that would show one tenant's answer on
  // another tenant's door.
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TENANT}/signin`]}>
        <Routes>
          <Route path="/:tenant/signin" element={<SignInPage client={client} />} />
          <Route path="*" element={<p>elsewhere</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return queryClient;
}

/**
 * ⚠ **THE PUBLIC READ HAS BEEN ANSWERED — not merely SENT.** A fetch counter
 * proves the request left; it says nothing about whether the page has drawn
 * the answer, and "absent" is also what the page shows while it waits. So a
 * withheld-box case waits until the sign-in-options query has SETTLED (success
 * or error) in the very cache the page reads, and one more render has run.
 *
 * (Until 2026-09-28 this waited on `findByLabelText(/Password/i)`, which
 * matched BOTH the password input and the "Show password" toggle and threw
 * "Found multiple elements" — and even with one match it proved nothing,
 * because the password field is drawn on first paint, before any answer.)
 */
async function answered(queryClient: QueryClient): Promise<void> {
  await waitFor(() => {
    const state = queryClient.getQueryState(queryKeys.signInOptions(TENANT));
    expect(state?.status === "success" || state?.status === "error").toBe(true);
  });
  // The settled state is written before React re-renders from it; give the
  // page the render in which it could have drawn the box.
  await screen.findByLabelText(/^Password/i, { selector: "input" });
  await new Promise((resolve) => setTimeout(resolve, 0));
}

const KEEP = /Keep me signed in/i;

describe("CR-145-BRC08 F3 — the tick box is the utility's to offer", () => {
  it("offers it when the utility does, and posts what the person chose", async () => {
    const { client, signInBodies } = utility(true);
    mountSignIn(client);

    // `findBy` cannot resolve before the public read has been answered, so
    // this assertion is impossible to satisfy from the pre-request screen.
    const box = await screen.findByLabelText(KEEP);
    expect(box).toBeInTheDocument();
    expect(box).not.toBeChecked(); // still starts unticked (BR-IDN-026)

    fireEvent.click(box);
    fireEvent.change(document.getElementById("signin-email") as HTMLInputElement, {
      target: { value: DANA.email },
    });
    fireEvent.change(document.getElementById("signin-password") as HTMLInputElement, {
      target: { value: "S3cure!passw0rd" },
    });
    fireEvent.submit(document.querySelector("form") as HTMLFormElement);

    await waitFor(() => expect(signInBodies).toHaveLength(1));
    expect(signInBodies[0]).toMatchObject({ keep_signed_in: true });
  });

  it("hides it when the utility has switched it off, and says nothing about the absence", async () => {
    const { client, optionsCalls, signInBodies } = utility(false);
    const queryClient = mountSignIn(client);

    // ⚠ WAIT FOR THE ANSWER FIRST. The box is also absent before the request
    // lands, so asserting absence straight away proves nothing at all — it is
    // the same screen with or without this feature.
    await waitFor(() => expect(optionsCalls).toHaveBeenCalled());
    await answered(queryClient);

    expect(screen.queryByLabelText(KEEP)).not.toBeInTheDocument();
    expect(document.getElementById("signin-keep")).toBeNull();
    // B14 rule 33: the screen does not explain the absence. Not "your utility
    // has turned this off", not a disabled box with a reason — nothing.
    expect(document.body.textContent ?? "").not.toMatch(/signed in/i);
    // The rest of the door still works, and the row keeps its other control.
    expect(screen.getByText(/Forgot password/i)).toBeInTheDocument();

    fireEvent.change(document.getElementById("signin-email") as HTMLInputElement, {
      target: { value: DANA.email },
    });
    fireEvent.change(document.getElementById("signin-password") as HTMLInputElement, {
      target: { value: "S3cure!passw0rd" },
    });
    fireEvent.submit(document.querySelector("form") as HTMLFormElement);

    await waitFor(() => expect(signInBodies).toHaveLength(1));
    expect(signInBodies[0]).toMatchObject({ keep_signed_in: false });
  });

  it("withholds it when the public read FAILS — absent until proven offered", async () => {
    // Hard-won law 3, fail closed: the cost of being wrong this way is one
    // convenience a person does not see. The cost the other way is offering a
    // utility exactly the thing its admin switched off.
    const { client, optionsCalls } = utility("refuses");
    const queryClient = mountSignIn(client);

    await waitFor(() => expect(optionsCalls).toHaveBeenCalled());
    await answered(queryClient);
    expect(queryClient.getQueryState(queryKeys.signInOptions(TENANT))?.status).toBe("error");
    expect(screen.queryByLabelText(KEEP)).not.toBeInTheDocument();
    // …and the sign-in form is still fully usable, which is the point of not
    // blocking the page on this read.
    expect(document.getElementById("signin-email")).toBeInTheDocument();
    expect(document.getElementById("signin-password")).toBeInTheDocument();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-145-BRC08 task F3 (frontend lane SESS-FRONTEND)
// generated: 2026-09-28
// exceptions: the path `/auth/sign-in-options` and the single field
//   `keep_signed_in_offered` are what this lane built against; `B13` owns the
//   endpoint and a divergence in either is a rename, not a redesign — reported.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
