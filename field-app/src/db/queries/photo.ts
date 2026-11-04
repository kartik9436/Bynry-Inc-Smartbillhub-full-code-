/**
 * `photo` — one row per photograph; the bytes are a FILE on disk (R52). Scoped.
 *
 * The file is deleted only when the server confirms the bytes are durably
 * stored (R61, R125), and the row is kept with its remote id afterwards, so the
 * gallery still shows it was taken. Never the other way round: a row without a
 * file is a gap; a file without a row is just bytes (Mobile data §10).
 */
import type { QueryRunner } from '../database';
import type { ScopedRunner } from '../scoped';
import type { PhotoState } from '../schema';

export interface PhotoRow {
  id: string;
  technician_id: string;
  outbox_id: string | null;
  declare_id: string | null;
  work_order_id: string | null;
  route_id: string | null;
  local_path: string;
  sha256: string;
  bytes: number;
  width: number | null;
  height: number | null;
  captured_by: string;
  captured_at: string;
  lat: number | null;
  lng: number | null;
  accuracy_m: number | null;
  state: PhotoState;
  attempts: number;
  next_attempt_at: string | null;
  last_error: string | null;
  upload_url: string | null;
  file_deleted: number;
  remote_id: string | null;
  uploaded_at: string | null;
  /** The reading this photograph proves (0006, DEF-FLD-10631); null for a job's. */
  route_read_id: string | null;
}

export interface NewPhotoRow {
  id: string;
  outboxId: string | null;
  declareId: string;
  workOrderId: string | null;
  /** The reading it is declared against — the declaration's own target. */
  routeReadId?: string | null;
  routeId: string | null;
  localPath: string;
  sha256: string;
  bytes: number;
  width?: number | null;
  height?: number | null;
  capturedBy: string;
  capturedAt: string;
  location: { lat: number; lng: number; accuracy_m: number } | null;
}

export function insert(s: ScopedRunner, row: NewPhotoRow): void {
  s.run(
    `INSERT INTO photo (id, technician_id, outbox_id, declare_id, work_order_id, route_id, local_path, sha256,
                        bytes, width, height, captured_by, captured_at, lat, lng, accuracy_m, route_read_id, state)
     VALUES (:id, :technician_id, :outbox_id, :declare_id, :work_order_id, :route_id, :local_path, :sha256,
             :bytes, :width, :height, :captured_by, :captured_at, :lat, :lng, :accuracy_m, :route_read_id, 'pending')`,
    {
      id: row.id,
      outbox_id: row.outboxId,
      declare_id: row.declareId,
      work_order_id: row.workOrderId,
      route_id: row.routeId,
      local_path: row.localPath,
      sha256: row.sha256,
      bytes: row.bytes,
      width: row.width,
      height: row.height,
      captured_by: row.capturedBy,
      captured_at: row.capturedAt,
      lat: row.location?.lat,
      lng: row.location?.lng,
      accuracy_m: row.location?.accuracy_m,
      route_read_id: row.routeReadId ?? null,
    },
  );
}

/**
 * FB-030 — a photograph the SERVER holds and this phone never had (a job or a
 * route refilled onto a new phone): a row with no file, already `uploaded`,
 * so the record shows it was taken and loads it on tap. Never overwrites a
 * row the phone already has (its own capture wins).
 */
export function insertRemote(
  s: ScopedRunner,
  row: { id: string; workOrderId?: string | null; routeId?: string | null; routeReadId?: string | null; capturedAt: string | null; at: string },
): void {
  s.run(
    `INSERT INTO photo (id, technician_id, work_order_id, route_id, route_read_id, local_path, sha256, bytes,
                        captured_by, captured_at, state, file_deleted, remote_id, uploaded_at)
     VALUES (:id, :technician_id, :work_order_id, :route_id, :route_read_id, '', '', 0,
             :technician_id, :captured_at, 'uploaded', 1, :id, :at)
     ON CONFLICT (id) DO NOTHING`,
    {
      id: row.id,
      work_order_id: row.workOrderId ?? null,
      route_id: row.routeId ?? null,
      route_read_id: row.routeReadId ?? null,
      captured_at: row.capturedAt ?? row.at,
      at: row.at,
    },
  );
}

