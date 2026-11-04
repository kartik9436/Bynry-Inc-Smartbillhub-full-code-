// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-IDN-10365 (CR-187-BRC10) — the office never saw a field
//          technician's phone app code. `POST users` answered it, the web drew
//          only the temporary password, and `POST users/{id}/activation-code`
//          had no button — so a new technician could not claim the phone app.
// Rules:   R105 (a six-character code, valid 7 days, claims the native app) ·
//          BR-IDN-022 (a credential is shown ONCE) · BR-IDN-009 (user
//          management is System Admin only) · B14 rule 15 (row actions are
//          icons with an accessible name) · rule 33 (label ≤ 3 words)
// ───────────────────────────────────────────────────────
/**
 * ⚠ **A FAKE SERVER, NOT A SEEDED CACHE.** The defect lived in what the screen
 * does with a RESPONSE it already received — the answer carried the code and
 * the screen dropped it — so the only honest fixture is one that answers the
 * POST with the server's real shape and lets the screen do the rest. The fake
 * records every request, so "the reissue calls the right endpoint" is asserted
 * against the method and the address actually sent, not against a function
 * name.
 *
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN** (`/:tenant/settings/users`). A
 * bare `MemoryRouter` leaves `useParams().tenant` undefined (DEF-CWP-3925).
 *
 * ⚠ **`findBy*` THROUGHOUT.** Every assertion reads the screen after the
 * request has been answered; a `getBy` taken before the mutation settles reads
 * the screen from before the click, where there is nothing to find and nothing
 * to fail on.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { TenantUser } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import { UsersTab, rowActionsFor } from "@/features/identity/SettingsUsersTab";

afterEach(cleanup);

const TENANT = "brazosbend";
const CODE = "K7QM2P";
const CODE_EXPIRES = "2026-10-29T15:00:00Z"; // issued + 7 days
const NEW_CODE = "R4XW9H";

const ADMIN_ROW: TenantUser = {
  id: "u-dana",
  name: "Dana Okafor",
  email: "dana@brazosbend.example",
  role: "system_admin",
  role_name: "System Admin",
  last_active_at: "2026-10-21T14:00:00Z",
  status: "active",
};

const TECH_ROW: TenantUser = {
  id: "u-luis",
  name: "Luis Ortega",
  email: "luis@brazosbend.example",
  phone: "+15125550142",
  role: "field_technician",
  role_name: "Field Technician",
  last_active_at: null,
  status: "invited",
};

const CLERK_ROW: TenantUser = {
  id: "u-priya",
  name: "Priya Menon",
  email: "priya@brazosbend.example",
  role: "billing_clerk",
  role_name: "Billing Clerk",
  last_active_at: "2026-10-20T09:00:00Z",
  status: "active",
};

const ROLES = {
  roles: [
    { code: "system_admin", name: "System Admin" },
    { code: "billing_clerk", name: "Billing Clerk" },
    { code: "executive", name: "Executive" },
    { code: "field_technician", name: "Field Technician" },
  ],
  permissions: [],
};

interface Sent {
  method: string;
  url: string;
  body: unknown;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** The server, as `apps/identity/api.py` answers. `viewerRole` is who is
 *  signed in; `created` is the row `POST users` makes. */
function fakeServer(viewerRole: string, created: TenantUser = TECH_ROW) {
  const sent: Sent[] = [];
  const client = createApiClient({
    tenant: TENANT,
    fetchImpl: (async (input: unknown, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const body = typeof init?.body === "string" ? JSON.parse(init.body) : null;
      sent.push({ method, url, body });
      if (method === "GET" && url.includes("/me/permissions")) {
        return json({ role: viewerRole, role_name: viewerRole, permissions: [] });
      }
      if (method === "GET" && url.includes("/roles")) return json(ROLES);
      if (method === "GET" && url.includes("/users")) {
        return json({ count: 3, next: null, previous: null, results: [ADMIN_ROW, TECH_ROW, CLERK_ROW] });
      }
      if (method === "POST" && url.endsWith("/activation-code")) {
        return json({ activation_code: NEW_CODE, activation_code_expires_at: CODE_EXPIRES }, 201);
      }
      if (method === "POST" && url.endsWith("/users")) {
        // `UsersView.post`: the two activation keys are added ONLY for a
        // field technician.
        const answer: Record<string, unknown> = {
          user: created,
          temp_password: "Tmp-8842-qz",
          invitation_email: { status: "queued", reason_code: null, email: created.email },
        };
        if (created.role === "field_technician") {
          answer.activation_code = CODE;
          answer.activation_code_expires_at = CODE_EXPIRES;
        }
        return json(answer, 201);
      }
      return json({ code: "SYS-404", message_key: "api.error.unexpected", params: {} }, 404);
    }) as typeof fetch,
  });
  return { client, sent };
}

