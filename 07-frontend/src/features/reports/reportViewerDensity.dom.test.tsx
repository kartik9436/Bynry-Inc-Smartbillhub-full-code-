// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  DEF-REP-7010 (the services column) · DEF-REP-7011 (the header block)
//          · DEF-REP-7012 (the filter row) · DEF-REP-7013 (the KPI band) —
//          the five changes the Product Owner asked for after looking at the
//          Billing Register on the deployed build `v2.380.3`, screen `RPT-02`.
//          Drawings: `05-prototype/09 Reports Build Brief.pdf` p024 (2·1a) and
//          p025 (2·1b, THE BILLING REGISTER), read as RENDERED IMAGES per B14
//          rule 42.
// Rules:   B14 rule 33 (a LABEL ≤ 3 words · a FACT ≤ 6 words · RATIONALE ZERO
//          words on screen) · B14 rule 43 (a piece of UI is a COMPONENT) ·
//          B14 rule 44 (our UI standard wins over the drawing) · B14 rule 31
//          (no database id on screen) · CLAUDE.md hard rule 3 (a quantity
//          always carries its unit) · hard-won law 2's MIRROR and its fixture
//          clause (mount under the REAL path pattern) · hard-won law 7 clause
//          (2) — what would make this check pass WRONGLY.
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHAT THIS CAN PROVE, AND WHAT ONLY A BROWSER CAN                        ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// **jsdom has no layout.** `getBoundingClientRect` is all zeroes here, so not
// one case below can say *the band is shorter* or *the labels are level* —
// which is the thing the Product Owner actually asked for. Those are counted
// in a real browser by
// `10-scripts/def_rep_7010_report_viewer_walkthrough.mjs`, and the row counts
// are in the close-out. Hard-won law 6, and this header exists so the next
// lane does not read a green suite as an answer to a question it never asked.
//
// **What IS provable here is the RULE**, and both directions of it:
//
//   · a services column every row agrees on is said ONCE, above the table, and
//     is NOT a column — and one whose rows DIFFER is chips, per row, with no
//     line above. *A rule proved in one direction only is half proved.*
//   · a zero that is a COUNT is dropped and a zero that is a READING is kept.
//     Those are the two halves of the PO's own sentence and they are one
//     function.
//   · the header carries no kicker while reading, and the grain joins the
//     window on ONE roll-up line.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 clause 2):
//
//   · **A screen that never rendered at all.** An empty document satisfies
//     *"no `REPORT` kicker"* and *"no services column"* perfectly. So every
//     case that asserts an ABSENCE also asserts a PRESENCE on the same
//     screen — the title, or a row's bill number.
//   · **A bare `MemoryRouter`.** `useParams().tenant` undefined makes every
//     address `//reports/…` and the page renders something that is not this
//     page. The router below mounts the real `/:tenant/reports/:reportKey`.
//   · **Asserting the chips by their COLOUR.** `ServiceChips` paints a runtime
//     token through `style`; a class assertion would pass on a square the
//     browser then drops. The chip's meaning is its accessible NAME and that
//     is what is read here.
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { ReportQuantity, ReportRow } from "@/api/reportsEndpoints";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";

import { ReportViewerPage, measuresWorthShowing } from "./ReportViewerPage";
import { uniformServices } from "./ReportServicesLine";
import { REPORTS_ROUTE } from "./reportsShared";

afterEach(cleanup);

const t = i18n.getFixedT("en");
const TENANT = "billnarrow-six";

const USER: SessionUser = {
  id: "u1",
  full_name: "BN Owner",
  email: "owner@sample.test",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "reports", label: "Reports", access: "Full" }],
};

const PERIOD = {
  fy_label: "FY2026",
  period: 9,
  start: "2026-09-01",
  end: "2026-09-30",
  status: "open",
};

/** The six services `BILLNARROW Six-Service Utility` bills on every account —
 *  the shape the Product Owner photographed, in the server's own sort order. */
const SIX = ["electric", "fire", "gas", "sewer", "trash", "water"];

/** ⚠ **THE EXACT CELL FROM THE LIVE SCREEN.** Two counted zeros — `cart` is
 *  trash's and `connection` is fire's, both CAPACITY services (BR-RAT-090) —
 *  and three real measures. `measured` is the server's word, not a guess. */
const USAGE: ReportQuantity[] = [
  { quantity: "0", unit: "cart", measured: false },
  { quantity: "40", unit: "ccf", measured: true },
  { quantity: "0", unit: "connection", measured: false },
  { quantity: "800", unit: "kWh", measured: true },
  { quantity: "15.2", unit: "kgal", measured: true },
];

