/**
 * The yield rule — T-73, R67, AD-18: telemetry is the THIRD queue and yields to
 * the outbox and the photo queue, always. A day of readings matters more than
 * our telemetry.
 *
 * The sync engine owns the other two queues and tells this gate about them by
 * calling `reportWork()`; telemetry asks `canSend()` before every send, and the
 * sync engine may ask it too. Nothing here reads the outbox itself — that would
 * be a write-adjacent dependency on another module's tables.
 *
 * FAILS CLOSED (hard-won law 3): until the sync engine has reported once,
 * `canSend()` is false. So until the sync engine is wired to this gate,
 * telemetry stays queued on the handset — it does not compete with work it
 * cannot see. That wiring is the sync lane's task; see `index.ts`.
 */

export interface WorkQueueState {
  /** Rows waiting in the outbox. */
  outbox: number;
  /** Photographs waiting to upload. */
  photos: number;
  /** A sync is running right now (a pull, a send, an upload). */
  syncing: boolean;
  /** The handset has a connection worth using. */
  online: boolean;
}

export interface WorkGate {
  reportWork(state: WorkQueueState): void;
  canSend(): boolean;
  /** Why not, for tests and the debug screen; never shown to a technician. */
  reason(): 'unreported' | 'offline' | 'syncing' | 'outbox' | 'photos' | 'clear';
}

export function createWorkGate(): WorkGate {
  let state: WorkQueueState | null = null;
  const reason: WorkGate['reason'] = () => {
    if (!state) return 'unreported';
    if (!state.online) return 'offline';
    if (state.syncing) return 'syncing';
    if (state.outbox > 0) return 'outbox';
    if (state.photos > 0) return 'photos';
    return 'clear';
  };
  return {
    reportWork(next) {
      state = { ...next };
    },
    canSend: () => reason() === 'clear',
    reason,
  };
}
