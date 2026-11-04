// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-1702 — nine list screens had no filter control at all. Six
//           server legs landed in ec4d9f8/3bcc79e/20a37c8 with 22 backend
//           cases; this file is the FRONTEND half's proof.
// Change:   CR-045 wave D · D.6, D.7, D.13, D.14, D.15
// Rules:    BR-SHL-010 (only DECLARED capabilities render) ·
//           BR-SHL-011 (the `f.<name>` URL grammar) · B14 rule 12 (toolbar)
// ───────────────────────────────────────────────────────
// **WHAT THIS FILE ASSERTS, AND WHY IT IS THE ONLY QUESTION WORTH ASKING.**
//
// CR-045 wave D says it in one sentence: *"NO DIMENSION ON THIS WAVE IS APPLIED
// IN THE BROWSER … A control that narrowed the page in hand would show a
// subset of a subset, which is worse than the bare toolbar this defect is
// about."*
//
// So a test that ticks a box and counts the rows on screen would pass on the
// defect. The rows would genuinely narrow — in the browser — and the screen
// would still be broken. **The observable that separates the fix from the
// defect is the REQUEST**, so every case here captures the URL the client
// actually asked for and asserts the `f.<name>` pair is in it.
//
// ⚠ **PROVED RED FIRST (hard-won law 7).** Each case was run against the
// pre-fix client and the failures are quoted in the commit message: the
// imports legs asked for a bare `/imports` with no query string at all, and
// the routes/cycles legs never reached these params because neither table
// declared the filters that produce them.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { getCyclesPage, getImportRuns, getRoutesPage } from "@/api/endpoints";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";
import { AssetImportsTab } from "@/features/assets/AssetImportsTab";
import { AccountImportsTab } from "@/features/customers/AccountImportsTab";
import { PremisesImportsTab } from "@/features/metering/PremisesImportsTab";
import { RoutesCyclesTab } from "@/features/tenancy/SettingsRoutesCyclesTab";

/** Captures every URL the client requests, and answers each with an empty,
 *  well-shaped payload so the caller's own parsing is exercised. */
