/**
 * Every act on the job screens, captured through the outbox (`sync/outbox.ts`)
 * so the act, its local change, its photo rows and its idempotency key land in
 * ONE transaction (Mobile data §1) — or not at all.
 *
 * Kinds: the server's own (`safety_tick`, `task_tick`, `reading`,
 * `material`, `photo`) go to `/work-orders/{id}/sync`; the ones with no server
 * door yet (`crew_time`, `hand_back`, `document`) are captured on the
 * `unrouted` channel and KEPT, never dropped (decision log 2026-10-21, Phase 1
 * database and sync). A field addition — a step, a material, a reading — is
 * never silent (R7): it carries its reason and `added_in_field` in its payload.
 *
 * ⚠ TWO ACTS HAVE NO OUTBOX KIND, AND ARE NAMED RATHER THAN SQUEEZED INTO ONE:
 *  - a CHECKLIST ANSWER — the server has no item kind for it and `UNROUTED_KINDS`
 *    has no `checklist_answer`; answers are saved on the handset (`wo_item.state`)
 *    and wait for that kind (`saveChecklistAnswer`).
 *  - an ADDED STEP — `task_tick` ticks a server task; there is no item that
 *    CREATES one. The step is held locally with its reason and sent as a
 *    `remark` (unrouted) carrying `added_in_field`, so the office's variance
 *    has its words even before the server learns the kind.
 */
import * as activityQ from '../../db/queries/activity';
import * as crewTimeQ from '../../db/queries/crewTime';
import * as documentQ from '../../db/queries/document';
import * as jobQ from '../../db/queries/jobScreens';
import * as photoQ from '../../db/queries/photo';
import * as woItemQ from '../../db/queries/woItem';
import * as woReadingQ from '../../db/queries/woReading';
import { scoped, type ScopedRunner } from '../../db/scoped';
import { capture, type PhotoCapture } from '../../sync/outbox';
import type { ReadyPhoto } from './camera';
import type { JobPortValue } from './JobPort';
import type { MaterialDetail, TaskDetail } from './jobModel';

const deps = (port: JobPortValue) => ({ newId: port.newId, clock: port.clock });

function nowIso(port: JobPortValue): string {
  return port.clock.now().toISOString();
}

function photoCaptures(photos: readonly ReadyPhoto[], target: PhotoCapture['target']): PhotoCapture[] {
  return photos.map((p) => ({
    localPath: p.localPath,
    sha256: p.sha256,
    bytes: p.bytes,
    width: p.width,
    height: p.height,
    target,
  }));
}

/** FF-16: one safety row ticked. All-or-none is the SCREEN's lock and the server re-derives it (R3). */
export function tickSafety(port: JobPortValue, workOrderId: string, safetyId: string): string {
  return capture(
    port.db,
    port.captor(),
    {
      kind: 'safety_tick',
      workOrderId,
      payload: { safety_id: safetyId },
      location: port.location(),
      apply: (s) => woItemQ.setState(s, safetyId, 'ticked'),
    },
    deps(port),
  ).key;
}

/** FF-17 *Mark done*. Short of the photo count warns and never blocks (R110). */
export function tickTask(port: JobPortValue, workOrderId: string, taskId: string): string {
  return capture(
    port.db,
    port.captor(),
    {
      kind: 'task_tick',
      workOrderId,
      payload: { task_id: taskId },
      location: port.location(),
      apply: (s) => woItemQ.setState(s, taskId, 'done'),
    },
    deps(port),
  ).key;
}

/**
 * A photograph taken ON a step or ON a reading (R6) when nothing else is being
 * captured with it: the act IS its declaration (R123) — one `photo` item
 * naming what it proves, and its row, in one transaction.
 */
export function capturePhoto(
  port: JobPortValue,
  workOrderId: string,
  photo: ReadyPhoto,
  target: { task_id?: string; reading_id?: string },
): string {
  const photoId = port.newId();
  const captor = port.captor();
  const location = port.location();
  return capture(
    port.db,
    captor,
    {
      kind: 'photo',
      workOrderId,
      payload: { photo_id: photoId, sha256: photo.sha256, ...target },
      location,
      apply: (s, key) =>
        photoQ.insert(s, {
          id: photoId,
          outboxId: key,
          declareId: key,
          workOrderId,
          routeId: null,
          localPath: photo.localPath,
          sha256: photo.sha256,
          bytes: photo.bytes,
          width: photo.width,
          height: photo.height,
          capturedBy: captor.capturedBy,
          capturedAt: nowIso(port),
          location: location ? { lat: location.lat, lng: location.lng, accuracy_m: location.accuracy_m } : null,
        }),
    },
    deps(port),
  ).key;
}

