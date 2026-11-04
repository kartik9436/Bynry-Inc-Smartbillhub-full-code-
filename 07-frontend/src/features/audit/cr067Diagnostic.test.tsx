// ── Trace ──────────────────────────────────────────────
// Change:  CR-067 tasks B1 · B2 · C1 — "a runtime error becomes reproducible".
//          PO 2026-09-02, verbatim, ruling the surface: *"You click the row that
//          failed — the drawer you already have, the one behind "Expand" — and the
//          diagnostic is a second section inside it. Everything on my wireframe
//          lives there + Same screen. No new tab."*   Screens: S61
// Rules:   B14 rule 31 (no database id is ever the visible value of a field —
//          PO 2026-08-31: *"no Databse ID on screen - that is a rule"*) ·
//          B14 rule 32 (a description budget: one sentence per section, a stated
//          absence is a `<details>` CLOSED by default, no rule id or internal code
//          in clerk-facing copy) · BR-AUD-002 (the audit log has no write verbs,
//          which is WHY the technical half is a separate expiring record) ·
//          BR-AUD-009 (System Admin + Executive read S61) · BR-SHL-025 (the server
//          enforces; UI gating is convenience) · G38 (a stated absence cites the
//          row that will kill it)
// Defects: DEF-3321 (nothing serves `error_diagnostics` to a screen)
// ───────────────────────────────────────────────────────
/**
 * **NO GATE IN THIS REPO READS RENDERED OUTPUT**, which is why every case here
 * asserts MARKUP rather than a function's return value. Rule 32's clauses are
 * RATIFIED and UNENFORCED for exactly that reason, and `DEF-2375` — raised the
 * same day, on a screen whose own comment already claimed the fix — is what it
 * costs when a check reads the source instead of the page.
 *
 * ⚠ **EVERY CASE BELOW WAS PROVED RED FIRST (hard-won law 7), AND THE FAILURE IS
 * QUOTED WHERE IT WAS MEASURED, NOT PARAPHRASED.** Each quote is the sabotage
 * named beside it, run against this file before the sabotage was undone.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n, { LOCALE_REGISTRY } from "@/i18n";

import type {
  AuditDiagnostic,
  AuditEntry,
  AuditListResult,
  AuditRow,
  MyPermissions,
} from "@/api/endpoints";
import { AUDIT_FILTERS, AUDIT_OUTCOME_ERROR } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";
import { ROLE_EXECUTIVE, ROLE_SYSTEM_ADMIN } from "@/features/metering/meteringShared";

import {
  AUDIT_ROUTE,
  AuditDiagnosticSection,
  AuditLogPage,
  DIAGNOSTIC_UNREAD,
  ENTRY_PARAM,
  archiveFromParams,
  auditFailureOf,
  auditTableConfig,
  failureAdviceKey,
  failureComponent,
} from "./AuditLogPage";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const ENGLISH = LOCALE_REGISTRY.find((locale) => locale.code === "en")!;

const CONFIG = auditTableConfig(t, [], {
  when: () => <span />,
  entity: () => <span />,
  actor: () => "",
  source: () => <span />,
  action: () => <span />,
  summary: () => <span />,
});

/**
 * The 2 September failure, in the shape `apps/tenancy/sample_data.
 * _audit_failed_block` actually writes it — every key read from that call site,
 * and `meaning` copied verbatim out of `sample_errors.CATALOGUE`.
 */
const FAILED_AFTER: Record<string, unknown> = {
  module: "tenancy",
  block: "seed_sample_records",
  label: "Documents",
  error_code: "SD-PRECONDITION",
  reason_code: "exception",
  failure_class: "root",
  root_block: null,
  meaning:
    "The block refused because something it needs was not in place, and wrote " +
    "nothing rather than writing a partial set. The operator sentence on " +
    "Settings > Company profile > Sample data names what was missing.",
  detail_location:
    "the full wording is on the setup screen for this utility; this entry is kept short on purpose",
  reference: "5F2B-9C1D",
};

const FAILED_ROW: AuditRow = {
  id: "0198f2ab-6f10-7c4d-9b2e-2a1f0c5d7e31",
  created_at: "2026-09-02T09:12:00Z",
  actor: { id: "u-alex", name: "Alex Reed" },
  action: "sample.block_failed",
  entity_type: "tenant",
  entity_id: "01a062a7-9f7d-73e6-96e4-700cba033c73",
  summary: "error_code: SD-PRECONDITION",
  source: null,
};

const FAILED_ENTRY: AuditEntry = {
  ...FAILED_ROW,
  before: null,
  after: FAILED_AFTER,
  request_metadata: null,
};

/** The same drawer over a row that records a SUCCESS — no code, so no section. */
const SEEDED_ENTRY: AuditEntry = {
  ...FAILED_ROW,
  id: "0198f2ab-6f10-7c4d-9b2e-2a1f0c5d7e32",
  action: "sample.block_retried",
  after: {
    module: "tenancy",
    block: "seed_sample_records",
    label: "Documents",
    outcome: "seeded",
    seeded_count: 12,
    // ⚠ THE RETRY WRITES THIS KEY EVEN WHEN IT WORKED, AND IT IS NULL. Keying
    // the panel on the ACTION rather than on the code would put "Why this
    // failed" on the row that says a step recovered.
    error_code: null,
  },
  before: null,
  request_metadata: null,
};

/**
 * The 2 September deployment's own diagnostic, in the shape
 * `GET /audit-log/{id}/diagnostic` serves it — every key read off
 * `apps/audit/diagnostics.payload()` and every value off CR-067 §5's worked
 * example, which is the failure the Product Owner was actually hunting.
 */
