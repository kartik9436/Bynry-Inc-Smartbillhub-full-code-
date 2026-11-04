/**
 * The outbox: every act, captured once, sent until the server has it.
 *
 * CAPTURE (R46, Mobile data §1): one row per act, its idempotency key minted
 * here on the handset — never at send, never by the server. The act, its photo
 * rows, their declarations and whatever the act changes locally land in ONE
 * transaction: a failure anywhere leaves nothing half-written.
 *
 * SEND (Mobile data §4, R45–R50): batches of 50, in capture order within one
 * technician's order or route; at most two batches in flight across orders and
 * never two of the same order at once (a safety tick lands before the close it
 * unlocks); per-item answers (`receipts.ts`); exponential backoff with a cap
 * (`backoff.ts`). Every technician's work sends under its OWN capture token,
 * whoever is signed in (E2E-21, BR-WRK-060).
 */
import type { TenantDb } from '../db/database';
import { fromJson } from '../db/json';
import * as outboxQ from '../db/queries/outbox';
import * as photoQ from '../db/queries/photo';
import * as workOrderQ from '../db/queries/workOrder';
import { deviceWide, scoped, type ScopedRunner } from '../db/scoped';
import { callDoor, DOOR_KINDS, doorCallFor, isDoorKind, type DoorKind } from './doors';
import { isJobWork, needsAccept } from './jobAcceptance';
import { asFieldApi } from './fieldApi';
import { applyBatchAnswer, applyBatchFailure, emptyTally, waitForCaptor, type ReceiptTally } from './receipts';
import { TransportError, type Transport, type WireItem } from './transport';

/** The server's own item kinds — `apps/work/sync_models.py ITEM_KINDS`.
 *  `outbox.test.ts` reads that file and fails when the two drift. */
export const JOB_SYNC_KINDS = [
  'safety_tick',
  'task_tick',
  'reading',
  'material',
  'attachment',
  'signature',
  'close',
  'photo',
] as const;

/** Kinds with no server door yet. Captured, kept, and NOT sent: each waits on
 *  the endpoint named in the report that introduced it.
 *
 *  Released by lane INTEGRATE-2 when their doors landed: `crew_time`, `raise`
 *  and `hand_back` go through their own doors (`doors.ts` — except the acts
 *  `doorCallFor` finds no door for, which still wait here, decided at
 *  capture: admin time); `field_asset` goes to the reads door as `add_meter`
 *  (`routeReads.ts`); `claim` was never captured — a claim is online only
 *  (`field_dispatch.claim`, AD-04), through `theDay/nearbyApi.ts`.
 *  `route_finding` (RW-18/RW-21's finding at a meter) was here until lane
 *  FINDINGS (2026-10-22): the reads door now takes it as `finding`
 *  (`routeReads.ts`), and Work keeps it — a rule for its kind raises the job,
 *  else a person does (BR-WRK-067). */
export const UNROUTED_KINDS = ['remark', 'document'] as const;

export type OutboxKind =
  | (typeof JOB_SYNC_KINDS)[number]
  | 'route_read'
  | 'route_finding'
  | 'field_asset'
  | 'route_position'
  | DoorKind
  | (typeof UNROUTED_KINDS)[number];

/** Every kind the outbox can hold, as a list — FF-50 needs a word for each
 *  (DEF-FLD-10623: a refused accept read as the bare `job_accept`).
 *  `kindWords.test.ts` iterates it; the type below fails `tsc` when a new
 *  `OutboxKind` is not listed here. */
export const CAPTURABLE_KINDS = [
  ...JOB_SYNC_KINDS,
  'route_read',
  'route_finding',
  'field_asset',
  'route_position',
  ...DOOR_KINDS,
  ...UNROUTED_KINDS,
] as const satisfies readonly OutboxKind[];

type Unlisted = Exclude<OutboxKind, (typeof CAPTURABLE_KINDS)[number]>;
/** Compiles only while no `OutboxKind` is missing from `CAPTURABLE_KINDS`. */
export const EVERY_KIND_LISTED: [Unlisted] extends [never] ? true : Unlisted = true;

export const BATCH_SIZE = 50;
export const MAX_BATCHES_IN_FLIGHT = 2;

export interface Clock {
  now(): Date;
}

export interface CaptureDeps {
  newId(): string;
  clock: Clock;
}

