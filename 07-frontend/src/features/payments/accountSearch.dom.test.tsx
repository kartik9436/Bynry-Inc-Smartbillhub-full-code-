// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-3506 — "On this payment record form unable to search account"
//          (Product Owner, walking the deployed build 2026-09-03). They typed
//          `AC-2026-00050` into "Find the account" and the Account dropdown
//          below still read "Choose an account".
// Story:   US-PAY-001 (the S22/S35 Record modal) · US-PAY-015 (S36 refunds —
//          the same picker, the same defect)
//          Screens: S22 · S35 · S36
// Rules:   IS-3 (search is SERVER-side and starts at two characters) ·
//          BR-SHL-020 (plain-language failure) · BR-SHL-012 (the A18 states —
//          a screen says which one it is in) · B14 rule 31 (no database id is
//          the visible value of a field) · B14 rule 32 (one sentence per
//          section)
// ───────────────────────────────────────────────────────
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHAT THE MODAL DID BEFORE THIS FILE, AND WHY IT LOOKED LIKE NOTHING     ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// The wire path was never broken, and that was established BEFORE anything was
// changed: a throwaway render of the pre-fix modal typed `AC-2026-00050`, waited
// on the select's options and logged them —
//
//     CALLS: ["/accounts {\"q\":\"AC-2026-00050\",\"per\":50}"]
//     OPTIONS: ["Choose an account","AC-2026-00050 — Miller, Sarah"]
//
// The query fired, the row came back and the option landed. So the fix is NOT
// to the request, and a lane that had gone straight to `getAccounts` would have
// changed a line that worked. The screen was still unusable, for two reasons
// that both look identical to a clerk:
//
//   1. **The two-character gate trimmed the term and the request did not.**
//      `enabled: accountQuery.trim().length >= 2` beside
//      `getAccounts({ q: accountQuery })`. Paste an account number out of a
//      spreadsheet or an email and the trailing space travels to the server,
//      where `account_no ILIKE '%AC-2026-00050 %'` matches nothing. The two
//      OTHER account searches in this product — `customers/accountFinder.tsx`
//      and `metering/OwnerAccount.tsx` — both send the trimmed term; payments
//      was the odd one out, twice (this modal and S36's).
//   2. **Nothing was drawn for searching, for no-match or for failed.** The
//      select renders its placeholder in all three states and in the success
//      state too, so "still looking", "no such account", "the search could not
//      run" and "here are your matches, open me" are ONE picture. That is the
//      PO's sentence exactly: the dropdown "still read Choose an account".
//
// **RED PROVED FIRST (hard-won law 7).** All FIVE cases below were run against
// the pre-fix build and all five failed. Verbatim:
//
//   × typing an account number offers that account, and it can be chosen
//     → expected 'Choose an account' to contain 'AC-2026-00050 — Miller, Sarah'
//   × a number pasted with a trailing space still finds the account
//     → expected [ '/accounts {"q":"AC-2026-00050 ","per":50}' ] to include
//       '/accounts {"q":"AC-2026-00050","per":50}'
//   × a search that matched nothing says so, in place of an empty picker
//     → Unable to find an element with the text:
//       payments.form.accountNoMatch
//   × a search that could not run says so, and is not read as no-match
//     → Unable to find an element with the text:
//       payments.form.accountSearchFailed
//   × the picker is not drawn until something matches
//     → expected <select id="account_id" …(2)>…(1)</select> to be null
//
//     Tests  5 failed (5)
//
// ⚠ **READ WHY CASE 1 WENT RED, BECAUSE IT IS NOT WHAT IT LOOKS LIKE AND A
// LANE THAT MISREADS IT FIXES THE WRONG THING.** It did NOT fail because the
// search was broken — the log above proves it was not. It failed because it
// waits on `#account_id` APPEARING, and before this change that select was
// always in the DOM, so the wait returned immediately and read the options
// before the query had resolved. **That is the defect stated as a timing
// fact:** a control whose presence carries no information cannot be waited on,
// and a clerk cannot wait on it either. After the fix the select appears only
// when something matched, so the same line is a real wait and the case passes
// for the reason it is written for.
// The two failures naming a raw key (`payments.form.accountNoMatch`) are the
// catalogue answering with the key because the sentence did not exist yet —
// which is the honest shape of "this screen had nothing to say".
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { AccountRow, PaymentMethodOption } from "@/api/endpoints";
import i18n from "@/i18n";
import { ToastProvider } from "@/components/Toast";

