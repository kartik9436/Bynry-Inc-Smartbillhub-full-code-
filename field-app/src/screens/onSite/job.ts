/**
 * One job, as the on-site, closing and raise screens read it: the order and
 * what hangs off it — the premise (the one place an address lives, hard rule
 * 8), the customer, the asset — all from the handset, all through the query
 * layer.
 */
import { fromJson } from '../../db/json';
import * as assetQ from '../../db/queries/asset';
import * as customerQ from '../../db/queries/customer';
import * as premiseQ from '../../db/queries/premise';
import * as technicianQ from '../../db/queries/technician';
import * as workOrderQ from '../../db/queries/workOrder';
import type { Wave } from './fieldData';

export interface JobView {
  order: workOrderQ.WorkOrderRow;
  premise: premiseQ.PremiseRow | null;
  customer: customerQ.CustomerRow | null;
  asset: assetQ.AssetRow | null;
  /** The server's fields the mirror has no column for, kept whole (R116). */
  extra: Record<string, unknown>;
}

export function loadJob(w: Wave, workOrderId: string | null): JobView | null {
  if (!workOrderId) return null;
  const order = workOrderQ.getMine(w.s, workOrderId);
  if (!order) return null;
  return {
    order,
    premise: order.premise_id ? (premiseQ.get(w.db, order.premise_id) ?? null) : null,
    customer: order.customer_id ? (customerQ.get(w.db, order.customer_id) ?? null) : null,
    asset: order.asset_id ? (assetQ.get(w.db, order.asset_id) ?? null) : null,
    extra: fromJson<Record<string, unknown>>(order.extra) ?? {},
  };
}

/**
 * R26: contractors see the customer's name, not their money. FB-023 F3 (PO
 * 2026-10-31): a technician is a contractor only on a CONTRACTOR crew, by the
 * server's own test (`money.employment_of`), which the change feed states and
 * `sync/delta.ts` keeps on this technician's roster row (DEF-FLD-10789 — before
 * it, nothing in production wrote the row and every phone hid every balance).
 *
 * `unknown` — never synced, or an older server: the money stays hidden AND the
 * screen does not say *Contractor*, because that would be untrue.
 */
export type MoneyRole = 'employee' | 'contractor' | 'unknown';

export function moneyRole(w: Pick<Wave, 'db' | 'me'>): MoneyRole {
  const e = technicianQ.get(w.db, w.me)?.employment;
  return e === 'employee' || e === 'contractor' ? e : 'unknown';
}

/** The roster's employment in words: the server's two codes are translated,
 *  anything else (a roster word typed elsewhere) is shown as it is. */
export function employmentWord(t: (key: string) => string, raw: string): string {
  if (raw === 'employee') return t('field.employment.employee');
  if (raw === 'contractor') return t('field.employment.contractor');
  return raw;
}

export function seesMoney(w: Pick<Wave, 'db' | 'me'>): boolean {
  return moneyRole(w) === 'employee';
}

/** FB-023 F4/F6 — the job's own copy of its template's display ticks. */
export function showsOf(job: JobView | null): workOrderQ.JobShows {
  return workOrderQ.showsOf(job?.order ?? null);
}

/**
 * The signed-in technician's display name, for "Captured by …" and the
 * activity's author: the roster's name, else the signed-in profile's — and
 * EMPTY when neither is known, never the id (B14 rule 31; DEF-FLD-10628: the
 * stamp read *"Captured by 01a0ecfb-ba9c-…"* on a phone whose roster had no
 * row for its own technician). A screen shows the time alone then.
 */
export function myName(w: Pick<Wave, 'db' | 'me' | 'meName'>): string {
  const roster = technicianQ.get(w.db, w.me)?.name?.trim();
  if (roster) return roster;
  return w.meName?.trim() ?? '';
}

/**
 * The crew's lead (R8: the lead closes). ⚠ The job card does not say who
 * leads a crew job yet (`07-endpoints.md` N17); until it does, the order's
 * `extra.lead_technician_id` is read when the server sends it, and the
 * technician whose job it is leads otherwise.
 */
export function leadOf(job: JobView): string {
  const lead = job.extra.lead_technician_id;
  return typeof lead === 'string' && lead !== '' ? lead : job.order.technician_id;
}

/**
 * Has the office accepted this close? ⚠ The job card does not carry it yet
 * (the server holds `accepted_by_id`; `07-endpoints.md` N21). Read from
 * `extra.accepted_at` when the server sends it; absent, the close is treated
 * as NOT accepted, and the server — which refuses a reopen after acceptance
 * (R22) — stays the authority.
 */
export function acceptedAt(job: { extra: Record<string, unknown> }): string | null {
  const v = job.extra.accepted_at;
  return typeof v === 'string' && v !== '' ? v : null;
}