const HELD_DIAGNOSTIC: AuditDiagnostic = {
  audit_action: "sample.block_failed",
  held: true,
  reason: "held",
  reference: "5F2B-9C1D",
  record: {
    reference: "5F2B-9C1D",
    trace_id: "5f2b9c1d3e7a41b8905c6d2e8f0a1b34",
    error_code: "SD-PRECONDITION",
    component: "tenancy:seed_sample_records",
    exception: {
      type: "StorageNotConfigured",
      module: "apps.tenancy.document_storage",
      chain: [],
    },
    frames: [
      { file: "06-backend/apps/tenancy/sample_data.py", function: "seed_sample_data", line: 1841 },
      { file: "06-backend/apps/tenancy/document_storage.py", function: "backend", line: 118 },
    ],
    settings_in_force: {
      DOCUMENT_STORAGE_BACKEND: "aws_s3",
      DOCUMENT_STORAGE_BUCKET: "",
      DOCUMENT_STORAGE_ALLOW_FILESYSTEM: false,
    },
    request_fields: ["subdomain", "company_name"],
    job: { kind: "sample_data_plant", id: "0198f2ab-6f10-7c4d-9b2e-2a1f0c5d7e40", step: 8, of: 18 },
    audit_action: "sample.block_failed",
    release: "2.128.2",
    captured_at: "2026-09-02T09:12:00Z",
    kept_until: "2026-12-01T09:12:00Z",
  },
};

/** The same reference, and nothing behind it — the record was swept (task A5). */
const SWEPT_DIAGNOSTIC: AuditDiagnostic = {
  audit_action: "sample.block_failed",
  held: false,
  reason: "not_held",
  reference: "5F2B-9C1D",
  record: null,
};

/** A row from before task A4 — it never had a reference at all. */
const NO_REFERENCE_DIAGNOSTIC: AuditDiagnostic = {
  audit_action: "sample.block_failed",
  held: false,
  reason: "no_reference",
  reference: null,
  record: null,
};

function listResult(rows: AuditRow[]): AuditListResult {
  return {
    page: { count: rows.length, next: null, previous: null, results: rows },
    window: { window: "hot", from: "2024-09-02T00:00:00+00:00" },
  };
}

function permissions(role: string): MyPermissions {
  return { role, role_name: role, permissions: [] };
}

/**
 * The drawer, opened the way a shared link opens it (`?entry=<id>`), with the
 * caller's own role already answered. The slice is the DIALOG only, so nothing
 * here can pass or fail on the list behind it.
 */
function drawer(
  entry: AuditEntry,
  role: string | null,
  diagnostic?: AuditDiagnostic,
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const path = `${AUDIT_ROUTE}?${ENTRY_PARAM}=${entry.id}`;
  const params = new URLSearchParams(path.split("?")[1] ?? "");
  const state = parseTableParams(params, CONFIG);
  const archive = archiveFromParams(params);
  queryClient.setQueryData(
    queryKeys.auditLog(serializeTableParams(state, CONFIG).toString() + `|${archive}`),
    listResult([FAILED_ROW]),
  );
  queryClient.setQueryData(queryKeys.auditEntry(entry.id), entry);
  // The System-Admin-only read. Left UNSEEDED by default, which is exactly the
  // state a real drawer is in for the first moment after it opens — the panel
  // must draw nothing then rather than claim an absence it has not been told
  // about.
  if (diagnostic !== undefined) {
    queryClient.setQueryData(queryKeys.auditDiagnostic(entry.id), diagnostic);
  }
  if (role !== null) {
    queryClient.setQueryData(queryKeys.myPermissions, permissions(role));
  }
  const html = renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <AuditLogPage timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  const start = html.indexOf('<div class="modal-overlay">');
  expect(start).toBeGreaterThan(-1);
  return html.slice(start);
}

/** The S61 list itself, with no row open — what the toolbar cases look at. */
function renderPage(): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const params = new URLSearchParams();
  const state = parseTableParams(params, CONFIG);
  queryClient.setQueryData(
    queryKeys.auditLog(serializeTableParams(state, CONFIG).toString() + "|false"),
    listResult([FAILED_ROW]),
  );
  queryClient.setQueryData(queryKeys.myPermissions, permissions(ROLE_SYSTEM_ADMIN));
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[AUDIT_ROUTE]}>
          <AuditLogPage timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The `<section data-audit="diagnostic">` only — never the whole drawer. */
function diagnosticSection(html: string): string {
  const start = html.indexOf('<section data-audit="diagnostic">');
  expect(start).toBeGreaterThan(-1);
  return html.slice(start, html.indexOf("</section>", start));
}

