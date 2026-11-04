// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.03 (lane MVI-LIST-UI) — the Move-ins list's tests,
//           REWRITTEN for the redesigned list (images 01 and 02) and for the two
//           sentences the redesign reversed: S3 (*"A move-in nobody has
//           approved yet is an application … so it is on the Requests tab"*)
//           and S4 (*"A move-in leaves this list the moment its account opens"*).
//           Both footnotes are gone; request rows and completed rows are rows.
// Rules:    CR-171-BRC10 §6.1 · §9.LIST · B14 rules 12, 15, 33, 42, 44 ·
//           BR-CUS-1046 · DEF-CUS-7900 · hard-won law 2 (whole addresses)
// Tests:    this file
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY ADDRESS IS ASSERTED WHOLE, TENANT SEGMENT AND ALL.** A link built
// without the tenant comes out `//moves/…` — a protocol-relative URL to another
// host — and `toContain("/moves/")` passes straight over it. `hrefOf` reads the
// href out of the ONE tag carrying a marker, so a second control on the same
// row pointing at the same place cannot satisfy an assertion about the first.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import { defaultRequestState } from "@/components/tableTypes";

import {
  MoveInsTab,
  listMoveIns,
  moveInActionPath,
  moveInFilterGroups,
  moveInStatusTone,
  moveInsKpis,
  moveInsQueryKey,
  moveInsTableConfig,
} from "./MoveInsTab";
import type { MoveInList, MoveInRow } from "./MoveInsTab";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const CONFIG = moveInsTableConfig(t, {
  reference: () => <span />,
  moveInDate: () => <span />,
  action: () => <span />,
});

/** What a person reads — every tag and attribute stripped. */
function visibleText(html: string): string {
  return html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ");
}

/** The `href` of the ONE anchor carrying `marker`, or `null`. */
function hrefOf(html: string, marker: string): string | null {
  const literal = marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const tag = html.match(new RegExp(`<a[^>]*${literal}[^>]*>`));
  if (tag === null) return null;
  const href = tag[0].match(/href="([^"]*)"/);
  return href === null ? null : href[1].replace(/&amp;/g, "&");
}

/** The `<tr>` whose text contains `needle`, as HTML. */
function rowHtml(html: string, needle: string): string {
  const rows = html.split("<tr").slice(1);
  return rows.find((one) => visibleText(one).includes(needle)) ?? "";
}

const NOT_YET_READ = {
  state: null,
  meters_total: null,
  meters_read: null,
  missing: [],
  readings: [],
  unavailable: {
    code: "no_opening_read_before_complete",
    br_ref: "CR-171 §6.1",
    detail: "Opening reads are taken when the move-in is completed.",
  },
};

const NO_DEPOSIT = {
  currency: null,
  amount: null,
  recorded: false,
  sentence: null,
  unavailable: [
    {
      code: "pending_move_in_has_no_deposit_on_file",
      br_ref: "BR-CUS-023",
      detail: "A deposit is held ON an account and this job has not opened one.",
    },
  ],
};

function deposit(display: string) {
  return {
    currency: "USD",
    amount: { stored: `${display}00`, display },
    recorded: true,
    sentence: null,
    unavailable: [],
  };
}

/** One row, the shape every kind shares (§9.LIST). */
function base(over: Partial<MoveInRow>): MoveInRow {
  return {
    move_no: null,
    move_no_unavailable: null,
    row_kind: "request",
    job_id: null,
    account_id: null,
    account_no: null,
    customer: "Asha Verma",
    customer_no: null,
    customer_source: "request_applicant",
    unit_id: "u-311",
    unit: "Kestrel Park ph. 2 · SCW-U-311",
    move_in_date: "2026-10-12",
    step: { reached: null, of: 4, id: null, name: null, unavailable: null },
    deposit: null,
    booked_in_on: "2026-10-03",
    age_days: 2,
    status: "to_approve",
    reference: "SR-26-0014",
    action: "review",
    services: ["water", "sewer"],
    opening_read: NOT_YET_READ,
    ...over,
  };
}

/** Image 01's rows, one per drawn status (figures are illustrations, rule 37 —
 *  the SHAPES are the test). */
