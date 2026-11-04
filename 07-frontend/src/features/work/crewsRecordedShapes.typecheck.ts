// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 4, lane CREWS — `tsc` compares every server
//           answer the Crews screens read with the type they read it through.
// Rules:    CR-168 §7 *"Fixtures come from the server"* · the pattern of
//           `recordedServerShapes.typecheck.ts` (lane SHAPE-SWEEP), whose
//           `Wire<T>` widens literal unions only.
// ───────────────────────────────────────────────────────
//
// Every JSON here is RECORDED by `10-scripts/cr168_capture_work_shapes.py` from
// `runserver` on PostgreSQL. A field the screen's type requires and the server
// does not send — or sends in another shape — fails `tsc` here, before any
// screen can crash on it (`DEF-WRK-9600`'s lesson).
import type { Paginated } from "@/api/paginated";
import type { LookupEntry } from "@/api/endpoints";

import type {
  CrewListRow,
  CrewsViewPage,
  StaffChoice,
  TechnicianJobRow,
  TechnicianListRow,
  TechnicianPerformance,
} from "./crewsEndpoints";
import type { TechnicianDetail } from "./workEndpoints";
import type { Wire } from "./recordedServerShapes.typecheck";

import TECHNICIANS from "./__fixtures__/server/work.crews.technicians.json";
import CREWS from "./__fixtures__/server/work.crews.crews.json";
import CONTRACTORS from "./__fixtures__/server/work.crews.contractors.json";
import TECHNICIAN from "./__fixtures__/server/work.technician.json";
import STAFF from "./__fixtures__/server/work.technicians.json";
import JOBS from "./__fixtures__/server/work.technician.jobs.json";
import JOBS_OPEN from "./__fixtures__/server/work.technician.jobs.open.json";
import JOBS_DONE from "./__fixtures__/server/work.technician.jobs.done.json";
import PERFORMANCE_ALL from "./__fixtures__/server/work.technician.performance.json";
import PERFORMANCE from "./__fixtures__/server/work.technician.performance.month.json";
import SKILLS from "./__fixtures__/server/work.lookups.work_skills.json";
import CERT_TYPES from "./__fixtures__/server/work.lookups.certification_types.json";

export const recordedCrews = {
  technicians: TECHNICIANS satisfies Wire<CrewsViewPage<TechnicianListRow>>,
  crews: CREWS satisfies Wire<CrewsViewPage<CrewListRow>>,
  contractors: CONTRACTORS satisfies Wire<CrewsViewPage<CrewListRow>>,
  technician: TECHNICIAN satisfies Wire<TechnicianDetail>,
  staff: STAFF satisfies Wire<Paginated<StaffChoice>>,
  jobs: JOBS satisfies Wire<Paginated<TechnicianJobRow>>,
  jobsOpen: JOBS_OPEN satisfies Wire<Paginated<TechnicianJobRow>>,
  jobsDone: JOBS_DONE satisfies Wire<Paginated<TechnicianJobRow>>,
  performance: PERFORMANCE satisfies Wire<TechnicianPerformance>,
  performanceAll: PERFORMANCE_ALL satisfies Wire<TechnicianPerformance>,
  skills: SKILLS satisfies Wire<Paginated<Pick<LookupEntry, "id" | "name" | "active">>>,
  certificationTypes: CERT_TYPES satisfies Wire<Paginated<Pick<LookupEntry, "id" | "name" | "active">>>,
};
