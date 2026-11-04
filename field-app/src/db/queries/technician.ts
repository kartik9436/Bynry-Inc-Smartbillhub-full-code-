/** `technician` — everyone who has used this handset. The roster the scope
 *  resolves against, so not scoped itself (Mobile data §2). */
import type { TenantDb } from '../database';

export interface TechnicianRow {
  id: string;
  name: string;
  role: string | null;
  employment: string | null;
  photo_path: string | null;
  last_signed_in_at: string | null;
  updated_at: string;
}

export function upsert(
  db: TenantDb,
  t: { id: string; name: string; role?: string | null; employment?: string | null; photoPath?: string | null },
  now: string,
): void {
  db.ref.run(
    `INSERT INTO technician (id, name, role, employment, photo_path, updated_at)
     VALUES (:id, :name, :role, :employment, :photo_path, :now)
     ON CONFLICT (id) DO UPDATE SET
       name = excluded.name, role = excluded.role, employment = excluded.employment,
       photo_path = COALESCE(excluded.photo_path, technician.photo_path), updated_at = excluded.updated_at`,
    { id: t.id, name: t.name, role: t.role, employment: t.employment, photo_path: t.photoPath, now },
  );
}

export function markSignedIn(db: TenantDb, id: string, at: string): void {
  db.ref.run('UPDATE technician SET last_signed_in_at = :at WHERE id = :id', { id, at });
}

export function list(db: TenantDb): TechnicianRow[] {
  return db.ref.all<TechnicianRow>('SELECT * FROM technician ORDER BY name LIMIT 200');
}

export function get(db: TenantDb, id: string): TechnicianRow | undefined {
  return db.ref.get<TechnicianRow>('SELECT * FROM technician WHERE id = :id', { id });
}

/**
 * FB-023 F3 — the signed-in technician's employment as the server's change
 * feed states it (`apps/work/mobile.changes` → `technician.employment`, by
 * the money read's own test). Creates the roster row when the handset has
 * none (nothing else in production writes one) with a BLANK name — `myName`
 * falls back to the signed-in profile's — and never touches a name, role or
 * photo the row already holds.
 */
export function setEmployment(db: TenantDb, id: string, employment: 'employee' | 'contractor', now: string): void {
  db.ref.run(
    `INSERT INTO technician (id, name, employment, updated_at) VALUES (:id, '', :employment, :now)
     ON CONFLICT (id) DO UPDATE SET employment = excluded.employment, updated_at = excluded.updated_at`,
    { id, employment, now },
  );
}
