// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LOAD-BEARING AND MUST STAY ON LINE 1. `vite.config.ts` keeps
// the default environment at `node` deliberately (`DEF-523`), so an interactive
// suite opts in per file. Without it every case here dies on
// `ReferenceError: document is not defined`.
/* ── Trace ──────────────────────────────────────────────
 * Story:   US-RBS-003 (EP-RBS-01) — CR-075 wave D task D2.
 * Screens: RBS-001.1 (populated, 7 regions) · RBS-001.2 (first visit) ·
 *          RBS-001.3 (a run in flight).
 * Rules:   B14 rule 2 · rule 15 · rule 16 · rule 17 · rule 31 · rule 32 ·
 *          rule 33 · BR-SHL-025 · NFR-3.
 * Defects: DEF-CWP-3925 (mount under the REAL path pattern; a fixture that
 *          cannot tell a working link from a broken one) · DEF-RBS-4304 ·
 *          DEF-RBS-4327 · DEF-SHL-4043 (a reason that is only a `title` is a
 *          reason nobody reads).
 * ─────────────────────────────────────────────────────── */

/**
 * Every case asserts a RULE — a region, a column order, a destination, an
 * absent id — and none asserts an impression.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * MOUNTED THROUGH `APP_ROUTES` AT A REAL TENANT ADDRESS, NEVER BARE
 * ══════════════════════════════════════════════════════════════════════════
 * `DEF-CWP-3925`: the portal's front-page test mounted its component bare in a
 * `MemoryRouter` with no `/:tenant/portal` route, so `useParams().tenant` was
 * `undefined` and every address the page built came out `//portal/…` — a
 * protocol-relative URL to ANOTHER HOST, which reads as a perfectly good string
 * to `toContain`. **A fixture that cannot tell a working link from a broken one
 * is how that defect hid**, behind 42 test files and 391 green cases.
 *
 * So the routed cases render the product's OWN route table at
 * `/{tenant}/runbooks`, and every link is asserted by its RESOLVED `href`.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, within } from "@testing-library/react";
import { MemoryRouter, useRoutes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import i18n from "@/i18n";
import { APP_ROUTES } from "@/App";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import type { RunRow } from "./homeEndpoints";
import { RUNBOOKS_HOME_ROUTE, RUNBOOKS_HOME_SCREEN } from "./RunbooksHome";

const TENANT = "brazosbend";
const t = i18n.getFixedT("en");

// ⚠ **THERE IS NO AUTO-CLEANUP IN THIS REPO.** `vite.config.ts` sets no
// `setupFiles` and no `globals: true`, so `@testing-library/react` never
// registers its own `afterEach` and each render is ADDED to the same document.
// Every "exactly N" assertion below depends on this line.
afterEach(cleanup);

const DANA: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@brazosbend.example",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const ADMIN_PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "reports", label: "reports", access: "Full" as const }],
};

const REGIONAL = { timezone: "America/Chicago", date_format: "MM/DD/YYYY" };

function run(over: Partial<RunRow>): RunRow {
  return {
    id: "018f-0000-0000-0000-000000000001",
    runbook_key: "configuration_check",
    runbook_name: "Can we bill?",
    kind: "check",
    category: "billing",
    version: 1,
    mode: "dry",
    trigger: "manual",
    status: "done",
    started_at: "2026-09-06T13:12:00Z",
    finished_at: "2026-09-06T13:12:12Z",
    took_seconds: 12,
    counts: { blocker: 3 },
    records: 3,
    by: { trigger: "manual", person: null },
    ...over,
  };
}

/** A page as `readListPage` hands it over — `{rows, total}`, never the wire. */
function page(rows: RunRow[], total = rows.length) {
  return { rows, total };
}

function RoutedApp() {
  return useRoutes(APP_ROUTES);
}

/**
 * Render the REAL route table at `/{TENANT}/runbooks`, with the three reads
 * seeded so nothing goes to the network.
 *
 * ⚠ The seed keys must match `RunbooksHomePage`'s exactly. They do not have to
 * be asserted here: if one drifts the query goes to a disabled fetcher, the
 * screen renders its loading skeleton and every region assertion below fails
 * loudly — which is the property `navHoldExpiry.test.tsx` had to add a whole
 * self-check for, and which this suite gets for free by asserting regions.
 */