describe("CR-067 B2 — the diagnostic is a SECOND SECTION in the drawer that already exists", () => {
  it("renders inside the one dialog this screen has, and nowhere else", () => {
    const html = drawer(FAILED_ENTRY, ROLE_SYSTEM_ADMIN);
    // LAW 0 in AuditLogPage.tsx: ONE dialog implementation. The PO's ruling adds
    // a section to it — "No new tab" — so exactly one overlay is rendered and
    // the section is inside it.
    expect(html.split('<div class="modal-overlay">').length - 1).toBe(1);
    expect(html).toContain('data-audit="diagnostic"');
    expect(html).toContain("Why this failed");
  });

  /**
   * RED FIRST — `auditFailureOf` reading *is the key present* instead of *is
   * there a code*, which is the mistake a hurried lane makes, because
   * `sample.block_retried` writes `error_code: null` on a retry that WORKED.
   * Two cases bit, quoted from the run (`scripts/cr067_red_proof.py
   * panel-on-success`):
   *
   *   AssertionError: expected '<div class="modal-overlay"><div tabin…' not to
   *   contain 'data-audit="diagnostic"'
   *   AssertionError: expected { errorCode: 'undefined', …(7) } to be null
   */
  it("B14 rule 32 — a row that records a SUCCESS gets no panel at all", () => {
    const html = drawer(SEEDED_ENTRY, ROLE_SYSTEM_ADMIN);
    expect(html).not.toContain('data-audit="diagnostic"');
    expect(html).not.toContain("Why this failed");
    // And the drawer itself still renders — the absence is the panel's, not the
    // screen's.
    expect(html).toContain("What changed");
  });

  /**
   * The PO's wireframe, left panel, in their own order: what was being done ·
   * the result · why in plain words · what to do about it · the reference.
   *
   * RED FIRST — `meaning` dropped from `auditFailureOf` (`no-meaning`):
   *
   *   AssertionError: expected '<section data-audit="diagnostic"><h5 …' to
   *   contain 'The block refused because something i…'
   */
  it("B1/B2 — the plain half carries all five things the wireframe asks for", () => {
    const section = diagnosticSection(drawer(FAILED_ENTRY, ROLE_EXECUTIVE));
    expect(section).toContain("What was running");
    expect(section).toContain("Documents");
    expect(section).toContain("Result");
    expect(section).toContain("Stopped before it finished");
    // "why, in plain words" is the server's own fixed catalogue sentence — the
    // one that is safe on an append-only row because it interpolates nothing.
    expect(section).toContain("The block refused because something it needs was not in place");
    expect(section).toContain("What to do");
    expect(section).toContain("This is where it started");
    expect(section).toContain("Reference");
    expect(section).toContain("5F2B-9C1D");
  });

  /**
   * RED FIRST — the copy control's handle taken off `ReferenceValue`, leaving
   * the code readable but not copyable (`no-copy-control`):
   *
   *   AssertionError: expected '<section data-audit="diagnostic"><h5 …' to
   *   contain 'data-audit="copy-reference"'
   */
  it("B1 — the reference is a readable code WITH a copy control, for everyone who can open the log", () => {
    const section = diagnosticSection(drawer(FAILED_ENTRY, ROLE_EXECUTIVE));
    expect(section).toContain('data-audit="reference"');
    expect(section).toContain('data-audit="copy-reference"');
    expect(section).toContain(">Copy<");
  });

  /**
   * ⚠ **THE COMMONEST STATE ON A LIVE DEPLOYMENT TODAY, AND IT IS THE ONE A
   * DEMO WOULD NEVER HIT.** `reference` arrived on the audit row with CR-067
   * task A4 — this afternoon. **Every `sample.block_failed` row written before
   * that has none**, including all of the reporting tenant's existing ones, so
   * the first thing the PO clicks is a row with no reference at all. The row is
   * OMITTED rather than drawn with a dash: a labelled field holding nothing
   * reads as a value that failed to load.
   */
  it("a failure row from before the reference existed draws the section without one", () => {
    const older: AuditEntry = {
      ...FAILED_ENTRY,
      id: "0198f2ab-6f10-7c4d-9b2e-2a1f0c5d7e34",
      after: { ...FAILED_AFTER, reference: undefined },
    };
    const section = diagnosticSection(drawer(older, ROLE_SYSTEM_ADMIN));
    expect(section).toContain("Why this failed");
    expect(section).toContain("Stopped before it finished");
    // No label, no empty box, and no copy control for a value that is not there.
    expect(section).not.toContain(">Reference<");
    expect(section).not.toContain('data-audit="copy-reference"');
    expect(section).not.toContain('data-audit="reference"');
  });

  /**
   * B14 rule 31. The reference is NOT a database id — eight characters, minted
   * to be dictated, searchable by prefix — and the row's own record id stays
   * behind the closed *Stored record* fold where DEF-2378 put it.
   *
   * RED FIRST — the row's own `entity_id` written into the section as a value
   * (`database-id-in-panel`), which is DEF-2378 one screen along:
   *
   *   AssertionError: expected '<section data-audit="diagnostic"><h5 …' not to
   *   match /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[…/
   */
  it("B14 rule 31 — no database id is the visible value of anything in this section", () => {
    const section = diagnosticSection(drawer(FAILED_ENTRY, ROLE_SYSTEM_ADMIN));
    expect(section).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/);
    expect(section).not.toContain(FAILED_ENTRY.id);
    expect(section).not.toContain(FAILED_ENTRY.entity_id ?? "—");
  });
});

describe("CR-067 B2 — the technical half is the System Admin's", () => {
  /**
   * RED FIRST — the gate short-circuited to always-open (`gate-always-open`),
   * which is what a CSS-hidden panel amounts to. BOTH cases below bit:
   *
   *   AssertionError: expected '<section data-audit="diagnostic"><h5 …' not to
   *   contain 'data-audit="diagnostic-technical"'
   */
  it("an Executive reads S61 and does NOT get the technical panel", () => {
    const section = diagnosticSection(drawer(FAILED_ENTRY, ROLE_EXECUTIVE));
    expect(section).not.toContain('data-audit="diagnostic-technical"');
    // Not merely hidden: the strings are absent from the markup entirely.
    expect(section).not.toContain("SD-PRECONDITION");
    expect(section).not.toContain("sample.block_failed");
    // The plain half is untouched by the gate — that is the whole point.
    expect(section).toContain("5F2B-9C1D");
  });

  it("an unanswered /me/permissions is NOT a System Admin — never guess a role, never grant one", () => {
    const section = diagnosticSection(drawer(FAILED_ENTRY, null));
    expect(section).not.toContain('data-audit="diagnostic-technical"');
    expect(section).not.toContain("SD-PRECONDITION");
  });

  /**
   * RED FIRST — `props.action` swapped for `failure.errorCode` in the Event row,
   * so the panel showed the code twice and never said which event it was
   * (`event-row-shows-the-code`):
   *
   *   AssertionError: expected '<section data-audit="diagnostic"><h5 …' to
   *   contain 'sample.block_failed'
   */
  it("a System Admin gets the error, its module, the event and nothing a clerk would read", () => {
    const section = diagnosticSection(drawer(FAILED_ENTRY, ROLE_SYSTEM_ADMIN));
    expect(section).toContain('data-audit="diagnostic-technical"');
    expect(section).toContain("Error code");
    expect(section).toContain("SD-PRECONDITION");
    expect(section).toContain("Where");
    expect(section).toContain("tenancy · seed_sample_records");
    expect(section).toContain("Event");
    expect(section).toContain("sample.block_failed");
  });

  /**
   * The five-reds-one-cause problem `sample_data.py` records from DEF-660: a
   * retirement in the meters block took billing, payments and the payment plan
   * with it, *"a chain of five failures that read like five separate bugs"*. The
   * clerk half says which kind this is WITHOUT naming the block (rule 32 — the
   * root is a key); the technical half names it, for the reader who can act.
   */
  it("a knock-on says so in words, and only the technical half names the block it came from", () => {
    const knockOn: AuditEntry = {
      ...FAILED_ENTRY,
      id: "0198f2ab-6f10-7c4d-9b2e-2a1f0c5d7e33",
      after: {
        ...FAILED_AFTER,
        failure_class: "consequence",
        root_block: "metering:seed_sample_records",
      },
    };
    const section = diagnosticSection(drawer(knockOn, ROLE_SYSTEM_ADMIN));
    const plain = section.slice(0, section.indexOf('data-audit="diagnostic-technical"'));
    expect(plain).toContain("An earlier step failed first");
    expect(plain).not.toContain("metering:seed_sample_records");
    expect(section).toContain("Started at");
    expect(section).toContain("metering:seed_sample_records");
  });

  /**
   * B14 rule 32's third clause — no internal code in clerk-facing copy. The
   * technical values live BELOW the plain `<dl>`, so a clerk half that grew a
   * code would put one on a screen the PO has ruled twice about (DEF-2377).
   */
  it("B14 rule 32 — the plain half above the technical panel carries no internal code", () => {
    const section = diagnosticSection(drawer(FAILED_ENTRY, ROLE_SYSTEM_ADMIN));
    const plain = section.slice(0, section.indexOf('data-audit="diagnostic-technical"'));
    expect(plain).not.toContain("SD-PRECONDITION");
    expect(plain).not.toContain("sample.block_failed");
    expect(plain).not.toContain("seed_sample_records");
    expect(plain).not.toContain("DEF-");
    expect(plain).not.toContain("BR-AUD");
  });
});

