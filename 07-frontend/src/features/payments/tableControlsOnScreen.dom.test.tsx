// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `CR-138-BRC07` `P4.19` — *"Five controls asserted on 7·1 and 7·3a
//           — search, filter, sort, columns, paging. **Five assertions the
//           screens fail today.**"* The screens are `P4.7` and `P4.9`, both
//           landed; this is the check that keeps them.
// Rules:    B14 rule 12 (the toolbar: search · filters · columns · export) ·
//           rule 13 (⇅ on a sortable header) · rule 14 (ONE table type) ·
//           rule 16 (a pagination footer on every list) · rule 19 (a list
//           declares its OWN search prompt) · BR-SHL-010 (an undeclared
//           capability never renders) · BR-PAY-029 (AR high → low)
// Screens:  7·1 Debtors (S34 · PAY-02) · 7·3a Ladder (PAY-06)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE BLUEPRINT'S OWN WORDS FOR 7·3a's TABLE-CONTROLS ROW: "All four absent
// today." AND FOR 7·1's: FIVE CONTROLS, NONE OF WHICH WORKED.
// ══════════════════════════════════════════════════════════════════════════
// That is what `P4.7` and `P4.9` closed by putting both lists on the kit's
// `DataTable`. This file is the assertion that they stay closed.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT WAS ALREADY COVERED — MEASURED, NOT ASSUMED
// ══════════════════════════════════════════════════════════════════════════
// `debtorScreens.dom.test.tsx` has a describe called *"7·1 · the table's five
// controls and its one door"*. Read case by case, it asserts **four facts and a
// door, all on the CONFIG OBJECT**:
//
//     searchPlaceholder · defaultSort · the default column set · which headers
//     carry `sortable: true` · `debtorDetailPath()`
//
// **Two of the five controls are not among them: FILTERS and PAGING.** And all
// four that are covered are properties of a plain object — `debtorsTableConfig`
// could return a perfect config to a screen that never renders a table, and
// every one of those cases would stay green. That is law 7's *looking at the
// wrong thing*: the task says *asserted on 7·1 and 7·3a*, and a config is not
// a screen.
//
// **And 7·3a has NO control coverage at all.** `ladderBoardConfig` is asserted
// nowhere in the suite; the only ladder cases in the repo are about the pill
// and the three-valued `runs` cell.
//
// ══════════════════════════════════════════════════════════════════════════
// SO THIS FILE RENDERS BOTH SCREENS AND LOOKS AT THE DOM
// ══════════════════════════════════════════════════════════════════════════
// ⚠⚠ **AND IT PASSES ROWS, WHICH IS THE ONE THING THAT MAKES IT A CHECK AT
// ALL.** `DataTable` draws its EMPTY STATE *instead of* the toolbar, the header
// row and the pager — so a fixture with no rows reports every one of these five
// controls absent, and a fixture whose rows fail to reach the table reports the
// same. `cr138_p4_debtor_screens_walkthrough.mjs` says so in its own header:
// *"'control missing' on an empty tenant is not a finding."* Every case below
// therefore asserts the ROW COUNT first, in the same breath as the control.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { LadderBoardResponse, LadderBoardRow } from "@/api/bankRecEndpoints";
import type { OutstandingRow, OutstandingsResponse } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { CollectionsPage, collectionsQueryKey } from "./CollectionsPage";
import { OutstandingsTab, outstandingsQueryKey } from "./OutstandingsTab";
import { PAYMENTS_PERMISSION } from "./paymentsShared";

afterEach(cleanup);

const TENANT = "brazosbend";
const AS_OF = "2026-09-23";

/** Enough rows that a pager has something to page, and enough of them for
 *  `DataTable` to draw its header row at all. */
const DEBTORS: OutstandingRow[] = Array.from({ length: 3 }, (_, index) => ({
  account_id: `01a046dd-d809-7e20-81a3-87b1eddc1b6${index}`,
  account_no: `AC-2026-0000${index + 1}`,
  customer_name: ["Ana Alvarez", "Ben Okafor", "Cara Lindqvist"][index],
  balance: ["1284.6000", "948.2000", "612.6000"][index],
  days_late: 91 - index * 10,
  bucket: "90+",
  open_bills: 2,
  last_payment_on: "2026-08-02",
  notice_summary: "1st sent",
  collection_tier: "friendly",
  next_step_due: null,
  plan_status: null,
  autopay: false,
  bad_address: false,
  gross_balance: null,
  credit_applied: null,
})) as unknown as OutstandingRow[];

