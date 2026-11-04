// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-003 (EP-TEN-03 §Stories)  Screens: S62
// Rules:    BR-TEN-015 (computed from live data; manual mark-done for advisory items only) · BR-TEN-016 (audited)
// ───────────────────────────────────────────────────────
// TC tests for S62. Markup asserts on react-dom/server static output
// (MemoryRouter + QueryClientProvider with the checklist seeded — the page
// links and reads); the laws run through the exported pure pieces. The server
// is the only place completion is computed, so most of this file proves the
// page RENDERS the server's verdict rather than forming one.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type { Checklist } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";

import {
  ChecklistPage,
  DASHBOARD_ROUTE,
  checklistTargetPath,
  firstIncomplete,
  itemDescKey,
  itemTitleKey,
} from "./ChecklistPage";

// §4 test data — Brazos Bend immediately post-signup: 2 services enabled at
// signup, everything else absent, so Company profile is INCOMPLETE.
const FRESH_TENANT: Checklist = {
  items: [
    {
      item: "company_profile",
      kind: "computed",
      done: false,
      source: null,
      target: "settings/company",
    },
    {
      item: "services_uom",
      kind: "computed",
      done: true,
      source: "computed",
      target: "settings/services",
    },
    { item: "rates_taxes", kind: "advisory", done: false, source: null, target: "plans-rates" },
    {
      item: "fiscal_billing",
      kind: "computed",
      done: false,
      source: null,
      target: "settings/regional",
    },
    {
      item: "numbering_documents",
      kind: "advisory",
      done: false,
      source: null,
      target: "settings/number-series",
    },
    { item: "invite_team", kind: "advisory", done: false, source: null, target: "settings/users" },
  ],
  progress: { done: 1, total: 6 },
  complete: false,
};

// S62 lives at `/{tenant}/checklist` (PO 2026-08-10) — which is exactly where
// the S114 commit now lands the new owner.
const TENANT = "brazosbend";

function renderChecklist(checklist: Checklist, tenant = TENANT): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.checklist, checklist);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${tenant}/checklist`]}>
        <ChecklistPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("US-TEN-003 — post-signup checklist surfacing Company gaps (S62)", () => {
  it("US-TEN-003 TC-1: a fresh tenant shows Company profile incomplete, Services complete, '1 of 6 complete'", () => {
    const html = renderChecklist(FRESH_TENANT);
    expect(html).toContain("1 of 6 complete");
    expect(html).toContain("Company profile");
    expect(html).toContain("Services &amp; units of measure");
    // The complete item carries the done state; the incomplete one does not.
    // CR-018 Route B: the state handle is `data-checklist-item="done|open"`
    // now — the class pair it grepped for was deleted with ChecklistPage.css.
    expect(html).toContain('data-checklist-item="done"');
    expect(html).toContain('data-checklist-item="open"');
  });

  it("US-TEN-003 TC-2: completing the data completes the item — no manual toggle exists for computed items (BR-TEN-015)", () => {
    const filled: Checklist = {
      ...FRESH_TENANT,
      items: FRESH_TENANT.items.map((item) =>
        item.item === "company_profile"
          ? { ...item, done: true, source: "computed" as const }
          : item,
      ),
      progress: { done: 2, total: 6 },
    };
    const html = renderChecklist(filled);
    expect(html).toContain("2 of 6 complete");
    // Mark-done is offered for the three ADVISORY items only — never for a
    // computed one (the server refuses those with 409 BIZ-STATE anyway).
    const markDoneCount = html.split("Mark as done").length - 1;
    expect(markDoneCount).toBe(3);
  });

  it("US-TEN-003 TC-3: 'Finish later' opens the app and the checklist stays reachable", () => {
    const html = renderChecklist(FRESH_TENANT);
    expect(html).toContain("Finish later — open the app");
    expect(DASHBOARD_ROUTE).toBe("/dashboard");
    // Nothing here writes a "dismissed forever" flag: state lives server-side
    // (tenants.checklist_state) and the route stays open.
    expect(html).not.toContain("dismiss-forever");
  });

  it("BR-TEN-015: every item deep-links to the Settings tab that fills it, and 'Continue setup' targets the first gap", () => {
    const html = renderChecklist(FRESH_TENANT);
    // PO 2026-08-10: the server still sends a tenant-RELATIVE fragment
    // ("settings/company") and the page adds the tenant — so one server answer
    // serves every tenant and no link can leave the current one.
    expect(html).toContain('href="/brazosbend/settings/company"');
    expect(html).toContain('href="/brazosbend/settings/services"');
    expect(html).toContain('href="/brazosbend/plans-rates"');
    expect(checklistTargetPath("settings/company")).toBe("/settings/company");
    expect(checklistTargetPath("/already-absolute")).toBe("/already-absolute");
    expect(firstIncomplete(FRESH_TENANT.items)?.item).toBe("company_profile");
    expect(firstIncomplete([])).toBeNull();
    // The same checklist rendered under another tenant links there instead.
    expect(renderChecklist(FRESH_TENANT, "lonestar")).toContain(
      'href="/lonestar/settings/company"',
    );
  });

  it("copy is keyed by the server's stable item code, never by row position", () => {
    expect(itemTitleKey("company_profile")).toBe("tenancy.checklist.item.company_profile.title");
    expect(itemDescKey("invite_team")).toBe("tenancy.checklist.item.invite_team.desc");
    // A code the catalog does not know renders its key — visible, never a crash
    // and never invented prose.
    const html = renderChecklist({
      ...FRESH_TENANT,
      items: [
        { item: "future_item", kind: "advisory", done: false, source: null, target: "settings" },
      ],
      progress: { done: 0, total: 1 },
    });
    expect(html).toContain("tenancy.checklist.item.future_item.title");
  });

  it.todo(
    "US-TEN-003 TC-4: a Billing Clerk opening the deep-links gets disabled-with-reason + a server refusal — route RBAC is FI-04/EP-SHL-06 and the Settings screens are later packets",
  );
  it.todo(
    "US-TEN-003 TC-5 (isolation): a Lone Star Ridge admin sees only their own completion state — server/RLS scope (G5)",
  );
  it.todo(
    "browser scope → Playwright journey J1: landing here after the S114 commit, clicking a deep link, and marking an advisory item done",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-003@d5f8c32 (story+rules snapshot hash — EP-TEN-03)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 144/144✔ (13 todo this packet — browser/journey/v2-deferred scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
