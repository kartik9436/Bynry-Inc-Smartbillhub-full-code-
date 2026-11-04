// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-014 (card + management view) · US-TEN-015 (define a field) ·
//           US-TEN-016 (placement) · US-TEN-017 (deactivate only)
//           Screens: S8
// Rules:    BR-TEN-047 (inside the Reference-data framework, no new screen ID) ·
//           BR-TEN-049 (`key` immutable) · BR-TEN-050 (deactivate only) ·
//           BR-TEN-051 (cap 10 active per entity) · BR-TEN-052 (placement is
//           platform-bounded) · BR-SHL-035 (one shell)
// ───────────────────────────────────────────────────────
// The load-bearing tests here are the two that would go green on a broken
// build if they were written the obvious way:
//   · BR-TEN-050 — that NO delete control is rendered. Asserted on the rendered
//     markup, not on a config flag, because a Delete button added later would
//     leave the flag alone.
//   · BR-TEN-047 — that the custom-fields card opens inside the SAME
//     SettingsFrame every other Reference-data card opens in.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  CustomFieldDefinition,
  CustomFieldEntitySlots,
  CustomFieldSlot,
  LookupCard,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { REFERENCE_CARDS, referenceCard, referenceCardViews } from "./referenceDataConfig";
import { ReferenceDataTab } from "./SettingsReferenceData";
import * as settingsCustomFields from "./SettingsCustomFields";
import {
  ACTIVE_CAP_PER_ENTITY,
  CUSTOM_FIELD_DATA_TYPES,
  DefinitionModal,
  PlacementModal,
  activeCountFor,
  choicesFor,
  modeForSlot,
  offeredEntities,
  parseOptions,
  previewKey,
  screensFor,
  slotGroups,
} from "./SettingsCustomFields";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function definition(over: Partial<CustomFieldDefinition> = {}): CustomFieldDefinition {
  return {
    id: "cf-1",
    entity: "assets",
    key: "feeder_number",
    label: "Feeder Number",
    help_text: "",
    data_type: "text",
    options: [],
    is_required: false,
    is_active: true,
    is_document_safe: false,
    placement: { S51: "input", S50: "view" },
    placement_count: 2,
    display_order: 0,
    eligible_slots: { input: ["S50", "S51"], view: ["S49", "S50"] },
    slots: [],
    input_route: "screen",
    ...over,
  };
}

/** A slot exactly as `GET /settings/custom-fields/slots` serves one. */
function slot(over: Partial<CustomFieldSlot> = {}): CustomFieldSlot {
  return {
    key: "S18",
    screen: "new_account",
    route: "clerk_input",
    modes: ["input"],
    presentation: "form",
    rendered: true,
    wave: "W1",
    ...over,
  };
}

/** The two account screens that render today (`custom_fields.SLOTS`). */
const ACCOUNT_SLOTS: CustomFieldSlot[] = [
  slot(),
  slot({ key: "S21", screen: "account_detail", modes: ["input", "view"], presentation: "page" }),
];

function renderPlacement(field: CustomFieldDefinition): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <PlacementModal
        client={undefined as never}
        field={field}
        onClose={() => undefined}
        onSaved={() => undefined}
      />
    </QueryClientProvider>,
  );
}

