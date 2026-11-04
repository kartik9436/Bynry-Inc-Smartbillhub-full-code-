/**
 * What the "me" screens (FF-42…FF-55, the Switch sheet) read and write, as
 * PORTS — one per thing the handset either holds or has to ask the server
 * for — and the React context that hands them to a screen.
 *
 * Two halves, and the difference is the point:
 *
 *  - `data` — what the HANDSET holds (the outbox, photos, `crew_time`, the
 *    work-order mirror): read through `db/queries` and `scoped()`, written
 *    through the outbox. `createDbMeData()` (`dbData.ts`) is the real one.
 *  - everything else — doors on the SERVER. The week, End shift and Submit
 *    the day are wired when a store is open (`shiftsPorts.ts`, CR-193-BRC10),
 *    and so is telling dispatch your availability (`availabilityPort.ts`, FB-033);
 *    the rest do not exist yet. Each not-wired port's
 *    default is NOT WIRED: a read answers `null` ("not known") and a write
 *    rejects with a `GapError` naming the missing door (`gaps.ts`). A screen
 *    shows "not on this phone yet" for `null`; it never shows an invented
 *    zero, an invented name or an invented shift.
 *
 * The app mounts `MeServicesProvider` with whatever is wired today (App.tsx);
 * a screen mounted with no provider at all gets the not-wired set, so every
 * screen renders — the doors test mounts them exactly that way.
 */
import { createContext, type ReactNode, useContext, useMemo } from 'react';

import type { Availability } from '../../navigation/ShellStatus';
import type { SyncReason, SyncRunOutcome } from '../../sync/syncReason';
import { MemoryKeyValueStore, type KeyValueStore } from '../../security/prefs';
import type { CrashCapture } from '../../telemetry/crashReporter';
import { GapError, GAPS } from './gaps';
import type { RefusalAction } from './refusalGroups';

// ── What the handset holds ──────────────────────────────────────────────────

export interface TodaySummary {
  done: number;
  left: number;
  workedMinutes: number;
}

export type AdminTask = 'vehicleCheck' | 'training' | 'depot' | 'crewMeeting' | 'other';
export const ADMIN_TASKS: readonly AdminTask[] = ['vehicleCheck', 'training', 'depot', 'crewMeeting', 'other'];

export interface TimeEntry {
  id: string;
  kind: 'travel' | 'labour' | 'admin';
  startedAt: string;
  /** null — the clock is running. */
  endedAt: string | null;
  workOrderId: string | null;
  /** The order's number and type, when the mirror has it ("WO-4822", "Meter exchange"). */
  workOrderNumber: string | null;
  workOrderType: string | null;
  /** For an admin entry, which task it was. */
  adminTask: AdminTask | null;
}

export interface RefusedItem {
  id: string;
  kind: string;
  /** The job it belongs to — FF-50 groups by job and reason (DEF-FLD-10612). */
  workOrderId?: string | null;
  workOrderNumber: string | null;
  capturedAt: string;
  /** The server's own reason, as it gave it. */
  reason: string;
  /**
   * The handset's words for it, when the server named a catalogue key the
   * handset carries (`work.mobile.reads.<reason>` → `field.reads.refused.<reason>`).
   */
  reasonKey?: string | null;
  /** What the technician can do about it (`refusalGroups.ts`); absent reads as *Fix and send again*. */
  action?: RefusalAction;
  /** The server kept a copy for the office (`kept_for_office`, CR-194-BRC10). */
  keptForOffice?: boolean;
}

/**
 * FF-50 *Needs attention* (FB-022, DEF-FLD-10794): an item the server has
 * failed `NEEDS_ATTENTION_AFTER` times or more and that is STILL PENDING —
 * still retried in the background, never discarded (`backoff.ts`).
 */
export interface StuckItem {
  id: string;
  kind: string;
  workOrderNumber: string | null;
  capturedAt: string;
  /** How many times it has failed. */
  failures: number;
  /** Why, from its saved failure; null when it names nothing. */
  reason: SyncReason | null;
  /** The server's trace, short (`7F3A-9C21`), for the reporter to quote; null — none. */
  reference: string | null;
}

/** FF-50 *Raised*: an order raised in the field, and its number once the office has it (DEF-FLD-10603). */
export interface RaisedItem {
  id: string;
  /** Still on the phone, or with the server (settled), or refused (shown under *needs you*). */
  sent: boolean;
  refused: boolean;
  capturedAt: string;
  templateName: string | null;
  /** The server's `WO-` number — never one the phone made up (R24). */
  orderNo: string | null;
}

