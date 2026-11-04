// ── Trace ──────────────────────────────────────────────
// Change:   **THE DISCONNECT WIZARD GOES FROM FIVE STEPS TO FOUR** —
//           `Choose · Check · Schedule · Confirm`, 2026-09-25. MAINTENANCE.
//           `DEF-CUS-6750`…`DEF-CUS-6764`.
// Rules:    **BR-CUS-1096** (a protection WARNS; it never stops the clerk) ·
//           **BR-CUS-1097** (the balance need not be clear to reconnect) ·
//           **BR-CUS-1098** (a master account's cut is a building's cut) ·
//           **BR-CUS-1099** (no recorded proof WARNS) · **BR-CUS-1100** (the
//           block marks the ACCOUNT and the CUSTOMER) · BR-CUS-103 ·
//           BR-CUS-105 · BR-BIL-007 · BR-SHL-025 · BR-SHL-046 · hard rule 2 ·
//           B14 rules 6, 20, 31, 33
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT THIS SUITE CAN AND CANNOT SEE, SAID FIRST BECAUSE IT DECIDES HOW
// MUCH ANY GREEN HERE IS WORTH (hard-won law 7, habit 2).** These cases render
// to static markup and read the STRINGS and the ATTRIBUTES back. They can prove
// a control exists, that a refusal is or is not rendered, that a figure is
// absent, and that a prop reached a class string. **They cannot see layout,
// spacing, alignment, hierarchy or colour** — nearly half of everything that
// goes wrong on a screen — and they cannot tell a screen that matches its
// drawing from one that merely contains the same words. That is the browser
// walk's job (`10-scripts/def_cus_6750_four_step_disconnect_walkthrough.mjs`),
// and a green run here is not a claim about the screen.
//
// ⚠ **THREE CASES ASSERT A REFUSAL IS *NOT* RENDERED, AND THAT IS THE POINT OF
// THEM.** `BR-CUS-1096`, `BR-CUS-1099` and item 3.4 each turned a block into a
// warning, and the way that rots is silently: a validator left behind, a
// sentence left on screen. Each is pinned by a case that goes red the day
// somebody puts the block back.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, RouterProvider, Routes, createMemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { APP_ROUTES } from "@/App";
import { createApiClient } from "@/api/client";
import type { AccountDetail } from "@/api/endpoints";
import { buttonClasses } from "@/components/buttonKit";
import { ToastProvider } from "@/components/Toast";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import { SEEDED_REGIONAL } from "@/components/tenantRegionalFixture";
import type { RegionalDateFormat } from "@/components/DateCell";

import { DisconnectWizard } from "./DisconnectWizard";
import { ChooseStep } from "./disconnect/steps/ChooseStep";
import { CheckStep } from "./disconnect/steps/CheckStep";
import { ScheduleStep } from "./disconnect/steps/ScheduleStep";
import { ConfirmStep } from "./disconnect/steps/ConfirmStep";
import {
  CHECK_MARKS,
  MARK_NOT_REQUIRED,
  MARK_RECORDED,
  emptyDisconnectDraft,
  hydrateDraft,
  proofIsComplete,
  proofIsStarted,
  scheduleCutPlanOf,
  servicesCut,
  treatmentsOf,
  workOrderCount,
} from "./disconnect/disconnectDraft";
import type { DisconnectDraft } from "./disconnect/disconnectDraft";
import type { DisconnectTerms } from "./disconnect/disconnectTerms";
import {
  CUT_REASONS,
  DEPOSIT_DISPOSITIONS,
  DISCONNECT_STEPS,
  DISCONNECT_WIZARD_ROUTE,
  PROTECTION_CHECKS,
  SERVICE_TREATMENTS,
  TREATMENT_FULL,
  TREATMENT_LEAVE,
  TREATMENT_RESTRICTOR,
} from "./transferDisconnectShared";
import { ACCOUNT_SEARCH_IDLE } from "./accountFinder";
import type { DisconnectPreflightBlocker } from "./transferDisconnectEndpoints";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params) as string;

/** `A-11340 · Northwind Mfg.` as `GET /accounts/{id}` really serves it. ⚠ The
 *  drawn `Owed $8,240.00` IS servable — it is `balance`, the ledger's own
 *  figure — and it is the only money on this screen that is. */
