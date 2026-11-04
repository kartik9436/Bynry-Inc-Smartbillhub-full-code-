// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-005 (S20 Move-Out wizard + the BR-CUS-031 handoff) ·
//           US-CUS-007 (the deposit fields inside step 3)
//           Screens: S20
// Rules:    BR-CUS-021 (final reads belong to metering) · BR-CUS-025 (deposit
//           applies to the final bill first; the refund is payments') ·
//           BR-CUS-030 (what a move-out writes, and what it cannot) ·
//           BR-CUS-031 (the final-bill handoff) · BR-CUS-055 (the seeded
//           statuses and their behaviour classes) · BR-CUS-056 (the outgoing
//           account pays the move day) · BR-CUS-057 (deposit interest) ·
//           BR-BIL-004 (issued invoices are immutable) · BR-MET-036 (occupancy
//           is DERIVED) · BR-SHL-018/019 (the shared rail and ONE commit) ·
//           BR-SHL-025 (disabled WITH the reason) · BR-SHL-044 (one header)
// ───────────────────────────────────────────────────────
// §4 test data is A-10432 (Miller, Sarah · U-10432-A), rendered through the
// seeded query cache — no network, ever.
//
// The assertions that matter most are NEGATIVE. This screen must not collect a
// move-out reason, a final reading, a deposit disposition or a refund method,
// because the endpoint refuses all four by name — and it must not print a
// prorated line or a "$184.20 due" total, because billing has no invoices to
// price one from. Each is one line in the defect log's fabricated-value family.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  AccountDetail,
  AccountMoveOutResult,
  FinalBillHandoff,
  MyPermissions,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { accountDetailQueryKey } from "./AccountDetailPage";
import { mailingAddressAnswer } from "./moveOutAccountPanel";
import {
  emptyFieldVisit,
  fieldVisitPayload,
  fieldVisitProblem,
} from "@/features/work/FieldVisitOrders";
import { parkAgeDays } from "@/components/WizardFrame";
import { ShortfallPaths } from "./moveOutTables";
import { unitAssetsQueryKey } from "./UnitAssetsPanel";
import type { UnitAssets } from "./UnitAssetsPanel";

