// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-037 (Work → Rules) · US-WRK-051 (Settings → Labour rates) ·
//           US-WRK-026 (the dispatcher). Screens: Work-026, Work-030, Work-007
// Defects:  DEF-WRK-4119 · DEF-WRK-4119 · DEF-WRK-4121 · DEF-AST-4120
// Rules:    CLAUDE.md hard-won law 2 and its mirror clause · law 6 · law 7's
//           *looking at the wrong thing* and *incapable of failing* clauses
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY FIXTURE IN THIS FILE IS A RECORDING OF WHAT THE SERVER ACTUALLY
// SENT, AND THAT IS THE ENTIRE POINT OF THE FILE.**
//
// On 2026-09-05 `Work → Rules` and `Settings → Labour rates` both drew an empty
// table over rows the API had returned, and **every check in the repository was
// green over both**: `tsc`, eslint, 116 gates, 9,810 backend tests, 367
// front-end test files. They were green because the only description of the
// wire was a hand-written TypeScript interface, TypeScript cannot check an
// interface against a live response, and **the two screens had no rendering
// test at all** — `RulesPage.test.tsx` contains zero `render(` calls (it checks
// routes, column keys and label translation with no DOM and no server) and
// `LabourRatesPage` had no test file whatsoever.
//
// So a fixture invented in a test file could only ever have agreed with the
// bug. `__fixtures__/work-rules.recorded.json` and
// `__fixtures__/labour-rates.recorded.json` are `curl` output — captured from
// `manage.py runserver` against a freshly migrated PostgreSQL 16 seeded with
// `seed_demo` + `load_sample_data --tenant brazosbend`, signed in as the sample
// System Admin. Their top-level keys are `count/next/previous/results`. **A
// hand-written fixture would have said `rows`, and this file would have passed
// over the defect exactly as the old ones did.**
//
// ⚠ **WHAT IT COST, STATED PLAINLY BECAUSE THE ANSWER MATTERS TO THE NEXT
// LANE:** the rules recording was free — `work` is a sample-data module since
// `DEF-WRK-4085` and a fresh seed produces the drawing's seven rules, six On.
// The labour-rates recording was NOT: **nothing seeds a labour rate anywhere in
// this repository**, so the four rows were created through the real
// `POST /work/labour-rates` and then read back. That makes the fixture honest
// (it is a real reply to a real read) and leaves a gap someone must close —
// `LabourRate` has no `is_sample` column, so a sample-data block for it needs a
// migration and its own story. Until then `Work-030` cannot be walked from a
// fresh seed, which is `DEF-WRK-4119`'s escape route still standing open.
//
// ⚠ **TWO HABITS THIS FILE OBEYS, BOTH LEARNED EXPENSIVELY:**
//   · **ASSERT YOU ARRIVED.** Every case names a witness that is on the screen
//     under test and nowhere else, AND rules out `NotBuiltYet` by its own
//     marker (`data-not-built-yet`). A screen that never mounted and a screen
//     that mounted empty look identical to a `queryBy…` that returns null.
//   · **PAIR EVERY ABSENCE WITH A PRESENCE.** *"the empty state is not shown"*
//     passes just as happily over a component that never rendered. So each
//     absence assertion sits beside a count of the rows that ARE drawn.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";
import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { LabourRatesPage } from "./LabourRatesPage";
import { RulesPage } from "./RulesPage";
import { listLabourRates, listWorkRules } from "./workEndpoints";

// Lane RULES (CR-168 round 5): the CURRENT server recording, which carries the
// round-5 rule shape (`triggers`, `incomplete`, `last_fired_at`) the rebuilt
// screen reads. The older `work-rules.recorded.json` predated it and is retired.
import RECORDED_RULES from "./__fixtures__/server/work.rules.json";
import RECORDED_RATES from "./__fixtures__/labour-rates.recorded.json";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** A client that answers ONLY the recorded bodies, by path. An unrecognised
 *  path THROWS rather than returning an empty page: a fake that quietly answers
 *  `{}` to everything turns "the screen asked for the wrong address" into "the
 *  screen rendered empty", which is the very confusion under test. */
function recordingClient(routes: Record<string, unknown>): ApiClient {
  const reply = async (path: string): Promise<ApiResponse<unknown>> => {
    const key = Object.keys(routes).find((candidate) => path.includes(candidate));
    if (key === undefined) {
      throw new Error(`no recording for ${path}`);
    }
    return { status: 200, data: routes[key], etag: null, notModified: false };
  };
  const write = async () => ({ status: 200, data: {}, etag: null, notModified: false });
  return {
    get: reply,
    post: write,
    put: write,
    patch: write,
    delete: write,
  } as unknown as ApiClient;
}

