// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 4, lane TEMPLATES — images 43–55
//           (`05-prototype/work-backoffice-2026-10-04/images/`), rulings 5–9
//           and PO answer 3 (a task carries instruction text).
// Tasks:    P3.12 (what a template is done to) · P3.13 (every added row edits
//           in place, five steps) · P3.15 (a change note on publish) · P3.25
//           (a Link kind) · P3.26 (ONE summary on Review and on Overview) ·
//           P3.29 (usage counts in words)
// Defects:  DEF-WRK-9565 · 9566 · 9567 · 9568 · 9577 · 9582 (the builder half)
// Rules:    B14 rules 21, 31, 33, 37, 42, 43, 44 · hard rule 3
// ───────────────────────────────────────────────────────
//
// ⚠ **THE TEMPLATE IS THE SERVER'S OWN RECORDING**, never a body typed here
// (`10-scripts/cr168_capture_work_shapes.py`, CR-168 §7 *"fixtures come from
// the server"*). Mounted under the REAL path patterns (`DEF-CWP-3925`).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import TEMPLATE from "./__fixtures__/server/work.template.json";
import TEMPLATE_PACKS from "./__fixtures__/server/work.template-packs.json";
import TEMPLATE_VERSIONS from "./__fixtures__/server/work.template.versions.json";
import TEMPLATE_USAGE from "./__fixtures__/server/work.template.usage.json";
import TEMPLATE_AUDIT from "./__fixtures__/server/work.template.audit.json";
import TEMPLATES from "./__fixtures__/server/work.templates.json";
import PARTS from "./__fixtures__/server/work.parts.json";
import RAISE_OPTIONS from "./__fixtures__/server/work.raise-options.json";
import { TemplateBuilder } from "./TemplateBuilder";
import { TemplateDetailPage } from "./TemplateDetailPage";
import { TemplatesPage } from "./TemplatesPage";

// The builder hydrates from the recording before a step is touched.
vi.setConfig({ testTimeout: 20000 });

const TENANT = "brazosbend";
const EDIT = `/${TENANT}/work/templates/${TEMPLATE.id}/edit`;
const EDIT_PATTERN = "/:tenant/work/templates/:templateId/edit";

type Call = { method: string; path: string; body: unknown };

function server(calls: Call[]): ApiClient {
  const routes: [string, unknown][] = [
    ["/work/template-packs", TEMPLATE_PACKS],
    ["/work/raise-options", RAISE_OPTIONS],
    ["/work/parts", PARTS],
    [`/work/templates/${TEMPLATE.id}/versions`, TEMPLATE_VERSIONS],
    [`/work/templates/${TEMPLATE.id}/usage`, TEMPLATE_USAGE],
    [`/work/templates/${TEMPLATE.id}/audit`, TEMPLATE_AUDIT],
    [`/work/templates/${TEMPLATE.id}`, TEMPLATE],
    ["/work/templates", TEMPLATES],
  ];
  const get = async (path: string): Promise<ApiResponse<unknown>> => {
    const hit = routes.find(([p]) => p === path.split("?")[0]);
    if (hit === undefined) throw new Error(`no recording for GET ${path}`);
    return { status: 200, data: hit[1], etag: null, notModified: false };
  };
  const write = (method: string) => async (path: string, body?: unknown) => {
    calls.push({ method, path, body });
    // The two upload answers, in the shape lane SRV-3 states for them (CR-168
    // §7.3 as appended); walked against the real server on PostgreSQL.
    if (path.endsWith("/help/upload-url")) {
      const ticket = { upload_url: `/work/templates/${TEMPLATE.id}/help/documents`, method: "POST", field: "file", max_bytes: 10485760, content_types: ["application/pdf", "image/png", "image/jpeg"] };
      return { status: 200, data: ticket, etag: null, notModified: false };
    }
    if (path.endsWith("/help/documents")) {
      const file = (body as FormData).get("file") as File;
      const stored = { id: "d1", ref: "work/templates/help/d1", name: file.name, content_type: file.type, bytes: 421888, url: "/x" };
      return { status: 201, data: stored, etag: null, notModified: false };
    }
    const data = path.endsWith("/publish")
      ? { ...TEMPLATE, created: true, version: TEMPLATE.version + 1, published_at: "2026-10-04T12:00:00Z" }
      : { ...TEMPLATE, collection: path.split("/").pop(), count: 0 };
    return { status: 200, data, etag: null, notModified: false };
  };
  return {
    get,
    post: write("POST"),
    put: write("PUT"),
    patch: write("PATCH"),
    del: write("DELETE"),
    delete: write("DELETE"),
  } as unknown as ApiClient;
}