/**
 * Who captured it. Written from the CAPTURE CREDENTIAL, never read from the
 * current session (Security §3: "that one line is what makes a shared handset
 * honest"). `technicianId` owns the row; `capturedBy` did the act — usually
 * the same person; when not, the server stores and flags, never refuses.
 */
export interface Captor {
  technicianId: string;
  capturedBy: string;
}

export interface CaptureLocation {
  lat: number;
  lng: number;
  accuracy_m: number;
  fix_at: string;
}

export interface PhotoCapture {
  localPath: string;
  sha256: string;
  bytes: number;
  width?: number;
  height?: number;
  /** What it proves, as the server's declaration names it (`photo_links.declare`). */
  target: { task_id?: string; reading_id?: string; route_read_id?: string };
  /** FB-003 (PO 2026-10-27): the photograph's OWN position, taken at the
   *  shutter — null for "no fix then". Absent: the act's position, as before. */
  location?: CaptureLocation | null;
}

export interface CaptureInput {
  kind: OutboxKind;
  workOrderId?: string | null;
  routeId?: string | null;
  payload: Record<string, unknown>;
  location?: CaptureLocation | null;
  photos?: readonly PhotoCapture[];
  /** The local change that belongs to the same act — a tick on wo_item, the
   *  figure on wo_reading or route_read. Runs inside the same transaction. */
  apply?: (s: ScopedRunner, key: string) => void;
  /** Send this ahead of every unsent item of its job (the job's accept, DEF-FLD-10579). */
  first?: boolean;
  /** The payload, built once the photographs' ids are minted — for an act that
   *  names a photograph INSIDE its payload (MQ-033: a photo answer carries its
   *  `photo_id`). Replaces `payload` when given; `photo_ids` is still added. */
  payloadFor?: (photoIds: readonly string[]) => Record<string, unknown>;
}

export interface Captured {
  key: string;
  photoIds: string[];
  declarationKeys: string[];
}

function channelFor(
  kind: OutboxKind,
  workOrderId: string | null,
  routeId: string | null,
  payload: Record<string, unknown>,
): outboxQ.Channel {
  if ((UNROUTED_KINDS as readonly string[]).includes(kind)) return 'unrouted';
  if (isDoorKind(kind)) {
    // Its own door, travelling in the job's group so it keeps its place in
    // capture order (R45) — or, when this act has no door, it waits.
    return doorCallFor(kind, payload, workOrderId, { key: '', capturedAt: '', location: null }) ? 'job' : 'unrouted';
  }
  if (
    kind === 'route_read' ||
    kind === 'field_asset' ||
    kind === 'route_finding' ||
    kind === 'route_position' ||
    (kind === 'photo' && routeId && !workOrderId)
  ) {
    if (!routeId) throw new Error(`${kind} needs the route it was read on`);
    return 'route';
  }
  if (!workOrderId) throw new Error(`${kind} needs the job it belongs to`);
  return 'job';
}

