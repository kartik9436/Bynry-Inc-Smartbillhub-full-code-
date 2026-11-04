// ── Trace ──────────────────────────────────────────────
// Defects: DEF-MET-6110 (step 6 offered `TAP` — a code billing cannot price —
//          and the last press answered "Something went wrong on our side"
//          after thirty-three clerk acts) · DEF-MET-6111 (units labelled the
//          same as ones the picked address already holds; the same raw 500)
// Decision: 12-governance/02-decision-log.md, 2026-09-21 — "A RULE REFUSAL
//          REACHES THE CLERK ON THE STEP THEY CHOSE IT". PO, verbatim: *"this
//          fix is correct - you ahve to show the error at step you mentioned"*.
// Rules:   B14 rule 33 (a fact ≤ 6 words, an instruction ≤ 6 words per
//          sentence, RATIONALE zero words on screen) · rule 43 (a piece of UI
//          is a COMPONENT) · BR-SHL-020 r2 (the sentence comes from the
//          catalogue and from nothing else)
// Screens: S87 step 3 (Units) · step 6 (Charges)
// ───────────────────────────────────────────────────────
//
// ⚠ **A NEW FILE RATHER THAN CASES ADDED TO `NewConnectWizard.test.tsx`.** That
// file is 1,400 lines and more than one lane edits this wizard at a time; in a
// shared tree the second lane to commit a shared file reverts the first, with a
// correct file count and nothing in the diff to notice (CLAUDE.md law 11).
//
// ⚠ **AND THE ONE CASE THAT COULD NOT BE WRITTEN HERE IS NAMED, NOT SKIPPED.**
// Whether the refusal actually LANDS on step 6 with the footer intact is a
// question about a rendered, routed, server-answering wizard, and no gate in
// this repo reads rendered output (law 6). It is proved by
// `10-scripts/cr126_s9_acceptance_walk.mjs` variations `x6110b` and `x6111`,
// which drive the real commit in Chromium and print the step, the strip, the
// footer buttons and the fields still held.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18next from "i18next";

import "@/i18n";

import { ApiError, createApiClient } from "@/api/client";

import { canBeRaisedOnItsOwn } from "./NewConnectChargesStep";
import { StepRefusal } from "./newConnectStepKit";
import { stepOwningRefusal } from "./NewConnectWizard";
import { UnitsStep } from "./NewConnectUnitsStep";

/** Answers every catalogue read with nothing, which is the state this file
 *  is about: the clash is computed from what the wizard already knows. */
