// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-194-BRC10 — Refused work, the fifth pane of *From the field*
//           (PO 2026-10-26, *"store on both"*)
// Rules:    BR-WRK-071 · NFR-3 · B14 rules 15 · 31 · 33 · CLAUDE.md hard rule 3
//           · hard-won law 2 (the door is asserted by ADDRESS)
// ───────────────────────────────────────────────────────
//
// Mounted under the REAL path patterns (`/:tenant/work/field…`), never a bare
// MemoryRouter (hard-won law 2's fixture clause): the photographs' addresses
// carry the tenant, and `//work-orders/…` would read as a good string.
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { activeWorkTab } from "../WorkShell";
import { FieldDeskPage } from "./FieldDeskPage";
import { commits, fakeClient } from "./fieldTestClient";
import type { Call } from "./fieldTestClient";
import type { RefusedDetail, RefusedRow } from "./refusedWorkEndpoints";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

const COPY_ID = "0c1d2e3f-2222-4b4b-8d8d-000000000028";
const ORDER_ID = "0b6f2c1e-1111-4a4a-9c9c-000000000028";
const ORTIZ_ID = "0a0a0a0a-3333-4c4c-8e8e-00000000000d";

function row(over: Partial<RefusedRow> = {}): RefusedRow {
  return {
    id: COPY_ID,
    door: "job",
    kind: "reading",
    status: "open",
    reason: "not_your_job",
    message_key: "work.mobile.not_your_job",
    params: { order_no: "WO-0028" },
    technician: "D. Ortiz",
    technician_id: ORTIZ_ID,
    work_order: { id: ORDER_ID, order_no: "WO-0028" },
    captured_at: "2026-10-26T14:02:00Z",
    first_refused_at: "2026-10-26T17:40:00Z",
    last_refused_at: "2026-10-26T17:40:00Z",
    refusal_count: 1,
    photographs: 2,
    note: "",
    reviewed_by: null,
    reviewed_at: null,
    applied_by: null,
    applied_at: null,
    ...over,
  };
}

function detail(over: Partial<RefusedDetail> = {}): RefusedDetail {
  return {
    ...row(),
    work: { kind: "reading", reading: { prompt: "Final read", value: "52410", unit: "kWh", flagged: false } },
    photos: [
      { state: "uploaded", attachment_id: "0d0d0d0d-4444-4d4d-8f8f-000000000001", work_order_id: ORDER_ID },
      { state: "on_phone" },
    ],
    can_apply: true,
    ...over,
  };
}

const FACETS = {
  reasons: [{ reason: "not_your_job", message_key: "work.mobile.not_your_job" }],
  kinds: ["reading"],
  technicians: [{ id: ORTIZ_ID, name: "D. Ortiz" }],
};

function page(rows: RefusedRow[]) {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    counts: { open: rows.length, reviewed: 0, applied: 0, applied_later: 0 },
    facets: FACETS,
  };
}

function Where() {
  return <span data-testid="where">{useLocation().pathname}</span>;
}

function mount(client: ApiClient, start = `/${TENANT}/work/field/refused`) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[start]}>
          <Routes>
            <Route path="/:tenant/work/field" element={<FieldDeskPage view="results" client={client} />} />
            <Route path="/:tenant/work/field/refused" element={<FieldDeskPage view="refused" client={client} />} />
          </Routes>
          <Where />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const READS = (calls: Call[]) => calls.filter((c) => c.path === "/work/refused-items");

