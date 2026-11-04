// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-1900 — NO HUMAN-FACING SURFACE CAN RECORD A CONNECTION SIZE.
//          The screen half. `grep size_class 07-frontend/src/features/assets`
//          returned NOTHING on 2026-08-27: AST-05 had no field, AST-01/02 had
//          no field, and the only writer of BR-AST-500's column anywhere in
//          the product was the API validator.
// Ruling:  PO 2026-08-28, verbatim *"Please do both"* — a column in the meter
//          upload AND a field on the meter screen. 12-governance/
//          02-decision-log.md, "THE CONNECTION SIZE GETS BOTH DOORS".
// Rules:   BR-AST-530 (the screens offer the tenant's ratified list; METERS
//          only; blank stays lawful) · BR-AST-500 (the column — NULL is a real
//          answer and is never defaulted) · BR-AST-501 (billing-affecting) ·
//          BR-TEN-171 (the forty ratified codes) · BR-TEN-078 (the list is NOT
//          service-scoped) · B14 rule 21 (both files are on
//          src/styles/route-b-migrated.txt, so their utilities emit)
// Tests:   TC-D1..D13 (D10..D13 added 2026-09-01 for DEF-2414)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY A `.dom.test.tsx` AND NOT THE PROJECT'S USUAL STATIC RENDER.** The
// two doors this file proves are both reached by PRESSING something — step 2
// of a four-step wizard, and the edit form behind a row action. A
// `renderToStaticMarkup` suite can assert the pure halves beautifully and can
// never press a button, which is exactly how DEF-1900 stayed invisible: the
// existing backend cases write through `assets.services.update_asset`, so they
// prove the CAPABILITY and cannot prove the SURFACE.
//
// RED-FIRST PROOF (r11 step 2d), taken in a clean `git worktree` pinned to the
// branch base `db84bc6`, before this lane's change:
//
//   TC-D1 → `Unable to find a label with the text of: Connection size`
//   TC-D4 → the same, on the edit form
//
// and after the change, with the control's `values.klass === "meters"` guard
// deliberately deleted, TC-D3 went RED with
// `expected null not to be null` — the sub-meter boundary the ruling's fourth
// judgment draws is asserted, not assumed.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { api } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { AssetRow, LookupEntry } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { AssetAddWizard, addPayload, initialAddValues, offersConnectionSize } from "./AssetAddWizard";
import {
  assetTypesQueryKey,
  meterTypesQueryKey,
  readMethodsQueryKey,
  sizeClassesQueryKey,
} from "./AssetRegistryPage";
// `AST-B-12`: the edit form left the registry for its own page (AST-09). The
// form is the same form and these cases assert the same two doors; what moved
// is where it is imported from and that its lookups arrive through the query
// cache rather than as props.
import { AssetEditForm } from "./AssetEditPage";

afterEach(cleanup);

const t = (key: string): string => i18n.t(key);

/**
 * Three of BR-TEN-171's ratified water codes, in the order the PO was shown
 * them. ⚠ **REAL CODES, NOT INVENTED ONES** — the same discipline the backend
 * suite states at its own constant: a fixture that types `5/8` teaches a
 * reader a vocabulary the product does not have.
 */
const SIZES: LookupEntry[] = [
  lookup("W-58", 'Water 5/8"'),
  lookup("W-2", 'Water 2"'),
  lookup("W-4", 'Water 4"', false),
];

const TYPES: LookupEntry[] = [
  // ⚠ **THE CATEGORY IS LOAD-BEARING SINCE THE CASES DRIVE FROM STEP 1.**
  // `typesForTab` offers only the entries whose `category` IS the tab, so the
  // two measuring rows used to be unreachable here and nobody noticed: every
  // case mounted straight onto step 2, where the type picker is not rendered.
  { ...lookup("meter", "Meter"), category: "meters" } as LookupEntry,
  { ...lookup("sub_meter", "Sub-meter"), category: "sub_meters" } as LookupEntry,
  { ...lookup("container_cart", "Container / Cart"), category: "behind_the_meter" } as LookupEntry,
  { ...lookup("backflow", "Backflow preventer"), category: "behind_the_meter" } as LookupEntry,
];

