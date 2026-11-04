/**
 * Nearby unassigned work (FF-11) and claiming one (FF-12), as a port.
 *
 * ⚠ **NEITHER ROUTE EXISTS ON THE SERVER YET.** `07-endpoints.md` N11
 * (`GET work/mobile/nearby`) and N15 (`POST work/mobile/jobs/{id}/claim`) are
 * both NEW, task T-39/T-40. Nearby work is not on the handset either: the
 * handset mirrors only the technician's OWN orders (`work_order` is scoped to
 * them, R132), so an unassigned order can only come from the server, and a
 * claim is online only (AD-04). So the shipped port refuses with
 * `NearbyGapError` naming the route, and FF-11 shows that it needs the
 * server — it never shows an empty radius, which would read as "no work near
 * you".
 *
 * ⚠ **ONE QUESTION IS NOT OURS TO ANSWER** (EP-FLD-02 US-FLD-023 §8): whether
 * a claim outside the technician's skills is refused (walkthrough E2E-19) or
 * only advised (signed `BR-WRK-029`, superseded 2026-09-23 to *advise, never
 * block*). The handset sends the claim and shows the server's answer; it
 * never filters by skill itself. `CLAIM_SKILL_QUESTION` is the question, for
 * an `OQ-FLD-` id.
 */

/** R34: the radius is a setting, default 2 miles; the field map lists 1 · 2 · 5 · 10. */
export const RADIUS_CHOICES_MI = [1, 2, 5, 10] as const;
export type RadiusMi = (typeof RADIUS_CHOICES_MI)[number];
export const DEFAULT_RADIUS_MI: RadiusMi = 2;

export interface NearbyJob {
  id: string;
  number: string | null;
  type: string | null;
  priorityCode: string | null;
  address: string | null;
  /** As the server measured it from the premise point, miles. */
  distanceMi: number | null;
  dueAt: string | null;
  estMinutes: number | null;
  /** Someone has it: their display name. Null while it is free. */
  takenBy: string | null;
}

export interface NearbyPage {
  jobs: NearbyJob[];
  /** All unassigned within the radius, not just this page. */
  count: number;
  hasMore: boolean;
}

export type ClaimResult = { ok: true } | { ok: false; takenBy: string | null };

export interface NearbyPort {
  list(input: { radiusMi: RadiusMi; page: number }): Promise<NearbyPage>;
  claim(jobId: string): Promise<ClaimResult>;
}

export const NEARBY_GAPS = {
  'nearby-list': {
    endpoint: 'GET /api/{tenant}/work/mobile/nearby?radius_mi=&type=&priority=&due=&unassigned=&page=',
    need: 'Unassigned orders near a point, paged, no hard cap (07-endpoints.md N11, T-40).',
  },
  'nearby-claim': {
    endpoint: 'POST /api/{tenant}/work/mobile/jobs/{id}/claim',
    need: 'Take nearby unassigned work, within the tenant; dispatch is told; another technician cannot take it (07-endpoints.md N15, T-39).',
  },
} as const;

export type NearbyGapId = keyof typeof NEARBY_GAPS;

export class NearbyGapError extends Error {
  readonly gap: NearbyGapId;

  constructor(gap: NearbyGapId) {
    super(`server gap ${gap}: ${NEARBY_GAPS[gap].endpoint} — ${NEARBY_GAPS[gap].need}`);
    this.name = 'NearbyGapError';
    this.gap = gap;
  }
}

/**
 * The handset does not know where it is — location is off, not yet allowed, or
 * no fix came (DEF-FLD-10605). FF-11 says *Location is off* and offers to turn
 * it on; it is never *Nearby needs a signal*, which is about the network.
 */
export class NearbyNoFixError extends Error {
  constructor() {
    super('no position fix — nearby work is measured from where the handset is');
    this.name = 'NearbyNoFixError';
  }
}

export const CLAIM_SKILL_QUESTION =
  'CLAIM_SKILL: is a claim from the handset refused outside the technician\'s skills (E2E-19), or only advised (BR-WRK-029 as superseded 2026-09-23)?';

export const nearbyNotWired: NearbyPort = {
  list: () => Promise.reject(new NearbyGapError('nearby-list')),
  claim: () => Promise.reject(new NearbyGapError('nearby-claim')),
};
