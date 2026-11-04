// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-WRK-10644 (FB-013) — the web phone shell's close never offered
//           *Not done — payment received*.
// Rules:    PO rulings (a)(b)(c) 2026-10-28 (decision log *"FB-013: a cleared
//           balance STOPS the money-check step"*) · R16 (money is READ) · R17
//           (stale is warned, never blocked — unchanged) · R18 (the check sits
//           on the template step; no code knows what a disconnect is) ·
//           CLAUDE.md hard rule 2 (decimal strings, never floats)
// Mirrors:  field-app/src/screens/onSite/DisconnectScreen.tsx (`stopped`,
//           `closePaid`) · field-app/src/screens/onSite/money.ts (`isCleared`,
//           `isFreshFor`) · field-app/src/session/fieldDoors.ts (`moneyFromWire`)
// Server:   apps/work/money.py `paid_close_record` refuses the paid close
//           unless this snapshot proves a fresh, cleared read on a money step.
// Tests:    src/features/work/mobile/ClosePane.dom.test.tsx
// ───────────────────────────────────────────────────────
import type { MobileJobMoney, MobileTaskRow } from "./mobileEndpoints";

/** `work_orders.outcome`'s paid token (`apps/work/connection_models.py`). */
export const PAID_OUTCOME = "not_done_payment_received" as const;

/** What the phone SAW, sent with the close as `field_data.money_seen` — the
 *  phone's `PaymentSeen` (`field-app/src/screens/closing/draft.ts`), field for
 *  field. */
export type PaymentSeen = {
  task_id: string;
  balance: string;
  currency: string;
  as_at: string;
  checked_at: string;
  latest_payment: { amount: string; at: string } | null;
};

/**
 * The step a paid close can stop: the NEXT step not yet done, and only when
 * it declares a payment check (R18 — `money_fresh_minutes` on the step). A
 * step already ticked was done, so nothing was stopped; the phone reads the
 * same `next` (`DisconnectScreen`).
 */
export function paymentCheckStep(tasks: readonly MobileTaskRow[]): MobileTaskRow | null {
  const next = [...tasks].sort((a, b) => a.seq - b.seq).find((row) => !row.ticked_at) ?? null;
  return next !== null && typeof next.money_fresh_minutes === "number" ? next : null;
}

/**
 * CLEARED is the owing figure at four places at or below zero (decision log
 * judgment 1). Read as DIGITS — never a float (hard rule 2); anything
 * unreadable is NOT cleared. The phone's `isCleared` and the server's
 * `is_cleared` read it the same way.
 */
export function isCleared(balance: string | null | undefined): boolean {
  if (typeof balance !== "string") return false;
  const m = /^(-)?(\d+)(?:\.(\d+))?$/.exec(balance.trim());
  if (!m) return false;
  if (m[1] === "-") return true;
  return !/[1-9]/.test(`${m[2]}${m[3] ?? ""}`);
}

/**
 * The snapshot that lets this close offer the paid outcome, or null. Null
 * unless the read is the job's own figure (not withheld), FRESH by the step's
 * own bar at `now` (inclusive, as the server's `verdict` is) and CLEARED.
 */
export function paidSnapshot(step: MobileTaskRow, money: MobileJobMoney, now: Date): PaymentSeen | null {
  const bar = step.money_fresh_minutes;
  if (typeof bar !== "number" || money.withheld) return null;
  const owing = money.owing ?? money.balance;
  if (!owing) return null;
  const asAt = Date.parse(money.as_at);
  if (Number.isNaN(asAt) || (now.getTime() - asAt) / 60_000 > bar) return null;
  if (!isCleared(owing.amount)) return null;
  const paid = money.latest_payment;
  return {
    task_id: step.id,
    balance: owing.amount,
    currency: money.currency ?? owing.currency ?? "",
    as_at: money.as_at,
    checked_at: now.toISOString(),
    latest_payment: paid ? { amount: paid.amount, at: paid.cleared_at ?? paid.posted_at ?? money.as_at } : null,
  };
}
