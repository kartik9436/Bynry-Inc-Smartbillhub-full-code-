// @vitest-environment jsdom
// CR-167-BRC10 round 2 task 5 — the New plan form, mounted under its REAL route
// pattern (hard-won law 2's fixture clause), against a fake API that answers
// the agreed contract (CR-167 §7.3). One `describe` per drawn state, named by
// its image in `05-prototype/plans-2026-10-03/images/`.
import "@/i18n";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { MyPermissions } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import appSource from "../../../App.tsx?raw";
import { NewPlanForm } from "./NewPlanForm";
import { FORM_OPTIONS } from "./planFormOptions.fixture";

afterEach(cleanup);

const TENANT = "brazosbend";
const NEW_ROUTE = "/plans-rates/plans/new";

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

/** `form-options` as the server answers it for a utility whose water has one
 *  base code per class (Brazos Bend: `BASE-W` residential, `BASE-W-COM`
 *  commercial): the base resolves ONLY when `?classes=` names one class. */
function narrowedOptions(url: string): unknown {
  const classes = new URL(url, "http://x").searchParams.get("classes");
  if (classes === "cls-res") return FORM_OPTIONS;
  return {
    ...FORM_OPTIONS,
    schedules: FORM_OPTIONS.schedules.map((row) =>
      row.service !== "water"
        ? row
        : {
            ...row,
            base: {
              code: null,
              sized_by_label: null,
              by_size: [],
              flat_display: null,
              state: "ambiguous",
              codes: ["BASE-W", "BASE-W-COM"],
              monthly_amount: null,
            },
          },
    ),
  };
}

function fakeClient(sent: Sent[], opts: { formOptions: boolean; narrow?: boolean }) {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input, init) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : null;
      sent.push({ method, url, body });
      const json = (status: number, payload: unknown) =>
        new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } });
      if (url.includes("/plans/form-options")) {
        if (!opts.formOptions) return json(404, { code: "NOT_FOUND", message_key: "x" });
        return json(200, opts.narrow === true ? narrowedOptions(url) : FORM_OPTIONS);
      }
      if (url.includes("/shell/display")) {
        return json(200, { regional: { currency: "USD" }, company: {}, period: null });
      }
      if (url.endsWith("/plans") && method === "POST") {
        const details = (body?.details ?? {}) as Record<string, unknown>;
        return json(201, {
          id: "plan-1",
          name: details.name ?? "",
          status: body?.publish === true ? "published" : "draft",
          effective_from: body?.effective_from ?? null,
        });
      }
      return json(200, {});
    },
  });
}

