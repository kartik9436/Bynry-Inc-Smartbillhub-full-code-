// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 2, lane ORDER-PAGE — the Checklist tab, images 05
//           (the PLAN, not completed) and 06 (the RECORD, completed), and the
//           Parts tab, image 07.
// Tasks:    P1.18 (no four trailing zeros) · P1.22 (the photographs, on the row
//           that asked for them) · P1.28 (tasks as a TABLE — ruling 14) · P1.29
//           (two shapes — rulings 15 and 17)
// Rules:    ruling 18 (*"back office cannot complete the job it can only accept
//           it"*) — so the office's tick boxes are GONE on both shapes; a line is
//           ticked on the phone and read here. `BR-WRK-039` (out of range FLAGS,
//           never blocks) and `BR-WRK-040` (a missing required photo BLOCKS) —
//           different tiers, different sentences. Hard rule 3 (the unit is its
//           own cell). B14 rule 31 (no id is a visible value) · rule 43.
// ───────────────────────────────────────────────────────
//
// ⚠ **THE PLAN SHOWS NO TICK, NO VALUE AND NO PHOTOGRAPH, EVEN WHERE THE ROW
// HAS ONE.** Ruling 15: *"if not completed then that data should not be
// visible"*. A job a technician is half-way through has ticked rows on the
// server; the open shape still draws the plan, because the record belongs to
// the completed job and the office reviews it once, whole.
//
// ⚠ **THE VERDICT IS READ, NEVER RECOMPUTED.** The footer's counts come from
// `GET …/close-readiness`; deriving them here from the rows would be a second
// opinion about whether a job can close.
import { useTranslation } from "react-i18next";

import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { Dash } from "@/features/metering/meteringShared";

import type {
  CloseReadiness,
  OrderAttachment,
  OrderChecklist,
  OrderReadingRow,
  OrderTaskRow,
} from "../workEndpoints";
import { quantityText, rangeText, whenText } from "./orderFormat";
import type { Regional } from "./orderFormat";
import type { OrderShape } from "./orderShape";
import { PhotoThumb } from "./PhotoViewer";
import type { ViewerPhoto } from "./PhotoViewer";

type Translator = (key: string, params?: Record<string, unknown>) => string;

/** Served beside `ticked_by` (lane ORDER-PAGE, CR-168 §7.3 appended): the NAME
 *  of whoever ticked the line on the phone. `ticked_by` is an id and is never
 *  drawn (B14 rule 31). */
type Ticked = { ticked_at: string | null; ticked_by_name?: string | null };

/** A text reading's answer (`value_text`, P1.33 — lane SRV-1), and the
 *  answer that there is no figure (`unable_to_read`, DEF-WRK-10601). */
type ReadingRow = OrderReadingRow & {
  value_text?: string | null;
  unable_to_read?: boolean;
  unable_reason?: string | null;
  /** DEF-MET-10609 — the reason's NAME from the one can't-read list, and the
   *  technician's optional note. */
  unable_reason_name?: string | null;
  unable_note?: string | null;
};
type TaskRow = OrderTaskRow & { instruction?: string | null; ticked_by_name?: string | null };

/** The one attachment kind that is not a photograph of the work. */
const SIGNATURE_KIND = "work_order_signature";

/**
 * Every photograph of the job, in the order a supervisor reads it — tasks
 * first (each task's photographs oldest first), then readings, then the
 * photographs that belong to the job at large — each with the words the
 * viewer shows. The viewer's *1 of 3* counts THIS list.
 *
 * ⚠ **EVERY PHOTOGRAPH, NOT ONE PER ROW (`DEF-FLD-10640`, PO report FB-015,
 * WO-0171).** This read only each task's and reading's single
 * `photo_attachment_id`, so a photograph taken for the job at large (no task,
 * no reading — `evidence_models.WorkOrderAttachment`'s third case) and a
 * task's second photograph were stored on the server and never shown: the
 * job read completed with no photo. The attachments list is the source; a
 * row's `photo_attachment_id` only decides which of its photographs comes
 * first and keeps its row key.
 */
