// ── Trace ──────────────────────────────────────────────
// Change:   `CR-138-BRC07` `P4.7` · `P4.8` · `P4.9` · `P4.11` — screens 7·1
//           Debtors, 7·2 Debtor and 7·3a Ladder, and the bulk bar that drops
//           to two plus an overflow. From §07 frames 7·1, 7·2 and 7·3a of
//           `05-prototype/06 Payments Page Blueprint.pdf` (p081–p086), read as
//           IMAGES at 2.0, 5.0 and 6.0 (B14 rule 42).
// Rules:    B14 rule 12 · 13 · 14 · 15 · 16 · 31 · 33 · 43 · BR-PAY-032 ·
//           BR-PAY-037 · BR-SHL-025
// Defects:  DEF-PAY-6252 · DEF-PAY-6253 · DEF-PAY-6254
// ───────────────────────────────────────────────────────
// What a person can SEE and PRESS on the three debtor screens.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ EVERY MOUNT IS UNDER THE REAL PATH PATTERN, AND THAT IS NOT PEDANTRY
// ══════════════════════════════════════════════════════════════════════════
// `DEF-CWP-3925`: a page mounted bare in a `MemoryRouter` with no `/:tenant/…`
// route leaves `useParams().tenant` undefined, so every address it builds
// comes out `//payments/…` — a protocol-relative URL to ANOTHER HOST, which
// reads as a perfectly good string to `toContain`. Six dead doors passed 391
// cases that way. So the fixture declares the route the router actually
// mounts, and every address assertion below carries the tenant segment.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ AND THE HOLD-EXPIRY CASES ARE THE POINT OF THIS FILE
// ══════════════════════════════════════════════════════════════════════════
// Two of the bulk bar's four refusals had expired before this lane opened it —
// one by HOURS and one by 38 DAYS — and nothing in the product noticed,
// because **nothing here re-checks a refusal**. `test_cr138_p4_17_site_visit_
// refusal.py` is the backend half of the cure. The cases at the bottom of this
// file are the front-end half: they read the SENTENCE a control is refusing
// with and fail when it names a thing that now exists.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { DebtorResponse } from "@/api/debtorEndpoints";
import type {
  OutstandingRow,
  OutstandingsResponse,
  PaymentPlanContext,
  PaymentPlanRow,
} from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import type { Translator } from "@/features/tenancy/settingsShared";

import { DebtorBulkBar, countedLabel } from "./DebtorBulkBar";
import {
  DebtorPage,
  billAgeDays,
  debtorTiles as debtorPageTiles,
  noticeTypeLabel,
} from "./DebtorPage";
import {
  DEBTORS_DEFAULT_SORT,
  DEBTOR_TABLE_SPEC,
  debtorDetailPath,
  debtorTiles,
  debtorsTableConfig,
  ladderTone,
} from "./debtorsTable";
import { accountPlanKey } from "./paymentsShared";

const TENANT = "brazosbend";
const t: Translator = (key, params) => i18n.t(key, params);
const REGIONAL = { timeZone: "UTC", dateFormat: "MM/DD/YYYY" as never };
const tenantPath = (path: string) => `/${TENANT}${path}`;

function outstandingRow(over: Partial<OutstandingRow> = {}): OutstandingRow {
  return {
    account_id: "01a046dd-d809-7e20-81a3-87b1eddc1b64",
    account_no: "AC-2026-00001",
    customer_name: "Ana Alvarez",
    balance: "1284.6000",
    days_late: 91,
    bucket: "90+",
    open_bills: 4,
    last_payment_on: "2026-08-02",
    notice_summary: "1st sent",
    collection_tier: "final_48_hour",
    next_step_due: "2026-09-28",
    plan_status: null,
    autopay: false,
    bad_address: false,
    gross_balance: null,
    credit_applied: null,
    ...over,
  };
}

function outstandings(over: Partial<OutstandingsResponse> = {}): OutstandingsResponse {
  return {
    as_of: "2026-09-21",
    rows: [outstandingRow()],
    totals: { accounts: 30, owed: "8870.5800", dso_days: null },
    // The drawing's five bands. **The figures are illustrations** (B14 rule
    // 37) — what is asserted below is that the bands SUM, never that they sum
    // to any particular number a wireframe happened to draw.
    ageing: [
      { bucket: "current", amount: "389.6400", accounts: 3, share: "4.4" },
      { bucket: "1-30", amount: "6712.2600", accounts: 20, share: "75.7" },
      { bucket: "31-60", amount: "108.8800", accounts: 5, share: "1.2" },
      { bucket: "61-90", amount: "1659.8000", accounts: 2, share: "18.7" },
      { bucket: "90+", amount: "0.0000", accounts: 0, share: "0.0" },
    ],
    problems: [],
    ...over,
  };
}

