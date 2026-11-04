/**
 * The minimum-version refusal, handset half (DEF-FLD-10355; 07-endpoints row
 * N7; R117; 15-release-and-rollback.md §5.2–§5.3).
 *
 * WHAT THE APP SENDS. Every request from both HTTP clients — the sync
 * transport (`sync/transport.ts`, which carries the reads too) and sign-in
 * (`security/httpAuthApi.ts`) — carries `X-Field-App-Version` (the product
 * version, `2.590.0`), `X-Field-App-Build` (the binary's store build, when it
 * has one) and `X-Field-App-Platform`. The server compares the version with
 * its `FIELD_APP_MIN_VERSION` (`06-backend/core/field_app_version.py`).
 *
 * WHAT THE APP DOES WITH A REFUSAL. A 426 whose `params.reason` is
 * `app_too_old` raises ONE signal, held here; `UpdateRequiredGate` shows the
 * *Update the app* screen over everything while it is up. The signal lives in
 * memory only: a store update restarts the app, so it clears itself, and a
 * restart without the update raises it again on the first refused call.
 *
 * UNSENT WORK IS NEVER TOUCHED BY IT. A refused batch is put back as pending
 * with no attempt counted (`sync/receipts.ts`), the run stops, and the pull is
 * skipped — but the server still ACCEPTS captured work from an old build
 * (07-endpoints §0 rule 2), so the outbox keeps draining while it does, and
 * whatever is refused sends after the update.
 */
import { nativeBuildNumber, PRODUCT_VERSION } from './build';

export const VERSION_HEADER = 'X-Field-App-Version';
export const BUILD_HEADER = 'X-Field-App-Build';
export const PLATFORM_HEADER = 'X-Field-App-Platform';
export const SCHEMA_HEADER = 'X-Field-Schema-Version';

export const UPGRADE_REQUIRED = 426;
export const REASON_APP_TOO_OLD = 'app_too_old';

function platformOs(): string | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const os = (require('react-native') as { Platform?: { OS?: string } }).Platform?.OS;
    return typeof os === 'string' ? os : null;
  } catch {
    return null;
  }
}

/** The headers every field-app request carries. A missing build or platform is left out, never made up. */
export function fieldAppHeaders(
  version: string = PRODUCT_VERSION,
  build: string | null = nativeBuildNumber(),
  platform: string | null = platformOs(),
): Record<string, string> {
  const out: Record<string, string> = { [VERSION_HEADER]: version };
  if (build) out[BUILD_HEADER] = build;
  if (platform) out[PLATFORM_HEADER] = platform;
  return out;
}

/** The server's minimum when `status`/`body` are the `app_too_old` refusal, else undefined. */
export function tooOldMinimum(status: number, body: unknown): string | null | undefined {
  if (status !== UPGRADE_REQUIRED || body == null || typeof body !== 'object') return undefined;
  const params = (body as { params?: { reason?: unknown; minimum?: unknown } }).params;
  if (params?.reason !== REASON_APP_TOO_OLD) return undefined;
  return typeof params.minimum === 'string' && params.minimum !== '' ? params.minimum : null;
}

export interface UpdateState {
  required: boolean;
  /** The server's minimum, when it said one. */
  minimum: string | null;
}

export interface UpdateSignal {
  get(): UpdateState;
  /** Raised by a client that met `app_too_old`. */
  raise(minimum: string | null): void;
  subscribe(listener: (state: UpdateState) => void): () => void;
  /** Tests only: back to "not required". */
  reset(): void;
}

export function createUpdateSignal(): UpdateSignal {
  let state: UpdateState = { required: false, minimum: null };
  const listeners = new Set<(state: UpdateState) => void>();
  const emit = () => listeners.forEach((l) => l(state));
  return {
    get: () => state,
    raise(minimum) {
      if (state.required && state.minimum === minimum) return;
      state = { required: true, minimum: minimum ?? state.minimum };
      emit();
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    reset() {
      state = { required: false, minimum: null };
      emit();
    },
  };
}

/** THE app's one signal — both HTTP clients raise it, the gate and the runtime read it. */
export const appUpdate: UpdateSignal = createUpdateSignal();