export interface SyncCounts {
  /** Data items not yet with the server (R65: items, not bytes). */
  itemsWaiting: number;
  photosWaiting: number;
  photosTotal: number;
  photosUploaded: number;
  photoBytesLeft: number;
  jobsTotal: number;
  jobsReady: number;
  /** When the handset last heard from the server; null — never. */
  lastReachedAt: string | null;
  /** Photographs waiting for their reading's / job's declaration to be answered (DEF-FLD-10629, I). */
  photosAwaitingRoute?: number;
  photosAwaitingJob?: number;
  /** The reader's open routes and their meters (DEF-FLD-10629, J). */
  routesTotal?: number;
  routeMeters?: number;
  /** Why the waiting items have not gone, from their saved failure (DEF-FLD-10624); null — nothing to say. */
  waitingReason?: SyncReason | null;
}

/** The handset's own record of a technician (the roster, `technician` table). */
export interface WhoFacts {
  role: string | null;
  employment: string | null;
}

/** Enough of a job to draw its card (FF-54 / FF-55 preview). */
export interface JobCard {
  id: string;
  number: string | null;
  type: string | null;
  state: string | null;
  priority: string | null;
  windowStart: string | null;
  windowEnd: string | null;
  address: string | null;
  locality: string | null;
}

export interface Captor {
  technicianId: string;
  capturedBy: string;
}

export interface MeData {
  /** False when no handset store is open: every read below answers null. */
  readonly wired: boolean;
  who(technicianId: string): WhoFacts | null;
  /** The first open job of the day, as Today orders it. */
  firstOpenJob(technicianId: string, now: Date): JobCard | null;
  today(technicianId: string, now: Date): TodaySummary | null;
  timesheet(technicianId: string, from: Date, to: Date): TimeEntry[] | null;
  runningClock(technicianId: string): TimeEntry | null;
  /** FF-48: start an admin clock (stopping whatever is running). Captured through the outbox. */
  startAdmin(captor: Captor, task: AdminTask, now: Date): void;
  /** FF-48: stop the running clock. */
  stopClock(captor: Captor, now: Date): void;
  /** FF-47 (R9): correct an entry's times. Captured through the outbox. */
  correct(captor: Captor, entryId: string, startedAt: string, endedAt: string | null, now: Date): void;
  syncCounts(technicianId: string): SyncCounts | null;
  refused(technicianId: string): RefusedItem[] | null;
  /** FF-50: the technician acts on a refusal — the same key goes again. */
  resend(technicianId: string, id: string): boolean;
  /** FF-50 *Needs attention*: pending items failed five times or more (absent where no store backs this port). */
  needsAttention?(technicianId: string): StuckItem[] | null;
  /** *Send again* on one: its wait is cleared so the next run sends it. Nothing is reset or discarded. */
  retryNow?(technicianId: string, id: string): boolean;
  /** FF-50 *Raised*, newest first, at most `limit` (absent where no store backs this port). */
  raised?(technicianId: string, limit: number): RaisedItem[] | null;
}

// ── Doors on the server ─────────────────────────────────────────────────────

export type AlertKind = 'emergency' | 'urgent' | 'jobCancelled' | 'paymentCleared' | 'schedule' | 'dispatch';

export interface AlertItem {
  id: string;
  kind: AlertKind;
  /** When it reached the handset (the emergency's five minutes run from here). */
  at: string;
  title: string;
  detail: string | null;
  /** A third, quieter line ("$241.38 cleared 18 Oct · 22 Cedar Court"; the author of a dispatch message). */
  note: string | null;
  read: boolean;
  workOrderNumber: string | null;
  // An emergency's own facts (FF-43).
  acknowledgedAt?: string | null;
  priority?: string | null;
  address?: string | null;
  locality?: string | null;
  reportedAt?: string | null;
  reportedBy?: string | null;
  distanceMiles?: number | null;
  driveMinutes?: number | null;
  said?: string | null;
}

export interface AlertsPort {
  list(technicianId: string): Promise<AlertItem[] | null>;
  /** R28: an emergency must be acknowledged. */
  acknowledge(technicianId: string, alertId: string, at: Date): Promise<void>;
  markAllRead(technicianId: string): Promise<void>;
}

export interface AvailabilityPort {
  /** Tell dispatch (FB-033): captured through the outbox as the captor, with
   *  the tap's time (`availabilityPort.ts`). The choice is kept on the
   *  handset either way. Only the three the technician may choose. */
  send(captor: Captor, value: Exclude<Availability, 'unavailable'>, at: Date): Promise<void>;
}

export interface ShiftDay {
  date: string;
  /** `off` — not a working day, or a day the office set off (CR-193-BRC10). */
  kind: 'shift' | 'timeOff' | 'holiday' | 'off';
  start: string | null;
  end: string | null;
  /** "Day shift", "Early", a holiday's name. */
  name: string | null;
  /** "Route 3", "Approved 02 Oct", "depot closed". */
  note: string | null;
}

