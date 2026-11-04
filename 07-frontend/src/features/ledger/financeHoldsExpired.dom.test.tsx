// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-LED-6662 (Revenue & AR's *"↓ Download period pack"* refused over
//          an export batch that had shipped) · DEF-LED-6664 (the batch journal
//          screen was routed, tested and reachable by nobody) ·
//          DEF-LED-6663 (Close & export → Export said *"Closed through
//          September."* over an OPEN September) · DEF-LED-6668 (a closed month
//          told the System Admin who closed it that their ROLE could not).
// Drawing: 05-prototype/07 Finance Blueprint.pdf — **p030** DOORS row
//          (*"Two — `+ Journal entry` on 1·1 · the ✎ row action on a draft"*) ·
//          **p069** (the Export head) · **p068** (step 2's commit).
// Rules:   CLAUDE.md hard-won law 2 and its MIRROR — *"when you write a hold,
//          write the test that fires when the hold expires, in the same commit
//          — assert the destination by ADDRESS and by the SCREEN ID it opens"*
//          · BR-SHL-025 (a control that cannot act says WHY, and the why is
//          true) · B14 rule 31 (no database id is a visible value).
// ───────────────────────────────────────────────────────
/*
THIS FILE IS THE ROT ALARM FOR FOUR HOLDS THAT ALREADY ROTTED ONCE.

Every one of the four was a rule with a clock in it — correct on the day it was
written, false on the day the thing it pointed at landed — and every one of
them survived `tsc`, every gate and 191 front-end cases, because **nothing in
this repository reads a rendered `title` or asks whether a REFUSAL is still
true.** All four were found by a person opening a screen.

WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first, per hard-won law 7
---------------------------------------------------------------------------
**(a) ASSERTING ONLY THE GOOD STATE.** A case that proved the period pack is a
link when a batch exists would be satisfied by a control that is ALWAYS a link,
including over a tenant that has handed nothing over — which is the same
untrue-sentence defect pointing the other way. Both states are asserted, from
the same component, with the only difference being the fixture's batch list.

**(b) A BARE `MemoryRouter` WITH NO `/:tenant` ROUTE.** `useTenantPath` then
builds `//finance/...` — a protocol-relative URL to ANOTHER HOST that reads as
a perfectly good string to `toContain`. CLAUDE.md records this costing the
customer portal eight doors. Every mount here is under the real path pattern
and the door case asserts the href STARTS WITH `/brazosbend/`.

**(c) ASSERTING AN ADDRESS AND NOTHING ELSE.** A hold-expiry test once asserted
a screen was REGISTERED at an address while the router mounted it somewhere
else, and both opened onto *"not built yet"*. So the journal door case mounts
the DESTINATION ROUTE TOO and asserts a string only `JournalBatchPage` renders
— *"New journal entries"* — after clicking the control a clerk clicks.

**(d) A FIXTURE THAT CANNOT TELL AN OPEN MONTH FROM A CLOSED ONE.** The head
cases would pass over a rollup hard-coded either way if only one were tested.
`closed` is flipped on ONE field of ONE fixture and both sentences are asserted.

**(e) READING A DISABLED BUTTON'S TEXT INSTEAD OF ITS `title`.** The whole of
DEF-LED-6668 is that the button was CORRECTLY disabled and the SENTENCE was
wrong. Nothing here asserts `disabled` alone; every case reads the `title`.
*/
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { CloseExportPage } from "./CloseExportPage";
import { GeneralLedgerPage } from "./GeneralLedgerPage";
import { JournalBatchPage } from "./JournalBatchPage";
import { RevenueArPage } from "./RevenueArPage";

afterEach(cleanup);

const TENANT = "brazosbend";
const PERIOD = { start: "2026-09-01", end: "2026-09-30" };

/** A batch whose window CONTAINS the open period — the pack that exists. */
const COVERING_BATCH = {
  batch_id: "b-9f2e",
  batch_no: "EXP-2609-0001",
  period: PERIOD,
  target: "qbo",
  granularity: "summary",
  entries: 12,
  total_debits: "15191.000000",
  total_credits: "15191.000000",
  currency: "USD",
  content_hash: "9f2ea1c4b70d55",
  created_at: "2026-10-01T09:00:00Z",
  created_by_user_id: "u-1",
};

/**
 * One fixture for every Finance screen in this file.
 *
 * `role` and `batches` are the only two knobs, because they are the only two
 * facts the four defects turn on: WHO is asking, and WHETHER anything has been
 * handed over. Everything unrecognised answers a SHAPED empty — named `rows`,
 * `results`, `items`, `problems` and `unavailable` — because a screen that
 * threw on an unrelated read would fail here for a reason that teaches nobody
 * anything, which two sibling files have each recorded costing an evening.
 */
