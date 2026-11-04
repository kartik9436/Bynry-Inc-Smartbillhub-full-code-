/**
 * CERTIFICATE PINNING, ENFORCED — the native half of `pins.ts`
 * (`OQ-FLD-12797`; `18-field-app/12-security.md` §4 *Transport*).
 *
 * The library is `react-native-ssl-public-key-pinning` (Expo SDK 53, a plain
 * autolinked native module — it needs a development or store build and does
 * nothing in Expo Go, which `isAvailable()` reports). Once initialised it pins
 * EVERY `fetch` to the server's host: OkHttp on Android, TrustKit on iOS. A
 * connection whose chain holds none of the keys is refused before a byte of
 * the request is sent.
 *
 * `PinningController` owns three things:
 *  - **the set in force** — the stored server list (`PinStore`), else the
 *    build's starting set (`extra.pins`);
 *  - **whether pinning is actually on** (`state`), which is what
 *    `arrivedPinned` means: a settings answer received while the state is
 *    `enforced` came over a pinned connection, because the library refuses
 *    every other one;
 *  - **the refresh** — `refresh(api)` reads `GET work/mobile/settings` and
 *    adopts the server's list only on `decideAdoption`'s say-so.
 *
 * ⚠ **`expirationDate` IS THE LATEST PIN'S LAST DAY, ON PURPOSE.** The library
 * stops pinning after that date. The design's warning is that *"a pinned app
 * with one expired pin is a fleet that cannot sync"*; a phone whose EVERY key
 * has expired, and which never managed to fetch the new list, would otherwise
 * be bricked until somebody reinstalled it. The office's 60-day warning on
 * Settings › Security exists so this date is never reached.
 *
 * ⚠ **THIS MODULE IS DORMANT — NO BUILD PINS (`CR-195-BRC10`; decision log
 * 2026-10-28, PO: *"start A1"*).** Pinning was dropped as a go-live
 * requirement; the phone relies on Android's standard certificate validation
 * (system authorities only — a user-installed authority is ignored from API
 * 24, cleartext is blocked from API 28; no `network_security_config`, no TLS
 * bypass anywhere). Unless the build's config says exactly
 * `extra.pinning: 'on'` (`pinningMode`, from `FIELD_APP_PINNING`; both EAS
 * profiles say `off`), `start()` never touches the native module,
 * `refresh()` never asks for or adopts the server's list (one adopted over an
 * unpinned connection is exactly what `decideAdoption` refuses), it is logged
 * once, and `pinningState()` reads `off_by_config`. **Nothing is shown to the
 * user** (Settings › About's *"Beta build — certificate check off"* was
 * removed the same day). The code is KEPT so it returns as configuration
 * only: `FIELD_APP_PINNING=on` plus the server's confirmed issuer and one
 * backup, in the build and in Settings › Security (whose card is hidden
 * behind `SBH_FIELD_APP_PINNING_ENABLED` on the server). This began
 * 2026-10-26 as a beta-only switch (`DEF-FLD-10617`); that entry's *"no
 * protection from a fake server on public Wi-Fi"* was CORRECTED on
 * 2026-10-28 — the standard check refuses a fake server; pinning adds only
 * protection against a wrongly issued real certificate or a rooted phone.
 *
 * A pin mismatch the library reports is passed to `noteCertificateRefusal`, so
 * the failed `fetch` behind it says *Can't verify the server* rather than *No
 * signal* (`certificateRefusal.ts`).
 */
import {
  addSslPinningErrorListener,
  initializeSslPinning,
  isSslPinningAvailable,
  type PinningOptions,
} from 'react-native-ssl-public-key-pinning';

import { noteCertificateRefusal } from './certificateRefusal';
import type { KeyValueStore } from './prefs';
import { decideAdoption, MIN_PINS, parsePins, type Adoption, type Pin, type PinningMode, usablePins, utcDay } from './pins';

/** The native library, behind a port so a test drives it. */
export interface PinningNative {
  isAvailable(): boolean;
  initialize(options: PinningOptions): Promise<void>;
  /** Told of each pin mismatch (optional: a test's fake need not report). */
  onRefusal?(listener: () => void): void;
}

export const nativePinning: PinningNative = {
  isAvailable: () => isSslPinningAvailable(),
  initialize: (options) => initializeSslPinning(options),
  onRefusal: (listener) => {
    addSslPinningErrorListener(() => listener());
  },
};

/** `GET work/mobile/settings` — the slice of it this file reads. */
export interface SettingsApi {
  settings(): Promise<{ field_app_pins?: unknown }>;
}

export function asSettingsApi(x: unknown): SettingsApi | null {
  return x && typeof (x as SettingsApi).settings === 'function' ? (x as SettingsApi) : null;
}

const STORE_KEY = 'security.pins.v1';

/** The server's list as last adopted, kept in the encrypted preferences. */
export class PinStore {
  constructor(private readonly kv: KeyValueStore) {}

