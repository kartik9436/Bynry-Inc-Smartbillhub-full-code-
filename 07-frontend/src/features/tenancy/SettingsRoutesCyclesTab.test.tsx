// ── Trace ──────────────────────────────────────────────
// Change:   CR-006 (PO 2026-08-16) — SET-05 landing + SET-06/07 wizards
// Story:    US-MET-006 (EP-MET-02 §Stories)  Screens: S8 (Settings → Routes & Cycles)
// Rules:    BR-MET-008 (route CRUD; delete audit-locked while members exist) ·
//           BR-MET-010 (one cycle per route — assigning MOVES it) ·
//           BR-MET-073 (route service · area · notes) · BR-MET-074 (a premises on
//           another route MOVES, with confirm) · BR-MET-075 (an excluded meter
//           stays on its premises) · BR-MET-076 (the Draft pill) ·
//           BR-MET-077 (day-of-month DEFAULTS, not dates) · BR-MET-078 (NO money
//           anywhere on this surface) · BR-MET-079 (reads history refuses delete) ·
//           BR-MET-080 (the coverage flag) · BR-MET-081 (an edit lands next read
//           window) · BR-MET-035b (read-only WITH the reason)
// B14:      rule 15 (ICON row actions with an accessible name) · 16 (pagination
//           footer) · 17 (empty state naming its action) · 6 (danger tier)
// ───────────────────────────────────────────────────────
/**
 * ⚠ **THE OLD SUITE ASSERTED THREE THINGS THAT NO LONGER EXIST, and they were
 * replaced rather than deleted.** It checked `cycleSchema`'s window/bill-date
 * ordering, `routeSchema`'s required code, and the sentence
 * `settings.routes.membershipPending` — *"membership is edited elsewhere"*.
 * All three belonged to the MODAL screen CR-006 replaces: the cycle no longer
 * stores dates (BR-MET-077 makes them day-of-month defaults), and membership
 * is now edited HERE, so a screen that says otherwise would be lying. The
 * behaviour each case protected is asserted below against the new shape.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type { CycleRow, RouteRow } from "@/api/endpoints";
import type { TableRequestState } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";

import { isDayOfMonth, movesFor, schedulePreview, selectionTotals } from "./RoutesCyclesWizards";
import { refusalOf } from "./settingsShared";
import {
  RoutesCyclesTab,
  cyclesPageKeyFor,
  deactivationImpact,
  routesPageKeyFor,
  lifecycleTone,
  orDash,
  readWindowLabel,
} from "./SettingsRoutesCyclesTab";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const ROUTES: RouteRow[] = [
  {
    id: "r1",
    code: "SCW-R1",
    name: "Downtown",
    route_type: "drive",
    feeder_ref: null,
    assigned_to: null,
    cycle_id: "c1",
    cycle_code: "SCW-M",
    status: "active",
    members: 412,
    meters: 418,
    collected: null,
    last_completion: null,
    progress: null,
    service_id: "s1",
    service_code: "water",
    services: ["water"],
    service_ids: ["s1"],
    area_id: null,
    area_code: null,
    area_name: null,
    notes: null,
    premises: 388,
    units: 412,
    meters_available: 420,
    meters_excluded: 2,
    excluded_asset_ids: ["a1", "a2"],
    exclusions: [],
  },
  {
    id: "r4",
    code: "SCW-R4",
    name: "Southside",
    route_type: "walk",
    feeder_ref: null,
    assigned_to: null,
    cycle_id: null,
    cycle_code: null,
    status: "draft",
    members: 0,
    meters: 0,
    collected: null,
    last_completion: null,
    progress: null,
    service_id: null,
    service_code: null,
    services: [],
    service_ids: [],
    area_id: null,
    area_code: null,
    area_name: null,
    notes: null,
    premises: 0,
    units: 0,
    meters_available: 0,
    meters_excluded: 0,
    excluded_asset_ids: [],
    exclusions: [],
  },
];

const CYCLES: CycleRow[] = [
  {
    id: "c1",
    code: "SCW-M",
    routes: ["SCW-R1", "SCW-R2"],
    window_start: null,
    window_end: null,
    bill_date: null,
    due_days: null,
    due_date: null,
    expected: 702,
    collected: null,
    progress: null,
    status: "scheduled",
    lifecycle_status: "active",
    name: "Monthly — residential",
    // ⚠ THE SERVER'S OWN WORD SINCE RC-W1's MIGRATION 0019. CR-006 wrote
    // `monthly`; `schedule.FREQUENCIES` serves `Monthly`, and the screen that
    // keyed the old spelling rendered the raw catalogue key.
    frequency: "Monthly",
    start_day: 1,
    days_to_complete: 3,
    read_window_source: "derived",
    first_run_date: "2026-10-01",
    bill_day: 5,
    accounts: 1124,
    route_ids: ["r1"],
    proposed_windows: [],
    next_period: null,
    next_cycle_date: null,
    effective_start_day: 1,
    start_day_differs: false,
    schedule_warning: null,
    schedule_gap: null,
  },
];

/** The state both landings open on. Seeded through the SCREEN's own key
 *  builder so a key change cannot leave this suite rendering a skeleton and
 *  passing every absence assertion in the file. */
