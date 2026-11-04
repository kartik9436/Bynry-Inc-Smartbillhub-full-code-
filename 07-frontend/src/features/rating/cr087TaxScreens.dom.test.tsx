// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-087 — the Taxes & fees screens against their drawn blueprint.
//           `CR-087-p022` / `p025` / `p027` (TAX-02's three steps) and
//           `p030` / `p034` / `p036` (S13's three tabs).
//           Screens: S13 · TAX-02
// Rules:    BR-RAT-104 (a live tax is CORRECTED with a new dated row carrying a
//           written reason, never edited in place) · BR-RAT-107 / PRB-05 (the
//           premises count narrows on class and service, not the boundary
//           alone) · BR-RAT-113 (the two ways a plan carries a tax) ·
//           BR-RAT-087 / DEF-364 (the SERVER renders a percent) · B14 rule 31
//           (no database id on screen) · B14 rule 37 (a drawn figure is an
//           illustration and no test may assert one) · hard-won law 2 (built is
//           not wired, in BOTH directions)
// ───────────────────────────────────────────────────────
/**
 * FOUR THINGS NO EXISTING TEST COULD SEE, AND WHY EACH ONE SURVIVED A GREEN SUITE
 * ══════════════════════════════════════════════════════════════════════════
 *
 * **1 · A DOOR THAT IS SERVED, TYPED AND CALLED BY NOTHING.**
 * `POST /taxes/{id}/corrections` has been implemented and routed since DEF-384
 * and `correctTax` typed in `endpoints.ts` since the same day — and no
 * component called it. Meanwhile `Edit` was live on a tax in force, opened this
 * wizard, and the wizard refused every field with
 * *"…that route has not been built, so nothing here can be saved"* — a sentence
 * that was true when written and false from the day the endpoint landed. Every
 * suite passed: a refusal renders perfectly well, and nothing asked whether it
 * was still TRUE. That is hard-won law 2 in both directions at once, on the one
 * action the blueprint calls this screen's primary.
 * **The assertion that catches it is about the REQUEST**, not about the DOM:
 * pressing the commit on an in-force tax must reach `/corrections`.
 *
 * **2 · TWO PREMISES COUNTS THAT COULD DISAGREE.** The blueprint's own sentence
 * is *"drawn by the same component as step 1, so the two counts cannot
 * disagree"*. The component WAS the same and the ARGUMENTS were not — step 1
 * passed all three narrowings and step 3 passed the boundary alone, and
 * `MatchedPremisesNote` defaults the missing lists to `[]`. So a tax restricted
 * to one class read its true reach on step 1 and the boundary's WHOLE count on
 * the last screen before the commit — larger than the truth. **Both steps
 * rendered a sentence, so every assertion in the suite passed**; nothing
 * compared the two numbers, and nothing could, because the difference is in the
 * QUERY. These cases read the request the wizard actually issues.
 *
 * **3 · THREE OF TEN DRAWN FACTS NOT READ BACK, AND ONE EXTRA THAT IS.** The
 * review step is the last screen before a levy goes live. It did not read back
 * the AUTHORITY, what is TAXED, or the DISCOUNT treatment — the field the
 * detail page itself calls *"the field that changes the arithmetic"* — and it
 * did read back `FILED`, which the wizard stopped collecting on 2026-09-08. A
 * read-back's one job is to be what the clerk just said.
 *
 * **4 · HALF THE KPI STRIP WAS FURNITURE.** Two of the four tiles were an
 * em-dash on every tax that has ever existed. `definitionDetail.tsx`'s own
 * comment on the DISCOUNT kind names the shape — *"furniture, not a stated
 * absence"* — and the same fix never reached the tax.
 *
 * ⚠ **NO DRAWN FIGURE IS ASSERTED ANYWHERE IN THIS FILE (B14 rule 37).** The
 * blueprint inks `1,284` premises, `6` plans, `74`/`12`/`1` units and
 * `6.25%`/`6.00%` rates. Every one is an illustration of a SHAPE. The fixtures
 * below carry this file's own numbers.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { GlAccountRef, TaxJurisdiction, TaxRow } from "@/api/endpoints";
import type { KpiTile } from "@/components/KPIStrip";

import {
  DEFINITION_KPI_LABEL_KEYS,
  presentTax,
} from "./definitionDetail";
import type { DefinitionRegional } from "./definitionDetail";
import type { Translator } from "./ratingShared";
import { taxRowDefaults } from "./taxRowFixture";

/**
 * A tile's rendered value. `KpiTile` is a UNION — a money tile or a value tile —
 * and all four of the tax's are value tiles.
 *
 * ⚠ **NARROWED, NOT CAST.** A cast would read a money tile's `undefined` as a
 * legitimate absence, which is exactly the state these cases exist to refuse:
 * the defect was two tiles that always rendered nothing.
 */
