// @vitest-environment jsdom
//
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-LED-6499 — Finance > General ledger told a clerk the journal
//          could not be filtered to one property, over a filter served in SQL
//          since 2026-09-03 (`CR-060` C24).
// Change:  Finance blueprint `P2.3` (add the control) + `P2.4` (delete the
//          panel that denied it), p014; the screen's own criteria table on
//          p023 marks `Property · premises · api.py:395 → reporting.py:730`
//          **SERVED**.
// Rules:   B14 rule 33 (RATIONALE is ZERO words on screen — rationale is
//          REMOVED, never shortened) · B14 rule 31 (no database id is a visible
//          value) · B14 rule 43 (a piece of UI is a COMPONENT) ·
//          B14 rule 8 (5+ options are searchable) · IS-3 (server search,
//          from two characters) · NFR-3 (universal server pagination) ·
//          NFR-5 (no hard caps anywhere) · CLAUDE.md hard-won law 2
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE ASSERTION THE PANEL'S OWN TEST NEVER MADE                           ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// The absence panel this replaces was covered by a test that asserted its
// sentence was PRESENT in eleven catalogues and that its English read exactly
// *"Every journal line carries its property. No report filters on it yet."*
// Both were true when written. **Neither could go red on the day the filter
// shipped**, so the screen went on denying a built feature for three weeks
// while every check passed — `DEF-2346`'s shape, which the decision log had
// already recorded about this same screen, repeated one panel further down.
//
// ⚠ **SO WHAT IS PINNED HERE IS THE WIRE, NOT THE WORDS.** A control can be
// drawn, labelled, translated into eleven languages and keyboard-reachable
// while sending nothing — hard-won law 2's dead UI, which `tsc` and a render
// assertion both pass over. The question that decides whether this task was
// actually done is *does `f.premises` reach the server*, and that is the
// question below.
//
// ⚠ **AND THE CACHE KEY IS THE SECOND HALF.** react-query answers by key: a
// filter the key does not name changes the request and not the cached answer,
// so the control moves, `f.premises` goes out on the wire, and the table keeps
// showing every property. That failure passes a naive "did we call the API"
// assertion, which is why the test reads the rows the screen ENDS UP with as
// well as the request it sent.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { GeneralLedgerPage } from "./GeneralLedgerPage";

const t = i18n.getFixedT("en");

/** Two properties, so "filtered" and "unfiltered" are different answers. */
const OAK = "01a0763a-0000-7000-8000-00000000pre1".replace("pre1", "0001");
const MARINA = "01a0763a-0000-7000-8000-00000000pre2".replace("pre2", "0002");

const PREMISES_PAGE = {
  count: 2,
  next: null,
  previous: null,
  rollup: {},
  results: [
    {
      id: OAK,
      premise_no: "PRM-0001",
      name: null,
      address_line: "500 Main St",
      city: "Oak Grove",
      state: "TX",
      postal_code: "78704",
      premises_type: null,
      premises_type_name: null,
    },
    {
      id: MARINA,
      premise_no: "PRM-0002",
      name: null,
      address_line: "12 Marina Bay",
      city: "Marina Bay",
      state: "TX",
      postal_code: "78705",
      premises_type: null,
      premises_type_name: null,
    },
  ],
};

/** One trial-balance row, in the exact shape `wire.trial_balance_dict` serves
 *  — every money field present, because `MoneyCell` REFUSES an absent amount by
 *  design (`DEF-151`) rather than drawing a zero, and a short fixture would
 *  fail this file for a reason that has nothing to do with the filter. */
function row(debit: string, closing: string) {
  return {
    account_id: "a1",
    code: "1200",
    name: "Accounts receivable",
    type: "asset",
    debit,
    credit: "0.000000",
    gross_debit: debit,
    gross_credit: "0.000000",
    opening: "0.000000",
    closing,
  };
}

/** Every property, and then only Oak Grove's — so a filter that does not bite
 *  shows the wrong NUMBER rather than merely the wrong row count. */
function trialBalance(filtered: boolean) {
  const debit = filtered ? "247.870000" : "553.690000";
  return {
    basis: "posting",
    currency: "USD",
    period: { start: "2026-07-01", end: "2026-07-31" },
    rows: [row(debit, debit)],
    total_debit: debit,
    total_credit: debit,
    total_opening: "0.000000",
    total_closing: "0.000000",
    difference: "0.000000",
    balanced: true,
  };
}

/** Records every path+query the screen asks for, and answers each read. */
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

      if (path.startsWith("/premises")) {
        return { data: PREMISES_PAGE };
      }
      if (path.startsWith("/shell/display")) {
        // The served accounting period. Without it `period` is null, the
        // trial-balance block never renders at all, and every assertion below
        // would fail for a reason that has nothing to do with the filter.
        return { data: { period: { start: "2026-07-01", end: "2026-07-31" } } };
      }
      if (path.includes("permissions")) {
        // BR-SHL-025's UI gating. Full access, because this test is about the
        // control and not about who may see it — a null cell hides nothing and
        // would leave the assertions passing over an unrendered screen.
        return { data: { permissions: [{ code: "finance_reconcile_export", access: "full" }] } };
      }
      if (path.includes("trial-balance")) {
        // THE POINT OF THE FIXTURE: the server answers differently when the
        // filter arrives, so a screen that sends it and ignores the answer is
        // distinguishable from one that filters properly.
        const filtered = query.get("f.premises");
        return { data: trialBalance(filtered === OAK) };
      }
      // Every other read the page makes — the close checklist, the chart, the
      // journal — answers EMPTY rather than throwing: this test is about one
      // control, and a screen that crashed on an unrelated read would fail for
      // a reason that teaches nobody anything.
      //
      // ⚠ `items` and `incomplete` are named because `CloseReadinessStrip`
      // calls `.filter` on them unguarded; an over-general `{}` here threw
      // before the params band ever rendered, and the failure read as
      // "the control is missing" rather than "the fixture is short".
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