/**
 * Two of BR-TEN-171's ratified TRASH codes — DEF-2414. ⚠ REAL CODES, the same
 * discipline the water constant above states: trash carries seven ratified
 * bands (35/64/96-gallon carts and 2/4/6/8 cu-yd dumpsters) and a fixture that
 * typed `96gal` would teach a vocabulary the product does not have.
 */
const TRASH_SIZES: LookupEntry[] = [
  lookup("CART-96", "Trash 96-gallon cart"),
  lookup("DUMP-4", "Trash 4 cu-yd dumpster"),
];

function lookup(code: string, name: string, active = true): LookupEntry {
  return { id: code, code, name, active, is_system: true, used_by: 0 };
}

function paged<T>(results: T[]) {
  return { results, page: 1, per: 200, total: results.length };
}

/**
 * The tenant's enabled services — `DEF-MET-4980`. `brazosbend` enables two of
 * the eleven the platform carries, and `gas` is here DISABLED so the picker's
 * filter is asserted rather than assumed.
 */
const SERVICES = [
  { service: "water", name: "Water", enabled: true },
  { service: "trash", name: "Trash", enabled: true },
  { service: "gas", name: "Gas", enabled: false },
];

/** One ACTIVE master, so a sub-meter can satisfy BR-AST-003 on step 1. */
const MASTERS = [
  {
    id: "m-1",
    asset_no: "M-MASTER-12",
    type: "meter",
    behavior_class: "in_service",
    net_metering: false,
    assigned_address: "1408 Bluestem Ln",
  },
];

function Providers(props: { children: ReactNode; path: string }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(["lookups", "asset_types"], paged(TYPES));
  queryClient.setQueryData(["lookups", "read_methods"], paged([lookup("ami", "AMI")]));
  queryClient.setQueryData(["lookups", "meter_types"], paged([lookup("ami", "AMI")]));
  queryClient.setQueryData(["lookups", "service_size_classes"], paged([...SIZES, ...TRASH_SIZES]));
  queryClient.setQueryData(queryKeys.tenantServices, SERVICES);
  queryClient.setQueryData(["assets", "add-parent-picker"], paged(MASTERS));
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[props.path]}>
          <Routes>
            <Route path="/:tenant/assets/new" element={props.children} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}

/**
 * Reach step 2 THE WAY A CLERK DOES — press through step 1.
 *
 * ⚠ **THIS USED TO MOUNT AT `?step=2` AND THAT ROUTE NO LONGER EXISTS FOR AN
 * UNTOUCHED FORM (`DEF-MET-4983`).** A step past the first, over a form nobody
 * has answered, is a reload that lost its answers: the wizard now sends the
 * person to step 1 and says so. Mounting deep would therefore have parked every
 * case below on step 1 — and TC-D3 and TC-D11, which assert an ABSENCE, would
 * have gone on PASSING while looking at the wrong screen. That is hard-won law
 * 7's *looking at the wrong thing*, and it is exactly how it arrives: not by
 * someone weakening a check, but by the screen moving under one.
 *
 * It is also what TC-D10 has said since it was written — *"DRIVEN FROM STEP 1,
 * not mounted on step 2 … a test that mounted on step 2 could never press the
 * thing this rule turns on"* — now true of the whole file.
 */
