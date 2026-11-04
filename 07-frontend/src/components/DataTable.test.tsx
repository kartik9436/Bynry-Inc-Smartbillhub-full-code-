// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-006 · US-SHL-007 · US-SHL-008 (EP-SHL-02 §Stories)  Screens: S17, S25, S30, S33, S34 (representative list screens)
// Rules:    BR-SHL-010 (one framework) · BR-SHL-011 (URL grammar) · BR-SHL-012 (state composition) · BR-SHL-013 (column visibility)
// ───────────────────────────────────────────────────────
// TC tests for FE-02 DataTable. Same conventions as the EP-SHL-04 maiden run:
// no DOM library is in package.json, so markup asserts on react-dom/server
// static output and interaction laws run through the exported pure functions
// (request-state transitions, search debouncer) under vitest fake timers.
// Anything needing a live browser, the server, or another module's packet is
// an honest it.todo.
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n"; // initializes the i18next singleton with the five catalogs

import {
  DataTable,
  SEARCH_DEBOUNCE_MS,
  SEARCH_MIN_CHARS,
  clearQueryAndFilters,
  createSearchDebouncer,
  moveColumnDown,
  moveColumnUp,
  nextSortState,
  toggleColumnVisible,
  withPageSize,
  withSearch,
} from "./DataTable";
import {
  DEFAULT_PAGE_SIZE,
  PAGE_SIZES,
  clampPage,
  columnPreferenceKey,
  columnsFromPreference,
  defaultRequestState,
  defaultVisibleColumns,
  parseTableParams,
  serializeTableParams,
} from "./tableTypes";
import type { TableConfig } from "./tableTypes";
import { createApiClient } from "@/api/client";
import { getUserPreference, putUserPreference } from "@/api/endpoints";

const noop = () => undefined;

type AccountRow = {
  id: string;
  account_no: string;
  name: string;
  balance: string;
  status: string;
};

// S17 Accounts capability-matrix row (illustrative per the epic — the accounts
// module owns the real row; the framework renders whatever is declared).
const s17Config: TableConfig<AccountRow> = {
  screenId: "S17",
  columns: [
    { key: "account_no", label: "Account #", identity: true, sortable: true },
    { key: "name", label: "Name", sortable: true },
    { key: "balance", label: "Balance", sortable: true, numeric: true },
    { key: "status", label: "Status" },
  ],
  getRowId: (row) => row.id,
  searchFields: ["account_no", "name"],
  filters: [
    {
      name: "status",
      label: "Status",
      options: [
        { value: "current", label: "Current" },
        { value: "past_due", label: "Past due" },
      ],
    },
  ],
  defaultSort: { sort: "balance", dir: "desc" },
};

// §4 test data: Silver Creek, 60 accounts A-10401…A-10460 (balances
// $0.00–$1,240.55, incl. A-10432 Maria Delgado $148.63).
function seedSilverCreek(): AccountRow[] {
  return Array.from({ length: 60 }, (_, i) => {
    const n = 10401 + i;
    return {
      id: `acc-${n}`,
      account_no: `A-${n}`,
      name: n === 10432 ? "Maria Delgado" : `Customer ${n}`,
      balance: n === 10432 ? "148.63" : (i * 21.02).toFixed(2),
      status: i % 3 === 0 ? "past_due" : "current",
    };
  });
}

const emptyCopy = {
  title: "No accounts yet.",
  helper: "Create your first account to start billing.",
  ctaLabel: "+ New account",
  onCta: noop,
};

afterEach(() => {
  vi.useRealTimers();
});

