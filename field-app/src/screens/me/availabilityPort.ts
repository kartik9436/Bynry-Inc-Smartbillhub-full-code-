/**
 * FF-45 *Available · On break · Off duty* — WIRED (FB-033, decision log
 * 2026-10-31; DEF-FLD-10799). Replaces the `ME-availability` hold.
 *
 * The tap is CAPTURED through the outbox at the press — its key minted here,
 * its moment the tap's own — and goes when there is signal
 * (`sync/doors.ts`, kind `availability` → `POST work/mobile/availability`).
 * The screen does not wait for the server: the chip already shows the choice
 * (`availability.tsx`), and the office's answer is read back after the next
 * sync (`sync/availability.ts`).
 */
import type { TenantDb } from '../../db/database';
import { capture } from '../../sync/outbox';
import { WIRE_OF } from '../../sync/availability';
import type { Choosable } from './availability';
import type { AvailabilityPort, Captor } from './services';

export interface AvailabilityDeps {
  db: TenantDb;
  newId(): string;
  now(): Date;
  /** Send now, quietly, when there may be signal; a failure leaves the item queued. */
  sendNow?: () => Promise<void>;
}

export function createAvailabilityPort(deps: AvailabilityDeps): AvailabilityPort {
  return {
    async send(captor: Captor, value: Choosable, at: Date) {
      capture(
        deps.db,
        captor,
        { kind: 'availability', payload: { at: at.toISOString(), value: WIRE_OF[value] } },
        { newId: deps.newId, clock: { now: deps.now } },
      );
      void deps.sendNow?.().catch(() => undefined);
    },
  };
}
