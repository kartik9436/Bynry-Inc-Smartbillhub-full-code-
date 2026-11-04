// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-732 — the transfer wizard asks a clerk to type a UUID. The PO
//           typed `AC-2026-00025` (the number every list, KPI tile and detail
//           header in this product shows) into step 1 and was told *"That
//           account could not be read"* — the endpoint correctly failing to
//           find a uuid that was never a uuid.
// Screens:  S89 `TRF-02.1` (transfer) · `DSC-02.1` (disconnect)
// Rules:    BR-CUS-053 (ONE box finds an account by account #, customer #,
//           customer name, service address or meter #) · BR-SHL-011 (a list URL
//           never 4xx's over its params) · CLAUDE.md hard rule 1 (the search is
//           the SERVER's, in the tenant's own scope) · hard rule 2 (never state
//           a fault for a fact about what was typed)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE ASSERTION THAT WAS MISSING IS THE WHOLE FILE.** Both wizards were
// already tested, both suites passed, and the usability of the one field a
// clerk must fill was never exercised — because **every case supplied a real
// uuid** as the draft's account id. These cases start from an empty box and
// type what a list displays.
//
// The second case is the one hard rule 2 exists for: a number that matches
// nothing and a system fault are DIFFERENT FACTS, and a clerk can act on only
// one of them. "Could not be read" over a term that simply found no account
// sends them to support instead of to their own typo.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { DisconnectWizard } from "./DisconnectWizard";
import { TransferWizard } from "./TransferWizard";
import { DISCONNECT_WIZARD_ROUTE, TRANSFER_WIZARD_ROUTE } from "./transferDisconnectShared";

afterEach(cleanup);

const TEST_TENANT = "brazosbend";

/** The number the PO typed, as the accounts register prints it in its first cell. */
const NUMBER = "AC-2026-00025";
const ACCOUNT_ID = "b1d3f2a4-5c6e-4f70-8a91-2b3c4d5e6f70";

/** One row of `GET /accounts?q=…` — the published search (BR-CUS-053). */
function listRow(over: Record<string, unknown> = {}) {
  return {
    id: ACCOUNT_ID,
    account_no: NUMBER,
    customer_no: "C-00091",
    name: "Iversen, Britt",
    unit_id: "unit-1",
    unit_label: "18 Marten Row",
    premise: "18 Marten Row",
    status: "active",
    balance: "0.0000",
    ...over,
  };
}

