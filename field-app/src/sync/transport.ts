/**
 * The wire. Every server call the sync engine makes goes through `Transport`,
 * so the engine is tested against a fake (`tests/sync/support/fakeServer.ts`)
 * that behaves like the real contract, and runs on the handset against
 * `HttpTransport`.
 *
 * THE CONTRACT IS THE SERVER'S, READ FROM THE CODE ON 2026-10-21:
 *   POST /api/<tenant>/work/mobile/jobs/<id>/sync   `apps/work/sync.py sync_batch`
 *        {items:[{key, kind, seq, captured_at, payload, location?, capture_token?}]}
 *        → {accepted, duplicate, refused, held_for_review, acknowledged:[key],
 *           items:[{key, kind, seq, result, ack?, detail?}], synced_at}
 *        ONE JOB PER CALL; at most 200 items (`MAX_ITEMS`); applied in the
 *        order sent, never re-sorted; a savepoint per item.
 *   PUT  /api/<tenant>/work/mobile/photos/<photo_id>  `photo_links.receive_bytes`
 *        multipart `file` → {photo_id, upload_url, state, attachment_id, duplicate}
 *        409 `work.photo.hash_mismatch` when the bytes are not the declared ones.
 *   GET  same address → the link's state (`pending` · `staged` · `landed`).
 *   GET  /api/<tenant>/work/mobile/changes?cursor=&page_size=  `mobile.changes`
 *        → {changes:[{change:'upsert', order_id, at, job} | {change:'removed', order_id, at}],
 *           count, next_cursor, has_more}
 *   GET  /api/<tenant>/work/mobile/reconciliation  `mobile.reconciliation`
 *
 *   POST /api/<tenant>/work/mobile/reads/sync    `metering/field_reads.sync_reads`
 *        (route readings, at most 50 per call; mapped both ways in `routeReads.ts`)
 *   GET  …/work/mobile/routes, …/routes/<id>, POST …/routes/<id>/turn-in,
 *   GET  …/work/mobile/cant-read-reasons            `metering/field_reads_api.py`
 *        (the route mode's downloads and turn-in, `routes.ts`)
 *
 * EVERY REQUEST HAS A TIME LIMIT (DEF-FLD-10608, decision log 2026-10-26
 * FA-10): `CALL_TIME_LIMIT_MS` (30 s) for a call, `TRANSFER_TIME_LIMIT_MS`
 * (2 min) for a photograph's bytes, both configurable on `HttpTransportConfig`.
 * A call with no answer by then is aborted and raised as a NETWORK
 * `TransportError` (`TimeLimitError`) — exactly what a dropped connection
 * raises, so the outbox retries it with backoff and every screen reads it as
 * *no signal*. Before this a hung call held the sync forever and FF-08 sat at
 * *Loading* with nothing to retry.
 *
 * EVERY REQUEST carries the build (`X-Field-App-Version`, `-Build`, `-Platform`,
 * `release/appUpdate.ts`); a 426 `app_too_old` is `TransportError('app_too_old')`
 * and raises *Update the app* (DEF-FLD-10355, 07-endpoints N7).
 *
 * AND THE ONLINE DOORS (`fieldApi.ts`, lane INTEGRATE-2): nearby, claim,
 * alerts, reopen, money, the job bundle, acts, labour, crew, hand-back, field
 * raise, asset search and the template catalogue.
 *
 * ⚠ WHAT THE SERVER DOES NOT HAVE YET (each stubbed below by name, never guessed):
 *   - a door for remarks, asset papers, admin (non-job) time and a route
 *     finding — those kinds are captured on the `unrouted` channel and wait.
 *     (A crew member leaving and a correction for another person went to the
 *     crew and labour doors with lane S-GAPS.)
 *   - a change feed for anything but work orders (routes, assets, templates).
 */

