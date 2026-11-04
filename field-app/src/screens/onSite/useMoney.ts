/**
 * The money one JOB shows on a screen: what the handset already holds, how
 * old it is, and *Check now* (R17). Read only (R16).
 *
 * FB-023 (PO 2026-10-31):
 *   F1 — the money is CHECKED LIVE WHEN THE SCREEN OPENS, unless the shell
 *        knows the phone is offline; offline, the last figure (kept on the
 *        handset across a restart) is shown with its age. No balance comes in
 *        the morning download.
 *   It is keyed by the WORK ORDER, because the server's door is per job and a
 *   downloaded job need not know its account (DEF-FLD-10790).
 *
 * `enabled` is whether the technician may see money at all (R26) — a
 * contractor's screen never asks. It is NOT the template's *Balance &
 * payments* tick: that only hides the display, and FB-013's stop still needs
 * the figure (decision log FB-023 item 4), so a screen passes the tick to its
 * card, never here.
 *
 * A failed check is not an error the technician must clear: the figure they
 * had stays on screen with its age, and nothing is blocked.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { TFunction } from 'i18next';

import { useShellStatus } from '../../navigation/ShellStatus';
import type { Wave } from './fieldData';
import { ageParts, isStale, type MoneyReading } from './money';

export interface MoneyState {
  reading: MoneyReading | null;
  stale: boolean;
  checking: boolean;
  /** The last check could not reach the server. */
  failed: boolean;
  check: () => Promise<void>;
}

export function useMoney(w: Wave, workOrderId: string | null, enabled = true): MoneyState {
  const status = useShellStatus();
  const known = useCallback(
    () => (enabled && workOrderId ? w.money.lastKnown(workOrderId, w.me) : null),
    [w, workOrderId, enabled],
  );
  const [reading, setReading] = useState<MoneyReading | null>(known);
  const [checking, setChecking] = useState(false);
  const [failed, setFailed] = useState(false);
  const [, setNow] = useState(0);
  const alive = useRef(true);
  useEffect(
    () => () => {
      alive.current = false;
    },
    [],
  );

  useEffect(() => {
    setReading(known());
  }, [known]);

  const check = useCallback(async () => {
    if (!enabled || !workOrderId) return;
    setChecking(true);
    try {
      const fresh = await w.money.check(workOrderId, w.me);
      if (!alive.current) return;
      setReading(fresh);
      setFailed(false);
    } catch {
      if (alive.current) setFailed(true);
    } finally {
      if (alive.current) {
        setChecking(false);
        setNow((n) => n + 1);
      }
    }
  }, [w, workOrderId, enabled]);

  // F1 — live when the screen opens; offline, the kept figure stands.
  const offline = status.connection === 'offline';
  useEffect(() => {
    if (enabled && workOrderId && !offline) void check();
    // Once per job opened, not on every re-render of the check.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, workOrderId, offline]);

  return { reading, stale: isStale(reading, w.clock.now()), checking, failed, check };
}

/** "Read 40 seconds ago" / "3 days old", in the catalogue's words. */
export function ageText(t: TFunction, reading: { asAt: string }, now: Date, form: 'read' | 'old'): string {
  const { unit, count } = ageParts(reading, now);
  return t(`field.money.age.${form}.${unit}`, { count });
}
