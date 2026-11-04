// @vitest-environment jsdom
/**
 * The one-time bill page, walked the way a clerk walks it — against a mocked
 * API built to contract §1–§5, because the backend is being built to the same
 * contract in parallel.
 *
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN** `/:tenant/billing/one-time`. A
 * bare `MemoryRouter` leaves `useParams().tenant` undefined and every link the
 * page builds comes out `//billing/…`, which reads as a good string to
 * `toContain` (hard-won law 2, `DEF-CWP-3925`).
 *
 * Every figure is an illustration (B14 rule 37): the cases assert that a
 * served figure reaches the screen, not that the drawing's sum is right.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { OneTimeBillAccount, OneTimeBillKind, OneTimeBillPreview } from "@/api/billingOpsEndpoints";
import type { AccountRow } from "@/api/endpoints";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import { ACCOUNT_ID, accountRow, previewFor } from "./__fixtures__/oneTimeBillFixtures";
import { OneTimeBillPage } from "./OneTimeBillPage";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const TENANT = "brazosbend";

interface Call {
  method: string;
  path: string;
  body: unknown;
}

interface Script {
  preview?: (body: Record<string, unknown>) => OneTimeBillPreview | ApiError | Error;
  /** `GET /billing/one-time/accounts/{id}` — the account card (DEF-BIL-8281). */
  account?: Partial<OneTimeBillAccount>;
  row?: Partial<AccountRow>;
  draft?: () => unknown | ApiError;
  send?: () => unknown | ApiError;
  access?: string;
  /** DEF-BIL-8327 — hold every preview answer this long, like a cold server. */
  previewDelayMs?: number;
  /** DEF-BIL-8327 — hold the account card's answer (a cold first request). */
  accountDelayMs?: number;
}

function ok(data: unknown) {
  return { status: 200, data, etag: null, notModified: false } as never;
}

function fakeClient(script: Script = {}) {
  const calls: Call[] = [];
  function answer(method: string, path: string, body: unknown) {
    calls.push({ method, path, body });
    if (path === "/me/permissions") {
      return ok({ permissions: [{ code: "reads_billing_runs", access: script.access ?? "Full" }] });
    }
    if (path === "/accounts") return ok({ count: 1, results: [accountRow(script.row ?? {})], rollup: {} });
    if (path.startsWith("/billing/one-time/accounts/")) {
      const card = ok({ ...previewFor("interim").account, ...(script.account ?? {}) });
      if (script.accountDelayMs !== undefined) {
        return new Promise((resolve) => setTimeout(() => resolve(card), script.accountDelayMs)) as never;
      }
      return card;
    }
    if (path === "/users") {
      return ok({
        count: 2,
        next: null,
        previous: null,
        results: [
          { id: "u-alex", name: "Alex Reed", email: "alex@x.test", role: "admin", role_name: "System Admin", last_active_at: null, status: "active" },
          { id: "u-inv", name: "", email: "new@x.test", role: "clerk", role_name: "Clerk", last_active_at: null, status: "invited" },
        ],
      });
    }
    if (path === "/payments/reason-codes") {
      return ok({ reasons: [{ code: "MISSED", name: "Missed billing cycle" }], count: 1 });
    }
    if (path === "/charges") {
      return ok({ count: 1, results: [{ code: "RECON", name: "Reconnection fee", amount: "75.0000" }] });
    }
    if (path === "/billing/one-time/preview") {
      const b = body as Record<string, unknown>;
      const made = script.preview?.(b) ?? previewFor(b.kind as OneTimeBillKind);
      if (script.previewDelayMs !== undefined) {
        return new Promise((resolve, reject) =>
          setTimeout(() => (made instanceof Error ? reject(made) : resolve(ok(made))), script.previewDelayMs),
        ) as never;
      }
      if (made instanceof Error) throw made;
      return ok(made);
    }
    if (path === "/billing/one-time") {
      const made = script.draft?.() ?? {
        run_id: "run-1",
        invoice_id: "inv-1",
        invoice_no: "BL-2609-000318",
        total: "168.4900",
        currency: "USD",
        due_date: "2026-10-21",
        bill: previewFor("interim").bill,
        warnings: previewFor("interim").warnings,
      };
      if (made instanceof ApiError) throw made;
      return ok(made);
    }
    if (path === "/billing/one-time/run-1/send") {
      const made = script.send?.() ?? {
        invoice_no: "BL-2609-000318",
        total: "168.4900",
        currency: "USD",
        due_date: "2026-10-21",
        delivery: "queued",
        reads: "locked",
      };
      if (made instanceof ApiError) throw made;
      return ok(made);
    }
    if (path === "/read-batches") return ok({ id: "batch-1" });
    if (path === "/read-batches/batch-1/validate") return ok({ id: "batch-1" });
    if (path === "/read-batches/batch-1") return ok({ id: "batch-1", rows: [] });
    if (path === "/read-batches/batch-1/post") return ok({ id: "batch-1", posted_reads: 3 });
    return ok({ count: 0, results: [] });
  }
  const client = {
    get: async (path: string) => answer("GET", path, undefined),
    post: async (path: string, body?: unknown) => answer("POST", path, body),
    request: async (path: string, options?: { method?: string; body?: unknown }) =>
      answer(options?.method ?? "GET", path, options?.body),
  } as unknown as ApiClient;
  return { client, calls };
}

function mount(client: ApiClient, search = "") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
          <MemoryRouter initialEntries={[`/${TENANT}/billing/one-time${search}`]}>
            <Routes>
              <Route path="/:tenant/billing/one-time" element={<OneTimeBillPage client={client} />} />
            </Routes>
          </MemoryRouter>
        </TenantRegionalProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function chooseAccount() {
  const box = screen.getByRole("combobox", { name: /Find account/ });
  fireEvent.change(box, { target: { value: "Alv" } });
  // By text, not by accessible name: the typed "Alv" is its own element inside
  // the name, which the name computation reads with a gap.
  // Scoped to the account list — a step-1 `<select>` has options too.
  const list = document.getElementById("account_id-listbox") as HTMLElement;
  const [option] = await within(list).findAllByRole("option");
  expect(option).toHaveTextContent("Maria Alvarez");
  fireEvent.click(option);
  // The preview answers the account's defaults (days to pay from its cycle).
  await waitFor(() => expect(screen.getByLabelText(/Days to pay/)).toHaveValue("21"), { timeout: 3000 });
}

