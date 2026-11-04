/**
 * The server's online doors (`sync/fieldApi.ts`) as the PORTS each wave's
 * screens were built against (lane INTEGRATE-2, releasing the holds the
 * Phase 14 proof listed). One adapter per port; no screen learns the wire.
 *
 *   nearby + claim  → `theDay/nearbyApi.ts`  NearbyPort      (FF-11, FF-12)
 *   alerts + ack    → `me/services.tsx`      AlertsPort      (FF-42, FF-43)
 *   money           → `onSite/money.ts`      MoneyPort       (FF-27, FF-26, FF-61…)
 *   reopen          → `closing/ReopenScreen` ReopenPort      (FF-36)
 *   asset search    → `raise/AssetSearchScreen` AssetFinder  (FF-41)
 *
 * The rest — the job bundle, the template catalogue — are DOWNLOADS, made at
 * sync (`sync/extras.ts`), never on a tap (BR-WRK-042).
 */
import type { TenantDb } from '../db/database';
import * as moneyLastQ from '../db/queries/moneyLast';
import { FIX_STALE_MS, type Fix, type LocationDevice } from '../device';
import { type AlertItem, type AlertKind, type AlertsPort } from '../screens/me/services';
import type { AssetFinder, ReopenPort } from '../screens/onSite/fieldData';
import type { MoneyPort, MoneyReading } from '../screens/onSite/money';
import { type ClaimResult, NearbyNoFixError, type NearbyPort } from '../screens/theDay/nearbyApi';
import { refusalOf, type FieldApi, type WireAlert, type WireJobMoney } from '../sync/fieldApi';

const decimal = (x: string | null | undefined): number | null => {
  if (x === null || x === undefined || x === '') return null;
  const n = Number(x);
  return Number.isFinite(n) ? n : null;
};

/**
 * Where Nearby measures from (DEF-FLD-10605): a FRESH fix, asked for on every
 * load and every *Try again* — the way a reading or a photograph asks
 * (`location.current()`). It once read only the fix the handset already HELD,
 * so with no watch running (permission granted after start-up) Nearby never
 * had a point, and *Try again* asked the same empty question. The held fix is
 * the fallback, and only while it is fresh: a stale one is not where the
 * handset is.
 */
export function nearbyFixFrom(location: LocationDevice, nowMs: () => number = () => Date.now()): () => Promise<Fix | null> {
  return async () => {
    const fresh = await location.current().catch(() => null);
    if (fresh) return fresh;
    const held = location.last();
    return held && nowMs() - Date.parse(held.fix_at) <= FIX_STALE_MS ? held : null;
  };
}

/** FF-11 / FF-12. The radius is the screen's; the point is where the handset is now (no fix → `NearbyNoFixError`). */
export function httpNearbyPort(api: FieldApi, where: () => Promise<Fix | null> | Fix | null): NearbyPort {
  return {
    async list({ radiusMi, page }) {
      const fix = await where();
      if (!fix) throw new NearbyNoFixError();
      const answer = await api.nearby({ lat: fix.lat, lng: fix.lng, radiusMi, page });
      return {
        jobs: answer.results.map((c) => ({
          id: c.id,
          number: c.order_no,
          type: c.type,
          priorityCode: c.priority?.code ?? null,
          address: c.premise?.address ?? null,
          // A distance, not money: a 2-place string on the wire, a number to draw.
          distanceMi: decimal(c.distance_mi),
          dueAt: c.due_at,
          estMinutes: c.est_minutes,
          takenBy: c.holder === 'taken' ? (c.taken_by ?? '') : null,
        })),
        count: typeof answer.unassigned === 'number' ? answer.unassigned : answer.count,
        hasMore: answer.next !== null && answer.next !== undefined,
      };
    },
    async claim(jobId): Promise<ClaimResult> {
      try {
        await api.claim(jobId);
        return { ok: true };
      } catch (err) {
        // Somebody took it a moment ago: the server names no one (HR-1).
        if (refusalOf(err)?.messageKey === 'work.claim.already_taken') return { ok: false, takenBy: null };
        throw err;
      }
    },
  };
}

const ALERT_KIND: Record<string, AlertKind> = {
  emergency: 'emergency',
  urgent_assignment: 'urgent',
  schedule_change: 'schedule',
  dispatch_message: 'dispatch',
};

export function alertFromWire(a: WireAlert): AlertItem {
  return {
    id: a.id,
    kind: ALERT_KIND[a.kind] ?? 'dispatch',
    at: a.sent_at,
    title: a.message ?? a.order_no ?? '',
    detail: a.premise?.address ?? null,
    note: null,
    read: a.acknowledged_at !== null || !a.ack_required,
    workOrderNumber: a.order_no,
    acknowledgedAt: a.acknowledged_at,
    address: a.premise?.address ?? null,
  };
}