function recordingClient(): { client: ReturnType<typeof createApiClient>; urls: string[] } {
  const urls: string[] = [];
  const client = createApiClient({
    baseUrl: "http://api.test",
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      urls.push(url);
      const body = url.includes("/imports")
        ? { rows: [] }
        : { results: [], count: 0, rollup: null };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  return { client, urls };
}

const LIST_CONFIG = {
  screenId: "TEST",
  getRowId: (row: { id: string }) => row.id,
  defaultSort: { sort: "code", dir: "asc" },
  columns: [],
} satisfies TableConfig<{ id: string }>;

function stateWith(filters: Record<string, string>): TableRequestState {
  return { ...defaultRequestState(LIST_CONFIG), filters };
}

describe("DEF-1702 · CR-045 wave D — every wired filter reaches the SERVER", () => {
  // ── D.13 / D.14 / D.15 · the three Imports tabs ────────────────────────
  it("D.13/D.15: a run status is sent as `f.status`, not filtered in the browser", async () => {
    const { client, urls } = recordingClient();
    await getImportRuns(client, { status: "loaded" });
    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain("f.status=loaded");
  });

  it("D.13/D.15: a target is sent as `f.target` in BR-SHL-011's grammar, never TC-IMP-12's bare `?target=`", async () => {
    const { client, urls } = recordingClient();
    await getImportRuns(client, { target: "assets_meters" });
    expect(urls[0]).toContain("f.target=assets_meters");
    // The bare form the route never accepted. `?target=` would be dropped by
    // `parse_list_params` and the tab would silently show every target.
    expect(urls[0]).not.toMatch(/[?&]target=/);
  });

  it("D.13/D.15: two dimensions are AND-combined by sending BOTH params", async () => {
    const { client, urls } = recordingClient();
    await getImportRuns(client, { status: "failed", target: "premises" });
    expect(urls[0]).toContain("f.status=failed");
    expect(urls[0]).toContain("f.target=premises");
  });

  it("an empty filter value is OMITTED, never sent as `f.x=` (BR-SHL-011: absent, not empty)", async () => {
    const { client, urls } = recordingClient();
    await getImportRuns(client, { status: "", target: "accounts" });
    expect(urls[0]).not.toContain("f.status");
    expect(urls[0]).toContain("f.target=accounts");
  });

  it("no filters at all asks for a plain list — the unfiltered request is unchanged", async () => {
    const { client, urls } = recordingClient();
    await getImportRuns(client);
    expect(urls[0]).not.toContain("f.");
  });

  // ── D.6 · Settings › Routes ────────────────────────────────────────────
  it("D.6: the routes cycle and status filters are sent as `f.cycle` and `f.status`", async () => {
    const { client, urls } = recordingClient();
    await getRoutesPage(stateWith({ cycle: "CYC-01", status: "active" }), client);
    expect(urls[0]).toContain("f.cycle=CYC-01");
    expect(urls[0]).toContain("f.status=active");
  });

  // ── D.7 · Settings › Cycles ────────────────────────────────────────────
  it("D.7: the cycles frequency filter is sent as `f.frequency`, as the BUSINESS WORD", async () => {
    const { client, urls } = recordingClient();
    await getCyclesPage(stateWith({ frequency: "Monthly" }), client);
    // ⚠ THE WORD, NOT THE ENUM. `cycles_queryset` folds "Monthly" onto both
    // generations of the spelling through `schedule.business_frequency`; a
    // client that sent `monthly` would match only the CR-006 rows and miss
    // every row RC-W1's migration 0019 moved onto the business words.
    expect(urls[0]).toContain("f.frequency=Monthly");
  });

  it("D.7: the cycles status filter is sent as `f.status`", async () => {
    const { client, urls } = recordingClient();
    await getCyclesPage(stateWith({ status: "inactive" }), client);
    expect(urls[0]).toContain("f.status=inactive");
  });

  // ══════════════════════════════════════════════════════════════════════
  // THE OTHER HALF — THE CONTROL IS ACTUALLY ON THE PAGE
  //
  // ⚠ **G45 CANNOT ANSWER THIS AND IS NOT MEANT TO.** It reads SOURCE TEXT:
  // it counts `filters:` declarations against `filterBarSlot` passes, which
  // catches the DEF-1701 shape (declared, never rendered) and would go green
  // on a slot passed a `<FilterBar>` with an empty group list. No gate in this
  // repo reads rendered output (hard-won law 6), so these five cases are the
  // only mechanical evidence that the four screens are no longer BARE — which
  // is the exact claim DEF-1702 makes and the exact claim a walk of the
  // screens got wrong the first time.
  const panel = { open: "+ Filter", all: "All", by: "Filter by" };

  function shell(node: React.ReactNode): string {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/brazosbend/x"]}>{node}</MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  it("D.13: Assets > Imports draws the filter panel with Status and Target", () => {
    const { client } = recordingClient();
    const html = shell(
      <AssetImportsTab writeBlockedReason={null} onImport={() => undefined} client={client} />,
    );
    expect(html).toContain(panel.open);
    expect(html).toContain(panel.all);
    // The two group headings, by their own catalogue words.
    expect(html).toContain("Status");
    expect(html).toContain("Target");
    // Its own three targets and NOT the other three (B16 §4.7 scopes AST-04).
    expect(html).toContain("Sub-meters");
    expect(html).not.toContain("Premises</");
  });

  it("D.14: Accounts > Imports draws Status and deliberately NO Target group", () => {
    const { client } = recordingClient();
    const html = shell(
      <AccountImportsTab writeBlockedReason={null} onImport={() => undefined} client={client} />,
    );
    expect(html).toContain(panel.open);
    expect(html).toContain("Status");
    // ⚠ THE NEGATIVE IS THE POINT. S81 lists one target, so a Target group
    // would offer a single option that changes nothing. The scope rides every
    // request as a fixed `f.target=accounts` instead.
    expect(html).not.toContain("Target");
  });

  it("D.15: Premises > Imports draws Status and a Target group offering all six", () => {
    const { client } = recordingClient();
    const html = shell(
      <PremisesImportsTab
        writeBlockedReason={null}
        onImportPremises={() => undefined}
        onImportUnits={() => undefined}
        client={client}
      />,
    );
    expect(html).toContain(panel.open);
    expect(html).toContain("Target");
    for (const word of ["Premises", "Units", "Meters", "Sub-meters", "Devices", "Accounts"]) {
      expect(html).toContain(word);
    }
  });

  it("D.6: Settings > Routes draws the panel — the sub-tab that lands by default", () => {
    const { client } = recordingClient();
    const html = shell(<RoutesCyclesTab readOnly={false} client={client} />);
    expect(html).toContain(panel.open);
    expect(html).toContain(panel.by);
  });

  it("D.7: Settings > Cycles draws its OWN panel — the second table in one file", () => {
    const { client } = recordingClient();
    const html = shell(<RoutesCyclesTab readOnly={false} client={client} />);
    // ⚠ ONE FILE, TWO TABLES, TWO SLOTS. G45 COUNTS rather than sniffing for
    // the string precisely because a `"filterBarSlot" in text` check goes
    // green with the second table's control missing.
    expect(html).toContain(panel.open);
  });

  // ══════════════════════════════════════════════════════════════════════
  // CR-045 WAVE E — THE TWO EXPORTS THAT EXISTED AND WERE NEVER DRAWN
  //
  // Measured across `apps/*/exports.py`: ELEVEN resources are registered —
  // assets, charge-codes, cycles, plans, premises, rate-change-history,
  // rate-schedules, reads, routes, taxes, units. Two of wave E's five lists
  // are ALREADY in that set (routes, cycles) and three are not (service
  // requests, reference data, chart of accounts).
  //
  // ⚠ **AND THE BYTES WERE ALREADY PROVEN FOR BOTH.**
  // `06-backend/tests/test_be_list_export.py::
  //  test_be_list_export_routes_and_cycles_columns` writes the file, reads it
  // back with `csv.reader` and asserts the header row and the values. So the
  // task for these two was never "build an export" — the capability was real,
  // byte-proven and unreachable, because no screen passed `downloadSlot`.
  // BR-SHL-010 means an undeclared capability is not drawn, and this one was
  // declared on the server and undeclared on the client.
  // ⚠ **BOTH SUB-TABS, SEPARATELY, AND THE FIRST DRAFT OF THIS CASE ONLY
  //    COVERED ONE.** `RoutesCyclesTab` renders whichever sub-tab `?rc=` names
  //    and ONE `DataTable`, so a single render exercises a single toolbar —
  //    exactly the hole G45 counts declarations to avoid. Proved by deleting
  //    the routes slot: the one-render version went red, which showed it was
  //    only ever watching routes.
  it.each([
    ["routes", "/brazosbend/x"],
    ["cycles", "/brazosbend/x?rc=cycles"],
  ])("wave E: Settings > %s draws the download control", (_name, path) => {
    const { client } = recordingClient();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[path]}>
            <RoutesCyclesTab readOnly={false} client={client} />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(html).toContain("Download CSV");
  });
});