function renderCustomFields(rows: CustomFieldDefinition[], readOnly = false): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const cards: LookupCard[] = [
    { list: "uoms", owner: "tenancy", count: 6, state: "seeded" },
    {
      list: "custom_fields",
      owner: "tenancy",
      count: rows.filter((r) => r.is_active).length,
      state: "seeded",
    },
  ];
  queryClient.setQueryData(queryKeys.lookupCards, cards);
  queryClient.setQueryData(queryKeys.customFields("||"), rows);
  // The served slot list (CR-161-BRC10 W1) — the filter's record types come
  // from here, never from a client copy.
  queryClient.setQueryData(
    queryKeys.customFieldSlots(),
    ["premises", "units", "service_points", "assets", "accounts", "contacts", "addresses", "service_agreements"].map(
      (entity) => ({ entity, import_columns: false, offered: true, slots: [] }),
    ),
  );
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/settings?tab=reference&list=custom_fields"]}>
          <ReferenceDataTab readOnly={readOnly} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-TEN-014 — the custom-fields card and management view", () => {
  it("US-TEN-014 TC-1: the grid carries a Custom fields card", () => {
    const codes = REFERENCE_CARDS.map((card) => card.code);
    expect(codes).toContain("custom_fields");
    // BR-TEN-047: no new screen ID is minted — it is a card in S8's own grid.
    expect(referenceCard("custom_fields")?.kind).toBe("custom");
    expect(referenceCard("custom_fields")?.owner).toBe("tenancy");
  });

  it("US-TEN-014 TC-1: the card keeps its place and its live count from the server", () => {
    const views = referenceCardViews([
      { list: "uoms", count: 6 },
      { list: "custom_fields", count: 4 },
    ]);
    const card = views.find((view) => view.card.code === "custom_fields");
    expect(card?.count).toBe(4);
    // Appended after the account lists, which is where the S8 capability row
    // puts it ("fixed card order (appended after Account statuses)").
    const order = REFERENCE_CARDS.map((c) => c.code);
    expect(order.indexOf("custom_fields")).toBeGreaterThan(order.indexOf("account_statuses"));
  });

  it("US-TEN-014 TC-2/TC-3: the table renders label, key, entity and type", () => {
    const html = renderCustomFields([
      definition(),
      definition({
        id: "cf-2",
        entity: "accounts",
        key: "service_class",
        label: "Service Class",
        data_type: "select",
        options: ["Residential", "Commercial", "Irrigation"],
        placement: { S18: "input" },
        placement_count: 1,
        eligible_slots: { input: ["S18", "S21"], view: ["S21"] },
      }),
    ]);
    expect(html).toContain("Feeder Number");
    expect(html).toContain("feeder_number");
    expect(html).toContain("Service Class");
    expect(html).toContain(t("settings.customFields.entity.assets"));
    expect(html).toContain(t("settings.customFields.type.select"));
  });

  it("DEF-1701: the declared entity and status filters RENDER — they were config-only", () => {
    // ⚠ **THE SIBLING OF THE SCREEN THE PO PHOTOGRAPHED.** This config has
    // declared `filters: [entity, status]` since US-TEN-014 and never passed
    // `DataTable`'s `filterBarSlot`, so TC-4's "an entity filter with no
    // matches lands on the empty state" described a filter no user could set.
    // Hard-won law 2 in the direction G13 cannot see — a CONFIG KEY nothing
    // reads rather than a PROP nothing passes; `G45` is the check that asks it.
    const html = renderCustomFields([definition({ entity: "accounts" })]);
    expect(html).toContain("+ Filter");
    // The panel names the two declared dimensions, using the SAME labels the
    // columns carry — so this goes red if the declaration and the control ever
    // stop reading from one place.
    expect(html).toContain(t("settings.customFields.col.entity"));
    expect(html).toContain(t("settings.customFields.col.status"));
    // Real entity options, not the `<select>`-era sentinel: `offerableFilters`
    // strips `{ value: "", label: "All entities" }` because FilterBar's own
    // `All` chip IS that control and a checkbox valued "" can never read as
    // checked.
    expect(html).toContain(t("settings.customFields.entity.premises"));
    expect(html).not.toContain(t("settings.customFields.filter.allEntities"));
  });

  it("US-TEN-014 TC-1: an empty tenant gets the A18 empty state with the Add action", () => {
    const html = renderCustomFields([]);
    expect(html).toContain(t("settings.customFields.emptyTitle"));
    expect(html).toContain(t("settings.customFields.add"));
  });

  it("BR-TEN-047: the custom-fields card opens in the SAME frame as every other card", () => {
    const html = renderCustomFields([definition()]);
    // Same shell: the "← Reference data" return and the shared audit line.
    expect(html).toContain(t("settings.reference.back"));
    expect(html).toContain(t("settings.auditLine"));
  });

  it("BR-SHL-025: a read-only role gets the controls disabled WITH their reason", () => {
    const html = renderCustomFields([definition()], true);
    expect(html).toContain("disabled");
    expect(html).toContain(t("settings.readOnlyReason"));
  });
});