const OUTSTANDINGS: OutstandingsResponse = {
  as_of: AS_OF,
  rows: DEBTORS,
  totals: { accounts: 137, owed: "2845.4000", dso_days: null },
  ageing: [
    { bucket: "current", amount: "0.0000", accounts: 0, share: "0.0" },
    { bucket: "1-30", amount: "0.0000", accounts: 0, share: "0.0" },
    { bucket: "31-60", amount: "0.0000", accounts: 0, share: "0.0" },
    { bucket: "61-90", amount: "0.0000", accounts: 0, share: "0.0" },
    { bucket: "90+", amount: "2845.4000", accounts: 3, share: "100.0" },
  ],
  problems: [],
} as unknown as OutstandingsResponse;

const LADDER_ROWS: LadderBoardRow[] = DEBTORS.map((debtor, index) => ({
  account_id: debtor.account_id,
  account_no: debtor.account_no,
  balance: debtor.balance,
  currency: "USD",
  oldest_due_on: "2026-07-14",
  current_tier: "friendly",
  tier_sent_on: "2026-09-08",
  last_notice_on: "2026-09-08",
  plan_paused: index === 2,
  plan_pause_reason: index === 2 ? "active_and_current" : "",
  plan_id: null,
  medical_hold: false,
  runs: index === 2 ? false : true,
  next_rung: "first_10_day",
  next_step_on: "2026-09-24",
  skip_reason: index === 2 ? "payment_plan_pause" : null,
  days_late: 62,
  detail_code: "",
})) as unknown as LadderBoardRow[];

const LADDER: LadderBoardResponse = {
  as_of: AS_OF,
  rows: LADDER_ROWS,
  rungs: ["friendly", "first_10_day", "second_5_day", "final_48_hour"],
  next_step_available: true,
  intervals: { reminder_days: 3, tier_days: [10, 5], final_hours: 48 },
  tiles: { accounts: 3, at_tier: { friendly: 3 }, not_started: 0, paused: 1, due_today: 2 },
  problems: [],
} as unknown as LadderBoardResponse;

function stub(match: string, body: unknown): ApiClient {
  const answer = async (path: string) => {
    if (path.startsWith(match)) {
      return { status: 200, data: body, headers: {} };
    }
    throw new Error(`the fixture was asked for ${path}, which it does not serve`);
  };
  return { get: answer, post: answer, put: answer, patch: answer, delete: answer } as never;
}

function provider(children: React.ReactNode, at: string, pattern: string, seed: (c: QueryClient) => void) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  seed(client);
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        {/* ⚠ **THE REAL PATH PATTERNS** `App.tsx` mounts. `DEF-CWP-3925`: a
            payments screen outside `/:tenant/…` builds every address as
            `//payments/…`, which `toContain` reads as a perfectly good string. */}
        <MemoryRouter initialEntries={[at]}>
          <Routes>
            <Route path={pattern} element={children} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** 7·1 Debtors, on screen, with rows. */
function open71() {
  return provider(
    <OutstandingsTab
      client={stub("/outstandings", OUTSTANDINGS)}
      asOf={AS_OF}
      onAsOfChange={() => {}}
      currency="USD"
      writeBlockedReason={null}
      timeZone="America/Chicago"
      dateFormat="MM/DD/YYYY"
    />,
    `/${TENANT}/payments/outstandings`,
    "/:tenant/payments/:tab",
    (client) => client.setQueryData(outstandingsQueryKey(AS_OF, "", false), OUTSTANDINGS),
  );
}

/** 7·3a Ladder, on screen, with rows. */
function open73a() {
  return provider(
    <CollectionsPage client={stub("/collections/ladder", LADDER)} today={AS_OF} />,
    `/${TENANT}/payments/collections`,
    "/:tenant/payments/collections",
    (client) => {
      client.setQueryData(collectionsQueryKey(AS_OF), LADDER);
      // `useAccessCell` reads `/me/permissions`; unseeded it is null, which
      // BR-SHL-025 treats as "offer the control". Seeded so the page is in the
      // state a real clerk is in rather than in an ambiguous one.
      // ⚠ **THE CODE IS `payments_record`, NOT `payments`, AND THE FIRST
      // DRAFT GUESSED.** `CollectionsPage` gates on
      // `useAccessCell(PAYMENTS_PERMISSION)` and `accessCell` returns
      // `CELL_NONE` for a code it cannot find — so a wrong code renders *"You
      // do not have access to collections"* and every control case below
      // reports the control missing from a screen that has it. **Seed it from
      // the constant**, never from a spelling of it.
      client.setQueryData(queryKeys.myPermissions, {
        role: "billing_clerk",
        role_name: "Billing Clerk",
        permissions: [{ code: PAYMENTS_PERMISSION, access: "write" }],
      });
    },
  );
}

/** The five controls, asked of whatever list is currently on screen.
 *
 *  ⚠ **EVERY ONE IS READ BY ITS ACCESSIBLE NAME OR ITS CATALOGUE SENTENCE**,
 *  never by a class name: a control a screen reader cannot find is a control a
 *  clerk using one does not have, and a CSS class is not a capability. */
