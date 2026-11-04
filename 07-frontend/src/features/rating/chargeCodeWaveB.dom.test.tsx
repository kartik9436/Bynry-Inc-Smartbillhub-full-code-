// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-156-BRC10 wave B — the charge-code List, View details and the
//           Add/Edit wizard, rebuilt from 05-prototype/charge-codes-2026-10-01.
// Defects:  DEF-RAT-8713 · 8714 · 8715 · 8716 · 8717 · 8719 — each case below
//           fails on the screen this rebuild replaced (the old ChargeCodeWizard
//           at 9910f15a8): it had no picker, no Effective from, a per-size grid
//           in CODE order, a hard-coded `null` GL on step 1, the "full amount"
//           sentence on a base code, and a review that dropped four settings.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { ChargeRow, LookupEntry, MyPermissions, TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { ChargeCodeDetailPage } from "./ChargeCodeDetailPage";
import { ChargeCodesTab } from "./ChargeCodesTab";
import { ChargeCodeWizard } from "./ChargeCodeWizard";

afterEach(cleanup);

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

const PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "plans_rates", label: "Plans & Rates", access: "Full" }],
} as unknown as MyPermissions;

const SERVICES = ["water", "sewer", "trash", "fire"].map(
  (service) =>
    ({ service, name: t(`rating.service.${service}`), enabled: true, primary_uom: null, alt_uom: null }) as unknown as TenantServiceRow,
);

function size(code: string, name: string, service: string): LookupEntry {
  return { id: code, code, name, active: true, is_system: true, used_by: 0, service: { id: service, code: service } } as unknown as LookupEntry;
}
/** Served in CODE order — the order DEF-RAT-8717 put on screen. */
const SIZES: LookupEntry[] = [
  size("FL-10", 'Fire line 10"', "fire"),
  size("FL-12", 'Fire line 12"', "fire"),
  size("FL-2", 'Fire line 2"', "fire"),
  size("FL-4", 'Fire line 4"', "fire"),
  size("FL-6", 'Fire line 6"', "fire"),
  size("FL-8", 'Fire line 8"', "fire"),
  size("CART-35", "Trash 35-gallon cart", "trash"),
  size("CART-64", "Trash 64-gallon cart", "trash"),
  size("DUMP-2", "Trash 2-yard dumpster", "trash"),
  size("DUMP-4", "Trash 4-yard dumpster", "trash"),
];
const CLASSES: LookupEntry[] = ["residential", "commercial"].map(
  (code) => ({ id: code, code, name: code, active: true, is_system: true, used_by: 0 }) as unknown as LookupEntry,
);

function charge(overrides: Partial<ChargeRow>): ChargeRow {
  return {
    id: "chg-1",
    code: "CODE",
    name: "A charge",
    charge_type: "one_time",
    service: null,
    is_base: false,
    kind: "other",
    amount_rule: "flat",
    amount: null,
    amount_display: null,
    percent: null,
    percent_display: null,
    min_amount: null,
    min_amount_display: null,
    max_amount: null,
    max_amount_display: null,
    taxable_default: false,
    auto_apply: false,
    waivable: false,
    separate_line: true,
    applies_to_customer_classes: [],
    status: "active",
    gl_account_id: null,
    gl_account_code: null,
    gl_account_name: null,
    used_by_plans: 0,
    used_by_invoice_lines: 0,
    size_amounts: [],
    prices: [],
    price_range: null,
    usage: { bills: 0, lines: 0, revenue: "0.0000", revenue_display: "0.00" },
    versions: [],
    ...overrides,
  } as unknown as ChargeRow;
}

function price(size_class: string, amount: string | null, customer_class: string | null = null) {
  return {
    id: `p-${size_class}-${customer_class ?? ""}`,
    size_class,
    customer_class,
    amount: amount === null ? null : `${amount}00`,
    amount_display: amount,
    currency: "USD",
    effective_from: "2000-01-01",
    effective_to: null,
    killed: false,
    version: 1,
  };
}

const BASE_FIRE = charge({
  id: "chg-fire",
  code: "BASE-FIRE",
  name: "Fire base charge",
  charge_type: "recurring",
  service: "fire",
  is_base: true,
  kind: "base",
  auto_apply: true,
  gl_account_id: "gl-4155",
  gl_account_code: "4155",
  gl_account_name: "Fire",
  size_amounts: [price("FL-10", "50.00"), price("FL-2", "12.00"), price("FL-6", "60.00")],
});
const BASE_S = charge({
  id: "chg-sewer",
  code: "BASE-S",
  name: "Sewer base charge",
  charge_type: "recurring",
  service: "sewer",
  is_base: true,
  kind: "base",
  amount: "9.0000",
  amount_display: "9.00",
});
const BASE_T = charge({
  id: "chg-trash",
  code: "BASE-T",
  name: "Trash base charge",
  charge_type: "recurring",
  service: "trash",
  is_base: true,
  kind: "base",
  gl_account_code: "4140",
  gl_account_name: "Trash",
  used_by_schedules: 2,
  size_amounts: [price("CART-35", "9.00"), price("CART-64", "12.00")],
});
const APP_FEE = charge({ id: "chg-app", code: "APP-FEE", name: "Applications fee", kind: "other", amount: "10.0000", amount_display: "10.00" });

interface Stub {
  client: ApiClient;
  gets: { path: string; query: Record<string, unknown> }[];
  patches: { path: string; body: Record<string, unknown> }[];
}