/**
 * FF-20: a figure (or *Unable to read*, R13) with its unit (R12), flagged when
 * entered twice out of range (R11) — and any photographs taken on this reading
 * before it was saved, in the SAME transaction.
 *
 * DEF-MET-10609 (decision log 2026-10-26, PO *"yes do it"*): *Unable to read*
 * carries ONE reason from the utility's can't-read list — the same list RW-17
 * picks from — as its CODE in `unable_reason`, plus an optional `note`. Both
 * keys travel only on an *Unable to read*; a figure never carries them. A
 * phone with no list sends `unable_reason: null` and the server keeps the
 * answer anyway (no field record is dropped).
 */
export function recordReading(
  port: JobPortValue,
  workOrderId: string,
  reading: { id: string; unit: string },
  value: { value: string | null; flagged: boolean; unableToRead: boolean; unableReason?: string | null; note?: string | null },
  photos: readonly ReadyPhoto[] = [],
): string {
  const at = nowIso(port);
  const note = value.note?.trim() ? value.note.trim() : null;
  return capture(
    port.db,
    port.captor(),
    {
      kind: 'reading',
      workOrderId,
      payload: {
        reading_id: reading.id,
        value: value.value,
        unit: reading.unit,
        flagged: value.flagged,
        unable_to_read: value.unableToRead,
        ...(value.unableToRead ? { unable_reason: value.unableReason ?? null, note } : {}),
      },
      location: port.location(),
      photos: photoCaptures(photos, { reading_id: reading.id }),
      apply: (s) => {
        const changed = woReadingQ.recordValue(s, reading.id, {
          value: value.value,
          unit: reading.unit,
          flagged: value.flagged,
          unableToRead: value.unableToRead,
          capturedAt: at,
        });
        if (changed !== 1) throw new Error('the reading was not recorded — its unit did not match (hard rule 3)');
      },
    },
    deps(port),
  ).key;
}

/**
 * FF-20: the words typed on a TEXT reading — a serial, a seal number
 * (DEF-FLD-10585) — exactly as typed, trimmed only, with any photographs held
 * for it. Sent as `value_text`, the shape the server's text reading takes
 * (`apps/work/evidence.py` `_set_text_reading`): no unit, no range, no flag,
 * never posted as a meter read.
 */
export function recordTextReading(
  port: JobPortValue,
  workOrderId: string,
  readingId: string,
  valueText: string,
  photos: readonly ReadyPhoto[] = [],
): string {
  const at = nowIso(port);
  const text = valueText.trim();
  return capture(
    port.db,
    port.captor(),
    {
      kind: 'reading',
      workOrderId,
      payload: { reading_id: readingId, value_text: text, unable_to_read: false },
      location: port.location(),
      photos: photoCaptures(photos, { reading_id: readingId }),
      apply: (s) => {
        const changed = woReadingQ.recordText(s, readingId, { valueText: text, capturedAt: at });
        if (changed !== 1) throw new Error('the reading was not recorded — it is not a text reading');
      },
    },
    deps(port),
  ).key;
}

/** FF-59: a reading the template did not ask for — a variance with its reason (R7, requirement 72). No range, so never flagged. */
export function addReading(
  port: JobPortValue,
  workOrderId: string,
  input: { assetId: string; assetLabel: string; reason: string; value: string; unit: string; position: number; prompt: string },
): string {
  if (!input.reason) throw new Error('an added reading needs its reason (R7)');
  if (!input.unit) throw new Error('a reading never exists without its unit (hard rule 3)');
  const readingId = port.newId();
  const at = nowIso(port);
  return capture(
    port.db,
    port.captor(),
    {
      kind: 'reading',
      workOrderId,
      payload: {
        reading_id: readingId,
        asset_id: input.assetId,
        value: input.value,
        unit: input.unit,
        flagged: false,
        unable_to_read: false,
        added_in_field: true,
        reason: input.reason,
      },
      location: port.location(),
      apply: (s) => {
        woReadingQ.upsert(
          s,
          { id: readingId, workOrderId, position: input.position, prompt: input.prompt, unit: input.unit },
          at,
        );
        woReadingQ.recordValue(s, readingId, { value: input.value, unit: input.unit, flagged: false, unableToRead: false, capturedAt: at });
      },
    },
    deps(port),
  ).key;
}