function theFiveControls(table: HTMLElement, searchPromptKey: string) {
  return {
    rows: within(table).getAllByRole("row").length,
    search: within(table).queryByPlaceholderText(i18n.t(searchPromptKey)),
    filter: within(table).queryByText(i18n.t("table.filters.open")),
    columns: within(table).queryByLabelText(i18n.t("table.columns.open")),
    // ⚠ **NOT A `⇅` GLYPH — `DataTable` DRAWS A `button.table-sort`.** The
    // first draft of this file looked for the arrow the BLUEPRINT prints in its
    // header row, found none, and reported the control missing on a screen that
    // has it. `⇅` is the drawing's notation for *this header sorts*; the
    // product's is a pressable header, with `▲`/`▼` on the one currently
    // sorted. Law 7's *looking at the wrong thing*, caught by the case failing.
    sortable: table.querySelectorAll("button.table-sort"),
    pager: within(table).queryByLabelText(i18n.t("table.pager.next")),
  };
}

function theTable(): HTMLElement {
  const frames = document.querySelectorAll(".data-table-frame");
  expect(frames.length).toBeGreaterThan(0);
  return frames[0] as HTMLElement;
}

describe("P4.19 · 7·1 Debtors — the five controls are ON THE SCREEN", () => {
  it("draws the toolbar's search box with THIS list's own prompt (B14 rule 19)", () => {
    open71();
    const table = theTable();
    // ⚠ **THE ROW COUNT IS PART OF THE ASSERTION.** `DataTable` renders its
    // empty state INSTEAD of the toolbar, so "no search box" over an empty
    // fixture is not a finding about the screen.
    expect(within(table).getAllByRole("row").length).toBeGreaterThan(1);
    expect(
      within(table).getByPlaceholderText(i18n.t("payments.outstandings.searchPlaceholder")),
    ).toBeInTheDocument();
  });

  it("draws `+ Filter` — the control `debtorScreens.dom.test.tsx` never asserts", () => {
    open71();
    expect(within(theTable()).getByText(i18n.t("table.filters.open"))).toBeInTheDocument();
  });

  it("draws the ▦ column chooser (B14 rule 14)", () => {
    open71();
    expect(within(theTable()).getByLabelText(i18n.t("table.columns.open"))).toBeInTheDocument();
  });

  it("makes the marked headers PRESSABLE to sort (B14 rule 13)", () => {
    open71();
    const table = theTable();
    // The drawing marks eight headers `⇅`; the product draws each as a
    // `button.table-sort` inside the `<th>`, which is the accessible form of
    // the same affordance — a header a keyboard can reach and press.
    expect(table.querySelectorAll("button.table-sort").length).toBeGreaterThan(4);
    // …and the one the list is sorted BY says so to a screen reader, which is
    // the half a glyph alone cannot carry.
    expect(table.querySelector("th[aria-sort]")).not.toBeNull();
  });

  it("draws the pagination footer — the OTHER control nothing asserted (rule 16)", () => {
    open71();
    const table = theTable();
    expect(within(table).getByLabelText(i18n.t("table.pager.next"))).toBeInTheDocument();
    expect(within(table).getByLabelText(i18n.t("table.pager.prev"))).toBeInTheDocument();
    // `NFR-5`: the footer states a RANGE and a COUNT, never a cap.
    expect(table.querySelector(".table-pager-range")?.textContent).toBe(
      i18n.t("table.pager.range", { from: 1, to: 3, total: 3 }),
    );
    // ⚠ **AND THE TOTAL IS THE PAGE'S, NOT THE TENANT'S — `DEF-PAY-6271`.**
    // The served body says 137 accounts owe money; the footer says *1–3 of 3*,
    // because `clientPage` pages what the server sent WHOLE and the screen
    // never asks `GET /outstandings` for a page. The control is on screen and
    // the paging is still in the browser, which is exactly what that defect
    // records. Asserted rather than glossed, so the day the screen starts
    // asking, this line moves with it.
    expect(table.textContent).not.toContain("137");
  });

  it("all five at once, so a regression that removes one cannot hide behind four", () => {
    open71();
    const found = theFiveControls(theTable(), "payments.outstandings.searchPlaceholder");
    expect(found.rows).toBeGreaterThan(1);
    expect(found.search).not.toBeNull();
    expect(found.filter).not.toBeNull();
    expect(found.columns).not.toBeNull();
    expect(found.sortable.length).toBeGreaterThan(0);
    expect(found.pager).not.toBeNull();
  });
});

