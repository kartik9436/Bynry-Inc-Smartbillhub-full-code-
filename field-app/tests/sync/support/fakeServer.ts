/**
 * A fake of the server's mobile contract, faithful to `apps/work/sync.py`,
 * `apps/work/photo_links.py` and `apps/work/mobile.changes` in the ways the
 * engine depends on:
 *   - one receipt per (job, key): a second sight of a key is `duplicate`, and
 *     applies nothing — the server's unique constraint;
 *   - items applied in the order sent;
 *   - a refused item's receipt is rolled back (its savepoint), so the same key
 *     may come again;
 *   - `acknowledged` lists every key except refused ones;
 *   - a photo declaration creates a link carrying the sha256; bytes whose hash
 *     differs are refused 409; accepted bytes are `staged` (durable).
 * And it can be told to die mid-batch, which is the point of T-45.
 *
 * The job bundle (`GET work/mobile/jobs/{id}`, `mobile.bundle`) answers from
 * `bundles`; `helpBundle` builds one whose `help` is in the server's own
 * `_help_row` shape — `{id, seq, kind, label, ref, url}`, where a document's
 * `ref` is its stored-document id and `url` a pre-signed link, a link's `url`
 * is its own https address, and a phone's number is in `ref` with `url` null
 * (DEF-FLD-10581). `documentFiles` holds the bytes behind each link.
 */
import { createHash } from 'crypto';

import type { WireBundle, WireHelp } from '../../../src/sync/fieldApi';
import {
  TransportError,
  type BatchAnswer,
  type ChangesPage,
  type ItemAnswer,
  type PhotoAnswer,
  type PhotoUpload,
  type JobCard,
  type Transport,
  type WireItem,
} from '../../../src/sync/transport';
import serverJob from './serverJob.json';

export interface AppliedItem {
  group: string;
  key: string;
  kind: string;
  seq: number;
  captor: string | null;
  payload: Record<string, unknown>;
}

export class FakeServer implements Transport {
  /** Every item the server APPLIED, in application order. */
  readonly applied: AppliedItem[] = [];
  readonly receipts = new Set<string>();
  readonly requests: { group: string; size: number }[] = [];
  duplicatesAnswered = 0;
  /** Request numbers (1-based, data batches only) that die after N items applied. */
  killPlan = new Map<number, number>();
  /** Answer a key `refused` while this returns true. */
  refuseWhen: (item: WireItem) => boolean = (item) => item.payload['refuse'] === true;
  /** Answer `held_for_review` for these kinds. */
  holdKinds = new Set<string>();
  authFails = false;
  inFlight = 0;
  maxInFlight = 0;
  routeEndpointExists = true;

  // photos
  readonly links = new Map<string, { sha256: string; state: 'pending' | 'staged' | 'landed' }>();
  readonly photoBytes = new Map<string, string>();
  photoPutFails = new Map<string, TransportError>();
  answerPhotoPending = false;
  readonly photoRequests: string[] = [];
  photosInFlight = 0;
  maxPhotosInFlight = 0;
  /** What the "disk" holds for each local path (the bytes a PUT reads). */
  readonly disk = new Map<string, string>();

  // the job bundle and the help documents behind its links
  readonly bundles = new Map<string, WireBundle>();
  /** Pre-signed link → the bytes it serves. */
  readonly documentFiles = new Map<string, string>();
  /** FB-031 — our own route's address prefix, and the credential it wants. */
  static readonly API = 'https://api.example.test/api/proof/';
  static readonly TOKEN = 'Bearer proof-token';

  /** FB-031 — `HttpTransport.fileRequest`'s shape: our own path, the tenant's address, the credential. */
  fileRequest(path: string): { url: string; headers: Record<string, string> } | null {
    return { url: `${FakeServer.API}${path.replace(/^\/+/, '')}`, headers: { Authorization: FakeServer.TOKEN, 'X-App-Build': 'proof' } };
  }

