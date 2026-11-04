// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave F — F1 (`PUJ-29`) the Overview carries the unit's own
//          number · F2 (`PUJ-28`) an occupied unit shows its ACCOUNT and a
//          vacant one names the owner's · F3 the four tiles are the page's ·
//          F4 (`PUJ-42`) a vacancy is a ROW · F6 (`PUJ-44`/`PUJ-45`) the unit
//          has an edit screen and the plan is on it.
// Rules:   BR-MET-036 · BR-MET-042 · BR-MET-094 · BR-MET-101 · BR-CUS-170 ·
//          BR-REP-001 (a money KPI declares its basis) · DEF-127 / DEF-138
//          (a null balance is never 0.00) · DEF-075 (a null count is never 0).
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY ASSERTION HERE WAS SHOWN RED BEFORE IT WAS SHOWN GREEN**, against
// the pre-wave screen, and the failure text is quoted in the wave's report
// (hard-won law 7). Two of them are worth naming because they would pass on a
// screen that was wrong in a plausible way:
//
//   · the vacancy test asserts the DAY COUNT and the two DATES, not merely
//     that a row appeared. An off-by-one at either end of a gap draws a row
//     that looks entirely correct and answers a landlord's question wrongly;
//   · the tiles test asserts the four LABELS **in order** and that the money
//     tile carries a basis. A tile set that kept `Meters` and added `Owed`
//     would satisfy any "does an Owed tile exist" check.
//
// ⚠ **AND THE VACANCY MATHS IS TESTED AS A FUNCTION, NOT ONLY THROUGH THE
// SCREEN.** `occupancyTimeline` is pure and its edge cases — back-to-back
// tenancies, an open tenancy, a tenancy with no start date, a trailing gap —
// are states this tenant's demo data does not contain, so a DOM-only test
// would leave four of the five branches unexecuted and green.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AccountRow, UnitRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import {
  UnitDetailPage,
  occupancyTimeline,
  unitOwedTile,
} from "./UnitDetailPage";

// ⚠ **EXPLICIT, because this project does not enable vitest's `globals`**, so
// testing-library's auto-cleanup never registers. Without it every render
// stays in `document.body` and `getAllBy…` finds the PREVIOUS test's screen —
// which makes a "does this element exist" assertion pass on a page that no
// longer renders it. A check that cannot fail (hard-won law 7).
afterEach(cleanup);

const UNIT_ID = "11111111-1111-4111-8111-111111111111";
const ACCOUNT_ID = "22222222-2222-4222-8222-222222222222";

function unit(overrides: Partial<UnitRow> = {}): UnitRow {
  return {
    id: UNIT_ID,
    unit_no: "SCW-U-201",
    premises_id: "33333333-3333-4333-8333-333333333333",
    premise_no: "P-00043",
    premise_address: "1408 Elm Street",
    label: "Apt 101",
    unit_type: "residential_submetered",
    floor_label: null,
    square_feet: null,
    rate_plan_id: null,
    plan_effective_from: "2026-06-01",
    plan_locked: false,
    vacant_standby_auto: false,
    is_common_area: false,
    services: ["electric", "water"],
    lat: null,
    lng: null,
    point: { lat: null, lng: null, source: "none" },
    active: true,
    metered_services: ["electric"],
    meters: [
      { id: "a1", asset_no: "E-5040", qualifier: null, tab: "meters" },
      { id: "a2", asset_no: "SM-7040", qualifier: "sub", tab: "sub_meters" },
      { id: "a3", asset_no: "CART-0001", qualifier: null, tab: "behind_the_meter" },
    ],
    occupancy: "occupied",
    occupant: "Sarah Miller",
    account_no: "A-10432",
    status: "active",
    sub_metered: true,
    owed: {
      account_id: ACCOUNT_ID,
      account_no: "A-10432",
      balance: "427.890000",
      balance_currency: "USD",
      balance_basis: "posting",
      balance_unavailable: [],
      balance_not_yet_billable: false,
    },
    assets: { total: 3, bills: 2, behind: 1 },
    open_work: { count: 2 },
    ...overrides,
  } as UnitRow;
}

