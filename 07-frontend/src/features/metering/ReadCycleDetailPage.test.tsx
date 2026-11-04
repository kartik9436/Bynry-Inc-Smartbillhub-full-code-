// ── Trace ──────────────────────────────────────────────
// Screen:   Meter Reads blueprint **entry 20 — "A cycle — the detail"**,
//           `/:tenant/reads/cycles/:cycleId` (p042–p048, read as images).
// Rules:    BR-MET-011 as NARROWED 2026-09-14 · BR-MET-057 · BR-SHL-011 (the
//           open tab is URL state) · BR-SHL-020/025 · NFR-3 · B14 rules 15, 16,
//           31, 33, 40, 41 · hard rule 3 (a quantity carries its unit) ·
//           `DEF-MET-5206` (two figures NOT built, PO *"Settle first."*)
// ───────────────────────────────────────────────────────
//
// **WHAT IS GUARDED HERE, AND EVERY ONE OF THEM SHIPS SILENTLY.**
//
// 1. **THE DOOR OPENS.** The route is asserted on `APP_ROUTES` AND the page is
//    rendered at that address — `DEF-CWP-3925`'s lesson, where a hold-expiry
//    test asserted a screen was registered at one address while the router
//    mounted it at another and both opened onto *"not built yet"*.
//
// 2. **THE TWO BLOCKED FIGURES ARE ABSENT.** `DEF-MET-5206` is a PO ruling, so
//    the absence is a REQUIREMENT and gets an assertion rather than a comment.
//    A later lane adding the Window pill or a Registers-collected column goes
//    RED here and reads why, which is the difference between a ruling that is
//    recorded and a ruling that is kept.
//
// 3. **NO UUID REACHES THE SCREEN (B14 rule 31).** The fixture ids are real
//    uuids precisely so `not.toContain` means something — a short placeholder
//    passes the same assertion over a screen that leaks the real thing.
//
// 4. **ONE CHASE ANSWER, READ THREE WAYS, ALL DESCRIBING ONE WINDOW.** The
//    helpers that turn the chase rows into the Collection panel's figures and
//    the Routes tab's SHORT column are pure and are asserted directly, because
//    a wrong tally is a number a person reads and believes.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import de from "@/i18n/locales/de.json";
import en from "@/i18n/locales/en.json";
import esMX from "@/i18n/locales/es-MX.json";
import es from "@/i18n/locales/es.json";
import fr from "@/i18n/locales/fr-FR.json";
import hi from "@/i18n/locales/hi.json";
import idID from "@/i18n/locales/id-ID.json";
import itIT from "@/i18n/locales/it-IT.json";
import ja from "@/i18n/locales/ja-JP.json";
import ko from "@/i18n/locales/ko-KR.json";
import pt from "@/i18n/locales/pt-BR.json";

// Static, so the (heavy) route-table import is paid in the collect phase.
import { APP_ROUTES } from "@/App";
import type { CycleRow, ReadChaseList, ReadChaseRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import {
  CycleRollup,
  ReadCycleDetailPage,
  READ_CYCLE_TABS,
  cycleStatusTone,
  cycleWindowAnchor,
  estimateTargetsFor,
  readCycleChaseKey,
  readCycleQueryKey,
  readCycleTabFromParam,
  shortChannels,
  shortMetersByRoute,
  shortRegisters,
  tickedMeters,
} from "./ReadCycleDetailPage";
import { PREMISES_PERMISSION, readCycleDetailPath } from "./meteringShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const TEST_TENANT = "brazosbend";
/** ⚠ REAL uuids, because the assertion that matters is `not.toContain`. */
const CYCLE_ID = "01a09e06-4523-7226-9328-26cbe9839a9e";
const METER_A = "01a09e06-452a-7db4-8d5f-6b33e4f2e3da";
const METER_B = "01a09e06-4531-7c11-b0a2-9d5a1f7c4e88";

function cycle(over: Partial<CycleRow> = {}): CycleRow {
  return {
    id: CYCLE_ID,
    code: "CY-001",
    routes: ["RT-001", "RT-003"],
    window_start: "2026-09-01",
    window_end: "2026-09-03",
    bill_date: "2026-11-05",
    due_days: 20,
    due_date: "2026-11-25",
    expected: 5,
    collected: 0,
    progress: 0,
    status: "in_progress",
    lifecycle_status: "active",
    name: null,
    frequency: "Monthly",
    start_day: 1,
    days_to_complete: 3,
    effective_start_day: 1,
    start_day_differs: false,
    read_window_source: "derived",
    first_run_date: "2026-06-01",
    bill_day: 5,
    accounts: 5,
    route_ids: [],
    proposed_windows: [],
    next_period: { period_start: "2026-10-01", period_end: "2026-10-03" },
    next_cycle_date: "2026-10-01",
    schedule_warning: null,
    schedule_gap: null,
    ...over,
  };
}

function chaseRow(over: Partial<ReadChaseRow> = {}): ReadChaseRow {
  return {
    unit_id: "u-1",
    unit: "2C",
    premises: "1408 Elm",
    meter: "MTR-0471",
    asset_id: METER_A,
    route: "RT-001",
    service: "electric",
    missing_channels: ["tou_mid"],
    days_left: -9,
    ...over,
  };
}

function chase(rows: ReadChaseRow[]): ReadChaseList {
  return {
    cycle_id: CYCLE_ID,
    cycle_code: "CY-001",
    window: { period_start: "2026-09-01", period_end: "2026-09-03", state: "closed" },
    rows,
    count: rows.length,
  };
}

function permissions(access: string): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access }],
  };
}

