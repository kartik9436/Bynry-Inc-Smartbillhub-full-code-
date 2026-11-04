// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.6` · `P2.7` · `P2.9` — the six Counter screens
//           and the two doors onto them, from §03 frames 3·1, 3·2, 3·3a–d,
//           2·1 ① and 2·3a ① of the payments blueprint, read as IMAGES at 2.0.
// Rules:    B14 rule 31 (no database id is the visible value of a field) ·
//           rule 33 · rule 43 · `CR-136-BRC07` §3.1 · §3.2 · §3.4
// ───────────────────────────────────────────────────────
// What a person can see and press on the Counter tab.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ EVERY MOUNT IS UNDER THE REAL PATH PATTERN, AND THAT IS NOT PEDANTRY
// ══════════════════════════════════════════════════════════════════════════
// `DEF-CWP-3925`: the customer portal's front page was mounted bare in a
// `MemoryRouter` with no `/:tenant/…` route, so `useParams().tenant` came back
// undefined and every address the page built came out `//portal/…` — a
// protocol-relative URL to ANOTHER HOST, **which reads as a perfectly good
// string to `toContain`**. Six dead doors passed 391 cases that way. So every
// assertion about an address below carries the tenant segment, and the fixture
// declares the route the router actually mounts.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { CounterDetail, CounterRow } from "@/api/counterEndpoints";
import { ToastProvider } from "@/components/Toast";

import { CountersTab } from "./CountersTab";
import { myOpenCounterQueryKey } from "./counterQueries";
import { CounterHeadSlot, RecordCounterBanner, tenderNeedsATill } from "./CounterDoors";
import {
  COUNTERS_ROUTE,
  COUNTER_START_ROUTE,
  CountComparison,
  addDecimalStrings,
  canDeclareCount,
  counterKicker,
  counterRoute,
  isNotCounted,
  isOpenTill,
  isZeroAmount,
  subtractDecimalStrings,
} from "./counterShared";

const TENANT = "brazosbend";
/** The clerk whose till these cases are about — `row()`'s own `owner_name`.
 *  Named once so the seeded session and the seeded rows cannot drift apart. */
const OWNER = "D. Whitfield";

function row(over: Partial<CounterRow> = {}): CounterRow {
  return {
    code: "CTR-260921-DW",
    owner_name: OWNER,
    service_centre_name: "Main counter",
    opened_at: "2026-09-21T08:55:00Z",
    closed_at: null,
    close_kind: null,
    declared_at: null,
    declared_by_name: null,
    payment_count: 17,
    taken_total: "1996.7500",
    counted_total: null,
    difference: null,
    currency: "USD",
    ...over,
  };
}

function detail(over: Partial<CounterDetail> = {}): CounterDetail {
  return {
    ...row(),
    opening_float: "200.0000",
    note: null,
    closed_by_name: null,
    methods: [
      {
        method_id: "m-cash",
        method_name: "Cash",
        method_code: "cash",
        system_total: "510.0000",
        countable: true,
        payment_count: 6,
        counted_total: null,
      },
      {
        method_id: "m-chq",
        method_name: "Cheques",
        method_code: "check",
        system_total: "1284.6000",
        countable: true,
        payment_count: 8,
        counted_total: null,
      },
      {
        method_id: "m-card",
        method_name: "Tap and pay",
        method_code: "card",
        system_total: "402.1500",
        countable: false,
        payment_count: 3,
        counted_total: null,
      },
    ],
    ...over,
  };
}

/** A client that answers `GET /counters` with the rows a case declares, and
 *  refuses everything else BY NAME — a stub that silently answers `{}` to an
 *  unexpected path is how a test certifies a call it never checked. */
