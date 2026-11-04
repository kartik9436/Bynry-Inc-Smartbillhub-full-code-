/**
 * `MeData` over the handset store — what the "me" screens read from the
 * tenant's SQLite file, through `db/queries` and `scoped()` (R133), and what
 * they write, through the outbox so an act and its key land together (R46).
 *
 * Time records (FF-47, FF-48): a clock is a `crew_time` row (R8: per person,
 * not per job; R9: travel and labour separate, both correctable). Starting,
 * stopping and correcting one is an OUTBOX act of kind `crew_time` whose
 * `apply` changes the row in the same transaction. That kind has no server
 * door yet (`N17`, `sync/outbox.ts UNROUTED_KINDS`): the act is captured,
 * kept and NOT sent until the door exists — nothing is lost while it waits.
 *
 * An admin entry's TASK (vehicle check, training …) is not a `crew_time`
 * column; it travels in the starting act's payload and is read back through
 * the row's `outbox_id`, so no schema change is needed to show it.
 */
import type { TenantDb } from '../../db/database';
import { fromJson } from '../../db/json';
import * as crewTime from '../../db/queries/crewTime';
import * as outboxQ from '../../db/queries/outbox';
import * as photoQ from '../../db/queries/photo';
import * as premiseQ from '../../db/queries/premise';
import * as routeQ from '../../db/queries/route';
import * as technicianQ from '../../db/queries/technician';
import * as syncState from '../../db/queries/syncState';
import * as workOrder from '../../db/queries/workOrder';
import { scoped, type ScopedRunner } from '../../db/scoped';
import { NEEDS_ATTENTION_AFTER } from '../../sync/backoff';
import { DELTA_TABLE } from '../../sync/delta';
import { capture, resendRefused } from '../../sync/outbox';
import { firstReason, reasonOfLastError, referenceOf } from '../../sync/syncReason';
import { ACCEPT_FIRST, keptForOfficeOf, readRefusal, refusalKeyOf, type RefusalReading } from './refusalGroups';
import { ADMIN_TASKS, type AdminTask, type Captor, type MeData, type RaisedItem, type RefusedItem, type StuckItem, type TimeEntry } from './services';

function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

function minutesBetween(a: string, b: string): number {
  return Math.max(0, Math.round((Date.parse(b) - Date.parse(a)) / 60_000));
}

function adminTaskOf(s: ScopedRunner, outboxId: string | null): AdminTask | null {
  if (!outboxId) return null;
  const row = outboxQ.getMine(s, outboxId);
  const task = fromJson<{ task?: string }>(row?.payload)?.task;
  return task && (ADMIN_TASKS as readonly string[]).includes(task) ? (task as AdminTask) : null;
}

function toEntry(s: ScopedRunner, row: crewTime.CrewTimeRow): TimeEntry {
  const order = row.work_order_id ? workOrder.getMine(s, row.work_order_id) : undefined;
  return {
    id: row.id,
    kind: row.kind,
    startedAt: row.started_at,
    endedAt: row.ended_at,
    workOrderId: row.work_order_id,
    workOrderNumber: order?.number ?? null,
    workOrderType: order?.type ?? null,
    adminTask: row.kind === 'admin' ? adminTaskOf(s, row.outbox_id) : null,
  };
}

function reasonOf(refusal: string | null): string {
  const r = fromJson<{ message?: unknown; reason?: unknown; code?: unknown }>(refusal);
  const text = r?.message ?? r?.reason ?? r?.code;
  return typeof text === 'string' && text.trim() !== '' ? text : '';
}

// `refusalKeyOf` moved beside the refusals' reading (DEF-FLD-10612); re-exported for its callers.
export { refusalKeyOf } from './refusalGroups';

export interface DbMeDataDeps {
  newId(): string;
}

