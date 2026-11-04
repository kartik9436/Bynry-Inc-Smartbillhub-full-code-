// ── Trace ──────────────────────────────────────────────
// Story:    US-REP-019 (S7 — the landing screen)   Screens: S7 / DSH-01
// Change:   CR-012 (PO 2026-08-18) — S7 becomes r10's DSH-01: six independent
//           regions, five FIXED service rows, bars proportional to the LARGEST
//           service, and money pre-formatted on the server.
// Rules:    BR-REP-025 (five fixed rows, em-dash never $0.00) · BR-REP-026 (bar
//           is a share of the largest, not the total) · BR-REP-028 (a region
//           fails alone) · BR-REP-029 (money is formatted where it is rounded)
//           · BR-REP-034 (no typed target ⇒ the figure alone, and that is a
//           RULED state, not a stub) · BR-REP-024 (a tile never computes) ·
//           BR-REP-033 (page actions decided on the server)
// ───────────────────────────────────────────────────────
// ⚠ THIS FILE REPLACES ITS OWN PREDECESSOR, AND THE REPLACEMENT IS DELIBERATE.
//
// The version before this one (generated 2026-08-16, DEF-129 lane) asserted the
// OPPOSITE of three things CR-012 requires, because it was written for a
// dashboard that could refuse nearly everything:
//
//   old TC-5  `expect(html).not.toContain("<table")`   — aging drew no table
//   old TC-6  `expect(html).not.toContain("width:")`   — the mix drew no bars
//   old TC-7  `expect(html).not.toMatch(/\b\d+\b/)`    — To-do carried no counts
//
// All three were correct then and are wrong now: CR-012 requires an aging table,
// requires bars, and requires To-do counts. Amending them in place would have
// hidden that a signed expectation moved, so the supersession is stated here —
// the tests did not "start failing", the requirement changed under them.
//
// What SURVIVES from that file, because CR-012 did not touch it: a KPI its owner
// does not publish still renders a REASON and never a zero, and that reason is
// keyed on the server's stable code rather than its English prose.
import { renderToStaticMarkup } from "react-dom/server";
import { StaticRouter } from "react-router-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  DashboardAgingRow,
  DashboardKpiTile,
  DashboardPeriodFilter,
  DashboardPeriodOption,
  DashboardRegion,
  DashboardServiceMix,
  DashboardTodoRow,
  LedgerUnavailable,
} from "@/api/endpoints";
import {
  ACTIVITY_CLASSES,
  ActivityRows,
  AgingTable,
  CycleStatusLine,
  KPI_ORDER,
  MIX_LABEL_KEYS,
  GAP_ACTIVE_CONNECTIONS,
  GAP_FAILED_PAYMENTS,
  GAP_REGION_FAILED,
  GAP_UNBILLED_READS,
  MixRow,
  PeriodBar,
  RegionFrame,
  ServiceMixBody,
  TODO_ONBOARDING_CODES,
  TodoRows,
  activityLabel,
  dashboardKpis,
  dashboardQueryKey,
  figureAgeMinutes,
  periodOptionLabel,
  reasonFor,
} from "./DashboardPage";

const t = i18n.getFixedT("en");

//: The PO's own figures for the bar rule (CR-013 record, "THE BAR RULE, WORKED"):
//: Electric $238,400 · Water $76,200 · Sewer $28,100, Trash and Gas unsold.
//: Share of the LARGEST gives 100 / 32 / 12 — a column summing to 144, which is
//: the rule working. r10's markup computes 70/22/8 (share of the TOTAL) and the
//: requirement REVERSED it, so these integers are the regression pin.
const MIX: DashboardServiceMix = {
  rows: [
    { service_code: "electric", amount: "238400.000000", display: "$238k", bar_pct: 100, share: 70, share_display: "70%" },
    { service_code: "water", amount: "76200.000000", display: "$76k", bar_pct: 32, share: 22, share_display: "22%" },
    { service_code: "sewer", amount: "28100.000000", display: "$28k", bar_pct: 12, share: 8, share_display: "8%" },
    { service_code: "trash", amount: null, display: "—", bar_pct: 0, share: null, share_display: null },
    { service_code: "gas", amount: null, display: "—", bar_pct: 0, share: null, share_display: null },
  ],
  remainder: null,
};

const GAPS: LedgerUnavailable[] = [
  { code: GAP_UNBILLED_READS, br_ref: "BR-REP-002 · BR-REP-024", detail: "metering publishes no unbilled-read count" },
  { code: GAP_ACTIVE_CONNECTIONS, br_ref: "BR-REP-012", detail: "customers publishes no status-class breakdown" },
  { code: GAP_FAILED_PAYMENTS, br_ref: "BR-REP-002 · BR-REP-024", detail: "payments publishes a fifty-row list, not a count" },
];

const ok = <T,>(data: T): DashboardRegion<T> => ({ state: "ok", data, error: null, unavailable: [] });