function row(over: Partial<ReportRow> = {}): ReportRow {
  return {
    invoice_id: "i1",
    invoice_no: "BL-2609-000042",
    account_no: "AC-2026-00001",
    customer_name: "Ana Alvarez",
    bill_type: "cycle",
    services: SIX,
    usage: USAGE,
    amount: "259.460000",
    flag: null,
    ...over,
  } as ReportRow;
}

const COLUMN_META = {
  invoice_no: { name: "invoice_no", type: "text", unit: null, unit_from: null, money_basis: null, scale: null },
  services: { name: "services", type: "text", unit: null, unit_from: null, money_basis: null, scale: null },
  usage: { name: "usage", type: "quantity", unit: null, unit_from: "usage_unit", money_basis: null, scale: null },
  amount: { name: "amount", type: "money", unit: null, unit_from: null, money_basis: "posting", scale: 4 },
};

function register(rows: ReportRow[]) {
  return {
    key: "billing_register",
    name: "Billing Register",
    basis: "posting",
    window: { start: "2026-09-01", end: "2026-09-30" },
    currency: "USD",
    columns: ["invoice_no", "account_no", "customer_name", "services", "usage", "amount"],
    column_meta: COLUMN_META,
    rows,
    kpis: [],
    totals: {},
    unavailable: [],
    grain: "bill",
    exportable: true,
    page: { page: 1, per: 50, total: rows.length, pages: 1 },
    controls: { sorts: ["invoice_no"], sort: "invoice_no", dir: "asc", searchable: true },
  };
}

function client(payload: unknown): ApiClient {
  const get = async (path: string) => {
    if (path.startsWith("/reports/")) return { data: payload, status: 200 };
    if (path === "/reports") {
      return {
        data: { cards: [], groups: [], vocabularies: { services: [], bill_types: [], purposes: [] } },
        status: 200,
      };
    }
    if (path.startsWith("/lookups/")) return { data: { results: [], count: 0 }, status: 200 };
    return { data: {}, status: 200 };
  };
  const write = async () => ({ data: {}, status: 200 });
  return { request: get, get, post: write, put: write, patch: write, delete: write } as unknown as ApiClient;
}

function mount(payload: unknown) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, USER);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
  );
  // ⚠ THE REAL PATH PATTERN — hard-won law 2's fixture clause.
  const router = createMemoryRouter(
    [
      {
        path: `/:tenant${REPORTS_ROUTE}/:reportKey`,
        element: (
          <ReportViewerPage client={client(payload)} timeZone="America/Chicago" today="2026-09-27" />
        ),
      },
    ],
    {
      initialEntries: [
        `/${TENANT}${REPORTS_ROUTE}/billing-register?f.from=2026-09-01&f.to=2026-09-30`,
      ],
    },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// DEF-REP-7010 · THE SERVICES COLUMN — BOTH DIRECTIONS OF THE PO'S RULE
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-REP-7010 · uniformServices decides which screen this is", () => {
  it("every row the same → the shared list", () => {
    expect(uniformServices([row(), row({ invoice_id: "i2" })], "services")).toEqual(SIX);
  });

  it("one row different → null, so the column stays", () => {
    expect(
      uniformServices([row(), row({ invoice_id: "i2", services: ["water"] })], "services"),
    ).toBeNull();
  });

  it("the SAME SET in a different ORDER is NOT a match", () => {
    // Order is part of *the same*: the line above the table has to draw ONE
    // order, and the other row's would then be wrong.
    expect(
      uniformServices([row({ services: ["gas", "water"] }), row({ services: ["water", "gas"] })], "services"),
    ).toBeNull();
  });

  it("no rows, and rows with no services, both collapse to nothing", () => {
    expect(uniformServices([], "services")).toBeNull();
    expect(uniformServices([row({ services: [] })], "services")).toBeNull();
  });

  it("a GROUP row is skipped, never read as a mismatch", () => {
    const group = {
      __kind__: "group",
      dimension: "cycle",
      value: "CY-001",
      rows: [],
      subtotals: {},
    } as never;
    expect(uniformServices([group, row(), row({ invoice_id: "i2" })], "services")).toEqual(SIX);
  });
});

