// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 4, lane CREWS — P3.27 (Add a crew), P3.43 (Add
//           crew member), P3.45 (a technician's Jobs), P3.48 (Certifications
//           as a table), P3.49 (Crews as three lists); rulings 26, 27, 28, 30,
//           31 (images 25–34).
// Contract: CR-168-BRC10 §7.3 and §16 (lane SRV-3, `2.502.0`). Every type here
//           is checked by `tsc` against a RECORDED server answer in
//           `__fixtures__/server/` (`crewsRecordedShapes.typecheck.ts`) — the
//           fixtures come from the server and are never hand-typed (§7).
// ───────────────────────────────────────────────────────
//
// ⚠ **A FILE OF ITS OWN RATHER THAN MORE OF `workEndpoints.ts`.** That file is
// 2,900 lines that three round-4 lanes read and two of them write; the reads
// below belong to the Crews screens alone, so they live beside them and no
// other lane's hunk can collide with them. `listCrews` (the one-table answer)
// stays where it is because the raise and the Orders filter still read it.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import type { Paginated } from "@/api/paginated";

import type {
  CertificateProof,
  HeldCertification,
  HeldSkill,
  TechnicianDetail,
  TechnicianStatus,
  WorkOrderDispatchRow,
} from "./workEndpoints";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

function blank(value: string | undefined): string | undefined {
  return value === undefined || value === "" ? undefined : value;
}

/** Ruling 30 — the Crews page is THREE lists. */
export type CrewsView = "technicians" | "crews" | "contractors";

/** A row of the Technicians list (image 25). */
export interface TechnicianListRow {
  id: string;
  kind: "person";
  name: string;
  slug: string;
  /** The *Job title* column — what the add form calls *Job title*. */
  role_label: string | null;
  crew: { id: string; name: string } | null;
  skills: HeldSkill[];
  certifications: HeldCertification[];
  shift: string | null;
  /** FB-033 — `on_break` / `off_duty` are what the technician said on the
   *  phone; `off_today` is End shift's. */
  status: TechnicianStatus;
  /** FB-033 — when the status took its value, in the utility's zone; null = not known. */
  status_since?: string | null;
  /** FB-033 (D4 = B) — off today because End shift still holds it. */
  shift_ended?: boolean;
  unavailable_reason: string | null;
  phone: string | null;
  email: string | null;
}

/** A row of the Crews list (image 27) or the Contractors list (image 28). */
export interface CrewListRow {
  id: string;
  kind: "crew" | "contractor";
  name: string;
  slug: string;
  /** A crew's *Does* — *Network crew*. */
  role_label: string | null;
  /** Counted on the server (`COUNT(*)`), never from a page of names. */
  members: number;
  /** Image 27's *D. Ortiz · R. Patel* — the members by name (lane SRV-4).
   *  Empty for a contractor (ruling 36). */
  member_names: string[];
  crew: null;
  skills: HeldSkill[];
  certifications: HeldCertification[];
  /** A contractor's set hours, or null for *By arrangement*. */
  shift: string | null;
  status: "crew" | "contractor";
  unavailable_reason: null;
  phone: string | null;
  email: string | null;
  active: boolean;
}

export interface CrewsViewCounts {
  technicians: number;
  crews: number;
  contractors: number;
}

export interface CrewsViewPage<Row> extends Paginated<Row> {
  /** The three tab badges — over the whole utility, never the page. */
  counts: CrewsViewCounts;
}

export interface CrewsViewQuery {
  q?: string;
  page?: number;
  per?: number;
  sort?: string;
  dir?: "asc" | "desc";
}

/** `GET /work/crews?view=…` — one list, cut in SQL (P3.4, ruling 30). */
export async function listCrewsView<Row = TechnicianListRow | CrewListRow>(
  view: CrewsView,
  query: CrewsViewQuery = {},
  client: ApiClient = api,
): Promise<CrewsViewPage<Row>> {
  return requireData(
    await client.get<CrewsViewPage<Row>>("/work/crews", {
      query: {
        view,
        q: blank(query.q),
        page: query.page,
        per: query.per,
        sort: query.sort,
        dir: query.dir,
      },
    }),
  );
}

/** One login on the *Person* picker of Add crew member (image 26). */
export interface StaffChoice {
  user_id: string;
  full_name: string | null;
  email: string;
  /** A CODE — rendered through the catalogue, never raw. */
  role_code: string;
  status: "active" | "invited" | "deactivated";
  has_profile: boolean;
  /** The person's technician profile, when they have one (lane SRV-4). */
  technician_id: string | null;
  /** Image 26's *on Field crew A* — the crew this login is on now, or null. */
  crew: { id: string; name: string } | null;
}

/** `GET /work/technicians?q=&page=&per=` — the logins that could be a crew
 *  member, PAGED on the server since lane SRV-4 (NFR-3). The picker filters on
 *  the client, so it asks for 200 by name — the crews picker's figure. */
export async function listStaffChoices(client: ApiClient = api): Promise<Paginated<StaffChoice>> {
  return requireData(
    await client.get<Paginated<StaffChoice>>("/work/technicians", { query: { page: 1, per: 200 } }),
  );
}

export interface CrewWrite {
  name: string;
  kind: "crew" | "contractor";
  role_label?: string;
  shift_start?: string | null;
  shift_end?: string | null;
  phone?: string;
  email?: string;
}

/** `POST /work/crews` — add a crew or a contractor (images 29, 30). */
export async function createCrew(body: CrewWrite, client: ApiClient = api): Promise<CrewListRow> {
  return requireData(await client.post<CrewListRow>("/work/crews", body));
}

