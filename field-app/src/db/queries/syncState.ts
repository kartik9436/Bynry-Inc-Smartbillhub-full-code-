/**
 * `sync_state` — per technician PER TABLE: the server cursor and the clocks.
 * The pair is the key (R134): one cursor per table would let the second
 * technician's pull advance the first's, who then loses deltas silently.
 */
import type { ScopedRunner } from '../scoped';

export interface SyncStateRow {
  technician_id: string;
  table_name: string;
  cursor: string | null;
  last_pull_at: string | null;
  last_push_at: string | null;
  pending_count: number;
}

export function get(s: ScopedRunner, tableName: string): SyncStateRow | undefined {
  return s.get<SyncStateRow>(
    'SELECT * FROM sync_state WHERE technician_id = :technician_id AND table_name = :table_name',
    { table_name: tableName },
  );
}

export function setCursor(s: ScopedRunner, tableName: string, cursor: string | null, at: string): void {
  s.run(
    `INSERT INTO sync_state (technician_id, table_name, cursor, last_pull_at)
     VALUES (:technician_id, :table_name, :cursor, :at)
     ON CONFLICT (technician_id, table_name) DO UPDATE SET cursor = excluded.cursor, last_pull_at = excluded.last_pull_at`,
    { table_name: tableName, cursor, at },
  );
}

export function touchPush(s: ScopedRunner, tableName: string, at: string, pendingCount: number): void {
  s.run(
    `INSERT INTO sync_state (technician_id, table_name, last_push_at, pending_count)
     VALUES (:technician_id, :table_name, :at, :pending)
     ON CONFLICT (technician_id, table_name) DO UPDATE SET last_push_at = excluded.last_push_at,
       pending_count = excluded.pending_count`,
    { table_name: tableName, at, pending: pendingCount },
  );
}