import { appUpdate, fieldAppHeaders, SCHEMA_HEADER, tooOldMinimum } from '../release/appUpdate';
import { requireServer } from '../release/serverAddress';
import { isCertificateRefusal } from '../security/certificateRefusal';
import { DEVICE_TIME_HEADER, recordServerTime, SERVER_TIME_HEADER } from './deviceClock';
import type { DoorExtra, FieldApi, LabourMoments, WireAlert, WireAssetHit, WireBundle, WireFinding, WireFindingOptions, WireJobMoney, WireNearbyCard, WirePage, WireStepStopped, WireTemplate } from './fieldApi';
import { batchAnswerFromReads, routeItemFromWire, type ServerReadsAnswer } from './routeReads';
import type { RouteStopsPage, RoutesApi, RoutesPage, ServedReadFormatVersion, TurnInBody } from './routes';
import type { HistoryPage } from './routeHistory';
import type { ShiftsApi, WireWeek } from './shifts';
import type { WireAvailability, WireAvailabilityStatus } from './availability';

export interface WireLocation {
  lat: number;
  lng: number;
  accuracy_m: number;
  fix_at: string;
}

export interface WireItem {
  key: string;
  kind: string;
  seq: number;
  captured_at: string;
  payload: Record<string, unknown>;
  location?: WireLocation;
  capture_token?: string;
}

export type ItemResult = 'accepted' | 'duplicate' | 'refused' | 'held_for_review';

export interface ItemAnswer {
  key: string;
  kind: string;
  seq: number;
  result: ItemResult;
  ack?: boolean;
  detail?: Record<string, unknown> | null;
}

export interface BatchAnswer {
  work_order_id?: string;
  accepted: number;
  duplicate: number;
  refused: number;
  held_for_review?: number;
  acknowledged: string[];
  items: ItemAnswer[];
  synced_at?: string;
}

export type LinkState = 'pending' | 'staged' | 'landed';

export interface PhotoAnswer {
  photo_id: string;
  upload_url?: string;
  state: LinkState;
  attachment_id?: string | null;
  duplicate?: boolean;
}

/**
 * The meter a job is about (`mobile._meter_of`, DEF-FLD-10582) — read live by
 * the server on every card, so a meter exchanged there is the new one here on
 * the next sync. No badge: which asset field IS the badge is undecided.
 */
export interface JobCardMeter {
  id: string;
  asset_no?: string | null;
  serial_no?: string | null;
  model?: string | null;
  size_class?: string | null;
  service?: string | null;
}

/** Where the job is (`selectors._premise_of`): the unit's own point where it
 *  has one, else the building's, and which (hard rule 8, BR-MET-1162). The
 *  coordinates are the column's NUMERIC strings. */
export interface JobCardPremise {
  id: string;
  premise_no?: string | null;
  address?: string | null;
  lat?: string | null;
  lng?: string | null;
  position_source?: 'unit' | 'premises' | null;
}

export interface JobCard {
  id: string;
  order_no?: string | null;
  type?: string | null;
  premise?: JobCardPremise | null;
  meter?: JobCardMeter | null;
  window_start?: string | null;
  window_end?: string | null;
  due_at?: string | null;
  est_minutes?: number | null;
  priority?: { code?: string | null; rank?: number | null } | null;
  state?: string | null;
  dispatch_state?: string | null;
  access_notes?: string | null;
  hazards?: string | null;
  gate_code?: string | null;
  /** FB-030 — a job closed anywhere arrives with when and how (`mobile._job_card`). */
  completed_at?: string | null;
  outcome?: string | null;
  /** The office's acceptance of the close (BR-MET-110); kept in `extra`, read by `acceptedAt`. */
  accepted_at?: string | null;
  [unknown: string]: unknown;
}

export type Change =
  | { change: 'upsert'; order_id: string; at: string; job: JobCard }
  | { change: 'removed'; order_id: string; at: string };

export interface ChangesPage {
  changes: Change[];
  count: number;
  next_cursor: string | null;
  has_more: boolean;
  /**
   * The wire's schema version (R117). The server sends it as the
   * `X-Field-Schema-Version` header on every field answer (DEF-FLD-10355);
   * `changes()` copies it here when the body does not carry one, so
   * `delta.ts` refuses a version this build does not know.
   */
  schema_version?: number;
  /** FB-023 F3 — who is syncing: `employee` sees money, `contractor` does not
   *  (`money.employment_of`). Absent on an older server. */
  technician?: { employment?: string | null } | null;
}

