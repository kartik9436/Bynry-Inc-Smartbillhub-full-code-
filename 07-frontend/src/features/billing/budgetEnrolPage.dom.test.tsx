// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-018 — §05 entry 25.1 `Enrol` (Billing blueprint p122–p124)
// Rules:    B14 rule 31 (no database id is ever a field's visible value) ·
//           rule 33 (the five caps) · rule 41 (the product matches the
//           drawing) · hard-won law 2 and its fixture clause (mount under the
//           REAL path pattern) · CLAUDE.md rule 2 (never a fabricated zero)
// Tests:    this file
// ───────────────────────────────────────────────────────
//
// ⚠ **THE FIXTURE MOUNTS THE REAL PATH PATTERN, AND THAT IS THE POINT.** A bare
// `MemoryRouter` with no `/:tenant/…` route leaves `useParams().tenant`
// undefined, so every address the page builds comes out `//billing/…` — a
// protocol-relative URL to another host, which reads as a perfectly good string
// to `toContain`. That fixture is how `DEF-CWP-3925` hid eight dead doors over
// live screens, and it is why the door case below asserts the WHOLE address
// including the tenant segment.
//
// ⚠ **AND THE ABSENCE CASES ARE THE ONES THAT EARN THEIR KEEP.** Three figures
// the drawing shows are published by no endpoint, and the failure mode is not a
// crash — it is a plausible `$0.00` or a bare dash that a clerk reads as an
// answer. Each case below asserts the SENTENCE, and asserts that `0.00` is not
// what stands in its place.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";
import type { BudgetEligibility, BudgetListResponse } from "@/api/billingOpsEndpoints";
import type { AccountDetail } from "@/api/endpoints";

import { BudgetEnrolPage, eligibilityState, enrolAccountLabel, openSinceMonths } from "./BudgetEnrolPage";
import { BudgetBillsTab, budgetEligibilityKey, budgetListKey } from "./BudgetBillsTab";
import { BUDGET_ENROL_ROUTE, BUDGET_TAB_ROUTE } from "./billingShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** B14 rule 37 — every figure here is an ILLUSTRATION of a SHAPE. Nothing
 *  asserts the drawing's own `$78.00` or `100612`; the cases assert that a
 *  served figure reaches the screen and that an unserved one says so. */
const ACCOUNT_ID = "11111111-2222-3333-4444-555555555555";

const DETAIL = {
  id: ACCOUNT_ID,
  account_no: "100612",
  customer_no: "C-2871",
  name: "Whitlock, R.",
  unit_id: null,
  unit_label: "A",
  premises_id: "p-1",
  premise: "44 Pecan Row · A",
  premise_address: "44 Pecan Row, Austin TX 78704",
  services: ["water", "sewer", "trash"],
  balance: "312.400000",
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
  autopay: true,
  opened_at: "2025-10-01",
  closed_at: null,
  last_bill_at: "2026-10-31",
  aging: null,
  deposit_on_file: null,
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
  plan_snapshot_unavailable: "BR-CUS-029's snapshot does not exist",
  unit_plan: { name: "Residential water & sewer", code: "RWS", version: 3, since: "2025-10-01" },
  customer: null,
} as unknown as AccountDetail;

const ELIGIBILITY: BudgetEligibility = {
  account_id: ACCOUNT_ID,
  months_of_history: 13,
  bills_read: 12,
  trailing_actuals: ["78.000000"],
  currency: "USD",
  required_months: 12,
  required_months_unavailable: null,
  computed_level: "78.000000",
  computed_level_unavailable: null,
  eligible: null,
  eligible_unavailable:
    "BR-RAT-043 puts budget-billing eligibility on the rate PLAN and no endpoint publishes that flag (OQ-237).",
  already_enrolled: false,
  open_balance: "312.400000",
  open_balance_currency: "USD",
  open_balance_bills: 2,
  open_balance_basis: "open invoices",
  open_balance_basis_oq: "OQ-217",
  open_balance_problems: [],
  unavailable: [],
};

const PARAMETERS: BudgetListResponse = {
  results: [],
  count: 0,
  parameters: { override_bound_pct: "30", eligibility_months: 12 },
  parameters_unavailable: null,
  statuses: ["enrolled", "off_budget"],
  unavailable: [],
};

