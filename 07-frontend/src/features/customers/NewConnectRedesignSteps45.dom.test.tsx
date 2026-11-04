// ── Trace ──────────────────────────────────────────────
// Change:  `CR-150-BRC09` tasks 11–14 — the rendered proof for **step 4 ·
//          Charges** and **step 5 · Review**, built from
//          `05-prototype/new-connect-redesign-2026-09-28/step4-charges.png`
//          and `step5-review.png`.
// Defects: `DEF-CUS-7610` (the payer options were disabled by a hardcoded
//          literal) · `DEF-CUS-7611` (no payment fields at all) ·
//          `DEF-CUS-7613` (the review is not grouped) · `DEF-CUS-7704` (the
//          two deliberately-unbuilt drawn items) · `DEF-088` / `DEF-127`
//          (money arithmetic in a browser)
// Questions: ⛔ `OQ-CUS-12770` — **OPEN**. The drawn editable Qty is NOT built
//          and one case below asserts that it is not, so the day somebody
//          builds it before the question is ruled, the suite goes red and
//          names it.
// Rules:   CLAUDE.md hard rule 2 (no money is multiplied, summed or rounded in
//          a browser) · B14 rules 31, 33, 43 · hard-won law 2 (built is not
//          wired, and its mirror) · law 6 (no gate reads rendered output) ·
//          law 7 (know what would make this pass wrongly)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS FILE CAN AND CANNOT SEE — READ IT BEFORE TRUSTING IT GREEN
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS HARNESS DOES NO LAYOUT. EVERY ELEMENT IS ZERO BY ZERO.** It cannot
// see a strip that wraps, a column out of alignment or a footer off the page.
// The rendered proof is a browser and there is no substitute (hard-won law 6).
//
// ⚠ **WHAT WOULD MAKE EACH CASE PASS WRONGLY** (law 7, habit 2), named per
// case below rather than left to be worked out. The two that matter most:
//
//   * **THE MONEY CASE.** Asserting that `$1,035.00` is on the screen would
//     pass just as happily over a browser-side multiply — it is the same
//     string either way. So the money case asserts the **MECHANISM**: it
//     renders a build whose lines the SERVER has not priced and proves the
//     screen prints a stated absence rather than a figure. A screen that
//     multiplied `qty x each` would have a number there, and this goes red.
//     It is the only assertion in this file that can tell those two apart.
//
//   * **THE FOLD CASE.** Counting six columns in the messages table would
//     pass over a fold that lost the contact card and the template picker
//     entirely. So it asserts each absorbed FIELD by its own DOM handle —
//     `data-telling-field`, `data-template-picker` — which is the audit in
//     §0 of `NewConnectCommunicationStep.tsx` made mechanical.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18next from "i18next";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { ChargesStep } from "./NewConnectChargesStep";
import { NewConnectWizard } from "./NewConnectWizard";
import { MESSAGES } from "./NewConnectCommunicationStep";
import { newConnectPlansQueryKey } from "./NewConnectPremiseStep";
import { ReviewStep, stepNumberOf } from "./NewConnectReviewStep";
import { commitPlanOf, emptyDraft } from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";
import { newConnectQuotePreviewQueryKey } from "./NewConnectChargesStep";
import { manifestPreview, NEW_CONNECT_STEPS } from "./newConnectShared";
import { quoteLinesOf } from "./newConnectDraft";

const TEST_TENANT = "brazosbend";
const t = (key: string, options?: unknown) => String(i18next.t(key, options as never));

/** A three-unit build on two services, priced by nothing — which is the state
 *  the money case needs and the ordinary state of a wizard mid-flight. */
