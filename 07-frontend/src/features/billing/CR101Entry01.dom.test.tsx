// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-101-BRC03 lane 01 — blueprint §02 entry 01 "All bills"
//           (`/:tenant/billing` · second address `/:tenant/billing/all` ·
//           S30 · BIL-01), built from the REDESIGN drawn on p007 of
//           `05-prototype/04 Billing, As Built.pdf` (default branch
//           `claude/confirm-understanding-3ktufc`, blob sha256
//           137a2a48…0971). B14 rule 42: the drawing was read AS AN IMAGE.
//           Screens: S30 · BIL-01, and the Print bills screen it now tabs to
// Rules:    PO ruling 2026-09-12 #10, verbatim *"We will need Print bills as
//           tab at Billing level"* (12-governance/02-decision-log.md) ·
//           B14 rule 32 (a stated absence is a disclosure CLOSED by default) ·
//           B14 rule 33 (rationale is ZERO WORDS ON SCREEN) · B14 rule 16 (the
//           list table's toolbar, footer and empty state) · A12 (money cells
//           right-aligned) · BR-SHL-011 (URL grammar + fallback law)
// Defects:  DEF-BIL-5231 (the header roll-up is served on ONE of six tabs)
// Tests:    this file
// ───────────────────────────────────────────────────────
/**
 * The four guards entry 01 needed, each proved RED before the build.
 *
 * ⚠ **THE FALSE PASS THIS FILE WAS WRITTEN AROUND, because it is the one that
 * nearly shipped.** The obvious way to test the header roll-up on a non-All
 * tab is to seed the query cache and assert the number renders. **That passes
 * on the BROKEN code**: `useQuery({ enabled: false })` still returns whatever
 * is in the cache, so a seeded test proves nothing about whether the client
 * ever asked. So the roll-up guard below uses a RECORDING CLIENT and asserts
 * two separate things — that `GET /invoices` was actually requested while the
 * Fix-a-bill tab was mounted, and that the served figure reached the screen.
 * Seed nothing.
 */
import "@testing-library/jest-dom/vitest";

import { afterEach, describe, expect, it } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import en from "@/i18n/locales/en.json";

import { BillsListPage } from "./BillsListPage";
import { PrintBillsPage, BILLING_PRINT_ROUTE } from "./PrintBillsPage";
import { BILLING_TABS, BILLING_TAB_ALL, billingTabFrom } from "./billingShared";

afterEach(cleanup);

const TENANT = "brazosbend";
const catalog = en as unknown as Record<string, string>;
const t = (key: string) => catalog[key] ?? key;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * The seeded tenant's real shape, rounded to what this file asserts: the LIST
 * envelope carries the roll-up the header reads. ⚠ B14 rule 37 — the drawing's
 * `7240` / `$342,180.00` / `3` are ILLUSTRATIONS and none of them is seeded
 * here. These are this fixture's own numbers.
 */
const ROLLUP = {
  bills: 92,
  billed_this_cycle: null,
  billed_currency: null,
  unresolved_from_last_run: 4,
};

/**
 * ONE issued row with `past_due: null` — the deployment state DEF-967 covers,
 * and the condition the disclosure and its ⓘ are both derived from. ⚠ B14 rule
 * 37: every figure here is this fixture's own, not the drawing's.
 */
const ROWS = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    invoice_no: "BL-2609-000001",
    bill_type: "cyclical",
    status: "issued",
    past_due: null,
    account_id: "22222222-2222-4222-8222-222222222222",
    account_no: "100244",
    customer_name: "R. Alvarez",
    cycle_label: "09-A",
    bill_run_id: null,
    service_date: "2026-09-01",
    period_start: "2026-08-01",
    period_end: "2026-08-31",
    issued_at: "2026-09-05T00:00:00Z",
    due_date: "2026-09-25",
    subtotal: "80.000000",
    tax_total: "4.000000",
    total: "84.000000",
    currency: "USD",
    template_version: 1,
  },
];

function recordingClient(calls: string[]) {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input) => {
      const url = typeof input === "string" ? input : String(input);
      const path = url.split("?")[0];
      calls.push(path);
      if (path.endsWith("/me/permissions")) {
        return json({
          role_name: "Billing Clerk",
          permissions: [
            { code: "reads_billing_runs", label: "Reads & Billing runs", access: "Full" },
          ],
        });
      }
      if (path.endsWith("/corrections/reasons")) {
        // ⚠ The Fix-a-bill tab CRASHES on a bare list envelope, and a crashed
        // tree renders an empty body — which reads exactly like "the header did
        // not render". The header guard below would then have failed for the
        // wrong reason, proving nothing. Answered properly so the only thing
        // this file can fail on is the header.
        return json({
          reasons: [],
          classes: [],
          routed_elsewhere: [],
          scope_kinds: [],
          approver_role: "Billing Supervisor",
          approval_mode: null,
          approval_mode_unavailable: null,
          backbill_window_months: null,
          backbill_window_unavailable: null,
          unavailable: [],
        });
      }
      if (path.endsWith("/invoices")) {
        return json({ count: 92, next: null, previous: null, results: ROWS, rollup: ROLLUP });
      }
      return json({ count: 0, next: null, previous: null, results: [] });
    },
  });
}