function tileValue(tile: KpiTile): unknown {
  return "value" in tile ? tile.value : undefined;
}

const t: Translator = (key, params) => i18n.t(key, params);
const REGIONAL: DefinitionRegional = { timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" };

afterEach(cleanup);

// ⚠ **THE TENANT SERVICE LIST IS DELIBERATELY NOT SEEDED.** Nothing below
// asserts on the service tick-list, and a hand-built `TenantServiceRow` is a
// second copy of a contract declared once in `endpoints.ts` — the exact reason
// `taxRowFixture.ts` exists. An empty list is what a screen legitimately gets
// while that reference read is in flight.

const JURISDICTIONS: TaxJurisdiction[] = [
  {
    id: "j-city",
    name: "City of Silver Creek",
    authority: "City of Silver Creek",
    level: "city",
    reference_no: null,
  },
];

const ACCOUNTS: GlAccountRef[] = [{ id: "gl-2301", code: "2301", name: "Tax payable — city" }];

/** A tax that IS IN FORCE — active, started, not ended. `taxIsInForce`'s own
 *  four conditions, which is what turns this wizard into a correction form. */
const IN_FORCE: TaxRow = {
  ...taxRowDefaults(),
  id: "tax-live",
  name: "City franchise fee",
  jurisdiction: JURISDICTIONS[0],
  kind: "percent",
  rate: "0.015000",
  rate_display: "1.50%",
  base_includes_usage: true,
  base_includes_base: true,
  applies_to_services: ["water"],
  applies_to_customer_classes: ["commercial"],
  premises_scope_kind: "city_limits",
  premises_scope_value: "Silver Creek",
  liability_gl_account_id: "gl-2301",
  remit_to: "City of Silver Creek",
  filing_frequency: "monthly",
  effective_from: "2026-01-01",
  effective_to: null,
  status: "active",
  used_by_plans: 2,
};

// ⚠ SECTIONS 1–3 (the correction door, one reader for the premises count, the
// review read-back) TESTED `TaxWizard.tsx`, RETIRED 2026-10-03 (CR-165-BRC10
// task 7). Their guarantees now live where the screens do:
//   · a live tax is CORRECTED, never edited in place — `taxForm/EditTaxForm.dom.test.tsx`
//     (Fix a mistake posts to /corrections with a reason; dates are read, not boxes);
//   · one premises count — the edit and New forms read it through ONE query
//     (`taxForm/useTaxFormLists.tsx`), so two steps cannot ask different questions;
//   · the review read-back — `taxForm/NewTaxWizard.dom.test.tsx` and the edit Review.

// ══════════════════════════════════════════════════════════════════════════
// 4 · THE KPI STRIP
// ══════════════════════════════════════════════════════════════════════════

describe("CR-087 p030 · the tax KPI strip carries no permanent em-dash", () => {
  it("the labels are the DRAWN facts, minus the status the pill already carries", () => {
    // ⚠ `…tax.base` and `…tax.collected` were two of the four and were an
    // em-dash on every tax that has ever existed — `PRB-06`, two reads that do
    // not exist. Half a strip of furniture.
    //
    // ⚠ **AND `…tax.status` WAS A THIRD KIND OF WASTE — NOT A BLANK, A SECOND
    // COPY.** The blueprint draws the tax status twice, as the pill under the
    // title and again as tile 3, and contradicts itself. PO 2026-09-10,
    // verbatim: *"show only one status"*. The pill wins, because that is where
    // every other Plans & Rates detail screen carries a lifecycle word, so the
    // tax strip is THREE and nothing was invented to refill the slot.
    expect(DEFINITION_KPI_LABEL_KEYS.tax).toEqual([
      "rating.definition.kpi.tax.plans",
      "rating.definition.kpi.tax.premises",
      "rating.definition.kpi.tax.rate",
    ]);
  });

  it("every tile carries a figure once the reach is counted", () => {
    const view = presentTax(IN_FORCE, t, ACCOUNTS, REGIONAL, {
      state: "counted",
      count: 4,
      total: 9,
      everywhere: false,
      narrowed: true,
    });
    // No tile is `NO_FIGURE`. The em-dash is reserved for a figure that is
    // genuinely absent, which is now none of the three.
    expect(view.kpis.map(tileValue)).not.toContain("—");
    expect(tileValue(view.kpis[1])).toBe(4);
    expect(view.kpis[1].detail).toBe(t("rating.definition.tax.reach.ofTotal", { total: 9 }));
    // ⚠ **SLOT 3 WAS THE STATUS AND IS NOW THE RATE** (PO 2026-09-10, *"show
    // only one status"*). Asserting the RATE here rather than deleting the line
    // keeps what this case is for: every slot on the strip carries a real
    // figure, and the last one is the figure the status tile used to crowd out.
    // Read from the FIXTURE's own display string, never a literal — the rate is
    // the server's `rate_display` and a number typed here twice is a number free
    // to drift from the row it is supposed to be describing.
    expect(tileValue(view.kpis[2])).toBe(
      t("rating.taxes.rate.percent", { rate: IN_FORCE.rate_display }),
    );
  });

  it("a boundary nothing can evaluate reads 0 WITH its reason, never a bare zero", () => {
    const view = presentTax(IN_FORCE, t, ACCOUNTS, REGIONAL, { state: "unresolvable", total: 9 });
    // ⚠ A bare 0 reads as *"your boundary matches nobody, fix your boundary"*.
    // The reason travels with it — `MatchedPremisesNote`'s own argument, one
    // component over.
    expect(tileValue(view.kpis[1])).toBe(0);
    expect(view.kpis[1].detail).toBe(t("rating.definition.tax.reach.unchecked"));
  });

  it("a read that failed says so and never counts nobody", () => {
    const view = presentTax(IN_FORCE, t, ACCOUNTS, REGIONAL, { state: "unavailable" });
    expect(tileValue(view.kpis[1])).toBe("—");
    expect(view.kpis[1].detail).toBe(t("rating.definition.tax.reach.unavailable"));
  });

  it("the sub-line says what Edit DOES, which is what the action ruling depends on", () => {
    const view = presentTax(IN_FORCE, t, ACCOUNTS, REGIONAL);
    // Page 33: *"What editing does still differs — and that belongs in a
    // sentence, not in a fourth name for the same button."* Without it, `Edit`
    // on a live tax is an unlabelled trap.
    expect(view.subline).toContain(t("rating.definition.tax.editPolicy"));
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 5 · 6 · THE TAB BODIES AND THE REMITTANCE BLOCK — MOVED, NOT DROPPED
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **CR-165-BRC10 round 3 (task 6) rebuilt the tax details page from images
// 18–23**, and the three things these sections tested no longer exist in the
// shape they tested: the Plans tab counts ACCOUNTS beside units with an *Add
// to a plan* door, the Audit tab is every change with its reason (PO round 6 —
// the versions moved to a table on Overview), and filing is READ on Overview
// rather than entered in a *Remittance & filings* form (README point 3). The
// cases that replace them are in `taxDetail/taxDetail.dom.test.tsx`, each
// watched failing on the old page first. `taxDetailTabs.tsx` is deleted.