/** One act, captured. Synchronous and atomic — see `db/driver.ts`. */
export function capture(db: TenantDb, captor: Captor, input: CaptureInput, deps: CaptureDeps): Captured {
  if (!captor.technicianId || !captor.capturedBy) throw new Error('a capture needs whose it is and who did it');
  const workOrderId = input.workOrderId ?? null;
  const routeId = input.routeId ?? null;
  const channel = channelFor(input.kind, workOrderId, routeId, input.payload);
  const capturedAt = deps.clock.now().toISOString();
  const s = scoped(db, captor.technicianId);
  return db.transaction(() => {
    const key = deps.newId();
    // DEF-FLD-10623: the job's number travels with the act, because the job
    // itself can leave the phone (reassigned: the feed removes it) while the
    // act is still waiting or refused, and FF-50 must still name it.
    const workOrderNumber = workOrderId ? (workOrderQ.getMine(s, workOrderId)?.number ?? null) : null;
    // A ROUTE act names its photographs by id ON the item: the reads door
    // keeps them on the reading (`photos`) and checks them (RW-18's plate,
    // RW-20's add-meter), while each declaration travels as its own `photo`
    // item (DEF-FLD-10357). The ids are minted first so the act can carry them.
    const photoIdsAhead = (input.photos ?? []).map(() => deps.newId());
    const base = input.payloadFor ? input.payloadFor(photoIdsAhead) : input.payload;
    const payload = channel === 'route' && photoIdsAhead.length ? { ...base, photo_ids: photoIdsAhead } : base;
    // DEF-FLD-10612 (PO, MQ-027): work on a job means the job is taken. The
    // first work saved on a job not yet accepted queues ONE accept, ahead of
    // every unsent item of that job — whichever screen saved it. The three
    // *Start* buttons find it waiting and queue nothing more (`jobAcceptance.ts`).
    if (workOrderId && !routeId && isJobWork(input.kind, input.payload) && needsAccept(s, workOrderId)) {
      outboxQ.insert(s, {
        id: deps.newId(),
        workOrderId,
        workOrderNumber,
        routeId: null,
        kind: 'job_accept',
        channel: 'job',
        payload: {},
        seq: outboxQ.seqAheadOfUnsent(s, workOrderId) ?? outboxQ.nextSeq(s, workOrderId, null),
        capturedBy: captor.capturedBy,
        capturedAt,
        location: input.location ?? null,
      });
    }
    const ahead = input.first && workOrderId && !routeId ? outboxQ.seqAheadOfUnsent(s, workOrderId) : null;
    let seq = ahead ?? outboxQ.nextSeq(s, workOrderId, routeId);
    outboxQ.insert(s, {
      id: key,
      workOrderId,
      workOrderNumber,
      routeId,
      kind: input.kind,
      channel,
      payload,
      seq,
      capturedBy: captor.capturedBy,
      capturedAt,
      location: input.location ?? null,
    });
    const photoIds: string[] = [];
    const declarationKeys: string[] = [];
    for (const [i, p] of (input.photos ?? []).entries()) {
      const photoId = photoIdsAhead[i]!;
      seq += 1;
      declarationKeys.push(
        declarePhoto(s, deps, {
          photoId,
          proves: key,
          photo: p,
          extra: {},
          // FB-003: a photograph carries the position of its own shutter press.
          location: p.location !== undefined ? p.location : (input.location ?? null),
          seq,
          channel: channel === 'unrouted' ? 'unrouted' : channel,
          workOrderId,
          workOrderNumber,
          routeId,
          capturedBy: captor.capturedBy,
          capturedAt,
        }),
      );
      photoIds.push(photoId);
    }
    input.apply?.(s, key);
    return { key, photoIds, declarationKeys };
  });
}

/**
 * R123: a photograph DECLARED with the data — id, sha256 and what it proves —
 * as the server's `photo` item; the bytes follow later. Writes the declaration
 * and the photo row and returns the declaration's key. Runs inside the
 * caller's transaction.
 */
function declarePhoto(
  s: ScopedRunner,
  deps: CaptureDeps,
  d: {
    photoId: string;
    /** The act the photograph proves — `photo.outbox_id`. */
    proves: string;
    photo: PhotoCapture;
    /** More for the declaration's payload (FB-019: the reading's key). */
    extra: Record<string, unknown>;
    location: CaptureLocation | null;
    seq: number;
    channel: outboxQ.Channel;
    workOrderId: string | null;
    workOrderNumber: string | null;
    routeId: string | null;
    capturedBy: string;
    capturedAt: string;
  },
): string {
  const declareKey = deps.newId();
  outboxQ.insert(s, {
    id: declareKey,
    workOrderId: d.workOrderId,
    workOrderNumber: d.workOrderNumber,
    routeId: d.routeId,
    kind: 'photo',
    channel: d.channel,
    payload: { photo_id: d.photoId, sha256: d.photo.sha256, ...d.photo.target, ...d.extra },
    seq: d.seq,
    capturedBy: d.capturedBy,
    capturedAt: d.capturedAt,
    location: d.location,
  });
  photoQ.insert(s, {
    id: d.photoId,
    outboxId: d.proves,
    declareId: declareKey,
    workOrderId: d.workOrderId,
    // DEF-FLD-10631: the reading it proves, from the declaration itself —
    // so a photo added after saving, or a reading saved twice, still counts.
    routeReadId: d.photo.target.route_read_id ?? null,
    routeId: d.routeId,
    localPath: d.photo.localPath,
    sha256: d.photo.sha256,
    bytes: d.photo.bytes,
    width: d.photo.width ?? null,
    height: d.photo.height ?? null,
    capturedBy: d.capturedBy,
    capturedAt: d.capturedAt,
    location: d.location,
  });
  return declareKey;
}

