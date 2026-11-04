// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-016 · US-CUS-017 (S23 — pick a plan, set the date, confirm)
// Change:   CR-094-BRC01 step 2 lane B — the screen is built to
//           `04-docs/05-modules/03-customers/blueprint/13-change-plan-wizard.md`
// Defects:  **DEF-CUS-5170** (rule ids, an open-question id and a Python module
//           path were on a clerk's screen) · **DEF-CUS-5171** (one fixed title
//           on all three steps, the kicker and the title swapped, no step name)
// Rules:    **B14 rule 41** (the product UI matches the blueprint exactly) ·
//           **B14 rule 31** (nothing internal is ever visible — not a rule
//           number, not a path, not a function name) · **B14 rule 33**
//           (RATIONALE is ZERO words on screen) · B14 rule 37 (a drawn figure
//           is an illustration) · BR-SHL-023 (one formatting path)
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS SCREEN HAD NO SUITE OF ITS OWN.** `S23` was covered only by
// `AccountActions.test.tsx`, which asserted that `CHANGE_PLAN_STEPS` equals
// `["plan","effective","confirm"]` — the array equalling itself. Nothing here
// had ever read the rendered screen, which is exactly how a page came to print
// `BR-CUS-042 · BR-CUS-062 · OQ-179` and
// `apps.rating.engine.prorate_base_charge` to a billing clerk for weeks with
// every gate green.
//
// ⚠ **NOT ONE DRAWN FIGURE IS ASSERTED (B14 rule 37).** The blueprint's
// `$30.50 · $42.00 · +$11.50 · 01/10/2026` are illustrations. The fixture
// carries its own numbers and only the SHAPE and the WORDS are checked.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  AccountDetail,
  MyPermissions,
  PlanChangeOptions,
  PlanChangePreview,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { accountDetailQueryKey } from "./AccountDetailPage";
import {
  CHANGE_PLAN_STEPS,
  CHANGE_PLAN_STEP_LABEL_KEYS,
  CHANGE_PLAN_TITLE_KEYS,
  ChangePlanWizard,
  PreviewPanel,
  UNAVAILABLE_LABEL_KEYS,
  UNAVAILABLE_REASON_KEYS,
  planChangeOptionsKey,
} from "./ChangePlanWizard";
import { ACCOUNTS_PERMISSION, accountChangePlanPath } from "./customersShared";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** What a person actually reads — `title=` holds evidence by design (B14 rule
 *  31 permits it in terms), so a whole-document `not.toContain` would read the
 *  evidence as the defect it exists to prevent. */
function visible(html: string): string {
  return html.replace(/<[^>]*>/g, " ");
}

function detail(over: Partial<AccountDetail> = {}): AccountDetail {
  return {
    id: "acc-11812",
    account_no: "A-11812",
    name: "Bramble Bakery",
    unit_id: "u-744",
    unit_label: "Suite 1",
    premise: "142 Bakers Row",
    services: ["electric", "water"],
    balance: "2410.0000",
    balance_currency: "USD",
    currency: "USD",
    // `accountHeadline` walks the contacts, so an account fixture without them
    // crashes the render — an empty list is the real shape of an account with
    // no contact on file, not a convenience.
    contacts: [],
    ...over,
  } as AccountDetail;
}

function options(over: Partial<PlanChangeOptions> = {}): PlanChangeOptions {
  return {
    account_id: "acc-11812",
    unit_id: "u-744",
    unit_services: ["electric", "water"],
    current_plan: {
      id: "plan-cur",
      code: "SCW-RES",
      name: "Sample — Residential",
      version: 3,
      base_charges: "20.0000",
    },
    plans: [
      {
        id: "plan-std",
        code: "RES-STD",
        name: "Residential Standard",
        version: 2,
        services: ["electric", "water"],
        base_charges: "42.0000",
        is_current: false,
        drops_services: [],
        requires_eligibility: [],
        ineligible_reason: null,
        missing_services: [],
      },
    ],
    ...over,
  };
}

function permissions(): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access: "Full" }],
  };
}

