// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-092-BRC01 step 2 wave C lane 1 — `AST-B-16` (two served Overview
//          figures) · `AST-B-22` (the attention strip) · `AST-B-21` (one
//          lifetime cost, both halves named beneath) · `AST-B-25` (a pencil per
//          panel) · `AST-B-27` (the sub-meter's allocation share).
//          Screens 08, 16, 17, 18, 19, 20, 21.
// Rules:   AST-R-04 (Measurement belongs to measuring kinds only) · AST-R-05
//          (allocation belongs to sub-meters only; a null share is never 0%) ·
//          AST-R-09 (a fact is said once) · AST-R-11 (panel order never varies
//          by kind) · BR-AST-020 (a retired asset takes no edit) ·
//          BR-WRK-051 (the ONE place a job's cost is worked out) ·
//          B14 rule 31 (no database id is ever a visible value).
//
// ⚠ **PROVED RED BEFORE IT WAS TRUSTED GREEN, IN THE HARNESS THAT RUNS IT**
// (hard-won law 7, both halves). Run in a `git worktree` pinned at
// `404ae10c0` — the tip this lane started from — through
// `npx vitest run src/features/assets/AssetOverviewPanels.dom.test.tsx`, which
// is the same entry point CI uses, the file does not compile at all: the
// module under test exports neither `assetOverviewPanelsFor` nor
// `assetAttention`, and `AssetPanelEdits` does not exist. Each case was then
// re-proved individually against the NEW module with its own feature removed —
// the per-case notes below record what each one said.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { AssetDetail, LookupEntry } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import {
  AssetDetailPage,
  assetAttention,
  assetOverviewPanelsFor,
} from "./AssetDetailPage";
import { ALLOCATION_RULES } from "./AssetPanelEdits";
import {
  assetTypesQueryKey,
  meterTypesQueryKey,
  readMethodsQueryKey,
  sizeClassesQueryKey,
} from "./AssetRegistryPage";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function lookup(code: string, name: string, category = ""): LookupEntry {
  return { id: code, code, name, active: true, is_system: true, used_by: 0, category } as LookupEntry;
}

function paged<T>(results: T[]) {
  return { results, page: 1, per: 200, total: results.length };
}

/** A meter with everything on: a costed life, an open job, an allocation-free
 *  measurement block and a full billing chain. Figures are this fixture's own
 *  and are NOT read off the drawing — B14 rule 37. */
function detail(over: Partial<AssetDetail> = {}): AssetDetail {
  return {
    id: "a-7001",
    asset_no: "M-7001",
    serial_no: "3894-A2210",
    external_ref: "LEGACY-88",
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
    size_class: "W-2",
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
      form_class: "2S",
      register_digits: 9,
      firmware_version: "3.2.1",
      seal_no: "SL-88214",
      warranty_end: null,
      last_test_date: "2024-02-01",
      test_interval_months: 96,
      location_note: "Pit at the kerb, north side",
      allocation_rule: null,
      loss_tolerance_pct: null,
      allocation_share_pct: null,
    },
    classifications: {
      asset_type: { code: "meter", name: "Meter" },
      meter_type: { code: "ami", name: "AMI" },
      read_method: { code: "ami", name: "AMI" },
    },
    billing_chain: {
      premises_id: "p-1",
      premise_no: "P-00004",
      premise_address: "118 Bayou Bend Dr",
      unit_id: "u-1",
      unit_label: "Unit 1",
      account: {
        id: "acc-1",
        account_no: "ACC-20194",
        customer_name: "Ruth Alvarez",
        status: "active",
      },
    },
    sub_assets: [],
    valuation: {
      supplier: "Badger Meter",
      purchase_cost: "182.0000",
      purchase_date: "2021-04-02",
      warranty_end: "2026-03-01",
      warranty_covered: false,
      depreciation_method: "straight_line",
      present_value: "54.6000",
      currency: "USD",
    },
    lifecycle: {
      age_months: 31,
      expected_life_years: 10,
      certification_due: "2032-02-01",
      replacement_year: 2034,
    },
    linked_meter: null,
    cost_rollup: {
      // ⚠ **A PAIR CHOSEN SO THE TWO ROUNDINGS DISAGREE, WHICH THE FIRST PAIR
      // DID NOT.** `BR-WRK-051`: the total is the sum of the two ROUNDED
      // displayed halves. 84.0060 → $84.01 and 138.4160 → $138.42, so the
      // figure is $222.43; sum-then-round is 222.4220 → $222.42. The pair this
      // file first carried (84.0000 / 138.4150) gives $222.42 BOTH ways, so
      // TC-C1 passed against a deliberately wrong implementation — it was
      // proved by flipping the fixture and watching it stay green, which is
      // law 7's *what would make this check pass wrongly* asked out loud.
      maintenance: "84.0060",
      work: "138.4160",
      lifetime: "222.4300",
      jobs_costed: 1,
      open_work_orders: 2,
      currency: "USD",
    },
    ...over,
  } as AssetDetail;
}