  // change feed
  pages: ChangesPage[] = [];
  readonly cursorsSeen: (string | null)[] = [];


  private requestNo = 0;

  private async batch(group: string, items: WireItem[]): Promise<BatchAnswer> {
    if (this.authFails) throw new TransportError('auth', 'HTTP 401', 401);
    this.requestNo += 1;
    this.requests.push({ group, size: items.length });
    this.inFlight += 1;
    this.maxInFlight = Math.max(this.maxInFlight, this.inFlight);
    try {
      await new Promise((r) => setTimeout(r, 1)); // let other batches start
      if (items.length > 200) throw new TransportError('http', 'too many items', 400);
      const killAfter = this.killPlan.get(this.requestNo);
      const answers: ItemAnswer[] = [];
      for (const [i, item] of items.entries()) {
        if (killAfter !== undefined && i >= killAfter) {
          throw new TransportError('network', `connection dropped in request ${this.requestNo} after ${killAfter} items`);
        }
        const receiptKey = `${group}|${item.key}`;
        if (this.receipts.has(receiptKey)) {
          this.duplicatesAnswered += 1;
          answers.push({ key: item.key, kind: item.kind, seq: item.seq, result: 'duplicate', ack: true });
          continue;
        }
        if (this.refuseWhen(item)) {
          answers.push({
            key: item.key,
            kind: item.kind,
            seq: item.seq,
            result: 'refused',
            detail: { code: 'BIZ-LOCKED', message_key: 'work.safety.locked' },
          });
          continue;
        }
        this.receipts.add(receiptKey);
        this.applied.push({
          group,
          key: item.key,
          kind: item.kind,
          seq: item.seq,
          captor: item.capture_token ?? null,
          payload: item.payload,
        });
        let detail: Record<string, unknown> | null = null;
        if (item.kind === 'photo') {
          const id = String(item.payload['photo_id']);
          if (!this.links.has(id)) this.links.set(id, { sha256: String(item.payload['sha256']), state: 'pending' });
          detail = { photo_id: id, upload_url: `/api/north/work/mobile/photos/${id}`, state: 'pending' };
        }
        const result = this.holdKinds.has(item.kind) ? 'held_for_review' : 'accepted';
        answers.push({ key: item.key, kind: item.kind, seq: item.seq, result, ack: true, detail });
      }
      return {
        accepted: answers.filter((a) => a.result === 'accepted').length,
        duplicate: answers.filter((a) => a.result === 'duplicate').length,
        refused: answers.filter((a) => a.result === 'refused').length,
        held_for_review: answers.filter((a) => a.result === 'held_for_review').length,
        acknowledged: answers.filter((a) => a.ack).map((a) => a.key),
        items: answers,
      };
    } finally {
      this.inFlight -= 1;
    }
  }

  sendJobBatch(workOrderId: string, items: WireItem[]): Promise<BatchAnswer> {
    return this.batch(`job:${workOrderId}`, items);
  }

  sendRouteReads(routeId: string, items: WireItem[]): Promise<BatchAnswer> {
    if (!this.routeEndpointExists) {
      return Promise.reject(new TransportError('endpoint_missing', 'route readings: no server endpoint yet'));
    }
    return this.batch(`route:${routeId}`, items);
  }

  async putPhoto(upload: PhotoUpload): Promise<PhotoAnswer> {
    this.photoRequests.push(upload.photoId);
    this.photosInFlight += 1;
    this.maxPhotosInFlight = Math.max(this.maxPhotosInFlight, this.photosInFlight);
    try {
      await new Promise((r) => setTimeout(r, 1));
      const fail = this.photoPutFails.get(upload.photoId);
      if (fail) throw fail;
      const link = this.links.get(upload.photoId);
      if (!link) throw new TransportError('http', 'HTTP 404', 404);
      if (link.state !== 'pending') return { photo_id: upload.photoId, state: link.state, duplicate: true };
      const bytes = this.disk.get(upload.localPath) ?? '';
      if (createHash('sha256').update(bytes).digest('hex') !== link.sha256) {
        throw new TransportError('http', 'HTTP 409', 409, { message_key: 'work.photo.hash_mismatch' });
      }
      if (this.answerPhotoPending) return { photo_id: upload.photoId, state: 'pending', duplicate: false };
      link.state = 'staged';
      this.photoBytes.set(upload.photoId, bytes);
      return { photo_id: upload.photoId, state: 'staged', attachment_id: null, duplicate: false };
    } finally {
      this.photosInFlight -= 1;
    }
  }

