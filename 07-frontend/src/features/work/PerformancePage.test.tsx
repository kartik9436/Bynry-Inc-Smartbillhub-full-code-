// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-054 (the performance tab) · US-WRK-051 (labour rates)
// Rules:    BR-WRK-053 (no link into Finance) · BR-WRK-004 (posted nowhere) ·
//           BR-WRK-020 (per role; a contractor one rate and a dash) ·
//           CLAUDE.md hard rule 2 (4 stored, 2 displayed — and Work-030's one
//           exception) · B14 rule 31 (no database id is a visible value) ·
//           rule 34 (*Recorded*, never *In the books*) · law 2 (built is not
//           wired, and its mirror — a live screen behind a dead door)
// Tests:    this file
// ───────────────────────────────────────────────────────
/**
 * `Work-027` and `Work-030`, and the things they must NOT show.
 *
 * ⚠ **THIS FILE MOUNTS NO ROUTED COMPONENT, AND SAYS SO RATHER THAN CLAIMING
 * OTHERWISE.** It asserts TABLE CONFIGS and ROUTE CONSTANTS: every cell below
 * is rendered on its own through `renderToStaticMarkup`, and no page is
 * rendered at all. Until 2026-09-05 the paragraph here described a routed
 * fixture — `MemoryRouter`, `Routes`, a `QueryClientProvider` — and the file
 * imported all three and used none of them, so the guarantee was a comment
 * (hard-won law 1) and eslint was the only thing that noticed.
 *
 * The address check this file DOES make is `DEF-WRK-4051`'s, in its own
 * describe below: a route constant may not carry `:tenant`, because `App.tsx`
 * mounts these under a `:tenant` route and registers each as `ROUTE.slice(1)`.
 * That is what caught wave H's two unreachable screens.
 *
 * The routed mount — the component under the real `/:tenant/...` path pattern,
 * so `useParams().tenant` is defined and an address assertion can tell a
 * working link from `//...` — lives in two other files and is no longer owed
 * (`DEF-WRK-4077`, closed 2026-10-05): `recordedServerShapes.dom.test.tsx`
 * mounts `PerformancePage` at `/:tenant/work/performance` and
 * `recordedShapes.dom.test.tsx` mounts `LabourRatesPage` at
 * `/:tenant/settings/labour-rates`.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";
import { WORK_TABS, WORK_PERFORMANCE_ROUTE } from "./WorkShell";
import { performanceTableConfig } from "./PerformancePage";
import { labourRatesTableConfig, WORK_LABOUR_RATES_ROUTE } from "./LabourRatesPage";

// ⚠ `as unknown as string` and not `as string`: i18next's return type does not
// overlap `string` closely enough for a direct assertion, and the TEST RUNNER
// DOES NOT TYPECHECK — `npx vitest run` was green on this file while `tsc`
// was red. The build typechecks, so a green suite here is not evidence.
const t = (key: string, params?: Record<string, unknown>) =>
  i18n.t(key, params as never) as unknown as string;

describe("US-WRK-054 — the performance tab carries nothing into Finance", () => {
  it("no column, cell or label mentions Finance, Cost & Margin, O&M or an account code", () => {
    // `BR-WRK-053`. r10 says the total *"feeds the O&M / labour line in
    // Finance → Cost & Margin"*; that arrow is not built, and the reason is
    // that payroll already posts the hour — posting field labour beside it
    // would count the same hour twice (`OQ-WRK-1491`, closed to option (a)).
    const config = performanceTableConfig(t, {
      costPerJob: () => null,
      totalCost: () => null,
    });
    const rendered = JSON.stringify(config.columns.map((c) => c.label));
    for (const forbidden of ["Finance", "Cost & Margin", "O&M", "5300", "6020"]) {
      expect(rendered).not.toContain(forbidden);
    }
  });

  it("the cost tile says Recorded — B14 rule 34's pair of words, and it is true", () => {
    // *Recorded* and *In the books* are ONE pair across all eleven catalogues.
    // This figure is recorded; it is not in the books, so the other word would
    // be inconsistent AND false.
    expect(t("work.performance.tile.recorded")).toBe("Recorded");
    expect(t("work.performance.tile.recorded")).not.toContain("In the books");
  });

  it("every column the drawing names is present, and no more", () => {
    const config = performanceTableConfig(t, { costPerJob: () => null, totalCost: () => null });
    expect(config.columns.map((c) => c.key)).toEqual([
      "job_type",
      "volume",
      "sla_met_pct",
      "first_time_fix_pct",
      "cost_per_job",
      "total_cost",
    ]);
  });

  it("DEF-WRK-4393 — there is no search box, because the endpoint cannot search", () => {
    // ⚠ ABSENT, not empty. `DataTable` renders the box on `!== undefined`, so
    // `searchFields: []` draws a LIVE search field over `GET /work/performance`,
    // which reads `period` and nothing else. `AwaitingApprovalPage` wrote this
    // rule down in its own test and this screen shipped the empty array anyway.
    // Put `searchFields: []` back and this case fails, which is its red proof.
    const config = performanceTableConfig(t, { costPerJob: () => null, totalCost: () => null });
    expect(config.searchFields).toBeUndefined();
    expect(config.searchPlaceholder).toBeUndefined();
  });

  it("the tab is wired to a screen and the screen is reachable at that address", () => {
    // Law 2 BOTH WAYS: the tab exists (a screen with no door is dead UI) and it
    // points at the route the app actually registers (a door onto nothing is
    // the mirror, and it is the one G13 cannot see).
    const tab = WORK_TABS.find((entry) => entry.id === "performance");
    expect(tab).toBeDefined();
    expect(tab?.path).toBe(WORK_PERFORMANCE_ROUTE);
    expect(i18n.exists("work.tabs.performance")).toBe(true);
  });
});

describe("DEF-WRK-4051 — a route constant carries no tenant segment", () => {
  it("neither of this wave's routes repeats :tenant", () => {
    // ⚠ **BOTH OF WAVE H's SCREENS WERE UNREACHABLE FROM THE DAY THEY SHIPPED**
    // because their constants carried the tenant while `App.tsx` mounts them
    // under a `:tenant` route and registers each as `ROUTE.slice(1)` — so they
    // came out `:tenant/:tenant/...`, matched nothing, and fell through to
    // *"This screen is not built yet"*. `tsc`, all 44 frontend test files, the
    // build and `G13` passed over it.
    for (const route of [WORK_PERFORMANCE_ROUTE, WORK_LABOUR_RATES_ROUTE]) {
      expect(route).not.toContain(":tenant");
      expect(route.startsWith("/")).toBe(true);
      // `.slice(1)` must leave a usable child path, not an empty string.
      expect(route.slice(1).length).toBeGreaterThan(0);
    }
  });
});

describe("US-WRK-051 — Work-030 shows four decimals, and a contractor a dash", () => {
  const config = (cells?: Partial<Parameters<typeof labourRatesTableConfig>[1]>) =>
    labourRatesTableConfig(t, {
      overtime: cells?.overtime ?? (() => null),
      threshold: cells?.threshold ?? (() => null),
      status: cells?.status ?? (() => null),
      effectiveFrom: cells?.effectiveFrom ?? (() => null),
    });

  it("the hourly rate is rendered VERBATIM at four decimals, never parsed", () => {
    // This is the ONE screen in the product that shows four, because the stored
    // value is what is being edited: a supervisor who types `48.5000` must see
    // `48.5000` back. The same rate is `$48.50` on the report a customer reads.
    // ⚠ The string is never turned into a number on the way — a float here is
    // the exact thing hard rule 2 forbids.
    const hourly = config().columns.find((c) => c.key === "hourly");
    const html = renderToStaticMarkup(
      <>{hourly?.cell?.({ hourly: "48.5000" } as never)}</>,
    );
    expect(html).toContain("48.5000");
    expect(html).not.toContain("48.50<");
  });

  it("there is no technician column and no way to reach one", () => {
    // `WM-45`: *"a per-person rate is a salary, it belongs in payroll, and
    // putting it on the crews screen would make WS-23 a page a billing clerk
    // must not open."*
    const keys = config().columns.map((c) => c.key);
    for (const forbidden of ["technician", "technician_id", "person", "employee"]) {
      expect(keys).not.toContain(forbidden);
    }
  });

  it("the ROLE CODE is never the visible value — B14 rule 31", () => {
    const role = config().columns.find((c) => c.key === "role_label");
    const html = renderToStaticMarkup(
      <>
        {role?.cell?.({ role: "field_technician", role_label: "Field technician" } as never)}
      </>,
    );
    expect(html).toContain("Field technician");
    expect(html).not.toContain("field_technician");
  });

  it("the footnote explains the four decimals in a clerk's words, with no rule id", () => {
    // B14 rule 32 — no rule id or internal code in clerk-facing copy.
    const footnote = t("work.labourRates.footnote");
    expect(footnote).toContain("four decimal");
    for (const forbidden of ["hard rule", "BR-WRK", "CLAUDE", "rule 2", "OQ-"]) {
      expect(footnote).not.toContain(forbidden);
    }
  });

  it("the consequence box states the one thing that matters before changing a price", () => {
    expect(t("work.labourRates.consequence.title")).toBe("A rate is dated.");
    expect(t("work.labourRates.consequence.body")).toContain("closed at");
  });
});

describe("every key both screens ask for exists in the catalogue", () => {
  it("no raw key can reach the screen", () => {
    // ⚠ `work.tabs.crews` existed in NONE of the eleven catalogues, so i18next
    // printed the key itself on every Work screen and the Product Owner saw it
    // in the running product. `G15` checks PARITY between catalogues, and a key
    // missing from all eleven is perfectly parity-clean — so nothing caught it.
    const keys = [
      "work.tabs.performance",
      "work.performance.title",
      "work.performance.description",
      "work.performance.tile.slaMet",
      "work.performance.tile.recorded",
      "work.performance.total",
      "work.performance.empty.title",
      "work.performance.empty.ctaReason",
      "work.performance.consequence.title",
      "work.performance.consequence.body",
      "work.labourRates.kicker",
      "work.labourRates.title",
      "work.labourRates.description",
      "work.labourRates.hoursPerDay",
      "work.labourRates.status.superseded",
      "work.labourRates.footnote",
      "work.labourRates.empty.ctaReason",
    ];
    for (const key of keys) {
      expect(i18n.exists(key), `${key} is missing — i18next would print the key`).toBe(true);
      expect(t(key)).not.toBe(key);
    }
  });
});