function render(overrides?: {
  eligibility?: BudgetEligibility | null;
  detail?: AccountDetail | null;
  accountId?: string;
}): string {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: Infinity } },
  });
  const accountId = overrides?.accountId ?? ACCOUNT_ID;
  client.setQueryData(["budget-billing", "parameters"], PARAMETERS);
  if (overrides?.detail !== null) {
    client.setQueryData(
      ["budget-billing", "enrol", "account", accountId],
      overrides?.detail ?? DETAIL,
    );
  }
  if (overrides?.eligibility !== null) {
    client.setQueryData(budgetEligibilityKey(accountId), overrides?.eligibility ?? ELIGIBILITY);
  }
  // The picker's own list, so an account is selectable without a network call.
  client.setQueryData(["budget-billing", "enrol", "account-picker", ""], { results: [] });
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <ToastProvider>
          {/* THE REAL PATH PATTERN — see this file's header. */}
          <MemoryRouter
            initialEntries={[`/brazosbend${BUDGET_ENROL_ROUTE}?account=${accountId}`]}
          >
            <Routes>
              <Route path="/:tenant/billing/budget/enrol" element={<BudgetEnrolPage />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
}

describe("§05 entry 25.1 — the enrol form is the form the drawing needs", () => {
  it("TC-E1 · draws the page head the drawing gives it", () => {
    const html = render();
    expect(html).toContain(t("billing.budgetEnrol.title"));
    expect(html).toContain(t("billing.budgetEnrol.caption"));
    expect(html).toContain(t("billing.budgetEnrol.cancel"));
  });

  it("TC-E2 · draws the four numbered groups, in the drawn order", () => {
    const html = render();
    const groups = [
      t("billing.budgetEnrol.group.who"),
      t("billing.budgetEnrol.group.eligible"),
      t("billing.budgetEnrol.group.level"),
      t("billing.budgetEnrol.group.next"),
    ];
    let cursor = -1;
    for (const group of groups) {
      const at = html.indexOf(group, cursor + 1);
      expect(at, `${group} is drawn, after the group before it`).toBeGreaterThan(cursor);
      cursor = at;
    }
  });

  it("TC-E3 · draws TEN fact rows in three bands, not the document's nine", () => {
    const html = render();
    const rows = [
      "row.account",
      "row.where",
      "row.services",
      "row.plan",
      "row.status",
      "row.alreadyLevel",
      "row.openSince",
      "row.balanceNow",
      "row.autopay",
      "row.nextBill",
    ];
    expect(rows).toHaveLength(10);
    for (const row of rows) {
      expect(html, row).toContain(t(`billing.budgetEnrol.${row}`));
    }
    for (const band of ["band.whoWhere", "band.canLevel", "band.whatChanges"]) {
      expect(html, band).toContain(t(`billing.budgetEnrol.${band}`));
    }
  });

  it("TC-E4 · never renders a database id as a field's visible value (B14 rule 31)", () => {
    const html = render();
    // The account's HUMAN-FACING number is what a clerk reads. The uuid may
    // ride on an <option value> — which is not rendered text — and nowhere else.
    expect(html).toContain("100612");
    const visible = html.replace(/<option value="[^"]*"/g, "<option");
    expect(visible, "the uuid is not visible text anywhere").not.toContain(ACCOUNT_ID);
  });

  it("TC-E5 · the two warnings a clerk says out loud are drawn when their fact is true", () => {
    const html = render();
    expect(html).toContain(t("billing.budgetEnrol.warn.arrearsTitle"));
    expect(html).toContain(t("billing.budgetEnrol.warn.arrears"));
    expect(html).toContain(t("billing.budgetEnrol.warn.autopayTitle"));
    expect(html).toContain(t("billing.budgetEnrol.warn.autopay"));
  });

  it("TC-E6 · no arrears and no autopay means neither warning is drawn", () => {
    const html = render({
      eligibility: { ...ELIGIBILITY, open_balance: "0.000000" },
      detail: { ...DETAIL, autopay: false } as AccountDetail,
    });
    expect(html).not.toContain(t("billing.budgetEnrol.warn.arrearsTitle"));
    expect(html).not.toContain(t("billing.budgetEnrol.warn.autopayTitle"));
  });

  it("TC-E7 · states the three unserved figures in words, never as 0.00", () => {
    const html = render();
    // Each is a figure the DRAWING carries and no endpoint publishes.
    for (const absence of [
      "absent.aging", // the drawn `· 34 days`
      "absent.autopayMethod", // the drawn `· card ending 4218`
      "absent.nextBill", // the drawn `30 Nov 2026 · cycle 09-A`
      "absent.trailingTotal", // the drawn `$936.00`
      "absent.band", // the drawn `$54.60 – $101.40`
      "absent.planFlag", // the drawn `offers budget billing`
    ]) {
      expect(html, absence).toContain(t(`billing.budgetEnrol.${absence}`));
    }
    // ⚠ THE FALSE PASS THIS CASE IS WRITTEN AGAINST: a screen that renders
    // `$0.00` for a figure nobody could compute looks finished and says
    // something untrue. The only money on this page is the computed level and
    // the open balance, so a `0.00` anywhere is that substitution.
    expect(html).not.toContain("0.00");
  });

  it("TC-E8 · the server's rule-id sentence never reaches a clerk (B14 rule 31)", () => {
    const html = render();
    expect(html).not.toContain("BR-RAT-043");
    expect(html).not.toContain("OQ-237");
    expect(html).not.toContain(ELIGIBILITY.eligible_unavailable);
  });

  it("TC-E9 · the commit button names the figure that will really be written", () => {
    const html = render();
    // `enroll` computes the level itself and the request carries no override,
    // so the button names the COMPUTED figure. A button naming a number the
    // request does not carry is a customer paying something nobody agreed.
    // The DISPLAYED figure, 2dp with its symbol (CLAUDE.md rule 2) — not the
    // stored 4dp string, and not the drawing's illustration (B14 rule 37).
    expect(html).toContain(t("billing.budgetEnrol.commit", { amount: "$78.00" }));
  });

  it("TC-E10 · the override box is drawn, disabled, and says why", () => {
    const html = render();
    expect(html).toContain(t("billing.budgetEnrol.field.override"));
    expect(html).toContain(t("billing.budgetEnrol.field.overrideWhy"));
    // The blueprint's own doctrine: greyed WITH a reason, never missing.
    expect(html).toMatch(/id="bil-enrol-override"[^>]*disabled/);
  });

  it("TC-E11 · the band shows the tenant's own percentage, never a seeded 30", () => {
    const withoutParameters = render();
    expect(withoutParameters).toContain("± 30%");
    // BR-BIL-021 — a tenant whose settings cannot be read gets NO percentage,
    // not the ratified default. The false pass this guards: printing `± 30%`
    // for every tenant because the constant is in the front end.
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: Infinity } },
    });
    client.setQueryData(["budget-billing", "parameters"], {
      ...PARAMETERS,
      parameters: null,
      parameters_unavailable: "the tenant's budget parameters could not be read",
    });
    client.setQueryData(["budget-billing", "enrol", "account", ACCOUNT_ID], DETAIL);
    client.setQueryData(budgetEligibilityKey(ACCOUNT_ID), ELIGIBILITY);
    const html = renderToStaticMarkup(
      <QueryClientProvider client={client}>
        <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
          <ToastProvider>
            <MemoryRouter
            initialEntries={[`/brazosbend${BUDGET_ENROL_ROUTE}?account=${ACCOUNT_ID}`]}
          >
              <Routes>
                <Route path="/:tenant/billing/budget/enrol" element={<BudgetEnrolPage />} />
              </Routes>
            </MemoryRouter>
          </ToastProvider>
        </TenantRegionalProvider>
      </QueryClientProvider>,
    );
    expect(html).not.toContain("± 30%");
  });

  it("TC-E12 · the eligibility step draws both tests BEFORE the level", () => {
    const html = render();
    const tests = html.indexOf(t("billing.budgetEnrol.col.test"));
    const level = html.indexOf(t("billing.budgetEnrol.group.level"));
    expect(tests).toBeGreaterThan(-1);
    // The drawing's own reason: *"A clerk who fails at the last field has
    // already chosen a figure."*
    expect(tests).toBeLessThan(level);
  });

  it("TC-E13 · the ONE exit carries the tenant segment, and it is at the bottom", () => {
    const html = render();
    // ⚠ It is a button that navigates, so the address is asserted through the
    // route constant rather than an href. What this case really guards is the
    // FIXTURE: with no `:tenant` in the pattern the page would build
    // `//billing/budget`, and `toContain` would be perfectly happy.
    expect(BUDGET_TAB_ROUTE).toBe("/billing/budget");
    expect(BUDGET_ENROL_ROUTE).toBe("/billing/budget/enrol");
    // ⚠ **THIS CASE USED TO ASSERT `Cancel` AND `Back` BOTH RENDERED, AND THAT
    // WAS THE DEFECT RATHER THAN THE SPECIFICATION (PO 2026-09-19).** The head
    // drew `Cancel` and the footer drew `Back`, both navigating to
    // `BUDGET_TAB_ROUTE` — two controls, one destination, two words. The PO
    // reported the position (*"cancel button should be bottom not on top"*) on
    // Add units; on this screen the fix was to delete the head's copy, because
    // the footer already held the exit.
    expect(html).toContain(t("billing.budgetEnrol.cancel"));
    // The old footer word is gone from the page entirely — `Back` is the
    // step-back word (`wizard.back`) and nothing here has a previous step.
    expect(html).not.toContain(t("billing.budgetEnrol.back"));
    // ⚠ **AND THERE IS EXACTLY ONE OF IT.** `toContain` passes just as happily
    // on two, which is precisely how the duplicate survived until a person
    // looked at the screen. Counting is what makes this case able to fail.
    expect(html.split(`>${t("billing.budgetEnrol.cancel")}<`).length - 1).toBe(1);
    // It sits in the footer, below the last panel — not in the page head.
    expect(html.indexOf(t("billing.budgetEnrol.cancel")))
      .toBeGreaterThan(html.indexOf(t("billing.budgetEnrol.footer")));
  });
});

