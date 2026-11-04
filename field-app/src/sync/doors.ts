/**
 * OUTBOX ITEMS THAT GO THROUGH THEIR OWN DOOR, not the job's sync batch
 * (lane INTEGRATE-2: the holds on FF-29, FF-37, FF-58 and FF-15's clocks,
 * released when their server routes landed; lane S-GAPS: keys, capture
 * tokens, a crew member leaving and a correction for another person).
 *
 *   crew_time  — a clock or a crew change on a job:
 *       start travel   → PUT  jobs/{id}/labour {depart_at}  + POST jobs/{id}/acts {act: depart, key}
 *       stop travel    → PUT  jobs/{id}/labour {arrive_at}  + POST jobs/{id}/acts {act: arrive, key}
 *       start labour   → PUT  jobs/{id}/labour {start_at}
 *       stop labour    → PUT  jobs/{id}/labour {end_at}
 *       correct a clock→ PUT  jobs/{id}/labour {the corrected pair} (R9: the server audits it)
 *       join           → POST jobs/{id}/crew   {technician_id, key}
 *       leave (FF-29 ×)→ POST jobs/{id}/crew   {act: leave, technician_id, ended_at}
 *       correct their time (FF-29, typed as MINUTES)
 *                      → PUT  jobs/{id}/labour {the moments those minutes mean, technician_id?}
 *   raise      → POST orders {key, template_id, …}  (FF-37, N16; idempotent on the key)
 *   hand_back  → POST jobs/{id}/hand-back {reason, note, key}  (FF-58, N20)
 *   job_accept → POST jobs/{id}/accept  (DEF-FLD-10579 — the first *Start*;
 *                `mobile.accept_job`, idempotent: a second accept answers the
 *                first stamp). Captured AHEAD of every unsent item of its job
 *                (`outbox.capture`'s `first`), because the server refuses a
 *                job's items until it is accepted (BR-WRK-059).
 *   job_decline→ POST jobs/{id}/decline {reason, note}  (DEF-FLD-10579 —
 *                *Decline* before starting; `mobile.decline_job`, the job
 *                stays with the technician until the dispatcher moves it).
 *   shift_end  → POST shift/end {at, key}  (FF-46 *End shift*, CR-193-BRC10;
 *                `shifts.end_shift`, one per person per day: a resend or a
 *                second press answers `duplicate`). NO JOB: it travels in the
 *                `job` channel's group with no order, so it keeps capture order.
 *   timesheet_submit → POST timesheet/submit {date, key}  (FF-47 *Submit the
 *                day*, CR-193-BRC10; `shifts.submit_day`, one per person per
 *                day, `duplicate` on a resend).
 *   availability → POST availability {at, value, key}  (FF-45, FB-033;
 *                `availability.record`: the TAP's time, so a late send counts
 *                from when it was pressed and never overwrites a newer office
 *                change; `duplicate` on a resend). NO JOB, like `shift_end`.
 *
 * EVERY CALL CARRIES THE ITEM'S KEY AND ITS CAPTOR'S CAPTURE TOKEN
 * (`DoorExtra`). The server writes the act as the token's captor
 * (`mobile.door_actor`), so these items no longer wait for their captor to be
 * the one signed in; and the acts and hand-back doors answer `duplicate` on a
 * replayed key, so a resend after a lost answer no longer appends a second
 * *depart* or meets a 404 for a hand-back that worked.
 *
 * A CORRECTION TYPED AS MINUTES is sent as MOMENTS. The server keeps one model
 * — four moments per person per job — so `crewActions.correctTime` works out
 * the moments its minutes mean at capture (travel ends at the arrival; labour
 * starts where it was recorded, or at the arrival) and stores them on the
 * item; this file sends them. Another person's correction names them
 * (`technician_id`), which the server honours only from the lead; the
 * captor's own correction names nobody.
 *
 * WHAT HAS NO DOOR, decided AT CAPTURE so it waits on the `unrouted` channel
 * rather than being refused later: admin time (labour is per job and
 * non-job time has no server home — `18-field-app/03-field-map.md` §11), a
 * correction captured before its moments were stored, and a raise with no
 * template (a route finding is not an order).
 *
 * ⚠ THE LABOUR DOOR HOLDS ONE OF EACH MOMENT PER PERSON PER JOB. A second
 * *Start work* after a pause therefore REPLACES `start_at` and the server
 * counts it as a correction (`work.labour.corrected`). That is the server's
 * model, not the handset's; reported, not papered over.
 */
