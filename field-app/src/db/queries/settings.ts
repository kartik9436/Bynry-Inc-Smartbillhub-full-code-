/** `settings` — device-level facts that must survive a reinstall and are not
 *  preferences (preferences live in MMKV, AD-17). Not scoped. */
import type { TenantDb } from '../database';
import { fromJson, toJson } from '../json';

export function get<T = unknown>(db: TenantDb, key: string): T | null {
  return fromJson<T>(db.ref.get<{ value: string }>('SELECT value FROM settings WHERE key = :key', { key })?.value);
}

export function set(db: TenantDb, key: string, value: unknown, now: string): void {
  db.ref.run(
    `INSERT INTO settings (key, value, updated_at) VALUES (:key, :value, :now)
     ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`,
    { key, value: toJson(value) ?? 'null', now },
  );
}
