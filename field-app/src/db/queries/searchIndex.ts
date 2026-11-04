/**
 * `search_index` — one FTS5 table over work-order number, customer name,
 * address, asset serial and badge (Mobile data §3). It carries technician_id
 * and is built from scoped rows, so a search can never surface another
 * technician's customers (R132). One query serves Today, Assets and Scan.
 *
 * Local search is bounded on purpose (R41, R42): the screen that shows these
 * results must say they are only what is on the handset.
 */
import type { ScopedRunner } from '../scoped';

export type SearchEntityKind = 'work_order' | 'asset' | 'route_stop';

export interface SearchFields {
  number?: string | null;
  customerName?: string | null;
  address?: string | null;
  serial?: string | null;
  badge?: string | null;
}

export interface SearchHit {
  entity_kind: SearchEntityKind;
  entity_id: string;
  number: string | null;
  customer_name: string | null;
  address: string | null;
  serial: string | null;
  badge: string | null;
}

export function remove(s: ScopedRunner, kind: SearchEntityKind, id: string): void {
  s.run(
    `DELETE FROM search_index WHERE technician_id = :technician_id AND entity_kind = :kind AND entity_id = :id`,
    { kind, id },
  );
}

/** Replace this technician's entry for one entity. */
export function put(s: ScopedRunner, kind: SearchEntityKind, id: string, f: SearchFields): void {
  remove(s, kind, id);
  s.run(
    `INSERT INTO search_index (technician_id, entity_kind, entity_id, number, customer_name, address, serial, badge)
     VALUES (:technician_id, :kind, :id, :number, :customer_name, :address, :serial, :badge)`,
    {
      kind,
      id,
      number: f.number ?? '',
      customer_name: f.customerName ?? '',
      address: f.address ?? '',
      serial: f.serial ?? '',
      badge: f.badge ?? '',
    },
  );
}

/**
 * The user's words as an FTS5 query: every word must match, each as a prefix,
 * each quoted so punctuation in a serial (`A-1234`) is never read as syntax.
 */
export function toMatchExpression(text: string): string | null {
  const words = text
    .split(/\s+/)
    .map((w) => w.replace(/"/g, '').trim())
    .filter((w) => w.length > 0);
  if (words.length === 0) return null;
  return words.map((w) => `"${w}"*`).join(' AND ');
}

export function search(s: ScopedRunner, text: string, opts: { limit: number; offset?: number }): SearchHit[] {
  const match = toMatchExpression(text);
  if (match === null) return [];
  return s.all<SearchHit>(
    `SELECT entity_kind, entity_id, number, customer_name, address, serial, badge
       FROM search_index
      WHERE search_index MATCH :match AND technician_id = :technician_id
      ORDER BY rank
      LIMIT :limit OFFSET :offset`,
    { match, limit: opts.limit, offset: opts.offset ?? 0 },
  );
}
