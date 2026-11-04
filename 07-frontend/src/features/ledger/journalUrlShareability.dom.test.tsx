// @vitest-environment jsdom
//
// ── Trace ──────────────────────────────────────────────
// Change:  Finance blueprint p013 `P1.11` (E2E) — *"`J2-read-to-cash`: add a
//          step: filter, copy the URL, open it in a new context, same rows"*.
//          OUTCOME: ***"Shareability is asserted, not assumed."***
//          Phase 1's own DONE WHEN (p012): *"Every list that grows with
//          transaction volume pages in SQL and carries its filters in the URL."*
// Journey: 08-qa/01-e2e/journeys/J2-read-to-cash.md step 12
// Rules:   BR-SHL-011 (an unknown param is ignored, an invalid value falls back
//          or clamps, never an error screen) · `CR-060` C14 (*"so a filtered
//          journal view becomes a shareable URL"*) · NFR-3 (universal server
//          pagination) · CLAUDE.md hard-won law 2 (built is not wired)
// Defect:  DEF-LED-6654 — the sibling control on this same screen, the Balance
//          view's property filter, was `useState` and reached no URL. It was
//          PINNED here; the pin FIRED on 2026-09-25 when lane FIN-WIRE wired
//          the control, and the three cases at the foot of this file are what
//          replaced it.
// ───────────────────────────────────────────────────────
/**
 * THE JOURNAL'S FILTERS TRAVEL IN THE URL, AND A SECOND READER GETS THE SAME ROWS.
 *
 * ⚠ **WHY A SECOND MOUNT AND NOT A RELOAD.** `P1.9` already proves a round
 * trip: the page writes its state into the query string and reads it back. That
 * is one component instance talking to itself, and it passes even if half the
 * state really lives in `useState` and merely happens to survive because
 * nothing unmounted. **A colleague opening a pasted link has NONE of that** —
 * no component state, no react-query cache, no preference store warmed by the
 * clicks that built the filter. So this file mounts the screen a SECOND time,
 * in a FRESH `QueryClient`, with the URL as the only thing carried across, and
 * asks whether the server is asked the same question and the table shows the
 * same rows.
 *
 * ⚠ **AND COMPARING THE TWO MOUNTS IS NOT ENOUGH ON ITS OWN.** Two unfiltered
 * mounts also agree with each other. A test that only diffed them would be
 * green over a screen that had dropped every filter on the floor — hard-won
 * law 7's *structurally incapable of failing*. So the fixture answers
 * DIFFERENTLY when the filters arrive: the filtered question returns one row
 * and the unfiltered question returns three, and both the REQUEST and the ROWS
 * are asserted against the filtered answer.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { GeneralLedgerPage } from "./GeneralLedgerPage";

/** What a clerk's address bar holds after filtering the journal.
 *
 * Every piece of it is a DECLARED criterion of `journalConfig`: a search term,
 * a sort and its direction, a page size, a page, and two of the three filter
 * chips. It is written out as a literal rather than built with
 * `serializeTableParams` on purpose — a helper on both sides of an assertion
 * proves the helper agrees with itself and nothing about the screen. This is
 * the string a person would actually paste. */
const SHARED_URL =
  "/brazosbend/finance/general-ledger?view=journal" +
  "&q=deposit&sort=entry_date&dir=asc&per=50&f.status=posted&f.type=system";

/** The same screen with nothing chosen — the link a clerk did NOT send. */
const BARE_URL = "/brazosbend/finance/general-ledger?view=journal";

function entry(id: string, number: string, memo: string) {
  return {
    entry_id: id,
    je_number: number,
    entry_date: "2026-07-14",
    type: "system",
    memo,
    source_type: "invoice",
    source_label: "invoice",
    source_mapped: true,
    status: "posted",
    debit_total: "100.000000",
    credit_total: "100.000000",
    currency: "USD",
    reversed_by_entry_id: null,
    reverses_entry_id: null,
  };
}

/** THE ROW ONLY THE FILTERED QUESTION RETURNS. */
const ONLY_WHEN_FILTERED = "JE-071426-0007";

/** Records every path+query the screen asks for, and answers the journal
 *  differently depending on whether the filters arrived. */
