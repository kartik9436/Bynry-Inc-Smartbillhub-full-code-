/**
 * What kind of connection the handset has — the sync engine asks before each
 * run (photos go on any connection unless *Photos on wi-fi only* is on —
 * PO 2026-10-28, FB-015; R54's wi-fi-by-default is SUPERSEDED)
 * and the work gate is told whether the handset is online (telemetry).
 *
 * The real one reads `@react-native-community/netinfo`. It is loaded lazily
 * and guarded: where the native module is absent (a test, a preview) the port
 * answers `none` — the safe answer, because "no connection" makes the sync
 * wait rather than pretend it sent.
 */
import type { NetworkKind } from '../sync/photos';

export interface NetworkPort {
  kind(): Promise<NetworkKind>;
  /** Called on every change; returns the unsubscribe. */
  subscribe(listener: (kind: NetworkKind) => void): () => void;
}

interface NetInfoStateLike {
  type?: string;
  isConnected?: boolean | null;
  isInternetReachable?: boolean | null;
}

export function kindOf(state: NetInfoStateLike | null | undefined): NetworkKind {
  if (!state || state.isConnected === false || state.isInternetReachable === false) return 'none';
  if (state.type === 'wifi' || state.type === 'ethernet') return 'wifi';
  if (state.type === 'cellular') return 'cellular';
  return state.isConnected ? 'cellular' : 'none';
}

interface NetInfoLike {
  fetch(): Promise<NetInfoStateLike>;
  addEventListener(listener: (state: NetInfoStateLike) => void): () => void;
}

function loadNetInfo(): NetInfoLike | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require('@react-native-community/netinfo') as { default?: NetInfoLike } & NetInfoLike;
    return mod.default ?? mod;
  } catch {
    return null;
  }
}

export function netInfoNetwork(): NetworkPort {
  const netInfo = loadNetInfo();
  return {
    async kind() {
      if (!netInfo) return 'none';
      try {
        return kindOf(await netInfo.fetch());
      } catch {
        return 'none';
      }
    },
    subscribe(listener) {
      if (!netInfo) return () => undefined;
      try {
        return netInfo.addEventListener((state) => listener(kindOf(state)));
      } catch {
        return () => undefined;
      }
    },
  };
}

/** A network a test drives. */
export class FakeNetwork implements NetworkPort {
  private readonly listeners = new Set<(kind: NetworkKind) => void>();
  constructor(public current: NetworkKind = 'wifi') {}
  kind(): Promise<NetworkKind> {
    return Promise.resolve(this.current);
  }
  subscribe(listener: (kind: NetworkKind) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
  set(kind: NetworkKind): void {
    this.current = kind;
    for (const l of this.listeners) l(kind);
  }
}