/**
 * ⚠ **THE STUB ANSWERS WITH THE ASSET UNDER TEST, NOT A CONSTANT.** It used to
 * answer `detail()` for every `/assets/{id}` read, so seeding the query cache
 * with a SUB-METER rendered the sub-meter for one frame and then react-query's
 * own refetch replaced it with the meter. The synchronous cases passed, the
 * awaited ones failed, and the failure named a missing `Allocation rule`
 * control on a screen that was drawing a meter. A fixture that cannot tell one
 * asset from another is law 7's *looking at the wrong thing*, one layer down.
 */
function stubClient(
  asset: AssetDetail,
  sent: { method: string; path: string; body: unknown }[],
): ApiClient {
  const answer = <T,>(data: unknown = {}) => ({
    data: data as T,
    status: 200,
    headers: new Headers(),
  });
  return {
    request: <T,>(path: string, options?: { method?: string; body?: unknown }) => {
      sent.push({ method: options?.method ?? "GET", path, body: options?.body });
      return Promise.resolve(answer<T>());
    },
    get: <T,>(path: string, options?: { query?: Record<string, unknown> }) => {
      // `DEF-AST-5117` — GETs are RECORDED now, WITH THEIR QUERY. Only
      // `request` was pushed before, so nothing here could say which page a
      // panel asked for — and the page does not travel in the path: the house
      // reader passes it as `client.get(path, { query })`, so a case reading
      // only the path sees two identical requests and concludes the pager is
      // dead when it is working.
      sent.push({ method: "GET", path, body: options?.query });
      // ⚠ **THE PERMISSIONS READ IS NOT OPTIONAL FURNITURE.** `useAccessCell`
      // reads `permissions.permissions.find(...)`, so a catch-all stub that
      // answers `{results: []}` throws inside the component and every
      // assertion below would fail for a reason that has nothing to do with
      // what it is testing — law 7's *looking at the wrong thing*, in a
      // fixture. A `Full` cell is what a clerk with write actually has.
      if (path === "/me/permissions") {
        return Promise.resolve(
          answer<T>({ permissions: [{ code: "premises_accounts", access: "Full" }] }),
        );
      }
      if (path.startsWith("/assets/") && !path.includes("/", 8)) {
        return Promise.resolve(answer<T>(asset));
      }
      // `DEF-AST-5117` — THE THREE PAGED LISTS ANSWER A REAL SECOND PAGE.
      // A stub that answers `count: 0` leaves `ListPager`'s Next DISABLED, so
      // a case could press it, see no request, and blame the screen: a fixture
      // that cannot reach page two cannot test paging (law 7's *incapable of
      // passing*). 120 rows at 50 a page is three.
      if (/\/(reads|assignments|maintenance)(\?|$)/.test(path)) {
        return Promise.resolve(
          answer<T>({ count: 120, next: `${path}&page=2`, previous: null, results: [] }),
        );
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

function mount(
  asset: AssetDetail,
  sent: { method: string; path: string; body: unknown }[] = [],
  search = "",
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(["assets", "detail", asset.id], asset);
  queryClient.setQueryData(readMethodsQueryKey, paged([lookup("ami", "AMI")]));
  queryClient.setQueryData(sizeClassesQueryKey, paged([lookup("W-2", 'Water 2"')]));
  queryClient.setQueryData(
    assetTypesQueryKey,
    paged([lookup("meter", "Meter", "meters"), lookup("sub_meter", "Sub-meter", "sub_meters")]),
  );
  queryClient.setQueryData(meterTypesQueryKey, paged([lookup("ami", "AMI")]));
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* Mounted under the REAL path pattern — a bare MemoryRouter leaves
            `useParams().tenant` undefined and every address comes out
            protocol-relative, which reads as a good string to `toContain`. */}
        <MemoryRouter initialEntries={[`/brazosbend/assets/${asset.id}${search}`]}>
          <Routes>
            <Route
              path="/:tenant/assets/:assetId"
              element={
                <AssetDetailPage
                  client={stubClient(asset, sent)}
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

// ── The panel set, derived ─────────────────────────────────────────────────

describe("AST-R-08/R-11 — the Overview panel set is DERIVED and its order never varies", () => {
  it("TC-P1: a meter draws all six, in the drawn reading order", () => {
    expect(assetOverviewPanelsFor({ tab: "meters", export_capacity_kw: null })).toEqual([
      "assignment",
      "due",
      "measurement",
      "device",
      "cost",
      "lifecycle",
    ]);
  });

  it("TC-P2: a plain device has NO Measurement panel — absent, not empty (AST-R-02/R-04)", () => {
    // RED PROOF: with the `measures` predicate removed the array came back with
    // six entries and this failed naming `measurement`.
    expect(assetOverviewPanelsFor({ tab: "behind_the_meter", export_capacity_kw: null })).toEqual([
      "assignment",
      "due",
      "device",
      "cost",
      "lifecycle",
    ]);
  });

  it("TC-P3: an exporting inverter keeps Measurement for its capacity alone", () => {
    expect(
      assetOverviewPanelsFor({ tab: "behind_the_meter", export_capacity_kw: "7.5000" }),
    ).toContain("measurement");
  });

  it("TC-P4: a kind that skips a panel CLOSES THE GAP — the set is always a subsequence", () => {
    const canonical = assetOverviewPanelsFor({ tab: "meters", export_capacity_kw: null });
    const device = assetOverviewPanelsFor({ tab: "behind_the_meter", export_capacity_kw: null });
    let cursor = 0;
    for (const panel of device) {
      cursor = canonical.indexOf(panel, cursor);
      expect(cursor).toBeGreaterThan(-1);
      cursor += 1;
    }
  });
});

// ── AST-B-22 — the attention strip ─────────────────────────────────────────

describe("AST-B-22 — the header earns its attention strip, and its SILENCE is the feature", () => {
  it("TC-A1: a healthy asset gets NO strip at all", () => {
    expect(
      assetAttention({
        test_due: false,
        valuation: { warranty_covered: true, warranty_end: "2029-01-01" },
        lifecycle: { certification_due: "2032-02-01" },
      } as never),
    ).toBeNull();
    const { container } = mount(
      detail({ valuation: { ...detail().valuation, warranty_covered: true } } as never),
    );
    expect(container.querySelector("[data-attention]")).toBeNull();
  });

  it("TC-A2: an overdue test states it AND carries the control that resolves it", () => {
    const { container } = mount(detail({ test_due: true }));
    const strip = container.querySelector('[data-attention="testOverdue"]');
    expect(strip).not.toBeNull();
    expect(strip?.textContent).toContain(t("assets.attention.testOverdue"));
    // The drawing's own split: this line offers the raise door; the quieter
    // line below does not, because there is nothing to DO about it.
    expect(strip?.querySelector("a[href*='/work-orders/new']")).not.toBeNull();
  });

  it("TC-A3: an expired warranty uses the quieter register and offers NO action", () => {
    const { container } = mount(detail());
    const strip = container.querySelector('[data-attention="warrantyEnded"]');
    expect(strip).not.toBeNull();
    expect(strip?.querySelector("a[href*='/work-orders/new']")).toBeNull();
  });

  it("TC-A4: the overdue test WINS over an expired warranty — one strip, never two", () => {
    const { container } = mount(detail({ test_due: true }));
    expect(container.querySelectorAll("[data-attention]").length).toBe(1);
  });
});

// ── AST-B-16 + AST-B-21 — the two served figures ───────────────────────────

describe("AST-B-16 / AST-B-21 — two SERVED figures, and one lifetime cost with both halves named", () => {
  it("TC-C1: the lifetime figure is the sum of the two DISPLAYED halves (BR-WRK-051)", () => {
    const { container } = mount(detail());
    const cell = container.querySelector("[data-lifetime-cost]");
    expect(cell).not.toBeNull();
    const text = cell?.textContent ?? "";
    // $84.01 + $138.42 = $222.43 — NOT $222.42, which is what summing the
    // stored 4-dp values and rounding once prints over these same two lines.
    expect(text).toContain("$222.43");
    expect(text).toContain("$84.01");
    expect(text).toContain("$138.42");
    // Both halves NAMED beneath — the PO's own words.
    expect(text).toContain(t("assets.cost.repairsHalf"));
    expect(text).toContain(t("assets.cost.jobsHalf"));
  });

  it("TC-C2: money displays at 2 dp however many it is stored to (hard rule 2)", () => {
    const { container } = mount(detail());
    expect(container.textContent).not.toContain("222.4300");
    expect(container.textContent).not.toContain("138.4160");
  });

  it("TC-C3: the open-work count is a SERVED number, and 0 renders as 0 rather than a dash", () => {
    const { container } = mount(
      detail({ cost_rollup: { ...detail().cost_rollup!, open_work_orders: 0 } }),
    );
    expect(container.querySelector("[data-open-work]")?.textContent).toBe("0");
  });

  it("TC-C4: an OLDER payload with no rollup draws the quiet dash, never a zero", () => {
    const without = detail();
    delete (without as { cost_rollup?: unknown }).cost_rollup;
    const { container } = mount(without);
    expect(container.querySelector("[data-open-work]")).toBeNull();
    expect(container.querySelector("[data-lifetime-cost]")).toBeNull();
  });
});

// ── AST-B-25 — a pencil per panel ──────────────────────────────────────────

describe("AST-B-25 — a pencil per panel, and Assignment has none on any kind", () => {
  it("TC-E1: five pencils on a meter, and NOT one on Assignment", () => {
    const { container } = mount(detail());
    for (const panel of ["due", "measurement", "device", "cost", "lifecycle"]) {
      expect(container.querySelector(`[data-testid="edit-${panel}"]`)).not.toBeNull();
    }
    expect(container.querySelector('[data-testid="edit-assignment"]')).toBeNull();
  });

  it("TC-E2: a RETIRED asset shows no pencil at all (BR-AST-020 — the server refuses first)", () => {
    const { container } = mount(detail({ status: "retired", actions: ["view"] }));
    expect(container.querySelectorAll('[data-testid^="edit-"]').length).toBe(0);
  });

  it("TC-E3: the Device pencil opens nine fields and sends them (external reference included)", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    mount(detail(), sent);
    await userEvent.click(screen.getByRole("button", { name: t("assets.panel.edit.device") }));
    expect(screen.getByText(t("assets.panel.title.device"))).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: t("assets.panel.save") }));
    const patch = sent.find((call) => call.method === "PATCH");
    expect(patch).toBeDefined();
    // Served on every row since the module shipped, written by the import
    // alone, typable from a screen for the first time.
    expect(Object.keys(patch?.body as object).sort()).toEqual([
      "external_ref",
      "firmware_version",
      "form_class",
      "manufacturer_model",
      "meter_type",
      "seal_no",
      "serial_no",
      "type",
    ]);
  });

  it("TC-E4: the Cost pencil sends the PURCHASE DATE — DEF-MET-4972's remaining half", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    mount(detail(), sent);
    await userEvent.click(screen.getByRole("button", { name: t("assets.panel.edit.cost") }));
    await userEvent.click(screen.getByRole("button", { name: t("assets.panel.save") }));
    const patch = sent.find((call) => call.method === "PATCH");
    expect(patch?.body).toMatchObject({ purchase_date: "2021-04-02" });
  });

  it("TC-E5: the Lifecycle pencil sends exactly two keys", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    mount(detail(), sent);
    await userEvent.click(screen.getByRole("button", { name: t("assets.panel.edit.lifecycle") }));
    await userEvent.click(screen.getByRole("button", { name: t("assets.panel.save") }));
    const patch = sent.find((call) => call.method === "PATCH");
    expect(Object.keys(patch?.body as object).sort()).toEqual(["install_date", "location_note"]);
  });
});