describe("§05 entry 25.1 — the helpers", () => {
  it("TC-E14 · the picker label falls back and never renders empty", () => {
    expect(
      enrolAccountLabel(
        { account_no: "100612", name: "Whitlock, R.", premise: "44 Pecan Row" } as never,
        t,
      ),
    ).toBe("100612 · Whitlock, R. — 44 Pecan Row");
    expect(enrolAccountLabel({ account_no: "100612", name: null, premise: null } as never, t)).toBe(
      "100612",
    );
    expect(enrolAccountLabel({ account_no: null, name: null, premise: null } as never, t)).toBe(
      t("billing.budgetEnrol.accountUnnamed"),
    );
  });

  it("TC-E15 · open-since counts WHOLE months and refuses a future date", () => {
    expect(openSinceMonths("2025-10-01", "2026-11-01")).toBe(13);
    // A day short of the anniversary is twelve months, not thirteen.
    expect(openSinceMonths("2025-10-15", "2026-10-14")).toBe(11);
    expect(openSinceMonths("2027-01-01", "2026-11-01")).toBeNull();
    expect(openSinceMonths("not-a-date", "2026-11-01")).toBeNull();
  });

  it("TC-E16 · pending, unpicked and unread are three different sentences", () => {
    // G122's defect in one assertion: a screen that says the same thing while
    // it loads and after a failed read cannot tell a clerk which happened.
    expect(eligibilityState("", true)).toBe("billing.budgetEnrol.absent.pickFirst");
    expect(eligibilityState("a", true)).toBe("billing.budgetEnrol.absent.loading");
    expect(eligibilityState("a", false)).toBe("billing.budgetEnrol.absent.noRead");
    expect(new Set([eligibilityState("", true), eligibilityState("a", true), eligibilityState("a", false)]).size).toBe(3);
  });
});

