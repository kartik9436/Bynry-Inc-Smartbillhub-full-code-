// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-192-BRC10 — MQ-033 task 11, Settings → Reads → Read formats:
//           the list, the builder, the question editor and the three pointers.
// Rules:    BR-MET-1210 … BR-MET-1214 · BR-MET-1217 · NFR-3 · B14 rules 15,
//           31, 33, 43
// Note:     Mounted under the REAL path patterns (`/:tenant/settings/…`), so a
//           link the page builds is the address a person opens (hard-won law
//           2's fixture clause). The load-bearing assertions read the WIRE:
//           a screen that draws the right words and sends the wrong body
//           would pass every visible check.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { ReadFormatDetailPage } from "./ReadFormatDetailPage";
import { CycleReadFormatPanel, RouteReadFormatPanel, RoutesReadFormatDialog } from "./ReadFormatPointer";
import { READ_FORMATS_ROUTE, ReadFormatsPage } from "./ReadFormatsPage";
import type { ReadFormatDetail, ReadFormatQuestion, ReadFormatRow } from "./readFormatsEndpoints";

const TENANT = "silver-creek-water1";
const FMT = "6f1c2a0e-1111-4c4c-9a9a-000000000001";

interface Sent {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
}

type Handler = (sent: Sent) => Response | undefined;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function page<T>(results: T[], count = results.length) {
  return { count, next: null, previous: null, results };
}

const DEFAULTS = {
  count: 2,
  results: [
    { service: { code: "electric", name: "Electric" }, read_format: null },
    { service: { code: "water", name: "Water" }, read_format: null },
  ],
};

const ROW: ReadFormatRow = {
  id: FMT,
  name: "Water monthly walk",
  service: { code: "water", name: "Water" },
  status: "published",
  current_version: { id: "v-1", version_no: 2, published_at: "2026-10-20T10:00:00Z" },
  draft_version_id: null,
  used_by: { routes: 2, cycles: 0, services: 1 },
  retired_at: null,
  created_at: "2026-10-01T10:00:00Z",
  updated_at: "2026-10-20T10:00:00Z",
};

function question(seq: number, key: string, label: string, extra: Partial<ReadFormatQuestion> = {}) {
  return {
    id: `q-${key}`,
    seq,
    key,
    label,
    help_text: null,
    data_type: "boolean",
    options: null,
    is_required: false,
    asked_when: "every_reading",
    show_if: null,
    raise_work: null,
    ...extra,
  } as ReadFormatQuestion;
}

const QUESTIONS = [
  question(10, "seal_intact", "Seal intact?"),
  question(20, "seal_photo", "Photo of the seal", {
    data_type: "photo",
    show_if: { question_key: "seal_intact", answer: false },
  }),
  question(30, "condition", "Meter condition", {
    data_type: "select",
    options: ["Good", "Damaged", "Missing"],
  }),
];

function detail(extra: Partial<ReadFormatDetail> = {}): ReadFormatDetail {
  return {
    ...ROW,
    status: "draft",
    current_version: null,
    draft_version_id: "v-d",
    current: null,
    draft: {
      id: "v-d",
      read_format_id: FMT,
      state: "draft",
      version_no: null,
      change_note: null,
      published_at: null,
      published_by: null,
      created_at: null,
      questions: QUESTIONS,
    },
    ...extra,
  };
}

function recordingClient(sent: Sent[], handler: Handler): ApiClient {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const body =
        init?.body === undefined || init?.body === null
          ? null
          : (JSON.parse(String(init.body)) as Record<string, unknown>);
      const one = { method, url, body };
      sent.push(one);
      const answer = handler(one);
      if (answer !== undefined) {
        return answer;
      }
      if (url.includes("/settings/read-formats/defaults")) {
        return json(DEFAULTS);
      }
      return json(page([]));
    },
  });
}

function Where() {
  const location = useLocation();
  return <output data-testid="where">{location.pathname}</output>;
}