/** `PUT /work/crews/{id}/skills` — a REPLACE (P3.52). */
export async function setCrewSkills(
  crewId: string,
  skills: { skill_id: string; proficiency?: "trained" | "certified" }[],
  client: ApiClient = api,
): Promise<CrewListRow> {
  return requireData(await client.put<CrewListRow>(`/work/crews/${crewId}/skills`, { skills }));
}

/** `POST /work/crews/{id}/members` — ruling 26. `{user_id}` makes a profile
 *  for a login that has none and puts it on the crew; one that has a profile
 *  moves. The answer is the crew with its counted `members`. */
export async function addCrewMember(
  crewId: string,
  body: {
    user_id: string;
    role_label?: string;
    shift_start?: string | null;
    shift_end?: string | null;
    van?: string;
  },
  client: ApiClient = api,
): Promise<CrewListRow> {
  return requireData(await client.post<CrewListRow>(`/work/crews/${crewId}/members`, body));
}

/** `POST /work/technicians` — a profile beside a login, on no crew. */
export async function createTechnician(
  body: {
    user_id: string;
    role_label?: string;
    shift_start?: string | null;
    shift_end?: string | null;
    van?: string;
  },
  client: ApiClient = api,
): Promise<TechnicianDetail> {
  return requireData(await client.post<TechnicianDetail>("/work/technicians", body));
}

/** `PATCH /work/technicians/{slug} {crew_id}` — P3.44, a move. */
export async function moveTechnician(
  slug: string,
  crewId: string | null,
  client: ApiClient = api,
): Promise<TechnicianDetail> {
  return requireData(
    await client.patch<TechnicianDetail>(`/work/technicians/${slug}`, { crew_id: crewId }),
  );
}

/** `PUT /work/technicians/{slug}/certifications` — a REPLACE of the whole set,
 *  which is how Add certification and Renew write one row (image 33). */
export async function setTechnicianCertifications(
  slug: string,
  certifications: { certification_type_id: string; expires_on: string | null }[],
  client: ApiClient = api,
): Promise<TechnicianDetail> {
  return requireData(
    await client.put<TechnicianDetail>(`/work/technicians/${slug}/certifications`, {
      certifications,
    }),
  );
}

/** The kinds and the ceiling `work/certificate_proof.py` accepts — checked here
 *  only so a clerk hears it BEFORE the upload; the server is the guard. */
export const PROOF_CONTENT_TYPES = ["application/pdf", "image/png", "image/jpeg"] as const;
export const PROOF_MAX_BYTES = 10 * 1024 * 1024;

/** `POST /work/technicians/{slug}/certifications/{type_id}/proof` — image 33's
 *  PROOF: the certificate's scan (multipart `file`). A renewal keeps it; a new
 *  upload replaces the pointer (lane SRV-4, `tenancy/0060`). */
export async function uploadCertificateProof(
  slug: string,
  certificationTypeId: string,
  file: File,
  client: ApiClient = api,
): Promise<CertificateProof> {
  const body = new FormData();
  body.append("file", file);
  return requireData(
    await client.post<CertificateProof>(
      `/work/technicians/${slug}/certifications/${certificationTypeId}/proof`,
      body,
    ),
  );
}

/** A row of a technician's Jobs tab (image 32): the dispatcher's own row. */
export interface TechnicianJobRow extends WorkOrderDispatchRow {
  /** False for a job that has since moved to somebody else. */
  still_holds: boolean;
  /** The office's acceptance of a finished job; null until accepted. */
  accepted?: { at: string | null; by: { name: string } | null } | null;
  /** The promise a job with no due date is measured against (PO answer 1). */
  sla?: { due_at: string | null; target: string; at_risk: boolean } | null;
  /** Image 32's CLOSED — when the field closed it; null on a job still out
   *  (served since lane SRV-4). */
  completed_at: string | null;
}

export type TechnicianJobState = "all" | "open" | "done";

/** `GET /work/technicians/{slug}/jobs?f.state=&q=&page=&per=` — P3.45. */
export async function listTechnicianJobs(
  slug: string,
  query: { state: TechnicianJobState; q?: string; page?: number; per?: number },
  client: ApiClient = api,
): Promise<Paginated<TechnicianJobRow>> {
  return requireData(
    await client.get<Paginated<TechnicianJobRow>>(`/work/technicians/${slug}/jobs`, {
      query: {
        "f.state": query.state === "all" ? undefined : query.state,
        q: blank(query.q),
        page: query.page,
        per: query.per,
      },
    }),
  );
}

/** Performance's arithmetic, for a period or one job type (image 34). */
export interface PerformanceFigures {
  closed: number;
  on_time: number;
  on_time_of: number;
  /** A decimal STRING — `"100.0"` — or null where nothing was closed. */
  first_visit_pct: string | null;
  vs_estimate_pct: string | null;
  vs_estimate_minutes: number | null;
}

export interface PerformanceByJobType extends PerformanceFigures {
  job_type: string | null;
  volume: number;
}

export interface TechnicianPerformance extends Paginated<PerformanceByJobType> {
  /** `YYYY-MM`, `YYYY`, or `""` for every closed job. */
  period: string;
  technician: { name: string; slug: string };
  tiles: PerformanceFigures;
}

/** `GET /work/technicians/{slug}/performance?period=&page=&per=` — P3.46. */
export async function getTechnicianPerformance(
  slug: string,
  query: { period: string; page?: number; per?: number },
  client: ApiClient = api,
): Promise<TechnicianPerformance> {
  return requireData(
    await client.get<TechnicianPerformance>(`/work/technicians/${slug}/performance`, {
      query: { period: blank(query.period), page: query.page, per: query.per },
    }),
  );
}