// ── 17 + 18 — the measurement confirm step ─────────────────────────────────

describe("Screens 17 + 18 — Continue, never Save, when a reading's MEANING changes", () => {
  it("TC-M1: nothing billing-affecting changed → the button reads Save and posts at once", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    mount(detail(), sent);
    await userEvent.click(
      screen.getByRole("button", { name: t("assets.panel.edit.measurement") }),
    );
    expect(screen.getByRole("button", { name: t("assets.panel.save") })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: t("assets.panel.save") }));
    expect(sent.some((call) => call.method === "PATCH")).toBe(true);
  });

  it("TC-M2: changing the multiplier makes it Continue, and the second step SAVES", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    mount(detail(), sent);
    await userEvent.click(
      screen.getByRole("button", { name: t("assets.panel.edit.measurement") }),
    );
    const multiplier = screen.getByLabelText(t("assets.form.multiplier"));
    await userEvent.clear(multiplier);
    await userEvent.type(multiplier, "10");
    const advance = screen.getByRole("button", { name: t("assets.panel.continue") });
    expect(advance).toBeInTheDocument();
    // NOTHING is posted by pressing Continue — the PATCH fires on step two.
    await userEvent.click(advance);
    expect(sent.some((call) => call.method === "PATCH")).toBe(false);
    expect(screen.getByText(t("assets.panel.title.measurementConfirm"))).toBeInTheDocument();
    expect(screen.getByText(t("assets.panel.forwardOnly.two"))).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: t("assets.panel.save") }));
    expect(sent.find((call) => call.method === "PATCH")?.body).toMatchObject({
      multiplier: "10",
    });
  });

  it("TC-M3: Back returns the TYPED value rather than discarding it (one modal, two steps)", async () => {
    mount(detail());
    await userEvent.click(
      screen.getByRole("button", { name: t("assets.panel.edit.measurement") }),
    );
    const multiplier = screen.getByLabelText(t("assets.form.multiplier"));
    await userEvent.clear(multiplier);
    await userEvent.type(multiplier, "10");
    await userEvent.click(screen.getByRole("button", { name: t("assets.panel.continue") }));
    await userEvent.click(screen.getByRole("button", { name: t("assets.panel.back") }));
    expect(screen.getByLabelText(t("assets.form.multiplier"))).toHaveValue("10");
  });
});