/** `GET /accounts/{id}` for the account the clerk picked. */
function detail(over: Record<string, unknown> = {}) {
  return {
    id: ACCOUNT_ID,
    account_no: NUMBER,
    customer_no: "C-00091",
    name: "Iversen, Britt",
    unit_id: "unit-1",
    unit_label: "18 Marten Row",
    premise: "18 Marten Row",
    services: ["electric"],
    balance: "0.0000",
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    // BR-CUS-510 / DEF-628 — the DEFAULT is `false`: this fixture's zero,
    // wherever it has one, is a real answer about money owed.
    balance_not_yet_billable: false,
    balance_cached: "0.0000",
    currency: "USD",
    status: "active",
    status_name: "Active",
    status_behavior_class: "billable",
    kind: "regular",
    account_type: "residential",
    account_subtype: null,
    autopay: false,
    opened_at: "2022-06-01",
    closed_at: null,
    deposit_on_file: "150.0000",
    plan: null,
    plan_snapshot_unavailable: "BR-CUS-029",
    credit_tier: null,
    contacts: [],
    addresses: [],
    service_agreements: [],
    notes: [],
    custom_data: {},
    unavailable: [],
    customer: {
      id: "cus-1",
      kind: "person",
      display_name: "Iversen, Britt",
      external_ref: null,
      accounts: [{ id: ACCOUNT_ID, account_no: NUMBER }],
    },
    ...over,
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

type Wizard = "transfer" | "disconnect";

/** The server as it really answers: the SEARCH finds by number, and the DETAIL
 *  only ever answers to the account's id. Anything else under `/accounts/` is a
 *  404 — which is exactly the behaviour DEF-732 was filed over. */
function server(url: string, over: { matches?: unknown[] } = {}): Response {
  const matches = over.matches ?? [listRow()];
  const path = url.split("?")[0];
  if (path.endsWith("/accounts")) {
    return json({ count: matches.length, results: matches });
  }
  if (path.endsWith(`/accounts/${ACCOUNT_ID}`)) {
    return json(detail());
  }
  if (path.includes("/accounts/")) {
    return json({ detail: "not found" }, 404);
  }
  // `DEF-CUS-9106` — the transfer step reads the account's UNIT PRICING once
  // the account resolves (`GET /units/{id}/pricing`, an OBJECT). The list
  // shape below answered it and the step crashed on `services.find`, so a
  // pasted id that DID resolve still drew nothing. Unpriced here, honestly.
  if (path.includes("/pricing")) {
    return json({ detail: "not found" }, 404);
  }
  return json({ count: 0, results: [] });
}

function mount(which: Wizard, onRequest: (url: string) => Response): { urls: string[] } {
  const urls: string[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input) => {
      urls.push(String(input));
      return onRequest(String(input));
    },
  });
  const route = which === "transfer" ? TRANSFER_WIZARD_ROUTE : DISCONNECT_WIZARD_ROUTE;
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${route}?step=1`]}>
          <Routes>
            <Route
              path={`/:tenant${route}`}
              element={
                which === "transfer" ? (
                  <TransferWizard client={client} />
                ) : (
                  <DisconnectWizard client={client} />
                )
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { urls };
}

const FIELD: Record<Wizard, RegExp> = {
  // ⚠ **`account being sold`, NOT `account they are leaving` — `DEF-CUS-5075`.**
  // The label changed when the JOB did: a transfer is a SALE (`BR-CUS-1030`,
  // PO 2026-09-01), so nobody is leaving — the account stays exactly where it
  // is and the customer changes. This file's own subject, `DEF-732`, is
  // untouched by that: a clerk still completes step 1 with the number their
  // lists display and never types a uuid, which is what the three cases below
  // assert. Only the field's name moved.
  transfer: /account being sold/i,
  disconnect: /^account/i,
};

describe.each<Wizard>(["transfer", "disconnect"])("DEF-732 · %s wizard step 1", (which) => {
  /**
   * **THE CASE THE ESCAPE COLUMN ASKS FOR.** A clerk holds a bill and a list;
   * both carry `AC-2026-00025` and neither carries a uuid. Step 1 must be
   * completable from that alone.
   */
  it("a clerk completes step 1 with the number the lists display, and never types an id", async () => {
    const { urls } = mount(which, (url) => server(url));

    const box = await screen.findByRole("combobox", { name: FIELD[which] });
    await userEvent.type(box, NUMBER);

    // The PUBLISHED search (BR-CUS-053) is what answers it — not a new endpoint.
    await waitFor(() =>
      expect(urls.some((url) => url.includes("/accounts?") && url.includes("q="))).toBe(true),
    );

    // ⊕ **ONE CONTROL, SO THE MATCH IS AN OPTION UNDER THE BOX A CLERK TYPED
    // IN — `DEF-CUS-6475` for the disconnect, `DEF-CUS-6382` for the
    // transfer.** This used to `selectOptions` a separate *Matching account*
    // `<select>`; both wizards now compose the kit's `RemoteSearchSelectField`,
    // whose listbox is the ARIA combobox pattern (BR-SHL-033), so the match is
    // OFFERED as an option and taken with one click rather than a second
    // gesture. The account is still named the way the register names it.
    const option = await screen.findByRole("option", { name: new RegExp(NUMBER) });
    await userEvent.click(option);

    // …and the wizard reads the account the choice resolved to.
    await waitFor(() =>
      expect(urls.some((url) => url.includes(`/accounts/${ACCOUNT_ID}`))).toBe(true),
    );
    // ⊕ **THE CHOSEN ACCOUNT IS NAMED IN THE BOX ITSELF NOW.** With one control
    // the input shows the chosen option's LABEL at rest, so the number is its
    // `value` rather than text on the page — and asserting the VALUE is the
    // stronger question anyway, because it is also B14 rule 31 (a clerk sees
    // the account's name, never its database id).
    await waitFor(() => expect((box as HTMLInputElement).value).toContain(NUMBER));

    // ⛔ AND THE SYSTEM-FAULT SENTENCE IS NEVER SHOWN FOR A GOOD NUMBER.
    //
    // ⚠ **THE MATCH NAMES *THAT ACCOUNT*, NOT ANY SENTENCE CONTAINING *could
    // not be read* — `DEF-CUS-6475`.** This read `/could not be read/i`, and
    // once the chosen account renders its panels the disconnect step draws
    // *"The ladder could not be read."* and *"The bills could not be read."* —
    // two absences about OTHER reads, in a fixture that serves neither. The
    // loose regex therefore failed on a screen that was behaving correctly,
    // which is hard-won law 7's *looking at the wrong thing*: a test named
    // after an assertion it does not make. DEF-732 is about ONE sentence — the
    // PLATFORM fault claimed over a good account number — so that is the one
    // asserted.
    expect(screen.queryByText(/that account could not be read/i)).toBeNull();
  });

  /**
   * Hard rule 2 — never fabricate, and never mis-state. A term that matches no
   * account is a fact about the TERM; "could not be read" is a fact about the
   * PLATFORM. Only one of them tells the clerk to check their typing.
   */
  it("a number that matches nothing says so — it does not report a system fault", async () => {
    mount(which, (url) => server(url, { matches: [] }));

    const box = await screen.findByRole("combobox", { name: FIELD[which] });
    await userEvent.type(box, "AC-2026-99999");

    await waitFor(() => expect(screen.getByText(/no account matches/i)).toBeInTheDocument());
    expect(screen.queryByText(/could not be read/i)).toBeNull();
  });

  /**
   * DEF-732 forbids trading one exclusive identifier for another: an id pasted
   * from a URL, a report or a support thread still resolves, with no second
   * click and no search.
   */
  it("an account id pasted into the box still resolves — the uuid was not traded away", async () => {
    const { urls } = mount(which, (url) => server(url));

    const box = await screen.findByRole("combobox", { name: FIELD[which] });
    // PASTED, which is how an id reaches a clerk — out of a URL or a support
    // thread, never typed out by hand.
    await userEvent.click(box);
    await userEvent.paste(ACCOUNT_ID);

    await waitFor(() =>
      expect(urls.some((url) => url.includes(`/accounts/${ACCOUNT_ID}`))).toBe(true),
    );
    await waitFor(() => expect(screen.getAllByText(NUMBER).length).toBeGreaterThan(0));
    // The search was never asked — an id is not a search term.
    expect(urls.some((url) => url.includes("/accounts?") && url.includes("q="))).toBe(false);
  });
});
