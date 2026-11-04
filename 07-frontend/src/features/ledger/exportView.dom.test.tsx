// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change: CR-140-BRC09 · Finance blueprint `P4.12` — 6·2 **Export**, p069–p071
// Rules:  IS-9 (a download carries the current filters AND the visible
//         columns) · `P4.13`'s ruling (*"all selected columns will go in
//         downloaded file"*) · BR-LED-004 (every figure drills back; a
//         hand-over is recorded once) · BR-LED-017 (an export needs the range
//         CLOSED) · B14 rule 31 (no database id is ever a visible value) ·
//         BR-SHL-025 (a control that cannot act says why)
// ───────────────────────────────────────────────────────
/*
WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first, per hard-won law 7
---------------------------------------------------------------------------
**(a) ASSERTING THE COLUMN KEYS AGAINST THEMSELVES.** A case listing the five
account column names would agree with a `GROUPINGS` table holding the same five
and would say NOTHING about the server, which is the only party that can drop a
name it does not recognise — silently, by `columns_for()`'s own design. So the
cross-language half of that check is a GATE
(`10-scripts/gates/g113_export_columns_agree.py`) that reads
`apps/ledger/finance_exports.py`, and what is asserted HERE is the property the
gate cannot see: the ORDER the clerk left the chooser in reaches the body.

**(b) A BARE `MemoryRouter` WITH NO `/:tenant` ROUTE.** `useTenantPath` then
builds `//finance/...` — a protocol-relative URL to another host, which reads
as a perfectly good string to `toContain`. Every render here mounts under the
real path pattern.

**(c) A FIXTURE WHOSE ROWS ARE ALL COMPLETE.** A preview with a code on every
account would draw no `Not available` and the absence cases would pass over a
component that cannot render one. The fixture carries an account with no code
and an authority with a `null` collected figure.

**(d) `toContain` OVER A CLASS NAME.** A sibling proved today that `text-right`
on a `PlainTable` cell renders nothing while `toContain` passes. Nothing here
asserts a class; the cases assert TEXT, hrefs and what was posted.
*/
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { ApiClient, JobRecord } from "@/api/client";
import type { ExportPreviewResponse } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import {
  EXPORT_GROUPINGS,
  ExportView,
  GROUPINGS,
  absentReasonKey,
  defaultVisibleColumns,
  downloadBody,
  exportGroupingFrom,
  sendChecks,
} from "./ExportView";

afterEach(cleanup);

const TENANT = "brazosbend";
const translate = (key: string) => key;

const PREVIEW: ExportPreviewResponse = {
  period: { start: "2026-08-01", end: "2026-08-31" },
  target: "qbo",
  granularity: "summary",
  currency: "USD",
  entries: 2,
  rows: [
    {
      code: "1200",
      name: "Accounts receivable",
      type: "asset",
      account_id: "a1",
      target_ref: "12",
      debit: "15066.000000",
      credit: "0.000000",
      currency: "USD",
      window: { start: "2026-08-01", end: "2026-08-31" },
    },
    {
      // (c) — the account with no code in the accounting package. It is what
      // blocks the whole hand-over (BR-LED-014 / US-LED-006 TC-5), so a clerk
      // has to be able to see WHICH one.
      code: "6900",
      name: "Bad debt",
      type: "expense",
      account_id: "a3",
      target_ref: null,
      debit: "0.000000",
      credit: "0.000000",
      currency: "USD",
      window: { start: "2026-08-01", end: "2026-08-31" },
    },
  ],
  total_debits: "15066.000000",
  total_credits: "15066.000000",
  period_total_debits: "15066.000000",
  period_total_credits: "15066.000000",
  balanced: true,
  period_closed: true,
  missing_refs: ["6900 · Bad debt"],
  already_exported: null,
  sendable: false,
  cost_section: {
    source: "register",
    in_trial_balance: false,
    entries: 0,
    cost_total: "0.000000",
    currency: "USD",
    rows: [],
    missing_refs: [],
    unavailable: [],
    settled: {
      count: 0,
      total: "0.000000",
      currency: "USD",
      source: "journal",
      in_trial_balance: true,
      label: "IN THE BOOKS",
    },
  },
};

