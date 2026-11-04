// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-004 (EP-WRK-01) — the Work rail entry becomes the shell.
//           TC-3 (the not-built-yet page is gone and no sentence says
//           "still being decided") · TC-4 (no id in the rendered copy) ·
//           TC-6 (the rail entry sits between Payments and Finance, unchanged)
// Rules:    BR-WRK-005 · BR-SHL-001 · BR-SHL-044 / B14 rule 2 (one page
//           header, and it is what draws a tab strip) · rule 36 (compose the
//           kit) · rules 18 · 21 · 31 · 32 · CLAUDE.md hard-won law 2 (a tab
//           pointing at nothing is dead UI)
// ───────────────────────────────────────────────────────
//
// ⚠ **AMENDED 2026-09-05 (`DEF-WRK-3955`) — THE STRIP IS THE SHARED PAGE
// HEADER'S NOW, SO THESE ASSERTIONS READ THE RENDERED APP RATHER THAN A
// STANDALONE COMPONENT.** `renderStrip` used to mount `<WorkTabs active=…/>`
// bare, which could only ever prove the thing it was handed. Reading the strip
// out of the routed app proves the thing a person sees, including that the
// header the strip sits in is the ONE header on the screen — the assertion
// that would have gone red on the defect and did not exist.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, useRoutes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
import { SHELL_NAV } from "@/components/AppShell";
import { UNBUILT_SIDEBAR_DESTINATIONS } from "@/components/NotBuiltYet";
import { ToastProvider } from "@/components/Toast";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import type { MyPermissions, SessionUser } from "@/api/endpoints";

import { activeWorkTab, WORK_ORDERS_ROUTE, WORK_ROUTE, WORK_TABS, WorkShell } from "./WorkShell";
import { SEEDED_REGIONAL } from "@/components/tenantRegionalFixture";

const TENANT = "brazosbend";
const CATCH_ALL_MARKER = 'data-not-built-yet="true"';

const DANA: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@brazosbend.example",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};
const ADMIN: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: ["settings_lookups", "accounts", "premises_units"].map((code) => ({
    code,
    label: code,
    access: "Full" as const,
  })),
};

function RoutedApp() {
  return useRoutes(APP_ROUTES);
}

/** The whole app at one address, with nothing allowed to fetch (routing only). */
function renderApp(url: string): string {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  // DEF-SHL-3964 — this mounts the REAL shell, and the shell now renders no
  // routed screen until it knows the tenant's date format and time zone. A
  // test that mounts the product says which tenant it is testing.
  // DEF-SHL-4272 — the shell boots on `GET /shell/display` (every signed-in
  // role), not on the two Admin/Executive settings reads. Without this seed
  // the shell holds and every address renders a loading skeleton.
  queryClient.setQueryData(queryKeys.shellDisplay, shellBootSeed(SEEDED_REGIONAL));
  queryClient.setQueryData(queryKeys.regionalSettings, SEEDED_REGIONAL);
  queryClient.setQueryData(queryKeys.me, DANA);
  queryClient.setQueryData(queryKeys.myPermissions, ADMIN);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[url]}>
          <RoutedApp />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The strip as a person meets it: inside the routed app, inside the screen's
 *  own page header. */
function renderStrip(tab: "orders" | "templates"): string {
  return renderApp(tab === "orders" ? `/${TENANT}${WORK_ROUTE}` : `/${TENANT}/work/templates`);
}

