// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Change:   CR-182-BRC10 — PO rulings A1–A5, 2026-10-14 (decision log *"HIGH
//           CONSUMPTION: THE CUSTOMER IS ALERTED AS SOON AS A READING IS
//           FLAGGED — PORTAL MESSAGE, EMAIL, BILL NOTE, READING TAG (A1–A5)"*)
// Screens:  CWP-022 (Home · *Needs your attention*) · CWP-028 (bill detail) ·
//           CWP-034 (Usage → Readings)
// Rules:    B14 rule 31 (no id on screen) · rule 33 (labels ≤ 3 words, facts ≤
//           6) · rule 35 (the catalogue writes the words) · hard-won law 2
//           (every door asserted by its WHOLE address, mounted under the real
//           `/:tenant/portal/...` pattern)
// Cases:    A1 the reading alert and its door · A1 the bill notice and its door
//           · A2 *High usage* on the bill, and its absence · A3 the readings
//           tag, and its absence
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { TenantRegionalProvider } from "@/components/TenantRegional";

import type {
  BalanceSummary,
  PortalBillDetail,
  PortalHome,
  PortalReading,
  PortalReadings,
} from "../api/portalClient";

let readHome: () => Promise<PortalHome> = async () => {
  throw new Error("no behaviour set");
};
let readBill: () => Promise<PortalBillDetail> = async () => {
  throw new Error("no behaviour set");
};
let readReadings: () => Promise<PortalReadings> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getHome: () => readHome(),
    getBillDetail: () => readBill(),
    getAccountReadings: () => readReadings(),
  };
});

const { HomeView } = await import("./Home");
const { BillDetailView } = await import("../bills/BillDetail");
const { ReadingsView } = await import("../usage/Readings");

afterEach(cleanup);

// ═══════════════════════════════════════════════════════════════════════════
// A1 · Home — *Needs your attention*
// ═══════════════════════════════════════════════════════════════════════════

const NOTHING_OWED: BalanceSummary = {
  as_of: "2026-10-01",
  account_count: 1,
  total_owing: "0.0000",
  currency: "USD",
  problems: [],
  accounts: [],
};

function drawHome(attention: PortalHome["attention"]) {
  readHome = async () => ({
    as_of: "2026-10-01",
    balances: NOTHING_OWED,
    last_bill: null,
    last_payment: null,
    usage: [],
    usage_series: [],
    recent_bills: [],
    service: {
      address: { value: null, varies: false },
      plan: { value: null, varies: false },
      billed: { value: null, varies: false },
      paperless: { value: null, varies: false },
    },
    identity: {
      name: { value: null, varies: false },
      status: { value: null, varies: false },
      status_class: { value: null, varies: false },
      services: [],
      equipment: [],
      phone: null,
      phone_varies: false,
      email: null,
      email_varies: false,
    },
    attention,
    tip: null,
  });
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/home"]}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <Routes>
          <Route
            path="/:tenant/portal/home"
            element={<HomeView today={new Date("2026-10-01T00:00:00Z")} />}
          />
        </Routes>
      </TenantRegionalProvider>
    </MemoryRouter>,
  );
}

