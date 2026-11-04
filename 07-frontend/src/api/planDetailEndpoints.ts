// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 7 — the plan DETAILS page's reads (images
//           24–37): the header and every tab, *Priced as of* a date, the Units
//           list and the Audit list, both paged by the server.
// Contract: CR-167-BRC10 §7.3 (as built at 2.484.0, §9) — `GET /plans/{id}?as_of=`,
//           `GET /plans/{id}/units` (`q`, `f.occupancy`, `format=csv`),
//           `GET /plans/{id}/audit` (`f.kind`, `f.from`, `f.to`, `format=csv`).
// Defects:  DEF-RAT-9353 (a unit row carries `premises_id` and `account_id`, so
//           both can be links — keys, never shown, B14 rule 31)
// ───────────────────────────────────────────────────────
//
// Kept apart from `planFormEndpoints.ts` (the form lane's) and `endpoints.ts`
// (22,000 lines that every lane appends to) — the tax and discount details
// pages' precedent. The SECTIONS are normalised by the form lane's
// `normalisePlanSections`, so the details tabs and Review read ONE shape
// (ruling 11).
//
// ⚠ **EVERY READ IS NORMALISED, NEVER TRUSTED** — a missing field is `null` or
// `[]` and the screen shows a dash, never a thrown render.
import { api } from "./client";
import type { ApiClient } from "./client";
import { readListPage } from "./paginated";
import type { PagedRows } from "./paginated";
import { normalisePlanSections } from "./planFormEndpoints";
import type { PlanSections } from "./planFormEndpoints";

type Raw = Record<string, unknown>;

function obj(raw: unknown): Raw | null {
  return typeof raw === "object" && raw !== null && !Array.isArray(raw) ? (raw as Raw) : null;
}

function str(raw: unknown): string | null {
  return typeof raw === "string" ? raw : typeof raw === "number" ? String(raw) : null;
}

function int(raw: unknown): number | null {
  return typeof raw === "number" && Number.isInteger(raw) ? raw : null;
}

function list(raw: unknown): unknown[] {
  return Array.isArray(raw) ? raw : [];
}

/** `draft · scheduled · in_force · ended · corrected` (`plan_reads.version_state`). */
export interface PlanVersionWindow {
  version: number;
  status: string;
  effective_from: string | null;
  effective_to: string | null;
  reason: string | null;
  /** `DEF-RAT-10031` — what this version changed against the one before it,
   *  in the server's words (*Minimum bill: $10.00 → $12.00*). Empty for the
   *  first version and wherever no change can be claimed. */
  changes?: WordedChange[];
  /** False where this version's stored copy predates the fix and does not
   *  record its terms — the screen marks it instead of claiming no change. */
  terms_recorded?: boolean;
}

/** One changed fact in words, as History serves it (`history_words`). */
export interface WordedChange {
  field: string;
  before: string;
  after: string;
}

export function wordedChanges(raw: unknown): WordedChange[] {
  return list(raw).flatMap((item) => {
    const row = obj(item);
    const field = row === null ? null : str(row.field);
    if (row === null || field === null) return [];
    return [{ field, before: str(row.before) ?? "—", after: str(row.after) ?? "—" }];
  });
}

/** Ruling 13's banner: a later version of the plan, or of something it names. */
export interface PlanUpcoming {
  kind: string;
  code: string;
  name: string;
  version: number | null;
  effective_from: string | null;
}

export interface PlanDetailRead {
  /** For keying and addresses only — never rendered (B14 rule 31). */
  id: string;
  name: string;
  code: string;
  /** `draft · published · archived` — `rate_plans.status`. */
  status: string;
  /** The date the sections were read on (`YYYY-MM-DD`). */
  as_of: string | null;
  /** The plan version in force on `as_of`. */
  plan_version: PlanVersionWindow | null;
  /** Every version, newest first. */
  versions: PlanVersionWindow[];
  upcoming: PlanUpcoming[];
  /** Current unit assignments — the Units tab's number. */
  units: number | null;
  sections: PlanSections;
}