function mount(entry: string, routes: { path: string; element: ReactNode }[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[entry]}>
          <Routes>
            {routes.map((route) => (
              <Route key={route.path} path={route.path} element={route.element} />
            ))}
          </Routes>
          <Where />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const LIST_PATH = `/:tenant${READ_FORMATS_ROUTE}`;
const DETAIL_PATH = `/:tenant${READ_FORMATS_ROUTE}/:formatId`;
const REGIONAL = { timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" } as const;

afterEach(() => cleanup());

describe("Settings → Reads → Read formats — the list", () => {
  it("draws the server's page, asks for it by page, and shows no database id", async () => {
    const sent: Sent[] = [];
    const client = recordingClient(sent, ({ method, url }) =>
      method === "GET" && /\/settings\/read-formats\?/.test(url) ? json(page([ROW], 61)) : undefined,
    );
    mount(`/${TENANT}${READ_FORMATS_ROUTE}`, [
      { path: LIST_PATH, element: <ReadFormatsPage client={client} {...REGIONAL} /> },
    ]);
    const link = await screen.findByRole("link", { name: "Water monthly walk" });
    expect(link).toHaveAttribute("href", `/${TENANT}${READ_FORMATS_ROUTE}/${FMT}`);
    const row = link.closest("tr") as HTMLElement;
    expect(within(row).getByText("Published")).toBeInTheDocument();
    expect(within(row).getByText("v2")).toBeInTheDocument();
    expect(within(row).getByText("Routes 2 · Cycles 0 · Services 1")).toBeInTheDocument();
    // B14 rule 31 — the format's uuid is an address, never a cell.
    expect(row.textContent ?? "").not.toContain(FMT);
    // NFR-3 — the SERVER pages: the request carries page and per.
    const list = sent.find((s) => /\/settings\/read-formats\?/.test(s.url));
    expect(list?.url).toMatch(/page=1/);
    expect(list?.url).toMatch(/per=\d+/);
    // The footer reads the server's total, not the rows in hand.
    expect(await screen.findByText(/61/)).toBeInTheDocument();
  });

  it("New format → name + service → POST → opens the builder at its address", async () => {
    const sent: Sent[] = [];
    const client = recordingClient(sent, ({ method, url }) =>
      method === "POST" && url.endsWith("/settings/read-formats") ? json(detail(), 201) : undefined,
    );
    mount(`/${TENANT}${READ_FORMATS_ROUTE}`, [
      { path: LIST_PATH, element: <ReadFormatsPage client={client} {...REGIONAL} /> },
      { path: DETAIL_PATH, element: <p>builder</p> },
    ]);
    const user = userEvent.setup();
    await user.click((await screen.findAllByRole("button", { name: "+ New format" }))[0] as HTMLElement);
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText(/Name/), "Water monthly walk");
    await waitFor(() =>
      expect(within(dialog).getByRole("option", { name: "Water" })).toBeInTheDocument(),
    );
    await user.selectOptions(within(dialog).getByLabelText(/Service/), "water");
    await user.click(within(dialog).getByRole("button", { name: "Create ✓" }));
    await waitFor(() =>
      expect(screen.getByTestId("where").textContent).toBe(`/${TENANT}${READ_FORMATS_ROUTE}/${FMT}`),
    );
    const post = sent.find((s) => s.method === "POST");
    expect(post?.body).toEqual({ name: "Water monthly walk", service: "water" });
  });

  it("Defaults by service: picking a format PUTs that service's default", async () => {
    const sent: Sent[] = [];
    const client = recordingClient(sent, ({ method, url }) => {
      if (method === "GET" && /status=published/.test(url) && /service=water/.test(url)) {
        return json(page([ROW]));
      }
      if (method === "PUT" && url.includes("/defaults/water")) {
        return json({
          count: 2,
          results: [
            DEFAULTS.results[0],
            { service: { code: "water", name: "Water" }, read_format: { id: FMT, name: ROW.name } },
          ],
        });
      }
      return undefined;
    });
    mount(`/${TENANT}${READ_FORMATS_ROUTE}`, [
      { path: LIST_PATH, element: <ReadFormatsPage client={client} {...REGIONAL} /> },
    ]);
    const select = await screen.findByLabelText("Format for Water");
    await waitFor(() =>
      expect(within(select).getByRole("option", { name: "Water monthly walk" })).toBeInTheDocument(),
    );
    await userEvent.setup().selectOptions(select, FMT);
    await waitFor(() => expect(sent.some((s) => s.method === "PUT")).toBe(true));
    const put = sent.find((s) => s.method === "PUT");
    expect(put?.url).toMatch(/\/settings\/read-formats\/defaults\/water$/);
    expect(put?.body).toEqual({ read_format_id: FMT });
  });
});

describe("Settings → Reads → one read format — the builder", () => {
  function mountBuilder(sent: Sent[], handler: Handler, body: ReadFormatDetail = detail()) {
    const client = recordingClient(sent, (one) => {
      const answer = handler(one);
      if (answer !== undefined) {
        return answer;
      }
      if (one.method === "GET" && one.url.endsWith(`/settings/read-formats/${FMT}`)) {
        return json(body);
      }
      return undefined;
    });
    mount(`/${TENANT}${READ_FORMATS_ROUTE}/${FMT}`, [
      { path: DETAIL_PATH, element: <ReadFormatDetailPage client={client} {...REGIONAL} /> },
    ]);
  }

  it("lists the draft's questions in order, with what each one does", async () => {
    mountBuilder([], () => undefined);
    const first = await screen.findByRole("button", { name: "Seal intact?" });
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows.map((r) => within(r).queryAllByRole("button")[0]?.textContent)).toEqual([
      "Seal intact?",
      "Photo of the seal",
      "Meter condition",
    ]);
    expect(within(rows[1] as HTMLElement).getByText("After “Seal intact?”")).toBeInTheDocument();
    expect(within(rows[1] as HTMLElement).getByText("Photo")).toBeInTheDocument();
    expect(first).toBeInTheDocument();
  });

  it.each([
    ["text", "Text"],
    ["number", "Number"],
    ["date", "Date"],
    ["boolean", "Yes / No"],
    ["select", "Pick one"],
    ["multi_select", "Pick several"],
    ["photo", "Photo"],
  ])("adds a %s question — the custom-field types plus Photo", async (dataType, typeWord) => {
    const sent: Sent[] = [];
    mountBuilder(sent, ({ method, url }) =>
      method === "POST" && url.endsWith("/questions") ? json(detail(), 201) : undefined,
    );
    const user = userEvent.setup();
    await user.click((await screen.findAllByRole("button", { name: "+ Add question" }))[0] as HTMLElement);
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText(/Label/), "Gate code");
    const type = within(dialog).getByLabelText(/^Type/);
    expect(within(type).getByRole("option", { name: typeWord })).toBeInTheDocument();
    await user.selectOptions(type, dataType);
    if (dataType === "select" || dataType === "multi_select") {
      await user.type(within(dialog).getByLabelText(/Options/), "Locked{enter}Open");
    }
    // A photo is never a job's trigger: the control is not offered.
    expect(within(dialog).queryByLabelText("Raise a job") === null).toBe(dataType === "photo");
    await user.click(within(dialog).getByRole("button", { name: "Add ✓" }));
    await waitFor(() => expect(sent.some((s) => s.method === "POST")).toBe(true));
    const post = sent.find((s) => s.method === "POST");
    expect(post?.body).toMatchObject({
      label: "Gate code",
      data_type: dataType,
      asked_when: "every_reading",
      show_if: null,
      raise_work: null,
    });
    if (dataType === "select" || dataType === "multi_select") {
      expect(post?.body?.options).toEqual(["Locked", "Open"]);
    } else {
      expect(post?.body).not.toHaveProperty("options");
    }
  });

  it("Show only if offers EARLIER questions only — never itself, a later one or a photo", async () => {
    const sent: Sent[] = [];
    mountBuilder(sent, ({ method, url }) =>
      method === "PATCH" && url.includes("/questions/condition") ? json(detail()) : undefined,
    );
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Meter condition" }));
    const dialog = await screen.findByRole("dialog");
    const showIf = within(dialog).getByLabelText(/Show only if/);
    expect(within(showIf).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Always",
      "Seal intact?",
    ]);
    await user.selectOptions(showIf, "seal_intact");
    await user.selectOptions(within(dialog).getByLabelText(/Answer is/), "false");
    await user.click(within(dialog).getByRole("button", { name: "Save ✓" }));
    await waitFor(() => expect(sent.some((s) => s.method === "PATCH")).toBe(true));
    expect(sent.find((s) => s.method === "PATCH")?.body).toMatchObject({
      show_if: { question_key: "seal_intact", answer: false },
      options: ["Good", "Damaged", "Missing"],
    });
  });

  it("the FIRST question offers no follow-up at all", async () => {
    mountBuilder([], () => undefined);
    await userEvent.setup().click(await screen.findByRole("button", { name: "Seal intact?" }));
    const dialog = await screen.findByRole("dialog");
    const showIf = within(dialog).getByLabelText(/Show only if/);
    expect(within(showIf).getAllByRole("option").map((o) => o.textContent)).toEqual(["Always"]);
  });

  it("Move up sends the WHOLE new order; a server refusal is said on the page", async () => {
    const sent: Sent[] = [];
    mountBuilder(sent, ({ method, url }) =>
      method === "POST" && url.endsWith("/questions/reorder")
        ? json(
            {
              code: "VAL-002",
              message_key: "metering.readFormats.invalid",
              params: {},
              field_errors: [
                {
                  field: "keys",
                  code: "VAL-002",
                  message_key: "metering.readFormats.show_if_earlier",
                  params: { question_key: "seal_intact" },
                },
              ],
              br_ref: "BR-MET-1212",
            },
            422,
          )
        : undefined,
    );
    await screen.findByRole("button", { name: "Seal intact?" });
    const rows = screen.getAllByRole("row").slice(1);
    await userEvent.setup().click(within(rows[1] as HTMLElement).getByRole("button", { name: "Move up" }));
    await waitFor(() => expect(sent.some((s) => s.url.endsWith("/reorder"))).toBe(true));
    expect(sent.find((s) => s.url.endsWith("/reorder"))?.body).toEqual({
      keys: ["seal_photo", "seal_intact", "condition"],
    });
    // The FIELD error's own sentence — not "Check the highlighted fields".
    expect(await screen.findByRole("alert")).toHaveTextContent("Pick an earlier question.");
  });

  it("Publish refused with no questions shows the server's sentence", async () => {
    mountBuilder([], ({ method, url }) =>
      method === "POST" && url.endsWith("/publish")
        ? json(
            { code: "BIZ-STATE", message_key: "metering.readFormats.no_questions", params: {}, br_ref: "BR-MET-1213" },
            409,
          )
        : undefined,
    );
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Publish ✓" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Publish ✓" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Add a question first.");
  });

  it("Retire refused while in use names what still uses it", async () => {
    const published = detail({
      status: "published",
      current_version: { id: "v-1", version_no: 2, published_at: "2026-10-20T10:00:00Z" },
      draft_version_id: null,
      draft: null,
      current: { ...(detail().draft as NonNullable<ReadFormatDetail["draft"]>), state: "published", version_no: 2 },
    });
    mountBuilder(
      [],
      ({ method, url }) =>
        method === "POST" && url.endsWith("/retire")
          ? json(
              {
                code: "BIZ-STATE",
                message_key: "metering.readFormats.in_use",
                params: { routes: 2, cycles: 0, services: 1 },
                br_ref: "BR-MET-1212",
              },
              409,
            )
          : undefined,
      published,
    );
    const user = userEvent.setup();
    // Published and no draft: the list is locked and says how to edit.
    expect(await screen.findByText("Start a new draft to edit.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retire" }));
    // B14 rule 6 — a destructive confirm is the shared ConfirmDialog.
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Retire" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Format still in use. Replace it first. Routes 2 · Cycles 0 · Services 1",
    );
  });
});

