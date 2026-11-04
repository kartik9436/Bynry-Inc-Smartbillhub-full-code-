// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-001 · US-SHL-002 · US-SHL-003 · US-SHL-004 · US-SHL-005 (EP-SHL-01 §Stories)  Screens: shell-chrome (hosts every authenticated screen), S48
// Rules:    BR-SHL-001 (order/widths) · BR-SHL-002 (first-paint state) · BR-SHL-003 (nav hidden) · BR-SHL-004 (breadcrumb) · BR-SHL-007 (bell) · BR-SHL-008 (user block + the four-item S48 menu) · BR-SHL-025 (an item with no destination is disabled WITH its reason)
// ───────────────────────────────────────────────────────
// TC tests for FE-01 AppShell. Same conventions as the prior packet runs:
// no DOM library in package.json, so markup asserts on react-dom/server
// static output (wrapped in a MemoryRouter — the shell reads the route) and
// interaction laws run through the exported pure functions. Anything needing
// a live browser, the server, or another packet's code is an honest it.todo.
//
// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…`, so
// the shell is rendered under a tenant here and `renderShell` takes the
// TENANT-RELATIVE path the nav config is written in — exactly the split the
// component makes. `breadcrumbFor` stays a pure function of the relative path.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n"; // initializes the i18next singleton with the five catalogs
import i18n from "@/i18n"; // the instance itself, for the eleven-catalogue checks

// The version oracle. Change process §7 rule 1: package.json's `version` is the
// ONE source of truth, so the test reads it rather than repeating it.
import pkg from "../../package.json";

import {
  AppShell,
  BELL_BADGE_CAP,
  HELP_ROUTE,
  SHELL_NAV,
  USER_MENU_ITEMS,
  UserMenu,
  breadcrumbFor,
  initialsOf,
  visibleNavItems,
} from "./AppShell";
import type { AppShellProps } from "./AppShell";

const TENANT = "brazosbend";

/**
 * `path` is tenant-relative ("/billing"); the shell is mounted at /{tenant}.
 *
 * `onSignOut` became REQUIRED on 2026-08-11 — a frame that can render a
 * signed-in user must be able to sign them out (DEF-008) — so the helper
 * supplies a no-op default and the tests that care pass their own.
 */
function renderShell(path: string, props: Partial<AppShellProps> = {}, tenant = TENANT) {
  const full: AppShellProps = { onSignOut: () => undefined, ...props };
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[`/${tenant}${path}`]}>
      <AppShell {...full} />
    </MemoryRouter>,
  );
}

// §4 test data: Silver Creek Utilities session, Alex Reed (System Admin).
// The email joins it 2026-08-11: the S48 menu header reads "email · role", and
// the prototype's own line is "alex@silvercreek.example · Owner".
const alex = {
  fullName: "Alex Reed",
  email: "alex.reed@silvercreekutilities.com",
  roleName: "System Admin",
};

/**
 * The OPEN S48 popover. It is its own exported component precisely so it can be
 * rendered here: `renderToStaticMarkup` cannot click the footer block, and a
 * test-only `userMenuOpen` prop would have been one more optional prop the app
 * never passes — the exact shape of DEF-007..010.
 */
function renderMenu() {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[`/${TENANT}/dashboard`]}>
      <UserMenu user={alex} onSignOut={() => undefined} onDismiss={() => undefined} />
    </MemoryRouter>,
  );
}

// A4 addendum: Billing Clerk has no Settings and no Finance — this is the
// SERVER-computed accessible-module set for Jordan's membership (BR-SHL-025:
// never a client-side role-name check).
const billingClerkModules = [
  "dashboard",
  "plans-rates",
  "premises",
  "assets",
  "accounts",
  "reads",
  "billing",
  "payments",
  "reports",
];

