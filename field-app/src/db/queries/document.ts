/**
 * `document` — SOPs, safety sheets and asset papers; `owner_kind` + `owner_id`
 * say what it hangs off, `source` where it came from (R108). Not scoped.
 * Files on disk, cached by content; evicted oldest-first above a 200 MB cap,
 * skipping anything a job in scope still cites (Mobile data §7, §10).
 */
import type { QueryRunner, TenantDb } from '../database';

/**
 * The document budget (Mobile data §10): the purge evicts above it, and a
 * help document fetched at sync never takes the store past it. One figure,
 * read by both (`purge.ts` `RETENTION.documentCapBytes`, `sync/extras.ts`).
 */
export const DOCUMENT_CAP_BYTES = 200 * 1024 * 1024;

export interface DocumentRow {
  id: string;
  owner_kind: 'work_order' | 'asset' | 'template' | 'tenant';
  owner_id: string | null;
  title: string;
  kind: string | null;
  source: 'server' | 'camera' | 'file' | 'typed';
  local_path: string | null;
  bytes: number;
  content_hash: string | null;
  outbox_id: string | null;
  last_used_at: string | null;
  updated_at: string;
  /** A help entry's server `ref`: a phone's number, a link's https address, a document's stored id (0002). */
  ref: string | null;
  /** A help document's pre-signed link, until its bytes are down (0002). */
  url: string | null;
}

/** The kinds a job's help entry takes (`work.models.HELP_KINDS`), stored in `document.kind`. */
export const HELP_KINDS = ['document', 'phone', 'link', 'note'] as const;
export type HelpKind = (typeof HELP_KINDS)[number];

export function isHelp(d: Pick<DocumentRow, 'kind'>): d is Pick<DocumentRow, 'kind'> & { kind: HelpKind } {
  return (HELP_KINDS as readonly (string | null)[]).includes(d.kind);
}

export interface HelpInput {
  id: string;
  workOrderId: string;
  kind: string;
  label: string;
  ref: string | null;
  url: string | null;
}

/**
 * One help entry from the job bundle (DEF-FLD-10581). The server wins on what
 * it sends; the phone's own copy of a document survives only while the entry
 * still names the SAME file (`ref` and `kind` unchanged). Returns the copy that
 * no longer belongs, for the caller to delete from disk.
 */
export function upsertHelp(db: TenantDb, h: HelpInput, now: string): string | null {
  const prev = get(db, h.id);
  const stale = prev?.local_path && (prev.ref !== h.ref || prev.kind !== h.kind) ? prev.local_path : null;
  db.ref.run(
    `INSERT INTO document (id, owner_kind, owner_id, title, kind, source, ref, url, bytes, last_used_at, updated_at)
     VALUES (:id, 'work_order', :wo, :title, :kind, 'server', :ref, :url, 0, :now, :now)
     ON CONFLICT (id) DO UPDATE SET
       owner_kind = excluded.owner_kind, owner_id = excluded.owner_id, title = excluded.title,
       local_path = CASE WHEN document.ref IS excluded.ref AND document.kind IS excluded.kind THEN document.local_path END,
       bytes = CASE WHEN document.ref IS excluded.ref AND document.kind IS excluded.kind THEN document.bytes ELSE 0 END,
       url = CASE WHEN document.ref IS excluded.ref AND document.kind IS excluded.kind AND document.local_path IS NOT NULL
                  THEN NULL ELSE excluded.url END,
       kind = excluded.kind, source = excluded.source, ref = excluded.ref, updated_at = excluded.updated_at`,
    { id: h.id, wo: h.workOrderId, title: h.label, kind: h.kind, ref: h.ref, url: h.url, now },
  );
  return stale;
}

/**
 * The job's server help entries the bundle no longer sends: deleted, and their
 * files returned for the caller to delete from disk. Papers captured on the
 * phone (`source` camera/file/typed) are never touched.
 */
export function removeHelpNotIn(db: TenantDb, workOrderId: string, keep: readonly string[]): string[] {
  const gone = db.ref
    .all<DocumentRow>(
      `SELECT * FROM document WHERE owner_kind = 'work_order' AND owner_id = :wo AND source = 'server'
         AND kind IN ('document','phone','link','note')`,
      { wo: workOrderId },
    )
    .filter((d) => !keep.includes(d.id));
  for (const d of gone) db.ref.run('DELETE FROM document WHERE id = :id', { id: d.id });
  return gone.map((d) => d.local_path).filter((p): p is string => !!p);
}

/** Help documents whose bytes are not on the phone yet and that have a link to fetch them by. */
export function helpAwaitingDownload(db: TenantDb, limit: number): DocumentRow[] {
  return db.ref.all<DocumentRow>(
    `SELECT * FROM document
      WHERE source = 'server' AND kind = 'document' AND local_path IS NULL AND url IS NOT NULL
      ORDER BY owner_id, id LIMIT :limit`,
    { limit },
  );
}

