// ── Trace ──────────────────────────────────────────────
// Change:   DEF-400 — the three lifecycle acts reach the shared definition
//           detail, so a drafted discount can be taken live from a screen.
//           Screens: CHG-01.discount
// Rules:    BR-RAT-072 (four statuses, five version states) · BR-RAT-077 (the
//           second approval — computed at SUBMIT and STORED with the threshold
//           that decided it; ALWAYS required where there is no budget cap) ·
//           BR-RAT-083 (anyone may DRAFT, Owner/Admin ACTIVATE) · BR-SHL-025
//           (a forbidden control is present and disabled WITH its reason) ·
//           B14 rule 21 (new UI is Tailwind)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WAS RED HERE BEFORE THE CHANGE, AND IT IS ONE LINE.** With
// `discountLifecycleAct` returning `null` for every status — which is what the
// screen effectively did while no route existed — the first case fails with
// `expected null to be "submit"`, and the render case fails on the missing
// button label. That is DEF-400 exactly: the status pill said `Draft` and no
// control on the page could change it.
//
// ⚠ **AND THE LAST CASE IS THE ONE THAT MATTERS MOST.** `activate` is offered
// from `scheduled` and NEVER from `draft`, because the second-approval
// requirement is written at SUBMIT: a version that skipped submit carries no
// requirement to read, so an Activate button on a draft would be a path around
// BR-RAT-077. The service still accepts a draft — DEF-479 — and this test is
// what keeps the SCREEN from opening that path while the rule question is
// settled.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { DiscountDetail, MyPermissions } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import {
  DISCOUNT_LIFECYCLE,
  DefinitionDetailPage,
  activationSkipsApprovalCheck,
  discountLifecycleAct,
  discountLifecycleActs,
} from "./DefinitionDetailPage";
import { DEFINITION_ROUTES, definitionPath } from "./definitionDetail";

import pageSource from "./DefinitionDetailPage.tsx?raw";

const TEST_TENANT = "brazosbend";

/** r10's SENIOR, as `GET /discounts/{id}` serves it — trimmed to the fields
 *  this suite reads, with the rest carried so the type is the real one. */
const SENIOR: DiscountDetail = {
  id: "d-senior",
  code: "SENIOR",
  name: "Senior discount",
  type: "percentage",
  value: "15.000000",
  value_display: "15.00%",
  currency: "USD",
  eligibility: "Age 65+",
  verification: "annual_recertification",
  plans: 3,
  enrolled: 72,
  status: "draft",
  programme_owner: "Customer service",
  funding_source: "Rate-payer funded",
  gl_account_id: null, // CR-066 table 3 — no override; the designation answers
  applies_to: "whole_bill",
  effective_from: "2026-01-01",
  version_no: 1,
  version_status: "draft",
  version_id: "0198c1aa-0000-7000-8000-00000000d411",
  report_in_assistance_filing: true,
  funding_exhausted_at: null,
  granted_to_date: "0.000000",
  granted_to_date_display: "0.00",
  budget_cap: "12312.000000",
  budget_cap_display: "12312.00",
  budget_remaining: "12312.000000",
  budget_remaining_display: "12312.00",
  second_approval_required: false,
  second_approval_threshold: null,
  second_approval_threshold_display: null,
  self_approved: false,
  change_reason: null,
};

function permissions(access: string): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: "plans_rates", label: "Plans & Rates", access }],
  };
}