/** ⚠ MOUNTED UNDER THE REAL PATH PATTERN (`DEF-CWP-3925`'s fixture lesson) — a
 *  bare `MemoryRouter` with no `/:tenant/…` route leaves `useParams().tenant`
 *  undefined, and every address the tree builds comes out `//…`, which reads as
 *  a perfectly good string to an assertion. */
function mount(client: ApiClient) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      {/* The page fires an A13 toast on every write, so the provider is part of
          its real mounting rather than scaffolding — without it the component
          throws before it renders a thing. */}
      <ToastProvider>
        {/* ⚠ **`?view=balance` IS LOAD-BEARING SINCE `P1.15`.** The sibling lane
          split the journal onto its own view and made `journal` the LANDING
          one, so `glViewFrom(null)` now answers `journal` — a fixture that
          entered with no `?view=` would render the journal, find no params
          band, and fail with "the control is missing" over a control that is
          there. The property filter lives on the Balance view, which is where
          p023's note 2 puts it. */}
      <MemoryRouter initialEntries={["/brazosbend/finance/general-ledger?view=balance"]}>
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

afterEach(cleanup);

describe("DEF-LED-6499 · P2.3 — the property filter reaches the server", () => {
  it("draws the control the deleted panel was standing in for", async () => {
    const { client } = recordingClient();
    mount(client);
    // ≤ 3 words, no sentence (B14 rule 33). The field's NAME.
    expect(
      await screen.findByRole("combobox", { name: t("finance.gl.premisesFilter.label") }),
    ).toBeTruthy();
  });

  it("sends f.premises, and the table takes the filtered answer", async () => {
    // PROVED RED FIRST, twice, through this same test, and the second proof
    // taught something the first draft of this comment got wrong:
    //
    //  (a) the control removed from the params band —
    //      TestingLibraryElementError: Unable to find role="combobox" and name
    //      "Property"  (all three cases red)
    //
    //  (b) the control present but `premisesId` left OUT of
    //      `trialBalanceQueryKey` —
    //      AssertionError: expected [] to not have a length of +0
    //
    // ⚠ **(b) IS SHARPER THAN EXPECTED AND THE COMMENT IS CORRECTED TO WHAT WAS
    // ACTUALLY WATCHED (hard-won law 1).** This was written predicting *"the
    // request goes out and the table keeps 553.69"*. It does not: with the key
    // unchanged react-query answers from CACHE and **no second request is made
    // at all**, so `f.premises` never reaches the wire. The cache key is not a
    // tidiness detail on top of a working filter — it is what makes the filter
    // happen. A lane that "simplified" it away would break the feature
    // completely while the control still moved on screen.
    const { client, calls } = recordingClient();
    const user = userEvent.setup();
    mount(client);

    const field = await screen.findByRole("combobox", { name: t("finance.gl.premisesFilter.label") });
    // IS-3: nothing is asked below two characters, so one keystroke must not
    // produce a request. Asserted rather than assumed — a control that searches
    // on every keystroke is 40,000 round trips at T5.
    await user.type(field, "O");
    expect(calls.filter((call) => call.startsWith("/premises"))).toHaveLength(0);

    await user.type(field, "ak");
    await screen.findByText("PRM-0001 — 500 Main St");
    await user.click(screen.getByText("PRM-0001 — 500 Main St"));

    await waitFor(() => {
      expect(calls.filter((call) => call.includes("f.premises"))).not.toHaveLength(0);
    });
    // The id is the VALUE and never the label (B14 rule 31) — what a clerk
    // reads is the premise number and the address.
    expect(calls.some((call) => call.includes(`f.premises=${OAK}`))).toBe(true);

    // …and the FILTERED figure is what the table ends up showing. This is the
    // cache-key half; without `premisesId` in the key this line is the only
    // thing in the file that goes red.
    await waitFor(() => {
      expect(document.body.textContent).toContain("247.87");
    });
    expect(document.body.textContent).not.toContain("553.69");
  });

  it("puts no database id on screen", async () => {
    // B14 rule 31, and the one assertion that has to read RENDERED text rather
    // than markup: this rule's own shape puts the internal value on `title`, so
    // a check over the DOM string goes green on the breach and red on the fix.
    const { client } = recordingClient();
    const user = userEvent.setup();
    mount(client);
    const field = await screen.findByRole("combobox", { name: t("finance.gl.premisesFilter.label") });
    await user.type(field, "Oak");
    await screen.findByText("PRM-0001 — 500 Main St");
    expect(document.body.textContent).not.toContain(OAK);
  });
});