function stub(rows: ChargeRow[], picker: Record<string, { id: string; code: string; name: string }[]> = {}): Stub {
  const gets: Stub["gets"] = [];
  const patches: Stub["patches"] = [];
  const ok = <T,>(data: T) => ({ status: 200, data, etag: null, notModified: false });
  const client = {
    get: vi.fn(async (path: string, options?: { query?: Record<string, unknown> }) => {
      const query = options?.query ?? {};
      gets.push({ path, query });
      if (path === "/charges/picker") {
        const key = `${String(query.kind)}:${String(query.service ?? "")}`;
        const list = picker[key] ?? picker[String(query.kind)] ?? [];
        return ok({ results: list.map((row) => ({ ...row, charge_type: null, kind: null, service: null })) });
      }
      if (path.startsWith("/lookups/service_size_classes")) return ok({ count: SIZES.length, results: SIZES });
      if (path.startsWith("/lookups/account_types")) return ok({ count: CLASSES.length, results: CLASSES });
      if (path.endsWith("/plans")) return ok({ count: 2, next: null, previous: null, results: [] });
      if (path === "/charges") {
        return ok({ count: rows.length, next: null, previous: null, results: rows, kind_counts: { all: 3, base: 1, plan: 1, other: 1 } });
      }
      const id = decodeURIComponent(path.replace("/charges/", ""));
      const row = rows.find((one) => one.id === id);
      if (row === undefined) throw new Error(`no stub for ${path}`);
      return ok(row);
    }),
    request: vi.fn(async (path: string, options: { method: string; body: Record<string, unknown> }) => {
      patches.push({ path, body: options.body });
      const id = decodeURIComponent(path.replace("/charges/", ""));
      const row = rows.find((one) => one.id === id) ?? rows[0];
      return ok({ ...row });
    }),
    post: vi.fn(),
  } as unknown as ApiClient;
  return { client, gets, patches };
}

function mount(element: JSX.Element, url: string, pattern: string) {
  const user = userEvent.setup();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  qc.setQueryData(queryKeys.tenantServices, SERVICES);
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={[url]}>
          <Routes>
            <Route path={pattern} element={element} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return user;
}

function mountAdd(s: Stub) {
  return mount(
    <ChargeCodeWizard client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
    `/${TENANT}/plans-rates/charge-codes/new`,
    "/:tenant/plans-rates/charge-codes/new",
  );
}
function mountEdit(s: Stub, row: ChargeRow) {
  return mount(
    <ChargeCodeWizard client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
    `/${TENANT}/plans-rates/charge-codes/${row.id}/edit`,
    "/:tenant/plans-rates/charge-codes/:definitionId/edit",
  );
}

const field = (label: string) => screen.getByLabelText(new RegExp(`^${label}`));
const continueButton = () => screen.getByRole("button", { name: t("wizard.continue") });
const pageText = () => document.body.textContent ?? "";
const factValue = (id: string) =>
  document.querySelector(`[data-facts="review-charge"] [data-fact="${id}"] dd`)?.textContent ?? null;
const asideGl = () => document.querySelector('[data-aside-row="gl"]')?.textContent ?? "";

async function pickCode(user: ReturnType<typeof userEvent.setup>, code: string) {
  const box = screen.getByLabelText(new RegExp(`^${t("rating.chargeCode.field.code")}`));
  await user.click(box);
  const option = await screen.findByRole("option", { name: new RegExp(`^${code} ·`) });
  await user.click(option);
}

// ── the Add picker: free codes only ─────────────────────────────────────
describe("CHG-02 Add · the code picker offers the FREE Settings codes only (PO 2026-10-01)", () => {
  it("asks the picker for the chosen kind and lists exactly what it serves", async () => {
    const s = stub([charge({ id: "chg-transfer", code: "TRANSFER", name: "Account transfer fee", kind: "plan" })], {
      plan: [
        { id: "chg-transfer", code: "TRANSFER", name: "Account transfer fee" },
        { id: "chg-moveout", code: "MOVE-OUT", name: "Move-out final read" },
      ],
    });
    const user = mountAdd(s);
    await user.selectOptions(await screen.findByLabelText(/^What is it\?/), "plan");
    await user.click(screen.getByLabelText(new RegExp(`^${t("rating.chargeCode.field.code")}`)));
    const listbox = await screen.findByRole("listbox");
    await waitFor(() => expect(within(listbox).getAllByRole("option").length).toBe(2));
    const options = within(listbox).getAllByRole("option");
    expect(options.map((option) => option.textContent)).toEqual([
      "TRANSFER · Account transfer fee",
      "MOVE-OUT · Move-out final read",
    ]);
    const asked = s.gets.filter((call) => call.path === "/charges/picker");
    expect(asked.at(-1)?.query).toEqual({ kind: "plan" });
  });

  it("says 'No free code. Add one in Settings.' when nothing is free (a trash base)", async () => {
    const s = stub([], { "base:trash": [] });
    const user = mountAdd(s);
    await user.selectOptions(await screen.findByLabelText(/^What is it\?/), "base");
    await user.selectOptions(screen.getByLabelText(/^Service/), "trash");
    await user.click(screen.getByLabelText(new RegExp(`^${t("rating.chargeCode.field.code")}`)));
    await waitFor(() => expect(pageText()).toContain("No free code. Add one in Settings."));
    expect(s.gets.find((call) => call.path === "/charges/picker")?.query).toEqual({ kind: "base", service: "trash" });
  });

  it("the bill line fills in from the picked code and stays editable", async () => {
    const s = stub([charge({ id: "chg-transfer", code: "TRANSFER", name: "Account transfer fee", kind: "plan" })], {
      plan: [{ id: "chg-transfer", code: "TRANSFER", name: "Account transfer fee" }],
    });
    const user = mountAdd(s);
    await user.selectOptions(await screen.findByLabelText(/^What is it\?/), "plan");
    await pickCode(user, "TRANSFER");
    const billLine = field("Bill line") as HTMLInputElement;
    expect(billLine.value).toBe("Account transfer fee");
    await user.clear(billLine);
    await user.type(billLine, "Transfer fee");
    expect(billLine.value).toBe("Transfer fee");
  });
});