function renderPage(
  seed: { cycle?: CycleRow; rows?: ReadChaseRow[]; tab?: string; access?: string } = {},
): string {
  const row = seed.cycle ?? cycle();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(readCycleQueryKey(CYCLE_ID), row);
  queryClient.setQueryData(
    readCycleChaseKey(CYCLE_ID, cycleWindowAnchor(row)),
    chase(seed.rows ?? [chaseRow()]),
  );
  queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access ?? "Full"));
  const address =
    `/${TEST_TENANT}${readCycleDetailPath(CYCLE_ID)}` + (seed.tab === undefined ? "" : `?tab=${seed.tab}`);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* ⚠ **MOUNTED UNDER THE REAL PATH PATTERN.** A bare `MemoryRouter`
            with no `/:tenant/…` route leaves `useParams().tenant` undefined, so
            every address the page builds comes out `//reads/…` — a
            protocol-relative URL to another host, which reads as a perfectly
            good string to `toContain` (hard-won law 2's fixture clause). */}
        <MemoryRouter initialEntries={[address]}>
          <Routes>
            <Route path="/:tenant/reads/cycles/:cycleId" element={<ReadCycleDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("entry 20 — the cycle detail is reachable and is the drawn frame", () => {
  it("`reads/cycles/:cycleId` is a ROUTED page, and the page renders at that address", () => {
    // RED first: before App.tsx carried the line this resolved to the
    // catch-all. Asserted on the ROUTE TABLE *and* by rendering, because
    // `DEF-CWP-3925` is a test that checked only the first half while the
    // router mounted the screen somewhere else.
    const tenant = APP_ROUTES.find((route) => route.path === "/:tenant");
    const shell = tenant?.children?.find((child) => child.path === undefined);
    const paths = (shell?.children ?? []).map((child) => child.path);
    expect(paths).toContain("reads/cycles/:cycleId");

    const html = renderPage();
    // B14 rule 31 — the cycle CODE is the title, and the uuid is the address.
    expect(html).toContain("CY-001");
    expect(html).not.toContain(CYCLE_ID);
    // The drawn back link, kicker and the five tabs.
    expect(html).toContain(t("metering.cycleDetail.back"));
    expect(html).toContain(t("metering.cycleDetail.tab.overview"));
    expect(html).toContain(t("metering.cycleDetail.tab.routes"));
    expect(html).toContain(t("metering.cycleDetail.tab.still"));
    expect(html).toContain(t("metering.cycleDetail.tab.reads"));
    expect(html).toContain(t("metering.cycleDetail.tab.history"));
  });

  it("the Overview stays reader-free — the 2026-10-24 ruling built the Reader on the Routes TAB only", () => {
    // ⚠ AMENDED 2026-10-24 (PO, MQ-033, `DEF-MET-10591`). This test read
    // *"⛔ the drawn Reader column is NOT built — OQ-343 and CR-029 D6"* and
    // asserted no `Reader` on either tab. The PO then ruled assign/reassign
    // on Reads → cycle → Routes, superseding D6 and OQ-343 FOR THAT TAB ONLY;
    // the Routes-tab column, its row action and the bulk assign are asserted
    // in `AssignReaderModal.dom.test.tsx` (it needs a live query this static
    // render cannot run). What is still true here is the Overview panel.
    const html = renderPage();
    expect(html).not.toMatch(/\bReader\b/);
  });

  it("B14 rule 40 — the page title is the shared PageHeader's 32px h1, not a local heading", () => {
    // The component EMITS the size class; whether it renders is the render
    // check's question (`cr093-page-title-size.mjs`), and this file says so
    // rather than implying it proved the pixel.
    const html = renderPage();
    expect(html).toMatch(/<h1[^>]*class="[^"]*text-h2/);
    expect(html).toMatch(/<h1[^>]*>CY-001<\/h1>/);
  });

  it("the five tabs are the drawing's, and an unknown `?tab=` falls back rather than erroring", () => {
    // ⚠ The blueprint's PROSE counts four and every frame draws five. B14 rule
    // 41 makes the drawing the specification; this pins the five so a lane
    // reading the prose cannot quietly drop one.
    expect([...READ_CYCLE_TABS]).toEqual(["overview", "routes", "still", "reads", "history"]);
    expect(readCycleTabFromParam("still")).toBe("still");
    expect(readCycleTabFromParam("nonsense")).toBe("overview"); // BR-SHL-011
    expect(readCycleTabFromParam(null)).toBe("overview");
  });
});

describe("⛔ DEF-MET-5206 — the two blocked figures are ABSENT, and that is the ruling", () => {
  // PO, 2026-09-14, verbatim: ***"Settle first."*** Two derivations of "the
  // current window" disagree, so anything comparing a COLLECTED count against an
  // EXPECTED one over that window would disagree with the dates printed beside
  // it. These assertions exist so the ruling is KEPT rather than merely recorded.

  it("no Window pill beside the status, and no WINDOW figure in the Collection panel", () => {
    const html = renderPage();
    // The status pill IS drawn — it is the operational status, not the window.
    expect(html).toContain(t("metering.cycles.status.in_progress"));
    // …and nothing anywhere says the window is closed, or how long ago.
    expect(html).not.toContain("Window closed");
    expect(html).not.toMatch(/days ago/);
  });

  it("no `Registers collected` anywhere — not in the roll-up, the panel, or a column", () => {
    const overview = renderPage();
    const routes = renderPage({ tab: "routes" });
    for (const html of [overview, routes]) {
      expect(html).not.toMatch(/[Rr]egisters collected/);
      // the drawn "0 of 18 registers" roll-up clause
      expect(html).not.toMatch(/\d+ of \d+ registers/);
    }
  });

  it("what IS built: Meters short, from the chase answer for the window the page prints", () => {
    const html = renderPage({
      rows: [chaseRow(), chaseRow({ asset_id: METER_B, meter: "MTR-0488", route: "RT-003" })],
    });
    expect(html).toContain(t("metering.cycleDetail.figure.metersShort"));
    expect(html).toContain(t("metering.cycleDetail.figure.ofMeters", { count: 5 }));
  });
});

describe("the roll-up line — the facts a person reads before deciding anything", () => {
  it("names the window, the bill and due dates, the routes and the meters", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <CycleRollup
          cycle={cycle()}
          routeCount={2}
          timeZone="America/Chicago"
          dateFormat="MM/DD/YYYY"
          t={t}
        />
      </MemoryRouter>,
    );
    expect(html).toContain(t("metering.cycleDetail.rollup.window"));
    expect(html).toContain("09/01/2026");
    expect(html).toContain("11/25/2026");
    expect(html).toContain(t("metering.cycleDetail.rollup.routes", { count: 2 }));
    expect(html).toContain(t("metering.cycleDetail.rollup.meters", { count: 5 }));
  });

  it("BR-SHL-020 — a cycle with no window SAYS SO rather than drawing an em-dash", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <CycleRollup
          cycle={cycle({ window_start: null, window_end: null })}
          routeCount={0}
          timeZone="America/Chicago"
          dateFormat="MM/DD/YYYY"
          t={t}
        />
      </MemoryRouter>,
    );
    expect(html).toContain(t("metering.cycleDetail.rollup.noWindow"));
  });
});