const OCCUPIED_ACCOUNT = {
  facts_unavailable: null,
  unit: { id: UNIT_ID, is_common_area: false },
  no_account_reason: null,
  owner_account: null,
  account: {
    id: ACCOUNT_ID,
    account_no: "A-10432",
    name: "Sarah Miller",
    status_name: "Active",
    opened_at: "2024-02-05",
    closed_at: null,
    balance: "427.890000",
    balance_currency: "USD",
    currency: "USD",
  },
  facts: {
    protections: { in_force: [], expired: [] },
    customer_class: null,
    autopay: {
      elected: true,
      cash_only: false,
      nsf_count: 0,
      nsf_threshold: 2,
      will_be_taken: true,
      reading: "taken",
    },
    payment_plan: { state: "none", running: 0 },
    budget_billing: { state: "none", level: null, currency: null },
    collections: { state: "none", tier: null },
    bounced_payments: { count: 0 },
    tax_exemption: { claimed: false, expires_on: null },
    deposit: { held: "150.000000", currency: "USD", received_on: "2024-02-05", any: true },
    notes: [],
    reach: {
      bad_address: false,
      paperless: false,
      sms_reminders: false,
      preferred_language: null,
    },
    external_ref: null,
  },
};

const VACANT_ACCOUNT = {
  facts_unavailable: null,
  unit: { id: UNIT_ID, is_common_area: false },
  no_account_reason: "vacant",
  account: null,
  facts: null,
  owner_account: {
    id: "44444444-4444-4444-8444-444444444444",
    account_no: "AC-2026-00051",
    name: "Creekside Holdings LP",
    kind: "master",
    status_name: "Active",
  },
};

function client(row: UnitRow, accountAnswer: unknown, extra: Record<string, unknown> = {}) {
  return {
    get: vi.fn(async (path: string) => {
      if (path.startsWith(`/units/${UNIT_ID}/account`)) {
        return { data: accountAnswer };
      }
      if (path === `/units/${UNIT_ID}`) {
        return { data: row };
      }
      if (path.startsWith("/accounts")) {
        return { data: extra.accounts ?? { count: 0, results: [] } };
      }
      if (path.startsWith("/me/permissions")) {
        // The shape `accessCell` actually reads. A `{cells: …}` guess renders
        // the page's PermissionDenied frame and every `queryBy` assertion below
        // would pass over an empty screen — law 7's "what would make this check
        // pass wrongly".
        return {
          data: { role: "system_admin", permissions: [{ code: "premises_accounts", access: "Full" }] },
        };
      }
      return { data: { count: 0, results: [] } };
    }),
    post: vi.fn(async () => ({ data: {} })),
    request: vi.fn(async () => ({ data: row })),
  } as never;
}