describe("US-TEN-017 — deactivate only", () => {
  it("US-TEN-017 TC-3: NO delete control is rendered, in any row state", () => {
    for (const row of [definition(), definition({ is_active: false })]) {
      const html = renderCustomFields([row]);
      // BR-TEN-050: the verb does not exist. Not a disabled button — absent.
      expect(html).not.toContain(t("settings.reference.delete"));
      expect(html.toLowerCase()).not.toContain(">delete<");
    }
  });

  it("US-TEN-017 TC-1/TC-2: the row action is Deactivate when active, Reactivate when not", () => {
    expect(renderCustomFields([definition()])).toContain(
      t("settings.customFields.deactivate"),
    );
    expect(renderCustomFields([definition({ is_active: false })])).toContain(
      t("settings.customFields.reactivate"),
    );
  });

  it("US-TEN-017: an inactive row is labelled inactive, not hidden from the manager", () => {
    const html = renderCustomFields([definition({ is_active: false })]);
    expect(html).toContain(t("settings.customFields.status.inactive"));
    expect(html).toContain("Feeder Number"); // still manageable
  });
});

describe("US-TEN-015 — the key, the cap and the option list", () => {
  it("US-TEN-015 TC-1: the key preview is derived from the label", () => {
    expect(previewKey("Feeder Number")).toBe("feeder_number");
    expect(previewKey("Co-op Member #")).toBe("co_op_member");
    expect(previewKey("  Tax District  ")).toBe("tax_district");
    // Starts with a digit → prefixed rather than rejected silently.
    expect(previewKey("2026 Survey")).toBe("f_2026_survey");
    // Reduces to nothing → EMPTY, and the server refuses it by name.
    expect(previewKey("###")).toBe("");
  });

  it("US-TEN-015 TC-5: the cap headroom is counted from ACTIVE rows only", () => {
    const rows = [
      ...Array.from({ length: 10 }, (_unused, i) =>
        definition({ id: `a${i}`, entity: "accounts", key: `k${i}` }),
      ),
      definition({ id: "z", entity: "accounts", key: "kz", is_active: false }),
    ];
    expect(activeCountFor(rows, "accounts")).toBe(10);
    expect(ACTIVE_CAP_PER_ENTITY - activeCountFor(rows, "accounts")).toBe(0);
    // …and the cap is PER ENTITY: assets is untouched by ten account fields.
    expect(activeCountFor(rows, "assets")).toBe(0);
  });

  it("US-TEN-015 TC-2: options keep the order they were typed", () => {
    expect(parseOptions("Residential\nCommercial\nIrrigation")).toEqual([
      "Residential",
      "Commercial",
      "Irrigation",
    ]);
    expect(parseOptions("Residential\n\n  Commercial  \n")).toEqual([
      "Residential",
      "Commercial",
    ]);
  });

  it("CR-161-BRC10 W1: the client carries NO list of record types — the server serves it", () => {
    // Hard-won law 5. `CUSTOM_FIELD_ENTITIES` was a hand copy of the server's
    // eight; it is gone, and the record types come from the served slot list.
    expect("CUSTOM_FIELD_ENTITIES" in settingsCustomFields).toBe(false);
    expect("slotChoices" in settingsCustomFields).toBe(false);
  });

  it("B2 r17.1: the client carries the signed type set, and invents none", () => {
    expect([...CUSTOM_FIELD_DATA_TYPES]).toEqual([
      "text",
      "number",
      "date",
      "boolean",
      "select",
      "multi_select",
    ]);
  });
});

