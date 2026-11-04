/**
 * How a job's dispatch state is shown — THE ONE LIST. The Today card (FF-10),
 * the job page's chip (FF-15, and the tablet job pane that mounts it), the map
 * pins and legend (FF-13), the stop (FF-14), the tablet day list and the
 * disconnect board (FF-27) all read the word and the tone from here, and no
 * screen prints a dispatch state any other way.
 *
 * MQ-009 (PO 2026-10-26, *"A Scheduled everywhere"*): the server's `scheduled`
 * reads **Scheduled**, as the web's Work → Orders does — the phone drawing's
 * *DISPATCHED* (FF-10, FF-13's legend) is overruled by that ruling. Until then
 * the card said *Dispatched* and the job page printed the raw server code in
 * the green tone (DEF-FLD-10610), because each had its own display.
 *
 * The server value is normalised ONCE, here (case, spaces, hyphens), so
 * `SCHEDULED`, `scheduled` and `On site` all find their row. Status meaning
 * only — the tone never decorates. A state that is not one of the seven shows
 * as neutral with NO word: a raw code is never printed.
 */
import type { StatusTone } from '../../theme';

export interface StatusLook {
  labelKey: string | null;
  tone: StatusTone;
  /** FF-13's legend: in progress · scheduled · queued (on hold reads as queued work not started). */
  legend: 'inProgress' | 'scheduled' | 'queued';
}

const LOOK: Record<string, StatusLook> = {
  en_route: { labelKey: 'field.job.state.enRoute', tone: 'success', legend: 'inProgress' },
  on_site: { labelKey: 'field.job.state.onSite', tone: 'success', legend: 'inProgress' },
  scheduled: { labelKey: 'field.job.state.scheduled', tone: 'info', legend: 'scheduled' },
  queued: { labelKey: 'field.job.state.queued', tone: 'neutral', legend: 'queued' },
  on_hold: { labelKey: 'field.job.state.onHold', tone: 'warning', legend: 'queued' },
  complete: { labelKey: 'field.job.state.complete', tone: 'success', legend: 'inProgress' },
  cancelled: { labelKey: 'field.job.state.cancelled', tone: 'neutral', legend: 'queued' },
};

const NONE: StatusLook = { labelKey: null, tone: 'neutral', legend: 'queued' };

/** `SCHEDULED` → `scheduled`, ` On site ` → `on_site`, `en-route` → `en_route`. */
export function normaliseDispatchState(state: string | null | undefined): string | null {
  if (!state) return null;
  const key = state.trim().toLowerCase().replace(/[\s-]+/g, '_');
  return key || null;
}

export function statusLook(state: string | null | undefined): StatusLook {
  const key = normaliseDispatchState(state);
  return (key && Object.prototype.hasOwnProperty.call(LOOK, key) ? LOOK[key] : undefined) ?? NONE;
}

/** P1 is the only priority drawn in the danger ink (FF-10, FF-14); every other code is neutral. */
export function priorityTone(code: string | null): StatusTone {
  return code === 'P1' ? 'danger' : code === 'P2' ? 'warning' : 'neutral';
}

export const LEGEND: ReadonlyArray<{ key: StatusLook['legend']; tone: StatusTone; labelKey: string }> = [
  { key: 'inProgress', tone: 'success', labelKey: 'field.map.legend.inProgress' },
  { key: 'scheduled', tone: 'info', labelKey: 'field.map.legend.scheduled' },
  { key: 'queued', tone: 'neutral', labelKey: 'field.map.legend.queued' },
];
