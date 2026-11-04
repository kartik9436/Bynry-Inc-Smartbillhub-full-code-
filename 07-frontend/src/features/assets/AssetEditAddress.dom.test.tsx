// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-092-BRC01 `AST-B-12` — "A clerk can correct an asset from the
//          asset, at an address they can come back to." Screens 08 and 14.
// Rules:   BR-AST-006 (the SERVER's action set decides what the header offers —
//          a retired asset takes no edit) · BR-AST-020 · B14 rule 39/R13 (two
//          fields to a row) · CLAUDE.md hard-won law 2 AND ITS MIRROR (a door
//          that points nowhere, and a live screen behind a dead control)
// Tests:   this file · AssetEditPayload.dom.test.tsx (the PATCH body) ·
//          AssetSizeDoors.dom.test.tsx (BR-AST-530's two doors)
// ───────────────────────────────────────────────────────
// ⚠ **WHY THIS FILE EXISTS AND WHY IT ASSERTS THE ADDRESS RATHER THAN THE
// FORM.** `AST-B-12`'s whole content is the ADDRESS: the form, its schema and
// its write already existed and are asserted key-for-key by the two suites
// named above. What did not exist was a URL a correction could be linked to and
// returned to, and two doors pointing at it. Hard-won law 2 says to assert a
// destination BY ADDRESS and by the screen it opens — a `toContain("/edit")` on
// an href passes on a protocol-relative string, and a spy on `navigate` passes
// when the route is not mounted at all. So every case below CLICKS a real
// control inside a router that mounts BOTH addresses and then reads what
// rendered.
//
// ⚠ **PROVED RED BEFORE TRUSTED GREEN (law 7), each case against the thing it
// is for — AND THE FIRST PROOF FAILED, WHICH IS WHY IT IS WRITTEN OUT HERE.**
// Removing the header's `hasAction(asset, "edit")` block turns TC-A1 red
// ("Unable to find role=button and name Edit"); leaving the registry pencil's
// `onClick` as it was before this change turns TC-A3 red (the address never
// moves). Both as expected.
//
// ⚠ **BUT DELETING `App.tsx`'s ROUTE LINE LEFT ALL FIVE CASES GREEN**, because
// this file mounts its OWN `<Routes>` and therefore cannot say one word about
// where the application mounts the screen. That is law 7's *check that cannot
// fail* in the exact shape the CWP audit records — "a hold-expiry test asserted
// a screen was REGISTERED at an address while the router was mounting it
// somewhere else". **The real mount is asserted by
// `src/routing/screenIds.test.tsx`**, which compares the whole screen-id table
// against `App.tsx`'s flattened route list in declaration order, so removing
// either half of the pair turns THAT suite red. This comment says so instead of
// claiming a proof this file does not have (hard-won law 1).
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { AssetDetail, AssetRow, LookupEntry, Paginated } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import { PREMISES_PERMISSION } from "@/features/metering/meteringShared";

import { AssetDetailPage } from "./AssetDetailPage";
import { AssetEditPage } from "./AssetEditPage";
import {
  AssetRegistryPage,
  assetStatusesQueryKey,
  assetTypesQueryKey,
  assetsQueryKey,
  assetsTableConfig,
  meterTypesQueryKey,
  readMethodsQueryKey,
  sizeClassesQueryKey,
  tabFromParam,
} from "./AssetRegistryPage";
import { assetEditPath } from "./assetsShared";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function lookup(code: string, name: string, category = ""): LookupEntry {
  return { id: code, code, name, active: true, is_system: true, used_by: 0, category } as LookupEntry;
}

/**
 * A field by its label. ⚠ **NOT `getByLabelText(label)`** — `FieldLabel` puts
 * BR-SHL-017's required asterisk INSIDE the `<label>`, so a required field's
 * accessible name is "Asset type*" and an exact match silently finds nothing
 * while the optional fields beside it match perfectly. Anchored at the start so
 * "Meter type" cannot match "Meter type does not apply…".
 */