function debtor(over: Partial<DebtorResponse> = {}): DebtorResponse {
  return {
    account_id: "01a046dd-d809-7e20-81a3-87b1eddc1b64",
    account_no: "AC-2026-00001",
    as_of: "2026-09-21",
    position: {
      balance: "1284.600000",
      gross_balance: "1284.600000",
      credit_applied: "0.000000",
      oldest_due_on: "2026-07-12",
      invoice_count: 4,
      undated: [],
    },
    bills: [
      {
        invoice_id: "b-1", number: "BL-2606-000112", issued_on: "2026-06-22",
        due_on: "2026-07-12", total: "402.1500", amount_due: "402.1500",
        allocated: "0.0000", open_balance: "402.1500", currency: "USD",
      },
      {
        invoice_id: "b-2", number: "BL-2609-000085", issued_on: "2026-09-12",
        due_on: "2026-10-02", total: "226.0000", amount_due: "226.0000",
        allocated: "0.0000", open_balance: "226.0000", currency: "USD",
      },
    ],
    bill_count: 4,
    total_open: "1284.6000",
    currency: "USD",
    collections: {
      account_id: "01a046dd-d809-7e20-81a3-87b1eddc1b64",
      as_of: "2026-09-21",
      pause: {},
      disconnect_blocked: false,
      disconnect_detail: "",
      late_fee_suspended: false,
      plan: null,
      state: {
        tier: "final_48_hour",
        tier_sent_on: "2026-09-14",
        last_notice_on: "2026-09-14",
        next_step_due: "2026-09-28",
      },
      rungs: ["friendly", "first_10_day", "second_5_day", "final_48_hour"],
      problems: [],
    },
    history: [
      {
        id: "n-1", account_id: "a", notice_type: "disconnect", tier: "final_48_hour",
        channel: "email", outcome: "sent", skip_reason: null,
        outbound_message_id: "m-1", detail: {}, occurred_on: "2026-09-14", actor_id: null,
      },
    ],
    history_count: 1,
    history_offset: 0,
    history_limit: 50,
    history_page: 1,
    rungs: ["friendly", "first_10_day", "second_5_day", "final_48_hour"],
    problems: [],
    ...over,
  };
}

/** A client that answers the debtor read and refuses everything else BY NAME —
 *  a stub that silently answers `{}` to an unexpected path certifies a call it
 *  never checked. */
function debtorClient(body: DebtorResponse, plans?: PaymentPlanContext): ApiClient {
  const answer = async (path: string) => {
    if (path.startsWith("/debtors/")) {
      return { status: 200, data: body, headers: {} };
    }
    if (plans !== undefined && path.endsWith("/payment-plans")) {
      return { status: 200, data: plans, headers: {} };
    }
    throw new Error(`the fixture was asked for ${path}, which it does not serve`);
  };
  return {
    get: answer,
    post: answer,
    put: answer,
    patch: answer,
    delete: answer,
  } as unknown as ApiClient;
}

