/**
 * FB-023 F1 — the last money figure the server gave for a JOB, kept on the
 * handset so it survives a restart and can be shown offline WITH ITS AGE (PO
 * 2026-10-31: *"check live when the job opens (keep the last figure with its
 * age when offline)"*).
 *
 * Kept in `settings` (key/value, no migration) under one key per technician
 * and job — `money.last.<technician>.<work order>` — so a shared tablet never
 * shows one login's figure to another. It is the server's own answer, stamped
 * with the server's `asAt`; nothing here computes money (R16). It goes when the
 * job leaves the phone (`sync/delta.ts`), and is never written into `customer`
 * (Mobile data §2).
 */
import type { TenantDb } from '../database';
import { fromJson, toJson } from '../json';

const PREFIX = 'money.last.';

export function keyOf(technicianId: string, workOrderId: string): string {
  return `${PREFIX}${technicianId}.${workOrderId}`;
}

export function get<T = unknown>(db: TenantDb, technicianId: string, workOrderId: string): T | null {
  const row = db.ref.get<{ value: string }>('SELECT value FROM settings WHERE key = :key', { key: keyOf(technicianId, workOrderId) });
  return fromJson<T>(row?.value);
}

export function put(db: TenantDb, technicianId: string, workOrderId: string, reading: unknown, now: string): void {
  db.ref.run(
    `INSERT INTO settings (key, value, updated_at) VALUES (:key, :value, :now)
     ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`,
    { key: keyOf(technicianId, workOrderId), value: toJson(reading) ?? 'null', now },
  );
}

export function remove(db: TenantDb, technicianId: string, workOrderId: string): void {
  db.ref.run('DELETE FROM settings WHERE key = :key', { key: keyOf(technicianId, workOrderId) });
}