describe("CR-012 · DSH-01 · the service mix draws all five services", () => {
  // DEF-282 FIXED 2026-08-19 — marker LIFTED. The five service labels had no
  // catalogue entry in any of the eleven, so this rendered
  // "dashboard.service.electric" on the first screen after every sign-in. Forty
  // keys landed across all eleven catalogues; this case now passes by passing.
  it("BR-REP-025: five rows, in the ruled order, whether or not they billed", () => {
    const html = renderToStaticMarkup(<ServiceMixBody data={MIX} t={t} />);
    for (const label of ["Electric", "Water", "Sewer", "Trash", "Gas"]) {
      expect(html, `${label} row must be drawn`).toContain(label);
    }
    // Order is the contract — "so row order is stable month to month".
    const seen = ["Electric", "Water", "Sewer", "Trash", "Gas"].map((l) => html.indexOf(l));
    expect(seen).toEqual([...seen].sort((a, b) => a - b));
  });

  it("BR-REP-025: an unsold service shows an em-dash and NEVER $0.00", () => {
    const html = renderToStaticMarkup(<ServiceMixBody data={MIX} t={t} />);
    expect(html).toContain("—");
    // A printed zero and an absent service look identical and mean opposite
    // things. This is the assertion that keeps them apart.
    expect(html).not.toContain("$0.00");
    expect(html).not.toMatch(/>\s*0\s*</);
  });

  it("BR-REP-026: the bar width is the SERVER's integer — share of the largest, not the total", () => {
    const html = renderToStaticMarkup(<ServiceMixBody data={MIX} t={t} />);
    // 100 / 32 / 12 is share-of-largest. If anything here recomputed a share of
    // the total it would emit r10's 70 / 22 / 8 instead.
    expect(html).toContain("width:100%");
    expect(html).toContain("width:32%");
    expect(html).toContain("width:12%");
    expect(html).not.toContain("width:70%");
    expect(html).not.toContain("width:22%");
  });

  it("the number and the bar cannot disagree, because they are one figure", () => {
    const row = { service_code: "water", amount: "76200.000000", display: "$76k", bar_pct: 32, share: 22, share_display: "22%" };
    const html = renderToStaticMarkup(<MixRow row={row} t={t} />);
    expect(html).toContain("width:32%");
    expect(html).toContain("$76k");
  });
});

describe("CR-012 · DSH-01 · a region fails alone", () => {
  it("BR-REP-028: a failed region states its own reason and does not throw", () => {
    const failed: DashboardRegion<DashboardServiceMix> = {
      state: "error",
      data: null,
      error: { code: GAP_REGION_FAILED, br_ref: "BR-REP-028", detail: "the region read raised", region: "service_mix" },
      unavailable: [],
    };
    const html = renderToStaticMarkup(
      <RegionFrame region={failed} title="Service mix" t={t} emptyText="Nothing billed yet">
        {(data) => <ServiceMixBody data={data} t={t} />}
      </RegionFrame>,
    );
    // Its own header survives — the panel is present and says why it is empty…
    expect(html).toContain("Service mix");
    expect(html).toContain('role="note"');
    // …and it did NOT fall back to drawing rows from nothing.
    expect(html).not.toContain('data-dash="mix-fill"');
  });

  it("a neighbouring region renders normally while another is failed", () => {
    const html = renderToStaticMarkup(
      <RegionFrame region={ok(MIX)} title="Service mix" t={t} emptyText="Nothing billed yet">
        {(data) => <ServiceMixBody data={data} t={t} />}
      </RegionFrame>,
    );
    expect(html).toContain("width:100%");
  });

  it("an EMPTY region keeps its header rather than disappearing", () => {
    const empty: DashboardRegion<DashboardServiceMix> = { state: "empty", data: null, error: null, unavailable: [] };
    const html = renderToStaticMarkup(
      <RegionFrame region={empty} title="Service mix" t={t} emptyText="Nothing billed yet">
        {(data) => <ServiceMixBody data={data} t={t} />}
      </RegionFrame>,
    );
    expect(html).toContain("Service mix");
    expect(html).toContain("Nothing billed yet");
  });
});

