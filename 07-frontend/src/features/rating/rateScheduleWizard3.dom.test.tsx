// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-157-BRC10 wave B — RAT-03, THREE steps (Details · Pricing ·
//          Review), built from 05-prototype/rate-schedules-2026-10-01/images/
//          40–71. Each case names the image it was written from.
// Rules:   TOU window → register (CR-157 wave A) · seasons store month + day
//          only · the minimum is per meter size (PO 2026-10-01, option A — the
//          per-version minimum is never sent) · BR-RAT-104 (a correction sends
//          no dates) · DEF-RAT-8748 (stored bounds shown trimmed)
// ───────────────────────────────────────────────────────
/**
 * ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 clause 2):
 *   · the step count read off a constant rather than the RENDERED rail — the
 *     first case counts `[data-wizard-step]` elements on the page;
 *   · the register asserted from the draft rather than the screen — the TOU
 *     case reads the read-only cell AND the posted payload;
 *   · a season's year leaking into storage — the seasonal case asserts the
 *     posted season has month/day keys and NO date string anywhere in it.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { ChargeRow, LookupEntry, MyPermissions, ScheduleDetail, TenantServiceRow, VersionRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { RateScheduleThreeStep, detailsProblems } from "./RateScheduleThreeStep";
import { registerForWindow, seasonFromPicker, seasonPickerValue, shownQuantity, shownRate } from "./rateScheduleWizardParts";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

const PERMISSIONS = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "plans_rates", label: "Plans & Rates", access: "Full" }],
} as unknown as MyPermissions;

const SERVICES = [
  { service: "water", name: "Water", enabled: true, primary_uom: "kgal", alt_uom: null, billed_uom: null },
  { service: "electric", name: "Electric", enabled: true, primary_uom: "kWh", alt_uom: null, billed_uom: null },
] as unknown as TenantServiceRow[];

const lookup = (code: string, name: string, service: string) =>
  ({ id: code, code, name, active: true, is_system: true, used_by: 0, service: { id: service, code: service } }) as unknown as LookupEntry;
const UOMS = [lookup("kgal", "kgal", "water"), lookup("kWh", "kWh", "electric")];
const SIZES = [
  lookup("W-1", 'Water 1"', "water"),
  lookup("W-34", 'Water 3/4"', "water"),
  lookup("W-58", 'Water 5/8"', "water"),
  lookup("E-100", "100 A", "electric"),
];
const CLASSES = [
  { id: "at-res", code: "residential", name: "Residential", active: true, is_system: true, used_by: 0 },
] as unknown as LookupEntry[];

function base(code: string, service: string, sizes: [string, string | null][]): ChargeRow {
  return {
    id: `chg-${code}`,
    code,
    name: `${code} base`,
    service,
    is_base: true,
    status: "active",
    amount: null,
    amount_display: null,
    size_amounts: sizes.map(([size_class, amount]) => ({
      size_class,
      customer_class: null,
      amount: amount === null ? null : `${amount}00`,
      amount_display: amount,
      currency: "USD",
    })),
  } as unknown as ChargeRow;
}
const BASE_W = base("BASE-W", "water", [
  ["W-58", "8.00"],
  ["W-34", "8.00"],
]);
const BASE_E = base("BASE-E", "electric", [["E-100", "12.00"]]);

interface Stub {
  client: ApiClient;
  posts: { path: string; body: Record<string, unknown> }[];
}

function stub(detail: ScheduleDetail | null = null): Stub {
  const posts: Stub["posts"] = [];
  const ok = <T,>(data: T) => ({ status: 200, data, etag: null, notModified: false });
  const saved = (body: Record<string, unknown>) =>
    ({ ...(detail ?? {}), id: detail?.id ?? "t-new", name: String(body.name ?? detail?.name ?? ""), status: "active", scheduled_change: null, notices: [] }) as unknown as ScheduleDetail;
  const client = {
    get: vi.fn(async (path: string) => {
      if (path.startsWith("/lookups/uoms")) return ok({ count: UOMS.length, results: UOMS });
      if (path.startsWith("/lookups/service_size_classes")) return ok({ count: SIZES.length, results: SIZES });
      if (path.startsWith("/lookups/")) return ok({ count: CLASSES.length, results: CLASSES });
      if (path === "/charges") return ok({ count: 2, next: null, previous: null, results: [BASE_W, BASE_E] });
      if (path.startsWith("/rate-schedules/") && detail !== null) return ok(detail);
      if (path.startsWith("/rate-schedules/percent-basis-options")) return ok({ results: [] });
      throw new Error(`no stub for ${path}`);
    }),
    post: vi.fn(async (path: string, body: Record<string, unknown>) => {
      posts.push({ path, body });
      return ok(saved(body));
    }),
    request: vi.fn(async (path: string, options: { body: Record<string, unknown> }) => {
      posts.push({ path, body: options.body });
      return ok(saved(options.body));
    }),
  } as unknown as ApiClient;
  return { client, posts };
}

function mount(s: Stub, url: string, pattern: string, services: TenantServiceRow[] = SERVICES) {
  const user = userEvent.setup();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  qc.setQueryData(queryKeys.tenantServices, services);
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={[url]}>
          <Routes>
            <Route
              path={pattern}
              element={<RateScheduleThreeStep client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" displayYear={2026} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return user;
}
const mountAdd = (s: Stub) => mount(s, `/${TENANT}/plans-rates/rates/new`, "/:tenant/plans-rates/rates/new");
const mountEdit = (s: Stub, id: string) =>
  mount(s, `/${TENANT}/plans-rates/rates/${id}/edit`, "/:tenant/plans-rates/rates/:tariffId/edit");

const continueButton = () => screen.getByRole("button", { name: t("wizard.continue") });
const pageText = () => document.body.textContent ?? "";
const select = (id: string) => document.getElementById(id) as HTMLSelectElement;

afterEach(() => cleanup());

/** Step 1, filled in for `service` and `model` — the shortest path to step 2. */
async function details(user: ReturnType<typeof userEvent.setup>, service: string, model: string, name = "Water — Residential 2027") {
  await waitFor(() => expect(select("rs-service")).toBeInTheDocument());
  await waitFor(() => expect(select("rs-service").options.length).toBeGreaterThan(1));
  await user.type(document.getElementById("rs-name") as HTMLInputElement, name);
  await user.selectOptions(select("rs-service"), service);
  await waitFor(() => expect(select("rs-unit").value).not.toBe(""));
  await user.selectOptions(select("rs-structure"), model);
}