async function mountWizard(klass: string): Promise<void> {
  render(
    <Providers path={`/brazosbend/assets/new?class=${klass}&step=1`}>
      <AssetAddWizard timeZone="America/Chicago" today="2026-08-28" />
    </Providers>,
  );
  const type = klass === "meters" ? "meter" : klass === "sub_meters" ? "sub_meter" : "backflow";
  // ⚠ A SUBSTRING MATCH — the TYPE control is required, so its label carries
  // the marker beside the words and an exact match cannot associate it.
  await userEvent.selectOptions(
    screen.getByLabelText(new RegExp(t("assets.col.assetType"))),
    type,
  );
  if (klass === "meters" || klass === "sub_meters") {
    // `DEF-MET-4981` — a measuring class may not leave step 1 without one.
    await userEvent.selectOptions(
      screen.getByLabelText(new RegExp(t("assets.form.utilityService"))),
      "water",
    );
  }
  if (klass === "sub_meters") {
    // BR-AST-003. The parent picker is a `SearchSelectField` — a combobox over
    // a long list, not a native select — so it is OPENED and an option is
    // CLICKED, which is what a clerk does and what `selectOptions` cannot do.
    // ⚠ It opens on TYPING, never on click — `open` is set in `onChange` — and
    // one character leaves the debouncer's committed query empty, so the list
    // shows every option. That is the control's own mechanics, not a trick.
    await userEvent.type(
      screen.getByRole("combobox", { name: new RegExp(t("assets.add.parent")) }),
      "M",
    );
    await userEvent.click(await screen.findByRole("option", { name: /M-MASTER-12/ }));
  }
  await userEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));
  // ⚠ **PROVE THE RAIL ACTUALLY MOVED.** Without this, a step 1 that silently
  // refused to advance would leave every assertion below looking at the wrong
  // screen and the ABSENCE cases would pass for the wrong reason. `Back` is the
  // one control that exists on steps 2..4 and on no other, and it is the same
  // on the measuring and the device variants.
  await screen.findByRole("button", { name: t("wizard.back") });
}

describe("DEF-1900 door one — AST-05 records a connection size", () => {
  it("TC-D1: step 2 of the meters wizard offers the tenant's ratified sizes", async () => {
    await mountWizard("meters");
    const control = screen.getByLabelText(t("assets.col.sizeClass")) as HTMLSelectElement;
    const options = within(control)
      .getAllByRole("option")
      .map((option) => (option as HTMLOptionElement).value);
    // ⚠ THE ACTIVE ONES, AND THE EMPTY ONE. `W-4` is INACTIVE in the fixture
    // and must not be offerable — a size Settings retired is a size a new
    // meter may not be tagged with, even though BR-AST-500 keeps it on a meter
    // that already priced with it.
    expect(options).toContain("W-58");
    expect(options).toContain("W-2");
    expect(options).not.toContain("W-4");
    // Blank stays lawful (ruling judgment 2) — there IS an empty option, and
    // its label says "not recorded" rather than reading as an error.
    expect(options).toContain("");
    expect(control).not.toBeRequired();
  });

  it("TC-D2: the value is CHOSEN, never typed — it is a select, not a text box", async () => {
    await mountWizard("meters");
    const control = screen.getByLabelText(t("assets.col.sizeClass"));
    // Ruling judgment 1. Free text would put a forty-first code into the
    // pricing ladder by typo — a size nothing prices, on a meter that then
    // bills off the wrong rung with nobody told.
    expect(control.tagName).toBe("SELECT");
  });

  it("TC-D3: a SUB-METER wizard has no size control at all", async () => {
    await mountWizard("sub_meters");
    // Ruling judgment 4. A connection size describes the service connection a
    // meter sits ON, and a sub-meter sits BEHIND one — which is the half of
    // judgment 4 that has not moved and must not.
    //
    // ⚠ THIS COMMENT QUOTED THE RULING AS *"Sub-meters and devices are OUT"*
    // UNTIL 2026-09-01 (DEF-2414). Devices are no longer categorically out:
    // one that DECLARES A SERVICE stands on that connection, so it is offered
    // a size (TC-D10..D13). Sub-meters are unchanged, and for judgment 4's own
    // stated reason rather than by omission.
    expect(screen.queryByLabelText(t("assets.col.sizeClass"))).toBeNull();
  });

  it("TC-D4: what the operator chose reaches the create payload — and blank sends nothing", async () => {
    await mountWizard("meters");
    const control = screen.getByLabelText(t("assets.col.sizeClass"));
    await userEvent.selectOptions(control, "W-2");
    expect((control as HTMLSelectElement).value).toBe("W-2");
    // The pure half, asserted beside the rendered one so a control that draws
    // and does not travel (hard-won law 2 — built is not wired) goes RED here.
    const chosen = { ...initialAddValues("meters"), type: "meter", size_class: "W-2" };
    expect(addPayload(chosen)).toMatchObject({ size_class: "W-2" });
    // ⚠ BLANK SENDS NOTHING, not `null`: on a CREATE there is nothing to
    // clear, and BR-AST-500 makes "no size recorded" the state a new meter
    // legitimately starts in.
    expect(addPayload({ ...initialAddValues("meters"), type: "meter" })).not.toHaveProperty(
      "size_class",
    );
  });

  it("TC-D5: a sub-meter's payload never carries a size, even if one is in state", () => {
    // The boundary held in TWO places that cannot drift apart: the control is
    // not rendered, AND the payload builder refuses. A stale form is the only
    // way to reach this line, and it is refused rather than trusted.
    const stale = {
      ...initialAddValues("sub_meters"),
      type: "sub_meter",
      parent_asset_no: "M-4021",
      size_class: "W-2",
    };
    expect(addPayload(stale)).not.toHaveProperty("size_class");
  });
});


