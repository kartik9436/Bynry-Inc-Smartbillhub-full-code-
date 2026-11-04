// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-039 wave C task 10 — *"a way to SET jurisdiction"*
// Defect:  DEF-517 (the column has no writer at any layer) · DEF-507 (the READ
//          half, whose own comment deferred the edit control)
// Screens: S16 (guided add, single-premise step) · PRM-01 (edit modal)
// Rules:   BR-RAT-101 (three states, `None` is not a default) · BR-RAT-102
//          (the surcharge this flag gates)
// ───────────────────────────────────────────────────────
// ⚠ **PROVED RED FIRST (2d).** Run with `JurisdictionField.tsx` present and
// neither form rendering it — `AddPremisesWizard.tsx` and `PremisesListPage.tsx`
// restored byte-for-byte from `0899de8` — this file reported **4 failed |
// 4 passed (8)**. The four that passed are the pure conversion functions, which
// is exactly the point: the component was BUILT and the screens did not USE it,
// so half a test file was green over a feature that did not exist (hard-won
// law 2). Verbatim from that run:
//
//     FAIL … > PRM-01's edit modal draws the three-state control
//     TestingLibraryElementError: Unable to find a label with the text of:
//     Jurisdiction
//
//     FAIL … > S16's payload carries the answer the clerk gave
//     AssertionError: expected undefined to be false // Object.is equality
//     - Expected:  false
//     + Received:  undefined
//
// The second failure is the one worth reading twice. `undefined` is what a
// payload key nobody added looks like — so before this change the wizard sent
// every hand-added premises at "nobody recorded it" whatever anyone typed,
// because there was nothing to type into.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { api } from "@/api/client";
import type { PremisesRow, PremisesType } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { addPremisePayload, emptyAddPremiseForm } from "@/features/metering/addPremise/addPremiseModel";
import type { AddPremiseForm } from "@/features/metering/addPremise/addPremiseModel";

/**
 * ⚠ `CR-177-BRC10` (2026-10-09): the old wizard's `singlePayload` is retired
 * with it. These cases ask the redesigned screen's payload builder the same
 * question, from the same fixture: the fixture's form is laid over an empty
 * one, a picked `master_account` becomes the LINKED owner, and `services: null`
 * (the old *never asked*) is an empty pick — the new screen always asks.
 */
function singlePayload(fixture: Record<string, unknown>): Record<string, unknown> {
  const picked = fixture.master_account as { id: string; account_no: string | null; name: string | null } | null | undefined;
  const form = {
    ...emptyAddPremiseForm(),
    ...(fixture as Partial<AddPremiseForm>),
    services: Array.isArray(fixture.services) ? (fixture.services as string[]) : [],
    custom_data: (fixture.custom_data as Record<string, unknown> | undefined) ?? {},
    unit_custom_data: (fixture.unit_custom_data as Record<string, unknown> | undefined) ?? {},
    service_point_custom_data:
      (fixture.service_point_custom_data as Record<string, Record<string, unknown>> | undefined) ?? {},
  } as AddPremiseForm;
  const owner =
    picked === null || picked === undefined
      ? null
      : {
          id: picked.id,
          account_no: picked.account_no,
          name: picked.name,
          account_type: "",
          account_type_name: null,
          party_kind: null,
          managed_by: null,
          status: "",
          status_name: null,
        };
  return addPremisePayload(form, { owner, addAnyway: false });
}
import {
  JURISDICTION_INSIDE,
  JURISDICTION_OUTSIDE,
  JURISDICTION_UNRECORDED,
  jurisdictionOption,
  jurisdictionPayloadValue,
} from "./JurisdictionField";
import { PremisesEditModal } from "./PremisesListPage";
import EN from "../../i18n/locales/en.json";

const TEST_TENANT = "brazosbend";

const TYPES: PremisesType[] = [
  { id: "t-1", code: "single_family", name: "Single family", active: true, is_system: true },
];

function premise(overrides: Partial<PremisesRow> = {}): PremisesRow {
  return {
    id: "p-101",
    premise_no: "P-11800",
    name: null,
    address_line: "4 Quarry Hill Rd",
    city: "Katy",
    state: "TX",
    postal_code: "77494",
    premises_type: "single_family",
    premises_type_name: "Single family",
    inside_city_limits: null,
    area_code: null,
    area_name: null,
    area_parent_code: null,
    area_path: null,
    services_available: null,
    master_account: null,
    owner_manager: null,
    external_ref: null,
    status: "active",
    unit_count: 1,
    ...overrides,
  } as PremisesRow;
}