export function getMine(s: ScopedRunner, id: string): PhotoRow | undefined {
  return s.get<PhotoRow>('SELECT * FROM photo WHERE technician_id = :technician_id AND id = :id', { id });
}

/** FF-50's own line for photographs (R65): counted, not weighed. */
export function countWaitingMine(s: ScopedRunner): number {
  return (
    s.get<{ n: number }>(
      `SELECT COUNT(*) AS n FROM photo WHERE technician_id = :technician_id AND state != 'uploaded'`,
    )?.n ?? 0
  );
}

// ── The upload phase (deviceWide 'send' / 'receipt') ─────────────────────────

/**
 * The next photographs to upload, oldest first (R53), page by page. A photo is
 * eligible only once the server has its DECLARATION (the `photo` item that
 * created its link, R123) — before that, there is nowhere to send the bytes.
 * A photo backing off is skipped, so one failure never blocks the next.
 */
export function dueForUpload(
  send: QueryRunner,
  now: string,
  after: { capturedAt: string; id: string } | null,
  limit: number,
): PhotoRow[] {
  return send.all<PhotoRow>(
    `SELECT p.* FROM photo p
       JOIN outbox d ON d.id = p.declare_id
      WHERE p.state IN ('pending','failed','uploading') AND p.file_deleted = 0
        AND d.state IN ('accepted','duplicate','held_for_review')
        AND COALESCE(p.next_attempt_at, '') <= :now
        AND (p.captured_at > :after_at OR (p.captured_at = :after_at AND p.id > :after_id))
      ORDER BY p.captured_at, p.id
      LIMIT :limit`,
    { now, after_at: after?.capturedAt ?? '', after_id: after?.id ?? '', limit },
  );
}

/** Photographs waiting for any reason, device-wide (the wi-fi wait line). */
export function countWaiting(device: QueryRunner): number {
  return device.get<{ n: number }>(`SELECT COUNT(*) AS n FROM photo WHERE state != 'uploaded'`)?.n ?? 0;
}

/** Photographs waiting, per technician, device-wide — the sign-out warning names
 *  everyone's unsent work under their own name (E2E-21, R64, R65). */
export function countWaitingByTechnician(device: QueryRunner): { technician_id: string; n: number }[] {
  return device.all(
    `SELECT technician_id, COUNT(*) AS n FROM photo WHERE state != 'uploaded' GROUP BY technician_id ORDER BY technician_id`,
  );
}

/** The link the server answered for this photo's declaration. */
export function setUploadUrlByDeclaration(receipt: QueryRunner, declareId: string, url: string | null): void {
  receipt.run('UPDATE photo SET upload_url = COALESCE(:url, upload_url) WHERE declare_id = :declare_id', {
    declare_id: declareId,
    url,
  });
}

export function markUploading(send: QueryRunner, id: string): void {
  send.run(`UPDATE photo SET state = 'uploading' WHERE id = :id`, { id });
}

/**
 * Durably received. FB-030 (PO 2026-10-31, R61 SUPERSEDED in part): the FILE
 * is KEPT — the record shows it for 3 days after its job closes or its route
 * is turned in, and the purge deletes it then (`photoFilesDue`). `fileGone`
 * is true only where the file was already missing when the server confirmed.
 */
export function markUploaded(receipt: QueryRunner, id: string, remoteId: string, at: string, fileGone = false): void {
  receipt.run(
    `UPDATE photo SET state = 'uploaded', remote_id = :remote_id, uploaded_at = :at,
            file_deleted = CASE WHEN :gone THEN 1 ELSE file_deleted END,
            last_error = NULL, next_attempt_at = NULL
      WHERE id = :id`,
    { id, remote_id: remoteId, at, gone: fileGone ? 1 : 0 },
  );
}

