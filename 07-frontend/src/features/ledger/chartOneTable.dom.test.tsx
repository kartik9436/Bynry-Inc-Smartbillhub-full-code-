// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Defect:  DEF-LED-6715 — Finance > General ledger > Chart was five tables
//          where the PO asked for one. PO, 2026-09-25: *"i will have 1 table
//          only and i will use columns to manage rest of the table"*, and of
//          the four panels beneath the chart: *"cant we merge it in charts -
//          first table itself"*.
// Drawing: 05-prototype/07 Finance Blueprint.pdf p024 (1·3 Chart, ONE panel,
//          nine columns) and p025 note 1 — *"the mapping is columns ④, not a
//          second name"* — read as IMAGES (B14 rule 42).
// Rules:   B14 rule 31 (no database id or raw code is ever the visible value) ·
//          rule 32 (a stated absence is CLOSED by default) · rule 33
//          (RATIONALE is zero words on screen) · BR-LED-796 (the worked case
//          of ONE caller that must refuse an unfilled role rather than
//          substitute — NOT a general refusal: measured 2026-09-25,
//          `selectors.gl_account_for_designation` returns None for an
//          unfilled role and raises only on an unknown designation NAME, so
//          the cases below assert that the gap is VISIBLE, which is the only
//          thing this screen can guarantee) · BR-SHL-013 (the identity
//          column can never be hidden)
// ─────────────────────────────────────────────────────────────────────────
/**
 * ⚠ **THE FIRST CASE IN THIS FILE IS A GUARD, AND EVERY ABSENCE ASSERTION
 * BELOW IT IS WORTHLESS WITHOUT IT.**
 *
 * An absence assertion over a blank page is the easiest false pass in this
 * repository to write, and it has already happened on these exact screens: the
 * one route-level rendered-output check could not reach any Finance screen's
 * BODY — with reads disabled the page stops at *"Set the fiscal year start to
 * see the current period"* — so five of its six *"this panel is absent"*
 * assertions were passing over nothing at all. A sibling lane deleted it rather
 * than ship a check that cannot fail.
 *
 * So `renders the accounts table at all` runs first and asserts the POSITIVE:
 * the chart's own heading, its column headers and a real row. Only a tree that
 * passes that is a tree in which *"the tax panel is gone"* means anything.
 *
 * ⚠ **AND THE SECOND HALF IS THE ONE THIS DEFECT WAS FILED WITH A WARNING
 * ABOUT.** Deleting *What each kind of money lands in* removes the only place
 * the product said *"No live account has this role"*. **That is true** — a
 * posting that needs an unfilled role refuses by name — and **a column cannot
 * carry it, because an unfilled role has no account row to appear on.** So the
 * absence became a served count and a filter value, and the cases below FAIL
 * if either stops being reachable. That is hard-won law 2's mirror written as a
 * test rather than as a paragraph: a real absence that stops being visible
 * because the thing that showed it was tidied away.
 */
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

// The catalogue is mocked for the reason `chartDialogs.dom.test.tsx` states in
// its own header: pulling eleven 1.3MB locale files through vite's transform
// makes this file report `0 test` on a loaded machine, which is not a failing
// assertion but a question nobody asked. These cases are about WHICH controls
// and cells exist, never about what the words say — G33 owns the words and G15
// owns the eleven catalogues.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: "en" } }),
  Trans: ({ i18nKey }: { i18nKey: string }) => i18nKey,
  initReactI18next: { type: "3rdParty", init: () => undefined },
}));

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { ChartOfAccountsPanel } from "./ChartOfAccountsPanel";

const t = (key: string) => key;

const ROWS = [
  {
    account_id: "acc-1",
    code: "1000",
    name: "Cash",
    type: "asset",
    category: "cash_and_investments",
    designation: "cash",
    status: "active",
    qbo_ref: "QBO-101",
    xero_ref: null,
    created_at: null,
    finance_signed: true,
    seeded: true,
    references: undefined,
  },
  {
    account_id: "acc-2",
    code: "2200-01",
    name: "Tax payable, State of Texas",
    type: "liability",
    category: "current_liabilities",
    designation: "tax_payable",
    status: "active",
    qbo_ref: null,
    xero_ref: "XR-L20",
    created_at: null,
    finance_signed: true,
    seeded: false,
    references: undefined,
  },
];

/**
 * ⚠ **THE THREE ROLES ARE THE ONES THE DEMO TENANT ACTUALLY HAS, READ BACK FROM
 * A REAL POSTGRES ON 2026-09-25**, not three names chosen to make a case pass:
 * `services.chart_of_accounts()` on `brazosbend` returns exactly
 * `('accrued_expenses', 'accumulated_depreciation', 'allowance_doubtful_accounts')`.
 *
 * `cash_over_short` was a fourth when this defect was reported and has an
 * account now, which is WHY the count is served and never hardcoded anywhere:
 * a screen carrying its own list of four would go on saying four.
 */
