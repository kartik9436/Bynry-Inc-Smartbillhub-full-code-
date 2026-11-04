// ── Trace ──────────────────────────────────────────────
// Story:    US-AUD-004 (S61 viewer — filters, table, roles) · US-AUD-005 (detail drawer) ·
//           US-AUD-006 (CSV export under the BR-SHL-016 guards)   Screens: S61
// Rules:    BR-AUD-002 (read-only by construction) · BR-AUD-006 (masked values as stored) ·
//           BR-AUD-007 (tenant-scoped only) · BR-AUD-009 (roles, filter vocabulary, six columns) ·
//           BR-AUD-013 (server pagination · hot window · EXPLICIT archive) ·
//           BR-AUD-014 (50k export cap → 422 BIZ-CAP) · BR-SHL-011 (URL grammar) ·
//           BR-SHL-033 (date pickers, searchable long lists) · BR-SHL-034 (the shared formatter)
// ───────────────────────────────────────────────────────
// §4 test data is Brazos Bend Utility District No. 1, America/Chicago, with the
// A1 fixture actors (Alex Reed — System Admin, Evan Ruiz — Executive).
//
// The load-bearing test here is TC-7: a DOM scan for any mutating affordance on
// S61. If a future edit ever adds one, that test fails — which is the only way
// "read-only by construction" stays true after the packet that wrote it.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError, createApiClient } from "@/api/client";
import {
  AUDIT_FILTERS,
  AUDIT_SORTS,
  AUDIT_WINDOW_FROM_HEADER,
  AUDIT_WINDOW_HEADER,
  auditWindowOf,
  getAuditLog,
  requestAuditExport,
} from "@/api/endpoints";
import type { AuditEntry, AuditListResult, AuditRow, Paginated, TenantUser } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { DEFAULT_PAGE_SIZE, parseTableParams, serializeTableParams } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";
import { isPermissionDenied } from "@/features/tenancy/settingsShared";

import { exportDownloadHref } from "@/features/exports/ListExportButton";

