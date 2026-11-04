/**
 * R28 / BR-FLD-00028 (PO ruled): *"An emergency must be acknowledged. No
 * acknowledgement in 5 minutes and dispatch is told."*
 *
 * TELLING dispatch is the server's act (`N25`: *"dispatch told after 5 minutes
 * unacknowledged"*) — a phone that is off, flat or in a basement cannot be the
 * thing that raises the alarm about itself. The handset's part is to show the
 * same clock, so the technician sees how long is left: FF-42 *Dispatch told in
 * 4:12* and FF-43 *Dispatch is told in 4:12*.
 */
import { useEffect, useState } from 'react';

import type { AlertItem } from './services';

export const EMERGENCY_ACK_MS = 5 * 60 * 1000;

export function isOpenEmergency(a: AlertItem): boolean {
  return a.kind === 'emergency' && !a.acknowledgedAt;
}

/** The emergency to put in front of the technician: the oldest not yet acknowledged. */
export function firstOpenEmergency(alerts: readonly AlertItem[] | null): AlertItem | null {
  if (!alerts) return null;
  const open = alerts.filter(isOpenEmergency).sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
  return open[0] ?? null;
}

/** Milliseconds until dispatch is told; 0 once it has been. */
export function msUntilDispatchTold(alert: AlertItem, now: Date): number {
  return Math.max(0, Date.parse(alert.at) + EMERGENCY_ACK_MS - now.getTime());
}

/** The time, re-read every second while `running`. */
export function useTicking(now: () => Date, running: boolean): Date {
  const [t, setT] = useState(() => now());
  useEffect(() => {
    if (!running) return;
    setT(now());
    const id = setInterval(() => setT(now()), 1000);
    return () => clearInterval(id);
  }, [now, running]);
  return t;
}
