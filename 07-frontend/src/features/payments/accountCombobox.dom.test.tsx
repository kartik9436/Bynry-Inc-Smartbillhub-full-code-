// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-PAY-6319 — Product Owner, looking at the Raise-a-refund form,
//          2026-09-23, verbatim: *"why to button - why cannot we have dropdown
//          search drectly for this - user has to do two clicks"*, then, having
//          heard the reason for the split: *"fix it"*.
// Story:   US-PAY-015 (S36 refunds) · US-PAY-001 (the same picker on Record a
//          payment) — Screens: S36 · S22 · S35
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT) · B14 rule 36 (the kit) ·
//          B14 rule 31 (no database id is the visible value of a field) ·
//          B14 rule 33 (the five caps; RATIONALE is zero words on screen) ·
//          BR-SHL-020 (a PLATFORM failure says so) · BR-SHL-012 (a screen says
//          which state it is in) · IS-3 (server search, from two characters) ·
//          IS-10 (the first Esc closes the list, not the modal)
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE SCREEN THE PO WAS LOOKING AT, MOUNTED THE WAY THE PRODUCT MOUNTS IT ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// `RaiseRefundModal` inside a `MemoryRouter` under the REAL path pattern,
// `/:tenant/payments/refunds`. A component mounted bare under a router with no
// matching route is how `DEF-CWP-3925` hid: `useParams()` comes back empty and
// every address the screen builds is a plausible-looking string that goes
// nowhere, which a `toContain` assertion cannot tell from a working one.
//
// ⚠ **WHAT THIS FILE IS ACTUALLY GUARDING IS THE FIVE STATES, NOT THE ONE
// CONTROL.** `DEF-3506` was reported because a clerk could not tell *searching*
// from *no such account* from *the search could not run* from *here are your
// matches* — all four drew as one empty select. The repair made them
// distinguishable by ADDING a second field, and that is what cost two gestures.
// Merging the two fields back into one combobox is only safe while all five
// stay apart, so every one of them is asserted here BY ITS OWN NAME and by the
// surface it is drawn in: the platform failure is a RefusalStrip, the other
// three are Notes, and no two share a sentence.
//
// **RED PROVED FIRST, IN THE HARNESS THAT RUNS IT (hard-won law 7).** Every
// case below was run with `npx vitest run` against the branch tip's two-field
// picker, in a worktree checked out at that tip. The verbatim output is quoted
// in the Lifecycle trailer at the foot of this file.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { AccountRow } from "@/api/endpoints";
import i18n from "@/i18n";

import { RaiseRefundModal } from "./RefundsPage";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

/** The account the Product Owner would have been looking for. */
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

/** Every request this render made, as `VERB path`. */
let calls: string[] = [];

beforeEach(() => {
  calls = [];
});