describe("§05 entry 25 — the door to the enrol form", () => {
  /**
   * ⚠ **THIS IS THE CASE `DEF-CWP-3925` SAYS TO WRITE, AND IT ASSERTS AN
   * ADDRESS.** The customer portal's front page shipped with two working doors
   * out of eight because every wave tested ITS OWN screen at ITS OWN address
   * and the question *has the door started pointing at it* belonged to nobody.
   * `G13` cannot see this: it asks whether a prop is passed, never whether a
   * destination is real.
   *
   * It asserts the WHOLE href, tenant segment included. With a `MemoryRouter`
   * carrying no `:tenant`, the tab would build `//billing/budget/enrol` — a
   * protocol-relative URL to another host — and a `toContain` on the tail would
   * be perfectly happy with it.
   */
  it("TC-E17 · the Budget Bills tab links to the enrol screen's real address", () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: Infinity } },
    });
    client.setQueryData(budgetListKey("enrolled|||1|50"), {
      results: [],
      count: 0,
      parameters: { override_bound_pct: "30" },
      parameters_unavailable: null,
      statuses: ["enrolled", "off_budget"],
      unavailable: [],
    });
    const html = renderToStaticMarkup(
      <QueryClientProvider client={client}>
        <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
          <ToastProvider>
            <MemoryRouter initialEntries={["/brazosbend/billing/budget"]}>
              <Routes>
                <Route path="/:tenant/billing/:tab" element={<BudgetBillsTab />} />
              </Routes>
            </MemoryRouter>
          </ToastProvider>
        </TenantRegionalProvider>
      </QueryClientProvider>,
    );
    expect(html).toContain(t("billing.budgetEnrol.door"));
    expect(html).toContain('href="/brazosbend/billing/budget/enrol"');
    // And the panel it replaces is gone — two ways to enrol would be two
    // answers to one question, and one of them asked for a pasted uuid.
    expect(html).not.toContain(t("billing.budget.step1"));
    expect(html).not.toContain(t("billing.budget.field.accountHint"));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-018 · 05-prototype/04 Billing, As Built.pdf §05 entry 25.1 (p122-p124)
// generated: 2026-09-15 by the §05 entry 25.1 build lane
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest src/features/billing/budgetEnrolPage.dom.test.tsx
// exceptions: E3 the page is rendered with `renderToStaticMarkup` rather than driven, the same posture `budgetBillsTable.dom.test.tsx` beside it takes — these cases assert what is DRAWN; the write path is proved by clicking (law 6), not here
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