describe("RAT-03 — THREE steps (40-add-1-details.png)", () => {
  it("the rail draws Details · Pricing · Review and nothing else", async () => {
    mountAdd(stub());
    await waitFor(() => expect(document.querySelectorAll("[data-wizard-step]").length).toBe(3));
    const labels = [...document.querySelectorAll("[data-wizard-step]")].map((node) => node.textContent ?? "");
    expect(labels[0]).toContain(t("rating.rs.wiz.step.details"));
    expect(labels[1]).toContain(t("rating.rs.wiz.step.pricing"));
    expect(labels[2]).toContain(t("rating.rs.wiz.step.review"));
  });

  it("step 1 refuses a missing name and base code in the drawn words (43-add-1-errors.png)", async () => {
    const user = mountAdd(stub());
    await waitFor(() => expect(select("rs-service").options.length).toBeGreaterThan(1));
    await user.click(continueButton());
    await waitFor(() => expect(pageText()).toContain(t("rating.rs.wiz.err.name")));
    expect(pageText()).toContain(t("rating.rs.wiz.err.baseCode"));
    expect(document.querySelector('[data-wizard-step="1"]')?.getAttribute("data-state")).toBe("active");
  });

  it("the summary aside follows step 1 — service, structure, unit, class, base code, sizes", async () => {
    const user = mountAdd(stub());
    await details(user, "water", "tiered");
    const aside = document.querySelector("[data-rs-aside]")?.textContent ?? "";
    expect(aside).toContain("Water — Residential 2027");
    expect(aside).toContain("Tiered");
    expect(aside).toContain("kgal");
    expect(aside).toContain(t("rating.rs.everyClass"));
    expect(aside).toContain("BASE-W"); // the service's one declared base, picked for the clerk
    expect(aside).toContain(t("rating.rs.wiz.nothingSaved"));
  });
});