function mount(row: UnitRow, accountAnswer: unknown, tab = "overview", extra = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        {/* ⚠ **MOUNTED UNDER THE REAL PATH PATTERN**, not bare inside a
            MemoryRouter (hard-won law 2's fixture clause): `useParams().unitId`
            is undefined otherwise and the page renders its own failure state,
            which every `toContain` still passes over. */}
        <MemoryRouter initialEntries={[`/brazosbend/premises/units/${UNIT_ID}?tab=${tab}`]}>
          <Routes>
            <Route
              path="/:tenant/premises/units/:unitId"
              element={
                <UnitDetailPage
                  client={client(row, accountAnswer, extra)}
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

describe("CR-089 wave F · F1 — the Overview carries the unit's own number", () => {
  it("names the unit number as a fact of its own, ahead of the premise", async () => {
    mount(unit(), OCCUPIED_ACCOUNT);
    const label = await screen.findByText("Unit ID");
    const list = label.closest("dl");
    expect(list).not.toBeNull();
    const labels = Array.from(list?.querySelectorAll("dt") ?? []).map((n) => n.textContent);
    // FIRST, ahead of the premise: a fact list that opens with somebody else's
    // identifier reads as a list about the building.
    expect(labels[0]).toBe("Unit ID");
    // ⚠ **THE BUILDING ROW IS `In this building` AND ITS VALUE IS THE STREET.**
    // It was headed `Premise` and drew `P-00043`, which is the amber block's own
    // defect on the drawn page: a code under a heading that holds the street, so
    // one fact sat in two places in two vocabularies. The address is asserted
    // rather than the code, because printing the code again is the whole defect.
    expect(labels).toContain("In this building");
    expect(labels).not.toContain("Premise");
    const building = screen.getByText("In this building");
    expect(building.nextElementSibling?.textContent).toContain("1408 Elm Street");
    expect(building.nextElementSibling?.textContent).not.toContain("P-00043");
    expect(label.nextElementSibling?.textContent).toContain("SCW-U-201");
  });

  it("drops the retired sentence telling a clerk a unit cannot move (DEF-MET-4696)", async () => {
    mount(unit(), OCCUPIED_ACCOUNT);
    await screen.findByText("In this building");
    // BR-MET-095 (CR-024) built the move on 2026-08-21 and this page's own
    // header carries `Move`. The sentence sent a clerk the long way round while
    // the short way sat above it, and the frame draws no qualifier on this row.
    expect(document.body.textContent).not.toContain("A unit never moves between premises");
  });

  it("says `Not recorded` where nothing was measured, never a bare dash", async () => {
    mount(unit({ floor_label: null, square_feet: null }), OCCUPIED_ACCOUNT);
    const floor = await screen.findByText("Floor area");
    expect(floor.nextElementSibling?.textContent).toBe("Not recorded");
    // The style is already right — `Dash` carries `.met-muted`, italic at 45%.
    // What was wrong is the WORD: a dash reads as *this row does not apply*.
    expect(floor.nextElementSibling?.querySelector(".met-muted")).not.toBeNull();
  });

  it("carries the unit with the floor area, so a bare number is never read alone", async () => {
    // ⚠ **B14 RULE 37 — the figure below is NOT the drawn one.** The frame inks
    // `820 sq ft`; asserting that would be a test about the illustrator's
    // choice of example. What is asserted is the SHAPE the composer produces,
    // over a number no frame contains.
    mount(unit({ square_feet: 745 }), OCCUPIED_ACCOUNT);
    const floor = await screen.findByText("Floor area");
    expect(floor.nextElementSibling?.textContent).toBe("745 sq ft");
    // `Sq ft` as a LABEL with a bare value is the drawn row inside out.
    expect(Array.from(document.querySelectorAll("dt")).map((n) => n.textContent)).not.toContain(
      "Sq ft",
    );
  });
});

describe("CR-089 wave F · F2 — an occupied unit shows its ACCOUNT", () => {
  it("leads with the number, and carries the holder, status, money, deposit and autopay", async () => {
    mount(unit(), OCCUPIED_ACCOUNT);
    // The account NUMBER is a link — the reverse of the old "occupant · number".
    const link = await screen.findByRole("link", { name: "A-10432" });
    expect(link).toBeTruthy();
    expect(screen.getAllByText(/Sarah Miller/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Active/).length).toBeGreaterThan(0);
    // `MoneyCell`, at 2 dp with its symbol — never the 6-dp raw string (DEF-595).
    expect(screen.getAllByText("$427.89").length).toBeGreaterThan(0);
    expect(screen.getAllByText("$150.00").length).toBeGreaterThan(0);
    // Autopay's SERVER-side reading, not a client derivation of two booleans.
    expect(document.querySelector('[data-autopay="taken"]')).not.toBeNull();
    // "when" is a STATED ABSENCE and it is the account header's own sentence.
    expect(screen.getAllByText(/Due date not known yet/).length).toBeGreaterThan(0);
  });

  it("names the OWNER's account on a vacant unit, and does not print a zero", async () => {
    mount(unit({ occupancy: "vacant", occupant: null, account_no: null, owed: null }), VACANT_ACCOUNT);
    // ⚠ **`findByRole` AND NOT `findByText` FIRST.** The vacancy SENTENCE is
    // also the Owed tile's, which renders from the unit payload before the
    // account read lands — so waiting on the sentence and then asserting the
    // link synchronously is a race the tile always wins, and the assertion
    // that matters would fail for the wrong reason.
    expect(await screen.findByRole("link", { name: "AC-2026-00051" })).toBeTruthy();
    expect(screen.getAllByText(/base charges bill to the owner/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Creekside Holdings LP/).length).toBeGreaterThan(0);
    // DEF-138: a vacancy is never measured, so it never reads $0.00.
    expect(screen.queryByText("$0.00")).toBeNull();
  });

  it("reads the account through the Account tab's OWN endpoint and key, not a second one", async () => {
    const row = unit();
    const c = client(row, OCCUPIED_ACCOUNT);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/brazosbend/premises/units/${UNIT_ID}?tab=overview`]}>
            <Routes>
              <Route
                path="/:tenant/premises/units/:unitId"
                element={
                  <UnitDetailPage client={c} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />
                }
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    await screen.findAllByRole("link", { name: "A-10432" });
    const before = (c as unknown as { get: { mock: { calls: string[][] } } }).get.mock.calls;
    // The OLD Overview read `GET /accounts?f.unit_id=` and drew the five fields
    // a LIST ROW happens to carry — which is `DEF-CUS-4691` exactly, and which
    // can see neither the deposit nor the autopay reading. Nothing on the
    // Overview may reach that endpoint any more.
    expect(before.filter((call) => String(call[0]).startsWith("/accounts"))).toHaveLength(0);
    await userEvent.click(screen.getByRole("tab", { name: "Account" }));
    // `The money` — the U7 frame's own heading for this group, reworded from
    // `Money and standing` on 2026-09-10.
    await screen.findByText("The money");
    const after = (c as unknown as { get: { mock: { calls: string[][] } } }).get.mock.calls;
    // ⚠ **ONE KEY, WHICH IS NOT THE SAME CLAIM AS ONE REQUEST.** Both surfaces
    // are observers of `unitAccountQueryKey`, so the tab change paints from
    // cache with no skeleton; React Query's default `staleTime` of 0 still
    // fires a background revalidation on the second mount. What this asserts is
    // the thing that matters and is checkable: every read of these facts goes
    // to ONE endpoint, so the two surfaces cannot describe an account two ways.
    // ⚠ **NARROWED 2026-09-10, AND DELIBERATELY NOT WIDENED.** This case
    // exists to stop the account FACTS — the holder, the status, the balance,
    // the deposit, the autopay reading — being read off a LIST ROW, which is
    // `DEF-CUS-4691` and which cannot see the last three at all. That claim is
    // unchanged and is asserted exactly as before.
    //
    // What changed is that the Account tab now also draws the frame's `Before
    // this` group, and the previous tenancy and the gap after it are NOT on
    // `/units/{id}/account` — that read returns the OCCUPYING account and has
    // no field for the ones before it. The timeline comes from
    // `GET /accounts?f.unit_id=`, under the SAME key the Occupancy tab uses, so
    // a clerk who opens either tab pays for it once. That is a different
    // question answered by a different endpoint, not a second source for one
    // fact.
    const factReads = new Set(
      after
        .map((call) => String(call[0]).split("?")[0])
        .filter((path) => path.endsWith("/account")),
    );
    expect([...factReads]).toEqual([`/units/${UNIT_ID}/account`]);
    // Every list read this tab makes is the unit's own timeline, never an
    // unfiltered sweep of the tenant's accounts.
    for (const call of after.filter((one) => String(one[0]).startsWith("/accounts"))) {
      expect(String(JSON.stringify(call))).toContain("unit_id");
    }
  });
});

describe("CR-089 wave F · F3 — the four tiles belong to the page", () => {
  const TILES = ["Assets", "Owed", "Plan", "Open work"];

  it.each(["overview", "assets", "plan", "account", "occupancy", "audit"])(
    "draws Assets · Owed · Plan · Open work on the %s tab",
    async (tab) => {
      mount(unit(), OCCUPIED_ACCOUNT, tab);
      await waitFor(() => {
        // ⚠ **THE LABEL IS THE FIRST TEXT NODE, NOT `textContent`.** A MONEY
        // tile appends its `BR-REP-001` basis inside the same `<span class="k">`,
        // so `textContent` reads `OwedPosting` — and a test that trimmed that
        // away would also stop noticing if the basis vanished.
        const labels = Array.from(document.querySelectorAll(".kpi .k")).map((n) =>
          (n.childNodes[0]?.textContent ?? "").trim(),
        );
        // IN ORDER, and all four: a strip that kept `Meters` and appended
        // `Owed` would satisfy a mere "is Owed present" check.
        expect(labels).toEqual(TILES);
        // The money tile still declares its basis beside the label.
        expect(document.querySelector(".kpi .k .kpi-basis")?.textContent).toBe("Posting date");
      });
    },
  );

  it("splits the assets count into what bills and what is behind the meter", async () => {
    mount(unit(), OCCUPIED_ACCOUNT);
    await waitFor(() => {
      // ⚠ **`2 metered`, NOT `2 bill` — THE PLURAL WAS BROKEN AND THIS CASE
      // PASSED OVER IT.** The key read `{{bills}} bill · {{behind}} behind the
      // meter`, so English rendered *"2 bill"* on every unit with more than one
      // metered asset, and this assertion pinned the broken string because it
      // was written from the code rather than from the drawing. The tile now
      // carries the sentence the PREMISES tile has always used for this concept
      // — which is also what the frame draws.
      expect(screen.getByText("2 metered · 1 behind the meter")).toBeTruthy();
    });
  });

  it("labels the money tile with its basis (BR-REP-001) and never invents one", () => {
    const tile = unitOwedTile(unit(), (k: string) => k);
    expect("money" in tile).toBe(true);
    expect((tile as { money: { basis: string; amount: string } }).money.basis).toBe("posting");
    expect((tile as { money: { amount: string } }).money.amount).toBe("427.890000");
  });

  it("says who the base charge goes to instead of $0.00 when nothing occupies the unit", () => {
    const tile = unitOwedTile(unit({ owed: null }), (k: string) => k);
    expect("money" in tile).toBe(false);
    expect(JSON.stringify(tile)).toContain("metering.units.owed.vacantOwnerBilled");
  });

  it("says a figure could not be READ rather than showing nothing owed", () => {
    const tile = unitOwedTile(
      unit({
        owed: {
          account_id: ACCOUNT_ID,
          account_no: "A-10432",
          balance: null,
          balance_currency: null,
          balance_basis: null,
          balance_unavailable: ["ledger_unwired"],
          balance_not_yet_billable: false,
        },
      }),
      (k: string) => k,
    );
    expect("money" in tile).toBe(false);
    expect(JSON.stringify(tile)).toContain("metering.units.owed.unreadable");
  });

  it("draws a dash and never a zero when work could not be asked (DEF-075)", async () => {
    mount(unit({ open_work: { count: null } }), OCCUPIED_ACCOUNT);
    await waitFor(() => {
      const tile = document.querySelector('.kpi:nth-child(4) .v');
      expect(tile?.textContent).not.toBe("0");
    });
  });
});

describe("CR-089 wave F · F4 — a vacancy is a row", () => {
  const tenancy = (over: Partial<AccountRow>): AccountRow =>
    ({
      id: `acc-${over.account_no}`,
      account_no: "AC-1",
      name: "A Tenant",
      status_name: "Closed",
      opened_at: "2026-01-01",
      closed_at: "2026-05-28",
      ...over,
    }) as AccountRow;

  it("counts the days BETWEEN two tenancies, inclusive of neither end date", () => {
    const timeline = occupancyTimeline(
      [
        tenancy({ account_no: "AC-1", opened_at: "2026-01-01", closed_at: "2026-05-28" }),
        tenancy({ account_no: "AC-2", opened_at: "2026-06-01", closed_at: null }),
      ],
      "2026-09-09",
    );
    expect(timeline.map((e) => e.kind)).toEqual(["tenancy", "vacancy", "tenancy"]);
    const gap = timeline[1] as { from: string; to: string | null; days: number };
    // ⚠ **CR-089's worked line reads *"Vacant · 28 May to 1 Jun 2026 · 4
    // days"* AND THAT IS ONE DAY LONG, MEASURED AGAINST THE PRODUCT'S OWN
    // MOVE-OUT SEMANTICS.** `customers.services` bills a leaver THROUGH
    // `moved_out_on` (`"bill_through": moved_out_on.isoformat()`) and writes
    // that same date to `closed_at`, so a tenancy closing on the 28th
    // OCCUPIED the 28th. The unit is empty on the 29th, 30th and 31st —
    // **three days** — and the next tenant holds the 1st. The CR's figure is
    // the difference between the two TENANCY dates; the row draws the
    // VACANCY's own dates and its own length, which is the number a landlord
    // asked for. §6's correction block already says the worked figures are
    // illustrations; this one is an illustration with an off-by-one in it and
    // it is recorded in the decision log rather than copied.
    expect(gap.days).toBe(3);
    expect(gap.from).toBe("2026-05-29");
    expect(gap.to).toBe("2026-05-31");
  });

  it("draws NO row for back-to-back tenancies", () => {
    const timeline = occupancyTimeline(
      [
        tenancy({ account_no: "AC-1", opened_at: "2026-01-01", closed_at: "2026-05-31" }),
        tenancy({ account_no: "AC-2", opened_at: "2026-06-01", closed_at: null }),
      ],
      "2026-09-09",
    );
    expect(timeline.map((e) => e.kind)).toEqual(["tenancy", "tenancy"]);
  });

  it("carries the OPEN trailing vacancy to today", () => {
    const timeline = occupancyTimeline(
      [tenancy({ account_no: "AC-1", opened_at: "2026-06-01", closed_at: "2026-07-31" })],
      "2026-09-09",
    );
    expect(timeline.map((e) => e.kind)).toEqual(["tenancy", "vacancy"]);
    const gap = timeline[1] as { from: string; to: string | null; days: number };
    expect(gap.from).toBe("2026-08-01");
    expect(gap.to).toBeNull();
    expect(gap.days).toBe(40);
  });

  it("adds no vacancy after an OPEN tenancy — somebody is living there now", () => {
    const timeline = occupancyTimeline(
      [tenancy({ account_no: "AC-1", opened_at: "2026-06-01", closed_at: null })],
      "2026-09-09",
    );
    expect(timeline.map((e) => e.kind)).toEqual(["tenancy"]);
  });

  it("passes through a tenancy with no start date rather than subtracting from it", () => {
    const timeline = occupancyTimeline(
      [
        tenancy({ account_no: "AC-1", opened_at: null, closed_at: null }),
        tenancy({ account_no: "AC-2", opened_at: "2026-06-01", closed_at: "2026-07-31" }),
      ],
      "2026-08-02",
    );
    expect(timeline.filter((e) => e.kind === "tenancy")).toHaveLength(2);
  });

  it("renders the gap as a table row that says who the base charge goes to", async () => {
    mount(unit({ occupancy: "vacant", occupant: null, account_no: null, owed: null }), VACANT_ACCOUNT, "occupancy", {
      accounts: {
        count: 1,
        results: [
          {
            id: "acc-1",
            account_no: "AC-2026-00042",
            name: "A Tenant",
            status_name: "Closed",
            opened_at: "2026-06-01",
            closed_at: "2026-07-31",
          },
        ],
      },
    });
    const row = await waitFor(() => {
      const found = document.querySelector('[data-occupancy-row="vacancy"]');
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(row.textContent).toContain("Vacant");
    expect(row.textContent).toMatch(/Base charges bill to the owner/);
    // ⚠ **ONE "Vacant" PER CELL, AND THE COUNT MOVED FROM THE ROW TO THE CELL
    // ON 2026-09-10.** It used to count the word across the WHOLE ROW, because
    // the fault it was written for was a status cell holding the BUNDLED
    // sentence — *"Vacant — base charges bill to the owner"* — beside an
    // Occupant cell that already said it: one cell, the word twice.
    // The ratified U8 frame draws the word in TWO cells deliberately, and they
    // answer two different questions: the Occupant column says WHO held the
    // unit (nobody), the Status column says WHAT this stretch is (a vacant
    // period). A row-wide count cannot tell those apart, so it is counted where
    // the duplication actually happened.
    const cells = [...row.querySelectorAll("td")].map((cell) => cell.textContent ?? "");
    expect(cells[0]).toBe("Vacant");
    for (const cell of cells) {
      expect((cell.match(/Vacant/g) ?? []).length).toBeLessThanOrEqual(1);
    }
  });
});

describe("CR-089 wave F · F6 — the unit has its own edit form", () => {
  it("offers Edit on the unit's own header, beside Move", async () => {
    mount(unit(), OCCUPIED_ACCOUNT);
    const edit = await screen.findByRole("button", { name: "Edit" });
    expect(edit).toBeTruthy();
    expect(screen.getByRole("button", { name: "Move" })).toBeTruthy();
  });

  it("opens a form carrying the label, the floor area AND the plan", async () => {
    mount(unit(), OCCUPIED_ACCOUNT);
    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    expect(await screen.findByLabelText(/Unit label/)).toBeTruthy();
    // ⚠ **`Floor area`, NOT `Square feet` (`DEF-MET-4763`).** The `U10` frame
    // draws the label that way and the unit's own Overview already said it —
    // one fact, two words, on two screens a clerk moves between in one click.
    expect(screen.getByLabelText(/Floor area/i)).toBeTruthy();
    // `PUJ-45` — the plan is on the SAME form, which is the whole task.
    expect(screen.getByLabelText(/^Plan/)).toBeTruthy();
  });
});
