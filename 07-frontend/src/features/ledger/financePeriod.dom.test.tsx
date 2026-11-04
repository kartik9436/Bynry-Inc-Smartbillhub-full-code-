// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-LED-10071 (J3 · J4 · J5 — the Journal's Period filter) ·
//           DEF-LED-10072 (P1 · P2 · P4 · P5 · P7 · P8 — the Trial balance
//           period is a control) · DEF-LED-10075 (P9 — the utility's format)
// Ruling:   12-governance/02-decision-log.md 2026-10-12 "FINANCE: JOURNAL
//           SEARCH AND THE PERIOD CONTROLS", CONFIRMED (PO: *"this good please
//           start and fix it"*)
// ───────────────────────────────────────────────────────
//
// The whole page, mounted under its real route with a recording client, so
// every assertion reads what went OUT ON THE WIRE and what the URL says — not
// what a component believes it asked for.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY (law 7 (2)).**
// * A window counted from the browser's clock: the business date here is set
//   through the page's `now` seam and the TENANT's zone — 15:00 UTC on 12
//   October is still 12 October in Chicago — and every expected date is
//   written out, so none of these can pass on another day.
// * A close strip that silently followed the picked window: P5 is asserted on
//   the close-checklist REQUEST after the window has moved.
// * A refused window that still reached the server: the refusal case reads
//   the LAST trial-balance request and the URL, and both must be unchanged.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { GeneralLedgerPage } from "./GeneralLedgerPage";

const NOW = "2026-10-12T15:00:00Z"; // 10:00 in Chicago — business date 2026-10-12

function entry(id: string, date: string) {
  return {
    entry_id: id,
    je_number: `JE-${id}`,
    entry_date: date,
    type: "standard",
    memo: "Counter drawer short $10.00",
    source_type: "counter_session",
    source_label: "counter_session",
    source_mapped: false,
    status: "posted",
    debit: "10.000000",
    credit: "10.000000",
    balanced: true,
    currency: "USD",
    reversed_by_entry_id: null,
    reversal_of_entry_id: null,
    auto_reverse_entry_id: null,
    posted_at: null,
  };
}

function recordingClient(): { client: ApiClient; calls: string[] } {
  const calls: string[] = [];
  const client = {
    get: async (path: string, options?: { query?: Record<string, unknown> }) => {
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(options?.query ?? {})) {
        if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
      }
      calls.push(query.toString() === "" ? path : `${path}?${query.toString()}`);
      if (path.startsWith("/shell/display")) {
        return { data: { period: { start: "2026-10-01", end: "2026-10-31", fy_label: "FY26", period: 10, status: "open" } } };
      }
      if (path.includes("permissions")) {
        return { data: { permissions: [{ code: "finance_reconcile_export", access: "full" }] } };
      }
      if (path === "/ledger/journal-entries") {
        return {
          data: {
            count: 1,
            next: null,
            previous: null,
            results: [entry("100126-0001", "2026-10-01")],
            unavailable: [],
          },
        };
      }
      if (path.includes("trial-balance")) {
        return {
          data: {
            basis: "posting",
            currency: "USD",
            period: { start: query.get("from"), end: query.get("to") },
            rows: [],
            total_debit: "0.000000",
            total_credit: "0.000000",
            total_opening: "0.000000",
            total_closing: "0.000000",
            difference: "0.000000",
            balanced: true,
            unavailable: [],
          },
        };
      }
      if (path.includes("close-checklist")) {
        return { data: { items: [], done: 0, total: 7, incomplete: [] } };
      }
      return { data: { rows: [], results: [], count: 0, unavailable: [], items: [], incomplete: [] } };
    },
    post: async () => ({ data: {} }),
    patch: async () => ({ data: {} }),
    put: async () => ({ data: {} }),
    delete: async () => ({ data: {} }),
  } as unknown as ApiClient;
  return { client, calls };
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.search}</output>;
}

