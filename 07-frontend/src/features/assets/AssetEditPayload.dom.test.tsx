// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-MET-4971 — THE ASSET EDIT DIALOG'S `Asset type` SELECT IS
//          REQUIRED, INTERACTIVE, AND NEVER SENT. A clerk changes it, presses
//          Save, gets the success toast, and the type is unchanged.
//          `AssetFormModal.submit()` builds the PATCH body in one place and
//          `type` was never in it; `FormModal` validates `values` against
//          `assetSchema` — which marks `type` required — and then hands the
//          consumer's `onSubmit` a value it discards.
// CR:      CR-092-BRC01 step 2, wave B lane 3.
// Rules:   BR-AST-044 (the THREE classifications: type · meter_type ·
//          read_method, each independent) · BR-AST-012 (billing-affecting
//          fields are forward-only; `type` is NOT one of the four) ·
//          BR-AST-530 / BR-AST-500 (the connection size travels on the
//          `offersConnectionSize` predicate and blank is an explicit clear).
// Tests:   TC-E1 .. TC-E4.
//
// ⚠ **WHY THIS FILE EXISTS AT ALL, AND IT IS THE DEFECT'S OWN ESCAPE REASON.**
// The only test that mounted `AssetFormModal` (`AssetSizeDoors.dom.test.tsx`)
// asserts which options the size select offers and **never submits the form**,
// so the PATCH body had no assertion anywhere in the repository. `tsc` is
// happy because `values.type` IS read — it drives the `measuring` branch —
// eslint sees no unused value, and no gate compares a rendered form's controls
// with the keys its `onSubmit` builds. **A control that is validated and
// discarded looks identical to a control that works, from every check this
// repo has.**
//
// RED-FIRST PROOF (r11 step 2d), taken before this lane's one-line change to
// `submit()`, through `npx vitest run src/features/assets/AssetEditPayload.dom.test.tsx`
// — the harness that runs it, not a hand-rolled entry point:
//
//   TC-E1 → AssertionError: expected { serial_no: 'SN-1', …(6) } to match
//           object { type: 'net_meter' } — the seven keys actually sent were
//           manufacturer_model, meter_type, multiplier, read_method,
//           serial_no, size_class, unit
//   TC-E2 → AssertionError: expected [ 'manufacturer_model', …(6) ] to deeply
//           equal [ 'manufacturer_model', …(7) ] — the diff is one line,
//           `- "type"`: eight controls a clerk can edit, seven keys sent
//   TC-E3 → the same omission beside the two classifications that DO travel
//   TC-E4 → the same omission on a non-measuring device (`- "type": 'battery'`)
//
// and it was also proved in a BROWSER against a real server, because a stub
// client cannot tell you the server kept the value:
// `10-scripts/render-checks/cr092-lane3-edit-writes.mjs` drove the dialog on
// brazosbend at 1280 and 1440, saw the success toast, and read the row back —
// *"chose backflow, the server still holds pv"*.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { AssetRow, LookupEntry } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import {
  assetTypesQueryKey,
  meterTypesQueryKey,
  readMethodsQueryKey,
  sizeClassesQueryKey,
} from "./AssetRegistryPage";
// `AST-B-12`: the form is the same form, on its own page now (AST-09).
import { AssetEditForm } from "./AssetEditPage";

afterEach(cleanup);

const t = (key: string): string => i18n.t(key);

function lookup(code: string, name: string, category: string, active = true): LookupEntry {
  return { id: code, code, name, active, is_system: true, used_by: 0, category } as LookupEntry;
}

/** ⚠ **REAL CODES AND REAL CATEGORIES.** `typesForTab` filters on the catalog
 *  `category`, so a fixture whose types carry no category renders an EMPTY
 *  select and every assertion below would pass over a form with no options —
 *  law 7's *incapable of failing* shape, one fixture down. */
const TYPES: LookupEntry[] = [
  lookup("meter", "Meter", "meters"),
  lookup("net_meter", "Net meter", "meters"),
  lookup("sub_meter", "Sub-meter", "sub_meters"),
  lookup("pv", "PV / solar", "behind_the_meter"),
  lookup("battery", "Battery storage", "behind_the_meter"),
];

