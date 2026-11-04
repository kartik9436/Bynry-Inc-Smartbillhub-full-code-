// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 3, lane RAISE — images 14–20
//           (`05-prototype/work-backoffice-2026-10-04/images/`), rulings 19–25
//           and 35. Defects held: DEF-WRK-9572 (free-text premises and type),
//           DEF-WRK-9582 (job type one flat list), DEF-WRK-4752 (a door that
//           opens the raise blank).
// Rules:    B14 rules 2/16 (actions top right; a step flow keeps its footer),
//           21, 31 (no database id on screen), 33, 37, 42, 44.
// ───────────────────────────────────────────────────────
//
// Mounted under the REAL path patterns: a bare mount leaves `useParams()`
// empty and every address the screen builds reads `//…` (hard-won law 2).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { RaiseWorkOrderPage } from "@/features/assets/RaiseWorkOrderPage";
import { NewOrderWizard } from "../NewOrderWizard";
// ⚠ REAL PostgreSQL answers recorded by lane SRV-2 (`10-scripts/cr168_srv2_record_shapes.py`)
// — the shapes the screen reads are the server's, never typed by hand here.
// The premises picker, the units page and a template's detail have no
// recording yet and are written in the server's shapes below.
import RECORDED_ASSETS from "../__fixtures__/work-raise-assets.recorded.json";
import RECORDED_ASSET_TEMPLATES from "../__fixtures__/asset-work-order-templates.recorded.json";
import RECORDED_BULK from "../__fixtures__/work-orders-bulk-raise.recorded.json";
import RECORDED_CANDIDATES from "../__fixtures__/work-raise-candidates.recorded.json";
import RECORDED_TEMPLATES from "../__fixtures__/work-templates-for-the-raise.recorded.json";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(() => cleanup());

type Call = { method: string; path: string; query: Record<string, unknown>; body: unknown };
const ok = (data: unknown) => ({ status: 200, data, etag: null, notModified: false }) as ApiResponse<unknown>;
const page = <R,>(results: R[]) => ({ count: results.length, next: null, previous: null, results });

const U1 = RECORDED_ASSETS.results[0].unit.id; // "Unit 1" of 101 Silver Creek Rd, as recorded
const METER_TYPE = RECORDED_ASSETS.results[0].type.id;
const T_MX = RECORDED_TEMPLATES.results.find((r) => r.name === "Meter exchange — residential")!.id;
const T_TAP = RECORDED_TEMPLATES.results.find((r) => r.name === "Tap and service line")!.id;
const ORTIZ = RECORDED_CANDIDATES.results.find((r) => r.name === "D. Ortiz")!.id;

const PREMISES = {
  id: "p-101",
  premise_no: "P-00101",
  address_line: "101 Silver Creek Rd",
  city: "Silver Creek",
  state: "TX",
  postal_code: "77001",
  premises_type: "apartment_complex",
  services_available: ["electric", "water"],
  units: [
    { id: U1, unit_no: "1", label: "Unit 1", is_common_area: false },
    { id: "u-2", unit_no: "2", label: "Unit 2", is_common_area: false },
    { id: "u-3", unit_no: "3", label: "Unit 3", is_common_area: false },
  ],
};
const ONE_UNIT_PREMISES = { ...PREMISES, id: "p-107", address_line: "107 Mill Pond Ln", premises_type: "single_family", units: [PREMISES.units[0]] };

function unitRow(id: string, label: string, occupancy = "occupied") {
  return {
    id, unit_no: label.replace("Unit ", ""), label, premises_id: "p-101", premise_no: "P-00101",
    premise_address: "101 Silver Creek Rd", unit_type: "residential_submetered",
    occupancy, status: "active", services: ["electric", "water"], metered_services: ["electric", "water"],
  };
}
const UNITS = page([unitRow(U1, "Unit 1"), unitRow("u-2", "Unit 2", "vacant"), unitRow("u-3", "Unit 3")]);