const AUTHORITY_ROWS = [
  {
    account_id: "t1",
    code: "2200-01",
    name: "Bexar County",
    remitting_basis: "collected",
    billed: "531.140000",
    // (c) — payments publishes no allocation for this window. `null`, never
    // `0.00`: a zero reads as "nothing was collected" about money that was.
    collected: null,
    remitted: "0.000000",
    outstanding_billed: "531.140000",
    outstanding_collected: null,
  },
];

function fakeClient(over: { job?: Partial<JobRecord> } = {}) {
  const posts: { path: string; body: unknown }[] = [];
  const gets: string[] = [];
  const job: JobRecord = {
    id: "job-9",
    kind: "list_export",
    status: "succeeded",
    progress: { done: 1, total: 1 },
    result_link: "/exports/job-9/file",
    error: null,
    ...over.job,
  };
  const client = {
    request: vi.fn(),
    put: vi.fn(),
    del: vi.fn(),
    get: async (path: string) => {
      gets.push(path);
      if (path.startsWith("/finance/export/preview")) {
        return { status: 200, data: PREVIEW, etag: null, notModified: false };
      }
      if (path.startsWith("/finance/export/extracts/authority")) {
        return {
          status: 200,
          data: {
            kind: "authority",
            available: true,
            currency: "USD",
            period: { start: "2026-08-01", end: "2026-08-31" },
            rows: AUTHORITY_ROWS,
          },
          etag: null,
          notModified: false,
        };
      }
      return {
        status: 200,
        data: {
          kind: "other",
          available: true,
          currency: "USD",
          period: { start: "2026-08-01", end: "2026-08-31" },
          rows: [],
        },
        etag: null,
        notModified: false,
      };
    },
    post: async (path: string, body?: unknown) => {
      posts.push({ path, body });
      return { status: 202, data: { job_id: job.id }, etag: null, notModified: false };
    },
    pollJob: async () => job,
  } as unknown as ApiClient;
  return { client, posts, gets };
}