describe("RAT-03 step 2 — Pricing (44–52)", () => {
  it("TOU: the Window is a dropdown and the Register follows it, read-only (46-add-2-pricing-tou.png)", async () => {
    const s = stub();
    const user = mountAdd(s);
    await details(user, "electric", "time_of_use", "Electric TOU");
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-array="rs-usage-rows"]')).toBeInTheDocument());
    await user.click(document.querySelector('[data-array="rs-usage-rows"] [data-array-action="add-window"]') as HTMLButtonElement);
    const windowSelect = document.querySelector('[data-cell="window-0"]') as HTMLSelectElement;
    expect(windowSelect.tagName).toBe("SELECT");
    await user.selectOptions(windowSelect, "On-peak");
    expect(document.querySelector("[data-register]")?.getAttribute("data-register")).toBe("tou_on");
    expect(document.querySelector("[data-register]")?.textContent).toBe(t("rating.rs.window.tou_on"));
    await user.selectOptions(windowSelect, "Off-peak");
    expect(document.querySelector("[data-register]")?.getAttribute("data-register")).toBe("tou_off");
    // Days is a dropdown of the product's own three day types.
    const days = document.querySelector('[data-cell="days-0"]') as HTMLSelectElement;
    expect([...days.options].map((option) => option.value).filter(Boolean)).toEqual(["weekday", "weekend", "holiday"]);
  });

  it("TOU: the first window brings one whole-year season, or the server refuses (rating.seasons.required)", async () => {
    const s = stub();
    const user = mountAdd(s);
    await details(user, "electric", "time_of_use", "Electric TOU");
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-array="rs-usage-rows"]')).toBeInTheDocument());
    await user.click(document.querySelector('[data-array="rs-usage-rows"] [data-array-action="add-window"]') as HTMLButtonElement);
    await user.selectOptions(document.querySelector('[data-cell="window-0"]') as HTMLSelectElement, "On-peak");
    fireEvent.change(document.querySelector('[data-cell="starts-0"]') as HTMLInputElement, { target: { value: "00:00" } });
    fireEvent.change(document.querySelector('[data-cell="ends-0"]') as HTMLInputElement, { target: { value: "00:00" } });
    await user.type(document.querySelector('[data-cell="window-price-0"]') as HTMLInputElement, "0.11");
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="review"]')).toBeInTheDocument());
    fireEvent.change(document.getElementById("rs-effective-from") as HTMLInputElement, { target: { value: "2027-01-01" } });
    await user.click(screen.getByRole("button", { name: t("rating.rs.wiz.create") }));
    await waitFor(() => expect(s.posts.length).toBeGreaterThan(0));
    const structure = s.posts[s.posts.length - 1].body.structure as {
      seasons: { label: string; start_month: string; end_month: string; end_day: string }[];
      windows: { season: string }[];
    };
    expect(structure.seasons).toHaveLength(1);
    expect(structure.seasons[0]).toMatchObject({ label: t("rating.rs.wiz.allYear"), start_month: "1", end_month: "12", end_day: "31" });
    expect(structure.windows[0].season).toBe(t("rating.rs.wiz.allYear"));
  });

  it("seasonal: date pickers in, month + day out — no year is ever stored (48-add-2-pricing-seasonal.png)", async () => {
    const s = stub();
    const user = mountAdd(s);
    await details(user, "water", "seasonal", "Irrigation seasonal");
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-array="rs-usage-rows"]')).toBeInTheDocument());
    const addSeason = document.querySelector('[data-array="rs-usage-rows"] [data-array-action="add-season"]') as HTMLButtonElement;
    await user.click(addSeason);
    await user.click(addSeason);
    fireEvent.change(document.querySelector('[data-cell="season-0"]') as HTMLInputElement, { target: { value: "Summer" } });
    fireEvent.change(document.querySelector('[data-cell="season-start-0"]') as HTMLInputElement, { target: { value: "2026-05-01" } });
    fireEvent.change(document.querySelector('[data-cell="season-end-0"]') as HTMLInputElement, { target: { value: "2026-09-30" } });
    fireEvent.change(document.querySelector('[data-cell="season-1"]') as HTMLInputElement, { target: { value: "Winter" } });
    fireEvent.change(document.querySelector('[data-cell="season-start-1"]') as HTMLInputElement, { target: { value: "2026-10-01" } });
    fireEvent.change(document.querySelector('[data-cell="season-end-1"]') as HTMLInputElement, { target: { value: "2027-04-30" } });
    // A season crossing New Year shows its end in the NEXT year, never before its start.
    expect((document.querySelector('[data-cell="season-end-1"]') as HTMLInputElement).value).toBe("2027-04-30");
    expect(pageText()).toContain(t("rating.rs.wiz.repeatsEveryYear"));
    // Save draft from step 3 posts what the screen holds.
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="review"]')).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: t("rating.rs.wiz.saveDraft") }));
    await waitFor(() => expect(s.posts.length).toBe(1));
    const structure = s.posts[0].body.structure as { seasons: Record<string, unknown>[] };
    expect(structure.seasons[0]).toMatchObject({ label: "Summer", start_month: "5", start_day: "1", end_month: "9", end_day: "30" });
    expect(structure.seasons[1]).toMatchObject({ label: "Winter", start_month: "10", start_day: "1", end_month: "4", end_day: "30" });
    expect(JSON.stringify(structure.seasons)).not.toMatch(/\d{4}-\d{2}-\d{2}/);
  });

  it("base rates: one row per size, base read-only from the code, Not priced where it has none (51)", async () => {
    const user = mountAdd(stub());
    await details(user, "water", "tiered");
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-array="rs-base-rows"]')).toBeInTheDocument());
    const add = document.querySelector('[data-array="rs-base-rows"] [data-array-action="add-size"]') as HTMLButtonElement;
    await user.click(add);
    await user.selectOptions(document.querySelector('[data-cell="size-0"]') as HTMLSelectElement, "W-1");
    expect(pageText()).toContain(t("rating.rs.notPriced"));
    expect(pageText()).toContain(t("rating.rs.wiz.notPricedLead", { missing: 1, total: 1 }));
    await user.click(add);
    await user.selectOptions(document.querySelector('[data-cell="size-1"]') as HTMLSelectElement, "W-58");
    expect(pageText()).toContain("$8.00");
    expect(pageText()).toContain(t("rating.rs.wiz.basePricedOf", { code: "BASE-W", priced: 1, total: 2 }));
    // The minimum is the size's own box (option A); blank reads No minimum.
    expect((document.querySelector('[data-cell="minimum-0"]') as HTMLInputElement).placeholder).toBe(t("rating.rs.noMinimum"));
  });

  it("DEF-RAT-8841: the TOU Window and Days dropdowns keep a floor width beside the time pickers (46)", async () => {
    // and the two time pickers a fixed width (they took the row before).
    const user = mountAdd(stub());
    await details(user, "electric", "time_of_use");
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-array="rs-usage-rows"]')).toBeInTheDocument());
    const addUsage = document.querySelectorAll('[data-step="pricing"] [data-array-action]');
    await user.click(addUsage[addUsage.length - 1] as HTMLButtonElement);
    for (const name of ["window-0", "days-0", "window-price-0"]) {
      // jsdom draws nothing, so the floor is read where it is declared; the
      // wave C photograph of image 46 is the proof that it holds on screen.
      const wrapper = (document.querySelector(`[data-cell="${name}"]`) as HTMLElement).closest(".min-w-24");
      expect(wrapper, name).not.toBeNull();
    }
    expect((document.querySelector("[data-register]") as HTMLElement).className).toContain("whitespace-nowrap");
  });

  it("DEF-RAT-8830: a row stays where it was added when its size is picked, and keeps focus", async () => {
    const user = mountAdd(stub());
    await details(user, "water", "tiered");
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-array="rs-base-rows"]')).toBeInTheDocument());
    const add = document.querySelector('[data-array="rs-base-rows"] [data-array-action="add-size"]') as HTMLButtonElement;
    const cell = (name: string) => document.querySelector(`[data-cell="${name}"]`) as HTMLInputElement & HTMLSelectElement;
    await user.click(add);
    await user.selectOptions(cell("size-0"), "W-1");
    await user.type(cell("minimum-0"), "40.00");
    await user.click(add);
    // 5/8" sorts before 1": picked into the SECOND row, it must stay there.
    await user.selectOptions(cell("size-1"), "W-58");
    expect(document.activeElement).toBe(cell("size-1"));
    expect([cell("size-0").value, cell("size-1").value]).toEqual(["W-1", "W-58"]);
    await user.type(cell("minimum-1"), "15.00");
    expect([cell("minimum-0").value, cell("minimum-1").value]).toEqual(["40.00", "15.00"]);
  });

  it("the size list reads 5/8\", not Water 5/8\" — the service has its own column (45-add-2-pricing-tiered.png)", async () => {
    const user = mountAdd(stub());
    await details(user, "water", "tiered");
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-array="rs-base-rows"]')).toBeInTheDocument());
    await user.click(document.querySelector('[data-array="rs-base-rows"] [data-array-action="add-size"]') as HTMLButtonElement);
    const sizes = document.querySelector('[data-cell="size-0"]') as HTMLSelectElement;
    expect([...sizes.options].filter((option) => option.value !== "").map((option) => option.textContent)).toEqual([
      '5/8"',
      '3/4"',
      '1"',
    ]);
  });
});