function fixture(opts: {
  closed?: boolean;
  role?: string;
  batches?: unknown[];
} = {}) {
  const calls: string[] = [];
  const client = {
    get: async (path: string, init?: { query?: Record<string, unknown> }) => {
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(init?.query ?? {})) {
        if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
      }
      calls.push(query.toString() === "" ? path : `${path}?${query.toString()}`);

      if (path.startsWith("/shell/display")) {
        return { data: { period: { ...PERIOD, fy_label: "FY2026", period: 12, status: "open" } } };
      }
      // ⚠ `/me/permissions` BEFORE `/me` — `startsWith("/me")` swallows both,
      // and answering the permissions read with `{id}` hands `accessCell` an
      // undefined `.permissions` to call `.find` on, which throws INSIDE
      // render and replaces the whole screen.
      if (path.startsWith("/me/permissions")) {
        return {
          data: {
            role: opts.role ?? "system_admin",
            permissions: [{ code: "finance_reconcile_export", access: "Full" }],
          },
        };
      }
      if (path.startsWith("/me")) return { data: { id: "u-1" } };
      // ⚠ **REVENUE & AR READS ITS PERIOD FROM `/settings/regional`, NOT
      // `/shell/display`.** Two Finance screens, two reads, one fact — and a
      // fixture answering only the second leaves `period === null`, which
      // renders *"Set the fiscal year start…"* and no page head at all. The
      // case then fails for a fixture fault wearing a product fault's clothes.
      if (path.startsWith("/settings/regional")) {
        return {
          data: {
            country: "US", state: "TX", timezone: "America/Chicago",
            language: "en", currency: "USD",
            current_period: { ...PERIOD, fy_label: "FY2026", period: 12,
              status: "open", close_by: null },
          },
        };
      }
      if (path.startsWith("/finance/close-checklist")) {
        return {
          data: {
            period: PERIOD,
            items: [
              { code: "batches_reconciled", state: "complete", complete: true, detail: "",
                wanted_reads: [], outstanding: null, amount: null },
              { code: "bank_rec_current", state: "incomplete", complete: false, detail: "",
                wanted_reads: [], outstanding: 3, amount: null },
            ],
            incomplete: opts.closed === true ? [] : ["bank_rec_current"],
            ready: opts.closed === true,
            closed: opts.closed === true,
            unavailable: [],
            closed_periods: [],
            currency: "USD",
          },
        };
      }
      if (path.startsWith("/finance/export/batches")) {
        return { data: { rows: opts.batches ?? [], currency: "USD", count: 0, targets: ["qbo"] } };
      }
      // ⚠ **A SHAPED EMPTY, NOT `{}`.** `revenueArKpis` reads `report.kpis
      // .billed` unguarded and `BadDebtCaveats` calls `.length` on `problems`,
      // so an over-general answer throws INSIDE render, React Router replaces
      // the whole screen, and the failure reads *"the control is missing"* —
      // a fixture fault wearing a product fault's clothes. Watched here, not
      // predicted.
      return {
        data: {
          rows: [], results: [], count: 0, unavailable: [], items: [], problems: [],
          totals: {}, currency: "USD", basis: "issued", period: PERIOD,
          revenue_by_service: [], aging: null,
          cash: { basis: "issued", realised: "0.0000", undeposited: "0.0000" },
          adjustments: {
            basis: "issued", credits_issued: "0.0000", debits_posted: "0.0000",
            late_fees_applied: null, net: "0.0000", pending_approval: null,
            unavailable: [],
          },
          tie_out: { ar_control: "0.0000", computed_by: null },
          kpis: {
            billed: "0.0000", collected: "0.0000", still_owed: "0.0000",
            collected_from_cash: "0.0000", collected_from_applied_deposits: "0.0000",
            accounts_owing: 0, collection_pct: null, dso: null,
            written_off_ytd: null,
          },
        },
      };
    },
    post: async () => ({ data: {} }),
    patch: async () => ({ data: {} }),
    put: async () => ({ data: {} }),
    delete: async () => ({ data: {} }),
  } as unknown as ApiClient;
  return { client, calls };
}

