/**
 * WHICH UTILITY THIS HANDSET SIGNS IN TO — learned from the office's code,
 * remembered on the handset, never baked into the build (`DEF-FLD-10580`,
 * beta report MQ-006).
 *
 * PO 2026-10-24, verbatim: *"A. The code from the office sets the utility
 * (recommended) - this is correct option"*. The app is ONE build for every
 * utility. A technician types the six-character code the office gave them on
 * FF-56; `POST /api/auth/activation/lookup` answers which utility holds it
 * (codes are unique across every utility, for ever — the server's register);
 * once they have set their password on FF-57 the utility is remembered HERE,
 * and every later sign-in on FF-05 uses it. *Change* on FF-05 goes back to
 * FF-56 and another code.
 *
 * Kept in the encrypted preference store (`prefs.ts`, MMKV): a utility's slug
 * and name are not secrets, and neither is the last login typed on this
 * handset — the session already keeps the logins it knows in the same store.
 * The last login is kept PER UTILITY, so a contractor who works for two keeps
 * each one's pre-filled email. Each utility's captured work is in its own
 * database file (`db/database.ts`, `field-<tenant>.sqlite`, R131), so changing
 * utility moves nothing between them.
 */
import { type KeyValueStore, MemoryKeyValueStore } from './prefs';

export interface RememberedUtility {
  /** The utility's slug — the path segment every call names, and the store's file name. */
  tenant: string;
  /** *City of Houston* — as the server named it. Null only for a handset that predates this. */
  utilityName: string | null;
}

export interface HandsetUtility {
  current(): RememberedUtility | null;
  remember(utility: RememberedUtility): void;
  /** The email or phone last signed in with at this utility on this handset. */
  lastLogin(tenant: string): string | null;
  rememberLogin(tenant: string, login: string): void;
  subscribe(listener: () => void): () => void;
}

const KEY_UTILITY = 'handset.utility';
const KEY_LAST_LOGIN = 'handset.utility.lastLogin.';

function parse(raw: string | undefined): RememberedUtility | null {
  if (!raw) return null;
  try {
    const v = JSON.parse(raw) as Partial<RememberedUtility>;
    if (typeof v.tenant !== 'string' || v.tenant.trim() === '') return null;
    return { tenant: v.tenant, utilityName: typeof v.utilityName === 'string' && v.utilityName !== '' ? v.utilityName : null };
  } catch {
    return null;
  }
}

/** The handset's remembered utility, in the given preference store. */
export function handsetUtilityIn(prefs: KeyValueStore): HandsetUtility {
  const listeners = new Set<() => void>();
  let cached = parse(prefs.getString(KEY_UTILITY));
  const emit = () => {
    for (const l of listeners) l();
  };
  return {
    current: () => cached,
    remember(utility) {
      cached = { tenant: utility.tenant.trim().toLowerCase(), utilityName: utility.utilityName || null };
      prefs.set(KEY_UTILITY, JSON.stringify(cached));
      emit();
    },
    lastLogin(tenant) {
      const v = prefs.getString(KEY_LAST_LOGIN + tenant.toLowerCase());
      return v && v !== '' ? v : null;
    },
    rememberLogin(tenant, login) {
      const v = login.trim();
      if (v === '') return;
      prefs.set(KEY_LAST_LOGIN + tenant.toLowerCase(), v);
      emit();
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}

/** For tests and previews: a fresh memory store, optionally already holding a utility. */
export function memoryHandsetUtility(seed?: RememberedUtility | null): HandsetUtility {
  const store = handsetUtilityIn(new MemoryKeyValueStore());
  if (seed) store.remember(seed);
  return store;
}