/**
 * `certificate` — the phone refused the server's certificate (pinning, or a
 * chain it does not trust; `security/certificateRefusal.ts`). Nothing was
 * sent, so the outbox treats it as a dropped connection (retried with
 * backoff), and a screen says *Can't verify the server* — never *No signal*
 * (`DEF-FLD-10617`).
 *
 * `endpoint_missing` from the wire — a 404/405 whose body is not JSON (an
 * HTML page): the door is not on this server, which predates the build.
 * Sending waits (`receipts.ts`), nothing is refused, and FF-08 says *The
 * server needs an update* (`DEF-FLD-10617`). A JSON 404 stays `http`: that
 * is the server's own answer about the item.
 *
 * `app_too_old` — the server refused THIS BUILD (426, DEF-FLD-10355): not a
 * failure of any item, so nothing is marked refused; sending waits for the
 * update (`receipts.ts`) and *Update the app* is shown (`release/appUpdate.ts`).
 */
export type TransportErrorKind = 'network' | 'certificate' | 'auth' | 'http' | 'endpoint_missing' | 'app_too_old';

export class TransportError extends Error {
  constructor(
    readonly kind: TransportErrorKind,
    message: string,
    readonly status?: number,
    readonly body?: unknown,
  ) {
    super(message);
    this.name = 'TransportError';
  }
}

/**
 * Why a step of a sync did not finish, kept as data so a screen can say it in
 * words (FF-08's reason line): the error's kind and status, never its text.
 */
export interface SyncFailure {
  kind: TransportErrorKind;
  status?: number;
  message: string;
}

/** A thrown error as a `SyncFailure`; anything not from the wire reads as the server's (`http`). */
export function failureOf(err: unknown): SyncFailure {
  if (err instanceof TransportError) return { kind: err.kind, ...(err.status !== undefined ? { status: err.status } : {}), message: err.message };
  return { kind: 'http', message: err instanceof Error ? err.message : String(err) };
}

/** A call's time limit: 30 s (decision log 2026-10-26, FA-10). */
export const CALL_TIME_LIMIT_MS = 30_000;
/** A photograph's or a document's bytes: longer, they are megabytes on a weak signal. */
export const TRANSFER_TIME_LIMIT_MS = 120_000;

/**
 * No answer inside the time limit. A NETWORK error on purpose — the outbox
 * retries it with backoff (`receipts.ts`, the connection-died branch) and a
 * screen reads it as *no signal*, the same as a dropped connection.
 */
export class TimeLimitError extends TransportError {
  constructor(readonly limitMs: number) {
    super('network', `no answer in ${limitMs} ms`);
    this.name = 'TimeLimitError';
  }
}

/**
 * Runs `work` with an abort signal and a time limit. The limit wins even when
 * the work ignores its signal (a fetch that never settles), so the caller is
 * ALWAYS answered by `ms`; `onTimeout` lets a caller cancel what the signal
 * cannot reach (a native download).
 */
export function withTimeLimit<T>(work: (signal: AbortSignal) => Promise<T>, ms: number, onTimeout?: () => void): Promise<T> {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const limit = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      reject(new TimeLimitError(ms));
      controller.abort();
      try {
        onTimeout?.();
      } catch {
        // cancelling is best effort; the caller already has its answer
      }
    }, ms);
  });
  return Promise.race([work(controller.signal), limit]).finally(() => clearTimeout(timer));
}

export interface PhotoUpload {
  photoId: string;
  uploadUrl: string | null;
  localPath: string;
  sha256: string;
  contentType: string;
}

export interface Transport {
  sendJobBatch(workOrderId: string, items: WireItem[]): Promise<BatchAnswer>;
  sendRouteReads(routeId: string, items: WireItem[]): Promise<BatchAnswer>;
  putPhoto(upload: PhotoUpload): Promise<PhotoAnswer>;
  photoState(photoId: string, uploadUrl?: string | null): Promise<PhotoAnswer | null>;
  changes(cursor: string | null, pageSize: number): Promise<ChangesPage>;
}

/**
 * The real one. `fetch` with the access token (Security §1: one hour, renewed
 * whenever there is a signal); the tenant is in the path and is resolved from
 * the credential server-side, never read from a body (R127).
 */