describe("CR-067 B2 — the reproduction record, which is what this change is FOR", () => {
  /**
   * ⚠ **THIS IS THE CASE `DEF-3321` WAS FILED FOR, AND UNTIL TODAY IT COULD NOT
   * BE WRITTEN.** `error_diagnostics` was written at the seeding seams,
   * referenced from the permanent audit row and swept at ninety days, and **no
   * route in `06-backend` served it** — `apps/audit/api.py` defined three and
   * none read that table. So the six facts CR-067 §5 measures the whole change
   * against reached no screen, and the panel honestly stated the absence
   * instead. `GET /audit-log/{id}/diagnostic` is the read that closed it.
   *
   * Every assertion below is one of §5's six, in the order a person reads them.
   *
   * RED FIRST — the panel bound to the old payload only, i.e. the
   * `ReproductionRecord` block deleted and the stated absence put back
   * (`record-not-drawn`). Quoted from the run:
   *
   *   AssertionError: expected '<section data-audit="diagnostic"><h5 …' to
   *   contain 'data-audit="diagnostic-record"'
   */
  it("a System Admin sees the exception, the code, the step, the build and the settings", () => {
    const section = diagnosticSection(drawer(FAILED_ENTRY, ROLE_SYSTEM_ADMIN, HELD_DIAGNOSTIC));
    expect(section).toContain('data-audit="diagnostic-record"');
    // 1 · what blew up, as a TYPE and a module — never a message.
    expect(section).toContain("Exception");
    expect(section).toContain("StorageNotConfigured · apps.tenancy.document_storage");
    // 2 · where in the code — the innermost frame, open, because it is the one
    //     a reader needs first.
    expect(section).toContain("06-backend/apps/tenancy/document_storage.py:118 · backend");
    // 3 · which step of which job.
    expect(section).toContain("sample_data_plant");
    expect(section).toContain("8 of 18");
    // 4 · which build.
    expect(section).toContain("2.128.2");
    // 5 · the settings in force — the three lines CR-067 §5's worked example
    //     prints, and the three that ARE the answer to this particular failure.
    // `&quot;` because this is MARKUP: the value goes through `JSON.stringify`,
    // so an EMPTY bucket reads as `""` on screen — which is the whole answer to
    // this particular failure and would be invisible drawn as a blank.
    expect(section).toContain('DOCUMENT_STORAGE_BACKEND = &quot;aws_s3&quot;');
    expect(section).toContain('DOCUMENT_STORAGE_BUCKET = &quot;&quot;');
    expect(section).toContain('DOCUMENT_STORAGE_ALLOW_FILESYSTEM = false');
    // 6 · the request's field NAMES. The writer's signature is what guarantees
    //     they are names; this row is where the guarantee is visible.
    expect(section).toContain("subdomain, company_name");
  });

  /**
   * CR-067 §5's own bar, applied to the SCREEN rather than to the record:
   * *"could somebody holding ONLY the diagnostic record write a failing test?"*
   *
   * The six lines §5 prints are rebuilt here from the rendered markup and from
   * nothing else — no fixture lookup, no second source. If this ever has to
   * reach past the panel for a value, the panel is incomplete.
   *
   * RED FIRST — the record panel not drawn at all, which is the state DEF-3321
   * recorded (`record-not-drawn`):
   *
   *   AssertionError: expected [] to deeply equal [ …(3) ]
   */
  it("§5 — the six lines of the failing test can be read off the panel itself", () => {
    const section = diagnosticSection(drawer(FAILED_ENTRY, ROLE_SYSTEM_ADMIN, HELD_DIAGNOSTIC));
    // `&quot;` because this is MARKUP — the panel renders the value through
    // `JSON.stringify`, so an empty string reads as `""` on screen and as
    // `&quot;&quot;` in the bytes. Reading the escaped form is the point: it is
    // what a person actually sees.
    const settings = /([A-Z][A-Z_]+) = (&quot;.*?&quot;|true|false)/g;
    const rebuilt = [...section.matchAll(settings)].map(
      (match) => `settings.${match[1]} = ${match[2].replaceAll("&quot;", '"')}`,
    );
    expect(rebuilt).toEqual([
      'settings.DOCUMENT_STORAGE_BACKEND = "aws_s3"',
      'settings.DOCUMENT_STORAGE_BUCKET = ""',
      "settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = false",
    ]);
    // …and the thing to assert `raises` on, with the module to import it from.
    expect(section).toContain("StorageNotConfigured");
    expect(section).toContain("apps.tenancy.document_storage");
  });

  /**
   * B14 rule 32. A call path is the least readable and most occasionally
   * decisive thing on this panel, so the innermost frame is open and the rest
   * folds. A `<details>` cannot leak its content onto the screen, because being
   * closed is what it IS.
   *
   * RED FIRST, twice. The fold rendered `open`, which is a paragraph with extra
   * steps (`stack-open`):
   *
   *   AssertionError: expected '<details open="" class="mt-2" data-au…' not to
   *   contain ' open'
   *
   * …and the whole record panel absent (`record-not-drawn`), where the message
   * is the check — `expected -1 to be greater than -1` alone could not say
   * which sabotage it caught (DEF-182):
   *
   *   AssertionError: the full call path is missing entirely: expected -1 to be
   *   greater than -1
   */
  it("B14 rule 32 — the full call path is a `<details>`, CLOSED, and the top frame is not", () => {
    const section = diagnosticSection(drawer(FAILED_ENTRY, ROLE_SYSTEM_ADMIN, HELD_DIAGNOSTIC));
    const start = section.indexOf('data-audit="diagnostic-stack"');
    expect(start, "the full call path is missing entirely").toBeGreaterThan(-1);
    const opening = section.lastIndexOf("<details", start);
    expect(opening, "the call path is not a <details> — a visible list is DEF-2375").toBeGreaterThan(
      -1,
    );
    expect(section.slice(opening, section.indexOf(">", start))).not.toContain(" open");
    // The outer frame is inside the fold; the innermost is above it, open.
    const inside = section.slice(opening, section.indexOf("</details>", opening));
    expect(inside).toContain("sample_data.py:1841");
    expect(section.slice(0, opening)).toContain("document_storage.py:118");
  });

  /**
   * ⚠ **THE RETENTION WINDOW IS A DATE AND NEVER A NUMBER OF DAYS, AND THE
   * REASON IS TWO RULES AT ONCE.** `OQ-1390` is OPEN — is ninety right, and does
   * a diagnostic fall under `audit_log`'s regime or its own — so printing a
   * figure would resolve an open question by choosing a value, which the prime
   * directive forbids. And `DIAGNOSTIC_RETENTION_DAYS` is a per-deployment
   * SETTING this screen cannot read, so a utility that set thirty would be told
   * ninety by its own product. The server stamps the date on the record at write
   * time; the screen renders that, through the shared formatter (BR-SHL-034).
   *
   * RED FIRST — the record panel not drawn (`record-not-drawn`):
   *
   *   AssertionError: expected '<section data-audit="diagnostic"><h5 …' to
   *   contain 'Detail kept until'
   */
  it("says when the detail expires as this deployment's own DATE, not as a number of days", () => {
    const section = diagnosticSection(drawer(FAILED_ENTRY, ROLE_SYSTEM_ADMIN, HELD_DIAGNOSTIC));
    expect(section).toContain("Detail kept until");
    expect(section).toContain('data-audit="diagnostic-kept-until"');
    // The drawer is rendered with MM/DD/YYYY and America/Chicago — the date is
    // the SERVER's stamp put through the screen's own formatter, not a string.
    expect(section).toContain("12/01/2026");
    // ⚠ `\b90\b`, NOT `"90"`. The full trace id on this panel happens to carry
    // the digits `905`, so the loose form fails on healthy markup — a check that
    // cannot tell a real breach from a hex string is DEF-182's *"worse than no
    // check, because it is trusted"*. What must never appear is the NUMBER.
    expect(section).not.toMatch(/\b90\b/);
    expect(section.toLowerCase()).not.toContain(" days");
  });

  /**
   * B14 rule 31 — PO 2026-08-31, *"no Databse ID on screen - that is a rule"*.
   *
   * The record's own row id is never SERVED (`apps/audit/diagnostics.payload()`
   * omits it deliberately), so it cannot be rendered by a later lane. What IS
   * here is the full trace id, which is a correlation value a server log is
   * grepped for and not a database key — and the eight-character reference,
   * which is minted to be dictated.
   *
   * RED FIRST — the job's uuid drawn beside its kind, which is the obvious
   * "while I'm here" (`draw-the-job-id`):
   *
   *   AssertionError: expected '<section data-audit="diagnostic"><h5 …' not to
   *   match /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[…/
   */
  it("B14 rule 31 — the record's own row id is nowhere, and the trace is not one", () => {
    const section = diagnosticSection(drawer(FAILED_ENTRY, ROLE_SYSTEM_ADMIN, HELD_DIAGNOSTIC));
    // No uuid anywhere in the panel — the job id is served and is not drawn.
    expect(section).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/);
    expect(section).not.toContain(HELD_DIAGNOSTIC.record!.job.id!);
    // ⚠ AND THE RAW TRACE IS NOT DRAWN EITHER, THOUGH IT IS SERVED. It was on
    // this panel for an hour and `G44` caught it: rule 31's letter is about a
    // database id and its REASON is about a value nobody can read aloud, which
    // a 32-hex string is. The reference IS its first eight hex, so a log grep
    // still works from what is on screen.
    expect(section).not.toContain("5f2b9c1d3e7a41b8905c6d2e8f0a1b34");
    // The one value that IS meant to be read.
    expect(section).toContain("5F2B-9C1D");
  });

  /**
   * ⚠ **THE ROLE GATE IS NOW A BOUNDARY, AND THIS IS THE CASE THAT SAYS SO.**
   * The record is deliberately put in the cache for an EXECUTIVE here — the one
   * state a "the browser was never sent it" argument cannot cover. The panel
   * still draws none of it, and the server refuses the read besides
   * (`tests/test_cr067_diagnostic_read.py`, 403 AUTH-002). Before this endpoint
   * existed there was only one payload and only the drawing could be gated.
   *
   * RED FIRST — the gate short-circuited to always-open (`gate-always-open`):
   *
   *   AssertionError: expected '<section data-audit="diagnostic"><h5 …' not to
   *   contain 'data-audit="diagnostic-record"'
   */
  it("an Executive holding the record in cache still gets none of it drawn", () => {
    const section = diagnosticSection(drawer(FAILED_ENTRY, ROLE_EXECUTIVE, HELD_DIAGNOSTIC));
    expect(section).not.toContain('data-audit="diagnostic-record"');
    expect(section).not.toContain("StorageNotConfigured");
    expect(section).not.toContain("DOCUMENT_STORAGE_BUCKET");
    expect(section).not.toContain("5f2b9c1d3e7a41b8905c6d2e8f0a1b34");
    // The plain half is untouched by the gate — that is the whole point.
    expect(section).toContain("5F2B-9C1D");
  });

  /**
   * Hard-won law 2, pointed at the moment BEFORE the answer arrives. While the
   * read is in flight the panel claims nothing: not a record, and not an
   * absence. An absence drawn optimistically is the same defect as a panel
   * bound to a key nothing sends — it states something the screen does not know.
   *
   * RED FIRST — the `!diagnosticPending` guard dropped, so the "could not be
   * read" note is drawn while the read is still in flight
   * (`absence-while-pending`):
   *
   *   AssertionError: expected '<section data-audit="diagnostic"><h5 …' not to
   *   contain 'data-audit="diagnostic-gap"'
   */
  it("claims nothing at all while the read is still in flight", () => {
    const section = diagnosticSection(drawer(FAILED_ENTRY, ROLE_SYSTEM_ADMIN));
    expect(section).toContain('data-audit="diagnostic-technical"');
    expect(section).not.toContain('data-audit="diagnostic-record"');
    expect(section).not.toContain('data-audit="diagnostic-gap"');
  });
});

