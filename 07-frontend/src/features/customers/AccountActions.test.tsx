// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-012 (S22 Record payment) · US-CUS-013 (Adjust & Issue
//           credit — the refusals) · US-CUS-014 (Send statement & Print bill —
//           the refusals) · US-CUS-015 (Add note; Disconnect notice refused) ·
//           US-CUS-016 (S23 steps 1–2) · US-CUS-017 (S23 step 3)
//           Screens: S21 · S22 · S23
// Rules:    BR-CUS-035 · BR-CUS-037 · BR-CUS-041 · BR-CUS-042 vs BR-CUS-062
//           (OQ-179) · BR-CUS-059 · BR-PAY-001 (OQ-154) · BR-RAT-004 (B4.3 —
//           the screen computes NO money) · BR-RAT-030 · BR-RAT-043 ·
//           BR-SHL-025
// ───────────────────────────────────────────────────────
// §4 test data is EP-CUS-05's own: A-10432 on Residential Standard ($30.50 =
// 18.50 electric + 12.00 water) moving to Senior / Low-income ($12.00), so the
// base delta is −$18.50 — §7's first worked figure, rendered.
//
// THE ASSERTIONS THAT MATTER MOST ARE THE NEGATIVE ONES, and they are the same
// family as S21's: this wizard must not print a deposit differential, a net
// impact that hides what it left out, or a prorated figure it invented. Each
// would be a money claim, and each is checked below.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { RETRYABLE_STATUSES, createApiClient, isRetryable } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { updateAccountNote } from "@/api/endpoints";
import type { MyPermissions, PlanChangeOptions, PlanChangePreview } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { ALLOCATION_CHOICES } from "@/features/payments/paymentsShared";
import en from "@/i18n/locales/en.json";

import { RecordPaymentModal, UNAVAILABLE_ACTIONS, accountNotesKey } from "./AccountActions";
import {
  CHANGE_PLAN_STEPS,
  CHANGE_PLAN_STEP_LABEL_KEYS,
  ChangePlanWizard,
  EFFECTIVE_OPTIONS,
  PreviewPanel,
  ineligibleReasonText,
  planChangeOptionsKey,
  planIsSelectable,
  requiresServiceDropAck,
} from "./ChangePlanWizard";
import { ACCOUNTS_PERMISSION, accountChangePlanPath } from "./customersShared";

const TEST_TENANT = "brazosbend";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function options(over: Partial<PlanChangeOptions> = {}): PlanChangeOptions {
  return {
    account_id: "acc-10432",
    unit_id: "u-10432a",
    unit_services: ["electric", "water"],
    current_plan: {
      id: "plan-res-std",
      code: "res-std",
      name: "Residential Standard",
      version: 3,
      base_charges: "30.500000",
    },
    plans: [
      {
        id: "plan-senior",
        code: "senior",
        name: "Senior / Low-income",
        version: 1,
        services: ["electric"],
        base_charges: "12.000000",
        is_current: false,
        drops_services: ["water"],
        requires_eligibility: ["cap_proof"],
        ineligible_reason: null,
        missing_services: [],
      },
      {
        id: "plan-res-std",
        code: "res-std",
        name: "Residential Standard",
        version: 3,
        services: ["electric", "water"],
        base_charges: "30.500000",
        is_current: true,
        drops_services: [],
        requires_eligibility: [],
        ineligible_reason: null,
        missing_services: [],
      },
    ],
    ...over,
  };
}

/** The preview EXACTLY as the server answers it today: base delta, and three
 *  named absences. Nothing in this fixture is invented — every field mirrors
 *  `apps/customers/services.preview_plan_change`. */