function renderDiscount(discount: DiscountDetail, access = "Full"): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions(access));
  queryClient.setQueryData(queryKeys.ledgerAccounts, []);
  queryClient.setQueryData(queryKeys.discount(discount.id), discount);
  const pattern = `/${TEST_TENANT}/plans-rates/${DEFINITION_ROUTES.discount.segment}/:definitionId`;
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${definitionPath("discount", discount.id)}`]}>
          <Routes>
            <Route path={pattern} element={<DefinitionDetailPage kind="discount" />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ── The act each state is due ──────────────────────────────────────────────

describe("DEF-400 — one act at a time, and only the legal one", () => {
  it("maps each version state to the single act CR-013 part 3 allows from it", () => {
    expect(discountLifecycleAct("draft")).toBe("submit");
    expect(discountLifecycleAct("pending_approval")).toBe("approve");
    expect(discountLifecycleAct("scheduled")).toBe("activate");
  });

  it("offers NOTHING on a version that has arrived or been superseded", () => {
    // An active version is in force and a superseded one is history. Neither
    // has a next step, and drawing a disabled control for a state with no act
    // would be inventing one.
    expect(discountLifecycleAct("active")).toBeNull();
    expect(discountLifecycleAct("superseded")).toBeNull();
  });

  it("offers nothing where there is no version at all", () => {
    // `create_discount` always writes v1, so this is a shape a future caller
    // could produce. Null in, null out — never a submit against no version.
    expect(discountLifecycleAct(null)).toBeNull();
    expect(discountLifecycleAct(undefined)).toBeNull();
  });

  it("BR-RAT-109: a DRAFT offers Activate too, WARNED rather than withheld", () => {
    // ⚠ AMENDED 2026-08-21 — THE PO OVERRULED THE ASSERTION THIS USED TO MAKE,
    // and the reasoning behind it was sound, so it is worth keeping visible.
    // It read "NEVER offers Activate on a DRAFT", because BR-RAT-077's
    // second-approval requirement is computed and STORED at submit — so a draft
    // carries none, and a discount with NO budget cap, the case the PO ruled
    // always needs two people, is the one that slips through most cleanly.
    //
    // The PO ruled warn-and-allow anyway: *"We will show message and not refuse
    // it."* Silver Creek has 1–2 staff, and a control needing a second person
    // is a control that stops the business — the same trade they made for
    // backdating (2026-08-11) and self-approval (2026-08-19).
    //
    // What replaces the gate is the WARNING and the AUDIT MARKER, and both are
    // asserted below. A withheld control and an unwarned one are equally
    // wrong, in opposite directions.
    expect(discountLifecycleActs("draft")).toEqual(["submit", "activate"]);
    // SUBMIT IS FIRST, and that ordering is load-bearing: it is the normal path
    // and the first act takes the primary button tier.
    expect(discountLifecycleActs("draft")[0]).toBe("submit");
    expect(DISCOUNT_LIFECYCLE.filter((row) => row.act === "activate")).toEqual([
      { from: "draft", act: "activate" },
      { from: "scheduled", act: "activate" },
    ]);
  });

  it("BR-RAT-109: only activate-from-draft is flagged as skipping the check", () => {
    // The flag must MEAN something. If it were true of every activation it
    // would be noise, and an operator scanning for it would learn nothing.
    expect(activationSkipsApprovalCheck("activate", "draft")).toBe(true);
    expect(activationSkipsApprovalCheck("activate", "scheduled")).toBe(false);
    expect(activationSkipsApprovalCheck("submit", "draft")).toBe(false);
  });
});

// ── What the screen draws ──────────────────────────────────────────────────

describe("DEF-400 — the control reaches the screen", () => {
  it("an ACTIVE discount gets no lifecycle control at all", () => {
    const html = renderDiscount({ ...SENIOR, status: "active", version_status: "active" });
    for (const act of ["submit", "approve", "activate"]) {
      expect(html).not.toContain(i18n.t(`rating.definition.lifecycle.${act}`));
    }
  });

  it("BR-SHL-025: a read-only role sees the control and its reason, not a blank space", () => {
    const html = renderDiscount(SENIOR, "View");
    expect(html).toContain(i18n.t("rating.definition.lifecycle.submit"));
    expect(html).toContain("disabled");
  });
});

// ── The two facts an approver must be able to READ ─────────────────────────

// ⚠ CR-166-BRC10 round 3 task 6 (2026-10-03): the discount route mounts its own
// details page (images 19–26), so the cases here that RENDERED the shell's
// lifecycle panel (Submit/Approve/Activate buttons, the BR-RAT-077 second-
// approval sentences, the BR-RAT-109 activate-without-submission warning) were
// RETIRED. Activate is gone by PO ruling (1) and BR-RAT-109 is superseded
// (CR-166 §2); the header's acts by status are asserted in
// `discountDetail/discountDetail.dom.test.tsx`. A negative assertion over a page
// that no longer draws the panel cannot fail, so it was removed rather than kept.

// ── The screen decides nothing ─────────────────────────────────────────────

describe("DEF-400 — no rule and no arithmetic on the client", () => {
  it("the page never computes a second-approval requirement of its own", () => {
    // §A7.6 as a build instruction, checked the way this suite already checks
    // the Versions tab is not `audit_log`: a rendering assertion cannot tell a
    // read-back figure from a recomputed one, so the source is the evidence.
    // It READS the served flag…
    expect(pageSource).toContain("row.second_approval_required === true");
    // …and never assigns one (an assignment here is a client-side decision)…
    expect(pageSource).not.toMatch(/second_approval_required\s*=\s*[^=]/);
    // …and never compares the budget cap to anything, which is the only way it
    // could re-derive the requirement the server already stored.
    expect(pageSource).not.toMatch(/budget_cap[^\n]*[<>]/);
  });

  it("carries DEF-400 and BR-RAT-109 in the source, so the next reader finds the record", () => {
    expect(pageSource).toContain("DEF-400");
    // Was DEF-479 — the defect that asked whether activate should refuse a
    // never-submitted version. The PO ruled it (warn, do not refuse), so the
    // source now cites the RULE rather than the open question it closed.
    expect(pageSource).toContain("BR-RAT-109");
  });
});