describe("CR-012 · DSH-01 · money is formatted where it is rounded", () => {
  const tile = (over: Partial<DashboardKpiTile>): DashboardKpiTile => ({
    id: "ar", kind: "money", value: "152.320000", display: "$152.32",
    basis: "posting", sub: null, unavailable_code: null, ...over,
  });

  it("BR-REP-029: the server's display string is rendered verbatim, and nothing reformats it", () => {
    const tiles = dashboardKpis([tile({})], GAPS, t);
    const html = renderToStaticMarkup(<>{tiles.map((k) => ("value" in k ? k.value : null))}</>);
    expect(html).toContain("$152.32");
    // The unrounded decimal must never reach the screen — that would be the
    // client rounding a second time, with its own rules.
    expect(html).not.toContain("152.320000");
  });

  it("BR-REP-034: no typed revenue target ⇒ the figure ALONE, with no percentage and no bar", () => {
    // The PO's ruling on the forecast sub-line: a per-tenant target, degrading
    // to the bare figure when nobody has typed one. `sub: null` is that state,
    // and it is RULED — not a stub, not a missing feature.
    const tiles = dashboardKpis([tile({ id: "period_revenue", display: "$553.69" })], GAPS, t);
    const html = renderToStaticMarkup(
      <>{tiles.map((k) => ("value" in k ? [k.value, k.detail] : null))}</>,
    );
    expect(html).toContain("$553.69");
    expect(html).not.toContain("%");
    expect(html).not.toContain("target");
  });

  it("BR-REP-024 + PO 2026-08-19 d.4: a KPI its owner cannot publish reads PLAIN LANGUAGE and never a zero", () => {
    // Preserved verbatim in intent from the pre-CR-012 file: this is the DEF-104
    // shape (four surfaces disagreeing, an account reading $0.00 over an issued,
    // unpaid $108.88).
    //
    // ⚠ WHAT THE 2026-08-19 RULING CHANGED, AND THE THING IT DID NOT.
    // The tile used to read "Not available — payments publishes a fifty-row
    // list, not a count": our module boundaries, explained to a utility clerk.
    // It now reads **"Not counted yet"**, and the architecture sentence moves
    // into the SUPPORT text where a person diagnosing can reach it.
    //
    // The PO proposed "reads not received" and it was ruled AGAINST: that
    // asserts a fact about the UTILITY'S data (no reads arrived) where the true
    // fact is about OUR product (we cannot count them). This case asserts the
    // shipped wording AND asserts the rejected one never appears, so a later
    // "simplification" back to it goes red.
    const tiles = dashboardKpis(
      [tile({ id: "failed_payments", kind: "count", value: null, display: null, unavailable_code: GAP_FAILED_PAYMENTS })],
      GAPS,
      t,
    );
    const html = renderToStaticMarkup(
      <>{tiles.map((k) => ("value" in k ? [k.value, k.detail] : null))}</>,
    );
    expect(html).toContain("Not counted yet");
    expect(html).not.toContain("Not available");
    expect(html.toLowerCase()).not.toContain("not received");
    // The reason SURVIVES — it moved, it was not deleted.
    expect(html).toContain("fifty");
    expect(html).toMatch(/role="note"/);
    // `?? 0` would emit exactly this.
    expect(html).not.toMatch(/>\s*0\s*</);
  });

  it("the reason is keyed on the server's CODE, never its English prose", () => {
    expect(reasonFor(GAPS, GAP_FAILED_PAYMENTS, t)).toContain("fifty");
    expect(reasonFor(GAPS, GAP_FAILED_PAYMENTS, t)).not.toContain(
      "payments publishes a fifty-row list, not a count",
    );
    // ⚠ THIS CASE MOVED WITH THE FACT ON 2026-09-01, IT WAS NOT DELETED.
    // It used to read `.toContain("some_code_nobody_wrote_copy_for")` — the
    // fallback NAMED the server's code and the rule it cited, and the case
    // pinned that as the desired behaviour. B14 rule 31 says the opposite:
    // nothing internal is ever visible to a utility user, a rule number and a
    // server-side identifier included, and the PO photographed the result of
    // this exact sentence on the Finance screen. The provenance was not
    // deleted — it lives in the code comment beside each call site, and the
    // server still sends `code` and `br_ref` on the wire.
    // So the assertion is inverted and the SURVIVING half is asserted too: a
    // code with no copy must still say, in words, that the figure is absent.
    // A blank here would be worse than a long sentence (G38).
    const unknown = reasonFor(GAPS, "some_code_nobody_wrote_copy_for", t);
    expect(unknown).not.toContain("some_code_nobody_wrote_copy_for");
    expect(unknown).not.toMatch(/BR-[A-Z]{3}-\d+/);
    expect(unknown).toBe(t("finance.gap.unknown"));
    expect(unknown.length).toBeGreaterThan(0);
  });
});