describe("the pointers — route → cycle → service", () => {
  function mountBare(node: ReactNode) {
    mount(`/${TENANT}/x`, [{ path: "/:tenant/x", element: node }]);
  }

  it("the cycle's Read format PUTs the cycle's own pointer", async () => {
    const sent: Sent[] = [];
    const client = recordingClient(sent, ({ method, url }) => {
      if (url.includes("/cycles/c-1/read-format")) {
        return json({ cycle_id: "c-1", read_format: method === "PUT" ? { id: FMT, name: ROW.name } : null });
      }
      if (/status=published/.test(url)) {
        return json(page([ROW]));
      }
      return undefined;
    });
    mountBare(<CycleReadFormatPanel cycleId="c-1" readOnly={false} client={client} />);
    const select = await screen.findByLabelText("Read format");
    await waitFor(() =>
      expect(within(select).getByRole("option", { name: "Water monthly walk · Water" })).toBeInTheDocument(),
    );
    const user = userEvent.setup();
    await user.selectOptions(select, FMT);
    await user.click(screen.getByRole("button", { name: "Save ✓" }));
    await waitFor(() => expect(sent.some((s) => s.method === "PUT")).toBe(true));
    expect(sent.find((s) => s.method === "PUT")?.body).toEqual({ read_format_id: FMT });
  });

  it("the route's panel says where each service's format comes from", async () => {
    const client = recordingClient([], ({ url }) =>
      url.includes("/routes/r-1/read-format")
        ? json({
            route_id: "r-1",
            route_read_format_id: null,
            results: [
              {
                service: "water",
                source: "cycle",
                read_format: { id: FMT, name: ROW.name, version_id: "v-1", version_no: 2 },
              },
              { service: "electric", source: null, read_format: null },
            ],
          })
        : undefined,
    );
    mountBare(<RouteReadFormatPanel routeId="r-1" service="water" readOnly={false} client={client} />);
    const list = await screen.findByRole("list", { name: "In use per service" });
    await waitFor(() => expect(within(list).getByText("Water")).toBeInTheDocument());
    expect(list).toHaveTextContent("Water Water monthly walk · From the cycle");
    expect(list).toHaveTextContent("Electric Plain reading");
    // B14 rule 31 — never the service CODE.
    expect(list.textContent ?? "").not.toMatch(/\bwater\b|\belectric\b/);
  });

  it("many routes in one move: PUT routes/read-format with every id", async () => {
    const sent: Sent[] = [];
    const done: number[] = [];
    const client = recordingClient(sent, ({ method, url }) => {
      if (method === "PUT" && url.endsWith("/routes/read-format")) {
        return json({ route_ids: ["r-1", "r-2"], read_format: { id: FMT, name: ROW.name }, updated: 2 });
      }
      if (/status=published/.test(url)) {
        return json(page([ROW]));
      }
      return undefined;
    });
    mountBare(
      <RoutesReadFormatDialog
        routeIds={["r-1", "r-2"]}
        services={["water"]}
        client={client}
        onClose={() => undefined}
        onDone={(n) => done.push(n)}
      />,
    );
    const dialog = await screen.findByRole("dialog");
    const select = within(dialog).getByLabelText("Read format");
    await waitFor(() =>
      expect(within(select).getByRole("option", { name: "Water monthly walk" })).toBeInTheDocument(),
    );
    // One shared service narrows the picker to that service's formats.
    expect(sent.find((s) => /status=published/.test(s.url))?.url).toMatch(/service=water/);
    const user = userEvent.setup();
    await user.selectOptions(select, FMT);
    await user.click(within(dialog).getByRole("button", { name: "Save ✓" }));
    await waitFor(() => expect(done).toEqual([2]));
    expect(sent.find((s) => s.method === "PUT")?.body).toEqual({
      route_ids: ["r-1", "r-2"],
      read_format_id: FMT,
    });
  });
});
