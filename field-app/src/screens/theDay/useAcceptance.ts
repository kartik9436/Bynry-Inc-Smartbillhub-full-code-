/**
 * The screens' handle on taking a job or turning it down (DEF-FLD-10579) —
 * `acceptance.ts` holds the rules; this binds them to the job port the app
 * mounts (who is capturing, the clock, the id source). With no port (a screen
 * mounted without a store) every job reads *pending* and Start only opens the
 * next screen, as before.
 */
import { useCallback, useMemo } from 'react';

import { scoped } from '../../db/scoped';
import { useJobPort } from '../theJob/JobPort';
import { acceptanceOf, acceptOnStart, declineJob, type Acceptance, type DeclineReason } from './acceptance';

export interface JobAcceptance {
  /** False with no job port: nothing can be captured, so no Decline is offered. */
  available: boolean;
  /** Whether a job is taken, declined, or neither yet (re-read on every render). */
  of(workOrderId: string): Acceptance;
  /** *Start*, *Open the job*, *Continue*: accept it first if it is not accepted yet. */
  start(workOrderId: string): void;
  /** *Decline*, with its reason. False when refused (no reason, or already started). */
  decline(workOrderId: string, answer: { reason: DeclineReason | null; note: string }): boolean;
}

export function useAcceptance(): JobAcceptance {
  const port = useJobPort();
  const s = useMemo(() => (port ? scoped(port.db, port.captor().technicianId) : null), [port]);
  const of = useCallback((id: string): Acceptance => (s ? acceptanceOf(s, id) : 'pending'), [s]);
  const start = useCallback(
    (id: string) => {
      if (!port || !s) return;
      if (acceptOnStart(port.db, s, port.captor(), id, { newId: port.newId, clock: port.clock })) port.changed();
    },
    [port, s],
  );
  const decline = useCallback(
    (id: string, answer: { reason: DeclineReason | null; note: string }) => {
      if (!port || !s) return false;
      const done = declineJob(port.db, s, port.captor(), id, answer, { newId: port.newId, clock: port.clock });
      if (done) port.changed();
      return done;
    },
    [port, s],
  );
  return { available: port !== null, of, start, decline };
}
