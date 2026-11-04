/**
 * The money the field app READS (R16: it never writes it), and how old it is.
 *
 * The read is the server's PER-JOB door, `GET work/mobile/jobs/{id}/money`
 * (`apps/work/money.money_read`): the job's account balance, the latest
 * payment that stands and its state, any fee a step names, and — on a
 * disconnect job — the payment plan and the disconnect notice. So the port is
 * keyed by the WORK ORDER, never by an account: a downloaded job need not know
 * its account for *Check now* to ask (DEF-FLD-10790, FB-023).
 *
 * FB-023 F1 (PO 2026-10-31): checked live when a money screen opens, online;
 * offline the LAST figure is shown with its age, and it is kept on the
 * handset (`db/queries/moneyLast.ts`) so a restart does not lose it.
 *
 * Amounts are decimal STRINGS (hard rule 2). The money is never stored in the
 * `customer` table (Mobile data §2); its `asAt` — the server's own stamp — is
 * what makes a kept figure honest.
 */

/** R17: "Money older than 5 minutes is warned, never blocked." */
export const MONEY_FRESH_MINUTES = 5;

export interface PaymentFact {
  amount: string;
  /** When it was posted, or — once the bank statement agrees — cleared. */
  at: string;
  /**
   * FB-023 F2 (PO 2026-10-31): `posted` when taken, `cleared` when the bank
   * statement agrees (CR-186-BRC10). A posted payment COUNTS as paid for the
   * step and is labelled *Posted*, never *Cleared* (DEF-FLD-10792).
   */
  state: 'posted' | 'cleared';
  /** Tender in the server's own words ("Card"). Shown, never interpreted. */
  method?: string | null;
}

/** FB-023 F5 — what a DISCONNECT job adds (null on every other job). */
export interface DisconnectFacts {
  /** `on_track`, `behind`, or null for no payment plan in force. */
  plan: 'on_track' | 'behind' | null;
  /** The latest disconnect notice on the open case: type, date, amount. */
  notice: { tier: string; issuedOn: string; amount: string | null } | null;
}

/** FB-028 — what a job RAISED ON SITE adds to its read (null elsewhere). */
export interface GateFacts {
  /** The last day of the disconnect notice period, `YYYY-MM-DD`, or null. */
  noticeEndsOn: string | null;
  /** True while today is on or before `noticeEndsOn` (the server's date). */
  noticeOpen: boolean;
  /** A medical certificate, a kept plan or a moratorium is in force. */
  protected: boolean;
}

/** FB-028 — the four stops the office is told about (`step_gates.STOP_REASONS`). */
export type StopReason = 'owes_over_limit' | 'balance_cleared' | 'notice_open' | 'protected';

export interface MoneyReading {
  /** The job the figure was read for — the port's key. */
  workOrderId: string;
  currency: string;
  /** What is owed now. */
  balance: string;
  /** When the server read the balance — the figure's age is measured from here. */
  asAt: string;
  /** The latest payment that stands, posted or cleared (FF-26, FF-61). */
  latestPayment?: PaymentFact | null;
  /** What the arrears were before that payment (FF-61 "Was $312.40"). */
  arrearsBefore?: string | null;
  /** N14: the reconnect fee, its own question beside the arrears (R111). */
  reconnectFee?: { amount: string; chargedAt: string; paid: boolean; paidAt?: string | null } | null;
  /** FB-023 F5 — disconnect jobs only. */
  disconnect?: DisconnectFacts | null;
  /** FB-028 — jobs raised on site only. */
  gate?: GateFacts | null;
}

export interface MoneyPort {
  /** Ask the server now, for one job. Rejects offline or with no server. */
  check(workOrderId: string, technicianId?: string): Promise<MoneyReading>;
  /** The last answer the handset holds for this job, however old. */
  lastKnown(workOrderId: string, technicianId?: string): MoneyReading | null;
  /** FB-028 — a raised job's gated step stopped: tell the office. Online;
   *  absent where there is no server. */
  tellOffice?(workOrderId: string, stop: { reason: StopReason; owing?: string | null; limit?: string | null; moneyAsAt?: string | null; endsOn?: string | null }): Promise<void>;
}