function recordingClient(): { client: ApiClient; calls: string[] } {
  const calls: string[] = [];
  const client = {
    get: async (path: string, options?: { query?: Record<string, unknown> }) => {
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(options?.query ?? {})) {
        if (value !== undefined && value !== null && value !== "") {
          query.set(key, String(value));
        }
      }
      const full = query.toString() === "" ? path : `${path}?${query.toString()}`;
      calls.push(full);

      if (path.startsWith("/shell/display")) {
        // Without the served accounting period the journal query is `enabled:
        // false` and never runs at all — every assertion here would then fail
        // for a reason that has nothing to do with the URL.
        return { data: { period: { start: "2026-07-01", end: "2026-07-31" } } };
      }
      if (path.includes("permissions")) {
        return { data: { permissions: [{ code: "finance_reconcile_export", access: "full" }] } };
      }
      if (path === "/ledger/journal-entries") {
        const filtered =
          query.get("f.status") === "posted" &&
          query.get("f.type") === "system" &&
          query.get("q") === "deposit";
        return {
          data: {
            count: filtered ? 1 : 3,
            next: null,
            previous: null,
            results: filtered
              ? [entry("e7", ONLY_WHEN_FILTERED, "deposit batch")]
              : [
                  entry("e1", "JE-070126-0001", "opening"),
                  entry("e2", "JE-070826-0004", "bill run"),
                  entry("e7", ONLY_WHEN_FILTERED, "deposit batch"),
                ],
            unavailable: [],
            vocabulary: {},
          },
        };
      }
      if (path.includes("trial-balance")) {
        // A SHAPED answer, not an empty one. `GeneralLedgerPage` reads
        // `report.period.start` unguarded, so an over-general `{}` here throws
        // inside render — and a thrown render reads as "the assertion below is
        // about a screen that is not there" rather than as a short fixture.
        return {
          data: {
            basis: "posting",
            currency: "USD",
            period: { start: "2026-07-01", end: "2026-07-31" },
            rows: [],
            total_debit: "0.000000",
            total_credit: "0.000000",
            total_opening: "0.000000",
            total_closing: "0.000000",
            difference: "0.000000",
            balanced: true,
          },
        };
      }
      return {
        data: { rows: [], results: [], count: 0, unavailable: [], items: [], incomplete: [] },
      };
    },
    post: async () => ({ data: {} }),
    patch: async () => ({ data: {} }),
    put: async () => ({ data: {} }),
    delete: async () => ({ data: {} }),
  } as unknown as ApiClient;
  return { client, calls };
}

/** ⚠ A FRESH `QueryClient` PER MOUNT IS THE WHOLE POINT OF THIS FILE — it is
 *  what makes the second mount a NEW CONTEXT rather than the same session
 *  reading its own cache. Sharing one would let a cached answer satisfy the
 *  second mount without a single parameter leaving the URL.
 *
 *  ⚠ AND IT IS MOUNTED UNDER THE REAL PATH PATTERN (`DEF-CWP-3925`'s fixture
 *  lesson): a bare `MemoryRouter` leaves `useParams().tenant` undefined and
 *  every address the tree builds comes out `//…`, which reads as a perfectly
 *  good string to an assertion. */