export interface HttpTransportConfig {
  origin: string;
  tenant: string;
  accessToken: () => string | null;
  fetchImpl?: typeof fetch;
  /** The build's headers on every request (default `fieldAppHeaders()`). */
  appHeaders?: () => Record<string, string>;
  /** Told when the server refuses this build (default: the app's one `appUpdate` signal). */
  onAppTooOld?: (minimum: string | null) => void;
  /** The phone's clock, sent as `X-Device-Time` on every call (FB-014; default `new Date()`). */
  now?: () => Date;
  /** A call's time limit (default `CALL_TIME_LIMIT_MS`, 30 s). */
  timeoutMs?: number;
  /** A photograph upload's time limit (default `TRANSFER_TIME_LIMIT_MS`, 2 min). */
  transferTimeoutMs?: number;
}

/**
 * An own-door body with the outbox item's extras (`DoorExtra`): `key`,
 * `capture_token`, `technician_id` — each only when present, so an online
 * call without them sends exactly what it sent before (rule 1, additive).
 */
export function withExtra<T extends object>(body: T, extra?: DoorExtra): T & Record<string, unknown> {
  const out: Record<string, unknown> = { ...(body as Record<string, unknown>) };
  if (extra?.key) out.key = extra.key;
  if (extra?.captureToken) out.capture_token = extra.captureToken;
  if (extra?.technicianId) out.technician_id = extra.technicianId;
  return out as T & Record<string, unknown>;
}

export class HttpTransport implements Transport, RoutesApi, FieldApi, ShiftsApi {
  private readonly fetchImpl: typeof fetch;

  constructor(private readonly cfg: HttpTransportConfig) {
    this.fetchImpl = cfg.fetchImpl ?? fetch;
  }

  /** Refuses (`NoServerError`) rather than build a relative `/api/…` address — see `release/serverAddress.ts`. */
  private url(path: string): string {
    return `${requireServer(this.cfg.origin)}/api/${encodeURIComponent(this.cfg.tenant)}/${path}`;
  }

  private async call<T>(url: string, init: RequestInit, limitMs?: number): Promise<T> {
    return (await this.callWithSchema<T>(url, init, limitMs)).body;
  }

  private async callWithSchema<T>(url: string, init: RequestInit, limitMs?: number): Promise<{ body: T; schema: number | undefined }> {
    const token = this.cfg.accessToken();
    if (!token) throw new TransportError('auth', 'no access token — sending waits for sign-in');
    // The limit covers the answer AND its body: a server that sends headers
    // and then stalls is as hung as one that never answers (DEF-FLD-10608).
    // FB-014 (DEF-FLD-10639): the phone's own clock at send, on EVERY call —
    // the server shifts every time in it onto its own clock and never refuses
    // a clock difference (`deviceClock.ts`).
    const clock = this.cfg.now ?? (() => new Date());
    const { res, body, json } = await withTimeLimit(async (signal) => {
      let answer: Response;
      const sentAt = clock();
      try {
        answer = await this.fetchImpl(url, {
          ...init,
          signal,
          headers: {
            ...(this.cfg.appHeaders ?? fieldAppHeaders)(),
            ...(init.headers as Record<string, string>),
            [DEVICE_TIME_HEADER]: sentAt.toISOString(),
            Authorization: `Bearer ${token}`,
          },
        });
        recordServerTime(sentAt, clock(), answer.headers?.get?.(SERVER_TIME_HEADER));
      } catch (err) {
        const message = err instanceof Error ? err.message : 'network error';
        throw new TransportError(isCertificateRefusal(err) ? 'certificate' : 'network', message);
      }
      let json = true;
      const parsed = await answer.json().catch(() => {
        json = false;
        return null;
      });
      return { res: answer, body: parsed, json };
    }, limitMs ?? this.cfg.timeoutMs ?? CALL_TIME_LIMIT_MS);
    const minimum = tooOldMinimum(res.status, body);
    if (minimum !== undefined) {
      (this.cfg.onAppTooOld ?? ((m) => appUpdate.raise(m)))(minimum);
      throw new TransportError('app_too_old', `HTTP ${res.status} app_too_old`, res.status, body);
    }
    if (res.status === 401 || res.status === 403) throw new TransportError('auth', `HTTP ${res.status}`, res.status, body);
    if (res.status >= 500) throw new TransportError('network', `HTTP ${res.status}`, res.status, body);
    // No such door on this server (an HTML 404/405): it needs an update (DEF-FLD-10617).
    if ((res.status === 404 || res.status === 405) && !json) {
      throw new TransportError('endpoint_missing', `HTTP ${res.status} not JSON — no such door on this server`, res.status, body);
    }
    if (!res.ok) throw new TransportError('http', `HTTP ${res.status}`, res.status, body);
    const header = res.headers?.get?.(SCHEMA_HEADER);
    const schema = header != null && /^\d+$/.test(header.trim()) ? Number(header.trim()) : undefined;
    return { body: body as T, schema };
  }

