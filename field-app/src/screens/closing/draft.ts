/**
 * The close as it is assembled across FF-32 Debrief → FF-33 Signature →
 * FF-34 Close: what the debrief says, whether the customer signed or
 * refused, and what an earlier screen knew about the money (FF-27's
 * unverified balance, FF-61's unpaid fee). It travels as route params, so
 * each screen hands the whole draft on and nothing is kept in a global.
 *
 * A route param does not survive the app being killed mid-close, so the draft
 * is ALSO kept on the handset (integration lane): `saveDraft` writes it to the
 * encrypted preferences (MMKV in the app) as it is typed on FF-32, keyed by
 * technician and job; FF-32, FF-33 and FF-34 read it back under whatever the
 * params carry (`withSaved`), and the close clears it once it is captured.
 * What is CAPTURED (the signature, the close) is in the outbox as before.
 */
import type { KeyValueStore } from '../../security/prefs';
import { useJobId, useParams } from '../onSite/fieldData';

export interface CloseDraft {
  workOrderId: string;
  debrief?: { problem: string; done: string };
  /** `at` — when it was signed or refused (FB-030: the record keeps the signer's time). */
  signature?: { kind: 'signed'; name: string; at?: string } | { kind: 'refused'; reason: string; at?: string };
  /** FF-27: proceeded on a balance older than five minutes (R17). */
  moneyUnverified?: { balance: string | null; as_at: string | null };
  /** FF-61: reconnected with the reconnect fee unpaid (R111, TC-2). */
  feeOutstanding?: { amount: string | null };
  /** FB-013 (PO 2026-10-28): FF-27 stopped the step on a FRESH cleared
   *  balance. What the phone SAW, sent with the close as `money_seen`; the
   *  server refuses *Not done — payment received* without it. */
  paymentReceived?: PaymentSeen;
}

export interface PaymentSeen {
  task_id: string;
  balance: string;
  currency: string;
  as_at: string;
  checked_at: string;
  latest_payment: { amount: string; at: string } | null;
}

export function draftOf(params: Record<string, unknown>): CloseDraft | null {
  const workOrderId = params.workOrderId;
  if (typeof workOrderId !== 'string' || workOrderId === '') return null;
  const out: CloseDraft = { workOrderId };
  const d = params.debrief as CloseDraft['debrief'] | undefined;
  if (d && typeof d.problem === 'string' && typeof d.done === 'string') out.debrief = d;
  const s = params.signature as CloseDraft['signature'] | undefined;
  if (s && (s.kind === 'signed' || s.kind === 'refused')) out.signature = s;
  const m = params.moneyUnverified as CloseDraft['moneyUnverified'] | undefined;
  if (m && typeof m === 'object') out.moneyUnverified = m;
  const f = params.feeOutstanding as CloseDraft['feeOutstanding'] | undefined;
  if (f && typeof f === 'object') out.feeOutstanding = f;
  const p = params.paymentReceived as CloseDraft['paymentReceived'] | undefined;
  if (p && typeof p === 'object' && typeof p.balance === 'string' && typeof p.as_at === 'string') out.paymentReceived = p;
  return out;
}

/** The draft as params for the next screen. */
export function asParams(d: CloseDraft): Record<string, unknown> {
  return { ...d };
}

const draftKey = (technicianId: string, workOrderId: string) => `closing.draft.${technicianId}.${workOrderId}`;

export function loadDraft(store: KeyValueStore | undefined, technicianId: string, workOrderId: string): CloseDraft | null {
  if (!store) return null;
  try {
    const raw = store.getString(draftKey(technicianId, workOrderId));
    return raw ? draftOf(JSON.parse(raw) as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export function saveDraft(store: KeyValueStore | undefined, technicianId: string, d: CloseDraft): void {
  if (!store) return;
  try {
    store.set(draftKey(technicianId, d.workOrderId), JSON.stringify(d));
  } catch {
    /* a draft that cannot be kept is still in the route params */
  }
}

export function clearDraft(store: KeyValueStore | undefined, technicianId: string, workOrderId: string): void {
  if (!store) return;
  try {
    store.delete(draftKey(technicianId, workOrderId));
  } catch {
    /* nothing to clear */
  }
}

/**
 * The close draft FOR THIS SCREEN'S JOB: the job from `useJobId()` (the route
 * param, else the job the job screens have open — DEF-FLD-10578), the draft
 * the params carry for it, and what the handset kept for it. A screen opened
 * from inside a job with no draft in its params starts one for that job (or
 * loads the one typed earlier); null only when there is no job at all.
 */
export function useCloseDraft(w: { prefs?: KeyValueStore; me: string }): CloseDraft | null {
  const params = useParams();
  const workOrderId = useJobId();
  return withSaved(w.prefs, w.me, workOrderId ? draftOf({ ...params, workOrderId }) : null);
}

/** The params' draft, with what the handset kept filling what the params lost. */
export function withSaved(store: KeyValueStore | undefined, technicianId: string, d: CloseDraft | null): CloseDraft | null {
  if (!d) return null;
  const saved = loadDraft(store, technicianId, d.workOrderId);
  if (!saved) return d;
  return {
    ...saved,
    ...d,
    debrief: d.debrief ?? saved.debrief,
    signature: d.signature ?? saved.signature,
    moneyUnverified: d.moneyUnverified ?? saved.moneyUnverified,
    feeOutstanding: d.feeOutstanding ?? saved.feeOutstanding,
    paymentReceived: d.paymentReceived ?? saved.paymentReceived,
  };
}
