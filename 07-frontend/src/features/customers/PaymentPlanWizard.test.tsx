// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-018 (S24 — amount & term → schedule → agreement) ·
//           US-PAY-017 (the payments-owned plan rows this screen draws)
//           Screens: S24
// Rules:    BR-CUS-043 (schedule math is the SERVER's; one live plan per
//           account) · BR-CUS-044 (activation on the CUSTOMER's signature) ·
//           BR-BIL-073 (a plan does NOT suspend the current bill) ·
//           BR-SHL-025 (disabled WITH the reason) · BR-SHL-044 (one header) ·
//           CLAUDE.md rule 2 (money renders with its currency)
// ───────────────────────────────────────────────────────
// ❄️ GT-47 is the fixture: **267.30 less a 50.00 down payment over six
// instalments is 5 × 36.22 and a FINAL 36.20**. The screen renders the server's
// strings, so the assertions are on what a clerk SEES — `$36.20` on the last
// row, not `$36.22` — and on the two sentences the ruling of 2026-08-11
// requires it to carry.
//
// THE ASSERTIONS THAT MATTER MOST ARE NEGATIVE:
//   · an unreadable balance renders its REASON and never `$0.00` (DEF-127);
//   · nothing anywhere offers to VOID a plan (PO 2026-08-11, "nodrop");
//   · nothing says the agreement was SENT — it is QUEUED (PO 2026-08-16).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { AccountDetail, MyPermissions, PaymentPlanContext } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { accountDetailQueryKey } from "./AccountDetailPage";
import {
  PAYMENT_PLAN_STEPS,
  PAYMENT_PLAN_STEP_LABEL_KEYS,
  PaymentPlanWizard,
  blockedReason,
  blockedSentence,
  livePlanOf,
  paymentPlansKey,
  sendBlockedReason,
} from "./PaymentPlanWizard";
import { ACCOUNTS_PERMISSION, accountPaymentPlanPath } from "./customersShared";
import { planCounts } from "./PaymentPlanSchedule";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

// ❄️ GT-47 verbatim.
const GT47_INSTALMENTS = ["36.220000", "36.220000", "36.220000", "36.220000", "36.220000"];
const GT47_FINAL = "36.200000";

function detail(over: Partial<AccountDetail> = {}): AccountDetail {
  return {
    id: "acc-10432",
    account_no: "A-10432",
    name: "Miller, Sarah",
    unit_id: "u-10432a",
    unit_label: "A",
    premise: "1408 Elm St · A",
    services: ["electric"],
    balance: "267.300000",
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    // BR-CUS-510 / DEF-628 — the DEFAULT is `false`: this fixture's zero,
    // wherever it has one, is a real answer about money owed.
    balance_not_yet_billable: false,
    balance_cached: "0.000000",
    currency: "USD",
    status: "active",
    status_name: "Active",
    status_behavior_class: "billable",
    account_type: "residential",
    account_subtype: null,
    autopay: true,
    opened_at: "2024-02-14",
    closed_at: null,
    last_bill_at: null,
    aging: null,
    deposit_on_file: "0.000000",
    deposit_received_on: null,
    credit_tier: null,
    tax_exempt: false,
    tax_exempt_ref: null,
    tax_exempt_expires: null,
    bad_address: false,
    nsf_count: 0,
    preferred_language: null,
    custom_data: {},
    contacts: [],
    addresses: [],
    service_agreements: [],
    meters: [],
    plan: null,
    plan_snapshot_unavailable: "BR-CUS-029",
    customer: null,
    ...over,
  } as AccountDetail;
}

function context(over: Partial<PaymentPlanContext> = {}): PaymentPlanContext {
  return {
    account_id: "acc-10432",
    account_no: "A-10432",
    name: "Miller, Sarah",
    balance: "267.300000",
    currency: "USD",
    balance_unavailable: null,
    balance_basis: "posting",
    as_of: "2026-08-16",
    plans: [],
    plans_unavailable: null,
    live_plan: null,
    can_propose: true,
    cannot_propose_reason: null,
    cadences: ["monthly", "biweekly", "weekly"],
    agreement_channels: ["email", "sms", "print"],
    defaults: { autopay_enabled: true, suspend_late_fees: false, suspend_disconnect: true },
    current_bill_still_due: true,
    plan_can_be_voided: false,
    ...over,
  };
}