  sendJobBatch(workOrderId: string, items: WireItem[]): Promise<BatchAnswer> {
    return this.call(this.url(`work/mobile/jobs/${encodeURIComponent(workOrderId)}/sync`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items }),
    });
  }

  /** `POST work/mobile/reads/sync` — the route's readings, mapped both ways in `routeReads.ts`. */
  async sendRouteReads(routeId: string, items: WireItem[]): Promise<BatchAnswer> {
    const answer = await this.call<ServerReadsAnswer>(this.url('work/mobile/reads/sync'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: items.map((i) => routeItemFromWire(i, routeId)) }),
    });
    return batchAnswerFromReads(items, answer ?? {});
  }

  // ── The route mode's downloads and turn-in (`routes.ts`) ──────────────────
  myRoutes(page: number): Promise<RoutesPage> {
    return this.call(this.url(`work/mobile/routes?page=${page}`), { method: 'GET' });
  }

  routePage(routeId: string, page: number): Promise<RouteStopsPage> {
    return this.call(this.url(`work/mobile/routes/${encodeURIComponent(routeId)}?page=${page}`), { method: 'GET' });
  }

  turnIn(routeId: string, body: TurnInBody): Promise<unknown> {
    return this.call(this.url(`work/mobile/routes/${encodeURIComponent(routeId)}/turn-in`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  /** FB-030 — `GET work/mobile/reads/history?page=`: the reader's own turned-in reads, 14 days. */
  readsHistory(page: number): Promise<HistoryPage> {
    return this.call(this.url(`work/mobile/reads/history?page=${page}`), { method: 'GET' });
  }

  /**
   * FB-030 — where a photograph whose file has left the phone loads from, ON
   * TAP: the server's own-work-only door, with this sign-in's credential.
   * Shown, never stored (`Cache-Control: no-store`). Null with no sign-in or
   * no server address.
   */
  photoSource(kind: 'job' | 'route', photoId: string): { uri: string; headers: Record<string, string> } | null {
    const token = this.cfg.accessToken();
    if (!token) return null;
    const id = encodeURIComponent(photoId);
    try {
      const uri = this.url(kind === 'route' ? `work/mobile/reads/photos/${id}/content` : `work/mobile/photos/${id}/content`);
      return { uri, headers: { ...(this.cfg.appHeaders ?? fieldAppHeaders)(), Authorization: `Bearer ${token}` } };
    } catch {
      return null;
    }
  }

  cantReadReasons(): Promise<{ results: Array<{ code: string; name: string; active?: boolean }> }> {
    return this.call(this.url('work/mobile/cant-read-reasons'), { method: 'GET' });
  }

  readFormatVersion(versionId: string): Promise<ServedReadFormatVersion> {
    return this.call(this.url(`work/mobile/read-formats/versions/${encodeURIComponent(versionId)}`), { method: 'GET' });
  }

  putPhoto(upload: PhotoUpload): Promise<PhotoAnswer> {
    // Binary multipart, one photograph per request, never base64 (R124). In
    // React Native a `{uri, name, type}` part streams the file from disk.
    const form = new FormData();
    form.append('file', {
      uri: upload.localPath,
      name: `${upload.photoId}.jpg`,
      type: upload.contentType,
    } as unknown as Blob);
    const url = upload.uploadUrl
      ? `${requireServer(this.cfg.origin)}${upload.uploadUrl}`
      : this.url(`work/mobile/photos/${encodeURIComponent(upload.photoId)}`);
    return this.call(url, { method: 'PUT', body: form }, this.cfg.transferTimeoutMs ?? TRANSFER_TIME_LIMIT_MS);
  }

  async photoState(photoId: string, uploadUrl?: string | null): Promise<PhotoAnswer | null> {
    // A route photograph's link is the reads door's (DEF-FLD-10357): ask the
    // address its declaration answered, the job door's otherwise.
    const url = uploadUrl ? `${requireServer(this.cfg.origin)}${uploadUrl}` : this.url(`work/mobile/photos/${encodeURIComponent(photoId)}`);
    try {
      return await this.call(url, { method: 'GET' });
    } catch (err) {
      if (err instanceof TransportError && err.status === 404) return null;
      throw err;
    }
  }

  // ── The online doors (`fieldApi.ts`) ───────────────────────────────────
  private json(method: string, body: unknown): RequestInit {
    return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}) };
  }

  nearby(q: { lat: number; lng: number; radiusMi: number; page: number; per?: number }): Promise<WirePage<WireNearbyCard>> {
    const p = new URLSearchParams({ lat: String(q.lat), lng: String(q.lng), radius_mi: String(q.radiusMi), scope: 'all', page: String(q.page), per: String(q.per ?? 50) });
    return this.call(this.url(`work/mobile/nearby?${p.toString()}`), { method: 'GET' });
  }

  claim(jobId: string): Promise<{ order_id: string; already_yours?: boolean }> {
    return this.call(this.url(`work/mobile/jobs/${encodeURIComponent(jobId)}/claim`), this.json('POST', {}));
  }

  alerts(page: number): Promise<WirePage<WireAlert>> {
    return this.call(this.url(`work/mobile/alerts?page=${page}&per=50`), { method: 'GET' });
  }

  acknowledgeAlert(alertId: string): Promise<WireAlert> {
    return this.call(this.url(`work/mobile/alerts/${encodeURIComponent(alertId)}/ack`), this.json('POST', {}));
  }

  reopen(jobId: string, body: { reason: string; note?: string | null; key: string }): Promise<unknown> {
    return this.call(this.url(`work/mobile/jobs/${encodeURIComponent(jobId)}/reopen`), this.json('POST', body));
  }

  jobMoney(jobId: string): Promise<WireJobMoney> {
    return this.call(this.url(`work/mobile/jobs/${encodeURIComponent(jobId)}/money`), { method: 'GET' });
  }

  stepStopped(jobId: string, body: WireStepStopped): Promise<unknown> {
    return this.call(this.url(`work/mobile/jobs/${encodeURIComponent(jobId)}/step-stopped`), this.json('POST', body));
  }

  jobBundle(jobId: string): Promise<WireBundle> {
    return this.call(this.url(`work/mobile/jobs/${encodeURIComponent(jobId)}`), { method: 'GET' });
  }

  /** FB-031 — our own path (`/work/mobile/jobs/…/content`) as an address on
   *  this tenant's server, with the build's headers and the access token. */
  fileRequest(path: string): { url: string; headers: Record<string, string> } | null {
    const token = this.cfg.accessToken();
    if (!token) return null;
    return {
      url: this.url(path.replace(/^\/+/, '')),
      headers: {
        ...(this.cfg.appHeaders ?? fieldAppHeaders)(),
        [DEVICE_TIME_HEADER]: (this.cfg.now ?? (() => new Date()))().toISOString(),
        Authorization: `Bearer ${token}`,
      },
    };
  }

  jobAct(jobId: string, act: 'depart' | 'arrive', extra?: DoorExtra): Promise<unknown> {
    return this.call(this.url(`work/mobile/jobs/${encodeURIComponent(jobId)}/acts`), this.json('POST', withExtra({ act }, extra)));
  }

  recordLabour(jobId: string, moments: LabourMoments, extra?: DoorExtra): Promise<unknown> {
    return this.call(this.url(`work/mobile/jobs/${encodeURIComponent(jobId)}/labour`), this.json('PUT', withExtra(moments, extra)));
  }

  addCrew(jobId: string, body: { technician_id: string; key: string }, extra?: DoorExtra): Promise<unknown> {
    return this.call(this.url(`work/mobile/jobs/${encodeURIComponent(jobId)}/crew`), this.json('POST', withExtra(body, extra)));
  }

  leaveCrew(jobId: string, body: { technician_id: string; ended_at: string | null }, extra?: DoorExtra): Promise<unknown> {
    const leave = { act: 'leave', technician_id: body.technician_id, ...(body.ended_at ? { ended_at: body.ended_at } : {}) };
    return this.call(this.url(`work/mobile/jobs/${encodeURIComponent(jobId)}/crew`), this.json('POST', withExtra(leave, extra)));
  }

  handBack(jobId: string, body: { reason: string; note: string | null }, extra?: DoorExtra): Promise<unknown> {
    return this.call(this.url(`work/mobile/jobs/${encodeURIComponent(jobId)}/hand-back`), this.json('POST', withExtra(body, extra)));
  }

  acceptJob(jobId: string, extra?: DoorExtra): Promise<unknown> {
    return this.call(this.url(`work/mobile/jobs/${encodeURIComponent(jobId)}/accept`), this.json('POST', withExtra({}, extra)));
  }

  declineJob(jobId: string, body: { reason: string; note: string | null }, extra?: DoorExtra): Promise<unknown> {
    const decline = { reason: body.reason, ...(body.note ? { note: body.note } : {}) };
    return this.call(this.url(`work/mobile/jobs/${encodeURIComponent(jobId)}/decline`), this.json('POST', withExtra(decline, extra)));
  }

  raiseOrder(body: Record<string, unknown>, extra?: DoorExtra): Promise<{ order_id?: string; order_no?: string | null; duplicate?: boolean }> {
    return this.call(this.url('work/mobile/orders'), this.json('POST', withExtra(body, extra)));
  }

  searchAssets(q: string, page: number): Promise<WirePage<WireAssetHit>> {
    const p = new URLSearchParams({ q, page: String(page), per: '50' });
    return this.call(this.url(`work/mobile/assets/search?${p.toString()}`), { method: 'GET' });
  }

  templates(page: number): Promise<WirePage<WireTemplate>> {
    return this.call(this.url(`work/mobile/templates?page=${page}&page_size=100`), { method: 'GET' });
  }

  findingOptions(): Promise<WireFindingOptions> {
    return this.call(this.url('work/mobile/findings/options'), { method: 'GET' });
  }

  finding(key: string): Promise<WireFinding> {
    return this.call(this.url(`work/mobile/findings/${encodeURIComponent(key)}`), { method: 'GET' });
  }

  findingWorkOrder(key: string, body: { template_id: string; priority_id?: string }): Promise<WireFinding> {
    return this.call(this.url(`work/mobile/findings/${encodeURIComponent(key)}/work-order`), this.json('POST', body));
  }

  // ── The week, End shift, Submit the day (`shifts.ts`, CR-193-BRC10) ──────
  myWeek(from?: string): Promise<WireWeek> {
    const q = from ? `?from=${encodeURIComponent(from)}` : '';
    return this.call(this.url(`work/mobile/week${q}`), { method: 'GET' });
  }

  endShift(body: { at: string }, extra?: DoorExtra): Promise<unknown> {
    return this.call(this.url('work/mobile/shift/end'), this.json('POST', withExtra(body, extra)));
  }

  submitTimesheet(body: { date: string }, extra?: DoorExtra): Promise<unknown> {
    return this.call(this.url('work/mobile/timesheet/submit'), this.json('POST', withExtra(body, extra)));
  }

  // ── Availability (`availability.ts`, FB-033) ─────────────────────────────
  sendAvailability(body: { at: string; value: WireAvailability }, extra?: DoorExtra): Promise<unknown> {
    return this.call(this.url('work/mobile/availability'), this.json('POST', withExtra(body, extra)));
  }

  myAvailability(): Promise<WireAvailabilityStatus> {
    return this.call(this.url('work/mobile/availability'), { method: 'GET' });
  }

  /** `GET work/mobile/settings` — the settings the handset keeps (`security/pinning.ts`). */
  settings(): Promise<{ field_app_pins?: unknown }> {
    return this.call(this.url('work/mobile/settings'), { method: 'GET' });
  }

  async changes(cursor: string | null, pageSize: number): Promise<ChangesPage> {
    const q = new URLSearchParams({ page_size: String(pageSize) });
    if (cursor) q.set('cursor', cursor);
    const { body, schema } = await this.callWithSchema<ChangesPage>(this.url(`work/mobile/changes?${q.toString()}`), { method: 'GET' });
    return body && body.schema_version === undefined && schema !== undefined ? { ...body, schema_version: schema } : body;
  }
}