/** FF-42 / FF-43. `markAllRead` has no door: it stays the port's refusal. */
export function httpAlertsPort(api: FieldApi, base: AlertsPort): AlertsPort {
  return {
    async list() {
      const out: AlertItem[] = [];
      // Every page (NFR-3: paged on the wire, no cap on the handset's list).
      for (let page = 1; ; page += 1) {
        const answer = await api.alerts(page);
        out.push(...answer.results.map(alertFromWire));
        if (answer.next === null || answer.next === undefined || answer.results.length === 0) return out;
      }
    },
    async acknowledge(_technicianId, alertId) {
      await api.acknowledgeAlert(alertId);
    },
    markAllRead: base.markAllRead,
  };
}

/** The server's answer as the screens' reading (R16: read only; amounts are strings). */
export function moneyFromWire(workOrderId: string, w: WireJobMoney): MoneyReading | null {
  if (w.withheld || !w.balance) return null;
  const owing = w.owing ?? w.balance;
  const paid = w.latest_payment;
  const fee = w.charges.find((c) => c.charged);
  // FB-023 F2 (DEF-FLD-10792): a payment is CLEARED only when the server says
  // so; anything else that stands is POSTED, dated when it was posted.
  const cleared = paid?.state === 'cleared';
  const d = w.disconnect ?? null;
  const plan = d?.plan?.status === 'on_track' || d?.plan?.status === 'behind' ? d.plan.status : null;
  return {
    workOrderId,
    currency: w.currency ?? owing.currency ?? '',
    balance: owing.amount,
    asAt: w.as_at,
    latestPayment: paid
      ? {
          amount: paid.amount,
          at: (cleared ? (paid.cleared_at ?? paid.posted_at) : paid.posted_at) ?? w.as_at,
          state: cleared ? 'cleared' : 'posted',
          method: paid.method ?? null,
        }
      : null,
    reconnectFee: fee?.charged
      ? { amount: fee.charged.amount, chargedAt: fee.charged_on ?? w.as_at, paid: fee.paid === true, paidAt: null }
      : null,
    disconnect: d
      ? {
          plan,
          notice: d.notice ? { tier: d.notice.tier, issuedOn: d.notice.issued_on, amount: d.notice.amount?.amount ?? null } : null,
        }
      : null,
    // FB-028 — the facts a raised job's steps gate on.
    gate: w.field_gate
      ? {
          noticeEndsOn: w.field_gate.notice?.ends_on ?? null,
          noticeOpen: w.field_gate.notice_open === true,
          protected: w.field_gate.protected === true,
        }
      : null,
  };
}

/** Where the port keeps the last figure of each job (FB-023 F1); absent = memory only. */
export interface MoneyMemory {
  read(workOrderId: string, technicianId: string): MoneyReading | null;
  write(workOrderId: string, technicianId: string, reading: MoneyReading): void;
}

/** The handset's store as the money memory (`db/queries/moneyLast.ts`). */
export function storeMoneyMemory(db: TenantDb, now: () => Date = () => new Date()): MoneyMemory {
  return {
    read: (wo, tech) => moneyLastQ.get<MoneyReading>(db, tech, wo),
    write: (wo, tech, reading) => moneyLastQ.put(db, tech, wo, reading, now().toISOString()),
  };
}

/** FF-25/26/27/61's money, through the JOB's door (`GET jobs/{id}/money`). */
export function httpMoneyPort(api: FieldApi, memory?: MoneyMemory | null): MoneyPort {
  const held = new Map<string, MoneyReading>();
  const key = (wo: string, tech?: string) => `${tech ?? ''}|${wo}`;
  return {
    async check(workOrderId, technicianId) {
      const answer = await api.jobMoney(workOrderId);
      const reading = moneyFromWire(workOrderId, answer);
      if (!reading) throw new Error(answer.withheld ? `withheld: ${answer.withheld}` : 'no figure');
      held.set(key(workOrderId, technicianId), reading);
      if (memory && technicianId) memory.write(workOrderId, technicianId, reading);
      return reading;
    },
    lastKnown(workOrderId, technicianId) {
      const inMemory = held.get(key(workOrderId, technicianId));
      if (inMemory) return inMemory;
      return memory && technicianId ? memory.read(workOrderId, technicianId) : null;
    },
    async tellOffice(workOrderId, stop) {
      if (!api.stepStopped) return;
      await api.stepStopped(workOrderId, {
        reason: stop.reason,
        owing: stop.owing ?? null,
        limit: stop.limit ?? null,
        money_as_at: stop.moneyAsAt ?? null,
        ends_on: stop.endsOn ?? null,
      });
    },
  };
}

/** FF-36's reasons in the board's words → the server's (`field_reopen.TECHNICIAN_REASONS`). */
export const REOPEN_REASON_WIRE: Record<string, string> = {
  wrongOutcome: 'wrong_outcome',
  missedStep: 'missed_step',
  evidenceMissing: 'missing_evidence',
};

export function httpReopenPort(api: FieldApi): ReopenPort {
  return {
    async reopen(workOrderId, reason, key) {
      await api.reopen(workOrderId, { reason: REOPEN_REASON_WIRE[reason] ?? reason, key });
    },
  };
}

export function httpAssetFinder(api: FieldApi): AssetFinder {
  return {
    async search(q, page) {
      const answer = await api.searchAssets(q, page);
      return { hits: answer.results, count: answer.count, hasMore: answer.next !== null && answer.next !== undefined };
    },
  };
}