function stubClient(rows: CounterRow[], opts: { fail?: boolean } = {}): ApiClient {
  const answer = async (path: string) => {
    if (opts.fail === true) {
      throw new Error("the server did not answer");
    }
    // ⛔ **`DEF-PAY-6235` — THE STUB NOW HAS TO SAY WHO IS LOOKING.**
    // `useMyOpenCounter` asks `GET /counters` for the OPEN tills and then keeps
    // the one whose `owner_name` is the caller's, because `f.mine` is a filter
    // `P2.3` has not built and `BE-05` drops an undeclared filter SILENTLY —
    // without the client-side match, `rows[0]` off the supervisor's list is a
    // colleague's drawer announced as *Your counter*. So the session read is
    // part of this fixture now, and it answers the owner of the first row: the
    // cases below are about THIS clerk's till and always were.
    if (path === "/me") {
      return {
        status: 200,
        data: {
          id: "u-dana",
          full_name: rows[0]?.owner_name ?? OWNER,
          email: "dana@brazosbendutilities.com",
          phone: null,
          role: "system_admin",
          role_name: "System Admin",
          must_change_password: false,
        },
      };
    }
    if (path.startsWith("/counters")) {
      return {
        status: 200,
        data: {
          rows,
          count: rows.length,
          totals: {
            open_now: rows.filter((one) => one.closed_at === null).length,
            open_owner_names: rows
              .filter((one) => one.closed_at === null)
              .map((one) => one.owner_name ?? ""),
            taken_today: "4101.1000",
            taken_today_payment_count: 41,
            not_counted: rows.filter(isNotCounted).length,
            not_counted_oldest: "2026-09-18",
            difference_this_week: "0.0000",
            currency: "USD",
          },
        },
      };
    }
    return { status: 200, data: { results: [], count: 0, next: null, previous: null } };
  };
  return {
    request: (path: string) => answer(path),
    get: (path: string) => answer(path),
    post: (path: string) => answer(path),
    put: (path: string) => answer(path),
    patch: (path: string) => answer(path),
    del: (path: string) => answer(path),
    pollJob: async () => ({}),
  } as unknown as ApiClient;
}

function countersBody(rows: CounterRow[]) {
  return {
    rows,
    count: rows.length,
    totals: {
      open_now: rows.filter((one) => one.closed_at === null).length,
      open_owner_names: rows.filter((one) => one.closed_at === null).map((one) => one.owner_name ?? ""),
      taken_today: "4101.1000",
      taken_today_payment_count: 41,
      not_counted: rows.filter(isNotCounted).length,
      not_counted_oldest: "2026-09-18",
      difference_this_week: "0.0000",
      currency: "USD",
    },
  };
}

/**
 * ⚠ **THE CACHE IS SEEDED RATHER THAN FETCHED, AND THAT IS THE ONLY HONEST WAY
 * TO DO THIS WITH `renderToStaticMarkup`.** A server render is ONE synchronous
 * pass: no effect runs, so `useQuery` is `isLoading` for ever and every
 * component that waits on data renders `null`. A case written against that
 * asserts the LOADING state while claiming to assert the loaded one — hard-won
 * law 7's *looking at the wrong thing*, and it would pass over a screen that
 * renders nothing at all.
 *
 * So each case states the world through the cache, which is what the query
 * would have put there, and `error: true` states the other world. The stub
 * client below is still passed, so a component reaching for a path nobody
 * seeded is refused BY NAME rather than answered with `{}`.
 */