function buildDraft(over: Partial<NewConnectDraft> = {}): NewConnectDraft {
  return {
    ...emptyDraft(),
    owner: { ...emptyDraft().owner, name: "Jonas Janssen", email: "j@example.test" },
    premise: { ...emptyDraft().premise, address: "New Highland Park", name: "New Highland Park" },
    pattern: { prefix: "Unit", from: "1", to: "3", includeCommonArea: false },
    premiseServices: ["electric", "water"],
    apartmentServices: ["electric", "water"],
    planApartments: "plan-1",
    quoteLines: [{ chargeCode: "CONN", basis: "per unit" }],
    quoteDueDays: "30",
    ...over,
  };
}

function client() {
  return createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      new Response(JSON.stringify({ count: 0, results: [], methods: [], rows: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  });
}

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/…` PATTERN** (hard-won law 2): a bare
 * `MemoryRouter` with no matching route leaves `useParams().tenant` undefined
 * and every address a screen builds comes out protocol-relative — a string
 * that reads as perfectly good to `toContain`. It also means `useSearchParams`
 * behaves, which the `Edit ›` links depend on.
 */
function mount(node: React.ReactNode, prepare?: (q: QueryClient) => void): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  prepare?.(queryClient);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new?step=4`]}>
          <Routes>
            <Route path="/:tenant/connections/new" element={node} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function charges(draft = buildDraft(), prepare?: (q: QueryClient) => void): string {
  return mount(
    <ChargesStep
      draft={draft}
      onPatch={() => undefined}
      t={t}
      dateFormat="MM/DD/YYYY"
      client={client()}
    />,
    prepare,
  );
}

function review(
  draft = buildDraft(),
  over: { quoteTotal?: string | null; quoteCurrency?: string | null } = {},
): string {
  const manifest = manifestPreview({
    units: [
      { label: "Unit 1", isCommonArea: false },
      { label: "Unit 2", isCommonArea: false },
      { label: "Unit 15", isCommonArea: false },
    ],
    unitServices: {
      "Unit 1": ["electric", "water"],
      "Unit 2": ["electric", "water"],
      "Unit 15": ["electric", "water"],
    },
    unitsWithAPlan: 3,
    ownerBecomesACustomer: true,
    quoteDisplay: over.quoteTotal ?? null,
  });
  return mount(
    <ReviewStep
      draft={draft}
      manifest={manifest}
      quoteTotal={over.quoteTotal ?? null}
      quoteCurrency={over.quoteCurrency ?? null}
      workOrderCount={2}
      onPatch={() => undefined}
      t={t}
      client={client()}
    />,
  );
}

// ══════════════════════════════════════════════════════════════════════════
// TASK 11 · CHARGES
// ══════════════════════════════════════════════════════════════════════════