import type { CaptureLocation } from './outbox';
import type { DoorExtra, FieldApi, LabourMoments } from './fieldApi';
import { asAvailabilityApi, type WireAvailability } from './availability';
import { asShiftsApi } from './shifts';
import { TransportError } from './transport';

export const DOOR_KINDS = [
  'crew_time',
  'raise',
  'hand_back',
  'job_accept',
  'job_decline',
  'shift_end',
  'timesheet_submit',
  'availability',
] as const;
export type DoorKind = (typeof DOOR_KINDS)[number];

export function isDoorKind(kind: string): kind is DoorKind {
  return (DOOR_KINDS as readonly string[]).includes(kind);
}

export type DoorCall =
  | { door: 'labour'; jobId: string; moments: LabourMoments; act?: 'depart' | 'arrive'; technicianId?: string }
  | { door: 'crew'; jobId: string; technicianId: string }
  | { door: 'crew_leave'; jobId: string; technicianId: string; endedAt: string | null }
  | { door: 'hand_back'; jobId: string; reason: string; note: string | null }
  | { door: 'accept'; jobId: string }
  | { door: 'decline'; jobId: string; reason: string; note: string | null }
  | { door: 'raise'; body: Record<string, unknown> }
  | { door: 'shift_end'; at: string }
  | { door: 'timesheet_submit'; date: string }
  | { door: 'availability'; at: string; value: WireAvailability };

const str = (v: unknown): string | null => (typeof v === 'string' && v !== '' ? v : null);

const MOMENT_NAMES = ['depart_at', 'arrive_at', 'start_at', 'end_at'] as const;

/** The moments a minutes-correction stored at capture, or null when it has none. */
function storedMoments(p: Record<string, unknown>): LabourMoments | null {
  const raw = (p.moments ?? null) as Record<string, unknown> | null;
  if (!raw || typeof raw !== 'object') return null;
  const out: LabourMoments = {};
  for (const name of MOMENT_NAMES) {
    const at = str(raw[name]);
    if (at) out[name] = at;
  }
  return Object.keys(out).length ? out : null;
}

function clockCall(jobId: string, p: Record<string, unknown>, captorId: string | null): DoorCall | null {
  const action = str(p.action);
  const kind = str(p.kind);
  if (action === 'start') {
    const at = str(p.at) ?? str(p.started_at);
    if (!at) return null;
    if (kind === 'travel') return { door: 'labour', jobId, moments: { depart_at: at }, act: 'depart' };
    if (kind === 'labour') return { door: 'labour', jobId, moments: { start_at: at } };
    return null;
  }
  if (action === 'stop') {
    const at = str(p.at) ?? str(p.ended_at);
    if (!at) return null;
    if (kind === 'travel') return { door: 'labour', jobId, moments: { arrive_at: at }, act: 'arrive' };
    if (kind === 'labour') return { door: 'labour', jobId, moments: { end_at: at } };
    return null;
  }
  if (action === 'correct') {
    const to = (p.to ?? {}) as Record<string, unknown>;
    const from = str(to.started_at);
    const until = str(to.ended_at);
    if (!from) return null;
    if (kind === 'travel') return { door: 'labour', jobId, moments: { depart_at: from, ...(until ? { arrive_at: until } : {}) } };
    if (kind === 'labour') return { door: 'labour', jobId, moments: { start_at: from, ...(until ? { end_at: until } : {}) } };
    return null;
  }
  const crewAct = str(p.act);
  if (crewAct === 'join') {
    const person = str(p.person_id);
    return person ? { door: 'crew', jobId, technicianId: person } : null;
  }
  if (crewAct === 'leave') {
    const person = str(p.person_id);
    return person ? { door: 'crew_leave', jobId, technicianId: person, endedAt: str(p.ended_at) } : null;
  }
  if (crewAct === 'correct') {
    const person = str(p.person_id);
    const moments = storedMoments(p);
    if (!person || !moments) return null;
    // The captor's own correction names nobody: the handset may key the
    // signed-in person by their login rather than their technician record,
    // and the server reads "no technician_id" as "my own clocks".
    return person === captorId
      ? { door: 'labour', jobId, moments }
      : { door: 'labour', jobId, moments, technicianId: person };
  }
  return null;
}

/**
 * The door one captured act goes through, or null when it has none. Called at
 * CAPTURE (to choose the channel) and again at SEND (to make the call), on the
 * same stored payload, so the two can never disagree.
 */