/**
 * FB-019 (`DEF-FLD-10637`, PO report 2026-10-28): a photograph added to a
 * route reading that is ALREADY SAVED. It is ONE item — the declaration —
 * naming the reading by the key the server holds it under (`reading_key`:
 * the reading's capture key, which is its `field_reads.key`). Until this the
 * camera captured a `photo` ACT beside the declaration; the act carried no
 * `photo_id` or `sha256`, so the reads door refused it *"This photo is
 * damaged"*, on every retake, and the declaration never said which reading it
 * belonged to.
 *
 * The photo row proves the reading's own act (`outbox_id` = its capture key)
 * and names it (`route_read_id`), so FB-002's count holds; a photograph with
 * no fix at the shutter is still given a late one within 5 minutes (FB-003,
 * `screens/reads/position.ts`), because the declaration is a route `photo`
 * item saved with no position.
 */
export function declareRoutePhoto(
  db: TenantDb,
  captor: Captor,
  input: {
    routeId: string;
    routeReadId: string;
    readingKey: string;
    photo: Omit<PhotoCapture, 'target'>;
  },
  deps: CaptureDeps,
): { photoId: string; declarationKey: string } {
  if (!captor.technicianId || !captor.capturedBy) throw new Error('a capture needs whose it is and who did it');
  if (!input.routeId || !input.readingKey) throw new Error('a photo added after saving needs its route and its reading');
  const s = scoped(db, captor.technicianId);
  const capturedAt = deps.clock.now().toISOString();
  return db.transaction(() => {
    const photoId = deps.newId();
    const declarationKey = declarePhoto(s, deps, {
      photoId,
      proves: input.readingKey,
      photo: { ...input.photo, target: { route_read_id: input.routeReadId } },
      extra: { reading_key: input.readingKey },
      location: input.photo.location ?? null,
      seq: outboxQ.nextSeq(s, null, input.routeId),
      channel: 'route',
      workOrderId: null,
      workOrderNumber: null,
      routeId: input.routeId,
      capturedBy: captor.capturedBy,
      capturedAt,
    });
    return { photoId, declarationKey };
  });
}

/**
 * FB-019 (`DEF-FLD-10637`): a phone that ran 2.606.0 or earlier may hold the
 * empty `photo` act that build queued beside a photo added after saving —
 * refused *"This photo is damaged"* and left on FF-50 as *needs you*. It never
 * carried anything its declaration does not (the reading's local id and the
 * photo's id), so once every photograph it names has its declaration SETTLED
 * (the server has it), the act is settled too, marked as swept. A declaration
 * still unsent or itself refused leaves the act exactly as it is. Runs before
 * and after every send; the second time catches an act refused in this run.
 */
export function settleEmptyPhotoActs(db: TenantDb, at: string): number {
  const send = deviceWide(db, 'send');
  const ids = outboxQ.emptyPhotoActsSettleable(send);
  if (ids.length === 0) return 0;
  db.transaction(() => {
    for (const id of ids) outboxQ.settle(send, id, 'accepted', at, { swept: 'DEF-FLD-10637' });
  });
  return ids.length;
}

// ── Sending ──────────────────────────────────────────────────────────────────

/** Each technician's capture credential, from the keystore (T-12). The
 *  outbox never stores a credential (Security §2). */
export interface CaptureTokens {
  tokenFor(technicianId: string): string | null;
}

export interface SendOptions {
  clock: Clock;
  tokens: CaptureTokens;
  random?: () => number;
  batchSize?: number;
  maxInFlight?: number;
  /** Observes every request — tests use it to count batches and concurrency. */
  onBatch?: (info: { group: outboxQ.SendGroup; size: number; inFlight: number }) => void;
}

export interface SendSummary extends ReceiptTally {
  batches: number;
  stoppedForAuth: boolean;
  /** The server refused this build (`app_too_old`): the run stopped, nothing was refused. */
  stoppedForUpdate: boolean;
  skippedNoToken: number;
  /** `skippedNoToken` per captor (DEF-FLD-10629): whose work waits for a sign-in. */
  skippedNoTokenBy: Record<string, number>;
  /**
   * Own-door items whose captor's capture token the server refused (expired,
   * or the handset signed out by the office): kept, and sent after that
   * captor's next sign-in. Not a stop for anyone else's work.
   */
  waitingForCaptor: number;
}