const STORED_TIERS = [
  { seq: 1, season: null, size_class: null, from_qty: "0.000000", to_qty: "5.000000", unit_price: "4.409600", from_qty_display: "0 kgal", to_qty_display: "5 kgal" },
  { seq: 2, season: null, size_class: null, from_qty: "5.000000", to_qty: null, unit_price: "5.210000", from_qty_display: "5 kgal", to_qty_display: null },
];
const IN_FORCE: VersionRow = {
  id: "v-3",
  corrects: null,
  superseded_by: null,
  correction_reason: null,
  corrected_by: null,
  model: "tiered",
  uom: "kgal",
  currency: "USD",
  base_charge: null,
  base_charge_code: "chg-BASE-W",
  minimum_bill: "17.000000",
  base_charge_display: null,
  minimum_bill_display: "17.00",
  size_rows: [{ size_class: "W-58", minimum_bill: "8.000000", minimum_bill_display: "8.00", currency: "USD" }],
  filing_authority: null,
  filed_on: null,
  regulator_approved_on: null,
  regulator_approver: null,
  effective_from: "2026-01-01",
  effective_to: null,
  approved_by: null,
  submitted_by: null,
  version_label: null,
  change_reason: "Board approved",
  regulator_ref: "Docket 25-114",
  notify_customers: false,
  publish_public: false,
  structure: { model: "tiered", unit: "kgal", currency: "USD", tiers: STORED_TIERS },
} as unknown as VersionRow;
const LIVE = {
  id: "t-water",
  name: "Water — Residential",
  service: "water",
  service_name: "Water",
  account_type_id: null,
  structure: "tiered",
  status: "active",
  scheduled_change: null,
  current_version: IN_FORCE,
  draft_version: null,
  used_by_plans: 3,
  applied_to_accounts: 1306,
  size_count: 1,
  season_labels: [],
  block_count: 2,
  window_count: 0,
  effective_from: "2026-01-01",
  versions: [IN_FORCE],
  uom_gate: { satisfied: true, reason: "match", schedule_uom: "kgal", billed_uom: "kgal", priced_against: "kgal", conversion_factor: null },
  current_version_issued_bills: 12,
} as unknown as ScheduleDetail;