import {
  AUDIT_ROUTE,
  AuditLogPage,
  ENTRY_PARAM,
  ExportReadyLine,
  actorLabel,
  archiveFromParams,
  auditParamsFrom,
  auditTableConfig,
  buildActorOptions,
  entityLabel,
  exportCapRefusal,
  windowBannerKey,
} from "./AuditLogPage";

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…` and
// every tenant-scoped call goes to `/api/{tenant}/…`. Tests state the tenant
// the browser would be showing, so both are visible here rather than implied.
const TEST_TENANT = "brazosbend";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const ALEX = { id: "u-alex", name: "Alex Reed" };

// The J6 fixture chain, as `GET /audit-log` serves it.
const ROWS: AuditRow[] = [
  {
    id: "a1",
    created_at: "2026-08-09T15:42:00Z",
    actor: ALEX,
    action: "billing_settings.updated",
    entity_type: "tenant_settings",
    entity_id: "11111111-1111-1111-1111-111111111111",
    summary: "late_grace_days: 10 → 15",
    source: null, // GAP AUD-D2
  },
  {
    id: "a2",
    created_at: "2026-08-09T14:05:00Z",
    actor: null, // BR-AUD-003: a system job
    action: "period.closed",
    entity_type: "accounting_period",
    entity_id: null,
    summary: "status: open → closed",
    source: null,
  },
];

const DRAWER: AuditEntry = {
  ...ROWS[0],
  before: { late_grace_days: 10 },
  after: { late_grace_days: 15 },
  request_metadata: null, // GAP AUD-D2 — present in the contract, empty today
};

function page(rows: AuditRow[], count = rows.length): Paginated<AuditRow> {
  return { count, next: null, previous: null, results: rows };
}

function result(
  rows: AuditRow[],
  window: "hot" | "archive" = "hot",
  from = "2024-08-10T00:00:00+00:00",
  count = rows.length,
): AuditListResult {
  return { page: page(rows, count), window: { window, from } };
}

const CONFIG = auditTableConfig(t, [], {
  when: () => <span />,
  entity: () => <span />,
  actor: () => "",
  source: () => <span />,
  // DEF-645: the Action and Summary cells are components now — this fixture
  // only needs the config's SHAPE (it is parsing URL params), so both are
  // stubbed like the other four.
  action: () => <span />,
  summary: () => <span />,
});

/**
 * Renders S61 with its list answer (and optionally its drawer answer) already
 * in the cache. No network, ever — the client seam exists so a screen can be
 * proved without one.
 */
function renderAudit(
  path: string,
  seed: { list?: AuditListResult; entry?: AuditEntry; users?: TenantUser[] } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const params = new URLSearchParams(path.split("?")[1] ?? "");
  const state = parseTableParams(params, CONFIG);
  const archive = archiveFromParams(params);
  if (seed.list !== undefined) {
    queryClient.setQueryData(
      queryKeys.auditLog(serializeTableParams(state, CONFIG).toString() + `|${archive}`),
      seed.list,
    );
  }
  if (seed.entry !== undefined) {
    queryClient.setQueryData(queryKeys.auditEntry(seed.entry.id), seed.entry);
  }
  if (seed.users !== undefined) {
    queryClient.setQueryData(queryKeys.tenantUsers(1, DEFAULT_PAGE_SIZE), {
      count: seed.users.length,
      next: null,
      previous: null,
      results: seed.users,
    });
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <AuditLogPage timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-AUD-004 — the S61 list: filters, columns, window", () => {
  it("US-AUD-004 TC-1: newest-first rows in the six default columns, tenant-TZ timestamps", () => {
    const html = renderAudit(AUDIT_ROUTE, { list: result(ROWS) });
    for (const label of ["When", "Actor", "Action", "Entity", "Summary", "Source"]) {
      expect(html).toContain(`>${label}<`);
    }
    // DEF-645 (2026-08-24): this case USED to assert the raw action code and
    // the server's `key: value` blob — the two halves of what the PO
    // photographed. Six columns, same six columns; what changed is that the
    // Action cell is now the event as a sentence and the Summary cell is a
    // "What changed" disclosure holding the WHOLE field set, not the server's
    // first three with "(+N more)" after them.
    expect(html).toContain("Billing settings updated");
    expect(html).not.toContain("late_grace_days: 10 → 15");
    expect(html).toContain("What changed");
    // Still one grep away for support, in the DOM and not in the text.
    expect(html).toContain('data-audit-action="billing_settings.updated"');
    expect(html).toContain("Alex Reed");
    // BR-SHL-034: the instant went through DateCell, into America/Chicago —
    // 15:42Z is 10:42 CDT, which is exactly the A1 fixture's own wording.
    expect(html).toContain('dateTime="2026-08-09T15:42:00Z"');
    expect(html).toContain("08/09/2026 10:42");
    // The capability row: newest first, and When is the identity column.
    expect(CONFIG.defaultSort).toEqual({ sort: "when", dir: "desc" });
    expect(CONFIG.columns.find((c) => c.identity === true)?.key).toBe("when");
    // A1 S61: no free-text search on this screen — the entity filter is the
    // lookup path, so the capability row declares no search fields.
    expect(CONFIG.searchFields).toBeUndefined();
    expect(html).not.toContain("table-search");
  });

  it("BR-AUD-003: a null actor is named as a system job, never left blank", () => {
    expect(actorLabel(ROWS[1], t)).toBe("System job");
    expect(actorLabel(ROWS[0], t)).toBe("Alex Reed");
    // A removed actor keeps its history — IN WORDS. This asserted
    // `toBe("User u-ghost")` until DEF-2378: `audit.actor.unknownId` read
    // "User {{id}}", so a deleted user's row printed a whole database uuid as
    // the visible value of the Actor cell. B14 rule 31 has no exception for
    // "the name is gone", and the history is kept either way.
    const ghost = { ...ROWS[0], actor: { id: "u-ghost", name: null } };
    expect(actorLabel(ghost, t)).toBe("User no longer listed");
    expect(actorLabel(ghost, t)).not.toContain("u-ghost");
    const html = renderAudit(AUDIT_ROUTE, { list: result(ROWS) });
    expect(html).toContain("System job");
  });

  it("US-AUD-004 TC-2/TC-3 / BR-SHL-011: every declared filter round-trips through the URL", () => {
    // The vocabulary is the SERVER's (BR-AUD-009), in the shared `f.<name>`
    // grammar — parsed and serialized by the ONE table framework.
    expect(CONFIG.filters?.map((f) => f.name)).toEqual([...AUDIT_FILTERS]);
    const url = new URLSearchParams(
      "sort=when&dir=desc&f.action=invoice.issued&f.entity_type=invoice&f.from=2026-08-01&f.to=2026-08-09",
    );
    const state = parseTableParams(url, CONFIG);
    expect(state.filters).toEqual({
      action: "invoice.issued",
      entity_type: "invoice",
      from: "2026-08-01",
      to: "2026-08-09",
    });
    // …and back out again, so a filtered view is shareable.
    const back = serializeTableParams(state, CONFIG);
    expect(back.get("f.action")).toBe("invoice.issued");
    expect(back.get("f.from")).toBe("2026-08-01");

    // The wrapper turns that state into the request the server reads.
    const params = auditParamsFrom(state, false);
    expect(params.filters.action).toBe("invoice.issued");
    expect(params.archive).toBe(false);
    // An unknown `f.<name>` is ignored rather than sent (US-SHL-007 TC-5).
    expect(parseTableParams(new URLSearchParams("f.nonsense=1"), CONFIG).filters).toEqual({});
  });

  it("US-AUD-004 TC-6 / BR-SHL-011: a hand-edited impossible range does not error the screen", () => {
    // From > To is a real possibility in a pasted URL. It parses, the request
    // goes, and the SERVER falls back to the window floor — no client-side
    // validation gate stands between the user and an honest empty result.
    const state = parseTableParams(
      new URLSearchParams("f.from=2026-08-09&f.to=2026-08-01"),
      CONFIG,
    );
    expect(state.filters.from).toBe("2026-08-09");
    const html = renderAudit(`${AUDIT_ROUTE}?f.from=2026-08-09&f.to=2026-08-01`, {
      list: result([], "hot", "2024-08-10T00:00:00+00:00", 0),
    });
    expect(html).not.toContain("state-failed");
  });

  it("BR-SHL-033: dates are PICKERS and the actor list is SEARCHABLE when it can be read", () => {
    const users: TenantUser[] = [
      {
        id: "u-alex",
        name: "Alex Reed",
        email: "alex@brazosbend.example",
        role: "system_admin",
        role_name: "System Admin",
        last_active_at: null,
        status: "active",
      },
    ];
    const html = renderAudit(AUDIT_ROUTE, { list: result(ROWS), users });
    expect(html).toContain('type="date"'); // from + to
    expect(html).toContain('role="combobox"'); // the type-ahead actor picker
    expect(buildActorOptions(users, t)).toEqual([
      { value: "system", label: "System job" }, // BR-AUD-003 is selectable
      // ⚠ ADDED 2026-09-06 (US-AUD-010). `f.actor=automation` narrows to every
      // NAMED non-person actor, and a server filter no control can select is a
      // feature that does not exist (hard-won law 2). Asserted in the OPTION
      // LIST rather than only in the label function, because the list is what
      // actually reaches the picker. `system` above now means the UNNAMED half
      // only — before this story one value answered both questions badly.
      { value: "automation", label: "Automations" }, // BR-AUD-019
      { value: "u-alex", label: "Alex Reed · alex@brazosbend.example" },
    ]);

    // `GET /users` is System-Admin-only. An Executive may read S61 but not the
    // user list, so the filter degrades to an id field — with the reason.
    const noList = renderAudit(AUDIT_ROUTE, { list: result(ROWS) });
    expect(noList).toContain("Your role can&#x27;t list users");
    expect(noList).not.toContain('role="combobox"');
  });

  it("BR-AUD-013: the banner states WHICH window answered, and the archive is an explicit toggle", () => {
    const hot = renderAudit(AUDIT_ROUTE, { list: result(ROWS) });
    expect(hot).toContain("Showing the last 2 years");
    expect(hot).toContain("View archive");
    // The floor is an instant, so it renders through the shared formatter too.
    expect(hot).toContain("08/09/2024");

    const archived = renderAudit(`${AUDIT_ROUTE}?archive=true`, {
      list: result(ROWS, "archive", "2019-08-11T00:00:00+00:00"),
    });
    expect(archived).toContain("Showing the full 7-year archive");
    expect(archived).toContain("Back to the last 2 years");

    // The window comes from the HEADER, never from a guess about the params.
    expect(windowBannerKey({ window: "hot", from: null })).toBe("audit.window.hot");
    expect(windowBannerKey({ window: "archive", from: null })).toBe("audit.window.archive");
  });

  it("BR-AUD-013: only an explicit truthy token opens the archive — a typo never widens it", () => {
    expect(archiveFromParams(new URLSearchParams(""))).toBe(false);
    expect(archiveFromParams(new URLSearchParams("archive=false"))).toBe(false);
    expect(archiveFromParams(new URLSearchParams("archive=maybe"))).toBe(false);
    for (const token of ["1", "true", "TRUE", "yes", "on"]) {
      expect(archiveFromParams(new URLSearchParams(`archive=${token}`))).toBe(true);
    }
    // And the request only carries the param when it was asked for.
    expect(auditParamsFrom(parseTableParams(new URLSearchParams(""), CONFIG), false).archive).toBe(
      false,
    );
  });

  it("the window headers are read off the response, and default honestly when absent", async () => {
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(JSON.stringify(page(ROWS)), {
          status: 200,
          headers: {
            "Content-Type": "application/json",
            [AUDIT_WINDOW_HEADER]: "archive",
            [AUDIT_WINDOW_FROM_HEADER]: "2019-08-11T00:00:00+00:00",
          },
        }),
    });
    const answer = await getAuditLog({}, client);
    expect(answer.window).toEqual({ window: "archive", from: "2019-08-11T00:00:00+00:00" });
    expect(answer.page.results).toHaveLength(2);

    // A response with no headers at all reads as the hot window with no floor —
    // never an invented date.
    expect(auditWindowOf({ status: 200, data: null, etag: null, notModified: false })).toEqual({
      window: "hot",
      from: null,
    });
  });

  it("US-AUD-004 TC-5: a role the server refuses is a permission STATE, not an error state", () => {
    // A 403 on the list read renders A18 §6 INSTEAD of the screen — the
    // component takes no children, so no rows can render behind it. The
    // classifier is the shared one, so S61 cannot disagree with any other
    // screen about what "denied" looks like.
    expect(isPermissionDenied(new ApiError(403, { code: "AUTH-002", message_key: "errors.auth-002" }))).toBe(true);
    // DEF-SHL-6378 — and a 401 is NOT a denial. This case asserted that it
    // was until 2026-09-23, which is how an expired session told a System
    // Admin their role could not open Payments: the defect was the tested
    // behaviour. A 401 is the shell's to answer (Session expired).
    expect(isPermissionDenied(new ApiError(401, { code: "AUTH-001", message_key: "errors.auth-001" }))).toBe(false);
    expect(isPermissionDenied(new ApiError(500, { code: "SYS-001", message_key: "errors.sys-internal" }))).toBe(
      false,
    );
    // …and the copy names the two roles BR-AUD-009 admits, not a role guess.
    expect(t("audit.denied")).toContain("System Admins and Executives");
  });

  it("US-AUD-004 TC-7: no mutating affordance exists anywhere on this screen", () => {
    const html = renderAudit(AUDIT_ROUTE, { list: result(ROWS) }).toLowerCase();
    // Not disabled — ABSENT. The store is append-only and the API defines no
    // such verb, so no permission could ever unlock one.
    for (const forbidden of [">edit<", ">delete<", ">annotate<", ">redact<", ">save<", ">void<"]) {
      expect(html).not.toContain(forbidden);
    }
    expect(html).not.toContain("<form");
    // The only row affordance is opening the read-only drawer.
    expect(html).toContain('data-audit="open"');
  });

  it("GAP AUD-D2: the Source column is PRESENT and empty, never hidden", () => {
    const html = renderAudit(AUDIT_ROUTE, { list: result(ROWS) });
    expect(html).toContain(">Source<");
    expect(html).toContain("Not recorded");
    expect(html).toContain('data-audit="empty"');
  });

  it("IS-2: the sortable set is the server's own", () => {
    const sortable = CONFIG.columns.filter((c) => c.sortable === true).map((c) => c.key);
    expect(sortable).toEqual([...AUDIT_SORTS]);
  });

  it.todo(
    "US-AUD-004 TC-8 (isolation): a forged cross-tenant entity id returns zero rows under RLS — server scope (G5)",
  );
  it.todo(
    "browser scope → Playwright: clicking a column header pushes ?sort/&dir and the pager keeps the filter state",
  );
});

describe("US-AUD-005 — the detail drawer", () => {
  it("US-AUD-005 TC-1: the drawer shows who/what/when/entity and the before → after diff", () => {
    const html = renderAudit(AUDIT_ROUTE, { list: result(ROWS), entry: DRAWER });
    // The drawer opens on a row click, so the affordance is what renders here…
    expect(html).toContain('data-audit="open"');
    expect(html).toContain("Open details for billing_settings.updated");
  });

  it("US-AUD-005 TC-1: the drawer says what changed, in words, 10 → 15", () => {
    // Rendered directly, because opening the drawer is a click (browser scope):
    // this asserts the CONTENT law, which is the part that must not drift.
    //
    // AMENDED 2026-08-24 (DEF-645). TC-1's law — "who/what/when/entity and the
    // before → after diff, only the field that changed" — is unchanged and is
    // asserted here in the form a person reads. What moved is the RAW JSON: it
    // is still in the drawer, still exactly as stored, now behind the "Stored
    // record" disclosure, because it is storage keys and it was the first thing
    // the reader met.
    const drawer = renderDrawerBody(DRAWER);
    expect(drawer).toContain("What changed");
    expect(drawer).toContain("Late grace days"); // the column, said in words
    expect(drawer).toContain("10");
    expect(drawer).toContain("15");
    expect(drawer).toContain("Alex Reed");
    expect(drawer).toContain("Billing settings updated");
    // The COLUMN name is gone from the words a person reads. It stays on
    // `data-audit-field` for support, the way the action code does.
    expect(drawer.replace(/<[^>]*>/g, " ")).not.toContain("late_grace_days");
    expect(drawer).toContain('data-audit-field="late_grace_days"');
    // The stored record is REACHABLE, not gone — Disclosure unmounts a closed
    // body, so what a static render can prove is the control and its label.
    expect(drawer).toContain("Stored record");
    expect(drawer).toContain("exactly as it was saved, technical");
  });

  it("US-AUD-005 §5: `source` and `request_metadata` are null today and render present-but-empty", () => {
    const drawer = renderDrawerBody(DRAWER);
    // Both fields are in the contract. Hiding them would hide the gap.
    expect(drawer).toContain("Source");
    expect(drawer).toContain("Request details");
    expect(drawer).toContain("Not recorded"); // source
    expect(drawer).toContain("Nothing recorded"); // request_metadata
  });

  it("BR-AUD-006: a masked value renders masked — there is no unmask path", () => {
    const masked: AuditEntry = {
      ...DRAWER,
      action: "account.updated",
      before: { date_of_birth: "06/****" },
      after: { date_of_birth: "11/****" },
      summary: "date_of_birth: 06/**** → 11/****",
    };
    const drawer = renderDrawerBody(masked);
    expect(drawer).toContain("06/****");
    expect(drawer).toContain("11/****");
    expect(drawer).toContain("Values appear exactly as they were stored");
  });

  it("US-AUD-005 TC-6: an entity with no reachable screen degrades to a LABEL — history never 404s", () => {
    // ⚠ THIS ASSERTED THE DEFECT UNTIL DEF-2378. It read
    //     expect(entityLabel(ROWS[0])).toBe(
    //       "tenant_settings · 11111111-1111-1111-1111-111111111111")
    // — a whole database uuid, PINNED as the Entity column's required value,
    // which is how the breach survived a green suite for three weeks and was
    // found by the Product Owner on a live deployment instead. Rule 31: the
    // cell says WHAT THE RECORD IS.
    expect(entityLabel(ROWS[0], t)).toBe("Settings");
    expect(entityLabel(ROWS[0], t)).not.toContain("11111111");
    // An entity type nobody has written a word for is still humanised, never
    // printed raw and never invented into a different noun.
    expect(entityLabel({ ...ROWS[0], entity_type: "wizard_park" }, t)).toBe("Park");
    expect(entityLabel({ ...ROWS[0], entity_type: "read_window" }, t)).toBe("Read window");
    // An export row covers a filtered SET, so it carries no entity id at all.
    expect(entityLabel(ROWS[1], t)).toBe("Accounting period");
    const html = renderAudit(AUDIT_ROUTE, { list: result(ROWS) });
    expect(html).toContain('data-audit="entity"');
    // No <a> is built for an entity: this app has no detail route to point at,
    // and a dead link is worse than an honest label.
    expect(html).not.toContain("<a ");
  });

  it("B14 rule 31 (DEF-2378): no uuid is READABLE anywhere on the list, and support still has it", () => {
    const html = renderAudit(AUDIT_ROUTE, { list: result(ROWS) });
    // The whole rendered list, with every tag stripped: what a person actually
    // reads. A uuid must not be in it. This is the assertion that would have
    // caught the defect the Product Owner reported, and it is deliberately
    // about TEXT rather than about one expression — G69 clause 2 guards the
    // expression, and the two together are what rule 31 asks for.
    const readable = html.replace(/<[^>]*>/g, " ");
    expect(readable).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
    // …and it is still reachable for a support call: on `title` for a person,
    // on a data attribute for a tool. Same posture as `data-br-ref` (DEF-322).
    expect(html).toContain('data-audit-entity-id="11111111-1111-1111-1111-111111111111"');
    expect(html).toContain('title="11111111-1111-1111-1111-111111111111"');
  });

  it("US-AUD-005 TC-7: the drawer exposes no write of any kind", () => {
    const drawer = renderDrawerBody(DRAWER).toLowerCase();
    // Two buttons exist and both only CLOSE the dialog — nothing edits,
    // annotates or redacts, because the store has no such path (BR-AUD-010).
    expect(drawer).not.toContain("<input");
    expect(drawer).not.toContain("<form");
    expect(drawer).not.toContain("<textarea");
    for (const forbidden of [">edit<", ">delete<", ">annotate<", ">redact<", ">save<"]) {
      expect(drawer).not.toContain(forbidden);
    }
    const buttons = drawer.match(/<button/g) ?? [];
    // The ✕, the Close in the footer, and — since DEF-645 — the "Stored record"
    // disclosure. A disclosure toggle SHOWS; it writes nothing, which is why
    // the forbidden-verb list above is the assertion that matters and this
    // count is only the guard against a fourth, mutating control appearing.
    expect(buttons).toHaveLength(3);
  });

  it.todo(
    "US-AUD-005 TC-2: the related approval reference links from the payload — no ratified key name exists for it in the drawer contract yet (reported)",
  );
  it.todo(
    "US-AUD-005 TC-3/TC-4: a per-entity Audit tab equals S61 filtered to that entity — the owning modules' tabs (S21/S50) are not built",
  );
  it.todo("US-AUD-005 TC-8 (isolation): the entity service is tenant-scoped first — server scope (G5)");
});

describe("US-AUD-006 — the CSV export", () => {
  it("US-AUD-006 TC-1: the export posts the CURRENT filters and gets a 202 + job id back", async () => {
    let sent: unknown = null;
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async (_input, init) => {
        sent = JSON.parse(String(init?.body));
        return new Response(JSON.stringify({ job_id: "job-77" }), {
          status: 202,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    const state = parseTableParams(
      new URLSearchParams("f.action=invoice.issued&f.from=2026-08-01"),
      CONFIG,
    );
    const accepted = await requestAuditExport(auditParamsFrom(state, false), client);
    expect(accepted.job_id).toBe("job-77");
    // IS-9: the caller's filters ride with the request, and only the set ones.
    expect(sent).toEqual({
      filters: { action: "invoice.issued", from: "2026-08-01" },
      archive: false,
    });
  });

  it("the 202 is POLLED through the client's own job helper to a terminal state", async () => {
    let polls = 0;
    const client = createApiClient({
      tenant: TEST_TENANT,
      sleep: async () => undefined,
      fetchImpl: async (input) => {
        const url = String(input);
        if (url.startsWith("/audit-log/export")) {
          return new Response(JSON.stringify({ job_id: "job-77" }), {
            status: 202,
            headers: { "Content-Type": "application/json" },
          });
        }
        polls += 1;
        return new Response(
          JSON.stringify({
            id: "job-77",
            kind: "audit_export",
            status: polls < 2 ? "running" : "succeeded",
            progress: null,
            result_link: polls < 2 ? null : "/exports/job-77/file",
            error: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      },
    });
    const accepted = await requestAuditExport({}, client);
    const job = await client.pollJob(accepted.job_id, { intervalMs: 0 });
    expect(job.status).toBe("succeeded");
    expect(polls).toBe(2); // it kept polling until the job was terminal
    // US-AUD-006 / IS-11: the terminal job carries the shared DOWNLOAD ROUTE,
    // read through the ONE helper the nine list exports use (LAW 0).
    expect(exportDownloadHref(job)).toBe("/exports/job-77/file");
  });

  it("IS-11: a finished S61 export renders a real download link, not a job id", () => {
    // Before the download lane this screen could only toast "your export is
    // ready" and name a `file://` path nobody could follow.
    const html = renderToStaticMarkup(<ExportReadyLine href="/exports/job-77/file" t={t} />);
    expect(html).toContain('href="/exports/job-77/file"');
    expect(html).toContain("download");
    expect(html).toContain("Download the CSV");
    expect(html).toContain("Your export is ready.");
    expect(html).not.toContain("file://");
  });

  it("a job with nothing to download produces no link at all", () => {
    // The screen renders the line only when the helper answered a href, so an
    // unfinished or file-less job leaves the surface unchanged (HR-1: the
    // route would 404 for it anyway).
    const base = { id: "job-77", kind: "audit_export", progress: null, error: null } as const;
    expect(exportDownloadHref({ ...base, status: "running", result_link: null })).toBeNull();
    expect(exportDownloadHref({ ...base, status: "failed", result_link: null })).toBeNull();
    expect(
      exportDownloadHref({ ...base, status: "succeeded", result_link: null }),
    ).toBeNull();
  });

  it("US-AUD-006 TC-5 / BR-AUD-014: the 50k cap renders the server's own numbers", () => {
    const capped = new ApiError(422, {
      code: "BIZ-CAP",
      message_key: "audit.export.row_cap_exceeded",
      params: { rows: 68000, cap: 50000 },
      br_ref: "BR-AUD-014",
    });
    const message = exportCapRefusal(capped, t);
    expect(message).toBe(
      "That's 68000 rows — more than the 50000 an export can carry. Narrow your filters and try again.",
    );
    // Only the cap gets "narrow your filters" — advice the count supports.
    const other = new ApiError(500, { code: "SYS-001", message_key: "errors.sys-internal" });
    expect(exportCapRefusal(other, t)).toBeNull();
    expect(exportCapRefusal(new Error("offline"), t)).toBeNull();
  });

  it("the export control is the ONE shared download button, CSV only (IS-11)", () => {
    const html = renderAudit(AUDIT_ROUTE, { list: result(ROWS) });
    expect(html).toContain('data-download="button"');
    expect(html).toContain("Download CSV");
    // IS-11: no XLSX exists in v1, and S61 declares no formatted PDF layout.
    expect(html.toLowerCase()).not.toContain("xlsx");
    expect(html).not.toContain('data-download="menu"');
  });

  it.todo(
    "US-AUD-006 TC-2: the export writes its own audit.exported row, visible in S61 moments later — server scope (BR-AUD-014 self-audit)",
  );
  it.todo(
    "US-AUD-006 TC-3/TC-4: an import-batch row links to its compliance stamp — the owning surfaces (S29, payments/assets batches) are not built",
  );
  it.todo("US-AUD-006 TC-8 (isolation): the file streams under the caller's own RLS — server scope (G5)");
});