// ── AST-B-27 — the sub-meter's allocation share ────────────────────────────

const SUB = (): AssetDetail =>
  detail({
    id: "a-2001",
    asset_no: "S-2001",
    tab: "sub_meters",
    type: "sub_meter",
    parent_asset_no: "E-5000",
    parent_asset_id: "a-5000",
    specs: {
      ...detail().specs,
      allocation_share_pct: "33.333333",
      allocation_rule: "equal",
      loss_tolerance_pct: "2.000000",
    },
  });

describe("AST-B-27 — allocation belongs to sub-meters, and the four words are RATIFIED", () => {
  it("TC-Q1: the three rows render on a sub-meter and NOWHERE else (AST-R-05)", () => {
    const sub = mount(SUB());
    expect(sub.container.textContent).toContain(t("assets.spec.allocationShare"));
    expect(sub.container.textContent).toContain(t("assets.spec.lossTolerance"));
    cleanup();
    const meter = mount(detail());
    expect(meter.container.textContent).not.toContain(t("assets.spec.lossTolerance"));
  });

  it("TC-Q2: the RULE renders in words, never as its stored code (B14 rule 31)", () => {
    const { container } = mount(SUB());
    expect(container.textContent).toContain(t("assets.allocationRule.equal"));
    expect(container.textContent).toContain("Split equally");
    for (const code of ALLOCATION_RULES) {
      // The code itself is never a visible value.
      expect(container.textContent).not.toContain(`>${code}<`);
    }
  });

  it("TC-Q3: a null share reads METERED, NOT ALLOCATED — never 0%", () => {
    const { container } = mount(
      SUB()
        ? ({
            ...SUB(),
            specs: { ...SUB().specs, allocation_share_pct: null },
          } as AssetDetail)
        : SUB(),
    );
    expect(container.textContent).toContain(t("assets.spec.allocationShareMetered"));
    expect(container.textContent).not.toContain("0.00%");
  });

  it("TC-Q4: the Measurement dialog sends all three allocation keys on a sub-meter", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    mount(SUB(), sent);
    await userEvent.click(
      screen.getByRole("button", { name: t("assets.panel.edit.measurement") }),
    );
    // All four ratified words are offered, IN THE RATIFIED ORDER. Read off the
    // `<select>`'s own options rather than through `getByRole("option")`: a
    // closed native select does not expose its options to the accessibility
    // tree in jsdom, so the role query answers nothing and the assertion would
    // fail over a control that is perfectly correct.
    const rule = screen.getByLabelText(t("assets.spec.allocationRule")) as HTMLSelectElement;
    expect(Array.from(rule.options).map((option) => option.textContent)).toEqual([
      t("assets.form.unset"),
      ...ALLOCATION_RULES.map((code) => t(`assets.allocationRule.${code}`)),
    ]);
    await userEvent.click(screen.getByRole("button", { name: t("assets.panel.save") }));
    const patch = sent.find((call) => call.method === "PATCH");
    expect(patch?.body).toMatchObject({
      allocation_share_pct: "33.333333",
      allocation_rule: "equal",
      loss_tolerance_pct: "2.000000",
    });
  });
});

