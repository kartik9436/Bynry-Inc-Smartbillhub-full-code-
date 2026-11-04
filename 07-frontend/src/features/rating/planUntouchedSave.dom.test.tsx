// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-5780 — the plan builder answered *what is the operator
//          editing* in TWO places and the two answers differed, so opening a
//          published plan and saving without typing sent an EMPTY payload,
//          whose `null` surcharge `services.py` reads as *this plan does not
//          surcharge* — every bill on the plan lost `BR-RAT-102`'s multiplier.
// Ported:  CR-167-BRC10 round 3 task 8 (2026-10-03) — `PlanWizard.tsx` is
//          retired and the Edit door opens `planForm/EditPlanForm.tsx`. CR-167
//          §5.5 says this file *"must keep guarding"*, so the guard moved with
//          the door. The new form sends ONLY WHAT MOVED (`planEditModel`), so
//          the property is now stronger: an untouched table is never SENT at
//          all, and the server keeps the version's own row (`_copy_bindings`).
// Rules:   BR-RAT-102 (the outside-city surcharge lives on the plan version) ·
//          BR-RAT-1016 (the three verbs) · BR-RAT-1066
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { EditPlanForm } from "./planForm/EditPlanForm";
import { PLAN_ID, PUBLISHED_PLAN } from "./planForm/planEdit.fixture";
import { FORM_OPTIONS } from "./planForm/planFormOptions.fixture";

const TENANT = "brazosbend";

afterEach(cleanup);

interface Call {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
}

/**
 * A client that RECORDS what the screen asked the server for.
 *
 * ⚠ **THE REQUEST IS THE ASSERTION AND NOTHING ELSE COULD BE.** Every rendering
 * in this scenario is correct — the screen draws the plan's real surcharge
 * throughout. The defect was entirely in what is SENT.
 */
function recordingClient(calls: Call[]): ApiClient {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input, init) => {
      const url = String(input);
      const method = String(init?.method ?? "GET").toUpperCase();
      calls.push({
        method,
        url,
        body: typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : null,
      });
      const body = url.includes("/plans/form-options")
        ? FORM_OPTIONS
        : url.includes(`/plans/${PLAN_ID}`)
          ? PUBLISHED_PLAN
          : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    },
  });
}

/** The form under its REAL route pattern — bare, every address it builds
 *  comes out `//plans-rates/…` (hard-won law 2). */
function mountEdit(client: ApiClient, query: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: "plans_rates", label: "Plans & Rates", access: "Full" }],
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/plans-rates/plans/${PLAN_ID}/edit${query}`]}>
          <Routes>
            <Route
              path="/:tenant/plans-rates/plans/:planId/edit"
              element={<EditPlanForm client={client} dateFormat="MM/DD/YYYY" timeZone="America/Chicago" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function writes(calls: Call[]): Call[] {
  return calls.filter((call) => call.method !== "GET");
}

describe("DEF-RAT-5780 — an untouched save never clears the plan", () => {
  // ⚠ THE CONTROL. If the form does not open on the plan, nothing below is
  // measuring anything.
  it("CONTROL: the form opens on the plan's own surcharge", async () => {
    mountEdit(recordingClient([]), "?change=change");
    await waitFor(() => expect(document.getElementById("plan-surcharge")).toHaveValue("25"));
  });

  it("THE SURCHARGE SURVIVES a new version that changes nothing priced — it is not even sent", async () => {
    const calls: Call[] = [];
    mountEdit(recordingClient(calls), "?change=change&step=4");
    await screen.findByText("How it is saved");
    const user = userEvent.setup();
    fireEvent.change(document.getElementById("plan-starts") as HTMLElement, { target: { value: "2027-01-01" } });
    await user.type(screen.getByLabelText(/^Reason/), "Dates only");
    await user.click(screen.getByRole("button", { name: "Publish new version" }));
    await waitFor(() => expect(writes(calls)).toHaveLength(1));
    const body = writes(calls)[0]?.body ?? {};
    expect(Object.keys(body).sort()).toEqual(["effective_from", "publish", "reason"]);
    expect(body).not.toHaveProperty("outside_city_percent");
    expect(body).not.toHaveProperty("services");
  });

  it("A FIX OF ONE FIGURE carries that figure alone — the surcharge is left to the server", async () => {
    const calls: Call[] = [];
    mountEdit(recordingClient(calls), "?change=correct&step=3");
    const user = userEvent.setup();
    const minimum = await screen.findByLabelText(/^Minimum bill/);
    await user.clear(minimum);
    await user.type(minimum, "11.00");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.type(await screen.findByLabelText(/^Reason/), "Typed 10 for 11");
    await user.click(screen.getByRole("button", { name: "Save correction" }));
    await waitFor(() => expect(writes(calls)).toHaveLength(1));
    expect(writes(calls)[0]?.url).toContain("/corrections");
    expect(writes(calls)[0]?.body).toEqual({ minimum_bill_amount: "11.00", reason: "Typed 10 for 11", version: 1 });
  });

  it("AND `?change=` ANYTHING ELSE IS Name and details — a URL is typed by anyone", async () => {
    mountEdit(recordingClient([]), "?change=banana");
    expect(await screen.findByRole("radio", { name: /Name and details/ })).toBeChecked();
  });
});
