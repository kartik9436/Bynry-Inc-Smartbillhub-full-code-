// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-LED-005 (the chart of accounts is tenant-customizable — add,
//           rename, re-point a designation).  Screen: SET-11 · S56
// Defects:  DEF-LED-6140 — add and edit were inline forms at the BOTTOM of a
//           15,354px panel, and the one refusal strip rendered at the TOP of
//           it, so pressing Save on an edit the server refused changed nothing
//           the clerk could see.
// Rules:    B14 rule 43 (a piece of UI is built as a COMPONENT — these are
//           `FormModal` dialogs, not a seventh inline form) · BR-SHL-020 (a
//           refusal is shown in plain language) · B14 rule 33 (the caps)
// ─────────────────────────────────────────────────────────────────────────
/**
 * ⚠ **THIS FILE ASSERTS *CONTAINMENT*, NOT PRESENCE, AND THAT IS THE WHOLE
 * POINT OF IT.**
 *
 * The defect these cases exist for was never a missing sentence. The refusal
 * was in the document the entire time — `expect(html).toContain(…)` passed, and
 * would have passed for the twenty days before anyone looked. It was **14,428px
 * above the button that produced it**, outside an 844px scroll viewport, and no
 * check in this repository can see a pixel.
 *
 * What a test CAN see is the DOM tree: *is the refusal a descendant of the
 * dialog the clerk is looking at?* A sentence inside the modal card cannot be
 * off-screen, because the card is what has the clerk's attention. So every
 * assertion below is scoped with `within(dialog)` rather than `screen`, and
 * using `screen` here would quietly restore the bug.
 */
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * ⚠ **THE CATALOGUE IS MOCKED, AND THAT IS A DECISION RATHER THAN A SHORTCUT.**
 *
 * `import "@/i18n"` pulls all ELEVEN locale files — about 1.3MB each — through
 * vite's transform before a single case runs. On a loaded machine that fetch
 * times out and the suite reports **`0 test`**, which is not a failing
 * assertion: it is a file that could not be asked the question. It did exactly
 * that three times while this was being written, and it does the same to
 * `ledgerAdmin.test.tsx`, which nothing here touched.
 *
 * **These cases are about WHERE a sentence renders, never about what it says.**
 * G33 owns the words and G15 owns the eleven catalogues; asserting on the KEY
 * proves containment just as well as asserting on the English, and it lets the
 * file run in about a second. A test that cannot be run is worth less than one
 * that asks a slightly smaller question.
 */
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: "en" } }),
  Trans: ({ i18nKey }: { i18nKey: string }) => i18nKey,
  initReactI18next: { type: "3rdParty", init: () => undefined },
}));

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";

import { ToastProvider } from "@/components/Toast";

import { ChartOfAccountsPanel } from "./ChartOfAccountsPanel";

/** The panel takes its own translator as a prop; identity, to match the mock. */
const t = (key: string) => key;

const ROW = {
  account_id: "acc-1",
  code: "1000",
  name: "Cash",
  type: "asset",
  category: "cash_and_investments",
  designation: "cash",
  status: "active",
  finance_signed: true,
  references: undefined,
};

const CHART = {
  rows: [ROW],
  types: ["asset", "liability", "equity", "revenue", "expense"],
  categories: ["cash_and_investments", "receivables"],
  designations: ["cash", "accounts_receivable"],
  pending_finance_re_sign_cost: [],
};

/**
 * A client that SERVES the chart and REFUSES the write, which is the exact
 * pair the defect lives between: the list is fine, the save is not.
 *
 * `refusal` is a real `ApiError` built from a real envelope, not a hand-made
 * object — `formErrorEnvelope` reads `fieldErrors` off the class, so a fake
 * would exercise a path the product does not have.
 */
function clientThatRefuses(envelope: {
  message_key: string;
  params?: Record<string, unknown>;
  field_errors?: { field: string; code: string | null; message_key: string }[];
}): ApiClient {
  const refuse = async () => {
    throw new ApiError(409, {
      code: "BIZ_STATE",
      message_key: envelope.message_key,
      params: envelope.params ?? {},
      field_errors: envelope.field_errors ?? [],
      br_ref: "BR-LED-014",
      trace_id: "0123456789abcdef0123456789abcdef",
    });
  };
  return {
    get: async () => ({ data: CHART }),
    post: refuse,
    patch: refuse,
    put: refuse,
    delete: refuse,
  } as unknown as ApiClient;
}

/** ⚠ MOUNTED UNDER THE REAL PATH PATTERN (`DEF-CWP-3925`'s fixture lesson) —
 *  a bare `MemoryRouter` with no `/:tenant/…` route leaves `useParams().tenant`
 *  undefined, and every address the tree builds then comes out `//…`, which
 *  reads as a perfectly good string to an assertion. */