const RAISE_OPTIONS = {
  types: [
    { id: "jt-meter", code: "METER", name: "Meter Maintenance", parent_name: null, default_priority_id: null },
    { id: "jt-change", code: "METER_CHANGE", name: "Meter Change", parent_name: "Meter Maintenance", default_priority_id: "pr-normal" },
    { id: "jt-dispose", code: "METER_DISPOSE", name: "Meter Dispose", parent_name: "Meter Maintenance", default_priority_id: "pr-normal" },
    { id: "jt-conn", code: "CONN", name: "Residential Connection", parent_name: null, default_priority_id: "pr-normal" },
  ],
  priorities: [
    { id: "pr-normal", code: "NORMAL", name: "Normal", sla_hours: 72 },
    { id: "pr-urgent", code: "URGENT", name: "Urgent", sla_hours: 4 },
  ],
};

// The recorded list, plus ONE draft — BR-WRK-011's case the recording does not
// hold (the server's `f.raisable=1` keeps drafts out; the screen must too).
const TEMPLATES = {
  ...RECORDED_TEMPLATES,
  results: [
    ...RECORDED_TEMPLATES.results,
    { ...RECORDED_TEMPLATES.results[0], id: "t-draft", name: "Backflow test — draft", version: 0, template_no: null, status: "draft" },
  ],
};
const MX_DETAIL = { ...RECORDED_TEMPLATES.results.find((r) => r.id === T_MX), bundle: { asset_types: [{ asset_type_id: METER_TYPE }] } };
const TAP_DETAIL = { ...RECORDED_TEMPLATES.results.find((r) => r.id === T_TAP), bundle: { asset_types: [] } };
const ASSET_TYPES = page([{ id: METER_TYPE, code: "meter", name: "Meter", active: true, is_system: true, used_by: 0 }]);

/** The bulk answer, ONE ROW PER SUBJECT in the recorded row's own shape. */
function bulkAnswer(body: { unit_ids?: string[]; asset_ids?: string[] }) {
  const shape = RECORDED_BULK.results[0];
  const subjects = body.asset_ids ?? body.unit_ids ?? [];
  const results = subjects.map((sid, i) => ({
    ...shape,
    unit_id: body.unit_ids ? sid : null,
    unit: body.unit_ids ? { label: UNITS.results.find((u) => u.id === sid)?.label ?? "" } : null,
    asset_id: body.asset_ids ? sid : null,
    asset: body.asset_ids ? { asset_no: RECORDED_ASSETS.results.find((r) => r.id === sid)?.asset_no ?? "" } : null,
    id: `wo-${i}`,
    order_no: `WO-00${45 + i}`,
  }));
  return { results, done: results.length, failed: 0, replayed: false };
}

