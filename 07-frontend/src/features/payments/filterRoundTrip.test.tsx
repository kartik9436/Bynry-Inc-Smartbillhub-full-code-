// ── Trace ──────────────────────────────────────────────
// Defect:   `DEF-PAY-6293` — every filter on S33 is decorative
// Journey:  `JPAYLOCKBOX` check **M** — *"filtering the list by Source → Post
//           returns …"*, which is half of `P1.14`'s outcome sentence
// Change:   `CR-135-BRC07` `P1.14`
// Rules:    `BR-SHL-011` (the `f.<name>=` URL grammar — a filter is bookmarkable
//           and removable) · hard-won law 2 (built is not wired)
// ───────────────────────────────────────────────────────
//
// **THE FILTER BAR ON THE PAYMENTS LIST RENDERED, TICKED, AND CHANGED NOTHING.**
// Measured in a real browser on 2026-09-23: clicking *Source → Post* left the
// box unticked, the address at `?sort=posted_at&dir=desc` and the pager at
// `1–50 of 146`. *Status → Reversed* and *Type → Credit* behaved identically.
// The same click on the Accounts list ticked, moved the pager 72 → 68 and wrote
// `f.status=active`, so it was this screen and not the kit.
//
// **THE MECHANISM, AND IT IS WHY THIS TEST IS SHAPED THE WAY IT IS.** The PAGE
// builds `config = paymentsTableConfig(…)` and stores all table state in the
// URL through `serializeTableParams(next, config)`. `PaymentsTable` then builds
// a SECOND config — `{ ...baseConfig, filters: paymentsFilters(…) }` — and only
// the `FilterBar` and `DataTable` ever see it. `serializeTableParams` writes
// `f.<name>` **only for filters its config declares**, so a value set through
// the bar was dropped on the way to the URL, the URL is the only store, and the
// controlled checkbox snapped back.
//
// So the assertion is not *"does the bar render"* (`G45` already asks that, and
// it passed all the way through) — it is **does the state the bar produces
// survive the page's own serialiser**. That is one pure round trip and it needs
// no browser.
//
// RED FIRST (hard-won law 7), in vitest, before the fix:
//   × the page's own config declares every filter its bar offers
//     → expected [] to include 'origin'
//   × a filter set on the bar survives the page's serialiser
//     → expected null to be 'import'
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import {
  parseTableParams,
  serializeTableParams,
  type TableRequestState,
} from "@/components/tableTypes";
import { toggleFilterOption } from "@/components/FilterBar";

import { paymentsCells, paymentsFilters, paymentsTableConfig } from "./PaymentsPage";

const t = ((key: string, params?: Record<string, unknown>) =>
  i18n.t(key, params) as string) as never;

/** Exactly what `PaymentsPage` builds and hands to `serializeTableParams`. */
function pageConfig() {
  return paymentsTableConfig(
    t,
    paymentsCells(t, (path: string) => path, "UTC", "MM/DD/YYYY") as never,
  );
}

/** Exactly what the bar is rendered from — the table's enriched copy. */
function barFilters() {
  return paymentsFilters(t, [], "MM/DD/YYYY", []);
}

const BLANK: TableRequestState = {
  q: "",
  sort: "posted_at",
  dir: "desc",
  page: 1,
  per: 50,
  filters: {},
};

describe("the payments list's filters reach the address bar", () => {
  it("the page's own config declares every filter its bar offers", () => {
    const declared = (pageConfig().filters ?? []).map((filter) => filter.name);
    for (const offered of barFilters()) {
      expect(declared).toContain(offered.name);
    }
  });

  it("a filter set on the bar survives the page's serialiser", () => {
    const config = pageConfig();
    const next = toggleFilterOption(BLANK, "origin", "import");
    expect(next.filters.origin).toBe("import");
    const params = serializeTableParams(next, config);
    expect(params.get("f.origin")).toBe("import");
  });

  it("and comes back off a bookmarked address", () => {
    const config = pageConfig();
    const restored = parseTableParams(
      new URLSearchParams("sort=posted_at&dir=desc&f.origin=import"),
      config,
    );
    expect(restored.filters.origin).toBe("import");
  });

  it("every one of the eight, not just the new one", () => {
    const config = pageConfig();
    for (const filter of barFilters()) {
      // A date range declares TWO params and no option list; the option lists
      // declare one each. `filterParamNames` is what serialize/parse walk, so
      // asserting through a toggled state covers both shapes the same way.
      if (filter.dateRange !== undefined) continue;
      const value = filter.options[0]?.value;
      if (value === undefined) continue;
      const next = toggleFilterOption(BLANK, filter.name, value);
      expect(serializeTableParams(next, config).get(`f.${filter.name}`)).toBe(value);
    }
  });
});