function mountEdit(row: PremisesRow) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  queryClient.setQueryData(queryKeys.tenantServices, []);
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises`]}>
          <PremisesEditModal
            row={row}
            types={TYPES}
            client={api}
            onClose={() => undefined}
            onSaved={() => undefined}
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const SINGLE_FORM = {
  address_line: "1901 Bluestem Ln",
  city: "Katy",
  state: "TX",
  postal_code: "77494",
  premises_type: "single_family",
  area: { top: "", sub: "" },
  services: null,
  inside_city_limits: null as boolean | null,
  master_account: null,
  owner_manager: "",
  // `DEF-MET-5840` — the owner's account type. "" is the SHIPPED
  // answer: no account type chosen, so no owner account.
  owner_account_type: "",
  // `OQ-MET-12472` — the owner's kind and identifier, blank here on purpose:
  // no identity means no owner account, and the address still saves.
  owner_kind: "",
  owner_ssn: "",
  owner_driving_licence: "",
  owner_phone: "",
  owner_tax_id: "",
  external_ref: "",
  gis_parcel_id: "",
  // CR-089 wave A `PUJ-04` — the three answers the create form now
  // collects. `gis_unchecked: true` is the default: nobody has checked a
  // property that does not exist yet.
  lat: "",
  lng: "",
  gis_unchecked: true,
  // CR-089 wave B: `route` (B6, optional at creation) and `common_areas`
  // (B5, recorded while creating) join the form the wizard collects.
  route: "",
  common_areas: [],
  // CR-089 `p008` §5 — `How many units?` is a NUMBER now, so the two
  // booleans this replaced are gone rather than defaulted around.
  unit_count: "0",
  unit_type: "",
};

afterEach(cleanup);

// ── The conversion, in both directions ─────────────────────────────────────
//
// ⚠ These four assertions exist because a `<select>` yields STRINGS and
// `"false"` is truthy in JavaScript. One missing conversion between the option
// and the request body prices an inside-city address as outside — silently,
// because the value is well-formed at every step.


/**
 * **THE CONTROL'S VISIBLE NAME (`DEF-MET-4803`).**
 *
 * These three cases asked for `Jurisdiction` until 2026-09-10. `5ca82a824`
 * (2026-09-09, `CR-089` P4) renamed the label to the clerk's own words — the
 * blueprint's frame draws `City limits`, `CR-089-p019` row 5 — and **the
 * control, both its mount points and all three of its states are untouched**.
 * Only the word moved, and these three went red for a day saying
 * `Unable to find a label with the text of: Jurisdiction`, which reads like a
 * missing control rather than a renamed one.
 *
 * ⚠ **THE RENAME IS RIGHT AND THE ROW STILL DECIDES MONEY.** Inside or outside
 * the city picks whether a plan's surcharge multiplies every bill at this
 * address, so what these cases guard — that `null` never renders as an ANSWER —
 * matters exactly as much under the new word as the old one.
 */
const CITY_LIMITS_LABEL = "City limits";

describe("DEF-MET-4803 — the label this file asks for is the label the product draws", () => {
  it("the catalogue still calls the field what these cases ask for", () => {
    expect((EN as Record<string, string>)["metering.premises.field.jurisdiction"]).toBe(
      CITY_LIMITS_LABEL,
    );
  });
});

describe("CR-039 C10 — the three states survive the round trip", () => {
  it("stored → option, for all three states", () => {
    expect(jurisdictionOption(true)).toBe(JURISDICTION_INSIDE);
    expect(jurisdictionOption(false)).toBe(JURISDICTION_OUTSIDE);
    expect(jurisdictionOption(null)).toBe(JURISDICTION_UNRECORDED);
  });

  it("option → payload, for all three states", () => {
    expect(jurisdictionPayloadValue(JURISDICTION_INSIDE)).toBe(true);
    expect(jurisdictionPayloadValue(JURISDICTION_OUTSIDE)).toBe(false);
    expect(jurisdictionPayloadValue(JURISDICTION_UNRECORDED)).toBeNull();
  });

  it("an option nobody defined falls through to NOT RECORDED, never to outside", () => {
    // The only one of the three that adds no charge to anybody's bill. A
    // fall-through that guessed `false` would surcharge on a typo.
    expect(jurisdictionPayloadValue("Outside")).toBeNull();
    expect(jurisdictionPayloadValue("false")).toBeNull();
  });
});

// ── Wired, not merely built (hard-won law 2) ───────────────────────────────

describe("CR-039 C10 — both premises forms carry the control", () => {
  it("PRM-01's edit modal draws the three-state control", () => {
    mountEdit(premise());
    const control = screen.getByLabelText(CITY_LIMITS_LABEL);
    expect(control).toBeInTheDocument();
    // THREE options, and the empty one is real. A two-option control would be
    // a checkbox wearing a select's clothes.
    const options = Array.from(control.querySelectorAll("option")).map((o) => o.textContent);
    expect(options).toEqual(["Not recorded", "Inside city limits", "Outside city limits"]);
  });

  it("the edit modal re-opens on what the SERVER stored, not on a default", () => {
    mountEdit(premise({ inside_city_limits: false }));
    expect((screen.getByLabelText(CITY_LIMITS_LABEL) as HTMLSelectElement).value).toBe(
      JURISDICTION_OUTSIDE,
    );
  });

  it("an unrecorded premises opens on the empty option and NOT on 'Outside'", () => {
    mountEdit(premise({ inside_city_limits: null }));
    expect((screen.getByLabelText(CITY_LIMITS_LABEL) as HTMLSelectElement).value).toBe(
      JURISDICTION_UNRECORDED,
    );
  });

  it("S16's payload carries the answer the clerk gave", () => {
    expect(singlePayload({ ...SINGLE_FORM, inside_city_limits: false }).inside_city_limits).toBe(
      false,
    );
    expect(singlePayload({ ...SINGLE_FORM, inside_city_limits: true }).inside_city_limits).toBe(
      true,
    );
  });

  it("S16 sends NO key when the clerk did not answer", () => {
    // The column has no default, so an absent key and an explicit null say the
    // same thing to the server — and the absent key is the honest shape for a
    // question nobody touched.
    expect("inside_city_limits" in singlePayload(SINGLE_FORM)).toBe(false);
  });
});