/** FF-18: a step the template did not plan, with why and how long (R7). */
export function addStep(
  port: JobPortValue,
  workOrderId: string,
  input: { label: string; reason: string; minutes: number; photoRequired: boolean; position: number },
): string {
  if (!input.label.trim() || !input.reason.trim()) throw new Error('an added step needs what and why (R7)');
  const stepId = port.newId();
  const at = nowIso(port);
  const detail: TaskDetail = { minutes: input.minutes, added_by: port.displayName, added_at: at };
  return capture(
    port.db,
    port.captor(),
    {
      kind: 'remark',
      workOrderId,
      payload: {
        added_in_field: true,
        item_kind: 'task',
        task_id: stepId,
        label: input.label.trim(),
        reason: input.reason.trim(),
        minutes: input.minutes,
        photo_required: input.photoRequired,
      },
      location: port.location(),
      apply: (s) =>
        woItemQ.upsert(
          s,
          {
            id: stepId,
            workOrderId,
            kind: 'task',
            position: input.position,
            label: input.label.trim(),
            photoRequired: input.photoRequired,
            photoMinCount: input.photoRequired ? 1 : 0,
            addedInField: true,
            reason: input.reason.trim(),
            detail,
          },
          at,
        ),
    },
    deps(port),
  ).key;
}

/** FF-23 / FF-24: how many of a planned part were used, against the step (requirement 16). Money is read, never written (R16). */
export function setMaterialUsed(
  port: JobPortValue,
  workOrderId: string,
  material: { id: string; detail: MaterialDetail; state: string | null },
  used: number,
  stepId: string | null,
): string {
  const detail: MaterialDetail = { ...material.detail, used, step_id: stepId ?? material.detail.step_id ?? null };
  return capture(
    port.db,
    port.captor(),
    {
      kind: 'material',
      workOrderId,
      payload: { material_id: material.id, used_qty: used, step_id: detail.step_id ?? null },
      location: port.location(),
      apply: (s) => jobQ.setItemStateAndDetail(s, material.id, used > 0 ? 'used' : null, detail),
    },
    deps(port),
  ).key;
}

/** FF-23 *Add material*: a part not on the template, with its reason (R7). */
export function addMaterial(
  port: JobPortValue,
  workOrderId: string,
  input: { label: string; code: string; qty: number; reason: string; position: number },
): string {
  if (!input.label.trim() || !input.reason.trim()) throw new Error('an added material needs what and why (R7)');
  const id = port.newId();
  const at = nowIso(port);
  const detail: MaterialDetail = { code: input.code.trim() || undefined, used: input.qty, added_by: port.displayName, added_at: at };
  return capture(
    port.db,
    port.captor(),
    {
      kind: 'material',
      workOrderId,
      payload: {
        material_id: id,
        used_qty: input.qty,
        added_in_field: true,
        label: input.label.trim(),
        code: input.code.trim() || null,
        reason: input.reason.trim(),
      },
      location: port.location(),
      apply: (s) =>
        woItemQ.upsert(
          s,
          {
            id,
            workOrderId,
            kind: 'material',
            position: input.position,
            label: input.label.trim(),
            addedInField: true,
            reason: input.reason.trim(),
            state: 'used',
            detail,
          },
          at,
        ),
    },
    deps(port),
  ).key;
}

/** FF-19: a checklist answer, held on the handset (see the header — no outbox kind exists for it). */
export function saveChecklistAnswer(port: JobPortValue, questionId: string, answer: string | null): void {
  const s = scoped(port.db, port.captor().technicianId);
  port.db.transaction(() => woItemQ.setState(s, questionId, answer ?? ''));
}

/** FF-58: back to Queued, unassigned, with the technician's name and reason (R106). Never an emergency (R107). */
export function handBack(
  port: JobPortValue,
  workOrderId: string,
  input: { reason: string; note: string; emergency: boolean },
): string {
  if (input.emergency) throw new Error('an emergency cannot be handed back from the app (R107)');
  if (!input.reason) throw new Error('a hand-back needs its reason (R106)');
  const at = nowIso(port);
  const captor = port.captor();
  return capture(
    port.db,
    captor,
    {
      kind: 'hand_back',
      workOrderId,
      payload: { reason: input.reason, note: input.note.trim() || null },
      location: port.location(),
      apply: (s, key) =>
        activityQ.insert(s, {
          id: port.newId(),
          workOrderId,
          kind: 'status',
          status: 'handed_back',
          text: input.reason,
          author: captor.capturedBy,
          at,
          outboxId: key,
        }),
    },
    deps(port),
  ).key;
}