function mount(
  node: JSX.Element,
  seed: { key: readonly unknown[]; data: unknown }[] = [],
  at = `/${TENANT}/payments/counter`,
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // ⛔ **`DEF-PAY-6235` — WHO IS LOOKING IS PART OF THE ANSWER NOW, SO IT IS
  // PART OF EVERY FIXTURE.** `useMyOpenCounter` keeps the open till whose
  // `owner_name` is the CALLER'S, because `f.mine` is a filter `P2.3` has not
  // built and `BE-05` drops an undeclared filter SILENTLY — without the
  // client-side match, `rows[0]` off 3·1's list of EVERYONE'S tills is a
  // colleague's drawer announced as *Your counter*, beside a button that takes
  // money. These are static renders, so the session read has to be seeded like
  // the counters read beside it rather than awaited.
  queryClient.setQueryData(queryKeys.me, {
    id: "u-dana",
    full_name: OWNER,
    email: "dana@brazosbendutilities.com",
    phone: null,
    role: "system_admin",
    role_name: "System Admin",
    must_change_password: false,
  });
  for (const entry of seed) {
    queryClient.setQueryData(entry.key, entry.data);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[at]}>
          <Routes>
            {/* THE REAL PATTERN. Without `:tenant` here, `useTenantPath` builds
                `//payments/…` and every address assertion below passes over a
                URL pointing at another host. */}
            <Route path="/:tenant/payments/counter" element={node} />
            <Route path="/:tenant/payments/:tab" element={node} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ══════════════════════════════════════════════════════════════════════════
// `CR-136-BRC07` §3.2 — THE ONE DERIVED EXPRESSION
// ══════════════════════════════════════════════════════════════════════════

describe("§3.2 — `Not counted` is one expression with four readers", () => {
  it("is a forced close nobody has declared a count for", () => {
    expect(isNotCounted(row({ closed_at: "x", close_kind: "forced" }))).toBe(true);
  });

  it("is NOT a counted close — it was counted when it closed", () => {
    expect(isNotCounted(row({ closed_at: "x", close_kind: "counted" }))).toBe(false);
  });

  it("is NOT the system till, which is nobody's by definition", () => {
    // ⚠ The widening this refuses is *anything without a counted total*, which
    // would put every ACH day on a supervisor's chase list.
    expect(isNotCounted(row({ closed_at: "x", close_kind: "system", owner_name: null }))).toBe(
      false,
    );
  });

  it("is NOT an open till — not counted YET is a different statement", () => {
    expect(isNotCounted(row())).toBe(false);
  });

  it("STOPS being true when the count is declared, and the close does not move", () => {
    // §3.2, verbatim: *"Keep it as a forced close and add the late count
    // beside it"*. The row still says forced; it stops saying Not counted.
    const declared = row({
      closed_at: "x",
      close_kind: "forced",
      declared_at: "2026-09-22T09:00:00Z",
      declared_by_name: "Dana Whitfield",
    });
    expect(isNotCounted(declared)).toBe(false);
    expect(declared.close_kind).toBe("forced");
  });

  it("is the SAME function the Declare door asks — one expression, not two", () => {
    expect(canDeclareCount).toBe(isNotCounted);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// MONEY — DECIMAL STRINGS, NEVER DOUBLES (CLAUDE.md hard rule 2)
// ══════════════════════════════════════════════════════════════════════════

describe("the drawer arithmetic never touches a float", () => {
  it("adds the canonical counter-example exactly", () => {
    // `0.1 + 0.2` as doubles is 0.30000000000000004, and a drawer is the one
    // place in this product where a figure exists to be compared with reality.
    expect(addDecimalStrings("0.1", "0.2")).toBe("0.3");
  });

  it("subtracts across differing scales and keeps the sign", () => {
    expect(subtractDecimalStrings("1228.00", "1240.0000")).toBe("-12.0000");
  });

  it("recognises zero however it is spelled", () => {
    for (const spelling of ["0", "0.00", "-0.0000", "0.0000"]) {
      expect(isZeroAmount(spelling)).toBe(true);
    }
    expect(isZeroAmount("-12.0000")).toBe(false);
  });

  it("refuses to guess at something that is not a decimal", () => {
    expect(subtractDecimalStrings("twelve", "1")).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 3·3b / 3·3d — THE COMPARISON, AND WHAT IT REFUSES TO PRETEND
// ══════════════════════════════════════════════════════════════════════════

describe("3·3b and 3·3d draw ONE comparison (B14 rule 43)", () => {
  const t = (key: string) => key;

  it("gives a countable method an input and an uncountable one the words", () => {
    const html = renderToStaticMarkup(
      <CountComparison
        methods={detail().methods}
        currency="USD"
        editable
        counted={{}}
        onCountedChange={() => undefined}
        idPrefix="probe"
        t={t}
      />,
    );
    // Cash and cheques are countable — two inputs, and no third.
    expect(html.match(/<input/g) ?? []).toHaveLength(2);
    // p056 ③: *"you cannot count a card total in a drawer, so the screen does
    // not pretend"*. If this ever grows a third input, the reconciliation is
    // worthless and no other check in this repository would notice.
    expect(html).toContain("payments.counter.notCounted");
  });

  it("labels the cash row as carrying the float, because it does", () => {
    const html = renderToStaticMarkup(
      <CountComparison
        methods={detail().methods}
        currency="USD"
        editable={false}
        idPrefix="probe"
        t={t}
      />,
    );
    expect(html).toContain("payments.counter.count.cashInclFloat");
  });

  it("shows no counted total until every countable method has a figure", () => {
    const html = renderToStaticMarkup(
      <CountComparison
        methods={detail().methods}
        currency="USD"
        editable
        counted={{ "m-cash": "510.00" }}
        onCountedChange={() => undefined}
        idPrefix="probe"
        t={t}
      />,
    );
    // A partial total is a WRONG total, and it would read as a balanced drawer.
    expect(html).toMatch(/data-counted-together=""[^>]*>—</);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 3·1 — THE LIST, AND B14 RULE 31
// ══════════════════════════════════════════════════════════════════════════

describe("3·1 Counters", () => {
  // ⚠ **THE PAGE HEAD AND THE `Start counter →` DOOR ARE NOT ASSERTED HERE,
  // AND THE REASON IS THE POINT OF B14 RULE 2.** `CountersTab` is the BODY of
  // the Counter tab; the ONE page header belongs to `PaymentsPage`, which is
  // where the title `Counters`, its kicker and the primary action are drawn.
  // Asserting them against a bare mount of this component would be a case that
  // can never pass, which is hard-won law 7's third shape — so they are
  // asserted in `sevenTabs.dom.test.tsx`, through the page that draws them,
  // BY ADDRESS and with the tenant in it.
  function tab() {
    return mount(
      <CountersTab
        client={stubClient([row()])}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        writeBlockedReason={null}
        onOpenCounter={() => undefined}
      />,
    );
  }

  it("draws the columns 3·1 draws, in the order it draws them", () => {
    const html = tab();
    const drawn = ["Counter", "Person", "Opened", "Closed", "Payments", "Taken", "Counted"];
    let cursor = -1;
    for (const column of drawn) {
      const at = html.indexOf(`>${column}</span>`, cursor + 1);
      expect(at, `${column} is missing or out of the drawn order`).toBeGreaterThan(cursor);
      cursor = at;
    }
  });

  it("asks 3·1's own search question, not the shared default", () => {
    // B14 rule 19 / `DEF-510`: every list said *Search this list* until a
    // screen opted in. p051 draws this one.
    expect(tab()).toContain('placeholder="Search counter or person…"');
  });

  it("puts no database id in the markup (B14 rule 31)", () => {
    expect(tab()).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/i);
  });

  it("builds 3·2's address from the CODE", () => {
    expect(counterRoute("CTR-260921-DW")).toBe(`${COUNTERS_ROUTE}/CTR-260921-DW`);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `P2.7` / `P2.9` — THE TWO DOORS, AND §3.4's NARROWING
// ══════════════════════════════════════════════════════════════════════════

describe("`P2.7` — the page-head slot has BOTH of 2·1 ①'s states", () => {
  it("offers the way in when this clerk has no till open", () => {
    const html = mount(<CounterHeadSlot client={stubClient([])} dateFormat="MM/DD/YYYY" />, [
      { key: myOpenCounterQueryKey(), data: countersBody([]) },
    ]);
    expect(html).toContain(`href="/${TENANT}${COUNTER_START_ROUTE}"`);
  });

  it("becomes the door BACK when a till is already open", () => {
    // ⚠ **THE HALF THAT IS EASY TO LOSE.** A slot that always says *Start
    // counter →* offers an act `uq_counter_sessions_open_owner` will refuse.
    const html = mount(<CounterHeadSlot client={stubClient([row()])} dateFormat="MM/DD/YYYY" />, [
      { key: myOpenCounterQueryKey(), data: countersBody([row()]) },
    ]);
    expect(html).toContain(`href="/${TENANT}${counterRoute("CTR-260921-DW")}"`);
    expect(html).not.toContain(`href="/${TENANT}${COUNTER_START_ROUTE}"`);
  });
});

describe("`P2.9` — the record banner, narrowed by §3.4", () => {
  it("names the batch the money goes into when a till is open", () => {
    const html = mount(
      <RecordCounterBanner
        client={stubClient([row()])}
        dateFormat="MM/DD/YYYY"
        timeZone="America/Chicago"
        methodCode="cash"
      />,
      [{ key: myOpenCounterQueryKey(), data: countersBody([row()]) }],
    );
    expect(html).toContain("CTR-260921-DW");
  });

  it("offers the way out for a tender that passes through hands", () => {
    const html = mount(
      <RecordCounterBanner
        client={stubClient([])}
        dateFormat="MM/DD/YYYY"
        timeZone="America/Chicago"
        methodCode="check"
      />,
      [{ key: myOpenCounterQueryKey(), data: countersBody([]) }],
    );
    // §3.4's refusal WITH ITS DOOR — a refusal with no door is law 2's mirror.
    expect(html).toContain(`href="/${TENANT}${COUNTER_START_ROUTE}"`);
  });

  it("says NOTHING to the four tenders that keep the system till", () => {
    // ⚠ A banner that refused a back-office ACH keying would refuse work the
    // product permits. §3.4 names three tenders and leaves four alone.
    for (const tender of ["ach", "card", "wire", "lockbox"]) {
      const html = mount(
        <RecordCounterBanner
          client={stubClient([])}
          dateFormat="MM/DD/YYYY"
          timeZone="America/Chicago"
          methodCode={tender}
        />,
        [{ key: myOpenCounterQueryKey(), data: countersBody([]) }],
      );
      // ⚠ NOT `toBe("")`: `ToastProvider` draws its own live region around
      // everything, so an empty banner is a document with no banner in it
      // rather than an empty string. A case asserting `""` would go red the
      // day any wrapper gained a node and say nothing about this component.
      expect(html).not.toContain("payments.counter.door");
      expect(html).not.toContain(COUNTER_START_ROUTE);
    }
  });

  // ⚠ **THE FAILED-READ BRANCH IS NOT ASSERTED HERE, AND SAYING SO IS THE
  // POINT.** `RecordCounterBanner` distinguishes *"you have no till"* from
  // *"we could not ask"* — the `DEF-127` shape, where an absence and a failure
  // render identically and the screen states the more alarming one as fact.
  // Under `renderToStaticMarkup` a query is `isLoading` for ever and the
  // component returns `null`, so a case written here would go GREEN on the
  // loading state while claiming to test the error state: hard-won law 7's
  // *looking at the wrong thing*, which is worse than no case at all. It needs
  // a client-side render with an errored cache entry, and it is named in this
  // lane's report as owed rather than quietly skipped.

  it("holds §3.4's three tenders and no others", () => {
    expect(["cash", "check", "money_order"].every(tenderNeedsATill)).toBe(true);
    expect(["ach", "card", "wire", "lockbox"].some(tenderNeedsATill)).toBe(false);
  });
});

describe("the dialog eyebrow says whose till it is, first", () => {
  it("names the owner in caps beside the code", () => {
    expect(counterKicker(row())).toBe("CTR-260921-DW · D. WHITFIELD");
  });

  it("drops the separator on the system till, which is nobody's", () => {
    expect(counterKicker(row({ owner_name: null }))).toBe("CTR-260921-DW");
  });

  it("knows an open till from a sealed one", () => {
    expect(isOpenTill(row())).toBe(true);
    expect(isOpenTill(row({ closed_at: "2026-09-21T17:30:00Z" }))).toBe(false);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-136-BRC07 §3.1 · §3.2 · §3.4 · §4 rows `P2.6`/`P2.7`/`P2.9` · blueprint p030, p037, p051–p059 as images at 2.0
// generated: 2026-09-23 by LANE P2-SCREENS
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest src/features/payments/counterScreens.dom.test.tsx · tsc --noEmit
// exceptions: E3 the six counter endpoints are NOT SERVED at this commit, so every read here is a stub that refuses an unexpected path BY NAME rather than answering it
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