describe("P4.19 · 7·3a Ladder — the four the blueprint calls ABSENT", () => {
  it("has rows at all, which everything below depends on", () => {
    open73a();
    expect(within(theTable()).getAllByRole("row").length).toBeGreaterThan(1);
  });

  it("draws its OWN search prompt, not the product default (B14 rule 19)", () => {
    open73a();
    expect(
      within(theTable()).getByPlaceholderText(i18n.t("payments.collections.searchPlaceholder")),
    ).toBeInTheDocument();
  });

  it("draws `+ Filter` — the drawing's `Due now ×` chip, as a declared filter", () => {
    open73a();
    // ⚠ Declared in `TableConfig.filters` rather than hand-rolled beside the
    // table: `DEF-1700` deleted the second toolbar row four screens had grown,
    // and `G43` clause (c) still refuses a dimension control in `downloadSlot`.
    expect(within(theTable()).getByText(i18n.t("table.filters.open"))).toBeInTheDocument();
  });

  it("draws the ▦ chooser and makes the marked headers PRESSABLE", () => {
    open73a();
    const table = theTable();
    expect(within(table).getByLabelText(i18n.t("table.columns.open"))).toBeInTheDocument();
    // Same correction as 7·1's: `⇅` is the blueprint's notation, the product
    // draws `button.table-sort` and `▼` on the column the list is sorted by.
    expect(table.querySelectorAll("button.table-sort").length).toBeGreaterThan(2);
    expect(table.querySelector("th[aria-sort]")).not.toBeNull();
  });

  it("draws a pagination footer", () => {
    open73a();
    expect(within(theTable()).getByLabelText(i18n.t("table.pager.next"))).toBeInTheDocument();
  });

  it("all five at once", () => {
    open73a();
    const found = theFiveControls(theTable(), "payments.collections.searchPlaceholder");
    expect(found.rows).toBeGreaterThan(1);
    expect(found.search).not.toBeNull();
    expect(found.filter).not.toBeNull();
    expect(found.columns).not.toBeNull();
    expect(found.sortable.length).toBeGreaterThan(0);
    expect(found.pager).not.toBeNull();
  });
});

describe("P4.19 · what would make every case above pass wrongly", () => {
  it("an EMPTY list draws none of them — so a fixture that loses its rows is RED, not green", () => {
    // ⚠ **THIS IS THE CONTROL CASE AND IT IS THE MOST IMPORTANT ONE HERE.**
    // `DataTable` swaps its empty state in for the whole frame. Without this,
    // every assertion above is a statement about a fixture that happens to
    // work, and the day one stops delivering rows the file reports five
    // missing controls and a reader goes looking at the screen.
    provider(
      <OutstandingsTab
        client={stub("/outstandings", { ...OUTSTANDINGS, rows: [] })}
        asOf={AS_OF}
        onAsOfChange={() => {}}
        currency="USD"
        writeBlockedReason={null}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
      />,
      `/${TENANT}/payments/outstandings`,
      "/:tenant/payments/:tab",
      (client) =>
        client.setQueryData(outstandingsQueryKey(AS_OF, "", false), {
          ...OUTSTANDINGS,
          rows: [],
          totals: { accounts: 0, owed: "0.0000", dso_days: null },
        }),
    );
    expect(
      screen.queryByPlaceholderText(i18n.t("payments.outstandings.searchPlaceholder")),
    ).toBeNull();
    expect(screen.queryByLabelText(i18n.t("table.pager.next"))).toBeNull();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-138-BRC07 `P4.19` · blueprint p023 (the task row) · p081 (7·1) ·
//         p085 (7·3a, *"All four absent today"*) · B14 rules 12–16, 19
// generated: 2026-09-23 by LANE P4-TESTS
// checklist: A=n/a B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST, through `vitest` — `ladderBoardConfig`'s `filters`
//         array emptied made both `+ Filter` cases fail on 7·3a while 7·1
//         stayed green, and `debtorsTableConfig`'s `searchPlaceholder` removed
//         made 7·1's search cases fail while 7·3a stayed green. Each half of
//         the file was shown to fail independently, so neither is riding on
//         the other.
// exceptions: (1) NO SERVER PAGING IS ASSERTED. `GET /outstandings` CAN page
//         since `P4.1` and the screen does not ask it to — `DEF-PAY-6271` —
//         and `GET /collections/ladder` takes no page at all. What is asserted
//         here is that the CONTROL is on screen, which is B14 rule 16 and is
//         what `P4.19` names; where the paging happens is `DEF-PAY-6271` and
//         `DEF-PAY-6300`.
//         (2) THE EXPORT CONTROL IS NOT ASSERTED. B14 rule 12 names it and
//         `OutstandingsTab`'s exception (1) says `POST /exports` registers no
//         `outstandings` resource, so BR-SHL-010 keeps it unrendered. A case
//         asserting it would be asserting a capability nobody declared.
// status: VERIFIED-UNRATIFIED