describe("CR-067 — the two absences that are REAL, and the note that expired with its defect", () => {
  /**
   * The record expired (task A5). CR-067 struck that bargain deliberately: the
   * detail is what carries risk, so the detail is what expires — and the
   * permanent row still reads correctly on its own, which is A5's actual
   * acceptance criterion.
   *
   * RED FIRST — the `<details>` rewritten as the always-visible `<div>`/`<h6>` a
   * first draft reaches for, which is `DEF-2375` exactly
   * (`absence-as-a-paragraph`):
   *
   *   AssertionError: the absence is not a <details> — a visible paragraph is
   *   DEF-2375: expected -1 to be greater than -1
   */
  it("B14 rule 32 — a swept record is a `<details>`, CLOSED, with the sentence inside it", () => {
    const section = diagnosticSection(drawer(FAILED_ENTRY, ROLE_SYSTEM_ADMIN, SWEPT_DIAGNOSTIC));
    const start = section.indexOf('data-audit="diagnostic-gap"');
    expect(start, "the stated absence is missing entirely").toBeGreaterThan(-1);
    // ⚠ THE MESSAGE IS THE CHECK HERE. `expect(-1).toBeGreaterThan(-1)` is what
    // this printed on its first RED run, and DEF-182's lesson is that a check
    // whose output cannot distinguish one failure from another is trusted and
    // useless. The sentence says which sabotage it caught.
    const before = section.lastIndexOf("<details", start);
    expect(
      before,
      "the absence is not a <details> — a visible paragraph is DEF-2375",
    ).toBeGreaterThan(-1);
    const open = section.slice(before, section.indexOf(">", start));
    expect(open).not.toContain(" open");
    const inside = section.slice(before, section.indexOf("</details>", before));
    expect(inside).toContain("The technical detail is no longer held");
    expect(inside).toContain("are still on this entry and are never removed");
    // And no record is drawn beside a sentence saying there is none.
    expect(section).not.toContain('data-audit="diagnostic-record"');
  });

  /**
   * ⚠ **THE STATE THE PRODUCT OWNER MEETS FIRST.** `reference` arrived on the
   * audit row with task A4; every `sample.block_failed` row written before that
   * has none, including all of the reporting tenant's existing ones. "This
   * failure predates the record" and "the record expired" are different facts
   * about the world, and saying the second when the first is true invents a
   * record that never existed.
   *
   * RED FIRST — the screen's own half of it: `absenceCopy` collapsed so
   * `no_reference` falls through to the expired sentence, which is the
   * tidier-looking version (`absence-one-sentence`). The server's half is
   * sabotaged separately as `be-one-absence-code`.
   */
  it("a failure from before the record existed says THAT, not that something expired", () => {
    const older: AuditEntry = {
      ...FAILED_ENTRY,
      id: "0198f2ab-6f10-7c4d-9b2e-2a1f0c5d7e35",
      after: { ...FAILED_AFTER, reference: undefined },
    };
    const section = diagnosticSection(drawer(older, ROLE_SYSTEM_ADMIN, NO_REFERENCE_DIAGNOSTIC));
    const start = section.indexOf('data-audit="diagnostic-gap"');
    const details = section.slice(section.lastIndexOf("<details", start));
    expect(details).toContain("recorded before the technical detail was kept");
    expect(details).not.toContain("no longer held");
    expect(section).toContain('data-diagnostic-absence="no_reference"');
  });

  /**
   * The read did not answer. Said rather than drawn as an empty panel, which
   * would read as "there is nothing here" — a claim the screen cannot make.
   * Rendered through the component directly because a failed query is the one
   * state static rendering cannot reach.
   *
   * RED FIRST — `absenceCopy` collapsed so every absence reads as the expired
   * one (`absence-one-sentence`), which would tell a reader a record was swept
   * when in fact nobody knows:
   *
   *   AssertionError: expected '<section data-audit="diagnostic"><h5 …' to
   *   contain 'could not be read'
   */
  it("a read that did not come back says so, instead of looking like an empty record", () => {
    const html = renderToStaticMarkup(
      <AuditDiagnosticSection
        failure={auditFailureOf(FAILED_AFTER)!}
        action="sample.block_failed"
        isSystemAdmin
        diagnostic={null}
        diagnosticPending={false}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        t={t}
      />,
    );
    expect(html).toContain(`data-diagnostic-absence="${DIAGNOSTIC_UNREAD}"`);
    expect(html).toContain("could not be read");
    expect(html).not.toContain('data-audit="diagnostic-record"');
  });

  /**
   * ⚠ **`OQ-1390` IS OPEN AND NONE OF THESE THREE SENTENCES MAY CARRY A DIGIT.**
   * The lane before this one put "90 days" into eleven catalogues and took it
   * back out within the hour: the prime directive forbids resolving an open
   * question by choosing a value, and `DIAGNOSTIC_RETENTION_DAYS` is a
   * per-deployment setting this screen cannot read, so a utility set to thirty
   * would be told ninety in its own language. The check now covers all three
   * absences rather than only the one that existed then.
   */
  it("no absence sentence names a retention window, in any of the eleven catalogues", () => {
    const keys = [
      "audit.diagnostic.goneTitle",
      "audit.diagnostic.goneBody",
      "audit.diagnostic.olderTitle",
      "audit.diagnostic.olderBody",
      "audit.diagnostic.unreadTitle",
      "audit.diagnostic.unreadBody",
    ];
    for (const locale of LOCALE_REGISTRY) {
      for (const key of keys) {
        const value = locale.catalog[key];
        expect(value, `${locale.code}.json is missing ${key}`).toBeTruthy();
        expect(value, `${locale.code}.json ${key} names a retention figure`).not.toMatch(/\d/);
      }
    }
  });

  /**
   * G38 / DEF-445, the other way round: **a stated absence must not outlive its
   * reason.** The panel used to carry a `<details data-tracks="DEF-3321">`
   * saying the technical record could not be read from this screen. That defect
   * is closed, so the sentence is false — and the copy is gone from all eleven
   * catalogues, not merely unrendered.
   *
   * The three that remain carry NO `data-tracks`, and that is correct rather
   * than an oversight: `tracks` names the row that will KILL the note, and no
   * row will close these. They are permanent facts about a record with a
   * lifetime.
   *
   * RED FIRST — the id put back on the disclosure, which is what a copy-paste of
   * the old note produces (`absence-note-outlives-its-defect`):
   *
   *   AssertionError: expected '<section data-audit="diagnostic"><h5 …' not to
   *   contain 'DEF-3321'
   */
  it("the DEF-3321 note is gone, because the endpoint it waited for exists", () => {
    for (const entry of [HELD_DIAGNOSTIC, SWEPT_DIAGNOSTIC, NO_REFERENCE_DIAGNOSTIC]) {
      const section = diagnosticSection(drawer(FAILED_ENTRY, ROLE_SYSTEM_ADMIN, entry));
      expect(section).not.toContain("DEF-3321");
      expect(section).not.toContain("not on this screen yet");
    }
    for (const locale of LOCALE_REGISTRY) {
      expect(locale.catalog["audit.diagnostic.gapTitle"], `${locale.code}.json`).toBeUndefined();
      expect(locale.catalog["audit.diagnostic.gapBody"], `${locale.code}.json`).toBeUndefined();
    }
  });
});