function versionWindow(raw: unknown): PlanVersionWindow | null {
  const row = obj(raw);
  if (row === null) return null;
  const version = int(row.version);
  if (version === null) return null;
  return {
    version,
    status: str(row.status) ?? "",
    effective_from: str(row.effective_from),
    effective_to: str(row.effective_to),
    reason: str(row.reason),
  };
}

export function normalisePlanDetail(raw: unknown): PlanDetailRead {
  const body = obj(raw) ?? {};
  const versions = list(body.versions).flatMap((item) => {
    // `versions[]` rows are the filing record WITH a `window` block (§9).
    const row = obj(item);
    const window = versionWindow(obj(row?.window) ?? row);
    return window === null
      ? []
      : [{ ...window, changes: wordedChanges(row?.change_words), terms_recorded: row?.terms_recorded !== false }];
  });
  return {
    id: str(body.id) ?? "",
    name: str(body.name) ?? "",
    code: str(body.code) ?? "",
    status: str(body.status) ?? "",
    as_of: str(body.as_of),
    plan_version: versionWindow(body.plan_version),
    versions,
    upcoming: list(body.upcoming).flatMap((item) => {
      const row = obj(item);
      const code = row === null ? null : str(row.code);
      if (row === null || code === null) return [];
      return [
        {
          kind: str(row.kind) ?? "",
          code,
          name: str(row.name) ?? code,
          version: int(row.version),
          effective_from: str(row.effective_from),
        },
      ];
    }),
    units: int(body.units) ?? int(body.accounts),
    sections: namedNotes(normalisePlanSections(body), body),
  };
}

/**
 * `DEF-RAT-9285`, the details page's half: a note stored before the form kept
 * class NAMES holds the class's database id in `value`, and the server serves
 * the name beside it as `value_label`. The shared normaliser keeps `value`
 * (the form posts it back unchanged), so the PAGE swaps in the label to draw.
 */
function namedNotes(sections: PlanSections, body: Raw): PlanSections {
  const raw = list(obj(body.details)?.notes);
  if (raw.length === 0) return sections;
  const labels = raw.flatMap((item) => {
    const row = obj(item);
    // The same rows the shared normaliser keeps, so the indices line up.
    if (row === null || str(row.attribute) === null || str(row.operator) === null || str(row.value) === null) return [];
    return [str(row.value_label) ?? str(row.value)];
  });
  return {
    ...sections,
    details: {
      ...sections.details,
      notes: sections.details.notes.map((note, index) => ({ ...note, value: labels[index] ?? note.value })),
    },
  };
}

export function planDetailPath(planId: string): string {
  return `/plans/${encodeURIComponent(planId)}`;
}

/** `GET /plans/{id}?as_of=` — the whole page AS OF a date (image 28). */
export async function getPlanDetailRead(
  planId: string,
  asOf: string | null = null,
  client: ApiClient = api,
): Promise<PlanDetailRead> {
  const query: Record<string, string> = {};
  if (asOf !== null && asOf !== "") query.as_of = asOf;
  const response = await client.get<unknown>(planDetailPath(planId), { query });
  return normalisePlanDetail(response.data);
}

/**
 * `POST /plans/{id}/duplicate` (`DEF-RAT-9352`, image 25) — a NEW draft plan
 * offering what this one offers today, under the name and code given. Answers
 * the COPY, never the source.
 */
export async function copyPlan(
  planId: string,
  body: { name: string; code: string },
  client: ApiClient = api,
): Promise<PlanDetailRead> {
  const response = await client.post<unknown>(`${planDetailPath(planId)}/duplicate`, body);
  return normalisePlanDetail(response.data);
}

/** `POST /plans/{id}/versions/{n}/publish` (`DEF-RAT-9364`) — publish a new
 *  version *Save new version* left unpublished; the version in force before
 *  its start ends the day before (`BR-RAT-1066`). */
