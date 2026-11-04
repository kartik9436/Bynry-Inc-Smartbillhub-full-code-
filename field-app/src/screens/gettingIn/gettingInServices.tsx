/**
 * What the getting-in screens need besides the session: the auth client (for
 * activation — the session manager signs in, but activation is the server's
 * own calls), which UTILITY this handset signs in to, the device's name, and
 * two ports nothing on the branch provides yet.
 *
 *   api          `AuthApi`. The app root passes the one it built
 *                (`AppServices.api`); the default is the same HTTP client.
 *   utility      WHICH UTILITY THIS HANDSET SIGNS IN TO, remembered on the
 *                handset (`security/handsetUtility.ts`). ⚠ **LEARNED FROM THE
 *                OFFICE'S CODE, NEVER FROM THE BUILD** (`DEF-FLD-10580`, beta
 *                MQ-006; PO 2026-10-24: *"A. The code from the office sets the
 *                utility"*). The app is ONE build for every utility. On FF-56
 *                the technician types the six-character code from Settings ›
 *                Users; `POST /api/auth/activation/lookup` says which utility
 *                holds it (codes are unique across every utility, for ever);
 *                FF-57 remembers that utility once the password is set, and
 *                FF-05 signs in to it from then on — *Change* goes back to
 *                FF-56 for another code, which is how a contractor working for
 *                two utilities moves between them (EP-FLD-01 TC-6). Each
 *                utility's work stays in its own database file (R131).
 *                Until 2026-10-24 the utility came from `EXPO_PUBLIC_TENANT`,
 *                baked into the build, under an unfiled `TENANT_SOURCE_QUESTION`;
 *                both are gone, and no store or preview profile carries one.
 *   tenant /     a utility to START with — tests and previews only; the app
 *   utilityName  root passes neither. Seeds a memory store when no `utility`
 *                is given.
 *   deviceName   *Van 14 tablet* on FF-57. Read from the device register;
 *                when the handset has no name yet FF-57 asks for one.
 *   deviceId     this handset's id from the device register, which FF-57's
 *                activation registers the name against, and which the lookup
 *                door counts tries by. The default refuses (nothing to
 *                register with) rather than inventing an id.
 *   permissions  FF-07's three questions (`permissions.ts`).
 *   serverSet    whether this build was given a usable server address
 *                (`release/serverAddress.ts`). False: FF-05 says *No server
 *                set* and offers no sign-in. An `api` passed in (a test's
 *                fake, the app's own client) counts as set unless told.
 *   reset        FF-06's three ways back in (`passwordReset.ts`).
 */
import { createContext, type ReactNode, useContext, useMemo, useSyncExternalStore } from 'react';

import { type AuthApi } from '../../security/authApi';
import { type HandsetUtility, memoryHandsetUtility, type RememberedUtility } from '../../security/handsetUtility';
import { createHttpAuthApi } from '../../security/httpAuthApi';
import { useOptionalSession } from '../../session/SessionProvider';
import { type PasswordResetPort, resetNotWired } from './passwordReset';
import { type PermissionsPort, permissionsNotWired } from './permissions';
import { serverAddress } from '../../release/serverAddress';

export interface GettingInServices {
  api: AuthApi;
  utility: HandsetUtility;
  /** Tests and previews only: a utility to start with when no `utility` is given. */
  tenant?: string | null;
  utilityName?: string | null;
  deviceName: () => Promise<string | null>;
  deviceId: () => Promise<string>;
  permissions: PermissionsPort;
  reset: PasswordResetPort;
  serverSet: boolean;
}

const DEFAULTS: Omit<GettingInServices, 'utility'> = {
  api: createHttpAuthApi({ baseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? '' }),
  deviceName: async () => null,
  deviceId: () => Promise.reject(new Error('device register not wired into the getting-in screens')),
  permissions: permissionsNotWired,
  reset: resetNotWired,
  serverSet: serverAddress() !== null,
};

const GettingInContext = createContext<GettingInServices>({ ...DEFAULTS, utility: memoryHandsetUtility() });

export function GettingInProvider(props: { value: Partial<GettingInServices>; children: ReactNode }) {
  const { value, children } = props;
  const { utility: given, tenant, utilityName } = value;
  // One store per mount when none is given, so two mounts never share a utility.
  const utility = useMemo<HandsetUtility>(
    () => given ?? memoryHandsetUtility(tenant ? { tenant, utilityName: utilityName ?? null } : null),
    [given, tenant, utilityName],
  );
  const merged = useMemo<GettingInServices>(
    () => ({
      ...DEFAULTS,
      ...value,
      utility,
      serverSet: value.serverSet ?? (value.api ? true : DEFAULTS.serverSet),
    }),
    [value, utility],
  );
  return <GettingInContext.Provider value={merged}>{children}</GettingInContext.Provider>;
}

export function useGettingIn(): GettingInServices {
  return useContext(GettingInContext);
}

/**
 * The utility this handset signs in to, and re-renders when it changes: the
 * one remembered from the office's code, else — for a handset that predates
 * `DEF-FLD-10580` — the one the last technician on it signed in to. Null when
 * neither is known; FF-05 then offers only *Activate*, never a guessed utility.
 */
export function useHandsetUtility(): RememberedUtility | null {
  const { utility } = useGettingIn();
  const remembered = useSyncExternalStore(utility.subscribe, utility.current, utility.current);
  const session = useOptionalSession();
  if (remembered) return remembered;
  const known = session?.snapshot.known ?? [];
  const last = known.length > 0 ? known[known.length - 1] : undefined;
  return last?.tenant ? { tenant: last.tenant, utilityName: null } : null;
}

/** The slug alone — what every call's path names. */
export function useHandsetTenant(): string | null {
  return useHandsetUtility()?.tenant ?? null;
}
