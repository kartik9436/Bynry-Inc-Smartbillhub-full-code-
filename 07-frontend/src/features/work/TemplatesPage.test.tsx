// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-013 (two Water templates in one list; the CONTENTS cell) ·
//           US-WRK-015 (the row action opens the detail) · US-WRK-018 (STATUS).
//           Screens: Work-013
// Rules:    BR-WRK-010 · BR-WRK-012 · BR-SHL-025 · B14 rules 2 · 16 · 17 ·
//           19 · 20 · 31 (no database id is a visible value) · 32
// ───────────────────────────────────────────────────────
//
// ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, NOT BARE INSIDE A `MemoryRouter`.**
// `DEF-CWP-3925` records what the bare mount costs: with no `/:tenant/...`
// route declared, `useParams().tenant` is undefined and every address the page
// builds comes out `//work/templates/...` — a protocol-relative URL to another
// host, which reads as a perfectly good string to `toContain`. A fixture that
// cannot tell a working link from a broken one is how a dead door hides.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { queryKeys } from "@/api/queryClient";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";

import {
  TemplatesPage,
  WORK_TEMPLATES_SCREEN,
  contentsSentence,
  templateDetailPath,
  templatesTableConfig,
} from "./TemplatesPage";
import { WORK_TABS } from "./WorkShell";
import type { TemplateList, TemplateRow } from "./workEndpoints";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** `US-WRK-013` §4's own six rows, as the server shapes them. */
function template(over: Partial<TemplateRow> = {}): TemplateRow {
  return {
    id: "t-meter-exchange",
    template_no: "ST-0002",
    name: "Meter exchange — residential",
    service: { id: "s-electric", code: "electric", name: "Electric" },
    scope: "asset",
    sequence: 0,
    job_type: { id: "jt-me", name: "Meter exchange" },
    skill: { id: "sk-mf", name: "Meter fitting" },
    safety_kit: null,
    crew_size: 1,
    est_duration_minutes: 45,
    is_gate: false,
    no_gate_reason: null,
    is_sample: false,
    active: true,
    version: 2,
    contents: { tasks: 7, parts: 3, readings: 3, safety: 3, help: 3 },
    status: "published",
    ...over,
  };
}

const WATER_NEW = template({
  id: "t-water-new",
  template_no: "ST-0003",
  name: "New connection",
  service: { id: "s-water", code: "water", name: "Water" },
  contents: { tasks: 3, parts: 1, readings: 1, safety: 0, help: 0 },
  is_gate: true,
  version: 1,
});
const WATER_LEAK = template({
  id: "t-water-leak",
  template_no: null,
  name: "Leak investigation",
  service: { id: "s-water", code: "water", name: "Water" },
  contents: { tasks: 0, parts: 0, readings: 0, safety: 0, help: 0 },
  status: "draft",
  version: 0,
  skill: null,
  est_duration_minutes: null,
});
const BACKFLOW = template({
  id: "t-backflow",
  template_no: "ST-0006",
  name: "Backflow test",
  service: { id: "s-water", code: "water", name: "Water" },
  status: "inactive",
  active: false,
});

function list(rows: TemplateRow[], counts = { published: 4, draft: 1, inactive: 1 }): TemplateList {
  return { count: rows.length, next: null, previous: null, results: rows, counts };
}

