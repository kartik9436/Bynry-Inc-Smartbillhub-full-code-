/**
 * The retention purge (T-11). Runs ON APP START, NEVER ON A TIMER, so it can
 * never run mid-upload (R63). Nothing in `src/sync/` imports this file, and
 * `purge.test.ts` fails if anything schedules it.
 *
 * ⚠ THE RULE WITH NO EXCEPTION (R60, PO ruled; requirement 48):
 *   "Nothing unsent is ever purged — at any age, under any sign-in, including
 *    another technician's work."
 * So every delete below names what it MAY take — settled outbox rows, photo
 * rows whose bytes the server confirmed, a closed job or turned-in route with
 * nothing unsent left in it — and nothing else. `refused` counts as unsent: it
 * waits for a person, whatever its age (Mobile data §10 rule 2).
 *
 * The figures are the design's (R62, Mobile data §7): sent work 7 days, closed
 * jobs and turned-in routes 14 days, documents to a 200 MB cap, oldest first —
 * and, from FB-030 (PO 2026-10-31, *"keep photos only for 3 days"*), a
 * photograph's FILE 3 days after its job closed or its route was turned in,
 * only once the server confirmed the bytes. The file used to go on receipt
 * (R61, SUPERSEDED in part); the ROW stays with its record for the 14 days,
 * and the record loads the picture from the server on tap.
 * They are OUR numbers, not the utility's (Security §7 item 4), so they are
 * options rather than constants buried in a query.
 *
 * Each cascade is ONE transaction (Mobile data §10 rule 3: "a half-deleted job
 * is worse than a stale one").
 */
import type { TenantDb } from './database';
import * as activityQ from './queries/activity';
import * as assetQ from './queries/asset';
import * as crewTimeQ from './queries/crewTime';
import * as documentQ from './queries/document';
import * as outboxQ from './queries/outbox';
import * as photoQ from './queries/photo';
import * as routeQ from './queries/route';
import * as searchQ from './queries/searchIndex';
import * as workOrderQ from './queries/workOrder';
import * as woItemQ from './queries/woItem';
import * as woReadingQ from './queries/woReading';
import { dropRouteIfSettled } from './routeDrop';
import { deviceWide, scoped } from './scoped';

const DAY_MS = 24 * 60 * 60 * 1000;

export const RETENTION = {
  sentDays: 7,
  closedDays: 14,
  /** FB-030 — a photo's file, from its job's close or its route's turn-in. */
  photoFileDays: 3,
  documentCapBytes: documentQ.DOCUMENT_CAP_BYTES,
} as const;

export interface PurgeFiles {
  delete(path: string): Promise<void>;
}

export interface PurgeOptions {
  now: Date;
  files: PurgeFiles;
  sentDays?: number;
  closedDays?: number;
  photoFileDays?: number;
  documentCapBytes?: number;
}

export interface PurgeReport {
  outboxRows: number;
  photoRows: number;
  /** FB-030 — photograph files deleted at 3 days (their rows stay). */
  photoFiles: number;
  closedJobs: number;
  closedJobsKeptForUnsentWork: number;
  routes: number;
  routesKeptForUnsentWork: number;
  documentsEvicted: number;
  assets: number;
}

function before(now: Date, days: number): string {
  return new Date(now.getTime() - days * DAY_MS).toISOString();
}

/** Call once, when the app starts. */
export async function purgeOnAppStart(db: TenantDb, opts: PurgeOptions): Promise<PurgeReport> {
  const purge = deviceWide(db, 'purge');
  const sentCutoff = before(opts.now, opts.sentDays ?? RETENTION.sentDays);
  const closedCutoff = before(opts.now, opts.closedDays ?? RETENTION.closedDays);
  const report: PurgeReport = {
    outboxRows: 0,
    photoRows: 0,
    photoFiles: 0,
    closedJobs: 0,
    closedJobsKeptForUnsentWork: 0,
    routes: 0,
    routesKeptForUnsentWork: 0,
    documentsEvicted: 0,
    assets: 0,
  };

  // 0 · FB-030 — photograph FILES, 3 days after the close or the turn-in, and
  // only once the server confirmed the bytes. The file first, then the mark:
  // a delete that throws leaves the row saying the file is here, and the next
  // start tries again (Mobile data §10's order).
  const photoCutoff = before(opts.now, opts.photoFileDays ?? RETENTION.photoFileDays);
  for (;;) {
    const due = photoQ.photoFilesDue(purge, photoCutoff, 50, sentCutoff);
    if (due.length === 0) break;
    for (const p of due) {
      if (p.local_path) await opts.files.delete(p.local_path);
      photoQ.markFileDeleted(purge, p.id);
      report.photoFiles += 1;
    }
  }

  // 1 · Closed jobs, 14 days on — the whole job or none of it.
  for (const job of workOrderQ.closedBefore(purge, closedCutoff)) {
    const s = scoped(db, job.technician_id);
    const target = { workOrderId: job.id };
    const orphans: string[] = [];
    const done = db.transaction(() => {
      if (outboxQ.unsentFor(s, target) > 0 || photoQ.unsentFor(s, target) > 0) return false;
      orphans.push(...photoQ.keptFilesFor(s, target));
      activityQ.deleteSettledForOrder(s, job.id);
      crewTimeQ.deleteSettledForOrder(s, job.id);
      photoQ.deleteUploadedFor(s, target);
      outboxQ.deleteSettledFor(s, target);
      woItemQ.deleteForOrder(s, job.id);
      woReadingQ.deleteForOrder(s, job.id);
      searchQ.remove(s, 'work_order', job.id);
      workOrderQ.deleteMine(s, job.id);
      return true;
    });
    for (const path of orphans) await opts.files.delete(path);
    if (done) report.closedJobs += 1;
    else report.closedJobsKeptForUnsentWork += 1;
  }

  // 2 · Turned-in routes, 14 days on — stops and reads go together.
  for (const r of routeQ.turnedInBefore(purge, closedCutoff)) {
    const s = scoped(db, r.technician_id);
    // The one route-drop rule, shared with the route download (DEF-FLD-10592).
    const orphans: string[] = [];
    const done = db.transaction(() => dropRouteIfSettled(s, r.id, orphans));
    for (const path of orphans) await opts.files.delete(path);
    if (done) report.routes += 1;
    else report.routesKeptForUnsentWork += 1;
  }

  // 3 · Sent work, 7 days on. Settled rows only.
  report.outboxRows = db.transaction(() => outboxQ.deleteSettledBefore(purge, sentCutoff));

  // 4 · Photo rows whose bytes the server confirmed and whose file is gone.
  report.photoRows = db.transaction(() => photoQ.deleteUploadedBefore(purge, sentCutoff));

  // 5 · Meters no job or route on the handset names any more.
  report.assets = db.transaction(() => assetQ.deleteOutOfScope(purge));

  // 6 · Documents above the cap, oldest-used first, skipping anything in scope.
  const cap = opts.documentCapBytes ?? RETENTION.documentCapBytes;
  let cached = documentQ.cachedBytes(db);
  while (cached > cap) {
    const batch = documentQ.evictionCandidates(purge, 20);
    if (batch.length === 0) break;
    for (const d of batch) {
      if (cached <= cap) break;
      if (d.local_path) await opts.files.delete(d.local_path);
      documentQ.markEvicted(purge, d.id);
      cached -= d.bytes;
      report.documentsEvicted += 1;
    }
  }

  return report;
}