function toWire(row: outboxQ.OutboxRow, token: string | null): WireItem {
  const item: WireItem = {
    key: row.id,
    kind: row.kind,
    seq: row.seq,
    captured_at: row.captured_at,
    payload: fromJson<Record<string, unknown>>(row.payload) ?? {},
  };
  // The server takes all four or none (`mobile.parse_location`).
  if (row.lat !== null && row.lng !== null && row.accuracy_m !== null && row.fix_at !== null) {
    item.location = { lat: row.lat, lng: row.lng, accuracy_m: row.accuracy_m, fix_at: row.fix_at };
  }
  if (token) item.capture_token = token;
  return item;
}

/**
 * Send everything that is due, once through. Call again later for what backed
 * off. Never throws for a server or network failure — the rows carry it.
 */
export async function sendPending(db: TenantDb, transport: Transport, opts: SendOptions): Promise<SendSummary> {
  const send = deviceWide(db, 'send');
  const batchSize = opts.batchSize ?? BATCH_SIZE;
  const maxInFlight = opts.maxInFlight ?? MAX_BATCHES_IN_FLIGHT;
  const summary: SendSummary = {
    ...emptyTally(),
    batches: 0,
    stoppedForAuth: false,
    stoppedForUpdate: false,
    skippedNoToken: 0,
    skippedNoTokenBy: {},
    waitingForCaptor: 0,
  };
  const api = asFieldApi(transport);

  outboxQ.resetInterrupted(send);
  settleEmptyPhotoActs(db, opts.clock.now().toISOString());
  const groups = outboxQ.dueGroups(send, opts.clock.now().toISOString());
  let inFlight = 0;
  let next = 0;

  const add = (t: ReceiptTally): void => {
    summary.accepted += t.accepted;
    summary.duplicate += t.duplicate;
    summary.held_for_review += t.held_for_review;
    summary.refused += t.refused;
    summary.unanswered += t.unanswered;
  };

  const sendGroup = async (group: outboxQ.SendGroup): Promise<void> => {
    const token = opts.tokens.tokenFor(group.technician_id);
    if (!token) {
      // Without the captor's credential the item would travel as whoever is
      // signed in — exactly what must never happen (Security §3). It waits.
      summary.skippedNoToken += group.n;
      summary.skippedNoTokenBy[group.technician_id] = (summary.skippedNoTokenBy[group.technician_id] ?? 0) + group.n;
      return;
    }
    for (;;) {
      if (summary.stoppedForAuth || summary.stoppedForUpdate) return;
      const due = outboxQ.nextBatch(send, group, batchSize, opts.clock.now().toISOString());
      if (due.length === 0) return;
      const head = due[0]!;
      if (group.channel === 'job' && isDoorKind(head.kind)) {
        // One item through its own door, under its CAPTOR's token whoever is
        // signed in (the server's `mobile.door_actor`, lane S-GAPS), then back
        // round for the next.
        const sent = await sendThroughDoor(db, api, head, token, opts, summary, add);
        // FB-014 (DEF-FLD-10639): a REFUSED item is answered — it waits on
        // FF-50 for the technician — so the job's next items go now, exactly
        // as a batch carries on past a refused item. Before this a refused
        // `time` held the CLOSE behind it until the next run (up to 15 min),
        // which is why the office saw WO-0171's status change late. A refused
        // ACCEPT still stops its job: everything behind it needs the accept.
        if (sent === 'refused' && head.kind !== 'job_accept') continue;
        if (sent !== true) return;
        continue;
      }
      // The batch stops before the next own-door item, so capture order holds.
      const firstDoor = group.channel === 'job' ? due.findIndex((r) => isDoorKind(r.kind)) : -1;
      const rows = firstDoor === -1 ? due : due.slice(0, firstDoor);
      db.transaction(() => outboxQ.markSending(send, rows.map((r) => r.id)));
      const items = rows.map((r) => toWire(r, token));
      inFlight += 1;
      summary.batches += 1;
      opts.onBatch?.({ group, size: rows.length, inFlight });
      try {
        const answer =
          group.channel === 'route'
            ? await transport.sendRouteReads(group.route_id ?? '', items)
            : await transport.sendJobBatch(group.work_order_id ?? '', items);
        add(applyBatchAnswer(db, rows, answer, opts.clock.now(), opts.random));
      } catch (err) {
        const e = err instanceof TransportError ? err : new TransportError('network', String(err));
        add(applyBatchFailure(db, rows, e, opts.clock.now(), opts.random));
        if (e.kind === 'auth') summary.stoppedForAuth = true;
        if (e.kind === 'app_too_old') summary.stoppedForUpdate = true;
        return; // this group backs off; the others carry on
      } finally {
        inFlight -= 1;
      }
    }
  };

  const worker = async (): Promise<void> => {
    while (next < groups.length && !summary.stoppedForAuth && !summary.stoppedForUpdate) {
      const group = groups[next++];
      if (group) await sendGroup(group);
    }
  };
  await Promise.all(Array.from({ length: Math.max(1, maxInFlight) }, worker));
  // FB-019: an empty act refused in THIS run beside an accepted declaration
  // is not left as *needs you*.
  settleEmptyPhotoActs(db, opts.clock.now().toISOString());
  return summary;
}

