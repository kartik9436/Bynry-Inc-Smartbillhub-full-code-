/**
 * The crew's acts on one job (FF-29, FF-32), each captured once through the
 * outbox with its local change in the same transaction (Mobile data §1).
 *
 * Outbox kind `crew_time` goes through the crew and labour doors
 * (`sync/doors.ts`): a join and FF-29's × to `POST jobs/{id}/crew`, a
 * correction to `PUT jobs/{id}/labour` — under the captor's capture token,
 * whoever is signed in when it sends.
 */
import * as activityQ from '../../db/queries/activity';
import * as crewTimeQ from '../../db/queries/crewTime';
import * as crewOrderQ from '../../db/queries/crewTimeOrder';
import { capture } from '../../sync/outbox';
import type { Wave } from './fieldData';

/** E2E-20: a second technician joins at a moment; their labour clock starts. */
export function addTechnician(
  w: Wave,
  workOrderId: string,
  person: { id: string; name: string },
  byName: string,
): string {
  const personId = person.id;
  const at = w.clock.now().toISOString();
  return capture(
    w.db,
    w.captor,
    {
      kind: 'crew_time',
      workOrderId,
      payload: { act: 'join', person_id: personId, kind: 'labour', started_at: at },
      apply: (s, key) => {
        crewTimeQ.insert(s, { id: w.newId(), workOrderId, personId, kind: 'labour', startedAt: at, outboxId: key });
        // R10: the change is stamped on the job's activity, who and when.
        activityQ.insert(s, {
          id: w.newId(),
          workOrderId,
          kind: 'status',
          status: 'crew_joined',
          text: person.name, // a name, never an id on screen (R35)
          author: byName,
          at,
          outboxId: key,
        });
      },
    },
    w.deps,
  ).key;
}

/** FF-29's ×: their clocks stop now. Their time so far stays theirs. */
export function removeTechnician(w: Wave, workOrderId: string, personId: string): string {
  const at = w.clock.now().toISOString();
  return capture(
    w.db,
    w.captor,
    {
      kind: 'crew_time',
      workOrderId,
      payload: { act: 'leave', person_id: personId, ended_at: at },
      apply: (s) => {
        crewOrderQ.endOpen(s, workOrderId, personId, at);
      },
    },
    w.deps,
  ).key;
}

/**
 * R9 / US-FLD-020 TC-3: a person's travel and labour corrected, stamped with
 * who corrected it and when (the capture's own `captured_by`/`captured_at`).
 * Travel ends where labour begins; the corrected labour starts where the
 * recorded labour did, or at the arrival when none was recorded.
 *
 * The sheet takes MINUTES; the server keeps MOMENTS (lane S-GAPS). So the
 * moments these minutes mean are worked out HERE, once, from the same rows
 * written locally, and stored on the item as `moments` — the labour door then
 * sends exactly what the handset shows. Zero travel with a known arrival is
 * sent as departing at the arrival (0 minutes); zero labour sends no finish,
 * because the server holds a finish only AFTER its start.
 */
export function correctTime(
  w: Wave,
  workOrderId: string,
  person: { personId: string; arrivedAt: string | null; labourFrom: string | null },
  minutes: { travel: number; labour: number },
): string {
  const now = w.clock.now();
  const startLabour = person.labourFrom ?? person.arrivedAt ?? now.toISOString();
  const labourStart = Date.parse(startLabour);
  const arrived = Date.parse(person.arrivedAt ?? startLabour);
  const rows: Array<{ id: string; kind: 'travel' | 'labour'; startedAt: string; endedAt: string | null }> = [];
  if (minutes.travel > 0) {
    rows.push({
      id: w.newId(),
      kind: 'travel',
      startedAt: new Date(arrived - minutes.travel * 60000).toISOString(),
      endedAt: new Date(arrived).toISOString(),
    });
  }
  rows.push({
    id: w.newId(),
    kind: 'labour',
    startedAt: new Date(labourStart).toISOString(),
    endedAt: new Date(labourStart + minutes.labour * 60000).toISOString(),
  });
  return capture(
    w.db,
    w.captor,
    {
      kind: 'crew_time',
      workOrderId,
      payload: {
        act: 'correct',
        person_id: person.personId,
        travel_minutes: minutes.travel,
        labour_minutes: minutes.labour,
        moments: momentsOf(rows, person.arrivedAt, arrived),
      },
      apply: (s, key) => crewOrderQ.replaceForPerson(s, workOrderId, person.personId, rows, key),
    },
    w.deps,
  ).key;
}

/** The four moments a corrected pair of rows means (`correctTime`). */
function momentsOf(
  rows: ReadonlyArray<{ kind: 'travel' | 'labour'; startedAt: string; endedAt: string | null }>,
  arrivedAt: string | null,
  arrived: number,
): Record<string, string> {
  const out: Record<string, string> = {};
  const travel = rows.find((r) => r.kind === 'travel');
  if (travel) {
    out.depart_at = travel.startedAt;
    if (travel.endedAt) out.arrive_at = travel.endedAt;
  } else if (arrivedAt) {
    const at = new Date(arrived).toISOString();
    out.depart_at = at;
    out.arrive_at = at;
  }
  const labour = rows.find((r) => r.kind === 'labour');
  if (labour) {
    out.start_at = labour.startedAt;
    if (labour.endedAt && labour.endedAt > labour.startedAt) out.end_at = labour.endedAt;
  }
  return out;
}
