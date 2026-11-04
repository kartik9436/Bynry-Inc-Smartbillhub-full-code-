/**
 * Labour is per person, not per job (R8): two technicians on one order are
 * two time records and the cost is their sum. Travel and labour are separate
 * clocks (R9). This folds a job's `crew_time` rows into one line per person —
 * what FF-29 Crew draws and FF-32 Debrief reads its own line from.
 */
import type { CrewTimeRow } from '../../db/queries/crewTime';
import { minutesBetween } from './format';

export interface CrewLine {
  personId: string;
  travelMinutes: number;
  labourMinutes: number;
  /** When they reached the site: travel's end, or the first labour start. */
  arrivedAt: string | null;
  /** First labour start and last labour end (FF-32's 08:46 – 09:58). */
  labourFrom: string | null;
  labourTo: string | null;
  /** A clock still running. */
  open: boolean;
}

export function crewLines(rows: readonly CrewTimeRow[], now: Date): CrewLine[] {
  const by = new Map<string, CrewLine>();
  for (const r of rows) {
    const line = by.get(r.person_id) ?? {
      personId: r.person_id,
      travelMinutes: 0,
      labourMinutes: 0,
      arrivedAt: null,
      labourFrom: null,
      labourTo: null,
      open: false,
    };
    const end = r.ended_at ?? now.toISOString();
    const minutes = minutesBetween(r.started_at, end);
    if (r.ended_at === null) line.open = true;
    if (r.kind === 'travel') {
      line.travelMinutes += minutes;
      if (r.ended_at && (!line.arrivedAt || r.ended_at > line.arrivedAt)) line.arrivedAt = r.ended_at;
    } else if (r.kind === 'labour') {
      line.labourMinutes += minutes;
      if (!line.labourFrom || r.started_at < line.labourFrom) line.labourFrom = r.started_at;
      if (!line.labourTo || end > line.labourTo) line.labourTo = end;
    }
    by.set(r.person_id, line);
  }
  for (const line of by.values()) {
    if (!line.arrivedAt) line.arrivedAt = line.labourFrom;
  }
  return [...by.values()];
}

/** The cost is the sum (R8). */
export function totalLabour(lines: readonly CrewLine[]): number {
  return lines.reduce((sum, l) => sum + l.labourMinutes, 0);
}
