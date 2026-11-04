// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-010 (effective-dated versioning + the S9 History view) ·
//           US-RAT-011 (bulk rate update: 202 + job_id, atomic, never re-run)
//           Screens: S9 (History)
// Rules:    BR-RAT-007 · BR-RAT-017 · BR-RAT-037 (append-only, reason required) ·
//           BR-RAT-040 (one batch, one reason, one date; never re-run) ·
//           BR-SHL-010/011/012/020/025/032/034
// ───────────────────────────────────────────────────────
// The two tests this file exists for:
//
//   · the compliance log is READ-ONLY BY CONSTRUCTION — a DOM scan proves no
//     mutating affordance exists on the History view;
//   · the bulk apply is the 202 → poll path, and it fails LOUDLY today because
//     the job store is not registered on this deployment. No test here asserts
//     a success the server cannot deliver.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError, createApiClient } from "@/api/client";
import { previewRateChange, requestRateChange } from "@/api/endpoints";
import type { Paginated, RateChangeRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { serializeTableParams } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";
import { apiErrorText } from "@/features/tenancy/settingsShared";

import {
  BulkPreview,
  DIFF_PARAM,
  HISTORY_ENTITY_TYPES,
  RateChangesTab,
  bulkBody,
  bulkDraftReady,
  emptyBulkDraft,
  historyTableConfig,
} from "./RateChangesTab";
import type { RatingTabRender, Translator } from "./ratingShared";

// US-SHL-020 addendum r2: a tab hands its button and its content to the frame
// rather than rendering the button itself. These tests exercise the tab alone,
// so they stand in for the frame and render both halves.
const bothHalves: RatingTabRender = ({ action, body }) => (
  <>
    {action}
    {body}
  </>
);

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…` and
// every tenant-scoped call goes to `/api/{tenant}/…`. Tests state the tenant
// the browser would be showing, so both are visible here rather than implied.
const TEST_TENANT = "brazosbend";

const t: Translator = (key, params) => i18n.t(key, params);

// US-RAT-010 TC-3's row: Res Water · Inclining, tier 1 from 3.20 to 3.45.
const TIER_CHANGE: RateChangeRow = {
  id: "log-1",
  changed_at: "2026-08-09T15:42:00Z",
  entity_type: "schedule",
  entity_id: "t-res-w",
  entity_name: "Res Water · Inclining",
  before: { name: "Res Water · Inclining", unit_price: "3.200000", model: "tiered" },
  after: { name: "Res Water · Inclining", unit_price: "3.450000", model: "tiered" },
  reason: "TWDB pass-through 2026",
  actor_user_id: "u-dana",
  actor: { name: "Dana Whitfield" },
  batch_id: null,
  is_batch: false,
  published_by: { name: null },
  before_kept: true,
  // DEF-RAT-10029 — the server words each changed fact; the screen lays it out.
  changes: [{ field: "Tier 1 · Rate", before: "$3.20", after: "$3.45" }],
  change_count: 1,
};

const BATCH_CHANGE: RateChangeRow = {
  ...TIER_CHANGE,
  id: "log-2",
  entity_type: "plan",
  entity_name: "Residential Standard",
  reason: "Board order 2026-12 annual adjustment",
  batch_id: "b-2026-001",
  is_batch: true,
  published_by: { name: "Dana Whitfield" },
};

// DEF-RAT-10029 — the PO's row, as the server stores it for a plan version
// published before the fix: no `before`, an `after` full of ids, a uuid actor.
const UUID_PATTERN = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
const QUEEN_WEST_PLAN: RateChangeRow = {
  id: "01a0f400-0000-7000-8000-000000000001",
  changed_at: "2026-10-08T15:42:00Z",
  entity_type: "plan",
  entity_id: "01a0f27b-3fdb-7c3e-9a51-6c1f0e2d4b11",
  entity_name: "Residential City Plan",
  before: null,
  after: {
    id: "01a0f27b-3fdb-7c3e-9a51-6c1f0e2d4b11",
    name: "Residential City Plan",
    account_type_id: "01a0f27b-4abc-7def-8123-456789abcdef",
    account_type_ids: ["01a0f27b-4abc-7def-8123-456789abcdef"],
    minimum_bill_amount: "12.000000",
    tax_attachments: [{ tax_id: "01a0f27b-5abc-7def-8123-456789abcdef", name: "State tax" }],
  },
  reason: "The amount changed",
  actor_user_id: "01a0f319-1111-7222-8333-444455556666",
  actor: { name: "Dana Whitfield" },
  batch_id: "01a0f319-9999-7222-8333-444455556666",
  is_batch: true,
  published_by: { name: "Dana Whitfield" },
  before_kept: false,
  changes: [
    { field: "Name", before: "—", after: "Residential City Plan" },
    { field: "Customer classes", before: "—", after: "Municipal" },
    { field: "Minimum bill", before: "—", after: "$12.00" },
    { field: "Taxes", before: "—", after: "State tax" },
  ],
  change_count: 4,
};

const QUEEN_WEST_EDIT: RateChangeRow = {
  ...QUEEN_WEST_PLAN,
  id: "01a0f400-0000-7000-8000-000000000002",
  before: { ...QUEEN_WEST_PLAN.after, minimum_bill_amount: "10.000000" },
  batch_id: null,
  is_batch: false,
  published_by: { name: null },
  before_kept: true,
  changes: [
    { field: "Customer classes", before: "Residential", after: "Municipal" },
    { field: "Minimum bill", before: "$10.00", after: "$12.00" },
  ],
  change_count: 2,
};

/** The text a person reads — markup and attributes stripped. */
function visibleText(html: string): string {
  return html.replace(/<[^>]*>/g, " ");
}

const CONFIG = historyTableConfig(t, {
  when: () => <span />,
  entity: () => "",
  change: () => <span />,
  actor: () => <span />,
  publishedBy: () => <span />,
  batch: () => <span />,
});

function renderHistory(path: string, rows: RateChangeRow[]): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const search = new URLSearchParams(path.split("?")[1] ?? "");
  const filters: Record<string, string> = {};
  for (const filter of CONFIG.filters ?? []) {
    const value = search.get(`f.${filter.name}`);
    if (value !== null && value !== "") {
      filters[filter.name] = value;
    }
  }
  const state = { q: "", page: 1, per: 50 as const, filters, ...CONFIG.defaultSort };
  queryClient.setQueryData(queryKeys.rateChanges(serializeTableParams(state, CONFIG).toString()), {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
  } satisfies Paginated<RateChangeRow>);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <RateChangesTab readOnly={false} timeZone="America/Chicago" dateFormat="MM/DD/YYYY"
              render={bothHalves}
            />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-RAT-010 — the S9 History view over the compliance log", () => {
  it("US-RAT-010 TC-3: the row carries when, entity, the before → after, the reason and who", () => {
    const html = renderHistory("/plans-rates/history", [TIER_CHANGE]);
    for (const label of ["When", "What changed", "Change", "Reason", "Who", "Batch"]) {
      expect(html).toContain(`>${label}<`);
    }
    expect(html).toContain("Res Water · Inclining");
    expect(html).toContain("TWDB pass-through 2026");
    // ⚠ AMENDED 2026-10-09 (`DEF-RAT-10029`). This read the STORED strings
    // (`3.200000 → 3.450000`) on the judgment that a compliance history should
    // quote the payload byte for byte. The PO's report on 2026-10-09 put that
    // screen in front of a clerk — field keys, uuids and a JSON dump — and B14
    // rule 31 forbids it. The server now words each fact: a unit price at up
    // to four places (hard rule 2), money at two. The stored payload is still
    // the CSV export's, for a regulator.
    expect(html).toContain("Tier 1 · Rate:");
    expect(html).toContain("$3.20");
    expect(html).toContain("$3.45");
    expect(html).toContain("Dana Whitfield");
    expect(html).not.toContain("u-dana");
    // BR-SHL-034: the instant renders in the tenant TZ (15:42Z is 10:42 CDT).
    expect(html).toContain("08/09/2026 10:42");
    // The matrix's own default: newest first.
    expect(CONFIG.defaultSort).toEqual({ sort: "changed_at", dir: "desc" });
  });

  // ⚠ THE THREE `diffFields` CASES THAT STOOD HERE (TC-3's comparison and
  // DEF-280's two structural cases) MOVED TO THE SERVER with the walk itself
  // (`DEF-RAT-10029`): `06-backend/tests/test_def_rat_10029_history_words.py`
  // asserts *Tier 1 · Rate: $3.20 → $3.45* from a real schedule version, which
  // is DEF-280's own case worded for a clerk rather than as a JSON path.

  it("DEF-RAT-10029: no database id reaches the History list or Change details", () => {
    // RED at 2.562.0: WHO printed `actor_user_id`, CHANGE printed
    // `account_type_id — → 01a0f27b-…`, Batch printed the batch uuid, and the
    // dialog dumped `after` as JSON.
    const list = visibleText(renderHistory("/plans-rates/history", [QUEEN_WEST_PLAN, QUEEN_WEST_EDIT]));
    expect(list).not.toMatch(UUID_PATTERN);
    expect(list).toContain("Dana Whitfield");
    expect(list).toContain("Bulk change");
    for (const row of [QUEEN_WEST_PLAN, QUEEN_WEST_EDIT]) {
      const dialog = visibleText(renderHistory(`/plans-rates/history?${DIFF_PARAM}=${row.id}`, [row]));
      expect(dialog).toContain("Change details");
      expect(dialog).not.toMatch(UUID_PATTERN);
      expect(dialog).not.toContain("account_type_id");
      expect(dialog).not.toContain("{");
    }
  });

  it("DEF-RAT-10029: CHANGE reads 'Field: before → after'; the dialog is a Field · Before · After table", () => {
    const list = visibleText(renderHistory("/plans-rates/history", [QUEEN_WEST_EDIT]));
    expect(list).toContain("Customer classes:");
    expect(list).toContain("Residential");
    expect(list).toContain("Municipal");
    expect(list).toContain("and 1 more");
    const dialog = renderHistory(`/plans-rates/history?${DIFF_PARAM}=${QUEEN_WEST_EDIT.id}`, [QUEEN_WEST_EDIT]);
    expect(dialog).toContain("<th>Field</th><th>Before</th><th>After</th>");
    expect(dialog).toContain("<td>Minimum bill</td><td>$10.00</td><td>$12.00</td>");
  });

  it("DEF-RAT-10029: a row stored with no before says so, never '89 more' changes", () => {
    const list = visibleText(renderHistory("/plans-rates/history", [QUEEN_WEST_PLAN]));
    expect(list).toContain("Earlier values not kept");
    expect(list).not.toContain("more");
    const dialog = renderHistory(`/plans-rates/history?${DIFF_PARAM}=${QUEEN_WEST_PLAN.id}`, [QUEEN_WEST_PLAN]);
    expect(dialog).toContain("Earlier values not kept");
    expect(dialog).toContain("<td>Minimum bill</td><td>—</td><td>$12.00</td>");
    expect(dialog).not.toContain("Nothing recorded");
  });

  it("BR-RAT-037: the History view is read-only BY CONSTRUCTION — no mutating affordance exists", () => {
    const html = renderHistory("/plans-rates/history", [TIER_CHANGE, BATCH_CHANGE]).toLowerCase();
    // Not disabled — ABSENT. The log is append-only and the API defines no
    // mutation route for it, so no permission could ever unlock one.
    for (const forbidden of [">edit<", ">delete<", ">annotate<", ">amend<", ">void<", ">redact<"]) {
      expect(html).not.toContain(forbidden);
    }
    expect(html).toContain("this record is written once and never changed");
  });

  it("US-RAT-010 TC-2/TC-6: the declared filters, and a blank reason is the server's refusal", () => {
    expect(CONFIG.filters?.map((filter) => filter.name)).toEqual([
      "entity_type",
      "batch",
      "from",
      "to",
    ]);
    // DEF-RAT-10032 (PO 2026-10-09, option (a)) — Tax and Discount joined the filter.
    expect([...HISTORY_ENTITY_TYPES]).toEqual(["schedule", "plan", "charge", "tax", "discount"]);
    expect(CONFIG.filters?.[0].options.map((option) => option.label)).toEqual(
      expect.arrayContaining(["rating.history.entity.tax", "rating.history.entity.discount"].map((key) => t(key))),
    );
    const refused = new ApiError(422, { code: "VAL-001", message_key: "rating.reason_required" });
    expect(apiErrorText(refused, t)).toBe("A reason is required for every rate change.");
  });

  it("US-RAT-010 TC-5: an overlapping window is refused with both dates named", () => {
    const overlap = new ApiError(409, {
      code: "BIZ-WINDOW",
      message_key: "rating.schedules.window_overlap",
      params: { effective_from: "2026-08-15", current_from: "2026-08-01" },
      br_ref: "BR-RAT-037",
    });
    const text = apiErrorText(overlap, t);
    expect(text).toContain("2026-08-15");
    expect(text).toContain("2026-08-01");
    expect(text).toContain("may not overlap");
  });

  it("BR-SHL-011: the open diff is URL state, so a compliance question is a shareable link", () => {
    expect(DIFF_PARAM).toBe("diff");
    const html = renderHistory(`/plans-rates/history?${DIFF_PARAM}=log-1`, [TIER_CHANGE]);
    expect(html).toContain("modal-overlay");
    expect(html).toContain("Change details");
    expect(html).toContain("TWDB pass-through 2026");
    // The drawer's two buttons only CLOSE it: there is nothing to submit.
    const drawer = html.slice(html.indexOf('<div class="modal-overlay">'));
    expect(drawer).not.toContain("<form");
    expect(drawer).not.toContain("<input");
  });

  it("a single change and a batch change are labelled differently — in words, never the batch id", () => {
    const html = renderHistory("/plans-rates/history", [TIER_CHANGE, BATCH_CHANGE]);
    expect(html).toContain("Single change");
    expect(html).toContain("Bulk change");
    expect(html).not.toContain("b-2026-001");
  });

  it("BR-SHL-010: the Download control renders now that POST /exports exists (2026-08-10)", () => {
    // EP-RAT-04 declares "Export: CSV (IS-9)" over the compliance log. This
    // assertion was the negative while no export route existed; the
    // list-export lane built it, so it is now the positive.
    const html = renderHistory("/plans-rates/history", [TIER_CHANGE]);
    expect(html).toContain('data-download="button"');
    expect(html).toContain('data-resource="rate-changes"');
    expect(html).not.toContain("XLSX");
  });

  it.todo(
    "US-RAT-010 TC-2/TC-4: repricing an Aug service date on the Aug version, and a 7-year-old version still resolving — server scope (BR-RAT-007/017)",
  );
  it.todo(
    "US-RAT-010 TC-7/TC-8 (isolation): the log is append-only and tenant-scoped — server scope (G5)",
  );
});

describe("US-RAT-011 — the bulk rate change", () => {
  it("US-RAT-011 TC-1: the batch body carries one change, one date and one reason", () => {
    const draft = {
      ...emptyBulkDraft(),
      entities: [
        { type: "schedule", id: "t-res-e" },
        { type: "schedule", id: "t-res-w" },
        { type: "plan", id: "p-res-std" },
      ],
      kind: "percent",
      value: "3.0",
      effectiveFrom: "2027-01-01",
      reason: "Board order 2026-12 annual adjustment",
    };
    expect(bulkDraftReady(draft)).toBe(true);
    expect(bulkBody(draft)).toEqual({
      entities: [
        { type: "schedule", id: "t-res-e" },
        { type: "schedule", id: "t-res-w" },
        { type: "plan", id: "p-res-std" },
      ],
      // The multiplier travels as a STRING; the server does the arithmetic.
      change: { kind: "percent", value: "3.0" },
      effective_from: "2027-01-01",
      reason: "Board order 2026-12 annual adjustment",
    });
  });

  it("US-RAT-011 TC-4 / BR-RAT-040: nothing is offered until entity, value, date AND reason exist", () => {
    const base = {
      ...emptyBulkDraft(),
      entities: [{ type: "schedule", id: "t-res-e" }],
      value: "3.0",
      effectiveFrom: "2027-01-01",
      reason: "Board order",
    };
    expect(bulkDraftReady(base)).toBe(true);
    expect(bulkDraftReady({ ...base, reason: "   " })).toBe(false); // TC-4
    expect(bulkDraftReady({ ...base, effectiveFrom: "" })).toBe(false);
    expect(bulkDraftReady({ ...base, entities: [] })).toBe(false);
    // A value that is not a decimal at all is a SHAPE failure, not a bound.
    expect(bulkDraftReady({ ...base, value: "three percent" })).toBe(false);
    // …and zero IS well-shaped, so the SERVER gets to refuse it as pointless.
    expect(bulkDraftReady({ ...base, value: "0" })).toBe(true);
    expect(t("rating.bulk.percent_zero")).toContain("would change nothing");
  });

  it("US-RAT-011 TC-1 / IS-6: the preview is a synchronous read that writes nothing", async () => {
    let sent: Record<string, unknown> = {};
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async (_input, init) => {
        sent = JSON.parse(String(init?.body)) as Record<string, unknown>;
        return new Response(
          JSON.stringify({
            preview: [
              {
                type: "schedule",
                id: "t-res-e",
                name: "Res Electric · Tiered",
                changes: [{ field: "tier[1].unit_price", before: "0.110000", after: "0.113300" }],
              },
            ],
            fingerprint: "abc123",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      },
    });
    const draft = {
      ...emptyBulkDraft(),
      entities: [{ type: "schedule", id: "t-res-e" }],
      value: "3.0",
      effectiveFrom: "2027-01-01",
      reason: "Board order 2026-12 annual adjustment",
    };
    const preview = await previewRateChange(bulkBody(draft), client);
    expect(sent.preview).toBe(true);
    expect(preview.fingerprint).toBe("abc123");
    // 0.11 × 1.03 = 0.1133 is the SERVER's multiplication, at NUMERIC(18,6),
    // and it renders as the string it sent — nothing is rounded on screen.
    const html = renderToStaticMarkup(<BulkPreview preview={preview} />);
    // Same judgment as the history above: a bulk PREVIEW quotes the payload the
    // server computed — `0.11 × 1.03 = 0.113300` at NUMERIC(18,6) — and its
    // whole job is to show the arithmetic unrounded before anyone approves it.
    // Rounding the left side to `$0.1100` while the right stayed `0.113300`
    // would make the preview disagree with itself.
    expect(html).toContain("0.110000");
    expect(html).toContain("0.113300");
    expect(html).toContain("tier[1].unit_price");
  });

  it("US-RAT-011 TC-1: the apply is the 202 + job_id path, polled through the ONE helper", async () => {
    let polls = 0;
    const client = createApiClient({
      tenant: TEST_TENANT,
      sleep: async () => undefined,
      fetchImpl: async (input) => {
        // Tenant-scoped work, un-tenanted job (PO 2026-08-10): the apply goes to
        // `/api/{tenant}/rate-changes` and its job is polled at `/api/jobs/…`.
        if (String(input).includes("/rate-changes")) {
          return new Response(
            JSON.stringify({ job_id: "job-42", status_url: "/api/jobs/job-42" }),
            {
              status: 202,
              headers: { "Content-Type": "application/json" },
            },
          );
        }
        polls += 1;
        return new Response(
          JSON.stringify({
            id: "job-42",
            kind: "rating.bulk_rate_update",
            status: polls < 2 ? "running" : "succeeded",
            progress: null,
            result_link: null,
            error: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      },
    });
    const accepted = await requestRateChange(
      {
        entities: [{ type: "schedule", id: "t-res-e" }],
        change: { kind: "percent", value: "3.0" },
        effective_from: "2027-01-01",
        reason: "Board order",
      },
      client,
    );
    expect(accepted.job_id).toBe("job-42");
    const job = await client.pollJob(accepted.job_id, { intervalMs: 0 });
    expect(job.status).toBe("succeeded");
    expect(polls).toBe(2);
  });

  it("the apply FAILS HONESTLY while the job store is missing — no fake progress, no toast", async () => {
    // The state of this deployment: `POST /rate-changes` enqueues through
    // core.jobs, which has no registered store, and `GET /jobs/{id}` has no
    // route. The screen renders the server's own words and writes nothing.
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(JSON.stringify({ code: "SYS-001", message_key: "errors.sys-internal" }), {
          status: 500,
          headers: { "Content-Type": "application/json" },
        }),
    });
    const error: unknown = await requestRateChange(
      {
        entities: [{ type: "schedule", id: "t-res-e" }],
        change: { kind: "percent", value: "3.0" },
        effective_from: "2027-01-01",
        reason: "Board order",
      },
      client,
    ).then(
      () => null,
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(500);
    // The text the user reads is the catalog's, not a raw code (BR-SHL-020).
    expect(apiErrorText(error, t)).not.toContain("SYS-001");
    expect(apiErrorText(error, t).length).toBeGreaterThan(10);
    // And the success copy is never reached: a failed job says so instead.
    expect(t("rating.bulk.jobFailed")).toContain("nothing was written");
  });

  it("US-RAT-011 TC-5: a conflicting pending version aborts the WHOLE batch, naming the entity", () => {
    const conflict = new ApiError(409, {
      code: "BIZ-WINDOW",
      message_key: "rating.bulk.entity_window_conflict",
      params: { entity: "Res Water · Inclining", current_from: "2026-09-01" },
      br_ref: "BR-RAT-040",
    });
    const text = apiErrorText(conflict, t);
    expect(text).toContain("Res Water · Inclining");
    expect(text).toContain("2026-09-01");
    expect(text).toContain("Nothing was changed");
  });

  it("US-RAT-011 TC-6 / BR-RAT-040: a replayed batch is refused as a replay, naming the first one", () => {
    const replay = new ApiError(409, {
      code: "BIZ-IDEMPOTENT",
      message_key: "rating.bulk.batch_already_applied",
      params: { batch_id: "b-2026-001", created_at: "2026-12-15 10:00:00+00:00" },
      br_ref: "BR-RAT-040",
    });
    const text = apiErrorText(replay, t);
    expect(text).toContain("b-2026-001");
    expect(text).toContain("never runs twice");
  });

  it("US-RAT-011 TC-7 / BR-SHL-025: a View role sees the bulk control disabled, with the reason", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const state = { q: "", page: 1, per: 50 as const, filters: {}, ...CONFIG.defaultSort };
    queryClient.setQueryData(
      queryKeys.rateChanges(serializeTableParams(state, CONFIG).toString()),
      {
        count: 1,
        next: null,
        previous: null,
        results: [TIER_CHANGE],
      } satisfies Paginated<RateChangeRow>,
    );
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/plans-rates/history"]}>
            <RateChangesTab readOnly timeZone="America/Chicago" dateFormat="MM/DD/YYYY"
                render={bothHalves}
              />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(html).toContain("Bulk rate change");
    expect(html).toContain('disabled=""');
    expect(html).toContain("Your role can view Plans &amp; Rates but not change them.");
  });

  it("BR-SHL-032: the apply confirm names the count, the date and the reason", () => {
    const body = t("rating.bulk.confirm.body", {
      count: 3,
      date: "2027-01-01",
      reason: "Board order 2026-12 annual adjustment",
    });
    expect(body).toContain("3 entries");
    expect(body).toContain("2027-01-01");
    expect(body).toContain("Board order 2026-12 annual adjustment");
    expect(t("rating.bulk.confirm.verb", { count: 3 })).toContain("3");
  });

  it.todo(
    "US-RAT-011 TC-2/TC-3: History filtered by batch, and an Aug service date still pricing pre-batch — server scope (BR-RAT-007)",
  );
  it.todo(
    "US-RAT-011 TC-8 (isolation): a batch touches only the caller's own tariffs — server scope (G5)",
  );
  it.todo(
    "browser scope → Playwright: pick entities → Preview → Apply, and the button stays disabled after a success",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RAT-010@f69a661 (story+rules snapshot hash — EP-RAT-04; co-story US-RAT-011@f69a661)
// generated: 2026-08-09 by story-coder v1 (W1 Plans & Rates frontend lane — S9 History + bulk) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ (227 stories, 459 BR refs, 60 OQs) run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ (399+111 baseline unchanged and green; this packet adds 88 passing + 19 todo across 5 files — every todo is browser-interaction, server/RLS-isolation or unbuilt-neighbour-module scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E3 no test asserts a SUCCESSFUL bulk apply against a live endpoint: core.jobs has no registered store on this deployment and `GET /jobs/{id}` has no route, so the 202→poll path is proved against the ratified 11b §2.17 contract with a mocked transport and the real-deployment failure is asserted as the honest outcome — reported · E4 the bulk modal opens on a click, so the flow's own gating is proved through `bulkDraftReady`/`bulkBody` and the preview rendering through `BulkPreview`
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
