/**
 * `asset` — meters and sub-meters in scope. Not scoped (R132).
 *
 * A scanned code is matched serial, then badge, then device id — one order,
 * everywhere, so the same sticker always finds the same meter (R43, R83).
 */
import type { QueryRunner, TenantDb } from '../database';
import { toJson } from '../json';

export interface AssetRow {
  id: string;
  serial: string | null;
  badge: string | null;
  device_id: string | null;
  model: string | null;
  size: string | null;
  service: string | null;
  parent_asset_id: string | null;
  premise_id: string | null;
  status: 'active' | 'pending';
  outbox_id: string | null;
  history: string | null;
  extra: string | null;
  updated_at: string;
}

export interface AssetInput {
  id: string;
  serial?: string | null;
  badge?: string | null;
  deviceId?: string | null;
  model?: string | null;
  size?: string | null;
  service?: string | null;
  parentAssetId?: string | null;
  premiseId?: string | null;
  status?: 'active' | 'pending';
  outboxId?: string | null;
  history?: unknown;
  extra?: Record<string, unknown> | null;
}

export function upsert(db: TenantDb, a: AssetInput, now: string): void {
  db.ref.run(
    `INSERT INTO asset (id, serial, badge, device_id, model, size, service, parent_asset_id, premise_id,
                        status, outbox_id, history, extra, updated_at)
     VALUES (:id, :serial, :badge, :device_id, :model, :size, :service, :parent_asset_id, :premise_id,
             :status, :outbox_id, :history, :extra, :now)
     ON CONFLICT (id) DO UPDATE SET
       serial = excluded.serial, badge = excluded.badge, device_id = excluded.device_id, model = excluded.model,
       size = excluded.size, service = excluded.service, parent_asset_id = excluded.parent_asset_id,
       premise_id = excluded.premise_id, status = excluded.status,
       outbox_id = COALESCE(excluded.outbox_id, asset.outbox_id),
       history = excluded.history, extra = excluded.extra, updated_at = excluded.updated_at`,
    {
      id: a.id,
      serial: a.serial,
      badge: a.badge,
      device_id: a.deviceId,
      model: a.model,
      size: a.size,
      service: a.service,
      parent_asset_id: a.parentAssetId,
      premise_id: a.premiseId,
      status: a.status ?? 'active',
      outbox_id: a.outboxId,
      history: toJson(a.history),
      extra: toJson(a.extra),
      now,
    },
  );
}

export function get(db: TenantDb, id: string): AssetRow | undefined {
  return db.ref.get<AssetRow>('SELECT * FROM asset WHERE id = :id', { id });
}

/** FF-38 Scan: serial, then badge, then device id (R43). */
export function matchScannedCode(db: TenantDb, code: string): { asset: AssetRow; matchedOn: 'serial' | 'badge' | 'device_id' } | null {
  for (const column of ['serial', 'badge', 'device_id'] as const) {
    const asset = db.ref.get<AssetRow>(`SELECT * FROM asset WHERE ${column} = :code ORDER BY id LIMIT 1`, { code });
    if (asset) return { asset, matchedOn: column };
  }
  return null;
}

/**
 * Assets that have left scope: active (not field-added), and no longer named by
 * any job or route reading on this handset. Asset history is kept while the
 * asset is in scope and dropped when it leaves (Mobile data §7).
 */
export function deleteOutOfScope(purge: QueryRunner): number {
  return purge.run(
    `DELETE FROM asset
      WHERE status = 'active'
        AND id NOT IN (SELECT asset_id FROM work_order WHERE asset_id IS NOT NULL)
        AND id NOT IN (SELECT asset_id FROM route_read)
        AND id NOT IN (SELECT parent_asset_id FROM route_read WHERE parent_asset_id IS NOT NULL)
        AND id NOT IN (SELECT parent_asset_id FROM asset WHERE parent_asset_id IS NOT NULL)`,
  ).changes;
}