function mount(client: ApiClient) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      {/* The panel fires an A13 toast on every SUCCESS, so the provider is part
          of its real mounting and not scaffolding — without it the component
          throws before it renders a thing. */}
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/settings/accounting"]}>
          <Routes>
            <Route
              path="/:tenant/settings/accounting"
              element={
                <ChartOfAccountsPanel
                  client={client}
                  now={() => "2026-09-22T00:00:00Z"}
                  t={t}
                  sections="chart"
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("DEF-LED-6140 · the chart's add and edit are dialogs", () => {
  it("offers Add at the TOP of the panel, and draws no form under the table", async () => {
    mount(clientThatRefuses({ message_key: "ledger.chart.code_taken" }));
    const add = await screen.findByRole("button", { name: t("finance.coa.add.open") });

    // THE DOOR IS IN THE TABLE'S OWN HEADING, which is what "on top, not at
    // bottom" means structurally: the button and the `<h3>` share a parent.
    const heading = screen.getByRole("heading", { name: t("finance.coa.title") });
    expect(heading.parentElement).toBe(add.parentElement);

    // AND THE TWO BOTTOM FORMS ARE GONE. Asserted as an ABSENCE of the heading
    // they carried, because an absence is what regressed here and an absence is
    // invisible to every other check in this repo.
    expect(screen.queryByRole("heading", { name: t("finance.coa.add.title") })).toBeNull();
    // Nothing commits until the dialog is opened, so the submit label — which
    // used to sit permanently on the page — must not be rendered at rest.
    expect(screen.queryByRole("button", { name: t("finance.coa.add.submit") })).toBeNull();
  });

  it("puts a refused SAVE inside the dialog, beside the button that failed", async () => {
    // The refusal the PO actually hit: another account already holds the role.
    // It arrives with NO field on it in the general case, so it is the
    // form-level line — and the question is where that line lands.
    mount(
      clientThatRefuses({
        message_key: "ledger.chart.designation_taken",
        params: { designation: "cash" },
      }),
    );
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: t("finance.coa.action.edit") }));

    const dialog = await screen.findByRole("dialog");
    const save = within(dialog).getByRole("button", { name: t("finance.coa.edit.submit") });
    await user.click(save);

    // ⚠ **`within(dialog)`, NEVER `screen`.** `screen.getByText(...)` passed on
    // the broken version too — the sentence was in the document, seventeen
    // screenfuls above the clerk. Scoping the query to the dialog is the
    // assertion; widening it back to `screen` is the defect returning.
    await waitFor(() =>
      expect(within(dialog).getByText(t("ledger.chart.designation_taken"))).toBeInTheDocument(),
    );
    // …and the dialog STAYS OPEN, so the clerk can act on what they just read.
    expect(within(dialog).getByRole("button", { name: t("finance.coa.edit.submit") })).toBeVisible();
  });

  it("puts a field reason on the field it names, and never says it twice", async () => {
    // `ledger.chart.code_taken` names `code` since DEF-LED-6140, so the sentence
    // belongs under the CODE box rather than above the buttons.
    mount(
      clientThatRefuses({
        message_key: "ledger.chart.code_taken",
        params: { code: "1000" },
        field_errors: [
          { field: "code", code: "BIZ_STATE", message_key: "ledger.chart.code_taken" },
        ],
      }),
    );
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: t("finance.coa.add.open") }));

    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText(/finance\.coa\.col\.code/), "1000");
    await user.type(within(dialog).getByLabelText(/finance\.coa\.col\.name/), "Petty cash");
    await user.click(within(dialog).getByRole("button", { name: t("finance.coa.add.submit") }));

    const sentence = t("ledger.chart.code_taken");
    await waitFor(() => expect(within(dialog).getAllByText(sentence).length).toBeGreaterThan(0));

    // ON the box: the input is marked invalid and DESCRIBED BY the message, so
    // a screen reader announces the two together (BR-SHL-017 / IS-10).
    const code = within(dialog).getByLabelText(/finance\.coa\.col\.code/);
    expect(code).toHaveAttribute("aria-invalid", "true");
    const describedBy = code.getAttribute("aria-describedby") ?? "";
    const named = describedBy
      .split(" ")
      .map((id) => document.getElementById(id)?.textContent ?? "")
      .join(" ");
    expect(named).toContain(sentence);

    // ⚠ ONCE. The envelope carries this sentence TWICE on purpose — as the
    // top-level `message_key` and inside `field_errors` — so a screen with no
    // form around it still has something to print. A dialog that rendered both
    // would put the identical words under the input and above the buttons,
    // which reads as two different problems (B14 rule 32).
    expect(within(dialog).getAllByText(sentence)).toHaveLength(1);
  });
});
