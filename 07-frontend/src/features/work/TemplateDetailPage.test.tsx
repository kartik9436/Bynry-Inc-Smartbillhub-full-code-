// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-018 (versions, and what v2 means) · US-WRK-015 (Duplicate ·
//           Deactivate · Delete-refused).  Screens: Work-022
// Rules:    BR-WRK-008 · BR-WRK-012 · BR-SHL-025 · B14 rules 2 · 6 · 20 · 31 · 32
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { queryKeys } from "@/api/queryClient";

import {
  TemplateDetailPage,
  WORK_TEMPLATE_DETAIL_SCREEN,
  deleteBlockedReason,
  templateTabs,
} from "./TemplateDetailPage";
import type { TemplateDetail, TemplateVersions } from "./workEndpoints";

const TENANT = "brazosbend";
const ID = "t-meter-exchange";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** `US-WRK-018` §4's own fixture: `ST-0002`, v1 four orders, v2 thirty-one. */
const DETAIL: TemplateDetail = {
  id: ID,
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
  orders_raised: 35,
  bundle: {
    details: {
      show_account_summary: true,
      show_asset_card: true,
      show_access_notes: true,
      show_appointment: true,
      // CR-070 wave E — the builder's step 7, `work/0005`. What the TEMPLATE
      // asks for; what a technician captured is `work_order_signatures`.
      signature_required: true,
      refusal_reason_required: true,
      door_hanger_on_no_answer: true,
    },
    safety: [{ seq: 1, text: "Isolate at the service head before removal", is_mandatory: true }],
    tasks: [
      { seq: 1, title: "Verify meter ID matches work order", est_minutes: 3, photo_required: true, is_mandatory: false },
    ],
    materials: [],
    readings: [],
    help: [],
    asset_types: [],
  },
};

const VERSIONS: TemplateVersions = {
  template_no: "ST-0002",
  name: "Meter exchange — residential",
  orders_raised: 35,
  versions: [
    {
      version: 2,
      published_at: "2026-02-28T09:00:00Z",
      published_by: "u-torres",
      change_note: "Added Apply tamper seal",
      orders_raised: 31,
      status: "current",
    },
    {
      version: 1,
      published_at: "2026-01-04T09:00:00Z",
      published_by: "u-reed",
      change_note: "First publish",
      orders_raised: 4,
      status: "superseded",
    },
  ],
};

function render(tab: string, detail: TemplateDetail | null = DETAIL): string {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: detail !== null } },
  });
  if (detail !== null) {
    queryClient.setQueryData(queryKeys.workTemplate(ID), detail);
    queryClient.setQueryData(queryKeys.workTemplateVersions(ID), VERSIONS);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      {/* Mounted under the REAL path pattern — `useParams().templateId` is what
          every query in this screen is keyed by, and a bare mount would key
          them all on "" and quietly render an empty screen that passes. */}
      <MemoryRouter initialEntries={[`/${TENANT}/work/templates/${ID}?tab=${tab}`]}>
        <Routes>
          <Route path="/:tenant/work/templates/:templateId" element={<TemplateDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("US-WRK-018 — the template detail (Work-022, template W5)", () => {
  it("draws the four tabs in the pack's order, Audit last", () => {
    expect(templateTabs(t).map((tab) => tab.id)).toEqual([
      "overview",
      "usage",
      "versions",
      "audit",
    ]);
  });

  it("the kicker carries the NUMBER and the version, never the uuid (B14 rule 31)", () => {
    const html = render("overview");
    expect(html).toContain("ST-0002");
    expect(html).toContain(`data-screen="${WORK_TEMPLATE_DETAIL_SCREEN}"`);
    expect(html).not.toContain(`>${ID}<`);
  });

  it("TC-1 — v2 reads Current above v1 Superseded, each with its own count", () => {
    const html = render("versions");
    expect(html).toContain('data-template-versions=""');
    expect(html).toContain("Added Apply tamper seal");
    expect(html).toContain(">31<");
    expect(html).toContain(">4<");
    const currentAt = html.indexOf("v2");
    const supersededAt = html.indexOf("v1");
    expect(currentAt).toBeGreaterThan(-1);
    expect(currentAt).toBeLessThan(supersededAt);
  });

  it("the versions footer says nothing was rewritten — BR-WRK-008 made readable", () => {
    const html = render("versions");
    expect(html).toContain('data-template-versions-footer=""');
    expect(html).toContain("35");
  });

  it("TC-4 — Delete is disabled and its reason carries the NUMBER of orders", () => {
    const reason = deleteBlockedReason(DETAIL, t);
    expect(reason).not.toBeNull();
    expect(reason).toContain("35");
    const html = render("overview");
    expect(html).toContain("disabled");
  });

  it("a template nothing was raised from CAN be deleted — the block is a fact, not a posture", () => {
    expect(deleteBlockedReason({ ...DETAIL, orders_raised: 0 }, t)).toBeNull();
  });

  it("a draft with no versions says so rather than drawing an empty table", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(queryKeys.workTemplate(ID), { ...DETAIL, version: 0 });
    queryClient.setQueryData(queryKeys.workTemplateVersions(ID), {
      ...VERSIONS,
      versions: [],
      orders_raised: 0,
    });
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/${TENANT}/work/templates/${ID}?tab=versions`]}>
          <Routes>
            <Route path="/:tenant/work/templates/:templateId" element={<TemplateDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(html).toContain('data-template-no-versions=""');
  });

  it("the way out is `← Templates`, and it is tenant-relative", () => {
    const html = render("overview");
    expect(html).toContain(`href="/${TENANT}/work/templates"`);
    expect(html).not.toContain('href="//work/templates');
  });

  // ⚠ **THE HOLD EXPIRED ON 2026-09-05 AND THIS IS WHAT IT BECAME.**
  //
  // Until CR-070 wave E this case asserted the button's ABSENCE, because the
  // eight-step builder did not exist. It landed, this case went red and named
  // the button, and the primary was added in the same commit — `DEF-CWP-3925`'s
  // prevention run once end to end. It now asserts the DESTINATION by address,
  // so a refactor that unpoints it fails here rather than silently.
  it("*Edit template* is LIVE and opens the builder on THIS template", () => {
    const html = render("overview");
    expect(html).toContain("Edit template");
    expect(html).toContain(`href="/${TENANT}/work/templates/${ID}/edit"`);
    expect(html).not.toContain('href="//work/templates');
  });
});
