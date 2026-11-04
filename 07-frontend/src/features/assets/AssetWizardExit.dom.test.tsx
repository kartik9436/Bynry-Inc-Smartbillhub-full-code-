// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-092-BRC01 step 2, wave C lane 2 — `AST-B-28` (Save as draft),
//          screens 24–26 and 28–32.
// Rules:   B19 §12.2 (`Save & exit` and `Park` are TWO controls, and
//          `Save & exit` *"leaves quietly and writes nothing of its own"*) ·
//          BR-SHL-025 (a control that cannot act is DISABLED CARRYING ITS
//          REASON — there is no boolean, so no consumer can disable it without
//          saying why) · BR-SHL-047 (every wizard parks) · BR-SHL-048 (a parked
//          wizard changes nothing until it is executed) · B14 rule 21 (both
//          wizards are on src/styles/route-b-migrated.txt)
// ───────────────────────────────────────────────────────
//
// **WHAT WAS WRONG, AND IT IS NOT WHAT THE SPECIFICATION SAID.** `AST-B-28`
// reads *"the button was drawn and saved nothing"*. That is true of the five
// CUSTOMER wizards. Here there was no button at all: **neither asset wizard
// passed `WizardFrame`'s optional `exit` prop**, so none of the four add steps
// and none of the three retire steps drew either control. A System Admin three
// steps into retiring the wrong meter had `← Back` and nothing that said
// *leave this*, while a clerk half way through a move-in had both.
//
// ⚠ **NOTHING COULD HAVE CAUGHT IT, AND THAT IS THE POINT.** An unset optional
// prop is exactly what an optional prop is for: `tsc` is happy, `G13` asks
// whether a declared prop is PASSED and these two never declared one, and every
// suite in this feature asserted what the steps contain rather than what the
// footer offers. It was found by reading the frame beside the screen.
//
// RED-FIRST PROOF (r11 step 2d), taken by reverting the `exit` object on each
// wizard in turn against the finished code:
//
//   add · Save & exit     → `Unable to find an accessible element with the role
//                            "button" and name "Save & exit"`
//   add · the refusal     → `Unable to find an element with the text: Drafts
//                            are not kept yet.`
//   retire · both cases   → the same two, on `/assets/a-4022/retire`
//   the hold-expiry case  → forced by adding "add_asset" to WIZARD_PARK_FLOWS:
//                            `expected [ 'move_in', … 'add_asset' ] not to
//                            contain 'add_asset'`
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";
import type { AssetDetail, LookupEntry } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { WIZARD_PARK_FLOWS } from "@/features/customers/wizardParkEndpoints";

import { AssetAddWizard } from "./AssetAddWizard";
import { AssetRetireWizard } from "./AssetRetireWizard";

afterEach(cleanup);

const t = (key: string): string => i18n.t(key);

function paged<T>(results: T[]) {
  return { results, page: 1, per: 200, total: results.length };
}

function lookup(code: string, name: string, category: string): LookupEntry {
  return { id: code, code, name, active: true, is_system: true, used_by: 0, category } as LookupEntry;
}

function Providers(props: { children: ReactNode; path: string; pattern: string }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(["lookups", "asset_types"], paged([lookup("meter", "Meter", "meters")]));
  queryClient.setQueryData(["lookups", "read_methods"], paged([]));
  queryClient.setQueryData(["lookups", "meter_types"], paged([]));
  queryClient.setQueryData(["lookups", "service_size_classes"], paged([]));
  queryClient.setQueryData(queryKeys.tenantServices, [
    { service: "water", name: "Water", enabled: true },
  ]);
  queryClient.setQueryData(["assets", "add-parent-picker"], paged([]));
  queryClient.setQueryData(["premises", "asset-add-picker"], paged([]));
  queryClient.setQueryData(["units", "asset-add-picker"], paged([]));
  queryClient.setQueryData(["assets", "detail", "a-4022"], RETIRABLE);
  queryClient.setQueryData(["assets", "retire-replacement-picker", "meters"], paged([]));
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* ⚠ MOUNTED UNDER THE REAL PATH PATTERN — a bare MemoryRouter leaves
            `useParams().tenant` undefined and every address the page builds
            comes out `//assets/…`, which reads as a good string to `toContain`
            (hard-won law 2). */}
        <MemoryRouter initialEntries={[props.path]}>
          <Routes>
            <Route path={props.pattern} element={props.children} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}