describe("DEF-RAT-9111 — a schedule priced from each class's own base code opens Edit", () => {
  // Seeded Residential Water: no class named and no single code — billing reads
  // BASE-W for residential and BASE-W-COM for commercial (DEF-RAT-8833). Step 1
  // demanded "Pick a base charge code" and Edit could not leave it.
  const PER_CLASS = {
    ...LIVE,
    current_version: { ...IN_FORCE, base_charge_code: null },
    versions: [{ ...IN_FORCE, base_charge_code: null }],
  } as unknown as ScheduleDetail;

  it("Continue reaches Pricing and Review without picking one code", async () => {
    const s = stub(PER_CLASS);
    const user = mountEdit(s, "t-water");
    await waitFor(() => expect(select("rs-service")).toBeDisabled());
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="pricing"]')).toBeInTheDocument());
    expect(pageText()).not.toContain(t("rating.rs.wiz.err.baseCode"));
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="review"]')).toBeInTheDocument());
  });

  it("DEF-RAT-9118: Review lists EVERY class code's price for each size, and Save leaves the codes alone", async () => {
    // The seeded figures: BASE-W $8.00 (residential, municipal) and BASE-W-COM
    // $15.00 (commercial, industrial) on a 5/8" meter. Review read BASE-W alone,
    // so the $15.00 the commercial accounts bill was nowhere on the screen.
    const withClasses = (row: ChargeRow, classes: string[]) => ({ ...row, applies_to_customer_classes: classes }) as ChargeRow;
    const res = withClasses(BASE_W, ["residential", "municipal"]);
    const com = withClasses(base("BASE-W-COM", "water", [["W-58", "15.00"], ["W-34", "15.00"]]), ["commercial", "industrial"]);
    const s = stub(PER_CLASS);
    const get = s.client.get as unknown as (path: string, options?: unknown) => Promise<unknown>;
    (s.client as unknown as { get: unknown }).get = vi.fn(async (path: string, options?: unknown) =>
      path === "/charges"
        ? { status: 200, data: { count: 3, next: null, previous: null, results: [com, res, BASE_E] }, etag: null, notModified: false }
        : get(path, options),
    );
    const user = mountEdit(s, "t-water");
    await waitFor(() => expect(select("rs-service")).toBeDisabled());
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="pricing"]')).toBeInTheDocument());
    // Step 2: the one 5/8" row names both codes and both prices.
    const pricing = document.querySelector('[data-step="pricing"]') as HTMLElement;
    expect(pricing.querySelector('[data-base-class-code="BASE-W"]')?.textContent).toBe("BASE-W · $8.00");
    expect(pricing.querySelector('[data-base-class-code="BASE-W-COM"]')?.textContent).toBe("BASE-W-COM · $15.00");
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="review"]')).toBeInTheDocument());
    const review = document.querySelector('[data-step="review"]') as HTMLElement;
    const classes = [...review.querySelectorAll("[data-base-row-class]")].map((node) => node.textContent);
    expect(classes).toEqual(["Residential, Municipal · BASE-W", "Commercial, Industrial · BASE-W-COM"]);
    const rows = [...review.querySelectorAll("[data-base-row-class]")].map((node) => node.closest("tr")?.textContent ?? "");
    expect(rows[0]).toContain("$8.00");
    expect(rows[1]).toContain("$15.00");
    expect(review.textContent).toContain("BASE-W · BASE-W-COM");
    // Saving the edit unchanged names no single code and posts no price.
    fireEvent.change(document.getElementById("rs-effective-from") as HTMLInputElement, { target: { value: "2027-01-01" } });
    await user.type(document.getElementById("rs-what-changed") as HTMLTextAreaElement, "No change");
    await user.click(screen.getByRole("button", { name: t("rating.rs.wiz.createVersion") }));
    await waitFor(() => expect(s.posts.length).toBe(1));
    expect(s.posts[0].body.base_charge_code).toBeNull();
    expect(s.posts[0].body.account_type_id).toBeNull();
    expect(JSON.stringify(s.posts[0].body)).not.toContain("15.00");
  });

  it("a NEW schedule still needs its base code (Add is unchanged)", () => {
    const blank = {
      name: "x",
      service: "water",
      uom: "kgal",
      model: "flat",
      base_charge_code: "",
      account_type_id: "",
    } as unknown as Parameters<typeof detailsProblems>[0];
    expect(detailsProblems(blank, t).base_charge_code).toBe(t("rating.rs.wiz.err.baseCode"));
  });
});

