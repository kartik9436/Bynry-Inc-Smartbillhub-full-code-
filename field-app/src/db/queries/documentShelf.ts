/**
 * `document` — FF-28's two shelves: the papers that hang off this job (its
 * own, its asset's, its template's) and the ones that are always on the phone
 * (`owner_kind = 'tenant'`), plus the footer's count, size and last update.
 * Not scoped (a document is reference data).
 */
import type { TenantDb } from '../database';
import type { DocumentRow } from './document';

export function forJob(
  db: TenantDb,
  job: { workOrderId: string; assetId: string | null; templateId: string | null },
): DocumentRow[] {
  return db.ref.all<DocumentRow>(
    `SELECT * FROM document
      WHERE (owner_kind = 'work_order' AND owner_id = :wo)
         OR (owner_kind = 'asset' AND owner_id = :asset)
         OR (owner_kind = 'template' AND owner_id = :template)
      ORDER BY owner_kind = 'work_order' DESC, title LIMIT 200`,
    { wo: job.workOrderId, asset: job.assetId ?? '', template: job.templateId ?? '' },
  );
}

export function alwaysOnPhone(db: TenantDb): DocumentRow[] {
  return db.ref.all<DocumentRow>("SELECT * FROM document WHERE owner_kind = 'tenant' ORDER BY title LIMIT 200");
}

export function shelfTotals(db: TenantDb): { count: number; bytes: number; updatedAt: string | null } {
  const row = db.ref.get<{ n: number; b: number | null; u: string | null }>(
    'SELECT COUNT(*) AS n, SUM(bytes) AS b, MAX(updated_at) AS u FROM document WHERE local_path IS NOT NULL',
  );
  return { count: row?.n ?? 0, bytes: row?.b ?? 0, updatedAt: row?.u ?? null };
}

export function markUsed(db: TenantDb, id: string, at: string): void {
  db.ref.run('UPDATE document SET last_used_at = :at WHERE id = :id', { id, at });
}