// ⚠ **`RecordPaymentModal` BECAME `RecordPaymentForm` ON 2026-09-23 (`DEF-PAY-6317`).**
// 2·3a is a PAGE at `/:tenant/payments/record/new` (blueprint p037), so the
// form is a COMPONENT (B14 rule 43) inside `FormPage` rather than `FormModal`.
// Same props, with `onClose` renamed `onCancel` — a page goes BACK somewhere;
// it does not close. Every case below is unchanged and asserts the same thing.
import { RecordPaymentForm } from "./RecordPaymentPage";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

const METHODS: PaymentMethodOption[] = [{ id: "met-check", code: "check", name: "Check" }];

/**
 * The account the Product Owner typed. `AC-2026-00050` is the tenant's own
 * numbering series — `customers/accountFinder.tsx` quotes the same shape in its
 * own help line — so this fixture is the row that walk was looking for.
 */
function account(over: Partial<AccountRow> = {}): AccountRow {
  return {
    id: "acc-0050",
    account_no: "AC-2026-00050",
    customer_no: "CU-2026-00050",
    name: "Miller, Sarah",
    unit_id: "unit-1",
    unit_label: "A",
    premises_id: "prem-1",
    premise: "1408 Elm St · A",
    services: ["electric"],
    balance: "108.880000",
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    balance_not_yet_billable: false,
    balance_cached: null,
    currency: "USD",
    status: "active",
    status_name: "Active",
    status_behavior_class: "billable",
    kind: "regular",
    account_type: "residential",
    account_subtype: null,
    autopay: false,
    opened_at: "2026-01-04",
    closed_at: null,
    last_bill_at: "2026-08-08",
    aging: null,
    ...over,
  } as AccountRow;
}

/** Every `/accounts` request this render made, as `path {query}`. */
let calls: string[] = [];

beforeEach(() => {
  calls = [];
});

function client(answer: { rows?: AccountRow[]; reject?: boolean }): ApiClient {
  return {
    get: vi
      .fn()
      .mockImplementation((path: string, options?: { query?: Record<string, unknown> }) => {
        if (path === "/accounts") {
          calls.push(`${path} ${JSON.stringify(options?.query ?? {})}`);
          if (answer.reject === true) {
            return Promise.reject(new Error("network"));
          }
          const rows = answer.rows ?? [];
          return Promise.resolve({
            data: {
              results: rows,
              count: rows.length,
              page: 1,
              per: 50,
              rollup: {
                accounts: rows.length,
                outstanding: null,
                currency: "USD",
                outstanding_basis: "posting",
                outstanding_unavailable: [],
                past_due_60_plus: null,
              },
            },
          });
        }
        return Promise.resolve({ data: { results: [], count: 0 } });
      }),
  } as unknown as ApiClient;
}

function mount(answer: { rows?: AccountRow[]; reject?: boolean }) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazos/payments/record"]}>
          <RecordPaymentForm
            client={client(answer)}
            methods={METHODS}
            today="2026-09-03"
            dateFormat="MM/DD/YYYY"
            currency="USD"
            onCancel={() => undefined}
            onRecorded={() => undefined}
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ⚠ **ONE CONTROL SINCE 2026-09-23 (`DEF-PAY-6319`).** There was a
// `#account_query` box and a `#account_id` select beside it until the Product
// Owner said, of the same picker on the refund form, *"why to button - why
// cannot we have dropdown search drectly for this - user has to do two
// clicks"*. The FIVE STATES below are unchanged and are the reason that
// combobox had to be written rather than reached for — see
// `components/RemoteSearchSelectField.tsx`, and `accountCombobox.dom.test.tsx`
// for the same five asserted on the screen the PO was looking at.
function type(value: string): void {
  const box = document.querySelector<HTMLInputElement>("#account_id");
  expect(box).not.toBeNull();
  fireEvent.change(box as HTMLInputElement, { target: { value } });
}

/** Which of the six the one panel says it is in. */
const state = (): string | null =>
  document.querySelector<HTMLElement>("[data-panel-state]")?.getAttribute("data-panel-state") ??
  null;

/** The matches, as the clerk sees them — options, never a `<select>`. */
const picker = (): HTMLElement[] => [...document.querySelectorAll<HTMLElement>('[role="option"]')];