export function checklistPhotos(
  list: OrderChecklist | undefined,
  attachments: OrderAttachment[],
  t: Translator,
): ViewerPhoto[] {
  const shots = attachments.filter((a) => a.kind !== SIGNATURE_KIND);
  const byId = new Map(shots.map((a) => [a.id, a]));
  const placed = new Set<string>();
  const photos: ViewerPhoto[] = [];
  const add = (key: string, id: string, title: string, forText: string) => {
    if (placed.has(id)) return;
    placed.add(id);
    const shot = byId.get(id);
    photos.push({
      key,
      title,
      attachmentId: id,
      takenBy: shot?.added_by_name ?? null,
      takenAt: shot?.taken_at ?? null,
      forText,
    });
  };
  const oldestFirst = (a: OrderAttachment, b: OrderAttachment) =>
    (a.taken_at ?? "").localeCompare(b.taken_at ?? "");
  for (const task of list?.tasks ?? []) {
    const forText = t("work.order.photo.forTask", { at: task.seq, total: list?.tasks_total ?? 0 });
    if (task.photo_attachment_id !== null) {
      add(`task-${task.seq}`, task.photo_attachment_id, task.title, forText);
    }
    shots
      .filter((a) => a.task_id === task.id)
      .sort(oldestFirst)
      .forEach((a, n) => add(`task-${task.seq}-${n + 1}`, a.id, task.title, forText));
  }
  for (const reading of list?.readings ?? []) {
    if (reading.photo_attachment_id !== null) {
      add(`reading-${reading.seq}`, reading.photo_attachment_id, reading.prompt, reading.prompt);
    }
    shots
      .filter((a) => a.reading_id === reading.id)
      .sort(oldestFirst)
      .forEach((a, n) => add(`reading-${reading.seq}-${n + 1}`, a.id, reading.prompt, reading.prompt));
  }
  // The job at large — and any photograph whose row this checklist no longer lists.
  [...shots]
    .filter((a) => !placed.has(a.id))
    .sort(oldestFirst)
    .forEach((a, n) => add(`job-${n + 1}`, a.id, t("work.order.photo.job"), t("work.order.photo.forJob")));
  return photos;
}

/**
 * *Photos* — every photograph of the completed job in one place, each opening
 * the viewer with who took it and when (`DEF-FLD-10640`). The checklist rows
 * still carry their own; this is where a photograph that belongs to no row is
 * seen at all. No id is drawn (B14 rule 31): a photograph is named by what it
 * was taken for.
 */
