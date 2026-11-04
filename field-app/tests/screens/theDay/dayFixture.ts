/**
 * Dana's Tuesday, 21 October 2026, in a real handset store (better-sqlite3,
 * the same SQL the phone runs): the boards' own test data (B14 rule 37 —
 * figures on a board are illustrations, used here as test data only).
 *
 *   WO-4822 Sarah Miller  1400 Elm Street · Unit A   on site     P3  08:00–12:00  60 min
 *   WO-4824 Aaron Bruner  22 Cedar Court, Austin TX  dispatched  P1  12:00–17:00  45 min
 *   WO-4831 Marcus Webb   88 Hillcrest Avenue        queued      P3  14:00–16:00  30 min
 *   WO-4833 —             5 Pine Vista (no point)    on hold     P2  15:00–16:00  20 min
 *   WO-4810 done today · WO-4901 tomorrow · WO-9999 is MARCO's (must never show)
 *
 * Route WLK-07: 1318 Maple Street (3 meters to read), 9 Oak Ridge (1 to read,
 * 2 read, 1 could not be read). Two items and one photograph waiting to
 * send; one item sent at 10:02. Crew time: travel 48m, on site 3h 04m,
 * admin 1h.
 */
import { type TenantDb } from '../../../src/db/database';
import * as customerQ from '../../../src/db/queries/customer';
import * as crewTimeQ from '../../../src/db/queries/crewTime';
import * as outboxQ from '../../../src/db/queries/outbox';
import * as photoQ from '../../../src/db/queries/photo';
import * as premiseQ from '../../../src/db/queries/premise';
import * as routeQ from '../../../src/db/queries/route';
import * as routeReadQ from '../../../src/db/queries/routeRead';
import * as routeStopQ from '../../../src/db/queries/routeStop';
import * as searchQ from '../../../src/db/queries/searchIndex';
import * as workOrderQ from '../../../src/db/queries/workOrder';
import { deviceWide, scoped } from '../../../src/db/scoped';
import { openStore } from '../../db/support/fixtures';
import { PEOPLE } from '../../session/fakes';

export const DANA = PEOPLE['d.ortiz']?.technicianId ?? 'tech-dana';
export const MARCO = PEOPLE['m.chen']?.technicianId ?? 'tech-marco';

/** 07:30 local on the day. */
export const NOW = new Date(2026, 9, 21, 7, 30);

export function at(day: number, h: number, m = 0): string {
  return new Date(2026, 9, day, h, m).toISOString();
}

const T = at(21, 7, 0);

interface Job {
  id: string;
  number: string;
  type: string;
  state: string;
  priority: string;
  premise: string;
  customer: string | null;
  from: string | null;
  to: string | null;
  est: number;
}

export const JOBS: Job[] = [
  { id: 'wo-4822', number: 'WO-4822', type: 'Meter exchange', state: 'on_site', priority: 'P3', premise: 'p-elm', customer: 'c-miller', from: at(21, 8), to: at(21, 12), est: 60 },
  { id: 'wo-4824', number: 'WO-4824', type: 'Disconnect — non-payment', state: 'scheduled', priority: 'P1', premise: 'p-cedar', customer: 'c-bruner', from: at(21, 12), to: at(21, 17), est: 45 },
  { id: 'wo-4831', number: 'WO-4831', type: 'Final read — move-out', state: 'queued', priority: 'P3', premise: 'p-hill', customer: 'c-webb', from: at(21, 14), to: at(21, 16), est: 30 },
  { id: 'wo-4833', number: 'WO-4833', type: 'Meter seal check', state: 'on_hold', priority: 'P2', premise: 'p-pine', customer: null, from: at(21, 15), to: at(21, 16), est: 20 },
  { id: 'wo-4810', number: 'WO-4810', type: 'Routine read', state: 'complete', priority: 'P3', premise: 'p-oak', customer: null, from: at(21, 7), to: at(21, 8), est: 15 },
  { id: 'wo-4901', number: 'WO-4901', type: 'Meter exchange', state: 'scheduled', priority: 'P3', premise: 'p-oak', customer: null, from: at(22, 9), to: at(22, 11), est: 60 },
];

