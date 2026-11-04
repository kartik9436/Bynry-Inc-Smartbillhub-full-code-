// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W7 — `TRF-02`'s cases (B18 §5.7.7). US-CUS-029 §3.
// Rules:    BR-CUS-057 + ❄️ WE-7 / GT-23 (the deposit's interest is unreadable,
//           so the CARRIED TOTAL is unreadable — asserted as an ABSENCE of the
//           drawn figures) · BR-CUS-023 · BR-CUS-086 · BR-SHL-025 · BR-SHL-046 ·
//           CLAUDE.md hard rule 2 (no money is computed in this client)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE MONEY CASES ASSERT THAT A FIGURE IS *NOT* ON THE SCREEN, AND THAT IS
// THE WHOLE POINT.** §5.7.7 draws `$150.00 principal`, `$3.50 interest` and
// `$153.50 moving across`, and the arithmetic foots four ways over three steps.
// The PRINCIPAL is servable — `GET /accounts/{id}` carries `deposit_on_file` —
// and the other two are not: BR-CUS-057's accrual is published by nothing, so
// principal + interest is not a number this product can produce.
//
// **The tempting bug is not printing a random figure; it is printing the
// PRINCIPAL as the carried amount.** That renders `$150.00` where `$153.50` is
// held, looks completely correct, and keeps $3.50 of the customer's money —
// which is exactly what ❄️ WE-7 / GT-23 was frozen to prevent. So the tests
// below pin the absence, because that is the behaviour that can regress into
// something plausible.
import type { ReactElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, RouterProvider, Routes, createMemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

// The catalogues are loaded so every `t(key, {defaultValue})` resolves exactly
// as it does in the product — the assertions read rendered SENTENCES.
import i18n from "@/i18n";

import { APP_ROUTES } from "@/App";
import { createApiClient } from "@/api/client";
import type { AccountDetail } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import {
  BuyerStep,
  LeavingStep,
  SaleDateStep,
  TakeOnStep,
  TransferReviewStep,
  TransferWizard,
  buyerShortfall,
  emptyTransferDraft,
  transferPlanOf,
} from "./TransferWizard";
import { emptyFieldVisit } from "@/features/work/FieldVisitOrders";
import { TRANSFER_STEPS, TRANSFER_WIZARD_ROUTE } from "./transferDisconnectShared";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import { SEEDED_REGIONAL } from "@/components/tenantRegionalFixture";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params) as string;

/** The account as `GET /accounts/{id}` really serves it. **The principal is a
 *  4-dp stored string and the interest is not a field at all** — there is no
 *  key on this payload that could carry it, which is the shape BR-CUS-057's
 *  absence takes on the wire. */
function drawnAccount(over: Partial<AccountDetail> = {}): AccountDetail {
  return {
    id: "acc-10650",
    account_no: "A-10650",
    customer_no: "C-0091",
    name: "Iversen, Britt",
    unit_id: "unit-1",
    unit_label: "18 Marten Row",
    premise: "18 Marten Row",
    services: ["electric", "water"],
    balance: "0.0000",
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    // BR-CUS-510 / DEF-628 — the DEFAULT is `false`: this fixture's zero,
    // wherever it has one, is a real answer about money owed.
    balance_not_yet_billable: false,
    balance_cached: "0.0000",
    currency: "USD",
    status: "active",
    status_name: "Active",
    status_behavior_class: "billable",
    kind: "regular",
    account_type: "residential",
    account_subtype: null,
    autopay: false,
    opened_at: "2022-06-01",
    closed_at: null,
    last_bill_at: "2026-08-01",
    aging: null,
    deposit_on_file: "150.0000",
    deposit_received_on: "2022-06-01",
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
    // DEF-2419 — the plan the UNIT stands on. Null here: these fixtures are
    // about a flow, not about the plan cell, and null is a real state
    // (a unit with no plan) rather than a placeholder.
    unit_plan: null,
    customer: {
      id: "cus-1",
      kind: "person",
      display_name: "Iversen, Britt",
      external_ref: null,
      accounts: [
        { id: "acc-10650", account_no: "A-10650" },
        { id: "acc-11512", account_no: "A-11512" },
      ],
    },
    ...over,
  };
}

interface Render {
  html: string;
  urls: string[];
  methods: string[];
}