export interface ShiftWeek {
  current: { start: string; end: string; startedAt: string } | null;
  days: ShiftDay[];
}

export interface ShiftsPort {
  week(technicianId: string, weekOf: Date): Promise<ShiftWeek | null>;
  /** Step 2 of MQ-040 — NOT approved; stays not wired. */
  requestTimeOff(technicianId: string): Promise<void>;
  /** Captured through the outbox as the captor (`shiftsPorts.ts`). */
  endShift(captor: Captor, at: Date): Promise<void>;
}

export interface VanItem {
  sku: string;
  name: string;
  onHand: number;
  /** Needed today for the assigned work; null — not known. */
  neededToday: number | null;
  /** A unit price as the server sends it — a decimal STRING and its currency, never a float (R16, hard rule 2). */
  unitPrice: { amount: string; currency: string } | null;
}

export interface VanStock {
  van: string;
  countedAt: string | null;
  items: VanItem[];
}

export interface VanPort {
  stock(technicianId: string): Promise<VanStock | null>;
  askDepot(technicianId: string, sku: string): Promise<void>;
}

export interface ProfileFacts {
  role: string | null;
  utility: string | null;
  employment: string | null;
  mobile: string | null;
  certificationsCurrent: number | null;
}

export interface ProfilePort {
  facts(technicianId: string): Promise<ProfileFacts | null>;
}

export interface TimesheetPort {
  /** Captured through the outbox as the captor (`shiftsPorts.ts`). */
  submitDay(captor: Captor, day: Date): Promise<void>;
  /** This day was submitted from this handset — the day then reads Submitted and is read-only. */
  submitted?(technicianId: string, day: Date): boolean;
}

export interface SyncActionsPort {
  /** `manual` — the technician pressed *Sync now*: backoff is cleared first (DEF-FLD-10624, C). */
  syncNow(opts?: { manual?: boolean }): Promise<SyncRunOutcome | void>;
}

export interface SoundsPort {
  play(kind: 'emergency' | 'newJob'): Promise<void>;
}

export interface DispatchPort {
  call(): Promise<void>;
}

export interface MeServices {
  data: MeData;
  alerts: AlertsPort;
  availability: AvailabilityPort;
  shifts: ShiftsPort;
  van: VanPort;
  profile: ProfilePort;
  timesheet: TimesheetPort;
  sync: SyncActionsPort;
  sounds: SoundsPort;
  dispatch: DispatchPort;
  /** Handset preferences (MMKV in the app). */
  prefs: KeyValueStore;
  /** Present → each screen is wrapped in a TelemetryErrorBoundary. */
  crash?: CrashCapture;
  now: () => Date;
}

// ── Not wired ───────────────────────────────────────────────────────────────

const gap = (id: (typeof GAPS)[keyof typeof GAPS]) => () => Promise.reject(new GapError(id));
const unknown = () => Promise.resolve(null);
const noStore = () => {
  throw new GapError(GAPS.time);
};

export const NO_DATA: MeData = {
  wired: false,
  who: () => null,
  firstOpenJob: () => null,
  today: () => null,
  timesheet: () => null,
  runningClock: () => null,
  startAdmin: noStore,
  stopClock: noStore,
  correct: noStore,
  syncCounts: () => null,
  refused: () => null,
  resend: () => false,
};

export function notWiredServices(overrides: Partial<MeServices> = {}): MeServices {
  return {
    data: NO_DATA,
    alerts: { list: unknown, acknowledge: gap(GAPS.alerts), markAllRead: gap(GAPS.alerts) },
    availability: { send: gap(GAPS.availability) },
    shifts: { week: unknown, requestTimeOff: gap(GAPS.shifts), endShift: gap(GAPS.shifts) },
    van: { stock: unknown, askDepot: gap(GAPS.van) },
    profile: { facts: unknown },
    timesheet: { submitDay: gap(GAPS.timesheetSubmit) },
    sync: { syncNow: gap(GAPS.syncEngine) },
    sounds: { play: gap(GAPS.sounds) },
    dispatch: { call: gap(GAPS.dispatchPhone) },
    prefs: new MemoryKeyValueStore(),
    now: () => new Date(),
    ...overrides,
  };
}

const MeServicesContext = createContext<MeServices | null>(null);

/** One not-wired set for every screen mounted with no provider (previews, the doors test). */
let fallback: MeServices | null = null;

export function MeServicesProvider({ services, children }: { services: MeServices; children: ReactNode }) {
  const value = useMemo(() => services, [services]);
  return <MeServicesContext.Provider value={value}>{children}</MeServicesContext.Provider>;
}

export function useMeServices(): MeServices {
  const ctx = useContext(MeServicesContext);
  if (ctx) return ctx;
  fallback ??= notWiredServices();
  return fallback;
}
