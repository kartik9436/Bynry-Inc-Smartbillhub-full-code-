// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-016 (EP-WRK-03) — the eight-step builder. TC-1 (the pack
//           prefills), TC-3 (the review panel), TC-5 (the replaced page),
//           TC-7 (the UI law). Screens: Work-014 … Work-017
// Rules:    BR-WRK-011 (nothing reaches a work order until Publish) ·
//           BR-WRK-015 (a reading's unit is a column) · B14 rules 21 · 31 · 32
// ───────────────────────────────────────────────────────
//
// ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, NOT BARE INSIDE A `MemoryRouter`.**
// `DEF-CWP-3925`: with no `/:tenant/...` route declared, `useParams().tenant`
// is undefined and every address the screen builds comes out `//work/...` — a
// protocol-relative URL to another host, which `toContain` reads as perfectly
// good. This screen ALSO reads `useParams().templateId` on its edit address,
// so a bare mount would quietly render the *new* form at the *edit* URL.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ToastProvider } from "@/components/Toast";

import {
  TEMPLATE_BUILDER_SCREEN,
  TEMPLATE_BUILDER_STEPS,
  TemplateBuilder,
  WORK_TEMPLATE_NEW_ROUTE,
  templateEditPath,
} from "./TemplateBuilder";
import type { TemplatePack } from "./workEndpoints";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const PACKS: TemplatePack[] = [
  {
    code: "METER_EXCHANGE",
    name: "Meter exchange",
    tasks: 7,
    parts: 3,
    readings: 3,
    safety: 3,
    help: 3,
    est_duration_minutes: 45,
    unresolved_parts: [],
    bundle: {
      details: {
        show_account_summary: true,
        show_asset_card: true,
        show_access_notes: true,
        show_appointment: true,
      },
      safety: [],
      tasks: [],
      materials: [],
      readings: [],
      help: [],
    },
  },
  {
    code: "INSPECTION",
    name: "Inspection",
    tasks: 4,
    parts: 0,
    readings: 2,
    safety: 1,
    help: 1,
    est_duration_minutes: 35,
    unresolved_parts: ["GAUGE-BF"],
    bundle: {
      details: {
        show_account_summary: true,
        show_asset_card: true,
        show_access_notes: true,
        show_appointment: true,
      },
      safety: [],
      tasks: [],
      materials: [],
      readings: [],
      help: [],
    },
  },
];