// ── AST-R-07 / AST-R-09 — the links, and saying a fact once ────────────────

describe("The Assignment panel's chain ends at the MONEY, and a fact is said once", () => {
  it("TC-L1: the account is a LINK — the chain no longer runs Premises → Unit → dead end", () => {
    const { container } = mount(detail());
    expect(container.querySelector('a[href="/brazosbend/accounts/acc-1"]')).not.toBeNull();
  });

  it("TC-L2: a sub-meter's master is a LINK, not plain text (AST-R-07)", () => {
    const { container } = mount(SUB());
    expect(container.querySelector('a[href="/brazosbend/assets/a-5000"]')).not.toBeNull();
  });

  it("TC-L3: no uuid is ever a rendered value (B14 rule 31 / AST-R-10)", () => {
    const { container } = mount(detail());
    expect(container.textContent).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
    );
  });

  it("TC-L4: every panel label is at most TWO words (AST-R-12)", () => {
    const { container } = mount(detail());
    for (const heading of Array.from(container.querySelectorAll("h3"))) {
      const words = (heading.textContent ?? "").replace(/&/g, "and").trim().split(/\s+/);
      expect(words.length).toBeLessThanOrEqual(3); // "Cost and value" — & counts as its word
    }
  });
});

// ── The three panels that page (DEF-AST-5117) ──────────────────────────────

