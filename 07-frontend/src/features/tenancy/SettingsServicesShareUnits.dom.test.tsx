// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-3232 — sewer is the one service ruled to have NO unit of
//          measure, and both halves of Settings → Services still refuse to
//          save a row without one, so a clerk who opens Sewer and presses
//          Save meets a refusal they cannot satisfy.
// Screens: S8 / SET-03 (Settings → Services & UoM)
// Rules:   BR-TEN-1181 (the primary unit is required for `metered` and
//          `capacity` and REFUSED for `share`) · BR-TEN-1180 clause (2) (a
//          share has "no register, no count, and no unit of its own", PO
//          ruling 2026-09-02) · US-TEN-008 TC-5, narrowed by BR-TEN-1181 ·
//          CLAUDE.md hard rule 3 (a consumption carries an explicit unit)
// ───────────────────────────────────────────────────────
// ⚠ **WHY THIS FILE EXISTS AND THE STATIC SUITE IS NOT ENOUGH — hard-won law 2.**
// `SettingsServicesTab.test.tsx` exercises `serviceSettingsSchema` as a PURE
// FUNCTION and never opens the modal (that file's own E-note (c) says so). So a
// schema correctly narrowed to let a share service through proves nothing about
// what a clerk meets: the form could still render four unit fields it will not
// accept, and still POST the `kgal` sitting in its state.
//
// So nothing below asserts a schema. Every case DRIVES THE SCREEN with a mouse
// and reads **the JSON body the server received**, through the real
// `ApiClient`, on the harness `SettingsServicesBasis.dom.test.tsx` established.
//
// RED PROVED FIRST — MEASURED, by putting the branch tip's own
// `SettingsServicesTab.tsx` back under this file and running it. `3 failed |
// 1 passed`, verbatim:
//
//     × Sewer's settings show no unit fields at all
//     × moving Water to '% of another service' clears its units on the wire
//       AssertionError: expected <select id="primary_uom" …(2)>…(2)</select>
//                       to be null
//     × pressing Save on an untouched Sewer sends four nulls and is not refused
//       AssertionError: expected [] to have a length of 1 but got +0
//
// The third message is the defect in one line: the array of requests the server
// received was EMPTY. The client schema refused the save with "Pick a primary
// unit." and nothing ever left the browser.
//
// ⚠ **AND THE FIRST DRAFT OF THIS FILE COULD NOT HAVE FAILED AT ALL**, which is
// the more useful half of the note. It asked for the label `"Primary unit"`
// exactly, while `FieldLabel` appends a required asterisk — so the query
// returned null whether the field was rendered or not, and the assertion
// `toBeNull()` was green on the broken build. `/^Primary unit/` is what makes
// it a check. A query that cannot distinguish pass from fail is worse than no
// check, because it is trusted.
//
// The metered case below was GREEN before and after: it is the guard on the
// guard, and it is the one that must never move.
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

/** Water as a metered service, and Sewer exactly as the platform now seeds it:
 *  `share`, with no unit at all (BR-TEN-1180's signed ten-row table). Both are
 *  ENABLED, because the settings control is refused on an off row. */
