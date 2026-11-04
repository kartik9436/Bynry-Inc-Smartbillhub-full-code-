/**
 * What the job screens show, READ from the handset store and counted from
 * rows (US-FLD-026 §5: *"section counts … counted from rows"*). No figure here
 * is invented: a section the store holds nothing for counts 0 of 0, and a fact
 * the handset does not carry (a balance, a van count the server did not send)
 * is absent, never zero.
 *
 * The order holds its OWN copy of the template (R112), so every count comes
 * from this order's `wo_item` / `wo_reading` rows and none from
 * `work_order_templates`.
 *
 * ⚠ GAPS IN THE STORE, NAMED RATHER THAN GUESSED:
 *  - `wo_reading` has no meter column, so a reading cannot say which meter
 *    (MASTER W-4471 / SUB-METER W-4471-A) — the design's R14 shape. The card
 *    shows the prompt and the unit; the meter line waits on a column
 *    (`asset_id`, and `added_in_field` + `reason` for FF-59, US-FLD-072 §5).
 *  - Nothing on the handset says a job is an EMERGENCY (R107). `isEmergency`
 *    reads `work_order.extra.emergency`, which the server's job card does not
 *    send yet — so today no job reads as one, and FF-58 still says, as drawn,
 *    that an emergency cannot be handed back here.
 *  - Van stock is not on the handset (FF-49 is read online); a material's van
 *    count is read from the item's own detail when the server sent one.
 */
import { fromJson } from '../../db/json';
import * as assetQ from '../../db/queries/asset';
import * as customerQ from '../../db/queries/customer';
import * as documentQ from '../../db/queries/document';
import * as jobQ from '../../db/queries/jobScreens';
import * as premiseQ from '../../db/queries/premise';
import * as workOrderQ from '../../db/queries/workOrder';
import * as woItemQ from '../../db/queries/woItem';
import * as woReadingQ from '../../db/queries/woReading';
import type { CrewTimeRow } from '../../db/queries/crewTime';
import type { OrderPhotoRow } from '../../db/queries/jobScreens';
import { scoped } from '../../db/scoped';
import type { JobPortValue } from './JobPort';

/** What only a task carries (R130: the kind's own detail). */
export interface TaskDetail {
  minutes?: number;
  /** The template's instruction for the step, verbatim — the open card's second line (DEF-FLD-10587). */
  instruction?: string;
  /** The template's words for each photograph it asks for ("Before", "After"). */
  photo_labels?: string[];
  added_by?: string;
  added_at?: string;
}

export interface MaterialDetail {
  code?: string;
  planned?: number;
  /** On the van, when the server sent it. */
  van?: number | null;
  used?: number;
  /** A unit price, a decimal string — shown up to 4 places, never computed with (R16, R20). */
  unit_cost?: string | null;
  serial?: string | null;
  step_id?: string | null;
  added_by?: string;
  added_at?: string;
}

export interface ChecklistDetail {
  answer_type?: 'yes_no' | 'number';
  unit?: string;
  /** Asked only when another question was answered this way (requirement 18). */
  show_if?: { item_id: string; answer: string };
  /** The template's own line under an answer ("No opens a tamper report"). */
  hints?: Record<string, string>;
}

export type ItemRow = woItemQ.WoItemRow;
export type ReadingRow = woReadingQ.WoReadingRow;

export interface TaskView {
  row: ItemRow;
  detail: TaskDetail;
  photos: OrderPhotoRow[];
  /** How many photographs the template asks for (R110); 0 when none. */
  photoMin: number;
  done: boolean;
}

export interface ReadingView {
  row: ReadingRow;
  photos: OrderPhotoRow[];
  taken: boolean;
}

export interface MaterialView {
  row: ItemRow;
  detail: MaterialDetail;
  planned: number;
  used: number;
  /** Planned but not enough on the van, when the van count is known. */
  shortOnVan: boolean;
}

export interface ChecklistView {
  row: ItemRow;
  detail: ChecklistDetail;
  visible: boolean;
  /** The question whose answer made this one appear. */
  because: ItemRow | null;
}

export interface ClockSummary {
  minutes: number;
  firstStart: string | null;
  lastEnd: string | null;
  running: boolean;
  /** The open segment's start, when one is running. */
  runningSince: string | null;
  openId: string | null;
  segments: CrewTimeRow[];
}

export interface JobView {
  order: workOrderQ.WorkOrderRow;
  customer: customerQ.CustomerRow | null;
  premise: premiseQ.PremiseRow | null;
  asset: assetQ.AssetRow | null;
  subMeters: number;
  safety: { items: ItemRow[]; done: number; total: number };
  tasks: { items: TaskView[]; done: number; total: number; needPhoto: number; estMinutes: number; currentIndex: number };
  materials: { items: MaterialView[]; planned: MaterialView[]; added: MaterialView[]; satisfied: number; notOnVan: number; short: number };
  checklist: { items: ChecklistView[]; answered: number; total: number };
  readings: { items: ReadingView[]; taken: number; total: number; needPhoto: number; flagged: number };
  photos: OrderPhotoRow[];
  papers: documentQ.DocumentRow[];
  help: number;
  travel: ClockSummary;
  labour: ClockSummary;
  crew: { people: string[]; minutes: number };
  events: number;
  remarks: number;
  emergency: boolean;
}