describe("CR-150-BRC09 task 11 — step 4 · Charges, from step4-charges.png", () => {
  it("draws the context strip, with a cell for each of the seven drawn facts", () => {
    const html = charges();
    // ⚠ FALSE PASS TO WATCH FOR: asserting the seven WORDS would pass over a
    // strip that drew seven headings and no values. Each cell is asserted by
    // its VALUE handle, which only exists where a value was rendered.
    for (const cell of ["customer", "premise", "scope", "units", "services", "counted", "plan"]) {
      expect(html).toContain(`data-context-value="${cell}"`);
    }
    expect(html).toContain("Jonas Janssen");
    expect(html).toContain("New Highland Park");
  });

  it("asks who is billed with ONE select and keeps all three options", () => {
    const html = charges();
    // `DEF-CUS-7610`, PO: *"this is wring - keep previous options"*.
    expect(html).toContain('id="nc_quote_payer"');
    expect(html).toContain('<select');
    // The two the server refuses are present AND unselectable — present beats
    // absent (a clerk would never learn they exist) and beats selectable
    // (they would only learn on submit).
    expect(html).toContain('value="each_unit_first_bill" disabled=""');
    expect(html).toContain('value="connection" disabled=""');
    expect(html).toContain('value="owner_account"');
    // And the one the product CAN honour is not disabled.
    expect(html).not.toContain('value="owner_account" disabled=""');
  });

  // ⊕ **LANE CF-1 (2026-10-18) — MOVE-IN'S TAX AND PREFERENCES PANELS**
  // (drawing set `customer-forms-2026-10-18`, image 02: *"Charges step uses
  // Move-in's Tax … and Preferences"*). The old four-box panel drew both tax
  // boxes disabled until ticked; Move-in's Tax panel is a TICK PANEL whose
  // boxes appear once ticked, so this case now asserts that shape and the
  // Preferences panel with Autopay.
  it("draws Move-in's Tax panel (boxes once ticked) and Preferences with Autopay", () => {
    // ⊕ lane CF-1 (`DEF-CUS-10233`) — Move-in's own TaxSection now, ids and
    // all: exemption type, certificate number, issued, expiry, certificate.
    const off = charges();
    expect(off).toContain('id="move_in_tax_on"');
    expect(off).not.toContain('id="move_in_tax_ref"');
    expect(off).toContain('id="move_in_discounts_on"');
    expect(off).toContain('id="nc_prefs_on"');
    expect(off).toContain('data-billing-section="preferences"');
    const on = charges(
      buildDraft({
        moveInExtras: {
          discountsOn: false,
          discounts: [],
          taxOn: true,
          tax: { categoryId: "", certificateRef: "", issuedOn: "", expiresOn: "", file: null },
        },
        prefsOn: true,
      }),
    );
    for (const id of ["move_in_tax_category", "move_in_tax_ref", "move_in_tax_issued", "move_in_tax_expires", "move_in_tax_certificate"]) {
      expect(on).toContain(`id="${id}"`);
    }
    expect(on).toContain('id="autopay"');
  });

  it("offers ONE payment option and names the reference after the tender", () => {
    // `DEF-CUS-7611`, PO: *"based on payment type we nedd to give all paymnet
    // fields"*. The drawing merges *Take payment* and *Method* into one.
    const html = charges();
    expect(html).toContain('id="nc_payment_option"');
    expect(html).not.toContain('id="nc_take_payment"');
    expect(html).toContain('id="nc_payment_amount"');
    expect(html).toContain('id="nc_payment_date"');
    expect(html).toContain('id="nc_payment_reference"');
    // DEF-CUS-10324 (CR-186-BRC10): posted at entry, cleared only at bank
    // reconciliation — the step asks no clearing date.
    expect(html).not.toContain('id="nc_payment_cleared_date"');
  });

  it("says CHECK and never CHEQUE — PO ruling 2026-09-29, American English", () => {
    const paying = charges(
      buildDraft({ takePayment: "deposit", paymentMethod: "check", paymentAmount: "500" }),
    );
    expect(paying).toContain("Check number");
    // ⚠ The whole screen, not just the label: the drawing says *Cheque* in two
    // places and a ruling beats a drawing.
    expect(paying.toLowerCase()).not.toContain("cheque");
  });

  it("⛔ does NOT build the drawn editable Qty — OQ-CUS-12770 is OPEN", () => {
    // The question *is a charge's quantity typed per charge or counted?* is
    // unruled, it is money on a real invoice, and the prime directive forbids
    // answering it by choosing. `CR-150-BRC09` §5: *"NOTHING IS BUILT HERE
    // UNTIL `OQ-CUS-12770` IS RULED."*
    //
    // ⚠ **THIS IS A HOLD WITH A CLOCK IN IT, SO IT HAS THE TEST THAT FIRES
    // WHEN THE HOLD EXPIRES** (hard-won law 2's mirror): the day somebody
    // builds the box before the ruling lands, this goes red and names the
    // question. When the PO rules (b) or (c), this case is what gets deleted,
    // deliberately and visibly.
    const html = charges();
    expect(html).toContain('data-cell="qty"');
    expect(html).not.toMatch(/data-cell="qty"[^>]*<input/);
    expect(html).not.toContain('data-cell="qty-0"');
  });

  it("draws Total, Paid now and Remaining — and Remaining carries NO figure", () => {
    // ⚠⚠ **HARD RULE 2.** `Remaining` is `Total − Paid now`, which is money
    // arithmetic in a browser. The row is drawn and the FIGURE is stated
    // absent (`DEF-CUS-7704`).
    const html = charges(
      buildDraft({ takePayment: "deposit", paymentMethod: "check", paymentAmount: "500.00" }),
    );
    expect(html).toContain('data-charge-total=""');
    expect(html).toContain('data-charge-paid=""');
    expect(html).toContain('data-charge-remaining=""');
    expect(html).toContain('data-charge-remaining-absent=""');
  });

  it("⚠ prints NO money figure the server did not serve — the arithmetic guard", () => {
    // ⚠⚠ **THE CASE THAT WOULD NOT PASS IF THE BROWSER MULTIPLIED.** This
    // build has a charge line and a payment amount and the quote preview has
    // answered NOTHING. A screen doing `qty × each` or `total − paid` would
    // have a currency figure on it; a screen that only prints what the server
    // served has none, and says so.
    //
    // ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** asserting on the ABSENCE
    // strings alone would pass over a screen that printed both the absence
    // AND a computed figure. So it also asserts that no `$` figure other than
    // the clerk's own typed `500.00` is anywhere in the markup.
    const html = charges(
      buildDraft({ takePayment: "deposit", paymentMethod: "check", paymentAmount: "500.00" }),
    );
    expect(html).toContain('data-charge-total-absent=""');
    expect(html).toContain('data-charge-remaining-absent=""');
    // 1 × 3 = 3 lines at any price would produce a product. There is no
    // price, so there is no product, and no `$` anywhere.
    expect(html).not.toContain("$");
  });

  it("sends nothing it did not collect — the commit payload is the screen's", () => {
    // Hard-won law 2: an engine nothing passes anything to is not a feature,
    // and the billing preferences would have been four dead boxes.
    const plan = commitPlanOf(
      buildDraft({
        billing: {
          autopay: true,
          taxExempt: true,
          taxExemptRef: "EX-99",
          taxExemptExpires: "2027-01-31",
        },
      }),
      null,
      [],
      null,
    );
    expect(plan.owner).toMatchObject({
      autopay: true,
      tax_exempt: true,
      tax_exempt_ref: "EX-99",
      tax_exempt_expires: "2027-01-31",
    });
    // And the quantity still travels COUNTED, which is what `OQ-CUS-12770`
    // leaves standing.
    expect(quoteLinesOf(buildDraft())[0]).toMatchObject({ charge_code: "CONN", quantity: 3 });
  });
});