function services(): TenantServiceRow[] {
  const base = {
    billed_uom: null,
    conversion_factor: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 2,
    active_accounts: 568,
  };
  return [
    {
      service: "water",
      name: "Water",
      enabled: true,
      billing_basis: "metered",
      primary_uom: "kgal",
      alt_uom: null,
      ...base,
    },
    {
      service: "sewer",
      name: "Sewer",
      enabled: true,
      billing_basis: "share",
      primary_uom: null,
      alt_uom: null,
      ...base,
    },
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
        return new Response(JSON.stringify({ ...services()[1], warnings: {} }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      // The GET is branched on the URL: a successful save invalidates the
      // services query, so the screen refetches the list one render after the
      // assertion and a stub answering every GET with the UoM page crashes the
      // table AFTER the test has passed.
      if (url.includes("/settings/services")) {
        return new Response(JSON.stringify(services()), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
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

/** Open the service-settings modal for the row at `index` (0 = Water, 1 = Sewer). */
async function openModal(user: ReturnType<typeof userEvent.setup>, index: number) {
  const edit = screen.getAllByRole("button", { name: "Service settings" });
  await user.click(edit[index]);
  await screen.findByText("Save settings");
}

afterEach(cleanup);

describe("DEF-3232 — a share service is never asked for a unit it does not have", () => {
  it("Sewer's settings show no unit fields at all", async () => {
    const user = userEvent.setup();
    mount([]);
    await openModal(user, 1);

    // The basis IS shown — it is the statement the utility makes about itself.
    expect(
      screen.getByLabelText("% of another service — a share of its charge"),
    ).toBeInTheDocument();

    // And all four unit controls are gone, because there is nothing to state.
    expect(screen.queryByLabelText(/^Primary unit/)).toBeNull();
    expect(screen.queryByLabelText(/^Alternate unit/)).toBeNull();
    expect(screen.queryByLabelText(/^Billed unit/)).toBeNull();
    expect(screen.queryByLabelText(/^Conversion factor/)).toBeNull();
  });

  it("pressing Save on an untouched Sewer sends four nulls and is not refused", async () => {
    const user = userEvent.setup();
    const sent: Sent[] = [];
    mount(sent);
    await openModal(user, 1);

    await user.click(screen.getByText("Save settings"));

    // **THE DEFECT, INVERTED.** Before BR-TEN-1181 nothing left the browser at
    // all: the client schema refused with "Pick a primary unit.", a refusal a
    // clerk had no way to satisfy on the one service that has none.
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0].method).toBe("PUT");
    expect(sent[0].url).toContain("/settings/services/sewer");
    expect(sent[0].body?.billing_basis).toBe("share");
    expect(sent[0].body?.primary_uom).toBeNull();
    expect(sent[0].body?.alt_uom).toBeNull();
    expect(sent[0].body?.billed_uom).toBeNull();
    expect(sent[0].body?.conversion_factor).toBeNull();
    expect(screen.queryByText("Pick a primary unit.")).toBeNull();
  });

  it("moving Water to '% of another service' clears its units on the wire", async () => {
    const user = userEvent.setup();
    const sent: Sent[] = [];
    mount(sent);
    await openModal(user, 0);

    // Water arrives metered and priced in kgal — the field is there and filled.
    expect(screen.getByLabelText(/^Primary unit/)).toBeInTheDocument();

    await user.click(screen.getByLabelText("% of another service — a share of its charge"));
    // The units go the moment the basis moves; the clerk does not clear them.
    expect(screen.queryByLabelText(/^Primary unit/)).toBeNull();

    await user.click(screen.getByText("Save settings"));
    await waitFor(() => expect(sent).toHaveLength(1));
    // The `kgal` still in component state is NOT what is sent. This is the
    // clause that repairs a tenant provisioned before 2026-09-02: migration
    // `tenancy 0031` moved sewer's basis and deliberately moved no unit.
    expect(sent[0].body?.primary_uom).toBeNull();
    expect(sent[0].body?.billing_basis).toBe("share");
  });

  it("THE GUARD ON THE GUARD: a metered service still cannot be saved with no unit", async () => {
    const user = userEvent.setup();
    const sent: Sent[] = [];
    mount(sent);
    await openModal(user, 0);

    // Clear the unit on a service that is still declared metered. CLAUDE.md
    // hard rule 3: a reading carries an explicit unit, never an assumed one.
    await user.selectOptions(screen.getByLabelText(/^Primary unit/), "");
    await user.click(screen.getByText("Save settings"));

    expect(await screen.findByText("Pick a primary unit.")).toBeInTheDocument();
    expect(sent).toHaveLength(0);
  });
});