function renderWizard(step: number): Render {
  const urls: string[] = [];
  const methods: string[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input, init) => {
      urls.push(String(input));
      methods.push(String((init as RequestInit | undefined)?.method ?? "GET"));
      return new Response(JSON.stringify({ count: 0, results: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // DEF-SHL-3964 — this mounts the REAL shell, and the shell now renders no
  // routed screen until it knows the tenant's date format and time zone. A
  // test that mounts the product says which tenant it is testing.
  // DEF-SHL-4272 — the shell boots on `GET /shell/display` (every signed-in
  // role), not on the two Admin/Executive settings reads. Without this seed
  // the shell holds and every address renders a loading skeleton.
  queryClient.setQueryData(queryKeys.shellDisplay, shellBootSeed(SEEDED_REGIONAL));
  queryClient.setQueryData(queryKeys.regionalSettings, SEEDED_REGIONAL);
  const html = renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${TRANSFER_WIZARD_ROUTE}?step=${step}`]}>
          <Routes>
            <Route
              path={`/:tenant${TRANSFER_WIZARD_ROUTE}`}
              element={<TransferWizard client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { html, urls, methods };
}

/** ⊕ `DEF-CUS-6392` — step 2 now mounts the shared `FieldVisitOrders`, which
 *  builds its order links under the tenant's path and reads Work's options
 *  through react-query. A static render of the step needs both around it; no
 *  query runs in a static render, so nothing is fetched. */
function inStepFrame(node: ReactElement): ReactElement {
  return (
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/brazosbend/transfers/new"]}>
        <Routes>
          <Route path="/:tenant/*" element={node} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("TRF-02 · the transfer wizard (CR-030 W7, US-CUS-029)", () => {
  /**
   * ⚠ **HARD-WON LAW 2, ASSERTED THROUGH THE REAL ROUTE TABLE AND NOT THROUGH A
   * `MemoryRouter` THIS FILE BUILT.** Every other case here mounts the component
   * directly, which is exactly the shape law 2 warns about: a wizard that
   * renders perfectly in a test and that `App.tsx` routes to nothing. This case
   * takes `APP_ROUTES` itself, walks it to the wizard's own address, and looks
   * for the screen. Delete the route line and it goes red.
   */
  it("law 2 — the wizard is REACHED at its address by the application's own route table", () => {
    const router = createMemoryRouter(APP_ROUTES, {
      initialEntries: [`/${TEST_TENANT}${TRANSFER_WIZARD_ROUTE}`],
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    // DEF-SHL-3964 — this mounts the REAL shell, and the shell now renders no
    // routed screen until it knows the tenant's date format and time zone. A
    // test that mounts the product says which tenant it is testing.
    // DEF-SHL-4272 — the shell boots on `GET /shell/display` (every signed-in
    // role), not on the two Admin/Executive settings reads. Without this seed
    // the shell holds and every address renders a loading skeleton.
    queryClient.setQueryData(queryKeys.shellDisplay, shellBootSeed(SEEDED_REGIONAL));
    queryClient.setQueryData(queryKeys.regionalSettings, SEEDED_REGIONAL);
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(html).toContain('data-r10="TRF-02"');
  });

  it("BR-SHL-046 — FIVE steps, declared once, and they are `transfers.STEPS`' own five", () => {
    expect(TRANSFER_STEPS).toHaveLength(5);
    // ⚠ **THESE FIVE IDS CHANGED WITH THE JOB — `DEF-CUS-5075`.** They were
    // `leaving · finalReads · arriving · money · review`, the steps of the
    // move-out-plus-move-in the PO replaced on 2026-09-01. A sale finds the
    // account, names the BUYER, takes ONE date, states what is taken on, and
    // reviews.
    expect(TRANSFER_STEPS.map((s) => s.id)).toEqual([
      "account",
      "buyer",
      "saleDate",
      "takeOn",
      "review",
    ]);
  });

  it("step 1 draws BOTH fact panels the blueprint draws, row for row", () => {
    // ⚠ **`DEF-CUS-5180` — READ OFF THE PAGE IMAGE, NOT THE TEXT EXTRACT.** The
    // blueprint (p113) draws step 1 as two panels of facts beside the search:
    // sixteen rows headed *"The account — and all of it changes hands"* and
    // twelve headed *"What is changing hands with it"*. The screen drew one
    // panel of six, and a text extract of a wireframe cannot tell those apart —
    // it flattens the headings, the grouping and the two columns into a list of
    // labels. PO ruling 2026-09-13: *"When you use images to create screens
    // your accuracy is higher; hence dont create screens using only Text"*.
    const html = renderToStaticMarkup(
      <LeavingStep
        draft={{ ...emptyTransferDraft(), fromAccountId: "acc-10650" }}
        account={drawnAccount()}
        failed={false}
        onPatch={() => undefined}
        dateFormat="MM/DD/YYYY"
        categoryName="Residential"
        t={t}
      />,
    );
    // The drawn labels, in the drawn order, asserted as an ORDERED walk rather
    // than a set: row order is part of the design, and a set passes over a
    // panel whose rows have been shuffled.
    const drawnRows = [
      "Account number",
      "Customer number",
      "Seller",
      "Customer kind",
      "Category",
      "Status",
      "Opened",
      "Current balance",
      "Deposit on file",
      "Deposit interest",
      "Autopay",
      "Paperless billing",
      "Bill email",
      "Phone",
      "Preferred language",
      "Mailing address",
      // — and the second panel, in its own drawn order
      "Unit",
      "Unit type",
      "Floor",
      "Floor area",
      "Premises",
      "Service address",
      "Services",
      "Meters",
      "Plan",
      "Base charge",
      "Billing cycle",
      "Ledger",
    ];
    let cursor = -1;
    for (const label of drawnRows) {
      const at = html.indexOf(`<th scope="row">${label}</th>`, cursor + 1);
      expect(at, `${label} is missing or out of drawn order`).toBeGreaterThan(cursor);
      cursor = at;
    }
    expect(html).toContain("The account — and all of it changes hands");
    expect(html).toContain("What is changing hands with it");
    // ⛔ **`DEF-CUS-5182` IS FIXED (2026-09-23): NOTHING IS HARD-CODED "NOT
    // AVAILABLE YET" ANY MORE.** The three rows read the step-1 preview; this
    // render passes none, so they draw a dash (not asked) and never the old
    // sentence tracked to the defect.
    expect(html.split('data-tracks="DEF-CUS-5182"').length - 1).toBe(0);
    expect(html).not.toContain("Not available yet");
    // B14 rule 31 — no database id is ever the visible value of a field. The
    // fixture's ids would print here if a row reached for one.
    expect(html).not.toContain("acc-10650");
  });

  /**
   * **`DEF-CUS-5991` — A METERLESS UNIT IS LAWFUL AND ORDINARY, AND STEP 1 SAYS
   * SO INSTEAD OF FALLING OVER.**
   *
   * The `Meters` cell read `account.meters.length` with no guard, so a payload
   * that carries no array at all took the WHOLE step down mid-render —
   * `TypeError: Cannot read properties of undefined (reading 'length')` at
   * `ChangingHandsPanel`. It hid because vitest prints it as an UNHANDLED
   * ERROR at the very end of a run rather than as a failing assertion, and the
   * two cases it actually broke read as a missing account number.
   *
   * ⚠ **THE FIX IS A STATED ABSENCE, NOT A SILENT GUARD.** An empty list used
   * to render a bare dash, which says *this row has no answer* about a row
   * that has a perfectly good one. The move-out side settled this already —
   * `R4` of the move-out scenarios is *"a unit with NO METER AT ALL"* and the
   * move record renders `No meter on this unit` — so this reuses that
   * catalogue key rather than minting a twelfth way to say the same thing.
   */
  it("DEF-CUS-5991 — a meterless account states it, and a payload with no meters array renders", () => {
    const meterless = renderToStaticMarkup(
      <LeavingStep
        draft={{ ...emptyTransferDraft(), fromAccountId: "acc-10650" }}
        account={drawnAccount({ meters: [] })}
        failed={false}
        onPatch={() => undefined}
        dateFormat="MM/DD/YYYY"
        categoryName="Residential"
        t={t}
      />,
    );
    // The house sentence, out of the catalogue all eleven locales already carry.
    expect(meterless).toContain(t("customers.moveRecord.readsAbsent.unit_has_no_meters"));
    expect(t("customers.moveRecord.readsAbsent.unit_has_no_meters")).toBe("No meter on this unit");

    // …and the crash itself. `meters` is typed non-optional, which is exactly
    // why nothing caught this: `tsc` is satisfied and the wire is not.
    const noArray = drawnAccount();
    delete (noArray as { meters?: unknown }).meters;
    const rendered = renderToStaticMarkup(
      <LeavingStep
        draft={{ ...emptyTransferDraft(), fromAccountId: "acc-10650" }}
        account={noArray}
        failed={false}
        onPatch={() => undefined}
        dateFormat="MM/DD/YYYY"
        categoryName="Residential"
        t={t}
      />,
    );
    // Not merely "it did not throw" — the step is ON SCREEN, with the account
    // number the lookup resolved, which is the assertion the two red cases in
    // `accountLookup.dom.test.tsx` were already asking for.
    expect(rendered).toContain("A-10650");
    expect(rendered).toContain("What is changing hands with it");
    expect(rendered).toContain(t("customers.moveRecord.readsAbsent.unit_has_no_meters"));
  });

  /** Step 3 renders the SAME panel with `period` on, so it takes the same
   *  crash and the same sentence — one component, proved at both addresses. */
  it("DEF-CUS-5991 — step 3's copy of the panel survives it too", () => {
    const noArray = drawnAccount();
    delete (noArray as { meters?: unknown }).meters;
    const html = renderToStaticMarkup(
      <SaleDateStep
        draft={emptyTransferDraft()}
        account={noArray}
        onPatch={() => undefined}
        dateFormat="MM/DD/YYYY"
        t={t}
      />,
    );
    expect(html).toContain(t("customers.moveRecord.readsAbsent.unit_has_no_meters"));
    expect(html).toContain("What changes hands on that day");
  });

  it("step 1 draws the two panels that are STATEMENTS rather than lookups", () => {
    const html = renderToStaticMarkup(
      <LeavingStep
        draft={{ ...emptyTransferDraft(), fromAccountId: "acc-10650" }}
        account={drawnAccount()}
        failed={false}
        onPatch={() => undefined}
        dateFormat="MM/DD/YYYY"
        categoryName="Residential"
        t={t}
      />,
    );
    // `The same customer elsewhere` — and the second row is the one the panel
    // exists for: a seller with three accounts is selling exactly one.
    expect(html).toContain("The same customer elsewhere");
    expect(html).toContain("Affected by this sale");
    // `What this sale will not touch` — hard rule 4 on screen. An issued bill,
    // a payment taken and a journal line may never be updated or deleted, and
    // a sale does not re-address one.
    expect(html).toContain("What this sale will not touch");
    for (const label of [
      "Issued bills",
      "Payments taken",
      "Journal entries",
      "The account number",
      "The unit and meters",
      "Service agreements",
    ]) {
      expect(html).toContain(`<th scope="row">${label}</th>`);
    }
  });

  it("step 3 draws what the date APPLIES TO, read-only", () => {
    // `DEF-CUS-5180`. The blueprint (p115) draws twelve rows under the date
    // field and the sentence beneath them is why: *"Read-only, and that is the
    // point. None of this is chosen on a sale."* The step had the date and
    // nothing the date applies to.
    const html = renderToStaticMarkup(
      <SaleDateStep
        draft={emptyTransferDraft()}
        account={drawnAccount()}
        onPatch={() => undefined}
        t={t}
        dateFormat="MM/DD/YYYY"
      />,
    );
    expect(html).toContain("What changes hands on that day");
    // ⛔ *"Read-only, and that is the point…"* was RATIONALE and is removed
    // (`DEF-CUS-6385`, PO 2026-09-23 — B14 rule 33).
    expect(html).not.toContain("Read-only, and that is the point");
    // ⚠ **THE STEP-3 PANEL SWAPS TWO ROWS, AND THAT IS THE DRAWING'S OWN
    // DIFFERENCE** — it carries the billing period instead of the unit's floor,
    // because step 1 asks *what am I selling* and step 3 asks *what does this
    // date apply to*. Asserted in both directions so a future edit that
    // collapses the two panels into one goes red.
    expect(html).toContain('<th scope="row">Current period</th>');
    expect(html).toContain('<th scope="row">Next bill</th>');
    expect(html).not.toContain('<th scope="row">Floor area</th>');
  });

  it("the line under the title NAMES the step, on every one of the five", () => {
    // ⚠ **THIS CASE ASSERTED THE DEFECT AS CORRECT UNTIL `DEF-CUS-5179`.** It
    // required the FLOW's slogan — *"one account changes hands, all at once"* —
    // on all five screens, which is what the screen drew and is not what the
    // blueprint draws. Its page image (p113–p117) writes `Step 1 of 5 · Find
    // the account` under the 32px title of every screen, the second half being
    // the STEP's own name. A test named after a drawn line that pins the
    // undrawn one is hard-won law 7's *looking at the wrong thing*.
    //
    // ⚠ **THE ATOMICITY CLAIM IS NOT DROPPED, IT MOVED TO WHERE THE DRAWING
    // PUTS IT** — step 5's consequence list, asserted below by `data-will`.
    // ⚠ **THE NAMES COME OFF THE DECLARED LIST, NOT OUT OF THIS FILE.** Typing
    // them here would make the test agree with itself when a label is reworded
    // in only one of the two places — the shape of every stale assertion in
    // this repo. `&` is escaped because `renderToStaticMarkup` escapes it, and
    // `Review & confirm` is the one drawn label that carries one.
    const drawn = TRANSFER_STEPS.map((defn) => defn.en.replace(/&/g, "&amp;"));
    // Every step, not a sample: the fault this replaces was identical on all
    // five, so three of five would have passed over it just as happily.
    for (const step of [1, 2, 3, 4, 5]) {
      const { html } = renderWizard(step);
      expect(html).toContain(`Step ${step} of 5 · ${drawn[step - 1]}`);
      expect(html).not.toContain("both halves");
      // The slogan is gone from the head. Named here so a lane re-adding it
      // has to delete an assertion rather than simply not notice.
      expect(html).not.toContain("Step ${step} of 5 · one account changes hands");
    }
    // ⚠ **AND THE COUNT IS DERIVED, NOT TYPED** — the fault one flow over was a
    // wizard telling every clerk it had five steps over a six-step rail. A
    // sixth step must move this line without anybody editing it, so the
    // assertion reads the declared list rather than the literal 5 above.
    const { html } = renderWizard(1);
    expect(html).toContain(`Step 1 of ${TRANSFER_STEPS.length}`);
    // ⛔ **THE SECOND COUNT IS GONE WITH THE ROLLUP IT SAT IN — `DEF-CUS-6542`,
    // 2026-09-24.** This line used to assert `${TRANSFER_STEPS.length} steps ·`
    // from the page-head paragraph *"5 steps · the account changes hands,
    // nothing else moves."* **p127–p131 draw no such paragraph on any of the
    // five steps**, and its count was a THIRD statement of a fact the line
    // above and the rail already make — B14 rule 32. `DEF-CUS-6480` deleted the
    // identical sentence from the move-out on the PO's own instruction the same
    // morning (*"too much text reduce it"*).
    //
    // **The derived-count guarantee this line was protecting is NOT weakened**:
    // it is the assertion directly above, which still reads the declared list
    // and still moves on its own when a sixth step arrives.
    expect(html).not.toContain("steps · the account changes hands");
  });

  // ✅ BR-CUS-085 — the STAYS-WITH-YOU sentence. Written into the register
  // 2026-08-25 (DEF-711): B18 had cited this id for TWO statements and the
  // register held neither (083 → 086); the PO ruled 085 is the DEPOSIT rule
  // and the parked-wizard statement took `BR-CUS-108`.
  // **The assertion is unchanged, deliberately** — it asserts the drawn COPY,
  // and the copy did not move when the id was allocated. The rule binds the
  // PROHIBITION only (no refund raised, no re-collection possible); the deposit
  // POSITION moving is BR-CUS-024 (PROPOSED) / OQ-365 (OPEN) and is asserted
  // nowhere here.
  it("`DEF-CUS-6385` — the PO's rationale is REMOVED from step 1, not shortened", () => {
    // PO 2026-09-23, naming each: *"Stays with you" + its sentence*, *"Moving
    // house is not a sale. Raise a service request."*, *"Deposit interest is
    // not built yet"*. B14 rule 33: rationale is ZERO words on screen.
    const { html } = renderWizard(1);
    expect(html).not.toContain("Stays with you");
    expect(html).not.toContain("all stay put");
    expect(html).not.toContain("Moving house is not a sale");
    expect(html).not.toContain("Deposit interest is not built yet");
    expect(html).not.toContain("This customer is not leaving");
  });

  it("`Split into two` is GONE — there is nothing at a sale to split into", () => {
    const { html } = renderWizard(1);
    // ⛔ **REMOVED, NOT DISABLED — `DEF-CUS-5075`.** It was drawn on the frame
    // of the replaced job, where a transfer was a move-out plus a move-in and
    // splitting it back was at least a coherent thing to want. Under
    // `BR-CUS-1030` one account changes hands and nothing closes, so there is
    // nothing to split into; and a greyed control for an incoherent act is
    // hard-won law 2's mirror — a dead door teaching a clerk the product might
    // one day do something it never will. The drawn step 1 at p113 carries only
    // `Save & exit` in its header.
    expect(html).not.toContain("Split into two");
    expect(html).not.toContain("there is nothing to split it into");
    // The header's action slot is empty rather than holding a dead control.
    expect(html).toContain('<div class="page-header-actions"></div>');
  });

  it("nothing is written before the commit — steps 1 to 4 issue no write of any kind", () => {
    for (const step of [1, 2, 3, 4]) {
      const { methods } = renderWizard(step);
      expect(methods.filter((method) => method.toUpperCase() !== "GET")).toEqual([]);
    }
  });

  // ══════════════════════════════════════════════════════════════════════
  // THE MONEY CASES — every one of them asserts an ABSENCE
  // ══════════════════════════════════════════════════════════════════════

  it("❄️ WE-7 / GT-23 — the deposit interest is an ABSENCE and no total is invented", () => {
    // ⚠ **NOT ONE FIGURE HERE IS THE DRAWING'S** (B14 rule 37 — a drawn number
    // is an ILLUSTRATION, never a fact to build to). `41.25` and `17.00` are
    // this test's own, chosen so the two sums it forbids — `58.25` and the
    // interest-inclusive one — cannot collide with any figure the blueprint
    // prints or with the fixture's own default of zero.
    const html = renderToStaticMarkup(
      <TakeOnStep
        draft={emptyTransferDraft()}
        account={drawnAccount({ balance: "41.2500", deposit_on_file: "17.0000" })}
        onPatch={() => undefined}
        dateFormat="MM/DD/YYYY"
        t={t}
      />,
    );
    // The server's own figures, displayed at 2 dp by the shared cell: the
    // balance and the deposit, which is what the buyer takes on.
    expect(html).toContain("17.00");
    // ⛔ The drawn interest and the drawn "carried" total, neither of which is
    // servable. ❄️ `WE-7` freezes $3.50 and the blueprint draws $153.50.
    expect(html).not.toContain("153.50");
    expect(html).not.toContain("3.50");
    expect(html).toContain('data-tracks="BR-CUS-057"');
    // ⚠ **THE MONEY-CELL COUNT WENT TWO → THREE WITH THE DRAWN TOTAL ROW, AND
    // COUNTING IS NO LONGER THE CHECK** (`DEF-CUS-5180`). The blueprint's page
    // image (p116) rules a line under the three figures and sets `Taken on by
    // the buyer $318.40` in bold beneath it, which READS like a total — and a
    // total of the rows above would be the balance PLUS the deposit, which is
    // not what the buyer takes on and is not what any signed rule says. A count
    // cannot tell an invented total from a restated balance, so it is replaced
    // by the assertion that actually holds: the taken-on row carries the
    // BALANCE and nothing is summed.
    expect(html.split("cell-money-amount").length - 1).toBe(3);
    const takenOn = html.slice(html.indexOf("data-taken-on"));
    expect(takenOn).toContain("41.25");
    // ⛔ The sum a browser must never do here: balance + deposit. `BR-CUS-1030`
    // — the debt goes with the property and the deposit does not move, so the
    // buyer takes on the BALANCE and a total of the rows above it is a figure
    // no signed rule produces. ❄️ WE-7 / GT-23 is the frozen version of the
    // same mistake one field over.
    expect(html).not.toContain("58.25");
  });

  it("BR-CUS-057 — the interest row never renders a zero", () => {
    const html = renderToStaticMarkup(
      <TakeOnStep
        draft={emptyTransferDraft()}
        account={drawnAccount()}
        onPatch={() => undefined}
        dateFormat="MM/DD/YYYY"
        t={t}
      />,
    );
    expect(html).toContain('data-tracks="BR-CUS-057"');
    // ⚠ **SCOPED TO THE INTEREST ROW, AND THE UNSCOPED VERSION WAS WRONG.** My
    // first draft asserted `not.toContain("$0.00")` over the whole step and
    // failed — because the fixture account's BALANCE really is zero and the
    // server really did send `0.000000`. `DEF-127` is about a figure that could
    // NOT BE READ rendering as `$0.00`; a balance of zero IS zero, and hiding it
    // would be the opposite error. What must never be `$0.00` is the INTEREST.
    const interestCell =
      /data-tracks="BR-CUS-057"[\s\S]*?<\/span><\/span>/.exec(html)?.[0] ?? "";
    expect(interestCell).not.toContain("$0.00");
    expect(interestCell).toContain("—");
  });

  it("the two elections the PO removed are GONE from the screen", () => {
    // ⚠ `OQ-1252` was answered inside the hour on 2026-09-01 — *"money follow
    // property - new owner boutght everything property + debt also"* — so a box
    // letting a clerk say the deposit stays or the arrear does not follow is a
    // control that can reverse a PO ruling. `acknowledge_money` reads no key.
    const html = renderToStaticMarkup(
      <TakeOnStep
        draft={emptyTransferDraft()}
        account={drawnAccount()}
        onPatch={() => undefined}
        dateFormat="MM/DD/YYYY"
        t={t}
      />,
    );
    expect(html).not.toContain("No refund, no re-collection");
    expect(html).not.toContain("Moving across");
    expect(html).toContain("The debt goes with the property");
    // And the fee absence is stated, with the drawing's cause CORRECTED: the
    // catalogue does hold `TRANSFER — Account transfer fee`; what it has no row
    // for is the AMOUNT.
    expect(html).toContain('data-fee="none"');
  });

  it("DEF-127 — a null balance renders its reason and NEVER `$0.00`", () => {
    const html = renderToStaticMarkup(
      <LeavingStep
        draft={{ ...emptyTransferDraft(), fromAccountId: "acc-10650" }}
        account={drawnAccount({ balance: null, balance_currency: null })}
        failed={false}
        onPatch={() => undefined}
        dateFormat="MM/DD/YYYY"
        categoryName="Residential"
        t={t}
      />,
    );
    expect(html).toContain("The balance could not be read.");
    expect(html).not.toContain("$0.00");
    expect(html).toContain('data-tracks="DEF-127"');
  });

  // ══════════════════════════════════════════════════════════════════════
  // THE CLEARANCE CASES — the screen says what it did NOT check
  // ══════════════════════════════════════════════════════════════════════

  it("step 1 claims no clearance it did not compute — no `Standalone`, no CHECKED", () => {
    const html = renderToStaticMarkup(
      <LeavingStep
        draft={{ ...emptyTransferDraft(), fromAccountId: "acc-10650" }}
        account={drawnAccount()}
        failed={false}
        onPatch={() => undefined}
        dateFormat="MM/DD/YYYY"
        categoryName="Residential"
        t={t}
      />,
    );
    // The drawn FINDINGS, each of which would be a statement nobody computed.
    // ⚠ The word "Standalone" itself is not what is asserted against — the
    // refusal names it in order to say the screen is NOT claiming it, and a
    // test on the bare word would fail on the honest copy. What must be absent
    // is the CLAIM.
    expect(html).not.toContain("Nothing else is attached");
    expect(html).not.toContain("Nothing blocks this transfer");
    // ⚠ **THE TWO SENTENCES THIS CASE USED TO PIN ARE NOW THE DEFECT, AND
    // THAT IS A PO RULING RATHER THAN A RELAXATION (2026-09-20).** It asserted
    // *"nothing here has ruled it out, so treat it as unchecked"* and *"it is
    // not telling you they are clear"*. The Product Owner read both off the
    // live product and ruled them off: the first is an apology for what the
    // screen cannot look up, which B14 rule 33 puts at ZERO words on screen,
    // and the second ended *"check them yourself before you finish the
    // transfer"* — the product telling a clerk to go and do the product's job.
    // ⛔ `OQ-680` is UNCHANGED and still OPEN. What moved is where it is
    // stated: in the register and in this file's own docstring, not in front of
    // a clerk. A lane closing it looks for a refusal at the door.
    expect(html).not.toContain("treat it as unchecked");
    expect(html).not.toContain("it is not telling you they are clear");
    expect(html).not.toContain("check them yourself");
    expect(html).not.toContain('data-relationships="absent"');
    expect(html).not.toContain('data-blockers="unchecked"');
    expect(html).not.toContain('data-premise="absent"');
    // ⚠ **AND THE TWO THE PO KEPT BY NAME, so a later tidy-up cannot take them
    // with the rest** — both are facts a clerk needs rather than explanations.
    expect(html).toContain("What this sale will not touch");
    // ⚠ An absence is NOT an error — no red strip on a clean first render.
    expect(html).not.toContain("data-refusal");
  });

  it("step 4's `Who gets told this figure` is GONE — PO 2026-09-20, *\"why we are showing this\"*", () => {
    // ⚠ **THE PANEL WAS BUILT ON PURPOSE AND IS REMOVED ON PURPOSE.** Its own
    // comment argued that *"a row saying `Not decided` is not the same as a
    // missing row"* — that rendering the open question is what puts it in front
    // of somebody who can answer it. The Product Owner is that somebody, they
    // read it off the live product, and the answer was that a clerk selling a
    // house should not be shown an internal question at all (B14 rule 32: no
    // internal code in clerk-facing copy; rule 33: rationale is zero words on
    // screen). `OQ-1253` is unchanged and still OPEN.
    const html = renderToStaticMarkup(
      <TakeOnStep
        draft={emptyTransferDraft()}
        account={drawnAccount()}
        onPatch={() => undefined}
        dateFormat="MM/DD/YYYY"
        t={t}
      />,
    );
    expect(html).not.toContain("Who gets told this figure");
    expect(html).not.toContain("Not decided");
    expect(html).not.toContain('data-buyer-told');
    // The money and the tick are untouched — only the undecided question went.
    expect(html).toContain("Account balance");
    expect(html).toContain("trf_shown_to_buyer");
  });

  it("panel (c) IS real — BR-CUS-054's entity is served, so the sibling count is the server's", () => {
    const html = renderToStaticMarkup(
      <LeavingStep
        draft={{ ...emptyTransferDraft(), fromAccountId: "acc-10650" }}
        account={drawnAccount()}
        failed={false}
        onPatch={() => undefined}
        dateFormat="MM/DD/YYYY"
        categoryName="Residential"
        t={t}
      />,
    );
    // Two accounts on the customer, so ONE other than this one.
    expect(html).toContain('data-other-accounts="1"');
  });

  it("step 5 reviews the SALE, and says nothing about an account closing", () => {
    // ⚠ **EVERY ROW OF THIS REVIEW USED TO DESCRIBE THE REPLACED JOB.** It
    // asserted `Closed, once the final bill settles` and *"otherwise the
    // customer ends up with no account anywhere"* — so a clerk was told, by the
    // screen, that an account was about to close, and then refused by the
    // server for a buyer nobody had asked them for. Nothing closes at a sale.
    const html = renderToStaticMarkup(
      <TransferReviewStep
        draft={{
          ...emptyTransferDraft(),
          fromAccountId: "acc-10650",
          soldOn: "2026-05-09",
          buyer: { ...emptyTransferDraft().buyer, full_name: "Vasquez, M.", customer_kind: "person", phone: "(512) 555-0197" },
        }}
        account={drawnAccount()}
        t={t}
        dateFormat="MM/DD/YYYY"
      />,
    );
    expect(html).not.toContain("Closed, once the final bill settles");
    expect(html).not.toContain("no account anywhere");
    expect(html).toContain("Vasquez, M.");
    // The date in the tenant's own format, never ISO (`BR-SHL-023`).
    expect(html).toContain("05/09/2026");
    expect(html).toContain("The buyer becomes the customer");
    // ⚠ **WHICH identifier, NEVER THE VALUE** — `BR-CUS-1020` / `BR-CUS-1023`.
    // A government identifier does not belong on a page a clerk can screenshot.
    expect(html).toContain("Phone");
    expect(html).not.toContain("555-0197");
    // ⛔ **THE TWO "HAZARDS" ARE GONE BECAUSE THE PO RULED THEM AWAY
    // (2026-09-23).** T3: the seller's email, phone and autopay are REMOVED at
    // the sale (`DEF-CUS-6393`); T2: the owner moves for a master account and
    // stays for a regular one (`DEF-CUS-6394`). Each consequence line is now
    // what the commit does.
    expect(html).not.toContain("Autopay and the bill email stay the seller");
    expect(html).not.toContain("owner record still wants updating by hand");
    expect(html).not.toContain("All five writes land together");
    expect(html).toContain('data-will="seller-reach"');
    expect(html).toContain("Bills go to the service address.");
    // No preview says this is a master account, so the owner stays.
    expect(html).toContain('data-will="owner"');
    // ⛔ `DEF-CUS-5949` — *"Nobody is told about this sale"* was FALSE: the
    // commit queues the buyer's and the seller's letters. The review names
    // them, and says QUEUED, never sent.
    expect(html).not.toContain("Nobody is told about this sale");
    expect(html).toContain('data-message="transfer_to_buyer"');
    expect(html).toContain('data-message="transfer_to_seller"');
    expect(html).toContain("Queued on confirm");
    // No visit was asked for, so no meter-visit text is listed.
    expect(html).not.toContain('data-message="transfer_field_visit_sms"');
  });

  // ══════════════════════════════════════════════════════════════════════
  // THE PURE FUNCTIONS
  // ══════════════════════════════════════════════════════════════════════

  // ⛔ **`sameDayOf` AND `datesAreOrdered` HAD A CASE EACH AND BOTH ARE GONE.**
  // They answered questions about TWO dates — is the arrival the same day as
  // the departure, and is it at least not before it. **A sale has one date**, so
  // neither question exists. Deleting a passing test is normally wrong; here
  // the functions they tested implement the job `BR-CUS-1030` replaced, and
  // keeping them would keep the second account the ruling removed alive in the
  // one place nobody looks.

  it("the buyer's block is refused at STEP 2, the way the server refuses it", () => {
    // ⚠ **THIS IS THE CASE THE WHOLE DEFECT NEEDED.** `set_new_customer`
    // answers `422 customers.transfer.buyer_required` and the wizard offered no
    // buyer at all, so the only refusal a clerk could reach was at step 5,
    // naming a field no step had. `buyerShortfall` is `accountIdentityShortfall`
    // — the same function `NewAccountWizard` and `MoveInWizard` use — so the
    // three screens and the server cannot disagree about what an identifier is.
    const blank = emptyTransferDraft();
    // ⛔ **THIS LINE READ `toBe("customers.transfer.buyer.findFirst")` FROM
    // `2.351.0` UNTIL `DEF-CUS-6549`, AND THAT IS HOW THE DEFECT SHIPPED.** The
    // commit that made the search a precondition EDITED THIS ASSERTION to
    // match, so the one case that could have caught it was turned into its
    // witness. A blank draft is refused for the FIELD that is missing — never
    // told to go and search (PO ruling 2026-09-24, option (a)).
    expect(buyerShortfall(blank)).toBe("customers.transfer.buyer.nameRequired");
    // A LINKED customer is the buyer and needs nothing more.
    expect(
      buyerShortfall({
        ...blank,
        // ⊕ `DEF-CUS-10255` — a row of the search results table now.
        buyerCustomer: {
          id: "c-1",
          customer_no: "C-00041",
          display_name: "Hollis, Marcus",
          kind: "person",
          verdict: "found",
          agreed: [],
          accounts: null,
          company: null,
        } as unknown as ReturnType<typeof emptyTransferDraft>["buyerCustomer"],
      }),
    ).toBeNull();
    // Nothing typed and nothing searched: the ordinary opening state.
    const empty = blank;
    expect(buyerShortfall(empty)).not.toBeNull();
    const named = { ...empty, buyer: { ...empty.buyer, full_name: "Vasquez, M." } };
    // A name with no KIND still fails: an unstated kind mints no customer
    // number and would judge a business by a date of birth (`BR-CUS-1022`).
    expect(buyerShortfall(named)).not.toBeNull();
    const person = { ...named, buyer: { ...named.buyer, customer_kind: "person" } };
    // A person with a kind and no identifier still fails.
    expect(buyerShortfall(person)).not.toBeNull();
    const withPhone = { ...person, buyer: { ...person.buyer, phone: "(512) 555-0197" } };
    expect(buyerShortfall(withPhone)).toBeNull();
    // And a COMPANY is not identified by a phone — only by its Tax ID.
    const company = { ...withPhone, buyer: { ...withPhone.buyer, customer_kind: "company" } };
    expect(buyerShortfall(company)).not.toBeNull();
    const withTaxId = { ...company, buyer: { ...company.buyer, tax_id: "82-1234567" } };
    expect(buyerShortfall(withTaxId)).toBeNull();
  });

  it("the buyer refusal is a SALE's sentence and never `opening the account`", () => {
    // ⚠ **FOUND BY WALKING IT, NOT BY A TEST — AND NOW BY A TEST.** The rule is
    // correctly reused from `NewAccountWizard`; its four CATALOGUE SENTENCES
    // were inherited with it and all four name the wrong act: *"Give the
    // customer a name before opening the account"*, *"an account cannot be
    // opened without it"*. A sale opens nothing, and a clerk selling a property
    // was told in a red strip that an account could not be opened. Reusing a
    // rule and inheriting its copy looks identical to reusing both, to every
    // check that exists.
    const empty = emptyTransferDraft();
    const html = renderToStaticMarkup(
      inStepFrame(
        <BuyerStep
          draft={empty}
          account={drawnAccount()}
          onPatch={() => undefined}
          t={t}
        />,
      ),
    );
    expect(html).toContain('data-buyer-shortfall=""');
    expect(html).not.toContain("opening the account");
    expect(html).not.toContain("cannot be opened");
    expect(html).toContain("Name the buyer");
    // And the key is remapped rather than the rule re-implemented.
    expect(buyerShortfall(empty)).toBe("customers.transfer.buyer.nameRequired");
  });

  it("step 2 shows only the identifiers the stated kind is known by", () => {
    // A LINKED buyer re-types none — `transferPlanOf` sends them as
    // `customer_id` with `identity: {}`, so a box here would be discarded.
    const empty = emptyTransferDraft();
    const person = renderToStaticMarkup(
      inStepFrame(
        <BuyerStep
          draft={{ ...empty, buyer: { ...empty.buyer, customer_kind: "person" } }}
          account={drawnAccount()}
          onPatch={() => undefined}
          t={t}
        />,
      ),
    );
    // ⊕ `DEF-CUS-10255` — the buyer step is Move-in's shared form now (CF-1's
    // `CustomerWhoPanel` + `CustomerIdentityPanel`), so the boxes carry the
    // shared form's ids: `ssn`, `driving_licence`, `tax_id`.
    expect(person).toContain('id="ssn"');
    expect(person).toContain('id="driving_licence"');
    expect(person).not.toContain('id="tax_id"');
    const company = renderToStaticMarkup(
      inStepFrame(
        <BuyerStep
          draft={{ ...empty, buyer: { ...empty.buyer, customer_kind: "company" } }}
          account={drawnAccount()}
          onPatch={() => undefined}
          t={t}
        />,
      ),
    );
    expect(company).toContain('id="tax_id"');
    // ⚠ A company's Social Security number is filed where the company matcher
    // never looks (`BR-CUS-1022`), so it is not OFFERED — not offered and then
    // discarded.
    expect(company).not.toContain('id="ssn"');
  });

  it("step 3 asks for ONE date and states that nothing is prorated", () => {
    const html = renderToStaticMarkup(
      <SaleDateStep
        draft={emptyTransferDraft()}
        account={null}
        onPatch={() => undefined}
        t={t}
        dateFormat="MM/DD/YYYY"
      />,
    );
    expect(html).toContain('id="trf_sold_on"');
    // DEF-CUS-10265 — the product's date picker in the tenant's format (PO
    // 2026-10-18: *"any date field in artifact should be date picker"*),
    // never a native browser date box.
    expect(html).not.toMatch(/<input[^>]*type="date"[^>]*id="trf_sold_on"|<input[^>]*id="trf_sold_on"[^>]*type="date"/);
    expect(html).toContain('placeholder="MM/DD/YYYY"');
    // ⛔ The second date, and the unit picker, are GONE — a sale closes nothing
    // and opens nothing, and a customer moving address is a service request.
    expect(html).not.toContain('id="trf_in_date"');
    expect(html).not.toContain('id="trf_to_unit"');
    expect(html).toContain("Nothing is prorated at a sale");
    // The sentence a clerk has to say out loud, which the drawing puts in the
    // danger tier for a reason.
    expect(html).toContain("The buyer pays for days the seller used");
  });

  it("the commit payload is exactly the three keys `transfer_commit` reads", () => {
    // ⚠ **THIS CASE IS WHY `DEF-CUS-5075` COULD SIT FOR ELEVEN DAYS.** It
    // asserted the SIX keys the screen sent and passed every day — nothing in
    // this repository compared them against the four the door reads. The old
    // assertion was `["arrears_follow", "deposit_carry", "from_account_id",
    // "in_date", "out_date", "to_unit_id"]`, and posting exactly that answered
    // `422 customers.transfer.buyer_required`. A test can pin what a client
    // sends; only a running server can say whether anything reads it.
    const empty = emptyTransferDraft();
    const plan = transferPlanOf({
      ...empty,
      fromAccountId: " acc-10650 ",
      soldOn: "2026-05-09",
      buyer: {
        ...empty.buyer,
        full_name: " Vasquez, M. ",
        customer_kind: "person",
        phone: " (512) 555-0197 ",
        // ⚠ A company identifier on a PERSON is dropped rather than sent —
        // `BR-CUS-1022`. The server strips it anyway; putting a government
        // identifier on a wire for no purpose is still the wrong side of
        // `BR-CUS-1020`.
        tax_id: "82-1234567",
      },
      fieldVisit: emptyFieldVisit(),
    });
    // Three keys: `field_visit` is OMITTED when nothing was ticked, exactly as
    // `final_reads` is on the move wizards — a transfer where nobody has to
    // attend is the ordinary one, and a key that means nothing is a key the
    // endpoint has to decide about.
    // ⊕ `DEF-CUS-10255` — plus `buyer_account`, the buyer's own Preferences
    // panel (opened ticked, as the drawing draws it): the buyer's elections
    // replace the seller's at the sale. Nothing else rides with nothing typed.
    expect(Object.keys(plan).sort()).toEqual(["buyer_account", "customer", "from_account_id", "sold_on"]);
    expect(plan.buyer_account).toEqual({ paperless: false, sms_reminders: false, autopay: false });
    expect(plan.from_account_id).toBe("acc-10650");
    expect(plan.sold_on).toBe("2026-05-09");
    expect(plan.customer.display_name).toBe("Vasquez, M.");
    expect(plan.customer.kind).toBe("person");
    expect(plan.customer.identity).toEqual({ phone: "(512) 555-0197" });
    expect(plan.customer.identity.tax_id).toBeUndefined();
  });

  /** `DEF-CUS-6392` — item 12: the ONE shared field-visit table's rows ride
   *  the one plan as `orders`, the holder split into technician or crew, and
   *  *No visit needed* rides as `{none: true}`. */
  it("the field-visit table's rows ride the one plan", () => {
    const empty = emptyTransferDraft();
    const base = {
      ...empty,
      fromAccountId: "acc-10650",
      soldOn: "2026-05-09",
      buyer: { ...empty.buyer, full_name: "Vasquez, M.", customer_kind: "person", phone: "x" },
    };
    const plan = transferPlanOf({
      ...base,
      fieldVisit: {
        none: false,
        rows: [
          { key: "r1", type_id: "wt-meter-exchange", priority_id: "pr-normal", due_on: "2026-09-24", holder: "technician:tech-7", note: " Check meter at sale " },
        ],
      },
    });
    expect(plan.field_visit).toEqual({
      orders: [
        { type_id: "wt-meter-exchange", priority_id: "pr-normal", due_on: "2026-09-24", technician_id: "tech-7", note: "Check meter at sale" },
      ],
    });
    expect(transferPlanOf({ ...base, fieldVisit: { none: true, rows: [] } }).field_visit).toEqual({ none: true });
  });

  it("the replaced job's keys are not sent under any circumstances", () => {
    // The guard against a lane re-adding one of them: five keys the door
    // ignores, asserted absent by name.
    const empty = emptyTransferDraft();
    const plan = transferPlanOf({
      ...empty,
      fromAccountId: "acc-10650",
      soldOn: "2026-05-09",
      buyer: { ...empty.buyer, full_name: "V", customer_kind: "person", phone: "x" },
    }) as unknown as Record<string, unknown>;
    for (const dead of ["to_unit_id", "out_date", "in_date", "deposit_carry", "arrears_follow"]) {
      expect(plan[dead]).toBeUndefined();
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-029 §3 · B18 §5.7.7 · BR-CUS-030 · BR-CUS-054 · BR-CUS-057 ·
//         BR-CUS-023 · BR-CUS-086 · BR-SHL-025 · BR-SHL-046 · ❄️ WE-7 / GT-23 ·
//         DEF-127
// generated: 2026-08-25 by lane W7WIZ
// checklist: A=n/a B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: E3 the money cases assert a figure is ABSENT — the drawn $153.50
//         and $3.50 belong to a seeded fixture and the second cannot be
//         produced at all, and printing the principal in their place is ❄️
//         WE-7 / GT-23's frozen failure exactly.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
