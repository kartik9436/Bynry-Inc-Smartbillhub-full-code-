// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CUS-5480 (the grid clipped after six rows and took the wizard
//          footer with it) · DEF-CUS-5481 (the work-order cell was plain text
//          and the install date drew its own label on all fourteen rows) ·
//          DEF-SHL-5477 (DatePickerField's `labelHidden`)
// Process: 12-governance/22-product-maintenance-process.md §4 — *"write the
//          test that would have caught it"*
// Rules:   B14 rule 31 (no database id is ever the visible value of a field) ·
//          rule 32 (a stated absence) · rule 33 (a label is ≤ 3 words) ·
//          hard-won law 2 (built is not wired) · law 6 (no gate reads
//          rendered output) · law 7 (know what would make this pass wrongly)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS FILE CAN AND CANNOT SEE — READ THIS BEFORE TRUSTING IT GREEN
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS HARNESS DOES NO LAYOUT. EVERY ELEMENT HERE IS ZERO BY ZERO**, so it
// can never see a clipped table, a row out of alignment or a footer off the
// page — which is exactly why all three defects above shipped green. Counting
// cells in the DOM is what MISSED them: the grid had all fourteen rows either
// way.
//
// So each case below asserts the **MECHANISM** rather than the symptom, and
// says which mechanism:
//
//   * a column the clerk decides is a `<select>`, not a word — source-checkable
//     and the thing `DEF-CUS-5481` says nothing asserted;
//   * a field inside a cell announces its label and does not draw it;
//   * a hidden label sits in a **positioned** wrapper, which is the whole of
//     `DEF-CUS-5480`: an `sr-only` box is `position: absolute`, and one with no
//     positioned ancestor escapes the screen's scroller and enlarges the
//     DOCUMENT instead.
//
// **The rendered proof is a browser and there is no substitute:**
// `10-scripts/def_cus_5480_step4_grid_walkthrough.mjs` measures the document
// against the viewport, scrolls to the last row and presses Continue. This file
// is the cheap half that runs on every commit; that one is the half that can
// actually see the defect.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18next from "i18next";

import "@/i18n";