// ══════════════════════════════════════════════════════════════════════════
// TASK 12 · REVIEW
// ══════════════════════════════════════════════════════════════════════════

describe("CR-164-BRC10 — step 4's order and terms (items 19, 20)", () => {
  it("draws What is charged ABOVE Who is billed and Payment", () => {
    const html = charges();
    const charged = html.indexOf('data-array="quote-lines"');
    const billed = html.indexOf('id="nc_quote_payer"');
    expect(charged).toBeGreaterThan(-1);
    expect(billed).toBeGreaterThan(-1);
    expect(charged).toBeLessThan(billed);
  });

  it("offers payment terms as 7, 15, 30, 60 and 90 days", () => {
    const html = charges();
    const from = html.indexOf('id="nc_quote_due_days"');
    expect(html.slice(html.lastIndexOf("<", from), from)).toContain("<select");
    for (const days of ["7", "15", "30", "60", "90"]) {
      expect(html).toContain(`<option value="${days}"`);
    }
  });

  it("offers no master account as payer on a build that opens none (DEF-CUS-9212)", () => {
    const base = buildDraft();
    const html = charges({ ...base, premise: { ...base.premise, accountKind: "regular" } });
    expect(html).toMatch(/<option value="owner_account" disabled/);
    const master = charges({ ...base, premise: { ...base.premise, accountKind: "master" } });
    expect(master).not.toMatch(/<option value="owner_account" disabled/);
  });

  it("says Master account, never the owner's account", () => {
    expect(charges()).not.toMatch(/owner&#x27;s account|owner's account/i);
    expect(review()).not.toMatch(/owner&#x27;s account|owner's account/i);
  });
});

describe("CR-150-BRC09 task 12 — step 5 · Review, from step5-review.png", () => {
  it("draws the At a glance strip with all nine cells", () => {
    const html = review();
    for (const cell of [
      "customers",
      "premises",
      "units",
      "service-points",
      "meters",
      "sub-meter-links",
      "plan-assignments",
      "work-orders",
      "one-time-charges",
    ]) {
      expect(html).toContain(`data-glance-value="${cell}"`);
    }
    // ⚠ **THE COUNT COMES FROM THE DRAFT, NOT FROM THE MANIFEST FIXTURE, AND
    // THE FIRST RUN OF THIS FILE PROVED IT** — it asserted the drawing's
    // twelve and got six, because `buildDraft()` is three units on two
    // services. **Six is the right answer and twelve was the drawing's
    // illustration** (B14 rule 37), which is the exact mistake rule 37 exists
    // to stop: an expectation taken off the PNG rather than off the build.
    // It is the SAME derivation the commit writes `connection_services` from
    // (`draftUnitServices`), which is why it cannot drift from what is made.
    expect(html).toContain(">6<");
  });

  it("draws four collapsible groups, each with an Edit at the RIGHT step", () => {
    const html = review();
    for (const group of ["customer", "premise", "units", "charges"]) {
      expect(html).toContain(`data-review-group="${group}"`);
      expect(html).toContain(`data-group-edit="${group}"`);
    }
    // ⚠⚠ **THE NUMBERS ARE LOOKED UP, NOT TYPED — AND THIS ASSERTS THE LOOKUP
    // RATHER THAN THE NUMBER.** Comparing against a literal `4` would be the
    // same hardcoding one layer out, and it would go stale the next time the
    // steps move. It compares against `NEW_CONNECT_STEPS`, which is the one
    // list the rail, the step line and `?step=` all read.
    for (const id of ["customer", "premise", "units", "charges"]) {
      const step = stepNumberOf(id);
      expect(step).not.toBeNull();
      expect(html).toContain(`data-edits-step="${String(step)}"`);
    }
    // ⚠ **AND `stepNumberOf` IS ITSELF PROVED AGAINST THE LIST**, so this
    // case cannot pass by agreeing with a helper that is wrong: every answer
    // it gives is the position of a step that really is in
    // `NEW_CONNECT_STEPS`, under its current id or the one alias the rename
    // is mid-flight on.
    for (const id of ["premise", "units", "charges"]) {
      const at = NEW_CONNECT_STEPS.findIndex((step) => step.id === id);
      expect(stepNumberOf(id)).toBe(at + 1);
    }
    // An id nothing answers for draws NO link, rather than a `?step=0` the
    // wizard clamps back to 1 — a link that silently goes somewhere else.
    expect(stepNumberOf("nothing-by-this-name")).toBeNull();
  });

  it("repeats the charge lines inside the charges group, read-only", () => {
    const html = review();
    expect(html).toContain('data-array="review-charges"');
    // Read-only: no remove control and no add button on this copy.
    expect(html).not.toContain('data-array-action="add-charge"');
  });

  it("prints One-time charges through MoneyCell and never as a bare number", () => {
    // The PO reported `1035.00` where every other money cell shows
    // `$1,035.00`. `MoneyCell` is the one formatting path (`BR-SHL-023`).
    const html = review(buildDraft(), { quoteTotal: "1035.0000", quoteCurrency: "USD" });
    expect(html).toContain("$1,035.00");
    expect(html).not.toContain(">1035.00<");
  });

  it("shows an em dash and never a zero where the commit writes nothing", () => {
    const html = review();
    // `sub_meter_links` is `None` from the commit with its own stated reason;
    // a zero would read as *we made none* where the truth is *we cannot make
    // them from here*.
    expect(html).toMatch(/data-glance-value="sub-meter-links"[\s\S]{0,120}data-absent/);
    // ⊕ `CR-164-BRC10` / `DEF-CUS-9197` — work orders are COUNTED now: the
    // commit raises one per surviving proposal, and the host hands that
    // figure in (`workOrderCount`, 2 in this fixture).
    expect(html).toMatch(/data-glance-value="work-orders"[\s\S]{0,60}>2</);
  });

  it("shows meters and behind-the-meter devices as two cells", () => {
    // `CR-164-BRC10` items 21, 29.
    const html = review();
    expect(html).toContain('data-glance-value="meters"');
    expect(html).toContain('data-glance-value="behind-the-meter"');
  });
});

// ══════════════════════════════════════════════════════════════════════════
// TASK 13 · THE COMMUNICATION FOLD — NOTHING LOST
// ══════════════════════════════════════════════════════════════════════════

describe("CR-150-BRC09 task 13 — Communication absorbed into Review", () => {
  it("renders the messages table with all three of the PO's occasions", () => {
    const html = review();
    expect(html).toContain('data-array="messages"');
    for (const message of MESSAGES) {
      expect(html).toContain(`data-cell="message-${message.code}"`);
    }
  });

  it("keeps every field the Communication step held — the absorbed-field audit", () => {
    // ⚠⚠ **THIS IS §0 OF `NewConnectCommunicationStep.tsx` MADE MECHANICAL.**
    // With the `communication` step id gone there is no other screen left that
    // holds any of this, so a field missed here is a field the product no
    // longer has. PO: *"we dont want any information to be reduced or lost"*.
    //
    // ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** counting the table's columns.
    // It asserts each absorbed field by its OWN DOM handle instead.
    const html = review();
    // Panel 1 — *Who we are telling*, four rows.
    for (const field of ["contact", "email", "phone", "language"]) {
      expect(html).toContain(`data-telling-field="${field}"`);
    }
    // Panel 2 — six columns, per row, by their own handles.
    expect(html).toContain('data-cell="message-to"');
    expect(html).toContain('data-cell="channel-build_created"');
    expect(html).toContain('data-cell="template-build_created"');
    expect(html).toContain('data-cell="message-when"');
    // ⊕ `CR-164-BRC10` (PO Q8) — every STATE cell says what will happen to
    // that message, from what is known before Create.
    for (const message of MESSAGES) {
      expect(html).toMatch(
        new RegExp(`data-cell="state-${message.code}"[\\s\\S]{0,80}data-message-state=`),
      );
    }
    // Panel 3 — the picker, behind its own button.
    expect(html).toContain('data-array-action="add-template"');
  });

  it("a removed message leaves the table, is said out loud, and TRAVELS", () => {
    // ⚠ **THIS IS THE REVERSAL OF THE 2026-09-28 DISABLED TICKS, ASSERTED.**
    // The comment defending them said *"nothing the clerk chose here could
    // travel"*; `queue_on_commit` has taken `{send, templates}` all along and
    // the wire was the missing half.
    const html = review(buildDraft({ messagesOff: ["contract"] }));
    // ⊕ `CR-164-BRC10` items 23/46 — it comes back through the table's own
    // `+ Add message`, which is live while anything is off.
    expect(html).toContain('data-array-action="add-message"');
    expect(html).not.toContain('data-cell="message-contract"');
    const plan = commitPlanOf(buildDraft({ messagesOff: ["contract"] }), null, [], null);
    expect(plan.messages).toEqual({ send: { contract: false } });
    // And an untouched build sends no `send` block at all: an absent code
    // means the occasion's own default, which is the PO's ruling.
    expect(commitPlanOf(buildDraft(), null, [], null).messages).toEqual({});
  });
});

// ══════════════════════════════════════════════════════════════════════════
// TASK 14 · WHAT PRESSING CREATE MAKES — IT MUST BE TRUE
// ══════════════════════════════════════════════════════════════════════════

describe("CR-150-BRC09 task 14 — the create table names what the commit writes", () => {
  it("names every record the commit really makes", () => {
    const html = review();
    for (const row of [
      "customer",
      "ownerAccount",
      "premises",
      "units",
      "servicePoints",
      "meters",
      "subMeterLinks",
      "planAssignments",
      "workOrders",
      "booksEntry",
      "payment",
      "messages",
      "audit",
      // ⊕ `CR-164-BRC10` — the two the PO asked for, and the request itself.
      "behindTheMeter",
      "request",
    ]) {
      expect(html).toContain(`data-creates="${row}"`);
    }
  });

  it("⚠ does NOT repeat the drawing's four false claims", () => {
    // Each of these was checked line by line against
    // `apps/metering/connections.py::commit_connection`; §2 of the Review
    // step records the reasoning. A row promising something the commit does
    // not do is worse than no table (`DEF-MET-5428`).
    const html = review();
    // ⊕ AMENDED `CR-164-BRC10` (items 27, 47, 31): the premises IS made by
    // Create when it is new (`_premises_made_for_the_wizard`, `DEF-2961`'s
    // count) and is Pending until approval; a meter row is made in Inventory
    // and Installed by its work order; the messages go on approval.
    expect(html).toMatch(/data-creates="premises"[\s\S]{0,600}Pending → Active on approval/);
    expect(html).toMatch(/data-creates="meters"[\s\S]{0,600}Inventory → Installed/);
    expect(html).toMatch(/data-creates="messages"[\s\S]{0,600}On approval/);
    expect(html).not.toContain("Already created");
    // 4 · the drawing's red note said the books entry and the payment do not
    //     happen. They do, since `BR-MET-1187`, inside the commit's own
    //     transaction — so the note is DELETED, not reworded (law 1).
    expect(html).not.toContain("do not happen today");
    expect(html).not.toContain("no invoice is written");
  });

  it("counts rows and never invents a number the manifest does not carry", () => {
    const html = review();
    // The audit row count is at least two and the manifest carries none, so
    // no number is printed rather than the drawing's `1`.
    expect(html).toMatch(/data-creates-count="audit"[\s\S]{0,120}data-absent/);
    // ⊕ `DEF-CUS-9197` — work orders are the count the commit raises.
    expect(html).toMatch(/data-creates-count="workOrders"[\s\S]{0,80}>2</);
  });

  it("puts the books entry and the payment through MoneyCell, server figures only", () => {
    const html = review(
      buildDraft({ takePayment: "deposit", paymentMethod: "check", paymentAmount: "500.00" }),
      { quoteTotal: "1035.0000", quoteCurrency: "USD" },
    );
    expect(html).toContain("$1,035.00");
    expect(html).toContain("$500.00");
    // ⚠ **AND NO THIRD FIGURE.** `1035 − 500 = 535` is the subtraction hard
    // rule 2 forbids; it appears nowhere on this screen.
    expect(html).not.toContain("535");
  });
});

// A reference so the quote-preview key stays imported and any rename of it is
// a compile error here rather than a silent cache miss on the charges step.
describe("the charges step and its preview share one cache key", () => {
  it("keys the preview on the LINES", () => {
    const lines = quoteLinesOf(buildDraft());
    expect(newConnectQuotePreviewQueryKey(lines)).toEqual([
      "new-connect",
      "quote-preview",
      lines,
    ]);
    expect(newConnectPlansQueryKey).toEqual(["new-connect", "plans"]);
  });
});

describe("DEF-CUS-7910 \u00b7 the absorbed panels appear ONCE on the assembled wizard", () => {
  /**
   * \u26a0\u26a0 **THIS MOUNTS THE WHOLE WIZARD, NOT THE REVIEW STEP, AND THAT IS
   * THE ENTIRE POINT.** Every other case in this file renders `ReviewStep` on
   * its own, where a second copy mounted by the wizard AROUND it is invisible
   * by construction. The defect lived in `NewConnectWizard.tsx`: an absorb
   * bridge rendered the old Communication panel beneath the review "until the
   * REVIEW lane draws it there", the Review lane drew it there in `2.401.0`,
   * and nobody removed the bridge \u2014 so the live screen carried *Who we are
   * telling* and *Messages* twice, including two copies of every template
   * `<select>` and therefore the same `id` twice in one document.
   *
   * \u26a0 **IT COUNTS. IT DOES NOT ASSERT PRESENCE.** `toContain` is satisfied
   * by the first copy and says nothing about the second, which is why 22
   * green cases, `tsc`, eslint and a browser walk all passed over this. The
   * walk's `page.$(sel)` has the identical blind spot. What found it was a
   * FULL-HEIGHT screenshot \u2014 hard-won law 6 \u2014 after it turned out
   * `fullPage: true` had been silently cropping a 3,326px screen to 1,400px
   * because this app scrolls an inner container.
   *
   * \u26a0 **PROVED RED FIRST** (hard-won law 7): with the bridge still in
   * `NewConnectWizard.tsx` this case reports `data-telling` 2 \u2192 expected 1.
   */
  function wizardAt(step: number): string {
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(JSON.stringify({ count: 0, results: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new?step=${step}`]}>
            <Routes>
              <Route
                path="/:tenant/connections/new"
                element={<NewConnectWizard client={client} />}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  const countOf = (html: string, needle: string) => html.split(needle).length - 1;

  it("renders `Who we are telling` exactly once on step 5", () => {
    expect(countOf(wizardAt(5), 'data-telling=""')).toBe(1);
  });

  it("renders the Messages table exactly once on step 5", () => {
    expect(countOf(wizardAt(5), 'data-array="messages"')).toBe(1);
  });

  it("offers `+ Add template` exactly once on step 5", () => {
    expect(countOf(wizardAt(5), 'data-array-action="add-template"')).toBe(1);
  });

  it("carries no duplicate of the absorbed panels on step 4", () => {
    const html = wizardAt(4);
    expect(countOf(html, 'data-telling=""')).toBe(0);
    expect(countOf(html, 'data-array="messages"')).toBe(0);
  });
});

describe("DEF-CUS-7911 \u00b7 the Review says what a charge COSTS", () => {
  /**
   * \u26a0 **FILED FROM A PHOTOGRAPH, NOT FROM A TEST** (lane NC5-PHOTOS).
   * `step5-review.png` draws `CHARGE \u00b7 BASIS \u00b7 QTY \u00b7 EACH \u00b7 AMOUNT`; the
   * built table had THREE columns, so the review summarised the charges and
   * never said what one costs. **The group's own docstring already promised
   * `Each` and `Amount` came from `quote-preview`** \u2014 hard-won law 1, a
   * comment claiming a guarantee is not the guarantee.
   *
   * \u26a0 **THESE ASSERT THE COLUMNS. EVERY EARLIER CASE ASSERTED THE ROWS**,
   * which were always right \u2014 a table can lose half its columns with every
   * row assertion green. Same blind spot as the duplicate panels, one axis
   * over.
   */
  it("draws the Each and Amount cells the drawing asks for", () => {
    const html = review();
    expect(html).toContain('data-quote-money="unit-price"');
    expect(html).toContain('data-quote-money="amount"');
  });

  it("prints NO figure at all when the server has priced nothing", () => {
    // \u26a0 **THE CASE THAT FAILS IF ANYBODY COMPUTES.** The draft carries
    // charge lines and quantities and the preview is unpriced, so a browser
    // doing `qty \u00d7 each` would put a figure on the screen \u2014 or, just as
    // wrong, `$0.00`, which reads as *free* where the truth is *not priced*.
    // A blank is the only correct answer (hard rule 2, `DEF-088`,
    // `DEF-127`).
    const html = review();
    expect(html).not.toContain("$");
  });
});