function mountTab(client: ReturnType<typeof createApiClient>) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/settings/users`]}>
          <Routes>
            <Route
              path="/:tenant/settings/users"
              element={
                <UsersTab readOnly={false} client={client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function addUser(name: string, email: string, role: string): Promise<void> {
  fireEvent.click(await screen.findByRole("button", { name: "+ Invite user" }));
  // The role list arrives from `GET /roles`; wait for the option to exist.
  await screen.findByRole("option", { name: ROLES.roles.find((r) => r.code === role)?.name ?? role });
  fireEvent.change(document.getElementById("full_name") as HTMLInputElement, { target: { value: name } });
  fireEvent.change(document.getElementById("email") as HTMLInputElement, { target: { value: email } });
  fireEvent.change(document.getElementById("role") as HTMLSelectElement, { target: { value: role } });
  fireEvent.click(await screen.findByRole("button", { name: "Create user" }));
}

describe("DEF-IDN-10365 · the phone app code after adding a user", () => {
  it("shows the code, its expiry and Copy beside the temporary password for a field technician", async () => {
    const { client } = fakeServer("system_admin", TECH_ROW);
    mountTab(client);
    await addUser("Luis Ortega", "luis@brazosbend.example", "field_technician");

    // The password panel is there, as before …
    expect(await screen.findByText("Tmp-8842-qz")).toBeInTheDocument();
    // … and the code is in the SAME panel, beside it, with its own heading.
    const code = await screen.findByText(CODE);
    const panel = code.closest("[data-phone-app-code]") as HTMLElement;
    expect(panel).not.toBeNull();
    expect(within(panel).getByText("Phone app code")).toBeInTheDocument();
    expect(within(panel).getByText("Expires 10/29/2026")).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Copy" })).toBeInTheDocument();
    expect(code.closest(".settings-temp-password")).toContainElement(screen.getByText("Tmp-8842-qz"));

    // Shown once: dismissing the password panel takes the code with it.
    fireEvent.click(screen.getByRole("button", { name: "I've copied it" }));
    expect(screen.queryByText(CODE)).not.toBeInTheDocument();
  });

  it("shows no code for any other role — the answer carries none", async () => {
    const created: TenantUser = { ...CLERK_ROW, id: "u-new", email: "new@brazosbend.example" };
    const { client } = fakeServer("system_admin", created);
    mountTab(client);
    await addUser("Sam Lee", "new@brazosbend.example", "billing_clerk");

    expect(await screen.findByText("Tmp-8842-qz")).toBeInTheDocument();
    expect(screen.queryByText("Phone app code")).not.toBeInTheDocument();
    expect(document.querySelector("[data-phone-app-code]")).toBeNull();
  });
});

describe("DEF-IDN-10365 · New app code on a field technician's row", () => {
  it("confirms first, calls POST users/{id}/activation-code, and shows the new code once", async () => {
    const { client, sent } = fakeServer("system_admin");
    mountTab(client);

    const action = await screen.findByRole("button", { name: "New app code" });
    // Exactly one row offers it — the technician's.
    expect(screen.getAllByRole("button", { name: "New app code" })).toHaveLength(1);
    fireEvent.click(action);

    // It voids the old code, so it asks first, and nothing has been sent yet.
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText("New app code for Luis Ortega?")).toBeInTheDocument();
    expect(within(dialog).getByText("The old code stops working.")).toBeInTheDocument();
    expect(sent.filter((r) => r.url.endsWith("/activation-code"))).toHaveLength(0);

    fireEvent.click(within(dialog).getByRole("button", { name: "New app code" }));

    const code = await screen.findByText(NEW_CODE);
    const posts = sent.filter((r) => r.method === "POST");
    expect(posts).toHaveLength(1);
    expect(posts[0].url).toMatch(new RegExp(`/api/${TENANT}/users/u-luis/activation-code$`));

    const panel = code.closest("[data-phone-app-code]") as HTMLElement;
    expect(within(panel).getByText("Phone app code")).toBeInTheDocument();
    expect(within(panel).getByText("For luis@brazosbend.example")).toBeInTheDocument();
    expect(within(panel).getByText("Expires 10/29/2026")).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Copy" })).toBeInTheDocument();

    fireEvent.click(within(panel).getByRole("button", { name: "I've copied it" }));
    expect(screen.queryByText(NEW_CODE)).not.toBeInTheDocument();
  });

  it("is hidden from anyone who is not a System Admin", async () => {
    const { client, sent } = fakeServer("executive");
    mountTab(client);
    // The rows are on screen and the viewer's role has been read …
    expect(await screen.findByText("Luis Ortega")).toBeInTheDocument();
    await screen.findAllByRole("button", { name: "Edit" });
    expect(sent.some((r) => r.url.includes("/me/permissions"))).toBe(true);
    // … and still no row offers a new code.
    expect(screen.queryByRole("button", { name: "New app code" })).not.toBeInTheDocument();
  });

  it("is offered only on a field technician who can still sign in", () => {
    expect(rowActionsFor(TECH_ROW, "system_admin")).toContain("activation_code");
    expect(rowActionsFor(CLERK_ROW, "system_admin")).not.toContain("activation_code");
    expect(rowActionsFor(ADMIN_ROW, "system_admin")).not.toContain("activation_code");
    expect(rowActionsFor({ ...TECH_ROW, status: "deactivated" }, "system_admin")).not.toContain(
      "activation_code",
    );
    // An unknown viewer (the read not back yet) is offered nothing that voids a code.
    expect(rowActionsFor(TECH_ROW, null)).not.toContain("activation_code");
    expect(rowActionsFor(TECH_ROW, "billing_clerk")).not.toContain("activation_code");
  });
});