export function seedDay(options: { tenant?: string } = {}): TenantDb {
  const db = openStore(options.tenant ?? 'silver-creek');
  premiseQ.upsert(db, { id: 'p-elm', addressLine: '1400 Elm Street · Unit A', locality: 'Austin', region: 'TX', postalCode: '78701', lat: 30.27, lng: -97.74 }, T);
  premiseQ.upsert(db, { id: 'p-cedar', addressLine: '22 Cedar Court', locality: 'Austin', region: 'TX', postalCode: '78704', lat: 30.25, lng: -97.76 }, T);
  premiseQ.upsert(db, { id: 'p-hill', addressLine: '88 Hillcrest Avenue', locality: 'Austin', region: 'TX', postalCode: '78702', lat: 30.26, lng: -97.72 }, T);
  premiseQ.upsert(db, { id: 'p-pine', addressLine: '5 Pine Vista', locality: 'Austin', region: 'TX', postalCode: '78703' }, T);
  premiseQ.upsert(db, { id: 'p-oak', addressLine: '9 Oak Ridge', locality: 'Austin', region: 'TX', postalCode: '78705', lat: 30.28, lng: -97.73 }, T);
  premiseQ.upsert(db, { id: 'p-maple', addressLine: '1318 Maple Street', locality: 'Austin', region: 'TX', postalCode: '78701', lat: 30.271, lng: -97.741 }, T);
  customerQ.upsert(db, { id: 'c-miller', name: 'Sarah Miller' }, T);
  customerQ.upsert(db, { id: 'c-bruner', name: 'Aaron Bruner' }, T);
  customerQ.upsert(db, { id: 'c-webb', name: 'Marcus Webb' }, T);

  const dana = scoped(db, DANA);
  for (const j of JOBS) {
    workOrderQ.upsertFromServer(
      dana,
      {
        id: j.id,
        number: j.number,
        type: j.type,
        state: null,
        dispatchState: j.state,
        priorityCode: j.priority,
        priorityRank: null,
        premiseId: j.premise,
        windowStart: j.from,
        windowEnd: j.to,
        dueAt: null,
        estMinutes: j.est,
        accessNotes: null,
        hazards: null,
        gateCode: null,
        extra: null,
        serverUpdatedAt: T,
      },
      T,
    );
    // The job feed does not carry the customer yet (reported); the fixture sets it as the mirror would.
    if (j.customer) {
      dana.run('UPDATE work_order SET customer_id = :c WHERE technician_id = :technician_id AND id = :id', { c: j.customer, id: j.id });
    }
    searchQ.put(dana, 'work_order', j.id, { number: j.number, customerName: j.customer ? j.customer.replace('c-', '') : null, address: null });
  }
  searchQ.put(dana, 'work_order', 'wo-4822', { number: 'WO-4822', customerName: 'Sarah Miller', address: '1400 Elm Street' });
  searchQ.put(dana, 'work_order', 'wo-4824', { number: 'WO-4824', customerName: 'Aaron Bruner', address: '22 Cedar Court' });

  // Marco's job, same store: Dana must never see it.
  const marco = scoped(db, MARCO);
  workOrderQ.upsertFromServer(
    marco,
    { id: 'wo-9999', number: 'WO-9999', type: 'Leak check', state: null, dispatchState: 'scheduled', priorityCode: 'P1', priorityRank: null, premiseId: 'p-elm', windowStart: at(21, 7), windowEnd: at(21, 9), dueAt: null, estMinutes: 30, accessNotes: null, hazards: null, gateCode: null, extra: null, serverUpdatedAt: T },
    T,
  );
  searchQ.put(marco, 'work_order', 'wo-9999', { number: 'WO-9999', customerName: 'Elm Tenant', address: '1400 Elm Street' });

  // Route WLK-07.
  routeQ.upsert(dana, { id: 'r-wlk07', code: 'WLK-07', windowStart: at(21, 7) }, T);
  routeStopQ.upsert(dana, { id: 's-maple', routeId: 'r-wlk07', premiseId: 'p-maple', walkPosition: 1 }, T);
  routeStopQ.upsert(dana, { id: 's-oak', routeId: 'r-wlk07', premiseId: 'p-oak', walkPosition: 2 }, T);
  const read = (id: string, stopId: string) =>
    routeReadQ.upsertFromServer(dana, { id, routeId: 'r-wlk07', stopId, assetId: `a-${id}`, unit: 'gal' }, T);
  ['m1', 'm2', 'm3'].forEach((id) => read(id, 's-maple'));
  ['o1', 'o2', 'o3', 'o4'].forEach((id) => read(id, 's-oak'));
  const capture = (id: string, status: 'read' | 'could_not_read') =>
    routeReadQ.recordCapture(dana, id, {
      captureKey: `k-${id}`,
      value: status === 'read' ? '48210.50' : null,
      unit: 'gal',
      readerStatus: status,
      capturedAt: at(21, 7, 10),
      capturedBy: DANA,
      identifiedBy: 'listed',
      readMethod: 'visual',
    });
  capture('o2', 'read');
  capture('o3', 'read');
  capture('o4', 'could_not_read');

  // Waiting to send: two items and one photograph; one item sent at 10:02.
  const item = (id: string, seq: number) =>
    outboxQ.insert(dana, { id, workOrderId: 'wo-4822', routeId: null, kind: 'task_tick', channel: 'job', payload: {}, seq, capturedBy: DANA, capturedAt: at(21, 8, seq), location: null });
  item('ob-1', 1);
  item('ob-2', 2);
  item('ob-sent', 3);
  deviceWide(db, 'receipt').run(`UPDATE outbox SET state = 'accepted', settled_at = :at WHERE id = 'ob-sent'`, { at: at(21, 10, 2) });
  outboxQ.insert(dana, { id: 'ob-photo', workOrderId: 'wo-4822', routeId: null, kind: 'photo', channel: 'job', payload: {}, seq: 4, capturedBy: DANA, capturedAt: at(21, 8, 4), location: null });
  photoQ.insert(dana, { id: 'ph-1', outboxId: 'ob-1', declareId: 'ob-photo', workOrderId: 'wo-4822', routeId: null, localPath: '/p/1.jpg', sha256: 'x', bytes: 10, capturedBy: DANA, capturedAt: at(21, 8, 4), location: null });

  // Hours: travel 48m, on site 3h 04m, admin 1h.
  crewTimeQ.insert(dana, { id: 'ct-1', workOrderId: null, personId: DANA, kind: 'travel', startedAt: at(21, 6, 0), endedAt: at(21, 6, 48) });
  crewTimeQ.insert(dana, { id: 'ct-2', workOrderId: 'wo-4822', personId: DANA, kind: 'labour', startedAt: at(21, 1, 0), endedAt: at(21, 4, 4) });
  crewTimeQ.insert(dana, { id: 'ct-3', workOrderId: null, personId: DANA, kind: 'admin', startedAt: at(21, 5, 0), endedAt: at(21, 6, 0) });
  return db;
}