const SIZES: LookupEntry[] = [lookup("W-58", 'Water 5/8"', ""), lookup("W-2", 'Water 2"', "")];

function paged<T>(results: T[]) {
  return { results, page: 1, per: 200, total: results.length };
}

function row(over: Partial<AssetRow> = {}): AssetRow {
  return {
    id: "a-1",
    asset_no: "M-7001",
    serial_no: "SN-1",
    external_ref: null,
    type: "meter",
    type_name: "Meter",
    tab: "meters",
    status: "installed",
    status_name: "Installed",
    behavior_class: "in_service",
    meter_type: "ami",
    meter_type_name: "AMI",
    read_method: "ami",
    read_method_name: "AMI",
    multiplier: "1.000000",
    size_class: null,
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
  } as AssetRow;
}

/**
 * A client that answers nothing and REMEMBERS EVERYTHING. The point of the
 * whole file is the `body` it keeps: the dialog's own report of itself is a
 * success toast, and a success toast is exactly what `DEF-MET-4971` produces.
 */
function recordingClient(sent: { method: string; path: string; body: unknown }[]): ApiClient {
  const answer = <T,>() => ({ data: {} as T, status: 200, headers: new Headers() });
  return {
    request: <T,>(path: string, options?: { method?: string; body?: unknown }) => {
      sent.push({ method: options?.method ?? "GET", path, body: options?.body });
      return Promise.resolve(answer<T>());
    },
    get: <T,>(path: string) => {
      sent.push({ method: "GET", path, body: undefined });
      return Promise.resolve(answer<T>());
    },
    post: () => {
      throw new Error("unplanned post()");
    },
    put: () => {
      throw new Error("unplanned put()");
    },
    patch: () => {
      throw new Error("unplanned patch() — updateAsset goes through request()");
    },
    del: () => {
      throw new Error("unplanned del()");
    },
    pollJob: () => {
      throw new Error("unplanned pollJob()");
    },
  } as unknown as ApiClient;
}