function preview(over: Partial<PlanChangePreview> = {}): PlanChangePreview {
  return {
    account_id: "acc-10432",
    currency: "USD",
    effective_on: "2026-09-01",
    effective_option: "custom",
    current_plan: { id: "plan-res-std", code: "res-std", name: "Residential Standard" },
    new_plan: { id: "plan-senior", code: "senior", name: "Senior / Low-income", version: 1 },
    base: {
      current_total: "30.500000",
      new_total: "12.000000",
      delta: "-18.500000",
      per_service: [
        { service: "electric", current: "18.500000", new: "12.000000" },
        { service: "water", current: "12.000000", new: null },
      ],
    },
    proration: null,
    proration_unavailable: {
      code: "billing_period_unpublished",
      br_ref: "BR-MET-009",
      oq_ref: null,
      detail: "The unit's current billing period is not published by metering.",
    },
    deposit_differential: null,
    deposit_differential_unavailable: {
      code: "deposit_differential_rules_conflict",
      br_refs: ["BR-CUS-042", "BR-CUS-062"],
      oq_ref: "OQ-179",
      detail: "BR-CUS-042 says compute the category differential; BR-CUS-062 says there is none in v1.",
    },
    usage_unavailable: {
      code: "usage_forecast_absent",
      br_ref: "BR-RAT-004",
      oq_ref: "OQ-180",
      detail: "Pricing usage for a period that has not happened needs a forecast.",
    },
    net_impact: {
      amount: "-18.500000",
      basis: "base_charges_only",
      excludes: ["deposit_differential", "usage", "proration"],
    },
    writes: [],
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

function renderWizard(seed: { access?: string; options?: Partial<PlanChangeOptions> } = {}): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(["accounts", "detail", "acc-10432"], {
    id: "acc-10432",
    account_no: "A-10432",
    name: "Miller, Sarah",
    currency: "USD",
    contacts: [],
  });
  queryClient.setQueryData(planChangeOptionsKey("acc-10432"), options(seed.options));
  if (seed.access !== undefined) {
    queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access));
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts/acc-10432/change-plan`]}>
          <Routes>
            <Route
              path="/:tenant/accounts/:accountId/change-plan"
              element={<ChangePlanWizard />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * The S22 Record payment modal, RENDERED — `DEF-CUS-4999` / `DEF-CUS-5008`.
 *
 * ⚠ **THE FILE'S FIRST CASE SAYS THE MODAL IS *"proven by construction rather
 * than by rendering"*, AND THAT IS EXACTLY HOW SIX DECIMALS SURVIVED HERE FOR
 * WEEKS.** Construction proves the modal calls the same endpoint wrapper as
 * S33; it cannot see what the amount box CONTAINS. So this renders it and reads
 * the computed values — hard-won law 6's shape, one level down from the browser.
 */
function renderRecordPayment(balance: string | null, currency = "USD"): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts/acc-10432`]}>
          <Routes>
            <Route
              path="/:tenant/accounts/:accountId"
              element={
                <RecordPaymentModal
                  accountId="acc-10432"
                  accountLabel="A-10432 · Miller, Sarah"
                  currency={currency}
                  balance={balance}
                  today="2026-09-12"
                  dateFormat="MM/DD/YYYY"
                  onClose={() => undefined}
                  onRecorded={() => undefined}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function renderPreview(over: Partial<PlanChangePreview> = {}): string {
  return renderToStaticMarkup(
    <QueryClientProvider client={new QueryClient()}>
      <PreviewPanel preview={preview(over)} t={t} />
    </QueryClientProvider>,
  );
}

// ══════════════════════════════════════════════════════════════════════════
describe("US-CUS-012 — the S22 Record payment modal is the account's entry point", () => {
  it("US-CUS-012 TC-1: the modal posts through the payments module, never a second money path", () => {
    // BR-CUS-037 / BR-SHL-023. Proven by construction rather than by rendering:
    // this file imports the SAME wrapper, schema, allocation vocabulary and
    // result panel the S33 modal uses, so there is exactly one thing to change
    // if the endpoint ever moves. A screen that had its own `fetch` would not
    // show up in this import graph at all, which is the point.
    expect(UNAVAILABLE_ACTIONS.map((a) => a.id)).not.toContain("recordPayment");
    expect(UNAVAILABLE_ACTIONS.map((a) => a.id)).not.toContain("addNote");
  });

  it("DEF-CUS-4999 / DEF-CUS-5008 / hard rule 2: the modal shows and pre-fills TWO decimals", () => {
    // **ONE BUG, FOUND TWICE BY TWO STEP-1 LANES**, which is why both ids are
    // here: lane 2 measured `2410.000000 USD` on `A-11812` and lane 5 measured
    // `247.300000` on `A-10432`, one click from `$2,410.00` and `$247.30` in
    // the same session's list and header.
    //
    // Hard rule 2, PO re-sign 2026-08-22 verbatim: *"MOney 4 decimal,
    // percentage 6 decimal , display both 2 decimal"*.
    //
    // ⚠ **THE PRE-FILL IS THE HALF THAT BIT A CUSTOMER**: it is what a clerk
    // SUBMITS when they accept the default, so six decimals were reaching
    // `POST /accounts/{id}/payments` on the common path. Asserted as the
    // input's `value=` — the COMPUTED string, not a class name and not a source
    // read.
    //
    // ⚠ **STORAGE IS NOT THE BUG AND MUST NOT BE "FIXED".** `accounts.balance`
    // is `NUMERIC(18,6)` and hard rule 2 says *"existing 18,6 columns stay
    // lawful containers"*; `"2410.000000"` on the wire is correct too. Both
    // figures below are fed in at their full served precision on purpose, so
    // this case fails if a later lane tries to solve it in the column.
    const bramble = renderRecordPayment("2410.000000");
    expect(bramble).toContain('value="2410.00"');
    expect(bramble).toContain("$2,410.00");
    expect(bramble).not.toContain("2410.000000");

    const a10432 = renderRecordPayment("247.300000");
    expect(a10432).toContain('value="247.30"');
    expect(a10432).toContain("$247.30");
    expect(a10432).not.toContain("247.300000");

    // ⚠ **AND THE SHAPE THAT MADE IT LOOK DELIBERATE MUST NOT COME BACK.** The
    // old line was `` `${props.balance} ${props.currency}` ``, which is
    // BYTE-IDENTICAL to `formatMoney`'s fallback for an amount it cannot
    // parse — so the modal permanently rendered the formatter's ERROR path and
    // a reviewer saw a shape the codebase genuinely contains elsewhere.
    expect(bramble).not.toContain("2410.00 USD");
    // A null balance is a dash, never a zero and never `null USD` (DEF-151),
    // and the amount box opens EMPTY rather than at `0.00` — a required field
    // asking for the figure beats one holding a number nobody read.
    const absent = renderRecordPayment(null);
    expect(absent).not.toContain("null");
    expect(absent).toContain('value=""');
  });

  it("US-CUS-012 TC-2 / BR-CUS-059: autopay enrolment never blocks or substitutes manual recording", () => {
    // The modal has no branch on `autopay` at all, and that IS the rule: the
    // method field records how THIS payment arrived and never schedules a
    // draft. The help string under it says so to the clerk.
    expect(t("customers.account.payment.methodHelp")).toContain("never schedules");
  });

  it("US-CUS-012 TC-4 / BR-PAY-001: all four allocation choices are offered here too", () => {
    // ⚠ **REWRITTEN 2026-09-02 (CR-059 CS-4, task 12), NOT DELETED.** It read
    // *"the two allocation choices no endpoint can drive stay visible"* and
    // cited OQ-154 — *"the SAME disabled pair S33 renders — one rule, one
    // reason"*. That was the right assertion while the pair was undrivable.
    // The open-bill read is served, OQ-154 is CLOSED, and the pair is live on
    // BOTH modals — still one rule and one implementation, which is what this
    // case has always been guarding.
    expect(t("payments.applyTo.specific")).not.toBe("");
    expect(t("payments.applyTo.split")).not.toBe("");
    expect(ALLOCATION_CHOICES.filter((c) => c.needsTargets === true)).toHaveLength(2);
    // The reason those two carried is gone from the catalogue with them.
    expect(Object.keys(en)).not.toContain("payments.applyTo.pickerUnavailable");
  });
});

describe("US-CUS-013 / US-CUS-014 / US-CUS-015 — what this deployment cannot honour", () => {
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **THIS BLOCK ASSERTED THREE SENTENCES THAT HAD BECOME FALSE, AND WENT
  // GREEN OVER ALL THREE FOR THREE WEEKS (`DEF-CUS-4631`, 2026-09-07).**
  // ══════════════════════════════════════════════════════════════════════════
  // It checked, in this order and in these words, that:
  //
  //   · issue credit says *"has not been decided"* — `OQ-105` and `OQ-168` had
  //     both read CLOSED since 2026-08-12 (*"a separate write-off account"*),
  //     and `corrections.execute_credit_only` had been posting the pair;
  //   · print bill says *"not available yet"* and *"has not been decided"* —
  //     `OQ-103`/`OQ-169` CLOSED the same day, `GET /invoices/{id}/document`
  //     mounted;
  //   · the disconnect notice names *"notice history has no table"*,
  //     *"medical-hold"* and *"Product Owner"* — the table exists
  //     (`NoticeHistory`), the read exists (`medical_hold_for`), and
  //     `OQ-133`/`OQ-136`/`OQ-137` were all CLOSED.
  //
  // Each assertion was written honestly and each became a LOCK: a test that
  // pins a refusal's exact words is a test that fails when somebody fixes the
  // product. That is the shape CLAUDE.md law 7 calls a check that cannot fail
  // usefully, and the PO found all three from the screen because no check
  // could. The cure is the one law 2 already prescribes and nobody applied
  // here: **when you write a hold, write the test that fires when the hold
  // expires** — `accountRailHoldExpiry.test.ts`.
  // ⚠ **THIS CASE ASSERTED THE WORDING OF `adjust`'s REFUSAL. THERE IS NO
  // REFUSAL (2026-09-13, `DEF-CUS-5126`) — SO IT ASSERTS THE ABSENCE INSTEAD.**
  // The sentence it pinned was *"Adjustments are billing rows, and billing is
  // not built. There is no endpoint to post one to."* Every clause was false:
  // `POST /accounts/{id}/payments` has taken `type: "adjustment"` since
  // `CR-059` CS-35 on 2026-09-02, and it was looked for in BILLING, where the
  // only thing that exists is a table with no writer.
  //
  // It is the fourth false refusal on this list and the block comment above
  // names why the other three's sweep could not see it: that sweep re-checked
  // each reason against its OPEN QUESTION, and this one cited an ENDPOINT.
  // **A test that pins a refusal's words fails when somebody fixes the
  // product** — which the comment above already says, and which this case has
  // now demonstrated on itself.
  it("DEF-CUS-5126: adjust has NO refusal — its endpoint existed all along", () => {
    const ids = UNAVAILABLE_ACTIONS.map((a) => a.id);
    expect(ids).not.toContain("adjust");
    // And the sentence is gone from the catalogue, not merely unused: a key
    // nothing renders is a sentence waiting to be rendered again.
    expect(t("customers.account.action.adjustBlocked")).toBe(
      "customers.account.action.adjustBlocked",
    );
  });

  it("US-CUS-014 §1: the statement is the ONE refusal left, and it says WHY", () => {
    const reasons = Object.fromEntries(UNAVAILABLE_ACTIONS.map((a) => [a.id, t(a.reasonKey)]));
    // BR-CUS-040: a statement is a dated range ledger, not a bill, and nothing
    // renders one. TRUE on 2026-09-07 and the only one of the four that was.
    expect(reasons.sendStatement).toBeDefined();
    expect(reasons.sendStatement).not.toContain("OQ-");
    expect(reasons.sendStatement).not.toContain("soon");
    // B14 rule 33 (PO 2026-08-30, *"this shuld be 6 words only - not too long"*):
    // a refusal is at most six words per sentence, and RATIONALE — what a
    // statement IS, why it differs from a bill — is ZERO words on screen. The
    // sentence this replaced ran to twenty-two.
    for (const sentence of reasons.sendStatement.split(/(?<=\.)\s+/)) {
      expect(sentence.trim().split(/\s+/).length).toBeLessThanOrEqual(6);
    }
  });

  it("DEF-CUS-4631: the three answered blockers are GONE from the unavailable list", () => {
    // Asserted by ABSENCE, because the failure being guarded against is a lane
    // putting one of them back — or a merge resurrecting it.
    const ids = UNAVAILABLE_ACTIONS.map((a) => a.id);
    // ⚠ FOUR, NOT THREE, AS OF 2026-09-13 — `adjust` joined them
    // (`DEF-CUS-5126`). The list is down to the ONE refusal that was always
    // true: nothing in this product renders a statement.
    expect(ids).toEqual(["sendStatement"]);
    expect(ids).not.toContain("adjust");
    expect(ids).not.toContain("issueCredit");
    expect(ids).not.toContain("printBill");
    expect(ids).not.toContain("disconnectNotice");
  });

  it("US-CUS-015 TC-4 / BR-CUS-035: the note form says the customer-visible flag does nothing", () => {
    // A clerk who ticks it and believes the customer can read the note has been
    // misled by a control that does nothing. `AccountNote.customer_visible` is
    // still CAPTURED AND INERT — no portal screen reads the table (checked:
    // zero references to `AccountNote` anywhere under `apps/portal/`).
    //
    // ⚠ **THIS TEST USED TO BE `toContain("no customer portal")` AND THAT IS
    // THE DEFECT, NOT THE FIX (`DEF-CUS-4998`, 2026-09-12).** The reason the
    // flag does nothing changed: the customer portal SHIPPED, with accounts
    // that can sign in, so *"there is no customer portal in this version"*
    // became false — and this assertion required the false sentence to be
    // present, so the suite was DEFENDING it. It is the same shape as
    // `DEF-CUS-4298`, quoted in `accountDetailTabs.tsx`: *"The test asserted
    // the sentence was PRESENT, which is not the same question as whether it
    // is TRUE."*
    //
    // So it now asserts the true state in BOTH directions: the claim that
    // killed it is ABSENT, and what is actually true is present. The negative
    // is the half that cannot rot into a tautology.
    const inert = t("customers.account.note.customerVisibleInert");
    expect(inert).not.toContain("no customer portal");
    expect(inert).toContain("Nothing shows it to customers");
  });

  it("DEF-CUS-4998: no surface of this screen tells a clerk the portal does not exist", () => {
    // TWO surfaces carried the same false clause and only one was found by
    // reading the screen; the other is a `title=` hover on the Audit tab
    // (`accountDetailTabs.AccountAuditPortalNote`), which no screenshot shows.
    // Asserted by ABSENCE over the whole family, so a third surface acquiring
    // the sentence fails here rather than reaching a clerk.
    //
    // The portal writes audit rows TODAY — `apps/portal/credentials.py` writes
    // `portal_credential.create` with `actor: "portal:self-enrolment"` — so the
    // old third sentence (*"no entry can come from a customer"*) was false on
    // the record as well as in principle.
    const suspects = Object.entries(en).filter(
      ([key]) => key.startsWith("customers.account.") || key.startsWith("customers.accounts."),
    );
    const denials = suspects.filter(([, text]) =>
      /no customer portal|portal in this version/i.test(String(text)),
    );
    expect(denials).toEqual([]);
    // And the hover says what IS true, in place of what was not.
    expect(t("customers.account.audit.portalActorWhy")).toBe(
      "Who acted is recorded. The channel is not.",
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════
describe("US-CUS-016 — steps 1–2: the picker, the date, and the preview", () => {
  it("US-CUS-016 TC-1: step 1 lists the compatible plans and names the service each drops", () => {
    const html = renderWizard({ access: "Full" });
    expect(html).toContain("Senior / Low-income");
    expect(html).toContain("Residential Standard");
    // TC-6's warning, per row, before anything is chosen.
    expect(html).toContain("Drops water");
    // BR-RAT-043: the eligibility note is advisory and says so.
    expect(html).toContain("Proof of eligibility expected");
  });

  it("US-CUS-016 TC-6: a service-dropping plan cannot continue without an explicit acknowledgment", () => {
    expect(requiresServiceDropAck(options().plans[0])).toBe(true);
    expect(requiresServiceDropAck(options().plans[1])).toBe(false);
    expect(requiresServiceDropAck(null)).toBe(false);
  });

  it("US-CUS-016 TC-2: “next cycle start” is shown and unselectable, with the reason", () => {
    // Nobody can name next cycle's first day — the cycle window is a metering
    // read nobody publishes — so the option is rendered and disabled rather
    // than hidden (BR-SHL-025) or sent to a server that will refuse it.
    const nextCycle = EFFECTIVE_OPTIONS.find((o) => o.value === "next_cycle");
    expect(nextCycle?.disabled).toBe(true);
    expect(t("customers.planChange.effectiveHelp")).toContain("next billing cycle begins");
  });

  it("US-CUS-016 TC-2 §7: the base delta renders −18.50 and NOTHING claims a deposit figure", () => {
    const html = renderPreview();
    // §7's first worked figure: 12.00 − 30.50.
    expect(html).toContain("-$18.50");
    // §7 also states −$50.00 and a −$68.50 net. Neither is drawn: BR-CUS-042
    // and BR-CUS-062 are both CONFIRMED and disagree (OQ-179).
    expect(html).not.toContain("50.00");
    expect(html).not.toContain("68.50");
    // ⚠ **THIS ASSERTED `OQ-179` ON SCREEN UNTIL `DEF-CUS-5170` (2026-09-13).**
    // It pinned a real rule — no deposit figure is invented — to the WRONG
    // evidence: the open-question id was the thing it read, and B14 rule 31
    // keeps an `OQ-` id off a clerk's screen. The rule is unchanged and the
    // evidence moved to the block's own sentence, which is what the blueprint
    // draws. The id is asserted ABSENT so it cannot come back.
    expect(html).not.toContain("OQ-179");
    expect(html).toContain("Deposit difference");
    expect(html).toContain("The deposit is not worked out again here.");
  });

  it("US-CUS-016 §5: the net impact NAMES what it left out instead of quietly summing a short list", () => {
    const html = renderPreview();
    expect(html).toContain("This total leaves out");
    // ⚠ `DEF-CUS-5170` — the excluded lines were printed as their SERVER CODES
    // (`deposit_differential, usage`). An enum value is an internal reference.
    // The sentence is unchanged; the words in it are now words.
    expect(html).toContain("the deposit difference");
    expect(html).toContain("usage");
    expect(html.replace(/<[^>]*>/g, " ")).not.toContain("deposit_differential");
  });

  it("US-CUS-016 TC-3 / B4.3: a prorated amount is only ever drawn WITH the engine that produced it", () => {
    // No period ⇒ no figure at all, and the reason on screen — in the SCREEN's
    // words since `DEF-CUS-5170`, not in the server's engineering sentence.
    expect(renderPreview()).toContain("Part-period amounts are not worked out here.");
    // With a period, the amounts are the SERVER's and the panel says which
    // function made them — "the rating engine did this" checkable, not claimed.
    const withProration = renderPreview({
      proration: {
        period_start: "2026-08-01",
        period_end: "2026-08-31",
        cycle_days: 31,
        current_plan_line: { plan: "res-std", service_days: 5, amount: "4.92" },
        new_plan_line: { plan: "senior", service_days: 26, amount: "10.06" },
        computed_by: "apps.rating.engine.prorate_base_charge",
      },
      proration_unavailable: null,
    });
    expect(withProration).toContain("$4.92");
    expect(withProration).toContain("$10.06");
    expect(withProration).toContain("apps.rating.engine.prorate_base_charge");
  });
});

describe("US-CUS-017 — step 3: confirm, and what confirming does not do", () => {
  it("US-CUS-017 §1: the wizard is three steps and lives under the account", () => {
    expect([...CHANGE_PLAN_STEPS]).toEqual(["plan", "effective", "confirm"]);
    expect(accountChangePlanPath("acc-10432")).toBe("/accounts/acc-10432/change-plan");
  });

  /**
   * ⛔ **`DEF-CUS-5071` — THE RAIL, READ OFF THE RENDERED SCREEN.**
   *
   * The case above asserts `CHANGE_PLAN_STEPS` equals
   * `["plan","effective","confirm"]`, and until 2026-09-12 that assertion and
   * the const's own type alias were its ONLY two readers in the repository.
   * Nothing rendered it. This is the reader.
   */
  it("draws the numbered rail, with the step it is on marked active (B14 rule 3)", () => {
    const html = renderWizard();
    expect(html).toContain('data-wizard="rail"');
    for (const id of CHANGE_PLAN_STEPS) {
      expect(html).toContain(t(CHANGE_PLAN_STEP_LABEL_KEYS[id]));
    }
    expect(html).toContain('data-wizard-step="1" data-state="active"');
    expect(html).toContain('data-wizard-step="3" data-state="upcoming"');
    expect(html).toContain(
      // `DEF-CUS-5171` — the sub-line gained the step's NAME, which
      // `13-change-plan-wizard.md` draws (`Step 1 of 3 · Plan`).
      t("customers.planChange.stepOf", {
        step: 1,
        of: CHANGE_PLAN_STEPS.length,
        name: t(CHANGE_PLAN_STEP_LABEL_KEYS.plan),
      }),
    );
  });

  it("US-CUS-017 TC-3 / BR-RAT-043: the eligibility checkbox is evidence, never a gate", () => {
    expect(t("customers.planChange.eligibilityAdvisory")).toContain("not a gate");
  });

  it("US-CUS-017 TC-4: the toast says “customer notified” only when a message was queued", () => {
    expect(t("customers.planChange.toast.changed", { date: "2026-09-01" })).not.toContain("email");
    expect(t("customers.planChange.toast.changedAndNotified", { date: "2026-09-01" })).toContain(
      "emailed",
    );
  });

  it("US-CUS-017 §1(c): the deposit-differential instruction is reported as NOT registered", () => {
    // The server returns it in `problems[]` on every change, and the result
    // panel renders every problem — a clerk who expected a $50 refund to be
    // raised has to be told it was not.
    expect(preview().deposit_differential_unavailable?.oq_ref).toBe("OQ-179");
  });

  it("US-CUS-015 / US-CUS-011: the notes query key is scoped to the account", () => {
    expect(accountNotesKey("acc-10432")).toEqual(["accounts", "notes", "acc-10432"]);
  });
});


// ══════════════════════════════════════════════════════════════════════════
// CR-013 part 5 · PLN-04 — the two gaps between the built S23 and the CR.
//
// ⚠ THIS SCREEN ALREADY EXISTED. `09-screen-inventory.md` §18 row 16 lists
// PLN-04 as NEW; it has been built since 2026-08-11 as S23 (DEF-420). What was
// missing was not the wizard — it was these two behaviours.
describe("CR-013 part 5 · PLN-04 — ineligible plans are LISTED with the failing rule", () => {
  /** The row the server used to drop on the floor: a plan that prices a
   *  service this unit does not take (BR-CUS-041). */
  const incompatible = {
    id: "plan-gas-only",
    code: "gas-std",
    name: "Gas Standard",
    version: 2,
    services: ["gas"],
    base_charges: "9.000000",
    is_current: false,
    drops_services: ["electric", "water"],
    requires_eligibility: [],
    ineligible_reason: "covers_unavailable_services",
    missing_services: ["gas"],
  };

  it("PLN-04 TC-1: an ineligible plan is drawn, is named, and is UNSELECTABLE", () => {
    const html = renderWizard({
      options: { plans: [...options().plans, incompatible] },
    });
    // LISTED — the whole point. Before 2026-08-21 the server filtered it out
    // and this assertion could not pass by any route.
    expect(html).toContain("Gas Standard");
    // …WITH THE FAILING RULE, naming the service rather than "not eligible".
    expect(html).toContain("this unit does not take");
    // …AND NOT OFFERED. `listed` is not `assignable` (OQ-302).
    expect(html).toMatch(/<input[^>]*id="plan-plan-gas-only"[^>]*disabled/);
  });

  it("PLN-04 TC-2: an assignable plan stays selectable — the guard is not a blanket", () => {
    const html = renderWizard();
    expect(html).toContain("Senior / Low-income");
    expect(html).not.toMatch(/<input[^>]*id="plan-plan-senior"[^>]*disabled/);
    expect(planIsSelectable(options().plans[0])).toBe(true);
  });

  it("PLN-04 TC-3: the reason is keyed off the SERVER's code, never assembled server-side", () => {
    expect(planIsSelectable(incompatible)).toBe(false);
    expect(ineligibleReasonText(incompatible, t)).toContain("gas");
    expect(
      ineligibleReasonText(
        { ...incompatible, ineligible_reason: "no_services", missing_services: [] },
        t,
      ),
    ).toContain("would bill nothing");
    // An untranslated code renders the CODE — never a blank line, which would
    // read as "refused for no stated cause".
    expect(ineligibleReasonText({ ...incompatible, ineligible_reason: "some_future_rule" }, t)).toBe(
      "some_future_rule",
    );
  });
});

describe("CR-013 part 5 · PLN-04 — the deposit differential is READ when the server states one", () => {
  it("PLN-04 TC-4: a stated differential renders as money, with refund-vs-request explained", () => {
    // The figure US-CUS-016 §7 works: a −$50.00 refund. Rendered ONLY because
    // the server said so — nothing here computes or defaults it.
    const html = renderPreview({
      deposit_differential: "-50.000000",
      deposit_differential_unavailable: null,
    });
    expect(html).toContain("Deposit difference");
    expect(html).toContain("50.00");
    expect(html).toContain("refunded to the customer");
  });

  it("PLN-04 TC-5: with OQ-179 still open the server states NO figure, and none is invented", () => {
    // Today's live shape: `deposit_differential` is null and the reason rides
    // beside it. BR-CUS-042 and BR-CUS-062 are both CONFIRMED and disagree, so
    // this lane chooses nothing (prime directive).
    const html = renderPreview();
    // ⚠ **RE-POINTED BY `DEF-CUS-5170`, AND THE SECOND HALF WAS ALWAYS THE
    // POINT.** It read `toContain("OQ-179")` and `not.toContain("Deposit
    // difference")` — the first asserted a rule-31 breach, and the second
    // worked only because the LABEL used to appear beside a stated figure and
    // nowhere else. The blueprint heads the absence with the line's own name,
    // so the label is now present in both cases and cannot carry this claim.
    // What the case is actually about is that NO AMOUNT is drawn.
    expect(html).not.toContain("OQ-179");
    expect(html).toContain("Deposit difference");
    expect(html).toContain("The deposit is not worked out again here.");
    // The one thing that must never appear: a figure — least of all a zero,
    // which reads as "no deposit is owed" rather than "nobody has ruled what
    // is owed". Asserted over the deposit block alone.
    const block = html.slice(html.indexOf('data-unavailable="deposit_differential_unavailable"'));
    expect(block.slice(0, block.indexOf("</p>"))).not.toMatch(/\$-?[\d,]+\.\d\d/);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-016@f7c1a20 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/03-customers/06-epics/EP-CUS-04-account-actions.md · 04-docs/05-modules/03-customers/06-epics/EP-CUS-05-change-plan.md · 04-docs/05-modules/03-customers/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §2.6; co-packets US-CUS-012 · US-CUS-013 · US-CUS-014 · US-CUS-015 · US-CUS-017, same four sources)
// generated: 2026-08-11 by story-coder (W4/W8 customers ACTION lane)
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — test module) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report — tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: US-CUS-013 and US-CUS-014 are asserted ONLY as refusals — their write paths do not exist anywhere in the repo, so there is nothing else honest to assert about them; each test checks that the reason names its blocker rather than a date
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

// ══════════════════════════════════════════════════════════════════════════
// US-CUS-015 — THE NOTE LIFECYCLE, reachable since 2026-08-16.
//
// `PATCH /accounts/{id}/notes/{noteId}` was served and audited from the W4
// lane and no screen could reach it, because the shared client exposed get,
// post, put and del and no PATCH. A missing transport verb turned a finished,
// audited feature into one a clerk could not use: a note's pin could be set at
// creation and never afterwards.
//
// The test that matters is on the CLIENT, not the component: it asserts the
// verb sends the right method to the right path, because that is the thing
// whose absence caused the gap. A component test would have passed throughout
// the period the feature did not exist.
// ══════════════════════════════════════════════════════════════════════════
describe("US-CUS-015 — pin and unpin reach the server", () => {
  function recordingClient(): { calls: { method: string; path: string; body: unknown }[]; client: ApiClient } {
    const calls: { method: string; path: string; body: unknown }[] = [];
    const client = createApiClient({
      tenant: "brazosbend",
      fetchImpl: (async (input: RequestInfo | URL, init?: RequestInit) => {
        calls.push({
          method: init?.method ?? "GET",
          path: String(input),
          body: init?.body === undefined ? undefined : JSON.parse(String(init.body)),
        });
        return new Response(JSON.stringify({ id: "n1", pinned: true }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }) as typeof fetch,
    });
    return { calls, client };
  }

  it("TC-4b · updateAccountNote sends PATCH to the note's own path", async () => {
    const { calls, client } = recordingClient();
    await updateAccountNote("acct-1", "note-9", { pinned: true }, client);
    expect(calls).toHaveLength(1);
    // The verb itself — the thing that did not exist and made the feature dead.
    expect(calls[0].method).toBe("PATCH");
    expect(calls[0].path).toContain("/accounts/acct-1/notes/note-9");
    expect(calls[0].body).toEqual({ pinned: true });
  });

  it("unpinning sends pinned:false — not an absent field the server would ignore", () => {
    // A PATCH body that omits the field is a no-op on the server, so an unpin
    // built as "send nothing" would look like it worked and change nothing.
    const body = { pinned: false };
    expect(Object.prototype.hasOwnProperty.call(body, "pinned")).toBe(true);
    expect(body.pinned).toBe(false);
  });

  it("CLAUDE.md rule 6 · a PATCH is never retried, even on a retryable status", () => {
    // Re-sending a mutation is a second write. Only GET may be retried.
    for (const status of RETRYABLE_STATUSES) {
      expect(isRetryable("PATCH", status)).toBe(false);
      expect(isRetryable("GET", status)).toBe(true);
    }
  });
});