// ── DEF-RAT-8717 · sizes in size order ──────────────────────────────────
describe("DEF-RAT-8717 · fire sizes read 2\" … 12\", never by code text", () => {
  it("step 2 starts with one row per fire size, FL-2, FL-4, FL-6, FL-8, FL-10, FL-12", async () => {
    const s = stub([BASE_FIRE], { "base:fire": [{ id: "chg-fire", code: "BASE-FIRE", name: "Fire base charge" }] });
    const user = mountAdd(s);
    await user.selectOptions(await screen.findByLabelText(/^What is it\?/), "base");
    await user.selectOptions(screen.getByLabelText(/^Service/), "fire");
    await pickCode(user, "BASE-FIRE");
    await user.click(continueButton());
    const selects = (await screen.findAllByLabelText(t("rating.chargeCode.col.size"))) as HTMLSelectElement[];
    expect(selects.map((select) => select.value)).toEqual(["FL-2", "FL-4", "FL-6", "FL-8", "FL-10", "FL-12"]);
    // A row removed hands its size back to the + Add row choice, still in size order.
    await user.click(document.querySelector('[data-array="charge-price-rows"] [data-remove-row="2"]') as HTMLElement);
    await user.click(screen.getByRole("button", { name: t("rating.chargeCode.addRow") }));
    const last = screen.getAllByLabelText(t("rating.chargeCode.col.size")).at(-1) as HTMLSelectElement;
    expect(within(last).getAllByRole("option").map((option) => option.textContent).slice(1)).toEqual(['Fire line 4"']); // DEF-RAT-9321 — the name, never FL-4
  });

  it("View details › Prices lists the stored rows in size order too", async () => {
    const s = stub([BASE_FIRE]);
    mount(
      <ChargeCodeDetailPage client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-fire?tab=prices`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    await waitFor(() => expect(document.querySelector('[data-array="charge-prices"]')).not.toBeNull());
    await waitFor(() => {
      const sizes = [...document.querySelectorAll('[data-array="charge-prices"] tbody strong')].map((cell) => cell.textContent);
      // DEF-RAT-9321 — the stored rows read by NAME, in size order.
      expect(sizes).toEqual(['Fire line 2"', 'Fire line 6"', 'Fire line 10"']);
    });
  });
});

// ── Effective from is required ──────────────────────────────────────────
describe("CHG-02 · Effective from is REQUIRED on Add (PO 2026-10-01)", () => {
  it("refuses Create with 'Pick a date.' and sends nothing; with a date it sends the date and the typed amount", async () => {
    const s = stub([charge({ id: "chg-reread", code: "RE-READ", name: "Meter re-read", kind: "other" })], {
      other: [{ id: "chg-reread", code: "RE-READ", name: "Meter re-read" }],
    });
    const user = mountAdd(s);
    await user.selectOptions(await screen.findByLabelText(/^What is it\?/), "other");
    await pickCode(user, "RE-READ");
    await user.click(continueButton());
    const amount = await screen.findByLabelText(/^Amount 1/);
    await user.type(amount, "20.00");
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="review"]')).not.toBeNull(), { timeout: 3000 }).catch(() => {
      throw new Error(`not on review: ${pageText().slice(0, 1500)}`);
    });
    await user.click(await screen.findByRole("button", { name: t("rating.chargeCode.create") }));
    await waitFor(() => expect(pageText()).toContain("Pick a date."));
    expect(s.patches).toEqual([]);

    fireEvent.change(field("Effective from"), { target: { value: "2026-11-01" } });
    await user.click(screen.getByRole("button", { name: t("rating.chargeCode.create") }));
    await waitFor(() => expect(s.patches).toHaveLength(1));
    const body = s.patches[0].body;
    expect(s.patches[0].path).toBe("/charges/chg-reread");
    expect(body).toMatchObject({
      kind: "other",
      is_base: false,
      effective_from: "2026-11-01",
      effective_to: null,
      amount: "20.00",
      size_amounts: [],
      amount_rule: "flat",
    });
    expect(body).not.toHaveProperty("reason");
    await waitFor(() => expect(pageText()).toContain("RE-READ created."));
  });
});

// ── DEF-RAT-8719 · the GL account is the code's own, on every step ──────
describe("DEF-RAT-8719 · steps 1 and 3 show the SAME GL account for a mapped code", () => {
  it("BASE-FIRE reads 4155 — Fire on step 1 and on step 3", async () => {
    const s = stub([BASE_FIRE]);
    const user = mountEdit(s, BASE_FIRE);
    await waitFor(() => expect(asideGl()).toContain("4155 — Fire"));
    expect(asideGl()).not.toContain(t("rating.gl.unset"));
    await user.click(continueButton());
    await user.click(continueButton());
    await screen.findByText(t("rating.chargeCode.whenAndWhy"));
    expect(asideGl()).toContain("4155 — Fire");
  });
});

// ── DEF-RAT-8713 · no "full amount" sentence on a base code ─────────────
describe("DEF-RAT-8717 · trash reads carts first, then dumpsters, smallest first in each (coordinator 2026-10-01)", () => {
  it("step 2 starts CART-35, CART-64, DUMP-2, DUMP-4 — not the 2-yard dumpster before the 35-gallon cart", async () => {
    const s = stub([BASE_T], { "base:trash": [{ id: "chg-trash", code: "BASE-T", name: "Trash base charge" }] });
    const user = mountAdd(s);
    await user.selectOptions(await screen.findByLabelText(/^What is it\?/), "base");
    await user.selectOptions(screen.getByLabelText(/^Service/), "trash");
    await pickCode(user, "BASE-T");
    await user.click(continueButton());
    const selects = (await screen.findAllByLabelText(t("rating.chargeCode.col.size"))) as HTMLSelectElement[];
    expect(selects.map((select) => select.value)).toEqual(["CART-35", "CART-64", "DUMP-2", "DUMP-4"]);
  });

  it("View details › Prices lists the stored trash rows in the same order", async () => {
    const trash = { ...BASE_T, size_amounts: [price("CART-35", "9.00"), price("CART-64", "12.00"), price("DUMP-2", "40.00")] } as ChargeRow;
    const s = stub([trash]);
    mount(
      <ChargeCodeDetailPage client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-trash?tab=prices`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    await waitFor(() => {
      const sizes = [...document.querySelectorAll('[data-array="charge-prices"] tbody strong')].map((cell) => cell.textContent);
      expect(sizes).toEqual(["Trash 35-gallon cart", "Trash 64-gallon cart", "Trash 2-yard dumpster"]); // DEF-RAT-9321
    });
  });
});

describe("CHG-01 · a BASE code's Type reads Every bill (image 18, the PO's View table)", () => {
  it("Overview › Details › Type is 'Every bill', not 'Recurring'", async () => {
    const s = stub([BASE_T]);
    mount(
      <ChargeCodeDetailPage client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-trash`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    await waitFor(() => expect(document.querySelector('[data-facts="details"] [data-fact="type"] dd')?.textContent).toBe("Every bill"));
  });
});

describe("DEF-RAT-8713 · a base code is cut down by days, and the screen says only that", () => {
  it("never renders 'The full amount is charged'; Part month is fixed at Cut down by days", async () => {
    const s = stub([BASE_FIRE]);
    const user = mountEdit(s, BASE_FIRE);
    // DEF-RAT-9804 (PO 2026-10-06) — a fixed value is drawn LOCKED (read-only,
    // full-strength) rather than as a dimmed disabled select.
    const partMonth = (await screen.findByLabelText(/^Part month/)) as HTMLInputElement;
    expect(partMonth.readOnly).toBe(true);
    expect(partMonth).toHaveAttribute("data-locked");
    expect(partMonth.value).toBe("Cut down by days");
    for (let step = 0; step < 2; step += 1) {
      expect(pageText()).not.toContain("The full amount is charged");
      await user.click(continueButton());
    }
    expect(pageText()).not.toContain("The full amount is charged");
    expect(factValue("partMonth")).toBe("Cut down by days");
  });
});

// ── DEF-RAT-8714 · a flat code is ONE amount ────────────────────────────
describe("DEF-RAT-8714 · a flat base code is one amount, never 'not priced for this size'", () => {
  it("BASE-S shows one row holding $9.00 and posts it as the flat amount", async () => {
    const s = stub([BASE_S]);
    const user = mountEdit(s, BASE_S);
    await user.click(await screen.findByRole("button", { name: t("wizard.continue") }));
    const box = (await screen.findByLabelText(/^Every class 1/)) as HTMLInputElement;
    expect(box.value).toBe("9.00");
    expect(pageText()).not.toMatch(/not priced for this size/i);
    expect(document.querySelectorAll('[data-array="charge-price-rows"] tbody tr')).toHaveLength(1);
    await user.clear(box);
    await user.type(box, "10.00");
    await user.click(continueButton());
    fireEvent.change(field("Effective from"), { target: { value: "2026-11-01" } });
    await user.type(field("Reason"), "Board approved");
    await user.click(screen.getByRole("button", { name: t("rating.chargeCode.saveChange") }));
    await waitFor(() => expect(s.patches).toHaveLength(1));
    expect(s.patches[0].body).toMatchObject({ amount: "10.00", size_amounts: [], effective_from: "2026-11-01" });
  });
});

// ── DEF-RAT-8715 · step 3 reads back every setting ──────────────────────
describe("DEF-RAT-8715 · step 3 names every step-1 setting the clerk chose", () => {
  it("May be taxed, Staff may waive and Own line on bill are read back as set", async () => {
    const s = stub([APP_FEE]);
    const user = mountEdit(s, APP_FEE);
    await user.selectOptions(await screen.findByLabelText(/^May be taxed/), "yes");
    await user.selectOptions(screen.getByLabelText(/^Staff may waive/), "yes");
    await user.selectOptions(screen.getByLabelText(/^Own line on bill/), "no");
    await user.click(continueButton());
    await user.click(continueButton());
    await screen.findByText(t("rating.chargeCode.whenAndWhy"));
    expect(factValue("taxed")).toBe("Yes");
    expect(factValue("waive")).toBe("Yes");
    expect(factValue("ownLine")).toBe("No");
    expect(factValue("auto")).toBe("No");
    expect(factValue("pricedBy")).toBe("One amount");
    expect(factValue("charged")).toBe("Once, when added");
  });
});

// ── DEF-RAT-8716 · text within B14 rule 33's caps ───────────────────────
describe("DEF-RAT-8716 · step 1's help lines are facts or instructions of six words or fewer", () => {
  it("no help line exceeds six words, and there is no 'More about this step'", async () => {
    const s = stub([BASE_FIRE]);
    mountEdit(s, BASE_FIRE);
    await screen.findByLabelText(/^Part month/);
    const helps = [...document.querySelectorAll(".field-help")].map((node) => node.textContent ?? "");
    expect(helps.length).toBeGreaterThan(0);
    for (const help of helps) {
      for (const sentence of help.split(/(?<=\.)\s+/)) {
        expect(sentence.trim().split(/\s+/).length, sentence).toBeLessThanOrEqual(6);
      }
    }
    expect(pageText()).not.toContain("More about this step");
    expect(pageText()).not.toContain("the server checks the limits");
  });
});

// ── Edit: a reason, and What changes ────────────────────────────────────
describe("CHG-02 Edit · a reason is asked for, and What changes lists the move", () => {
  it("BASE-T CART-64 $12.00 → $13.00 from 11/01 reads as one change and posts reason and date", async () => {
    const s = stub([BASE_T]);
    const user = mountEdit(s, BASE_T);
    await user.click(await screen.findByRole("button", { name: t("wizard.continue") }));
    const second = (await screen.findByLabelText(/^Every class 2/)) as HTMLInputElement;
    expect(second.value).toBe("12.00");
    await user.clear(second);
    await user.type(second, "13.00");
    await user.click(continueButton());
    const changes = await waitFor(() => {
      const table = document.querySelector('[data-array="charge-changes"]');
      expect(table).not.toBeNull();
      return table as HTMLElement;
    });
    const rows = [...changes.querySelectorAll("tbody tr")].map((row) => row.textContent);
    expect(rows).toEqual(["Trash 64-gallon cart · Every class$12.00$13.00"]); // DEF-RAT-9321
    fireEvent.change(field("Effective from"), { target: { value: "2026-11-01" } });
    await user.click(screen.getByRole("button", { name: t("rating.chargeCode.saveChange") }));
    await waitFor(() => expect(pageText()).toContain("Add a reason."));
    expect(s.patches).toEqual([]);
    await user.type(field("Reason"), "Board approved, Oct 2026");
    await user.click(screen.getByRole("button", { name: t("rating.chargeCode.saveChange") }));
    await waitFor(() => expect(s.patches).toHaveLength(1));
    expect(s.patches[0].body).toMatchObject({
      reason: "Board approved, Oct 2026",
      effective_from: "2026-11-01",
      size_amounts: [
        { size_class: "CART-35", customer_class: null, amount: "9.00" },
        { size_class: "CART-64", customer_class: null, amount: "13.00" },
      ],
    });
  });
});

// ── the List ────────────────────────────────────────────────────────────
describe("S9 Charge codes list · Kind and Priced by, the kind chips, the range", () => {
  it("draws the two new columns, the range for a sized code, Not set for a missing GL, and filters by kind", async () => {
    const sized = { ...BASE_T, price_range: { low: "9.0000", high: "40.0000", low_display: "9.00", high_display: "40.00", priced_by: "size", rows: 7 } };
    const app = { ...APP_FEE, price_range: { low: "10.0000", high: "10.0000", low_display: "10.00", high_display: "10.00", priced_by: "flat", rows: 1 } };
    const s = stub([sized as ChargeRow, app as ChargeRow]);
    const user = mount(
      <ChargeCodesTab
        readOnly={false}
        client={s.client}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        render={(parts) => <>{parts.body}</>}
      />,
      `/${TENANT}/plans-rates/charge-codes`,
      "/:tenant/plans-rates/charge-codes",
    );
    await waitFor(() => expect(pageText()).toContain("BASE-T"));
    const headers = [...document.querySelectorAll("thead th")].map((th) => th.textContent?.trim() ?? "");
    expect(headers.join("|")).toMatch(/Description\|Kind\|Type/);
    expect(headers.join("|")).toMatch(/Priced by\|Amount/);
    expect(headers).toContain(t("rating.plan.customerClassLabel"));
    expect(pageText()).toContain("$9.00 – $40.00");
    expect(pageText()).toContain("7 sizes");
    expect(document.querySelector('[data-gl="unset"]')).not.toBeNull();
    expect(document.querySelector('[data-kind-badge="base"]')?.textContent).toBe("Base charge");
    // DEF-RAT-9803 (PO 2026-10-06) — Kind moved from a chip row into the
    // `+ Filter` panel, keeping its count; `f.kind` is unchanged.
    expect(document.querySelector("[data-kind-chips]")).toBeNull();
    const baseOption = screen.getByLabelText("Base · 1");
    await user.click(baseOption);
    await waitFor(() =>
      expect(s.gets.some((call) => call.path === "/charges" && call.query["f.kind"] === "base")).toBe(true),
    );
  });
});

// ── View details varies by kind ─────────────────────────────────────────
describe("CHG-01 · View details varies by kind (PO 2026-10-01)", () => {
  it("an OTHER code has no Plans tab and warns when no GL account is set", async () => {
    const s = stub([APP_FEE]);
    mount(
      <ChargeCodeDetailPage client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-app`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    await waitFor(() => expect(pageText()).toContain("Applications fee"));
    const tabs = screen.getAllByRole("tab").map((tab) => tab.textContent);
    expect(tabs).toEqual(["Overview", "Prices", "Audit"]);
    expect(pageText()).toContain("No GL account. Set it in Settings → Accounting.");
    expect(pageText()).toContain("Times used last month");
  });

  it("a BASE code shows Sizes priced and a scheduled change", async () => {
    const scheduled = {
      ...BASE_FIRE,
      versions: [
        { effective_from: "2026-11-01", effective_to: null, state: "scheduled", created: false, changes: [{ size_class: "FL-6", customer_class: null, before_display: "20.00", after_display: "24.00", new: false }], who: "Vijay Bikkad", why: "Board approved, Oct 2026" },
        { effective_from: "2026-06-01", effective_to: "2026-10-31", state: "in_force", created: true, changes: [], who: null, why: null },
      ],
    } as unknown as ChargeRow;
    const s = stub([scheduled]);
    mount(
      <ChargeCodeDetailPage client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-fire?tab=audit`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    await waitFor(() => expect(pageText()).toContain("Change scheduled."));
    expect(pageText()).toContain("Sizes priced");
    expect(pageText()).toContain("3 of 3");
    expect(pageText()).toContain('Fire line 6": $20.00 → $24.00'); // DEF-RAT-9321
    expect(pageText()).toContain("Board approved, Oct 2026");
  });
});

// ── WAVE C · DEF-RAT-8753 — the two pricings wave B showed disabled ──────
// Images 41 · 64 · 70 (entered when used) and 31 · 61 · 67 · 77 (a penalty
// priced by customer class). Each case fails on the wave-B screen, where both
// options rendered `disabled` and could not be chosen.
describe("DEF-RAT-8753 · an OTHER code's amount can be ENTERED WHEN USED", () => {
  it("the option is offered, step 2 says so, and the save posts amount_rule per_case with no price", async () => {
    const s = stub([charge({ id: "chg-tap", code: "TAP", name: "Tap fee", kind: "other" })], {
      other: [{ id: "chg-tap", code: "TAP", name: "Tap fee" }],
    });
    const user = mountAdd(s);
    await user.selectOptions(await screen.findByLabelText(/^What is it\?/), "other");
    await pickCode(user, "TAP");
    const mode = document.querySelector("#cc-amount-mode") as HTMLSelectElement;
    const entered = within(mode).getByRole("option", { name: t("rating.chargeCode.pricedBy.entered") }) as HTMLOptionElement;
    expect(entered.disabled).toBe(false);
    await user.selectOptions(mode, "entered");
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-charge-note="entered"]')).not.toBeNull());
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="review"]')).not.toBeNull());
    fireEvent.change(field("Effective from"), { target: { value: "2026-11-01" } });
    await user.click(screen.getByRole("button", { name: t("rating.chargeCode.create") }));
    await waitFor(() => expect(s.patches).toHaveLength(1));
    expect(s.patches[0].body).toMatchObject({
      kind: "other",
      amount_rule: "per_case",
      amount: null,
      size_amounts: [],
      percent: null,
    });
  });

  it("a stored per_case code reads 'Entered when used' on View details", async () => {
    const tap = charge({ id: "chg-tap", code: "TAP", name: "Tap fee", kind: "other", amount_rule: "per_case" });
    const s = stub([tap]);
    mount(
      <ChargeCodeDetailPage client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-tap?tab=prices`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    await waitFor(() => expect(document.querySelector("[data-prices-entered]")).not.toBeNull());
  });
});

describe("DEF-RAT-8752 · the base Minimum column and the Plans tab's class and accounts", () => {
  it("View › Prices draws the schedules' minimum per size: a figure, a range, or a dash", async () => {
    const water = charge({
      id: "chg-water",
      code: "BASE-W",
      name: "Water base charge",
      charge_type: "recurring",
      service: "water",
      is_base: true,
      kind: "base",
      size_amounts: [price("5/8", "8.00"), price("1", "11.50"), price("2", "28.00")],
      size_minimums: {
        "5/8": { state: "one", low: "4.2400", high: "4.2400", low_display: "4.24", high_display: "4.24", schedules: 2 },
        "1": { state: "range", low: "6.0000", high: "7.5000", low_display: "6.00", high_display: "7.50", schedules: 2 },
        "2": { state: "mixed", low: null, high: null, low_display: null, high_display: null, schedules: 2 },
      },
    });
    const s = stub([water]);
    mount(
      <ChargeCodeDetailPage client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-water?tab=prices`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    await waitFor(() => expect(document.querySelectorAll('[data-array="charge-prices"] tbody tr').length).toBe(3));
    const rows = [...document.querySelectorAll('[data-array="charge-prices"] tbody tr')].map((row) => row.textContent ?? "");
    expect(rows.find((row) => row.includes("5/8"))).toContain("$4.24");
    expect(rows.find((row) => row.includes("11.50"))).toContain("$6.00 – $7.50");
    expect(rows.find((row) => row.includes("28.00"))).toMatch(/—$/);
  });

  it("the Plans tab reads Plan · Customer class · Accounts", async () => {
    const s = stub([BASE_T]);
    const original = s.client.get;
    (s.client as unknown as { get: unknown }).get = vi.fn(async (path: string, options?: { query?: Record<string, unknown> }) => {
      if (path.endsWith("/plans")) {
        return {
          status: 200,
          etag: null,
          notModified: false,
          data: {
            count: 2,
            next: null,
            previous: null,
            results: [
              { plan_id: "p1", plan_name: "Residential standard", plan_code: null, reached_by: "base", units: 3, customer_classes: ["Residential"], accounts: 1240 },
              { plan_id: "p2", plan_name: "Small commercial", plan_code: null, reached_by: "base", units: 1, customer_classes: [], accounts: null },
            ],
          },
        };
      }
      return (original as (p: string, o?: unknown) => Promise<unknown>)(path, options);
    });
    mount(
      <ChargeCodeDetailPage client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-trash?tab=plans`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    await waitFor(() => expect(document.querySelectorAll('[data-array="charge-plans"] tbody tr').length).toBe(2));
    const heads = [...document.querySelectorAll('[data-array="charge-plans"] thead th')].map((th) => th.textContent);
    expect(heads).toEqual(["Plan", "Customer class", "Accounts"]);
    const rows = [...document.querySelectorAll('[data-array="charge-plans"] tbody tr')].map((row) => row.textContent ?? "");
    expect(rows[0]).toContain("Residential");
    expect(rows[0]).toContain("1,240");
    expect(rows[1]).toContain(t("rating.chargeCode.everyClass"));
    expect(rows[1]).toContain("—");
  });
});

describe("DEF-RAT-8753 · a PENALTY priced BY CUSTOMER CLASS (LATE 1.50% min $5.00 / 2.00% min $10.00)", () => {
  it("By customer class is offered for a penalty and the save posts one percent and minimum per class", async () => {
    const s = stub([charge({ id: "chg-late", code: "LATE", name: "Late payment", kind: "plan", charge_type: "penalty" })], {
      plan: [{ id: "chg-late", code: "LATE", name: "Late payment" }],
    });
    const user = mountAdd(s);
    await user.selectOptions(await screen.findByLabelText(/^What is it\?/), "plan");
    await pickCode(user, "LATE");
    await user.selectOptions(document.querySelector("#cc-type") as HTMLSelectElement, "penalty");
    const pricedBy = document.querySelector("#cc-priced-by") as HTMLSelectElement;
    const byClass = within(pricedBy).getByRole("option", { name: t("rating.chargeCode.pricedByOption.class") }) as HTMLOptionElement;
    expect(byClass.disabled).toBe(false);
    await user.selectOptions(pricedBy, "class");
    await user.click(continueButton());
    const percents = (await screen.findAllByLabelText(new RegExp(`^${t("rating.chargeCode.col.percent")} \\d`))) as HTMLInputElement[];
    const minimums = screen.getAllByLabelText(new RegExp(`^${t("rating.chargeCode.col.minimum")} \\d`)) as HTMLInputElement[];
    expect(percents).toHaveLength(2);
    await user.type(percents[0], "1.50");
    await user.type(minimums[0], "5.00");
    await user.type(percents[1], "2.00");
    await user.type(minimums[1], "10.00");
    await user.click(continueButton());
    await waitFor(() => expect(document.querySelector('[data-step="review"]')).not.toBeNull());
    fireEvent.change(field("Effective from"), { target: { value: "2026-11-01" } });
    await user.click(screen.getByRole("button", { name: t("rating.chargeCode.create") }));
    await waitFor(() => expect(s.patches).toHaveLength(1));
    expect(s.patches[0].body).toMatchObject({
      charge_type: "penalty",
      amount_rule: "percent_with_minimum",
      percent: null,
      min_amount: null,
      class_terms: [
        { customer_class: "residential", percent: "0.0150", min_amount: "5.00" },
        { customer_class: "commercial", percent: "0.0200", min_amount: "10.00" },
      ],
    });
  });

  it("View details › Prices lists each class's percent and minimum, Residential first", async () => {
    const terms = (cls: string, pct: string, min: string) => ({
      ...price("All sizes", null, cls),
      percent_display: pct,
      min_amount_display: min,
    });
    const late = charge({
      id: "chg-late",
      code: "LATE",
      name: "Late payment",
      kind: "plan",
      charge_type: "penalty",
      amount_rule: "percent_with_minimum",
      class_terms: [terms("commercial", "2.00%", "10.00"), terms("residential", "1.50%", "5.00")],
    });
    const s = stub([late]);
    mount(
      <ChargeCodeDetailPage client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-late?tab=prices`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    await waitFor(() => expect(document.querySelector('[data-array="charge-prices"]')).not.toBeNull());
    const rows = [...document.querySelectorAll('[data-array="charge-prices"] tbody tr')].map((row) => row.textContent ?? "");
    expect(rows[0]).toContain("1.50%");
    expect(rows[0]).toContain("$5.00");
    expect(rows[1]).toContain("2.00%");
    expect(rows[1]).toContain("$10.00");
  });
});

// ── DEF-RAT-9109: the backfill's 2000-01-01 is never printed as a date ───
describe("DEF-RAT-9109 · View details never prints the backfill's 01/01/2000", () => {
  const backfilled = (tab: string) => {
    const row = {
      ...BASE_T,
      versions: [{ effective_from: "2000-01-01", effective_to: null, state: "in_force", created: true, changes: [], who: null, why: null }],
    } as unknown as ChargeRow;
    mount(
      <ChargeCodeDetailPage client={stub([row]).client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/${row.id}?tab=${tab}`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
  };
  it("Overview: Effective from reads no date", async () => {
    backfilled("overview");
    await waitFor(() => expect(document.querySelector('[data-screen="CHG-01"]')).not.toBeNull());
    await waitFor(() => expect(pageText()).toContain(t("rating.chargeCode.field.effectiveFrom")));
    expect(pageText()).not.toContain("01/01/2000");
  });
  it("Audit: the version row reads no date in From", async () => {
    backfilled("audit");
    await waitFor(() => expect(document.querySelector('[data-array="charge-versions"]')).not.toBeNull());
    expect(pageText()).not.toContain("01/01/2000");
  });
});

// ── DEF-RAT-9116: Edit is a plain button, as on rate-schedule details ─────
describe("DEF-RAT-9116 · charge-code details head: Duplicate · Edit · Retire, no primary", () => {
  it("Edit is secondary and Retire is danger (CR-087 E1)", async () => {
    mount(
      <ChargeCodeDetailPage client={stub([BASE_T]).client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/${BASE_T.id}`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    const head = await waitFor(() => {
      const node = document.querySelector<HTMLElement>(".page-header-actions");
      expect(node?.querySelectorAll("button").length).toBe(3);
      return node as HTMLElement;
    });
    const variants = [...head.querySelectorAll("button")].map((b) => b.getAttribute("data-variant"));
    expect(variants).not.toContain("primary");
    expect(variants[2]).toBe("danger");
  });
});

// ── DEF-RAT-9114: the module's page padding, like every Plans & Rates screen
describe("DEF-RAT-9114 · charge-code screens carry the Plans & Rates page padding", () => {
  it("View details and the wizard roots are pt-6 px-4 pb-8, as rate schedules and plans are", async () => {
    mount(
      <ChargeCodeDetailPage client={stub([BASE_T]).client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/${BASE_T.id}`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    const view = await waitFor(() => {
      const node = document.querySelector<HTMLElement>('[data-screen="CHG-01"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });
    expect(view.className.split(" ")).toEqual(expect.arrayContaining(["pt-6", "px-4", "pb-8"]));
    cleanup();
    mountAdd(stub([BASE_T]));
    const wizard = await waitFor(() => {
      const node = document.querySelector<HTMLElement>('[data-screen="CHG-02"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });
    expect(wizard.className.split(" ")).toEqual(expect.arrayContaining(["pt-6", "px-4", "pb-8"]));
  });
});

// ── DEF-RAT-9104: the wizard footer and the summary's Effective ───────────
/**
 * PO 2026-10-02: *"button in details view of chrage code ar all over the
 * place"* — the Edit wizard's footer had Cancel far left, Save draft floating
 * mid-page, Back beside it and Save change at the right of the LEFT column.
 * The footer is now the rate-schedule wizard's (2.436.6): full width, Cancel
 * alone at the left, then Save draft · Back · Continue/commit.
 *
 * ⚠ WHAT WOULD MAKE THESE PASS WRONGLY: asserting the buttons exist — so the
 * footer's own children are read in DOM order and the `mr-auto` items counted
 * (two of them is what floated Back mid-row).
 */
function chargeFooter(): { left: string[]; right: string[]; autoMargins: number } {
  const bar = document.querySelector("[data-wizard=actions]") as HTMLElement;
  const left = [...bar.querySelectorAll("[data-wizard=left] button")].map((node) => node.textContent ?? "");
  const right = [...bar.querySelectorAll(":scope > button")].map((node) => node.textContent ?? "");
  const autoMargins = [...bar.children].filter((node) => node.classList.contains("mr-auto")).length;
  return { left, right, autoMargins };
}

describe("DEF-RAT-9104 · the charge-code wizard footer is the rate-schedule wizard's", () => {
  it("Edit: step 1 Cancel | Continue · step 3 Cancel | Save draft · Back · Save change, one auto-margin", async () => {
    const user = mountEdit(stub([BASE_T]), BASE_T);
    const go = await screen.findByRole("button", { name: t("wizard.continue") });
    const cancel = t("rating.plan.cancel");
    expect(chargeFooter()).toEqual({ left: [cancel], right: [t("wizard.continue")], autoMargins: 1 });
    await user.click(go);
    await user.click(await screen.findByRole("button", { name: t("wizard.continue") }));
    await waitFor(() => expect(document.querySelector('[data-step="review"]')).toBeInTheDocument());
    expect(chargeFooter()).toEqual({
      left: [cancel],
      right: [t("rating.rate.saveDraft"), t("wizard.back"), t("rating.chargeCode.saveChange")],
      autoMargins: 1,
    });
  });

  it("the footer spans the steps AND the summary, not the left column", async () => {
    mountAdd(stub([BASE_T]));
    const layout = (await waitFor(() => {
      const node = document.querySelector("[data-charge-layout]");
      expect(node).not.toBeNull();
      return node;
    })) as HTMLElement;
    expect(layout.className).toContain("[&_[data-wizard=actions]]:col-span-2");
    expect(layout.className).not.toContain("[&_[data-wizard=actions]]:col-start-1");
  });

  it("Edit: before a new date is typed, Effective reads the in-force price's start, never a dash", async () => {
    const dated = charge({
      ...BASE_T,
      versions: [
        { effective_from: "2026-06-01", effective_to: null, state: "in_force", created: false, changes: [], who: null, why: null },
      ],
    } as Partial<ChargeRow>);
    mountEdit(stub([dated]), dated);
    await screen.findByRole("button", { name: t("wizard.continue") });
    const effective = await waitFor(() => {
      const row = document.querySelector('[data-aside-row="effective"]');
      expect(row).not.toBeNull();
      return row as HTMLElement;
    });
    expect(effective.textContent).toContain("06/01/2026");
    expect(effective.textContent).not.toContain("—");
  });
});