/** FF-60: a paper about the asset — camera, file or typed, the source recorded on each (R108). */
export function addPaper(
  port: JobPortValue,
  workOrderId: string,
  assetId: string,
  input:
    | { source: 'camera'; title: string; photo: ReadyPhoto }
    | { source: 'file'; title: string; localPath: string; bytes: number; kind: string | null }
    | { source: 'typed'; title: string; text: string },
): string {
  if (!input.title.trim()) throw new Error('a paper needs a name');
  const documentId = port.newId();
  const at = nowIso(port);
  const localPath = input.source === 'camera' ? input.photo.localPath : input.source === 'file' ? input.localPath : null;
  const bytes = input.source === 'camera' ? input.photo.bytes : input.source === 'file' ? input.bytes : 0;
  return capture(
    port.db,
    port.captor(),
    {
      kind: 'document',
      workOrderId,
      payload: {
        document_id: documentId,
        asset_id: assetId,
        title: input.title.trim(),
        source: input.source,
        text: input.source === 'typed' ? input.text.trim() : null,
        sha256: input.source === 'camera' ? input.photo.sha256 : null,
      },
      location: port.location(),
      apply: (_s, key) =>
        documentQ.upsert(
          port.db,
          {
            id: documentId,
            ownerKind: 'asset',
            ownerId: assetId,
            title: input.title.trim(),
            kind: input.source === 'file' ? input.kind : input.source === 'camera' ? 'image/jpeg' : 'text/plain',
            source: input.source,
            localPath,
            bytes,
            outboxId: key,
          },
          at,
        ),
    },
    deps(port),
  ).key;
}

// ── The clocks (R8, R9) ──────────────────────────────────────────────────────

function clockAct(
  port: JobPortValue,
  workOrderId: string,
  payload: Record<string, unknown>,
  apply: (s: ScopedRunner, key: string) => void,
): string {
  return capture(
    port.db,
    port.captor(),
    { kind: 'crew_time', workOrderId, payload, location: port.location(), apply },
    deps(port),
  ).key;
}

/**
 * Start a clock — Depart starts travel, Start work starts labour (R9). Any
 * running clock of the OTHER kind for this person stops at the same instant,
 * so travel and labour never overlap. Exported for FF-14 (Stop), which draws
 * Depart / Arrive / Start.
 */
export function startClock(port: JobPortValue, workOrderId: string, kind: 'travel' | 'labour'): string {
  const captor = port.captor();
  const at = nowIso(port);
  const segmentId = port.newId();
  return clockAct(port, workOrderId, { action: 'start', kind, segment_id: segmentId, at }, (s, key) => {
    for (const seg of jobQ.crewTimeForOrder(s, workOrderId)) {
      if (seg.person_id === captor.technicianId && seg.ended_at === null) jobQ.endCrewTime(s, seg.id, at);
    }
    crewTimeQ.insert(s, { id: segmentId, workOrderId, personId: captor.technicianId, kind, startedAt: at, outboxId: key });
  });
}

/** Stop a running clock — Arrive stops travel, Pause stops labour. */
export function stopClock(port: JobPortValue, workOrderId: string, segmentId: string): string {
  const at = nowIso(port);
  // Which clock stops decides the server's moment (`sync/doors.ts`): travel
  // stopping is the ARRIVAL, labour stopping is the end of work.
  const kind =
    jobQ.crewTimeForOrder(scoped(port.db, port.captor().technicianId), workOrderId).find((seg) => seg.id === segmentId)?.kind ?? null;
  return clockAct(port, workOrderId, { action: 'stop', segment_id: segmentId, kind, at }, (s) => {
    if (jobQ.endCrewTime(s, segmentId, at) !== 1) throw new Error('that clock is not running');
  });
}

/** *Correct time* (R9), stamped who and when on the job's activity (R10). */
export function correctClock(
  port: JobPortValue,
  workOrderId: string,
  segment: { id: string; started_at: string; ended_at: string | null; kind: string },
  to: { startedAt: string; endedAt: string | null },
): string {
  if (to.endedAt !== null && to.endedAt < to.startedAt) throw new Error('a clock cannot end before it starts');
  const captor = port.captor();
  const at = nowIso(port);
  return clockAct(
    port,
    workOrderId,
    {
      action: 'correct',
      segment_id: segment.id,
      kind: segment.kind,
      from: { started_at: segment.started_at, ended_at: segment.ended_at },
      to: { started_at: to.startedAt, ended_at: to.endedAt },
    },
    (s, key) => {
      jobQ.correctCrewTime(s, segment.id, to.startedAt, to.endedAt);
      activityQ.insert(s, {
        id: port.newId(),
        workOrderId,
        kind: 'status',
        status: 'time_corrected',
        text: segment.kind,
        author: captor.capturedBy,
        at,
        outboxId: key,
      });
    },
  );
}