function mountAt(path: string, pattern: string, element: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        {/* ⚠ MOUNTED UNDER THE REAL PATH PATTERN, never bare. A component with
            no matching route has `useParams().tenant` undefined and every
            address it builds comes out `//…` — a protocol-relative URL to
            another host that reads as a perfectly good string to `toContain`
            (`DEF-CWP-3925`). */}
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path={pattern} element={element} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The two things that must be true before ANY other assertion means anything:
 *  we are on the screen we think we are, and it is not the placeholder.
 *
 *  ⚠ **THE WITNESS IS THE HEADING, BY ROLE.** A bare `getByText("Rules")`
 *  matches the tab strip's own word as well as the `<h1>`, so it throws
 *  *"found multiple elements"* on the very screen it is meant to confirm — a
 *  check that cannot distinguish arrival from ambiguity. */
async function assertArrived(witness: string) {
  expect(await screen.findByRole("heading", { name: witness })).toBeTruthy();
  expect(document.querySelector("[data-not-built-yet]")).toBeNull();
  expect(screen.queryByText(t("shell.notBuilt.title"))).toBeNull();
}

afterEach(cleanup);

describe("DEF-WRK-4119 — the recorded reply is the envelope, not the selector's dict", () => {
  it("the server's own answer has count/results and NO `rows` key", () => {
    // The fixture is a recording, so this case is a statement about the
    // PRODUCT rather than about the test: if the wire ever grows a `rows` key
    // this goes red and the two screens below are re-examined.
    expect(Object.keys(RECORDED_RULES).sort()).toEqual([
      "count",
      "next",
      "previous",
      "results",
    ]);
    expect(Object.keys(RECORDED_RATES).sort()).toEqual([
      "count",
      "next",
      "previous",
      "results",
    ]);
    expect((RECORDED_RULES as Record<string, unknown>).rows).toBeUndefined();
    expect((RECORDED_RATES as Record<string, unknown>).rows).toBeUndefined();
  });

  it("the wrappers read it — seven rules and four rates, not zero", async () => {
    const rules = await listWorkRules({}, recordingClient({ "/work/rules": RECORDED_RULES }));
    const rates = await listLabourRates(
      {},
      recordingClient({ "/work/labour-rates": RECORDED_RATES }),
    );
    expect(rules.rows).toHaveLength(7);
    expect(rules.total).toBe(7);
    expect(rates.rows).toHaveLength(4);
    expect(rates.total).toBe(4);
  });
});

describe("DEF-WRK-4119 — Work → Rules draws the seven rules a supervisor created", () => {
  it("lists every rule, and does NOT draw the empty state over them", async () => {
    mountAt(
      `/${TENANT}/work/rules`,
      "/:tenant/work/rules",
      <RulesPage client={recordingClient({ "/work/rules": RECORDED_RULES })} />,
    );

    await (assertArrived(t("work.rules.title")));

    // THE POSITIVE, FIRST. Every rule the server sent is on the page by name.
    const names = (RECORDED_RULES as { results: { name: string }[] }).results.map((r) => r.name);
    expect(names).toHaveLength(7);
    // `findByText` on the FIRST row: the table paints when the query resolves,
    // and a synchronous `getByText` here would be asserting about the render
    // BEFORE the fetch — which fails on a working screen and would have been
    // "fixed" by deleting the assertion.
    expect(await screen.findByText(names[0])).toBeTruthy();
    for (const name of names.slice(1)) {
      expect(screen.getByText(name)).toBeTruthy();
    }

    // ⚠ AND ONLY THEN THE ABSENCE. On its own this assertion passes over a
    // component that never rendered at all, which is how a check on wave L
    // passed over a page that had never loaded.
    expect(screen.queryByText(t("work.rules.empty.title"))).toBeNull();
    expect(screen.queryByText(t("work.rules.empty.helper"))).toBeNull();
  });

  it("the consequence box counts the SIX that are on — the sentence the supervisor reads", async () => {
    mountAt(
      `/${TENANT}/work/rules`,
      "/:tenant/work/rules",
      <RulesPage client={recordingClient({ "/work/rules": RECORDED_RULES })} />,
    );
    await (assertArrived(t("work.rules.title")));

    const on = (RECORDED_RULES as { results: { enabled: boolean }[] }).results.filter(
      (r) => r.enabled,
    ).length;
    // The recording is the drawing's fixture: seven rules, six On.
    expect(on).toBe(6);

    // Wait for the rows before reading the sentence — the count is computed
    // FROM them, so an early read would see the pre-fetch zero and pass over
    // exactly the defect under test.
    await screen.findByText("Asset age rule");
    const box = document.querySelector("[data-consequence='work-rules']");
    expect(box).not.toBeNull();
    // ⚠ THE WHOLE DEFECT IN ONE ASSERTION. It read `0 rules run tonight…` over
    // six that were on, because `rows` was undefined so `onCount` was 0.
    expect(within(box as HTMLElement).getByText(/6 rules run tonight/)).toBeTruthy();
    expect(within(box as HTMLElement).queryByText(/^0 rules run tonight/)).toBeNull();
  });
});

describe("DEF-WRK-4119 — Settings → Labour rates draws the four rates", () => {
  it("lists every rate by its role label, and not the empty state", async () => {
    mountAt(
      `/${TENANT}/settings/labour-rates`,
      "/:tenant/settings/labour-rates",
      <LabourRatesPage client={recordingClient({ "/work/labour-rates": RECORDED_RATES })} />,
    );

    await (assertArrived(t("work.labourRates.title")));

    const labels = (RECORDED_RATES as { results: { role_label: string }[] }).results.map(
      (r) => r.role_label,
    );
    expect(labels).toHaveLength(4);
    expect(await screen.findByText(labels[0])).toBeTruthy();
    for (const label of labels.slice(1)) {
      expect(screen.getByText(label)).toBeTruthy();
    }

    expect(screen.queryByText(t("work.labourRates.empty.title"))).toBeNull();
    expect(screen.queryByText(t("work.labourRates.empty.helper"))).toBeNull();
  });

  it("the contractor's overtime is a DASH and never a zero (BR-WRK-020)", async () => {
    mountAt(
      `/${TENANT}/settings/labour-rates`,
      "/:tenant/settings/labour-rates",
      <LabourRatesPage client={recordingClient({ "/work/labour-rates": RECORDED_RATES })} />,
    );
    await (assertArrived(t("work.labourRates.title")));

    // The recording carries exactly one row with null overtime — the agency
    // that invoices its own. Rendering `0.0000` there would state that their
    // overtime is free, so the screen must show neither that nor a blank.
    const nulls = (RECORDED_RATES as { results: { overtime_hourly: string | null }[] }).results
      .filter((r) => r.overtime_hourly === null);
    expect(nulls).toHaveLength(1);
    // …and the rates that DO have overtime are drawn, so the line below is not
    // passing merely because nothing rendered.
    expect(await screen.findByText("72.7500")).toBeTruthy();
    expect(screen.queryByText("0.0000")).toBeNull();
  });
});

describe("DEF-WRK-4096 — FIXED by lane SRV-4 (2.512.0): every count is a fact; only an incomplete trigger is a dash", () => {
  // ⚠ **SUPERSEDED CASE, REWRITTEN BY LANE RULES (CR-168 round 5).** These two
  // cases asserted `ruleCanRaise`: four of five sources drew a DASH in THIS
  // MONTH because the raise stamped a module name the order table refused.
  // SRV-4 fixed the stamp, so the predicate — and the dash it drew over a
  // working rule — would now be the lie. What still cannot raise is a trigger
  // missing a setting its process requires (`incomplete`, `DEF-WRK-4097`): the
  // recorded *Leak investigation* has no service and no unit.

  it("the recording carries one rule that cannot raise (incomplete) and six that can", () => {
    const rules = (RECORDED_RULES as { results: { name: string; incomplete: unknown[] }[] }).results;
    const incomplete = rules.filter((r) => r.incomplete.length > 0).map((r) => r.name);
    expect(incomplete).toEqual(["Leak investigation"]);
    expect(rules.length - incomplete.length).toBe(6);
  });

  it("draws THIS MONTH as a count for a rule that can raise and a dash for the incomplete one", async () => {
    mountAt(
      `/${TENANT}/work/rules`,
      "/:tenant/work/rules",
      <RulesPage client={recordingClient({ "/work/rules": RECORDED_RULES })} />,
    );
    await assertArrived(t("work.rules.title"));
    const leak = (await screen.findByText("Leak investigation")).closest("tr") as HTMLElement;
    const asset = screen.getByText("Asset age rule").closest("tr") as HTMLElement;
    const monthIndex = Array.from(document.querySelectorAll("thead th")).findIndex(
      (th) => th.textContent?.trim() === t("work.rules.col.thisMonth"),
    );
    expect(monthIndex).toBeGreaterThanOrEqual(0);
    expect(leak.querySelectorAll("td")[monthIndex]?.textContent?.trim()).toBe("—");
    // The fact the dash was hiding before SRV-4: this rule raised three.
    expect(asset.querySelectorAll("td")[monthIndex]?.textContent?.trim()).toBe("3");
  });
});