/** The bytes are down: the phone's own copy, and the link is forgotten. */
export function markDownloaded(db: TenantDb, id: string, localPath: string, bytes: number, at: string): void {
  db.ref.run('UPDATE document SET local_path = :p, bytes = :b, url = NULL, updated_at = :at WHERE id = :id', {
    id,
    p: localPath,
    b: bytes,
    at,
  });
}

/**
 * One row per help entry, however many owners carry it: the job's copy of a
 * template's help names the same file, number or address, so a `ref` counts
 * once (FF-15's *Help and SOPs*). An entry with no `ref` counts by its own id.
 */
export function distinctHelp<T extends Pick<DocumentRow, 'id' | 'kind' | 'ref'>>(rows: readonly T[]): T[] {
  const seen = new Set<string>();
  return rows.filter((d) => {
    const key = d.ref ? `${d.kind ?? ''}|${d.ref}` : `id|${d.id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export interface DocumentInput {
  id: string;
  ownerKind: DocumentRow['owner_kind'];
  ownerId: string | null;
  title: string;
  kind?: string | null;
  source: DocumentRow['source'];
  localPath?: string | null;
  bytes?: number;
  contentHash?: string | null;
  outboxId?: string | null;
  lastUsedAt?: string | null;
}

export function upsert(db: TenantDb, d: DocumentInput, now: string): void {
  db.ref.run(
    `INSERT INTO document (id, owner_kind, owner_id, title, kind, source, local_path, bytes, content_hash,
                           outbox_id, last_used_at, updated_at)
     VALUES (:id, :owner_kind, :owner_id, :title, :kind, :source, :local_path, :bytes, :content_hash,
             :outbox_id, :last_used_at, :now)
     ON CONFLICT (id) DO UPDATE SET
       owner_kind = excluded.owner_kind, owner_id = excluded.owner_id, title = excluded.title,
       kind = excluded.kind, source = excluded.source, local_path = excluded.local_path,
       bytes = excluded.bytes, content_hash = excluded.content_hash,
       outbox_id = COALESCE(excluded.outbox_id, document.outbox_id), updated_at = excluded.updated_at`,
    {
      id: d.id,
      owner_kind: d.ownerKind,
      owner_id: d.ownerId,
      title: d.title,
      kind: d.kind,
      source: d.source,
      local_path: d.localPath,
      bytes: d.bytes ?? 0,
      content_hash: d.contentHash,
      outbox_id: d.outboxId,
      last_used_at: d.lastUsedAt ?? now,
      now,
    },
  );
}

export function listForOwner(db: TenantDb, ownerKind: DocumentRow['owner_kind'], ownerId: string): DocumentRow[] {
  return db.ref.all<DocumentRow>(
    'SELECT * FROM document WHERE owner_kind = :owner_kind AND owner_id = :owner_id ORDER BY title LIMIT 500',
    { owner_kind: ownerKind, owner_id: ownerId },
  );
}

export function get(db: TenantDb, id: string): DocumentRow | undefined {
  return db.ref.get<DocumentRow>('SELECT * FROM document WHERE id = :id', { id });
}

export function cachedBytes(db: TenantDb): number {
  return db.ref.get<{ n: number | null }>('SELECT SUM(bytes) AS n FROM document WHERE local_path IS NOT NULL')?.n ?? 0;
}

/**
 * Cached files that MAY be evicted, oldest-used first: not cited by any job or
 * route on the handset, and not a captured paper whose outbox row is unsent.
 */
export function evictionCandidates(purge: QueryRunner, limit: number): DocumentRow[] {
  return purge.all<DocumentRow>(
    `SELECT * FROM document d
      WHERE d.local_path IS NOT NULL
        AND NOT (d.owner_kind = 'work_order' AND d.owner_id IN (SELECT id FROM work_order))
        AND NOT (d.owner_kind = 'asset' AND (
              d.owner_id IN (SELECT asset_id FROM work_order WHERE asset_id IS NOT NULL)
           OR d.owner_id IN (SELECT asset_id FROM route_read)))
        AND NOT (d.outbox_id IS NOT NULL AND d.outbox_id IN (
              SELECT id FROM outbox WHERE state IN ('pending','sending','refused')))
      ORDER BY COALESCE(d.last_used_at, d.updated_at), d.id
      LIMIT :limit`,
    { limit },
  );
}

/** The file is gone; the row stays so it can be fetched again. */
export function markEvicted(purge: QueryRunner, id: string): void {
  purge.run('UPDATE document SET local_path = NULL, bytes = 0 WHERE id = :id', { id });
}