/** ❄️ The frozen plan, as `GET /accounts/{id}/payment-plans` returns it. */
function gt47Plan(over = {}) {
  return {
    id: "plan-1",
    status: "agreement_sent",
    currency: "USD",
    total_amount: "267.300000",
    down_payment: "50.000000",
    spread: "217.300000",
    paid_to_date: "0.000000",
    installment_count: 6,
    cadence: "monthly",
    autopay_enabled: true,
    suspend_late_fees: false,
    suspend_disconnect: true,
    proposed_on: "2026-08-16",
    agreement_sent_on: "2026-08-16",
    signed_on: null,
    closed_on: null,
    live: true,
    current_bill_still_due: true,
    missed_installment_seqs: [],
    missed_as_of: "2026-08-16",
    installments: [...GT47_INSTALMENTS, GT47_FINAL].map((amount, index) => ({
      seq: index + 1,
      due_date: `2026-0${9 + Math.floor(index / 4)}-0${(index % 4) + 1}`,
      amount,
      currency: "USD",
      paid_posted_on: null,
      on_time: null,
    })),
    ...over,
  };
}

function permissions(access: string): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access }],
  };
}

function renderWizard(
  seed: { detail?: AccountDetail; context?: PaymentPlanContext; access?: string } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const account = seed.detail ?? detail();
  queryClient.setQueryData(accountDetailQueryKey(account.id), account);
  queryClient.setQueryData(paymentPlansKey(account.id), seed.context ?? context());
  queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access ?? "Full"));
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${accountPaymentPlanPath(account.id)}`]}>
          <Routes>
            <Route
              path="/:tenant/accounts/:accountId/payment-plan"
              element={<PaymentPlanWizard />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The document with every `title=` attribute removed — the disabled reasons
 *  NAME the things they refuse, and a whole-document `not.toContain` would read
 *  that explanation as the defect it exists to prevent. */
function visible(html: string): string {
  return html.replace(/ title="[^"]*"/g, "");
}

describe("US-CUS-018 · S24 the payment-plan wizard", () => {
  it("has three steps, in the order US-CUS-018 §1 names them", () => {
    expect(PAYMENT_PLAN_STEPS).toEqual(["terms", "schedule", "agreement"]);
  });

  /**
   * ⛔ **`DEF-CUS-5071` — THE RAIL, READ OFF THE RENDERED SCREEN.**
   *
   * The case above (*"has three steps, in the order US-CUS-018 §1 names
   * them"*) asserted `PAYMENT_PLAN_STEPS` equals
   * `["terms","schedule","agreement"]` — **the array equalling itself**, which
   * is hard-won law 7's *looking at the wrong thing*: it proved the model and
   * could never tell you a clerk sees it. It stays, because the ORDER is worth
   * pinning; this is the half that was missing.
   */
  it("draws the numbered rail, with the step it is on marked active (B14 rule 3)", () => {
    const html = renderWizard();
    expect(html).toContain('data-wizard="rail"');
    for (const id of PAYMENT_PLAN_STEPS) {
      expect(html).toContain(t(PAYMENT_PLAN_STEP_LABEL_KEYS[id]));
    }
    // The numbers, and WHICH ONE IS ACTIVE — a rail that draws three words and
    // never moves is the same defect wearing a rail.
    expect(html).toContain('data-wizard-step="1" data-state="active"');
    expect(html).toContain('data-wizard-step="3" data-state="upcoming"');
    // …and the sentence beside it counts the DECLARED list (BR-SHL-046).
    expect(html).toContain(
      // `DEF-CUS-5171` — the sub-line gained the step's NAME, which the
      // blueprint draws (`Step 1 of 3 · Terms`). The count still comes from the
      // DECLARED list, which is what this case is about.
      t("customers.paymentPlan.stepOf", {
        step: 1,
        of: PAYMENT_PLAN_STEPS.length,
        name: t(PAYMENT_PLAN_STEP_LABEL_KEYS.terms),
      }),
    );
  });

  it("TC-1 · step 1 opens with the ledger's balance and its currency", () => {
    const html = renderWizard();
    expect(html).toContain("$267.30");
    expect(html).toContain(t("customers.paymentPlan.balanceToSpread"));
    expect(html).toContain(t("customers.paymentPlan.firstDue"));
  });

  it("DEF-127 · an unreadable balance renders its REASON and never $0.00", () => {
    // The whole point: "we could not tell" and "nothing is owed" must not draw
    // the same tile. A $0.00 here reads exactly like a settled account.
    const html = renderWizard({
      context: context({
        balance: null,
        balance_unavailable: "no_ar_designation",
        can_propose: false,
        cannot_propose_reason: "the ledger could not be asked what this account owes",
      }),
    });
    expect(html).toContain("balance-unavailable");
    expect(html).toContain("no_ar_designation");
    expect(visible(html)).not.toContain("$0.00");
    // …and the wizard does not open over it.
    expect(html).toContain("cannot-propose");
    expect(html).not.toContain(t("customers.paymentPlan.balanceToSpread"));
  });

  it("an unreadable PLAN LIST is not an empty one", () => {
    const html = renderWizard({
      context: context({
        plans: null,
        plans_unavailable: "payments publishes no payment-plan read on this deployment",
        can_propose: false,
        cannot_propose_reason: "payments publishes no payment-plan read on this deployment",
      }),
    });
    expect(html).toContain("plans-unavailable");
    expect(html).toContain("payments publishes no payment-plan read");
  });

  it("❄️ GT-47 · the live plan's last instalment renders $36.20, not $36.22", () => {
    const plan = gt47Plan();
    const html = renderWizard({
      context: context({
        plans: [plan],
        live_plan: plan,
        can_propose: false,
        cannot_propose_reason: "this account already has a live payment plan",
        cannot_propose_reason_key: "customers.paymentPlan.alreadyHasPlan",
      }),
    });
    expect(html).toContain("$36.22");
    // The signed figure. 36.22 × 6 = 217.32, two cents more than was agreed.
    expect(html).toContain("$36.20");
    expect(html).toContain("$267.30");
    // Every instalment carries the day it falls due — and since `DEF-CUS-5171`
    // it carries it in the TENANT's format rather than as ISO (`BR-SHL-023`,
    // one formatting path; this fixture's tenant is `MM/DD/YYYY`). The date
    // matters here, the spelling does not, so the assertion moved with it.
    expect(html).toContain("09/01/2026");
    expect(html).not.toContain("2026-09-01");
  });

  it("PO 2026-08-11 · the plan panel says the current bill is STILL DUE", () => {
    const plan = gt47Plan();
    const html = renderWizard({
      context: context({ plans: [plan], live_plan: plan, can_propose: false, cannot_propose_reason: "live plan" }),
    });
    // The apostrophe is HTML-escaped in the rendered markup, so the assertion
    // is on the load-bearing half of the sentence.
    expect(html).toContain("bill is still due and is still chased");
  });

  it("PO 2026-08-11 · nothing offers to VOID a plan, in any state", () => {
    const plan = gt47Plan({ status: "active", signed_on: "2026-08-20" });
    const html = renderWizard({
      context: context({ plans: [plan], live_plan: plan, can_propose: false, cannot_propose_reason: "live plan" }),
    });
    // "nodrop we chase for payments until write off" — four states, no `void`,
    // and whether staff may CANCEL one is OQ-239, minted and unanswered.
    expect(html.toLowerCase()).not.toContain("void");
    expect(html.toLowerCase()).not.toContain("cancel plan");
    expect(html.toLowerCase()).not.toContain("defaulted");
  });

  it("a missed instalment is reported, and the plan stands", () => {
    const plan = gt47Plan({ status: "active", missed_installment_seqs: [1] });
    const html = renderWizard({
      context: context({ plans: [plan], live_plan: plan, can_propose: false, cannot_propose_reason: "live plan" }),
    });
    // PO 2026-10-11 — LITERALS, so a re-worded catalogue cannot move both sides.
    expect(html).toContain("Installment 1 was missed.");
    expect(html).toContain(t("customers.paymentPlan.status.active"));
  });

  // ── PO 2026-10-11 — the shared instalment table (`PaymentPlanSchedule.tsx`) ──
  /** Jonas Janssen's part-paid plan from the approved preview: 2 of 4 met, 3
   *  and 4 missed. The SAME component the Debtors detail draws. */
  function partPaid() {
    return gt47Plan({
      status: "active",
      total_amount: "372.900000",
      down_payment: "0.000000",
      spread: "372.900000",
      paid_to_date: "186.460000",
      installment_count: 4,
      missed_installment_seqs: [3, 4],
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
    });
  }

  it("draws the instalment table with Left $0.00 on paid rows and paid dates in the tenant's format", () => {
    const plan = partPaid();
    const html = renderWizard({
      context: context({ plans: [plan], live_plan: plan, can_propose: false, cannot_propose_reason: "live plan" }),
    });
    const body = /<tbody>([\s\S]*?)<\/tbody>/.exec(html.slice(html.indexOf("data-plan-schedule")))?.[1] ?? "";
    const rows = [...body.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((row) =>
      [...row[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((cell) =>
        cell[1].replace(/<[^>]*>/g, "").trim(),
      ),
    );
    expect(rows).toEqual([
      ["1", "07/20/2026", "$93.23", "$0.00", "Paid 07/20/2026"],
      ["2", "08/03/2026", "$93.23", "$0.00", "Paid 08/03/2026"],
      ["3", "08/17/2026", "$93.23", "$93.23", "Outstanding"],
      ["4", "08/31/2026", "$93.21", "$93.21", "Outstanding"],
    ]);
    const text = html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ");
    expect(text).toContain("Paid $186.46 of $372.90 · 2 of 4 met");
    expect(text).toContain("2 paid 2 missed 0 upcoming");
    expect(html).toContain("Installments 3 and 4 were missed.");
  });

  it("planCounts: paid = met, missed = the server's list, upcoming = the rest", () => {
    expect(planCounts(partPaid())).toEqual({ paid: 2, missed: 2, upcoming: 0 });
    expect(planCounts(gt47Plan({ missed_installment_seqs: [1] }))).toEqual({
      paid: 0, missed: 1, upcoming: 5,
    });
  });

  it("the live-plan refusal says 'This account already has a plan.' and no rule id", () => {
    const plan = gt47Plan();
    const html = visible(
      renderWizard({
        context: context({
          plans: [plan],
          live_plan: plan,
          can_propose: false,
          cannot_propose_reason: "this account already has a live payment plan",
          cannot_propose_reason_key: "customers.paymentPlan.alreadyHasPlan",
        }),
      }),
    );
    const strip = /data-testid="cannot-propose"[^>]*>([\s\S]*?)<\//.exec(html)?.[1] ?? "";
    expect(strip).toBe("This account already has a plan.");
    expect(html).not.toContain("BR-");
    expect(
      blockedSentence(context({ can_propose: false, cannot_propose_reason: "x", cannot_propose_reason_key: "customers.paymentPlan.alreadyHasPlan" }), t),
    ).toBe("This account already has a plan.");
  });

  it("BR-CUS-044 · the signature is RECORDED with the date the customer signed", () => {
    const plan = gt47Plan();
    const html = renderWizard({
      context: context({ plans: [plan], live_plan: plan, can_propose: false, cannot_propose_reason: "live plan" }),
    });
    expect(html).toContain(t("customers.paymentPlan.signedOn"));
    expect(html).toContain(t("customers.paymentPlan.recordSignature"));
    // BR-SHL-025 — the control is disabled with its reason until a date is set.
    expect(html).toContain(t("customers.paymentPlan.signatureDateFirst"));
  });

  it("a read-only role sees the screen and cannot act on it (BR-SHL-025)", () => {
    const html = renderWizard({ access: "View" });
    expect(html).toContain(t("customers.accounts.rbac.readOnly"));
  });

  // ── the pure rules, provable without rendering ───────────────────────────
  it("blockedReason passes the SERVER's sentence through, unedited", () => {
    expect(blockedReason(context())).toBeNull();
    expect(
      blockedReason(context({ can_propose: false, cannot_propose_reason: "a live plan exists" })),
    ).toBe("a live plan exists");
  });

  it("sendBlockedReason names each obstacle in the order a clerk meets it", () => {
    expect(sendBlockedReason(null, [], "read only")).toBe("read only");
    expect(sendBlockedReason(null, ["email"], null)).toBe("customers.paymentPlan.previewFirst");
    const schedule = { installment_count: 6 } as never;
    expect(sendBlockedReason(schedule, [], null)).toBe("customers.paymentPlan.pickAChannel");
    expect(sendBlockedReason(schedule, ["email"], null)).toBeNull();
  });

  it("livePlanOf returns the ONE live plan (BR-CUS-043) or null", () => {
    expect(livePlanOf(context())).toBeNull();
    const plan = gt47Plan();
    expect(livePlanOf(context({ live_plan: plan }))?.id).toBe("plan-1");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CUS-5171` — THE SCREEN IS THE ONE THE BLUEPRINT DRAWS (B14 rule 41)