describe("RAT-03 — Edit: Change the rate · Fix an error (62–71)", () => {
  it("DEF-RAT-8829: Fix an error names the version it corrects, not the count of live versions (69/71)", async () => {
    // v1 in force for 2026 with v2 already scheduled from 2027: the correction
    // is of v1. Counting the live rows read `v2 (corrected)`.
    const v1 = { ...IN_FORCE, id: "v-1", effective_to: "2026-12-31" } as VersionRow;
    const v2 = { ...IN_FORCE, id: "v-2", effective_from: "2027-01-01", effective_to: null } as VersionRow;
    const user = mountEdit(stub({ ...LIVE, current_version: v1, versions: [v1, v2] } as ScheduleDetail), "t-water");
    await waitFor(() => expect(select("rs-service")).toBeDisabled());
    await user.click(screen.getByText(t("rating.rate.intent.correct"), { exact: true }));
    await waitFor(() => expect(pageText()).toContain(t("rating.rs.wiz.versionCorrected", { n: 1 })));
    expect(pageText()).not.toContain(t("rating.rs.wiz.versionCorrected", { n: 2 }));
  });

  it("DEF-RAT-8835: the Base charge code field shows the schedule's code on Edit (62-edit-change-1.png)", async () => {
    // The code list arrives AFTER the record, as 200 codes do in the product:
    // the field has mounted, empty, by the time its option exists.
    const s = stub(LIVE);
    const get = s.client.get as unknown as (path: string, options?: unknown) => Promise<unknown>;
    let release: () => void = () => undefined;
    const codesLate = new Promise<void>((resolve) => {
      release = resolve;
    });
    (s.client as unknown as { get: unknown }).get = vi.fn(async (path: string, options?: unknown) => {
      if (path === "/charges") await codesLate;
      return get(path, options);
    });
    mountEdit(s, "t-water");
    await waitFor(() => expect(select("rs-service")).toBeDisabled());
    expect((document.getElementById("rs-base-code") as HTMLInputElement).value).toBe("");
    release();
    // DEF-RAT-10026 — the picker shows code · name (two codes may share a class).
    await waitFor(() =>
      expect((document.getElementById("rs-base-code") as HTMLInputElement).value).toBe("BASE-W · BASE-W base"),
    );
  });

  it("DEF-RAT-8748: a stored bound shows trimmed (0, 5) and a rate at four places (4.4096)", async () => {
    const user = mountEdit(stub(LIVE), "t-water");
    await waitFor(() => expect(select("rs-service")).toBeDisabled());
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-cell="tier-from-0"]')).toBeInTheDocument());
    expect((document.querySelector('[data-cell="tier-from-0"]') as HTMLInputElement).value).toBe("0");
    expect((document.querySelector('[data-cell="tier-to-0"]') as HTMLInputElement).value).toBe("5");
    expect((document.querySelector('[data-cell="tier-price-0"]') as HTMLInputElement).value).toBe("4.4096");
    expect(pageText()).not.toContain("0.000000");
  });

  it("DEF-RAT-9119: a stored per-size minimum shows as money (8.00), typing is not fought, and the draft keeps 8.000000", async () => {
    // The box printed the stored `8.000000` (`15.000000` on the seeded
    // Residential Water); Review and View details print `$8.00`. Display only:
    // the unchanged save below in "Change the rate" still posts `8.000000`.
    const user = mountEdit(stub(LIVE), "t-water");
    await waitFor(() => expect(select("rs-service")).toBeDisabled());
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-cell="minimum-0"]')).toBeInTheDocument());
    const box = () => document.querySelector('[data-cell="minimum-0"]') as HTMLInputElement;
    expect(box().value).toBe("8.00");
    await user.clear(box());
    await user.type(box(), "12.0");
    expect(box().value).toBe("12.0");
  });

  it("Change the rate: Service locked, What changed required, posts a NEW version with no version minimum (62–66)", async () => {
    const s = stub(LIVE);
    const user = mountEdit(s, "t-water");
    await waitFor(() => expect(select("rs-service")).toBeDisabled());
    expect(pageText()).toContain(t("rating.rs.wiz.serviceLocked"));
    expect(pageText()).toContain(t("rating.rs.wiz.changeFact"));
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="pricing"]')).toBeInTheDocument());
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="review"]')).toBeInTheDocument());
    fireEvent.change(document.getElementById("rs-effective-from") as HTMLInputElement, { target: { value: "2027-01-01" } });
    await user.click(screen.getByRole("button", { name: t("rating.rs.wiz.createVersion") }));
    await waitFor(() => expect(pageText()).toContain(t("rating.rs.wiz.err.whatChanged")));
    expect(s.posts.length).toBe(0);
    await user.type(document.getElementById("rs-what-changed") as HTMLTextAreaElement, "Board approved new tiers");
    await user.click(screen.getByRole("button", { name: t("rating.rs.wiz.createVersion") }));
    await waitFor(() => expect(s.posts.length).toBe(1));
    expect(s.posts[0].path).toBe("/rate-schedules/t-water/versions");
    expect(s.posts[0].body.reason).toBe("Board approved new tiers");
    expect(s.posts[0].body).not.toHaveProperty("minimum_bill");
    expect((s.posts[0].body.size_rows as { minimum_bill?: string }[])[0].minimum_bill).toBe("8.000000");
    await waitFor(() => expect(pageText()).toContain(t("rating.rs.wiz.newVersionLead", { name: "Water — Residential" })));
    expect(document.querySelector("[data-rs-aside]")?.textContent).toContain(t("rating.rs.wiz.saved"));
  });

  it("Fix an error: Structure locked, no dates, a reason, Save correction to the version in force (67–71)", async () => {
    const s = stub(LIVE);
    const user = mountEdit(s, "t-water");
    await waitFor(() => expect(document.querySelector("[data-rs-intent]")).toBeInTheDocument());
    await user.click(screen.getByRole("radio", { name: t("rating.rate.intent.correct") }));
    expect(select("rs-structure")).toBeDisabled();
    expect(pageText()).toContain(t("rating.rs.wiz.correctFact"));
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="pricing"]')).toBeInTheDocument());
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="review"]')).toBeInTheDocument());
    expect(document.getElementById("rs-effective-from")).toBeNull();
    expect(pageText()).toContain(t("rating.rs.wiz.billsSent", { count: 12 }));
    await user.click(screen.getByRole("button", { name: t("rating.rs.wiz.saveCorrection") }));
    await waitFor(() => expect(pageText()).toContain(t("rating.rs.wiz.err.reason")));
    await user.type(document.getElementById("rs-reason") as HTMLTextAreaElement, "Tier 1 typed 4.4069");
    await user.click(screen.getByRole("button", { name: t("rating.rs.wiz.saveCorrection") }));
    await waitFor(() => expect(s.posts.length).toBe(1));
    expect(s.posts[0].path).toBe("/rate-schedules/t-water/versions/v-3/corrections");
    expect(s.posts[0].body).not.toHaveProperty("effective_from");
    expect(s.posts[0].body.reason).toBe("Tier 1 typed 4.4069");
  });
});

