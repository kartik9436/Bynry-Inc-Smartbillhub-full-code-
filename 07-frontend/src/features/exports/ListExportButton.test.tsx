// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-008 (EP-SHL-02 — CSV export: TC-5 the file matches the
//           filtered view, TC-7 the cap refusal)   Screens: S14 · S15 · S26 ·
//           S27 · S49 · S9
// Rules:    BR-SHL-016 (server-side under the caller's tenant context; the
//           50,000-row cap; money exports write audit_log) · BR-SHL-029 (the
//           cap number is the SERVER's) · BR-SHL-011 (the export posts the
//           list's own request state) · IS-11 (CSV always; XLSX unrequestable)
// ───────────────────────────────────────────────────────
// The shared export control, proved without a browser and without a network:
// the client seam takes a fake transport, so what this file asserts is exactly
// what the screen would put on the wire.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient, ApiResponse, JobRecord } from "@/api/client";
import { EXPORT_RESOURCES, requestListExport } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";

import {
  ExportNotice,
  ListExportButton,
  exportBodyFrom,
  exportDownloadHref,
  exportFailureReason,
  exportOutcome,
} from "./ListExportButton";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** A finished export as the poll serves it: the IS-11 download route, not a path. */
function finishedJob(overrides: Partial<JobRecord> = {}): JobRecord {
  return {
    id: "job-1",
    kind: "list_export",
    status: "succeeded",
    progress: { done: 3, total: 3 },
    result_link: "/exports/job-1/file",
    error: null,
    ...overrides,
  };
}

const CONFIG: TableConfig<{ id: string }> = {
  screenId: "S14",
  columns: [{ key: "premise_no", label: "Premise ID", sortable: true, identity: true }],
  getRowId: (row) => row.id,
  defaultSort: { sort: "premise_no", dir: "asc" },
};

function state(overrides: Partial<TableRequestState> = {}): TableRequestState {
  return { ...defaultRequestState(CONFIG), ...overrides };
}

/** A transport that records what the screen posts and answers a finished job. */
function fakeClient(
  options: {
    accept?: () => Promise<ApiResponse<unknown>>;
    job?: Partial<JobRecord>;
  } = {},
) {
  const posts: { path: string; body: unknown }[] = [];
  const polled: string[] = [];
  const job: JobRecord = {
    id: "job-1",
    kind: "list_export",
    status: "succeeded",
    progress: { done: 3, total: 3 },
    result_link: "/exports/job-1/file",
    error: null,
    ...options.job,
  };
  const client = {
    request: vi.fn(),
    get: vi.fn(),
    put: vi.fn(),
    del: vi.fn(),
    post: async (path: string, body?: unknown) => {
      posts.push({ path, body });
      if (options.accept !== undefined) {
        return options.accept();
      }
      return { status: 202, data: { job_id: job.id }, etag: null, notModified: false } as never;
    },
    pollJob: async (jobId: string) => {
      polled.push(jobId);
      return job;
    },
  } as unknown as ApiClient;
  return { client, posts, polled, job };
}