const detailOf = <T,>(row: { detail: string | null }): T => (fromJson<T>(row.detail) ?? ({} as T));

export function isEmergency(order: workOrderQ.WorkOrderRow): boolean {
  const extra = fromJson<Record<string, unknown>>(order.extra) ?? {};
  return extra.emergency === true;
}

/** Every photograph the template asks for on a task: the count, else one if it is required. */
export function photosAskedFor(row: { photo_required: number; photo_min_count: number }): number {
  return Math.max(row.photo_min_count, row.photo_required ? 1 : 0);
}

function summarise(segments: CrewTimeRow[], now: string): ClockSummary {
  let minutes = 0;
  let runningSince: string | null = null;
  let openId: string | null = null;
  let lastEnd: string | null = null;
  for (const seg of segments) {
    const end = seg.ended_at ?? now;
    minutes += Math.max(0, Math.floor((Date.parse(end) - Date.parse(seg.started_at)) / 60000));
    if (seg.ended_at === null) {
      runningSince = seg.started_at;
      openId = seg.id;
    } else if (lastEnd === null || seg.ended_at > lastEnd) {
      lastEnd = seg.ended_at;
    }
  }
  return {
    minutes,
    firstStart: segments[0]?.started_at ?? null,
    lastEnd,
    running: openId !== null,
    runningSince,
    openId,
    segments,
  };
}

/** The checklist with each question's visibility worked out from the answers so far. */
export function checklistView(items: ItemRow[]): ChecklistView[] {
  const byId = new Map(items.map((r) => [r.id, r]));
  const visible = new Map<string, boolean>();
  const isVisible = (row: ItemRow, depth = 0): boolean => {
    const known = visible.get(row.id);
    if (known !== undefined) return known;
    const d = detailOf<ChecklistDetail>(row);
    let v = true;
    if (d.show_if && depth < items.length) {
      const parent = byId.get(d.show_if.item_id);
      v = parent !== undefined && isVisible(parent, depth + 1) && parent.state === d.show_if.answer;
    }
    visible.set(row.id, v);
    return v;
  };
  return items.map((row) => {
    const detail = detailOf<ChecklistDetail>(row);
    return {
      row,
      detail,
      visible: isVisible(row),
      because: detail.show_if ? (byId.get(detail.show_if.item_id) ?? null) : null,
    };
  });
}

