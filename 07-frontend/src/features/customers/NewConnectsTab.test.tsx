// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W6 task 6.12 — S86 `NCT-01`, the FRONTEND half's cases.
//           Written against B18 §5.4.1/§5.4.2/§5.4.8/§5.4.9, which declared
//           them before this code existed (r11 step 2c: test code is written
//           for the cases §3 already declares, never authored to match the
//           code).
// Rules:    OQ-371 (OPEN — the segment strip) · CR-032 (`activated`, not
//           `energised`) · BR-SHL-025 (disabled WITH the reason) · hard-won
//           law 2 (built is not wired — the first case below is that assertion)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE FIRST CASE IS THE DEFECT THIS LANE EXISTS TO FIX, AND IT IS ASSERTED
// ON THE WIRE.** The PO's report was *"nothing on new connect + on all of these
// screens"*: the read model was finished, `GET /connections` was mounted, and
// NOTHING CALLED IT — `connection_reads.py`'s own trailer said so. A test that
// only rendered a seeded payload would pass over exactly that defect, so this
// file records the URLs the component actually requested and asserts one of
// them is `/connections`.
//
// ⚠ **AND THE SEGMENT CASE ASSERTS AN ABSENCE ON THE WIRE TOO.** OQ-371 is
// open, the server refuses every segment but `all`, and the rule this screen
// obeys is *never call the route to discover it fails* — so the assertion is
// that no request carries a `segment=` parameter at all, which a rendered
// string cannot show.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import { defaultRequestState, defaultVisibleColumns } from "@/components/tableTypes";
import { internalReferencesInMarkup } from "@/testSupport/internalReferences";
import { APP_ROUTES } from "@/App";

import {
  NEW_CONNECTS_PARAM_PREFIX,
  NewConnectsTab,
  OrdersCell,
  ServicesCell,
  connectionFilterGroups,
  connectionStateTone,
  connectionsQueryKey,
  newConnectsKpis,
  newConnectsTableConfig,
  newConnectsTiles,
  rowDoor,
} from "./NewConnectsTab";
import {
  ACTS_DECIDED_BY_STATE_ALONE,
  BUILD_ROW_ACTS,
  BuildBulkBar,
  eligibleForAct,
  pressTile,
  rowBuildFacts,
} from "./newConnectListViews";
import { listConnections } from "./worklistEndpoints";
import type { ConnectionList, ConnectionRow } from "./worklistEndpoints";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const CONFIG = newConnectsTableConfig(t, {
  select: () => <span />,
  connection: () => <span />,
  premise: () => <span />,
  // `DEF-CUS-7804` — the three cells the tab hands down. They are stubbed here
  // because this constant exists to assert the COLUMN SET; each cell has its
  // own case below, rendered for real.
  customer: () => <span />,
  charged: () => <span />,
  lastEvent: () => <span />,
  services: () => <span />,
  orders: () => <span />,
  target: () => <span />,
  state: () => <span />,
  actions: () => <span />,
});

/** The refusal `apps/metering/api.py` serves on EVERY response, verbatim. */
const SEGMENTS_NOT_DECIDED = {
  code: "segments_not_decided",
  br_ref: "OQ-371 (OPEN) · B18 §5.4.2 · §5.4.9 NCT-01",
  tracks: "OQ-371",
  segments: ["in_progress", "waiting", "partly_activated", "done"],
  detail:
    "Every new connect is listed together for now. The In progress, Waiting, " +
    "Partly activated and Done tabs are switched off because a build can be " +
    "part-way through AND waiting on somebody at the same time, and which of " +
    "those two tabs should hold it has not been decided yet. Filtering them " +
    "on a guess would hide a build rather than show it in the wrong place.",
};

/** §5.4.9's own drawn rows. `CON-26-0117` is the one that exercises every
 *  interesting cell at once: 25 units, five services behind a `+1` chip,
 *  `5 of 7` orders, waiting on inspection, and `partly_activated`. */
function row(over: Partial<ConnectionRow> = {}): ConnectionRow {
  return {
    id: "con-0117",
    connection_no: "CON-26-0117",
    premises: {
      id: "prm-500",
      premise_no: "P-000500",
      name: "Main Street Block",
      address: "500 Main Street",
    },
    // CR-070 wave O — where the eye GOES. This build's home is its premises
    // because no owner account was named on it; `owner_account_id` is OPTIONAL.
    // ⚠ **This comment said "nothing fills it (`OQ-373`)" until 2026-09-12
    // (`DEF-MET-5081`) — `create_owner_account()` fills it, since 2026-08-25.**
    home: { kind: "premises", id: "prm-500" },
    units: 25,
    services: ["electric", "water", "sewer", "trash", "gas"],
    orders: { done: 5, total: 7 },
    target_activation: "2026-09-30",
    waiting_on: "inspection",
    state: "partly_activated",
    request_no: "SR-26-0018",
    applicant: "Rodriguez, M.",
    ...over,
  };
}

function payload(over: Partial<ConnectionList> = {}): ConnectionList {
  return {
    count: 8,
    next: null,
    previous: null,
    results: [row()],
    // §5.4.1's five drawn figures, plus the two `00-list.png` adds
    // (`DEF-CUS-7804`). `connection_reads._kpis` serves all seven.
    kpis: {
      open: 7,
      waiting_on_inspection: 2,
      partly_activated: 3,
      units_awaiting_activation: 42,
      oldest: { days: 19, connection_no: "CON-26-0119", waiting_on: "permit" },
      // Every open build with ANY `waiting_on`, not the one literal above.
      waiting_on_anyone: 3,
      // ⛔ `DEF-CUS-7619` — exactly one of the two is ever set, and today it
      // is always the reason. `OWED_ON_OPEN_BUILDS_UNAVAILABLE`, verbatim.
      owed_on_open_builds: null,
      owed_on_open_builds_unavailable: {
        code: "billing_publishes_no_batched_invoice_position",
        tracks: "DEF-CUS-7619",
        detail:
          "What each build still owes is held on its bill, and the bills cannot be read a " +
          "page at a time yet. No total is shown, and nothing says these builds are paid for.",
      },
    },
    segment: "all",
    unavailable: [SEGMENTS_NOT_DECIDED],
    // CR-045 wave D · D.11 — `connection_reads` serves BOTH on every response,
    // and they answer different questions. `unavailable[].segments` is the four
    // drawn tabs nobody has ranked (OQ-371); `states` is `OPEN_STATES`, the
    // stored states `f.state` accepts. The panel reads the second.
    filters: ["state"],
    states: [
      { code: "draft" },
      { code: "requested" },
      { code: "in_progress" },
      { code: "partly_activated" },
      { code: "on_hold" },
    ],
    ...over,
  };
}

