// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-6350 — and the PO's second addition of 2026-09-23
//           (`OQ-CUS-12616` CLOSED, decision log *"RULED: THE MOVE-IN APPROVAL
//           FLOW, SIX STEPS"*): *after approval, the request page shows where it
//           went* — `Approved → Move-in MVI-26-0115`, as a LINK to the job.
// Rules:    B14 rule 31 (the job's human NUMBER, never its id — and where there
//           is no number, the words say so) · rule 43 (a component in its own
//           file; the page mounts it in one line) · rule 21 (Tailwind; on
//           route-b-migrated.txt) · hard-won law 2's mirror (a link only where
//           the destination is a screen that opens)
// Tests:    ServiceRequestDetailPage.dom.test.tsx (under the real route)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE FACT IS THE SERVER'S `header.job`, READ BACK ON EVERY LOAD** — never
// the approval's own response held in page state, which is gone the moment the
// clerk reloads. So the line a clerk sees next week is the line they saw at the
// press.
//
// ⚠ **WHERE EACH KIND LINKS, AND WHY THE BUILD SOMETIMES DOES NOT.**
//   * a MOVE-IN links to its own record, `/moves/{MVI-…}` — the screen the
//     Move-ins tab's row opens, and where the clerk lands after Approve;
//   * a BUILD links to the New connect wizard ONLY while it is a DRAFT
//     (`draftBuildPath`, the one builder of that address). Once submitted, a
//     build's home is its premises or account (`buildHomePath`), which this
//     payload does not carry — so the number is printed without a link rather
//     than pointing at `/connections/<id>`, a retired address `G93` refuses.
import { Link } from "react-router-dom";

import { Note } from "@/components/TextBits";
import { PREMISES_ROUTE } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { moveRecordPath } from "./MoveRecordPage";
import { draftBuildPath, isDraftBuild } from "./newConnectShared";
import type { ServiceRequestHeaderJob } from "./serviceRequestEndpoints";

type Translate = (key: string, params?: Record<string, unknown>) => string;

const NS = "customers.serviceRequest.approveChecks";

/** Where a job's own screen is, or `null` when it has none a clerk can open. */
export function jobPath(job: ServiceRequestHeaderJob): string | null {
  if (job.kind === "move_in") {
    return job.number !== null && job.number !== "" ? moveRecordPath(job.number) : null;
  }
  if (job.kind === "connection") {
    return job.id !== null && job.id !== "" && isDraftBuild(String(job.state ?? ""))
      ? draftBuildPath(job.id)
      : null;
  }
  return null;
}

/**
 * `DEF-CUS-9036` — **the other way to fulfil an approved move-in: the owner's
 * MASTER account** (PO ruling 2026-10-01, *"you will ahve to create regular or
 * master customer"*). An owner or a manager taking a whole building at an
 * address on file is a master account, not a tenant's move-in, and that
 * account is created on the property's Common areas tab. The link carries the
 * request, so the account takes the customer and class the clerk set on it and
 * the pending move-in job closes. `null` while the job is not a move-in or the
 * request names no property.
 */
export function ownerMasterPath(
  job: ServiceRequestHeaderJob,
  requestId: string | null | undefined,
  premisesId: string | null | undefined,
): string | null {
  if (job.kind !== "move_in" || !requestId || !premisesId) {
    return null;
  }
  const query = new URLSearchParams({ tab: "common-areas", request: requestId });
  return `${PREMISES_ROUTE}/${premisesId}?${query.toString()}`;
}

/** `BR-CUS-1114` — a premises with fewer than two live units takes no master
 *  account. `undefined`/`null` (not served, or no premises) is not a refusal. */
function singleUnit(units: number | null | undefined): boolean {
  return typeof units === "number" && units < 2;
}

export function ServiceRequestJobLink(props: {
  job: ServiceRequestHeaderJob | null | undefined;
  t: Translate;
  /** `DEF-CUS-9036` — the request's own id and its resolved property, for the
   *  owner's-master-account door. Both optional: every existing mount draws
   *  exactly what it drew. */
  requestId?: string | null;
  premisesId?: string | null;
  /** `BR-CUS-1114` — the resolved premises' live unit count. Below two the
   *  owner's-master-account door is shown CLOSED with its reason
   *  (BR-SHL-025). Omitted or `null`: the door draws as before. */
  premisesUnits?: number | null;
  /** `CR-162-BRC10` (Q1) — the SERVER's answer, read off the premises type's
   *  *Account type*. When given it decides; absent, the unit count decides as
   *  on 2.442.0. */
  masterAllowed?: boolean | null;
}) {
  const tenantPath = useTenantPath();
  const job = props.job;
  if (job === null || job === undefined || (job.kind !== "move_in" && job.kind !== "connection")) {
    return null;
  }
  const words =
    job.number !== null && job.number !== ""
      ? props.t(`${NS}.approvedTo.${job.kind}`, { number: job.number })
      : props.t(`${NS}.approvedToUnnumbered.${job.kind}`);
  const path = jobPath(job);
  const masterPath = ownerMasterPath(job, props.requestId, props.premisesId);
  const closed =
    typeof props.masterAllowed === "boolean" ? !props.masterAllowed : singleUnit(props.premisesUnits);
  const byType = typeof props.masterAllowed === "boolean";
  return (
    <p className="my-4 flex flex-wrap gap-4 text-md" data-request-job={job.kind} role="status">
      {path === null ? (
        <span className="font-semibold text-neutral-900">{words}</span>
      ) : (
        <Link
          to={tenantPath(path)}
          className="font-semibold text-accent underline underline-offset-2"
          data-request-job-link={job.number ?? ""}
        >
          {words}
        </Link>
      )}
      {masterPath !== null && closed && (
        // `BR-CUS-1114` (PO 2026-10-02) — no master account on a single unit;
        // the applicant's move-in opens a regular one. The server refuses too.
        <span className="text-neutral-700" data-request-owner-master-closed="">
          {props.t(`${NS}.ownerMaster`)}{" "}
          <Note as="span">
            {byType
              ? props.t("customers.account.master_not_for_single_family", {
                  defaultValue:
                    "Single-family homes have no master account. Open a regular account at Move-in.",
                })
              : props.t("customers.account.master_needs_two_units", {
                  defaultValue: "Single unit. Open a regular account.",
                })}
          </Note>
        </span>
      )}
      {masterPath !== null && !closed && (
        <Link
          to={tenantPath(masterPath)}
          className="font-semibold text-accent underline underline-offset-2"
          data-request-owner-master=""
        >
          {props.t(`${NS}.ownerMaster`)}
        </Link>
      )}
    </p>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-6350 · OQ-CUS-12616 (CLOSED) · B14 rules 21, 31, 43
// generated: 2026-09-23 by lane APPROVE-CHECKS
// checklist: A=n/a B✔ C✔ D✔(header.job) E✔(ServiceRequestDetailPage mounts it) F✔ G✔ H=n/a
// gates: tsc · vitest ServiceRequestDetailPage.dom.test.tsx · routeBUtilities
// exceptions: a submitted build prints its number without a link — its home is not on this payload
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
