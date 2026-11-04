// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W6 tasks 6.11 and **6.16** — S87's cases, and the four
//           `TC-NCT-*` cases of B18 §5.4.7 that are expressible on a SCREEN.
//           The other five are service-layer or tenancy cases and are named in
//           the file trailer with where each one actually lives, rather than
//           being re-asserted here over a fixture (a screen test that seeds its
//           own payload cannot prove a tenant boundary).
// Rules:    BR-MET-112 (nothing is written until step 9 — asserted ON THE WIRE:
//           steps 1–8 issue no request) · BR-MET-111 · BR-MET-113 · BR-SHL-025
//           (disabled WITH the reason) · CLAUDE.md hard rule 2 (no money is
//           computed in this client — asserted as an ABSENCE of the drawn
//           figures)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE MONEY CASES ASSERT THAT A FIGURE IS *NOT* ON THE SCREEN, AND THAT IS
// DELIBERATE.** B18 draws `$150.00 per residential unit`, `$762.50 / month` and
// a `$14,435.00` quote. Every one of them belongs to a specific seeded build or
// a tenant's own policy, and none is served to this wizard. A screen that
// printed them would be showing a person a real-looking number about their
// money that came from a design document — which is the DEF-127 shape. So the
// tests pin their absence, because that is the behaviour that could regress.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

// The catalogues are loaded so every `t(key, {defaultValue})` in the wizard
// resolves exactly as it does in the product — the assertions below read the
// rendered sentence, so a key the catalogue DOES hold would be caught here too.
import i18next from "i18next";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import {
  NewConnectWizard,
  commitPlanOf,
  draftManifest,
  draftUnitServices,
  draftUnits,
  emptyDraft,
} from "./NewConnectWizard";
import type { NewConnectDraft } from "./NewConnectWizard";
import type { UnitPattern } from "./newConnectShared";
// Imported from the modules that OWN them rather than through the wizard's
// re-exports: the step files are one-per-lane and adding a re-export line to
// the orchestrator for every helper is a shared-file edit per lane (law 11).
import { UnitsStep, occupancyLabelCodes } from "./NewConnectUnitsStep";
import {
  SERVICE_ASSET_DEFAULT,
  SERVICE_ASSET_TYPES,
  assetTypesForService,
  gridCounts,
  gridRows,
  orderForService,
  sizesForService,
} from "./NewConnectServicesStep";
import {
  PremiseStep,
  newConnectPlansQueryKey,
  patchFromPickedPremises,
} from "./NewConnectPremiseStep";
// `DEF-CUS-5483` — the counting IS the calculation on step 6, so it is
// asserted from the module that owns it.
import { quoteCounts } from "./NewConnectChargesStep";
// `CR-150-BRC09` task 12 — occupancy is ASKED on the unit rows now and SHOWN
// on the review, so the four-option VOCABULARY is asserted from the module
// that defines it rather than from a screen that no longer offers the radio.
import { OCCUPANCY_COPY } from "./NewConnectReviewStep";
import { BUILD_CHARGE_BASES, buildChargeQuantities } from "./newConnectDraft";
import { fileOwnerDocuments } from "./NewConnectWizard";
import { occupancyOfUnit, unitServiceKey } from "./newConnectDraft";
import {
  COMMON_AREA_LABEL,
  NEW_CONNECT_STEPS,
  OCCUPANCY_CHOICES,
  availabilityBreaches,
  expandUnitPattern,
  newConnectStepNumber,
  planCoverageGaps,
  sewerWithoutWater,
  takesAMeter,
} from "./newConnectShared";

const TEST_TENANT = "brazosbend";
const TEST_PLAN_ID = "11111111-1111-1111-1111-111111111111";
/** `queryKeys.tenantServices`, restated rather than imported so this file does
 *  not grow a dependency on the query-key module for one array. */
const TENANT_SERVICES_KEY = ["settings", "services"] as const;

/**
 * The drawn build's per-unit answer, expressed the way the product now stores
 * it: **one entry per unit per service** (PO 2026-09-16 — units inherit every
 * service the premise takes and the clerk drops what a unit does not take).
 *
 * ⚠ **THIS REPLACES `apartmentServices`/`commonAreaServices` IN THE FIXTURE,
 * AND THE TWO ARE NOT THE SAME THING.** Those were ONE set for every dwelling,
 * so the drawn common area — *"electric and water and no sewer"* — could only
 * ever be a second global set. Written as a grid the fixture says the same
 * build and can also say *unit 4 is different*, which is what every case below
 * about a single unit needs.
 */
function drawnGrid(
  pattern: UnitPattern,
  dwelling: readonly string[],
  common: readonly string[],
): Record<string, { taken: boolean }> {
  const grid: Record<string, { taken: boolean }> = {};
  for (const unit of expandUnitPattern(pattern)) {
    const wants = unit.isCommonArea ? common : dwelling;
    for (const service of DRAWN_PREMISE_SERVICES) {
      grid[unitServiceKey(unit.label, service)] = { taken: wants.includes(service) };
    }
  }
  return grid;
}

const DRAWN_PATTERN: UnitPattern = {
  prefix: "Apt",
  from: "101",
  to: "125",
  includeCommonArea: true,
};
const DRAWN_PREMISE_SERVICES = ["electric", "water", "sewer", "trash", "storm_water"];

/** The drawn build: `500 Main Street`, `Apt 101–125` plus the common area, the
 *  street offering five services, apartments on E/W/S and the common area on
 *  trash and storm water. Every figure below is §5.4.10's own. */
function drawnDraft(over: Partial<NewConnectDraft> = {}): NewConnectDraft {
  return {
    ...emptyDraft(),
    // ⚠ **THE TWO NESTED LITERALS SPREAD THEIR OWN EMPTY SHAPE FIRST, AND
    //    THAT IS A FIX RATHER THAN A STYLE (2026-09-16).** Written as bare
    //    literals they RESTATE `OwnerForm` and `premise` in full, so every
    //    field a lane adds to the draft breaks this fixture and every test in
    //    the file with it — which is what happened twice today: `7f023f0f`
    //    added the owner's party kind and identity, `3e018eab` added the
    //    premises id, name, city, state and ZIP, and both left this file
    //    type-broken on the branch. Spreading means a new field arrives with
    //    its own default and the drawn build keeps naming only what it draws.
    owner: {
      ...emptyDraft().owner,
      name: "Ridge Property LLC",
      kind: "builder_developer",
      subCategory: "construction_temporary",
      // `DEF-CUS-5467` — the drawn build is a COMPANY, and a company opens its
      // master account on a Tax ID and on nothing else (`BR-CUS-1023`: a phone
      // mints a number for a person and never for a business). Without these
      // two the drawn build carries an unstated party kind, which is a real
      // answer that mints no customer number — so the fixture would be a build
      // that cannot complete.
      partyKind: "company",
      taxId: "TX-4471-08",
    },
    scope: "new_premise",
    targetActivation: "2026-09-30",
    mode: "our_crew",
    premise: {
      ...emptyDraft().premise,
      address: "500 Main Street",
      premiseType: "multi_unit",
      parcelRef: "PL-2026-0884",
      readRoute: "RT-001",
    },
    pattern: DRAWN_PATTERN,
    premiseServices: DRAWN_PREMISE_SERVICES,
    // The drawn build, said per unit: apartments on E/W/S, the common area on
    // trash and storm water. `premiseServices` offers five, so every unit drops
    // the two it does not take — which is the grid's whole job.
    unitServiceGrid: drawnGrid(
      DRAWN_PATTERN,
      ["electric", "water", "sewer"],
      ["trash", "storm_water"],
    ),
    ...over,
  };
}

interface Render {
  html: string;
  urls: string[];
}

/**
 * Render ONE step over a build that actually has units in it.
 *
 * ⚠ **`renderWizard(3)` CANNOT DO THIS AND THAT IS NOT A GAP IN IT.** The
 * wizard owns its own draft and starts from `emptyDraft()`, whose pattern is
 * two empty strings — so step 3 renders its controls over ZERO rows and every
 * `toContain` about a CELL passes or fails for the wrong reason. A row-level
 * assertion needs a build, and a build needs the component.
 *
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/...` PATTERN** (hard-won law 2): a bare
 * `MemoryRouter` with no matching route leaves `useParams().tenant` undefined,
 * and every address the page builds comes out `//...` — a protocol-relative URL
 * to another host that reads as a perfectly good string to `toContain`.
 */
function renderStep(node: React.ReactNode): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new?step=3`]}>
          <Routes>
            <Route path="/:tenant/connections/new" element={<>{node}</>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Step 3 over the drawn build, with a translator that resolves exactly as the
 *  product's does.
 *
 *  ⚠ **`labelsAlreadyHere` IS REQUIRED AND DEFAULTS TO EMPTY HERE, WHICH IS A
 *  FACT AND NOT A CONVENIENCE (`DEF-MET-6111`).** `[]` says *this address holds
 *  nothing* — the answer for every build on a NEW address — and a test that
 *  wants the clash passes the labels. */
/** Answers every reference read with nothing. The cases below are about the
 *  unit pattern and the clash, neither of which needs a catalogue. */
const unitsStepClient = createApiClient({
  tenant: TEST_TENANT,
  fetchImpl: async () =>
    new Response(JSON.stringify({ count: 0, results: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
});

function renderUnits(draft: NewConnectDraft, labelsAlreadyHere: readonly string[] = []): string {
  // ⚠ **THE SIX EXTRA PROPS ARE THE TWO ABSORBED STEPS' OWN** — step 3 took
  // *Map services* and *Work orders* in on 2026-09-28 (`CR-150-BRC09`).
  return renderStep(
    <UnitsStep
      draft={draft}
      units={draftUnits(draft)}
      labelsAlreadyHere={labelsAlreadyHere}
      breaches={[]}
      sewerGaps={[]}
      proposed={[]}
      proposalsUnavailable={false}
      onPatch={() => undefined}
      client={unitsStepClient}
      t={(key, options) => String(i18next.t(key, options))}
      dateFormat="MM/DD/YYYY"
    />,
  );
}

function renderWizard(step: number): Render {
  const urls: string[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input) => {
      urls.push(String(input));
      return new Response(JSON.stringify({ count: 0, results: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const html = renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new?step=${step}`]}>
          <Routes>
            <Route path="/:tenant/connections/new" element={<NewConnectWizard client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { html, urls };
}