function renderWizard(seed: { options?: PlanChangeOptions } = {}): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const account = detail();
  queryClient.setQueryData(accountDetailQueryKey(account.id), account);
  queryClient.setQueryData(planChangeOptionsKey(account.id), seed.options ?? options());
  queryClient.setQueryData(queryKeys.myPermissions, permissions());
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${accountChangePlanPath(account.id)}`]}>
          <Routes>
            <Route path="/:tenant/accounts/:accountId/change-plan" element={<ChangePlanWizard />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** A preview as the server really answers it on a tenant where neither the
 *  deposit differential nor the usage half can be stated — which is every
 *  tenant in this tree (`OQ-179`, `OQ-180`, both OPEN). */
function preview(): PlanChangePreview {
  return {
    account_id: "acc-11812",
    currency: "USD",
    current_plan: { id: "plan-cur", code: "SCW-RES", name: "Sample — Residential" },
    new_plan: { id: "plan-std", code: "RES-STD", name: "Residential Standard" },
    effective_on: "2026-10-01",
    base: { current_total: "20.0000", new_total: "42.0000", delta: "22.0000" },
    proration: {
      // ⚠ Deliberately NOT zero. A zero here is a legitimate `$0.00` on the
      // part-period line and would make the absence assertion below pass for
      // the wrong reason — a check looking at the wrong thing (law 7).
      current_plan_line: { plan: "SCW-RES", service_days: 9, amount: "6.0000" },
      new_plan_line: { plan: "RES-STD", service_days: 31, amount: "42.0000" },
      computed_by: "apps.rating.engine.prorate_base_charge",
    },
    proration_unavailable: null,
    deposit_differential: null,
    deposit_differential_unavailable: {
      code: "deposit_differential_unavailable",
      br_refs: ["BR-CUS-042", "BR-CUS-062"],
      oq_ref: "OQ-179",
      detail:
        "BR-CUS-042 says compute the category differential on a plan change; BR-CUS-062 says there is no deposit recompute in v1.",
    },
    usage_unavailable: {
      code: "usage_unavailable",
      br_ref: "BR-RAT-004",
      oq_ref: "OQ-180",
      detail: "B4.3 prorates usage as well as base.",
    },
    net_impact: { amount: "22.0000", excludes: ["deposit_differential", "usage"] },
  } as unknown as PlanChangePreview;
}

function previewHtml(): string {
  return renderToStaticMarkup(<PreviewPanel preview={preview()} t={t} />);
}

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CUS-5170` — NOTHING INTERNAL REACHES A CLERK
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CUS-5170 — the preview says nothing internal", () => {
  it("prints no rule id and no open-question id, anywhere a person reads", () => {
    const seen = visible(previewHtml());
    // Every one of these was ON the rendered page, measured in Chromium on
    // `brazosbend` 2026-09-13. B14 rule 31 names all three families.
    for (const internal of ["BR-CUS-042", "BR-CUS-062", "OQ-179", "BR-RAT-004", "OQ-180"]) {
      expect(seen).not.toContain(internal);
    }
  });

  it("prints no Python module path and no function name", () => {
    // `computed_by` is `apps.rating.engine.prorate_base_charge`. The claim it
    // supports — *"Computed by the server."* — is what a clerk can act on.
    expect(visible(previewHtml())).not.toContain("apps.rating.engine");
    expect(previewHtml()).toContain(t("customers.planChange.computedBy"));
  });

  it("keeps the evidence on `title`, which rule 31 allows, rather than deleting it", () => {
    // *"The provenance is not deleted, it MOVES"* — B14 rule 31, verbatim. A
    // reader who needs to know WHICH function priced this can still find out.
    expect(previewHtml()).toContain('title="apps.rating.engine.prorate_base_charge"');
  });

  it("names the excluded lines in words, never by their server codes", () => {
    const html = previewHtml();
    expect(visible(html)).not.toContain("deposit_differential");
    expect(html).toContain(t("customers.planChange.excluded.deposit_differential"));
  });

  it("heads each absent line with the LINE, and says the blueprint's sentence", () => {
    const html = previewHtml();
    // The drawing heads the deposit absence `DEPOSIT DIFFERENTIAL` and gives it
    // one sentence. Two blocks both headed `Not calculated` say neither.
    expect(html).toContain(t(UNAVAILABLE_LABEL_KEYS.deposit_differential_unavailable));
    expect(html).toContain(t(UNAVAILABLE_REASON_KEYS.deposit_differential_unavailable));
    // And the server's engineering paragraph does not travel.
    expect(visible(html)).not.toContain("says compute the category differential");
  });

  it("still refuses to invent a figure the server would not state (OQ-179 is OPEN)", () => {
    // The whole point of the absence. A `$0.00` would read as *no deposit is
    // owed* rather than *nobody has ruled what is owed*.
    expect(visible(previewHtml())).not.toContain("$0.00");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CUS-5171` — THE HEAD IS THE ONE THE BLUEPRINT DRAWS (B14 rule 41)
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CUS-5171 — the change plan matches its blueprint", () => {
  it("kickers `CHANGE PLAN` and titles the step's own question", () => {
    const html = renderWizard();
    expect(html).toContain(t("customers.planChange.kicker"));
    expect(html).toContain(t(CHANGE_PLAN_TITLE_KEYS.plan));
    // The two were the other way round: the account number kickered the page
    // and `Change plan` titled all three steps.
    expect(visible(html)).not.toContain("Account A-11812");
  });

  it("has a title for every declared step, so a fourth step cannot lose one", () => {
    for (const step of CHANGE_PLAN_STEPS) {
      expect(CHANGE_PLAN_TITLE_KEYS[step]).toBeDefined();
      expect(t(CHANGE_PLAN_TITLE_KEYS[step])).not.toBe(CHANGE_PLAN_TITLE_KEYS[step]);
    }
  });

  /**
   * ⚠ **ASSERTED AS A LITERAL, AND THE FIRST DRAFT WAS NOT.** It built the
   * expected string from the same catalogue the screen renders from — so at
   * `ffe3a8152`, where `stepOf` held no `{{name}}`, both sides read
   * `Step 1 of 3` and the case PASSED over the defect it was written for. That
   * is law 7's second habit (*ask what would make this check pass wrongly*)
   * catching a check I had just written. The literal is the drawn sub-line.
   */
  it("prints the drawn sub-line `Step 1 of 3 · Plan`, naming the step", () => {
    const html = visible(renderWizard());
    expect(html).toContain("Step 1 of 3 · Plan");
    expect(t(CHANGE_PLAN_STEP_LABEL_KEYS.plan)).toBe("Plan");
    expect(t("customers.planChange.stepOf", { step: 1, of: 3, name: "X" })).toContain("X");
  });

  it("draws the drawing's two roll-up rows — `Current plan` and `Current base`", () => {
    const html = renderWizard();
    expect(html).toContain(t("customers.planChange.currentPlan"));
    expect(html).toContain(t("customers.planChange.currentBaseShort"));
    // ⚠ The base is the SERVER's string through `MoneyCell` — two decimals on
    // a four-decimal value, and nothing in this screen divides or rounds.
    expect(html).toContain("$20.00");
    expect(html).not.toContain("20.0000");
  });

  it("labels the picker `New plan` and carries the drawn sentence under it", () => {
    const html = renderWizard();
    expect(html).toContain(t("customers.planChange.newPlan"));
    expect(html).toContain(t("customers.planChange.onlyCovering"));
    // The heading that repeated the step number the rail already carries.
    expect(visible(html)).not.toContain("1 · Pick the new plan");
  });

  it("uses the drawing's preview labels, not the product's older sentences", () => {
    const html = previewHtml();
    for (const key of [
      "customers.planChange.currentBase",
      "customers.planChange.newBase",
      "customers.planChange.baseDelta",
      "customers.planChange.netImpact",
    ]) {
      expect(html).toContain(t(key));
    }
    for (const gone of [
      "Current plan, base charges",
      "New plan, base charges",
      "Difference on the next bill",
      "Net effect on the next bill",
    ]) {
      expect(visible(html)).not.toContain(gone);
    }
  });

  it("commits with `Confirm ✓` — B14 rule 4's `Verb ✓`", () => {
    // Tier 2, and labelled as such: the commit button lives on step 3 and this
    // file renders step 1. The button itself was read off the running product
    // (Chromium at 1280 on `brazosbend`, 2026-09-13).
    expect(t("customers.planChange.confirm")).toBe("Confirm ✓");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CUS-5178` — AN ACCOUNT WITH NO UNIT HAS NO PLAN, AND SAYS SO
// ══════════════════════════════════════════════════════════════════════════
//
// A master account carries sub-accounts and no unit of its own, and the account
// DERIVES its plan from the unit — so there is nothing to change and the
// options read answers 404, correctly. The screen used to read that as a
// FAILURE and tell a clerk *"It may have been removed, or the address may be
// wrong"* over a correct address, with a `Retry` that could only fail again.
// Measured at 1280 and 1440 on `AC-2026-00052`: a 253px card where every
// sibling dialog is 648–836.
describe("DEF-CUS-5178 — no unit, no plan, and the screen states it", () => {
  function noUnit(): string {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const account = detail({ unit_id: null, unit_label: null } as Partial<AccountDetail>);
    queryClient.setQueryData(accountDetailQueryKey(account.id), account);
    // ⚠ The options read is left UNSEEDED on purpose: the point of the fix is
    // that the screen decides on a fact it already holds and never waits for a
    // read that will 404. Seeding it would test the opposite thing.
    queryClient.setQueryData(planChangeOptionsKey(account.id), undefined);
    queryClient.setQueryData(queryKeys.myPermissions, permissions());
    return renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TEST_TENANT}${accountChangePlanPath(account.id)}`]}>
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

  it("refuses with the reason instead of reporting a failure", () => {
    const html = noUnit();
    expect(html).toContain('data-refusal="no-unit"');
    expect(html).toContain(t("customers.planChange.noUnit"));
  });

  it("never says the address may be wrong about a correct address", () => {
    const html = visible(noUnit());
    // ⚠ **THE POSITIVE HALF IS WHAT MAKES THE NEGATIVE ONE MEAN ANYTHING.**
    // Without it this case passed at `ffe3a8152` — over a LOADING SKELETON,
    // which contains the failure copy no more than the refusal does. A pure
    // `not.toContain` cannot tell "the words are gone" from "nothing rendered".
    expect(html).toContain(t("customers.planChange.noUnit"));
    expect(html).not.toContain("the address may be wrong");
    expect(html).not.toContain("Download error report");
  });

  it("offers no Retry, because retrying cannot change the answer", () => {
    // A `Retry` over a business refusal is a control that can only fail again,
    // which is worse than no control: it says the product thinks it might work.
    expect(visible(noUnit())).not.toContain("Retry");
    expect(noUnit()).toContain(t("customers.planChange.backToAccount"));
  });

  it("still keeps its head, so the dialog is not a bare sentence", () => {
    const html = noUnit();
    expect(html).toContain(t("customers.planChange.kicker"));
    expect(html).toContain(t(CHANGE_PLAN_TITLE_KEYS.plan));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: 04-docs/05-modules/03-customers/blueprint/13-change-plan-wizard.md ·
//         04-docs/02-decisions/14-ui-conventions.md rules 31, 33, 37, 41 ·
//         DEF-CUS-5170 · DEF-CUS-5171 · CLAUDE.md hard rule 2
// generated: 2026-09-13 by CR-094-BRC01 step 2 lane B
// checklist: A=n/a B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST at `ffe3a8152`, in a `git worktree`, through
//         `npx vitest run` — the harness that runs them, never `__main__`
//         (DEF-GOV-3733). Transcript in the lane report.
// exceptions: (1) two cases are TIER 2 and say so — the commit label and the
//         `Send agreement ✓` sibling live on step 3, which a static render at
//         step 1 cannot reach; both buttons were read off the running product
//         instead. A case that mounted step 1 and claimed to prove the footer
//         would be hard-won law 7's *looking at the wrong thing*.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
