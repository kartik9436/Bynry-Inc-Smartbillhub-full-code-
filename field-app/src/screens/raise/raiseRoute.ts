/**
 * What a raise carries from screen to screen — FF-37 Raise and FF-62 Pick a
 * template hand these on to each other unchanged, so picking the template
 * after the place (or the place after the template) loses neither
 * (DEF-FLD-10603, MQ-036).
 *
 *   carriedFrom — the job it was raised from (Completed, a job's screens).
 *   returnTo    — the screen it was opened from, where Send and Cancel go back
 *                 to. Before DEF-FLD-10603 both went to FF-35 Completed from
 *                 everywhere, so a raise from Home landed on *Nothing closed*.
 *   where*      — the place picked on FF-37's *Where* card when there is no
 *                 job. Named apart from `assetId`, which the board header
 *                 carries to the asset screens (`onSite/common.tsx`).
 */
import type { ScreenId } from '../../navigation/screens';
import type { PlaceAnchors } from '../../db/queries/placeSearch';

export const RAISE_CARRY = ['carriedFrom', 'returnTo', 'wherePremiseId', 'whereAccountId', 'whereAssetId'] as const;

/** The raise's own params, out of a screen's params, for the next door. */
export function raiseCarry(params: Record<string, unknown>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const name of RAISE_CARRY) {
    const v = params[name];
    if (typeof v === 'string' && v !== '') out[name] = v;
  }
  return out;
}

/** The picked place as route params (empty strings clear a previous pick). */
export function whereParams(place: PlaceAnchors | null): Record<string, string> {
  return {
    wherePremiseId: place?.premiseId ?? '',
    whereAccountId: place?.accountId ?? '',
    whereAssetId: place?.assetId ?? '',
  };
}

/** The picked place out of the params, or null when none is picked. */
export function whereOf(params: Record<string, unknown>): PlaceAnchors | null {
  const str = (v: unknown) => (typeof v === 'string' && v !== '' ? v : null);
  const place = { premiseId: str(params.wherePremiseId), accountId: str(params.whereAccountId), assetId: str(params.whereAssetId) };
  return place.premiseId || place.accountId || place.assetId ? place : null;
}

/**
 * Where Send and Cancel go: the screen the raise was opened from. A raise
 * carried from a job with no `returnTo` came from Completed (FF-35), its only
 * door with a job; anything else with no `returnTo` goes Home (FF-63).
 */
export function returnTarget(params: Record<string, unknown>): ScreenId {
  if (typeof params.returnTo === 'string' && params.returnTo !== '') return params.returnTo as ScreenId;
  return typeof params.carriedFrom === 'string' && params.carriedFrom !== '' ? 'FF-35' : 'FF-63';
}