// The drawer is URL state (`?entry=<id>`), so a test opens it exactly the way a
// shared link does — no click, no browser, no test-only prop on the screen.
// The returned markup is the DIALOG only, so an assertion about the drawer can
// never accidentally pass (or fail) on something the list behind it rendered.
function renderDrawerBody(entry: AuditEntry): string {
  const html = renderAudit(`${AUDIT_ROUTE}?${ENTRY_PARAM}=${entry.id}`, {
    list: result(ROWS),
    entry,
  });
  const start = html.indexOf('<div class="modal-overlay">');
  expect(start).toBeGreaterThan(-1);
  return html.slice(start);
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-AUD-004@009e809 (story+rules snapshot hash — EP-AUD-02 lead story; co-stories US-AUD-005@009e809 · US-AUD-006@009e809)
// generated: 2026-08-09 by story-coder v1 (W0 frontend integration lane — S61) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 296 passed / 83 todo across 30 files✔ (239+72 baseline unchanged and green; this packet adds 57 passing + 11 todo — the todos are browser-interaction, server/RLS and unbuilt-neighbour-screen scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E4 US-AUD-005 TC-2's related-approval reference has no ratified key name in the drawer contract — it stays todo rather than asserting an invented field · E4 US-AUD-005 TC-3/TC-4 need the owning modules' Audit tabs (S21/S50), which are not built · E4 the isolation halves of TC-8 are the G5 suite's, on live Postgres
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