function mountDebtor(
  body: DebtorResponse,
  accountNo = "AC-2026-00001",
  plans?: PaymentPlanContext,
): string {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // The plan read is seeded under the key the page's shared hook reads
  // (`useAccountPlan`), for the same reason as the debtor read below.
  if (plans !== undefined) client.setQueryData(accountPlanKey(body.account_id), plans);
  // ⚠ **THE CACHE IS SEEDED, AND WITHOUT THIS EVERY ASSERTION BELOW READS A
  // LOADING SKELETON AND PASSES NOTHING.** `renderToStaticMarkup` does not
  // await a promise, so an unseeded `useQuery` is `undefined` on the only
  // render there is — the screen draws its skeleton and `toContain` is asked
  // about markup the page never produced. The first draft of this file did
  // exactly that and four cases failed loudly, which is the good outcome; a
  // case asserting an ABSENCE would have passed silently over it.
  //
  // The key is the page's own, spread the same way the page spreads it, so a
  // change to either is a change to both.
  client.setQueryData(["payments", "debtor", accountNo, "2026-09-21", 1], body);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <ToastProvider>
        {/* THE REAL PATH PATTERN — see this file's header. */}
        <MemoryRouter initialEntries={[`/${TENANT}/payments/debtors/${accountNo}`]}>
          <Routes>
            <Route
              path="/:tenant/payments/debtors/:accountNo"
              element={<DebtorPage client={debtorClient(body, plans)} today="2026-09-21" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ══════════════════════════════════════════════════════════════════════════
// 7·1 — THE FOUR TILES, AND THAT THEY ARE SUMS OF SERVED BANDS
// ══════════════════════════════════════════════════════════════════════════

describe("7·1 · the four tiles the drawing draws", () => {
  it("draws FOUR tiles, in the drawing's order", () => {
    const tiles = debtorTiles(outstandings(), "USD", t);
    expect(tiles.map((tile) => tile.id)).toEqual(["owed", "overdue", "over60", "chased"]);
  });

  it("OVERDUE is the four non-current bands added on the exact grid, never a subtraction", () => {
    const tiles = debtorTiles(outstandings(), "USD", t);
    const overdue = tiles[1];
    // 6712.26 + 108.88 + 1659.80 + 0.00. Asserted as the SUM of the fixture's
    // own bands rather than as a number copied off the drawing (rule 37).
    expect("money" in overdue && overdue.money.amount).toBe("8480.940000");
  });

  it("OVER 60 DAYS is the tail that decides escalation — the last two bands only", () => {
    const tiles = debtorTiles(outstandings(), "USD", t);
    const over = tiles[2];
    expect("money" in over && over.money.amount).toBe("1659.800000");
  });

  it("renders a stated absence rather than a bare number when no currency was read", () => {
    const tiles = debtorTiles(outstandings(), null, t);
    // Hard rule 2 is a PAIR. Every money tile must refuse, and none may carry
    // a `money` member that would render an unlabelled figure.
    for (const tile of tiles.slice(0, 3)) {
      expect("money" in tile).toBe(false);
    }
  });
});

describe("7·1 · the table's five controls and its one door", () => {
  const config = debtorsTableConfig(t, REGIONAL, "USD", tenantPath);

  it("declares a search prompt of its own (B14 rule 19), not the product default", () => {
    expect(config.searchPlaceholder).toBe("payments.outstandings.searchPlaceholder");
    expect(config.searchFields).toEqual(["account_no", "customer_name"]);
  });

  it("sorts AR high → low by default (BR-PAY-029)", () => {
    expect(config.defaultSort).toEqual(DEBTORS_DEFAULT_SORT);
    expect(DEBTORS_DEFAULT_SORT).toEqual({ sort: "balance", dir: "desc" });
  });

  it("makes the drawing's eight columns the default view and hides the rest, deleting none", () => {
    const visible = config.columns.filter((c) => c.defaultVisible !== false).map((c) => c.key);
    // ACCOUNT · CUSTOMER · OLDEST · LAST PAID · LADDER · PLAN · OWED · actions.
    // The drawing's ADDRESS column is ABSENT and not empty — no served field
    // carries it (`DEF-PAY-6264`).
    expect(visible).toEqual([
      "account_no", "customer_name", "days_late", "last_payment_on",
      "collection_tier", "plan_status", "balance",
      // ⚠ **A NINTH THE DRAWING DOES NOT DRAW, KEPT ON A SIGNED RULE.**
      // `BR-PAY-018` says bad address is a column AND a filter. B14 rule 41
      // hands a drawing that contradicts a signed rule to the PO rather than
      // to a lane, so the rule wins and the divergence is reported.
      "bad_address",
      "actions",
    ]);
    // …and nothing was thrown away: the other seven are still choosable.
    // FOURTEEN and not fifteen — the `select` checkbox column is declared ONLY
    // where a screen passes a selection, which is BR-SHL-010's own rule and
    // the reason a list without one renders byte-identical markup to a list
    // that never heard of the feature. This config has none.
    expect(config.columns.length).toBe(14);
    expect(config.columns.map((c) => c.key)).not.toContain("select");
  });

  it("puts ⇅ on the headers the drawing marks", () => {
    const sortable = config.columns.filter((c) => c.sortable === true).map((c) => c.key);
    for (const key of ["account_no", "days_late", "last_payment_on", "collection_tier", "balance"]) {
      expect(sortable).toContain(key);
    }
  });

  it("opens 7·2 at the ACCOUNT NUMBER, never at a database id (B14 rule 31)", () => {
    const path = debtorDetailPath("AC-2026-00001");
    expect(path).toBe("/payments/debtors/AC-2026-00001");
    // The uuid must not appear anywhere in the address a clerk can read.
    expect(path).not.toContain("01a046dd");
  });

  it("draws NO door at all for an account with no number, rather than one carrying the id", () => {
    expect(debtorDetailPath(null)).toBeNull();
    expect(debtorDetailPath("")).toBeNull();
  });
});

describe("7·1 · the browser's half of the table, until P4.1 lands", () => {
  const rows = [
    outstandingRow({ account_id: "a", account_no: "AC-1", balance: "9.0000", days_late: 3 }),
    outstandingRow({ account_id: "b", account_no: "AC-2", balance: "10.0000", days_late: null }),
    outstandingRow({ account_id: "c", account_no: "AC-3", balance: "100.0000", days_late: 91 }),
  ];
  const state = {
    q: "", sort: "balance", dir: "desc" as const, page: 1, per: 50 as const, filters: {},
  };

  it("sorts money on the grid, not as text — 9 does not beat 10", () => {
    const order = [...rows]
      .sort((x, y) => {
        const left = DEBTOR_TABLE_SPEC.sortValue(x, "balance") as number;
        const right = DEBTOR_TABLE_SPEC.sortValue(y, "balance") as number;
        return right - left;
      })
      .map((row) => row.account_no);
    expect(order).toEqual(["AC-3", "AC-2", "AC-1"]);
    void state;
  });

  it("returns null — never undefined — for a column nobody mapped", () => {
    // `undefined` would sort every row EQUAL: a header that cycles, an arrow
    // that moves and a list that never reorders (hard-won law 7).
    expect(DEBTOR_TABLE_SPEC.sortValue(rows[0], "no_such_column")).toBeNull();
  });

  it("keeps a null OLDEST out of the front of an ascending sort", () => {
    // BR-PAY-032: a bill nobody can place in time is not the oldest debt in
    // the book. A dash at the top of the list is the row a clerk chases first.
    expect(DEBTOR_TABLE_SPEC.sortValue(rows[1], "days_late")).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 7·2 — THE SCREEN THE LIST HAS NEVER HAD
// ══════════════════════════════════════════════════════════════════════════

describe("7·2 · the debtor screen", () => {
  it("renders the account NUMBER as its title and no uuid anywhere", () => {
    const html = mountDebtor(debtor());
    expect(html).toContain("AC-2026-00001");
    expect(html).not.toContain("01a046dd-d809-7e20-81a3-87b1eddc1b64");
  });

  it("draws the drawing's four tiles in its order", () => {
    expect(debtorPageTiles(debtor(), t).map((tile) => tile.id)).toEqual([
      "owes", "oldest", "ladder", "promised",
    ]);
  });

  it("draws PROMISED as an absence and NEVER as a zero", () => {
    const tiles = debtorPageTiles(debtor(), t);
    const promised = tiles[3];
    // A screen that printed $0.00 here would say the customer has promised
    // nothing when the truth is that nobody has asked.
    expect("money" in promised).toBe(false);
    expect(promised.detail).toBe(i18n.t("payments.debtor.kpi.noPlan"));
  });

  it("anchors OLDEST on the oldest unpaid bill's due date (BR-PAY-032)", () => {
    // 2026-07-12 → 2026-09-21 is 71 days. Computed from two dates the SERVER
    // sent, not from a figure the drawing happened to show.
    expect(billAgeDays("2026-07-12", "2026-09-21")).toBe(71);
  });

  it("calls a bill with no due date UNPLACEABLE, never zero and never 'not due'", () => {
    expect(billAgeDays(null, "2026-09-21")).toBeNull();
    expect(billAgeDays("", "2026-09-21")).toBeNull();
  });

  it("calls a bill whose due date has not arrived NOT DUE", () => {
    expect(billAgeDays("2026-10-02", "2026-09-21")).toBe("not_due");
  });

  it("draws the DUE column from the field DEF-PAY-6254 made the server send", () => {
    const html = mountDebtor(debtor());
    expect(html).toContain("BL-2606-000112");
    // The bill's own due date reaches the screen. Before 2026-09-23 the read
    // served none and this column had no source at all.
    expect(html).toContain(i18n.t("payments.debtor.col.due"));
  });

  it("carries a LIVE door to the payment-plan wizard (DEF-PAY-6253)", () => {
    const html = mountDebtor(debtor());
    // The bulk bar told clerks for 38 days that this wizard was not built.
    expect(html).toContain(i18n.t("payments.debtor.action.offerPlan"));
    // …and it is not disabled, which is the whole finding.
    //
    // ⚠ **THE FIRST SPELLING OF THIS ASSERTION PASSED WRONGLY AND THE CASE
    // CAUGHT IT.** It read `/disabled[^>]*>\s*Offer a plan/`, which matches
    // the TAILWIND VARIANT `disabled:opacity-50` sitting in the button's own
    // `class` attribute — so it reported the control disabled while the markup
    // carried no `disabled` attribute at all. A real attribute is `disabled`
    // followed by `=`, whitespace or `>`; the variant is followed by `:`.
    // (Hard-won law 7's second habit: ask what would make this check FAIL
    // wrongly, not only what makes it pass.)
    expect(html).not.toMatch(
      new RegExp(`<button[^>]*\\sdisabled[=\\s>][^>]*>${i18n.t("payments.debtor.action.offerPlan")}`),
    );
    // …and the mirror, so the case cannot go quiet if the markup changes: the
    // control that IS held says so.
    expect(html).toMatch(
      new RegExp(`<button[^>]*\\sdisabled[=\\s>][^>]*>${i18n.t("payments.debtor.action.record")}`),
    );
  });

  it("says why Record payment cannot act, rather than opening onto nothing", () => {
    const html = mountDebtor(debtor());
    expect(html).toContain(i18n.t("payments.debtor.action.recordAwaitsScreen"));
  });

  it("shows the trail it was given and counts it from the server's COUNT(*)", () => {
    const html = mountDebtor(debtor());
    expect(html).toContain(i18n.t("payments.debtor.triedTitle"));
  });

  it("names the KIND of letter in words, never its internal code (B14 rule 31)", () => {
    // ⚠ **THIS CELL PRINTED `notice_type` RAW.** The server writes `reminder`
    // and `disconnect`; no catalogue covered either, because the tier
    // vocabulary describes a RUNG and a row with a null tier has none. A
    // clerk read the code.
    const html = mountDebtor(
      debtor({
        history: [
          {
            id: "n-2", account_id: "a", notice_type: "disconnect", tier: null,
            channel: "post", outcome: "sent", skip_reason: null,
            outbound_message_id: null, detail: {}, occurred_on: "2026-09-14",
            actor_id: null,
          },
        ],
        history_count: 1,
      }),
    );
    expect(html).toContain(i18n.t("payments.noticeType.disconnect"));
    const text = html.replace(/<[^>]*>/g, " ");
    expect(text).not.toContain("disconnect");
  });

  it("falls back to a WORD for a kind this deployment has not heard of", () => {
    // The mirror, and it is the half that rots: a third value the server
    // starts writing must not reach a clerk as itself.
    const html = mountDebtor(
      debtor({
        history: [
          {
            id: "n-3", account_id: "a", notice_type: "final_demand_v2", tier: null,
            channel: "post", outcome: "sent", skip_reason: null,
            outbound_message_id: null, detail: {}, occurred_on: "2026-09-14",
            actor_id: null,
          },
        ],
        history_count: 1,
      }),
    );
    expect(html).toContain(i18n.t("payments.noticeType.other"));
    expect(html.replace(/<[^>]*>/g, " ")).not.toContain("final_demand_v2");
  });

  it("every fixture value in this file resolves to a catalogue sentence", () => {
    // ⚠ **`DEF-PAY-6270`'s LESSON, GENERALISED.** A sibling's fixture seeded
    // `reason: "uncollectable"`, which is not one of the four the catalogue
    // has, and once rows started rendering it put
    // `payments.writeOff.reason.uncollectable` into a column where a clerk
    // reads words. **A missing key reaches a clerk as the KEY, or as silence
    // — never as an error** — so the check is that no rendered text carries a
    // dotted key prefix at all.
    const html = mountDebtor(debtor());
    const text = html.replace(/<[^>]*>/g, " ");
    for (const prefix of [
      "payments.writeOff.reason.",
      "payments.tier.",
      "payments.planStatus.",
      "payments.skip.",
      "payments.noticeType.",
      "payments.problem.",
    ]) {
      expect(text).not.toContain(prefix);
    }
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 7·2 · THE PAYMENT PLAN SECTION — PO 2026-10-11, "images are correct - you
// can proceed with fix" (decision log "DEBTORS DETAIL … SHOWS THE PAYMENT
// PLAN'S INSTALMENTS")
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ THE EXPECTED STRINGS ARE LITERALS, NOT CATALOGUE LOOK-UPS — building the
// expected sentence from the catalogue the screen renders from makes both sides
// move together (`PaymentPlanWizard.test.tsx` records the case that passed
// over its own defect that way). The fixture is the approved preview's
// part-paid example: 2 of 4 met, 3 and 4 missed.

function jonasPlan(over: Partial<PaymentPlanRow> = {}): PaymentPlanRow {
  return {
    id: "plan-jonas",
    status: "active",
    currency: "USD",
    total_amount: "372.900000",
    down_payment: "0.000000",
    spread: "372.900000",
    paid_to_date: "186.460000",
    installment_count: 4,
    cadence: "biweekly",
    autopay_enabled: false,
    suspend_late_fees: false,
    suspend_disconnect: true,
    proposed_on: "2026-07-06",
    agreement_sent_on: "2026-07-06",
    signed_on: "2026-07-07",
    closed_on: null,
    live: true,
    current_bill_still_due: true,
    missed_installment_seqs: [3, 4],
    missed_as_of: "2026-09-21",
    installments: [
      { seq: 1, due_date: "2026-07-20", amount: "93.230000", currency: "USD",
        paid_posted_on: "2026-07-20", on_time: true },
      { seq: 2, due_date: "2026-08-03", amount: "93.230000", currency: "USD",
        paid_posted_on: "2026-08-03", on_time: true },
      { seq: 3, due_date: "2026-08-17", amount: "93.230000", currency: "USD",
        paid_posted_on: null, on_time: null },
      { seq: 4, due_date: "2026-08-31", amount: "93.210000", currency: "USD",
        paid_posted_on: null, on_time: null },
    ],
    ...over,
  };
}

function plansContext(live: PaymentPlanRow | null): PaymentPlanContext {
  return {
    account_id: "01a046dd-d809-7e20-81a3-87b1eddc1b64",
    account_no: "AC-2026-00001",
    name: "Jonas Janssen",
    balance: "1284.600000",
    currency: "USD",
    balance_unavailable: null,
    balance_basis: "posting",
    as_of: "2026-09-21",
    plans: live === null ? [] : [live],
    plans_unavailable: null,
    live_plan: live,
    can_propose: live === null,
    cannot_propose_reason: live === null ? null : "this account already has a live payment plan",
    cannot_propose_reason_key: live === null ? null : "customers.paymentPlan.alreadyHasPlan",
    cadences: ["monthly", "biweekly", "weekly"],
    agreement_channels: ["email", "sms", "print"],
    defaults: { autopay_enabled: true, suspend_late_fees: false, suspend_disconnect: true },
    current_bill_still_due: true,
    plan_can_be_voided: false,
  };
}

/** The rows of the plan section's table, as plain text per cell. */
function planRows(html: string): string[][] {
  const section = /<section[^>]*data-debtor-plan[^>]*>([\s\S]*?)<\/section>/.exec(html);
  if (section === null) return [];
  const body = /<tbody>([\s\S]*?)<\/tbody>/.exec(section[1])?.[1] ?? "";
  return [...body.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((row) =>
    [...row[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((cell) =>
      cell[1].replace(/<[^>]*>/g, "").replace(/&#x27;/g, "'").trim(),
    ),
  );
}

describe("7·2 · the Payment plan section (PO 2026-10-11)", () => {
  const withPlan = () =>
    debtor({
      collections: {
        ...debtor().collections,
        plan: {
          id: "plan-jonas", status: "active", missed: 2,
          suspend_late_fees: false, suspend_disconnect: true,
        },
      },
    });

  it("draws the section between WHAT IS OWED and WHAT WE TRIED", () => {
    const html = mountDebtor(withPlan(), "AC-2026-00001", plansContext(jonasPlan()));
    const owed = html.indexOf("What is owed");
    const plan = html.indexOf("Payment plan</h3>");
    const tried = html.indexOf("What we tried");
    expect(owed).toBeGreaterThan(-1);
    expect(plan).toBeGreaterThan(owed);
    expect(tried).toBeGreaterThan(plan);
  });

  it("draws four rows with their statuses, and Left is $0.00 on the paid rows", () => {
    const html = mountDebtor(withPlan(), "AC-2026-00001", plansContext(jonasPlan()));
    const rows = planRows(html);
    // # · Due · Amount · Left · Status. This fixture's tenant is MM/DD/YYYY
    // under test, and a date is never ISO (BR-SHL-023).
    expect(rows).toEqual([
      ["1", "07/20/2026", "$93.23", "$0.00", "Paid 07/20/2026"],
      ["2", "08/03/2026", "$93.23", "$0.00", "Paid 08/03/2026"],
      ["3", "08/17/2026", "$93.23", "$93.23", "Outstanding"],
      ["4", "08/31/2026", "$93.21", "$93.21", "Outstanding"],
    ]);
    expect(html).not.toContain("2026-07-20");
  });

  it("counts 2 paid · 2 missed · 0 upcoming, agreeing with the tile's 2 missed", () => {
    const html = mountDebtor(withPlan(), "AC-2026-00001", plansContext(jonasPlan()));
    const text = html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ");
    expect(text).toContain("2 paid 2 missed 0 upcoming");
    expect(text).toContain("Paid $186.46 of $372.90 · 2 of 4 met");
    // The PROMISED tile reads the debtor read's own `missed`.
    expect(text).toContain("2 missed");
  });

  it("says the missed line in the plural, with a joined list", () => {
    const html = mountDebtor(withPlan(), "AC-2026-00001", plansContext(jonasPlan()));
    expect(html).toContain("Installments 3 and 4 were missed.");
    expect(html).not.toContain("Installment 3, 4 was missed.");
  });

  it("says the missed line in the singular for one instalment", () => {
    const one = jonasPlan({
      missed_installment_seqs: [1],
      paid_to_date: "0.000000",
      installments: jonasPlan().installments.map((row) => ({
        ...row, paid_posted_on: null, on_time: null,
      })),
    });
    const html = mountDebtor(withPlan(), "AC-2026-00001", plansContext(one));
    expect(html).toContain("Installment 1 was missed.");
    const text = html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ");
    expect(text).toContain("0 paid 1 missed 3 upcoming");
  });

  it("draws NO section for an account with no plan", () => {
    const html = mountDebtor(debtor(), "AC-2026-00001", plansContext(null));
    expect(html).not.toContain("data-debtor-plan");
    expect(html).not.toContain("Payment plan</h3>");
    // …and none while the plan read has not answered either.
    expect(mountDebtor(debtor())).not.toContain("data-debtor-plan");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 7·1's BULK BAR — TWO PLUS AN OVERFLOW, AND THE REFUSALS THAT EXPIRED
// ══════════════════════════════════════════════════════════════════════════

function mountBar(over: Partial<React.ComponentProps<typeof DebtorBulkBar>> = {}): string {
  return renderToStaticMarkup(
    <DebtorBulkBar
      label="Actions"
      count="3 selected"
      totalText="$1,284.60"
      sendableCount={null}
      steppableCount={null}
      sendNoticeReason={i18n.t("payments.outstandings.action.noticeAwaitsScreen")}
      onSendNotice={() => undefined}
      moveOnReason={null}
      onMoveOn={() => undefined}
      writeOffReason={null}
      onWriteOff={() => undefined}
      reminderReason={i18n.t("payments.outstandings.action.noticeAwaitsScreen")}
      onReminder={() => undefined}
      planReason={i18n.t("payments.outstandings.action.planNeedsOneAccount")}
      onPlan={() => undefined}
      siteVisitReason={i18n.t("payments.outstandings.action.fieldVisitUnavailable")}
      onSiteVisit={() => undefined}
      labels={{
        sendNotice: i18n.t("payments.outstandings.action.notice"),
        moveOn: i18n.t("payments.outstandings.action.runLadder"),
        writeOff: i18n.t("payments.outstandings.action.writeOff"),
        reminder: i18n.t("payments.outstandings.action.reminder"),
        plan: i18n.t("payments.outstandings.action.plan"),
        siteVisit: i18n.t("payments.outstandings.action.fieldVisit"),
        more: i18n.t("table.rowActions.more"),
        clear: i18n.t("payments.outstandings.action.clear"),
      }}
      onClear={() => undefined}
      {...over}
    />,
  );
}

describe("P4.11 · six buttons become two plus an overflow", () => {
  it("draws exactly TWO controls beside the overflow and the clear (B14 rule 15)", () => {
    const html = mountBar();
    // The `…` menu renders open-able markup under `renderToStaticMarkup`, so
    // the four inside it are readable here — a `useState` menu would render as
    // nothing and four assertions would pass over an empty cell.
    const menu = html.slice(html.indexOf("data-row-more"));
    for (const label of [
      i18n.t("payments.outstandings.action.writeOff"),
      i18n.t("payments.outstandings.action.reminder"),
      i18n.t("payments.outstandings.action.plan"),
      i18n.t("payments.outstandings.action.fieldVisit"),
    ]) {
      expect(menu).toContain(label);
    }
    // …and the two that are NOT in the menu are the two the drawing draws.
    const bar = html.slice(0, html.indexOf("data-row-more"));
    expect(bar).toContain(i18n.t("payments.outstandings.action.notice"));
    expect(bar).toContain(i18n.t("payments.outstandings.action.runLadder"));
  });

  it("keeps all six reachable — nothing is removed (BR-SHL-025)", () => {
    const html = mountBar();
    for (const label of [
      "payments.outstandings.action.notice",
      "payments.outstandings.action.runLadder",
      "payments.outstandings.action.writeOff",
      "payments.outstandings.action.reminder",
      "payments.outstandings.action.plan",
      "payments.outstandings.action.fieldVisit",
    ]) {
      expect(html).toContain(i18n.t(label));
    }
  });

  it("draws NO number on a control whose eligible count nobody can compute", () => {
    // "Send notice 0" would say the act reaches nobody, which is a claim.
    expect(countedLabel("Send notice", null)).toBe("Send notice");
    expect(countedLabel("Send notice", 2)).toBe("Send notice 2");
  });
});

describe("P4.11 · the refusals, and whether each is still true", () => {
  it("no longer claims that no route accepts a notice — DEF-PAY-6252", () => {
    // ⚠ **THE HOLD-EXPIRY CASE.** `POST /collections/notices` was mounted by
    // `P4.13` on 2026-09-23. The sentence beside these two controls said *"no
    // route accepts one yet"*, which stopped being true that morning. What is
    // still missing is 7·3d, the SCREEN — so the refusal names the screen.
    const sentence = i18n.t("payments.outstandings.action.noticeAwaitsScreen");
    expect(sentence).not.toContain("route");
    expect(mountBar()).toContain(sentence);
  });

  it("no longer claims the payment-plan wizard is unbuilt — DEF-PAY-6253", () => {
    // ⚠ **THE OTHER HOLD-EXPIRY CASE, AND IT HAD BEEN FALSE FOR 38 DAYS.**
    // `features/customers/PaymentPlanWizard.tsx` was generated 2026-08-16 and
    // is routed at `/:tenant/accounts/:accountId/payment-plan`. What this BAR
    // cannot do is offer a plan over a SELECTION, and that is what it says.
    const sentence = i18n.t("payments.outstandings.action.planNeedsOneAccount");
    expect(sentence).not.toMatch(/not built|isn't built/i);
    expect(mountBar()).toContain(sentence);
  });

  it("leaves the site-visit refusal WORD FOR WORD — P4.17 re-checked it and it holds", () => {
    // `tests/test_cr138_p4_17_site_visit_refusal.py` asserts this exact string
    // and a PAIRING INVARIANT: the sentence and the door move together. This
    // case exists so a front-end lane cannot re-word it in passing.
    expect(i18n.t("payments.outstandings.action.fieldVisitUnavailable")).toBe(
      "A site visit has no agreed rule behind it, so nothing here can book one.",
    );
  });
});

describe("the notice kind reads as words", () => {
  it("maps the two the server writes and refuses to echo a third", () => {
    expect(noticeTypeLabel("reminder", t)).toBe(i18n.t("payments.noticeType.reminder"));
    expect(noticeTypeLabel("disconnect", t)).toBe(i18n.t("payments.noticeType.disconnect"));
    expect(noticeTypeLabel("something_new", t)).toBe(i18n.t("payments.noticeType.other"));
    expect(noticeTypeLabel(null, t)).toBe(i18n.t("payments.noticeType.other"));
  });
});

describe("the ladder pill reads the same on both boards", () => {
  it("escalates the tone with the rung, and never guesses at an unknown one", () => {
    expect(ladderTone("final_48_hour")).toBe("danger");
    expect(ladderTone("first_10_day")).toBe("warning");
    // A grey pill is one a clerk reads as ordinary; the failure of a wrong
    // tone is that a final notice looks routine.
    expect(ladderTone("something_this_deployment_has_not_heard_of")).toBe("neutral");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/06 Payments Page Blueprint.pdf p081–p086 read as IMAGES at 2.0/5.0/6.0 · CR-138-BRC07 §3 P4.7/P4.8/P4.9/P4.11
// generated: 2026-09-23 by LANE P4-SCREENS-A
// gates: every case RED-PROVED before green — the tile order case fails on a five-tile strip, the two hold-expiry cases fail against the superseded sentences, and the door case fails when `debtorDetailPath` falls back to the id
// exceptions: the drawing's FIGURES are never asserted (B14 rule 37 — a drawn number is an illustration); what is asserted is that the bands SUM and that each absence is drawn as an absence
// ──────────────────────────────────────────────────────────