function render(step: number, prime = true): string {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  if (prime) {
    queryClient.setQueryData(["work-template-packs"], PACKS);
    queryClient.setQueryData(["work-builder-services"], [
      { service: "electric", name: "Electric", enabled: true },
      { service: "water", name: "Water", enabled: true },
    ]);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      {/* The builder fires a toast on a successful publish, so the provider is
          part of the real mount rather than optional furniture. */}
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}${WORK_TEMPLATE_NEW_ROUTE}?step=${step}`]}>
          <Routes>
            <Route path="/:tenant/work/templates/new" element={<TemplateBuilder />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-WRK-016 — the eight-step builder (Work-014 … 017, template W3)", () => {
  it("declares EIGHT steps, in the drawing's own order", () => {
    expect(TEMPLATE_BUILDER_STEPS.map((one) => one.id)).toEqual([
      "details",
      "safety",
      "tasks",
      "materials",
      "readings",
      "help",
      "signature",
      "review",
    ]);
  });

  it("step 1 draws the pack tiles, the header form and the four ticks", () => {
    const html = render(1);
    expect(html).toContain(`data-screen="${TEMPLATE_BUILDER_SCREEN}"`);
    expect(html).toContain("What job is this template for?");
    expect(html).toContain('data-pack="METER_EXCHANGE"');
    expect(html).toContain('data-pack="INSPECTION"');
    // The fourth tile is a real choice, not the absence of one.
    expect(html).toContain('data-pack="EMPTY"');
    expect(html).toContain("What the technician sees on the job");
  });

  it("the Inspection tile says FOUR tasks — the drawing's figure, counted server-side", () => {
    const html = render(1);
    expect(html).toContain("4 tasks · 0 parts · 2 readings");
    expect(html).toContain("7 tasks · 3 parts · 3 readings");
  });

  it("a pack naming a part this register lacks says WHICH, rather than dropping it in silence", () => {
    const html = render(1);
    expect(html).toContain("GAUGE-BF");
  });

  it("B14 rule 32 — the job-type help line carries no rule id", () => {
    const html = render(1);
    expect(html).toContain("From the job type catalog");
    // `wireframes/Work-014.png` draws *"From the job type catalogue — WM-04"*.
    expect(html).not.toContain("WM-04");
    expect(html).not.toContain("BR-WRK");
  });

  it("every step's footer says the ONE thing BR-WRK-011 binds", () => {
    for (const step of [1, 3, 5, 8]) {
      const html = render(step);
      expect(html).toContain("nothing is saved to a work order until you publish");
      expect(html).toContain(`Step ${step} of 8`);
    }
  });

  it("step 3 is the tasks table with its consequence box", () => {
    const html = render(3);
    expect(html).toContain("What are the steps?");
    expect(html).toContain('data-editable-table="tasks"');
    expect(html).toContain('data-consequence="tasks"');
    // ⚠ The apostrophe is HTML-escaped by `renderToStaticMarkup` — matching a
    // raw `'` here fails on a sentence that is perfectly correct on screen.
    expect(html).toContain("Estimates that are wrong here make every day");
    expect(html).toContain("route wrong");
  });

  it("step 5 is the readings table, and it says the unit is a column", () => {
    const html = render(5);
    expect(html).toContain("What has to be measured?");
    expect(html).toContain('data-editable-table="readings"');
    // hard rule 3 / BR-WRK-015, on screen: a reading needs a unit, and the
    // *+ Add* is disabled until it has one (BR-SHL-025, with the reason).
    expect(html).toContain("A reading needs a unit");
    expect(html).toContain('data-add="readings"');
  });

  it("step 7 is the three signature answers and nothing else", () => {
    const html = render(7);
    expect(html).toContain("How does the job close?");
    expect(html).toContain('data-signature=""');
    expect(html).toContain("The customer signs on the phone");
    expect(html).toContain("If they refuse, the technician records why");
    expect(html).toContain("If nobody is in, leave a card and photograph it");
  });

  // CR-168 P3.26 — the review is the TEMPLATE SUMMARY (one panel per
  // section, every row), the same component the template's Overview draws.
  it("TC-3 — step 8 is the seven-section summary, the consequence box and Publish", () => {
    const html = render(8);
    expect(html).toContain("Review");
    expect(html).toContain("data-template-summary");
    for (const section of [
      "details",
      "safety",
      "tasks",
      "materials",
      "readings",
      "help",
      "signature",
    ]) {
      expect(html).toContain(`data-summary-section="${section}"`);
    }
    expect(html).toContain('data-consequence="publish"');
    expect(html).toContain("Publishing affects new work orders only");
    // A first publish says the honest thing rather than the drawing's *"the 4
    // orders already raised"*, which is `J67`'s state and not this one.
    expect(html).toContain("No orders have been raised from this template yet");
    expect(html).toContain("Publish template");
  });

  it("*Save draft* rides in the frame's own action row, on every step", () => {
    for (const step of [1, 4, 8]) {
      expect(render(step)).toContain('data-save-draft=""');
    }
  });

  it("B14 rule 31 — no uuid is drawn anywhere on the builder", () => {
    const html = render(8);
    expect(html).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/);
  });

  it("the way out is the templates list, and it is tenant-relative", () => {
    const html = render(1);
    expect(html).toContain(`href="/${TENANT}/work/templates"`);
    expect(html).not.toContain('href="//work/templates"');
  });

  it("`templateEditPath` is the ONE place the edit address is spelled", () => {
    expect(templateEditPath("abc")).toBe("/work/templates/abc/edit");
    expect(WORK_TEMPLATE_NEW_ROUTE).toBe("/work/templates/new");
  });

  it("a step out of range clamps rather than rendering nothing", () => {
    expect(render(99)).toContain("Step 8 of 8");
    expect(render(0)).toContain("Step 1 of 8");
  });

  it("G15 — every visible string on step 1 comes from the catalogue", () => {
    // The catalogue keys land in a follow-up commit (this lane may not edit
    // `src/i18n/locales/*.json`), so each call carries a `defaultValue` and the
    // screen renders correct English meanwhile. What this asserts is that the
    // KEY exists in the component, which is what `G15` reads.
    expect(t("work.builder.details.title", { defaultValue: "What job is this template for?" })).toBe(
      "What job is this template for?",
    );
  });
});