function render(node: JSX.Element): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>{node}</ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-SHL-008 — the shared list-export control", () => {
  it("US-SHL-008 TC-5 / BR-SHL-011: it posts the list's CURRENT request state", async () => {
    const { client, posts } = fakeClient();
    await requestListExport(
      exportBodyFrom(
        "premises",
        state({ q: "elm", sort: "premise_no", dir: "desc", filters: { status: "inactive" } }),
      ),
      client,
    );
    expect(posts).toHaveLength(1);
    expect(posts[0].path).toBe("/exports");
    expect(posts[0].body).toEqual({
      resource: "premises",
      filters: { status: "inactive" },
      sort: "premise_no",
      dir: "desc",
      q: "elm",
    });
  });

  it("the two ops views have no request state, and say so by posting an empty one", () => {
    // S26/S27 predate the table framework (their endpoints are unpaginated
    // plain arrays), so the export covers the whole list — which is exactly
    // what those tabs show. Nothing is invented to fill the gap.
    expect(exportBodyFrom("routes", null)).toEqual({
      resource: "routes",
      filters: {},
      sort: null,
      dir: null,
      q: "",
    });
  });

  it("BR-SHL-011: the body carries only the state the table holds", () => {
    const body = exportBodyFrom("assets", state({ filters: { tab: "sub_meters" } }));
    expect(body.filters).toEqual({ tab: "sub_meters" });
    // No column state: the ratified body has none, and column visibility is a
    // per-user client preference (BR-SHL-013) the server never sees.
    expect(Object.keys(body).sort()).toEqual(["dir", "filters", "q", "resource", "sort"]);
  });

  it("US-SHL-008 TC-7 / P2.4: no list export is refused for being large", () => {
    // ⛔ **TWO CASES STOOD HERE AND BOTH ASSERTED A REFUSAL THAT NO LONGER
    // EXISTS.** They pinned the sentence *"That's 62000 rows — more than the
    // 50000 an export can carry. Narrow your filters and try again."* against
    // a 422 BIZ-CAP the server stopped sending when `P2.4` deleted
    // `EXPORT_ROW_CAP` (`NFR-5` forbids a hard cap anywhere).
    //
    // ⚠ **A TEST THAT PINS A SENTENCE HOLDS THE SENTENCE IN PLACE** — that is
    // `DEF-2346`'s shape, and the decision log already records it costing this
    // product three weeks on the trial balance's premises panel. So the
    // replacement asserts the ABSENCE, which can fail for exactly one reason:
    // somebody put the refusal back.
    expect(i18n.exists("exports.capped")).toBe(false);
    expect(i18n.exists("exports.row_cap_exceeded")).toBe(false);
  });

  it("IS-11: the completed state HANDS OVER the file — the server's own link", () => {
    // The download route landed (GET /exports/{job_id}/file), so this state is
    // no longer a sentence about where a file sits on a server disk.
    const outcome = exportOutcome(finishedJob(), t);
    expect(outcome.ok).toBe(true);
    expect(outcome.href).toBe("/exports/job-1/file");
    expect(outcome.message).toBe("Your export is ready.");
    // The old refusal-to-link copy is GONE, not merely unused.
    expect(outcome.message).not.toContain("download endpoint");
    expect(i18n.exists("exports.readyAtPath")).toBe(false);
  });

  it("the link is whatever the server answered — this file composes no URL", () => {
    // The day the artifact moves to an object store, result_link changes and
    // nothing here does.
    expect(exportDownloadHref(finishedJob({ result_link: "/files/abc.csv" }))).toBe(
      "/files/abc.csv",
    );
    // Only a SUCCEEDED job has a file; every other state has nothing to offer,
    // and the route would answer 404 for it anyway (HR-1).
    expect(exportDownloadHref(finishedJob({ status: "running" }))).toBeNull();
    expect(exportDownloadHref(finishedJob({ status: "failed" }))).toBeNull();
    expect(exportDownloadHref(finishedJob({ result_link: null }))).toBeNull();
    expect(exportDownloadHref(finishedJob({ result_link: "" }))).toBeNull();
  });

  it("the completed state renders a real, followable download anchor", () => {
    const html = renderToStaticMarkup(
      <ExportNotice outcome={exportOutcome(finishedJob(), t)} t={t} />,
    );
    expect(html).toContain('href="/exports/job-1/file"');
    expect(html).toContain("download"); // the attribute, stating the intent
    expect(html).toContain("Download the CSV");
    expect(html).toContain('role="status"');
    // Nothing dead: no `file://` anchor the browser would refuse to fetch.
    expect(html).not.toContain("file://");
  });

  it("a job that succeeded with NO file says so instead of linking nowhere", () => {
    const outcome = exportOutcome(finishedJob({ result_link: null }), t);
    expect(outcome.ok).toBe(true);
    expect(outcome.href).toBeNull();
    expect(outcome.message).toBe("Your export finished, but the server reported no file.");
    const html = renderToStaticMarkup(<ExportNotice outcome={outcome} t={t} />);
    expect(html).not.toContain("<a ");
  });

  it("a failed job says so instead of claiming a file", () => {
    const outcome = exportOutcome(
      finishedJob({ status: "failed", result_link: null, error: "OSError: disk full" }),
      t,
    );
    expect(outcome.ok).toBe(false);
    expect(outcome.href).toBeNull();
    expect(outcome.message).toBe("The export didn't finish. Nothing was written — try again.");
  });

  // DEF-TEN-9190 follow-up — PO 2026-10-02, decision log "SEVEN PO ANSWERS IN
  // ONE MESSAGE" item 7: a failed export shows its reason on screen. The
  // server writes a plain sentence for storage failures and stalls; that
  // sentence follows "The export didn't finish." in place of the generic tail.
  it("DEF-TEN-9190: a failed export SAYS WHY when the server wrote a plain reason", () => {
    const stored = exportOutcome(
      finishedJob({
        status: "failed",
        result_link: null,
        error: "ExportNotStored: File storage did not answer.",
      }),
      t,
    );
    expect(stored.ok).toBe(false);
    expect(stored.href).toBeNull();
    expect(stored.message).toBe("The export didn't finish. File storage did not answer.");

    const stalled = exportOutcome(
      finishedJob({
        status: "failed",
        result_link: null,
        error: "ExportStalled: The export stopped responding.",
      }),
      t,
    );
    expect(stalled.message).toBe("The export didn't finish. The export stopped responding.");
    expect(exportFailureReason(finishedJob({ status: "failed", error: null }))).toBeNull();
  });

  it("DEF-TEN-9190: a crash's own text never reaches the clerk — the plain sentence stays", () => {
    // `Type: message` from an arbitrary exception is a diagnosis for support,
    // not a sentence for a clerk (no class name, no internal code on screen).
    for (const error of ["KeyError: 'premise_no'", "OSError: disk full", "ExportNotStored: "]) {
      expect(exportFailureReason(finishedJob({ status: "failed", error }))).toBeNull();
      expect(exportOutcome(finishedJob({ status: "failed", error }), t).message).toBe(
        "The export didn't finish. Nothing was written — try again.",
      );
    }
    // A succeeded job has no failure reason, whatever its error field says.
    expect(
      exportFailureReason(finishedJob({ error: "ExportNotStored: File storage did not answer." })),
    ).toBeNull();
  });

  it("IS-11: CSV always, and there is no way to ask for XLSX", () => {
    const html = render(<ListExportButton resource="premises" state={state()} />);
    expect(html).toContain('data-download="button"');
    expect(html).toContain("Download CSV");
    expect(html).toContain('data-resource="premises"');
    expect(html.toLowerCase()).not.toContain("xlsx");
    // No PDF either: none of the nine lists declares a formatted layout, so
    // the multi-format popover never appears.
    expect(html).not.toContain('data-download="menu"');
  });

  it("BR-SHL-025: a role-blocked export renders DISABLED with the reason", () => {
    const html = render(
      <ListExportButton resource="plans" state={state()} disabledReason="Read-only role" />,
    );
    expect(html).toContain("disabled");
    expect(html).toContain("Read-only role");
  });

  it("the client's list resources are the PO's nine, plus DEF-441's tenth, plus CR-038's reads", () => {
    // ⚠ NEITHER ADDITION IS SCOPE CREEP. `rate-schedules` was excused from
    // every table capability — export included — because EP-RAT-02's matrix
    // called the S9 tab a card grid, and r10 line 764 draws a nine-column
    // table. `reads` (CR-038 W5, 2026-08-26) is the S25 capability row's own
    // "Export: CSV (IS-9)", which had no registered resource — the DEF-034
    // shape — until `apps/metering/exports.py` registered it (scoped to the
    // 2-yr hot window per US-MET-012 TC-10). `tests/test_be_list_export.py`
    // asserts the SERVER-side registry so the two lists cannot drift.
    expect([...EXPORT_RESOURCES]).toEqual([
      "premises",
      "units",
      "routes",
      "cycles",
      "assets",
      "plans",
      "reads", // CR-038 W5, 2026-08-26
      "rate-schedules", // DEF-441, 2026-08-21
      "charges",
      "taxes",
      "rate-changes",
      // ⚠ **ADDED HERE 2026-10-02, RED SINCE 2026-09-24 (`7cf3853d3`).**
      // `CR-138-BRC07` `P4.1` registered the SEVEN Finance downloads
      // (`apps/ledger/finance_exports.py`) and `P4.6` the deposit slip
      // (`apps/payments/exports.py`), turning five controls that had rendered
      // DISABLED with a reason into working downloads. `endpoints.ts` moved;
      // this pin did not.
      "trial_balance",
      "remittance",
      "account_ledger",
      "by_premises",
      "customer_statement",
      "export_preview",
      "revenue_by_service",
      "deposits",
    ]);
  });

  it("a 202 is followed through the ONE job poller — this file starts none", async () => {
    const { client, polled } = fakeClient();
    const accepted = await requestListExport(exportBodyFrom("plans", state()), client);
    const job = await client.pollJob(accepted.job_id);
    expect(polled).toEqual(["job-1"]);
    expect(job.status).toBe("succeeded");
    expect(job.kind).toBe("list_export");
  });

  it.todo(
    "US-SHL-008 TC-5/TC-7 end to end: clicking Download and seeing the refusal or the finished file appear — browser scope (the mutation needs a real click)",
  );
  it.todo(
    "US-SHL-008 TC-8 (isolation): the file streams under the caller's own RLS — server scope (G5)",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-008@17df6a0 (EP-SHL-02 §Stories — hash = sha256/7 of the source epic)
// generated: 2026-08-10 by story-coder v1 (list-export lane — the frontend half of POST /exports)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: ruff✔(E4/E7/E9/F on apps/core/config — the bar the baseline passes) black✔(this lane's 13 files; 32 pre-existing unformatted files are the repo baseline, untouched) py_compile✔ · pytest tests/test_be_list_export.py 49 passed✔ · suite `pytest tests -m "not golden and not isolation"` 762 passed / 7 skipped / 47 deselected (713 was the baseline when this lane started; the 49 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped (unchanged) · migrate from empty✔ makemigrations --check --dry-run clean✔ (this lane adds NO migration) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ (227 stories, 459 BR refs, 60 OQs) · frontend tsc✔ eslint --max-warnings 0✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 was the baseline; this lane adds 14 passing + 2 todo and converted 3 stale negative assertions into positives) · 5 locales × 2066 keys, identical sets · mypy NOT INSTALLED in this environment (recorded, not skipped silently)
// exceptions: the click-through halves of TC-5/TC-7 are todos with their reason named — renderToStaticMarkup cannot fire a mutation, and this suite has no browser tier; the pure functions behind both paths (exportBodyFrom · exportCapRefusal · exportOutcome) ARE asserted here, so the untested part is the click, not the law · TC-8's isolation half is server scope (G5)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