describe("S87 · the New Connect wizard (CR-030 W6 task 6.11)", () => {
  it("DEF-CUS-5186 — the rail is FIVE steps, in the drawings' order, and `scope` is not one of them", () => {
    // ⚠ **THE IDS ARE ASSERTED, NOT ONLY THE COUNT.** A count alone goes green
    // again the moment somebody re-splits customer and scope and drops another
    // step to compensate, which is exactly the shape this defect was: the rail
    // said nine while the drawing said eight for three weeks and every suite
    // passed.
    //
    // ⊕ **AMENDED 2026-09-29 (`ed4e7cb30`, `CR-150-BRC09` — *"New Connect is
    // FIVE steps, one word each"*).** The case is RE-POINTED, not relaxed: it
    // still pins the whole list by id, in order, with its length and its first
    // word, so the defect it was written for — a rail that quietly gains or
    // re-splits a step — still goes red. What moved is the shape it pins.
    // `services` and `plans` are absorbed into `units`, `communication` into
    // `review`, and `owner` is renamed `customer` (`newConnectShared.tsx`'s
    // `NEW_CONNECT_STEPS` docstring carries the PO's own map).
    //
    // ⚠ **AND `scope` IS STILL NOT ONE OF THEM**, which is the half of this
    // case's title that the redesign did not touch — it is a FIELD on step 2
    // (`What is built`), never a step, and the negative below says so.
    expect(NEW_CONNECT_STEPS.map((step) => step.id)).toEqual([
      "customer",
      "premise",
      "units",
      "charges",
      "review",
    ]);
    expect(NEW_CONNECT_STEPS).toHaveLength(5);
    expect(NEW_CONNECT_STEPS[0].en).toBe("Customer");
    expect(NEW_CONNECT_STEPS.map((step) => step.id)).not.toContain("scope");
  });

  it("BR-MET-112 — the wizard no longer PRINTS it, and still does not write until the last step", () => {
    const { html } = renderWizard(1);
    // AMENDED 2026-09-28 (PO reported bug 1, "To Much text on every step
    // reduce it"). This case asserted the note "Nothing is written until step
    // 8. Create connection writes it." on every one of the eight screens. The
    // redesign drawings list it under "Removed from this step" on ALL FIVE new
    // screens, and it is B14 rule 33's rationale - why the product works this
    // way - at zero words on screen.
    //
    // BR-MET-112 ITSELF IS UNTOUCHED, and the two halves of it that a check can
    // actually hold are asserted here instead: no step-1 render performs a
    // write, and the commit lives on the LAST step behind its own button. The
    // old assertion only ever proved a sentence existed.
    expect(html).not.toContain("Nothing is written until step");
    expect(html).not.toContain("Create connection writes it.");
    expect(html).not.toContain("data-draft-notice");
    // ⊕ **AMENDED 2026-09-29 (`ed4e7cb30` — eight steps became five).** The
    // three assertions below are RE-POINTED at the new last step, not dropped:
    // each still asks exactly what it asked before.
    //   · the rail carries every step, so the person can see how far this goes
    //     — that was `8` of 8 and is `5` of 5;
    //   · `DEF-CUS-5198`'s guard is "there is no cell PAST the last one", the
    //     overflowing cell that hung 244px outside the rail at 1280 — that was
    //     the ninth and is now the sixth;
    //   · the one commit is on the LAST step and nowhere else (BR-SHL-019) —
    //     that was step 8 and is step 5.
    expect(html).toContain(`data-wizard-step="${NEW_CONNECT_STEPS.length}"`);
    expect(html).not.toContain(`data-wizard-step="${NEW_CONNECT_STEPS.length + 1}"`);
    expect(html).not.toContain("Create connection \u2713");
    expect(renderWizard(NEW_CONNECT_STEPS.length).html).toContain("Create connection \u2713");
  });

  it("DEF-CUS-5435 — every element p086/p087 draws on step 1 is ON step 1", () => {
    const { html } = renderWizard(1);
    // The four that were on another page or on no page at all.
    expect(html).toContain('id="nc_prefix"');          // was step 4 (Units)
    expect(html).toContain('id="nc_external_ref"');    // was nowhere
    // ⚠ `SegmentedField` renders `name="<id>"` on each radio and `id="<id>-label"`
    // on the label — never a bare `id="<id>"`. Asserting the id that does not
    // exist is a check that can only ever fail, which is its own defect class.
    // ⊕ **AMENDED 2026-09-29 (`CR-150-BRC09` `NCT-01`, the five-step
    // redesign).** Two changes, both the drawing's:
    //   * **`Scope` LEFT STEP 1 AGAIN** — `step1-customer.png` lists *"Scope
    //     and its three explanation lines"* under *Removed from this step* and
    //     `step2-premise.png` draws it as `What is built`. So the assertion is
    //     reversed rather than deleted: it must NOT be here, and the second
    //     line proves it IS on step 2.
    //   * **`Mode` IS A DROPDOWN** in the drawing's `Work` panel, not a
    //     segmented radio group, so it carries a bare `id` again.
    expect(html).not.toContain('name="nc_scope"');
    expect(html).not.toContain('id="nc_scope"');
    expect(renderWizard(2).html).toContain('id="nc_scope"');
    expect(html).toContain('id="nc_mode"');            // was step 2
    // AMENDED 2026-09-28 (PO reported bug 1). This case asserted the red strip
    // "This build has no home yet. The premise arrives next step." and the
    // placeholder "if known". The drawing lists both under "Removed from this
    // step": the strip explained the SHAPE of the wizard and the placeholder
    // said only that a field is optional, which the missing required marker
    // already says. The case is about WHICH FIELDS are on step 1, and every
    // field assertion around this block is unchanged.
    expect(html).not.toContain("This build has no home yet.");
    expect(html).not.toContain("The premise arrives next step.");
    expect(html).not.toContain("if known");
    // The ones that were already right and must not be lost in the merge.
    // ⊕ lane CF-1 (2026-10-18) — the shared customer form's own ids (drawing
    // set `customer-forms-2026-10-18`, image 06); Owner type keeps its id.
    expect(html).toContain('id="full_name"');
    expect(html).toContain('id="nc_owner_kind"');
    expect(html).toContain("data-customer-category");
    expect(html).toContain('id="email"');
    expect(html).toContain('id="phone"');
    expect(html).toContain("Becomes a customer");
    // And the drawn H1 for the merged step.
    expect(html).toContain("Who is asking, and what for?");
  });

  it("DEF-CUS-5435 — the two that MOVED are no longer on the page they left", () => {
    // The prefix left the units step; the target date left step 1.
    //
    // ⊕ **AMENDED 2026-09-29 (`ed4e7cb30` — eight steps became five).** Only
    // the DESTINATION of the target date moved, and the case keeps both of its
    // halves: it still says the field is absent from the page it left AND
    // present on the page it went to, which is the pair that makes this a
    // guard rather than a hole. `plans` (old step 5) was absorbed into `units`
    // (step 3), so `nc_target` now renders from `NewConnectUnitsStep`; the
    // step is named through `newConnectStepNumber` rather than typed, because
    // a literal here is right until the day the list changes shape — which is
    // what happened to this line twice in twelve days.
    const unitsStep = newConnectStepNumber("units");
    expect(unitsStep).not.toBeNull();
    expect(renderWizard(unitsStep as number).html).not.toContain('id="nc_prefix"');
    expect(renderWizard(1).html).not.toContain('id="nc_target"');
    expect(renderWizard(unitsStep as number).html).toContain('id="nc_target"');
  });

  it("BR-MET-112 on the wire — steps 1 to 7 make no write request of any kind", () => {
    for (const step of [1, 2, 3, 4, 5, 6, 7]) {
      const { urls } = renderWizard(step);
      // The ONLY request the wizard may make before the commit is the READ of
      // the published plans step 6 chooses from. Nothing may be created.
      for (const url of urls) {
        expect(url).toContain("/plans");
      }
      expect(urls.filter((url) => url.includes("/connections"))).toHaveLength(0);
    }
  });

  it("§5.4.10 step 1 — the owner BECOMES A CUSTOMER, and the badge says so (BR-MET-111 / DEF-650)", () => {
    const { html } = renderWizard(1);
    expect(html).toContain("Becomes a customer");
    // ⚠ **THE SENTENCE UNDER IT IS GONE AND THE BADGE IS THE WHOLE STATEMENT.**
    // *"These details create a customer record, which is what makes the owner
    // billable at the charges step…"* is RATIONALE, which B14 rule 33 gives
    // ZERO words on screen; it lives in `OwnerScopeStep`'s own comment now.
    expect(html).not.toContain("makes the owner billable");
  });

  it("§5.4.10 step 1 — the third mode is DISABLED with its reason, matching the backend's OQ-249 stub (BR-SHL-025)", () => {
    const { html } = renderWizard(1);
    // ⊕ **AMENDED 2026-09-29 (`CR-150-BRC09` `NCT-01`).** The drawing makes
    // `Work` a DROPDOWN whose third entry reads *We schedule it (disabled)*,
    // so the refusal moved from a dead button beside the control INTO the
    // control — which is `FieldOption.disabled`'s own documented purpose:
    // *"Present and unselectable beats absent (the user would never learn it
    // exists) and beats selectable (they would only learn on submit)."*
    //
    // ⚠ **NOTHING IS ENABLED BY THIS, WHICH IS WHAT THE CASE IS FOR.**
    // `_check_mode` still raises `NotImplementedError("OQ-249")` for this
    // value, so the option must carry `disabled` — and the assertion reads the
    // ATTRIBUTE on that option rather than the word beside it.
    const option = /<option[^>]*value="we_schedule"[^>]*disabled[^>]*>/.exec(html);
    expect(option).not.toBeNull();
    // ⚠ **THE PARAGRAPH IS DELETED, NOT SHORTENED.** *"Coming with the Work
    // module — crews, dispatch and scheduling are a later release."* is the
    // definition of B14 rule 33's RATIONALE — *why a control is absent* — at
    // zero words on screen, and the drawing lists it under *Removed from this
    // step*. It lives in `OwnerScopeStep`'s comment and in `OQ-249`.
    expect(html).not.toContain("Coming with the Work module");
    // The two real modes are both offered.
    expect(html).toContain('value="our_crew"');
    expect(html).toContain('value="external"');
  });

  it("§5.4.10 step 3 — the pattern produces 26 units, and the common area is NOT ticked by default", () => {
    // ⛔ **`BR-MET-1179` (PO 2026-09-21) — THE LAST LINE OF THIS CASE IS
    // REVERSED AND THE REST IS UNTOUCHED.** It asserted
    // `includeCommonArea === true`, copied from B18's own argument: *"Corridors,
    // car park, irrigation. It always exists and nobody remembers to add it."*
    // **That default is what the acceptance walk caught.** A clerk building a
    // HOUSE has no unit numbers to type, so they left `from`/`to` empty, carried
    // on, and committed **one common area and no dwelling at all** — with
    // nothing on screen saying it was wrong. B18's own drawing already rendered
    // the box UNTICKED; the prose beside it was read as the authority.
    //
    // ⚠ **OPTIONAL, NEVER PRE-SELECTED — AND NEVER FORBIDDEN.** The drawn build
    // below still makes its 26 units, because `drawnDraft()` TICKS the box, and
    // that is the point: the option is offered on every premise type and a
    // clerk who wants a shared unit gets one.
    const draft = drawnDraft();
    const units = draftUnits(draft);
    expect(units).toHaveLength(26); // 25 apartments + 1 common area — it foots
    expect(units[0].label).toBe("Apt 101");
    expect(units[24].label).toBe("Apt 125");
    expect(units[25].isCommonArea).toBe(true);
    expect(emptyDraft().pattern.includeCommonArea).toBe(false);
  });

  it("BR-MET-1179 — a fresh draft makes NO unit at all, rather than a lone common area", () => {
    // The trap, asserted as the shape it took rather than as a flag: an
    // untouched draft — a clerk who has typed nothing on step 3 — used to
    // expand to exactly one unit, and that unit was the common area. Step 3's
    // own `validate` then passed, because it counted UNITS. The wizard now
    // refuses a build with no DWELLING; this holds the half that feeds it.
    const units = draftUnits(emptyDraft());
    expect(units).toHaveLength(0);
    expect(units.some((unit) => unit.isCommonArea)).toBe(false);
  });

  // ════════════════════════════════════════════════════════════════════════
  // STEP 3 · THE TABLE ARRIVES FILLED IN (PO 2026-09-16)
  // ════════════════════════════════════════════════════════════════════════

  it("step 3 — every dwelling row arrives DEFAULTED to vacant and the common area to a dash", () => {
    const draft = drawnDraft();
    const units = draftUnits(draft);
    // BR-MET-116, PO 2026-08-25: *"unit will be all vacant right now"*. This is
    // what lets the commit open the owner's master account at all, so a default
    // of anything else puts BR-CUS-017's one-occupying-account guard back in
    // play two modules away from this screen.
    expect(occupancyOfUnit(draft, units[0])).toBe("vacant_service_off");
    expect(occupancyOfUnit(draft, units[24])).toBe("vacant_service_off");
    expect(units[25].isCommonArea).toBe(true);
    expect(occupancyOfUnit(draft, units[25])).toBeNull();

    // ⚠ **THE SURFACE MOVED IN THE 2026-09-28 FOLD AND THE FACT DID NOT.**
    // Step 3 absorbed *Map services* and *Work orders* (`CR-150-BRC09`), so
    // occupancy is a CELL of the shared table array rather than a column this
    // screen draws itself, and the table is GROUPED BY UNIT with only the
    // first group open. What is asserted is unchanged: the default is vacant,
    // and a common area gets a dash and no control.
    const html = renderUnits(draft);
    expect(html).toContain("Occupancy");
    // The open group's rows carry the occupancy control, defaulted to vacant.
    expect(html).toContain('data-cell="occupancy"');
    expect(html).toContain('value="vacant_service_off" selected');

    // ⚠ **ASSERT THE DASH AND THE ABSENT CONTROL, NOT AN ATTRIBUTE.** A first
    // draft of this case checked `data-occupancy="none"`, which the cell
    // emitted from `isCommonArea` alone — so deleting the dash branch entirely
    // left it GREEN. It was proved incapable of failing before it was
    // rewritten (CLAUDE.md law 7).
    const commonOnly = renderUnits(
      drawnDraft({ pattern: { prefix: "", from: "", to: "", includeCommonArea: true } }),
    );
    // One unit, the common area, and its occupancy cell is a dash with no
    // control inside it.
    expect(commonOnly).toContain(">\u2014<");
    expect(commonOnly).not.toMatch(/data-cell="occupancy"><select/);
  });

  it("step 3 — occupancy is PER UNIT: unit 4 can have a tenant while the rest do not", () => {
    // The case that could not be expressed at all before this column existed.
    const units = draftUnits(drawnDraft());
    const draft = drawnDraft({ unitOccupancy: { "Apt 104": "vacant_base_only" } });
    expect(occupancyOfUnit(draft, units[3])).toBe("vacant_base_only");
    expect(occupancyOfUnit(draft, units[0])).toBe("vacant_service_off");
    expect(occupancyOfUnit(draft, units[4])).toBe("vacant_service_off");
    // Only the moved unit is stored — a 26-unit build holds ONE entry.
    expect(Object.keys(draft.unitOccupancy)).toHaveLength(1);
  });

  it("step 3 — the review step's whole-build choice still SETS THEM ALL, and a per-unit answer outranks it", () => {
    const units = draftUnits(drawnDraft());
    const draft = drawnDraft({
      occupancy: "vacant_base_only",
      unitOccupancy: { "Apt 104": "vacant_service_off" },
    });
    // Every row the clerk did not touch follows the build.
    expect(occupancyOfUnit(draft, units[0])).toBe("vacant_base_only");
    // The one they did keeps what they said.
    expect(occupancyOfUnit(draft, units[3])).toBe("vacant_service_off");
    // And the common area is still not a thing a tenant can move into.
    expect(occupancyOfUnit(draft, units[25])).toBeNull();
  });

  it("step 3 — `DEF-CUS-9050` (PO 2026-10-02): two choices, and a parked retired one reads as its successor", () => {
    // *Open an account now* is removed and *Landlord-billed between tenants*
    // is merged into *Vacant · base charges only* — the owner's master account
    // pays an empty unit's base until a tenant moves in.
    expect(emptyDraft().occupancy).toBe("vacant_service_off");
    expect(emptyDraft().unitOccupancy).toEqual({});
    expect([...occupancyLabelCodes()].sort()).toEqual(["vacant_base_only", "vacant_service_off"]);
    expect(renderUnits(drawnDraft())).not.toContain("Open an account");
    const units = draftUnits(drawnDraft());
    const parked = drawnDraft({
      occupancy: "landlord_billed" as never,
      unitOccupancy: { "Apt 104": "open_account_now" as never },
    });
    expect(occupancyOfUnit(parked, units[0])).toBe("vacant_base_only");
    expect(occupancyOfUnit(parked, units[3])).toBe("vacant_service_off");
  });

  it("step 3's cell words and the signed choices are the SAME SET, so neither can drift", () => {
    // A code in one list and not the other renders an empty cell — visible to
    // nobody and asserted by nothing else.
    expect([...occupancyLabelCodes()].sort()).toEqual([...OCCUPANCY_CHOICES].sort());
  });

  // ════════════════════════════════════════════════════════════════════════
  // STEP 4 · THE GRID CARRIES THE ASSET, NOT A TICK (PO 2026-09-16)
  // ════════════════════════════════════════════════════════════════════════

  /** The six-unit build the blueprint draws, on the three services it draws. */
  const SIX: UnitPattern = { prefix: "", from: "1", to: "6", includeCommonArea: true };
  function sixUnitDraft(over: Partial<NewConnectDraft> = {}): NewConnectDraft {
    return drawnDraft({
      pattern: SIX,
      premiseServices: ["electric", "water", "sewer"],
      unitServiceGrid: {},
      ...over,
    });
  }
  /** The tenant's own thirteen, as `/lookups/asset_types` serves them. */
  const ASSET_TYPES = [
    { code: "meter", name: "Meter", category: "meters" },
    { code: "net_meter", name: "Net meter", category: "meters" },
    { code: "sub_meter", name: "Sub-meter", category: "sub_meters" },
    { code: "backflow", name: "Backflow preventer", category: "behind_the_meter" },
    { code: "pv", name: "PV / solar", category: "behind_the_meter" },
    { code: "container_cart", name: "Container / Cart", category: "behind_the_meter" },
    { code: "fire_line", name: "Fire service line", category: "behind_the_meter" },
  ];
  const METER_CODES = new Set(
    ASSET_TYPES.filter((row) => row.category === "meters").map((row) => row.code),
  );

  it("step 4 — a six-unit build is 21 rows: every unit inherits every premise service", () => {
    const draft = sixUnitDraft();
    const units = draftUnits(draft);
    expect(units).toHaveLength(7); // six dwellings + the common area
    const rows = gridRows(draft, units);
    // 7 units x 3 services. Nothing was ticked; inheritance filled it in.
    expect(rows).toHaveLength(21);
    expect(rows.every((row) => row.taken)).toBe(true);
    // ⚠ THE COMMON AREA'S LABEL IS `Common area`, NOT `CA`. p088's compressed
    // table draws `CA` and p089's grid draws `Common area`; the label is what
    // `units.label` is WRITTEN as, so the one the product already commits wins
    // and the drawing's two spellings are not reconciled on this screen.
    expect(
      rows.filter((row) => row.unit.label === COMMON_AREA_LABEL).map((row) => row.service),
    ).toEqual([
      "electric",
      "water",
      "sewer",
    ]);
  });

  it("step 4 — the counts are computed from the grid, never from the drawn figure", () => {
    const draft = sixUnitDraft();
    const rows = gridRows(draft, draftUnits(draft));
    const assetOf = (row: { service: string }) => SERVICE_ASSET_DEFAULT[row.service] ?? "";
    const orderOf = (row: { service: string }) => `tpl-${row.service}`;
    const counts = gridCounts(rows, METER_CODES, assetOf, orderOf);
    expect(counts.servicePoints).toBe(21);
    // Electric and water default to a meter; SEWER DEFAULTS TO NOTHING, which
    // is the point of `SERVICE_ASSET_DEFAULT` having no sewer entry - a meter
    // on every sewer connection would be seven jobs somebody has to cancel.
    expect(counts.meters).toBe(14);
    // DISTINCT TEMPLATES, because the commit raises one order per payload entry
    // and that entry names no unit (OQ-MET-12382).
    expect(counts.workOrders).toBe(3);
  });

  it("step 4 — INHERITANCE IS A DEFAULT, NOT A LOCK: the common area drops its sewer", () => {
    // The blueprint's own argument for this grid: *"It takes electric and water
    // and no sewer - there is nothing to drain from a hallway and a car park."*
    const draft = sixUnitDraft({
      unitServiceGrid: { [unitServiceKey(COMMON_AREA_LABEL, "sewer")]: { taken: false } },
    });
    const services = draftUnitServices(draft);
    expect(services[COMMON_AREA_LABEL]).toEqual(["electric", "water"]);
    // And no dwelling moved with it.
    expect(services["1"]).toEqual(["electric", "water", "sewer"]);
    const counts = gridCounts(
      gridRows(draft, draftUnits(draft)),
      METER_CODES,
      (row) => SERVICE_ASSET_DEFAULT[row.service] ?? "",
      () => "",
    );
    expect(counts.servicePoints).toBe(20); // 21 minus the common area's sewer
  });

  it("step 4 — sizes come from the TENANT's list, scoped to the service, and sewer has none", () => {
    // As `/lookups/service_size_classes` serves them since CR-065: a row names
    // its service, and NULL means *nobody has said* and lists everywhere.
    const served = [
      { code: "W-58", name: 'Water 5/8"', service: { id: "1", code: "water" } },
      { code: "W-34", name: 'Water 3/4"', service: { id: "2", code: "water" } },
      { code: "E-1P-200", name: "Electric 1\u03c6 200A", service: { id: "3", code: "electric" } },
      { code: "HOUSE-STD", name: "House standard", service: null },
    ];
    expect(sizesForService(served, "water").map((row) => row.code)).toEqual([
      "W-58",
      "W-34",
      "HOUSE-STD",
    ]);
    // BR-RAT-015 - sewer is a share of the water usage charge, reads no
    // register and has nothing to size. An untagged tenant row still lists.
    expect(sizesForService(served, "sewer").map((row) => row.code)).toEqual(["HOUSE-STD"]);
    expect(sizesForService([], "sewer")).toEqual([]);
  });

  it("step 4 — FIRE takes the FIRE LINE, by PO ruling (OQ-1361, 2026-10-02)", () => {
    // ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-10-02** — *"FIRE's asset
    // type is NOT decided here"*, because `OQ-1361`'s fire-line half was open
    // and a lane may not decide a device. The PO decided it, verbatim (decision
    // log *"THREE PO RULINGS IN ONE MESSAGE"* (2)): *"A · A fire service gets a
    // "fire line" item with a size (2" to 10"), like a trash cart. The clerk
    // picks the size on New Connection."* So a fire row offers exactly the
    // tenant's `fire_line`, and arrives on it, as a trash row arrives on a cart.
    expect(SERVICE_ASSET_TYPES.fire).toEqual(["fire_line"]);
    expect(assetTypesForService(ASSET_TYPES, "fire")).toEqual([
      { code: "fire_line", name: "Fire service line" },
    ]);
    expect(SERVICE_ASSET_DEFAULT.fire).toBe("fire_line");
    // Storm water is still absent, for a DIFFERENT reason and it is not a gap:
    // it is billed on area and no ratified asset type is a storm-water
    // connection.
    expect(assetTypesForService(ASSET_TYPES, "storm_water")).toEqual([]);
  });

  it("step 4 — solar and battery offer NO net meter (DEF-MET-9037, PO 2026-10-02)", () => {
    // *"we are not doing net metering right now - we are doing capacity based
    // panel - A · The net meter doesn't count toward capacity. Capacity is the
    // panels or battery only."*
    expect(assetTypesForService(ASSET_TYPES, "solar").map((row) => row.code)).toEqual(["pv"]);
    expect(SERVICE_ASSET_TYPES.solar).not.toContain("net_meter");
    expect(SERVICE_ASSET_TYPES.battery).not.toContain("net_meter");
    expect(takesAMeter("solar")).toBe(false);
    expect(takesAMeter("battery")).toBe(false);
    expect(takesAMeter("electric")).toBe(true);
  });

  it("step 4 — an asset type the tenant does not have is simply not offered", () => {
    // The map decides ORDER and OFFERING; the tenant's own list decides what
    // exists. A tenant with no carts cannot be given one.
    expect(assetTypesForService(ASSET_TYPES, "water").map((row) => row.code)).toEqual([
      "meter",
      "sub_meter",
      "backflow",
    ]);
    expect(assetTypesForService([], "water")).toEqual([]);
    // And the NAME a clerk reads is the tenant's, never the code.
    expect(assetTypesForService(ASSET_TYPES, "trash")[0].name).toBe("Container / Cart");
  });

  it("step 4 — the work order is matched on the template's OWN service, never on a name", () => {
    const proposed = [
      { template_id: "t1", name: "Set a water meter", service: { id: "1", code: "water" } },
      { template_id: "t2", name: "Energise", service: null },
    ] as unknown as Parameters<typeof orderForService>[0];
    expect(orderForService(proposed, "water")?.template_id).toBe("t1");
    expect(orderForService(proposed, "electric")).toBeNull();
  });

  it("an unreadable unit range produces NOTHING, never one unit", () => {
    // A wizard that answered an unreadable range with a single unit would build
    // a one-unit premises for a 25-unit development, silently.
    expect(expandUnitPattern({ prefix: "Apt", from: "", to: "", includeCommonArea: false })).toEqual(
      [],
    );
    expect(
      expandUnitPattern({ prefix: "Apt", from: "125", to: "101", includeCommonArea: false }),
    ).toEqual([]);
  });

  it("TC-NCT-1 — a single-unit build collapses to ONE row through the same screen", () => {
    // *"a house is a fast path through the same screen, not a second wizard"*
    // (§5.4.4 step 3). One row, no common area.
    const house = drawnDraft({
      pattern: { prefix: "", from: "1", to: "1", includeCommonArea: false },
    });
    expect(draftUnits(house)).toEqual([{ label: "1", isCommonArea: false }]);
  });

  it("TC-NCT-2 — 26 UNITS, and the ORDERS come from the utility's templates rather than from any arithmetic here", () => {
    // B18 asks for *"25 units and 7 work orders, not 76"*. The PO reframed that
    // on 2026-08-25: batching is NOT a system rule — *"utility users can issue
    // as many work order they want … they will develope these templats in work
    // order section"*. So this screen computes NO order count of its own.
    //
    // ⚠ **THE SENTENCE THIS CASE USED TO MATCH IS GONE, AND ON PURPOSE**
    // (CR-070 wave E, `US-WRK-017`). It read *"…Those templates are not built
    // yet, so no orders are proposed here"*, and it was true until the builder
    // landed on 2026-09-05. What replaces it says where the jobs come from and
    // that nothing is created until the last step — and the LIST beside it is
    // read from `GET /connections/proposed-work-orders`, which is the utility's
    // own published templates and not a rule in this file.
    const draft = drawnDraft();
    expect(draftUnits(draft)).toHaveLength(26);
    // ⊕ **AMENDED 2026-09-29 (`ed4e7cb30` — eight steps became five).** The
    // work orders were old step 5 · `plans`, which is absorbed into `units`
    // (step 3): `NewConnectPlansStep` is no longer mounted by the wizard and
    // the picker, the commit and `nc_target` all render from
    // `NewConnectUnitsStep` now. Only the STEP THIS RENDERS moved — every
    // assertion below is the one this case already made, and the point of it
    // is unchanged: this screen computes no order count of its own.
    const { html } = renderWizard(newConnectStepNumber("units") as number);
    // ⚠ **THE TWO SENTENCES THIS ASSERTED ARE GONE AND THE STEP IS RENAMED**
    // (`DEF-CUS-5482`, PO 2026-09-16). They read *"come from the templates your
    // utility has published"* and *"nothing is created until the last step"* —
    // both RATIONALE, which B14 rule 33 gives zero words on screen, and both
    // over the six-words-a-sentence cap. **Re-pointed rather than deleted**: a
    // red that names a SENTENCE reads like somebody tweaking wording, which is
    // how a true red acquires the protective colouring of a known one.
    //
    // What it asks now is the same thing through what the screen IS:
    //   · the step is named after work orders and no longer after the plan;
    //   · the proposal list is a read, so an empty one says so and offers the
    //     door to the templates screen (B14 rule 17);
    //   · the ADD control exists, which is the thing the PO asked for and the
    //     thing that did not exist at all.
    expect(html).toContain(">Work orders<");
    expect(html).not.toContain("All units on");
    expect(html).not.toContain("Common area on");
    expect(html).toContain('data-add-order="picker"');
    // ⊕ **AMENDED 2026-09-29 (`75b5841da`, `CR-150-BRC09` T3).** This line read
    // `data-add-order-commit=""` — the *Add work order* BUTTON beside the old
    // step-5 dropdown. Adding an order is ONE act now, not two:
    // `step3b-add-work-order.png` draws a template SEARCH whose `onChange`
    // adds the row, so `NewConnectUnitsStep` renders a
    // `RemoteSearchSelectField` and there is no separate commit button left to
    // find. **The question is re-asked, not dropped** — deleting it would
    // leave *"the ADD control exists"*, the thing the PO asked for and the
    // thing that did not exist at all, guarded by nothing. So both halves of
    // the new one-act control are pinned instead: the ACTION that opens the
    // picker, and the FIELD inside it that commits the choice.
    expect(html).toContain('data-array-action="add-work-order"');
    expect(html).toContain('id="nc_add_order"');
    expect(html).toContain('id="nc_target"');
    // Neither 7 nor 76 is claimed anywhere: the count on screen is however many
    // rows the read came back with, and this fixture's query is not primed.
    expect(html).not.toContain("7 orders");
    expect(html).not.toContain("76");
  });

  it("§5.4.10 step 4 — a unit can never take a service the street does not have", () => {
    // ⚠ **THE BREACH IS BUILT THE ONLY WAY A CLERK CAN REACH IT NOW.** Rows
    // inherit from `premiseServices`, so a unit cannot name an unavailable
    // service by drifting — it takes an EXPLICIT tick that the availability
    // list later loses. That is a real afternoon: tick gas on the grid, then
    // untick gas above. If this were derived from `premiseServices` alone the
    // refusal could never fire at all, which is a strip no clerk could ever see.
    const gasOnEveryDwelling: Record<string, { taken: boolean }> = {};
    for (const unit of expandUnitPattern(DRAWN_PATTERN)) {
      if (!unit.isCommonArea) {
        gasOnEveryDwelling[unitServiceKey(unit.label, "gas")] = { taken: true };
      }
    }
    const base = drawnDraft();
    const bad = drawnDraft({
      unitServiceGrid: { ...base.unitServiceGrid, ...gasOnEveryDwelling },
    });
    const breaches = availabilityBreaches(bad.premiseServices, draftUnitServices(bad));
    // 25 apartments × the one unavailable service.
    expect(breaches).toHaveLength(25);
    expect(breaches[0].service).toBe("gas");
    // The good draft breaches nothing.
    expect(availabilityBreaches(drawnDraft().premiseServices, draftUnitServices(drawnDraft()))).toEqual(
      [],
    );
  });

  it("TC-NCT-6 — sewer with no water on the unit is REFUSED, not warned", () => {
    // Every dwelling drops WATER and keeps sewer — one untick per unit on the
    // grid, which is exactly how a clerk would reach it.
    const noWater: Record<string, { taken: boolean }> = {};
    for (const unit of expandUnitPattern(DRAWN_PATTERN)) {
      if (!unit.isCommonArea) {
        noWater[unitServiceKey(unit.label, "water")] = { taken: false };
      }
    }
    const bad = drawnDraft({ unitServiceGrid: { ...drawnDraft().unitServiceGrid, ...noWater } });
    expect(sewerWithoutWater(draftUnitServices(bad))).toHaveLength(25);
    expect(sewerWithoutWater(draftUnitServices(drawnDraft()))).toEqual([]);
  });

  it("TC-NCT-7 — trash maps onto the common area and nothing refuses it (OQ-348 is CLOSED)", () => {
    const draft = drawnDraft();
    const services = draftUnitServices(draft);
    expect(services["Common area"]).toContain("trash");
    expect(services["Common area"]).toContain("storm_water");
    expect(availabilityBreaches(draft.premiseServices, services)).toEqual([]);
    // ⚠ AND NO CONTAINER COUNT IS COLLECTED. `BR-MET-104` puts the pricing
    // characteristic on the UNIT and `BR-MET-108` gives it a row — but WHICH
    // KEYS each flat service has is OQ-370, OPEN, so this wizard captures none
    // and invents no key name. The case's *"the step advances"* half holds; its
    // *"captured against the unit"* half is not built here.
    expect(takesAMeter("trash")).toBe(false);
    expect(takesAMeter("storm_water")).toBe(false);
    // ⚠ **`thermal_heat` ANSWERED `true` UNTIL 2026-09-07 AND NOW ANSWERS
    // `false` (`CR-080`).** The PO ruled it billed on connected tonnage rather
    // than on a meter, so a unit taking thermal gets no meter fitted — which
    // is a number a crew is sent to work to, not a label. Asserted beside the
    // two flat services rather than in a case of its own, because this is the
    // one question the family table answers.
    expect(takesAMeter("thermal_heat")).toBe(false);
    expect(takesAMeter("water")).toBe(true);
  });

  it("§5.4.10 step 5 — the WON'T COVER check is computed against the plan's own service list", () => {
    // *"Common area takes trash and storm water. Commercial Standard covers
    // both, but Residential Standard does not — do not apply it there."*
    expect(planCoverageGaps(["trash", "storm_water"], ["electric", "water", "sewer"])).toEqual([
      "trash",
      "storm_water",
    ]);
    expect(planCoverageGaps(["trash", "storm_water"], ["trash", "storm_water"])).toEqual([]);
    // ⚠ A PLAN WHOSE COVERAGE IS UNKNOWN WARNS ABOUT NOTHING. Returning "all
    // uncovered" would put a false red warning on every unit.
    expect(planCoverageGaps(["trash"], null)).toEqual([]);
  });

  it("§5.4.10 step 8 — the manifest is the drawn seven, and `Meters 50` foots", () => {
    const manifest = draftManifest(drawnDraft(), null);
    expect(manifest.customers).toBe(1); // BR-MET-111
    expect(manifest.premises).toBe(1);
    expect(manifest.units).toBe(26);
    // 25 electric + 25 water. Sewer adds none (derived), and the common area's
    // trash and storm water add none (flat) — §5.4.5's families doing the work.
    expect(manifest.meters).toBe(50);
    // ⚠ NOT ZERO. `commit_connection` answers `sub_meter_links: None` with a
    // stated reason, and the preview says what the commit will say.
    expect(manifest.subMeterLinks).toBeNull();
  });

  it("the manifest never invents a money figure — no quote means no total, not $0.00", () => {
    expect(draftManifest(drawnDraft(), null).oneTimeCharges).toBeNull();
    const { html } = renderWizard(8);
    // AMENDED 2026-09-28 (PO reported bug 1). The cell drew an em dash AND the
    // sentence "No quote on this build, so nothing is charged."; the drawing
    // lists that sentence under "Removed from this step". THE RULE THIS CASE
    // EXISTS FOR IS UNCHANGED and is asserted harder than before: an unpriced
    // build shows the dash and never a zero (hard rule 2, DEF-088, DEF-127).
    expect(html).not.toContain("No quote on this build");
    // ⊕ 2026-09-29 (`CR-150-BRC09` task 12) — the manifest table became the
    // *At a glance* strip, so the handle moved from `data-manifest-charges`
    // to the strip's own cell. **THE RULE IS UNCHANGED AND IS WHY THIS CASE
    // EXISTS**: an unpriced build shows the dash and never a zero (hard rule
    // 2, `DEF-088`, `DEF-127`).
    const from = html.indexOf('data-glance-value="one-time-charges"');
    expect(from).toBeGreaterThan(-1);
    expect(html.slice(from, html.indexOf("</div>", from))).toContain("\u2014");
    expect(html).not.toContain("$0.00");
    expect(html).not.toContain("14,435");
  });

  it("no drawn money figure is printed anywhere in the wizard (hard rule 2 · DEF-127)", () => {
    for (const step of [5, 6, 8]) {
      const { html } = renderWizard(step);
      expect(html).not.toContain("$150.00"); // the deposit policy — a tenant's
      expect(html).not.toContain("$762.50"); // 30.50 × 25 — priced by rating
      expect(html).not.toContain("$30.50");
    }
  });

  it("§5.4.10 step 8 — the four occupancy options are offered and `service off` is the default (BR-MET-105 survives)", () => {
    const { html } = renderWizard(8);
    // ⊕ 2026-09-29 (`CR-150-BRC09` task 12, `DEF-CUS-7613`) — **THE RADIO IS
    // NOT ON THE REVIEW STEP ANY MORE.** Occupancy is asked on the UNIT ROWS
    // at step 3 and the review SHOWS it without asking it, which is the PO's
    // own report: *"the information architecture is not grouped in logical
    // section and text is so much please reduce it"*.
    //
    // ⚠ **SO THIS CASE ASSERTS THE VOCABULARY AND THE DEFAULT, WHICH IS WHAT
    // `BR-MET-105` IS ABOUT, AND NOT THE CONTROL'S LOCATION.** All four
    // options still exist and the second is still the one that accrues the
    // `$30.50` base charge to the owner; a lane that quietly dropped one from
    // `OCCUPANCY_COPY` still goes red here. The screen shows the CHOSEN one.
    // ⛔ TWO since 2026-10-02 (`DEF-CUS-9050`, PO option A).
    expect(OCCUPANCY_COPY.map((row) => row.en)).toEqual([
      "Vacant · service off, billing nobody",
      "Vacant · base charges only",
    ]);
    expect(html).toContain("Vacant · service off, billing nobody");
    expect(emptyDraft().occupancy).toBe("vacant_service_off");
  });

  it("BR-MET-113 — the commit tags the quote to an owner ACCOUNT, and sends no float", () => {
    const plan = commitPlanOf(drawnDraft(), null);
    expect(plan.create_owner_account).toBe(true);
    expect(plan.units).toHaveLength(26);
    expect(plan.meters).toHaveLength(50);
    // Every meter goes out with NO number — step 9's own outstanding item 1,
    // *"50 meters still read 'to assign'"*. A serial invented here is a serial
    // nobody has.
    expect(plan.meters.every((meter) => meter.asset_no === null)).toBe(true);
    // Money is a STRING or null on the wire, never a number (hard rule 2).
    expect(plan.quote_total).toBeNull();
    expect(plan.mode).not.toBe("we_schedule");
  });

  it("§5.4.10 step 6 — the quote is COUNTED from the grid, and nothing is priced here", () => {
    // ⚠ **THIS CASE ASSERTED THE PREMISE THE PO REJECTED** (`DEF-CUS-5483`).
    // It required *"not re-priced here"* and *"There is no quote on this
    // build"* — a screen that renders a quote it is GIVEN, which means a build
    // raised directly can never be charged at all. p090 says the opposite in
    // red: *"Every quantity is counted from the services grid, not typed."*
    const { html } = renderWizard(6);

    // 1 · THE COUNTS ARE REAL AND COME OFF THE DRAWN 26-UNIT BUILD. This is the
    //     assertion the old screen could not have: a number that MOVES.
    // ⊕ 2026-09-29 (`CR-150-BRC09` task 11) — the *What is counted* table
    // became the context strip's `Counted` cell (units · meters · premises),
    // read from the SAME `quoteCounts` derivation. **THE RULE IS UNCHANGED**:
    // the quote is COUNTED from the grid and nothing is priced on this step.
    expect(html).toContain('data-context-value="counted"');
    const at = html.indexOf('data-context-value="counted"');
    expect(at).toBeGreaterThan(-1);
    const counted = html.slice(at, html.indexOf("</div>", at));
    // ⚠ **THREE NUMBERS, AND THE DERIVATION PROVED SEPARATELY — the two
    // halves are asserted in the two places that can each see one.**
    //
    // The CELL: three numbers rather than three dashes. It reads `0 · 0 · 0`
    // in this harness and that is CORRECT — the wizard mounts its own empty
    // draft, so there are no units, no meters and no premises to count. An
    // earlier draft of this line asserted *not all zero* and went red on a
    // true answer; a rendered count cannot tell an honest zero from a broken
    // one, which is exactly why the second half exists.
    //
    // The DERIVATION: `quoteCounts` on the drawn 26-unit build, which is the
    // number that MOVES and the thing `DEF-CUS-5483` was filed about.
    expect(counted).toMatch(/\d+ · \d+ · \d+/);
    const drawn = quoteCounts(drawnDraft());
    expect(drawn.units).toBeGreaterThan(0);
    expect(drawn.meters).toBeGreaterThan(0);
    expect(drawn.premises).toBe(1);

    // 2 · NO MONEY IS MULTIPLIED UP IN THIS BROWSER (hard rule 2, `DEF-088`,
    //     `DEF-BIL-5486`). The drawn figures are ILLUSTRATIONS (B14 rule 37)
    //     and none of them may appear — nor may any currency symbol, which is
    //     the assertion that fails if somebody later "helpfully" extends a line.
    expect(html).not.toContain("3,030");
    expect(html).not.toContain("1,950");
    expect(html).not.toContain("$");

    // 3 · WHO IS BILLED IS A LIVE RADIO GROUP AND THE CHOICE TRAVELS.
    // ⊕ 2026-09-29 (`CR-150-BRC09` task 11, `DEF-CUS-7610`) — *Who is billed*
    // is ONE select now instead of three radio cards, so the `data-billed-to`
    // attribute on the radiogroup is gone with them. **THE RULE IS UNCHANGED
    // AND IS ASSERTED HARDER:** the owner's account is the default AND the
    // only one of the three the product can honour, so the other two are
    // present and unselectable rather than absent (PO: *"this is wring -
    // keep previous options"*).
    expect(html).toContain('id="nc_quote_payer"');
    expect(html).toContain('value="each_unit_first_bill" disabled=""');
    expect(html).toContain('value="connection" disabled=""');
    // ⊕ `DEF-CUS-9212` (2026-10-02) — the master account is offered only to a
    // build that opens one (PO Q1). This harness mounts an EMPTY draft — no
    // owner, no units — which opens none, so the option is present and
    // refused; the enabled case is asserted on a built draft in
    // `NewConnectRedesignSteps45.dom.test.tsx`.
    expect(html).toContain('value="owner_account" disabled=""');
    // ⚠ **THE THREE `data-payer` LINES THAT STOOD HERE ARE RETIRED WITH THE
    // CARDS THEY DESCRIBED, AND THIS LANE LEFT THEM RED FOR ONE COMMIT.**
    // They read:
    //   `data-payer="each_unit_first_bill"` · `data-payer="connection"` ·
    //   `…="each_unit_first_bill" data-state="unselected" data-available="false"`
    // and their point was *both refused payers are DISABLED RADIOS, not divs
    // that swallow a click*. A `<select>` has no divs to swallow anything and
    // a `disabled` `<option>` is unselectable by keyboard and by mouse alike,
    // so the same guarantee is the `value="…" disabled=""` pair above — one
    // line per refused payer, by name.
    //
    // ⚠ **AND THE HALF THEY COULD NOT ASSERT IS NOW ASSERTED:** that the
    // owner's account is NOT disabled. The three cards could have been all
    // three unusable and passed every one of the retired lines.
    expect(html).not.toContain("data-payer=");

    // 4 · THE FIELD THAT TURNS THE MONEY PATH ON (`DEF-CUS-5485`). Without it
    //     every commit takes `quote_payment_terms_not_captured` and raises
    //     nothing, which is what every commit this product has made did.
    expect(html).toContain('id="nc_quote_due_days"');
    expect(html).toContain('id="nc_quote_posting_date"');

    // 5 · THE DRAWN PAYMENT CAPTURE IS BUILT, AND THIS CASE IS TURNED ROUND
    //     RATHER THAN DELETED (`DEF-CUS-7824`, 2026-09-29).
    //     It asserted `data-take-payment="not-built"` — the refusal that stood
    //     while no door accepted a payment at commit. `00d45f7ad` (2026-09-28,
    //     `DEF-CUS-7611`) landed the real control, so the refusal is gone and
    //     this case went red naming it. **That is the hold-expiry test working
    //     exactly as written** — the half that was missed is the other one:
    //     when you land a screen, grep for the control that was holding it.
    //     ⚠ AMENDED, NEVER DELETED. `DEF-REP-7640` is the precedent: three
    //     hold cases over `+ Build your own` were DELETED the day their hold
    //     expired, after which `grep -r buildYourOwn` across every test file
    //     returned zero and the button shipped pointing at nothing. A case
    //     that guards a door is re-aimed at the open door, so the door stays
    //     guarded. The live control's own behaviour is covered by
    //     `NewConnectPaymentTaken.dom.test.tsx`; this asserts the DOOR only.
    expect(html).not.toContain('data-take-payment="not-built"');
    // ⊕ 2026-09-29 (`CR-150-BRC09` task 11, `DEF-CUS-7611`) — *Take payment*
    // and *Method* were two controls and the drawing asks ONE, so the yes/no
    // is gone and the tender list IS the chooser. Its empty option is *No
    // payment now*, which is the drawn default. **THE RULE IS UNCHANGED**:
    // the step takes a payment at the counter, and the commit writes the
    // connection, the invoice and that payment in one act or nothing at all.
    expect(html).toContain('id="nc_payment_option"');
  });

  it("§5.4.10 step 7 — the `On creation` trigger is GONE (BR-MET-115, DEF-679)", () => {
    const { html } = renderWizard(7);
    // ⚠ **THE RULE IS UNCHANGED AND THE SENTENCES THAT CARRIED IT ARE GONE
    // (`0a1d0c0a`, 2026-09-16).** This asserted the wave-1 placeholder's prose —
    // *"Nothing is sent when the connection is created"*, *"marks the job
    // complete"*, *"no message kind for a connection"* — and step 7 is now the
    // drawn screen, so all three moved. **Re-pointed rather than deleted**: a
    // red that names a SENTENCE reads like somebody tweaking wording, which is
    // exactly how a true red acquires the protective colouring of a known one.
    //
    // What it asks now is the same two things, through what the screen states:
    //   · nothing is SENT — `BR-NOT-013`, no provider adapter on any channel;
    //   · `Unit energised` does not fire here — it is drawn `As each unit
    //     activates` and `BR-MET-115` moved it to the work-order screen, so it
    //     is absent from a table that is about what happens ON COMMIT.
    // AMENDED 2026-09-28 (PO reported bug 1). The strip carrying "Everything
    // is queued. Nothing is sent." is listed under "Removed from this step"
    // and is gone; the FACT it stated is on every row, in the State column,
    // which is what the two row assertions below and the stop-key assertion at
    // the foot of this case read. Nothing about BR-NOT-013 has changed.
    expect(html).not.toContain("Everything is queued. Nothing is sent.");
    expect(html).not.toContain("Unit energised");
    // ⚠ PIN THE SHAPE, or the `not.toContain` above passes over any page at all
    // — including a step 7 that failed to render (the vacuous pass this file's
    // own step-2 block was written against).
    // ⊕ 2026-09-29 (`CR-150-BRC09` task 13) — the messages table is the kit's
    // `TableArray` now, so a row is found by its cell rather than by a
    // `data-message` attribute on the `<tr>`. **THE RULE IS UNCHANGED**:
    // `BR-MET-115` moved `Unit energised` to the work-order screen and this
    // table is what happens ON COMMIT.
    expect(html).toContain('data-cell="message-build_created"');
    expect(html).toContain('data-cell="message-quote_and_what_is_owed"');
    // ⊕ `CR-164-BRC10` (`DEF-CUS-9198`, PO Q8) — every row says WHEN it goes,
    // and it is approval, never Create; the per-row state is what the screen
    // can know before Create (a template, or none).
    expect(html).toContain("On approval");
    expect(html).not.toContain("On commit");
    expect(html).toMatch(/data-message-state="(on-approval|no-template)"/);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// STEPS 5 AND 6 · `DEF-CUS-5482` · `DEF-CUS-5483` · `DEF-CUS-5485`
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **THESE ARE THE PREVENTIONS THE THREE ROWS PROMISED, AND EVERY ONE OF THEM
// ASKS ABOUT SOMETHING THAT WAS INVISIBLE TO EVERY OTHER CHECK HERE.** The
// wizard asked for the plan twice and the commit sent three fields as `null`
// forever: `tsc` passed, 39 cases passed, the commit answered 201 and the build
// was correct. Nothing went red because nothing was WRONG — something was
// simply missing, which is the shape `DEF-CUS-5468` already cost this file
// once. So the assertions are on the PAYLOAD KEYS and on the COUNTS, which are
// what can go absent again.
describe("S87 steps 5–6 · work orders, and the money the build is counted on", () => {
  it("counts the quote off the grid — 25 dwellings, 50 meters, one premise", () => {
    // The drawn build is `Apt 101–125` plus a common area: 25 dwellings on
    // electric/water/sewer and the common area on trash and storm water.
    // `per unit` counts DWELLINGS, because the common area is the `per premise`
    // line on p090's own table. `per meter` uses the same `takesAMeter` rule
    // `commitPlanOf` uses to build `meters`, so the screen and the payload
    // cannot come to disagree: electric and water are metered, sewer is derived
    // and trash and storm water are flat — 25 × 2 = 50.
    expect(quoteCounts(drawnDraft())).toEqual({ units: 25, meters: 50, premises: 1 });
    // ⚠ **AND IT MOVES WITH STEP 4, WHICH IS THE WHOLE CLAIM.** p090, in red:
    // *"change a tick on step 4 and these move with it."* A count that does not
    // move is a drawn figure wearing a variable's clothes.
    const withoutWater = drawnDraft({
      unitServiceGrid: drawnGrid(DRAWN_PATTERN, ["electric", "sewer"], ["trash", "storm_water"]),
    });
    expect(quoteCounts(withoutWater).meters).toBe(25);
  });

  it("carries the payer, the terms and the posting date into the commit", () => {
    // ⚠ **THIS IS `DEF-CUS-5485`.** `POST /connections/commit` has accepted all
    // three since `CR-109` and `commitPlanOf` sent NONE of them, so every real
    // commit took `quote_payment_terms_not_captured` and raised no charge at
    // all — over a money path proved on real PostgreSQL. Asserted by KEY,
    // because the failure mode is absence and absence is what nothing else sees.
    const plan = commitPlanOf(
      drawnDraft({ quotePayer: "owner_account", quoteDueDays: "30", quotePostingDate: "2026-09-20" }),
      null,
    );
    expect(plan.quote_payer).toBe("owner_account");
    expect(plan.quote_due_days).toBe(30);
    expect(plan.quote_posting_date).toBe("2026-09-20");
    // ⚠ **AN UNANSWERED TERM IS `null` AND IS NEVER A ZERO OR A GUESS.**
    // `BR-BIL-024` derives a due date from a cycle's days and a build's bill has
    // no cycle; the PO ruled on 2026-08-23 that a clerk captures the terms. A
    // guessed number starts a late-fee clock on a real customer's invoice.
    expect(commitPlanOf(drawnDraft(), null).quote_due_days).toBeNull();
    expect(commitPlanOf(drawnDraft(), null).quote_posting_date).toBeNull();
  });

  // ══════════════════════════════════════════════════════════════════════
  // BR-MET-1178 · A BUILD PRICES ITSELF (PO ruling 2026-09-21)
  // ══════════════════════════════════════════════════════════════════════
  //
  // PO, verbatim: *"…this request is new work and recognized seperately from
  // applcaition and hence we should not make it dependent on applciation #"*.
  //
  // ⚠ **WHAT THIS REPLACES.** Step 6 refused with *"No priced lines yet.
  // Charges are raised from an application."* and `commitPlanOf` sent the
  // application reference EMPTY on every build — so NO build made through this
  // wizard could ever raise a charge, and not one of the nine connections in
  // the demo tenant carries a quote total.
  describe("BR-MET-1178 — the build's own charge lines", () => {
    it("sends the code, the basis and a quantity COUNTED from step 4", () => {
      const plan = commitPlanOf(
        drawnDraft({
          quoteLines: [
            { chargeCode: "CONN", basis: "per unit" },
            { chargeCode: "METER-TEST", basis: "per meter" },
            { chargeCode: "INSPECT", basis: "per premise" },
          ],
        }),
        null,
      );
      // The drawn build is 26 dwellings plus a common area on five services,
      // and `quoteCounts` above already pins the same three numbers — so these
      // are read off the SAME arithmetic the screen shows, never a second one.
      const counts = quoteCounts(drawnDraft());
      expect(plan.quote_lines).toEqual([
        { charge_code: "CONN", quantity: counts.units, basis: "per unit" },
        { charge_code: "METER-TEST", quantity: counts.meters, basis: "per meter" },
        { charge_code: "INSPECT", quantity: counts.premises, basis: "per premise" },
      ]);
    });

    it("sends NO amount anywhere — hard rule 2 and BR-BIL-020", () => {
      // What crosses the wire is a COUNT. Billing reads the price off the
      // tenant's own charge row and multiplies; a figure computed here would be
      // the second rounding path the money rules exist to prevent.
      const plan = commitPlanOf(
        drawnDraft({ quoteLines: [{ chargeCode: "CONN", basis: "per unit" }] }),
        null,
      );
      expect(plan.quote_lines).toHaveLength(1);
      for (const line of plan.quote_lines) {
        expect(Object.keys(line).sort()).toEqual(["basis", "charge_code", "quantity"]);
      }
    });

    it("spells the basis the way BILLING spells it, with spaces", () => {
      // ⚠ **THIS CASE EXISTS BECAUSE THE FIRST DRAFT GOT IT WRONG.**
      // `fee_bill.BASIS_UNITS` keys on `"per unit"` · `"per meter"` ·
      // `"per premise"`; an underscored spelling is refused two modules away
      // with a message no clerk can act on, AFTER a build has been written.
      expect(BUILD_CHARGE_BASES).toEqual(["per unit", "per meter", "per premise"]);
      const plan = commitPlanOf(
        drawnDraft({ quoteLines: [{ chargeCode: "CONN", basis: "per unit" }] }),
        null,
      );
      expect(plan.quote_lines[0].basis).toBe("per unit");
    });

    it("drops a line that counts nothing rather than sending a free charge", () => {
      // A build with no units counts zero premises and zero meters. The server
      // refuses a zero BY NAME — a line priced $0.00 prints on a real
      // customer's bill as a charge that was free — so the screen never sends
      // one. ⚠ The POSITIVE half is asserted first, or this would pass over a
      // `quote_lines` that is empty for some entirely different reason.
      // ⚠ **THE POSITIVE HALF FIRST**, or this passes over a `quote_lines`
      // that is empty for some entirely different reason.
      expect(
        commitPlanOf(
          drawnDraft({ quoteLines: [{ chargeCode: "CONN", basis: "per unit" }] }),
          null,
        ).quote_lines,
      ).toHaveLength(1);
      // A fresh draft has the common area and no dwellings, so `per unit`
      // counts ZERO — pinned here, because the case is about the COUNT and an
      // assertion about the list alone could pass for any other reason.
      const noDwellings = {
        ...emptyDraft(),
        quoteLines: [{ chargeCode: "CONN", basis: "per unit" as const }],
      };
      expect(buildChargeQuantities(noDwellings)["per unit"]).toBe(0);
      expect(commitPlanOf(noDwellings, null).quote_lines).toEqual([]);
    });

    it("sends an EMPTY list when the clerk put no charge on the build", () => {
      // Lawful, and the server states the absence rather than counting $0.00.
      expect(commitPlanOf(drawnDraft(), null).quote_lines).toEqual([]);
    });
  });

  it("puts a work order the clerk added into the commit, with its version", () => {
    // ⚠ **`DEF-CUS-5482` — the list was REMOVE-ONLY.** A clerk who knew this
    // build needed a pole set had no way to say so. `BR-WRK-008` is *copy,
    // never link*, so the VERSION has to travel with the id or the order has
    // nothing to name the copy it was raised from.
    const added = {
      template_id: "t-pole-set",
      template_no: "WT-0044",
      name: "Pole set",
      service: { id: "s-e", code: "electric", name: "Electric" },
      scope: "premise",
      sequence: 3,
      job_type: null,
      is_gate: false,
      version: 4,
      est_duration_minutes: 90,
    };
    const plan = commitPlanOf(drawnDraft({ addedWorkOrders: [added] }), null, [added]);
    expect(plan.work_orders).toContainEqual({ template_id: "t-pole-set", template_version: 4 });
  });
});

// ══════════════════════════════════════════════════════════════════════════
// STEP 2 · THE PREMISE — `CR-094-BRC01` wave 2 lane G
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **THESE ARE THE PREVENTIONS `DEF-CUS-5468` AND `DEF-MET-5469` PROMISED,
// AND THEY EXIST BECAUSE AN ABSENCE IS INVISIBLE TO EVERY OTHER CHECK HERE.**
// The step asked for the whole address in one box, so every property the
// wizard built held NULL for city, state and postal_code — with `tsc` green,
// every test green and the commit answering 201. Nothing went red because
// nothing was wrong; something was simply missing. So the assertions are on
// the FIELDS BY ID and on the PAYLOAD KEYS, which is what can go absent again.
describe("S87 step 2 · the premise, as p087 draws it", () => {
  /** Step 2 with a catalogue ALREADY IN THE CACHE.
   *
   * ⚠ **SEEDING THE CACHE IS THE WHOLE POINT, NOT A SHORTCUT.**
   * `renderToStaticMarkup` is synchronous, so a `useQuery` that has to fetch
   * resolves AFTER the render and its data never reaches the HTML. A test that
   * asserts `not.toContain("$762.50")` over a screen whose plan never loaded
   * passes because nothing rendered at all — it is the *check that cannot
   * fail* shape, and the first draft of this block had it. Pre-filling the
   * cache makes the summary, the chips and the coverage warning render for
   * real, which is what makes their absences worth asserting.
   */
  function renderStep2(): { html: string; urls: string[] } {
    const urls: string[] = [];
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async (input) => {
        urls.push(String(input));
        return new Response(JSON.stringify({ count: 0, results: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    // The tenant sells FIVE of the platform's eleven. A screen holding its own
    // list would offer all eleven regardless — which is exactly how `fire`
    // reached position 11 and never appeared on the sign-up screen.
    queryClient.setQueryData(TENANT_SERVICES_KEY, [
      { service: "electric", name: "Electric", enabled: true },
      { service: "water", name: "Water", enabled: true },
      { service: "sewer", name: "Sewer", enabled: true },
      { service: "trash", name: "Trash", enabled: true },
      { service: "storm_water", name: "Storm water", enabled: true },
    ]);
    queryClient.setQueryData(newConnectPlansQueryKey, {
      count: 1,
      results: [
        {
          id: TEST_PLAN_ID,
          code: "RES-STD",
          name: "Residential Standard",
          status: "published",
          // Covers three of the five the drawn build offers, so WON'T COVER
          // has something TRUE to say about trash and storm water.
          services: ["electric", "water", "sewer"],
          effective_from: "2026-01-01",
        },
      ],
    });
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new?step=2`]}>
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
    return { html, urls };
  }

  /** The step rendered over a draft that has ALREADY chosen a plan, so the
   *  summary is on the screen.
   *
   *  ⚠ **THIS EXISTS BECAUSE THE MONEY CASE BELOW COULD NOT FAIL WITHOUT IT,
   *  AND THAT WAS PROVED RATHER THAN GUESSED.** `renderStep2` drives the whole
   *  wizard, which owns its draft and starts from `emptyDraft()` — where
   *  `planApartments` is `""`, so `chosenPlan` is null and the summary never
   *  renders at all. Pasting `$30.50/month × 25 = $762.50` straight into the
   *  summary left the suite GREEN. A `not.toContain` over a block that is
   *  never emitted is hard-won law 7's *structurally incapable of failing*,
   *  wearing the costume of a passing test. */
  function renderSummary(): string {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(TENANT_SERVICES_KEY, [
      { service: "electric", name: "Electric", enabled: true },
    ]);
    queryClient.setQueryData(newConnectPlansQueryKey, {
      count: 1,
      results: [
        {
          id: TEST_PLAN_ID,
          code: "RES-STD",
          name: "Residential Standard",
          status: "published",
          services: ["electric", "water", "sewer"],
          effective_from: "2026-01-01",
        },
      ],
    });
    return renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new?step=2`]}>
          <Routes>
            <Route
              path="/:tenant/connections/new"
              element={
                <PremiseStep
                  draft={drawnDraft({ planApartments: TEST_PLAN_ID })}
                  onPatch={() => undefined}
                  t={(key, params) => i18next.t(key, params)}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it("DEF-CUS-5468 — the address is FOUR fields and a name, not one box", () => {
    const { html } = renderStep2();
    for (const id of ["nc_address", "nc_city", "nc_state", "nc_zip", "nc_premise_name"]) {
      expect(html).toContain(`id="${id}"`);
    }
    // The drawn group headings, so a field cannot drift out of its group.
    // ⊕ **`Service address` BECAME `Address` ON 2026-09-29** — it is the
    // panel's own heading on `step2-premise.png`, and the group it used to
    // name is now the whole panel.
    expect(html).toContain("Address");
    expect(html).toContain("The record");
  });

  it("the drawn `Unit, apt. or suite` box is ENABLED and optional", () => {
    // ⊕ **REVERSED 2026-09-29 (`CR-150-BRC09` `NCT-01`), AND THE PO ASKED FOR
    // IT.** They questioned why the box was required and why it was disabled.
    // `step2-premise.png` answers both in its own *Changed 28 Sep* note:
    // *"Unit, apt. or suite is enabled and optional. It is part of the postal
    // address; unit labels stay on step 3."*
    //
    // ⚠ **THE OLD CASE IS NOT DELETED, IT IS INVERTED**, because the risk it
    // guarded is still real in the other direction: a box that silently
    // started CREATING a unit would break step 3's pattern. The postal line
    // and the unit labels stay two different things, and the help line says
    // which this is.
    const { html } = renderStep2();
    expect(html).toContain('id="nc_unit"');
    expect(html).not.toContain("Named on the next step");
    expect(html).toContain("Units are named on step 3.");
    const box = html.slice(html.indexOf('id="nc_unit"'));
    expect(box.slice(0, 400)).not.toContain("disabled");
  });

  it("DEF-MET-5469 — the commit CARRIES the town and the building's name", () => {
    const plan = commitPlanOf(
      drawnDraft({
        premise: {
          ...emptyDraft().premise,
          address: "212 Balcones Drive",
          name: "Balcones Tower",
          city: "Austin",
          state: "TX",
          postalCode: "78704",
          premiseType: "single_family",
        },
      }),
      null,
    );
    expect(plan.premises.name).toBe("Balcones Tower");
    expect(plan.premises.city).toBe("Austin");
    expect(plan.premises.state).toBe("TX");
    expect(plan.premises.postal_code).toBe("78704");
    // ⚠ **AND THE DOOR HAS A ROW FOR EVERY ONE OF THESE FOUR.**
    // `_premises_block_in_the_doors_language` REFUSES an unknown key by name
    // (`metering.connection.premises_field_unknown`), so a key added here
    // without its row in `PREMISES_BLOCK_FIELDS` does not get dropped — it
    // refuses the whole build. Measured red before the rows were added.
  });

  // ══════════════════════════════════════════════════════════════════════
  // DEF-CUS-6057 · A PICKED ADDRESS KEEPS WHAT IT OFFERS
  // ══════════════════════════════════════════════════════════════════════
  //
  // ⚠ **THE DEFECT WAS IN NEITHER SIDE OF THE SEAM, WHICH IS WHY NOTHING SAW
  // IT.** `address_picker.row()` served six honest fields and `pick()` wrote
  // four honest ones; the backend test asserted the six and the front-end
  // tests asserted the four, and both were true. **Nothing asked whether the
  // pair was enough to finish the wizard** — so choosing an address already on
  // file silently discarded what services it offers, the clerk's step-4 ticks
  // became a local fiction, and every meter was refused at the last press.
  //
  // These cases assert the SEAM: what a pick writes, given what the picker
  // hands over. `patchFromPickedPremises` is exported for exactly that reason.
  describe("DEF-CUS-6057 — picking an address keeps its service list", () => {
    const REGISTER_ROW = {
      id: "prm-7",
      premise_no: "PR-0731",
      address_line: "212 Balcones Drive",
      city: "Austin",
      state: "TX",
      postal_code: "78704",
      services_available: ["electric", "water", "sewer"],
      units: [],
    };

    it("carries the services the register holds for that address", () => {
      const patch = patchFromPickedPremises(emptyDraft(), REGISTER_ROW);
      expect(patch.premiseServices).toEqual(["electric", "water", "sewer"]);
      // …and still writes the whole address at once, which is what it always
      // did and is the half that must not regress.
      expect(patch.premise?.premisesId).toBe("prm-7");
      expect(patch.premise?.address).toBe("212 Balcones Drive");
      expect(patch.premise?.city).toBe("Austin");
      expect(patch.premise?.state).toBe("TX");
      expect(patch.premise?.postalCode).toBe("78704");
    });

    it("COPIES the list rather than sharing it, so the draft cannot edit the cache", () => {
      const patch = patchFromPickedPremises(emptyDraft(), REGISTER_ROW);
      // ⚠ **PIN THE VALUE FIRST.** `not.toBe` alone passes when the key is
      // ABSENT — `undefined` is not the array either — so on the broken code
      // this case stayed GREEN while the two beside it went red. A check that
      // passes on the defect it sits next to is law 7's *incapable of
      // failing*, and it was measured that way before this line was added.
      expect(patch.premiseServices).toEqual(REGISTER_ROW.services_available);
      expect(patch.premiseServices).not.toBe(REGISTER_ROW.services_available);
    });

    it("`null` leaves the clerk's own ticks alone — DEF-762, it is not `[]`", () => {
      // ⚠ **THE WHOLE POINT OF THE CONDITION.** SQL NULL means *nobody has
      // ever been asked about this address*. Writing `[]` from that would
      // blank a list the clerk had already ticked, on an address the register
      // simply has no opinion about — a second silent loss curing the first.
      const ticked = { ...emptyDraft(), premiseServices: ["electric"] };
      const patch = patchFromPickedPremises(ticked, {
        ...REGISTER_ROW,
        services_available: null,
      });
      expect("premiseServices" in patch).toBe(false);
      expect(patch.premise?.premisesId).toBe("prm-7");
    });

    it("a row that predates the field is read as `null`, never as empty", () => {
      const ticked = { ...emptyDraft(), premiseServices: ["electric"] };
      // A row from BEFORE the field existed: the key is ABSENT, not null. Built by
      // deleting it from a copy, because a destructure leaves an unused binding
      // the lint gate refuses (`DEF-CUS-9107`).
      const copy: Partial<typeof REGISTER_ROW> = { ...REGISTER_ROW };
      delete copy.services_available;
      const older = copy as Omit<typeof REGISTER_ROW, "services_available">;
      expect("premiseServices" in patchFromPickedPremises(ticked, older)).toBe(false);
    });

    it("an address that really offers NOTHING is written as nothing", () => {
      // `[]` IS an answer — *this address offers nothing* — and it must reach
      // the draft, or step 4 would go on showing a list the register denies.
      const ticked = { ...emptyDraft(), premiseServices: ["electric"] };
      const patch = patchFromPickedPremises(ticked, {
        ...REGISTER_ROW,
        services_available: [],
      });
      expect(patch.premiseServices).toEqual([]);
    });
  });

  it("an address PICKED out of the register is named, never re-created (hard rule 8)", () => {
    const picked = commitPlanOf(
      drawnDraft({
        premise: { ...emptyDraft().premise, premisesId: "abc-123", address: "500 Main Street" },
      }),
      null,
    );
    expect(picked.premises.id).toBe("abc-123");
    // And an unpicked build still creates one, or the search would have broken
    // the ordinary path.
    expect(commitPlanOf(drawnDraft(), null).premises.id).toBeNull();
  });

  it("the plan is asked HERE, and its summary carries NO monthly figure", () => {
    expect(renderStep2().html).toContain('id="nc_plan"');

    const summary = renderSummary();
    // ⚠ **THE POSITIVE ASSERTIONS COME FIRST AND THEY ARE LOAD-BEARING.** They
    // prove the summary is actually on the page, which is the only thing that
    // makes the three absences below capable of failing.
    expect(summary).toContain("Residential Standard");
    // ⊖ `DEF-CUS-9821` — the picker's `2026-01-01` is no longer echoed: the
    // redrawn block's *In force* reads the plan's own row, once it has loaded.
    expect(summary).toContain("data-plan-summary=\"RES-STD\"");

    // p087's sibling page prints `$30.50/month × 25 = $762.50`. Money is
    // rounded once, on the server (hard rule 2), and no endpoint publishes a
    // plan's base charge per unit to this screen — a figure multiplied up here
    // would be the second rounding path DEF-088 removed, printed beside real
    // ones.
    expect(summary).not.toContain("762.50");
    expect(summary).not.toContain("30.50");
    expect(summary).not.toContain("/month");
  });

  it("the service list comes from the TENANT, never from a list typed into the screen", () => {
    const { html } = renderStep2();
    // BR-MET-003 — a premises may offer only what this utility SELLS, and
    // `GET /settings/services` is the one place that answers which. The cache
    // above holds five; the platform has ELEVEN. A screen with its own list
    // would offer `fire` and `battery` to a tenant that sells neither.
    expect(html).toContain("Storm water");
    expect(html).toContain("Electric");
    expect(html).not.toContain(">Fire<");
    expect(html).not.toContain(">Battery<");
  });

  it("the coverage warning runs against THIS step's services and plan, and never blocks", () => {
    // The computation itself, over the pair step 2 now owns: the services the
    // premise offers and the plan chosen beside them. Trash and storm water
    // are offered and the plan prices neither.
    const offered = ["electric", "water", "sewer", "trash", "storm_water"];
    expect(planCoverageGaps(offered, ["electric", "water", "sewer"])).toEqual([
      "trash",
      "storm_water",
    ]);
    // ⚠ **A PLAN WHOSE COVERED SET IS UNKNOWN WARNS ABOUT NOTHING.** `null` is
    // *we were not told*, and returning "everything is uncovered" would put a
    // false red warning on every build.
    expect(planCoverageGaps(offered, null)).toEqual([]);
  });

});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W6 tasks 6.11 + 6.16 · B18 §5.4.7 (the nine TC-NCT cases) ·
//         §5.4.10 · BR-MET-111/112/113/115 · OQ-249 · OQ-370
// generated: 2026-08-25 by lane W6-SCREENS
// checklist: A=n/a B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions:
//   E3 **FOUR OF THE NINE `TC-NCT-*` CASES ARE HERE; THE OTHER FIVE ARE NOT,
//      AND EACH HAS AN ADDRESS.** TC-NCT-1, 2, 6 and 7 are screen behaviour and
//      are asserted above. **TC-NCT-3** (gas gates on the light-up, not the
//      meter set) and **TC-NCT-5** (a `failed` outcome raises a follow-up and
//      holds the connection) are service-layer rules with no screen able to
//      exercise them — no activation and no outcome endpoint is mounted.
//      **TC-NCT-4** and **TC-NCT-8** are rendering cases and are asserted in
//      `ConnectionDetailPage.test.tsx`, where the payload they describe is.
//      **TC-NCT-9** is a tenancy boundary and is already asserted where it can
//      actually be proved — `06-backend/tests/test_w6_connection_list.py`,
//      against a second tenant's rows. A screen test seeding its own fixture
//      cannot prove a tenant boundary and must not pretend to.
//   E3 TC-NCT-7's *"captured against the UNIT"* half is NOT built: which
//      characteristic keys a flat service has is OQ-370, OPEN, and this wizard
//      invents no key name.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

// ══════════════════════════════════════════════════════════════════════════
// PO 2026-09-21 · THE OWNER'S DOCUMENTS REACH A REAL DOOR
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS IS HARD-WON LAW 2 ASSERTED RATHER THAN HOPED FOR.** *Built is not
// wired.* A document-capture control whose files reached nothing would render
// perfectly, pass `tsc` and pass every other test in this file — four defects
// in one day were exactly that shape. So the upload is an INJECTED door and
// these cases watch it being called.
describe("PO 2026-09-21 — the owner's documents are filed after the commit", () => {
  function held(name: string) {
    return {
      id: `local-${name}`,
      docType: "contract",
      name,
      whatItProves: "",
      required: false,
      file: new File(["x"], name, { type: "application/pdf" }),
    };
  }

  it("uploads every held file against the account the commit opened", async () => {
    const calls: { accountId: string; name: string }[] = [];
    const outcome = await fileOwnerDocuments(
      [held("deed.pdf"), held("id.pdf")],
      { kind: "account", id: "acct-7" },
      async (accountId, doc) => {
        calls.push({ accountId, name: doc.name });
      },
    );
    expect(calls).toEqual([
      { accountId: "acct-7", name: "deed.pdf" },
      { accountId: "acct-7", name: "id.pdf" },
    ]);
    expect(outcome).toEqual({ filed: 2, unfiled: 0 });
  });

  it("files NOTHING and says how many, when the build opened no owner account", async () => {
    // ⚠ `create_owner_account` is OPT-IN (`BR-MET-1024`), so a clerk who
    // unticked it has nowhere for these to hang. **The count is what they are
    // told** — silence here is the failure this whole describe block is about.
    const calls: string[] = [];
    const outcome = await fileOwnerDocuments(
      [held("deed.pdf")],
      { kind: "premises", id: "prm-1" },
      async (_accountId, doc) => {
        calls.push(doc.name);
      },
    );
    expect(calls).toEqual([]);
    expect(outcome).toEqual({ filed: 0, unfiled: 1 });
  });

  it("one refusal does not stop the rest, and the count is honest", async () => {
    // The build is committed and immutable by the time this runs. A 415 on the
    // second file must not lose the first, nor the third.
    const outcome = await fileOwnerDocuments(
      [held("a.pdf"), held("b.exe"), held("c.pdf")],
      { kind: "account", id: "acct-7" },
      async (_accountId, doc) => {
        if (doc.name.endsWith(".exe")) {
          throw new Error("415");
        }
      },
    );
    expect(outcome).toEqual({ filed: 2, unfiled: 1 });
  });

  it("says NOTHING at all when the clerk brought no documents", async () => {
    // ⚠ `null` is not `{filed: 0}`. *They brought none* and *none of theirs
    // could be filed* are two different facts, and only one of them is worth a
    // sentence on a completion screen.
    expect(
      await fileOwnerDocuments([], { kind: "account", id: "acct-7" }, async () => undefined),
    ).toBeNull();
  });
});