function fakeClient(calls: Call[], extra: Record<string, unknown> = {}, bulk?: unknown): ApiClient {
  const reads: Record<string, unknown> = {
    "/premises/picker": page([PREMISES, ONE_UNIT_PREMISES]),
    "/premises/types": [
      { id: "pt-1", code: "apartment_complex", name: "Apartment complex", active: true, is_system: true },
      { id: "pt-2", code: "single_family", name: "Single-family", active: true, is_system: true },
    ],
    "/premises/p-101": {
      id: "p-101", premise_no: "P-00101", address_line: "101 Silver Creek Rd", city: "Silver Creek",
      premises_type: "apartment_complex", premises_type_name: "Apartment complex", unit_rows: [],
    },
    "/units/unit-types": { results: [{ code: "residential", name: "Residential" }, { code: "commercial", name: "Commercial" }, { code: "common_area", name: "Common area" }] },
    "/work/raise-options": RAISE_OPTIONS,
    "/work/templates": TEMPLATES,
    [`/work/templates/${T_MX}`]: MX_DETAIL,
    [`/work/templates/${T_TAP}`]: TAP_DETAIL,
    "/lookups/asset_types": ASSET_TYPES,
    "/work/raise/assets": RECORDED_ASSETS,
    "/work/candidates": RECORDED_CANDIDATES,
    ...extra,
  };
  const write = (method: string) => async (path: string, body?: unknown) => {
    calls.push({ method, path, query: {}, body: body ?? null });
    return ok(bulk ?? bulkAnswer((body ?? {}) as { unit_ids?: string[]; asset_ids?: string[] }));
  };
  return {
    get: async (path: string, opts?: { query?: Record<string, unknown> }) => {
      calls.push({ method: "GET", path, query: opts?.query ?? {}, body: null });
      if (path === "/units") {
        const q = opts?.query ?? {};
        if (q["f.premises_id"] === "p-107") return ok(page([unitRow(U1, "Unit 1")]));
        return ok(UNITS);
      }
      if (path in reads) return ok(reads[path]);
      if (path.startsWith("/custom-fields")) return ok({ results: [] });
      throw new Error(`unexpected read: ${path}`);
    },
    post: write("POST"),
    patch: write("PATCH"),
    put: write("PUT"),
    del: write("DELETE"),
    request: write("REQUEST"),
  } as unknown as ApiClient;
}