  async photoState(photoId: string): Promise<PhotoAnswer | null> {
    const link = this.links.get(photoId);
    return link ? { photo_id: photoId, state: link.state } : null;
  }

  /** `mobile.bundle` — a job this server does not hold is a 404, as the real one answers. */
  async jobBundle(jobId: string): Promise<WireBundle> {
    const b = this.bundles.get(jobId);
    if (!b) throw new TransportError('http', 'HTTP 404', 404);
    return b;
  }

  async changes(cursor: string | null, _pageSize: number): Promise<ChangesPage> {
    this.cursorsSeen.push(cursor);
    const index = cursor === null ? 0 : Number(cursor.replace('c', ''));
    const page = this.pages[index];
    if (!page) return { changes: [], count: 0, next_cursor: cursor, has_more: false };
    return page;
  }
}

export function sha256(text: string): string {
  return createHash('sha256').update(text).digest('hex');
}

/**
 * The REAL server shapes (DEF-FLD-10582): `serverJob.json` is one job card and
 * one bundle as `apps/work/mobile.py` sends them, and
 * `06-backend/tests/test_def_fld_10582_job_card_meter_point.py` fails when the
 * server's keys drift from it. Build sync tests from these, never from a card
 * typed by hand — MQ-015 hid in exactly that gap.
 */
export function serverCard(over: Partial<JobCard> = {}): JobCard {
  return { ...(JSON.parse(JSON.stringify(serverJob.card)) as JobCard), ...over };
}

/** The bundle for `card`, carrying it under `card` exactly as the server does. */
export function serverBundle(card: JobCard = serverCard(), over: Record<string, unknown> = {}): WireBundle {
  const bundle = JSON.parse(JSON.stringify(serverJob.bundle)) as WireBundle;
  return { ...bundle, order_id: card.id, order_no: card.order_no ?? null, card, ...over };
}

/**
 * A job bundle carrying the three help kinds a technician taps — an SOP, the
 * supervisor's number and a video link — exactly as `mobile._help_row` sends
 * them; the SOP's bytes are put behind its link on `server`.
 */
export function helpBundle(server: FakeServer, orderId: string, extra: Partial<WireBundle> = {}): WireBundle {
  const sopUrl = `https://files.example.test/stored/${orderId}-sop.pdf?X-Amz-Expires=14400&X-Amz-Signature=abc`;
  server.documentFiles.set(sopUrl, `%PDF-1.7 shut-off SOP for ${orderId}`);
  const help: WireHelp[] = [
    { id: `${orderId}-h1`, seq: 1, kind: 'document', label: 'Water shut-off SOP', ref: '0192a7c4-5b1e-7d2a-9c11-000000000001', url: sopUrl },
    { id: `${orderId}-h2`, seq: 2, kind: 'phone', label: 'Supervisor', ref: '(512) 555-0142', url: null },
    { id: `${orderId}-h3`, seq: 3, kind: 'link', label: 'Meter swap video', ref: 'https://video.example.test/meter-swap', url: 'https://video.example.test/meter-swap' },
  ];
  const b: WireBundle = {
    order_id: orderId,
    order_no: orderId.toUpperCase(),
    template_id: null,
    template_version: null,
    safety: [],
    tasks: [],
    readings: [],
    materials: [],
    help,
    ...extra,
  };
  server.bundles.set(orderId, b);
  return b;
}