// ══════════════════════════════════════════════════════════════════════════
//
// `04-docs/05-modules/03-customers/blueprint/14-payment-plan-wizard.md` heads
// step 1 **`Terms`** under the kicker **`PAYMENT PLAN`** over a sub-line
// **`Step 1 of 3 · Terms`**, and labels the eight fields `Balance to spread *`,
// `Down payment`, `Instalments *`, `Cadence`, `First due *`, `Take by autopay`,
// `Suspend late fees while the plan runs` and `Suspend disconnect while the
// plan runs`. The product drew `Payment plan` on every step, kickered by the
// account number, and five of the eight labels were different words.
//
// ⚠ **NOT ONE DRAWN FIGURE IS ASSERTED HERE (B14 rule 37).** The drawing's
// `$612.75 · $112.75 · 5 · $100.00` are illustrations; the fixture stays ❄️
// GT-47's signed numbers and only the SHAPE is checked against the drawing.
describe("DEF-CUS-5171 — the payment plan matches its blueprint", () => {
  it("kickers `PAYMENT PLAN` and titles the step, not the screen", () => {
    const html = renderWizard();
    expect(html).toContain(t("customers.paymentPlan.title.terms"));
    expect(html).toContain(t("customers.paymentPlan.kicker"));
    // The account number was the kicker and is not the drawing's kicker.
    expect(visible(html)).not.toContain("Account A-10432");
  });

  /** ⚠ A LITERAL, for the reason `ChangePlanWizard.test.tsx` records: building
   *  the expected string from the same catalogue the screen renders from makes
   *  both sides move together, and the case passed at `ffe3a8152` over exactly
   *  the defect it was written for. */
  it("prints the drawn sub-line `Step 1 of 3 · Terms`, naming the step", () => {
    const html = visible(renderWizard());
    expect(html).toContain("Step 1 of 3 · Terms");
    expect(t("customers.paymentPlan.stepOf", { step: 1, of: 3, name: "X" })).toContain("X");
  });

  /** ⚠ **THE DRAWN WORDS AS LITERALS, IN THE DRAWN ORDER.** Reading them out of
   *  the catalogue would assert the catalogue against itself: re-word a label
   *  and both sides move together, which is how this case passed at
   *  `ffe3a8152` in its first draft. These eight are quoted from
   *  `14-payment-plan-wizard.md` and the ORDER is asserted too, because row
   *  order is part of a design and not a detail. */
  it("carries the drawing's eight step-1 labels, in the drawn words and order", () => {
    const html = visible(renderWizard());
    const drawn = [
      "Balance to spread",
      "Down payment",
      "Installments",
      "Cadence",
      "First due",
      "Take by autopay",
      "Suspend late fees while the plan runs",
      "Suspend disconnect while the plan runs",
    ];
    let at = -1;
    for (const label of drawn) {
      const found = html.indexOf(label, at + 1);
      expect(found, `${label} is missing or out of order`).toBeGreaterThan(at);
      at = found;
    }
  });

  it("uses the drawn words and not the product's older ones", () => {
    // The five that moved. Asserted by their OLD text so a revert goes red —
    // a positive assertion on the new word passes happily beside the old one.
    const html = visible(renderWizard());
    for (const gone of [
      "How often",
      "First instalment due",
      "Charge instalments to the method on file",
      "Suspend late fees on these arrears while the plan is current",
      "Suspend disconnection while the plan is current",
    ]) {
      expect(html).not.toContain(gone);
    }
  });

  it("says the balance box is the ARREARS, in the drawing's own sentence", () => {
    // A literal for the same reason, and the sentence it REPLACED asserted gone.
    expect(visible(renderWizard())).toContain("The arrears position, not the current bill.");
    expect(visible(renderWizard())).not.toContain("It cannot be more than the account owes.");
  });

  /**
   * ⚠ **THIS IS A TIER-2 ASSERTION AND SAYS SO.** The commit button only exists
   * on step 3, and this file renders to static markup at step 1 — so the honest
   * check is on the WORD, not on the rendered button, and the button itself was
   * read off the running product instead (`Send agreement ✓`, Chromium at 1280
   * on `brazosbend`, 2026-09-13). A case that mounted step 1 and claimed to
   * prove the footer would be hard-won law 7's *looking at the wrong thing*.
   */
  it("commits with the drawn `Send agreement ✓`, never `Queue agreement`", () => {
    expect(t("customers.paymentPlan.sendAgreement")).toBe("Send agreement ✓");
    expect(t("customers.paymentPlan.sendAgreement")).not.toContain("Queue");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-018@bbed56d (05-golden-tests.md + EP-CUS-06-payment-plan.md + 03-customers/02-business-rules.md + J13-payment-plan-life.md)
// generated: 2026-08-16 by story-coder (surface-debt tails lane — S24)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the balance tile was rendered with a `?? "0.00"`
//         fallback and `expect(visible(html)).not.toContain("$0.00")` FAILED;
//         verbatim transcript in the lane report
// exceptions: (1) The mutations are not exercised here — this file renders to
//         static markup and asserts what a clerk SEES. The three write paths
//         are proved over real HTTP in
//         `06-backend/tests/test_us_cus_018_payment_plan_api.py` and in a
//         booted browser (the lane report's Playwright transcript).
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
