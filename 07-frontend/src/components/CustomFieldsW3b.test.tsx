// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 W3 (lane CF-W3b) — custom fields on premises, units,
//          service points and assets
// Defects: DEF-MET-9226 · DEF-MET-9227 · DEF-MET-9173 · DEF-AST-9171
// ───────────────────────────────────────────────────────
// The client halves the server cannot see: what each form SENDS (only what was
// typed, the first unit only, only services the units take), the review recap,
// the table column, and a refusal turned into the control's own sentence.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { CustomFieldRegistryEntry } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { addUnitsRequest, emptyAddUnitsForm } from "@/features/metering/AddUnitsWizard";
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
import { addPayload, initialAddValues } from "@/features/assets/AssetAddWizard";
import type { AssetTab } from "@/api/endpoints";

import { CustomFieldsAnswers, customFieldErrors, useCustomFieldColumns } from "./CustomFields";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const ROOF: CustomFieldRegistryEntry = {
  id: "cf-roof",
  key: "roof_material",
  label: "Roof Material",
  help_text: "",
  data_type: "select",
  options: ["Metal", "Tile"],
  is_required: true,
  display_order: 0,
  placement: { S16: "input", S14: "view" },
};

function withRegistry(
  node: React.ReactElement,
  seed: { entity: string; screen: string; mode: "input" | "view"; fields: CustomFieldRegistryEntry[] },
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.customFieldRegistry(seed.entity, seed.screen, seed.mode), seed.fields);
  return renderToStaticMarkup(<QueryClientProvider client={queryClient}>{node}</QueryClientProvider>);
}

const SINGLE = {
  address_line: "4410 Roofline Dr",
  city: "",
  state: "",
  postal_code: "",
  premises_type: "",
  area: { top: "", sub: "" },
  services: ["water", "electric"],
  inside_city_limits: null,
  master_account: null,
  owner_manager: "",
  owner_account_type: "",
  owner_kind: "",
  owner_ssn: "",
  owner_driving_licence: "",
  owner_phone: "",
  owner_tax_id: "",
  external_ref: "",
  gis_parcel_id: "",
  lat: "",
  lng: "",
  gis_unchecked: true,
  route: "",
  common_areas: [],
  unit_count: "2",
  unit_type: "",
};

describe("CR-161-BRC10 W3 — Add Premises sends what was typed, where it was typed", () => {
  it("DEF-MET-9226: a tenant with no fields posts exactly the payload it always did", () => {
    const payload = singlePayload(SINGLE);
    expect(payload).not.toHaveProperty("custom_data");
    expect((payload.units as Record<string, unknown>[])[0]).not.toHaveProperty("custom_data");
  });

  it("DEF-MET-9227/9173: the premises' answer, and the FIRST unit's own and its services'", () => {
    const payload = singlePayload({
      ...SINGLE,
      custom_data: { roof_material: "Metal" },
      unit_custom_data: { gate_code: "4471" },
      service_point_custom_data: {
        water: { valve_location: "Front curb" },
        // a service the address no longer offers is not sent
        gas: { valve_location: "Side" },
      },
    });
    const units = payload.units as Record<string, unknown>[];
    expect(payload.custom_data).toEqual({ roof_material: "Metal" });
    expect(units[0].custom_data).toEqual({ gate_code: "4471" });
    expect(units[0].service_point_custom_data).toEqual({ water: { valve_location: "Front curb" } });
    expect(units[1]).not.toHaveProperty("custom_data");
    expect(units[1]).not.toHaveProperty("service_point_custom_data");
  });
});

describe("CR-161-BRC10 W3 — Add units and Add asset", () => {
  it("DEF-MET-9227: Add units carries one set of answers onto the run, only when typed", () => {
    const plain = addUnitsRequest({ ...emptyAddUnitsForm("p-1"), units_per_floor: "2" });
    // Absent on the wire: an undefined key is not serialised.
    expect(JSON.stringify(plain)).not.toContain("custom_data");
    const typed = addUnitsRequest({
      ...emptyAddUnitsForm("p-1"),
      units_per_floor: "2",
      services: ["water"],
      custom_data: { gate_code: "9090" },
      service_point_custom_data: { water: { valve_location: "Basement" }, electric: { valve_location: "x" } },
    });
    expect(typed.pattern?.custom_data).toEqual({ gate_code: "9090" });
    expect(typed.pattern?.service_point_custom_data).toEqual({ water: { valve_location: "Basement" } });
  });

  it("DEF-AST-9171: Add asset sends custom_data only when something was typed", () => {
    const base = initialAddValues("meters" as AssetTab);
    expect(addPayload({ ...base, custom_data: {} })).not.toHaveProperty("custom_data");
    expect(addPayload({ ...base, custom_data: { warranty_provider: "Acme" } }).custom_data).toEqual({
      warranty_provider: "Acme",
    });
  });
});

describe("CR-161-BRC10 W3 — the recap, the column and the refusal", () => {
  it("Step 3 lists the answers under the field's label, and nothing for a tenant with none", () => {
    const html = withRegistry(
      <CustomFieldsAnswers entity="premises" screen="S16" values={{ roof_material: "Metal" }} />,
      { entity: "premises", screen: "S16", mode: "input", fields: [ROOF] },
    );
    expect(html).toContain("Roof Material");
    expect(html).toContain("Metal");
    expect(html).not.toContain("roof_material");
    const none = withRegistry(
      <CustomFieldsAnswers entity="premises" screen="S16" values={{}} />,
      { entity: "premises", screen: "S16", mode: "input", fields: [] },
    );
    expect(none).toBe("");
  });

  it("a list column per field switched on, its cell prefixed by the service it belongs to", () => {
    let columns: { key: string; label: string; cell?: (row: { v: Record<string, unknown> }) => unknown }[] = [];
    function Probe() {
      columns = useCustomFieldColumns<{ v: Record<string, unknown> }>({
        entity: "premises",
        screen: "S14",
        valuesOf: (row) => [{ prefix: "Water", values: row.v }],
      });
      return null;
    }
    withRegistry(<Probe />, { entity: "premises", screen: "S14", mode: "view", fields: [ROOF] });
    expect(columns.map((c) => c.label)).toEqual(["Roof Material"]);
    expect(columns[0].cell?.({ v: { roof_material: "Tile" } })).toBe("Water: Tile");
    expect(columns[0].cell?.({ v: {} })).toBe("");
  });

  it("a refused custom field becomes its control's own sentence; other fields are left alone", () => {
    const errors = customFieldErrors(
      [
        { field: "custom_data.roof_material", message_key: "customFields.required", params: {} },
        { field: "address_line", message_key: "metering.premises.address_required", params: {} },
        { field: null, message_key: "customFields.invalid" },
      ],
      t,
    );
    expect(errors).toEqual({ "custom_data.roof_material": t("customFields.required") });
  });
});
