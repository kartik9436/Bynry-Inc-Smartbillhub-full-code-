// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-5754 — `GET /tax-jurisdictions` served a bare
//          `TaxJurisdiction[]` with no pager at all (NFR-3). Paging it CHANGES
//          THE SHAPE ON THE WIRE, so the backend half alone would have broken
//          the S13 wizard's step-1 picker in silence. These are the client
//          half; neither half proves the fix alone.
// Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
//          BR-SHL-033 (a dropdown past LONG_LIST_THRESHOLD is a type-ahead —
//          so a picker that can see only page 1 is a NEW defect, not a fix) ·
//          BR-TEN-037 (tenant-entered jurisdictions) · hard-won law 2 (built
//          is not wired) · CR-029 RC-W5-T6 (`/routes` and `/cycles` made this
//          exact wire change; `routesCyclesLists.cr029.test.ts` is the shape)
// Tests:   this file · 06-backend/tests/test_def_rat_5754_jurisdictions_page_in_sql.py
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY A FOLLOW-THE-COUNT LOOP AND NOT ONE PAGE, WHICH IS THE WHOLE POINT
// OF THIS FILE.** The control behind `getTaxJurisdictions` is
// `SearchSelectField`. It filters CLIENT-SIDE (`filterOptions(props.options,
// query)`) and it resolves the selected option's LABEL out of that same array
// (`props.options.find((o) => o.value === props.value)`). Hand it one page and
// TWO things break at once, both silently:
//
//   1. the type-ahead stops finding a jurisdiction past the page size; and
//   2. REOPENING a tax whose jurisdiction sits past the page size renders the
//      picker EMPTY — a wizard step that looks unfilled over a value that is
//      set, which is worse than the truncation because it invites a clerk to
//      re-pick and overwrite a correct answer.
//
// `tsc` sees neither. Every existing test passes over both. So the assertions
// below are about the REQUESTS the wrapper makes, not about the array it
// returns — a case that only checked the returned rows would have gone green
// against a one-page read for any fixture smaller than a page.
import { describe, expect, it } from "vitest";

import type { ApiClient } from "./client";
import { getTaxJurisdictions } from "./endpoints";
import { ListEnvelopeError } from "./paginated";

interface Recorded {
  path: string;
  query: Record<string, unknown> | undefined;
}

/** A stub client that records what was asked and replays a scripted answer.
 *  Copied in shape from `routesCyclesLists.cr029.test.ts`, which proved the
 *  identical wire change on `/routes` and `/cycles`. */
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

const jurisdiction = (name: string) => ({
  id: `j-${name}`,
  name,
  authority: `${name} authority`,
  level: "city",
  reference_no: `REF-${name}`,
});

const envelope = (rows: unknown[], count: number) => ({
  count,
  next: null,
  previous: null,
  results: rows,
});

describe("DEF-RAT-5754 · the jurisdictions read speaks the paged envelope", () => {
  it("asks for a page and hands the caller a plain array", async () => {
    const { client, calls } = stubClient([
      envelope([jurisdiction("Travis"), jurisdiction("Hays")], 2),
    ]);

    const rows = await getTaxJurisdictions(client);

    expect(rows.map((row) => row.name)).toEqual(["Travis", "Hays"]);
    expect(calls).toHaveLength(1);
    expect(calls[0].path).toBe("/tax-jurisdictions");
    // BR-SHL-011's grammar, and `per` at the top of the IS-2 vocabulary so the
    // one request is the only request for any tenant this product is built for.
    expect(calls[0].query).toMatchObject({ page: 1, per: 1000 });
  });

  it("keeps asking until it holds every row, so the S13 picker never truncates in silence", async () => {
    const first = Array.from({ length: 1000 }, (_, i) => jurisdiction(`J-${i}`));
    const second = [jurisdiction("LAST")];
    const { client, calls } = stubClient([envelope(first, 1001), envelope(second, 1001)]);

    const rows = await getTaxJurisdictions(client);

    expect(rows).toHaveLength(1001);
    // The row a one-page read would have lost — the jurisdiction a clerk could
    // no longer choose, and the label a reopened tax could no longer show.
    expect(rows[1000].name).toBe("LAST");
    expect(calls).toHaveLength(2);
    expect(calls[1].query).toMatchObject({ page: 2, per: 1000 });
  });

  it("stops when a page comes back empty rather than asking forever", async () => {
    // A server whose `count` disagrees with what it serves must not spin the
    // browser. The loop's exit is the EMPTY page, not arithmetic on `count`.
    const { client, calls } = stubClient([
      envelope([jurisdiction("Travis")], 99),
      envelope([], 99),
    ]);

    const rows = await getTaxJurisdictions(client);

    expect(rows).toHaveLength(1);
    expect(calls).toHaveLength(2);
  });

  it("serves an empty catalogue as an empty array in ONE request", async () => {
    // BR-TEN-037: a tenant that has entered no jurisdictions is a normal
    // state, not an error — the wizard's step 1 says so on screen. `{count: 0,
    // results: []}` must not read as "keep asking".
    const { client, calls } = stubClient([envelope([], 0)]);

    expect(await getTaxJurisdictions(client)).toEqual([]);
    expect(calls).toHaveLength(1);
  });

  it("throws by name when the reply is NOT the envelope, instead of reading as empty", async () => {
    // ⚠ THIS IS THE CASE THAT WOULD HAVE CAUGHT THE HALF-SHIPPED FIX.
    // The failure mode being cured is *a missing key reads as an empty list*:
    // had the backend half not landed, this wrapper would meet the OLD bare
    // array, and a helper that merely destructured `body.results` would hand
    // the picker `undefined ?? []` and render "No jurisdictions yet" over a
    // tenant that has fifty. `readListPage` asserts the shape and throws,
    // naming the path — which a person reads in the console in five seconds.
    const { client } = stubClient([[jurisdiction("Travis"), jurisdiction("Hays")]]);

    await expect(getTaxJurisdictions(client)).rejects.toBeInstanceOf(ListEnvelopeError);
  });

  it("never caps: a catalogue larger than two pages is returned whole (NFR-5)", async () => {
    const page = (n: number) =>
      envelope(
        Array.from({ length: 1000 }, (_, i) => jurisdiction(`P${n}-${i}`)),
        2500,
      );
    const { client, calls } = stubClient([
      page(1),
      page(2),
      envelope(
        Array.from({ length: 500 }, (_, i) => jurisdiction(`P3-${i}`)),
        2500,
      ),
    ]);

    const rows = await getTaxJurisdictions(client);

    expect(rows).toHaveLength(2500);
    expect(calls).toHaveLength(3);
    expect(calls[2].query).toMatchObject({ page: 3, per: 1000 });
  });
});
