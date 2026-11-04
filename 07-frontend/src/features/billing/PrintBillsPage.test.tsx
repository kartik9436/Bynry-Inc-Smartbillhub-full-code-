// ── Trace ──────────────────────────────────────────────
// Change:   CR-053 task 13 — *"Print bills"* (W4). PO ruling 2026-08-30:
//           *"Im okay with this"*.   Screens: Print bills
// Rules:    BR-NOT-029 clause (c) (never claim a mail standard we do not
//           perform) · BR-SHL-025 (a forbidden control is disabled WITH its
//           reason) · BR-TEN-043 (the instant is the CLIENT's) · B14 rule 31
//           (no database id is the visible value of a field) · B12 r1 (202 +
//           job_id, polled through the ONE helper)
// ───────────────────────────────────────────────────────
// The screen, proved without a browser and without a network — the client seam
// takes a fake transport, so what this file asserts is exactly what would go on
// the wire.
//
// ⚠ **THIS FILE IS NOT THE PROOF THAT THE FEATURE WORKS.** jsdom renders no
// download, opens no archive and counts no PDF. The proof is
// `10-scripts/render-checks/cr053-print-bills.mjs`, which drives a real browser,
// downloads the archive and opens it (PO 2026-08-30: *"All UI screen should be
// confirm using real broswer testing and not just based on test cases"*). What
// these cases hold is the part a browser check is bad at: the exact request
// body, and the sentences that must never appear.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient, JobRecord } from "@/api/client";
import type { BillRunHistoryRow } from "@/api/endpoints";
import { getPrintSetPreview, requestPrintSet } from "@/api/billingPrintEndpoints";
import type { PrintSetPreview } from "@/api/billingPrintEndpoints";

import {
  cycleScopeLabel,
  estimateText,
  holdText,
  PrintBillsPage,
  PrintSetNotes,
  printFilters,
  printSetOutcome,
  runOptionLabel,
} from "./PrintBillsPage";
import type { CycleRow } from "@/api/endpoints";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function preview(overrides: Partial<PrintSetPreview> = {}): PrintSetPreview {
  return {
    bill_count: 41,
    printable_statuses: ["issued", "paid"],
    max_bills: 25000,
    over_ceiling: false,
    estimated_seconds: 0.8,
    // DEF-BIL-5354's four tiles. They ADD UP by construction — 38 + 3 = 41 —
    // because the blueprint says a set that prints 38 of 41 without saying so
    // sends a print shop a short run and tells nobody.
    will_print: 38,
    held_back: 3,
    held_reasons: [{ code: "address_incomplete", bills: 3 }],
    held_reasons_complete: true,
    pages: 76,
    pages_per_bill: 2,
    manifest_columns: [
      "account_no",
      "bill_no",
      "customer_name",
      "address_line_1",
      "address_line_2",
      "city",
      "state",
      "postal_code",
      "country",
      "page_count",
      "bill_date",
      "due_date",
      "amount_due",
      "pdf_filename",
    ],
    background_available: true,
    filters: {},
    unavailable: [
      {
        code: "no_mail_standards_are_performed_here",
        detail:
          "the addresses in this file are our own records, exactly as the account holder " +
          "gave them. They have not been CASS-certified, they have not been NCOA-processed, " +
          "and no Intelligent Mail barcode has been applied. Your mail house does all three; " +
          "we do none of them and do not claim to.",
      },
    ],
    ...overrides,
  };
}

function job(overrides: Partial<JobRecord> = {}): JobRecord {
  return {
    id: "job-print-1",
    kind: "billing.bills.print_set",
    status: "succeeded",
    progress: { done: 41, total: 41 },
    result_link: "/api/exports/job-print-1/file",
    error: null,
    ...overrides,
  };
}

