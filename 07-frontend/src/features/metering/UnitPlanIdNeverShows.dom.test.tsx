// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-2412 (2026-09-01) — the unit screen printed the plan's raw
//          database id while the plan's NAME was still in flight.
// Rules:   B14 rule 31 (nothing internal is ever visible to a utility user —
//          "no Databse ID on screen - that is a rule", PO 2026-08-30) ·
//          BR-MET-040 (a unit's plan)
// Screens: PRM-03 (S15 unit detail — the Plan tab and the KPI strip)
// ───────────────────────────────────────────────────────
// **A TRANSIENT IS INVISIBLE TO EVERY OTHER TEST IN THIS REPO, AND THAT IS THE
// WHOLE REASON THIS FILE EXISTS.**
//
// `PlanNameAndVersion` fetches the plan by id because the unit payload carries
// `rate_plan_id` and no name. The suites that render this screen assert the
// SETTLED state — they wait for the name and then check it — so a value that
// appears for one frame and is replaced was invisible to all of them, while
// being perfectly visible to a person on a slow connection. No gate helps
// either: G28 reads source strings for internal references and this is a
// RUNTIME value, and nothing in this repo reads rendered output.
//
// So the case has to assert the FIRST paint, before the query resolves, and
// then the settled one — which is what the three cases below do.
//
// **RED PROVED FIRST**, on the pre-fix component:
//
//     AssertionError: expected '…<span>7c9e6679-7425-40de-944b-e07fc1f90ae7…'
//     not to contain '7c9e6679-7425-40de-944b-e07fc1f90ae7'
//
// and, for the error branch, the same uuid again where a sentence belongs.
//
// ⚠ **THE ID IS NOT DELETED, IT MOVES.** B14 rule 31's own words: where a
// human-facing reference does not exist, "the field says so in words and the
// internal value may ride on `title` as evidence". So these cases assert the
// uuid is absent from the TEXT a person reads and present on `title`, which is
// how somebody diagnosing keeps what they had.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import i18n from "@/i18n";

import { PlanNameAndVersion } from "./UnitDetailPage";

const TEST_TENANT = "brazosbend";
const PLAN_ID = "7c9e6679-7425-40de-944b-e07fc1f90ae7";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** A client whose plan read never settles — the in-flight frame, held open. */
function neverAnswers() {
  return createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: () => new Promise<Response>(() => undefined),
  });
}

function answers(body: unknown) {
  return createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
  });
}

function refuses() {
  return createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      new Response(JSON.stringify({ code: "not_found", message_key: "errors.not_found" }), {
        status: 404,
        headers: { "content-type": "application/json" },
      }),
  });
}

function draw(client: ReturnType<typeof answers>) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  // Mounted under the REAL route pattern (hard-won law 2's fixture clause) —
  // the plan name is a record link since 2026-10-20 and needs the tenant.
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/units/u-1`]}>
        <Routes>
          <Route
            path="/:tenant/premises/units/:unitId"
            element={<PlanNameAndVersion planId={PLAN_ID} client={client} t={t} />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("DEF-2412 · PRM-03 never shows the plan's database id", () => {
  it("while the name is in flight the block states its ABSENCE, not the id", () => {
    const { container } = draw(neverAnswers());
    expect(container.textContent ?? "").not.toContain(PLAN_ID);
    expect(screen.getByText(t("metering.units.plan.loading"))).toBeInTheDocument();
    // The evidence a support engineer needs is still one hover away.
    expect(container.querySelector(`[title="${PLAN_ID}"]`)).not.toBeNull();
  });

  it("once the plan answers, the NAME and the version render as before", async () => {
    const { container } = draw(
      answers({ id: PLAN_ID, name: "Residential Standard", version: 2, rate_schedules: [] }),
    );
    await waitFor(() => expect(screen.getByText(/Residential Standard/)).toBeInTheDocument());
    expect(container.textContent ?? "").toContain("v2");
    expect(container.textContent ?? "").not.toContain(PLAN_ID);
    // Record links (PO 2026-10-19): the name opens the plan — the id rides
    // only in the ADDRESS, never in the text.
    expect(screen.getByRole("link", { name: "Residential Standard" })).toHaveAttribute(
      "href",
      `/${TEST_TENANT}/plans-rates/plans/${PLAN_ID}`,
    );
  });

  it("a plan this role cannot read says so in words — it does not fall back to the id", async () => {
    // The old comment here read "renders the id it was given rather than a
    // blank — the id is at least traceable". Traceable to an ENGINEER; to a
    // billing clerk it is a 36-character string where a plan name belongs, and
    // B14 rule 31 was ratified after the PO read exactly that kind of value on
    // a screen.
    const { container } = draw(refuses());
    await waitFor(() =>
      expect(screen.getByText(t("metering.units.plan.unreadable"))).toBeInTheDocument(),
    );
    expect(container.textContent ?? "").not.toContain(PLAN_ID);
    expect(container.querySelector(`[title="${PLAN_ID}"]`)).not.toBeNull();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-2412 (12-governance/10-defect-log.csv) · B14 rule 31
//         (04-docs/02-decisions/14-ui-conventions.md) · US-MET-002
// screens: S15
// generated: 2026-09-01 by the customer-facing-copy lane
// gates: RED PROVED FIRST — cases 1 and 3 failed on the pre-fix component with
//        the uuid in the rendered text; the quote is in this file's header.
// exceptions: (1) this is a jsdom suite because the defect is a FRAME, and the
//     node-environment `renderToStaticMarkup` suites next door cannot hold a
//     query open or let one settle · (2) it asserts `title` carries the id,
//     which is B14 rule 31's own named exception and not an oversight
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
