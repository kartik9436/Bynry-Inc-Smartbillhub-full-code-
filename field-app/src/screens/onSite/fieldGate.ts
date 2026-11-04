/**
 * FB-028 — how a job RAISED ON SITE gates its own reconnect and disconnect
 * steps (PO rulings of 2026-10-31, decision log *"FB-028: raised reconnects go
 * to the technician…"* and *"Field-raised disconnects go to the technician with
 * the live checks; the reconnect limit lives on the work-order template"*).
 *
 *   RECONNECT (FF-61). *"if outstanding balance for a given customer reduces
 *     below 25 dollors (for example) then techncinan should able to perform
 *     reconnect"*. The live balance AT OR BELOW the job's Reconnect limit (the
 *     template's, copied onto the job) enables Reconnect; above it the step
 *     stops — *"Still owes $804.50. Leave it off."* — and the office is told.
 *     A figure that is not fresh (no signal, or older than five minutes, R17's
 *     bar) CANNOT pass: *"Check the balance with signal."* A POSTED payment
 *     counts (F2 = A) — the read's balance already nets it.
 *   DISCONNECT (FF-27). The step stops on a cleared balance (FB-013, already
 *     on the screen for every job), and on a raised job ALSO while the notice
 *     period runs (*"Notice period ends 5 Nov. Leave it on."*) or the account
 *     is protected (*"Protected account. Leave it on."*). Each stop is told to
 *     the office.
 *
 * ⚠ **ONLY A JOB RAISED ON SITE IS GATED HERE.** The office-requested
 * reconnect (2026-10-29 C1) is never refused for owing, and that ruling is
 * unchanged: the job's details say `raised_on_site` (the server's bundle) and
 * the money read carries `field_gate` only for such a job.
 *
 * Money is compared as DIGITS (hard rule 2), never as a float: both sides are
 * scaled to four places as integers.
 */
import type { GateFacts, MoneyReading, StopReason } from './money';

/** A decimal string as ten-thousandths, or null when it is not one. */
export function tenThousandths(amount: string | null | undefined): bigint | null {
  if (typeof amount !== 'string') return null;
  const m = /^(-)?(\d+)(?:\.(\d+))?$/.exec(amount.trim());
  if (!m) return null;
  const frac = `${m[3] ?? ''}0000`.slice(0, 4);
  const value = BigInt(`${m[2]}${frac}`);
  return m[1] === '-' ? -value : value;
}

/** True when `owing` is at or below `limit`; false when either is unreadable. */
export function atOrBelow(owing: string | null | undefined, limit: string | null | undefined): boolean {
  const a = tenThousandths(owing);
  const b = tenThousandths(limit);
  return a !== null && b !== null && a <= b;
}

export type ReconnectGate =
  /** Not a raised job, or its template carries no limit: the screen as before. */
  | { kind: 'none' }
  /** At or below the limit, on a fresh figure: Reconnect is enabled. */
  | { kind: 'pass' }
  /** Above the limit: leave it off; the office is told. */
  | { kind: 'stop'; reason: StopReason; owing: string; limit: string }
  /** No fresh figure: cannot pass. `withheld` for a contractor (R26). */
  | { kind: 'blocked'; why: 'stale' | 'withheld' };

export function reconnectGate(input: {
  raisedOnSite: boolean;
  limit: string | null;
  employee: boolean;
  reading: MoneyReading | null;
  stale: boolean;
}): ReconnectGate {
  if (!input.raisedOnSite || input.limit === null) return { kind: 'none' };
  if (!input.employee) return { kind: 'blocked', why: 'withheld' };
  const r = input.reading;
  if (r === null || input.stale) return { kind: 'blocked', why: 'stale' };
  if (atOrBelow(r.balance, input.limit)) return { kind: 'pass' };
  return { kind: 'stop', reason: 'owes_over_limit', owing: r.balance, limit: input.limit };
}

export type DisconnectGate =
  | { kind: 'none' }
  | { kind: 'stop'; reason: 'notice_open'; endsOn: string }
  | { kind: 'stop'; reason: 'protected' }
  /** A raised job with no figure at all: the facts are unknown, so it waits. */
  | { kind: 'blocked'; why: 'stale' };

/**
 * The two stops a RAISED disconnect adds to FB-013's cleared-balance stop.
 * Protection first (it outlives any notice), then the notice period. A figure
 * that is merely old still carries both facts (they are dates and a list, not
 * a balance), so R17's warning keeps governing the balance itself; with no
 * figure ever read the facts are unknown and the step waits for a signal.
 */
export function disconnectGate(input: { raisedOnSite: boolean; employee: boolean; reading: MoneyReading | null }): DisconnectGate {
  if (!input.raisedOnSite) return { kind: 'none' };
  const facts: GateFacts | null | undefined = input.reading?.gate;
  if (!facts) return input.employee ? { kind: 'blocked', why: 'stale' } : { kind: 'none' };
  if (facts.protected) return { kind: 'stop', reason: 'protected' };
  if (facts.noticeOpen && facts.noticeEndsOn) return { kind: 'stop', reason: 'notice_open', endsOn: facts.noticeEndsOn };
  return { kind: 'none' };
}

/** One tell per job and reason per app session — a screen re-rendering, or
 *  opened twice, does not tell the office twice (the server's notice is also
 *  written once per job and reason). */
const told = new Set<string>();

export function tellOnce(
  port: { tellOffice?: (id: string, stop: { reason: StopReason; owing?: string | null; limit?: string | null; moneyAsAt?: string | null; endsOn?: string | null }) => Promise<void> },
  workOrderId: string,
  stop: { reason: StopReason; owing?: string | null; limit?: string | null; moneyAsAt?: string | null; endsOn?: string | null },
): void {
  const key = `${workOrderId}|${stop.reason}`;
  if (told.has(key) || !port.tellOffice) return;
  told.add(key);
  port.tellOffice(workOrderId, stop).catch(() => told.delete(key));
}

/** Tests only: forget what was told. */
export function resetTold(): void {
  told.clear();
}