describe("one chase answer, read three ways — the pure tallies", () => {
  it("SHORT counts METERS per route, never registers (the two questions kept apart)", () => {
    const rows = [
      chaseRow({ route: "RT-001", missing_channels: ["tou_on", "tou_mid", "tou_off"] }),
      chaseRow({ asset_id: METER_B, meter: "MTR-0488", route: "RT-001" }),
      chaseRow({ asset_id: "c", meter: "MTR-0492", route: "RT-003" }),
    ];
    // The first row owes THREE registers and is ONE short meter.
    expect(shortMetersByRoute(rows)).toEqual({ "RT-001": 2, "RT-003": 1 });
  });

  it("a meter on no route is counted under no route, never under an invented one", () => {
    expect(shortMetersByRoute([chaseRow({ route: null })])).toEqual({});
  });

  it("the short-register line names the ONE meter, and counts the many", () => {
    const rows = [
      chaseRow({ missing_channels: ["total"] }),
      chaseRow({ asset_id: METER_B, meter: "MTR-0488", missing_channels: ["total", "demand"] }),
    ];
    expect(shortRegisters(rows)).toEqual([
      // two meters owe `total`, so no name — naming one of two reads as the only one
      { channel: "total", meters: 2, meter: null },
      { channel: "demand", meters: 1, meter: "MTR-0488" },
    ]);
  });

  it("the register chips are every register the shortfall owes, deduplicated", () => {
    const rows = [
      chaseRow({ missing_channels: ["total"] }),
      chaseRow({ asset_id: METER_B, missing_channels: ["total", "demand"] }),
    ];
    expect(shortChannels(rows)).toEqual(["total", "demand"]);
  });
});