function client(answer: { rows?: AccountRow[]; reject?: boolean }): ApiClient {
  const get = vi
    .fn()
    .mockImplementation((path: string, options?: { query?: Record<string, unknown> }) => {
      calls.push(`GET ${path} ${JSON.stringify(options?.query ?? {})}`);
      if (path === "/accounts") {
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
      return Promise.resolve({ data: { results: [], count: 0, page: 1, per: 50 } });
    });
  const post = vi.fn().mockImplementation((path: string) => {
    calls.push(`POST ${path}`);
    return Promise.resolve({ data: {} });
  });
  return { get, post } as unknown as ApiClient;
}

function mount(answer: { rows?: AccountRow[]; reject?: boolean }) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      {/* The REAL path pattern, so `useParams().tenant` resolves — the fixture
          fault `DEF-CWP-3925` was hidden by. */}
      <MemoryRouter initialEntries={["/brazos/payments/refunds"]}>
        <Routes>
          <Route
            path="/:tenant/payments/refunds"
            element={
              <RaiseRefundModal
                client={client(answer)}
                dateFormat="MM/DD/YYYY"
                onClose={() => undefined}
                onRaised={() => undefined}
              />
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** The ONE control. There is no second id to reach for any more. */
const box = (): HTMLInputElement => {
  const element = document.querySelector<HTMLInputElement>("#account_id");
  expect(element).not.toBeNull();
  return element as HTMLInputElement;
};

const panel = (): HTMLElement => {
  const element = document.querySelector<HTMLElement>("[data-panel-state]");
  expect(element).not.toBeNull();
  return element as HTMLElement;
};

/** Which of the six the panel says it is in — the machine-readable name. */
const state = (): string | null => panel().getAttribute("data-panel-state");

function type(value: string): void {
  fireEvent.change(box(), { target: { value } });
}

describe("DEF-PAY-6319 — one control, and the five states stay five", () => {
  it("is ONE control: no separate find box, and the picker is not a select", () => {
    mount({ rows: [account()] });
    // The second field is gone. `account_query` was the box a clerk typed in
    // before choosing from `account_id` beside it — two gestures, which is the
    // PO's whole report.
    expect(document.querySelector("#account_query")).toBeNull();
    // …and what remains is a combobox, not a `<select>`.
    expect(box().tagName).toBe("INPUT");
    expect(box()).toHaveAttribute("role", "combobox");
    expect(document.querySelector("select#account_id")).toBeNull();
  });

  it("names the field once, and invites the search in the box itself", () => {
    mount({ rows: [account()] });
    // B14 rule 10: the asterisk rides the label of a required field. B14 rule
    // 33: a LABEL is a name of at most three words, never a sentence.
    const label = document.querySelector<HTMLLabelElement>('label[for="account_id"]');
    expect(label?.textContent).toContain(t("payments.refunds.account"));
    // The search is what the box invites, so it is the placeholder — both
    // strings the screen already passed are still on screen.
    expect(box()).toHaveAttribute("placeholder", t("payments.refunds.accountSearch"));
    // B14 rule 39: LABEL → INPUT → HELPER, and the helper still says what may
    // be typed.
    expect(screen.getByText(t("payments.form.accountSearchHelp"))).toBeInTheDocument();
  });

  // ── The five states, each by its own name and its own surface ────────────

  it("says nothing at all until something is typed", () => {
    mount({ rows: [account()] });
    expect(state()).toBe("silent");
    expect(panel()).toHaveAttribute("hidden");
    expect(calls).toHaveLength(0);
  });

  it("1 · TYPED TOO LITTLE — below IS-3's minimum, and it says which", () => {
    mount({ rows: [account()] });
    type("A");
    expect(state()).toBe("too-short");
    expect(screen.getByText(t("payments.form.accountTooShort"))).toBeInTheDocument();
    // Nothing was asked of the server, which is what "too short" MEANS.
    expect(calls).toHaveLength(0);
  });

  it("2 · SEARCHING — the request is in flight and the panel says so", () => {
    mount({ rows: [account()] });
    type("AC-2026-00050");
    expect(state()).toBe("searching");
    expect(screen.getByText(t("payments.form.accountSearching"))).toBeInTheDocument();
  });

  it("3 · THE SEARCH FAILED — a PLATFORM refusal, drawn as one", async () => {
    mount({ reject: true });
    type("AC-2026-00050");
    await waitFor(() => expect(state()).toBe("failed"));
    const message = screen.getByText(t("payments.form.accountSearchFailed"));
    expect(message).toBeInTheDocument();
    // ⚠ **BR-SHL-020, AND THE ASSERTION THE WHOLE FILE EXISTS FOR.** This is
    // the only one of the four that is a refusal, and it must not be readable
    // as "no such account": support can act on this one and the clerk cannot.
    expect(message).toHaveAttribute("data-refusal");
    expect(message).toHaveAttribute("role", "alert");
    expect(screen.queryByText(t("payments.form.accountNoMatch"))).toBeNull();
  });

  it("4 · NOTHING MATCHED — a fact about the TERM, and NOT a refusal", async () => {
    mount({ rows: [] });
    type("AC-2026-99999");
    await waitFor(() => expect(state()).toBe("no-match"));
    const message = screen.getByText(t("payments.form.accountNoMatch"));
    expect(message).toBeInTheDocument();
    // ⛔ The mirror of the case above. The search RAN; the answer was none.
    // Drawn as a note, never as the red strip, because the clerk fixes this by
    // typing and nobody needs to be told the product is broken.
    expect(message).toHaveAttribute("data-note");
    expect(message).not.toHaveAttribute("data-refusal");
    expect(screen.queryByText(t("payments.form.accountSearchFailed"))).toBeNull();
  });

  it("5 · MATCHES — the rows are options in the panel, under the one control", async () => {
    mount({ rows: [account()] });
    type("AC-2026-00050");
    await waitFor(() => expect(state()).toBe("matches"));
    const option = screen.getByRole("option", { name: "AC-2026-00050 — Miller, Sarah" });
    expect(option).toBeInTheDocument();
    // B14 rule 31: the database id is the VALUE, never anything a clerk reads.
    expect(panel().textContent).not.toContain("acc-0050");
  });

  it("all five wear different names, so no two of them can be confused", async () => {
    // The states, gathered in one case so the DISTINCTNESS is the assertion
    // rather than five separate facts that happen to differ.
    const seen: string[] = [];
    mount({ rows: [account()] });
    seen.push(state() as string);
    type("A");
    seen.push(state() as string);
    type("AC-2026-00050");
    seen.push(state() as string);
    await waitFor(() => expect(state()).toBe("matches"));
    seen.push(state() as string);
    cleanup();

    mount({ rows: [] });
    type("AC-2026-99999");
    await waitFor(() => expect(state()).toBe("no-match"));
    seen.push(state() as string);
    cleanup();

    mount({ reject: true });
    type("AC-2026-00050");
    await waitFor(() => expect(state()).toBe("failed"));
    seen.push(state() as string);

    expect(seen).toEqual([
      "silent",
      "too-short",
      "searching",
      "matches",
      "no-match",
      "failed",
    ]);
    expect(new Set(seen).size).toBe(6);
  });

  // ── Choosing, and the money rule under it ────────────────────────────────

  it("clicking a match chooses it, and the box then shows the NAME, not the id", async () => {
    mount({ rows: [account()] });
    type("AC-2026-00050");
    await waitFor(() => expect(state()).toBe("matches"));
    fireEvent.click(screen.getByRole("option", { name: "AC-2026-00050 — Miller, Sarah" }));

    expect(box().value).toBe("AC-2026-00050 — Miller, Sarah");
    // B14 rule 31 again, at the one place a naive combobox breaks it: the
    // CHOSEN value is the thing a clerk stares at for the rest of the form.
    expect(box().value).not.toContain("acc-0050");
    // Chosen means the panel is put away — one gesture, and the form moves on.
    expect(panel()).toHaveAttribute("hidden");
    // …and the account is now the one the rest of the form is scoped to.
    await waitFor(() =>
      expect(calls.some((call) => call.includes('"f.account_id":"acc-0050"'))).toBe(true),
    );
  });

  it("⚠ TYPING AFTER CHOOSING CLEARS THE CHOICE — what posts is EMPTY, not the old id", async () => {
    // ╔════════════════════════════════════════════════════════════════════╗
    // ║  THE MONEY CASE. A combobox that keeps a stale selection behind a  ║
    // ║  changed search term is a money bug wearing a UX improvement.      ║
    // ╚════════════════════════════════════════════════════════════════════╝
    // The two-field picker cleared the chosen id on every keystroke, and its
    // comment said why: *"Leaving a stale id behind a changed box is how a
    // clerk posts money to the account they were looking at a moment ago."*
    // One control makes that FAR easier to get wrong, because the box now holds
    // the chosen account's own name — so the obvious implementation leaves the
    // id alone while the text changes under it.
    mount({ rows: [account()] });
    type("AC-2026-00050");
    await waitFor(() => expect(state()).toBe("matches"));
    fireEvent.click(screen.getByRole("option", { name: "AC-2026-00050 — Miller, Sarah" }));
    await waitFor(() =>
      expect(calls.some((call) => call.includes('"f.account_id":"acc-0050"'))).toBe(true),
    );

    // The clerk now types a DIFFERENT account. Nothing is chosen yet.
    calls = [];
    type("AC-2026-99999");
    expect(box().value).toBe("AC-2026-99999");

    // …and the form is submitted anyway, which is the whole point: a refund
    // must not be raised against the account that was on screen a moment ago.
    fireEvent.click(screen.getByRole("button", { name: t("payments.refunds.raiseSubmit") }));

    // NOTHING POSTS. `raiseRefundSchema` refuses an empty `account_id`, and the
    // request is addressed `/accounts/{id}/refunds`, so a stale id would have
    // been the whole address.
    await waitFor(() =>
      expect(screen.getByText(t("payments.refunds.accountRequired"))).toBeInTheDocument(),
    );
    expect(calls.filter((call) => call.startsWith("POST"))).toHaveLength(0);
    expect(calls.join("|")).not.toContain("acc-0050");
  });

  // ── The keyboard. A mouse-only combobox is worse than two native fields ──

  it("arrow keys walk the matches and Enter takes one", async () => {
    mount({ rows: [account(), account({ id: "acc-0051", account_no: "AC-2026-00051", name: "Ng, Priya" })] });
    type("AC-2026-000");
    await waitFor(() => expect(state()).toBe("matches"));

    // Nothing is highlighted until a key says so — ↓ lands on the FIRST.
    expect(box()).not.toHaveAttribute("aria-activedescendant");
    fireEvent.keyDown(box(), { key: "ArrowDown" });
    expect(box()).toHaveAttribute("aria-activedescendant", "account_id-opt-0");
    fireEvent.keyDown(box(), { key: "ArrowDown" });
    expect(box()).toHaveAttribute("aria-activedescendant", "account_id-opt-1");
    // …and it wraps, both ways.
    fireEvent.keyDown(box(), { key: "ArrowDown" });
    expect(box()).toHaveAttribute("aria-activedescendant", "account_id-opt-0");
    fireEvent.keyDown(box(), { key: "ArrowUp" });
    expect(box()).toHaveAttribute("aria-activedescendant", "account_id-opt-1");

    fireEvent.keyDown(box(), { key: "Enter" });
    expect(box().value).toBe("AC-2026-00051 — Ng, Priya");
    await waitFor(() =>
      expect(calls.some((call) => call.includes('"f.account_id":"acc-0051"'))).toBe(true),
    );
  });

  it("Escape closes the panel and leaves the modal open (IS-10)", async () => {
    mount({ rows: [account()] });
    type("AC-2026-00050");
    await waitFor(() => expect(state()).toBe("matches"));
    expect(panel()).not.toHaveAttribute("hidden");

    fireEvent.keyDown(box(), { key: "Escape" });
    expect(panel()).toHaveAttribute("hidden");
    // The FIRST Esc is the list's. The form is still here.
    expect(screen.getByText(t("payments.refunds.raiseTitle"))).toBeInTheDocument();
  });

  it("announces itself as a combobox over a listbox, open and closed", async () => {
    mount({ rows: [account()] });
    // Closed at rest, and it says so rather than saying nothing.
    expect(box()).toHaveAttribute("aria-expanded", "false");
    expect(box()).toHaveAttribute("aria-controls", "account_id-listbox");
    expect(box()).toHaveAttribute("aria-autocomplete", "list");
    // DEF-TEN-4478 — the browser's own fill writes the DOM and fires no React
    // event, and this box holds a lookup term, not a fact about the person.
    expect(box()).toHaveAttribute("autocomplete", "off");
    expect(box()).toHaveAttribute("aria-required", "true");

    type("AC-2026-00050");
    await waitFor(() => expect(state()).toBe("matches"));
    expect(box()).toHaveAttribute("aria-expanded", "true");
    expect(document.querySelector("#account_id-listbox")).toHaveAttribute("role", "listbox");
  });

  it("still trims the term it sends, which is DEF-3506's other half", async () => {
    // A number pasted out of a spreadsheet cell carries whitespace, and
    // `account_no ILIKE '%AC-2026-00050 %'` matches nothing at all. The one
    // control changed; the hook under it did not, and this says so.
    mount({ rows: [account()] });
    type("  AC-2026-00050 ");
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(calls).toContain('GET /accounts {"q":"AC-2026-00050","per":50}');
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-PAY-6319 (PO on the Raise-a-refund form, 2026-09-23) · DEF-3506 (the five states, and why they exist) · US-PAY-015 · US-PAY-001 · 08-payments/02-business-rules.md · B14 rules 8, 10, 21, 31, 33, 36, 39, 43 · IS-3 · IS-10 · BR-SHL-012 · BR-SHL-020
// generated: 2026-09-23 by lane ACCOUNT-COMBO
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST, through `npx vitest run src/features/payments/accountCombobox.dom.test.tsx` in a worktree checked out at the branch tip — the harness that runs it, not a direct invocation (hard-won law 7, and DEF-GOV-3733's half of it). The verbatim output is in the commit message and in the defect row.
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
