// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-192-BRC10 — MQ-033 task 13: *"filterable in Reads lists"*.
// Rules:    BR-MET-1218 (`answer[<key>]=<value>`, AND-ed) · IS-4 (removable
//           chips, kept in the URL) · BR-SHL-011 (the export carries what the
//           list shows) · hard-won law 2 (mounted under `/:tenant/reads`)
// ───────────────────────────────────────────────────────
// RED FIRST: before this lane `GET /reads` was never sent an `answer[…]`
// parameter — the server had accepted it since task 10 and no control wrote
// one — and `ReadAnswerFilter` / `readAnswersShared` did not exist.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import i18n from "i18next";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import { getReads } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { AnswerFilterDialog } from "./ReadAnswerFilter";
import { ReadsListPage } from "./ReadsListPage";
import {
  answerFilterEntries,
  answerFiltersFrom,
  writeAnswerFilters,
} from "./readAnswersShared";
import type { AnswerQuestion } from "./readAnswersShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const TENANT = "brazosbend";

afterEach(cleanup);

const CONDITION: AnswerQuestion = {
  read_format_id: "f-1",
  format_name: "Water monthly walk",
  version_no: 1,
  key: "meter_condition",
  label: "Meter condition",
  data_type: "select",
  options: ["Good", "Damaged", "Missing"],
};
const SEAL: AnswerQuestion = {
  ...CONDITION,
  key: "seal_intact",
  label: "Seal intact?",
  data_type: "boolean",
  options: [],
};

type Call = { path: string; query?: Record<string, unknown> };

function recordingClient(calls: Call[]): ApiClient {
  const ok = <T,>(data: T) => Promise.resolve({ status: 200, data, etag: null, notModified: false });
  const page = (results: unknown[]) => ok({ count: results.length, next: null, previous: null, results });
  return {
    get: vi.fn((path: string, options?: { query?: Record<string, unknown> }) => {
      calls.push({ path, query: options?.query });
      if (path.startsWith("/reads/answer-questions")) {
        const params = new URLSearchParams(path.split("?")[1] ?? "");
        const keys = params.getAll("key");
        const all = [SEAL, CONDITION];
        return page(keys.length > 0 ? all.filter((q) => keys.includes(q.key)) : all);
      }
      if (path === "/reads") return page([]);
      // Reference reads (services, routes, cycles) answer an empty LIST.
      return ok([]);
    }),
    post: vi.fn(() => ok({})),
    patch: vi.fn(() => ok({})),
    put: vi.fn(() => ok({})),
    delete: vi.fn(() => ok({})),
  } as unknown as ApiClient;
}

function WhereAmI() {
  const location = useLocation();
  return <output data-testid="where">{location.search}</output>;
}

function mountList(search: string, client: ApiClient) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/reads${search}`]}>
          <Routes>
            <Route
              path="/:tenant/reads"
              element={
                <>
                  <ReadsListPage client={client} />
                  <WhereAmI />
                </>
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("MQ-033 task 13 — the URL grammar of an answer filter", () => {
  it("reads `answer[<key>]=<value>` from the address bar and writes it back", () => {
    const params = new URLSearchParams("answer%5Bmeter_condition%5D=Damaged&f.status=ok&answer%5B%5D=x");
    expect(answerFiltersFrom(params)).toEqual({ meter_condition: "Damaged" });
    const out = new URLSearchParams();
    writeAnswerFilters(out, { meter_condition: "Damaged", seal_intact: "true" });
    expect(out.get("answer[meter_condition]")).toBe("Damaged");
    expect(out.get("answer[seal_intact]")).toBe("true");
  });

  it("the list request and the export body carry the SAME spelling the server reads", async () => {
    const calls: Call[] = [];
    await getReads({ answers: { meter_condition: "Damaged", seal_intact: "false" } }, recordingClient(calls));
    expect(calls[0]?.query).toMatchObject({
      "answer[meter_condition]": "Damaged",
      "answer[seal_intact]": "false",
    });
    expect(answerFilterEntries({ meter_condition: "Damaged" })).toEqual({
      "answer[meter_condition]": "Damaged",
    });
  });
});

describe("MQ-033 task 13 — the Answer filter on the Reads list", () => {
  it("an answer in the URL reaches GET /reads and shows as a chip in the utility's words", async () => {
    const calls: Call[] = [];
    mountList("?answer%5Bmeter_condition%5D=Damaged", recordingClient(calls));
    await waitFor(() =>
      expect(calls.some((c) => c.path === "/reads" && c.query?.["answer[meter_condition]"] === "Damaged")).toBe(true),
    );
    await waitFor(() =>
      expect(document.querySelector('[data-answer-chip="meter_condition"]')).toHaveTextContent(
        t("table.filters.chip", { label: "Meter condition", value: "Damaged" }),
      ),
    );
    // ⚠ AND THE TOOLBAR STAYS once the list answers with NO rows: `DataTable`
    // swaps in the first-use empty state when nothing is filtered, which hid
    // the very chip that removes the filter (found by this test, first run).
    await waitFor(() => expect(calls.filter((c) => c.path === "/reads").length).toBeGreaterThan(0));
    expect(await screen.findByRole("button", { name: t("metering.reads.answerFilter.open") })).toBeInTheDocument();
  });

  it("the chip's ✕ takes the answer out of the URL and out of the request", async () => {
    const calls: Call[] = [];
    mountList("?answer%5Bmeter_condition%5D=Damaged", recordingClient(calls));
    const remove = await screen.findByRole("button", {
      name: t("table.filters.remove", { label: "Meter condition" }),
    });
    fireEvent.click(remove);
    await waitFor(() => expect(screen.getByTestId("where").textContent).not.toContain("answer"));
    const last = [...calls].reverse().find((c) => c.path === "/reads");
    expect(last?.query?.["answer[meter_condition]"]).toBeUndefined();
  });

  it("+ Answer is on the list's toolbar", async () => {
    mountList("", recordingClient([]));
    expect(await screen.findByRole("button", { name: t("metering.reads.answerFilter.open") })).toBeInTheDocument();
  });
});

describe("MQ-033 task 13 — the Filter by answer dialog", () => {
  it("finds a question by typing, offers its choices, and applies key + value", async () => {
    const onApply = vi.fn();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <AnswerFilterDialog
          client={recordingClient([])}
          dateFormat="MM/DD/YYYY"
          onClose={() => undefined}
          onApply={onApply}
        />
      </QueryClientProvider>,
    );
    fireEvent.change(document.getElementById("question") as HTMLInputElement, {
      target: { value: "cond" },
    });
    fireEvent.click(await screen.findByText("Meter condition"));
    await waitFor(() => expect(document.getElementById("value")).not.toBeNull());
    const value = document.getElementById("value") as HTMLSelectElement;
    expect([...value.querySelectorAll("option")].map((o) => o.textContent)).toEqual(
      expect.arrayContaining(["Good", "Damaged", "Missing"]),
    );
    fireEvent.change(value, { target: { value: "Damaged" } });
    fireEvent.click(screen.getByRole("button", { name: t("metering.reads.answerFilter.apply") }));
    await waitFor(() => expect(onApply).toHaveBeenCalledWith("meter_condition", "Damaged"));
  });
});
