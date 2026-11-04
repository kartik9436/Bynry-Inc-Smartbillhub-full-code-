// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 3, lane RAISE — the raise and its two doors
//           (P2.2–P2.4, P2.15, P2.16, P2.18, P2.19), built from images 14–20 of
//           `05-prototype/work-backoffice-2026-10-04/images/`.
// Contract: CR-168 §7.3 — `GET /work/raise/assets`, `GET /work/candidates`,
//           `POST /work-orders/bulk-raise`, `GET /work/templates` with the
//           raise's filters. Served by lane SRV-2 in the same round; the names
//           here are the contract's and nothing is invented beside them.
// Tests:    src/features/work/raise/cr168Raise.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **A FILE OF ITS OWN, NOT ROWS IN `workEndpoints.ts`.** Four lanes write
// Work's screens this round, and `workEndpoints.ts` is the file every one of
// them reaches for; a pathspec commit takes the whole file (hard-won law 11).
// The raise's reads and its one write live here, beside the screen that
// calls them, and import the shared shapes they need from there.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import type { Paginated } from "@/api/paginated";
import type { UnitsPage } from "@/api/endpoints";

import { normaliseCandidates } from "../workEndpoints";
import type { CandidatePage, TemplateList } from "../workEndpoints";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** Only SET values travel (BR-SHL-011): an empty filter is absent, never `f.x=`. */
function compact(query: Record<string, string | number | undefined>) {
  const out: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") out[key] = value;
  }
  return out;
}

/** The units of ONE premises — `GET /units?f.premises_id=`, paged and searched
 *  on the server (NFR-3: a building of four hundred flats pages like any list). */
export async function listRaiseUnits(
  query: { premisesId: string; q?: string; unitType?: string; page?: number; per?: number },
  client: ApiClient = api,
): Promise<UnitsPage> {
  return requireData(
    await client.get<UnitsPage>("/units", {
      query: compact({
        "f.premises_id": query.premisesId,
        // Image 14's chips — SRV-2's `f.unit_type`, narrowed in SQL so the
        // list still pages there (NFR-3).
        "f.unit_type": query.unitType,
        q: query.q,
        page: query.page,
        per: query.per,
      }),
    }),
  );
}

/** `GET /units/unit-types` — the tenant's own unit-type words, readable by a
 *  clerk (`DEF-MET-5656`); image 14's chips are these, never a typed list. */
export async function listUnitTypeOptions(
  client: ApiClient = api,
): Promise<{ results: { code: string; name: string }[] }> {
  return requireData(await client.get<{ results: { code: string; name: string }[] }>("/units/unit-types"));
}

/** One asset on the ticked units — §7.3 `GET /work/raise/assets`. `unit.id`
 *  and `location`/`last_read` are read when served; the screen draws a dash
 *  for what is absent and never invents it. */
export interface RaiseAssetRow {
  id: string;
  asset_no: string;
  serial: string | null;
  type: { name: string } | null;
  service: { code: string; name: string } | null;
  unit: { id?: string; label: string | null } | null;
  premises: { address: string | null } | null;
  /** True when another asset of the type stands on the same unit (SRV-2). */
  shares_unit?: boolean;
  /** Where on site — *Front boundary box*. Optional on the wire. */
  location?: string | null;
  /** The last reading, already worded by the server — *2,546 kgal · 11 Aug*. */
  last_read?: { reading: string | null; unit: string | null; on: string | null } | null;
}

export async function listRaiseAssets(
  query: {
    unitIds: readonly string[];
    assetType: string;
    service?: string;
    q?: string;
    page?: number;
    per?: number;
  },
  client: ApiClient = api,
): Promise<Paginated<RaiseAssetRow>> {
  return requireData(
    await client.get<Paginated<RaiseAssetRow>>("/work/raise/assets", {
      query: compact({
        unit_ids: query.unitIds.join(","),
        asset_type: query.assetType,
        service: query.service,
        q: query.q,
        page: query.page,
        per: query.per,
      }),
    }),
  );
}

