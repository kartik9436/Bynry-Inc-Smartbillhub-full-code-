/**
 * The server this build talks to: `EXPO_PUBLIC_API_BASE_URL`, written into the
 * JavaScript at BUILD time (Expo inlines `EXPO_PUBLIC_*`), so each EAS profile
 * names its own server in `eas.json` → `build.<profile>.env`.
 *
 * ⚠ **NEVER A RELATIVE ADDRESS.** On a handset there is no page origin: an
 * empty base would turn every call into `/api/<tenant>/…`, which goes
 * nowhere and fails as "no signal" — the technician would be told to find
 * wi-fi when the build itself is wrong. So an address is accepted only when it
 * is an absolute `https://host…`, and everything that talks to the server
 * refuses with `NoServerError` otherwise; FF-05 then says *No server set*.
 *
 * ⚠ **`https://` ONLY — `http://` IS REFUSED (`CR-195-BRC10`, 2026-10-28).**
 * Certificate pinning is dormant (PO *"start A1"*), so the standard TLS check
 * is the transport's whole protection, and a plain `http` address would skip
 * it. No EAS profile uses `http` (`development` names no server), so there is
 * no development exception; add one behind an explicit flag only if a
 * profile ever needs it.
 *
 * `eas.json`'s `preview` profile carries `__SET_STAGING_URL__` until the
 * staging address is known; that placeholder (or anything still holding
 * `__`) counts as no address, so a build made before the address arrives
 * says so on the sign-in screen instead of calling a host named
 * `__SET_STAGING_URL__`.
 */
export const STAGING_URL_PLACEHOLDER = '__SET_STAGING_URL__';

/** The build's server, trailing slashes removed — or null when it has none usable. */
export function serverAddress(raw: string | null | undefined = process.env.EXPO_PUBLIC_API_BASE_URL): string | null {
  const v = (raw ?? '').trim().replace(/\/+$/, '');
  if (v === '' || v === STAGING_URL_PLACEHOLDER || v.includes('__')) return null;
  return /^https:\/\/[^/\s?#]+/i.test(v) ? v : null;
}

/** Thrown instead of calling a server this build was not given. */
export class NoServerError extends Error {
  constructor() {
    super('no server address in this build (EXPO_PUBLIC_API_BASE_URL)');
    this.name = 'NoServerError';
  }
}

/** The address, or a `NoServerError`. */
export function requireServer(raw: string | null | undefined): string {
  const v = serverAddress(raw);
  if (v === null) throw new NoServerError();
  return v;
}