export async function publishPlanVersion(
  planId: string,
  version: number,
  client: ApiClient = api,
): Promise<PlanDetailRead> {
  const response = await client.post<unknown>(`${planDetailPath(planId)}/versions/${version}/publish`);
  return normalisePlanDetail(response.data);
}

// ── Units (images 31–33) ────────────────────────────────────────────────────

export const PLAN_UNIT_OCCUPANCY = ["occupied", "vacant"] as const;
export type PlanUnitOccupancy = (typeof PLAN_UNIT_OCCUPANCY)[number];

export interface PlanUnitRow {
  unit_id: string;
  unit_label: string | null;
  unit_no: string | null;
  /** `DEF-RAT-9353` — the premises the row links to. Never shown. */
  premises_id: string | null;
  premises_address: string | null;
  premises_city: string | null;
  /** Service CODES — the badges the product already draws. */
  services: string[];
  /** `DEF-RAT-9353` — the account the row links to. Never shown. */
  account_id: string | null;
  account_no: string | null;
  account_closed: boolean;
  customer_name: string | null;
  vacant: boolean;
  assigned_from: string | null;
}

export interface PlanUnitQuery {
  q?: string;
  occupancy?: string;
  page: number;
  per: number;
}

function unitQuery(query: Omit<PlanUnitQuery, "page" | "per">): Record<string, string> {
  const out: Record<string, string> = {};
  if (query.q !== undefined && query.q.trim() !== "") out.q = query.q.trim();
  if (query.occupancy !== undefined && (PLAN_UNIT_OCCUPANCY as readonly string[]).includes(query.occupancy)) {
    out["f.occupancy"] = query.occupancy;
  }
  return out;
}

function normaliseUnit(raw: unknown): PlanUnitRow | null {
  const row = obj(raw);
  const unitId = row === null ? null : str(row.unit_id);
  if (row === null || unitId === null) return null;
  return {
    unit_id: unitId,
    unit_label: str(row.unit_label),
    unit_no: str(row.unit_no),
    premises_id: str(row.premises_id),
    premises_address: str(row.premises_address),
    premises_city: str(row.premises_city),
    services: list(row.services).flatMap((code) => (typeof code === "string" ? [code] : [])),
    account_id: str(row.account_id),
    account_no: str(row.account_no),
    account_closed: row.account_closed === true,
    customer_name: str(row.customer_name),
    vacant: row.vacant === true,
    assigned_from: str(row.assigned_from),
  };
}

/** `GET /plans/{id}/units` — searched, filtered and paged in SQL (`NFR-3`). */
export async function getPlanUnitPage(
  planId: string,
  query: PlanUnitQuery,
  client: ApiClient = api,
): Promise<PagedRows<PlanUnitRow>> {
  const page = await readListPage<unknown>(
    `${planDetailPath(planId)}/units`,
    { ...unitQuery(query), page: query.page, per: query.per },
    client,
  );
  return { rows: page.rows.flatMap((row) => normaliseUnit(row) ?? []), total: page.total };
}

/** `?format=csv` — the WHOLE filtered set, streamed by the server. */
export async function getPlanUnitsCsv(
  planId: string,
  query: Omit<PlanUnitQuery, "page" | "per">,
  client: ApiClient = api,
): Promise<string> {
  const response = await client.get<string>(`${planDetailPath(planId)}/units`, {
    query: { ...unitQuery(query), format: "csv" },
    accept: "text/csv",
  });
  return typeof response.data === "string" ? response.data : "";
}

// ── Audit (images 34–36) ────────────────────────────────────────────────────

export const PLAN_AUDIT_KINDS = ["plan", "underneath"] as const;
export type PlanAuditKind = (typeof PLAN_AUDIT_KINDS)[number];

