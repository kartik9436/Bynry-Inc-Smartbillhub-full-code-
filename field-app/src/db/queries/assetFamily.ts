/**
 * `asset` — a meter's sub-meters (FF-39 SUB-METERS) and the assets a search
 * hit names (FF-41). Not scoped (R132): assets are reference data reached
 * from a technician's rows, never a technician's own.
 *
 * Kept apart from `asset.ts` so two waves never edit the same file.
 */
import type { TenantDb } from '../database';
import type { AssetRow } from './asset';

export function children(db: TenantDb, parentId: string): AssetRow[] {
  return db.ref.all<AssetRow>(
    'SELECT * FROM asset WHERE parent_asset_id = :parent ORDER BY serial, id LIMIT 200',
    { parent: parentId },
  );
}

export function getMany(db: TenantDb, ids: readonly string[]): AssetRow[] {
  if (ids.length === 0) return [];
  const params: Record<string, string> = {};
  const names = ids.map((id, i) => {
    params[`a${i}`] = id;
    return `:a${i}`;
  });
  return db.ref.all<AssetRow>(`SELECT * FROM asset WHERE id IN (${names.join(', ')})`, params);
}