const ROLES_NEEDING_ACCOUNT = [
  "accrued_expenses",
  "accumulated_depreciation",
  "allowance_doubtful_accounts",
];

function chartPayload(overrides: Record<string, unknown> = {}) {
  return {
    rows: ROWS,
    types: ["asset", "liability", "equity", "revenue", "expense"],
    categories: ["cash_and_investments", "current_liabilities"],
    designations: ["cash", "tax_payable", "accrued_expenses"],
    roles_needing_account: ROLES_NEEDING_ACCOUNT,
    pending_finance_re_sign: [],
    pending_finance_re_sign_cost: [],
    pending_finance_re_sign_books: [],
    cost_section_source: "",
    utility_books_source: "",
    currency: "USD",
    ...overrides,
  };
}

/**
 * A client that serves the chart and refuses everything else BY NAME.
 *
 * ⚠ **`GET /settings/preferences/...` MUST ANSWER, AND ANSWER `null`.** The
 * column chooser reads the stored set on mount (BR-SHL-024: an unknown key
 * reads as ABSENT and the caller keeps its defaults). A client that threw here
 * would leave the panel on its defaults too — by accident — and the case that
 * asserts the default column set would pass for the wrong reason.
 */
function client(payload: Record<string, unknown> = chartPayload()): ApiClient {
  return {
    get: async (path: string) => {
      if (path.includes("/preferences")) {
        return { data: null };
      }
      return { data: payload };
    },
    post: async () => ({ data: {} }),
    patch: async () => ({ data: {} }),
    put: async () => ({ data: {} }),
    delete: async () => ({ data: {} }),
  } as unknown as ApiClient;
}