  read(): Pin[] | null {
    const raw = this.kv.getString(STORE_KEY);
    if (!raw) return null;
    try {
      return parsePins(JSON.parse(raw));
    } catch {
      return null;
    }
  }

  write(pins: readonly Pin[]): void {
    this.kv.set(STORE_KEY, JSON.stringify(pins));
  }
}

export type PinningState =
  /** Every connection to the server is pinned. */
  | 'enforced'
  /** This binary has no pinning module (Expo Go, a test) — nothing is pinned. */
  | 'unavailable'
  /** The build names no server, so there is no host to pin. */
  | 'no_host'
  /** Fewer than two unexpired keys in the set in force — the build's config is wrong. */
  | 'no_valid_pins'
  /** The module refused the set. */
  | 'failed'
  /** `start()` has not run. */
  | 'off'
  /** This build pins nothing on purpose — `extra.pinning` is not `on` (dormant, CR-195-BRC10). */
  | 'off_by_config';

/** The latest controller's state, for diagnostics. */
let reported: PinningState = 'off';

/** Whether this phone pins right now — `off_by_config` while pinning is dormant. For diagnostics only; never shown. */
export function pinningState(): PinningState {
  return reported;
}

let saidOffOnce = false;

export function hostOf(origin: string): string | null {
  const m = /^https?:\/\/([^/:?#\s]+)/i.exec(origin.trim());
  return m ? m[1]!.toLowerCase() : null;
}

export interface PinningControllerDeps {
  native: PinningNative;
  store: PinStore;
  /** The build's starting set (`bootstrapPins(extra)`). */
  bootstrap: readonly Pin[];
  /** The server's origin (`EXPO_PUBLIC_API_BASE_URL`). */
  origin: string;
  now: () => Date;
  /** `pinningMode(extra)` — `off` unless the build says exactly `on`. Default `off` (CR-195-BRC10). */
  mode?: PinningMode;
}

export class PinningController {
  private stateValue: PinningState = 'off';
  private listening = false;

  constructor(private readonly deps: PinningControllerDeps) {}

  get state(): PinningState {
    return this.stateValue;
  }

  private get stateNow(): PinningState {
    return this.stateValue;
  }

  private set stateNow(next: PinningState) {
    this.stateValue = next;
    reported = next;
  }

  private get off(): boolean {
    return this.deps.mode !== 'on';
  }

  /** The set in force: the server's last adopted list, else the build's starting set. */
  current(): Pin[] {
    return this.deps.store.read() ?? [...this.deps.bootstrap];
  }

  private options(host: string, pins: readonly Pin[]): PinningOptions {
    const lastDay = pins.map((p) => p.not_after).sort().pop();
    return {
      [host]: {
        includeSubdomains: false,
        publicKeyHashes: pins.map((p) => p.spki_sha256),
        ...(lastDay ? { expirationDate: lastDay } : {}),
      },
    };
  }

  private async apply(pins: readonly Pin[]): Promise<PinningState> {
    const host = hostOf(this.deps.origin);
    if (!host) return (this.stateNow = 'no_host');
    if (!this.deps.native.isAvailable()) return (this.stateNow = 'unavailable');
    const usable = usablePins(pins, utcDay(this.deps.now()));
    if (usable.length < MIN_PINS) return (this.stateNow = 'no_valid_pins');
    try {
      await this.deps.native.initialize(this.options(host, usable));
      if (!this.listening && this.deps.native.onRefusal) {
        this.listening = true;
        this.deps.native.onRefusal(() => noteCertificateRefusal());
      }
      return (this.stateNow = 'enforced');
    } catch {
      return (this.stateNow = 'failed');
    }
  }

  /** Pin every connection to the server with the set in force. Before ANY request. */
  start(): Promise<PinningState> {
    if (this.off) {
      if (!saidOffOnce) {
        saidOffOnce = true;
        console.warn('[security] certificate pinning is OFF in this build (dormant, CR-195-BRC10)');
      }
      return Promise.resolve((this.stateNow = 'off_by_config'));
    }
    return this.apply(this.current());
  }

  /**
   * Read the server's list and adopt it when `decideAdoption` allows —
   * only over a pinned connection, never one that leaves fewer than two
   * unexpired keys or no key in common with the set in force. A refusal keeps
   * the last good set untouched. Network errors propagate to the caller.
   */
  async refresh(api: SettingsApi): Promise<Adoption> {
    // A build that pins nothing cannot trust anything it hears as a key list.
    if (this.off) return { adopt: false, reason: 'pinning_off' };
    const pinnedBefore = this.stateNow === 'enforced';
    const body = await api.settings();
    const decision = decideAdoption({
      current: this.current(),
      incoming: body?.field_app_pins,
      // Pinned when asked AND still pinned when answered.
      arrivedPinned: pinnedBefore && this.stateNow === 'enforced',
      today: utcDay(this.deps.now()),
    });
    if (decision.adopt) {
      this.deps.store.write(decision.pins);
      await this.apply(decision.pins);
    }
    return decision;
  }
}