function mount(path: string, pattern: string, element: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path={pattern} element={element} />
            <Route path="/:tenant/work/templates/:templateId" element={<div data-landed-detail="" />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function builderAt(step: number, calls: Call[] = []) {
  mount(`${EDIT}?step=${step}`, EDIT_PATTERN, <TemplateBuilder client={server(calls)} />);
  // Hydrated from the recording — the first task's title is in its own box.
  await screen.findAllByDisplayValue(TEMPLATE.bundle.tasks[0].title, undefined, { timeout: 4000 }).catch(() => undefined);
  return calls;
}

function lastPut(calls: Call[], collection: string): { rows: Record<string, unknown>[] } {
  const hit = [...calls].reverse().find((c) => c.method === "PUT" && c.path.endsWith(`/${collection}`));
  if (hit === undefined) throw new Error(`no PUT …/${collection}`);
  return hit.body as { rows: Record<string, unknown>[] };
}

afterEach(() => cleanup());

describe("P3.13 — every added row edits in place (ruling 5; DEF-WRK-9565, 9566)", () => {
  it("Safety: the check is a text box holding the row, and an edit is what Save draft sends", async () => {
    const calls = await builderAt(2);
    const box = await screen.findByRole("textbox", { name: "Check 1" });
    expect(box).toHaveProperty("value", TEMPLATE.bundle.safety[0].text);
    fireEvent.change(box, { target: { value: "Isolate at the main breaker" } });
    await userEvent.setup().click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(lastPut(calls, "safety").rows[0].text).toBe("Isolate at the main breaker"));
  });

  it("Tasks: the task, its minutes and its instruction are boxes; all three reach the server", async () => {
    const calls = await builderAt(3);
    const task = await screen.findByRole("textbox", { name: "Task 2" });
    expect(task).toHaveProperty("value", TEMPLATE.bundle.tasks[1].title);
    expect(screen.getByRole("textbox", { name: "Minutes 2" })).toHaveProperty(
      "value",
      String(TEMPLATE.bundle.tasks[1].est_minutes),
    );
    fireEvent.change(task, { target: { value: "Fit the new meter" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Minutes 2" }), { target: { value: "25" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Instruction 2" }), {
      target: { value: "Isolate at the main before touching the meter." },
    });
    await userEvent.setup().click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => {
      const row = lastPut(calls, "tasks").rows[1];
      expect(row.title).toBe("Fit the new meter");
      expect(row.est_minutes).toBe(25);
      expect(row.instruction).toBe("Isolate at the main before touching the meter.");
    });
  });

  it("FB-013 — Tasks: Check payment opens minutes and a fee code, and both reach the server", async () => {
    const calls = await builderAt(3);
    await screen.findByRole("textbox", { name: "Task 2" });
    expect(screen.queryByRole("textbox", { name: "Fresh minutes 2" })).toBeNull();
    const ticks = screen.getAllByRole("checkbox", { name: "Check payment" });
    expect(ticks).toHaveLength(TEMPLATE.bundle.tasks.length);
    await userEvent.setup().click(ticks[1]);
    const minutes = await screen.findByRole("textbox", { name: "Fresh minutes 2" });
    expect(minutes).toHaveProperty("value", "5");
    fireEvent.change(minutes, { target: { value: "10" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Fee charge code 2" }), { target: { value: "CC-RECON" } });
    await userEvent.setup().click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => {
      const rows = lastPut(calls, "tasks").rows;
      expect([rows[1].money_fresh_minutes, rows[1].money_charge_code]).toEqual([10, "CC-RECON"]);
      expect([rows[0].money_fresh_minutes, rows[0].money_charge_code]).toEqual([null, null]);
    });
  });

  it("DEF-WRK-10645 — a filled payment check still says which box is which (visible words, not placeholders)", async () => {
    await builderAt(3);
    await screen.findByRole("textbox", { name: "Task 2" });
    await userEvent.setup().click(screen.getAllByRole("checkbox", { name: "Check payment" })[1]);
    const minutes = await screen.findByRole("textbox", { name: "Fresh minutes 2" });
    fireEvent.change(minutes, { target: { value: "5" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Fee charge code 2" }), { target: { value: "CC-RECON" } });
    // textContent never includes a placeholder, so these words are only here
    // if they are drawn beside the boxes.
    const line = document.querySelector('[data-money-check="1"]') as HTMLElement;
    expect(line.textContent).toContain("Fresh minutes");
    expect(line.textContent).toContain("Fee charge code");
  });

  it("Materials: the part is the add row's own list and the quantity a box without four trailing zeros", async () => {
    const calls = await builderAt(4);
    const qty = await screen.findByRole("textbox", { name: "Quantity 1" });
    expect(qty).toHaveProperty("value", "2");
    const part = screen.getByRole("combobox", { name: "Part 1" });
    expect(within(part).getAllByRole("option").length).toBeGreaterThan(1);
    fireEvent.change(qty, { target: { value: "3" } });
    await userEvent.setup().click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(lastPut(calls, "materials").rows[0].planned_qty).toBe("3"));
  });

  it("Readings: prompt, unit, min and max are boxes", async () => {
    const calls = await builderAt(5);
    const unit = await screen.findByRole("textbox", { name: "Unit 1" });
    expect(screen.getByRole("textbox", { name: "Prompt 1" })).toHaveProperty("value", TEMPLATE.bundle.readings[0].prompt);
    expect(screen.getByRole("textbox", { name: "Min 1" })).toHaveProperty("value", "220");
    fireEvent.change(unit, { target: { value: "kV" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Max 1" }), { target: { value: "260" } });
    await userEvent.setup().click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => {
      const row = lastPut(calls, "readings").rows[0];
      expect(row.unit_of_measure).toBe("kV");
      expect(row.max).toBe("260");
    });
  });

  it("Help: kind, what it is and where to find it edit in place", async () => {
    const calls = await builderAt(6);
    const label = await screen.findByRole("textbox", { name: "What it is 2" });
    fireEvent.change(label, { target: { value: "Metering supervisor" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Where to find it 2" }), {
      target: { value: "(512) 555-0100" },
    });
    await userEvent.setup().click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => {
      const row = lastPut(calls, "help").rows[1];
      expect(row.label).toBe("Metering supervisor");
      expect(row.ref).toBe("(512) 555-0100");
    });
  });
});

describe("P3.25 — a Link kind for a video or a web page (ruling 6; DEF-WRK-9567)", () => {
  it("offers Document, Phone and Link, and says links need a signal", async () => {
    await builderAt(6);
    const kind = await screen.findByRole("combobox", { name: "Kind" });
    const words = within(kind).getAllByRole("option").map((o) => o.textContent);
    expect(words).toEqual(["Document", "Phone", "Link"]);
    expect(screen.getByText("Carried on the phone. Documents work with no signal; links need one.")).toBeTruthy();
  });

  it("a YouTube address is badged as a video and is sent as a link", async () => {
    const calls = await builderAt(6);
    const user = userEvent.setup();
    await user.selectOptions(await screen.findByRole("combobox", { name: "Kind" }), "link");
    await user.type(screen.getByRole("textbox", { name: "What it is" }), "Fitting a single-phase meter");
    await user.type(
      screen.getByRole("textbox", { name: "Where to find it" }),
      "https://www.youtube.com/watch?v=Qx4dF2mT9sE",
    );
    const before = screen.queryAllByText("▶ Video · needs a signal").length;
    await user.click(screen.getByRole("button", { name: "+ Add" }));
    await waitFor(() => expect(screen.getAllByText("▶ Video · needs a signal").length).toBe(before + 1));
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => {
      const rows = lastPut(calls, "help").rows;
      expect(rows[rows.length - 1]).toMatchObject({
        kind: "link",
        label: "Fitting a single-phase meter",
        link: "https://www.youtube.com/watch?v=Qx4dF2mT9sE",
      });
    });
  });

  it("an address that is not https cannot be added", async () => {
    await builderAt(6);
    const user = userEvent.setup();
    await user.selectOptions(await screen.findByRole("combobox", { name: "Kind" }), "link");
    await user.type(screen.getByRole("textbox", { name: "What it is" }), "Fitting");
    await user.type(screen.getByRole("textbox", { name: "Where to find it" }), "http://example.com/v");
    expect(screen.getByRole("button", { name: "+ Add" })).toHaveProperty("disabled", true);
  });
});

describe("P3.14 — a help document is held, not named (ruling 6; DEF-WRK-9567)", () => {
  it("Choose a file stores it, the row shows its name and size, and the help PUT carries its ref", async () => {
    const calls = await builderAt(6);
    const user = userEvent.setup();
    await user.type(await screen.findByRole("textbox", { name: "What it is" }), "Meter exchange procedure");
    const file = new File(["%PDF-1.4"], "meter-exchange-procedure.pdf", { type: "application/pdf" });
    await user.upload(screen.getByLabelText("Choose a file"), file);
    expect(await screen.findByText("meter-exchange-procedure.pdf")).toBeTruthy();
    expect(screen.getByText("· 412 KB")).toBeTruthy();
    expect(calls.map((c) => c.path)).toEqual(
      expect.arrayContaining([`/work/templates/${TEMPLATE.id}/help/upload-url`, `/work/templates/${TEMPLATE.id}/help/documents`]),
    );
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => {
      const rows = lastPut(calls, "help").rows;
      expect(rows[rows.length - 1]).toEqual({ kind: "document", label: "Meter exchange procedure", ref: "work/templates/help/d1" });
    });
  });
});

describe("P3.12 — what a template is done to (DEF-WRK-9577)", () => {
  it("step 1 asks it, hydrated from the template, and the header carries it", async () => {
    const calls = await builderAt(1);
    const scope = await screen.findByRole("combobox", { name: /Done to/u });
    await waitFor(() => expect(scope).toHaveProperty("value", TEMPLATE.scope));
    const user = userEvent.setup();
    await user.selectOptions(scope, "per_asset");
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => {
      const header = calls.find((c) => c.method === "PATCH");
      expect((header?.body as { scope?: string }).scope).toBe("per_asset");
    });
  });

  it("the list draws a Done to column", async () => {
    mount(`/${TENANT}/work/templates`, "/:tenant/work/templates", <TemplatesPage client={server([])} />);
    expect(await screen.findByRole("columnheader", { name: /Done to/u })).toBeTruthy();
    expect(screen.getAllByText("Premises").length).toBeGreaterThan(0);
  });
});

describe("DEF-WRK-9582 — the builder's job type is the two-level picker", () => {
  it("a heading with sub-types is a group, not an option beside them", async () => {
    await builderAt(1);
    const type = await screen.findByRole("combobox", { name: /Job type/u });
    await waitFor(() => expect(type.querySelectorAll("optgroup").length).toBeGreaterThan(0));
    const groups = [...type.querySelectorAll("optgroup")].map((g) => g.getAttribute("label"));
    expect(groups).toContain("Connection");
  });
});

describe("P3.26 — ONE template summary, on Review and on Overview (rulings 7, 8, 9)", () => {
  it("Review shows every row of every section, each with ✎ Edit back to its step", async () => {
    await builderAt(8);
    const summary = await screen.findByTestId("template-summary");
    for (const task of TEMPLATE.bundle.tasks) expect(within(summary).getAllByText(task.title).length).toBe(1);
    for (const part of TEMPLATE.bundle.materials) expect(within(summary).getByText(`${part.part_no} · ${part.name}`)).toBeTruthy();
    expect(within(summary).getByText(TEMPLATE.bundle.readings[0].prompt)).toBeTruthy();
    for (const help of TEMPLATE.bundle.help) expect(within(summary).getByText(help.label)).toBeTruthy();
    for (const safety of TEMPLATE.bundle.safety) expect(within(summary).getByText(safety.text)).toBeTruthy();
    // The old count table is gone, with its stock sentences (B14 rule 37).
    expect(document.querySelector("[data-review-table]")).toBeNull();
    await userEvent.setup().click(within(summary).getByRole("button", { name: "Edit Tasks" }));
    expect(await screen.findByRole("textbox", { name: "Task 1" })).toBeTruthy();
  });

  it("Overview is the same component, every tab drawn, and ✎ Edit opens the builder at that step", async () => {
    mount(
      `/${TENANT}/work/templates/${TEMPLATE.id}`,
      "/:tenant/work/templates/:templateId",
      <TemplateDetailPage client={server([])} />,
    );
    const summary = await screen.findByTestId("template-summary", undefined, { timeout: 4000 });
    for (const task of TEMPLATE.bundle.tasks) expect(within(summary).getByText(task.title)).toBeTruthy();
    const edit = within(summary).getByRole("link", { name: "Edit Materials" });
    expect(edit.getAttribute("href")).toBe(`/${TENANT}/work/templates/${TEMPLATE.id}/edit?step=4`);
  });
});

describe("P3.15 — a change note on publish (DEF-WRK-9568)", () => {
  it("Review asks what changed on a published template, and Publish sends it", async () => {
    const calls = await builderAt(8);
    const user = userEvent.setup();
    await user.type(await screen.findByRole("textbox", { name: /What changed/u }), "Instruction on the fit task");
    await user.click(screen.getByRole("button", { name: /Publish template/u }));
    await waitFor(() => {
      const publish = calls.find((c) => c.path.endsWith("/publish"));
      expect((publish?.body as { change_note: string | null }).change_note).toBe("Instruction on the fit task");
    });
  });
});

describe("P3.29 — usage counts in words", () => {
  it("one order, two versions — the catalogue's plurals, never a pasted count", async () => {
    mount(
      `/${TENANT}/work/templates/${TEMPLATE.id}?tab=usage`,
      "/:tenant/work/templates/:templateId",
      <TemplateDetailPage client={server([])} />,
    );
    expect(TEMPLATE_VERSIONS.orders_raised).toBe(1);
    expect(TEMPLATE_VERSIONS.versions.length).toBe(2);
    expect(await screen.findByText("1 order raised across 2 versions", undefined, { timeout: 4000 })).toBeTruthy();
  });
});

describe("P3.28 — a template's change history (image 47)", () => {
  it("the Audit tab reads the recorded trail in words, and the hold sentence is gone", async () => {
    mount(
      `/${TENANT}/work/templates/${TEMPLATE.id}?tab=audit`,
      "/:tenant/work/templates/:templateId",
      <TemplateDetailPage client={server([])} />,
    );
    const table = await screen.findByRole("table", undefined, { timeout: 4000 });
    expect(within(table).getAllByText("Dana Whitfield").length).toBe(
      TEMPLATE_AUDIT.results.filter((r) => r.by?.name === "Dana Whitfield").length,
    );
    expect(within(table).getAllByText("Tasks changed").length).toBeGreaterThan(0);
    expect(within(table).getAllByText("Published v2").length).toBeGreaterThan(0);
    // Every row has words — no act code (`replaced`, `asset-types`) on screen (B14 rule 31).
    expect(table.textContent).not.toMatch(/replaced|asset-types|help_document_stored/u);
    expect(document.body.textContent).not.toContain("opens with the next release");
  });
});

describe("DEF-WRK-4637 — a template that will not open says so, and offers nothing over nothing", () => {
  function refusing(status: number): ApiClient {
    const fail = async (): Promise<never> => {
      throw new ApiError(status, { code: null, message_key: "errors.not-found" });
    };
    return { get: fail, post: fail, put: fail, patch: fail, del: fail, delete: fail } as unknown as ApiClient;
  }

  it("an unknown template id names the failure — never 'Loading' for ever under live commands", async () => {
    mount(
      `/${TENANT}/work/templates/00000000-0000-4000-8000-000000000000`,
      "/:tenant/work/templates/:templateId",
      <TemplateDetailPage client={refusing(404)} />,
    );
    expect(await screen.findByText(i18n.t("work.template.failedTitle"))).toBeTruthy();
    expect(screen.getByText(i18n.t("work.template.notFound"))).toBeTruthy();
    expect(screen.queryByText(i18n.t("work.template.loading"))).toBeNull();
    for (const name of [/Edit template/, /Duplicate/, /Deactivate/, /Delete/]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
      expect(screen.queryByRole("link", { name })).toBeNull();
    }
    // The way back to the list stays.
    expect(screen.getByRole("link", { name: /Templates/ }).getAttribute("href")).toBe(`/${TENANT}/work/templates`);
  });

  it("a read that fails for another reason says it could not be read, and offers Try again", async () => {
    mount(
      `/${TENANT}/work/templates/${TEMPLATE.id}`,
      "/:tenant/work/templates/:templateId",
      <TemplateDetailPage client={refusing(500)} />,
    );
    expect(await screen.findByText(i18n.t("work.template.unreadable"))).toBeTruthy();
    expect(screen.getByRole("button", { name: /Retry/ })).toBeTruthy();
  });
});