function mountDispatcher(calls: Call[], search = "", bulk?: unknown) {
  const client = fakeClient(calls, {}, bulk);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/work/orders/new${search}`]}>
          <Routes>
            <Route path="/:tenant/work/orders/new" element={<NewOrderWizard client={client} />} />
            <Route path="/:tenant/work/orders" element={<p>orders list</p>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function pickPremises(user: ReturnType<typeof userEvent.setup>, line: RegExp = /101 Silver Creek Rd/u) {
  const box = await screen.findByRole("combobox", { name: t("work.raise.premises") });
  await user.type(box, "Silver");
  await user.click(await screen.findByRole("option", { name: line }));
}

describe("CR-168 image 14 · the raise on units (DEF-WRK-9572)", () => {
  it("the premises is a dropdown you type into — never a free-text box", async () => {
    const calls: Call[] = [];
    mountDispatcher(calls);
    const box = await screen.findByRole("combobox", { name: t("work.raise.premises") });
    expect(box.tagName).toBe("INPUT");
    const user = userEvent.setup();
    await pickPremises(user);
    // The typed term SEARCHES (IS-3: once, after the last keystroke).
    const search = calls.filter((c) => c.path === "/premises/picker").pop();
    expect(search?.query).toMatchObject({ q: "Silver" });
    // The picked row's fact under the field — its type and its unit count.
    expect(await screen.findByText(/Apartment complex · 3 units/u)).toBeTruthy();
  });

  it("ruling 19 — the building's units are a table you tick; one job per unit", async () => {
    const calls: Call[] = [];
    mountDispatcher(calls);
    const user = userEvent.setup();
    await pickPremises(user);
    const units = await screen.findByTestId("raise-units");
    await within(units).findByText("Unit 3");
    // B14 rule 31 — no uuid is a visible value anywhere in the table.
    expect(units.textContent ?? "").not.toContain(U1);
    await user.click(within(units).getByRole("checkbox", { name: t("work.raise.tick", { unit: "Unit 1" }) }));
    await user.click(within(units).getByRole("checkbox", { name: t("work.raise.tick", { unit: "Unit 2" }) }));
    expect(within(units).getByText(t("work.raise.chosen", { n: 2, total: 3 }))).toBeTruthy();
    expect(screen.getByText(t("work.raise.summaryUnits", { count: 2 }))).toBeTruthy();
    // The unit read is the server's page, scoped to the building (NFR-3).
    expect(calls.find((c) => c.path === "/units")?.query).toMatchObject({ "f.premises_id": "p-101" });
    // Image 14's chips are the tenant's own unit types (never Common area),
    // and a chip narrows the SERVER read.
    await user.click(within(units).getByRole("button", { name: "Residential" }));
    await waitFor(() =>
      expect(calls.filter((c) => c.path === "/units").pop()?.query).toMatchObject({ "f.unit_type": "residential" }),
    );
    expect(within(units).queryByRole("button", { name: "Common area" })).toBeNull();
  });

  it("DEF-WRK-9616 — tick-all chooses EVERY unit on the page, and stays ticked", async () => {
    mountDispatcher([]);
    const user = userEvent.setup();
    await pickPremises(user);
    const units = await screen.findByTestId("raise-units");
    await within(units).findByText("Unit 3");
    const all = within(units).getByRole("checkbox", { name: t("work.raise.tickAll") }) as HTMLInputElement;
    await user.click(all);
    expect(within(units).getByText(t("work.raise.chosen", { n: 3, total: 3 }))).toBeTruthy();
    expect(all.checked).toBe(true);
    await user.click(all);
    expect(within(units).getByText(t("work.raise.chosen", { n: 0, total: 3 }))).toBeTruthy();
  });

  it("Continue on nothing names the field that is missing, not 'Premises and type needed.'", async () => {
    mountDispatcher([]);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: t("wizard.continue") }));
    expect(await screen.findByText(t("work.raise.need.premises"))).toBeTruthy();
    expect(screen.queryByText("Premises and type needed.")).toBeNull();
  });
});

describe("CR-168 · job type as a two-level picker (DEF-WRK-9582)", () => {
  it("a heading's sub-types sit in its group; a heading with sub-types is not a job", async () => {
    mountDispatcher([]);
    const select = (await screen.findByLabelText(new RegExp(t("work.raise.type"), "u"))) as HTMLSelectElement;
    await waitFor(() => expect(select.querySelectorAll("optgroup").length).toBe(1));
    const group = select.querySelector("optgroup");
    expect(group?.getAttribute("label")).toBe("Meter Maintenance");
    expect(Array.from(group?.querySelectorAll("option") ?? []).map((o) => o.textContent)).toEqual([
      "Meter Change",
      "Meter Dispose",
    ]);
    const loose = Array.from(select.querySelectorAll(":scope > option")).map((o) => o.textContent);
    expect(loose).not.toContain("Meter Maintenance");
    expect(loose).toContain("Residential Connection");
  });
});

async function stepOne(
  user: ReturnType<typeof userEvent.setup>,
  units: string[],
  type: string,
  template: string,
) {
  await pickPremises(user);
  const table = await screen.findByTestId("raise-units");
  await within(table).findByText("Unit 1");
  for (const label of units) {
    await user.click(within(table).getByRole("checkbox", { name: t("work.raise.tick", { unit: label }) }));
  }
  await user.selectOptions(screen.getByLabelText(new RegExp(t("work.raise.type"), "u")), type);
  const templateSelect = screen.getByLabelText(new RegExp(t("work.raise.template"), "u"));
  await waitFor(() => expect(templateSelect.querySelectorAll(`option[value='${template}']`).length).toBe(1));
  return templateSelect;
}

describe("CR-168 image 15 · an asset type chosen (ruling 20, ruling 22)", () => {
  it("the ticked units' assets, with their own search; two of the type on one unit read Choose one", async () => {
    const calls: Call[] = [];
    mountDispatcher(calls);
    const user = userEvent.setup();
    const templateSelect = await stepOne(user, ["Unit 1", "Unit 2"], "jt-change", T_MX);
    await user.selectOptions(templateSelect, T_MX);
    await waitFor(() => expect(screen.getByText(t("work.raise.assetTypeSet"))).toBeTruthy());
    const assets = await screen.findByTestId("raise-assets");
    await within(assets).findByText("W-5000");
    expect(within(assets).getByRole("searchbox", { name: t("work.raise.assetsSearchLabel") })).toBeTruthy();
    // `shares_unit` (recorded true on both) → each reads Choose one.
    expect(within(assets).getAllByText(t("work.raise.chooseOne")).length).toBe(2);
    // The last reading with its unit (hard rule 3), never the raw decimal.
    expect(within(assets).getByText(/1,024 kgal/u)).toBeTruthy();
    const read = calls.filter((c) => c.path === "/work/raise/assets").pop();
    expect(read?.query).toMatchObject({ unit_ids: `${U1},u-2`, asset_type: METER_TYPE, service: "water" });
    // Ruling 20 — nothing ticked: Continue refuses under the table.
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
    expect(await screen.findByText(t("work.raise.need.assets"))).toBeTruthy();
    // One chosen: Choose one goes, and the summary counts assets.
    await user.click(within(assets).getByRole("checkbox", { name: t("work.raise.tick", { unit: "W-5000" }) }));
    expect(within(assets).queryAllByText(t("work.raise.chooseOne")).length).toBe(0);
    expect(screen.getByText(t("work.raise.summaryOne", { subject: "W-5000" }))).toBeTruthy();
  });
});

describe("CR-168 images 16–18 · schedule & crew, confirm, result", () => {
  it("rulings 23–25: a due date picker, no Area, assign or leave blank — then N jobs in one press", async () => {
    const calls: Call[] = [];
    mountDispatcher(calls);
    const user = userEvent.setup();
    const templateSelect = await stepOne(user, ["Unit 1", "Unit 2"], "jt-conn", T_TAP);
    // TC-5 · BR-WRK-008 — published templates only, each by its NAME (rule 31).
    expect(templateSelect.querySelector("option[value='t-draft']")).toBeNull();
    expect(templateSelect.textContent ?? "").not.toContain(T_TAP);
    await user.selectOptions(templateSelect, T_TAP);
    // The template names no asset type, so it stays None — the unit itself.
    expect(await screen.findByText(t("work.raise.assetTypeHelp"))).toBeTruthy();
    expect(screen.getByText(t("work.raise.summaryUnits", { count: 2 }))).toBeTruthy();
    // The template read asks the server for what may be raised.
    const templateRead = calls.filter((c) => c.path === "/work/templates").pop()?.query ?? {};
    // The server narrows by job type (untyped templates included, SRV-3's
    // `DEF-WRK-9612` fix) and offers only what may be raised.
    expect(templateRead).toMatchObject({ "f.job_type": "jt-conn", "f.raisable": 1 });
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));

    // Step 2 — image 16.
    const due = (await screen.findByLabelText(t("work.raise.due"))) as HTMLInputElement;
    expect(due.type).toBe("date");
    expect(due.value).not.toBe(""); // opens on the priority's promise
    // Ruling 24 — no Area on the raise; the job takes its building's.
    expect(screen.queryByLabelText(/^Area/u)).toBeNull();
    const assign = screen.getByRole("combobox", { name: t("work.raise.assignTo") });
    await user.click(assign);
    // Best fit first, every holder kind offered (recorded: D. Ortiz).
    const options = await screen.findAllByRole("option");
    expect(options.map((o) => o.textContent ?? "").join("|")).toMatch(/D\. Ortiz.*Field crew B.*Redline Meter Services/u);
    await user.click(screen.getByRole("option", { name: /D\. Ortiz/u }));
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));

    // Step 3 — image 17. Dates in the tenant's regional format, never ISO.
    expect(await screen.findByTestId("raise-jobs")).toBeTruthy();
    const dueFact = document.querySelector('[data-raise-fact="due"] dd')?.textContent ?? "";
    expect(dueFact).toMatch(/^\d{2}\/\d{2}\/\d{4}$/u);
    await user.click(screen.getByRole("button", { name: t("work.raise.commit", { count: 2 }) }));

    // Image 18 — the result, and the ONE write it came from.
    expect(await screen.findByText(t("work.raise.resultTitle", { count: 2 }))).toBeTruthy();
    const post = calls.find((c) => c.method === "POST");
    expect(post?.path).toBe("/work-orders/bulk-raise");
    expect(post?.body).toMatchObject({
      template_id: T_TAP,
      type_id: "jt-conn",
      type: "Residential Connection",
      premises_id: "p-101",
      unit_ids: [U1, "u-2"],
      assignee: { technician_id: ORTIZ },
      source: "dispatcher",
    });
    expect(post?.body).not.toHaveProperty("area_id");
    expect(post?.body).not.toHaveProperty("asset_type_id");
    expect((post?.body as { idempotency_key: string }).idempotency_key).toMatch(/^[0-9a-f]{32}$/u);
    expect(screen.getByText("WO-0045")).toBeTruthy();
    expect(screen.getByRole("button", { name: t("work.raise.openOrders") })).toBeTruthy();
    expect(screen.getByRole("button", { name: t("work.raise.raiseMore") })).toBeTruthy();
  });

  it("one unit, one job — the recorded answer drawn as image 18", async () => {
    const calls: Call[] = [];
    mountDispatcher(calls, "", RECORDED_BULK);
    const user = userEvent.setup();
    await pickPremises(user, /107 Mill Pond Ln/u);
    // A building of one unit arrives with it ticked.
    const units = await screen.findByTestId("raise-units");
    await waitFor(() => expect(within(units).getByText(t("work.raise.chosen", { n: 1, total: 1 }))).toBeTruthy());
    await user.selectOptions(screen.getByLabelText(new RegExp(t("work.raise.type"), "u")), "jt-conn");
    const templateSelect = screen.getByLabelText(new RegExp(t("work.raise.template"), "u"));
    await waitFor(() => expect(templateSelect.querySelectorAll(`option[value='${T_TAP}']`).length).toBe(1));
    await user.selectOptions(templateSelect, T_TAP);
    expect(await screen.findByText(t("work.raise.summaryOne", { subject: "Unit 1" }))).toBeTruthy();
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
    await screen.findByLabelText(t("work.raise.due"));
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
    await user.click(await screen.findByRole("button", { name: t("work.raise.commit", { count: 1 }) }));
    expect(await screen.findByText(t("work.raise.resultTitle", { count: 1 }))).toBeTruthy();
    expect(screen.getByText("WO-0042")).toBeTruthy();
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toMatchObject({ unit_ids: [U1], assignee: null });
  });
});

describe("CR-168 image 14 door · a premises arrives picked (DEF-WRK-4752)", () => {
  it("?premises= opens the raise on that building, its units already listed", async () => {
    const calls: Call[] = [];
    mountDispatcher(calls, "?premises=p-101");
    expect(await screen.findByTestId("raise-units")).toBeTruthy();
    expect(calls.find((c) => c.path === "/units")?.query).toMatchObject({ "f.premises_id": "p-101" });
  });
});

describe("CR-168 image 20 · raised from an asset (ruling 35; figure 42 retired)", () => {
  it("the same three-step raise, arriving filled from the asset, offered only its own templates", async () => {
    const calls: Call[] = [];
    const recorded = RECORDED_ASSET_TEMPLATES;
    const ASSET = recorded.asset.id; // E-5000, as recorded
    const client = fakeClient(calls, {
      [`/assets/${ASSET}`]: {
        id: ASSET, asset_no: recorded.asset.asset_no, type: "meter", type_name: "Meter", read_method_name: "Walk-by",
        service: recorded.asset.service_code, assigned_unit_id: U1, assigned_address: "101 Silver Creek Rd",
        assigned: true, status: "in_service", status_name: "In service", actions: [], warnings: [],
        specs: { location_note: "Front boundary box" },
      },
      [`/units/${U1}`]: unitRow(U1, "Unit 1"),
      [`/units/${U1}/account`]: {
        unit: { id: U1, unit_no: "1", label: "Unit 1", is_common_area: false },
        account: { id: "acc-1", account_no: "AC-2026-00001", name: "Ana Alvarez" }, facts: null,
        owner_account: null, no_account_reason: null, facts_unavailable: null,
      },
      [`/assets/${ASSET}/work-order-templates`]: recorded,
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}/assets/${ASSET}/work-orders/new`]}>
            <Routes>
              <Route path="/:tenant/assets/:assetId/work-orders/new" element={<RaiseWorkOrderPage client={client} />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(await screen.findByText(t("work.raise.fromAsset"))).toBeTruthy();
    // The three-step rail, not the retired one-page form.
    expect(document.querySelector('[data-wizard="rail"]')).not.toBeNull();
    expect(await screen.findByText(t("work.raise.kicker.asset", { asset: "E-5000" }))).toBeTruthy();
    expect(await screen.findByText(t("work.raise.summaryOne", { subject: "E-5000" }))).toBeTruthy();
    expect(await screen.findByText("AC-2026-00001")).toBeTruthy();
    // Premises and units are the asset's own — not asked again.
    expect(screen.queryByRole("combobox", { name: t("work.raise.premises") })).toBeNull();
    // The asset's own (electric) templates, read from `results` — never the
    // one-round `rows` twin.
    const templateSelect = screen.getByLabelText(new RegExp(t("work.raise.template"), "u")) as HTMLSelectElement;
    await waitFor(() =>
      expect(Array.from(templateSelect.options).map((o) => o.textContent).slice(1)).toEqual(
        recorded.results.map((r) => r.name),
      ),
    );

    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText(new RegExp(t("work.raise.type"), "u")), "jt-change");
    await user.selectOptions(templateSelect, recorded.results[0].id);
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
    await screen.findByLabelText(t("work.raise.due"));
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
    await user.click(await screen.findByRole("button", { name: t("work.raise.commit", { count: 1 }) }));
    expect(await screen.findByText(t("work.raise.resultTitle", { count: 1 }))).toBeTruthy();
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toMatchObject({ asset_ids: [ASSET], premises_id: "p-101", source: "assets" });
    expect(post?.body).not.toHaveProperty("unit_ids");
  });
});