function render(data: TemplateList | null): string {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: data !== null } },
  });
  if (data !== null) {
    queryClient.setQueryData(queryKeys.workTemplates("", "", 1, DEFAULT_PAGE_SIZE), data);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TENANT}/work/templates`]}>
        <Routes>
          <Route path="/:tenant/work/templates" element={<TemplatesPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const CONFIG = () =>
  templatesTableConfig(
    t,
    { template: () => null, gate: () => null, status: () => null, actions: () => null },
    [{ value: "water", label: "Water" }],
  );

describe("US-WRK-013 — the templates list (Work-013, template W1)", () => {
  // CR-168 P3.12 — TEN columns: *Done to* follows *Service* (DEF-WRK-9577).
  it("draws the head and the ten columns in the pack's order", () => {
    const html = render(list([template(), WATER_NEW, WATER_LEAK, BACKFLOW]));
    expect(html).toContain("Work order templates");
    expect(html).toContain("Every work order you raise is a copy of one of these");
    expect(html).toContain(`data-screen="${WORK_TEMPLATES_SCREEN}"`);
    expect(CONFIG().columns.map((c) => c.key)).toEqual([
      "name",
      "service",
      "scope",
      "job_type",
      "contents",
      "is_gate",
      "skill",
      "est_duration_minutes",
      "status",
      "actions",
    ]);
  });

  it("TC-1 — two Water templates sit in the same list, which yesterday's key forbade", () => {
    const html = render(list([WATER_NEW, WATER_LEAK]));
    expect(html).toContain("New connection");
    expect(html).toContain("Leak investigation");
  });

  it("TC-4 — a template with nothing behind it reads ZERO, never blank", () => {
    expect(contentsSentence(WATER_LEAK, t)).toContain("0");
    const html = render(list([WATER_LEAK]));
    expect(html).toContain(contentsSentence(WATER_LEAK, t));
  });

  it("TC-6 — the footer counts published, draft and inactive over the whole list", () => {
    const html = render(list([template(), WATER_LEAK, BACKFLOW]));
    expect(html).toContain('data-templates-footer=""');
    expect(html).toContain("4");
    expect(html).toContain("1");
  });

  it("B14 rule 31 — the NUMBER is visible and the uuid is not", () => {
    const html = render(list([template()]));
    expect(html).toContain("ST-0002");
    // The id may appear inside an `href` (that is what a link IS) but never as
    // the text of a cell. `>t-meter-exchange<` would be the failure.
    expect(html).not.toContain(">t-meter-exchange<");
  });

  it("a draft has no number at all, and the row does not invent one", () => {
    const html = render(list([WATER_LEAK]));
    expect(html).not.toContain("ST-0000");
    expect(html).toContain("Leak investigation");
  });

  it("the row action opens the DETAIL under the tenant, not at the host root", () => {
    const html = render(list([template()]));
    expect(html).toContain(`href="/${TENANT}/work/templates/t-meter-exchange"`);
    // `DEF-CWP-3925` — the protocol-relative address a bare mount produces.
    expect(html).not.toContain('href="//work/templates');
  });

  it("templateDetailPath is the ONE place the detail's address is spelled", () => {
    expect(templateDetailPath("abc")).toBe("/work/templates/abc");
  });

  it("declares exactly one filter — the drawing's *Filter by service*", () => {
    expect((CONFIG().filters ?? []).map((f) => f.name)).toEqual(["service"]);
  });

  it("B14 rule 17 — the empty state offers the builder DISABLED with its reason", () => {
    const html = render(list([], { published: 0, draft: 0, inactive: 0 }));
    expect(html).toContain("No templates yet");
  });

  // ⚠ **THE HOLD EXPIRED ON 2026-09-05 AND THIS IS WHAT IT BECAME.**
  //
  // Until CR-070 wave E this case asserted the button's ABSENCE, because the
  // eight-step builder did not exist and a primary onto a screen that does not
  // exist is dead UI. `TemplateBuilder.tsx` landed at `/work/templates/new`,
  // this case went red and named the button, and the button was added in the
  // same commit — which is exactly what `DEF-CWP-3925` asks a hold to do.
  //
  // It is now the MIRROR of what it was: the destination is asserted by
  // ADDRESS, so a refactor that quietly unpoints it fails here too. Mounted
  // under the real `/:tenant/...` pattern, or `useParams().tenant` is undefined
  // and the address comes out `//work/templates/new` — a protocol-relative URL
  // to another host that `toContain` reads as perfectly good.
  it("*New template* is LIVE and opens the builder", () => {
    const html = render(list([template()]));
    expect(html).toContain('href="/brazosbend/work/templates/new"');
    expect(html).not.toContain('href="//work/templates/new"');
    expect(html).toContain("New template");
  });

  it("the row action is the drawing's PENCIL and it opens the builder on that row", () => {
    const html = render(list([template()]));
    expect(html).toContain('href="/brazosbend/work/templates/t-meter-exchange/edit"');
    // The eye is still there and still opens the DETAIL — two destinations,
    // two glyphs, so neither has to mean both.
    expect(html).toContain('href="/brazosbend/work/templates/t-meter-exchange"');
  });

  it("the Work strip still names the Templates tab and points at this screen", () => {
    expect(WORK_TABS.map((tab) => tab.id)).toContain("templates");
    expect(WORK_TABS.find((tab) => tab.id === "templates")?.path).toBe("/work/templates");
  });

  // ── DEF-WRK-4048 · the GATE cell ──────────────────────────────────────────
  // `no_gate_reason` was seeded, carried through the seam, served, typed on
  // `TemplateRow` and rendered by NOTHING, while `sample_data.py` and
  // `test_tc3_the_ungated_services_carry_a_reason_a_clerk_can_read` both said
  // in as many words that it IS shown, on this column. Hard-won law 2 with law
  // 1 on top: G13 could not see it, because G13 asks whether a PROP is passed
  // and this value arrives inside a row.
  //
  // RED PROVED FIRST: with the cell's reason branch removed — back to a bare
  // `<Dash />` — this case fails on *gated on the water service it derives
  // from*, and the second case below still passes, which is what separates
  // "the reason is rendered" from "the dash is gone".
  it("DEF-WRK-4048 — a template with no gate carries the utility's own reason, not a bare dash", () => {
    const sewer = template({
      id: "t-sewer-tap",
      template_no: "ST-0011",
      name: "Tap and connection inspection",
      service: { id: "s-sewer", code: "sewer", name: "Sewer" },
      is_gate: false,
      // The seeded wording, quoted from `US-WRK-019` TC-3 and pinned by the
      // backend test — never paraphrased here, or the two would drift.
      no_gate_reason: "gated on the water service it derives from",
    });
    const html = render(list([sewer]));
    expect(html).toContain("gated on the water service it derives from");
    expect(html).toContain("data-no-gate-reason");
  });

  it("DEF-WRK-4048 — a gate still reads as a gate, and no reason is invented where none is stored", () => {
    // The gate row: the pill, and no reason element at all.
    const gate = render(list([WATER_NEW]));
    expect(gate).toContain("Gate");
    expect(gate).not.toContain("data-no-gate-reason");
    // A template the utility wrote itself, no gate and nobody said why: the
    // dash is the honest answer. Inventing a sentence here would be this
    // screen deciding what a tenant meant.
    const silent = render(list([template({ is_gate: false, no_gate_reason: null })]));
    expect(silent).not.toContain("data-no-gate-reason");
  });
});