describe("RAT-03 — the pure pieces", () => {
  it("a window name sets its register; a tenant's own name keeps the one it states", () => {
    expect(registerForWindow({ label: "On-peak", channel: "" })).toBe("tou_on");
    expect(registerForWindow({ label: "mid peak", channel: "" })).toBe("tou_mid");
    expect(registerForWindow({ label: "OFFPEAK", channel: "tou_on" })).toBe("tou_off");
    expect(registerForWindow({ label: "Punta", channel: "tou_on" })).toBe("tou_on");
  });

  it("a season picker carries a display year; storage gets month and day", () => {
    expect(seasonPickerValue("5", "1", 2026)).toBe("2026-05-01");
    expect(seasonFromPicker("2031-05-01")).toEqual({ month: "5", day: "1" });
    expect(seasonPickerValue("", "", 2026)).toBe("");
  });

  it("DEF-RAT-8748: bounds and rates are shown trimmed, never rounded", () => {
    expect(shownQuantity("0.000000")).toBe("0");
    expect(shownQuantity("5.500000")).toBe("5.5");
    expect(shownRate("4.409600")).toBe("4.4096");
    expect(shownRate("6.100000")).toBe("6.1000");
    expect(shownRate("4.40965")).toBe("4.40965");
    expect(shownRate("4.4")).toBe("4.4");
  });
});

/**
 * DEF-RAT-8824 — PO 2026-10-01: *"all buttom position on bottom pf the page -
 * they are all over the place"*. Every page button sits in the ONE footer
 * bar, in one order: `Cancel` alone at the left, then right-aligned
 * `Save draft` · `Back` · `Continue`/commit; the page head holds none.
 *
 * ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 clause 2): asserting the
 * buttons EXIST (every earlier case did, over a footer with `Back` floating
 * mid-row) — so these read the footer's own children, in DOM order, and count
 * which of them carry `mr-auto`, which is what split the row.
 */
function footer(): { left: string[]; right: string[]; autoMargins: number; head: number } {
  const bar = document.querySelector("[data-wizard=actions]") as HTMLElement;
  const left = [...bar.querySelectorAll("[data-wizard=left] button")].map((node) => node.textContent ?? "");
  const right = [...bar.querySelectorAll(":scope > button")].map((node) => node.textContent ?? "");
  const autoMargins = [...bar.children].filter((node) => node.classList.contains("mr-auto")).length;
  const head = document.querySelectorAll(".page-header-actions button").length;
  return { left, right, autoMargins, head };
}

describe("DEF-RAT-8824 — one footer bar, one order, on every step", () => {
  it("Add: step 1 Cancel | Continue · step 2 Cancel | Back · Continue · step 3 Cancel | Save draft · Back · Create", async () => {
    const user = mountAdd(stub());
    await waitFor(() => expect(select("rs-service").options.length).toBeGreaterThan(1));
    const cancel = t("rating.plan.cancel");
    expect(footer()).toEqual({ left: [cancel], right: [t("wizard.continue")], autoMargins: 1, head: 0 });
    await details(user, "water", "flat");
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="pricing"]')).toBeInTheDocument());
    expect(footer()).toEqual({ left: [cancel], right: [t("wizard.back"), t("wizard.continue")], autoMargins: 1, head: 0 });
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="review"]')).toBeInTheDocument());
    expect(footer()).toEqual({
      left: [cancel],
      right: [t("rating.rs.wiz.saveDraft"), t("wizard.back"), t("rating.rs.wiz.create")],
      autoMargins: 1,
      head: 0,
    });
  });

  it("Edit (Fix an error): the same bar, the commit's own word last", async () => {
    const user = mountEdit(stub(LIVE), "t-water");
    await waitFor(() => expect(select("rs-service")).toBeDisabled());
    const cancel = t("rating.plan.cancel");
    expect(footer()).toEqual({ left: [cancel], right: [t("wizard.continue")], autoMargins: 1, head: 0 });
    await user.click(screen.getByRole("radio", { name: t("rating.rate.intent.correct") }));
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="pricing"]')).toBeInTheDocument());
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="review"]')).toBeInTheDocument());
    expect(footer()).toEqual({
      left: [cancel],
      right: [t("rating.rs.wiz.saveDraft"), t("wizard.back"), t("rating.rs.wiz.saveCorrection")],
      autoMargins: 1,
      head: 0,
    });
  });

  it("the bar spans the whole page under the steps AND the summary, not the left column", () => {
    mountAdd(stub());
    const layout = document.querySelector("[data-rs-layout]") as HTMLElement;
    expect(layout.className).toContain("[&_[data-wizard=actions]]:col-span-2");
    expect(layout.className).not.toContain("[&_[data-wizard=actions]]:col-start-1");
  });
});