export function markFailed(receipt: QueryRunner, id: string, nextAttemptAt: string | null, error: string): void {
  receipt.run(
    `UPDATE photo SET state = 'failed', attempts = attempts + 1, next_attempt_at = :next, last_error = :error
      WHERE id = :id`,
    { id, next: nextAttemptAt, error },
  );
}

/**
 * DEF-FLD-10629 (FB-004, I): this technician's photographs that CANNOT upload
 * yet because the server has not answered their declaration (the act they
 * prove has not gone) — split by what they wait for. They are not
 * *uploading*, and FF-50's bar does not count them.
 */
export function awaitingDeclarationMine(s: ScopedRunner): { route: number; job: number } {
  const row = s.get<{ route: number | null; job: number | null }>(
    `SELECT SUM(CASE WHEN p.route_id IS NOT NULL AND p.work_order_id IS NULL THEN 1 ELSE 0 END) AS route,
            SUM(CASE WHEN p.route_id IS NOT NULL AND p.work_order_id IS NULL THEN 0 ELSE 1 END) AS job
       FROM photo p JOIN outbox d ON d.id = p.declare_id
      WHERE p.technician_id = :technician_id AND p.state != 'uploaded'
        AND d.state NOT IN ('accepted','duplicate','held_for_review')`,
  );
  return { route: row?.route ?? 0, job: row?.job ?? 0 };
}

/** A MANUAL *Sync now* (DEF-FLD-10624, C): this technician's photographs try again at once. */
export function clearBackoffMine(s: ScopedRunner): number {
  return s.run(
    `UPDATE photo SET next_attempt_at = NULL
      WHERE technician_id = :technician_id AND state IN ('pending','failed') AND next_attempt_at IS NOT NULL`,
  ).changes;
}

export function attemptsOf(receipt: QueryRunner, id: string): number {
  return receipt.get<{ attempts: number }>('SELECT attempts FROM photo WHERE id = :id', { id })?.attempts ?? 0;
}

/** An auth stop: back to pending without counting an attempt. */
export function release(receipt: QueryRunner, id: string): void {
  receipt.run(`UPDATE photo SET state = 'pending' WHERE id = :id AND state = 'uploading'`, { id });
}

// ── The purge ────────────────────────────────────────────────────────────────

/**
 * Uploaded rows whose file is gone, older than the cutoff, and whose job and
 * route have both left the handset. Nothing else: FB-030 — a photo row stays
 * as long as the record it belongs to (14 days), so the record shows it was
 * taken and loads it on tap.
 */
export function deleteUploadedBefore(purge: QueryRunner, cutoff: string): number {
  return purge.run(
    `DELETE FROM photo WHERE state = 'uploaded' AND file_deleted = 1 AND uploaded_at < :cutoff
        AND NOT EXISTS (SELECT 1 FROM work_order w
                         WHERE w.technician_id = photo.technician_id AND w.id = photo.work_order_id)
        AND NOT EXISTS (SELECT 1 FROM route r
                         WHERE r.technician_id = photo.technician_id AND r.id = photo.route_id)`,
    { cutoff },
  ).changes;
}

/**
 * FB-030 (PO 2026-10-31, *"keep photos only for 3 days"*) — photographs whose
 * FILE may go: the server confirmed the bytes (`uploaded`; never before, R61's
 * half that stands) and their job closed, or their route was turned in,
 * before the cutoff. An open job's or a walking route's photos stay. A photo
 * whose job and route have both left the handset (taken away by the office)
 * has no record to show it in: its file goes at `orphanCutoff` (7 days after
 * the upload, the sent-work figure), and its row after it.
 */