export function OrderPhotosPanel(props: {
  orderId: string;
  photos: ViewerPhoto[];
  onOpenPhoto: (key: string) => void;
  regional: Regional;
}) {
  const { t } = useTranslation();
  if (props.photos.length === 0) return null;
  return (
    <Panel title={t("work.order.photos.title")}>
      <ul className="grid grid-cols-2 gap-4 sm:grid-cols-4" data-order-photos="">
        {props.photos.map((photo) => (
          <li key={photo.key} className="flex flex-col gap-1" data-order-photo={photo.key}>
            <PhotoThumb
              orderId={props.orderId}
              photo={photo}
              onOpen={() => props.onOpenPhoto(photo.key)}
            />
            <span className="text-sm text-neutral-900">{photo.title}</span>
            <span className="text-sm text-neutral-600">
              {[photo.takenBy, whenText(photo.takenAt, props.regional)].filter(Boolean).join(" · ") || (
                <Dash />
              )}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

/** A stored document's key is an id (B14 rule 31) — `DEF-WRK-9637`. Since
 *  `2.504.0` a help document uploaded in the builder keeps its stored file's
 *  id in `ref`, and this read carries no file name beside it, so an id-shaped
 *  ref is never drawn: the row reads by its label alone. */
const STORED_KEY = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;

/** Where a help row is found: a link OPENS (P3.25), a typed place or a phone
 *  number reads as itself, and a stored key reads as nothing. */
function HelpPlace(props: { kind: string; value: string | null }) {
  const value = props.value;
  if (value === null || value === "" || STORED_KEY.test(value)) return null;
  if (props.kind === "link") {
    return (
      <span className="text-neutral-600">
        {" · "}
        <a className="text-accent" href={value} target="_blank" rel="noreferrer">
          {value}
        </a>
      </span>
    );
  }
  return <span className="text-neutral-600"> · {value}</span>;
}

function doneBy(row: Ticked, regional: Regional): string | null {
  if (row.ticked_at === null) return null;
  return [row.ticked_by_name ?? null, whenText(row.ticked_at, regional)].filter(Boolean).join(" · ");
}

export function OrderChecklistTab(props: {
  orderId: string;
  shape: OrderShape;
  list: OrderChecklist | undefined;
  readiness?: CloseReadiness;
  photos: ViewerPhoto[];
  onOpenPhoto: (key: string) => void;
  regional: Regional;
}) {
  const { t } = useTranslation();
  const list = props.list;
  if (list === undefined) return null;
  // B14 rule 17 — an order with no template has no checklist: an empty state.
  // The sentence is chosen on `template_id`, never on the counts (DEF-WRK-4635).
  if (list.tasks.length === 0 && list.safety.length === 0) {
    return (
      <Panel title={t("work.order.checklist.title")}>
        <Note>
          {t(list.template_id === null ? "work.order.checklist.empty" : "work.order.checklist.emptyTemplate")}
        </Note>
      </Panel>
    );
  }
  const record = props.shape === "completed";
  const photoKey = new Map(props.photos.map((p) => [p.attachmentId, p]));
  return (
    <div className="flex flex-col" data-checklist={record ? "record" : "plan"}>
      <Panel title={t("work.order.safety.title")}>
        <ul className="flex flex-col gap-1.5">
          {list.safety.map((safety) => {
            const done = record ? doneBy(safety as Ticked, props.regional) : null;
            return (
              <li key={safety.id} className="flex items-baseline gap-2" data-safety-row={safety.seq}>
                <span aria-hidden="true">{done !== null ? "✓" : "·"}</span>
                <span>{safety.text}</span>
                {done !== null && (
                  <span className="text-neutral-600" data-done-by="">
                    · {done}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </Panel>

      <Panel
        title={t("work.order.tasks.title", {
          // `count` picks `_one` / `_other` — without it the panel printed its
          // own key (DEF-WRK-4104).
          count: list.tasks_total,
          steps: list.tasks_total,
          minutes: list.tasks_est_minutes,
        })}
      >
        {record && (
          <p className="mb-3" data-tasks-count="">
            {t("work.order.tasks.count", { done: list.tasks_ticked, total: list.tasks_total })}
          </p>
        )}
        <PlainTable>
          <thead>
            <tr>
              <th>{t("work.order.tasks.seq")}</th>
              <th>{t("work.order.tasks.task")}</th>
              <th>{t("work.order.tasks.minutesHead")}</th>
              <th>{t("work.order.tasks.photo")}</th>
              {record && <th>{t("work.order.tasks.done")}</th>}
            </tr>
          </thead>
          <tbody>
            {list.tasks.map((raw) => {
              const task = raw as TaskRow;
              const photo = task.photo_attachment_id ? photoKey.get(task.photo_attachment_id) : undefined;
              const done = doneBy(task, props.regional);
              return (
                <tr key={task.id} data-task-row={task.seq}>
                  <td>{task.seq}</td>
                  <td>
                    {task.title}
                    {task.instruction ? (
                      <span className="mt-1 block text-sm text-neutral-600" data-task-instruction="">
                        {task.instruction}
                      </span>
                    ) : null}
                  </td>
                  <td>{t("work.order.tasks.minutes", { minutes: task.est_minutes })}</td>
                  <td>
                    {record && photo !== undefined ? (
                      <PhotoThumb
                        orderId={props.orderId}
                        photo={photo}
                        onOpen={() => props.onOpenPhoto(photo.key)}
                      />
                    ) : record && task.photo_required ? (
                      <span className="text-sm text-warning-700" data-flag="missing-photo">
                        {t("work.order.readings.photoMissing")}
                      </span>
                    ) : task.photo_required ? (
                      <StatusPill tone="neutral">{t("work.order.readings.required")}</StatusPill>
                    ) : (
                      <Dash />
                    )}
                  </td>
                  {record && (
                    <td data-task-done="">{done !== null ? `✓ ${done}` : <Dash />}</td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </PlainTable>
      </Panel>

      <Panel title={t("work.order.readings.title")}>
        <ReadingsTable
          orderId={props.orderId}
          rows={list.readings as ReadingRow[]}
          record={record}
          readiness={props.readiness}
          photoKey={photoKey}
          onOpenPhoto={props.onOpenPhoto}
        />
      </Panel>

      <Panel title={t("work.order.help.title")}>
        <ul className="flex flex-col gap-1.5">
          {list.help.map((help) => (
            <li key={help.id} data-help-row={help.seq}>
              <span>{help.label}</span>
              <HelpPlace kind={help.kind} value={help.ref} />
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

function ReadingsTable(props: {
  orderId: string;
  rows: ReadingRow[];
  record: boolean;
  readiness?: CloseReadiness;
  photoKey: Map<string | null, ViewerPhoto>;
  onOpenPhoto: (key: string) => void;
}) {
  const { t } = useTranslation();
  const ready = props.readiness;
  return (
    <>
      <PlainTable>
        <thead>
          <tr>
            <th>{t("work.order.readings.reading")}</th>
            <th>{t("work.order.readings.unit")}</th>
            <th>{t("work.order.readings.range")}</th>
            <th>{t("work.order.readings.photo")}</th>
            {props.record && <th>{t("work.order.readings.value")}</th>}
            {props.record && <th>{t("work.order.readings.photograph")}</th>}
          </tr>
        </thead>
        <tbody>
          {props.rows.map((reading) => {
            const missingPhoto = reading.photo_required && !reading.photo_attachment_id;
            const photo = reading.photo_attachment_id
              ? props.photoKey.get(reading.photo_attachment_id)
              : undefined;
            // DEF-WRK-10601 — *Unable to read* is the technician's answer, not a
            // blank: shown as such, with the reason when there is one.
            // DEF-MET-10609 — the reason's NAME from the one can't-read list
            // (*Unable to read · Dog*), never its code; a row from before the
            // list carries the phone's own words, and those are shown as sent.
            const value = reading.unable_to_read
              ? [t("work.order.readings.unable"), reading.unable_reason_name ?? reading.unable_reason]
                  .filter(Boolean)
                  .join(" · ")
              : (reading.value_text ?? quantityText(reading.value));
            return (
              <tr key={reading.id} data-reading-row={reading.seq}>
                <td>{reading.prompt}</td>
                <td>{reading.unit_of_measure}</td>
                <td>{rangeText(reading.min_value, reading.max_value) ?? <Dash />}</td>
                <td>
                  <StatusPill tone="neutral">
                    {reading.photo_required
                      ? t("work.order.readings.required")
                      : t("work.order.readings.optional")}
                  </StatusPill>
                </td>
                {props.record && (
                  <td>
                    {value ?? <Dash>{t("work.order.readings.notTaken")}</Dash>}
                    {reading.unable_to_read && reading.unable_note ? (
                      <span className="mt-1 block text-sm text-neutral-600" data-reading-note>
                        {reading.unable_note}
                      </span>
                    ) : null}
                    {reading.in_range === false ? (
                      <span className="mt-1 block text-sm text-danger-700" data-flag="out-of-range">
                        {t("work.order.readings.outOfRange")}
                      </span>
                    ) : null}
                  </td>
                )}
                {props.record && (
                  <td>
                    {photo !== undefined ? (
                      <PhotoThumb
                        orderId={props.orderId}
                        photo={photo}
                        onOpen={() => props.onOpenPhoto(photo.key)}
                      />
                    ) : missingPhoto ? (
                      <span className="block text-sm text-warning-700" data-flag="missing-photo">
                        {t("work.order.readings.photoMissing")}
                      </span>
                    ) : (
                      <Dash />
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </PlainTable>

      {props.record && ready !== undefined ? (
        <div className="mt-4 border-t border-divider pt-3">
          <p className="text-sm text-neutral-600" data-readings-footer="">
            {t("work.order.readings.footer", {
              captured: ready.readings_captured,
              total: ready.readings_total,
              photos: ready.required_photos_taken,
              photosTotal: ready.required_photos_total,
            })}
          </p>
          <p className="mt-2 text-sm text-neutral-700" data-consequence="work-order-readings">
            {t("work.order.readings.consequence")}
          </p>
        </div>
      ) : null}
    </>
  );
}

/** Image 07 — Part · Planned · Used. `2 each`, never `2.0000 each` (P1.18). */
export function OrderPartsTab(props: { list: OrderChecklist | undefined }) {
  const { t } = useTranslation();
  const rows = props.list?.materials ?? [];
  if (rows.length === 0) {
    return (
      <Panel title={t("work.order.parts.title")}>
        <Note>{t("work.order.parts.empty")}</Note>
      </Panel>
    );
  }
  return (
    <Panel title={t("work.order.parts.title")}>
      <PlainTable>
        <thead>
          <tr>
            <th>{t("work.order.parts.part")}</th>
            <th>{t("work.order.parts.planned")}</th>
            <th>{t("work.order.parts.used")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((material) => (
            <tr key={material.id} data-part-row={material.part_no}>
              <td>
                {material.part_no} · {material.part_name}
              </td>
              {/* Hard rule 3 — a quantity carries its unit, every time. */}
              <td>
                {quantityText(material.planned_qty)} {material.unit_of_measure}
              </td>
              <td>
                {material.used_qty === null ? (
                  <Dash />
                ) : (
                  `${quantityText(material.used_qty) ?? ""} ${material.unit_of_measure}`
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </Panel>
  );
}