interface Render {
  html: string;
  urls: string[];
}

/**
 * CR-045 wave G · `DEF-1702` — the tab rendered with `state.filters` set.
 *
 * ⚠ **THE URL IS THE ASSERTION AND THE ROW COUNT IS NOT.** `/connections` is
 * PAGED: it answers one window plus a `total`. A case that set a filter and
 * counted rendered rows would pass on a screen that narrowed the page in hand —
 * a subset of a subset under an authoritative-looking total, which is worse
 * than no control at all and is exactly the shape `DEF-1702` is about.
 */
async function renderTab(
  body: ConnectionList | "unreadable",
  filters: Record<string, string> = {},
): Promise<Render> {
  const urls: string[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input) => {
      urls.push(String(input));
      return body === "unreadable"
        ? new Response(JSON.stringify({ detail: "boom" }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          })
        : new Response(JSON.stringify(body), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = { ...defaultRequestState(CONFIG), filters };
  // ⚠ **THE FILTER GOES IN THE ADDRESS AS WELL AS INTO THE PREFETCH
  // (`CR-150-BRC09`).** This tab reads its state from the URL under its own
  // `nc.` namespace (`DEF-CUS-6099`), so a case that seeded only the query
  // cache was rendering an UNFILTERED screen and asserting the REQUEST. That
  // is enough for *does the filter leave the browser* and it cannot see
  // whether the toolbar says so — which is exactly what task 16 turns on.
  const address = new URLSearchParams({ tab: "new-connects" });
  for (const [name, value] of Object.entries(filters)) {
    if (value !== "") {
      address.set(`${NEW_CONNECTS_PARAM_PREFIX}f.${name}`, value);
    }
  }
  try {
    await queryClient.prefetchQuery({
      queryKey: connectionsQueryKey(state),
      queryFn: () =>
        listConnections(
          { q: state.q, page: state.page, per: state.per, filters: state.filters },
          client,
        ),
    });
  } catch {
    // An unreadable payload is one of the cases under test.
  }
  const html = renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?${address.toString()}`]}>
        <NewConnectsTab client={client} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { html, urls };
}

describe("S86 · NCT-01, the New connects tab (CR-030 W6 task 6.12)", () => {
  it("law 2 — the tab CALLS `GET /connections`; the endpoint is not merely wired in a comment", async () => {
    const { urls } = await renderTab(payload());
    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain("/connections");
    // The tenant travels in the PATH (BR-TEN-003, PO 2026-08-10), which is what
    // makes this a real call and not a same-origin guess.
    expect(urls[0]).toContain(TEST_TENANT);
  });

  it("§5.4.2 — the eight drawn columns render the drawn row", async () => {
    const { html } = await renderTab(payload());
    expect(html).toContain("CON-26-0117");
    expect(html).toContain("500 Main Street");
    // UNITS — the metric that makes a 25-unit job visible as 25 units of risk
    // rather than one row (§5.4.1).
    expect(html).toContain(">25<");
    // ORDERS is a FRACTION. §5.4.2: *"not a percentage, not a bar alone. The
    // fraction is readable; a bar is not."*
    expect(html).toContain('data-orders="5/7"');
    expect(html).toContain("5 of 7");
    // ⚠ THE PERCENTAGE EXISTS AND IS NOT TEXT, which is the whole of the rule.
    // `width:71%` is the underline BENEATH the fraction; what §5.4.2 forbids is
    // a percentage a person READS, so the assertion is on rendered text and not
    // on the raw string — an earlier draft asserted the raw string and went red
    // on the bar the design asks for.
    expect(html).not.toMatch(/>[^<]*71%[^<]*</);
    expect(html).toContain("inspection");
  });

  // ── CR-045 wave G · B14 RULE 12 · THE `+ Filter ▾` PANEL IS ON THE TOOLBAR
  //    ROW, AND THE SEGMENT STRIP THAT USED TO BE HERE IS GONE (`DEF-1702`) ──
  //
  // ⚠ **WHAT THESE TWO CASES REPLACED, AND WHY THE REPLACEMENT IS STRICTER.**
  // One asserted that `WorklistSegments` rendered inside `.table-toolbar`; the
  // other that five segments were drawn with four DISABLED carrying the
  // server's sentence. Both were true, both were carefully built to go RED on
  // the thing they watched — and **both were GREEN on a screen with no filter
  // control at all.** The strip's `onSelect` was `() => undefined`, so every
  // assertion about its enabled-ness held over a control that could not narrow
  // anything. That is how this screen was counted as *having* a filter twice
  // while having none. The order check is kept and pointed at the control that
  // now does the job; the disabled-segment check is replaced by its own
  // negation, so re-adding the dead strip goes RED.
  it("B14 rule 12 — the `+ Filter` panel renders INSIDE the shared toolbar row", async () => {
    const { html } = await renderTab(payload());
    const toolbar = html.indexOf("table-toolbar");
    const panel = html.indexOf("+ Filter");
    const table = html.indexOf("<table");
    expect(toolbar).toBeGreaterThan(-1);
    expect(panel).toBeGreaterThan(-1);
    expect(table).toBeGreaterThan(-1);
    expect(toolbar).toBeLessThan(panel);
    expect(panel).toBeLessThan(table);
  });

  it("⛔ `DEF-1702` — the INERT segment strip is gone; nothing here renders a control that ignores clicks", async () => {
    const { html } = await renderTab(payload());
    // `WorklistSegments` emitted both markers and nothing else did. Asserting
    // the MARKERS rather than the segment WORDS is deliberate: `Waiting` and
    // `In progress` are also STATE-cell and filter-option words on this screen,
    // so a word-based negative would fail on chrome that has nothing to do with
    // the strip. (It did, on the S90 sibling case, before this note was written.)
    expect(html).not.toContain("data-worklist-segments");
    expect(html).not.toContain("data-segment=");
  });

  it("⛔ OQ-371 is UNTOUCHED — the refusal still travels on the payload and the route is still never asked", async () => {
    const { urls } = await renderTab(payload());
    // The screen no longer DRAWS the four tabs; it also never asks for one. A
    // request carrying `segment=` would meet `NotImplementedError("OQ-371")`
    // translated into a refusal and empty the tab — the "call the route to find
    // out" `unavailable` exists to prevent.
    expect(urls[0]).not.toContain("segment=");
  });

  it("CR-032 — the tab says `activated`, and the word `energis` appears nowhere on it", async () => {
    const { html } = await renderTab(payload());
    // PO 2026-08-25: *"instead of energise can we use activated"*. B18 still
    // DRAWS "Partly energised" and is stamped; the product ships the ruling.
    expect(html).toContain("Partly activated");
    expect(html.toLowerCase()).not.toContain("energis");
  });

  it("§5.4.1 — OLDEST states there is none rather than printing `0 days`", async () => {
    const { html } = await renderTab(payload({ kpis: { ...payload().kpis, oldest: null } }));
    // A tenant with no open build has NO oldest one. "0 days" is a different
    // claim from "there is none" — the same judgment DEF-127 was filed for on a
    // money figure.
    expect(html).toContain("None open");
    expect(html).not.toContain("0 days");
  });

  it("§5.4.1's five figures reach the strip, and so do the drawing's two (DEF-CUS-7804)", async () => {
    // ⚠ **THIS CASE ASSERTED FIVE UNTIL 2026-09-29 AND THE STRIP HOLDS
    // SEVEN.** `waiting_on_anyone` and the owed tile's stated absence were
    // served by `01580d8fc` and read by nothing. The two the drawing DROPPED
    // — `Waiting on inspection` and `Oldest` — are still here, still live and
    // still served, which is `DEF-CUS-7805` and is a product judgment rather
    // than this lane's to take.
    const tiles = newConnectsKpis(payload(), t);
    expect(tiles.map((tile) => tile.id)).toEqual([
      "open",
      "waiting-anyone",
      "waiting-inspection",
      "partly-activated",
      "units-awaiting",
      "oldest",
      "owed",
    ]);
    const values = tiles.map((tile) => ("value" in tile ? tile.value : null));
    expect(values.slice(0, 6)).toEqual([7, 3, 2, 3, 42, "19 days"]);
    // ⛔ THE OWED TILE IS A NODE AND NOT A FIGURE, WHICH IS THE ASSERTION.
    // `DEF-CUS-7619` — there is no total, so the tile carries the stated
    // absence and never a number. A `toEqual` over a rendered string could
    // not tell `"0.00"` from a real zero; this asks what the tile IS.
    expect(typeof values[6]).not.toBe("number");
    expect(renderToStaticMarkup(<>{values[6]}</>)).toContain("No total yet");
    expect(renderToStaticMarkup(<>{values[6]}</>)).toContain(
      "billing_publishes_no_batched_invoice_position",
    );
    // ⚠ The caption is the DESIGN's and the figure is the SERVER's, and
    // `connection_reads` §2 measured that they do not quite agree: 42 is every
    // unit of an open build, including ones already live. The tile prints both
    // as served — reconciling them here would invent the split.
    //
    // ⚠ **FOUND BY ID AND NOT BY POSITION**, because this line read
    // `tiles[3]` and the two new tiles moved that index onto a different
    // tile — a case still passing while asserting about something else is
    // hard-won law 7's *looking at the wrong thing*.
    expect(tiles.find((tile) => tile.id === "units-awaiting")?.detail).toContain("7");
  });

  it("§5.4.9 — SERVICES shows four badges and a `+1` overflow chip", () => {
    const html = renderToStaticMarkup(
      <ServicesCell services={["electric", "water", "sewer", "trash", "gas"]} t={t} />,
    );
    expect(html).toContain('data-services-overflow="1"');
    // Four is READ OFF THE DRAWING (`E W S T +1`), not chosen.
    expect(html).toContain("+1");
  });

  it("ORDERS draws a fraction over an underline, and a build with no orders draws no full bar", () => {
    const empty = renderToStaticMarkup(
      <OrdersCell row={row({ orders: { done: 0, total: 0 } })} t={t} />,
    );
    // Zero of zero is not complete.
    expect(empty).toContain("width:0%");
    const part = renderToStaticMarkup(<OrdersCell row={row()} t={t} />);
    expect(part).toContain('data-orders="5/7"');
  });

  // ⚠ **THIS CASE USED TO ASSERT THE OPPOSITE, AND THAT IS DEF-730.** It read
  // *"the empty state's CTA is DISABLED with its reason, not a button onto
  // nothing"* and expected the string `not built yet`. It was TRUE the day it
  // was written and it went FALSE the same night, when `NewConnectWizard`
  // landed at `/connections/new` — 1,610 lines, nine steps, routed. From then
  // on the product refused an action it could perform and told the user a
  // falsehood about itself, and this case HELD THE FALSEHOOD IN PLACE: it was
  // green, and going green was the bug. Hard-won law 1, in a test file.
  it("DEF-730 — the empty state's CTA is LIVE, and the `not built yet` sentence is gone from the tab", async () => {
    const { html } = await renderTab(payload({ count: 0, results: [] }));
    expect(html).toContain("No new connects yet");
    // The refusal is gone, not reworded.
    expect(html).not.toContain("not built yet");
    // …and the control it guarded is LIVE. `EmptyList` renders a disabled
    // `<Button title={ctaReason}>` when the CTA is blocked and a live one with
    // an `onClick` when it is not, so `disabled=""` on THAT TAG is the whole
    // difference. It is asserted as `disabled=""` and never as the substring
    // "disabled", which every button in the kit carries in
    // `disabled:opacity-45` — the loose form is true of a live button and could
    // not go red.
    const cta = /<button[^>]*>\+ New connect<\/button>/.exec(html)?.[0] ?? "";
    expect(cta).not.toBe("");
    expect(cta).not.toContain('disabled=""');
  });

  it("DEF-730 · CR-151-BRC09 §6a — a ROW's eye opens the BUILD, at its own address", async () => {
    const { html } = await renderTab(payload());
    // ⚠ **RE-POINTED TWICE, AND THIS IS THE SECOND TIME.** `DEF-730` put the
    // eye on the row; `CR-070` wave O then sent it to the build's HOST, because
    // the PO had ruled the build's own screen one destination too many and the
    // address had become a redirect. `CR-151-BRC09` (PO 2026-09-28) reverses
    // that first clause: the build has its own page again, at the address it
    // always had, and `App.tsx` mounts `BuildDetailPage` there.
    expect(html).toContain(`href="/${TEST_TENANT}/connections/con-0117"`);
    // The HOST destination, asserted ABSENT by name — a row that offered both
    // would be the duplicate door this flip removes, and a lane re-pointing at
    // the host turns this red rather than adding a second quietly.
    expect(html).not.toContain(`href="/${TEST_TENANT}/premises/prm-500?tab=build"`);
    // B14 rule 15 / G37 — an ICON with an accessible NAME, never a text link.
    expect(html).toContain('aria-label="Open this connection"');
    expect(html).not.toContain(">Open this connection<");
  });

  it("a build with no target renders a dash and is not given a date", async () => {
    const { html } = await renderTab(payload({ results: [row({ target_activation: null })] }));
    expect(html).toContain("—");
    expect(html).not.toContain("2026-09-30");
  });

  it("the filter panel offers NOTHING before the first response, and the SERVER's states after it", () => {
    // Before a response the screen does not know which states this tenant's
    // list holds. An empty group is DROPPED by `offerableFilters` rather than
    // drawn as a legend over nothing (`DEF-782`).
    expect(connectionFilterGroups(undefined, t)[0].options).toEqual([]);
    const served = connectionFilterGroups([{ code: "on_hold" }, { code: "requested" }], t)[0];
    expect(served.name).toBe("state");
    expect(served.options.map((option) => option.value)).toEqual(["on_hold", "requested"]);
    // ⚠ **NOT the drawn SEGMENTS.** `waiting` and `done` are segment codes
    // derived from `waiting_on` and from being off the list; offering either
    // here would be answering OQ-371 by rendering.
    expect(served.options.map((option) => option.value)).not.toContain("waiting");
    expect(served.options.map((option) => option.value)).not.toContain("done");
    // ⛔ **THIS CASE USED TO ASSERT `"zz_new"` — THE DEFECT ENCODED AS THE
    // CONTRACT (`DEF-CUS-6098`).** It read *"an unknown code renders as ITSELF
    // — never blank, never a raw key"*, on the reasoning that a code is ugly
    // and visible. **A code on screen is not ugly-and-visible; it is
    // invisible**, because it looks deliberate and is never blank — which is
    // exactly how `in_progress_draft` and `parked` sat in this panel beside
    // eight translated words for as long as the two codes have existed.
    //
    // It is the same correction `disconnectStateLabels.test.ts` records about
    // its own predecessor, made for the same reason one tab over.
    const said: string[] = [];
    const real = console.error;
    console.error = (...args: unknown[]) => void said.push(String(args[0]));
    let unknown: string;
    try {
      unknown = connectionFilterGroups([{ code: "zz_new" }], t)[0].options[0].label;
    } finally {
      console.error = real;
    }
    expect(unknown).not.toBe("zz_new");
    expect(unknown).toBe("Not named yet");
    // The LOUD half, asserted rather than assumed: a guard nobody hears is a
    // guard that is not there (CLAUDE.md law 7).
    expect(said.join(" ")).toContain("zz_new");
    // And the two the server really does mint read as WORDS.
    const minted = connectionFilterGroups(
      [{ code: "in_progress_draft", label: "Draft" }, { code: "parked", label: "Parked" }],
      t,
    )[0];
    expect(minted.options.map((option) => option.label)).toEqual(["Draft", "Parked"]);
  });

  it("CR-045 wave G — `f.state` LEAVES THE BROWSER, which is the only thing that makes this a filter", async () => {
    const { urls } = await renderTab(payload(), { state: "partly_activated" });
    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain("f.state=partly_activated");
    // BR-SHL-011's grammar, not a bare `?state=` the route would drop.
    expect(urls[0]).not.toMatch(/[?&]state=partly_activated/);
  });

  it("an EMPTY filter value is an ABSENT dimension, never `f.state=`", async () => {
    const { urls } = await renderTab(payload(), { state: "" });
    expect(urls[0]).not.toContain("f.state");
  });

  it("the query key carries the filters, or the filtered request reads the unfiltered cache", () => {
    const base = defaultRequestState(CONFIG);
    expect([...connectionsQueryKey(base)]).not.toEqual([
      ...connectionsQueryKey({ ...base, filters: { state: "on_hold" } }),
    ]);
  });

  it("the STATE tone is the screen's and decides nothing about OQ-371", () => {
    expect(connectionStateTone("activated")).toBe("success");
    expect(connectionStateTone("partly_activated")).toBe("warning");
    expect(connectionStateTone("requested")).toBe("neutral");
  });

  it("a failed read never renders the empty state — that would assert 'you have none'", async () => {
    const { html } = await renderTab("unreadable");
    // ⚠ **WHAT THIS HARNESS CAN AND CANNOT SEE, MEASURED HERE AND NOT ASSUMED**
    // — the same finding `ServiceRequestsListPage.test.tsx` and
    // `AccountUsageTab.test.tsx` already record. `renderToStaticMarkup` runs no
    // effects, and TanStack Query's `retryOnMount` makes an ERRORED cache entry
    // report `status: "pending"` on first paint (probed directly: cache
    // `error`, render `status=pending pending=true error=false`). So the
    // POSITIVE assertion — the failure line and its Retry appear — belongs to
    // the browser walkthrough, and what is provable here is the negative that
    // actually matters: a list that could not be READ must never draw the
    // shared empty state, because that state asserts *"you have none"* about
    // builds we simply failed to fetch.
    expect(html).not.toContain("No new connects yet");
  });

  /**
   * ⚠ **G27 IS RED ON THIS FILE BY CONSTRUCTION, AND THIS IS THE ASSERTION THAT
   * SAYS WHAT THAT RED DOES AND DOES NOT MEAN.**
   *
   * G27 exists because the PO photographed a deployed panel whose heading read
   * `notifications.rights.title` — a screen rendering its own source code. It
   * finds every LITERAL `t("some.key")` whose key no catalogue defines, and it
   * reports 21 of them here, because a lane may not write the shared
   * catalogues and this tab's keys are handed over rather than merged.
   *
   * **What G27 cannot see is `defaultValue`.** Every call site in this tab
   * supplies one, so nothing renders a dotted key at a person — which is the
   * harm G27's own message claims. This case is the proof, and it is the thing
   * that must go red if a future edit drops a `defaultValue`: a key with no
   * fallback and no catalogue entry renders itself.
   *
   * **A DEFECT IS OWED ON THE GATE, not on this file:** G27's message says
   * *"Each renders its own key name to a user"*, and for a call site carrying a
   * `defaultValue` that sentence is false. Its own header already records the
   * correct rule for dynamic keys — *"most such call sites already pass a
   * `defaultValue`, which is the correct pattern"* — and the same reasoning
   * applies to a literal one.
   */
  it("no raw translation key reaches the screen — every call site carries a defaultValue", async () => {
    const { html } = await renderTab(payload());
    // The families this tab names. A miss renders as the dotted key itself.
    expect(html).not.toMatch(/customers\.(newConnects|transfers|disconnects)\.[a-zA-Z0-9_.]+/);
  });

  // ══════════════════════════════════════════════════════════════════════
  // THE TOOLBAR, AND HOW THE LIST BEHAVES UNDER A CLERK'S HANDS
  // PO, 2026-09-16: *"on List view - can you imporve the interaction design,
  // you also dont have filter and toolkit - elements search, filter, colum
  // selecot, description etc"*.
  // Built to `05-prototype/02 Accounts Menu Blueprint.pdf` p093 + p094, read as
  // IMAGES at scale 2 and the toolbar band again at scale 4 (B14 rule 42).
  // ══════════════════════════════════════════════════════════════════════

  it("the tab carries ONE description sentence, and it is the list's drawn brief", async () => {
    const { html } = await renderTab(payload());
    // p093's own sentence, as a FACT at rule 33's six-word cap.
    expect(html).toContain("Raised here, or from a request.");
    // ⚠ **RULE 33's RATIONALE CLAUSE, ASSERTED AS AN ABSENCE.** p094 prints two
    // grey paragraphs under its pager arguing WHY `Partly activated` is a state
    // and WHY `From request` is the spine. Rationale is ZERO words on screen, so
    // the argument reaches the product as the column and the state, never as
    // prose. A lane that "completes" the screen by pasting them in goes red here.
    expect(html).not.toContain("would be wrong");
    expect(html).not.toContain("is the spine");
    // Rule 32's budget: ONE sentence. A second `<p>` of description would be a
    // second sentence, so the count is the assertion rather than the wording.
    expect(html.match(/Raised here/g)).toHaveLength(1);
  });

  // ⚠⚠ **THESE TWO CASES ASSERTED THE OPPOSITE UNTIL 2026-09-28, AND THEY ARE
  // REWRITTEN RATHER THAN DELETED BECAUSE THE RULING MOVED AND NOT THE CODE'S
  // MIND (`CR-150-BRC09`).** They read *"FROM REQUEST is a column a clerk can
  // see WITHOUT opening the chooser"* and *"a build raised at the counter says
  // so with a dash"*, built to the Accounts blueprint p093/p094 — the drawing
  // of this list BEFORE the PO redrew it. `00-list.png` draws ten columns and
  // `From request` is not one of them, and its README names it in the six the
  // chooser holds: *"Columns chooses the rest: charged, mode, scope, raised
  // by, request number, last event."* A later drawing of the same screen wins
  // (B14 rule 41), so the column is DECLARED and OFF and the assertion is now
  // its own negation — re-defaulting it on goes RED here and names why.
  //
  // ⚠ **THE COLUMN IS NOT DELETED, WHICH IS WHAT THE SECOND HALF ASSERTS.**
  // p093's brief — *"either raised directly or created by approving a request
  // — and the list says which"* — is still true of the register, and the
  // chooser is where the drawing puts the answer. Dropping the column would
  // make the question unanswerable rather than one click away.
  it("`CR-150-BRC09` — FROM REQUEST is BEHIND the chooser, not on the drawn ten", async () => {
    const { html } = await renderTab(payload());
    // Not in a drawn cell…
    expect(html).not.toContain("SR-26-0018");
    // …and still offered, which is what the `▦ Columns` panel lists.
    expect(html).toContain("From request");
  });

  it("`CR-150-BRC09` — the column is DECLARED and off, so one click brings it back", () => {
    const declared = CONFIG.columns.find((column) => column.key === "request_no");
    expect(declared).toBeDefined();
    expect(declared?.defaultVisible).toBe(false);
    // `defaultVisibleColumns` is what `Reset` returns to and what a fresh
    // clerk sees, so it is the honest place to assert the default set.
    expect(defaultVisibleColumns(CONFIG)).not.toContain("request_no");
  });

  it("p094 — the drawn chips are OFFERED, in the drawn order, and `Open` reads as a word", () => {
    // The server hands the vocabulary; the screen only labels it (BR-SHL-010).
    const served = connectionFilterGroups(
      [{ code: "open" }, { code: "partly_activated" }, { code: "activated" }, { code: "on_hold" }],
      t,
    );
    expect(served[0].options.map((option) => option.value)).toEqual([
      "open",
      "partly_activated",
      "activated",
      "on_hold",
    ]);
    expect(served[0].options.map((option) => option.label)).toEqual([
      "Open",
      "Partly activated",
      "Activated",
      "On hold",
    ]);
    // ⚠ The CHIP's word is `Show`, which is the sentence the Requests tab one
    // tab over already prints. Two tabs of one register, one voice.
    expect(served[0].label).toBe("Show");
    expect(served[0].label).toBe(t("customers.serviceRequest.list.segment"));
  });

  it("the `Activated` chip reaches the SERVER — the value that used to narrow to nothing", async () => {
    // `DEF-CUS-5431`: `f.state=activated` was mapped to an empty queryset on the
    // written belief that this list had a window excluding it. It has none, and
    // the blueprint draws an activated build in the list. The browser half of
    // that fix is that the value leaves at all.
    const { urls } = await renderTab(payload(), { state: "activated" });
    expect(urls[0]).toContain("f.state=activated");
  });

  it("the `Open` chip leaves as a value and is NEVER expanded into states in the browser", async () => {
    // NFR-3: `open` is a SET, and the set is resolved in SQL. A screen that
    // expanded it here would either send five params the route does not accept
    // or narrow the page in hand — a subset of a subset under an authoritative
    // total, which is worse than no control (`DEF-1702`'s own shape).
    const { urls } = await renderTab(payload(), { state: "open" });
    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain("f.state=open");
    expect(urls[0]).not.toContain("in_progress");
    expect(urls[0]).not.toContain("f.state=draft");
  });

  it("the toolbar carries the COLUMN SELECTOR, and it has a panel behind it", async () => {
    const { html } = await renderTab(payload());
    // The PO asked for a column selector; the check that matters is not that an
    // icon is present but that the panel behind it names this table's columns —
    // an icon with nothing behind it is the dead-control shape (law 2, backward).
    expect(html).toContain("Columns");
    expect(html).toContain("Applicant");
  });

  // ── INTERACTION DESIGN: THE ROW'S OWN DOOR ────────────────────────────
  it("PO — the CONNECTION NUMBER opens the build, because that is where a clerk's hand goes", async () => {
    const { html } = await renderTab(payload());
    // ⚠ **THE DESTINATION IS THE BUILD'S OWN PAGE FROM 2026-09-28**
    // (`CR-151-BRC09` §6a). It was the build's HOST while the address mounted
    // a redirect; `App.tsx` mounts `BuildDetailPage` there now.
    const href = `href="/${TEST_TENANT}/connections/con-0117"`;
    // Two doors on one row, ONE destination — the number and the eye.
    expect(html.split(href).length - 1).toBe(2);
    // ⚠ The ADDRESS is asserted in full, tenant segment included. A fixture that
    // could not tell a working link from a broken one is how the portal's front
    // page shipped eight doors with two of them working (law 2): a bare
    // `toContain("/connections/")` passes on `//connections/...`, a
    // protocol-relative URL to another host.
    expect(html).not.toContain('href="//connections');
    // Rule 31 — the number a clerk reads is the HUMAN number, never the row id.
    expect(html).toMatch(/>CON-26-0117</);
    expect(html).not.toMatch(/>con-0117</);
  });

  it("a PARKED row — no build behind it — renders its number as TEXT, never as a link onto nothing", async () => {
    // ⚠ **THE *NO DOOR* CASE MOVED ON 2026-09-28 (`CR-151-BRC09` §6a), AND THE
    // MOVE IS THE POINT.** It used to be *no HOME*: the row pointed at the
    // build's host, so a build whose address had not resolved had nowhere to
    // go and its number rendered as text. The build has its own page now, so a
    // homeless build HAS a door — the only row left with none is a PARKED
    // wizard, which has no build id at all. That is strictly fewer dead
    // numbers on this list, not more.
    const { html } = await renderTab(payload({ results: [row({ id: "", home: null })] }));
    expect(html).toContain("CON-26-0117");
    expect(html).not.toContain(`href="/${TEST_TENANT}/connections/`);
    expect(html).not.toContain(`href="/${TEST_TENANT}/premises/prm-500?tab=build"`);
  });

  it("a build with NO HOME still opens its own page (CR-151-BRC09 §6a)", async () => {
    // The mirror of the case above, asserted rather than implied: wave O left
    // these rows with no link whatsoever, and that was the whole of
    // `DEF-CUS-6132`'s complaint about drafts one paragraph over.
    const { html } = await renderTab(payload({ results: [row({ home: null })] }));
    expect(html).toContain(`href="/${TEST_TENANT}/connections/con-0117"`);
  });

  it("rule 31/32 — nothing internal reaches the clerk, read off the RENDERED output", async () => {
    // `internalReferencesIn` reads text nodes, `title` and `aria-label`, which is
    // what a clerk sees — the only kind of check that catches a rule id arriving
    // inside a sentence a component prints verbatim (`DEF-BIL-5339`).
    const { html } = await renderTab(payload());
    expect(internalReferencesInMarkup(html)).toEqual([]);
  });

  it.todo(
    "TC (isolation): tenant B sees none of tenant A's connections — RLS FORCE is the guarantee and it is asserted server-side (06-backend/tests/test_w6_connection_list.py), never through a mocked client seam",
  );
  it.todo(
    "the segment strip FILTERS once OQ-371 closes — there is nothing to assert while `segment=all` is the only value the server serves, and a test that asserted a filter would pin a rule nobody has made",
  );

  // ══════════════════════════════════════════════════════════════════════
  // `CR-150-BRC09` — THE 2026-09-28 REVAMP
  // Built to `05-prototype/new-connect-detail-2026-09-28/00-list.png`, read
  // as an IMAGE (B14 rule 42), and to that folder's README.
  // ══════════════════════════════════════════════════════════════════════

  it("the drawn columns are the DEFAULT set, in the drawn order", () => {
    // The drawing's header row, left to right: the tick box, BUILD, PREMISE,
    // CUSTOMER, UNITS, SERVICES, ORDERS, DUE, TARGET, STATE, AGING, `⋮`.
    //
    // ⚠ **THIS LIST HELD NEITHER `customer` NOR `aging` UNTIL 2026-09-29 AND
    // THE COMMENT ABOVE IT SAID THE SERVER DID NOT SERVE THEM.** It did, from
    // `01580d8fc` on 2026-09-28, and the sentence outlived the fact by a day
    // (`DEF-CUS-7804`, hard-won law 1). Both are drawn columns and both are
    // on by default, in the drawing's own order: CUSTOMER after PREMISE,
    // AGING after STATE.
    //
    // ⛔ **`due` IS STILL ABSENT AND THAT IS STILL DELIBERATE** — no row
    // carries the key, billing publishes no batched invoice position, and
    // `DEF-CUS-7619` is where it comes back. **This assertion is the record
    // of that**: the day the field lands, this case names what to add.
    expect(defaultVisibleColumns(CONFIG)).toEqual([
      "select",
      "connection_no",
      "premise",
      "customer",
      "units",
      "services",
      "orders",
      "target_activation",
      "state",
      "aging",
      "actions",
    ]);
    expect(CONFIG.columns.map((column) => column.key)).not.toContain("due");
  });

  it("the chooser holds the rest, and the tick box and the actions cannot be hidden", () => {
    const hidden = CONFIG.columns
      .filter((column) => column.defaultVisible === false)
      .map((column) => column.key);
    // The README's own list is *charged, mode, scope, raised by, request
    // number, last event*.
    //
    // ⚠ **THIS LINE READ `["waiting_on", "request_no", "applicant"]` UNTIL
    // 2026-09-29, ON THE REASONING THAT *"five of those six have no served
    // field"*.** All five were served on 2026-09-28 by `01580d8fc` and
    // declared nowhere, so the chooser offered a clerk five columns fewer
    // than the endpoint could fill (`DEF-CUS-7804`). All six of the README's
    // are behind the chooser now, plus the applicant (served only because the
    // SEARCH matches on it) and the waiting-on fact the STATE cell folds in.
    expect(hidden).toEqual([
      "waiting_on",
      "request_no",
      "quote_total",
      "mode",
      "scope",
      "raised_by",
      "last_stamped_event",
      "applicant",
    ]);
    // BR-SHL-013's `locked`: a list with no tick boxes and no row menu is not
    // a shorter list, it is a different screen.
    expect(CONFIG.columns.find((column) => column.key === "select")?.locked).toBe(true);
    expect(CONFIG.columns.find((column) => column.key === "actions")?.locked).toBe(true);
  });

  it("the BUILD column is headed `Build` and keyed `connection_no`", () => {
    const build = CONFIG.columns.find((column) => column.key === "connection_no");
    // The drawing's word…
    expect(build?.label).toBe("Build");
    // …over the key `DataTable` stores a saved column set against and the
    // server sorts by. Renaming the KEY would discard every stored preference
    // on S86 and silently stop the header sorting.
    expect(build?.sortable).toBe(true);
    expect(build?.identity).toBe(true);
  });

  it("⛔ no money is INVENTED — `DUE` is still absent and nothing prints a currency", async () => {
    const { html } = await renderTab(payload());
    // Hard rule 2 — money is rounded once, server-side, and this screen
    // PRINTS the server's string. A `$0.00` anywhere here would be
    // `DEF-127`'s fabricated figure that *"looks exactly like a settled
    // account"*, and a `$` at all would assert a currency `_pair` never sent
    // (`DEF-CUS-7806`).
    expect(html).not.toContain("$");
    expect(html).not.toContain("0.00");
    // ⚠ **THIS CASE NAMED THREE ABSENT COLUMNS UNTIL 2026-09-29 AND TWO OF
    // THEM ARE NOW DRAWN** (`DEF-CUS-7804` — the server served them and the
    // screen read none). `due` is the one that is genuinely still missing:
    // no row carries the key, because billing publishes no batched invoice
    // position for a page of builds (`DEF-CUS-7619`).
    expect(CONFIG.columns.map((column) => column.key)).not.toContain("due");
    expect(CONFIG.columns.map((column) => column.key)).toContain("aging");
    expect(CONFIG.columns.map((column) => column.key)).toContain("customer");
    // …and the OWED tile says so in words rather than in a zero.
    expect(html).toContain("No total yet");
  });

  it("⛔ task 17 — there are NO saved-view chips, and state is a filter", async () => {
    // PO 2026-09-28: *"all these option will anyway will be in filter - so we
    // dont need them outside"*. `DEF-1702` already removed the inert segment
    // strip; this is the assertion that nothing puts a second one back under
    // another name. The `+ Filter ▾` panel is what offers the same choices.
    const { html } = await renderTab(payload());
    expect(html).not.toContain("data-view-chip");
    expect(html).not.toContain("data-saved-view");
    expect(html).toContain("+ Filter");
  });

  it("rule 19 — the search prompt names all five things the server matches", async () => {
    const { html } = await renderTab(payload());
    // `connection_reads._search` has five `Q(...)` legs and the prompt names
    // five things. The words are the catalogue's; what is asserted is that
    // the box does not say "Search this list" over a five-leg search.
    expect(CONFIG.searchFields).toEqual([
      "connection_no",
      "premise",
      "address",
      "applicant",
      "request_no",
    ]);
    expect(html).toContain("premise");
    expect(html).toContain("request");
  });

  // ── TASK 16 · THE TILES ARE THE FILTER ────────────────────────────────
  it("pressing a tile SETS the filter, and pressing it again clears it", () => {
    const base = defaultRequestState(CONFIG);
    const applied = pressTile(base, "open");
    expect(applied.filters).toEqual({ state: "open" });
    // The page goes back to 1 — narrowing nine pages to one while a clerk
    // stands on page 4 answers with an empty table under an honest total.
    expect(applied.page).toBe(1);
    expect(pressTile(applied, "open").filters).toEqual({});
  });

  it("task 16 — after a tile is pressed the FILTER BAR shows it applied", async () => {
    // ⚠ **THIS IS THE ASSERTION THE TASK NAMES, AND IT IS WHY THE TILE WRITES
    // `state.filters` RATHER THAN NARROWING THE ROWS ITSELF.** A tile holding
    // its own selection would leave the bar saying *no filters* over a
    // narrowed table — two controls disagreeing about what the table shows.
    const pressed = pressTile(defaultRequestState(CONFIG), "open");
    // ⚠ **`states` CARRIES `open` HERE BECAUSE THE SERVER'S DOES.**
    // `connection_reads.STATE_FILTER_VALUES` begins with `SCOPE_OPEN`, and the
    // chip renders the OPTION's word (`Open`) rather than the code — so a
    // fixture missing the option would show the bar falling back to `open`
    // and this case would be asserting a screen no tenant ever sees. The base
    // fixture predates the value and is left alone for the cases built on it.
    const served = payload({
      states: [{ code: "open" }, ...(payload().states ?? [])],
    });
    const { html } = await renderTab(served, pressed.filters);
    // The bar renders an applied filter as a CHIP carrying `{label}` and the
    // value's WORD — `Show` and `Open`, never the code.
    const bar = html.slice(html.indexOf("table-toolbar"), html.indexOf("<table"));
    expect(bar).toContain("Show");
    expect(bar).toContain("Open");
    // …and the tile reads its own pressed-ness back out of the same state, so
    // the two controls cannot say different things.
    expect(html).toContain('data-tile="open"');
    expect(html).toContain('aria-pressed="true"');
  });

  it("task 16 — the five tiles with no served dimension are FACTS, not dead buttons", async () => {
    const { html } = await renderTab(payload());
    const tiles = newConnectsTiles(payload(), t);
    // ⚠ **THIS LIST HELD FIVE ENTRIES UNTIL 2026-09-29 AND HOLDS SEVEN**
    // (`DEF-CUS-7804`). Only the two that name a value `f.state` actually
    // accepts carry a filter, and that number has NOT moved.
    expect(tiles.map((one) => [one.tile.id, one.filter])).toEqual([
      ["open", "open"],
      // *Waiting* is derived from the `waiting_on` COLUMN and is `OQ-371`'s
      // own open question; `f.state=on_hold` would be a plausible-looking lie.
      // BOTH waiting tiles are facts, for that one reason.
      ["waiting-anyone", null],
      ["waiting-inspection", null],
      ["partly-activated", "partly_activated"],
      // It counts UNITS where every control here selects BUILDS.
      ["units-awaiting", null],
      // It names ONE build rather than a set.
      ["oldest", null],
      // ⛔ `DEF-CUS-7619` — no figure at all, so certainly nothing to filter by.
      ["owed", null],
    ]);
    // Law 2's mirror: a tile that cannot filter is not drawn as a control a
    // clerk presses and then finds does nothing.
    expect(html.match(/data-tile-filter=/g)).toHaveLength(2);
  });

  // ── TASK 15 · THE ROW DOOR, AND THE HOLD THAT IS STILL TRUE ───────────
  it("task 15 — ONE function decides both doors on a row", () => {
    // ⚠ **THE HOLD EXPIRED ON 2026-09-28 AND THIS IS THE LINE IT NAMED.** A
    // FINISHED build goes to ITS OWN PAGE at `/connections/{id}`; a DRAFT goes
    // to its own wizard (`DEF-CUS-6132`); a PARKED row — no build id — carries
    // no link at all. Until `CR-151-BRC09` §6a flipped the route, the first of
    // those read `/premises/prm-500?tab=build`, because that address mounted a
    // redirect and pointing a row at it would have been a live control onto a
    // doorway.
    expect(rowDoor(row())).toBe("/connections/con-0117");
    expect(rowDoor(row({ state: "draft" }))).toContain("/connections/new");
    expect(rowDoor(row({ id: "", home: null }))).toBeNull();
  });

  it("task 15 — the build address mounts the PAGE, which is what `rowDoor` now points at", () => {
    // ⚠ **THE HOLD'S OWN TEST, KEPT AND TURNED ROUND (hard-won law 2's
    // mirror).** It used to assert the address still mounted `BuildRedirect`
    // and to name the one line to change when it stopped. It stopped: the
    // assertion is now that the doorway is GONE, so a lane that reinstates a
    // redirect here without moving `rowDoor` back meets a red test rather than
    // a row whose number opens a page that bounces.
    const connections = APP_ROUTES.flatMap((route) => route.children ?? [])
      .flatMap((route) => route.children ?? [])
      .filter((route) => (route.path ?? "").endsWith("connections/:connectionId"));
    expect(connections).toHaveLength(1);
    const element = connections[0].element as { type?: { name?: string } } | undefined;
    expect(element?.type?.name).not.toBe("BuildRedirect");
    expect(element?.type?.name).toBe("BuildDetailPage");
  });

  // ── TASK 22 · THE ROW MENU AND THE BULK BAR ───────────────────────────
  it("task 22 — the row menu offers Hold, Waiting on and Cancel, in the drawn order", async () => {
    const { html } = await renderTab(payload());
    // `RowActionsMore` is a `<details>`, so its contents render statically —
    // which is why a static case can read a menu at all.
    expect(html).toContain("data-row-more");
    const menu = html.slice(html.indexOf("data-row-more"));
    expect(menu.indexOf("Hold")).toBeLessThan(menu.indexOf("Waiting on"));
    expect(menu.indexOf("Waiting on")).toBeLessThan(menu.indexOf("Cancel"));
  });

  it("task 22 — a CANCELLED build's acts are refused with the SERVER's own reason", async () => {
    const { html } = await renderTab(payload({ results: [row({ state: "cancelled" })] }));
    // Not a hardcoded `disabled`: `actBlockedReason` is Work's function and
    // the sentence is the one the service itself would answer with.
    expect(html).toContain("This build is canceled.");
    expect(html).toContain("disabled");
  });

  it("task 22 — the menu never offers an act whose refusal reads a field a ROW cannot fill", () => {
    // ⚠ **THE CHECK THAT FIRES ON A FOURTH ACT.** `rowBuildFacts` maps a list
    // row into the shape `actBlockedReason` reads, and a list row carries no
    // to-do list — so `outstanding` is `[]` and `closeOutstanding` would
    // refuse on every row forever. A refusal that is not a real check is the
    // one thing this wiring exists to avoid.
    for (const act of BUILD_ROW_ACTS) {
      expect(ACTS_DECIDED_BY_STATE_ALONE).toContain(act);
    }
    expect(BUILD_ROW_ACTS).not.toContain("closeOutstanding");
  });

  it("task 22 — the bulk bar acts on the rows that CAN take the act, and says how many", () => {
    const rows = [row(), row({ id: "con-dead", state: "cancelled" })];
    // One of the two is cancelled, so one can be held.
    expect(eligibleForAct(rows, "hold", t).map((one) => one.id)).toEqual(["con-0117"]);
    // And a selection where NONE can act reads the first row's real reason.
    expect(eligibleForAct([rows[1]], "cancel", t)).toEqual([]);
  });

  it("task 22 — the bar SAYS how many can act before anybody presses it", () => {
    // `SelectionToolbar.eligibility`'s own reason: *"a bar that goes live when
    // the action will mostly fail is worse than one that is greyed out"*. Two
    // ticked, one cancelled — the bar must not report *2 selected* over an act
    // that will run on one.
    const html = renderToStaticMarkup(
      <BuildBulkBar
        rows={[row(), row({ id: "con-dead", state: "cancelled" })]}
        t={t}
        onAct={() => undefined}
        onClear={() => undefined}
      />,
    );
    expect(html).toContain("2 selected");
    expect(html).toContain("1 can be held");
  });

  it("task 22 — an EMPTY selection draws no bar rather than throwing", () => {
    // A ticked id survives a page, a sort and a filter change, so *ticked
    // something* and *that row is on the page* are two questions and the
    // second can be no. The bar reads `rows[0]` for its refusal sentence, so
    // the empty case is a white screen and not a missing bar.
    const html = renderToStaticMarkup(
      <BuildBulkBar rows={[]} t={t} onAct={() => undefined} onClear={() => undefined} />,
    );
    expect(html).toBe("");
  });

  it("task 22 — `rowBuildFacts` carries the row's own state and invents nothing", () => {
    const facts = rowBuildFacts(row({ state: "on_hold" }));
    expect(facts.state).toBe("on_hold");
    // The two fields a list row does not carry are stated as absent rather
    // than filled with a plausible value.
    expect(facts.mode).toBeNull();
    expect(facts.quote_total).toEqual({ stored: null, display: null });
    expect(facts.outstanding).toEqual([]);
  });

  it("the STATE cell folds `waiting_on` in, which is why the column moved behind the chooser", async () => {
    const { html } = await renderTab(payload());
    expect(html).toContain("Waiting · inspection");
    // A build nobody is waiting on reads its state, exactly as before.
    const quiet = await renderTab(payload({ results: [row({ waiting_on: null })] }));
    expect(quiet.html).toContain("Partly activated");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W6 task 6.12 (S86 `NCT-01`) · B18 §5.4 · OQ-371 · CR-032
// generated: 2026-08-25 by lane F-TABS
// checklist: A=n/a B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: E4 the isolation case is a server/RLS claim a mocked seam cannot
//         prove, and a test that pretended to would be worse than none · E4 the
//         segment FILTER cannot be asserted while OQ-371 is open
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