export function loadJob(port: JobPortValue, workOrderId: string): JobView | null {
  const tech = port.captor().technicianId;
  const s = scoped(port.db, tech);
  const order = workOrderQ.getMine(s, workOrderId);
  if (!order) return null;
  const now = port.clock.now().toISOString();
  const items = woItemQ.listForOrder(s, workOrderId);
  const readingRows = woReadingQ.listForOrder(s, workOrderId);
  const photos = jobQ.photosForOrder(s, workOrderId);
  const ofKind = (k: woItemQ.WoItemKind) => items.filter((i) => i.kind === k).sort((a, b) => a.position - b.position);

  const safetyItems = ofKind('safety');
  const taskRows = ofKind('task');
  const tasks: TaskView[] = taskRows.map((row) => ({
    row,
    detail: detailOf<TaskDetail>(row),
    photos: photos.filter((p) => p.task_id === row.id),
    photoMin: photosAskedFor(row),
    done: row.state === 'done',
  }));
  const currentIndex = tasks.findIndex((t) => !t.done);

  const materials: MaterialView[] = ofKind('material').map((row) => {
    const detail = detailOf<MaterialDetail>(row);
    const planned = row.added_in_field ? 0 : (detail.planned ?? 0);
    const used = detail.used ?? 0;
    const van = detail.van;
    return { row, detail, planned, used, shortOnVan: van !== undefined && van !== null && used < planned && van < planned - used };
  });
  const plannedMaterials = materials.filter((m) => !m.row.added_in_field);
  const addedMaterials = materials.filter((m) => m.row.added_in_field);

  const checklist = checklistView(ofKind('checklist'));
  const shown = checklist.filter((c) => c.visible);

  const readings: ReadingView[] = readingRows.map((row) => ({
    row,
    photos: photos.filter((p) => p.reading_id === row.id),
    // DEF-FLD-10585: a text reading is taken when its words are saved.
    taken: row.value !== null || row.value_text !== null || row.unable_to_read === 1,
  }));

  const crew = jobQ.crewTimeForOrder(s, workOrderId);
  const mine = crew.filter((c) => c.person_id === tech);
  const travel = summarise(mine.filter((c) => c.kind === 'travel'), now);
  const labour = summarise(mine.filter((c) => c.kind === 'labour'), now);
  const people = [...new Set(crew.map((c) => c.person_id))];
  const crewMinutes = summarise(crew.filter((c) => c.kind === 'labour'), now).minutes;

  const asset = order.asset_id ? (assetQ.get(port.db, order.asset_id) ?? null) : null;
  // Every help entry the job carries — the SOP, the numbers, the links — its
  // own and its template's, each once: the job's copy of a template's entry
  // names the same file or number (DEF-FLD-10581, MQ-011).
  const help = documentQ.distinctHelp([
    ...documentQ.listForOwner(port.db, 'work_order', workOrderId),
    ...(order.template_id ? documentQ.listForOwner(port.db, 'template', order.template_id) : []),
  ]).length;
  const counts = jobQ.activityCounts(s, workOrderId);

  return {
    order,
    customer: order.customer_id ? (customerQ.get(port.db, order.customer_id) ?? null) : null,
    premise: order.premise_id ? (premiseQ.get(port.db, order.premise_id) ?? null) : null,
    asset,
    subMeters: asset ? jobQ.subMeterCount(port.db, asset.id) : 0,
    safety: { items: safetyItems, done: safetyItems.filter((i) => i.state === 'ticked').length, total: safetyItems.length },
    tasks: {
      items: tasks,
      done: tasks.filter((t) => t.done).length,
      total: tasks.length,
      needPhoto: tasks.filter((t) => t.photoMin > t.photos.length).length,
      estMinutes: tasks.reduce((n, t) => n + (t.detail.minutes ?? 0), 0),
      currentIndex,
    },
    materials: {
      items: materials,
      planned: plannedMaterials,
      added: addedMaterials,
      satisfied: plannedMaterials.filter((m) => m.used >= m.planned).length,
      notOnVan: plannedMaterials.filter((m) => m.shortOnVan).length,
      short: plannedMaterials.filter((m) => m.used < m.planned).length,
    },
    checklist: {
      items: checklist,
      answered: shown.filter((c) => c.row.state !== null && c.row.state !== '').length,
      total: shown.length,
    },
    readings: {
      items: readings,
      // MQ-020 (PO 2026-10-24): a figure saved without its REQUIRED dial photo is not done yet.
      taken: readings.filter((r) => r.taken && (r.row.unable_to_read === 1 || !(r.row.photo_required === 1 && r.photos.length === 0))).length,
      total: readings.length,
      needPhoto: readings.filter((r) => r.row.photo_required === 1 && r.photos.length === 0).length,
      flagged: readings.filter((r) => r.row.flagged === 1).length,
    },
    photos,
    papers: asset ? documentQ.listForOwner(port.db, 'asset', asset.id) : [],
    help,
    travel,
    labour,
    crew: { people, minutes: crewMinutes },
    events: counts.events,
    remarks: counts.remarks,
    emergency: isEmergency(order),
  };
}

/**
 * ⚠ WHETHER A REQUIRED PHOTOGRAPH NEVER TAKEN STOPS THE CLOSE — ONE CONSTANT.
 * PO 2026-10-21 (decision log, "the PO corrects four of the ten answers"): a
 * required photo missing at close WARNS AND NEVER BLOCKS — the close goes
 * ahead and records the gap (FF-34 sends `required_photos_missing` with it),
 * the field app's R110 carried to zero taken. This supersedes the signed
 * `BR-WRK-040` clause *"A missing REQUIRED photograph stops the job closing"*
 * for the native app (the supersession is the coordinator's to stamp on the
 * rule). FF-34 reads this constant; the server re-derives readiness either way.
 */
export const REQUIRED_PHOTO_BLOCKS_CLOSE = false;

/** Required photographs never taken — shown as missing whether or not they block (FF-21, FF-34). */
export function requiredPhotosMissing(view: JobView): string[] {
  return [
    ...view.tasks.items.filter((t) => t.row.photo_required && t.photos.length === 0).map((t) => t.row.id),
    ...view.readings.items.filter((r) => r.row.photo_required && r.photos.length === 0).map((r) => r.row.id),
  ];
}

/** What stops the close for want of a photograph, and what only warns (R110). */
export function photoReadiness(view: JobView): { blocking: string[]; short: string[] } {
  const blocking: string[] = [];
  const short: string[] = [];
  for (const task of view.tasks.items) {
    if (task.row.photo_required && task.photos.length === 0) blocking.push(task.row.id);
    else if (task.photos.length < task.photoMin) short.push(task.row.id);
  }
  for (const reading of view.readings.items) {
    if (reading.row.photo_required && reading.photos.length === 0) blocking.push(reading.row.id);
  }
  return { blocking: REQUIRED_PHOTO_BLOCKS_CLOSE ? blocking : [], short: REQUIRED_PHOTO_BLOCKS_CLOSE ? short : [...blocking, ...short] };
}

/** All-or-none (R3): every safety row ticked. A job with no safety rows has nothing locking it. */
export function safetyPassed(view: JobView | null): boolean {
  return view === null || view.safety.done === view.safety.total;
}