describe("CR-194-BRC10 — Refused work: what the server refused, kept for the office", () => {
  it("the door: the fifth sub-tab opens /work/field/refused and keeps the Work tab lit", async () => {
    const calls: Call[] = [];
    mount(fakeClient(calls, { "/work/acceptance-queue": { count: 0, next: null, previous: null, results: [], tally: {} }, "/work/refused-items": page([]) }), `/${TENANT}/work/field`);
    fireEvent.click(screen.getByRole("tab", { name: t("work.field.view.refused") }));
    await waitFor(() => expect(screen.getByTestId("where").textContent).toBe(`/${TENANT}/work/field/refused`));
    expect(activeWorkTab(`/${TENANT}/work/field/refused`)).toBe("field");
  });

  it("asks for OPEN copies, paged, and draws Technician · Job · What · Reason · When · Status — no id on screen", async () => {
    const calls: Call[] = [];
    mount(fakeClient(calls, { "/work/refused-items": page([row()]) }));
    await waitFor(() => expect(screen.getByText("WO-0028")).toBeInTheDocument());

    const read = READS(calls)[0];
    expect(read?.query.status).toBe("open");
    expect(read?.query.page).toBe(1);
    expect(read?.query.per).toBeDefined();

    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent ?? "");
    for (const label of [
      t("work.field.col.technician"),
      t("work.refused.col.job"),
      t("work.refused.col.what"),
      t("work.field.col.reason"),
      t("work.refused.col.when"),
      t("work.field.col.status"),
    ]) {
      expect(headers.some((h) => h.includes(label))).toBe(true);
    }
    const line = screen.getByText("WO-0028").closest("tr") as HTMLElement;
    expect(within(line).getByText("D. Ortiz")).toBeInTheDocument();
    expect(within(line).getByText(t("work.refused.kind.reading"))).toBeInTheDocument();
    expect(within(line).getByText(t("work.mobile.not_your_job"))).toBeInTheDocument();
    expect(within(line).getByText(t("work.refused.status.open"))).toBeInTheDocument();
    // Rule 31 — no address-only value reaches the screen.
    expect(document.body.textContent).not.toContain(COPY_ID);
    expect(document.body.textContent).not.toContain(ORDER_ID);
    expect(document.body.textContent).not.toContain(ORTIZ_ID);
  });

  it("the detail draws the reading WITH its unit, the photographs, and both acts", async () => {
    const calls: Call[] = [];
    mount(fakeClient(calls, { "/work/refused-items": page([row()]), [`/work/refused-items/${COPY_ID}`]: detail() }));
    await waitFor(() => expect(screen.getByText("WO-0028")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("refused-open"));

    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(within(dialog).getByText("52410 kWh")).toBeInTheDocument());
    expect(within(dialog).getByText("Final read")).toBeInTheDocument();
    const uploaded = dialog.querySelector('[data-refused-photo="uploaded"]') as HTMLImageElement;
    expect(uploaded.getAttribute("src")).toContain(
      `/${TENANT}/work-orders/${ORDER_ID}/attachments/0d0d0d0d-4444-4d4d-8f8f-000000000001/content`,
    );
    expect(within(dialog).getByText(t("work.refused.photoOnPhone"))).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: t("work.refused.apply") })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: t("work.refused.markReviewed") })).toBeInTheDocument();
  });

  it("Mark reviewed posts the note; Apply to job posts to the copy's own address", async () => {
    const calls: Call[] = [];
    const client = fakeClient(calls, {
      "/work/refused-items": page([row()]),
      [`/work/refused-items/${COPY_ID}`]: detail(),
      [`POST /work/refused-items/${COPY_ID}/review`]: detail({ status: "reviewed" }),
      [`POST /work/refused-items/${COPY_ID}/apply`]: detail({ status: "applied" }),
    });
    mount(client);
    await waitFor(() => expect(screen.getByText("WO-0028")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("refused-open"));
    const dialog = await screen.findByRole("dialog");
    const note = await within(dialog).findByLabelText(t("work.refused.noteLabel"));
    fireEvent.change(note, { target: { value: "Chen re-reads Monday" } });
    fireEvent.click(within(dialog).getByRole("button", { name: t("work.refused.markReviewed") }));
    await waitFor(() => expect(commits(calls).length).toBe(1));
    expect(commits(calls)[0]).toMatchObject({
      method: "POST",
      path: `/work/refused-items/${COPY_ID}/review`,
      body: { note: "Chen re-reads Monday" },
    });

    fireEvent.click(screen.getByTestId("refused-open"));
    const again = await screen.findByRole("dialog");
    const apply = await within(again).findByRole("button", { name: t("work.refused.apply") });
    fireEvent.click(apply);
    await waitFor(() => expect(commits(calls).length).toBe(2));
    expect(commits(calls)[1]).toMatchObject({ method: "POST", path: `/work/refused-items/${COPY_ID}/apply` });
  });

  it("a refused Apply shows the server's reason in words, and a route reading offers no Apply", async () => {
    const calls: Call[] = [];
    const client = fakeClient(calls, {
      "/work/refused-items": page([row()]),
      [`/work/refused-items/${COPY_ID}`]: detail(),
      [`POST /work/refused-items/${COPY_ID}/apply`]: () => {
        throw new ApiError(409, { code: "BIZ-001", message_key: "work.sync.job_cancelled", params: {} });
      },
    });
    mount(client);
    await waitFor(() => expect(screen.getByText("WO-0028")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("refused-open"));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(await within(dialog).findByRole("button", { name: t("work.refused.apply") }));
    await waitFor(() => expect(within(dialog).getByText(t("work.sync.job_cancelled"))).toBeInTheDocument());
    cleanup();

    const reads = row({ door: "reads", work_order: null, message_key: "work.mobile.reads.unit_missing", reason: "unit_missing" });
    mount(
      fakeClient([], {
        "/work/refused-items": page([reads]),
        [`/work/refused-items/${COPY_ID}`]: detail({ ...reads, can_apply: false, work: { kind: "reading", reading: { meter_no: "MTR-0471", value: "52410", unit: null } } }),
      }),
    );
    await waitFor(() => expect(screen.getByText(t("field.reads.refused.unit_missing"))).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("refused-open"));
    const second = await screen.findByRole("dialog");
    await within(second).findByText("MTR-0471");
    expect(within(second).queryByRole("button", { name: t("work.refused.apply") })).toBeNull();
    expect(within(second).getByRole("button", { name: t("work.refused.markReviewed") })).toBeInTheDocument();
  });

  it("the words exist in all eleven catalogues", async () => {
    const languages = ["en", "de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR"];
    for (const lng of languages) {
      await i18n.loadLanguages(lng);
      for (const key of ["work.field.view.refused", "work.refused.apply", "work.refused.markReviewed", "field.ff50.keptForOffice"]) {
        expect(i18n.exists(key, { lng }), `${lng} ${key}`).toBe(true);
      }
    }
  });
});