describe("US-SHL-006 — table core: server pagination, sorting & per-list search", () => {
  it("US-SHL-006 TC-1: S17 with 60 seeded accounts renders one server page + pager, amended page-size set, default sort indicated", () => {
    const rows = seedSilverCreek();
    const state = defaultRequestState(s17Config);
    const html = renderToStaticMarkup(
      <DataTable
        config={s17Config}
        state={state}
        onStateChange={noop}
        rows={rows.slice(0, 50)} // the server serves ONE page (IS-2)
        totalRows={60}
        loading={false}
        empty={emptyCopy}
      />,
    );
    // IS-2 as amended 2026-08-09: default 50 (the epic's "25 rows + options
    // 50/100" TC text is superseded — reported, not resolved here).
    expect(PAGE_SIZES).toEqual([50, 100, 200, 500, 1000]);
    expect(DEFAULT_PAGE_SIZE).toBe(50);
    expect((html.match(/data-table-row/g) ?? []).length).toBe(50);
    expect(html).toContain("1–50 of 60");
    for (const size of [100, 200, 500, 1000]) {
      expect(html).toContain(`>${size}</option>`);
    }
    expect(html).toMatch(/<option[^>]*selected[^>]*>50<\/option>/);
    // Default sort (balance desc per the matrix row) is visually indicated.
    expect(html).toContain('aria-sort="descending"');
    expect(html).toContain("▼");
  });

  it("US-SHL-006 TC-2: clicking the Balance header toggles direction; the URL carries sort=balance&dir=desc; secondary sort by id stays server-side", () => {
    const base = defaultRequestState(s17Config); // balance desc (matrix default)
    const first = nextSortState(base, "balance"); // toggle → asc
    const second = nextSortState(first, "balance"); // toggle again → desc
    expect(first).toMatchObject({ sort: "balance", dir: "asc", page: 1 });
    expect(second).toMatchObject({ sort: "balance", dir: "desc", page: 1 });
    // A different column starts ascending.
    expect(nextSortState(base, "name")).toMatchObject({ sort: "name", dir: "asc" });

    // BR-SHL-011: the URL grammar carries exactly sort + dir — ties broken by
    // a STABLE secondary sort on id happen on the server (IS-2), never as a
    // second URL param.
    const params = serializeTableParams(second, s17Config);
    expect(params.toString()).toContain("sort=balance&dir=desc");
    expect(params.get("sort")).toBe("balance");

    const html = renderToStaticMarkup(
      <DataTable
        config={s17Config}
        state={first}
        onStateChange={noop}
        rows={seedSilverCreek().slice(0, 50)}
        totalRows={60}
        loading={false}
        empty={emptyCopy}
      />,
    );
    expect(html).toContain('aria-sort="ascending"');
    expect(html).toContain("▲");
  });

  it("US-SHL-006 TC-3: typing 'Delgado' issues ONE debounced request after 300 ms; under 2 chars never queries; ✕ clears immediately", () => {
    vi.useFakeTimers();
    expect(SEARCH_DEBOUNCE_MS).toBe(300); // IS-3
    expect(SEARCH_MIN_CHARS).toBe(2); // IS-3

    const fired: string[] = [];
    const debouncer = createSearchDebouncer((q) => fired.push(q));
    for (const keystroke of ["D", "De", "Del", "Delg", "Delga", "Delgad", "Delgado"]) {
      debouncer.type(keystroke);
      vi.advanceTimersByTime(50); // fast typing — every keystroke inside the window
    }
    expect(fired).toEqual([]); // nothing fires mid-burst
    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS);
    expect(fired).toEqual(["Delgado"]); // exactly ONE request for the burst

    // IS-3 min 2 chars: a 1-char query is treated as no query.
    const shortFired: string[] = [];
    const short = createSearchDebouncer((q) => shortFired.push(q));
    short.type("D");
    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS);
    expect(shortFired).toEqual([]);

    // Dropping below 2 chars after a real query restores the full list.
    debouncer.type("D");
    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS);
    expect(fired).toEqual(["Delgado", ""]);

    // ✕ clears the request state immediately (no debounce on clear).
    const cleared = withSearch({ ...defaultRequestState(s17Config), q: "Delgado", page: 2 }, "");
    expect(cleared).toMatchObject({ q: "", page: 1 });

    // The search box renders only because S17 DECLARES search fields
    // (BR-SHL-010), pre-filled from state with its ✕ visible.
    const html = renderToStaticMarkup(
      <DataTable
        config={s17Config}
        state={{ ...defaultRequestState(s17Config), q: "Delgado" }}
        onStateChange={noop}
        rows={seedSilverCreek().filter((r) => r.name === "Maria Delgado")}
        totalRows={1}
        loading={false}
        empty={emptyCopy}
      />,
    );
    expect(html).toContain('value="Delgado"');
    expect(html).toContain("Clear search");
  });

  // ── B14 rule 19 · EACH LIST'S OWN SEARCH PROMPT (DEF-510) ───────────────
  //
  // Every list in the product said "Search this list" — not because a screen
  // chose it, but because `TableConfig` had no field to say anything else, and
  // DataTable named one shared key. r10 writes a different sentence per list,
  // each saying WHAT the search matches. Both halves are asserted here: the
  // DEFAULT (so the field could land without moving a screen) and the OPT-IN.
  it("US-SHL-006 (B14 rule 19 / DEF-510): a list draws its OWN search prompt, and the default is unchanged", () => {
    const table = (config: typeof s17Config) =>
      renderToStaticMarkup(
        <DataTable
          config={config}
          state={defaultRequestState(config)}
          onStateChange={noop}
          rows={seedSilverCreek().slice(0, 3)}
          totalRows={3}
          loading={false}
          empty={emptyCopy}
        />,
      );

    // Default: the string every list has always shown, on both the visible
    // prompt and the accessible name.
    const byDefault = table(s17Config);
    expect(byDefault).toContain('placeholder="Search this list"');
    expect(byDefault).toContain('aria-label="Search this list"');

    // Opt-in: one line on the config, and the two move TOGETHER — a screen
    // reader hearing "Search this list" over a box the sighted user is told
    // matches accounts, meters and addresses is the split rule 19 closes.
    // `templates.catalog.searchPlaceholder` is used because it is a key that
    // ALREADY EXISTS in all eleven catalogues — the opt-in has to be provable
    // without minting a key no screen has a call site for (G18 counts those).
    const own = table({ ...s17Config, searchPlaceholder: "templates.catalog.searchPlaceholder" });
    // ⚠ THE SENTENCE MOVED ON 2026-08-27 (CR-045 wave B task B.1) and is
    // quoted from the catalogue rather than re-guessed: the templates catalog
    // searches name, code, category and used-by, and B14 rule 19's grammar
    // says the prompt names them. What this case asserts is the OPT-IN — that
    // `searchPlaceholder` reaches both attributes and displaces the default —
    // so the string is incidental and only has to be the current one.
    expect(own).toContain('placeholder="Search template name, code, category or use…"');
    expect(own).toContain('aria-label="Search template name, code, category or use…"');
    expect(own).not.toContain("Search this list");
  });

  it("US-SHL-006 TC-4: while fetching, skeleton rows (6–10 grey bars) render — never a bare spinner — and the toolbar stays", () => {
    const html = renderToStaticMarkup(
      <DataTable
        config={s17Config}
        state={defaultRequestState(s17Config)}
        onStateChange={noop}
        rows={[]}
        totalRows={null}
        loading={true}
        empty={emptyCopy}
      />,
    );
    const rowCount = (html.match(/skeleton-row/g) ?? []).length;
    expect(rowCount).toBeGreaterThanOrEqual(6);
    expect(rowCount).toBeLessThanOrEqual(10);
    expect(html).not.toContain("spinner");
    expect(html).toContain("table-toolbar"); // filters/search remain during a page fetch
    expect(html).not.toContain("<td"); // no stale rows behind the skeleton
  });

  it("US-SHL-006 TC-5 (negative): ?page=999&per=37&sort=nonsense falls back/clamps per BR-SHL-011 and renders normally", () => {
    const parsed = parseTableParams(
      new URLSearchParams("page=999&per=37&sort=nonsense&hello=world"),
      s17Config,
    );
    expect(parsed.per).toBe(50); // 37 is not in the amended 50/100/200/500/1000 set
    expect(parsed.sort).toBe("balance"); // nonsense → screen default
    expect(parsed.dir).toBe("desc");
    // BR-SHL-011: the out-of-range page clamps to the last REAL page once the
    // server total (60) is known — page 2 at 50/page.
    const page = clampPage(parsed.page, 60, parsed.per);
    expect(page).toBe(2);

    const rows = seedSilverCreek();
    const html = renderToStaticMarkup(
      <DataTable
        config={s17Config}
        state={{ ...parsed, page }}
        onStateChange={noop}
        rows={rows.slice(50)}
        totalRows={60}
        loading={false}
        empty={emptyCopy}
      />,
    );
    expect((html.match(/data-table-row/g) ?? []).length).toBe(10);
    expect(html).toContain("51–60 of 60"); // renders normally — no error screen
  });

  it("US-SHL-006 TC-6 (negative): a 500 from the list endpoint renders the A18 §4 failed card with Retry against the UNCHANGED query state", () => {
    const state = defaultRequestState(s17Config);
    const html = renderToStaticMarkup(
      <DataTable
        config={s17Config}
        state={state}
        onStateChange={noop}
        rows={[]}
        totalRows={null}
        loading={false}
        error={{ onRetry: noop }} // Retry = the consumer refetches with the same state
        empty={emptyCopy}
      />,
    );
    expect(html).toContain("state-failed"); // the ONE FailedWithRetry (BR-SHL-020)
    expect(html).toContain("Retry");
    expect(html).toContain("This list couldn&#x27;t load.");
    // BR-SHL-020: plain-language default reason, never a raw code alone.
    expect(html).toContain("Retry runs the same request again.");
    expect(html).toContain("table-toolbar"); // search/filters stay reachable
  });

  it.todo(
    "US-SHL-006 TC-7 (isolation): 60 Silver Creek + 40 Harbor Point accounts — no cross-tenant row id in any page/sort/search permutation; RLS/server scope, lands with the accounts-list journey + backend isolation suite",
  );

  // ── Supplementary (non-TC) coverage for the BR-SHL-012 state composition ──
  it("US-SHL-006 (BR-SHL-012 / A18 §1): zero rows with no query state renders ONLY the consumer's empty-list block — no table header, no toolbar", () => {
    const html = renderToStaticMarkup(
      <DataTable
        config={s17Config}
        state={defaultRequestState(s17Config)}
        onStateChange={noop}
        rows={[]}
        totalRows={0}
        loading={false}
        empty={emptyCopy}
      />,
    );
    expect(html).toContain("No accounts yet.");
    expect(html).toContain("+ New account");
    expect(html).not.toContain("<table"); // BR-SHL-012: empty-header ban
    expect(html).not.toContain("<th");
    expect(html).not.toContain("table-toolbar");
  });

  it("US-SHL-006 (BR-SHL-012 / A18 §2): zero rows AFTER a search keeps the toolbar and replaces the rows region with ZeroResults", () => {
    const html = renderToStaticMarkup(
      <DataTable
        config={s17Config}
        state={{ ...defaultRequestState(s17Config), q: "zzzz" }}
        onStateChange={noop}
        rows={[]}
        totalRows={0}
        loading={false}
        empty={emptyCopy}
      />,
    );
    expect(html).toContain("No results for");
    expect(html).toContain("zzzz");
    expect(html).toContain("Clear filters");
    expect(html).toContain("table-toolbar"); // toolbar/filters stay (A18 §2)
    expect(html).not.toContain("<table"); // still no empty header
    // The one clear action drops search AND filters together.
    const cleared = clearQueryAndFilters({
      ...defaultRequestState(s17Config),
      q: "zzzz",
      filters: { status: "past_due" },
      page: 3,
    });
    expect(cleared).toMatchObject({ q: "", filters: {}, page: 1 });
  });

  it("US-SHL-006 (BR-SHL-010): a capability absent from the matrix row does not render — no search box without declared search fields", () => {
    const noSearchConfig: TableConfig<AccountRow> = { ...s17Config, searchFields: undefined };
    const html = renderToStaticMarkup(
      <DataTable
        config={noSearchConfig}
        state={defaultRequestState(noSearchConfig)}
        onStateChange={noop}
        rows={seedSilverCreek().slice(0, 50)}
        totalRows={60}
        loading={false}
        empty={emptyCopy}
      />,
    );
    expect(html).not.toContain('type="search"');
    // Changing the page size returns to page 1 (result window changed).
    expect(withPageSize({ ...defaultRequestState(s17Config), page: 2 }, 200)).toMatchObject({
      per: 200,
      page: 1,
    });
  });
});

