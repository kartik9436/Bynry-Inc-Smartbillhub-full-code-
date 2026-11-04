// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 §F — lane FIELD-2: the field app sends its location
//           automatically (PO 2026-10-04: "techcian app will also send lat and
//           long data automatically … generally Lat long key take time … before
//           submission we have to collect accurate lat long").
// Rules:    BR-WRK-061 (every item and the close carry lat, lng, accuracy_m and
//           fix_at; a close is never refused for location)
// Tests:    src/features/work/mobile/location.test.ts
// ───────────────────────────────────────────────────────

/**
 * The best location fix for the job in hand — started when the job opens,
 * kept while the technician works, and stamped on every item they capture.
 *
 * ⚠ **IT STARTS AT JOB START AND NOT AT CLOSE, AND THAT IS THE WHOLE RULE.**
 * The PO: a precise fix can take ~180 seconds to arrive. Asked for at the
 * moment of closing, it would be a 300 m guess every time — which the office
 * reads as *Location not precise*. Asked for when the job opens, the phone
 * has the whole visit to settle, and keeps the BEST fix it has seen.
 *
 * ⚠ **BEST MEANS SMALLEST ACCURACY RADIUS**, and a newer fix of the same
 * radius replaces an older one. A worse fix never replaces a better one: a
 * technician walking into a basement must not trade a 6 m fix from the
 * doorstep for a 300 m one from beside the meter.
 *
 * ⚠ **NOTHING HERE EVER BLOCKS A CAPTURE.** No permission, no fix, a phone
 * with no GPS — each is `null`, the item goes without a location, and the
 * office sees *Location not precise* (the PO's (a): *"Allow the close, send the
 * best fix with its accuracy"*).
 *
 * The fix is persisted per job so the Close pane — a different route — and a
 * reloaded page read the same best fix the job page has been collecting.
 */

import { readFix, writeFix, type LocationFix } from "./offlineStore";

export type { LocationFix } from "./offlineStore";

/** Is `next` better than `current`? Smaller radius; on a tie, the newer one. */
export function better(current: LocationFix | null, next: LocationFix): boolean {
  if (current === null) return true;
  if (next.accuracy_m < current.accuracy_m) return true;
  return next.accuracy_m === current.accuracy_m && next.fix_at > current.fix_at;
}

/** A browser position as the wire's four fields (`BR-WRK-061`). */
export function fixFromPosition(position: GeolocationPosition): LocationFix {
  return {
    lat: Number(position.coords.latitude.toFixed(6)),
    lng: Number(position.coords.longitude.toFixed(6)),
    accuracy_m: Number(position.coords.accuracy.toFixed(1)),
    fix_at: new Date(position.timestamp || Date.now()).toISOString(),
  };
}

const best = new Map<string, LocationFix>();
let watching: { orderId: string; id: number } | null = null;

/**
 * Start (or keep) acquiring for this job. Idempotent: the same job twice is
 * one watch; a different job moves the watch. Returns nothing — the fix is
 * read with `bestFix`.
 */
export function startFix(orderId: string): void {
  if (typeof navigator === "undefined" || !navigator.geolocation) return;
  if (watching?.orderId === orderId) return;
  stopFix();
  try {
    const id = navigator.geolocation.watchPosition(
      (position) => {
        const next = fixFromPosition(position);
        const current = best.get(orderId) ?? null;
        if (better(current, next)) {
          best.set(orderId, next);
          void writeFix(orderId, next);
        }
      },
      () => {
        // No permission, no signal, a timeout — not an error a technician
        // can act on. The item goes without a fix (see the module docstring).
      },
      // `maximumAge: 0` — a cached fix from the depot is not where the meter is.
      { enableHighAccuracy: true, maximumAge: 0, timeout: 180_000 },
    );
    watching = { orderId, id };
  } catch {
    watching = null;
  }
}

export function stopFix(): void {
  if (watching && typeof navigator !== "undefined" && navigator.geolocation) {
    try {
      navigator.geolocation.clearWatch(watching.id);
    } catch {
      // Nothing to clear.
    }
  }
  watching = null;
}

/** The best fix this job has seen, in memory or from the store; or `null`. */
export async function bestFix(orderId: string): Promise<LocationFix | null> {
  const inMemory = best.get(orderId);
  if (inMemory) return inMemory;
  const stored = await readFix(orderId);
  if (stored) best.set(orderId, stored);
  return stored;
}

/** Test seam. */
export function resetLocationForTests(): void {
  stopFix();
  best.clear();
}
