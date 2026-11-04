/**
 * The gaps the "me" screens stop at, each NAMED (CLAUDE.md prime directive:
 * implement up to the boundary and stub the gap with its id in the code).
 *
 * An `N…` id is a row of `04-docs/05-modules/18-field-app/07-endpoints.md`.
 * The `ME-…` ids are server doors that table does NOT list yet — reported to
 * the coordinator to be filed, and spelt here so a grep finds every place one
 * of them is hit. Nothing here is a business answer: each is a door that is
 * missing, and every screen that needs one says "not on this phone yet"
 * rather than inventing a value.
 */
export const GAPS = {
  /** Push kinds, the alert feed and the emergency acknowledgement route (R28). */
  alerts: 'N25',
  /** Outbox kind `time` — labour and travel reach the server (R8, R9). The
   *  handset captures them now as `crew_time`, which waits unrouted. */
  time: 'N17',
  /** Availability reaching dispatch — released by FB-033 (`availabilityPort.ts`,
   *  outbox kind `availability` → `POST work/mobile/availability`); kept for
   *  the not-wired port a screen gets with no store open. */
  availability: 'ME-availability',
  /** Requesting time off — MQ-040 STEP 2, NOT approved. The week and End
   *  shift were released by CR-193-BRC10 (`shiftsPorts.ts`); this id now holds
   *  only the request, and the not-wired port a screen gets with no store. */
  shifts: 'ME-shifts',
  /** Submitting the day — released by CR-193-BRC10 (`shiftsPorts.ts`); kept for
   *  the not-wired port a screen gets with no store open. */
  timesheetSubmit: 'ME-timesheet-submit',
  /** What is on the van (read only — counting is out of scope). Not in 07-endpoints. */
  van: 'ME-van-stock',
  /** The technician's own facts the handset does not hold: utility name, mobile, certifications. Not in 07-endpoints. */
  profile: 'ME-profile',
  /** The dispatch phone number "Call dispatch" dials. Not in 07-endpoints. */
  dispatchPhone: 'ME-dispatch-phone',
  /** Playing an alert's sound on FF-52 — push and its sounds are wired later (T-41). */
  sounds: 'T-41',
  /** The sync engine driven from a screen: "Sync now" (T-10 runs it, nothing in the app mounts it yet). */
  syncEngine: 'T-10',
} as const;

export type GapId = (typeof GAPS)[keyof typeof GAPS];

/** Thrown by a port whose door does not exist yet. The message is the gap id. */
export class GapError extends Error {
  constructor(readonly gap: GapId) {
    super(`not built yet: ${gap}`);
    this.name = 'GapError';
  }
}

export function isGap(err: unknown): err is GapError {
  return err instanceof GapError;
}