describe("DEF-BIL-9014 — a service read from its own meter is never priced as a share", () => {
  // The SAME screen with the tenant's declaration the only thing that moves:
  // water read from a meter, sewer not — and then sewer switched to a meter.
  const declared = (sewerBasis: string) =>
    [
      { service: "water", name: "Water", enabled: true, primary_uom: "kgal", alt_uom: null, billed_uom: null, billing_basis: "metered" },
      { service: "sewer", name: "Sewer", enabled: true, primary_uom: "kgal", alt_uom: null, billed_uom: null, billing_basis: sewerBasis },
    ] as unknown as TenantServiceRow[];
  const shareOption = () =>
    [...select("rs-structure").options].find((option) => option.value === "percent_of_service") as HTMLOptionElement;
  const hint = () => t("rating.rs.wiz.hasMeters", { model: t("rating.model.percent_of_service") });
  const mountWith = (sewerBasis: string) =>
    mount(stub(), `/${TENANT}/plans-rates/rates/new`, "/:tenant/plans-rates/rates/new", declared(sewerBasis));

  it("DEF-BIL-9014: water is read from a meter, so the share option is greyed with a hint", async () => {
    const user = mountWith("share");
    await waitFor(() => expect(select("rs-service").options.length).toBeGreaterThan(1));
    await user.selectOptions(select("rs-service"), "water");
    expect(shareOption().disabled).toBe(true);
    expect(shareOption().textContent).toBe(hint());
  });

  it("DEF-BIL-9014: sewer has no meter, so it may still be priced as a share of water", async () => {
    const user = mountWith("share");
    await waitFor(() => expect(select("rs-service").options.length).toBeGreaterThan(1));
    await user.selectOptions(select("rs-service"), "sewer");
    expect(shareOption().disabled).toBe(false);
    expect(shareOption().textContent).toBe(t("rating.model.percent_of_service"));
  });

  it("DEF-BIL-9014: a utility that reads sewer from a meter sees it greyed for sewer too", async () => {
    const user = mountWith("metered");
    await waitFor(() => expect(select("rs-service").options.length).toBeGreaterThan(1));
    await user.selectOptions(select("rs-service"), "sewer");
    expect(shareOption().disabled).toBe(true);
    expect(shareOption().textContent).toBe(hint());
  });
});

describe("DEF-RAT-10026 — two base codes for one class are told apart on the picker", () => {
  it("each option shows code · name and the classes it covers", async () => {
    // PO 2026-10-09: a service may hold BASE-E and BASE-E-OUT, both Residential.
    // The picker drew the code alone; it now draws code · name, classes at right.
    const residential = (code: string, name: string) =>
      ({ ...base(code, "electric", [["E-100", "12.00"]]), name, applies_to_customer_classes: ["residential"] }) as ChargeRow;
    const s = stub();
    const get = s.client.get as unknown as (path: string, options?: unknown) => Promise<unknown>;
    (s.client as unknown as { get: unknown }).get = vi.fn(async (path: string, options?: unknown) => {
      if (path === "/charges")
        return {
          status: 200,
          etag: null,
          notModified: false,
          data: {
            count: 2,
            next: null,
            previous: null,
            results: [residential("BASE-E", "Electric base urban"), residential("BASE-E-OUT", "Electric base suburban")],
          },
        };
      return get(path, options);
    });
    const user = mountAdd(s);
    await waitFor(() => expect(select("rs-service").options.length).toBeGreaterThan(1));
    await user.selectOptions(select("rs-service"), "electric");
    await user.click(document.getElementById("rs-base-code") as HTMLInputElement);
    const urban = await screen.findByRole("option", { name: /^BASE-E · Electric base urban/ });
    const suburban = await screen.findByRole("option", { name: /^BASE-E-OUT · Electric base suburban/ });
    expect(urban.textContent).toContain("Residential");
    expect(suburban.textContent).toContain("Residential");
  });
});

describe("DEF-RAT-10220 — a FLAT schedule priced per the summing unit suggests Capacity", () => {
  // `capacity_uom` is the SERVER's configuration; the rate form names no
  // service. The clerk's unit is `KW` and the capacity's is `kW` — one unit.
  const SOLAR = [
    ...SERVICES,
    { service: "solar", name: "Solar", enabled: true, billing_basis: "capacity", capacity_uom: "kW", primary_uom: "KW", alt_uom: null, billed_uom: null },
    { service: "trash", name: "Trash", enabled: true, billing_basis: "capacity", capacity_uom: null, primary_uom: "cart", alt_uom: null, billed_uom: null },
  ] as unknown as TenantServiceRow[];
  const warning = t("rating.rs.wiz.flatPerCapacity", { uom: "kW" });

  async function pick(service: string, model: string) {
    UOMS.push(lookup("KW", "KW", "solar"), lookup("cart", "cart", "trash"));
    try {
      const user = mount(stub(), `/${TENANT}/plans-rates/rates/new`, "/:tenant/plans-rates/rates/new", SOLAR);
      await waitFor(() => expect(select("rs-service").options.length).toBeGreaterThan(3));
      await user.selectOptions(select("rs-service"), service);
      await waitFor(() => expect(select("rs-unit").value).not.toBe(""));
      await user.selectOptions(select("rs-structure"), model);
    } finally {
      UOMS.splice(UOMS.length - 2, 2);
    }
  }

  it("solar FLAT per KW shows the two-sentence suggestion", async () => {
    await pick("solar", "flat");
    expect(pageText()).toContain(warning);
  });

  it("solar on Capacity says nothing", async () => {
    await pick("solar", "capacity");
    expect(pageText()).not.toContain(warning);
  });

  it("trash FLAT per cart says nothing — it counts, it does not sum", async () => {
    await pick("trash", "flat");
    expect(pageText()).not.toContain("Consider Capacity");
  });
});