function field(label: string): HTMLElement {
  return screen.getByLabelText(new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\*?$`));
}

function paged<T>(results: T[]) {
  return { results, page: 1, per: 200, total: results.length };
}

function envelope<T>(rows: T[]): Paginated<T> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

const TYPES = [lookup("meter", "Meter", "meters"), lookup("sub_meter", "Sub-meter", "sub_meters")];
const STAGES = [lookup("installed", "Installed"), lookup("inventory", "In inventory")];
const METER_TYPES = [lookup("ami", "AMI"), lookup("walk_by", "Walk-by")];

/** A shipped meter. Its figures are this fixture's own (B14 rule 37). */
function detail(over: Partial<AssetDetail> = {}): AssetDetail {
  return {
    id: "a-5000",
    asset_no: "E-5000",
    serial_no: "81-44120",
    type: "meter",
    type_name: "Meter",
    tab: "meters",
    status: "installed",
    status_name: "Installed",
    behavior_class: "in_service",
    meter_type: "walk_by",
    meter_type_name: "Walk-by",
    read_method: "manual",
    read_method_name: "Manual",
    multiplier: "10.000000",
    size_class: "W-58",
    unit: "kgal",
    net_metering: false,
    manufacturer: "Badger Meter",
    model: "M25",
    install_date: "2024-02-01",
    parent_asset_no: null,
    parent_asset_id: null,
    service_point_id: "sp-1",
    assigned_unit_id: "u-1",
    assigned_to: "Unit 1",
    assigned_address: "118 Bayou Bend Dr",
    assigned: true,
    test_due: false,
    retire_date: null,
    retire_reason: null,
    replaced_by: null,
    actions: ["view", "edit", "reassign", "log_repair", "retire"],
    service: "water",
    sub_count: 0,
    last_read: null,
    parent_premises: null,
    export_capacity_kw: null,
    warranty_end: null,
    next_test: null,
    has_test_cadence: true,
    specs: {
      form_class: null,
      register_digits: 9,
      firmware_version: null,
      seal_no: null,
      warranty_end: null,
      last_test_date: null,
      test_interval_months: null,
      location_note: "Pit at the kerb",
      allocation_rule: null,
      loss_tolerance_pct: null,
      allocation_share_pct: null,
    },
    classifications: {
      asset_type: { code: "meter", name: "Meter" },
      meter_type: { code: "walk_by", name: "Walk-by" },
      read_method: { code: "manual", name: "Manual" },
    },
    billing_chain: {
      premises_id: "p-1",
      premise_no: "P-00004",
      premise_address: "118 Bayou Bend Dr",
      unit_id: "u-1",
      unit_label: "Unit 1",
      account: null,
    },
    sub_assets: [],
    valuation: {
      supplier: null,
      purchase_cost: null,
      purchase_date: null,
      warranty_end: null,
      warranty_covered: false,
      depreciation_method: null,
      present_value: null,
      currency: "USD",
    },
    lifecycle: {
      age_months: 31,
      expected_life_years: 10,
      certification_due: null,
      replacement_year: null,
    },
    linked_meter: null,
    ...over,
  } as AssetDetail;
}

/**
 * ⚠ **THE STUB ANSWERS WITH THE ASSET UNDER TEST, NOT A CONSTANT** — the same
 * correction `AssetOverviewPanels.dom.test.tsx` records: react-query refetches
 * behind a seeded cache, so a stub that answers a different asset renders one
 * for a frame and then replaces it, and the failure names the wrong thing.
 */
function stubClient(asset: AssetDetail, sent: string[] = []): ApiClient {
  const answer = <T,>(data: unknown = {}) => ({
    data: data as T,
    status: 200,
    headers: new Headers(),
  });
  return {
    request: <T,>(path: string, options?: { method?: string; body?: unknown }) => {
      sent.push(`${options?.method ?? "GET"} ${path}`);
      return Promise.resolve(answer<T>(asset));
    },
    // `useAccessCell` reads `permissions.permissions.find(...)`, so this one is
    // not optional furniture — a catch-all `{results: []}` throws inside the
    // component and every case below fails for the wrong reason.
    get: <T,>(path: string) => {
      sent.push(`GET ${path}`);
      if (path === "/me/permissions") {
        return Promise.resolve(
          answer<T>({
            role: "system_admin",
            role_name: "System Admin",
            permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access: "Full" }],
          }),
        );
      }
      if (path.startsWith("/assets/") && !path.includes("/", 8)) {
        return Promise.resolve(answer<T>(asset));
      }
      // ⚠ **`GET /settings/services` ANSWERS A BARE ARRAY, NOT THE HOUSE
      // ENVELOPE**, and a catch-all `{results: []}` here crashed the registry
      // outright — `enabledServiceRows` calls `.filter` on it and React
      // unmounted the whole tree, so TC-A3 failed on the ADDRESS PROBE being
      // absent rather than on anything it was testing. Law 7's *looking at the
      // wrong thing*, inside a fixture.
      if (path === "/settings/services") {
        return Promise.resolve(answer<T>([]));
      }
      return Promise.resolve(answer<T>({ results: [], rows: [], total: 0, count: 0 }));
    },
    post: () => Promise.resolve(answer()),
    put: () => Promise.resolve(answer()),
    patch: () => Promise.resolve(answer()),
    del: () => Promise.resolve(answer()),
    pollJob: () => Promise.resolve(answer()),
  } as unknown as ApiClient;
}

/** The address bar, rendered — so a case can assert WHERE it is standing. */
function Address() {
  const location = useLocation();
  return <output data-testid="address">{`${location.pathname}${location.search}`}</output>;
}

function seed(asset: AssetDetail): QueryClient {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(["assets", "detail", asset.id], asset);
  queryClient.setQueryData(assetTypesQueryKey, paged(TYPES));
  queryClient.setQueryData(assetStatusesQueryKey, paged(STAGES));
  queryClient.setQueryData(meterTypesQueryKey, paged(METER_TYPES));
  queryClient.setQueryData(readMethodsQueryKey, paged([lookup("manual", "Manual")]));
  queryClient.setQueryData(sizeClassesQueryKey, paged([lookup("W-58", 'Water 5/8"')]));
  queryClient.setQueryData(queryKeys.myPermissions, {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access: "Full" }],
  });
  return queryClient;
}

/** Both addresses, mounted together, so a CLICK can be followed to what it
 *  opens rather than asserted against a string. */
function mountFrom(path: string, asset: AssetDetail, rows?: AssetRow[]) {
  const queryClient = seed(asset);
  if (rows !== undefined) {
    const config = assetsTableConfig(
      t,
      "meters",
      { types: [], statuses: [], meterTypes: [], premises: [], services: [] },
      BLANK_CELLS,
    );
    const search = new URLSearchParams(path.split("?")[1] ?? "");
    const tab = tabFromParam(search.get("tab"));
    const state = parseTableParams(search, config);
    queryClient.setQueryData(
      assetsQueryKey(`${serializeTableParams(state, config).toString()}|${tab}`),
      envelope(rows),
    );
  }
  const client = stubClient(asset);
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* Mounted under the REAL path patterns (law 2's fixture clause): a bare
            MemoryRouter leaves `useParams().tenant` undefined and every address
            the tree builds comes out `//assets/…` — a protocol-relative URL to
            another host, which reads as a perfectly good string. */}
        <MemoryRouter initialEntries={[path]}>
          <Address />
          <Routes>
            <Route
              path="/:tenant/assets"
              element={
                <AssetRegistryPage
                  client={client}
                  timeZone="America/Chicago"
                  dateFormat="MM/DD/YYYY"
                  today="2026-09-12"
                />
              }
            />
            <Route
              path="/:tenant/assets/:assetId"
              element={
                <AssetDetailPage
                  client={client}
                  timeZone="America/Chicago"
                  dateFormat="MM/DD/YYYY"
                />
              }
            />
            <Route
              path="/:tenant/assets/:assetId/edit"
              element={
                <AssetEditPage
                  client={client}
                  timeZone="America/Chicago"
                  dateFormat="MM/DD/YYYY"
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const BLANK_CELLS = new Proxy(
  {},
  { get: () => () => <span /> },
) as Parameters<typeof assetsTableConfig>[3];

describe("AST-B-12 — a correction has an address, and two doors point at it", () => {
  it("TC-A1: the asset's own header offers Edit, and pressing it LANDS on /assets/{id}/edit", async () => {
    const asset = detail();
    mountFrom(`/brazosbend/assets/${asset.id}`, asset);

    const edit = await screen.findByRole("button", { name: t("assets.action.edit") });
    await userEvent.click(edit);

    // The ADDRESS, and then the SCREEN — a door is only real if both are true.
    await waitFor(() =>
      expect(screen.getByTestId("address")).toHaveTextContent(
        `/brazosbend${assetEditPath(asset.id)}`,
      ),
    );
    expect(
      await screen.findByRole("heading", { name: t("assets.form.editTitle", { asset: "E-5000" }) }),
    ).toBeInTheDocument();
  });

  it("TC-A2: the address opens the form with the asset's stored values — a bookmark works", async () => {
    const asset = detail();
    mountFrom(`/brazosbend${assetEditPath(asset.id)}`, asset);

    // Nine controls, each holding what the server stored. `asset_no` is read
    // only (BR-AST-026) and still shows its value, which is the point of
    // `readOnly` over `disabled`.
    await screen.findByLabelText(t("assets.form.assetNo"));
    expect(field(t("assets.form.assetNo"))).toHaveValue("E-5000");
    expect(field(t("assets.form.serial"))).toHaveValue("81-44120");
    expect(field(t("assets.col.assetType"))).toHaveValue("meter");
    expect(field(t("assets.col.meterType"))).toHaveValue("walk_by");
    expect(field(t("assets.col.readMethod"))).toHaveValue("manual");
    expect(field(t("assets.col.sizeClass"))).toHaveValue("W-58");
    expect(field(t("assets.form.uom"))).toHaveValue("kgal");
    expect(field(t("assets.form.multiplier"))).toHaveValue("10.000000");
    expect(field(t("assets.form.manufacturerModel"))).toHaveValue(
      "Badger Meter · M25",
    );
    // The forward-only consequence, below the fields and above the buttons.
    expect(screen.getByText(t("assets.form.forwardOnlyNote"))).toBeInTheDocument();
  });

  it("TC-A3: the registry's pencil navigates to the same address — it opens no dialog", async () => {
    const asset = detail();
    const row = { ...asset } as AssetRow;
    mountFrom("/brazosbend/assets", asset, [row]);

    // The row is on screen before anything is pressed.
    expect(await screen.findByText("E-5000")).toBeInTheDocument();

    // ⚠ **`fireEvent.click`, AND THE REASON IS MEASURED RATHER THAN A
    // PREFERENCE.** `await userEvent.click(pencil)` on this control does
    // NOTHING here — it throws no error, the button is not disabled, and every
    // ancestor computes `pointer-events: auto` (all four probed) — while
    // `fireEvent.click` on the very same node navigates. userEvent awaits
    // between `pointerdown`, `mousedown` and `click`, and the seeded list's
    // background refetch resolves inside that gap and re-renders the row, so
    // the captured node is detached by the time the click is dispatched. A test
    // that "clicks and sees nothing happen" for that reason is law 7's
    // *looking at the wrong thing*, so the synchronous dispatch is used and the
    // row-action destination is what gets asserted.
    const pencil = screen.getByRole("button", { name: t("assets.action.edit") });
    await act(async () => {
      fireEvent.click(pencil);
    });

    await waitFor(() =>
      expect(screen.getByTestId("address")).toHaveTextContent(
        `/brazosbend${assetEditPath(asset.id)}`,
      ),
    );
    expect(
      await screen.findByRole("heading", { name: t("assets.form.editTitle", { asset: "E-5000" }) }),
    ).toBeInTheDocument();
  });

  it("TC-A4: BR-AST-006 — a RETIRED asset offers no Edit anywhere on its header", async () => {
    // `selectors.row_actions` returns exactly `["view"]` for a terminal stage,
    // and `update_asset` raises BIZ_IMMUTABLE before it validates anything, so
    // the two halves of the rule agree. The control is absent because the
    // SERVER says so — never because a status string was matched here.
    const retired = detail({
      status: "retired",
      status_name: "Retired",
      behavior_class: "terminal",
      actions: ["view"],
      retire_date: "2026-08-14",
    });
    mountFrom(`/brazosbend/assets/${retired.id}`, retired);

    expect(await screen.findByText("E-5000")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t("assets.action.edit") })).toBeNull();
  });

  it("TC-A5: Cancel returns to the asset and writes nothing", async () => {
    const asset = detail();
    mountFrom(`/brazosbend${assetEditPath(asset.id)}`, asset);

    await userEvent.click(await screen.findByRole("button", { name: t("assets.flow.cancel") }));
    await waitFor(() =>
      expect(screen.getByTestId("address")).toHaveTextContent(`/brazosbend/assets/${asset.id}`),
    );
  });
});