export function createDbMeData(db: TenantDb, deps: DbMeDataDeps): MeData {
  const clockOf = (now: Date) => ({ now: () => now });

  function stopRunning(s: ScopedRunner, at: string): string | null {
    const running = crewTime.runningMine(s);
    if (!running) return null;
    crewTime.setTimes(s, running.id, running.started_at, at);
    return running.id;
  }

  return {
    wired: true,

    who(technicianId) {
      const row = technicianQ.get(db, technicianId);
      return row ? { role: row.role, employment: row.employment } : null;
    },

    firstOpenJob(technicianId, now) {
      const s = scoped(db, technicianId);
      const end = addDays(startOfDay(now), 1).toISOString();
      const row = workOrder.listDay(s, { before: end, limit: 1 })[0];
      if (!row) return null;
      const premise = row.premise_id ? premiseQ.get(db, row.premise_id) : undefined;
      const locality = [premise?.locality, [premise?.region, premise?.postal_code].filter(Boolean).join(' ')]
        .filter(Boolean)
        .join(', ');
      return {
        id: row.id,
        number: row.number,
        type: row.type,
        state: row.state,
        priority: row.priority_code,
        windowStart: row.window_start,
        windowEnd: row.window_end,
        address: premise?.address_line ?? null,
        locality: locality || null,
      };
    },

    today(technicianId, now) {
      const s = scoped(db, technicianId);
      const from = startOfDay(now);
      const to = addDays(from, 1);
      const entries = crewTime.listBetween(s, from.toISOString(), to.toISOString(), 500);
      const nowIso = now.toISOString();
      const worked = entries.reduce((n, e) => n + minutesBetween(e.started_at, e.ended_at ?? nowIso), 0);
      return {
        done: workOrder.countClosedBetween(s, from.toISOString(), to.toISOString()),
        left: workOrder.countOpenBefore(s, to.toISOString()),
        workedMinutes: worked,
      };
    },

    timesheet(technicianId, from, to) {
      const s = scoped(db, technicianId);
      return crewTime.listBetween(s, from.toISOString(), to.toISOString(), 500).map((row) => toEntry(s, row));
    },

    runningClock(technicianId) {
      const s = scoped(db, technicianId);
      const row = crewTime.runningMine(s);
      return row ? toEntry(s, row) : null;
    },

    startAdmin(captor: Captor, task, now) {
      const at = now.toISOString();
      const id = deps.newId();
      capture(
        db,
        captor,
        {
          kind: 'crew_time',
          payload: { action: 'start', crew_time_id: id, kind: 'admin', task, started_at: at },
          apply: (s, key) => {
            stopRunning(s, at);
            crewTime.insert(s, { id, workOrderId: null, personId: captor.technicianId, kind: 'admin', startedAt: at, outboxId: key });
          },
        },
        { newId: deps.newId, clock: clockOf(now) },
      );
    },

    stopClock(captor, now) {
      const at = now.toISOString();
      const s = scoped(db, captor.technicianId);
      const running = crewTime.runningMine(s);
      if (!running) return;
      capture(
        db,
        captor,
        {
          kind: 'crew_time',
          workOrderId: running.work_order_id,
          payload: { action: 'stop', crew_time_id: running.id, kind: running.kind, ended_at: at },
          apply: (inner) => {
            crewTime.setTimes(inner, running.id, running.started_at, at);
          },
        },
        { newId: deps.newId, clock: clockOf(now) },
      );
    },

    correct(captor, entryId, startedAt, endedAt, now) {
      if (endedAt !== null && Date.parse(endedAt) < Date.parse(startedAt)) {
        throw new RangeError('an entry cannot end before it starts');
      }
      capture(
        db,
        captor,
        {
          kind: 'crew_time',
          payload: { action: 'correct', crew_time_id: entryId, started_at: startedAt, ended_at: endedAt },
          apply: (s) => {
            if (crewTime.setTimes(s, entryId, startedAt, endedAt) !== 1) {
              throw new Error('no such time entry for this technician');
            }
          },
        },
        { newId: deps.newId, clock: clockOf(now) },
      );
    },

    syncCounts(technicianId) {
      const s = scoped(db, technicianId);
      const photos = photoQ.progressMine(s);
      const jobs = workOrder.bundleCounts(s);
      const state = syncState.get(s, DELTA_TABLE);
      const awaiting = photoQ.awaitingDeclarationMine(s);
      const routes = routeQ.countsMine(s);
      const reached = [state?.last_pull_at, state?.last_push_at].filter((x): x is string => !!x).sort();
      return {
        itemsWaiting: outboxQ.countUnsentMine(s),
        photosWaiting: photoQ.countWaitingMine(s),
        photosTotal: photos.total,
        photosUploaded: photos.uploaded,
        photoBytesLeft: photos.bytesLeft,
        jobsTotal: jobs.total,
        jobsReady: jobs.ready,
        lastReachedAt: reached.at(-1) ?? null,
        // DEF-FLD-10629 (I, J): photographs that cannot upload yet; the reader's routes.
        photosAwaitingRoute: awaiting.route,
        photosAwaitingJob: awaiting.job,
        routesTotal: routes.routes,
        routeMeters: routes.meters,
        // DEF-FLD-10624 (A): why the waiting items have not gone, from their own saved failure.
        waitingReason: firstReason(outboxQ.pendingErrorsMine(s).map(reasonOfLastError)),
      };
    },

    refused(technicianId) {
      const s = scoped(db, technicianId);
      const rows = outboxQ.needsAttentionMine(s, NEEDS_ATTENTION_AFTER).filter((row) => row.state === 'refused');
      const jobs = new Map<string, ReturnType<typeof workOrder.getMine>>();
      const jobOf = (id: string) => {
        if (!jobs.has(id)) jobs.set(id, workOrder.getMine(s, id));
        return jobs.get(id);
      };
      // DEF-FLD-10612: a job whose ACCEPT was refused — its work refused
      // *Accept the job first* says the accept's reason instead, with no button.
      const acceptRefusal = new Map<string, RefusalReading>();
      for (const row of rows) {
        if (row.kind !== 'job_accept' || !row.work_order_id) continue;
        acceptRefusal.set(row.work_order_id, readRefusal(row.refusal, jobOf(row.work_order_id)?.dispatch_state === 'cancelled'));
      }
      return rows.map<RefusedItem>((row) => {
        const job = row.work_order_id ? jobOf(row.work_order_id) : undefined;
        let reading = readRefusal(row.refusal, job?.dispatch_state === 'cancelled');
        const accept = row.work_order_id ? acceptRefusal.get(row.work_order_id) : undefined;
        if (accept && refusalKeyOf(row.refusal) === ACCEPT_FIRST) reading = { reasonKey: accept.reasonKey, action: 'none' };
        return {
          id: row.id,
          kind: row.kind,
          workOrderId: row.work_order_id,
          // DEF-FLD-10623: the number kept at capture first — a reassigned
          // job has left the phone, and the mirror's number went with it.
          workOrderNumber: row.work_order_number ?? job?.number ?? null,
          capturedAt: row.captured_at,
          reason: reasonOf(row.refusal),
          reasonKey: reading.reasonKey,
          action: reading.action,
          keptForOffice: keptForOfficeOf(row.refusal),
        };
      });
    },

    resend(technicianId, id) {
      return resendRefused(db, technicianId, id);
    },

    // FB-022 (DEF-FLD-10794): `backoff.ts` promised these "show on FF-50 as
    // needing attention" and `refused()` filtered them out. Photographs are
    // counted on their own line, so they are not listed here.
    needsAttention(technicianId) {
      const s = scoped(db, technicianId);
      return outboxQ
        .needsAttentionMine(s, NEEDS_ATTENTION_AFTER)
        .filter((row) => row.state === 'pending' && row.kind !== 'photo')
        .map<StuckItem>((row) => ({
          id: row.id,
          kind: row.kind,
          workOrderNumber: row.work_order_number ?? (row.work_order_id ? (workOrder.getMine(s, row.work_order_id)?.number ?? null) : null),
          capturedAt: row.captured_at,
          failures: row.attempts,
          reason: reasonOfLastError(row.last_error),
          reference: referenceOf(row.last_error),
        }));
    },

    retryNow(technicianId, id) {
      return outboxQ.retryNowMine(scoped(db, technicianId), id) === 1;
    },

    raised(technicianId, limit) {
      return outboxQ.raisesMine(scoped(db, technicianId), limit).map<RaisedItem>((row) => ({
        id: row.id,
        sent: row.state !== 'pending' && row.state !== 'sending' && row.state !== 'refused',
        refused: row.state === 'refused',
        capturedAt: row.captured_at,
        templateName: row.template_name,
        orderNo: row.order_no,
      }));
    },
  };
}