const stepRefusalClient = createApiClient({
  tenant: "ottumwa",
  fetchImpl: async () =>
    new Response(JSON.stringify({ count: 0, results: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
});
import { emptyDraft } from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";
import { draftUnits } from "./newConnectDraft";

const t = (key: string, options?: Record<string, unknown>) => String(i18next.t(key, options));

function refusalFrom(params: Record<string, unknown>): ApiError {
  return new ApiError(422, {
    code: "BIZ-COMPLETENESS",
    message_key: "metering.connection_unit_label_taken",
    params,
    br_ref: "BR-MET-112",
  });
}

function unitsDraft(from: string, to: string, prefix = "Apt"): NewConnectDraft {
  const draft = emptyDraft();
  return { ...draft, pattern: { ...draft.pattern, prefix, from, to } };
}

// ════════════════════════════════════════════════════════════════════════════
// 1 · WHICH STEP OWNS A REFUSAL
// ════════════════════════════════════════════════════════════════════════════
describe("stepOwningRefusal", () => {
  it("resolves the server's step ID to this wizard's own position", () => {
    // ⚠ **THE POSITION IS LOOKED UP, NEVER HARDCODED.** `owner` and `scope`
    // merged into one screen on 2026-09-16 and every later step moved down a
    // number; a refusal carrying `6` would have meant Charges before that day
    // and Communication after it, with nothing going red.
    expect(stepOwningRefusal(refusalFrom({ step: "units" }))).toEqual({
      id: "units",
      position: 3,
    });
    // ⚠ **AND IT HAPPENED AGAIN, WHICH IS THE POINT: `charges` WAS POSITION 6
    // AND IS POSITION 4 SINCE 2026-09-28 (`CR-150-BRC09`, eight → five).**
    // The ID did not move and no second map was written — `stepOwningRefusal`
    // resolves it out of the declared list and the server still stamps
    // `charges` at the call site (`DEF-MET-7690`). The figure is AMENDED
    // rather than loosened: a case that stopped asserting the position would
    // stop being able to catch the thing it exists for.
    expect(stepOwningRefusal(refusalFrom({ step: "charges" }))).toEqual({
      id: "charges",
      position: 4,
    });
    expect(stepOwningRefusal(refusalFrom({ step: "premise" }))).toEqual({
      id: "premise",
      position: 2,
    });
  });

  it("routes nothing it does not recognise", () => {
    // The front-end half of the server's *"anything unrecognised is re-raised
    // untouched"*. A destination invented here lands the clerk on a screen
    // where the field they must change is not.
    expect(stepOwningRefusal(refusalFrom({}))).toBeNull();
    expect(stepOwningRefusal(refusalFrom({ step: "" }))).toBeNull();
    expect(stepOwningRefusal(refusalFrom({ step: "a-step-that-does-not-exist" }))).toBeNull();
    expect(stepOwningRefusal(refusalFrom({ step: 6 }))).toBeNull();
    expect(stepOwningRefusal(new Error("a network drop"))).toBeNull();
    expect(stepOwningRefusal(null)).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 2 · `DEF-MET-6110` LAYER 1 — WHICH CHARGE CODES STEP 6 MAY OFFER
// ════════════════════════════════════════════════════════════════════════════
describe("canBeRaisedOnItsOwn", () => {
  const row = (over: Record<string, unknown> = {}) =>
    ({
      id: "c1",
      code: "CONN",
      name: "Connection fee",
      charge_type: "one_time",
      service: null,
      amount_rule: "flat",
      amount: "45.000000",
      percent: null,
      min_amount: null,
      max_amount: null,
      amount_display: "45.00",
      percent_display: null,
      min_amount_display: null,
      max_amount_display: null,
      gl_account_id: "gl-1",
      ...over,
    }) as Parameters<typeof canBeRaisedOnItsOwn>[0];

  it("offers a flat code with a price and an account", () => {
    // Without this the filter could be *return false* — a check incapable of
    // passing, which empties the picker and is the mirror of the defect.
    expect(canBeRaisedOnItsOwn(row())).toBe(true);
    // `null` states no rule, and `charge_by_code` reads that as flat. The two
    // defaults have to agree or the picker and the server disagree about the
    // same row.
    expect(canBeRaisedOnItsOwn(row({ amount_rule: null }))).toBe(true);
  });

  it("refuses the three shapes billing refuses", () => {
    // `TAP` on the seeded demo: no amount at all. This is the exact row the PO
    // picked out of the product's own picker.
    expect(canBeRaisedOnItsOwn(row({ code: "TAP", amount: null, amount_rule: null }))).toBe(false);
    // `LATE`: a percent rule needs a basis a standalone fee has none of, so
    // `charge_by_code` answers `amount: null` deliberately.
    expect(canBeRaisedOnItsOwn(row({ amount_rule: "percent_with_minimum", amount: null }))).toBe(
      false,
    );
    expect(canBeRaisedOnItsOwn(row({ amount_rule: "percent" }))).toBe(false);
    // No GL account — refused at pricing rather than at issue, so no invoice
    // number is spent on a draft that can never become a bill.
    expect(canBeRaisedOnItsOwn(row({ gl_account_id: null }))).toBe(false);
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 3 · `DEF-MET-6111` LAYER 1 — STEP 3 ASKS BEFORE THE CLERK WORKS
// ════════════════════════════════════════════════════════════════════════════
describe("step 3 · what this address already holds", () => {
  // ⚠ **STEP 3 ABSORBED *Map services* AND *Work orders* ON 2026-09-28**
  // (`CR-150-BRC09`), so it reads the tenant's catalogues and builds a tenant
  // path. It therefore needs a query client and a REAL `/:tenant/…` route —
  // a bare `MemoryRouter` leaves `useParams().tenant` undefined and every URL
  // the screen builds comes out `//…`, which reads as a good string to
  // `toContain` (CLAUDE.md hard-won law 2).
  const render = (draft: NewConnectDraft, held: readonly string[]) => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/ottumwa/connections/new"]}>
          <Routes>
            <Route
              path="/:tenant/connections/new"
              element={
                <UnitsStep
                  draft={draft}
                  units={draftUnits(draft)}
                  labelsAlreadyHere={held}
                  breaches={[]}
                  sewerGaps={[]}
                  proposed={[]}
                  proposalsUnavailable={false}
                  onPatch={() => undefined}
                  client={stepRefusalClient}
                  t={t}
                  dateFormat="MM/DD/YYYY"
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
  };

  it("names the clashing label before a word is typed", () => {
    const html = render(unitsDraft("101", "103"), ["Apt 101", "Apt 102", "Apt 103"]);
    expect(html).toContain("data-labels-taken");
    // The PO's own words for what this screen should say.
    expect(html).toContain("Apt 101 already exists here.");
    expect(html).toContain("Change the unit numbers.");
  });

  it("marks every clashing unit, not only the one the sentence names", () => {
    // A build can clash on several labels at once and one sentence can name
    // one of them. The strip says what happened; each unit's GROUP says which.
    // ⚠ **THE SURFACE MOVED IN THE 2026-09-28 FOLD AND THE COVERAGE DID NOT.**
    // The table is grouped by unit now, so the per-unit mark is that group's
    // own error rather than a cell attribute.
    const html = render(unitsDraft("101", "103"), ["Apt 101", "Apt 102", "Apt 103"]);
    expect(html.split("Already exists here.").length - 1).toBe(3);
  });

  it("says nothing where nothing collides", () => {
    // ⚠ **THE CASE THAT STOPS THIS BEING A CHECK THAT CANNOT FAIL.** A screen
    // that warned on every build would satisfy both cases above and would make
    // the warning meaningless.
    const clean = render(unitsDraft("104", "106"), ["Apt 101", "Apt 102", "Apt 103"]);
    expect(clean).not.toContain("data-labels-taken");
    expect(clean).not.toContain("Already exists here.");
    // A build on a NEW address holds nothing, which is `[]` and not *unasked*.
    const fresh = render(unitsDraft("101", "103"), []);
    expect(fresh).not.toContain("data-labels-taken");
  });

  it("renders the catalogue's sentence and never the key", () => {
    // BR-SHL-020 r2 — if the key were missing from `en.json`, i18next prints
    // the key itself and a test asserting `toContain("Apt 101")` would still
    // pass on the interpolated default. This asks for the absence of the key.
    const html = render(unitsDraft("101", "101"), ["Apt 101"]);
    expect(html).not.toContain("customers.newConnect.step4.labelTaken");
    expect(html).toContain("Already exists here.");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 4 · THE REFUSAL COMPONENT ITSELF
// ════════════════════════════════════════════════════════════════════════════
describe("StepRefusal", () => {
  it("renders nothing for a step that was not refused", () => {
    // A step mounts it unconditionally, so `null` has to be silent — otherwise
    // every step would carry its own *should I show this* branch.
    expect(renderToStaticMarkup(<StepRefusal step="charges" message={null} />)).toBe("");
  });

  it("carries the step it belongs to, so a walk can read it", () => {
    const html = renderToStaticMarkup(
      <StepRefusal step="charges" message="A charge here cannot be billed." />,
    );
    expect(html).toContain('data-step-refusal="charges"');
    expect(html).toContain('role="alert"');
    expect(html).toContain("A charge here cannot be billed.");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 5 · B14 RULE 33 — THE COPY IS CAPPED BY WHAT IT IS FOR
// ════════════════════════════════════════════════════════════════════════════
describe("the sentences these refusals put on screen", () => {
  // ⚠ **G33 ALREADY COUNTS WORDS AND THIS IS NOT A SECOND COPY OF IT.** What
  // this pins is that these five keys EXIST in the catalogue at all: a key a
  // lane retires, or never fans in, renders as the key string and every
  // assertion above that reads a sentence would go red — except this one, which
  // says why.
  const keys = [
    "metering.connection_charge_refused",
    "metering.connection_unit_label_taken",
    "customers.newConnect.step4.labelTaken",
    "customers.newConnect.step4.labelTakenCell",
    "customers.newConnect.step6.noneBillable",
  ];

  it("are in the catalogue and are sentences, not keys", () => {
    for (const key of keys) {
      const rendered = t(key, { label: "Apt 101" });
      expect(rendered, `${key} is missing from the catalogue`).not.toBe(key);
      expect(rendered.length, `${key} is empty`).toBeGreaterThan(0);
    }
  });

  it("carry no rule id and no internal code — B14 rule 33", () => {
    for (const key of keys) {
      const rendered = t(key, { label: "Apt 101" });
      expect(rendered, `${key} shows an ID to a clerk`).not.toMatch(
        /\b(?:BR|OQ|DEF|GT|US|EP|CR)-[A-Z]{0,3}-?\d/,
      );
      // A leftover placeholder means a param the call site never passes.
      expect(rendered, `${key} has an unfilled placeholder`).not.toMatch(/\{\{/);
    }
  });
});
