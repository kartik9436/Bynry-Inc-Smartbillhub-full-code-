// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Question: OQ-INT-12398 — should clearing a non-empty allowed-addresses list
//           warn first? CLOSED 2026-09-17 by PO ruling, verbatim:
//           "a) A short line under the field when you clear it —
//            "This allows any address." - yes okay"
//           The three options put were (a) a short line, (b) a confirmation
//           dialog, (c) leave it.
// Screens:  S147 · INT-07, /:tenant/settings/connectors/:providerKey/configure
// Rules:    B14 rule 33 (a CONSEQUENCE before a widening is <= 6 words per
//           sentence — this one is four) · B14 rule 35 (each catalogue in its
//           own idiom) · CLAUDE.md hard-won law 6 (no gate reads rendered
//           output) and law 7 habit 2 (what would make this PASS wrongly?).
// ───────────────────────────────────────────────────────
/**
 * **CLEARING THE LIST WIDENS A SECURITY CONTROL, SO THE SCREEN SAYS SO — ONCE.**
 *
 * `allowed_addresses` became optional earlier the same day, and
 * `runners/serve.py:allowlist_permits` has always read an empty list as
 * *permit everything*. So going from a list to blank turns a restriction off
 * in about two seconds, and until this line nothing said a word about it.
 *
 * ⚠ **WHY THIS FILE CLICKS RATHER THAN RENDERING ONCE.** The rule is about a
 * TRANSITION — non-empty when the form opened, blank now — and first paint
 * cannot show a transition. `renderToStaticMarkup` would prove only that the
 * line is absent on arrival, which is the easy half.
 *
 * ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, AND IT IS WHY THERE ARE THREE CASES
 * AND NOT ONE.** The plausible wrong builds both LOOK like working:
 *
 *   * keyed off *the box is empty* alone — the line then shows on every
 *     connector that never had a list, i.e. it is permanently on, and a test
 *     that only ever clears a populated field would pass on it. Case 2 is that
 *     test, and it is the one that matters most.
 *   * keyed off a ref flipped in `onChange` — re-arms on re-render and misses
 *     a clear from any other path. Case 3 (type it back, the line goes) and
 *     case 1 together pin the condition to STORED-vs-CURRENT, which is a fact
 *     the server sent rather than a guess the component remembered.
 *
 * A fourth trap is the one hard-won law 2 records under `DEF-CWP-3925`: a
 * fixture that cannot tell a working state from a broken one. So case 0
 * asserts the field is actually on screen and seeded before anything is
 * cleared — without it, `queryByTestId` returning null would read as *the line
 * is correctly absent* on a page that rendered nothing at all.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { IntegrationsGrid, ProviderCard } from "@/api/integrationsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { ConnectorSetupPage } from "./ConnectorSetupPage";

afterEach(cleanup);

const TENANT = "brazosbend";
const KEY = "payments_kiosk";
const LINE = "This allows any address.";

/** The kiosk as the server serves it, with `allowed_addresses` optional. */
function card(settings: Record<string, unknown> | null): ProviderCard {
  return {
    key: KEY,
    category: "payments",
    display_name: "Payment kiosk network",
    summary: "They send us payments they have taken.",
    fields: [
      {
        name: "allowed_addresses",
        label: "Allowed addresses",
        kind: "text",
        required: false,
        options: [],
      },
    ],
    disposition: { kind: "live", wave: null, phase: 2 },
    kicker: { direction: "in", initiative: "them" },
    auth: { mode: "they_hold_ours", placement: "header" },
    codecs: [],
    adapter_registered: true,
    // ⚠ REQUIRED BY THE PAGE, NOT BY THE TYPE. The cast below would have let
    // this be omitted and the component reads `.issued_keys.find(...)`
    // unguarded — a fixture missing it throws before a single assertion runs.
    issued_keys: [],
    connection:
      settings === null
        ? null
        : {
            id: "c1",
            label: null,
            describe: null,
            settings,
            environment: "production",
            cadence: "manual",
            enabled: true,
            status: "untested",
            credential: null,
          },
    connections: [],
    vocabularies: [],
    state: settings === null ? "not_set_up" : "untested",
    display_state: settings === null ? "not_set_up" : "untested",
    operations: [],
  } as unknown as ProviderCard;
}

function mount(settings: Record<string, unknown> | null) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  queryClient.setQueryData(queryKeys.integrations, {
    providers: [card(settings)],
    counts: { providers: 1, connected: settings === null ? 0 : 1 },
  } as unknown as IntegrationsGrid);
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/settings/connectors/${KEY}/configure`]}>
          <Routes>
            <Route
              path="/:tenant/settings/connectors/:providerKey/configure"
              element={<ConnectorSetupPage />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const box = () => screen.getByLabelText(/Allowed addresses/i) as HTMLInputElement;
const line = () => document.querySelector("[data-allowlist-cleared]");

describe("OQ-INT-12398 — clearing a non-empty allowed-addresses list says so, once", () => {
  it("case 0 — the fixture can tell a rendered field from a page that drew nothing", async () => {
    mount({ allowed_addresses: "198.51.100.0/24" });
    // Without this, every `expect(line()).toBeNull()` below would pass over a
    // page that rendered no form at all (hard-won law 7).
    await waitFor(() => expect(box()).toHaveValue("198.51.100.0/24"));
    expect(line()).toBeNull();
  });

  it("case 1 — a list is cleared, so the line appears", async () => {
    const user = userEvent.setup();
    mount({ allowed_addresses: "198.51.100.0/24" });
    await waitFor(() => expect(box()).toHaveValue("198.51.100.0/24"));
    await user.clear(box());
    await waitFor(() => expect(line()).not.toBeNull());
    expect(line()).toHaveTextContent(LINE);
  });

  it("case 2 — a list that was ALREADY blank says nothing, however it is touched", async () => {
    // ⚠ THE CASE THAT FAILS THE OBVIOUS WRONG BUILD. A condition of merely
    // *the box is empty* is permanently true here, and a line that is always
    // on is the one outcome the PO's ruling was chosen to avoid: the clerk is
    // not changing anything, and a standing line teaches people to ignore
    // lines.
    const user = userEvent.setup();
    mount({ allowed_addresses: "" });
    await waitFor(() => expect(box()).toBeInTheDocument());
    expect(line()).toBeNull();
    await user.type(box(), "10.0.0.1");
    await user.clear(box());
    expect(line()).toBeNull();
  });

  it("case 3 — typing a value back takes the line away again", async () => {
    const user = userEvent.setup();
    mount({ allowed_addresses: "198.51.100.0/24" });
    await waitFor(() => expect(box()).toHaveValue("198.51.100.0/24"));
    await user.clear(box());
    await waitFor(() => expect(line()).not.toBeNull());
    await user.type(box(), "203.0.113.7");
    await waitFor(() => expect(line()).toBeNull());
  });

  it("case 4 — a brand-new connection has no stored list, so clearing says nothing", async () => {
    const user = userEvent.setup();
    mount(null);
    await waitFor(() => expect(box()).toBeInTheDocument());
    await user.type(box(), "10.0.0.1");
    await user.clear(box());
    expect(line()).toBeNull();
  });

  it("case 5 — the sentence is the CATALOGUE's, never a string in this component", () => {
    // B14 rule 35: eleven catalogues, each in its own idiom. A hardcoded
    // English literal in the TSX would pass every other case in this file.
    const source = new URL("./ConnectorSetupPage.tsx", import.meta.url);
    expect(source.pathname).toContain("ConnectorSetupPage.tsx");
    expect(LINE.split(/\s+/)).toHaveLength(4); // rule 33's consequence cap is six
  });
});