export interface PlanAuditRow {
  /** For keying only. */
  id: string;
  at: string | null;
  actor_name: string | null;
  what_kind: string;
  what_name: string | null;
  /** `created · edited · new_version · correction · added · removed · published`. */
  change: string;
  reason: string | null;
  before_display: string | null;
  after_display: string | null;
  /** `DEF-RAT-9502` — the same changed facts as CODES, so the screen words
   *  them in its language: the field's `key` (and its English `label` as the
   *  fallback), and for a yes/no, a status or a date its `raw` value. Null
   *  from an older server, which then draws the English `*_display`. */
  before_facts?: PlanAuditFact[] | null;
  after_facts?: PlanAuditFact[] | null;
  facts_more?: number;
  version: { kind: string; version: number | null; effective_from: string | null } | null;
  /** `DEF-RAT-10033` — for a row UNDERNEATH the plan (a tax, a discount, a
   *  schedule, a charge code), what changed in words (*Rate: 2.00% → 6.00%*). */
  changes?: WordedChange[];
}

export interface PlanAuditFact {
  key: string;
  label: string;
  kind: "bool" | "date" | "status" | "text" | string;
  raw: string | boolean | null;
  value: string;
}

function auditFacts(raw: unknown): PlanAuditFact[] | null {
  if (!Array.isArray(raw)) return null;
  return raw.flatMap((item) => {
    const fact = obj(item);
    const key = fact === null ? null : str(fact.key);
    if (fact === null || key === null) return [];
    const value = fact.raw;
    return [
      {
        key,
        label: str(fact.label) ?? key,
        kind: str(fact.kind) ?? "text",
        raw: typeof value === "boolean" || typeof value === "string" ? value : null,
        value: str(fact.value) ?? "",
      },
    ];
  });
}

export interface PlanAuditQuery {
  kind?: string;
  from?: string;
  to?: string;
  page: number;
  per: number;
}

function auditQuery(query: Omit<PlanAuditQuery, "page" | "per">): Record<string, string> {
  const out: Record<string, string> = {};
  if (query.kind !== undefined && (PLAN_AUDIT_KINDS as readonly string[]).includes(query.kind)) out["f.kind"] = query.kind;
  if (query.from !== undefined && query.from !== "") out["f.from"] = query.from;
  if (query.to !== undefined && query.to !== "") out["f.to"] = query.to;
  return out;
}

function normaliseAudit(raw: unknown, index: number): PlanAuditRow | null {
  const row = obj(raw);
  if (row === null) return null;
  const what = obj(row.what) ?? {};
  const version = obj(row.version);
  return {
    id: str(row.id) ?? `row-${index}`,
    at: str(row.at),
    actor_name: str(obj(row.actor)?.name),
    what_kind: str(what.kind) ?? "",
    what_name: str(what.name),
    change: str(row.change) ?? "edited",
    reason: str(row.reason),
    before_display: str(row.before_display),
    after_display: str(row.after_display),
    before_facts: auditFacts(row.before_facts),
    after_facts: auditFacts(row.after_facts),
    facts_more: int(row.facts_more) ?? 0,
    changes: wordedChanges(row.changes),
    version:
      version === null
        ? null
        : { kind: str(version.kind) ?? "", version: int(version.version), effective_from: str(version.effective_from) },
  };
}

/** `GET /plans/{id}/audit` — one paged read in words (J10). */
export async function getPlanAuditPage(
  planId: string,
  query: PlanAuditQuery,
  client: ApiClient = api,
): Promise<PagedRows<PlanAuditRow>> {
  const page = await readListPage<unknown>(
    `${planDetailPath(planId)}/audit`,
    { ...auditQuery(query), page: query.page, per: query.per },
    client,
  );
  return { rows: page.rows.flatMap((row, index) => normaliseAudit(row, index) ?? []), total: page.total };
}

export async function getPlanAuditCsv(
  planId: string,
  query: Omit<PlanAuditQuery, "page" | "per">,
  client: ApiClient = api,
): Promise<string> {
  const response = await client.get<string>(`${planDetailPath(planId)}/audit`, {
    query: { ...auditQuery(query), format: "csv" },
    accept: "text/csv",
  });
  return typeof response.data === "string" ? response.data : "";
}
