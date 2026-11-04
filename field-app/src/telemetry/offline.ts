/**
 * Shared send discipline for both telemetry queues (R67): a send that throws,
 * rejects or hangs is a failure telemetry absorbs. Nothing here logs, alerts or
 * rethrows — a dead endpoint must be invisible to the technician.
 */
export type SendOutcome = 'sent' | 'yielded' | 'failed' | 'empty' | 'busy';

export async function withTimeout<T>(work: () => Promise<T>, ms: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      Promise.resolve().then(work),
      new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Error('telemetry send timed out')), ms);
      }),
    ]);
  } finally {
    if (timer !== undefined) clearTimeout(timer);
  }
}