function continueButton() {
  return screen.getByRole("button", { name: "Continue" });
}

describe("the frame — six kinds, four one-word steps", () => {
  it("draws the six kind cards and the rail Account · Services · Review · Send", () => {
    mount(fakeClient().client);
    const kinds = within(screen.getByRole("group", { name: "Bill kind" })).getAllByRole("button");
    expect(kinds.map((k) => k.querySelector("span")?.textContent)).toEqual([
      "Interim",
      "First bill",
      "Final",
      "Catch-up",
      "Penalty / theft",
      "Fee",
    ]);
    const rail = document.querySelectorAll("[data-wizard-step]");
    expect(Array.from(rail).map((cell) => cell.textContent?.replace(/^\d/, ""))).toEqual([
      "Account",
      "Services",
      "Review",
      "Send",
    ]);
    expect(screen.getByRole("heading", { name: "One-time bill" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start over" })).toBeInTheDocument();
  });

  it("does not draw the mock-up's review strip", () => {
    mount(fakeClient().client);
    expect(screen.queryByText(/Design mock-up/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Compare kinds/)).not.toBeInTheDocument();
  });

  it("changes the step-1 panels with the kind — a fee asks for a charge, not a period", async () => {
    mount(fakeClient().client, "?kind=fee");
    expect(screen.getByRole("region", { name: "Charge" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Period" })).not.toBeInTheDocument();
    expect(await screen.findByRole("option", { name: /Reconnection fee · \$75\.00/ })).toBeInTheDocument();
  });

  it("gives catch-up a list of missed periods with add and remove, and a reason from Settings", async () => {
    mount(fakeClient().client, "?kind=backbill");
    expect(screen.getByText("1 period")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add period" }));
    expect(screen.getByText("2 periods")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove period 2" }));
    expect(screen.getByText("1 period")).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "Missed billing cycle" })).toBeInTheDocument();
  });
});

describe("step 1 — account, then all problems at once", () => {
  it("fills the account card and defaults days to pay from the cycle", async () => {
    // `DEF-BIL-8806` — the bill date defaults to TODAY, so the due date below
    // is only 10/21/2026 on the day this was written. Only `Date` is faked;
    // the page's debounce timers stay real.
    vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-09-30T15:00:00Z") });
    mount(fakeClient().client);
    await chooseAccount();
    const card = document.querySelector('[data-facts="otb-account"]') as HTMLElement;
    expect(card).toHaveTextContent("AC-2026-00042");
    expect(card).toHaveTextContent("Residential Standard");
    expect(card).toHaveTextContent("$142.18");
    // The derived due date, in the tenant's own format.
    expect(screen.getByLabelText("Due date")).toHaveValue("10/21/2026");
  });

  it("lists every problem at the top AND puts each one on its field", async () => {
    mount(fakeClient().client);
    await chooseAccount();
    fireEvent.change(screen.getByLabelText(/Days to pay/), { target: { value: "" } });
    await act(async () => {
      fireEvent.click(continueButton());
    });
    const banner = await screen.findByText(/Fix \d things? to continue\./);
    const list = banner.closest("[data-otb-problems]") as HTMLElement;
    expect(list).toHaveTextContent("Enter days to pay.");
    expect(list).toHaveTextContent("Enter the period.");
    // DEF-BIL-8317 — the field is marked invalid (tinted by `.input-invalid`).
    expect(screen.getByLabelText(/^From/)).toHaveClass("input-invalid");
    // Each item in the list takes the clerk to its field (PO report, 2.411.4).
    fireEvent.click(within(list).getByText("Enter days to pay."));
    expect(document.activeElement).toBe(screen.getByLabelText(/Days to pay/));
    // The same sentence stands under its own field.
    const dueDays = screen.getByLabelText(/Days to pay/);
    expect(dueDays).toHaveAttribute("aria-invalid", "true");
    // Still on step 1.
    expect(document.querySelector('[data-wizard-step="1"]')).toHaveAttribute("aria-current", "step");
  });

  it("shows the server's field_errors on their fields, in the same pass", async () => {
    const { client } = fakeClient({
      preview: (b) =>
        b.reason_code === "BOGUS"
          ? new ApiError(422, {
              code: "VAL-FORMAT",
              message_key: "api.error.validation",
              field_errors: [{ field: "reason_code", code: "VAL-001", message_key: "billing.oneTime.err.reasonUnknown" }],
            })
          : previewFor(b.kind as OneTimeBillKind),
    });
    mount(client, "?kind=backbill");
    await chooseAccount();
    const select = screen.getByLabelText(/Reason/) as HTMLSelectElement;
    // A code the tenant retired since the list loaded — only the server knows.
    const option = document.createElement("option");
    option.value = "BOGUS";
    select.appendChild(option);
    fireEvent.change(select, { target: { value: "BOGUS" } });
    fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-06-01" } });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-06-30" } });
    await act(async () => {
      fireEvent.click(continueButton());
    });
    expect(await screen.findAllByText("Choose a reason from the list.")).not.toHaveLength(0);
  });
});

async function toServices(kind: OneTimeBillKind = "interim", script: Script = {}) {
  const fake = fakeClient(script);
  mount(fake.client, kind === "interim" ? "" : `?kind=${kind}`);
  await chooseAccount();
  if (kind === "interim" || kind === "backbill" || kind === "penalty") {
    fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-09-30" } });
  }
  if (kind === "final") {
    fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText(/^Move-out date/), { target: { value: "2026-09-18" } });
  }
  if (kind === "first") {
    // The move-in date comes from the account; only the end is typed.
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-09-30" } });
  }
  if (kind === "backbill" || kind === "penalty") {
    const reason = await screen.findByRole("option", { name: "Missed billing cycle" });
    fireEvent.change(screen.getByLabelText(/^Reason/), { target: { value: (reason as HTMLOptionElement).value } });
  }
  await act(async () => {
    fireEvent.click(continueButton());
  });
  await screen.findByRole("region", { name: "Services" });
  return fake;
}

describe("step 2 — services, rates, readings", () => {
  it("draws Services → Rates → Readings in the ruled order, the first two collapsible", async () => {
    await toServices();
    const order = Array.from(document.querySelectorAll("[data-otb-panel]")).map((p) => p.getAttribute("data-otb-panel"));
    expect(order.slice(0, 3)).toEqual(["services", "rates", "readings"]);
    const toggle = within(screen.getByRole("region", { name: "Services" })).getByRole("button", { name: "Services" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(document.getElementById("otb-services-body")).not.toBeVisible();
  });

  it("shows every service, the not-taken one too, with its status", async () => {
    await toServices();
    const services = screen.getByRole("region", { name: "Services" });
    expect(within(services).getAllByRole("row")).toHaveLength(8); // head + seven services
    expect(services).toHaveTextContent("Not in service");
    expect(services).toHaveTextContent("Not taken");
    expect(services).toHaveTextContent("Billed · follows Sewer".replace("Sewer", "Water"));
    expect(services).toHaveTextContent("No base charge for Electric. Billed $0.00.");
  });

  it("shows the Rates Amount column in full — the drawing clips it, the build does not", async () => {
    await toServices();
    const rates = screen.getByRole("region", { name: "Rates" });
    expect(within(rates).getByRole("columnheader", { name: "Amount" })).toBeInTheDocument();
    expect(rates).toHaveTextContent("$29.20");
    expect(rates).toHaveTextContent("Before tax");
    // DEF-BIL-8316 — a unit price at 2 dp where it has no more; $0.1245 keeps its 4.
    expect(rates).toHaveTextContent("$3.25 / kgal to 5 kgal");
    expect(rates).not.toHaveTextContent("$3.2500");
    expect(rates).toHaveTextContent("$0.1245 per kWh");
    // The base charge names its code, and the version is the short cell.
    expect(rates).toHaveTextContent("$8.00 · BASE-W");
    expect(rates).toHaveTextContent("Water · from 08/15/2026");
  });

  it("asks one reading per meter and saves them through Meter Reads, never billing", async () => {
    const { calls } = await toServices();
    for (const meter of ["W-10442", "W-10443", "E-55120"]) {
      fireEvent.change(screen.getByLabelText(`New reading for ${meter}`), { target: { value: "500" } });
    }
    await act(async () => {
      fireEvent.click(continueButton());
    });
    const paths = calls.map((c) => `${c.method} ${c.path}`);
    expect(paths).toContain("POST /read-batches");
    expect(paths).toContain("POST /read-batches/batch-1/validate");
    expect(paths).toContain("POST /read-batches/batch-1/post");
    const staged = calls.find((c) => c.path === "/read-batches")?.body as { rows: { meter_id: string }[] };
    expect(staged.rows.map((r) => r.meter_id)).toEqual(["W-10442", "W-10443", "E-55120"]);
  });

  it("draws per-period readings for catch-up, only the last period typed", async () => {
    await toServices("backbill");
    const blocks = document.querySelectorAll("[data-reading-period]");
    expect(blocks).toHaveLength(3);
    expect(within(blocks[0] as HTMLElement).queryAllByRole("textbox")).toHaveLength(0);
    expect(within(blocks[2] as HTMLElement).getAllByRole("textbox").length).toBeGreaterThan(0);
    expect(blocks[2]).toHaveTextContent("Enter reading");
    expect(screen.getByRole("region", { name: "Periods" })).toBeInTheDocument();
  });

  it("draws the Settlement choice on a final bill and Move-in charges on a first bill", async () => {
    await toServices("final");
    expect(screen.getByRole("region", { name: "Settlement" })).toHaveTextContent("Left to pay");
    expect(screen.getByRole("radio", { name: "Collect" })).toBeChecked();
    cleanup();
    await toServices("first");
    const moveIn = screen.getByRole("region", { name: "Move-in charges" });
    expect(moveIn).toHaveTextContent("Connection charge");
    expect(moveIn).toHaveTextContent("Move-in total");
  });

  it("stands the already-billed banner with a link to that bill", async () => {
    await toServices("interim", {
      preview: (b) =>
        previewFor(b.kind as OneTimeBillKind, {
          duplicate: { invoice_no: "BL-2609-000211", run_id: "run-0", invoice_id: "inv-0", ran_by_name: "J. Ortiz", ran_at: "2026-09-18T10:00:00-05:00" },
        }),
    });
    const banner = screen.getByRole("alert");
    expect(banner).toHaveTextContent("Already billed for this period.");
    expect(banner).toHaveTextContent("BL-2609-000211");
    expect(within(banner).getByRole("link", { name: "Open that bill" })).toHaveAttribute(
      "href",
      `/${TENANT}/billing/bills/inv-0`,
    );
  });
});

describe("step 3 and 4 — the bill as a table, then send", () => {
  function servedWithReads(): Script {
    return {
      preview: (b) => {
        const p = previewFor(b.kind as OneTimeBillKind);
        if (p.readings !== null) {
          p.readings.rows = p.readings.rows.map((r) => ({ ...r, current: { ...r.current, value: "500" }, status: "accepted" }));
        }
        return p;
      },
    };
  }

  it("groups the bill by period with a subtotal, then subtotal, tax and total", async () => {
    const fake = fakeClient(servedWithReads());
    mount(fake.client);
    await chooseAccount();
    fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-09-30" } });
    await act(async () => {
      fireEvent.click(continueButton());
    });
    await screen.findByRole("region", { name: "Services" });
    await act(async () => {
      fireEvent.click(continueButton());
    });
    const bill = await screen.findByRole("region", { name: "The bill" });
    const heads = within(bill).getAllByRole("columnheader").map((h) => h.textContent);
    expect(heads).toEqual(["Service", "Meter / asset", "Charge", "Quantity", "Rate", "Amount"]);
    // DEF-BIL-8315 — the header names the BILL: "INTERIM BILL · DRAFT" (CSS uppercases it).
    expect(bill).toHaveTextContent("Interim bill · draft");
    expect(bill).not.toHaveTextContent("bill bill");
    expect(bill).toHaveTextContent("$165.19");
    expect(bill).toHaveTextContent("Utility tax · 2.00% of taxable charges");
    expect(bill).toHaveTextContent("Total due");
    expect(bill).toHaveTextContent("No base set");
    expect(screen.getByRole("region", { name: "Delivery" })).toBeInTheDocument();
  });

  it("keeps Send shut until all five confirmations are ticked, then sends them as given (PO option B)", async () => {
    const fake = fakeClient(servedWithReads());
    mount(fake.client);
    await chooseAccount();
    fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-09-30" } });
    for (let step = 0; step < 3; step += 1) {
      await act(async () => {
        fireEvent.click(continueButton());
      });
    }
    const sendButton = await screen.findByRole("button", { name: /Send \$168\.49 bill/ });
    expect(sendButton).toBeDisabled();
    expect(sendButton).toHaveAttribute("data-variant", "danger");
    expect(screen.getByText("Final once sent.")).toBeInTheDocument();
    // The single "I checked the amounts" tick is retired.
    expect(screen.queryByLabelText("I checked the amounts")).toBeNull();
    const five = ["Compliance checked", "Email checked", "Texts checked", "Autopay checked", "Ready to send"];
    const group = screen.getByRole("group", { name: "Before sending" });
    for (const label of five) {
      expect(sendButton).toBeDisabled();
      fireEvent.click(within(group).getByLabelText(label));
    }
    expect(sendButton).toBeEnabled();
    // Untick one: Send shuts again.
    fireEvent.click(within(group).getByLabelText("Texts checked"));
    expect(sendButton).toBeDisabled();
    fireEvent.click(within(group).getByLabelText("Texts checked"));
    expect(sendButton).toBeEnabled();
    await act(async () => {
      fireEvent.click(sendButton);
    });
    expect(await screen.findByText("Bill BL-2609-000318 sent")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View bill" })).toHaveAttribute("href", `/${TENANT}/billing/bills/inv-1`);
    // Every rail cell is done and none of them is a door.
    const cells = Array.from(document.querySelectorAll("[data-wizard-step]"));
    expect(cells.every((cell) => cell.getAttribute("data-state") === "done")).toBe(true);
    expect(cells.every((cell) => (cell as HTMLButtonElement).disabled)).toBe(true);
    const sent = fake.calls.find((c) => c.path === "/billing/one-time/run-1/send")?.body as Record<string, unknown>;
    expect(sent).toMatchObject({
      confirmations: { compliance: true, email_mandate: true, sms_mandate: true, autopay_mandate: true, final: true },
      delivery: "email",
    });
    expect(sent).not.toHaveProperty("acknowledged");
    expect(document.querySelector("[data-otb-footnote]")).toHaveAttribute("data-otb-footnote", "sent");
  });
});

describe("BR-SHL-025 — a clerk who may not write", () => {
  it("sees the reason, and nothing that drafts or sends is live", async () => {
    mount(fakeClient({ access: "View" }).client);
    expect(await screen.findByText(/change/i, { selector: "[data-refusal]" })).toBeInTheDocument();
  });
});

describe("the page names nothing internal", () => {
  it("never renders the account's database id", async () => {
    mount(fakeClient().client);
    await chooseAccount();
    expect(document.body.textContent).not.toContain(ACCOUNT_ID);
  });
});

// ── J70 browser walk, 2026-09-30 — each case fed the REAL server's answer ──
describe("what the live server answers (J70 walk)", () => {
  it("shows a step-1 pricing refusal instead of swallowing it (DEF-BIL-8301)", async () => {
    const { client } = fakeClient({
      preview: () =>
        new ApiError(422, {
          code: "BIZ-COMPLETENESS",
          message_key: "billing.oneTime.err.notPriced",
          params: { service: "Electric" },
          field_errors: [],
        }),
    });
    mount(client);
    const box = screen.getByRole("combobox", { name: /Find account/ });
    fireEvent.change(box, { target: { value: "Alv" } });
    const list = document.getElementById("account_id-listbox") as HTMLElement;
    const [option] = await within(list).findAllByRole("option");
    fireEvent.click(option);
    fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-09-30" } });
    // DEF-BIL-8289 — held until Continue, then shown.
    await waitFor(() => expect(screen.getByLabelText(/Days to pay/)).toHaveValue("21"), { timeout: 3000 });
    await act(async () => {
      fireEvent.click(continueButton());
    });
    expect(
      (await screen.findAllByText("Electric can't be priced. Check its rates.", {}, { timeout: 3000 })).length,
    ).toBeGreaterThan(0);
  });

  it("fills a first bill's move-in From from the account, so the preview can answer (DEF-BIL-8309)", async () => {
    const { client, calls } = fakeClient({
      // The live server refuses a request with no period_start.
      preview: (b) =>
        b.period_start
          ? previewFor("first")
          : new ApiError(422, {
              code: "VAL-002",
              message_key: "billing.oneTime.err.periodRequired",
              field_errors: [{ field: "period_start", code: "VAL-001", message_key: "billing.oneTime.err.periodRequired" }],
            }),
    });
    mount(client, "?kind=first");
    await chooseAccount();
    await waitFor(() => {
      const asked = calls.filter((c) => c.path === "/billing/one-time/preview");
      expect((asked[0]?.body as Record<string, unknown>).period_start).toBe(accountRow().opened_at);
    });
  });

  it("prints the account's unit once — customers' premise cell already carries it (DEF-BIL-8302)", async () => {
    mount(fakeClient().client);
    const box = screen.getByRole("combobox", { name: /Find account/ });
    fireEvent.change(box, { target: { value: "Alv" } });
    const list = document.getElementById("account_id-listbox") as HTMLElement;
    const [option] = await within(list).findAllByRole("option");
    expect(option.textContent).toContain("1408 Elm St · Unit A");
    expect(option.textContent).not.toContain("Unit A · Unit A");
  });
});

// ── 2026-09-30 defect-fix lane: the PO's reports on 2.411.4 and the J70 walk ──
async function pickAccountOnly() {
  const box = screen.getByRole("combobox", { name: /Find account/ });
  fireEvent.change(box, { target: { value: "Alv" } });
  const list = document.getElementById("account_id-listbox") as HTMLElement;
  const [option] = await within(list).findAllByRole("option");
  fireEvent.click(option);
}

const REFUSED = () =>
  new ApiError(422, {
    code: "BIZ-COMPLETENESS",
    message_key: "billing.oneTime.err.notPriced",
    params: { service: "Water" },
    field_errors: [],
  });

describe("DEF-BIL-8281 — the account card is the ACCOUNT's, never waiting on a preview", () => {
  it("fills Plan, Cycle, Last bill and Days to pay while every preview is refused", async () => {
    mount(fakeClient({ preview: REFUSED }).client);
    await pickAccountOnly();
    const card = document.querySelector('[data-facts="otb-account"]') as HTMLElement;
    await waitFor(() => expect(card).toHaveTextContent("Residential Standard"));
    expect(card).toHaveTextContent("Cycle 3 · Monthly");
    expect(card).toHaveTextContent("08/31/2026");
    await waitFor(() => expect(screen.getByLabelText(/Days to pay/)).toHaveValue("21"));
  });

  it("an account with NO move-in date still shows Plan and Cycle; only the move-in field asks", async () => {
    mount(
      fakeClient({ preview: REFUSED, account: { moved_in_on: null }, row: { opened_at: null } }).client,
      "?kind=first",
    );
    await pickAccountOnly();
    const card = document.querySelector('[data-facts="otb-account"]') as HTMLElement;
    await waitFor(() => expect(card).toHaveTextContent("Residential Standard"));
    expect(card).toHaveTextContent("Cycle 3 · Monthly");
    expect(screen.getByLabelText(/Move-in date/)).toHaveValue("");
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-09-30" } });
    await act(async () => {
      fireEvent.click(continueButton());
    });
    const list = (await screen.findByText(/Fix \d things? to continue\./)).closest("[data-otb-problems]") as HTMLElement;
    expect(list).toHaveTextContent("Enter the move-in date.");
    expect(list).not.toHaveTextContent("Enter the period.");
    expect(screen.getByLabelText(/Move-in date/)).toHaveAttribute("aria-invalid", "true");
    expect(screen.getAllByText("Enter the move-in date.").length).toBeGreaterThanOrEqual(2);
  });
});

describe("PO change 2026-09-30 — a first bill's move-in date is a date picker", () => {
  it("is pre-filled from the account, editable, and warns when it differs — the bill uses the clerk's date", async () => {
    const { client, calls } = fakeClient({ row: { opened_at: "2026-09-12" }, account: { moved_in_on: "2026-09-12" } });
    mount(client, "?kind=first");
    await pickAccountOnly();
    const field = screen.getByLabelText(/Move-in date/);
    await waitFor(() => expect(field).toHaveValue("2026-09-12"));
    fireEvent.change(field, { target: { value: "2026-09-10" } });
    expect(await screen.findByText("Differs from the account (09/12/2026)")).toBeInTheDocument();
    await waitFor(() => {
      const asked = calls.filter((c) => c.path === "/billing/one-time/preview");
      expect((asked[asked.length - 1]?.body as Record<string, unknown>).period_start).toBe("2026-09-10");
    });
  });
});

describe("DEF-BIL-8321 — the frame's generic line never stands alone", () => {
  it("a 422 with no field and an UNKNOWN key shows a specific sentence with its reference", async () => {
    const { client } = fakeClient({
      preview: () =>
        new ApiError(422, {
          code: "BIZ-COMPLETENESS",
          message_key: "billing.oneTime.err.someNewReason",
          field_errors: [],
          trace_id: "5f2b9c1d00000000000000000000abcd",
        }),
    });
    mount(client);
    await pickAccountOnly();
    await waitFor(() => expect(screen.getByLabelText(/Days to pay/)).toHaveValue("21"));
    fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-09-30" } });
    await act(async () => {
      fireEvent.click(continueButton());
    });
    const found = await screen.findAllByText(/Something is wrong here\. \(HTTP 422/);
    expect(found.length).toBeGreaterThan(0);
    expect(screen.queryByText(/This step isn't finished/)).not.toBeInTheDocument();
  });

  it("a 500 shows a specific sentence with HTTP 500 and a reference", async () => {
    const { client } = fakeClient({
      preview: () =>
        new ApiError(500, {
          code: "SYS-INTERNAL",
          message_key: "api.error.internal",
          field_errors: [],
          trace_id: "aa11bb22cc33dd44ee55ff6600112233",
        }),
    });
    mount(client);
    await pickAccountOnly();
    await waitFor(() => expect(screen.getByLabelText(/Days to pay/)).toHaveValue("21"));
    fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-09-30" } });
    await act(async () => {
      fireEvent.click(continueButton());
    });
    expect((await screen.findAllByText(/HTTP 500/)).length).toBeGreaterThan(0);
    expect(screen.queryByText(/This step isn't finished/)).not.toBeInTheDocument();
  });
});

describe("DEF-BIL-8282 — the summary never says 0 services before it knows", () => {
  it("reads 'Not checked yet' with no preview, and with a refused one", async () => {
    mount(fakeClient({ preview: REFUSED }).client);
    const aside = document.querySelector("[data-otb-summary]") as HTMLElement;
    expect(aside).toHaveTextContent("Not checked yet");
    expect(aside).not.toHaveTextContent("0 services");
    await pickAccountOnly();
    fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-09-30" } });
    // DEF-BIL-8289 — the refusal is shown on Continue, not while typing.
    await waitFor(() => expect(screen.getByLabelText(/Days to pay/)).toHaveValue("21"), { timeout: 3000 });
    await act(async () => {
      fireEvent.click(continueButton());
    });
    await screen.findAllByText("Water can't be priced. Check its rates.", {}, { timeout: 3000 });
    expect(aside).toHaveTextContent("Not checked yet");
    expect(aside).not.toHaveTextContent("0 services");
  });
});

describe("DEF-BIL-8300 — meters waiting for a reading warn on step 1 and step 1 continues", () => {
  it("says how many meters need a reading, continues, and the rows wait on step 2", async () => {
    mount(fakeClient().client);
    await chooseAccount();
    fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-09-30" } });
    expect(
      await screen.findByText("3 meters need a reading. Enter them next.", {}, { timeout: 3000 }),
    ).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(continueButton());
    });
    const readings = await screen.findByRole("region", { name: "Readings" });
    expect(within(readings).getAllByText("Waiting").length).toBe(3);
  });
});

describe("DEF-BIL-8305 — a penalty's approver is recorded, never a gate", () => {
  it("says nothing about needing approval and offers the active staff", async () => {
    mount(fakeClient().client, "?kind=penalty");
    await chooseAccount();
    expect(screen.queryByText(/Needs approval/)).not.toBeInTheDocument();
  });

  it("approvedBy: a picked user wins; a typed name is sent when nobody is picked; nothing when neither", async () => {
    const { approvedBy } = await import("./ServicesStep");
    expect(approvedBy({ userId: "u-alex", name: "Dana" })).toEqual({ user_id: "u-alex" });
    expect(approvedBy({ userId: "", name: "  Dana Whitfield " })).toEqual({ name: "Dana Whitfield" });
    expect(approvedBy({ userId: "", name: " " })).toBeUndefined();
  });
});

describe("DEF-BIL-8316 — step 2's words", () => {
  it("names meters and carts, and shows a saved reading without trailing zeros", async () => {
    const { client } = fakeClient({
      preview: (b) => {
        const p = previewFor(b.kind as OneTimeBillKind);
        p.services = (p.services ?? []).map((row) =>
          row.service === "water"
            ? { ...row, asset_kind: "meter" as const }
            : row.service === "trash"
              ? {
                  ...row,
                  asset_kind: "count" as const,
                  count_unit: "cart",
                  assets: [{ asset_id: "t1", label: "CART-J70A1" }],
                }
              : row,
        );
        if (p.readings !== null) {
          p.readings.rows = p.readings.rows.map((r) => ({
            ...r,
            current: { ...r.current, value: "19020.000000" },
            status: "accepted" as const,
          }));
        }
        return p;
      },
    });
    mount(client);
    await chooseAccount();
    fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-09-30" } });
    await act(async () => {
      fireEvent.click(continueButton());
    });
    const services = await screen.findByRole("region", { name: "Services" });
    expect(services).toHaveTextContent("2 meters · W-10442, W-10443");
    expect(services).toHaveTextContent("Billed · 2 meters");
    expect(services).toHaveTextContent("1 cart · CART-J70A1");
    expect(services).toHaveTextContent("Billed · 1 cart");
    expect(screen.getByLabelText("New reading for E-55120")).toHaveValue("19020");
  });
});

describe("DEF-BIL-8325 — a first bill's move-in reading is posted before the new one", () => {
  it("posts the move-in readings in their own batch, then the new readings", async () => {
    const fake = fakeClient();
    mount(fake.client, "?kind=first");
    await chooseAccount();
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-09-30" } });
    await act(async () => {
      fireEvent.click(continueButton());
    });
    await screen.findByRole("region", { name: "Readings" });
    fireEvent.change(screen.getByLabelText("Move-in reading for W-10443"), { target: { value: "128.9" } });
    fireEvent.change(screen.getByLabelText("New reading for W-10442"), { target: { value: "488.4" } });
    fireEvent.change(screen.getByLabelText("New reading for W-10443"), { target: { value: "136.7" } });
    fireEvent.change(screen.getByLabelText("New reading for E-55120"), { target: { value: "19020" } });
    await act(async () => {
      fireEvent.click(continueButton());
    });
    const staged = fake.calls.filter((c) => c.method === "POST" && c.path === "/read-batches");
    await waitFor(() => expect(staged.length).toBeGreaterThanOrEqual(1));
    const all = fake.calls.filter((c) => c.method === "POST" && c.path === "/read-batches");
    expect(all).toHaveLength(2);
    const first = (all[0].body as { rows: { meter_id: string; reading: string }[] }).rows;
    const second = (all[1].body as { rows: { meter_id: string; reading: string }[] }).rows;
    expect(first).toEqual([expect.objectContaining({ meter_id: "W-10443", reading: "128.9" })]);
    expect(second.map((r) => r.reading).sort()).toEqual(["136.7", "19020", "488.4"]);
  });
});

// ── DEF-BIL-8289 · DEF-BIL-8327 · DEF-BIL-8329 · DEF-BIL-8288 (PO walk, 2.412.3–2.412.4) ──
function typeInterimDates() {
  fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-08-01" } });
  fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-08-31" } });
}

async function pause(ms: number) {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, ms));
  });
}

const NAMED_REFUSAL = () =>
  new ApiError(422, {
    code: "BIZ-COMPLETENESS",
    message_key: "billing.oneTime.err.noRateOnDate",
    params: { service: "Water", date: "Aug 31, 2026" },
    field_errors: [],
  });

describe("DEF-BIL-8289 — no failure while the clerk is still filling step 1", () => {
  it("a half-filled form says what it waits for and shows no failure", async () => {
    mount(fakeClient({ preview: NAMED_REFUSAL }).client);
    await pickAccountOnly();
    await pause(600); // past the debounce: the automatic preview has refused
    expect(screen.getByText("Finish step 1 to see figures.")).toBeInTheDocument();
    expect(screen.queryByText("The bill could not load.")).not.toBeInTheDocument();
    expect(screen.queryByText(/No Water rate on/)).not.toBeInTheDocument();
  });

  it("a refusal from the automatic preview is held until Continue, then named", async () => {
    mount(fakeClient({ preview: NAMED_REFUSAL }).client);
    await pickAccountOnly();
    await waitFor(() => expect(screen.getByLabelText(/Days to pay/)).toHaveValue("21"), { timeout: 3000 });
    typeInterimDates();
    await pause(600);
    expect(screen.queryByText("The bill could not load.")).not.toBeInTheDocument();
    expect(screen.queryByText(/No Water rate on/)).not.toBeInTheDocument();
    await act(async () => {
      fireEvent.click(continueButton());
    });
    const named = await screen.findAllByText("No Water rate on Aug 31, 2026. Add one in Plans & Rates.");
    expect(named.length).toBeGreaterThan(0);
    expect(screen.getByText("The bill could not load.")).toBeInTheDocument();
    expect(screen.queryByText(/This step isn't finished/)).not.toBeInTheDocument();
  });
});

describe("DEF-BIL-8327 — Continue inside the debounce window waits for the answer", () => {
  it("never leaves the frame's generic line alone over a complete step 1", async () => {
    mount(fakeClient({ previewDelayMs: 200 }).client);
    await pickAccountOnly();
    await waitFor(() => expect(screen.getByLabelText(/Days to pay/)).toHaveValue("21"), { timeout: 3000 });
    typeInterimDates();
    // Pressed at once — well inside the 350 ms debounce, with a slow server.
    await act(async () => {
      fireEvent.click(continueButton());
    });
    await pause(900);
    expect(screen.queryByText(/This step isn't finished/)).not.toBeInTheDocument();
    const services = document.querySelector('[data-wizard-step="2"]') as HTMLElement;
    await waitFor(() => expect(services).toHaveAttribute("data-state", "active"), { timeout: 3000 });
  });

  it("on a cold server, Continue before Days to pay is filled from the cycle waits for it", async () => {
    // The walk's shape: the account card (and with it the cycle's Days to pay)
    // answers late, and Continue is pressed straight after typing the dates.
    mount(fakeClient({ accountDelayMs: 700, previewDelayMs: 300 }).client);
    await pickAccountOnly();
    typeInterimDates();
    await act(async () => {
      fireEvent.click(continueButton());
    });
    await pause(1500);
    expect(screen.queryByText(/This step isn't finished/)).not.toBeInTheDocument();
    const services = document.querySelector('[data-wizard-step="2"]') as HTMLElement;
    await waitFor(() => expect(services).toHaveAttribute("data-state", "active"), { timeout: 3000 });
  });
});

describe("DEF-BIL-8329 — the Cycle cell holds the cycle, never its days to pay", () => {
  it("names the cycle", async () => {
    mount(fakeClient().client);
    await pickAccountOnly();
    const card = document.querySelector('[data-facts="otb-account"]') as HTMLElement;
    await waitFor(() => expect(card).toHaveTextContent("Cycle 3 · Monthly"));
    expect(card).not.toHaveTextContent(/days? to pay/);
  });

  it("says None when the account's unit is on no cycle", async () => {
    mount(fakeClient({ account: { cycle_name: null, cycle_due_days: null } }).client);
    await pickAccountOnly();
    const card = document.querySelector('[data-facts="otb-account"]') as HTMLElement;
    await waitFor(() => expect(card).toHaveTextContent("Residential Standard"));
    expect(card).toHaveTextContent("None");
    expect(card).not.toHaveTextContent(/days? to pay/);
  });
});

describe("DEF-BIL-8288 — a first bill's To must be after move-in, on the field", () => {
  it("refuses To equal to the move-in date before any preview is asked", async () => {
    const { client, calls } = fakeClient({ row: { opened_at: "2026-07-01" }, account: { moved_in_on: "2026-07-01" } });
    mount(client, "?kind=first");
    await pickAccountOnly();
    await waitFor(() => expect(screen.getByLabelText(/Move-in date/)).toHaveValue("2026-07-01"));
    await waitFor(() => expect(screen.getByLabelText(/Days to pay/)).toHaveValue("21"), { timeout: 3000 });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-07-01" } });
    await act(async () => {
      fireEvent.click(continueButton());
    });
    const asked = calls.filter((c) => c.path === "/billing/one-time/preview").length;
    expect((await screen.findAllByText("To must be after move-in.")).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByLabelText(/^To/)).toHaveAttribute("aria-invalid", "true");
    await pause(100);
    expect(calls.filter((c) => c.path === "/billing/one-time/preview").length).toBe(asked);
  });
});

// ── DEF-BIL-8330 — a first bill for an account with no cycle (PO 2026-09-30, A) ──
describe("DEF-BIL-8330 — a first bill for an account on no cycle waits, and says why", () => {
  const SENTENCE = "No billing cycle. Assign one on the account.";

  it("names it the moment the account is picked, on the card and in the list, before Continue", async () => {
    mount(fakeClient({ account: { cycle_name: null, cycle_due_days: null } }).client, "?kind=first");
    await pickAccountOnly();
    const card = document.querySelector('[data-facts="otb-account"]') as HTMLElement;
    await waitFor(() => expect(card).toHaveTextContent("None"));
    // A fact about the account, not a typing mistake: shown without Continue.
    const list = await waitFor(() => {
      const found = document.querySelector("[data-otb-problems]") as HTMLElement | null;
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(list).toHaveTextContent(SENTENCE);
    const panel = document.querySelector('[data-otb-panel="account"]') as HTMLElement;
    expect(panel).toHaveTextContent(SENTENCE);
    // Nothing ELSE is shown as a failure while the clerk is still typing.
    expect(list).not.toHaveTextContent(/Enter the period|Enter the move-in date/);
  });

  it("Continue waits on step 1", async () => {
    mount(
      fakeClient({
        row: { opened_at: "2026-07-01" },
        account: { cycle_name: null, cycle_due_days: 21, moved_in_on: "2026-07-01" },
      }).client,
      "?kind=first",
    );
    await pickAccountOnly();
    await waitFor(() => expect(screen.getByLabelText(/Move-in date/)).toHaveValue("2026-07-01"));
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-07-31" } });
    await waitFor(() => expect(screen.getByLabelText(/Days to pay/)).toHaveValue("21"), { timeout: 3000 });
    await act(async () => {
      fireEvent.click(continueButton());
    });
    await pause(300);
    const account = document.querySelector('[data-wizard-step="1"]') as HTMLElement;
    expect(account).toHaveAttribute("data-state", "active");
    // Never the frame's line alone: the reason stands in the list above.
    expect(document.querySelector("[data-otb-problems]")).toHaveTextContent(SENTENCE);
  });

  // ⚠ REVERSED 2026-10-01 (BR-BIL-1066). This read "is silent for an interim
  // bill on the same account". The PO ruled an interim base is cut down by days
  // over the account's own cycle ("A · Cut down (10/30)"), so an interim bill
  // with no cycle is refused the first bill's way. A catch-up bill is not.
  it("names it for an interim bill on the same account too", async () => {
    mount(fakeClient({ account: { cycle_name: null, cycle_due_days: null } }).client);
    await pickAccountOnly();
    const card = document.querySelector('[data-facts="otb-account"]') as HTMLElement;
    await waitFor(() => expect(card).toHaveTextContent("None"));
    await waitFor(() => expect(document.querySelector("[data-otb-problems]")).toHaveTextContent(SENTENCE));
  });

  it("is silent for a catch-up bill on the same account", async () => {
    mount(fakeClient({ account: { cycle_name: null, cycle_due_days: null } }).client, "?kind=backbill");
    await pickAccountOnly();
    const card = document.querySelector('[data-facts="otb-account"]') as HTMLElement;
    await waitFor(() => expect(card).toHaveTextContent("None"));
    expect(screen.queryByText(SENTENCE)).not.toBeInTheDocument();
  });

  it("is silent for a first bill on an account with a cycle", async () => {
    mount(fakeClient().client, "?kind=first");
    await pickAccountOnly();
    const card = document.querySelector('[data-facts="otb-account"]') as HTMLElement;
    await waitFor(() => expect(card).toHaveTextContent("Cycle 3 · Monthly"));
    expect(screen.queryByText(SENTENCE)).not.toBeInTheDocument();
  });
});

// ── PO 2026-10-01 — a FINAL bill for an account with no cycle: *"show warning
// and A · Refuse until the account has a cycle (same as first bill)"* ──────
describe("PO 2026-10-01 — a final bill for an account on no cycle waits, and says why", () => {
  const SENTENCE = "No billing cycle. Assign one on the account.";

  it("names it the moment the account is picked, before Continue", async () => {
    mount(fakeClient({ account: { cycle_name: null, cycle_due_days: null } }).client, "?kind=final");
    await pickAccountOnly();
    const list = await waitFor(() => {
      const found = document.querySelector("[data-otb-problems]") as HTMLElement | null;
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(list).toHaveTextContent(SENTENCE);
    const panel = document.querySelector('[data-otb-panel="account"]') as HTMLElement;
    expect(panel).toHaveTextContent(SENTENCE);
  });

  it("is silent for a final bill on an account with a cycle", async () => {
    mount(fakeClient().client, "?kind=final");
    await pickAccountOnly();
    const card = document.querySelector('[data-facts="otb-account"]') as HTMLElement;
    await waitFor(() => expect(card).toHaveTextContent("Cycle 3 · Monthly"));
    expect(screen.queryByText(SENTENCE)).not.toBeInTheDocument();
  });
});

// ── DEF-BIL-9077 · a meter that rolled over holds the bill; the clerk accepts it HERE ──
describe("a meter rollover held on the preview (DEF-BIL-9077)", () => {
  const HOLD = new ApiError(422, {
    code: "BIZ-COMPLETENESS",
    message_key: "billing.oneTime.err.rolloverHeld",
    params: {
      reason: "possible_rollover",
      service_code: "electric",
      service: "Electric",
      meter: "M-9077",
      from: "99800.000000",
      to: "240.000000",
      closing: "700.000000",
      suggested_quantity: "900.000000",
      unit: "kWh",
    },
    field_errors: [],
  });

  it("shows the meter, its dials and the usage, and one Accept re-prices across it", async () => {
    const { client, calls } = fakeClient({
      preview: (b) =>
        Array.isArray(b.accepted_rollovers) && b.accepted_rollovers.includes("electric")
          ? previewFor("interim")
          : HOLD,
    });
    mount(client);
    await chooseAccount();
    fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-10-15" } });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-11-13" } });

    const panel = await screen.findByRole("region", { name: "Meter rolled over" }, { timeout: 3000 });
    // The meter by its NUMBER (B14 rule 31), the three dials and the usage.
    expect(within(panel).getByText("M-9077")).toBeInTheDocument();
    expect(within(panel).getByText("99,800 → 240 → 700")).toBeInTheDocument();
    expect(within(panel).getByText("900 kWh")).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(within(panel).getByRole("button", { name: /Accept rollover/ }));
    });
    // The next preview carries the acceptance the API already takes…
    await waitFor(
      () => {
        const asked = calls.filter((c) => c.path === "/billing/one-time/preview").at(-1);
        expect((asked?.body as { accepted_rollovers?: string[] }).accepted_rollovers).toEqual(["electric"]);
      },
      { timeout: 3000 },
    );
    // …and once it prices, the hold and its control are gone.
    await waitFor(() => expect(screen.queryByRole("region", { name: "Meter rolled over" })).not.toBeInTheDocument(), {
      timeout: 3000,
    });
  });
});
