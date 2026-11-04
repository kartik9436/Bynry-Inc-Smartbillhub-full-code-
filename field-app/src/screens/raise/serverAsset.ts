/**
 * A meter the SERVER found and the phone did not hold (N9,
 * `GET work/mobile/assets/search`) — the one way FF-41 Asset search and FF-38
 * Scan take a server hit onto the phone, so FF-39 opens it like any other.
 *
 * Moved here from `AssetSearchScreen.keepAndOpen` for FB-009
 * (DEF-FLD-10634): Scan never asked the server, and when it began to it had to
 * open a hit exactly as FF-41 does, not a second way.
 */
import * as assetQ from '../../db/queries/asset';
import * as premiseQ from '../../db/queries/premise';
import type { WireAssetHit } from '../../sync/fieldApi';
import { TransportError } from '../../sync/transport';
import type { Wave } from '../onSite/fieldData';

/** Keep the hit (asset and its premises) on the phone. */
export function keepServerAsset(w: Pick<Wave, 'db' | 'clock'>, h: WireAssetHit): void {
  const at = w.clock.now().toISOString();
  const premise = h.place?.premises ?? null;
  w.db.transaction(() => {
    if (premise?.id) premiseQ.upsert(w.db, { id: premise.id, premiseNo: premise.premise_no ?? null, addressLine: premise.address ?? null }, at);
    assetQ.upsert(
      w.db,
      { id: h.id, serial: h.serial, deviceId: h.asset_no, model: h.model, size: h.size_class, premiseId: premise?.id ?? null, status: 'active' },
      at,
    );
  });
}

/**
 * The hit whose serial or asset number IS the code (case-insensitive,
 * trimmed), or null. The server also matches prefixes, addresses and account
 * numbers; a scanned code is one meter, so only an exact hit is that meter —
 * opening the first prefix hit would open the wrong meter with confidence
 * (decision log 2026-10-27, FB-009).
 */
export function exactServerMatch(hits: readonly WireAssetHit[], code: string): WireAssetHit | null {
  const k = code.trim().toLowerCase();
  if (!k) return null;
  return hits.find((h) => [h.serial, h.asset_no].some((v) => v != null && v.trim().toLowerCase() === k)) ?? null;
}

/** No signal: the call never reached a server (a dropped connection or no answer in time). */
export function isNoSignal(err: unknown): boolean {
  return err instanceof TransportError && err.kind === 'network' && err.status === undefined;
}