/**
 * One own-door item: called, then answered on its row exactly as a batch
 * item is (`receipts.ts`) — settled, refused with the server's reason, or
 * back to pending with its backoff. False when the run should stop for this
 * group (a failure; the row carries it); `'refused'` when the server answered
 * it with a refusal, which is final for that item and stops nothing else.
 */
async function sendThroughDoor(
  db: TenantDb,
  api: ReturnType<typeof asFieldApi>,
  row: outboxQ.OutboxRow,
  token: string,
  opts: SendOptions,
  summary: SendSummary,
  add: (t: ReceiptTally) => void,
): Promise<boolean | 'refused'> {
  const payload = fromJson<Record<string, unknown>>(row.payload) ?? {};
  const location =
    row.lat !== null && row.lng !== null && row.accuracy_m !== null && row.fix_at !== null
      ? { lat: row.lat, lng: row.lng, accuracy_m: row.accuracy_m, fix_at: row.fix_at }
      : null;
  const call = doorCallFor(row.kind, payload, row.work_order_id, {
    key: row.id,
    capturedAt: row.captured_at,
    location,
    captorId: row.technician_id,
  });
  const send = deviceWide(db, 'send');
  db.transaction(() => outboxQ.markSending(send, [row.id]));
  summary.batches += 1;
  try {
    if (!api) throw new TransportError('endpoint_missing', 'this transport has no field doors');
    if (!call) throw new TransportError('endpoint_missing', `no door for this ${row.kind}`);
    const answer = await callDoor(api, call, row.id, token);
    const result = answer && answer.duplicate === true ? 'duplicate' : 'accepted';
    if (call.door === 'accept') {
      // The job is accepted: what the server sent back for want of that goes
      // again in this same run, behind the accept (DEF-FLD-10579).
      outboxQ.requeueRefusedForAcceptance(scoped(db, row.technician_id), call.jobId);
    }
    add(
      applyBatchAnswer(
        db,
        [row],
        {
          accepted: result === 'accepted' ? 1 : 0,
          duplicate: result === 'duplicate' ? 1 : 0,
          refused: 0,
          acknowledged: [row.id],
          items: [{ key: row.id, kind: row.kind, seq: row.seq, result, ack: true, detail: answer ?? null }],
        },
        opts.clock.now(),
        opts.random,
      ),
    );
    return true;
  } catch (err) {
    const e = err instanceof TransportError ? err : new TransportError('network', String(err));
    if (captorTokenRefused(e)) {
      // The server read the CAPTOR's token and refused it — expired, or the
      // office signed that handset out. The courier's own sign-in is fine, so
      // this stops nobody else's work: the item waits for its captor to sign
      // in again and get a fresh token; its key then makes a repeat harmless.
      waitForCaptor(db, [row]);
      summary.waitingForCaptor += 1;
      summary.unanswered += 1;
      return false;
    }
    const tally = applyBatchFailure(db, [row], e, opts.clock.now(), opts.random);
    add(tally);
    if (e.kind === 'auth') summary.stoppedForAuth = true;
    if (e.kind === 'app_too_old') summary.stoppedForUpdate = true;
    return tally.refused > 0 ? 'refused' : false;
  }
}

/** A 401/403 naming the CAPTURE token (`work.mobile.capture_token_*`), not the session. */
function captorTokenRefused(e: TransportError): boolean {
  if (e.kind !== 'auth') return false;
  const key = (e.body as { message_key?: unknown } | null | undefined)?.message_key;
  return typeof key === 'string' && key.startsWith('work.mobile.capture_token_');
}

/** FF-50: the technician acts on a refusal and sends it again, same key. */
export function resendRefused(db: TenantDb, technicianId: string, key: string): boolean {
  return outboxQ.requeueRefused(scoped(db, technicianId), key) === 1;
}