function open(url: string) {
  const recorded = recordingClient();
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={[url]}>
          <Routes>
            <Route
              path="/:tenant/finance/general-ledger"
              element={
                <>
                  <GeneralLedgerPage
                    client={recorded.client}
                    now={() => NOW}
                    timeZone="America/Chicago"
                    dateFormat="MM/DD/YYYY"
                  />
                  <LocationProbe />
                </>
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return recorded.calls;
}

const BALANCE = "/brazosbend/finance/general-ledger?view=balance";
const JOURNAL = "/brazosbend/finance/general-ledger?view=journal";

function last(calls: string[], fragment: string): URLSearchParams {
  const hit = calls.filter((call) => call.includes(fragment)).pop() ?? "";
  return new URLSearchParams(hit.split("?")[1] ?? "");
}

async function lastWindow(calls: string[], fragment: string): Promise<[string | null, string | null]> {
  await waitFor(() => expect(calls.some((call) => call.includes(fragment))).toBe(true));
  const sent = last(calls, fragment);
  return [sent.get("from"), sent.get("to")];
}

function urlParams(): URLSearchParams {
  return new URLSearchParams(screen.getByTestId("location").textContent ?? "");
}

afterEach(cleanup);

describe("DEF-LED-10072 — the Trial balance period is a control", () => {
  it("P1 — opens on the finance month, ending today (P4)", async () => {
    const calls = open(BALANCE);
    expect(await lastWindow(calls, "trial-balance")).toEqual(["2026-10-01", "2026-10-12"]);
    expect(await screen.findByLabelText("Period")).toHaveValue("this_month");
  });

  it.each([
    ["last_month", "2026-09-01", "2026-09-30"],
    ["last_30", "2026-09-13", "2026-10-12"],
    ["last_60", "2026-08-14", "2026-10-12"],
    ["last_90", "2026-07-15", "2026-10-12"],
  ])("P2 — %s fills From/To and asks the server for that window", async (choice, from, to) => {
    const calls = open(BALANCE);
    const select = await screen.findByLabelText("Period");
    await userEvent.selectOptions(select, choice);
    await waitFor(() => expect(last(calls, "trial-balance").get("from")).toBe(from));
    expect(last(calls, "trial-balance").get("to")).toBe(to);
    // P7 — and the URL carries it.
    expect([urlParams().get("range"), urlParams().get("from"), urlParams().get("to")]).toEqual([
      choice,
      from,
      to,
    ]);
  });

  it("P2 — typing a date switches the choice to Custom", async () => {
    const calls = open(BALANCE);
    const from = await screen.findByLabelText("From");
    await userEvent.clear(from);
    await userEvent.type(from, "10/05/2026");
    await waitFor(() => expect(last(calls, "trial-balance").get("from")).toBe("2026-10-05"));
    expect(screen.getByLabelText("Period")).toHaveValue("custom");
    expect(urlParams().get("range")).toBe("custom");
  });

  it("P4 — To before From is refused in words and never sent", async () => {
    const calls = open(BALANCE);
    await lastWindow(calls, "trial-balance");
    const to = await screen.findByLabelText("To");
    await userEvent.clear(to);
    await userEvent.type(to, "09/01/2026");
    expect(await screen.findByText("To is before From.")).toBeInTheDocument();
    expect(last(calls, "trial-balance").get("to")).toBe("2026-10-12");
    expect(urlParams().get("to")).toBeNull();
  });

  it("P4 — a period cannot end after today", async () => {
    const calls = open(BALANCE);
    await lastWindow(calls, "trial-balance");
    const to = await screen.findByLabelText("To");
    await userEvent.clear(to);
    await userEvent.type(to, "10/20/2026");
    expect(await screen.findByText("A period cannot end after today.")).toBeInTheDocument();
    expect(last(calls, "trial-balance").get("to")).toBe("2026-10-12");
  });

  it("P7 — a pasted link restores its window", async () => {
    const calls = open(`${BALANCE}&range=custom&from=2026-08-03&to=2026-08-21`);
    expect(await lastWindow(calls, "trial-balance")).toEqual(["2026-08-03", "2026-08-21"]);
    expect(await screen.findByLabelText("Period")).toHaveValue("custom");
  });

  it("P7 — a link naming a quick choice is re-counted from today", async () => {
    const calls = open(`${BALANCE}&range=last_30&from=2026-01-01&to=2026-01-30`);
    expect(await lastWindow(calls, "trial-balance")).toEqual(["2026-09-13", "2026-10-12"]);
  });

  it("P5 — the close strip stays on the month being CLOSED, not the picked window", async () => {
    const calls = open(BALANCE);
    const select = await screen.findByLabelText("Period");
    await userEvent.selectOptions(select, "last_90");
    await waitFor(() => expect(last(calls, "trial-balance").get("from")).toBe("2026-07-15"));
    const close = last(calls, "close-checklist");
    expect([close.get("from"), close.get("to")]).toEqual(["2026-10-01", "2026-10-31"]);
  });

  it("P6 — the date basis is a fact, labelled Dated by", async () => {
    open(BALANCE);
    expect(await screen.findByText("Dated by")).toBeInTheDocument();
    expect(screen.getByText("Posting date")).toBeInTheDocument();
  });
});

describe("DEF-LED-10071 — the Journal's search and Period", () => {
  it("J4 — no period by default: every entry", async () => {
    const calls = open(JOURNAL);
    expect(await lastWindow(calls, "/ledger/journal-entries")).toEqual([null, null]);
  });

  it("J2 — the search box names what it finds", async () => {
    open(JOURNAL);
    expect(
      await screen.findByPlaceholderText("Entry, memo, account, customer or address"),
    ).toBeInTheDocument();
  });

  it("J3 — Last 30 days in + Filter sends from/to and shows a removable chip", async () => {
    const calls = open(JOURNAL);
    const range = await screen.findByLabelText("Range");
    await userEvent.selectOptions(range, "last_30");
    await waitFor(() =>
      expect(last(calls, "/ledger/journal-entries").get("from")).toBe("2026-09-13"),
    );
    expect(last(calls, "/ledger/journal-entries").get("to")).toBe("2026-10-12");
    expect(urlParams().get("f.period")).toBe("last_30");
    expect(await screen.findByText("Period: Last 30 days")).toBeInTheDocument();
  });

  it("J3 · J5 — a link with a period restores it, and the chip's ✕ clears it", async () => {
    const calls = open(`${JOURNAL}&f.period=last_60`);
    expect(await lastWindow(calls, "/ledger/journal-entries")).toEqual(["2026-08-14", "2026-10-12"]);
    const remove = await screen.findByRole("button", { name: /Period/ });
    await userEvent.click(remove);
    await waitFor(() => expect(last(calls, "/ledger/journal-entries").get("from")).toBeNull());
    expect(urlParams().get("f.period")).toBeNull();
  });

  it("J3 — Custom From/To from a link, shown in the utility's format", async () => {
    const calls = open(
      `${JOURNAL}&f.period=custom&f.period_from=2026-10-01&f.period_to=2026-10-05`,
    );
    expect(await lastWindow(calls, "/ledger/journal-entries")).toEqual(["2026-10-01", "2026-10-05"]);
    expect(await screen.findByText("Period: 10/01/2026 to 10/05/2026")).toBeInTheDocument();
  });

  it("P9 — the DATE column reads 10/01/2026, and the source reads Counter session", async () => {
    open(JOURNAL);
    const table = await screen.findByRole("table");
    expect(await within(table).findByText("10/01/2026")).toBeInTheDocument();
    expect(within(table).queryByText("2026-10-01")).toBeNull();
    expect(within(table).getByText(i18n.t("finance.journal.sourceCode.counter_session"))).toBeInTheDocument();
    expect(within(table).getByText("Counter session")).toBeInTheDocument();
  });
});