// ══════════════════════════════════════════════════════════════════════════
// DOOR THREE — THE EQUIPMENT THAT IS NOT A METER (DEF-2414)
// ══════════════════════════════════════════════════════════════════════════
//
// PO ruling 2026-09-01: *"we will ahve to set in seeder as well as in setting
// the sizes also on Units - so it works properly"*, confirmed the same day as
// *"this is correct - The size stays on the equipment record, not on the unit
// itself."*
//
// ⚠ **WHAT WAS WRONG, AND IT IS A BOUNDARY DRAWN ONE WORD TOO NARROW.**
// BR-AST-530's judgment 4 said METERS ONLY and gave a reason about POSITION —
// *"a sub-meter sits BEHIND a service connection rather than on one"*. A trash
// cart sits ON one; it IS the equipment the trash connection consists of, and
// its size is the connection's size (BR-RAT-090 prices trash by the count of
// those carts, and BR-RAT-1010 lets a charge code price per band). So the
// original REASON included it and the original WORDING excluded it, and no
// surface in the product could record a cart's size at all.
//
// The predicate is `offersConnectionSize` in `assetsShared`, in ONE place
// because judgment 4 asked for exactly that — it named four sites that must not
// drift, and four copies of `=== "meters"` could not drift while the rule was
// one word long. It has two clauses now, so they call it instead of copying it.