export function photoFilesDue(
  purge: QueryRunner,
  cutoff: string,
  limit: number,
  orphanCutoff: string = cutoff,
): { id: string; local_path: string }[] {
  return purge.all(
    `SELECT p.id, p.local_path FROM photo p
      WHERE p.state = 'uploaded' AND p.file_deleted = 0
        AND (EXISTS (SELECT 1 FROM work_order w
                      WHERE w.technician_id = p.technician_id AND w.id = p.work_order_id
                        AND w.closed_at IS NOT NULL AND w.closed_at < :cutoff)
          OR EXISTS (SELECT 1 FROM route r
                      WHERE r.technician_id = p.technician_id AND r.id = p.route_id
                        AND r.status = 'turned_in' AND r.turned_in_at < :cutoff)
          OR (p.uploaded_at < :orphan_cutoff
              AND NOT EXISTS (SELECT 1 FROM work_order w WHERE w.technician_id = p.technician_id AND w.id = p.work_order_id)
              AND NOT EXISTS (SELECT 1 FROM route r WHERE r.technician_id = p.technician_id AND r.id = p.route_id)))
      ORDER BY p.captured_at, p.id
      LIMIT :limit`,
    { cutoff, limit, orphan_cutoff: orphanCutoff },
  );
}

/** The file is gone from the handset; the row (and its remote id) stays. */
export function markFileDeleted(purge: QueryRunner, id: string): void {
  purge.run(`UPDATE photo SET file_deleted = 1 WHERE id = :id AND state = 'uploaded'`, { id });
}

/** Not yet confirmed at the server, for one order or route (the cascade's guard). */
export function unsentFor(s: ScopedRunner, target: { workOrderId?: string; routeId?: string }): number {
  return (
    s.get<{ n: number }>(
      `SELECT COUNT(*) AS n FROM photo
        WHERE technician_id = :technician_id AND state != 'uploaded'
          AND (work_order_id = :work_order_id OR route_id = :route_id)`,
      { work_order_id: target.workOrderId ?? null, route_id: target.routeId ?? null },
    )?.n ?? 0
  );
}

/** FB-030 — the files a cascade must delete before it drops the rows (uploaded, file still here). */
export function keptFilesFor(s: ScopedRunner, target: { workOrderId?: string; routeId?: string }): string[] {
  return s
    .all<{ local_path: string }>(
      `SELECT local_path FROM photo
        WHERE technician_id = :technician_id AND state = 'uploaded' AND file_deleted = 0 AND local_path != ''
          AND (work_order_id = :work_order_id OR route_id = :route_id)`,
      { work_order_id: target.workOrderId ?? null, route_id: target.routeId ?? null },
    )
    .map((r) => r.local_path);
}

/** Uploaded rows for one order or route. FB-030: the caller deletes any kept file first (`keptFilesFor`). */
export function deleteUploadedFor(s: ScopedRunner, target: { workOrderId?: string; routeId?: string }): number {
  return s.run(
    `DELETE FROM photo
      WHERE technician_id = :technician_id AND state = 'uploaded'
        AND (work_order_id = :work_order_id OR route_id = :route_id)`,
    { work_order_id: target.workOrderId ?? null, route_id: target.routeId ?? null },
  ).changes;
}

/** FF-50 *Photos 24 of 62 · 41 MB left*: this technician's photographs still
 *  on the handset, how many are up, and the bytes not yet up. */
export function progressMine(s: ScopedRunner): { total: number; uploaded: number; bytesLeft: number } {
  const row = s.get<{ total: number; uploaded: number | null; left: number | null }>(
    `SELECT COUNT(*) AS total,
            SUM(CASE WHEN state = 'uploaded' THEN 1 ELSE 0 END) AS uploaded,
            SUM(CASE WHEN state != 'uploaded' THEN bytes ELSE 0 END) AS left
       FROM photo WHERE technician_id = :technician_id`,
  );
  return { total: row?.total ?? 0, uploaded: row?.uploaded ?? 0, bytesLeft: row?.left ?? 0 };
}
