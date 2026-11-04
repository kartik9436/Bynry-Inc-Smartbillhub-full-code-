/**
 * `work_order_templates` — FF-62's search and FF-37's chosen template. Not
 * scoped: the tenant's catalogue (see `workOrderTemplates.ts`). Published
 * only (US-FLD-076 TC-4: a draft is never offered).
 */
import type { TenantDb } from '../database';
import { cleanRow, cleanRows, type TemplateRow } from './workOrderTemplates';

export function countPublished(db: TenantDb): number {
  return db.ref.get<{ n: number }>('SELECT COUNT(*) AS n FROM work_order_templates WHERE published = 1')?.n ?? 0;
}

/** Name contains the words, recently used first, then by name; paged. */
export function searchPublished(db: TenantDb, text: string, opts: { limit: number; offset?: number }): TemplateRow[] {
  const like = `%${text.trim().replace(/[\\%_]/g, (c) => `\\${c}`)}%`;
  return cleanRows(
    db.ref.all<TemplateRow>(
      `SELECT * FROM work_order_templates WHERE published = 1 AND name LIKE :like ESCAPE '\\'
        ORDER BY last_used_at IS NULL, last_used_at DESC, name LIMIT :limit OFFSET :offset`,
      { like, limit: opts.limit, offset: opts.offset ?? 0 },
    ),
  );
}

export function getPublished(db: TenantDb, id: string): TemplateRow | undefined {
  return cleanRow(db.ref.get<TemplateRow>('SELECT * FROM work_order_templates WHERE id = :id AND published = 1', { id }));
}