describe("CR-067 B3 — \"Errors only\", and the silent drop it has to survive", () => {
  /**
   * ⚠ **THE ASSERTION THAT MATTERS MOST IN THIS FILE, AND IT LOOKS LIKE
   * BOOKKEEPING.** `parseTableParams` and `serializeTableParams` walk
   * `TableConfig.filters`; `auditQuery` walks `AUDIT_FILTERS`; and the server
   * DROPS an `f.<name>` it does not declare rather than refusing it
   * (BR-SHL-011 — a list param never 4xx's). **Three places, three silent
   * drops, and the only symptom of any of them is a count that did not move.**
   * On the reporting tenant's 809 audit rows, a toggle that fails this way
   * returns all 809 and reads as a product with no errors in it — which is
   * worse than having no toggle, and is why `DEF-3322` says the filter lands
   * before the control does.
   *
   * RED FIRST — `outcome` removed from `auditTableConfig.filters`, leaving the
   * control in place (`filter-not-declared`):
   *
   *   AssertionError: the toggle did not reach the URL — an undeclared filter
   *   is dropped in silence and the list comes back unfiltered: expected
   *   'sort=when&dir=desc' to contain 'f.outcome=error'
   *
   * And RED again one layer on, with the screen declaring it and the typed
   * client not (`filter-not-in-the-client`) — the same drop, in the file that
   * builds the query string:
   *
   *   AssertionError: expected [ 'actor', 'action', …(5) ] to include 'outcome'
   */
  it("the toggle reaches the URL and the request, because both vocabularies declare it", () => {
    const state = { ...parseTableParams(new URLSearchParams(), CONFIG) };
    state.filters = { outcome: AUDIT_OUTCOME_ERROR };
    const url = serializeTableParams(state, CONFIG).toString();
    expect(
      decodeURIComponent(url),
      "the toggle did not reach the URL — an undeclared filter is dropped in "
        + "silence and the list comes back unfiltered",
    ).toContain("f.outcome=error");
    // …and it survives the round trip, so a shared link and a reload land on
    // the same narrowed list.
    expect(parseTableParams(new URLSearchParams(url), CONFIG).filters.outcome).toBe("error");
    // …and the API client sends it (a filter it does not know is dropped there
    // too, one layer further on).
    expect(AUDIT_FILTERS).toContain("outcome");
  });

  /**
   * The PO asked for the control in as many words — *"What I would add to the
   * toolbar is a "Errors only" filter, so you can jump straight to the failures
   * without scrolling past 800 rows of successful seeding. - Yes this is
   * required"*.
   *
   * RED FIRST — the checkbox removed from `AuditFilterPanel` (`no-errors-only`):
   *
   *   AssertionError: expected '<div class="px-4 pt-6 pb-8"><div><spa…' to
   *   contain 'id="f.outcome"'
   */
  it("draws the control the PO asked for, off by default", () => {
    const html = renderPage();
    expect(html).toContain('id="f.outcome"');
    expect(html).toContain("Errors only");
    // Unchecked until somebody ticks it: the default list is the whole log.
    const input = html.slice(html.indexOf('id="f.outcome"'));
    expect(input.slice(0, input.indexOf(">"))).not.toContain("checked");
  });

  /**
   * ⚠ **THE STRUCTURAL HALF OF THIS IS IN `AuditToolbarAlignment.dom.test.tsx`
   * AND NOT HERE, BECAUSE THIS FILE CANNOT ANSWER IT.** "Is the toggle inside
   * the six-filter grid" is a question about NESTING, and a static string can
   * only answer questions about ORDER: a sabotage that put the checkbox
   * straight into the grid with `className="contents"` left the markup order
   * untouched and this file green. `closest()` in jsdom decides it, so the case
   * moved to the suite that has a DOM (DEF-182 — a check that cannot tell the
   * breach from the fix is worse than none).
   *
   * What stays here is the half a string CAN prove: the toggle writes the
   * filter, and it is the last thing in the panel rather than the first, so a
   * person meets the six named filters before the one blunt jump.
   */
  it("sits after the six named filters, so the blunt jump is not the first thing met", () => {
    const html = renderPage();
    expect(html.indexOf('id="f.outcome"')).toBeGreaterThan(html.indexOf('id="f.to"'));
    expect(html.indexOf('id="f.outcome"')).toBeGreaterThan(html.indexOf('id="f.actor"'));
  });
});

