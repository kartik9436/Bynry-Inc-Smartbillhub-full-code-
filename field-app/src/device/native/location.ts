/**
 * The REAL position behind `LocationDevice` (`../ports.ts`): `expo-location`.
 *
 * BEST FIX WINS (R90): a reading or a photograph carries the best position the
 * handset holds, not merely the newest. A fresh fix replaces the held one when
 * it is at least as accurate, or when the held one has gone stale; otherwise
 * the held one stands. `current()` asks for a fix now and also weighs the
 * platform's last known one, so a cold GPS under a porch roof does not throw
 * away a good fix from the kerb a few seconds earlier.
 *
 * Stored as the outbox stores it: latitude and longitude to 6 decimals (about
 * 11 cm), accuracy in metres to 1 decimal.
 *
 * NO PROMPT FROM `current()`: without permission it answers "no fix", which
 * every screen warns about and still accepts (R91). A position is never
 * invented. ⚠ **THE PROMPT IS `ensureOn()` — FB-003, PO 2026-10-27** (*"if
 * user has location permission not enabled asked the user to give
 * permission"*): the route and the camera call it as they open, so Android's
 * own *Allow location?* prompt — and, with the phone's Location off, its own
 * *Turn on location?* dialog — appear where a position is about to be needed,
 * not only once on FF-07 at sign-in. Refused with *Don't ask again*, Android
 * shows nothing more; the screen then offers *Open settings* (`openSettings`).
 */
import * as Location from 'expo-location';
import { Linking } from 'react-native';

import { withSystemInteraction } from '../../session/systemInteraction';
import { FIX_STALE_MS, type Fix, type LocationAccess, type LocationDevice } from '../ports';

/** A held fix older than this loses to any new one, however rough (defined beside the port). */
export { FIX_STALE_MS };
/** The platform's last known position is weighed only when this recent. */
export const LAST_KNOWN_MAX_AGE_MS = 60 * 1000;
/** The background watch: how often, and how far the van must move. */
export const WATCH = { timeInterval: 30_000, distanceInterval: 25 } as const;

const round = (n: number, places: number) => Math.round(n * 10 ** places) / 10 ** places;

interface PositionLike {
  coords: { latitude: number; longitude: number; accuracy: number | null };
  timestamp: number;
}

/** expo-location's position → the outbox's fix; null without an accuracy (R90 needs one). */
export function fixOf(pos: PositionLike | null | undefined): Fix | null {
  if (!pos || pos.coords.accuracy == null || !Number.isFinite(pos.coords.accuracy)) return null;
  const { latitude, longitude, accuracy } = pos.coords;
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  return {
    lat: round(latitude, 6),
    lng: round(longitude, 6),
    accuracy_m: round(accuracy, 1),
    fix_at: new Date(pos.timestamp).toISOString(),
  };
}

/** Does `next` replace `held`? */
export function betterFix(held: Fix | null, next: Fix | null, nowMs: number): Fix | null {
  if (!next) return held;
  if (!held) return next;
  const heldAge = nowMs - Date.parse(held.fix_at);
  if (heldAge > FIX_STALE_MS) return next;
  return next.accuracy_m <= held.accuracy_m ? next : held;
}

export interface ExpoLocationOptions {
  now?: () => number;
  /** Start the background watch (off in tests that drive `current()` only). */
  watch?: boolean;
}

export function expoLocation(opts: ExpoLocationOptions = {}): LocationDevice & { stop(): void; startWatch(): void } {
  const now = opts.now ?? (() => Date.now());
  let held: Fix | null = null;
  let sub: { remove(): void } | null = null;
  let starting = false;
  let stopped = false;
  const listeners = new Set<(fix: Fix) => void>();

  const keep = (fix: Fix | null) => {
    const before = held;
    held = betterFix(held, fix, now());
    // FB-003: a fix the handset now holds is told to whoever listens — the
    // camera's stamp, and the late position for a reading saved without one.
    if (held && held !== before) for (const l of [...listeners]) l(held);
  };

  const allowed = async () => {
    try {
      return (await Location.getForegroundPermissionsAsync()).granted;
    } catch {
      return false;
    }
  };

  // DEF-FLD-10605: the watch is started whenever permission is there — at
  // start-up, AND later when it is granted after start-up (`startWatch()` from
  // the permission grant, or the next `current()`). It used to start only at
  // construction, so a technician who allowed location after opening the app
  // held no fix until it restarted. Idempotent: one watch, however often asked.
  const startWatch = () => {
    if (opts.watch === false || stopped || sub || starting) return;
    starting = true;
    void (async () => {
      try {
        if (!(await allowed()) || stopped) return;
        const s = await Location.watchPositionAsync({ accuracy: Location.Accuracy.Balanced, ...WATCH }, (pos) => keep(fixOf(pos)));
        if (stopped) s.remove();
        else sub = s;
      } catch {
        // No watch: `current()` still asks when a screen needs a fix.
      } finally {
        starting = false;
      }
    })();
  };

  startWatch();

  return {
    async current() {
      if (!(await allowed())) return null;
      startWatch();
      const [fresh, lastKnown] = await Promise.all([
        Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High }).catch(() => null),
        Location.getLastKnownPositionAsync({ maxAge: LAST_KNOWN_MAX_AGE_MS }).catch(() => null),
      ]);
      keep(fixOf(lastKnown));
      keep(fixOf(fresh));
      // A held fix gone stale is not "where the handset is": no fix instead.
      return held && now() - Date.parse(held.fix_at) <= FIX_STALE_MS ? held : null;
    },
    last: () => held,
    startWatch,
    async ensureOn(): Promise<LocationAccess> {
      try {
        let answer = await Location.getForegroundPermissionsAsync();
        if (!answer.granted) {
          if (answer.canAskAgain === false) return 'blocked';
          // The platform's dialog is the app's own pop-up, never "leaving" (MQ-019).
          answer = await withSystemInteraction(() => Location.requestForegroundPermissionsAsync());
          if (!answer.granted) return answer.canAskAgain === false ? 'blocked' : 'refused';
        }
        startWatch();
        if (!(await Location.hasServicesEnabledAsync())) {
          // Android's own *Turn on location?* dialog. It rejects when declined
          // (and on iOS, which has no such dialog): the answer is re-read.
          await withSystemInteraction(() => Location.enableNetworkProviderAsync()).catch(() => undefined);
          if (!(await Location.hasServicesEnabledAsync())) return 'off';
        }
        return 'on';
      } catch {
        return 'unknown';
      }
    },
    subscribe(onFix) {
      listeners.add(onFix);
      return () => {
        listeners.delete(onFix);
      };
    },
    // Held until the app is active again — openSettings resolves on launch (MQ-019).
    openSettings: () => withSystemInteraction(() => Linking.openSettings(), { untilReturn: true }),
    stop() {
      stopped = true;
      sub?.remove();
      sub = null;
    },
  };
}