function mount(path: string, calls: string[]) {
  const client = recordingClient(calls);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}${path}`]}>
          <Routes>
            {/* The order App.tsx mounts them in — the STATIC segment first, or
                `print` is read as a tab id. Mounting these any other way is the
                fixture that cannot tell a working link from a broken one. */}
            <Route path="/:tenant/billing/print" element={<PrintBillsPage client={client} />} />
            <Route path="/:tenant/billing" element={<BillsListPage client={client} />} />
            <Route path="/:tenant/billing/:tab" element={<BillsListPage client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CR-101 entry 01 · the seventh tab (PO ruling 2026-09-12 #10)", () => {
  it("the strip is SEVEN wide and `Print bills` is the seventh", () => {
    expect(BILLING_TABS.map((tab) => t(tab.labelKey))).toEqual([
      "All bills",
      "Run bills",
      "One-time bill",
      "Budget Bills",
      "Fix a bill",
      "Past billing runs",
      "Print bills",
    ]);
    expect(BILLING_TABS[6].id).toBe("print");
    // BR-SHL-011's fallback law still holds, and `print` is now a known id.
    expect(billingTabFrom("print")).toBe("print");
    expect(billingTabFrom("nonsense")).toBe(BILLING_TAB_ALL);
  });

  it("the seventh tab's ADDRESS opens the Print bills screen, not a tab body", async () => {
    // Hard-won law 2's mirror: assert the destination by ADDRESS *and* by the
    // screen it opens. `/billing/print` must reach PrintBillsPage — if the
    // static route ever loses its precedence over `billing/:tab`, this fails
    // instead of quietly rendering an empty All-bills table.
    const calls: string[] = [];
    mount(BILLING_PRINT_ROUTE, calls);
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      t("billing.print.title"),
    );
  });

  it("the Print bills screen carries the Billing strip with the seventh tab selected", async () => {
    const calls: string[] = [];
    mount(BILLING_PRINT_ROUTE, calls);
    const tab = await screen.findByRole("tab", { name: t("billing.tab.print") });
    expect(tab).toHaveAttribute("aria-selected", "true");
    // …and the other six are reachable from it, or the tab is a one-way door.
    expect(screen.getByRole("tab", { name: t("billing.tab.all") })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });
});

describe("CR-101 entry 01 · DEF-BIL-5231 — the header belongs to the SCREEN, not the tab", () => {
  it("asks the server for the roll-up while a tab other than All bills is mounted", async () => {
    const calls: string[] = [];
    mount("/billing/fix", calls);
    await waitFor(() => {
      expect(calls.some((path) => path.endsWith("/invoices"))).toBe(true);
    });
  });

  it("renders the served lifetime count on the Fix-a-bill tab", async () => {
    const calls: string[] = [];
    mount("/billing/fix", calls);
    // Nothing is seeded, so a `92` on screen can only have come from the wire.
    expect(await screen.findByText("92")).toBeInTheDocument();
    expect(screen.getByText(t("billing.rollup.bills"))).toBeInTheDocument();
  });

  it("no roll-up sentence claims the SERVER has not counted", () => {
    // The client never asked; saying "nothing serves that list yet" told a
    // clerk a falsehood about the deployment. `GET /invoices` has been served
    // since 2026-08-14 and answers `count: 92` on this tenant.
    for (const key of [
      "billing.rollup.billsWhy",
      "billing.rollup.thisCycleWhy",
      "billing.rollup.unresolvedWhy",
    ]) {
      expect(t(key)).not.toMatch(/nothing serves that list yet/i);
      expect(t(key)).not.toMatch(/no count is shown/i);
    }
  });
});

describe("CR-101 entry 01 · legend 3 — the unresolved count becomes the door", () => {
  it("the served figure is a link to the pending queue", async () => {
    const calls: string[] = [];
    mount("/billing", calls);
    const link = await screen.findByRole("link", {
      name: new RegExp(t("billing.rollup.unresolved"), "i"),
    });
    expect(link).toHaveAttribute("href", `/${TENANT}/billing/pending`);
    expect(link).toHaveTextContent("4");
  });
});

describe("CR-101 entry 01 · legend 1 — the past-due note, collapsed and moved", () => {
  it("B14 rule 32: it is a <details> CLOSED by default, below the table", async () => {
    const calls: string[] = [];
    const { container } = mount("/billing", calls);
    await screen.findByRole("table");
    const disclosure = container.querySelector<HTMLDetailsElement>(
      'details[data-bil="past-due-unknown"]',
    );
    expect(disclosure).not.toBeNull();
    expect(disclosure?.open).toBe(false);
    expect(disclosure?.querySelector("summary")?.textContent?.trim()).toBe(
      t("billing.bills.pastDueSummary"),
    );
    // Drawn BELOW the table. jsdom lays nothing out, so this is document
    // ORDER — which is the half that decides reading order anyway.
    const table = container.querySelector("table");
    expect(
      table && disclosure
        ? table.compareDocumentPosition(disclosure) & Node.DOCUMENT_POSITION_FOLLOWING
        : 0,
    ).toBeTruthy();
  });

  it("the drawn summary, character for character", () => {
    expect(t("billing.bills.pastDueSummary")).toBe("Why no bill is marked past due");
  });

  it("an ⓘ marker sits on the Status header, where the fact bites", async () => {
    const calls: string[] = [];
    const { container } = mount("/billing", calls);
    await screen.findByRole("table");
    const headers = [...container.querySelectorAll("thead th")];
    const status = headers.find((th) =>
      (th.textContent ?? "").toUpperCase().includes(t("billing.bills.col.status").toUpperCase()),
    );
    expect(status).toBeDefined();
    expect(status?.querySelector("[data-header-note]")).not.toBeNull();
  });
});
