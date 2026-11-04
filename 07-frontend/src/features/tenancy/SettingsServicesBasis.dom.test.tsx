// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-2409 — *"this says, metered or unmeters, but we agreed, we will
//          have 3 states - meter unmetered and % oaf service"*, then *"Shall we
//          consider Metered, % of service and Capacity based"* (PO, 2026-09-02)
// Screens: S8 / SET-03 (Settings → Services & UoM)
// Rules:   BR-RAT-081 as re-ruled (a service declares HOW IT IS BILLED, one of
//          three) · BR-TEN-810 (forward-only) · B14 rule 32 (no internal code in
//          clerk-facing copy)
// ───────────────────────────────────────────────────────
// ⚠ **WHY THIS FILE EXISTS AND THE STATIC SUITE IS NOT ENOUGH — hard-won law 2.**
// A three-state control whose `onChange` reaches nothing is dead UI: it renders,
// every `toContain("Capacity")` assertion passes, and the utility still cannot
// tell us how it bills sewer. Four defects in one day came from exactly that
// shape, which is why G13 exists.
//
// So nothing here asserts markup. Every case DRIVES THE SCREEN with a mouse and
// then reads **the JSON body the server received**, through the real
// `ApiClient` so the body under assertion is the one that goes over the wire.
//
// ⚠ AND THE LAST CASE IS THE ONE THAT IS EASY TO GET WRONG. A form holding no
// basis must send NO `billing_basis` at all — not `"metered"`, not `""`.
// Sending a value the clerk did not pick is resolving DEF-2409 by guessing, and
// it is how the boolean's safe default wrote METERED onto all ten services in
// the first place. The server does answer the key today (BR-TEN-1180), so that
// case is a guard rather than a picture of the payload.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { ServicesTab } from "./SettingsServicesTab";

const TEST_TENANT = "brazosbend";

interface Sent {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
}

/** Water, as `GET /settings/services` serves it once the server ships the
 *  field, and Sewer with NO declaration at all — which is what every row looks
 *  like until it does. Both are ENABLED, because the edit control is refused on
 *  an off row (the units live on `tenant_services`, which only exists then). */
function services(): TenantServiceRow[] {
  const base = {
    primary_uom: "kgal",
    alt_uom: null,
    billed_uom: null,
    conversion_factor: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 2,
    active_accounts: 568,
  };
  return [
    { service: "water", name: "Water", enabled: true, billing_basis: "metered", ...base },
    // No `billing_basis` key: the server has not answered it for this row.
    { service: "sewer", name: "Sewer", enabled: true, ...base },
  ];
}

function recordingClient(sent: Sent[]) {
  return createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (method !== "GET") {
        sent.push({
          method,
          url,
          body:
            init?.body === undefined || init?.body === null
              ? null
              : (JSON.parse(String(init.body)) as Record<string, unknown>),
        });
        return new Response(JSON.stringify({ ...services()[0], warnings: {} }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      // ⚠ THE GET IS BRANCHED ON THE URL, and it has to be: a successful save
      // invalidates the services query, so the screen REFETCHES the list one
      // render after the assertion. A stub answering every GET with the UoM
      // page crashes the table with `rows.map is not a function` — after the
      // test has already passed, which is the worst place for it.
      if (url.includes("/settings/services")) {
        return new Response(JSON.stringify(services()), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      // The modal's own UoM vocabulary (EP-TEN-07). It selects from this list;
      // it never creates a unit.
      return new Response(
        JSON.stringify({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "kgal",
              code: "kgal",
              name: "kgal",
              active: true,
              is_system: true,
              used_by: 0,
              service: null,
            },
          ],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    },
  });
}

function mount(sent: Sent[]) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  qc.setQueryData(queryKeys.tenantServices, services());
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/settings/services`]}>
          <ServicesTab readOnly={false} client={recordingClient(sent)} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Open the service-settings modal for the row at `index` (0 = Water). */
async function openModal(user: ReturnType<typeof userEvent.setup>, index: number) {
  const edit = screen.getAllByRole("button", { name: "Service settings" });
  await user.click(edit[index]);
  await screen.findByText("Save settings");
}

afterEach(cleanup);

describe("DEF-2409 — the billing basis a clerk picks is the one the server receives", () => {
  it("all THREE options are offered, and none of them shows a wire value", async () => {
    const user = userEvent.setup();
    mount([]);
    await openModal(user, 0);

    expect(screen.getByLabelText("Metered — a meter is read")).toBeInTheDocument();
    expect(
      screen.getByLabelText("% of another service — a share of its charge"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Capacity — priced by size or count")).toBeInTheDocument();
    expect(screen.getByText("How this service is billed")).toBeInTheDocument();

    // B14 rule 32 — the codes on the wire never reach a person.
    expect(screen.queryByLabelText("share")).toBeNull();
    expect(screen.queryByLabelText("capacity")).toBeNull();
    // And the state the ruling deleted is gone from the control entirely.
    expect(screen.queryByLabelText(/Unmetered/)).toBeNull();
  });

  it("picking 'Capacity' PUTs billing_basis: capacity — the control is wired, not drawn", async () => {
    const user = userEvent.setup();
    const sent: Sent[] = [];
    mount(sent);
    await openModal(user, 0);

    await user.click(screen.getByLabelText("Capacity — priced by size or count"));
    await user.click(screen.getByText("Save settings"));

    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0].method).toBe("PUT");
    expect(sent[0].url).toContain("/settings/services/water");
    expect(sent[0].body?.billing_basis).toBe("capacity");
    // The boolean is gone from the wire, not merely hidden on the screen.
    expect(sent[0].body).not.toHaveProperty("metered");
  });

  it("picking '% of another service' PUTs billing_basis: share — sewer can finally be said", async () => {
    const user = userEvent.setup();
    const sent: Sent[] = [];
    mount(sent);
    await openModal(user, 1);

    await user.click(screen.getByLabelText("% of another service — a share of its charge"));
    await user.click(screen.getByText("Save settings"));

    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0].url).toContain("/settings/services/sewer");
    expect(sent[0].body?.billing_basis).toBe("share");
  });

  it("a row the server never declared sends NO basis at all when the clerk picks none", async () => {
    // THE GUESSING CASE. Saving a unit change on an undeclared service must not
    // quietly declare it. `"metered"` here would be DEF-2409 reproduced by the
    // screen instead of by provisioning.
    const user = userEvent.setup();
    const sent: Sent[] = [];
    mount(sent);
    await openModal(user, 1);

    await user.click(screen.getByText("Save settings"));

    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0].body).not.toHaveProperty("billing_basis");
    expect(sent[0].body).not.toHaveProperty("metered");
    // …and the rest of the form still went, so this is an OMISSION and not a
    // save that silently did nothing.
    expect(sent[0].body?.primary_uom).toBe("kgal");
  });
});