function mount(api: ApiClient) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        {/* ⚠ MOUNTED UNDER THE REAL PATH PATTERN (`DEF-CWP-3925`'s fixture
            lesson): a bare `MemoryRouter` with no `/:tenant/…` route leaves
            `useParams().tenant` undefined, and every address the tree builds
            comes out `//…` — which reads as a perfectly good string to an
            assertion. */}
        <MemoryRouter initialEntries={["/brazosbend/finance?view=chart"]}>
          <Routes>
            <Route
              path="/:tenant/finance"
              element={
                <ChartOfAccountsPanel client={api} now={() => "2026-09-25T00:00:00Z"} t={t} />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("DEF-LED-6715 · the Chart tab is ONE table", () => {
  // ══ THE GUARD ═══════════════════════════════════════════════════════════
  it("GUARD — the accounts table renders, so an absence below means something", async () => {
    mount(client());
    // The POSITIVE first: a heading, a column header and a real row. Each of
    // the three fails differently, which is what makes this a guard rather than
    // a smoke test — a tree with headers and no rows is a skeleton, and a
    // skeleton is exactly what the walkthrough photographed on its first run.
    expect(await screen.findByText("finance.coa.title")).toBeInTheDocument();
    expect(await screen.findByRole("columnheader", { name: "finance.coa.col.code" })).toBeVisible();
    expect(await screen.findByText("Tax payable, State of Texas")).toBeInTheDocument();
  });

  it("draws ONE table, and the four panels beneath it are gone", async () => {
    mount(client());
    await screen.findByText("Tax payable, State of Texas");
    // GUARDED: the row above proves the body rendered before any of this runs.
    expect(document.querySelectorAll("table")).toHaveLength(1);
    // Each deleted panel by the heading key it drew. Asserting the KEY rather
    // than the English is deliberate — the catalogue is mocked to identity here
    // — and it is STRICTER, because a panel that came back with re-worded copy
    // would still carry its key.
    for (const heading of [
      "finance.map.designations.title",
      "finance.map.services.title",
      "finance.map.taxes.title",
      "finance.map.export.title",
    ]) {
      expect(screen.queryByText(heading)).not.toBeInTheDocument();
    }
  });

  it("the package codes are COLUMNS now, off by default and on from the menu", async () => {
    const user = userEvent.setup();
    mount(client());
    await screen.findByText("Tax payable, State of Texas");
    // p025 note 4's judgment, carried across: they are the two columns an admin
    // turns on to reconcile with their package and nobody else ever wants.
    expect(screen.queryByRole("columnheader", { name: "finance.map.col.qbo" })).toBeNull();
    await user.click(screen.getByLabelText("table.columns.open"));
    await user.click(screen.getByLabelText("finance.map.col.qbo"));
    expect(
      await screen.findByRole("columnheader", { name: "finance.map.col.qbo" }),
    ).toBeVisible();
    // US-LED-006 TC-1 — a gap is a VISIBLE empty state, never a blank cell:
    // `BR-LED-014` makes the ref required per target AT EXPORT, so this is what
    // the S42 gate refuses the month on.
    expect(screen.getByText("finance.map.noRef")).toBeInTheDocument();
  });

  // ══ THE WARNING THAT HAD TO SURVIVE THE DELETION ════════════════════════
  it("BR-LED-796 — the roles with no account are COUNTED without opening anything", async () => {
    mount(client());
    await screen.findByText("Tax payable, State of Texas");
    const badge = await screen.findByTestId("coa-unfilled-roles-count");
    // The NUMBER, not a sentence. B14 rule 33 puts the reason at zero words on
    // screen; the count is a fact and is the whole disclosure.
    expect(badge).toHaveTextContent("3");
  });

  it("BR-LED-796 — and are REACHABLE, by their human names, through the filter", async () => {
    const user = userEvent.setup();
    mount(client());
    await screen.findByText("Tax payable, State of Texas");
    // OPERATED THROUGH THE CONTROL A CLERK USES, never by poking state: a test
    // that sets the filter directly proves nothing about whether the option is
    // on the menu.
    await user.selectOptions(screen.getByTestId("coa-role-filter"), "needs-account");
    const table = await screen.findByRole("table");
    for (const role of ROLES_NEEDING_ACCOUNT) {
      // B14 rule 31 — the HUMAN name. `DEF-LED-6612` is this exact cell
      // rendering `accrued_expenses` on the panel this replaces, and the raw
      // code is a real non-empty string that every `toContain` passes over.
      expect(within(table).getByText(`finance.designation.${role}`)).toBeInTheDocument();
      expect(within(table).queryByText(role)).toBeNull();
    }
    // And the accounts are NOT also on screen — this is a different question
    // and answering both at once would put two kinds of row in one table.
    expect(within(table).queryByText("Tax payable, State of Texas")).toBeNull();
  });

  it("B14 rule 32 — the absence is CLOSED by default: the list is not on arrival", async () => {
    mount(client());
    await screen.findByText("Tax payable, State of Texas");
    // The count is visible; the roles themselves are not, until asked for.
    // ⚠ **SCOPED TO THE TABLE, AND THE FIRST DRAFT WAS NOT — IT LOOKED AT THE
    // WRONG THING AND WENT RED.** `accrued_expenses` is also an `<option>` in
    // the Role filter, legitimately, because it is a designation some account
    // could carry. A page-wide `queryByText` therefore asks *"does this string
    // appear anywhere"* when the question is *"is the ROLE LIST rendered"*.
    const table = screen.getByRole("table");
    expect(within(table).queryByText("finance.designation.accrued_expenses")).toBeNull();
  });

  it("says NOTHING when every role has an account — no badge, no option", async () => {
    // ⚠ **THE OTHER DIRECTION, AND IT IS WHAT STOPS THE COUNT BECOMING
    // FURNITURE.** A badge reading 0 on a healthy chart is noise a clerk learns
    // to ignore, and the day it reads 3 they ignore that too.
    mount(client(chartPayload({ roles_needing_account: [] })));
    await screen.findByText("Tax payable, State of Texas");
    expect(screen.queryByTestId("coa-unfilled-roles-count")).toBeNull();
    const filter = screen.getByTestId("coa-role-filter");
    expect(within(filter).queryByText("finance.coa.filter.roleNeedsAccount")).toBeNull();
  });

  it("the Role filter is SERVED, not sliced — choosing one re-asks the server", async () => {
    const user = userEvent.setup();
    const asked: string[] = [];
    const api = {
      get: async (path: string, options?: { query?: Record<string, unknown> }) => {
        if (path.includes("/preferences")) {
          return { data: null };
        }
        asked.push(String(options?.query?.["f.designation"] ?? ""));
        return { data: chartPayload() };
      },
      post: async () => ({ data: {} }),
      patch: async () => ({ data: {} }),
      put: async () => ({ data: {} }),
      delete: async () => ({ data: {} }),
    } as unknown as ApiClient;
    mount(api);
    await screen.findByText("Tax payable, State of Texas");
    await user.selectOptions(screen.getByTestId("coa-role-filter"), "tax_payable");
    // NFR-3 — the filter is a REQUEST, not a `rows.filter()` in the browser. A
    // screen that narrowed its own page would be right on this fixture's two
    // rows and wrong on the PO's 282.
    await waitFor(() => expect(asked).toContain("tax_payable"));
  });

  it("BR-SHL-013 — the identity column cannot be hidden", async () => {
    const user = userEvent.setup();
    mount(client());
    await screen.findByText("Tax payable, State of Texas");
    await user.click(screen.getByLabelText("table.columns.open"));
    // A chart row with no code is not a row anybody can act on. The lock is
    // enforced in the TRANSITION and not only on the checkbox, which is what a
    // keyboard and an old stored preference go through.
    expect(screen.getByLabelText("finance.coa.col.code")).toBeDisabled();
  });
});