describe("CWP-022 · the high consumption alert (A1)", () => {
  it("names the service and the date, and its door opens the readings", async () => {
    const { container } = drawHome([
      { kind: "high_consumption", service: "water", service_name: "Water", taken_on: "2026-09-19" },
    ]);
    const item = await screen.findByText("High consumption alert");
    expect(item).toBeTruthy();
    const row = container.querySelector("[data-attention='high_consumption']") as HTMLElement;
    expect(row.textContent).toContain("Water reading on");
    expect(row.textContent).toContain("unusually high.");
    expect(row.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/); // B14 rule 31
    // ⚠ Asserted WHOLE — `toContain` passes on `//portal/readings`.
    expect(row.querySelector("a")?.getAttribute("href")).toBe("/pine-hill/portal/readings");
    expect(row.querySelector("a")?.textContent).toBe("See your readings");
  });

  it("once billed: *Your last bill is higher than usual* and *See why* opens the comparison", async () => {
    const { container } = drawHome([{ kind: "high_bill", number: "BL-2609-0151" }]);
    expect(await screen.findByText("Your last bill is higher than usual.")).toBeTruthy();
    const row = container.querySelector("[data-attention='high_bill']") as HTMLElement;
    expect(row.textContent).toContain("High usage");
    expect(row.querySelector("a")?.getAttribute("href")).toBe(
      "/pine-hill/portal/bills/BL-2609-0151/comparison",
    );
    expect(row.querySelector("a")?.textContent).toBe("See why →");
  });

  it("two meters flagged draw two items, not one", async () => {
    const { container } = drawHome([
      { kind: "high_consumption", service: "water", service_name: "Water", taken_on: "2026-09-19" },
      { kind: "high_consumption", service: "gas", service_name: "Gas", taken_on: "2026-09-18" },
    ]);
    await screen.findAllByText("High consumption alert");
    expect(container.querySelectorAll("[data-attention='high_consumption']")).toHaveLength(2);
  });

  it("nothing flagged, nothing owed: no attention panel at all (BR-CWP-093)", async () => {
    drawHome([]);
    await screen.findByText("Where things stand");
    expect(screen.queryByText("High consumption alert")).toBeNull();
    expect(document.querySelector("[data-testid='home-attention']")).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// A2 · bill detail — *High usage*, nothing longer
// ═══════════════════════════════════════════════════════════════════════════

const BILL: PortalBillDetail = {
  number: "BL-2609-0151",
  issued_on: "2026-09-30",
  due_on: "2026-10-14",
  period_start: "2026-09-01",
  period_end: "2026-09-30",
  total: "612.4000",
  owing: "612.4000",
  currency: "USD",
  state: "due",
  replaced_by: null,
  replaces: null,
  attached_answer: null,
  subtotal_display: "612.40",
  tax_display: "0.00",
  total_display: "612.40",
  account: { brought_forward: "0.00", paid_since: "0.00", this_bill: "612.40", owing: "612.40" },
  groups: [],
  readings: [],
};

function drawBill(bill: PortalBillDetail) {
  readBill = async () => bill;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/bills/BL-2609-0151"]}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <Routes>
          <Route
            path="/:tenant/portal/bills/:number"
            element={<BillDetailView number="BL-2609-0151" />}
          />
        </Routes>
      </TenantRegionalProvider>
    </MemoryRouter>,
  );
}

describe("CWP-028 · *High usage* on a bill that priced a flagged reading (A2)", () => {
  it("says *High usage* beside *Why is this different?*, which opens the comparison", async () => {
    const { container } = drawBill({ ...BILL, high_usage: true });
    expect(await screen.findByText("High usage")).toBeTruthy();
    const link = container.querySelector("[data-link='comparison']") as HTMLElement;
    expect(link.getAttribute("href")).toBe("/pine-hill/portal/bills/BL-2609-0151/comparison");
    expect(container.querySelector("[data-chip='bill-high-usage']")?.textContent).toBe(
      "High usage",
    );
  });

  it("says nothing on an ordinary bill", async () => {
    const { container } = drawBill({ ...BILL, high_usage: false });
    await screen.findByText("What you were charged");
    expect(screen.queryByText("High usage")).toBeNull();
    expect(container.querySelector("[data-link='comparison']")).not.toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// A3 · Usage → Readings — the tag on the flagged row
// ═══════════════════════════════════════════════════════════════════════════

const ROW: PortalReading = {
  taken_on: "2026-08-31",
  meter_serial: "88-40219",
  meter_no: "M-88402",
  meter_service: "water",
  meter_service_name: "Water",
  reading: "153040.000000",
  reading_display: "153040",
  used_since: "4820.000000",
  used_since_display: "4820 gal",
  unit: "gal",
  how: "reader",
  read_method: "walk_by",
  read_method_origin: "recorded",
  estimated: false,
  high_consumption: false,
  correction: null,
  channel: "total",
  on_bill: "BL-2608-0141",
};
const FLAGGED: PortalReading = {
  ...ROW,
  taken_on: "2026-09-30",
  reading: "193040.000000",
  reading_display: "193040",
  used_since: "40000.000000",
  used_since_display: "40000 gal",
  high_consumption: true,
  on_bill: null,
};

function drawReadings(rows: PortalReading[]) {
  readReadings = async () => ({
    readings: rows,
    services: [{ code: "water", name: "Water", meters: ["88-40219"] }],
    next_read: null,
    count: rows.length,
    page: 1,
    per: 50,
  });
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/readings"]}>
      <Routes>
        <Route path="/:tenant/portal/readings" element={<ReadingsView accountId="acc-1" />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("CWP-034 · the *High consumption alert* tag (A3)", () => {
  it("tags the flagged reading — in the table and on the phone card — and no other", async () => {
    const { container } = drawReadings([FLAGGED, ROW]);
    await screen.findAllByText("High consumption alert");
    expect(container.querySelector("[data-chip='high-2026-09-30']")?.textContent).toBe(
      "High consumption alert",
    );
    expect(container.querySelector("[data-chip='card-high-2026-09-30']")).not.toBeNull();
    expect(container.querySelector("[data-chip='high-2026-08-31']")).toBeNull();
    expect(container.querySelector("[data-chip='card-high-2026-08-31']")).toBeNull();
  });

  it("no flagged reading, no tag", async () => {
    const { container } = drawReadings([ROW]);
    await screen.findAllByText("4,820 gal");
    expect(container.querySelector("[data-chip^='high-']")).toBeNull();
  });
});
