/**
 * THE APP'S OWN SYSTEM POP-UPS NEVER COUNT AS LEAVING (MQ-019, decision log
 * 2026-10-26; DEF-FLD-10614).
 *
 * Android reports its own permission dialog as the app going to the
 * background, so before this guard answering *Don't allow* on the camera
 * question locked the app mid-job. Every place the app asks the platform for
 * something wraps the call in `withSystemInteraction`; while the guard is up,
 * `SessionManager.onBackground()` ignores the report entirely — no time away
 * is recorded.
 *
 * The call sites, and nothing else (a Call or Navigate hand-off IS leaving):
 *   - permission requests — `device/native/permissions.ts` (location, camera,
 *     notifications), the camera hook in `device/native/DeviceHost.tsx`, the
 *     microphone in `device/native/dictation.ts`;
 *   - opening the app's settings (`Linking.openSettings`) — `untilReturn`,
 *     because that promise resolves as soon as the settings screen launches,
 *     BEFORE the platform reports the background; the guard then holds until
 *     the app is active again (`systemInteractionReturned`);
 *   - the fingerprint prompt — `device/native/biometric.ts`;
 *   - the platform file picker — `device/native/files.ts` (FF-60 *A file*).
 *
 * A counter, not a flag, so two overlapping asks cannot release each other.
 * A failed call releases its hold, so a refused settings launch cannot leave
 * every later real leave ignored.
 */

let pending = 0;
let holdUntilReturn = false;

export function isSystemInteractionActive(): boolean {
  return pending > 0 || holdUntilReturn;
}

export async function withSystemInteraction<T>(ask: () => Promise<T>, opts: { untilReturn?: boolean } = {}): Promise<T> {
  pending += 1;
  if (opts.untilReturn) holdUntilReturn = true;
  try {
    return await ask();
  } catch (err) {
    if (opts.untilReturn) holdUntilReturn = false;
    throw err;
  } finally {
    pending -= 1;
  }
}

/** The app is active again: a settings visit it opened is over. */
export function systemInteractionReturned(): void {
  holdUntilReturn = false;
}

export function resetSystemInteractionForTests(): void {
  pending = 0;
  holdUntilReturn = false;
}
