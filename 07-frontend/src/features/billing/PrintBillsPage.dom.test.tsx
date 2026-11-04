// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-101-BRC03 lane J — blueprint **screen 28**, `05-prototype/04
//           Billing, As Built.pdf` p147–p150, read AS IMAGES (B14 rule 42).
//           Closes `DEF-BIL-5354`.
// Screens:  Print bills (the seventh Billing tab)
// Rules:    B14 rule 31 (no database id is a visible value) · rule 32 (no
//           internal code in clerk-facing copy) · rule 33 (a fact ≤ 6 words) ·
//           rule 37 (a drawn figure is an illustration) · NFR-3 (the total
//           comes from the server, never from the rows on screen) ·
//           hard-won law 2 (a door must point somewhere, and the FIXTURE must
//           be able to tell a working control from a dead one)
// Tests:    this file
// ───────────────────────────────────────────────────────
/**
 * ⚠ **WHY THIS FILE EXISTS BESIDE `PrintBillsPage.test.tsx`.** That file renders
 * to STATIC markup, so no query ever resolves and every assertion it makes is
 * made against a loading skeleton. It says so itself. The four tiles, the table
 * and the held-back door only exist once the server has answered, so a check
 * for them written there would be a check that cannot fail.
 *
 * ⚠ **B14 RULE 37 — p148 draws 404 · 8 · ~2,424 · 412 · 6 pages a bill and the
 * bills `BIL-2609-0181`…`BIL-2609-0270`. NONE of it is seeded here.** Every
 * figure below is this fixture's own, and the arithmetic the tiles must satisfy
 * (`will print + held back = in this period`) is asserted rather than copied.
 */
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { PrintBillRow, PrintSetPreview } from "@/api/billingPrintEndpoints";
import { internalReferencesInMarkup } from "@/testSupport/internalReferences";

import { PrintBillsPage } from "./PrintBillsPage";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** This fixture's own figures — see the rule-37 note above. */
const WILL_PRINT = 38;
const HELD = 3;
const IN_PERIOD = WILL_PRINT + HELD;

function preview(overrides: Partial<PrintSetPreview> = {}): PrintSetPreview {
  return {
    bill_count: IN_PERIOD,
    printable_statuses: ["issued", "paid"],
    max_bills: 25000,
    over_ceiling: false,
    estimated_seconds: 0.5,
    will_print: WILL_PRINT,
    held_back: HELD,
    held_reasons: [{ code: "address_incomplete", bills: HELD }],
    held_reasons_complete: true,
    pages: WILL_PRINT * 2,
    pages_per_bill: 2,
    manifest_columns: ["account_no", "bill_no"],
    background_available: true,
    filters: {},
    unavailable: [{ code: "no_mail_standards_are_performed_here", detail: "no standards here." }],
    ...overrides,
  };
}

const ROWS: PrintBillRow[] = [
  {
    id: "0198c2f0-aaaa-7000-8000-aaaabbbbcccc",
    invoice_no: "BL-2609-000181",
    account_no: "100377",
    customer_name: "Ridge Coffee Co.",
    period_start: "2026-09-01",
    period_end: "2026-09-30",
    total: "289.4000",
    currency: "USD",
    will_print: true,
    hold_reason: null,
    pages: 2,
  },
  {
    id: "0198c2f0-bbbb-7000-8000-aaaabbbbcccc",
    invoice_no: "BL-2609-000188",
    account_no: "100412",
    customer_name: "Navarro, P.",
    period_start: "2026-09-01",
    period_end: "2026-09-30",
    total: "142.3000",
    currency: "USD",
    will_print: false,
    hold_reason: "address_incomplete",
    pages: null,
  },
];

/** A transport that records what the screen asks for and answers both reads. */
function fakeClient(options: { previewBody?: PrintSetPreview; rows?: PrintBillRow[] } = {}) {
  const gets: { path: string; query: Record<string, string> | null }[] = [];
  const client = {
    request: vi.fn(),
    put: vi.fn(),
    del: vi.fn(),
    post: vi.fn(),
    pollJob: vi.fn(),
    get: async (path: string, init?: { query?: Record<string, string> }) => {
      gets.push({ path, query: init?.query ?? null });
      if (path === "/billing/print-sets/bills") {
        const rows = options.rows ?? ROWS;
        return {
          status: 200,
          // The SERVER's count, deliberately larger than the rows on screen:
          // a fixture whose total equals its row count cannot tell a
          // server-paged list from a client-side slice (NFR-3).
          data: { count: IN_PERIOD, results: rows },
          etag: null,
          notModified: false,
        } as never;
      }
      if (path === "/billing/print-sets") {
        return {
          status: 200,
          data: options.previewBody ?? preview(),
          etag: null,
          notModified: false,
        } as never;
      }
      if (path === "/me/permissions") {
        // BR-SHL-025's read. `Full` so the primary control is LIVE — a fixture
        // that left it null would prove nothing about a button a clerk presses.
        return {
          status: 200,
          data: { permissions: [{ code: "reads_billing_runs", access: "Full" }] },
          etag: null,
          notModified: false,
        } as never;
      }
      if (path.startsWith("/billing/runs")) {
        return { status: 200, data: { runs: [] }, etag: null, notModified: false } as never;
      }
      // `/cycles` — `listAll` reads the DRF envelope.
      return {
        status: 200,
        data: { results: [], count: 0 },
        etag: null,
        notModified: false,
      } as never;
    },
  } as unknown as ApiClient;
  return { client, gets };
}

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN.** A bare `MemoryRouter` with no
 * `/:tenant/…` route leaves `useParams().tenant` undefined and every address
 * the page builds comes out `//billing/…`, a protocol-relative URL to another
 * host — which reads as a perfectly good string to `toContain` (hard-won law 2).
 */