const RETIRABLE = {
  id: "a-4022",
  asset_no: "M-4022",
  type: "meter",
  type_name: "Meter",
  tab: "meters",
  status: "active",
  behavior_class: "in_service",
  actions: ["view", "retire"],
  multiplier: "1",
  unit: "kgal",
  install_date: "2024-03-12",
  // ⚠ **THE SHAPE IS COPIED FROM WHAT THE SERVER ANSWERS, NOT INVENTED.**
  // `valuation: null` crashed step 3 on `present_value` — a fixture the author
  // made up cannot tell a working screen from a broken one, which is the
  // lesson `WizardParkSubjectRef` records one module across.
  valuation: {
    supplier: null,
    purchase_cost: "164.0000",
    purchase_date: "2024-03-12",
    warranty_end: null,
    warranty_covered: false,
    depreciation_method: null,
    present_value: "144.1833",
    accumulated_depreciation: "19.8167",
    age_months: 29,
    life_months: 240,
    book_value_amount: null,
    book_value_treatment: null,
    currency: "USD",
  },
  lifecycle: {
    age_months: 29,
    expected_life_years: 20,
    certification_due: null,
    replacement_year: 2044,
  },
  linked_meter: null,
} as unknown as AssetDetail;

// ══════════════════════════════════════════════════════════════════════════
describe("AST-B-28 — both asset wizards have a way out that is not Back", () => {
  it("the ADD wizard draws Save & exit on its first step", () => {
    render(
      <Providers path="/brazosbend/assets/new?class=meters" pattern="/:tenant/assets/new">
        <AssetAddWizard timeZone="America/Chicago" today="2026-09-12" />
      </Providers>,
    );
    expect(screen.getByRole("button", { name: t("wizard.exit.saveAndExit") })).toBeInTheDocument();
  });

  it("the RETIRE wizard draws it too — its footer was one button", () => {
    render(
      <Providers path="/brazosbend/assets/a-4022/retire" pattern="/:tenant/assets/:assetId/retire">
        <AssetRetireWizard today="2026-09-12" />
      </Providers>,
    );
    expect(screen.getByRole("button", { name: t("wizard.exit.saveAndExit") })).toBeInTheDocument();
  });

  it("Park is offered, disabled, and carries its reason — never absent", () => {
    render(
      <Providers path="/brazosbend/assets/new?class=meters" pattern="/:tenant/assets/new">
        <AssetAddWizard timeZone="America/Chicago" today="2026-09-12" />
      </Providers>,
    );
    const park = screen.getByRole("button", { name: t("wizard.exit.park") }) as HTMLButtonElement;
    // BR-SHL-025 — there is no boolean on `WizardExit`, so a consumer cannot
    // refuse Park without saying why. Assert BOTH halves: a disabled control
    // with no sentence is the defect this rule exists for.
    expect(park.disabled).toBe(true);
    expect(screen.getByText(t("assets.wizard.parkBlocked"))).toBeInTheDocument();
    // The refusal is a CATALOGUE string and not a `defaultValue`: it is always
    // on screen, so a `defaultValue` would ship English to every tenant.
    expect(t("assets.wizard.parkBlocked")).not.toBe("assets.wizard.parkBlocked");
  });
});

// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE HOLD-EXPIRY GUARD — hard-won law 2's mirror, written in the same
// commit as the hold it guards.** *"When you write a hold, write the test that
// fires when the hold expires."*
//
// Park is refused on both asset wizards for two reasons that are facts about
// the STORE rather than about these screens:
//
//   1. `wizard_parks.flow` is a DATABASE CHECK CONSTRAINT over five values, so
//      `add_asset` and `retire_asset` are a MIGRATION rather than a client
//      change (decision log, 2026-09-12, in those words);
//   2. CR-035 AMENDMENT 1 puts a parked draft *"directly on each request"* tab
//      and the Assets registry has no Drafts home — screen 33 is drawn and
//      unbuilt. A draft nothing lists is a write nobody can read.
//
// The day somebody lands (1), this case goes RED and names the two `exit`
// objects that must stop refusing. Without it the refusal rots exactly the way
// `CR-068` R3's holds did: correct the day it was written, silently false the
// day the thing it pointed at arrived, with every check passing over it.
describe("AST-B-28 — the Park refusal cannot rot silently", () => {
  it("no asset flow is in the park store's vocabulary yet", () => {
    expect(WIZARD_PARK_FLOWS).not.toContain("add_asset");
    expect(WIZARD_PARK_FLOWS).not.toContain("retire_asset");
    // If either of the two above fails: the store now accepts asset drafts, so
    // `AssetAddWizard.tsx` and `AssetRetireWizard.tsx` must drop
    // `parkBlockedReason` and wire `useWizardPark`, and the Assets registry
    // needs the Drafts home (screen 33) for the draft to be findable.
  });
});