describe("US-TEN-016 — placement", () => {
  it("DEF-TEN-9153: the editor offers only RENDERED screens from the server's list", () => {
    const groups = slotGroups(
      definition({
        entity: "accounts",
        slots: [
          ...ACCOUNT_SLOTS,
          // Declared and not yet drawn by any screen (W6) — never offered.
          slot({ key: "REQUEST_NEW", screen: "staff_new_request", rendered: false, wave: "W6" }),
        ],
      }),
    );
    expect(groups.map((g) => g.route)).toEqual(["clerk_input"]);
    expect(groups[0].slots.map((s) => s.key)).toEqual(["S18", "S21"]);
    // S31 (Run Bills) and the money screens are not in any list the server
    // publishes, so they cannot be offered here either.
    expect(groups.flatMap((g) => g.slots.map((s) => s.key))).not.toContain("S31");
  });

  it("DEF-TEN-9154: each screen offers ITS OWN choices, in the Roof Material table's words", () => {
    const words = (s: CustomFieldSlot) => choicesFor(s).map((c) => t(c.labelKey));
    expect(words(slot({ presentation: "portal", route: "portal" }))).toEqual([
      "Ask the customer",
      "Don't ask",
    ]);
    expect(words(slot({ presentation: "list", modes: ["view"], route: "read_only" }))).toEqual([
      "Show as column",
      "Not shown",
    ]);
    expect(words(slot({ modes: ["input", "view"], presentation: "form" }))).toEqual([
      "Input",
      "View",
      "Not shown",
    ]);
    expect(words(slot({ modes: ["view"], presentation: "page", route: "read_only" }))).toEqual([
      "View",
      "Not shown",
    ]);
  });

  it("DEF-TEN-9154: the dialog names screens and groups them — no screen id on screen", () => {
    const html = renderPlacement(
      definition({ entity: "accounts", placement: { S18: "input" }, slots: ACCOUNT_SLOTS }),
    );
    expect(html).toContain(t("settings.customFields.route.clerk_input"));
    expect(html).toContain(t("settings.customFields.screen.new_account"));
    expect(html).toContain(t("settings.customFields.screen.account_detail"));
    // B14 rule 31: the KEY travels in an id attribute and never as text.
    const text = html.replace(/<[^>]+>/g, " ");
    expect(text).not.toMatch(/\bS\d{1,3}\b/);
    expect(text).not.toContain("Screen ");
  });

  it("CR-161-BRC10 R4: an import-fed type with no screen yet says it is filled by import", () => {
    const html = renderPlacement(
      definition({ entity: "premises", placement: {}, slots: [], input_route: "import" }),
    );
    expect(html).toContain(t("settings.customFields.filledByImport"));
    const none = renderPlacement(
      definition({ entity: "contacts", placement: {}, slots: [], input_route: "none" }),
    );
    expect(none).toContain(t("settings.customFields.slot_not_rendered"));
  });

  it("CR-161-BRC10 W1: Applies to offers only types something collects, plus the field's own", () => {
    const catalogue: CustomFieldEntitySlots[] = [
      { entity: "premises", import_columns: true, offered: true, slots: [] },
      { entity: "contacts", import_columns: false, offered: false, slots: [] },
      { entity: "accounts", import_columns: false, offered: true, slots: ACCOUNT_SLOTS },
    ];
    expect(offeredEntities(catalogue)).toEqual(["premises", "accounts"]);
    expect(offeredEntities(catalogue, "contacts")).toEqual(["premises", "contacts", "accounts"]);
  });

  it("BR-TEN-052: input implies view on the same screen", () => {
    const placement = { S51: "input", S50: "view" };
    expect(screensFor(placement, "input")).toEqual(["S51"]);
    expect(screensFor(placement, "view")).toEqual(["S50", "S51"]);
  });

  it("US-TEN-016 TC-3: a slot absent from the map reads as Not shown", () => {
    expect(modeForSlot({ S51: "input" }, "S51")).toBe("input");
    expect(modeForSlot({ S51: "input" }, "S49")).toBe("not_shown");
  });

  it("DEF-TEN-9156: the Type help speaks only for a Number", () => {
    const render = (dataType: CustomFieldDefinition["data_type"]) =>
      renderToStaticMarkup(
        <QueryClientProvider client={new QueryClient()}>
          <DefinitionModal
            client={undefined as never}
            existing={definition({ entity: "accounts", data_type: dataType, options: ["A", "B"] })}
            catalogue={[]}
            rows={[]}
            onClose={() => undefined}
            onSaved={() => undefined}
          />
        </QueryClientProvider>,
      );
    const numberHelp = t("settings.customFields.typeHelp.number");
    expect(render("number")).toContain(numberHelp);
    for (const other of ["text", "date", "boolean", "select", "multi_select"] as const) {
      expect(render(other)).not.toContain(numberHelp);
    }
  });

  it("US-TEN-016: the placement count on the row is what the table shows", () => {
    const html = renderCustomFields([definition({ placement_count: 2 })]);
    expect(html).toContain(t("settings.customFields.col.placements"));
    expect(html).toContain(t("settings.customFields.placement"));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-014@a1c9f04 (story+rules snapshot over EP-TEN-09-custom-fields.md)
// generated: 2026-08-15 by story-coder (tenant custom-fields lane)
// checklist: A✔ B✔ C✔ D=deferred(server halves live in the pytest suite) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest — see the lane report, including the four checks proved RED first
// exceptions: the modal interactions (typing a label, submitting, the cap 422 rendering) are pure-function + markup assertions here rather than user-event drives — this suite renders to static markup, which is the pattern every other settings suite in this repo uses
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