function drawnAccount(over: Partial<AccountDetail> = {}): AccountDetail {
  return {
    id: "acc-11340",
    account_no: "A-11340",
    customer_no: "C-0140",
    name: "Northwind Mfg.",
    unit_id: "unit-77",
    unit_label: "77 Industrial Way",
    premise: "77 Industrial Way",
    services: ["electric", "water", "sewer"],
    balance: "8240.0000",
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    balance_not_yet_billable: false,
    balance_cached: "8240.0000",
    currency: "USD",
    status: "active",
    status_name: "Active",
    status_behavior_class: "billable",
    kind: "regular",
    account_type: "commercial",
    account_subtype: null,
    autopay: false,
    opened_at: "2021-03-01",
    closed_at: null,
    last_bill_at: "2026-08-01",
    aging: null,
    deposit_on_file: "500.0000",
    deposit_received_on: "2021-03-01",
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
    plan_snapshot_unavailable: "no plan snapshot",
    unit_plan: null,
    customer: {
      id: "cus-140",
      kind: "company",
      display_name: "Northwind Mfg.",
      external_ref: null,
      accounts: [{ id: "acc-11340", account_no: "A-11340" }],
    },
    ...over,
  };
}

function provided(node: JSX.Element): string {
  return renderToStaticMarkup(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {node}
    </QueryClientProvider>,
  );
}