describe("the shortfall's two writes — BR-MET-011 as narrowed, the reading WORK", () => {
  it("a ticked meter becomes ONE estimate target per register it owes", () => {
    const rows = [
      chaseRow({ missing_channels: ["tou_on", "tou_mid"] }),
      chaseRow({ asset_id: METER_B, meter: "MTR-0488", missing_channels: ["demand"] }),
    ];
    // Only METER_A is ticked, and it owes two registers → two records.
    expect(estimateTargetsFor(rows, [METER_A], "2026-09-03")).toEqual([
      { asset_id: METER_A, meter_no: "MTR-0471", channel: "tou_on", read_at: "2026-09-03" },
      { asset_id: METER_A, meter_no: "MTR-0471", channel: "tou_mid", read_at: "2026-09-03" },
    ]);
  });

  it("the field-visit dialog is handed METER NUMBERS beside the anchor, never a number alone", () => {
    const rows = [chaseRow(), chaseRow({ asset_id: METER_B, meter: "MTR-0488" })];
    expect(tickedMeters(rows, [METER_B])).toEqual([
      { assetId: METER_B, meterNo: "MTR-0488" },
    ]);
  });

  it("nothing ticked means nothing targeted — the bulk bar cannot act on the whole list by default", () => {
    expect(estimateTargetsFor([chaseRow()], [], "2026-09-03")).toEqual([]);
    expect(tickedMeters([chaseRow()], [])).toEqual([]);
  });
});

describe("the window every figure is measured against", () => {
  it("is the cycle row's own window start, so the roll-up and the shortfall describe one period", () => {
    expect(cycleWindowAnchor(cycle())).toBe("2026-09-01");
  });

  it("is empty — not a guess — when the cycle has no window", () => {
    expect(cycleWindowAnchor(cycle({ window_start: null }))).toBe("");
    expect(cycleWindowAnchor(undefined)).toBe("");
  });

  it("the status tone is the OPERATIONAL status, and matches S27's so one word is one colour", () => {
    expect(cycleStatusTone("in_progress")).toBe("warning");
    expect(cycleStatusTone("billed")).toBe("success");
    expect(cycleStatusTone("scheduled")).toBe("neutral");
  });
});