/** A named gap: thrown where a call has nothing behind it yet. */
export class FieldGapError extends Error {
  readonly gap: string;

  constructor(gap: string, detail: string) {
    super(`${gap}: ${detail}`);
    this.name = 'FieldGapError';
    this.gap = gap;
  }
}

export const unwiredMoneyPort: MoneyPort = {
  // No server (a preview, a test with no transport): nothing to ask.
  check: () => Promise.reject(new FieldGapError('N13 (T-33)', 'no server on this build')),
  lastKnown: () => null,
};

/** In-memory money for tests and previews: set what the server would answer, per job. */
export class FakeMoneyPort implements MoneyPort {
  private readonly held = new Map<string, MoneyReading>();
  private readonly server = new Map<string, MoneyReading>();
  online = true;
  checks = 0;
  /** Every job a check was asked for, in order. */
  readonly asked: string[] = [];
  /** FB-028 — every stop the office was told, in order. */
  readonly told: Array<{ workOrderId: string; reason: StopReason; owing?: string | null }> = [];

  tellOffice(workOrderId: string, stop: { reason: StopReason; owing?: string | null }): Promise<void> {
    if (!this.online) return Promise.reject(new Error('no signal'));
    this.told.push({ workOrderId, reason: stop.reason, owing: stop.owing ?? null });
    return Promise.resolve();
  }

  /** What the handset already holds (the figure kept from before). */
  hold(reading: MoneyReading): this {
    this.held.set(reading.workOrderId, reading);
    return this;
  }

  /** What the server will answer to the next check. */
  answer(reading: MoneyReading): this {
    this.server.set(reading.workOrderId, reading);
    return this;
  }

  check(workOrderId: string): Promise<MoneyReading> {
    this.checks += 1;
    this.asked.push(workOrderId);
    const r = this.server.get(workOrderId);
    if (!this.online || !r) return Promise.reject(new Error('no signal'));
    this.held.set(workOrderId, r);
    return Promise.resolve(r);
  }

  lastKnown(workOrderId: string): MoneyReading | null {
    return this.held.get(workOrderId) ?? null;
  }
}

/** Minutes since the figure was read. */
export function ageMinutes(reading: { asAt: string }, now: Date): number {
  return Math.max(0, (now.getTime() - Date.parse(reading.asAt)) / 60000);
}

/** Older than five minutes — warned, never blocked (R17). */
export function isStale(reading: { asAt: string } | null, now: Date): boolean {
  return reading === null || ageMinutes(reading, now) > MONEY_FRESH_MINUTES;
}

/** FB-013 — fresh by a STEP's own bar (its `money_fresh_minutes`), not the
 *  global five: the boundary is inclusive, as the server's `verdict` is. */
export function isFreshFor(reading: { asAt: string } | null, minutes: number, now: Date): boolean {
  return reading !== null && ageMinutes(reading, now) <= minutes;
}

/**
 * FB-013 (decision log judgment 1): CLEARED is the owing figure at four places
 * at or below zero. Read as DIGITS (hard rule 2 — never a float); anything
 * unreadable is NOT cleared, so a paid close is never offered on a figure
 * nobody can parse.
 */
export function isCleared(balance: string | null | undefined): boolean {
  if (typeof balance !== 'string') return false;
  const m = /^(-)?(\d+)(?:\.(\d+))?$/.exec(balance.trim());
  if (!m) return false;
  if (m[1] === '-') return true;
  // Exact, never rounded: any non-zero digit owes (the server's `is_cleared`).
  return !/[1-9]/.test(`${m[2]}${m[3] ?? ''}`);
}

/** How old, in the unit a person would say: seconds, minutes, hours or days. */
export function ageParts(reading: { asAt: string }, now: Date): { unit: 'seconds' | 'minutes' | 'hours' | 'days'; count: number } {
  const seconds = Math.max(0, Math.floor((now.getTime() - Date.parse(reading.asAt)) / 1000));
  if (seconds < 60) return { unit: 'seconds', count: seconds };
  if (seconds < 3600) return { unit: 'minutes', count: Math.floor(seconds / 60) };
  if (seconds < 86400) return { unit: 'hours', count: Math.floor(seconds / 3600) };
  return { unit: 'days', count: Math.floor(seconds / 86400) };
}