import {
  MOVE_OUT_STEP_COUNT,
  MOVE_OUT_STEP_IDS,
  MoveOutDone,
  MoveOutWizard,
  closeImpactQueryKey,
  finalBillPreviewQueryKey,
  handoffGaps,
  moveOutDateProblem,
  moveOutPayload,
  moveOutStepFromParam,
  ourBlockedReasons,
  readsProgress,
  settleShortfall,
} from "./MoveOutWizard";
import {
  CLOSE_REASONS,
  MONEY_LANDINGS,
  MOVE_OUT_STEPS,
  PATH_ASKS,
  moveOutStoredStep,
  closeImpactPort,
  dayAfter,
  finalBillPreviewPort,
  dunningOnClose,
  flowProgress,
  outgoingMessageDefaults,
  parkStoreBlockedReason,
  paymentPlanOnClose,
  settlementMoneyOf,
  shortfallChoices,
  unitPlanLine,
  vacancyDispositions,
  wizardParkPort,
} from "./moveShared";
import type { CloseImpact, FinalBillPreview } from "./moveShared";
import { clampToSteps } from "./wizardPark";
import {
  ACCOUNTS_PERMISSION,
  accountMoveInPath,
  accountMoveOutPath,
  earliestMoveInDate,
  isOccupyingAccount,
  warningText,
} from "./customersShared";

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…`.
const TEST_TENANT = "brazosbend";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function detail(over: Partial<AccountDetail> = {}): AccountDetail {
  return {
    id: "acc-10432",
    account_no: "A-10432",
    // BR-CUS-068 — `kind` is served on every account payload (regular | master).
    kind: "regular",
    name: "Miller, Sarah",
    unit_id: "u-10432a",
    unit_label: "A",
    premise: "1408 Elm St · A",
    services: ["electric", "water"],
    balance: "120.840000",
    // DEF-127 — the LEDGER's figure and the CHAR(3) it derived for it.
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
    deposit_on_file: "150.000000",
    deposit_received_on: "2024-02-14",
    credit_tier: null,
    tax_exempt: false,
    tax_exempt_ref: null,
    tax_exempt_expires: null,
    bad_address: false,
    nsf_count: 0,
    preferred_language: null,
    custom_data: {},
    contacts: [
      {
        id: "c-1",
        full_name: "Miller, Sarah",
        email: "sarah.miller@example.com",
        phone: "+1 (512) 555-0184",
        dob: "1987-04-12",
        gov_id_last4: "4218",
        is_primary: true,
      },
    ],
    addresses: [],
    service_agreements: [
      {
        id: "sa-1",
        service_point_id: "sp-1",
        service: "electric",
        started_on: "2024-02-14",
        ended_on: null,
      },
    ],
    meters: [
      { id: "ast-4021", asset_no: "M-4021", qualifier: null },
      { id: "ast-4022", asset_no: "M-4022", qualifier: null },
    ],
    plan: null,
    plan_snapshot_unavailable: "BR-CUS-029",
    // DEF-2419 — the plan the UNIT stands on. Null here: these fixtures are
    // about a flow, not about the plan cell, and null is a real state
    // (a unit with no plan) rather than a placeholder.
    unit_plan: null,
    // BR-CUS-054's entity landed 2026-08-11 (US-CUS-019). An account created
    // before it — which is every account in these fixtures — carries no link,
    // and null is the honest value rather than a customer nobody created.
    customer: null,
    ...over,
  };
}

/**
 * The unit's registers, as `GET /units/{id}/assets` serves them (`OQ-394`).
 *
 * ⚠ **`42864.000000` IS THE WIRE, NOT THE SCREEN.** BR-MET-019 stores the
 * register at `NUMERIC(18,6)` and the payload carries it verbatim; the six
 * zeros are storage, and what the PO was shown — and ruled on — is `42,864`.
 * The fixture keeps the wire form on purpose, so the trim is exercised rather
 * than assumed.
 */
function unitAssets(): UnitAssets {
  return {
    unit: {
      id: "u-10432a",
      unit_no: "A",
      label: "88 Pine Vista · A",
      premises_id: "p-10432",
      premise_no: "P-10432",
      premise_address: "88 Pine Vista",
    },
    counts: { total: 2 },
    reading_expected: { served: false, reason: "no reader", tracks: "DEF-495" },
    groups: [
      {
        category: "meters",
        assets: [
          {
            id: "ast-4021",
            asset_no: "M-4021",
            type: "electric_meter",
            type_name: "Electric meter",
            category: "meters",
            qualifier: null,
            service: "electric",
            last_read: {
              read_id: "r-4021",
              read_at: "2026-07-31",
              channel: "total",
              current_value: "42864.000000",
              consumption: "684.000000",
              unit: "kWh",
              current_value_display: "42864 kWh",
            },
          },
          {
            id: "ast-4022",
            asset_no: "M-4022",
            type: "water_meter",
            type_name: "Water meter",
            category: "meters",
            qualifier: null,
            service: "water",
            last_read: null,
          },
        ],
      },
    ],
  };
}

/** `services._final_bill_handoff` verbatim — four elements absent WITH rules. */
function handoff(over: Partial<FinalBillHandoff> = {}): FinalBillHandoff {
  return {
    account_id: "acc-10432",
    account_no: "A-10432",
    unit_id: "u-10432a",
    moved_out_on: "2026-08-14",
    bill_through: "2026-08-14",
    bill_through_br_ref: "BR-CUS-056",
    currency: "USD",
    prior_balance: "120.840000",
    deposit_on_file: "150.000000",
    deposit_received_on: "2024-02-14",
    final_reads: null,
    final_reads_unavailable: "BR-CUS-021",
    plan_snapshot: null,
    plan_snapshot_unavailable: "BR-CUS-029",
    deposit_interest_accrued: null,
    deposit_interest_unavailable: "BR-CUS-057",
    deposit_disposition: null,
    deposit_disposition_unavailable: "BR-CUS-025",
    refund_method: null,
    refund_method_unavailable: "BR-CUS-025",
    persisted: false,
    persistence_unavailable: "BR-CUS-031",
    ...over,
  };
}

/**
 * `services.MOVE_OUT_UNAVAILABLE` (eight) plus the issued-bill check that could
 * not run — the NINE every move-out answers with. Verbatim codes: an unknown
 * one renders its code, and a missing catalog key is a G15 failure, so the list
 * being complete here is what proves the screen shows all of them.
 */
const NINE_WARNINGS = [
  { code: "move_out_date_not_checked_against_issued_bills", br_ref: "BR-BIL-004" },
  { code: "final_bill_not_issued", br_ref: "BR-CUS-031" },
  { code: "final_bill_handoff_not_persisted", br_ref: "BR-CUS-031" },
  { code: "final_reads_not_committed", br_ref: "BR-CUS-021" },
  { code: "deposit_not_settled", br_ref: "BR-CUS-025" },
  { code: "deposit_interest_not_accrued", br_ref: "BR-CUS-057" },
  { code: "close_reason_not_recorded", br_ref: "BR-CUS-030" },
  { code: "dunning_not_stopped", br_ref: "BR-CUS-030" },
  { code: "closeout_documents_not_queued", br_ref: "BR-CUS-030" },
];

function moveOutResult(): AccountMoveOutResult {
  return {
    ...detail({
      status: "closed",
      status_name: "Closed",
      status_behavior_class: "terminal",
      closed_at: "2026-08-14",
    }),
    final_bill_handoff: handoff(),
    warnings: NINE_WARNINGS,
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
  path: string,
  seed: {
    detail?: AccountDetail;
    access?: string;
    assets?: UnitAssets;
    /** DEF-669 — seed the close-impact answer, so a case can assert what the
     *  panels do with the six fields the server does not serve. */
    impact?: CloseImpact;
    /** The final-bill preview (`GET …/final-bill-preview`), seeded the same
     *  way — and through the component's OWN key builder, so a fixture cannot
     *  address a key the screen does not ask for. */
    preview?: FinalBillPreview;
    /** The move-out date the flow is carrying; part of both read keys. */
    movedOutOn?: string;
  } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (seed.detail !== undefined) {
    queryClient.setQueryData(accountDetailQueryKey(seed.detail.id), seed.detail);
    const movedOutOn = seed.movedOutOn ?? "";
    if (seed.preview !== undefined) {
      queryClient.setQueryData(
        finalBillPreviewQueryKey(seed.detail.id, movedOutOn),
        seed.preview,
      );
    }
    if (seed.impact !== undefined) {
      queryClient.setQueryData(
        closeImpactQueryKey(seed.detail.id, seed.preview?.total ?? null, movedOutOn),
        seed.impact,
      );
    }
  }
  if (seed.access !== undefined) {
    queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access));
  }
  // ⚠ **OPT-IN, AND EVERY EXISTING CASE STAYS OPTED OUT.** The case above this
  // one deliberately never stubs `GET /units/{id}/assets`, because that is what
  // proves the capture STATES an unreadable inventory instead of vanishing.
  // Seeding it globally would delete that proof.
  if (seed.assets !== undefined) {
    queryClient.setQueryData(unitAssetsQueryKey(seed.assets.unit.id), seed.assets);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <Routes>
            <Route path="/:tenant/accounts/:accountId/move-out" element={<MoveOutWizard />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function renderDone(): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts/acc-10432/move-out`]}>
      <Routes>
        <Route
          path="/:tenant/accounts/:accountId/move-out"
          element={
            <MoveOutDone
              result={moveOutResult()}
              t={t}
              timeZone="UTC"
              dateFormat="MM/DD/YYYY"
            />
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

/** The document with every `title=` attribute removed — the reasons NAME the
 * things they refuse, and a whole-document `not.toContain` would read that
 * explanation as the defect it exists to prevent. */
function visible(html: string): string {
  return html.replace(/ title="[^"]*"/g, "");
}

/** ⚠ **HOISTED TO MODULE SCOPE 2026-09-19.** It lived inside the impact
 *  `describe`, so the block that proves the 2026-09-19 build could not reach
 *  it — and a second copy of a contract fixture is how two suites come to
 *  disagree about what the server sends. One base, every block. */
const IMPACT_BASE: CloseImpact = {
  landing: "settled",
  open_sub_accounts: 0,
  units_occupied_after: null,
  owner_on_record: null,
  owner_is_free_text: null,
  common_area_account_no: null,
  unit_falls_to: null,
  vacant_base_charge: null,
  vacant_base_charges: null,
  payment_plan: null,
  money: null,
  shortfall_paths: [],
  refund_methods: [],
  gaps: [],
  step_4_live: null,
};

describe("US-CUS-005 — the S20 Move-out wizard", () => {
  it("PO 2026-09-24: FOUR steps render on the SHARED wizard frame, from ONE declared list", () => {
    // ⚠ **THIS CASE PINNED SIX UNTIL 2026-09-24 AND THE SUPERSESSION IS NAMED.**
    // `BR-SHL-046` (PO 2026-08-24, verbatim *"6 steps"*) closed `DEF-648`,
    // where the wizard shipped four while its own header said six. The PO has
    // now ruled the SHAPE four — *"i okay with these steps"* — merging old 3+4
    // (one subtraction; *Short by* is its bottom line) and old 5+6 (old step 5
    // had no input anywhere on it). **The NUMBER in BR-SHL-046 moves; its
    // MECHANISM does not**, and the mechanism is what the rest of this case
    // asserts.
    //
    // ⚠ **THIS FOUR IS NOT `DEF-648`'s FOUR.** That one was a DRAWN count that
    // never matched the wizard. This one IS the wizard's declared list.
    expect([...MOVE_OUT_STEP_IDS]).toEqual(["account", "date", "settlement", "review"]);
    expect(MOVE_OUT_STEP_COUNT).toBe(4);
    // The DURABLE half of the ruling: the wizard's count and the list's segment
    // count are the SAME declared list, not two literals that agree today.
    expect(MOVE_OUT_STEP_COUNT).toBe(MOVE_OUT_STEPS.length);
    expect(MOVE_OUT_STEP_IDS).toEqual(MOVE_OUT_STEPS.map((step) => step.id));
    const html = renderWizard(accountMoveOutPath("acc-10432"), {
      detail: detail(),
      access: "Full",
    });
    // The frame's own rail and action row (B13 §1) — this screen draws neither.
    expect(html).toContain('data-wizard="frame"');
    expect(html).toContain('data-wizard="rail"');
    expect((html.match(/data-wizard-step=/g) ?? []).length).toBe(4);
    expect(html).toContain("Find account");
    expect(html).toContain("Date &amp; reads");
    expect(html).toContain("Bill &amp; deposit");
    expect(html).toContain("Review &amp; close");
    // ⛔ The two steps that were ABSORBED must not still be drawn as segments.
    expect(html).not.toContain("The shortfall");
    expect(html).not.toContain("What happens next");
    // The step line a row reopens against — the same index the Move-outs tab's
    // STEP column must address. `4 of 4` beside a six-step rail is DEF-648.
    expect(html).toContain("Step 1 of 4");
  });

  it("PO 2026-09-24: NO move-out step is conditional any more — the shortfall is ABSORBED, not skipped", () => {
    // ⚠ The six-step shape rendered `4 · Shortfall · skipped`, greyed, and kept
    // it in the count because the number is an INDEX (BR-SHL-046). There is no
    // longer a segment standing for it: it is a SECTION of step 3, shown only
    // when the subtraction lands `short`. So the property that used to be
    // asserted — *exactly one conditional step* — inverts.
    expect(MOVE_OUT_STEPS.filter((step) => step.conditional === true)).toHaveLength(0);
    expect(flowProgress(MOVE_OUT_STEPS, 3)).toEqual({ step: 3, of: 4 });
    expect(flowProgress(MOVE_OUT_STEPS, 99)).toEqual({ step: 4, of: 4 });
  });

  it("PO 2026-09-24: a step PARKED under the six-step shape opens where it belongs, and a clamp would not", () => {
    // ⚠⚠ **THE ONE ROW THAT FAILS IN THE UNSAFE DIRECTION IS OLD 4.** A clamp
    // holds a stored step inside `[1, 4]`, which is right BY LUCK on five of
    // the six numbers a move-out draft can carry. Old 4 — *The shortfall* — is
    // already in range, so a clamp passes it straight through onto new 4,
    // *Review & close*: a clerk resumes PAST the money step, at the confirm.
    // Landing a clerk EARLY on a flow that GREW is safe; this flow SHRANK.
    expect(moveOutStoredStep(1)).toBe(1);
    expect(moveOutStoredStep(2)).toBe(2);
    expect(moveOutStoredStep(3)).toBe(3);
    expect(moveOutStoredStep(4)).toBe(3); // ⛔ a clamp gives 4 — Review & close
    expect(moveOutStoredStep(5)).toBe(4);
    expect(moveOutStoredStep(6)).toBe(4);
    // ⚠ **THE CLAMP IS NOT REPLACED AND MUST NOT BE.** A number this map does
    // not know is handed through untouched, and `clampToSteps` still catches
    // it — a corrupted row, a hand-edited `?step=`, a flow that grows later.
    expect(moveOutStoredStep(7)).toBe(7);
    expect(clampToSteps(moveOutStoredStep(7), MOVE_OUT_STEPS)).toBe(4);
    expect(clampToSteps(moveOutStoredStep(0), MOVE_OUT_STEPS)).toBe(1);
    expect(clampToSteps(moveOutStoredStep(1.5), MOVE_OUT_STEPS)).toBe(1);
    // And the REASON old 4 matters: the two steps are not interchangeable.
    expect(MOVE_OUT_STEPS[moveOutStoredStep(4) - 1].id).toBe("settlement");
    expect(MOVE_OUT_STEPS[3].id).toBe("review");
  });

  it("US-CUS-005 §1 / BR-SHL-044: the shared page header carries the prototype's kicker and H1", () => {
    const html = renderWizard(accountMoveOutPath("acc-10432"), {
      detail: detail(),
      access: "Full",
    });
    expect(html).toContain("page-header");
    expect(html).toContain("Move-out");
    expect(html).toMatch(/<h1[^>]*>Close an account and free the unit\.<\/h1>/);
    // Back to the account this move-out acts on, not to a generic list.
    expect(html).toContain("Miller, Sarah");
    expect(html).not.toContain("cus-head");
  });

  it("US-CUS-005 TC-1: step 1 confirms the account and offers NO search of its own", () => {
    const html = renderWizard(accountMoveOutPath("acc-10432"), {
      detail: detail(),
      access: "Full",
    });
    // ⚠ **THE PANEL'S HEADING IS THE DRAWING'S, AND IT APPEARS ONCE.**
    // `01-find-account.png` heads this panel *This account*; the step's own
    // question (*"Which account is moving out?"*) was printed as well, so a
    // clerk read two headings one line apart. The browser walk showed it and no
    // unit case could, because both were well-formed keys resolving in eleven
    // languages — **so the count is asserted, not just the presence.**
    expect(html).toContain("This account");
    expect(html.split("This account").length - 1).toBe(1);
    expect(html).not.toContain("Which account is moving out?");
    expect(html).toContain("A-10432");
    expect(html).toContain("1408 Elm St · A");
    // The endpoint is account-scoped, so a second picker here could choose an
    // account this page cannot act on.
    //
    // ⚠ **THE ASSERTION IS ON THE CONTROLS, NOT ON A SENTENCE —
    // `DEF-CUS-6481`.** This used to assert the 37-word hint *"…there is no
    // search on this step"*, which is RATIONALE (B14 rule 33 puts *why a
    // control is absent* at ZERO words on screen) and is deleted. What this
    // case is actually about is that NO PICKER IS DRAWN, which is what the
    // three `not.toContain`s below check — the hint's own absence included, so
    // re-adding the paragraph turns this red rather than passing quietly.
    expect(html).not.toContain("there is no search on this step");
    expect(html).not.toContain('id="account_search"');
    expect(html).not.toContain('id="mvo_account_q"');
    expect(html).not.toContain("Miller / 10432 / M-4021");
  });

  it("US-CUS-005 / BR-CUS-030: a non-occupant is refused BEFORE the commit, not by it", () => {
    expect(isOccupyingAccount(detail())).toBe(true);
    expect(isOccupyingAccount(detail({ status_behavior_class: "non_billable" }))).toBe(false);
    expect(isOccupyingAccount(detail({ status_behavior_class: "terminal" }))).toBe(false);
    expect(isOccupyingAccount(detail({ status_behavior_class: "billable_base_only" }))).toBe(true);

    const closed = renderWizard(accountMoveOutPath("acc-10432"), {
      detail: detail({
        status: "closed",
        status_name: "Closed",
        status_behavior_class: "terminal",
        closed_at: "2026-08-14",
      }),
      access: "Full",
    });
    expect(closed).toContain("This account does not hold its unit");
  });

  // ══════════════════════════════════════════════════════════════════════
  // BR-CUS-1082 — A PARENT WITH OPEN CHILDREN IS WARNED ON STEP 1
  // ══════════════════════════════════════════════════════════════════════
  // ⚠ **THESE TWO CASES ASSERTED A REFUSAL UNTIL 2026-09-20 AND ARE REWRITTEN
  // RATHER THAN DELETED.** PO ruling closing `OQ-CUS-12515` on option (b),
  // verbatim: *"option B - give a warning and allow it; if owner has sold the
  // property to new owner then we are transfering all libalities and ownership
  // to new owner"*. Where a property is SOLD the act is a TRANSFER, which
  // carries the tenants untouched, so the case the refusal protected against
  // already has its own flow. **The contract these cases guard is still real
  // and has simply moved: a clerk is TOLD, and may continue.**

  it("BR-CUS-1082: a master with open children is WARNED on step 1 — a fact, with no instruction", () => {
    const html = renderWizard(accountMoveOutPath("acc-10432"), {
      detail: detail(),
      access: "Full",
      impact: { ...IMPACT_BASE, open_sub_accounts: 2 },
    });
    // The FACT, and the COUNT the settlement measured — `2`, not a vague
    // "some". B14 rule 33: a fact of five words.
    expect(visible(html)).toContain("2 sub-accounts are still open");
    // ⚠ **THE INSTRUCTION IS GONE, AND ITS ABSENCE IS THE RULING.** It read
    // *"Close or reassign them first."* — an instruction that stopped being
    // true the moment the clerk was allowed to continue. Asserted as an
    // absence, because a sentence nobody removed from the catalogues would
    // still render here and every other assertion would still pass.
    expect(visible(html)).not.toContain("Close or reassign");
    // ⚠ **A WARNING IN THE DOM, NOT ONLY IN THE COLOUR.** It was a
    // `RefusalStrip` — `data-refusal`, `role="alert"`. A warning left in that
    // wrapper still announces itself as a refusal to a screen reader whatever
    // the words say, so the tier is asserted rather than assumed.
    expect(html).toContain('data-warning="customers-open-sub-accounts"');
    // ⚠ **NO RULE ID AND NO REASON ON SCREEN** — B14 rule 32 keeps an internal
    // code out of clerk-facing copy, rule 33 puts RATIONALE at zero words. The
    // WHY (a sale is a transfer, and a transfer carries the tenants) lives in
    // the decision log and in `br_ref`.
    expect(visible(html)).not.toContain("BR-CUS-1082");
    expect(visible(html)).not.toContain("BR-CUS-171");
    expect(visible(html)).not.toContain("OQ-CUS-12515");
    expect(visible(html)).not.toContain("transfer");
  });

  it("BR-CUS-1082: the warning is drawn for a KNOWN count only — never over one nobody took", () => {
    // ⚠ **THE FALSE PASS THIS CASE EXISTS FOR, AND THE REVERSAL DID NOT
    // REMOVE IT — IT MADE IT QUIETER.** `impact` is null while the
    // close-impact read is in flight and stays null if it fails, and a
    // `null > 0` test would warn on EVERY move-out in the product while making
    // the case above green exactly as the correct version does. A wrong
    // refusal stops a clerk and gets reported; a wrong warning is just noise
    // on every screen, which nobody reports and everybody learns to ignore.
    const notMeasured = renderWizard(accountMoveOutPath("acc-10432"), {
      detail: detail(),
      access: "Full",
    });
    expect(visible(notMeasured)).not.toContain("still open");
    expect(notMeasured).not.toContain('data-warning="customers-open-sub-accounts"');

    // …and a master measured at zero is a MEASUREMENT, not a warning.
    const none = renderWizard(accountMoveOutPath("acc-10432"), {
      detail: detail(),
      access: "Full",
      impact: { ...IMPACT_BASE, open_sub_accounts: 0 },
    });
    expect(visible(none)).not.toContain("still open");
    expect(none).not.toContain('data-warning="customers-open-sub-accounts"');
  });

  it("US-CUS-005 §5: the payload is EXACTLY the one field the endpoint accepts", () => {
    const payload = moveOutPayload("2026-08-14");
    expect(payload).toEqual({ moved_out_on: "2026-08-14" });
    // `services.REFUSED_FIELDS` — each of these fails the WHOLE move-out if
    // sent, and a screen that stripped them before sending would be the same
    // lie one layer down.
    for (const refused of [
      // ⚠ **`reason` LEFT THIS LIST ON 2026-09-20** (PO ruling, option A) — it
      // is an ACCEPTED field now and the case below asserts it is SENT. It is
      // still absent from THIS payload because none was passed, which is the
      // lawful no-clerk case; asserting it as refused would have been a check
      // that passes for the wrong reason.
      // `close_reason` stays: the COLUMN's name is refused on every door,
      // including this one, so there is exactly one spelling in.
      "close_reason",
      "final_reads",
      "deposit_disposition",
      "deposit_interest_accrued",
      "refund_method",
      "deposit_on_file",
      "closed_at",
      "unit_id",
      "plan",
      "customer_id",
    ]) {
      expect(payload).not.toHaveProperty(refused);
    }
    // `status` is omitted so the SERVER picks the tenant's own terminal status
    // (BR-CUS-055 is tenant-extensible — choosing one here would decide for it).
    expect(payload).not.toHaveProperty("status");
  });

  it("PO 2026-09-20 item 3: the chosen reason is SENT, and an unchosen one is omitted", () => {
    // ✅ **THE RULING'S WHOLE POINT, AS ONE ASSERTION.** The blueprint's p110
    // says the wizard *"asks and forgets"*; this is the line that would go red
    // the day it started forgetting again. A screen that draws the select and
    // drops the value on the floor passes every OTHER case in this file.
    expect(moveOutPayload("2026-08-14", {}, undefined, "lease_ended")).toEqual({
      moved_out_on: "2026-08-14",
      reason: "lease_ended",
    });

    // ⛔ **OMITTED, NEVER `""`.** `field_visit` is omitted for the same reason:
    // a key that is simply absent needs no test at the far end. This also
    // keeps a move-out lawful for a caller with no clerk in front of it.
    expect(moveOutPayload("2026-08-14", {}, undefined, "")).not.toHaveProperty("reason");

    // ⚠ **EVERY CODE THE SCREEN OFFERS SURVIVES THE ROUND TRIP.** Asserting
    // one would pass over a builder that hardcoded it — the "what would make
    // this check pass WRONGLY" question, answered.
    for (const code of CLOSE_REASONS) {
      expect(moveOutPayload("2026-08-14", {}, undefined, code)).toHaveProperty("reason", code);
    }
  });

  it("DEF-CUS-6464: when the bill cannot be priced, step 3 says WHY, in the engine's words", () => {
    // ⚠ **THE PO's OWN QUESTION, 2026-09-24:** *"no bill is generated here ...
    // why are we unable to generate the bill here?"* The server had always
    // answered it — `priced_unavailable{reason, detail}` — and the answer
    // reached the DOM only inside a `rows.length === 0` branch that stopped
    // being reachable on 2026-09-19, when the export-credit and *Final bill,
    // net* rows were added. Measured on the seeded tenant: **30 of 75 open
    // accounts refuse to price**, and on every one the panel drew two rows and
    // no sentence at all.
    //
    // **What would make this pass WRONGLY?** Asserting the sentence appears
    // anywhere. So this mounts the REAL step 3 and also asserts the two money
    // rows are STILL drawn beside it — rendering the refusal INSTEAD of the
    // table would trade one silence for another, because the export credit and
    // the net are real figures even when the priced lines are missing.
    // ⚠ **RE-QUOTED 2026-09-24 (`DEF-CUS-6550`).** This is a FIXTURE, so it
    // passed whatever the engine's real sentence was — and the real one was
    // **63 words over four sentences**, printing a Python `None` and a PO
    // ruling date to a clerk. B14 rule 33 caps it at six words a sentence;
    // the engine composes it, so the length is held where it is composed
    // (`06-backend/tests/test_def_cus_6550_base_refusals_are_short.py`), which
    // is the only place it CAN be held. What this file owns is that whatever
    // the engine says travels to the screen VERBATIM.
    const engineSentence = "BASE-E has no price for E-200. Price it on the charge code.";
    const html = renderWizard(`${accountMoveOutPath("acc-10432")}?step=3`, {
      detail: detail(),
      access: "Full",
      preview: {
        priced: false,
        lines: [],
        total: null,
        currency: null,
        periodStart: null,
        periodEnd: null,
        subtotal: null,
        taxTotal: null,
        fromUncommittedReads: false,
        unavailable: "plan_has_no_tariff_for_service",
        unavailableDetail: engineSentence,
      },
    });
    // The engine's own words, verbatim — not a paraphrase behind a catalogue
    // key, which would be a second copy of an engine message free to drift.
    expect(html).toContain(engineSentence);
    // ⛔ The CODE never reaches the screen (B14 rule 32) — only the `data-`.
    //
    // ⚠ **`visible()` IS NOT A TEXT EXTRACTOR AND THIS ASSERTION WAS WRITTEN AS
    // IF IT WERE.** It strips `title="…"` and nothing else, so every `data-`
    // attribute survives it — the first draft of this line failed on its own
    // `data-final-bill-unavailable`, which is exactly where the code is
    // SUPPOSED to be. Rule 32 is about what a clerk READS, so the check has to
    // be against text content, not against the markup.
    expect(html).toContain('data-final-bill-unavailable="plan_has_no_tariff_for_service"');
    const textOnly = html.replace(/<[^>]*>/g, " ");
    expect(textOnly).not.toContain("plan_has_no_tariff_for_service");
  });

  it("DEF-CUS-6464: a PRICED preview draws no refusal", () => {
    // The mirror case: the sentence must not appear on the 45 of 75 accounts
    // that price perfectly well. It is keyed on `priced === false`, so a
    // preview that priced carries no refusal even if a stale detail rode along
    // — which is the shape that would otherwise put a permanent warning on a
    // healthy screen.
    const html = renderWizard(`${accountMoveOutPath("acc-10432")}?step=3`, {
      detail: detail(),
      access: "Full",
      preview: {
        priced: true,
        lines: [
          {
            description: "Water \u00b7 base",
            amount: "19.6000",
            quantity: null,
            unit: null,
            estimated: false,
            service: "water",
            unitPrice: null,
            kind: "base",
          },
        ],
        total: "19.6000",
        subtotal: "19.6000",
        taxTotal: "0.0000",
        currency: "USD",
        periodStart: "2026-09-01",
        periodEnd: "2026-09-30",
        fromUncommittedReads: false,
        unavailable: null,
        unavailableDetail: "a stale sentence that must not render",
      },
    });
    expect(html).not.toContain("a stale sentence that must not render");
    expect(html).not.toContain("data-final-bill-unavailable");
  });

  it("DEF-CUS-6550: no step of ACC-06 ends with the audit-log sentence", () => {
    // ⛔ **DELETED, NOT SHORTENED.** *"Closing an account is recorded in the
    // audit log by the server, with who, when, and everything that changed."*
    // — nineteen words under the footer of EVERY step, telling a clerk how the
    // product works rather than anything about this account. B14 rule 33 puts
    // RATIONALE at zero words on screen, and the repo's precedent for rationale
    // is removal (`CorrectionRetentionNote`; the transfer wizard's six
    // sentences, `DEF-CUS-6385`; and the PO's own approved remedy list for this
    // screen, which deletes *What confirming writes*).
    //
    // **What would make this pass WRONGLY?** Asserting on the catalogue KEY:
    // the key is retired, so a `not.toContain` on it passes even if the English
    // were hard-coded back into the TSX. So this asserts on the WORDS, and on
    // the class the line was rendered with — either coming back fails it.
    //
    // ⚠ **AND ON ALL FOUR STEPS, not just the one that was reported.** The
    // line was rendered by the wizard SHELL, below `WizardFrame`, so it
    // appeared on every step; a test of step 3 alone would pass over three
    // surviving copies.
    for (const step of [1, 2, 3, 4]) {
      const html = renderWizard(`${accountMoveOutPath("acc-10432")}?step=${step}`, {
        detail: detail(),
        access: "Full",
      });
      const textOnly = html.replace(/<[^>]*>/g, " ");
      expect(textOnly).not.toContain("audit log");
      expect(textOnly).not.toContain("everything that changed");
      // A raw key on screen is the defect G32 exists for: retiring a key whose
      // call site is still live prints the KEY, because a catalogue entry beats
      // a `defaultValue`. This is what proves the call site went too.
      expect(html).not.toContain("customers.moveOut.auditLine");
      expect(html).not.toContain("settings-audit-line");
    }
  });

  it("DEF-CUS-6465: no move-out warning claims a module has no tables when it has them", () => {
    // ⚠ **THREE SENTENCES EVERY COMPLETED MOVE-OUT SHOWED WERE FALSE.** They
    // named billing, payments and the deposit-interest engine and said each was
    // absent; `invoices`, `refunds` and `payments` all have tables, and the
    // accrual has answered since 2026-09-03. `MOVE_OUT_UNAVAILABLE` is a tuple
    // of PROSE in the write path, so nothing re-checks it when the module it
    // describes ships — hard-won law 1 in the direction nothing looks at.
    //
    // **This guards the CLERK-FACING half**, which is a separate copy of the
    // same claims in eleven languages: a lane correcting the server and not the
    // catalogue would move nothing a user reads (DEF-731's shape).
    const catalogue = i18n.getResourceBundle("en", "translation") as Record<string, string>;
    const stale: string[] = [];
    for (const [key, value] of Object.entries(catalogue)) {
      if (!key.startsWith("customers.account.warning.")) continue;
      // The two modules that genuinely have no tables keep their sentences, and
      // this is the mirror-image defect: a sweep that "corrects" them too.
      if (key.endsWith(".dunning_not_stopped") || key.endsWith(".closeout_documents_not_queued")) {
        continue;
      }
      if (/\b(billing|payments|invoices|refunds)\b[^.]*\bno tables\b/i.test(value)) {
        stale.push(`${key} = ${value}`);
      }
    }
    expect(stale).toEqual([]);

    // The accrual is BUILT, so nothing may say it is not — and the row is now
    // conditional on the server, so it only reaches a clerk when the figure
    // really could not be worked out.
    expect(catalogue["customers.account.warning.deposit_interest_not_accrued"]).not.toMatch(
      /not built/i,
    );
    // The issued-bill check blamed a missing invoices table; its seam has been
    // wired since DEF-035, so a miss now means THIS ACCOUNT has no issued bill.
    expect(
      catalogue["customers.account.warning.move_out_date_not_checked_against_issued_bills"],
    ).not.toMatch(/no invoices table/i);

    // ⛔ **AND THE TWO THAT ARE STILL TRUE MUST SURVIVE.** Collections and
    // notifications genuinely have no tables; saying so is the only honest
    // thing, and it is one keystroke from being swept with the rest.
    expect(catalogue["customers.account.warning.dunning_not_stopped"]).toMatch(/no tables/i);
    expect(catalogue["customers.account.warning.closeout_documents_not_queued"]).toMatch(
      /no tables/i,
    );
  });

  it("DEF-CUS-6476: step 1's panel draws every row 01-find-account.png draws, in its order", () => {
    // ⚠ **THE CASE THE DEFECT IS, AND IT IS A PRESENCE-AND-ORDER CHECK ON
    // PURPOSE.** Four of these rows were absent before 2026-09-24 — the mailing
    // address, the type, the sub-type and the kind — and **every one was
    // already on the wire**. An absence is invisible to every check this repo
    // has (hard rule 8's own lesson), so the only thing that finds one is
    // reading the drawing row by row and asserting the list.
    //
    // **What would make this pass WRONGLY?** Asserting the labels exist
    // anywhere on the page — the stepper and the header carry words too. So the
    // ORDER is asserted as well: the drawn sequence is part of the design, and
    // a row appearing in the wrong column would still satisfy a presence-only
    // check.
    const html = renderWizard(`${accountMoveOutPath("acc-10432")}?step=1`, {
      detail: detail(),
      access: "Full",
    });
    const panel = html.slice(html.indexOf("data-move-out-account-panel"));
    const drawn = [
      "Account",
      "Name",
      "Service address",
      "Mailing address",
      "Services",
      "Plan",
      "Type",
      "Sub-type",
      "Kind",
      "Status",
      "Since",
      "Balance",
    ];
    let at = -1;
    for (const label of drawn) {
      const found = panel.indexOf(`>${label}<`, at + 1);
      expect(found, `${label} is missing from the panel, or is out of drawn order`).toBeGreaterThan(
        at,
      );
      at = found;
    }
    // It is the REGULAR variant, so no master badge.
    expect(panel).toContain('data-move-out-account-panel="regular"');
    expect(panel).not.toContain('data-account-kind="master"');
  });

  it("DEF-CUS-6476: no mailing row on file reads 'Same as service address', never blank", () => {
    // ⚠ **THE TWO ABSENCES ARE DIFFERENT CLAIMS AND THE PANEL MUST NOT COLLAPSE
    // THEM.** `addressLine`'s own docstring makes the point: an account with no
    // mailing row means the bill goes to the service address, which is a
    // different fact from an address nobody typed. Collapsing them is how a
    // landlord's bills quietly start going to the flat they do not live in.
    // Proved on the PURE function, so it needs no mount.
    expect(mailingAddressAnswer([])).toEqual({ kind: "same" });
    expect(
      mailingAddressAnswer([
        {
          id: "adr-1",
          kind: "mailing",
          line1: "PO Box 219",
          city: "Ottumwa",
          state: "IA",
          postal_code: "52501",
        },
      ]),
    ).toEqual({ kind: "line", text: "PO Box 219, Ottumwa, IA, 52501" });
    // A mailing ROW whose every part is empty is still "same as service" — an
    // empty line is not an address, and printing a blank row claims one exists.
    expect(
      mailingAddressAnswer([
        { id: "adr-2", kind: "mailing", line1: null, city: null, state: null, postal_code: null },
      ]),
    ).toEqual({ kind: "same" });
    // ⛔ A `service` row is NOT read here — `kind='service'` is retired and
    // refused by name (hard rule 8), and the service address is derived by
    // walking to the premises.
    expect(
      mailingAddressAnswer([
        { id: "adr-3", kind: "service", line1: "18 Marten Row", city: "Ottumwa", state: "IA", postal_code: "52501" },
      ]),
    ).toEqual({ kind: "same" });
  });

  it("DEF-CUS-6487: the whole field-visit election reaches the wire, not just template ids", () => {
    // ⚠ **THE CASE THE DEFECT IS.** `POST /accounts/{id}/move-out` read
    // `field_visit.template_ids` alone, so the ROWS a clerk adds in the
    // PO-approved table and the *No visit needed* answer were parsed out of the
    // payload and dropped — while the move-out reported success and no crew was
    // ever sent. The door was widened in the same commit; this is the front
    // end's half of that contract.
    //
    // **What would make this check pass WRONGLY?** A builder that hardcoded
    // `{none: true}`, or one that sent `orders` but lost the note and the
    // holder. Both are covered: the three shapes are asserted separately and
    // the row's own fields are read back out of the built payload.
    const declined = moveOutPayload(
      "2026-08-14",
      {},
      fieldVisitPayload({ none: true, rows: [] }),
      "lease_ended",
    );
    expect(declined.field_visit).toEqual({ none: true });

    const withRow = moveOutPayload(
      "2026-08-14",
      {},
      fieldVisitPayload({
        none: false,
        rows: [
          {
            key: "r1",
            type_id: "type-final-read",
            priority_id: "",
            due_on: "2026-08-15",
            holder: "crew:crew-b",
            note: "Final read",
          },
        ],
      }),
      "lease_ended",
    );
    const visit = withRow.field_visit as { orders: Record<string, unknown>[] };
    expect(visit.orders).toHaveLength(1);
    expect(visit.orders[0]).toMatchObject({
      type_id: "type-final-read",
      due_on: "2026-08-15",
      note: "Final read",
      crew_id: "crew-b",
    });
    // The priority was left alone, so the key is ABSENT and the job type's own
    // default applies at the far end (BR-WRK-018) — never `""`.
    expect(visit.orders[0]).not.toHaveProperty("priority_id");

    // ⛔ **NOTHING SAID, NOTHING SENT.** An untouched panel omits the key
    // entirely rather than sending an empty election, which is the posture the
    // builder has always taken for `final_reads` and `reason`.
    expect(moveOutPayload("2026-08-14", {}, fieldVisitPayload(emptyFieldVisit()), "lease_ended"))
      .not.toHaveProperty("field_visit");
  });

  it("DEF-CUS-6487: a field-visit row with no job type stops Continue on step 2", () => {
    // The server refuses it before the transaction opens; stopping it here
    // keeps the refusal beside the row that caused it rather than on the commit
    // three steps later. The EMPTY panel and *No visit needed* are both fine —
    // a clerk who was never asked and a clerk who answered "nobody" must both
    // be able to go on.
    expect(fieldVisitProblem(emptyFieldVisit())).toBeNull();
    expect(fieldVisitProblem({ none: true, rows: [] })).toBeNull();
    expect(
      fieldVisitProblem({
        none: false,
        rows: [{ key: "r1", type_id: "", priority_id: "", due_on: "", holder: "", note: "x" }],
      }),
    ).not.toBeNull();
  });

  it("PO 2026-09-20 item 3: the five the screen offers ARE the five the server stores", () => {
    // ⚠ **HARD-WON LAW 2's LESSON, AS A GUARD.** The eleven services are typed
    // out by hand in two places, so an eleventh *"does NOT appear on screen on
    // its own and it fails SILENTLY"*. A reason list typed inside the wizard
    // would fail identically: the server would accept a sixth code no clerk
    // could ever choose. This pins the ONE declaration against the server's
    // vocabulary, character for character.
    expect([...CLOSE_REASONS]).toEqual([
      "lease_ended",
      "owner_sold",
      "downgrade_or_hardship",
      "deceased",
      "other",
    ]);
  });

  it("US-CUS-005 §5 / BR-CUS-030 / BR-CUS-021: step 2 collects the DATE and the REASON, and the reads are captured", () => {
    const html = renderWizard(`${accountMoveOutPath("acc-10432")}?step=2`, {
      detail: detail(),
      access: "Full",
    });
    expect(html).toContain("Move-out date &amp; final meter read.");
    expect(html).toContain('id="moved_out_on"');
    expect(html).toContain('type="date"');

    // ⚠ **INVERTED 2026-09-20 (PO ruling, option A — the reason gets a
    // column).** RED-FIRST PROOF, verbatim, with the select wired and these
    // lines still asserting the refusal:
    //   AssertionError: expected '<div class="cus-page">…' to contain
    //   'Not stored'
    // This case used to assert that the five options lived in a rationale
    // sentence and that NO control was drawn for any of them. The blueprint's
    // own p110 calls that *"worse than not asking"*, and it is now a real
    // required select whose value reaches `accounts.close_reason`.
    expect(html).not.toContain("Not stored");
    expect(html).toContain('id="close_reason"');
    expect(html).toContain('<option value="lease_ended">');
    expect(html).toContain('<option value="owner_sold">');
    expect(html).toContain('<option value="downgrade_or_hardship">');
    expect(html).toContain('<option value="deceased">');
    expect(html).toContain('<option value="other">');
    // The leading empty option — nothing is preselected, because a default
    // here would be the product deciding why somebody left.
    // ⚠ The attribute order is React's, and `selected=""` rides the empty
    // option on a static render — so this asserts the two facts that matter
    // (an EMPTY leading option, carrying the placeholder words) rather than a
    // markup string that would go red on a React upgrade.
    expect(html).toMatch(/<option value=""[^>]*>Choose a reason<\/option>/);

    // ⚠ **B14 RULE 32 — NO RULE ID IN CLERK-FACING COPY, and the old version
    // of this case asserted the OPPOSITE** (`expect(html).toContain(
    // "BR-CUS-030")`). The id was on screen only because the absence carried
    // it; with the control built there is nothing to explain and nothing to
    // cite. This asserts the rule that replaced it.
    expect(visible(html)).not.toContain("BR-CUS-030");

    // ⚠ **B14 RULE 39 — the two fields do not touch.** `FieldStack` is what
    // supplies the 20px; a bare run of `.field`s inside a `Panel` measures
    // 0px, which is `DEF-CUS-5098`. Asserting the wrapper is the only part of
    // rule 39 a suite can see — the MEASUREMENT needs a browser.
    expect(html).toContain('data-field-stack=""');

    // ⚠ **INVERTED 2026-08-26 (CR-038 W9 task 4).** RED-FIRST PROOF, verbatim,
    // with the capture wired and this line still asserting the refusal:
    //   AssertionError: expected '<div class="cus-page">…' to contain
    //   'Not captured here'
    expect(html).not.toContain("Not captured here");

    // ⚠ **ONE TABLE SINCE 2026-09-24, NOT A LIST BESIDE A PANEL.** The PO
    // approved the nine-column reading table for the move-out (*"this si
    // correct use it"*), and it replaces BOTH the account's `<ul>` of meter
    // refs and the separate capture panel — two lists of the same registers,
    // one of them with no box on it. `M-4021`/`M-4022` were that `<ul>`.
    expect(html).not.toContain('data-move-reads="inventory-unreadable"');

    // ⚠ THIS CLIENT NEVER STUBS `GET /units/{id}/assets`, and the case is kept
    // that way ON PURPOSE: the absence must still be STATED rather than the
    // control silently not being there — hard-won law 2 inside the fix for
    // hard-won law 2. The shared table states it in its own voice.
    // `DEF-CUS-10051` — the services table (every service, by billing basis).
    expect(html).toMatch(/data-move-out-services="(loading|failed)"/);
    expect(visible(html)).not.toContain("AMI · pulled today");
    expect(visible(html)).not.toContain("Δ usage");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // OQ-394 — THE PO'S OWN SCREEN, WITH THE PO'S OWN NUMBER
  //
  // PO ruling 2026-08-27, verbatim: *"(a) Box opens with 42,864 in it"*. The
  // case above renders this step with NO asset answer, so it can only prove the
  // absence is stated; this one stubs the unit's registers and proves the
  // prefill on the wizard the ruling was actually about.
  // ══════════════════════════════════════════════════════════════════════════
  it("OQ-394 / BR-CUS-021: step 2's box OPENS with 42,864 and says how old it is", () => {
    const html = renderWizard(`${accountMoveOutPath("acc-10432")}?step=2`, {
      detail: detail(),
      access: "Full",
      assets: unitAssets(),
    });
    // ⚠ **THE PREFILL SURVIVED THE MOVE TO THE PO-APPROVED TABLE, AND THAT IS
    // THE WHOLE POINT OF THIS CASE.** `MoveReadsCapture` was replaced by the
    // nine-column `MoveInReadingsTable` on 2026-09-24. The prefill is NOT in
    // that component and was never passed to it as a flag — it lives in the
    // DRAFT (`useReadsDraft` lays the clerk's entries over `prefilledReadsDraft`
    // as a derived value), so the table renders whatever the host's draft holds
    // and the two flows differ without the table knowing. **Had the prefill
    // been re-implemented inside the table, this line would still pass and the
    // move-in's empty box would have silently filled in.**
    expect(html).toContain('id="moveOut-read-ast-4021" class="input input-num" type="text" inputMode="decimal" value="42864"');

    // ⛔ Never the grouped form inside the input — the commas would travel to
    // the server as part of the decimal.
    expect(html).not.toContain('inputMode="decimal" value="42,864"');

    // A register with no committed read still opens EMPTY: refusal 1 survives.
    expect(html).toContain('id="moveOut-read-ast-4022" class="input input-num" type="text" inputMode="decimal" value=""');

    // ⚠ **THE PROVENANCE MOVED FROM A HELP LINE INTO TWO COLUMNS**, which is
    // the approved design rather than a loss: `Last reading` and `Last read on`
    // are columns 5 and 6 of the table the PO ratified. The old case asserted
    // the sentence *"Last read 42,864 kWh · read 8 days ago"* under each box
    // and `data-move-reads="prefilled"`; both belonged to the panel that is
    // gone. The FACT is still on screen, and this asserts it where it now is.
    expect(html).toContain("42,864");
    expect(html).toContain("Last reading");
    expect(html).toContain("Last read on");

    // ⚠ **AND THE COLUMN A CLERK TYPES INTO DOES NOT SAY *Move-in* ON A
    // MOVE-OUT.** A shared table hands you the other flow's word for free; this
    // is the assertion that catches it, because nothing else can.
    expect(html).not.toContain("Move-in reading");
  });

  it("US-CUS-005 TC-2 / BR-BIL-004: step 3 prints NO priced line and NO final total", () => {
    // ⚠ **REPOINTED 2026-09-19, and the GUARANTEE is unchanged.** This asserted
    // the words of the panel that stood here (*"Final bill & deposit
    // settlement."*, *"Waiting on the final bill"*). Step 3 is now the
    // blueprint's own three sections; what must still be true, and is the only
    // thing this case was ever protecting, is that **no figure is drawn that
    // the server did not send** (CLAUDE.md #2). With no preview and no
    // settlement served, the whole step is stated absences.
    const html = renderWizard(`${accountMoveOutPath("acc-10432")}?step=3`, {
      detail: detail(),
      access: "Full",
    });
    // ⚠ **THE SECTION IDS MOVED WITH THE MERGE (PO 2026-09-24).**
    // `final-bill` + `subtraction` were step 3's two panels; the drawing
    // replaces them with `money` (the subtraction, six rows) and `draft-bill`
    // (what the closing window will be billed). The GUARANTEE this case exists
    // for is unchanged and is asserted below: no figure the server did not
    // send.
    expect(html).toContain('data-step-section="money"');
    expect(html).toContain('data-step-section="draft-bill"');
    // The prototype's six priced lines and its total — every one absent.
    const shown = visible(html);
    for (const captured of ["184.20", "38.94", "8.35", "4.83", "284 kWh"]) {
      expect(shown).not.toContain(captured);
    }
    // ⚠ AND THE BLUEPRINT'S OWN FIGURES TOO — B14 rule 37: a figure drawn in a
    // wireframe is an ILLUSTRATION, never a fact to build to. p112 draws
    // $71.40, $17.70, $89.10, $247.30, $336.40 and $186.40 and not one of them
    // is this or any tenant's number.
    for (const drawn of ["71.40", "17.70", "89.10", "247.30", "336.40", "186.40"]) {
      expect(shown).not.toContain(drawn);
    }
    // What renders in their place is the absence, per figure.
    expect(html).toContain('data-tracks="short-by"');
  });

  it("US-CUS-005 §5 / BR-CUS-025 / BR-CUS-057: the four dispositions are NAMED and none is offered", () => {
    // ⚠ **REPOINTED 2026-09-19.** The old step stated five `NotRecorded` facts.
    // p112 draws the four dispositions with three GREYED and each saying why,
    // and its own caption gives the reason it is not a control: *"Which of the
    // four is available is decided by the subtraction below, NOT BY THE
    // CLERK"*. `POST /accounts/{id}/move-out` refuses `deposit_disposition`
    // and `refund_method` outright, so the guarantee this case protects is
    // exactly the one it always protected: **nothing here collects a field the
    // endpoint throws away.**
    const html = renderWizard(`${accountMoveOutPath("acc-10432")}?step=3`, {
      detail: detail(),
      access: "Full",
    });
    for (const option of ["apply", "refund", "hold", "transfer"]) {
      expect(html).toContain(`data-deposit-option="${option}"`);
    }
    // ONE is selected and it is the apply-first rule (BR-CUS-025).
    expect(html).toContain('data-deposit-option="apply" data-selected="yes"');
    expect(html).toContain('data-deposit-option="refund" data-selected="no"');
    // NO control posts a disposition, a refund method or an interest figure.
    expect(html).not.toContain('type="radio"');
    expect(html).not.toContain('id="refund_method"');
    expect(html).not.toContain('id="deposit_disposition"');
    expect(html).not.toContain('id="amount_to_apply"');
    // BR-CUS-057 — no interest amount is implied anywhere, and $0.00 least of
    // all: the accrual engine is not built and the settlement says so.
    const shown = visible(html);
    expect(shown).not.toContain("153.20");
    expect(shown).not.toContain("3.20");
    // The deposit ON FILE is the account's own served column — the SAME column
    // `settlement_for` reads as `deposit_held` — so it renders where the
    // drawing puts it and disagrees with nothing.
    expect(shown).toContain("150.00");
    // …and the PRIOR BALANCE does NOT fall back to `detail.balance`, which is
    // a cache nothing writes (DEF-127) where the settlement reads the ledger.
    expect(shown).not.toContain("120.84");
  });

  it("US-CUS-005 §5 / BR-CUS-030 / BR-MET-036: the read-back draws no checkbox, and names the one derivation", () => {
    // ⚠ **STEP 6 BECAME STEP 4 ON 2026-09-24** — old 5 and 6 merged, because
    // old step 5 had no input anywhere on it and was a review page one click
    // before the review page.
    const html = renderWizard(`${accountMoveOutPath("acc-10432")}?step=4`, {
      detail: detail(),
      access: "Full",
    });
    // ⛔ **THE STEP'S OWN `<h3>` WENT WITH THE MERGE.** The page head already
    // says *Step 4 of 4 · Review & close* and the rail names it again; a third
    // statement is B14 rule 32's *a row never repeats what its own control
    // offers*. `customers.moveOut.closeout.title` is retired.
    expect(html).not.toContain("Close-out &amp; documents.");
    // ⚠ **THE TWO PROSE PANELS ARE GONE AND THE CASE NOW ASSERTS THE FACTS
    // INSTEAD — `DEF-CUS-6477`.** It used to assert *What confirming writes*
    // (66 words) and *What confirming does not do* (59 words), which between
    // them described our storage design and named our unbuilt modules to a
    // clerk; B14 rule 33 puts RATIONALE at ZERO words on screen and says to
    // REMOVE rather than shorten. Their absence is asserted so a lane cannot
    // reinstate them without this going red.
    expect(html).not.toContain("What confirming writes");
    expect(html).not.toContain("What confirming does not do");
    expect(html).not.toContain("One of the five things the design does");
    // ⚠ **WHAT THE CASE IS NAMED FOR IS UNCHANGED AND IS NOW WHAT IT CHECKS.**
    // The title says *draws no checkbox, and names the one derivation* — so the
    // derivation itself (BR-MET-036: the unit falls vacant because the account
    // stops occupying it, never a switch a clerk flips) is asserted by the ROW
    // that states it, which is the fact a clerk reads.
    // ⚠ **THE DERIVATION MOVED PANELS WITH THE MERGE, NOT AWAY.** Old step 6
    // recapped it as *Vacant, and it keeps its plan*; the drawing states the
    // two halves as their own rows of *The unit* — *Falls to · Vacant, from
    // <date>* and *Plan · Stays on the unit*. `BR-MET-036` is what this case
    // is named for and is unchanged: the unit falls vacant BECAUSE the account
    // stops occupying it, never because a clerk flipped a switch.
    expect(html).toContain("Stays on the unit");
    expect(html).not.toContain('type="checkbox"');
    expect(html).not.toContain('id="send_final_statement"');
    expect(html).not.toContain('id="stop_dunning"');
  });

  it("US-CUS-005 §5 / BR-SHL-011: an out-of-range or non-numeric ?step= clamps rather than erroring", () => {
    expect(moveOutStepFromParam(null)).toBe(1);
    expect(moveOutStepFromParam("3")).toBe(3);
    expect(moveOutStepFromParam("0")).toBe(1);
    expect(moveOutStepFromParam("99")).toBe(4);
    expect(moveOutStepFromParam("banana")).toBe(1);
  });

  it("US-CUS-005 TC-6 / BR-SHL-019: exactly ONE commit, and it is the frame's ✓", () => {
    const html = renderWizard(accountMoveOutPath("acc-10432"), {
      detail: detail(),
      access: "Full",
    });
    // The prototype's second button ("Complete & start move-in →") is NOT a
    // second commit: it is a link on the answer (asserted below).
    // ⚠ CLASS NAME -> `data-variant` (CR-018 Phase 4a, 2026-08-20). Route B
    // deletes the name; `buttonKit` stamps `data-variant`/`data-size` on every
    // kit button precisely so a check has something stable to read.
    expect((html.match(/data-variant="primary"/g) ?? []).length).toBe(1);
    expect(html).toContain("Continue");
  });

  it("US-CUS-005 §5: the date guard mirrors the server's two refusals and invents no third", () => {
    expect(moveOutDateProblem("", "2024-02-14")).toBe("required");
    expect(moveOutDateProblem("2024-02-13", "2024-02-14")).toBe("before_start");
    expect(moveOutDateProblem("2026-08-14", "2024-02-14")).toBeNull();
    // No `opened_at` on the account ⇒ nothing to compare, never a guess.
    expect(moveOutDateProblem("2020-01-01", null)).toBeNull();
  });

  it("US-CUS-005 TC-1 / BR-CUS-031: the answer shows ALL NINE warnings, each with its rule", () => {
    const html = renderDone();
    expect(html).toContain("What the server could not do");
    for (const warning of NINE_WARNINGS) {
      // The translated sentence, not the raw code — a raw code on screen is a
      // missing catalog key (G15) rather than an answer.
      const text = warningText(warning, t);
      expect(text).not.toBe(warning.code);
      expect(html).toContain(text.slice(0, 40).replace(/&/g, "&amp;"));
    }
    // Nine <li>, not eight and not a summary of them.
    // AMENDED 2026-08-21 (DEF-332): `<li\b`, because the rule id moved out of
    // the sentence and onto `data-br-ref` on the item, so the tag now carries
    // an attribute. The count is the same count.
    expect((html.match(/<li\b/g) ?? []).length).toBe(NINE_WARNINGS.length);
    for (const warning of NINE_WARNINGS) {
      expect(html).toContain(`data-br-ref="${String(warning.br_ref)}"`);
    }
  });

  it("US-CUS-005 TC-1 / BR-CUS-031: the handoff renders WITH `persisted: false` and its four gaps", () => {
    // The fixture's seam DID NOT ANSWER (`final_reads_unavailable` is set), so
    // the reads gap is listed — the deployment case the rule id exists for.
    const gaps = handoffGaps(handoff());
    expect(gaps.map((gap) => gap.ruleRef)).toEqual([
      "BR-CUS-021",
      "BR-CUS-029",
      "BR-CUS-057",
      "BR-CUS-025",
      "BR-CUS-025",
    ]);

    // ⚠ **AND IT DROPS OUT WHEN THE ELEMENT IS SERVED (2026-08-26, CR-038 W9
    // task 4).** `final_reads_unavailable` was typed non-nullable and this
    // entry was unconditional, so a move-out that committed its closing
    // readings would still have listed them as a gap the product could not
    // fill. RED-FIRST PROOF, verbatim, with the type widened and `handoffGaps`
    // unchanged:
    //   AssertionError: expected [ 'BR-CUS-021', 'BR-CUS-029', …(3) ] to
    //   deeply equal [ 'BR-CUS-029', 'BR-CUS-057', 'BR-CUS-025',
    //   'BR-CUS-025' ]
    const served = handoffGaps({
      ...handoff(),
      final_reads: { unit_id: "u-1", as_of: "2026-08-14", meters: [] },
      final_reads_unavailable: null,
      final_read_state: "taken",
    });
    expect(served.map((gap) => gap.ruleRef)).toEqual([
      "BR-CUS-029",
      "BR-CUS-057",
      "BR-CUS-025",
      "BR-CUS-025",
    ]);

    const html = renderDone();
    expect(html).toContain("The final-bill handoff for billing");
    // BR-CUS-056: the boundary day is stated, with the server's own rule id.
    expect(html).toContain("Bill through");
    expect(html).toContain("08/14/2026");
    expect(html).toContain("BR-CUS-056");
    expect(html).toContain("Not stored anywhere");
    expect(html).toContain("BR-CUS-031");
    // Money from the handoff travels as the served decimal + its CHAR(3) code.
    expect(html).toContain("120.84");
    expect(html).toContain("150.00");
  });

  it("US-CUS-005 TC-3 / BR-CUS-056: the answer offers the chain as a link, not a second commit", () => {
    const html = renderDone();
    expect(html).toContain("Move the next tenant in →");
    expect(html).toContain(`href="/${TEST_TENANT}${accountMoveInPath("acc-10432")}"`);
    expect(html).toContain("Open the closed account");
    expect(html).toContain(`href="/${TEST_TENANT}/accounts/acc-10432"`);
    // BR-CUS-056, computed rather than described: Aug 14 → Aug 15.
    expect(earliestMoveInDate("2026-08-14")).toBe("2026-08-15");
    // Month and year boundaries, in UTC, with no local-time off-by-one.
    expect(earliestMoveInDate("2026-08-31")).toBe("2026-09-01");
    expect(earliestMoveInDate("2026-12-31")).toBe("2027-01-01");
    expect(earliestMoveInDate("2028-02-28")).toBe("2028-02-29");
    expect(earliestMoveInDate(null)).toBeNull();
  });

  it("US-CUS-005 §RBAC / BR-SHL-025: a View role sees the flow with the reason, and a '—' cell sees nothing", () => {
    const viewOnly = renderWizard(accountMoveOutPath("acc-10432"), {
      detail: detail(),
      access: "View",
    });
    expect(viewOnly).toContain("Your role can view accounts but not change them.");
    expect(viewOnly).toContain('data-wizard="frame"');

    const denied = renderWizard(accountMoveOutPath("acc-10432"), {
      detail: detail(),
      access: "—",
    });
    expect(denied).toContain("state-denied");
    expect(denied).not.toContain('data-wizard="frame"');
  });

  it.todo(
    "US-CUS-005 TC-1: Continue through all four steps and commit — the click path needs a browser; each step's fields, the payload and the answer are asserted statically above",
  );
  it.todo(
    "US-CUS-005 TC-5 (negative): a final read below the prior one routes into the metering exception path — there is no final-read control to refuse (BR-CUS-021)",
  );
  it.todo(
    "US-CUS-005 TC-6 (negative): a move-out behind the last issued bill blocks — billing has no invoices table, so the server warns that the check could not run and this screen shows that warning",
  );
  it.todo(
    "US-CUS-005 TC-7 (isolation): J. Okafor sees no Brazos Bend account — server/RLS scope (G5)",
  );
});


// ══════════════════════════════════════════════════════════════════════════
// CR-030 W5 · task 5.1 (park & resume) and task 5.7 (the impact screen)
// ══════════════════════════════════════════════════════════════════════════

describe("BR-SHL-047 (DEF-649) — every wizard parks, move-out included", () => {
  /**
   * ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-08-26, AND IT WAS RIGHT.**
   * It read *"`Park` is DISABLED CARRYING its reason"* and asserted the visible
   * *"Parking is not available here yet"*, `parkStoreBlockedReason(t)` non-null
   * and `wizardParkPort()` null. All true while there was no store — the reason
   * was STORAGE and never design, which is why DEF-649's id stayed off the
   * screen and still does.
   *
   * **CR-035 built the store, so the fact changed and the rule did not.**
   * Inverted rather than deleted: the pair is one rule read from both ends.
   */
  it("draws BOTH controls: `Save & exit` acts, and `Park` is no longer blocked", () => {
    const html = renderWizard(accountMoveOutPath("acc-10432"), {
      detail: detail(),
      access: "Full",
    });
    expect(html).toContain('data-wizard="exit"');
    expect(html).toContain("Save &amp; exit");
    expect(html).toContain("Park");
    // BR-SHL-025's wrapper renders only when there IS a reason. There is not.
    expect(html).not.toContain('data-wizard="park-blocked"');
    expect(visible(html)).not.toContain("Parking is not available here yet");
    // DEF-332 — our internal ids never reach a clerk's screen, then or now.
    expect(visible(html)).not.toContain("DEF-649");
    expect(parkStoreBlockedReason(t)).toBeNull();
    expect(wizardParkPort()).not.toBeNull();
  });

  it("the park FORM is drawn on `?park=1` now that its submit has somewhere to go", () => {
    const html = renderWizard(`${accountMoveOutPath("acc-10432")}?park=1`, {
      detail: detail(),
      access: "Full",
    });
    // ⚠ **THE SUPERSEDED ASSERTION WAS `not.toContain`, AND ITS REASON IS THE
    // REASON THIS ONE IS SAFE:** *"`?park=1` is honoured only where the flow
    // said park may act, so a pasted link cannot open a form whose submit has
    // nowhere to go."* The submit has somewhere to go now, so the pasted link
    // opens the form — the guard was never about the URL, it was about the
    // store behind it.
    expect(html).toContain('data-wizard="park"');
    // B18 §4.2's nine, drawn as options a clerk can actually answer.
    expect(html).toContain("waiting on a deposit");
  });

  it("BR-SHL-048 (c): the age is counted, NO limit is invented, and it no longer says the unit is held", () => {
    // A parked move-out still holds its unit. The PO settled that parking is
    // offered and did NOT settle what stops one sitting forever.
    const now = new Date("2026-08-24T12:00:00Z");
    expect(parkAgeDays(null, now)).toBeNull();
    expect(parkAgeDays("", now)).toBeNull();
    expect(parkAgeDays("2026-08-24T00:00:00Z", now)).toBe(0);
    expect(parkAgeDays("2026-08-09T12:00:00Z", now)).toBe(15);
    // A clock skew reads as zero days, never as a negative age.
    expect(parkAgeDays("2026-08-25T12:00:00Z", now)).toBe(0);
    expect(parkAgeDays("not a date", now)).toBeNull();
  });
});

describe("CR-030 W5 task 5.7 — the move-out impact screen (B18 §5.6.5 · B19 §15.10)", () => {
  // ⚠ **STEP 5 BECAME STEP 4 ON 2026-09-24** — the PO ruled old steps 5 and 6
  // into one (*"i okay with these steps"*), because old step 5 had **no input
  // anywhere on it**: every panel was read-only, so it was a review page
  // sitting one click before the review page. Every panel it drew is still
  // drawn; what went is the step, and two panels the same ruling deleted for
  // being rationale rather than fact.
  const impactStep = `${accountMoveOutPath("acc-10432")}?step=4`;

  // ══════════════════════════════════════════════════════════════════════
  // ⚠ **STEP 5 WAS REBUILT TO ITS DRAWING ON 2026-09-19 (PO: *"we should build
  // this"*), SO THE CASES THAT ASSERTED THE NINE-PANEL SHAPE ARE SUPERSEDED.**
  // DEF-705's lesson, applied: when a fact is superseded the tests asserting
  // the old one are PART of the supersession, and leaving them green over a
  // deleted screen is how a suite starts pinning a defect in place. Every
  // GUARANTEE they held is re-asserted below against the drawn screen —
  // nothing was dropped to get to green.
  // ══════════════════════════════════════════════════════════════════════

  it("PO 2026-09-24 — the drawn panels of step 4, in the drawn order, and the two that were deleted", () => {
    const html = renderWizard(impactStep, { detail: detail(), access: "Full" });
    expect(html).toContain('data-close-impact=""');
    // `04-review-and-close.png`: the account, the unit and the meters down the
    // left; the money and what we will send down the right.
    for (const section of ["account", "unit", "closing-meters", "money", "messages"]) {
      expect(html).toContain(`data-step-section="${section}"`);
    }
    // …in the drawn order, which is a property no `toContain` can see on its
    // own — and order IS the design (the skill's §4 step 2).
    const order = ["account", "unit", "closing-meters", "money", "messages"].map((section) =>
      html.indexOf(`data-step-section="${section}"`),
    );
    expect(order).toEqual([...order].sort((a, b) => a - b));
    // ⛔ **THE TWO PANELS THE PO DELETED — `not-do` AND `unstated`.** Twelve
    // rows between them, four of the second reading *"The close read does not
    // answer this."*, all of it RATIONALE about what the product does not do
    // and what a read did not answer. PO 2026-09-24: *"on last step - too much
    // information"*. B14 rule 33 removes rationale rather than shortening it.
    expect(html).not.toContain('data-step-section="not-do"');
    expect(html).not.toContain('data-step-section="unstated"');
    expect(html).not.toContain('data-close-unstated=""');
    expect(visible(html)).not.toContain("What this close does NOT do");
    expect(visible(html)).not.toContain("Not stated here");
    // The NINE prose panels are gone, and with them ~900 words of rationale.
    expect((html.match(/data-impact-panel=/g) ?? []).length).toBe(0);
  });

  it("PO 2026-09-24 — p115's panel goes and ONE row of it survives, by ruling, inside The unit", () => {
    // ⚠ **FIVE OF THE SIX WERE RATIONALE AND THE SIXTH IS MONEY.** The panel
    // named *Premises occupancy · Owner on record · Vacant-charge position ·
    // Payment-plan progress · What happens to the assets · Master-account
    // effect*, four of them reading *"The close read does not answer this."*
    // The PO deleted the panel (*"on last step - too much information"*), and
    // was separately shown that an empty unit is charged every month and
    // answered ***"(a) Keep, as one line in 'The unit'"***. So the vacant
    // charge MOVED and the other five went.
    const html = renderWizard(impactStep, {
      detail: detail(),
      access: "Full",
      impact: {
        ...IMPACT_BASE,
        vacant_base_charges: [
          { service: "water", name: "Water", stored: "8.0000", display: "8.00", currency: "USD" },
          { service: "sewer", name: "Sewer", stored: "9.0000", display: "9.00", currency: "USD" },
          { service: "trash", name: "Trash", stored: "0.0000", display: "0.00", currency: "USD" },
          { service: "battery", name: "Battery", stored: "5.0000", display: "5.00", currency: "USD" },
        ],
      },
    });
    const shown = visible(html);
    expect(html).not.toContain('data-close-unstated=""');
    for (const gone of [
      "Premises occupancy",
      "Owner on record",
      "Vacant-charge position",
      "Payment-plan progress",
      "What happens to the assets",
      "Master-account effect",
    ]) {
      expect(shown).not.toContain(gone);
    }
    // ⚠ **THE ARITHMETIC, NOT THE DRAWN FIGURE (B14 rule 37).** `$22.00` is
    // `8 + 9 + 0 + 5` off the plan's OWN per-service standing charges, and the
    // drawing's `$22.00 a month · Water, Sewer, Battery` ties out to exactly
    // that — which is what the drawn figures are FOR. Trash charges nothing,
    // so it is not named: listing it would tell a clerk the unit is charged
    // for something it is not.
    expect(shown).toContain("Vacant charges");
    expect(shown).toContain("$22.00");
    expect(shown).toContain("a month");
    expect(shown).toContain("Water, Sewer, Battery");
    expect(shown).not.toContain("Trash");
    // The facts that ARE known are still stated, not hedged.
    expect(shown).toContain("Stays on the unit");
    // ⛔ …and *They stay fitted — Yes, a move-out removes nothing* is NOT one
    // of them. It is rationale about what a move-out does not do, and the
    // drawing replaces that whole panel with the meters themselves.
    expect(shown).not.toContain("a move-out removes nothing");
  });

  it("the money group states every figure it was not served, and invents none", () => {
    // With no settlement served — which is every account in this product until
    // a final bill is stated — the five money rows are absences, never zeros.
    const html = renderWizard(impactStep, { detail: detail(), access: "Full" });
    expect(html).toContain('data-step-section="money"');
    const shown = visible(html);
    expect(shown).not.toContain("$0.00");
    // ⚠ **THE INTEREST ROW MOVED INTO `The money` TABLE AND ITS ABSENCE
    // SENTENCE WITH IT.** The old panel said *Not recorded*; the drawn table
    // states the shared absence, because BR-CUS-057's accrual engine is not
    // built and the FIGURE is the thing that must never be invented. **Never
    // `$0.00`** — on a final settlement that is the claim this customer owes
    // nothing, which is a money claim nobody measured.
    expect(shown).toContain("Not worked out yet");
    expect(html).toContain('data-tracks="deposit-interest"');
  });

  it("CR-056 W6 — the owner is NAMED where served, and never called free text", () => {
    // ⚠ **THE GUARANTEE OF THE RETIRED `FREE TEXT` ADVISORY, KEPT.** That
    // advisory once fired on EVERY move-out in the product, telling a clerk
    // *"nothing can be billed or transferred to them"* about a landlord the
    // product was about to bill (DEF-669's correction one panel over). The
    // drawn screen has no such advisory; what it must never do is make the
    // claim. The owner is one of p115's six — named when served, stated as an
    // absence when not, and characterised never.
    const html = renderWizard(impactStep, {
      detail: detail(),
      access: "Full",
      impact: { ...IMPACT_BASE, owner_is_free_text: false, owner_on_record: "Miller Property LLC" },
    });
    const shown = visible(html);
    // ⚠ **THE ROW THAT NAMED THE OWNER WENT WITH p115's PANEL (PO
    // 2026-09-24), AND THE GUARANTEE THIS CASE HOLDS IS THE NEGATIVE ONE.**
    // The retired advisory fired on EVERY move-out telling a clerk *"nothing
    // can be billed or transferred to them"* about a landlord the product was
    // about to bill. The screen must never make that claim — and that is a
    // property of what is ABSENT, which survives the panel being deleted
    // whereas *"the owner is named"* does not.
    expect(shown).not.toContain("not an account");
    expect(shown).not.toContain("is a name on the premise record");
    expect(shown).not.toContain("is free text on the premise record");
    expect(html).not.toContain('data-advisory="DEF-650"');
    // Where the owner's ACCOUNT is served it is still named, on the row the
    // drawing keeps — the unit's standing charge has to say where it goes.
    expect(html).not.toContain('data-tracks="owner"');
  });


  it("CLAUDE.md #2 — no figure is invented for the six fields nobody serves", () => {
    const html = renderWizard(impactStep, { detail: detail(), access: "Full" });
    // ⛔ **THIS ASSERTED `closeImpactPort()).toBeNull()` UNTIL DEF-669.** It was
    // true when written and it went FALSE on 2026-08-25, when the route was
    // mounted — so the check was pinning the defect in place, which is DEF-705's
    // lesson: when a fact is superseded, the tests asserting the old one are
    // part of the supersession. The port is now real; what it must never do is
    // INVENT the six fields it is not served.
    expect(closeImpactPort()).not.toBeNull();
    // B19 §15.10's captured numbers belong to ONE fixture account. None of them
    // is a rule, and none of them is printed here.
    for (const captured of ["30.50", "13.12", "153.50", "4.10", "948.20", "1 of 3"]) {
      expect(visible(html)).not.toContain(captured);
    }
    // ⚠ **REPOINTED AGAIN 2026-09-24 — THE PANEL THAT NAMED THE SIX IS
    // DELETED AND THE RULE IT SERVED IS NOT.** CLAUDE.md hard rule 2 is about
    // what may be PRINTED, so this case's subject is the captured figures
    // above, every one of which must stay off the screen. Naming an unserved
    // field was p115's answer to *how do we say we do not know*; the PO's
    // answer is to say nothing, which satisfies the same rule more strictly.
    expect(html).not.toContain('data-step-section="unstated"');
    // The ONE of the six that survives, by ruling, states its own absence
    // rather than printing a zero — real money, so *we could not read it* and
    // *it costs nothing* must not look the same.
    expect(html).toContain('data-tracks="vacant-charge"');
  });

  it("DEF-669 — a served impact does not print `0 of 3` for occupancy nobody measured", () => {
    // **THE HAZARD THE WIRING CREATED, PINNED.** The occupancy line tested the
    // WHOLE `impact` for null and then read `units_occupied_after?.occupied ?? 0`.
    // The moment the port returned an object — which it now does — that branch
    // printed a measurement, in a consequence panel, that nobody took.
    const html = renderWizard(impactStep, {
      detail: detail(),
      access: "Full",
      impact: {
        landing: "settled",
        open_sub_accounts: 0,
        units_occupied_after: null,
        owner_on_record: null,
        owner_is_free_text: null,
        common_area_account_no: null,
        unit_falls_to: null,
        vacant_base_charge: null,
        vacant_base_charges: null,
        payment_plan: null,
        money: null,
        shortfall_paths: [],
        refund_methods: [],
        gaps: [],
        step_4_live: null,
      },
    });
    // ⚠ **THE OCCUPANCY ROW WENT WITH p115's PANEL ON 2026-09-24, AND THE
    // NEGATIVE THIS CASE PINS IS WHAT MATTERED.** The defect was a MEASUREMENT
    // being printed that nobody took; the row that printed it no longer
    // exists, so the guarantee is now absolute rather than conditional.
    expect(visible(html)).not.toContain("0 of 0");
    expect(visible(html)).not.toContain("0 of 3");
    expect(html).not.toContain('data-tracks="occupancy"');
    // and `owner_is_free_text: null` must not assert FREE TEXT about a premises
    // nobody read — it was typed `boolean` and defaulted to `true`.
    expect(visible(html)).not.toContain("is free text on the premise record");
  });

  // ══════════════════════════════════════════════════════════════════════
  // CR-056 W6 TASK 26 — THE UNIT FALLS TO THE OWNER, AND THE SCREEN SAYS SO
  // ══════════════════════════════════════════════════════════════════════
  // PO 2026-08-31, and *explicitly* is the operative word: *"The unit falling
  // to the owner's account is a new consequence of that act and must be drawn
  // there in words — which account it moves to, and that the standing charge
  // continues on it."* The same ruling requires the REVERSE EDGE in the same
  // section. Both halves are asserted here, and so is the branch where there
  // is no owner account, because a fault and a silence are different facts.

  it("CR-056 W6 — the PORT maps the four served impact fields instead of nulling them", async () => {
    // ⚠ **THIS CASE EXISTS BECAUSE PROVING THE OTHERS RED FOUND A HOLE IN THEM
    // (hard-won law 7 doing its job).** The two panel cases below hand a
    // `CloseImpact` straight to the wizard, so they test the PANELS and say
    // nothing about the PORT — the server could serve all four fields and the
    // port could go on mapping them to `null`, and both would still pass. That
    // is hard-won law 2 exactly: built, not wired, every test green. Restoring
    // the old `units_occupied_after: null` block was run against the suite and
    // **nothing went red**, which is what this case fixes.
    const served = {
      landing: "short",
      open_sub_accounts: 0,
      units_occupied_after: { occupied: 1, total: 3 },
      owner_on_record: "Miller Property LLC",
      owner_is_free_text: false,
      common_area_account_no: "AC-2026-00052",
      unit_falls_to: {
        available: true,
        account_id: "018f6f6a-0000-7000-8000-0000000000aa",
        account_no: "AC-2026-00052",
        br_ref: "BR-MET-105a · BR-MET-1010",
        reason: null,
      },
      vacant_base_charges: [
        {
          service: "electric",
          name: "Electric",
          stored: "12.0000",
          display: "12.00",
          currency: "USD",
        },
      ],
    };
    const client = {
      get: async () => ({ data: served, status: 200, ok: true }),
    } as unknown as Parameters<typeof closeImpactPort>[0];
    const impact = await closeImpactPort(client).read("acc-10432");
    expect(impact.units_occupied_after).toEqual({ occupied: 1, total: 3 });
    expect(impact.owner_on_record).toBe("Miller Property LLC");
    expect(impact.owner_is_free_text).toBe(false);
    expect(impact.common_area_account_no).toBe("AC-2026-00052");
    expect(impact.unit_falls_to?.account_no).toBe("AC-2026-00052");
    expect(impact.vacant_base_charges?.[0].display).toBe("12.00");
    // …and the one field that is still deliberately not served stays null.
    expect(impact.vacant_base_charge).toBeNull();
  });

  it("CR-056 W6 — a server that serves none of them still yields null, never 0 or false", async () => {
    // DEF-669's own correction, kept: `undefined` renders as `0 of 0` and as
    // "not free text", which is the screen stating measurements nobody took.
    const client = {
      get: async () => ({ data: { landing: "settled" }, status: 200, ok: true }),
    } as unknown as Parameters<typeof closeImpactPort>[0];
    const impact = await closeImpactPort(client).read("acc-10432");
    expect(impact.units_occupied_after).toBeNull();
    expect(impact.owner_is_free_text).toBeNull();
    expect(impact.unit_falls_to).toBeNull();
    expect(impact.vacant_base_charges).toBeNull();
  });

  it("CR-056 W6 task 26 — the impact names the owner's account and says the charge comes off it again", () => {
    const html = renderWizard(impactStep, {
      detail: detail(),
      access: "Full",
      impact: {
        ...IMPACT_BASE,
        units_occupied_after: { occupied: 1, total: 3 },
        owner_on_record: "Miller Property LLC",
        owner_is_free_text: false,
        common_area_account_no: "AC-2026-00052",
        unit_falls_to: {
          available: true,
          account_id: "018f6f6a-0000-7000-8000-0000000000aa",
          account_no: "AC-2026-00052",
          br_ref: "BR-MET-105a · BR-MET-1010",
          reason: null,
        },
        vacant_base_charges: [
          {
            service: "electric",
            name: "Electric",
            stored: "12.0000",
            display: "12.00",
            currency: "USD",
          },
        ],
      },
    });
    const shown = visible(html);
    // ⚠ **THE `1 of 3` OCCUPANCY COUNT WENT WITH p115's PANEL (PO
    // 2026-09-24).** It was one of the six *unstated consequences*, and the
    // whole panel is deleted; what CR-056 W6 task 26 actually delivered — the
    // owner's account NAMED, and the standing charge continuing on it — is on
    // the row the drawing keeps, and is what this case checks.
    expect(shown).not.toContain("1 of 3");
    // WHICH account it moves to…
    expect(shown).toContain("AC-2026-00052");
    // …that the standing charge continues on it, and the REVERSE EDGE — as TWO
    // sentences of six words rather than the one of thirty this asserted
    // before, which was a B14 rule 33 breach on a live screen.
    expect(shown).toContain("Billed to AC-2026-00052 while empty");
    expect(shown).toContain("It stops when someone moves in");
    // …on the FACE of the step, where it cannot be folded away (B19 §15.7).
    expect(html).toContain('data-step-section="unit"');
    // ⛔ **THE `1 of 3` OCCUPANCY COUNT WENT WITH p115's PANEL (PO
    // 2026-09-24).** What CR-056 W6 task 26 actually delivered — the owner's
    // account NAMED, and the standing charge continuing on it — is on the row
    // the drawing keeps, asserted above.
    expect(shown).not.toContain("1 of 3");
    // and nothing characterises an owner who HAS an account as free text
    expect(shown).not.toContain("is a name on the premise record");
  });

  it("CR-056 W6 task 26 — an address with no owner account is a FAULT, not a blank", () => {
    // PO 2026-08-31, ruling 1 consequence 3: *"no lines because nothing falls
    // to it"* and *"no lines although the premises HAS an unoccupied unit"*
    // are different facts and only one of them is good news.
    const html = renderWizard(impactStep, {
      detail: detail(),
      access: "Full",
      impact: {
        ...IMPACT_BASE,
        owner_on_record: "Miller Property LLC",
        owner_is_free_text: true,
        unit_falls_to: {
          available: false,
          account_id: null,
          account_no: null,
          br_ref: "BR-MET-105a · BR-MET-1010",
          reason: "this address has no owner account to post to.",
        },
      },
    });
    const shown = visible(html);
    // A FAULT — *"this address has no owner account"* — and never a blank, and
    // never the same sentence as *the read did not answer*, which is the third
    // state and is asserted in its own case above.
    expect(shown).toContain("This address has no owner account");
    expect(html).toContain('data-step-section="unit"');
    // …and it is NOT the unread sentence.
    expect(shown).not.toContain("Not served by the close read.");
  });

  it("DEF-650: two of the four vacancy dispositions cannot post anywhere, and say so", () => {
    const options = vacancyDispositions({
      commonAreaAccountNo: "MA-1408",
      ownerOnRecord: "Ridge Property LLC",
      ownerIsFreeText: true,
    });
    expect(options.map((option) => option.id)).toEqual([
      "vacant_base_only",
      "vacant_service_off",
      "landlord_billed",
      "occupied_owner_billed",
    ]);
    // ① posts to a REAL master account and ② posts to nobody — both buildable.
    expect(options[0].blockedReason).toBeNull();
    expect(options[1].blockedReason).toBeNull();
    // ③ and ④ post to free text, which is DEF-650. BR-MET-105 sends the empty
    // unit's $30.50 to "the owner / landlord", and a charge cannot be sent to a
    // name — so the two carry the reason instead of being dropped.
    expect(options[2].blockedReason).toContain("free text");
    expect(options[3].blockedReason).toContain("free text");
    // BR-MET-036: one of them is what the unit becomes by DERIVATION.
    expect(options.filter((option) => option.isDerivedDefault)).toHaveLength(1);
    // With no common-area account there is nothing for base charges to bill to,
    // and ① states that rather than naming a master that does not exist.
    const noMaster = vacancyDispositions({
      commonAreaAccountNo: null,
      ownerOnRecord: null,
      ownerIsFreeText: true,
    });
    expect(noMaster[0].blockedReason).not.toBeNull();
    expect(noMaster[0].description).not.toContain("MA-");
  });
});

describe("B19 §15.10 · §15.12 item 6 — the three sentences that must NOT be constants", () => {
  it("BR-CUS-082 supersedes `Dunning · Stops on close` the moment a balance survives", () => {
    // The captured screenshot is `Refusal · excess`, where nothing is owed. Under
    // `Short by` the debt is CHASED ON and the ladder restarts at TIER 1 — the
    // opposite sentence, on the same panel.
    expect(dunningOnClose("short").ruleRef).toBe("BR-CUS-082");
    expect(dunningOnClose("short").text).toContain("tier 1");
    expect(dunningOnClose("short").text).not.toContain("Stops");
    expect(dunningOnClose("settled").text).toContain("Stops at the close");
    expect(dunningOnClose("refund_due").text).toContain("Stops at the close");
    // Unknown is its OWN answer, not the captured one.
    expect(dunningOnClose(null).text).not.toContain("Stops at the close");
    for (const landing of MONEY_LANDINGS) {
      expect(dunningOnClose(landing).text.length).toBeGreaterThan(0);
    }
  });

  it("the payment-plan label follows the acceleration, and is absent when there is no plan", () => {
    expect(paymentPlanOnClose("settled", null)).toBeNull();
    const short = paymentPlanOnClose("short", { paid: 4, of: 9 });
    expect(short?.text).toContain("accelerated");
    expect(short?.text).not.toContain("nothing outstanding");
    expect(paymentPlanOnClose("refused_excess", { paid: 4, of: 9 })?.text).toContain(
      "nothing outstanding",
    );
    expect(paymentPlanOnClose(null, { paid: 4, of: 9 })?.text).not.toContain(
      "nothing outstanding",
    );
  });

  it("the six outgoing messages DEFAULT from the outcome — no demand letter to a customer owed money", () => {
    const captured = outgoingMessageDefaults("refused_excess");
    const refundNotice = captured.find((row) => row.id === "refund_notice");
    const demand = captured.find((row) => row.id === "shortfall_letter");
    // B19 §15.11's screenshot has these two the wrong way round in a scenario
    // where money is owed BACK — "drawn as-is they would post a demand letter
    // to a customer owed $13.12".
    expect(demand?.on).toBe(false);
    expect(refundNotice?.on).toBe(false);
    // A refund leaves the building → the refund notice goes, the demand does not.
    const refunding = outgoingMessageDefaults("refund_due");
    expect(refunding.find((row) => row.id === "refund_notice")?.on).toBe(true);
    expect(refunding.find((row) => row.id === "shortfall_letter")?.on).toBe(false);
    // A shortfall remains → the demand goes, the refund notice does not.
    const shortfall = outgoingMessageDefaults("short");
    expect(shortfall.find((row) => row.id === "shortfall_letter")?.on).toBe(true);
    expect(shortfall.find((row) => row.id === "refund_notice")?.on).toBe(false);
    // The four that do not depend on money are constant in every landing.
    for (const landing of MONEY_LANDINGS) {
      const rows = outgoingMessageDefaults(landing);
      expect(rows).toHaveLength(6);
      expect(rows.find((row) => row.id === "final_bill")?.on).toBe(true);
      expect(rows.find((row) => row.id === "owner_notice")?.on).toBe(true);
    }
  });

  // ══════════════════════════════════════════════════════════════════════
  // WHAT FIXING THE 404 MADE REACHABLE — `DEF-CUS-5095`
  // ══════════════════════════════════════════════════════════════════════
  // Step 4's `close-impact` read 404'd on every tenant (`DEF-CUS-5072`), so no
  // path was ever offered and the step showed a stated absence. Fixing one
  // character made the four paths render — and with them the server's own
  // `reason` for a BLOCKED path, which is 1,200 characters of engineering prose
  // naming `BR-MET-105a`, `CR-056` and a PO ruling, printed twice, on the step
  // where a clerk decides where a departing tenant's debt goes.
  //
  // ⚠ **THE GENERAL LESSON, AND IT COST TWO SCREENS TODAY:** when a transport
  // fix makes a screen reachable for the first time, **every string on it is
  // new and none of it has been read.** `DEF-CUS-5087` is the same mechanism on
  // the close-out screen, found the same way — by clicking it.
  it("a blocked shortfall path says why in OUR words, never the server's", () => {
    // The server's real sentence, verbatim — a fixture with clean strings in it
    // would prove nothing about the screen, which is `screenVoice.guard`'s own
    // reasoning one wizard over.
    const served = ourBlockedReasons(
      [
        {
          path: "pursue",
          label: "Pursue it",
          description: "",
          blockedReason: null,
          consequence: "",
          targetAccountNo: null,
        },
        {
          path: "transfer",
          label: "Tie it back to the master account",
          description: "",
          blockedReason:
            "this address has no owner account to post to. BR-MET-105a makes the owner a real " +
            "party and CR-056 gives every address its owner a Master Account. The PO ruled on " +
            "2026-09-01 that an owner's account appears when the owner is IDENTIFIED, never at " +
            "a migration that would invent one.",
          consequence: "",
          targetAccountNo: null,
        },
      ],
      t,
    );
    // An unblocked path is untouched — the map must not invent a refusal.
    expect(served[0].blockedReason).toBeNull();
    // And the blocked one says it in six words.
    expect(served[1].blockedReason).toBe("This address has no owner account.");
    // ⛔ Not one word of the server's reasoning survives into what renders.
    const rendered = JSON.stringify(served);
    for (const leak of ["BR-MET-105a", "CR-056", "The PO ruled", "IDENTIFIED", "migration"]) {
      expect(rendered).not.toContain(leak);
    }
  });

  it("the read-back renders the six from the landing rather than from six literals", () => {
    const html = renderWizard(`${accountMoveOutPath("acc-10432")}?step=4`, {
      detail: detail(),
      access: "Full",
    });
    // ⚠ **`What we'll send` IS THE ONE PANEL IN SIX REPORTS THE PO DID NOT ASK
    // TO CHANGE** (specification sheet 2, *kept on purpose*), and the merge
    // moved it from old step 6 to step 4 without touching it. It is drawn by
    // `CloseImpactPanels`' own matrix now rather than by `OutgoingMessages`,
    // which was old step 6's copy of the same six rows — two components
    // rendering one list is how they come to disagree, so one went.
    expect(html).toContain('data-move-matrix="messages"');
    expect(visible(html)).toContain("Shortfall demand letter");
    expect(visible(html)).toContain("Deposit refund notice");
    // Nothing has said how the money lands, so neither money-dependent message
    // is ticked on a guess. Its two `Not sent` rows are a consequence of the
    // settlement, not copy.
    expect(visible(html)).toContain("Not queued here");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE STEP LINE, AGAINST THE DRAWING — blueprint pages 98–106, lane A 2026-09-13
// ══════════════════════════════════════════════════════════════════════════
describe("the move-out step line says WHICH step, not only which number", () => {
  it("BR-SHL-046: `Step N of 6 · <the step>` on every one of the six", () => {
    // The blueprint writes `Step 1 of 6 · Find account` under the title of all
    // six screens. This line read `Step 1 of 6` from the day it was written, so
    // a clerk reopening a parked move-out at step 4 was told a number and not
    // what step 4 asks for.
    //
    // ⚠ **THE NAME IS READ OFF THE RENDER, NOT OFF `step.en`.** A catalogue
    // entry BEATS a `defaultValue`, so `MOVE_OUT_STEPS[2]` carries `Settle the
    // money` as its English while `customers.moveOut.step.settlement` renders
    // `Final bill & deposit`; asserting the fallback would pin a string no
    // clerk ever sees.
    const named: string[] = [];
    for (const index of MOVE_OUT_STEPS.keys()) {
      const html = renderWizard(`${accountMoveOutPath("acc-10432")}?step=${index + 1}`, {
        detail: detail(),
        access: "Full",
      });
      const line = new RegExp(
        `Step ${index + 1} of ${MOVE_OUT_STEPS.length}\\s*·\\s*([^<\\n]{2,40})`,
      ).exec(visible(html));
      // ⚠ Both sides of this must DIFFER in the failing case or it is a check
      // that cannot fail. The left is what was found; the right is what a
      // passing render holds, and they part company exactly when the name is
      // missing — which is the whole subject of this case.
      expect({ step: index + 1, line: line === null ? null : line[0] }).toEqual({
        step: index + 1,
        line: line === null ? "NO NAME ON THE STEP LINE" : line[0],
      });
      named.push((line?.[1] ?? "").trim());
    }
    // Six lines, six DIFFERENT names — a constant would satisfy "a name is
    // present" and tell a clerk nothing, which is the failure this guards.
    expect(new Set(named).size).toBe(MOVE_OUT_STEPS.length);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// PO RULING 2026-09-19 — STEPS 3, 4 AND 5 BUILT TO THEIR DRAWING, AND THE
// PLAN NAME ON STEP 1 (blueprint p110–p115)
// ══════════════════════════════════════════════════════════════════════════
describe("PO 2026-09-19 — the move-out wizard, built to its drawing", () => {
  const step = (n: number): string => `${accountMoveOutPath("acc-10432")}?step=${n}`;

  // ── STEP 1 · the one change the PO asked for ────────────────────────────
  it("step 1 shows the plan the unit stands on — *\"you should have plan name also in this\"*", () => {
    const withPlan = {
      ...detail(),
      unit_plan: { name: "Residential", code: "SCW-RES", version: 1, since: "2024-02-14" },
    };
    const html = renderWizard(step(1), { detail: withPlan, access: "Full" });
    // p110 draws it `SCW-RES · Residential · v1`, and step 6's recap prints the
    // same line off the same formatter.
    expect(visible(html)).toContain("SCW-RES · Residential · v1");
    // ⚠ B14 rule 31 — no database id is ever the visible value of a field, and
    // the payload deliberately carries none to be leaked.
    expect(html).not.toContain("rate_plan_id");
  });

  it("step 1 states the absence rather than composing a line out of nulls", () => {
    // Three different REAL absences arrive as one null: the account names no
    // unit, the unit stands on no plan, or the plan is no longer published.
    const html = renderWizard(step(1), { detail: { ...detail(), unit_plan: null }, access: "Full" });
    expect(visible(html)).not.toContain("· v");
    expect(visible(html)).not.toContain("undefined");
  });

  it("unitPlanLine is pure, and drops the parts it was not given", () => {
    expect(unitPlanLine(null)).toBeNull();
    expect(unitPlanLine(undefined)).toBeNull();
    expect(unitPlanLine({ name: null, code: null, version: null, since: null })).toBeNull();
    expect(unitPlanLine({ name: "Residential", code: "SCW-RES", version: 1, since: null })).toBe(
      "SCW-RES · Residential · v1",
    );
    // A plan with no code is still a plan; the line shortens, it does not gain
    // an empty segment or the word "null".
    expect(unitPlanLine({ name: "Residential", code: null, version: 2, since: null })).toBe(
      "Residential · v2",
    );
    expect(unitPlanLine({ name: null, code: "SCW-RES", version: null, since: null })).toBe(
      "SCW-RES",
    );
  });

  // ── BR-CUS-056 · the day after ──────────────────────────────────────────
  it("dayAfter is calendar arithmetic with no clock in it, and refuses rubbish", () => {
    expect(dayAfter("2026-01-28")).toBe("2026-01-29");
    // month, year and LEAP boundaries — the three a hand-rolled +1 gets wrong
    expect(dayAfter("2026-01-31")).toBe("2026-02-01");
    expect(dayAfter("2026-12-31")).toBe("2027-01-01");
    expect(dayAfter("2028-02-28")).toBe("2028-02-29");
    expect(dayAfter("2026-02-28")).toBe("2026-03-01");
    // …and an undated flow gets "", which the screen renders as an absence
    // rather than as a date it made up.
    expect(dayAfter("")).toBe("");
    expect(dayAfter("not a date")).toBe("");
    expect(dayAfter("2026-13-45")).toBe("");
  });

  it("readsProgress counts what the clerk keyed, and a blank row is NEITHER", () => {
    expect(readsProgress({})).toEqual({ taken: 0, estimated: 0, total: 0 });
    expect(
      readsProgress({
        "ast-1": { meterNo: "M-4021", value: "52410", estimate: false, readAt: "" },
        "ast-2": { meterNo: "M-4022", value: "", estimate: true, readAt: "" },
        // The honest third state: offered, and answered with nothing.
        "ast-3": { meterNo: "M-4023", value: "   ", estimate: false, readAt: "" },
      }),
    ).toEqual({ taken: 1, estimated: 1, total: 3 });
  });

  // ── STEP 3 · the final bill, assembled from BOTH reads ──────────────────
  it("step 3 draws the priced lines, the export credit and the net — from two reads", () => {
    const preview: FinalBillPreview = {
      priced: true,
      lines: [
        {
          description: "Electric",
          amount: "71.4000",
          quantity: "634",
          unit: "kWh",
          estimated: false,
          service: "electric",
          unitPrice: "0.1126",
          kind: "usage",
        },
        {
          description: "Water",
          amount: "17.7000",
          quantity: "14",
          unit: "kgal",
          estimated: true,
          service: "water",
          unitPrice: "1.2643",
          kind: "usage",
        },
      ],
      total: "89.1000",
      currency: "USD",
      periodStart: "2025-12-28",
      periodEnd: "2026-01-28",
      // `DEF-CUS-5931` — this figure came off reads the clerk keyed on step 2
      // and nobody has committed. The wizard's own path, so it is the default
      // shape of this fixture rather than a variant of it.
      subtotal: "89.1000",
      taxTotal: "0.0000",
      fromUncommittedReads: true,
      unavailable: null,
      unavailableDetail: null,
    };
    const html = renderWizard(step(3), {
      detail: detail(),
      access: "Full",
      // ⚠ **SEEDED UNDER THE EMPTY DATE ON PURPOSE, AND IT IS A LIMIT OF THIS
      // HARNESS RATHER THAN OF THE SCREEN.** The move-out date is COMPONENT
      // state — the clerk types it on step 2 — so a static render cannot set
      // it, and the read keys carry it. Seeding the key the component actually
      // asks for is what lets this case see the rendered table at all; a
      // fixture that cannot address what the component asks for is the check
      // that does not check, which is what `closeImpactQueryKey` exists to
      // stop. The DATE's own effect on the read is proved in the port case
      // below, where the URL is inspected directly.
      preview,
      impact: {
        ...IMPACT_BASE,
        landing: "short",
        money: {
          currency: "USD",
          priorBalance: { stored: "247.3000", display: "247.30" },
          finalBill: { stored: "89.1000", display: "89.10" },
          exportCredit: { stored: "0.0000", display: "0.00" },
          finalBillNet: { stored: "89.1000", display: "89.10" },
          outstanding: { stored: "336.4000", display: "336.40" },
          depositHeld: { stored: "150.0000", display: "150.00" },
          depositInterest: { stored: null, display: null },
          unappliedCredit: { stored: "0.0000", display: "0.00" },
          applied: { stored: "150.0000", display: "150.00" },
          net: { stored: "186.4000", display: "186.40" },
          shortfall: { stored: "186.4000", display: "186.40" },
          excess: { stored: "0.0000", display: "0.00" },
          settledFromDeposit: { stored: "150.0000", display: "150.00" },
          refundAmount: { stored: "0.0000", display: "0.00" },
        },
      },
    });
    const shown = visible(html);
    // The LINE column composes description · quantity+unit · the estimate flag
    // — rule 3, a quantity never travels without its unit.
    // ⚠ **THE DRAWN TABLE SPLITS SERVICE FROM LINE (PO 2026-09-24)** —
    // `Service · Line · Period · Quantity · Amount` — so *Electric · 634 kWh*
    // is no longer one welded string.
    expect(shown).toContain("Electric");
    expect(shown).toContain("634 kWh");
    expect(shown).toContain("Water");
    expect(shown).toContain("14 kgal");
    expect(shown).toContain("estimated");
    // Money DISPLAYS to 2 decimals however many it is stored to (rule 2).
    expect(shown).toContain("$71.40");
    expect(shown).not.toContain("71.4000");
    // DEF-CUS-9142 · PO 2026-10-02 (*"Show unit prices with up to 4 decimals
    // and keep every total at 2."*): the rate beside the quantity is a UNIT
    // PRICE, so `0.1126` reads `$0.1126` — it read `$0.11` through MoneyCell.
    expect(shown).toContain("$0.1126");
    expect(shown).toContain("$1.2643");
    expect(shown).not.toMatch(/@ \$0\.11(?!\d)/);
    // The export-credit row and the net come from the SETTLEMENT, not the
    // preview — BR-MET-107 is metering's fact and the engine prices no line
    // for it. Subtracting it in the preview would double-count it.
    // ⚠ **`Unbanked export credit` IS NOT A ROW OF THE DRAWN TABLE, AND THE
    // FIGURE IS NOT LOST.** `03-bill-and-deposit.png` draws SIX money rows —
    // prior balance · final bill, net · deposit applied · deposit interest ·
    // unapplied credit · **Short by** — and `final_bill_net` is already NET of
    // BR-MET-107's credit, which is what its name says and what the port's own
    // comment says (*"neither half computes the other's figure — subtracting
    // the credit here would double-count it"*). Drawing it again would show a
    // clerk a credit that has already been taken off the line beneath it.
    // **Reported to the PO as a deliberate difference from the old screen.**
    expect(shown).not.toContain("Unbanked export credit");
    expect(shown).toContain("Final bill, net");
    // ⚠ **THE INTERMEDIATE `Outstanding` SUBTOTAL — `$336.40` — IS NOT A ROW
    // OF THE DRAWN TABLE EITHER.** Both drawings list six rows and no subtotal
    // between them; the served figure is untouched, and what the drawing drops
    // is a line restating a sum the clerk can see. Ending on the verdict
    // figure is the property that matters and it is unchanged.
    expect(shown).not.toContain("$336.40");
    expect(shown).toContain("$186.40");
    // ⛔ …and the five-landings table it used to be marked on is DELETED
    // (PO 2026-09-24). The landing a clerk ACTS on is the `Short by` row.
    expect(html).not.toContain('data-move-matrix="landings"');
    expect(shown).toContain("Short by");
    // ⚠ **AND THE TABLE SAYS WHAT IT WAS PRICED FROM (`DEF-CUS-5931`, PO
    // 2026-09-20 *"option b is correct"*).** Six words, B14 rule 33's cap on
    // a FACT, and no rationale on screen.
    expect(shown).toContain("Priced from reads not yet committed.");
    expect(html).toContain('data-tracks="final-bill-from-keyed-reads"');
  });

  it("step 3 says NOTHING about keyed reads when the closing read is committed", () => {
    // ⚠ **THE OTHER DIRECTION, AND IT IS THE HALF THAT CAN ROT.** A sentence
    // that is always on screen tells a clerk nothing; this one is a claim
    // about THIS bill, so a preview priced from a read taken in the field
    // before the wizard opened must not carry it. Without this case the line
    // could be hard-coded and every other assertion would still pass —
    // hard-won law 7's *ask what would make this check pass wrongly*.
    const html = renderWizard(step(3), {
      detail: detail(),
      access: "Full",
      preview: {
        priced: true,
        lines: [
          {
            description: "Electric",
            amount: "71.4000",
            quantity: "634",
            unit: "kWh",
            estimated: false,
            service: "electric",
            unitPrice: "0.1126",
            kind: "usage",
          },
        ],
        total: "71.4000",
        subtotal: "71.4000",
        taxTotal: "0.0000",
        currency: "USD",
        periodStart: "2025-12-28",
        periodEnd: "2026-01-28",
        fromUncommittedReads: false,
        unavailable: null,
        unavailableDetail: null,
      },
    });
    const shown = visible(html);
    // ⚠ **THE DRAWN TABLE SPLITS SERVICE FROM LINE (PO 2026-09-24).**
    // `03-bill-and-deposit.png` draws *Service · Line · Period · Quantity ·
    // Amount*, so *Electric · 634 kWh* is no longer one welded string — and
    // the RATE rides with the quantity, as a printed bill sets it.
    expect(shown).toContain("Electric");
    expect(shown).toContain("634 kWh");
    expect(shown).not.toContain("Priced from reads not yet committed.");
    expect(html).not.toContain('data-tracks="final-bill-from-keyed-reads"');
  });

  it("step 3 states every absence and invents nothing when neither read answers", () => {
    const html = renderWizard(step(3), { detail: detail(), access: "Full" });
    const shown = visible(html);
    // ⚠ NEVER $0.00 — on a final settlement that is the claim that this
    // customer owes nothing, which is a money claim nobody measured.
    expect(shown).not.toContain("$0.00");
    expect(shown).toContain("Not worked out yet");
    expect(html).toContain('data-tracks="short-by"');
  });

  // ══════════════════════════════════════════════════════════════════════
  // DEF-CUS-5920 — STEP 4's FOUR RADIOS RENDERED LIVE OVER A POST THAT
  // REFUSED EVERY TIME (hard-won law 2's mirror: a dead control over a live
  // screen is one defect; a LIVE control that can never succeed is the other)
  // ══════════════════════════════════════════════════════════════════════
  const PATHS = [
    { path: "collect", enabled: true, br_ref: "BR-BIL-013", reason: null },
    { path: "payment_plan", enabled: true, br_ref: "BR-BIL-013", reason: null },
    { path: "transfer", enabled: true, br_ref: "BR-CUS-097", reason: null },
  ];

  it("PO 2026-09-24 — with NO landing, step 3 offers no shortfall paths at all", () => {
    // **`DEF-CUS-5920`, PINNED AND MOVED TO ITS NEW STEP.** The skip test once
    // read `landing !== null && landing !== "short"`, which is FALSE under a
    // null landing — and the landing was null on every account until a final
    // bill was stated. So the four paths and `Record this decision` rendered
    // ENABLED, and `POST /accounts/{id}/settle-shortfall` refused
    // `no_shortfall` every single time. The server's own `step_4_live` is
    // False here and is still what decides it.
    //
    // ⚠ **THE FIELD IS STILL CALLED `step_4_live` AND THE STEP IS NOW 3.** The
    // NAME is one step out of date; the VALUE is not. Renaming a wire field is
    // not this lane's change, and what matters is the property: the control is
    // not offered over a door that would refuse it.
    //
    // ⚠ **AND IT NO LONGER *SAYS* ANYTHING.** The six-step shape rendered
    // *"The subtraction has not run yet."* here. That is RATIONALE — why a
    // control is absent — which B14 rule 33 puts at ZERO words on screen, and
    // the PO deleted it on 2026-09-24. A clerk with no shortfall simply sees
    // no shortfall section.
    const html = renderWizard(step(3), {
      detail: detail(),
      access: "Full",
      impact: {
        ...IMPACT_BASE,
        landing: null as unknown as CloseImpact["landing"],
        gaps: ["final_bill_not_stated"],
        step_4_live: false,
        shortfall_paths: PATHS,
      },
    });
    expect(html).not.toContain("data-move-matrix=\"shortfall-paths\"");
    expect(html).not.toContain("data-shortfall-confirm");
    expect(visible(html)).not.toContain("The subtraction has not run yet.");
  });

  it("PO 2026-09-24 — on the `short` landing the three paths ARE offered on step 3, unselected", () => {
    const html = renderWizard(step(3), {
      detail: detail(),
      access: "Full",
      impact: {
        ...IMPACT_BASE,
        landing: "short",
        step_4_live: true,
        shortfall_paths: PATHS,
        money: null,
      },
    });
    expect(html).toContain("data-move-matrix=\"shortfall-paths\"");
    for (const path of ["collect", "payment_plan", "transfer"]) {
      expect(html).toContain(`data-shortfall-pick="${path}"`);
    }
    // PO 2026-10-12 — *"we will not write off at the time of move out"*: no
    // write-off row, no reason dropdown, no note box.
    expect(html).not.toContain('data-shortfall-pick="write_off"');
    expect(html).not.toContain("data-shortfall-write-off");
    expect(visible(html)).not.toContain("Write it off");
    // ⚠ **THE THREE PROPERTIES `BR-CUS-097` MADE LOAD-BEARING SURVIVE THE
    // MERGE**, which is the whole reason they are re-asserted here rather than
    // assumed to have travelled.
    // 1 · NOTHING IS PRESELECTED — a default would be the product choosing
    //     where a departing tenant's debt goes.
    expect(html).not.toContain('checked=""');
    // 2 · THE TARGET IS NAMED, NEVER TYPED — no free-text account field.
    expect(html).not.toContain('name="target_account"');
    // 3 · WHO MAY TAKE EACH PATH is on the row, off `PATH_ASKS` — p113's own
    //     column, now a column of the merged table rather than a second one.
    //     Every remaining path is any clerk's (write-off left 2026-10-12).
    expect(visible(html)).not.toContain("A supervisor");
    expect(visible(html)).toContain("Any clerk");
    expect(visible(html)).not.toContain("admin approval");
  });

  it("PO 2026-09-24 — a settled account draws no shortfall section, and says nothing about it", () => {
    // ⚠ **THE SIX-STEP SHAPE DREW `Shortfall · skipped`, GREYED, AND KEPT THE
    // SEGMENT** because the step number was an INDEX (BR-SHL-046). There is no
    // segment any more: the shortfall is ABSORBED into step 3 and simply is
    // not rendered when there is nothing to settle. *"Nothing is left to
    // decide"* went with it — rationale, at zero words (B14 rule 33).
    const html = renderWizard(step(3), {
      detail: detail(),
      access: "Full",
      impact: { ...IMPACT_BASE, landing: "settled", step_4_live: false, shortfall_paths: PATHS },
    });
    expect(html).not.toContain("data-move-matrix=\"shortfall-paths\"");
    expect(visible(html)).not.toContain("skipped");
    expect(visible(html)).not.toContain("Nothing is left to decide");
  });


  // ── THE READ THAT UNBLOCKS THE CHAIN ────────────────────────────────────
  it("the close-impact read STATES the final bill and the accrual date", async () => {
    // Without `?final_bill=` the settlement reports `final_bill_not_stated`,
    // no landing and fourteen null totals — which is what every account in the
    // product answered, because no caller ever stated one.
    const asked: string[] = [];
    const client = {
      get: async (url: string) => {
        asked.push(url);
        return { data: { landing: "short", step_4_live: true }, status: 200, ok: true };
      },
    } as unknown as Parameters<typeof closeImpactPort>[0];
    await closeImpactPort(client).read("acc-10432", {
      finalBill: "89.1000",
      asOf: "2026-01-28",
    });
    expect(asked[0]).toContain("final_bill=89.1000");
    expect(asked[0]).toContain("as_of=2026-01-28");
    // ⚠ THE LEADING SLASH — `DEF-CUS-4010` and `DEF-CUS-5072`, twice on this
    // screen. Without it every tenant gets a 404 and the screen says nothing.
    expect(asked[0].startsWith("/accounts/")).toBe(true);

    // …and with nothing to state it asks the bare path rather than `?=`.
    asked.length = 0;
    await closeImpactPort(client).read("acc-10432");
    expect(asked[0]).toBe("/accounts/acc-10432/close-impact");
  });

  // ═══════════════════════════════════════════════════════════════════════
  // 🔒 `DEF-CUS-5927` — THE WRITE STATES WHAT THE READ STATES
  // ═══════════════════════════════════════════════════════════════════════
  // ⚠ **THIS CASE CANNOT SEE THE DEFECT ON ITS OWN AND DOES NOT CLAIM TO.**
  // Both halves behaved correctly in isolation — the backend's `tc16`
  // (`test_br_bil_013_final_bill_preview.py`) proves the service records a
  // decision when the figure is stated and refuses when it is not, and every
  // case above proves the READ states it. The fault was that the two
  // disagreed, which only a real stack shows: `POST` with `{"path":"collect"}`
  // answered **409 `customers.move_out.no_shortfall`, `params {landing: null,
  // gaps: ["final_bill_not_stated"]}`** on `AC-2026-00031` while the screen
  // printed `Short by $1,591.85`.
  //
  // What this case IS: the guard that goes RED if the body ever loses the two
  // terms again. It asserts the BODY, which is the thing that was wrong.
  it("DEF-CUS-5927 — the shortfall WRITE carries the same two terms the read sends", async () => {
    const posted: { url: string; body: unknown }[] = [];
    const client = {
      post: async (url: string, body: unknown) => {
        posted.push({ url, body });
        return { data: {}, status: 200, ok: true };
      },
    } as unknown as Parameters<typeof closeImpactPort>[0];

    await settleShortfall(
      "acc-10432",
      "collect",
      { finalBill: "789.42", asOf: "2026-09-30" },
      client,
    );
    // The server's own wire names — `api._settlement_payload` parses these two
    // and `shortfall_decision` hands them to `settlement_for`.
    expect(posted[0].body).toEqual({
      path: "collect",
      final_bill: "789.42",
      as_of: "2026-09-30",
    });
    // ⚠ THE LEADING SLASH — `DEF-CUS-5072`. On a WRITE the missing character
    // is a 404 where a business refusal belongs.
    expect(posted[0].url).toBe("/accounts/acc-10432/settle-shortfall");

    // …and an unstated term is ABSENT rather than empty: `""` would be a
    // stated figure of nothing, which the service refuses by name.
    posted.length = 0;
    await settleShortfall("acc-10432", "collect", { finalBill: null, asOf: null }, client);
    expect(posted[0].body).toEqual({ path: "collect" });
  });

  // 🔒 CR-185-BRC10 · `OQ-1250` CLOSED 2026-10-14 → (a), PO D5 — the tie-back
  // POSTS. The screen's *posted* sentence must come from the SERVER's
  // `posting.posted`, never from the path the clerk chose: a refused posting
  // refuses the whole decision, so a `transfer` that answered 200 without
  // `posted: true` (collect, a payment plan) must still read *Recorded*.
  it("CR-185-BRC10 — the write returns the server's verdict: recorded, posted when the final bill is sent", async () => {
    // ONLY MONEY IN THE BOOKS MOVES (coordinator ruling 2026-10-14): on an open account the
    // server RECORDS the tie-back and previews the figure; the final bill's
    // issue posts it. The screen reads `posts_at`, never the path it chose.
    let answer: unknown = {
      posting: { posted: false, posts_at: "final_bill_issue",
                 amount: { display: "328.70" }, to_account_no: "AC-2026-00053" },
    };
    const client = {
      post: async () => ({ data: answer, status: 200, ok: true }),
    } as unknown as Parameters<typeof closeImpactPort>[0];
    expect(await settleShortfall("acc-10432", "transfer", {}, client)).toEqual({
      posted: false, postsAtCompletion: true, amount: "328.70", toAccountNo: "AC-2026-00053",
    });
    answer = { posting: { posted: true, entry_id: "je-1" } };
    expect(await settleShortfall("acc-10432", "transfer", {}, client)).toMatchObject({
      posted: true, postsAtCompletion: false,
    });
    answer = {};
    expect(await settleShortfall("acc-10432", "collect", {}, client)).toMatchObject({
      posted: false, postsAtCompletion: false,
    });
  });

  it("CR-185-BRC10 — the completion screen says Posted, or when it will move", () => {
    const render = (balance: unknown) =>
      renderToStaticMarkup(
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts/acc-10432/move-out`]}>
          <Routes>
            <Route
              path="/:tenant/accounts/:accountId/move-out"
              element={
                <MoveOutDone
                  result={{ ...moveOutResult(), balance_to_owner: balance } as never}
                  t={t}
                  timeZone="UTC"
                  dateFormat="MM/DD/YYYY"
                />
              }
            />
          </Routes>
        </MemoryRouter>,
      );
    const posted = render({ posted: true, amount: { stored: "328.7000", display: "328.70" } });
    expect(posted).toContain("move-out-done-balance-to-owner");
    expect(posted).toContain("$328.70");
    expect(posted).toContain("$328.70 · Posted");
    const pending = render({ posted: false, pending: true, amount: { stored: "917.1000", display: "917.10" } });
    expect(pending).toContain("move-out-done-balance-to-owner");
    expect(pending).toContain("$917.10 · Moves to the owner when the final bill is sent");
    expect(pending).not.toContain("Posted");
    expect(render(null)).not.toContain("move-out-done-balance-to-owner");
    expect(render({ posted: false, reason: "nothing_owed_at_move_out" })).not.toContain(
      "move-out-done-balance-to-owner",
    );
  });

  // PO 2026-10-12 — *"MOVE-OUT DOES NOT WRITE OFF"*. The 2026-10-11 build
  // sent a reason and note on `write_off` and showed *"Write-off $182.90 ·
  // Waiting for approval"*; both are gone with the path.
  it("PO 2026-10-12 — step 3 has no write-off: no row, no ask, and the WRITE sends only the path and terms", async () => {
    expect(Object.keys(PATH_ASKS).sort()).toEqual(["collect", "payment_plan", "transfer"]);
    const choices = shortfallChoices(PATHS);
    expect(choices.map((c) => c.path)).toEqual(["collect", "payment_plan", "transfer"]);
    const html = renderToStaticMarkup(
      <ShortfallPaths
        choices={choices}
        chosen="collect"
        onChoose={() => undefined}
        onConfirm={() => undefined}
        confirming={false}
        t={t}
      />,
    );
    expect(html).not.toContain("write_off");
    expect(html).not.toContain("data-shortfall-write-off");
    expect(html).not.toContain(i18n.t("payments.writeOff.reason.uncollectible_120_days"));
    // A path picked is enough to record — no write-off fields to wait on.
    expect(html.match(/<button[^>]*data-shortfall-confirm[^>]*>/)?.[0] ?? "").not.toContain(
      ' disabled=""',
    );

    const posted: { url: string; body: unknown }[] = [];
    const client = {
      post: async (url: string, body: unknown) => {
        posted.push({ url, body });
        return { data: {}, status: 200, ok: true };
      },
    } as unknown as Parameters<typeof closeImpactPort>[0];
    await settleShortfall("acc-10432", "collect", { finalBill: "336.40", asOf: "2026-01-28" }, client);
    expect(posted[0].body).toEqual({ path: "collect", final_bill: "336.40", as_of: "2026-01-28" });
  });

  it("DEF-CUS-5928 — step 4's heading spells the money the way the cell below it does", () => {
    // The heading interpolated the served 2dp string raw, so it read *What
    // happens to 1591.85* directly above a `Short by` cell reading
    // *$1,591.85*. One screen, one customer's money, two spellings.
    const html = renderWizard(step(4), {
      detail: detail(),
      access: "Full",
      impact: {
        ...IMPACT_BASE,
        landing: "short",
        step_4_live: true,
        shortfall_paths: PATHS,
        money: settlementMoneyOf({
          currency: "USD",
          landing: "short",
          complete: true,
          everything_outstanding: { total: { stored: "1591.8500", display: "1591.85" } },
          what_is_applied: { deposit_held: { stored: "0.0000", display: "0.00" } },
          verdict: { shortfall: { stored: "1591.8500", display: "1591.85" } },
        }),
      },
    });
    const shown = visible(html);
    // ⚠ **THE HEADING THAT CARRIED THE DEFECT IS DELETED, AND THE GUARANTEE
    // IS NOT.** `ShortfallHeadline` read *What happens to 1591.85* — the
    // served 2dp string interpolated raw — directly above a `Short by` cell
    // reading *$1,591.85*: one screen, one customer's money, two spellings. It
    // went with the step it belonged to (PO 2026-09-24), and it was RATIONALE
    // in any case. **What this case has always been protecting is that a money
    // figure reaches a clerk through `MoneyCell` and never as a bare string**,
    // so it now asserts that over the whole of step 3 — a stricter test than
    // the one it replaces, because it covers every figure rather than one.
    expect(shown).toContain("$1,591.85");
    expect(shown).not.toContain("1591.85 ");
    expect(shown).not.toContain(">1591.85");
  });

  it("DEF-CUS-5926 — a verdict the arithmetic never reached is NOT $0.00", () => {
    // ⚠ **FOUND IN A BROWSER AND BY NOTHING ELSE (hard-won law 6).** The
    // settlement fails closed on the landing and the totals, and its four
    // verdict properties are typed `-> Decimal` and return ZERO when `net` is
    // None — so the payload carries `verdict.shortfall = "0.0000"` under a
    // gap, and the screen printed **Short by $0.00** three rows under its own
    // sentence *"The subtraction has not run yet"*. On a final settlement
    // $0.00 is the claim that this customer owes nothing.
    const gapped = settlementMoneyOf({
      currency: "USD",
      landing: null,
      complete: false,
      gaps: ["final_bill_not_stated"],
      everything_outstanding: {
        prior_balance: { stored: "247.3000", display: "247.30" },
        total: { stored: null, display: null },
      },
      what_is_applied: { deposit_held: { stored: "150.0000", display: "150.00" } },
      verdict: {
        shortfall: { stored: "0.0000", display: "0.00" },
        excess: { stored: "0.0000", display: "0.00" },
        refund_amount: { stored: "0.0000", display: "0.00" },
        settled_from_deposit: { stored: "0.0000", display: "0.00" },
      },
    });
    for (const unmeasured of [
      gapped.shortfall,
      gapped.excess,
      gapped.refundAmount,
      gapped.settledFromDeposit,
      gapped.net,
    ]) {
      expect(unmeasured).toEqual({ stored: null, display: null });
    }
    // …and the two terms the ACCOUNT answers for are real reads and survive.
    expect(gapped.priorBalance.display).toBe("247.30");
    expect(gapped.depositHeld.display).toBe("150.00");

    // With a landing, the same verdict IS a measurement and reads through.
    const decided = settlementMoneyOf({
      currency: "USD",
      landing: "short",
      complete: true,
      verdict: { shortfall: { stored: "186.4000", display: "186.40" } },
    });
    expect(decided.shortfall.display).toBe("186.40");
  });

  it("PO 2026-09-24 — the three things the PO deleted are OFF step 3, and stay off", () => {
    // ⚠⚠ **THIS IS THE HEADLINE CHANGE AND IT IS ASSERTED AS A NEGATIVE, ON
    // PURPOSE.** The PO opened the running move-out on 2026-09-24 and could
    // still see all three of these on step 3, having personally asked for them
    // to go. Nothing in this repository reads rendered output (hard-won law
    // 6), so a deletion with no case behind it is a deletion that comes back.
    //
    // * *The five landings, one arithmetic* — a table of OUR derivation
    //   (`Settled · nothing left either way`), which is rationale.
    // * *What the other three would ask for* — the fields of three deposit
    //   options a clerk cannot take, which is rationale about an absence.
    // * *"The subtraction has not run yet."* — why a control is missing.
    //
    // B14 rule 33 puts RATIONALE at ZERO WORDS ON SCREEN and says to REMOVE
    // rather than shorten, which is why all three are gone and none is
    // reworded. Asserted on BOTH landings, because the third string used to
    // render on the undecided one only.
    for (const impact of [
      undefined,
      { ...IMPACT_BASE, landing: null as unknown as CloseImpact["landing"], step_4_live: false },
      { ...IMPACT_BASE, landing: "short" as const, step_4_live: true, shortfall_paths: PATHS },
    ]) {
      const html = renderWizard(step(3), {
        detail: detail(),
        access: "Full",
        ...(impact === undefined ? {} : { impact }),
      });
      const shown = visible(html);
      expect(shown).not.toContain("The five landings");
      expect(shown).not.toContain("one arithmetic");
      expect(shown).not.toContain("What the other three would ask for");
      expect(shown).not.toContain("The subtraction has not run yet");
      expect(html).not.toContain('data-move-matrix="landings"');
      expect(html).not.toContain('data-move-matrix="other-three"');
    }
  });

  it("B14 rule 32 — a refund METHOD reaches the clerk as words, never as its code", () => {
    const html = renderWizard(step(3), {
      detail: detail(),
      access: "Full",
      impact: { ...IMPACT_BASE, refund_methods: ["ach", "mailed_cheque", "carry_to_new_account"] },
    });
    const shown = visible(html);
    // The browser showed *"Method — ach · mailed cheque · carry to new
    // account"*: three server enum codes with their underscores combed.
    expect(shown).not.toContain("mailed_cheque");
    expect(shown).not.toContain("carry to new account");
    expect(shown).not.toMatch(/·\s*ach\b/);
  });

  it("the settlement's money is mapped, and an unread TERM stays null", () => {
    const mapped = settlementMoneyOf({
      currency: "USD",
      // A LANDING, because without one the verdict is dropped on purpose —
      // `DEF-CUS-5926` above. This case is about the MAPPING.
      landing: "short",
      complete: true,
      everything_outstanding: {
        prior_balance: { stored: "247.3000", display: "247.30" },
        final_bill: { stored: null, display: null },
      },
      what_is_applied: { deposit_held: { stored: "150.0000", display: "150.00" } },
      verdict: { shortfall: { stored: "186.4000", display: "186.40" } },
    });
    expect(mapped.priorBalance).toEqual({ stored: "247.3000", display: "247.30" });
    expect(mapped.shortfall.display).toBe("186.40");
    // ⚠ A TERM THE SERVER COULD NOT READ STAYS NULL — never 0, which on a
    // settlement is a claim about somebody's money.
    expect(mapped.finalBill).toEqual({ stored: null, display: null });
    expect(mapped.depositInterest).toEqual({ stored: null, display: null });
    // …and a payload with none of the blocks at all yields fourteen nulls
    // rather than throwing on a screen a clerk is standing in.
    expect(settlementMoneyOf({}).outstanding).toEqual({ stored: null, display: null });
  });

  // ── STEP 6 · the recap carries what landed on 3 and 5 ───────────────────
  it("PO 2026-09-24 — `The money` is ONE component and step 4 mounts the SAME one as step 3", () => {
    // ⚠ **THE SPECIFICATION SAYS SO IN AS MANY WORDS** (sheet 1: *"ONE
    // component, mounted twice"*), and B14 rule 43 is why: a piece of UI is a
    // COMPONENT, never standalone code inside a page. **Two renderings of one
    // customer's closing position is how a recap comes to disagree with the
    // step it recaps**, and the merge raised the stakes — step 4 is now the
    // only screen between the clerk and an irreversible close.
    //
    // **What would make this pass wrongly?** Asserting the table exists on
    // both steps: a copy-paste would satisfy that. So it compares the rendered
    // TABLE, markup for markup, across the two steps.
    const impact = { ...IMPACT_BASE, landing: "settled" as const };
    const table = (html: string): string => {
      const at = html.indexOf('<table class="mt-2 w-full text-sm" data-move-matrix="money">');
      expect(at).toBeGreaterThanOrEqual(0);
      return html.slice(at, html.indexOf("</table>", at));
    };
    const onThree = renderWizard(step(3), { detail: detail(), access: "Full", impact });
    const onFour = renderWizard(step(4), { detail: detail(), access: "Full", impact });
    expect(table(onFour)).toEqual(table(onThree));
    // And the review still carries what the drawing puts beside it.
    expect(onFour).toContain('data-move-matrix="messages"');
    expect(visible(onFour)).toContain("What we will send");
  });

  // ══════════════════════════════════════════════════════════════════════
  // DEF-CUS-5931 — STEP 3 PRICES WHAT STEP 2 KEYED, AND THE READS STILL
  // COMMIT WITH THE CLOSE (PO 2026-09-20, verbatim *"option b is correct"*)
  // ══════════════════════════════════════════════════════════════════════
  it("the preview port GETs when nothing is keyed and POSTs the capture when it is", async () => {
    const seen: { method: string; path: string; body: unknown }[] = [];
    const client = {
      get: async (path: string) => {
        seen.push({ method: "GET", path, body: undefined });
        return { data: { priced: false, lines: [] }, status: 200 };
      },
      post: async (path: string, body: unknown) => {
        seen.push({ method: "POST", path, body });
        return {
          data: { priced: true, lines: [], priced_from_uncommitted_reads: true },
          status: 200,
        };
      },
    } as never;

    // ⚠ **NOTHING KEYED IS STILL THE GET IT HAS ALWAYS BEEN.** An account whose
    // closing read was taken in the field must make the identical request it
    // made before this ruling — the change may not move a call it does not own.
    const plain = await finalBillPreviewPort(client).read("acc-1", "2026-01-28");
    expect(plain.fromUncommittedReads).toBe(false);

    const keyed = await finalBillPreviewPort(client).read("acc-1", "2026-01-28", [
      { meter_no: "M-4021", value: "52410" },
    ]);
    expect(keyed.fromUncommittedReads).toBe(true);

    expect(seen.map((call) => call.method)).toEqual(["GET", "POST"]);
    // The leading slash is load-bearing on BOTH — `DEF-CUS-4010` and
    // `DEF-CUS-5072`, twice on this very screen.
    expect(seen[0].path.startsWith("/accounts/acc-1/final-bill-preview")).toBe(true);
    expect(seen[1].path.startsWith("/accounts/acc-1/final-bill-preview")).toBe(true);
    // The move-out date is a QUERY term on both, because it is the window's
    // end (BR-CUS-056) and the day the deposit interest accrues to.
    expect(seen[1].path).toContain("moved_out_on=2026-01-28");
    // …and the capture travels in the BODY, in the shape step 6 already posts.
    expect(seen[1].body).toEqual({ final_reads: [{ meter_no: "M-4021", value: "52410" }] });
  });

  it("the preview key carries the reads, so a corrected register re-prices and nothing else does", () => {
    // ⚠ **PO ruling 2026-09-20, option C: re-price when, and ONLY when, a read
    // moved.** The key IS that rule — React Query refetches on a changed key
    // and serves the cache otherwise — so this case is what proves the rule
    // rather than a comment claiming it (hard-won law 1).
    const first = finalBillPreviewQueryKey("acc-1", "2026-01-28", [
      { meter_no: "M-4021", value: "52410" },
    ]);
    const same = finalBillPreviewQueryKey("acc-1", "2026-01-28", [
      { meter_no: "M-4021", value: "52410" },
    ]);
    const corrected = finalBillPreviewQueryKey("acc-1", "2026-01-28", [
      { meter_no: "M-4021", value: "52401" },
    ]);
    expect(same).toEqual(first);
    expect(corrected).not.toEqual(first);
    // And an account with nothing keyed keys on the account and the date
    // alone, exactly as it did before the ruling.
    expect(finalBillPreviewQueryKey("acc-1", "2026-01-28")).toEqual(
      finalBillPreviewQueryKey("acc-1", "2026-01-28", []),
    );
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-005@bbed56d (story+rules snapshot — EP-CUS-02 move-out lead story)
// generated: 2026-08-11 by story-coder (W2 customers FRONTEND lane 3 — S20)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 702 passed / 168 todo across 51 files✔ (670 passed / 160 todo across 49 files was the pre-lane baseline — this lane adds 32 passing + 8 todo and dropped nothing) · vite build✔ · run_gates 12 PASS · 2 FAIL · 1 SKIP — and the two FAILs ARE NOT THIS LANE'S, stated rather than rounded up (hard-won law 1): G7 names six 06-backend files (db/rls_ledger_w5.sql, db/rls_notifications_w3.sql, ledger 0002_rls_w5_and_immutability.py, notifications 0002_rls_w3_outbound_queue.py …) with no human-review-ledger row, and G10 names US-BIL-023/024 · US-NOT-002/015 · US-PAY-014 with no backend TC test. All eleven belong to the W3/W5 billing·notifications·ledger lanes landing in 06-backend during this session; this lane touched no backend file. The FRONTEND half of G10 is clean (0 of the frontend-cited stories miss a test, US-CUS-004/005 included), and G13 unwired-props, G14 prototype-conformance and G15 i18n-parity (5 locales × 2466 keys, identical sets) all PASS. The pre-lane baseline for this session was 14 PASS · 0 FAIL · 1 SKIP
// exceptions: E4 TC-1's four-step walk and the commit itself need a browser (the frame's Continue is a click): every step's fields, every refusal, the exact payload and the rendered answer are asserted statically instead, which is where the defects would be · E4 TC-5's negative-read refusal has no control to refuse — final reads are metering's (BR-CUS-021) · E4 TC-6's issued-bill refusal cannot be reached: billing has no `invoices` table, so the server always answers `move_out_date_not_checked_against_issued_bills` instead, and THAT warning is asserted here · E4 TC-7 is server/RLS scope (G5)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