describe("DEF-MET-4973 — an asset no template fits is not a dead end", () => {
  it("the refusal under Template is joined by a link to New template, by its address", async () => {
    const calls: Call[] = [];
    const recorded = RECORDED_ASSET_TEMPLATES;
    const ASSET = recorded.asset.id;
    const client = fakeClient(calls, {
      [`/assets/${ASSET}`]: {
        id: ASSET, asset_no: "M-7204", type: "sub_meter", type_name: "Sub-meter", read_method_name: "Walk-by",
        service: "electric", assigned_unit_id: U1, assigned_address: "500 Mason Rd Plaza",
        assigned: true, status: "in_service", status_name: "In service", actions: [], warnings: [],
        specs: { location_note: null },
      },
      [`/units/${U1}`]: unitRow(U1, "Suite 200"),
      [`/units/${U1}/account`]: {
        unit: { id: U1, unit_no: "200", label: "Suite 200", is_common_area: false },
        account: null, facts: null, owner_account: null, no_account_reason: null, facts_unavailable: null,
      },
      // The server's answer for M-7204 on brazosbend: nothing fits.
      [`/assets/${ASSET}/work-order-templates`]: { ...recorded, count: 0, results: [] },
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}/assets/${ASSET}/work-orders/new`]}>
            <Routes>
              <Route path="/:tenant/assets/:assetId/work-orders/new" element={<RaiseWorkOrderPage client={client} />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(await screen.findByText(new RegExp(t("assets.raiseWork.noneApply"), "u"))).toBeTruthy();
    const templateSelect = screen.getByLabelText(new RegExp(t("work.raise.template"), "u")) as HTMLSelectElement;
    expect(templateSelect.disabled).toBe(true);
    const next = await screen.findByRole("link", { name: t("work.templates.new") });
    expect(next.getAttribute("href")).toBe(`/${TENANT}/work/templates/new`);
  });
});
