// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-092-BRC01 step 2 — `AST-B-19`, the FRONT half of server-side
//          paging inside an asset. `AST-B-24` (wave C lane 3, 2.237.8) moved
//          three in-asset lists onto the house envelope and said in terms that
//          four shipped consumers still read the old shape; this is that debt,
//          and it is a LIVE BREAK rather than a missing feature.
// Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
//          hard-won law 5 (one description of a generated thing) · law 7's
//          *incapable of failing* clause · B14 rule 14 (a list carries the
//          pagination footer)
// Tests:   this file
// Impacts: src/api/endpoints.ts (three wrappers) ·
//          src/features/assets/AssetDetailPage.tsx (reads, assignments) ·
//          src/features/metering/ReadDetailPage.tsx ·
//          src/features/customers/accountDetailTabs.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY THIS FILE DRIVES THE CLIENT AND NOT THE CACHE, AND IT IS THE WHOLE
// REASON THE BREAK SHIPPED.** `AssetDetail.test.tsx` seeds React Query
// directly — `queryClient.setQueryData(assetReadsQueryKey(id), READS)` with
// `READS: AssetReadRow[]` — so the component is handed an ARRAY by the test
// and an ENVELOPE by the server, and every case passes over a screen that
// throws. A fixture that never crosses the boundary cannot see a boundary
// change. So each case here answers through a stub `ApiClient` with the
// **recorded server body** and lets the real wrapper unwrap it.
//
// The precedent is in `src/api/paginated.ts`'s own docstring: three Work
// screens drew empty tables over rows the server had returned
// (`DEF-WRK-4119`, `DEF-AST-4120`) because each described the reply by hand.
// The rule it states is the one these cases enforce: **a screen never
// describes a paged reply — it calls `readListPage` and gets rows and a
// total.**
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import { getAssetAssignments, getAssetReads } from "@/api/endpoints";

/** The body `GET /assets/{id}/reads` actually answers since `2.237.8`.
 *  Four keys, `results` carrying the rows — `apps/assets/api.py:267` builds it
 *  through DRF's `get_paginated_response`, and `count` there is the number of
 *  read DATES rather than of rows (the endpoint's own comment says so). */
const READS_BODY = {
  count: 1460,
  next: "/assets/a-1/reads?page=2",
  previous: null,
  results: [
    { read_id: "r-1", date: "2026-08-31", channel: "import", reading: "14212", consumption: "412", unit: "kWh", export: null, export_unit: null, export_read_id: null, source: "ami", read_type: "actual", status: "committed" },
    { read_id: "r-2", date: "2026-07-31", channel: "import", reading: "13800", consumption: "398", unit: "kWh", export: null, export_unit: null, export_read_id: null, source: "ami", read_type: "actual", status: "committed" },
  ],
};

const ASSIGNMENTS_BODY = {
  count: 37,
  next: "/assets/a-1/assignments?page=2",
  previous: null,
  results: [
    { id: "as-1", from_date: "2026-01-01", to_date: null, current: true, unit_id: "u-1", unit_label: "A", premise_address: "12 Foundry Row", by: "System", final_read_id: null },
  ],
};

/** Answers the recorded body for whichever of the two paths is asked for, and
 *  RECORDS the query it was asked with — a page control that sends nothing is
 *  the other half of this defect and a test that only checks rows cannot see
 *  it. */
function recordingClient(): { client: ApiClient; asked: { path: string; query?: Record<string, unknown> }[] } {
  const asked: { path: string; query?: Record<string, unknown> }[] = [];
  const client = {
    get: async (path: string, options?: { query?: Record<string, unknown> }) => {
      asked.push({ path, query: options?.query });
      const body = path.includes("/reads") ? READS_BODY : ASSIGNMENTS_BODY;
      return { ok: true, status: 200, data: body } as never;
    },
  } as unknown as ApiClient;
  return { client, asked };
}

describe("AST-B-19 · the front half: an asset's lists read the envelope the server answers", () => {
  it("tc1: a meter's reads come back as ROWS AND A TOTAL, not as the envelope itself", async () => {
    // RED BEFORE THE FIX, and this is the measured production behaviour rather
    // than a guess: `getAssetReads` declared `client.get<AssetReadRow[]>` and
    // returned the body unchanged, so the caller received
    // `{count, next, previous, results}` typed as an array. `.length` on that
    // is `undefined`, `undefined === 0` is false, and the panel handed the
    // OBJECT to `DataTable` as `rows`.
    const { client } = recordingClient();
    const page = await getAssetReads("a-1", client);
    expect(Array.isArray(page.rows), "rows must be an array, whatever the wire wraps them in").toBe(true);
    expect(page.rows).toHaveLength(2);
    expect(page.rows[0]?.reading).toBe("14212");
    // The TRUE total, so "1–50 of 1,460" is a true sentence rather than a
    // count of what happened to arrive.
    expect(page.total).toBe(1460);
  });

  it("tc2: the read page asked for is sent to the server, not filtered in the browser", async () => {
    // The half a rows-only assertion cannot see: NFR-3 is about the query, so
    // a wrapper that takes a page and forgets to send it passes tc1 and pages
    // nothing.
    const { client, asked } = recordingClient();
    await getAssetReads("a-1", client, { page: 3, per: 25 });
    expect(asked).toHaveLength(1);
    expect(asked[0]?.query).toMatchObject({ page: 3, per: 25 });
  });

  it("tc3: an asset's assignment history reads the same convention", async () => {
    const { client } = recordingClient();
    const page = await getAssetAssignments("a-1", client);
    expect(Array.isArray(page.rows)).toBe(true);
    expect(page.rows[0]?.premise_address).toBe("12 Foundry Row");
    expect(page.total).toBe(37);
  });

  it("tc4: a body that is NOT the envelope is refused by name rather than rendered as empty", async () => {
    // `readListPage` asserts at runtime because the types are the thing that
    // failed (paginated.ts's own reasoning). A bare array — the shape this
    // endpoint answered BEFORE 2.237.8 — must raise here rather than reach a
    // screen as zero rows, because "the server changed back" and "there are no
    // reads" are different facts and only one of them is a defect.
    const client = {
      get: async () => ({ ok: true, status: 200, data: [{ read_id: "r-1" }] }) as never,
    } as unknown as ApiClient;
    await expect(getAssetReads("a-1", client)).rejects.toThrow(/results|envelope|list/i);
  });
});
