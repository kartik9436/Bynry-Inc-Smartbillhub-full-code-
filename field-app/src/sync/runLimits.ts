/**
 * EVERY STEP OF A SYNC RUN HAS A TIME LIMIT (DEF-FLD-10624, decision log
 * 2026-10-27, *"start A to F"* — F).
 *
 * A run is one promise that every later *Sync now* joins. Until this, only the
 * WIRE had limits (`transport.ts`, 30 s a call); the steps around it — the
 * network check (`NetInfo.fetch`), the retention purge, the queue count, the
 * turn-ins, the week, the certificate keys — had none, and one that never
 * settled kept the run alive forever: every press joined a dead run, and an
 * app restart could hang on the same step again. The PO's phone showed ONLINE
 * with 16 waiting for fifteen minutes and made no request at all.
 *
 * `within` ends the WAIT, not the work: the step may still finish later. That
 * is safe here because every send is keyed (a late repeat is a duplicate, R49)
 * and the next run puts rows left `sending` back to pending.
 */

export interface RunLimits {
  /** The network check: a check that does not answer is *unknown — try anyway*, never *no signal*. */
  networkMs: number;
  /** Any one step outside the engine (purge, queue count, sign-in renewal, turn-ins, week, keys). */
  stepMs: number;
  /** The engine's whole run (push, photographs, pull, bundles); each call inside has its own 30 s. */
  runMs: number;
}

export const DEFAULT_RUN_LIMITS: RunLimits = {
  networkMs: 5_000,
  stepMs: 60_000,
  runMs: 10 * 60_000,
};

/** A step did not answer inside its limit. Never a network error: it says *Run timed out*. */
export class StepTimeLimitError extends Error {
  constructor(
    readonly step: string,
    readonly limitMs: number,
  ) {
    super(`${step}: no answer in ${limitMs} ms`);
    this.name = 'StepTimeLimitError';
  }
}

/** `work`, or a `StepTimeLimitError` after `ms` — whichever comes first. */
export function within<T>(work: Promise<T>, ms: number, step: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const limit = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new StepTimeLimitError(step, ms)), ms);
  });
  return Promise.race([work, limit]).finally(() => clearTimeout(timer));
}
