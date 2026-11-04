// @vitest-environment jsdom
// CR-167-BRC10 round 3 task 8 — EDIT a plan: the New form with three choices,
// mounted under its REAL route pattern (hard-won law 2's fixture clause)
// against a fake API answering the server built at 2.484.0 (CR-167 §9). One
// `describe` per drawn state, named by its image in
// `05-prototype/plans-2026-10-03/images/`.
import "@/i18n";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { MyPermissions } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import appSource from "../../../App.tsx?raw";
import { EditPlanForm } from "./EditPlanForm";
import { DRAFT_PLAN, PLAN_ID, PUBLISHED_PLAN } from "./planEdit.fixture";
import { FORM_OPTIONS } from "./planFormOptions.fixture";

afterEach(cleanup);

const TENANT = "brazosbend";
const EDIT_ROUTE = "/plans-rates/plans/:planId/edit";

function permissions(): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: "plans_rates", label: "Plans & Rates", access: "Full" }],
  };
}

interface Sent {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
}

function fakeClient(sent: Sent[], plan: Record<string, unknown>) {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input, init) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : null;
      sent.push({ method, url, body });
      const json = (status: number, payload: unknown) =>
        new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } });
      if (url.includes("/plans/form-options")) return json(200, FORM_OPTIONS);
      if (url.includes("/shell/display")) return json(200, { regional: { currency: "USD" }, company: {}, period: null });
      if (url.includes(`/plans/${String(plan.id)}`)) return json(method === "POST" ? 201 : 200, plan);
      return json(200, {});
    },
  });
}

function Where() {
  const location = useLocation();
  return <output data-testid="where">{location.pathname + location.search}</output>;
}