describe("DEF-REP-7010 · on the screen", () => {
  it("every row the same → ONE line above the table, and no SERVICES column", async () => {
    mount(register([row(), row({ invoice_id: "i2", invoice_no: "BL-2609-000043" })]));
    // PRESENCE first — an empty document would satisfy every absence below.
    await screen.findByText("BL-2609-000042");

    const line = document.querySelector("[data-services-line]");
    expect(line, "the collapsed services line is not on screen").not.toBeNull();
    expect(line?.textContent).toContain(t("reports.services.everyRow"));
    // The chips are inside it, by accessible NAME and not by colour.
    for (const code of SIX) {
      expect(
        line?.querySelector(`[data-service="${code}"]`),
        `no chip for ${code} on the collapsed line`,
      ).not.toBeNull();
    }
    // …and the column is gone from the table head.
    // ⚠ **A SORTED HEAD CARRIES ITS CARET IN THE SAME TEXT NODE** — `Bill #▲`,
    // not `Bill #` — so an equality match here would report the column missing
    // from a head that draws it perfectly (law 7's *looking at the wrong
    // thing*). The PRESENCE assertion is what keeps the absence honest.
    const heads = [...document.querySelectorAll("thead th")].map((th) => th.textContent ?? "");
    expect(heads.some((head) => head.includes(t("reports.col.invoice_no")))).toBe(true);
    expect(heads.some((head) => head.includes(t("reports.col.services")))).toBe(false);
  });

  it("rows that DIFFER → chips per row, and NO line above the table", async () => {
    mount(
      register([
        row(),
        row({ invoice_id: "i2", invoice_no: "BL-2609-000043", services: ["water", "sewer"] }),
      ]),
    );
    await screen.findByText("BL-2609-000042");

    expect(document.querySelector("[data-services-line]")).toBeNull();
    const heads = [...document.querySelectorAll("thead th")].map((th) => th.textContent ?? "");
    expect(heads.some((head) => head.includes(t("reports.col.services")))).toBe(true);
    // The cells are CHIPS and not `electric · fire · gas`.
    const cellChips = document.querySelectorAll("tbody [data-testid='service-chips']");
    expect(cellChips.length, "the services cells are not chips").toBe(2);
    expect(document.body.textContent).not.toContain("electric · fire");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DEF-REP-7010 · THE USAGE CELL — TWO KINDS OF ZERO
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-REP-7010 · a counted zero goes, a measured zero stays", () => {
  it("drops a zero the server called a COUNT", () => {
    expect(measuresWorthShowing(USAGE).map((one) => one.unit)).toEqual(["ccf", "kWh", "kgal"]);
  });

  it("KEEPS a zero the server called a READING — the PO's own caveat", () => {
    // *"A zero that MEANS something (a meter read of zero) is not the same as
    // a measure that does not apply — do not collapse the two."*
    expect(
      measuresWorthShowing([{ quantity: "0", unit: "kgal", measured: true }]).map((o) => o.unit),
    ).toEqual(["kgal"]);
  });

  it("KEEPS a NON-ZERO count — `1 cart` is what the bill charged for", () => {
    expect(
      measuresWorthShowing([{ quantity: "1", unit: "cart", measured: false }]).map((o) => o.unit),
    ).toEqual(["cart"]);
  });

  it("KEEPS everything when the server says nothing — every older report is unchanged", () => {
    expect(
      measuresWorthShowing([
        { quantity: "0", unit: "cart" },
        { quantity: "15.2", unit: "kgal" },
      ]).map((o) => o.unit),
    ).toEqual(["cart", "kgal"]);
  });

  it("on the screen: `40 ccf · 800 kWh · 15.2 kgal`, and no `0 cart`", async () => {
    mount(register([row()]));
    await screen.findByText("BL-2609-000042");
    const body = document.body.textContent ?? "";
    expect(body).toContain("15.2 kgal");
    expect(body).toContain("800 kWh");
    expect(body).not.toContain("0 cart");
    expect(body).not.toContain("0 connection");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DEF-REP-7011 · THE HEADER IS TWO LINES
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-REP-7011 · title, then window and grain together", () => {
  it("no `REPORT` kicker while the report is simply being read", async () => {
    mount(register([row()]));
    // PRESENCE — the title IS drawn, so the absence below is about the kicker
    // and not about a screen that failed to render.
    await screen.findByRole("heading", { name: "Billing Register" });
    expect(screen.queryByText(t("reports.kicker"))).toBeNull();
  });

  it("the grain sits on the SAME roll-up line as the window and the basis", async () => {
    mount(register([row()]));
    await screen.findByRole("heading", { name: "Billing Register" });
    const rollup = document.querySelector(".fin-rollup");
    expect(rollup, "no roll-up on the page head").not.toBeNull();
    const words = rollup?.textContent ?? "";
    expect(words).toContain("2026-09-01");
    expect(words).toContain(t("cells.basis.posting"));
    expect(words).toContain(t("reports.grain.bill"));
    // ⚠ **AND THE GRAIN IS NOT ALSO DRAWN ON ITS OWN LINE.** Two copies of one
    // fact is the four-line header this defect is about, wearing a fix.
    expect(document.querySelectorAll("[data-grain]").length).toBe(1);
  });
});