function mountHome(seed: {
  needsYou?: ReturnType<typeof page>;
  inFlight?: ReturnType<typeof page>;
  history?: ReturnType<typeof page>;
}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  queryClient.setQueryData(queryKeys.me, DANA);
  queryClient.setQueryData(queryKeys.myPermissions, ADMIN_PERMISSIONS);
  queryClient.setQueryData(queryKeys.shellDisplay, shellBootSeed(REGIONAL));
  queryClient.setQueryData(queryKeys.regionalSettings, REGIONAL);
  queryClient.setQueryData(
    ["runbooks", "home", "needsYou", 1, 50],
    seed.needsYou ?? page([]),
  );
  queryClient.setQueryData(["runbooks", "home", "inFlight"], seed.inFlight ?? page([]));
  queryClient.setQueryData(["runbooks", "home", "history", 1, 50], seed.history ?? page([]));
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <TenantRegionalProvider
          value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}
        >
          <MemoryRouter initialEntries={[`/${TENANT}${RUNBOOKS_HOME_ROUTE}`]}>
            <RoutedApp />
          </MemoryRouter>
        </TenantRegionalProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function homeRoot(): HTMLElement {
  const root = document.querySelector(`[data-screen="${RUNBOOKS_HOME_SCREEN}"]`);
  if (root === null) {
    throw new Error(
      `RBS-001 did not render at /${TENANT}${RUNBOOKS_HOME_ROUTE}. Either the route is gone ` +
        `from App.tsx, or the shell is holding on a seed this fixture does not provide — ` +
        `check ShellWithSession's gate before assuming the screen is broken.`,
    );
  }
  return root as HTMLElement;
}

