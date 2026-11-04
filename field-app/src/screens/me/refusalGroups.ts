/**
 * FF-50's refusals, read for WHAT THE TECHNICIAN CAN DO about each one, and
 * grouped by job and reason (DEF-FLD-10612, PO beta MQ-027: *"WO-0028 · 13
 * items · This job was reassigned."*).
 *
 * Before this every refused item was its own row with *Fix and send again* —
 * thirteen rows for one job the dispatcher had moved, each with a button that
 * could not fix it. Now each reason carries its own act:
 *
 *  - **the job has gone from this technician** — reassigned (the server answers
 *    a job that is no longer theirs with a 404, `mobile._own_job_or_404`, or
 *    `work.mobile.not_your_job`), cancelled (`work.sync.job_cancelled`, or the
 *    accept's `work.mobile.job_finished` on a job the feed says is cancelled),
 *    or declined (`work.mobile.job_already_declined`): NO button. Nothing on
 *    the phone can change it. The items stay here, never dropped (R48).
 *  - ⚠ **AND FROM 2026-10-26 THE SERVER ALSO KEEPS A COPY FOR THE OFFICE**
 *    (PO *"store on both"*, `CR-194-BRC10`) — it was *"nothing is stored"*
 *    (2026-10-21) until then, which is why this file promised nothing. A
 *    refusal whose answer carries `kept_for_office: true` is stored with that
 *    flag in `outbox.refusal` (no handset migration), and the row adds *The
 *    office will review this.* ONLY when every item behind it carries it —
 *    a copy the server failed to write is answered without the flag, so the
 *    sentence is never a promise nobody kept. The job's refused ACCEPT is not
 *    asked: it is the row's cause, not its work, and its door keeps no copy
 *    (DEF-FLD-10623 — asking it meant the sentence could never appear).
 *  - **the capture credential** (`work.mobile.capture_token_*`): *Sign in
 *    again*, and the group goes again once a fresh credential exists.
 *  - **the server could not apply it just now** (`work.sync.item_not_applied`,
 *    or a 5xx / 408 / 429 kept as a refusal), **or refused a time ahead of
 *    its clock** (`CLOCK_REFUSALS`, FB-014): *Send again*, the whole group.
 *  - **anything else**: *Fix and send again*, per item, as before.
 *
 * And the job's work refused *Accept the job first* when the ACCEPT itself was
 * refused shows the accept's reason — the real one — and no button.
 */
import { fromJson } from '../../db/json';

/**
 * The catalogue key to show a refusal in. The reads door answers
 * `message_key: work.mobile.reads.<reason>` (top level, or inside `detail`);
 * the handset carries those words as `field.reads.refused.<reason>`
 * (`i18n/keys/refusals.en.json`). ANY OTHER server key is returned as it is
 * (DEF-FLD-10579): the catalogue carries the server's own refusal sentences
 * (`i18n/catalogues.ts`, `work.*`), so *Accept the job first.* shows as words
 * and not as `accept_the_job_first`. FF-50 shows the key's sentence where the
 * catalogue has one and the server's reason as it gave it where not.
 */
export function refusalKeyOf(refusal: string | null): string | null {
  const r = fromJson<{ message_key?: unknown; detail?: { message_key?: unknown } | null; body?: { message_key?: unknown } | null }>(refusal);
  const key =
    typeof r?.message_key === 'string'
      ? r.message_key
      : typeof r?.detail?.message_key === 'string'
        ? r.detail.message_key
        : typeof r?.body?.message_key === 'string'
          ? r.body.message_key
          : null;
  if (!key) return null;
  const m = /^work\.mobile\.reads\.([a-z0-9_]+)$/.exec(key);
  return m ? `field.reads.refused.${m[1]}` : key;
}

export type RefusalAction = 'none' | 'signIn' | 'sendAgain' | 'fix';

/** True when the server said it kept a copy for the office — `kept_for_office`
 *  on the refusal itself (the job door's `detail`) or inside its `detail`
 *  (the reads door's answer, as `batchAnswerFromReads` stores it). */
export function keptForOfficeOf(refusal: string | null): boolean {
  const r = fromJson<{ kept_for_office?: unknown; detail?: { kept_for_office?: unknown } | null }>(refusal);
  return r?.kept_for_office === true || r?.detail?.kept_for_office === true;
}

export interface RefusalReading {
  /** The catalogue key to say it in, or null (then the server's text). */
  reasonKey: string | null;
  action: RefusalAction;
}

export const ACCEPT_FIRST = 'work.mobile.accept_the_job_first';

/**
 * FB-014 (DEF-FLD-10639): the server once refused a time AHEAD of its own
 * clock — a phone running fast. Nothing on the phone fixes that, so these are
 * *Send again*, never *Fix and send again*: this build sends its clock with
 * every call and the server shifts the time instead of refusing it
 * (`sync/deviceClock.ts`), so the resend goes through. Items refused before
 * the update are still on phones with exactly these keys.
 */
export const CLOCK_REFUSALS: ReadonlySet<string> = new Set([
  'work.labour.moment_in_future',
  'work.raise.captured_in_future',
  'work.shifts.future_day',
]);