function renderEdit(query = "", plan: Record<string, unknown> = PUBLISHED_PLAN) {
  const sent: Sent[] = [];
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions());
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/plans-rates/plans/${String(plan.id)}/edit${query}`]}>
          <Routes>
            <Route
              path={`/:tenant${EDIT_ROUTE}`}
              element={
                <>
                  <EditPlanForm client={fakeClient(sent, plan)} dateFormat="MM/DD/YYYY" timeZone="America/Chicago" />
                  <Where />
                </>
              }
            />
            <Route path="/:tenant/plans-rates/plans/:planId" element={<p>the plan page</p>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return sent;
}

type User = ReturnType<typeof userEvent.setup>;

async function rail(): Promise<string[]> {
  const nav = await screen.findByRole("navigation");
  return within(nav)
    .getAllByRole("button")
    .map((b) => b.textContent?.replace(/^[\d✓]/, "") ?? "");
}

function writes(sent: Sent[]): Sent[] {
  return sent.filter((call) => call.method !== "GET");
}

async function continueTo(user: User, times: number) {
  for (let i = 0; i < times; i += 1) {
    await user.click(screen.getByRole("button", { name: "Continue" }));
  }
}

describe("App.tsx · the Edit door opens this form", () => {
  it("plans-rates/plans/:planId/edit mounts EditPlanForm — PlanWizard is retired", () => {
    expect(appSource).toMatch(/path: "plans-rates\/plans\/:planId\/edit", element: <EditPlanForm \/>/);
    expect(appSource).not.toMatch(/<PlanWizard|features\/rating\/PlanWizard"/);
  });
});

describe("images 38 · 40 · 43 · What to change", () => {
  it("three cards in the drawn order, Name and details chosen by default", async () => {
    renderEdit();
    const group = await screen.findByRole("radiogroup", { name: "What to change" });
    const radios = within(group).getAllByRole("radio");
    expect(radios.map((r) => r.closest("label")?.textContent)).toEqual([
      "Name and detailsSaved on this version",
      "Change from a dateMakes a new version",
      "Fix a mistakeSame dates, with a reason",
    ]);
    expect(radios[0]).toBeChecked();
    expect(await rail()).toEqual(["Details", "Review"]);
  });

  it("image 38: the code is a fact, prices are locked behind 'Change from a date.'", async () => {
    renderEdit("?change=info");
    expect(await screen.findByLabelText(/^Plan name/)).toHaveValue("Residential City Plan");
    expect(document.querySelector('[data-read-only-fact="plan-code"]')).toHaveTextContent("RCP");
    expect(screen.queryByRole("textbox", { name: /^Code/ })).toBeNull();
    const locked = screen.getByRole("region", { name: "Services, charges and billing" });
    expect(locked).toHaveTextContent("Change from a date.");
    expect(locked).toHaveTextContent("Water, Sewer");
  });

  it("image 40: Change from a date is Services · Charges · Billing · Review, opening on the plan's own rows", async () => {
    renderEdit("?change=change");
    expect(await rail()).toEqual(["Services", "Charges", "Billing", "Review"]);
    await waitFor(() => expect(screen.getAllByRole("combobox", { name: "Service" }).map((c) => (c as HTMLSelectElement).value)).toEqual(["water", "sewer"]));
    expect(screen.getAllByRole("combobox", { name: "Rate schedule" }).map((c) => (c as HTMLSelectElement).value)).toEqual(["sch-w", "sch-s"]);
  });

  it("image 37 · the details page's section Edit address: ?change=change&step=2 opens Charges", async () => {
    renderEdit("?change=change&step=2");
    expect(await screen.findByRole("button", { name: "+ Add charge code" })).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent(`/plans/${PLAN_ID}/edit?change=change&step=2`);
  });

  it("switching cards starts that flow again from the plan as saved", async () => {
    const user = userEvent.setup();
    renderEdit("?change=info");
    const name = await screen.findByLabelText(/^Plan name/);
    await user.clear(name);
    await user.type(name, "Renamed");
    await user.click(screen.getByRole("radio", { name: /Fix a mistake/ }));
    expect(await rail()).toEqual(["Services", "Charges", "Billing", "Review"]);
    expect(screen.getByTestId("where")).toHaveTextContent("change=correct");
    await user.click(screen.getByRole("radio", { name: /Name and details/ }));
    expect(await screen.findByLabelText(/^Plan name/)).toHaveValue("Residential City Plan");
  });
});

describe("DEF-RAT-9328 · Edit half — the late fee is a row of the plan's ONE Charges list", () => {
  it("Charges lists LATE with a remove control; removing it sends the list without it", async () => {
    const user = userEvent.setup();
    const sent = renderEdit("?change=change&step=2");
    await screen.findByRole("button", { name: "+ Add charge code" });
    const codes = await screen.findAllByRole("combobox", { name: "Charge code" });
    expect(codes.map((c) => (c as HTMLSelectElement).value)).toEqual(["cc-late", "cc-recon"]);
    const table = codes[0]?.closest("table") as HTMLElement;
    await user.click(within(table).getAllByRole("button", { name: /Remove/ })[0] as HTMLElement);
    expect(screen.getAllByRole("combobox", { name: "Charge code" }).map((c) => (c as HTMLSelectElement).value)).toEqual(["cc-recon"]);
    await continueTo(user, 2);
    fireEvent.change(document.getElementById("plan-starts") as HTMLElement, { target: { value: "2027-01-01" } });
    await user.type(screen.getByLabelText(/^Reason/), "Late fee dropped by council");
    await user.click(screen.getByRole("button", { name: "Publish new version" }));
    await waitFor(() => expect(writes(sent)).toHaveLength(1));
    expect(writes(sent)[0]?.body?.charge_codes).toEqual([{ charge: "cc-recon" }]);
  });

  it("a plan that charges no code opens with NO row — the New form's default LATE is never added", async () => {
    renderEdit("?change=change&step=2", { ...PUBLISHED_PLAN, charge_codes: [] });
    await screen.findByRole("button", { name: "+ Add charge code" });
    expect(screen.queryAllByRole("combobox", { name: "Charge code" })).toEqual([]);
  });
});

describe("Change from a date builds on the LATEST version", () => {
  it("with a v2 already filed from 01/01/2027 the plan is read as of that day, and the next is v3", async () => {
    const plan = {
      ...PUBLISHED_PLAN,
      versions: [
        { version: 2, status: "scheduled", effective_from: "2027-01-01", effective_to: null },
        { version: 1, status: "in_force", effective_from: "2026-09-01", effective_to: "2026-12-31" },
      ],
    };
    const sent = renderEdit("?change=change&step=4", plan);
    await screen.findByText("How it is saved");
    expect(sent.some((call) => call.method === "GET" && call.url.includes(`/plans/${PLAN_ID}?as_of=2027-01-01`))).toBe(true);
    expect(screen.getByText("v3 · new")).toBeInTheDocument();
  });
});

describe("images 41 · 42 · Change from a date · Review", () => {
  it("v1 ends the day before, v2 new, units move — and Back · Save new version · Publish new version (ruling 10)", async () => {
    const user = userEvent.setup();
    renderEdit("?change=change&step=4");
    await screen.findByText("How it is saved");
    expect(screen.getByText("Nothing changed yet.")).toBeInTheDocument();
    fireEvent.change(document.getElementById("plan-starts") as HTMLElement, { target: { value: "2027-01-01" } });
    const versions = document.querySelector("[data-plan-versions]") as HTMLElement;
    expect(within(versions).getAllByRole("row").slice(1).map((r) => r.textContent)).toEqual([
      "v1 · today09/01/2026 – 12/31/2026Gets an end date",
      "v2 · new01/01/2027 – No endNew version",
    ]);
    expect(screen.getByText("5 units move to v2 on 01/01/2027.")).toBeInTheDocument();
    expect(screen.getByText("Today's version ends 12/31/2026.")).toBeInTheDocument();
    const footer = document.querySelector('[data-wizard="actions"]') as HTMLElement;
    expect(within(footer).getAllByRole("button").map((b) => b.textContent)).toEqual([
      "Back",
      "Save new version",
      "Publish new version",
    ]);
    await user.click(screen.getByRole("button", { name: "Publish new version" }));
    expect(await screen.findByText("Enter the reason.")).toBeInTheDocument();
    expect(document.querySelector("[data-plan-fix-count]")).toHaveTextContent("Fix 1 thing first.");
    // A refusal by the FORM is not a failed save: no failure card (image 42).
    expect(screen.queryByText("The plan was not saved.")).toBeNull();
  });

  it("Publish new version is ONE call with the window and the reason, and no untouched table (DEF-RAT-9330)", async () => {
    const user = userEvent.setup();
    const sent = renderEdit("?change=change&step=4");
    await screen.findByText("How it is saved");
    fireEvent.change(document.getElementById("plan-starts") as HTMLElement, { target: { value: "2027-01-01" } });
    await user.type(screen.getByLabelText(/^Reason/), "New sewer schedule from council");
    await user.click(screen.getByRole("button", { name: "Publish new version" }));
    expect(await screen.findByText("v2 starts 01/01/2027. Logged in Audit.")).toBeInTheDocument();
    expect(writes(sent).map((c) => [c.method, c.url.replace(/^.*\/plans/, "/plans")])).toEqual([
      ["POST", `/plans/${PLAN_ID}/versions`],
    ]);
    expect(writes(sent)[0]?.body).toEqual({
      effective_from: "2027-01-01",
      reason: "New sewer schedule from council",
      publish: true,
    });
  });

  it("Save new version files it unpublished", async () => {
    const user = userEvent.setup();
    const sent = renderEdit("?change=change&step=4");
    await screen.findByText("How it is saved");
    fireEvent.change(document.getElementById("plan-starts") as HTMLElement, { target: { value: "2027-01-01" } });
    await user.type(screen.getByLabelText(/^Reason/), "Next year");
    await user.click(screen.getByRole("button", { name: "Save new version" }));
    expect(await screen.findByText("v2 saved. Not published yet.")).toBeInTheDocument();
    expect(writes(sent)[0]?.body?.publish).toBe(false);
  });

  it("a start on or before today's version's start is refused on its box", async () => {
    const user = userEvent.setup();
    renderEdit("?change=change&step=4");
    await screen.findByText("How it is saved");
    fireEvent.change(document.getElementById("plan-starts") as HTMLElement, { target: { value: "2026-09-01" } });
    await user.type(screen.getByLabelText(/^Reason/), "x");
    await user.click(screen.getByRole("button", { name: "Publish new version" }));
    expect(await screen.findByText("Must be after 09/01/2026.")).toBeInTheDocument();
  });
});

describe("image 44 · Fix a mistake · Review", () => {
  it("same dates as facts, the correction keeps v1, issued bills keep v1; Save correction waits for a change", async () => {
    renderEdit("?change=correct&step=4");
    await screen.findByText("How it is saved");
    expect(document.querySelector('[data-read-only-fact="plan-starts"]')).toHaveTextContent("09/01/2026");
    expect(document.querySelector('[data-read-only-fact="plan-ends"]')).toHaveTextContent("No end");
    const versions = document.querySelector("[data-plan-versions]") as HTMLElement;
    expect(within(versions).getAllByRole("row").slice(1).map((r) => r.textContent)).toEqual([
      "v1 · today09/01/2026 – No endSuperseded, kept",
      "v1 · correction09/01/2026 – No endReplaces v1",
    ]);
    expect(screen.getByText("Issued bills keep v1. Correct those bills separately.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save correction" })).toBeDisabled();
  });

  it("a fixed minimum bill sends only what moved, the reason and WHICH version", async () => {
    const user = userEvent.setup();
    const sent = renderEdit("?change=correct&step=3");
    const minimum = await screen.findByLabelText(/^Minimum bill/);
    await user.clear(minimum);
    await user.type(minimum, "12.00");
    await continueTo(user, 1);
    expect(await screen.findByText("What changes")).toBeInTheDocument();
    const changes = screen.getByRole("region", { name: "What changes" });
    expect(within(changes).getAllByRole("row").slice(1).map((r) => r.textContent)).toEqual(["Minimum bill$10.00$12.00"]);
    await user.type(screen.getByLabelText(/^Reason/), "Typed 10 for 12");
    await user.click(screen.getByRole("button", { name: "Save correction" }));
    expect(await screen.findByText("v1 corrected. Logged in Audit.")).toBeInTheDocument();
    expect(writes(sent)[0]?.url).toMatch(new RegExp(`/plans/${PLAN_ID}/corrections$`));
    expect(writes(sent)[0]?.body).toEqual({ minimum_bill_amount: "12.00", reason: "Typed 10 for 12", version: 1 });
  });
});

describe("image 39 · Name and details · Review (same version)", () => {
  it("a rename is a PATCH of that one detail, listed before → after; Save changes", async () => {
    const user = userEvent.setup();
    const sent = renderEdit("?change=info");
    const name = await screen.findByLabelText(/^Plan name/);
    await user.clear(name);
    await user.type(name, "Residential — City");
    await continueTo(user, 1);
    const changes = await screen.findByRole("region", { name: "What changes" });
    expect(within(changes).getAllByRole("row").slice(1).map((r) => r.textContent)).toEqual([
      "Plan nameResidential City PlanResidential — City",
    ]);
    expect(screen.queryByText("How it is saved")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Saved on this version. Logged in Audit.")).toBeInTheDocument();
    expect(writes(sent).map((c) => c.method)).toEqual(["PATCH"]);
    expect(writes(sent)[0]?.body).toEqual({ details: { name: "Residential — City" } });
  });
});

describe("a draft has one choice and edits in place", () => {
  it("no cards, the five New steps, Review ends Save as draft · Publish plan", async () => {
    const user = userEvent.setup();
    const sent = renderEdit("?step=5", DRAFT_PLAN);
    await screen.findByRole("button", { name: "Publish plan" });
    expect(screen.queryByRole("radiogroup", { name: "What to change" })).toBeNull();
    expect(await rail()).toEqual(["Details", "Services", "Charges", "Billing", "Review"]);
    expect(screen.getByRole("button", { name: "Save as draft" })).toBeInTheDocument();
    fireEvent.change(document.getElementById("plan-starts") as HTMLElement, { target: { value: "2026-11-01" } });
    await user.click(screen.getByRole("button", { name: "Publish plan" }));
    await waitFor(() => expect(writes(sent)).toHaveLength(2));
    expect(writes(sent).map((c) => [c.method, c.url.replace(/^.*\/plans/, "/plans")])).toEqual([
      ["PATCH", "/plans/p-draft"],
      ["POST", "/plans/p-draft/publish"],
    ]);
    // DEF-RAT-9514 — `details` always travels on a PATCH (the contract's marker).
    expect(writes(sent)[0]?.body).toEqual({ details: {}, effective_from: "2026-11-01" });
  });
});