describe("RBS-001.1 — the populated screen, region by region", () => {
  it("region 1 — the page head carries the kicker, the title and the subtitle", () => {
    mountHome({ history: page([run({})]) });
    const root = homeRoot();
    expect(within(root).getByText("Operations")).toBeTruthy();
    expect(within(root).getByRole("heading", { level: 1 }).textContent).toBe("Runbooks");
    expect(within(root).getByText("Checks report. Actions send.")).toBeTruthy();
  });

  it("region 1 — three actions in the frame's order: two live, one held", () => {
    // BR-SHL-025: a control that cannot act is DISABLED WITH ITS REASON, never
    // hidden. Linking them today would be worse than holding them —
    // `/{tenant}/runbooks/templates` matches `runbooks/:key` and opens the
    // setup screen for *the runbook whose key is templates*.
    mountHome({ history: page([run({})]) });
    const root = homeRoot();
    const actions = Array.from(
      root.querySelectorAll("[data-open], [data-held]"),
    ) as HTMLElement[];
    // The frame's order, whatever tier each one is in today.
    expect(actions.map((el) => (el.textContent ?? "").trim())).toEqual([
      "Templates →",
      "History →",
      "Work list →",
    ]);
    // Templates → is LIVE: RBS-002 landed the same day (CR-075 wave D task D3),
    // and this file's sibling homeHoldExpiry.test.tsx is what went red on it.
    const templates = actions[0];
    expect(templates.tagName).toBe("A");
    expect(templates.getAttribute("href")).toBe(`/${TENANT}/runbooks/templates`);
    // ⚠ **History → BECAME LIVE ON 2026-09-07** (`CR-075` wave I task `I6`),
    // and this assertion was turned around rather than deleted. Its address is
    // checked BY ADDRESS, because `DEF-CWP-3925`'s dead `//host/…` hrefs were
    // perfectly good strings to every check that only asked *is there a link*.
    const history = actions[1];
    expect(history.tagName).toBe("A");
    expect(history.getAttribute("href")).toBe(`/${TENANT}/runbooks/runs`);
    // ⚠ **Work list → BECAME LIVE ON 2026-10-02**, twenty-five days after
    // `RBS-007` landed at `runbooks/work` (2026-09-07, `df1ade52e`). This was
    // the held-button assertion — disabled, titled *"Not built yet."* — and it
    // was turned around rather than deleted, the same way History →'s was.
    const workList = actions[2];
    expect(workList.tagName).toBe("A");
    expect(workList.getAttribute("href")).toBe(`/${TENANT}/runbooks/work`);
    expect(root.querySelectorAll("[data-held]")).toHaveLength(0);
  });

  it("region 2 — four KPI tiles, and the two with no source draw a dash", () => {
    // DEF-RBS-4304. A confident zero under *Block billing* would read as
    // "nothing is stopping the bill run".
    mountHome({ needsYou: page([], 4), inFlight: page([], 1), history: page([run({})]) });
    const root = homeRoot();
    const labels = Array.from(root.querySelectorAll(".kpi .k")).map((n) =>
      (n.textContent ?? "").trim(),
    );
    expect(labels).toEqual([
      "Block billing",
      "Waiting for you",
      "Running now",
      "Ran clean today",
    ]);
    const absent = Array.from(root.querySelectorAll("[data-kpi-absent]")).map((n) =>
      n.getAttribute("data-kpi-absent"),
    );
    expect(absent).toEqual(["blockBilling", "ranCleanToday"]);
    // The absence is RENDERED, not a tooltip. DEF-SHL-4043: a reason that lives
    // only on `title` opens on hover, after a delay, and never on a touch
    // screen — twenty screens drew a grey button that said nothing.
    expect(within(root).getAllByText("Not counted yet.")).toHaveLength(2);
    // …and the two the server DOES answer carry its own totals.
    const values = Array.from(root.querySelectorAll(".kpi .v")).map((n) =>
      (n.textContent ?? "").trim(),
    );
    expect(values[1]).toBe("4");
    expect(values[2]).toBe("1");
  });

  it("regions 3 and 5 — two section headings, Needs you above Finished recently", () => {
    // `08-screen-layouts.md`: *Needs you* sits ABOVE *Finished recently*
    // because a clerk opening this screen has one real question.
    mountHome({ history: page([run({})]) });
    const headings = within(homeRoot())
      .getAllByRole("heading", { level: 5 })
      .map((h) => (h.textContent ?? "").trim());
    expect(headings).toEqual(["Needs you", "Finished recently"]);
  });

  it("region 4 — the Needs you table's five columns, in the sheet's order", () => {
    mountHome({
      needsYou: page([run({ status: "awaiting_approval", finished_at: null, took_seconds: null })]),
      history: page([run({})]),
    });
    const tables = homeRoot().querySelectorAll("table");
    const head = Array.from(tables[0].querySelectorAll("thead th")).map((n) =>
      (n.textContent ?? "").replace(/[⇅]/g, "").trim(),
    );
    expect(head.slice(0, 5)).toEqual(["Run", "State", "Detail", "Started", "Actions"]);
  });

  it("DEF-RBS-4334 — no unsubstituted {{placeholder}} reaches a clerk, anywhere", () => {
    // ⚠ **THIS SHIPPED TO A SCREENSHOT.** The Detail cell read `Records {{n}}`
    // in a real browser: i18next substitutes by NAME and the cell passed
    // `{ count: … }` against a line declaring `{{n}}`. `tsc` types that second
    // argument as an open record so any key compiles, eslint has no opinion,
    // G18 checks that a KEY has a call site and never that a PARAM has a value,
    // and this suite asserted the column HEADER and four other cells.
    //
    // Written as the GENERAL form rather than as one cell, so the next
    // mismatched param on this screen goes red whatever key it comes from.
    mountHome({
      needsYou: page([run({ status: "awaiting_approval", records: 3 })]),
      history: page([run({})]),
    });
    const root = homeRoot();
    const text = root.textContent ?? "";
    const leaked = text.match(/\{\{[^}]*\}\}/g) ?? [];
    expect(leaked, `an unsubstituted placeholder reached the screen: ${leaked.join(", ")}`).toEqual(
      [],
    );
    // …and the cell really says what it is for, rather than merely not saying
    // the braces — the assertion that would still pass over an empty cell.
    const needsBody = root.querySelectorAll("table")[0].querySelector("tbody");
    expect(needsBody?.textContent ?? "").toContain("Records 3");
  });

  it("region 6 — the Finished recently table's six columns, in the sheet's order", () => {
    mountHome({ history: page([run({})]) });
    const tables = homeRoot().querySelectorAll("table");
    const head = Array.from(tables[tables.length - 1].querySelectorAll("thead th")).map((n) =>
      (n.textContent ?? "").replace(/[⇅]/g, "").trim(),
    );
    expect(head.slice(0, 6)).toEqual([
      "Run",
      "Kind",
      "Outcome",
      "Took",
      "Finished",
      "Actions",
    ]);
  });

  it("no header offers a sort, because the endpoint declares none", () => {
    // `GET /runbooks/runs` passes `allowed_sorts=()`; it orders on
    // `(-started_at, -created_at, -id)` and drops a `sort` param. A ⇅ that
    // changes nothing is dead UI (hard-won law 2).
    mountHome({ history: page([run({})]) });
    expect(homeRoot().textContent).not.toContain("⇅");
  });

  it("region 7 — B14 rule 16: a pagination footer on BOTH tables, not just one", () => {
    // The sheet draws one, under *Finished recently*. The RULE puts one on
    // every list table and `NFR-3` makes it the deliverable rather than the
    // background, so the rule wins; the divergence is stamped in
    // 08-screen-layouts.md under RBS-001.
    mountHome({ needsYou: page([run({ status: "awaiting_approval" })]), history: page([run({})]) });
    expect(homeRoot().querySelectorAll(".table-pager")).toHaveLength(2);
  });

  it("the footer's total is the SERVER's count, never the number of rows drawn", () => {
    // NFR-5's shape on a screen. The RANGE is the page's window (`1–34` at 50
    // per page over 34 rows) and the TOTAL is the server's — a screen that
    // counted its own rows would say `of 2` here.
    //
    // ⚠ **THE SHEET'S OWN ARITHMETIC IS WRONG AND `08-screen-layouts.md` SAYS
    // SO IN TERMS**: *"Pager arithmetic to fix in the fixture, not to copy: the
    // sheet reads Showing 1–5 of 34 · Rows per page 50 · Page 1 of 1. At 50 per
    // page, 34 rows is Showing 1–34 of 34. The drawing shows five rows because
    // five were drawn."* This asserts the arithmetic, not the drawing.
    mountHome({ history: page([run({}), run({ id: "b" })], 34) });
    expect(homeRoot().textContent).toContain("1–34 of 34");
  });

  it("Took and Finished are dashes on a run that has not finished", () => {
    mountHome({
      history: page([run({ status: "running", finished_at: null, took_seconds: null })]),
    });
    const body = homeRoot().querySelector("tbody");
    expect((body?.textContent ?? "").includes("—")).toBe(true);
  });

  it("a duration is spelled the way the frame spells it", () => {
    mountHome({ history: page([run({ took_seconds: 64 })]) });
    expect(homeRoot().textContent).toContain("1m 04s");
  });
});