describe("DEF-3506 — the Record payment modal can find an account", () => {
  it("typing an account number offers that account, and it can be chosen", async () => {
    mount({ rows: [account()] });
    type("AC-2026-00050");
    await waitFor(() => expect(state()).toBe("matches"));
    const labels = picker().map((option) => option.textContent);
    expect(labels.join("|")).toContain("AC-2026-00050 — Miller, Sarah");

    // B14 rule 31: the LABEL is the account number, never the database id —
    // the id is only ever the option's value, which is what posts.
    expect(labels.join("|")).not.toContain("acc-0050");

    // …and choosing it sticks. A picker whose options render but whose value
    // will not take is the same dead end wearing a different mask.
    fireEvent.click(picker()[0]);
    const box = document.querySelector<HTMLInputElement>("#account_id") as HTMLInputElement;
    expect(box.value).toBe("AC-2026-00050 — Miller, Sarah");
  });

  it("a number pasted with a trailing space still finds the account", async () => {
    // The half of DEF-3506 a machine can prove. Copying `AC-2026-00050 ` out of
    // a spreadsheet cell or an email is the ordinary way a clerk gets a number
    // into this box, and the untrimmed term matched nothing, silently.
    mount({ rows: [account()] });
    type("  AC-2026-00050 ");
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(calls).toContain('/accounts {"q":"AC-2026-00050","per":50}');
  });

  it("a search that matched nothing says so, in place of an empty picker", async () => {
    mount({ rows: [] });
    type("AC-2026-99999");
    expect(await screen.findByText(t("payments.form.accountNoMatch"))).toBeInTheDocument();
    // ⛔ NOT a list with one placeholder in it. The search RAN and the answer
    // was "no account of yours looks like that" — a fact about the term, which
    // is the one a clerk can act on.
    expect(state()).toBe("no-match");
    expect(picker()).toHaveLength(0);
  });

  it("a search that could not run says so, and is not read as no-match", async () => {
    mount({ reject: true });
    type("AC-2026-00050");
    expect(await screen.findByText(t("payments.form.accountSearchFailed"))).toBeInTheDocument();
    expect(screen.queryByText(t("payments.form.accountNoMatch"))).toBeNull();
    expect(state()).toBe("failed");
    expect(picker()).toHaveLength(0);
  });

  it("the picker is not drawn until something matches", () => {
    mount({ rows: [account()] });
    // Nothing typed: no request, no options, and no dropdown reading "Choose an
    // account" over an empty list. The panel says nothing at all.
    expect(picker()).toHaveLength(0);
    expect(state()).toBe("silent");
    expect(calls).toHaveLength(0);

    // One character is below IS-3's minimum, and the screen says which state
    // it is in rather than looking like a search that found nothing.
    type("A");
    expect(calls).toHaveLength(0);
    expect(screen.getByText(t("payments.form.accountTooShort"))).toBeInTheDocument();
    expect(state()).toBe("too-short");
    expect(picker()).toHaveLength(0);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-3506 + DEF-3507 (the Product Owner's walk of all four Payments tabs, 2026-09-03) · CR-059 §8 CS-4/CS-35 · US-PAY-001 · 08-payments/02-business-rules.md · B14 rules 31 and 32 · features/customers/accountFinder.tsx (the ratified pattern this follows)
// generated: 2026-09-03 by the payments PO-walk lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — all five cases failed against the pre-fix build and the verbatim output is quoted in the header above · tsc --noEmit✔ · eslint --max-warnings 0 (features/payments)✔ · vitest src/features/payments src/styles = 285 passed / 19 files✔ (280 / 18 before this file) · G31 PASS (0 undeclared classes; the stylesheets are AT rule 21's ceiling of 470, so this lane added none) · G38 PASS (83 absences, 66 citing nothing, baseline 66 — the two ArrivesWith panels moved inside a <details> and kept their call sites) · G15 PASS (10676 keys, 0 missing, 0 extra) · G27 PASS · G43 PASS · G44 PASS · G33 red on three messages, all pre-existing at the tip and none of them payments' — proved by diffing en.json against origin: this lane changed six payments keys and added nine, and all fifteen are within six words
// exceptions: the SERVER half is not re-proved here — `selectors.account_list` already matches `account_no__icontains` and has its own tests; what was broken was entirely on the screen
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