/**
 * ⚠ **`AST-B-19` MOVED FOUR PANELS ONTO SERVER PAGING AND BUILT THE FOOTER ON
 * ONE OF THEM.** Export and Assignment history were left holding `page`/`per`
 * state that nothing could set — dead UI, hard-won law 2 — and Work &
 * maintenance did not pass a page at all, so it took the server's first one and
 * threw the `total` beside it away. Every existing case passed over all three,
 * because a page of rows renders correctly whether or not a second page is
 * reachable. These cases ask the only question that separates the two: **does
 * pressing the footer make the SERVER answer a different page?**
 *
 * PROVED RED by removing each `ListPager` again: the pager case fails on the
 * footer being absent and the request case on the page-2 read never being made.
 */
/** Did the screen ask the SERVER for that page? The page travels in the query
 *  rather than in the path (`client.get(path, { query })`), so this reads the
 *  recorded query and not the URL. */
function askedForPage(
  sent: { method: string; path: string; body: unknown }[],
  path: string,
  page: number,
): boolean {
  return sent.some(
    (call) => call.path === path && (call.body as { page?: number } | undefined)?.page === page,
  );
}

describe("DEF-AST-5117 — every paged panel carries the footer that drives it", () => {
  /**
   * ⚠ **THE ADDRESS AND THE ENDPOINT ARE NO LONGER THE SAME WORD** — which is
   * why `search` is spelled out per panel rather than derived from `tab`.
   * Screen 12 of `05-prototype/01 Assets Menu Blueprint.pdf` merged Maintenance
   * into `Work & maintenance` at `?tab=work` and split it into two sub-tabs
   * (figure 18, p59); `Open work` is the half a person lands on, so the history
   * table — and the pager this case is about — only renders at
   * `?tab=work&section=history`. The REST path is still `/maintenance`.
   *
   * Deriving the query string from the endpoint name is what made this case
   * mount the wrong half, so the two are now separate fields.
   */
  const panels = [
    { tab: "assignments", search: "?tab=assignments", path: "/assets/a-7001/assignments" },
    { tab: "maintenance", search: "?tab=work&section=history", path: "/assets/a-7001/maintenance" },
  ] as const;

  for (const panel of panels) {
    it(`TC-P-${panel.tab}: the ${panel.tab} panel renders a pager, and Next asks the server for page 2`, async () => {
      const sent: { method: string; path: string; body: unknown }[] = [];
      mount(detail(), sent, panel.search);

      // B14 rule 16 through the kit's own footer — the same `table-pager`
      // furniture `DataTable` uses, so every list in the product has one thing.
      const next = await screen.findByRole("button", { name: t("table.pager.next") });
      expect(document.querySelector(".table-pager")).not.toBeNull();

      await userEvent.click(next);

      await waitFor(() => expect(askedForPage(sent, panel.path, 2)).toBe(true));
    });
  }

  it("TC-P-export: the inverter's Export panel pages its linked meter's reads", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    // `assetDetailTabsFor`: the Export tab exists ONLY on a behind-the-meter
    // asset whose linked meter is a NET meter — anything else has no such tab
    // and `?tab=export` falls back to Overview, which is a fixture that would
    // have tested nothing.
    const inverter = detail({
      tab: "behind_the_meter",
      type: "inverter",
      type_name: "Inverter",
      linked_meter: { id: "m-1", asset_no: "M-4022", net_metering: true },
    } as Partial<AssetDetail>);
    mount(inverter, sent, "?tab=export");

    const next = await screen.findByRole("button", { name: t("table.pager.next") });
    await userEvent.click(next);

    await waitFor(() => expect(askedForPage(sent, "/assets/m-1/reads", 2)).toBe(true));
  });
});
