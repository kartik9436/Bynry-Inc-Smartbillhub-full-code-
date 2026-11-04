// ── Trace ──────────────────────────────────────────────
// Story:   US-MET-002 (S15 unit detail — the Account tab) · CR-089 wave I
// Rules:   CLAUDE.md hard-won law 2 (a fixture that cannot tell a working link
//          from a broken one is how a defect hides — MOUNT UNDER THE REAL PATH
//          PATTERN, or `useParams().tenant` is undefined and every address the
//          page builds comes out `//portal/…`, which reads as a perfectly good
//          string to `toContain`)
// ───────────────────────────────────────────────────────
/**
 * The Account tab's fixtures, in ONE place because two test files need them.
 *
 * ⚠ **EVERY RENDER HERE GOES THROUGH THE REAL ROUTE PATTERN**
 * (`/:tenant/premises/units/:unitId`). That is not tidiness: `DEF-CWP-3925`
 * records a front page whose test mounted the component bare inside a
 * `MemoryRouter` with no route, so `useParams().tenant` was undefined and every
 * link came out protocol-relative — a URL to another host that passes
 * `toContain` perfectly. The one assertion that could have caught it could not
 * be written. So the harness mounts what the app mounts.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { AccountRow, UnitAccountResponse, UnitRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { UnitDetailPage, unitAccountQueryKey, unitDetailQueryKey } from "./UnitDetailPage";
import { premisesAssetsQueryKey } from "./PremisesDetailPage";

export const TEST_TENANT = "brazosbend";
export const UNIT_ID = "u-101a";

export const UNIT: UnitRow = {
  id: UNIT_ID,
  unit_no: "U-00101-A",
  premises_id: "p-101",
  premise_no: "P-00101",
  premise_address: "1408 Bluestem Ln",
  label: "Unit A",
  unit_type: "residential",
  floor_label: null,
  square_feet: null,
  rate_plan_id: null,
  plan_effective_from: null,
  plan_locked: false,
  vacant_standby_auto: false,
  is_common_area: false,
  active: true,
  services: ["electric", "water"],
  meters: [],
  occupancy: "occupied",
  occupant: "Miller, Sarah",
  account_no: "A-00412",
  status: "active",
  metered_services: [],
  sub_metered: false,
} as unknown as UnitRow;

export const ACCOUNT: AccountRow = {
  id: "acc-1",
  account_no: "A-00412",
  name: "Miller, Sarah",
  unit_id: UNIT_ID,
  unit_label: "Unit A",
  balance: "247.300000",
  balance_currency: "USD",
  currency: "USD",
  status: "active",
  status_name: "Active",
  autopay: false,
  opened_at: "2024-03-12",
  closed_at: null,
} as unknown as AccountRow;

/**
 * The quiet shape — an occupied unit with nothing held and nothing owed beyond
 * its balance. **Every money state is a stated *none*, which is the answer**
 * (`PUJ-39`): a screen that omits the row has not looked, and a clerk cannot
 * tell those apart.
 */
export function quietAnswer(): UnitAccountResponse {
  return {
    unit: { id: UNIT_ID, unit_no: UNIT.unit_no, label: UNIT.label, is_common_area: false },
    account: ACCOUNT,
    facts: {
      protections: { in_force: [], lapsed: [], disconnection_held: false, kinds_in_force: [] },
      customer_class: {
        code: "residential",
        name: "Residential",
        legacy: false,
        subtype_code: null,
        subtype_name: null,
      },
      autopay: {
        elected: false,
        cash_only: false,
        nsf_count: 0,
        nsf_threshold: 2,
        will_be_taken: false,
        reading: "not_elected",
      },
      payment_plan: { state: "none", count: 0, running: 0 },
      budget_billing: { state: "none", level: null, currency: null },
      collections: { state: "none", tier: null, paused_reason: null },
      bounced_payments: { count: 0 },
      tax_exemption: { claimed: false, reference: null, expires_on: null },
      deposit: { held: "0.000000", currency: "USD", received_on: null, any: false },
      notes: [],
      reach: {
        bad_address: false,
        paperless: false,
        sms_reminders: false,
        preferred_language: null,
      },
      external_ref: null,
      credit_tier: { value: null, computed: false, why: "credit_tier_rules_unbuilt" },
    },
    owner_account: null,
    no_account_reason: null,
    facts_unavailable: null,
  };
}

/** Render the unit's Account tab, mounted at the address the app mounts it at. */
export function renderAccountTab(answer: UnitAccountResponse): string {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(unitDetailQueryKey(UNIT_ID), UNIT);
  client.setQueryData(unitAccountQueryKey(UNIT_ID), answer);
  // The Assets tab shares the premises registry key with PRM-02; unseeded, the
  // KPI strip above the tab renders a skeleton and swallows the panel.
  client.setQueryData(premisesAssetsQueryKey(UNIT.premises_id), {
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/units/${UNIT_ID}?tab=account`]}>
          <Routes>
            <Route path="/:tenant/premises/units/:unitId" element={<UnitDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}