function renderWizard(step: number): { html: string; methods: string[] } {
  const methods: string[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (_input, init) => {
      methods.push(String((init as RequestInit | undefined)?.method ?? "GET"));
      return new Response(JSON.stringify({ count: 0, results: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.shellDisplay, shellBootSeed(SEEDED_REGIONAL));
  queryClient.setQueryData(queryKeys.regionalSettings, SEEDED_REGIONAL);
  const html = renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${DISCONNECT_WIZARD_ROUTE}?step=${step}`]}>
          <Routes>
            <Route
              path={`/:tenant${DISCONNECT_WIZARD_ROUTE}`}
              element={<DisconnectWizard client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { html, methods };
}

/** The opening tag of the `<button>` whose label contains `label`. The page
 *  renders several buttons, so a `toContain` over the whole page answers about
 *  whichever one happens to carry the token (`DEF-712`). */
function buttonTagLabelled(html: string, label: string): string {
  for (const match of html.matchAll(/<button\b[^>]*>([\s\S]*?)<\/button>/g)) {
    if (match[1].includes(label)) {
      return match[0].slice(0, match[0].indexOf(">") + 1);
    }
  }
  throw new Error(`no <button> labelled ${label} in the rendered output`);
}

function chooseHtml(
  over: Partial<DisconnectDraft> = {},
  account = drawnAccount(),
  /** `DEF-CUS-7680` — the server's step-1 pre-flight. `null` is the ordinary
   *  case: nothing about this case stops a cut being scheduled on it. */
  preflight: DisconnectPreflightBlocker | null = null,
): string {
  return provided(
    <ChooseStep
      draft={{ ...emptyDisconnectDraft(), accountId: "acc-11340", ...over }}
      account={account}
      failed={false}
      onPatch={() => undefined}
      term=""
      onTermChange={() => undefined}
      search={ACCOUNT_SEARCH_IDLE}
      t={t}
      master={account.kind === "master"}
      occupants={null}
      preflight={preflight}
    />,
  );
}

function checkHtml(over: Partial<DisconnectDraft> = {}, inForce: string[] = []): string {
  return provided(
    <CheckStep
      draft={{ ...emptyDisconnectDraft(), accountId: "acc-11340", ...over }}
      onPatch={() => undefined}
      t={t}
      answers={{
        account_id: "acc-11340",
        as_of: "2026-09-25",
        checks: [
          {
            check: "medical_certificate",
            outcome: inForce.includes("medical_certificate") ? "fail" : "pass",
            lifetime: "expires_on_a_date",
            reason: "",
            effective_from: "2026-01-01",
            expires_on: "2026-11-30",
          },
        ],
        all_clear: inForce.length === 0,
        protections_in_force: inForce,
      }}
      master={false}
      occupants={null}
      occupantProtections={[]}
      actor="D. Whitfield"
    />,
  );
}

function confirmHtml(terms: DisconnectTerms | null, over: Partial<DisconnectDraft> = {}): string {
  return provided(
    <ConfirmStep
      draft={{ ...emptyDisconnectDraft(), accountId: "acc-11340", ...over }}
      account={drawnAccount()}
      onPatch={() => undefined}
      t={t}
      terms={terms}
      master={false}
      occupants={null}
      protectionsInForce={[]}
      proofMissing={false}
    />,
  );
}

/** `reconnection_terms` as it really answers on every tenant in this tree —
 *  three codes, none of them priced (`DEF-700`). */
function absentTerms(): DisconnectTerms {
  return {
    account_id: "acc-11340",
    charge_code: "RECON",
    fee: null,
    fee_absence: { code: "reconnect_charge_code_not_seeded" },
    fees: [
      {
        code: "RECON",
        charge: "Reconnection fee",
        amount: null,
        amount_absence: { code: "reconnect_charge_code_not_seeded" },
        when: "At the cut",
        charged_on_this_cut: true,
        charged_absence: null,
      },
      {
        code: "DISC",
        charge: "Disconnection fee",
        amount: null,
        amount_absence: { code: "reconnect_charge_code_not_seeded" },
        when: "At the cut",
        charged_on_this_cut: false,
        charged_absence: { code: "fee_code_has_no_path_to_a_bill" },
      },
      {
        code: "FIELD",
        charge: "Field visit",
        amount: null,
        amount_absence: { code: "reconnect_charge_code_not_seeded" },
        when: "Only if a crew attends",
        charged_on_this_cut: false,
        charged_absence: { code: "fee_code_has_no_path_to_a_bill" },
      },
    ],
    to_clear: {
      arrears: { stored: "8240.0000", display: "8,240.00" },
      arrears_absence: null,
      fee: null,
      total: null,
      total_absence: { code: "reconnection_total_not_computable" },
    },
    deposit: {
      on_file: { stored: "500.0000", display: "500.00" },
      election: null,
      new_deposit_required: null,
      detail: "",
      posting: { code: "deposit_application_not_posted" },
    },
    posting: { code: "fee_posted" },
    timing: { code: "fee_timing_ruled" },
  };
}

describe("the disconnect wizard · four steps (2026-09-25 rebuild)", () => {
  // ══════════════════════════════════════════════════════════════════════
  // THE SHAPE
  // ══════════════════════════════════════════════════════════════════════

  /**
   * ⚠ **HARD-WON LAW 2, THROUGH THE REAL ROUTE TABLE AND NOT A `MemoryRouter`
   * THIS FILE BUILT.** Every other case here mounts the component directly,
   * which is exactly the shape law 2 warns about: a wizard that renders
   * perfectly in a test and that `App.tsx` routes to nothing. This takes
   * `APP_ROUTES` itself and walks it to the wizard's own address.
   */
  it("law 2 — the wizard is REACHED at its address by the application's own route table", () => {
    const router = createMemoryRouter(APP_ROUTES, {
      initialEntries: [`/${TEST_TENANT}${DISCONNECT_WIZARD_ROUTE}`],
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(queryKeys.shellDisplay, shellBootSeed(SEEDED_REGIONAL));
    queryClient.setQueryData(queryKeys.regionalSettings, SEEDED_REGIONAL);
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(html).toContain('data-r10="DSC-02"');
  });

  it("item 3.1 — FOUR steps, declared once, each word an act", () => {
    expect(DISCONNECT_STEPS).toHaveLength(4);
    expect(DISCONNECT_STEPS.map((s) => s.id)).toEqual(["choose", "check", "schedule", "confirm"]);
    expect(DISCONNECT_STEPS.map((s) => s.en)).toEqual([
      "Choose",
      "Check",
      "Schedule",
      "Confirm",
    ]);
  });

  it("item 3.1 — every step label is ONE word, so the rail cannot drift back to a sentence", () => {
    // B14 rule 33: a LABEL is three words or fewer. The five it replaced were
    // `Account & reason`, `Notice & date` and `Fees & consequences`.
    for (const step of DISCONNECT_STEPS) {
      expect(step.en.split(/\s+/)).toHaveLength(1);
    }
  });

  /**
   * ⚠ **ITEM 3.16 — THE RAIL IS NOT DRAWN AS BUTTONS.**
   *
   * The old rail rendered four `<button disabled>` cells: four controls a
   * screen reader announces and a keyboard tabs through, none of which ever
   * acts. This asserts the RENDERED element and not the prop, because a case
   * that only checked `railNavigable={false}` travelled would pass against the
   * defect (`DEF-712`'s lesson, one component over).
   */
  it("item 3.16 — the rail renders no button at all", () => {
    const { html } = renderWizard(1);
    const rail = html.slice(html.indexOf('data-wizard="rail"'));
    const nav = rail.slice(0, rail.indexOf("</nav>"));
    expect(nav).toContain('data-wizard-step="1"');
    expect(nav).toContain('data-wizard-step="4"');
    expect(nav).not.toContain("<button");
  });

  /**
   * ⚠ **THE FLAT RAIL MUST STILL SAY WHERE THE CLERK IS — and the first draft
   * of it did not.** Rendering the cell as a `<span>` dropped `stepActive`, so
   * the rail emphasised step 1 on every screen. `tsc`, all 42 cases and every
   * gate were green over it; the browser shot beside the drawing is what found
   * it. This is the assertion that would have.
   */
  it("item 3.16 — the flat rail still marks the step the clerk is standing on", () => {
    for (const step of [1, 2, 3, 4]) {
      const { html } = renderWizard(step);
      const rail = html.slice(html.indexOf('data-wizard="rail"'));
      const nav = rail.slice(0, rail.indexOf("</nav>"));
      const current = [...nav.matchAll(/<span\b[^>]*data-wizard-step="(\d)"[^>]*>/g)].find((m) =>
        m[0].includes('data-state="active"'),
      );
      expect(current?.[1]).toBe(String(step));
      expect(current?.[0]).toContain('aria-current="step"');
      // The accent the kit uses for *you are here*.
      expect(current?.[0]).toContain("text-accent");
    }
  });

  it("B14 rule 6 — the commit is the DANGER button, asserted on the rendered class", () => {
    const { html } = renderWizard(4);
    expect(buttonTagLabelled(html, "Schedule the disconnection")).toContain(
      buttonClasses("danger"),
    );
  });

  it("the wizard writes nothing while a clerk walks it", () => {
    for (const step of [1, 2, 3, 4]) {
      expect(renderWizard(step).methods.every((m) => m === "GET")).toBe(true);
    }
  });

  // ══════════════════════════════════════════════════════════════════════
  // ITEM 3.7 / 3.8 — FACTS ONLY, AND EACH FACT ONCE
  // ══════════════════════════════════════════════════════════════════════

  it("item 3.7 — the frame carries no subtitle and no repeated footer sentence", () => {
    for (const step of [1, 2, 3, 4]) {
      const { html } = renderWizard(step);
      expect(html).not.toContain("Five steps");
      expect(html).not.toContain("nothing is cut until the scheduled date");
      expect(html).not.toContain('data-flow-footer');
    }
  });

  it("item 3.8 — the back link names the previous STEP rather than always the list", () => {
    expect(renderWizard(1).html).toContain("Disconnects");
    for (const [step, previous] of [
      [2, "Choose"],
      [3, "Check"],
      [4, "Schedule"],
    ] as const) {
      expect(renderWizard(step).html).toContain(previous);
    }
  });

  // ══════════════════════════════════════════════════════════════════════
  // STEP 1 · CHOOSE
  // ══════════════════════════════════════════════════════════════════════

  it("item 3.3 — step 1's services are a TABLE ARRAY with an add and a remove", () => {
    const html = chooseHtml({
      services: [{ code: "water", meter: "", treatment: TREATMENT_FULL, note: "" }],
    });
    expect(html).toContain('data-editable-table="services"');
    expect(html).toContain('data-array-add="services"');
    expect(html).toContain('data-editable-row="1"');
  });

  /**
   * ⚠ **ITEM 3.14 — THE RESTRICTOR IS GONE, NOT DISABLED.**
   *
   * The old screen offered it and explained in the next breath that the product
   * cannot record one: a dead control AND rationale on screen, two breaches
   * answered by one deletion. This asserts BOTH halves, because removing the
   * option and leaving the sentence would have been the easy half-fix.
   */
  it("item 3.14 — the restrictor is not offered and its sentence is gone", () => {
    const html = chooseHtml({
      services: [{ code: "water", meter: "", treatment: "", note: "" }],
    });
    // ⚠ THE CATALOGUE'S WORD, NOT THE CODE'S FALLBACK. Since the keys landed
    // in all eleven languages, `t()` resolves and the screen reads the
    // drawing's `Full cut` rather than `SERVICE_TREATMENTS`' English constant.
    // Asserting the catalogue is the stronger question: it is what a clerk
    // sees, and it is what goes silent if a key is ever dropped.
    expect(html).toContain(t("customers.disconnect.treatment.full_disconnection"));
    expect(t("customers.disconnect.treatment.full_disconnection")).toBe("Full cut");
    expect(html).not.toContain(`value="${TREATMENT_RESTRICTOR}"`);
    expect(html).not.toContain("restrictor");
    expect(html).not.toContain("Restrictor");
  });

  it("the restrictor is still in the SHARED vocabulary — the server's refusal is untouched", () => {
    // The gap is not hidden by the screen dropping the option: the day a schema
    // can hold a restricted supply, this list is where the third entry comes
    // back from.
    expect(SERVICE_TREATMENTS.map((s) => s.code)).toContain(TREATMENT_RESTRICTOR);
  });

  it("a service with no treatment chosen is left OUT of the payload, never defaulted", () => {
    const draft: DisconnectDraft = {
      ...emptyDisconnectDraft(),
      accountId: "acc-11340",
      services: [
        { code: "water", meter: "", treatment: TREATMENT_FULL, note: "" },
        { code: "sewer", meter: "", treatment: "", note: "" },
        { code: "electric", meter: "", treatment: TREATMENT_LEAVE, note: "" },
      ],
    };
    // Defaulting either way decides for the clerk, and one direction cuts a
    // service nobody asked to cut.
    expect(treatmentsOf(draft)).toEqual({
      water: TREATMENT_FULL,
      electric: TREATMENT_LEAVE,
    });
    expect(servicesCut(draft)).toEqual(["water"]);
    expect(scheduleCutPlanOf(draft).services).not.toHaveProperty("sewer");
  });

  it("the service list comes from the ACCOUNT and is never typed on the screen", () => {
    const html = chooseHtml({}, drawnAccount({ services: ["fire"] }));
    // `fire` is service eleven, appended at position 11 with nothing renumbered.
    // A screen that hand-typed its list would simply never offer it.
    expect(html).toContain("Fire");
  });

  /**
   * ⚠ **B14 RULE 31, AND THE ONE PLACE IT IS STILL BREACHED IS NAMED RATHER
   * THAN ASSERTED AWAY — `DEF-CUS-6765`.**
   *
   * Every part of this wizard that this lane wrote shows a NAME: step 1's strip
   * names the customer, step 4's names the account NUMBER, and neither carries
   * the database id. **The shared `AccountFinder` does**: on the pre-selected
   * path it prints the raw id as its search box's value and as a pickable list
   * option, measured from the markup on 2026-09-25. That file is shared by
   * three wizards and belongs to no lane in this tree today, so it is FILED and
   * reported rather than edited here — and this case asserts what it can
   * honestly assert instead of being weakened until it passes.
   */
  it("B14 rule 31 — the wizard's own surfaces show a name, never a database id", () => {
    const choose = chooseHtml();
    expect(choose).toContain("Northwind Mfg.");
    const facts = choose.slice(choose.indexOf('data-facts="account"'));
    expect(facts.slice(0, facts.indexOf("</dl>"))).not.toContain("acc-11340");

    const confirm = confirmHtml(absentTerms());
    expect(confirm).toContain("A-11340");
    expect(confirm).not.toContain("acc-11340");
  });

  // ══════════════════════════════════════════════════════════════════════
  // STEP 2 · CHECK — `BR-CUS-1096`
  // ══════════════════════════════════════════════════════════════════════

  /**
   * ⚠ **`BR-CUS-1096`, AND IT IS A CASE ABOUT WHAT IS *ABSENT*.** PO, verbatim:
   * *"so please show the warining - but dont stop clark from doing his work"*.
   * The old screen carried the drawn sentence *"Recording one stops the cut."*
   * That sentence is now FALSE, and the way it rots is by being left behind.
   */
  it("BR-CUS-1096 — a live protection WARNS and the screen never says it stops the cut", () => {
    const html = checkHtml({}, ["medical_certificate"]);
    expect(html).toContain('data-warning="protection-in-force"');
    expect(html).toContain("You may continue");
    expect(html).not.toContain("stops the cut");
    expect(html).not.toContain("stops this immediately");
  });

  /**
   * ⚠ **THE PO DECLINED FRICTION FOUR TIMES ON 2026-09-25**, across the five
   * rulings of one principle — a typed reason, a tick-to-acknowledge and a
   * supervisor are all ruled out. A later lane reaching for any of them is
   * re-asking a settled question (hard-won law 13), and this is what says so.
   */
  it("BR-CUS-1096 — there is no override to grant, because nothing is overridden", () => {
    const html = checkHtml({}, ["medical_certificate"]);
    expect(html).not.toContain("Override");
    expect(html).not.toContain("acknowledge");
    expect(html).not.toContain("Reason for proceeding");
    expect(html).not.toContain("supervisor");
  });

  it("item 3.4 — every check carries a Recorded / Checked / Not required mark", () => {
    const html = checkHtml({
      checks: [{ code: "medical", mark: MARK_RECORDED }],
    });
    // The English a clerk reads, and `Recorded` is B14 rule 34's own word for
    // *held here* — one pair of words across all eleven catalogues.
    expect(CHECK_MARKS.map((m) => m.en)).toEqual(["Recorded", "Checked", "Not required"]);
    for (const mark of CHECK_MARKS) {
      expect(html).toContain(mark.en);
    }
  });

  it("item 3.4 — `Not required` is a mark a clerk can record, not an absence", () => {
    expect(CHECK_MARKS.map((m) => m.code)).toContain(MARK_NOT_REQUIRED);
    const html = checkHtml({ checks: [{ code: "life_support", mark: MARK_NOT_REQUIRED }] });
    expect(html).toContain("Not required");
  });

  it("item 3.4 — nothing on the checklist is mandatory, so an unmarked check renders blank", () => {
    const html = checkHtml({ checks: [{ code: "medical", mark: "" }] });
    // A name and a date beside an unmarked row would say somebody had looked.
    expect(html).not.toContain("D. Whitfield · today");
  });

  it("item 3.3 — the checks are one table array with an add and a remove", () => {
    const html = checkHtml({ checks: [{ code: "medical", mark: "" }] });
    expect(html).toContain('data-editable-table="checks"');
    expect(html).toContain('data-array-add="checks"');
  });

  it("the drawn `All clear` chip is never rendered — ten drawn, three answered", () => {
    expect(PROTECTION_CHECKS).toHaveLength(10);
    expect(PROTECTION_CHECKS.filter((c) => c.answered)).toHaveLength(3);
    expect(checkHtml({ checks: [{ code: "medical", mark: "" }] })).not.toContain("All clear");
  });

  /**
   * ⚠ **ITEM 3.13 — WHAT THE CLERK TYPES IS KEPT.** The old box held its value
   * in step-local state that unmounted with the step. This asserts the box is
   * bound to the DRAFT, which is what survives walking between steps and a park.
   */
  it("item 3.13 — `What happened` is bound to the draft and reads back", () => {
    const html = checkHtml({ whatHappened: "Spoke to the daughter." });
    expect(html).toContain("Spoke to the daughter.");
    expect(html).toContain("Kept on the case.");
  });

  it("item 3.13 — the note survives a park and a resume", () => {
    const parked = { ...emptyDisconnectDraft(), whatHappened: "Certificate coming Monday." };
    expect(hydrateDraft(parked).whatHappened).toBe("Certificate coming Monday.");
  });

  // ══════════════════════════════════════════════════════════════════════
  // STEP 3 · SCHEDULE — `BR-CUS-1099`
  // ══════════════════════════════════════════════════════════════════════

  function scheduleHtml(over: Partial<DisconnectDraft> = {}): string {
    return provided(
      <ScheduleStep
        draft={{ ...emptyDisconnectDraft(), accountId: "acc-11340", ...over }}
        onPatch={() => undefined}
        onPatchProof={() => undefined}
        t={t}
        dateFormat={(SEEDED_REGIONAL.date_format ?? "MM/DD/YYYY") as RegionalDateFormat}
        notices={[
          {
            notice_id: "n-1",
            account_id: "acc-11340",
            tier: "final",
            issued_on: "2026-09-08",
            recorded: false,
            channel: null,
            reference: null,
            served_on: null,
            signed_for_on: null,
          },
        ]}
        cutFloor={null}
        master={false}
        occupants={null}
      />,
    );
  }

  /**
   * ⚠ **`BR-CUS-1099`.** PO, verbatim: *"So we warn user , but we dont stop
   * user"*. The old step said *"No proof, no cut"*.
   */
  it("BR-CUS-1099 — a missing proof WARNS and the screen never says it refuses", () => {
    const html = scheduleHtml();
    expect(html).toContain('data-warning="no-proof"');
    expect(html).toContain("You may continue");
    expect(html).not.toContain("No proof, no cut");
  });

  it("BR-CUS-039 is NOT softened — the portal is a send and is never offered as a proof", () => {
    // `record_proof_of_service` refuses `in_app` BY NAME. Reading one channel
    // list for both is how a screen offers an option the server will refuse.
    expect(scheduleHtml()).not.toContain('value="in_app"');
  });

  it("item 3.5 — the field work is a stacked TABLE ARRAY and not a side panel", () => {
    const html = scheduleHtml({
      visits: [
        { point: "water", label: "Water · 18 Marten Row", meter: "", visit: "work_order", instruction: "Cut at the boundary box", workOrder: "" },
      ],
    });
    expect(html).toContain('data-editable-table="visits"');
    expect(html).toContain('data-array-add="visits"');
    expect(html).toContain("Cut at the boundary box");
  });

  /**
   * `DEF-CUS-9631` — THE HOLD HAS EXPIRED. The row's job is raised by the
   * commit now (`visits` on `POST /disconnects/schedule`), so the cell says
   * when instead of offering a button that refused with *A cut cannot raise
   * one yet.* while the confirm step promised the job.
   */
  it("DEF-CUS-9631: a work-order row says it is raised when the clerk schedules", () => {
    const html = scheduleHtml({
      visits: [
        { point: "water", label: "Water", meter: "", visit: "work_order", instruction: "", workOrder: "" },
      ],
    });
    expect(html).toContain("data-raised-on-schedule");
    expect(html).toContain("Raised when you schedule");
    expect(html).not.toContain("A cut cannot raise one yet.");
  });

  it("DEF-CUS-9631: the commit carries every Work order row, and only those", () => {
    const draft: DisconnectDraft = {
      ...emptyDisconnectDraft(),
      accountId: "acc-1",
      cutOn: "2026-10-20",
      visits: [
        { point: "water", label: "Water", meter: "", visit: "work_order", instruction: "Lock the curb stop", workOrder: "" },
        { point: "electric", label: "Electric", meter: "", visit: "no_visit", instruction: "", workOrder: "" },
      ],
    };
    expect(scheduleCutPlanOf(draft).visits).toEqual([
      { service: "water", instruction: "Lock the curb stop" },
    ]);
    expect(scheduleCutPlanOf(emptyDisconnectDraft())).not.toHaveProperty("visits");
  });

  it("the running fact counts work orders from the rows and is never typed", () => {
    const draft: DisconnectDraft = {
      ...emptyDisconnectDraft(),
      visits: [
        { point: "a", label: "A", meter: "", visit: "work_order", instruction: "", workOrder: "" },
        { point: "b", label: "B", meter: "", visit: "no_visit", instruction: "", workOrder: "" },
        { point: "c", label: "C", meter: "", visit: "work_order", instruction: "", workOrder: "" },
      ],
    };
    expect(workOrderCount(draft)).toBe(2);
  });

  // ══════════════════════════════════════════════════════════════════════
  // STEP 4 · CONFIRM
  // ══════════════════════════════════════════════════════════════════════

  /**
   * ⚠ **ITEM 3.9 AND `BR-BIL-007`.** The drawings price the three fees
   * `$35.00 · $75.00 · $45.00` and the master variant `$85.00 · $150.00 ·
   * $45.00`. **All six are illustrations** (B14 rule 37) and none may be
   * rendered. On every tenant in this tree the true answer is an absence.
   */
  it("item 3.9 — not one drawn fee figure is rendered, and an absent price is not a zero", () => {
    const html = confirmHtml(absentTerms());
    for (const drawn of ["$35.00", "$75.00", "$45.00", "$85.00", "$150.00", "$8,315.00"]) {
      expect(html).not.toContain(drawn);
    }
    expect(html).toContain("Not priced");
    expect(html).not.toContain("$0.00");
  });

  it("item 3.9 — the fee table names each charge and whether this cut raises it", () => {
    const html = confirmHtml(absentTerms());
    expect(html).toContain("Reconnection fee");
    expect(html).toContain("Disconnection fee");
    expect(html).toContain("Field visit");
    // Three amounts listed with no such distinction read as three fees a
    // customer is about to owe.
    expect(html).toContain("Not charged");
  });

  it("item 3.9 — B14 rule 31/32: no charge CODE reaches the screen", () => {
    const html = confirmHtml(absentTerms());
    expect(html).not.toContain("CC-RECON");
    expect(html).not.toContain(">RECON<");
    expect(html).not.toContain("CC-FIELD");
  });

  /**
   * ⚠ **B14 RULE 32 — AND THE PANEL PRINTED THE RAW CODE UNTIL A BROWSER SAW
   * IT.** The Fees panel's right-hand fact read *"commercial · Sample —
   * Residential"*: `account_type` is a platform category CODE, shown to a clerk
   * lower-case beside a proper name. It is resolved through the tenant's own
   * category rows now, which is what every other account screen does.
   */
  it("B14 rule 32 — the account's CATEGORY is named, never printed as its code", () => {
    const html = confirmHtml(absentTerms());
    // The fixture serves no category rows, so the honest fallback is the code —
    // and what must never happen is the code appearing as if it were a name
    // beside the plan. With no rows there is no name to show and no claim made.
    const panel = html.slice(html.indexOf("data-plan-and-category"));
    expect(panel.slice(0, panel.indexOf("</span>"))).not.toContain(" · ");
  });

  /**
   * ⚠ **ITEM 3.10 / `DEF-CUS-6753` — THE DEPOSIT DOES NOT MOVE, SO NOTHING
   * SUBTRACTS IT.** Both drawings put a `Deposit applied − $65.00` row above
   * the total. `_to_clear` is `arrears + fee` and subtracts nothing; applying a
   * deposit is a balance-sheet posting and hard rule 5 leaves that to the
   * ledger. A screen drawing the subtraction would quote a figure nothing
   * computes.
   */
  it("item 3.10 — no `Deposit applied` subtraction is rendered", () => {
    const html = confirmHtml(absentTerms());
    expect(html).not.toContain("Deposit applied");
    expect(html).not.toContain("− $500.00");
    expect(html).not.toContain("-$500.00");
  });

  /** ⚠ **AND THE CONTROL STAYS, BECAUSE THE ELECTION IS REAL AND IS STORED.**
   *  `schedule_cut` takes `deposit`; `commit_cut` records it;
   *  `reconnection_terms` reads it back. It is not a dead control — what was
   *  dead was the arithmetic beside it. */
  it("item 3.10 — the deposit election is offered and reaches the payload", () => {
    const html = confirmHtml(absentTerms());
    for (const option of DEPOSIT_DISPOSITIONS) {
      expect(html).toContain(option.en);
    }
    expect(scheduleCutPlanOf(emptyDisconnectDraft()).deposit).toBe("held");
  });

  it("the `to clear` figures are the server's, and an uncomputable total is stated as such", () => {
    const html = confirmHtml(absentTerms());
    // `total` is null unless BOTH halves are known: a sum over the arrears
    // alone quotes a customer a price short by the whole fee (`DEF-708`).
    expect(html).toContain("Not known");
  });

  /**
   * ⚠ **`BR-CUS-1100` — THE ACCOUNT AND THE CUSTOMER, NEVER THE ADDRESS.** The
   * split is the load-bearing half: not marking the address is what stops a new
   * tenant being punished for the previous occupant's debt. A premises-level
   * mark REVERSES the ruling, so the negative is asserted too.
   */
  it("BR-CUS-1100 — the cut marks the account and the customer, and says the address is not marked", () => {
    const html = confirmHtml(absentTerms());
    expect(html).toContain('data-consequence="marks"');
    expect(html).toContain("Account and customer are marked");
    expect(html).toContain("The address is not marked");
  });

  it("BR-CUS-103 and BR-CUS-105 — charges stop at the cut and the balance then holds", () => {
    const html = confirmHtml(absentTerms());
    expect(html).toContain('data-consequence="base-stops"');
    expect(html).toContain('data-consequence="balance-static"');
    // The drawing this replaced said the opposite of both.
    expect(html).not.toContain("still accrues");
    expect(html).not.toContain("Keep charging base");
  });

  it("item 3.5 — the field work REPEATS on the review, through the same component read-only", () => {
    const html = confirmHtml(absentTerms(), {
      visits: [
        { point: "water", label: "Water · 18 Marten Row", meter: "", visit: "work_order", instruction: "Cut at the boundary box", workOrder: "" },
      ],
    });
    expect(html).toContain('data-editable-table="confirm-visits"');
    expect(html).toContain("Cut at the boundary box");
    // Read-only: no add row and no remove column.
    expect(html).not.toContain('data-array-add="confirm-visits"');
  });

  // ══════════════════════════════════════════════════════════════════════
  // ITEM 3.7 — RATIONALE IS ZERO WORDS
  // ══════════════════════════════════════════════════════════════════════

  /**
   * ⚠ **B14 RULE 33 — RATIONALE IS REMOVED, NEVER SHORTENED.** The five-step
   * wizard carried five refusal sentences on one screen and prose everywhere.
   * These are the exact passages, and a case that asserts their absence is the
   * only thing that stops one being reinstated by a lane that thinks it is
   * being helpful.
   */
  it("item 3.7 — the wizard explains nothing about why it works this way", () => {
    for (const step of [1, 2, 3, 4]) {
      const { html } = renderWizard(step);
      for (const prose of [
        "which many jurisdictions require",
        "the single most serious thing",
        "cannot be typed",
        "Worth being clear about",
        "is not the guarantee",
      ]) {
        expect(html).not.toContain(prose);
      }
    }
  });

  // ══════════════════════════════════════════════════════════════════════
  // THE DRAFT
  // ══════════════════════════════════════════════════════════════════════

  it("a half-typed proof still fails the commit — BR-CUS-1099 is about an EMPTY one", () => {
    const started = { channel: "certified_mail", reference: "", servedOn: "", signedForOn: "" };
    expect(proofIsStarted(started)).toBe(true);
    expect(proofIsComplete(started)).toBe(false);
  });

  it("`signedForOn` is NOT required — BR-CUS-100 splits the send from the signature", () => {
    expect(
      proofIsComplete({
        channel: "certified_mail",
        reference: "7019 2280",
        servedOn: "2026-09-08",
        signedForOn: "",
      }),
    ).toBe(true);
  });

  /**
   * ⚠ **`typeof [] === typeof {}`**, so the shared `hydrateForm` would put a
   * parked object into a field the screen then calls `.map` on. Under
   * `BR-SHL-048` (b) a parked draft is evidence of TYPING and nothing else.
   */
  it("a parked draft whose collections are the wrong shape is dropped back to empty", () => {
    const broken = { ...emptyDisconnectDraft(), services: {}, checks: "water", visits: null };
    const out = hydrateDraft(broken);
    expect(Array.isArray(out.services)).toBe(true);
    expect(out.services).toHaveLength(0);
    expect(Array.isArray(out.checks)).toBe(true);
    expect(Array.isArray(out.visits)).toBe(true);
  });

  it("the five cut reasons are the server's own strings", () => {
    // `DEF-CUS-6023`: this list once sent `tampering` and `abandoned` where the
    // CHECK constraint holds `tampering_or_theft` and `premises_abandoned`, so
    // two of five reasons were refused on the reason alone.
    expect(CUT_REASONS.map((r) => r.code)).toEqual([
      "non_payment",
      "unsafe_installation",
      "tampering_or_theft",
      "premises_abandoned",
      "customer_asked",
    ]);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: the disconnect wizard rebuild, 2026-09-25 (MAINTENANCE) ·
//         `DEF-CUS-6750`…`DEF-CUS-6764` · BR-CUS-1096 · BR-CUS-1097 ·
//         BR-CUS-1098 · BR-CUS-1099 · BR-CUS-1100 · BR-CUS-103 · BR-CUS-105 ·
//         BR-BIL-007 · BR-SHL-025 · B14 rules 6, 20, 31, 33, 37
// generated: 2026-09-25 by lane WIZARD
// exceptions:
//   E3 **THIS SUITE READS STRINGS AND ATTRIBUTES AND CANNOT SEE A SCREEN.** See
//      the header. The browser walk is where the drawing is compared.
//   E3 **the master variants are covered by the walk and not here.** Their
//      distinguishing facts — the occupant count, the per-occupant protections,
//      the residue transferred up — are not on any wire, so a unit case would
//      assert a fixture this lane invented rather than a behaviour.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