describe("B14 rules 15 and 31 — the row action, and what a clerk never reads", () => {
  it("the row action is an ICON that opens the run's result at its real address", () => {
    // Asserted as a DESTINATION that resolves, never as "there is a link".
    // `//host/…` reads as a perfectly good href to a string assertion.
    mountHome({ history: page([run({ id: "abc", runbook_key: "configuration_check" })]) });
    const link = within(homeRoot()).getAllByRole("link", { name: "View" })[0];
    expect(link.getAttribute("href")).toBe(
      `/${TENANT}/runbooks/configuration_check/runs/abc`,
    );
    // An icon, not a text link — rule 15. The accessible name carries the verb.
    expect(link.textContent).toBe("");
    expect(link.querySelector("svg")).toBeTruthy();
  });

  it("no database id and no internal code reaches the clerk", () => {
    // Read as TEXT, not as markup: rule 31's own sentence puts the internal
    // value on an attribute, so a check over the DOM string goes RED on a
    // correct fix and green on the breach.
    mountHome({
      needsYou: page([run({ status: "awaiting_approval" })]),
      history: page([run({ id: "018f-1111-2222-3333-444455556666" })]),
    });
    const text = homeRoot().textContent ?? "";
    expect(text).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/);
    expect(text).not.toContain(RUNBOOKS_HOME_SCREEN);
    expect(text).not.toContain("CR-075");
    expect(text).not.toMatch(/\bBR-[A-Z]{3}-\d{3,5}\b/);
    expect(text).not.toMatch(/\b(?:OQ|DEF|TC|US|EP|GT|RB)-(?:[A-Z]{3}-)?\d{2,5}\b/);
  });

  it("DEF-RBS-4327 — Outcome says what the run DID, never an invented verdict", () => {
    // `counts` keys are the runbook author's own English words, chosen in
    // Python. Drawing one would be an untranslated internal word in a cell.
    mountHome({ history: page([run({ status: "done", counts: { blocker: 3 } })]) });
    const text = homeRoot().textContent ?? "";
    expect(text).toContain("Done");
    expect(text, "a runbook's internal outcome word reached a cell").not.toContain("blocker");
  });
});