function renderForm(opts: { formOptions?: boolean; narrow?: boolean } = {}) {
  const sent: Sent[] = [];
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions());
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}${NEW_ROUTE}`]}>
          <Routes>
            <Route
              path={`/:tenant${NEW_ROUTE}`}
              element={
                <NewPlanForm
                  client={fakeClient(sent, { formOptions: opts.formOptions ?? true, narrow: opts.narrow })}
                  dateFormat="MM/DD/YYYY"
                  timeZone="America/Chicago"
                />
              }
            />
            <Route path="/:tenant/plans-rates/plans" element={<p>the list</p>} />
            <Route path="/:tenant/plans-rates/plans/:planId" element={<p>the plan page</p>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return sent;
}

type User = ReturnType<typeof userEvent.setup>;

async function fillDetails(user: User) {
  await user.type(await screen.findByLabelText(/^Plan name/), "Residential City Plan");
  await user.type(screen.getByLabelText(/^Code/), "RCP");
}

async function addService(user: User, service: string, schedule: string) {
  await user.click(screen.getByRole("button", { name: "+ Add service" }));
  const services = screen.getAllByRole("combobox", { name: "Service" });
  await user.selectOptions(services[services.length - 1] as HTMLElement, service);
  const schedules = screen.getAllByRole("combobox", { name: "Rate schedule" });
  await user.selectOptions(schedules[schedules.length - 1] as HTMLElement, schedule);
}

async function toServices(user: User) {
  await fillDetails(user);
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await screen.findByText("Services and rate schedules");
  await waitFor(() => expect(screen.getByRole("button", { name: "+ Add service" })).toBeEnabled());
}

async function toCharges(user: User) {
  await toServices(user);
  await addService(user, "water", "sch-w");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await screen.findByRole("button", { name: "+ Add charge code" });
}

async function toReview(user: User) {
  await toCharges(user);
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await screen.findByRole("button", { name: "+ Add deposit" });
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await screen.findByRole("button", { name: "Publish plan" });
}

function lastPost(sent: Sent[]): Record<string, unknown> {
  const post = [...sent].reverse().find((call) => call.method === "POST");
  expect(post).toBeDefined();
  return post?.body ?? {};
}

describe("ruling 1 · five one-word steps (image 04)", () => {
  it("the rail is Details · Services · Charges · Billing · Review", async () => {
    renderForm();
    const rail = await screen.findByRole("navigation");
    expect(within(rail).getAllByRole("button").map((b) => b.textContent?.replace(/^[\d✓]/, ""))).toEqual([
      "Details",
      "Services",
      "Charges",
      "Billing",
      "Review",
    ]);
  });

  it("App.tsx mounts the New plan form at plans-rates/plans/new; the Edit route opens the same steps (round 3 task 8)", () => {
    expect(appSource).toMatch(/path: "plans-rates\/plans\/new", element: <NewPlanForm \/>/);
    // The hold this line kept until round 3 has expired: the Edit door is the
    // redrawn form with three choices, and PlanWizard is retired (CR-167 §14).
    expect(appSource).toMatch(/path: "plans-rates\/plans\/:planId\/edit", element: <EditPlanForm \/>/);
  });
});

describe("image 05 · Continue on an empty step names each missing box", () => {
  it("says Fix 2 things first and names the plan name and the code; nothing is posted", async () => {
    const user = userEvent.setup();
    const sent = renderForm();
    await user.click(await screen.findByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Fix 2 things first.")).toBeInTheDocument();
    expect(screen.getByText("Enter the plan name.")).toBeInTheDocument();
    expect(screen.getByText("Enter a code.")).toBeInTheDocument();
    expect(sent.some((call) => call.method === "POST")).toBe(false);
  });
});

describe("image 06 · customer classes is one tick dropdown, Every customer class first (ruling 4)", () => {
  it("opens to Every customer class, then the served classes", async () => {
    const user = userEvent.setup();
    renderForm();
    const box = await screen.findByRole("button", { name: /^Customer classes/ });
    expect(box).toHaveTextContent("Every customer class");
    await waitFor(() => expect(screen.queryByText("Residential")).toBeNull());
    await user.click(box);
    const list = await screen.findByRole("group", { name: /Customer classes/ });
    expect(within(list).getAllByRole("checkbox").map((c) => c.closest("label")?.textContent)).toEqual([
      "Every customer class",
      "Residential",
      "Commercial",
    ]);
  });
});

describe("image 07 · intended for: three ticks and the notes table (ruling 5)", () => {
  it("draws the three ticks and an empty notes table with + Add note", async () => {
    renderForm();
    expect(await screen.findByLabelText("Proof of hardship or assistance")).toBeInTheDocument();
    expect(screen.getByLabelText("At least 25 kW of demand")).toBeInTheDocument();
    expect(screen.getByLabelText("Owner-occupied premises")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Add note" })).toBeInTheDocument();
  });
});

describe("images 08–11 · services table array (rulings 6, 7, 8)", () => {
  it("a picked schedule shows its base $ and code, version and from-date, minimum, and the monthly total", async () => {
    const user = userEvent.setup();
    renderForm();
    await toServices(user);
    await addService(user, "water", "sch-w");
    const table = document.querySelector('[data-array="plan-services"]') as HTMLElement;
    const base = table.querySelector('[data-cell="base"]') as HTMLElement;
    expect(within(base).getByText("$10.00")).toBeInTheDocument();
    expect(within(base).getByText("BASE-W1")).toBeInTheDocument();
    expect(within(table).getByText("V2")).toBeInTheDocument();
    expect(within(table).getByText("from 09/01/2026")).toBeInTheDocument();
    expect(within(table).getByText("V4")).toBeInTheDocument();
    expect(within(table).getByText("$5.00")).toBeInTheDocument();
    expect(within(table).getByText("GL 4110")).toBeInTheDocument();
    await addService(user, "sewer", "sch-s");
    expect(within(table.querySelector("[data-plan-monthly]") as HTMLElement).getByText("$19.00")).toBeInTheDocument();
  });

  it("an empty row is refused by name (image 10)", async () => {
    const user = userEvent.setup();
    renderForm();
    await toServices(user);
    await addService(user, "water", "sch-w");
    await user.click(screen.getByRole("button", { name: "+ Add service" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Choose a service in each row.")).toBeInTheDocument();
    expect(screen.getByText("Fix 1 thing first.")).toBeInTheDocument();
  });

  it("+ Add service greys and says All added. when every service is a row (image 11)", async () => {
    const user = userEvent.setup();
    renderForm();
    await toServices(user);
    await addService(user, "water", "sch-w");
    await addService(user, "sewer", "sch-s");
    expect(screen.getByRole("button", { name: "+ Add service" })).toBeDisabled();
    expect(screen.getByText("All added.")).toBeInTheDocument();
    expect(screen.getByText("2 of 2 switched on")).toBeInTheDocument();
  });

  it("the surcharge tick works only once outside-city premises pay more (image 12)", async () => {
    const user = userEvent.setup();
    renderForm();
    await toServices(user);
    await addService(user, "water", "sch-w");
    const tick = screen.getByRole("checkbox", { name: "Surcharge" });
    expect(tick).toBeDisabled();
    await user.selectOptions(screen.getByLabelText(/^Outside-city premises pay more/), "yes");
    expect(screen.getByRole("checkbox", { name: "Surcharge" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Enter the surcharge.")).toBeInTheDocument();
  });
});

describe("images 13–16 · charge codes and taxes (DEF-RAT-9328)", () => {
  it("the utility's late fee is a visible, removable ROW on a new plan — never a silent default", async () => {
    const user = userEvent.setup();
    renderForm();
    await toCharges(user);
    const table = document.querySelector('[data-array="plan-charges"]') as HTMLElement;
    const codes = within(table).getAllByRole("combobox", { name: "Charge code" });
    expect(codes).toHaveLength(1);
    expect(codes[0]).toHaveValue("cc-late");
    expect(within(table).getByText("by customer class")).toBeInTheDocument();
    expect(within(table).getByText("1 on this plan")).toBeInTheDocument();
  });

  it("an empty code row is refused by name and the × removes it (images 15, 16)", async () => {
    const user = userEvent.setup();
    renderForm();
    await toCharges(user);
    await user.click(screen.getByRole("button", { name: "+ Add charge code" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Choose a code, or remove it.")).toBeInTheDocument();
    const removes = screen.getAllByRole("button", { name: /Remove/ });
    await user.click(removes[removes.length - 1] as HTMLElement);
    expect(screen.queryByText("Choose a code, or remove it.")).toBeNull();
  });

  it("taxes add up to a combined rate, exactly (image 14)", async () => {
    const user = userEvent.setup();
    renderForm();
    await toCharges(user);
    for (const tax of ["tx-state", "tx-bexar"]) {
      await user.click(screen.getByRole("button", { name: "+ Add tax" }));
      const boxes = screen.getAllByRole("combobox", { name: "Tax" });
      await user.selectOptions(boxes[boxes.length - 1] as HTMLElement, tax);
    }
    expect(screen.getByText("8.25% combined")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Add tax" })).toBeDisabled();
  });
});

describe("images 17–19 · deposits, discounts and billing terms (ruling 9)", () => {
  it("a deposit row shows its class amounts; an empty one is refused by name", async () => {
    const user = userEvent.setup();
    renderForm();
    await toCharges(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(await screen.findByRole("button", { name: "+ Add deposit" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Choose a deposit, or remove it.")).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Deposit" }), "dep-1");
    expect(screen.getByText("$150.00")).toBeInTheDocument();
    expect(screen.getByText("$300.00")).toBeInTheDocument();
  });

  it("a discount shows its take-up (Enrolled) and refuses an until before its from", async () => {
    const user = userEvent.setup();
    renderForm();
    await toCharges(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(await screen.findByRole("button", { name: "+ Add discount" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Discount" }), "disc-senior");
    expect(screen.getByText("12")).toBeInTheDocument();
    fireEvent.change(document.getElementById("plan-discount-from-0") as HTMLElement, { target: { value: "2026-11-01" } });
    fireEvent.change(document.getElementById("plan-discount-until-0") as HTMLElement, { target: { value: "2026-10-01" } });
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Until is before from.")).toBeInTheDocument();
  });
});

describe("images 20–23 · Review, Publish plan and Save as draft (rulings 9, 10, 11)", () => {
  it("Review draws the shared sections and ends in Save as draft · Publish plan; no Try a bill", async () => {
    const user = userEvent.setup();
    renderForm();
    await toReview(user);
    expect(document.querySelector("[data-plan-sections]")).not.toBeNull();
    expect(document.querySelector('[data-plan-service="water"]')).not.toBeNull();
    expect(screen.getByRole("button", { name: "Save as draft" })).toBeInTheDocument();
    expect(screen.queryByText(/Try a bill/)).toBeNull();
    const charges = document.querySelector('[data-plan-section="charges"]') as HTMLElement;
    expect(within(charges).getByText("LATE")).toBeInTheDocument();
    expect(within(charges).getByText("1.50% · min $5.00")).toBeInTheDocument();
  });

  it("the footer reads Back on the left, then Save as draft · Publish plan together (image 21)", async () => {
    const user = userEvent.setup();
    renderForm();
    await toReview(user);
    const row = document.querySelector('[data-wizard="actions"]') as HTMLElement;
    const words = within(row).getAllByRole("button").map((b) => b.textContent);
    expect(words).toEqual(["Back", "Save as draft", "Publish plan"]);
  });

  it("Publish plan with no start date names the box and posts nothing", async () => {
    const user = userEvent.setup();
    const sent = renderForm();
    await toReview(user);
    await user.click(screen.getByRole("button", { name: "Publish plan" }));
    expect(await screen.findByText("Enter the start date.")).toBeInTheDocument();
    expect(sent.some((call) => call.method === "POST")).toBe(false);
    // DEF-RAT-9362 — a form-side refusal is not a failed publish: no card.
    expect(screen.queryByText("Plan not published.")).toBeNull();
  });

  it("Publish plan posts ONE body with publish:true and the late fee named in charge_codes (image 22)", async () => {
    const user = userEvent.setup();
    const sent = renderForm();
    await toReview(user);
    fireEvent.change(document.getElementById("plan-starts") as HTMLElement, { target: { value: "2026-11-01" } });
    await user.click(screen.getByRole("button", { name: "Publish plan" }));
    expect(await screen.findByText("Residential City Plan published")).toBeInTheDocument();
    expect(screen.getByText("Live from 11/01/2026. Assign units from the plan.")).toBeInTheDocument();
    const body = lastPost(sent);
    expect(body.publish).toBe(true);
    expect(body.charge_codes).toEqual([{ charge: "cc-late" }]);
    expect(body.services).toEqual([{ service: "water", schedule: "sch-w", surcharged: false }]);
    expect((body.details as Record<string, unknown>).customer_classes).toEqual([]);
    expect(body.effective_from).toBe("2026-11-01");
    await user.click(screen.getByRole("button", { name: "Open plan" }));
    expect(await screen.findByText("the plan page")).toBeInTheDocument();
  });

  it("Save as draft posts publish:false and shows the saved state (image 23)", async () => {
    const user = userEvent.setup();
    const sent = renderForm();
    await toReview(user);
    await user.click(screen.getByRole("button", { name: "Save as draft" }));
    expect(await screen.findByText("Residential City Plan saved")).toBeInTheDocument();
    expect(screen.getByText("Saved as a draft. Publish it from the plan.")).toBeInTheDocument();
    expect(lastPost(sent).publish).toBe(false);
  });

  it("removing the late fee row sends charge_codes: [] — the clerk's answer, never an omitted key", async () => {
    const user = userEvent.setup();
    const sent = renderForm();
    await toCharges(user);
    const table = document.querySelector('[data-array="plan-charges"]') as HTMLElement;
    await user.click(within(table).getByRole("button", { name: /Remove/ }));
    expect(within(table).getByText("0 on this plan")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(await screen.findByRole("button", { name: "Continue" }));
    await user.click(await screen.findByRole("button", { name: "Save as draft" }));
    await screen.findByText("Residential City Plan saved");
    expect(lastPost(sent).charge_codes).toEqual([]);
  });
});

describe("an unserved form-options route is an empty list, never a broken step", () => {
  it("renders step 1 with an empty class list", async () => {
    renderForm({ formOptions: false });
    expect(await screen.findByLabelText(/^Plan name/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Customer classes/ })).toHaveTextContent("Every customer class");
  });
});

describe("DEF-RAT-9351 · step 1's customer classes narrow each service's base (CR-167 §7.3 ?classes=)", () => {
  function optionsCalls(sent: Sent[]): URLSearchParams[] {
    return sent
      .filter((call) => call.url.includes("/plans/form-options"))
      .map((call) => new URL(call.url, "http://x").searchParams);
  }

  async function tick(user: User, label: string) {
    await user.click(screen.getByRole("button", { name: /^Customer classes/ }));
    const list = await screen.findByRole("group", { name: /Customer classes/ });
    await user.click(within(list).getByRole("checkbox", { name: label }));
    await user.keyboard("{Escape}");
  }

  function monthly(): HTMLElement {
    return document.querySelector("[data-plan-monthly]") as HTMLElement;
  }

  it("Every customer class asks form-options for every class", async () => {
    const user = userEvent.setup();
    const sent = renderForm({ narrow: true });
    await toServices(user);
    const last = optionsCalls(sent).at(-1);
    expect(last?.get("classes")).toBe("cls-res,cls-com");
  });

  it("ticking Residential asks for Residential, and water's base reads $10.00 — never $0.00", async () => {
    const user = userEvent.setup();
    const sent = renderForm({ narrow: true });
    await fillDetails(user);
    await tick(user, "Residential");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByText("Services and rate schedules");
    await waitFor(() => expect(optionsCalls(sent).at(-1)?.get("classes")).toBe("cls-res"));
    await waitFor(() => expect(screen.getByRole("button", { name: "+ Add service" })).toBeEnabled());
    await addService(user, "water", "sch-w");
    const base = await waitFor(() => document.querySelector('[data-cell="base"]') as HTMLElement);
    await waitFor(() => expect(within(base).getByText("$10.00")).toBeInTheDocument());
    expect(within(base).getByText("BASE-W1")).toBeInTheDocument();
    expect(within(monthly()).getByText("$10.00")).toBeInTheDocument();
    expect(document.querySelector("[data-plan-summary-figure]")).toHaveTextContent("$10.00");
  });

  it("a picked schedule whose base stops resolving keeps its row, names its codes, and never totals $0.00", async () => {
    const user = userEvent.setup();
    renderForm({ narrow: true });
    await fillDetails(user);
    await tick(user, "Residential");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByText("Services and rate schedules");
    await waitFor(() => expect(screen.getByRole("button", { name: "+ Add service" })).toBeEnabled());
    await addService(user, "water", "sch-w");
    await waitFor(() => expect(within(monthly()).getByText("$10.00")).toBeInTheDocument());
    // back to Details: untick Residential, so the plan is for every class again
    await user.click(screen.getByRole("button", { name: "Back" }));
    await tick(user, "Residential");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByText("Services and rate schedules");
    const table = document.querySelector('[data-array="plan-services"]') as HTMLElement;
    expect((within(table).getByRole("combobox", { name: "Rate schedule" }) as HTMLSelectElement).value).toBe("sch-w");
    await waitFor(() => expect(within(table).getByText("Choose a base code")).toBeInTheDocument());
    expect(within(table).getByText("BASE-W, BASE-W-COM")).toBeInTheDocument();
    expect(monthly()).not.toHaveTextContent("$0.00");
    expect(monthly()).toHaveTextContent("—");
    expect(document.querySelector("[data-plan-summary-figure]")).not.toHaveTextContent("$0.00");
  });
});

describe("photographed against the real server (CR-167 §11.2)", () => {
  it("DEF-RAT-9355: This plan follows the page as it scrolls (images 19–20 draw it part-way down)", async () => {
    renderForm();
    await screen.findByLabelText(/^Plan name/);
    const panel = document.querySelector("[data-plan-summary]") as HTMLElement;
    expect(panel.parentElement?.className.split(" ")).toEqual(expect.arrayContaining(["sticky", "top-4", "self-start"]));
  });

  it("DEF-RAT-9356: a charge type is worded, never its stored code (image 13: One-time)", async () => {
    const user = userEvent.setup();
    renderForm();
    await toCharges(user);
    const table = document.querySelector('[data-array="plan-charges"]') as HTMLElement;
    await user.click(screen.getByRole("button", { name: "+ Add charge code" }));
    const codes = within(table).getAllByRole("combobox");
    await user.selectOptions(codes[codes.length - 1] as HTMLElement, "cc-recon");
    expect(within(table).getByText("One-time")).toBeInTheDocument();
    expect(within(table).queryByText("one_time")).toBeNull();
  });

  it("DEF-RAT-9357 / DEF-SHL-9523: the surcharge help reads in American English — Check the services above.", async () => {
    const user = userEvent.setup();
    renderForm();
    await toServices(user);
    await user.selectOptions(screen.getByLabelText(/^Outside-city premises pay more/), "yes");
    expect(screen.getByText("Check the services above.")).toBeInTheDocument();
  });
});