export function doorCallFor(
  kind: string,
  payload: Record<string, unknown>,
  workOrderId: string | null,
  meta: { key: string; capturedAt: string; location: CaptureLocation | null; captorId?: string | null },
): DoorCall | null {
  if (kind === 'crew_time') return workOrderId ? clockCall(workOrderId, payload, meta.captorId ?? null) : null;
  if (kind === 'hand_back') {
    const reason = str(payload.reason);
    return workOrderId && reason ? { door: 'hand_back', jobId: workOrderId, reason, note: str(payload.note) } : null;
  }
  if (kind === 'job_accept') return workOrderId ? { door: 'accept', jobId: workOrderId } : null;
  if (kind === 'job_decline') {
    const reason = str(payload.reason);
    return workOrderId && reason ? { door: 'decline', jobId: workOrderId, reason, note: str(payload.note) } : null;
  }
  if (kind === 'shift_end') {
    const at = str(payload.at);
    return at ? { door: 'shift_end', at } : null;
  }
  if (kind === 'timesheet_submit') {
    const date = str(payload.date);
    return date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? { door: 'timesheet_submit', date } : null;
  }
  if (kind === 'availability') {
    const at = str(payload.at);
    const value = str(payload.value);
    return at && (value === 'available' || value === 'on_break' || value === 'off_duty') ? { door: 'availability', at, value } : null;
  }
  if (kind === 'raise') {
    const templateId = str(payload.template_id);
    if (!templateId) return null;
    const body: Record<string, unknown> = {
      key: meta.key,
      template_id: templateId,
      template_version: payload.template_version ?? null,
      carried_from: str(payload.carried_from),
      premises_id: str(payload.premise_id),
      account_id: str(payload.account_id),
      asset_id: str(payload.asset_id),
      // FB-028 — the unit the carried job stands on, when the phone knows it.
      unit_id: str(payload.unit_id),
      urgency: str(payload.urgency) ?? 'normal',
      note: str(payload.note),
      captured_at: meta.capturedAt,
    };
    if (meta.location) body.location = meta.location;
    for (const k of Object.keys(body)) if (body[k] === null) delete body[k];
    return { door: 'raise', body };
  }
  return null;
}

/**
 * Make the call, under the item's key and its captor's capture token. Throws
 * `TransportError` exactly as the transport does.
 */
export async function callDoor(
  api: FieldApi,
  call: DoorCall,
  key: string,
  captureToken: string | null = null,
): Promise<Record<string, unknown> | null> {
  const extra: DoorExtra = { key, captureToken };
  switch (call.door) {
    case 'labour': {
      // The moments first: they are idempotent (the same value again changes
      // nothing), so a failure of the act after them is safe to send again —
      // and the act now carries the key, so its resend answers `duplicate`.
      const labourExtra: DoorExtra = { captureToken, ...(call.technicianId ? { technicianId: call.technicianId } : {}) };
      const answer = (await api.recordLabour(call.jobId, call.moments, labourExtra)) as Record<string, unknown> | null;
      if (call.act) await api.jobAct(call.jobId, call.act, extra);
      return answer;
    }
    case 'crew':
      return (await api.addCrew(call.jobId, { technician_id: call.technicianId, key }, { captureToken })) as Record<string, unknown> | null;
    case 'crew_leave':
      return (await api.leaveCrew(call.jobId, { technician_id: call.technicianId, ended_at: call.endedAt }, { captureToken })) as Record<
        string,
        unknown
      > | null;
    case 'hand_back':
      return (await api.handBack(call.jobId, { reason: call.reason, note: call.note }, extra)) as Record<string, unknown> | null;
    case 'accept':
      return (await api.acceptJob(call.jobId, { captureToken })) as Record<string, unknown> | null;
    case 'decline':
      return (await api.declineJob(call.jobId, { reason: call.reason, note: call.note }, { captureToken })) as Record<string, unknown> | null;
    case 'raise':
      return (await api.raiseOrder(call.body, { captureToken })) as Record<string, unknown> | null;
    case 'availability': {
      const door = asAvailabilityApi(api);
      if (!door) throw new TransportError('endpoint_missing', 'this transport has no availability door');
      return (await door.sendAvailability({ at: call.at, value: call.value }, extra)) as Record<string, unknown> | null;
    }
    case 'shift_end':
    case 'timesheet_submit': {
      const shifts = asShiftsApi(api);
      if (!shifts) throw new TransportError('endpoint_missing', `this transport has no ${call.door} door`);
      return (
        call.door === 'shift_end'
          ? await shifts.endShift({ at: call.at }, extra)
          : await shifts.submitTimesheet({ date: call.date }, extra)
      ) as Record<string, unknown> | null;
    }
  }
}