function openLink(url: string, client: ApiClient) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={[url]}>
          <Routes>
            <Route
              path="/:tenant/finance/general-ledger"
              element={<GeneralLedgerPage client={client} now={() => "2026-09-24T00:00:00Z"} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The journal request this mount sent, as a query string. */
async function journalCall(calls: string[]): Promise<string> {
  await waitFor(() => {
    expect(calls.filter((c) => c.startsWith("/ledger/journal-entries"))).not.toHaveLength(0);
  });
  const journal = calls.filter((c) => c.startsWith("/ledger/journal-entries"));
  return journal[journal.length - 1];
}

afterEach(cleanup);

describe("P1.11 · J2 step 12 — a filtered journal is a shareable link", () => {
  it("asks the server the SAME question from a bare URL as from a clicked filter", async () => {
    const first = recordingClient();
    openLink(SHARED_URL, first.client);
    const asked = await journalCall(first.calls);
    cleanup();

    // Every declared criterion is on the wire. Asserted one by one rather than
    // as one string compare, so a failure names WHICH criterion was dropped.
    const sent = new URLSearchParams(asked.split("?")[1]);
    expect(sent.get("q")).toBe("deposit");
    expect(sent.get("sort")).toBe("entry_date");
    expect(sent.get("dir")).toBe("asc");
    expect(sent.get("per")).toBe("50");
    expect(sent.get("f.status")).toBe("posted");
    expect(sent.get("f.type")).toBe("system");
    // The period is the tenant's open month and travels with it (BR-LED-010).
    // `DEF-LED-10071` J4 (PO 2026-10-12) — NO period unless one is chosen. The
    // journal used to be narrowed to the finance month without saying so;
    // these two read `2026-07-01` / `2026-07-31` until the ruling.
    expect(sent.get("from")).toBeNull();
    expect(sent.get("to")).toBeNull();

    // A SECOND READER: new client, new cache, nothing but the URL.
    const second = recordingClient();
    openLink(SHARED_URL, second.client);
    expect(await journalCall(second.calls)).toBe(asked);
  });

  it("shows the colleague the filtered rows, not every row", async () => {
    const second = recordingClient();
    openLink(SHARED_URL, second.client);
    expect(await screen.findByText(ONLY_WHEN_FILTERED)).toBeTruthy();
    // The two rows the UNFILTERED answer carries must not be on this screen —
    // this is the assertion that a dropped filter fails and a compare of two
    // mounts against each other cannot make.
    await waitFor(() => {
      expect(screen.queryByText("JE-070126-0001")).toBeNull();
    });
    expect(screen.queryByText("JE-070826-0004")).toBeNull();
  });

  it("is a DIFFERENT question from the bare screen — the fixture can tell them apart", async () => {
    const bare = recordingClient();
    openLink(BARE_URL, bare.client);
    const asked = await journalCall(bare.calls);
    const sent = new URLSearchParams(asked.split("?")[1]);
    expect(sent.get("q")).toBeNull();
    expect(sent.get("f.status")).toBeNull();
    expect(await screen.findByText("JE-070126-0001")).toBeTruthy();
  });

  it("ignores an unknown param and falls back on an invalid sort (BR-SHL-011)", async () => {
    // A pasted link is hand-editable and arrives truncated, so the screen must
    // never answer a bad one with an error page. `sort=banana` is outside the
    // sortable set and falls back to the screen's default; `&colour=red` is not
    // a declared param and is ignored.
    const odd = recordingClient();
    openLink(`${BARE_URL}&sort=banana&dir=asc&colour=red`, odd.client);
    const sent = new URLSearchParams((await journalCall(odd.calls)).split("?")[1]);
    expect(sent.get("sort")).toBe("entry_date");
    expect(sent.get("dir")).toBe("desc");
    expect(sent.get("colour")).toBeNull();
  });

  // ── `DEF-LED-6654` — THE HOLD EXPIRED, AND THESE ARE WHAT REPLACED IT ────
  //
  // ⚠ **THIS FILE HELD A PIN AND THE PIN FIRED.** Until 2026-09-25 the case
  // below asserted the OPPOSITE — that the Balance view's property filter
  // reaches no URL — so that the day anyone wired it the suite would go red
  // and name the defect rather than the gap being quietly outlived by its own
  // hold (hard-won law 2). It went red on exactly that line, on exactly that
  // message: *expected '/ledger/trial-balance?…' not to contain 'f.premises'*.
  // The pin is now the assertion, in both directions, because a filter that
  // travels ONE way is the same silent lie in the other: a link that carries
  // it but a control that does not write it is a link nobody can produce.
  const A_PROPERTY = "01a0763a-0000-7000-8000-000000000001";
  const BALANCE_LINK = `/brazosbend/finance/general-ledger?view=balance&f.premises=${A_PROPERTY}`;

  /** The trial-balance request this mount sent, as a whole path. */
  async function trialBalanceCall(calls: string[]): Promise<string> {
    await waitFor(() => {
      expect(calls.filter((c) => c.includes("trial-balance"))).not.toHaveLength(0);
    });
    return calls.filter((c) => c.includes("trial-balance")).pop() ?? "";
  }

  it("carries the Balance view's property filter from a PASTED LINK to the server — DEF-LED-6654", async () => {
    // The colleague's half: nothing but the URL, a fresh client, a fresh cache.
    const balance = recordingClient();
    openLink(BALANCE_LINK, balance.client);
    const tb = await trialBalanceCall(balance.calls);
    expect(new URLSearchParams(tb.split("?")[1]).get("f.premises")).toBe(A_PROPERTY);
  });

  it("is a DIFFERENT question from the unfiltered Balance view — the fixture can tell them apart", async () => {
    // ⚠ **WITHOUT THIS CASE THE ONE ABOVE COULD PASS WRONGLY.** A screen that
    // put `f.premises` on EVERY trial-balance request — a hard-coded param, a
    // default that is never cleared — would satisfy it. So the bare Balance
    // view is asserted to send NO `f.premises` at all, which is the same
    // sentence the retired pin made and is now true only of the unfiltered
    // screen.
    const bare = recordingClient();
    openLink("/brazosbend/finance/general-ledger?view=balance", bare.client);
    const tb = await trialBalanceCall(bare.calls);
    expect(tb).not.toContain("f.premises");
  });

  it("keeps the property filter when the journal beside it is paged — DEF-LED-6654", async () => {
    // ⚠ **ONE QUERY STRING, TWO VIEWS.** `serializeTableParams` writes the
    // table's own declared params and nothing else, so before this fix a sort
    // or a page on either table silently dropped a filter living beside them.
    // A filter that clears itself when a clerk clicks a column heading is
    // worse than one that never travelled.
    const both = recordingClient();
    openLink(`${BALANCE_LINK}&sort=code&dir=asc&page=2`, both.client);
    const tb = await trialBalanceCall(both.calls);
    expect(tb).toContain(`f.premises=${A_PROPERTY}`);
  });
});