function mount(client: ApiClient, extra: Partial<Parameters<typeof ExportView>[0]> = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* (b) — the REAL path pattern, so `useTenantPath` resolves. */}
        <MemoryRouter initialEntries={[`/${TENANT}/finance/export?view=export`]}>
          <Routes>
            <Route
              path="/:tenant/finance/export"
              element={
                <ExportView
                  client={client}
                  t={translate}
                  dateFormat="YYYY-MM-DD"
                  period={{ start: "2026-08-01", end: "2026-08-31" }}
                  target="qbo"
                  onTargetChange={() => undefined}
                  onSend={() => undefined}
                  onDrill={() => undefined}
                  {...extra}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("P4.12 — what the file is asked for", () => {
  it("carries the ticked columns IN THE ORDER THEY ARE TICKED, not the drawn order", async () => {
    // `P4.13`'s ruling is about the clerk's order, and the whole point of
    // asserting it is that re-deriving the list from `GROUPINGS` would give the
    // DRAWN order and pass a test that used the drawn order as its expectation.
    const reordered = ["credit", "debit", "gl_account"];
    const body = downloadBody({
      grouping: "account",
      from: "2026-08-01",
      to: "2026-08-31",
      target: "qbo",
      granularity: "summary",
      visible: reordered,
      q: "",
    });
    expect(body.columns).toEqual(reordered);
    expect(body.resource).toBe("export_preview");
  });

  it("sends target and granularity ONLY for the grouping whose resource declares them", () => {
    // `export_preview` declares `filters=("from","to","target","granularity")`;
    // the other three declare `("from","to")`. The kernel IGNORES an undeclared
    // filter, so sending them everywhere would be harmless and dishonest.
    const account = downloadBody({
      grouping: "account", from: "a", to: "b", target: "xero",
      granularity: "weekly", visible: [], q: "",
    });
    expect(account.filters).toEqual({
      from: "a", to: "b", target: "xero", granularity: "weekly",
    });
    for (const grouping of ["service", "premises", "authority"] as const) {
      const other = downloadBody({
        grouping, from: "a", to: "b", target: "xero",
        granularity: "weekly", visible: [], q: "",
      });
      expect(Object.keys(other.filters).sort()).toEqual(["from", "to"]);
    }
  });

  it("gives each grouping its OWN export resource, and no two share one", () => {
    const resources = EXPORT_GROUPINGS.map((one) => GROUPINGS[one].resource);
    expect(new Set(resources).size).toBe(EXPORT_GROUPINGS.length);
  });

  it("starts with the two window columns UNTICKED, so today's file does not change shape", () => {
    expect(defaultVisibleColumns("account")).toEqual([
      "gl_account", "name", "target_ref", "debit", "credit",
    ]);
    // Every other grouping shows everything it has.
    for (const grouping of ["service", "premises", "authority"] as const) {
      expect(defaultVisibleColumns(grouping)).toEqual(
        GROUPINGS[grouping].columns.map((column) => column.key),
      );
    }
  });

  it("falls back to the landing grouping rather than 404ing (BR-SHL-011)", () => {
    expect(exportGroupingFrom("service")).toBe("service");
    expect(exportGroupingFrom("nonsense")).toBe("account");
    expect(exportGroupingFrom(null)).toBe("account");
  });
});

describe("P4.12 — the four checks are the SERVER's four gates", () => {
  it("reads each check off its own served field", () => {
    expect(sendChecks(PREVIEW).map((check) => [check.id, check.passed])).toEqual([
      ["closed", true],
      ["notSent", true],
      ["balances", true],
      // `missing_refs` carries one account, so the codes gate is the failing one.
      ["codes", false],
    ]);
  });

  it("never re-derives `sendable` from the four", () => {
    // `sendable` is false on this fixture while three of the four checks pass.
    // A screen that ANDed the four would enable a button the server refuses.
    expect(PREVIEW.sendable).toBe(false);
    expect(sendChecks(PREVIEW).filter((check) => check.passed)).toHaveLength(3);
  });
});

describe("P4.12 — three absences, three reasons", () => {
  it("never gives one sentence to three different absences", () => {
    expect(absentReasonKey("target_ref")).toBe("finance.export.refMissing");
    expect(absentReasonKey("collected")).toBe("finance.export.collectedAbsent");
    expect(absentReasonKey("outstanding_collected")).toBe("finance.export.collectedAbsent");
    expect(absentReasonKey("debit")).toBe("finance.export.valueAbsent");
  });
});

describe("P4.12 — the view in a browser", () => {
  it("draws the account preview, and the account with no code is visible on its row", async () => {
    const { client } = fakeClient();
    mount(client);
    await waitFor(() => expect(screen.getByText("1200")).toBeInTheDocument());
    expect(screen.getByText("6900")).toBeInTheDocument();
    // The missing code renders as a stated absence rather than as a blank cell.
    expect(screen.getAllByText("finance.absent").length).toBeGreaterThan(0);
  });

  it("puts the four groupings in the drawn order and nothing else", async () => {
    const { client } = fakeClient();
    mount(client);
    const picker = await screen.findByLabelText("finance.export.groupBy");
    const options = within(picker).getAllByRole("option").map((one) => one.getAttribute("value"));
    expect(options).toEqual(["account", "service", "premises", "authority"]);
  });

  it("disables Weekly on a grouping that has no window to split (BR-SHL-025)", async () => {
    const user = userEvent.setup();
    const { client } = fakeClient();
    mount(client);
    const detail = await screen.findByLabelText("finance.export.detail");
    expect(detail).not.toBeDisabled();
    await user.selectOptions(await screen.findByLabelText("finance.export.groupBy"), "premises");
    expect(await screen.findByLabelText("finance.export.detail")).toBeDisabled();
    // The reason is RENDERED, not only a tooltip — `DEF-SHL-4043`'s lesson.
    expect(screen.getByText("finance.export.detail.accountOnly")).toBeInTheDocument();
  });

  it("refuses Send on a grouping that is an extract, and says why", async () => {
    const user = userEvent.setup();
    const { client } = fakeClient();
    mount(client);
    await user.selectOptions(await screen.findByLabelText("finance.export.groupBy"), "authority");
    await user.click(screen.getByRole("button", { name: "finance.export.apply" }));
    await waitFor(() =>
      expect(screen.getByText("finance.export.sendAccountsOnly")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "finance.export.send" })).toBeDisabled();
  });

  it("switches the table to the chosen grouping's OWN columns and read", async () => {
    const user = userEvent.setup();
    const { client, gets } = fakeClient();
    mount(client);
    await user.selectOptions(await screen.findByLabelText("finance.export.groupBy"), "authority");
    await user.click(screen.getByRole("button", { name: "finance.export.apply" }));
    await waitFor(() => expect(screen.getByText("Bexar County")).toBeInTheDocument());
    expect(gets.some((path) => path.startsWith("/finance/export/extracts/authority"))).toBe(true);
    // ⚠ **EXACTLY TWO ABSENCES ON THIS ROW, AND THAT IS THE ASSERTION.**
    // `collected` and `outstanding_collected` are `null` and render as stated
    // absences; `remitted` is a real `0.000000` and renders as **$0.00**. A
    // case that simply asserted *"no $0.00 anywhere"* would go red on the
    // honest zero and would say nothing about the two nulls — which is the
    // confusion the null-is-not-zero rule exists to prevent, wearing a test.
    const row = screen.getByText("Bexar County").closest("tr") as HTMLElement;
    expect(within(row).getAllByText("finance.absent")).toHaveLength(2);
    expect(within(row).getByText("$0.00")).toBeInTheDocument();
  });

  it("posts the download with the visible columns and hands back the file link", async () => {
    const user = userEvent.setup();
    const { client, posts } = fakeClient();
    mount(client);
    await waitFor(() => expect(screen.getByText("1200")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Download CSV" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].path).toBe("/exports");
    expect(posts[0].body).toMatchObject({
      resource: "export_preview",
      filters: { from: "2026-08-01", to: "2026-08-31", target: "qbo", granularity: "summary" },
      columns: ["gl_account", "name", "target_ref", "debit", "credit"],
    });
    // The file is HANDED OVER, not merely promised: a toast saying "queued"
    // over no link is a download control that downloads nothing.
    // ⚠ `ExportNotice` renders through the `t` this view was GIVEN, so the name
    // here is the key the stub echoes — unlike `DownloadButton`, which reaches
    // for `useTranslation` itself and therefore carries the real English.
    const link = await screen.findByRole("link", { name: "exports.download" });
    expect(link).toHaveAttribute("href", "/exports/job-9/file");
  });

  it("hands the SEND the window the clerk was looking at, with its preview", async () => {
    const user = userEvent.setup();
    const { client } = fakeClient();
    const sent: unknown[] = [];
    mount(client, { onSend: (handover) => sent.push(handover) });
    await waitFor(() => expect(screen.getByText("1200")).toBeInTheDocument());
    const sendable: ExportPreviewResponse = { ...PREVIEW, sendable: true, missing_refs: [] };
    cleanup();
    const second = fakeClient();
    (second.client as unknown as { get: unknown }).get = async (path: string) => {
      if (path.startsWith("/finance/export/preview")) {
        return { status: 200, data: sendable, etag: null, notModified: false };
      }
      return { status: 200, data: { kind: "x", currency: "USD",
        period: { start: "", end: "" }, rows: [] }, etag: null, notModified: false };
    };
    mount(second.client, { onSend: (handover) => sent.push(handover) });
    const button = await screen.findByRole("button", { name: "finance.export.send" });
    await waitFor(() => expect(button).not.toBeDisabled());
    await user.click(button);
    expect(sent).toHaveLength(1);
    expect(sent[0]).toMatchObject({
      from: "2026-08-01",
      to: "2026-08-31",
      granularity: "summary",
    });
  });

  it("opens the account code to its lines (BR-LED-004), and the extracts do not pretend to", async () => {
    const user = userEvent.setup();
    const drilled: string[] = [];
    const { client } = fakeClient();
    mount(client, { onDrill: (code) => drilled.push(code) });
    await waitFor(() => expect(screen.getByText("1200")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "1200" }));
    expect(drilled).toEqual(["1200"]);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/07 Finance Blueprint.pdf p069–p071 read as IMAGES (B14
//         rule 42) · 06-backend/apps/ledger/finance_exports.py ·
//         06-backend/apps/tenancy/exports.py `columns_for`
// generated: 2026-09-24 by LANE FIN-P4B
// exceptions: the CROSS-LANGUAGE half of the column contract is not here and
//         cannot be — a vitest case cannot read Python. It is
//         `10-scripts/gates/g113_export_columns_agree.py`, and (a) above says
//         why a same-file assertion would have been worse than nothing.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