describe("CR-067 — the reader, provable without a browser", () => {
  it("a payload with no error code is not a failure, whatever the action says", () => {
    expect(auditFailureOf(null)).toBeNull();
    expect(auditFailureOf({})).toBeNull();
    expect(auditFailureOf({ error_code: null })).toBeNull();
    expect(auditFailureOf({ error_code: "   " })).toBeNull();
    // Not a string is not a code — a number here would render as one.
    expect(auditFailureOf({ error_code: 42 })).toBeNull();
    expect(auditFailureOf(SEEDED_ENTRY.after)).toBeNull();
  });

  it("every field is read from the payload the server already sends, and nothing is invented", () => {
    const failure = auditFailureOf(FAILED_AFTER);
    expect(failure).not.toBeNull();
    expect(failure?.errorCode).toBe("SD-PRECONDITION");
    expect(failure?.label).toBe("Documents");
    expect(failure?.module).toBe("tenancy");
    expect(failure?.block).toBe("seed_sample_records");
    expect(failure?.failureClass).toBe("root");
    expect(failure?.rootBlock).toBeNull();
    expect(failure?.reference).toBe("5F2B-9C1D");
    expect(failureComponent(failure!)).toBe("tenancy · seed_sample_records");
  });

  it("a knock-on is not the one to fix, and the advice says which it is", () => {
    const root = auditFailureOf({ error_code: "SD-DB-ERROR", failure_class: "root" });
    const knockOn = auditFailureOf({
      error_code: "SD-DB-ERROR",
      failure_class: "consequence",
      root_block: "metering:seed_sample_records",
    });
    expect(failureAdviceKey(root!)).toBe("audit.diagnostic.adviceRoot");
    expect(failureAdviceKey(knockOn!)).toBe("audit.diagnostic.adviceKnockOn");
    // An older row that never carried the class gets NO advice rather than the
    // wrong one — an invented instruction is worse than a missing row.
    expect(failureAdviceKey(auditFailureOf({ error_code: "SD-DB-ERROR" })!)).toBeNull();
    // Rule 32 again: the root block is a KEY, so the clerk-facing advice never
    // names it. It renders in the technical half.
    expect(t("audit.diagnostic.adviceKnockOn")).not.toContain("metering:");
  });

  it("the component line is omitted rather than drawn around nothing", () => {
    expect(failureComponent(auditFailureOf({ error_code: "SD-DB-ERROR" })!)).toBeNull();
    expect(failureComponent(auditFailureOf({ error_code: "X", module: "billing" })!)).toBe(
      "billing",
    );
  });
});