function mountEditForm(
  tab: "meters" | "sub_meters" | "behind_the_meter",
  sent: { method: string; path: string; body: unknown }[],
  over: Partial<AssetRow> = {},
): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(readMethodsQueryKey, paged([lookup("ami", "AMI", "")]));
  queryClient.setQueryData(sizeClassesQueryKey, paged(SIZES));
  // The two the registry used to hand down as props.
  queryClient.setQueryData(assetTypesQueryKey, paged(TYPES));
  queryClient.setQueryData(meterTypesQueryKey, paged([lookup("ami", "AMI", "")]));
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* ⚠ Mounted under the REAL path pattern (hard-won law 2's fixture
            clause): a bare MemoryRouter leaves `useParams().tenant` undefined
            and every address the tree builds comes out protocol-relative. */}
        <MemoryRouter initialEntries={["/brazosbend/assets"]}>
          <Routes>
            <Route
              path="/:tenant/assets"
              element={
                <AssetEditForm
                  asset={row({ tab, ...over })}
                  client={recordingClient(sent)}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Every id the form renders as an editable control, in sorted order. */
function controlIds(): string[] {
  return Array.from(document.querySelectorAll<HTMLElement>("[data-asset-edit-form] .field"))
    .map((field) => field.querySelector<HTMLElement>("input, select, textarea"))
    .filter((el): el is HTMLElement => el !== null)
    .filter((el) => !(el as HTMLInputElement).readOnly)
    .map((el) => el.id)
    .sort();
}

function patchBody(sent: { method: string; path: string; body: unknown }[]) {
  const patch = sent.find((call) => call.method === "PATCH");
  expect(patch, "the form sent no PATCH at all").toBeDefined();
  return patch?.body as Record<string, unknown>;
}

describe("DEF-MET-4971 — what the edit dialog SHOWS, it SENDS", () => {
  it("TC-E1: the Asset type a clerk chooses reaches the PATCH body", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    mountEditForm("meters", sent);
    const control = (await screen.findByLabelText(
      `${t("assets.col.assetType")}*`,
    )) as HTMLSelectElement;
    expect(control.value).toBe("meter");
    await userEvent.selectOptions(control, "net_meter");
    expect(control.value).toBe("net_meter");
    await userEvent.click(screen.getByRole("button", { name: t("assets.form.save") }));
    // ⚠ THE ASSERTION THE WHOLE DEFECT TURNS ON. Before this lane's change the
    // body held seven keys and `type` was not one of them, while the form
    // reported success — so the clerk's change was validated and discarded.
    expect(patchBody(sent)).toMatchObject({ type: "net_meter" });
  });

  it("TC-E2: every editable control in the dialog is represented in the body", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    mountEditForm("meters", sent, { size_class: "W-2" });
    await screen.findByLabelText(`${t("assets.col.assetType")}*`);
    // ⚠ **THE CENSUS IS TAKEN BEFORE SAVE IS PRESSED, AND THAT IS NOT A
    // TIDINESS.** A successful save now LEAVES this screen — it is a page, and
    // it returns the clerk to the asset they were correcting — so a census
    // taken afterwards reads an unmounted form and reports an empty list. It
    // did, which is how the ordering was found.
    const rendered = controlIds();
    await userEvent.click(screen.getByRole("button", { name: t("assets.form.save") }));
    const body = patchBody(sent);
    // The generalisable shape `DEF-MET-4971`'s prevention column asks for:
    // for any field-component consumer, every id passed to a field should
    // appear in the payload its submit builds, OR be readOnly with a help
    // line saying why. `asset_no` is the correct shape of that exemption —
    // it is `readOnly` and its helper says the number is not edited here.
    // ⚠ The container hook moved with the form: it read `.modal-body .field`
    // while this was a dialog, and a selector that matches nothing reports an
    // EMPTY census as a pass against an empty expectation — so the assertion
    // below compares against a WRITTEN list of eight ids, which is what made
    // the move visible instead of silent.
    expect(rendered).toEqual(
      [
        "manufacturer_model",
        "meter_type",
        "multiplier",
        "read_method",
        "serial_no",
        "size_class",
        "type",
        "unit",
      ].sort(),
    );
    // `CR-161-BRC10` W3 — `custom_data` rides every save (only what changed;
    // `{}` here, where nothing changed) so a required field placed on Edit
    // asset can refuse; it is the custom-field section's key, not a control id.
    expect(body.custom_data).toEqual({});
    expect(Object.keys(body).filter((key) => key !== "custom_data").sort()).toEqual(rendered);
  });

  it("TC-E3: the three classifications travel independently (BR-AST-044)", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    mountEditForm("meters", sent);
    await screen.findByLabelText(`${t("assets.col.assetType")}*`);
    await userEvent.click(screen.getByRole("button", { name: t("assets.form.save") }));
    const body = patchBody(sent);
    // `type` is not billing-affecting (BILLING_AFFECTING_FIELDS is multiplier,
    // unit, net_metering, service), so adding it to the body raises no
    // forward-only warning of its own — but it must not displace the other two.
    expect(body).toMatchObject({ type: "meter", meter_type: "ami", read_method: "ami" });
  });

  it("TC-E4: a non-measuring device sends its type and no measuring fields", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    mountEditForm("behind_the_meter", sent, {
      type: "pv",
      type_name: "PV / solar",
      meter_type: null,
      unit: null,
      service: null,
    });
    const control = (await screen.findByLabelText(
      `${t("assets.col.assetType")}*`,
    )) as HTMLSelectElement;
    await userEvent.selectOptions(control, "battery");
    await userEvent.click(screen.getByRole("button", { name: t("assets.form.save") }));
    const body = patchBody(sent);
    expect(body).toMatchObject({ type: "battery" });
    // BR-AST-044: meter_type travels ONLY for a measuring type, and the server
    // refuses it by name on anything else. The control is not rendered here
    // either, so the two halves of the rule cannot drift.
    expect(body).not.toHaveProperty("meter_type");
    expect(body).not.toHaveProperty("unit");
    expect(body).not.toHaveProperty("multiplier");
    // ⚠ And `size_class` is ABSENT rather than null: `offersConnectionSize`
    // is false for a device that declares no service, so there is nothing to
    // clear and nothing to send (BR-AST-530 as amended, DEF-2414).
    expect(body).not.toHaveProperty("size_class");
  });
});
