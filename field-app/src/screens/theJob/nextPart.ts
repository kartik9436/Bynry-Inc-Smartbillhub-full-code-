/**
 * Where FF-15's *Continue* goes: the NEXT UNFINISHED PART of the job
 * (DEF-FLD-10586, beta MQ-024, fix approved by the PO 2026-10-24).
 *
 * In this order, each read from the job's own rows; a part the job does not
 * have (no planned materials, no readings) is skipped:
 *   safety not passed            → FF-16 *Continue — safety first* (R3)
 *   a task not done              → FF-17 *Continue — step n of m*
 *   a planned material short     → FF-23 *Continue — materials*
 *   a reading not taken          → FF-20 *Continue — readings*
 *   everything done              → FF-32 *Finish — debrief*
 *   closed on this phone         → nowhere, *Closed* (disabled)
 *
 * Until this, the button only knew safety and tasks: with every task done it
 * read *"step 8 of 8"* and opened the task list again. The drawing
 * (`FF-15-job.png`) shows only the mid-job state, so it never said otherwise.
 *
 * "Materials done" is `materials.short === 0` — every PLANNED material used
 * at least its planned quantity. A material added in the field plans nothing
 * and so never holds the job up. The checklist is not in the approved order
 * and does not stop the button; FF-15 shows its count beside the others.
 */
import type { ScreenId } from '../../navigation/screens';
import { type JobView, safetyPassed } from './jobModel';

export type NextPart =
  | { part: 'safety'; to: ScreenId }
  | { part: 'tasks'; to: ScreenId; step: number; total: number }
  | { part: 'materials'; to: ScreenId }
  | { part: 'readings'; to: ScreenId }
  | { part: 'debrief'; to: ScreenId }
  | { part: 'closed'; to: null };

export function nextPart(view: JobView | null): NextPart {
  // No job open: the old behaviour — the task list, which says so itself.
  if (view === null) return { part: 'tasks', to: 'FF-17', step: 0, total: 0 };
  if (view.order.closed_at !== null) return { part: 'closed', to: null };
  if (!safetyPassed(view)) return { part: 'safety', to: 'FF-16' };
  const { tasks } = view;
  if (tasks.done < tasks.total) {
    const step = tasks.currentIndex >= 0 ? tasks.currentIndex + 1 : tasks.done + 1;
    return { part: 'tasks', to: 'FF-17', step, total: tasks.total };
  }
  if (view.materials.short > 0) return { part: 'materials', to: 'FF-23' };
  if (view.readings.taken < view.readings.total) return { part: 'readings', to: 'FF-20' };
  return { part: 'debrief', to: 'FF-32' };
}

/**
 * HAS THE JOB BEEN STARTED? — one rule, used by the Today card (FF-10, and the
 * tablet's FF-10 T list, which is the same card) to choose *Start* or
 * *Resume* (DEF-FLD-10607; PO 2026-10-26, *"A Resume — start"*).
 *
 * A job is started when WORK HAS BEEN CAPTURED ON IT on this phone: a safety
 * check ticked, a task done, a reading taken, a material used, or labour
 * clocked. Pressing *Start* alone (the accept, MQ-026) is not work — a job
 * accepted and left before anything was ticked still reads *Start*, and both
 * words open Safety then, so nothing is lost by the choice. The dispatch state
 * is not read: it is the office's word, and it can say *on site* before this
 * phone has touched the job.
 */
export function jobStarted(view: JobView): boolean {
  return (
    view.safety.done > 0 ||
    view.tasks.done > 0 ||
    view.readings.items.some((r) => r.taken) ||
    view.materials.items.some((m) => m.used > 0) ||
    view.labour.segments.length > 0
  );
}

/**
 * The Today card's one button, AGREEING WITH FF-15's *Continue* (both read
 * `nextPart`):
 *   not started           → *Start*  → FF-16 Safety (and accepts the job)
 *   started, part left    → *Resume* → the next unfinished part
 *                                      (safety → FF-17 tasks → FF-23
 *                                      materials → FF-20 readings)
 *   started, all done     → *Finish* → FF-32 Debrief
 *   closed on this phone  → no button
 * With no job loaded (no store), *Start* — what the card always did.
 * The FF-10 drawing shows *Start* on an *In progress* card; the PO chose
 * *Resume* knowing that (decision log 2026-10-26).
 */
export type CardAct =
  | { act: 'start'; to: ScreenId }
  | { act: 'resume'; to: ScreenId }
  | { act: 'finish'; to: ScreenId }
  | { act: 'none'; to: null };

export function cardAct(view: JobView | null): CardAct {
  if (view === null) return { act: 'start', to: 'FF-16' };
  const next = nextPart(view);
  if (next.to === null) return { act: 'none', to: null };
  if (!jobStarted(view)) return { act: 'start', to: 'FF-16' };
  if (next.part === 'debrief') return { act: 'finish', to: next.to };
  return { act: 'resume', to: next.to };
}

/** The button's words for that part. */
export function nextPartLabel(next: NextPart, t: (key: string, values?: Record<string, unknown>) => string): string {
  switch (next.part) {
    case 'safety':
      return t('field.ff15.continueSafety');
    case 'tasks':
      return next.total > 0 ? t('field.ff15.continueStep', { step: next.step, total: next.total }) : t('field.ff15.continue');
    case 'materials':
      return t('field.ff15.continueMaterials');
    case 'readings':
      return t('field.ff15.continueReadings');
    case 'debrief':
      return t('field.ff15.finishDebrief');
    case 'closed':
      return t('field.ff15.closed');
  }
}