export const JOB_GONE = {
  reassigned: 'field.ff50.refused.reassigned',
  cancelled: 'field.ff50.refused.cancelled',
  declined: 'field.ff50.refused.declined',
} as const;

interface Stored {
  message_key?: unknown;
  status?: unknown;
  detail?: { message_key?: unknown; status?: unknown } | null;
  body?: { message_key?: unknown } | null;
}

function serverKey(refusal: string | null): string | null {
  const r = fromJson<Stored>(refusal);
  const key = r?.message_key ?? r?.detail?.message_key ?? r?.body?.message_key;
  return typeof key === 'string' ? key : null;
}

function statusOf(refusal: string | null): number | null {
  const r = fromJson<Stored>(refusal);
  const status = r?.status ?? r?.detail?.status;
  return typeof status === 'number' ? status : null;
}

/** What a refusal means for the technician. `jobCancelled`: the feed says the job is cancelled. */
export function readRefusal(refusal: string | null, jobCancelled = false): RefusalReading {
  const key = serverKey(refusal);
  const status = statusOf(refusal);
  if (key === 'work.mobile.job_already_declined') return { reasonKey: JOB_GONE.declined, action: 'none' };
  if (key === 'work.sync.job_cancelled') return { reasonKey: JOB_GONE.cancelled, action: 'none' };
  if (key === 'work.mobile.job_finished') {
    return { reasonKey: jobCancelled ? JOB_GONE.cancelled : key, action: 'none' };
  }
  if (key === 'work.mobile.not_your_job' || status === 404) return { reasonKey: JOB_GONE.reassigned, action: 'none' };
  if (key?.startsWith('work.mobile.capture_token_')) return { reasonKey: key, action: 'signIn' };
  if (
    key === 'work.sync.item_not_applied' ||
    (key !== null && CLOCK_REFUSALS.has(key)) ||
    (status !== null && (status >= 500 || status === 408 || status === 429))
  ) {
    return { reasonKey: key, action: 'sendAgain' };
  }
  return { reasonKey: refusalKeyOf(refusal), action: 'fix' };
}

export interface GroupableRefusal {
  id: string;
  /** The outbox kind — a refused `job_accept` is the group's CAUSE, not its work. */
  kind?: string;
  workOrderId?: string | null;
  workOrderNumber: string | null;
  reason: string;
  reasonKey?: string | null;
  action?: RefusalAction;
  /** The server kept a copy for the office (CR-194-BRC10). */
  keptForOffice?: boolean;
}

export interface RefusalGroup<T extends GroupableRefusal> {
  /** Stable for a render: the first item's id. */
  id: string;
  workOrderNumber: string | null;
  reason: string;
  reasonKey: string | null;
  action: RefusalAction;
  /** Every WORK item behind the row was kept for the office — only then may it say so. */
  keptForOffice: boolean;
  /** Everything behind the row, the cause included — what *Send again* sends. */
  items: T[];
  /** The work the row counts: every item but the cause. */
  work: T[];
  /** The job's refused accept, when the job has gone from the technician
   *  (reassigned · cancelled · declined): the REASON the work came back, not
   *  work — counted nowhere, and never asked whether the office kept it,
   *  because the accept door keeps no office copy (DEF-FLD-10623). */
  cause: T | null;
}

/** A refused accept on a job that has gone: the cause of its group, not an item of it. */
export function isCause(item: GroupableRefusal): boolean {
  return item.kind === 'job_accept' && (item.action ?? 'fix') === 'none';
}

/**
 * One group per job and reason, in the order the first of each was refused.
 *
 * DEF-FLD-10623 (PO retest item 7): the job's accept goes first
 * (DEF-FLD-10579), so after a reassignment the accept comes back alone on one
 * sync and the work on the next. The accept is the CAUSE — the row reads
 * *"WO-0155 · This job was reassigned."* from the first sync, and
 * *"WO-0155 · 3 items · …"* once the work comes back, the three counted and the
 * office sentence asked of the three alone.
 */
export function groupRefusals<T extends GroupableRefusal>(items: readonly T[]): RefusalGroup<T>[] {
  const groups = new Map<string, RefusalGroup<T>>();
  for (const item of items) {
    const action = item.action ?? 'fix';
    const at = `${item.workOrderId ?? item.workOrderNumber ?? ''}|${item.reasonKey ?? item.reason}|${action}`;
    let g = groups.get(at);
    if (!g) {
      g = {
        id: item.id,
        workOrderNumber: item.workOrderNumber,
        reason: item.reason,
        reasonKey: item.reasonKey ?? null,
        action,
        keptForOffice: false,
        items: [],
        work: [],
        cause: null,
      };
      groups.set(at, g);
    }
    g.items.push(item);
    g.workOrderNumber = g.workOrderNumber ?? item.workOrderNumber;
    if (isCause(item) && !g.cause) g.cause = item;
    else g.work.push(item);
  }
  for (const g of groups.values()) g.keptForOffice = g.work.length > 0 && g.work.every((i) => i.keptForOffice === true);
  return [...groups.values()];
}