describe("US-SHL-007 — dynamic column chooser (interim ⋮ spec) & URL grammar fallbacks", () => {
  it("US-SHL-007 TC-3: hide 'Status', move 'Balance' first — the table re-renders in the stored order (persistence wiring is US-SHL-013's)", () => {
    const defaults = defaultVisibleColumns(s17Config);
    expect(defaults).toEqual(["account_no", "name", "balance", "status"]);

    let visible = toggleColumnVisible(defaults, "status", s17Config);
    expect(visible).toEqual(["account_no", "name", "balance"]);
    visible = moveColumnUp(visible, "balance");
    visible = moveColumnUp(visible, "balance");
    expect(visible).toEqual(["balance", "account_no", "name"]);
    // This ordered array IS the `table.S17.columns` preference value the
    // consumer persists server-side (BR-SHL-013/BR-SHL-027, via US-SHL-013).

    const html = renderToStaticMarkup(
      <DataTable
        config={s17Config}
        state={defaultRequestState(s17Config)}
        onStateChange={noop}
        rows={seedSilverCreek().slice(0, 50)}
        totalRows={60}
        loading={false}
        empty={emptyCopy}
        visibleColumns={visible}
      />,
    );
    const thead = html.slice(html.indexOf("<thead"), html.indexOf("</thead>"));
    expect(thead).not.toContain("Status"); // hidden column has no header cell
    expect(thead.indexOf("Balance")).toBeLessThan(thead.indexOf("Account #")); // reordered
    expect(html).toContain("Status"); // …but it still appears in the ⋮ menu, re-showable
    expect(html).toContain("Reset table"); // BR-SHL-013 reset control
  });

  it("US-SHL-007 TC-4 (negative): the identity column cannot be hidden — toggle is a no-op and its ⋮ control renders disabled", () => {
    const defaults = defaultVisibleColumns(s17Config);
    // BR-SHL-013: identity column (Account #) never leaves the visible set.
    expect(toggleColumnVisible(defaults, "account_no", s17Config)).toEqual(defaults);
    // Even a stored preference missing the identity column renders it anyway.
    const html = renderToStaticMarkup(
      <DataTable
        config={s17Config}
        state={defaultRequestState(s17Config)}
        onStateChange={noop}
        rows={seedSilverCreek().slice(0, 50)}
        totalRows={60}
        loading={false}
        empty={emptyCopy}
        visibleColumns={["name", "balance"]}
      />,
    );
    const thead = html.slice(html.indexOf("<thead"), html.indexOf("</thead>"));
    expect(thead).toContain("Account #");
    // BR-SHL-013: the identity column's hide control renders DISABLED and
    // CHECKED — it stays visible always.
    //
    // ⚠ AMENDED 2026-08-21 (DEF-440). This asserted the exact attribute
    // BYTE ORDER — `'<input type="checkbox" disabled="" checked=""'` — so
    // adding a `className` to the input broke it while the RULE it exists for
    // was untouched. An assertion on serialisation order fails on changes it
    // was never meant to catch, and passes on a control that is disabled for
    // the wrong column. It now asserts the rule.
    const identityBox = html.slice(html.indexOf("<input type=\"checkbox\""));
    const firstBox = identityBox.slice(0, identityBox.indexOf(">") + 1);
    expect(firstBox).toContain('disabled=""');
    expect(firstBox).toContain('checked=""');
  });

  it("US-SHL-007 TC-5 (negative): an unknown f.bogus param is ignored; declared filters still restore", () => {
    const parsed = parseTableParams(new URLSearchParams("f.bogus=1&f.status=past_due"), s17Config);
    // BR-SHL-011: only DECLARED filters exist in the request state.
    expect(parsed.filters).toEqual({ status: "past_due" });
  });

  // ── DEF-647 · US-SHL-013's service has LANDED, so this stops being a todo ──
  //
  // ⚠ **THE `it.todo` THAT USED TO SIT HERE IS WHY THE COLUMN SELECTOR SHIPPED
  // BROKEN.** Its own title said it "lands with US-SHL-013's service"; the
  // deferral was honest, was never converted into a defect row, and so was
  // invisible to everything that counts work — while every OTHER test on this
  // page passed, because they all assert within ONE render and the bug only
  // exists at the SECOND one. The PO found it by using the product.
  //
  // The remount half of TC-7 needs a real DOM and lives in
  // `DataTableColumnPrefs.dom.test.tsx` (vitest.config.ts reserves this file's
  // `node` environment for the 200+ static-markup suites, DEF-523). What is
  // asserted HERE is the half that belongs in this tier: the CLIENT's side of
  // the isolation law, and the sanitiser that stands between a stored value and
  // this component.

  it("US-SHL-007 TC-7 (isolation, client half): the request names only the KEY — a client cannot ask for another user's columns", async () => {
    const seen: { url: string; method: string; body: string | null }[] = [];
    const client = createApiClient({
      tenant: "silvercreek",
      fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
        seen.push({
          url: String(input),
          method: init?.method ?? "GET",
          body: typeof init?.body === "string" ? init.body : null,
        });
        return new Response(JSON.stringify({ key: "table.S17.columns", value: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });

    await getUserPreference("table.S17.columns", client);
    await putUserPreference("table.S17.columns", ["account_no", "name"], client);

    // The tenant is the URL's first path segment (BR-TEN-003, put there by the
    // transport). The USER appears nowhere at all — not in the path, not in the
    // query, not in the body — so the only preference a session can reach is
    // its own. That is what makes TC-7 a property of the endpoint rather than a
    // promise the UI keeps; the server half is proved in
    // 06-backend/tests/test_us_shl_013_user_preferences.py, its tenant half
    // under a NOSUPERUSER/NOBYPASSRLS RLS probe.
    expect(seen).toHaveLength(2);
    for (const call of seen) {
      expect(call.url).toContain("/api/silvercreek/user-preferences/table.S17.columns");
      expect(call.url).not.toContain("user_id");
      expect(call.url).not.toContain("user=");
      expect(call.body ?? "").not.toContain("user");
      expect(call.body ?? "").not.toContain("tenant");
    }
    expect(seen[1].method).toBe("PUT");
    // What is stored is EXACTLY the ordered array the pure transitions return.
    expect(seen[1].body).toBe(JSON.stringify({ value: ["account_no", "name"] }));
  });

  it("US-SHL-007 TC-3/TC-4: the key is per screen, and a screen id that cannot form a lawful key does not persist", () => {
    expect(columnPreferenceKey(s17Config)).toBe("table.S17.columns");
    // BR-SHL-024's grammar, mirrored client-side: a screen whose id carries a
    // character the server refuses is skipped SILENTLY rather than answered
    // with a 422 on every column click.
    expect(columnPreferenceKey({ ...s17Config, screenId: "S17 accounts" })).toBeNull();
    expect(columnPreferenceKey({ ...s17Config, screenId: "" })).toBeNull();
  });

  it("US-SHL-007 TC-3 + BR-SHL-024: a stored set is sanitised against the LIVE config, never trusted", () => {
    // Nothing stored yet → the declared defaults (unknown key reads as absent).
    expect(columnsFromPreference(null, s17Config)).toEqual(defaultVisibleColumns(s17Config));
    // A stored key the screen no longer has is IGNORED, not rendered.
    expect(columnsFromPreference(["account_no", "phone", "status"], s17Config)).toEqual([
      "account_no",
      "status",
    ]);
    // Order is preserved — it is the user's reorder (IS-5), not a set.
    expect(columnsFromPreference(["status", "name", "account_no"], s17Config)).toEqual([
      "status",
      "name",
      "account_no",
    ]);
    // Wrong shape, or nothing left after filtering → defaults, never a crash
    // and never an empty table the user cannot get back from.
    expect(columnsFromPreference({ account_no: true }, s17Config)).toEqual(
      defaultVisibleColumns(s17Config),
    );
    expect(columnsFromPreference(["phone"], s17Config)).toEqual(
      defaultVisibleColumns(s17Config),
    );
  });
});

describe("US-SHL-008 — row actions, bulk bar & CSV export (this packet ships the IS-9 hook point only)", () => {
  it("US-SHL-008 (IS-9 hook): the capability row renders the consumer's download slot ahead of the ⋮ chooser — FE-14 DownloadButton plugs in later", () => {
    const html = renderToStaticMarkup(
      <DataTable
        config={s17Config}
        state={defaultRequestState(s17Config)}
        onStateChange={noop}
        rows={seedSilverCreek().slice(0, 50)}
        totalRows={60}
        loading={false}
        empty={emptyCopy}
        downloadSlot={
          <button type="button" className="download-stub">
            Download CSV
          </button>
        }
      />,
    );
    expect(html).toContain("download-stub");
    expect(html).toContain("Download CSV");
    expect(html.indexOf("download-stub")).toBeGreaterThan(html.indexOf("table-toolbar"));
    // Ordering is asserted against the chooser's own accessible name rather
    // than a class name, so a restyle cannot break a test about ORDER.
    expect(html.indexOf("download-stub")).toBeLessThan(
      html.indexOf('aria-label="Show or hide columns"'),
    );
  });

  it.todo(
    "US-SHL-008 TC-1..TC-3: multi-select + dark bulk bar with live count and display-only running $ total (BR-SHL-014/015) — lands with the money-table packets + FE-04 ConfirmDialog",
  );
  it.todo(
    "US-SHL-008 TC-4: per-row action dropdowns varying by row state — consuming screens' A2 declarations + US-SHL-014 disabled-with-reason gating",
  );
  it.todo(
    "US-SHL-008 TC-5..TC-8: CSV export execution, 50,000-row guard, audit_log row, tenant isolation (BR-SHL-016) — server-side BE-21 + FE-14 DownloadButton scope",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-006@e879338 (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ tsc✔ eslint✔ vitest 31/31✔ (5 TC todo this packet — browser/journey/backend scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────


// ── IS-5 · reorder is BI-directional (DEF-358 amended) ─────────────────────
//
// ⚠ THE DEFECT AS FIRST FILED WAS WRONG, AND THIS BLOCK IS WHAT IT SHOULD HAVE
// SAID. DEF-358 claimed the column panel was "built, tested and reachable by
// nobody" on the evidence that `toggleColumnVisible` had two hits in
// DataTable.tsx and three in its test — read as "definition only". Both hits in
// DataTable.tsx are the definition AND the panel's own call site: the panel
// exists and always has.
//
// What was actually missing is smaller and real: `moveColumnUp` had no
// counterpart, so a column could be moved up and never back down. A user who
// overshot had to Reset table and start again.

describe("moveColumnDown", () => {
  const ORDER = ["code", "name", "amount", "status"];

  it("swaps a column with the one after it", () => {
    expect(moveColumnDown(ORDER, "name")).toEqual(["code", "amount", "name", "status"]);
  });

  it("is a no-op at the end of the order — there is nowhere further to go", () => {
    expect(moveColumnDown(ORDER, "status")).toEqual(ORDER);
  });

  it("is a no-op for a column that is not visible", () => {
    expect(moveColumnDown(ORDER, "gl_account")).toEqual(ORDER);
  });

  it("round-trips with moveColumnUp, which is the property that was missing", () => {
    const moved = moveColumnDown(ORDER, "code");
    expect(moved).not.toEqual(ORDER);
    expect(moveColumnUp(moved, "code")).toEqual(ORDER);
  });

  it("does not mutate the array it was given", () => {
    const original = [...ORDER];
    moveColumnDown(ORDER, "name");
    expect(ORDER).toEqual(original);
  });
});

// ── RC-W3-T0 · EXPANDABLE ROWS (CR-029 B17 §7, needed by SET-06.3) ─────────
//
// The kit had NO disclosure capability at all: FE-01..21 carries no expandable
// row and `DataTable` had no slot for one, so CR-029's route wizard step 3 —
// premises rows that open into a unit/meter sub-table — had nothing lawful to
// build on. B8's ONE-implementation rule and B14 rule 20's one-table-type make
// a second table component the wrong answer; this is the same table, with one
// more declared capability.
//
// ⚠ THESE TESTS ARE THE WIRING PROOF, DELIBERATELY (hard-won law 2). The
// capability lands a wave BEFORE its consumer (RC-W3-T1..T5), so no screen
// passes `renderExpanded` yet. A component with an optional prop nothing passes
// is dead UI — so the suite exercises the REAL states (collapsed → expanded →
// collapsed, per row and in bulk, by mouse and by keyboard) rather than
// asserting that a type exists. The interactive half is
// `DataTable.dom.test.tsx`; this half is first-paint and the pure transitions.
// The fixture is read through Vite's own `?raw`, not `node:fs`: this app
// carries no `@types/node` on purpose (it would put Node's globals over 127
// components — `setTimeout` returning NodeJS.Timeout, and the rest), so a
// static `node:fs` import passes vitest and FAILS `tsc --noEmit`, which breaks
// `npm run build`. `tailwindTheme.test.ts` records the same trap.
import baselineHtml from "./__fixtures__/DataTable.baseline.html?raw";

import { areAllRowsExpanded, collapseAllRows, expandAllRows, toggleExpandedRow } from "./DataTable";

type RouteRow = { id: string; code: string; name: string; count: string };

const expandableRows: RouteRow[] = [
  { id: "r1", code: "RT-001", name: "Downtown loop", count: "12" },
  { id: "r2", code: "RT-002", name: "Harbor walk", count: "8" },
  { id: "r3", code: "RT-003", name: "Ridge drive", count: "31" },
];

// The SAME config the committed baseline fixture was rendered from — three
// columns, no search, no filters — so the comparison below is a fact about the
// component and not about a screen.
const baselineConfig: TableConfig<RouteRow> = {
  screenId: "BASELINE",
  columns: [
    { key: "code", label: "Code", identity: true, sortable: true },
    { key: "name", label: "Name", sortable: true },
    { key: "count", label: "Count", numeric: true },
  ],
  getRowId: (row) => row.id,
  defaultSort: { sort: "code", dir: "asc" },
};

const baselineEmpty = { title: "t", helper: "h", ctaLabel: "c", onCta: noop };

function renderBaseline(config: TableConfig<RouteRow>): string {
  return renderToStaticMarkup(
    <DataTable
      config={config}
      state={defaultRequestState(config)}
      onStateChange={noop}
      rows={expandableRows}
      totalRows={3}
      loading={false}
      empty={baselineEmpty}
    />,
  );
}

describe("RC-W3-T0 — DataTable gains expandable rows (CR-029 SET-06.3)", () => {
  it("RC-W3-T0 (backward compatibility): a list that declares no renderExpanded renders BYTE-IDENTICALLY to the pre-change component", () => {
    // ⚠ `__fixtures__/DataTable.baseline.html` was captured from this component
    // at HEAD BEFORE the capability was written — it is the only artefact that
    // can answer "did every existing caller keep its exact output". Structural
    // assertions ("still three columns") pass on a table that gained a stray
    // wrapper, an aria attribute or a whitespace text node; bytes do not.
    //
    // REGENERATING IT IS A DELIBERATE ACT. A future change to DataTable that
    // legitimately moves this markup re-captures the file in the same commit,
    // and the diff is then the reviewable statement of what moved on every list
    // screen in the product.
    expect(renderBaseline(baselineConfig)).toBe(baselineHtml);

    // ⚠ AND THE COMPARISON CAN TELL PASS FROM FAIL (law 7, and DEF-182's
    // lesson that a check whose output cannot distinguish the two is worse
    // than no check). The SAME comparison against the SAME fixture, with the
    // capability declared, must go red — otherwise the assertion above proves
    // only that a string was read from disk.
    expect(renderBaseline({ ...baselineConfig, renderExpanded: () => <tbody /> })).not.toBe(
      baselineHtml,
    );
  });

  it("RC-W3-T0 (BR-SHL-010): an UNDECLARED capability never renders — no expander column, no control, no expanded region", () => {
    const html = renderBaseline(baselineConfig);
    expect(html).not.toContain("aria-expanded");
    expect(html).not.toContain("colspan");
    expect(html).not.toContain("Expand");
    // Three declared columns → exactly three header cells and three body cells
    // per row. A leaked expander column shows up here as a fourth.
    // `/<th[ >]/` and not `/<th/` — the slice starts AT `<thead`, which the
    // looser pattern counts as a header cell.
    const thead = html.slice(html.indexOf("<thead"), html.indexOf("</thead>"));
    expect((thead.match(/<th[ >]/g) ?? []).length).toBe(3);
    const tbody = html.slice(html.indexOf("<tbody"), html.indexOf("</tbody>"));
    expect((tbody.match(/<tr/g) ?? []).length).toBe(3);
    expect((tbody.match(/<td/g) ?? []).length).toBe(9);
  });

  it("RC-W3-T0: a DECLARED list draws one real <button> per row, collapsed, with aria-expanded=false and a row-specific accessible name", () => {
    const config: TableConfig<RouteRow> = {
      ...baselineConfig,
      renderExpanded: (row) => <tbody data-row={row.id} />,
    };
    const html = renderBaseline(config);

    // A11y: a real button, not a clickable <td>/<span>. Three rows → three.
    expect((html.match(/aria-expanded="false"/g) ?? []).length).toBe(3);
    expect(html).not.toContain('aria-expanded="true"'); // first paint is collapsed
    // The accessible name names the ROW, from the identity column — twelve
    // buttons all called "Expand" are unusable with a screen reader.
    expect(html).toContain('aria-label="Expand RT-001"');
    expect(html).toContain('aria-label="Expand RT-002"');
    expect(html).toContain('aria-label="Expand RT-003"');
    // Collapsed rows render NO expanded region (it is not merely hidden).
    expect(html).not.toContain("colspan");
    expect(html).not.toContain('data-row="r1"');

    // The expander column is one extra cell in the header and in every row.
    const thead = html.slice(html.indexOf("<thead"), html.indexOf("</thead>"));
    expect((thead.match(/<th[ >]/g) ?? []).length).toBe(4);
    const tbody = html.slice(html.indexOf("<tbody"), html.indexOf("</tbody>"));
    expect((tbody.match(/<td/g) ?? []).length).toBe(12);
  });

  it("RC-W3-T0: the Expand-all affordance is a real button in the header, and it too only exists when the capability is declared", () => {
    const config: TableConfig<RouteRow> = {
      ...baselineConfig,
      renderExpanded: (row) => <tbody data-row={row.id} />,
    };
    const html = renderBaseline(config);
    // B14 rule 12 fixes the toolbar's grammar — `[Search…] [chips] [+ Filter]
    // … [▦ Columns]` — so a new control does NOT go there. It lives in the
    // expander column's own header cell, which is where the reader looks for
    // the control that governs that column.
    const thead = html.slice(html.indexOf("<thead"), html.indexOf("</thead>"));
    expect(thead).toContain('aria-label="Expand all rows"');
    expect(thead).toContain("<button");
    expect(renderBaseline(baselineConfig)).not.toContain("Expand all rows");
  });
});

// ── The pure transitions, testable with no DOM (this file's convention) ────
describe("RC-W3-T0 — expanded-row state transitions", () => {
  const IDS = ["r1", "r2", "r3"];

  it("toggleExpandedRow opens a closed row and closes an open one", () => {
    expect(toggleExpandedRow([], "r2")).toEqual(["r2"]);
    expect(toggleExpandedRow(["r1", "r2"], "r2")).toEqual(["r1"]);
  });

  it("toggleExpandedRow does not mutate the array it was given", () => {
    const open = ["r1"];
    toggleExpandedRow(open, "r2");
    expect(open).toEqual(["r1"]);
  });

  it("expandAllRows opens exactly the rows on the CURRENT page — paging is server-side, so there is nothing else to open", () => {
    expect(expandAllRows(IDS)).toEqual(IDS);
    expect(collapseAllRows()).toEqual([]);
  });

  it("areAllRowsExpanded is the label's own predicate, and an empty page is never 'all expanded'", () => {
    expect(areAllRowsExpanded(IDS, IDS)).toBe(true);
    expect(areAllRowsExpanded(["r1", "r2"], IDS)).toBe(false);
    // A stale id left over from the previous page does not make the new page
    // look expanded — the answer is about THESE rows.
    expect(areAllRowsExpanded(["r9"], IDS)).toBe(false);
    expect(areAllRowsExpanded([], [])).toBe(false);
  });
});

// ── CR-045 A.4 ──────────────────────────────────────────────────────────────
describe("CR-045 A.4 — the toolbar's slot ORDER is the frame's, not the consumer's", () => {
  // ⚠ **WHY THIS IS ASSERTED AND NOT MERELY WRITTEN.** The order was already
  // correct in the JSX and had been for months, and three screens still got a
  // toolbar the PO called wrong — because "correct in the JSX" is a fact about
  // one commit and nothing re-asks it. DEF-896 moved the filter container,
  // DEF-1085 moved two chip groups OUT of `downloadSlot`, and CR-041 changed
  // the search prompt: three lanes, one row, no owner.
  //
  // The order is a CR-045 ratified fact now — search · filters · spacer · ↓ · ▥
  // — so it is pinned where a reorder goes red rather than unnoticed.
  //
  // It cannot claim the row LOOKS right: jsdom computes no layout and no gate
  // in this repo reads rendered output (hard-won law 6). Document order is what
  // a render can see, and document order is what the rule is about.
  it("renders search · filters · spacer · download · columns, in that order", () => {
    const rows = seedSilverCreek();
    const html = renderToStaticMarkup(
      <DataTable
        config={s17Config}
        state={defaultRequestState(s17Config)}
        onStateChange={noop}
        rows={rows.slice(0, 5)}
        totalRows={5}
        loading={false}
        empty={emptyCopy}
        filterBarSlot={<span data-probe="filters" />}
        downloadSlot={<span data-probe="download" />}
      />,
    );
    const toolbar = html.slice(
      html.indexOf('class="table-toolbar"'),
      html.indexOf("<table"),
    );
    const at = (needle: string) => {
      const index = toolbar.indexOf(needle);
      expect(index, `not in the toolbar: ${needle}`).toBeGreaterThan(-1);
      return index;
    };
    const order = [
      'type="search"',
      'data-probe="filters"',
      "table-toolbar-spacer",
      'data-probe="download"',
      "<details",
    ].map(at);
    expect(order).toEqual([...order].sort((a, b) => a - b));
  });

  it("puts the download control AFTER the spacer, which is what right-aligns it", () => {
    // ⚠ ROWS, NOT AN EMPTY LIST. The first draft passed `rows={[]}` and went red
    // with `expected -1 to be less than -1` — the empty state replaces the WHOLE
    // table region, toolbar included, so neither marker was in the markup and
    // `indexOf` returned -1 twice. A check whose two sides are both absent
    // reports a comparison it never made (DEF-182).
    //
    // The spacer is the only thing in this toolbar that pushes a control to the
    // right-hand end. A download slot rendered BEFORE it would sit against the
    // filters — and that is exactly the confusion that made three screens put
    // their segmented filters in `downloadSlot` in the first place (DEF-1085).
    const html = renderToStaticMarkup(
      <DataTable
        config={s17Config}
        state={defaultRequestState(s17Config)}
        onStateChange={noop}
        rows={seedSilverCreek().slice(0, 3)}
        totalRows={3}
        loading={false}
        empty={emptyCopy}
        downloadSlot={<span data-probe="download" />}
      />,
    );
    expect(html.indexOf("table-toolbar-spacer")).toBeLessThan(
      html.indexOf('data-probe="download"'),
    );
  });
});