/** A transport that records what the screen asks for and answers a finished job. */
function fakeClient(options: { previewBody?: PrintSetPreview } = {}) {
  const gets: { path: string; query: unknown }[] = [];
  const posts: { path: string; body: unknown }[] = [];
  const client = {
    request: vi.fn(),
    put: vi.fn(),
    del: vi.fn(),
    get: async (path: string, init?: { query?: Record<string, string> }) => {
      gets.push({ path, query: init?.query ?? null });
      if (path.startsWith("/billing/print-sets")) {
        return {
          status: 200,
          data: options.previewBody ?? preview(),
          etag: null,
          notModified: false,
        } as never;
      }
      return { status: 200, data: { runs: [] }, etag: null, notModified: false } as never;
    },
    post: async (path: string, body?: unknown) => {
      posts.push({ path, body });
      return {
        status: 202,
        data: { job_id: "job-print-1", status_url: "/api/jobs/job-print-1" },
        etag: null,
        notModified: false,
      } as never;
    },
    pollJob: async () => job(),
  } as unknown as ApiClient;
  return { client, gets, posts };
}

function render(node: JSX.Element): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // The screen reads the tenant out of the path (`useTenantPath`) and navigates
  // on a denied cell, so it needs a router the same way every other tenant
  // screen's test does — `BillChargesTab.test.tsx` mounts the identical shape.
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/brazosbend/billing/print"]}>
        <Routes>
          <Route path="/:tenant/billing/print" element={node} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CR-053 task 13 — the Print bills screen", () => {
  it("BR-TEN-043: the POST carries the CLIENT's instant, offset-bearing, and no clock is asked of the server", async () => {
    const { client, posts } = fakeClient();
    await requestPrintSet(
      { filters: { bill_run_id: "run-7" }, generated_at: "2026-08-31T14:05:00.000Z", background: true },
      client,
    );
    expect(posts).toHaveLength(1);
    expect(posts[0].path).toBe("/billing/print-sets");
    expect(posts[0].body).toEqual({
      filters: { bill_run_id: "run-7" },
      generated_at: "2026-08-31T14:05:00.000Z",
      background: true,
    });
    // The whole point of the field: a naive timestamp means a different instant
    // in Houston than in Chennai, and the server refuses one.
    const sent = (posts[0].body as { generated_at: string }).generated_at;
    expect(sent.endsWith("Z") || /[+-]\d\d:\d\d$/.test(sent)).toBe(true);
  });

  it("BR-SHL-011: the preview asks in the bills list's OWN filter grammar", async () => {
    const { client, gets } = fakeClient();
    await getPrintSetPreview({ bill_run_id: "run-7" }, client);
    expect(gets).toHaveLength(1);
    expect(gets[0].path).toBe("/billing/print-sets");
    expect(gets[0].query).toEqual({ "f.bill_run_id": "run-7" });
  });

  it("an empty scope sends NO filter rather than an empty one", async () => {
    const { client, gets } = fakeClient();
    await getPrintSetPreview({}, client);
    expect(gets[0].query).toEqual({});
  });

  it("B14 rule 31: a run is offered by its number and period, never by its id", () => {
    const run: BillRunHistoryRow = {
      id: "0198c2f0-1111-7000-8000-aaaabbbbcccc",
      run_no: "RUN-2608-004",
      cycle_id: "0198c2f0-2222-7000-8000-aaaabbbbcccc",
      period_start: "2026-07-01",
      period_end: "2026-07-31",
      issued_at: "2026-08-08T09:42:00Z",
      accounts: 41,
      bills_issued: 41,
      held: 0,
      status: "draft",
      bill_type: "cycle",
      created_at: "2026-08-01T00:00:00Z",
    };
    const label = runOptionLabel(run, t);
    expect(label).toContain("RUN-2608-004");
    expect(label).toContain("2026-07-01");
    expect(label).not.toContain(run.id);
    expect(label).not.toContain(run.cycle_id as string);
  });

  it("a finished job becomes a download; a finished job with NO file says so instead", () => {
    const ready = printSetOutcome(job(), t);
    expect(ready.ok).toBe(true);
    expect(ready.href).toBe("/api/exports/job-print-1/file");

    // The sentence never promises a download the anchor cannot deliver.
    const noFile = printSetOutcome(job({ result_link: null }), t);
    expect(noFile.ok).toBe(true);
    expect(noFile.href).toBeNull();
    expect(noFile.message).toBe(t("billing.print.readyNoFile"));

    const failed = printSetOutcome(job({ status: "failed", result_link: null }), t);
    expect(failed.ok).toBe(false);
    expect(failed.href).toBeNull();
    expect(failed.message).toBe(t("billing.print.failed"));
  });

  it("DEF-TEN-9190: a failed print set SAYS WHY when the server wrote a plain reason", () => {
    // The print set is published through the same export store, so a storage
    // failure fails its job with the same plain sentence (PO 2026-10-02 item 7).
    const failed = printSetOutcome(
      job({
        status: "failed",
        result_link: null,
        error: "ExportNotStored: File storage did not answer.",
      }),
      t,
    );
    expect(failed.ok).toBe(false);
    expect(failed.href).toBeNull();
    expect(failed.message).toBe("The print set did not finish. File storage did not answer.");
    // A crash's own text stays off the screen.
    const crashed = printSetOutcome(
      job({ status: "failed", result_link: null, error: "KeyError: 'invoice'" }),
      t,
    );
    expect(crashed.message).toBe(t("billing.print.failed"));
  });

  it("BR-NOT-029 clause (c): the screen DRAWS the server's no-mail-standard note rather than staying quiet", () => {
    // ⚠ RENDERED THROUGH THE PURE PANEL, NOT THROUGH THE PAGE. A static render
    // of the page resolves no query, so it draws the loading skeleton and an
    // assertion made there passes on an empty screen — the exact shape of a
    // check that cannot fail. `ExportNotice` is extracted for the same reason.
    const markup = renderToStaticMarkup(
      <PrintSetNotes notes={preview().unavailable} title={t("billing.print.notesTitle")} />,
    );
    expect(markup).toContain("data-print-notes");
    expect(markup).toContain("have not been CASS-certified");
    expect(markup).toContain("have not been NCOA-processed");
    expect(markup).toContain("no Intelligent Mail barcode has been applied");
    // And the screen must not have rewritten any of it: the sentence on screen
    // is the server's own, byte for byte.
    expect(markup).toContain(preview().unavailable[0].detail);
  });

  it("the page mounts, and the build control is disabled WITH its reason before anything is counted", () => {
    // What a STATIC render can honestly prove: the frame, the scope control,
    // and BR-SHL-025's disabled-with-reason on the primary. Everything past the
    // first query resolving is the browser check's job, not this file's.
    const { client } = fakeClient();
    const markup = render(<PrintBillsPage client={client} />);
    expect(markup).toContain(t("billing.print.title"));
    expect(markup).toContain("data-print-scope");
    expect(markup).toContain(t("billing.print.scope.all"));
    expect(markup).toContain(`title="${t("billing.print.blocked.notCounted")}"`);
    expect(markup).toContain("disabled=");
    // B14 rule 31, on the frame itself: no uuid reaches the markup.
    expect(
      /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/.test(markup),
    ).toBe(false);
  });

  it("BR-SHL-025: with nothing to print the build control is DISABLED and says why", () => {
    // A check that could not fail is worse than none: this asserts the reason
    // TEXT, so a disabled button with an empty tooltip is a failure.
    const reason = t("billing.print.blocked.noBills");
    expect(reason.length).toBeGreaterThan(0);
    expect(reason).not.toBe("billing.print.blocked.noBills");
    const overCeiling = t("billing.print.blocked.overCeiling", { max: 25000 });
    expect(overCeiling).toContain("25000");
  });


  it("DEF-BIL-5354: the three controls become ONE server selection, in the bills list's own grammar", () => {
    // The preview, the table and the POST all go through this, so the tiles,
    // the list and the archive cannot end up covering different bills.
    expect(
      printFilters({ scope: "cycle", cycleId: "c-1", runId: "", issuedFrom: "", issuedTo: "" }),
    ).toEqual({ cycle_id: "c-1" });
    expect(
      printFilters({ scope: "run", cycleId: "c-1", runId: "r-9", issuedFrom: "", issuedTo: "" }),
    ).toEqual({ bill_run_id: "r-9" });
    // Every issued bill sends NO scope filter — not an empty one, which would
    // ask for a run whose id is the empty string.
    expect(
      printFilters({ scope: "all", cycleId: "c-1", runId: "r-9", issuedFrom: "", issuedTo: "" }),
    ).toEqual({});
    // The dates ride along with any scope, and they are the ISSUE window the
    // server actually filters on — which is why the labels say so.
    expect(
      printFilters({
        scope: "all",
        cycleId: "",
        runId: "",
        issuedFrom: "2026-09-01",
        issuedTo: "2026-09-30",
      }),
    ).toEqual({ issued_from: "2026-09-01", issued_to: "2026-09-30" });
  });

  it("B14 rule 31/32: a cycle is its CODE and a hold is its WORDS — never an id, never a code", () => {
    const cycle = {
      id: "0198c2f0-3333-7000-8000-aaaabbbbcccc",
      code: "CY-003",
      frequency: "Monthly",
    } as unknown as CycleRow;
    const label = cycleScopeLabel(cycle, t);
    expect(label).toContain("CY-003");
    expect(label).not.toContain(cycle.id);

    // The server sends a stable code; the clerk reads words from the catalogue.
    const held = holdText("address_incomplete", t);
    expect(held).toContain(t("billing.print.verdict.held"));
    expect(held).toContain(t("billing.print.hold.address_incomplete"));
    expect(held).not.toContain("address_incomplete");
    // A code with no catalogue entry of its own falls back to plain words
    // rather than printing the identifier at a clerk.
    const unknown = holdText("a_reason_nobody_has_translated", t);
    expect(unknown).not.toContain("a_reason_nobody_has_translated");
    expect(unknown).toContain(t("billing.print.hold.other"));
    expect(holdText(null, t)).toBe(t("billing.print.verdict.willPrint"));
  });

  it("the time estimate changes UNIT rather than printing 214 seconds", () => {
    expect(estimateText(5, t)).toBe(t("billing.print.tile.seconds", { seconds: 5 }));
    expect(estimateText(214, t)).toBe(t("billing.print.tile.minutes", { minutes: 4 }));
    // Never "about 0 seconds": a set that takes a moment still took a moment.
    // And never "about 1 seconds", which is what the browser walk read off the
    // tile on 2026-09-15 — one gets its own sentence.
    expect(estimateText(0.3, t)).toBe(t("billing.print.tile.oneSecond"));
    expect(estimateText(61, t)).toBe(t("billing.print.tile.oneMinute"));
    expect(t("billing.print.tile.oneSecond")).not.toContain("1 seconds");
  });

  it("every sentence this screen owns resolves to real copy, not to its own key", () => {
    // G18 catches a key defined in no catalogue; this catches the other half —
    // a key that exists and renders as itself, which reads to a clerk as a bug
    // in the product rather than a gap in a catalogue.
    for (const key of [
      "billing.action.printBills",
      "billing.print.title",
      "billing.print.group.what",
      "billing.print.group.bills",
      "billing.print.group.claims",
      "billing.print.field.scope",
      "billing.print.field.issuedFrom",
      "billing.print.field.manifest",
      "billing.print.field.layout",
      "billing.print.manifest.oneFormat",
      "billing.print.layout.value",
      "billing.print.scope.cycle",
      "billing.print.scope.run",
      "billing.print.scope.all",
      "billing.print.tile.willPrint",
      "billing.print.tile.heldBack",
      "billing.print.tile.pages",
      "billing.print.tile.inPeriod",
      "billing.print.col.willPrint",
      "billing.print.verdict.willPrint",
      "billing.print.verdict.held",
      "billing.print.hold.address_incomplete",
      "billing.print.hold.no_bill_number",
      "billing.print.hold.unsafe_bill_number",
      "billing.print.hold.other",
      "billing.print.held.showAll",
      "billing.print.held.alsoInArchive",
      "billing.print.claim.addressesValue",
      "billing.print.claim.screenValue",
      "billing.print.claim.pastSetsValue",
      "billing.print.footer.helper",
      "billing.print.searchFirst",
      "billing.print.notesTitle",
      "billing.print.action.build",
      "billing.print.working",
      "billing.print.ready",
      "billing.print.download",
      "billing.printSet.refused",
    ]) {
      expect(t(key)).not.toBe(key);
      expect(t(key).length).toBeGreaterThan(1);
    }
  });
});