function mount(at: string, routes: Array<[string, React.ReactElement]>) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={[at]}>
          <Routes>
            {routes.map(([path, element]) => (
              <Route key={path} path={path} element={element} />
            ))}
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-LED-6662 · the period pack's refusal is derived from the books", () => {
  function drawRevenue(batches: unknown[]) {
    const { client } = fixture({ batches });
    return mount(`/${TENANT}/finance/revenue`, [
      ["/:tenant/finance/revenue", <RevenueArPage client={client} />],
    ]);
  }

  it("is a REAL DOWNLOAD when a handed-over batch covers the open period", async () => {
    drawRevenue([COVERING_BATCH]);
    const link = await screen.findByTestId("download-period-pack");
    // BY ADDRESS: the batch file endpoint, tenant-scoped, absolute.
    expect(link.getAttribute("href")).toBe(
      `/api/${TENANT}/finance/export/batches/${COVERING_BATCH.batch_id}/file`,
    );
    // (b) — a protocol-relative `//…` would satisfy a `toContain`; this cannot.
    expect(link.getAttribute("href")?.startsWith(`/api/${TENANT}/`)).toBe(true);
    expect(link).toHaveAttribute("download");
    expect(link.textContent).toContain("Download period pack");
    // B14 rule 31 — the batch id is in the href and on no screen.
    expect(link.textContent).not.toContain(COVERING_BATCH.batch_id);
  });

  it("still refuses when nothing has been handed over — but says THAT, not that the pack is unbuilt", async () => {
    drawRevenue([]);
    const control = await screen.findByRole("button", { name: /Download period pack/ });
    expect(control).toBeDisabled();
    // The sentence that rotted, asserted ABSENT by its own words. This is the
    // assertion that would have failed for the eleven days DEF-LED-6662 was live.
    expect(control.getAttribute("title")).not.toContain("not built");
    expect(control.getAttribute("title")).toBe("No month has been handed over yet.");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-LED-6664 · '+ Journal entry' opens the batch screen", () => {
  it("goes to the ADDRESS, and that address opens the SCREEN (law 2's own words)", async () => {
    const { client } = fixture();
    mount(`/${TENANT}/finance`, [
      ["/:tenant/finance", <GeneralLedgerPage client={client} />],
      ["/:tenant/finance/journal-entries/new", <JournalBatchPage client={client} />],
    ]);
    const open = await screen.findByTestId("open-journal-entry");
    expect(open.textContent).toContain("Journal entry");
    await userEvent.click(open);

    // ⚠ **(c) — THE SCREEN, NOT THE ADDRESS.** A route registered at one
    // address while the router mounts it at another passes an address-only
    // check and opens onto nothing. *"New journal entries"* is
    // `finance.batch.title` and no other Finance screen renders it.
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "New journal entries" })).toBeInTheDocument();
    });
    // And the modal it replaces is NOT what opened.
    expect(screen.queryByText("Manual journal entry")).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-LED-6663 · the Export head states what the BOOKS say", () => {
  function drawExport(closed: boolean) {
    const { client } = fixture({ closed });
    return mount(`/${TENANT}/finance/export?view=export`, [
      ["/:tenant/finance/export", <CloseExportPage client={client} />],
    ]);
  }

  it("does NOT claim the month is closed through while it is open", async () => {
    drawExport(false);
    expect(await screen.findByRole("heading", { name: "Export" })).toBeInTheDocument();
    // The exact sentence a clerk read on 2026-09-24, ten lines above the
    // hand-over panel's "This month is still open."
    expect(screen.queryByText("Closed through September.")).toBeNull();
    expect(screen.getByText(/September is open\./)).toBeInTheDocument();
  });

  it("DOES say it once the books say it", async () => {
    drawExport(true);
    expect(await screen.findByText("Closed through September.")).toBeInTheDocument();
    expect(screen.queryByText(/September is open\./)).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-LED-6668 · a closed month is not a role refusal", () => {
  function drawClose(opts: { closed: boolean; role?: string }) {
    const { client } = fixture(opts);
    return mount(`/${TENANT}/finance/export?view=close`, [
      ["/:tenant/finance/export", <CloseExportPage client={client} />],
    ]);
  }

  const ROLE_SENTENCE = "Your role cannot close an accounting period.";

  it("tells a System Admin the month is closed, not that their role is wrong", async () => {
    drawClose({ closed: true, role: "system_admin" });
    const button = await screen.findByRole("button", { name: /Close September/ });
    expect(button).toBeDisabled();
    // The defect, in one line: this was the role sentence.
    expect(button.getAttribute("title")).not.toBe(ROLE_SENTENCE);
    expect(button.getAttribute("title")).toBe("The month is closed.");
    // Step 2's note stated what was still undone over a month already closed.
    expect(screen.queryByText(/You can still close/)).toBeNull();
  });

  it("STILL says the role sentence to a role that genuinely may not close", async () => {
    // ⚠ **WITHOUT THIS THE CASE ABOVE COULD PASS WRONGLY**: deleting the role
    // reason entirely would satisfy it. `apps/ledger/close.close_period` is
    // System Admin + Billing Clerk (ruled 2026-09-24); a meter reader is
    // neither, and BR-SHL-025 says they see the control DISABLED WITH ITS
    // REASON rather than not at all.
    drawClose({ closed: false, role: "meter_reader" });
    const button = await screen.findByRole("button", { name: /Close September/ });
    expect(button).toBeDisabled();
    expect(button.getAttribute("title")).toBe(ROLE_SENTENCE);
  });

  it("offers the close to a Billing Clerk, which is the other role the service allows", async () => {
    drawClose({ closed: false, role: "billing_clerk" });
    const button = await screen.findByRole("button", { name: /Close September/ });
    expect(button).not.toBeDisabled();
    expect(button.getAttribute("title")).toBeNull();
  });
});