describe("DEF-2414 door three — a container on a connection records its size", () => {
  it("TC-D10: a device that DECLARES A SERVICE is offered the ratified sizes", async () => {
    // ⚠ DRIVEN FROM STEP 1, not mounted on step 2 like TC-D1, and that is the
    // case rather than a detail of it: the SERVICE is named on step 1 and it is
    // what decides whether step 2 offers a size at all. A test that mounted on
    // step 2 could never press the thing this rule turns on.
    render(
      <Providers path="/brazosbend/assets/new?class=behind_the_meter&step=1">
        <AssetAddWizard timeZone="America/Chicago" today="2026-09-01" />
      </Providers>,
    );
    // ⚠ A SUBSTRING MATCH, because the TYPE control is REQUIRED and its label
    // therefore carries the required marker beside the words — an exact match
    // finds the text and cannot associate the control.
    await userEvent.selectOptions(
      screen.getByLabelText(new RegExp(t("assets.col.assetType"))),
      "container_cart",
    );
    // ⚠ **THIS TYPED `trash` INTO A TEXT BOX UNTIL `DEF-MET-4980`.** The
    // control is a `SelectField` over `GET /settings/services` filtered to the
    // tenant's ENABLED set, so the answer is chosen — which is the whole point:
    // `watr` used to reach the server and come back 422 three steps later.
    await userEvent.selectOptions(
      screen.getByLabelText(new RegExp(t("assets.form.utilityService"))),
      "trash",
    );
    await userEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));
    const control = (await screen.findByLabelText(
      t("assets.col.sizeClass"),
    )) as HTMLSelectElement;
    const options = within(control)
      .getAllByRole("option")
      .map((option) => (option as HTMLOptionElement).value);
    expect(options).toContain("CART-96");
    // BR-TEN-078 — the list is NOT service-scoped, so the water bands are still
    // offered. That is the PO's own ruling and this case must not quietly
    // re-scope it while widening something else.
    expect(options).toContain("W-58");
    expect(options).not.toContain("W-4"); // inactive, never offerable
    expect(options).toContain(""); // blank stays lawful (BR-AST-500)
    expect(control).not.toBeRequired();
    expect(control.tagName).toBe("SELECT"); // chosen, never typed
  });

  it("TC-D11: a device that declares NO service is offered nothing", async () => {
    // The rendered half: step 2 of a BTM wizard with no service named draws no
    // size control at all — a thing in the yard has no connection to be sized.
    await mountWizard("behind_the_meter");
    expect(screen.queryByLabelText(t("assets.col.sizeClass"))).toBeNull();
    // A backflow preventer, an EV charger and a comms endpoint belong to a
    // CUSTOMER, not to a connection (BR-AST-009 — a non-measuring device
    // carries no service). Testing the TYPE instead would hardcode
    // `container_cart` and answer wrongly for the next non-measuring thing that
    // stands on a connection — storm water's and broadband's equipment, both
    // `capacity` services under the PO ruling of 2026-09-01 (DEF-2409).
    expect(offersConnectionSize({ ...initialAddValues("behind_the_meter") })).toBe(false);
    expect(
      offersConnectionSize({
        ...initialAddValues("behind_the_meter"),
        type: "backflow",
        service: "   ",
      }),
    ).toBe(false);
  });

  it("TC-D12: what the operator chose reaches the create payload", () => {
    // Hard-won law 2 — a control that draws and does not travel is dead UI.
    const cart = {
      ...initialAddValues("behind_the_meter"),
      type: "container_cart",
      service: "trash",
      size_class: "CART-96",
    };
    expect(addPayload(cart)).toMatchObject({ size_class: "CART-96", service: "trash" });
    // Blank sends NOTHING on a create — there is nothing to clear.
    expect(
      addPayload({ ...cart, size_class: "" }),
    ).not.toHaveProperty("size_class");
    // And a stale size on a serviceless device is refused, not trusted: the
    // payload builder holds the same boundary the control renders on.
    expect(
      addPayload({ ...cart, service: "", size_class: "CART-96" }),
    ).not.toHaveProperty("size_class");
  });

  it("TC-D13: an existing container's size can be corrected on the edit form", async () => {
    mountEditForm("behind_the_meter", {
      type: "container_cart",
      type_name: "Container / Cart",
      meter_type: null,
      service: "trash",
      size_class: "CART-96",
    });
    const control = (await screen.findByLabelText(
      t("assets.col.sizeClass"),
    )) as HTMLSelectElement;
    // It opens showing what is stored, never a default (BR-AST-500).
    expect(control.value).toBe("CART-96");
  });
});


// ══════════════════════════════════════════════════════════════════════════
// DOOR TWO — THE SIZE ON A METER THAT IS ALREADY ON FILE (S51 · AST-02)
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **WHY THE CONTROL IS ON THE EDIT FORM AND NOT ON `AssetDetailPage`, WHICH
// IS THE SCREEN THE RULING NAMES.** AST-01/02's Specifications panel is a
// read-only `<dl>` — it has no edit affordance of any kind, and `updateAsset`
// has exactly one caller in the whole frontend, this form behind the registry's
// row action. So the ruling's *"a field on the meter screen"* lands as TWO
// halves rather than one: the detail panel SHOWS the size (TC-D9, and its
// absence is a sentence rather than a dash), and the form a person reaches
// from the row's pencil RECORDS it. Putting an input into the read-only panel
// would have been a second write path for one column, which is how two screens
// come to disagree about one fact. Recorded in the decision log rather than
// decided quietly.

const REGISTRY_TYPES: LookupEntry[] = [
  { ...lookup("meter", "Meter"), category: "meters" } as LookupEntry,
  { ...lookup("sub_meter", "Sub-meter"), category: "sub_meters" } as LookupEntry,
  { ...lookup("container_cart", "Container / Cart"), category: "behind_the_meter" } as LookupEntry,
];

