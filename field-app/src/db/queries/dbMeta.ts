/** `db_meta` — facts about the file itself; today, which tenant it belongs to (R131). */
import type { TenantDb } from '../database';

export function get(db: TenantDb, key: string): string | undefined {
  return db.ref.get<{ value: string }>('SELECT value FROM db_meta WHERE key = :key', { key })?.value;
}

export function set(db: TenantDb, key: string, value: string): void {
  db.ref.run(
    `INSERT INTO db_meta (key, value) VALUES (:key, :value)
     ON CONFLICT (key) DO UPDATE SET value = excluded.value`,
    { key, value },
  );
}