function imageRows(): MoveInRow[] {
  return [
    base({
      request_id: "req-14",
      request: {
        id: "req-14",
        request_no: "SR-26-0014",
        waiting_on: null,
        park_note: null,
        state: "submitted",
        requested_start: "2026-10-12",
      },
    }),
    base({
      row_kind: "pending_job",
      job_id: "job-11",
      customer: "Carl Brandt",
      unit: "88 Pine Vista · SCW-U-206",
      move_in_date: "2026-10-14",
      status: "not_started",
      reference: "MVI-26-0011",
      move_no: "MVI-26-0011",
      action: "start",
      services: ["water"],
      deposit: NO_DEPOSIT,
      request: {
        id: "req-11",
        request_no: "SR-26-0011",
        waiting_on: null,
        park_note: null,
        state: "approved",
        requested_start: "2026-10-14",
      },
    }),
    base({
      row_kind: "move_record",
      record_id: "rec-10",
      account_id: "acc-10",
      account_no: "A-10010",
      customer: "Nilesh G",
      unit: "Kestrel Park ph. 2 · SCW-U-308",
      move_in_date: "2026-10-10",
      status: "waiting_on_a_read",
      reference: "MVI-26-0010",
      move_no: "MVI-26-0010",
      action: "view",
      step: { reached: null, of: 4, id: null, name: null, unavailable: null, done: true },
      deposit: deposit("150.00"),
      opening_read: {
        state: "due",
        meters_total: 2,
        meters_read: 1,
        missing: ["SM-7041"],
        readings: [],
        unavailable: null,
      },
    }),
    base({
      row_kind: "parked_move_in",
      park_id: "park-9",
      customer: "Lena Ortiz",
      unit: "12 Harbour View · Unit 1",
      move_in_date: "2026-10-09",
      status: "draft",
      reference: "MVI-26-0009",
      move_no: "MVI-26-0009",
      action: "resume",
      services: ["water"],
      age_days: 2,
      step: { reached: 3, of: 4, id: "billing", name: "Billing", unavailable: null },
      deposit: NO_DEPOSIT,
    }),
    base({
      row_kind: "move_record",
      record_id: "rec-6",
      account_id: "acc-6",
      account_no: "A-10006",
      customer: "Priya Raman",
      unit: "1408 Elm Street · Unit A",
      move_in_date: "2026-10-05",
      status: "completed",
      reference: "MVI-26-0006",
      move_no: "MVI-26-0006",
      action: "view",
      services: ["electric", "water"],
      step: { reached: null, of: 4, id: null, name: null, unavailable: null, done: true },
      deposit: deposit("0.00"),
      opening_read: {
        state: "taken",
        meters_total: 2,
        meters_read: 2,
        missing: [],
        readings: [
          { register: "E-5041", reading: "16082.000000", unit: "kWh" },
          { register: "W-5041", reading: "841.000000", unit: "kgal" },
        ],
        unavailable: null,
      },
    }),
  ];
}

function payload(over: Partial<MoveInList> = {}): MoveInList {
  return {
    rows: imageRows(),
    kpis: { to_approve: 2, not_started: 3, drafts: 1, starting_this_week: 4, waiting_on_a_read: 1 },
    page: 1,
    per: 50,
    total: 5,
    pages: 1,
    columns: [],
    statuses: [
      "to_approve",
      "waiting_on_customer",
      "declined",
      "not_started",
      "draft",
      "waiting_on_a_read",
      "completed",
      "cancelled",
    ],
    filters: ["status", "service", "state"],
    search: { hint: "Search customer, unit, MVI…", min_chars: 2, legs: [], unavailable: [] },
    exclusion: { callout: "", contract: [], half_account_ids: [] },
    // Still served — and, since S3/S4, never drawn.
    unavailable: [
      {
        code: "pending_job_closes_on_the_recorded_move",
        br_ref: "BR-CUS-1077",
        detail: "a job closes on the recorded move.",
      },
    ],
    as_of: "2026-10-05",
    ...over,
  };
}