function row(over: Partial<AssetRow> = {}): AssetRow {
  return {
    id: "a-4021",
    asset_no: "M-4021",
    serial_no: "3894-A2210",
    type: "meter",
    type_name: "Meter",
    tab: "meters",
    status: "active",
    status_name: "Installed/Active",
    behavior_class: "in_service",
    meter_type: "ami",
    meter_type_name: "AMI",
    read_method: "ami",
    read_method_name: "AMI",
    multiplier: "1.000000",
    // BR-AST-500 — the state every meter loaded before today is in.
    size_class: null,
    // The size AS A CLERK READS IT, beside the code (`DEF-AST-7130`).
    size_class_name: null,
    unit: "gal",
    net_metering: false,
    manufacturer: "Itron",
    model: "OpenWay",
    install_date: "2024-03-12",
    parent_asset_no: null,
    service_point_id: "sp-1",
    assigned_unit_id: "u-101a",
    assigned_to: "Unit A",
    assigned_address: "1408 Elm Street",
    assigned: true,
    test_due: false,
    retire_date: null,
    retire_reason: null,
    replaced_by: null,
    actions: ["view", "edit"],
    service: "water",
    sub_count: 0,
    last_read: null,
    parent_premises: null,
    export_capacity_kw: null,
    warranty_end: null,
    next_test: null,
    ...over,
  };
}

function mountEditForm(
  tab: "meters" | "sub_meters" | "behind_the_meter",
  over: Partial<AssetRow> = {},
): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(readMethodsQueryKey, paged([lookup("ami", "AMI")]));
  queryClient.setQueryData(sizeClassesQueryKey, paged([...SIZES, ...TRASH_SIZES]));
  // The two the registry used to hand down as props.
  queryClient.setQueryData(assetTypesQueryKey, paged(REGISTRY_TYPES));
  queryClient.setQueryData(meterTypesQueryKey, paged([lookup("ami", "AMI")]));
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/assets"]}>
          <AssetEditForm
            asset={row({ tab, type: tab === "meters" ? "meter" : "sub_meter", ...over })}
            client={api}
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("DEF-1900 door two — an existing meter's size can be corrected", () => {
  it("TC-D6: the edit form offers the tenant's ratified sizes, active ones only", async () => {
    mountEditForm("meters");
    const control = (await screen.findByLabelText(
      t("assets.col.sizeClass"),
    )) as HTMLSelectElement;
    const options = within(control)
      .getAllByRole("option")
      .map((option) => (option as HTMLOptionElement).value);
    expect(options).toContain("W-58");
    expect(options).toContain("W-2");
    // A size Settings RETIRED is not offerable on a NEW tagging, even though
    // BR-AST-500 keeps it on a meter that already priced with it.
    expect(options).not.toContain("W-4");
  });

  it("TC-D7: a meter with no size recorded opens on the empty option, never a default", async () => {
    mountEditForm("meters", { size_class: null });
    const control = (await screen.findByLabelText(
      t("assets.col.sizeClass"),
    )) as HTMLSelectElement;
    // ⚠ THE ONE THAT MATTERS ON A MIGRATION. Defaulting here would invent a
    // connection size for 1,847 meters at once, and every one of them would
    // then price off a rung nobody chose.
    expect(control.value).toBe("");
  });

  it("TC-D8: a meter that HAS a size opens showing it", async () => {
    mountEditForm("meters", { size_class: "W-2" });
    const control = (await screen.findByLabelText(
      t("assets.col.sizeClass"),
    )) as HTMLSelectElement;
    expect(control.value).toBe("W-2");
  });

  it("TC-D9: a SUB-METER's edit form has no size control, and still has its meter type", async () => {
    mountEditForm("sub_meters");
    // Ruling judgment 4, held on the edit door as well as the create door. The
    // meter-type assertion is the guard against a FALSE pass: without it this
    // case would go green on a form that failed to render at all.
    expect(await screen.findByLabelText(t("assets.col.meterType"))).toBeInTheDocument();
    expect(screen.queryByLabelText(t("assets.col.sizeClass"))).toBeNull();
  });
});