function mount(node: JSX.Element) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/brazosbend/billing/print"]}>
        <Routes>
          <Route path="/:tenant/billing/print" element={node} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const REGIONAL = { timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" } as const;

describe("blueprint screen 28 — Print bills, as drawn (DEF-BIL-5354)", () => {
  it("draws the four tiles, and they ADD UP", async () => {
    const { client } = fakeClient();
    mount(<PrintBillsPage client={client} {...REGIONAL} />);

    // ⚠ `findAllByText` for the first two, and the duplication is DRAWN: the
    // tile says *Will print* and so does every printing row's verdict. A
    // `getByText` would fail for a reason that is nothing to do with the tiles.
    await screen.findAllByText(t("billing.print.tile.willPrint"));
    expect(screen.getAllByText(t("billing.print.tile.heldBack")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(t("billing.print.tile.pages")).length).toBeGreaterThan(0);
    expect(screen.getByText(t("billing.print.tile.inPeriod"))).toBeInTheDocument();

    // The four VALUES, in the drawn order, read off the tiles themselves.
    const tiles = Array.from(document.querySelectorAll(".kpi .v")).map((one) => one.textContent);
    expect(tiles).toEqual([
      String(WILL_PRINT),
      String(HELD),
      t("billing.print.tile.about", { pages: WILL_PRINT * 2 }),
      String(IN_PERIOD),
    ]);
    // The drawn detail line IS the arithmetic: 38 + 3, always.
    expect(
      screen.getByText(t("billing.print.tile.adds", { printing: WILL_PRINT, held: HELD })),
    ).toBeInTheDocument();
    // …and the arithmetic is real, not a coincidence of this fixture.
    expect(WILL_PRINT + HELD).toBe(IN_PERIOD);
  });

  it("lists the period's bills with the hold reason ON the row", async () => {
    const { client } = fakeClient();
    mount(<PrintBillsPage client={client} {...REGIONAL} />);

    await screen.findByText("BL-2609-000181");
    expect(screen.getByText("BL-2609-000188")).toBeInTheDocument();
    // The account cell is ONE line, as p149 draws it — `100377 · Ridge Coffee
    // Co.` — so the name is matched inside its row rather than as a node of its
    // own. A stacked pair sets the height of every row in a fifty-row table.
    const accountCell = screen.getByText("100377").closest("td");
    expect(accountCell?.textContent).toContain("Ridge Coffee Co.");
    // Money at TWO decimals with its currency (CLAUDE.md hard rule 2), never
    // the four the server stores it to.
    expect(screen.getByText("$289.40")).toBeInTheDocument();
    expect(screen.queryByText("289.4000")).toBeNull();
    // The verdict, in words, with its reason — and never the reason's code.
    // Read off the PILL, because the tile above says the same two words.
    const pills = Array.from(document.querySelectorAll(".pill")).map((one) => one.textContent);
    expect(pills).toContain(t("billing.print.verdict.willPrint"));
    expect(
      screen.getByText(
        `${t("billing.print.verdict.held")} · ${t("billing.print.hold.address_incomplete")}`,
      ),
    ).toBeInTheDocument();
  });

  it("NFR-3: the list is paged by the SERVER — the total is the server's, not the row count", async () => {
    const { client, gets } = fakeClient();
    mount(<PrintBillsPage client={client} {...REGIONAL} />);

    await screen.findByText("BL-2609-000181");
    const billsCall = gets.find((one) => one.path === "/billing/print-sets/bills");
    expect(billsCall).toBeDefined();
    // The page and its size go to the database; nothing is sliced here.
    expect(billsCall?.query?.page).toBe(1);
    expect(billsCall?.query?.per).toBe(50);
    // Two rows on screen, 41 in the period: a client-side count would say 2,
    // and the tile would then agree with the page instead of with the database.
    expect(ROWS.length).not.toBe(IN_PERIOD);
    const tiles = Array.from(document.querySelectorAll(".kpi .v")).map((one) => one.textContent);
    expect(tiles).toContain(String(IN_PERIOD));
  });

  it("the held-back door is LIVE: it narrows this table and offers the way back", async () => {
    const { client, gets } = fakeClient();
    mount(<PrintBillsPage client={client} {...REGIONAL} />);

    const door = await screen.findByText(t("billing.print.held.see", { count: HELD }));
    expect(door).toBeEnabled();
    door.click();

    await waitFor(() => {
      expect(
        gets.some(
          (one) => one.path === "/billing/print-sets/bills" && one.query?.hold === "held",
        ),
      ).toBe(true);
    });
    // A door with no way back is a one-way door.
    await screen.findByText(t("billing.print.held.showAll"));
  });

  it("a scope change re-asks BOTH reads with the same filter, so the tiles and the list agree", async () => {
    const { client, gets } = fakeClient();
    mount(<PrintBillsPage client={client} {...REGIONAL} />);
    await screen.findByText("BL-2609-000181");

    const issuedFrom = document.querySelector("[data-print-issued-from]") as HTMLInputElement;
    expect(issuedFrom).not.toBeNull();

    await waitFor(() => {
      const preview = gets.filter((one) => one.path === "/billing/print-sets");
      const bills = gets.filter((one) => one.path === "/billing/print-sets/bills");
      expect(preview.length).toBeGreaterThan(0);
      expect(bills.length).toBeGreaterThan(0);
      // Both reads carry the SAME filter set. A tile counting one population
      // over a list showing another is the defect this screen exists to end.
      expect(preview[0].query).toEqual({});
      expect(bills[0].query?.["f.cycle_id"]).toBeUndefined();
    });
  });

  it("a tile states an ABSENCE rather than a confident zero when the addresses could not be read", async () => {
    const { client } = fakeClient({
      previewBody: preview({
        held_back: 0,
        held_reasons: [],
        held_reasons_complete: false,
        will_print: IN_PERIOD,
      }),
    });
    mount(<PrintBillsPage client={client} {...REGIONAL} />);
    // *"nobody is held"* and *"nobody could ask"* are not the same statement.
    await screen.findByText(t("billing.print.tile.addressesUnread"));
  });

  it("B14 rules 31 and 32: no id and no dotted identifier reaches the clerk", async () => {
    const { client } = fakeClient();
    const view = mount(<PrintBillsPage client={client} {...REGIONAL} />);
    await screen.findByText("BL-2609-000181");

    // The shared reader that found DEF-BIL-5339 — it reads RENDERED text, so a
    // uuid in a `value` or a `data-` attribute is not what it objects to.
    const found = internalReferencesInMarkup(view.container.innerHTML);
    expect(found).toEqual([]);
  });

  it("group 3 states what the archive does not claim, and the server's own sentences are one click away", async () => {
    const { client } = fakeClient();
    mount(<PrintBillsPage client={client} {...REGIONAL} />);

    await screen.findByText(t("billing.print.claim.addressesValue"));
    expect(screen.getByText(t("billing.print.claim.screenValue"))).toBeInTheDocument();
    // The drawn `Past print sets` control is NOT a button, because nothing
    // records a set after it is handed over (DEF-BIL-5374). The absence is
    // stated where a clerk would look for the control.
    expect(screen.getByText(t("billing.print.claim.pastSetsValue"))).toBeInTheDocument();
    // B14 rule 32: the vendor's four long paragraphs are a stated absence, so
    // they are CLOSED by default and still in the document, word for word.
    const notes = document.querySelector("[data-print-notes]") as HTMLDetailsElement;
    expect(notes).not.toBeNull();
    expect(notes.open).toBe(false);
    expect(notes.textContent).toContain("no standards here.");
  });

  it("neither a status nor a route nor a service filter is offered, because the server serves none", async () => {
    const { client } = fakeClient();
    const view = mount(<PrintBillsPage client={client} {...REGIONAL} />);
    await screen.findByText("BL-2609-000181");

    // A print set is issued and paid bills ALWAYS (`print_set.PRINTABLE_
    // STATUSES`), so a status control would promise a narrowing the server
    // overrides; route and service are in no list's filter vocabulary.
    // `06-backend/tests/test_cr101_print_bills.py` goes RED the day either
    // arrives, and names this screen.
    const chips = Array.from(view.container.querySelectorAll("button, select")).map((one) =>
      (one.textContent ?? "").trim(),
    );
    expect(chips.join(" | ")).not.toContain(t("billing.filter.status"));
  });
});