describe("CR-067 C1 — all ELEVEN catalogues", () => {
  /**
   * RED FIRST — one key removed from `de.json`, which is the shape G15 was
   * written for and which renders the raw key name to anyone not reading English
   * (`english-only`):
   *
   *   AssertionError: de.json is missing keys: expected [
   *   'audit.diagnostic.advice' ] to have a length of +0 but got 1
   *
   * And RED again on G15's other half — the key present with the English string
   * in it (`english-pasted-in`), which is what a hurried eleven-file edit
   * produces and what the parity gate's 5,848-row baseline makes easy to miss:
   *
   *   AssertionError: it-IT.json left English in place: expected [
   *   'audit.diagnostic.techWhere' ] to have a length of +0 but got 1
   */
  it("carry every new key, and none of them is the English string pasted in", () => {
    // BR-SHL-041's ONE registry, not a directory listing: the picker, the tenant
    // default and the per-user override all read this, so a catalogue that is on
    // disk and not in here is not a language this product offers.
    expect(LOCALE_REGISTRY).toHaveLength(11);
    const english = ENGLISH.catalog;
    const keys = Object.keys(english).filter(
      (key) => key.startsWith("audit.diagnostic.") || key === "audit.filter.errorsOnly",
    );
    // 17 from the B1/B2 lane, minus the two `gap*` keys whose absence stopped
    // being true when `DEF-3321` closed, plus 16 diagnostic keys for the record
    // and the three real absences, plus the toolbar's own label = 32.
    expect(keys).toHaveLength(32);
    for (const locale of LOCALE_REGISTRY) {
      const missing = keys.filter((key) => !(key in locale.catalog));
      expect(missing, `${locale.code}.json is missing keys`).toHaveLength(0);
      if (locale.code === "en") {
        continue;
      }
      // A value byte-identical to English is a paste-in that was never
      // translated — G15's own rule, asserted here for THESE keys so the lane
      // cannot rely on somebody reading a 5,848-row baseline.
      const pasted = keys.filter((key) => locale.catalog[key] === english[key]);
      expect(pasted, `${locale.code}.json left English in place`).toHaveLength(0);
    }
  });

  it("the copy a clerk reads names no rule, no defect and no code (B14 rule 32)", () => {
    const english = ENGLISH.catalog;
    for (const [key, value] of Object.entries(english)) {
      if (!key.startsWith("audit.diagnostic.")) {
        continue;
      }
      expect(value, key).not.toMatch(/\b(?:DEF|OQ|BR|US|EP|GT|CR|IS|ADR)-\d/);
      expect(value, key).not.toContain("error_diagnostics");
      expect(value, key).not.toContain("audit_log");
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-067 §3 (the approved shape) + §5 (the acceptance test) + §6 tasks B1/B2/B3/C1 + the PO's ruling of 2026-09-02 quoted in the header + B14 rules 31/32 + BR-AUD-002/009 + BR-SHL-011/025 + defects DEF-3321 and DEF-3322
// generated: 2026-09-02 by the CR-067 frontend lane; extended the same day by the CR-067 B2/B3 lane when the endpoint and the filter landed
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report
// exceptions: (1) **THE ROLE GATE IS A BOUNDARY NOW AND WAS NOT WHEN THIS FILE WAS WRITTEN, AND THE DIFFERENCE IS WHICH READ THE DATA CAME FROM.** The reproduction record arrives on `GET /audit-log/{id}/diagnostic` behind `SystemAdminOnly`, so an Executive is refused 403 by the server (`tests/test_cr067_diagnostic_read.py`) and never receives it; `useTenantRole` here decides whether to ASK. What is still drawn from the shared payload — the plain half and the four summary rows — remains BR-SHL-025 convenience, and the case above proves the gate holds even when the record is put in an Executive's cache by hand. (2) the SERVER half of the "Errors only" filter is not asserted here and is not claimed: this file proves the toggle reaches the URL and the request, and `tests/test_cr067_diagnostic_read.py` proves the eight action codes narrow a 24-row log to its 4 failures.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