describe("DEF-RBS-4333 — the frame BEFORE the counts arrive", () => {
  /**
   * Mount with the two count reads NEVER SEEDED, so both are pending.
   *
   * ⚠ **THIS IS THE ONE CASE IN THE FILE THAT DOES NOT SEED ITS DATA, AND
   * THAT IS THE WHOLE POINT.** Every other case here hands the screen its
   * rows, so the screen is never rendered pending and the first paint is
   * invisible to all of them. It was invisible to the browser walkthrough
   * too — every Playwright locator auto-waits — and the defect was found by
   * opening the SCREENSHOT the walkthrough saved.
   *
   * The shape is `UnitPlanIdNeverShows.dom.test.tsx`'s, written for
   * `DEF-2412`: hold the query open, assert on the first paint, then let it
   * settle and assert again. A screen that shows a served number must be
   * asked what it draws in the frame before it has one.
   */
  it("draws no number under Waiting for you until the server has answered", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, enabled: false } },
    });
    queryClient.setQueryData(queryKeys.me, DANA);
    queryClient.setQueryData(queryKeys.myPermissions, ADMIN_PERMISSIONS);
    queryClient.setQueryData(queryKeys.shellDisplay, shellBootSeed(REGIONAL));
    queryClient.setQueryData(queryKeys.regionalSettings, REGIONAL);
    // …and DELIBERATELY no runbooks seed: both counts are pending.
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <TenantRegionalProvider
            value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}
          >
            <MemoryRouter initialEntries={[`/${TENANT}${RUNBOOKS_HOME_ROUTE}`]}>
              <RoutedApp />
            </MemoryRouter>
          </TenantRegionalProvider>
        </ToastProvider>
      </QueryClientProvider>,
    );
    const root = homeRoot();
    const values = Array.from(root.querySelectorAll(".kpi .v")).map((n) =>
      (n.textContent ?? "").trim(),
    );
    expect(
      values.filter((v) => /\d/.test(v)),
      "a KPI tile printed a DIGIT before the server answered. A `0` under " +
        '"Waiting for you" reads as "nothing is waiting for you", which is the most ' +
        "dangerous sentence this screen can print (DEF-RBS-4333).",
    ).toEqual([]);
    // …and the labels are still there, so this is a skeleton and not an
    // empty page — the difference the assertion above cannot tell on its own.
    expect(root.textContent ?? "").toContain("Runbooks");
  });

  it("and draws them the moment it has them — the same strip, settled", () => {
    mountHome({ needsYou: page([], 4), inFlight: page([], 1), history: page([run({})]) });
    const values = Array.from(homeRoot().querySelectorAll(".kpi .v")).map((n) =>
      (n.textContent ?? "").trim(),
    );
    expect(values[1]).toBe("4");
    expect(values[2]).toBe("1");
  });
});