describe("CR-012 · DSH-01 · aging and To-do", () => {
  // DEF-283 FIXED 2026-08-19 — the marker is LIFTED, which is the whole point of
  // having pinned it: `totalDisplay` was accepted, passed, and drawn nowhere, and
  // this case failed on exactly that. It now renders in a `tfoot`. If the total
  // ever stops rendering again this goes red as an ordinary failure rather than
  // quietly passing, which is what an un-lifted marker would have done.
  it("the aging table draws its bands and its total, and its percentages need not total 100", () => {
    // The PO ruled the percentages are "rounded, need not total 100%" — so a
    // test asserting they sum to 100 would be asserting a defect.
    const band = (
      bucket: string, accounts: number, amount: string, amountDisplay: string, share: number,
    ): DashboardAgingRow => ({
      bucket, accounts, accounts_display: String(accounts), amount,
      amount_display: amountDisplay, share, share_display: `${share}%`,
      // r10 puts its danger emphasis on the OLDEST bucket alone.
      emphasis: bucket === "over_90" ? "danger" : null,
    });
    const rows: DashboardAgingRow[] = [
      band("current", 812, "104200.000000", "$104,200.00", 61),
      band("d31_60", 96, "31400.000000", "$31,400.00", 18),
      band("d61_90", 24, "12800.000000", "$12,800.00", 8),
      band("over_90", 11, "22300.000000", "$22,300.00", 13),
    ];
    const html = renderToStaticMarkup(<AgingTable rows={rows} totalDisplay="$170,700.00" t={t} />);
    expect(html).toContain("$104,200.00");
    expect(html).toContain("$170,700.00");
    expect(61 + 18 + 8 + 13).toBe(100);
  });

  it("To-do rows route out through the real router — not dead spans", () => {
    // A panel of <span>s passes a text assertion and is hard-won law 2 all over
    // again: built, and not wired.
    const rows: DashboardTodoRow[] = [
      { kind: "review", code: "billing_exceptions", count: 3, count_display: "3", module: "billing", target: "billing" },
    ];
    const html = renderToStaticMarkup(
      <StaticRouter location="/brazosbend/dashboard">
        <TodoRows rows={rows} t={t} />
      </StaticRouter>,
    );
    expect(html).toContain("href=");
    expect(html).toContain("/brazosbend/");
  });
});

describe("CR-012 · the five PO rulings of 2026-08-19", () => {
  // RED, quoted, before any of this landed: MIX_LABEL_KEYS held five codes, so
  // a broadband utility's row rendered the raw code —
  //   AssertionError: expected '<span class="dash-mix-label">broadband…' to
  //   contain 'Broadband'
  // which is DEF-282's shape one ruling later: a served row with no label.
  it("d.1 · a service the tenant sells but this app had no label for renders its NAME, not its code", () => {
    const mix: DashboardServiceMix = {
      rows: [
        { service_code: "water", amount: "27000.000000", display: "$27k", bar_pct: 33, share: null, share_display: null },
        { service_code: "broadband", amount: "81000.000000", display: "$81k", bar_pct: 100, share: null, share_display: null },
      ],
      remainder: null,
    };
    const html = renderToStaticMarkup(<ServiceMixBody data={mix} t={t} />);
    expect(html).toContain("Broadband");
    expect(html).not.toContain(">broadband<");
  });

  it("d.1 · the label map covers ALL ELEVEN platform services, because the server may now send any of them", () => {
    // The row set is the TENANT's list, so every platform code is reachable.
    // A code with no label falls through to itself on the landing screen.
    //
    // ⚠ **THIS PIN DID NOT CATCH `fire` AND COULD NOT HAVE — SAY SO RATHER THAN
    // LETTING IT LOOK LIKE A CROSS-BOUNDARY CHECK (`DEF-3091`).** It compares
    // one frontend artefact to another frontend artefact written in the same
    // file, so on the day the catalogue went to eleven both sides still said
    // ten and this stayed green; it went red only once a person added `fire` to
    // the map by hand. The check that CAN see a missing service is
    // `signupServices.test.ts`, which reads the platform MIGRATIONS — and it
    // knows about one of the four hand-written service lists in this app.
    expect(Object.keys(MIX_LABEL_KEYS).sort()).toEqual(
      [
        "battery",
        "broadband",
        "electric",
        "fire",
        "gas",
        "sewer",
        "solar",
        "storm_water",
        "thermal_heat",
        "trash",
        "water",
      ],
    );
    for (const key of Object.values(MIX_LABEL_KEYS)) {
      expect(t(key), `${key} must have copy`).not.toBe(key);
    }
  });

  it("d.3 · a To-do row the owner could not count shows NO NUMBER — never a zero", () => {
    // THE defect the ruling was made about: `row.count ?? 0` printed "Review 0
    // billing exceptions", which tells the operator nothing needs their
    // attention. It does not, because nobody counted.
    const rows: DashboardTodoRow[] = [
      { kind: "action", code: "billing_exceptions", count: null, count_display: null, module: "billing", target: "billing" },
      { kind: "draft", code: "finance_close", count: null, count_display: null, module: "ledger", target: "finance" },
    ];
    const html = renderToStaticMarkup(
      <StaticRouter location="/brazosbend/dashboard">
        <TodoRows rows={rows} t={t} />
      </StaticRouter>,
    );
    expect(html).toContain("Review billing exceptions");
    // ⚠ THE DIGIT IS LOOKED FOR IN THE TEXT A PERSON READS, NOT IN THE MARKUP
    // (CR-018 Route B, 2026-08-22). This read `expect(html).not.toMatch(/\b0\b/)`
    // over the whole HTML string, and utilities put digits in `class=` —
    // `m-0`, `gap-2`, `pt-2` — so the assertion turned red on a migration that
    // changed nothing a user can see. Stripping the tags first asks the
    // question the ruling was actually about: does the OPERATOR read a zero?
    const text = html.replace(/<[^>]*>/g, " ");
    expect(text).not.toMatch(/\b0\b/);
    expect(html).not.toContain("Review  billing");
  });

  it("d.3 · all six emittable To-do codes have countless copy in every one of the eleven catalogues", () => {
    const codes = [
      "billing_exceptions",
      "disconnect_eligible",
      "finance_close",
      "rate_approvals",
      "import_reads",
      "run_billing",
    ];
    for (const lng of i18n.options.supportedLngs === false
      ? ["en"]
      : (i18n.options.supportedLngs as string[]).filter((code) => code !== "cimode")) {
      const translate = i18n.getFixedT(lng);
      for (const code of codes) {
        const key = `dashboard.todo.itemNoCount.${code}`;
        expect(translate(key), `${lng} is missing ${key}`).not.toBe(key);
      }
    }
  });

  it("d.5 · the not-configured cycle line STATES the fact and offers no set-up link", () => {
    const html = renderToStaticMarkup(
      <StaticRouter location="/brazosbend/dashboard">
        <CycleStatusLine
          region={ok({
            state: "not_configured" as const,
            cycle_code: null,
            cycle_name: null,
            days: null,
            close_date: null,
            accounts: null,
          })}
          asOf="2026-08-19"
          t={t}
          locale="en-US"
        />
      </StaticRouter>,
    );
    expect(html).not.toContain("href=");
    expect(html).not.toContain("Set up billing cycles");
    expect(html).toContain("No billing cycle is set up yet.");
  });

  it("d.6 · the Recent-activity panel SAYS how far back it looked", () => {
    // "Nothing has happened here yet" means something very different at 24
    // hours than at forever, and on a utility's first Monday the difference is
    // the whole message.
    expect(t("dashboard.panel.activity", { hours: 24 })).toContain("24");
    expect(t("dashboard.activity.empty", { hours: 24 })).toContain("24");
    expect(t("dashboard.activity.empty", { hours: 24 })).not.toBe(
      "Nothing has happened here yet.",
    );
  });
});