/** §7.3 `GET /work/candidates` — everybody a NEW job may be given, best fit
 *  first, paged and uncapped (NFR-5). The rows are the same shape as an
 *  order's candidates, so they are read by the same defensive reader
 *  (`normaliseCandidates`) the ASSIGN lane wrote. Advice only (ruling 2). */
export async function listRaiseCandidates(
  query: {
    templateId?: string;
    premisesId?: string;
    unitIds?: readonly string[];
    on?: string;
    q?: string;
    page?: number;
    per?: number;
  },
  client: ApiClient = api,
): Promise<CandidatePage> {
  const response = await client.get<unknown>("/work/candidates", {
    query: compact({
      template_id: query.templateId,
      premises_id: query.premisesId,
      unit_ids: (query.unitIds ?? []).join(","),
      on: query.on,
      q: query.q,
      page: query.page,
      per: query.per,
    }),
  });
  return normaliseCandidates(requireData(response));
}

/** Published templates for the raise, narrowed by what the job already knows. */
export async function listRaiseTemplates(
  query: { jobTypeId?: string; service?: string; assetType?: string; per?: number },
  client: ApiClient = api,
): Promise<TemplateList> {
  return requireData(
    await client.get<TemplateList>("/work/templates", {
      query: compact({
        // The job type picked on step 1 (a kind or its heading); a template
        // naming no job type is offered for every one (SRV-3, `DEF-WRK-9612`).
        "f.job_type": query.jobTypeId,
        "f.service": query.service,
        "f.asset_type": query.assetType,
        // Active and published only (SRV-2) — the server's word for what may
        // be raised, so a draft is never offered (BR-WRK-011).
        "f.raisable": 1,
        per: query.per ?? 100,
      }),
    }),
  );
}

export interface BulkRaiseBody {
  template_id: string;
  /** The job type's catalogue row — the promise (`BR-WRK-018`) needs it.
   *  Optional for a template that names no job type (P5.5's raise across
   *  buildings sends the template's words alone then). */
  type_id?: string;
  /** The job type's words — what the order's own `type` column reads. */
  type: string;
  /** Ruling 20 binds when the raise NAMES the type (SRV-2 judgment 8). */
  asset_type_id?: string;
  /** Absent on the raise ACROSS buildings (P5.5): each asset then names its
   *  own building by the walk asset → unit → premises (P2.20). */
  premises_id?: string;
  unit_ids?: string[];
  asset_ids?: string[];
  account_id?: string;
  priority_id: string | null;
  due_on: string | null;
  window_start: string | null;
  window_end: string | null;
  technician_notes: string | null;
  assignee: { technician_id: string } | { crew_id: string } | null;
  idempotency_key: string;
  /** CR-161 W4 — the utility's own answers, sent always (`{}` included): the
   *  server reads the key as "typed on New work order" (§5.7, N4). */
  custom_data: Record<string, unknown>;
  /** `BR-WRK-024` — who raised it: the office (`dispatcher`) or the Assets
   *  door (`assets`), which is what the order's RAISED BY reads. */
  source: "dispatcher" | "assets";
}

export interface BulkRaiseResult {
  unit_id: string | null;
  asset_id: string | null;
  /** SRV-2's appendix — the words image 18's Unit and Asset columns read. */
  unit?: { label: string | null } | null;
  asset?: { asset_no: string | null } | null;
  ok: boolean;
  id: string | null;
  order_no: string | null;
  /** A catalogue KEY, so the result says why in the reader's language. */
  reason: string | null;
}

export interface BulkRaiseOutcome {
  results: BulkRaiseResult[];
  done: number;
  failed: number;
}

/** §7.3 `POST /work-orders/bulk-raise` — one job per unit (or per asset), one
 *  savepoint per job on the server, and a repeated key returns the first
 *  answer, so a double press raises nothing twice. */
export async function bulkRaise(body: BulkRaiseBody, client: ApiClient = api): Promise<BulkRaiseOutcome> {
  return requireData(
    await client.post<BulkRaiseOutcome>("/work-orders/bulk-raise", body),
  );
}
