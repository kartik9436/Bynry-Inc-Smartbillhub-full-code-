/**
 * THE WEEK, END SHIFT AND SUBMIT THE DAY — the handset's half of `CR-193-BRC10`
 * (MQ-040 step 1, decision log 2026-10-26).
 *
 * Read from the server's code (`06-backend/apps/work/shifts_api.py`):
 *
 *   GET  work/mobile/week?from=YYYY-MM-DD        `shifts.week`
 *        → {from, to, today, days:[WireShiftDay], current: WireCurrent|null, ended_at}
 *   POST work/mobile/shift/end      {key, at?, capture_token?}      `shifts.end_shift`
 *        → {date, ended_at, status, duplicate}
 *   POST work/mobile/timesheet/submit {date, key, capture_token?}   `shifts.submit_day`
 *        → {date, jobs, labour_minutes, travel_minutes, lines, submitted_at, duplicate}
 *
 * THE WEEK IS DOWNLOADED WITH THE DAY'S SYNC AND KEPT, so FF-46 opens with no
 * signal (`downloadWeek`, called by `FieldRuntime` after each run). It is kept
 * in the handset's preferences under one key per technician: a small JSON
 * document replaced whole, never a table, because nothing queries inside it.
 *
 * THE TWO ACTS GO THROUGH THE OUTBOX (`doors.ts`, kinds `shift_end` and
 * `timesheet_submit`): captured at the press with a key minted on the handset,
 * sent when there is signal under the captor's own token, and answered
 * `duplicate` on a resend. The screen does not wait for the server: what the
 * handset has CAPTURED is what it shows (`endedLocally`, `submittedLocally`).
 */
import type { KeyValueStore } from '../security/prefs';
import type { DoorExtra } from './fieldApi';

export interface WireShiftDay {
  date: string;
  weekday: string;
  kind: 'shift' | 'off' | 'holiday';
  start: string | null;
  end: string | null;
  holiday: string | null;
  note: string | null;
  exception: 'off' | 'window' | null;
}

export interface WireCurrent {
  start: string;
  end: string;
  started_at: string;
  minutes_so_far: number;
}

export interface WireWeek {
  from: string;
  to: string;
  today: string;
  days: WireShiftDay[];
  current: WireCurrent | null;
  ended_at: string | null;
  /** Stamped by the HANDSET when it kept the answer (`downloadWeek`), never sent by the server. */
  downloaded_at?: string;
}

export interface ShiftsApi {
  myWeek(from?: string): Promise<WireWeek>;
  endShift(body: { at: string }, extra?: DoorExtra): Promise<unknown>;
  submitTimesheet(body: { date: string }, extra?: DoorExtra): Promise<unknown>;
}

export function asShiftsApi(x: unknown): ShiftsApi | null {
  return x && typeof (x as ShiftsApi).myWeek === 'function' && typeof (x as ShiftsApi).submitTimesheet === 'function'
    ? (x as ShiftsApi)
    : null;
}

const WEEK_KEY = (technicianId: string) => `me.week.${technicianId}`;
const ENDED_KEY = (technicianId: string) => `me.shiftEnded.${technicianId}`;
const SUBMITTED_KEY = (technicianId: string) => `me.timesheetSubmitted.${technicianId}`;

function readJson<T>(kv: KeyValueStore, key: string): T | null {
  const raw = kv.getString(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

/** The week as last downloaded, or null — never one made up. */
export function cachedWeek(kv: KeyValueStore, technicianId: string): WireWeek | null {
  const week = readJson<WireWeek>(kv, WEEK_KEY(technicianId));
  return week && Array.isArray(week.days) ? week : null;
}

/** Download this week (the server's own Monday) and keep it. A failure keeps the last one. */
export async function downloadWeek(api: ShiftsApi, kv: KeyValueStore, technicianId: string, now: Date): Promise<WireWeek> {
  const week = { ...(await api.myWeek()), downloaded_at: now.toISOString() };
  kv.set(WEEK_KEY(technicianId), JSON.stringify(week));
  return week;
}

/** `YYYY-MM-DD` of an instant on the handset's own calendar. */
export function localDay(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** End shift was pressed on this handset: `{day, at}` of the last press. */
export function endedLocally(kv: KeyValueStore, technicianId: string): { day: string; at: string } | null {
  return readJson<{ day: string; at: string }>(kv, ENDED_KEY(technicianId));
}

export function markEnded(kv: KeyValueStore, technicianId: string, at: Date): void {
  kv.set(ENDED_KEY(technicianId), JSON.stringify({ day: localDay(at), at: at.toISOString() }));
}

/** The days submitted from this handset, newest last (kept to the last 31). */
export function submittedLocally(kv: KeyValueStore, technicianId: string): string[] {
  const days = readJson<string[]>(kv, SUBMITTED_KEY(technicianId));
  return Array.isArray(days) ? days : [];
}

export function markSubmitted(kv: KeyValueStore, technicianId: string, day: string): void {
  const days = submittedLocally(kv, technicianId).filter((d) => d !== day);
  kv.set(SUBMITTED_KEY(technicianId), JSON.stringify([...days, day].slice(-31)));
}
