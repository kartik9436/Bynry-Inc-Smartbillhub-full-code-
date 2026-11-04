// ── Trace ──────────────────────────────────────────────
// Change:   DEF-MET-10633 — FB-003, the office half. PO ruling 2026-10-27
//           (decision log "FB-003: the position is captured automatically,
//           never by a button"): *"The office sees the position and its time;
//           a late one reads added at 18:35 beside the saved time."*
// Rules:    BR-MET-1202 (the phone's position at capture — evidence, never an
//           address) · B14 rules 31 (no photo id on screen), 33 (labels ≤ 3
//           words, facts ≤ 6, no rationale), 36/43 (the kit's Panel, built as a
//           component), 44 (our spacing and type)
//           · DEF-FLD-10637 (FB-019, PO 2026-10-28): a photo added on the
//           phone after the reading was saved is listed with it, marked
//           "Added after saving"
// Tests:    FieldPositionPanel.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * WHERE IT WAS READ — one information group on the reading's page, a `Panel`
 * like the ones beside it, served by `GET reads/{id}` → `field_capture`.
 *
 * Top to bottom: the position (taken at save, or — saved without one — the
 * late one with *added at* its own time), the time the reading was saved, then
 * each photograph's position the same way. A late position is shown as what it
 * is, a separate fact with its own time, never as if it were there at save.
 *
 * A read that did not come from a route reading renders NOTHING: a panel saying
 * so would be rationale (B14 rule 33).
 */
import { useTranslation } from "react-i18next";

import type { FieldCapture, FieldPosition } from "@/api/endpoints";
import { formatDate, type RegionalDateFormat } from "@/components/DateCell";
import { Panel } from "@/components/Panel";
import { Kicker } from "@/components/TextBits";

import { Dash } from "./meteringShared";

/** The page's own muted ink (ReadDetailPage's `MUTED60`). */
const MUTED60 = "text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]";

/** The wall-clock time of an instant in the utility's zone, 24-hour. */
export function clockIn(iso: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const part = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${part("hour")}:${part("minute")}`;
}

export function FieldPositionPanel(props: {
  capture: FieldCapture | null | undefined;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const capture = props.capture ?? null;
  if (capture === null) return null;
  return (
    <Panel as="section" title={<Kicker>{t("metering.read.panel.fieldPosition")}</Kicker>}>
      <dl className="met-facts text-sm leading-note" data-testid="field-position">
        <dt>{t("metering.read.field.position")}</dt>
        <dd className="flex flex-wrap items-center gap-2">
          <Point position={capture.position} timeZone={props.timeZone} testId="field-position" />
        </dd>
        <dt>{t("metering.read.field.saved")}</dt>
        <dd data-testid="field-position-saved">
          {capture.captured_at === null ? (
            <Dash />
          ) : (
            formatDate(capture.captured_at, props.timeZone, props.dateFormat, true)
          )}
        </dd>
        {capture.photos.map((photo, i) => (
          <PhotoRow
            key={photo.photo_id}
            n={i + 1}
            position={photo.position}
            addedAfterSave={photo.added_after_save === true}
            timeZone={props.timeZone}
          />
        ))}
      </dl>
    </Panel>
  );
}

function PhotoRow(props: { n: number; position: FieldPosition | null; addedAfterSave: boolean; timeZone: string }) {
  const { t } = useTranslation();
  return (
    <>
      <dt>{t("metering.read.field.photo", { n: props.n })}</dt>
      <dd className="flex flex-wrap items-center gap-2" data-testid="field-position-photo">
        <Point position={props.position} timeZone={props.timeZone} />
        {/* FB-019 (DEF-FLD-10637): added on the phone after the reading was saved. */}
        {props.addedAfterSave && (
          <span className={MUTED60} data-testid="field-position-photo-after">
            {t("metering.read.field.addedAfterSave")}
          </span>
        )}
      </dd>
    </>
  );
}

function Point(props: { position: FieldPosition | null; timeZone: string; testId?: string }) {
  const { t } = useTranslation();
  const p = props.position;
  const pointId = props.testId ? `${props.testId}-point` : undefined;
  const addedId = props.testId ? `${props.testId}-added` : undefined;
  if (p === null) {
    return <span data-testid={pointId}>{t("metering.read.field.none")}</span>;
  }
  const acc = p.accuracy_m === null ? null : Math.round(Number(p.accuracy_m));
  return (
    <>
      <span data-testid={pointId}>
        {acc === null
          ? `${p.lat}, ${p.lng}`
          : // The Work field desk's own words for a phone's position (one sentence, one key).
            t("work.field.position", { lat: p.lat, lng: p.lng, accuracy: acc })}
      </span>
      {p.added && p.at !== null && (
        <span className={MUTED60} data-testid={addedId}>
          {t("metering.read.field.addedAt", { time: clockIn(p.at, props.timeZone) })}
        </span>
      )}
    </>
  );
}