const OPEN_STATE: TableRequestState = {
  q: "",
  sort: "code",
  dir: "asc",
  page: 1,
  per: 50,
  filters: {},
};

/**
 * ⚠ **THE SUB-TAB IS SET THROUGH THE URL, NOT A PROP.** SET-05 is two sub-tabs
 * now (B17 §4), so a render is a render OF ONE OF THEM — and `?rc=` is how a
 * person, a link and this suite all say which. An optional `subTab` prop was
 * written first and G13 named it on the commit that added it: `SettingsPage`
 * never passed one, so it would have existed for tests alone. The
 * two-stacked-tables assertions this file used to make moved to
 * `SettingsRoutesCycles.cr029.test.tsx` with the markup they were about.
 */
function renderTab(
  readOnly = false,
  subTab: "routes" | "cycles" = "routes",
  cycles: readonly CycleRow[] = CYCLES,
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(routesPageKeyFor(OPEN_STATE), {
    rows: ROUTES,
    total: ROUTES.length,
    pagedBy: "client",
  });
  queryClient.setQueryData(cyclesPageKeyFor(OPEN_STATE), {
    rows: cycles,
    total: cycles.length,
    pagedBy: "client",
  });
  queryClient.setQueryData(["cycles", "coverage", "landing"], { uncovered_accounts: 42 });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/acme/settings/reference-data/routes-cycles?rc=${subTab}`]}>
          <RoutesCyclesTab readOnly={readOnly} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CR-006 SET-05 — the Routes & Cycles landing page", () => {
  it("both sub-tabs render, and the cycle shows DAY-OF-MONTH defaults, never dates", () => {
    expect(renderTab(false, "routes")).toContain("SCW-R1");
    const cycles = renderTab(false, "cycles");
    expect(cycles).toContain("SCW-M");
    expect(cycles).toContain("Monthly");
    // BR-MET-077: a SHAPE — not a rendered calendar date. The old screen put
    // `<time dateTime=…>` here; a cycle stores no date now. CR-029 splits the
    // one "1–3" cell into the two fields it always was, `start_day` and
    // `days_to_complete`, so the assertion follows the ruled model.
    expect(cycles).not.toContain("dateTime=");
    expect(readWindowLabel(CYCLES[0], "—")).toBe("1–3");
  });

  it("BR-MET-078: NOTHING on this surface names a fee, a rate or a late date", () => {
    const html = (renderTab(false, "routes") + renderTab(false, "cycles")).toLowerCase();
    for (const banned of ["late fee", "penalty", "grace", "$", "late /"]) {
      expect(html).not.toContain(banned);
    }
  });

  it("BR-MET-076: a draft route wears a Draft pill, and draft is not inactive", () => {
    expect(renderTab()).toContain("Draft");
    expect(lifecycleTone("draft")).toBe("warning");
    expect(lifecycleTone("inactive")).toBe("neutral");
    expect(lifecycleTone("active")).toBe("success");
  });

  it("B14 rule 15: row actions are ICONS that still carry their name", () => {
    const html = renderTab();
    // The words moved onto the control; they did not disappear. That is what
    // makes an icon usable without a mouse — an unnamed icon passes a
    // text-absence check and is unreachable.
    expect(html).toContain('aria-label="Edit SCW-R1"');
    expect(html).toContain('aria-label="Deactivate"');
    expect(html).toContain('aria-label="Delete"');
    expect(html).toContain("<svg");
    // …and no text link survives in the actions column.
    expect(html).not.toContain(">Edit<");
    expect(html).not.toContain(">Delete<");
  });

  it("B14 rule 16: each sub-tab carries the pagination footer with its five sizes", () => {
    for (const subTab of ["routes", "cycles"] as const) {
      const html = renderTab(false, subTab);
      expect(html).toContain("Rows per page");
      for (const size of [50, 100, 200, 500, 1000]) {
        expect(html).toContain(`>${size}<`);
      }
      // ⚠ EXACTLY ONE FOOTER PER RENDER, and the count is the assertion. CR-029
      // split the stacked pair into sub-tabs, so "2" would now mean a second
      // table leaked onto a tab that should show one.
      expect(html.split("table-pager-range").length - 1).toBe(1);
    }
  });

  it("B14 rule 17: an empty list says what is missing AND offers the action", () => {
    /**
     * ⚠ **THE ACTION IS ASSERTED INSIDE THE EMPTY-STATE BLOCK, and the first
     * version of this case could not fail.** It read `expect(html).toContain(
     * "+ Add route")`, which passes whether or not the empty state has a
     * button — because the PAGE HEADER has one too. Deleting the empty state's
     * button left this test GREEN. That is DEF-182's shape exactly: a check
     * whose output cannot distinguish pass from fail.
     *
     * CR-029 moved the empty state into the shared `DataTable`'s `EmptyList`
     * (the `settings-empty` cell is gone with the hand-rolled table), so the
     * block is located by that component's own class instead — the assertion
     * keeps its teeth and stops naming markup this screen no longer owns.
     */
    for (const [subTab, title, action] of [
      ["routes", "No routes yet", "+ Add route"],
      ["cycles", "No billing cycles yet", "+ Add cycle"],
    ] as const) {
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      queryClient.setQueryData(routesPageKeyFor(OPEN_STATE), {
        rows: [],
        total: 0,
        pagedBy: "client",
      });
      queryClient.setQueryData(cyclesPageKeyFor(OPEN_STATE), {
        rows: [],
        total: 0,
        pagedBy: "client",
      });
      queryClient.setQueryData(["cycles", "coverage", "landing"], { uncovered_accounts: 0 });
      const html = renderToStaticMarkup(
        <QueryClientProvider client={queryClient}>
          <ToastProvider>
            <MemoryRouter
              initialEntries={[`/acme/settings/reference-data/routes-cycles?rc=${subTab}`]}
            >
              <RoutesCyclesTab readOnly={false} />
            </MemoryRouter>
          </ToastProvider>
        </QueryClientProvider>,
      );
      expect(html).toContain(title);
      const blocks = html.split('class="state-frame state-empty"').slice(1);
      expect(blocks).toHaveLength(1);
      expect(blocks[0]).toContain("<button");
      expect(blocks[0]).toContain(action);
    }
  });

  it("SET-05: deactivating a route in a cycle warns with the cycle's OWN window", () => {
    // Verbatim from the CR: *"Route SCW-R2 is in cycle SCW-M — reads
    // scheduled Sep 1–5 will skip 388 premises."*
    const impact = deactivationImpact(ROUTES[0], CYCLES);
    expect(impact).toEqual({ cycle: "SCW-M", from: 1, to: 3, premises: 388 });
    expect(
      t("settings.routes.deactivateInCycle", {
        code: "SCW-R1",
        cycle: "SCW-M",
        from: 1,
        to: 3,
        premises: 388,
      }),
    ).toContain("will skip 388 premises");
  });

  it("a route on NO cycle gets no cycle warning — one that always fires is ignored", () => {
    expect(deactivationImpact(ROUTES[1], CYCLES)).toBeNull();
  });

  it("BR-MET-079: the reads-history refusal is the SERVER's, with its count", () => {
    const blocked = new ApiError(409, {
      code: "BIZ-LOCKED",
      message_key: "metering.route.delete_blocked_read_history",
      params: { reads: 1204, alternative: "deactivate" },
      br_ref: "BR-MET-079",
    });
    const refusal = refusalOf(blocked, t);
    expect(refusal.message).toContain("1204");
    expect(refusal.message).toContain("Deactivate");
    expect(refusal.brRef).toBe("BR-MET-079");
  });

  it("BR-MET-008: the members refusal still renders, with its own counts", () => {
    const blocked = new ApiError(409, {
      code: "BIZ-LOCKED",
      message_key: "metering.route.delete_blocked_referenced",
      params: { members: 412, service_points: 412, alternative: "deactivate" },
      br_ref: "BR-MET-008",
    });
    expect(refusalOf(blocked, t).message).toContain("412 members");
  });

  it("BR-MET-035b: a role that may not write sees the reason ON the control", () => {
    const html = renderTab(true);
    expect(html).toContain("Your role can view this, but not change it.");
    expect(html).toContain("disabled");
    // …and the controls are still THERE. BR-SHL-025 forbids hiding them: a
    // Billing Clerk must be able to see that routes are configured here.
    expect(html).toContain("+ Add route");
  });

  it("BR-MET-075: the meters column is available MINUS exclusions", () => {
    expect(ROUTES[0].meters).toBe(ROUTES[0].meters_available - ROUTES[0].meters_excluded);
    expect(renderTab()).toContain(">418<");
  });

  it("readWindowLabel and orDash never invent a figure the server has not given", () => {
    expect(readWindowLabel(CYCLES[0], "—")).toBe("1–3");
    // W5-T2: the label derives from the ruled pair, so the "nothing to say"
    // case is a cycle with no START DAY rather than no legacy from-day.
    // ⚠ **BOTH DAYS, NOT JUST THE STORED ONE (OQ-340, RC-W6b).** The label
    // reads the EFFECTIVE start day now, so a fixture that nulled `start_day`
    // and left `effective_start_day: 1` describes a cycle that cannot exist —
    // and the old one-field version of this line passed over the new code by
    // accident. A cycle with no anchor at all has neither.
    expect(
      readWindowLabel({ ...CYCLES[0], start_day: null, effective_start_day: null }, "—"),
    ).toBe("—");
    expect(orDash(null, "—")).toBe("—");
    expect(orDash(0, "—")).toBe("0");
  });

  /**
   * ⚠ **`paginate` WAS DELETED, NOT LEFT UNTESTED (CR-029 RC-W3-T1).** This
   * screen hand-rolled its own window because it hand-rolled its own table;
   * both are the shared `DataTable`'s now, so the slicing this case protected
   * is `tableTypes`' `clampPage`/`pageCount` and is asserted there. Removing
   * the case without saying so is how a deletion looks like a regression.
   */
});

describe("CR-006 SET-06/07 — the wizards' own rules", () => {
  const PICKER = [
    {
      id: "p1",
      premise_no: "PRM-1088",
      address_line: "1408 Elm St",
      premises_type: "Single-family",
      units: 1,
      unit_ids: ["u1"],
      meters: 1,
      area_code: "SOUTH",
      area_name: "South",
      area_path: "South · SE",
      current_route: null,
      current_route_id: null,
      on_this_route: false,
    },
    {
      id: "p2",
      premise_no: "PRM-1121",
      address_line: "903 Birch Ln",
      premises_type: "Single-family",
      units: 2,
      unit_ids: ["u2", "u3"],
      meters: 3,
      area_code: "SOUTH",
      area_name: "South",
      area_path: "South · SW",
      current_route: "SCW-R2",
      current_route_id: "r2",
      on_this_route: false,
    },
  ];

  it("BR-MET-074: the move is tallied PER ROUTE before the commit (B14 rule 11)", () => {
    expect(movesFor(PICKER, new Set(["p1"]))).toEqual([]);
    expect(movesFor(PICKER, new Set(["p1", "p2"]))).toEqual([{ route: "SCW-R2", count: 1 }]);
    // The consequence sentence is the CR's own, and its second half is the
    // part a staff member most needs: this changes who READS them.
    expect(t("settings.routes.wizard.moveBody")).toContain("No bills change");
  });

  it("the selection counter adds units and meters, not just premises", () => {
    expect(selectionTotals(PICKER, new Set(["p1", "p2"]))).toEqual({
      premises: 2,
      units: 3,
      meters: 4,
      unitIds: ["u1", "u2", "u3"],
    });
  });

  it("BR-MET-078: the preview STOPS at `due` — r10's late-fee clause is gone", () => {
    // ⚠ THE INPUTS ARE THE RULED FIELDS NOW (W5-T2). This passed
    // `{readFrom, readTo, due}` — three of the five columns metering 0021
    // dropped — and the wizard wrote them. It takes start day + days to
    // complete + due DAYS, and DERIVES the same window: the 1st for 3 days
    // closes on the 3rd, which is what `readTo: 3` still asserts.
    const preview = schedulePreview({
      startDay: "1",
      daysToComplete: "3",
      bill: "5",
      dueDays: "21",
    });
    expect(preview).toEqual({
      readFrom: 1,
      readTo: 3,
      exceptionsBy: 4,
      bill: 5,
      due: 26, // the 5th + 21 days, inside a nominal 31-day month
      wraps: false,
    });
    // DEF-224: the caller passes ORDINALS now, per r10's "bills out 5th · due
    // 26th". This case used to assert "due the 26" — the copy the walkthrough
    // filed — so it is inverted rather than deleted: it now fails if the
    // redundant "the" comes back.
    const rendered = t("settings.cycles.wizard.previewBody", {
      readFrom: 1,
      readTo: 3,
      exceptionsBy: "4th",
      bill: "5th",
      due: "26th",
    });
    expect(rendered).toContain("bills out 5th");
    expect(rendered).toContain("due 26th");
    expect(rendered).not.toContain("due the");
    // r10's string ends "· late fee 31st". Ours must not, and must not be
    // able to grow one from the Billing-defaults grace either.
    expect(rendered.toLowerCase()).not.toContain("late");
    expect(rendered.toLowerCase()).not.toContain("fee");
  });

  it("a due day on or before the bill day WRAPS rather than being refused", () => {
    // Net-10 billed on the 26th is a real cycle. r10's hint ("read → bill →
    // due → late") describes one example and must not refuse the others.
    // The 20th for 5 days closes on the 24th; billed on the 26th, Net-10 falls
    // due on the 5th of the FOLLOWING month.
    const preview = schedulePreview({
      startDay: "20",
      daysToComplete: "5",
      bill: "26",
      dueDays: "10",
    });
    expect(preview?.readTo).toBe(24);
    expect(preview?.due).toBe(5); // the 26th + 10 days = the 5th of the next month
    expect(preview?.wraps).toBe(true);
    expect(t("settings.cycles.wizard.previewWraps")).toContain("following month");
  });

  it("day-of-month validation is 1–31, and a bad day yields no preview at all", () => {
    expect(isDayOfMonth("1")).toBe(true);
    expect(isDayOfMonth("31")).toBe(true);
    expect(isDayOfMonth("0")).toBe(false);
    expect(isDayOfMonth("32")).toBe(false);
    expect(isDayOfMonth("")).toBe(false);
    expect(
      schedulePreview({ startDay: "44", daysToComplete: "3", bill: "5", dueDays: "21" }),
    ).toBeNull();
    // ⚠ AND `dueDays: "0"` IS NOT NULL — due ON the bill date is lawful
    // (BR-MET-009: due_days ≥ 0), and the 1–31 check this box used to sit
    // behind would have refused it.
    expect(
      schedulePreview({ startDay: "1", daysToComplete: "3", bill: "5", dueDays: "0" })?.due,
    ).toBe(5);
  });

  it("BR-MET-081: an edit states inline that changes land next read window", () => {
    expect(t("settings.routes.wizard.nextReadWindow")).toContain("next read window");
    expect(t("settings.cycles.wizard.nextReadWindow")).toContain("next read window");
    // …and hard rule 4's promise travels with the first-run note.
    // ⚠ Capital N: the clause is the SECOND SENTENCE now, not a trailing
    // subordinate one (DEF-TEN-5707 split it to meet B14 rule 33's six-words-
    // per-sentence cap). The promise it carries is identical.
    expect(t("settings.cycles.wizard.firstRunNote")).toContain("Nothing already issued changes");
  });

  it("BR-MET-075: the copy says an excluded meter STAYS on its premises", () => {
    // ⚠ The sentence is plural now — *"Unticked meters stay on their
    // premises"* — because DEF-TEN-5707 cut a 27-word lede to two sentences of
    // six (B14 rule 33). BR-MET-075's promise is unchanged and still ON SCREEN:
    // it is a CONSEQUENCE of unticking, which rule 33 keeps, not rationale.
    expect(t("settings.routes.wizard.step3Lede")).toContain("stay on their premises");
    expect(t("settings.routes.wizard.noMeterBody")).toContain("no meter · verify");
  });

  it("BR-MET-080: the coverage flag says the count already allows for this cycle", () => {
    // ⚠ *"already counted"* rather than *"already allows for the routes"*.
    // B14 rule 33 names **a count qualifier** as a FACT and caps it at six
    // words, so the qualifier is exactly what survived the cut: a clerk still
    // cannot read this number as excluding the routes they just picked.
    expect(t("settings.cycles.wizard.uncoveredBody")).toContain("already counted");
  });

  it("BR-MET-073: a missing numbering series is REPORTED, never silently blank", () => {
    expect(t("settings.routes.wizard.codeSeriesMissing")).toContain("No numbering format");
  });

  it("ruling 2 reaches the user: the cycle wizard groups routes and states no date", () => {
    // ⚠ **THIS ASSERTION MOVED FROM A PARAGRAPH TO THE BUILD, AND THAT IS THE
    //    POINT (DEF-TEN-5707).** It used to read the 32-word step-1 lede for
    //    *"group of routes"* and *"confirmed when you actually run it"*. That
    //    lede is DELETED: it was RATIONALE — what a cycle IS, explained to
    //    somebody already creating one — and B14 rule 33, ratified 2026-08-30
    //    and therefore NEWER than CR-006's ruling 2 of 2026-08-16, puts
    //    rationale at ZERO words on screen.
    //
    //    **The ruling did not move; only its explanation did.** Ruling 2 says
    //    the wizard DEFINES a cycle — identity and membership — and that the
    //    timing inputs are taken at run time. That is a statement about what
    //    this screen stores, and it is what is asserted here: step 2 picks
    //    ROUTES, and nothing on the surface states a date on which money moves
    //    (BR-MET-078). A sentence can be reworded by any lane; these cannot.
    //
    //    The full explanation still reaches a reader who wants it, on the cycle
    //    DETAIL screen's `defaultsFootnote` — which DEF-606 owns and asserts.
    expect(t("settings.cycles.wizard.step2Title").toLowerCase()).toContain("routes");
    expect(t("settings.cycles.wizard.railRoutes").toLowerCase()).toContain("routes");
    // Ruling 3 — defaults, and the run may override them — survives ON SCREEN
    // as a six-word FACT rather than a 44-word lede.
    const schedule = t("settings.cycles.wizard.step3Lede");
    expect(schedule).toContain("Defaults only");
    expect(schedule).toContain("Each run can change them");
  });

  it.todo(
    "browser walkthrough of SET-05/06/07 against r10 — hard-won law 6; no gate reads rendered output and none has run for this screen",
  );
});

// ═══════════════════════════════════════════════════════════════════════════
// OQ-340 — THE CYCLES LANDING SHOWS THE DAY THE CYCLE ACTUALLY STARTS
//
// PO, verbatim, 2026-08-23: *"A: first window 15–17 Sep (start day becomes
// decorative)"*. The engine anchors on the first run and does not rewrite
// `cycles.start_day`, so this column had a number in it that the product
// ignores — and the read-window label beside it was derived from that same
// number, which made TWO cells wrong from one cause.
// ═══════════════════════════════════════════════════════════════════════════
describe("SET-05.cycles — the start day is the EFFECTIVE one (OQ-340)", () => {
  /** The PO's own figure: start day 1, first run 15 Sep → windows on the 15th. */
  const DECORATIVE: CycleRow = {
    ...CYCLES[0],
    start_day: 1,
    first_run_date: "2026-09-15",
    effective_start_day: 15,
    start_day_differs: true,
  };

  it("the cell shows 15, and says the saved 1 is not the one used", () => {
    const html = renderTab(false, "cycles", [DECORATIVE]);
    expect(html).toContain("15");
    expect(html).toContain(t("settings.cycles.startDay.saved", { stored: 1 }));
  });

  it("the read-window label follows the effective day too — 15–17, not 1–3", () => {
    expect(readWindowLabel(DECORATIVE, "—")).toBe("15–17");
  });

  it("a cycle whose dates agree is unchanged — no suffix, and 1–3", () => {
    const html = renderTab(false, "cycles");
    expect(html).not.toContain(t("settings.cycles.startDay.saved", { stored: 1 }));
    expect(readWindowLabel(CYCLES[0], "—")).toBe("1–3");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-006 (SET-05/06/07) — the five PO rulings of 2026-08-16
// generated: 2026-08-09 by story-coder v1; REWRITTEN 2026-08-17 for CR-006
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ vitest (targeted)
// exceptions: no browser walkthrough — recorded as an it.todo above rather than claimed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