import { createApiClient } from "@/api/client";
import type { TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import type { ProposedWorkOrder } from "@/features/work/workEndpoints";

import { emptyDraft } from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";
import type { DraftUnit } from "./newConnectShared";
import { ServicesStep, workOrderOptions } from "./NewConnectServicesStep";

const TEST_TENANT = "brazosbend";

/** Two jobs, two services — what `GET /connections/proposed-work-orders` hands
 *  step 4 on the electric-and-water build the PO reported from. */
function proposedOrder(over: Partial<ProposedWorkOrder>): ProposedWorkOrder {
  return {
    template_id: "00000000-0000-0000-0000-000000000000",
    template_no: null,
    name: "Service drop",
    service: { id: "svc", code: "electric", name: "Electric" },
    scope: "per_premise",
    sequence: 1,
    job_type: null,
    is_gate: false,
    version: 1,
    est_duration_minutes: null,
    ...over,
  };
}
const DROP = proposedOrder({ template_id: "tpl-drop", name: "Service drop" });
const MARK_OUT = proposedOrder({
  template_id: "tpl-markout",
  name: "Site inspection & mark-out",
  service: { id: "svc-w", code: "water", name: "Water" },
  sequence: 2,
});
const PROPOSED: ProposedWorkOrder[] = [DROP, MARK_OUT];

/** Six dwellings and the common area, on electric and water: the build in
 *  `DEF-CUS-5480`, which is fourteen grid rows. */
const UNITS: DraftUnit[] = [
  ...[1, 2, 3, 4, 5, 6].map((n) => ({ label: `Apt ${n}`, isCommonArea: false })),
  { label: "Common area", isCommonArea: true },
];

function sixUnitDraft(over: Partial<NewConnectDraft> = {}): NewConnectDraft {
  return { ...emptyDraft(), premiseServices: ["electric", "water"], ...over };
}

/**
 * **THE ELEVEN PLATFORM SERVICES AS `GET /settings/services` ANSWERS THEM** —
 * every row, `enabled` where this tenant sells it. The demo utility the PO
 * reported from has **electric and water on, and nine off**.
 *
 * ⚠ **THE ORDER IS THE PLATFORM'S SEED ORDER AND `fire` IS ELEVENTH**
 * (`CR-063`, `BR-RAT-024`), so the case that enables `fire` proves the eleventh
 * service reaches the screen with nothing in the product naming it.
 */
const PLATFORM_SERVICES = [
  "electric",
  "water",
  "gas",
  "sewer",
  "trash",
  "storm_water",
  "solar",
  "broadband",
  "thermal_heat",
  "battery",
  "fire",
] as const;

function tenantServices(enabled: readonly string[]): TenantServiceRow[] {
  return PLATFORM_SERVICES.map((service) => ({
    service: service as string,
    name: service as string,
    enabled: enabled.includes(service),
    // The rest of the served row. Present because the TYPE requires them and
    // a partial cast would let a real field quietly go missing from the
    // fixture — which is the shape this whole describe block is about.
    primary_uom: null,
    alt_uom: null,
    billed_uom: null,
    conversion_factor: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: null,
    active_accounts: null,
  }));
}

/** Every `id` of a rendered tick, in the order drawn. */
function tickedServices(html: string): string[] {
  return [...html.matchAll(/id="nc_premise_services_([a-z_]+)"/g)].map((hit) => hit[1]);
}

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/...` PATTERN** (hard-won law 2): a bare
 * `MemoryRouter` with no matching route leaves `useParams().tenant` undefined
 * and every address the screen builds comes out protocol-relative — a string
 * that reads as perfectly good to `toContain`.
 */
function renderGrid(
  draft: NewConnectDraft = sixUnitDraft(),
  /** Left out, the tenant-services read stays PENDING — which is what a bare
   *  mount does, and what the loading case below asserts. `[]` is a SUCCESSFUL
   *  read of a tenant that sells nothing, which is a different answer from a
   *  read that failed; see `prepared` below. */
  services?: TenantServiceRow[],
  /** A cache already in some state — how the FAILED case is built, because a
   *  read only reaches its error state by actually being refused, and
   *  `renderToStaticMarkup` is synchronous so a rejection inside the render
   *  would never land. `prefetchQuery` swallows the refusal and leaves the
   *  query in error, which is the state a clerk would be looking at. */
  prepared?: QueryClient,
): string {
  const queryClient = prepared ?? new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (services !== undefined) {
    queryClient.setQueryData(queryKeys.tenantServices, services);
  }
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      new Response(JSON.stringify({ count: 0, results: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new?step=4`]}>
          <Routes>
            <Route
              path="/:tenant/connections/new"
              element={
                <ServicesStep
                  draft={draft}
                  breaches={[]}
                  sewerGaps={[]}
                  units={UNITS}
                  proposed={PROPOSED}
                  client={client}
                  onPatch={() => undefined}
                  t={(key, options) => String(i18next.t(key, options))}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("New Connect step 4 · the grid's cells", () => {
  // ════════════════════════════════════════════════════════════════════════
  // DEF-CUS-5481 (1) · THE WORK ORDER COLUMN IS A CONTROL
  // ════════════════════════════════════════════════════════════════════════

  it("every work-order cell is a SELECT the clerk can change, not a word", () => {
    // ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, and it is why the assertion is
    // shaped this way (law 7):** the old cell held the RIGHT NAME — `Service
    // drop` on the electric rows, `Site inspection & mark-out` on the water
    // ones — so every assertion that reads the VALUE passed over a cell that
    // happened not to be editable. A read-only cell and a defaulted dropdown
    // are indistinguishable by text. So this asserts the ELEMENT.
    const html = renderGrid();
    const selects = html.match(/<select id="nc_workorder_[^"]*"/g) ?? [];
    expect(selects).toHaveLength(14); // 7 units x 2 services
  });

  it("a work-order cell offers EVERY proposed job, so one unit can take a different one", () => {
    // PO, 2026-09-16: *"work order is drop down - you can give default values
    // ot it - but you need to allow user to select it"*. A dropdown holding
    // only the job the row already has is the read-only cell wearing a chevron.
    expect(workOrderOptions(PROPOSED).map((o) => o.label)).toEqual([
      "Service drop",
      "Site inspection & mark-out",
    ]);
    // One template proposed for two services is ONE option, not two identical
    // words a clerk has to choose between.
    expect(
      workOrderOptions([DROP, { ...DROP, service: MARK_OUT.service }]),
    ).toHaveLength(1);
  });

  it("the cell arrives on the job that fits its service, and still offers the others", () => {
    const html = renderGrid();
    // The electric row's select opens on the service drop...
    expect(html).toContain('<option value="tpl-drop" selected="">Service drop</option>');
    // ...and the mark-out is on the same select, unselected.
    expect(html).toContain('<option value="tpl-markout">Site inspection &amp; mark-out</option>');
  });

  it("B14 rule 31 — the template id is the option VALUE and never a word on screen", () => {
    const html = renderGrid();
    // The id appears only inside a value attribute; it is never rendered text.
    expect(html).not.toMatch(/>[^<]*tpl-drop[^<]*</);
    expect(html).toContain("Service drop");
  });

  // ════════════════════════════════════════════════════════════════════════
  // DEF-CUS-5481 (2) / DEF-SHL-5477 · THE COLUMN HEADER IS THE FIELD'S LABEL
  // ════════════════════════════════════════════════════════════════════════

  it("no cell draws its own label — the column header is the label, once", () => {
    const html = renderGrid();
    // ⚠ Fourteen rows each drew a label above their input, repeating the header
    // and making that one cell taller than its neighbours, so the row no longer
    // lined up. The words survive — announced, not drawn — so the count is of
    // VISIBLE ones, which is every label that is not `sr-only`.
    // ⚠ **THE COLUMN THIS CASE WAS WRITTEN ABOUT IS GONE (`DEF-CUS-6101`,
    // 2026-09-21).** It asked for a planned install date per unit-service —
    // fourteen here, sixteen on the walk's seven-unit block — and
    // `commitPlanOf` sent NONE of them. A field that will not keep what you
    // type is worse than no field, so the column was removed rather than
    // wired; where a per-row planned date should live is `OQ-MET-12571`, OPEN.
    // **The SHAPE this case exists for is unchanged and is now asserted over
    // the work-order column**, which is the cell `DEF-CUS-5481` named beside
    // the date one.
    const drawn = (
      html.match(/<label(?![^>]*class="sr-only")[^>]*>Work order<\/label>/g) ?? []
    ).length;
    expect(drawn).toBe(0);
    // Announced on every row, so a screen reader still hears it.
    const announced = (html.match(/<label for="nc_workorder_[^"]*" class="sr-only">/g) ?? [])
      .length;
    expect(announced).toBe(14);
    // And drawn ONCE, as the column header it belongs to.
    expect((html.match(/<th>Work order<\/th>/g) ?? [])).toHaveLength(1);
  });

  it("DEF-CUS-6101 — step 4 asks for NO per-unit install date at all", () => {
    // ⚠ **THE ASSERTION IS THE ABSENCE OF A CONTROL, NOT OF A WORD.** The
    // column collected sixteen dates on a seven-unit block and the commit
    // payload carried none of them: hard-won law 2's plainest form, and `G13`
    // cannot see it — it is not an unpassed prop, it is a field that writes to
    // the draft correctly and is never read back out.
    const html = renderGrid();
    expect(html).not.toContain('id="nc_install_');
    expect(html).not.toContain("Planned installation date");
    // And the sentence that stood under the grid excusing it goes with it. A
    // stated absence that outlives its cause is a lie the product tells about
    // itself (hard-won law 1), and *"Per-unit dates are not stored yet"* was
    // RATIONALE on screen besides — B14 rule 33 puts that at zero words.
    expect(html).not.toContain("not stored yet");
  });

  // ════════════════════════════════════════════════════════════════════════
  // DEF-CUS-5480 · A HIDDEN LABEL MUST NOT ESCAPE THE SCREEN'S SCROLLER
  // ════════════════════════════════════════════════════════════════════════

  it("every hidden label sits in a POSITIONED wrapper, so it cannot enlarge the document", () => {
    // ⚠ **THIS IS THE MECHANISM, NOT THE SYMPTOM, AND THE DIFFERENCE MATTERS.**
    // `sr-only` is `position: absolute`. An absolutely positioned box is clipped
    // by an ancestor's `overflow` ONLY when that ancestor is also its containing
    // block, so a hidden label with no positioned ancestor escapes the screen's
    // scroller and grows the DOCUMENT instead. Measured on the running product:
    // forty of them on this grid put `documentElement.scrollHeight` at 1,782
    // against a 1,000px viewport — a second scrollbar that scrolled 782px into
    // empty grey, taking the panel border and the Back/Continue footer with it.
    //
    // ⚠ **THIS ASSERTION CANNOT SEE THAT.** It reads a class name; nothing here
    // computes a style or a box. It goes red on the code that shipped the defect
    // and it is a proxy. The measurement lives in
    // `10-scripts/def_cus_5480_step4_grid_walkthrough.mjs`.
    const html = renderGrid();
    const hidden = (html.match(/<label [^>]*class="sr-only"/g) ?? []).length;
    // ⚠ **FORTY UNTIL 2026-09-21, AND TWENTY-SIX SINCE (`DEF-CUS-6101`).** It
    // was fourteen install dates, fourteen work orders and twelve occupancies
    // — the common area has none, because occupancy is a dwelling's fact. The
    // install-date column is REMOVED: it collected sixteen dates on the walk's
    // seven-unit block and the commit sent none of them. Fourteen fewer hidden
    // labels is fourteen fewer boxes that could escape the scroller, so the
    // defect this case guards is smaller, not differently shaped.
    expect(hidden).toBe(26);
    // Each hidden label's own wrapper is the positioned one.
    const wrapped = (html.match(/<div class="relative"><label [^>]*class="sr-only"/g) ?? [])
      .length;
    expect(wrapped).toBe(hidden);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE AVAILABILITY TICK LIST — PO ruling 2026-09-21
// ══════════════════════════════════════════════════════════════════════════
//
// PO, verbatim: *"here filter only active Utility services for that Tenant"*.
//
// ⚠ **NOTHING TESTED THIS LIST AT ALL BEFORE TODAY.** Six cases in this file
// and every one of them reads the GRID below it; the tick list that decides
// which services the grid even has was asserted by nobody, in a file whose own
// header is about checks that do not check. That is why the hand-typed
// `TEN_SERVICES` could offer nine services the commit refuses by name and stay
// green for as long as it did.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY.** A `toContain` over one tick's id
// passes on a screen offering all eleven, so every case here asserts the WHOLE
// SET by equality, in order — and the loading case pins the shape first,
// because a mount whose query never resolves renders no ticks at all and would
// make an "offers only two" assertion pass for entirely the wrong reason.
describe("New Connect step 4 · only the services this utility sells", () => {
  it("offers the tenant's ENABLED services and not the platform's eleven", () => {
    const html = renderGrid(sixUnitDraft(), tenantServices(["electric", "water"]));
    expect(tickedServices(html)).toEqual(["electric", "water"]);
    // ABSENT BY NAME — the nine the demo utility does not sell. Each of these
    // was a live tick box that the commit refuses with *"gas isn't one of the
    // services this utility bills"*, after all eight steps.
    for (const off of ["gas", "sewer", "trash", "storm_water", "solar", "broadband", "fire"]) {
      expect(html).not.toContain(`id="nc_premise_services_${off}"`);
    }
  });

  it("counts against what the TENANT sells, never against eleven", () => {
    const html = renderGrid(sixUnitDraft(), tenantServices(["electric", "water"]));
    // The drawn line is *"{{count}} of {{total}} available at this address"*.
    // `total` was `TEN_SERVICES.length` — the platform's eleven — on a utility
    // that sells two, so the sentence itself was false.
    expect(html).toContain("2 of 2 available at this address");
    expect(html).not.toContain("of 11 available");
  });

  it("offers the ELEVENTH service the day a tenant enables it, naming nothing", () => {
    // ⚠ **THIS IS THE CASE hard-won law 2 EXISTS FOR.** *"an eleventh service
    // does NOT appear on screen on its own and it fails SILENTLY"* — the row
    // exists, the API serves it, `tsc` and every test pass, and the screen
    // never offers it. Nothing in `NewConnectServicesStep.tsx` names `fire`;
    // enabling it on the tenant is the whole change.
    const html = renderGrid(sixUnitDraft(), tenantServices(["electric", "water", "fire"]));
    expect(tickedServices(html)).toEqual(["electric", "water", "fire"]);
  });

  it("keeps the platform's seed order, and never re-sorts it", () => {
    // `GET /settings/services` answers in seed order and every screen in the
    // product lists services that way. A sort here would be a second order.
    const html = renderGrid(sixUnitDraft(), tenantServices(["fire", "gas", "electric"]));
    expect(tickedServices(html)).toEqual(["electric", "gas", "fire"]);
  });

  it("says it is READING rather than drawing an empty list", () => {
    // ⚠ **AN EMPTY TICK LIST IS A TRUE ANSWER ONLY WHEN THE READ SUCCEEDED.**
    // While it is in flight the same empty list says *"this utility sells
    // nothing"*, which is a different claim and a wrong one.
    const html = renderGrid();
    expect(html).toContain("data-services-loading");
    expect(tickedServices(html)).toEqual([]);
    expect(html).not.toContain("available at this address");
  });

  it("says the read FAILED rather than drawing an empty list", async () => {
    // ⚠ **`retryOnMount: false` IS LOAD-BEARING AND IS NOT A TEST TRICK.** With
    // React Query's default, an observer mounting over an errored query starts
    // a fresh fetch and the frame reads PENDING again — so the refusal would
    // have been asserted over a loading state, and the case would have failed
    // for a reason that has nothing to do with the screen. Turning it off is
    // how the test looks at the state a clerk is actually left in.
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, retryOnMount: false } },
    });
    await queryClient.prefetchQuery({
      queryKey: queryKeys.tenantServices,
      queryFn: () => Promise.reject(new Error("settings/services refused")),
      retry: false,
    });
    const html = renderGrid(sixUnitDraft(), undefined, queryClient);
    expect(html).toContain("data-services-failed");
    expect(html).toContain("The services did not load.");
    expect(tickedServices(html)).toEqual([]);
    // The count sentence must NOT appear — *"0 of 0"* over a failed read is a
    // claim about the utility made out of a network error.
    expect(html).not.toContain("available at this address");
  });

  it("a tenant that really sells nothing gets `0 of 0`, which is a different answer", () => {
    // ⚠ **`[]` AND A FAILURE ARE TWO ANSWERS AND ONLY ONE IS ABOUT THE
    // UTILITY.** A successful read of an empty set is *this tenant has enabled
    // no services yet* — worth saying plainly — and the case above is *we do
    // not know*. Drawing the same empty list for both is the shape
    // `ServicesAvailableField` already records for `null` against `[]`.
    const html = renderGrid(sixUnitDraft({ premiseServices: [] }), []);
    expect(html).not.toContain("data-services-failed");
    expect(html).toContain("0 of 0 available at this address");
    expect(tickedServices(html)).toEqual([]);
  });
});
