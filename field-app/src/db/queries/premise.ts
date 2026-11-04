/**
 * `premise` — the one place an address lives on the handset (CLAUDE.md hard
 * rule 8). Not scoped: reference data reached by join from a scoped row, so
 * one building is never two rows (R132).
 */
import type { TenantDb } from '../database';
import { toJson } from '../json';

export interface PremiseRow {
  id: string;
  premise_no: string | null;
  address_line: string | null;
  locality: string | null;
  region: string | null;
  postal_code: string | null;
  lat: number | null;
  lng: number | null;
  extra: string | null;
  updated_at: string;
}

export interface PremiseInput {
  id: string;
  premiseNo?: string | null;
  addressLine?: string | null;
  locality?: string | null;
  region?: string | null;
  postalCode?: string | null;
  lat?: number | null;
  lng?: number | null;
  extra?: Record<string, unknown> | null;
}

/** Server wins, but a field the server did not send this time is kept. */
export function upsert(db: TenantDb, p: PremiseInput, now: string): void {
  db.ref.run(
    `INSERT INTO premise (id, premise_no, address_line, locality, region, postal_code, lat, lng, extra, updated_at)
     VALUES (:id, :premise_no, :address_line, :locality, :region, :postal_code, :lat, :lng, :extra, :now)
     ON CONFLICT (id) DO UPDATE SET
       premise_no = COALESCE(excluded.premise_no, premise.premise_no),
       address_line = COALESCE(excluded.address_line, premise.address_line),
       locality = COALESCE(excluded.locality, premise.locality),
       region = COALESCE(excluded.region, premise.region),
       postal_code = COALESCE(excluded.postal_code, premise.postal_code),
       lat = COALESCE(excluded.lat, premise.lat),
       lng = COALESCE(excluded.lng, premise.lng),
       extra = COALESCE(excluded.extra, premise.extra),
       updated_at = excluded.updated_at`,
    {
      id: p.id,
      premise_no: p.premiseNo,
      address_line: p.addressLine,
      locality: p.locality,
      region: p.region,
      postal_code: p.postalCode,
      lat: p.lat,
      lng: p.lng,
      extra: toJson(p.extra),
      now,
    },
  );
}

export function get(db: TenantDb, id: string): PremiseRow | undefined {
  return db.ref.get<PremiseRow>('SELECT * FROM premise WHERE id = :id', { id });
}