describe("RBS-001.2 — the first visit", () => {
  it("draws the empty state, its two buttons, and NO tables", () => {
    mountHome({});
    const root = homeRoot();
    expect(within(root).getByText("Nothing has run yet")).toBeTruthy();
    expect(within(root).getByText("Start with a check. Nothing is sent.")).toBeTruthy();
    expect(within(root).getByRole("link", { name: "Run “Can we bill?” ▶" })).toBeTruthy();
    const browse = within(root).getByRole("link", { name: "Browse templates →" });
    expect(browse.getAttribute("href")).toBe(`/${TENANT}/runbooks/templates`);
    expect(root.querySelectorAll("table")).toHaveLength(0);
  });

  // ⚠ **THIS CASE ASSERTED THE BUTTON WAS HELD — *"Runs cannot start yet."*
  // — AND IS TURNED AROUND (2026-10-13, `DEF-WRK-10120`).** `POST
  // /runbooks/{key}/runs` landed on 2026-10-07 and the hold had expired; the
  // button now opens runbook 1's Check wizard, the ONE way a run starts
  // (`OQ-WRK-12792` → A). Asserted BY ADDRESS, and the refusal sentence must
  // be gone from the page — a held reason under a live button is the same lie.
  it("Run “Can we bill?” ▶ opens the Check wizard by address, and no hold sentence remains", () => {
    mountHome({});
    const root = homeRoot();
    const runNow = within(root).getByRole("link", { name: "Run “Can we bill?” ▶" });
    expect(runNow.getAttribute("href")).toBe(`/${TENANT}/runbooks/configuration_check/run`);
    expect(root.textContent ?? "").not.toContain("Runs cannot start yet.");
  });

  it("an empty PAGE of a real history is not an empty product", () => {
    // `rows.length === 0` is also true of page 7 of a 300-run history. The
    // screen asks the SERVER's totals, so a clerk paging past the end sees an
    // empty table rather than "Nothing has run yet".
    mountHome({ history: page([], 300) });
    const root = homeRoot();
    expect(root.querySelectorAll("table").length).toBeGreaterThan(0);
    expect(within(root).queryByText("Nothing has run yet")).toBeNull();
  });
});

describe("RBS-001.3 — a run in flight", () => {
  it("draws the banner, a real Watch link, and Stop held in the danger tier", () => {
    mountHome({
      inFlight: page([run({ id: "live-1", status: "running", finished_at: null, took_seconds: null })]),
      history: page([run({})]),
    });
    const root = homeRoot();
    const banner = root.querySelector("[data-in-flight]");
    expect(banner, "no in-flight banner over a running run").toBeTruthy();
    expect(banner?.textContent).toContain("Can we bill? is running");
    const watch = within(banner as HTMLElement).getByRole("link", { name: "Watch →" });
    expect(watch.getAttribute("href")).toBe(
      `/${TENANT}/runbooks/configuration_check/runs/live-1`,
    );
    const stop = within(banner as HTMLElement).getByRole("button", {
      name: "Stop",
    }) as HTMLButtonElement;
    expect(stop.disabled).toBe(true);
    expect(stop.getAttribute("title")).toBe("Stopping is not ready.");
    // B14 rule 6 — the danger tier stays where the frame puts it, so the
    // control a clerk needs is where they will look for it the day it works.
    expect(stop.className).toContain("danger");
  });

  it("DEF-RBS-4286 — no progress bar and no time estimate, because none is recorded", () => {
    // `RunResult.step_runs` is a count held in memory and never persisted; the
    // run row carries no step state. A bar at an invented percentage is worse
    // than no bar (hard-won law 1).
    mountHome({
      inFlight: page([run({ status: "running", finished_at: null, took_seconds: null })]),
      history: page([run({})]),
    });
    const text = homeRoot().textContent ?? "";
    expect(text).not.toMatch(/Step \d+ of \d+/);
    expect(text).not.toMatch(/seconds left/);
    expect(homeRoot().querySelector("progress")).toBeNull();
  });

  it("no banner when nothing is in flight", () => {
    mountHome({ history: page([run({})]) });
    expect(homeRoot().querySelector("[data-in-flight]")).toBeNull();
  });
});

describe("B14 rule 33 — the refusals a clerk reads are at most six words", () => {
  it("every hold sentence on this screen fits the cap", () => {
    for (const key of [
      "runbooks.home.hold.screen",
      "runbooks.home.hold.stop",
      "runbooks.home.kpi.notCounted",
    ]) {
      const words = t(key).trim().split(/\s+/).length;
      expect(words, `${key} is ${words} words: "${t(key)}"`).toBeLessThanOrEqual(6);
    }
  });
});

/* ── Lifecycle ─────────────────────────────────────────────
 * packet: US-RBS-003 (CR-075 wave D task D2; wireframes/RBS-001.1–.3)
 * generated: 2026-09-06 by the CR-075 wave D task D2 build lane
 * checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
 * gates: ./node_modules/.bin/vitest run src/features/runbooks/home/RunbooksHome.dom.test.tsx
 * exceptions: none
 * status: VERIFIED-UNRATIFIED
 * ────────────────────────────────────────────────────────── */