describe("US-WRK-004 — the Work shell", () => {
  it("TC-3: /work is a screen now, not the not-built-yet page, and nothing says 'still being decided'", () => {
    const html = renderApp(`/${TENANT}${WORK_ROUTE}`);
    expect(html).not.toContain(CATCH_ALL_MARKER);
    expect(html).toContain('data-work-shell=""');
    expect(html).toContain('data-work-active-tab="orders"');
    expect(html).toContain('data-work-orders=""');
    expect(html).not.toContain("still being decided");
    expect(html).not.toContain("not built yet");
    // The register that used to name /work is empty — the mechanism stays.
    expect(UNBUILT_SIDEBAR_DESTINATIONS.find((entry) => entry.path === WORK_ROUTE)).toBeUndefined();
  });

  // ⚠ AMENDED 2026-09-05 (CR-070 wave D): the Templates tab no longer opens a
  // BLANK page. `Work-013` replaced it, so `data-work-order-templates` — the
  // blank page's own marker — is gone with the file, and the marker asserted
  // here is the list's. The tab itself and the strip around it are unchanged.
  it("/work/orders is the same screen, and /work/templates renders the LIST under the strip", () => {
    expect(renderApp(`/${TENANT}${WORK_ORDERS_ROUTE}`)).toContain('data-work-active-tab="orders"');
    const templates = renderApp(`/${TENANT}/work/templates`);
    expect(templates).toContain('data-work-active-tab="templates"');
    expect(templates).toContain('data-work-templates=""');
    expect(templates).not.toContain(CATCH_ALL_MARKER);
    // The stated absence went with the commit that made it untrue (law 2's
    // mirror, `DEF-CWP-3925`): there IS a writer for `work_order_templates`
    // now, so a screen still saying *not built yet* would be the dead refusal
    // over a live screen that law names.
    expect(templates).not.toContain("not built yet");
  });

  // CR-168-BRC10 §30 — At risk is its OWN screen at its OWN address, mounted
  // by the real router (law 2: assert the destination by ADDRESS and by the
  // screen it opens, `WRK-25`), and the 2.514.0 view no longer draws it.
  it("/work/at-risk opens the At risk tab, WRK-25, under the strip", () => {
    const html = renderApp(`/${TENANT}/work/at-risk`);
    expect(html).toContain('data-work-active-tab="at-risk"');
    expect(html).toContain('data-work-at-risk=""');
    expect(html).toContain('data-screen="WRK-25"');
    expect(html).toContain('data-tab="at-risk" aria-selected="true"');
    expect(html).not.toContain(CATCH_ALL_MARKER);
  });

  // ⚠ AMENDED 2026-09-04 (CR-070 wave C): THREE, because Parts has a screen now.
  // ⚠ AMENDED AGAIN 2026-09-04 (CR-070 wave B): FOUR — *Awaiting approval*
  // (`Work-009`) landed hours after Parts, from a different lane, into this same
  // array. This assertion is the guard that stops a tab going missing when two
  // lanes edit `WORK_TABS` in the same hour, and it has now gone RED for that
  // reason on two consecutive commits, which is exactly what it is for: the
  // failure it prints names the tab that would have been dropped.
  it("the strip renders ONLY the tabs whose screen exists at this wave — eight (law 2)", () => {
    // ⚠ **FOUR BECAME FIVE ON 2026-09-05 (CR-070 wave F, `Work-023`).** This
    // assertion has now gone RED on three consecutive waves and that is what it
    // is FOR: the wave that lands a screen adds its tab in the same commit, and
    // the failure names the tab that arrived or would have been dropped.
    //
    // ⚠ AND *Crews* SITS BEFORE *Parts*, WHICH IS NOT THE ORDER IT WAS BUILT
    // IN. The inventory draws the strip as *Orders · Awaiting approval · Map ·
    // Crews · Parts · Templates · Rules · Performance*, and the strip is read by
    // a dispatcher rather than by a changelog — a strip that grew in commit
    // order would reshuffle itself under a clerk every wave.
    expect(WORK_TABS.map((tab) => tab.id)).toEqual([
      "orders",
      // ⚠ **NINE SINCE CR-168-BRC10 §30 (2026-10-05) — At risk left the
      // Performance views and became a tab RIGHT AFTER ORDERS**, by the PO's
      // answer (1): *"Make At risk its own tab next to Orders"*. The one tab
      // placed by a ruling rather than by the inventory's order.
      "at-risk",
      "approvals",
      // ⚠ **TEN SINCE CR-187-BRC10 (2026-10-21) — `Work-034`, *From the
      // field*, landed with its tab in the same commit, beside Approvals: the
      // drawn queue and what the handsets sent are two halves of one desk.
      "field",
      // ⚠ **SIX SINCE CR-070 WAVE I (2026-09-05) — the Map screen landed, so
      // its tab did, in the same commit.** This assertion has now gone red on
      // FOUR consecutive waves, which is exactly its job.
      "map",
      "crews",
      "parts",
      "templates",
      // ⚠ **EIGHT SINCE CR-070 WAVE M (2026-09-05) — `Work-026` landed, so
      // its tab did, in the same commit — and it went BETWEEN Templates and
      // Performance, which is where wave N's own note in `WorkShell.tsx` said
      // it would go rather than on the end.** SIX consecutive waves have turned
      // this assertion red and every one was the assertion working: it names
      // the tab that arrived, so a screen cannot ship with no door onto it and
      // a door cannot ship pointing at nothing.
      "rules",
      "performance",
    ]);
    const html = renderStrip("orders");
    for (const built of [
      "orders",
      "at-risk",
      "approvals",
      "field",
      "map",
      "crews",
      "parts",
      "templates",
      "rules",
      "performance",
    ]) {
      expect(html).toContain(`data-tab="${built}"`);
    }
    // ⚠ **THE UNBUILT LIST IS NOW EMPTY, AND EMPTY IS A STATEMENT.** It held
    // "rules" until CR-070 wave M landed `Work-026`, and this loop is what went
    // RED on the day it did — naming the tab that arrived. Every tab the
    // inventory draws now has a screen behind it. A later wave that adds a
    // ninth puts it here first and inherits the check rather than re-inventing
    // it, which is what nobody does (hard-won law 2's mirror clause).
    for (const unbuilt of [] as string[]) {
      expect(html).not.toContain(`data-tab="${unbuilt}"`);
    }
    // Each tab is still a LINK to a tenant-relative path. `PageHeaderTab.to`
    // was added to the kit in the commit that deleted this module's own strip,
    // precisely so that composing the kit cost no behaviour: a tab that
    // navigates stays ⌘-clickable and copy-linkable.
    expect(html).toContain(`href="/${TENANT}${WORK_ORDERS_ROUTE}"`);
    expect(html).toContain(`href="/${TENANT}/work/awaiting-approval"`);
    expect(html).toContain(`href="/${TENANT}/work/crews"`);
    expect(html).toContain(`href="/${TENANT}/work/parts"`);
    expect(html).toContain(`href="/${TENANT}/work/templates"`);
    expect(html).toContain(`href="/${TENANT}/work/rules"`);
    // §30 — the At risk tab is a link to its OWN address, never to a view of
    // Performance (hard-won law 2: assert the destination by address).
    expect(html).toContain(`href="/${TENANT}/work/at-risk"`);
    expect(html).not.toContain("view=at-risk");
    // CR-187-BRC10 — the *From the field* tab is a link to `Work-034`'s address.
    expect(html).toContain(`href="/${TENANT}/work/field"`);
  });

  // ⚠ **THE ASSERTION THE DEFECT WOULD HAVE FAILED, AND IT IS THE ONLY ONE
  // THAT MATTERS HERE (`DEF-WRK-3955`).** Everything above passed on the boxed
  // strip: it rendered, it linked, it marked the active tab, it named no id.
  // What nothing asked was whether the strip was the KIT'S — so Work drew a
  // second one and looked different from the other eight features for two days
  // with every check green.
  it("the strip is the SHARED page header's, and there is exactly one header on the screen", () => {
    for (const url of [
      `/${TENANT}${WORK_ROUTE}`,
      `/${TENANT}${WORK_ORDERS_ROUTE}`,
      `/${TENANT}/work/awaiting-approval`,
      `/${TENANT}/work/parts`,
      `/${TENANT}/work/templates`,
    ]) {
      const html = renderApp(url);
      // The kit drew it: `.page-header-tabs` is `PageHeader`'s own class and no
      // Work file may declare a second one (B14 rules 21 and 36).
      expect(html).toContain('data-page-header-tabs=""');
      expect(html).toContain('class="page-header-tabs"');
      // And the module's own hand-rolled markers are GONE, by name.
      expect(html).not.toContain("data-work-tabs");
      expect(html).not.toContain("data-work-tab=");
      // One header, one strip — B14 rule 2. A screen that drew its own strip
      // above the header had two, which is what this counts.
      expect(html.split('class="page-header-tabs"').length - 1).toBe(1);
      expect(html.split('class="page-header"').length - 1).toBe(1);
    }
  });

  // B14 rule 18 — a description caps at 80% of the content width
  // (`--desc-measure`). The sentence rode in `page-header-rollup`, which sets
  // no width at all, so it ran the full width of the window on every Work
  // screen. `page-header-explainer` is the slot that carries the cap.
  it("each screen's one sentence is the tab's EXPLAINER, so rule 18's 80% cap reaches it", () => {
    for (const [url, sentence] of [
      [`/${TENANT}${WORK_ROUTE}`, "Everything open, across every connection and every account."],
      [`/${TENANT}/work/awaiting-approval`, "The field has finished these. Nobody has accepted them yet."],
      [`/${TENANT}/work/parts`, "What your crews fit, and what each one costs."],
    ] as const) {
      const html = renderApp(url);
      expect(html).toContain("page-header-explainer");
      const explainer = html.slice(html.indexOf("page-header-explainer"));
      expect(explainer).toContain(sentence);
      // ...and the strip comes FIRST, which is the kit's own order: the strip
      // is what a returning user reaches for before they read anything.
      expect(html.indexOf("page-header-tabs")).toBeLessThan(html.indexOf("page-header-explainer"));
    }
  });

  // The active tab is derived from the URL, never restated by a screen — two
  // answers to one question is how a strip ends up pointing at the wrong tab
  // the day a route moves.
  it("the active tab comes from the address", () => {
    expect(activeWorkTab(`/${TENANT}/work`)).toBe("orders");
    expect(activeWorkTab(`/${TENANT}/work/`)).toBe("orders");
    expect(activeWorkTab(`/${TENANT}/work/orders`)).toBe("orders");
    expect(activeWorkTab(`/${TENANT}/work/awaiting-approval`)).toBe("approvals");
    expect(activeWorkTab(`/${TENANT}/work/at-risk`)).toBe("at-risk");
    expect(activeWorkTab(`/${TENANT}/work/parts`)).toBe("parts");
    expect(activeWorkTab(`/${TENANT}/work/templates`)).toBe("templates");
    // A record detail is NOT one of the tabs, and lighting one up would tell a
    // reader they are somewhere they are not.
    expect(activeWorkTab(`/${TENANT}/work/templates/abc`)).toBeNull();
  });

  it("marks the active tab, and only it", () => {
    const orders = renderStrip("orders");
    expect(orders).toContain('data-tab="orders" aria-selected="true"');
    expect(orders).toContain('data-tab="templates" aria-selected="false"');
    expect(orders).toMatch(/data-tab="orders" aria-selected="true" class="active"/);
    const templates = renderStrip("templates");
    expect(templates).toContain('data-tab="templates" aria-selected="true"');
    expect(templates).toContain('data-tab="orders" aria-selected="false"');
  });

  it("TC-4: no rule id, question id, screen id or uuid reaches the rendered copy (B14 rule 31)", () => {
    const html = renderApp(`/${TENANT}${WORK_ROUTE}`);
    const visible = html.replace(/<[^>]*>/g, " ");
    expect(visible).not.toMatch(/\bBR-[A-Z]{3}-\d+|\bOQ-(?:[A-Z]{3}-)?\d+|\bDEF-(?:[A-Z]{3}-)?\d+|\bUS-[A-Z]{3}-\d+|\bWork-0\d\d\b|\bWS-\d\d\b/);
    expect(visible).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/);
  });

  it("TC-6: the rail entry is unchanged — Work sits between Payments and Finance", () => {
    const paths = SHELL_NAV.map((item) => item.path);
    const work = paths.indexOf(WORK_ROUTE);
    expect(work).toBeGreaterThan(paths.indexOf("/payments"));
    expect(work).toBeLessThan(paths.indexOf("/finance"));
    expect(SHELL_NAV.find((item) => item.path === WORK_ROUTE)?.children).toBeUndefined();
  });

  it("the frame carries the screen it was handed, and draws no strip of its own", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={[`/${TENANT}${WORK_ROUTE}`]}>
        <WorkShell tab="orders">
          <p data-child="">hello</p>
        </WorkShell>
      </MemoryRouter>,
    );
    expect(html).toContain('data-work-shell=""');
    expect(html).toContain('data-child=""');
    // The frame is a frame. The strip belongs to the screen's page header,
    // which is what B14 rule 2 means by ONE page header.
    expect(html).not.toContain("data-work-tabs");
    expect(html).not.toContain("page-header-tabs");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-004@67caa1a9 (EP-WRK-01 §3 TC-3 · TC-4 · TC-6)
// generated: 2026-09-03 by the CR-070 wave A build lane
// checklist: A=n/a B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST — with the /work register entry left in NotBuiltYet.tsx and the old route table, TC-3 fails on the catch-all marker; quoted in the lane report
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
