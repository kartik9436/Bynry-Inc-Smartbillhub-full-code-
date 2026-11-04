/**
 * Exponential backoff with jitter, capped (Mobile data §4):
 * 2s, 4s, 8s, 30s, 2m, 10m — and 10m from then on. After five failures the
 * row shows on FF-50 as needing attention; it is never dropped.
 */
export const BACKOFF_STEPS_MS = [2_000, 4_000, 8_000, 30_000, 120_000, 600_000] as const;
export const BACKOFF_CAP_MS = 600_000;
export const NEEDS_ATTENTION_AFTER = 5;
/** ± this share of the step, so a depot full of handsets does not retry in step. */
export const JITTER = 0.2;

/** The delay before attempt `failures + 1`, given `failures` so far (≥ 1). */
export function backoffMs(failures: number, random: () => number = Math.random): number {
  const step = BACKOFF_STEPS_MS[Math.min(Math.max(failures, 1), BACKOFF_STEPS_MS.length) - 1] ?? BACKOFF_CAP_MS;
  const jittered = step * (1 - JITTER + 2 * JITTER * random());
  return Math.min(Math.round(jittered), BACKOFF_CAP_MS);
}

export function nextAttemptAt(now: Date, failures: number, random?: () => number): string {
  return new Date(now.getTime() + backoffMs(failures, random)).toISOString();
}
