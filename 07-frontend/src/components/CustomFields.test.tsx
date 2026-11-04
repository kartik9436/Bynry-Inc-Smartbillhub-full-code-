// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-015 (capture custom fields on input screens) · US-SHL-016
//           (display them, and include them in exports)
//           Screens: S16 · S18 · S21 · S49 · S50 · S51
// Rules:    BR-SHL-036 (one control per data type) · BR-SHL-037 (the existing
//           envelope, keyed `custom_data.<key>`) · BR-SHL-038 (available,
//           never default; unsorted in R2) · BR-SHL-039 (CSV columns headed
//           with the label, IS-11 formats) · BR-TEN-048 (never a money input)
// ───────────────────────────────────────────────────────
// The load-bearing test in this file is TC-4: a tenant with NO fields renders
// NOTHING — not an empty section, not a heading, not a spacer. That is the one
// a careless implementation gets wrong, and the one a user notices as a gap in
// the middle of a form they use every day.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { CustomFieldRegistryEntry } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";

import {
  CustomFieldsInput,
  CustomFieldsView,
  displayValue,
  fieldErrorId,
} from "./CustomFields";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const isoDate = (iso: string): string => {
  const [y, m, d] = iso.split("-");
  return `${m}/${d}/${y}`; // stand-in for the tenant's IS-8 formatter
};

function field(over: Partial<CustomFieldRegistryEntry> = {}): CustomFieldRegistryEntry {
  return {
    id: "cf-1",
    key: "feeder_number",
    label: "Feeder Number",
    help_text: "",
    data_type: "text",
    options: [],
    is_required: false,
    display_order: 0,
    placement: { S51: "input", S50: "view" },
    ...over,
  };
}

const POLE_TAG = field({
  id: "cf-2",
  key: "pole_tag",
  label: "Pole Tag",
  display_order: 1,
});

function render(
  node: React.ReactElement,
  seed: { entity: string; screen: string; mode: "input" | "view"; fields: CustomFieldRegistryEntry[] },
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(
    queryKeys.customFieldRegistry(seed.entity, seed.screen, seed.mode),
    seed.fields,
  );
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>{node}</QueryClientProvider>,
  );
}

describe("US-SHL-015 — capture", () => {
  it("US-SHL-015 TC-1: both fields render in display order under a tenant heading", () => {
    const html = render(
      <CustomFieldsInput
        entity="assets"
        screen="S51"
        values={{}}
        onChange={() => undefined}
        tenantName="Brazos Bend Utilities"
      />,
      { entity: "assets", screen: "S51", mode: "input", fields: [field(), POLE_TAG] },
    );
    expect(html).toContain(
      t("customFields.sectionHeading", { tenant: "Brazos Bend Utilities" }),
    );
    expect(html.indexOf("Feeder Number")).toBeLessThan(html.indexOf("Pole Tag"));
  });

  it("US-SHL-015 TC-2: a select renders its defined options in the defined order", () => {
    const html = render(
      <CustomFieldsInput
        entity="accounts"
        screen="S18"
        values={{ service_class: "Commercial" }}
        onChange={() => undefined}
      />,
      {
        entity: "accounts",
        screen: "S18",
        mode: "input",
        fields: [
          field({
            key: "service_class",
            label: "Service Class",
            data_type: "select",
            options: ["Residential", "Commercial", "Irrigation"],
          }),
        ],
      },
    );
    expect(html.indexOf("Residential")).toBeLessThan(html.indexOf("Commercial"));
    expect(html.indexOf("Commercial")).toBeLessThan(html.indexOf("Irrigation"));
  });

  it("US-SHL-015 TC-3: the control's id is the key the SERVER keys its errors by", () => {
    // BR-SHL-037 — no second error path is invented; FormModal's existing
    // context finds the control because the id matches `custom_data.<key>`.
    expect(fieldErrorId("feeder_number")).toBe("custom_data.feeder_number");
    const html = render(
      <CustomFieldsInput
        entity="assets"
        screen="S51"
        values={{}}
        onChange={() => undefined}
      />,
      { entity: "assets", screen: "S51", mode: "input", fields: [field({ is_required: true })] },
    );
    expect(html).toContain('id="custom_data.feeder_number"');
    expect(html).toContain('aria-required="true"');
  });

  it("US-SHL-015 TC-4: a tenant with no fields renders NOTHING AT ALL", () => {
    const html = render(
      <CustomFieldsInput
        entity="assets"
        screen="S51"
        values={{}}
        onChange={() => undefined}
        tenantName="Lone Star Ridge Water Co-op"
      />,
      { entity: "assets", screen: "S51", mode: "input", fields: [] },
    );
    // Not an empty <section>, not a heading, not a spacer — the empty string.
    expect(html).toBe("");
  });

  it("BR-SHL-036: one control per data type, and a number is NOT a money control", () => {
    const html = render(
      <CustomFieldsInput
        entity="assets"
        screen="S51"
        values={{}}
        onChange={() => undefined}
      />,
      {
        entity: "assets",
        screen: "S51",
        mode: "input",
        fields: [
          field({ key: "multiplier", label: "Multiplier", data_type: "number" }),
          field({ key: "ada_flag", label: "ADA flag", data_type: "boolean" }),
          field({ key: "installed_on", label: "Installed on", data_type: "date" }),
        ],
      },
    );
    expect(html).toContain("<select"); // boolean: a Yes / No choice (DEF-SHL-9240)
    expect(html).toContain("YYYY-MM-DD"); // date, stored ISO whatever the UI shows
    // BR-TEN-048: no MoneyCell, no currency, no grouping anywhere near it.
    expect(html).not.toContain("money");
  });
});

