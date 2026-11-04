/**
 * The second phase: photograph BYTES (Mobile data §5, R51–R55, R61, R123–R125).
 *
 *  - Declared first, with the data (`outbox.capture` writes a `photo` item
 *    carrying the id and sha256); a photograph is eligible here only once the
 *    server has acknowledged that declaration and so has a link for it.
 *  - One at a time, oldest first, resumable; a failure backs off THAT photo
 *    and the queue moves to the next (R53).
 *  - Binary multipart, one per request, never base64 (R124) — `transport.ts`.
 *  - Any connection, mobile data or wi-fi, unless *Photos on wi-fi only* is
 *    on (`allowMobileData` false). PO 2026-10-28, FB-015 option A — R54's
 *    wi-fi-by-default is SUPERSEDED; the runtime reads the switch through
 *    `screens/me/prefs.ts` `photosWifiOnly()`.
 *  - A photo is CONFIRMED only when the server says the bytes are DURABLY
 *    stored — `staged` (in PostgreSQL, committed, before the filing job is
 *    enqueued) or `landed` — never because a request was sent (R61, R125).
 *    Then the row is marked uploaded, keeping its remote id.
 *  - ⚠ FB-030 (PO 2026-10-31, *"keep photos only for 3 days"*) SUPERSEDES
 *    R61's "delete on receipt": the FILE is KEPT, so the record shows it,
 *    and the start-up purge deletes it 3 days after its job closed or its
 *    route was turned in (`db/purge.ts`, `photo.photoFilesDue`) — never
 *    before this confirmation, which is R61's half that stands.
 */
import type { TenantDb } from '../db/database';
import * as photoQ from '../db/queries/photo';
import { deviceWide } from '../db/scoped';
import { nextAttemptAt } from './backoff';
import type { Clock } from './outbox';
import { TransportError, type LinkState, type PhotoAnswer, type Transport } from './transport';

/** What "the server has the bytes" means. Anything else keeps the file. */
export const DURABLE_LINK_STATES: readonly LinkState[] = ['staged', 'landed'];

export interface FileStore {
  exists(path: string): Promise<boolean>;
  delete(path: string): Promise<void>;
}

export type NetworkKind = 'wifi' | 'cellular' | 'none';

export interface PhotoOptions {
  clock: Clock;
  network: NetworkKind;
  /** `!photosWifiOnly(prefs)` — true unless FF-51's *Photos on wi-fi only* is on (PO 2026-10-28). */
  allowMobileData?: boolean;
  random?: () => number;
  /** Observes each upload — tests use it to prove one in flight. */
  onUpload?: (info: { photoId: string; inFlight: number }) => void;
}

export interface PhotoSummary {
  uploaded: number;
  failed: number;
  waitingForWifi: boolean;
  stoppedForAuth: boolean;
  /** The server refused this build (`app_too_old`): the photo is released, the file kept. */
  stoppedForUpdate?: boolean;
}

function isDurable(answer: PhotoAnswer | null): boolean {
  return answer !== null && DURABLE_LINK_STATES.includes(answer.state);
}

export async function uploadPhotos(
  db: TenantDb,
  transport: Transport,
  files: FileStore,
  opts: PhotoOptions,
): Promise<PhotoSummary> {
  const summary: PhotoSummary = { uploaded: 0, failed: 0, waitingForWifi: false, stoppedForAuth: false };
  if (opts.network === 'none') return summary;
  if (opts.network === 'cellular' && !opts.allowMobileData) {
    summary.waitingForWifi = true;
    return summary;
  }
  const send = deviceWide(db, 'send');
  const receipt = deviceWide(db, 'receipt');
  let after: { capturedAt: string; id: string } | null = null;
  let inFlight = 0;

  const fail = (id: string, error: string): void => {
    const failures = photoQ.attemptsOf(receipt, id) + 1;
    photoQ.markFailed(receipt, id, nextAttemptAt(opts.clock.now(), failures, opts.random), error);
    summary.failed += 1;
  };

  const confirm = (p: photoQ.PhotoRow, answer: PhotoAnswer): void => {
    // FB-030: the file is KEPT (the purge takes it 3 days after the close or
    // the turn-in); only the row is marked.
    photoQ.markUploaded(receipt, p.id, answer.attachment_id ?? answer.photo_id, opts.clock.now().toISOString());
    summary.uploaded += 1;
  };

  for (;;) {
    const page = photoQ.dueForUpload(send, opts.clock.now().toISOString(), after, 20);
    if (page.length === 0) break;
    for (const p of page) {
      after = { capturedAt: p.captured_at, id: p.id };
      photoQ.markUploading(send, p.id);
      inFlight += 1;
      opts.onUpload?.({ photoId: p.id, inFlight });
      try {
        if (!(await files.exists(p.local_path))) {
          // The file is gone (a crash between delete and mark, last time). Ask
          // the server whether it has the bytes before saying anything.
          const state = await transport.photoState(p.id, p.upload_url);
          if (state !== null && isDurable(state)) {
            photoQ.markUploaded(receipt, p.id, state.attachment_id ?? state.photo_id, opts.clock.now().toISOString(), true);
            summary.uploaded += 1;
          } else {
            fail(p.id, 'file_missing');
          }
          continue;
        }
        const answer = await transport.putPhoto({
          photoId: p.id,
          uploadUrl: p.upload_url,
          localPath: p.local_path,
          sha256: p.sha256,
          contentType: 'image/jpeg',
        });
        if (isDurable(answer)) confirm(p, answer);
        else fail(p.id, `not_durable:${answer.state}`);
      } catch (err) {
        const e = err instanceof TransportError ? err : new TransportError('network', String(err));
        if (e.kind === 'auth') {
          photoQ.release(receipt, p.id);
          summary.stoppedForAuth = true;
          return summary;
        }
        if (e.kind === 'app_too_old') {
          photoQ.release(receipt, p.id);
          summary.stoppedForUpdate = true;
          return summary;
        }
        // 409 hash mismatch → send again later; 404 → the link is not there
        // yet; network → later. The file is kept in every case.
        fail(p.id, e.status ? `HTTP ${e.status}` : e.message);
      } finally {
        inFlight -= 1;
      }
    }
  }
  return summary;
}
