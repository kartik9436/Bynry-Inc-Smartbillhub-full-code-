/** `schema_migrations` — which migrations this file has had. Store housekeeping. */
import type { TenantDb } from '../database';

export function ensure(db: TenantDb): void {
  db._exec(
    `CREATE TABLE IF NOT EXISTS schema_migrations (
       id         INTEGER PRIMARY KEY,
       name       TEXT NOT NULL,
       applied_at TEXT NOT NULL
     )`,
  );
}

export function appliedIds(db: TenantDb): number[] {
  return db.ref.all<{ id: number }>('SELECT id FROM schema_migrations ORDER BY id').map((r) => r.id);
}

export function record(db: TenantDb, id: number, name: string, appliedAt: string): void {
  db.ref.run('INSERT INTO schema_migrations (id, name, applied_at) VALUES (:id, :name, :applied_at)', {
    id,
    name,
    applied_at: appliedAt,
  });
}