describe("B14 rule 33 and the 2026-09-14 five-to-six-word ruling", () => {
  /**
   * ⚠ **THE WORD COUNT IS LATIN-SCRIPT ONLY, AND SAYING SO IS THE POINT.** A
   * word is `[A-Za-z0-9]`-bearing, so Hindi, Japanese and Korean count ZERO and
   * pass every cap trivially. Hard-won law 7: *a declared blind spot with no
   * NUMBER attached is indistinguishable from an empty one* — so the counted
   * scope is asserted below (**8 of 11** catalogues), and the three it cannot
   * read are named rather than quietly included in a green.
   */
  const COUNTED = ["en", "de", "es", "es-MX", "fr-FR", "id-ID", "it-IT", "pt-BR"] as const;
  const UNCOUNTED = ["hi", "ja-JP", "ko-KR"] as const;

  const meaningful = (sentence: string): number =>
    sentence
      .replace(/\{\{[^}]+\}\}/g, "N")
      .split(/[\s·]+/)
      .filter((word) => /[A-Za-z0-9]/.test(word)).length;

  const CATALOGUES: Record<string, Record<string, string>> = {
    en: en as Record<string, string>,
    de: de as Record<string, string>,
    es: es as Record<string, string>,
    "es-MX": esMX as Record<string, string>,
    "fr-FR": fr as Record<string, string>,
    "id-ID": idID as Record<string, string>,
    "it-IT": itIT as Record<string, string>,
    "pt-BR": pt as Record<string, string>,
    hi: hi as Record<string, string>,
    "ja-JP": ja as Record<string, string>,
    "ko-KR": ko as Record<string, string>,
  };

  it("counts 8 of the 11 catalogues, and names the 3 it cannot read", () => {
    expect(COUNTED.length + UNCOUNTED.length).toBe(Object.keys(CATALOGUES).length);
    expect(COUNTED.length).toBe(8);
    // …and the uncounted three really are the non-Latin ones, not a list that
    // rotted: every one of them scores ZERO on its own tab label.
    for (const locale of UNCOUNTED) {
      expect(
        meaningful(CATALOGUES[locale]["metering.cycleDetail.tab.overview"]),
        locale,
      ).toBe(0);
    }
  });

  it("every floor note is six words or fewer per sentence, in all 8 counted catalogues", () => {
    // The drawing writes *"Every figure is measured against this cycle's
    // window."* — eight. The rule caps a FACT at six, and the 2026-09-14 ruling
    // makes five or six the working target.
    for (const locale of COUNTED) {
      for (const key of [
        "metering.cycleDetail.routes.floorNote",
        "metering.cycleDetail.chase.floorNote",
        "metering.cycleDetail.shortBeforeBill",
        "metering.cycleDetail.history.body",
        "metering.bulkEstimate.consequence.body",
      ]) {
        const value = CATALOGUES[locale][key];
        expect(value, `${locale} is missing ${key}`).toBeTypeOf("string");
        for (const sentence of value.split(/(?<=[.。])\s*/).filter((part) => part !== "")) {
          expect(meaningful(sentence), `${locale} · ${key} — "${sentence}"`).toBeLessThanOrEqual(6);
        }
      }
    }
  });

  it("a LABEL is three words or fewer and carries no sentence, in all 8", () => {
    for (const locale of COUNTED) {
      for (const key of [
        "metering.cycleDetail.panel.collection",
        "metering.cycleDetail.panel.routes",
        "metering.cycleDetail.panel.schedule",
        "metering.cycleDetail.panel.billing",
        "metering.cycleDetail.figure.metersShort",
        "metering.cycleDetail.tab.still",
        "metering.cycleDetail.routes.short",
      ]) {
        const value = CATALOGUES[locale][key];
        expect(meaningful(value), `${locale} · ${key}`).toBeLessThanOrEqual(3);
        expect(value, `${locale} · ${key}`).not.toContain(".");
      }
    }
  });

  it("every key this screen adds is present in ALL ELEVEN — a missing one is SILENCE", () => {
    // `G15` is the gate; this is the same question asked where the screen can
    // name its own keys, because a key missing from `ko-KR` renders as nothing
    // at all rather than as an error.
    const mine = Object.keys(en).filter(
      (key) =>
        key.startsWith("metering.cycleDetail.") || key.startsWith("metering.bulkEstimate."),
    );
    expect(mine.length).toBeGreaterThan(50);
    for (const [locale, catalogue] of Object.entries(CATALOGUES)) {
      const absent = mine.filter((key) => catalogue[key] === undefined);
      expect(absent, `${locale} is missing ${absent.length} of this screen's keys`).toEqual([]);
    }
  });

  it("rule 31 — no rule, defect or question id reaches a clerk-facing string", () => {
    // The absence of `DEF-MET-5206` from the screen is the point: the ruling
    // lives in the code and the register, and rationale is ZERO words on screen.
    const html = renderPage() + renderPage({ tab: "history" });
    expect(html).not.toMatch(/\b(BR|DEF|OQ|US|GT)-[A-Z]{0,3}-?\d/);
    expect(html).not.toContain("NFR-3");
  });
});

describe("History — the one tab nothing serves", () => {
  it("renders the honest absence and NOT a table of invented windows", () => {
    const html = renderPage({ tab: "history" });
    expect(html).toContain(t("metering.cycleDetail.history.title"));
    expect(html).toContain(t("metering.cycleDetail.history.body"));
    // ⚠ The drawn twelve-window table is NOT drawn over placeholder rows. A
    // list filled with sample data is this repo's most expensive habit.
    expect(html).not.toContain(t("metering.cycles.col.billDate"));
    // …and the drawn sentence's RATIONALE half ("needs one endpoint that does
    // not exist") is nowhere: rule 33 puts rationale at zero words on screen.
    expect(html).not.toMatch(/endpoint/i);
  });
});