describe("US-SHL-016 — display and export", () => {
  it("US-SHL-016 TC-1: view placements render read-only in display order", () => {
    const html = render(
      <CustomFieldsView
        entity="assets"
        screen="S50"
        values={{ feeder_number: "F-12", pole_tag: "P-8842" }}
        formatDate={isoDate}
      />,
      { entity: "assets", screen: "S50", mode: "view", fields: [field(), POLE_TAG] },
    );
    expect(html).toContain("F-12");
    expect(html).toContain("P-8842");
    expect(html).not.toContain("<input"); // read-only, not a disabled form
    expect(html.indexOf("F-12")).toBeLessThan(html.indexOf("P-8842"));
  });

  it("US-SHL-016 TC-4: a missing value is an EMPTY cell — never null, None or undefined", () => {
    expect(displayValue(field(), {}, isoDate, t)).toBe("");
    expect(displayValue(field(), { feeder_number: null }, isoDate, t)).toBe("");
    const html = render(
      <CustomFieldsView entity="assets" screen="S50" values={{}} formatDate={isoDate} />,
      { entity: "assets", screen: "S50", mode: "view", fields: [field()] },
    );
    expect(html).not.toContain("null");
    expect(html).not.toContain("undefined");
  });

  it("US-SHL-016 TC-5: a date reads the tenant format on screen and ISO in the export", () => {
    const dateField = field({ key: "installed_on", data_type: "date" });
    const values = { installed_on: "2026-03-04" };
    expect(displayValue(dateField, values, isoDate, t)).toBe("03/04/2026");
    // The STORED value stays ISO-8601 — which is what a CSV export will carry
    // when that half is built, and is the same string the BILL prints
    // (BR-TEN-082). Storage is one thing; rendering is three.
    expect(values.installed_on).toBe("2026-03-04");
  });

  it("BR-TEN-048: a number is rendered verbatim — never grouped, never rounded", () => {
    const numberField = field({ key: "legacy_id", data_type: "number" });
    // BR-TEN-082's own ratified literal: `10432`, not `10,432`.
    expect(displayValue(numberField, { legacy_id: "10432" }, isoDate, t)).toBe("10432");
    expect(displayValue(numberField, { legacy_id: "1.5" }, isoDate, t)).toBe("1.5");
  });

  it("a multi-select renders in the tenant's stored order", () => {
    const notes = field({
      key: "site_notes",
      data_type: "multi_select",
      options: ["Locked gate", "Dog on site"],
    });
    // BR-TEN-082's fourth literal: `Locked gate, Dog on site`.
    expect(
      displayValue(notes, { site_notes: ["Locked gate", "Dog on site"] }, isoDate, t),
    ).toBe("Locked gate, Dog on site");
  });



  it("US-SHL-016 TC-8: a tenant with no fields renders no custom section at all", () => {
    const html = render(
      <CustomFieldsView entity="assets" screen="S50" values={{}} formatDate={isoDate} />,
      { entity: "assets", screen: "S50", mode: "view", fields: [] },
    );
    expect(html).toBe("");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-015@a1c9f04 (story+rules snapshot over EP-SHL-07-custom-field-rendering.md)
// generated: 2026-08-15 by story-coder (tenant custom-fields lane)
// checklist: A✔ B✔ C✔ D=deferred(the server halves live in the pytest suite) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest — see the lane report, including the checks proved RED first
// exceptions: US-SHL-016's LIST-COLUMN (BR-SHL-038) and CSV (BR-SHL-039) halves are NOT BUILT and have no tests here — the helpers for them were written and then DELETED rather than left green and uncalled; see the block in CustomFields.tsx for the two changes each half needs and which lane owns them · the BOOLEAN screen rendering (`Yes`/`No` from the catalogue, so a Spanish user reads Sí/No while the BILL prints English) and the DATE format divergence between screen, bill and CSV are both UNRATIFIED readings on BR-TEN-082 — asserted here as BEHAVIOUR so a change goes RED, and FLAGGED rather than settled
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
