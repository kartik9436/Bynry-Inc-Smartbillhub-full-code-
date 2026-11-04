// ── Trace ──────────────────────────────────────────────
// Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W5 task W5-T6:
//           the eight shipped callers of `GET /routes` / `GET /cycles` move onto
//           the paged envelope, and the bare-array branch retires on BOTH sides.
// Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §7 W5-T6
// Rules:    D7 (*"Yes - please do it"* — server-side pagination and sorting) ·
//           BR-SHL-011 (q/sort/dir/page/per/f.<name>; never error, always clamp) ·
//           hard-won law 2 (built is not wired — a payload no screen can read is
//           as dead as a screen with no payload)
// ───────────────────────────────────────────────────────
// RC-W3b made the server page these two lists ONLY when asked, because eight
// shipped callers read them as bare arrays and call `.find`/`.filter`. This is
// the migration that retires that branch: `getRoutes()`/`getCycles()` now ASK
// for a page and unwrap the envelope, so every one of those callers keeps the
// array it has always had while the wire carries `{count, results}`.
//
// ⚠ **THE TRUNCATION QUESTION IS THE REASON THESE ARE NOT ONE REQUEST.** A
// picker that quietly stops at the page size is a route a clerk cannot choose
// and no error anywhere — so `listAll` reads `count` and keeps asking until it
// holds every row. One request for any real tenant (routes are dozens; `per`
// tops out at 1000 under IS-2), and CORRECT for one that is not.
import { describe, expect, it } from "vitest";

import { getCycles, getRoutes } from "./endpoints";
import type { ApiClient } from "./client";

interface Recorded {
  path: string;
  query: Record<string, unknown> | undefined;
}

/** A stub client that records what was asked and replays a scripted answer. */
function stubClient(pages: unknown[]): { client: ApiClient; calls: Recorded[] } {
  const calls: Recorded[] = [];
  let index = 0;
  const client = {
    get: async (path: string, options?: { query?: Record<string, unknown> }) => {
      calls.push({ path, query: options?.query });
      const body = pages[Math.min(index, pages.length - 1)];
      index += 1;
      return { data: body, status: 200, headers: new Headers() };
    },
  } as unknown as ApiClient;
  return { client, calls };
}

const routeRow = (code: string) => ({ id: code, code, name: code, status: "active" });

describe("W5-T6 · the route and cycle lists speak the paged envelope", () => {
  it("asks for a page and hands the caller a plain array", async () => {
    const { client, calls } = stubClient([
      { count: 2, next: null, previous: null, results: [routeRow("RT-001"), routeRow("RT-002")] },
    ]);

    const rows = await getRoutes(client);

    expect(rows.map((row) => row.code)).toEqual(["RT-001", "RT-002"]);
    expect(calls).toHaveLength(1);
    expect(calls[0].path).toBe("/routes");
    // BR-SHL-011's grammar, and `per` at the top of the IS-2 vocabulary so the
    // one request is the only request for any tenant this product is built for.
    expect(calls[0].query).toMatchObject({ page: 1, per: 1000 });
  });

  it("keeps asking until it holds every row, so a picker never truncates in silence", async () => {
    const first = Array.from({ length: 1000 }, (_, i) => routeRow(`RT-${i}`));
    const second = [routeRow("RT-1000")];
    const { client, calls } = stubClient([
      { count: 1001, next: "?page=2", previous: null, results: first },
      { count: 1001, next: null, previous: "?page=1", results: second },
    ]);

    const rows = await getRoutes(client);

    expect(rows).toHaveLength(1001);
    expect(rows[1000].code).toBe("RT-1000");
    expect(calls).toHaveLength(2);
    expect(calls[1].query).toMatchObject({ page: 2, per: 1000 });
  });

  it("stops when a page comes back empty rather than asking forever", async () => {
    // A server whose `count` disagrees with what it serves must not spin the
    // browser. The loop's exit is the EMPTY page, not arithmetic on `count`.
    const { client, calls } = stubClient([
      { count: 99, next: null, previous: null, results: [routeRow("RT-001")] },
      { count: 99, next: null, previous: null, results: [] },
    ]);

    const rows = await getRoutes(client);

    expect(rows).toHaveLength(1);
    expect(calls).toHaveLength(2);
  });

  it("does the same for cycles", async () => {
    const { client, calls } = stubClient([
      { count: 1, next: null, previous: null, results: [{ id: "c", code: "CY-001" }] },
    ]);

    const rows = await getCycles(client);

    expect(rows.map((row) => row.code)).toEqual(["CY-001"]);
    expect(calls[0].path).toBe("/cycles");
  });
});
