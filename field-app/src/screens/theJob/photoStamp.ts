/**
 * The words on a photograph: the stamp burned into its pixels at capture
 * (R94 — date, time, position with accuracy, who, which order, the utility)
 * and the same facts read back from its row for the review.
 *
 * A poor or absent fix warns and accepts (R91): no position is a stamp
 * without a position line, never a refused photograph.
 */
import type { TFunction } from 'i18next';

import type { OrderPhotoRow } from '../../db/queries/jobScreens';
import type { CaptureLocation } from '../../sync/outbox';
import type { PhotoStamp } from './camera';
import { dayMonthYear, hhmm, position } from './format';

function months(t: TFunction): string[] {
  return t('field.job.months').split(',');
}

export function stampLines(
  t: TFunction,
  fact: { at: string; lat: number | null; lng: number | null; accuracy: number | null; who: string; order: string; tenant: string },
): string[] {
  const where = position(fact.lat, fact.lng);
  const lines = [`${dayMonthYear(fact.at, months(t))} · ${hhmm(fact.at)}`];
  if (where) {
    lines.push(fact.accuracy !== null ? `${where} · ${t('field.job.accuracy', { metres: Math.round(fact.accuracy) })}` : where);
  }
  lines.push([fact.who, fact.order, fact.tenant].filter(Boolean).join(' · '));
  return lines;
}

/** The stamp handed to the camera pipeline, at the moment of capture. */
export function stampForCapture(
  t: TFunction,
  at: Date,
  location: CaptureLocation | null,
  who: string,
  order: string,
  tenant: string,
): PhotoStamp {
  return {
    lines: stampLines(t, {
      at: at.toISOString(),
      lat: location?.lat ?? null,
      lng: location?.lng ?? null,
      accuracy: location?.accuracy_m ?? null,
      who,
      order,
      tenant,
    }),
  };
}

/** The stamp's facts, read back from a photograph's row. */
export function stampOfRow(t: TFunction, photo: OrderPhotoRow, who: string, order: string, tenant: string): string[] {
  return stampLines(t, {
    at: photo.captured_at,
    lat: photo.lat,
    lng: photo.lng,
    accuracy: photo.accuracy_m,
    who,
    order,
    tenant,
  });
}

/** A photograph's file, while the handset still has it (R61: deleted on confirmed receipt). */
export function pathOf(photo: OrderPhotoRow): string | null {
  return photo.file_deleted ? null : photo.local_path;
}