describe("every one of the eleven catalogues carries this screen's strings", () => {
  it("no key on the first screen after sign-in renders as a raw dotted string", () => {
    for (const lng of i18n.options.supportedLngs === false
      ? ["en"]
      : (i18n.options.supportedLngs as string[]).filter((code) => code !== "cimode")) {
      const translate = i18n.getFixedT(lng);
      for (const key of [
        "dashboard.panel.todo",
        "dashboard.error.title",
        `finance.gap.${GAP_UNBILLED_READS}`,
      ]) {
        expect(translate(key), `${lng} is missing ${key}`).not.toBe(key);
      }
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-012 (12-governance/11-change-requests.md · "S7 Dashboard: make it the r10 DSH-01 screen") + US-REP-019
// screens: S7
// generated: 2026-08-19 — REPLACES the 2026-08-16 file, whose TC-5/6/7 asserted the pre-CR-012 contract
// checklist: A✔ B✔ C✔ D=deferred(fixture transcribed, not recomputed) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST for every 2026-08-19 case — the ten-service label map case failed on `expected '<span class="dash-mix-label">broadband…' to contain 'Broadband'`, and the refusal-copy case on `expected '<span class="dash-kpi-absent">Not cou…' to contain 'Not available'` before each ruling landed. tsc✔ eslint --max-warnings 0✔ vitest 20/20✔ (the browser half is 07-frontend/e2e/CR-012-dashboard.spec.ts, 8/8 against the booted stack)
// exceptions: (1) the mix figures are the PO's OWN worked example (238400/76200/28100 → 100/32/12), so this file pins the ruled arithmetic rather than the implementation's · (2) the three superseded assertions are quoted in the header rather than deleted silently, because a signed expectation moved and a reader must be able to see that it did
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

// ══════════════════════════════════════════════════════════════════════════
// CR-015 · THE PERIOD FILTER, AND THE PERIOD STATED ON SCREEN
// ══════════════════════════════════════════════════════════════════════════
//
// **RED PROVED FIRST.** Every case below failed on
// `SyntaxError: The requested module './DashboardPage' does not provide an
// export named 'PeriodBar'` before the component existed.
//
// ⚠ **WHAT THESE CASES REFUSE TO DO.** None of them asserts that a `<select>`
// exists. A picker nobody can read the window off is exactly what CR-015
// forbids — *"the selected period is stated prominently, NOT BURIED IN A
// FILTER CONTROL"* — so every case here asserts on the SPELLED-OUT DATES that
// a person compares against Finance, and the control is checked only for
// carrying the same options the server offered.
const PERIOD_OPTIONS: DashboardPeriodOption[] = [
  {
    id: "last_cycle",
    start: "2026-08-12",
    end: "2026-08-19",
    cycle_code: "08-B",
    cycle_name: null,
    fy_label: null,
    period_no: null,
  },
  {
    id: "last_30_days",
    start: "2026-07-21",
    end: "2026-08-19",
    cycle_code: null,
    cycle_name: null,
    fy_label: null,
    period_no: null,
  },
  {
    id: "last_period",
    start: "2026-07-01",
    end: "2026-07-31",
    cycle_code: null,
    cycle_name: null,
    fy_label: "FY2026",
    period_no: 10,
  },
];

const periodBar = (
  filter: DashboardPeriodFilter,
  asOf: string | null,
  ageMinutes: number | null = null,
) =>
  renderToStaticMarkup(
    <PeriodBar
      filter={filter}
      asOf={asOf}
      ageMinutes={ageMinutes}
      onSelect={() => undefined}
      t={t}
      locale="en-GB"
    />,
  );

describe("CR-015 · the dashboard states which window it is reporting over", () => {
  it("the SELECTED window is spelled out in dates, not only named in the control", () => {
    const html = periodBar(
      { selected: "last_cycle", default: "last_cycle", options: PERIOD_OPTIONS },
      "2026-08-19",
    );
    // The point of the whole requirement: a reader comparing this screen
    // against Finance meets the dates without opening anything.
    expect(html).toContain("12 Aug 2026");
    expect(html).toContain("19 Aug 2026");
    expect(html).toContain("Showing");
  });

  it("DEF-299: the as-of moment is stated beside the window, and it is the READ moment", () => {
    // The screen used to say `as of 31 Aug` on the 19th. Both halves of the
    // PO's consistency rule are on screen now: WHICH window, and AS OF WHEN.
    const html = periodBar(
      { selected: "last_cycle", default: "last_cycle", options: PERIOD_OPTIONS },
      "2026-08-19",
    );
    expect(html).toContain("Figures as of 19 Aug 2026");
  });

  it("a CLOSED window states the period end as its as-of, and the dates say so", () => {
    const html = periodBar(
      { selected: "last_period", default: "last_cycle", options: PERIOD_OPTIONS },
      "2026-07-31",
    );
    expect(html).toContain("1 Jul 2026");
    expect(html).toContain("31 Jul 2026");
    expect(html).toContain("Figures as of 31 Jul 2026");
  });

  // ⚠ **AMENDED 2026-08-23 (CR-029 D8① · RC-W3c) — THIS CASE USED TO ASSERT
  // "Last completed cycle" AND THAT COPY IS DELETED.** The PO withdrew the
  // whole concept — *"what makes a cycle completed - dont build it"* — so
  // `dashboard_period.OPTION_ORDER` never offers `last_cycle`, and its two
  // catalogue keys had no caller left and were removed from all eleven
  // catalogues. Rewriting the assertion rather than the copy would have put a
  // translated label behind an option no server sends.
  //
  // What the case still proves, and it is the half that matters: a
  // cycle-bearing option NAMES ITS CYCLE, and an option this app has no copy
  // for still names itself rather than rendering blank — the `defaultValue`
  // fallback `periodOptionLabel` documents, exercised here on a real id.
  it("a cycle-bearing option names its cycle, and an uncopied id names itself", () => {
    const html = periodBar(
      { selected: "last_cycle", default: "last_cycle", options: PERIOD_OPTIONS },
      "2026-08-19",
    );
    // "…· 08-B" is a window an operator recognises; "12 Aug – 19 Aug" alone is
    // an arbitrary week.
    expect(html).toContain("08-B");
    const withdrawn = periodOptionLabel(PERIOD_OPTIONS[0], t);
    expect(withdrawn).toContain("08-B");
    expect(withdrawn).not.toBe("");
    // The withdrawn option carries no translated label anywhere any more.
    expect(t("dashboard.period.option.last_cycle")).toBe("dashboard.period.option.last_cycle");
    expect(periodOptionLabel(PERIOD_OPTIONS[1], t)).toBe("Last 30 days");
  });

  it("every option the SERVER offered is in the control, and no option it did not", () => {
    const html = periodBar(
      { selected: "last_cycle", default: "last_cycle", options: PERIOD_OPTIONS },
      "2026-08-19",
    );
    expect(html).toContain('value="last_cycle"');
    expect(html).toContain('value="last_30_days"');
    expect(html).toContain('value="last_period"');
    // `this_period` was NOT offered by this server (no fiscal calendar), so the
    // screen must not invent it — an option selecting a window nobody can
    // compute is the same false affordance as a KPI showing zero.
    expect(html).not.toContain('value="this_period"');
  });

  it("no options at all ⇒ no bar, and certainly no empty picker", () => {
    expect(periodBar({ selected: null, default: null, options: [] }, null)).toBe("");
  });

  it("B14 rule 8: the picker is the shared `.input` select, not a bespoke one", () => {
    const html = periodBar(
      { selected: "last_cycle", default: "last_cycle", options: PERIOD_OPTIONS },
      "2026-08-19",
    );
    expect(html).toContain('class="input"');
  });

  it("the freshness line states the age of the figures, and says nothing while fresh", () => {
    // The PO's condition on caching — *"where cached, state cache age rather
    // than disagree with Finance"* — applied to the cache that EXISTS (the
    // 5-minute client `staleTime`). Under a minute it says nothing: "0 minutes
    // ago" reads as a fault where silence reads as the truth.
    const fresh = periodBar(
      { selected: "last_cycle", default: "last_cycle", options: PERIOD_OPTIONS },
      "2026-08-19",
      null,
    );
    expect(fresh).not.toContain("ago");

    const stale = periodBar(
      { selected: "last_cycle", default: "last_cycle", options: PERIOD_OPTIONS },
      "2026-08-19",
      4,
    );
    expect(stale).toContain("Read 4 minutes ago");
  });

  it("figureAgeMinutes floors to whole minutes and stays silent under one", () => {
    const base = 1_000_000;
    expect(figureAgeMinutes(base, base)).toBeNull();
    expect(figureAgeMinutes(base, base + 59_000)).toBeNull();
    expect(figureAgeMinutes(base, base + 60_000)).toBe(1);
    expect(figureAgeMinutes(base, base + 5 * 60_000 + 30_000)).toBe(5);
  });

  it("the cache key carries the period, so one window's figures cannot head another", () => {
    // With a constant key the 5-minute staleTime would serve the previous
    // window's figures under the new window's heading — the exact "dashboard
    // disagrees with Finance" failure the on-screen statement exists to stop.
    expect(dashboardQueryKey("last_period")).not.toEqual(dashboardQueryKey("last_cycle"));
    expect(dashboardQueryKey(null)).toEqual(dashboardQueryKey(undefined));
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-2417 · A MACHINE TOKEN IS NOT A LABEL — B14 rule 31
// ══════════════════════════════════════════════════════════════════════════
//
// **RED PROVED FIRST, and the quoted failures are the defect itself.** Before
// the catalogue keys landed, the first case below failed on
//
//     AssertionError: en has no label for the KPI tile ar-outstanding
//     expected 'dashboard.kpi.ar-outstanding' not to be
//              'dashboard.kpi.ar-outstanding'
//
// for all five tiles in all eleven catalogues, and the render case on
//
//     AssertionError: expected [ 'ar-outstanding', 'unbilled-reads', … ] to
//     contain 'AR outstanding'
//
// **WHY NOTHING CAUGHT IT WHILE IT WAS LIVE.** Every label on this screen is
// asked for through a key BUILT from the server's token, and a built key is
// invisible to the two checks that would otherwise have found it: G27 reads
// LITERAL `t("…")` calls only — its own docstring says a computed key "cannot
// be resolved without running the app" — and G18 treats the static stem
// `dashboard.kpi.` as covering every leaf beneath it, so the five camelCase
// keys that DID exist were never reported dead and the five kebab ids the
// server actually sends were never reported missing. Two gates, both green,
// disagreeing with each other.
//
// So the check has to be a TEST, and it has to ask in the SERVER's vocabulary:
// for every token the server can emit, is there copy? The Python half —
// `06-backend/tests/test_def2417_dashboard_labels.py` — reads the backend
// constants and this catalogue, so a tile added to `apps/reports/dashboard`
// with no label goes RED there. This half asserts the same lists in all ELEVEN
// catalogues, and asserts that a token the product has NO copy for still never
// reaches a screen.
describe("DEF-2417 · every server token on the landing screen renders LANGUAGE, never its id", () => {
  const languages = () =>
    i18n.options.supportedLngs === false
      ? ["en"]
      : (i18n.options.supportedLngs as string[]).filter((code) => code !== "cimode");

  const kpiTile = (id: string): DashboardKpiTile => ({
    id,
    kind: "money",
    value: "1234.000000",
    display: "$1,234.00",
    basis: null,
    sub: null,
    unavailable_code: null,
  });

  it("every KPI tile id the server can send has a label in all eleven catalogues", () => {
    for (const lng of languages()) {
      const translate = i18n.getFixedT(lng);
      for (const id of KPI_ORDER) {
        const key = `dashboard.kpi.${id}`;
        expect(translate(key), `${lng} has no label for the KPI tile ${id}`).not.toBe(key);
      }
    }
  });

  it("every operator activity class the server can send has a label in all eleven catalogues", () => {
    for (const lng of languages()) {
      const translate = i18n.getFixedT(lng);
      for (const klass of ACTIVITY_CLASSES) {
        const key = `dashboard.activity.class.${klass}`;
        expect(translate(key), `${lng} has no label for activity class ${klass}`).not.toBe(key);
      }
    }
  });

  it("every onboarding step the checklist can send has a label in all eleven catalogues", () => {
    for (const lng of languages()) {
      const translate = i18n.getFixedT(lng);
      for (const code of TODO_ONBOARDING_CODES) {
        const key = `dashboard.todo.onboarding.${code}`;
        expect(translate(key), `${lng} has no label for onboarding step ${code}`).not.toBe(key);
      }
    }
  });

  it("the three unnamed-token fallbacks are themselves translated everywhere", () => {
    // A fallback is what a token with no copy renders INSTEAD of itself. One
    // missing from a catalogue would print its own key, which is this defect
    // again, one level up.
    for (const lng of languages()) {
      const translate = i18n.getFixedT(lng);
      for (const key of [
        "dashboard.kpi.unnamed",
        "dashboard.activity.unnamed",
        "dashboard.todo.unnamed",
      ]) {
        expect(translate(key), `${lng} is missing ${key}`).not.toBe(key);
      }
    }
  });

  it("the five tiles carry their NAMES, and no tile carries its id", () => {
    const labels = dashboardKpis(KPI_ORDER.map(kpiTile), [], t).map((k) => k.label);
    expect(labels).toEqual([
      "AR outstanding",
      "Unbilled reads",
      "Failed payments",
      "Revenue this period",
      "Active connections",
    ]);
    // The ids are the CONTRACT and they stay — on the React key, on the wire,
    // in this fixture. What must never happen is one of them being READ ALOUD
    // by the screen, which is what `defaultValue: tile.id` did: `Kicker`
    // upper-cases the label, so the front page said AR-OUTSTANDING.
    for (const id of KPI_ORDER) {
      expect(labels, `${id} is printed as a label`).not.toContain(id);
      expect(labels).not.toContain(id.toUpperCase());
    }
  });

  it("a tile, an activity class and a to-do code this app has NO copy for still never print the token", () => {
    // The next tile the server adds. Before DEF-2417 this rendered
    // ANNUAL-TRUE-UP as the tile's own heading.
    const [unknownTile] = dashboardKpis([kpiTile("annual-true-up")], [], t);
    expect(unknownTile.label).toBe("Unnamed figure");

    // The activity feed's version of the same fallback: the server sends
    // `<class>.<verb>` and an unknown class used to print the whole action.
    expect(activityLabel("bill_run.finalised", t)).toBe("Bill run");
    expect(activityLabel("moon_landing.completed", t)).toBe("Other activity");

    // And the To-do panel's, on all three of its columns.
    const rows: DashboardTodoRow[] = [
      {
        kind: "action",
        code: "unheard_of",
        count: 3,
        count_display: "3",
        module: "billing",
        target: "billing",
      },
      {
        kind: "review",
        code: "also_unheard_of",
        count: null,
        count_display: null,
        module: "billing",
        target: "billing",
      },
      {
        kind: "onboarding",
        code: "not_a_step",
        count: null,
        count_display: null,
        module: "tenancy",
        target: "settings/company",
      },
    ];
    const todo = renderToStaticMarkup(
      <StaticRouter location="/brazosbend/dashboard">
        <TodoRows rows={rows} t={t} />
      </StaticRouter>,
    );
    expect(todo).not.toContain("unheard_of");
    expect(todo).not.toContain("not_a_step");
    expect(todo).toContain("Open task");
  });

  it("the activity row prints the CLASS in language and never the raw action string", () => {
    const html = renderToStaticMarkup(
      <ActivityRows
        rows={[
          {
            at: "2026-09-01T09:15:00Z",
            action: "read_batch.imported",
            // The audit row's own table name. It USED to render beside the
            // class label, so the feed read "Meter reads · read_batch" — the
            // same word twice, one of them in machine. See the comment in
            // `ActivityRows` for why it is not drawn any more and where it
            // still lives.
            entity_type: "read_batch",
            entity_id: "1f0c…",
            actor: "Sarah",
            amount: null,
            amount_display: "—",
          },
        ]}
        t={t}
        locale="en-US"
      />,
    );
    expect(html).toContain("Meter reads");
    expect(html).not.toContain("read_batch");
    expect(html).not.toContain("1f0c");
    // Nothing on this row is a lower_snake_case token. The assertion is on the
    // SHAPE rather than on the two values above, so a future field carrying
    // another table name cannot slip in beside them.
    expect(html.replace(/class="[^"]*"|data-[a-z]+="[^"]*"/g, "")).not.toMatch(
      />[^<]*[a-z]+_[a-z]+[^<]*</,
    );
  });

  it("the onboarding steps read as instructions a clerk can act on", () => {
    // B14 rule 33: an INSTRUCTION is at most six words per sentence, and the
    // panel's existing rows ("Run bills for this cycle") set the voice.
    for (const code of TODO_ONBOARDING_CODES) {
      const key = `dashboard.todo.onboarding.${code}`;
      const copy = t(key);
      // Without this line the word count would pass on the KEY itself, which
      // has no spaces — a check that cannot tell pass from fail.
      expect(copy, `${code} has no copy`).not.toBe(key);
      expect(copy.split(/\s+/).length, `${code}: "${copy}"`).toBeLessThanOrEqual(6);
    }
  });
});