describe("US-SHL-001 — collapsible sidebar navigation", () => {
  it("US-SHL-001 TC-1: the THIRTEEN items render in the BR-SHL-001 canonical order with inline-SVG icons; Billing has no submenu", () => {
    const html = renderShell("/dashboard");
    // PO ruling 2026-08-10 ("Setting should be at last on nav bar") — Settings
    // moved from second to LAST. This test failed on that change, which is what
    // it is for: it had pinned the BR-SHL-001 order while the prototype drew
    // Settings last, a divergence reported and left standing until the PO saw
    // the deployed sidebar.
    // BR-SHL-001 amendment 2 (PO 2026-08-16, prototype r10): Premises and
    // Assets SWAP, and Work joins between Payments and Finance — twelve items.
    // This assertion failed on that change, which is what it is for: it pinned
    // the old order, exactly as it did when Settings moved to last.
    // BR-SHL-001 amendment 3 (PO 2026-09-06, "Nav bar will have Runbook as menu
    // item - above reports module"): RUNBOOKS joins between Finance and
    // Reports — THIRTEEN items. It failed on that change too, and the failure
    // named the item, because the list below says WHICH label arrived rather
    // than only how many there are (DEF-3463: `expected 5 to be 4` reads like a
    // typo, so a real nav change sat red on the branch and nobody connected it
    // to the two other mirrors of the same list).
    const labels = [
      "Dashboard",
      "Plans &amp; Rates",
      "Premises",
      "Assets",
      "Accounts",
      "Reads",
      "Billing",
      "Payments",
      "Work",
      "Finance",
      "Runbooks",
      "Reports",
      "Settings",
    ];
    const sidebar = html.slice(html.indexOf("<aside"), html.indexOf("</aside>"));
    let cursor = -1;
    for (const label of labels) {
      const at = sidebar.indexOf(`<span class="side-label">${label}</span>`);
      expect(at, `${label} present in order`).toBeGreaterThan(cursor);
      cursor = at;
    }
    expect((sidebar.match(/class="side-item/g) ?? []).length).toBe(13);
    expect(sidebar).toContain("<svg"); // A12: inline SVG icons, no icon font
    // BR-SHL-001: Billing is a tabbed page — the config declares no submenu.
    expect(SHELL_NAV.find((i) => i.module === "billing")?.children).toBeUndefined();
    // …while the sectioned modules declare theirs.
    // PO ruling 2026-08-10: Plans & Rates has NO submenu — the four sub-paths
    // are the page's own tab strip, as the prototype draws them.
    // PO rulings 2026-08-10 (Plans & Rates, then Premises, each with a
    // prototype screenshot): the sidebar has NO submenus at all. Every
    // sub-destination is the page's own tab strip.
    // PO rulings 2026-08-10 (Plans & Rates, then Premises): the sidebar RENDERS
    // no submenus. The config keeps `children` — US-SHL-002's breadcrumb
    // resolves its second crumb from it — so the assertion is about the markup,
    // not the data.
    expect(renderShell("/finance")).not.toContain("side-sub");
    // ⚠ **A COUNT, AND IT COULD NOT NAME WHAT CHANGED (DEF-3463).** This read
    // `children?.length).toBe(4)` until 2026-09-03. CR-060 T10 added
    // `/finance/revenue` to the Finance children, the assertion failed with
    // `expected 5 to be 4`, and that sentence reads like a typo rather than
    // like a nav change — so the suite sat red on the branch while two other
    // mirrors of the same list (`sidebarDestinations.ts` and the screen-id map)
    // were red for the same one commit and nobody connected the three.
    //
    // The list says WHICH child arrived. It is the same discipline
    // `sidebarReachability.test.tsx` already runs on `SIDEBAR_DESTINATIONS` —
    // exact, in order, in both directions — and it was proved RED the way that
    // one was: dropping "/finance/revenue" from the array below fails with
    // *"expected [ …4 items ] to deeply equal [ …5 items ]"* NAMING the missing
    // path, and adding a "/finance/nowhere" fails naming that.
    expect(SHELL_NAV.find((i) => i.module === "finance")?.children?.map((c) => c.path)).toEqual([
      "/finance",
      "/finance/revenue",
      "/finance/deposits",
      "/finance/taxes",
      "/finance/export",
    ]);
  });

  it("US-SHL-001 TC-2 (partial): a stored collapsed preference renders collapsed in the FIRST static paint — no width flash", () => {
    // BR-SHL-002: the session wiring reads `shell.sidebar_collapsed` BEFORE
    // mounting the shell and passes it as the controlled prop; the very first
    // markup already carries the collapsed class (CSS: 64px, labels hidden).
    const collapsed = renderShell("/dashboard", { collapsed: true });
    expect(collapsed).toContain('class="app-shell collapsed"');
    expect(collapsed).toContain("<svg"); // icons remain on the collapsed rail
    expect(collapsed).toContain("Expand sidebar"); // topbar toggle takes over
    // Default (no stored preference) is expanded.
    const expanded = renderShell("/dashboard");
    expect(expanded).toContain('class="app-shell"');
    expect(expanded).toContain("Collapse sidebar");
  });

  it("US-SHL-001 TC-3: navigating to /billing highlights the Billing item and no other", () => {
    const html = renderShell("/billing");
    const active = html.match(/class="side-item active"[^>]*href="([^"]*)"/g) ?? [];
    expect(active.length).toBe(1);
    // The href carries the tenant; the highlight is decided on the relative path.
    expect(active[0]).toContain('href="/brazosbend/billing"');
  });

  it("BR-SHL-001 (PO 2026-08-10): EVERY nav target keeps the current tenant segment", () => {
    const html = renderShell("/premises/units");
    const allHrefs = [...html.matchAll(/href="([^"]*)"/g)].map((m) => m[1]);
    // ⚠ **AMENDED TWICE, AND THE SECOND AMENDMENT DELETES THE FIRST'S CARVE-OUT
    // (`DEF-SHL-7825`, 2026-09-29).** On 2026-08-21 `DEF-450` added r10's help
    // control, this case was told *"it is the one link in the frame that must
    // NOT carry a tenant segment"*, and an exception was written for it — one
    // absolute href, allowed by name. The exception was honest and the thing it
    // was protecting was not: that href went to another company's product
    // documentation, and this assertion is the one place in the repo that
    // NOTICED an off-product link and was amended to permit it.
    //
    // **So the carve-out is gone rather than re-aimed, and the rule is STRONGER
    // than before: NO href the shell frame draws leaves this product.** The day
    // a help destination exists it will be an external link again and this will
    // go red — which is correct, and the amendment then made is a deliberate
    // one rather than a reflex, because `AppShell.tsx`'s `HELP_ROUTE` docstring
    // and the `DEF-SHL-7825` block below say what to do.
    const external = allHrefs.filter((h) => h.startsWith("http"));
    expect(external).toHaveLength(0);
    const hrefs = allHrefs.filter((h) => !h.startsWith("http"));
    // Every nav item + the breadcrumb's clickable ancestor — all the INTERNAL
    // links the frame draws. It was +3 while Premises expanded two sub-items
    // into the rail; the PO removed sidebar submenus on 2026-08-10 and those
    // two links went with them (the destinations remain, as the page's own tab
    // strip). ⚠ THIS COMMENT SAID "11 nav items" while the rail drew twelve,
    // and now thirteen — the assertion itself is derived from SHELL_NAV.length
    // and was always right, so nothing failed and the sentence rotted quietly.
    // Hard-won law 1: a comment is a note, and a stale one is a note that lies.
    // +2 since 2026-10-22: the bell's one-click *Messages needing attention*
    // link (PO: *"clerks can still reach failed messages in one click from the
    // bell"*), which carries the tenant segment like every other.
    expect(hrefs.length).toBe(SHELL_NAV.length + 2);
    expect(hrefs).toContain("/brazosbend/settings/reference-data/notifications/messages");
    for (const href of hrefs) {
      expect(href.startsWith("/brazosbend/")).toBe(true);
    }
    // The config itself stays tenant-relative — one config, every tenant.
    for (const item of SHELL_NAV) {
      expect(item.path.startsWith("/brazosbend")).toBe(false);
      expect(hrefs).toContain(`/brazosbend${item.path}`);
    }
    // Another tenant, same code, different URLs — nothing is hardcoded.
    const other = renderShell("/premises/units", {}, "lonestar");
    // Was /lonestar/premises/units — the expanded sub-item link. With sidebar
    // submenus gone the nav item itself carries the proof, and the tenant
    // segment is the point of the assertion either way.
    expect(other).toContain('href="/lonestar/premises"');
    expect(other).not.toContain("/brazosbend/");
  });

  it("US-SHL-001 TC-4: Jordan Blake's (Billing Clerk) server-provided set hides Settings and Finance; the other nine render", () => {
    const visible = visibleNavItems(SHELL_NAV, billingClerkModules);
    expect(visible.map((i) => i.module)).toEqual(billingClerkModules);

    const html = renderShell("/dashboard", { accessibleModules: billingClerkModules });
    const sidebar = html.slice(html.indexOf("<aside"), html.indexOf("</aside>"));
    expect(sidebar).not.toContain(">Settings<");
    expect(sidebar).not.toContain(">Finance<");
    expect((sidebar.match(/class="side-item/g) ?? []).length).toBe(9);
  });

  it("US-SHL-001 (PO 2026-08-10): NO submenu renders under any section", () => {
    // Was "submenus expand under the active section only". The PO removed
    // submenus entirely after seeing the prototype: the same destinations were
    // listed twice, and the daily items sat below a stack of sub-links.
    for (const path of ["/payments", "/finance", "/premises", "/reads", "/plans-rates"]) {
      expect(renderShell(path)).not.toContain("side-sub");
    }
  });

  it.todo(
    "US-SHL-001 TC-2/TC-6: preference roundtrip via user_preferences (shell.sidebar_collapsed, per user AND tenant) — US-SHL-013's service + backend isolation suite scope",
  );
  it.todo(
    "US-SHL-001 TC-5: deep-link to /finance as Billing Clerk renders the A18 §6 permission-denied block with no data behind — route gating lands with FI-04 / EP-SHL-06's packet",
  );
});

describe("US-SHL-002 — topbar breadcrumb & title", () => {
  it("US-SHL-002 TC-1: /accounts renders breadcrumb 'Accounts' as the plain-text leaf", () => {
    expect(breadcrumbFor("/accounts", SHELL_NAV)).toEqual([
      { labelKey: "shell.nav.accounts" },
    ]);
    const html = renderShell("/accounts");
    const crumbs = html.slice(html.indexOf('class="crumbs"'), html.indexOf("shell-search"));
    expect(crumbs).toContain('<span class="cur">Accounts</span>');
    expect(crumbs).not.toContain("<a"); // a lone leaf is never a link
    // BR-SHL-004: the tab title mirrors the leaf — docTitle key carries the
    // pattern (set via effect; browser-side assertion is journey scope).
    expect(SHELL_NAV.find((i) => i.path === "/accounts")).toBeDefined();
  });

  it("US-SHL-002 TC-4 (partial): /finance/deposits renders 'Finance › Deposits & Bank' with a clickable ancestor", () => {
    expect(breadcrumbFor("/finance/deposits", SHELL_NAV)).toEqual([
      { labelKey: "shell.nav.finance", path: "/finance" },
      { labelKey: "shell.nav.finance.deposits" },
    ]);
    const html = renderShell("/finance/deposits");
    // The crumb is computed from the tenant-relative path and LINKED with the
    // tenant on it — a breadcrumb can never walk out of the current utility.
    expect(html).toContain('href="/brazosbend/finance"');
    expect(html).toContain('<span class="cur">Deposits &amp; Bank</span>');
    expect(html).toContain("›");
    expect(renderShell("/finance/deposits", {}, "lonestar")).toContain(
      'href="/lonestar/finance"',
    );
  });

  it("US-SHL-002 TC-3 (partial) + TC-5: deeper/unknown paths keep the module crumb — query state and bad ids never move it", () => {
    // TC-3: ?step= is query state — breadcrumbFor reads only the pathname,
    // so a wizard step change cannot move the leaf.
    expect(breadcrumbFor("/billing/run", SHELL_NAV)).toEqual([
      { labelKey: "shell.nav.billing" },
    ]);
    // TC-5: an unknown/bad record id falls back to the module crumb — no
    // crash, no UUID leaf (the A18 §4 content block is the detail screen's).
    expect(breadcrumbFor("/accounts/0198ffff-dead-7000-a000-000000000000", SHELL_NAV)).toEqual([
      { labelKey: "shell.nav.accounts" },
    ]);
    // An unroutable path renders no crumb at all rather than lying.
    expect(breadcrumbFor("/nonsense", SHELL_NAV)).toEqual([]);
  });

  it.todo(
    "US-SHL-002 TC-2/TC-4 (leaf): detail crumbs use the record's human identifier (A-10432, DEP-0806 — never a UUID) and ancestors restore prior URL state — lands with the consuming detail screens (FE-16) + FI-01",
  );
  it.todo(
    "US-SHL-002 (BR-SHL-004): browser tab title mirrors the breadcrumb leaf ('DEP-0806 · SMART360 Next') — document.title effect needs a browser; journey scope",
  );
});

describe("US-SHL-003 — global search (the box, wired 2026-09-03)", () => {
  // ══════════════════════════════════════════════════════════════════════
  // THE BOX SEARCHES. DEF-2423's ABSENCE STATE IS GONE, AND SO IS ITS COPY.
  // ══════════════════════════════════════════════════════════════════════
  //
  // From 2026-09-01 this input rendered DISABLED with "Search is not available
  // yet", because `onSearch` had no caller — the BE-08 kernel, the debouncer
  // and the ✕ all existed and no route joined them. `GET /search` exists now
  // and `ShellWithSession` passes the handler, so the disabled branch, its two
  // cases here and the `shell.search.unavailable` string in all eleven
  // catalogues are retired together. A test asserting copy that nothing renders
  // is the next lane's false lead.
  //
  // **AND `check_unwired_props.py`'s BY-NAME EXEMPTION FOR `AppShell.onSearch`
  // IS REMOVED IN THE SAME COMMIT.** It let G13 pass on purpose while the
  // endpoint was missing; left behind, it would leave the guard blind to this
  // prop forever and the next lane to break the wiring would not be told.
  it("US-SHL-003: the box is LIVE, named, and shows no ✕ while empty", () => {
    const html = renderShell("/dashboard", { onSearch: () => undefined });
    // ⚠ REWORDED. It used to read "Search accounts, premises, bills…" — three
    // of what are now NINE groups, so it was about to be wrong about six of
    // them. B14 rule 32 caps a description at one sentence; this names the ACT.
    expect(html).toContain('placeholder="Search"');
    expect(html).toContain('aria-label="Global search"');
    // ⚠ **NARROWED TO THE SEARCH BOX (`DEF-SHL-7825`, 2026-09-29).** This read
    // `expect(html).not.toContain("disabled")` over the WHOLE FRAME, so it was
    // asserting something about the sidebar, the bell and the user block that
    // it never meant and that nobody had agreed — law 7's *looking at the wrong
    // thing*. It went red the moment a NEIGHBOUR gained a lawful
    // `aria-disabled` (the help control, refusing per `BR-SHL-025`), which is a
    // true failure of a false claim. The subject of the sentence is the box, so
    // the assertion is now about the box.
    // ⚠ The ELEMENT first. `indexOf` returns -1 when the box is not drawn at
    // all, and `slice(-1)` would then hand a one-character string to a
    // `not.toContain` that passes on anything — a narrowed check that cannot
    // fail is worse than the broad one it replaced.
    const at = html.indexOf('<div class="shell-search"');
    expect(at).toBeGreaterThan(-1);
    const box = html.slice(at);
    expect(box.slice(0, box.indexOf("</div>"))).not.toContain("disabled");
    // IS-3: ✕ appears only once there is input to clear.
    expect(html).not.toContain("shell-search-clear");
    // IS-3 mechanics (300 ms debounce, min 2 chars) come from the ONE
    // createSearchDebouncer — its laws are proven in DataTable.test.tsx.
  });

  it("US-SHL-003: the shell RENDERS the results it is given — the last link in the chain", () => {
    // ⚠ The wiring is a CHAIN and each link is guarded separately, because a
    // break in any one of them is silent:
    //   ShellWithSession → AppShell   `ShellWithSession.wiring.test.tsx`
    //   AppShell → GlobalSearchResults  ← THIS CASE
    //   inside the popover              `GlobalSearchResults.test.tsx`
    // Without this one, AppShell could accept all five props and drop them, and
    // every other test in the product would still pass while the box showed
    // nothing — hard-won law 2 one component further along than usual.
    const html = renderShell("/dashboard", {
      onSearch: () => undefined,
      searchStatus: "ready",
      searchGroups: [
        {
          entity: "accounts",
          rows: [
            {
              id: "01a064d5-bf86-72bb-97d9-cdd65f650afe",
              label: "A-10432",
              context: "Maria Delgado",
              amount: null,
              currency: null,
            },
          ],
        },
      ],
    });
    expect(html).toContain("A-10432");
    expect(html).toContain("Maria Delgado");
    expect(html).toContain("Accounts"); // the group heading, from the catalogue
    // B14 rule 31 — the id reached the href and nothing else.
    expect(html.replace(/href="[^"]*"/g, "")).not.toContain("01a064d5-bf86");
  });

  it("US-SHL-003: the retired absence copy is gone from all eleven catalogues", () => {
    // The mirror of the case this replaces. It used to assert the string was
    // PRESENT everywhere; a string nothing renders is debt, and this is what
    // keeps it from creeping back.
    for (const lng of i18n.options.supportedLngs === false
      ? ["en"]
      : (i18n.options.supportedLngs as string[]).filter((code) => code !== "cimode")) {
      const key = "shell.search.unavailable";
      expect(i18n.getFixedT(lng)(key), `${lng} still carries ${key}`).toBe(key);
    }
  });

  it("US-SHL-003: all nine group headings are in all eleven catalogues", () => {
    // BR-SHL-005 as amended 2026-09-03. G15 compares the catalogues against
    // EACH OTHER, so nine keys missing from all eleven would be in perfect
    // parity and invisible to it (DEF-3061's shape) — this asks the other
    // question: does the key resolve to anything at all?
    const groups = [
      "premises",
      "units",
      "assets",
      "masterAccounts",
      "accounts",
      "customers",
      "bills",
      "payments",
      "requests",
    ];
    expect(groups).toHaveLength(9);
    for (const lng of i18n.options.supportedLngs === false
      ? ["en"]
      : (i18n.options.supportedLngs as string[]).filter((code) => code !== "cimode")) {
      for (const group of groups) {
        const key = `shell.search.group.${group}`;
        expect(i18n.getFixedT(lng)(key), `${lng} is missing ${key}`).not.toBe(key);
      }
      for (const key of [
        "shell.search.noResults",
        "shell.search.viewAll",
        "shell.search.searching",
        "shell.search.failed",
        "shell.search.retry",
      ]) {
        expect(i18n.getFixedT(lng)(key), `${lng} is missing ${key}`).not.toBe(key);
      }
    }
  });

  it.todo(
    "US-SHL-003 TC-6: a 500 from GET /search shows the A18 §4 pattern with Retry inside the popover — the popover's own states are covered in GlobalSearchResults.test.tsx; this one needs a live input plus a failing server, which is journey scope",
  );
});

describe("US-SHL-004 — notifications bell (UI shell; events land with BE-09)", () => {
  it("US-SHL-004 TC-1 (partial): 3 unread events badge '3' and list newest-first as served", () => {
    const items = [
      { id: "e3", text: "Billing run 08-A: 11 missing reads", read: false },
      { id: "e2", text: "Deposit DEP-0806 doesn't match bank · –$100.00", read: false },
      { id: "e1", text: "Payment failed · A-10432 · $148.63", read: false },
    ];
    const html = renderShell("/dashboard", { bellItems: items });
    expect(html).toContain('class="bell-badge"');
    expect(html).toContain(">3</span>");
    const first = html.indexOf("Billing run 08-A");
    const second = html.indexOf("DEP-0806");
    const third = html.indexOf("Payment failed");
    expect(first).toBeGreaterThan(-1);
    expect(first).toBeLessThan(second);
    expect(second).toBeLessThan(third);
    expect(html).toContain("Mark all read");
  });

  it("US-SHL-004 TC-4 (negative): no events — no badge, popover says \"You're all caught up.\"", () => {
    const html = renderShell("/dashboard");
    expect(html).not.toContain("bell-badge");
    expect(html).toContain("You&#x27;re all caught up.");
    expect(html).not.toContain("Mark all read");
  });

  it("US-SHL-004 (BR-SHL-007): the unread badge caps its display at 9+", () => {
    expect(BELL_BADGE_CAP).toBe(9);
    const items = Array.from({ length: 12 }, (_, i) => ({
      id: `e${i}`,
      text: `Event ${i}`,
      read: false,
    }));
    const html = renderShell("/dashboard", { bellItems: items });
    expect(html).toContain(">9+</span>");
  });

  it.todo(
    "US-SHL-004 TC-2/TC-3/TC-5: deep-link to the subject, read-state decrement, mark-all persistence and tenant isolation — BR-SHL-026 event feed + BE-09 wiring",
  );
});

describe("BR-SHL-008 — sidebar footer user block (S48 menu is US-SHL-005's packet)", () => {
  it("US-SHL-005 TC-1 (block half): renders 'AR · Alex Reed · System Admin' from the session props", () => {
    const html = renderShell("/dashboard", { user: alex, tenantName: "Silver Creek Utilities" });
    expect(html).toContain(">AR</span>");
    expect(html).toContain("Alex Reed");
    expect(html).toContain("System Admin"); // CURRENT-tenant membership role
    expect(html).toContain("Silver Creek Utilities");
    // Without session data (pre-identity wiring) the block simply absents.
    expect(renderShell("/dashboard")).not.toContain('class="foot"');
  });

  it("BR-SHL-008: initials derive from first + last name", () => {
    expect(initialsOf("Alex Reed")).toBe("AR");
    expect(initialsOf("Maria Elena Delgado")).toBe("MD");
    expect(initialsOf("Priya")).toBe("P");
    expect(initialsOf("  ")).toBe("");
  });

  it("US-SHL-005 TC-1 (DEF-038): the menu is FOUR items in the prototype's order, not one", () => {
    // 05-prototype/UtilityBilling.html:626-630 — My profile · Change password ·
    // Two-factor authentication · <hr> · Sign out. The live app showed a box
    // containing "Sign out" and nothing else (PO, 2026-08-11).
    //
    // Pinned on the CONFIG, so this assertion holds whatever the catalogs say
    // and stays green while the ten new keys are being added. The rendered
    // copy is asserted separately below.
    expect(USER_MENU_ITEMS.map((i) => i.id)).toEqual([
      "profile",
      "changePassword",
      "twoFactor",
      "signOut",
    ]);
    expect(USER_MENU_ITEMS.map((i) => i.labelKey)).toEqual([
      "shell.user.myProfile",
      "shell.user.changePassword",
      "shell.user.twoFactor",
      "shell.user.signOut",
    ]);
    // The prototype's rule sits above Sign out and nowhere else.
    expect(USER_MENU_ITEMS.filter((i) => i.separatorBefore === true).map((i) => i.id)).toEqual([
      "signOut",
    ]);
  });

  it("US-SHL-005 TC-1 (DEF-038): the open menu renders all four items, in that order, with the rule above Sign out", () => {
    const menu = renderMenu();

    // Four menu items and no more — a fifth would have to be specified.
    expect((menu.match(/role="menuitem"/g) ?? []).length).toBe(4);

    // Order read off the MARKUP, not off the config, so a render that reorders
    // them independently of USER_MENU_ITEMS still fails.
    const buttons = [...menu.matchAll(/<button[^>]*role="menuitem"[^>]*>([^<]*)</g)].map(
      (m) => m[1],
    );
    expect(buttons.length).toBe(4);
    let cursor = -1;
    for (const label of buttons) {
      const at = menu.indexOf(`>${label}<`);
      expect(at).toBeGreaterThan(cursor);
      cursor = at;
    }
    // The <hr> falls between the third item and the fourth — the prototype puts
    // Sign out alone below the rule.
    const rule = menu.indexOf("foot-menu-sep");
    expect(rule).toBeGreaterThan(menu.indexOf(`>${buttons[2]}<`));
    expect(rule).toBeLessThan(menu.indexOf("foot-menu-signout"));

    // The closed menu renders nothing at all (a popover, not a hidden div).
    expect(renderShell("/dashboard", { user: alex })).not.toContain("foot-menu");
    // …and the block that opens it is a real menu trigger.
    expect(renderShell("/dashboard", { user: alex })).toContain('aria-haspopup="menu"');
  });

  it("US-SHL-005 TC-1 / BR-SHL-025 (DEF-038): the three unbuilt items are DISABLED WITH THEIR REASON — never absent, never inert", () => {
    const menu = renderMenu();

    // Exactly three disabled, exactly one live — and the live one is Sign out.
    expect((menu.match(/disabled=""/g) ?? []).length).toBe(3);
    expect((menu.match(/aria-disabled="true"/g) ?? []).length).toBe(3);
    expect(menu).toContain("foot-menu-signout");

    // A disabled item must carry a title: a greyed-out control with no reason
    // is precisely the defect BR-SHL-025 exists to forbid.
    const titled = [...menu.matchAll(/<button[^>]*disabled=""[^>]*title="([^"]*)"[^>]*>/g)];
    expect(titled.length).toBe(3);
    for (const [, reason] of titled) {
      expect(reason.length).toBeGreaterThan(0);
    }
    // Two DIFFERENT reasons are given, not one blanket "coming soon": the
    // profile/password modals wait on a screen (their endpoints are served),
    // two-factor waits on the feature itself (BR-IDN-028).
    expect(new Set(titled.map(([, reason]) => reason)).size).toBeGreaterThan(1);

    // Sign out is NOT disabled — the one item that works must work.
    const signOut = menu.slice(menu.indexOf("<button", menu.indexOf("foot-menu-sep")));
    expect(signOut.slice(0, signOut.indexOf(">"))).not.toContain("disabled");
  });

  it("US-SHL-005 TC-1 (DEF-038, i18n): the menu's rendered COPY is the prototype's, and the header reads 'email · role'", () => {
    // ⚠ EXPECTED RED until the ten `shell.user.*` / `shell.tenant.*` keys land
    // in the five catalogs (this lane may not edit i18n/locales/*.json — the
    // keys are listed in the packet report). i18next renders the KEY when a key
    // is missing, so this test names the missing copy precisely rather than the
    // packet quietly shipping key-strings to users.
    const menu = renderMenu();
    expect(menu).toContain("My profile");
    expect(menu).toContain("Change password");
    expect(menu).toContain("Two-factor authentication");
    expect(menu).toContain("Sign out");
    // The prototype's identity header: name on one line, "email · role" below.
    expect(menu).toContain("Alex Reed");
    expect(menu).toContain("alex.reed@silvercreekutilities.com · System Admin");
    // No key-strings leaked to the user anywhere in the popover.
    expect(menu).not.toContain("shell.user.");
  });

  it("BR-SHL-008: the tenant block draws the utility's NAME (DEF-2887 removed its second line)", () => {
    // ⚠ **THIS TEST ONCE ASSERTED THE OPPOSITE, AND THAT IS THE POINT.**
    // DEF-040 (2026-08-11) added a second line because r9 drew one — *"1,247
    // connections · Growth"* — and the figures were fixture data nobody
    // served, so the line stated the ABSENCE instead: *"Connections and plan
    // not shown yet"*. Correct at the time, and law 1's own shape.
    //
    // DEF-2887 (PO, 2026-08-31, from the deployed product) is what that cost.
    // A sentence in an identity slot is read as identity, on every screen of
    // the product, and by then the absence was also STALE: Settings → Billing
    // plan ships and shows the subscription. The sentence moved to that tab,
    // where the figures are; the slot keeps the name.
    const html = renderShell("/dashboard", { tenantName: "Silver Creek Water" });
    const block = html.slice(html.indexOf('class="tenant"'), html.indexOf("<nav"));
    expect(block).toContain('class="tn">Silver Creek Water<');
    expect(block).not.toContain("tenant-sub");
  });

  it("CR-048 wave D: the tenant block draws the utility's own mark beside its name", () => {
    // Hard-won law 2 has been paid FOUR times in this one file (the user block,
    // sign-out, the tenant name, the bell), so `tenantMark` gets the assertion
    // that a prop nothing passes would fail: the shell renders what it is
    // given, and ShellWithSession.test.tsx asserts that it IS given.
    const html = renderShell("/dashboard", {
      tenantName: "Silver Creek Water",
      tenantMark: <span data-mark="SC">SC</span>,
    });
    const block = html.slice(html.indexOf('class="tenant"'), html.indexOf("<nav"));
    expect(block).toContain('data-mark="SC"');
    // …and it sits BEFORE the name, where a logo sits on a letterhead.
    expect(block.indexOf('data-mark="SC"')).toBeLessThan(block.indexOf("Silver Creek Water"));
    // Absent when nothing passes one — the shell invents no mark of its own.
    const bare = renderShell("/dashboard", { tenantName: "Silver Creek Water" });
    expect(bare).not.toContain("data-mark");
  });

  it("BR-SHL-008 (DEF-040): the tenant block invents NO figure and offers NO tenant switcher", () => {
    const html = renderShell("/dashboard", { tenantName: "Silver Creek Water" });
    const block = html.slice(html.indexOf('class="tenant"'), html.indexOf("<nav"));
    // The prototype's fixture numbers must never reach a user as if measured.
    expect(block).not.toContain("1,247");
    expect(block).not.toContain("Growth");
    expect(block).not.toMatch(/\d[\d,]{2,}/); // no digit-group of any kind
    // No chevron: nothing switches tenants, and under path tenancy the tenant
    // is the URL. A disclosure control that discloses nothing is a promise.
    expect(block).not.toContain("<svg");
    expect(block).not.toContain("<button");
  });

  it("DEF-2887: the identity slot is the utility's NAME and nothing else", () => {
    // ⚠ **THIS TEST REPLACES ITS OWN OPPOSITE.** It used to assert that a
    // second line said what was missing and why — `shell.tenant.
    // metricsUnavailable`, *"Connections and plan not shown yet"*, which the
    // PO then read on every screen of the deployed product as part of the
    // utility's identity (2026-08-31).
    //
    // The sentence is not lost, it MOVED: Settings → Billing plan now ships
    // (`SettingsBillingPlanTab.tsx`) and states the one still-unserved figure
    // at `settings.billingPlan.plan.connectionsUnavailable`, where a person
    // goes looking for it. Hard-won law 1 asks that an absence be SAID, not
    // that it be said everywhere.
    //
    // So the assertion is now a fence: the block holds the name and nothing
    // that reads as a sentence about it. A lane restoring the sub-line, or
    // adding any other second line to the identity slot, goes red here.
    const html = renderShell("/dashboard", { tenantName: "Silver Creek Water" });
    const block = html.slice(html.indexOf('class="tenant"'), html.indexOf("<nav"));
    expect(block).toContain("Silver Creek Water");
    expect(block).not.toContain("shell.tenant."); // i18next echoes a missing key
    expect(block).not.toContain("tenant-sub");
    // Both catalogue entries are gone with their only call site, so a
    // reinstated sub-line cannot quietly find its copy again either.
    expect(block).not.toContain("Connections and plan");
  });

  it.todo(
    "US-SHL-005 TC-2/TC-3/TC-4/TC-6: the My profile / Change password / Two-factor MODALS and their field-level behaviour — the open remainder of US-SHL-005. `PATCH /me` and `POST /me/password` are already SERVED with no typed wrapper and no caller (law 2, reported 2026-08-11); Two-factor has no endpoint at all (BR-IDN-028)",
  );
});

// ── The product version on screen (change process §7) ──────────────────────
// 12-governance/13-change-process.md §7 rule 2: "VISIBLE IN THE RUNNING APP. If
// a user cannot read the version on screen, a defect report cannot name it, and
// 'is it fixed?' becomes unanswerable."
//
// These assertions are written against `pkg.version` and NEVER against a
// literal like "2.4.0". That is the whole point of rule 1 ("ONE SOURCE OF
// TRUTH, derived everywhere else"): a test carrying its own copy of the number
// is a third copy, it goes red on every legitimate bump, and someone edits the
// literal instead of asking why. Here the manifest is the oracle, so the only
// way to make these red is to stop rendering the version at all — which is the
// failure they exist to catch.
describe("change process §7 — the product version is visible in the running app", () => {
  it("the sidebar renders the version from package.json, and does not hard-code it", () => {
    const html = renderShell("/dashboard", { user: alex });
    expect(html).toContain(`>v${pkg.version}<`);
    // Not "a version somewhere" — the exact string the manifest holds.
    expect(pkg.version).toMatch(/^\d+\.\d+\.\d+$/); // <release>.<change>.<fix>
    expect(pkg.version).not.toBe("0.0.1"); // the state §7 was written about
  });

  it("the version renders on a frame with NO user block", () => {
    // The user block is optional; the version must not be. A signed-out or
    // half-loaded frame is exactly the screenshot a defect report carries.
    const html = renderShell("/dashboard");
    expect(html).not.toContain('class="foot-wrap"');
    expect(html).toContain(`>v${pkg.version}<`);
  });

  it("the version is in the SIDEBAR, above the user block, and carries a test hook", () => {
    const html = renderShell("/dashboard", { user: alex });
    const aside = html.slice(html.indexOf("<aside"), html.indexOf("</aside>"));
    expect(aside).toContain('data-testid="app-version"');
    // Order matters to the layout: `.sidebar-version` holds the column's only
    // `margin-top: auto`, so it must precede `.foot-wrap` (see AppShell.css).
    expect(aside.indexOf('class="sidebar-version"')).toBeLessThan(
      aside.indexOf('class="foot-wrap"'),
    );
  });

  it("the version is not a translation key — it reads the same in every locale", () => {
    const html = renderShell("/dashboard", { user: alex });
    // The element first — a bare `not.toContain` passes trivially on a frame
    // that renders no version at all, which is the failure this file exists to
    // catch. Proved RED 2026-08-17: without this line the assertion stayed
    // GREEN while the other three went red on the deleted element.
    expect(html).toContain('class="sidebar-version"');
    // i18next echoes a missing key, so a key here would ship literal
    // `shell.version` to a user. There is no key: the number is the copy.
    expect(html).not.toContain("shell.version");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-SHL-7825` · THE HELP CONTROL'S HOLD, AND THE TEST THAT FIRES WHEN IT
// EXPIRES — CLAUDE.md hard-won law 2's mirror
// ══════════════════════════════════════════════════════════════════════════
//
// **WHAT WAS ON SCREEN.** The `?` in the top bar of all 114 screens was a live
// link to `https://code.claude.com/docs` — the documentation for the tool this
// product is built WITH. A clerk who pressed it left SMARTBillHub and landed on
// a page about writing code. Measured in a browser on 2026-09-28, from the New
// connects list, during the New Connect walk.
//
// ⚠ **NOTHING COULD HAVE CAUGHT IT AND THAT IS THE POINT.** No gate reads a
// rendered `href`, and nothing asks whether an external host belongs to this
// product. Both places a reader would check DESCRIBED A DIFFERENT DESTINATION:
// the constant's own docstring said *"the product's own documentation route"*
// and `OQ-307`'s register row said *"a page written for engineers"*. Hard-won
// law 1 — a comment claiming a guarantee is not the guarantee — and law 6: the
// browser found it and nothing else could.
//
// ⚠ **WHY THIS IS A HOLD AND NOT A DESTINATION.** `OQ-307` asks where the
// control should point and is OPEN. Answering it here by picking a URL is the
// thing the prime directive forbids, so the control takes `BR-SHL-025`'s ruled
// shape instead — disabled, with its reason on the control, never hidden.
//
// ⚠ **A FAILURE HERE IS GOOD NEWS.** It means `OQ-307` was answered and a
// destination arrived. The fix is never to loosen these assertions: it is to
// make the control a link again and delete this block.
describe("DEF-SHL-7825 · the help control's hold", () => {
  it("has no destination at all — the day it does, this goes red", () => {
    // ⚠ THE WHOLE HOLD IN ONE LINE. `HELP_ROUTE` is exported for this and for
    // nothing else. When `OQ-307` is answered somebody sets it, and the message
    // below is the instruction they need at the moment they need it.
    expect(
      HELP_ROUTE,
      `\`HELP_ROUTE\` now holds a destination, so the help control must stop
refusing: render it as an <a href={HELP_ROUTE}> again, drop
\`shell.help.unavailable\` from the eleven catalogues, and delete this describe
block. Landing the help centre and releasing the control that pointed at it are
two acts, and this is the one that does not feel like work (DEF-CWP-3925).`,
    ).toBeNull();
  });

  it("refuses by name rather than doing nothing, and says so where it can be read", () => {
    const html = renderShell("/dashboard", { user: alex });
    // The ELEMENT first. A bare `not.toContain` passes trivially on a frame
    // that renders no help control at all, which is the wrong fix and the one
    // this case exists to refuse — BR-SHL-008 already ruled that an absent
    // control teaches a user the feature does not exist.
    expect(html).toContain("shell-help");
    expect(html).toContain("data-help-unavailable");
    expect(html).toContain('aria-disabled="true"');
    // `RowAction`'s shape, copied rather than re-invented: the accessible name
    // is the LABEL and the `title` carries the REASON. Both are asserted, so
    // dropping either is red — a disabled glyph with no reason is the thing
    // BR-SHL-025 exists to forbid, and one with no name is rule 15's.
    expect(html).toContain(`aria-label="${i18n.t("shell.help.label")}"`);
    expect(html).toContain(`title="${i18n.t("shell.help.unavailable")}"`);
    // And they are real copy from the catalogues, not echoed keys.
    expect(i18n.t("shell.help.unavailable")).not.toBe("shell.help.unavailable");
    expect(i18n.t("shell.help.label")).not.toBe("shell.help.label");
  });

  it("points at no external host from the shell frame", () => {
    const html = renderShell("/dashboard", { user: alex });
    // ⚠ THE GENERAL FORM OF THE DEFECT, not the one URL. Asserting the absence
    // of `code.claude.com` alone would pass the day somebody pointed the `?` at
    // a different company's site, which is the same bug wearing a new hostname.
    expect(html).not.toContain("code.claude.com");
    const externalHrefs = [...html.matchAll(/href="(https?:\/\/[^"]+)"/g)].map((m) => m[1]);
    expect(externalHrefs).toEqual([]);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-001@b16a4de (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 94/94✔ (12 todo this packet — browser/server/consumer scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔ · 2026-08-11 S48 user-menu re-run: tsc✔ eslint✔
// exceptions: E1 [2026-08-11] the two `(…, i18n)` tests are EXPECTED RED in this packet: they assert the menu's and the tenant block's rendered COPY, and the ten new `shell.user.*` / `shell.tenant.*` keys are added by the i18n lane, which owns locales/*.json. They are written now, and left failing on purpose, so the keys cannot be forgotten and so key-strings can never be shipped to a user unnoticed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
