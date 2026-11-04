// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 8 — the reads and writes the plan EDIT
//           form makes (images 37–44 of `05-prototype/plans-2026-10-03/`).
// Contract: CR-167-BRC10 §7.3 and §9 (server built at 2.484.0) —
//           `GET /plans/{id}` (the plan, its sections and its versions),
//           `PATCH /plans/{id}` (*Name and details*: same version, BR-RAT-1067;
//           a draft: anything), `POST /plans/{id}/versions` (*Change from a
//           date*, BR-RAT-1066), `POST /plans/{id}/corrections` (*Fix a
//           mistake*, BR-RAT-1016 verb 2), `POST /plans/{id}/publish` (a draft).
// ───────────────────────────────────────────────────────
//
// ONE READ, NORMALISED DEFENSIVELY: a field the server does not send is a dash
// or an empty list on screen, never a broken step. The sections are the SAME
// `PlanSections` the details tabs and the New form's Review draw (ruling 11),
// so the edit draft is read back from exactly what the clerk sees there.
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { normalisePlanSections } from "@/api/planFormEndpoints";
import type { PlanSections } from "@/api/planFormEndpoints";

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

/** One version of the plan with its window (§7.3 `versions[]`). */
export interface PlanEditVersion {
  version: number;
  /** `draft · scheduled · in_force · ended · corrected` (§7.3). */
  status: string;
  effective_from: string | null;
  effective_to: string | null;
}

export interface PlanEditRow {
  id: string;
  name: string;
  /** The PLAN's status — `draft · published · archived`. */
  status: string;
  /** The version in force today (`plan_version.version`), else the plan's. */
  version: number;
  /** The window of the version in force today. */
  effective_from: string | null;
  effective_to: string | null;
  /**
   * The figures the boxes open on, read from the SECTIONS — the version the
   * read answered for (`as_of`). ⚠ Never the top-level `minimum_bill_amount` /
   * `outside_city_percent`: those are `rate_plans` columns that mirror the
   * HEAD version, so once a v2 is filed from a later date they describe v2
   * while every section describes v1 (found on the walk, CR-167 §14).
   */
  minimum_bill_amount: string | null;
  outside_city_percent: string | null;
  /** Units assigned to the plan today — *N units move to v2* (image 41). */
  units: number | null;
  versions: PlanEditVersion[];
  sections: PlanSections;
}

export function normalisePlanEditRow(raw: unknown): PlanEditRow {
  const body = obj(raw) ?? {};
  const inForce = obj(body.plan_version);
  const versions = (Array.isArray(body.versions) ? body.versions : []).flatMap((item) => {
    const row = obj(item);
    const version = row === null ? null : int(row.version) ?? int(row.version_no);
    if (row === null || version === null) return [];
    return [
      {
        version,
        status: str(row.status) ?? "",
        effective_from: str(row.effective_from),
        effective_to: str(row.effective_to),
      },
    ];
  });
  const sections = normalisePlanSections(raw);
  return {
    id: str(body.id) ?? "",
    name: str(body.name) ?? sections.details.name,
    status: str(body.status) ?? "",
    version: (inForce === null ? null : int(inForce.version)) ?? int(body.version) ?? 1,
    effective_from: (inForce === null ? null : str(inForce.effective_from)) ?? str(body.effective_from),
    effective_to: inForce === null ? str(body.effective_to) : str(inForce.effective_to),
    minimum_bill_amount: sections.details.minimum_bill_display,
    outside_city_percent: sections.outside_city_surcharge?.percent_display.replace(/%$/, "") ?? null,
    units: int(body.units) ?? int(body.account_count) ?? int(body.accounts),
    versions,
    sections,
  };
}

function planPath(planId: string, tail = ""): string {
  return `/plans/${encodeURIComponent(planId)}${tail}`;
}

/** `asOf` — the day the plan is read AS OF (§7.3): the version in force that
 *  day and each item's version that day. `null` is the utility's today. */
export async function getPlanForEdit(planId: string, client: ApiClient = api, asOf: string | null = null): Promise<PlanEditRow> {
  const query: Record<string, string> = {};
  if (asOf !== null && asOf !== "") query.as_of = asOf;
  const response = await client.get<unknown>(planPath(planId), { query });
  return normalisePlanEditRow(response.data);
}

/** The start of the LATEST published version — what *Change from a date*
 *  copies from (`plan_writes.new_version` takes over from the version in
 *  force on the new start), when it starts after the one in force today. */
export function latestVersionStart(row: Pick<PlanEditRow, "versions" | "effective_from">): string | null {
  const starts = row.versions
    .filter((one) => one.status === "scheduled" || one.status === "in_force")
    .map((one) => one.effective_from ?? "")
    .filter((day) => day !== "")
    .sort();
  const last = starts[starts.length - 1] ?? null;
  return last !== null && last > (row.effective_from ?? "") ? last : null;
}

/** *Name and details* (a live plan: `details` only, same version) — or a
 *  draft's edit in place (anything). */
export async function patchPlan(planId: string, body: Record<string, unknown>, client: ApiClient = api): Promise<PlanEditRow> {
  const response = await client.patch<unknown>(planPath(planId), body);
  return normalisePlanEditRow(response.data);
}

/** *Change from a date* — *Save new version* (`publish: false`) or *Publish
 *  new version* (`publish: true`), one call (§7.3, DEF-RAT-9330). */
export async function newPlanVersion(planId: string, body: Record<string, unknown>, client: ApiClient = api): Promise<PlanEditRow> {
  const response = await client.post<unknown>(planPath(planId, "/versions"), body);
  return normalisePlanEditRow(response.data);
}

/** *Fix a mistake* — the named version restated, same number, same dates. */
export async function correctPlan(planId: string, body: Record<string, unknown>, client: ApiClient = api): Promise<PlanEditRow> {
  const response = await client.post<unknown>(planPath(planId, "/corrections"), body);
  return normalisePlanEditRow(response.data);
}

/** A draft's *Publish plan*, after its edit is saved in place. */
export async function publishDraftPlan(planId: string, client: ApiClient = api): Promise<PlanEditRow> {
  const response = await client.post<unknown>(planPath(planId, "/publish"));
  return normalisePlanEditRow(response.data);
}