async function renderTab(
  body: MoveInList | "unreadable",
  filters: Record<string, string> = {},
): Promise<{ html: string; urls: string[] }> {
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
  try {
    await queryClient.prefetchQuery({
      queryKey: moveInsQueryKey(state),
      queryFn: () =>
        listMoveIns(
          {
            q: state.q,
            page: state.page,
            per: state.per,
            filters: state.filters,
            sort: state.sort,
            dir: state.dir,
          },
          client,
        ),
    });
  } catch {
    // An unreadable payload is one of the cases under test.
  }
  const html = renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=move-ins`]}>
        <MoveInsTab client={client} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { html, urls };
}

function tileValues(list: MoveInList): string {
  const tiles = moveInsKpis(list, t);
  return visibleText(
    renderToStaticMarkup(
      <>{tiles.map((tile) => ("value" in tile ? <b key={tile.id}>{tile.value}</b> : null))}</>,
    ),
  ).trim();
}

describe("CR-171-BRC10 P2.01 — the Move-ins list, image 01", () => {
  it("law 2 — the tab CALLS `GET /move-ins` for this tenant", async () => {
    const { urls } = await renderTab(payload());
    expect(urls[0]).toContain("/move-ins");
    expect(urls[0]).toContain(TEST_TENANT);
  });

  it("the columns are image 01's nine, in its order, then the icon", () => {
    expect(CONFIG.columns.map((column) => column.label)).toEqual([
      "Reference",
      "Customer",
      "Unit",
      "Services",
      "Move-in date",
      "Step",
      "Opening read",
      "Deposit",
      "State",
      "",
    ]);
  });

  it("the five tiles, the server's counts, in image 01's order", () => {
    expect(moveInsKpis(payload(), t).map((tile) => tile.label)).toEqual([
      "To approve",
      "Not started",
      "Drafts",
      "Starting this week",
      "Waiting on a read",
    ]);
    expect(tileValues(payload())).toBe("2 3 1 4 1");
  });

  it("⛔ a tile the server did not send draws `—`, never `0`", () => {
    expect(tileValues(payload({ kpis: { to_approve: 0 } }))).toBe("0 — — — —");
  });

  it("each row wears the server's status as image 01's pill", async () => {
    const { html } = await renderTab(payload());
    const text = visibleText(html);
    for (const pill of ["To approve", "Not started", "Waiting on a read", "Draft · 2 days", "Completed"]) {
      expect(text).toContain(pill);
    }
  });

  it("S3 — a request that suggests a move-in IS a row, and its reference opens the details view", async () => {
    const { html } = await renderTab(payload());
    expect(hrefOf(html, 'data-move-in-reference="SR-26-0014"')).toBe(
      `/${TEST_TENANT}/moves/SR-26-0014`,
    );
  });

  it("S4 — a completed move-in stays on the list", async () => {
    const { html } = await renderTab(payload());
    expect(rowHtml(html, "MVI-26-0006")).toContain('data-move-in-status="completed"');
  });

  it("⛔ S3/S4 — no footnote under the table, no sort sentence, no list absence", async () => {
    const { html } = await renderTab(payload());
    const text = visibleText(html);
    expect(text).not.toContain("Requests tab");
    expect(text).not.toContain("leaves this list");
    expect(text).not.toContain("newest first");
    expect(html).not.toContain('data-move-absent="list"');
  });

  it("the Reference never wraps (P2.02)", async () => {
    const { html } = await renderTab(payload());
    const tag = html.match(/<a[^>]*data-move-in-reference="MVI-26-0010"[^>]*>/)?.[0] ?? "";
    expect(tag).toContain("whitespace-nowrap");
  });

  it("STEP reads `—` before anybody started, `3 of 4 · Billing` on a draft, `Done` once complete", async () => {
    const { html } = await renderTab(payload());
    expect(rowHtml(html, "SR-26-0014")).toMatch(/<td[^>]*>\s*<span aria-label="None">—<\/span>/);
    expect(visibleText(rowHtml(html, "MVI-26-0009"))).toContain("3 of 4 · Billing");
    expect(visibleText(rowHtml(html, "MVI-26-0006"))).toContain("Done");
  });

  it("OPENING READ reads `Waiting` while due and the readings with their units once taken", async () => {
    const { html } = await renderTab(payload());
    expect(visibleText(rowHtml(html, "MVI-26-0010"))).toContain("Waiting");
    expect(visibleText(rowHtml(html, "MVI-26-0006"))).toContain("16,082 kWh · 841 kgal");
  });

  it("DEPOSIT reads the amount held, or a dash — never a sentence in the cell", async () => {
    const { html } = await renderTab(payload());
    expect(visibleText(rowHtml(html, "MVI-26-0010"))).toContain("$150.00");
    const job = visibleText(rowHtml(html, "MVI-26-0011"));
    expect(job).not.toContain("deposit");
    expect(job).not.toContain("None recorded");
  });

  it("services are image 01's letter squares, named for a screen reader", async () => {
    const { html } = await renderTab(payload());
    const request = rowHtml(html, "SR-26-0014");
    expect(request).toContain('aria-label="Water"');
    expect(request).toContain('aria-label="Sewer"');
  });

  it("a failed load renders no row and no fabricated figure", async () => {
    const { html } = await renderTab("unreadable");
    expect(html).not.toContain("SR-26-0014");
    expect(html).not.toContain("<tbody");
  });
});

describe("CR-171-BRC10 P2.02 — ONE icon per row, named with its reference", () => {
  it("To approve → Review, onto the details view", async () => {
    const { html } = await renderTab(payload());
    const row = rowHtml(html, "SR-26-0014");
    expect(row).toContain('title="Review SR-26-0014"');
    expect(hrefOf(row, 'aria-label="Review SR-26-0014"')).toBe(`/${TEST_TENANT}/moves/SR-26-0014`);
  });

  it("Not started → Start, onto the wizard filled from its request", async () => {
    const { html } = await renderTab(payload());
    expect(hrefOf(html, 'aria-label="Start MVI-26-0011"')).toBe(
      `/${TEST_TENANT}/move-ins/new?request=req-11`,
    );
  });

  it("Draft → Resume, onto the wizard at its parked draft (DEF-CUS-7900)", async () => {
    const { html } = await renderTab(payload());
    expect(hrefOf(html, 'aria-label="Resume MVI-26-0009"')).toBe(
      `/${TEST_TENANT}/move-ins/new?parked=park-9`,
    );
  });

  it("Waiting on a read and Completed → View, onto the details view", async () => {
    const { html } = await renderTab(payload());
    expect(hrefOf(html, 'aria-label="View MVI-26-0010"')).toBe(`/${TEST_TENANT}/moves/MVI-26-0010`);
    expect(hrefOf(html, 'aria-label="View MVI-26-0006"')).toBe(`/${TEST_TENANT}/moves/MVI-26-0006`);
  });

  it("exactly one icon on every row", async () => {
    const { html } = await renderTab(payload());
    expect(html.match(/data-move-in-action="/g)?.length).toBe(5);
  });

  it("a legacy job with no request starts from its details view; a row with nowhere to go draws no icon", () => {
    const job = imageRows()[1];
    expect(moveInActionPath({ ...job, request: null })).toBe("/moves/MVI-26-0011");
    expect(moveInActionPath({ ...job, reference: null, request: null })).toBeNull();
  });
});

describe("CR-171-BRC10 P2.01 — image 02's filter: Status and Service", () => {
  it("the panel offers Status as image 02's three groups and Service as the tenant's", () => {
    const groups = moveInFilterGroups([{ value: "water", label: "Water" }], t);
    expect(groups.map((group) => group.name)).toEqual(["status", "service"]);
    expect(groups[0].options.map((option) => option.label)).toEqual([
      "To approve",
      "Open",
      "Completed",
    ]);
    expect(groups[1].options).toEqual([{ value: "water", label: "Water" }]);
  });

  it("`f.status` and `f.service` LEAVE THE BROWSER; the old `f.state` never does", async () => {
    const { urls } = await renderTab(payload(), {
      status: "open",
      service: "water,sewer",
      state: "due",
    });
    const url = decodeURIComponent(urls[0]);
    expect(url).toContain("f.status=open");
    expect(url).toContain("f.service=water,sewer");
    expect(url).not.toContain("f.state");
  });

  it("the query key carries filters, sort and direction", () => {
    const state = { ...defaultRequestState(CONFIG), filters: { status: "open" } };
    expect(moveInsQueryKey(state)).toContainEqual({ status: "open" });
    expect(moveInsQueryKey(state)).toContain("created");
  });

  it("tones: amber for the two waiting on a clerk, blue for Not started, green for Completed", () => {
    expect(moveInStatusTone("to_approve")).toBe("warning");
    expect(moveInStatusTone("waiting_on_a_read")).toBe("warning");
    expect(moveInStatusTone("not_started")).toBe("info");
    expect(moveInStatusTone("completed")).toBe("success");
    expect(moveInStatusTone("draft")).toBe("neutral");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-171-BRC10 §5 · §6 · §8 P2.01–P2.03 · §9.LIST
// generated: 2026-10-05 by lane MVI-LIST-UI — the CR-030 W5 suite this file
//         held is superseded by the redesign; its surviving rules (whole
//         addresses, server-owned counts, no fabricated figure) are kept above
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
